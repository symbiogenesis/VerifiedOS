# SPDX-License-Identifier: Apache-2.0
"""pins: every upstream pin this repository states, against the artifact that owns it.

An upstream arrives here as a gitlink: the index carries a path and a commit id and
none of the code, and [THIRD-PARTY.md](../../../THIRD-PARTY.md) carries the licence
record over those pins, one row per submodule, each stating the short id its terms
were read at. The row is hand-copied from the gitlink and the copy had no owner.

**That copy is the one derived fact in this repository whose defect cannot be
repaired downstream.** [CLAUDE.md](../../../CLAUDE.md) and [the plan's
§12](../../../docs/implementation-checklist.md#12-build-order-milestones-and-execution-state)
both say it: a licence is a property of the *arrival*, read at the milestone that
would incorporate the upstream, and work built on terms that forbid the composition
is not re-licensed by finding out later. A gitlink advanced without its row moving
leaves the page asserting that somebody read an edition nobody has opened, and every
other rule here stays green over it, because the row is prose that resolves, cites
nothing, and counts nothing.

**Three artifacts state a pin and they are not three opinions.** The index owns it;
the record copies it and is where the terms were read; and the rest of the
repository, the plan's completion notes, the RTL delta's provenance table, the ported
model headers and the tools' own oracle-tree name, restates what the record says. So
the rule is two hops rather than one comparison, and each hop has its own owner.

**Hop one: the record against the index, in both directions, and never repaired.**
A gitlink with no row is an upstream whose terms are not on the page at all; a row
naming no gitlink is a pin for something this repository does not carry; and a row
whose id is not the gitlink's is the defect above. None of the three is rewritten
under `--fix`, and that is the strongest ground in this rule rather than a
convenience. The Pin cell is where the licence was read, and the row's own Licence
cell, its Standing, and the page's reading paragraphs are that reading; advancing the
cell from the index would record a reading nobody took, under a flag run to repair
checklist arithmetic. [marks.py](marks.py) already refuses this repair one artifact
over, on the same ground: what `--fix` rewrites is recomputed from something the
repository already determined, and a provenance claim is not that. The finding *is*
the instruction: somebody moved a gitlink and owes a licence read.

**Hop two: every other site against the record.** What those sites restate is the
record's account, so the record is the artifact that owns the id for them, exactly as
an entry owns a figure the documents restate under K-69. A site is found by the shape
a restatement takes rather than by a list of places to look: an abbreviated object id
on a line that has already named the upstream it belongs to.

**A pin whose row is itself a finding has its sites left alone**, reported by
neither hop. One gitlink advancing moves every site at once, so holding the sites
against a record that is already red would price one act as a dozen findings and
point every one of them at a repair that belongs at the record. One act, one
finding, at the one place a person has to act.

**Nothing here is repaired, and the ground is the same one the whole rule stands
on.** The obvious reading is that a short id in a normalized document is a pure token
substitution and so belongs to `--fix`, and it is wrong about every site this
repository actually has. Each of them states the id *beside what was done at it*:
the record's own row beside the terms read there, the RTL delta's provenance table
beside the date its tree was read on, the plan's completion notes beside a licence
reading taken at a milestone, a ported header beside the file it was transplanted
from, and `vos/env.py`'s `ORACLE_TREE` beside a build tree that stands on disk.
Rewriting the id alone leaves every one of those sentences describing work done at a
commit it no longer names, which is the half-a-sentence hazard that keeps K-70
report-only and, here, is worse than that: it would record a licence reading nobody
took, under a flag run to repair checklist arithmetic. Two further grounds fall in
the same direction and would each be enough on their own, the ported headers being
under [model/](../../../model/)'s `-text` tree where a rewrite risks the line-ending
sweep K-57 names, and `vos/env.py`'s id being a directory's name rather than a
sentence's figure. A pin is never arithmetic to recompute; it is always the record of
something somebody did at a commit, which is the shape K-76 declines to repair one
artifact over.

**Fail-closed at every reading.** An absent record, a pin table this parse cannot
locate by its own heading and column names, a table with no rows, an index carrying
no gitlink at all, and a model window the counts group has not read are each one
finding that stops or narrows the comparison, because each of them would otherwise
leave this rule reporting that every pin of none agrees. The gitlink's id lives in
the index whether or not the submodule is checked out, which is why the index is the
instrument: most checkouts here have `upstream/` unpopulated, and this rule decides
exactly the same thing on one of those.

**The residues are declared and are held in both directions.** A commit id written
beside an upstream's name that is *not* that upstream's pin is exactly what a reader
would misread, so it is named here with what it actually is. The table asks for a
decision the way [marks.py](marks.py)'s kinds do, and an entry that suppresses
nothing goes the way a ruling nothing exercises does. It is keyed by the id and not
by the pin beside it, because what a residue declares is what that commit *is*, which
does not change with whichever name a sentence happens to put in front of it. The
alternative to declaring them is narrowing the shape until they fall out of it, and
that trade runs the wrong way: a token of seven or more hexadecimal digits is what an
abbreviated commit looks like, so any narrowing tight enough to exclude a decimal
figure would one day stop reading a pin whose own id took that shape, silently, where
a residue is loud and asks for a decision.

**What this rule cannot attribute it does not decide.** An id is paired with the last
upstream *named on its own line*, so an id standing on a line that names none is read
by nothing here: the RTL delta's `Read at ...` sentence and its second table's
display-name cell are both such sites today. Attribution by nearness across lines is
the obvious alternative and is worse, that same table putting one upstream's row four
lines above another upstream's cell, so it would pair ids with the wrong pins rather
than leave them unpaired. Membership against the whole pin set was the other
candidate and is worse again: this repository writes many commits of other trees
beside its own, a branch head, an embedded revision, an emulator's own revision, and
holding every id-shaped token against the pins would demand a declaration for each of
them and grow one per completion note. So the residue is stated rather than closed.

**What this cannot decide is whether the terms at the pin were read correctly**, or
read at all. That is the same residue every group here declares: the id is checked
for agreement, and what somebody found when they opened the licence file at it is a
person's to know.

K-97 is this group's other kind of pin, and it is here rather than beside K-81 for one
reason and separated from it for another. **An upstream pins by version as well as by
commit**, and the licence record carries both kinds in one page: a submodule's terms are
read at an object id, and a development tool arrives from a distribution at a version
number, which is the edition its own row's terms were read at exactly as a commit is.
**What owns the two is not the same artifact.** A commit pin is owned by the git index,
which is a fact about the checkout; a version pin is owned by the constant the lane
actually enforces it at, `VERILATOR_PIN` in [vos/cli/rtl.py](../cli/rtl.py), which every
`rtl` loop compares an installed elaborator against and refuses on. So the record is a
restatement here where it is the owner there, and the direction of the reading flips
with it.

**Nothing held that constant's restatements**, and the two neighbouring rules each miss
it by their own subject: K-81 reads abbreviated object ids and a dotted version is not
one, and K-67 reads the two checkers `run.py typecheck` installs and no third pin. What
was left is a figure restated in the record's development-tools row, in the record's own
Verilator paragraph, and in the plan's RTL-track cell, with the constant that enforces it
free to move under all three. A pin stale in the record is the same defect K-81 exists
for one column over: the row's terms were read at an edition, and a reader installing
what the row states runs a lane the tools refuse.

**The sites are enumerated in code and read fail-closed**, on K-67's and K-75's ground,
which is why this rule owes the floors group no member: a site whose pattern no longer
matches is a finding here, on the day it stops matching, rather than a set that has
quietly gone to zero one group later. The window is the enumeration and not a scan, and
what that leaves out is declared rather than discovered. The plan's own completion notes
state the elaborator's version beside an elaboration run at it, which is a measurement
recorded at a gate and not a restatement of the pin, exactly as K-81 leaves a commit
written beside what was done at it to the sentence that did it; the provisioner and its
test compose the figure from the constant rather than restating it, so neither is a site;
and the *upstream's own* version of the same tool, the one the imported core's own flow
pins through nix, is a fact about that upstream rather than a pin taken here, so no rule
holds it and this one says so rather than reaching for it.

**Reported and never repaired**, on this group's own ground. The record's row states the
version beside the terms read at it and the plan's cell states it beside a lane, so a
token substitution would leave both sentences describing work done at a version they no
longer name.
"""

import re
from typing import TYPE_CHECKING, cast

from vos import corpus as corpus_mod
from vos import figures
from vos import pins as pins_mod
from vos.checks import generated

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== pins: every upstream pin against the artifact that owns it ==="

# The version pin K-97 holds, and the three sites that restate it. The constant is read
# out of the source as text rather than imported, for the reason K-67 reads typecheck.py
# the same way: the rule is about what the file *states*, and a value taken by import
# would be the checker's own module rather than the one under the root it was pointed at.
VERILATOR_SRC = "tools/vos/cli/rtl.py"
_VERILATOR_SRC_RE = re.compile(r'(?m)^VERILATOR_PIN = "([^"\r\n]*)"')

PLAN = "docs/implementation-checklist.md"

# Each row is a site, the file carrying it, and the pattern that reads the figure out of
# it. Every pattern is anchored on the sentence's own words rather than on the number, so
# a reworded site is a finding and never a site that quietly stopped being read.
_VERILATOR_SITES: list[tuple[str, str, re.Pattern[str]]] = [
    ("development-tools row", pins_mod.RECORD,
     re.compile(r"(?m)^\| Verilator \|[^|]*\|[^|]*pinned at \*\*([^*]+)\*\*")),
    ("pin paragraph", pins_mod.RECORD,
     re.compile(r"\*\*Verilator is pinned[^*]*\*\* The pin is \*\*([^*]+)\*\*")),
    ("RTL-track cell", PLAN,
     re.compile(r"Verilator is pinned at (\S+) with its own")),
]

# Every id this repository writes beside an upstream's name that is not that
# upstream's pin, with what it actually is. Each one is a reading trap on its face:
# a reader meeting it next to the project's name has every reason to take it for the
# pin, which is why it is named here rather than excluded by a shape.
#
# The first is the deliberate residue this rule declines to own. THIRD-PARTY.md's
# vendored table states the commit `model/` was taken from, and no gitlink owns it,
# because a vendored tree has none: the tree is tracked here whole and its baseline
# is a fact about how it was made rather than a pointer git resolves. That is the
# shape K-71 already declines to hold for the corpus manifest's edition, and the
# precedent is followed rather than a second owner invented for it. What the pin
# table records for `upstream/sail-riscv` is a different figure with a different
# meaning, the edition the curation is reconciled *against*, and that one is held.
RESIDUE: dict[str, str] = {
    "8f91355e": "the commit the curated model was vendored from, which no gitlink "
                "owns because a vendored tree has none",
    "b748a82": "the older `sail-riscv` the CHERI oracle's own tree embeds, a fact "
               "about that upstream rather than a pin taken here",
    "435618bf": "the tag object `v0.1.1` names, recorded beside the commit it points "
                "at because transcribing the tag is the trap that row warns of",
    "11007678": "the numeral of SECOMP's Zenodo DOI, which is not an object id",
}


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)
    _pins(ctx)
    _version_pin(ctx)
    rep.line()


def _version_pin(ctx: Context) -> None:
    """K-97: every site stating the elaborator's version states the one rtl.py fixes.

    Fail-closed at every reading, on K-67's and K-75's ground. The constant either
    parses in the form it is written in today or there is no owner to hold anything
    against; a document the corpus does not carry is a finding rather than a site
    silently dropped; and a site whose pattern no longer matches, or has come to match
    a sentence that no longer states the pin, is a finding rather than a pass over
    nothing. That is what makes this rule owe the floors group no member of its own.
    """
    rep = ctx.rep
    findings: list[str] = []

    try:
        source = (ctx.root / VERILATOR_SRC).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        source = ""
    stated = _VERILATOR_SRC_RE.search(source)
    if stated is None:
        findings.append(f"{VERILATOR_SRC} no longer states VERILATOR_PIN in a form this "
                        "rule reads, so there is no owner to hold the sites against")

    pin = stated.group(1) if stated else ""
    if stated is not None:
        for label, file, pattern in _VERILATOR_SITES:
            text = ctx.text(file)
            if not text:
                findings.append(f"{file} is not in the repository, so its {label} cannot "
                                "be read")
                continue
            hit = pattern.search(text)
            if hit is None:
                findings.append(f"{file} no longer states the elaborator's pin in its "
                                f"{label}, in a form this rule reads")
            elif hit.group(1) != pin:
                findings.append(
                    f"{file}'s {label} states {hit.group(1)}, {VERILATOR_SRC} pins "
                    f"{pin}; that row's terms were read at the version it states and "
                    "the lane refuses any other, so the edit is a person's")

    rep.report("K-97", "site(s) restating a version pin the lane's own constant does "
               "not fix:", findings,
               f"the {figures.words(len(_VERILATOR_SITES))} sites restating the "
               f"elaborator's version state {pin or 'no version'}, which "
               f"{VERILATOR_SRC} fixes and every rtl loop refuses another of")


def _sources(ctx: Context) -> list[tuple[str, list[str], list[bool]]]:
    """Every file this rule reads, as its lines and which of them a fence displays.

    **The window is the git index**, because a pin is restated wherever somebody
    argues from one and a list of places to look would be a membership nobody
    maintains: the plan's completion notes, the RTL delta's provenance table, a Sail
    header, a build tree's name in `vos/env.py`. So the tool walks what git tracks
    rather than a set some sentence points it at, and the only way for a site to
    escape is for it to leave the repository.

    The tracked files arrive by three routes, and the routes are about *reading* them
    once rather than about which are in scope. A **document** comes from the corpus,
    which already holds its lines and the fence mask over them, so the mask is used
    rather than recomputed here. **`model/`** comes through the citation window the
    counts group already read, handed on rather than opened a second time, which is
    the duplication [vos/](..) exists to refuse. Everything else is read here, and
    carries no mask, a fence being a thing Markdown does and these files are not.

    That leaves two parts of the index unread and both are worth stating. `model/`
    *outside* the citation window is vendored upstream at its own revisions,
    `dependencies/` most of all, and a commit recorded there is somebody else's
    provenance rather than a pin taken here. Holding an upstream's own recorded commits
    against this repository's licence record is not a claim anyone should make, which is
    the ground `corpus.is_model_citation_path` already gives for the same boundary.

    The second is **the generated artifacts**, and the ground is this rule's own subject
    rather than a cost. What it holds is a *restatement*: a person naming an upstream and
    writing a commit beside it, which drifts because a person wrote it. A generated
    artifact restates nothing, its content being a function of its owners and held
    byte-for-byte by K-88, so an object-id-shaped token inside one is not a
    transcription and there is no edit for a finding to ask for. The bundle makes that
    concrete: it is one line of four megabytes carrying every Sail bit literal in the
    model, so `0b00000` reads as seven hex digits on a line that also names an upstream,
    and the rule reported thousands of restatements nobody wrote.

    A file that will not read as text is skipped rather than reported: what every
    tracked file is made of is the glyphs group's question, and pricing one
    unreadable file under both would report one defect twice.
    """
    window: list[tuple[str, list[str], list[bool]]] = [
        (doc.name, doc.lines, doc.fenced) for doc in ctx.corpus.docs]
    machine = generated.paths()

    # Narrowed here rather than trusted, which is what `Context.shared` being `Any`
    # asks of each reader: the counts group puts `(rel, text)` pairs there and this
    # is the sentence saying so.
    ported = cast("list[tuple[str, str]]", ctx.shared.get("citation_window", []))
    window += [(rel, text.split("\n"), []) for rel, text in ported]

    for rel in ctx.corpus.tracked:
        if rel in ctx.corpus or rel.startswith(corpus_mod.UNREAD_PREFIX):
            continue
        if rel in machine:
            continue
        try:
            text = (ctx.root / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        window.append((rel, text.split("\n"), []))
    return window


def _pins(ctx: Context) -> None:
    """K-81: the record's pin table against the index, and every restatement against it."""
    rep, sh = ctx.rep, ctx.shared
    label = "upstream pin(s) that disagree with the gitlink that owns them:"
    record = pins_mod.RECORD

    # Every gitlink and not only the ones under `upstream/`. The record's own section
    # says *these are gitlink entries*, so the set it accounts for is the index's and
    # not a subtree of it, and a submodule added anywhere else would otherwise be an
    # upstream with no terms on the page and nothing to say so.
    gitlinks = ctx.corpus.gitlinks
    read = pins_mod.read_record(ctx.text(record))

    if read.fault is not None or not gitlinks:
        sh["record_pins"] = 0
        sh["pin_restatements"] = 0
        rep.report("K-81", label, [
            read.fault,
            f"the git index carries no gitlink at all, so {record}'s pin table would "
            "be held against nothing" if not gitlinks else None,
        ])
        return

    findings: list[str] = []
    settled: dict[str, tuple[pins_mod.Pin, str]] = {}
    seen: set[str] = set()
    if "citation_window" not in sh:
        findings.append("the counts group has not read the model window, so the "
                        "commits the ported headers state are unread here")
    for pin in read.rows:
        where = f"{record}:{pin.line}"
        if pin.path and pin.path in seen:
            findings.append(f"{where} is a second row for {pin.path}, and a pin stated "
                            "twice is a pin the page can disagree with itself about")
            continue
        seen.add(pin.path)
        if not pin.path:
            findings.append(f"{where} names no submodule in a form this rule reads, "
                            "so the row pins nothing")
        elif pin.path not in gitlinks:
            findings.append(f"{where} pins {pin.path}, which the index carries no "
                            "gitlink for")
        elif not pin.short:
            findings.append(f"{where} pins {pin.path} and states no commit id, so the "
                            "edition its terms were read at is not recorded")
        elif not gitlinks[pin.path].startswith(pin.short):
            findings.append(
                f"{where} pins {pin.path} at {pin.short} and the index carries it at "
                f"{gitlinks[pin.path][:12]}; the terms on that row were read at the "
                "commit the row states, so the repair is a licence read and not a "
                "transcription")
        else:
            settled[pin.path] = (pin, gitlinks[pin.path])

    findings += [f"the index carries a gitlink at {path} and {record}'s pin table has "
                 "no row for it, so an upstream this repository pins has no terms on "
                 "the page" for path in sorted(set(gitlinks) - {p.path for p in read.rows})]

    held, used = _restatements(ctx, read.rows, settled, findings)

    findings += [f"{ident} is declared here as {why}, and no site states it any more; "
                 "a residue that suppresses nothing is a carve-out nobody audits"
                 for ident, why in RESIDUE.items() if ident not in used]

    sh["record_pins"] = len(read.rows)
    sh["pin_restatements"] = held
    rep.report("K-81", label, findings,
               f"the {len(read.rows)} upstream pins {record} records are the commits "
               f"the index carries, and the {held} sites restating one state the same "
               "id")


def _restatements(ctx: Context, rows: list[pins_mod.Pin],
                  settled: dict[str, tuple[pins_mod.Pin, str]],
                  findings: list[str]) -> tuple[int, set[str]]:
    """Every site that restates a pin, held against the record's row.

    The record's own table rows are skipped, because holding them here would price
    one drifted row as two findings: they are the first hop's subject and this is the
    second's. A row's other statements of its pin in the page's prose are not
    skipped, being restatements like any other.

    A site is held against the whole object id and reported against the record's own
    eight digits, and those are two different lengths on purpose. A site may
    abbreviate the same commit shorter or longer than the record does and be right
    either way, which only the full id can decide; what the finding quotes back is
    the spelling the record uses, because the record is what these sites restate.

    A fenced line is skipped where the file has a fence to speak of, which is the
    corpus's own rule and the corpus's own mask: an id inside one is displayed as
    text and names nothing.
    """
    named = pins_mod.spellings(rows)
    table = {(pins_mod.RECORD, pin.line) for pin in rows}
    used: set[str] = set()
    held = 0

    for file, lines, fenced in _sources(ctx):
        for site in pins_mod.scan(file, lines, named):
            if fenced and fenced[site.index]:
                continue
            if site.ident in RESIDUE:
                used.add(site.ident)
                continue
            if (file, site.line) in table or site.pin.path not in settled:
                continue
            held += 1
            pin, oid = settled[site.pin.path]
            if oid.startswith(site.ident):
                continue
            findings.append(
                f"{site.where()} states the {site.pin.path} pin as {site.ident}, "
                f"{pins_mod.RECORD} records {pin.short}; the sentence around it says "
                "what was done at that commit, so the edit is a person's")
    return held, used
