# SPDX-License-Identifier: Apache-2.0
"""Independent authored identities and strict-parser refusal controls."""

from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.harness import Case, ensure
from vos import matrix_identity as identity


def _refuses(action: Callable[[], object]) -> None:
    try:
        action()
    except ValueError:
        return
    raise AssertionError("invalid finite identity accepted")


def _linear_programs() -> None:
    matrix, counts = identity.program("t0:=i0+i1; o0:=t0/2; o1:=i0-i1;", 2, 2)
    ensure(matrix == [[Fraction(1, 2), Fraction(1, 2)], [Fraction(1), Fraction(-1)]],
           "exact rational symbolic interpretation")
    ensure(counts == {"additions_subtractions": 2, "nonunit_scalings": 1, "unary_negations": 0},
           "count every arithmetic operation")
    for source in ("o0:=i0*i1;", "o0:=i2;", "o0:=i0; o0:=i1;", "i0:=i1; o0:=i0;",
                   "o0:=i0; o1:=i1;", "o0:=i0", "o0:=__import__('os');", "o0:=i0/0;"):
        _refuses(lambda source=source: identity.program(source, 2, 1))


def _matrix_parsing() -> None:
    ensure(identity.matrix("1 2 R\n1 2 -1/2\n0 0 0\n") == [[Fraction(0), Fraction(-1, 2)]],
           "parse exact sparse coefficient")
    for source in ("1 1 R\n1 1 1\n1 1 2\n0 0 0", "1 1 R\n2 1 1\n0 0 0",
                   "1 1 R\n1 1 1", "1 1 R\n0 0 0\n1 1 1", "1 1 R\n1 1 1/0\n0 0 0"):
        _refuses(lambda source=source: identity.matrix(source))


def _independent_tensor() -> None:
    # Classical 2x2 multiplication, independently enumerate its eight scalar products.
    left, right = [], []
    output = [[Fraction(0)] * 8 for _ in range(4)]
    rank = 0
    for row in range(2):
        for column in range(2):
            for inner in range(2):
                left.append([Fraction(int(a == 2 * row + inner)) for a in range(4)])
                right.append([Fraction(int(b == 2 * inner + column)) for b in range(4)])
                output[2 * row + column][rank] = Fraction(1)
                rank += 1
    ensure(identity.tensor(left, right, output, 2) == 64, "all classical tensor coefficients")
    output[0][0] = Fraction(2)
    _refuses(lambda: identity.tensor(left, right, output, 2))
    _refuses(lambda: identity.tensor([], [], [], 0))


def _receipt_identity() -> None:
    root = Path(__file__).resolve().parents[2]
    with TemporaryDirectory(prefix="vos-matrix-receipt-") as temporary:
        copy = Path(temporary)
        for name in (identity.PIN, identity.REPORT, *identity.SOURCES):
            path = copy / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((root / name).read_bytes())
        identity.check_report(copy)
        source = copy / identity.SOURCES[0]
        source.write_bytes(source.read_bytes() + b"\n")
        _refuses(lambda: identity.check_report(copy))


def cases() -> list[Case]:
    return [Case("exact-linear-program-and-refusals", _linear_programs),
            Case("sparse-matrix-strict-parse", _matrix_parsing),
            Case("independent-tensor-corruption", _independent_tensor),
            Case("stale-replay-receipt-refused", _receipt_identity)]
