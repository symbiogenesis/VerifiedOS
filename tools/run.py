#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The one way into this repository's tools.

    python tools/run.py                      prepare instructions, then every host gate
    python tools/run.py --fix                also repair derived artifacts, then validate
    python tools/run.py --check --tests      complete read-only CI validation
    python tools/run.py check                one gate alone, after a document edit
    python tools/run.py coread --show R-15-073c
    python tools/run.py model build          dispatched into WSL from here
    python tools/run.py evidence             the whole exit-evidence sweep

[vos/commands.py](vos/commands.py#COMMANDS) defines the command table;
`run.py <name> --help` prints that command's help. With no command name, `run.py`
runs the [`gate`](vos/cli/gate.py#main) wave, forwarding any flags (such as `--fix`).

Document gates run on the host; model, RTL, generator, and prover commands run in WSL.
When a guest-only command is invoked on Windows, `run.py` re-launches it in WSL
automatically. Subcommands that can run on the host are listed in `Command.host_ok`
(see [tools/README.md](README.md)).

Arguments after the command name are passed verbatim to that command's `main(argv)`.
Exit 0 is clean and 1 is a finding. The repository root is resolved from this file's
path rather than the working directory.
"""

import io
import shlex
import subprocess
import sys
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import cast

# Put `tools/` on `sys.path` so `vos` can be imported without package installation.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from vos import pyversion

if __name__ == "__main__":
    try:
        pyversion.require_supported(Path(__file__).resolve().parents[1])
    except (OSError, ValueError) as error:
        raise SystemExit(str(error)) from error

from vos import corpus as corpus_mod
from vos import toolenv
from vos.commands import BY_NAME, COMMANDS, Command

type Main = Callable[[list[str]], int]

# WSL invocation prefix. Uses the toolchain's default distribution; see
# [the host selection guidance](README.md#running-them).
GUEST = ("wsl", "-u", "root", "-e", "python3", "tools/run.py")


def _utf8_output() -> None:
    """Reconfigure stdout and stderr to UTF-8 when backed by `io.TextIOWrapper`."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")


def _usage() -> str:
    """Format the command table and lane annotations for `--help`."""
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
    """Re-launch a guest command through WSL from the repository root."""
    print(f"== {command.name} runs in WSL; re-launching there", file=sys.stderr, flush=True)
    try:
        return subprocess.run([*GUEST, command.name, *argv],
                              cwd=root, check=False).returncode
    except OSError as err:
        retry = shlex.join(["python3", "tools/run.py", command.name, *argv])
        print(f"the guest lane could not be reached: {err}\n"
              f"run it inside WSL as: {retry}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    _utf8_output()
    args = list(sys.argv[1:] if argv is None else argv)

    if args and args[0] in ("help", "--help", "-h"):
        print(_usage())
        return 0

    # With no command name (or only flags), dispatch to `gate`.
    name, rest = ("gate", args) if not args or args[0].startswith("-") else (args[0], args[1:])

    command = BY_NAME.get(name)
    if command is None:
        print(f"no such command: {name}\n\n{_usage()}", file=sys.stderr)
        return 2

    root = corpus_mod.find_root()
    if command.guest_only(rest) and sys.platform == "win32":
        return _in_guest(root, command, rest)

    if (code := toolenv.bootstrap(root, args)) is not None:
        return code

    module = import_module(command.module)
    return cast("Main", module.main)(rest)


if __name__ == "__main__":
    sys.exit(main())
