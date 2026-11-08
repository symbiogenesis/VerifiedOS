# SPDX-License-Identifier: Apache-2.0
"""Check core-class vector geometry and core-roster counts across prose and composition (`K-60`, via [vos/coreclass.py](../coreclass.py))."""

from typing import TYPE_CHECKING

from vos import coreclass

if TYPE_CHECKING:
    from . import Context


def core_classes(ctx: Context) -> None:
    """K-60: core-class vector geometries, core-roster counts, and `VLEN=n` tokens match the primary Sail composition.

    Checks that:
    1. Every prose core-class table ([spec.md](../../../docs/spec.md),
       [isa-profile.md](../../../docs/hardware/isa-profile.md), and `R-15-113`) states
       the per-class vector geometry declared in
       [`CONFIG`](../coreclass.py#CONFIG) (`R-15-005`, `R-15-113`).
    2. The per-class core counts in [spec.md](../../../docs/spec.md) match the composed
       `platform.core_roster`.
    3. Every unfenced `VLEN=n` token in the Markdown corpus names a non-zero `VLEN`
       present in the composed core classes.
    """
    rep, reg = ctx.rep, ctx.reg
    cc = coreclass.read(ctx.root, reg.body.get("R-15-113", ""))

    findings = [f"{site} no longer writes the core-class table in a form this rule reads"
                for site, table in sorted(cc.stated.items()) if table is None]
    if cc.declared is None:
        findings.append(f"{coreclass.CONFIG} no longer declares a per-class vector "
                        "geometry this rule reads")
    if cc.roster is None:
        findings.append(f"{coreclass.CONFIG} no longer declares a core roster this "
                        "rule reads")

    if cc.declared is not None:
        for site, table in sorted(cc.stated.items()):
            if table is None:
                continue
            findings += [
                f"{site} states {name}-class at "
                + (f"VLEN={table[name]}" if table[name] else "no vector geometry")
                + ", the composition declares "
                + (f"VLEN={cc.declared[name]}" if cc.declared[name] else "none")
                for name in coreclass.CLASSES if table[name] != cc.declared[name]]

    if cc.roster is not None:
        if not cc.counts:
            findings.append("the specification's core-class table states no counts this "
                            "rule reads, so nothing holds the roster to a stated one")
        findings += [f"the specification states {n} {name}-class core(s) and the "
                     f"composed roster carries {cc.roster[name]}"
                     for name, n in sorted(cc.counts.items()) if cc.roster[name] != n]

    tokens = 0
    if cc.declared is not None:
        geometries = {v for v in cc.declared.values() if v}
        for doc in ctx.corpus.docs:
            for m in coreclass.VLEN_RE.finditer(doc.raw):
                if doc.is_fenced(m.start()):
                    continue
                tokens += 1
                if int(m.group(1)) not in geometries:
                    findings.append(
                        f"{doc.name}:{doc.at(m.start())} states VLEN={m.group(1)}, "
                        f"a geometry no composed class carries")

    ctx.shared["core_class_sites"] = sum(
        1 for table in cc.stated.values() if table is not None) + (
        (cc.declared is not None) + (cc.roster is not None))
    ctx.shared["vlen_tokens"] = tokens
    rep.report("K-60", "core-class table site(s) that disagree:", findings,
               f"the {len(coreclass.CLASSES)} core classes carry one vector geometry "
               f"across all {len(cc.stated) + 1} sites that write it, the "
               f"{len(cc.counts)} stated counts are the composed roster's, and every "
               f"one of the corpus's {tokens} VLEN tokens is a composed geometry")
