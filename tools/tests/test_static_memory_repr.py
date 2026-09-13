# SPDX-License-Identifier: Apache-2.0
"""Independent finite tests of the legal-position layer and its lower bound."""

import dataclasses
import json
import random
from collections.abc import Callable, Sequence
from itertools import product
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import memplan
from vos import static_memory as memory
from vos import static_memory_corpus as witnesses
from vos import static_memory_repr as representability

ROOT = Path(__file__).resolve().parents[2]


def _toy_granule(length: int) -> int:
    """A coarse granule at small extents, so an exhaustive grid stays exhaustible.

    The ported granule is one byte below its threshold, which no instance small enough
    to enumerate completely can reach, so a soundness test over the real function would
    be a test over the empty constraint.
    """
    if length < 4:
        return 1
    return 2 if length < 8 else 4


def _object(identifier: str, size: int, start: int, reuse: int,
            base: int = 0, alignment: int = 1) -> dict[str, Any]:
    return {"id": identifier, "arena": "a", "size": size, "payload": size,
            "alignment": alignment, "start": start, "payload_end": reuse,
            "authority_end": reuse, "sweep_end": reuse, "reuse": reuse, "base": base}


def _raw(objects: list[dict[str, Any]], capacity: int) -> dict[str, Any]:
    return {"name": "repr-test", "mode": "single-fixed-trace",
            "provenance": "synthetic test fixture, no product measurement",
            "arenas": [{"id": "a", "owner": "owner-a", "capacity": capacity}],
            "objects": objects}


def _load_here(case: memory.Case, arena_id: str) -> int:
    """The charged live load, spelled here rather than asked of the module under test.

    The layer's bound starts from `memory.peak_load`, so comparing it against that same
    call would read one value against itself; this is an independent second spelling,
    and it is what the bound's floor is checked against.
    """
    objects = [obj for obj in case.objects if obj.arena == arena_id]
    instants = {obj.start for obj in objects} | {obj.reuse for obj in objects}
    return max((sum(obj.size for obj in objects if obj.start <= time < obj.reuse)
                for time in instants), default=0)


def _grid_optimum(case: memory.Case, capacity: int,
                  granule: Callable[[int], int] | None) -> int | None:
    """An independent exhaustive grid sharing no arithmetic with the layer under test.

    Legality is spelled here rather than asked of the module: a base must be a multiple
    of the object's alignment and, where a granule function is supplied, of that
    object's granule.
    """
    objects = case.objects
    domains = [[base for base in range(0, capacity - obj.size + 1, obj.alignment)
                if granule is None or base % granule(obj.size) == 0]
               for obj in objects]
    best: int | None = None
    for bases in product(*domains):
        legal = True
        for i, left in enumerate(objects):
            for j in range(i):
                right = objects[j]
                simultaneous = (set(range(left.start, left.reuse))
                                & set(range(right.start, right.reuse)))
                shared = (set(range(bases[i], bases[i] + left.size))
                          & set(range(bases[j], bases[j] + right.size)))
                if simultaneous and shared:
                    legal = False
        if legal:
            span = max(base + obj.size
                       for base, obj in zip(bases, objects, strict=True))
            best = span if best is None else min(best, span)
    return best


def _granule_comes_from_the_plan_and_a_mutant_refuses() -> None:
    ensure(representability.granule_of_size(200) == memplan.representable_granule(200),
           "the layer must derive its granule from the plan's own function")
    case = memory.parse_case(_raw([_object("x", 3, 0, 2, 0), _object("y", 5, 0, 2, 3)], 64))
    placement = memory.standing_placement(case)
    ensure(not memory.check_placement(case, placement,
                                      legal_base=representability.base_refusal),
           "sub-threshold extents have a one-byte granule and refuse no base")
    with patch.object(memplan, "representable_granule", lambda length: 8):
        findings = memory.check_placement(case, placement,
                                          legal_base=representability.base_refusal)
        ensure(any(item.startswith("representable:") and "y" in item for item in findings),
               f"a coarser granule must refuse the base it no longer divides: {findings}")
        ensure(representability.base_refusal(representability.probe("y", 5), 3) is not None,
               "the layer must read the mutated granule at every entry point")
        moved = memory.solve_exact(case, legal_base=representability.base_refusal)
        ensure(moved["arenas"][0]["best_span"] == 11,
               f"the search must move the refused object to its next legal base: {moved}")
    ensure(not memory.check_placement(case, placement,
                                      legal_base=representability.base_refusal),
           "the mutation must not outlive its patch")


def _exact_length_refusals_report_rather_than_round() -> None:
    obj = representability.probe("odd", 129)
    refusal = representability.length_refusal(obj)
    ensure(refusal is not None, "an extent its granule does not divide has no exact bounds")
    if refusal is None:
        raise AssertionError("unreachable")
    ensure(refusal["size"] == 129 and refusal["quantized_size"] == 130
           and refusal["padding_bytes"] == 1,
           f"the refusal must carry what a quantized plan would charge: {refusal}")
    ensure(representability.length_refusal(representability.probe("even", 130)) is None,
           "an extent its own granule divides is exactly representable")
    for size in (1, 127, 128, 129, 255, 256, 1000, 1025, 4096, 4097, 1 << 20):
        quantized = representability.quantized_size(size)
        granule = representability.granule_of_size(quantized)
        ensure(quantized >= size and quantized % granule == 0,
               f"the quantized extent must be a fixed point of its own granule: {size}")
    raw = representability.families()[0]
    before = json.dumps(raw, sort_keys=True)
    item = representability.compare_case(raw)
    ensure(json.dumps(raw, sort_keys=True) == before,
           "reporting a refusal must not rewrite the contract's charged sizes")
    refusals = [row for arena in item["arenas"] for row in arena["exact_length_refusals"]]
    ensure(len(refusals) == 1 and refusals[0]["id"] == "wide",
           f"the fixture's one inexact extent must be named: {refusals}")


def _stacked_bound_is_sound_against_an_independent_grid() -> None:
    rng = random.Random(20260912)  # noqa: S311 - reproducible sampling, no security use
    capacity = 14
    # The three arms the sample has to reach: a bound that settles a span outright, a
    # bound the charged load alone supplies, and a bound the legal positions raise
    # above that load. Whether any sampled instance separates the bound from the
    # optimum is an observation and not a requirement, so it is not asserted.
    checked = {"settled": 0, "at_load": 0, "raised": 0}
    with patch.object(memplan, "representable_granule", _toy_granule):
        for trial in range(60):
            objects: list[dict[str, Any]] = []
            for index in range(3):
                start = rng.randrange(3)
                objects.append(_object(str(index), rng.randrange(1, 8), start,
                                       start + rng.randrange(1, 3),
                                       alignment=rng.randrange(1, 3)))
            case = memory.parse_case(_raw(objects, capacity))
            for representable, granule in ((False, None), (True, _toy_granule)):
                layer = representability.base_refusal if representable else None
                bound = representability.arena_lower_bound(
                    case, "a", representable=representable)
                optimum = _grid_optimum(case, capacity, granule)
                found = memory.solve_exact(case, legal_base=layer)
                ensure(bound >= _load_here(case, "a"),
                       f"trial {trial}: the bound fell below the charged load")
                if optimum is None:
                    ensure(found["status"] == "infeasible",
                           f"trial {trial}: expected no legal placement: {found}")
                    continue
                ensure(found["status"] == "optimal"
                       and found["arenas"][0]["best_span"] == optimum,
                       f"trial {trial}: search and independent grid disagree: {found}")
                ensure(bound <= optimum,
                       f"trial {trial}: bound {bound} exceeds the exhaustive optimum "
                       f"{optimum} under representable={representable}")
                if bound == optimum:
                    checked["settled"] += 1
                if bound == memory.peak_load(case, "a"):
                    checked["at_load"] += 1
                elif representable:
                    checked["raised"] += 1
    ensure(all(count > 0 for count in checked.values()),
           f"the sample must reach every arm of the bound: {checked}")


def _bound_is_strictly_loose_on_a_declared_instance() -> None:
    """The bound is a bound: one declared fixture holds it strictly below the optimum.

    Without such an instance nothing separates `this is a lower bound` from `this
    computes the optimum at instances of this shape`, since the bound meets the optimum
    on every other row of the receipt.
    """
    raw = next(item for item in representability.families()
               if item["name"] == "repr-bound-is-loose")
    case = memory.parse_case(raw)
    capacity = case.arenas[0].capacity
    grid = _grid_optimum(case, capacity, None)
    for representable in (False, True):
        layer = representability.base_refusal if representable else None
        bound = representability.arena_lower_bound(case, "arena",
                                                   representable=representable)
        found = memory.solve_exact(case, legal_base=layer)
        ensure(found["status"] == "optimal" and found["arenas"][0]["best_span"] == grid,
               f"the search and the independent grid must agree here: {found}")
        ensure(bound < found["arenas"][0]["best_span"],
               f"this fixture exists to hold the bound strictly below the optimum: "
               f"{bound} against {found['arenas'][0]['best_span']}")
        ensure(bound >= _load_here(case, "arena"),
               "the bound still stands at or above the charged load")


def _quantized_lengths_are_reported_beside_the_base_model() -> None:
    """A base-quantized span is not a representable plan's span, and the receipt says so."""
    for raw in [*witnesses.corpus("fixture"), *representability.families()]:
        grown = representability.quantized_contract(raw)
        ensure(grown["name"] != raw["name"], "the derived contract is named apart")
        for before, after in zip(raw["objects"], grown["objects"], strict=True):
            ensure(set(before) == set(after),
                   "the derived contract must keep the contract's own field set")
            ensure(after["size"] == representability.quantized_size(before["size"])
                   and after["size"] >= before["size"],
                   f"{before['id']}: the derived extent is its own granule's")
        item = representability.compare_case(raw)
        for row in item["arenas"]:
            grown_span = row["quantized_lengths"]["best_span"]
            span = row["representable"]["best_span"]
            ensure(row["quantized_lengths"]["status"] == "optimal"
                   and grown_span is not None and span is not None,
                   f"{raw['name']}: the quantized-length model must finish here")
            ensure(grown_span >= span,
                   f"{raw['name']}: growing every extent cannot lower the optimum")
            ensure(row["quantized_length_span_cost"] == grown_span - span
                   and row["quantized_length_cost_status"] == "both-optimal",
                   f"{raw['name']}: the reported cost is not the two spans' difference")
    rows = {raw["name"]: representability.compare_case(raw)["arenas"][0]
            for raw in representability.families()}
    inexact = rows["repr-length-only"]
    ensure(inexact["representability_span_cost"] == 0
           and inexact["quantized_length_span_cost"] > 0,
           "an inexact extent at a legal base costs nothing until its length is quantized")
    ensure(len(inexact["exact_length_refusals"]) == 2,
           "both of that fixture's extents have no exact bounds at any base")


def _permits_every_base(obj: memory.Object, base: int) -> str | None:
    """A layer that refuses nothing, and so must decide nothing."""
    del obj, base
    return None


def _default_and_permissive_layers_leave_the_oracle_alone() -> None:
    keys = {"case", "contract_sha256", "status", "work_budget", "nodes", "standing_valid",
            "standing_findings", "standing_preserved", "placement", "best_placement",
            "arenas"}
    permissive: memory.LegalBase = _permits_every_base
    contracts = [*witnesses.corpus("fixture"), *representability.families()]
    for raw in contracts:
        case = memory.parse_case(raw)
        default = memory.solve_exact(case)
        ensure(set(default) == keys, f"the receipt gained a field: {set(default) - keys}")
        ensure(json.dumps(default, sort_keys=True)
               == json.dumps(memory.solve_exact(case, legal_base=None), sort_keys=True),
               f"{case.name}: an absent layer must be the receipt that stood")
        opened = memory.solve_exact(case, legal_base=permissive)
        ensure(json.dumps(opened, sort_keys=True) == json.dumps(default, sort_keys=True),
               f"{case.name}: a layer that refuses nothing must decide nothing")
        if default["status"] == "optimal":
            replay = memory.verify_optimality(case, default)
            ensure(json.dumps(replay, sort_keys=True)
                   == json.dumps(memory.verify_optimality(case, default,
                                                          legal_base=permissive),
                                 sort_keys=True),
                   f"{case.name}: replay under an empty layer must not move")
        plain = memory.compare_heuristics(case)
        ensure(json.dumps(plain, sort_keys=True)
               == json.dumps(memory.compare_heuristics(case, legal_base=None),
                             sort_keys=True),
               f"{case.name}: the heuristics' receipt must not move either")
        opened_rows = memory.compare_heuristics(case, legal_base=permissive)
        for was, now in zip(plain, opened_rows, strict=True):
            ensure(was["placement"] == now["placement"] and was["spans"] == now["spans"]
                   and was["status"] == now["status"],
                   f"{case.name}: first fit moved under a layer that refuses nothing")
            ensure(now["nodes"] >= was["nodes"],
                   "walking to a legal base is work and must be counted")
    case = memory.parse_case(_raw([_object("x", 2, 0, 2, 1, 2)], 8))
    ensure(memory.check_placement(case, memory.standing_placement(case))
           == ["alignment: x base is not a multiple of 2"],
           "the alignment finding must be exactly what it was")


def _first_fit_walks_to_a_legal_base() -> None:
    """First fit under a refusing layer: the walk moves a base, costs work, and can fail.

    A layer that refuses nothing leaves the endpoints where they are, so the advancing
    pass is unexercised until something is refused; every arm of it is driven here.
    """
    raw = next(item for item in representability.families()
               if item["name"] == "repr-threshold-pin")
    case = memory.parse_case(raw)
    plain = memory.compare_heuristics(case)
    walked = memory.compare_heuristics(case, legal_base=representability.base_refusal)
    for was, now in zip(plain, walked, strict=True):
        candidate = now["candidate"]
        ensure(now["status"] == "feasible" and candidate is not None,
               f"{now['method']}: the walk must still place this fixture: {now}")
        if candidate is None:
            raise AssertionError("unreachable")
        for row in candidate:
            obj = next(item for item in case.objects if item.id == row["id"])
            ensure(representability.base_refusal(obj, row["base"]) is None,
                   f"{now['method']}: first fit chose a base the layer refuses: {row}")
        ensure(not memory.check_placement(case, candidate,
                                          legal_base=representability.base_refusal),
               f"{now['method']}: the candidate must pass the independent checker")
        ensure(now["nodes"] > was["nodes"],
               f"{now['method']}: walking to a legal base is work and must be counted")
    by_method = {row["method"]: row for row in walked}
    before = {row["method"]: row for row in plain}
    ensure(_base_of(before["first-fit-start"]["candidate"], "wide") == 3
           and _base_of(by_method["first-fit-start"]["candidate"], "wide") == 4,
           "the endpoint must advance to the least legal base at or above it")
    # An endpoint whose walk leaves the arena is dropped rather than rounded into it.
    tight = memory.parse_case(_raw([_object("pin", 3, 0, 4, 0),
                                    _object("wide", 129, 0, 4, 3)], 132))
    open_rows = {row["method"]: row for row in memory.compare_heuristics(tight)}
    closed_rows = {row["method"]: row
                   for row in memory.compare_heuristics(
                       tight, legal_base=representability.base_refusal)}
    ensure(open_rows["first-fit-start"]["status"] == "feasible"
           and closed_rows["first-fit-start"]["status"] == "no-fit",
           "an endpoint with no legal base inside the arena leaves first fit no fit")
    ensure(memory.solve_exact(tight, legal_base=representability.base_refusal)["status"]
           == "optimal",
           "and that is first fit's failure, not an absence of legal placements")
    # A budget spent inside the walk is a cutoff and never a report of no fit.
    walking = memory.parse_case(_raw([_object("a-pin", 1, 0, 4, 0),
                                      _object("b-big", 1024, 0, 4, 16)], 4096))
    ensure(memory.compare_heuristics(walking, 4)[0]["status"] == "feasible",
           "without a layer this budget finishes, so the walk is what spends it")
    for row in memory.compare_heuristics(walking, 4,
                                         legal_base=representability.base_refusal):
        ensure(row["status"] == "incomplete" and row["candidate"] is None,
               f"a budget exhausted inside the walk is incomplete, not no-fit: {row}")
    finished = memory.compare_heuristics(walking,
                                         legal_base=representability.base_refusal)[0]
    ensure(finished["status"] == "feasible"
           and _base_of(finished["candidate"], "b-big")
           % representability.granule_of_size(1024) == 0,
           f"the same walk under a whole budget reaches a legal base: {finished}")


def _base_of(placement: list[dict[str, Any]] | None, identifier: str) -> int:
    if placement is None:
        raise AssertionError(f"no placement to read {identifier} from")
    base = next(row["base"] for row in placement if row["id"] == identifier)
    if not isinstance(base, int):
        raise TypeError(f"{identifier}: a placement base must be an integer")
    return base


def _every_witness_survives_a_refusing_layer() -> None:
    """Every contract, every method: what first fit returns is what the checker admits.

    The advancing pass is separate from the scan that follows precisely so the blocker
    cursor keeps meeting an ascending candidate list; a skipped blocker would show up
    as an overlapping candidate, which `placement_spans` raises on and this re-checks.
    """
    contracts = [*witnesses.corpus("fixture"), *representability.families()]
    checked = 0
    for raw in contracts:
        case = memory.parse_case(raw)
        for row in memory.compare_heuristics(case,
                                             legal_base=representability.base_refusal):
            candidate = row["candidate"]
            if candidate is None:
                continue
            ensure(not memory.check_placement(case, candidate,
                                              legal_base=representability.base_refusal),
                   f"{raw['name']} {row['method']}: the checker rejects first fit's own "
                   f"candidate")
            checked += 1
    ensure(checked >= len(contracts),
           f"every contract owes at least one checked candidate: {checked}")


def _restriction_never_lowers_an_optimum() -> None:
    for raw in representability.families():
        item = representability.compare_case(raw)
        for row in item["arenas"]:
            plain, exact = row["alignment_only"], row["representable"]
            if plain["status"] != "optimal" or exact["status"] != "optimal":
                raise AssertionError(f"{raw['name']}: a declared fixture must finish")
            if plain["best_span"] is None or exact["best_span"] is None:
                raise AssertionError(f"{raw['name']}: an optimum without a span")
            ensure(exact["best_span"] >= plain["best_span"],
                   f"{raw['name']}: restricting the legal bases lowered the optimum")
            ensure(exact["replay_status"] == "verified"
                   and plain["replay_status"] == "verified",
                   f"{raw['name']}: both optima owe an independent replay")
    costs = {raw["name"]: max(row["representability_span_cost"] or 0
                              for row in representability.compare_case(raw)["arenas"])
             for raw in representability.families()}
    ensure(costs["repr-threshold-pin"] > 0 and costs["repr-coarse-granule"] > 0,
           f"the two fixtures whose bases move must show a cost to pay for: {costs}")
    ensure(costs["repr-already-quantized"] == 0 and costs["repr-length-only"] == 0
           and costs["repr-bound-is-loose"] == 0,
           f"a fixture no base of which moves must pay nothing: {costs}")


def _q5_regions_agree_and_an_empty_export_refuses() -> None:
    agreement = representability.q5_agreement(ROOT)
    ensure(not agreement["findings"],
           f"the layer and the plan's own port disagree: {agreement['findings']}")
    ensure(agreement["regions"], "the cross-check must decide about actual regions")
    ensure(any(row["granule"] > 1 for row in agreement["regions"]),
           "a cross-check over one-byte granules alone would decide nothing")
    plan = memplan.plan_of(memplan.read(ROOT), memplan.STANDING)
    # Agreement over an exported plan every verdict of which is True would read the
    # same way if neither predicate ever refused, so the counts the plan declares are
    # mutated until the two sides answer differently and the finding is required.
    bases = dataclasses.replace(plan, base_granules=tuple(
        plan.base_granules_of(region) + 1 for region in plan.regions()))
    lengths = dataclasses.replace(plan, length_granules=tuple(
        plan.length_granules_of(region) + 1 for region in plan.regions()))
    for word, mutant in (("base_is_quantized", bases),
                         ("length_is_quantized", lengths)):
        with patch.object(memplan, "plan_of", return_value=mutant):
            disagreed = representability.q5_agreement(ROOT)
        ensure(len(disagreed["findings"]) == len(disagreed["regions"]),
               f"{word}: every region of the mutant must be reported: {disagreed}")
        ensure(all(word in finding for finding in disagreed["findings"]),
               f"{word}: the finding must name the predicate that moved: {disagreed}")
        ensure(all(f"region {row['region']}:" in finding
                   for row, finding in zip(disagreed["regions"],
                                           disagreed["findings"], strict=True)),
               f"{word}: each finding must name its own region: {disagreed}")
    empty = dataclasses.replace(plan, region_count=0)
    with patch.object(memplan, "plan_of", return_value=empty):
        try:
            representability.q5_agreement(ROOT)
        except memory.CaseError:
            pass
        else:
            raise AssertionError("an export with no region must refuse, not agree")
    short = dataclasses.replace(plan, region_count=1, lengths=(0,))
    with patch.object(memplan, "plan_of", return_value=short):
        try:
            representability.q5_agreement(ROOT)
        except memory.CaseError:
            return
    raise AssertionError("a region with no positive length must refuse")


def _report_replays_and_checks_its_own_bound() -> None:
    receipt = representability.report(ROOT, "test-revision")
    ensure(not receipt["errors"], f"representability replay failed: {receipt['errors']}")
    ensure(receipt == representability.report(ROOT, "test-revision"),
           "the representability report must reproduce")
    rows = [row for item in receipt["reproducible"]["cases"] for row in item["arenas"]]
    ensure(bool(rows), "the report must decide about actual arenas")
    for row in rows:
        for side in ("alignment_only", "representable"):
            span = row[side]["best_span"]
            if row[side]["status"] == "optimal" and span is not None:
                ensure(row[side]["stacked_lower_bound"] <= span,
                       f"{row['arena']}: {side} bound exceeds an exhaustive optimum")
    corpus_rows = [row for item in receipt["reproducible"]["cases"]
                   if item["contract"]["name"] in
                   {case["name"] for case in witnesses.corpus("fixture")}
                   for row in item["arenas"]]
    ensure(bool(corpus_rows) and all(row["representability_span_cost"] == 0
                                     and not row["exact_length_refusals"]
                                     for row in corpus_rows),
           "every corpus extent is below the threshold, so the layer costs nothing there")


def _bound_reaches_past_the_charged_load() -> None:
    """The declared corpus carries an instance the charged load alone cannot decide."""
    raw = next(case for case in witnesses.corpus("fixture")
               if case["name"] == "adversarial-alignment")
    case = memory.parse_case(raw)
    load = memory.peak_load(case, "arena")
    bound = representability.arena_lower_bound(case, "arena", representable=True)
    found = memory.solve_exact(case, legal_base=representability.base_refusal)
    ensure(bound > load, "aligned bases must raise the bound above the charged load")
    ensure(bound == found["arenas"][0]["best_span"],
           f"the bound must meet the exhaustive optimum here: {bound}")


def _stacked_bound_declines_a_set_it_cannot_walk() -> None:
    live: Sequence[memory.Object] = tuple(
        representability.probe(str(index), 1)
        for index in range(representability.MAX_STACKED_OBJECTS + 1))
    ensure(representability.stacked_bound(live, representable=True) is None,
           "an oversized live set must decline rather than enumerate")
    ensure(representability.stacked_bound((), representable=True) == 0,
           "an empty live set reaches zero")


def cases() -> list[Case]:
    return [
        Case("repr granule is the plan's and a mutant refuses",
             _granule_comes_from_the_plan_and_a_mutant_refuses),
        Case("repr exact-length refusals report rather than round",
             _exact_length_refusals_report_rather_than_round),
        Case("repr stacked bound sound against an independent grid",
             _stacked_bound_is_sound_against_an_independent_grid),
        Case("repr bound is strictly loose on a declared instance",
             _bound_is_strictly_loose_on_a_declared_instance),
        Case("repr quantized lengths are reported beside the base model",
             _quantized_lengths_are_reported_beside_the_base_model),
        Case("repr default and permissive layers leave the oracle alone",
             _default_and_permissive_layers_leave_the_oracle_alone),
        Case("repr first fit walks to a legal base",
             _first_fit_walks_to_a_legal_base),
        Case("repr every witness survives a refusing layer",
             _every_witness_survives_a_refusing_layer),
        Case("repr restriction never lowers an optimum",
             _restriction_never_lowers_an_optimum),
        Case("repr Q5 regions agree and an empty export refuses",
             _q5_regions_agree_and_an_empty_export_refuses),
        Case("repr report replays and checks its own bound",
             _report_replays_and_checks_its_own_bound),
        Case("repr bound reaches past the charged load",
             _bound_reaches_past_the_charged_load),
        Case("repr stacked bound declines a set it cannot walk",
             _stacked_bound_declines_a_set_it_cannot_walk),
    ]
