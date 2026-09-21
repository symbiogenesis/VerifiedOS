# SPDX-License-Identifier: Apache-2.0
"""Read-only Sail context through versioned MCP over standard input/output."""

import argparse
import sys

from vos import sailmcp
from vos.corpus import find_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py sail-mcp", description=__doc__)
    parser.parse_args(argv)
    return sailmcp.serve(find_root(), sys.stdin.buffer, sys.stdout.buffer)
