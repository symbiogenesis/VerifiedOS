#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Refuse an unready signature campaign before allocating its target runners."""

import argparse
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from vos import boot_crypto_target  # noqa: E402 (standalone workflow entry point)


def case_timeout(value: str) -> int:
    """Two bounded phases must fit the campaign's 320-minute execution step."""
    maximum = 9600
    if (len(value) > len(str(maximum)) or re.fullmatch(r"[0-9]+", value) is None
            or not 1 <= int(value) <= maximum):
        raise ValueError(f"case_timeout must be a whole number of seconds from 1 to {maximum}")
    return int(value)


def readiness(root: Path, value: str) -> int:
    """Strict verification requires current source and complete compiler provenance."""
    case_timeout(value)
    _, streams = boot_crypto_target.staged(root)
    return len(streams)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(suggest_on_error=True, description=__doc__)
    parser.add_argument("--timeout", required=True)
    parser.add_argument("--github-output", type=Path,
                        help="append the validated decimal timeout for dependent jobs")
    parser.add_argument("--timeout-only", action="store_true",
                        help="validate in the dispatching checkout before switching revision")
    args = parser.parse_args(argv)
    try:
        seconds = case_timeout(args.timeout)
        streams = None if args.timeout_only else readiness(TOOLS.parent, args.timeout)
        if args.github_output is not None:
            with args.github_output.open("a", encoding="utf-8", newline="\n") as output:
                output.write(f"case_timeout={seconds}\n")
    except (OSError, ValueError, TypeError, KeyError, ImportError, RuntimeError) as error:
        print(f"FAIL boot-crypto plan: {error}")
        return 1
    if streams is None:
        print(f"ok boot-crypto timeout: {seconds} seconds; staging readiness remains unchecked")
    else:
        print(f"ok boot-crypto plan: {streams} streams are ready; case timeout {seconds} seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
