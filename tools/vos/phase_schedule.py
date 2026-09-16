# SPDX-License-Identifier: Apache-2.0
"""Extract a declared periodic schedule into Q22e's finite service contract.

The declaration is not an instruction-stream emitter or a qualified resource
measurement. Its alternatives remain joint and ordered, including traffic which
the service predicate refutes. Only malformed declarations are rejected here.
"""

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Never, cast

from vos.jsonc import Json
from vos.phase_service import Batch, Contract


@dataclass(frozen=True)
class Bank:
    name: str
    path_cycles: int
    occupancy_cycles: dict[str, int]
    refresh_cycles: int | None


@dataclass(frozen=True)
class Resources:
    harts: dict[str, int]
    operations: tuple[str, ...]
    banks: tuple[Bank, ...]


@dataclass(frozen=True)
class InjectionExcess:
    phase: int
    alternative: int
    requests: int
    grant: int


@dataclass(frozen=True)
class Extraction:
    name: str
    schedule_sha256: str
    resources_sha256: str
    bank_names: tuple[str, ...]
    hart_names: tuple[str, ...]
    operation_names: tuple[str, ...]
    injection_excesses: tuple[InjectionExcess, ...]
    contract: Contract


def _pairs(pairs: list[tuple[str, Json]]) -> dict[str, Json]:
    result: dict[str, Json] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _noninteger(_value: str) -> Never:
    raise ValueError("floating-point and non-finite JSON numbers are unsupported")


def _decode(raw: bytes) -> Json:
    try:
        return cast(Json, json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                                    parse_float=_noninteger, parse_constant=_noninteger))
    except RecursionError as err:
        raise ValueError("JSON nesting exceeds the decoder limit") from err


def _object(node: Json, fields: set[str], what: str) -> dict[str, Json]:
    if not isinstance(node, dict) or node.keys() != fields:
        raise ValueError(f"{what} requires exactly these fields: {', '.join(sorted(fields))}")
    return node


def _rows(node: Json, what: str, *, nonempty: bool = False) -> list[Json]:
    if not isinstance(node, list) or (nonempty and not node):
        raise ValueError(f"{what} must be {'a nonempty' if nonempty else 'an'} array")
    return node


def _integer(node: Json, what: str, minimum: int = 0) -> int:
    if isinstance(node, bool) or not isinstance(node, int) or node < minimum:
        raise ValueError(f"{what} must be an integer at least {minimum}")
    return node


def _name(node: Json, what: str) -> str:
    if not isinstance(node, str) or re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", node) is None:
        raise ValueError(f"{what} must be an ASCII identifier starting with a letter")
    return node


def _names(node: Json, what: str) -> tuple[str, ...]:
    names = tuple(_name(value, what) for value in _rows(node, what, nonempty=True))
    if len(set(names)) != len(names):
        raise ValueError(f"duplicate {what}")
    return names


def _resources(raw: bytes) -> Resources:
    data = _object(_decode(raw), {"schema", "harts", "operations", "banks"}, "resources")
    if data["schema"] != "phase-resources-v1":
        raise ValueError("unsupported resource schema")
    operations = _names(data["operations"], "operation name")
    harts: dict[str, int] = {}
    for member in _rows(data["harts"], "harts", nonempty=True):
        row = _object(member, {"name", "issue_limit"}, "hart")
        name = _name(row["name"], "hart name")
        if name in harts:
            raise ValueError(f"duplicate hart name: {name}")
        harts[name] = _integer(row["issue_limit"], f"{name} issue_limit", 1)
    banks: list[Bank] = []
    bank_names: set[str] = set()
    for member in _rows(data["banks"], "banks", nonempty=True):
        row = _object(member, {"name", "path_cycles", "occupancy_cycles", "refresh_cycles"}, "bank")
        name = _name(row["name"], "bank name")
        if name in bank_names:
            raise ValueError(f"duplicate bank name: {name}")
        bank_names.add(name)
        occupancy = row["occupancy_cycles"]
        if not isinstance(occupancy, dict) or not occupancy:
            raise ValueError(f"{name} occupancy_cycles must be a nonempty operation map")
        durations: dict[str, int] = {}
        for operation, cycles in occupancy.items():
            if operation not in operations:
                raise ValueError(f"{name} names unknown operation: {operation}")
            durations[operation] = _integer(cycles, f"{name}.{operation} occupancy_cycles", 1)
        refresh = row["refresh_cycles"]
        banks.append(Bank(name, _integer(row["path_cycles"], f"{name} path_cycles"),
                          durations, None if refresh is None else
                          _integer(refresh, f"{name} refresh_cycles", 1)))
    return Resources(harts, operations, tuple(banks))


def _request(node: Json, resources: Resources, bank_ids: dict[str, int],
             hart_ids: dict[str, int]) -> tuple[int, int, int]:
    row = _object(node, {"bank", "hart", "operation"}, "request")
    bank = _name(row["bank"], "request bank")
    hart = _name(row["hart"], "request hart")
    operation = _name(row["operation"], "request operation")
    if bank not in bank_ids or hart not in hart_ids:
        raise ValueError(f"request names unknown bank or hart: {bank}, {hart}")
    durations = resources.banks[bank_ids[bank]].occupancy_cycles
    if operation not in durations:
        raise ValueError(f"bank {bank} has no occupancy for operation {operation}")
    return bank_ids[bank], durations[operation], hart_ids[hart]


def _alternatives(node: Json, resources: Resources, bank_ids: dict[str, int],
                  hart_ids: dict[str, int]) -> tuple[Batch, ...]:
    alternatives: list[Batch] = []
    for member in _rows(node, "alternatives", nonempty=True):
        batch = tuple(_request(request, resources, bank_ids, hart_ids)
                      for request in _rows(member, "request batch"))
        counts = [0] * len(resources.harts)
        for _, _, hart in batch:
            counts[hart] += 1
        for name, limit in resources.harts.items():
            if counts[hart_ids[name]] > limit:
                raise ValueError(f"alternative exceeds hart {name} issue_limit {limit}")
        alternatives.append(batch)
    return tuple(alternatives)


def _refresh(node: Json, resources: Resources, bank_ids: dict[str, int]) -> Batch:
    entries: list[tuple[int, int]] = []
    seen: set[str] = set()
    for value in _rows(node, "refresh"):
        name = _name(value, "refresh bank")
        if name not in bank_ids or name in seen:
            raise ValueError(f"unknown or duplicate refresh bank: {name}")
        seen.add(name)
        bank = bank_ids[name]
        cycles = resources.banks[bank].refresh_cycles
        if cycles is None:
            raise ValueError(f"bank {name} has no refresh_cycles declaration")
        entries.append((bank, cycles))
    return tuple(entries)


def extract(schedule_raw: bytes, resources_raw: bytes) -> Extraction:
    """Read one mode and all its alternatives without filtering service conflicts."""
    data = _object(_decode(schedule_raw), {"schema", "name", "mode", "resources_sha256", "phases"},
                   "schedule")
    if data["schema"] != "phase-schedule-v1" or data["mode"] != "periodic":
        raise ValueError("only phase-schedule-v1 with mode periodic is supported")
    name = _name(data["name"], "schedule name")
    expected = data["resources_sha256"]
    if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        raise ValueError("resources_sha256 must be a full lowercase SHA-256 digest")
    resources_sha256 = hashlib.sha256(resources_raw).hexdigest()
    if expected != resources_sha256:
        raise ValueError("resources_sha256 does not match the supplied resource bytes")
    resources = _resources(resources_raw)
    bank_ids = {bank.name: index for index, bank in enumerate(resources.banks)}
    hart_ids = {hart: index for index, hart in enumerate(resources.harts)}
    grants: list[int] = []
    arrivals: list[tuple[Batch, ...]] = []
    refresh: list[Batch] = []
    excesses: list[InjectionExcess] = []
    for phase, member in enumerate(_rows(data["phases"], "phases", nonempty=True)):
        row = _object(member, {"grant", "alternatives", "refresh"}, "phase")
        grant = _integer(row["grant"], "phase grant")
        alternatives = _alternatives(row["alternatives"], resources, bank_ids, hart_ids)
        grants.append(grant)
        arrivals.append(alternatives)
        refresh.append(_refresh(row["refresh"], resources, bank_ids))
        excesses.extend(InjectionExcess(phase, index, len(batch), grant)
                        for index, batch in enumerate(alternatives) if len(batch) > grant)
    contract = Contract(tuple(grants), tuple(arrivals), len(resources.banks), tuple(refresh),
                        tuple(bank.path_cycles for bank in resources.banks))
    return Extraction(name, hashlib.sha256(schedule_raw).hexdigest(), resources_sha256,
                      tuple(bank_ids), tuple(hart_ids), resources.operations, tuple(excesses), contract)


def contract_bytes(contract: Contract) -> bytes:
    """Exact portable bytes emitted for the existing phase-service reader."""
    return (json.dumps(asdict(contract), sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
