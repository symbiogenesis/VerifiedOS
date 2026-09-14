# SPDX-License-Identifier: Apache-2.0
"""Hold Q12's derived static records against the captured instrument output."""
from __future__ import annotations

import runpy

from tests.harness import TOOLS, Case, ensure


def _generated() -> None:
    script = TOOLS.parent / "docs" / "performance" / "inference-demand" / "ternary.py"
    generate = runpy.run_path(str(script))["outputs"]
    for path, expected in generate().items():
        ensure(path.is_file(), f"missing generated ternary artifact: {path}")
        ensure(path.read_text(encoding="utf-8") == expected,
               f"ternary artifact differs from its observations and generator: {path}")


def cases() -> list[Case]:
    return [Case("generated-static-records", _generated)]
