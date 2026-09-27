# SPDX-License-Identifier: Apache-2.0
"""Compare bounded signature verification C with pinned ACVP and OpenSSL."""

import argparse
import json
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
    modes = tuple(args.mode) if args.mode else boot_crypto_target.MODES
    with env.hold_lock(out, "boot signature target comparison"):
        receipts.write(out / "report.json", {"passed": False, "status": "incomplete",
                                              "milestone_acceptance": "open"})
        try:
            result = boot_crypto_target.run(e.root, out, None if args.staged else Path(args.ccomp),
                args.ccomp_arg, Path(args.simulator), Path(args.build_receipt), args.timeout,
                args.inst_limit, args.first, args.jobs, modes)
        except (OSError, ValueError, TypeError, KeyError, RuntimeError,
                subprocess.SubprocessError) as error:
            receipts.write(out / "report.json", {"passed": False, "status": "failed", "error": str(error),
                                                 "milestone_acceptance": "open"})
            print(f"FAIL boot-crypto target: {error}")
            return 1
        result["status"] = "passed" if result["passed"] else "failed"
        receipts.write(out / "report.json", result)
    print(f"{'ok' if result['passed'] else 'FAIL'} boot-crypto target: {out / 'report.json'}; "
          "scalar signature comparison; firmware join separate")
    return 0 if result["passed"] else 1


def cmd_stage(args: argparse.Namespace) -> int:
    e = env.load()
    out = Path(args.out) if args.out else e.lane_root / "boot-crypto-stage"
    out.mkdir(parents=True, exist_ok=True)
    with env.hold_lock(out, "boot signature staging"):
        receipts.write(out / "stage.json", {"passed": False, "status": "incomplete"})
        try:
            result = boot_crypto_target.stage(e.root, out, Path(args.ccomp), args.ccomp_arg, args.check)
        except (OSError, ValueError, TypeError, KeyError, RuntimeError,
                subprocess.SubprocessError) as error:
            receipts.write(out / "stage.json", {"passed": False, "status": "failed", "error": str(error)})
            print(f"FAIL boot-crypto stage: {error}")
            return 1
        receipts.write(out / "stage.json", result)
    if not result["passed"]:
        for name in result["differences"]:
            print(f"FAIL boot-crypto stage --check: {boot_crypto_target.STAGED}/{name} differs")
        return 1
    done = "matches the compiler" if args.check else "written"
    print(f"ok boot-crypto stage: {boot_crypto_target.STAGED} {done}; receipt {out / 'stage.json'}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    try:
        manifest, _ = boot_crypto_target.staged(env.load(toolchain=False).root)
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"FAIL boot-crypto verify: {error}")
        return 1
    print(f"ok boot-crypto verify: {len(manifest['modes'])} staged streams match "
          f"{boot_crypto_target.MANIFEST} and {len(manifest['sources_sha256'])} source files")
    return 0


def cmd_join(args: argparse.Namespace) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        reports = {name: json.loads(Path(name).read_text(encoding="utf-8")) for name in args.reports}
        result = boot_crypto_target.join(reports)
    except (OSError, ValueError, TypeError, KeyError) as error:
        receipts.write(out / "report.json", {"passed": False, "status": "failed", "error": str(error),
                                              "milestone_acceptance": "open"})
        print(f"FAIL boot-crypto join: {error}")
        return 1
    result["shard_reports_sha256"] = {name: receipts.digest(Path(name)) for name in args.reports}
    receipts.write(out / "report.json", result)
    print(f"{'ok' if result['passed'] else 'FAIL'} boot-crypto join: {out / 'report.json'}; "
          f"{len(result['cases'])} of {sum(map(len, result['selection'].values()))} cases executed")
    return 0 if result["passed"] else 1


TABLE: Table = {"run": (cmd_run, "standard vectors, refusal controls and independent oracle"),
                "target": (cmd_target, "real signature interfaces through the accepted scalar backend"),
                "stage": (cmd_stage, "compile the tracked target streams, or --check them"),
                "verify": (cmd_verify, "hold the tracked target streams to their manifest and sources"),
                "join": (cmd_join, "compose interface shard reports into one campaign receipt")}


def _flags(name: str, parser: argparse.ArgumentParser) -> None:
    if name == "join":
        parser.add_argument("--out", required=True, help="directory for the joined report.json")
        parser.add_argument("reports", nargs="+", help="shard report.json files, one or more interfaces each")
        return
    if name == "verify":
        return
    parser.add_argument("--out", help="native lane output directory")
    if name == "stage":
        parser.add_argument("--ccomp", required=True, help="accepted contained compiler")
        parser.add_argument("--ccomp-arg", action="append", default=[], help="compiler argument, repeatable")
        parser.add_argument("--check", action="store_true", help="compare with the tracked streams; write nothing")
        return
    parser.add_argument("--first", action="store_true", help="first positive per scheme only; incomplete evidence")
    if name == "run":
        parser.add_argument("--gallina", action="store_true", help="also compare the exact ML-DSA Gallina reference")
        return
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--ccomp", help="accepted contained compiler")
    source.add_argument("--staged", action="store_true",
                        help=f"execute the tracked streams under {boot_crypto_target.STAGED}")
    parser.add_argument("--ccomp-arg", action="append", default=[], help="compiler argument, repeatable")
    parser.add_argument("--mode", action="append", choices=boot_crypto_target.MODES,
                        help="interface to execute, repeatable; default all five")
    parser.add_argument("--simulator", required=True, help="golden model executable")
    parser.add_argument("--build-receipt", required=True, help="successful matching model build receipt")
    parser.add_argument("--timeout", type=int, default=1200, help="seconds per target case")
    parser.add_argument("--inst-limit", type=int, default=500_000_000, help="instructions per target case")
    parser.add_argument("--jobs", type=int, choices=range(1, 7), default=1, help="isolated target cases in parallel")


def main(argv: list[str] | None = None) -> int:
    return dispatch(__doc__, TABLE, argv, _flags, prog="run.py boot-crypto")
