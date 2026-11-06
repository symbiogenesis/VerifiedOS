# SPDX-License-Identifier: Apache-2.0
"""One bounded pure-prototype check, run by the host language server's worker."""

import hashlib
import json
import sys

from vos.protocol_json import MAX_BODY_BYTES
from vos.vela import MAX_SOURCE_BYTES, VelaError, inspect_source, translate
from vos.vela.authoring import format_source


def main() -> int:
    source = sys.stdin.buffer.read(MAX_SOURCE_BYTES + 1)
    if sys.argv[1:] == ["--format"]:
        result: dict[str, object] = {"source_sha256": hashlib.sha256(source).hexdigest()}
        try:
            result.update(status="ok", formatted=format_source(source).decode("utf-8"))
        except VelaError as error:
            result.update(status="unavailable", reason=error.kind)
        encoded = json.dumps(result, ensure_ascii=True)
        if len(encoded.encode("utf-8")) > MAX_BODY_BYTES:
            return 1
        print(encoded, end="")
        return 0
    if sys.argv[1:] == ["--inspect"]:
        try:
            inspection = inspect_source(source)
        except VelaError as error:
            inspection = {"status": "unavailable", "reason": error.kind}
        encoded = json.dumps(inspection, ensure_ascii=True)
        if len(encoded.encode("utf-8")) > MAX_BODY_BYTES:
            encoded = json.dumps({"status": "unavailable", "reason": "inspection-limit"})
        print(encoded, end="")
        return 0
    if sys.argv[1:]:
        return 2
    error_data: dict[str, object] | None = None
    try:
        translate(source)
    except VelaError as error:
        error_data = {"kind": error.kind, "line": error.line, "column": error.column,
                      "message": error.message[:4096]}
    print(json.dumps(error_data, ensure_ascii=True))
    return 0
