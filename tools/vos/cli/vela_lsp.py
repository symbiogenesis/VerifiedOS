# SPDX-License-Identifier: Apache-2.0
"""Serve unqualified pure Vela diagnostics and navigation over standard input/output."""

import argparse
import sys

from vos.vela_lsp import serve


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(suggest_on_error=True, description=__doc__)
    parser.parse_args(argv)
    return serve(sys.stdin.buffer, sys.stdout.buffer)
