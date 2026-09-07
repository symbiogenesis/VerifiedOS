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

Every module the wave compiled is then handed to `rocqchk`, the prover's own kernel
re-checker, in one invocation. R-05-016a licenses exactly this and says why it costs
no trust: a re-check can only reject, so a second implementation refusing a
kernel-checked term is a finding, and one accepting a term adds no ground the first did
not already give. **The honest limit is the same entry's**, and is booked here rather
than left for a reader to supply: `rocqchk` shares the kernel's lineage, and the
prover's own bug list records defects reaching that checker equally, so this is a
second reading and not independence. Nothing downstream may cite it as a second
implementation in R-05-016's sense.

The same run holds the decidable half of R-05-166. Each artifact states its obligations
over an arbitrary instance of a carrier record (`Machine`, `Composition`, `Plan`,
`Vocabulary`) whose fields are what the register leaves to composition, and a
quantifier over a record nobody builds is R-05-165's uninhabited-domain mode. So for
every record a file's theorem statements quantify over, the artifact carries a named
witness, a closed top-level `Definition witness_<Record> : <Record> := ...` in that file
or in one it Requires, and this gate looks that constant up rather than deciding
inhabitation itself. **The decision is the prover's**: the definition either type-checks
at the record or the compile above fails, so what is read here is a name and an
ascription, where reading a construction out of the text would be an approximation of a
type judgement. Whether a witness is non-trivial is a judgement the register books under
§17, not a check.

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

# The lexical half of this parse, promoted to `vos.proofs` when a second tool needed it
# and imported back under the name this module already used, so that the reading below
# is unchanged by the move. `a parse two tools make is written once` is that module's
# own convention and this is it applied to itself. `strip_comments` came back with it and
# is no longer imported here: its one consumer was the anywhere-matching witness search,
# which retired when the prover took the inhabitation judgement over.
from vos.proofs import sentences as _sentences

PROOFS = "proofs"
CLOSED = "Closed under the global context"

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
        description="Compile every shipped proof, re-check the compiled modules with "
                    "rocqchk, hold every assumption against the declared set "
                    "(R-05-163), and hold every record the theorems quantify over to a "
                    "named witness (R-05-166's decidable half).",
        epilog=f"The witness convention the artifacts follow is {WITNESS_CONVENTION}. "
               "The gate decides on the name and the ascription and never on the "
               "inhabitation, which the compile above decided by type-checking the "
               "definition; the witnesses it counts are the quantified records that "
               "carry one. Whether a witness is non-trivial is a judgement outside "
               "this gate, booked in the register's §17. The rocqchk pass is "
               "R-05-016a's re-check, which can only reject: it is a second reading "
               "of the same kernel lineage and not an independent one."
               ).parse_args(argv)

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
            print(f"FAIL: {source.name} quantifies over Record {record} and carries no "
                  f"witness for it (R-05-166): neither it nor a proof it Requires "
                  f"defines a closed `{WITNESS_PREFIX}{record} : {record}`")
        return 1

    # Last, because it is the expensive reading and every cheap one above decides
    # without it: a witness the artifacts do not carry is worth reporting in seconds
    # rather than after a re-check of the whole tree.
    rechecked = _recheck(root, sources)
    said = f"{rechecked.stdout}\n{rechecked.stderr}".strip()
    # Under -silent a clean re-check says nothing at all, so output is a rejection or a
    # diagnostic and neither passes beneath this gate, on the reading `_assumptions`
    # takes of the compiler's own chatter.
    if rechecked.returncode != 0 or said:
        print(f"FAIL: rocqchk did not re-check what the compiler accepted "
              f"(exit {rechecked.returncode}). R-05-016a: a re-check can only reject, "
              f"so a refusal here is a finding about the terms:")
        print(said or "it printed nothing and exited non-zero")
        return 1
    print(f"ok: {closed} constant(s), each closed under the global context and "
          f"re-checked by rocqchk, which shares the kernel's lineage and is a second "
          f"reading rather than an independent one; {witnessed} witness(es), one per "
          f"quantified record")
    return 0

