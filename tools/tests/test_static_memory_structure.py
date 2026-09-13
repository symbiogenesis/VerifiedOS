# SPDX-License-Identifier: Apache-2.0
"""Independent finite tests of the scoped laminar construction and deletion bound."""

import itertools
import random
from dataclasses import replace
from typing import Any

from tests.harness import Case, ensure
from vos import static_memory as memory
from vos import static_memory_structure as structure


def _case(intervals: tuple[tuple[int, int], ...],
          sizes: tuple[int, ...]) -> memory.Case:
    objects = tuple(memory.Object(str(i), "a", size, size, 1, start, end, end, end,
                                  end, 0)
                    for i, ((start, end), size) in enumerate(zip(intervals, sizes, strict=True)))
    return memory.Case("test", "private finite fixture", "one trace",
                       (memory.Arena("a", "owner", max(1, sum(sizes))),), objects)


def _is_laminar(intervals: tuple[tuple[int, int], ...]) -> bool:
    # Crossing is the strict interlacing endpoint order; equal endpoints nest.
    return not any(a < c < b < d or c < a < d < b
                   for (a, b), (c, d) in itertools.combinations(intervals, 2))


def _random_family(rng: random.Random, objects: int, horizon: int,
                   max_size: int) -> memory.Case:
    intervals: list[tuple[int, int]] = []
    for _ in range(objects):
        start = rng.randint(0, horizon - 1)
        intervals.append((start, rng.randint(start + 1, horizon)))
    sizes = tuple(rng.randint(1, max_size) for _ in range(objects))
    return _case(tuple(intervals), sizes)


def _byte_oracle(case: memory.Case, placement: list[dict[str, Any]],
                 horizon: int) -> tuple[bool, int, int]:
    # Legality, peak load and span by a cell-at-a-time replay that shares no code with
    # the module's checker or load computation.
    by_id: dict[str, int] = {row["id"]: row["base"] for row in placement}
    legal, peak = True, 0
    for tick in range(horizon):
        used: set[int] = set()
        load = 0
        for obj in case.objects:
            if obj.start <= tick < obj.reuse:
                cells = set(range(by_id[obj.id], by_id[obj.id] + obj.size))
                legal = legal and not used & cells
                used.update(cells)
                load += obj.size
        peak = max(peak, load)
    span = max((by_id[o.id] + o.size for o in case.objects), default=0)
    return legal, peak, span


def _finite_constructor() -> None:
    domain = tuple(itertools.combinations(range(4), 2))
    accepted = refused = 0
    for intervals in itertools.product(domain, repeat=3):
        for sizes in itertools.product((1, 2), repeat=3):
            case = _case(intervals, sizes)
            try:
                placement = structure.laminar_placement(case)
            except memory.CaseError:
                ensure(not _is_laminar(intervals), "constructor refused a laminar family")
                refused += 1
                continue
            ensure(_is_laminar(intervals), "constructor accepted crossing reservations")
            legal, peak, span = _byte_oracle(case, placement, 4)
            ensure(legal, "byte oracle found overlapping live slots")
            ensure(span == peak, "independent live-byte bound differs from span")
            accepted += 1
    ensure(accepted > 0 and refused > 0, "finite corpus must exercise both outcomes")


def _deletion_minimality_and_cutoff() -> None:
    domain = tuple(itertools.combinations(range(4), 2))
    for intervals in itertools.product(domain, repeat=3):
        case = _case(intervals, (1, 1, 1))
        receipt = structure.deletion_witness(case)
        minimum = min(len(intervals) - len(retained)
                      for count in range(4)
                      for retained in itertools.combinations(range(3), count)
                      if _is_laminar(tuple(intervals[i] for i in retained)))
        ensure(receipt["minimum"] == minimum, "deletion minimum differs from retained-set oracle")
        kept = tuple(interval for i, interval in enumerate(intervals)
                     if str(i) not in receipt["removed"])
        ensure(_is_laminar(kept), "deletion witness leaves a crossing")
        short = structure.deletion_witness(case, max_subsets=1)
        if minimum:
            ensure(short["status"] == "incomplete" and short["minimum"] is None,
                   "cutoff must never become an optimum")
            ensure(short["proven_lower_bound"] <= minimum, "cutoff lower bound unsound")
    for invalid in (0, -1, True):
        try:
            structure.deletion_witness(_case((), ()), invalid)
        except memory.CaseError:
            continue
        raise AssertionError("invalid subset budget accepted")


def _deletion_dynamic_programme() -> None:
    domain = tuple(itertools.combinations(range(4), 2))
    for intervals in itertools.product(domain, repeat=3):
        case = _case(intervals, (1, 2, 1))
        result = structure.maximum_laminar_subfamily(case)
        minimum = min(len(intervals) - len(retained)
                      for count in range(4)
                      for retained in itertools.combinations(range(3), count)
                      if _is_laminar(tuple(intervals[i] for i in retained)))
        ensure(result["minimum"] == minimum, "dynamic programme differs from retained-set oracle")
        kept = tuple(intervals[int(i)] for i in result["kept"])
        ensure(_is_laminar(kept), "dynamic programme kept a crossing pair")
        ensure(sorted(result["kept"] + result["removed"]) == [str(i) for i in range(3)],
               "kept and removed must partition the family")
    rng = random.Random(20260912)  # noqa: S311 - deterministic finite sampling
    for _ in range(300):
        case = _random_family(rng, rng.randint(0, 8), 8, 3)
        enumerated = structure.deletion_witness(case, max_subsets=1000)
        result = structure.maximum_laminar_subfamily(case)
        ensure(enumerated["minimum"] == result["minimum"],
               "dynamic programme differs from subset enumeration")
        ensure(result["distinct_coordinates"]
               == len({c for o in case.objects for c in (o.start, o.reuse)}),
               "coordinate count must be the number of distinct endpoints")
        reversed_case = replace(case, objects=tuple(reversed(case.objects)))
        ensure(structure.maximum_laminar_subfamily(reversed_case) == result,
               "input order must not change the dynamic programme's answer")
    equal = structure.maximum_laminar_subfamily(_case(((0, 5),) * 3, (1, 2, 3)))
    ensure(equal["minimum"] == 0 and equal["kept"] == ["0", "1", "2"],
           "equal intervals nest and are never deleted")
    adjacent = structure.maximum_laminar_subfamily(_case(((0, 2), (2, 3), (1, 2)), (1, 1, 1)))
    ensure(adjacent["minimum"] == 0, "adjacent and nested endpoints are laminar")
    ensure(structure.maximum_laminar_subfamily(_case((), ()))["minimum"] == 0,
           "the empty family needs no deletion")


def _cycle_crosses(case: memory.Case, cycle: list[str]) -> bool:
    pairs = set(structure.crossing_pairs(case))
    return all((min(a, b), max(a, b)) in pairs
               for a, b in zip(cycle, cycle[1:] + cycle[:1], strict=True))


def _two_stack_theorem() -> None:
    rng = random.Random(912)  # noqa: S311 - deterministic finite sampling
    bipartite = odd = 0
    for _ in range(400):
        case = _random_family(rng, rng.randint(1, 7), 7, 3)
        colouring = structure.two_colouring(case)
        minimum = structure.maximum_laminar_subfamily(case)["minimum"]
        if colouring["bipartite"]:
            bipartite += 1
            placement = structure.two_stack_placement(case, colouring["lower"], colouring["upper"])
            legal, peak, span = _byte_oracle(case, placement, 7)
            ensure(legal, "byte oracle found overlapping live slots in the two-stack placement")
            oracle = memory.solve_exact(case, work_budget=200_000)
            ensure(oracle["status"] == "optimal", "small bipartite families must complete in the oracle")
            ensure(span == peak == oracle["arenas"][0]["best_span"],
                   "two laminar stacks must attain the charged load, which is the optimum")
            continue
        odd += 1
        ensure(minimum >= 2, "one deletion always leaves a bipartite crossing graph")
        cycle = colouring["odd_cycle"]
        ensure(len(cycle) % 2 == 1 and len(cycle) >= 3 and len(set(cycle)) == len(cycle),
               "a non-bipartite certificate is a simple odd cycle")
        ensure(_cycle_crosses(case, cycle), "odd cycle edges must be crossing pairs")
    ensure(bipartite > 0 and odd > 0, "random families must exercise both outcomes")
    crossing = _case(((0, 2), (1, 3), (0, 1)), (1, 2, 1))
    for lower, upper in ((["0", "1"], ["2"]), (["0"], ["1"]), (["0", "2"], ["1", "2"])):
        try:
            structure.two_stack_placement(crossing, lower, upper)
        except memory.CaseError:
            continue
        raise AssertionError("a crossing half or a non-partition was accepted")
    narrow = replace(crossing, arenas=(replace(crossing.arenas[0], capacity=2),))
    try:
        structure.two_stack_placement(narrow, ["0", "2"], ["1"])
    except memory.CaseError:
        pass
    else:
        raise AssertionError("insufficient capacity was accepted")


def _justified_exact() -> None:
    rng = random.Random(1973)  # noqa: S311 - deterministic finite sampling
    searched = 0
    for _ in range(150):
        case = _random_family(rng, rng.randint(0, 6), 6, 3)
        result = structure.justified_exact(case)
        oracle = memory.solve_exact(case, work_budget=200_000)
        ensure(result["status"] == "optimal" and oracle["status"] == "optimal",
               "small families must complete in both searches")
        ensure(result["span"] == oracle["arenas"][0]["best_span"],
               "justified search differs from the address-enumerating oracle")
        ensure(not memory.check_placement(case, result["placement"]), "justified witness refused")
        if result["crossing_graph"]["bipartite"]:
            ensure(result["method"] == "two-laminar-stacks" and result["nodes"] == 0,
                   "a bipartite crossing graph needs no search")
        else:
            searched += 1
            ensure(result["infeasible_through"] == result["span"] - 1,
                   "a completed search certifies exactly the height below its span")
    ensure(searched > 0, "random families must reach the justified search")
    witness = _case(((0, 2), (0, 3), (1, 4), (2, 5), (4, 6)), (1, 1, 1, 1, 2))
    cut = structure.justified_exact(witness, work_budget=1)
    ensure(cut["status"] == "incomplete" and cut["method"] is None
           and cut["proven_lower_bound"] == 3 and cut["span"] == 4,
           "a cutoff keeps the proved bounds and claims no optimum")
    ensure(not memory.check_placement(witness, cut["placement"]),
           "the retained upper-bound placement must be legal")
    full = structure.justified_exact(witness)
    ensure(full["status"] == "optimal" and full["span"] == 3 and full["nodes"] > 0,
           "the canonical-remainder witness is solved by search at its load")
    reversed_case = replace(witness, objects=tuple(reversed(witness.objects)))
    ensure(structure.justified_exact(reversed_case)["placement"] == full["placement"],
           "identity order must fix the justified witness")
    tight = replace(witness, arenas=(replace(witness.arenas[0], capacity=3),))
    ensure(structure.justified_exact(tight)["status"] == "optimal",
           "a capacity below the trivial bound forces a search at the capacity")
    narrow = replace(witness, arenas=(replace(witness.arenas[0], capacity=2),))
    ensure(structure.justified_exact(narrow)["status"] == "infeasible",
           "a capacity below the charged load is infeasible")
    huge = 1 << 1024
    triangle = _case(((0, 3), (1, 4), (2, 5)), (huge, huge + 1, huge + 2))
    result = structure.justified_exact(triangle)
    ensure(result["status"] == "optimal" and result["span"] == 3 * huge + 3
           and not result["crossing_graph"]["bipartite"],
           "binary magnitudes must not require address enumeration")
    for invalid in (replace(triangle, objects=(replace(triangle.objects[0], alignment=2),)),
                    replace(triangle, arenas=(triangle.arenas[0], memory.Arena("b", "p", 1)))):
        try:
            structure.justified_exact(invalid)
        except memory.CaseError:
            continue
        raise AssertionError("unsupported premise accepted by the justified search")
    try:
        structure.justified_exact(triangle, work_budget=0)
    except memory.CaseError:
        pass
    else:
        raise AssertionError("invalid work budget accepted")


def _decompositions() -> None:
    receipt = structure.report("test-revision")
    ensure(not receipt["errors"], "structural witness replay failed")
    verdicts = {row["name"]: row["refuted"] for row in receipt["decompositions"]}
    ensure(verdicts == {c["name"]: True for c in structure.CONTRACTS},
           "every declared contract must be refuted by its witness")
    cases = {row["contract"]["name"]: row for row in receipt["cases"]}
    canonical = cases["canonical-remainder-witness"]["refutations"]
    ensure(canonical["minimum"] == 2 and [c["removed"] for c in canonical["covers"]] == [["d1", "d2"]],
           "the canonical witness has one minimum deletion set of two crossing objects")
    ensure(not cases["canonical-remainder-witness"]["crossing_graph"]["bipartite"],
           "the canonical witness lies outside the two-stack theorem")
    crossing = memory.parse_case(cases["crossing"]["contract"])
    ensure(structure.canonical_remainder_extends(crossing, ("a",), 2)
           and not structure.canonical_remainder_extends(crossing, ("a",), 1),
           "a single deleted object extends the canonical remainder at the load")
    sweep = receipt["sweep"]
    first = {name: (row["objects"] if row else None)
             for name, row in sweep["first_refutation"].items()}
    ensure(sweep["status"] == "complete" and not sweep["span_above_load"],
           "the default sweep completes and finds no span above load")
    ensure(first == {"bottom-block": 3, "signature": 3, "band": None, "canonical-remainder": None},
           "three objects refute exactly the bottom-block and signature contracts")
    sample = receipt["sample"]
    ensure(sample["status"] == "complete" and sample["incomplete_searches"] == 0
           and not sample["span_above_load"]
           and sample["attained_load"] == sample["domain"]["families"],
           "the shipped sample decides every family and finds none above its load")
    ensure(sample["non_bipartite"] > 0
           and any(int(k) >= 2 for k in sample["by_minimum_deletions"]),
           "the sample must reach non-bipartite families with deletion number at least two")
    ensure(len(list(structure.interval_shapes(2, 3))) == 3, "two-interval shapes over four coordinates")
    for shape in structure.interval_shapes(3, 4):
        ensure({c for s, e in shape for c in (s, e)} == set(range(5)), "a shape uses every coordinate")
    try:
        structure.decomposition_sweep(0, 1)
    except memory.CaseError:
        pass
    else:
        raise AssertionError("an empty sweep domain was accepted")


def _load_attainment_sample() -> None:
    small = structure.load_attainment_sample(seed=2, families=40, objects=(4, 7),
                                             horizon=6, max_weight=2)
    ensure(small == structure.load_attainment_sample(seed=2, families=40, objects=(4, 7),
                                                     horizon=6, max_weight=2),
           "the sample must reproduce from its seed")
    ensure(small["domain"] == {"seed": 2, "families": 40, "min_objects": 4, "max_objects": 7,
                               "horizon": 6, "max_weight": 2,
                               "work_budget": structure.JUSTIFIED_WORK_BUDGET},
           "the sample receipt states its whole domain")
    ensure(small["attained_load"] + small["incomplete_searches"] + len(small["span_above_load"])
           == 40 == sum(small["by_minimum_deletions"].values()),
           "every sampled family is tallied exactly once")
    ensure(small["non_bipartite"] > 0 and small["status"] == "complete",
           "the small sample must reach the justified search and complete it")
    ensure(small != structure.load_attainment_sample(seed=3, families=40, objects=(4, 7),
                                                     horizon=6, max_weight=2),
           "a different seed draws a different sample")
    cut = structure.load_attainment_sample(seed=2, families=40, objects=(4, 7),
                                           horizon=6, max_weight=2, work_budget=1)
    ensure(cut["status"] == "incomplete" and cut["incomplete_searches"] > 0
           and not cut["span_above_load"]
           and cut["attained_load"] + cut["incomplete_searches"] == 40,
           "a cutoff is tallied as undecided and never as a span above load")
    ensure(cut["by_minimum_deletions"] == small["by_minimum_deletions"],
           "the budget must not change the deletion numbers drawn")
    for seed, families, objects, horizon, weight in (
            (True, 4, (2, 3), 4, 2), (7, 0, (2, 3), 4, 2), (7, True, (2, 3), 4, 2),
            (7, 4, (0, 3), 4, 2), (7, 4, (4, 3), 4, 2), (7, 4, (2, 3), 0, 2), (7, 4, (2, 3), 4, 0)):
        try:
            structure.load_attainment_sample(seed, families, objects, horizon, weight)
        except memory.CaseError:
            continue
        raise AssertionError("invalid sample argument accepted")


def _four_object_sweep() -> None:
    sweep = structure.decomposition_sweep(4, 2)
    first = {name: (row["objects"] if row else None)
             for name, row in sweep["first_refutation"].items()}
    ensure(sweep["status"] == "complete" and not sweep["span_above_load"],
           "every four-object shape with weights at most two attains its load")
    ensure(first == {"bottom-block": 3, "signature": 3, "band": 4, "canonical-remainder": None},
           "four objects refute the band contract and not the canonical remainder")
    ensure("3" in sweep["families"][-1]["by_minimum_deletions"],
           "four mutually crossing intervals reach deletion number three")


def _premises_and_binary_scale() -> None:
    huge = 1 << 1024
    case = _case(((0, huge), (1, 2), (2, 3)), (huge, huge + 1, huge + 2))
    placement = structure.laminar_placement(case)
    ensure(memory.placement_spans(case, placement)["a"] == 2 * huge + 2,
           "binary magnitudes must not require address enumeration")
    variants = [replace(case, arenas=(case.arenas[0], memory.Arena("b", "peer", 1))),
                replace(case, objects=(replace(case.objects[0], alignment=2),)),
                replace(case, arenas=(replace(case.arenas[0], capacity=1),))]
    for mutant in variants:
        try:
            structure.laminar_placement(mutant)
        except memory.CaseError:
            continue
        raise AssertionError("unsupported theorem premise or insufficient capacity accepted")
    ensure(structure.laminar_placement(_case((), ())) == [], "empty family needs zero span")
    changed = replace(case, objects=tuple(reversed(case.objects)))
    ensure(placement == structure.laminar_placement(changed), "identity must fix tie order")


def _report() -> None:
    receipt: dict[str, Any] = structure.report("test-revision")
    ensure(not receipt["errors"], "structural witness replay failed")
    ensure(receipt == structure.report("test-revision"), "structural report must reproduce")
    gap = next(row for row in receipt["cases"]
               if row["contract"]["name"] == "alignment-breaks-equality")
    ensure(gap["exact"]["arenas"][0]["best_span_over_load"] == 1,
           "equal lifetimes with constrained bases must retain the negative result")
    for row in receipt["cases"]:
        ensure({"deletion", "deletion_dp", "crossing_graph", "charged_load_lower_bound",
                "construction"} <= row.keys(), "every case keeps the original receipt fields")
    ensure({"cases", "decompositions", "sweep", "sample", "errors", "open_obligations"}
           <= receipt.keys(), "the report carries the sweep and the sample beside the cases")


def cases() -> list[Case]:
    return [
        Case("structure laminar finite byte oracle", _finite_constructor),
        Case("structure deletion independent minimum and cutoff", _deletion_minimality_and_cutoff),
        Case("structure deletion number dynamic programme", _deletion_dynamic_programme),
        Case("structure two-stack theorem and odd cycles", _two_stack_theorem),
        Case("structure justified exact search", _justified_exact),
        Case("structure decomposition witnesses and sweep", _decompositions),
        Case("structure seeded load-attainment sample", _load_attainment_sample),
        Case("structure exhaustive four-object sweep", _four_object_sweep, slow=True),
        Case("structure premises and binary magnitude", _premises_and_binary_scale),
        Case("structure replayable scoped report", _report),
    ]
