# SPDX-License-Identifier: Apache-2.0
"""Portable boundary checks, retained baselines and finite certificate replay."""

import itertools
import random
from copy import deepcopy
from dataclasses import asdict
from typing import Any

from tests.harness import Case, ensure
from vos import memory_planner as memory


def _buffer(identifier: str, size: int, **extra: object) -> dict[str, Any]:
    return {"id": identifier, "size": size, "allowed_pools": ["a"],
            "intervals": [[0, 2]], **extra}


def _raw(buffers: list[dict[str, Any]], capacity: int = 12, **extra: object) -> dict[str, Any]:
    return {"name": "portable-test", "pools": [{"id": "a", "capacity": capacity}],
            "buffers": buffers, **extra}


def _placement(*offsets: int, pool: str = "a") -> memory.Placement:
    return [{"id": str(i), "pool": pool, "offset": offset} for i, offset in enumerate(offsets)]


def _refused(raw: object) -> None:
    try:
        memory.parse_instance(raw)
    except memory.PlannerError:
        return
    raise AssertionError(f"bad schema accepted: {raw}")


def _schema_and_integer_boundaries() -> None:
    raw = _raw([_buffer("0", 0)])
    for key, value in (("size", True), ("size", -1), ("size", memory.MAX_INTEGER + 1),
                       ("alignment", 0), ("alignment", 0.5), ("intervals", [[2, 2]]),
                       ("intervals", [[-1, 2]]), ("allowed_pools", []),
                       ("allowed_pools", ["missing"]), ("fixed_pool", "missing"),
                       ("fixed_offset", -1), ("alias_offset", 1), ("gap_window", [0, 3])):
        mutant = deepcopy(raw)
        mutant["buffers"][0][key] = value
        _refused(mutant)
    for mutant in ([], {}, {**raw, "relocation": True}, {**raw, "buffers": raw["buffers"] * 2},
                   {**raw, "conflicts": [["0", "missing"]]},
                   {**raw, "pools": [{"id": "a", "capacity": 2, "reserved": [[0, 3]]}]}):
        _refused(mutant)
    instance = memory.parse_instance(raw)
    raw["buffers"][0]["size"] = 3
    ensure(instance.buffers[0].size == 0, "parser retained a mutable input container")
    huge = memory.parse_instance(_raw([_buffer("0", 0)], memory.MAX_INTEGER))
    result = memory.solve(huge, work_budget=1, certify=True)
    ensure(result["evidence"]["status"] == "checked optimal", "zero size huge domain overflowed")
    huge_positive = memory.parse_instance(_raw([_buffer("0", 1)], memory.MAX_INTEGER))
    ensure(memory.solve(huge_positive, work_budget=1)["placement"] == _placement(0),
           "bounded search materialized a huge address range")


def _checker_preserves_every_constraint() -> None:
    instance = memory.parse_instance(_raw([
        _buffer("0", 3, alignment=3, intervals=[[0, 2], [4, 6]]),
        _buffer("1", 3, intervals=[[2, 4]], fixed_offset=0),
    ]))
    valid = _placement(0, 0)
    ensure(not memory.check_placement(instance, valid), "half-open gaps must permit sharing")
    ensure(memory.pool_heights(instance, valid) == {"a": 3}, "objective drift")
    for mutant in (valid[:-1], [*valid, valid[0]], {"0": 0}, _placement(1, 0), _placement(12, 0),
                   _placement(0, 3), [*valid, {"id": "unknown", "pool": "a", "offset": 0}]):
        ensure(bool(memory.check_placement(instance, mutant)), f"bad candidate accepted: {mutant}")
    for key, value in (("pool", "other"), ("offset", True), ("offset", -1), ("size", 1)):
        mutant = deepcopy(valid)
        mutant[0][key] = value
        ensure(bool(memory.check_placement(instance, mutant)), f"constraint mutation accepted: {key}")
    conflict = asdict(instance)
    conflict["conflicts"] = [["0", "1"]]
    ensure(bool(memory.check_placement(memory.parse_instance(conflict), valid)),
           "explicit conflicts must augment separated lifetimes")
    reserved = memory.parse_instance(_raw([_buffer("0", 2)],
                                         pools=[{"id": "a", "capacity": 12, "reserved": [[0, 4]]}]))
    ensure(bool(memory.check_placement(reserved, _placement(0))), "reserved region overwritten")
    ensure(memory.pool_heights(reserved, _placement(4)) == {"a": 6}, "reservation omitted")


def _aliases_and_zero_extents() -> None:
    instance = memory.parse_instance(_raw([
        _buffer("0", 6), _buffer("1", 3, alias_of="0", alias_offset=3),
        _buffer("2", 0, fixed_offset=12),
    ]))
    ensure(not memory.check_placement(instance, _placement(0, 3, 12)), "direct view rejected")
    ensure(memory.pool_heights(instance, _placement(0, 3, 12)) == {"a": 6}, "zero extent charged")
    ensure(bool(memory.check_placement(instance, _placement(0, 0, 12))), "alias offset dropped")
    bad = asdict(instance)
    bad["buffers"] = list(bad["buffers"])
    bad["buffers"][2]["alias_of"] = "1"
    _refused(bad)
    instance = memory.parse_instance(_raw([
        _buffer("0", 6, intervals=[[0, 1]]),
        _buffer("1", 3, alias_of="0", alias_offset=3, intervals=[[1, 4]]),
        _buffer("2", 3, intervals=[[2, 3]]),
    ]))
    ensure(bool(memory.check_placement(instance, _placement(0, 3, 3))),
           "live view must conflict after root's last use")


def _baseline_retention_and_componentwise_objective() -> None:
    raw = _raw([_buffer("0", 2, allowed_pools=["a", "b"]),
                _buffer("1", 2, allowed_pools=["a", "b"])],
               pools=[{"id": "a", "capacity": 10}, {"id": "b", "capacity": 10}])
    instance = memory.parse_instance(raw)
    baseline = [{"id": "0", "pool": "a", "offset": 6},
                {"id": "1", "pool": "b", "offset": 0}]
    regression = [{"id": "0", "pool": "b", "offset": 2},
                  {"id": "1", "pool": "b", "offset": 0}]
    better = [{"id": "0", "pool": "a", "offset": 0},
              {"id": "1", "pool": "b", "offset": 0}]

    def broken(copy: memory.Instance) -> memory.Placement:
        object.__setattr__(copy.buffers[0], "size", 0)
        raise RuntimeError("failed optional generator")

    report = memory.plan(instance, baseline, candidates=[regression, [], broken, better], certify=True)
    ensure(report["placement"] == better, "selection lost checked improvement")
    ensure(len(report["evidence"]["rejected"]) == 3, "failed candidates missing")
    ensure(instance.buffers[0].size == 2, "generator mutated retained instance")
    ensure(memory.verify_evidence(instance, report)["status"] == "checked optimal",
           "checked result did not replay")
    called = []

    def observe(_: memory.Instance) -> memory.Placement:
        called.append(True)
        return better

    refused = memory.plan(instance, [], candidates=[observe])
    ensure(refused["placement"] is None and not called, "invalid baseline reached optional work")
    first = memory.plan(instance, baseline, work_budget=3, certify=True, replay_budget=0)
    second = memory.plan(instance, baseline, work_budget=3, certify=True, replay_budget=0)
    ensure(first == second and first["evidence"]["status"] == "checked feasible",
           "deterministic cutoff changed incumbent or claimed optimality")
    ensure(first["evidence"]["baseline_pool_heights"] == {"a": 8, "b": 2},
           "baseline pool metric lost")


def _certificates_are_scoped_and_replayed() -> None:
    instance = memory.parse_instance(_raw([_buffer("0", 2), _buffer("1", 2)], 4))
    solved = memory.solve(instance, work_budget=20, certify=True)
    ensure(solved["evidence"]["status"] == "checked optimal", "small exact instance uncertified")
    ensure(memory.verify_evidence(instance, solved)["status"] == "checked optimal", "replay failed")
    for kind in ("digest", "height", "baseline", "placement", "objective"):
        mutant = deepcopy(solved)
        if kind == "digest":
            mutant["evidence"]["instance_digest"] = "wrong"
        elif kind == "height":
            mutant["evidence"]["pool_heights"]["a"] = 0
        elif kind == "baseline":
            mutant["evidence"]["baseline_placement"] = []
        elif kind == "placement":
            mutant["placement"][1]["offset"] = 0
        else:
            mutant["evidence"]["objective"]["metric"] = "committed-pages"
        ensure(memory.verify_evidence(instance, mutant)["status"] in {"unknown", "unsupported"},
               f"tampered certificate accepted: {kind}")
    loose = memory.parse_instance(_raw([_buffer("0", 2), _buffer("1", 2)], 7))
    certificate = memory.certify_placement(loose, _placement(0, 4))
    ensure(certificate["status"] == "unknown" and bool(certificate.get("counterexample")),
           "false optimality lacked a counterexample")
    impossible = memory.parse_instance(_raw([_buffer("0", 2), _buffer("1", 2)], 3))
    nofit = memory.solve(impossible, work_budget=100, certify=True)
    ensure(nofit["evidence"]["status"] == "checked infeasible", "finite nofit incorrectly classified")
    ensure(memory.verify_evidence(impossible, nofit)["status"] == "checked infeasible",
           "infeasibility did not replay")
    unknown = memory.solve(impossible, work_budget=0)
    ensure(unknown["evidence"]["status"] == "unknown", "budget exhaustion became infeasibility")
    bounded = memory.certify_placement(instance, _placement(0, 2), work_budget=0)
    ensure(bounded["status"] == "unknown", "unfinished replay became optimality")
    one = memory.parse_instance(_raw([_buffer("0", 3, fixed_offset=3)], 6))
    lower = memory.certify_placement(one, _placement(3), work_budget=0)
    ensure(lower["status"] == "checked optimal" and lower["replay_work"] == 0,
           "independent fixed-extent lower bound missing")


def _exact_search_matches_an_independent_grid() -> None:
    rng = random.Random(4221)  # noqa: S311 - deterministic differential test inputs, no secrets
    for trial in range(25):
        sizes = [rng.randint(1, 3) for _ in range(3)]
        intervals = [(rng.randrange(3), rng.randrange(3, 5)) for _ in sizes]
        buffers = [_buffer(str(i), size, intervals=[list(intervals[i])])
                   for i, size in enumerate(sizes)]
        instance = memory.parse_instance(_raw(buffers, 6))
        optima = []
        for offsets in itertools.product(range(6), repeat=3):
            if any(offsets[i] + sizes[i] > 6 for i in range(3)):
                continue
            if any(max(intervals[i][0], intervals[j][0]) < min(intervals[i][1], intervals[j][1])
                   and max(offsets[i], offsets[j]) < min(offsets[i] + sizes[i], offsets[j] + sizes[j])
                   for i in range(3) for j in range(i)):
                continue
            optima.append(max(offsets[i] + sizes[i] for i in range(3)))
        actual = memory.solve(instance, work_budget=500, certify=True, replay_budget=500)
        if optima:
            ensure(actual["evidence"]["status"] == "checked optimal"
                   and actual["evidence"]["pool_heights"]["a"] == min(optima),
                   f"trial {trial}: finite result disagrees with independent grid")
        else:
            ensure(actual["evidence"]["status"] == "checked infeasible", f"trial {trial}: false fit")


def cases() -> list[Case]:
    return [Case("schema-and-integer-boundaries", _schema_and_integer_boundaries),
            Case("checker-preserves-every-constraint", _checker_preserves_every_constraint),
            Case("aliases-and-zero-extents", _aliases_and_zero_extents),
            Case("baseline-retention-and-pool-objective", _baseline_retention_and_componentwise_objective),
            Case("certificates-scoped-and-replayed", _certificates_are_scoped_and_replayed),
            Case("exact-search-independent-grid", _exact_search_matches_an_independent_grid)]
