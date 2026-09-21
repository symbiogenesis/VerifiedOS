# SPDX-License-Identifier: Apache-2.0
"""Stalled transition bounds over declared per-hart programs for Q22e's cost branch.

A `phase-program-v1` document lists, per hart and slot, alternative request
programs whose gaps are relative to the acceptance of the request before. Under
the zero-wait hypothesis every gap is absolute and the programs expand into the
existing `Contract`; the stalled exploration below instead re-presents a refused
request every cycle, shifts every later request by the accumulated stall,
branches over every maximal arbiter choice and reports per (hart, slot) stall,
boundary-residency and drain bounds. Nothing here extracts traffic from a binary,
models an arbiter's policy, pipeline backpressure or a mode change, or qualifies
an occupancy: the stalled-transition contract states the semantics and the receipt
names what stays open.
"""

import hashlib
import itertools
import re
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from vos import phase_cost, phase_service
from vos.jsonc import Json
from vos.phase_cost import Bound, Comparison
from vos.phase_schedule import (
    Resources,
    _decode,
    _integer,
    _name,
    _object,
    _refresh,
    _resources,
    _rows,
)
from vos.phase_service import Batch, Contract, _fields

SCHEMA = "phase-program-v1"


@dataclass(frozen=True)
class Request:
    bank: int
    operation: str
    occupancy: int
    gap: int


@dataclass(frozen=True)
class Slot:
    name: str
    start: int
    length: int
    alternatives: tuple[tuple[Request, ...], ...]

    @property
    def end(self) -> int:
        return self.start + self.length - 1

    def inside(self, phase: int) -> bool:
        return self.start <= phase <= self.end


@dataclass(frozen=True)
class Program:
    name: str
    program_sha256: str
    resources_sha256: str
    resources: Resources
    bank_names: tuple[str, ...]
    hart_names: tuple[str, ...]
    grants: tuple[int, ...]
    refresh: tuple[Batch, ...]
    harts: tuple[tuple[Slot, ...], ...]

    @property
    def paths(self) -> tuple[int, ...]:
        return tuple(bank.path_cycles for bank in self.resources.banks)


@dataclass(frozen=True)
class Presented:
    hart: str
    bank: str
    operation: str
    accepted: bool


type Cycle = tuple[Presented, ...]


@dataclass(frozen=True)
class Overrun:
    hart: str
    slot: str
    residency: int


@dataclass(frozen=True)
class SlotReport:
    hart: str
    slot: str
    stall_total_max: int
    stall_single_max: int
    boundary_outstanding: bool
    boundary_witness: tuple[Cycle, ...] | None
    boundary_residency_max: int
    drain_max: int
    # Requests of the chosen alternative an occurrence neither accepted nor holds at
    # its slot end: the tail the contract cuts, shifted past the end by accumulated
    # stall or refused beside a held head. Zero whenever nothing stalled.
    cut_max: int


@dataclass(frozen=True)
class Stalled:
    """The stalled exploration's verdicts; `slots` is filled only on closure.

    `closed` is the acceptance-side closure: no `path-blocked`, `refresh-overlap`
    or `residency-overrun` step. A completion inversion sets `ordered` false with
    its trace and the exploration continues, so the stall bounds stay complete.
    """

    closed: bool
    ordered: bool | None
    states: int
    reason: str | None = None
    trace: tuple[Cycle, ...] = ()
    overrun: Overrun | None = None
    inversion: tuple[Cycle, ...] | None = None
    slots: tuple[SlotReport, ...] = ()
    program_zero_wait: bool = False

    @property
    def refuted(self) -> bool:
        return not self.closed or self.ordered is False


@dataclass(frozen=True)
class Analysis:
    name: str
    program_sha256: str
    resources_sha256: str
    bank_names: tuple[str, ...]
    hart_names: tuple[str, ...]
    operation_names: tuple[str, ...]
    contract: Contract
    acceptance: phase_service.Result
    realizable: bool | None
    expansion: str
    zero_wait: bool
    stalled: Stalled
    program_zero_wait: bool
    # Every declared slot as (hart name, slot id, start phase, end phase), present
    # whether or not the exploration closed, so a cost input is validated against the
    # declaration when `stalled.slots` is empty.
    slots: tuple[tuple[str, str, int, int], ...]


def _requests(node: Json, resources: Resources, bank_ids: dict[str, int], limit: int,
              length: int, what: str) -> tuple[Request, ...]:
    requests: list[Request] = []
    run = 0
    total = 0
    for member in _rows(node, what):
        row = _object(member, {"bank", "operation", "gap"}, f"{what} request")
        bank = _name(row["bank"], f"{what} request bank")
        operation = _name(row["operation"], f"{what} request operation")
        if bank not in bank_ids:
            raise ValueError(f"{what} names unknown bank: {bank}")
        durations = resources.banks[bank_ids[bank]].occupancy_cycles
        if operation not in durations:
            raise ValueError(f"bank {bank} has no occupancy for operation {operation}")
        gap = _integer(row["gap"], f"{what} request gap")
        run = run + 1 if requests and gap == 0 else 1
        if run > limit:
            raise ValueError(f"{what} zero-gap run exceeds issue_limit {limit}")
        total += gap
        requests.append(Request(bank_ids[bank], operation, durations[operation], gap))
    if requests and total >= length:
        raise ValueError(f"{what} leaves its slot: gaps sum to {total} against length {length}")
    return tuple(requests)


def _slots(node: Json, hart: str, limit: int, phases: int, resources: Resources,
           bank_ids: dict[str, int], names: set[str]) -> tuple[Slot, ...]:
    slots: list[Slot] = []
    for member in _rows(node, f"{hart} slots"):
        row = _object(member, {"id", "start", "length", "alternatives"}, f"{hart} slot")
        name = _name(row["id"], f"{hart} slot id")
        if name in names:
            raise ValueError(f"duplicate slot id: {name}")
        names.add(name)
        start = _integer(row["start"], f"{name} start")
        length = _integer(row["length"], f"{name} length", 1)
        if start + length > phases:
            raise ValueError(f"slot {name} exceeds the phase count")
        alternatives = tuple(
            _requests(alternative, resources, bank_ids, limit, length, f"{name} alternative {index}")
            for index, alternative in enumerate(_rows(row["alternatives"], f"{name} alternatives",
                                                      nonempty=True)))
        slots.append(Slot(name, start, length, alternatives))
    ordered = sorted(slots, key=lambda slot: slot.start)
    for earlier, later in itertools.pairwise(ordered):
        if earlier.end >= later.start:
            raise ValueError(f"{hart} slots overlap: {earlier.name}, {later.name}")
    return tuple(slots)


def read(program_raw: bytes, resources_raw: bytes) -> Program:
    """Read one program document against the resource bytes its digest binds."""
    data = _object(_decode(program_raw), {"schema", "name", "resources_sha256", "phases", "harts"},
                   "program")
    if data["schema"] != SCHEMA:
        raise ValueError(f"only {SCHEMA} is supported")
    name = _name(data["name"], "program name")
    expected = data["resources_sha256"]
    if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        raise ValueError("resources_sha256 must be a full lowercase SHA-256 digest")
    resources_sha256 = hashlib.sha256(resources_raw).hexdigest()
    if expected != resources_sha256:
        raise ValueError("resources_sha256 does not match the supplied resource bytes")
    resources = _resources(resources_raw)
    bank_ids = {bank.name: index for index, bank in enumerate(resources.banks)}
    grants: list[int] = []
    refresh: list[Batch] = []
    for member in _rows(data["phases"], "phases", nonempty=True):
        row = _object(member, {"grant", "refresh"}, "phase")
        grants.append(_integer(row["grant"], "phase grant"))
        refresh.append(_refresh(row["refresh"], resources, bank_ids))
    harts = data["harts"]
    if not isinstance(harts, dict) or set(harts) != set(resources.harts):
        raise ValueError("harts must map exactly the declared hart names")
    names: set[str] = set()
    slots = tuple(_slots(harts[hart], hart, limit, len(grants), resources, bank_ids, names)
                  for hart, limit in resources.harts.items())
    return Program(name, hashlib.sha256(program_raw).hexdigest(), resources_sha256, resources,
                   tuple(bank_ids), tuple(resources.harts), tuple(grants), tuple(refresh), slots)


def _placements(alternative: tuple[Request, ...]) -> dict[int, list[Request]]:
    """Offset from the slot start to the requests placed there under zero wait."""
    placed: dict[int, list[Request]] = {}
    offset = 0
    for request in alternative:
        offset += request.gap
        placed.setdefault(offset, []).append(request)
    return placed


def _covering(slots: tuple[Slot, ...], phase: int) -> Slot | None:
    for slot in slots:
        if slot.inside(phase):
            return slot
    return None


def expand(program: Program) -> Contract:
    """The zero-wait expansion: joint alternatives are the product over harts."""
    arrivals: list[tuple[Batch, ...]] = []
    for phase in range(len(program.grants)):
        options: list[list[Batch]] = []
        for hart, slots in enumerate(program.harts):
            slot = _covering(slots, phase)
            if slot is None:
                options.append([()])
                continue
            options.append([tuple((request.bank, request.occupancy, hart) for request in
                                  _placements(alternative).get(phase - slot.start, []))
                            for alternative in slot.alternatives])
        arrivals.append(tuple(tuple(itertools.chain.from_iterable(choice))
                              for choice in itertools.product(*options)))
    return Contract(program.grants, tuple(arrivals), len(program.bank_names), program.refresh,
                    program.paths)


def realizable(program: Program, trace: tuple[Batch, ...]) -> bool:
    """Whether one alternative per entered occurrence places exactly the trace's requests."""
    frame = len(program.grants)
    for hart, slots in enumerate(program.harts):
        taken = [tuple((bank, occupancy) for bank, occupancy, owner in map(_fields, batch)
                       if owner == hart) for batch in trace]
        for slot in slots:
            for start in range(slot.start, len(trace), frame):
                covered = range(start, min(start + slot.length, len(trace)))
                if not any(all(tuple((request.bank, request.occupancy) for request in
                                     _placements(alternative).get(cycle - start, [])) == taken[cycle]
                               for cycle in covered) for alternative in slot.alternatives):
                    return False
    return True


# One issued operation: bank, cycles to and including bank acceptance (zero once
# accepted), remaining occupancy, hart. Kept in issue order across harts.
type Op = tuple[int, int, int, int]
# One hart at a boundary: slot index or -1, alternative, program position, cycles
# the head has been refused, cycles before the next run may present, stall in this
# occurrence, refused cycles after the slot end.
type HartState = tuple[int, int, int, int, int, int, int]
type State = tuple[int, tuple[int, ...], tuple[Op, ...], tuple[HartState, ...]]

IDLE: HartState = (-1, 0, 0, 0, 0, 0, 0)


@dataclass
class _Record:
    total: int = 0
    single: int = 0
    outstanding: bool = False
    witness: tuple[Cycle, ...] | None = None
    residency: int = 0
    drain: int = 0
    cut: int = 0


def _run(program: tuple[Request, ...], position: int) -> tuple[Request, ...]:
    """The maximal zero-gap run headed by the request at `position`."""
    end = position + 1
    while end < len(program) and program[end].gap == 0:
        end += 1
    return program[position:end]


def _presentation(slots: tuple[Slot, ...], state: HartState, phase: int) -> tuple[Request, ...]:
    slot, alternative, position, head_wait, delay, _, _ = state
    if slot < 0:
        return ()
    program = slots[slot].alternatives[alternative]
    if position >= len(program):
        return ()
    if head_wait > 0:
        return _run(program, position) if slots[slot].inside(phase) else (program[position],)
    return _run(program, position) if slots[slot].inside(phase) and delay == 0 else ()


def _arbitrations(runs: list[tuple[Request, ...]], occupied: list[int],
                  in_transit: list[list[int]], paths: tuple[int, ...],
                  grant: int) -> list[tuple[int, ...]]:
    """Every maximal prefix-acceptance vector under bank, grant and order constraints."""
    def feasible(counts: tuple[int, ...]) -> bool:
        claimed: set[int] = set()
        total = 0
        for hart, run in enumerate(runs):
            for index in range(counts[hart]):
                request = run[index]
                path = paths[request.bank]
                if total >= grant:
                    return False
                if path == 0:
                    if occupied[request.bank] or request.bank in claimed:
                        return False
                    claimed.add(request.bank)
                if any(remaining > path for remaining in in_transit[hart]):
                    return False
                if any(paths[run[earlier].bank] > path for earlier in range(index)):
                    return False
                total += 1
        return True

    admitted = [counts for counts in itertools.product(*(range(len(run) + 1) for run in runs))
                if feasible(counts)]
    return [counts for counts in admitted
            if not any(counts[hart] < len(runs[hart])
                       and feasible((*counts[:hart], counts[hart] + 1, *counts[hart + 1:]))
                       for hart in range(len(runs)))]


def _drain(ops: list[Op], hart: int, origin: int, exclude: int | None) -> int:
    """Cycles from `origin` (an offset from the current cycle) until the hart's ops complete."""
    drain = 0
    for index, (_, transit, occupancy, owner) in enumerate(ops):
        if owner != hart or index == exclude:
            continue
        completion = transit + occupancy - 1
        drain = max(drain, completion - origin + 1)
    return drain


def explore(program: Program) -> Stalled:
    """Explore the stalled semantics to closure or to the first acceptance-side refutation."""
    frame = len(program.grants)
    paths = program.paths
    harts = program.harts
    starts = [{slot.start: index for index, slot in enumerate(slots)} for slots in harts]
    initial: State = (0, (0,) * len(program.bank_names), (), (IDLE,) * len(harts))
    pending: deque[State] = deque([initial])
    history: dict[State, tuple[Cycle, ...]] = {initial: ()}
    records = {(hart, index): _Record() for hart, slots in enumerate(harts)
               for index in range(len(slots))}
    inversion: tuple[Cycle, ...] | None = None

    def refutation(reason: str, trace: tuple[Cycle, ...], overrun: Overrun | None = None) -> Stalled:
        return Stalled(False, False if inversion else None, len(history), reason, trace, overrun,
                       inversion)

    while pending:
        state = pending.popleft()
        phase, maintenance, ops, hart_states = state
        prefix = history[state]
        choices: list[list[HartState]] = []
        for hart, current in enumerate(hart_states):
            index = starts[hart].get(phase)
            if index is None:
                choices.append([current])
                continue
            if current[3] > 0:
                return refutation("residency-overrun", prefix,
                                  Overrun(program.hart_names[hart], harts[hart][current[0]].name,
                                          current[6]))
            choices.append([(index, choice, 0, 0, alternative[0].gap if alternative else 0, 0, 0)
                            for choice, alternative in enumerate(harts[hart][index].alternatives)])
        occupied = list(maintenance)
        for bank, transit, occupancy, _ in ops:
            if transit == 0:
                occupied[bank] = occupancy
        reserved = list(maintenance)
        for bank, duration in program.refresh[phase]:
            if occupied[bank]:
                return refutation("refresh-overlap", prefix)
            occupied[bank] = duration
            reserved[bank] = duration
        active: list[Op] = []
        for bank, transit, occupancy, owner in ops:
            if transit > 1:
                active.append((bank, transit - 1, occupancy, owner))
            elif transit == 1:
                if occupied[bank]:
                    return refutation("path-blocked", prefix)
                occupied[bank] = occupancy
                active.append((bank, 0, occupancy, owner))
            else:
                active.append((bank, transit, occupancy, owner))
        in_transit = [[transit for _, transit, _, owner in active if owner == hart and transit > 0]
                      for hart in range(len(harts))]
        next_maintenance = tuple(max(0, cycles - 1) for cycles in reserved)
        for chosen in itertools.product(*choices):
            runs = [_presentation(harts[hart], current, phase) for hart, current in enumerate(chosen)]
            for counts in _arbitrations(runs, occupied, in_transit, paths, program.grants[phase]):
                presented: list[Presented] = []
                issued = list(active)
                successors: list[HartState] = []
                # Deferred bookkeeping: (kind, hart, slot, value, origin, excluded op index).
                events: list[tuple[str, int, int, int, int, int | None]] = []
                for hart, current in enumerate(chosen):
                    slot, alternative, position, head_wait, delay, stall, residency = current
                    run, accepted = runs[hart], counts[hart]
                    own: int | None = None
                    for index, request in enumerate(run):
                        presented.append(Presented(program.hart_names[hart],
                                                   program.bank_names[request.bank],
                                                   request.operation, index < accepted))
                        if index < accepted:
                            own = len(issued)
                            issued.append((request.bank, paths[request.bank], request.occupancy, hart))
                    if slot < 0:
                        successors.append(current)
                        continue
                    declared = harts[hart][slot]
                    program_requests = declared.alternatives[alternative]
                    refused = accepted < len(run)
                    if run:
                        if accepted == 0:
                            next_position, next_wait = position, head_wait + 1
                        else:
                            next_position, next_wait = position + accepted, 1 if refused else 0
                        next_delay = (program_requests[next_position].gap - 1
                                      if not refused and next_position < len(program_requests) else 0)
                    else:
                        next_position, next_wait, next_delay = position, head_wait, max(0, delay - 1)
                    if not declared.inside(phase):
                        # Held past the slot end: the head alone is presented until accepted.
                        if refused:
                            successors.append((slot, alternative, position, head_wait, 0, 0,
                                               residency + 1))
                        else:
                            span = paths[run[0].bank] + run[0].occupancy
                            events.append(("residency", hart, slot, residency + span, span, own))
                            successors.append(IDLE)
                        continue
                    next_stall = stall + (1 if refused else 0)
                    record = records[(hart, slot)]
                    record.total = max(record.total, next_stall)
                    record.single = max(record.single, next_wait)
                    if phase == declared.end:
                        held = 1 if next_wait > 0 else 0
                        record.cut = max(record.cut, len(program_requests) - next_position - held)
                    if phase != declared.end:
                        successors.append((slot, alternative, next_position, next_wait, next_delay,
                                           next_stall, 0))
                    elif next_wait > 0:
                        events.append(("outstanding", hart, slot, 0, 0, None))
                        successors.append((slot, alternative, next_position, next_wait, 0, 0, 0))
                    else:
                        events.append(("drain", hart, slot, 0, 1, None))
                        successors.append(IDLE)
                trace = (*prefix, tuple(presented))
                remaining: list[Op] = []
                unfinished: set[int] = set()
                for bank, transit, occupancy, owner in issued:
                    if transit:
                        remaining.append((bank, transit, occupancy, owner))
                        unfinished.add(owner)
                    elif occupancy > 1:
                        remaining.append((bank, 0, occupancy - 1, owner))
                        unfinished.add(owner)
                    elif owner in unfinished and inversion is None:
                        inversion = trace
                for kind, hart, slot, value, origin, exclude in events:
                    record = records[(hart, slot)]
                    if kind == "outstanding":
                        if not record.outstanding:
                            record.outstanding, record.witness = True, trace
                    else:
                        if kind == "residency":
                            record.residency = max(record.residency, value)
                        record.drain = max(record.drain, _drain(issued, hart, origin, exclude))
                successor: State = ((phase + 1) % frame, next_maintenance, tuple(remaining),
                                    tuple(successors))
                if successor not in history:
                    history[successor] = trace
                    pending.append(successor)
    reports = tuple(SlotReport(program.hart_names[hart], slot.name, records[(hart, index)].total,
                               records[(hart, index)].single, records[(hart, index)].outstanding,
                               records[(hart, index)].witness, records[(hart, index)].residency,
                               records[(hart, index)].drain, records[(hart, index)].cut)
                    for hart, slots in enumerate(harts) for index, slot in enumerate(slots))
    zero = all(report.stall_total_max == 0 and not report.boundary_outstanding for report in reports)
    return Stalled(True, inversion is None, len(history), inversion=inversion, slots=reports,
                   program_zero_wait=zero)


def analyze(program_raw: bytes, resources_raw: bytes) -> Analysis:
    """Read, expand, check the expansion, decide realizability and run the stalled exploration."""
    program = read(program_raw, resources_raw)
    contract = expand(program)
    acceptance = phase_service.check(contract)
    realized: bool | None = None
    if acceptance.zero_wait:
        expansion = "closed"
    else:
        realized = realizable(program, acceptance.trace)
        expansion = "refuted" if realized else "unrealizable"
    stalled = explore(program)
    declared = tuple((hart, slot.name, slot.start, slot.end)
                     for hart, slots in zip(program.hart_names, program.harts, strict=True)
                     for slot in slots)
    return Analysis(program.name, program.program_sha256, program.resources_sha256,
                    program.bank_names, program.hart_names, program.resources.operations, contract,
                    acceptance, realized, expansion, acceptance.zero_wait, stalled,
                    stalled.program_zero_wait, declared)


def verify_identity(comparison: Comparison, analysis: Analysis, cost_path: Path,
                    program_path: Path) -> None:
    """The cost input's schedule object must name the program document itself."""
    named = Path(comparison.schedule_path)
    if not named.is_absolute():
        named = cost_path.resolve().parent / named
    mismatches = [f"{field} expected {expected} got {actual}" for field, expected, actual in (
        ("path", program_path.resolve(), named.resolve()),
        ("sha256", analysis.program_sha256, comparison.schedule_sha256),
        ("id", analysis.name, comparison.schedule_id)) if expected != actual]
    if mismatches:
        raise ValueError("cost schedule must name the program document: "
                         + "; ".join(mismatches))


def verify_slots(comparison: Comparison, analysis: Analysis) -> None:
    """Every cost slot names a declared slot, and no two named slots run concurrently.

    A serial admission domain runs one slot at a time, so two named slots on
    different harts whose phase ranges overlap cannot both belong to it; the
    declared ranges decide, so the check stands whether or not the exploration closed.
    """
    declared = {slot_id: (hart, start, end) for hart, slot_id, start, end in analysis.slots}
    named: list[tuple[str, str, int, int]] = []
    for slot in comparison.slots:
        if slot.name not in declared:
            raise ValueError(f"cost slot names no program slot: {slot.name}")
        hart, start, end = declared[slot.name]
        named.append((slot.name, hart, start, end))
    for (first, hart_a, start_a, end_a), (second, hart_b, start_b, end_b) in \
            itertools.combinations(named, 2):
        if hart_a != hart_b and start_a <= end_b and start_b <= end_a:
            raise ValueError(f"cost slots {first} and {second} run concurrently on harts "
                             f"{hart_a} and {hart_b}; a serial admission domain names no "
                             "overlapping slots on different harts")


def _interval(bound: Bound) -> str:
    return "unknown" if bound is None else f"[{bound.low}, {bound.high}]"


def _term(name: str, bound: Bound, required: int, quantity: str = "") -> tuple[str, str | None]:
    """A term's status under the three-way rule and, unless covered, its reason.

    `quantity` names the modeled value in the reason, as in "modeled residency 4",
    and is empty for a term compared with a bound of its own name.
    """
    status = phase_cost.cover(bound, required)
    if status == "covered":
        return status, None
    if status == "unknown":
        return status, f"{name} unknown"
    relation = "below" if status == "refuted" else "overlaps"
    return status, f"{name} declared {_interval(bound)} {relation} modeled {quantity}{required}"


def join(analysis: Analysis, comparison: Comparison) -> dict[str, Json]:
    """Compare declared candidate intervals with the modeled bounds by the three-way rule."""
    if analysis.stalled.refuted:
        raise ValueError("a refuted program contract has no bounds to join")
    verify_slots(comparison, analysis)
    reports = {report.slot: report for report in analysis.stalled.slots}
    statuses: list[str] = []
    reasons: list[Json] = []
    slots: list[Json] = []
    named: list[SlotReport] = []
    cut = False
    for slot in comparison.slots:
        report = reports[slot.name]
        named.append(report)
        stalls, stalls_reason = _term(f"{slot.name}.stalls", slot.candidate.stalls,
                                      report.stall_total_max)
        residency, residency_reason = _term(f"{slot.name}.trap_per_switch",
                                            slot.candidate.trap_per_switch,
                                            report.boundary_residency_max, "residency ")
        # Every occurrence visits the boundary once per frame, so a declared switch
        # count of zero lies below the model on that term.
        switches = "refuted" if slot.switches == 0 else "covered"
        statuses.extend((stalls, residency, switches))
        reasons.extend(reason for reason in (stalls_reason, residency_reason) if reason)
        if residency == "unknown" and report.boundary_outstanding:
            reasons.append("boundary-outstanding-uncovered")
        if switches == "refuted":
            reasons.append(f"{slot.name}.switches declared 0 below the one boundary visit per "
                           "frame the model exhibits")
        if report.cut_max > 0:
            cut = True
            reasons.append(f"{slot.name}: cut_max {report.cut_max}, the modeled bounds exclude "
                           "a cut tail")
        slots.append({"id": slot.name, "hart": report.hart,
                      "stalls": {"declared": phase_cost._json(slot.candidate.stalls),
                                 "modeled": report.stall_total_max, "status": stalls},
                      "residency": {"declared": phase_cost._json(slot.candidate.trap_per_switch),
                                    "modeled": report.boundary_residency_max, "status": residency,
                                    "boundary_outstanding": report.boundary_outstanding},
                      "switches": {"declared": slot.switches, "status": switches},
                      "cut_max": report.cut_max})
    drain_required = max((report.drain_max for report in named), default=0)
    drain, drain_reason = _term("boundary.d_pipe_completion", comparison.d_pipe_completion,
                                drain_required, "drain ")
    statuses.append(drain)
    if drain_reason:
        reasons.append(drain_reason)
    arithmetic = phase_cost.assess(comparison)
    arithmetic_verdict = arithmetic["arithmetic_verdict"]
    if not isinstance(arithmetic_verdict, str):
        raise TypeError("cost analysis returned no arithmetic verdict")
    if arithmetic_verdict != "favorable":
        arithmetic_reason = f"arithmetic: {arithmetic['reason']}"
        if arithmetic_verdict == "open":
            unknown = arithmetic["unknown_operands"]
            if isinstance(unknown, list):
                arithmetic_reason += ": " + ", ".join(str(name) for name in unknown)
        reasons.append(arithmetic_reason)
    if "refuted" in statuses or arithmetic_verdict == "refuted":
        verdict = "refuted"
    elif "unknown" in statuses or cut or arithmetic_verdict == "open":
        verdict = "open"
    elif "inconclusive" in statuses or arithmetic_verdict == "inconclusive":
        verdict = "inconclusive"
    else:
        verdict = arithmetic_verdict
        reasons.append("every named term is covered; the scoped cost arithmetic decides")
    joined = {slot.name for slot in comparison.slots}
    unjoined: list[Json] = [{"hart": report.hart, "slot": report.slot}
                            for report in analysis.stalled.slots if report.slot not in joined]
    return {"join_verdict": verdict, "reasons": reasons, "slots": slots,
            "drain": {"declared": phase_cost._json(comparison.d_pipe_completion),
                      "modeled": drain_required, "status": drain},
            "unjoined": unjoined, "arithmetic": arithmetic}
