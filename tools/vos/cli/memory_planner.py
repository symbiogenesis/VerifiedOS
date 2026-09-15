# SPDX-License-Identifier: Apache-2.0
"""Check and improve portable fixed-instance memory plans with separate evidence."""

import argparse
import hashlib
import json
from functools import partial
from pathlib import Path
from typing import Any

from vos import env
from vos import memory_planner as planner
from vos import memory_planner_adapters as adapters
from vos import memory_planner_contracts as contracts
from vos import memory_planner_resources as resources
from vos.corpus import find_root


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("action", choices=("plan", "check", "solve", "verify", "demo", "contracts",
                                          "resources", "resource-proof", "demo-tflm"))
    result.add_argument("--instance", type=Path, help="portable instance JSON")
    result.add_argument("--baseline", type=Path, help="standing placement JSON, checked first")
    result.add_argument("--candidate", type=Path, action="append", default=[],
                        help="candidate placement JSON; repeat for a portfolio")
    result.add_argument("--contract", type=Path, help="bounded component contract JSON")
    result.add_argument("--resource-budget", type=Path,
                        help="resource contract JSON including placement, budgets and event costs")
    result.add_argument("--evidence", type=Path, help="complete result JSON for independent replay")
    result.add_argument("--work-budget", type=int, default=0,
                        help="deterministic optional search budget; zero retains supplied candidates")
    result.add_argument("--certify", action="store_true", help="request independent finite optimality replay")
    result.add_argument("--replay-budget", type=int, default=100000)
    result.add_argument("--json", action="store_true", help="emit the full result and evidence")
    return result


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def read_json(path: Path, inputs: dict[str, str]) -> object:
    """Hash the bytes actually parsed, without rereading a mutable input."""
    data = path.read_bytes()
    inputs[str(path)] = hashlib.sha256(data).hexdigest()
    return json.loads(data, object_pairs_hook=unique_object)


def source_identity(root: Path) -> dict[str, str]:
    names = ("tools/vos/memory_planner.py", "tools/vos/memory_planner_contracts.py",
             "tools/vos/memory_planner_adapters.py", "tools/vos/memory_planner_resources.py",
             "tools/vos/cli/memory_planner.py", "proofs/MemoryPlannerContracts.v",
             "proofs/MemoryPlannerResources.v")
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def load_candidate(path: Path, inputs: dict[str, str], _: planner.Instance) -> planner.Placement:
    """Optional input is read only after the baseline has been checked and retained."""
    raw = read_json(path, inputs)
    if not isinstance(raw, list):
        raise TypeError("candidate placement must be an array")
    return raw


def service_demo() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Four asynchronous workers, each with exclusive scratch phases, in bytes."""
    unit = 1024 * 1024
    buffers: list[dict[str, Any]] = []
    baseline: list[dict[str, Any]] = []
    candidate: list[dict[str, Any]] = []
    for worker in range(4):
        for phase, size, start in (("a", 4, 0), ("b", 3, 1)):
            name = f"worker-{worker}-{phase}"
            buffers.append({"id": name, "size": size * unit, "alignment": unit,
                            "intervals": [[start, start + 1]], "allowed_pools": ["scratch"]})
            baseline.append({"id": name, "pool": "scratch",
                             "offset": (worker * 7 + (4 if phase == "b" else 0)) * unit})
            candidate.append({"id": name, "pool": "scratch", "offset": worker * 4 * unit})
    conflicts = [[left["id"], right["id"]]
                 for i, left in enumerate(buffers) for right in buffers[i + 1:]
                 if left["id"].split("-")[1] != right["id"].split("-")[1]]
    instance = {
        "name": "bounded-service-four-workers",
        "pools": [{"id": "scratch", "capacity": 28 * unit}],
        "buffers": buffers, "conflicts": conflicts,
        "assumptions": ["Each worker finishes all phase-A users before phase B.",
                        "Workers progress independently; cross-worker conflicts are explicit.",
                        "Synthetic scratch only; metadata and target timing are unmeasured."],
    }
    return instance, baseline, candidate


def run(args: argparse.Namespace, inputs: dict[str, str]) -> dict[str, Any]:
    if args.work_budget < 0 or args.replay_budget < 1:
        raise ValueError("work budget must be nonnegative and replay budget positive")
    # Refuse unused input files before dispatch can silently replace a caller's
    # standing plan, contract or evidence with another action's defaults.
    input_actions: dict[str, set[str]] = {
        "instance": {"plan", "check", "solve", "verify"},
        "baseline": {"plan"},
        "candidate": {"plan", "check"},
        "contract": {"contracts"},
        "resource_budget": {"resources", "resource-proof"},
        "evidence": {"verify"},
    }
    for option, actions in input_actions.items():
        if getattr(args, option) and args.action not in actions:
            flag = "--" + option.replace("_", "-")
            raise ValueError(f"{flag} is only supported by {', '.join(sorted(actions))}")
    if args.action in {"resources", "resource-proof"}:
        if (args.instance or args.baseline or args.candidate or args.contract or args.evidence
                or args.work_budget or args.certify):
            raise ValueError("resource actions take the complete contract through --resource-budget")
        raw = read_json(args.resource_budget, inputs) if args.resource_budget else resources.demo_resources()
        report = resources.analyze_resources(raw, max_work=args.replay_budget)
        result = {"resource_contract": report, "status": report["status"], "errors": report["errors"]}
        if args.action == "resource-proof" and not report["errors"]:
            result["rocq_source"] = resources.emit_resource_certificate(raw, max_work=args.replay_budget)
        return result
    if args.action == "contracts":
        raw = read_json(args.contract, inputs) if args.contract else contracts.demo_contract()
        result = contracts.extract_contract(raw)
        planner.parse_instance(result["instance"])
        return result
    if args.action == "demo-tflm":
        root = find_root()
        output = env.lane_root(env.lane_of(root)) / "memory-planner-tflm"
        return adapters.tflm_demo(root, output)
    if args.action == "demo":
        raw, baseline, candidate = service_demo()
        instance = planner.parse_instance(raw)
        result = planner.plan(instance, baseline, candidates=(candidate,),
                              work_budget=args.work_budget, certify=args.certify,
                              replay_budget=args.replay_budget)
        result.update(instance=raw, baseline=baseline,
                      measurement_scope="constructed non-ML scratch example, not a target benchmark")
        return result
    if args.instance is None:
        raise ValueError("--instance is required for this action")
    instance = planner.parse_instance(read_json(args.instance, inputs))
    if args.action == "solve":
        return planner.solve(instance, work_budget=args.work_budget, certify=args.certify,
                             replay_budget=args.replay_budget)
    if args.action == "verify":
        if args.evidence is None:
            raise ValueError("verify requires --evidence")
        return {"evidence": planner.verify_evidence(
            instance, read_json(args.evidence, inputs), work_budget=args.replay_budget)}
    if args.action == "check":
        if len(args.candidate) != 1:
            raise ValueError("check requires exactly one --candidate")
        placement = read_json(args.candidate[0], inputs)
        return planner.plan(instance, placement, work_budget=0)
    if args.baseline is None:
        raise ValueError("plan requires --baseline")
    baseline = read_json(args.baseline, inputs)
    candidates = tuple(partial(load_candidate, path, inputs) for path in args.candidate)
    return planner.plan(instance, baseline, candidates=candidates,
                        work_budget=args.work_budget, certify=args.certify,
                        replay_budget=args.replay_budget)


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    inputs: dict[str, str] = {}
    result: dict[str, Any]
    try:
        result = run(args, inputs)
    except (OSError, ValueError, TypeError, KeyError) as err:
        result = {"evidence": {"status": "unknown/unsupported", "findings": [str(err)]}}
        code = 2
    else:
        evidence = result.get("evidence", {})
        if args.action in {"plan", "check", "demo", "solve"}:
            code = 0 if result.get("placement") is not None else 1
        elif args.action == "verify":
            code = 0 if evidence.get("status") in {"checked feasible", "checked optimal", "checked infeasible"} else 1
        else:
            code = 1 if result.get("errors") or evidence.get("findings") else 0
    result["input_sha256"] = inputs
    result["sources_sha256"] = source_identity(find_root())
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        evidence = result.get("evidence", {})
        print(evidence.get("status", result.get("status", "contract extracted")))
        for finding in evidence.get("findings", []):
            print(f"  {finding}")
        print("Use --json for placements, input identities, assumptions and evidence.")
    return code
