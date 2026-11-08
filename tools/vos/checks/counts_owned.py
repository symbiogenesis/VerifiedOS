# SPDX-License-Identifier: Apache-2.0
"""Check figures owned by a single requirement entry and restated verbatim in other documents (`K-69`)."""

import re
from typing import TYPE_CHECKING

from vos import figures
from vos.register import REGISTER

if TYPE_CHECKING:
    from . import Context

SPEC = "docs/spec.md"
CONTRACT = "docs/hardware/bank-count-dse-contract.md"

# (key, owner_requirement_id, owner_regex, [(target_file, site_regex), ...])
OWNED: list[tuple[str, str, str, list[tuple[str, str]]]] = [
    ("kernel-line-budget", "R-07-001", r"targeting ≤(\d+k) lines", [
        (SPEC, r"(?<=target ≤)\d+k(?= lines)"),
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
    # Tag-plane share of the codeword with its DECTED code at the normative (128-bit)
    # and fallback (64-bit) payloads, owned by `R-15-181a` (whose arithmetic K-54 checks).
    ("tag-plane-share", "R-15-181a",
     r"tag plane with its own code is \d+, some ([\d.]+)% of the payload", [
        (REGISTER, r"(?<=plus that code, some )[\d.]+(?=–[\d.]+% of the bulk array)"),
        (SPEC, r"(?<=plus that code, some )[\d.]+(?=–[\d.]+% of the bulk array)"),
        (SPEC, r"(?<=at 128, some )[\d.]+(?=% and [\d.]+% of the payload)"),
        (CONTRACT, r"(?<=plus its own DECTED code, some )[\d.]+"
                   r"(?= to [\d.]+% of the bulk array)"),
    ]),
    ("tag-plane-share-fallback", "R-15-181a",
     r"the tag plane with its code \d+ of them at ([\d.]+)%", [
        (REGISTER, r"(?<=–)[\d.]+(?=% of the bulk array)"),
        (SPEC, r"(?<=–)[\d.]+(?=% of the bulk array)"),
        (SPEC, r"(?<=% and )[\d.]+(?=% of the payload)"),
        (CONTRACT, r"(?<= to )[\d.]+(?=% of the bulk array)"),
    ]),
]

# Range figure owned by `R-15-007e`, preserving hyphen (`-`) vs. en-dash (`–`) at each site.
RANGE_OWNER = ("R-15-007e", r"the (\d+)-(\d+)% no-C penalty")
RANGE_SITES: list[tuple[str, str, str]] = [
    (REGISTER, r"(?<=the )\d+-\d+(?=% no-C penalty)", "{lo}-{hi}"),
    (SPEC, r"\d+–\d+(?=% code-size penalty for deleting the C extension)", "{lo}–{hi}"),
    (SPEC, r"(?<=the former )\d+-\d+(?=% code-size penalty)", "{lo}-{hi}"),
]


def owned_figures(ctx: Context) -> None:
    """K-69: figures fixed by an owning requirement entry match every registered restatement site (rewritten from the owner under `--fix`)."""
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
            if bool(r.fixed):
                rep.line(r.fixed)
            if bool(r.finding):
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
            if bool(r.fixed):
                rep.line(r.fixed)
            if bool(r.finding):
                missed.append(r.finding)

    rep.report("K-69", "owned figure(s) restated differently than their entry fixes:",
               missed,
               f"all {len(OWNED) + 1} owned figures are restated identically at "
               f"their {held} registered sites")
