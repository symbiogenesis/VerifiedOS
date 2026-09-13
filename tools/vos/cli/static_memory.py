# SPDX-License-Identifier: Apache-2.0
"""Replay static-memory placement, service, structure and reclamation experiments.

Service equivalence concerns a bounded research interpreter, without target admission.
Receipts bind the input bytes and working-tree implementation, including local edits.
"""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from time import perf_counter
from typing import Any

from vos import static_memory as oracle
from vos import static_memory_corpus as witnesses
from vos import static_memory_modes as mode_family
from vos import static_memory_reclaim as reclaim
from vos import static_memory_scale as scale
from vos import static_memory_structure as structure
from vos import static_memory_transform as transform

SOURCES = (
    "tools/vos/static_memory.py", "tools/vos/static_memory_corpus.py",
    "tools/vos/cli/static_memory.py", "proofs/MemoryPlan.v", "tools/vos/memplan.py",
    "docs/implementation/static-memory-baseline.md",
    "docs/implementation/static-memory-corpus.md",
    "docs/implementation/static-memory-experiments.md",
)

EXPERIMENT_SOURCES: dict[str, tuple[str, ...]] = {
    "structure": ("tools/vos/static_memory_structure.py",),
    "transform": ("tools/vos/static_memory_transform.py",
                  "docs/implementation/static-memory-transformations.md"),
    "reclaim": ("tools/vos/static_memory_reclaim.py",
                "docs/implementation/static-memory-reclamation.md",
                "tools/vos/revocation.py"),
    "scale": ("tools/vos/static_memory_scale.py",
              "docs/implementation/static-memory-scaling.md",
              "tools/vos/cli/placement.py"),
    "modes": ("tools/vos/static_memory_modes.py",
              "docs/implementation/static-memory-modes.md"),
}


def identity(root: Path, names: tuple[str, ...]) -> dict[str, Any]:
    """Bind the actual source bytes; a Git revision alone misses local changes."""
    revision = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
        text=True, check=True, timeout=30).stdout.strip()
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=normal"],
        capture_output=True, text=True, check=True, timeout=30).stdout
    return {
        "revision": revision,
        "working_tree_dirty": bool(status),
        "sources_sha256": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in names
        },
    }


def read_input(path: Path) -> tuple[object, str]:
    """Read once so parsing and receipt hashing refer to the same input bytes."""
    data = path.read_bytes()
    return json.loads(data), hashlib.sha256(data).hexdigest()


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    result.add_argument("action", choices=("corpus", "compare", "check",
                                          *EXPERIMENT_SOURCES))
    result.add_argument("--json", action="store_true", help="emit the replayable receipt")
    result.add_argument("--case", help="select one named synthetic witness")
    result.add_argument("--contract", type=Path, help="read one explicit research contract")
    result.add_argument("--candidate", type=Path, help="check a candidate against --contract")
    result.add_argument("--max-nodes", type=int,
                        help="bounded exact-search budget; exhaustion is incomplete")
    result.add_argument("--sizes", type=int, nargs="+",
                        help="scale only: positive synthetic family object counts")
    result.add_argument("--q5-max-leaves", type=int,
                        help="scale only: bounded existing Q5 enumeration leaves")
    return result


def experiment(args: argparse.Namespace, root: Path) -> int:
    """Keep new research receipts separate from ordinary supplied-plan checking."""
    receipt = identity(root, (*SOURCES, *EXPERIMENT_SOURCES[args.action]))
    if args.action == "structure":
        result = structure.report(receipt["revision"])
    elif args.action == "transform":
        result = transform.transformation_report(receipt["revision"])
    elif args.action == "reclaim":
        result = reclaim.report(root)
    elif args.action == "modes":
        result = mode_family.report(receipt["revision"])
    else:
        result = scale.report(root, receipt["revision"],
                              sizes=tuple(args.sizes or (8, 32, 128)),
                              work_budget=args.max_nodes or 100000,
                              q5_max_leaves=args.q5_max_leaves or 256)
    receipt.update({"schema": "static-memory-experiment-v1", "action": args.action,
                    "experiment": result})
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(result.get("scope", "finite host research; no target admission"))
        print(f"{args.action}: {'refused' if result.get('errors') else 'replayed'}")
        print("Use --json for contracts, source identities, measurements and open obligations.")
    return 1 if result.get("errors") else 0


def timeline(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Observe all state changes, with end events preceding new starts."""
    return [witnesses.ledger(raw, time) for time in witnesses.event_times(raw)]


def requests(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Optional diagnostics have their own schema, outside placement constraints."""
    queries = raw.get("requests", [])
    if not isinstance(queries, list):
        raise TypeError("requests must be a list")
    result: list[dict[str, Any]] = []
    required = {"time", "owner", "arena", "size"}
    for request in queries:
        if not isinstance(request, dict) or not required <= request.keys():
            raise ValueError("request requires time, owner, arena and size")
        if request.keys() - (required | {"alignment"}):
            raise ValueError("unknown request fields")
        if any(not isinstance(request[key], str) or not request[key].strip()
               for key in ("owner", "arena")):
            raise ValueError("request owner and arena must be nonempty strings")
        result.append(witnesses.diagnose_request(
            raw, request["time"], request["owner"], request["arena"],
            request["size"], request.get("alignment", 1)))
    return result


def selected(args: argparse.Namespace,
             revision: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Choose the declared contracts without silently falling back after bad input."""
    if args.contract is not None:
        raw, digest = read_input(args.contract)
        oracle.parse_case(raw)
        if not isinstance(raw, dict):
            raise ValueError("contract must be an object")
        return [raw], {"contract_sha256": digest}
    cases = witnesses.corpus(revision)
    if args.case is not None:
        cases = [case for case in cases if case["name"] == args.case]
        if not cases:
            raise ValueError(f"unknown case: {args.case}")
    return cases, {}


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.max_nodes is not None and args.max_nodes < 1:
        parser().error("--max-nodes must be positive")
    if args.sizes is not None and (args.action != "scale" or any(n < 1 for n in args.sizes)):
        parser().error("--sizes requires scale and positive object counts")
    if args.q5_max_leaves is not None and (args.action != "scale" or args.q5_max_leaves < 1):
        parser().error("--q5-max-leaves requires scale and a positive budget")
    if args.case and args.contract:
        parser().error("--case and --contract are mutually exclusive")
    if args.candidate and (args.action != "check" or not args.contract):
        parser().error("--candidate requires check --contract")
    if args.action in EXPERIMENT_SOURCES:
        if args.case or args.contract or args.candidate:
            parser().error("this experiment uses declared fixtures; case/contract/candidate are unsupported")
        if args.max_nodes is not None and args.action != "scale":
            parser().error("--max-nodes is supported by compare and scale")
    root = Path(__file__).resolve().parents[3]
    try:
        if args.action in EXPERIMENT_SOURCES:
            return experiment(args, root)
        args.max_nodes = args.max_nodes or 100000
        report = identity(root, SOURCES)
        cases, bindings = selected(args, report["revision"])
        report.update(bindings)
        report.update({
            "schema": "static-memory-research-v1",
            "scope": "finite host research; no target admission or service-equivalence claim",
            "action": args.action,
            "settings": {"max_nodes": args.max_nodes},
            "cases": [],
        })
        failed = False
        for raw in cases:
            case = oracle.parse_case(raw)
            item: dict[str, Any] = {"contract": raw}
            if args.action == "corpus":
                errors = oracle.check_placement(case, oracle.standing_placement(case))
                item["standing_errors"] = errors
                if errors:
                    failed = True
                else:
                    item["timeline"] = timeline(raw)
                    item["requests"] = requests(raw)
            elif args.action == "compare":
                started = perf_counter()
                item["heuristics"] = oracle.compare_heuristics(case, work_budget=args.max_nodes)
                item["exact"] = oracle.solve_exact(case, work_budget=args.max_nodes)
                item["search_elapsed_seconds"] = perf_counter() - started
                item["elapsed_is_reproducible"] = False
                if item["exact"]["status"] == "optimal":
                    item["optimality_replay"] = oracle.verify_optimality(
                        case, item["exact"], work_budget=args.max_nodes)
                    failed = failed or item["optimality_replay"]["status"] == "rejected"
                failed = failed or item["exact"]["status"] == "infeasible"
            else:
                candidate: object = oracle.standing_placement(case)
                if args.candidate is not None:
                    candidate, digest = read_input(args.candidate)
                    report["candidate_sha256"] = digest
                item["errors"] = oracle.check_placement(case, candidate)
                item["accepted"] = not item["errors"]
                failed = failed or not item["accepted"]
            report["cases"].append(item)
        if args.action == "corpus" and args.contract is None:
            report["q5_bridge"] = witnesses.q5_bridge(root, report["revision"])
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
        print(json.dumps({"error": str(error), "status": "malformed-or-unreadable"})
              if args.json else f"FAIL static-memory: {error}")
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(report["scope"])
        for item in report["cases"]:
            name = item["contract"]["name"]
            if args.action == "compare":
                exact = item["exact"]
                replay = item.get("optimality_replay", {}).get("status", "n/a")
                print(f"{name}: {exact['status']}; nodes={exact['nodes']}; replay={replay}")
                for arena in exact["arenas"]:
                    print(f"  {arena['arena']}: load={arena['charged_load_lower_bound']} "
                          f"proved={arena['proven_lower_bound']} span={arena['best_span']} "
                          f"optimality_gap={arena['optimality_gap']} "
                          f"span_over_load={arena['best_span_over_load']}")
            elif args.action == "check":
                print(f"{name}: {'accepted' if item['accepted'] else 'refused'} "
                      f"{item['errors']}")
            else:
                print(f"{name}: {len(item.get('timeline', []))} event snapshots; "
                      f"standing errors={item['standing_errors']}")
        print("Use --json for contracts, cost assumptions, source hashes and full evidence.")
    return 1 if failed else 0
