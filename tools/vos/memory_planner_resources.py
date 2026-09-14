# SPDX-License-Identifier: Apache-2.0
"""Resource-aware contracts for already placed, bounded component slots.

Logical byte credits alone do not promise a suitably shaped free extent. This
checker therefore requires the independent fixed-placement checker as well as
the resource ledger. Credits return at safe reuse, never at lexical release.
Every operation's elapsed upper bound is a caller obligation, including device
wait, scheduling and cleanup; no event count is reported as measured time.

The strong/weak specification pattern is inspired by Verified Sequential
Malloc/Free; its bin allocator, VST proofs and runtime mechanisms are not imported.
The accompanying Gallina model proves the credit arithmetic and duration bound,
not correspondence from Vela source or this Python implementation.
"""

import copy
import hashlib
import json
from typing import Any

from vos import memory_planner as planner
from vos import memory_planner_contracts as contracts

SCHEMA = "memory-resource-contract-v1"
ASSUMPTIONS = (
    "The fixed slot placement and its overhead tail are physically backed before activation.",
    "No more than the declared request slots execute simultaneously, with no cross-slot borrowing.",
    "Step bounds cover elapsed service, blocking, preemption and completion delay in the stated unit.",
    "Every terminal path returns its obligations through the checked reuse barrier.",
    "Charged sizes and overhead include target metadata, padding and capability representation costs.",
    "Credit and duration theorems are mathematical models; Python, source and target refinement remain open.",
)


class ResourceError(ValueError):
    """Malformed or unplaced resource input cannot establish guaranteed success."""


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def required_credit(events: list[tuple[str, int]]) -> int:
    """Exact minimum initial logical credit; refunds are supplied protocol facts."""
    required = 0
    for kind, amount in reversed(events):
        if type(amount) is not int or amount < 0 or kind not in {"take", "return"}:
            raise ResourceError("invalid credit event")
        required = required + amount if kind == "take" else max(0, required - amount)
    return required


def run_credit(events: list[tuple[str, int]], initial: int) -> int | None:
    """Independent forward credit execution; insufficient credit returns failure."""
    if type(initial) is not int or initial < 0:
        raise ResourceError("initial credit must be a natural number")
    credit = initial
    for kind, amount in events:
        if type(amount) is not int or amount < 0 or kind not in {"take", "return"}:
            raise ResourceError("invalid credit event")
        if kind == "take":
            if amount > credit:
                return None
            credit -= amount
        else:
            credit += amount
    return credit


def _amounts(raw: object, names: set[str], where: str) -> dict[str, int]:
    values = contracts._object(raw, where)
    if set(values) != names:
        raise ResourceError(f"{where}: values must name every pool exactly once")
    return {key: contracts._nat(value, where) for key, value in values.items()}


def analyze_resources(raw: object, *, max_work: int = 1000000) -> dict[str, Any]:
    """Check prepaid budgets and bound release request/start through safe reuse.

    Required fields: schema, contract, placement, reserved_bytes, overhead_bytes,
    step_bounds, reuse_deadline, time_unit. Only assumptions is optional. Byte maps
    name every pool. Step bounds name exactly the operations present in the paths.
    All quantities fit the portable signed-64 range; limits refuse partial output.
    The deadline includes the release operation itself through barrier completion.
    """
    limits = contracts.Limits(max_expansion_work=contracts._nat(max_work, "max_work", 1))
    source = contracts._snapshot(raw, limits, contracts._ExpansionBudget(max_work))
    contracts._fields(source, {"schema", "contract", "placement", "reserved_bytes",
                               "overhead_bytes", "step_bounds", "reuse_deadline", "time_unit"},
                      {"assumptions"}, "resource contract")
    if source["schema"] != SCHEMA:
        raise ResourceError("unsupported resource contract schema")
    extraction = contracts.extract_contract(source["contract"], max_expansion_work=max_work)
    instance = planner.parse_instance(extraction["instance"])
    placement_errors = planner.check_placement(instance, source["placement"])
    if placement_errors:
        raise ResourceError("fixed placement rejected: " + "; ".join(placement_errors))
    placement = source["placement"]
    pool_ids = {pool.id for pool in instance.pools}
    reserved = _amounts(source["reserved_bytes"], pool_ids, "reserved_bytes")
    overhead = _amounts(source["overhead_bytes"], pool_ids, "overhead_bytes")
    deadline = contracts._nat(source["reuse_deadline"], "reuse_deadline")
    unit = contracts._name(source["time_unit"], "time_unit")
    assumptions = [contracts._name(s, "assumption")
                   for s in contracts._list(source.get("assumptions", []), "assumptions")]
    paths = extraction["evidence"]["paths"]
    operations = {op for path in paths for op in path["operations"]}
    raw_bounds = contracts._object(source["step_bounds"], "step_bounds")
    if set(raw_bounds) != operations:
        raise ResourceError("step_bounds must name every used operation exactly once")
    bounds = {op: contracts._nat(value, f"step_bounds.{op}") for op, value in raw_bounds.items()}
    heights = planner.pool_heights(instance, placement)
    positioned = {row["id"]: row for row in placement}
    buffers = {buffer.id: buffer for buffer in instance.buffers}
    slots = extraction["evidence"]["slots"]
    if len(pool_ids) * slots > max_work:
        raise contracts.UnsupportedContractError("resource pool-slot product exceeds max_work")
    slot_peaks = {(pool, slot): 0 for pool in pool_ids for slot in range(slots)}
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    work = maximum_release = 0
    for index, path in enumerate(paths):
        costs = [bounds[op] for op in path["operations"]]
        prefixes = [0]
        for cost in costs:
            prefixes.append(contracts._nat(prefixes[-1] + cost, "path elapsed bound"))
        releases = []
        for lease in path["leases"]:
            release_bound = prefixes[lease["barrier"] + 1] - prefixes[lease["release"]]
            maximum_release = max(maximum_release, release_bound)
            releases.append({**lease, "elapsed_bound": release_bound,
                             "clock_origin": "release request/start of release operation",
                             "clock_end": "reuse barrier completion",
                             "step_bounds": costs[lease["release"]:lease["barrier"] + 1]})
            if release_bound > deadline:
                errors.append(f"path {index}, {lease['object']}: reuse bound {release_bound} exceeds {deadline}")
        meters = []
        for slot in range(slots):
            for pool in sorted(pool_ids):
                work += 1
                if work > max_work:
                    raise contracts.UnsupportedContractError("resource path-pool-slot product exceeds max_work")
                events: list[tuple[int, str, int, str]] = []
                for serial, lease in enumerate(path["leases"]):
                    work += 1
                    if work > max_work:
                        raise contracts.UnsupportedContractError("resource metering exceeds max_work")
                    ident = f"{lease['object']}@{slot}"
                    if positioned[ident]["pool"] != pool:
                        continue
                    size = buffers[ident].size
                    ticket = f"{ident}#{serial}"
                    events.extend(((lease["acquire"], "take", size, ticket),
                                   (lease["barrier"], "return", size, ticket)))
                events.sort()
                # Keep identity accounting separate from logical credit arithmetic.
                held: dict[str, int] = {}
                peak = used = 0
                for _, kind, amount, ticket in events:
                    if kind == "take":
                        if ticket in held:
                            raise ResourceError("duplicate metering obligation")
                        held[ticket] = amount
                        used += amount
                        peak = max(peak, used)
                    else:
                        if held.pop(ticket, None) != amount:
                            raise ResourceError("missing or mismatched metering obligation")
                        used -= amount
                if held or used:
                    raise ResourceError("a terminal metering obligation was discarded")
                credit_events = [(kind, amount) for _, kind, amount, _ in events]
                required = required_credit(credit_events)
                if required != peak or run_credit(credit_events, required) != required:
                    raise ResourceError("independent credit and occupancy computations disagree")
                slot_peaks[pool, slot] = max(slot_peaks[pool, slot], required)
                meters.append({"pool": pool, "slot": slot, "required_credit": required,
                               "events": [{"step": step, "kind": kind, "bytes": amount,
                                           "ticket": ticket} for step, kind, amount, ticket in events]})
        rows.append({"path": index, "outcome": path["outcome"], "elapsed_bound": prefixes[-1],
                     "releases": releases, "meters": meters})
    pools = []
    for pool in instance.pools:
        footprint = contracts._nat(heights[pool.id] + overhead[pool.id], "backed footprint")
        peak = contracts._nat(overhead[pool.id] + sum(slot_peaks[pool.id, s] for s in range(slots)),
                              "independent-slot occupancy")
        if footprint > reserved[pool.id] or reserved[pool.id] > pool.capacity:
            errors.append(f"{pool.id}: checked layout plus overhead does not fit its reserved physical budget")
        if peak > reserved[pool.id]:
            errors.append(f"{pool.id}: simultaneous request-slot credits exceed the reserved budget")
        pools.append({"pool": pool.id, "reserved_bytes": reserved[pool.id],
                      "layout_span": heights[pool.id], "overhead_bytes": overhead[pool.id],
                      "backed_footprint": footprint, "occupancy_bound": peak,
                      "slot_credits": [slot_peaks[pool.id, s] for s in range(slots)]})
    return {"schema": SCHEMA, "status": "refused resource contract" if errors else "checked resource contract",
            "errors": errors, "scope": "conditional guaranteed success for checked fixed request slots",
            "input_sha256": _digest(source), "contract_sha256": extraction["evidence"]["contract_sha256"],
            "placement_sha256": _digest(placement), "instance_sha256": planner.instance_digest(instance),
            "time_unit": unit, "reuse_deadline": deadline, "maximum_release_bound": maximum_release,
            "pools": pools, "paths": rows, "work": work,
            "assumptions": [*extraction["instance"]["assumptions"], *ASSUMPTIONS, *assumptions],
            "proof_endpoints": ["MemoryPlannerResources.required_credit_exact",
                                "MemoryPlannerResources.credit_conservation",
                                "MemoryPlannerResources.release_deadline_sound"]}


def replay_resources(raw: object, report: object) -> list[str]:
    try:
        expected = analyze_resources(raw)
        matches = _digest(expected) == _digest(report)
    except (TypeError, ValueError) as exc:
        return [str(exc)]
    return [] if matches else ["resource report differs from deterministic replay"]


def emit_resource_certificate(raw: object, *, max_work: int = 1000000) -> str:
    """Emit kernel-replayable finite credit and deadline facts from fresh analysis.

    This is an optional host artifact: no compiler is invoked and no target code
    consumes the text. Hashes bind its normalized source/report; the finite facts
    do not prove that source extraction or the supplied timing bounds are sound.
    """
    report = analyze_resources(raw, max_work=max_work)
    if report["errors"]:
        raise ResourceError("cannot certify a refused resource contract")
    lines = ["(* SPDX-License-Identifier: Apache-2.0 *)",
             f"(* Input SHA256: {report['input_sha256']}; report SHA256: {_digest(report)}. *)",
             "(* Finite credit/deadline replay; source and target refinement are assumptions. *)",
             "From Stdlib Require Import List Lia.", "Require Import MemoryPlannerResources.",
             "Import ListNotations."]
    serial = 0
    for path in report["paths"]:
        for meter in path["meters"]:
            events = "; ".join(f"{'Take' if e['kind'] == 'take' else 'Return'} {e['bytes']}"
                               for e in meter["events"])
            amount = meter["required_credit"]
            lines.extend([f"Example credit_{serial} : run_credit [{events}] {amount} = Some {amount}.",
                          "Proof. vm_compute. reflexivity. Qed."])
            serial += 1
        for release in path["releases"]:
            costs = "; ".join(str(n) for n in release["step_bounds"])
            lines.extend([f"Example deadline_{serial} : list_sum [{costs}] <= {report['reuse_deadline']}.",
                          "Proof. vm_compute. lia. Qed."])
            serial += 1
    return "\n".join(lines) + "\n"


def demo_resources() -> dict[str, Any]:
    """Synthetic four-slot service with declared costs, not a hardware measurement."""
    contract = contracts.demo_contract()
    extraction = contracts.extract_contract(contract)
    operations = {op for path in extraction["evidence"]["paths"] for op in path["operations"]}
    costs = dict.fromkeys(operations, 1)
    costs.update(complete=4, sweep=2, scrub=2)
    placement = [{"id": f"{name}@{slot}", "pool": "scratch", "offset": slot * 4 * 1024 * 1024}
                 for slot in range(4) for name in ("phase-a", "phase-b")]
    return {"schema": SCHEMA, "contract": copy.deepcopy(contract), "placement": placement,
            "reserved_bytes": {"scratch": 16 * 1024 * 1024 + 64},
            "overhead_bytes": {"scratch": 64}, "step_bounds": costs,
            "reuse_deadline": 11, "time_unit": "synthetic admitted elapsed ticks"}
