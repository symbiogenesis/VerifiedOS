# SPDX-License-Identifier: Apache-2.0
"""Compare the supervisor reference and exercise its contained target transport.

    python tools/run.py supervisor check

Generated C answers are compiled as exact equalities against SupervisionTree.v.
Consumer and generated effect controls are reported separately. The target command
is a distinct bounded privilege/transport experiment, not full roster acceptance.
"""

import argparse
from pathlib import Path

from vos import cli, env, lifecycle_target, supervisor
from vos.corpus import find_root


def cmd_check(_args: argparse.Namespace) -> int:
    work = env.load().lane_root / "supervisor"
    with env.hold_lock(work, "a supervisor reference comparison"):
        code, output = supervisor.check(find_root(), work)
    print("\n".join(output))
    return code


def cmd_target(args: argparse.Namespace) -> int:
    work = env.load().lane_root / "supervisor-target"
    with env.hold_lock(work, "a contained supervisor lifecycle target experiment"):
        report = lifecycle_target.run(find_root(), args.ccomp, args.compiler_config,
                                      args.simulator, args.build_receipt, work, args.timeout)
    print(f"report: {work / 'report.json'}")
    print("Bounded target transport; full roster acceptance remains open.")
    return 0 if report["ok"] else 1


def flags(name: str, parser: argparse.ArgumentParser) -> None:
    if name == "target":
        parser.add_argument("--ccomp", type=Path, required=True)
        parser.add_argument("--compiler-config", type=Path, required=True)
        parser.add_argument("--simulator", type=Path, required=True)
        parser.add_argument("--build-receipt", type=Path, required=True)
        parser.add_argument("--timeout", type=int, default=180)


COMMANDS: cli.Table = {
    "check": (cmd_check, "host C against the locked Gallina definitions"),
    "target": (cmd_target, "contained supervisor publication and trusted timer consumption"),
}


def main(argv: list[str] | None = None) -> int:
    return cli.dispatch(__doc__, COMMANDS, argv, flags, prog="run.py supervisor")
