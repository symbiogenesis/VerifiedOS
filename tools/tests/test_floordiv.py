# SPDX-License-Identifier: Apache-2.0
"""Generated exact-division comparisons and independent encoded RV64 arithmetic."""

import json
from collections.abc import Callable
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
from typing import override

from tests.harness import Case, ensure
from vos import asm
from vos.cli import floor_div as cli
from vos.floordiv import Plan, assembly, evaluate, plan, validate

_MASK = (1 << 64) - 1


def _raises(kind: type[Exception], action: Callable[[], object], fragment: str) -> None:
    try:
        action()
    except kind as error:
        ensure(fragment in str(error), f"missing {fragment!r} from {error}")
        return
    raise AssertionError(f"expected {kind.__name__}: {fragment}")


def _random_words(width: int, count: int) -> list[int]:
    """A fixed test sequence; no entropy, host state or cryptographic use."""
    state = 0xD1701DE
    result: list[int] = []
    for _ in range(count):
        state = (6364136223846793005 * state + 1442695040888963407) & _MASK
        word = state & ((1 << width) - 1)
        result.append(word - (1 << width) if word >> (width - 1) else word)
    return result


def _divisors(width: int) -> list[int]:
    half = 1 << (width - 1)
    values = {1, -1, -half, half - 1}
    for bit in range(width - 1):
        for delta in (-1, 0, 1):
            for sign in (-1, 1):
                values.add(sign * ((1 << bit) + delta))
    for magnitude in (3, 5, 6, 7, 9, 14, 17, 49, 73, 127, 337, 511, 100, 86400):
        values.update((magnitude, -magnitude))
    for endpoint in (half - 1, half + 1):
        for factor in range(1, 65):
            if endpoint % factor == 0:
                for delta in (-1, 0, 1):
                    magnitude = endpoint // factor + delta
                    values.update((magnitude, -magnitude))
    values.update(_random_words(width, 96))
    return sorted(value for value in values if -half <= value < half and value != 0)


def _values(width: int, divisor: int) -> list[int]:
    half = 1 << (width - 1)
    values = {-half, -half + 1, -half + 2, half - 1, half - 2, -2, -1, 0, 1, 2}
    # Exact multiples and neighbors around both extrema and around the origin.
    for quotient in (-half // divisor, (half - 1) // divisor, -2, -1, 0, 1, 2):
        for step in (-1, 0, 1):
            multiple = (quotient + step) * divisor
            values.update((multiple - 1, multiple, multiple + 1))
    values.update(_random_words(width, 64))
    return sorted(value for value in values if -half <= value < half)


def _exhaustive_small() -> None:
    modes: set[str] = set()
    for divisor in range(-128, 128):
        if divisor == 0:
            continue
        parameters = plan(8, divisor)
        modes.add(parameters.mode)
        for value in range(-128, 128):
            if value == -128 and divisor == -1:
                _raises(OverflowError, lambda parameters=parameters, value=value:
                        evaluate(parameters, value), "INT_MIN")
                continue
            got = evaluate(parameters, value)
            ensure(got == value // divisor,
                   f"8-bit {value}//{divisor}: {parameters} gave {got}")
    ensure(modes == {"power-of-two", "sign-selected", "round-up", "round-down"},
           f"small exhaustion missed a variant: {modes}")


def _wider_samples() -> None:
    for width in (16, 32, 64):
        modes: set[str] = set()
        for divisor in _divisors(width):
            parameters = plan(width, divisor)
            ensure(parameters == plan(width, divisor), "planner is not deterministic")
            modes.add(parameters.mode)
            for value in _values(width, divisor):
                if value == -(1 << (width - 1)) and divisor == -1:
                    _raises(OverflowError, lambda parameters=parameters, value=value:
                            evaluate(parameters, value), "INT_MIN")
                    continue
                got = evaluate(parameters, value)
                ensure(got == value // divisor,
                       f"{width}-bit {value}//{divisor}: {parameters} gave {got}")
        ensure(modes == {"power-of-two", "sign-selected", "round-up", "round-down"},
               f"{width}-bit samples missed a variant: {modes}")


def _sext(value: int, width: int) -> int:
    value &= (1 << width) - 1
    return value - (1 << width) if value >> (width - 1) else value


def _execute(code: bytes, value: int) -> int:
    """Decode emitted bytes directly; unknown instructions fail closed.

    This deliberately does not use dialect encoding tables, planner helpers or
    assembler pseudo expansion. It covers only these fragments' RV64 integer
    operations, not capabilities, control flow, memory or timing.
    """
    ensure(len(code) % 4 == 0 and 0 < len(code) <= 256,
           "fragment must be nonempty, bounded and canonically word-sized")
    regs = [(0x9E3779B97F4A7C15 * number) & _MASK for number in range(32)]
    regs[0], regs[10] = 0, value & _MASK
    initial = list(regs)
    for offset in range(0, len(code), 4):
        instruction = int.from_bytes(code[offset:offset + 4], "little")
        opcode = instruction & 127
        destination = (instruction >> 7) & 31
        function = (instruction >> 12) & 7
        source = (instruction >> 15) & 31
        other = (instruction >> 20) & 31
        upper = instruction >> 25
        immediate = _sext(instruction >> 20, 12)
        left, right = regs[source], regs[other]
        result: int
        if opcode == 0x37:
            result = _sext(instruction & 0xFFFFF000, 32)
        elif opcode == 0x1B and function == 0:
            result = _sext(left + immediate, 32)
        elif opcode == 0x13 and function == 0:
            result = left + immediate
        elif opcode == 0x13 and function == 1 and instruction >> 26 == 0:
            result = left << ((instruction >> 20) & 63)
        elif opcode == 0x13 and function == 5 and instruction >> 26 == 0x10:
            result = _sext(left, 64) >> ((instruction >> 20) & 63)
        elif opcode == 0x33 and upper == 0 and function == 0:
            result = left + right
        elif opcode == 0x33 and upper == 0x20 and function == 0:
            result = left - right
        elif opcode == 0x33 and upper == 0 and function == 7:
            result = left & right
        elif opcode == 0x33 and upper == 0 and function == 2:
            result = int(_sext(left, 64) < _sext(right, 64))
        elif opcode == 0x33 and upper == 0 and function == 3:
            result = int(left < right)
        elif opcode == 0x33 and upper == 1 and function == 1:
            result = (_sext(left, 64) * _sext(right, 64)) >> 64
        else:
            raise ValueError(f"unknown instruction {instruction:#010x}")
        ensure(destination in (5, 6, 7, 10), f"unexpected clobber x{destination}")
        regs[destination] = result & _MASK
    for number in range(32):
        if number not in (5, 6, 7, 10):
            ensure(regs[number] == initial[number], f"changed preserved register x{number}")
    return _sext(regs[10], 64)


def _encoded(source: str) -> bytes:
    sections, _, _ = asm.Assembler(".text\n_start:\n" + source, "floor-div.s").assemble()
    ensure(not sections[1].data, "fragment introduced data")
    return bytes(sections[0].data)


def _assembly_samples() -> None:
    modes: set[str] = set()
    for divisor in _divisors(64):
        if divisor == -1:
            continue
        parameters = plan(64, divisor)
        modes.add(parameters.mode)
        code = _encoded(assembly(parameters))
        for value in _values(64, divisor):
            got = _execute(code, value)
            ensure(got == value // divisor,
                   f"RV64 {value}//{divisor}: {parameters} gave {got}")
    ensure(modes == {"power-of-two", "sign-selected", "round-up", "round-down"},
           "assembly samples missed a variant")
    _raises(ValueError, lambda: _execute(b"\x73\x00\x00\x00", 0), "unknown instruction")


def _invalid_and_mutants() -> None:
    class ForgedPlan(Plan):
        @override
        def __eq__(self, other: object) -> bool:
            return True

        @override
        def __hash__(self) -> int:
            return 0

    forged = ForgedPlan(64, 3, "sign-selected", 0, 64)
    _raises(TypeError, lambda: validate(forged), "exactly a Plan")
    _raises(TypeError, lambda: evaluate(forged, 3), "exactly a Plan")
    _raises(TypeError, lambda: assembly(forged), "exactly a Plan")
    for width in (0, 7, 128, True):
        _raises(ValueError, lambda width=width: plan(width, 1), "width")
    for divisor in (0, -129, 128, True):
        _raises(ValueError, lambda divisor=divisor: plan(8, divisor),
                "nonzero" if divisor == 0 else "divisor")
    original = plan(64, 3)
    for mutant in (replace(original, multiplier=original.multiplier + 1),
                   replace(original, shift=original.shift + 1),
                   replace(original, mode="round-down"),
                   replace(original, mode="unknown"),
                   replace(original, shift=True), replace(original, width=True)):
        _raises(ValueError, lambda mutant=mutant: validate(mutant),
                "width" if mutant.width is True else "canonical")
        _raises(ValueError, lambda mutant=mutant: evaluate(mutant, 1),
                "width" if mutant.width is True else "canonical")
        _raises(ValueError, lambda mutant=mutant: assembly(mutant),
                "width" if mutant.width is True else "canonical")
    for value in (-(1 << 63) - 1, 1 << 63, True):
        _raises(ValueError, lambda value=value: evaluate(original, value), "dividend")
    # Frozen records can still be changed with object.__setattr__; they must
    # neither become their own validation oracle nor contaminate later plans.
    damaged = plan(64, 3)
    object.__setattr__(damaged, "multiplier", damaged.multiplier + 1)
    _raises(ValueError, lambda: validate(damaged), "canonical")
    _raises(ValueError, lambda: evaluate(damaged, 3), "canonical")
    _raises(ValueError, lambda: assembly(damaged), "canonical")
    fresh = plan(64, 3)
    ensure(fresh == original and fresh is not original and fresh is not damaged,
           "caller mutation contaminated a later plan")
    ensure(evaluate(fresh, -3) == -1 and _execute(_encoded(assembly(fresh)), -3) == -1,
           "fresh arithmetic did not recover after caller mutation")
    _raises(ValueError, lambda: assembly(plan(8, 3)), "width 64")
    _raises(ValueError, lambda: assembly(plan(64, -1)), "overflow contract")
    _raises(OverflowError, lambda: evaluate(plan(64, -1), -(1 << 63)), "INT_MIN")
    # Removing the positive saturating correction must produce a wrong result.
    corrected = assembly(plan(64, 5))
    ensure("add x10, x10, x6\n" in corrected, "control no longer mutates a correction")
    mutant_code = _encoded(corrected.replace("add x10, x10, x6\n", ""))
    ensure(_execute(mutant_code, 5) != 5 // 5, "missing-correction mutant survived")
    # Reversing the sign-selected adjustment must also produce an actual witness.
    selected = assembly(original)
    ensure("add x5, x5, x6\n" in selected, "control no longer mutates sign selection")
    mutant_code = _encoded(selected.replace("add x5, x5, x6", "sub x5, x5, x6"))
    ensure(_execute(mutant_code, -3) != -3 // 3, "wrong-sign mutant survived")


def _cli() -> None:
    with redirect_stdout(output := StringIO()):
        code = cli.main(["--width", "64", "--divisor", "3", "--value", "-7",
                         "--value", "7"])
    report = json.loads(output.getvalue())
    ensure(code == 0 and report["target_adoption"] == "open", "CLI hid developer scope")
    ensure(report["results"] == [{"value": -7, "quotient": -3},
                                 {"value": 7, "quotient": 2}], "CLI did not floor")
    with redirect_stdout(output := StringIO()):
        code = cli.main(["--width", "64", "--divisor", "-8", "--assembly"])
    ensure(code == 0 and _execute(_encoded(output.getvalue()), -(1 << 63)) == 1 << 60,
           "CLI assembly did not preserve the negative-power endpoint")
    for arguments, fragment in ((["--width", "64", "--divisor", "0"], "nonzero"),
                                (["--width", "64", "--divisor", "-1", "--value",
                                  str(-(1 << 63))], "INT_MIN"),
                                (["--width", "16", "--divisor", "3", "--assembly"],
                                 "width 64")):
        with redirect_stdout(output := StringIO()):
            code = cli.main(arguments)
        ensure(code == 1 and fragment in output.getvalue(), f"CLI did not refuse {arguments}")


def cases() -> list[Case]:
    return [Case("exhaustive-small", _exhaustive_small), Case("wider-samples", _wider_samples),
            Case("encoded-rv64-samples", _assembly_samples),
            Case("invalid-and-mutants", _invalid_and_mutants), Case("cli", _cli)]
