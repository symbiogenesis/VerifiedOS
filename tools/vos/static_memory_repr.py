# SPDX-License-Identifier: Apache-2.0
"""Representability-granule placement layer for static-memory research contracts.

Evaluates static-memory contracts under three models:
- `alignment_only`: alignment constraints without CHERI representability granules.
- `representable`: alignment plus R-15-007c base-granule quantization (`memplan.representable_granule`).
- `quantized_lengths`: R-15-007k granule-quantized extents and base-granule quantization.

See [representability.md](../../docs/implementation/static-memory/representability.md).
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

WORK_BUDGET = 200_000

# Skip exponential subset-stacking bound when an instant has more than 14 live objects.
MAX_STACKED_OBJECTS = 14

# Fixed-point iteration cap for `quantized_size`.
MAX_QUANTIZE_STEPS = 4


class Refusal(TypedDict):
    """An object whose charged extent is not a multiple of its representability granule."""

    id: str
    arena: str
    size: int
    granule: int
    quantized_size: int
    padding_bytes: int


class SideRow(TypedDict):
    """Placement result and lower bound for one arena under one model."""

    best_span: int | None
    status: str
    certificate: dict[str, Any] | None
    replay_status: str | None
    stacked_lower_bound: int
    span_over_stacked_bound: int | None


class ArenaRow(TypedDict):
    """Comparison of `alignment_only`, `representable`, and `quantized_lengths` for one arena."""

    arena: str
    owner: str
    charged_load: int
    alignment_only: SideRow
    representable: SideRow
    quantized_lengths: SideRow
    representability_span_cost: int | None
    representability_cost_status: str
    quantized_length_span_cost: int | None
    quantized_length_cost_status: str
    exact_length_refusals: list[Refusal]


class AgreementRow(TypedDict):
    """Cross-check row comparing this module's predicates with `memplan`'s for one region."""

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
    """Round `value` up to the nearest multiple of positive `step`."""
    if step < 1:
        raise memory.CaseError("a legal-position step must be a positive integer")
    return ((value + step - 1) // step) * step


def granule_of_size(size: int) -> int:
    """Return R-15-007c's representability granule for positive `size` via `memplan`."""
    if type(size) is not int or size < 1:
        raise memory.CaseError("a charged extent must be a positive integer")
    return memplan.representable_granule(size)


def base_refusal(obj: memory.Object, base: int) -> str | None:
    """Return a refusal string if `base` is not a multiple of `obj`'s granule, else `None`."""
    granule = granule_of_size(obj.size)
    if base % granule:
        return (f"representable: {obj.id} base {base} is no whole number of its "
                f"{granule}-byte granule")
    return None


def probe(identifier: str, size: int) -> memory.Object:
    """Construct a minimal `memory.Object` with `id=identifier` and `size=size`."""
    return memory.Object(identifier, "probe", size, size, 1, 0, 0, 0, 0, 1, 0)


def length_refusal(obj: memory.Object) -> Refusal | None:
    """Return a `Refusal` if `obj.size` is not a multiple of its granule, else `None`."""
    granule = granule_of_size(obj.size)
    if obj.size % granule == 0:
        return None
    quantized = quantized_size(obj.size)
    return Refusal(id=obj.id, arena=obj.arena, size=obj.size, granule=granule,
                   quantized_size=quantized, padding_bytes=quantized - obj.size)


def quantized_size(size: int) -> int:
    """Return the least extent `>= size` that is a multiple of its own granule."""
    extent = size
    for _ in range(MAX_QUANTIZE_STEPS):
        granule = granule_of_size(extent)
        if extent % granule == 0:
            return extent
        extent = _round_up(extent, granule)
    raise memory.CaseError(f"no quantized extent at or above {size} within "
                           f"{MAX_QUANTIZE_STEPS} steps of its own granule")


def step_of(obj: memory.Object, *, representable: bool) -> int:
    """Return the base alignment step for `obj` (`alignment` or `lcm(alignment, granule)`)."""
    if not representable:
        return obj.alignment
    return lcm(obj.alignment, granule_of_size(obj.size))


def stacked_bound(objects: Sequence[memory.Object], *, representable: bool) -> int | None:
    """Compute the minimum span of any disjoint stacking of `objects` via subset DP."""
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
    """Compute a lower bound on `arena_id`'s span from peak load and per-instant `stacked_bound`."""
    load = memory.peak_load(case, arena_id)
    objects = [obj for obj in case.objects if obj.arena == arena_id]
    bound = load
    for time in sorted({obj.start for obj in objects}):
        live = [obj for obj in objects if obj.start <= time < obj.reuse]
        stacked = stacked_bound(live, representable=representable)
        if stacked is not None and stacked > bound:
            bound = stacked
    return bound


def quantized_contract(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of contract `raw` with every object's `size` rounded to `quantized_size`."""
    objects = [dict(obj) | {"size": quantized_size(obj["size"])} for obj in raw["objects"]]
    return dict(raw) | {"name": f"{raw['name']}-quantized-lengths", "objects": objects}


def _side(case: memory.Case, arena: memory.Arena, side: dict[str, Any], *,
          representable: bool) -> SideRow:
    row = next(item for item in side["exact"]["arenas"] if item["arena"] == arena.id)
    replay = side["optimality_replay"]
    span = row["best_span"]
    bound = arena_lower_bound(case, arena.id, representable=representable)
    return SideRow(best_span=span, status=row["status"], certificate=row["certificate"],
                   replay_status=None if replay is None else replay["status"],
                   stacked_lower_bound=bound,
                   span_over_stacked_bound=None if span is None else span - bound)


def _cost(lower: SideRow, upper: SideRow) -> tuple[int | None, str]:
    """Return `(upper_span - lower_span, status)` when both runs reached optimality."""
    spans = (lower["best_span"], upper["best_span"])
    if (lower["status"] == "optimal" and upper["status"] == "optimal"
            and spans[0] is not None and spans[1] is not None):
        return spans[1] - spans[0], "both-optimal"
    return None, "bounded-only"


def compare_case(raw: dict[str, Any], work_budget: int = WORK_BUDGET) -> dict[str, Any]:
    """Solve contract `raw` under the three models and compare arena spans."""
    case = memory.parse_case(raw)
    findings = memory.check_placement(case, memory.standing_placement(case))
    if findings:
        raise memory.CaseError(f"{case.name}: invalid standing contract: "
                               + "; ".join(findings))
    grown_case = memory.parse_case(quantized_contract(raw))
    models: tuple[tuple[str, memory.Case, memory.LegalBase | None, bool], ...] = (
        ("alignment_only", case, None, False),
        ("representable", case, base_refusal, True),
        ("quantized_lengths", grown_case, base_refusal, True))
    sides: dict[str, dict[str, Any]] = {}
    for label, subject, layer, _ in models:
        exact = memory.solve_exact(subject, work_budget, legal_base=layer)
        replay = (memory.verify_optimality(subject, exact, work_budget, legal_base=layer)
                  if exact["status"] == "optimal" else None)
        sides[label] = {"exact": exact, "optimality_replay": replay,
                        "contract_sha256": memory.contract_hash(subject)}
    rows: list[ArenaRow] = []
    errors: list[str] = []
    for arena in case.arenas:
        decided = {label: _side(subject, arena, sides[label], representable=representable)
                   for label, subject, _, representable in models}
        plain, exact = decided["alignment_only"], decided["representable"]
        grown = decided["quantized_lengths"]
        cost, cost_status = _cost(plain, exact)
        length_cost, length_status = _cost(exact, grown)
        rows.append(ArenaRow(
            arena=arena.id, owner=arena.owner,
            charged_load=memory.peak_load(case, arena.id),
            alignment_only=plain, representable=exact, quantized_lengths=grown,
            representability_span_cost=cost,
            representability_cost_status=cost_status,
            quantized_length_span_cost=length_cost,
            quantized_length_cost_status=length_status,
            exact_length_refusals=[refusal for obj in case.objects
                                   if obj.arena == arena.id
                                   and (refusal := length_refusal(obj)) is not None]))
        errors.extend(_arena_findings(case.name, rows[-1]))
    for label, side in sides.items():
        replay = side["optimality_replay"]
        if replay is not None and replay["status"] == "rejected":
            errors.append(f"{case.name} {label}: independent optimality replay rejected")
        if side["exact"]["status"] == "infeasible":
            errors.append(f"{case.name} {label}: no legal placement exists in this arena set")
    return {"contract": raw, "contract_sha256": memory.contract_hash(case),
            "quantized_contract_sha256": sides["quantized_lengths"]["contract_sha256"],
            "arenas": rows, "errors": errors,
            "alignment_only": sides["alignment_only"],
            "representable": sides["representable"],
            "quantized_lengths": sides["quantized_lengths"]}


def _arena_findings(name: str, row: ArenaRow) -> list[str]:
    """Check lower-bound soundness and monotonicity across the three models for `row`."""
    findings: list[str] = []
    for label, side in (("alignment-only", row["alignment_only"]),
                        ("representability", row["representable"]),
                        ("quantized-length", row["quantized_lengths"])):
        span = side["best_span"]
        if (side["status"] == "optimal" and span is not None
                and side["stacked_lower_bound"] > span):
            findings.append(f"{name} {row['arena']}: the {label} stacked lower bound "
                            f"{side['stacked_lower_bound']} exceeds an exhaustive "
                            f"optimum of {span}")
    if (row["representability_span_cost"] or 0) < 0:
        findings.append(f"{name} {row['arena']}: restricting the legal bases produced "
                        f"a smaller optimum, which no restriction can do")
    if (row["quantized_length_span_cost"] or 0) < 0:
        findings.append(f"{name} {row['arena']}: growing every extent to its own granule "
                        f"produced a smaller optimum, which a growth under a granule no "
                        f"finer cannot do")
    return findings


def _contract(name: str, note: str, arenas: tuple[tuple[str, str, int], ...],
              rows: tuple[tuple[str, str, int, int, int, int, int], ...]) -> dict[str, Any]:
    """Build and validate a synthetic representability fixture contract."""
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
    """Return synthetic fixtures exercising extents across the 128-byte granule threshold."""
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
        _contract("repr-bound-is-loose",
                  "an object living across two instants whose base must serve the later "
                  "instant's aligned neighbour, so the earlier instant's tightest stack "
                  "is unreachable and the one-instant bound falls short of the optimum",
                  (("arena", "owner", 32),),
                  (("bridge", "arena", 2, 4, 4, 1, 4),
                   ("early-wide", "arena", 3, 4, 0, 1, 2),
                   ("early-filler", "arena", 2, 1, 6, 1, 2),
                   ("late", "arena", 4, 4, 0, 3, 6))),
    ]


def q5_agreement(root: Path) -> dict[str, Any]:
    """Cross-check base and length quantization predicates against `memplan` on `STANDING`."""
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
    """Replay every witness and fixture under each model, with the Q5 cross-check."""
    if not isinstance(source_revision, str) or not source_revision.strip():
        raise memory.CaseError("source-revision: a nonempty input identity is required")
    contracts = [*witnesses.corpus(source_revision), *families()]
    items = [compare_case(raw, work_budget) for raw in contracts]
    agreement = q5_agreement(root)
    errors = [finding for item in items for finding in item["errors"]]
    errors.extend(f"Q5 cross-check: {finding}" for finding in agreement["findings"])
    sources = (GENERATOR, "tools/vos/static_memory.py", "tools/vos/static_memory_corpus.py",
               "tools/vos/memplan.py",
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
