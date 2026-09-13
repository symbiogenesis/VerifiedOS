# SPDX-License-Identifier: Apache-2.0
"""Deterministic scaling contracts and comparisons, separate from host timing.

Synthetic traces supply their own milestones. They establish neither lifecycle
barriers nor a workload envelope. The Q5 comparison retains Q5's own predicates;
its placement-only projection supplies no missing operational contract.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any

from vos import memplan
from vos import static_memory as memory
from vos import static_memory_bounds as lower_bounds

GENERATOR = "tools/vos/static_memory_scale.py"
VERSION = "static-memory-scale-v1"
SCHEMA = "static-memory-scale-v2"
FAMILIES = ("laminar", "crossing", "heterogeneous-aligned", "burst-safe-reuse",
            "two-instant-witness")
# One gadget of the witness family: extent, alignment, start offset and duration.
# Its two instants share the second reservation, and no other pair of its objects is
# charged at the same time, so the two-instant relaxation is exact for one gadget.
WITNESS_GADGET = ((1, 8, 0, 1), (3, 4, 0, 3), (2, 8, 0, 1), (5, 2, 2, 1))
DEFAULT_SIZES = (8, 32, 128)
MAX_SIZE = 2048

type Ordering = Callable[[memory.Object], tuple[int, int, int, str]]

# The three shared keys reproduce the oracle's own methods, which is what the focused
# tests hold them to; the three below them are this experiment's additions.
ORDERINGS: dict[str, Ordering] = {
    "first-fit-start": lambda o: (o.start, 0, 0, o.id),
    "first-fit-size": lambda o: (-o.size, o.start, 0, o.id),
    "first-fit-retention": lambda o: (o.start - o.reuse, -o.size, 0, o.id),
    "first-fit-alignment": lambda o: (-o.alignment, -o.size, o.start, o.id),
    "first-fit-extent": lambda o: (-o.size * (o.reuse - o.start), -o.size, o.start, o.id),
    "first-fit-reuse": lambda o: (o.reuse, -o.size, o.start, o.id),
}
ADDED_METHODS: tuple[str, ...] = ("first-fit-alignment", "first-fit-extent",
                                  "first-fit-reuse")


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
                elif family == "burst-safe-reuse":
                    start = (i // 8) * 4 + i % 3
                    reuse = start + 6 + i % 3
                else:
                    gadget, role = divmod(i, len(WITNESS_GADGET))
                    extent, alignment, offset, span = WITNESS_GADGET[role]
                    start = 4 * gadget + offset
                    reuse = start + span
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


def interferes(left: memory.Object, right: memory.Object) -> bool:
    """Charged extents overlapping in time: the half-open reading the checker holds.

    Stated here because the oracle keeps its own copy private; the focused tests hold
    this one against `check_placement`'s verdict rather than against that copy.
    """
    return max(left.start, right.start) < min(left.reuse, right.reuse)


def _lowest_base(obj: memory.Object, blockers: list[tuple[int, int]], capacity: int,
                 standing: int | None, work: lower_bounds.Work) -> tuple[str, int | None]:
    """The least aligned base clearing every blocking extent, at or below `standing`.

    Zero and the aligned ends of the blocking extents are the whole candidate set: a
    feasible base that is neither is one alignment step above an infeasible base, so
    some blocker ends inside that step and its aligned end is the base itself. One
    forward cursor decides overlap, blockers being sorted and candidates ascending.
    """
    candidates = {0} | {lower_bounds.align_up(high, obj.alignment) for _, high in blockers}
    if standing is not None:
        candidates.add(standing)
    ranges = sorted(blockers)
    cursor = 0
    for base in sorted(candidates):
        if not work.step():
            return "incomplete", None
        while cursor < len(ranges) and ranges[cursor][1] <= base:
            cursor += 1
        overlaps = cursor < len(ranges) and ranges[cursor][0] < base + obj.size
        if base + obj.size <= capacity and not overlaps:
            return "feasible", base
    return "no-fit", None


def first_fit(case: memory.Case, order: Ordering,
              work: lower_bounds.Work) -> tuple[str, list[dict[str, Any]] | None]:
    """Place each object at its lowest feasible base in one pass over `order`."""
    bases: dict[str, int] = {}
    for arena in case.arenas:
        placed: list[tuple[memory.Object, int]] = []
        for obj in sorted((o for o in case.objects if o.arena == arena.id), key=order):
            blockers = [(base, base + prev.size) for prev, base in placed
                        if interferes(obj, prev)]
            status, base = _lowest_base(obj, blockers, arena.capacity, None, work)
            if base is None:
                return status, None
            placed.append((obj, base))
            bases[obj.id] = base
    return "feasible", [{"id": o.id, "arena": o.arena, "base": bases[o.id]}
                        for o in case.objects]


def lower_to_fixed_point(case: memory.Case, placement: list[dict[str, Any]],
                         work: lower_bounds.Work) -> tuple[str, list[dict[str, Any]]]:
    """Re-place every object at its lowest feasible base until nothing moves.

    Each pass considers objects by current base and identity, and a base only ever
    falls, so the sum of bases strictly decreases between passes and the fixed point
    is reached in finite work. The result is a placement for the checker to judge,
    never an optimum: the operator moves one object at a time and cannot exchange two.
    """
    bases = {row["id"]: row["base"] for row in placement}
    capacities = {arena.id: arena.capacity for arena in case.arenas}
    objects = {obj.id: obj for obj in case.objects}
    neighbours = {obj.id: [other for other in case.objects if other.id != obj.id
                           and other.arena == obj.arena and interferes(obj, other)]
                  for obj in case.objects}
    status = "fixed-point"
    moved = True
    while moved:
        moved = False
        for identifier in sorted(bases, key=lambda key: (bases[key], key)):
            obj = objects[identifier]
            blockers = [(bases[other.id], bases[other.id] + other.size)
                        for other in neighbours[identifier]]
            found, base = _lowest_base(obj, blockers, capacities[obj.arena],
                                       bases[identifier], work)
            if found == "incomplete":
                return "incomplete", [{"id": o.id, "arena": o.arena, "base": bases[o.id]}
                                      for o in case.objects]
            if base is None:
                raise RuntimeError("standing base of a legal placement became infeasible")
            if base < bases[identifier]:
                bases[identifier] = base
                moved = True
                status = "feasible"
    return status, [{"id": o.id, "arena": o.arena, "base": bases[o.id]}
                    for o in case.objects]


def _improves(spans: dict[str, int] | None,
              standing_spans: dict[str, int] | None) -> bool:
    """The comparison's rule: no arena larger, at least one smaller, never a sum."""
    if spans is None:
        return False
    if standing_spans is None:
        return True
    return (all(spans[key] <= standing_spans[key] for key in spans)
            and any(spans[key] < standing_spans[key] for key in spans))


def _heuristic_row(case: memory.Case, method: str, status: str,
                   candidate: list[dict[str, Any]] | None, work: lower_bounds.Work,
                   standing: list[dict[str, Any]],
                   standing_spans: dict[str, int]) -> dict[str, Any]:
    """One comparison row, with the same fields and fallback rule the oracle emits."""
    spans = memory.placement_spans(case, candidate) if candidate is not None else None
    preserve = not _improves(spans, standing_spans)
    return {"method": method, "status": status, "nodes": work.spent,
            "work_budget": work.limit, "candidate": candidate,
            "candidate_spans": spans, "standing_preserved": preserve,
            "placement": standing if preserve else candidate,
            "spans": standing_spans if preserve else spans}


def added_heuristics(case: memory.Case, work_budget: int,
                     supplied: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The added orderings, then the lowering pass over every checked candidate.

    The pass runs on the standing plan and on every complete candidate, including the
    oracle's own. It earns a row where it moved something; where it did not, the
    source row's `lowering_moved` records that its placement is already a fixed point
    and the receipt keeps one copy of the placement instead of two.
    """
    _budget(work_budget)
    standing = memory.standing_placement(case)
    standing_spans = memory.placement_spans(case, standing)
    rows: list[dict[str, Any]] = []
    for method in ADDED_METHODS:
        work = lower_bounds.Work(work_budget)
        status, candidate = first_fit(case, ORDERINGS[method], work)
        rows.append(_heuristic_row(case, method, status, candidate, work, standing,
                                   standing_spans))
    sources: list[tuple[str, list[dict[str, Any]], dict[str, Any] | None]] = [
        ("standing", standing, None)]
    sources.extend((row["method"], row["candidate"], row)
                   for row in (*supplied, *rows) if row["candidate"] is not None)
    lowered: list[dict[str, Any]] = []
    for name, source, origin in sources:
        work = lower_bounds.Work(work_budget)
        status, candidate = lower_to_fixed_point(case, source, work)
        if origin is not None:
            origin["lowering_moved"] = status != "fixed-point"
        if status == "fixed-point" and origin is not None:
            continue
        row = _heuristic_row(case, f"lowered-{name}", status, candidate, work,
                             standing, standing_spans)
        row["lowered_from"] = name
        lowered.append(row)
    return rows + lowered


def _gaps(case: memory.Case, spans: dict[str, int], lower: dict[str, int],
          proved_by: dict[str, str], supplier: dict[str, str]) -> list[dict[str, Any]]:
    """Per arena: the charged load, the strongest bound and its source, span and gap."""
    rows: list[dict[str, Any]] = []
    for arena in case.arenas:
        load = memory.peak_load(case, arena.id)
        span, bound = spans[arena.id], lower[arena.id]
        if span == load:
            status = "optimal-by-load-equality"
        elif span == bound:
            status = f"optimal-by-{proved_by[arena.id]}"
        else:
            status = "bounded-only"
        rows.append({"arena": arena.id, "owner": arena.owner,
                     "charged_load_lower_bound": load, "proven_lower_bound": bound,
                     "proven_lower_bound_source": proved_by[arena.id],
                     "feasible_span": span, "feasible_span_source": supplier[arena.id],
                     "remaining_gap": span - bound, "span_status": status})
    return rows


def _proved(case: memory.Case, exact: dict[str, Any], replay: dict[str, Any] | None,
            bounds_budget: int) -> tuple[dict[str, int], dict[str, str],
                                         list[lower_bounds.ArenaBounds]]:
    """Take the strongest bound per arena, naming the one that supplied it."""
    rows = lower_bounds.case_bounds(case, bounds_budget)
    lower = {row["arena"]: row["proven_lower_bound"] for row in rows}
    proved_by = {row["arena"]: row["proven_lower_bound_source"] for row in rows}
    # A claimed exact bound enters the comparison only after its independent replay.
    if replay is not None and replay["status"] == "verified":
        for row in exact["arenas"]:
            if row["proven_lower_bound"] > lower[row["arena"]]:
                lower[row["arena"]] = row["proven_lower_bound"]
                proved_by[row["arena"]] = "replayed-exact"
    return lower, proved_by, rows


def compare_case(raw: dict[str, Any], work_budget: int = 100_000,
                 bounds_budget: int = lower_bounds.DEFAULT_WORK_BUDGET) -> dict[str, Any]:
    """Compare complete witnesses only; the unchanged standing plan remains a fallback."""
    _budget(work_budget)
    _budget(bounds_budget)
    case = memory.parse_case(raw)
    standing = memory.standing_placement(case)
    findings = memory.check_placement(case, standing)
    if findings:
        raise memory.CaseError("generator emitted invalid standing plan: " + "; ".join(findings))
    heuristics = memory.compare_heuristics(case, work_budget)
    heuristics.extend(added_heuristics(case, work_budget, heuristics))
    exact = memory.solve_exact(case, work_budget)
    replay = memory.verify_optimality(case, exact, work_budget) if exact["status"] == "optimal" else None
    lower, proved_by, bound_rows = _proved(case, exact, replay, bounds_budget)
    best = standing
    best_spans = memory.placement_spans(case, standing)
    supplier = {arena.id: "standing" for arena in case.arenas}
    candidates = [(row["method"], row["candidate"]) for row in heuristics
                  if row["status"] == "feasible" and row["candidate"] is not None]
    if exact["status"] == "optimal":
        candidates.append(("bounded-exact-search", exact["best_placement"]))
    # Arenas are independent. Assemble their smallest checked complete witnesses,
    # and check the assembled witness again instead of adding arena capacities.
    for name, candidate in candidates:
        spans = memory.placement_spans(case, candidate)
        for arena in case.arenas:
            if spans[arena.id] < best_spans[arena.id]:
                best = [row for row in best if row["arena"] != arena.id] + [
                    row for row in candidate if row["arena"] == arena.id]
                best_spans[arena.id] = spans[arena.id]
                supplier[arena.id] = name
    ordered = {row["id"]: row for row in best}
    best = [ordered[obj.id] for obj in case.objects]
    if memory.check_placement(case, best):
        raise RuntimeError("assembled scale witness failed independent checking")
    for arena in case.arenas:
        # A sound bound never exceeds a span some checked placement already attains.
        if lower[arena.id] > best_spans[arena.id]:
            raise RuntimeError(f"{case.name}/{arena.id}: proved lower bound "
                               f"{lower[arena.id]} exceeds a checked placement")
    for row in heuristics:
        label = "standing" if row["standing_preserved"] else row["method"]
        row["arenas"] = _gaps(case, row["spans"], lower, proved_by,
                              {arena.id: label for arena in case.arenas})
    preserve = replay is None or replay["status"] != "verified" or best == standing
    return {"contract": raw, "contract_sha256": memory.contract_hash(case),
            "heuristics": heuristics, "exact": exact, "optimality_replay": replay,
            "lower_bounds": bound_rows,
            "best_feasible_placement": best,
            "arenas": _gaps(case, best_spans, lower, proved_by, supplier),
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
           work_budget: int = 100_000, q5_max_leaves: int = 256,
           bounds_budget: int = lower_bounds.DEFAULT_WORK_BUDGET) -> dict[str, Any]:
    """Return replayable settings/results and a separate, nonreproducible timing ledger."""
    _sizes(sizes)
    _budget(work_budget)
    _budget(q5_max_leaves)
    _budget(bounds_budget)
    generated = corpus(revision, sizes)
    items: list[dict[str, Any]] = []
    measurements: list[dict[str, Any]] = []
    for raw in generated:
        started = perf_counter()
        items.append(compare_case(raw, work_budget, bounds_budget))
        measurements.append({"case": raw["name"], "elapsed_seconds": perf_counter() - started})
    started = perf_counter()
    q5 = q5_compare(root, work_budget, q5_max_leaves)
    measurements.append({"case": "q5-comparison", "elapsed_seconds": perf_counter() - started})
    sources = (GENERATOR, "tools/vos/static_memory.py", "tools/vos/static_memory_bounds.py",
               "tools/vos/memplan.py", memplan.SOURCE)
    reproducible = {"schema": SCHEMA, "source_revision": revision,
                    "sources_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                                       for name in sources},
                    "settings": {"sizes": list(sizes), "families": list(FAMILIES),
                                 "work_budget": work_budget, "exact_max_objects_per_arena": memory.MAX_EXACT_OBJECTS,
                                 "q5_max_leaves_per_island": q5_max_leaves,
                                 "bounds_work_budget": bounds_budget,
                                 "bounds": list(lower_bounds.BOUNDS),
                                 "bounds_max_objects_per_live_set": lower_bounds.MAX_CLIQUE_OBJECTS,
                                 "bounds_max_objects_per_instant_pair": lower_bounds.MAX_UNION_OBJECTS,
                                 "methods": list(memory.METHODS) + list(ADDED_METHODS)
                                            + ["lowering-pass-to-fixed-point"],
                                 "budget_units": "candidate bases per heuristic; subset-enumeration "
                                                 "transitions and live sets per arena for the bounds",
                                 "time_units": "synthetic integer ticks", "size_units": "synthetic bytes"},
                    "cases": items, "q5_comparison": q5}
    errors = [f"{item['contract']['name']}: independent optimality replay rejected"
              for item in items if item["optimality_replay"] is not None
              and item["optimality_replay"]["status"] == "rejected"]
    # The charged load is attained by some live set, or one of the two disagrees.
    errors.extend(f"{item['contract']['name']}/{row['arena']}: charged load attains no live set"
                  for item in items for row in item["lower_bounds"]
                  for entry in row["bounds"]
                  if entry["status"] == "unattained-by-any-live-set")
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
