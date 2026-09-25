# SPDX-License-Identifier: Apache-2.0
"""Check the copy service's bounded C against the shipped ring reference.

    python tools/run.py copy-service check
"""

import argparse

from vos import cli, copy_service, env
from vos.corpus import find_root


def cmd_check(_args: argparse.Namespace) -> int:
    work = env.load().lane_root / "copy-service"
    with env.hold_lock(work, "a copy service reference comparison"):
        code, output = copy_service.check(find_root(), work)
    print("\n".join(output))
    return code


COMMANDS: cli.Table = {"check": (cmd_check, "bounded C and atomic payload controls against the ring reference")}


def main(argv: list[str] | None = None) -> int:
    return cli.dispatch(__doc__, COMMANDS, argv, prog="run.py copy-service")
