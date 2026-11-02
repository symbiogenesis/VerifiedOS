# SPDX-License-Identifier: Apache-2.0
"""One bounded pure-prototype check, run by the host language server's worker."""

import json
import sys

from vos.vela import MAX_SOURCE_BYTES, VelaError, translate


def main() -> int:
    source = sys.stdin.buffer.read(MAX_SOURCE_BYTES + 1)
    error_data: dict[str, object] | None = None
    try:
        translate(source)
    except VelaError as error:
        error_data = {"kind": error.kind, "line": error.line, "column": error.column,
                      "message": error.message[:4096]}
    print(json.dumps(error_data, ensure_ascii=True))
    return 0
