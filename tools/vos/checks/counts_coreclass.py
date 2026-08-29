# SPDX-License-Identifier: Apache-2.0
"""counts, the core classes: one table, written in four idioms.

One Sail model is parameterized by core class, and what each class *is* is stated
three times in prose and once in the composition the model is built from. The
composition is the reference and the prose sites are held against it; the reading
itself is `vos/coreclass.py`'s, so nothing here states a geometry of its own.
"""

from typing import TYPE_CHECKING

from vos import coreclass

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context


def core_classes(ctx: Context) -> None:
    """K-60: the core-class table, in every artifact that writes it.

    One Sail model is parameterized by core class (R-15-005), and the table saying what
    each class *is* is written four times: once as the specification's core-class table,
    once as the profile's, once as the register's one-sentence enumeration, and once as
    the class table the model is actually composed from. The first three are prose in
    three different idioms, which is what makes this the shape where an edit to one
    renders correctly in all four; the fourth is the only one the machine reads, so a
    document that has drifted from it describes a machine nobody runs.

    Counts are held on a narrower ground and it is worth stating, because R-15-113 calls
    them composition parameters rather than architecture. A machine may carry any
    roster. This repository composes exactly one, so the reference instantiation the
    specification states is a claim about *that* roster, and a count in prose that no
    roster realizes is a figure nobody renders wrong. Only the specification states
    counts, so only it is held against the roster.

    Reported and never repaired, for K-57's two reasons: the composition is under a
    `-text` tree where a rewrite risks the line-ending sweep the tools' `newline=""`
    convention exists to prevent, and which geometry a class takes is R-15-108's
    exploration rather than arithmetic.
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

    # Every readable prose site against the one table the machine is built from. The
    # composition is the reference and not merely a fourth opinion: it is what the
    # emulator, the generated devicetree, and the validator all read.
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

    # The free-prose tokens beyond the four table sites: a VLEN=n anywhere in the
    # corpus is a claim about some composed class's datapath, and the ones outside
    # the tables were held by nothing, so a re-picked geometry (R-15-108 names each
    # class's VLEN as a searched parameter) moved the tables and left the prose
    # citing a machine no longer composed. Membership is the strongest form the
    # token admits: a bare VLEN=n names no class, so a swap of two classes'
    # geometries stays in-set and is the residue the registry row declares.
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
