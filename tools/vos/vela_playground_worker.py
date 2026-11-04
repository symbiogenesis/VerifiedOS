# SPDX-License-Identifier: Apache-2.0
"""Isolated compiler worker for the local browser playground."""

import hashlib
import sys
from typing import cast

from vos.protocol_json import MAX_BODY_BYTES, decode_message, encode_message
from vos.vela import ValueType, VelaError, evaluate, translate


def compile_request(request: dict[str, object]) -> dict[str, object]:
    source = cast("str", request["source"]).encode("utf-8")
    digest = hashlib.sha256(source).hexdigest()
    try:
        if request["action"] == "compile":
            compiled = translate(source)
            return {"ok": True, "sourceHash": digest,
                    "module": compiled.module, "gallina": compiled.gallina}
        result = evaluate(source, cast("str", request["expression"]),
                          cast("ValueType", request["valueType"]))
        value = ("true" if result.value else "false") if result.value_type == "bool" else str(result.value)
        return {"ok": True, "sourceHash": digest, "valueType": result.value_type, "value": value}
    except VelaError as error:
        return {"ok": False, "sourceHash": digest,
                "error": {"kind": error.kind, "message": error.message,
                          "line": error.line, "column": error.column}}


def main() -> int:
    try:
        request = decode_message(sys.stdin.buffer.read(MAX_BODY_BYTES + 1))
        response = compile_request(request)
        raw = encode_message(response).split(b"\r\n\r\n", 1)[1]
    except (KeyError, TypeError, ValueError, UnicodeError):
        return 1
    sys.stdout.buffer.write(raw)
    return 0
