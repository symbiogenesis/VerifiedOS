# SPDX-License-Identifier: Apache-2.0
"""Both root agent entry points carry the same working rules."""

from typing import TYPE_CHECKING

from vos.cli import sync_instructions

if TYPE_CHECKING:
    from . import Context

HEADING = "=== instructions: both agent entry points carry the same working rules ==="


def run(ctx: Context) -> None:
    ctx.rep.line(HEADING)
    faults = [f"{name} is not tracked" for name in sync_instructions.NAMES
              if name not in ctx.corpus.tracked]
    try:
        sync_instructions.sync(ctx.root, check=True)
    except (ValueError, OSError) as exc:
        faults.append(str(exc))
    ctx.rep.report("K-110", "missing or divergent agent instructions:", faults,
                   "AGENTS.md and CLAUDE.md are tracked and byte-identical")
    ctx.rep.line()
