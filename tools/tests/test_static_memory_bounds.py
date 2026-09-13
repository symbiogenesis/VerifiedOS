# SPDX-License-Identifier: Apache-2.0
"""Every span bound against bounded exact search, its own budget and its invariance."""

import itertools
import random
from dataclasses import replace

from tests.harness import Case, ensure
from vos import static_memory as memory
from vos import static_memory_bounds as bounds

type Row = tuple[str, int, int, int, int]
type Item = tuple[int, int]


def _case(rows: list[Row]) -> memory.Case:
    """A private fixture whose standing plan packs each arena in supplied order."""
    cursors: dict[str, int] = {}
    objects: list[memory.Object] = []
    for index, (arena, size, alignment, start, end) in enumerate(rows):
        base = bounds.align_up(cursors.get(arena, 0), alignment)
        cursors[arena] = base + size
        objects.append(memory.Object(f"o{index:03d}", arena, size, size, alignment,
                                     start, end, end, end, end, base))
    arenas = tuple(memory.Arena(name, f"owner-{name}", cursors[name])
                   for name in sorted(cursors))
    return memory.Case("generated", "private finite fixture", "one declared trace",
                       arenas, tuple(objects))


def _random_case(rng: random.Random, count: int, arenas: int = 1) -> memory.Case:
    rows: list[Row] = []
    for _ in range(count):
        start = rng.randrange(5)
        rows.append((f"a{rng.randrange(arenas)}", rng.randrange(1, 7),
                     rng.choice((1, 2, 4, 8)), start, start + rng.randrange(1, 5)))
    return _case(rows)


def _stacked(items: tuple[Item, ...]) -> int:
    """Independent reference: stack these extents in the supplied order."""
    end = 0
    for size, alignment in items:
        end = ((end + alignment - 1) // alignment) * alignment + size
    return end


def _enumerated_orders(items: tuple[Item, ...]) -> int:
    """Independent reference: the least span over every order of one live set."""
    return min((_stacked(order) for order in itertools.permutations(items)), default=0)


def _searched_pairs(items: tuple[Item, ...], membership: tuple[str, ...]) -> int:
    """Independent reference: least span over aligned bases, by exhaustive search."""
    ceiling = _stacked(items)
    best = ceiling
    for based in itertools.product(*[range(0, ceiling, align) for _, align in items]):
        legal = True
        for left, right in itertools.combinations(range(len(items)), 2):
            if {membership[left], membership[right]} == {"first", "second"}:
                continue
            low, high = based[left], based[right]
            if low < high + items[right][0] and high < low + items[left][0]:
                legal = False
                break
        if legal:
            best = min(best, max(base + items[i][0] for i, base in enumerate(based)))
    return best


def _bounds_never_exceed_exact_optima() -> None:
    rng = random.Random(9122026)  # noqa: S311 - deterministic synthetic tests
    searched = replayed = 0
    for trial in range(240):
        case = _random_case(rng, rng.randrange(2, 7), 1 + trial % 2)
        exact = memory.solve_exact(case, 200_000)
        if exact["status"] != "optimal":
            continue
        searched += 1
        optima = {row["arena"]: row["best_span"] for row in exact["arenas"]}
        for row in bounds.case_bounds(case):
            optimum = optima[row["arena"]]
            for entry in row["bounds"]:
                ensure(entry["value"] is None or entry["value"] <= optimum,
                       f"trial {trial}: {entry} exceeds exact optimum {optimum}")
            ensure(row["charged_load"] <= row["proven_lower_bound"] <= optimum,
                   f"trial {trial}: bound ordering broken against {optimum}")
        if len(case.objects) <= 3:
            replay = memory.verify_optimality(case, exact, 200_000)
            replayed += replay["status"] == "verified"
    ensure(searched > 100 and replayed > 0,
           f"the sample must exercise search and replay: {searched}, {replayed}")


def _exact_live_set_matches_order_enumeration() -> None:
    rng = random.Random(41)  # noqa: S311 - deterministic synthetic tests
    for _ in range(400):
        items = tuple((rng.randrange(1, 9), rng.choice((1, 2, 4, 8)))
                      for _ in range(rng.randrange(1, 6)))
        value = bounds.pack_span(items, ("both",) * len(items), bounds.Work(1_000_000))
        ensure(value == _enumerated_orders(items),
               f"live-set enumeration disagrees on {items}: {value}")
    ensure(bounds.pack_span((), (), bounds.Work(10)) == 0, "an empty live set needs no span")


def _two_instant_matches_independent_search() -> None:
    rng = random.Random(2026)  # noqa: S311 - deterministic synthetic tests
    strict = compared = 0
    for _ in range(600):
        count = rng.randrange(2, 5)
        items = tuple((rng.randrange(1, 6), rng.choice((1, 2, 4, 8)))
                      for _ in range(count))
        membership = tuple(bounds.MEMBERSHIP[rng.randrange(3)] for _ in range(count))
        if "first" not in membership or "second" not in membership:
            continue
        compared += 1
        value = bounds.pack_span(items, membership, bounds.Work(1_000_000))
        ensure(value == _searched_pairs(items, membership),
               f"two-instant enumeration disagrees on {items}, {membership}: {value}")
        singles = [_enumerated_orders(tuple(item for item, kind in zip(items, membership,
                                                                      strict=True)
                                            if kind != other))
                   for other in ("second", "first")]
        ensure(value is not None and value >= max(singles),
               "the two-instant relaxation must not fall below one instant")
        strict += value is not None and value > max(singles)
    ensure(compared > 200 and strict > 0,
           f"the pair bound must decide somewhere: {compared}, {strict}")


def _block_bound_holds_where_enumeration_cannot() -> None:
    rng = random.Random(8)  # noqa: S311 - deterministic synthetic tests
    for _ in range(200):
        rows: list[Row] = [("a0", rng.randrange(1, 12), rng.choice((1, 2, 4, 8)), 0, 2)
                           for _ in range(rng.randrange(13, 21))]
        case = _case(rows)
        live = bounds.live_objects(case, "a0", 0)
        items = tuple((obj.size, obj.alignment) for obj in live)
        value = bounds.block_bound(live)
        ensure(sum(size for size, _ in items) <= value <= _stacked(items),
               f"block bound outside load and an achievable span: {value}")
        row = bounds.arena_bounds(case, "a0")
        ensure(row["bounds"][2]["status"] == "over-budget",
               "a live set beyond the enumeration limit must withhold the exact bound")
        ensure(row["proven_lower_bound"] == value,
               "the block bound must reach the report when enumeration cannot")


def _budget_and_settings_refuse_rather_than_guess() -> None:
    case = _case([("a0", 1, 8, 0, 2), ("a0", 3, 4, 0, 4), ("a0", 2, 8, 0, 2),
                  ("a0", 5, 2, 3, 4)])
    full = bounds.arena_bounds(case, "a0")
    ensure(full["proven_lower_bound"] > full["charged_load"]
           and full["proven_lower_bound_source"] != bounds.BOUNDS[0],
           f"the fixture must be decided by a bound beyond the load: {full}")
    starved = bounds.arena_bounds(case, "a0", 0)
    ensure(starved["proven_lower_bound"] == starved["charged_load"]
           and starved["proven_lower_bound_source"] == bounds.BOUNDS[0],
           "an exhausted budget must leave the charged load standing alone")
    ensure(all(entry["value"] is None for entry in starved["bounds"][1:]),
           f"an exhausted budget must claim no value: {starved['bounds']}")
    ensure(all(entry["status"] == "over-budget" for entry in starved["bounds"][1:]),
           f"an exhausted budget must say so: {starved['bounds']}")
    for arena, budget in (("a0", -1), ("a0", True), ("missing", 10)):
        try:
            bounds.arena_bounds(case, arena, budget)
        except memory.CaseError:
            continue
        raise AssertionError(f"invalid bound setting accepted: {arena}, {budget}")
    for labels in ((), ("both", "unknown")):
        try:
            bounds.pack_span(((1, 1), (2, 2)), labels, bounds.Work(10))
        except memory.CaseError:
            continue
        raise AssertionError(f"invalid membership accepted: {labels}")
    empty = replace(case, arenas=(*case.arenas, memory.Arena("a1", "peer", 4)))
    spare = next(row for row in bounds.case_bounds(empty) if row["arena"] == "a1")
    ensure(spare["proven_lower_bound"] == 0
           and all(entry["status"] != "unattained-by-any-live-set"
                   for entry in spare["bounds"]),
           f"an arena charging nothing needs no span and reports no finding: {spare}")
    for alignment in (0, -4):
        try:
            bounds.align_up(3, alignment)
        except memory.CaseError:
            continue
        raise AssertionError("non-positive alignment accepted")


def _identical_under_permutation() -> None:
    rng = random.Random(777)  # noqa: S311 - deterministic synthetic tests
    for _ in range(60):
        case = _random_case(rng, rng.randrange(4, 10), 2)
        shuffled = list(case.objects)
        rng.shuffle(shuffled)
        other = replace(case, objects=tuple(shuffled))
        ensure(bounds.case_bounds(case) == bounds.case_bounds(other),
               "bounds must not depend on the order objects are supplied in")


def cases() -> list[Case]:
    return [
        Case("bounds never exceed exact optima", _bounds_never_exceed_exact_optima),
        Case("live-set bound matches order enumeration", _exact_live_set_matches_order_enumeration),
        Case("two-instant bound matches independent search", _two_instant_matches_independent_search),
        Case("block bound holds beyond enumeration", _block_bound_holds_where_enumeration_cannot),
        Case("budget and settings refuse rather than guess", _budget_and_settings_refuse_rather_than_guess),
        Case("bounds identical under permutation", _identical_under_permutation),
    ]
