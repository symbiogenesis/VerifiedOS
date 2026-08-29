# SPDX-License-Identifier: Apache-2.0
"""counts, the owned figures: a number one entry fixes and other sites repeat.

The tag plane's shape without the arithmetic. A budget, a measurement or a frozen
width is one entry's statement and every other site restates it verbatim, so the
owner is where the decision lives and every registered site is held to it. Each row
below is the figure's key, the entry that owns it, the pattern reading it out of that
entry's own lines, and the sites a repair rewrites from the owner.
"""

import re
from typing import TYPE_CHECKING

from vos import figures
from vos.register import REGISTER

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

SPEC = "docs/spec.md"

# K-69: a figure one entry fixes and other sites restate verbatim, with no arithmetic
# between them: the K-54 shape without the ratio. Each row is the figure's key, the
# owning entry, the pattern reading it from that entry's own lines, and the sites the
# repair rewrites from the owner. Each site pattern captures the figure alone and
# holds every occurrence its file carries.
OWNED: list[tuple[str, str, str, list[tuple[str, str]]]] = [
    ("kernel-line-budget", "R-07-001", r"targeting ≤(\d+k) lines", [
        # anchored on the microkernel's own sentence, not the stock magnitude
        # idiom: "on the order of Nk LoC" is a spelling any entry may use, and a
        # repair rewrites every match its pattern holds
        (REGISTER, r"(?<=microkernel is on the order of )\d+k(?= LoC of verified C)"),
        (SPEC, r"(?<=\(~)\d+k(?= LoC verified C\))"),
        (SPEC, r"(?<=target ≤)\d+k(?= lines)"),
        # the prose writes a thin space (U+2009) between the sign and the figure
        (SPEC, r"(?<=below the ≤\u2009)\d+k(?=-line target)"),
    ]),
    ("range-decoder-share", "R-15-067g", r"measured at roughly (\d+)% of decode time", [
        (SPEC, r"(?<=measured at roughly )\d+(?=% of decode time)"),
    ]),
    ("reference-slot-width", "R-15-036a", r"seven (\d+)-bit slots", [
        (SPEC, r"(?<=At the reference )\d+(?=-bit slot)"),
        (SPEC, r"(?<=collects one )\d+(?=-bit slot rather than four bytes)"),
        (REGISTER, r"(?<=collects one )\d+(?=-bit slot rather than four bytes)"),
    ]),
    ("rvc-break-even", "R-15-036k", r"fails below \*p\* = ([\d.]+)", [
        (SPEC, r"(?<=reached at \*p\* = \*\*)[\d.]+(?=\*\*)"),
    ]),
]

# The one owned figure that is a range, held in both dash spellings: the documents
# write 33-43 in an entry's own line and 33–43 in running prose, both derived from
# the owner's capture below, so neither spelling is normalized away.
RANGE_OWNER = ("R-15-007e", r"the (\d+)-(\d+)% no-C penalty")
RANGE_SITES: list[tuple[str, str, str]] = [
    (REGISTER, r"(?<=the )\d+-\d+(?=% no-C penalty)", "{lo}-{hi}"),
    (SPEC, r"(?<=an accepted )\d+–\d+(?=% code-size penalty)", "{lo}–{hi}"),
    (SPEC, r"(?<=the former )\d+-\d+(?=% code-size penalty)", "{lo}-{hi}"),
]


def owned_figures(ctx: Context) -> None:
    """K-69: every figure one entry fixes, restated identically wherever it is stated.

    The K-54 shape without the arithmetic: a budget, a measurement, or a frozen width
    is one entry's statement, other sites repeat it verbatim, and an edit to the owner
    left the repeats standing in pairs whose other side states no figure at all, which
    is the drift the co-statement survey found K-61 structurally cannot see. Each
    figure is read from the entry that fixes it and every registered site is held to
    it; under `--fix` the sites are rewritten from the owner, never the other way,
    because the owner is where the decision lives.

    The one range among them is held in both dash spellings on purpose: an entry's own
    line writes 33-43 and running prose writes 33–43, both derived from the owner's
    captures, so the hold does not flatten a typographic convention.
    """
    rep, reg = ctx.rep, ctx.reg
    missed: list[str] = []
    held = 0

    def owner_text(ident: str) -> str:
        return reg.body.get(ident, "") + " " + reg.accept_text.get(ident, "")

    for key, ident, owner_pattern, sites in OWNED:
        m = re.search(owner_pattern, owner_text(ident))
        if not m:
            missed.append(f"{ident} no longer states the {key} figure in a form this "
                          "rule reads")
            continue
        for file, pattern in sites:
            held += 1
            r = figures.resolve_claim(ctx, file, pattern, m.group(1),
                                      f"the {key} figure")
            if r.fixed:
                rep.line(r.fixed)
            if r.finding:
                missed.append(r.finding)

    range_id, range_pattern = RANGE_OWNER
    m = re.search(range_pattern, owner_text(range_id))
    if not m:
        missed.append(f"{range_id} no longer states the no-C code-size range in a "
                      "form this rule reads")
    else:
        lo, hi = m.group(1), m.group(2)
        for file, pattern, shape in RANGE_SITES:
            held += 1
            r = figures.resolve_claim(ctx, file, pattern,
                                      shape.format(lo=lo, hi=hi),
                                      "the no-C code-size range")
            if r.fixed:
                rep.line(r.fixed)
            if r.finding:
                missed.append(r.finding)

    rep.report("K-69", "owned figure(s) restated differently than their entry fixes:",
               missed,
               f"all {len(OWNED) + 1} owned figures are restated identically at "
               f"their {held} registered sites")
