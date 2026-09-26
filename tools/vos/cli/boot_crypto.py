# SPDX-License-Identifier: Apache-2.0
"""Compare bounded signature verification C with pinned ACVP and OpenSSL."""

import argparse
import subprocess
from pathlib import Path

from vos import boot_crypto, env, receipts
from vos.cli import Table, dispatch


def cmd_run(args: argparse.Namespace) -> int:
    e = env.load()
    out = Path(args.out) if args.out else e.lane_root / "boot-crypto"
    out.mkdir(parents=True, exist_ok=True)
    with env.hold_lock(out, "boot signature comparison"):
        receipts.write(out / "report.json", {"passed": False, "status": "incomplete", "milestone_acceptance": "open"})
        try:
            result = boot_crypto.campaign(e.root, out, args.gallina, args.first)
        except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
            receipts.write(out / "report.json", {"passed": False, "status": "failed", "error": str(error),
                                                 "milestone_acceptance": "open"})
            print(f"FAIL boot-crypto: {error}")
            return 1
        receipts.write(out / "report.json", result)
    print(f"{'ok' if result['passed'] else 'FAIL'} boot-crypto: {out / 'report.json'}; "
          "host executable comparison; milestone_acceptance: open")
    return 0 if result["passed"] else 1


TABLE: Table = {"run": (cmd_run, "standard vectors, refusal controls and independent oracle")}


def _flags(name: str, parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", help="native lane output directory")
    parser.add_argument("--gallina", action="store_true", help="also build and compare the exact ML-DSA Gallina reference")
    parser.add_argument("--first", action="store_true", help="first positive per scheme only; incomplete evidence")


def main(argv: list[str] | None = None) -> int:
    return dispatch(__doc__, TABLE, argv, _flags, prog="run.py boot-crypto")
