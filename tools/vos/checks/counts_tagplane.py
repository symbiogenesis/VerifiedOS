# SPDX-License-Identifier: Apache-2.0
"""counts, the tag plane: the ratio one register field fixes, wherever it is stated.

A cardinality is not the only figure a document can restate, and this is the second
kind. The tag plane's cost is not a count of anything: it is one register field, the
granule width, read as a ratio, and four documents state that ratio in four spellings
between them. Nothing about it is anybody's measurement, so a granule that moves has
to move every one of them in the same edit, which is exactly what a claim is. The
band beside it is the other half and is not arithmetic at all, the DECTED code over
the plane being fixed at no width; that half is held by inequality against the bare
figure and never rewritten.
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

# The DECTED-inclusive bands beside the bare figures. These are judgment: the code over
# the plane is "about one check bit per codeword" and the register fixes no width for
# it, so the band is nobody's arithmetic and is never rewritten. What is machine-held is
# that it stands above the plane it includes, which is the one thing a band that had
# drifted off its own figure would stop doing.
BAND_MB_RE = re.compile(r"about (\d+)–(\d+) MB of SRAM per GB")
BAND_PCT_RE = re.compile(r"some ([\d.]+)–([\d.]+)% of the bulk array")
SIDECAR_RE = re.compile(r"consume (\d+)–\d+% of a \d+–(\d+) GB first class")
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

    # The bands are read from the entry that states them and compared by inequality
    # alone. A band that includes the plane's own code must exceed the bare plane; the
    # sidecar's low end is the one figure in the sentence that is a product of the
    # others and so has an answer.
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
        # low band MB per GB over the whole tier, against the largest first class
        want = round(float(band_mb.group(1)) * int(tier.group(1))
                     / (int(sidecar.group(2)) * 1000) * 100)
        if int(sidecar.group(1)) != want:
            missed.append(f"R-15-247a says a sidecar consumes {sidecar.group(1)}% of the "
                          f"largest first class at the band's low end, the figures "
                          f"beside it give {want}%")

    ctx.shared["tag_plane"] = len(TAG_PLANE)
    rep.report("K-54", "tag-plane figure(s) disagreeing with the fields they derive from:",
               missed,
               f"all {len(TAG_PLANE)} tag-plane figures follow the {g}-bit granule "
               f"R-15-203 fixes and the {p}-bit payload R-15-181a fixes")
