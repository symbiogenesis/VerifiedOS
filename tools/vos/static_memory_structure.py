# SPDX-License-Identifier: Apache-2.0
"""Executable laminar construction, deletion number, two-stack theorem and bounded witnesses.

The constructor uses binary integers and never enumerates addresses. Independent
placement and load checks validate its output. The deletion number is computed by an
endpoint dynamic programme that is polynomial in the binary input length, and the
two-stack construction attains the charged load whenever the crossing graph is
bipartite. The justified search is exact and magnitude-independent but exponential in
the object count; it establishes no parameterized theorem. Decomposition contracts are
refuted by finite witnesses that the exact oracle replays, and a sweep over small
families bounds the object count at which each contract first fails.
"""

import itertools
from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, TypedDict

from vos import static_memory as memory

SWEEP_MAX_OBJECTS = 3
SWEEP_MAX_WEIGHT = 2
JUSTIFIED_WORK_BUDGET = 100_000
ORACLE_WORK_BUDGET = 200_000


class Contract(TypedDict):
    """A candidate decomposition, its formal reading and the smallest count it needs."""

    name: str
    statement: str
    minimum_objects: int
    below_minimum: str
    witness: str | None


CONTRACTS: tuple[Contract, ...] = (
    Contract(name="bottom-block",
             statement="for some minimum deletion set D, placing D optimally on its own "
                       "at the origin and stacking the laminar remainder above that block "
                       "attains the optimal span",
             minimum_objects=3,
             below_minimum="two objects with a nonzero deletion number cross, so they "
                           "overlap in time and every placement spans both weights",
             witness="bottom-block-witness"),
    Contract(name="signature",
             statement="the optimal span is a function of the remainder's charged load and "
                       "the multiset of deleted weights, for every minimum deletion set",
             minimum_objects=3,
             below_minimum="with two objects the span is the sum of both weights, which the "
                           "signature determines",
             witness="signature-pair-large"),
    Contract(name="band",
             statement="for some minimum deletion set D, the optimal span is the larger of "
                       "the charged load and D's own optimal span plus the remainder's "
                       "largest load during D's lifetimes",
             minimum_objects=4,
             below_minimum="one deleted object never exceeds the load by the two-stack "
                           "theorem, and three mutually crossing intervals share an instant, "
                           "so every stack of the three is optimal",
             witness="band-witness"),
    Contract(name="canonical-remainder",
             statement="for some minimum deletion set D, the laminar constructor's placement "
                       "of the remainder at the origin extends to an optimal placement by "
                       "choosing bases for D alone",
             minimum_objects=5,
             below_minimum="a laminar deletion set is handled by the two-stack theorem, and "
                           "the only three-object crossing graph without one is a triangle, "
                           "whose intervals share an instant; four-object families with "
                           "weights at most two are exhausted by the slow test's sweep",
             witness="canonical-remainder-witness"),
)


@dataclass
class _Counter:
    limit: int
    nodes: int = 0

    def step(self) -> bool:
        if self.nodes >= self.limit:
            return False
        self.nodes += 1
        return True


def crossing_pairs(case: memory.Case) -> list[tuple[str, str]]:
    """Pairwise violations of laminarity, irrespective of placement or size."""
    result: list[tuple[str, str]] = []
    for i, left in enumerate(case.objects):
        for right in case.objects[i + 1:]:
            disjoint = left.reuse <= right.start or right.reuse <= left.start
            contains = left.start <= right.start and right.reuse <= left.reuse
            contained = right.start <= left.start and left.reuse <= right.reuse
            if not (disjoint or contains or contained):
                result.append((min(left.id, right.id), max(left.id, right.id)))
    return sorted(result)


def laminar_placement(case: memory.Case) -> list[dict[str, Any]]:
    """Construct stack placement under the baseline theorem's exact premises.

    Equal intervals are ordered by identity and nest on the stack, which places
    their objects consecutively. The independent checker runs after construction;
    its quadratic replay is separate from the sorting/stack algorithm's cost.
    """
    if len(case.arenas) != 1 or any(o.alignment != 1 for o in case.objects):
        raise memory.CaseError("laminar theorem requires one arena and unit alignment")
    stack: list[tuple[memory.Object, int]] = []
    placement: list[dict[str, Any]] = []
    for obj in sorted(case.objects, key=lambda o: (o.start, -o.reuse, o.id)):
        while stack and stack[-1][0].reuse <= obj.start:
            stack.pop()
        if stack and obj.reuse > stack[-1][0].reuse:
            raise memory.CaseError("crossing reservation intervals violate laminarity")
        base = stack[-1][1] if stack else 0
        placement.append({"id": obj.id, "arena": obj.arena, "base": base})
        stack.append((obj, base + obj.size))
    placement.sort(key=lambda row: row["id"])
    errors = memory.check_placement(case, placement)
    if errors:
        raise memory.CaseError("constructed placement refused: " + "; ".join(errors))
    return placement


def deletion_witness(case: memory.Case, max_subsets: int = 10000) -> dict[str, Any]:
    """Minimum interval deletions by bounded subset enumeration of crossing edges.

    Every crossing edge needs an endpoint removed. Edges are independent of any
    deletion, so hitting every edge is exactly the required laminarity condition.
    Only fully exhausted smaller cardinalities contribute to the lower bound.
    """
    if type(max_subsets) is not int or max_subsets < 1:
        raise memory.CaseError("max_subsets must be a positive integer")
    pairs = crossing_pairs(case)
    identifiers = sorted(o.id for o in case.objects)
    subsets = 0
    for count in range(len(identifiers) + 1):
        for removed in itertools.combinations(identifiers, count):
            if subsets >= max_subsets:
                return {"status": "incomplete", "minimum": None,
                        "proven_lower_bound": count, "removed": None,
                        "subsets": subsets, "crossing_pairs": pairs}
            subsets += 1
            discarded = set(removed)
            if all(left in discarded or right in discarded for left, right in pairs):
                return {"status": "optimal", "minimum": count,
                        "proven_lower_bound": count, "removed": list(removed),
                        "subsets": subsets, "crossing_pairs": pairs}
    raise RuntimeError("deleting all intervals must remove every crossing")


def maximum_laminar_subfamily(case: memory.Case) -> dict[str, Any]:
    """Largest laminar subfamily by an endpoint dynamic programme over sorted coordinates.

    F(s, t) is the largest laminar subfamily of the intervals inside [c_s, c_t) for
    distinct sorted coordinates c. Equal intervals nest, so they form one group whose
    weight is its size, and every interval inside [c_s, c_t) nests in that group:
    F(s, t) = w(s, t) + max(F(s + 1, t), max over s < q < t of F(s, q) + F(q, t)).
    Coordinates are only sorted and compared, so the work is cubic in the number of
    distinct endpoints and independent of the numerical magnitudes. The complement of
    the returned subfamily is a minimum deletion set.
    """
    coordinates = sorted({c for o in case.objects for c in (o.start, o.reuse)})
    index = {c: i for i, c in enumerate(coordinates)}
    count = len(coordinates)
    groups: dict[tuple[int, int], list[str]] = {}
    for obj in sorted(case.objects, key=lambda o: o.id):
        groups.setdefault((index[obj.start], index[obj.reuse]), []).append(obj.id)
    table = [[0] * count for _ in range(count)]
    split = [[-1] * count for _ in range(count)]
    for width in range(1, count):
        for s in range(count - width):
            t = s + width
            best, chosen = table[s + 1][t], -1
            for q in range(s + 1, t):
                value = table[s][q] + table[q][t]
                if value > best:
                    best, chosen = value, q
            table[s][t] = len(groups.get((s, t), ())) + best
            split[s][t] = chosen
    kept: list[str] = []
    pending = [(0, count - 1)] if count else []
    while pending:
        s, t = pending.pop()
        if s >= t:
            continue
        kept.extend(groups.get((s, t), ()))
        if split[s][t] < 0:
            pending.append((s + 1, t))
        else:
            pending.extend(((s, split[s][t]), (split[s][t], t)))
    kept.sort()
    if count and len(kept) != table[0][count - 1]:
        raise RuntimeError("reconstructed laminar subfamily differs from the table value")
    removed = sorted({o.id for o in case.objects} - set(kept))
    pairs = crossing_pairs(case)
    discarded = set(removed)
    if not all(left in discarded or right in discarded for left, right in pairs):
        raise RuntimeError("dynamic programme kept a crossing pair")
    return {"method": "endpoint-dynamic-programme", "minimum": len(removed),
            "removed": removed, "kept": kept, "distinct_coordinates": count,
            "crossing_pairs": pairs}


def _odd_cycle(left: str, right: str, parent: dict[str, str | None]) -> list[str]:
    """Close the BFS tree paths of two equally coloured neighbours into an odd cycle."""
    def ascent(node: str) -> list[str]:
        path = [node]
        while (above := parent[path[-1]]) is not None:
            path.append(above)
        return path

    left_path, right_path = ascent(left), ascent(right)
    while len(left_path) > 1 and len(right_path) > 1 and left_path[-2] == right_path[-2]:
        left_path.pop()
        right_path.pop()
    cycle = [*left_path, *reversed(right_path[:-1])]
    if len(cycle) % 2 == 0:
        raise RuntimeError("two equally coloured neighbours must close an odd cycle")
    return cycle


def two_colouring(case: memory.Case) -> dict[str, Any]:
    """Two-colour the crossing graph; a failure carries an odd cycle of crossing pairs."""
    identifiers = sorted(o.id for o in case.objects)
    adjacency: dict[str, set[str]] = {i: set() for i in identifiers}
    for left, right in crossing_pairs(case):
        adjacency[left].add(right)
        adjacency[right].add(left)
    colour: dict[str, int] = {}
    parent: dict[str, str | None] = {}
    for root in identifiers:
        if root in colour:
            continue
        colour[root] = 0
        parent[root] = None
        queue = deque([root])
        while queue:
            node = queue.popleft()
            for other in sorted(adjacency[node]):
                if other not in colour:
                    colour[other] = 1 - colour[node]
                    parent[other] = node
                    queue.append(other)
                elif colour[other] == colour[node]:
                    return {"bipartite": False, "lower": None, "upper": None,
                            "odd_cycle": _odd_cycle(node, other, parent)}
    return {"bipartite": True,
            "lower": [i for i in identifiers if colour[i] == 0],
            "upper": [i for i in identifiers if colour[i] == 1],
            "odd_cycle": None}


def _subfamily(case: memory.Case, identifiers: set[str] | frozenset[str]) -> memory.Case:
    objects = tuple(o for o in case.objects if o.id in identifiers)
    return memory.Case(case.name, case.provenance, case.mode, case.arenas, objects)


def two_stack_placement(case: memory.Case, lower: list[str],
                        upper: list[str]) -> list[dict[str, Any]]:
    """Stack one laminar subfamily up from the origin and the other down from the load.

    At any instant the lower stack occupies exactly its own load from zero and the
    upper stack exactly its own load below the charged load, so the two never meet
    and the span equals the charged load, which is also a lower bound.
    """
    if len(case.arenas) != 1 or any(o.alignment != 1 for o in case.objects):
        raise memory.CaseError("two-stack theorem requires one arena and unit alignment")
    if set(lower) | set(upper) != {o.id for o in case.objects} or set(lower) & set(upper):
        raise memory.CaseError("two-stack halves must partition the family")
    arena = case.arenas[0]
    load = memory.peak_load(case, arena.id)
    if load > arena.capacity:
        raise memory.CaseError("charged load exceeds the arena capacity")
    sizes = {o.id: o.size for o in case.objects}
    placement = laminar_placement(_subfamily(case, set(lower)))
    placement.extend({"id": row["id"], "arena": row["arena"],
                      "base": load - row["base"] - sizes[row["id"]]}
                     for row in laminar_placement(_subfamily(case, set(upper))))
    placement.sort(key=lambda row: row["id"])
    errors = memory.check_placement(case, placement)
    if errors:
        raise memory.CaseError("two-stack placement refused: " + "; ".join(errors))
    if case.objects and memory.placement_spans(case, placement)[arena.id] != load:
        raise RuntimeError("two-stack construction must attain the charged load")
    return placement


def _justified_search(objects: tuple[memory.Object, ...], height: int,
                      budget: _Counter) -> tuple[str, dict[str, int] | None]:
    """Complete search over left-justified placements of at most the given height.

    In some optimal placement every base is zero or the top of an interfering object
    below it, so visiting objects in nondecreasing base order with identity ties and
    offering only those candidates loses no such placement. A state whose completion
    failed is remembered, since the remaining subproblem depends only on the placed
    set. Candidates are sums of weights, never a scan over the numeric address range.
    """
    order = sorted(objects, key=lambda o: o.id)
    sizes = {o.id: o.size for o in order}
    interferes = {o.id: {p.id for p in order
                         if p.id != o.id and o.start < p.reuse and p.start < o.reuse}
                  for o in order}
    failed: set[frozenset[tuple[str, int]]] = set()
    placed: dict[str, int] = {}

    def visit(last_base: int, last_id: str) -> str:
        if len(placed) == len(order):
            return "feasible"
        key = frozenset(placed.items())
        if key in failed:
            return "infeasible"
        for obj in order:
            if obj.id in placed:
                continue
            below = [j for j in interferes[obj.id] if j in placed]
            candidates = {0} | {placed[j] + sizes[j] for j in below}
            for base in sorted(candidates):
                if base < last_base or (base == last_base and obj.id <= last_id):
                    continue
                if base + obj.size > height:
                    continue
                if any(base < placed[j] + sizes[j] and placed[j] < base + obj.size
                       for j in below):
                    continue
                if not budget.step():
                    return "incomplete"
                placed[obj.id] = base
                status = visit(base, obj.id)
                if status != "infeasible":
                    return status
                del placed[obj.id]
        failed.add(key)
        return "infeasible"

    status = visit(0, "")
    return status, dict(placed) if status == "feasible" else None


def justified_exact(case: memory.Case, work_budget: int = JUSTIFIED_WORK_BUDGET) -> dict[str, Any]:
    """Exact span without address enumeration: two stacks when bipartite, else a search.

    A bipartite crossing graph is placed by the two-stack construction at the charged
    load. Otherwise the deletion set gives a feasible upper bound, and a binary search
    over heights, each decided by the complete justified search, finds the least
    feasible height. The number of heights tested is logarithmic in the weight sum,
    but each search is exponential in the object count in the worst case; a cutoff
    reports `incomplete` with the bounds proved so far and no optimum.
    """
    if type(work_budget) is not int or work_budget < 1:
        raise memory.CaseError("work_budget must be a positive integer")
    if len(case.arenas) != 1 or any(o.alignment != 1 for o in case.objects):
        raise memory.CaseError("justified search requires one arena and unit alignment")
    arena = case.arenas[0]
    lower = memory.peak_load(case, arena.id)
    colouring = two_colouring(case)
    deletion = maximum_laminar_subfamily(case)
    budget = _Counter(work_budget)
    result: dict[str, Any] = {
        "case": case.name, "contract_sha256": memory.contract_hash(case),
        "charged_load_lower_bound": lower, "capacity": arena.capacity,
        "crossing_graph": colouring, "deletion": deletion, "work_budget": work_budget,
        "heights": [], "status": "incomplete", "method": None, "span": None,
        "placement": None, "proven_lower_bound": lower, "infeasible_through": lower - 1,
    }
    if lower > arena.capacity:
        result.update({"status": "infeasible", "method": "load-exceeds-capacity",
                       "infeasible_through": arena.capacity, "nodes": 0})
        return result
    if colouring["bipartite"]:
        placement = two_stack_placement(case, colouring["lower"], colouring["upper"])
        result.update({"status": "optimal", "method": "two-laminar-stacks", "span": lower,
                       "placement": placement, "proven_lower_bound": lower, "nodes": 0})
        return result
    objects = case.objects
    sizes = {o.id: o.size for o in objects}
    kept = laminar_placement(_subfamily(case, set(deletion["kept"])))
    top = max((row["base"] + sizes[row["id"]] for row in kept), default=0)
    stacked: dict[str, int] = {row["id"]: row["base"] for row in kept}
    for identifier in deletion["removed"]:
        stacked[identifier] = top
        top += sizes[identifier]
    witness: dict[str, int] | None = stacked
    low, high = lower - 1, top
    if top > arena.capacity:
        high = arena.capacity
        status, witness = _justified_search(objects, high, budget)
        result["heights"].append({"height": high, "status": status, "nodes": budget.nodes})
        if status == "infeasible":
            result.update({"status": "infeasible", "method": "justified-exhaustive",
                           "infeasible_through": arena.capacity, "nodes": budget.nodes})
            return result
        if status == "incomplete":
            result["nodes"] = budget.nodes
            return result
    complete = True
    while high - low > 1:
        middle = (low + high) // 2
        before = budget.nodes
        status, found = _justified_search(objects, middle, budget)
        result["heights"].append({"height": middle, "status": status,
                                  "nodes": budget.nodes - before})
        if status == "feasible":
            high, witness = middle, found
        elif status == "infeasible":
            low = middle
        else:
            complete = False
            break
    if witness is None:
        raise RuntimeError("a feasible height must carry its witness")
    placement = sorted(({"id": o.id, "arena": o.arena, "base": witness[o.id]} for o in objects),
                       key=lambda row: row["id"])
    if memory.check_placement(case, placement):
        raise RuntimeError("justified search witness failed the independent checker")
    if memory.placement_spans(case, placement)[arena.id] > high:
        raise RuntimeError("justified search witness exceeds its height")
    result.update({"span": high, "placement": placement, "nodes": budget.nodes,
                   "infeasible_through": low, "proven_lower_bound": low + 1})
    if complete:
        result.update({"status": "optimal",
                       "method": "load-equality" if high == lower else "justified-exhaustive"})
    return result


def minimum_deletion_sets(case: memory.Case, minimum: int) -> list[tuple[str, ...]]:
    """Every deletion set of the minimum size, by enumeration over a small family."""
    pairs = crossing_pairs(case)
    identifiers = sorted(o.id for o in case.objects)
    return [removed for removed in itertools.combinations(identifiers, minimum)
            if all(left in removed or right in removed for left, right in pairs)]


def _exact_span(case: memory.Case, work_budget: int) -> int:
    receipt = memory.solve_exact(case, work_budget=work_budget)
    if receipt["status"] != "optimal":
        raise memory.CaseError(f"{case.name}: exact oracle did not complete")
    span = receipt["arenas"][0]["best_span"]
    if not isinstance(span, int):
        raise TypeError("a completed optimum carries an integer span")
    return span


def decomposition_values(case: memory.Case, removed: tuple[str, ...],
                         optimum: int, work_budget: int = ORACLE_WORK_BUDGET) -> dict[str, Any]:
    """Evaluate every candidate decomposition for one minimum deletion set.

    `bottom_block` places the deleted objects optimally on their own and the laminar
    remainder above them. `band` reserves the deleted objects' own optimal span above
    the remainder's largest load during their lifetimes. `signature` is the remainder's
    charged load with the deleted weights. `canonical_extends` asks whether the
    remainder's constructor placement extends to a placement of the given span by
    choosing bases for the deleted objects, searched over their justified candidates.
    """
    arena = case.arenas[0].id
    deleted = _subfamily(case, set(removed))
    remainder = _subfamily(case, {o.id for o in case.objects} - set(removed))
    remainder_load = memory.peak_load(remainder, arena) if remainder.objects else 0
    deleted_span = _exact_span(deleted, work_budget) if deleted.objects else 0
    # Loads are step functions changing at starts, so every start inside a deleted
    # lifetime, whichever object it belongs to, samples the remainder's largest load.
    instants = sorted({o.start for o in case.objects})
    during = max((sum(r.size for r in remainder.objects if r.start <= t < r.reuse)
                  for t in instants
                  if any(d.start <= t < d.reuse for d in deleted.objects)), default=0)
    load = memory.peak_load(case, arena)
    return {"removed": list(removed),
            "bottom_block": deleted_span + remainder_load,
            "band": max(load, during + deleted_span),
            "signature": {"remainder_load": remainder_load,
                          "deleted_weights": sorted(o.size for o in deleted.objects)},
            "canonical_extends": canonical_remainder_extends(case, removed, optimum)}


def canonical_remainder_extends(case: memory.Case, removed: tuple[str, ...], span: int) -> bool:
    """Whether the constructor's remainder placement extends to the given span.

    The deleted objects alone are searched over left-justified candidates: shifting a
    deleted object down never moves the fixed remainder, so the normal-form argument
    applies with the remainder as fixed obstacles and the candidate set is complete.
    """
    remainder = _subfamily(case, {o.id for o in case.objects} - set(removed))
    fixed = {row["id"]: row["base"] for row in laminar_placement(remainder)}
    deleted = sorted((o for o in case.objects if o.id in removed), key=lambda o: o.id)
    sizes = {o.id: o.size for o in case.objects}
    objects = {o.id: o for o in case.objects}

    def interferes(left: memory.Object, right: memory.Object) -> bool:
        return left.start < right.reuse and right.start < left.reuse

    def visit(placed: dict[str, int], last_base: int, last_id: str) -> bool:
        if len(placed) == len(deleted):
            return True
        for obj in deleted:
            if obj.id in placed:
                continue
            below = {j: b for j, b in {**fixed, **placed}.items()
                     if interferes(obj, objects[j])}
            for base in sorted({0} | {b + sizes[j] for j, b in below.items()}):
                if base < last_base or (base == last_base and obj.id <= last_id):
                    continue
                if base + obj.size > span:
                    continue
                if any(base < b + sizes[j] and b < base + obj.size for j, b in below.items()):
                    continue
                if visit({**placed, obj.id: base}, base, obj.id):
                    return True
        return False

    return visit({}, 0, "")


def interval_shapes(count: int, coordinates: int) -> Iterator[list[tuple[int, int]]]:
    """Multisets of `count` intervals over 0..coordinates that use every coordinate.

    Every family of `count` intervals is order-isomorphic to exactly one shape with at
    most 2 * count distinct coordinates, so iterating `coordinates` up to that bound
    covers every interval family of that size once.
    """
    items = [(s, e) for s in range(coordinates + 1) for e in range(s + 1, coordinates + 1)]

    def extend(start: int, remaining: int, used: frozenset[int],
               chosen: list[tuple[int, int]]) -> Iterator[list[tuple[int, int]]]:
        if remaining == 0:
            if len(used) == coordinates + 1:
                yield list(chosen)
            return
        if len(used) + 2 * remaining < coordinates + 1:
            return
        for position in range(start, len(items)):
            s, e = items[position]
            chosen.append((s, e))
            yield from extend(position, remaining - 1, used | {s, e}, chosen)
            chosen.pop()

    yield from extend(0, count, frozenset(), [])


def _contract(name: str, rows: list[tuple[str, int, int, int]],
              alignment: int = 1) -> dict[str, Any]:
    objects: list[dict[str, Any]] = []
    base = 0
    for identifier, size, start, end in rows:
        base = (base + alignment - 1) // alignment * alignment
        objects.append({"id": identifier, "arena": "arena", "size": size,
                        "payload": size, "alignment": alignment, "base": base,
                        "start": start, "payload_end": end, "authority_end": end,
                        "sweep_end": end, "reuse": end})
        base += size
    return {"name": name, "provenance": "synthetic structural witness",
            "mode": "one declared execution",
            "arenas": [{"id": "arena", "owner": "owner", "capacity": max(1, base)}],
            "objects": objects}


def _refutations(case: memory.Case, optimum: int,
                 work_budget: int = ORACLE_WORK_BUDGET) -> dict[str, Any]:
    """Which contracts this family refutes, over every minimum deletion set."""
    deletion = maximum_laminar_subfamily(case)
    covers = minimum_deletion_sets(case, deletion["minimum"])
    values = [decomposition_values(case, removed, optimum, work_budget) for removed in covers]
    return {"minimum": deletion["minimum"], "covers": values,
            "bottom-block": bool(values) and all(v["bottom_block"] > optimum for v in values),
            "band": bool(values) and all(v["band"] > optimum for v in values),
            "canonical-remainder": bool(values) and not any(v["canonical_extends"]
                                                            for v in values)}


def decomposition_sweep(max_objects: int = SWEEP_MAX_OBJECTS,
                        max_weight: int = SWEEP_MAX_WEIGHT,
                        work_budget: int = ORACLE_WORK_BUDGET) -> dict[str, Any]:
    """Exhaust every interval shape up to a size and weight bound against the oracle.

    The sweep records the smallest object count at which each contract is refuted
    inside its domain, the deletion numbers seen, and every family whose optimum
    exceeds its charged load. It is finite evidence about that domain and nothing
    about larger weights, larger families or the general complexity question.
    """
    if min(max_objects, max_weight) < 1:
        raise memory.CaseError("sweep bounds must be positive")
    first: dict[str, dict[str, Any] | None] = {c["name"]: None for c in CONTRACTS}
    signatures: dict[tuple[int, tuple[int, ...]], tuple[int, dict[str, Any]]] = {}
    per_size: list[dict[str, Any]] = []
    above_load: list[dict[str, Any]] = []
    incomplete = 0
    for count in range(1, max_objects + 1):
        families = 0
        by_minimum: dict[str, int] = {}
        for coordinates in range(1, 2 * count):
            for shape in interval_shapes(count, coordinates):
                for weights in itertools.product(range(1, max_weight + 1), repeat=count):
                    rows = [(f"o{i}", w, s, e)
                            for i, ((s, e), w) in enumerate(zip(shape, weights, strict=True))]
                    raw = _contract(f"sweep-{count}-{coordinates}-{families}", rows)
                    case = memory.parse_case(raw)
                    families += 1
                    receipt = memory.solve_exact(case, work_budget=work_budget)
                    if receipt["status"] != "optimal":
                        incomplete += 1
                        continue
                    optimum = receipt["arenas"][0]["best_span"]
                    load = memory.peak_load(case, "arena")
                    found = _refutations(case, optimum, work_budget)
                    key = str(found["minimum"])
                    by_minimum[key] = by_minimum.get(key, 0) + 1
                    if optimum > load:
                        above_load.append({"contract": raw, "load": load, "optimum": optimum,
                                           "minimum_deletions": found["minimum"]})
                    if found["minimum"] == 0:
                        continue
                    for name in ("bottom-block", "band", "canonical-remainder"):
                        if found[name] and first[name] is None:
                            first[name] = {"objects": count, "contract": raw,
                                           "optimum": optimum, "covers": found["covers"]}
                    for cover in found["covers"]:
                        signature = (cover["signature"]["remainder_load"],
                                     tuple(cover["signature"]["deleted_weights"]))
                        seen = signatures.setdefault(signature, (optimum, raw))
                        if seen[0] != optimum and first["signature"] is None:
                            first["signature"] = {"objects": count, "contract": raw,
                                                  "optimum": optimum, "removed": cover["removed"],
                                                  "other_contract": seen[1],
                                                  "other_optimum": seen[0]}
        per_size.append({"objects": count, "families": families,
                         "by_minimum_deletions": dict(sorted(by_minimum.items()))})
    return {"domain": {"max_objects": max_objects, "max_weight": max_weight,
                       "coordinates": "every shape, at most two per object",
                       "oracle_work_budget": work_budget},
            "status": "complete" if not incomplete else "incomplete",
            "incomplete_oracle_runs": incomplete, "families": per_size,
            "first_refutation": first, "span_above_load": above_load}


def report(source_revision: str = "unspecified",
           sweep_max_objects: int = SWEEP_MAX_OBJECTS) -> dict[str, Any]:
    """Replay scoped positive and assumption-breaking construction witnesses."""
    huge = 1 << 256
    contracts = [
        _contract("equal-nested-disjoint", [("outer", 2, 0, 10),
                  ("equal", 3, 0, 10), ("left", 4, 1, 4), ("right", 6, 4, 9)]),
        _contract("crossing", [("a", 1, 0, 2), ("b", 1, 1, 3)]),
        _contract("three-mutually-crossing", [("a", 1, 0, 3),
                  ("b", 1, 1, 4), ("c", 1, 2, 5)]),
        _contract("alignment-breaks-equality", [("a", 1, 0, 1),
                  ("b", 1, 0, 1)], alignment=2),
        _contract("binary-address-scale", [("outer", huge, 0, huge),
                  ("left", huge + 1, 1, 3), ("right", huge + 2, 3, huge - 1)]),
        _contract("empty-family", []),
        _contract("binary-scale-triangle", [("a", huge, 0, 3), ("b", huge + 1, 1, 4),
                  ("c", huge + 2, 2, 5), ("inner", huge + 3, 0, 1)]),
        _contract("bottom-block-witness", [("a", 2, 0, 1), ("b", 1, 1, 3), ("c", 1, 2, 4)]),
        _contract("signature-pair-small", [("a", 1, 0, 2), ("b", 2, 1, 3)]),
        _contract("signature-pair-large", [("a", 1, 0, 1), ("b", 1, 0, 2), ("c", 1, 1, 3)]),
        _contract("band-witness", [("a", 1, 0, 2), ("b", 1, 0, 4), ("c", 1, 1, 3),
                  ("d", 2, 3, 5)]),
        _contract("canonical-remainder-witness", [("r1", 1, 0, 2), ("r", 1, 0, 3),
                  ("d1", 1, 1, 4), ("d2", 1, 2, 5), ("r2", 2, 4, 6)]),
    ]
    exact_cases = {"alignment-breaks-equality", "three-mutually-crossing", "crossing",
                   "bottom-block-witness", "signature-pair-small", "signature-pair-large",
                   "band-witness", "canonical-remainder-witness"}
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    optima: dict[str, int] = {}
    refuted: dict[str, dict[str, Any]] = {}
    for raw in contracts:
        case = memory.parse_case(raw)
        item: dict[str, Any] = {
            "contract": raw, "contract_sha256": memory.contract_hash(case),
            "deletion": deletion_witness(case),
            "deletion_dp": maximum_laminar_subfamily(case),
            "crossing_graph": two_colouring(case),
            "charged_load_lower_bound": memory.peak_load(case, "arena"),
        }
        if (item["deletion"]["status"] == "optimal"
                and item["deletion"]["minimum"] != item["deletion_dp"]["minimum"]):
            errors.append(f"{case.name}: dynamic programme disagrees with enumeration")
        supported = not crossing_pairs(case) and all(o.alignment == 1 for o in case.objects)
        try:
            placement = laminar_placement(case)
        except memory.CaseError as error:
            item.update({"construction": "outside-premises", "reason": str(error)})
            if supported:
                errors.append(f"{case.name}: supported construction refused: {error}")
        else:
            span = memory.placement_spans(case, placement)["arena"]
            item.update({"construction": "checked", "placement": placement,
                         "span": span, "attains_load": span == item["charged_load_lower_bound"]})
            if not item["attains_load"]:
                errors.append(f"{case.name}: laminar construction failed to attain load")
            if not supported:
                errors.append(f"{case.name}: construction accepted unsupported premises")
        if all(o.alignment == 1 for o in case.objects):
            item["exact_justified"] = justified_exact(case)
            if item["exact_justified"]["status"] != "optimal":
                errors.append(f"{case.name}: justified search did not complete")
            elif (item["crossing_graph"]["bipartite"]
                  and item["exact_justified"]["span"] != item["charged_load_lower_bound"]):
                errors.append(f"{case.name}: two-stack theorem failed to attain load")
        if case.name in exact_cases:
            item["exact"] = memory.solve_exact(case, work_budget=ORACLE_WORK_BUDGET)
            item["optimality_replay"] = memory.verify_optimality(case, item["exact"])
            if item["optimality_replay"]["status"] != "verified":
                errors.append(f"{case.name}: oracle optimality did not replay")
            else:
                optimum = item["exact"]["arenas"][0]["best_span"]
                optima[case.name] = optimum
                justified = item.get("exact_justified")
                if justified is not None and justified["span"] != optimum:
                    errors.append(f"{case.name}: justified search differs from the oracle")
                if not any(o.alignment != 1 for o in case.objects):
                    item["refutations"] = _refutations(case, optimum)
                    refuted[case.name] = item["refutations"]
        results.append(item)
    decompositions: list[dict[str, Any]] = []
    for contract in CONTRACTS:
        entry: dict[str, Any] = dict(contract)
        witness = contract["witness"]
        if witness is None or witness not in refuted:
            errors.append(f"{contract['name']}: witness was not replayed")
            entry["refuted"] = False
        elif contract["name"] == "signature":
            small = next(v for v in refuted["signature-pair-small"]["covers"]
                         if v["removed"] == ["a"])
            large = next(v for v in refuted["signature-pair-large"]["covers"]
                         if v["removed"] == ["c"])
            entry["refuted"] = (small["signature"] == large["signature"]
                                and optima["signature-pair-small"] != optima["signature-pair-large"])
            entry["evidence"] = {"signature": small["signature"],
                                 "optima": {"signature-pair-small": optima["signature-pair-small"],
                                            "signature-pair-large": optima["signature-pair-large"]}}
        else:
            entry["refuted"] = refuted[witness][contract["name"]]
            entry["evidence"] = {"optimum": optima[witness], "covers": refuted[witness]["covers"]}
        if not entry["refuted"]:
            errors.append(f"{contract['name']}: declared witness does not refute the contract")
        decompositions.append(entry)
    sweep = decomposition_sweep(sweep_max_objects)
    if sweep["status"] != "complete":
        errors.append("decomposition sweep left oracle runs incomplete")
    for contract in CONTRACTS:
        found = sweep["first_refutation"][contract["name"]]
        if found is not None and found["objects"] < contract["minimum_objects"]:
            errors.append(f"{contract['name']}: sweep refuted below the stated minimum")
    return {
        "schema": "static-memory-structure-v1", "source_revision": source_revision,
        "scope": "executable finite evidence and a laminar constructor; no machine-checked theorem",
        "settings": {"deletion_max_subsets": 10000, "address_enumeration_in_constructor": False,
                     "justified_work_budget": JUSTIFIED_WORK_BUDGET,
                     "oracle_work_budget": ORACLE_WORK_BUDGET,
                     "sweep_max_objects": sweep_max_objects, "sweep_max_weight": SWEEP_MAX_WEIGHT},
        "cases": results, "decompositions": decompositions, "sweep": sweep, "errors": errors,
        "open_obligations": [
            "source and admitted execution refinement to reservation intervals",
            "machine-checked general construction and optimality theorem",
            "exact placement for a non-bipartite crossing graph in time f(k) times a "
            "polynomial of the binary input length, or hardness for a fixed k",
            "the smallest deletion number of a family whose optimum exceeds its load",
            "full CHERI, bank, owner and multiple-execution constraints",
        ],
    }
