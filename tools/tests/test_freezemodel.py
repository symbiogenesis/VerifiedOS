# SPDX-License-Identifier: Apache-2.0
"""The freeze density model's host half: the arithmetic, the domain, and the comparison.

The prover is the guest's and is not reachable here, so what this module exercises is
everything that decides the comparison's *answer* before the prover is asked. Three
things fail quietly and each has cases below.

**The rearrangement.** [freezemodel.py](../vos/freezemodel.py) states the model over
exact rationals and [FreezeModel.v](../quickchick/FreezeModel.v) states it over integer
numerators and denominators, because Rocq has no rational this comparison would want.
That is an algebraic rearrangement per figure, `2 - bar*(k - 1)/(per_slot*k)` becoming
`(200*bundle - bar*(k - 1))/(100*bundle)`, and a rearrangement is where an arithmetic
loses a factor without losing its shape. `_the_rearrangement_is_the_same_arithmetic`
rebuilds every vector by the harness's own integer recipe and holds the two lists equal.

**The domain.** Two grids that drift apart do not disagree, they stop overlapping, and
the comparison then reports missing points rather than a wrong answer. The grids and the
scales are read out of the harness text and held against the module's.

**The floors.** A prover that printed nothing, a family whose grid went empty, and a
register sentence that moved out from under the reader are each a pass this comparison
must not be able to make.

**What is NOT decided here, and it is the residue this module cannot close.** The mirror
below is a *transcription* of the harness's definitions into Python, so it decides that
the harness's arithmetic is the model's and not that the harness compiles, that its
renderer prints what these expressions compute, or that a later edit to the `.v` is
reflected here. Only `run.py quickchick freeze`, in the guest, decides those.
"""

import re
from fractions import Fraction

from tests.harness import Case, ensure, sandbox_tree
from vos import corpus as corpus_mod
from vos import freezemodel as fm

# =====================================================================================
# the harness's own arithmetic, transcribed
# =====================================================================================
#
# One function per `Definition` in FreezeModel.v, spelled as that file spells it: an
# unreduced numerator and denominator, one flooring division, and no `Fraction`
# anywhere. The grids are deliberately not transcribed, the domain case below holding
# them equal against the file's own text instead, so this mirror carries the arithmetic
# and nothing else and there is one transcription here rather than two.

_P = fm.P_SCALE
_BITS = fm.BITS_SCALE
_RATE = fm.RATE_SCALE
_COEFF = fm.COEFF_SCALE
_CANON = 32
_OPT_PCT = 70
_PESS_PCT = 75
_INDEX_BOUND = 16
_ESCAPE_PAIR = _CANON // 2
_BAR = _OPT_PCT * _CANON              # optimistic_bar, in hundredths of a bit
_W = 16


def _z_scaled(num: int, den: int, scale: int) -> int:
    """`Z.div (2 * num * scale + den) (2 * den)`, over a positive `den`."""
    return (2 * num * scale + den) // (2 * den)


def _z_bundle(w: int, h: int, k: int) -> int:
    return h + w * k


def _z_bare(w: int, h: int, k: int, pm: int) -> int:
    return _z_scaled(_z_bundle(w, h, k) * (2 * _P - pm), _P * k, _BITS)


def _z_packed(w: int, h: int, k: int, pm: int, ln: int, ld: int) -> int:
    return _z_scaled(_z_bundle(w, h, k) * ((2 * _P - pm) * ld + _P * ln),
                     _P * k * ld, _BITS)


def _z_bound_num(pm: int) -> int:
    return 2 * _P - pm


def _z_bound_den(k: int) -> int:
    return _P * (k - 1)


def _z_required_num(w: int, h: int, k: int, pm: int) -> int:
    return _BAR * k * 10 - (2 * _P - pm) * _z_bundle(w, h, k)


def _z_required_den(w: int, h: int, k: int) -> int:
    return _P * _z_bundle(w, h, k)


def _z_at_bound_num(w: int, h: int, k: int) -> int:
    return 200 * _z_bundle(w, h, k) - _BAR * (k - 1)


def _z_unpacked_num(w: int, h: int, k: int) -> int:
    return 200 * _z_bundle(w, h, k) - _BAR * k


def _z_min_p_den(w: int, h: int, k: int) -> int:
    return 100 * _z_bundle(w, h, k)


def _z_bit(flag: bool) -> str:
    return "1" if flag else "0"


def _z_lines() -> list[str]:
    """Every vector the harness states, by the harness's own expressions."""
    out = [f"fm bar -> {_CANON} {_OPT_PCT} {_PESS_PCT} {_BAR} {_PESS_PCT * _CANON}"]
    for w in fm.SLOT_WIDTHS:
        # the harness spells the first and third `Z.leb <constant> <expression>`; the
        # operands are turned around here and the relation is not
        escape, waste, index = 2 * w >= _CANON, w <= _ESCAPE_PAIR, w >= _INDEX_BOUND
        out.append(f"fm swd {w} -> {_z_bit(escape)} {_z_bit(waste)} {_z_bit(index)} "
                   f"{_z_bit(escape and waste and index)}")
    for h in fm.HEADERS:
        for k in fm.SLOT_COUNTS:
            bundle = _z_bundle(_W, h, k)
            out.append(f"fm lin {_W} {h} {k} -> {_z_scaled(2 * bundle, k, _COEFF)} "
                       f"{_z_scaled(bundle, k, _COEFF)} {bundle} "
                       f"{_z_scaled(bundle, k, _BITS)}")
    for pm in fm.HIT_RATES:
        num, den = _z_bound_num(pm), _z_bound_den(7)
        out.append(f"fm ref {pm} -> {_z_bare(_W, 16, 7, pm)} {num} {den} "
                   f"{_z_scaled(num, den, _RATE)} "
                   f"{_z_packed(_W, 16, 7, pm, num, den)}")
    for h in fm.HEADERS:
        for k in fm.SLOT_COUNTS:
            for pm in fm.GEOMETRY_RATES:
                bundle = _z_bundle(_W, h, k)
                need = _z_required_num(_W, h, k, pm)
                clears = (_z_bound_num(pm) * _z_required_den(_W, h, k)
                          <= need * _z_bound_den(k))
                out.append(
                    f"fm geo {_W} {h} {k} {pm} -> {bundle} {_z_bit(k <= h)} "
                    f"{_z_scaled(bundle, k, _BITS)} "
                    f"{_z_scaled(_z_bound_num(pm), _z_bound_den(k), _RATE)} "
                    f"{_z_scaled(need, _z_required_den(_W, h, k), _RATE)} "
                    f"{_z_scaled(_z_at_bound_num(_W, h, k), _z_min_p_den(_W, h, k), _RATE)} "
                    f"{_z_scaled(_z_unpacked_num(_W, h, k), _z_min_p_den(_W, h, k), _RATE)} "
                    f"{_z_bit(clears)} {_z_bit(need < 0)} {_z_bare(_W, h, k, pm)}")
    for n in fm.REGION_LENGTHS:
        absolute = f"{(n + 1) // (n - 1) + 1}" if n > 1 else "n"
        pcrelative = f"{(n + 1) // (n - 2) + 1}" if n > 2 else "n"
        out.append(f"fm obe {n} -> {absolute} {pcrelative}")
    return out


# =====================================================================================
# the harness text, read for what it declares
# =====================================================================================

_LIST = re.compile(r"^Definition (\w+) : list Z :=\s*([^.]*)\.", re.MULTILINE)
_CONST = re.compile(r"^Definition (\w+) : Z := (-?\d+)\.", re.MULTILINE)
_FAMILY = re.compile(r'"fm (\w+) ')


def _harness_text() -> str:
    return (corpus_mod.find_root() / fm.HARNESS).read_text(encoding="utf-8")


def _harness_lists(text: str) -> dict[str, tuple[int, ...]]:
    return {name: tuple(int(v) for v in body.strip().strip("[]").split(";") if v.strip())
            for name, body in _LIST.findall(text)}


# =====================================================================================
# the cases
# =====================================================================================


def _scaled_rounds_half_up() -> None:
    """One flooring division and therefore one rule, sign included: a value that rounds
    to zero from below is `0` and never `-0`, which Z has no way to spell either."""
    for value, scale, want in ((Fraction(1, 2), 1, 1), (Fraction(3, 2), 1, 2),
                               (Fraction(1, 3), 1, 0), (Fraction(-1, 2), 1, 0),
                               (Fraction(-3, 2), 1, -1), (Fraction(-1, 3), 1, 0)):
        got = fm.scaled(value, scale)
        ensure(got == want, f"{value} at 1/{scale} came out {got}, wanted {want}")


def _scaled_ignores_the_reduction() -> None:
    """The module reduces its fractions and the harness does not, so the two agree only
    because the recipe depends on the rational's value and never on its spelling."""
    for num, den, scale in ((2000, 6000, 10000), (1, 3, 10000), (128, 7, 100),
                            (-106, 165, 10000), (-212000, 330000, 10000)):
        got = fm.scaled(Fraction(num, den), scale)
        want = _z_scaled(num, den, scale)
        ensure(got == want,
               f"{num}/{den} at 1/{scale}: the module says {got} and the harness's "
               f"recipe says {want}")


def _the_rearrangement_is_the_same_arithmetic() -> None:
    """Every vector, rebuilt by the harness's integer expressions.

    This is the case the whole module is for. The two statements are not compiled
    against each other and cannot be, so what would otherwise decide their agreement is
    a guest run that costs a prover; this decides the part of it that is arithmetic.
    """
    ours, mirror = fm.vector_lines(), _z_lines()
    ensure(len(ours) == len(mirror),
           f"the module states {len(ours)} vector(s) and the harness's recipe "
           f"{len(mirror)}")
    differ = [(a, b) for a, b in zip(ours, mirror, strict=True) if a != b]
    if differ:
        raise AssertionError(
            f"{len(differ)} vector(s) differ; the first is\n"
            f"  module:  {differ[0][0]}\n  harness: {differ[0][1]}")


def _every_vector_is_keyed_once() -> None:
    """The comparison is keyed by the fields before the arrow, so a key stated twice is
    a point that silently leaves the comparison at whichever value came last."""
    keys = [line.split(" -> ")[0] for line in fm.vector_lines()]
    twice = sorted({key for key in keys if keys.count(key) > 1})
    ensure(not twice, f"these points are stated more than once: {twice}")


def _the_domain_is_the_harness_s() -> None:
    """The grids the module walks are the grids the harness walks.

    Read out of the `.v` rather than transcribed, because two grids that drift apart do
    not disagree on a figure: they stop overlapping, and the guest run then reports
    missing points at both ends where the defect is one edit in one file.
    """
    lists = _harness_lists(_harness_text())
    for name, want in (("slot_widths", fm.SLOT_WIDTHS), ("headers", fm.HEADERS),
                       ("slot_counts", fm.SLOT_COUNTS), ("hit_rates", fm.HIT_RATES),
                       ("geometry_rates", fm.GEOMETRY_RATES),
                       ("region_lengths", fm.REGION_LENGTHS)):
        ensure(name in lists, f"{fm.HARNESS} declares no `{name}` this reader can find")
        ensure(lists[name] == want,
               f"{fm.HARNESS}'s `{name}` is {lists[name]} and {fm.MODULE}'s is {want}")


def _the_scales_are_the_harness_s() -> None:
    """And so are the constants the format fixes: a scale stated at two values makes
    every figure in its family differ by a factor nobody would read as one."""
    consts = dict(_CONST.findall(_harness_text()))
    for name, want in (("p_scale", _P), ("bits_scale", _BITS), ("rate_scale", _RATE),
                       ("coeff_scale", _COEFF), ("canonical_bits", fm.CANONICAL_BITS),
                       ("optimistic_share", fm.OPTIMISTIC_SHARE_PCT),
                       ("pessimistic_share", fm.PESSIMISTIC_SHARE_PCT),
                       ("dictionary_index_bound", fm.DICTIONARY_INDEX_BOUND),
                       ("slot_width", fm.SLOT_WIDTH),
                       ("ref_header", fm.REFERENCE[1]), ("ref_slots", fm.REFERENCE[2])):
        ensure(name in consts,
               f"{fm.HARNESS} declares no `{name}` this reader can find")
        ensure(int(consts[name]) == want,
               f"{fm.HARNESS}'s `{name}` is {consts[name]} and {fm.MODULE}'s is {want}")


def _the_families_are_the_harness_s() -> None:
    families = set(_FAMILY.findall(_harness_text()))
    ensure(families == set(fm.FAMILIES),
           f"{fm.HARNESS} prints the families {sorted(families)} and {fm.MODULE} "
           f"declares {sorted(fm.FAMILIES)}")


def _an_empty_family_is_a_finding() -> None:
    """Fail-closed on the narrowing the comparison cannot otherwise see: two grids
    emptied in step agree with each other on everything they still carry."""
    got = fm.empty_families([], "a side that printed nothing")
    ensure(len(got) == len(fm.FAMILIES),
           f"an empty side yielded {len(got)} finding(s) for {len(fm.FAMILIES)} "
           "declared families")
    ensure(not fm.empty_families(fm.vector_lines(), fm.MODULE),
           "the module's own vectors were read as leaving a family empty")


def _a_silent_harness_is_one_finding() -> None:
    """One finding rather than one per point. A harness that printed nothing disagrees
    with every vector at once, and a report saying so line by line buries the fact."""
    got = fm.compare([], fm.vector_lines())
    ensure(len(got) == 1, f"a silent harness yielded {len(got)} finding(s): {got[:3]}")
    ensure("no vector at all" in got[0], f"the finding read {got[0]!r}")


def _a_disagreement_is_named_both_ways() -> None:
    ours = fm.vector_lines()
    moved = [ours[0].replace("-> 32", "-> 33"), *ours[1:-1], "fm obe 99 -> 1 1"]
    got = fm.compare(moved, ours)
    ensure(len(got) == 3, f"three defects were seeded and {len(got)} reported: {got}")
    ensure(any("this model answers" in f for f in got), f"no value disagreement: {got}")
    ensure(any("the harness states `fm obe 99`" in f for f in got),
           f"an invented point was not named: {got}")
    ensure(any("this model states `fm obe 8`" in f for f in got),
           f"a dropped point was not named: {got}")


def _a_moved_register_sentence_decides_nothing() -> None:
    """Fail-closed on the third reading. Two statements agreeing with each other say
    nothing about either agreeing with the entry, so a register this reader cannot
    parse is a finding and never a comparison quietly made without it."""
    with sandbox_tree({fm.REGISTER: "**R-15-036h** IS: the model, restated.\n"}) as root:
        fixed, said = fm.anchors(root)
    ensure(fixed is None, "a register stating neither figure was read as stating both")
    ensure(len(said) == 2, f"one finding per moved sentence, got {len(said)}: {said}")
    with sandbox_tree({"README.md": "no register here\n"}) as root:
        fixed, said = fm.anchors(root)
    ensure(fixed is None and len(said) == 1,
           f"an absent register gave {fixed} and {said}")


def _the_register_states_the_four_figures() -> None:
    """The live register, read for the four figures R-15-036h and R-15-036j quote, and
    the module's own vectors held against them.

    This is the reading the guest run makes of the harness, made here of the module: the
    register's prose is the only statement of this arithmetic outside the two files that
    compute it, and it is the one a person checks by eye.
    """
    fixed, said = fm.anchors(corpus_mod.find_root())
    ensure(fixed is not None and not said,
           f"{fm.REGISTER}'s own figures were not read: {said}")
    if fixed is None:
        return
    findings = fm.held(fm.vector_lines(), fixed, fm.MODULE)
    ensure(not findings, "\n".join(findings))


def _a_side_stating_no_reference_point_is_a_finding() -> None:
    fixed, said = fm.anchors(corpus_mod.find_root())
    ensure(fixed is not None, f"{fm.REGISTER}'s own figures were not read: {said}")
    if fixed is None:
        return
    got = fm.held(["fm bar -> 32 70 75 2240 2400"], fixed, "a side")
    ensure(len(got) == 1 and "reference instantiation" in got[0],
           f"a side stating no reference line gave {got}")


def _the_bar_is_a_product_and_not_a_figure() -> None:
    """22.4 is nowhere computed as a figure: it is 70% of 32, and the two operands are
    what make the freeze measurement contract's own sentence checkable at all."""
    ensure(fm.exact_bar() == Fraction(fm.OPTIMISTIC_SHARE_PCT * fm.CANONICAL_BITS, 100),
           f"the bar is not the product of its operands: {fm.exact_bar()}")
    ensure(fm.exact_bar() == Fraction(112, 5), f"the bar came out {fm.exact_bar()}")


def _a_one_slot_bundle_is_refused_where_it_is_not_stated() -> None:
    """R-15-036j's bound is `(2 - p)/(k - 1)`, which is not a bound on anything at
    `k = 1`, so the exact scoring refuses it rather than dividing by zero or inventing
    an answer; the float-facing reader carries the degenerate case explicitly."""
    try:
        fm.score(16, 1)
    except ValueError as err:
        ensure("no packing term" in str(err), f"the refusal said {err!r}")
    else:
        raise AssertionError("a one-slot bundle was scored against a bound")
    degenerate = fm.geometry(16, 1)
    ensure(degenerate.lambda_bound == float("inf"),
           f"a one-slot bundle's bound came out {degenerate.lambda_bound}")
    ensure(degenerate.min_p_at_bound == degenerate.min_p_unpacked,
           "a bundle with one slot strands none, so its two hit rates are one")


def _the_outlining_break_even_is_the_register_s() -> None:
    """R-15-036p states one worked figure in its own prose: a two-instruction region
    pays from four sites under the absolute form and never under the PC-relative one."""
    rows = {row.n: row for row in fm.outlining_break_even([2, 3])}
    ensure(rows[2].break_even_absolute == 4,
           f"a two-instruction region pays from {rows[2].break_even_absolute} sites")
    ensure(rows[2].break_even_pcrelative is None,
           "a two-instruction region was made to pay under the PC-relative form")


def cases() -> list[Case]:
    # Every case here is a read of this checkout and of nothing else, so none carries a
    # lane. The prover is the guest's and `run.py quickchick freeze` is what asks for
    # it; a case marked "host" would be one the Ubuntu runner in CI never ran, which is
    # the wrong half of the world to leave this arithmetic unchecked on.
    return [
        Case("scaled-rounds-half-up", _scaled_rounds_half_up),
        Case("scaled-ignores-the-reduction", _scaled_ignores_the_reduction),
        Case("the-rearrangement-is-the-same-arithmetic",
             _the_rearrangement_is_the_same_arithmetic),
        Case("every-vector-is-keyed-once", _every_vector_is_keyed_once),
        Case("the-domain-is-the-harness's", _the_domain_is_the_harness_s),
        Case("the-scales-are-the-harness's", _the_scales_are_the_harness_s),
        Case("the-families-are-the-harness's", _the_families_are_the_harness_s),
        Case("an-empty-family-is-a-finding", _an_empty_family_is_a_finding),
        Case("a-silent-harness-is-one-finding", _a_silent_harness_is_one_finding),
        Case("a-disagreement-is-named-both-ways", _a_disagreement_is_named_both_ways),
        Case("a-moved-register-sentence-decides-nothing",
             _a_moved_register_sentence_decides_nothing),
        Case("the-register-states-the-four-figures",
             _the_register_states_the_four_figures),
        Case("a-side-stating-no-reference-point-is-a-finding",
             _a_side_stating_no_reference_point_is_a_finding),
        Case("the-bar-is-a-product-and-not-a-figure",
             _the_bar_is_a_product_and_not_a_figure),
        Case("a-one-slot-bundle-is-refused",
             _a_one_slot_bundle_is_refused_where_it_is_not_stated),
        Case("the-outlining-break-even-is-the-register's",
             _the_outlining_break_even_is_the_register_s),
    ]
