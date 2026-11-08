# SPDX-License-Identifier: Apache-2.0
"""freeze: check the profile-freeze measurement instrument against its contract (K-77).

[docs/implementation/contracts/freeze-measurement.md](../../../docs/implementation/contracts/freeze-measurement.md)
defines the corpus members, recipe steps, operand classes, region classes and refusal
reasons, decisions, report blocks, declared parameters, and CI predicates implemented by
[freeze.py](../freeze.py).

K-77 checks agreement in both directions over:
- each of those nine enumerations (as sets, rejecting duplicates and empty tables),
- the corpus-to-decision `Feeds` relation (§2 vs. `DECISIONS`),
- the per-decision threshold bindings (§6 and §8 vs. `DECISIONS`), and
- the refusal-reason prose count in §5 against the enumerated refusal bullets.

The contract is read from the tracked corpus (`ctx.corpus`) rather than directly from disk.
"""

from typing import TYPE_CHECKING

from quarantine import freeze

if TYPE_CHECKING:
    from . import Context

HEADING = "=== freeze: the measurement instrument against its contract ==="


def run(ctx: Context) -> None:
    """Run K-77 and record enumeration and relation sizes in `ctx.shared`."""
    rep = ctx.rep
    rep.line(HEADING)

    # Read from the tracked corpus so an untracked or index-deleted file does not pass.
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
