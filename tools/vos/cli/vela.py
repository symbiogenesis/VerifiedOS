# SPDX-License-Identifier: Apache-2.0
"""Check pure Vela prototype source or emit its unqualified Gallina translation."""

import argparse
import sys
from pathlib import Path

from vos.atomic import atomic_path
from vos.vela import MAX_SOURCE_BYTES, VelaError, translate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(suggest_on_error=True, description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "emit"):
        command = commands.add_parser(name)
        command.add_argument("source", type=Path)
        if name == "emit":
            command.add_argument("--output", type=Path,
                                 help="atomically replace a file in an existing directory")
    args = parser.parse_args(argv)
    source = Path(args.source)
    try:
        # Bound reads as well as parsing, including when the input is a special file.
        with source.open("rb") as stream:
            raw = stream.read(MAX_SOURCE_BYTES + 1)
        translation = translate(raw)
        if args.command == "check":
            print(f"ok vela: {translation.module}: pure prototype checked; unqualified")
        elif args.output is None:
            print(translation.gallina, end="")
        else:
            destination = Path(args.output)
            if (source.resolve() == destination.resolve()
                    or (destination.exists() and source.samefile(destination))):
                print(f"{source}:1:1: io: output aliases the input", file=sys.stderr)
                return 1
            with atomic_path(destination) as pending:
                pending.write_text(translation.gallina, encoding="utf-8", newline="")
    except VelaError as error:
        print(f"{source}:{error.line}:{error.column}: {error.kind}: {error.message}",
              file=sys.stderr)
        return 1
    except OSError as error:
        print(f"{source}:1:1: io: {error}", file=sys.stderr)
        return 1
    return 0
