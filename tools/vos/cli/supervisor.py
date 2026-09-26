# SPDX-License-Identifier: Apache-2.0
"""Check the supervisor's GC-free host core against the locked Gallina reference.

    python tools/run.py supervisor check

Generated C answers are compiled as exact equalities against SupervisionTree.v.
Consumer and generated effect controls are reported separately. No target image is built.
"""

import argparse

from vos import cli, env, supervisor
from vos.corpus import find_root


def cmd_check(_args: argparse.Namespace) -> int:
    work = env.load().lane_root / "supervisor"
    with env.hold_lock(work, "a supervisor reference comparison"):
        code, output = supervisor.check(find_root(), work)
    print("\n".join(output))
    return code


COMMANDS: cli.Table = {"check": (cmd_check, "host C against the locked Gallina definitions")}


def main(argv: list[str] | None = None) -> int:
    return cli.dispatch(__doc__, COMMANDS, argv, prog="run.py supervisor")
