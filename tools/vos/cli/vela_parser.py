# SPDX-License-Identifier: Apache-2.0
"""Build or qualify the syntax-only Menhir development parser, or parse a file."""

import argparse
import json
import sys
from pathlib import Path

from filelock import Timeout

from vos import vela_migration, vela_parser, vela_parser_checked
from vos.vela import VelaError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(suggest_on_error=True, description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build", help="make a fresh native parser and receipt")
    commands.add_parser("qualify", help="check independent AST/refusal fixtures and regeneration")
    commands.add_parser("migration", help="compare generated AST translation with the retained prototype")
    support = commands.add_parser("support", help="build and kernel-check the pinned Rocq support library")
    support.add_argument("--archive", type=Path, help="use an already downloaded authenticated release archive")
    parse = commands.add_parser("parse", help="emit a complete located syntax tree as JSON")
    parse.add_argument("source", type=Path)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    try:
        if args.command == "support":
            output = vela_parser_checked.qualify(root, archive=args.archive)
        elif args.command == "migration":
            output = vela_migration.qualify(root)
        elif args.command == "qualify":
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
    if args.command == "migration" and output["status"] != "agreed":
        return 1
    return 0
