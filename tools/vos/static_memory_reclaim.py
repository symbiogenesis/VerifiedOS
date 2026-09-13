# SPDX-License-Identifier: Apache-2.0
"""Conditional fixed-schedule reclamation and capacity research, in synthetic ticks.

The timing model is deliberately separate from Q22's authority model. Neither
its holder-footprint premise nor its service rates are target qualifications.
The calendar's two holder terms are derived from Q22a's fixture holder map: a
holder kind that neither lifecycle stage retires refuses the calendar instead of
disappearing into a fixed group count.
"""

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from math import lcm
from pathlib import Path
from typing import Any, Literal, TypedDict

from vos import revocation as authority

SCHEMA = "static-memory-reclamation-v2"
SCOPE = ("conditional synthetic fixed calendar and finite host traces; "
         "no target rates or theorem")

type Stage = Literal["containment", "post-barrier-pass"]
type Signature = tuple[authority.Place, bool, bool, bool, bool]


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
    protocol_ticks: int = 4
    containment_bytes_per_tick: int = 40


@dataclass(frozen=True)
class Policy:
    name: str
    release_phases: tuple[int, ...]
    pass_period: int
    sweep_ticks: int = 4
    sweep_bytes_per_tick: int = 16
    zero_ticks: int = 4
    zero_bytes_per_tick: int = 16


@dataclass(frozen=True)
class HolderClass:
    """One Q22a holder kind, its structural signature and its declared charge.

    `containment_bytes` is charged when containment retires the kind and
    `sweep_bytes` when the post-barrier full pass reaches it. A kind charged at
    neither stage is unaccounted and refuses the calendar. The charge is per
    class, so more holders of a mapped kind move no calendar term.
    """

    name: str
    members: tuple[str, ...]
    place: authority.Place
    remote: bool
    borrowed: bool
    covered: bool
    retired_authority: bool
    containment_bytes: int
    sweep_bytes: int
    prefix: str = ""

    def signature(self) -> Signature:
        return (self.place, self.remote, self.borrowed, self.covered,
                self.retired_authority)

    def stages(self) -> tuple[Stage, ...]:
        charged: tuple[tuple[Stage, int], ...] = (
            ("containment", self.containment_bytes),
            ("post-barrier-pass", self.sweep_bytes))
        return tuple(stage for stage, charge in charged if charge)

    def matches(self, name: str) -> bool:
        return name in self.members or (bool(self.prefix) and name.startswith(self.prefix))


class ClassRow(TypedDict):
    """One holder class actually present in the supplied composition."""

    name: str
    stages: tuple[Stage, ...]
    holders: tuple[str, ...]
    containment_bytes: int
    sweep_bytes: int
    cleared_by_containment: bool
    visited_by_pass: bool


# Every kind Q22a's fixture supplies, with the stage its own model reaches it at.
# `coverage` rechecks both the signature and the stage against that model, so this
# table cannot drift from the qualification it claims to cover.
HOLDER_CLASSES: tuple[HolderClass, ...] = (
    HolderClass("live-general-root", ("register",), "live", False, False, True, True, 16, 0),
    HolderClass("live-special-root", ("mepcc",), "live", False, False, True, True, 16, 0),
    HolderClass("borrowed-live-root", ("callee",), "live", False, True, False, True, 16, 0),
    HolderClass("remote-delegate-root", ("remote-register",), "live", True, False, True,
                True, 16, 0),
    HolderClass("loan-copy", ("loan-copy",), "saved", False, True, False, True, 16, 8),
    HolderClass("saved-context", ("saved",), "saved", False, False, True, True, 0, 8),
    HolderClass("trusted-stack-root", ("trusted-stack",), "saved", False, False, True,
                True, 0, 8),
    HolderClass("grant-storage", ("grant-storage",), "memory", False, False, True, True, 0, 8),
    HolderClass("outside-interval-copy", ("outside-interval-copy",), "memory", False,
                False, True, True, 0, 8),
    HolderClass("proxy-slot", ("proxy-slot",), "memory", True, False, True, True, 0, 8),
    HolderClass("unrelated-grant", ("unrelated-grant",), "memory", False, False, False,
                False, 0, 8),
    HolderClass("interior-representation", (), "memory", False, False, True, True, 0, 8,
                prefix="interior-"),
)

# A Q22a refusal reason belongs to exactly one reclamation stage. The completion
# vocabulary withholds the barrier; the reuse vocabulary withholds reuse after a
# pass the schedule has already paid for.
COMPLETION_REASONS = frozenset({
    "holder-map", "sweep-map", "holder-shape", "loading-island", "composition-shape",
    "proxy-map", "acknowledgement-failure", "publication", "new-invocation",
    "authority", "outstanding-loan", "remote-acknowledgement", "device-completion"})
PASS_REASONS = frozenset({"post-barrier-full-pass", "reuse-resurrection"})


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


def service_ticks(work_bytes: int, bytes_per_tick: int) -> int:
    """Whole reserved ticks for one stage's charge; a partial tick is not service."""
    if type(work_bytes) is not int or type(bytes_per_tick) is not int or bytes_per_tick < 1:
        raise ValueError("a stage charge needs a positive integer service rate")
    return (work_bytes + bytes_per_tick - 1) // bytes_per_tick


def signature(comp: authority.Composition, holder: authority.Holder) -> Signature:
    """The structural facts Q22a's own fields decide; the holder name decides none."""
    root = min(comp.cores)
    return (holder.place, holder.core != root, bool(holder.cap.loan),
            (holder.cap.island, holder.cap.base // authority.GRANULE) in comp.targets,
            holder.cap.retired)


def with_holder(comp: authority.Composition, state: authority.State,
                holder: authority.Holder) -> tuple[authority.Composition, authority.State]:
    """Admit one more holder into the finite map, keeping its sweep inventory exact."""
    if holder.name in comp.holders:
        raise ValueError("an added holder needs a name the composition does not hold")
    stored = frozenset({holder.name}) if holder.place != "live" else frozenset()
    return (replace(comp, holders=comp.holders | {holder.name},
                    swept=comp.swept | stored),
            replace(state, holders=(*state.holders, holder)))


def coverage(comp: authority.Composition, initial: authority.State,
             classes: tuple[HolderClass, ...] = HOLDER_CLASSES) -> dict[str, Any]:
    """Classify every holder the composition supplies and derive its stage charges.

    Coverage is relative to Q22a's supplied map and admitted shapes. It discovers
    no holder in a compiled image and proves no relation to one.
    """
    errors: list[str] = []
    names = [item.name for item in classes]
    if len(set(names)) != len(names):
        errors.append("duplicate holder class")
    errors.extend("composition:" + reason for reason in authority.map_errors(comp, initial))
    if initial.clock or initial.bits or initial.invocations_closed:
        errors.append("coverage requires the initial composition state")
    cleared: dict[str, bool] = {}
    try:
        contained = authority.ready(comp, initial)
    except authority.RevocationError as exc:
        errors.append(f"containment-unreachable:{exc}")
    else:
        cleared = {holder.name: not holder.cap.tag for holder in contained.holders}
    assigned: dict[str, list[str]] = {}
    for holder in initial.holders:
        found = [item for item in classes if item.matches(holder.name)]
        if len(found) != 1:
            errors.append(("ambiguous-holder:" if found else "unclassified-holder:")
                          + holder.name)
            continue
        if signature(comp, holder) != found[0].signature():
            errors.append(f"signature:{found[0].name}/{holder.name}")
        assigned.setdefault(found[0].name, []).append(holder.name)
    rows: list[ClassRow] = []
    for item in classes:
        members = assigned.get(item.name)
        if members is None:
            continue
        scrubbed = bool(cleared) and all(cleared.get(name) for name in members)
        visited = all(name in comp.swept for name in members)
        if not item.stages():
            errors.append(f"unaccounted-class:{item.name}")
        if bool(item.containment_bytes) != scrubbed:
            errors.append(f"containment-stage:{item.name}")
        if bool(item.sweep_bytes) != visited:
            errors.append(f"pass-stage:{item.name}")
        rows.append({"name": item.name, "stages": item.stages(),
                     "holders": tuple(members),
                     "containment_bytes": item.containment_bytes,
                     "sweep_bytes": item.sweep_bytes,
                     "cleared_by_containment": scrubbed, "visited_by_pass": visited})
    containment_bytes = sum(row["containment_bytes"] for row in rows)
    sweep_bytes = sum(row["sweep_bytes"] for row in rows)
    if not containment_bytes or not sweep_bytes:
        errors.append("empty containment or post-barrier inventory")
    return {"classes": rows, "holders": len(initial.holders),
            "containment_bytes": containment_bytes, "sweep_bytes": sweep_bytes,
            "errors": errors,
            "scope": "coverage relative to Q22a's fixture holder map and admitted "
                     "shapes; no holder discovery in a compiled image"}


def calendar_terms(env: Envelope, policy: Policy, cov: dict[str, Any]) -> dict[str, int]:
    """C and S count the holder classes present, at their declared per-class charge.

    Containment also pays the protocol obligations that belong to no holder class:
    publication, proxy notification, device completion and proxy acknowledgement.
    """
    if cov["errors"]:
        raise ValueError("an unaccounted holder class cannot derive a calendar term")
    return {"containment_ticks": env.protocol_ticks + service_ticks(
                cov["containment_bytes"], env.containment_bytes_per_tick),
            "sweep_ticks": service_ticks(cov["sweep_bytes"], policy.sweep_bytes_per_tick)}


def derived(env: Envelope, policy: Policy,
            terms: dict[str, int]) -> tuple[Envelope, Policy]:
    """Install the two holder-derived terms; every other calendar input is unchanged."""
    return (replace(env, containment_ticks=terms["containment_ticks"]),
            replace(policy, sweep_ticks=terms["sweep_ticks"]))


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
                      failed: frozenset[int] = frozenset(),
                      refused_reuse: frozenset[int] = frozenset()) -> list[dict[str, Any]]:
    """Full-demand witness with per-pass zero service; never invent an overflow slot.

    A failed containment remains retained forever in this finite observation, and
    so does a request the post-barrier reuse gate refuses after its pass. A refused
    reuse keeps its reserved cohort position rather than releasing it to a peer.
    The caller must check reservation feasibility before claiming availability.
    """
    validate(env, policy)
    if type(cycles) is not int or not 1 <= cycles <= 100:
        raise ValueError("finite replay requires one to one hundred periods")
    if any(type(index) is not int or not 0 <= index < cycles * env.requests
           for group in (failed, refused_reuse) for index in group):
        raise ValueError("failed identity is outside the finite request calendar")
    if failed & refused_reuse:
        raise ValueError("one request cannot be refused at two stages")
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
                "terminal_at": barrier if index in failed else None,
                "terminal_stage": "containment" if index in failed else None,
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
            if row["id"] in refused_reuse:
                row.update(status="reuse-gate-refused", terminal_at=row["sweep_end"],
                           terminal_stage="post-barrier-pass")
            elif position >= policy.zero_ticks:
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
            elif obj["terminal_at"] is not None and tick >= obj["terminal_at"]:
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


def refusal_stage(reasons: list[str]) -> str:
    """Route one Q22a refusal to the schedule stage that must withhold service."""
    tokens = {reason.split(":", 1)[0] for reason in reasons}
    if not reasons or not tokens <= COMPLETION_REASONS | PASS_REASONS:
        return "unrouted"
    return "containment" if tokens & COMPLETION_REASONS else "post-barrier-pass"


def refusal_schedule(env: Envelope, policy: Policy) -> dict[str, Any]:
    """Replay every Q22a counterexample at the schedule stage its own reasons name.

    A completion refusal never reaches a barrier, so its extent stays charged from
    the failure decision. A reuse refusal reaches and pays for its post-barrier
    pass and is still denied reuse, so its extent stays charged from the pass end.
    """
    horizon = env.period + 4 * policy.pass_period
    stages = {"containment": scheduled_records(env, policy, 1, failed=frozenset({0})),
              "post-barrier-pass": scheduled_records(env, policy, 1,
                                                     refused_reuse=frozenset({0}))}
    errors: list[str] = []
    outcomes: dict[str, dict[str, Any]] = {}
    for stage, records in stages.items():
        row = records[0]
        ledger = timeline(env, records, horizon)
        outcomes[stage] = {
            "status": row["status"], "release": row["release"], "barrier": row["barrier"],
            "pass_start": row["pass_start"], "sweep_end": row["sweep_end"],
            "reuse": row["reuse"], "terminal_at": row["terminal_at"],
            "terminal_stage": row["terminal_stage"], "horizon": horizon,
            "retained_bytes_at_horizon": ledger[-1]["failed_retention"],
            "occupied_backing_at_horizon": ledger[-1]["occupied_backing"]}
        if row["reuse"] is not None or ledger[-1]["failed_retention"] != env.extent_bytes:
            errors.append(f"{stage}: a refused request regained reusable backing")
    if outcomes["containment"]["barrier"] is not None:
        errors.append("containment: a refused containment issued a barrier")
    if (outcomes["post-barrier-pass"]["barrier"] is None
            or outcomes["post-barrier-pass"]["sweep_end"]
            != outcomes["post-barrier-pass"]["terminal_at"]):
        errors.append("post-barrier-pass: the refusal did not follow a completed pass")
    cases: list[dict[str, Any]] = []
    for name, reasons in authority.counterexamples():
        stage = refusal_stage(reasons)
        if stage == "unrouted":
            errors.append(f"unrouted Q22a refusal: {name}")
        outcome = outcomes.get(stage, {})
        cases.append({"case": name, "reasons": reasons, "stage": stage,
                      "schedule_status": outcome.get("status"),
                      "reuse": outcome.get("reuse"),
                      "terminal_stage": outcome.get("terminal_stage")})
    return {"stages": outcomes, "cases": cases, "errors": errors,
            "scope": "every Q22a counterexample routed by its own reasons; the "
                     "schedule withholds service, it does not requalify the barrier"}


def variant(name: str, note: str, env: Envelope, policy: Policy,
            comp: authority.Composition, initial: authority.State,
            classes: tuple[HolderClass, ...]) -> dict[str, Any]:
    """One composition's coverage, its derived calendar terms and its bound."""
    cov = coverage(comp, initial, classes)
    row: dict[str, Any] = {
        "variant": name, "note": note, "errors": cov["errors"],
        "holders": cov["holders"],
        "present_classes": [item["name"] for item in cov["classes"]],
        "containment_bytes": cov["containment_bytes"],
        "sweep_bytes": cov["sweep_bytes"]}
    if cov["errors"]:
        return row | {"status": "coverage-refused", "containment_ticks": None,
                      "sweep_ticks": None, "release_to_reuse": None, "terms": None}
    terms = calendar_terms(env, policy, cov)
    contract = bounds(*derived(env, policy, terms))
    return row | {"status": contract["status"], **terms,
                  "release_to_reuse": contract["release_to_reuse"],
                  "terms": {key: contract.get(key) for key in ("C", "W", "S", "Z")}}


def holder_coverage(env: Envelope, policy: Policy,
                    classes: tuple[HolderClass, ...] = HOLDER_CLASSES) -> dict[str, Any]:
    """Derive the holder terms from Q22a's fixture and move them by changing kinds."""
    comp, initial = authority.fixture()
    cap = next(holder.cap for holder in initial.holders if holder.name == "saved")
    saved_class = HolderClass("vector-save-area", ("vector-save-area",), "saved",
                              False, False, True, True, 0, 8)
    root_class = HolderClass("timer-root", ("timer-root",), "live",
                             False, False, True, True, 16, 0)
    grown = with_holder(comp, initial,
                        authority.Holder("vector-save-area", "saved", 0, cap))
    rooted = with_holder(comp, initial, authority.Holder("timer-root", "live", 0, cap))
    stale = tuple(replace(item, containment_bytes=16) if item.name == "saved-context"
                  else item for item in classes)
    rows = [
        variant("q22a-fixture", "the qualification fixture's own composition",
                env, policy, comp, initial, classes),
        variant("wider-retired-object", "more holders of a mapped kind, no new kind",
                env, policy, *authority.fixture(8), classes),
        variant("extra-saved-context-class", "one more kind the post-barrier pass reaches",
                env, policy, *grown, (*classes, saved_class)),
        variant("extra-live-root-class", "one more kind containment retires",
                env, policy, *rooted, (*classes, root_class)),
        variant("unmapped-holder-class", "the same added holder with no kind mapped",
                env, policy, *grown, classes),
        variant("misdeclared-stage", "a mapped kind charged at a stage that does not retire it",
                env, policy, comp, initial, stale),
    ]
    base = rows[0]
    for row in rows[1:]:
        row["delta_release_to_reuse"] = (
            None if row["release_to_reuse"] is None or base["release_to_reuse"] is None
            else row["release_to_reuse"] - base["release_to_reuse"])
    named = {row["variant"]: row for row in rows}
    errors: list[str] = []
    if base["errors"]:
        errors.append("Q22a fixture holder coverage is incomplete")
    if named["wider-retired-object"]["sweep_ticks"] != base["sweep_ticks"]:
        errors.append("more holders of one mapped kind changed the class-charged pass term")
    added = named["extra-saved-context-class"]
    if (added["sweep_ticks"] is None or base["sweep_ticks"] is None
            or added["sweep_ticks"] <= base["sweep_ticks"]
            or added["delta_release_to_reuse"] is None
            or added["delta_release_to_reuse"] <= 0):
        errors.append("an added pass kind did not lengthen the pass term and the bound")
    lifted = named["extra-live-root-class"]
    if (lifted["containment_ticks"] is None
            or lifted["containment_ticks"] <= base["containment_ticks"]):
        errors.append("an added containment kind did not lengthen the containment term")
    errors.extend(f"{name}: an unaccounted holder kind did not refuse the calendar"
                  for name in ("unmapped-holder-class", "misdeclared-stage")
                  if not named[name]["errors"])
    return {"classes": [asdict(item) for item in classes], "variants": rows,
            "base": coverage(comp, initial, classes), "errors": errors,
            "scope": "class-charged terms over Q22a's fixture and admitted shapes; "
                     "no production holder roster and no measured service rate"}


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


SOURCES = ("tools/vos/static_memory_reclaim.py", "tools/tests/test_static_memory_reclaim.py",
           "tools/vos/revocation.py", "docs/assurance/revocation-qualification.md",
           "docs/implementation/static-memory-baseline.md",
           "docs/implementation/static-memory-reclamation.md")


def report(root: Path, classes: tuple[HolderClass, ...] = HOLDER_CLASSES) -> dict[str, Any]:
    """Return a deterministic replay receipt; the shared CLI adds Git identity."""
    declared = Envelope()
    late = (declared.result_phase,) * declared.requests
    early = tuple(range(1, declared.requests + 1))
    template = Policy("declared", late, 24)
    comp, initial = authority.fixture()
    cov = coverage(comp, initial, classes)
    hashes = {name: sha256((root / name).read_bytes()).hexdigest() for name in SOURCES}
    if cov["errors"]:
        return {"schema": SCHEMA, "scope": SCOPE,
                "holder_coverage": {"base": cov, "variants": [], "errors": cov["errors"],
                                    "classes": [asdict(item) for item in classes],
                                    "scope": cov["scope"]},
                "errors": ["holder coverage refuses the calendar: "
                           + ", ".join(cov["errors"])],
                "sources_sha256": hashes}
    terms = calendar_terms(declared, template, cov)
    env, _ = derived(declared, template, terms)
    sweep = terms["sweep_ticks"]
    policies = (Policy("deferred-slow", late, 24, sweep_ticks=sweep),
                Policy("eager-slow", early, 24, sweep_ticks=sweep),
                Policy("deferred-faster", late, 12, sweep_ticks=sweep),
                Policy("eager-faster", early, 12, sweep_ticks=sweep),
                Policy("overreserved-sweep", early, 6, sweep_ticks=sweep))
    scenarios = [experiment(env, policy) for policy in policies]
    storm_env = replace(env, requests=8)
    storm = experiment(storm_env, Policy("restart-burst-outside-service-envelope",
                                         (8,) * 8, 24, sweep_ticks=sweep))
    failed = scheduled_records(env, policies[0], 2, frozenset(range(env.requests)))
    failure_rows = timeline(env, failed, 3 * env.period)
    checks = semantic_checks()
    coverage_block = holder_coverage(env, policies[0], classes)
    refusals = refusal_schedule(env, policies[0])
    errors = [f"{item['policy']['name']}: {error}" for item in scenarios
              for error in item.get("errors", [])]
    errors.extend(coverage_block["errors"])
    errors.extend(refusals["errors"])
    if (declared.containment_ticks, template.sweep_ticks) != (env.containment_ticks, sweep):
        errors.append("declared calendar defaults no longer match the Q22a holder terms")
    if (checks["positive_reuse_errors"] or not checks["premature_bit_clear_exposes"]
            or any(not case["refusals"] for case in checks["cases"])):
        errors.append("Q22 semantic positive/refusal witness failed")
    baseline, _, _, joint, _ = scenarios
    return {
        "schema": SCHEMA,
        "scope": SCOPE,
        "envelope": asdict(env),
        "service_contract": {
            "arrival_rule": "a subset of four named requests at each multiple of 24 ticks",
            "results": "same deterministic result per request, visible only at public phase 8",
            "computation": "four independent one-tick tasks at phases 0..3; results copied to permanent outbox",
            "retirement_change": "deferred release holds inputs until delivery; eager release follows each task",
            "permanent_charge": "64 synthetic bytes for control, descriptors and result outbox in every variant",
            "containment": "the protocol obligations that belong to no holder class, "
                           "publication, proxy notification, device completion and proxy "
                           "acknowledgement, plus the declared charge of every holder "
                           "class containment retires, padded exactly to C",
            "control_cost": "each active request consumes two synthetic bytes per containment tick; concurrent pipelines must fit the fixed control grant",
            "holder_coverage": "one declared charge for each Q22a holder class actually "
                               "present, classified from the qualification fixture and "
                               "assigned to the stage that retires it; complete coverage "
                               "and no repopulation remain premises",
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
        "holder_coverage": coverage_block,
        "stage_refusals": refusals,
        "semantic_checks": checks, "errors": errors,
        "sources_sha256": hashes,
    }
