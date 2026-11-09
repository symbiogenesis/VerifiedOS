# SPDX-License-Identifier: Apache-2.0
"""Lazy JSON Schema validation with Python integers and caller-owned schemas."""

import json
from collections.abc import Iterator, Mapping
from functools import cache, lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

from vos.jsonutil import unique_object

if TYPE_CHECKING:
    from jsonschema.protocols import Validator


class _RsValidator(Protocol):
    def is_valid(self, instance: object) -> bool: ...


def _is_integer(checker: object, value: object) -> bool:
    return type(value) is int


def _has_float(value: object) -> bool:
    """True when `value` contains a Python `float` that standard JSON Schema could coerce to `integer`."""
    stack = [value]
    while stack:
        current = stack.pop()
        if type(current) is float:
            return True
        if isinstance(current, dict):
            stack.extend(current.values())
        elif isinstance(current, (list, tuple)):
            stack.extend(current)
    return False


def _has_external_ref(schema: object) -> bool:
    """True when `schema` contains a non-fragment `$ref` requiring offline Registry refusal."""
    stack = [schema]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            ref = current.get("$ref")
            if isinstance(ref, str) and not ref.startswith("#"):
                return True
            stack.extend(current.values())
        elif isinstance(current, (list, tuple)):
            stack.extend(current)
    return False


@lru_cache(maxsize=64)
def _rs_for_text(schema_json: str) -> _RsValidator | None:
    import jsonschema_rs  # noqa: PLC0415

    parsed = json.loads(schema_json)
    if not isinstance(parsed, dict) or _has_external_ref(parsed):
        return None
    try:
        return cast("_RsValidator", jsonschema_rs.validator_for(parsed, validate_formats=False))
    except Exception:
        return None


def _rs_for_schema(schema: object) -> _RsValidator | None:
    if not isinstance(schema, Mapping) or _has_external_ref(schema):
        return None
    try:
        key = json.dumps(schema, sort_keys=True, separators=(",", ":"))
    except TypeError, ValueError:
        return None
    return _rs_for_text(key)


@cache
def _validator_class() -> type[Validator]:
    # Ring declarations are also imported by lightweight corpus readers.
    from jsonschema import Draft202012Validator, validators  # noqa: PLC0415

    checker = Draft202012Validator.TYPE_CHECKER.redefine("integer", _is_integer)
    base = validators.extend(Draft202012Validator, type_checker=checker)

    class _FastStrictValidator(base):  # type: ignore[valid-type,misc]
        def iter_errors(self, instance: object, _schema: object = None) -> Iterator[Any]:
            if _schema is None and not _has_float(instance):
                rs = _rs_for_schema(self.schema)
                if rs is not None and rs.is_valid(instance):
                    return iter(())
            if _schema is not None:
                return super().iter_errors(instance, _schema)
            return super().iter_errors(instance)

        def is_valid(self, instance: object, _schema: object = None) -> bool:
            if _schema is None and not _has_float(instance):
                rs = _rs_for_schema(self.schema)
                if rs is not None:
                    return bool(rs.is_valid(instance))
            if _schema is not None:
                return bool(super().is_valid(instance, _schema))
            return bool(super().is_valid(instance))

    return _FastStrictValidator


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


@lru_cache(maxsize=64)
def _compiled_authored_schema(raw_text: str) -> tuple[Validator, _RsValidator | None]:
    from referencing import Registry  # noqa: PLC0415

    schema = json.loads(raw_text, object_pairs_hook=unique_object)
    validator = _validator_class()
    validator.check_schema(schema)
    bound = validator(schema, registry=Registry())
    rs = _rs_for_schema(schema) if isinstance(schema, dict) else None
    return bound, rs


def validate(schema_path: Path, value: object) -> None:
    """Validate against an authored schema; unreadable or invalid owners refuse.

    Dependencies remain lazy for readers that only import this module. Every
    finding names its schema and the JSON path within the supplied value. Local
    references are supported; an empty retrieval registry keeps validation offline.
    """
    from jsonschema.exceptions import SchemaError  # noqa: PLC0415
    from referencing.exceptions import Unresolvable  # noqa: PLC0415

    try:
        raw_text = schema_path.read_text(encoding="utf-8")
        bound, rs = _compiled_authored_schema(raw_text)
        if rs is not None and not _has_float(value) and rs.is_valid(value):
            return
        errors = sorted(bound.iter_errors(value), key=lambda error: error.json_path)
    except (OSError, ValueError, SchemaError, Unresolvable) as error:
        raise ValueError(f"{schema_path}: cannot read a valid schema: {error}") from error
    if errors:
        raise ValueError(f"{schema_path}: " + "; ".join(
            f"{error.json_path}: {error.message}" for error in errors))
