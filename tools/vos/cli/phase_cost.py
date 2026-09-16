# SPDX-License-Identifier: Apache-2.0
"""Compare declared workload costs; arithmetic success never closes target Q22e."""

import argparse
import hashlib
import json
from pathlib import Path

from vos.jsonc import Json
from vos.phase_cost import assess, bind_schedule, parse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, metavar="FILE")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    sources = ("tools/vos/phase_cost.py", "tools/vos/cli/phase_cost.py",
               "tools/tests/test_phase_cost.py",
               "docs/implementation/phase-service/prerequisite-contract.md",
               "docs/implementation/phase-service/cost-input.md")
    report: dict[str, Json] = {
        "scope": "declared-workload-cost-arithmetic", "target_comparison": "open",
        "open_because": ["workload completeness", "WCET soundness", "memory and timing qualification",
                         "ordering refinement", "physical correspondence"],
        "input": str(args.input.resolve()),
        "sources_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                           for name in sources},
    }
    try:
        raw = args.input.read_bytes()
        report["input_sha256"] = hashlib.sha256(raw).hexdigest()
        report["input_bytes"] = len(raw)
        comparison = parse(raw)
        report["schedule"] = bind_schedule(comparison, args.input)
        report["workload"] = comparison.workload
        report["domain"] = {"id": comparison.domain_id, "kind": "serial"}
        report["clock"] = {"id": comparison.clock_id, "hz": comparison.clock_hz}
        report["units"] = {"time": "cycles", "area": "um2", "power": "uW"}
        result = assess(comparison)
        report["result"] = result
    except (OSError, ValueError, TypeError) as err:
        report["error"] = str(err)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"malformed comparison: {err}")
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{comparison.workload}: arithmetic={result['arithmetic_verdict']}; {result['reason']}")
        print("target comparison open: declared arithmetic does not establish qualification")
    return 1 if result["arithmetic_verdict"] == "refuted" else 0
