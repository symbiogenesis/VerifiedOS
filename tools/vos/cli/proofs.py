#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compile shipped proofs and audit the native environment, independent of footers.

The gate enumerates each module with Rocq Search after disabling both search filters,
then asks Print Assumptions about every returned symbol. This includes local lemmas,
nested modules and generated obligations. Claims must resolve to compiled propositions.
The existing record-witness check remains the decidable part of the non-vacuity gate.

Independent dependency-wave members run concurrently under one directory lock. Unchanged
compiled products are reused from successful receipts; changed dependencies invalidate
their consumers. Audits and kernel verdicts are reused for the same checked bytes.
A joint kernel environment checks changed modules against those checked dependencies;
--fresh disables all reuse. Sources are staged into this checkout's native guest build lane; compiler
outputs, audit scratch, the directory lock and full receipt stay there. Successful
runs also publish a portable receipt in the checkout. `proofs status` uses the guest
hop to hash native outputs; `proofs export` preserves an existing run without Rocq.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import cast

from vos import env, proofaudit, receipts
from vos import proofs as proofs_mod
from vos.corpus import find_root

# The lexical half of this parse, promoted to `vos.proofs` when a second tool needed it
# and imported back under the name this module already used, so that the reading below
# is unchanged by the move. `a parse two tools make is written once` is that module's
# own convention and this is it applied to itself. `strip_comments` came back with it and
# is no longer imported here: its one consumer was the anywhere-matching witness search,
# which retired when the prover took the inhabitation judgement over.
from vos.proofs import sentences as _sentences

PROOFS = "proofs"
RECEIPT = "proofs/proof-evidence.json"
RECEIPT_SCHEMA = 2


def workspace(root: Path) -> Path:
    """The persistent, guest-native area owned exclusively by this proof gate."""
    target = (env.lane_root(env.lane_of(root)) / "proof-gate").resolve()
    if (target.is_relative_to(root.resolve())
            # These are refused locations, never temporary-file destinations.
            or target.is_relative_to(Path("/tmp"))  # noqa: S108
            or target.is_relative_to(Path("/var/tmp"))  # noqa: S108
            or env.filesystem(target) in env.CROSS_OS_FILESYSTEMS | env.VOLATILE_FILESYSTEMS):
        raise ValueError(f"proof outputs need persistent native storage outside the checkout: {target}")
    return target


def receipt_path(root: Path) -> Path:
    return workspace(root) / RECEIPT

# The witness convention the artifacts keep, stated here so the help text can say what
# the gate reads. It is a *name*, and that is the whole of the change R-05-166's
# decidable half needed: the inhabitant of a carrier record R is a closed top-level
# `Definition witness_R : R := <term>`, whose term is usually an alias of the artifact's
# own reference instance (`demo`, `demo_plan`, `l2_demo`, `trivial_vocabulary`) and is
# a construction of its own where the artifact had none. The prover decides that the
# term inhabits the record, by type-checking the ascription during the compile above;
# this gate decides only that the constant is there and is ascribed at the record it
# names. A witness renamed is therefore no longer a witness, which is deliberate: the
# name is what makes the author's claim locatable, where a shape read out of the text
# was an approximation that admitted a construction sitting inside a hypothesis, a
# refuted example, or any term that never was a closed inhabitant.
WITNESS_PREFIX = "witness_"
WITNESS_CONVENTION = (f"a closed top-level `Definition {WITNESS_PREFIX}<Record> : "
                      "<Record> := ...` in the artifact or in one it Requires, whose "
                      "term is the artifact's own reference instance where it has one")

# The vernaculars whose sentence states a theorem, and so whose binders are the
# quantifiers this gate reads; and, beside them, every vernacular whose sentence carries
# a name and an ascription at all, which is the shape this parse walks. `Example` is on
# both lists on purpose: it states and it defines. Only `Definition` can be a witness,
# which the witness lookup requires of the keyword rather than of this table, so that
# widening the parse cannot widen what counts as an inhabitant.
STATEMENTS = ("Theorem", "Lemma", "Example", "Corollary", "Fact", "Remark", "Proposition")
DEFINERS = ("Definition", "Example", "Theorem", "Lemma", "Corollary", "Fact", "Instance")
# A section binder quantifies every statement in its section, so it is a quantifier too.
SECTION_BINDERS = ("Variable", "Variables", "Context", "Hypothesis", "Hypotheses")

_RECORD = re.compile(r"^(?:Record|Structure)\s+([\w']+)")
_DEFINER = re.compile(r"^(?:Program\s+)?(" + "|".join(DEFINERS) + r")\s+([\w']+)(.*)", re.DOTALL)
_SECTION_BINDER = re.compile(r"^(" + "|".join(SECTION_BINDERS) + r")\s+(.*)", re.DOTALL)
# `(x y : T)`, `{x : T}` and `forall x : T,` / `exists x : T,`: each names a type a
# variable ranges over.
_BINDER = re.compile(r"[({]\s*[\w']+(?:\s+[\w']+)*\s*:\s*([^)}]*)[)}]")
_QUANTIFIER = re.compile(r"\b(?:forall|exists)\s+[\w']+(?:\s+[\w']+)*\s*:\s*([^,]*),")
_HEAD = re.compile(r"^([\w']+)")
_TOP_DELIMITERS = {mark: re.compile(r"[()\[\]{}]|" + re.escape(mark))
                   for mark in (":", ":=", "->")}
_REQUIRE_TOKEN = re.compile(r"\bRequire\b")
_DYNAMIC_SOURCE = re.compile(
    r'^(?:(?:Local|Global|Time|Fail|Succeed)\s+|Timeout\s+\d+\s+'
    r'|Redirect\s+"[^"]*"\s+|#\[[^\]]*\]\s*)*'
    r'(?:Load|Cd|(?:Add|Remove)\s+(?:Rec\s+)?(?:LoadPath|ML\s+Path)'
    r'|Declare\s+ML\s+Module)\b')


@dataclass(frozen=True)
class Witnesses:
    """What one source's text says about the records its statements range over.

    `quantified` maps each such record to how many statements quantify it; `witnesses`
    maps a record to the named witness constants ascribed at it; `unbuilt` names the
    quantified records no witness inhabits, which is the gate's finding.
    """

    quantified: dict[str, int] = field(default_factory=dict)
    witnesses: dict[str, list[str]] = field(default_factory=dict)
    unbuilt: list[str] = field(default_factory=list)

    @property
    def witness_count(self) -> int:
        """How many of the quantified records carry a witness, counted over records
        rather than over names: one record reached both from the source and from a
        companion it Requires is one witnessed record and not two, so the figure this
        reports is comparable with the quantified count printed beside it."""
        return sum(1 for record in self.quantified if self.witnesses.get(record))


def _split_top(text: str, mark: str) -> tuple[str, str] | None:
    """`text` cut at the first `mark` outside every bracket, or None. A `:` is only
    the ascription colon when it is not the first character of `:=`, `::` or `:>`."""
    depth = 0
    # Skip ordinary text in the regex engine; only bracket and marker sites can
    # change the answer. Keep the lexical treatment of strings and nesting intact.
    for token in _TOP_DELIMITERS[mark].finditer(text):
        ch = token.group()
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif depth == 0:
            i = token.start()
            if mark == ":" and text[i + 1:i + 2] in ("=", ":", ">"):
                continue
            return text[:i], text[token.end():]
    return None


def _has_top_arrow(text: str) -> bool:
    return _split_top(text, "->") is not None


def _instance_head(typ: str) -> str | None:
    """The record a type ascription is an instance of: its head identifier, provided the
    type is not an arrow, a binder or a quantified statement, so `Machine -> Prop` and
    `forall m : Machine, P m` name no instance of `Machine`."""
    typ = typ.strip()
    if _has_top_arrow(typ):
        return None
    head = _HEAD.match(typ)
    if head is None:
        return None
    name = str(head.group(1))
    if name in ("forall", "exists", "fun", "let", "match"):
        return None
    return name


def _quantified_heads(text: str) -> set[str]:
    """Every record a binder or quantifier in `text` ranges a variable over."""
    found: set[str] = set()
    for pattern in (_BINDER, _QUANTIFIER):
        for hit in pattern.finditer(text):
            head = _instance_head(hit.group(1))
            if head is not None:
                found.add(head)
    return found


def scan_witnesses(text: str, imported: tuple[str, ...] = ()) -> Witnesses:
    """R-05-166's decidable half over one source.

    Two readings, and they are not the same kind of reading, which is why one of them
    is a lexical scan and the other is a lookup.

    **Which records are quantified** is read from this source's own statements, and
    over-approximating there is fail-loud: a binder this misreads as ranging over a
    record demands a witness the artifact then has to carry, so the error costs an
    author a line and never lets a vacuous theorem through.

    **Whether a record is inhabited** is not read at all. The artifact names its
    witness, `Definition witness_<Record> : <Record>`, and the compile that produced
    this file's assumption evidence is what decided the ascription holds; here it is a
    name and a head identifier. Under-approximating that is fail-loud in the same
    direction and over-approximating it was the defect: a construction matched anywhere
    in the text can sit inside a hypothesis, a refuted example or a term that never was
    a closed inhabitant, and a non-vacuity gate that over-approximates goes false green.

    Records and witnesses are read from the source and from the sources it Requires
    locally, because an artifact may state its obligations over a record a companion
    declares and inhabit it with the companion's witness.
    """
    return _combine_witnesses(_witness_facts(tuple(_sentences(text))),
                              tuple(_witness_facts(tuple(_sentences(source)))
                                    for source in imported))


@dataclass(frozen=True)
class _WitnessFacts:
    records: frozenset[str]
    witnesses: Mapping[str, tuple[str, ...]]
    quantified: Mapping[str, int]


def _witness_facts(statements: tuple[str, ...]) -> _WitnessFacts:
    """Parse a source's declarations once, before choosing an importing context."""
    records: set[str] = set()
    witnesses: dict[str, list[str]] = {}
    quantified: dict[str, int] = {}
    for sentence in statements:
        record = _RECORD.match(sentence)
        if record:
            records.add(record.group(1))
            continue
        binder = _SECTION_BINDER.match(sentence)
        if binder:
            for head in _quantified_heads(f"({binder.group(2)})"):
                quantified[head] = quantified.get(head, 0) + 1
            continue
        definer = _DEFINER.match(sentence)
        if not definer:
            continue
        keyword, name, rest = definer.groups()
        split = _split_top(rest, ":")
        if split is None:
            continue
        binders, typ = split
        body = _split_top(typ, ":=")
        if body is not None:
            typ = body[0]
        if keyword in STATEMENTS:
            for head in _quantified_heads(f"{binders} {typ}"):
                quantified[head] = quantified.get(head, 0) + 1
        # Only a closed, correctly ascribed Definition names a record witness.
        if keyword != "Definition" or not name.startswith(WITNESS_PREFIX) or binders.strip():
            continue
        claimed = name[len(WITNESS_PREFIX):]
        if _instance_head(typ) == claimed and name not in witnesses.get(claimed, []):
            witnesses.setdefault(claimed, []).append(name)
    return _WitnessFacts(frozenset(records), MappingProxyType(
        {record: tuple(names) for record, names in witnesses.items()}),
        MappingProxyType(quantified))


def _combine_witnesses(own: _WitnessFacts, imported: tuple[_WitnessFacts, ...]) -> Witnesses:
    records: set[str] = set()
    witnesses: dict[str, list[str]] = {}
    for source in (own, *imported):
        records.update(source.records)
        for record, names in source.witnesses.items():
            found = witnesses.setdefault(record, [])
            found.extend(name for name in names if name not in found)
    ranged = {record: count for record, count in own.quantified.items() if record in records}
    return Witnesses(quantified=ranged, witnesses=witnesses,
                     unbuilt=sorted(record for record in ranged if record not in witnesses))


@dataclass(frozen=True)
class ProofAnalysis:
    """Run-local lexical analysis shared by dependency scheduling and witness audits."""

    index: proofs_mod.SourceIndex
    witnesses: Mapping[Path, Witnesses]

    @classmethod
    def read(cls, sources: list[Path]) -> ProofAnalysis:
        index = proofs_mod.SourceIndex.read(sources)
        facts = {source: _witness_facts(parsed) for source, parsed in index.statements.items()}
        witnesses = {source: _combine_witnesses(own, tuple(facts[path] for path in index.imports[source]))
                     for source, own in facts.items()}
        return cls(index, MappingProxyType(witnesses))


def _imported(source: Path, sources: list[Path]) -> tuple[str, ...]:
    """The text of every proof this source reaches through a local Require."""
    stems = {candidate.stem: candidate for candidate in sources}
    reach: set[str] = set()
    frontier = proofs_mod.local_requires(source, set(stems))
    while frontier:
        stem = frontier.pop()
        if stem in reach:
            continue
        reach.add(stem)
        frontier |= proofs_mod.local_requires(stems[stem], set(stems))
    return tuple(stems[stem].read_text(encoding="utf-8") for stem in sorted(reach))

# The statement artifact, whose absence is reported by name: a gate over an empty
# directory would pass green with nothing enumerated to fail it.
STATEMENT = "ApexTheorem.v"

# The declared set, which R-05-164 reads from the register. It is empty today, and an
# entry is added here only when the register grows one, never to make a run pass.
DECLARED: set[str] = set()


def _hold(proofs: Path) -> int:
    """Hold the lane's native proof workspace for the whole run.

    Two concurrent gates rewrite each other's .vo mid-Require, so the second blocks
    until the first is done, when content identities determine reusable outputs.
    The lock is the directory's own descriptor
    rather than a lock file. Staged sources can then be replaced under that stable
    native directory without touching the original checkout. The descriptor
    stays open, and locked, until the process exits.

    POSIX-only, and this file is typed on the host as well as run in the guest, so the
    import is deferred the way `vos.env` defers its own.
    """
    import fcntl  # noqa: PLC0415
    proofs.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(proofs), os.O_RDONLY)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _compile(root: Path, source: Path) -> subprocess.CompletedProcess[str]:
    # -Q roots the logical path so a companion's Require Import resolves to the .vo
    # built here, never to an installed one
    return subprocess.run(
        [*env.rocq_command(), "-q", "-Q", PROOFS, "",
         source.relative_to(root).as_posix()],
        cwd=root, capture_output=True, text=True, encoding="utf-8", check=False)


def _recheck(root: Path, sources: list[Path],
             reused: frozenset[str] = frozenset()) -> subprocess.CompletedProcess[str]:
    """One joint environment, admitting only previously checked dependency closures.

    Rocq's -admit skips a root and its dependencies, except explicit check targets.
    A fresh, empty joining module requires ALL roots, including disconnected cached
    ones. This preserves joint consistency and makes every -admit root reachable.
    Changed roots are explicit targets, so no admission can accidentally skip them.
    No -norec or VM trust is used. The caller verifies bytes before and after this act.
    """
    command = [*env.rocqchk_command(), "-silent", "-Q", PROOFS, ""]
    changed = [source.stem for source in sources if source.stem not in reused]
    if not reused:
        return subprocess.run([*command, *changed], cwd=root, capture_output=True,
                              text=True, encoding="utf-8", check=False)
    with tempfile.TemporaryDirectory(prefix="kernel-", dir=root) as temporary:
        # Avoid collision with an authored module, even if it uses our usual name.
        name = "VerifiedOSProofClosure"
        stems = {source.stem for source in sources}
        while name in stems:
            name += "_"
        join = Path(temporary) / f"{name}.v"
        join.write_text("".join(f"Require {source.stem}.\n" for source in sources),
                        encoding="utf-8", newline="")
        compiled = _compile(root, join)
        if compiled.returncode or compiled.stderr.strip():
            return compiled
        return subprocess.run(
            [*command, str(join.with_suffix(".vo")), *changed,
             *(arg for stem in sorted(reused) for arg in ("-admit", stem))],
            cwd=root, capture_output=True, text=True, encoding="utf-8", check=False)


def _inputs(root: Path, sources: list[Path]) -> dict[str, str]:
    tools = root / "tools"
    owned = [tools / "run.py", tools / "vos" / "__init__.py",
             tools / "vos" / "cli" / "__init__.py", tools / "vos" / "env.py",
             tools / "vos" / "corpus.py", tools / "vos" / "register.py",
             tools / "vos" / "proofs.py", tools / "vos" / "proofcites.py",
             tools / "vos" / "proofaudit.py", tools / "vos" / "receipts.py",
             tools / "vos" / "toolenv.py", tools / "pyproject.toml", tools / "uv.lock",
             tools / "vos" / "cli" / "proofs.py",
             root / "docs" / "requirements-register.md"]
    return receipts.snapshot(root, [*sources, *owned])


def _sources(root: Path) -> list[Path]:
    """The complete supported source set, refusing silently omitted subdirectories."""
    folder = root / PROOFS
    sources = sorted(folder.rglob("*.v"))
    nested = [source.relative_to(root).as_posix() for source in sources
              if source.parent != folder]
    if nested:
        raise proofaudit.AuditError("nested proof source paths need namespace-aware "
                                   "dependency support and cannot be omitted: "
                                   + ", ".join(nested))
    return sources


def _query(root: Path, directory: Path, name: str, text: str) -> str:
    query = directory / f"{name}.v"
    query.write_text(text, encoding="utf-8", newline="")
    done = subprocess.run(
        [*env.rocq_command(), "-q", "-Q", str(root / PROOFS), "", str(query)],
        cwd=root, capture_output=True, text=True, encoding="utf-8", check=False)
    if done.returncode or done.stderr.strip():
        raise proofaudit.AuditError(
            f"{name} failed (exit {done.returncode}): "
            f"{done.stderr.strip() or done.stdout.strip() or 'no diagnostic'}")
    return done.stdout


@dataclass(frozen=True)
class Checked:
    source: Path
    symbols: list[proofaudit.Symbol] = field(default_factory=list)
    witnesses: Witnesses = field(default_factory=Witnesses)
    error: str = ""


def _check_source(root: Path, source: Path, sources: list[Path] | ProofAnalysis, *,
                  compiled: bool = False) -> Checked:
    try:
        text = (sources.index.texts[source] if isinstance(sources, ProofAnalysis)
                else source.read_text(encoding="utf-8"))
        unsupported = proofaudit.unsupported_abstractions(text)
        if unsupported:
            raise proofaudit.AuditError(
                "native inventory cannot enumerate inaccessible module bodies: "
                + "; ".join(unsupported))
        if not compiled:
            done = _compile(root, source)
            if done.returncode:
                raise proofaudit.AuditError(
                    f"compile exited {done.returncode}: "
                    f"{done.stderr.strip() or done.stdout.strip() or 'no diagnostic'}")
        with tempfile.TemporaryDirectory(prefix="audit-", dir=root) as temporary:
            directory = Path(temporary)
            output = _query(root, directory, "Inventory",
                            proofaudit.inventory_query(source.stem))
            symbols = proofaudit.inventory(output, source.stem)
            proofaudit.bind_claims(text, symbols)
            output = _query(root, directory, "Assumptions",
                            proofaudit.assumption_query(source.stem, symbols))
            proofaudit.assumptions(output, symbols)
        undeclared = [(symbol["name"], assumption) for symbol in symbols
                      for assumption in symbol["assumptions"] if assumption not in DECLARED]
        if undeclared:
            raise proofaudit.AuditError("undeclared assumptions: " + "; ".join(
                f"{name}: {assumption}" for name, assumption in undeclared))
        witnesses = (sources.witnesses[source] if isinstance(sources, ProofAnalysis)
                     else scan_witnesses(text, _imported(source, sources)))
        if witnesses.unbuilt:
            raise proofaudit.AuditError(
                "quantified records have no named witness: " + ", ".join(witnesses.unbuilt))
        return Checked(source, symbols, witnesses)
    except (OSError, ValueError) as err:
        return Checked(source, error=str(err))


def _toolchain() -> dict[str, object]:
    compiler = Path(env.rocq_command()[0]).resolve()
    checker = Path(env.rocqchk_command()[0]).resolve()
    done = subprocess.run([*env.rocq_command(), "--version"], capture_output=True,
                          text=True, encoding="utf-8", check=False)
    if done.returncode or not done.stdout.strip():
        raise proofaudit.AuditError("cannot identify the Rocq compiler version")
    version = re.search(r"\bversion\s+([^\s]+)", done.stdout)
    # Rocq 9.2.0 prints "9.2". Only a zero patch may be omitted: accepting an
    # arbitrary prefix would also admit prereleases or a different patch release.
    releases = {env.ROCQ_VERSION}
    if env.ROCQ_VERSION.endswith(".0"):
        releases.add(env.ROCQ_VERSION.removesuffix(".0"))
    if version is None or version.group(1) not in releases:
        raise proofaudit.AuditError(f"Rocq version differs from pin {env.ROCQ_VERSION}")
    return {"version": done.stdout.strip(), "pin": env.ROCQ_VERSION,
            "compiler": {"path": str(compiler), "sha256": receipts.digest(compiler)},
            "checker": {"path": str(checker), "sha256": receipts.digest(checker)}}


def _record_symbols(filename: str, artifact: object) -> list[proofaudit.Symbol]:
    """Validate cached native audit data before any of it can authorize reuse."""
    if not isinstance(artifact, dict) or not isinstance(artifact.get("symbols"), list):
        raise TypeError(f"{filename} has no native symbol inventory")
    symbols = artifact["symbols"]
    names: set[str] = set()
    for symbol in symbols:
        if not isinstance(symbol, dict):
            raise TypeError(f"{filename} carries a malformed symbol")
        name, typ = symbol.get("name"), symbol.get("type")
        if (not isinstance(name, str) or not name.startswith(Path(filename).stem + ".")
                or name in names or not isinstance(typ, str) or not typ):
            raise ValueError(f"{filename} carries an invalid native symbol or type")
        if symbol.get("assumptions") != []:
            raise ValueError(f"{name} has no closed assumption verdict")
        claims = symbol.get("claims")
        if not isinstance(claims, list) or any(not isinstance(c, str) for c in claims):
            raise ValueError(f"{name} has malformed claims")
        names.add(name)
    return cast("list[proofaudit.Symbol]", symbols)


def _kernel_evidence(record: dict[str, object], stems: set[str]) -> None:
    evidence = record.get("kernel_evidence")
    if not isinstance(evidence, dict):
        raise TypeError("receipt has no kernel coverage evidence")
    checked, reused = evidence.get("checked"), evidence.get("reused")
    if (not isinstance(checked, list) or not isinstance(reused, list)
            or any(not isinstance(name, str) for name in [*checked, *reused])
            or len(set(checked + reused)) != len(checked + reused)
            or set(checked + reused) != stems):
        raise ValueError("kernel evidence does not cover exactly the proof set")
    basis = evidence.get("basis_sha256")
    if reused:
        if (evidence.get("mode") != "incremental" or not isinstance(basis, str)
                or re.fullmatch(r"[0-9a-f]{64}", basis) is None):
            raise ValueError("incremental kernel evidence has no prior receipt identity")
    elif evidence.get("mode") != "full" or basis is not None:
        raise ValueError("full kernel evidence has an invalid reuse declaration")


def _validate_receipt(root: Path, *, historical: bool = False) -> None:
    work = workspace(root)
    raw: object = json.loads((work / RECEIPT).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("receipt is not an object")
    record = cast("dict[str, object]", raw)
    if record.get("schema") != RECEIPT_SCHEMA or record.get("status") != "passed":
        raise ValueError("receipt has no supported successful verdict")
    sources = _sources(work if historical else root)
    inputs = record.get("inputs")
    if not isinstance(inputs, dict):
        raise TypeError("receipt has no input manifest")
    if not historical and inputs != _inputs(root, sources):
        raise ValueError("proof inputs or proof-gate implementation have changed")
    staged = [work / PROOFS / source.name for source in sources]
    recorded_sources = {name: digest for name, digest in inputs.items()
                        if isinstance(name, str) and name.startswith(PROOFS + "/")}
    if receipts.snapshot(work, staged) != recorded_sources:
        raise ValueError("staged proof sources differ from the recorded inputs")
    outputs = receipts.snapshot(work, (source.with_suffix(".vo") for source in staged))
    if record.get("outputs") != outputs:
        raise ValueError("compiled proof artifacts have changed")
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {source.name for source in sources}:
        raise ValueError("receipt does not enumerate the current proof artifacts")
    total = 0
    for filename, artifact in artifacts.items():
        if not isinstance(filename, str) or not isinstance(artifact, dict):
            raise TypeError("malformed artifact identity")
        total += len(_record_symbols(filename, artifact))
    if not total:
        raise ValueError("receipt has no native symbols")
    toolchain = record.get("toolchain")
    if not isinstance(toolchain, dict) or toolchain.get("pin") != env.ROCQ_VERSION:
        raise ValueError("receipt does not identify the pinned toolchain")
    if record.get("declared_assumptions") != sorted(DECLARED):
        raise ValueError("receipt uses a different declared assumption set")
    if record.get("kernel_recheck") != "passed":
        raise ValueError("receipt has no successful kernel recheck")
    _kernel_evidence(record, {source.stem for source in sources})


def _json_digest(value: object) -> str:
    """Identity of a JSON value, independent of its on-disk indentation."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _portable_receipt(path: Path) -> dict[str, object]:
    """Project a validated native receipt without recording guest-specific paths."""
    raw = path.read_bytes()
    record = json.loads(raw)
    artifacts = {
        name: {"constants": len(artifact["symbols"]),
               "inventory_sha256": _json_digest(artifact["symbols"]),
               "requires": artifact["requires"], "witnesses": artifact["witnesses"]}
        for name, artifact in record["artifacts"].items()}
    toolchain = record["toolchain"]
    return {
        "format": "verifiedos-portable-proof-receipt", "schema": RECEIPT_SCHEMA,
        "native_receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "status": record["status"], "kernel_recheck": record["kernel_recheck"],
        "kernel_evidence": record["kernel_evidence"],
        "inputs": record["inputs"], "outputs": record["outputs"],
        "toolchain": {"pin": toolchain["pin"], "version": toolchain["version"],
                      "compiler_sha256": toolchain["compiler"]["sha256"],
                      "checker_sha256": toolchain["checker"]["sha256"]},
        "cache_context_sha256": _json_digest(record["cache_context"]),
        "declared_assumptions": record["declared_assumptions"],
        "artifacts": artifacts, "timings": record["timings"],
        "reused_compilations": record["reused_compilations"],
        "reused_audits": record["reused_audits"]}


def _publish_receipt(root: Path, *, check: bool = False) -> None:
    target = root / RECEIPT
    portable = _portable_receipt(receipt_path(root))
    if check:
        if json.loads(target.read_text(encoding="utf-8")) != portable:
            raise ValueError("portable receipt differs from the completed native run")
    else:
        receipts.write(target, portable)


def _export(root: Path, *, check: bool = False) -> int:
    """Export historical evidence, never changing its recorded input identities."""
    try:
        held = _hold(workspace(root))
        try:
            _validate_receipt(root, historical=True)
            _publish_receipt(root, check=check)
        finally:
            os.close(held)
    except (OSError, KeyError, TypeError, ValueError) as err:
        print(f"FAIL: proof evidence export: {err}")
        return 1
    print(f"ok: {root / RECEIPT} {'matches' if check else 'records'} the completed native run; "
          "original input hashes retained; current checkout freshness is not asserted")
    return 0


def _status(root: Path) -> int:
    try:
        held = _hold(workspace(root))
        try:
            _validate_receipt(root)
        finally:
            os.close(held)
    except (OSError, TypeError, ValueError) as err:
        print(f"FAIL: proof evidence is absent or stale: {err}; run `run.py proofs`")
        return 1
    else:
        print(f"ok: {receipt_path(root)} matches all current proof inputs and compiled outputs; "
              "the guest toolchain identity is recorded, not re-probed")
        return 0


def _cache_context(work: Path, sources: list[Path]) -> dict[str, object] | None:
    """Hash installed libraries and runtime files, including actual load paths.

    Unrecognized configurations disable caching, not checking. Dynamic source/ML
    loads can read undeclared inputs, so they cannot use this cache. File timestamps
    never stand in for bytes. Only shell launch bookkeeping and WSL's per-launch
    interop socket are excluded from the environment identity. Other irrelevant
    environment changes may cause extra work, but cannot preserve a stale hit.
    """
    source_sentences = [sentence for source in sources
                        for sentence in _sentences(source.read_text(encoding="utf-8"))]
    # Dependency parsing intentionally supports only plain Require sentences.
    # A wrapped Require must not hide an edge from incremental invalidation.
    if any("Require" in sentence and _REQUIRE_TOKEN.search(sentence)
           and not proofs_mod.REQUIRE.fullmatch(sentence)
           for sentence in source_sentences):
        return None
    if any(_DYNAMIC_SOURCE.match(sentence) for sentence in source_sentences):
        return None
    try:
        command = env.rocq_command()
        config = subprocess.run([*command, "-config"], cwd=work, capture_output=True,
                                text=True, encoding="utf-8", check=False)
        where = subprocess.run([*env.rocqchk_command(), "-where"], cwd=work,
                               capture_output=True, text=True, encoding="utf-8", check=False)
        paths = subprocess.run([*command[:-1], "top", "-q", "-quiet"], cwd=work,
                               input="Print LoadPath.\n", capture_output=True,
                               text=True, encoding="utf-8", check=False)
        if config.returncode or where.returncode or paths.returncode or not where.stdout.strip():
            return None
        settings = dict(line.split("=", 1) for line in config.stdout.splitlines() if "=" in line)
        roots = {Path(settings[key]).resolve() for key in ("COQLIB", "COQCORELIB")}
        roots.add(Path(where.stdout.strip()).resolve())
        listing = re.sub(r"\n\s+(/)", r" \1", paths.stdout).splitlines()
        if not listing or listing[0] != "Installed / Logical Path / Physical path:":
            return None
        for line in listing[1:]:
            found = re.fullmatch(r"\s*(?:i\s+)?(?:<>|[\w.]+)\s+(/.+)", line)
            if found is None:
                return None
            path = Path(found.group(1)).resolve()
            if path != work.resolve():
                roots.add(path)
        # Print LoadPath lists every subdirectory. Hash each tree only once.
        minimal = sorted(path for path in roots
                         if not any(path != other and path.is_relative_to(other) for other in roots))
        files: dict[str, str] = {}
        for directory in minimal:
            if not directory.is_dir():
                return None
            for path in sorted(directory.rglob("*")):
                if path.is_symlink() and path.is_dir():
                    return None
                if path.is_file():
                    files[str(path)] = receipts.digest(path)
        if not files:
            return None
        return {"files": files, "config": config.stdout,
                "load_path": paths.stdout,
                "environment_sha256": hashlib.sha256(
                    json.dumps({key: value for key, value in os.environ.items()
                                if key not in {"WSL_INTEROP", "SHLVL", "_"}},
                               sort_keys=True).encode("utf-8")).hexdigest()}
    except (OSError, ValueError, KeyError):
        return None


@dataclass(frozen=True)
class Cached:
    sha256: str
    symbols: list[proofaudit.Symbol]


def _cache_receipt(work: Path) -> Path:
    current = work / RECEIPT
    return current if current.is_file() else work / "previous-proof-evidence.json"


def _reusable(root: Path, work: Path, sources: list[Path], inputs: dict[str, str],
              toolchain: dict[str, object], context: dict[str, object] | None) -> dict[str, Cached]:
    """Reuse checked objects and audits only across identical prerequisite closures.

    Gate/toolchain changes invalidate all evidence. Register prose is recorded but
    is not a compiler or audit input: claims bind IDs from the source; their semantic
    agreement with requirements belongs to review and K-109. Adding/removing a source
    invalidates any changed local dependency resolution, not unrelated components.
    """
    try:
        if context is None:
            return {}
        raw: object = json.loads(_cache_receipt(work).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return {}
        record = cast("dict[str, object]", raw)
        previous, outputs, artifacts = (record.get("inputs"), record.get("outputs"),
                                        record.get("artifacts"))
        if (record.get("schema") != RECEIPT_SCHEMA or record.get("status") != "passed"
                or record.get("kernel_recheck") != "passed"
                or record.get("toolchain") != toolchain
                or record.get("cache_context") != context
                or record.get("declared_assumptions") != sorted(DECLARED)
                or not isinstance(previous, dict) or not isinstance(outputs, dict)
                or not isinstance(artifacts, dict)):
            return {}
        _kernel_evidence(record, {Path(name).stem for name in artifacts})

        def gate_inputs(values: Mapping[str, object]) -> dict[str, object]:
            return {name: value for name, value in values.items()
                    if not name.startswith(PROOFS + "/")
                    and name != "docs/requirements-register.md"}

        if gate_inputs(previous) != gate_inputs(inputs):
            return {}
        reusable: dict[str, Cached] = {}
        index = proofs_mod.SourceIndex.read(sources)
        for wave in index.ordered:
            for source in wave:
                name = source.relative_to(root).as_posix()
                staged = work / PROOFS / source.name
                product = staged.with_suffix(".vo")
                needs = {required.stem for required in index.needs[source]}
                artifact = artifacts.get(source.name)
                if (previous.get(name) == inputs[name]
                        and isinstance(artifact, dict)
                        and artifact.get("requires") == sorted(needs)
                        and needs <= reusable.keys()
                        and staged.is_file() and not staged.is_symlink()
                        and product.is_file() and not product.is_symlink()
                        and receipts.digest(staged) == inputs[name]
                        and (product_hash := receipts.digest(product))
                        == outputs.get(product.relative_to(work).as_posix())):
                    reusable[source.stem] = Cached(product_hash,
                                                    _record_symbols(source.name, artifact))
    except (OSError, ValueError, TypeError):
        return {}
    else:
        return reusable


def _run_locked(root: Path, jobs: int, fresh: bool = False) -> int:
    started = time.perf_counter()
    work = workspace(root)
    folder = work / PROOFS
    if folder.is_symlink():
        raise ValueError(f"proof staging directory must not be a symlink: {folder}")
    sources = _sources(root)
    inputs = _inputs(root, sources)
    toolchain = _toolchain()
    context = _cache_context(work, sources)
    reusable = {} if fresh else _reusable(root, work, sources, inputs, toolchain, context)
    if sources and len(reusable) == len(sources):
        try:
            _validate_receipt(root)
        except (OSError, TypeError, ValueError):
            pass
        else:
            if (inputs == _inputs(root, _sources(root)) and toolchain == _toolchain()
                    and context == _cache_context(work, sources)):
                _validate_receipt(root)
                _publish_receipt(root)
                print(f"ok: reused previous kernel evidence for {len(sources)} proof(s); "
                      f"all input, output and toolchain hashes match ({time.perf_counter() - started:.2f}s); "
                      f"evidence: {root / RECEIPT}; use --fresh to rebuild and recheck")
                return 0
    basis = receipts.digest(_cache_receipt(work)) if reusable else None
    # Keep the last success as cache input, never as today's status. Failed runs
    # preserve unchanged staged objects, whose bytes this receipt can still bind.
    # Changed/absent outputs and their consumers must earn new evidence on retry.
    if reusable and (work / RECEIPT).is_file():
        (work / RECEIPT).replace(work / "previous-proof-evidence.json")
    (work / RECEIPT).unlink(missing_ok=True)
    # This private staging directory is the only subtree the gate replaces. The
    # lock lives in its parent, so replacing it never releases another gate.
    with tempfile.TemporaryDirectory(prefix="stage-", dir=work) as temporary:
        replacement = Path(temporary) / PROOFS
        replacement.mkdir()
        for source in sources:
            shutil.copyfile(source, replacement / source.name)
            if source.stem in reusable:
                product = source.with_suffix(".vo").name
                shutil.copyfile(folder / product, replacement / product)
                if receipts.digest(replacement / product) != reusable[source.stem].sha256:
                    raise ValueError(f"cached object changed while being staged: {product}")
        if folder.exists():
            shutil.rmtree(folder)
        replacement.replace(folder)
    staged = [folder / source.name for source in sources]
    source_inputs = {source.relative_to(root).as_posix(): inputs[source.relative_to(root).as_posix()]
                     for source in sources}
    if receipts.snapshot(work, staged) != source_inputs:
        raise ValueError("proof sources changed while being staged")
    compile_started = time.perf_counter()
    analysis = ProofAnalysis.read(staged)
    needs = {source.stem: {required.stem for required in required_sources}
             for source, required_sources in analysis.index.needs.items()}
    checked: list[Checked] = []
    failed: set[str] = set()

    def check(source: Path) -> Checked:
        if source.stem in reusable:
            return Checked(source, reusable[source.stem].symbols,
                           analysis.witnesses[source])
        return _check_source(work, source, analysis)

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for wave in analysis.index.ordered:
            ready: list[Path] = []
            for source in wave:
                blocked = needs[source.stem] & failed
                if blocked:
                    source.with_suffix(".vo").unlink(missing_ok=True)
                    failed.add(source.stem)
                    checked.append(Checked(source, error="blocked by failed dependencies: "
                                           + ", ".join(sorted(blocked))))
                else:
                    ready.append(source)
            results = list(pool.map(check, ready))
            checked.extend(results)
            failed.update(item.source.stem for item in results if item.error)
    if failed:
        for item in sorted(checked, key=lambda item: item.source.name):
            if item.error:
                print(f"FAIL: {item.source.name}: {item.error}")
        return 1
    total = sum(len(item.symbols) for item in checked)
    if not total:
        print("FAIL: native Rocq inventory contains no compiled constant")
        return 1
    compile_seconds = time.perf_counter() - compile_started
    outputs = receipts.snapshot(work, (source.with_suffix(".vo") for source in staged))
    if any(outputs[f"{PROOFS}/{stem}.vo"] != cached.sha256
           for stem, cached in reusable.items()):
        print("FAIL: previously checked object changed during compilation or auditing")
        return 1
    recheck_started = time.perf_counter()
    print(f"  compile/audit: {compile_seconds:.2f}s; "
          f"{len(reusable)}/{len(staged)} compiled objects and audits reused; "
          f"starting {'incremental' if reusable else 'full'} kernel recheck", flush=True)
    rechecked = _recheck(work, staged, frozenset(reusable))
    recheck_seconds = time.perf_counter() - recheck_started
    said = f"{rechecked.stdout}\n{rechecked.stderr}".strip()
    if rechecked.returncode or said:
        print(f"FAIL: rocqchk recheck (exit {rechecked.returncode}): "
              f"{said or 'no diagnostic'}")
        return 1
    if (inputs != _inputs(root, _sources(root)) or toolchain != _toolchain()
            or context != _cache_context(work, sources)
            or receipts.snapshot(work, staged) != source_inputs
            or outputs != receipts.snapshot(work, (source.with_suffix(".vo") for source in staged))):
        print("FAIL: proof inputs, compiled outputs or the toolchain changed during the run")
        return 1
    artifacts: dict[str, object] = {}
    witnessed = 0
    for item in sorted(checked, key=lambda item: item.source.name):
        witnesses = item.witnesses.witness_count
        witnessed += witnesses
        artifacts[item.source.name] = {
            "symbols": item.symbols,
            "requires": sorted(needs[item.source.stem]),
            "witnesses": item.witnesses.witnesses}
        print(f"  {item.source.name}: {len(item.symbols)} constant(s), "
              f"{witnesses} witness(es) over "
              f"{len(item.witnesses.quantified)} quantified record(s)")
    receipts.write(work / RECEIPT, {
        "schema": RECEIPT_SCHEMA, "status": "passed", "inputs": inputs,
        "outputs": outputs, "toolchain": toolchain, "artifacts": artifacts,
        "cache_context": context,
        "declared_assumptions": sorted(DECLARED), "kernel_recheck": "passed",
        "kernel_evidence": {"mode": "incremental" if reusable else "full",
                            "checked": sorted(source.stem for source in sources
                                              if source.stem not in reusable),
                            "reused": sorted(reusable), "basis_sha256": basis},
        "timings": {"compile_audit_seconds": compile_seconds,
                    "kernel_recheck_seconds": recheck_seconds,
                    "total_seconds": time.perf_counter() - started},
        "reused_compilations": len(reusable), "reused_audits": len(reusable)})
    _publish_receipt(root)
    print(f"  kernel recheck: {recheck_seconds:.2f}s; "
          f"total: {time.perf_counter() - started:.2f}s")
    print(f"ok: {total} constant(s), each enumerated by Rocq, closed under the "
          "global context and re-checked by rocqchk, which shares the kernel's "
          f"lineage; {witnessed} witness(es); evidence: {root / RECEIPT}; "
          f"full native receipt: {work / RECEIPT}")
    return 0


def _run(root: Path, jobs: int, fresh: bool = False) -> int:
    proofs = root / PROOFS
    if not (proofs / STATEMENT).exists():
        print(f"FAIL: {PROOFS}/{STATEMENT} is not in the repository")
        return 1
    try:
        descriptor = _hold(workspace(root))
    except (OSError, ValueError) as err:
        print(f"FAIL: proof gate: {err}")
        return 1
    try:
        result = _run_locked(root, jobs, fresh)
    except (OSError, ValueError) as err:
        print(f"FAIL: proof gate: {err}")
        return 1
    else:
        return result
    finally:
        os.close(descriptor)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "headers":
        from vos import proofheaders  # noqa: PLC0415
        return proofheaders.main(args[1:])
    parser = argparse.ArgumentParser(
        prog="run.py proofs",
        description="Reuse content-matched proof evidence or compile dependency waves "
                    "incrementally and concurrently; enumerate symbols, types "
                    "and assumptions through Rocq; validate claims and witnesses; "
                    "recheck with rocqchk and record content-bound evidence.")
    parser.add_argument("command", nargs="?", choices=("run", "status", "export"), default="run")
    parser.add_argument("--check", action="store_true",
                        help="with export, compare the portable receipt without writing")
    parser.add_argument("--jobs", type=int, default=min(4, os.process_cpu_count() or 1),
                        help="maximum concurrent proof jobs (default: at most four)")
    parser.add_argument("--fresh", action="store_true",
                        help="recompile every source and run a fresh full kernel recheck")
    parsed = parser.parse_args(args)
    if parsed.jobs < 1:
        parser.error("--jobs must be positive")
    if parsed.check and parsed.command != "export":
        parser.error("--check requires export")
    if parsed.fresh and parsed.command != "run":
        parser.error("--fresh requires run")
    root = find_root()
    if parsed.command == "export":
        return _export(root, check=parsed.check)
    return _status(root) if parsed.command == "status" else _run(root, parsed.jobs, parsed.fresh)
