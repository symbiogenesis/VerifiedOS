# SPDX-License-Identifier: Apache-2.0
"""Shared JSON decoder hooks; each caller chooses its numeric and shape policy."""

import math


def unique_object[T](pairs: list[tuple[str, T]]) -> dict[str, T]:
    """Keep member order and reject the first repeated key, at any object depth."""
    result: dict[str, T] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def finite_float(value: str) -> float:
    """Reject finite JSON spellings that overflow the host float representation."""
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"JSON number exceeds finite precision: {value}")
    return parsed
