# SPDX-License-Identifier: Apache-2.0
"""The command modules, one per command, and the dispatch they share.

[vos/commands.py](../commands.py) names each command's module and lane, and
[run.py](../../run.py) imports the module a command names. Each module here keeps its
docstring, its argparse and its `main(argv)`, so `run.py <name> --help` is that
command's own help. This initializer runs whenever a command module is imported, so it
holds only the helpers those modules share and never the table itself.
"""

import argparse
import sys
from collections.abc import Callable
from pathlib import Path

# What a subcommand handler is, and the table a command's module keeps them in: one
# row per subcommand, the handler and the line `--help` prints for it. Four modules
# wrote the same dispatch over the same shape, which is the two-copies-of-one-parse
# defect these tools exist to catch, in the tools.
type Handler = Callable[[argparse.Namespace], int]
type Table = dict[str, tuple[Handler, str]]


def positive_int(value: str) -> int:
    """An argparse count that cannot accidentally request unlimited workers."""
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def dispatch(doc: str | None, table: Table, argv: list[str] | None,
             flags: Callable[[str, argparse.ArgumentParser], None] | None = None,
             prog: str | None = None) -> int:
    """Parse one command's own arguments and run the subcommand they name.

    `flags` is where a module says what its subcommands take beyond their name; it
    is handed each subparser as it is built, so a flag stays beside the subcommand
    it belongs to rather than moving into a table nothing reads.
    """
    parser = argparse.ArgumentParser(
        prog=prog, description=(doc or "").splitlines()[0] if doc else None)
    subs = parser.add_subparsers(dest="command", required=True)
    for name, (_, help_text) in table.items():
        sub = subs.add_parser(name, help=help_text)
        if flags is not None:
            flags(name, sub)
    args = parser.parse_args(argv)
    handler, _ = table[args.command]
    return handler(args)


def entry(command: str, *args: str) -> list[str]:
    """The argv that runs one command again in a process of its own.

    Two loops detach a child that re-runs them in the background, and both used to
    name their own file. There is one entry point now, so the argv is written once
    here rather than derived from `__file__` at each site, which is also what keeps a
    detached child launching through the same table its parent was dispatched by.
    """
    return [sys.executable, str(Path(__file__).resolve().parents[2] / "run.py"),
            command, *args]
