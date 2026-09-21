# SPDX-License-Identifier: Apache-2.0
"""Bound memory-issue stalls, boundary residency and drain over declared per-hart programs."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from vos import phase_cost, phase_stall
from vos.jsonc import Json

SOURCES = ("tools/vos/phase_stall.py", "tools/vos/cli/phase_stall.py",
           "tools/tests/test_phase_stall.py",
           "docs/implementation/phase-service/stall-contract.md")

NOT_ESTABLISHED = ("the actual arbiter", "pipeline backpressure", "mode changes and initial states",
                   "instruction-stream correspondence", "qualified occupancies and refresh", "WCET")

STATEMENTS = {
    "serial_domain": "the named cost slots must belong to harts of one serial admission domain; "
                     "the instrument cannot check that condition",
    "residency_coverage": "the join compares declared intervals at the model's boundaries and "
                          "verifies no residency coverage: it has no timer or handler model and "
                          "no way to detect an input measured at other boundaries",
    "arbiter_class": "bounds hold for every arbiter that refuses a contender only for a busy "
                     "zero-path bank, an exhausted phase grant or a same-cycle conflict and "
                     "accepts every contender it can; a per-bank rotation is outside that class",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py phase-stall", description=__doc__)
    parser.add_argument("program", type=Path, help="phase-program-v1 JSON declaration")
    parser.add_argument("resources", type=Path, help="digest-bound phase-resources-v1 JSON")
    parser.add_argument("--costs", type=Path, metavar="COSTS",
                        help="phase-cost input whose schedule object names the program")
    parser.add_argument("--json", action="store_true", help="emit the analysis, join and receipt")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    report: dict[str, Json] = {
        "scope": "declared-program-stall-bounds",
        "target_comparison": "open",
        "not_established": list(NOT_ESTABLISHED),
        "statements": dict(STATEMENTS),
        "program": str(args.program), "resources": str(args.resources),
        "costs": None if args.costs is None else str(args.costs),
    }
    joined: dict[str, Json] | None = None
    try:
        program_raw = args.program.read_bytes()
        resources_raw = args.resources.read_bytes()
        digests: dict[str, Json] = {"program": hashlib.sha256(program_raw).hexdigest(),
                                    "resources": hashlib.sha256(resources_raw).hexdigest()}
        report["inputs_sha256"] = digests
        analysis = phase_stall.analyze(program_raw, resources_raw)
        if args.costs is not None:
            cost_raw = args.costs.read_bytes()
            digests["costs"] = hashlib.sha256(cost_raw).hexdigest()
            comparison = phase_cost.parse(cost_raw)
            phase_stall.verify_identity(comparison, analysis, args.costs, args.program)
            if not analysis.stalled.refuted:
                joined = phase_stall.join(analysis, comparison)
        report["analysis"] = asdict(analysis)
        report["join"] = joined
        report["sources_sha256"] = {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCES
        }
    except (OSError, TypeError, ValueError) as err:
        report["error"] = str(err)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"malformed or stale program, resources or costs: {err}")
        return 2
    stalled = analysis.stalled
    refuted = stalled.refuted or (joined is not None and joined["join_verdict"] == "refuted")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{analysis.name}: closed={stalled.closed}, ordered={stalled.ordered}, "
              f"reason={stalled.reason}, states={stalled.states}, "
              f"expansion={analysis.expansion}, zero_wait={analysis.zero_wait}, "
              f"program_zero_wait={analysis.program_zero_wait}")
        for slot in stalled.slots:
            print(f"  {slot.hart}/{slot.slot}: stall_total_max={slot.stall_total_max}, "
                  f"stall_single_max={slot.stall_single_max}, "
                  f"boundary_outstanding={slot.boundary_outstanding}, "
                  f"boundary_residency_max={slot.boundary_residency_max}, "
                  f"drain_max={slot.drain_max}")
        if joined is not None:
            print(f"join: {joined['join_verdict']}; {joined['reasons']}")
        print("declared programs only; target comparison open")
    return 1 if refuted else 0
