#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Refuse an unready staged chain before the hosted campaign allocates its runners."""

import argparse
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from vos import boot_chain, boot_chain_target  # noqa: E402 (standalone workflow entry point)


def case_timeout(value: str) -> int:
    """Whole decimal seconds within the campaign's fixed execution budget."""
    maximum = boot_chain_target.TIMEOUTS["boot"]
    if (len(value) > len(str(maximum)) or re.fullmatch(r"[0-9]+", value) is None
            or not 1 <= int(value) <= maximum):
        raise ValueError(f"case_timeout must be a whole number of seconds from 1 to {maximum}")
    return int(value)


def readiness(root: Path, value: str) -> boot_chain.Staged:
    """Use the strict target verifier; historical integrity supplies no readiness."""
    case_timeout(value)
    return boot_chain_target.verify(root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", required=True)
    parser.add_argument("--github-output", type=Path,
                        help="append the validated decimal timeout for dependent jobs")
    args = parser.parse_args(argv)
    try:
        staged = readiness(TOOLS.parent, args.timeout)
        if args.github_output is not None:
            with args.github_output.open("a", encoding="utf-8", newline="\n") as output:
                output.write(f"case_timeout={case_timeout(args.timeout)}\n")
    except (OSError, ValueError, TypeError, KeyError, ImportError, RuntimeError) as error:
        print(f"FAIL boot-chain plan: {error}")
        return 1
    print(f"ok boot-chain plan: {len(staged.streams)} streams and {len(staged.images)} "
          f"images are ready; case timeout {case_timeout(args.timeout)} seconds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
