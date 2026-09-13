# SPDX-License-Identifier: Apache-2.0
"""Legal slot positions under the profile's own representability granule.

The research placement oracle models an object as a charged extent with an alignment
and says that arbitrary CHERI representability is outside its declared model. This
layer closes the representability half of that gap for the format this repository
actually fixes, and closes nothing else.

**The granule is derived, never restated.** A region's granule is R-15-007c's
function of its own charged length, ported once from `MemoryPlan.v` into
[memplan](memplan.py) as `representable_granule` and called here through that module,
so a change to the function moves this layer with it and a mutant of it refuses the
placements it should. Every parameter of the format itself is read where
[capformat](capformat.py) reads it and is named rather than copied.

**Two decisions, kept apart because the register keeps them apart.** A base off its
granule is a position the plan may not choose, so it is offered to the oracle as a
legal-base layer and every search, checker and replay obeys it. A *length* its own
granule does not divide has no exact bounds at any base whatever, so it is reported
per object as an exact-length refusal and is never quietly rounded: R-15-007k puts
that rounding in the static memory plan, which lays each object at its representable
alignment and at a granule-quantized length, and declines `CSetBoundsExact` so that
an outward round is a defect in the plan rather than a runtime event. The quantized
length this module computes is what such a plan would have to charge, and it is
reported beside the object rather than substituted for its charged size.

Everything else the format decides stays outside, and
[the representability document](../../docs/implementation/static-memory-representability.md)
names each part. This module is host research: it admits nothing, plans nothing, and
credits nothing to the product.
"""

import hashlib
import json
from collections.abc import Sequence
from math import lcm
from pathlib import Path
from typing import Any, TypedDict

from vos import memplan
from vos import static_memory as memory
from vos import static_memory_corpus as witnesses

GENERATOR = "tools/vos/static_memory_repr.py"
VERSION = "static-memory-representability-v1"

# The exact search and its replay are bounded here rather than by the command, so the
# receipt's statuses are a property of the fixtures and this constant alone.
WORK_BUDGET = 200_000

# Above this many simultaneously live objects the stacked bound is not computed for
# that instant and the charged load stands for it. The bound below is exponential in
# the size of one live set, and an instant left out weakens the bound without making
# it unsound: it is a maximum over instants, each of which is a lower bound on its own.
MAX_STACKED_OBJECTS = 14

# How many times the quantized length is allowed to move before the module refuses.
# One step always suffices at the ported granule, and the proof is in the document;
# the bound is here so that a mutated granule raises instead of looping.
MAX_QUANTIZE_STEPS = 4


class Refusal(TypedDict):
    """One object whose charged extent has no exact bounds at any base."""

    id: str
    arena: str
    size: int
    granule: int
    quantized_size: int
    padding_bytes: int


class SideRow(TypedDict):
    """One arena's result under one of the two legal-position models."""

    best_span: int | None
    status: str
    certificate: dict[str, Any] | None
    replay_status: str | None
    stacked_lower_bound: int
    span_over_stacked_bound: int | None


class ArenaRow(TypedDict):
    """The two models beside each other for one arena, and what separates them."""

    arena: str
    owner: str
    charged_load: int
    alignment_only: SideRow
    representable: SideRow
    representability_span_cost: int | None
    representability_cost_status: str
    exact_length_refusals: list[Refusal]


class AgreementRow(TypedDict):
    """One exported region, decided by this layer and by the memory plan's own port."""

    region: int
    length: int
    base: int
    granule: int
    declared_base_granules: int
    declared_length_granules: int
    base_legal_here: bool
    base_quantized_there: bool
    length_legal_here: bool
    length_quantized_there: bool


def _round_up(value: int, step: int) -> int:
    """The least multiple of `step` at or above `value`, for positive `step`."""
    if step < 1:
        raise memory.CaseError("a legal-position step must be a positive integer")
    return ((value + step - 1) // step) * step


def granule_of_size(size: int) -> int:
    """R-15-007c's granule for a charged extent, from the memory plan's own port.

    The call is what makes this a derivation rather than a second copy of the
    function: `memplan.representable_granule` ports the `.v`'s definition, and this
    module holds no threshold, no exponent and no arithmetic of its own.
    """
    if type(size) is not int or size < 1:
        raise memory.CaseError("a charged extent must be a positive integer")
    return memplan.representable_granule(size)


def base_refusal(obj: memory.Object, base: int) -> str | None:
    """The legal-base layer: a base is legal exactly where the object's granule divides it.

    This is `memplan.base_is_quantized` decided from the base itself rather than from a
    declared granule count, which is the only form available here: a research contract
    states a base and no count. The two agree wherever the count is the base's own,
    which the cross-check against the exported plan is what establishes.
    """
    granule = granule_of_size(obj.size)
    if base % granule:
        return (f"representable: {obj.id} base {base} is no whole number of its "
                f"{granule}-byte granule")
    return None


def probe(identifier: str, size: int) -> memory.Object:
    """An object carrying only what the legal-base layer reads: an identity and an extent.

    The lifetime fields are filled with the shortest legal trace because the layer never
    looks at them, which is what lets a region of the exported plan be asked the same
    question a research contract's object is asked, through the same function.
    """
    return memory.Object(identifier, "probe", size, size, 1, 0, 0, 0, 0, 1, 0)


def length_refusal(obj: memory.Object) -> Refusal | None:
    """The object's exact-length refusal, or None where its extent is already quantized.

    Nothing is rounded: the quantized extent is reported as what a plan meeting
    R-15-007k would have to charge, and the object keeps the size its contract states.
    """
    granule = granule_of_size(obj.size)
    if obj.size % granule == 0:
        return None
    quantized = quantized_size(obj.size)
    return Refusal(id=obj.id, arena=obj.arena, size=obj.size, granule=granule,
                   quantized_size=quantized, padding_bytes=quantized - obj.size)


def quantized_size(size: int) -> int:
    """The least charged extent at or above `size` that its own granule divides.

    Rounding up can coarsen the granule, so the answer is a fixed point rather than one
    division: the loop re-derives the granule of the extent it just produced and stops
    where that extent is a whole number of it. At the ported granule the first step
    always lands on one, which the document proves; the bound is what keeps a mutated
    granule a refusal instead of a hang.
    """
    extent = size
    for _ in range(MAX_QUANTIZE_STEPS):
        granule = granule_of_size(extent)
        if extent % granule == 0:
            return extent
        extent = _round_up(extent, granule)
    raise memory.CaseError(f"no quantized extent at or above {size} within "
                           f"{MAX_QUANTIZE_STEPS} steps of its own granule")


def step_of(obj: memory.Object, *, representable: bool) -> int:
    """The spacing every legal base of this object is a multiple of.

    Alignment alone under the model the existing receipts were computed under, and the
    least common multiple of that alignment and the object's granule under this layer,
    a base having to be a multiple of both.
    """
    if not representable:
        return obj.alignment
    return lcm(obj.alignment, granule_of_size(obj.size))


def stacked_bound(objects: Sequence[memory.Object], *, representable: bool) -> int | None:
    """The least end any disjoint stacking of one live set can reach, or None if too large.

    Sound as a lower bound on the arena's span at that instant, and the document states
    the argument: the objects live at one instant occupy disjoint extents, so ordering
    them by base gives b1 < b2 < ... with b1 >= 0 and b(j+1) >= b(j) + size(j) rounded
    up to the next multiple of object j+1's step. Each step of that recurrence is
    monotone in the end below it, so the exchange argument holds and the minimum over
    orders is computed by a subset walk rather than over the orders themselves.
    """
    items = tuple((obj.size, step_of(obj, representable=representable)) for obj in objects)
    if not items:
        return 0
    if len(items) > MAX_STACKED_OBJECTS:
        return None
    best = [0] * (1 << len(items))
    for mask in range(1, 1 << len(items)):
        reached: int | None = None
        for index, (extent, step) in enumerate(items):
            bit = 1 << index
            if not mask & bit:
                continue
            end = _round_up(best[mask ^ bit], step) + extent
            if reached is None or end < reached:
                reached = end
        if reached is None:
            raise RuntimeError("a nonempty subset carried no member")
        best[mask] = reached
    return best[-1]


def arena_lower_bound(case: memory.Case, arena_id: str, *, representable: bool) -> int:
    """A sound lower bound on that arena's span: the charged load, raised where a live
    set cannot be stacked as tightly as its bytes.

    Only start times are examined, every live set being contained in the live set at
    the latest start among its members, and the charged load stands for any instant
    whose live set is larger than the stacked bound will walk.
    """
    load = memory.peak_load(case, arena_id)
    objects = [obj for obj in case.objects if obj.arena == arena_id]
    bound = load
    for time in sorted({obj.start for obj in objects}):
        live = [obj for obj in objects if obj.start <= time < obj.reuse]
        stacked = stacked_bound(live, representable=representable)
        if stacked is not None and stacked > bound:
            bound = stacked
    return bound


def _side(case: memory.Case, arena: memory.Arena, exact: dict[str, Any],
          replay: dict[str, Any] | None, *, representable: bool) -> SideRow:
    row = next(item for item in exact["arenas"] if item["arena"] == arena.id)
    span = row["best_span"]
    bound = arena_lower_bound(case, arena.id, representable=representable)
    return SideRow(best_span=span, status=row["status"], certificate=row["certificate"],
                   replay_status=None if replay is None else replay["status"],
                   stacked_lower_bound=bound,
                   span_over_stacked_bound=None if span is None else span - bound)


def compare_case(raw: dict[str, Any], work_budget: int = WORK_BUDGET) -> dict[str, Any]:
    """Solve one contract under both legal-position models and report what separates them."""
    case = memory.parse_case(raw)
    findings = memory.check_placement(case, memory.standing_placement(case))
    if findings:
        raise memory.CaseError(f"{case.name}: invalid standing contract: "
                               + "; ".join(findings))
    sides: dict[str, dict[str, Any]] = {}
    for label, layer in (("alignment_only", None), ("representable", base_refusal)):
        exact = memory.solve_exact(case, work_budget, legal_base=layer)
        replay = (memory.verify_optimality(case, exact, work_budget, legal_base=layer)
                  if exact["status"] == "optimal" else None)
        sides[label] = {"exact": exact, "optimality_replay": replay}
    rows: list[ArenaRow] = []
    errors: list[str] = []
    for arena in case.arenas:
        plain = _side(case, arena, sides["alignment_only"]["exact"],
                      sides["alignment_only"]["optimality_replay"], representable=False)
        exact = _side(case, arena, sides["representable"]["exact"],
                      sides["representable"]["optimality_replay"], representable=True)
        both = plain["status"] == "optimal" and exact["status"] == "optimal"
        cost = (exact["best_span"] - plain["best_span"]
                if both and exact["best_span"] is not None
                and plain["best_span"] is not None else None)
        rows.append(ArenaRow(
            arena=arena.id, owner=arena.owner,
            charged_load=memory.peak_load(case, arena.id),
            alignment_only=plain, representable=exact,
            representability_span_cost=cost,
            representability_cost_status="both-optimal" if both else "bounded-only",
            exact_length_refusals=[refusal for obj in case.objects
                                   if obj.arena == arena.id
                                   and (refusal := length_refusal(obj)) is not None]))
        errors.extend(_arena_findings(case.name, rows[-1], plain, exact, cost))
    for label, side in sides.items():
        replay = side["optimality_replay"]
        if replay is not None and replay["status"] == "rejected":
            errors.append(f"{case.name} {label}: independent optimality replay rejected")
        if side["exact"]["status"] == "infeasible":
            errors.append(f"{case.name} {label}: no legal placement exists in this arena set")
    return {"contract": raw, "contract_sha256": memory.contract_hash(case),
            "arenas": rows, "errors": errors,
            "alignment_only": sides["alignment_only"],
            "representable": sides["representable"]}


def _arena_findings(name: str, row: ArenaRow, plain: SideRow, exact: SideRow,
                    cost: int | None) -> list[str]:
    """The invariants a run of this experiment is allowed to fail on.

    An unsound bound is the one that matters: a lower bound above a span an exhaustive
    search reached is a defect in the bound and not a result about the layout.
    """
    findings: list[str] = []
    for label, side in (("alignment-only", plain), ("representability", exact)):
        span = side["best_span"]
        if (side["status"] == "optimal" and span is not None
                and side["stacked_lower_bound"] > span):
            findings.append(f"{name} {row['arena']}: the {label} stacked lower bound "
                            f"{side['stacked_lower_bound']} exceeds an exhaustive "
                            f"optimum of {span}")
        if span is not None and side["stacked_lower_bound"] < row["charged_load"]:
            findings.append(f"{name} {row['arena']}: the {label} stacked lower bound "
                            f"fell below the charged load")
    if cost is not None and cost < 0:
        findings.append(f"{name} {row['arena']}: restricting the legal bases produced "
                        f"a smaller optimum, which no restriction can do")
    return findings


def _contract(name: str, note: str, arenas: tuple[tuple[str, str, int], ...],
              rows: tuple[tuple[str, str, int, int, int, int, int], ...]) -> dict[str, Any]:
    """One declared fixture from (id, arena, size, alignment, base, start, reuse) rows.

    Completion milestones are the reuse time throughout: these fixtures exist to move
    bases, and they make no claim about a containment barrier or a sweep.
    """
    objects = [{"id": identifier, "arena": arena, "size": size, "payload": size,
                "alignment": alignment, "base": base, "start": start,
                "payload_end": reuse, "authority_end": reuse, "sweep_end": reuse,
                "reuse": reuse}
               for identifier, arena, size, alignment, base, start, reuse in rows]
    raw: dict[str, Any] = {
        "name": name, "mode": "single-fixed-trace",
        "provenance": "synthetic representability fixture; no measured product roster",
        "note": note,
        "arenas": [{"id": identifier, "owner": owner, "capacity": capacity}
                   for identifier, owner, capacity in arenas],
        "objects": objects}
    case = memory.parse_case(raw)
    findings = memory.check_placement(case, memory.standing_placement(case))
    if findings:
        raise memory.CaseError(f"{name}: invalid standing fixture: " + "; ".join(findings))
    return raw


def families() -> list[dict[str, Any]]:
    """Small declared families that straddle the exactness threshold.

    The corpus witnesses are all below it, where the granule is one byte and this layer
    asks for nothing, so a fixture that reaches past it is what makes the cost of
    representability visible at all. Each is small enough that both models finish, which
    is what lets the two optima be compared rather than two cutoffs.
    """
    return [
        _contract("repr-threshold-pin",
                  "one object just past the exactness threshold beside a coarsely "
                  "aligned neighbour that occupies the origin",
                  (("arena", "owner", 512),),
                  (("pin", "arena", 3, 128, 0, 0, 4),
                   ("wide", "arena", 129, 1, 3, 0, 4))),
        _contract("repr-coarse-granule",
                  "an extent whose granule is several bytes wide, pushed off the origin "
                  "by a neighbour it cannot be stacked under",
                  (("arena", "owner", 4096),),
                  (("pin", "arena", 3, 1024, 0, 0, 4),
                   ("block", "arena", 1025, 1, 3, 0, 4))),
        _contract("repr-already-quantized",
                  "two extents their own granules already divide, laid at bases those "
                  "granules already divide",
                  (("arena", "owner", 2048),),
                  (("block", "arena", 1024, 1, 0, 0, 4),
                   ("tail", "arena", 256, 1, 1024, 0, 4))),
        _contract("repr-length-only",
                  "sequential reuse of one extent whose length is inexact and whose "
                  "base is not",
                  (("arena", "owner", 512),),
                  (("early", "arena", 129, 1, 0, 0, 2),
                   ("late", "arena", 129, 1, 0, 2, 4))),
        _contract("repr-two-arenas",
                  "one arena paying for representability beside one that does not, so "
                  "neither arena's bytes can pay for the other's",
                  (("hot", "hot-owner", 512), ("cold", "cold-owner", 2048)),
                  (("pin", "hot", 3, 128, 0, 0, 4),
                   ("wide", "hot", 129, 1, 3, 0, 4),
                   ("resident", "cold", 1024, 1, 0, 0, 4))),
    ]


def q5_agreement(root: Path) -> dict[str, Any]:
    """Decide every region of the exported plan twice and require the two to agree.

    The memory plan multiplies a declared granule count back and this layer divides the
    base by the granule, so the two are different questions about the same region and
    agree exactly where the declared counts are the region's own. A disagreement is a
    finding about the plan or about this layer and is reported as one; an export with no
    region is a reader that has stopped reading, and is refused rather than reported as
    agreement over nothing.
    """
    plan = memplan.plan_of(memplan.read(root), memplan.STANDING)
    regions = tuple(plan.regions())
    if not regions:
        raise memory.CaseError(f"{memplan.SOURCE}'s {memplan.STANDING} exports no region; "
                               f"there is nothing to cross-check against")
    rows: list[AgreementRow] = []
    findings: list[str] = []
    for region in regions:
        length = plan.length_of(region)
        if length < 1:
            raise memory.CaseError(f"region {region} of {memplan.STANDING} has no "
                                   f"positive length to derive a granule from")
        granule = granule_of_size(length)
        here_base = base_refusal(probe(f"r{region}", length), plan.base_of(region)) is None
        here_length = length_refusal(probe(f"r{region}", length)) is None
        there_base = memplan.base_is_quantized(plan, region)
        there_length = memplan.length_is_quantized(plan, region)
        rows.append(AgreementRow(
            region=region, length=length, base=plan.base_of(region), granule=granule,
            declared_base_granules=plan.base_granules_of(region),
            declared_length_granules=plan.length_granules_of(region),
            base_legal_here=here_base, base_quantized_there=there_base,
            length_legal_here=here_length, length_quantized_there=there_length))
        if here_base != there_base:
            findings.append(f"region {region}: this layer and `base_is_quantized` "
                            f"disagree about base {plan.base_of(region)}")
        if here_length != there_length:
            findings.append(f"region {region}: this layer and `length_is_quantized` "
                            f"disagree about length {length}")
    return {"plan": plan.name, "source": memplan.SOURCE, "regions": rows,
            "findings": findings,
            "scope": "the standing exported plan's own regions; the search's candidate "
                     "grid, island containment and the rest of the plan's checks are "
                     "memplan's and are not decided here"}


def report(root: Path, source_revision: str = "unspecified",
           work_budget: int = WORK_BUDGET) -> dict[str, Any]:
    """Replay every witness and fixture under both models, with the Q5 cross-check."""
    if not isinstance(source_revision, str) or not source_revision.strip():
        raise memory.CaseError("source-revision: a nonempty input identity is required")
    contracts = [*witnesses.corpus(source_revision), *families()]
    items = [compare_case(raw, work_budget) for raw in contracts]
    agreement = q5_agreement(root)
    errors = [finding for item in items for finding in item["errors"]]
    errors.extend(f"Q5 cross-check: {finding}" for finding in agreement["findings"])
    sources = (GENERATOR, "tools/vos/static_memory.py", "tools/vos/memplan.py",
               memplan.SOURCE)
    reproducible = {
        "schema": VERSION, "source_revision": source_revision,
        "sources_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                           for name in sources},
        "settings": {"work_budget": work_budget,
                     "exact_max_objects_per_arena": memory.MAX_EXACT_OBJECTS,
                     "max_stacked_objects": MAX_STACKED_OBJECTS,
                     "granule_owner": "memplan.representable_granule",
                     "size_units": "synthetic bytes", "time_units": "ordinal ticks"},
        "cases": items, "q5_agreement": agreement}
    encoded = json.dumps(reproducible, sort_keys=True, separators=(",", ":"))
    return {
        "scope": "finite host research over one declared representability rule; "
                 "no target admission and no capability-format claim",
        "errors": errors, "reproducible": reproducible,
        "result_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "open_obligations": [
            "island containment and the island map, which the memory plan owns",
            "bank selection, which the plan reads only as an island map",
            "the encoding's own exponent range and mantissa-derived checks",
            "sealing, object types and the permission lattice",
            "admission itself, which no research receipt performs",
        ]}
