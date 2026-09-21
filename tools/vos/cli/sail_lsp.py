# SPDX-License-Identifier: Apache-2.0
"""Guest-only optional native Sail language server commands."""

import argparse
import json
import subprocess
import sys

from vos import env, saillsp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py sail-lsp", description=saillsp.NOTICE)
    commands = parser.add_subparsers(dest="operation", required=True)
    for operation in ("install", "status", "serve", "qualify"):
        command = commands.add_parser(operation)
        if operation != "serve":
            command.add_argument("--json", action="store_true")
        if operation == "qualify":
            command.add_argument("--timeout", type=float, default=90,
                                 help="per-operation bound in seconds (1..600; default 90)")
    args = parser.parse_args(argv)
    try:
        environment = env.load()
        if args.operation == "serve":
            return saillsp.serve(environment)
        if args.operation == "qualify":
            if not 1 <= args.timeout <= 600:
                parser.error("--timeout must be between 1 and 600 seconds")
            report = saillsp.qualify(environment, timeout=args.timeout)
        else:
            report = saillsp.install(environment) if args.operation == "install" else saillsp.status(environment)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"sail-lsp: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 1 if report.get("all_required_checks_passed") is False else 0
