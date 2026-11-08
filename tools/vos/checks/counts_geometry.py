# SPDX-License-Identifier: Apache-2.0
"""Check welded block-size declarations and candidate-set arithmetic (`K-57`, via [vos/geometry.py](../geometry.py))."""

import re
from typing import TYPE_CHECKING

from vos import capformat, figures, geometry
from vos.checks.counts_fields import PAYLOAD_RE

if TYPE_CHECKING:
    from . import Context

# Normative welded-block ceiling stated in `R-15-007q`.
BLOCK_CEILING_RE = re.compile(r"the block at most \*\*(\d+) bytes\*\*")

# Candidate-set sentence in `geometry.DOCUMENT` repaired in both bytes and granules under `--fix`.
BLOCK_CANDIDATE_SENTENCE = (
    r"\*\*the block is (?P<bytes>[\d, ]+or \d+) bytes\*\*, which is "
    r"(?P<granules>[\d, ]+or \d+) granules")


def _series(values: list[int]) -> str:
    """Format `values` as an English `or`-conjoined series (`16 or 32` or `16, 32, or 64`)."""
    if len(values) == 2:
        return f"{values[0]} or {values[1]}"
    if len(values) < 2:
        return ", ".join(str(v) for v in values)
    return ", ".join(str(v) for v in values[:-1]) + f", or {values[-1]}"


def block_geometry(ctx: Context) -> None:
    """K-57: welded block-size declarations agree and sit inside the admissible candidate set.

    Recomputes the power-of-two candidate set bounded below by one ECC codeword payload
    (`R-15-181a`) and above by `granule * XLEN` (`R-15-007q`), checks and repairs the
    candidate-set sentence in [`DOCUMENT`](../geometry.py#DOCUMENT) under `--fix`, and
    verifies that all declared block-size sites in [vos/geometry.py](../geometry.py)
    agree and lie within the candidate set (report-only for site declarations and
    `R-15-007q`'s ceiling).
    """
    rep, reg = ctx.rep, ctx.reg
    geo = geometry.read(ctx.root, ctx.shared.get("bundle"))
    payload = PAYLOAD_RE.search(reg.body.get("R-15-181a", ""))
    xlen = capformat.read(ctx.root, ctx.shared.get("bundle")).defined.get("xlen")

    if geo.granule_exp is None or payload is None or xlen is None:
        rep.report("K-57", "block-geometry reading(s) that have moved:", [
            None if geo.granule_exp is not None else
            "the model no longer declares log2_cap_size in a form this rule reads, so "
            "there is no granule to derive the block against",
            None if payload is not None else
            "R-15-181a no longer states the codeword's data payload, so there is no "
            "floor to derive the block against",
            None if xlen is not None else
            "the model no longer declares xlen in a form this rule reads, so the "
            "integer register the group comes back in has no width",
        ])
        ctx.shared["block_candidates"] = 0
        return

    findings: list[str] = []
    written = {site: exp for site, exp in geo.sites.items() if exp is not None}
    findings += [f"{site} no longer writes the block size in a form this rule reads"
                 for site, exp in geo.sites.items() if exp is None]

    if len(set(written.values())) > 1:
        findings += [f"{site} writes a block of {1 << exp} bytes"
                     for site, exp in sorted(written.items())]

    # Floor: one ECC codeword (C5); ceiling: widest tag group fitting in XLEN (C3).
    granule = 1 << geo.granule_exp
    codeword = int(payload.group(1)) // 8
    ceiling = granule * xlen                     # caps_per_block at most XLEN
    candidates = [b for e in range(13) if codeword <= (b := 1 << e) <= ceiling]

    sentence = figures.resolve_line(
        ctx, geometry.DOCUMENT, BLOCK_CANDIDATE_SENTENCE,
        {"bytes": _series(candidates),
         "granules": _series([b // granule for b in candidates])},
        "the block's candidate set")
    findings += sentence.findings
    for repaired in sentence.fixed:
        rep.line(repaired)

    stated = BLOCK_CEILING_RE.search(reg.accept_text.get("R-15-007q", ""))
    if stated is None:
        findings.append("R-15-007q no longer states the welded block's ceiling in a "
                        "form this rule reads, so the bound the destination register "
                        "sets has no normative statement left")
    elif int(stated.group(1)) != ceiling:
        findings.append(f"R-15-007q states a ceiling of {stated.group(1)} bytes, the "
                        f"{granule}-byte granule and an integer destination give "
                        f"{ceiling}")

    for site, exp in written.items():
        if (1 << exp) not in candidates:
            findings.append(f"{site} writes a block of {1 << exp} bytes, which is "
                            "outside the candidate set the constraints admit")

    ctx.shared["block_candidates"] = len(candidates)
    rep.report("K-57", "welded block-size site(s) that disagree:", findings,
               f"the welded block size is {1 << next(iter(written.values()), 0)} bytes "
               f"in all {len(geo.sites)} sites that write it, inside a candidate set of "
               f"{len(candidates)} under the {ceiling}-byte ceiling R-15-007q states")
