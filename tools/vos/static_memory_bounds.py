# SPDX-License-Identifier: Apache-2.0
"""Lower bounds on the minimal span of a legal placement, decided without a search.

Each bound restricts an arbitrary legal placement to a subset of one arena's objects
and to one or two instants. Restriction keeps every constraint the retained objects
already carried and drops the rest, and deleting objects never raises a span, so the
minimum of a restricted problem never exceeds the minimum of the whole arena. The
bounds differ in which restriction they take and in what each can afford: the charged
load of one instant, which the oracle already computes and this module cross-checks;
an alignment block count for an instant of any size; an exact enumeration of orders
for one small instant; and an exact enumeration of the relaxation that keeps two
instants and forgets every other interference.

A bound is evidence about the declared finite integer model alone. It accepts no
requirement and confers no landing credit. It reads no candidate placement and calls
no search, so it can be used to check one; a value that exceeds an exact optimum is a
defect, which is what the tests decide against bounded exact search.

Every row also states how much of its own domain its scan reached. A value drawn from
part of a trace remains a lower bound, being a maximum over the restrictions actually
scored, but it is not the strongest that bound could give, and a row that read like a
finished one would say otherwise.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, TypedDict

from vos import static_memory as memory

BOUNDS: tuple[str, ...] = ("charged-load", "alignment-block", "alignment-clique",
                           "two-instant")
MEMBERSHIP: tuple[str, ...] = ("both", "first", "second")
# A status reports how far a scan got, never whether some value appeared.
STATUSES: tuple[str, ...] = ("computed", "partial", "over-budget", "over-limit",
                             "dominated-by-single-instant", "no-live-set",
                             "no-instant-pair", "unattained-by-any-live-set")
DEFAULT_WORK_BUDGET = 50_000
MAX_CLIQUE_OBJECTS = 12
MAX_UNION_OBJECTS = 12

type Item = tuple[int, int]


class Coverage(TypedDict):
    """How much of one bound's own domain its scan reached, and what it left behind.

    `pruned` counts restrictions proved unable to raise the value already in hand, so
    skipping them costs nothing. `over_limit` and `over_budget` count the ones nothing
    here examined: either of those makes the row partial evidence, because a
    restriction never scored could have carried a larger value.
    """

    scored: int
    pruned: int
    over_limit: int
    over_budget: int


class BoundRow(TypedDict):
    """One bound's value, how far its computation got, and what it read."""

    bound: str
    value: int | None
    status: str
    complete: bool
    coverage: Coverage
    witness: dict[str, Any]


class ArenaBounds(TypedDict):
    """Every bound for one arena, and the strongest of them with its source.

    `proven_lower_bound_complete` says whether the row that supplied the value covered
    its own domain, so whether that value stands at any larger budget.
    `scans_complete` says whether every row did, so whether a stronger value was left
    unexamined at these settings. The first can hold while the second does not.
    """

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
    """Deterministic work limit. Unfinished restrictions supply no bound value."""

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
    """The least multiple of `alignment` at or above `value`; the one rounding here."""
    if type(alignment) is not int or alignment < 1:
        raise memory.CaseError("alignment must be a positive integer")
    return ((value + alignment - 1) // alignment) * alignment


def sequential_span(items: tuple[Item, ...]) -> int:
    """Span of stacking these extents in the given order: an achievable upper bound."""
    end = 0
    for size, alignment in items:
        end = align_up(end, alignment) + size
    return end


def _record(target: dict[int, int], first_end: int, second_end: int) -> None:
    """Keep the Pareto-minimal front pairs only.

    Both transitions and the objective are monotone in each front, so a pair no
    smaller than another in both coordinates can complete no better and is dropped.
    """
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
    """Exact minimal span for one instant, or for the two-instant relaxation.

    Objects marked `both` are disjoint from everything; `first` objects are disjoint
    from each other and from `both`, and so are `second` objects, while a `first` and
    a `second` object may share bytes. Sorting a legal placement by base makes each
    object start at or above the highest end already placed in each set it belongs
    to, and lowering a base to exactly that aligned front never constrains a later
    object more, so enumerating subsets with the reachable front pairs is exact.

    Every object marked `both` is the single-instant case, where one front is kept
    and the result is the least span of any placement of that instant's live set.
    Returns None when the work limit is reached, which withholds the bound.
    """
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
    """Alignment block accounting for one instant's live set, at any size.

    Fix an alignment A and let G be the objects whose alignment is a multiple of A.
    Each of them starts at a multiple of A, so it owns the whole A-sized blocks its
    extent meets, and no other member of G can start inside them. Let t be the object
    of the live set with the highest base: every other live object ends at or below
    base(t), so base(t) is at least the block bytes owned by the members of G below
    it, and at least the sizes of every other live object plus the block padding that
    no live object can cover. Minimizing over the choice of t and maximizing over A
    gives a bound that needs no search and holds for a live set of any size.
    """
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
                # The highest object owns its own blocks; the rest sit below them.
                below = owned - blocks[top.id]
                unusable = padding - pads[top.id]
                coverable = fillers
            else:
                # The highest member of G may straddle base(t): drop its padding, and
                # charge the others one block less than their own count.
                below = max(0, owned - alignment + 1)
                unusable = padding - widest
                coverable = fillers - top.size
            packed = (load - top.size) + max(0, unusable - coverable)
            candidates.append(max(below, packed) + top.size)
        strongest = max(strongest, min(candidates))
    return strongest


def live_objects(case: memory.Case, arena_id: str,
                 time: int) -> tuple[memory.Object, ...]:
    """The arena's objects charged at `time`, in identity order."""
    return tuple(sorted((obj for obj in case.objects if obj.arena == arena_id
                         and obj.start <= time < obj.reuse), key=lambda obj: obj.id))


def cliques(case: memory.Case,
            arena_id: str) -> list[tuple[int, tuple[memory.Object, ...]]]:
    """One representative instant per distinct live set, by earliest start time.

    A live set is maximal at some object's start, so the starts carry every clique of
    the interference graph. Two instants whose live sets agree on the multiset of
    sizes and alignments have the same bound, so one representative is kept; that
    can only withhold pair evidence, never raise a bound.
    """
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
    """Read a status off what the scan covered, never off whether a value appeared.

    A scan that skipped part of its domain for a limit or a budget is `partial`: its
    value is still a lower bound, being a maximum over the restrictions it did score,
    and it is not the strongest this bound could give. A scan that scored nothing
    names the limit that stopped it and claims no value at all.
    """
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
    """The charged load, with the instant that attains it as an independent witness.

    A live set only grows at a start, so the charged peak is attained at one of the
    instants enumerated here; a load no live set attains says so rather than passing.
    The oracle scans the whole trace for this value, so the row is complete unless
    that cross-check fails, which is a finding the report turns into an error.
    """
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
    """The block bound over every live set and the exact bound over the small ones.

    Live sets are taken by descending charged total, so a scan the budget stops still
    carries the strongest evidence it reached. Each row counts what it skipped and
    whether an object-count setting or the work limit was what skipped it, because a
    live set never scored could have carried a larger value than the one reported.
    """
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
        # The cost of one exact live set is known before it starts, so an unaffordable
        # one is skipped whole rather than spending the budget on a partial answer.
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
    """The exact bound for the relaxation that keeps two instants and drops the rest.

    A pair whose objects stacked in one order already fit below the strongest bound
    in hand cannot raise it, so it is skipped without enumeration and counted as
    pruned rather than as unexamined; the value here is therefore the strongest pair
    evidence found, not a survey of every pair.
    """
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
    """Every bound for one arena, and the strongest with the bound that supplied it."""
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
    # The unit is one subset-enumeration transition or one live set examined; the
    # report states it once beside the settings rather than once per arena.
    return {"arena": arena_id, "charged_load": load, "proven_lower_bound": proven,
            "proven_lower_bound_source": source,
            "proven_lower_bound_complete": settled,
            "scans_complete": all(row["complete"] for row in rows), "bounds": rows,
            "work": {"budget": work.limit, "spent": work.spent}}


def case_bounds(case: memory.Case, work_budget: int = DEFAULT_WORK_BUDGET,
                max_clique: int = MAX_CLIQUE_OBJECTS,
                max_union: int = MAX_UNION_OBJECTS) -> list[ArenaBounds]:
    """Bounds for every arena; arenas are independent and are never added together."""
    return [arena_bounds(case, arena.id, work_budget, max_clique, max_union)
            for arena in case.arenas]
