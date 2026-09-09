# SPDX-License-Identifier: Apache-2.0
"""Generated proof headers agree with the register after any arithmetic repairs."""

import copy
from typing import TYPE_CHECKING

from vos import corpus as corpus_mod
from vos import memplan, proofcites, proofheaders
from vos.register import REGISTER, read_register

if TYPE_CHECKING:
    from . import Context

HEADING = "=== headers: generated proof manifests against their requirement owners ==="


def run(ctx: Context) -> None:
    ctx.rep.line(HEADING)
    reg = ctx.reg
    if REGISTER in ctx.fixed:
        # Do not publish a register midway through a repair. Only this reader needs
        # its repaired lines; all other corpus indexes retain their current owner.
        corpus = copy.copy(ctx.corpus)
        corpus.by_name = {**corpus.by_name,
                          REGISTER: corpus_mod.from_text(ctx.fixed[REGISTER], REGISTER)}
        reg = read_register(corpus)
    rels = [rel for rel in ctx.corpus.tracked
            if proofcites.is_source(rel) and rel not in proofheaders.EXCLUDED]
    changed, faults = proofheaders.plan(ctx.root, reg, rels)
    if not rels:
        faults.append("the index carries no proof header for this rule to check")
    if ctx.fix:
        if memplan.SOURCE in changed:
            # K-88 already ran against the old source. Queue this dependent export
            # from the same pending bytes, without publishing either file early.
            try:
                ctx.fixed[memplan.ARTIFACT] = memplan.emit(
                    ctx.root, source_text=changed[memplan.SOURCE])
            except (RuntimeError, ValueError, KeyError) as exc:
                faults.append(f"{memplan.ARTIFACT}: generation from its repaired "
                              f"proof header failed: {exc}")
                del changed[memplan.SOURCE]
            else:
                ctx.rep.line(f"fixed: {memplan.ARTIFACT} from its repaired proof header")
        ctx.fixed.update(changed)
        for rel in changed:
            ctx.rep.line(f"fixed: {rel} generated requirement header")
    else:
        faults.extend(f"{rel}: generated requirement header is stale" for rel in changed)
    ctx.rep.report("K-109", "stale or unreadable generated proof header(s):", faults,
                   f"all {len(rels)} generated proof headers match their requirement owners")
    ctx.rep.line()
