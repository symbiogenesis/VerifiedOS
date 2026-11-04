# SPDX-License-Identifier: Apache-2.0
"""Parse Vela, elaborate mathematical terms, or qualify development tooling."""

import argparse
import json
import sys
from pathlib import Path

from filelock import Timeout

from vos import (
    vela_elaborate,
    vela_elaboration_check,
    vela_migration,
    vela_parser,
    vela_parser_checked,
)
from vos.atomic import atomic_path
from vos.vela import VelaError


def _publish(source: Path, destination: Path, gallina: str) -> None:
    if (source.resolve() == destination.resolve()
            or (destination.exists() and source.samefile(destination))):
        raise VelaError("io", 1, 1, "output aliases the input")
    with atomic_path(destination) as pending:
        pending.write_text(gallina, encoding="utf-8", newline="")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(suggest_on_error=True, description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build", help="make a fresh native parser and receipt")
    commands.add_parser("qualify", help="check independent AST/refusal fixtures and regeneration")
    commands.add_parser("migration", help="compare generated AST translation with the retained prototype")
    commands.add_parser("elaborate-qualify", help="replay pure and mathematical elaboration through the locked kernel")
    elaborate = commands.add_parser(
        "elaborate", help="emit unqualified Gallina for the bounded generic/dependent mathematical fragment",
        description="Elaborate generic dependent mathematics and explicit proofs. Development prototype; "
                    "emission supplies no kernel or source-correspondence verdict. "
                    "Unsupported contracts, effects, resource syntax and unresolved holes are refused.")
    elaborate.add_argument("source", type=Path)
    elaborate.add_argument("--output", type=Path,
                           help="atomically replace a file in an existing directory")
    support = commands.add_parser("support", help="build and kernel-check the pinned Rocq support library")
    support.add_argument("--archive", type=Path, help="use an already downloaded authenticated release archive")
    parse = commands.add_parser("parse", help="emit a complete located syntax tree as JSON")
    parse.add_argument("--surface", action="store_true", help="parse the full development surface as schema 2")
    parse.add_argument("source", type=Path)
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    try:
        if args.command == "elaborate":
            source = vela_parser.read_source(args.source)
            parsed = vela_parser.parse_source(vela_parser.build(root), source, surface=True)
            translation = vela_elaborate.elaborate(source, parsed)
            if args.output is None:
                print(translation.gallina, end="")
            else:
                _publish(args.source, args.output, translation.gallina)
            return 0
        if args.command == "elaborate-qualify":
            output = vela_elaboration_check.qualify(root)
        elif args.command == "support":
            output = vela_parser_checked.qualify(root, archive=args.archive)
        elif args.command == "migration":
            output = vela_migration.qualify(root)
        elif args.command == "qualify":
            output = vela_parser.qualify(root)
        elif args.command == "build":
            output = vela_parser.build(root).receipt
        else:
            source = vela_parser.read_source(args.source)
            output = vela_parser.parse_source(vela_parser.build(root), source, surface=args.surface)
    except VelaError as error:
        site = str(args.source) if args.command in {"parse", "elaborate"} else "qualification"
        print(f"{site}:{error.line}:{error.column}: {error.kind}: {error.message}", file=sys.stderr)
        return 1
    except (OSError, RuntimeError, TypeError, ValueError, Timeout) as error:
        print(f"FAIL vela-parser: {error}", file=sys.stderr)
        return 1
    print(json.dumps(output, indent=2, sort_keys=True))
    if args.command == "migration" and output["status"] != "agreed":
        return 1
    return 0
