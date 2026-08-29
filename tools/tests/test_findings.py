# SPDX-License-Identifier: Apache-2.0
"""The findings register's parse, the plan's own findings blocks, and the relation.

`findings.parse` and `findings.plan` are exercised against the live tree on every
`check.py` run, which decides that today's two documents agree and nothing about the
readings themselves: a block whose bullets a rewritten note indents differently, a
count word that stops being a count, an entry whose disposition is misspelled. Those
are what this module fixes, on fixtures small enough to read.

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

# The plan side: an unchecked item, a checked one carrying a counted block whose
# bullets run to a sibling at the header's own depth, a struck one carrying the
# singleton form, and an item whose label has no middot at all.
_PLAN: Final[str] = """\
* [ ] **S1 · Discharge the owed register acts** · 12 h, range 8–16 · 1.1% · I
  * Fourteen acts the tree already reports and nothing prices.
* [x] **M0.16 · Refresh and discharge sequencer** · 5.5 h actual · 0.5%
  * Two findings.
    * **The first.** A sentence that runs on
      and continues on a second line.
    * **The second.**
  * Something else this note says.
* ~~**M2.1 · Fork CHERI-QEMU and narrow compressed capabilities**~~ · struck
  * Finding, about the algebra: something the fork measured.
* [x] **Initial check/emit/FAST tooling** · 0.9 h actual · 0.1%
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
    read = findings.plan(_PLAN)
    ensure(read.present, "a plan with text present must read as present")
    ensure(read.items == {"S1", "M0.16", "M2.1", "Initial check/emit/FAST tooling"},
           f"unchecked, checked, struck and middot-free labels must all land: "
           f"{sorted(read.items)}")


def _plan_blocks() -> None:
    read = findings.plan(_PLAN)
    ensure([(b.item, b.declared, b.size) for b in read.blocks]
           == [("M0.16", 2, 2), ("M2.1", 0, 1)],
           f"one counted block and one singleton: "
           f"{[(b.item, b.declared, b.size) for b in read.blocks]}")
    ensure(findings.counted(read) == {"M0.16": 2, "M2.1": 1},
           f"the per-item count must be the sum of block sizes, "
           f"got {findings.counted(read)}")


def _a_leading_word_that_is_not_a_count() -> None:
    # The paragraph the live plan opens `Environment findings` is prose the register
    # indexes by hand, so it must not read as a block this parse could not count.
    read = findings.plan(_PLAN)
    ensure(all(b.item != "Initial check/emit/FAST tooling" for b in read.blocks),
           "a findings bullet whose leading word is not a count is not a block")
    # And a count word that stops being one takes its whole block out of the plan's
    # side rather than reading as a block of zero, which is what makes the comparison
    # itself the fail-closed reading.
    moved = _PLAN.replace("  * Two findings.", "  * Twwo findings.")
    ensure(not any(b.item == "M0.16" for b in findings.plan(moved).blocks),
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


def _disagreements() -> None:
    index, read = findings.parse(_REGISTER), findings.plan(_PLAN)
    found = findings.disagreements(index, read)
    # M0.16 counts two and the register indexes one; M2.1 counts one and the register
    # indexes none; M3.1 is not an item this plan carries and its entry is in prose,
    # so it is named once for the item and never for a count.
    ensure(len(found) == 3, f"the fixture pair disagrees three ways: {found}")
    ensure(sum(1 for f in found if "M3.1" in f) == 1,
           f"the prose entry's absent item is named once, not once per reading: {found}")
    ensure(sum(1 for f in found if f.startswith("M0.16")) == 1
           and sum(1 for f in found if f.startswith("M2.1")) == 1,
           f"each item's count disagreement is named once: {found}")

    ensure(findings.disagreements(findings.parse(""), read)
           == [f"{findings.REGISTER} is not in the checker's corpus, so no finding "
               "the plan records is indexed by anything"],
           "an absent register is one finding and not one per item")
    ensure(len(findings.disagreements(index, findings.plan(""))) == 1,
           "an absent plan is one finding too")


def _in_prose_is_not_counted() -> None:
    # The half the rule does not hold: an entry marked `in prose` is outside the
    # per-item count entirely, so adding one to an item that already agrees must not
    # make it disagree.
    text = _PLAN.replace("* ~~**M2.1", "* ~~**M9.9")
    plan_only_m016 = findings.plan(text)
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
        Case("a-leading-word-that-is-not-a-count", _a_leading_word_that_is_not_a_count),
        Case("block-size-boundaries", _block_size_boundaries),
        Case("disagreements", _disagreements),
        Case("in-prose-is-not-counted", _in_prose_is_not_counted),
    ]
