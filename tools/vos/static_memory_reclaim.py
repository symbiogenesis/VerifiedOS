# SPDX-License-Identifier: Apache-2.0
"""Conditional fixed-schedule reclamation and capacity research, in synthetic ticks.

The timing model is deliberately separate from Q22's authority model. Neither
its holder-footprint premise nor its service rates are target qualifications.
"""

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from math import lcm
from pathlib import Path
from typing import Any

from vos import revocation as authority


@dataclass(frozen=True)
class Envelope:
    """Each public period permits a subset of four fixed request identities."""

    period: int = 24
    requests: int = 4
    extent_bytes: int = 16
    payload_bytes: int = 12
    result_phase: int = 8
    permanent_bytes: int = 64
    workload_bytes_per_tick: int = 32
    fabric_bytes_per_tick: int = 64
    control_bytes_per_tick: int = 8
    control_work_bytes_per_request_tick: int = 2
    containment_ticks: int = 6


@dataclass(frozen=True)
class Policy:
    name: str
    release_phases: tuple[int, ...]
    pass_period: int
    sweep_ticks: int = 4
    sweep_bytes_per_tick: int = 16
    zero_ticks: int = 4
    zero_bytes_per_tick: int = 16


def validate(env: Envelope, policy: Policy) -> None:
    values = asdict(env) | {key: value for key, value in asdict(policy).items()
                           if key not in {"name", "release_phases"}}
    if any(type(value) is not int or value <= 0 for value in values.values()):
        raise ValueError("all sizes and service quantities must be positive integers")
    if (env.payload_bytes > env.extent_bytes or env.result_phase >= env.period
            or len(policy.release_phases) != env.requests
            or policy.pass_period < max(policy.sweep_ticks, policy.zero_ticks)
            or policy.zero_bytes_per_tick != env.extent_bytes):
        raise ValueError("unsupported envelope or complete-slot service shape")
    if any(type(phase) is not int or not 0 < phase <= env.result_phase
           for phase in policy.release_phases):
        raise ValueError("retirement must follow computation and precede result delivery")


def retirement_envelope(env: Envelope, policy: Policy, duration: int) -> int:
    """Exact sup of charged arrivals in (s, s+duration] for the periodic superset.

    Every admitted input is a subset of this fixed calendar. This is not an
    envelope inferred from a finite trace or from an average retirement rate.
    """
    validate(env, policy)
    if type(duration) is not int or duration < 0:
        raise ValueError("window duration must be a nonnegative integer")
    whole, remainder = divmod(duration, env.period)
    residual = max((sum(0 < (phase - start) % env.period <= remainder
                        for phase in policy.release_phases)
                    for start in range(env.period)), default=0)
    return (whole * env.requests + residual) * env.extent_bytes


def next_pass(policy: Policy, barrier: int) -> int:
    """Even an equal-timestamp pass is ineligible: its start must follow the barrier."""
    return (barrier // policy.pass_period + 1) * policy.pass_period


def reservation(env: Envelope, policy: Policy) -> list[dict[str, int]]:
    """Price simultaneous fixed reservations, including unused reserved service."""
    validate(env, policy)
    rows: list[dict[str, int]] = []
    for tick in range(lcm(env.period, policy.pass_period)):
        sweep = (policy.sweep_bytes_per_tick
                 if tick % policy.pass_period < policy.sweep_ticks else 0)
        zero = (policy.zero_bytes_per_tick
                if (tick - policy.sweep_ticks) % policy.pass_period < policy.zero_ticks
                else 0)
        available = env.fabric_bytes_per_tick - env.control_bytes_per_tick - sweep - zero
        # Count every release still in its C-tick control pipeline, including
        # prior periods. Each of its serial jobs has this synthetic byte cost.
        control_active = sum((tick - phase) // env.period
                             - (tick - env.containment_ticks - phase) // env.period
                             for phase in policy.release_phases)
        rows.append({"tick": tick, "sweep": sweep, "zeroization": zero,
                     "control": env.control_bytes_per_tick,
                     "control_required": control_active * env.control_work_bytes_per_request_tick,
                     "workload_required": env.workload_bytes_per_tick,
                     "workload_available": available,
                     "total_reserved": env.control_bytes_per_tick + sweep + zero
                                       + env.workload_bytes_per_tick})
    return rows


def scheduled_records(env: Envelope, policy: Policy, cycles: int,
                      failed: frozenset[int] = frozenset()) -> list[dict[str, Any]]:
    """Full-demand witness with per-pass zero service; never invent an overflow slot.

    A failed containment remains retained forever in this finite observation.
    The caller must check reservation feasibility before claiming availability.
    """
    validate(env, policy)
    if type(cycles) is not int or not 1 <= cycles <= 100:
        raise ValueError("finite replay requires one to one hundred periods")
    if any(type(index) is not int or not 0 <= index < cycles * env.requests
           for index in failed):
        raise ValueError("failed identity is outside the finite request calendar")
    records: list[dict[str, Any]] = []
    cohorts: dict[int, list[dict[str, Any]]] = {}
    for cycle in range(cycles):
        for slot, phase in enumerate(policy.release_phases):
            index = cycle * env.requests + slot
            start = cycle * env.period
            release = start + phase
            barrier = release + env.containment_ticks
            row: dict[str, Any] = {
                "id": index, "start": start, "result": start + env.result_phase,
                "release": release, "failure_decision": barrier if index in failed else None,
                "barrier": None if index in failed else barrier,
                "pass_start": None, "sweep_end": None, "reuse": None,
                "extent_bytes": env.extent_bytes, "payload_bytes": env.payload_bytes,
                "status": "failed-containment" if index in failed else "pending",
            }
            records.append(row)
            if index not in failed:
                cohorts.setdefault(next_pass(policy, barrier), []).append(row)
    for begin, cohort in sorted(cohorts.items()):
        # Every full post-barrier pass serves the complete authority-source map,
        # not just retired data. Zeroization is FIFO by immutable request id.
        for position, row in enumerate(cohort):
            row.update(pass_start=begin, sweep_end=begin + policy.sweep_ticks)
            if position >= policy.zero_ticks:
                row["status"] = "zeroization-reservation-exhausted"
            else:
                row.update(reuse=begin + policy.sweep_ticks + position + 1,
                           status="reusable")
    return records


def bounds(env: Envelope, policy: Policy) -> dict[str, Any]:
    """Conditional periodic-calendar bound, independent of the finite trace horizon.

    Containment is deliberately padded to exactly C. Each pass cohort has its
    own reserved zero slots. Deleting an optional request only removes work.
    """
    validate(env, policy)
    cycle = lcm(env.period, policy.pass_period)
    groups: dict[int, int] = {}
    waits: list[int] = []
    # Representatives modulo the hyperperiod include cohorts across its cut.
    for start in range(0, cycle, env.period):
        for phase in policy.release_phases:
            barrier = start + phase + env.containment_ticks
            begin = next_pass(policy, barrier)
            waits.append(begin - barrier)
            key = begin % cycle
            groups[key] = groups.get(key, 0) + 1
    max_cohort = max(groups.values())
    rows = reservation(env, policy)
    errors = []
    if any(row["control_required"] > row["control"] for row in rows):
        errors.append("retirement pipeline exceeds its fixed containment control grant")
    if any(row["workload_available"] < row["workload_required"] for row in rows):
        errors.append("fixed reclamation reservation removes required workload service")
    if max_cohort > policy.zero_ticks:
        errors.append("a post-barrier cohort exceeds its reserved zeroization slots")
    if errors:
        return {"status": "refused", "errors": errors, "max_cohort_slots": max_cohort,
                "release_to_reuse": None}
    containment = env.containment_ticks
    wait = max(waits)
    sweep = policy.sweep_ticks
    zero = max_cohort
    total = containment + wait + sweep + zero
    return {"status": "conditional", "errors": [], "C": containment, "W": wait,
            "S": sweep, "Z": zero, "release_to_reuse": total,
            "unphased_wait_bound": policy.pass_period,
            "max_cohort_slots": max_cohort,
            "retirement_reserve_bytes": retirement_envelope(env, policy, total),
            "quantifier": "all subsets of the fixed periodic request calendar, with successful premises",
            "initial_backlog": "zero; an arbitrary initial backlog must be added separately"}


def timeline(env: Envelope, records: list[dict[str, Any]], horizon: int) -> list[dict[str, int]]:
    """A disjoint byte partition; old-slot completions precede new-slot acquisition."""
    rows = []
    for tick in range(horizon + 1):
        charges = dict.fromkeys(("useful_payload", "live_slack", "quiescing",
                                "quarantined", "zeroizing", "failed_retention"), 0)
        for obj in records:
            if tick < obj["start"] or (obj["reuse"] is not None and tick >= obj["reuse"]):
                continue
            if tick < obj["release"]:
                charges["useful_payload"] += env.payload_bytes
                charges["live_slack"] += env.extent_bytes - env.payload_bytes
            elif obj["failure_decision"] is not None and tick >= obj["failure_decision"]:
                charges["failed_retention"] += env.extent_bytes
            elif obj["barrier"] is None or tick < obj["barrier"]:
                charges["quiescing"] += env.extent_bytes
            elif obj["sweep_end"] is None or tick < obj["sweep_end"]:
                charges["quarantined"] += env.extent_bytes
            else:
                charges["zeroizing"] += env.extent_bytes
        rows.append({"tick": tick, **charges,
                     "unreusable_retired": sum(charges[key] for key in (
                         "quiescing", "quarantined", "zeroizing", "failed_retention")),
                     "occupied_backing": sum(charges.values()),
                     "permanent": env.permanent_bytes,
                     "total_charge": sum(charges.values()) + env.permanent_bytes})
    return rows


def fixed_bindings(records: list[dict[str, Any]], slots: int) -> dict[str, Any]:
    """Replay the precomputed id-modulo-slots binding; no runtime placement search."""
    if type(slots) is not int or slots < 1:
        raise ValueError("at least one fixed slot is required")
    busy: dict[int, int | None] = {}
    refused = []
    for row in records:
        slot = row["id"] % slots
        if slot in busy and (busy[slot] is None or busy[slot] > row["start"]):
            refused.append(row["id"])
        else:
            busy[slot] = row["reuse"]
    return {"slots": slots, "binding": "immutable request id modulo slots",
            "refused_ids": refused, "same_service_admitted": not refused}


def semantic_checks() -> dict[str, Any]:
    """Reuse the authority predicates, and expose actual resurrection behind a cursor."""
    comp, initial = authority.fixture()
    swept = authority.reclaimed(comp, initial)
    safe = authority.reuse(comp, swept)
    old = next(holder for holder in initial.holders if holder.name == "saved")
    behind = authority.replace_holder(swept, old.name, old)
    prematurely_cleared = replace(behind, bits=behind.bits - comp.targets)
    timed_out = authority.acknowledgement_timeout(authority.ready(comp, initial))
    cases = [{"case": name, "refusals": reasons}
             for name, reasons in authority.counterexamples()]
    cases.append({"case": "failure-deadline-is-not-reuse",
                  "refusals": authority.reuse_errors(comp, timed_out)})
    return {"cases": cases, "positive_reuse_errors": authority.exposed(safe),
            "behind_cursor_tag_remains": old.cap.tag,
            "behind_cursor_reuse_errors": authority.reuse_errors(comp, behind),
            "premature_bit_clear_exposes": authority.exposed(prematurely_cleared),
            "scope": "Q22 finite authority fixtures, separate from the synthetic timing calendar"}


def experiment(env: Envelope, policy: Policy, cycles: int = 4) -> dict[str, Any]:
    contract = bounds(env, policy)
    result: dict[str, Any] = {"policy": asdict(policy), "bound": contract,
                              "reservation": reservation(env, policy)}
    if contract["status"] == "refused":
        result.update(status="service-refused", same_service_admitted=False)
        return result
    records = scheduled_records(env, policy, cycles)
    final = max(row["reuse"] for row in records if row["reuse"] is not None)
    rows = timeline(env, records, final)
    peak = max(row["occupied_backing"] for row in rows)
    peak_slots = peak // env.extent_bytes
    bindings = fixed_bindings(records, peak_slots)
    errors = []
    if bindings["refused_ids"]:
        errors.append("peak-sized fixed binding does not implement the witness")
    if any(row["reuse"] is None or row["reuse"] - row["release"]
           > contract["release_to_reuse"] for row in records):
        errors.append("finite trace violates the conditional successful delay")
    if any(row["unreusable_retired"] > contract["retirement_reserve_bytes"] for row in rows):
        errors.append("finite trace violates the retirement envelope")
    result.update(status="witness" if not errors else "finding", errors=errors,
                  records=records, timeline=rows, required_binding=bindings,
                  fixed_capacity_binding=fixed_bindings(records, env.requests),
                  trace_cycles=cycles, finite_trace_only=True,
                  peak_occupied_backing_bytes=peak,
                  peak_total_bytes=peak + env.permanent_bytes,
                  peak_unreusable_retired_bytes=max(row["unreusable_retired"] for row in rows),
                  peak_quarantined_bytes=max(row["quarantined"] for row in rows),
                  max_observed_reuse_delay=max(row["reuse"] - row["release"] for row in records),
                  fixed_capacity_bytes=env.requests * env.extent_bytes + env.permanent_bytes)
    return result


SOURCES = ("tools/vos/static_memory_reclaim.py", "tools/tests/test_static_memory_reclaim.py",
           "tools/vos/revocation.py", "docs/assurance/revocation-qualification.md",
           "docs/implementation/static-memory-baseline.md",
           "docs/implementation/static-memory-reclamation.md")


def report(root: Path) -> dict[str, Any]:
    """Return a deterministic replay receipt; the shared CLI adds Git identity."""
    env = Envelope()
    late = (env.result_phase,) * env.requests
    early = tuple(range(1, env.requests + 1))
    policies = (Policy("deferred-slow", late, 24), Policy("eager-slow", early, 24),
                Policy("deferred-faster", late, 12), Policy("eager-faster", early, 12),
                Policy("overreserved-sweep", early, 6))
    scenarios = [experiment(env, policy) for policy in policies]
    storm_env = replace(env, requests=8)
    storm = experiment(storm_env, Policy("restart-burst-outside-service-envelope", (8,) * 8, 24))
    failed = scheduled_records(env, policies[0], 2, frozenset(range(env.requests)))
    failure_rows = timeline(env, failed, 3 * env.period)
    checks = semantic_checks()
    errors = [f"{item['policy']['name']}: {error}" for item in scenarios
              for error in item.get("errors", [])]
    if (checks["positive_reuse_errors"] or not checks["premature_bit_clear_exposes"]
            or any(not case["refusals"] for case in checks["cases"])):
        errors.append("Q22 semantic positive/refusal witness failed")
    baseline, _, _, joint, _ = scenarios
    return {
        "schema": "static-memory-reclamation-v1",
        "scope": "conditional synthetic fixed calendar and finite host traces; no target rates or theorem",
        "envelope": asdict(env),
        "service_contract": {
            "arrival_rule": "a subset of four named requests at each multiple of 24 ticks",
            "results": "same deterministic result per request, visible only at public phase 8",
            "computation": "four independent one-tick tasks at phases 0..3; results copied to permanent outbox",
            "retirement_change": "deferred release holds inputs until delivery; eager release follows each task",
            "permanent_charge": "64 synthetic bytes for control, descriptors and result outbox in every variant",
            "containment": "six serial one-tick obligations, padded exactly: publish, live/saved roots, loan cancellation, proxy notify, DMA completion, proxy acknowledgement",
            "control_cost": "each active request consumes two synthetic bytes per containment tick; concurrent pipelines must fit the fixed control grant",
            "holder_coverage": "four fixed authority-source groups, each read+rewrite charged at 16 bytes; full coverage and no repopulation are premises",
            "cost_limits": "synthetic fabric reservations include data/tag/ECC effects by assumption; target WCET, power and code extraction are open",
            "telemetry_label": "public synthetic research inputs; no private runtime occupancy",
        },
        "scenarios": scenarios,
        "comparisons": {"baseline": baseline["policy"]["name"], "joint": joint["policy"]["name"],
                        "finite_trace_backing_saved_bytes": baseline["peak_total_bytes"] - joint["peak_total_bytes"],
                        "finite_trace_quarantine_saved_bytes": baseline["peak_quarantined_bytes"] - joint["peak_quarantined_bytes"],
                        "interpretation": "capacity comes from reuse before the next admission; separate peak quarantine does not shrink"},
        "restart_stress": {"scope": "eight simultaneous retirements change the four-request envelope", "experiment": storm},
        "failed_containment": {"records": failed, "timeline": failure_rows,
                               "successful_reuse_bound": None,
                               "binding": fixed_bindings(failed, env.requests),
                               "rule": "failed slots remain charged; later requests are refused"},
        "semantic_checks": checks, "errors": errors,
        "sources_sha256": {name: sha256((root / name).read_bytes()).hexdigest() for name in SOURCES},
    }
