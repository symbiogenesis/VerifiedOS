# SPDX-License-Identifier: Apache-2.0
"""Run the native metadata control through the repository's guest dispatcher."""

import runpy
import sys
from collections.abc import Callable
from typing import cast

from vos.corpus import find_root


def main(argv: list[str] | None = None) -> int:
    source = find_root() / "tools" / "rocq-census" / "qualify.py"
    arguments = sys.argv[1:] if argv is None else argv
    namespace = runpy.run_path(str(source))
    entry = cast(Callable[[], int], namespace["main"])
    previous = sys.argv
    try:
        sys.argv = ["run.py rocq-census", *arguments]
        return entry()
    finally:
        sys.argv = previous
