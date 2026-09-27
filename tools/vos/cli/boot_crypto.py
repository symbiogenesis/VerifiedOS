# SPDX-License-Identifier: Apache-2.0
"""Compare bounded signature verification C with pinned ACVP and OpenSSL."""

import argparse
import subprocess
from pathlib import Path

from vos import boot_crypto, boot_crypto_target, env, receipts
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


def cmd_target(args: argparse.Namespace) -> int:
    e = env.load()
    out = Path(args.out) if args.out else e.lane_root / "boot-crypto-target"
    out.mkdir(parents=True, exist_ok=True)
    with env.hold_lock(out, "boot signature target comparison"):
        receipts.write(out / "report.json", {"passed": False, "status": "incomplete",
                                              "milestone_acceptance": "open"})
        try:
            result = boot_crypto_target.run(e.root, out, Path(args.ccomp), args.ccomp_arg,
                Path(args.simulator), Path(args.build_receipt), args.timeout, args.inst_limit, args.first, args.jobs)
        except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError) as error:
            receipts.write(out / "report.json", {"passed": False, "status": "failed", "error": str(error),
                                                 "milestone_acceptance": "open"})
            print(f"FAIL boot-crypto target: {error}")
            return 1
        result["status"] = "passed" if result["passed"] else "failed"
        receipts.write(out / "report.json", result)
    print(f"{'ok' if result['passed'] else 'FAIL'} boot-crypto target: {out / 'report.json'}; "
          "scalar signature comparison; firmware join separate")
    return 0 if result["passed"] else 1


TABLE: Table = {"run": (cmd_run, "standard vectors, refusal controls and independent oracle"),
                "target": (cmd_target, "real signature interfaces through the accepted scalar backend")}


def _flags(name: str, parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", help="native lane output directory")
    parser.add_argument("--first", action="store_true", help="first positive per scheme only; incomplete evidence")
    if name == "run":
        parser.add_argument("--gallina", action="store_true", help="also compare the exact ML-DSA Gallina reference")
    else:
        parser.add_argument("--ccomp", required=True, help="accepted contained compiler")
        parser.add_argument("--ccomp-arg", action="append", default=[], help="compiler argument, repeatable")
        parser.add_argument("--simulator", required=True, help="golden model executable")
        parser.add_argument("--build-receipt", required=True, help="successful matching model build receipt")
        parser.add_argument("--timeout", type=int, default=1200, help="seconds per target case")
        parser.add_argument("--inst-limit", type=int, default=500_000_000, help="instructions per target case")
        parser.add_argument("--jobs", type=int, choices=range(1, 7), default=1, help="isolated target cases in parallel")


def main(argv: list[str] | None = None) -> int:
    return dispatch(__doc__, TABLE, argv, _flags, prog="run.py boot-crypto")
