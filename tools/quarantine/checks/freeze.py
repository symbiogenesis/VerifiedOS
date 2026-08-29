# SPDX-License-Identifier: Apache-2.0
"""freeze: the measurement instrument against the contract that defines it.

`docs/freeze-measurement-contract.md` fixes the instrument M1.8 builds: the corpus
members, the recipe steps, the operand classes, the region classes with their
enumerated refusal reasons, the decisions, the report blocks, the declared
parameters, and the CI predicates. `tools/quarantine/freeze.py` is that instrument, and
every one of those enumerations is a *membership it has to carry*, because each is
behaviour: a corpus member is a producer and a set of pins the report records, a
region class is a row with one refusal count per reason under it, a decision is a
column set and a threshold, and a predicate is a function that can reject a report.

Nothing held the two together. The views group holds the contract against the
*register*, so a requirement the contract must carry is checked; K-70 holds
R-15-014a's closed delta against the contract's §1 and §10, so a delta item nothing
instruments is checked. Neither reaches the analyzer at all, and the analyzer is
where the enumeration turns into work. A member added to the contract and not to the
instrument is a report block nobody writes, and the gate of §9 rejects the report
for a reason no reader would trace back to this edit; one added to the instrument
and not to the contract is a column measuring something nothing asked for, which is
worse, because it will be believed.

**Both directions, one pair per enumeration.** Each is held as a set rather than as
a count: a count would move under `--fix` as the new member landed and leave the
sentence forbidding it standing after the edit that falsified it, which is the shape
K-73 was written against.

**Two further pairs beside those are relations and not memberships**, because each is
a place a membership stops being enough.

- **The feeds column is an inversion.** §2 states which decisions each corpus member
  feeds and the instrument states which members each decision is measured over, and
  the two are the same relation written from its two ends. Holding only the member
  ids would pass a report in which FM-4 is carried, FD-7 names it, and §2 says it
  feeds FD-5 alone, which is `G-1` deciding about the wrong set. It is quantified
  over the **union** of the two rosters rather than over the instrument's own, because
  the failure a per-member walk cannot reach is an addition: a decision naming a
  member neither side declares is a corpus this analyzer would go looking for.
- **A declared parameter is bound per decision, not per set.** §8 collects the numbers
  the contract chooses so that every judgment is findable in one table, and §6 states
  in each decision's own section which of them it spends. A set comparison over §8's
  keys passes any permutation of the two, including FD-4 spending the 0.5% floor that
  costs opcode space where the contract puts the 0.1% one that costs none. So four
  of the keys are held by the decision they name outright, and the two backticked
  floors by whether the decision's own §6 section names them, in both directions.

**One count is read and the rest are refused.** §5 states in words how many refusal
reasons it enumerates, and a reason added to the document's bullets and to the
instrument's tuple at once passes every membership while that sentence stands, so the
sentence is held against the bullets. Nothing else here reads a count, for the reason
above.

**Fail-closed on the reading itself, and the reading is of the index.** A contract
outside the checker's corpus is one finding rather than one empty comparison per
enumeration, and an enumeration this rule reads and finds empty stops its own pair
rather than reporting that two empty sets agree. The corpus is what git tracks, so a
contract deleted from the index and left in the working tree is a document this
repository does not have; reading it off disk instead would report green over it,
which is the one place this group and the tool that shares its parse have to differ.
The quarantine's gate carries a member count for each enumeration and a size for each
of the two relations besides, and the second is a floor under the *rule* rather than
under the document: a relation dropped from the comparison narrows what K-77 decides
with every gate still green, and no membership floor can see that.

**Report-only, and the ground is the tool's ordinary split.** Adding a member to the
instrument is writing a producer, a pin set, a column set, or a predicate body,
which is code and not arithmetic; removing one from the contract is a specification
act of the R-18-003b class. Neither is a figure to recompute, so `--fix` rewrites
nothing here and the finding names the side that has to be edited by a person.
"""

from typing import TYPE_CHECKING

from quarantine import freeze

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== freeze: the measurement instrument against its contract ==="


def run(ctx: Context) -> None:
    """K-77, over the pairs `quarantine.freeze` states once and two callers read.

    The comparison lives beside the parse rather than here, because `freeze-report.py`
    asks the same question of the same document before it will report about a set that
    is not its contract's, and two copies of one list is the drift this checker exists
    to catch. What is this group's own is the verdict, the floors it registers, and the
    reasoning above.
    """
    rep = ctx.rep
    rep.line(HEADING)

    # the index and not the disk: the checker's corpus is what git tracks, so a contract
    # deleted from the index and left in the working tree is a document this repository
    # does not have, and reading it off disk would report green over it
    present = freeze.CONTRACT in ctx.corpus
    contract = freeze.parse(ctx.text(freeze.CONTRACT) if present else "")
    enumerated = freeze.enumerations(contract)
    for enum in enumerated:
        ctx.shared[enum.floor] = len(enum.stated)
    ctx.shared.update(freeze.relations(contract))

    if not contract.present:
        rep.report("K-77", "instrument-and-contract disagreement(s):",
                   [f"{freeze.CONTRACT} is not in the checker's corpus, so the "
                    f"instrument {freeze.MODULE} runs against nothing and every "
                    "enumeration it carries is held by no document"])
        rep.line()
        return

    sized = freeze.relations(contract)
    rep.report("K-77", "instrument-and-contract disagreement(s):",
               freeze.disagreements(contract),
               f"the instrument carries every enumeration {freeze.CONTRACT} states, in "
               f"both directions, over its {len(contract.members)} corpus members, "
               f"{len(contract.decisions)} decisions and {len(contract.predicates)} CI "
               f"predicates, and both relations beside them, "
               f"{sized['freeze corpus feeds edges']} feeds edges and "
               f"{sized['freeze threshold bindings in §6']} threshold bindings")
    rep.line()
