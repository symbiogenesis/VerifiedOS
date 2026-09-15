# SPDX-License-Identifier: Apache-2.0
"""Hold Q12's derived static records against the captured instrument output."""
from __future__ import annotations

import json
import runpy
from pathlib import Path
from tempfile import TemporaryDirectory

from tests.harness import TOOLS, Case, ensure


def _generated() -> None:
    script = TOOLS.parent / "docs" / "performance" / "inference-demand" / "ternary.py"
    generate = runpy.run_path(str(script))["outputs"]
    for path, expected in generate().items():
        ensure(path.is_file(), f"missing generated ternary artifact: {path}")
        ensure(path.read_text(encoding="utf-8") == expected,
               f"ternary artifact differs from its observations and generator: {path}")


def _cache_membership() -> None:
    script = TOOLS.parent / "docs" / "performance" / "inference-demand" / "ternary.py"
    generate = runpy.run_path(str(script))["outputs"]
    with TemporaryDirectory(prefix="vos-ternary-") as temporary:
        fixture = Path(temporary)
        generate.__globals__["ROOT"] = fixture
        for logs in ({}, {"f16": ""}, {"q8_0": ""},
                     {"f16": "", "q8_0": "", "unknown": ""}, None, []):
            (fixture / "ternary-observations.json").write_text(
                json.dumps({"loader_logs": logs}), encoding="utf-8")
            try:
                generate()
            except ValueError as error:
                ensure(str(error) == "loader observations must contain exactly f16 and q8_0",
                       f"wrong cache-membership refusal: {error}")
            else:
                raise AssertionError(f"accepted incomplete or unknown cache observations: {logs}")


def cases() -> list[Case]:
    return [Case("generated-static-records", _generated),
            Case("cache-membership-refusal", _cache_membership)]
