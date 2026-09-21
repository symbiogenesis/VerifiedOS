# SPDX-License-Identifier: Apache-2.0
"""Portable navigation of fresh recorded Sail source owners through the bundle."""

import argparse
import json
import sys

from vos import sailbundle, sailcontext
from vos.corpus import find_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py sail-context", description=sailcontext.NOTICE)
    commands = parser.add_subparsers(dest="operation", required=True)
    for operation, help_text in (("search", "rank local declaration examples by words"),
                                 ("symbol", "find an exact symbol across kinds and clauses"),
                                 ("references", "find compiler-recorded incoming links")):
        command = commands.add_parser(operation, help=help_text)
        command.add_argument("query", metavar="QUERY" if operation == "search" else "NAME")
        command.add_argument("--json", action="store_true", help="versioned JSON Schema output")
        command.add_argument("--limit", type=int, default=5, help="result bound, 1..50 (default: 5)")
        command.add_argument("--max-chars", type=int, default=1600,
                             help="excerpt character bound, 256..16000 (default: 1600)")
        if operation == "search":
            command.add_argument("--kind", choices=sailcontext.KINDS, action="append", default=[],
                                 help="declaration kind; repeat for alternatives")
            command.add_argument("--exclude", action="append", default=[], metavar="PATH",
                                 help="exact recorded model/model/... owner to omit; repeatable")
        else:
            command.set_defaults(kind=[], exclude=[])
    args = parser.parse_args(argv)
    try:
        sailcontext.validate(args.operation, args.query, tuple(args.kind), tuple(args.exclude),
                             args.limit, args.max_chars)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        report = sailcontext.context(find_root(), args.operation, args.query,
                                     kinds=tuple(args.kind), exclude=tuple(args.exclude),
                                     limit=args.limit, max_chars=args.max_chars)
    except (OSError, ValueError, sailbundle.BundleError) as exc:
        print(f"sail-context: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 0
    lines = [report["notice"], f"bundle SHA-256: {report['bundle_sha256']}",
             f"{len(report['matches'])} of {report['total_matches']} local match(es); "
             f"{report['sources_checked']} recorded owner(s) checked.",
             f"Omitted matching entries: {report['omitted_matches']['unlocated']} unlocated, "
             f"{report['omitted_matches']['unrecorded']} without a recorded local owner."]
    if report["known_symbol"] is False:
        lines.append("The compiler bundle records no such symbol or link target.")
    for hit in report["matches"]:
        label = f"{hit['kind']} {hit['symbol']}"
        if hit["target"] is not None:
            label += f" -> {hit['reference_kind']} {hit['target']}"
        lines.extend(["", f"{hit['path']}:{hit['line']}:{hit['column']} {label}",
                      f"source SHA-256: {hit['source_sha256']}", hit["excerpt"]])
        if hit["excerpt_truncated"]:
            lines.append("[excerpt truncated]")
    if report["truncated"]:
        lines.append("[result list truncated]")
    print("\n".join(lines))
    return 0
