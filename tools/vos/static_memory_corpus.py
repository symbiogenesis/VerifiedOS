# SPDX-License-Identifier: Apache-2.0
"""Deterministic research witnesses and a disjoint physical byte ledger.

Every generated service name denotes a synthetic finite trace, not emitted code or
an admitted workload. Timeline boundaries are assumptions. In particular,
``authority_end`` does not prove Q22's semantic completion predicate. A snapshot
fit is neither permission to borrow an arena nor a runtime allocation decision.

Each contract also declares which of the research agenda's families it witnesses and
what its bytes and ticks are assumed to cost. The coverage table and the per-contract
demand series are computed from those labels and from the ledger below; neither is a
measured demand, and a covered family is a witness rather than an admitted workload.
"""

import copy
import hashlib
import json
from itertools import pairwise
from pathlib import Path
from typing import Any, NamedTuple, TypedDict

from vos import memplan
from vos import static_memory as sm

GENERATOR = "tools/vos/static_memory_corpus.py"
SCHEMA = 1
CHARGES = ("useful_payload", "slot_slack", "retained", "quarantined",
           "initializing", "idle_reserved", "layout_gaps", "unreserved_tail")
RETENTION = ("useful_payload", "retained", "quarantined", "initializing")
METADATA = ("provenance", "source_revision", "source_hashes", "manifest", "covers",
            "demand_envelope", "cost_assumptions", "telemetry_label",
            "service_contract", "reuse_semantics")

# The families the research agenda's corpus item names, in the order it names them.
# The vocabulary is closed: a contract labels itself with these and nothing else.
FAMILIES: tuple[str, ...] = (
    "bounded-parsers", "sessions", "rings", "saved-application-state",
    "frame-pipelines", "inference", "crossing-lifetimes", "adversarial-sizes",
    "burst-teardown", "delayed-device-completion")

# The provenance every generated contract carries, and the one a real composed roster
# would carry. No generated contract may claim the second.
WITNESS_PROVENANCE = "synthetic-witness"
ROSTER_PROVENANCE = "composed-roster"


class CaseCosts(TypedDict):
    """What one contract assumes it is paying for, beside the shared cost model."""

    payload_versus_size: str
    alignment: str
    arena_capacity: str


class Spec(NamedTuple):
    """One declared contract before its provenance, identity and series are attached."""

    name: str
    mode: str
    arenas: list[dict[str, Any]]
    objects: list[dict[str, Any]]
    requests: list[dict[str, Any]]
    envelope: str
    covers: tuple[str, ...]
    costs: CaseCosts


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def _costs(payload_versus_size: str, alignment: str, arena_capacity: str) -> CaseCosts:
    return {"payload_versus_size": payload_versus_size, "alignment": alignment,
            "arena_capacity": arena_capacity}


def _object(name: str, arena: str, base: int, size: int, payload: int,
            start: int, payload_end: int, authority_end: int, sweep_end: int,
            reuse: int, alignment: int = 1) -> dict[str, Any]:
    return {"id": name, "arena": arena, "base": base, "size": size,
            "payload": payload, "alignment": alignment, "start": start,
            "payload_end": payload_end, "authority_end": authority_end,
            "sweep_end": sweep_end, "reuse": reuse}


def _arena(name: str, owner: str, capacity: int) -> dict[str, Any]:
    return {"id": name, "owner": owner, "capacity": capacity}


def _request(time: int, owner: str, arena: str, size: int,
             alignment: int = 1) -> dict[str, Any]:
    return {"time": time, "owner": owner, "arena": arena,
            "size": size, "alignment": alignment}


def corpus(source_revision: str) -> list[dict[str, Any]]:
    """Return independent, replayable finite cases with explicit witness costs.

    Units are literal model bytes and ordinal event ticks. Their small magnitudes
    keep exact enumeration useful and intentionally model no actual service sizes.
    One immutable placement serves one declared trace/mode per case. The generator
    has no randomness, target telemetry, environment-driven cost or third party
    dependency. The source digest binds dirty generator contents as well as HEAD.
    """
    if not isinstance(source_revision, str) or not source_revision.strip():
        raise ValueError("source-revision: a nonempty input identity is required")
    specs: list[Spec] = [
        Spec("bounded-parser", "one-record", [_arena("parser", "parser", 24)], [
            _object("input", "parser", 0, 8, 7, 0, 2, 3, 4, 5),
            _object("scratch", "parser", 8, 4, 3, 1, 3, 3, 4, 5),
            _object("result", "parser", 12, 8, 5, 2, 6, 6, 7, 8),
        ], [_request(3, "parser", "parser", 8),
            _request(5, "parser", "parser", 8)],
         "One bounded record; input, scratch and result identities occur once.",
         covers=("bounded-parsers",),
         costs=_costs(
             "each record's useful prefix is shorter than its slot; the rest is live slack",
             "unit alignment; the three slots are consecutive and nothing is pinned",
             "capacity above the reserved span leaves a tail no declared slot can claim")),
        Spec("bounded-sessions", "owner-a-burst", [
            _arena("a-pool", "owner-a", 16), _arena("b-pool", "owner-b", 16)], [
            *[_object(f"a-{i}", "a-pool", i * 4, 4, 3, 0, 4, 5, 6, 7)
              for i in range(4)],
            *[_object(f"b-{i}", "b-pool", i * 4, 4, 2, 8, 10, 10, 11, 12)
              for i in range(4)],
        ], [_request(2, "owner-a", "a-pool", 4),
            _request(2, "owner-a", "b-pool", 4)],
         "Four declared session slots per owner; one owner bursts while the other is idle.",
         covers=("sessions",),
         costs=_costs(
             "every session takes one declared class; its unused bytes stay its owner's charge",
             "unit alignment; a pool's four equal slots are consecutive",
             "each capacity is exactly its four slots, so a fifth session has no backing")),
        Spec("bounded-ring", "two-laps", [_arena("ring", "producer", 16)], [
            _object("lap0-slot0", "ring", 0, 4, 3, 0, 2, 2, 3, 4),
            _object("lap0-slot1", "ring", 4, 4, 4, 1, 3, 3, 4, 5),
            _object("lap1-slot0", "ring", 0, 4, 2, 4, 6, 6, 7, 8),
            _object("lap1-slot1", "ring", 4, 4, 3, 5, 7, 7, 8, 9),
        ], [_request(4, "producer", "ring", 4)],
         "Two slots, two finite laps; a slot is rebound at the preceding reuse boundary.",
         covers=("rings",),
         costs=_costs(
             "a lap's payload varies inside one fixed slot size; the difference is slack",
             "unit alignment; a lap rebinds the preceding base rather than moving it",
             "capacity above the two-slot span is unreserved tail and never a third slot")),
        Spec("saved-application-state", "background-retention", [
            _arena("state", "application", 24)], [
            _object("saved-state", "state", 0, 12, 10, 0, 10, 11, 12, 13),
            _object("foreground-scratch", "state", 12, 8, 6, 1, 3, 4, 5, 6),
        ], [_request(8, "application", "state", 12)],
         "Saved state remains useful resident payload during inactivity; one foreground phase.",
         covers=("saved-application-state",),
         costs=_costs(
             "saved state stays useful payload while its application is inactive",
             "unit alignment; the foreground slot follows the saved slot directly",
             "capacity above the span keeps free geometry visible beside a refusal")),
        Spec("frame-pipeline", "two-frames", [_arena("frames", "media", 32)], [
            _object("capture0", "frames", 0, 8, 8, 0, 2, 3, 4, 5),
            _object("display0", "frames", 8, 12, 10, 1, 5, 6, 7, 8),
            _object("capture1", "frames", 0, 8, 8, 5, 7, 8, 9, 10),
            _object("display1", "frames", 20, 12, 10, 6, 10, 11, 12, 13),
        ], [_request(7, "media", "frames", 12)],
         "Two fixed frame identities; capture completion and display retention are explicit assumptions.",
         covers=("frame-pipelines",),
         costs=_costs(
             "capture is wholly useful; a display frame declares a shorter useful prefix",
             "unit alignment; the second display takes its own slot instead of overlaying",
             "capacity equals the reserved span, so the pipeline keeps no spare backing")),
        Spec("resident-inference", "two-stages", [
            _arena("weights", "inference", 32), _arena("work", "inference", 24)], [
            _object("immutable-weights", "weights", 0, 24, 24, 0, 12, 12, 13, 14),
            _object("activation0", "work", 0, 8, 6, 1, 3, 3, 4, 5),
            _object("activation1", "work", 8, 8, 7, 2, 5, 5, 6, 7),
            _object("kv-state", "work", 16, 8, 7, 0, 12, 12, 13, 14),
        ], [_request(8, "inference", "work", 12)],
         "One resident weight object, one retained KV object and two bounded activation stages.",
         covers=("inference",),
         costs=_costs(
             "the weight object is wholly useful; work objects declare shorter prefixes",
             "unit alignment; three equal work slots are consecutive",
             "the work arena is exactly its three slots; the weight arena keeps a tail")),
        Spec("crossing-lifetimes", "crossing", [_arena("arena", "owner", 16)], [
            _object("a", "arena", 0, 3, 3, 0, 3, 3, 3, 3),
            _object("b", "arena", 4, 4, 4, 1, 5, 5, 5, 5),
            _object("c", "arena", 8, 3, 3, 2, 4, 4, 4, 4),
            _object("d", "arena", 0, 3, 3, 3, 6, 6, 6, 6),
        ], [_request(2, "owner", "arena", 4)],
         "Four fixed identities with crossing intervals; equal boundaries mean completion before rebinding.",
         covers=("crossing-lifetimes",),
         costs=_costs(
             "payload equals the slot for every identity, so no slack hides the crossing",
             "unit alignment; every nonnegative integer base is legal here",
             "capacity above the span leaves an interior layout gap and a tail")),
        Spec("adversarial-alignment", "uneven-extents", [
            _arena("arena", "owner", 24)], [
            _object("odd-a", "arena", 0, 3, 2, 0, 4, 4, 4, 4, 8),
            _object("odd-b", "arena", 8, 5, 3, 0, 4, 4, 4, 4, 8),
            _object("odd-c", "arena", 16, 3, 3, 0, 4, 4, 4, 4, 8),
        ], [_request(5, "owner", "arena", 8),
            _request(5, "owner", "arena", 5, 16)],
         "Three simultaneous odd-sized objects with eight-byte base alignment; no CHERI quantization theorem assumed.",
         covers=("adversarial-sizes",),
         costs=_costs(
             "odd payloads sit inside odd slots; the cost is in the bases, not the extents",
             "eight-byte bases; the declared alignment, not the sizes, sets the span",
             "capacity admits the aligned span and is no representability quantum")),
        Spec("burst-teardown", "simultaneous-retirement", [
            _arena("pool", "service", 24)], [
            *[_object(f"slot-{i}", "pool", i * 4, 4, 3,
                      0, 2, 3, 4 + i, 5 + i) for i in range(4)],
        ], [_request(3, "service", "pool", 4),
            _request(5, "service", "pool", 4)],
         "Four simultaneous retirements; one synthetic slot initialization completes per tick.",
         covers=("burst-teardown",),
         costs=_costs(
             "each slot's payload is shorter than its extent; retirement charges it whole",
             "unit alignment; four consecutive equal slots",
             "capacity above the four slots keeps free bytes visible while all are retired")),
        Spec("delayed-device-completion", "late-completion", [
            _arena("io", "driver", 16)], [
            _object("device-buffer", "io", 0, 8, 7, 0, 2, 8, 9, 10),
            _object("restart-workspace", "io", 8, 8, 4, 3, 5, 6, 7, 8),
        ], [_request(4, "driver", "io", 8),
            _request(8, "driver", "io", 8)],
         "One device transfer retains authority through tick eight while restart work overlaps.",
         covers=("delayed-device-completion",),
         costs=_costs(
             "the transfer buffer's useful prefix ends long before its authority does",
             "unit alignment; the restart workspace follows the device buffer",
             "capacity equals the two declared slots, so the overlap has no spare backing")),
        Spec("multi-owner-burst-teardown", "clustered-retirement", [
            _arena("alpha-pool", "alpha", 10), _arena("beta-pool", "beta", 10),
            _arena("gamma-pool", "gamma", 10)], [
            _object("alpha-0", "alpha-pool", 0, 4, 3, 0, 2, 4, 5, 6),
            _object("alpha-1", "alpha-pool", 4, 4, 4, 0, 3, 4, 5, 6),
            _object("beta-0", "beta-pool", 0, 4, 2, 0, 2, 4, 5, 7),
            _object("beta-1", "beta-pool", 4, 4, 3, 0, 3, 4, 5, 7),
            _object("gamma-0", "gamma-pool", 0, 4, 4, 0, 3, 4, 5, 8),
            _object("gamma-1", "gamma-pool", 4, 4, 1, 0, 3, 4, 5, 8),
        ], [_request(5, "alpha", "alpha-pool", 4),
            _request(6, "alpha", "alpha-pool", 4),
            _request(6, "beta", "alpha-pool", 4)],
         "Synthetic witness: six owner-bound slots retire inside one short window, one "
         "assumed barrier and sweep serve them all, and initialization is staggered so "
         "reuse is deferred owner by owner.",
         covers=("burst-teardown", "sessions"),
         costs=_costs(
             "each slot declares a shorter prefix; a retired slot is charged whole, slack included",
             "unit alignment; two consecutive equal slots per owner",
             "each capacity exceeds its two slots by less than one slot, so the tail fits "
             "no request while every slot is unreusable")),
        Spec("device-completion-window", "accepted-transfer-lag", [
            _arena("dma", "driver", 16)], [
            _object("accepted-transfer", "dma", 0, 8, 6, 0, 2, 7, 8, 9),
            _object("restart-scratch", "dma", 8, 4, 4, 0, 3, 3, 4, 5),
            _object("restart-retry", "dma", 8, 4, 2, 5, 7, 7, 8, 9),
        ], [_request(4, "driver", "dma", 8),
            _request(4, "driver", "dma", 12),
            _request(9, "driver", "dma", 8)],
         "Synthetic witness: one accepted device transfer holds authority for a declared "
         "completion window after its last useful byte, and a request inside that window "
         "is refused while restart work rebinds its own slot.",
         covers=("delayed-device-completion",),
         costs=_costs(
             "the transfer's useful prefix ends at payload_end; the window is charged whole",
             "unit alignment; the retry slot rebinds the restart base after its barrier",
             "capacity above the reserved span is unreserved tail, not a declared slot")),
        Spec("saved-state-across-phases", "three-phases", [
            _arena("resident", "application", 20)], [
            _object("saved-profile", "resident", 0, 10, 8, 0, 14, 15, 16, 17),
            _object("phase0-workspace", "resident", 12, 6, 5, 0, 3, 4, 5, 6, 4),
            _object("phase1-workspace", "resident", 12, 6, 6, 7, 9, 10, 11, 12, 4),
            _object("phase2-workspace", "resident", 12, 6, 4, 13, 14, 14, 14, 15, 4),
        ], [_request(4, "application", "resident", 6),
            _request(6, "application", "resident", 6),
            _request(4, "application", "resident", 10)],
         "Synthetic witness: one saved profile stays useful across three separated phases "
         "whose workspace is rebound only after each reuse barrier completes.",
         covers=("saved-application-state",),
         costs=_costs(
             "the saved profile stays useful payload across every phase and the gaps between",
             "four-byte workspace bases, so a declared layout gap follows the saved slot",
             "capacity admits the aligned workspace end; the standing plan is not its "
             "minimum span, which the exact oracle reports separately")),
        Spec("rotating-inference-activations", "four-rotations", [
            _arena("weights", "inference", 16),
            _arena("activations", "inference", 16)], [
            _object("weight-set", "weights", 0, 16, 16, 0, 10, 11, 12, 13),
            _object("activation-0", "activations", 0, 6, 5, 0, 2, 3, 3, 4, 2),
            _object("activation-1", "activations", 6, 6, 6, 2, 4, 5, 5, 6, 2),
            _object("activation-2", "activations", 0, 6, 4, 4, 6, 7, 7, 8, 2),
            _object("activation-3", "activations", 6, 6, 5, 6, 8, 9, 9, 10, 2),
        ], [_request(3, "inference", "activations", 6),
            _request(0, "inference", "weights", 16),
            _request(11, "inference", "activations", 6)],
         "Synthetic witness: one fixed resident weight set and four rotating activation "
         "buffers whose reservations cross, rebinding two fixed bases in turn.",
         covers=("inference", "crossing-lifetimes"),
         costs=_costs(
             "the weight set is wholly useful; a rotating activation declares a shorter prefix",
             "two-byte activation bases; the rotation rebinds two fixed bases",
             "the weight arena is exactly the resident extent, and the activation tail is "
             "smaller than one rotation slot")),
        Spec("crossing-alignment-gap", "three-stages", [
            _arena("mixed", "codec", 16)], [
            _object("stage-a", "mixed", 0, 6, 5, 0, 2, 3, 3, 4, 4),
            _object("stage-b", "mixed", 8, 6, 6, 2, 4, 5, 5, 6, 4),
            _object("stage-c", "mixed", 4, 4, 3, 4, 6, 7, 7, 8, 4),
        ], [_request(3, "codec", "mixed", 6),
            _request(3, "codec", "mixed", 7),
            _request(8, "codec", "mixed", 6)],
         "Synthetic witness: three stage reservations that cross rather than nest, so the "
         "family is non-laminar by its endpoint order, and whose exact optimum exceeds "
         "their charged load. The declared four-byte bases are the premise that costs the "
         "excess: the same extents and intervals at unit alignment reach the charged load, "
         "so the gap follows from the alignment and not from the crossing.",
         covers=("crossing-lifetimes", "adversarial-sizes"),
         costs=_costs(
             "payload is at or just below each stage's extent, so slack does not make the gap",
             "four-byte stage bases; this premise, not the crossing, is what the optimum pays",
             "capacity admits the optimal span; a smaller arena would refuse the family")),
    ]
    digest = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result: list[dict[str, Any]] = []
    for spec in specs:
        manifest = {"schema": SCHEMA, "generator": GENERATOR,
                    "case": spec.name, "mode": spec.mode, "arenas": spec.arenas,
                    "objects": spec.objects, "requests": spec.requests}
        case: dict[str, Any] = {
            "name": spec.name, "mode": spec.mode, "arenas": spec.arenas,
            "objects": spec.objects, "requests": spec.requests,
            "provenance": WITNESS_PROVENANCE,
            "source_revision": source_revision,
            "source_hashes": {GENERATOR: digest},
            "manifest": {"schema": SCHEMA, "generator": GENERATOR,
                         "sha256": _hash(manifest)},
            "covers": list(family_labels(spec.covers)),
            "telemetry_label": "public-synthetic-host-fixture; no target telemetry",
            "demand_envelope": {"kind": "finite-declared-trace",
                                "description": spec.envelope,
                                "object_occurrences": len(spec.objects),
                                "horizon": max(obj["reuse"] for obj in spec.objects),
                                "all_execution_bound": False},
            "cost_assumptions": {
                "storage_unit": "literal model byte; not a target service size",
                "time_unit": "ordinal event tick; not cycles or elapsed measurement",
                "payload": "constant useful extent until payload_end; saved state remains useful",
                "size": "entire charged slot including synthetic slot slack",
                "target_cycles": None, "target_bandwidth": None, "target_energy": None,
                "unmodeled": ["emitted code", "metadata and capability descriptors",
                              "bank traffic", "deadline proof", "whole-image reservations"],
                "this_case": dict(spec.costs),
            },
            "service_contract": {"kind": "synthetic-witness", "comparison": "no service change",
                                 "product_admission_evidence": False},
            "reuse_semantics": {
                "status": "assumed finite timeline; no authority-completion proof",
                "boundary_order": "half-open lifetimes: end events precede starts at equal ticks",
                "authority_end": "assumed complete resident, saved, loan, proxy and device barrier",
                "sweep_end": "assumed completed full post-barrier sweep",
                "reuse": "assumed required initialization complete",
            },
        }
        parsed = sm.parse_case(case)
        errors = sm.check_placement(parsed, sm.standing_placement(parsed))
        if errors:
            raise sm.CaseError("invalid-generated-standing-placement: " + ", ".join(errors))
        case["demand_series"] = demand_series(case)
        result.append(case)
    audit = family_audit(result)
    for case in result:
        case["family_audit"] = copy.deepcopy(audit)
    return result


def family_labels(value: object) -> tuple[str, ...]:
    """Read one contract's agenda coverage against the closed declared vocabulary.

    An unknown, repeated or missing label is a parse failure rather than an unread
    annotation: the receipt's coverage table is computed from these labels alone, so a
    silent typo would drop a family from that table without moving any other verdict.
    """
    if not isinstance(value, list | tuple) or not value:
        raise sm.CaseError("case.covers: expected a nonempty list of agenda families")
    labels: list[str] = []
    for label in value:
        if not isinstance(label, str) or label not in FAMILIES:
            raise sm.CaseError(f"case.covers: {label!r} is no declared agenda family; "
                               f"declared {list(FAMILIES)}")
        if label in labels:
            raise sm.CaseError(f"case.covers: {label} is declared twice")
        labels.append(label)
    return tuple(labels)


def family_audit(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate the declared labels into the agenda's family coverage table.

    Coverage is computed from the contracts handed in and never declared beside them,
    so a family whose only witness is withdrawn appears here as uncovered. The agenda's
    other named input, a real composed roster, is a provenance no generated contract
    carries; its absence is reported rather than approximated by a synthetic witness.
    """
    covered: dict[str, list[str]] = {family: [] for family in FAMILIES}
    provenances: list[str] = []
    for case in cases:
        parsed = sm.parse_case(case)
        if parsed.provenance not in provenances:
            provenances.append(parsed.provenance)
        for label in family_labels(case.get("covers")):
            covered[label].append(parsed.name)
    return {
        "declared_families": list(FAMILIES),
        "covered": covered,
        "uncovered_families": [family for family in FAMILIES if not covered[family]],
        "contract_provenance": sorted(provenances),
        "composed_roster_present": ROSTER_PROVENANCE in provenances,
        "scope": "agenda-family coverage of the declared synthetic witnesses; a covered "
                 "family is a witness at one finite trace, never an admitted workload",
    }


def demand_series(case: dict[str, Any]) -> dict[str, Any]:
    """Project the existing ledger and load bound into one step function per arena.

    Every figure is read from `ledger`, `event_times`, `peak_load` and
    `placement_spans`; nothing is accounted a second time here. The projection is
    checked against the independently swept charged-load bound, so a step function
    disagreeing with that bound raises instead of being reported as demand.
    """
    parsed = sm.parse_case(case)
    times = event_times(case)
    reports = [ledger(case, time) for time in times]
    spans = sm.placement_spans(parsed, sm.standing_placement(parsed))
    arenas: list[dict[str, Any]] = []
    for arena in parsed.arenas:
        steps = [{"time": report["time"],
                  "charged_bytes": next(row["occupancy"] for row in report["rows"]
                                        if row["arena"] == arena.id)}
                 for report in reports]
        peak = sm.peak_load(parsed, arena.id)
        if max(step["charged_bytes"] for step in steps) != peak:
            raise sm.CaseError(f"charged-load-disagreement: {parsed.name}/{arena.id}")
        arenas.append({"arena": arena.id, "owner": arena.owner,
                       "capacity": arena.capacity, "charged_load": steps,
                       "peak_charged_load": peak, "standing_span": spans[arena.id]})
    return {
        "event_times": times, "arenas": arenas,
        "charge_totals": [{"time": report["time"],
                           **{name: report["totals"][name] for name in RETENTION}}
                          for report in reports],
        "scope": "one finite declared trace; a charged step function is neither a "
                 "measured demand nor an admitted envelope",
    }


def event_times(case: dict[str, Any]) -> list[int]:
    """All times at which a disjoint charge can change, including final idleness."""
    parsed = sm.parse_case(case)
    return sorted({0, *(getattr(obj, field) for obj in parsed.objects
                         for field in ("start", "payload_end", "authority_end",
                                       "sweep_end", "reuse"))})


def _checked(case: dict[str, Any], time: int, alignment: int) -> sm.Case:
    if type(time) is not int or time < 0:
        raise sm.CaseError("invalid-time: expected a nonnegative integer")
    if type(alignment) is not int or alignment <= 0:
        raise sm.CaseError("invalid-alignment: expected a positive integer")
    parsed = sm.parse_case(case)
    errors = sm.check_placement(parsed, sm.standing_placement(parsed))
    if errors:
        raise sm.CaseError("invalid-standing-placement: " + ", ".join(errors))
    return parsed


def _overlap(lo: int, hi: int, other_lo: int, other_hi: int) -> bool:
    return lo < other_hi and other_lo < hi


def _stage(obj: sm.Object, time: int) -> str:
    if time < obj.payload_end:
        return "useful_payload"
    if time < obj.authority_end:
        return "retained"
    if time < obj.sweep_end:
        return "quarantined"
    return "initializing"


def _free_extents(capacity: int, occupied: list[sm.Object]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    cursor = 0
    for obj in sorted(occupied, key=lambda obj: obj.base):
        if cursor < obj.base:
            result.append((cursor, obj.base))
        cursor = obj.base + obj.size
    if cursor < capacity:
        result.append((cursor, capacity))
    return result


def _idle_slots(objects: list[sm.Object], occupied: list[sm.Object]) -> list[sm.Object]:
    return [obj for obj in objects if not any(
        _overlap(obj.base, obj.base + obj.size, active.base, active.base + active.size)
        for active in occupied)]


def ledger(case: dict[str, Any], time: int, alignment: int = 1) -> dict[str, Any]:
    """Partition physical bytes once by owner/arena/mode at one event instant.

    Overlapping placements with disjoint times contribute their union to backing.
    Each arena starts at offset zero and belongs to exactly one owner. Gaps below
    the maximum reserved end and the tail above it are separate. Geometric free
    extents include those gaps; existing idle slot extents do not. Neither means a
    new request may allocate dynamically or survive the next scheduled start.
    """
    parsed = _checked(case, time, alignment)
    rows: list[dict[str, Any]] = []
    for arena in parsed.arenas:
        objects = [obj for obj in parsed.objects if obj.arena == arena.id]
        occupied = [obj for obj in objects if obj.start <= time < obj.reuse]
        span = max((obj.base + obj.size for obj in objects), default=0)
        edges = sorted({0, arena.capacity, span,
                        *(point for obj in objects for point in
                          (obj.base, obj.base + obj.payload, obj.base + obj.size))})
        charges = dict.fromkeys(CHARGES, 0)
        segments: list[dict[str, Any]] = []
        for lo, hi in pairwise(edges):
            if lo == hi:
                continue
            active = next((obj for obj in occupied
                           if obj.base <= lo < obj.base + obj.size), None)
            if active is not None:
                charge = _stage(active, time)
                if charge == "useful_payload" and lo >= active.base + active.payload:
                    charge = "slot_slack"
            elif any(obj.base <= lo < obj.base + obj.size for obj in objects):
                charge = "idle_reserved"
            else:
                charge = "layout_gaps" if lo < span else "unreserved_tail"
            charges[charge] += hi - lo
            segments.append({"base": lo, "end": hi, "bytes": hi - lo,
                             "charge": charge, "object": active.id if active else None})
        free = _free_extents(arena.capacity, occupied)
        largest = max((max(0, hi - ((lo + alignment - 1) // alignment) * alignment)
                       for lo, hi in free), default=0)
        idle = _idle_slots(objects, occupied)
        occupancy = sum(charges[name] for name in CHARGES[:5])
        retired = sum(charges[name] for name in ("retained", "quarantined", "initializing"))
        if sum(charges.values()) != arena.capacity:
            raise sm.CaseError("capacity-conservation: internal ledger error")
        rows.append({
            "owner": arena.owner, "arena": arena.id, "mode": parsed.mode,
            "time": time, "capacity": arena.capacity, "reserved_span": span,
            "reserved_backing": arena.capacity - charges["layout_gaps"] - charges["unreserved_tail"],
            "charges": charges, "occupancy": occupancy,
            "unreusable_retired_bytes": retired, "free_physical_bytes": arena.capacity - occupancy,
            "payload_utilization": {"numerator": charges["useful_payload"], "denominator": arena.capacity},
            "query_alignment": alignment, "largest_free_aligned_extent": largest,
            "largest_idle_declared_slot_extent": max(
                (obj.size for obj in idle if obj.base % alignment == 0), default=0),
            "free_extents": [{"base": lo, "end": hi} for lo, hi in free],
            "segments": segments, "capacity_conserved": True,
        })
    return {"case": parsed.name, "mode": parsed.mode, "time": time,
            **{name: case[name] for name in METADATA if name in case},
            "scope": "one finite trace, one instant; no target measurement or runtime permission",
            "rows": rows,
            "totals": {name: sum(row["charges"][name] for row in rows) for name in CHARGES},
            "total_capacity": sum(row["capacity"] for row in rows),
            "arena_capacities_interchangeable": False}


def diagnose_request(case: dict[str, Any], time: int, owner: str, arena: str,
                     size: int, alignment: int = 1) -> dict[str, Any]:
    """Diagnose one hypothetical request against currently idle declared slots.

    A fit is only a geometric witness at the instant. The request carries no end
    time, future non-overlap proof, slot-binding certificate or authority evidence.
    It never returns an admission verdict or a new runtime placement.
    """
    parsed = _checked(case, time, alignment)
    if type(size) is not int or size <= 0:
        raise sm.CaseError("invalid-request-size: expected a positive integer")
    request = _request(time, owner, arena, size, alignment)
    result: dict[str, Any] = {
        "request": request, "case": parsed.name, "mode": parsed.mode,
        "telemetry_label": case.get("telemetry_label", "unspecified"),
        "runtime_permission": False,
        "scope": "instantaneous fit in an existing slot; no binding or future lifetime checked",
    }
    selected = next((item for item in parsed.arenas if item.id == arena), None)
    if selected is None:
        return {**result, "verdict": "refused", "reason": "unknown-arena"}
    if selected.owner != owner:
        return {**result, "verdict": "refused", "reason": "foreign-owner"}
    objects = [obj for obj in parsed.objects if obj.arena == arena]
    occupied = [obj for obj in objects if obj.start <= time < obj.reuse]
    shaped = [obj for obj in objects if obj.size >= size]
    aligned = [obj for obj in shaped if obj.base % alignment == 0]
    idle = _idle_slots(aligned, occupied)
    row = next(row for row in ledger(case, time, alignment)["rows"] if row["arena"] == arena)
    result.update({key: row[key] for key in
                   ("free_physical_bytes", "largest_free_aligned_extent",
                    "largest_idle_declared_slot_extent", "unreusable_retired_bytes")})
    if idle:
        return {**result, "verdict": "fits-at-instant", "reason": None,
                "slot_witnesses": sorted({(obj.base, obj.size) for obj in idle})}
    if not shaped:
        reason = "slot-size"
    elif not aligned:
        reason = "slot-alignment"
    elif any(active.payload_end <= time and _overlap(
            slot.base, slot.base + slot.size, active.base, active.base + active.size)
             for slot in aligned for active in occupied):
        reason = "reuse-pending"
    else:
        reason = "slot-occupied"
    return {**result, "verdict": "refused", "reason": reason}


def q5_bridge(root: Path, source_revision: str) -> dict[str, Any]:
    """Carry Q5's existing exporter whole, with absent semantic fields left absent.

    The proof witness has no owner or completion fields and is deliberately not
    coerced into this corpus's operational schema. A real roster must supply
    those inputs before a meaningful per-owner safe-reuse ledger can be made.
    """
    source = memplan.read(root)
    exported = memplan.export(source)
    plan = memplan.plan_of(source, memplan.STANDING)
    source_paths = (memplan.SOURCE, "tools/vos/memplan.py", GENERATOR)
    return {
        "schema": SCHEMA, "provenance": "q5-proof-witness-export",
        "source_revision": source_revision,
        "source_hashes": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                          for name in source_paths},
        "telemetry_label": "public-proof-witness; no measured product roster",
        "q5_export": exported,
        "standing_refusals": memplan.refused_by(plan),
        "island_scores": [{"island": island,
                           "capacity": plan.island_span(island),
                           "live_footprint": memplan.score(plan, island).footprint,
                           "reserved_span": memplan.score(plan, island).span_used,
                           "padding": memplan.score(plan, island).padding}
                          for island in plan.island_ids()],
        "operational_ledger": {"verdict": "unavailable",
                               "reason": "missing-owner-and-completion-contract",
                               "missing": ["owner", "payload", "payload_end", "authority_end",
                                           "sweep_end", "reuse", "demand_envelope",
                                           "whole-image-costs"]},
        "product_admission_evidence": False,
    }
