# SPDX-License-Identifier: Apache-2.0
"""Duplicate-field policy shared by the memory-planner JSON readers."""

from vos import jsonutil


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Retain member order and the planner's duplicate-field diagnostic."""
    return jsonutil.unique_object(pairs, duplicate_error=lambda key: ValueError(f"duplicate JSON field: {key}"))
