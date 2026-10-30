# SPDX-License-Identifier: Apache-2.0
# Portions adapted from Ben Joffe's fastdiv, Copyright (c) 2026 Ben Joffe.
# Upstream MIT notice: tools/fast-floordiv/LICENSE.md.
"""Checked constant floor-division parameters and experimental RV64 arithmetic.

The reciprocal search and correction variants adapt Ben Joffe's algorithm:
https://github.com/benjoffe/fastdiv/blob/608fda7a6ea7322a55b9fb848be5ab252a341194/algorithms/benjoffe.hpp
Host-independent selection replaces its architecture-specific preferences.
Python integers model exact double-width products, never wrapping signed values.
"""

from dataclasses import dataclass
from functools import cache
from typing import Literal

type Mode = Literal["power-of-two", "sign-selected", "round-up", "round-down"]


@dataclass(frozen=True)
class Plan:
    """A checked arithmetic candidate, not a compiler or timing certificate."""

    width: int
    divisor: int
    mode: Mode
    multiplier: int
    shift: int


def _limits(width: int) -> tuple[int, int]:
    if type(width) is not int or width not in (8, 16, 32, 64):
        raise ValueError("width must be 8, 16, 32 or 64")
    half = 1 << (width - 1)
    return -half, half - 1


def _word(value: int, low: int, high: int, role: str) -> None:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{role} must be a signed word in [{low}, {high}]")


def _candidate(width: int, divisor: int, upward: bool, shift: int) -> tuple[int, int] | None:
    """Qualify at the worst numerator, including the strict INT_MIN endpoint."""
    half = 1 << (width - 1)
    magnitude = abs(divisor)
    top = half + (divisor < 0)
    upper_bound = top // magnitude * magnitude - 1
    down_multiple = half // magnitude * magnitude + 1
    lower_bound = down_multiple - (divisor < 0 and down_multiple == half)
    bound = upper_bound if upward else lower_bound
    scale = 1 << shift
    quotient, remainder = divmod(scale, magnitude)
    multiplier = quotient + upward
    error = magnitude - remainder if upward else remainder
    if multiplier < half and scale > bound * error:
        return multiplier, shift
    return None


def _search(width: int, divisor: int, upward: bool) -> tuple[int, int] | None:
    for shift in range(width, 2 * width):
        candidate = _candidate(width, divisor, upward, shift)
        if candidate is not None:
            return candidate
    return None


@cache
def _planned(width: int, divisor: int) -> Plan:
    magnitude = abs(divisor)
    if magnitude & (magnitude - 1) == 0:
        return Plan(width, divisor, "power-of-two", 0, magnitude.bit_length() - 1)
    upward = _search(width, divisor, True)
    downward = _search(width, divisor, False)
    sign = -1 if divisor < 0 else 1
    if upward is None and downward is None:
        raise ValueError("no qualified signed reciprocal candidate")
    if upward is None or (downward is not None and downward[1] == width
                          and upward[1] != width):
        if downward is None:
            raise ValueError("missing downward candidate")
        return Plan(width, divisor, "round-down", sign * downward[0], downward[1])
    if downward is None or (upward[1] == width and downward[1] != width):
        return Plan(width, divisor, "round-up", sign * upward[0], upward[1])
    shift = max(upward[1], downward[1])
    if (_candidate(width, divisor, True, shift) is None
            or _candidate(width, divisor, False, shift) is None):
        raise ValueError("sign-selected common shift failed qualification")
    multiplier = sign * ((1 << shift) // magnitude + (divisor > 0))
    low, high = _limits(width)
    if not low <= multiplier - 1 <= multiplier <= high:
        raise ValueError("sign-selected multipliers do not fit the signed word")
    return Plan(width, divisor, "sign-selected", multiplier, shift)


def plan(width: int, divisor: int) -> Plan:
    """Select parameters using exact worst-case inequalities, never sample search."""
    low, high = _limits(width)
    _word(divisor, low, high, "divisor")
    if divisor == 0:
        raise ValueError("divisor must be nonzero")
    return _planned(width, divisor)


def validate(parameters: Plan) -> None:
    """Refuse caller-constructed parameter changes before arithmetic or emission."""
    if not isinstance(parameters, Plan):
        raise TypeError("parameters must be a Plan")
    if (type(parameters.multiplier) is not int or type(parameters.shift) is not int
            or type(parameters.mode) is not str
            or parameters != plan(parameters.width, parameters.divisor)):
        raise ValueError("parameters differ from the qualified canonical plan")


def evaluate(parameters: Plan, value: int) -> int:
    """Compute floor(value/divisor) or refuse an input/representability failure."""
    validate(parameters)
    low, high = _limits(parameters.width)
    _word(value, low, high, "dividend")
    if value == low and parameters.divisor == -1:
        raise OverflowError("INT_MIN / -1 is not representable")
    if parameters.mode == "power-of-two":
        quotient = value >> parameters.shift
        if parameters.divisor > 0:
            return quotient
        return -quotient - int(bool(value & ((1 << parameters.shift) - 1)))
    if parameters.mode == "sign-selected":
        multiplier = parameters.multiplier + (value >> (parameters.width - 1))
        return (value * multiplier) >> parameters.shift
    if parameters.mode == "round-up":
        correction = value > 1 if parameters.divisor < 0 else value < -1
    else:
        unsigned = value & ((1 << parameters.width) - 1)
        half = 1 << (parameters.width - 1)
        correction = unsigned > half if parameters.divisor < 0 else unsigned < half - 1
    adjusted = value - correction if parameters.divisor < 0 else value + correction
    return (adjusted * parameters.multiplier) >> parameters.shift


def assembly(parameters: Plan) -> str:
    """Emit RV64 arithmetic in integer temporaries, clobbering their capability tags.

    x10 is input/output; x5/x6/x7 are scratch. None may carry live capabilities.
    This is a branch-free arithmetic candidate, not an admitted target function.
    """
    validate(parameters)
    if parameters.width != 64:
        raise ValueError("assembly requires width 64")
    if parameters.divisor == -1:
        raise ValueError("assembly for -1 needs a caller-level checked overflow contract")
    lines = ["# Experimental arithmetic fragment; no target proof or timing verdict.",
             "# Integer input/result x10; scratch x5, x6, x7; capability tags clobbered."]
    shift = parameters.shift
    if parameters.mode == "power-of-two":
        if parameters.divisor > 0:
            lines.append(f"srai x10, x10, {shift}")
        else:
            lines.extend([f"li x5, {(1 << shift) - 1}", "and x5, x10, x5",
                          "sltu x5, x0, x5", f"srai x10, x10, {shift}",
                          "sub x10, x0, x10", "sub x10, x10, x5"])
        return "\n".join(lines) + "\n"
    lines.append(f"li x5, {parameters.multiplier}")
    if parameters.mode == "sign-selected":
        lines.extend(["srai x6, x10, 63", "add x5, x5, x6"])
    elif parameters.mode == "round-up":
        if parameters.divisor > 0:
            lines.extend(["addi x7, x0, -1", "slt x6, x10, x7", "add x10, x10, x6"])
        else:
            lines.extend(["addi x7, x0, 1", "slt x6, x7, x10", "sub x10, x10, x6"])
    elif parameters.divisor > 0:
        lines.extend([f"li x7, {(1 << 63) - 1}", "sltu x6, x10, x7", "add x10, x10, x6"])
    else:
        lines.extend([f"li x7, {-(1 << 63)}", "sltu x6, x7, x10", "sub x10, x10, x6"])
    lines.append("mulh x10, x10, x5")
    if shift > 64:
        lines.append(f"srai x10, x10, {shift - 64}")
    return "\n".join(lines) + "\n"
