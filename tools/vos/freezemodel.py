# SPDX-License-Identifier: Apache-2.0
"""Exact rational arithmetic for R-15-036h's slot model, R-15-036j's packing term, and R-15-036p's outlining break-even.

Cross-checked against [tools/quickchick/FreezeModel.v](../quickchick/FreezeModel.v) by
`run.py quickchick freeze` and anchored against the four reference figures stated in
[docs/requirements-register.md](../../docs/requirements-register.md).
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Final

SLOT_MODEL = "R-15-036h"
PACKING_TERM = "R-15-036j"
COMMITMENT = "R-15-036i"
REGISTER = "docs/requirements-register.md"

MODULE = "tools/vos/freezemodel.py"
HARNESS = "tools/quickchick/FreezeModel.v"

CANONICAL_BITS: Final[int] = 32
OPTIMISTIC_SHARE_PCT: Final[int] = 70
PESSIMISTIC_SHARE_PCT: Final[int] = 75
OPTIMISTIC_SHARE: Final[float] = OPTIMISTIC_SHARE_PCT / 100
PESSIMISTIC_SHARE: Final[float] = PESSIMISTIC_SHARE_PCT / 100

# Two slots hold one 32-bit canonical instruction verbatim (`2w >= 32`) and index up to 2^16 entries.
SLOT_WIDTH: Final[int] = 16
DICTIONARY_INDEX_BOUND: Final[int] = 16
ESCAPE_PAIR_WIDTH: Final[int] = CANONICAL_BITS // 2

# Break-even hit rate against the optimistic bar (R-15-036j), in thousandths.
BREAK_EVEN_MILLI: Final[int] = 804
BREAK_EVEN: Final[float] = BREAK_EVEN_MILLI / 1000

# Reference instantiation `(w, h, k)` (R-15-036h).
REFERENCE: Final[tuple[int, int, int]] = (SLOT_WIDTH, 16, 7)


def optimistic_bar() -> float:
    """Acceptance bar in encoded bits per instruction (`float`)."""
    return float(exact_bar())


def pessimistic_bar() -> float:
    """Pessimistic reference bar in encoded bits per instruction (`float`)."""
    return float(Fraction(PESSIMISTIC_SHARE_PCT * CANONICAL_BITS, 100))


def exact_bar() -> Fraction:
    """Acceptance bar as an exact `Fraction` (`70% * 32 = 112/5 = 22.4`)."""
    return Fraction(OPTIMISTIC_SHARE_PCT * CANONICAL_BITS, 100)


def slot_width_constraints(w: int) -> tuple[bool, bool, bool]:
    """Evaluate `(2w >= 32, w <= 16, w >= 16)` for slot width `w`."""
    return (2 * w >= CANONICAL_BITS, w <= ESCAPE_PAIR_WIDTH,
            w >= DICTIONARY_INDEX_BOUND)


def slot_width_derivation() -> list[tuple[str, str, bool]]:
    """Return the three constraints deriving `w = SLOT_WIDTH` and their evaluation."""
    escape, waste, index = slot_width_constraints(SLOT_WIDTH)
    return [
        ("an escape is two slots holding one canonical instruction verbatim",
         f"2w = {2 * SLOT_WIDTH} bits against {CANONICAL_BITS} canonical bits", escape),
        ("a wider slot wastes escape bits and buys index space the profile has no use "
         "for",
         f"2(w - {ESCAPE_PAIR_WIDTH}) = {2 * (SLOT_WIDTH - ESCAPE_PAIR_WIDTH)} bits "
         "wasted per escape", waste),
        ("a slot must index the dictionary, which is bounded at 2^16 entries",
         f"w = {SLOT_WIDTH} against log2(N) at most {DICTIONARY_INDEX_BOUND}", index),
    ]


def per_slot_of(w: int, h: int, k: int) -> Fraction:
    """Effective bits per slot `w + h/k` (R-15-036h)."""
    return Fraction(bundle_of(w, h, k), k)


def bundle_of(w: int, h: int, k: int) -> int:
    """Bundle width `h + w * k` in bits."""
    return h + w * k


def bits(per_slot: Fraction, hit_rate: Fraction, packing: Fraction) -> Fraction:
    """Encoded bits per instruction `(w + h/k)(2 - p + L)` (R-15-036h, R-15-036j)."""
    return per_slot * (2 - hit_rate + packing)


def lambda_bound_of(hit_rate: Fraction, k: int) -> Fraction:
    """Worst-case packing loss bound `(2 - p) / (k - 1)` (R-15-036j)."""
    return (2 - hit_rate) / (k - 1)


def model_bits(per_slot: float, hit_rate: float, packing: float) -> float:
    """Floating-point wrapper around `bits`."""
    return float(bits(Fraction(per_slot), Fraction(hit_rate), Fraction(packing)))


@dataclass(frozen=True)
class Geometry:
    """Floating-point evaluation of an `(h, k, w)` bundle geometry candidate."""

    h: int
    k: int
    w: int
    bundle: int
    per_slot: float
    lambda_bound: float
    required_lambda: float
    min_p_at_bound: float
    min_p_unpacked: float
    legal: bool

    @property
    def clears_at_break_even(self) -> bool:
        return self.required_lambda >= self.lambda_bound

    @property
    def infeasible_at_break_even(self) -> bool:
        return self.required_lambda < 0.0


@dataclass(frozen=True)
class Exact:
    """Exact rational evaluation of an `(h, k, w)` bundle geometry candidate (`k >= 2`)."""

    w: int
    h: int
    k: int
    p: Fraction
    bundle: int
    per_slot: Fraction
    lambda_bound: Fraction
    required_lambda: Fraction
    min_p_at_bound: Fraction
    min_p_unpacked: Fraction
    legal: bool

    @property
    def clears(self) -> bool:
        return self.required_lambda >= self.lambda_bound

    @property
    def infeasible(self) -> bool:
        return self.required_lambda < 0


def score(h: int, k: int, w: int = SLOT_WIDTH,
          p: Fraction = Fraction(BREAK_EVEN_MILLI, 1000)) -> Exact:
    """Score candidate geometry `(h, k, w)` at hit rate `p` in exact rationals (`k >= 2`)."""
    if k < 2:
        raise ValueError(f"a bundle of {k} slot(s) has no packing term to bound, so "
                         "R-15-036j's arithmetic is not stated over it")
    per_slot = per_slot_of(w, h, k)
    bar = exact_bar()
    return Exact(
        w=w, h=h, k=k, p=p, bundle=bundle_of(w, h, k), per_slot=per_slot,
        lambda_bound=lambda_bound_of(p, k),
        required_lambda=bar / per_slot - (2 - p),
        min_p_at_bound=2 - bar * (k - 1) / (per_slot * k),
        min_p_unpacked=2 - bar / per_slot,
        legal=h >= k,
    )


def geometry(h: int, k: int, w: int = SLOT_WIDTH, p: float = BREAK_EVEN) -> Geometry:
    """Score candidate geometry `(h, k, w)` at hit rate `p` as floating-point values."""
    if k < 2:
        per_slot = w + h / k
        unpacked = 2.0 - optimistic_bar() / per_slot
        return Geometry(h=h, k=k, w=w, bundle=bundle_of(w, h, k), per_slot=per_slot,
                        lambda_bound=float("inf"),
                        required_lambda=optimistic_bar() / per_slot - (2.0 - p),
                        min_p_at_bound=unpacked, min_p_unpacked=unpacked, legal=h >= k)
    exact = score(h, k, w, Fraction(p))
    return Geometry(
        h=h, k=k, w=w, bundle=exact.bundle, per_slot=float(exact.per_slot),
        lambda_bound=float(exact.lambda_bound),
        required_lambda=float(exact.required_lambda),
        min_p_at_bound=float(exact.min_p_at_bound),
        min_p_unpacked=float(exact.min_p_unpacked), legal=exact.legal)


@dataclass(frozen=True)
class Outlining:
    """Break-even site counts for outlining a region of length `n` (R-15-036p)."""

    n: int
    break_even_absolute: int | None
    break_even_pcrelative: int | None


def outlining_break_even(lengths: Iterable[int]) -> list[Outlining]:
    """Compute break-even site counts for each region length `n` in `lengths`."""
    out: list[Outlining] = []
    for n in lengths:
        # nm > n + m + 1 <=> m(n - 1) > n + 1, and nm > n + 2m + 1 <=> m(n - 2) > n + 1
        absolute = (n + 1) // (n - 1) + 1 if n > 1 else None
        pcrelative = (n + 1) // (n - 2) + 1 if n > 2 else None
        out.append(Outlining(n=n, break_even_absolute=absolute,
                             break_even_pcrelative=pcrelative))
    return out


P_SCALE: Final[int] = 1_000              # hit rate in thousandths
BITS_SCALE: Final[int] = 100             # bits per instruction in hundredths
RATE_SCALE: Final[int] = 10_000          # probability or packing term in ten-thousandths
COEFF_SCALE: Final[int] = 10             # linear-form coefficients in tenths

SLOT_WIDTHS: Final[tuple[int, ...]] = (8, 12, 16, 17, 20, 32)
HEADERS: Final[tuple[int, ...]] = (8, 16, 32)
SLOT_COUNTS: Final[tuple[int, ...]] = (2, 3, 4, 7, 8, 15, 16)
HIT_RATES: Final[tuple[int, ...]] = (0, 500, 728, 775, 800, BREAK_EVEN_MILLI, 850, 900,
                                     950, 1000)
GEOMETRY_RATES: Final[tuple[int, ...]] = (0, BREAK_EVEN_MILLI, 950)
REGION_LENGTHS: Final[tuple[int, ...]] = (1, 2, 3, 4, 5, 6, 7, 8)

FAMILIES: Final[tuple[str, ...]] = ("bar", "swd", "lin", "ref", "geo", "obe")

PREFIX: Final[str] = "fm"


def scaled(value: Fraction, scale: int) -> int:
    """Return `floor(value * scale + 1/2)` (matching `Z.div (2 * num * scale + den) (2 * den)`)."""
    num, den = (value * scale).as_integer_ratio()
    return (2 * num + den) // (2 * den)


def _bit(value: bool) -> str:
    return "1" if value else "0"


def _opt(value: int | None) -> str:
    return "n" if value is None else str(value)


def vector_lines() -> list[str]:
    """Render all freeze-model comparison vectors in harness output order."""
    out: list[str] = [
        f"{PREFIX} bar -> {CANONICAL_BITS} {OPTIMISTIC_SHARE_PCT} "
        f"{PESSIMISTIC_SHARE_PCT} {scaled(exact_bar(), BITS_SCALE)} "
        f"{scaled(Fraction(PESSIMISTIC_SHARE_PCT * CANONICAL_BITS, 100), BITS_SCALE)}"]

    for w in SLOT_WIDTHS:
        escape, waste, index = slot_width_constraints(w)
        out.append(f"{PREFIX} swd {w} -> {_bit(escape)} {_bit(waste)} {_bit(index)} "
                   f"{_bit(escape and waste and index)}")

    for h in HEADERS:
        for k in SLOT_COUNTS:
            per_slot = per_slot_of(SLOT_WIDTH, h, k)
            out.append(
                f"{PREFIX} lin {SLOT_WIDTH} {h} {k} -> "
                f"{scaled(2 * per_slot, COEFF_SCALE)} "
                f"{scaled(per_slot, COEFF_SCALE)} {bundle_of(SLOT_WIDTH, h, k)} "
                f"{scaled(per_slot, BITS_SCALE)}")

    w, h, k = REFERENCE
    per_slot = per_slot_of(w, h, k)
    for milli in HIT_RATES:
        p = Fraction(milli, P_SCALE)
        num, den = 2 * P_SCALE - milli, P_SCALE * (k - 1)
        bound = Fraction(num, den)
        out.append(
            f"{PREFIX} ref {milli} -> "
            f"{scaled(bits(per_slot, p, Fraction(0)), BITS_SCALE)} {num} {den} "
            f"{scaled(bound, RATE_SCALE)} "
            f"{scaled(bits(per_slot, p, bound), BITS_SCALE)}")

    for h in HEADERS:
        for k in SLOT_COUNTS:
            for milli in GEOMETRY_RATES:
                g = score(h, k, SLOT_WIDTH, Fraction(milli, P_SCALE))
                out.append(
                    f"{PREFIX} geo {SLOT_WIDTH} {h} {k} {milli} -> {g.bundle} "
                    f"{_bit(g.legal)} {scaled(g.per_slot, BITS_SCALE)} "
                    f"{scaled(g.lambda_bound, RATE_SCALE)} "
                    f"{scaled(g.required_lambda, RATE_SCALE)} "
                    f"{scaled(g.min_p_at_bound, RATE_SCALE)} "
                    f"{scaled(g.min_p_unpacked, RATE_SCALE)} "
                    f"{_bit(g.clears)} {_bit(g.infeasible)} "
                    f"{scaled(bits(g.per_slot, g.p, Fraction(0)), BITS_SCALE)}")

    out += [f"{PREFIX} obe {row.n} -> {_opt(row.break_even_absolute)} "
            f"{_opt(row.break_even_pcrelative)}"
            for row in outlining_break_even(list(REGION_LENGTHS))]
    return out


_LINEAR_RE = re.compile(
    r"at the reference instantiation(?: \([^)]*\))? is ([\d.]+) [-−] ([\d.]+)\*p\*")
_ENDPOINT_RE = re.compile(
    r"reaches (\d+)/(\d+) at \*p\* = 0, where [^.]*?for ([\d.]+) bits per instruction "
    r"against the bare model's ([\d.]+)")


@dataclass(frozen=True)
class Anchors:
    """Reference-instantiation figures extracted from R-15-036h and R-15-036j in the register."""

    intercept: Fraction
    slope: Fraction
    bound_num: int
    bound_den: int
    packed: Fraction
    bare: Fraction


def anchors(root: Path) -> tuple[Anchors | None, list[str]]:
    """Extract the four reference-instantiation `Anchors` from `docs/requirements-register.md`."""
    path = root / REGISTER
    if not path.is_file():
        return None, [f"{REGISTER} is not in this checkout, so the four figures "
                      f"{SLOT_MODEL} and {PACKING_TERM} state are read from nothing"]
    raw = path.read_text(encoding="utf-8")
    linear, endpoint = _LINEAR_RE.search(raw), _ENDPOINT_RE.search(raw)
    said: list[str] = []
    if linear is None:
        said.append(f"{REGISTER} no longer states {SLOT_MODEL}'s linear form in a shape "
                    "this reader knows, so its intercept and slope decide nothing here")
    if endpoint is None:
        said.append(f"{REGISTER} no longer states {PACKING_TERM}'s endpoint at p = 0 in "
                    "a shape this reader knows, so the bound and the two bits figures "
                    "decide nothing here")
    if linear is None or endpoint is None:
        return None, said
    return Anchors(intercept=Fraction(linear.group(1)), slope=Fraction(linear.group(2)),
                   bound_num=int(endpoint.group(1)), bound_den=int(endpoint.group(2)),
                   packed=Fraction(endpoint.group(3)),
                   bare=Fraction(endpoint.group(4))), said


def held(lines: list[str], fixed: Anchors, whose: str) -> list[str]:
    """Check one side's vector `lines` against the register's `fixed` reference `Anchors`."""
    found = {line.split(" -> ")[0]: line.split(" -> ")[1].split()
             for line in lines if " -> " in line}
    w, h, k = REFERENCE
    findings: list[str] = []
    linear = found.get(f"{PREFIX} lin {w} {h} {k}")
    reference = found.get(f"{PREFIX} ref 0")
    if (linear is None or reference is None
            or len(linear) < 2 or len(reference) < 5):
        return [f"{whose} states no complete line at the reference instantiation "
                f"(w = {w}, h = {h}, k = {k}), so none of the four figures "
                f"{SLOT_MODEL} and {PACKING_TERM} quote is decided"]
    for what, got, want, scale in (
            ("the intercept of the linear form", linear[0], fixed.intercept,
             COEFF_SCALE),
            ("the slope of the linear form", linear[1], fixed.slope, COEFF_SCALE),
            ("the bare model at p = 0", reference[0], fixed.bare, BITS_SCALE),
            ("the packed model at p = 0", reference[4], fixed.packed, BITS_SCALE)):
        at = want * scale
        if at.denominator != 1:
            findings.append(f"{REGISTER} states {what} as {want}, which is finer than "
                            f"the 1/{scale} this comparison is stated at")
        elif got != str(int(at)):
            findings.append(f"{whose} makes {what} {got} and {REGISTER} states "
                            f"{int(at)}, both at 1/{scale} of a bit")
    num, den = int(reference[1]), int(reference[2])
    if num * fixed.bound_den != den * fixed.bound_num:
        findings.append(
            f"{whose} makes the packing bound at p = 0 and k = {k} {num}/{den} and "
            f"{REGISTER} states {fixed.bound_num}/{fixed.bound_den}")
    return findings


def family_counts(lines: list[str]) -> dict[str, int]:
    """Count vectors per declared family (`FAMILIES`) in `lines`."""
    counts = dict.fromkeys(FAMILIES, 0)
    for line in lines:
        field = line.split()
        if len(field) > 1 and field[0] == PREFIX and field[1] in counts:
            counts[field[1]] += 1
    return counts


def empty_families(lines: list[str], whose: str) -> list[str]:
    """Report any family in `FAMILIES` with zero vectors in `lines`."""
    return [f"{whose} states no vector in the `{name}` family, so this comparison "
            f"decides nothing about it" for name, count in family_counts(lines).items()
            if count == 0]


def compare(theirs: list[str], ours: list[str]) -> list[str]:
    """Compare prover vector lines `theirs` against model vector lines `ours` by point key."""
    def index(lines: list[str]) -> dict[str, str]:
        return {line.split(" -> ")[0]: line.split(" -> ")[1]
                for line in lines if line.startswith(f"{PREFIX} ") and " -> " in line}

    prover, model = index(theirs), index(ours)
    if not prover:
        return [f"the harness states no vector at all, having printed {len(theirs)} "
                f"line(s) none of which is a `{PREFIX} ` point"]
    findings = [f"the harness answers `{key} -> {prover[key]}` and this model answers "
                f"`{ours_at}`" for key, ours_at in model.items()
                if key in prover and prover[key] != ours_at]
    findings += [f"the harness states `{key}` and this model states no such point"
                 for key in prover if key not in model]
    findings += [f"this model states `{key}` and the harness states no such point"
                 for key in model if key not in prover]
    return findings
