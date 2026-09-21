# SPDX-License-Identifier: Apache-2.0
"""Join declared schedule, completion and cost evidence for the zero-wait branch."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import cast

from vos import phase_completion, phase_cost, phase_modes, phase_schedule, phase_service
from vos.jsonc import Json

SINGLE_MODE_SCOPE = "declared-single-mode-zero-wait-comparison"
MODE_PRODUCT_SCOPE = "declared-mode-product-zero-wait-comparison"
OPEN_BECAUSE: tuple[str, ...] = (
    "actual schedule, instruction-stream and arbiter correspondence",
    "non-empty initial states",
    "mode-transition budget and dwell (R-15-247g, R-15-189i)",
    "the executive's own switch work",
    "edge-certificate correspondence and the recovery-state entry a failed edge takes "
    "after teardown (R-11-018)",
    "qualified occupancy and timing (R-15-247m)",
    "whole-image WCET and physical area/power evidence",
    "architectural ordering and visibility refinement",
    "qualified second-class service and timer-residency bounds (R-15-247m, R-07-040)",
)
# A term the join's arithmetic does not carry: a mode change adds no boundary visit,
# and the cost input's `switches` stays the declared slot-boundary count.
TERMS_NOT_CARRIED: tuple[str, ...] = (
    "mode-transition budget: a mode change adds no boundary visit and the cost input's "
    "switches remain the declared slot-boundary count",
)
SOURCES = ("tools/vos/cli/phase_evaluate.py", "tools/vos/phase_schedule.py",
           "tools/vos/phase_service.py", "tools/vos/phase_completion.py",
           "tools/vos/phase_cost.py", "tools/tests/test_phase_pipeline.py",
           "docs/implementation/phase-service/prerequisite-contract.md")
MODE_SOURCES = ("tools/vos/phase_modes.py", "docs/implementation/phase-service/mode-contract.md")

type Acceptance = phase_service.Result | phase_modes.ModeResult
type Completion = phase_completion.Result | phase_modes.ModeCompletionResult
type Read = phase_schedule.Extraction | phase_modes.ModeExtraction


def _join(acceptance: Acceptance, completion: Completion,
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


def _verify_schedule(costs: phase_cost.Comparison, extraction: Read,
                     cost_path: Path, schedule_path: Path) -> None:
    cost_schedule = Path(costs.schedule_path)
    if not cost_schedule.is_absolute():
        cost_schedule = cost_path.resolve().parent / cost_schedule
    if (cost_schedule.resolve() != schedule_path.resolve()
            or costs.schedule_sha256 != extraction.schedule_sha256
            or costs.schedule_id != extraction.name):
        raise ValueError("cost schedule path, SHA-256 and id must match the extracted schedule")


def _check(extraction: Read) -> tuple[Acceptance, Completion, bytes, dict[str, Json], bool]:
    """Both verdicts, the emitted contract bytes and object, and whether a product was declared."""
    if isinstance(extraction, phase_modes.ModeExtraction):
        contract = extraction.contract
        return (phase_modes.check(contract), phase_modes.check_completion(contract),
                phase_modes.emitted_bytes(contract), phase_modes.emitted_json(contract),
                phase_modes.single_mode(contract) is None)
    contract = extraction.contract
    return (phase_service.check(contract), phase_completion.check(contract),
            phase_schedule.contract_bytes(contract), cast("dict[str, Json]", asdict(contract)),
            False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run.py phase-evaluate", description=__doc__)
    parser.add_argument("schedule", type=Path)
    parser.add_argument("resources", type=Path)
    parser.add_argument("--costs", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[3]
    report: dict[str, Json] = {
        "scope": SINGLE_MODE_SCOPE,
        "target_comparison": "open",
        "open_because": list(OPEN_BECAUSE),
        "terms_not_carried": list(TERMS_NOT_CARRIED),
    }
    try:
        schedule_raw = args.schedule.read_bytes()
        resources_raw = args.resources.read_bytes()
        cost_raw = args.costs.read_bytes()
        extraction = phase_modes.read(schedule_raw, resources_raw)
        costs = phase_cost.parse(cost_raw)
        _verify_schedule(costs, extraction, args.costs, args.schedule)
        acceptance, completion, emitted, contract, product = _check(extraction)
        arithmetic = phase_cost.assess(costs)
        verdict, reason = _join(acceptance, completion, costs, arithmetic)
        sources = SOURCES
        if isinstance(extraction, phase_modes.ModeExtraction):
            report["schema"] = phase_modes.SCHEMA
            sources += MODE_SOURCES
        else:
            report["schema"] = "phase-schedule-v1"
        if product:
            report["scope"] = MODE_PRODUCT_SCOPE
        report.update({
            "branch_verdict": verdict, "reason": reason,
            "schedule_id": extraction.name, "workload": costs.workload,
            "domain_id": costs.domain_id,
            "clock": {"id": costs.clock_id, "hz": costs.clock_hz},
            "inputs_sha256": {"schedule": extraction.schedule_sha256,
                              "resources": extraction.resources_sha256,
                              "costs": hashlib.sha256(cost_raw).hexdigest(),
                              "contract": hashlib.sha256(emitted).hexdigest()},
            "contract": contract,
            "acceptance": asdict(acceptance), "completion": asdict(completion),
            "cost": arithmetic,
        })
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
        print("target comparison open; this join does not qualify supplied evidence; "
              "the mode-transition budget is not carried")
    return 1 if verdict == "refuted" else 0
