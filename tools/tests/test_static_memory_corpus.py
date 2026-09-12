# SPDX-License-Identifier: Apache-2.0
"""Capacity conservation, delayed reuse, isolation and source-bound witness labels."""

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from tests.harness import Case, ensure
from vos import memplan
from vos import static_memory as sm
from vos import static_memory_corpus as c


def _case(name: str) -> dict[str, Any]:
    return next(case for case in c.corpus("test-revision") if case["name"] == name)


def deterministic_identity_and_explicit_assumptions() -> None:
    first, second = c.corpus("test-revision"), c.corpus("test-revision")
    ensure(json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True),
           "the witness corpus depends on nondeterministic state")
    for case in first:
        ensure(case["provenance"] == "synthetic-witness", "product claim entered the corpus")
        ensure(not case["service_contract"]["product_admission_evidence"], "witness claims admission")
        ensure(not case["demand_envelope"]["all_execution_bound"], "trace became a universal bound")
        ensure(case["cost_assumptions"]["target_cycles"] is None, "invented target cycle cost")
        ensure(case["requests"], "no refusal or fit probes")
        ensure("no authority-completion proof" in case["reuse_semantics"]["status"],
               "timestamps became semantic evidence")
        ensure(case["source_hashes"][c.GENERATOR] == hashlib.sha256(
            Path(c.__file__).read_bytes()).hexdigest(), "dirty source was not bound")
    first[0]["objects"][0]["size"] = 999
    ensure(second[0]["objects"][0]["size"] != 999, "cases share mutable generator state")
    ensure({case["name"] for case in first} >= {
        "bounded-parser", "bounded-sessions", "bounded-ring", "saved-application-state",
        "frame-pipeline", "resident-inference", "crossing-lifetimes",
        "adversarial-alignment", "burst-teardown", "delayed-device-completion"},
        "research scenario coverage missing")


def byte_enumeration_independently_checks_every_snapshot() -> None:
    # A byte-at-a-time oracle independent of the ledger's interval boundaries.
    for case in c.corpus("test-revision"):
        for time in range(case["demand_envelope"]["horizon"] + 1):
            report = c.ledger(case, time)
            ensure(sum(report["totals"].values()) == report["total_capacity"],
                   f"global conservation failed: {case['name']}/{time}")
            for row in report["rows"]:
                objects = [obj for obj in case["objects"] if obj["arena"] == row["arena"]]
                charges = dict.fromkeys(c.CHARGES, 0)
                span = max((obj["base"] + obj["size"] for obj in objects), default=0)
                for byte in range(row["capacity"]):
                    active = [obj for obj in objects if obj["start"] <= time < obj["reuse"]
                              and obj["base"] <= byte < obj["base"] + obj["size"]]
                    ensure(len(active) <= 1, "fixture has overlapping live slots")
                    if active:
                        obj = active[0]
                        if time < obj["payload_end"]:
                            charge = ("useful_payload" if byte < obj["base"] + obj["payload"]
                                      else "slot_slack")
                        elif time < obj["authority_end"]:
                            charge = "retained"
                        elif time < obj["sweep_end"]:
                            charge = "quarantined"
                        else:
                            charge = "initializing"
                    elif any(obj["base"] <= byte < obj["base"] + obj["size"] for obj in objects):
                        charge = "idle_reserved"
                    else:
                        charge = "layout_gaps" if byte < span else "unreserved_tail"
                    charges[charge] += 1
                ensure(charges == row["charges"], f"wrong physical partition: {case['name']}/{time}")
                ensure(report["telemetry_label"] == case["telemetry_label"], "telemetry label lost")


def retirement_stages_charge_slot_slack_only_once() -> None:
    case = _case("burst-teardown")
    payload = c.ledger(case, 1)["rows"][0]["charges"]
    retained = c.ledger(case, 2)["rows"][0]["charges"]
    quarantine = c.ledger(case, 3)["rows"][0]["charges"]
    sweep = c.ledger(case, 4)["rows"][0]["charges"]
    ensure(payload["useful_payload"] == 12 and payload["slot_slack"] == 4,
           "live slack missing")
    ensure(retained["retained"] == 16 and retained["slot_slack"] == 0,
           "retention double-counted slack")
    ensure(quarantine["quarantined"] == 16 and quarantine["retained"] == 0,
           "quarantine did not take the complete slot")
    ensure(sweep["initializing"] == 4 and sweep["quarantined"] == 12,
           "sweep completion made bytes reusable before initialization")
    ensure(c.ledger(case, 5)["rows"][0]["charges"]["idle_reserved"] == 4,
           "reuse did not occur at the half-open boundary")


def equal_boundaries_rebind_without_double_charging_backing() -> None:
    case = _case("bounded-ring")
    row = c.ledger(case, 4)["rows"][0]
    ensure(row["reserved_backing"] == 8 and sum(obj["size"] for obj in case["objects"]) == 16,
           "overlaid slots were charged twice as permanent backing")
    ensure(row["charges"]["useful_payload"] == 2 and row["charges"]["initializing"] == 4,
           "end/start ordering changed at rebinding")
    ensure(c.event_times(case)[-1] == 9, "the final idle state is not replayed")


def saved_state_and_device_authority_remain_charged() -> None:
    saved = c.ledger(_case("saved-application-state"), 8)["rows"][0]
    ensure(saved["charges"]["useful_payload"] == 10, "inactive saved state treated as dead")
    device = c.ledger(_case("delayed-device-completion"), 7)["rows"][0]
    ensure(device["charges"]["retained"] == 8, "late device authority released on last use")
    ensure(device["unreusable_retired_bytes"] == 16, "restart overlap dropped from charge")


def typed_refusals_preserve_owner_and_declared_slot_limits() -> None:
    sessions = _case("bounded-sessions")
    ensure(c.diagnose_request(sessions, 2, "owner-a", "absent", 4)["reason"] == "unknown-arena",
           "unknown arena accepted")
    ensure(c.diagnose_request(sessions, 2, "owner-a", "b-pool", 4)["reason"] == "foreign-owner",
           "idle foreign backing was borrowed")
    own = c.diagnose_request(sessions, 2, "owner-a", "a-pool", 4)
    ensure(own["reason"] == "slot-occupied" and own["free_physical_bytes"] == 0,
           "full owner pool was not refused")
    alignment = _case("adversarial-alignment")
    ensure(c.diagnose_request(alignment, 5, "owner", "arena", 8)["reason"] == "slot-size",
           "geometric capacity silently became a new larger slot")
    ensure(c.diagnose_request(alignment, 5, "owner", "arena", 5, 16)["reason"] == "slot-alignment",
           "request rebased a fixed slot")
    burst = _case("burst-teardown")
    ensure(c.diagnose_request(burst, 3, "service", "pool", 4)["reason"] == "reuse-pending",
           "retired slots were used before safe reuse")
    fit = c.diagnose_request(burst, 5, "service", "pool", 4)
    ensure(fit["verdict"] == "fits-at-instant" and not fit["runtime_permission"],
           "snapshot fit became runtime permission")


def aligned_geometric_extent_does_not_merge_across_live_bytes() -> None:
    case = _case("crossing-lifetimes")
    case["arenas"] = [{"id": "arena", "owner": "owner", "capacity": 16}]
    template = case["objects"][0]
    case["objects"] = [dict(template, id="pinned", base=5, size=2, payload=2,
                            start=0, payload_end=5, authority_end=5, sweep_end=5, reuse=5)]
    row = c.ledger(case, 1, 8)["rows"][0]
    ensure(row["free_physical_bytes"] == 14 and row["largest_free_aligned_extent"] == 8,
           "alignment or occupied separation was ignored")
    ensure(row["largest_idle_declared_slot_extent"] == 0,
           "a geometric gap became a declared slot")
    ensure(row["charges"]["layout_gaps"] == 5 and row["charges"]["unreserved_tail"] == 9,
           "interior gaps and tail merged")


def malformed_lifetimes_and_overlap_fail_before_accounting() -> None:
    for mutation in ("overlap", "early-reuse", "boolean-time"):
        case = copy.deepcopy(_case("bounded-parser"))
        if mutation == "overlap":
            case["objects"][1]["base"] = 0
        elif mutation == "early-reuse":
            case["objects"][0]["reuse"] = 1
        try:
            c.ledger(case, True if mutation == "boolean-time" else 1)
        except sm.CaseError:
            pass
        else:
            raise AssertionError(f"accounted a malformed {mutation} case")


def q5_bridge_preserves_absence_instead_of_inventing_owners() -> None:
    root = Path(__file__).resolve().parents[2]
    bridge = c.q5_bridge(root, "test-revision")
    ensure(bridge["q5_export"] == memplan.export(memplan.read(root)), "Q5 export forked")
    ensure("owner" in bridge["q5_export"]["absent"], "existing owner absence dropped")
    ensure(bridge["operational_ledger"]["verdict"] == "unavailable", "invented reuse evidence")
    ensure("authority_end" in bridge["operational_ledger"]["missing"], "barrier absence lost")
    ensure(not bridge["product_admission_evidence"], "proof witness presented as product")
    ensure(bridge["source_hashes"][memplan.SOURCE] == hashlib.sha256(
        (root / memplan.SOURCE).read_bytes()).hexdigest(), "dirty source not bound")


def cases() -> list[Case]:
    return [Case(fn.__name__, fn) for fn in (
        deterministic_identity_and_explicit_assumptions,
        byte_enumeration_independently_checks_every_snapshot,
        retirement_stages_charge_slot_slack_only_once,
        equal_boundaries_rebind_without_double_charging_backing,
        saved_state_and_device_authority_remain_charged,
        typed_refusals_preserve_owner_and_declared_slot_limits,
        aligned_geometric_extent_does_not_merge_across_live_bytes,
        malformed_lifetimes_and_overlap_fail_before_accounting,
        q5_bridge_preserves_absence_instead_of_inventing_owners,
    )]
