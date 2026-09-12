# SPDX-License-Identifier: Apache-2.0
"""Small-layout evidence: immutable contracts, independent optima and interrupted work."""

import random
from copy import deepcopy
from itertools import product
from typing import Any

from tests.harness import Case, ensure
from vos import static_memory as memory


def _object(identifier: str, size: int, start: int, reuse: int,
            base: int = 0, alignment: int = 1, arena: str = "a") -> dict[str, Any]:
    return {"id": identifier, "arena": arena, "size": size, "payload": size,
            "alignment": alignment, "start": start, "payload_end": reuse,
            "authority_end": reuse, "sweep_end": reuse, "reuse": reuse, "base": base}


def _raw(objects: list[dict[str, Any]], capacity: int = 16) -> dict[str, Any]:
    return {"name": "test-witness", "mode": "single-fixed-trace",
            "provenance": "synthetic test, no product measurement",
            "arenas": [{"id": "a", "owner": "owner-a", "capacity": capacity}],
            "objects": objects}


def _refused(raw: object) -> None:
    try:
        memory.parse_case(raw)
    except memory.CaseError:
        return
    raise AssertionError(f"malformed contract accepted: {raw}")


def _schema_is_explicit() -> None:
    valid = _raw([_object("x", 2, 0, 3)])
    for key, value in (("size", 0), ("size", True), ("payload", 3),
                       ("alignment", 0), ("start", -1), ("reuse", 0),
                       ("authority_end", 4), ("base", 1.0), ("arena", "unknown")):
        mutant = deepcopy(valid)
        mutant["objects"][0][key] = value
        _refused(mutant)
    for field in ("payload_end", "authority_end", "sweep_end", "reuse"):
        mutant = deepcopy(valid)
        del mutant["objects"][0][field]
        _refused(mutant)
    for part in ("objects", "arenas"):
        mutant = deepcopy(valid)
        mutant[part].append(deepcopy(mutant[part][0]))
        _refused(mutant)
    mutant = deepcopy(valid)
    mutant["objects"][0]["pinned"] = True
    _refused(mutant)
    mutant = deepcopy(valid)
    mutant["arenas"][0]["capacity"] = False
    _refused(mutant)
    _refused([])
    _refused({})


def _candidate_cannot_change_the_contract() -> None:
    raw = _raw([_object("x", 2, 0, 4, alignment=2), _object("y", 2, 4, 8)])
    raw["arenas"].append({"id": "b", "owner": "other-owner", "capacity": 16})
    case = memory.parse_case(raw)
    standing = memory.standing_placement(case)
    ensure(not memory.check_placement(case, standing), "equality at reuse must permit sharing")
    mutants: list[object] = [standing[:-1], [*standing, standing[0]],
                             {"x": 0, "y": 0}]
    for key, value in (("base", 1), ("base", 16), ("base", -1), ("base", True),
                       ("id", "intruder"), ("arena", "b"), ("reuse", 2),
                       ("owner", "other-owner"), ("size", 1), ("payload_end", 1)):
        mutant = deepcopy(standing)
        mutant[0][key] = value
        mutants.append(mutant)
    for mutant in mutants:
        ensure(bool(memory.check_placement(case, mutant)), f"illegal candidate accepted: {mutant}")
    # An earlier payload death does not finish containment, the sweep or initialization.
    for late_field in ("authority_end", "sweep_end", "reuse"):
        delayed = deepcopy(raw)
        delayed["objects"][0]["payload_end"] = 1
        for field in ("authority_end", "sweep_end", "reuse"):
            delayed["objects"][0][field] = 4
        fields = ("authority_end", "sweep_end", "reuse")
        for field in fields[fields.index(late_field):]:
            delayed["objects"][0][field] = 5
        altered = memory.parse_case(delayed)
        findings = memory.check_placement(altered, standing)
        ensure(any(item.startswith("overlap:") for item in findings),
               f"late {late_field} failed to block reuse: {findings}")
    reordered = memory.parse_case({**raw, "objects": list(reversed(raw["objects"]))})
    ensure(not memory.check_placement(reordered, standing), "candidate identity is by ID, not order")


def _load_and_exact_optimum_have_separate_certificates() -> None:
    tight = memory.parse_case(_raw([_object("outer", 2, 0, 8),
                                    _object("left", 3, 1, 3, 4),
                                    _object("right", 1, 4, 7, 9)]))
    found = memory.solve_exact(tight)
    ensure(found["status"] == "optimal" and found["arenas"][0]["best_span"] == 5,
           f"laminar unaligned witness must attain load: {found}")
    ensure(memory.verify_optimality(tight, found)["status"] == "verified",
           "load equality proves the checked laminar witness optimal")
    gap = memory.parse_case(_raw([_object("x", 1, 0, 2, 0, 4),
                                  _object("y", 1, 0, 2, 4, 4)], 8))
    found = memory.solve_exact(gap)
    row = found["arenas"][0]
    ensure((row["lower_bound"], row["best_span"], row["remaining_gap"]) == (2, 5, 3),
           f"alignment gap must not be mistaken for load or heuristic error: {row}")
    ensure(row["certificate"] == {"method": "exhaustive", "infeasible_through": 4},
           f"non-tight load requires independent exhaustion evidence: {row}")
    replay = memory.verify_optimality(gap, found)
    ensure(replay["status"] == "verified" and replay["nodes"] == 1,
           f"only (0,0) fits the address domains below five: {replay}")
    ensure(memory.verify_optimality(gap, found, 0)["status"] == "incomplete",
           "replay interrupted before evidence leaves optimality unchecked")
    false = deepcopy(found)
    false["arenas"][0]["certificate"]["infeasible_through"] = 2
    ensure(memory.verify_optimality(gap, false)["status"] == "rejected",
           "a certificate skipping the immediately preceding height proves nothing")
    false = deepcopy(found)
    false["arenas"][0]["lower_bound"] = 5
    ensure(memory.verify_optimality(gap, false)["status"] == "rejected",
           "a receipt cannot invent its load bound")
    false = deepcopy(found)
    false["best_placement"][1]["base"] = 0
    ensure(memory.verify_optimality(gap, false)["status"] == "rejected",
           "an optimality receipt must carry an independently feasible witness")
    changed = _raw([_object("x", 1, 0, 2, 0, 4), _object("y", 1, 0, 2, 4, 4)], 8)
    changed["arenas"][0]["owner"] = "new-owner"
    ensure(memory.verify_optimality(memory.parse_case(changed), found)["status"] == "rejected",
           "owner changes invalidate receipt binding even when numerical optima match")


def _interruption_and_failure_keep_the_standing_plan() -> None:
    case = memory.parse_case(_raw([_object("x", 2, 0, 2), _object("y", 2, 1, 3, 6)]))
    standing = memory.standing_placement(case)
    for limit in (0, 1, 2):
        found = memory.solve_exact(case, limit)
        ensure(found["status"] == "incomplete" and found["placement"] == standing
               and found["standing_preserved"] and found["nodes"] <= limit,
               f"cutoff must preserve the plan and never claim infeasibility: {found}")
    for report in memory.compare_heuristics(case, 0):
        ensure(report["status"] == "incomplete" and report["placement"] == standing,
               f"heuristic interruption lost standing plan: {report}")
    impossible = memory.parse_case(_raw([_object("x", 3, 0, 2),
                                         _object("y", 3, 0, 2)], 5))
    found = memory.solve_exact(impossible, 0)
    ensure(found["status"] == "infeasible" and found["placement"] is None
           and found["arenas"][0]["certificate"]["method"] == "load-exceeds-capacity",
           f"load is sufficient to prove capacity refusal without search: {found}")
    aligned = memory.parse_case(_raw([_object("x", 1, 0, 2, 0, 4),
                                      _object("y", 1, 0, 2, 0, 4)], 4))
    ensure(memory.solve_exact(aligned, 0)["status"] == "incomplete",
           "an alignment-infeasible case needs search, not a timeout verdict")
    ensure(memory.solve_exact(aligned)["status"] == "infeasible",
           "complete enumeration can prove infeasibility beyond the load bound")
    oversized = memory.parse_case(_raw([_object(str(i), 1, 0, 1, i * 2)
                                        for i in range(memory.MAX_EXACT_OBJECTS + 1)], 40))
    found = memory.solve_exact(oversized)
    ensure(found["status"] == "incomplete" and found["standing_preserved"],
           "the explicit small-instance limit must not claim infeasibility")


def _replay_refutes_a_false_optimum_and_bounds_its_memory() -> None:
    raw = _raw([_object("x", 1, 0, 2), _object("y", 1, 0, 2, 4)], 8)
    case = memory.parse_case(raw)
    false = memory.solve_exact(case)
    false["best_placement"] = memory.standing_placement(case)
    false["arenas"][0]["best_span"] = 5
    false["arenas"][0]["certificate"] = {"method": "exhaustive", "infeasible_through": 4}
    replay = memory.verify_optimality(case, false)
    ensure(replay["status"] == "rejected"
           and "smaller feasible placement" in replay["findings"][0],
           f"independent replay failed to find a refuting witness: {replay}")
    raw["arenas"][0]["capacity"] = 10 ** 30
    raw["objects"][1]["base"] = 10 ** 29
    enormous = memory.parse_case(raw)
    false["contract_sha256"] = memory.contract_hash(enormous)
    false["best_placement"] = memory.standing_placement(enormous)
    false["arenas"][0]["best_span"] = 10 ** 29 + 1
    false["arenas"][0]["certificate"]["infeasible_through"] = 10 ** 29
    replay = memory.verify_optimality(enormous, false)
    ensure(replay["status"] == "incomplete" and replay["nodes"] == 0,
           f"huge integer domains must not pool memory or refute an unchecked claim: {replay}")


def _brute_optimum(raw: dict[str, Any]) -> int | None:
    """An independent exhaustive integer grid, sharing no planner/checker arithmetic."""
    objects = raw["objects"]
    capacity = raw["arenas"][0]["capacity"]
    best: int | None = None
    domains = [range(0, capacity - obj["size"] + 1, obj["alignment"]) for obj in objects]
    for bases in product(*domains):
        valid = True
        for i, left in enumerate(objects):
            for j in range(i):
                right = objects[j]
                simultaneous = set(range(left["start"], left["reuse"])) & set(
                    range(right["start"], right["reuse"]))
                occupied = set(range(bases[i], bases[i] + left["size"])) & set(
                    range(bases[j], bases[j] + right["size"]))
                if simultaneous and occupied:
                    valid = False
        if valid:
            span = max(int(base) + int(obj["size"])
                       for base, obj in zip(bases, objects, strict=True))
            best = span if best is None else min(best, span)
    return best


def _exact_search_matches_an_independent_grid() -> None:
    rng = random.Random(812014)  # noqa: S311 - reproducible test sampling, no security use
    for trial in range(40):
        objects: list[dict[str, Any]] = []
        for i in range(3):
            start = rng.randrange(4)
            objects.append(_object(str(i), rng.randrange(1, 4), start,
                                   start + rng.randrange(1, 4), alignment=rng.randrange(1, 3)))
        raw = _raw(objects, 7)
        case = memory.parse_case(raw)
        expected = _brute_optimum(raw)
        actual = memory.solve_exact(case)
        if expected is None:
            ensure(actual["status"] == "infeasible", f"trial {trial}: {actual}, expected no fit")
        else:
            ensure(actual["status"] == "optimal"
                   and actual["arenas"][0]["best_span"] == expected,
                   f"trial {trial}: {actual}, expected {expected}")
            ensure(memory.verify_optimality(case, actual)["status"] == "verified",
                   f"trial {trial}: independent certificate replay failed")


def _heuristics_are_deterministic_and_keep_arenas_separate() -> None:
    raw = _raw([_object("x", 2, 0, 2), _object("y", 3, 1, 3, 6),
                _object("z", 3, 3, 5, 9)])
    raw["arenas"].append({"id": "b", "owner": "other-owner", "capacity": 5})
    raw["objects"].append(_object("private", 5, 0, 5, arena="b"))
    case = memory.parse_case(raw)
    before = deepcopy(raw)
    first, second = memory.compare_heuristics(case), memory.compare_heuristics(case)
    ensure(first == second and raw == before, "heuristics must be reproducible and nonmutating")
    exact = memory.solve_exact(case)
    optima = {r["arena"]: r["best_span"] for r in exact["arenas"]}
    for report in first:
        ensure(report["status"] == "feasible" and not memory.check_placement(case, report["placement"]),
               f"heuristic emitted an invalid plan: {report}")
        ensure(all(report["spans"][arena] >= span for arena, span in optima.items()),
               f"heuristic claims a span below the exact optimum: {report}")
        ensure(report["spans"]["b"] == 5, "idle bytes in another arena cannot pay this owner")


def cases() -> list[Case]:
    return [
        Case("schema-is-explicit", _schema_is_explicit),
        Case("candidate-cannot-change-contract", _candidate_cannot_change_the_contract),
        Case("load-and-optimum-have-separate-certificates", _load_and_exact_optimum_have_separate_certificates),
        Case("interruption-and-failure-keep-standing", _interruption_and_failure_keep_the_standing_plan),
        Case("replay-refutes-false-optimum-and-bounds-memory", _replay_refutes_a_false_optimum_and_bounds_its_memory),
        Case("exact-search-matches-independent-grid", _exact_search_matches_an_independent_grid),
        Case("heuristics-deterministic-and-arenas-separate", _heuristics_are_deterministic_and_keep_arenas_separate),
    ]
