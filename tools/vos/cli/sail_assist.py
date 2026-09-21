# SPDX-License-Identifier: Apache-2.0
"""Record bounded Sail repair sessions and preserve actual compiler diagnostics."""

import argparse
import json
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

from vos import env, sailassist


def _check_checkout(e: env.Environment) -> None:
    checkout = Path(__file__).resolve().parents[3]
    if e.root.resolve() != checkout or e.model.resolve() != checkout / "model":
        raise ValueError("sail-assist requires this checkout's root and model; VOS_ROOT/VOS_MODEL overrides are unsupported")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py sail-assist", description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    for action in ("init", "status", "typecheck", "pause", "resume", "replan", "finish", "recover"):
        command = subs.add_parser(action)
        command.add_argument("session")
        command.add_argument("--json", action="store_true")
        if action == "init":
            command.add_argument("--plan", type=Path, required=True)
            command.add_argument("--attempt-limit", type=int, default=12)
            command.add_argument("--active-seconds", type=int, default=1800)
        elif action == "typecheck":
            command.add_argument("--change", required=True)
            command.add_argument("--timeout", type=float, default=600)
        elif action != "status":
            command.add_argument("--note", required=True)
    args = parser.parse_args(argv)
    try:
        with redirect_stdout(sys.stderr):
            e = env.load(toolchain=args.action == "typecheck")
        _check_checkout(e)
        directory = sailassist.session_dir(e.lane_root, args.session)
        code = 0
        with env.hold_lock(directory, "a Sail assistance session"):
            if args.action == "init":
                result = sailassist.status(sailassist.initialize(
                    e.root, directory, sailassist.read_json(args.plan), args.attempt_limit, args.active_seconds))
            elif args.action == "typecheck":
                result, code = sailassist.typecheck(e.root, directory, e.log_root / f"sail-assist-{e.lane or 'main'}",
                                                   args.change, args.timeout)
            elif args.action == "status":
                result = sailassist.status(sailassist.load(directory))
            else:
                result = sailassist.status(sailassist.transition(e.root, directory, args.action, args.note))
    except (OSError, TypeError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"sail-assist: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=True, indent=2, allow_nan=False))
    else:
        print(f"{args.session}: {result['checkpoint']['state']}; "
              f"{len(result['checkpoint']['attempts'])} attempt(s); "
              f"{result['remaining_seconds']:.1f}s remaining")
        print(result["reason"] or result["checkpoint"]["next_action"])
        print("Advisory handoff journal; acceptance requires the artifact's existing gates.")
    return code
