# SPDX-License-Identifier: Apache-2.0
"""Build or qualify the syntax-only Menhir development parser, or parse a file."""

import argparse
import json
import sys
from pathlib import Path

from filelock import Timeout

from vos import vela_parser
from vos.vela import VelaError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(suggest_on_error=True, description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build", help="make a fresh native parser and receipt")
    commands.add_parser("qualify", help="check independent AST/refusal fixtures and regeneration")
    parse = commands.add_parser("parse", help="emit a complete located syntax tree as JSON")
    parse.add_argument("source", type=Path)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    try:
        if args.command == "qualify":
            output = vela_parser.qualify(root)
        elif args.command == "build":
            output = vela_parser.build(root).receipt
        else:
            source = vela_parser.read_source(args.source)
            output = vela_parser.parse_source(vela_parser.build(root), source)
    except VelaError as error:
        site = str(args.source) if args.command == "parse" else "qualification"
        print(f"{site}:{error.line}:{error.column}: {error.kind}: {error.message}", file=sys.stderr)
        return 1
    except (OSError, RuntimeError, TypeError, ValueError, Timeout) as error:
        print(f"FAIL vela-parser: {error}", file=sys.stderr)
        return 1
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0
