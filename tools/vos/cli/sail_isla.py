# SPDX-License-Identifier: Apache-2.0
"""Provision optional Isla tools or run the finite curated permission campaign."""

import argparse
import json
import sys

from vos import env, sailisla


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py sail-isla", description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    install = commands.add_parser("provision", help="explicit locked downloads and isolated builds")
    install.add_argument("--jobs", type=int, default=2, help="native build jobs, 1..16")
    install.add_argument("--json", action="store_true")
    qualify = commands.add_parser("qualify", help="generate witnesses, replay and run defect controls")
    qualify.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.operation == "provision" and not 1 <= args.jobs <= 16:
        parser.error("--jobs must be in 1..16")
    try:
        environment = env.load()
        if args.operation == "provision":
            stamp = sailisla.provision(environment, args.jobs)
            if args.json:
                print(json.dumps(stamp, indent=2))
            else:
                print(f"Optional Isla tools provisioned in {environment.lane_root / 'sail-isla'}")
            return 0
        report = sailisla.qualify(environment)
    except (OSError, ValueError) as exc:
        print(f"sail-isla: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(report["notice"])
        print(f"{len(report['cases'])} generated cases match the primary oracle and isla-testgen.")
        for control in report["controls"]:
            print(f"{control['name']}: {control['status']} ({len(control['mismatches'])} mismatches)")
        print(f"Report: {report['directory']}/report.json")
    return 0 if report["passed"] else 1
