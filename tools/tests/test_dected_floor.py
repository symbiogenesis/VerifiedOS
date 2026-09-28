# SPDX-License-Identifier: Apache-2.0
"""The distance-6 floor K-54 holds, derived here rather than read from its table.

`counts_tagplane` tables the fewest check bits a binary code of minimum distance 6
admits over 1, 2, 4 and 8 information bits, for any code and for linear codes, and
holds R-15-181a's DECTED width against it. A table is a hand-written fact, so every
entry is proved twice over with no network and no library: a code reaching it is built
and its minimum distance enumerated, and a closed-form bound refuses every length one
check bit shorter. The SECDED count the ladder prices is held the same way, against
the sphere-packing bound for distance 4.
"""

from itertools import combinations
from math import comb

from tests.harness import Case, ensure
from vos.checks.counts_tagplane import (
    DECTED_FLOOR_ANY,
    DECTED_FLOOR_LINEAR,
    DISTANCE,
    secded_bits,
)

# One generator matrix per linear entry, a row per information bit. Nothing below
# trusts them: each is checked for full rank, for the length its entry names, and for
# its minimum distance by enumerating every codeword.
_GENERATORS: dict[int, list[str]] = {
    1: ["111111"],
    2: ["111111000", "000111111"],
    4: ["100000011111", "010001100111", "001010101011", "000111010101"],
    8: ["10000000000011111", "01000000001100111", "00100000010101011",
        "00010000011010101", "00001000100101101", "00000100101010110",
        "00000010110110111", "00000001111011011"],
}

# The cyclic binary Golay code's generator polynomial, 1 + x^2 + x^4 + x^5 + x^6 +
# x^10 + x^11, by its exponents; the code it generates is checked below rather than
# believed.
_GOLAY_EXPONENTS = (0, 2, 4, 5, 6, 10, 11)


def _span(rows: list[int]) -> list[int]:
    """Every sum of a subset of the rows, one per subset, so a dependent set of rows
    shows as a repeated word."""
    words: list[int] = [0]
    for row in rows:
        words += [w ^ row for w in words]
    return words


def _min_distance(words: list[int]) -> int:
    return min((a ^ b).bit_count() for a, b in combinations(words, 2))


def _hamming(n: int, d: int) -> int:
    """The sphere-packing bound on A(n, d): the balls of radius (d - 1) // 2 about the
    words are disjoint, so no more of them fit than the space holds."""
    t = (d - 1) // 2
    return (1 << n) // sum(comb(n, i) for i in range(t + 1))


def _upper(n: int, d: int) -> int:
    """An upper bound on A(n, d), the most words of length n pairwise d apart."""
    if n < d:
        return 1
    bounds = [_hamming(n, d)]
    if d % 2 == 0:
        # a word's parity bit adds one to every odd distance, so A(n, d) = A(n - 1, d - 1)
        bounds.append(_hamming(n - 1, d - 1))
        if n < 2 * d:
            # Plotkin: for even d and n < 2d, A(n, d) <= 2 * floor(d / (2d - n))
            bounds.append(2 * (d // (2 * d - n)))
    return min(bounds)


def _linear_refused(n: int, k: int, d: int) -> bool:
    """Whether no linear [n, k, d'] code with d' >= d exists, by its residual code.

    A codeword of the minimum weight d' leaves, on the coordinates outside its support,
    a residual [n - d', k - 1, ceil(d'/2)] code; the sphere-packing bound refusing that
    at every d' the Singleton bound (d' <= n - k + 1) leaves refuses the code, and where
    that bound leaves no d' at all it refuses the code alone.
    """
    return all((1 << (k - 1)) > _hamming(n - dd, -(-dd // 2)) for dd in range(d, n - k + 2))


def _golay() -> list[int]:
    """The extended Golay code: the cyclic code of length 23 and an overall parity bit."""
    g = sum(1 << e for e in _GOLAY_EXPONENTS)
    return [w | (w.bit_count() & 1) << 23 for w in _span([g << i for i in range(12)])]


def _nordstrom_robinson() -> tuple[int, list[int]]:
    """A (16, 256, 6) code, nonlinear: the Golay words whose restriction to one octad is
    zero or a weight-2 pattern through the octad's first coordinate, with the octad
    then deleted. Returns the length and the words."""
    golay = _golay()
    octad = next(w for w in golay if w.bit_count() == 8)
    inside = [i for i in range(24) if octad >> i & 1]
    outside = [i for i in range(24) if not octad >> i & 1]
    heads = {0} | {1 << inside[0] | 1 << j for j in inside[1:]}
    return len(outside), [sum((w >> i & 1) << j for j, i in enumerate(outside))
                          for w in golay if (w & octad) in heads]


def _tables_cover_the_same_tag_counts() -> None:
    ensure(DISTANCE == 2 + 3 + 1,
           "two corrected and three detected errors need minimum distance 6")
    ensure(set(DECTED_FLOOR_ANY) == set(DECTED_FLOOR_LINEAR) == set(_GENERATORS),
           "every tag count carries an any-code entry, a linear entry and a generator")
    ensure(all(DECTED_FLOOR_ANY[k] <= DECTED_FLOOR_LINEAR[k] for k in DECTED_FLOOR_ANY),
           "a linear code is a code, so no linear floor lies below the any-code floor")


def _linear_entries_are_reached() -> None:
    for k, rows in _GENERATORS.items():
        n = k + DECTED_FLOOR_LINEAR[k]
        ensure(all(len(row) == n for row in rows) and len(rows) == k,
               f"the [{n},{k}] generator has {k} rows of length {n}")
        words = _span([int(row, 2) for row in rows])
        ensure(len(set(words)) == 2 ** k, f"the [{n},{k}] generator has full rank")
        weight = min(w.bit_count() for w in words if w)
        ensure(weight >= DISTANCE,
               f"the [{n},{k}] code reaches distance {DISTANCE}, not {weight}")


def _nonlinear_entry_is_reached() -> None:
    golay = _golay()
    ensure(len(set(golay)) == 4096 and min(w.bit_count() for w in golay if w) == 8,
           "the generator polynomial gives the [24,12,8] extended Golay code")
    n, words = _nordstrom_robinson()
    ensure(n == 16 and len(set(words)) == 256, "the construction gives 256 words of length 16")
    ensure(_min_distance(words) >= DISTANCE,
           "the Nordstrom-Robinson words lie at least 6 apart")
    for k, floor in DECTED_FLOOR_ANY.items():
        if floor < DECTED_FLOOR_LINEAR[k]:
            ensure(k == 8 and n == k + floor,
                   f"the any-code entry at {k} bits is reached by a code this test builds")


def _every_shorter_length_is_refused() -> None:
    for k, floor in DECTED_FLOOR_ANY.items():
        for n in range(k, k + floor):
            ensure(_upper(n, DISTANCE) < 2 ** k,
                   f"no code of length {n} carries {k} bits at distance {DISTANCE}")
    for k, floor in DECTED_FLOOR_LINEAR.items():
        for n in range(k, k + floor):
            ensure(_upper(n, DISTANCE) < 2 ** k or _linear_refused(n, k, DISTANCE),
                   f"no linear code of length {n} carries {k} bits at distance {DISTANCE}")
    # the one linear entry above its any-code floor rests on the residual argument alone
    ensure(_upper(16, DISTANCE) >= 2 ** 8 and _linear_refused(16, 8, DISTANCE),
           "the linear [16,8,6] code is refused by its residual code and not by a bound "
           "that would refuse Nordstrom-Robinson as well")


def _secded_count_is_the_distance_4_floor() -> None:
    """Extended Hamming's count at each rung is the fewest distance 4 admits.

    With c check bits over k data bits the words have length n = k + c, and
    A(n, 4) = A(n - 1, 3) <= 2^(n-1) / n, so c must satisfy k + c <= 2^(c-1). That is
    also the count of distinct odd-weight columns of length c, any k + c of which make a
    parity-check matrix of distance 4, so the least such c is reached as well.
    """
    for k in (64, 128, 256, 512):
        least = next(c for c in range(2, 64) if k + c <= 2 ** (c - 1))
        ensure(secded_bits(k) == least,
               f"{k} data bits take {least} SECDED check bits, not {secded_bits(k)}")


def cases() -> list[Case]:
    return [
        Case("tables-cover-the-same-tag-counts", _tables_cover_the_same_tag_counts),
        Case("linear-entries-are-reached", _linear_entries_are_reached),
        Case("nonlinear-entry-is-reached", _nonlinear_entry_is_reached),
        Case("every-shorter-length-is-refused", _every_shorter_length_is_refused),
        Case("secded-count-is-the-distance-4-floor", _secded_count_is_the_distance_4_floor),
    ]
