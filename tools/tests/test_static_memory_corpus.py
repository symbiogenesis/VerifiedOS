# SPDX-License-Identifier: Apache-2.0
"""Capacity conservation, delayed reuse, isolation and source-bound witness labels."""

import copy
import hashlib
import itertools
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from tests.harness import Case, ensure
from vos import memplan
from vos import static_memory as sm
from vos import static_memory_corpus as c

# The contracts that stood before the coverage work, each with the two digests that
# bind the model other lanes read: the manifest's, over the case name, mode, arenas,
# objects and diagnostic requests, and the parsed contract's, over what the placement
# model itself receives. The whole case dictionary cannot be pinned, because it carries
# the generator's own SHA-256 and so moves with any edit to that file; these two do not,
# and a change to either is a change to a witness another lane already reads.
BASE_REVISION_CONTRACTS: tuple[tuple[str, str, str], ...] = (
    ("bounded-parser",
     "9574a37739947be9555b40f47db9f1a578635480fc6c4a6d790d5e798a981b08",
     "3c908558529264bdad81f58b368081c1fad62b88a87ab828e71cbeef504fd03a"),
    ("bounded-sessions",
     "1c18b6ef7a1ead8892eef3e08e64bd0f28a858105a3c39d9c62f8db3560520e0",
     "6c9e9be2bc80ac4af841f3181d75c67b80bc4f1e04a32fd7ce0b49930e4ac734"),
    ("bounded-ring",
     "b31e950383e08050657cd95aaae04c8d4294bec8cb43b690d4b62b63106cdff4",
     "4aef8d5f3c0dc18e2481b30b28c8c5d163aefe3d6e505a1d90ac190f8984f32f"),
    ("saved-application-state",
     "80d34047f453bf6f65f0873140efaf6521d15df1acd79cad512c175dbe6f9e92",
     "cdffd402a60e4f7ed794dcc4982786e6a0426d9d971b2d709a87305218485ff3"),
    ("frame-pipeline",
     "28aea4ee0f733b3a06a677fbdeb61d70138ead46b9d6809fe586ed8446f19ee1",
     "dde719e68545f733d9290a618d5e42fa7274b36097aeb0acb9a295ac992852f8"),
    ("resident-inference",
     "b05e81754768a0b16aa0758ed638fb165b02dc1e4153e5dd1222c8491a750d58",
     "6fc0f4b5bb4280e9e76f40f124f91a04492bbe5421833954c8f5a1f6ed484989"),
    ("crossing-lifetimes",
     "3eea9612d3af0bd6d4a23da02ea0ed2fe0ae656840cba28fc420b9ca3b9a43f4",
     "b7d28026f5bf41c3ddd1e18b786260f771751774056591d690cd260826e2588f"),
    ("adversarial-alignment",
     "70dc2359f7890deae477dcb531ec5e003f2e194f364e627ae13516aba1e54dc1",
     "c3fe1bb9e2855c31e16b47731a4691788839e51442c718d34138bddd11aeb384"),
    ("burst-teardown",
     "a857db25b92f70a63e95b4e5d623fad2b2aa63765a207d460567061aa0937dc1",
     "952a5aafa6436a48f6da00a160d446e3b3b24cdb5e09e2cca014e977209b85fb"),
    ("delayed-device-completion",
     "72c112312aa39d9f9376d918f188c16c5de2677fc07a3786eab9e0a5bf07b521",
     "6fc10545f9253ca07e881cde626dc8ee6b42bd73347c6e7491a2f7384b5d174a"),
)


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


def existing_contracts_keep_their_base_revision_identities() -> None:
    # Other lanes read these witnesses; new coverage appends and never edits one.
    cases = c.corpus("test-revision")
    pinned = len(BASE_REVISION_CONTRACTS)
    ensure(len(cases) > pinned, "the coverage contracts must append to the corpus")
    for case, (name, manifest, contract) in zip(cases[:pinned], BASE_REVISION_CONTRACTS,
                                                strict=True):
        ensure(case["name"] == name, f"contract order moved at {case['name']}")
        ensure(case["manifest"]["sha256"] == manifest,
               f"{name}: its declared arenas, objects, mode or requests changed")
        ensure(sm.contract_hash(sm.parse_case(case)) == contract,
               f"{name}: the contract the placement model receives changed")


def every_contract_declares_exact_fields_and_an_accepted_standing_plan() -> None:
    arena_fields = {"id", "owner", "capacity"}
    object_fields = {"id", "arena", "size", "payload", "alignment", "start",
                     "payload_end", "authority_end", "sweep_end", "reuse", "base"}
    cost_fields = {"payload_versus_size", "alignment", "arena_capacity"}
    for case in c.corpus("test-revision"):
        parsed = sm.parse_case(case)
        ensure(all(set(arena) == arena_fields for arena in case["arenas"]),
               f"{parsed.name}: an arena carries an unread or missing field")
        ensure(all(set(obj) == object_fields for obj in case["objects"]),
               f"{parsed.name}: an object carries an unread or missing field")
        ensure(not sm.check_placement(parsed, sm.standing_placement(parsed)),
               f"{parsed.name}: the standing placement is not accepted")
        costs = case["cost_assumptions"]["this_case"]
        ensure(set(costs) == cost_fields and all(value.strip() for value in costs.values()),
               f"{parsed.name}: a per-contract cost assumption is missing")
        ensure(bool(c.family_labels(case["covers"])), f"{parsed.name}: no agenda coverage")


def family_audit_is_computed_from_a_closed_label_vocabulary() -> None:
    cases = c.corpus("test-revision")
    audit = c.family_audit(cases)
    ensure(audit["declared_families"] == list(c.FAMILIES),
           "the audited vocabulary is not the agenda's family list")
    ensure(not audit["uncovered_families"],
           f"agenda families without a witness: {audit['uncovered_families']}")
    ensure(audit["contract_provenance"] == [c.WITNESS_PROVENANCE],
           "a generated contract claimed a provenance it cannot have")
    ensure(not audit["composed_roster_present"],
           "a synthetic witness was counted as a real composed roster")
    ensure(all(case["family_audit"] == audit for case in cases),
           "a receipt carries a coverage table other than the computed one")
    # Withdrawing the only witness of a family must move the table, not a note beside it.
    thinned = copy.deepcopy(cases)
    for case in thinned:
        case["covers"] = [label for label in case["covers"]
                          if label != "frame-pipelines"] or ["rings"]
    ensure("frame-pipelines" in c.family_audit(thinned)["uncovered_families"],
           "coverage is declared beside the labels instead of computed from them")
    for broken in (["not-a-family"], ["rings", "rings"], [], "rings", None):
        try:
            c.family_labels(broken)
        except sm.CaseError:
            continue
        raise AssertionError(f"the closed vocabulary accepted {broken!r}")


def demand_series_projects_the_ledger_and_an_independent_load_sweep() -> None:
    for case in c.corpus("test-revision"):
        series, times = case["demand_series"], c.event_times(case)
        ensure(series["event_times"] == times, "the series skipped a charge boundary")
        ensure(series == c.demand_series(case), "the embedded series is not reproducible")
        for row in series["arenas"]:
            # An independent sweep of declared extents, not the byte partition's answer.
            live = [{"time": time,
                     "charged_bytes": sum(obj["size"] for obj in case["objects"]
                                          if obj["arena"] == row["arena"]
                                          and obj["start"] <= time < obj["reuse"])}
                    for time in times]
            ensure(row["charged_load"] == live,
                   f"{case['name']}/{row['arena']}: charged step function differs")
            ensure(row["peak_charged_load"] == max(item["charged_bytes"] for item in live),
                   "the peak is not the maximum of its own step function")
            ensure(row["standing_span"] == max(
                (obj["base"] + obj["size"] for obj in case["objects"]
                 if obj["arena"] == row["arena"]), default=0),
                "the standing span is not the highest declared slot end")
            ensure(row["peak_charged_load"] <= row["standing_span"] <= row["capacity"],
                   "charged load, span and capacity left the baseline's ordering")
        for time, totals in zip(times, series["charge_totals"], strict=True):
            report = c.ledger(case, time)
            ensure(totals["time"] == time, "a retention row lost its instant")
            ensure(all(totals[name] == report["totals"][name] for name in c.RETENTION),
                   "the retained-versus-payload series differs from the ledger")


def delayed_completion_refusal_reproduces_through_diagnose_request() -> None:
    case = _case("device-completion-window")
    transfer = next(obj for obj in case["objects"] if obj["id"] == "accepted-transfer")
    window = range(transfer["payload_end"], transfer["authority_end"])
    ensure(len(window) > 1, "the completion window must lag the last useful byte")
    for time in window:
        answer = c.diagnose_request(case, time, "driver", "dma", transfer["size"])
        ensure(answer["verdict"] == "refused" and answer["reason"] == "reuse-pending",
               f"a request inside the completion window was not refused at {time}")
        ensure(c.ledger(case, time)["rows"][0]["charges"]["retained"] == transfer["size"],
               "lagging device authority stopped charging its whole slot")
    ensure(c.diagnose_request(case, transfer["payload_end"] - 1, "driver", "dma",
                              transfer["size"])["reason"] == "slot-occupied",
           "a transfer still holding useful payload was refused as pending reuse")
    ensure(c.diagnose_request(case, transfer["reuse"], "driver", "dma",
                              transfer["size"])["verdict"] == "fits-at-instant",
           "the slot stayed refused after its declared initialization completed")


def burst_reuse_deferral_is_visible_in_the_ledger() -> None:
    case = _case("multi-owner-burst-teardown")
    sweeps = {obj["sweep_end"] for obj in case["objects"]}
    ensure(len(sweeps) == 1, "the burst must share one clustered sweep completion")
    sweep = sweeps.pop()
    for row in c.ledger(case, sweep)["rows"]:
        ensure(row["charges"]["initializing"] == row["reserved_span"],
               f"{row['arena']}: the whole pool is not awaiting initialization")
        ensure(row["unreusable_retired_bytes"] == row["reserved_span"]
               and row["free_physical_bytes"] == row["capacity"] - row["reserved_span"],
               f"{row['arena']}: swept bytes were counted as available")
    ensure(c.diagnose_request(case, sweep, "alpha", "alpha-pool", 4)["reason"]
           == "reuse-pending", "a swept slot was offered before its initialization")
    reuses = sorted({obj["reuse"] for obj in case["objects"]})
    ensure(len(reuses) > 1, "the burst must stagger its initialization service")
    rows = c.ledger(case, reuses[0])["rows"]
    ready = [row["arena"] for row in rows if row["charges"]["idle_reserved"]]
    waiting = [row["arena"] for row in rows if row["charges"]["initializing"]]
    ensure(len(ready) == 1 and len(waiting) == len(rows) - 1,
           "staggered reuse did not separate the owners at the first reuse boundary")


def crossing_optimum_exceeds_load_only_under_the_declared_alignment() -> None:
    case = sm.parse_case(_case("crossing-alignment-gap"))
    receipt = sm.solve_exact(case)
    arena = receipt["arenas"][0]
    ensure(receipt["status"] == "optimal" and arena["optimality_gap"] == 0,
           "the separation witness must carry a completed optimum")
    ensure(arena["best_span_over_load"] > 0,
           "the witness must separate its optimum from charged load")
    ensure(sm.verify_optimality(case, receipt)["status"] == "verified",
           "the separation must survive the independent optimality replay")
    spans = [(obj.start, obj.reuse) for obj in case.objects]
    ensure(any(a < x < b < y or x < a < y < b
               for (a, b), (x, y) in itertools.combinations(spans, 2)),
           "the witness family is laminar and so cannot carry this negative result")
    # The excess is the alignment premise's, not the crossing's: relax one and it goes.
    unit = replace(case, objects=tuple(replace(obj, alignment=1) for obj in case.objects))
    relaxed = sm.solve_exact(unit)
    ensure(relaxed["status"] == "optimal"
           and relaxed["arenas"][0]["best_span_over_load"] == 0,
           "the same extents and intervals at unit alignment must reach charged load")


def cases() -> list[Case]:
    return [Case(fn.__name__, fn) for fn in (
        deterministic_identity_and_explicit_assumptions,
        existing_contracts_keep_their_base_revision_identities,
        every_contract_declares_exact_fields_and_an_accepted_standing_plan,
        family_audit_is_computed_from_a_closed_label_vocabulary,
        demand_series_projects_the_ledger_and_an_independent_load_sweep,
        byte_enumeration_independently_checks_every_snapshot,
        retirement_stages_charge_slot_slack_only_once,
        equal_boundaries_rebind_without_double_charging_backing,
        saved_state_and_device_authority_remain_charged,
        delayed_completion_refusal_reproduces_through_diagnose_request,
        burst_reuse_deferral_is_visible_in_the_ledger,
        crossing_optimum_exceeds_load_only_under_the_declared_alignment,
        typed_refusals_preserve_owner_and_declared_slot_limits,
        aligned_geometric_extent_does_not_merge_across_live_bytes,
        malformed_lifetimes_and_overlap_fail_before_accounting,
        q5_bridge_preserves_absence_instead_of_inventing_owners,
    )]
