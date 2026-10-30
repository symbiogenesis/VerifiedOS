# SPDX-License-Identifier: Apache-2.0
"""Strict integer boundaries, schema policy and lightweight import behavior."""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from jsonschema.exceptions import SchemaError

from tests.harness import Case, ensure
from vos.schema import strict_integer_validator, validate


def _integer_values() -> None:
    validator = strict_integer_validator({
        "type": "object", "properties": {
            "items": {"type": "array", "items": {"type": "integer"}},
            "enabled": {"type": "boolean"}}, "required": ["items", "enabled"]},
        check_schema=True)
    # Generate related integer and float spellings through the real JSON decoder.
    spellings = ["true", "false", "null", '"1"', "[]", "{}"]
    for number in range(-3, 4):
        spellings.extend((str(number), f"{number}.0", f"{number}.5", f"{number}e0"))
    spellings.extend((str(2 ** 128), str(-(2 ** 128))))
    for spelling in spellings:
        value = json.loads(spelling)
        errors = list(validator.iter_errors({"items": [0, value], "enabled": True}))
        expected = spelling.lstrip("-").isdigit()
        ensure(bool(errors) != expected, f"wrong strict-integer decision for {spelling}")
        if errors:
            ensure(errors[0].json_path == "$.items[1]", "nested diagnostic path changed")
    ensure(not validator.is_valid({"items": [1], "enabled": 1}),
           "integer policy must preserve boolean validation")


def _caller_schema_policy() -> None:
    invalid = {"type": "invented-type"}
    strict_integer_validator(invalid)
    try:
        strict_integer_validator(invalid, check_schema=True)
    except SchemaError:
        pass
    else:
        raise AssertionError("requested schema self-validation was skipped")
    # Constants are a caller-owned policy: JSON Schema equates 1 and 1.0 here.
    ensure(strict_integer_validator({"const": 1}).is_valid(1.0),
           "integer consolidation changed const semantics")
    ensure(strict_integer_validator(True).is_valid(None), "true schema changed")
    ensure(not strict_integer_validator(False).is_valid(None), "false schema changed")
    errors = list(strict_integer_validator({
        "properties": {"second": {"type": "integer"}, "first": {"type": "integer"}}
    }).iter_errors({"first": False, "second": 1.0}))
    ensure([error.json_path for error in errors] == ["$.second", "$.first"],
           "caller schema diagnostic order changed")


def _lazy_import() -> None:
    done = subprocess.run(
        [sys.executable, "-c", "import sys; import vos.schema; "
         "raise SystemExit(any(n == 'jsonschema' or n.startswith('jsonschema.') "
         "for n in sys.modules))"], capture_output=True, text=True, check=False,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1])})
    ensure(done.returncode == 0, f"schema helper eagerly loads jsonschema: {done.stderr}")


def _authored_schema() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-schema-") as directory:
        path = Path(directory) / "policy.schema.json"
        path.write_text(json.dumps({
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object", "required": ["count"], "additionalProperties": False,
            "properties": {"count": {"type": "integer"}}}), encoding="utf-8")
        validate(path, {"count": 1})
        for value in ({"count": True}, {"count": 1.0}, {"count": 1.5}, {},
                      {"count": 1, "extra": 2}):
            try:
                validate(path, value)
            except ValueError as error:
                ensure(str(path) in str(error) and "$" in str(error),
                       f"a finding lost its schema or data path: {error}")
            else:
                raise AssertionError(f"authored schema admitted {value!r}")
        for contents in (None, "{", '{"type":"object","type":"array"}',
                         '{"type":"unknown"}', "null", "[]", "\ufffd",
                         '{"$ref":"#/$defs/missing"}',
                         '{"$ref":"https://example.invalid/unavailable.schema.json"}'):
            if contents is None:
                path.unlink()
            else:
                path.write_text(contents, encoding="utf-8")
            try:
                validate(path, {})
            except ValueError as error:
                ensure(str(path) in str(error) and "cannot read a valid schema" in str(error),
                       f"malformed owner diagnostic lost context: {error}")
            else:
                raise AssertionError(f"schema owner did not refuse {contents!r}")
        path.write_text('false', encoding="utf-8")
        try:
            validate(path, {})
        except ValueError as error:
            ensure("$: False schema" in str(error)
                   and "cannot read a valid schema" not in str(error),
                   f"a false schema must produce an ordinary data finding: {error}")
        else:
            raise AssertionError("a false schema admitted data")
        path.write_text('{"$defs":{"count":{"type":"integer"}},'
                        '"$ref":"#/$defs/count"}', encoding="utf-8")
        validate(path, 1)


def cases() -> list[Case]:
    return [Case("generated-strict-integer-values", _integer_values),
            Case("caller-schema-policy-and-diagnostics", _caller_schema_policy),
            Case("authored-schema-refusals", _authored_schema),
            Case("lazy-jsonschema-import", _lazy_import)]
