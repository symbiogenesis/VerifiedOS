# SPDX-License-Identifier: Apache-2.0
"""Check the differential corpus manifest, documentation, assembly programs, and RVFI schema (`K-50`, `K-51`, `K-71`, `K-72`, `K-85`).

- `K-50` checks bidirectional membership between
  [corpus/manifest.json](../../../corpus/manifest.json) and
  [docs/assurance/differential-corpus.md](../../../docs/assurance/differential-corpus.md).
- `K-51` assembles every corpus program via [vos/asm.py](../asm.py), verifies its
  recorded check count, and requires a non-empty commit-trace digest. (Actual digest
  reproduction requires the emulator and runs under `run.py model corpus`.)
- `K-71` checks that `trace_schema` in
  [corpus/manifest.json](../../../corpus/manifest.json) matches the version stated in
  §4's heading of [docs/assurance/differential-corpus.md](../../../docs/assurance/differential-corpus.md).
- `K-72` checks that every `.word` directive in the corpus is enumerated in §3 of
  [docs/assurance/differential-corpus.md](../../../docs/assurance/differential-corpus.md)
  and that assembling the documented reading agrees with the stated ground (`cannot`,
  `refuses`, or `reader`).
- `K-85` checks that the commit-trace record kinds declared in §4 are partitioned by
  §9's meeting and elision tables and match the kinds emitted by
  [`records`](../rvfi.py#records) and dropped by [`packet_view`](../rvfi.py#packet_view).
"""

import json
import posixpath
import re
from typing import TYPE_CHECKING

from vos import asm, differential, rvfi

if TYPE_CHECKING:
    from . import Context

HEADING = "=== differential: the corpus manifest, its document, and its programs ==="

DOC = "docs/assurance/differential-corpus.md"
CORPUS_LINK = posixpath.relpath(differential.CORPUS_DIR, posixpath.dirname(DOC))

# §4 heading declaring the commit-trace schema version.
_SCHEMA_HEADING_RE = re.compile(
    r"(?m)^## (\d+)\. The commit-trace schema, version (\d+)\s*$")


def run(ctx: Context) -> None:
    rep, root = ctx.rep, ctx.root
    rep.line(HEADING)

    try:
        corpus = differential.load(root)
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        # TypeError is a manifest whose members is not the list of row mappings the
        # parse iterates, which is as unreadable as a row missing a key
        rep.report("K-50", "corpus manifest(s) unreadable:",
                   [f"{differential.CORPUS_DIR}/{differential.MANIFEST}: {exc}"],
                   "the corpus manifest parses")
        rep.report("K-51", "corpus member(s) that do not assemble:", [],
                   "no members to assemble")
        # the manifest is the rule's other side, so an unreadable one is a finding
        # rather than a rule that quietly does not run
        _schema(ctx, None)
        # K-85 reads the document and the code and never the manifest, so it runs on
        # this path too: a manifest that stopped parsing must not take down a rule
        # whose two sides are both still there to be held against each other
        _record_kinds(ctx)
        rep.line()
        return

    ctx.shared["corpus_members"] = corpus.members

    # Membership, both directions. The document names a member by linking its
    # source, which is the one spelling that cannot drift from the manifest's
    # while still resolving: the links group already holds the link itself.
    doc = ctx.text(DOC)
    described = {m.name for m in corpus.members
                 if f"({CORPUS_LINK}/{m.source})" in doc}
    listed = {m.name for m in corpus.members}
    linked = _linked_sources(doc)
    gaps = [f"{name} is in the manifest and {DOC} does not carry it"
            for name in sorted(listed - described)]
    gaps += [f"{DOC} carries {source}, which the manifest does not list"
             for source in sorted(linked - {m.source for m in corpus.members})]
    rep.report("K-50", "corpus member(s) in one artifact and not the other:", gaps,
               f"all {len(corpus.members)} members are listed and described")

    # Every member assembles, and the checks it declares are the checks it has.
    faults = []
    for member in corpus.members:
        source = corpus.source(member)
        if not source.is_file():
            faults.append(f"{member.name}: {member.source} is not in the repository")
            continue
        text = source.read_text(encoding="utf-8")
        try:
            assembler = asm.Assembler(text, member.source)
            assembler.assemble()
        except asm.AsmError as exc:
            # the assembler's own diagnostic and nothing broader: any other exception
            # is a defect in the checker, which crashes loudly rather than reading as
            # one more corpus finding
            faults.append(f"{member.name}: {exc}")
            continue
        checks = differential.count_checks(text)
        if checks != member.checks:
            faults.append(f"{member.name}: the manifest records {member.checks} checks "
                          f"and the program carries {checks}")
        if not member.digest:
            faults.append(f"{member.name}: no commit-trace digest; run "
                          f"`run.py model corpus --refresh`")
    rep.report("K-51", "corpus member(s) that do not assemble as recorded:", faults,
               f"all {len(corpus.members)} members assemble, with "
               f"{sum(m.checks for m in corpus.members)} checks and a recorded digest")

    _schema(ctx, corpus.trace_schema)
    _hand_written_words(ctx, corpus, doc)
    _record_kinds(ctx)
    rep.line()


def _schema(ctx: Context, declared: int | None) -> None:
    """K-71: the manifest's trace_schema is the version the document's §4 heading states.

    Fail-closed on the reading itself, in the shape used for the tools' own
    pins: the manifest's field and the heading either answer in the form written
    today or are findings, so a reworded heading takes the comparison down loudly
    instead of leaving the rule green over a version nothing states.
    """
    rep = ctx.rep
    findings: list[str] = []
    manifest = f"{differential.CORPUS_DIR}/{differential.MANIFEST}"
    section, stated = "", ""

    if declared is None:
        findings.append(f"{manifest} does not state a trace_schema this rule can read")

    m = _SCHEMA_HEADING_RE.search(ctx.text(DOC))
    if m is None:
        findings.append(f"{DOC} no longer states the commit-trace schema's version in "
                        "its section heading, in a form this rule reads")
    else:
        section, stated = m.group(1), m.group(2)
        if declared is not None and stated != str(declared):
            findings.append(f"{DOC}'s §{section} heading states version {stated}, "
                            f"{manifest} declares trace_schema {declared}")

    rep.report("K-71", "commit-trace schema version(s) the document and the manifest "
               "disagree on:", findings,
               f"{DOC}'s §{section} heading states commit-trace schema version "
               f"{stated}, the grammar {manifest} declares")


# The three grounds §3 admits, keyed by the word the Ground cell leads with, and
# what each one says the encoder does with the reading beside it. `False` is the
# ground that expires: the encoder must not build the word, and the day a row
# lands that does, this rule is what says so.
GROUNDS = {"cannot": False, "refuses": False, "reader": True}

# One row of §3's table: the member's link, the word, the ground, and the reading.
_ROW = re.compile(
    r"^\| \[(?P<member>[\w-]+)\]\(" + re.escape(CORPUS_LINK)
    + r"/(?P<source>[\w.-]+)\) "
    r"\| `0x(?P<word>[0-9A-Fa-f]{8})` "
    r"\| (?P<ground>[^|]+?) "
    r"\| `(?P<reading>[^`]+)` \|$", re.MULTILINE)


def _hand_written_words(ctx: Context, corpus: differential.Corpus, doc: str) -> None:
    """K-72: every `.word` in a member is enumerated, on a ground the encoder agrees to."""
    rep = ctx.rep
    declared: dict[tuple[str, int], tuple[str, str]] = {}
    faults = []

    for row in _ROW.finditer(doc):
        key = (row["source"], int(row["word"], 16))
        # The ground is prose and the keyword is what carries it, so the cell is read
        # by which keyword it contains and a cell containing two is as unreadable as
        # one containing none: this rule reports rather than guesses.
        words = set(row["ground"].split())
        named = sorted(words & GROUNDS.keys())
        if len(named) != 1:
            faults.append(f"{DOC}: 0x{row['word']} in {row['source']} states the ground "
                          f"\"{row['ground'].strip()}\", which names "
                          + ("none" if not named else f"{len(named)}")
                          + " of the three §3 admits")
            continue
        declared[key] = (named[0], row["reading"])

    # Both directions over the corpus's own sources, so a word added to a member
    # and never enumerated is a finding, and so is a row for a word that has gone.
    found: set[tuple[str, int]] = set()
    for member in corpus.members:
        source = corpus.source(member)
        if not source.is_file():
            continue
        for text in differential.hand_written_words(source.read_text(encoding="utf-8")):
            try:
                found.add((member.source, int(text, 0)))
            except ValueError:
                faults.append(f"{member.source} writes `.word {text}`, an operand this "
                              f"rule cannot read as a number")
    faults += [f"{source} writes 0x{word:08X} by hand and {DOC} does not enumerate it"
               for source, word in sorted(found - set(declared))]
    faults += [f"{DOC} enumerates 0x{word:08X} in {source}, which no longer writes it"
               for source, word in sorted(set(declared) - found)]

    # And the ground itself, decided against the encoder rather than asserted.
    for (source, word), (lead, reading) in sorted(declared.items()):
        built = _encode(reading)
        builds = built == word
        if builds is not GROUNDS[lead]:
            faults.append(
                f"{source}: 0x{word:08X} stands on \"{lead}\" and the encoder "
                + (f"builds it from `{reading}`, so that ground has expired"
                   if builds else
                   f"answers `{reading}` with "
                   + ("a refusal" if built is None else f"0x{built:08X}")
                   + ", which is not the word the member writes"))

    rep.report("K-72", "hand-written corpus word(s) unenumerated or on a stale ground:",
               faults, f"all {len(declared)} hand-written words are enumerated on a "
                       f"ground the encoder agrees to")


def _encode(reading: str) -> int | None:
    """The word the encoder builds from one instruction, or None where it refuses.

    A refusal is an answer rather than an error here, which is why the reading is
    assembled in isolation: a whole member would report the first fault anywhere
    in it, and what this asks about is one line.
    """
    try:
        assembler = asm.Assembler(f"        .text\n_start:\n        {reading}\n", "<reading>")
        sections, _symbols, _entry = assembler.assemble()
    except asm.AsmError:
        return None
    data = b"".join(section.data for section in sections)
    return int.from_bytes(data[:4], "little") if len(data) >= 4 else None


# §9's two tables, located by their own headings. The section numbers are wildcards
# for the reason the version heading above gives: renumbering is not this rule's
# subject, and a heading that no longer answers in the form written today is a finding
# rather than a table read as empty.
_MEET_HEADING_RE = re.compile(
    r"(?m)^### (\d+\.\d+) Where the packet and §\d+'s record meet[^\r\n]*$")
_ELIDE_HEADING_RE = re.compile(r"(?m)^### (\d+\.\d+) Where they do not[ \t]*$")

# A table row whose first cell is one record kind. Single letters and nothing else,
# which is what leaves §9.3's three further rows outside the rule: `order` is a field,
# and the other two name a count and an ordering rather than a kind.
_KIND_ROW_RE = re.compile(r"(?m)^\| `([A-Z])` \|")

# One packet with every branch of the projection taken at once: a destination register
# write, a memory read and a memory write. Nothing here is a trace and no value decides
# anything; only the branches do, so what this yields is the set of record kinds the
# projection can emit at all.
_MAXIMAL = rvfi.Execution(wire=2, rd_addr=1, mem_rmask=0xFF, mem_wmask=0xFF,
                          integer_present=True, memory_present=True)


def _section(doc: str, heading: re.Match[str]) -> str:
    """The body under one heading, bounded at the next heading of any depth.

    Required rather than tidy: the record kinds are spelled identically in §4 and in
    both §9 tables, so a row pattern run over the whole document answers with
    whichever table carries that letter first instead of with the one being read.
    """
    rest = doc[heading.end():]
    nxt = re.search(r"(?m)^#", rest)
    return rest[:nxt.start()] if nxt else rest


def _kinds(section: str) -> set[str]:
    return {m.group(1) for m in _KIND_ROW_RE.finditer(section)}


def _record_kinds(ctx: Context) -> None:
    """K-85: §4's record kinds, split by §9's two tables, and the split the code makes.

    Three readings held together rather than two, because the split is written a third
    time in `rvfi.py` and that third copy is the one an executor is adjudicated
    through. The code side is decided by calling both functions, so what the rule holds
    is what the projection does and not what a pattern says about its source.
    """
    rep = ctx.rep
    doc = ctx.text(DOC)
    findings: list[str] = []
    declared: set[str] = set()
    meets: set[str] = set()
    elides: set[str] = set()

    # Fail-closed at each heading, on K-71's ground: a section this rule cannot find
    # leaves its set empty, and an empty set satisfies every membership vacuously.
    schema = _SCHEMA_HEADING_RE.search(doc)
    if schema is None:
        findings.append(f"{DOC} states no commit-trace schema heading this rule can "
                        "find, so the record kinds it declares are read from nothing")
    else:
        declared = _kinds(_section(doc, schema))

    meet = _MEET_HEADING_RE.search(doc)
    if meet is None:
        findings.append(f"{DOC} states no heading for the table of records the packet "
                        "meets, in a form this rule reads")
    else:
        meets = _kinds(_section(doc, meet))

    elide = _ELIDE_HEADING_RE.search(doc)
    if elide is None:
        findings.append(f"{DOC} states no heading for the table of records the packet "
                        "elides, in a form this rule reads")
    else:
        elides = _kinds(_section(doc, elide))

    findings += [f"{DOC} declares the `{kind}` record and §9 both meets and elides it"
                 for kind in sorted(meets & elides)]
    findings += [f"{DOC} declares the `{kind}` record and §9 neither meets nor elides it"
                 for kind in sorted(declared - meets - elides)]
    findings += [f"{DOC}'s meeting table carries `{kind}`, which its schema table does "
                 "not declare" for kind in sorted(meets - declared)]
    findings += [f"{DOC}'s elision table carries `{kind}`, which its schema table does "
                 "not declare" for kind in sorted(elides - declared)]

    produced = {record[0] for record in rvfi.records(_MAXIMAL)}
    findings += [f"rvfi.records emits the `{kind}` record and {DOC}'s meeting table "
                 "does not carry it" for kind in sorted(produced - meets)]
    findings += [f"{DOC}'s meeting table carries `{kind}` and rvfi.records never emits "
                 "it" for kind in sorted(meets - produced)]

    # One record of every kind §4 declares, so the stream is the document's enumeration
    # rather than a list written here beside it.
    try:
        view, _elided = rvfi.packet_view([f"{kind} 0" for kind in sorted(declared)])
    except KeyError as exc:
        # A kind added to §4 with no branch in the packet view raises exactly here, and
        # that is the drift this rule exists to catch: it is reported at the checker,
        # where the document is being read, rather than left to stop the rig.
        findings.append(f"rvfi.packet_view has no branch for the {exc} record, which "
                        f"{DOC} declares")
    else:
        dropped = declared - {record[0] for record in view}
        findings += [f"rvfi.packet_view drops the `{kind}` record and {DOC}'s elision "
                     "table does not carry it" for kind in sorted(dropped - elides)]
        findings += [f"{DOC}'s elision table carries `{kind}` and rvfi.packet_view "
                     "keeps it" for kind in sorted(elides - dropped)]

    ctx.shared["record kinds the commit-trace schema declares"] = len(declared)
    rep.report("K-85", "commit-trace record kind(s) the document and the projection "
               "disagree on:", findings,
               f"all {len(declared)} record kinds {DOC}'s schema table declares are met "
               f"or elided exactly once, and that split is the {len(meets)} kinds "
               f"rvfi.py's projection emits against the {len(elides)} its packet view "
               "drops")


def _linked_sources(doc: str) -> set[str]:
    prefix = f"({CORPUS_LINK}/"
    found = set()
    at = doc.find(prefix)
    while at != -1:
        end = doc.find(")", at)
        if end != -1:
            found.add(doc[at + len(prefix):end])
        at = doc.find(prefix, at + 1)
    return {name for name in found if name.endswith(".s")}
