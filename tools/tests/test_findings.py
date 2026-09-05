# SPDX-License-Identifier: Apache-2.0
"""The findings register's parse, the notes' own findings blocks, and the relation.

`findings.parse` and `findings.plan` are exercised against the live tree on every
`check.py` run, which decides that today's three documents agree and nothing about the
readings themselves: a block whose bullets a rewritten note indents differently, a
count word that stops being a count, an entry whose disposition is misspelled, a log
entry whose heading no landed item answers to. Those are what this module fixes, on
fixtures small enough to read.

The fixtures are written in the live documents' own shapes rather than in a
simplified one, indentation included, because indentation is what `_block_size`
decides on and a fixture that flattened it would hold nothing.
"""

from typing import Final

from tests.harness import Case, ensure
from vos import findings

# The register side: a fenced template above two entries, one counted and one in
# prose, the second restating the first. Every property line the parse reads is
# present and in the order the live document writes them.
_REGISTER: Final[str] = """\
# Findings Register

```
**F-nnn** <type>: what was found
· Raised: the checklist item whose note records it
· Disposition: open, closed, or standing
```

**F-001** measurement: the first thing found
· Raised: M0.16
· Disposition: standing, nothing being owed

**F-002** owed-act: the same thing, met again
· Raised: M3.1, in prose
· Disposition: open, an act being owed
· Restates: F-001
"""

# The plan side: an unchecked item carrying its own note, a checked one, a struck one
# and an item whose label has no middot at all, the three landed ones each carrying
# the one line and the link the plan keeps for a landed item.
_PLAN: Final[str] = """\
* [ ] **S1 · Discharge the owed register acts** · 12 h, range 8–16 · 1.1% · I
  * Fourteen acts the tree already reports and nothing prices.
* [x] **M0.16 · Refresh and discharge sequencer** · 5.5 h actual · 0.5%
  * The sequencer lands. ([note](completion-log.md#m016-refresh-and-discharge-sequencer))
* ~~**M2.1 · Fork CHERI-QEMU and narrow compressed capabilities**~~ · struck
  * Struck. ([note](completion-log.md#m21-fork-cheri-qemu-and-narrow-compressed-capabilities))
* [x] **Initial check/emit/FAST tooling** · 0.9 h actual · 0.1%
  * The first tooling. ([note](completion-log.md#initial-checkemitfast-tooling))
"""

# The log side: one entry per landed item under a heading spelling its label, a
# counted block whose bullets run to a sibling at the header's own depth, the singleton
# form, and a paragraph whose leading word is not a count.
_LOG: Final[str] = """\
# Completion Log

## S · Serial-path decisions and program instruments

### M0.16 · Refresh and discharge sequencer

  * Two findings.
    * **The first.** A sentence that runs on
      and continues on a second line.
    * **The second.**
  * Something else this note says.

### M2.1 · Fork CHERI-QEMU and narrow compressed capabilities

  * Finding, about the algebra: something the fork measured.

### Initial check/emit/FAST tooling

  * Environment findings, booked for later lanes. Three of them, in prose.
"""


def _parse_entries() -> None:
    index = findings.parse(_REGISTER)
    ensure(index.present, "a register with text present must read as present")
    ensure(not index.malformed, f"the fixture is well formed: {index.malformed}")
    ensure([e.ident for e in index.entries] == ["F-001", "F-002"],
           f"both entries must be read, got {[e.ident for e in index.entries]}")
    first, second = index.entries
    ensure(first.kind == "measurement" and first.raised == "M0.16"
           and not first.in_prose and first.disposition == "standing"
           and not first.restates,
           f"the counted entry read wrongly: {first}")
    ensure(second.kind == "owed-act" and second.raised == "M3.1"
           and second.in_prose and second.disposition == "open"
           and second.restates == "F-001",
           f"the prose entry read wrongly: {second}")
    ensure(first.line == 9 and second.line == 13,
           f"an entry must know its own line, got {first.line} and {second.line}")


def _fenced_template_is_not_an_entry() -> None:
    # Two guards stand between the template and the comparison, and this pins both:
    # the fence blanks the span, and the id shape refuses `F-nnn` even unfenced.
    ensure(len(findings.parse(_REGISTER).entries) == 2,
           "the fenced template must not read as a third entry")
    unfenced = _REGISTER.replace("```\n", "")
    ensure(len(findings.parse(unfenced).entries) == 2,
           "`F-nnn` is not an id, fence or no fence")


def _absent_register() -> None:
    index = findings.parse("")
    ensure(not index.present and not index.entries and not index.malformed,
           f"an empty register must be absent and carry nothing, got {index}")


def _malformed_entries() -> None:
    def one(text: str) -> list[str]:
        return findings.parse(text).malformed

    good = "**F-001** method: a thing\n· Raised: M0.16\n· Disposition: closed, by it\n"
    ensure(not one(good), f"the control must be clean, got {one(good)}")
    ensure(len(one(good.replace("method", "guesswork"))) == 1,
           "a type outside the four must be one finding")
    ensure(len(one(good.replace("closed", "pending"))) == 1,
           "a disposition outside the three must be one finding")
    ensure(len(one(good.replace("· Raised: M0.16\n", ""))) == 1,
           "an entry with no Raised line must be one finding")
    ensure(len(one(good + good)) == 1,
           "an id carried twice must be one finding, ids being permanent")
    dangling = good.rstrip("\n") + "\n· Restates: F-404\n"
    ensure(len(one(dangling)) == 1,
           "a Restates line naming an entry the register lacks must be one finding")
    # The malformed entry is dropped from the comparison rather than half-read, which
    # is what keeps a mistyped entry from also reading as a missing one somewhere else.
    ensure(not findings.parse(good.replace("method", "guesswork")).entries,
           "an entry this parse cannot place must not reach the entry list")


def _plan_items() -> None:
    read = findings.plan(_PLAN, _LOG)
    ensure(read.present and read.log_present,
           "a plan and a log with text present must both read as present")
    ensure(read.items == {"S1", "M0.16", "M2.1", "Initial check/emit/FAST tooling"},
           f"unchecked, checked, struck and middot-free labels must all land: "
           f"{sorted(read.items)}")
    ensure(read.done == {"M0.16", "M2.1", "Initial check/emit/FAST tooling"},
           f"the checked and struck items are the landed ones: {sorted(read.done)}")
    ensure(read.log_items == read.done,
           f"the log's headings are the landed items' labels: {sorted(read.log_items)}")


def _plan_blocks() -> None:
    read = findings.plan(_PLAN, _LOG)
    ensure([(b.doc, b.item, b.declared, b.size) for b in read.blocks]
           == [(findings.LOG, "M0.16", 2, 2), (findings.LOG, "M2.1", 0, 1)],
           f"one counted block and one singleton, both in the log: "
           f"{[(b.doc, b.item, b.declared, b.size) for b in read.blocks]}")
    ensure(findings.counted(read) == {"M0.16": 2, "M2.1": 1},
           f"the per-item count must be the sum of block sizes, "
           f"got {findings.counted(read)}")


def _a_block_in_the_plan_is_read_too() -> None:
    # An open item's note stays in the plan, and a finding it records is attributed to
    # it exactly as one in the log is attributed to its heading.
    text = _PLAN.replace("  * Fourteen acts the tree already reports and nothing prices.",
                         "  * Finding: the first thing S1 found.")
    read = findings.plan(text, _LOG)
    first = next((b.doc, b.item) for b in read.blocks)
    ensure(first == (findings.PLAN, "S1"),
           f"a block under an open item is the plan's and that item's: {read.blocks}")


def _a_leading_word_that_is_not_a_count() -> None:
    # The paragraph the live log opens `Environment findings` is prose the register
    # indexes by hand, so it must not read as a block this parse could not count.
    read = findings.plan(_PLAN, _LOG)
    ensure(all(b.item != "Initial check/emit/FAST tooling" for b in read.blocks),
           "a findings bullet whose leading word is not a count is not a block")
    # And a count word that stops being one takes its whole block out of the notes'
    # side rather than reading as a block of zero, which is what makes the comparison
    # itself the fail-closed reading.
    moved = _LOG.replace("  * Two findings.", "  * Twwo findings.")
    ensure(not any(b.item == "M0.16" for b in findings.plan(_PLAN, moved).blocks),
           "a misspelled count word must remove its block, not empty it")


def _block_size_boundaries() -> None:
    def size(body: str) -> int:
        text = ("* [x] **X · An item** · 1 h actual · 0.1%\n"
                "  * Three findings.\n" + body)
        blocks = findings.plan(text).blocks
        return blocks[0].size if blocks else -1

    ensure(size("    * one\n    * two\n    * three\n") == 3, "three siblings are three")
    ensure(size("    * one\n\n    * two\n") == 2, "a blank line does not end a block")
    ensure(size("    * one\n      continued here\n    * two\n") == 2,
           "a member's own continuation line is not a member")
    ensure(size("    * one\n      * deeper\n    * two\n") == 2,
           "a bullet deeper than the first member is not a member")
    ensure(size("    * one\n  * a sibling of the header\n    * two\n") == 1,
           "a bullet at the header's own depth ends the block")
    ensure(size("    * one\n#### A heading\n    * two\n") == 1,
           "content at or above the header's depth ends the block")
    ensure(size("") == 0, "a header with nothing under it is a block of zero")


def _log_headings() -> None:
    # A section heading is two hashes and names no item; an entry is three or four,
    # the fourth level being a child item of a split milestone.
    log = _LOG.replace("### M2.1 ·", "#### M2.1 ·")
    read = findings.plan(_PLAN, log)
    ensure(read.log_items == {"M0.16", "M2.1", "Initial check/emit/FAST tooling"},
           f"a fourth-level heading is an entry: {sorted(read.log_items)}")
    ensure("S" not in read.log_items,
           "the section heading must not read as an entry")


def _disagreements() -> None:
    index, read = findings.parse(_REGISTER), findings.plan(_PLAN, _LOG)
    found = findings.disagreements(index, read)
    # M0.16 counts two and the register indexes one; M2.1 counts one and the register
    # indexes none; M3.1 is not an item this plan carries and its entry is in prose,
    # so it is named once for the item and never for a count. The log agrees with the
    # landed items in both directions, so nothing is named for it.
    ensure(len(found) == 3, f"the fixture pair disagrees three ways: {found}")
    ensure(sum(1 for f in found if "M3.1" in f) == 1,
           f"the prose entry's absent item is named once, not once per reading: {found}")
    ensure(sum(1 for f in found if f.startswith("M0.16")) == 1
           and sum(1 for f in found if f.startswith("M2.1")) == 1,
           f"each item's count disagreement is named once: {found}")
    ensure(any(f.startswith((f"{findings.LOG}:", "M0.16")) for f in found),
           f"a block's disagreement names the document it sits in: {found}")

    ensure(findings.disagreements(findings.parse(""), read)
           == [f"{findings.REGISTER} is not in the checker's corpus, so no finding "
               "the plan records is indexed by anything"],
           "an absent register is one finding and not one per item")
    ensure(len(findings.disagreements(index, findings.plan("", _LOG))) == 1,
           "an absent plan is one finding too")


def _log_totality() -> None:
    index = findings.parse(_REGISTER)
    baseline = findings.disagreements(index, findings.plan(_PLAN, _LOG))

    # a landed item whose entry is gone is named, once, by its label
    missing = _LOG.replace("### Initial check/emit/FAST tooling\n", "")
    found = findings.disagreements(index, findings.plan(_PLAN, missing))
    ensure(len(found) == len(baseline) + 1
           and any(f.startswith("Initial check/emit/FAST tooling is a landed item")
                   for f in found),
           f"a landed item with no log entry is one finding naming it: {found}")

    # an entry naming no landed item is named, once, by its label, and an open item's
    # label does not answer for it
    extra = _LOG + "\n### S1 · Discharge the owed register acts\n\n  * A note.\n"
    found = findings.disagreements(index, findings.plan(_PLAN, extra))
    ensure(len(found) == len(baseline) + 1
           and any("carries an entry for S1, which is not a landed item" in f
                   for f in found),
           f"an entry for an item that has not landed is one finding: {found}")

    # a renamed heading fires both directions at once
    renamed = _LOG.replace("### M2.1 ·", "### M2.9 ·")
    found = findings.disagreements(index, findings.plan(_PLAN, renamed))
    ensure(any("M2.1 is a landed item" in f for f in found)
           and any("entry for M2.9" in f for f in found),
           f"a renamed heading is an item without an entry and an entry without an item: "
           f"{found}")

    # an absent log is one finding rather than one per landed item
    found = findings.disagreements(index, findings.plan(_PLAN, ""))
    ensure(sum(1 for f in found if f.startswith(f"{findings.LOG} is not")) == 1
           and not any("is a landed item" in f for f in found),
           f"an absent log is named once and no item is named for it: {found}")


def _in_prose_is_not_counted() -> None:
    # The half the rule does not hold: an entry marked `in prose` is outside the
    # per-item count entirely, so adding one to an item that already agrees must not
    # make it disagree.
    text = _PLAN.replace("* ~~**M2.1", "* ~~**M9.9")
    log = _LOG.replace("### M2.1 ·", "### M9.9 ·")
    plan_only_m016 = findings.plan(text, log)
    reg = ("**F-001** method: a\n· Raised: M0.16\n· Disposition: closed, x\n\n"
           "**F-002** method: b\n· Raised: M0.16\n· Disposition: closed, x\n\n"
           "**F-003** method: c\n· Raised: M0.16, in prose\n· Disposition: open, y\n")
    index = findings.parse(reg)
    ensure(findings.indexed(index) == {"M0.16": 2},
           f"a prose entry is outside the count, got {findings.indexed(index)}")
    ensure(all("M0.16" not in f
               for f in findings.disagreements(index, plan_only_m016)),
           "two counted entries and one prose entry must agree with a block of two")


def cases() -> list[Case]:
    return [
        Case("parse-entries", _parse_entries),
        Case("fenced-template-is-not-an-entry", _fenced_template_is_not_an_entry),
        Case("absent-register", _absent_register),
        Case("malformed-entries", _malformed_entries),
        Case("plan-items", _plan_items),
        Case("plan-blocks", _plan_blocks),
        Case("a-block-in-the-plan-is-read-too", _a_block_in_the_plan_is_read_too),
        Case("a-leading-word-that-is-not-a-count", _a_leading_word_that_is_not_a_count),
        Case("block-size-boundaries", _block_size_boundaries),
        Case("log-headings", _log_headings),
        Case("disagreements", _disagreements),
        Case("log-totality", _log_totality),
        Case("in-prose-is-not-counted", _in_prose_is_not_counted),
    ]
