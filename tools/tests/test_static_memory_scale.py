# SPDX-License-Identifier: Apache-2.0
"""Generated scale contracts, fail-closed comparisons and independent scan parity."""

import hashlib
import json
import random
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import memplan
from vos import static_memory as memory
from vos import static_memory_bounds as bounds
from vos import static_memory_scale as scale

ROOT = Path(__file__).resolve().parents[2]


def _generators_are_identified_and_feasible() -> None:
    first = scale.corpus("test-revision", (1, 8, 33))
    ensure(first == scale.corpus("test-revision", (1, 8, 33)), "generation must replay exactly")
    ensure({raw["generator"]["family"] for raw in first} == set(scale.FAMILIES),
           "each declared family must appear")
    for raw in first:
        case = memory.parse_case(raw)
        ensure(len(case.objects) == raw["generator"]["size"], "generator size is an object count")
        ensure(not memory.check_placement(case, memory.standing_placement(case)),
               f"standing generator witness refused: {case.name}")
        ensure(raw["generator"]["revision"] == "test-revision", "source identity is retained")
        if raw["generator"]["family"] == "laminar":
            for left in case.objects:
                for right in case.objects:
                    ensure(left.reuse <= right.start or right.reuse <= left.start or (
                        left.start <= right.start and right.reuse <= left.reuse) or (
                        right.start <= left.start and left.reuse <= right.reuse),
                        "Euler lifetime family must be laminar")
        if raw["generator"]["family"] == "burst-safe-reuse":
            ensure(all(obj.payload_end < obj.authority_end < obj.sweep_end < obj.reuse
                       for obj in case.objects), "reuse must charge every delayed stage")
        if raw["generator"]["family"] == "two-instant-witness":
            width = len(scale.WITNESS_GADGET)
            ensure(all(len(bounds.live_objects(case, "a", obj.start)) < width
                       for obj in case.objects),
                   "no witness instant may charge a whole gadget at once")
            for left in case.objects:
                for right in case.objects:
                    ensure(int(left.id[1:]) // width == int(right.id[1:]) // width
                           or not scale.interferes(left, right),
                           "witness gadgets must not interfere with one another")
    for sizes in ((), (0,), (True,), (scale.MAX_SIZE + 1,), (8, 8)):
        try:
            scale.corpus("test", sizes)
        except memory.CaseError:
            continue
        raise AssertionError(f"invalid size setting accepted: {sizes}")


def _small_oracles_and_large_bounds_stay_distinct() -> None:
    supplied: set[str] = set()
    for raw in scale.corpus("test", (8, 32)):
        item = scale.compare_case(raw, 100_000)
        case = memory.parse_case(raw)
        ensure(not memory.check_placement(case, item["best_feasible_placement"]),
               "assembled best witness must check independently")
        methods = {row["method"] for row in item["heuristics"]} | {"standing",
                                                                   "bounded-exact-search"}
        for row in item["arenas"]:
            ensure(row["feasible_span"] >= row["proven_lower_bound"]
                   >= row["charged_load_lower_bound"] and row["remaining_gap"] >= 0,
                   f"invalid bound ordering: {row}")
            ensure(row["proven_lower_bound_source"] in (*bounds.BOUNDS, "replayed-exact"),
                   f"a proved bound must name the bound that supplied it: {row}")
            ensure(row["feasible_span_source"] in methods,
                   f"a span must name the candidate that attained it: {row}")
            supplied.add(row["proven_lower_bound_source"])
        if raw["generator"]["family"] == "two-instant-witness":
            ensure(all(row["span_status"] == f"optimal-by-{bounds.BOUNDS[3]}"
                       and row["remaining_gap"] == 0 for row in item["arenas"]),
                   f"the pair bound must settle its own witness family: {item['arenas']}")
        if raw["generator"]["size"] == 8:
            ensure(item["exact"]["status"] == "optimal" and item["optimality_replay"]["status"] == "verified",
                   "small finite families owe independent exact replay")
            ensure(all(row["remaining_gap"] == 0 for row in item["arenas"]),
                   "small best witness should attain replayed optimum")
        else:
            ensure(item["exact"]["status"] == "incomplete" and item["optimality_replay"] is None,
                   "over-limit exact runs must not claim an optimum")
            ensure(item["standing_preserved"] and item["selected_placement"] == memory.standing_placement(case),
                   "an incomplete overall comparison keeps candidate evidence separate from selection")
    ensure(supplied >= set(bounds.BOUNDS),
           f"every reported bound must supply the strongest value somewhere: {supplied}")


def _cutoff_preserves_every_standing_plan() -> None:
    for raw in scale.corpus("test", (8,)):
        before = deepcopy(raw)
        item = scale.compare_case(raw, 0, 0)
        standing = memory.standing_placement(memory.parse_case(raw))
        ensure(raw == before and item["standing_preserved"]
               and item["best_feasible_placement"] == standing and item["selected_placement"] == standing,
               "zero-budget comparison must leave all input and standing bindings intact")
        ensure(all(row["status"] == "incomplete" and row["placement"] == standing
                   for row in item["heuristics"]), "heuristics must retain fallback on cutoff")
        ensure(all(row["proven_lower_bound"] == row["charged_load_lower_bound"]
                   and row["proven_lower_bound_source"] == bounds.BOUNDS[0]
                   for row in item["arenas"]),
               "an exhausted bound budget must leave the charged load standing alone")


def _inflated_bound_is_refused() -> None:
    """A bound bug must fail comparison even when the placement itself still checks."""
    raw = scale.corpus("test", (8,))[0]
    case = memory.parse_case(raw)
    forged = bounds.case_bounds(case)
    standing = memory.placement_spans(case, memory.standing_placement(case))
    forged[0]["proven_lower_bound"] = standing[forged[0]["arena"]] + 1
    with patch.object(bounds, "case_bounds", return_value=forged):
        try:
            scale.compare_case(raw, 0)
        except RuntimeError as error:
            ensure("exceeds a checked placement span" in str(error),
                   f"an inflated bound must fail its own consistency check: {error}")
        else:
            raise AssertionError("an inflated lower bound passed the comparison")


def _added_orderings_reproduce_the_oracle_and_recheck() -> None:
    for raw in scale.corpus("test", (8, 32)):
        case = memory.parse_case(raw)
        supplied = {row["method"]: row for row in memory.compare_heuristics(case, 100_000)}
        for method in memory.METHODS:
            status, candidate = scale.first_fit(case, scale.ORDERINGS[method],
                                                bounds.Work(100_000))
            ensure(status == supplied[method]["status"]
                   and candidate == supplied[method]["candidate"],
                   f"{raw['name']}: added first fit diverged from the oracle on {method}")
        for method in scale.ADDED_METHODS:
            status, candidate = scale.first_fit(case, scale.ORDERINGS[method],
                                                bounds.Work(100_000))
            ensure(status == "feasible" and candidate is not None,
                   f"{raw['name']}: {method} found no placement")
            ensure(not memory.check_placement(case, candidate),
                   f"{raw['name']}: {method} emitted a candidate the checker refuses")
        starved = scale.first_fit(case, scale.ORDERINGS[scale.ADDED_METHODS[0]],
                                  bounds.Work(0))
        ensure(starved == ("incomplete", None), f"a cutoff must emit no candidate: {starved}")


def _lowering_reaches_a_fixed_point_and_never_grows() -> None:
    for raw in scale.corpus("test", (8, 32)):
        case = memory.parse_case(raw)
        standing = memory.standing_placement(case)
        spans = memory.placement_spans(case, standing)
        status, once = scale.lower_to_fixed_point(case, standing, bounds.Work(1_000_000))
        ensure(status == "feasible" and not memory.check_placement(case, once),
               f"{raw['name']}: the lowering pass must emit a checked placement")
        lowered = memory.placement_spans(case, once)
        ensure(all(lowered[key] <= spans[key] for key in spans),
               f"{raw['name']}: lowering must not grow an arena")
        again = scale.lower_to_fixed_point(case, once, bounds.Work(1_000_000))
        ensure(again == ("fixed-point", once),
               f"{raw['name']}: a second pass must find the same fixed point")
        interrupted, partial = scale.lower_to_fixed_point(case, standing, bounds.Work(1))
        ensure(interrupted == "incomplete" and not memory.check_placement(case, partial),
               f"{raw['name']}: an interrupted pass must still emit a legal placement")


def _interference_agrees_with_the_checker() -> None:
    rng = random.Random(9122026)  # noqa: S311 - deterministic synthetic tests
    decided = 0
    for _ in range(240):
        objects: list[memory.Object] = []
        for index in range(2):
            start = rng.randrange(4)
            end = start + rng.randrange(1, 5)
            size = rng.randrange(1, 4)
            objects.append(memory.Object(f"o{index}", "a", size, size, 1, start, end,
                                         end, end, end, 0))
        case = memory.Case("pair", "private finite fixture", "one declared trace",
                           (memory.Arena("a", "owner", 8),), tuple(objects))
        shared = [finding for finding in
                  memory.check_placement(case, memory.standing_placement(case))
                  if finding.startswith("overlap:")]
        ensure(bool(shared) == scale.interferes(objects[0], objects[1]),
               f"interference disagrees with the checker: {objects}, {shared}")
        decided += bool(shared)
    ensure(0 < decided < 240, "the sample must contain both verdicts")


def _reference_first_fit(case: memory.Case, method: str,
                         limit: int) -> dict[str, Any]:
    """Original direct pairwise endpoint scan, independent of the optimized cursor."""
    placed: list[tuple[memory.Object, int]] = []
    nodes = 0
    for arena in case.arenas:
        objects = [obj for obj in case.objects if obj.arena == arena.id]
        if method == "first-fit-start":
            order = sorted(objects, key=lambda obj: (obj.start, obj.id))
        elif method == "first-fit-size":
            order = sorted(objects, key=lambda obj: (-obj.size, obj.start, obj.id))
        else:
            order = sorted(objects, key=lambda obj: (obj.start - obj.reuse, -obj.size, obj.id))
        for obj in order:
            conflicts = [(other, base) for other, base in placed if other.arena == arena.id
                         and max(obj.start, other.start) < min(obj.reuse, other.reuse)]
            endpoints = {0} | {((base + other.size + obj.alignment - 1) // obj.alignment)
                               * obj.alignment for other, base in conflicts}
            offset = None
            for base in sorted(endpoints):
                if nodes == limit:
                    return {"status": "incomplete", "nodes": nodes, "candidate": None}
                nodes += 1
                if base + obj.size <= arena.capacity and all(
                        base + obj.size <= other_base or other_base + other.size <= base
                        for other, other_base in conflicts):
                    offset = base
                    break
            if offset is None:
                return {"status": "no-fit", "nodes": nodes, "candidate": None}
            placed.append((obj, offset))
    by_id = {obj.id: base for obj, base in placed}
    return {"status": "feasible", "nodes": nodes,
            "candidate": [{"id": obj.id, "arena": obj.arena, "base": by_id[obj.id]}
                          for obj in case.objects]}


def _cursor_matches_independent_pairwise_scan() -> None:
    rng = random.Random(8122026)  # noqa: S311 - deterministic synthetic tests
    for trial in range(90):
        raw = scale.corpus("test", (8,))[trial % len(scale.FAMILIES)]
        for obj in raw["objects"]:
            obj["size"] = rng.randrange(1, 10)
            obj["payload"] = obj["size"]
            obj["alignment"] = rng.randrange(1, 6)
            obj["start"] = rng.randrange(6)
            end = obj["start"] + rng.randrange(1, 8)
            for key in ("payload_end", "authority_end", "sweep_end", "reuse"):
                obj[key] = end
        for arena in raw["arenas"]:
            arena["capacity"] = rng.randrange(1, 60)
        case = memory.parse_case(raw)
        limit = (0, 1, 7, 20, 1000)[trial % 5]
        for actual in memory.compare_heuristics(case, limit):
            expected = _reference_first_fit(case, actual["method"], limit)
            ensure({key: actual[key] for key in expected} == expected,
                   f"cursor changed candidate/order/budget: trial {trial}, {actual}, {expected}")


def _q5_keeps_original_predicates_and_grid_limits() -> None:
    item = scale.q5_compare(ROOT, 10000, 256)
    ensure(not item["standing_refusals"] and not item["product_admission_evidence"],
           "Q5 input is a proof witness, without product admission evidence")
    plan = memplan.plan_of(memplan.read(ROOT), memplan.STANDING)
    for row in item["heuristics"]:
        ensure(row["status"] == "feasible" and not row["q5_candidate_refusals"],
               "projected heuristic bases must survive Q5's original checks")
        restored = memplan.with_bases(plan, dict(enumerate(row["q5_selected_bases"])))
        ensure(not memplan.refused_by(restored), "selected Q5 plan must be checked as a whole")
    ensure(any(row["status"] == "incomplete" and row["standing_preserved"]
               for row in item["enumeration"]), "truncated Q5 grid must preserve its standing plan")
    ensure(any(row["status"] == "complete-over-declared-grid"
               for row in item["enumeration"]), "small Q5 island supplies complete enumeration")
    for row in item["enumeration"]:
        ensure(row["remaining_grid_gap"] >= 0, "Q5 bounds must be ordered")
        if row["standing_preserved"]:
            ensure(row["selected_bases"] == [[r, plan.base_of(r)] for r in row["regions"]],
                   "incomplete search must retain the original Q5 plan")
    cutoff = scale.q5_compare(ROOT, 0, 0)
    ensure(all(row["standing_preserved"] for row in cutoff["enumeration"]),
           "zero Q5 budget is incomplete without enumerating one leaf")


def _receipts_bind_results_separately_from_host_time() -> None:
    first = scale.report(ROOT, "test", (8,), 10000, 1)
    second = scale.report(ROOT, "test", (8,), 10000, 1)
    ensure(first["reproducible"] == second["reproducible"]
           and first["result_sha256"] == second["result_sha256"],
           "settings, inputs and algorithmic results must replay byte-for-byte")
    ensure(not first["host_measurements"]["reproducible"], "wall time is a host measurement")
    ensure(scale.GENERATOR in first["reproducible"]["sources_sha256"],
           "receipts bind working-tree generator bytes")
    ensure("tools/vos/static_memory_bounds.py" in first["reproducible"]["sources_sha256"],
           "receipts bind the bytes that decided every reported bound")
    changed = deepcopy(first)
    changed["host_measurements"]["runs"] = [{"case": "elsewhere", "elapsed_seconds": 99.0}]
    encoded = json.dumps(changed["reproducible"], sort_keys=True, separators=(",", ":"))
    ensure(hashlib.sha256(encoded.encode("utf-8")).hexdigest() == first["result_sha256"],
           "the digest must cover the reproducible block and nothing measured on a host")


def cases() -> list[Case]:
    return [
        Case("generators-identified-and-feasible", _generators_are_identified_and_feasible),
        Case("small-oracles-and-large-bounds-distinct", _small_oracles_and_large_bounds_stay_distinct),
        Case("cutoff-preserves-standing", _cutoff_preserves_every_standing_plan),
        Case("inflated-bound-refused", _inflated_bound_is_refused),
        Case("added-orderings-reproduce-the-oracle", _added_orderings_reproduce_the_oracle_and_recheck),
        Case("lowering-reaches-a-fixed-point", _lowering_reaches_a_fixed_point_and_never_grows),
        Case("interference-agrees-with-the-checker", _interference_agrees_with_the_checker),
        Case("cursor-matches-pairwise-scan", _cursor_matches_independent_pairwise_scan),
        Case("q5-original-predicates-and-grid-limits", _q5_keeps_original_predicates_and_grid_limits),
        Case("receipt-results-separate-from-time", _receipts_bind_results_separately_from_host_time),
    ]
