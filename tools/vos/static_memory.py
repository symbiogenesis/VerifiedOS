# SPDX-License-Identifier: Apache-2.0
"""Bounded research layouts, independently checked witnesses and replayable optima.

This model is a fixed trace, with integer byte addresses relative to each immutable
arena. An object reserves its entire contiguous extent on [start, reuse), including
retained authority, quarantine and initialization. Placement changes bases alone.
The lifetime milestones are supplied assumptions, not evidence of a real barrier.
Alignment is an input constraint; it does not certify CHERI bounds or admission.

Search is deliberately small and untrusted. A witness goes through the separate
checker; an optimum additionally needs the independently computed load bound or a
Cartesian replay at the preceding height. Exhaustion of a work budget is unfinished
research, never infeasibility. No search changes the input or writes a plan.
"""

import hashlib
import itertools
import json
from dataclasses import asdict, dataclass
from typing import Any

MAX_EXACT_OBJECTS = 12
METHODS: tuple[str, ...] = ("first-fit-start", "first-fit-size", "first-fit-retention")


class CaseError(ValueError):
    """A research contract is malformed or requests an unsupported shape."""


@dataclass(frozen=True)
class Arena:
    id: str
    owner: str
    capacity: int


@dataclass(frozen=True)
class Object:
    id: str
    arena: str
    size: int
    payload: int
    alignment: int
    start: int
    payload_end: int
    authority_end: int
    sweep_end: int
    reuse: int
    base: int


@dataclass(frozen=True)
class Case:
    name: str
    provenance: str
    mode: str
    arenas: tuple[Arena, ...]
    objects: tuple[Object, ...]


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise CaseError(f"{label}: expected an object with string keys")
    return value


def _fields(value: dict[str, Any], names: set[str], label: str) -> None:
    if set(value) != names:
        raise CaseError(f"{label}: missing {sorted(names - set(value))}; "
                        f"unknown {sorted(set(value) - names)}")


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CaseError(f"{label}: expected a nonempty string")
    return value


def _integer(value: object, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise CaseError(f"{label}: expected an integer >= {minimum}")
    return value


def parse_case(raw: object) -> Case:
    """Read the model once; allow documentary root metadata, never unknown constraints.

    Root metadata is deliberately outside the mathematical contract. Object and arena
    fields are exact, so a supplied pin, bank or authority constraint cannot disappear
    silently. Invalid standing bases are checker findings rather than parse failures.
    """
    data = _mapping(raw, "case")
    name = _string(data.get("name"), "case.name")
    provenance = _string(data.get("provenance"), "case.provenance")
    mode = _string(data.get("mode"), "case.mode")
    if not isinstance(data.get("arenas"), list) or not data["arenas"]:
        raise CaseError("case.arenas: expected a nonempty list")
    if not isinstance(data.get("objects"), list):
        raise CaseError("case.objects: expected a list")
    arenas: list[Arena] = []
    for i, raw_arena in enumerate(data["arenas"]):
        label = f"arenas[{i}]"
        arena = _mapping(raw_arena, label)
        _fields(arena, {"id", "owner", "capacity"}, label)
        arenas.append(Arena(_string(arena["id"], f"{label}.id"),
                            _string(arena["owner"], f"{label}.owner"),
                            _integer(arena["capacity"], f"{label}.capacity", 1)))
    arena_ids = {a.id for a in arenas}
    if len(arena_ids) != len(arenas):
        raise CaseError("case.arenas: duplicate id")
    objects: list[Object] = []
    fields = {"id", "arena", "size", "payload", "alignment", "start", "payload_end",
              "authority_end", "sweep_end", "reuse", "base"}
    for i, raw_object in enumerate(data["objects"]):
        label = f"objects[{i}]"
        obj = _mapping(raw_object, label)
        _fields(obj, fields, label)
        identifier = _string(obj["id"], f"{label}.id")
        arena_id = _string(obj["arena"], f"{label}.arena")
        if arena_id not in arena_ids:
            raise CaseError(f"{label}.arena: unknown arena {arena_id}")
        nums = {key: _integer(obj[key], f"{label}.{key}",
                             1 if key in {"size", "alignment"} else 0)
                for key in fields - {"id", "arena"}}
        if nums["payload"] > nums["size"]:
            raise CaseError(f"{label}: payload exceeds physical size")
        lifetime = [nums[key] for key in ("start", "payload_end", "authority_end",
                                         "sweep_end", "reuse")]
        if lifetime != sorted(lifetime) or lifetime[0] == lifetime[-1]:
            raise CaseError(f"{label}: require start <= payload_end <= authority_end "
                            "<= sweep_end <= reuse and start < reuse")
        objects.append(Object(identifier, arena_id, nums["size"], nums["payload"],
                              nums["alignment"], nums["start"], nums["payload_end"],
                              nums["authority_end"], nums["sweep_end"], nums["reuse"],
                              nums["base"]))
    if len({o.id for o in objects}) != len(objects):
        raise CaseError("case.objects: duplicate id")
    return Case(name, provenance, mode, tuple(arenas), tuple(objects))


def contract_hash(case: Case) -> str:
    """Bind a receipt to all parsed contract fields, including its standing plan."""
    encoded = json.dumps(asdict(case), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def standing_placement(case: Case) -> list[dict[str, Any]]:
    return [{"id": o.id, "arena": o.arena, "base": o.base} for o in case.objects]


def check_placement(case: Case, placement: object) -> list[str]:
    """Check only an offset certificate against the unchanged lifecycle contract.

    This does not call the search's conflict predicates or trust its objective. Reject
    extra fields instead of accepting a candidate's altered sizes, owners or barriers.
    Event ordering is half-open: release at reuse precedes an allocation at that time.
    """
    if not isinstance(placement, list):
        return ["schema: placement must be a list"]
    errors: list[str] = []
    by_id: dict[str, dict[str, Any]] = {}
    expected = {o.id for o in case.objects}
    capacities = {a.id: a.capacity for a in case.arenas}
    for i, raw in enumerate(placement):
        try:
            row = _mapping(raw, f"placement[{i}]")
            _fields(row, {"id", "arena", "base"}, f"placement[{i}]")
            identifier = _string(row["id"], f"placement[{i}].id")
            _string(row["arena"], f"placement[{i}].arena")
            _integer(row["base"], f"placement[{i}].base")
        except CaseError as error:
            errors.append(f"schema: {error}")
            continue
        if identifier in by_id:
            errors.append(f"identity: duplicate object {identifier}")
        if identifier not in expected:
            errors.append(f"identity: unknown object {identifier}")
        by_id[identifier] = row
    for obj in case.objects:
        row = by_id.get(obj.id)
        if row is None:
            errors.append(f"identity: missing object {obj.id}")
            continue
        if row["arena"] != obj.arena:
            errors.append(f"ownership: {obj.id} cannot change arena {obj.arena}")
        if row["base"] % obj.alignment:
            errors.append(f"alignment: {obj.id} base is not a multiple of {obj.alignment}")
        if row["base"] + obj.size > capacities[obj.arena]:
            errors.append(f"capacity: {obj.id} exceeds arena {obj.arena}")
    for i, left in enumerate(case.objects):
        if left.id not in by_id:
            continue
        for right in case.objects[i + 1:]:
            if right.id not in by_id or left.arena != right.arena:
                continue
            if max(left.start, right.start) >= min(left.reuse, right.reuse):
                continue
            lb, rb = by_id[left.id]["base"], by_id[right.id]["base"]
            if max(lb, rb) < min(lb + left.size, rb + right.size):
                errors.append(f"overlap: {left.id}/{right.id} share bytes before safe reuse")
    return errors


def peak_load(case: Case, arena_id: str) -> int:
    """Charged physical load through safe reuse, independently of chosen bases."""
    if arena_id not in {a.id for a in case.arenas}:
        raise CaseError(f"unknown arena {arena_id}")
    events: dict[int, int] = {}
    for obj in case.objects:
        if obj.arena == arena_id:
            events[obj.start] = events.get(obj.start, 0) + obj.size
            events[obj.reuse] = events.get(obj.reuse, 0) - obj.size
    current = peak = 0
    for time in sorted(events):
        current += events[time]
        peak = max(peak, current)
    return peak


def placement_spans(case: Case, placement: list[dict[str, Any]]) -> dict[str, int]:
    """Maximum endpoint from each arena origin, not a fungible global capacity."""
    findings = check_placement(case, placement)
    if findings:
        raise CaseError("invalid placement: " + "; ".join(findings))
    sizes = {o.id: o.size for o in case.objects}
    return {a.id: max((row["base"] + sizes[row["id"]] for row in placement
                       if row["arena"] == a.id), default=0) for a in case.arenas}


def _interferes(left: Object, right: Object) -> bool:
    return left.start < right.reuse and right.start < left.reuse


@dataclass
class _Budget:
    limit: int
    nodes: int = 0

    def step(self) -> bool:
        if self.nodes >= self.limit:
            return False
        self.nodes += 1
        return True


def _fit_at_height(objects: tuple[Object, ...], height: int,
                   budget: _Budget) -> tuple[str, dict[str, int] | None]:
    """Complete aligned integer DFS; count every root and considered base."""
    if not budget.step():
        return "incomplete", None
    order = sorted(objects, key=lambda o: (-sum(_interferes(o, p) for p in objects
                                               if o.id != p.id), -o.size, o.id))
    chosen: list[tuple[Object, int]] = []

    def visit(index: int) -> tuple[str, dict[str, int] | None]:
        if index == len(order):
            return "feasible", {obj.id: base for obj, base in chosen}
        obj = order[index]
        for base in range(0, height - obj.size + 1, obj.alignment):
            if not budget.step():
                return "incomplete", None
            if any(_interferes(obj, prev) and base < offset + prev.size
                   and offset < base + obj.size for prev, offset in chosen):
                continue
            chosen.append((obj, base))
            status, result = visit(index + 1)
            chosen.pop()
            if status != "infeasible":
                return status, result
        return "infeasible", None

    return visit(0)


def solve_exact(case: Case, work_budget: int = 100_000) -> dict[str, Any]:
    """Minimize each arena's span by bounded enumeration; preserve standing on cutoff.

    At most MAX_EXACT_OBJECTS per arena are enumerated. All capacities and alignments
    remain arbitrary positive integers; enumerating their numeric ranges is knowingly
    pseudopolynomial and says nothing about parameterized complexity. `nodes` counts
    search roots and candidate bases, not wall time or validation cost.
    """
    budget = _Budget(_integer(work_budget, "work_budget"))
    standing = standing_placement(case)
    standing_findings = check_placement(case, standing)
    standing_valid = not standing_findings
    selected: dict[str, int] = {}
    results: list[dict[str, Any]] = []
    for arena in case.arenas:
        objects = tuple(o for o in case.objects if o.arena == arena.id)
        subcase = Case(case.name, case.provenance, case.mode, (arena,), objects)
        substanding = standing_placement(subcase)
        valid = not check_placement(subcase, substanding)
        best = {o.id: o.base for o in objects} if valid else None
        best_span = max((o.base + o.size for o in objects), default=0) if valid else None
        lower = peak_load(case, arena.id)
        result: dict[str, Any] = {
            "arena": arena.id, "owner": arena.owner, "lower_bound": lower,
            "best_span": best_span, "remaining_gap": None, "status": "incomplete",
            "certificate": None, "attempts": [],
        }
        if best_span == lower:
            result["status"] = "optimal"
            result["certificate"] = {"method": "load-equality", "infeasible_through": None}
        elif lower > arena.capacity:
            result["status"] = "infeasible"
            result["certificate"] = {"method": "load-exceeds-capacity",
                                     "infeasible_through": arena.capacity}
        elif len(objects) > MAX_EXACT_OBJECTS:
            result["reason"] = f"more than {MAX_EXACT_OBJECTS} objects in this arena"
        else:
            upper = best_span if best_span is not None else arena.capacity
            for height in range(lower, upper + 1):
                # A standing witness at this height needs no repeated search.
                if best_span == height:
                    result["status"] = "optimal"
                    result["certificate"] = {"method": "exhaustive",
                                             "infeasible_through": height - 1}
                    break
                before = budget.nodes
                status, found = _fit_at_height(objects, height, budget)
                result["attempts"].append({"height": height, "status": status,
                                           "nodes": budget.nodes - before})
                if status == "incomplete":
                    result["reason"] = "work budget exhausted"
                    break
                if status == "feasible":
                    if found is None:
                        raise RuntimeError("feasible search returned no witness")
                    best, best_span = found, height
                    result["status"] = "optimal"
                    result["certificate"] = {
                        "method": "load-equality" if height == lower else "exhaustive",
                        "infeasible_through": None if height == lower else height - 1,
                    }
                    break
            else:
                result["status"] = "infeasible"
                result["certificate"] = {"method": "exhaustive",
                                         "infeasible_through": arena.capacity}
        if best is not None:
            selected.update(best)
        result["best_span"] = best_span
        result["remaining_gap"] = best_span - lower if best_span is not None else None
        results.append(result)
    statuses = {r["status"] for r in results}
    status = "infeasible" if "infeasible" in statuses else (
        "incomplete" if "incomplete" in statuses else "optimal")
    best_placement = [{"id": o.id, "arena": o.arena, "base": selected[o.id]}
                      for o in case.objects] if len(selected) == len(case.objects) else None
    if best_placement is not None and check_placement(case, best_placement):
        raise RuntimeError("search witness failed the independent placement checker")
    retained = status == "incomplete" and standing_valid
    return {"case": case.name, "contract_sha256": contract_hash(case), "status": status,
            "work_budget": budget.limit, "nodes": budget.nodes,
            "standing_valid": standing_valid, "standing_findings": standing_findings,
            "standing_preserved": retained,
            "placement": standing if retained else best_placement,
            "best_placement": best_placement, "arenas": results}


def compare_heuristics(case: Case, work_budget: int = 100_000) -> list[dict[str, Any]]:
    """Deterministic first fit at zero and aligned ends of interfering placed objects.

    A failed, interrupted or non-improving attempt retains a valid standing plan.
    Improvement means no arena gets larger and at least one gets smaller; bytes in
    distinct arenas cannot compensate one another. Every proposed witness is checked.
    """
    _integer(work_budget, "work_budget")
    standing = standing_placement(case)
    valid = not check_placement(case, standing)
    standing_spans = placement_spans(case, standing) if valid else None
    reports: list[dict[str, Any]] = []
    for method in METHODS:
        budget = _Budget(work_budget)
        placed: list[tuple[Object, int]] = []
        status = "feasible"
        for arena in case.arenas:
            objects = [o for o in case.objects if o.arena == arena.id]
            if method == "first-fit-start":
                order = sorted(objects, key=lambda o: (o.start, o.id))
            elif method == "first-fit-size":
                order = sorted(objects, key=lambda o: (-o.size, o.start, o.id))
            else:
                order = sorted(objects, key=lambda o: (o.start - o.reuse, -o.size, o.id))
            for obj in order:
                conflicts = [(prev, base) for prev, base in placed
                             if prev.arena == arena.id and _interferes(obj, prev)]
                endpoints = {0} | {((base + prev.size + obj.alignment - 1)
                                   // obj.alignment) * obj.alignment
                                  for prev, base in conflicts}
                found: int | None = None
                for base in sorted(endpoints):
                    if not budget.step():
                        status = "incomplete"
                        break
                    if base + obj.size <= arena.capacity and not any(
                            base < offset + prev.size and offset < base + obj.size
                            for prev, offset in conflicts):
                        found = base
                        break
                if found is None:
                    if status != "incomplete":
                        status = "no-fit"
                    break
                placed.append((obj, found))
            if status != "feasible":
                break
        candidate: list[dict[str, Any]] | None = None
        spans: dict[str, int] | None = None
        if status == "feasible":
            offsets = {obj.id: base for obj, base in placed}
            candidate = [{"id": o.id, "arena": o.arena, "base": offsets[o.id]}
                         for o in case.objects]
            spans = placement_spans(case, candidate)
        improved = spans is not None and (standing_spans is None or (
            all(spans[k] <= standing_spans[k] for k in spans)
            and any(spans[k] < standing_spans[k] for k in spans)))
        preserve = valid and not improved
        reports.append({"method": method, "status": status, "nodes": budget.nodes,
                        "work_budget": budget.limit, "candidate": candidate,
                        "candidate_spans": spans, "standing_preserved": preserve,
                        "placement": standing if preserve else candidate,
                        "spans": standing_spans if preserve else spans})
    return reports


def verify_optimality(case: Case, receipt: object,
                      work_budget: int = 100_000) -> dict[str, Any]:
    """Check a witness and independently replay the prior height by Cartesian product.

    Replay deliberately does not call the DFS, its ordering, pruning or conflict test.
    Monotonicity in available height means infeasibility at h-1 covers every smaller
    height. Budget counts full candidate placements. The method can take more work
    than search. A cutoff leaves the optimality claim unchecked, even if feasible.
    """
    budget = _Budget(_integer(work_budget, "work_budget"))

    def answer(status: str, findings: list[str]) -> dict[str, Any]:
        return {"status": status, "findings": findings, "nodes": budget.nodes,
                "work_budget": budget.limit}

    try:
        report = _mapping(receipt, "receipt")
        if report.get("contract_sha256") != contract_hash(case):
            return answer("rejected", ["receipt does not bind this contract"])
        if report.get("status") != "optimal":
            return answer("rejected", ["receipt does not claim a complete feasible optimum"])
        witness = report.get("best_placement")
        findings = check_placement(case, witness)
        if findings:
            return answer("rejected", findings)
        if not isinstance(witness, list):
            return answer("rejected", ["receipt witness is not a list"])
        spans = placement_spans(case, witness)
        rows = report.get("arenas")
        if not isinstance(rows, list) or len(rows) != len(case.arenas):
            return answer("rejected", ["receipt arenas do not match contract"])
        indexed: dict[str, dict[str, Any]] = {}
        for raw in rows:
            row = _mapping(raw, "receipt arena")
            identifier = _string(row.get("arena"), "receipt arena.id")
            if identifier in indexed:
                return answer("rejected", ["duplicate receipt arena"])
            indexed[identifier] = row
        if set(indexed) != {a.id for a in case.arenas}:
            return answer("rejected", ["receipt arena identities do not match contract"])
        for arena in case.arenas:
            row = indexed[arena.id]
            lower = peak_load(case, arena.id)
            height = spans[arena.id]
            reported_lower = _integer(row.get("lower_bound"), "receipt lower_bound")
            reported_height = _integer(row.get("best_span"), "receipt best_span")
            if (row.get("status") != "optimal" or reported_lower != lower
                    or reported_height != height):
                return answer("rejected", [f"{arena.id}: false span, bound or status"])
            certificate = _mapping(row.get("certificate"), "certificate")
            _fields(certificate, {"method", "infeasible_through"}, "certificate")
            if certificate["infeasible_through"] is not None:
                _integer(certificate["infeasible_through"], "certificate infeasible_through")
            if height == lower:
                if certificate != {"method": "load-equality", "infeasible_through": None}:
                    return answer("rejected", ["load equality certificate malformed"])
                continue
            if certificate != {"method": "exhaustive", "infeasible_through": height - 1}:
                return answer("rejected", ["exhaustive certificate must challenge exactly span - 1"])
            objects = tuple(o for o in case.objects if o.arena == arena.id)
            if len(objects) > MAX_EXACT_OBJECTS:
                return answer("incomplete", [f"{arena.id}: replay exceeds small-instance limit"])
            subcase = Case(case.name, case.provenance, case.mode, (arena,), objects)
            # itertools.product eagerly pools each range. Refuse oversized products
            # before building them; a byte-wide arena must not defeat a work budget.
            domains = [range(0, height - obj.size, obj.alignment) for obj in objects]
            counts = [max(0, (height - obj.size + obj.alignment - 1) // obj.alignment)
                      for obj in objects]
            if any(count == 0 for count in counts):
                continue
            if sum(counts) > budget.limit - budget.nodes:
                return answer("incomplete", [f"{arena.id}: Cartesian replay exceeds budget"])
            for bases in itertools.product(*domains):
                if not budget.step():
                    return answer("incomplete", [f"{arena.id}: replay work budget exhausted"])
                candidate = [{"id": obj.id, "arena": arena.id, "base": base}
                             for obj, base in zip(objects, bases, strict=True)]
                if not check_placement(subcase, candidate):
                    return answer("rejected", [f"{arena.id}: smaller feasible placement exists"])
    except CaseError as error:
        return answer("rejected", [str(error)])
    except OverflowError:
        return answer("incomplete", ["Cartesian replay exceeds interpreter range limits"])
    return answer("verified", [])
