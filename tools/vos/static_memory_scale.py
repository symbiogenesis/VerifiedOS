# SPDX-License-Identifier: Apache-2.0
"""Deterministic scaling contracts and comparisons, separate from host timing.

Synthetic traces supply their own milestones. They establish neither lifecycle
barriers nor a workload envelope. The Q5 comparison retains Q5's own predicates;
its placement-only projection supplies no missing operational contract.
"""

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any

from vos import memplan
from vos import static_memory as memory

GENERATOR = "tools/vos/static_memory_scale.py"
VERSION = "static-memory-scale-v1"
FAMILIES = ("laminar", "crossing", "heterogeneous-aligned", "burst-safe-reuse")
DEFAULT_SIZES = (8, 32, 128)
MAX_SIZE = 2048


def _sizes(sizes: tuple[int, ...]) -> None:
    if not sizes or len(set(sizes)) != len(sizes) or any(
            type(size) is not int or not 1 <= size <= MAX_SIZE for size in sizes):
        raise memory.CaseError(f"sizes must be distinct integers from 1 through {MAX_SIZE}")


def _budget(work_budget: int) -> None:
    if type(work_budget) is not int or work_budget < 0:
        raise memory.CaseError("work_budget must be a nonnegative integer")


def _laminar_intervals(size: int) -> dict[int, tuple[int, int]]:
    """Euler intervals of a finite binary tree are laminar by construction."""
    intervals: dict[int, tuple[int, int]] = {}
    clock = 0

    def visit(index: int) -> None:
        nonlocal clock
        if index >= size:
            return
        start = clock
        clock += 1
        visit(2 * index + 1)
        visit(2 * index + 2)
        clock += 1
        intervals[index] = (start, clock)

    visit(0)
    return intervals


def corpus(revision: str, sizes: tuple[int, ...] = DEFAULT_SIZES) -> list[dict[str, Any]]:
    """Generate identified, valid standing plans without sampling or product traces."""
    _sizes(sizes)
    results: list[dict[str, Any]] = []
    for size in sizes:
        intervals = _laminar_intervals(size)
        for family in FAMILIES:
            objects: list[dict[str, Any]] = []
            cursor: dict[str, int] = {"a": 0, "b": 0} if family == FAMILIES[2] else {"a": 0}
            for i in range(size):
                arena = "b" if family == FAMILIES[2] and i % 2 else "a"
                alignment = 1
                extent = 1 + i % 5
                if family == "laminar":
                    start, reuse = intervals[i]
                elif family == "crossing":
                    start, reuse = i, i + max(3, size // 8)
                elif family == "heterogeneous-aligned":
                    start = (i * 7) % max(4, size // 2)
                    reuse = start + 1 + (i * 11) % max(3, size // 4)
                    alignment = (1, 2, 4, 8)[i % 4]
                    extent = 1 + (i * 13) % 17
                else:
                    start = (i // 8) * 4 + i % 3
                    reuse = start + 6 + i % 3
                base = ((cursor[arena] + alignment - 1) // alignment) * alignment
                cursor[arena] = base + extent + alignment
                delayed = family == "burst-safe-reuse"
                objects.append({
                    "id": f"o{i:05d}", "arena": arena, "size": extent,
                    "payload": max(0, extent - 1) if delayed else extent,
                    "alignment": alignment, "start": start,
                    "payload_end": start + 1 if delayed else reuse,
                    "authority_end": start + 2 if delayed else reuse,
                    "sweep_end": start + 4 + i % 2 if delayed else reuse,
                    "reuse": reuse, "base": base,
                })
            results.append({
                "name": f"scale-{family}-{size}", "mode": "single-fixed-trace",
                "provenance": "synthetic formula; no measured product workload",
                "generator": {"version": VERSION, "source": GENERATOR,
                              "revision": revision, "family": family, "size": size},
                "arenas": [{"id": key, "owner": f"owner-{key}", "capacity": end + 8}
                           for key, end in cursor.items()],
                "objects": objects,
            })
    return results


def _gaps(case: memory.Case, spans: dict[str, int],
          lower: dict[str, int]) -> list[dict[str, Any]]:
    return [{"arena": arena.id, "owner": arena.owner,
             "charged_load_lower_bound": memory.peak_load(case, arena.id),
             "proven_lower_bound": lower[arena.id], "feasible_span": spans[arena.id],
             "remaining_gap": spans[arena.id] - lower[arena.id],
             "span_status": "optimal-by-load-equality" if spans[arena.id] == memory.peak_load(case, arena.id)
             else "optimal-by-replayed-exact" if spans[arena.id] == lower[arena.id] else "bounded-only"}
            for arena in case.arenas]


def compare_case(raw: dict[str, Any], work_budget: int = 100_000) -> dict[str, Any]:
    """Compare complete witnesses only; the unchanged standing plan remains a fallback."""
    _budget(work_budget)
    case = memory.parse_case(raw)
    standing = memory.standing_placement(case)
    findings = memory.check_placement(case, standing)
    if findings:
        raise memory.CaseError("generator emitted invalid standing plan: " + "; ".join(findings))
    heuristics = memory.compare_heuristics(case, work_budget)
    exact = memory.solve_exact(case, work_budget)
    replay = memory.verify_optimality(case, exact, work_budget) if exact["status"] == "optimal" else None
    lower = {arena.id: memory.peak_load(case, arena.id) for arena in case.arenas}
    # A claimed exact bound enters the comparison only after its independent replay.
    if replay is not None and replay["status"] == "verified":
        lower = {row["arena"]: row["proven_lower_bound"] for row in exact["arenas"]}
    best = standing
    best_spans = memory.placement_spans(case, standing)
    candidates = [row["candidate"] for row in heuristics if row["status"] == "feasible"]
    if exact["status"] == "optimal":
        candidates.append(exact["best_placement"])
    # Arenas are independent. Assemble their smallest checked complete witnesses,
    # and check the assembled witness again instead of adding arena capacities.
    for candidate in candidates:
        spans = memory.placement_spans(case, candidate)
        for arena in case.arenas:
            if spans[arena.id] < best_spans[arena.id]:
                best = [row for row in best if row["arena"] != arena.id] + [
                    row for row in candidate if row["arena"] == arena.id]
                best_spans[arena.id] = spans[arena.id]
    ordered = {row["id"]: row for row in best}
    best = [ordered[obj.id] for obj in case.objects]
    if memory.check_placement(case, best):
        raise RuntimeError("assembled scale witness failed independent checking")
    for row in heuristics:
        row["arenas"] = _gaps(case, row["spans"], lower)
    preserve = replay is None or replay["status"] != "verified" or best == standing
    return {"contract": raw, "contract_sha256": memory.contract_hash(case),
            "heuristics": heuristics, "exact": exact, "optimality_replay": replay,
            "best_feasible_placement": best, "arenas": _gaps(case, best_spans, lower),
            "best_candidate_matches_standing": best == standing,
            "selected_placement": standing if preserve else best,
            "standing_preserved": preserve,
            "selection_policy": "whole comparison preserves standing unless exact search and replay complete; "
                                "complete heuristic candidates remain separate research evidence",
            "no_product_admission_claim": True}


def q5_projection(plan: memplan.Plan) -> tuple[memory.Case, dict[str, Any]]:
    """Project the declared Q5 grid to relative addresses, with explicit missing inputs.

    Island identifiers are opaque partition labels, never inferred security owners.
    Q5 has no completion milestones: all four end fields equal its declared live end
    as a placement experiment assumption, and are not operational safe-reuse facts.
    """
    arenas: list[dict[str, Any]] = []
    objects: list[dict[str, Any]] = []
    grids: list[dict[str, Any]] = []
    for island in plan.island_ids():
        regions, quantum, steps, domains = memplan.candidate_grid(plan, island)
        origin = plan.island_base(island)
        # The research checker constrains relative-base multiples. Q5 also checks
        # absolute quantization; the recheck below keeps that stronger predicate.
        arenas.append({"id": f"island-{island}", "owner": f"opaque-q5-partition-{island}",
                       "capacity": plan.island_span(island)})
        grids.append({"island": island, "quantum": quantum, "steps": list(steps),
                      "domain_counts": [len(domain) for domain in domains]})
        for region, step in zip(regions, steps, strict=True):
            end = plan.live_to(region)
            objects.append({"id": f"r{region}", "arena": f"island-{island}",
                            "size": plan.length_of(region), "payload": plan.length_of(region),
                            "alignment": step, "start": plan.live_from(region),
                            "payload_end": end, "authority_end": end, "sweep_end": end,
                            "reuse": end, "base": plan.base_of(region) - origin})
    raw = {"name": f"q5-grid-projection-{plan.name}", "mode": "single-fixed-trace",
           "provenance": "Q5 placement witness projection; owners and barriers unavailable",
           "arenas": arenas, "objects": objects}
    return memory.parse_case(raw), {"projection": raw, "grids": grids,
                                    "missing_operational_inputs": ["security-owner", "payload",
                                       "payload_end", "authority_end", "sweep_end", "safe-reuse-proof"]}


def q5_compare(root: Path, work_budget: int = 100_000,
               max_leaves: int = 256) -> dict[str, Any]:
    """Reuse the exporter and enumerator; recheck heuristic bases in the original plan."""
    _budget(work_budget)
    _budget(max_leaves)
    source = memplan.read(root)
    plan = memplan.plan_of(source, memplan.STANDING)
    projected, description = q5_projection(plan)
    heuristic_rows = memory.compare_heuristics(projected, work_budget)
    for row in heuristic_rows:
        candidate = row["candidate"]
        if candidate is None:
            row["q5_candidate_refusals"] = None
            row["q5_candidate_scores"] = None
            row["q5_standing_preserved"] = True
            row["q5_selected_bases"] = list(plan.bases)
            continue
        offsets = {int(item["id"][1:]): item["base"] for item in candidate}
        proposed = memplan.with_bases(plan, {
            region: offsets[region] + plan.island_base(plan.island_of(region))
            for region in plan.regions()})
        row["q5_candidate_refusals"] = memplan.refused_by(proposed)
        row["q5_candidate_scores"] = [
            {"island": island, **asdict(memplan.score(proposed, island))}
            for island in plan.island_ids()]
        row["q5_standing_preserved"] = bool(row["q5_candidate_refusals"]) or row["standing_preserved"]
        row["q5_selected_bases"] = list(plan.bases if row["q5_standing_preserved"] else proposed.bases)
    enumeration: list[dict[str, Any]] = []
    for island in plan.island_ids():
        if max_leaves == 0:
            enumeration.append({"island": island, "status": "incomplete", "leaves": 0,
                                "reason": "zero leaf budget", "standing_preserved": True,
                                "selected_bases": [[r, plan.base_of(r)] for r in plan.regions()
                                                   if plan.island_of(r) == island]})
            continue
        found = memplan.enumerate_island(plan, island, max_leaves=max_leaves)
        row = asdict(found)
        row["status"] = "incomplete" if found.truncated else "complete-over-declared-grid"
        row["standing_preserved"] = found.truncated or found.best is None or (
            found.best.score is None or found.best.score.key() >= found.standing.key())
        row["selected_bases"] = [[r, plan.base_of(r)] for r in found.regions] if row[
            "standing_preserved"] else list(found.best.bases) if found.best is not None else []
        best_score = found.best.score if found.best is not None else None
        feasible_span = min(found.standing.span_used, best_score.span_used) if best_score else found.standing.span_used
        lower = best_score.span_used if not found.truncated and best_score else found.standing.footprint
        row["best_feasible_span"] = feasible_span
        row["proven_grid_lower_bound"] = lower
        row["remaining_grid_gap"] = feasible_span - lower
        row["span_certificate"] = "load-equality" if feasible_span == found.standing.footprint else (
            "complete-declared-grid" if not found.truncated and best_score else None)
        enumeration.append(row)
    return {**description, "export": memplan.export(source),
            "candidate_set": memplan.PREDICATE, "heuristics": heuristic_rows,
            "enumeration": enumeration, "standing_refusals": memplan.refused_by(plan),
            "budget_unit": "leaves per island for Q5; candidate bases per heuristic",
            "max_leaves_per_island": max_leaves,
            "limitations": "Q5 leaf budget does not bound pruned-prefix visits or wall time; "
                           "enumeration optimum concerns its declared grid only",
            "product_admission_evidence": False}


def report(root: Path, revision: str, sizes: tuple[int, ...] = DEFAULT_SIZES,
           work_budget: int = 100_000, q5_max_leaves: int = 256) -> dict[str, Any]:
    """Return replayable settings/results and a separate, nonreproducible timing ledger."""
    _sizes(sizes)
    _budget(work_budget)
    _budget(q5_max_leaves)
    generated = corpus(revision, sizes)
    items: list[dict[str, Any]] = []
    measurements: list[dict[str, Any]] = []
    for raw in generated:
        started = perf_counter()
        items.append(compare_case(raw, work_budget))
        measurements.append({"case": raw["name"], "elapsed_seconds": perf_counter() - started})
    started = perf_counter()
    q5 = q5_compare(root, work_budget, q5_max_leaves)
    measurements.append({"case": "q5-comparison", "elapsed_seconds": perf_counter() - started})
    sources = (GENERATOR, "tools/vos/static_memory.py", "tools/vos/memplan.py", memplan.SOURCE)
    reproducible = {"schema": VERSION, "source_revision": revision,
                    "sources_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                       for name in sources},
                    "settings": {"sizes": list(sizes), "families": list(FAMILIES),
                                 "work_budget": work_budget, "exact_max_objects_per_arena": memory.MAX_EXACT_OBJECTS,
                                 "q5_max_leaves_per_island": q5_max_leaves,
                                 "time_units": "synthetic integer ticks", "size_units": "synthetic bytes"},
                    "cases": items, "q5_comparison": q5}
    errors = [f"{item['contract']['name']}: independent optimality replay rejected"
              for item in items if item["optimality_replay"] is not None
              and item["optimality_replay"]["status"] == "rejected"]
    errors.extend(f"Q5 {row['method']}: original predicates refused the projected candidate"
                  for row in q5["heuristics"] if row["q5_candidate_refusals"])
    errors.extend(f"Q5 standing: {finding}" for finding in q5["standing_refusals"])
    encoded = json.dumps(reproducible, sort_keys=True, separators=(",", ":"))
    return {"scope": "finite synthetic scaling and Q5 grid comparison; no target admission",
            "errors": errors, "reproducible": reproducible,
            "result_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            "host_measurements": {"reproducible": False,
                                  "scope": "host Python generation excluded; checking and search included; "
                                           "no target build or execution measurement",
                                  "runs": measurements}}
