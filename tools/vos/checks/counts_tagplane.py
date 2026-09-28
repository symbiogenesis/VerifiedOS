# SPDX-License-Identifier: Apache-2.0
"""counts, the tag plane: the ratio one register field fixes, wherever it is stated.

A cardinality is not the only figure a document can restate, and this is the second
kind. The tag plane's cost is not a count of anything: it is one register field, the
granule width, read as a ratio. Deliberately retained numerical statements are checked
against their owner and repaired from it; background and performance discussions link
to the canonical calculation. Nothing about the ratio is a measurement.

The code over the plane is the other half. R-15-181a states the DECTED code's width as
an authored decision, and coding theory bounds that decision below: correcting two
errors while detecting three needs minimum distance 6, and no code of that distance
over so few tag bits is shorter than the floor tabled here. Everything built on the
width is arithmetic again, the codeword's metadata totals, the plane's share of it,
the ladder the width is chosen from and the megabytes a gigabyte of data then carries,
so the width is held at or above its floor and every figure built on it against the
entry's own bit counts. Those findings are reported and never rewritten: each sits in a
sentence whose other figures may be the ones that moved, and a width above the floor
is a judgment no repair may make.
"""

import re
from dataclasses import dataclass
from itertools import pairwise
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
]

# The minimum distance double-error correction with triple-error detection needs: two
# corrected and three detected errors must never meet, so d >= 2 + 3 + 1.
DISTANCE = 6

# The fewest check bits a binary code of minimum distance 6 admits over k information
# bits, at each tag count a codeword on the ladder carries. A stated width is held
# against the any-code row, a code being free to be nonlinear; the ladder is priced at
# the linear row, which is what R-15-181a says it prices. Each entry is an explicit code
# reaching it and a bound refusing one check bit fewer, and
# tests/test_dected_floor.py derives both without reading this table. A tag count the
# table does not carry is a finding, never a guess.
DECTED_FLOOR_ANY: dict[int, int] = {
    1: 5,   # [6,1,6], the repetition code; no two words of length 5 lie 6 apart
    2: 7,   # [9,2,6]; Plotkin, A(8,6) <= 2 < 4
    4: 8,   # [12,4,6]; Plotkin, A(11,6) <= 12 < 16
    8: 8,   # Nordstrom-Robinson (16,256,6); A(15,6) = A(14,5) <= 2^14 // 106 = 154 < 256
}
DECTED_FLOOR_LINEAR: dict[int, int] = {
    **DECTED_FLOOR_ANY,
    # [17,8,6]; a linear [16,8,d] code with d >= 6 has a residual code [16-d,7,ceil(d/2)],
    # [10,7,3] at d = 6, and the Hamming bound refuses it at every d the Singleton bound
    # leaves (2^7 * 11 > 2^10 at d = 6)
    8: 9,
}

# The normative codeword, read from the entry that fixes the code over the plane: the
# SECDED check bits over the data, the DECTED check bits over the tags, the bit count it
# gives the plane with that code and the plane's share of the payload, and the total
# metadata beside them. The width is a judgment above the floor; the rest is its sum.
SECDED_RE = re.compile(r"data payload is \d+ bits with (\d+) SECDED check bits")
SHARE_RE = re.compile(r"DECTED code of (?:about )?(\d+) (?:check )?bits.*?tag plane with its "
                      r"own code is (\d+), some ([\d.]+)% of the payload")
# where the entry calls its width the fewest a code admits, that is a claim of equality
# with the floor, and it is held as one; an entry saying "fewest" in a form this does not
# read is a finding, so a reworded claim cannot step out from under the hold
FEWEST_RE = re.compile(r"the fewest any code of minimum distance (\d+) over (\d+) "
                       r"(?:tag )?bits admits")
TOTAL_RE = re.compile(r"total metadata of some (\d+) bits per (\d+) data bits \(([\d.]+)%\)")
# the fallback codeword states its totals and its plane, and so implies its code's width
FALLBACK_RE = re.compile(r"(\d+) bits \((\d+) per \1, ([\d.]+)%, the tag plane with its code "
                         r"(\d+) of them at ([\d.]+)%\) is the fallback")

# The ladder the width is chosen from: the DECTED code's check bits at each tag count,
# and what the codeword's metadata then costs at each payload. A series is read in
# either spelling, "5, 7, 8, 9" in an entry's line and "5, 7, 8, and 9" in running prose.
_SERIES = r"\d+(?:, (?:and )?\d+)+"
LIST_RE = re.compile(rf"\(({_SERIES}) check bits at ({_SERIES}) tag bits, the fewest a "
                     r"linear code of minimum distance (\d+) admits")
LADDER_RE = re.compile(r"full ladder is ([\d.]+(?: / [\d.]+)+)% where the data code alone "
                       r"reads ([\d.]+(?: / [\d.]+)+)%")
DECLINED_RE = re.compile(r"(\d+) is declined as the smallest ladder step")
SPEC_DATA_RE = re.compile(rf"SECDED alone falls ([\d.]+(?: → [\d.]+)+)% across payloads of "
                          rf"({_SERIES}) data bits")
SPEC_TOTAL_RE = re.compile(r"total metadata per byte of data falls "
                           r"\*\*([\d.]+(?: → [\d.]+)+)%\*\*")
# the second figure closes its sentence, so a decimal is read as one and not as [\d.]+
SPEC_STEP_RE = re.compile(r"the step from (\d+) to (\d+) is worth (\d+(?:\.\d+)?) points where "
                          r"the data code alone showed (\d+(?:\.\d+)?)")
SPEC_LAST_RE = re.compile(r"(\d+) is not taken, its further ([\d.]+) points being the "
                          r"smallest step on the ladder")
SPEC_PLANE_RE = re.compile(r"tag plane with its own code is (\d+) of the (\d+) at (\d+) and "
                           r"(\d+) of the (\d+) at (\d+)")

# The DECTED-inclusive bands beside the bare figures, in R-15-247a and in the
# specification's copy of it. Both ends of each are machine-held: the megabyte band
# opens at the normative codeword's plane, above the bare plane it includes, and closes
# at the fallback's, and the sidecar band is the product of those ends, the tier and the
# first class, its low end against the largest first class and its high end against
# the smallest. The percentage band is the plane's share at the two codewords,
# which K-69 holds against R-15-181a; this rule holds only that it opens above the bare
# plane.
BAND_MB_RE = re.compile(r"about (\d+)–(\d+) MB of SRAM per GB")
BAND_PCT_RE = re.compile(r"some ([\d.]+)–([\d.]+)% of the bulk array")
SIDECAR_RE = re.compile(r"consume (\d+)–(\d+)% of a ([\d.]+)–([\d.]+) GB first class")
TIER_RE = re.compile(r"a (\d+) GB bulk tier")


@dataclass(frozen=True)
class Codeword:
    """One codeword width R-15-181a prices: its payload, the tag bits it carries, and
    the bits the entry gives the plane with its code and the metadata in total."""

    payload: int
    tags: int
    plane: int
    total: int | None


@dataclass(frozen=True)
class Rung:
    """One payload on the ladder, its metadata as exact percentages of the payload: all
    of it at the linear floor, and the data code alone."""

    width: int
    total: float
    data: float


def secded_bits(k: int) -> int:
    """Extended Hamming's check bits over `k` data bits: the smallest r with
    2^r >= k + r + 1, plus the overall parity bit."""
    r = 1
    while 2 ** r < k + r + 1:
        r += 1
    return r + 1


def _pct(bits: int, payload: int) -> str:
    return figures.quantize(100 * bits / payload, 1)


def _whole(v: float) -> int:
    """A derived figure stated as a whole number, rounded the way `quantize` rounds."""
    return int(figures.quantize(v, 0).replace(",", ""))


def _series(text: str) -> list[int]:
    return [int(v) for v in re.findall(r"\d+", text)]


def _only(pattern: re.Pattern[str], raw: str, what: str,
          missed: list[str]) -> re.Match[str] | None:
    """The one sentence of the specification a pattern reads, or a finding: a sentence
    reworded away and a sentence stated twice are both readings this rule cannot make."""
    hits = list(pattern.finditer(raw))
    if len(hits) != 1:
        missed.append(f"{SPEC} states {what} in {len(hits)} places this rule reads, "
                      "where it reads exactly one")
        return None
    return hits[0]


def _floor(tags: int, what: str, g: int, missed: list[str]) -> int | None:
    floor = DECTED_FLOOR_ANY.get(tags)
    if floor is None:
        missed.append(f"{what} carries {tags} tag bits at the {g}-bit granule, a count the "
                      f"distance-{DISTANCE} floor table does not cover; table it with the "
                      "code reaching it and the bound behind it")
    return floor


def _normative(body: str, g: int, p: int, missed: list[str]) -> Codeword | None:
    """The normative codeword: a code at or above its floor, and totals that are sums."""
    tags = p // g
    floor = _floor(tags, f"R-15-181a's {p}-bit payload", g, missed)
    share = SHARE_RE.search(body)
    if not share:
        missed.append("R-15-181a no longer states the tag plane's share of the codeword "
                      "in a form this rule reads")
        return None
    code, plane, stated = int(share.group(1)), int(share.group(2)), share.group(3)
    if floor is not None and code < floor:
        missed.append(f"R-15-181a puts a DECTED code of {code} check bits over {tags} tag "
                      f"bits, below the {floor} any code of minimum distance {DISTANCE} "
                      f"over {tags} bits needs")
    fewest = FEWEST_RE.search(body)
    if not fewest and re.search(r"\bfewest\b", body):
        missed.append("R-15-181a calls its DECTED width the fewest in a form this rule does "
                      "not read")
    if fewest and floor is not None and (int(fewest.group(1)), int(fewest.group(2)),
                                         code) != (DISTANCE, tags, floor):
        missed.append(f"R-15-181a calls its {code} check bits the fewest any code of "
                      f"minimum distance {fewest.group(1)} over {fewest.group(2)} bits "
                      f"admits, where {tags} tag bits at distance {DISTANCE} need {floor}")
    if plane != tags + code:
        missed.append(f"R-15-181a puts the tag plane with its code at {plane} bits, where "
                      f"its {tags} tag bits under {code} check bits give {tags + code}")
    if stated != _pct(plane, p):
        missed.append(f"R-15-181a states the tag plane's share as {stated}% of the payload, "
                      f"where {plane} bits per {p} give {_pct(plane, p)}%")

    secded, total = SECDED_RE.search(body), TOTAL_RE.search(body)
    if not (secded and total):
        missed.append("R-15-181a no longer states its SECDED check bits and total metadata "
                      "in a form this rule reads")
        return Codeword(p, tags, plane, None)
    s, bits, per, pct = (int(secded.group(1)), int(total.group(1)), int(total.group(2)),
                         total.group(3))
    if s != secded_bits(p):
        missed.append(f"R-15-181a puts {s} SECDED check bits over its {p}-bit payload, "
                      f"where extended Hamming needs {secded_bits(p)}")
    if per != p:
        missed.append(f"R-15-181a states its total metadata per {per} data bits, where its "
                      f"payload is {p}")
    if bits != s + tags + code:
        missed.append(f"R-15-181a puts the codeword's metadata at {bits} bits, where {s} "
                      f"SECDED, {tags} tag and {code} DECTED bits give {s + tags + code}")
    if pct != _pct(bits, p):
        missed.append(f"R-15-181a states its total metadata as {pct}%, where {bits} bits "
                      f"per {p} give {_pct(bits, p)}%")
    return Codeword(p, tags, plane, bits)


def _fallback(body: str, g: int, missed: list[str]) -> Codeword | None:
    """The fallback codeword, whose code's width is implied rather than stated: the
    plane with its code less the tag bits under it, held at the same floor."""
    m = FALLBACK_RE.search(body)
    if not m:
        missed.append("R-15-181a no longer states its fallback codeword in a form this "
                      "rule reads")
        return None
    fp, bits, pct = int(m.group(1)), int(m.group(2)), m.group(3)
    plane, share = int(m.group(4)), m.group(5)
    tags = fp // g
    floor = _floor(tags, f"R-15-181a's {fp}-bit fallback", g, missed)
    if floor is not None and plane - tags < floor:
        missed.append(f"R-15-181a's {fp}-bit fallback gives the tag plane with its code "
                      f"{plane} bits, leaving {plane - tags} check bits over {tags} tag "
                      f"bits, below the {floor} any code of minimum distance {DISTANCE} "
                      f"over {tags} bits needs")
    want = secded_bits(fp) + plane
    if bits != want:
        missed.append(f"R-15-181a puts the {fp}-bit fallback's metadata at {bits} bits, "
                      f"where {secded_bits(fp)} SECDED check bits and the plane's {plane} "
                      f"give {want}")
    if pct != _pct(bits, fp):
        missed.append(f"R-15-181a states the fallback's total metadata as {pct}%, where "
                      f"{bits} bits per {fp} give {_pct(bits, fp)}%")
    if share != _pct(plane, fp):
        missed.append(f"R-15-181a states the fallback plane's share as {share}%, where "
                      f"{plane} bits per {fp} give {_pct(plane, fp)}%")
    return Codeword(fp, tags, plane, bits)


def _check_bits(m: re.Match[str] | None, where: str, missed: list[str]) -> list[int] | None:
    """A per-rung list of the DECTED code's check bits, against the linear floor at each
    tag count it names; the tag counts are what the ladder beside it is priced at."""
    if not m:
        missed.append(f"{where} no longer states the DECTED code's check bits per tag count "
                      "in a form this rule reads")
        return None
    bits, tags, distance = _series(m.group(1)), _series(m.group(2)), int(m.group(3))
    if len(bits) != len(tags):
        missed.append(f"{where} lists {len(bits)} check-bit counts against {len(tags)} tag "
                      "counts")
        return None
    if distance != DISTANCE:
        missed.append(f"{where} prices the tag code at minimum distance {distance}, where "
                      f"double-error correction with triple-error detection needs {DISTANCE}")
    for t, b in zip(tags, bits, strict=True):
        want = DECTED_FLOOR_LINEAR.get(t)
        if want is None:
            missed.append(f"{where} names {t} tag bits, a count the distance-{DISTANCE} "
                          "floor table does not cover")
        elif b != want:
            missed.append(f"{where} states {b} check bits at {t} tag bits, where the fewest "
                          f"a linear code of minimum distance {DISTANCE} admits is {want}")
    return tags


def _rungs(widths: list[int], g: int, where: str, missed: list[str]) -> list[Rung] | None:
    """The ladder at the payloads a site names: extended-Hamming SECDED over the data,
    one tag bit per granule, and the linear floor over the tags."""
    rungs = []
    for w in widths:
        tags = w // g
        code = DECTED_FLOOR_LINEAR.get(tags)
        if w % g or code is None:
            missed.append(f"{where} prices a {w}-bit payload, whose tag count at the {g}-bit "
                          f"granule the distance-{DISTANCE} floor table does not cover")
            return None
        s = secded_bits(w)
        rungs.append(Rung(w, 100 * (s + tags + code) / w, 100 * s / w))
    return rungs


def _hold_series(where: str, what: str, stated: list[str], exact: list[float],
                 missed: list[str]) -> None:
    want = [figures.quantize(v, 1) for v in exact]
    if len(stated) != len(want) or not all(
            figures.same_figure(a, b) for a, b in zip(stated, want, strict=True)):
        missed.append(f"{where} states {what} as {' / '.join(stated)}%, where the rungs "
                      f"give {' / '.join(want)}%")


def _smallest_step(rungs: list[Rung], width: int, where: str,
                   missed: list[str]) -> float | None:
    """The step onto `width`, which the site declines as the ladder's smallest."""
    at = [r.width for r in rungs]
    if width not in at[1:]:
        missed.append(f"{where} declines a {width}-bit rung its ladder does not step onto")
        return None
    steps = [a.total - b.total for a, b in pairwise(rungs)]
    step = steps[at.index(width) - 1]
    if step > min(steps):
        missed.append(f"{where} declines {width} as the smallest step, where its "
                      f"{figures.quantize(step, 1)} points exceed the ladder's smallest, "
                      f"{figures.quantize(min(steps), 1)}")
    return step


def _register_ladder(accept: str, g: int, missed: list[str]) -> None:
    listed = _check_bits(LIST_RE.search(accept), "R-15-181a", missed)
    ladder = LADDER_RE.search(accept)
    if not ladder:
        missed.append("R-15-181a no longer states the metadata ladder in a form this rule "
                      "reads")
    if listed is None or not ladder:
        return
    rungs = _rungs([t * g for t in listed], g, "R-15-181a", missed)
    if rungs is None:
        return
    _hold_series("R-15-181a", "the full ladder", ladder.group(1).split(" / "),
                 [r.total for r in rungs], missed)
    _hold_series("R-15-181a", "the data code's ladder", ladder.group(2).split(" / "),
                 [r.data for r in rungs], missed)
    declined = DECLINED_RE.search(accept)
    if not declined:
        missed.append("R-15-181a no longer names the rung it declines in a form this rule "
                      "reads")
    else:
        _smallest_step(rungs, int(declined.group(1)), "R-15-181a", missed)


def _spec_ladder(raw: str, g: int, missed: list[str]) -> None:
    listed_m = _only(LIST_RE, raw, "the DECTED code's check bits per tag count", missed)
    listed = _check_bits(listed_m, SPEC, missed) if listed_m else None
    data = _only(SPEC_DATA_RE, raw, "the data code's ladder", missed)
    total = _only(SPEC_TOTAL_RE, raw, "the full ladder", missed)
    step = _only(SPEC_STEP_RE, raw, "the step the width buys", missed)
    last = _only(SPEC_LAST_RE, raw, "the rung it declines", missed)
    if data is None:
        return
    widths = _series(data.group(2))
    if listed is not None and [t * g for t in listed] != widths:
        missed.append(f"{SPEC} names tag counts {listed} beside payloads {widths}, where the "
                      f"{g}-bit granule gives {[w // g for w in widths]}")
    rungs = _rungs(widths, g, SPEC, missed)
    if rungs is None:
        return
    _hold_series(SPEC, "the data code's ladder", data.group(1).split(" → "),
                 [r.data for r in rungs], missed)
    if total:
        _hold_series(SPEC, "the full ladder", total.group(1).split(" → "),
                     [r.total for r in rungs], missed)
    by = {r.width: r for r in rungs}
    if step:
        a, b = by.get(int(step.group(1))), by.get(int(step.group(2)))
        if a is None or b is None:
            missed.append(f"{SPEC} prices a step from {step.group(1)} to {step.group(2)} "
                          "its ladder does not carry")
        else:
            for name, found, want in (
                    ("the full ladder's", step.group(3), a.total - b.total),
                    ("the data code's", step.group(4), a.data - b.data)):
                if not figures.same_figure(found, figures.quantize(want, 1)):
                    missed.append(f"{SPEC} puts {name} step from {a.width} to {b.width} "
                                  f"at {found} points, where the rungs give "
                                  f"{figures.quantize(want, 1)}")
    if last:
        declined = _smallest_step(rungs, int(last.group(1)), SPEC, missed)
        if declined is not None and not figures.same_figure(
                last.group(2), figures.quantize(declined, 1)):
            missed.append(f"{SPEC} puts the step onto {last.group(1)} at {last.group(2)} "
                          f"points, where the rungs give {figures.quantize(declined, 1)}")


def _spec_plane(raw: str, normative: Codeword | None, fallback: Codeword | None,
                missed: list[str]) -> None:
    """The specification's restatement of R-15-181a's plane among its metadata. A
    codeword the entry could not be read for is already a finding, so a width is blamed
    on the entry only when both codewords were read and neither is it."""
    m = _only(SPEC_PLANE_RE, raw, "the tag plane's bits among the codeword's metadata",
              missed)
    if not m:
        return
    by = {c.payload: c for c in (normative, fallback) if c is not None}
    for plane, total, width in (m.group(1, 2, 3), m.group(4, 5, 6)):
        c = by.get(int(width))
        if c is None and (normative is None or fallback is None):
            continue
        if c is None:
            missed.append(f"{SPEC} prices the tag plane at a {width}-bit codeword R-15-181a "
                          "does not state")
        elif int(plane) != c.plane or (c.total is not None and int(total) != c.total):
            missed.append(f"{SPEC} gives the tag plane with its code {plane} of the {total} "
                          f"metadata bits at {width}, where R-15-181a gives {c.plane} of "
                          f"{c.total}")


def _bands(text: str, where: str, g: int, normative: Codeword | None,
           fallback: Codeword | None, missed: list[str]) -> tuple[str, ...] | None:
    """R-15-247a's DECTED-inclusive bands, wherever a copy of them is stated, and the
    figures read, so that a copy can be held against the entry as well."""
    band_mb, band_pct = BAND_MB_RE.search(text), BAND_PCT_RE.search(text)
    sidecar, tier = SIDECAR_RE.search(text), TIER_RE.search(text)
    if not (band_mb and band_pct and sidecar and tier):
        missed.append(f"{where} no longer states the DECTED-inclusive bands in a form this "
                      "rule reads")
        return None
    lo_mb, hi_mb = int(band_mb.group(1)), int(band_mb.group(2))
    if lo_mb <= 1000 / g:
        missed.append(f"{where}'s DECTED band opens at {lo_mb} MB per GB, at or below the "
                      f"bare plane's {figures.quantize(1000 / g, 1)}")
    if float(band_pct.group(1)) <= 100 / g:
        missed.append(f"{where}'s DECTED band opens at {band_pct.group(1)}% of the array, "
                      f"at or below the bare plane's {figures.quantize(100 / g, 4)}")
    # the bare plane's megabytes per gigabyte, scaled by the plane with its code over
    # the tag bits alone, at the normative codeword and at the fallback
    for end, stated, c in (("opens", lo_mb, normative), ("closes", hi_mb, fallback)):
        if c is None:
            continue
        want = _whole(1000 / g * c.plane / c.tags)
        if stated != want:
            missed.append(f"{where}'s DECTED band {end} at {stated} MB per GB, where "
                          f"R-15-181a's {c.plane} bits over {c.tags} tag bits at "
                          f"{c.payload} give {want}")
    # each end's megabytes per gigabyte over the whole tier: the low end against the
    # largest first class and the high end against the smallest
    gb = int(tier.group(1))
    for end, stated, mb, first in (
            ("low", int(sidecar.group(1)), lo_mb, sidecar.group(4)),
            ("high", int(sidecar.group(2)), hi_mb, sidecar.group(3))):
        want = _whole(mb * gb / (float(first) * 1000) * 100)
        if stated != want:
            missed.append(f"{where} says a sidecar consumes {stated}% of a {first} GB first "
                          f"class at the band's {end} end, where {mb} MB per GB over a "
                          f"{gb} GB tier give {want}%")
    return tuple(str(v) for v in (*band_mb.group(1, 2), *sidecar.group(1, 2, 3, 4),
                                  tier.group(1)))


def _band_text(held: tuple[str, ...]) -> str:
    mb_lo, mb_hi, s_lo, s_hi, c_lo, c_hi, gb = held
    return (f"{mb_lo}–{mb_hi} MB per GB and a {gb} GB tier's {s_lo}–{s_hi}% of a "
            f"{c_lo}–{c_hi} GB first class")


def tag_plane(ctx: Context) -> None:
    """K-54: every stated tag-plane figure, against the fields and the floor it rests on.

    The granule is one bit of validity per so many bits of data, so the plane is
    `100/granule` percent of the array it covers and `1000/granule` megabytes per
    gigabyte of it, and the ECC codeword carries `payload/granule` tag bits. Source
    parameters and the code-inclusive figures stay checked independently of which
    narrative documents repeat the arithmetic. The code's width is held at or above
    the distance-6 floor for its tag count, at the normative codeword and at the
    fallback, and every total, share, ladder rung, step and band built on it is held
    against the bit counts beside it; those are reported, never rewritten.

    A reading that has moved is the one finding this rule cannot repair: with no
    granule there is no arithmetic to compare against, so it reports and stops rather
    than passing over an empty claim table, which is the vacuity the floors group
    exists to refuse and would not see here, the table being a literal. Each sentence
    the code-inclusive holds read is one sentence, so a reading that fails is itself a
    finding rather than a count the floors group would need.
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
        "mb-per-gb": figures.quantize(1000 / g, 1),
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

    # The two codewords R-15-181a prices, each held at the floor and at its own sums,
    # and the ladder its acceptance criterion chooses the width from.
    body = reg.body.get("R-15-181a", "")
    normative = _normative(body, g, p, missed)
    fallback = _fallback(body, g, missed)
    _register_ladder(reg.accept_text.get("R-15-181a", ""), g, missed)

    # The bands are read from the entry that states them and from the specification's
    # copy, each held against the two codewords, and the copy against the entry.
    held = _bands(reg.accept_text.get("R-15-247a", ""), "R-15-247a", g, normative,
                  fallback, missed)
    # a specification the corpus lacks is already a finding of every claim above
    if SPEC in ctx.corpus:
        raw = ctx.text(SPEC)
        _spec_ladder(raw, g, missed)
        _spec_plane(raw, normative, fallback, missed)
        m = _only(BAND_MB_RE, raw, "the DECTED-inclusive megabyte band", missed)
        if m:
            start, end = raw.rfind("\n", 0, m.start()) + 1, raw.find("\n", m.end())
            copy = _bands(raw[start:end if end >= 0 else len(raw)], SPEC, g, normative,
                          fallback, missed)
            if held and copy and copy != held:
                missed.append(f"{SPEC} restates R-15-247a's bands as {_band_text(copy)}, "
                              f"where the entry states {_band_text(held)}")

    ctx.shared["tag_plane"] = len(TAG_PLANE)
    rep.report("K-54", "tag-plane figure(s) disagreeing with the fields they derive from:",
               missed,
               f"all {len(TAG_PLANE)} tag-plane figures follow the {g}-bit granule "
               f"R-15-203 fixes and the {p}-bit payload R-15-181a fixes, and the DECTED "
               f"code over the plane clears the distance-{DISTANCE} floor beneath every "
               "figure built on it")
