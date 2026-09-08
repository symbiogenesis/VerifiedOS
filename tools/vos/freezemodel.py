# SPDX-License-Identifier: Apache-2.0
"""R-15-036h's slot model, R-15-036j's packing term, and the arithmetic over both.

The dictionary is a **permanent freeze-time commitment** (R-15-036i): every stored
executable object is in that encoding, so a wrong answer here is not a recompile, it is
stored code invalidated wholesale. That is the one place in this tree where a tool's
output cannot be repaired downstream, which is why the arithmetic is stated twice on
purpose and the two statements are compared: this module, and
[tools/quickchick/FreezeModel.v](../quickchick/FreezeModel.v), which states the same
model in Gallina and prints what it computes. `run.py quickchick freeze` runs the second
and holds it against the first.

**Owned here rather than in the quarantine, for the reason
[freezeschema.py](freezeschema.py) is.** There are two ends of this arithmetic now: the
deferred instrument that reports it and the comparison that checks it, and K-83 holds the
landing loop out of `tools/quarantine/` while leaving the other direction open. So the
model lives here and the instrument reads it, and the names it re-exports are the ones
its own readers already ask for.

**Exact rationals, and integers at a declared scale.** Every figure below is computed
over `Fraction` and rendered as an integer at a scale this module fixes, so the
comparison against the prover is an integer equality rather than a float epsilon, and
the rounding rule is one both sides can state: floor(value * scale + 1/2), which is
`Z.div (2 * num * scale + den) (2 * den)` in the harness and `//` here. Neither side
rounds twice, and neither carries a tolerance.

**What this does not decide.** The bar, the geometry candidates and the hit rate are the
freeze measurement contract's to declare and K-77's to hold; what is here is the
arithmetic over them and nothing about whether a candidate is the right one. And nothing
here is a measurement: the corpus §2 names does not exist yet, so every figure is a shape
a candidate must satisfy whatever the observation turns out to be.
"""

import re
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Final

# The register entry each half of this arithmetic is stated at, for a finding that has to
# say which sentence it is about.
SLOT_MODEL = "R-15-036h"
PACKING_TERM = "R-15-036j"
COMMITMENT = "R-15-036i"
REGISTER = "docs/requirements-register.md"

# =====================================================================================
# what the format and R-15-036 already fix
# =====================================================================================

# The `C` counterfactual R-15-036 rests the exclusion on, and the canonical stream it is
# a share of. The bar is their product and is derived here rather than copied from any
# sentence, which is what makes the contract's 22.4 checkable at all. The shares are
# whole percents because that is what they are: a float literal for 0.70 is not 7/10 and
# would put a binary rounding error inside an arithmetic whose whole point is exactness.
CANONICAL_BITS: Final[int] = 32
OPTIMISTIC_SHARE_PCT: Final[int] = 70
PESSIMISTIC_SHARE_PCT: Final[int] = 75
OPTIMISTIC_SHARE: Final[float] = OPTIMISTIC_SHARE_PCT / 100
PESSIMISTIC_SHARE: Final[float] = PESSIMISTIC_SHARE_PCT / 100

# The slot width the format leaves no room in: an escape is exactly two slots carrying
# one canonical instruction verbatim, so 2w >= 32; any wider slot wastes 2(w - 16) bits
# on every escape and buys index space above the 2^16 dictionary bound.
SLOT_WIDTH: Final[int] = 16
DICTIONARY_INDEX_BOUND: Final[int] = 16          # log2 of the entries a slot can index
ESCAPE_PAIR_WIDTH: Final[int] = CANONICAL_BITS // 2

# R-15-036j's break-even hit rate against the optimistic figure, in thousandths, which is
# where the freeze measurement contract's own sentence puts it. Stated as the integer
# because that is the scale the model is walked at; the float is what a reader wants.
BREAK_EVEN_MILLI: Final[int] = 804
BREAK_EVEN: Final[float] = BREAK_EVEN_MILLI / 1000

# The reference instantiation R-15-036h names, `(w, h, k)`.
REFERENCE: Final[tuple[int, int, int]] = (SLOT_WIDTH, 16, 7)


def optimistic_bar() -> float:
    """The acceptance bar in encoded bits per instruction, derived and not declared."""
    return float(exact_bar())


def pessimistic_bar() -> float:
    """The figure reported beside the bar, which is not the bar."""
    return float(Fraction(PESSIMISTIC_SHARE_PCT * CANONICAL_BITS, 100))


def exact_bar() -> Fraction:
    """The same bar, as the rational the vectors are rendered from."""
    return Fraction(OPTIMISTIC_SHARE_PCT * CANONICAL_BITS, 100)


def slot_width_constraints(w: int) -> tuple[bool, bool, bool]:
    """The three constraints that derive `w` rather than sweeping it, at one width.

    Stated once here because both the derivation below and the vectors read them, and a
    predicate written twice is the defect this repository is built to catch.
    """
    return (2 * w >= CANONICAL_BITS, w <= ESCAPE_PAIR_WIDTH,
            w >= DICTIONARY_INDEX_BOUND)


def slot_width_derivation() -> list[tuple[str, str, bool]]:
    """Why `w` is derived and not swept: each constraint, its arithmetic, and whether
    the reference width satisfies it."""
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


# =====================================================================================
# the model itself, over exact rationals
# =====================================================================================


def per_slot_of(w: int, h: int, k: int) -> Fraction:
    """R-15-036h's `w + h/k`: the bits an instruction pays for one slot with its share
    of the bundle header, which is the bundle width over the slot count."""
    return Fraction(bundle_of(w, h, k), k)


def bundle_of(w: int, h: int, k: int) -> int:
    """The bundle width `h + wk`, which FD-2 sweeps and the format fixes at 128."""
    return h + w * k


def bits(per_slot: Fraction, hit_rate: Fraction, packing: Fraction) -> Fraction:
    """R-15-036h's slot model with R-15-036j's packing term: `(w + h/k)(2 - p + L)`."""
    return per_slot * (2 - hit_rate + packing)


def lambda_bound_of(hit_rate: Fraction, k: int) -> Fraction:
    """R-15-036j's `(2 - p)/(k - 1)`, which reaches 1/3 at `p = 0` and `k = 7`."""
    return (2 - hit_rate) / (k - 1)


def model_bits(per_slot: float, hit_rate: float, packing: float) -> float:
    """The same model for a reader that wants a number rather than a rational.

    Routed through the exact arithmetic rather than restating it: `Fraction` of a float
    is that float exactly, so this rounds once where a float expression rounds at every
    operator, and the two agree to well inside every tolerance a caller here carries.
    """
    return float(bits(Fraction(per_slot), Fraction(hit_rate), Fraction(packing)))


@dataclass(frozen=True)
class Geometry:
    """One `(h, k)` candidate, and the model over it.

    `per_slot` is R-15-036h's `w + h/k`. `lambda_bound` is R-15-036j's `(2 - p)/(k - 1)`.
    `required_lambda` is the packing term the geometry may realize and still clear the
    bar at the stated hit rate, and `min_p_at_bound` is the hit rate it would need if the
    packing were at its own worst case.
    """

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
        """Whether the geometry clears the bar at the break-even hit rate for every
        packing term its own bound admits."""
        return self.required_lambda >= self.lambda_bound

    @property
    def infeasible_at_break_even(self) -> bool:
        """Whether it fails the bar at the break-even hit rate even with perfect
        packing, which no measurement can rescue."""
        return self.required_lambda < 0.0


@dataclass(frozen=True)
class Exact:
    """The same candidate with every figure an exact rational, which is what the
    vectors are rendered from and what the comparison decides over.

    `k` is at least 2 here and the caller is refused below 2: a one-slot bundle has no
    packing choice, so `(2 - p)/(k - 1)` is not a bound on anything and the float-facing
    `geometry` below carries the degenerate branch instead of this one pretending to.
    """

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
    """One candidate bundle geometry, scored against the derived bar in exact rationals.

    `legal` is FD-2's own structural constraint, `h >= k`, which holds because the header
    carries one escape-start bit per slot: a candidate below it is not a narrower search,
    it is a bundle whose header cannot say where its escapes begin.
    """
    if k < 2:
        raise ValueError(f"a bundle of {k} slot(s) has no packing term to bound, so "
                         "R-15-036j's arithmetic is not stated over it")
    per_slot = per_slot_of(w, h, k)
    bar = exact_bar()
    return Exact(
        w=w, h=h, k=k, p=p, bundle=bundle_of(w, h, k), per_slot=per_slot,
        lambda_bound=lambda_bound_of(p, k),
        required_lambda=bar / per_slot - (2 - p),
        # the hit rate that puts the model on the bar with the packing at its own bound,
        # and with no packing loss at all; both are `2 - x` for the x each case solves to
        min_p_at_bound=2 - bar * (k - 1) / (per_slot * k),
        min_p_unpacked=2 - bar / per_slot,
        legal=h >= k,
    )


def geometry(h: int, k: int, w: int = SLOT_WIDTH, p: float = BREAK_EVEN) -> Geometry:
    """The same candidate as floats, which is what the instrument's report renders.

    A one-slot bundle is the one case `score` refuses, so it is carried here: its bound
    is infinite rather than a number, and its two hit-rate figures collapse onto each
    other because a bundle with one slot strands none.
    """
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
    """One region length, and the site count at which outlining begins to pay.

    R-15-036p's arithmetic: a region of `n` instructions at `m` site-invariant sites
    costs `nm` slots inline, `n + m + 1` outlined under a composition-time absolute call
    whose one target is one shared dictionary entry, and `n + 2m + 1` under a PC-relative
    one whose per-site displacement is a site-varying two-slot escape. `None` is *never
    pays*, which is a result and not a missing figure.
    """

    n: int
    break_even_absolute: int | None
    break_even_pcrelative: int | None


def outlining_break_even(lengths: "list[int] | range") -> list[Outlining]:
    """The site count at which each region length starts to pay, under both forms."""
    out: list[Outlining] = []
    for n in lengths:
        # nm > n + m + 1 <=> m(n - 1) > n + 1, and nm > n + 2m + 1 <=> m(n - 2) > n + 1
        absolute = (n + 1) // (n - 1) + 1 if n > 1 else None
        pcrelative = (n + 1) // (n - 2) + 1 if n > 2 else None
        out.append(Outlining(n=n, break_even_absolute=absolute,
                             break_even_pcrelative=pcrelative))
    return out


# =====================================================================================
# the vectors, and the scales they are stated at
# =====================================================================================
#
# These grids are this comparison's domain and not the contract's candidate set: what is
# being decided is the arithmetic, and which `(h, k)` the freeze actually weighs is §8's
# to declare and K-77's to hold. The grid contains the three declared candidates, so a
# disagreement about one of them is inside this comparison, and it contains illegal and
# infeasible candidates too, because a column that is constant down a family decides
# nothing.

P_SCALE: Final[int] = 1_000              # a hit rate, in thousandths
BITS_SCALE: Final[int] = 100             # a bits-per-instruction figure, in hundredths
RATE_SCALE: Final[int] = 10_000          # a probability or a packing term
COEFF_SCALE: Final[int] = 10             # the linear form's coefficients, in tenths

SLOT_WIDTHS: Final[tuple[int, ...]] = (8, 12, 16, 17, 20, 32)
HEADERS: Final[tuple[int, ...]] = (8, 16, 32)
SLOT_COUNTS: Final[tuple[int, ...]] = (2, 3, 4, 7, 8, 15, 16)
HIT_RATES: Final[tuple[int, ...]] = (0, 500, 728, 775, 800, BREAK_EVEN_MILLI, 850, 900,
                                     950, 1000)
GEOMETRY_RATES: Final[tuple[int, ...]] = (0, BREAK_EVEN_MILLI, 950)
REGION_LENGTHS: Final[tuple[int, ...]] = (1, 2, 3, 4, 5, 6, 7, 8)

# The families a run walks, in the order the harness prints them. Named so that a floor
# can be stated over the set rather than over a number somebody wrote down.
FAMILIES: Final[tuple[str, ...]] = ("bar", "swd", "lin", "ref", "geo", "obe")

PREFIX: Final[str] = "fm"


def scaled(value: Fraction, scale: int) -> int:
    """`value` at `scale`, rounded to the nearest integer with a half rounded up.

    floor(value * scale + 1/2), which is what `Z.div (2n*s + d) (2d)` computes in the
    harness: `Z.div` is floor division and so is `//`, and the expression depends on the
    rational's value alone, so the harness's unreduced fraction and this reduced one give
    the same integer. Half-up rather than half-away-from-zero because that is the rule a
    single flooring division states, and a signed magnitude rounded apart from its sign
    would be a second rule.
    """
    num, den = (value * scale).as_integer_ratio()
    return (2 * num + den) // (2 * den)


def _bit(value: bool) -> str:
    return "1" if value else "0"


def _opt(value: int | None) -> str:
    return "n" if value is None else str(value)


def vector_lines() -> list[str]:
    """Every vector this model states, in the order the harness prints them.

    One line per point, keyed by the fields before the `->` and valued by the fields
    after it, which is the form both earlier model-as-oracle rigs crossed in: the two
    sides are not compiled against each other and a disagreement names a line a person
    reads on both sides.
    """
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


# =====================================================================================
# the four figures the register states in its own prose
# =====================================================================================
#
# R-15-036h and R-15-036j each quote the model at the reference instantiation, and those
# quotations are the only place in this repository where the arithmetic is written down
# in a form a reader checks by eye. They are read out of the register rather than copied
# here for the reason the instrument reads its contract's break-even rather than
# declaring it: a constant here would be a third statement of a figure that already has
# two, and the failure it would hide is the one this whole comparison is against.

_LINEAR_RE = re.compile(
    r"at the reference instantiation(?: \([^)]*\))? is ([\d.]+) [-−] ([\d.]+)\*p\*")
_ENDPOINT_RE = re.compile(
    r"reaches (\d+)/(\d+) at \*p\* = 0, where [^.]*?for ([\d.]+) bits per instruction "
    r"against the bare model's ([\d.]+)")


@dataclass(frozen=True)
class Anchors:
    """The four reference figures the register's own prose states, as exact rationals.

    `intercept` and `slope` are R-15-036h's linear form; `bound_num` over `bound_den` is
    R-15-036j's packing bound at `p = 0`; `packed` and `bare` are the two endpoints that
    entry states beside it.
    """

    intercept: Fraction
    slope: Fraction
    bound_num: int
    bound_den: int
    packed: Fraction
    bare: Fraction


def anchors(root: Path) -> tuple[Anchors | None, list[str]]:
    """The register's own four figures, or what stopped this reading.

    Fail-closed on either sentence having moved: a comparison against an empty set of
    anchors would report the two arithmetics agreeing with each other and say nothing
    about whether either agrees with the entry it implements.
    """
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
    """One side's vectors against the register's four figures.

    Run over the prover's answer and over this module's alike, because the two agreeing
    with each other says nothing about either agreeing with the entry: a defect
    transcribed into both statements is exactly what a comparison of the two cannot see,
    and the register's own prose is the third reading that can.
    """
    found = {line.split(" -> ")[0]: line.split(" -> ")[1].split()
             for line in lines if " -> " in line}
    w, h, k = REFERENCE
    findings: list[str] = []
    linear = found.get(f"{PREFIX} lin {w} {h} {k}")
    reference = found.get(f"{PREFIX} ref 0")
    if linear is None or reference is None:
        return [f"{whose} states no line at the reference instantiation "
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


def compare(theirs: list[str], ours: list[str]) -> list[str]:
    """The prover's vectors against this module's, keyed by the point each states.

    Keyed rather than zipped, so that a grid one side walks and the other does not is a
    line named in the report instead of every later line reading as a disagreement. Both
    directions, because a point the harness dropped and a point it invented are the same
    defect seen from two sides.
    """
    def index(lines: list[str]) -> dict[str, str]:
        return {line.split(" -> ")[0]: line.split(" -> ")[1]
                for line in lines if line.startswith(f"{PREFIX} ") and " -> " in line}

    prover, model = index(theirs), index(ours)
    findings = [f"the harness states no vector at all, having printed "
                f"{len(theirs)} line(s) none of which is a `{PREFIX} ` point"] \
        if not prover else []
    findings += [f"the harness answers `{key} -> {prover[key]}` and this model answers "
                 f"`{ours_at}`" for key, ours_at in model.items()
                 if key in prover and prover[key] != ours_at]
    findings += [f"the harness states `{key}` and this model states no such point"
                 for key in prover if key not in model]
    findings += [f"this model states `{key}` and the harness states no such point"
                 for key in model if key not in prover]
    return findings
