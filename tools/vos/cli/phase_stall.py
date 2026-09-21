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
                     "the instrument refuses named slots on different harts whose phase ranges "
                     "overlap and cannot check serial execution beyond that",
    "residency_coverage": "the join compares declared intervals at the model's boundaries and "
                          "verifies no residency coverage: it has no timer or handler model and "
                          "no way to detect an input measured at other boundaries",
    "arbiter_class": "bounds hold for every arbiter that refuses a contender only for a busy "
                     "zero-path bank, an exhausted phase grant or a same-cycle conflict for a "
                     "zero-path bank and accepts every contender it can; a per-bank rotation and "
                     "an arbiter serialising same-cycle nonzero-path pairs are outside that class",
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
    # The receipt binds the instrument and every input it managed to read, so a
    # refusal still names the sources and the digests read before it.
    report["sources_sha256"] = {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCES
    }
    digests: dict[str, Json] = {}
    report["inputs_sha256"] = digests
    joined: dict[str, Json] | None = None
    try:
        program_raw = args.program.read_bytes()
        digests["program"] = hashlib.sha256(program_raw).hexdigest()
        resources_raw = args.resources.read_bytes()
        digests["resources"] = hashlib.sha256(resources_raw).hexdigest()
        analysis = phase_stall.analyze(program_raw, resources_raw)
        if args.costs is not None:
            cost_raw = args.costs.read_bytes()
            digests["costs"] = hashlib.sha256(cost_raw).hexdigest()
            comparison = phase_cost.parse(cost_raw)
            phase_stall.verify_identity(comparison, analysis, args.costs, args.program)
            phase_stall.verify_slots(comparison, analysis)
            if not analysis.stalled.refuted:
                joined = phase_stall.join(analysis, comparison)
        report["analysis"] = asdict(analysis)
        report["join"] = joined
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
                  f"drain_max={slot.drain_max}, cut_max={slot.cut_max}")
        if joined is not None:
            _print_join(joined)
        elif args.costs is not None:
            print("join: skipped (program contract refuted)")
        print("declared programs only; target comparison open")
    return 1 if refuted else 0


def _interval(value: Json) -> str:
    if isinstance(value, list) and len(value) == 2:
        return f"[{value[0]}, {value[1]}]"
    return "unknown" if value is None else str(value)


def _compared(term: Json) -> str:
    if not isinstance(term, dict):
        raise TypeError("a joined term is an object")
    return f"declared {_interval(term['declared'])} modeled {term['modeled']} {term['status']}"


def _print_join(joined: dict[str, Json]) -> None:
    slots = joined["slots"]
    unjoined = joined["unjoined"]
    reasons = joined["reasons"]
    if not isinstance(slots, list) or not isinstance(unjoined, list) \
            or not isinstance(reasons, list):
        raise TypeError("the join carries lists of slots, unjoined slots and reasons")
    for slot in slots:
        if not isinstance(slot, dict):
            raise TypeError("a joined slot is an object")
        switches = slot["switches"]
        declared = switches["declared"] if isinstance(switches, dict) else switches
        print(f"join {slot['id']}: stalls {_compared(slot['stalls'])}; "
              f"trap_per_switch {_compared(slot['residency'])}; switches {declared}; "
              f"cut_max {slot['cut_max']}")
    print(f"join drain: {_compared(joined['drain'])}")
    names = [f"{entry['hart']}/{entry['slot']}" for entry in unjoined if isinstance(entry, dict)]
    print(f"join unjoined: {', '.join(names) if names else 'none'}")
    print("; ".join([f"join: {joined['join_verdict']}", *(str(reason) for reason in reasons)]))
