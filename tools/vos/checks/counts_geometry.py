# SPDX-License-Identifier: Apache-2.0
"""counts, the welded block: one parameter, and the constraints that admit it.

The block-size declarations must agree and lie in the admissible set. The constraint
document keeps one derived candidate calculation; its other explanations use the
governing formulas and reference the exact bound R-15-007q owns. Removing those
incidental copies does not remove the source, equality or membership checks.
"""

import re
from typing import TYPE_CHECKING

from vos import capformat, figures, geometry
from vos.checks.counts_fields import PAYLOAD_RE

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

# R-15-007q's own statement of the welded block's ceiling. The bound is the width of
# the register the group comes back in, so it is the entry's to state and this rule's
# to recompute: of every site that writes a figure about this parameter, the entry is
# the only normative one, and the only one an edit can move without the model or a
# composition rendering wrong.
BLOCK_CEILING_RE = re.compile(r"the block at most \*\*(\d+) bytes\*\*")

# One required calculation presents the admissible set in bytes and granules.
# Repair both units together; the constraint rows refer to their source parameters.
BLOCK_CANDIDATE_SENTENCE = (
    r"\*\*the block is (?P<bytes>[\d, ]+or \d+) bytes\*\*, which is "
    r"(?P<granules>[\d, ]+or \d+) granules")


def _series(values: list[int]) -> str:
    """A set of candidates as the document writes one, not as a list repr.

    A repair writes prose back into a sentence, so the spelling is the sentence's: the
    members separated by commas with an `or` before the last, and no comma before it
    where there are only two, which is the one place the pattern would otherwise put
    one.
    """
    if len(values) == 2:
        return f"{values[0]} or {values[1]}"
    if len(values) < 2:
        return ", ".join(str(v) for v in values)
    return ", ".join(str(v) for v in values[:-1]) + f", or {values[-1]}"


def block_geometry(ctx: Context) -> None:
    """K-57: the welded block size, in every artifact that writes it.

    The model, composition, configuration template, harness and authored RTL must
    agree. Their selected value is a freeze decision, so disagreement is reported,
    never repaired. Missing source parameters are findings even if narrative copies
    are absent.

    The candidate set is recomputed from the model's granule and register width and
    R-15-181a's payload. Its single document calculation is repaired in both units.
    The ceiling R-15-007q fixes is checked against that same arithmetic but is never
    repaired: its normative decision stays with the register.
    """
    rep, reg = ctx.rep, ctx.reg
    geo = geometry.read(ctx.root, ctx.shared.get("bundle"))
    payload = PAYLOAD_RE.search(reg.body.get("R-15-181a", ""))
    # The destination register's width, read from the model rather than written here.
    # It was a bare `64` with a comment saying what it was, in a module whose own
    # preamble says it states no width of its own, and the group is the one that
    # exists to keep a figure from being a copy nothing holds.
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

    # The two derivable constraints that bind, C5 and C3 of the document. The floor is
    # one ECC codeword, no sub-codeword write existing at the array; the ceiling is the
    # widest tag group an integer destination can carry back. The rest of the derivable
    # rows are implied by these two over a power-of-two space, which is what the
    # document says and what this arithmetic is the other statement of.
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
