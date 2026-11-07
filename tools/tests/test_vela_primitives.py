# SPDX-License-Identifier: Apache-2.0
"""Independent value controls for Vela's fixed-width integer and `char` primitives.

Expected values come from a reference written here over Python integers, directly
from the [primitive contract](../../docs/languages/vela/first-release.md#primitive-semantics):
truncating division through `Fraction`, modular reduction from the type's minimum,
clamping by sorting and range tests by comparison. The reference shares no helper
with the static evaluator or with the Gallina prelude, and both are held to it.

Partial operations have total images. Their out-of-domain results are fixed by the
two implementations rather than by the contract, and the reference names them
apart as image conventions: ordinary arithmetic reduces modulo `2^w`, division by
zero yields zero, remainder by zero yields the dividend, an excessive shift yields
the fill bits, a narrowing `From` keeps the low bits, a negative `to_nat` is zero and
`nat_to_usize` reduces modulo `2^64`. The checked operations, which the contract
does define everywhere, use no convention.

The kernel replay emits the prelude with one `eq_refl` definition per sampled row
and compiles it with the locked prover; it runs in the toolchain lane, which the
runner leaves out wherever the guest switch is not standing. Its fault controls
restore former placeholder definitions and require a check, not the prelude, to
fail.
"""

import itertools
import re
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import env, proofenv
from vos.vela import elaborate_whnf
from vos.vela.elaborate import _Elaborator
from vos.vela.elaborate_protocol import _Protocol
from vos.vela.elaborate_types import (
    _GALLINA,
    _INT_SPECS,
    _PRELUDE,
    _allows_from_conversion,
    _apps,
    _constant,
    _int_term,
    _Term,
    _term,
)


@dataclass(frozen=True)
class _Width:
    name: str
    tag: int
    bits: int
    signed: bool

    @property
    def lo(self) -> int:
        return -(1 << (self.bits - 1)) if self.signed else 0

    @property
    def hi(self) -> int:
        return (1 << (self.bits - 1)) - 1 if self.signed else (1 << self.bits) - 1


_WIDTHS = {width.name: width for width in (
    _Width("u8", 0, 8, False), _Width("u16", 1, 16, False), _Width("u32", 2, 32, False),
    _Width("u64", 3, 64, False), _Width("usize", 4, 64, False), _Width("i8", 5, 8, True),
    _Width("i16", 6, 16, True), _Width("i32", 7, 32, True), _Width("i64", 8, 64, True))}
# The boundary classes the brief names: u8, i8, u16, i32, u64, i64 and usize.
_SAMPLED = ("u8", "i8", "u16", "i32", "u64", "i64", "usize")
_USIZE = _WIDTHS["usize"]
_SCALAR_MAX = 0x10FFFF
_SURROGATES = range(0xD800, 0xE000)

# An outcome: an integer, a Boolean, ("nat", n), ("char", c),
# ("ok", value) or ("err", constructor name).
type Outcome = object


def _fits(width: _Width, value: int) -> bool:
    return width.lo <= value <= width.hi


def _reduce(width: _Width, value: int) -> int:
    return width.lo + (value - width.lo) % (1 << width.bits)


def _clamp(width: _Width, value: int) -> int:
    return sorted((width.lo, value, width.hi))[1]


def _quotient(a: int, b: int) -> int:
    return int(Fraction(a, b))


def _remainder(a: int, b: int) -> int:
    return a - b * _quotient(a, b)


def _pattern(width: _Width, value: int) -> int:
    return value % (1 << width.bits)


def _from_pattern(width: _Width, bits: int) -> int:
    return bits - (1 << width.bits) if width.signed and bits >= (1 << (width.bits - 1)) else bits


def _checked(width: _Width, exact: int) -> Outcome:
    return ("ok", exact) if _fits(width, exact) else ("err", "Overflow")


def _binary(width: _Width, op: str, a: int, b: int) -> Outcome:
    """The contract's meaning of `op` at `width`, with the named image conventions."""
    exact = {"add": a + b, "sub": a - b, "mul": a * b}
    if op.removeprefix("wrap_") in exact:
        return _reduce(width, exact[op.removeprefix("wrap_")])
    if op.startswith("sat_"):
        return _clamp(width, exact[op[4:]])
    if op in {"chk_add", "chk_sub", "chk_mul"}:
        return _checked(width, exact[op[4:]])
    if op == "div":
        return 0 if b == 0 else _reduce(width, _quotient(a, b))
    if op == "rem":
        return a if b == 0 else _remainder(a, b)
    if op == "chk_div":
        return ("err", "ZeroDivisor") if b == 0 else _checked(width, _quotient(a, b))
    if op == "chk_rem":
        return ("err", "ZeroDivisor") if b == 0 else ("ok", _remainder(a, b))
    if op in {"and", "or", "xor"}:
        x, y = _pattern(width, a), _pattern(width, b)
        return _from_pattern(width, {"and": x & y, "or": x | y, "xor": x ^ y}[op])
    return {"eq": a == b, "ne": a != b, "lt": a < b, "le": a <= b, "gt": a > b, "ge": a >= b}[op]


def _unary(width: _Width, op: str, a: int) -> Outcome:
    if op in {"neg", "wrap_neg"}:
        return _reduce(width, -a)
    if op == "sat_neg":
        return _clamp(width, -a)
    if op == "chk_neg":
        return _checked(width, -a)
    if op == "not":
        return _from_pattern(width, 2 ** width.bits - 1 - _pattern(width, a))
    ensure(op == "to_nat", f"unknown unary operation {op}")
    return ("nat", max(a, 0))


def _shift(width: _Width, op: str, a: int, count: int) -> Outcome:
    valid = count < width.bits
    fill = -1 if a < 0 else 0
    if op in {"shl", "wrap_shl"}:
        return _reduce(width, a * 2 ** count) if valid else 0
    if op == "shr":
        return a // 2 ** count if valid else fill
    if not valid:
        return ("err", "InvalidShift")
    if op == "chk_shl":
        return _checked(width, a * 2 ** count)
    ensure(op == "chk_shr", f"unknown shift operation {op}")
    return ("ok", a // 2 ** count)


def _values(width: _Width) -> list[int]:
    chosen = {0, 1, 2, width.hi, width.hi - 1, width.lo, width.lo + 1, width.hi // 2 + 1, 0x5A}
    if width.signed:
        chosen |= {-1, -2, -0x5A, width.lo // 2}
    return sorted(chosen)


def _kernel_values(width: _Width) -> list[int]:
    chosen = {0, 1, width.hi, width.lo, 0x5A}
    if width.signed:
        chosen |= {-1, -0x5A}
    return sorted(chosen)


def _counts(width: _Width) -> list[int]:
    return sorted({0, 1, width.bits - 1, width.bits, width.bits + 1, _USIZE.hi})


_BINARY = ("add", "sub", "mul", "div", "rem", "and", "or", "xor",
           "wrap_add", "wrap_sub", "wrap_mul", "sat_add", "sat_sub", "sat_mul",
           "chk_add", "chk_sub", "chk_mul", "chk_div", "chk_rem",
           "eq", "ne", "lt", "le", "gt", "ge")
_UNARY = ("neg", "not", "wrap_neg", "sat_neg", "chk_neg", "to_nat")
_SHIFTS = ("shl", "shr", "wrap_shl", "chk_shl", "chk_shr")


@dataclass(frozen=True)
class _Row:
    """One sampled application: the evaluator's constant, its arguments and the
    reference outcome, with the value width of an integer or `Ok` result."""

    name: str
    arguments: tuple[tuple[str, int], ...]
    expected: Outcome
    result: str
    error: str = "vela_ArithmeticError"


def _rows(widths: tuple[str, ...], values: Callable[[_Width], list[int]],
          counts: Callable[[_Width], list[int]]) -> Iterator[_Row]:
    for name in widths:
        width = _WIDTHS[name]
        sample = values(width)
        for op in _BINARY:
            for a, b in itertools.product(sample, sample):
                yield _Row(f"int_{op}_{name}", ((name, a), (name, b)), _binary(width, op, a, b), name)
        for op in _UNARY:
            for a in sample:
                yield _Row(f"int_{op}_{name}", ((name, a),), _unary(width, op, a), name)
        for op in _SHIFTS:
            for a, count in itertools.product(sample, counts(width)):
                yield _Row(f"int_{op}_{name}", ((name, a), ("usize", count)),
                           _shift(width, op, a, count), name)
        for target in widths:
            dst = _WIDTHS[target]
            for a in sample:
                converted = _reduce(dst, a)
                yield _Row(f"int_from_{name}_{target}", ((name, a),), converted, target)
                yield _Row(f"int_try_from_{name}_{target}", ((name, a),),
                           ("ok", a) if _fits(dst, a) else ("err", "OutOfRange"),
                           target, "vela_ConversionError")


def _nat_rows(limit: int) -> Iterator[tuple[str, int, Outcome, str]]:
    for name, width in _WIDTHS.items():
        for n in sorted({0, 1, width.hi, width.hi + 1, 2 * width.hi + 1, 2 ** 64}):
            if n <= limit:
                yield (f"int_try_from_Nat_{name}", n,
                       ("ok", n) if n <= width.hi else ("err", "OutOfRange"), name)


def _scalar(code: int) -> bool:
    return 0 <= code <= _SCALAR_MAX and code not in _SURROGATES


_CODES = (0, 0x41, 0x7F, 0xFF, 0xD7FF, 0xD800, 0xDBFF, 0xDFFF, 0xE000, 0xFFFF,
          0x10000, _SCALAR_MAX, _SCALAR_MAX + 1, 0xFFFFFFFF)


# Static evaluator side.


class _Evaluator:
    """The elaborator's static reducer, with a fresh budget for every application."""

    def __init__(self) -> None:
        self.elaborator = _Elaborator(_Protocol(b"module Primitives;"))

    def run(self, name: str, *arguments: _Term) -> _Term:
        self.elaborator.work = 200_000
        self.elaborator.reductions = 20_000
        return self.elaborator.whnf(_apps(_constant(name), *arguments))

    def decode(self, term: _Term, result: str) -> Outcome:
        if term.kind == "int":
            ensure(term.args[0] == _INT_SPECS[result].const, f"result typed {term.args[0]}, not {result}")
            return cast("int", term.value)
        if term.kind == "bool":
            return bool(term.value)
        if term.kind in {"nat", "char"}:
            return (term.kind, cast("int", term.value))
        head, arguments = self.elaborator.spine(term)
        ensure(head.kind == "const" and len(arguments) == 3, f"irreducible result {term}")
        if head.value == "vela_Result_Ok":
            return ("ok", self.decode(arguments[2], result))
        ensure(head.value == "vela_Result_Err", f"unknown result constructor {head.value}")
        error, _ = self.elaborator.spine(arguments[2])
        return ("err", cast("str", error.value).rsplit("_", 1)[1])


def _disagreements(evaluator: _Evaluator, rows: Iterator[_Row]) -> list[str]:
    found: list[str] = []
    for row in rows:
        terms = [_int_term(_INT_SPECS[name], value) for name, value in row.arguments]
        actual = evaluator.decode(evaluator.run(row.name, *terms), row.result)
        if actual != row.expected:
            found.append(f"{row.name}{tuple(v for _, v in row.arguments)}: "
                         f"expected {row.expected}, got {actual}")
    return found


def _evaluator_rows() -> Iterator[_Row]:
    return _rows(tuple(_WIDTHS), _values, _counts)


def _width_table() -> None:
    for name, width in _WIDTHS.items():
        spec = _INT_SPECS[name]
        ensure((spec.tag, spec.bits, spec.signed, spec.min_val, spec.max_val)
               == (width.tag, width.bits, width.signed, width.lo, width.hi),
               f"{name} specification differs from the contract's range")
    ensure(set(_INT_SPECS) == set(_WIDTHS), "integer specification set changed")


def _evaluator_agrees() -> None:
    found = _disagreements(_Evaluator(), _evaluator_rows())
    ensure(not found, f"{len(found)} evaluator disagreement(s):\n" + "\n".join(found[:20]))


def _evaluator_conversions() -> None:
    evaluator = _Evaluator()
    found: list[str] = []
    for name, n, expected, result in _nat_rows(2 ** 64):
        actual = evaluator.decode(evaluator.run(name, _term("nat", value=n)), result)
        if actual != expected:
            found.append(f"{name}({n}): expected {expected}, got {actual}")
    for src, dst in itertools.product(_WIDTHS.values(), _WIDTHS.values()):
        admitted = _allows_from_conversion(_INT_SPECS[src.name], _INT_SPECS[dst.name])
        if admitted and not (dst.lo <= src.lo and src.hi <= dst.hi):
            found.append(f"From {src.name} -> {dst.name} is admitted but can lose range")
    for code in _CODES:
        u32 = _int_term(_INT_SPECS["u32"], code) if code <= _WIDTHS["u32"].hi else None
        want = ("ok", ("char", code)) if _scalar(code) else ("err", "OutOfRange")
        for name, argument in (("char_try_from_Nat", _term("nat", value=code)),
                               ("char_try_from_u32", u32)):
            if argument is None:
                continue
            actual = evaluator.decode(evaluator.run(name, argument), "u32")
            if actual != want:
                found.append(f"{name}({code:#x}): expected {want}, got {actual}")
        if _scalar(code):
            char = _term("char", value=code)
            for name, want_value in (("char_to_u32", code), ("char_to_nat", ("nat", code))):
                actual = evaluator.decode(evaluator.run(name, char), "u32")
                if actual != want_value:
                    found.append(f"{name}({code:#x}): expected {want_value}, got {actual}")
    for byte in (0, 0x41, 0xFF):
        actual = evaluator.decode(evaluator.run("char_from_u8", _int_term(_INT_SPECS["u8"], byte)), "u8")
        if actual != ("char", byte):
            found.append(f"char_from_u8({byte}): got {actual}")
    for n in (0, 1, _USIZE.hi, _USIZE.hi + 1, 2 ** 64 + 5):
        actual = evaluator.decode(evaluator.run("nat_to_usize", _term("nat", value=n)), "usize")
        if actual != n % 2 ** 64:
            found.append(f"nat_to_usize({n}): got {actual}")
    ensure(not found, f"{len(found)} conversion disagreement(s):\n" + "\n".join(found[:20]))


def _evaluator_contract_rows() -> None:
    """The contract's own named examples, stated once more without the sampler."""
    i8, i32, u8 = _WIDTHS["i8"], _WIDTHS["i32"], _WIDTHS["u8"]
    named = [
        (_binary(i8, "div", -7, 2), -3), (_binary(i8, "rem", -7, 2), -1),
        (_binary(i8, "rem", 7, -2), 1), (_binary(i8, "chk_div", -128, -1), ("err", "Overflow")),
        (_binary(i8, "chk_rem", -128, -1), ("ok", 0)), (_binary(i8, "rem", -128, -1), 0),
        (_binary(i8, "chk_div", -128, 0), ("err", "ZeroDivisor")),
        (_binary(u8, "sat_add", 250, 10), 255), (_unary(i8, "sat_neg", -128), 127),
        (_binary(u8, "wrap_mul", 16, 17), 16), (_shift(i8, "shr", -7, 1), -4),
        (_shift(i32, "chk_shl", 1, 31), ("err", "Overflow")),
        (_shift(i32, "chk_shl", -1, 31), ("ok", -(2 ** 31))),
        (_shift(i32, "chk_shr", 1, 32), ("err", "InvalidShift")),
    ]
    for index, (actual, expected) in enumerate(named):
        ensure(actual == expected, f"reference row {index}: expected {expected}, got {actual}")


def _evaluator_fault_controls() -> None:
    """Removing reduction, clamping or truncation from the evaluator must be detected."""
    def unreduced(_: object, value: int) -> int:
        return value

    def floored(a: int, b: int) -> int:
        return a % b

    for helper, replacement in (("_wrap_int", unreduced), ("_clamp_int", unreduced),
                                ("_trunc_rem", floored)):
        with patch.object(elaborate_whnf, helper, replacement):
            found = _disagreements(_Evaluator(), _evaluator_rows())
        ensure(bool(found), f"replacing the evaluator's {helper} survived the value controls")


# Kernel side.

_NAT = "Corelib.Init.Datatypes.nat"


def _literal(width: _Width, value: int) -> str:
    bits = "vela_bnil"
    pattern = _pattern(width, value)
    for shift in range(0, width.bits, 4):
        bits = f"(vela_x{(pattern >> shift) & 0xF:x} {bits})"
    return f"(@vela_mk_int ({width.tag} : {_NAT}) {bits})"


def _gallina_value(value: object, width: _Width) -> str:
    if isinstance(value, bool):
        return "Corelib.Init.Datatypes.true" if value else "Corelib.Init.Datatypes.false"
    if isinstance(value, int):
        return _literal(width, value)
    kind, payload = cast("tuple[str, int]", value)
    return f"({payload} : {_NAT})" if kind == "nat" else f"(vela_mk_char ({payload} : {_NAT}))"


def _gallina_outcome(expected: Outcome, width: _Width, error: str = "vela_ArithmeticError",
                     value_type: str = "") -> str:
    value_type = value_type or f"(vela_int ({width.tag} : {_NAT}))"
    if isinstance(expected, tuple) and expected[0] in {"ok", "err"}:
        kind, payload = cast("tuple[str, object]", expected)
        if kind == "ok":
            return f"(vela_Result_Ok {value_type} {error} {_gallina_value(payload, width)})"
        return f"(vela_Result_Err {value_type} {error} ({error}_{payload} Corelib.Init.Datatypes.tt))"
    return _gallina_value(expected, width)


def _kernel_rows() -> Iterator[tuple[str, str, str]]:
    """The sampled rows as (evaluator constant, Gallina application, expected term)."""
    for row in _rows(_SAMPLED, _kernel_values,
                     lambda width: [0, 1, width.bits - 1, width.bits, _USIZE.hi]):
        arguments = " ".join(_literal(_WIDTHS[name], value) for name, value in row.arguments)
        yield (row.name, f"({_GALLINA[row.name]} {arguments})",
               _gallina_outcome(row.expected, _WIDTHS[row.result], row.error))
    for name, n, expected, result in _nat_rows(70_000):
        yield (name, f"({_GALLINA[name]} ({n} : {_NAT}))",
               _gallina_outcome(expected, _WIDTHS[result], "vela_ConversionError"))
    u32 = _WIDTHS["u32"]
    for code in _CODES:
        scalar = _scalar(code)
        outcome = ("ok", ("char", code)) if scalar else ("err", "OutOfRange")
        expected = _gallina_outcome(outcome, u32, "vela_ConversionError", "vela_char")
        # A scalar above U+FFFF would make the kernel build its unary code point.
        if code <= 0xFFFF or not scalar:
            yield ("char_try_from_u32", f"({_GALLINA['char_try_from_u32']} {_literal(u32, code)})",
                   expected)
        if code <= 0xFFFF:
            yield ("char_try_from_Nat", f"({_GALLINA['char_try_from_Nat']} ({code} : {_NAT}))",
                   expected)
            if scalar:
                yield ("char_to_u32",
                       f"({_GALLINA['char_to_u32']} (vela_mk_char ({code} : {_NAT})))",
                       _literal(u32, code))
    for n in (0, 1, 255, 65_536):
        yield ("nat_to_usize", f"({_GALLINA['nat_to_usize']} ({n} : {_NAT}))", _literal(_USIZE, n))


def _kernel_file(prelude: str, rows: list[tuple[str, str, str]]) -> str:
    checks = "".join(
        f"Definition vela_primitive_check_{index} : Corelib.Init.Logic.eq {expression} {expected} "
        f":= Corelib.Init.Logic.eq_refl.\n"
        for index, (_, expression, expected) in enumerate(rows))
    return prelude + "\n" + checks


def _compile(directory: Path, name: str, text: str) -> subprocess.CompletedProcess[str]:
    path = directory / f"{name}.v"
    path.write_text(text, encoding="utf-8", newline="\n")
    return subprocess.run([*proofenv.rocq_command(), "-q", path.name], cwd=directory,
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=False, timeout=1800)


def _scratch() -> tempfile.TemporaryDirectory[str]:
    root = Path(__file__).resolve().parents[2]
    lane = env.lane_root(env.lane_of(root)) / "vela-primitives"
    lane.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix="kernel-", dir=lane)


def _kernel_replay() -> None:
    rows = list(_kernel_rows())
    ensure(len(rows) > 5000, f"kernel sample shrank to {len(rows)} rows")
    ensure({name for name, _, _ in rows} >= {f"int_{op}_{width}" for op in (*_BINARY, *_UNARY, *_SHIFTS)
                                             for width in _SAMPLED},
           "kernel sample omits a primitive")
    with _scratch() as temporary:
        done = _compile(Path(temporary), "VelaPrimitives", _kernel_file(_PRELUDE, rows))
    ensure(done.returncode == 0,
           f"locked prover refused the primitive checks: {done.returncode} "
           f"{(done.stdout + done.stderr)[-3000:]}")


# Former placeholders, restored one at a time. Each must leave the prelude
# compiling and fail a sampled check.
_PLACEHOLDERS = {
    "int_mul_": (r"Definition vela_int_mul \(tag : nat\) \(a b : vela_int tag\) : vela_int tag :=\n[^\n]*\n",
                 "Definition vela_int_mul (tag : nat) (a _ : vela_int tag) : vela_int tag := a.\n"),
    "int_lt_": (r"Definition vela_int_lt \(tag : nat\) \(a b : vela_int tag\) : bool :=\n[^\n]*\n",
                "Definition vela_int_lt (tag : nat) (a b : vela_int tag) : bool :=\n"
                "  vela_bits_ult (vela_int_bits tag a) (vela_int_bits tag b).\n"),
    "int_chk_rem_": (r"Definition vela_int_chk_rem \(tag : nat\) \(a b : vela_int tag\)\n(?:  [^\n]*\n)+",
                     "Definition vela_int_chk_rem (tag : nat) (a _ : vela_int tag)\n"
                     "    : vela_Result (vela_int tag) vela_ArithmeticError :=\n"
                     "  vela_Result_Ok (vela_int tag) vela_ArithmeticError a.\n"),
    "char_try_from_u32": (r"Definition vela_char_try_from_u32 \(v : vela_int \(2 : nat\)\)\n(?:  [^\n]*\n)+",
                          "Definition vela_char_try_from_u32 (_ : vela_int (2 : nat))\n"
                          "    : vela_Result vela_char vela_ConversionError :=\n"
                          "  vela_Result_Ok vela_char vela_ConversionError (vela_mk_char O).\n"),
}


def _kernel_fault_controls() -> None:
    """Each restored placeholder is killed by a check, never stillborn in the prelude."""
    prelude_lines = _PRELUDE.count("\n") + 1
    rows = list(_kernel_rows())
    with _scratch() as temporary:
        directory = Path(temporary)
        for index, (prefix, (pattern, placeholder)) in enumerate(_PLACEHOLDERS.items()):
            mutated, replaced = re.subn(pattern, placeholder, _PRELUDE)
            ensure(replaced == 1, f"{prefix} placeholder control no longer matches the prelude")
            selected = [row for row in rows if row[0].startswith(prefix)]
            ensure(bool(selected), f"{prefix} placeholder control selected no checks")
            done = _compile(directory, f"Mutant{index}", _kernel_file(mutated, selected))
            output = done.stdout + done.stderr
            line = re.search(r"line (\d+)", output)
            ensure(done.returncode != 0, f"{prefix} placeholder survived the kernel checks")
            ensure(line is not None and int(line[1]) > prelude_lines,
                   f"{prefix} placeholder was stillborn rather than killed: {output[-2000:]}")


def cases() -> list[Case]:
    return [Case("vela-primitive-widths-match-the-contract-ranges", _width_table),
            Case("vela-primitive-reference-named-contract-rows", _evaluator_contract_rows),
            Case("vela-primitive-static-evaluator-matches-the-reference", _evaluator_agrees),
            Case("vela-primitive-static-conversions-and-char-scalars", _evaluator_conversions),
            Case("vela-primitive-static-evaluator-fault-controls", _evaluator_fault_controls),
            Case("vela-primitive-gallina-kernel-replay", _kernel_replay, lane="toolchain"),
            Case("vela-primitive-gallina-placeholder-controls", _kernel_fault_controls,
                 lane="toolchain")]
