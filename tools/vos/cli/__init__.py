# SPDX-License-Identifier: Apache-2.0
"""Every command this repository's tools offer, and the lane each one runs in.

There used to be seventeen executables under `tools/`, and using them meant knowing
which file answered which question and which of the two lanes it ran in. That is the
whole of what this package removes: one entry point, [run.py](../../run.py), reads
the table below, and a command is a name rather than a path.

Each module here is what one of those executables was, less its own preamble and its
own `__main__` block: it keeps its docstring, its argparse, and its `main(argv)`, so
`run.py <name> --help` is the help that command always printed. Nothing about what a
command decides moved with it.

**The lane is data here rather than a thing the caller remembers.** The document
gates run on the Windows host and the model, RTL and prover loops run inside WSL,
where the toolchain lives. A guest command asked for on the host is re-launched
through `wsl` by `run.py` rather than refused, so the two lanes are one command
surface; a `host_ok` subcommand is the exception that answers on either lane,
because it reads a file rather than driving a toolchain.

`tools/check.py` is the one command that is still its own file as well as a name
here, and the reason is that the normative documents cite that path: the register,
the coverage matrix, the crown jewels, the field bindings and the findings register
all say what `tools/check.py` decides, so the path is load-bearing and stays.
"""

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

# What a subcommand handler is, and the table a command's module keeps them in: one
# row per subcommand, the handler and the line `--help` prints for it. Four modules
# wrote the same dispatch over the same shape, which is the two-copies-of-one-parse
# defect these tools exist to catch, in the tools.
type Handler = Callable[[argparse.Namespace], int]
type Table = dict[str, tuple[Handler, str]]


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


@dataclass(frozen=True)
class Command:
    """One command: what to import, what it decides, and where it can decide it."""

    name: str
    module: str
    decides: str
    lane: str = "host"
    # The subcommands of a guest command that answer on the host too, because they
    # read this checkout rather than drive a toolchain. Everything else in a guest
    # command hops.
    host_ok: frozenset[str] = field(default_factory=frozenset)

    def guest_only(self, argv: list[str]) -> bool:
        """Whether this invocation must run in the guest rather than here."""
        if self.lane != "guest":
            return False
        return not argv or argv[0] not in self.host_ok


# The order is the order `run.py` lists them in: the gates first, then the documents,
# then the model and the loops over it, then the generators, then the proofs.
COMMANDS: tuple[Command, ...] = (
    Command("gate", "vos.cli.gate",
            "the host gates over this tree, in one run and one verdict"),
    Command("check", "check",
            "every derived fact against the artifact that owns it"),
    Command("selftest", "vos.cli.selftest",
            "every rule the checker carries, against its own mutant"),
    Command("typecheck", "vos.cli.typecheck",
            "the tools' own Python, under two pinned checkers"),
    Command("test", "vos.cli.test",
            "the tools' own behavioral tests"),
    Command("coread", "vos.cli.coread",
            "a register entry against the prose it cites, and the reading recorded"),
    Command("view", "vos.cli.view",
            "the specification and the register woven into one reading view"),
    Command("blast", "vos.cli.blast",
            "what an edit to the apex statement re-opens, before the work starts"),
    Command("model", "vos.cli.model",
            "every loop over the curated Sail model", lane="guest",
            host_ok=frozenset({"config-keys", "validate-config", "asm"})),
    Command("evidence", "vos.cli.evidence",
            "the whole exit-evidence sweep over the model, as one block",
            lane="guest"),
    Command("rtl", "vos.cli.rtl",
            "the authored RTL, its provenance, and the cross-check against the model",
            lane="guest", host_ok=frozenset({"provenance"})),
    Command("oracle", "vos.cli.oracle",
            "the model-as-oracle vector generator", lane="guest",
            host_ok=frozenset({"list", "emit"})),
    Command("seed", "vos.cli.seed",
            "the seeded-defect generator, pointed at an oracle that must notice",
            lane="guest", host_ok=frozenset({"list"})),
    Command("ring", "vos.cli.ring",
            "the ring contract's generated interface artifact, from its two owners"),
    Command("quickchick", "vos.cli.quickchick",
            "the Gallina front's input side", lane="guest"),
    Command("testrig", "vos.cli.testrig",
            "the RVFI-DII rig", lane="guest", host_ok=frozenset({"protocol"})),
    Command("proofs", "vos.cli.proofs",
            "every shipped proof, and its assumptions against the declared set",
            lane="guest"),
)

BY_NAME: dict[str, Command] = {command.name: command for command in COMMANDS}
