# SPDX-License-Identifier: Apache-2.0
"""Search-free lower bounds on the minimal span of a legal static-memory placement.

Computes four sound lower bounds per arena by restricting the placement problem to
subsets of objects and instants:
- `charged-load`: peak simultaneous byte load at a single instant.
- `alignment-block`: alignment-block padding accounting for a single instant of any size.
- `alignment-clique`: exact subset-DP span over a single small instant (`<= MAX_CLIQUE_OBJECTS`).
- `two-instant`: exact Pareto-front subset-DP span over pairs of instants (`<= MAX_UNION_OBJECTS`).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, TypedDict

from vos import static_memory as memory

BOUNDS: tuple[str, ...] = ("charged-load", "alignment-block", "alignment-clique",
                           "two-instant")
MEMBERSHIP: tuple[str, ...] = ("both", "first", "second")
STATUSES: tuple[str, ...] = ("computed", "partial", "over-budget", "over-limit",
                             "dominated-by-single-instant", "no-live-set",
                             "no-instant-pair", "unattained-by-any-live-set")
DEFAULT_WORK_BUDGET = 50_000
MAX_CLIQUE_OBJECTS = 12
MAX_UNION_OBJECTS = 12

type Item = tuple[int, int]


class Coverage(TypedDict):
    """Domain coverage counts for one bound scan (`scored`, `pruned`, `over_limit`, `over_budget`)."""

    scored: int
    pruned: int
    over_limit: int
    over_budget: int


class BoundRow(TypedDict):
    """Result, completion status, domain coverage, and witness for one lower bound."""

    bound: str
    value: int | None
    status: str
    complete: bool
    coverage: Coverage
    witness: dict[str, Any]


class ArenaBounds(TypedDict):
    """All computed lower bounds for one arena and the strongest proven bound."""

    arena: str
    charged_load: int
    proven_lower_bound: int
    proven_lower_bound_source: str
    proven_lower_bound_complete: bool
    scans_complete: bool
    bounds: list[BoundRow]
    work: dict[str, int]


@dataclass
class Work:
    """Deterministic work counter bounded by `limit`."""

    limit: int
    spent: int = 0

    def step(self) -> bool:
        if self.spent >= self.limit:
            return False
        self.spent += 1
        return True

    def affordable(self, cost: int) -> bool:
        return self.limit - self.spent >= cost


def align_up(value: int, alignment: int) -> int:
    """Round `value` up to the nearest multiple of positive `alignment`."""
    if type(alignment) is not int or alignment < 1:
        raise memory.CaseError("alignment must be a positive integer")
    return ((value + alignment - 1) // alignment) * alignment


def sequential_span(items: tuple[Item, ...]) -> int:
    """Return the span of stacking `(size, alignment)` `items` in order."""
    end = 0
    for size, alignment in items:
        end = align_up(end, alignment) + size
    return end


def _record(target: dict[int, int], first_end: int, second_end: int) -> None:
    """Insert `(first_end, second_end)` into `target`, retaining only Pareto-minimal pairs."""
    standing = target.get(first_end)
    if standing is not None and standing <= second_end:
        return
    for other, value in tuple(target.items()):
        if other <= first_end and value <= second_end:
            return
        if first_end <= other and second_end <= value:
            del target[other]
    target[first_end] = second_end


def pack_span(items: tuple[Item, ...], membership: Sequence[str],
              work: Work) -> int | None:
    """Return the exact minimal span for one instant or a two-instant relaxation (`None` on budget exhaustion)."""
    if len(items) != len(membership) or set(membership) - set(MEMBERSHIP):
        raise memory.CaseError(f"membership must label every item one of {MEMBERSHIP}")
    count = len(items)
    if count == 0:
        return 0
    full = (1 << count) - 1
    reached: list[dict[int, int]] = [{} for _ in range(full + 1)]
    reached[0] = {0: 0}
    for mask in range(full):
        fronts = reached[mask]
        if not fronts:
            continue
        for first_end in sorted(fronts):
            second_end = fronts[first_end]
            for index in range(count):
                bit = 1 << index
                if mask & bit:
                    continue
                if not work.step():
                    return None
                size, alignment = items[index]
                kind = membership[index]
                if kind == "both":
                    base = align_up(max(first_end, second_end), alignment)
                    _record(reached[mask | bit], base + size, base + size)
                elif kind == "first":
                    _record(reached[mask | bit], align_up(first_end, alignment) + size,
                            second_end)
                else:
                    _record(reached[mask | bit], first_end,
                            align_up(second_end, alignment) + size)
        reached[mask] = {}
    return min(max(first_end, second_end)
               for first_end, second_end in reached[full].items())


def block_bound(objects: tuple[memory.Object, ...]) -> int:
    """Compute an alignment-block lower bound for a single instant's live set `objects`."""
    load = sum(obj.size for obj in objects)
    strongest = load
    for alignment in sorted({obj.alignment for obj in objects if obj.alignment > 1}):
        grouped = [obj for obj in objects if obj.alignment % alignment == 0]
        if not grouped:
            continue
        blocks = {obj.id: align_up(obj.size, alignment) for obj in grouped}
        pads = {obj.id: blocks[obj.id] - obj.size for obj in grouped}
        owned = sum(blocks.values())
        padding = sum(pads.values())
        widest = max(pads.values())
        fillers = load - sum(obj.size for obj in grouped)
        candidates: list[int] = []
        for top in objects:
            if top.id in blocks:
                below = owned - blocks[top.id]
                unusable = padding - pads[top.id]
                coverable = fillers
            else:
                below = max(0, owned - alignment + 1)
                unusable = padding - widest
                coverable = fillers - top.size
            packed = (load - top.size) + max(0, unusable - coverable)
            candidates.append(max(below, packed) + top.size)
        strongest = max(strongest, min(candidates))
    return strongest


def live_objects(case: memory.Case, arena_id: str,
                 time: int) -> tuple[memory.Object, ...]:
    """Return objects in `arena_id` live at `time`, sorted by `id`."""
    return tuple(sorted((obj for obj in case.objects if obj.arena == arena_id
                         and obj.start <= time < obj.reuse), key=lambda obj: obj.id))


def cliques(case: memory.Case,
            arena_id: str) -> list[tuple[int, tuple[memory.Object, ...]]]:
    """Return one representative `(time, live_objects)` per distinct `(size, alignment)` multiset."""
    if arena_id not in {arena.id for arena in case.arenas}:
        raise memory.CaseError(f"unknown arena {arena_id}")
    seen: set[tuple[Item, ...]] = set()
    result: list[tuple[int, tuple[memory.Object, ...]]] = []
    for time in sorted({obj.start for obj in case.objects if obj.arena == arena_id}):
        live = live_objects(case, arena_id, time)
        signature = tuple(sorted((obj.size, obj.alignment) for obj in live))
        if not live or signature in seen:
            continue
        seen.add(signature)
        result.append((time, live))
    return result


def _items(objects: tuple[memory.Object, ...]) -> tuple[Item, ...]:
    return tuple((obj.size, obj.alignment) for obj in objects)


def _coverage(scored: int = 0, pruned: int = 0, over_limit: int = 0,
              over_budget: int = 0) -> Coverage:
    return {"scored": scored, "pruned": pruned, "over_limit": over_limit,
            "over_budget": over_budget}


def _decide(best: int, coverage: Coverage, empty: str) -> tuple[int | None, str, bool]:
    """Derive `(value, status, complete)` from `best` and `coverage`."""
    complete = not (coverage["over_limit"] or coverage["over_budget"])
    if coverage["scored"]:
        return best, "computed" if complete else "partial", complete
    if coverage["over_budget"]:
        return None, "over-budget", False
    if coverage["over_limit"]:
        return None, "over-limit", False
    if coverage["pruned"]:
        return None, "dominated-by-single-instant", True
    return None, empty, True


def _row(bound: str, value: int | None, status: str, complete: bool,
         coverage: Coverage, witness: dict[str, Any]) -> BoundRow:
    return {"bound": bound, "value": value, "status": status, "complete": complete,
            "coverage": coverage, "witness": witness}


def _load_row(arena_id: str, load: int,
              found: list[tuple[int, tuple[memory.Object, ...]]]) -> BoundRow:
    """Build the `charged-load` row with a witness instant attaining `load`."""
    coverage = _coverage(scored=len(found))
    for time, live in found:
        if sum(obj.size for obj in live) == load:
            return _row(BOUNDS[0], load, "computed", True, coverage,
                        {"instant": time, "objects": [obj.id for obj in live]})
    if not found and load == 0:
        return _row(BOUNDS[0], 0, "computed", True, coverage,
                    {"arena": arena_id, "objects": []})
    return _row(BOUNDS[0], load, "unattained-by-any-live-set", False, coverage,
                {"arena": arena_id, "objects": []})


def _clique_rows(found: list[tuple[int, tuple[memory.Object, ...]]], work: Work,
                 max_clique: int) -> tuple[BoundRow, BoundRow]:
    """Compute `alignment-block` and `alignment-clique` bound rows over `found`."""
    ordered = sorted(found, key=lambda item: (-sum(obj.size for obj in item[1]),
                                              item[0]))
    block = _coverage()
    clique = _coverage()
    block_best = 0
    block_witness: dict[str, Any] = {"objects": []}
    exact_best = 0
    exact_witness: dict[str, Any] = {"objects": []}
    for index, (time, live) in enumerate(ordered):
        if not work.step():
            remaining = len(ordered) - index
            block["over_budget"] += remaining
            clique["over_budget"] += remaining
            break
        block["scored"] += 1
        value = block_bound(live)
        if value > block_best:
            block_best = value
            block_witness = {"instant": time, "objects": [obj.id for obj in live]}
        count = len(live)
        if count > max_clique:
            clique["over_limit"] += 1
            continue
        if not work.affordable(count * (1 << count)):
            clique["over_budget"] += 1
            continue
        span = pack_span(_items(live), (MEMBERSHIP[0],) * count, work)
        if span is None:
            clique["over_budget"] += 1
            continue
        clique["scored"] += 1
        if span > exact_best:
            exact_best = span
            exact_witness = {"instant": time, "objects": [obj.id for obj in live]}
    block_value, block_status, block_done = _decide(block_best, block, "no-live-set")
    exact_value, exact_status, exact_done = _decide(exact_best, clique, "no-live-set")
    return (_row(BOUNDS[1], block_value, block_status, block_done, block, block_witness),
            _row(BOUNDS[2], exact_value, exact_status, exact_done, clique, exact_witness))


def _union(first: tuple[memory.Object, ...],
           second: tuple[memory.Object, ...]) -> tuple[memory.Object, ...]:
    merged = {obj.id: obj for obj in (*first, *second)}
    return tuple(sorted(merged.values(), key=lambda obj: obj.id))


def _pair_row(found: list[tuple[int, tuple[memory.Object, ...]]], work: Work,
              max_union: int, standing: int) -> BoundRow:
    """Compute the `two-instant` relaxation bound row over pairs from `found`."""
    members = dict(found)
    identities = {time: frozenset(obj.id for obj in live) for time, live in found}
    times = sorted(members)
    pairs = [(first, second) for index, first in enumerate(times)
             for second in times[index + 1:]]
    coverage = _coverage()
    candidates: list[tuple[int, int, int]] = []
    for index, (first_time, second_time) in enumerate(pairs):
        if not work.step():
            coverage["over_budget"] += len(pairs) - index
            break
        if len(identities[first_time] | identities[second_time]) > max_union:
            coverage["over_limit"] += 1
            continue
        objects = _union(members[first_time], members[second_time])
        candidates.append((-sum(obj.size for obj in objects),
                           first_time, second_time))
    best = 0
    witness: dict[str, Any] = {"objects": []}
    admitted = sorted(candidates)
    for position, (_, first_time, second_time) in enumerate(admitted):
        objects = _union(members[first_time], members[second_time])
        items = _items(objects)
        if sequential_span(items) <= max(best, standing):
            coverage["pruned"] += 1
            continue
        first_ids, second_ids = identities[first_time], identities[second_time]
        labels = [MEMBERSHIP[0] if obj.id in first_ids and obj.id in second_ids
                  else MEMBERSHIP[1] if obj.id in first_ids else MEMBERSHIP[2]
                  for obj in objects]
        span = pack_span(items, labels, work)
        if span is None:
            coverage["over_budget"] += len(admitted) - position
            break
        coverage["scored"] += 1
        if span > best:
            best = span
            witness = {"instants": [first_time, second_time],
                       "objects": [obj.id for obj in objects]}
    value, status, complete = _decide(best, coverage, "no-instant-pair")
    return _row(BOUNDS[3], value, status, complete, coverage, witness)


def arena_bounds(case: memory.Case, arena_id: str,
                 work_budget: int = DEFAULT_WORK_BUDGET,
                 max_clique: int = MAX_CLIQUE_OBJECTS,
                 max_union: int = MAX_UNION_OBJECTS) -> ArenaBounds:
    """Compute all four lower bounds for `arena_id` and select the strongest proven bound."""
    for setting in (work_budget, max_clique, max_union):
        if type(setting) is not int or setting < 0:
            raise memory.CaseError("bound settings must be nonnegative integers")
    work = Work(work_budget)
    load = memory.peak_load(case, arena_id)
    found = cliques(case, arena_id)
    rows = [_load_row(arena_id, load, found)]
    block_row, clique_row = _clique_rows(found, work, max_clique)
    rows.extend((block_row, clique_row))
    standing = max(value for value in (load, block_row["value"], clique_row["value"])
                   if value is not None)
    rows.append(_pair_row(found, work, max_union, standing))
    proven = load
    source = BOUNDS[0]
    settled = rows[0]["complete"]
    for row in rows:
        value = row["value"]
        if value is not None and value > proven:
            proven = value
            source = row["bound"]
            settled = row["complete"]
    return {"arena": arena_id, "charged_load": load, "proven_lower_bound": proven,
            "proven_lower_bound_source": source,
            "proven_lower_bound_complete": settled,
            "scans_complete": all(row["complete"] for row in rows), "bounds": rows,
            "work": {"budget": work.limit, "spent": work.spent}}


def case_bounds(case: memory.Case, work_budget: int = DEFAULT_WORK_BUDGET,
                max_clique: int = MAX_CLIQUE_OBJECTS,
                max_union: int = MAX_UNION_OBJECTS) -> list[ArenaBounds]:
    """Compute `ArenaBounds` for every arena in `case`."""
    return [arena_bounds(case, arena.id, work_budget, max_clique, max_union)
            for arena in case.arenas]
