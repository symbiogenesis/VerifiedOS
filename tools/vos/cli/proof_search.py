# SPDX-License-Identifier: Apache-2.0
"""Portable lexical proof-example retrieval, with human and versioned JSON output."""

import argparse
import json
import sys

from vos import proofsearch
from vos.corpus import find_root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run.py proof-search",
        description="Search current local Rocq sources; every result is advisory only.")
    parser.add_argument("query", nargs="?", default="",
                        help="query words (OR); name matches rank above statements and scripts")
    parser.add_argument("--tactic", action="append", default=[], metavar="WORD",
                        help="require an exact script identifier token (repeatable, AND)")
    parser.add_argument("--requirement", action="append", default=[], metavar="ID",
                        help="require a file-level authored requirement citation (repeatable, AND)")
    parser.add_argument("--exclude", action="append", default=[], metavar="proofs/Name.v",
                        help="omit an existing source with exact path spelling (repeatable)")
    parser.add_argument("--limit", type=int, default=5, help="maximum results, 1..50 (default: 5)")
    parser.add_argument("--max-chars", type=int, default=1600,
                        help="maximum characters per excerpt, 256..16000 (default: 1600)")
    parser.add_argument("--json", action="store_true",
                        help="version 1 JSON described by tools/proof-search.schema.json")
    args = parser.parse_args(argv)
    try:
        proofsearch.validate(args.query, tuple(args.tactic), tuple(args.requirement),
                             tuple(args.exclude), args.limit, args.max_chars)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        report = proofsearch.search(
            find_root(), args.query, tactics=tuple(args.tactic),
            requirements=tuple(args.requirement), exclude=tuple(args.exclude),
            limit=args.limit, max_chars=args.max_chars)
    except (OSError, ValueError) as exc:
        print(f"proof-search: {exc}", file=sys.stderr)
        return 1
    if args.json:
        # ASCII escapes are valid UTF-8 JSON even on a legacy Windows console.
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 0
    lines = [proofsearch.ADVISORY,
             f"{len(report['matches'])} of {report['total_matches']} match(es); "
             f"{report['sources_read']} source(s) read."]
    for hit in report["matches"]:
        lines.extend(["", f"{hit['path']}:{hit['line']}:{hit['column']} (through line {hit['end_line']}) "
                      f"{hit['kind']} {hit['name']} [{hit['status']}; score {hit['score']}]",
                      f"source SHA-256: {hit['source_sha256']}",
                      "file citations: " + (", ".join(hit["requirements"]) or "none"),
                      hit["excerpt"]])
        if hit["excerpt_truncated"]:
            lines.append("[excerpt truncated]")
    if report["truncated"]:
        lines.append("[result list truncated]")
    print("\n".join(lines))
    return 0
