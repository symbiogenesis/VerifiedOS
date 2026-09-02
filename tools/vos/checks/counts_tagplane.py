# SPDX-License-Identifier: Apache-2.0
"""counts, the tag plane: the ratio one register field fixes, wherever it is stated.

A cardinality is not the only figure a document can restate, and this is the second
kind. The tag plane's cost is not a count of anything: it is one register field, the
granule width, read as a ratio, and four documents state that ratio in four spellings
between them. Nothing about it is anybody's measurement, so a granule that moves has
to move every one of them in the same edit, which is exactly what a claim is. The
band beside it is the other half: the DECTED code over the plane is a width
R-15-181a states as a judgment, and everything built on that width is arithmetic
again, the plane's share of the codeword with its code and the megabytes a gigabyte
of data then carries, so the share is held against the entry's own bit counts and
the band against the share, and only the code's width itself is never rewritten.
"""

import re
from typing import TYPE_CHECKING

from vos import figures
from vos.checks.counts_fields import GRANULE_RE, PAYLOAD_RE
from vos.register import REGISTER

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

SPEC = "docs/spec.md"
ALTERNATIVES = "docs/architectural-alternatives.md"
ESTIMATES = "docs/performance-estimates.md"

# file, key, and the pattern capturing the stated figure alone. Each pattern holds
# exactly one site in its own file, which a claim owes because a repair rewrites every
# site the pattern matches.
TAG_PLANE: list[tuple[str, str, str]] = [
    (REGISTER, "mb-per-gb", r"(?<=granule is )[\d.]+(?= MB per GB of data)"),
    (REGISTER, "plane-exact", r"(?<=native tags cost )[\d.]+(?=% plus that code)"),
    (REGISTER, "plane-short", r"(?<=tag-plane density doubles to )[\d.]+(?=% of the array)"),
    (SPEC, "mb-per-gb", r"(?<=granule is )[\d.]+(?= MB per GB of data)"),
    (SPEC, "plane-exact", r"(?<=native tags cost )[\d.]+(?=% plus that code)"),
    (SPEC, "plane-short", r"(?<=the tag plane doubles to )[\d.]+(?=% of the array)"),
    (REGISTER, "plane-short", r"(?<=tag plane's ~)[\d.]+(?=% share of the array)"),
    (SPEC, "plane-short", r"(?<=tag plane's ~)[\d.]+(?=% share of the array)"),
    (ALTERNATIVES, "mb-per-gb", r"(?<=granule is )[\d.]+(?= MB per GB of data)"),
    (ESTIMATES, "plane-short", r"(?<=and )[\d.]+(?=% in array area)"),
    (ESTIMATES, "plane-short", r"(?<=the plane is )[\d.]+(?=% of the array rather than)"),
    (ESTIMATES, "half-short", r"(?<=% of the array rather than )[\d.]+(?=% and its DECTED)"),
    (ESTIMATES, "payload", r"(?<=codeword is unchanged at )\d+(?= data bits)"),
    # [\w-]+ and not \w+: the expected value is figures.words(payload // granule), and
    # every word form from twenty-one up that is not a round ten is hyphenated, so a
    # bare \w+ would repair to a spelling its own pattern can no longer find.
    (ESTIMATES, "tags-per-codeword", r"(?<=data bits carrying )[\w-]+(?= tag bits)"),
]

# The plane's share of the codeword, read from the entry that fixes the code over it:
# the DECTED check bits it states as a judgment, the bit count it gives the plane with
# that code, and the share of the payload it states for the two together. The last two
# are arithmetic over the first and the fields above, so both are held.
SHARE_RE = re.compile(r"DECTED code of about (\d+) bits.*?tag plane with its own code "
                      r"is (\d+), some ([\d.]+)% of the payload")

# The DECTED-inclusive bands beside the bare figures. The code's width is R-15-181a's
# judgment and is never rewritten; what is machine-held is that each band opens at
# the arithmetic of that width, above the bare plane it includes, and that the sidecar
# figure beside them is the product it claims to be. The bands' upper ends are the
# fallback codeword's and are held by K-69 against the entry stating them.
BAND_MB_RE = re.compile(r"about (\d+)–(\d+) MB of SRAM per GB")
BAND_PCT_RE = re.compile(r"some ([\d.]+)–([\d.]+)% of the bulk array")
SIDECAR_RE = re.compile(r"consume (\d+)–\d+% of a [\d.]+–([\d.]+) GB first class")
TIER_RE = re.compile(r"a (\d+) GB bulk tier")


def tag_plane(ctx: Context) -> None:
    """K-54: every stated tag-plane figure, against the two fields it is arithmetic over.

    The granule is one bit of validity per so many bits of data, so the plane is
    `100/granule` percent of the array it covers and `1000/granule` megabytes per
    gigabyte of it, and the ECC codeword carries `payload/granule` tag bits. Three
    quantities, two register fields, and four documents that between them state the
    result eleven times over.

    A reading that has moved is the one finding this rule cannot repair: with no
    granule there is no arithmetic to compare against, so it reports and stops rather
    than passing over an empty claim table, which is the vacuity the floors group
    exists to refuse and would not see here, the table being a literal.
    """
    rep, reg = ctx.rep, ctx.reg

    granule = GRANULE_RE.search(reg.body.get("R-15-203", ""))
    payload = PAYLOAD_RE.search(reg.body.get("R-15-181a", ""))
    if not granule or not payload:
        rep.report("K-54", "tag-plane field(s) the register no longer fixes:", [
            None if granule else
            "R-15-203 no longer states the granule width in a form this rule reads",
            None if payload else
            "R-15-181a no longer states the codeword's data payload in a form this "
            "rule reads",
        ])
        ctx.shared["tag_plane"] = 0
        return

    g, p = int(granule.group(1)), int(payload.group(1))
    expected = {
        "plane-exact": figures.quantize(100 / g, 4),
        "plane-short": figures.quantize(100 / g, 2),
        # the halved comparator: the plane a granule twice this wide would have given,
        # which the estimate row states beside the one this profile took
        "half-short": figures.quantize(100 / (2 * g), 2),
        "mb-per-gb": figures.quantize(1000 / g, 1),
        "payload": str(p),
        "tags-per-codeword": figures.words(p // g),
    }

    missed: list[str] = []
    for file, key, pattern in TAG_PLANE:
        # The spans are discarded where the CLAIMS loop keeps them, and that is an
        # invariant rather than an oversight: a kept span exists to exempt its site
        # from K-26, which proposes only the distinctive forms of the counted
        # quantities, and no tag-plane figure is ever one of those, each being a
        # decimal ratio, a payload width no quantity counts, or a word form below
        # eleven. A tag-plane site therefore never needs a span to be exempted.
        r = figures.resolve_claim(ctx, file, pattern, expected[key],
                                  f"the tag plane's {key} figure")
        if r.fixed:
            rep.line(r.fixed)
        if r.finding:
            missed.append(r.finding)

    # The plane's share with its code, held against the entry's own bit counts: the
    # plane is the codeword's tag bits plus the check bits over them, and the share is
    # that over the payload.
    share = SHARE_RE.search(reg.body.get("R-15-181a", ""))
    plane_bits: int | None = None
    if not share:
        missed.append("R-15-181a no longer states the tag plane's share of the codeword "
                      "in a form this rule reads")
    else:
        code, plane_bits, stated = int(share.group(1)), int(share.group(2)), share.group(3)
        if plane_bits != p // g + code:
            missed.append(f"R-15-181a puts the tag plane with its code at {plane_bits} "
                          f"bits, where its {p // g} tag bits under {code} check bits give "
                          f"{p // g + code}")
        want_share = figures.quantize(100 * plane_bits / p, 1)
        if stated != want_share:
            missed.append(f"R-15-181a states the tag plane's share as {stated}% of the "
                          f"payload, where {plane_bits} bits per {p} give {want_share}%")

    # The bands are read from the entry that states them. Each opens at the plane's
    # share with its code, so the low ends are arithmetic over R-15-181a's bits and
    # must exceed the bare plane; the sidecar's low end is the one figure in the
    # sentence that is a product of the others and so has an answer.
    accept = reg.accept_text.get("R-15-247a", "")
    band_mb, band_pct = BAND_MB_RE.search(accept), BAND_PCT_RE.search(accept)
    sidecar, tier = SIDECAR_RE.search(accept), TIER_RE.search(accept)
    if not (band_mb and band_pct and sidecar and tier):
        missed.append("R-15-247a no longer states the DECTED-inclusive bands in a form "
                      "this rule reads")
    else:
        if float(band_mb.group(1)) <= 1000 / g:
            missed.append(f"R-15-247a's DECTED band opens at {band_mb.group(1)} MB per "
                          f"GB, at or below the bare plane's {expected['mb-per-gb']}")
        if float(band_pct.group(1)) <= 100 / g:
            missed.append(f"R-15-247a's DECTED band opens at {band_pct.group(1)}% of the "
                          f"array, at or below the bare plane's {expected['plane-exact']}")
        if plane_bits is not None:
            # the bare plane's megabytes per gigabyte, scaled by the plane with its
            # code over the tag bits alone
            want_mb = round(1000 / g * plane_bits / (p // g))
            if int(band_mb.group(1)) != want_mb:
                missed.append(f"R-15-247a's DECTED band opens at {band_mb.group(1)} MB "
                              f"per GB, where R-15-181a's {plane_bits} bits over "
                              f"{p // g} tag bits give {want_mb}")
        # low band MB per GB over the whole tier, against the largest first class
        want = round(float(band_mb.group(1)) * int(tier.group(1))
                     / (float(sidecar.group(2)) * 1000) * 100)
        if int(sidecar.group(1)) != want:
            missed.append(f"R-15-247a says a sidecar consumes {sidecar.group(1)}% of the "
                          f"largest first class at the band's low end, the figures "
                          f"beside it give {want}%")

    ctx.shared["tag_plane"] = len(TAG_PLANE)
    rep.report("K-54", "tag-plane figure(s) disagreeing with the fields they derive from:",
               missed,
               f"all {len(TAG_PLANE)} tag-plane figures follow the {g}-bit granule "
               f"R-15-203 fixes and the {p}-bit payload R-15-181a fixes")
