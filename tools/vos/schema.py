# SPDX-License-Identifier: Apache-2.0
"""Lazy JSON Schema validation with Python integers and caller-owned schemas."""

from collections.abc import Mapping
from functools import cache
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from jsonschema.protocols import Validator


def _is_integer(checker: object, value: object) -> bool:
    return type(value) is int


@cache
def _validator_class() -> type[Validator]:
    # Ring declarations are also imported by lightweight corpus readers.
    from jsonschema import Draft202012Validator, validators  # noqa: PLC0415

    checker = Draft202012Validator.TYPE_CHECKER.redefine("integer", _is_integer)
    return validators.extend(Draft202012Validator, type_checker=checker)


def strict_integer_validator(schema: Mapping[str, Any] | bool, *,
                             check_schema: bool = False) -> Validator:
    """Build a validator without coercion; callers choose schema self-validation.

    JSON Schema normally accepts integral floats as integers. Generated Gallina
    and C consumers require actual Python integers; booleans also remain distinct.
    Each call binds its own schema, while the validator class is shared lazily.
    """
    validator = _validator_class()
    if check_schema:
        validator.check_schema(schema)
    return validator(schema)
