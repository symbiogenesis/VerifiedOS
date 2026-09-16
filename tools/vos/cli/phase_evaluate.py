# SPDX-License-Identifier: Apache-2.0
"""Join declared schedule, completion and cost evidence for the zero-wait branch."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from vos import phase_completion, phase_cost, phase_schedule, phase_service
from vos.jsonc import Json


def _join(acceptance: phase_service.Result, completion: phase_completion.Result,
          costs: phase_cost.Comparison, arithmetic: dict[str, Json]) -> tuple[str, str]:
    if not acceptance.zero_wait:
        return "refuted", "the declared zero-wait service branch is refuted; stalled execution is unmodeled"
    if completion.ordered is False or completion.drain_status == "blocked":
        return "refuted", "declared completion order or quiescent drain is refuted"
    if arithmetic["arithmetic_verdict"] == "refuted":
        return "refuted", "a declared candidate cost budget is definitely violated"
    declared = costs.d_pipe_completion
    required = completion.quiescent_drain
    if declared is None or required is None or completion.ordered is None:
        return "open", "the joined completion-drain bound is unavailable"
    if declared.high < required:
        return "refuted", "the declared candidate drain is below the modeled completion bound"
    if declared.low < required:
        return "inconclusive", "the declared drain interval overlaps values below the modeled bound"
    verdict = arithmetic["arithmetic_verdict"]
    if not isinstance(verdict, str):
        raise TypeError("cost analysis returned no arithmetic verdict")
    return verdict, "service and completion close; the scoped cost arithmetic decides the join"


def _verify_schedule(costs: phase_cost.Comparison, extraction: phase_schedule.Extraction,
                     cost_path: Path, schedule_path: Path) -> None:
    cost_schedule = Path(costs.schedule_path)
    if not cost_schedule.is_absolute():
        cost_schedule = cost_path.resolve().parent / cost_schedule
    if (cost_schedule.resolve() != schedule_path.resolve()
            or costs.schedule_sha256 != extraction.schedule_sha256
            or costs.schedule_id != extraction.name):
        raise ValueError("cost schedule path, SHA-256 and id must match the extracted schedule")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py phase-evaluate", description=__doc__)
    parser.add_argument("schedule", type=Path)
    parser.add_argument("resources", type=Path)
    parser.add_argument("--costs", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    report: dict[str, Json] = {
        "scope": "declared-single-mode-zero-wait-comparison",
        "target_comparison": "open",
        "open_because": ["actual schedule, instruction-stream and arbiter correspondence",
                         "initial states and mode transitions", "qualified memory and timing",
                         "whole-image WCET and physical area/power evidence",
                         "architectural ordering and visibility refinement",
                         "second-class baseline decision where applicable"],
    }
    try:
        schedule_raw = args.schedule.read_bytes()
        resources_raw = args.resources.read_bytes()
        cost_raw = args.costs.read_bytes()
        extraction = phase_schedule.extract(schedule_raw, resources_raw)
        costs = phase_cost.parse(cost_raw)
        _verify_schedule(costs, extraction, args.costs, args.schedule)
        acceptance = phase_service.check(extraction.contract)
        completion = phase_completion.check(extraction.contract)
        arithmetic = phase_cost.assess(costs)
        verdict, reason = _join(acceptance, completion, costs, arithmetic)
        emitted = phase_schedule.contract_bytes(extraction.contract)
        report.update({
            "branch_verdict": verdict, "reason": reason,
            "schedule_id": extraction.name, "workload": costs.workload,
            "domain_id": costs.domain_id,
            "clock": {"id": costs.clock_id, "hz": costs.clock_hz},
            "inputs_sha256": {"schedule": extraction.schedule_sha256,
                              "resources": extraction.resources_sha256,
                              "costs": hashlib.sha256(cost_raw).hexdigest(),
                              "contract": hashlib.sha256(emitted).hexdigest()},
            "contract": asdict(extraction.contract),
            "acceptance": asdict(acceptance), "completion": asdict(completion),
            "cost": arithmetic,
        })
        sources = ("tools/vos/cli/phase_evaluate.py", "tools/vos/phase_schedule.py",
                   "tools/vos/phase_service.py", "tools/vos/phase_completion.py",
                   "tools/vos/phase_cost.py", "tools/tests/test_phase_pipeline.py",
                   "docs/implementation/phase-service/prerequisite-contract.md")
        report["sources_sha256"] = {
            path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in sources
        }
    except (OSError, TypeError, ValueError) as error:
        report.update({"branch_verdict": "malformed", "error": str(error)})
        print(json.dumps(report, indent=2) if args.json else f"malformed comparison join: {error}")
        return 2
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"declared zero-wait branch: {verdict}; {reason}")
        print("target comparison open; this join does not qualify supplied evidence")
    return 1 if verdict == "refuted" else 0
