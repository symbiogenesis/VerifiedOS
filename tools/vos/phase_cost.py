# SPDX-License-Identifier: Apache-2.0
"""Conservative arithmetic on declared Q22e workload costs, without qualification."""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from vos.jsonc import Json


@dataclass(frozen=True)
class Interval:
    low: int
    high: int

    def json(self) -> list[Json]:
        return [self.low, self.high]


type Bound = Interval | None


def add(*terms: Bound) -> Bound:
    if any(term is None for term in terms):
        return None
    known = [term for term in terms if term is not None]
    return Interval(sum(term.low for term in known), sum(term.high for term in known))


def subtract(left: Bound, right: Bound) -> Bound:
    if left is None or right is None:
        return None
    return Interval(left.low - right.high, left.high - right.low)


def multiply(count: int, value: Bound) -> Bound:
    if count == 0:
        return Interval(0, 0)
    return None if value is None else Interval(count * value.low, count * value.high)


def _json(value: Bound) -> Json:
    return None if value is None else value.json()


def _pairs(pairs: list[tuple[str, Json]]) -> dict[str, Json]:
    result: dict[str, Json] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError(f"non-JSON numeric constant: {value}")


def _object(value: Json, fields: set[str], where: str,
            required: set[str] | None = None) -> dict[str, Json]:
    if not isinstance(value, dict):
        raise TypeError(f"{where} must be an object")
    if unknown := set(value) - fields:
        raise ValueError(f"{where}: unknown fields {sorted(unknown)}")
    if absent := (fields if required is None else required) - set(value):
        raise ValueError(f"{where}: missing fields {sorted(absent)}")
    return value


def _name(value: Json, where: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f"{where} must be a nonempty string without edge whitespace")
    return value


def _integer(value: Json, where: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{where} must be an integer >= {minimum}")
    return value


def _bound(value: Json, where: str) -> Bound:
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"{where} must be [low, high] or null")
    low = _integer(value[0], where)
    high = _integer(value[1], where)
    if low > high:
        raise ValueError(f"{where}: lower bound exceeds upper bound")
    return Interval(low, high)


@dataclass(frozen=True)
class Costs:
    execution: Bound
    stalls: Bound
    trap_per_switch: Bound
    other: Bound

    def exclusive(self, switches: int) -> Bound:
        return add(self.execution, self.stalls, self.other,
                   multiply(switches, self.trap_per_switch))


@dataclass(frozen=True)
class Slot:
    name: str
    switches: int
    deadline: Bound
    baseline: Costs
    candidate: Costs


@dataclass(frozen=True)
class Comparison:
    workload: str
    domain_id: str
    schedule_id: str
    schedule_path: str
    schedule_sha256: str
    clock_id: str
    clock_hz: int
    slots: tuple[Slot, ...]
    fence_t: Bound
    d_pipe_completion: Bound
    vmclear: Bound
    opp_relock: Bound
    frame_budget: Bound
    baseline_area: Bound
    candidate_area: Bound
    area_budget: Bound
    baseline_power: Bound
    candidate_power: Bound
    power_budget: Bound


def _costs(value: Json, where: str) -> Costs:
    fields = ("execution", "stalls", "trap_per_switch", "other")
    data = _object(value, set(fields), where, set())
    return Costs(*(_bound(data.get(key), f"{where}.{key}") for key in fields))


def parse(raw: bytes) -> Comparison:
    """Parse strict JSON. Omitted numeric operands are unknown, never zero."""
    try:
        value = cast("Json", json.loads(raw, object_pairs_hook=_pairs, parse_constant=_constant))
    except RecursionError as err:
        raise ValueError("comparison JSON nesting exceeds the parser limit") from err
    data = _object(value, {"version", "workload", "domain", "schedule", "clock", "units", "slots",
                           "boundary", "budgets", "area", "power"}, "comparison")
    if _integer(data["version"], "version") != 1:
        raise ValueError("version must be 1")
    units = _object(data["units"], {"time", "area", "power"}, "units")
    if units != {"time": "cycles", "area": "um2", "power": "uW"}:
        raise ValueError("units must be time=cycles, area=um2, power=uW")
    clock = _object(data["clock"], {"id", "hz"}, "clock")
    domain = _object(data["domain"], {"id", "kind"}, "domain")
    if domain["kind"] != "serial":
        raise ValueError("domain.kind must be serial; parallel frame joins are unsupported")
    schedule = _object(data["schedule"], {"id", "path", "sha256"}, "schedule")
    digest = _name(schedule["sha256"], "schedule.sha256")
    if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("schedule.sha256 must be 64 lowercase hexadecimal characters")
    boundary = _object(data["boundary"], {"fence_t", "d_pipe_completion", "vmclear", "opp_relock"},
                       "boundary", set())
    budgets = _object(data["budgets"], {"frame", "area", "power"}, "budgets", set())
    area = _object(data["area"], {"baseline", "candidate"}, "area", set())
    power = _object(data["power"], {"baseline", "candidate"}, "power", set())
    if not isinstance(data["slots"], list) or not data["slots"]:
        raise ValueError("slots must be a nonempty list")
    slots: list[Slot] = []
    names: set[str] = set()
    for node in data["slots"]:
        slot = _object(node, {"id", "switches", "deadline", "baseline", "candidate"}, "slot",
                       {"id", "switches", "baseline", "candidate"})
        name = _name(slot["id"], "slot.id")
        if name in names:
            raise ValueError(f"duplicate slot identity: {name}")
        names.add(name)
        slots.append(Slot(name, _integer(slot["switches"], f"{name}.switches"),
                          _bound(slot.get("deadline"), f"{name}.deadline"),
                          _costs(slot["baseline"], f"{name}.baseline"),
                          _costs(slot["candidate"], f"{name}.candidate")))
    return Comparison(
        _name(data["workload"], "workload"), _name(domain["id"], "domain.id"),
        _name(schedule["id"], "schedule.id"),
        _name(schedule["path"], "schedule.path"), digest,
        _name(clock["id"], "clock.id"), _integer(clock["hz"], "clock.hz", 1), tuple(slots),
        _bound(boundary.get("fence_t"), "boundary.fence_t"),
        _bound(boundary.get("d_pipe_completion"), "boundary.d_pipe_completion"),
        _bound(boundary.get("vmclear"), "boundary.vmclear"),
        _bound(boundary.get("opp_relock"), "boundary.opp_relock"),
        _bound(budgets.get("frame"), "budgets.frame"),
        _bound(area.get("baseline"), "area.baseline"),
        _bound(area.get("candidate"), "area.candidate"),
        _bound(budgets.get("area"), "budgets.area"),
        _bound(power.get("baseline"), "power.baseline"),
        _bound(power.get("candidate"), "power.candidate"),
        _bound(budgets.get("power"), "budgets.power"),
    )


def budget_status(cost: Bound, budget: Bound) -> str:
    if cost is None or budget is None:
        return "unknown"
    if cost.high <= budget.low:
        return "met"
    return "violated" if cost.low > budget.high else "uncertain"


def _relation(saving: Bound) -> str:
    if saving is None:
        return "unknown"
    if saving.low > 0:
        return "improved"
    if saving.low == 0:
        return "no-regression"
    return "regressed" if saving.high < 0 else "uncertain"


def assess(comparison: Comparison) -> dict[str, Json]:
    """Compare an explicitly declared serial frame; no admission/WCET assertion."""
    model = comparison
    shared = add(model.vmclear, model.opp_relock)
    baseline_boundary = add(model.fence_t, shared)
    candidate_boundary = add(model.d_pipe_completion, shared)
    switch_saving = subtract(model.fence_t, model.d_pipe_completion)
    unknown: list[Json] = [name for name in (
        "fence_t", "d_pipe_completion", "vmclear", "opp_relock", "frame_budget",
        "baseline_area", "candidate_area", "area_budget", "baseline_power",
        "candidate_power", "power_budget") if getattr(model, name) is None]
    baseline_totals: list[Bound] = []
    candidate_totals: list[Bound] = []
    net_savings: list[Bound] = []
    baseline_budgets: dict[str, Json] = {}
    candidate_budgets: dict[str, Json] = {}
    relations: dict[str, Json] = {}
    slots: list[Json] = []
    for slot in model.slots:
        if slot.deadline is None:
            unknown.append(f"slots.{slot.name}.deadline")
        for side, costs in (("baseline", slot.baseline), ("candidate", slot.candidate)):
            unknown.extend(f"slots.{slot.name}.{side}.{field}"
                           for field in ("execution", "stalls", "trap_per_switch", "other")
                           if getattr(costs, field) is None)
        baseline = add(slot.baseline.exclusive(slot.switches),
                       multiply(slot.switches, baseline_boundary))
        candidate = add(slot.candidate.exclusive(slot.switches),
                        multiply(slot.switches, candidate_boundary))
        # Shared boundary operands denote the same quantity on both sides and cancel.
        saving = add(subtract(slot.baseline.exclusive(slot.switches),
                              slot.candidate.exclusive(slot.switches)),
                     multiply(slot.switches, switch_saving))
        baseline_totals.append(baseline)
        candidate_totals.append(candidate)
        net_savings.append(saving)
        key = f"slot:{slot.name}"
        baseline_budgets[key] = budget_status(baseline, slot.deadline)
        candidate_budgets[key] = budget_status(candidate, slot.deadline)
        relations[key] = _relation(saving)
        slots.append({"id": slot.name, "switches": slot.switches,
                      "baseline_cycles": _json(baseline), "candidate_cycles": _json(candidate),
                      "switch_saving_cycles": _json(multiply(slot.switches, switch_saving)),
                      "net_saving_cycles": _json(saving), "deadline_cycles": _json(slot.deadline)})
    baseline_frame = add(*baseline_totals)
    candidate_frame = add(*candidate_totals)
    frame_saving = add(*net_savings)
    area_saving = subtract(model.baseline_area, model.candidate_area)
    power_saving = subtract(model.baseline_power, model.candidate_power)
    for name, baseline, candidate, budget in (
        ("frame", baseline_frame, candidate_frame, model.frame_budget),
        ("area", model.baseline_area, model.candidate_area, model.area_budget),
        ("power", model.baseline_power, model.candidate_power, model.power_budget),
    ):
        baseline_budgets[name] = budget_status(baseline, budget)
        candidate_budgets[name] = budget_status(candidate, budget)
    relations.update(frame=_relation(frame_saving), area=_relation(area_saving),
                     power=_relation(power_saving))
    if "violated" in candidate_budgets.values():
        verdict, reason = "refuted", "a candidate budget is definitely violated"
    elif unknown:
        verdict, reason = "open", "mandatory numeric operands are unknown"
    elif any(status != "met" for status in baseline_budgets.values()):
        verdict, reason = "inconclusive", "baseline feasibility is not established"
    elif any(status != "met" for status in candidate_budgets.values()):
        verdict, reason = "inconclusive", "candidate feasibility is not established"
    elif all(status in {"improved", "no-regression"} for status in relations.values()) \
            and "improved" in relations.values():
        verdict, reason = "favorable", "all budgets met; no regression and strict improvement"
    else:
        verdict, reason = "inconclusive", "overlap, regression, tradeoff or no strict improvement"
    return {
        "arithmetic_verdict": verdict, "reason": reason, "unknown_operands": unknown,
        "baseline_budget_status": baseline_budgets, "candidate_budget_status": candidate_budgets,
        "relations": relations, "slots": slots,
        "boundary_cycles": {"baseline": _json(baseline_boundary),
                            "candidate": _json(candidate_boundary),
                            "saving_per_switch": _json(switch_saving)},
        "frame_cycles": {"baseline": _json(baseline_frame), "candidate": _json(candidate_frame),
                         "net_saving": _json(frame_saving),
                         "switch_saving": _json(multiply(sum(s.switches for s in model.slots),
                                                           switch_saving))},
        "area_um2": {"baseline": _json(model.baseline_area), "candidate": _json(model.candidate_area),
                     "saving": _json(area_saving)},
        "power_uW": {"baseline": _json(model.baseline_power), "candidate": _json(model.candidate_power),
                     "saving": _json(power_saving)},
    }


def bind_schedule(comparison: Comparison, input_path: Path) -> dict[str, Json]:
    """Read once and hash the exact schedule bytes, with no semantic promotion."""
    path = Path(comparison.schedule_path)
    if not path.is_absolute():
        path = input_path.parent / path
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != comparison.schedule_sha256:
        raise ValueError(f"schedule SHA-256 mismatch: expected {comparison.schedule_sha256}, got {actual}")
    return {"id": comparison.schedule_id, "path": str(path.resolve()), "sha256": actual,
            "bytes": len(raw)}
