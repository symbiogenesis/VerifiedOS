# SPDX-License-Identifier: Apache-2.0
"""Protocol mutations, independently derived conflicts and extraction replay."""

import copy
import random
from collections.abc import Callable
from itertools import combinations
from typing import Any

from tests.harness import Case, ensure
from vos import memory_planner_contracts as contracts


def _event(op: str, name: str = "a", *, transfer: str | None = None) -> dict[str, Any]:
    result = {"op": op, "object": name}
    if transfer is not None:
        result["token"] = transfer
    return result


def _finish(outcome: str = "normal") -> dict[str, Any]:
    return {"op": "finish", "outcome": outcome}


def _service(name: str) -> list[dict[str, Any]]:
    return [_event(op, name) for op in ("acquire", "release", "revoke", "sweep", "scrub", "barrier")]


def _contract(body: list[dict[str, Any]], names: tuple[str, ...] = ("a",),
              outcomes: tuple[str, ...] = ("normal",)) -> dict[str, Any]:
    return {"schema": contracts.SCHEMA, "name": "test-service", "slots": 1,
            "pools": [{"id": "p", "capacity": 64}],
            "objects": [{"id": n, "size": 4, "allowed_pools": ["p"]} for n in names],
            "outcomes": list(outcomes), "body": body}


def _reject(fn: Callable[[], object], text: str,
            kind: type[contracts.ContractError] = contracts.ContractError) -> None:
    try:
        fn()
    except kind as exc:
        ensure(text in str(exc), f"expected {text!r}, got {exc}")
    else:
        raise AssertionError(f"expected refusal: {text}")


def _edge_set(report: dict[str, Any]) -> set[frozenset[str]]:
    return {frozenset(pair) for pair in report["instance"]["conflicts"]}


def _fits(report: dict[str, Any], offsets: dict[str, int]) -> bool:
    """Independent small-fixture extent check, with no extractor helper calls."""
    sizes = {obj["id"]: obj["size"] for obj in report["instance"]["buffers"]}
    return all(offsets[a] + sizes[a] <= offsets[b] or offsets[b] + sizes[b] <= offsets[a]
               for a, b in report["instance"]["conflicts"])


def _demo_savings_and_async_refutation() -> None:
    normal = contracts.extract_contract(contracts.demo_contract())
    late = contracts.extract_contract(contracts.demo_contract(late_completion=True))
    ensure(normal["evidence"]["expanded_paths"] == 4, "all exceptional outcomes must be explored")
    packed = {f"{phase}@{slot}": slot * 4 * 1024 * 1024
              for slot in range(4) for phase in ("phase-a", "phase-b")}
    ensure(_fits(normal, packed), "disjoint phases should fit the illustrative 16 MiB layout")
    ensure(not _fits(late, packed), "accepted late DMA must reject that same physical layout")
    ensure(len(_edge_set(late) - _edge_set(normal)) == 4,
           "late branch must add one same-slot conflict for every request slot")
    for slot in range(4):
        ensure(frozenset((f"phase-a@{slot}", f"phase-b@{slot}")) not in _edge_set(normal),
               "mutually disjoint local phases may share backing")
    ensure("source and target refinement remain assumptions" in normal["evidence"]["scope"],
           "evidence may not claim a Vela or machine proof")


def _generated_interleavings() -> None:
    """Generate valid protocols; independently derive edges from acquire/barrier indices."""
    rng = random.Random(7182)  # noqa: S311 - deterministic protocol test generation
    protocols = {
        "a": [_event("acquire"), _event("submit", transfer="dma"), _event("release"),
              _event("revoke"), _event("complete", transfer="dma"), _event("sweep"),
              _event("scrub"), _event("barrier")],
        "b": _service("b"), "c": _service("c"),
    }
    branches: list[dict[str, Any]] = []
    union: set[frozenset[str]] = set()
    for case in range(80):
        pending = copy.deepcopy(protocols)
        events: list[dict[str, Any]] = []
        while pending:
            name = rng.choice(sorted(pending))
            events.append(pending[name].pop(0))
            if not pending[name]:
                del pending[name]
        endpoints = {name: (next(i for i, e in enumerate(events)
                                if e["object"] == name and e["op"] == "acquire"),
                            next(i for i, e in enumerate(events)
                                 if e["object"] == name and e["op"] == "barrier"))
                     for name in protocols}
        expected = {frozenset((f"{a}@0", f"{b}@0")) for a, b in combinations(protocols, 2)
                    if max(endpoints[a][0], endpoints[b][0]) < min(endpoints[a][1], endpoints[b][1])}
        body = [*events, _finish()]
        report = contracts.extract_contract(_contract(body, tuple(protocols)))
        ensure(_edge_set(report) == expected, f"independent interval oracle differs in case {case}")
        union.update(expected)
        branches.append({"label": f"interleaving-{case}", "body": body})
    report = contracts.extract_contract(_contract([{"op": "choice", "branches": branches}],
                                                 tuple(protocols)))
    ensure(_edge_set(report) == union, "branch extraction must union every executable alternative")
    ensure(report["evidence"]["expanded_paths"] == 80, "no generated branch may disappear")


def _barrier_mutations() -> None:
    valid = _contract([*_service("a"), _finish()])
    for op in ("release", "revoke", "sweep", "scrub"):
        mutant = copy.deepcopy(valid)
        mutant["body"] = [e for e in mutant["body"] if e["op"] != op]
        _reject(lambda m=mutant: contracts.extract_contract(m), "a:")
    mutant = copy.deepcopy(valid)
    mutant["body"].insert(1, _event("submit", transfer="late"))
    _reject(lambda: contracts.extract_contract(mutant), "device work drain")
    mutant["body"].insert(4, _event("complete", transfer="late"))
    ensure(contracts.extract_contract(mutant)["evidence"]["checked_barriers"] == 1,
           "actual completion must permit the later sweep and reuse barrier")


def _retained_values() -> None:
    body = [_event("acquire"), _event("retain"), _event("release"), _event("use"),
            _event("drop"), _event("revoke"), _event("sweep"), _event("scrub"),
            _event("barrier"), _finish()]
    contracts.extract_contract(_contract(body))
    _reject(lambda: contracts.extract_contract(_contract([e for e in body if e["op"] != "drop"])),
            "device work drain")
    body.insert(2, _event("retain"))
    _reject(lambda: contracts.extract_contract(_contract(body)), "duplicate retained holder")


def _named_holders_and_unique_use() -> None:
    body = [_event("acquire"), {**_event("retain"), "holder": "parser"},
            {**_event("retain"), "holder": "writer"}, _event("release"),
            {**_event("drop"), "holder": "parser"},
            {**_event("use"), "holder": "writer"},
            {**_event("drop"), "holder": "writer"}, _event("revoke"),
            _event("sweep"), _event("scrub"), _event("barrier"), _finish()]
    source = _contract(body)
    source["objects"][0]["retained_limit"] = 2
    result = contracts.extract_contract(source)
    ensure(result["evidence"]["paths"][0]["peak_retained_holders"] == 2,
           "both named obligations must be charged and retained")
    ensure("retained_limit" not in result["instance"]["buffers"][0],
           "source accounting metadata must not become an unknown placement constraint")
    bad = copy.deepcopy(source)
    bad["body"][5]["holder"] = "parser"
    _reject(lambda: contracts.extract_contract(bad), "stale retained holder")
    bad = copy.deepcopy(source)
    del bad["body"][6]
    _reject(lambda: contracts.extract_contract(bad), "device work drain")
    bad = copy.deepcopy(source)
    bad["objects"][0]["retained_limit"] = 1
    _reject(lambda: contracts.extract_contract(bad), "holder limit exceeded")
    unique = _contract([_event("acquire"), _event("unique-use"), *_service("a")[1:], _finish()])
    contracts.extract_contract(unique)
    unique["body"].insert(1, _event("retain"))
    _reject(lambda: contracts.extract_contract(unique), "unique lexical ownership")
    repeated = copy.deepcopy(source)
    repeated["body"] = [*body[:-1], *copy.deepcopy(body)]
    _reject(lambda: contracts.extract_contract(repeated), "holder reused across lease incarnations")


def _exceptional_cleanup() -> None:
    good = contracts.demo_contract(slots=1)
    bad = copy.deepcopy(good)
    rare = bad["body"][-1]["branches"][-1]["body"]
    rare[:] = [e for e in rare if e.get("op") != "barrier"]
    _reject(lambda: contracts.extract_contract(bad), "terminal outcome retains")
    bad = copy.deepcopy(good)
    bad["outcomes"].remove("timeout")
    _reject(lambda: contracts.extract_contract(bad), "declared outcomes differ")
    bad = _contract([*_service("a"), _finish(), _event("acquire")])
    _reject(lambda: contracts.extract_contract(bad), "instruction after terminal")


def _bounded_repetition_and_choices() -> None:
    repeat = {"op": "repeat", "min": 0, "max": 3, "body": _service("a")}
    result = contracts.extract_contract(_contract([repeat, _finish()]))
    ensure(result["evidence"]["expanded_paths"] == 4, "all bounded iteration counts must be visited")
    ensure(result["evidence"]["interpreted_events"] == 40, "repeat expansion event accounting")
    choice = {"op": "choice", "branches": [
        {"label": "first", "body": _service("a")},
        {"label": "second", "body": _service("b")}]}
    body = [{"op": "repeat", "min": 0, "max": 3, "body": [choice]}, _finish()]
    result = contracts.extract_contract(_contract(body, ("a", "b")))
    ensure(result["evidence"]["expanded_paths"] == 15, "every per-iteration branch combination is required")
    ensure(not result["instance"]["conflicts"], "drained iterations may reuse backing")
    bad = _contract([{"op": "repeat", "min": 0, "max": 1,
                      "body": [_event("acquire")]}, *_service("a")[1:], _finish()])
    _reject(lambda: contracts.extract_contract(bad), "without an active lease")


def _bounded_refusals() -> None:
    demo = contracts.demo_contract()
    _reject(lambda: contracts.extract_contract(demo, max_paths=3), "budget",
            contracts.UnsupportedContractError)
    _reject(lambda: contracts.extract_contract(demo, max_events=2), "budget",
            contracts.UnsupportedContractError)
    _reject(lambda: contracts.extract_contract(demo, max_objects=2), "max_objects",
            contracts.UnsupportedContractError)
    _reject(lambda: contracts.extract_contract(demo, max_pair_checks=1), "max_pair_checks",
            contracts.UnsupportedContractError)
    loop = _contract([{"op": "repeat", "min": 0, "max": 1000001, "body": []}, _finish()])
    _reject(lambda: contracts.extract_contract(loop), "budget", contracts.UnsupportedContractError)
    deep: list[dict[str, Any]] = _service("a")
    for i in range(5):
        deep = [{"op": "choice", "branches": [{"label": str(i), "body": deep}]}]
    _reject(lambda: contracts.extract_contract(_contract([*deep, _finish()]), max_depth=2),
            "max_depth", contracts.UnsupportedContractError)
    empty_choice = {"op": "choice", "branches": [{"label": "empty", "body": []}]}
    inner = {"op": "repeat", "min": 10, "max": 10, "body": [empty_choice]}
    outer = {"op": "repeat", "min": 10, "max": 10, "body": [inner]}
    empty = _contract([outer, _finish()], ())
    result = contracts.extract_contract(empty)
    ensure(result["evidence"]["interpreted_events"] == 1,
           "the adversarial fixture must generate labels with no resource events")
    ensure(len(result["evidence"]["paths"][0]["labels"]) == 111,
           "nested empty loops must retain their complete branch annotations")
    _reject(lambda: contracts.extract_contract(empty, max_expansion_work=100),
            "max_expansion_work", contracts.UnsupportedContractError)
    deep_empty: list[dict[str, Any]] = []
    for _ in range(70):
        deep_empty = [{"op": "choice", "branches": [{"label": "nested", "body": deep_empty}]}]
    _reject(lambda: contracts.extract_contract(_contract([*deep_empty, _finish()], ())),
            "snapshot depth", contracts.UnsupportedContractError)
    cyclic: dict[str, Any] = {}
    cyclic["cycle"] = cyclic
    _reject(lambda: contracts.extract_contract(cyclic), "snapshot depth",
            contracts.UnsupportedContractError)


def _device_tokens_and_reacquisition() -> None:
    body = [_event("acquire"), _event("submit", transfer="x"), _event("submit", transfer="x"),
            *_service("a")[1:], _finish()]
    _reject(lambda: contracts.extract_contract(_contract(body)), "duplicate outstanding")
    body[2] = _event("complete", transfer="y")
    _reject(lambda: contracts.extract_contract(_contract(body)), "unmatched device completion")
    body = [_event("acquire"), _event("release"), _event("acquire"), _finish()]
    _reject(lambda: contracts.extract_contract(_contract(body)), "before its safe-reuse barrier")
    body = [*_service("a"), *_service("a"), _finish()]
    ensure(contracts.extract_contract(_contract(body))["evidence"]["checked_barriers"] == 2,
           "a drained object can be reacquired without creating a second placement identity")
    cycle = [_event("acquire"), _event("submit", transfer="x"),
             _event("complete", transfer="x"), *_service("a")[1:]]
    _reject(lambda: contracts.extract_contract(_contract([*cycle, *cycle, _finish()])),
            "device token reused across lease incarnations")
    fresh = copy.deepcopy(cycle)
    fresh[1]["token"] = fresh[2]["token"] = "next-incarnation"
    ensure(contracts.extract_contract(_contract([*cycle, *fresh, _finish()]))
           ["evidence"]["checked_barriers"] == 2,
           "distinct device identities permit safe bounded reincarnation")


def _unsupported_constraints_and_malformed_inputs() -> None:
    source = _contract([*_service("a"), _finish()])
    for field, value in (("alias_of", "b"), ("intervals", [[0, 1]]), ("runtime_size", 4)):
        bad = copy.deepcopy(source)
        bad["objects"][0][field] = value
        _reject(lambda m=bad: contracts.extract_contract(m), "unsupported fields",
                contracts.UnsupportedContractError)
    for field, value in (("size", True), ("alignment", 0), ("fixed_offset", -1)):
        bad = copy.deepcopy(source)
        bad["objects"][0][field] = value
        _reject(lambda m=bad: contracts.extract_contract(m), "expected an integer")
    bad = copy.deepcopy(source)
    bad["objects"].append(copy.deepcopy(bad["objects"][0]))
    _reject(lambda: contracts.extract_contract(bad), "duplicate object")
    bad = copy.deepcopy(source)
    bad["objects"][0]["allowed_pools"] = ["missing"]
    _reject(lambda: contracts.extract_contract(bad), "declared pools")
    bad = copy.deepcopy(source)
    bad["pools"][0]["reserved"] = [[0, 0]]
    _reject(lambda: contracts.extract_contract(bad), "reserved extent must be nonempty")
    bad = copy.deepcopy(source)
    bad["body"][0]["object"] = "missing"
    _reject(lambda: contracts.extract_contract(bad), "unknown object")
    bad = copy.deepcopy(source)
    bad["body"][0]["op"] = "runtime-allocate"
    _reject(lambda: contracts.extract_contract(bad), "unsupported operation",
            contracts.UnsupportedContractError)


def _declaration_preservation_and_slot_isolation() -> None:
    source = _contract([*_service("a"), *_service("b"), _finish()], ("a", "b"))
    source["slots"] = 2
    source["pools"][0]["reserved"] = [[0, 4]]
    source["objects"][0].update(alignment=8, fixed_pool="p", fixed_offset=8)
    result = contracts.extract_contract(source)
    ensure(result["instance"]["pools"] == source["pools"], "pool reservations must survive extraction")
    for obj in result["instance"]["buffers"]:
        if obj["id"].startswith("a@"):
            ensure(obj["alignment"] == 8 and obj["fixed_offset"] == 8 and obj["fixed_pool"] == "p",
                   "all placement constraints must survive extraction")
    expected = {frozenset((f"{a}@0", f"{b}@1")) for a in ("a", "b") for b in ("a", "b")}
    ensure(_edge_set(result) == expected, "independent request slots must not share their reservations")


def _evidence_identity_and_replay() -> None:
    source = contracts.demo_contract()
    original = copy.deepcopy(source)
    report = contracts.extract_contract(source)
    ensure(source == original, "extraction must not mutate the caller's contract")
    ensure(not contracts.replay_extraction(source, report), "valid extraction evidence must replay")
    reordered = {key: source[key] for key in reversed(source)}
    ensure(report == contracts.extract_contract(reordered), "JSON key order is not semantic identity")
    broken = copy.deepcopy(report)
    broken["instance"]["conflicts"].clear()
    ensure(bool(contracts.replay_extraction(source, broken)), "conflict deletion must invalidate replay")
    source["objects"][0]["size"] += 1
    changed = contracts.extract_contract(source)
    ensure(changed["evidence"]["contract_sha256"] != report["evidence"]["contract_sha256"]
           and changed["evidence"]["instance_sha256"] != report["evidence"]["instance_sha256"],
           "both input and placement identities must change when an object bound changes")


def cases() -> list[Case]:
    return [
        Case("contracts bounded desktop packing and late completion refutation", _demo_savings_and_async_refutation),
        Case("contracts generated interleavings against independent interval oracle", _generated_interleavings),
        Case("contracts reuse barrier prerequisite mutations", _barrier_mutations),
        Case("contracts retained values outlive lexical release", _retained_values),
        Case("contracts named obligations and unique in-place use", _named_holders_and_unique_use),
        Case("contracts exceptional paths require complete cleanup", _exceptional_cleanup),
        Case("contracts bounded loops enumerate every branch combination", _bounded_repetition_and_choices),
        Case("contracts exhausted bounds refuse partial conflict graphs", _bounded_refusals),
        Case("contracts device identities and safe reacquisition", _device_tokens_and_reacquisition),
        Case("contracts malformed and unsupported source constraints", _unsupported_constraints_and_malformed_inputs),
        Case("contracts placement constraints survive independent slot expansion", _declaration_preservation_and_slot_isolation),
        Case("contracts content-bound extraction evidence replays", _evidence_identity_and_replay),
    ]
