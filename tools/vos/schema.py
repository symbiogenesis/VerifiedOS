# SPDX-License-Identifier: Apache-2.0
"""Lazy JSON Schema validation with Python integers and caller-owned schemas."""

import json
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vos.jsonutil import unique_object

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


def validate(schema_path: Path, value: object) -> None:
    """Validate against an authored schema; unreadable or invalid owners refuse.

    Dependencies remain lazy for readers that only import this module. Every
    finding names its schema and the JSON path within the supplied value.
    """
    from jsonschema.exceptions import SchemaError  # noqa: PLC0415

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"),
                            object_pairs_hook=unique_object)
        validator = strict_integer_validator(schema, check_schema=True)
    except (OSError, ValueError, SchemaError) as error:
        raise ValueError(f"{schema_path}: cannot read a valid schema: {error}") from error
    errors = sorted(validator.iter_errors(value), key=lambda error: error.json_path)
    if errors:
        raise ValueError(f"{schema_path}: " + "; ".join(
            f"{error.json_path}: {error.message}" for error in errors))
