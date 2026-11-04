# SPDX-License-Identifier: Apache-2.0
"""Isolated compiler worker for the local browser playground."""

import hashlib
import sys
from pathlib import Path
from typing import cast

from vos import vela_mathematical
from vos.protocol_json import MAX_BODY_BYTES, decode_message, encode_message
from vos.vela import ValueType, VelaError, evaluate, translate
from vos.vela_authoring import lint_source, preview_bindings


def _mathematical_request(request: dict[str, object], source: bytes, digest: str,
                         parser: Path | None) -> dict[str, object]:
    if parser is None or request["action"] not in {"compile", "evaluate"}:
        raise VelaError("unsupported", 1, 1, "Mathematical compiler unavailable")
    if request["action"] == "compile":
        compiled = vela_mathematical.compile_source(source, parser)
        return {"ok": True, "sourceHash": digest,
                "module": compiled.module, "gallina": compiled.gallina,
                "findings": [{"code": finding.code, "message": finding.message,
                              "line": finding.line, "column": finding.column}
                             for finding in compiled.findings]}
    result = vela_mathematical.evaluate_source(
        source, cast("str", request["expression"]), cast("ValueType", request["valueType"]), parser)
    value = (("true" if result.value else "false") if result.value_type == "bool" else str(result.value))
    return {"ok": True, "sourceHash": digest, "valueType": result.value_type, "value": value}


def _mathematical_mode(request: dict[str, object]) -> bool:
    mode = request.get("mode", "pure")
    if mode not in {"pure", "mathematical"}:
        raise VelaError("unsupported", 1, 1, "Unknown compiler mode")
    return mode == "mathematical"


def compile_request(request: dict[str, object], *,
                    mathematical_parser: Path | None = None) -> dict[str, object]:
    source = cast("str", request["source"]).encode("utf-8")
    digest = hashlib.sha256(source).hexdigest()
    try:
        if _mathematical_mode(request):
            return _mathematical_request(request, source, digest, mathematical_parser)
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


def _verify_parser(parser: Path | None, digest: str | None) -> None:
    if parser is not None and hashlib.sha256(parser.read_bytes()).hexdigest() != digest:
        raise ValueError("prepared mathematical parser changed")


def main(*, mathematical_parser: Path | None = None, parser_sha256: str | None = None) -> int:
    try:
        _verify_parser(mathematical_parser, parser_sha256)
        request = decode_message(sys.stdin.buffer.read(MAX_BODY_BYTES + 1))
        response = compile_request(request, mathematical_parser=mathematical_parser)
        raw = encode_message(response).split(b"\r\n\r\n", 1)[1]
    except (KeyError, TypeError, ValueError, UnicodeError, OSError, RuntimeError):
        return 1
    sys.stdout.buffer.write(raw)
    return 0
