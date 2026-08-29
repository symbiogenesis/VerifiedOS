# SPDX-License-Identifier: Apache-2.0
"""findings: the findings register against the plan's notes, in both directions.

The implementation plan produces findings and, until this register existed, nothing
read them. That cost three ways, all three of which are failures of *totality* rather
than of content: one fact was found at two items with nothing to say so, an owed act
had nowhere to live until somebody assembled S1's rows out of prose by hand, and a
methodological finding stayed a paragraph where it was a rule. An index that is
merely a snapshot fixes none of them, because the day it stops covering the plan is
the day it starts costing exactly what it was written to save, and nothing says so.

So the claim this group holds is totality and not shape. A completion note declares
its own findings, under a count with its bullets beneath it or as a bullet opening
`Finding`, and every one of those is required to have exactly one entry in the
register, and every entry to name an item the plan carries. Both directions matter
and they fail differently. A counted finding with no entry is the rediscovery this
whole artifact exists to end, arriving silently as a note grows. An entry naming a
finding its item no longer records is worse, because it will be believed: the
register would go on saying an act is owed at an item whose note has moved out from
under it. And an entry naming no item at all is what a split or a strike produces,
which this plan does often: six items were split at entry and four were struck, and
each of those moves an id that entries point at.

**The block's size is its bullets and never its own word**, which is the ordinary
recompute-rather-than-trust discipline applied to a document's own enumeration: held
against the word, a note that had come to lie about itself would carry a register
agreeing with the lie. The word is then held against the bullets as its own reading,
so a count and its block cannot drift apart either.

**Half the relation is a reading and the register says which half.** Most findings a
note states under a count, and that half is what is held here. The rest it states in
prose, and an entry indexing one of those carries `in prose` and is held only at its
item existing, because which prose sentence is a finding is a judgment and a judgment
is the thing no rule makes. That residue is declared in the register's own preamble
rather than left to be discovered, and it is the same shape every enumeration in this
tool declares: the tool decides that the sets agree and never that they are the right
sets.

**Fail-closed on the reading itself.** An entry whose type is none of the four the
register declares, whose disposition is none of the three, or which carries no
`Raised` line at all is an entry this group cannot place, and each is a finding rather
than an entry quietly dropped out of the comparison; so is an id carried twice, a
finding id being permanent and naming one finding. A `Restates` line is an intra-
document citation and resolves or is a finding, which is what keeps the register's own
answer to rediscovery from pointing at nothing. An absent register is one finding
rather than one empty comparison per item.

**Two figures are arithmetic and are repaired.** The register states its own size and
the number of items it indexes, both sums over its entries, so `--fix` rewrites them
exactly as it rewrites a subtotal. Nothing else here is repairable: an entry is a
reading of a note somebody wrote, and a missing one is a paragraph to index rather
than a figure to recompute.
"""

from typing import TYPE_CHECKING

from vos import figures, findings

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== findings: the findings register against the plan's notes ==="

# The register's own two derived figures, each captured alone out of the sentence that
# states them. They are claims in exactly the counts group's sense and are registered
# with that group's, so the floors group's requirement that every computed quantity be
# claimed stays total over these two as well.
ENTRY_COUNT = "findings the plan records"
ITEM_COUNT = "items whose findings the plan records"
CLAIMS: list[tuple[str, str, str, str]] = [
    (findings.REGISTER, ENTRY_COUNT, "digits",
     r"(?<=The plan records )[\d,]+(?= of them across)"),
    (findings.REGISTER, ITEM_COUNT, "digits",
     r"(?<=of them across )[\d,]+(?= items)"),
]


def run(ctx: Context) -> None:
    """K-82, over the two sides `vos.findings` reads and this group decides about."""
    rep = ctx.rep
    rep.line(HEADING)

    # the index and not the disk, on K-77's own ground: the checker's corpus is what
    # git tracks, so a register deleted from the index and left in the working tree is
    # a document this repository does not have
    index = findings.parse(ctx.text(findings.REGISTER)
                           if findings.REGISTER in ctx.corpus else "")
    read = findings.plan(ctx.text(findings.PLAN)
                         if findings.PLAN in ctx.corpus else "")

    items = sorted({e.raised for e in index.entries})
    ctx.shared["findings the register indexes"] = len(index.entries)
    ctx.shared["findings the plan's notes count"] = sum(b.size for b in read.blocks)
    ctx.q[ENTRY_COUNT] = len(index.entries)
    ctx.q[ITEM_COUNT] = len(items)
    # rebound rather than appended to: the counts group's own list is a module-level
    # constant, and mutating it here would grow it once per run in a process that
    # performs many, which the mutation selftest is
    ctx.claims = [*ctx.claims, *CLAIMS]

    found = findings.disagreements(index, read)
    for file, quantity, _, pattern in CLAIMS:
        result = figures.resolve_claim(ctx, file, pattern, str(ctx.q[quantity]),
                                       quantity)
        if result.fixed:
            rep.line(result.fixed)
        if result.finding:
            found.append(result.finding)

    opened = sum(1 for e in index.entries
                 if e.kind == "owed-act" and e.disposition == "open")
    rep.report("K-82", "finding(s) the register and the plan's notes disagree on:",
               found,
               f"the register indexes {len(index.entries)} findings across "
               f"{len(items)} items, one for each of the "
               f"{sum(b.size for b in read.blocks)} the plan's notes count and "
               f"{sum(1 for e in index.entries if e.in_prose)} more it states in "
               f"prose, and {opened} open owed acts stand where S1 reads them")
    rep.line()
