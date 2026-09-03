#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The R-05-163 assumption gate, wired ahead of the first closing theorem as R-05-168
requires.

It compiles every shipped proof artifact and compares the mechanically enumerated
assumption set of each constant the artifact prints (its trailing Print Assumptions
block) against the declared set, which R-05-164 reads from the register: the admission
axioms of R-06-011, the bootstrap root of R-06-014, and the Ax ledger of R-18-031(c).
None of those is authored yet, so the declared set is empty and the only passing output
is "Closed under the global context". When the register's declared set gains an entry,
this gate grows an allowlist read from it, never from the development.

An admitted lemma, an unresolved obligation, a locally declared parameter, or any axiom
fails this gate rather than shipping green.

The same run holds the decidable half of R-05-166. Each artifact states its obligations
over an arbitrary instance of a carrier record (`Machine`, `Composition`, `Plan`,
`Vocabulary`) whose fields are what the register leaves to composition, and a
quantifier over a record nobody builds is R-05-165's uninhabited-domain mode. So for
every record a file's theorem statements quantify over, the gate requires that the file
constructs one: a closed top-level definition typed at the record, which is the
`demo` convention every artifact follows, or failing that its `Build_` constructor or a
record literal opening with one of its fields anywhere in the source. The closed
definitions are the witnesses it counts beside each file's constants. Whether a
witness is non-trivial is a judgement the register books under §17, not a check.

Needs the pinned Rocq switch, which `vos.env` locates and which is deliberately not the
switch the Sail toolchain lives in. It is a guest command, so `python tools/run.py
proofs` on the host re-launches it there rather than refusing.
"""

import argparse
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from vos import env
from vos import proofs as proofs_mod
from vos.corpus import find_root

PROOFS = "proofs"
CLOSED = "Closed under the global context"

# The witness convention, read across the shipped artifacts and stated here so the help
# text can say what the gate reads. The inhabitant of a carrier record is a closed
# top-level Definition typed at it, named `demo` or a `demo_<variant>` / `<variant>_demo`
# of it (`demo_plan`, `demo_composition`, `l2_demo`; `trivial_vocabulary` for the apex
# statement), with the instances a refutation rejects as closed definitions of the same
# type beside it (`leaky_vocabulary`, `refusing_harmonic`, `over_margin_plan`). The gate
# decides on the shape, a closed definition typed at a quantified record, and never on
# the name, so a witness renamed is still a witness and a name without a construction
# behind it is not one.
WITNESS_CONVENTION = ("a closed top-level Definition typed at the carrier record, named "
                      "`demo` or a `demo_<variant>` of it, with each refuted instance a "
                      "closed definition of the same type beside it")

# The vernaculars whose sentence states a theorem, and so whose binders are the
# quantifiers this gate reads; and the ones whose sentence can define a closed term, and
# so can be a witness. `Example` is on both lists on purpose: it states and it defines.
STATEMENTS = ("Theorem", "Lemma", "Example", "Corollary", "Fact", "Remark", "Proposition")
DEFINERS = ("Definition", "Example", "Theorem", "Lemma", "Corollary", "Fact", "Instance")
# A section binder quantifies every statement in its section, so it is a quantifier too.
SECTION_BINDERS = ("Variable", "Variables", "Context", "Hypothesis", "Hypotheses")

# A Rocq sentence ends at a full stop followed by whitespace, which is what keeps
# `m.(field)` and `Nat.add` inside their sentence.
_SENTENCE_END = re.compile(r"\.(?=\s|$)")
_RECORD = re.compile(r"^(?:Record|Structure)\s+([\w']+)")
_DEFINER = re.compile(r"^(?:Program\s+)?(" + "|".join(DEFINERS) + r")\s+([\w']+)(.*)", re.DOTALL)
_SECTION_BINDER = re.compile(r"^(" + "|".join(SECTION_BINDERS) + r")\s+(.*)", re.DOTALL)
# `(x y : T)`, `{x : T}` and `forall x : T,` / `exists x : T,`: each names a type a
# variable ranges over.
_BINDER = re.compile(r"[({]\s*[\w']+(?:\s+[\w']+)*\s*:\s*([^)}]*)[)}]")
_QUANTIFIER = re.compile(r"\b(?:forall|exists)\s+[\w']+(?:\s+[\w']+)*\s*:\s*([^,]*),")
_HEAD = re.compile(r"^([\w']+)")
_BUILD = re.compile(r"\bBuild_([\w']+)\b")
_LITERAL = re.compile(r"\{\|\s*([\w']+)\s*:=")


@dataclass(frozen=True)
class Witnesses:
    """What one source's text says about the records its statements range over.

    `quantified` maps each such record to how many statements quantify it; `witnesses`
    maps a record to the closed definitions typed at it; `unbuilt` names the quantified
    records the source never constructs at all, which is the gate's finding.
    """

    quantified: dict[str, int] = field(default_factory=dict)
    witnesses: dict[str, list[str]] = field(default_factory=dict)
    unbuilt: list[str] = field(default_factory=list)

    @property
    def witness_count(self) -> int:
        return sum(len(names) for record, names in self.witnesses.items()
                   if record in self.quantified)


def _strip_comments(text: str) -> str:
    """The source with its comments blanked. Rocq comments nest, and a string literal
    outside one is kept whole so a `(*` inside it does not open one."""
    out: list[str] = []
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("(*", i):
            depth += 1
            i += 2
            continue
        if depth and text.startswith("*)", i):
            depth -= 1
            i += 2
            continue
        if depth == 0 and text[i] == '"':
            j = text.find('"', i + 1)
            j = n - 1 if j < 0 else j
            out.append(text[i:j + 1])
            i = j + 1
            continue
        if depth == 0 or text[i] == "\n":
            out.append(text[i])
        i += 1
    return "".join(out)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_END.split(_strip_comments(text)) if s.strip()]


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


def _record_fields(sentence: str) -> list[str]:
    """The field names a Record sentence declares, in order."""
    start = sentence.find("{")
    end = sentence.rfind("}")
    if start < 0 or end < start:
        return []
    names: list[str] = []
    depth = 0
    part: list[str] = []
    for ch in sentence[start + 1:end] + ";":
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == ";" and depth == 0:
            split = _split_top("".join(part), ":")
            if split is not None and split[0].strip():
                names.append(split[0].split()[0])
            part = []
        else:
            part.append(ch)
    return names


def scan_witnesses(text: str, imported: tuple[str, ...] = ()) -> Witnesses:
    """R-05-166's decidable half over one source.

    Records and constructions are read from the source and from the sources it Requires
    locally, because an artifact may state its obligations over a record a companion
    declares and inhabit it with the companion's witness; quantification is read from
    this source's own statements, which are the theorems it ships.
    """
    records: dict[str, list[str]] = {}
    witnesses: dict[str, list[str]] = {}
    built: set[str] = set()
    quantified: dict[str, int] = {}
    for index, source in enumerate((text, *imported)):
        own = index == 0
        for sentence in _sentences(source):
            record = _RECORD.match(sentence)
            if record:
                records[record.group(1)] = _record_fields(sentence)
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
            if binders.strip():
                continue
            head = _instance_head(typ)
            if head is not None:
                witnesses.setdefault(head, []).append(name)
        built |= {hit.group(1) for hit in _BUILD.finditer(source)}
        by_field = {name: record for record, names in records.items() for name in names}
        built |= {by_field[hit.group(1)] for hit in _LITERAL.finditer(source)
                  if hit.group(1) in by_field}

    ranged = {record: count for record, count in quantified.items() if record in records}
    unbuilt = sorted(record for record in ranged
                     if record not in witnesses and record not in built)
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


def _assumptions(stdout: str) -> tuple[int, list[str]]:
    """One compile's Print Assumptions output, read back block by block.

    An `Axioms:` header opens a block and is structure rather than a finding, and a
    wrapped axiom type's indented continuation lines belong to the entry above them,
    so an axiom compares against the declared set whole rather than line by line.
    Anything else the compiler printed is an entry too: chatter fails the gate rather
    than passing beneath it.
    """
    closed = 0
    entries: list[str] = []
    in_axioms = False
    for raw in stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line == CLOSED:
            closed += 1
            in_axioms = False
            continue
        if line == "Axioms:":
            in_axioms = True
            continue
        if in_axioms and raw[:1].isspace() and entries:
            entries[-1] += f" {line}"
            continue
        entries.append(line)
    return closed, entries


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(
        prog="run.py proofs",
        description="Compile every shipped proof, hold its assumptions against the "
                    "declared set (R-05-163), and hold every record its theorems "
                    "quantify over to a construction (R-05-166's decidable half).",
        epilog=f"The witness convention the artifacts follow is {WITNESS_CONVENTION}. "
               "The gate decides on the shape rather than the name: a record a file's "
               "statements quantify over must be constructed in that file or one it "
               "Requires, by a closed definition typed at it, by its Build_ constructor, "
               "or by a record literal opening with one of its fields; the closed "
               "definitions are the witnesses counted beside each file's constants. "
               "Whether a witness is non-trivial is a judgement outside this gate, "
               "booked in the register's §17.").parse_args(argv)

    root = find_root()
    proofs = root / PROOFS
    statement = proofs / STATEMENT
    if not statement.exists():
        print(f"FAIL: {PROOFS}/{STATEMENT} is not in the repository")
        return 1
    _hold(proofs)

    # Every source is compiled and every verdict kept, so a run with two broken proofs
    # reports two rather than whichever came first. The recompile is unconditional on
    # every run, fresh .vo or not: the Print Assumptions output produced during
    # compilation is the evidence this gate reads, and a skipped compile is a skipped
    # enumeration.
    failures: list[tuple[Path, str]] = []
    closed = 0
    undeclared: list[str] = []
    unbuilt: list[tuple[Path, str]] = []
    witnessed = 0
    lines: list[str] = []
    sources = sorted(proofs.glob("*.v"))
    for wave in proofs_mod.waves(sources):
        for source in wave:
            done = _compile(root, source)
            if done.returncode != 0:
                failures.append((source, done.stderr.strip()))
                continue
            enumerated, entries = _assumptions(done.stdout)
            closed += enumerated
            undeclared.extend(entry for entry in entries if entry not in DECLARED)
            found = scan_witnesses(source.read_text(encoding="utf-8"),
                                   _imported(source, sources))
            witnessed += found.witness_count
            unbuilt.extend((source, record) for record in found.unbuilt)
            lines.append(f"  {source.name}: {enumerated} constant(s), "
                         f"{found.witness_count} witness(es) over "
                         f"{len(found.quantified)} quantified record(s)")

    if failures:
        for source, stderr in failures:
            print(f"FAIL: {source.name} did not compile:\n{stderr}")
        return 1
    if undeclared:
        print("FAIL: an assumption outside the declared set, which is empty (R-05-164):")
        for entry in undeclared:
            print(entry)
        return 1
    if not closed:
        print("FAIL: no constant was enumerated; the artifact must end in Print Assumptions")
        return 1
    print("\n".join(lines))
    if unbuilt:
        for source, record in unbuilt:
            print(f"FAIL: {source.name} quantifies over Record {record} and never "
                  f"constructs one (R-05-166): no closed definition typed at it, no "
                  f"Build_{record}, no record literal opening with one of its fields")
        return 1
    print(f"ok: {closed} constant(s), each closed under the global context; "
          f"{witnessed} witness(es), every quantified record constructed")
    return 0

