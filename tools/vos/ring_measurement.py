# SPDX-License-Identifier: Apache-2.0
"""Analyze supplied ring observations under the roster-measurement contract.

The declaration reader owns limits. This instrument checks captured arithmetic,
not producer truth, an admitted roster, notification protocol or target WCET.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import cast

from vos.cli import ring as ring_owner
from vos.jsonc import Json

COST_FIELDS = ("validation_cost", "device_service_bound", "cancellation_cleanup_cost",
               "completion_publication_cost")
REQUEST_BOUNDS = {**{field: field for field in COST_FIELDS},
                  "payload_bytes": "max_payload_bytes",
                  "segment_count": "max_segment_count", "notifications": "max_notifications"}
IDENTITY_FIELDS = {"roster_revision", "image_sha256", "composition_sha256"}
SCOPE = "host capture analysis; target acceptance pending"


@dataclass(frozen=True)
class Rate:
    numerator: int
    denominator: int


@dataclass(frozen=True)
class Window:
    start_tick: int
    end_tick: int
    tick_hz: int


@dataclass(frozen=True)
class RequestAccounting:
    operation: str
    observed: dict[str, int]
    declared_bounds: dict[str, int]
    cost: int


@dataclass(frozen=True)
class Activation:
    tick: int
    queue_high_water: int
    batch_size: int
    notifications: int
    generated_notifications: int
    activation_overhead_cost: int
    cost: int
    remaining_budget: int
    requests: tuple[RequestAccounting, ...]


@dataclass(frozen=True)
class RingSummary:
    ring_id: str
    world: str
    capacity: int
    max_batch_size: int
    slot_budget: int
    queue_high_water: int
    batch_high_water: int
    max_activation_cost: int
    request_count: int
    observed_notifications: int
    generated_notifications: int
    observed_interval_ticks: int
    observed_notifications_per_second: Rate | None
    activation_gaps_ticks: tuple[int, ...]
    unmeasured_tail_ticks: int
    activations: tuple[Activation, ...]


@dataclass(frozen=True)
class Analysis:
    schema_version: int
    scope: str
    milestone_acceptance: str
    verdict: str
    identity: dict[str, str]
    capture_sha256: str
    expected_identity_sha256: str
    declaration_sha256: str
    cost_unit: str
    window: Window
    rings: tuple[RingSummary, ...]
    findings: tuple[str, ...]


def _pairs(pairs: list[tuple[str, Json]]) -> dict[str, Json]:
    result: dict[str, Json] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _noninteger(_value: str) -> None:
    raise ValueError("floating-point and non-finite numbers are unsupported")


def _decode(blob: bytes) -> Json:
    return cast(Json, json.loads(blob.decode("utf-8"), object_pairs_hook=_pairs,
                                 parse_float=_noninteger, parse_constant=_noninteger))


def _object(value: Json, keys: set[str], where: str) -> dict[str, Json]:
    if not isinstance(value, dict) or value.keys() != keys:
        raise ValueError(f"{where}: expected fields {', '.join(sorted(keys))}")
    return value


def _array(value: Json, where: str, *, nonempty: bool = False) -> list[Json]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{where}: expected {'nonempty ' if nonempty else ''}array")
    return value


def _name(value: Json, where: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f"{where}: expected nonempty identifier without outer whitespace")
    return value


def _number(value: Json, where: str, *, positive: bool = False) -> int:
    if type(value) is not int or value < (1 if positive else 0):
        raise ValueError(f"{where}: expected {'positive' if positive else 'nonnegative'} integer")
    return value


def _digest(value: Json, where: str, *, revision: bool = False) -> str:
    pattern = r"(?:[0-9a-f]{40}|[0-9a-f]{64})" if revision else r"[0-9a-f]{64}"
    if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
        raise ValueError(f"{where}: expected full lowercase {'Git' if revision else 'SHA-256'} digest")
    return value


def _check_limit(observed: int, limit: int, where: str, findings: list[str]) -> None:
    if observed > limit:
        findings.append(f"{where}: observed {observed} exceeds declared {limit}")


def _records(world: ring_owner.World) -> dict[str, dict[str, int]]:
    fields = world["operation_record_fields"]
    required = {*REQUEST_BOUNDS.values(), "max_requests_drained"}
    if len(fields) != len(set(fields)) or set(fields) != required:
        raise ValueError(f"world {world['world']}: unsupported or repeated operation record fields")
    records: dict[str, dict[str, int]] = {}
    for operation in world["operations"]:
        name = operation["name"]
        if name in records:
            raise ValueError(f"world {world['world']}: repeated operation {name}")
        records[name] = dict(zip(fields, operation["record"], strict=True))
    return records


def _activation(value: Json, world: ring_owner.World, records: dict[str, dict[str, int]],
                where: str, findings: list[str]) -> Activation:
    row = _object(value, {"tick", "queue_high_water", "notifications",
                          "activation_overhead_cost", "requests"}, where)
    tick = _number(row["tick"], f"{where}/tick")
    high_water = _number(row["queue_high_water"], f"{where}/queue_high_water")
    notifications = _number(row["notifications"], f"{where}/notifications")
    overhead = _number(row["activation_overhead_cost"], f"{where}/activation_overhead_cost")
    requests = _array(row["requests"], f"{where}/requests")
    constants = world["ring"]
    _check_limit(high_water, constants["capacity"], f"{where}/queue_high_water", findings)
    _check_limit(len(requests), constants["max_batch_size"], f"{where}/batch_size", findings)
    accounting: list[RequestAccounting] = []
    represented: set[str] = set()
    for index, request in enumerate(requests):
        location = f"{where}/requests/{index}"
        observed = _object(request, {"operation", *REQUEST_BOUNDS}, location)
        operation = _name(observed["operation"], f"{location}/operation")
        if operation not in records:
            raise ValueError(f"{location}: undeclared operation {operation}")
        limits = records[operation]
        charges = {field: _number(observed[field], f"{location}/{field}")
                   for field in REQUEST_BOUNDS}
        for field, bound in REQUEST_BOUNDS.items():
            _check_limit(charges[field], limits[bound], f"{location}/{field}", findings)
        if operation not in represented:
            _check_limit(len(requests), limits["max_requests_drained"],
                         f"{where}/{operation}/max_requests_drained", findings)
            represented.add(operation)
        accounting.append(RequestAccounting(operation, charges, limits,
                                             sum(charges[field] for field in COST_FIELDS)))
    cost = overhead + sum(request.cost for request in accounting)
    _check_limit(cost, constants["slot_budget"], f"{where}/activation_cost", findings)
    return Activation(tick, high_water, len(requests), notifications,
                      sum(request.observed["notifications"] for request in accounting),
                      overhead, cost, constants["slot_budget"] - cost, tuple(accounting))


def _ring(value: Json, worlds: dict[str, ring_owner.World], window: Window,
          findings: list[str]) -> RingSummary:
    row = _object(value, {"ring_id", "world", "activations"}, "ring")
    name = _name(row["ring_id"], "ring_id")
    world_name = _name(row["world"], f"{name}/world")
    if world_name not in worlds:
        raise ValueError(f"{name}: undeclared world {world_name}")
    world = worlds[world_name]
    records = _records(world)
    activations = tuple(_activation(value, world, records, f"{name}/activations/{index}", findings)
                        for index, value in enumerate(_array(row["activations"],
                                                             f"{name}/activations", nonempty=True)))
    previous = window.start_tick - 1
    for activation in activations:
        if not window.start_tick <= activation.tick < window.end_tick or activation.tick <= previous:
            raise ValueError(f"{name}: activation ticks must strictly increase inside the window")
        previous = activation.tick
    duration = activations[-1].tick - window.start_tick
    notifications = sum(activation.notifications for activation in activations)
    rate = Fraction(notifications * window.tick_hz, duration) if duration else None
    constants = world["ring"]
    return RingSummary(name, world_name, constants["capacity"], constants["max_batch_size"],
                       constants["slot_budget"], max(row.queue_high_water for row in activations),
                       max(row.batch_size for row in activations), max(row.cost for row in activations),
                       sum(row.batch_size for row in activations), notifications,
                       sum(row.generated_notifications for row in activations),
                       duration, Rate(rate.numerator, rate.denominator) if rate is not None else None,
                       tuple(right.tick - left.tick for left, right in pairwise(activations)),
                       window.end_tick - activations[-1].tick, activations)


def analyze(capture_blob: bytes, expected_blob: bytes, root: Path) -> Analysis:
    """Refuse malformed bindings; return finite-capture bound findings and exact rates."""
    expected = _object(_decode(expected_blob), IDENTITY_FIELDS | {"capture_sha256"}, "expected identity")
    capture = _object(_decode(capture_blob), {"schema_version", "complete", "identity", "window",
                                             "declaration_sha256", "cost_unit", "rings"}, "capture")
    if _number(capture["schema_version"], "schema_version") != 1:
        raise ValueError("unsupported capture schema_version")
    if capture["complete"] is not True:
        raise ValueError("capture is not complete")
    if capture["cost_unit"] != "declaration_units":
        raise ValueError("cost_unit must be declaration_units, without conversion to clock ticks")
    identity = _object(capture["identity"], IDENTITY_FIELDS, "identity")
    checked: dict[str, str] = {}
    for field in sorted(IDENTITY_FIELDS):
        wanted = _digest(expected[field], f"expected/{field}", revision=field == "roster_revision")
        actual = _digest(identity[field], f"identity/{field}", revision=field == "roster_revision")
        if actual != wanted:
            raise ValueError(f"identity mismatch: {field}")
        checked[field] = actual
    capture_hash = hashlib.sha256(capture_blob).hexdigest()
    if _digest(expected["capture_sha256"], "expected/capture_sha256") != capture_hash:
        raise ValueError("capture_sha256 does not bind the supplied capture bytes")
    declaration_blob = (root / ring_owner.DECLARATION).read_bytes()
    declaration_hash = hashlib.sha256(declaration_blob).hexdigest()
    if _digest(capture["declaration_sha256"], "declaration_sha256") != declaration_hash:
        raise ValueError("declaration_sha256 does not bind the current ring declaration")
    # The owning reader validates declaration shapes but permits duplicate JSON keys.
    # Apply this instrument's strict JSON boundary to the exact bytes bound above.
    _decode(declaration_blob)
    try:
        declaration = ring_owner.declaration(root)
    except ring_owner.RingError as error:
        raise ValueError(f"ring declaration: {error}") from error
    if (root / ring_owner.DECLARATION).read_bytes() != declaration_blob:
        raise ValueError("ring declaration changed during analysis")
    worlds = {world["world"]: world for world in declaration["worlds"]}
    times = _object(capture["window"], {"start_tick", "end_tick", "tick_hz"}, "window")
    window = Window(_number(times["start_tick"], "window/start_tick"),
                    _number(times["end_tick"], "window/end_tick"),
                    _number(times["tick_hz"], "window/tick_hz", positive=True))
    if window.end_tick <= window.start_tick:
        raise ValueError("window must have positive duration")
    findings: list[str] = []
    rings = tuple(_ring(value, worlds, window, findings)
                  for value in _array(capture["rings"], "rings", nonempty=True))
    if len({ring.ring_id for ring in rings}) != len(rings):
        raise ValueError("repeated ring_id")
    return Analysis(1, SCOPE, "open", "exceeds_limits" if findings else "within_limits",
                    checked, capture_hash, hashlib.sha256(expected_blob).hexdigest(),
                    declaration_hash, "declaration_units", window, rings, tuple(findings))
