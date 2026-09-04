#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The one way into this repository's tools.

    python tools/run.py                      every host gate, one verdict
    python tools/run.py --fix                and rewrite what is arithmetic first
    python tools/run.py check                one gate alone, after a document edit
    python tools/run.py coread --show R-15-073c
    python tools/run.py model build          dispatched into WSL from here
    python tools/run.py evidence             the whole exit-evidence sweep

A command is a name and never a path: `vos/cli/__init__.py` carries the table, and
`run.py <name> --help` is that command's own help. Asked for nothing, this runs the
host gate wave, which is what has to be green before anything lands.

**The two lanes are one command surface.** The document gates run on the Windows
host; the model, RTL, generator and prover loops run inside WSL, where the toolchain
lives. Rather than refuse a guest command asked for on the host, this re-launches it
through `wsl` and says so, so there is no `wsl -u root -e python3` to remember and no
wrong lane to be in. A guest command has to *drive* the toolchain to need the hop:
every subcommand `vos/cli/__init__.py` marks `host_ok`, `rtl filelist` and `testrig
protocol` among them, reads this checkout and answers here. Which ones those are is
read off that table rather than listed again here.

Everything past the command's name is that command's own, verbatim, including
`--help` and anything this file would otherwise read as its own flag. There is one
exception and it is the wave's: with no command at all, the arguments are the
wave's, which is what makes `run.py --fix` the repair.

Exit 0 is clean and 1 is a finding, on the convention every tool here keeps. It may
be run from anywhere: the repository root is found from this file, never from the
working directory.
"""

import io
import subprocess
import sys
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import cast

# The tools import `vos` without being installed, so the one entry point puts its own
# directory on the path first. Every import below this line is deliberately not at
# the top.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vos import corpus as corpus_mod
from vos.cli import BY_NAME, COMMANDS, Command

# What every command's entry point is. `import_module` hands back a module whose
# attributes are untyped, so the shape is stated once here and asserted at the single
# point one is called.
type Main = Callable[[list[str]], int]

# How the guest is reached from the host. There is no `-d`, because `Ubuntu` is WSL's
# default distribution and nothing here reads the distribution's name; `wsl -l -v`
# says which one holds the default and `wsl -s Ubuntu` puts it back.
GUEST = ("wsl", "-u", "root", "-e", "python3", "tools/run.py")


def _utf8_output() -> None:
    """Make redirected output obey the corpus's UTF-8 encoding, on either lane.

    `reconfigure` belongs to `io.TextIOWrapper` and not to the `TextIO` protocol the
    streams are typed as, so the guard is the type checker's, and a stream that is not
    a wrapper (a harness's capture, say) keeps the encoding its owner gave it."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")


def _usage() -> str:
    """Every command, what it decides, and the lane it decides it in."""
    width = max(len(command.name) for command in COMMANDS)
    lines = [__doc__.split("\n\n")[0], "", "commands:"]
    for command in COMMANDS:
        lane = "" if command.lane == "host" else "  [wsl]"
        lines.append(f"  {command.name:<{width}}  {command.decides}{lane}")
    lines += ["",
              "`run.py <command> --help` is that command's own help.",
              "A [wsl] command asked for here is re-launched in the guest."]
    return "\n".join(lines)


def _in_guest(root: Path, command: Command, argv: list[str]) -> int:
    """Re-launch a guest command through WSL, from the repository root.

    The path is relative and the working directory is the root, so WSL's own
    translation of the current directory is what makes the guest find this file:
    that is the one mapping both lanes already agree on, and it needs no `wslpath`
    of its own. The child's output is this run's output, streamed rather than
    captured, because a build is a quarter of an hour and its log is the point.
    """
    print(f"== {command.name} runs in WSL; re-launching there", flush=True)
    try:
        return subprocess.run([*GUEST, command.name, *argv],
                              cwd=root, check=False).returncode
    except OSError as err:
        print(f"the guest lane could not be reached: {err}\n"
              f"run it inside WSL as: python3 tools/run.py {command.name} "
              f"{' '.join(argv)}".rstrip(), file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    _utf8_output()
    args = list(sys.argv[1:] if argv is None else argv)

    if args and args[0] in ("help", "--help", "-h"):
        print(_usage())
        return 0

    # No command at all is the wave, and what follows is the wave's own arguments.
    # That is the one place this file reads a flag rather than passing it through.
    name, rest = ("gate", args) if not args or args[0].startswith("-") else (args[0], args[1:])

    command = BY_NAME.get(name)
    if command is None:
        print(f"no such command: {name}\n\n{_usage()}", file=sys.stderr)
        return 2

    root = corpus_mod.find_root()
    if command.guest_only(rest) and sys.platform == "win32":
        return _in_guest(root, command, rest)

    module = import_module(command.module)
    return cast("Main", module.main)(rest)


if __name__ == "__main__":
    sys.exit(main())
