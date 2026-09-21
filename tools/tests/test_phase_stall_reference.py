# SPDX-License-Identifier: Apache-2.0
"""An independent bounded-horizon reference for the stalled exploration.

The simulator below is *not* `phase_stall.explore`. It was written from the text of
the [stall contract](../../docs/implementation/phase-service/stall-contract.md) and
the [completion conventions](../../docs/implementation/phase-service/completion-model.md)
before the module's exploration was read, and it never imports the module's step
functions: only `analyze` and the field names of its `Stalled` report. It keeps
absolute cycle times and walks every history through each frame as a tree. Two
implementations that share no code and agree on every reported field are evidence
the fields follow from the contract rather than from one loop's arithmetic.

Conventions, each traced to a sentence of the contract:

  C1  "Each cycle refresh reserves first, requests completing transit accept next,
      and each hart then presents its next request, or its zero-gap run."
  C2  "a request issued in cycle t with path p ... is accepted at its bank in cycle
      t+p"; occupancy includes the acceptance cycle, so an occupancy n accepted in
      cycle a completes at the end of cycle a+n-1.
  C3  "A request that cannot be accepted at issue ... holds the hart: it is
      re-presented every following cycle until accepted, the hart presents nothing
      else while held, and ... every later request shifts by the accumulated stall."
  C4  "A presented run is accepted by prefix in issue order"; "a cycle in which any
      presented request of a hart is refused adds one to that hart's stall whatever
      the run's width"; "a member refused beside a refused predecessor is not itself
      held until that predecessor is accepted."
  C5  The in-step order interlock: the hart waits at issue until every earlier
      request of its own still in transit after this cycle's transit step, a member
      earlier in the same presented run included, reaches its bank no later than
      this request would; acceptance within one cycle counts as ordered.
  C6  "each cycle branches over every maximal set of presented requests that
      respects one acceptance per bank, the phase grant and per-hart issue order";
      "A re-presented request counts against the grant of the cycle it is finally
      accepted at issue in and no other."
  C7  "Programs restart at their slot's start phase every frame with the alternative
      chosen afresh"; a request still held when the same hart's next slot occurrence
      begins is a `residency-overrun`, reported for the slot whose head is held.
  C8  `stalls` counts refused cycles up to and including the slot's last cycle;
      `stall_single_max` is one request's hold from its earliest issue to its
      acceptance at issue, truncated at the slot end; a head held at the slot end is
      boundary-outstanding, keeps being presented alone, and its residency runs from
      the first cycle after the slot end through its completion.
  C9  `drain_max` runs from the first cycle after the end of residency, the slot end
      when nothing was held, through the completion of everything the hart has
      issued and still has outstanding; `cut_max` counts the chosen alternative's
      requests neither accepted nor held at the slot end. The campaign adjudicated
      C9's span: the Outputs section says "until the last operation the hart issued
      in that occurrence completes", which differs from the hart-wide span exactly
      when an occurrence issues nothing, or completion order is inverted, while an
      earlier occurrence's operation is still outstanding. The hart-wide span is
      what the switch after that slot has outstanding, the per-switch operand
      `d_pipe_completion` covers, and the conservative one; the `adjudicated` case
      pins the programs where the readings part.
  C10 `ordered` is the completion-order predicate over the same histories: one
      hart's later operation never completes before an earlier one; an inversion
      refutes without stopping, whereas `path-blocked`, `refresh-overlap` and
      `residency-overrun` stop the exploration at the step, so the stop reported is
      the earliest reachable one and `ordered` reads an inversion only before it.

Horizon. Every quantity above is decided within one frame from the situation at
that frame's first boundary, provided the situation carries the residual occupancy,
the operations in flight with their occurrence, and each hart's held head with its
slot end. Inside a frame the reference walks every history as a tree, every
alternative entered and every maximal arbiter choice, with nothing merged. Across
frames it walks each frame-boundary situation, expressed relative to its boundary,
once: the continuation from a situation is a function of the situation alone, so a
second walk from it would find the same occurrences, refutations and finalisations
at later cycles. Frames are taken in order, so a situation is walked at the first
frame it can be reached in and every event is found at its earliest cycle; the
situations are finite, since residues are bounded by the longest occupancy plus path
and every counter restarts each frame, so the walk ends when no new situation
appears. Walking each situation once rather than once per history is the one place
the reference merges anything, and it merges at frame boundaries only, on a
situation built from absolute times rather than from the module's per-boundary
counters; a step cap and a frame cap guard against a runaway and are reported,
never silently absorbed.
"""

import hashlib
import itertools
import json
import random
import time
from dataclasses import dataclass, field, replace

from tests.harness import TOOLS, Case, ensure
from vos.phase_stall import Stalled, analyze

EXAMPLES = TOOLS.parent / "docs" / "implementation" / "phase-service" / "program-examples"
FIXTURES = ("refresh-stall", "joint-loser", "split-run", "path-wait", "boundary-outstanding",
            "worked-tail")

# The campaign is seeded and fixed so a failure is reproducible from this module
# alone. The size is set by the module's wall-time budget, not by a coverage claim.
CAMPAIGN_SEED = 20260920
CAMPAIGN_COUNT = 10000
# Frames one branch may run, and cycles one walk may take in all, before the walk
# reports itself as capped; a capped walk decides nothing and the campaign says so.
MAX_FRAMES = 64
MAX_STEPS = 200_000


# --------------------------------------------------------------------------
# Program representation, independent of the module's dataclasses
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class RefBank:
    name: str
    path: int
    occupancy: tuple[tuple[str, int], ...]
    refresh: int | None

    def cycles(self, operation: str) -> int:
        return dict(self.occupancy)[operation]


@dataclass(frozen=True)
class RefRequest:
    bank: int
    operation: str
    gap: int


@dataclass(frozen=True)
class RefSlot:
    name: str
    start: int
    length: int
    alternatives: tuple[tuple[RefRequest, ...], ...]

    @property
    def end(self) -> int:
        return self.start + self.length - 1


@dataclass(frozen=True)
class RefProgram:
    harts: tuple[str, ...]
    limits: tuple[int, ...]
    banks: tuple[RefBank, ...]
    grants: tuple[int, ...]
    refresh: tuple[tuple[int, ...], ...]
    slots: tuple[tuple[RefSlot, ...], ...]

    @property
    def phases(self) -> int:
        return len(self.grants)


@dataclass(frozen=True)
class Conventions:
    """Four contract sentences the positive control bends, each exact by default.

    `charge_presented` charges the grant for every presented request, accepted or
    not, in hart order (against C6). `interlock` False drops C5. `residency_from_end`
    counts the slot end itself as residency (against C8). `cut` False skips C9's term.
    `drain_occurrence_only` is the literal Outputs reading of C9's span, kept so the
    adjudication stays visible.
    """

    charge_presented: bool = False
    interlock: bool = True
    residency_from_end: bool = False
    cut: bool = True
    drain_occurrence_only: bool = False


EXACT = Conventions()


# --------------------------------------------------------------------------
# One history's situation, in absolute cycle time
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Op:
    hart: int
    bank: int
    issue: int
    accept: int
    complete: int
    occurrence: int


@dataclass(frozen=True)
class HartSim:
    """One hart: idle, inside a slot, or holding a head past its slot end."""

    mode: str = "idle"
    slot: int = -1
    alt: int = -1
    end: int = -1
    pos: int = 0
    prev: int = 0
    stall: int = 0
    single: int = 0
    occurrence: int = 0
    ops: tuple[Op, ...] = ()


@dataclass(frozen=True)
class Sim:
    busy: tuple[int, ...]
    harts: tuple[HartSim, ...]


type HartCanonical = tuple[str, int, int, int, int, tuple[tuple[int, int, int, bool], ...]]
type Canonical = tuple[tuple[int, ...], tuple[HartCanonical, ...]]


@dataclass
class SlotTally:
    stall: int = 0
    single: int = 0
    outstanding: bool = False
    witness: int | None = None
    residency: int = 0
    drain: int = 0
    cut: int = 0


@dataclass
class Tally:
    """Everything the walk found: stops, overruns, the earliest inversion, the slot maxima."""

    slots: dict[tuple[int, int], SlotTally]
    stops: dict[str, int] = field(default_factory=dict)
    overruns: set[tuple[int, int, int, int]] = field(default_factory=set)
    inversion: int | None = None
    capped: bool = False
    frames: int = 0
    choices: int = 0
    steps: int = 0

    @property
    def stop_cycle(self) -> int | None:
        return min(self.stops.values(), default=None)

    def stop(self, reason: str, cycle: int) -> None:
        if reason not in self.stops or self.stops[reason] > cycle:
            self.stops[reason] = cycle


# --------------------------------------------------------------------------
# One cycle
# --------------------------------------------------------------------------

def _alternative(program: RefProgram, h: int, hs: HartSim) -> tuple[RefRequest, ...]:
    return program.slots[h][hs.slot].alternatives[hs.alt]


def _presented(program: RefProgram, harts: list[HartSim], t: int) -> dict[int, list[int]]:
    """C3 and C4: each hart's presented run, as positions in its chosen alternative.

    A hart presents when its head's earliest issue, the previous acceptance plus the
    gap, has arrived; inside the slot the head brings its zero-gap successors, past
    the slot end a held head is presented alone (C8).
    """
    runs: dict[int, list[int]] = {}
    for h, hs in enumerate(harts):
        if hs.mode == "idle":
            continue
        alt = _alternative(program, h, hs)
        if hs.pos >= len(alt) or hs.prev + alt[hs.pos].gap > t:
            continue
        members = [hs.pos]
        if hs.mode == "slot":
            following = hs.pos + 1
            while following < len(alt) and alt[following].gap == 0:
                members.append(following)
                following += 1
        runs[h] = members
    return runs


def _admits(program: RefProgram, hs: HartSim, req: RefRequest, earlier: list[int],
            busy: list[int], taken: set[int], used: int, grant: int, t: int,
            conv: Conventions) -> bool:
    """Whether one more member can be accepted at issue in cycle `t`.

    `earlier` holds the paths of this run's members accepted before it this cycle.
    C6: the grant and one acceptance per zero-path bank; C5: every earlier request of
    the hart still in transit after this cycle, `accept > t`, must reach its bank no
    later than this one would, `t + path`.
    """
    if used >= grant:
        return False
    bank = program.banks[req.bank]
    if bank.path == 0 and (busy[req.bank] >= t or req.bank in taken):
        return False
    if conv.interlock:
        latest = t + bank.path
        if any(op.accept > t and op.accept > latest for op in hs.ops):
            return False
        if any(path > 0 and t + path > latest for path in earlier):
            return False
    return True


def _maximal(program: RefProgram, harts: list[HartSim], runs: dict[int, list[int]],
             busy: list[int], t: int, grant: int, conv: Conventions) -> list[dict[int, int]]:
    """C6: every maximal arbiter choice, as accepted prefix lengths per presenting hart.

    A choice is feasible when each accepted member is admitted in turn, and maximal
    when no hart could take one more member under the banks and grant it leaves.
    """
    order = sorted(runs)
    vectors: list[dict[int, int]] = []
    for lengths in itertools.product(*(range(len(runs[h]) + 1) for h in order)):
        taken: set[int] = set()
        used = 0
        feasible = True
        for h, k in zip(order, lengths, strict=True):
            alt = _alternative(program, h, harts[h])
            paths: list[int] = []
            for index in runs[h][:k]:
                req = alt[index]
                if not _admits(program, harts[h], req, paths, busy, taken, used, grant, t, conv):
                    feasible = False
                    break
                if program.banks[req.bank].path == 0:
                    taken.add(req.bank)
                used += 1
                paths.append(program.banks[req.bank].path)
            if not feasible:
                break
            if conv.charge_presented:
                used += len(runs[h]) - k
        if not feasible:
            continue
        extendable = False
        for h, k in zip(order, lengths, strict=True):
            if k == len(runs[h]):
                continue
            alt = _alternative(program, h, harts[h])
            paths = [program.banks[alt[index].bank].path for index in runs[h][:k]]
            if _admits(program, harts[h], alt[runs[h][k]], paths, busy, taken, used, grant, t,
                       conv):
                extendable = True
                break
        if not extendable:
            vectors.append(dict(zip(order, lengths, strict=True)))
    return vectors


def _last_completion(hs: HartSim, ops: tuple[Op, ...], conv: Conventions, floor: int) -> int:
    """C9: the end of the drain, the last completion among what the hart has outstanding."""
    return max((op.complete for op in ops
                if not conv.drain_occurrence_only or op.occurrence == hs.occurrence),
               default=floor)


def _slot_end(program: RefProgram, h: int, hs: HartSim, t: int, tally: Tally,
              conv: Conventions) -> HartSim:
    """C8 and C9 at the slot's last cycle `t`, after its arbitration.

    A head whose earliest issue has arrived and that is still unaccepted was refused
    this cycle: it is boundary-outstanding, its hold is truncated here, its zero-gap
    successors are cut, and the hart keeps presenting it. Otherwise the occurrence
    ends, every unaccepted request was shifted past the end, and the drain runs from
    the next cycle through the last completion.
    """
    alt = _alternative(program, h, hs)
    report = tally.slots[(h, hs.slot)]
    report.stall = max(report.stall, hs.stall)
    single = hs.single
    if hs.pos < len(alt) and hs.prev + alt[hs.pos].gap <= t:
        single = max(single, t + 1 - (hs.prev + alt[hs.pos].gap))
        cut = len(alt) - hs.pos - 1
        report.outstanding = True
        report.witness = t if report.witness is None else min(report.witness, t)
        mode = "residency"
    else:
        cut = len(alt) - hs.pos
        report.drain = max(report.drain, _last_completion(hs, hs.ops, conv, t) - t)
        mode = "idle"
    report.single = max(report.single, single)
    if conv.cut:
        report.cut = max(report.cut, cut)
    return replace(hs, mode=mode, single=single)


def _accept(program: RefProgram, harts: list[HartSim], runs: dict[int, list[int]],
            vector: dict[int, int], busy: list[int], t: int, tally: Tally,
            conv: Conventions) -> Sim:
    """Apply one arbiter choice, then the cycle's completions and slot ends."""
    busy = list(busy)
    harts = list(harts)
    for h, members in runs.items():
        hs = harts[h]
        alt = _alternative(program, h, hs)
        ops = list(hs.ops)
        pos, prev, single = hs.pos, hs.prev, hs.single
        for index in members[:vector[h]]:
            req = alt[index]
            bank = program.banks[req.bank]
            accept = t + bank.path
            complete = accept + bank.cycles(req.operation) - 1
            ops.append(Op(h, req.bank, t, accept, complete, hs.occurrence))
            if bank.path == 0:
                busy[req.bank] = complete
            if hs.mode == "slot":
                single = max(single, t - (prev + req.gap))
            prev, pos = t, index + 1
        stall = hs.stall + (1 if hs.mode == "slot" and vector[h] < len(members) else 0)
        mode = hs.mode
        if hs.mode == "residency" and vector[h] == 1:
            head = ops[-1]
            report = tally.slots[(h, hs.slot)]
            residency = head.complete - hs.end + (1 if conv.residency_from_end else 0)
            last = _last_completion(hs, tuple(ops), conv, head.complete)
            report.residency = max(report.residency, residency)
            report.drain = max(report.drain, last - head.complete)
            mode = "idle"
        harts[h] = replace(hs, mode=mode, pos=pos, prev=prev, stall=stall, single=single,
                           ops=tuple(ops))
    # C10: completion order at the end of cycle t, per hart in issue order.
    for hs in harts:
        for index, op in enumerate(hs.ops):
            if op.complete == t and any(earlier.complete > t for earlier in hs.ops[:index]):
                tally.inversion = t if tally.inversion is None else min(tally.inversion, t)
    for h, hs in enumerate(harts):
        if hs.mode == "slot" and hs.end == t:
            harts[h] = _slot_end(program, h, hs, t, tally, conv)
    harts = [replace(hs, ops=tuple(op for op in hs.ops if op.complete > t)) for hs in harts]
    return Sim(tuple(busy), tuple(harts))


def run_cycle(program: RefProgram, sim: Sim, t: int, tally: Tally,
              conv: Conventions) -> list[Sim]:
    """Cycle `t` from the boundary before its refresh: every successor, none on a stop.

    C7 first: a slot occurrence beginning while its hart still holds a head is a
    `residency-overrun`. Then C1: refresh, transit acceptances, presentation, and one
    branch per alternative entered and per maximal arbiter choice (C6).
    """
    phase = t % program.phases
    busy = list(sim.busy)
    harts = list(sim.harts)
    starters: list[tuple[int, int]] = []
    for h, hs in enumerate(harts):
        for s, slot in enumerate(program.slots[h]):
            if slot.start != phase:
                continue
            if hs.mode == "residency":
                tally.stop("residency-overrun", t)
                tally.overruns.add((t, h, hs.slot, t - hs.end - 1))
                return []
            starters.append((h, s))
    for bank in program.refresh[phase]:
        cycles = program.banks[bank].refresh
        if cycles is None:
            raise ValueError(f"bank {program.banks[bank].name} declares no refresh")
        if busy[bank] >= t:
            tally.stop("refresh-overlap", t)
            return []
        busy[bank] = t + cycles - 1
    for hs in harts:
        for op in hs.ops:
            if op.accept == t and op.issue < t:
                if busy[op.bank] >= t:
                    tally.stop("path-blocked", t)
                    return []
                busy[op.bank] = op.complete
    successors: list[Sim] = []
    ranges = [range(len(program.slots[h][s].alternatives)) for h, s in starters]
    for combo in itertools.product(*ranges):
        entered = list(harts)
        for (h, s), alt in zip(starters, combo, strict=True):
            entered[h] = HartSim("slot", s, alt, t + program.slots[h][s].length - 1, 0, t, 0, 0,
                                 entered[h].occurrence + 1, entered[h].ops)
        runs = _presented(program, entered, t)
        vectors = _maximal(program, entered, runs, busy, t, program.grants[phase], conv)
        if len(vectors) > 1:
            tally.choices += 1
        successors.extend(_accept(program, entered, runs, vector, busy, t, tally, conv)
                          for vector in vectors)
    return successors


# --------------------------------------------------------------------------
# The walk
# --------------------------------------------------------------------------

def _canonical(sim: Sim, t: int) -> Canonical:
    """The situation at boundary `t` with its times shifted to `t`, for the branch cut.

    It carries exactly what decides a later frame: residual occupancy, every live
    operation with whether it belongs to the occurrence still in residency, and for a
    hart in residency its held head and slot end.
    """
    def hart(hs: HartSim) -> HartCanonical:
        residency = hs.mode == "residency"
        ops = tuple((op.bank, op.accept - t, op.complete - t,
                     residency and op.occurrence == hs.occurrence) for op in hs.ops)
        return (hs.mode, hs.slot if residency else -1, hs.alt if residency else -1,
                hs.pos if residency else 0, hs.end - t if residency else 0, ops)

    return tuple(max(last - t, -1) for last in sim.busy), tuple(hart(hs) for hs in sim.harts)


def _walk_frame(program: RefProgram, sim: Sim, start: int, tally: Tally,
                conv: Conventions) -> list[Sim]:
    """Every history through the frame beginning at `start`, as a tree; its end boundaries.

    Cycles past the earliest stop are dropped, since a stop is reported from that
    cycle and the slot maxima are reported only on closure; the stop's own cycle
    still runs on every branch, because `ordered` may still read an inversion there.
    """
    boundaries: list[Sim] = []
    stack: list[tuple[int, Sim]] = [(start, sim)]
    end = start + program.phases
    while stack:
        t, current = stack.pop()
        tally.steps += 1
        if tally.steps > MAX_STEPS:
            tally.capped = True
            return boundaries
        stop = tally.stop_cycle
        if stop is not None and t > stop:
            continue
        if t == end:
            boundaries.append(current)
            continue
        stack.extend((t + 1, following) for following in run_cycle(program, current, t, tally, conv))
    return boundaries


def simulate(program: RefProgram, conv: Conventions = EXACT) -> Tally:
    """Walk every history from the empty start at phase zero, frame by frame.

    Each frame is a tree walk from its first boundary; a boundary situation already
    walked is not walked again, and frames are taken in order, so a situation is
    walked at the first frame it can be reached in and every event is found at its
    earliest cycle. The walk ends when no new situation appears, or after the frame
    in which the earliest stop lies.
    """
    tally = Tally({(h, s): SlotTally() for h, slots in enumerate(program.slots)
                   for s in range(len(slots))})
    frame = program.phases
    root = Sim(tuple(-1 for _ in program.banks), tuple(HartSim() for _ in program.harts))
    level = [root]
    known = {_canonical(root, 0)}
    number = 0
    while level and not tally.capped:
        if number >= MAX_FRAMES:
            tally.capped = True
            break
        tally.frames = number
        following: list[Sim] = []
        for sim in level:
            for boundary in _walk_frame(program, sim, number * frame, tally, conv):
                key = _canonical(boundary, (number + 1) * frame)
                if key not in known:
                    known.add(key)
                    following.append(boundary)
        if tally.stop_cycle is not None:
            break
        level = following
        number += 1
    return tally


# --------------------------------------------------------------------------
# The differential comparison, one entry per field of the module's report
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class RefSlotReport:
    stall_total_max: int
    stall_single_max: int
    boundary_outstanding: bool
    boundary_residency_max: int
    drain_max: int
    cut_max: int
    witness_cycles: int | None


def reference_slots(program: RefProgram, tally: Tally) -> dict[tuple[str, str], RefSlotReport]:
    """The per-(hart, slot) report the walk decided, keyed by names."""
    return {
        (program.harts[h], program.slots[h][s].name): RefSlotReport(
            entry.stall, entry.single, entry.outstanding, entry.residency, entry.drain,
            entry.cut, None if entry.witness is None else entry.witness + 1)
        for (h, s), entry in tally.slots.items()}


def compare(program: RefProgram, stalled: Stalled, tally: Tally) -> list[str]:
    """Every field of the module's `Stalled` report against the walk; empty on agreement.

    A stop is compared by its earliest reachable cycle: the module's reason must be
    one reachable there and its trace must end there. `ordered` reads an inversion
    before the stop; at the stop's own cycle either reading is accepted, since the
    contract fixes no order between a step's stop and that cycle's completions.
    """
    found: list[str] = []
    stop = tally.stop_cycle
    inversion = tally.inversion
    if stop is not None:
        reasons = sorted(reason for reason, cycle in tally.stops.items() if cycle == stop)
        if stalled.closed:
            found.append(f"closed: module closes, reference stops at cycle {stop} with {reasons}")
            return found
        if stalled.reason not in reasons:
            found.append(f"reason: module {stalled.reason}, reference {reasons} at cycle {stop}")
        if len(stalled.trace) != stop:
            found.append(f"trace: module {len(stalled.trace)} cycles, reference stop at {stop}")
        if stalled.reason == "residency-overrun":
            facts = {(program.harts[h], program.slots[h][s].name, residency)
                     for cycle, h, s, residency in tally.overruns if cycle == stop}
            overrun = stalled.overrun
            reported = None if overrun is None else (overrun.hart, overrun.slot,
                                                     overrun.residency)
            if reported not in facts:
                found.append(f"overrun: module {reported}, reference {sorted(facts)}")
        if inversion is None or inversion > stop:
            expected: set[bool | None] = {None}
        elif inversion < stop:
            expected = {False}
        else:
            expected = {None, False}
        if stalled.ordered not in expected:
            found.append(f"ordered: module {stalled.ordered}, reference {sorted(map(str, expected))}"
                         f" with inversion at {inversion}")
        if stalled.slots:
            found.append("slots: reported without closure")
        if stalled.program_zero_wait:
            found.append("program_zero_wait: true without closure")
        return found
    if not stalled.closed:
        found.append(f"closed: module stops with {stalled.reason} after {len(stalled.trace)} "
                     f"cycles, reference closes")
        return found
    if stalled.reason is not None:
        found.append(f"reason: module {stalled.reason} on closure")
    if inversion is None:
        if stalled.ordered is not True:
            found.append(f"ordered: module {stalled.ordered}, reference sees no inversion")
    elif stalled.ordered is not False:
        found.append(f"ordered: module {stalled.ordered}, reference inverts at cycle {inversion}")
    elif stalled.inversion is None or len(stalled.inversion) != inversion + 1:
        found.append(f"inversion: module trace of "
                     f"{None if stalled.inversion is None else len(stalled.inversion)} cycles, "
                     f"reference inverts at cycle {inversion}")
    expected_slots = reference_slots(program, tally)
    reported_slots = {(report.hart, report.slot): report for report in stalled.slots}
    if set(reported_slots) != set(expected_slots):
        found.append(f"slots: module {sorted(reported_slots)}, reference {sorted(expected_slots)}")
        return found
    for key, ref in expected_slots.items():
        report = reported_slots[key]
        found.extend(f"{key[0]}/{key[1]} {name}: module {getattr(report, name)}, "
                     f"reference {getattr(ref, name)}"
                     for name in ("stall_total_max", "stall_single_max", "boundary_outstanding",
                                  "boundary_residency_max", "drain_max", "cut_max")
                     if getattr(report, name) != getattr(ref, name))
        witness = None if report.boundary_witness is None else len(report.boundary_witness)
        if witness != ref.witness_cycles:
            found.append(f"{key[0]}/{key[1]} witness: module {witness} cycles, "
                         f"reference {ref.witness_cycles}")
    zero = all(ref.stall_total_max == 0 and ref.stall_single_max == 0
               and not ref.boundary_outstanding for ref in expected_slots.values())
    if stalled.program_zero_wait != zero:
        found.append(f"program_zero_wait: module {stalled.program_zero_wait}, reference {zero}")
    return found


# --------------------------------------------------------------------------
# Documents: the fixture reader and the campaign's encoder
# --------------------------------------------------------------------------

def from_json(program_raw: bytes, resources_raw: bytes) -> RefProgram:
    """A tracked fixture, parsed here rather than through the module's reader."""
    resources = json.loads(resources_raw)
    document = json.loads(program_raw)
    banks = tuple(RefBank(bank["name"], int(bank["path_cycles"]),
                          tuple((op, int(n)) for op, n in bank["occupancy_cycles"].items()),
                          None if bank["refresh_cycles"] is None else int(bank["refresh_cycles"]))
                  for bank in resources["banks"])
    index = {bank.name: number for number, bank in enumerate(banks)}
    harts = tuple(hart["name"] for hart in resources["harts"])
    limits = tuple(int(hart["issue_limit"]) for hart in resources["harts"])
    grants = tuple(int(phase["grant"]) for phase in document["phases"])
    refresh = tuple(tuple(index[name] for name in phase["refresh"]) for phase in document["phases"])
    slots = tuple(
        tuple(RefSlot(slot["id"], int(slot["start"]), int(slot["length"]),
                      tuple(tuple(RefRequest(index[req["bank"]], req["operation"], int(req["gap"]))
                                  for req in alternative)
                            for alternative in slot["alternatives"]))
              for slot in document["harts"][hart])
        for hart in harts)
    return RefProgram(harts, limits, banks, grants, refresh, slots)


def to_json(program: RefProgram, name: str) -> tuple[bytes, bytes]:
    """The program and resource documents the module reads, as bytes."""
    resources = {
        "schema": "phase-resources-v1",
        "harts": [{"name": hart, "issue_limit": limit}
                  for hart, limit in zip(program.harts, program.limits, strict=True)],
        "operations": sorted({op for bank in program.banks for op, _ in bank.occupancy}),
        "banks": [{"name": bank.name, "path_cycles": bank.path,
                   "occupancy_cycles": dict(bank.occupancy), "refresh_cycles": bank.refresh}
                  for bank in program.banks],
    }
    resources_raw = json.dumps(resources).encode("utf-8")
    document = {
        "schema": "phase-program-v1",
        "name": name,
        "resources_sha256": hashlib.sha256(resources_raw).hexdigest(),
        "phases": [{"grant": grant, "refresh": [program.banks[bank].name for bank in banks]}
                   for grant, banks in zip(program.grants, program.refresh, strict=True)],
        "harts": {hart: [{"id": slot.name, "start": slot.start, "length": slot.length,
                          "alternatives": [[{"bank": program.banks[req.bank].name,
                                             "operation": req.operation, "gap": req.gap}
                                            for req in alternative]
                                           for alternative in slot.alternatives]}
                         for slot in slots]
                  for hart, slots in zip(program.harts, program.slots, strict=True)},
    }
    return json.dumps(document).encode("utf-8"), resources_raw


def _windows(rng: random.Random, phases: int, count: int) -> list[tuple[int, int]]:
    """`count` non-overlapping (start, length) windows inside a frame of `phases`."""
    if count == 1:
        length = rng.randint(1, phases)
        return [(rng.randint(0, phases - length), length)]
    first_length = rng.randint(1, phases - 1)
    first_start = rng.randint(0, phases - 1 - first_length)
    earliest = first_start + first_length
    second_length = rng.randint(1, phases - earliest)
    return [(first_start, first_length),
            (rng.randint(earliest, phases - second_length), second_length)]


def _requests(rng: random.Random, banks: tuple[RefBank, ...], length: int,
              limit: int) -> tuple[RefRequest, ...]:
    """One alternative valid under the contract's reader: runs within the issue limit,
    gaps summing below the slot length; empty one draw in seven."""
    if rng.random() < 0.15:
        return ()
    budget = length - 1
    run = 0
    requests: list[RefRequest] = []
    for index in range(rng.randint(1, 3)):
        options = [gap for gap in (0, 0, 1, 2)
                   if gap <= budget and (index == 0 or gap > 0 or run < limit)]
        if not options:
            break
        gap = rng.choice(options)
        budget -= gap
        run = run + 1 if index > 0 and gap == 0 else 1
        bank = rng.randrange(len(banks))
        requests.append(RefRequest(bank, rng.choice([op for op, _ in banks[bank].occupancy]), gap))
    return tuple(requests)


def random_program(rng: random.Random) -> RefProgram:
    """A small valid program, the campaign's shape.

    One or two harts with issue limit one or two; two or three banks, at most one
    with a nonzero path of one or two; a frame of two to five phases with grants zero
    to two and refresh on at most one bank in at most one phase; per hart one or two
    slots, each with one or two alternatives of up to three requests.
    """
    harts = ("X", "Y")[:rng.choice([1, 2])]
    limits = tuple(rng.choice([1, 2]) for _ in harts)
    bank_count = rng.choice([2, 3])
    path_bank = rng.choice([None, *range(bank_count)])
    banks: list[RefBank] = []
    for number in range(bank_count):
        occupancy = [("rd", rng.choice([1, 1, 2, 3]))]
        if rng.random() < 0.6:
            occupancy.append(("wr", rng.choice([1, 2, 3, 3])))
        banks.append(RefBank(f"b{number}", rng.choice([1, 2]) if number == path_bank else 0,
                             tuple(occupancy), rng.choice([None, 1, 2])))
    phases = rng.randint(2, 5)
    # Grants lean away from zero so that closures, not overruns, dominate the draw.
    grants = tuple(rng.choice([0, 1, 1, 2, 2]) for _ in range(phases))
    refresh: list[tuple[int, ...]] = [() for _ in range(phases)]
    refreshable = [number for number, bank in enumerate(banks) if bank.refresh is not None]
    if refreshable and rng.random() < 0.5:
        refresh[rng.randrange(phases)] = (rng.choice(refreshable),)
    slots: list[tuple[RefSlot, ...]] = []
    for hart, limit in zip(harts, limits, strict=True):
        windows = _windows(rng, phases, rng.choice([1, 1, 2]))
        slots.append(tuple(
            RefSlot(f"{hart}{number}", start, length,
                    tuple(_requests(rng, tuple(banks), length, limit)
                          for _ in range(rng.choice([1, 2]))))
            for number, (start, length) in enumerate(windows)))
    return RefProgram(harts, limits, tuple(banks), grants, tuple(refresh), tuple(slots))


# --------------------------------------------------------------------------
# Cases
# --------------------------------------------------------------------------

# The stall contract's acceptance table and worked occurrence, per (hart, slot):
# stall_total_max, stall_single_max, boundary_outstanding, boundary_residency_max,
# drain_max and cut_max, the last zero because every fixture program is fully
# accepted or holds its head with no successor beside it.
CONTRACT_TABLE: dict[str, dict[tuple[str, str], tuple[int, int, bool, int, int, int]]] = {
    "refresh-stall": {("X", "sx"): (2, 2, False, 0, 0, 0)},
    "joint-loser": {("X", "sx"): (3, 3, False, 0, 0, 0), ("Y", "sy"): (3, 3, False, 0, 0, 0)},
    "split-run": {("X", "sx"): (1, 1, False, 0, 0, 0)},
    "path-wait": {("X", "sx"): (1, 1, False, 0, 0, 0)},
    "boundary-outstanding": {("X", "sx"): (1, 1, True, 4, 0, 0)},
    "worked-tail": {("X", "sx"): (3, 3, True, 4, 0, 0), ("Y", "sy"): (0, 0, False, 0, 1, 0)},
}

# The fixtures' resource declaration, as the contract states it.
FIXTURE_BANKS = (RefBank("b0", 0, (("rd", 1), ("wr", 3)), 2), RefBank("b1", 0, (("rd", 1),), None),
                 RefBank("f2", 2, (("rd", 1),), None))


def _relation(grants: tuple[int, ...], refresh: dict[int, int], x: tuple[RefSlot, ...],
              y: tuple[RefSlot, ...] = ()) -> RefProgram:
    """One of the contract's decidable relations over the fixture resources."""
    return RefProgram(("X", "Y"), (2, 1), FIXTURE_BANKS, grants,
                      tuple((refresh[phase],) if phase in refresh else ()
                            for phase in range(len(grants))), (x, y))


def _b0(operation: str, gap: int) -> RefRequest:
    return RefRequest(0, operation, gap)


# The relations the contract decides by hand, read as the reference's answer key.
CUT_SHIFTED = _relation((1, 1, 1), {0: 0},
                        (RefSlot("sx", 0, 3, ((_b0("rd", 0), RefRequest(1, "rd", 2)),)),))
CUT_HELD = _relation((1, 1, 1), {0: 0},
                     (RefSlot("sx", 0, 2, ((_b0("rd", 0), RefRequest(1, "rd", 0)),)),))
GRANT_GAP = _relation((2, 0), {}, (RefSlot("sx", 1, 1, ((_b0("rd", 0),),)),))
FRAME_WRAP = _relation((1, 1, 1, 1), {}, (RefSlot("sx", 0, 3, ((_b0("rd", 0),),)),),
                       (RefSlot("sy", 3, 1, ((_b0("wr", 0),),)),))
PATH_BLOCKED = _relation((2, 0, 0), {}, (RefSlot("sx", 0, 1, ((RefRequest(2, "rd", 0),),)),),
                         (RefSlot("sy", 0, 1, ((RefRequest(2, "rd", 0),),)),))
REFRESH_OVERLAP = _relation((1, 1, 1, 1, 1), {2: 0},
                            (RefSlot("sx", 0, 5, ((_b0("rd", 0), _b0("wr", 0)),)),))
INVERSION = _relation((1, 1, 1), {},
                      (RefSlot("sx", 0, 3, ((_b0("wr", 0), RefRequest(1, "rd", 1)),)),))
OVERRUN = _relation((1, 1), {}, (RefSlot("sx", 0, 1, ((_b0("rd", 0),),)),),
                    (RefSlot("sy", 1, 1, ((_b0("wr", 0),),)),))


# The programs on which the two readings of C9's span part, minimised from the
# campaign's first disagreements: one hart, a second slot whose window lies after an
# earlier occurrence's operation was issued and before it completes.
WR3 = RefBank("b0", 0, (("wr", 3),), None)
RD2 = RefBank("b1", 0, (("rd", 2),), None)
FAR3 = RefBank("f2", 2, (("rd", 3),), None)
ADJUDICATED: tuple[tuple[str, RefProgram, str, int], ...] = (
    # An empty occurrence while the previous occurrence's write still occupies its bank.
    ("empty-after-write", RefProgram(("X",), (1,), (WR3, RD2), (1, 1, 1), ((), (), ()), ((
        RefSlot("X0", 0, 1, ((RefRequest(0, "wr", 0),),)), RefSlot("X1", 1, 1, ((),))),)),
     "X1", 1),
    # The write held at its slot end is accepted in residency, whose span covers the
    # empty occurrence's whole window.
    ("empty-inside-residency", RefProgram(("X",), (1,), (WR3, RD2), (0, 1, 1, 1),
                                          ((), (), (), ()), ((
        RefSlot("X0", 0, 1, ((RefRequest(0, "wr", 0),),)), RefSlot("X1", 2, 1, ((),))),)),
     "X1", 1),
    # A cross-occurrence completion inversion: the path-two read of X0 completes after
    # X1's read, held at its slot end and accepted in residency.
    ("inversion-across-occurrences", RefProgram(("X",), (1,), (WR3, RD2, FAR3), (1, 1, 0, 1),
                                                ((), (), (), ()), ((
        RefSlot("X0", 1, 1, ((RefRequest(2, "rd", 0),),)),
        RefSlot("X1", 2, 1, ((RefRequest(1, "rd", 0),),))),)),
     "X1", 1),
)


def _adjudicated() -> None:
    """The reading of C9's span the campaign settled, pinned as a regression.

    On each program the module and the hart-wide reference agree on every field, the
    later slot's `drain_max` is the earlier operation's residue past that slot, and
    the literal occurrence-only reading reports zero there and nowhere else.
    """
    for name, program, slot, drain in ADJUDICATED:
        program_raw, resources_raw = to_json(program, f"synthetic-{name}")
        stalled = analyze(program_raw, resources_raw).stalled
        tally = simulate(program)
        found = compare(program, stalled, tally)
        ensure(not found, f"{name}: the hart-wide reading no longer agrees: {found}")
        ensure(reference_slots(program, tally)[("X", slot)].drain_max == drain,
               f"{name}: {slot} drains {reference_slots(program, tally)[('X', slot)]}")
        literal = compare(program, stalled, simulate(program, Conventions(drain_occurrence_only=True)))
        ensure(literal == [f"X/{slot} drain_max: module {drain}, reference 0"],
               f"{name}: the occurrence-only reading parts elsewhere: {literal}")


def _fixture(name: str) -> tuple[RefProgram, bytes, bytes]:
    program_raw = (EXAMPLES / f"{name}.json").read_bytes()
    resources_raw = (EXAMPLES / "resources.json").read_bytes()
    return from_json(program_raw, resources_raw), program_raw, resources_raw


def _row(report: RefSlotReport) -> tuple[int, int, bool, int, int, int]:
    return (report.stall_total_max, report.stall_single_max, report.boundary_outstanding,
            report.boundary_residency_max, report.drain_max, report.cut_max)


def _tracked_fixtures() -> None:
    """The reference alone decides every fixture as the contract's table says; the
    module then agrees with it on every field."""
    for name in FIXTURES:
        program, program_raw, resources_raw = _fixture(name)
        tally = simulate(program)
        ensure(not tally.stops and tally.inversion is None and not tally.capped,
               f"{name}: reference stops {tally.stops}, inversion {tally.inversion}")
        slots = reference_slots(program, tally)
        for key, expected in CONTRACT_TABLE[name].items():
            ensure(_row(slots[key]) == expected,
                   f"{name}/{key[1]}: reference {_row(slots[key])}, contract table {expected}")
        found = compare(program, analyze(program_raw, resources_raw).stalled, tally)
        ensure(not found, f"{name}: module and reference disagree: {found}")


def _relations() -> None:
    """The contract's decidable relations, decided by the reference alone."""
    closed: list[tuple[str, RefProgram, dict[str, tuple[int, int, bool, int, int, int]]]] = [
        ("cut-shifted", CUT_SHIFTED, {"sx": (2, 2, False, 0, 0, 1)}),
        ("cut-held", CUT_HELD, {"sx": (2, 2, True, 1, 0, 1)}),
        ("grant-gap", GRANT_GAP, {"sx": (1, 1, True, 1, 0, 0)}),
        ("frame-wrap", FRAME_WRAP, {"sx": (2, 2, False, 0, 0, 0), "sy": (0, 0, False, 0, 2, 0)}),
    ]
    for name, program, table in closed:
        tally = simulate(program)
        ensure(not tally.stops and not tally.capped, f"{name}: reference stops {tally.stops}")
        slots = reference_slots(program, tally)
        for (hart, slot), report in slots.items():
            ensure(_row(report) == table[slot], f"{name}/{hart}/{slot}: reference {_row(report)}")
    stops: list[tuple[str, RefProgram, str, int]] = [
        ("path-blocked", PATH_BLOCKED, "path-blocked", 2),
        ("refresh-overlap", REFRESH_OVERLAP, "refresh-overlap", 2),
        ("residency-overrun", OVERRUN, "residency-overrun", 4),
    ]
    for name, program, reason, cycle in stops:
        tally = simulate(program)
        ensure(tally.stops == {reason: cycle}, f"{name}: reference stops {tally.stops}")
    tally = simulate(OVERRUN)
    ensure(tally.overruns == {(4, 0, 0, 1)}, f"overrun facts moved: {tally.overruns}")
    tally = simulate(INVERSION)
    ensure(not tally.stops and tally.inversion == 1, f"inversion moved: {tally}")


def _perturbation_control() -> None:
    """A one-convention error in the reference must surface as a disagreement.

    Without this the campaign's silence would be evidence about nothing: a
    reference that agreed by construction would agree with a wrong module too.
    """
    controls: list[tuple[str, RefProgram, bytes, bytes, Conventions]] = []
    for name, conv in (("worked-tail", Conventions(charge_presented=True)),
                       ("path-wait", Conventions(interlock=False)),
                       ("boundary-outstanding", Conventions(residency_from_end=True))):
        controls.append((name, *_fixture(name), conv))
    program_raw, resources_raw = to_json(CUT_SHIFTED, "synthetic-cut-shifted")
    controls.append(("cut-shifted", CUT_SHIFTED, program_raw, resources_raw, Conventions(cut=False)))
    for name, program, program_raw, resources_raw, conv in controls:
        stalled = analyze(program_raw, resources_raw).stalled
        exact = compare(program, stalled, simulate(program))
        ensure(not exact, f"{name}: the exact reference must agree first: {exact}")
        ensure(bool(compare(program, stalled, simulate(program, conv))),
               f"{name}: {conv} went unreported")


def _campaign() -> None:
    """A seeded differential campaign: the module against the reference on every field.

    The floors keep a generator that stopped producing interesting programs, or a
    walk that stopped resolving them, from passing this vacuously.
    """
    rng = random.Random(CAMPAIGN_SEED)  # noqa: S311 - a fixed differential campaign, no secrets
    disagreements: list[str] = []
    counts = dict.fromkeys(("closed", "stopped", "inverted", "outstanding", "stalled", "cut",
                            "residency", "drained", "choices", "capped", "path-blocked",
                            "refresh-overlap", "residency-overrun"), 0)
    started = time.perf_counter()
    for index in range(CAMPAIGN_COUNT):
        program = random_program(rng)
        program_raw, resources_raw = to_json(program, f"campaign-{index}")
        tally = simulate(program)
        try:
            stalled = analyze(program_raw, resources_raw).stalled
        except (TypeError, ValueError) as err:
            disagreements.append(f"program {index} {program}: module refused it: {err}")
            continue
        found = compare(program, stalled, tally)
        if found:
            disagreements.append(f"program {index} {program}: {found}")
            if len(disagreements) > 3:
                break
        slots = reference_slots(program, tally).values()
        counts["capped"] += tally.capped
        counts["stopped"] += bool(tally.stops)
        counts["closed"] += not tally.stops
        for reason, cycle in tally.stops.items():
            counts[reason] += cycle == tally.stop_cycle
        counts["inverted"] += tally.inversion is not None and not tally.stops
        counts["choices"] += tally.choices > 0
        counts["outstanding"] += any(slot.boundary_outstanding for slot in slots)
        counts["stalled"] += any(slot.stall_total_max > 0 for slot in slots)
        counts["cut"] += any(slot.cut_max > 0 for slot in slots)
        counts["residency"] += any(slot.boundary_residency_max > 0 for slot in slots)
        counts["drained"] += any(slot.drain_max > 0 for slot in slots)
    elapsed = time.perf_counter() - started
    ensure(not disagreements, "module and reference disagree: " + "; ".join(disagreements))
    ensure(counts["capped"] == 0, f"{counts['capped']} programs hit the {MAX_FRAMES}-frame cap")
    floors = {"closed": CAMPAIGN_COUNT // 5, "stopped": CAMPAIGN_COUNT // 20,
              "inverted": CAMPAIGN_COUNT // 100, "outstanding": CAMPAIGN_COUNT // 50,
              "stalled": CAMPAIGN_COUNT // 10, "cut": CAMPAIGN_COUNT // 200,
              "residency": CAMPAIGN_COUNT // 50, "drained": CAMPAIGN_COUNT // 50,
              "choices": CAMPAIGN_COUNT // 100, "path-blocked": CAMPAIGN_COUNT // 100,
              "refresh-overlap": CAMPAIGN_COUNT // 100,
              "residency-overrun": CAMPAIGN_COUNT // 100}
    thin = {name: counts[name] for name, floor in floors.items() if counts[name] < floor}
    ensure(not thin, f"the campaign is thin: {thin} of {CAMPAIGN_COUNT} in {elapsed:.1f}s")


def cases() -> list[Case]:
    return [Case("tracked-fixtures", _tracked_fixtures), Case("relations", _relations),
            Case("perturbation-control", _perturbation_control),
            Case("adjudicated", _adjudicated), Case("campaign", _campaign)]
