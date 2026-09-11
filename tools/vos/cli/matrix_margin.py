# SPDX-License-Identifier: Apache-2.0
"""Check a sustained GEMM report against its independently supplied campaign plan."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from vos.matrix_margin import compare


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py matrix-margin", description=__doc__)
    parser.add_argument("plan", type=Path, help="reviewed matrix-margin-plan-v1 JSON")
    parser.add_argument("report", type=Path, help="matrix-margin-report-v1 measurements")
    parser.add_argument("--json", action="store_true", help="emit exact ratios and source identities")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    try:
        result = compare(args.plan.read_bytes(), args.report.read_bytes())
        sources = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                   for name in ("tools/vos/matrix_margin.py", "tools/vos/cli/matrix_margin.py",
                                "docs/implementation/matrix-margin-contract.md")}
    except (OSError, ValueError, RecursionError) as error:
        if args.json:
            print(json.dumps({"verdict": "incomplete", "reason": str(error),
                              "milestone_acceptance": "open"}, indent=2))
        else:
            print(f"FAIL matrix-margin: {error}")
        return 1
    if args.json:
        print(json.dumps({"verdict": "compared", "milestone_acceptance": "open",
                          "sources_sha256": sources, **asdict(result)}, indent=2))
    else:
        print(f"ok matrix-margin: {result.band}; wider per-watt: {result.wider_per_watt}")
        for row in result.cases:
            print(f"  {row.id} ({row.dtype}): throughput {row.throughput}, "
                  f"per-watt {row.per_watt}; {row.band}; wider per-watt: {row.wider_per_watt}")
        print("supplied measurements only; M0.8c admission remains open")
    return 0
