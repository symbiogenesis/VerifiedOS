# SPDX-License-Identifier: Apache-2.0
"""Build a contained compiler with validated default reuse; inspect evidence read-only."""

import argparse
import json
import sys
from pathlib import Path

from vos import compiler_build
from vos.cli import positive_int
from vos.corpus import find_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py compiler-build", description=__doc__)
    operations = parser.add_subparsers(dest="operation", required=True)
    for operation in ("build", "status"):
        command = operations.add_parser(operation)
        for name in ("source", "lane-root", "out", "cache", "driver-root", "driver-manifest",
                     "opam-root", "lock", "configuration"):
            command.add_argument("--" + name, type=Path, required=True)
        command.add_argument("--source-revision", required=True)
        command.add_argument("--switch", required=True)
        command.add_argument("--kernel-profile", choices=("standard", "vm"), required=True)
        command.add_argument("--jobs", type=positive_int, default=1)
        command.add_argument("--reuse-from", type=Path)
        command.add_argument("--json", action="store_true")
        if operation == "build":
            command.add_argument("--fresh", action="store_true", help="bypass both reuse tiers and the index")
            command.add_argument("--profile", action="store_true", help="request new kernel profile output")
    args = vars(parser.parse_args(argv))
    operation = args.pop("operation")
    as_json = args.pop("json")
    try:
        report = compiler_build.run(compiler_build.Settings(**args), find_root(), status=operation == "status")
    except (OSError, ValueError, TypeError, SystemExit):
        print("compiler-build: refused invalid, changed or unavailable operation inputs", file=sys.stderr)
        return 1
    if as_json:
        print(json.dumps(report, sort_keys=True, ensure_ascii=True, indent=2))
    else:
        print(f"compiler-build: {report['outcome']}; {report['candidate_reason']}")
        for name, phase in report["phases"].items():
            print(f"  {name}: {phase['action']} ({phase['status']})")
        print(f"  current validation/operation: {report['validation_seconds']:.2f}s; reused execution timings are historical")
    return 0 if report["outcome"] in {"complete", "status"} else 1
