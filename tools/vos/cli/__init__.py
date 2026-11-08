# SPDX-License-Identifier: Apache-2.0
"""Shared CLI dispatch helpers for `vos.cli` command modules.

[vos/commands.py](../commands.py#COMMANDS) registers each command's module and lane, and
[run.py](../../run.py#main) imports the selected module. Each module defines its own
docstring, argument parser, and `main(argv)`.
"""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

type Handler = Callable[[argparse.Namespace], int]
type Table = dict[str, tuple[Handler, str]]


def positive_int(value: str) -> int:
    """Parse a positive integer argument (`>= 1`)."""
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def dispatch(doc: str | None, table: Table, argv: list[str] | None,
             flags: Callable[[str, argparse.ArgumentParser], None] | None = None,
             prog: str | None = None) -> int:
    """Parse arguments for a subcommand table and invoke the selected handler.

    If `flags` is provided, it is called with `(name, subparser)` as each subcommand
    parser is constructed.
    """
    parser = argparse.ArgumentParser(
        suggest_on_error=True, prog=prog, description=(doc or "").splitlines()[0] if bool(doc) else None)
    subs = parser.add_subparsers(dest="command", required=True)
    for name, (_, help_text) in table.items():
        sub = subs.add_parser(name, suggest_on_error=True, help=help_text)
        if flags is not None:
            flags(name, sub)
    args = parser.parse_args(argv)
    handler, _ = table[args.command]
    return handler(args)


def entry(command: str, *args: str) -> list[str]:
    """Return the `argv` list that invokes `tools/run.py <command> <args...>` in a child process."""
    return [sys.executable, str(Path(__file__).resolve().parents[2] / "run.py"),
            command, *args]
