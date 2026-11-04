# SPDX-License-Identifier: Apache-2.0
"""Isolated compiler worker for the local browser playground."""

import hashlib
import sys
from pathlib import Path
from typing import cast

from vos.protocol_json import MAX_BODY_BYTES, decode_message, encode_message
from vos.vela import ValueType, VelaError, evaluate, translate
from vos.vela_authoring import lint_source, preview_bindings


def compile_request(request: dict[str, object], *,
                    mathematical_parser: Path | None = None) -> dict[str, object]:
    source = cast("str", request["source"]).encode("utf-8")
    digest = hashlib.sha256(source).hexdigest()
    try:
        if request.get("mode") == "mathematical":
            from vos import vela_mathematical
            if mathematical_parser is None or request["action"] not in {"compile", "evaluate"}:
                raise VelaError("unsupported", 1, 1, "Mathematical compiler unavailable")
            if request["action"] == "compile":
                compiled_math = vela_mathematical.compile_source(source, mathematical_parser)
                return {"ok": True, "sourceHash": digest,
                        "module": compiled_math.module, "gallina": compiled_math.gallina}
            result_math = vela_mathematical.evaluate_source(
                source, cast("str", request["expression"]),
                cast("ValueType", request["valueType"]), mathematical_parser)
            value_math = (("true" if result_math.value else "false")
                          if result_math.value_type == "bool" else str(result_math.value))
            return {"ok": True, "sourceHash": digest,
                    "valueType": result_math.value_type, "value": value_math}
        if request.get("mode", "pure") != "pure":
            raise VelaError("unsupported", 1, 1, "Unknown compiler mode")
        if request["action"] == "compile":
            compiled = translate(source)
            return {"ok": True, "sourceHash": digest,
                    "module": compiled.module, "gallina": compiled.gallina}
        if request["action"] == "authoring":
            findings = lint_source(source)
            preview = preview_bindings(source)
            return {"ok": True, "sourceHash": digest,
                    "findings": [{"code": finding.code, "message": finding.message,
                                  "line": finding.line, "column": finding.column}
                                 for finding in findings],
                    "bindingPreview": preview.decode("utf-8")}
        result = evaluate(source, cast("str", request["expression"]),
                          cast("ValueType", request["valueType"]))
        value = ("true" if result.value else "false") if result.value_type == "bool" else str(result.value)
    except VelaError as error:
        return {"ok": False, "sourceHash": digest,
                "error": {"kind": error.kind, "message": error.message,
                          "line": error.line, "column": error.column}}
    return {"ok": True, "sourceHash": digest, "valueType": result.value_type, "value": value}


def main(*, mathematical_parser: Path | None = None, parser_sha256: str | None = None) -> int:
    try:
        if (mathematical_parser is not None
                and hashlib.sha256(mathematical_parser.read_bytes()).hexdigest() != parser_sha256):
            raise ValueError("prepared mathematical parser changed")
        request = decode_message(sys.stdin.buffer.read(MAX_BODY_BYTES + 1))
        response = compile_request(request, mathematical_parser=mathematical_parser)
        raw = encode_message(response).split(b"\r\n\r\n", 1)[1]
    except (KeyError, TypeError, ValueError, UnicodeError, OSError, RuntimeError):
        return 1
    sys.stdout.buffer.write(raw)
    return 0
