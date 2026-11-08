# SPDX-License-Identifier: Apache-2.0
"""Check [docs/assurance/findings-register.md](../../../docs/assurance/findings-register.md) against [PLAN.md](../../../PLAN.md) and [docs/implementation/completion-log.md](../../../docs/implementation/completion-log.md) (`K-82`, `K-113`).

- `K-82` checks bidirectional agreement between the findings register and the
  completion notes in [PLAN.md](../../../PLAN.md) and
  [docs/implementation/completion-log.md](../../../docs/implementation/completion-log.md)
  (via [vos/findings.py](../findings.py)): every counted finding in a note must have a
  register entry, every register entry must reference an existing item and have a valid
  type, disposition, and `Restates` target, every landed plan item must have a
  completion-log entry, and the register's two summary counts (`CLAIMS`) are checked
  and repaired under `--fix`.
- `K-113` checks that every landed item in [PLAN.md](../../../PLAN.md) retains only its
  header line, one summary line, and its completion-log link.
"""

from typing import TYPE_CHECKING

from vos import figures, findings

if TYPE_CHECKING:
    from . import Context

HEADING = "=== findings: the findings register against the plan's notes ==="

# Derived summary counts in docs/assurance/findings-register.md, registered in `ctx.q`.
ENTRY_COUNT = "findings the plan records"
ITEM_COUNT = "items whose findings the plan records"
CLAIMS: list[tuple[str, str, str, str]] = [
    (findings.REGISTER, ENTRY_COUNT, "digits",
     r"(?<=The plan records )[\d,]+(?= of them across)"),
    (findings.REGISTER, ITEM_COUNT, "digits",
     r"(?<=of them across )[\d,]+(?= items)"),
]


def run(ctx: Context) -> None:
    """Run `K-82` and `K-113` over the parsed findings register, plan, and completion log."""
    rep = ctx.rep
    rep.line(HEADING)

    # Read from the tracked corpus (`ctx.corpus`), never directly from untracked disk files.
    index = findings.parse(ctx.text(findings.REGISTER)
                           if findings.REGISTER in ctx.corpus else "")
    plan_text = ctx.text(findings.PLAN) if findings.PLAN in ctx.corpus else ""
    read = findings.plan(plan_text,
                         ctx.text(findings.LOG)
                         if findings.LOG in ctx.corpus else "")

    items = sorted({e.raised for e in index.entries})
    ctx.shared["findings the register indexes"] = len(index.entries)
    ctx.shared["findings the plan's notes count"] = sum(b.size for b in read.blocks)
    ctx.shared["landed items the completion log carries an entry for"] = len(read.log_items)
    ctx.q[ENTRY_COUNT] = len(index.entries)
    ctx.q[ITEM_COUNT] = len(items)

    found = findings.disagreements(index, read)
    for file, quantity, _, pattern in CLAIMS:
        result = figures.resolve_claim(ctx, file, pattern, str(ctx.q[quantity]),
                                       quantity)
        if bool(result.fixed):
            rep.line(result.fixed)
        if bool(result.finding):
            found.append(result.finding)

    opened = sum(1 for e in index.entries
                 if e.kind == "owed-act" and e.disposition == "open")
    rep.report("K-82", "finding(s) the register and the plan's notes disagree on:",
               found,
               f"the register indexes {len(index.entries)} findings across "
               f"{len(items)} items, one for each of the "
               f"{sum(b.size for b in read.blocks)} the notes count and "
               f"{sum(1 for e in index.entries if e.in_prose)} more they state in "
               f"prose, the completion log carries an entry for each of the plan's "
               f"{len(read.done)} landed items, and {opened} open owed acts stand "
               "where S1 reads them")
    rep.report("K-113", "landed item(s) keeping more than one summary line and the link "
               "to its completion-log entry:", findings.shapes(plan_text, read),
               f"each of the plan's {len(read.done)} landed items keeps its header, one "
               "summary line and a link to its own completion-log entry")
    rep.line()
