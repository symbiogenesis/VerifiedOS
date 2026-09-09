# SPDX-License-Identifier: Apache-2.0
"""K-104 regenerates the adapter's exception section from its Sail definitions."""

from typing import TYPE_CHECKING

from vos import capcauses

if TYPE_CHECKING:
    from . import Context


def cap_causes(ctx: Context) -> None:
    faults: list[str] = []
    try:
        for name in (capcauses.ADAPTER, *capcauses.OWNERS):
            if name not in ctx.corpus.tracked:
                raise capcauses.CauseError(f"the index does not carry {name}")
        actual = (ctx.root / capcauses.ADAPTER).read_text(encoding="utf-8")
        expected = capcauses.replace(actual, capcauses.emit(ctx.root))
        if actual != expected:
            if ctx.fix:
                ctx.fixed[capcauses.ADAPTER] = expected
                ctx.rep.line(f"fixed: {capcauses.ADAPTER} generated capability exceptions")
            else:
                faults.append(f"{capcauses.ADAPTER}: generated exception section is stale; "
                              "run tools/run.py check --fix")
    except (capcauses.CauseError, OSError, UnicodeError) as exc:
        faults.append(str(exc))
    ctx.rep.report("K-104", "stale or unreadable capability exception section(s):", faults,
                   "the adapter's exception section is regenerated from its Sail owners")
