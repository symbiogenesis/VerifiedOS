# SPDX-License-Identifier: Apache-2.0
"""counts, the welded block: one parameter, and the constraints that admit it.

Four instructions share the block size, four artifacts write it, and the document
beside them states the set it may be taken from and the bound it sits under. The set
and the bound are arithmetic over the granule the model declares and the codeword
R-15-181a fixes, so both are recomputed here rather than trusted where they are
written.
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

# The constraint document's own statements of the figures this rule computes. The two
# in §3 are held as whole sentences because each states its figure a second way, the
# ceiling beside the granule it is taken at and the set in bytes and again in granules:
# a repair that wrote one and left the other would leave the sentence describing a set
# it no longer carries, which is the shape that keeps K-70 report-only. The two in the
# constraint table stand alone in their own rows and are claims accordingly.
BLOCK_CEILING_SENTENCE = (
    r"At the (?P<granule>\d+)-byte granule R-15-203 fixes, that is a "
    r"ceiling of \*\*(?P<ceiling>\d+) bytes\*\*")
BLOCK_CANDIDATE_SENTENCE = (
    r"\*\*the block is (?P<bytes>[\d, ]+or \d+) bytes\*\*, which is "
    r"(?P<granules>[\d, ]+or \d+) granules")
BLOCK_C3_CEILING = r"(?<=so the block is at most )\d+(?= bytes)"
BLOCK_C5_CODEWORD = r"(?<=whole number of ECC codewords, )\d+(?= bytes at the payload)"


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

    Four instructions share one parameter, and it is written at four sites: the model's
    declaration, the frozen profile's composition, the generated configurations'
    template, and a literal in the model's own harness. The assertions inside the model
    hold the declaration and the composition together at run time; nothing held the
    template or the harness's literal against them, nor the set the document beside them
    states, and a document stating a figure nothing checks is worse than one that states
    none, because it reads as checked.

    The candidate set is recomputed rather than trusted, from the granule the model
    declares and the codeword the payload gives, so a candidate row edited in the
    document without its arithmetic is a finding.

    **What is repaired and what is reported divides on the two grounds, and the two
    grounds fall on different sides of it.** All four sites are under a `-text` tree,
    where a rewrite risks the line-ending sweep the tools' `newline=""` convention
    exists to prevent, so a site that disagrees is reported; and which value inside the
    set is taken is R-15-014a's second act rather than arithmetic, so it is not this
    rule's to write at all. Neither ground reaches the *document's* own figures: they
    are arithmetic over the granule and the codeword, in a document git normalizes like
    every other, so the ceiling, the candidate set, and the two constraint rows that
    restate them are rewritten from the arithmetic under `--fix`. Two of the four are
    repaired as whole sentences, because the prose beside each states its figure a second
    way, the ceiling beside the granule it is taken at and the set in bytes and again in
    granules: half a sentence rewritten leaves the other half describing a set it no
    longer carries, which is the shape that keeps K-70 report-only. What the document
    states from an operand this rule does not read stays a person's: R-15-181a's fallback
    codeword and the halved floor it gives are stated in those same two places and held
    by nothing.

    The ceiling has a ground as well as a value, and R-15-007q states both: the group
    comes back in one integer register, so the bound is that register's width times the
    granule. Holding the entry's number against the same arithmetic is what keeps the
    derivable half of the constraint from having its only normative statement be one a
    later edit could move on its own. That one is reported and never repaired however
    the document's copies are treated: the value is the entry's, the arithmetic is here,
    and a repair rewriting the normative statement from the tool would delete the
    decision instead of checking it.
    """
    rep, reg = ctx.rep, ctx.reg
    geo = geometry.read(ctx.root)
    payload = PAYLOAD_RE.search(reg.body.get("R-15-181a", ""))
    # The destination register's width, read from the model rather than written here.
    # It was a bare `64` with a comment saying what it was, in a module whose own
    # preamble says it states no width of its own, and the group is the one that
    # exists to keep a figure from being a copy nothing holds.
    xlen = capformat.read(ctx.root).defined.get("xlen")

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

    for pattern, want, what in (
        (BLOCK_CEILING_SENTENCE,
         {"granule": str(granule), "ceiling": str(ceiling)},
         "the block-size ceiling"),
        (BLOCK_CANDIDATE_SENTENCE,
         {"bytes": _series(candidates),
          "granules": _series([b // granule for b in candidates])},
         "the block's candidate set"),
    ):
        sentence = figures.resolve_line(ctx, geometry.DOCUMENT, pattern, want, what)
        findings += sentence.findings
        for repaired in sentence.fixed:
            rep.line(repaired)

    for pattern, value, what in ((BLOCK_C3_CEILING, ceiling, "the C3 row's ceiling"),
                                 (BLOCK_C5_CODEWORD, codeword, "the C5 row's codeword")):
        row = figures.resolve_claim(ctx, geometry.DOCUMENT, pattern, str(value), what)
        if row.fixed:
            rep.line(row.fixed)
        if row.finding:
            findings.append(row.finding)

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
