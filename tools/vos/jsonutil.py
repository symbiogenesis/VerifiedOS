# SPDX-License-Identifier: Apache-2.0
"""Shared JSON decoder hooks; each caller chooses its numeric and shape policy."""

import math
from collections.abc import Callable


def unique_object[T](pairs: list[tuple[str, T]], *,
                     duplicate_error: Callable[[str], Exception] | None = None) -> dict[str, T]:
    """Keep member order and reject repeats, with the caller's diagnostic if supplied."""
    result: dict[str, T] = {}
    for key, value in pairs:
        if key in result:
            if duplicate_error is not None:
                raise duplicate_error(key)
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def finite_float(value: str) -> float:
    """Reject finite JSON spellings that overflow the host float representation."""
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"JSON number exceeds finite precision: {value}")
    return parsed
