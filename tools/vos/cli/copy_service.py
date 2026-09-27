# SPDX-License-Identifier: Apache-2.0
"""Check the copy service's bounded C against the shipped ring reference.

    python tools/run.py copy-service check
"""

import argparse
from pathlib import Path

from vos import cli, copy_notification, copy_service, copy_target, env
from vos.corpus import find_root


def cmd_check(_args: argparse.Namespace) -> int:
    work = env.load().lane_root / "copy-service"
    with env.hold_lock(work, "a copy service reference comparison"):
        code, output = copy_service.check(find_root(), work)
    print("\n".join(output))
    return code


def cmd_target(args: argparse.Namespace) -> int:
    work = env.load().lane_root / "copy-target"
    reference = args.reference or env.load().lane_root / "copy-service"
    with env.hold_lock(work, "a scalar copy service target comparison"):
        report = copy_target.run(find_root(), work, reference, args.ccomp,
                                 args.ccomp_arg, args.simulator, args.build_receipt)
    print(f"ok copy target: {report['rows']} reference rows and actual atomic payload controls")
    print(f"report: {work / 'report.json'}")
    print(report["limits"])
    return 0


def cmd_notification(args: argparse.Namespace) -> int:
    work = env.load().lane_root / "copy-notification"
    with env.hold_lock(work, "an actual copy notification experiment"):
        report = copy_notification.run(find_root(), work, args.ccomp, args.ccomp_arg,
                                       args.simulator, args.build_receipt)
    print(f"ok actual copy notification, ordinary poll and two executed controls: {work / 'report.json'}")
    print(report["limits"])
    return 0


def target_parser(name: str, parser: argparse.ArgumentParser) -> None:
    if name not in {"target", "notification"}:
        return
    parser.add_argument("--ccomp", type=Path, required=True)
    parser.add_argument("--ccomp-arg", action="append", default=[])
    parser.add_argument("--simulator", type=Path, required=True)
    parser.add_argument("--build-receipt", type=Path, required=True)
    parser.add_argument("--reference", type=Path)


COMMANDS: cli.Table = {
    "check": (cmd_check, "bounded C and atomic payload controls against the ring reference"),
    "target": (cmd_target, "accepted scalar stages and actual fenced ring adapter"),
    "notification": (cmd_notification, "actual interrupt-file store and ordinary pending load"),
}


def main(argv: list[str] | None = None) -> int:
    return cli.dispatch(__doc__, COMMANDS, argv, target_parser, prog="run.py copy-service")
