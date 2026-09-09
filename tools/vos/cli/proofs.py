#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compile shipped proofs and audit the native environment, independent of footers.

The gate enumerates each module with Rocq Search after disabling both search filters,
then asks Print Assumptions about every returned symbol. This includes local lemmas,
nested modules and generated obligations. Claims must resolve to compiled propositions.
The existing record-witness check remains the decidable part of the non-vacuity gate.

Independent dependency-wave members run concurrently under one directory lock. Build
products are cleared before the wave, and failed dependencies block their consumers.
Every accepted module is rechecked by rocqchk before a content-bound JSON receipt is
written. `proofs status` checks that receipt on either host without invoking Rocq;
it records the guest toolchain identity and does not re-probe that guest from the host.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
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
RECEIPT_SCHEMA = 1

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
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif depth == 0 and text.startswith(mark, i):
            if mark == ":" and text[i + 1:i + 2] in ("=", ":", ">"):
                i += 1
                continue
            return text[:i], text[i + len(mark):]
        i += 1
    return None


def _has_top_arrow(text: str) -> bool:
    depth = 0
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif depth == 0 and text.startswith("->", i):
            return True
        i += 1
    return False


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
    records: set[str] = set()
    witnesses: dict[str, list[str]] = {}
    quantified: dict[str, int] = {}
    for index, source in enumerate((text, *imported)):
        own = index == 0
        for sentence in _sentences(source):
            record = _RECORD.match(sentence)
            if record:
                records.add(record.group(1))
                continue
            binder = _SECTION_BINDER.match(sentence)
            if binder and own:
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
            if own and keyword in STATEMENTS:
                for head in _quantified_heads(f"{binders} {typ}"):
                    quantified[head] = quantified.get(head, 0) + 1
            # A witness is a Definition, takes no argument, and is ascribed at the very
            # record its name claims: `witness_Plan : Plan` and, where the record is a
            # family, `witness_Installed : Installed demo_wx`, whose head is the record.
            # Each of the three is checked rather than assumed, so a `witness_Plan`
            # ascribed at something else is not a witness and says so by its absence.
            if keyword != "Definition" or not name.startswith(WITNESS_PREFIX):
                continue
            if binders.strip():
                continue
            claimed = name[len(WITNESS_PREFIX):]
            if _instance_head(typ) == claimed and name not in witnesses.get(claimed, []):
                witnesses.setdefault(claimed, []).append(name)

    ranged = {record: count for record, count in quantified.items() if record in records}
    unbuilt = sorted(record for record in ranged if record not in witnesses)
    return Witnesses(quantified=ranged, witnesses=witnesses, unbuilt=unbuilt)


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
    """Hold the proofs directory for the whole run.

    Two concurrent gates rewrite each other's .vo mid-Require, so the second blocks
    until the first is done, which the unconditional recompile then makes a correct
    second verdict rather than a stale one. The lock is the directory's own descriptor
    rather than a lock file, because everything this gate writes is gitignored and a
    lock file beside the proofs would be a tree write nothing owns. The descriptor
    stays open, and locked, until the process exits.

    POSIX-only, and this file is typed on the host as well as run in the guest, so the
    import is deferred the way `vos.env` defers its own.
    """
    import fcntl  # noqa: PLC0415
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


def _recheck(root: Path, sources: list[Path]) -> subprocess.CompletedProcess[str]:
    """Every compiled module handed to the kernel's own re-checker, in one invocation.

    One invocation over all of them rather than one per artifact, for a reason that is
    about what is decided and only then about cost. `rocqchk` loads a module's
    dependencies whichever way it is called, so per-artifact re-checks the shared ones
    once per dependent, and it builds **one** global environment out of what it was
    handed, so a single run is also the only one of the two shapes that decides the
    modules are consistent *together* rather than eighteen times apart. It was the
    faster shape as well when the two were timed against each other, though by a margin
    inside the run-to-run spread, so cost did not decide it.

    `-silent` suppresses the per-constant trace, which is a progress report rather than
    evidence; a rejection still prints. `-Q proofs ""` is the compile's own mapping, so
    a module is named by its bare stem exactly as the artifacts Require it.
    """
    return subprocess.run(
        [*env.rocqchk_command(), "-silent", "-Q", PROOFS, "",
         *(source.stem for source in sources)],
        cwd=root, capture_output=True, text=True, encoding="utf-8", check=False)


def _inputs(root: Path, sources: list[Path]) -> dict[str, str]:
    tools = root / "tools"
    owned = [tools / "run.py", tools / "vos" / "__init__.py",
             tools / "vos" / "cli" / "__init__.py", tools / "vos" / "env.py",
             tools / "vos" / "corpus.py", tools / "vos" / "register.py",
             tools / "vos" / "proofs.py", tools / "vos" / "proofcites.py",
             tools / "vos" / "proofaudit.py", tools / "vos" / "receipts.py",
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


def _check_source(root: Path, source: Path, sources: list[Path]) -> Checked:
    try:
        text = source.read_text(encoding="utf-8")
        unsupported = proofaudit.unsupported_abstractions(text)
        if unsupported:
            raise proofaudit.AuditError(
                "native inventory cannot enumerate inaccessible module bodies: "
                + "; ".join(unsupported))
        done = _compile(root, source)
        if done.returncode:
            raise proofaudit.AuditError(
                f"compile exited {done.returncode}: "
                f"{done.stderr.strip() or done.stdout.strip() or 'no diagnostic'}")
        with tempfile.TemporaryDirectory(prefix="vos-proof-audit-") as temporary:
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
        witnesses = scan_witnesses(text, _imported(source, sources))
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
    if version is None or version.group(1) != env.ROCQ_VERSION:
        raise proofaudit.AuditError(f"Rocq version differs from pin {env.ROCQ_VERSION}")
    return {"version": done.stdout.strip(), "pin": env.ROCQ_VERSION,
            "compiler": {"path": str(compiler), "sha256": receipts.digest(compiler)},
            "checker": {"path": str(checker), "sha256": receipts.digest(checker)}}


def _validate_receipt(root: Path) -> None:
    raw: object = json.loads((root / RECEIPT).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("receipt is not an object")
    record = cast("dict[str, object]", raw)
    if record.get("schema") != RECEIPT_SCHEMA or record.get("status") != "passed":
        raise ValueError("receipt has no supported successful verdict")
    sources = _sources(root)
    if record.get("inputs") != _inputs(root, sources):
        raise ValueError("proof inputs or proof-gate implementation have changed")
    outputs = receipts.snapshot(root, (source.with_suffix(".vo") for source in sources))
    if record.get("outputs") != outputs:
        raise ValueError("compiled proof artifacts have changed")
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {source.name for source in sources}:
        raise ValueError("receipt does not enumerate the current proof artifacts")
    total = 0
    for filename, artifact in artifacts.items():
        if not isinstance(filename, str) or not isinstance(artifact, dict):
            raise TypeError("malformed artifact identity")
        symbols = artifact.get("symbols")
        if not isinstance(symbols, list):
            raise TypeError(f"{filename} has no native symbol inventory")
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
        total += len(names)
    if not total:
        raise ValueError("receipt has no native symbols")
    toolchain = record.get("toolchain")
    if not isinstance(toolchain, dict) or toolchain.get("pin") != env.ROCQ_VERSION:
        raise ValueError("receipt does not identify the pinned toolchain")
    if record.get("declared_assumptions") != sorted(DECLARED):
        raise ValueError("receipt uses a different declared assumption set")
    if record.get("kernel_recheck") != "passed":
        raise ValueError("receipt has no successful kernel recheck")


def _status(root: Path) -> int:
    try:
        _validate_receipt(root)
    except (OSError, TypeError, ValueError) as err:
        print(f"FAIL: proof evidence is absent or stale: {err}; run `run.py proofs`")
        return 1
    else:
        print(f"ok: {RECEIPT} matches all current proof inputs and compiled outputs; "
              "the guest toolchain identity is recorded, not re-probed on the host")
        return 0


def _run_locked(root: Path, jobs: int) -> int:
    sources = _sources(root)
    inputs = _inputs(root, sources)
    toolchain = _toolchain()
    stems = {source.stem for source in sources}
    needs = {source.stem: proofs_mod.local_requires(source, stems) for source in sources}
    # Remove only this run's own build products, under the held proof directory.
    # Even an unrecognized dependency cannot consume a previous run's .vo.
    for source in sources:
        for suffix in (".vo", ".vos", ".vok"):
            source.with_suffix(suffix).unlink(missing_ok=True)
    (root / RECEIPT).unlink(missing_ok=True)
    checked: list[Checked] = []
    failed: set[str] = set()
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for wave in proofs_mod.waves(sources):
            ready: list[Path] = []
            for source in wave:
                blocked = needs[source.stem] & failed
                if blocked:
                    failed.add(source.stem)
                    checked.append(Checked(source, error="blocked by failed dependencies: "
                                           + ", ".join(sorted(blocked))))
                else:
                    ready.append(source)
            results = list(pool.map(lambda source: _check_source(root, source, sources), ready))
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
    rechecked = _recheck(root, sources)
    said = f"{rechecked.stdout}\n{rechecked.stderr}".strip()
    if rechecked.returncode or said:
        print(f"FAIL: rocqchk recheck (exit {rechecked.returncode}): "
              f"{said or 'no diagnostic'}")
        return 1
    if inputs != _inputs(root, sources) or toolchain != _toolchain():
        print("FAIL: proof inputs or the toolchain changed during the run")
        return 1
    outputs = receipts.snapshot(root, (source.with_suffix(".vo") for source in sources))
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
    receipts.write(root / RECEIPT, {
        "schema": RECEIPT_SCHEMA, "status": "passed", "inputs": inputs,
        "outputs": outputs, "toolchain": toolchain, "artifacts": artifacts,
        "declared_assumptions": sorted(DECLARED), "kernel_recheck": "passed"})
    print(f"ok: {total} constant(s), each enumerated by Rocq, closed under the "
          "global context and re-checked by rocqchk, which shares the kernel's "
          f"lineage; {witnessed} witness(es); evidence: {RECEIPT}")
    return 0


def _run(root: Path, jobs: int) -> int:
    proofs = root / PROOFS
    if not (proofs / STATEMENT).exists():
        print(f"FAIL: {PROOFS}/{STATEMENT} is not in the repository")
        return 1
    descriptor = _hold(proofs)
    try:
        result = _run_locked(root, jobs)
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
        description="Compile dependency waves concurrently; enumerate symbols, types "
                    "and assumptions through Rocq; validate claims and witnesses; "
                    "recheck with rocqchk and record content-bound evidence.")
    parser.add_argument("command", nargs="?", choices=("run", "status"), default="run")
    parser.add_argument("--jobs", type=int, default=min(4, os.process_cpu_count() or 1),
                        help="maximum concurrent proof jobs (default: at most four)")
    parsed = parser.parse_args(args)
    if parsed.jobs < 1:
        parser.error("--jobs must be positive")
    root = find_root()
    return _status(root) if parsed.command == "status" else _run(root, parsed.jobs)
