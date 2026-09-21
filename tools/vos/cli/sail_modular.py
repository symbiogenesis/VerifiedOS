# SPDX-License-Identifier: Apache-2.0
"""Qualify optional static libraries partitioned from the locked Sail C++ model."""

import argparse
import json
import sys
from typing import cast

from vos import env, sailmodular


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py sail-modular", description=__doc__)
    parser.add_argument("action", choices=("qualify",))
    parser.add_argument("--partitions", type=int, default=4, help="method libraries, 2..16 (default: 4)")
    parser.add_argument("--json", action="store_true", help="print the complete qualification report")
    args = parser.parse_args(argv)
    if not 2 <= args.partitions <= 16:
        parser.error("--partitions must be between 2 and 16")
    try:
        report = sailmodular.qualify(env.load(), args.partitions)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"sail-modular: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=True))
    else:
        print(f"PASS {report['methods']} methods in {report['partitions']} method libraries; "
              f"{report['suite_cases']} suite cases and "
              f"{len(cast('list[object]', report['corpus']))} corpus members")
        print(f"Evidence: {report['run']}/qualification.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
