# SPDX-License-Identifier: Apache-2.0
"""An independent bounded-horizon reference for the two finite phase checkers.

The simulator below is *not* the checker. It is written from the documented
semantics only, which are the module docstrings of
[phase_service.py](../vos/phase_service.py) and
[phase_completion.py](../vos/phase_completion.py), the cycle, ordering and drain
conventions of the
[completion model](../../docs/implementation/phase-service/completion-model.md), and
the verdict table of the
[store-buffer comparison](../../docs/implementation/comparisons/store-buffer.md). It keeps every
quantity in absolute cycle time instead of the checkers' per-boundary residues, it
enumerates arrival histories forward from an empty state instead of exploring a
state graph, and it never imports the checkers' step functions. Two implementations
that share no code and agree on a verdict are evidence the verdict follows from the
semantics rather than from one loop's arithmetic.

Absolute-time conventions, each traced to a sentence of the prose:

  R1  "Refresh reserves its bank first." "They must start on idle banks; neither
      refresh nor requests may preempt a residual operation."
  R2  "Requests completing transit accept next" and "a request that finds its bank
      taken on arrival is a queue in the fabric, which the predicate forbids."
  R3  "One hart's requests must be accepted in issue order, batch order standing
      for issue order within a cycle and acceptance within one cycle counting as
      ordered."
  R4  "the current phase's joint batch issues last" and "phase grants bound total
      injection at issue."
  R5  "The same bank cannot accept two operations in one cycle."
  R6  "For each hart, a later operation may complete in the same cycle as an
      earlier operation, but never before it."
  R7  "Fabric transit counts cycles from the boundary after issue; occupancy
      includes the acceptance cycle" and "at the boundary immediately after issue
      its remaining time to completion is p+n-1. Both terms include the same
      acceptance cycle; adding another cycle would count it twice."
  R8  "At each reachable boundary the checker stops all new arrivals and replays
      the remaining operations to completion ... Scheduled refresh continues with
      its original phase and occupancy."
  R9  "The initial state is empty at phase zero" and the exploration "retains
      operation residue across every frame wrap."

An operation issued in cycle `issue` to a bank with path `path` and occupancy `occ`
accepts in cycle `issue + path` and occupies `accept .. accept + occ - 1`. A refresh
started in cycle `start` for `dur` cycles occupies `start .. start + dur - 1`.

The exploration takes every arrival alternative in every cycle up to a horizon.
Histories reaching an identical residual situation at the same cycle are merged,
which is memoisation of a deterministic cycle function and changes no history. A
frame boundary whose residual set repeats the previous frame boundary's is a
fixpoint, so a finite horizon still reports closure over arbitrarily many frames.

The cases are a positive control (the reference alone decides every tracked fixture
and scenario as the documents say), a seeded differential campaign against both
checkers, a perturbation control showing the campaign can detect a one-convention
error, and the two contracts whose reading the campaign had to adjudicate.
"""

import json
import random
from dataclasses import dataclass
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos.phase_completion import State as ModuleCompletionState
from vos.phase_completion import check as completion_check
from vos.phase_service import Contract, scenarios
from vos.phase_service import check as acceptance_check

FIXTURES = TOOLS.parent / "docs" / "implementation" / "phase-service"

# The campaign is seeded and fixed so a failure is reproducible from this module
# alone. The size is set by the module's wall-time budget, not by a coverage claim.
CAMPAIGN_SEED = 20260920
CAMPAIGN_CONTRACTS = 20000


# --------------------------------------------------------------------------
# Contract representation, independent of the checkers' dataclasses
# --------------------------------------------------------------------------

type Request = tuple[int, ...]
type Batch = tuple[Request, ...]
type Trace = tuple[Batch, ...]


@dataclass(frozen=True)
class RefContract:
    """The documented JSON fields, read as plain data."""

    grants: tuple[int, ...]
    arrivals: tuple[tuple[Batch, ...], ...]
    banks: int = 1
    refresh: tuple[tuple[tuple[int, int], ...], ...] = ()
    paths: tuple[int, ...] = ()

    @property
    def phases(self) -> int:
        return len(self.grants)

    def refresh_table(self) -> tuple[tuple[tuple[int, int], ...], ...]:
        return self.refresh or ((),) * self.phases

    def path_table(self) -> tuple[int, ...]:
        return self.paths or (0,) * self.banks


@dataclass(frozen=True)
class Conventions:
    """The two documented conventions the perturbation control bends.

    `transit_bias` moves the R7 transit count off the documented `p+n-1` reading,
    which is the convention a hand port gets wrong first. `drain_bias` moves the
    R8 quiescent-drain attribution by a cycle. Both are zero for every case but
    the control, so the reference is exact wherever a verdict is claimed.
    """

    transit_bias: int = 0
    drain_bias: int = 0


EXACT = Conventions()


@dataclass(frozen=True)
class Op:
    issue: int
    bank: int
    occ: int
    hart: int
    path: int

    @property
    def accept(self) -> int:
        return self.issue + self.path

    @property
    def complete(self) -> int:
        return self.accept + self.occ - 1


@dataclass(frozen=True)
class Reservation:
    start: int
    bank: int
    dur: int

    @property
    def end(self) -> int:
        return self.start + self.dur - 1


@dataclass(frozen=True)
class Failure:
    """A refutation: the boundary it is attributed to and the module's vocabulary.

    For a drain, `cycle` is the source boundary whose drain blocked and `reached`
    the boundary the empty-arrival replay reached before blocking.
    """

    cycle: int
    stage: str
    reason: str
    reached: int | None = None


type Situation = tuple[tuple[Op, ...], tuple[Reservation, ...]]
type Fingerprint = tuple[tuple[tuple[int, int, int, int, int], ...],
                         tuple[tuple[int, int, int], ...]]
# The phase_service state shape: phase, per-bank residue, in-flight requests.
type AcceptanceProjection = tuple[int, tuple[int, ...], tuple[tuple[int, int, int, int], ...]]
# The phase_completion state shape: phase, maintenance residue, operations.
type CompletionProjection = tuple[int, tuple[int, ...], tuple[tuple[int, int, int, int], ...]]

EMPTY: Situation = ((), ())


def request_fields(request: Request) -> tuple[int, int, int]:
    """(bank, occupancy, hart), the hart defaulting to zero."""
    bank, occ, *rest = request
    return bank, occ, (rest[0] if rest else 0)


def to_module(contract: RefContract) -> Contract:
    """The same contract in the checkers' own dataclass."""
    return Contract(grants=contract.grants, arrivals=contract.arrivals,
                    banks=contract.banks, refresh=contract.refresh, paths=contract.paths)


def from_module(contract: Contract) -> RefContract:
    """A named scenario, read as the reference's own data."""
    return RefContract(
        grants=contract.grants, arrivals=contract.arrivals, banks=contract.banks,
        refresh=tuple(tuple((entry[0], entry[1]) for entry in batch)
                      for batch in contract.refresh),
        paths=contract.paths)


def from_json(path: Path) -> RefContract:
    """A tracked fixture, parsed here rather than through the checkers' loader."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return RefContract(
        grants=tuple(raw["grants"]),
        arrivals=tuple(tuple(tuple(tuple(r) for r in batch) for batch in alternatives)
                       for alternatives in raw["arrivals"]),
        banks=int(raw.get("banks", 1)),
        refresh=tuple(tuple((entry[0], entry[1]) for entry in batch)
                      for batch in raw.get("refresh", ())),
        paths=tuple(raw.get("paths", ())),
    )


# --------------------------------------------------------------------------
# One cycle of absolute time
# --------------------------------------------------------------------------

def live(sit: Situation, t: int) -> Situation:
    """Everything still live at boundary `t`; R9 carries the rest of the residue."""
    ops, refs = sit
    return (tuple(op for op in ops if op.complete >= t),
            tuple(ref for ref in refs if ref.end >= t))


def canonical(sit: Situation, t: int) -> Fingerprint:
    """The residual situation with its times shifted to `t`, for merging histories."""
    ops, refs = live(sit, t)
    return (tuple((op.issue - t, op.bank, op.occ, op.hart, op.path) for op in ops),
            tuple(sorted((ref.start - t, ref.bank, ref.dur) for ref in refs)))


def step(contract: RefContract, t: int, sit: Situation, batch: Batch | None, *,
         order_checks: bool = True, completion_checks: bool = True) -> Situation | Failure:
    """Run cycle `t`. `batch` None runs only the pre-arrival stages, R1 and R2."""
    phase = t % contract.phases
    refresh_table = contract.refresh_table()
    paths = contract.path_table()
    ops, refs = live(sit, t)

    def held_before(bank: int) -> bool:
        """Something accepted or reserved in an earlier cycle still holds `bank` in `t`."""
        return (any(op.bank == bank and op.accept < t <= op.complete for op in ops)
                or any(ref.bank == bank and ref.start < t <= ref.end for ref in refs))

    taken: set[int] = set()
    new_refs = list(refs)

    # R1: refresh reserves first and must find its bank idle.
    for bank, dur in refresh_table[phase]:
        if held_before(bank) or bank in taken:
            return Failure(t, "refresh", "refresh-overlap")
        new_refs.append(Reservation(t, bank, dur))
        taken.add(bank)

    # R2, R3 and R5: requests completing transit accept next, in issue order.
    for index, op in enumerate(ops):
        if op.accept != t or op.path == 0:
            continue
        if held_before(op.bank) or op.bank in taken:
            return Failure(t, "flight", "path-blocked")
        if order_checks and any(other.hart == op.hart and other.accept > t
                                for other in ops[:index]):
            return Failure(t, "flight", "order-inverted")
        taken.add(op.bank)

    new_ops = list(ops)
    if batch is not None:
        # R4: the phase's joint batch issues last, bounded by the grant.
        if len(batch) > contract.grants[phase]:
            return Failure(t, "arrival", "arrival-blocked")
        for request in batch:
            bank, occ, hart = request_fields(request)
            op = Op(t, bank, occ, hart, paths[bank])
            if op.path == 0:
                if held_before(bank) or bank in taken:
                    return Failure(t, "arrival", "arrival-blocked")
                if order_checks and any(other.hart == hart and other.accept > t
                                        for other in new_ops):
                    return Failure(t, "arrival", "order-inverted")
                taken.add(bank)
            new_ops.append(op)

    # R6: completion order at the end of cycle `t`.
    if completion_checks:
        for index, op in enumerate(new_ops):
            if op.complete == t and any(other.hart == op.hart and other.complete > t
                                        for other in new_ops[:index]):
                return Failure(t, "completion", "completion-order-inverted")

    return (tuple(new_ops), tuple(new_refs))


def flight_residue(sit: Situation, t: int, conv: Conventions = EXACT) -> int:
    """R7: the longest remaining transit at boundary `t`.

    A request accepting in cycle `accept` has `accept - t + 1` transit cycles left
    at boundary `t`, the acceptance cycle being the last of them.
    """
    ops, _ = live(sit, t)
    return max([0, *(op.accept - t + 1 + conv.transit_bias for op in ops if op.accept >= t)])


def drain(contract: RefContract, t: int, sit: Situation,
          conv: Conventions = EXACT) -> tuple[int, Failure | None]:
    """R8: stop arrivals at boundary `t`, keep refresh, run until nothing is live."""
    elapsed = 0
    now = t
    current = sit
    while live(current, now)[0]:
        outcome = step(contract, now, current, (), order_checks=False, completion_checks=False)
        if isinstance(outcome, Failure):
            return elapsed, Failure(t, "drain", "drain-" + outcome.reason, reached=now)
        current = outcome
        now += 1
        elapsed += 1
    return elapsed + conv.drain_bias, None


# --------------------------------------------------------------------------
# Exploration
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Exploration:
    mode: str
    horizon: int
    earliest: int | None
    reasons: frozenset[str]
    closed: bool
    fabric_drain: int
    quiescent_drain: int | None

    @property
    def refuted(self) -> bool:
        return self.earliest is not None

    @property
    def verdict(self) -> str:
        if self.refuted:
            return "refuted"
        return "closed" if self.closed else "open"


def explore(contract: RefContract, horizon: int, mode: str,
            conv: Conventions = EXACT) -> Exploration:
    """Enumerate every arrival history up to `horizon` cycles.

    "acceptance" applies R1 to R5 and R7, which is the phase_service predicate.
    "completion" adds R6 and R8, which is the phase_completion predicate.
    """
    completion = mode == "completion"
    failures: list[Failure] = []
    fabric = 0
    quiescent = 0
    frontier: dict[Fingerprint, Situation] = {canonical(EMPTY, 0): EMPTY}
    previous: frozenset[Fingerprint] | None = None
    closed = False
    t = 0
    while t < horizon:
        if t % contract.phases == 0:
            frame = frozenset(frontier)
            if previous is not None and frame == previous and not failures:
                closed = True
                break
            previous = frame
        following: dict[Fingerprint, Situation] = {}
        for sit in frontier.values():
            fabric = max(fabric, flight_residue(sit, t, conv))
            if completion:
                cycles, blocked = drain(contract, t, sit, conv)
                if blocked is not None:
                    # The checker stops at the earliest blocked source boundary.
                    failures.append(blocked)
                    continue
                quiescent = max(quiescent, cycles)
            for batch in contract.arrivals[t % contract.phases]:
                outcome = step(contract, t, sit, batch, completion_checks=completion)
                if isinstance(outcome, Failure):
                    failures.append(outcome)
                    continue
                key = canonical(outcome, t + 1)
                if key not in following:
                    following[key] = outcome
        frontier = following
        t += 1
        if failures:
            break
    earliest = min((failure.cycle for failure in failures), default=None)
    reasons = frozenset(failure.reason for failure in failures if failure.cycle == earliest)
    return Exploration(mode, horizon, earliest, reasons, closed, fabric,
                       quiescent if completion else None)


def default_horizon(contract: RefContract, frames: int = 4) -> int:
    """Four frames plus the longest residue any single operation can carry."""
    occ = max((request_fields(r)[1] for alternatives in contract.arrivals
               for batch in alternatives for r in batch), default=1)
    path = max(contract.path_table(), default=0)
    refresh = max((dur for batch in contract.refresh_table() for _, dur in batch), default=0)
    return frames * contract.phases + occ + path + refresh


def explore_resolved(contract: RefContract, mode: str,
                     conv: Conventions = EXACT) -> tuple[Exploration, bool]:
    """Explore at the default horizon, extending once when neither side resolves."""
    horizon = default_horizon(contract)
    result = explore(contract, horizon, mode, conv)
    if result.refuted or result.closed:
        return result, False
    extended = explore(contract, horizon * 4, mode, conv)
    return extended, not (extended.refuted or extended.closed)


def replay(contract: RefContract, trace: Trace, *,
           mode: str) -> tuple[Failure | None, Situation, int]:
    """Replay a checker's trace; return its failure, the boundary situation and cycle.

    The batches are applied at cycles 0 to len-1. When they all succeed the
    pre-arrival stages of the next cycle run too, because a checker failure before
    that cycle's arrivals carries only the accepted prefix.
    """
    completion = mode == "completion"
    sit: Situation = EMPTY
    for index, batch in enumerate(trace):
        outcome = step(contract, index, sit, batch, completion_checks=completion)
        if isinstance(outcome, Failure):
            return outcome, sit, index
        sit = outcome
    boundary = len(trace)
    outcome = step(contract, boundary, sit, None, completion_checks=completion)
    return (outcome if isinstance(outcome, Failure) else None), sit, boundary


def replay_prefix(contract: RefContract, trace: Trace, *, mode: str) -> Situation | None:
    """The situation at boundary len(trace), or None when a batch does not apply."""
    completion = mode == "completion"
    sit: Situation = EMPTY
    for index, batch in enumerate(trace):
        outcome = step(contract, index, sit, batch, completion_checks=completion)
        if isinstance(outcome, Failure):
            return None
        sit = outcome
    return sit


def acceptance_projection(contract: RefContract, sit: Situation, t: int) -> AcceptanceProjection:
    """Project a boundary onto the phase_service state shape."""
    ops, refs = live(sit, t)
    busy = [0] * contract.banks
    for op in ops:
        if op.accept < t <= op.complete:
            busy[op.bank] = op.complete - t + 1
    for ref in refs:
        if ref.start < t <= ref.end:
            busy[ref.bank] = max(busy[ref.bank], ref.end - t + 1)
    flight = tuple((op.bank, op.accept - t + 1, op.occ, op.hart)
                   for op in ops if op.accept >= t)
    return (t % contract.phases, tuple(busy), flight)


def completion_projection(contract: RefContract, sit: Situation, t: int) -> CompletionProjection:
    """Project a boundary onto the phase_completion state shape, in issue order."""
    ops, refs = live(sit, t)
    maintenance = [0] * contract.banks
    for ref in refs:
        if ref.start < t <= ref.end:
            maintenance[ref.bank] = max(maintenance[ref.bank], ref.end - t + 1)
    operations = tuple((op.bank, op.accept - t + 1, op.occ, op.hart) if op.accept >= t
                       else (op.bank, 0, op.complete - t + 1, op.hart) for op in ops)
    return (t % contract.phases, tuple(maintenance), operations)


def module_completion_state(state: ModuleCompletionState) -> CompletionProjection:
    """The checker's own completion state in the projection shape."""
    return (state.phase, tuple(state.maintenance),
            tuple((op.bank, op.transit, op.occupancy, op.hart) for op in state.operations))


# --------------------------------------------------------------------------
# The differential comparison, one entry per field the reference can decide
# --------------------------------------------------------------------------

def compare_acceptance(contract: RefContract,
                       conv: Conventions = EXACT) -> tuple[list[str], bool]:
    """Disagreements with phase_service, and whether the horizon left a case open."""
    module = acceptance_check(to_module(contract))
    reference, limited = explore_resolved(contract, "acceptance", conv)
    found: list[str] = []
    if module.zero_wait:
        if reference.refuted:
            found.append(f"acceptance-verdict: checker closes, reference refutes at cycle "
                         f"{reference.earliest} with {sorted(reference.reasons)}")
        elif reference.closed:
            if module.drain != reference.fabric_drain:
                found.append(f"acceptance-drain: checker {module.drain}, "
                             f"reference {reference.fabric_drain}")
        else:
            limited = True
        return found, limited

    outcome, sit, cycle = replay(contract, module.trace, mode="acceptance")
    if outcome is None or outcome.reason != module.reason:
        found.append(f"acceptance-trace-invalid: checker {module.reason} on trace "
                     f"{module.trace}, replay {outcome.reason if outcome else None} "
                     f"at cycle {cycle}")
        return found, limited
    projected = acceptance_projection(contract, sit, cycle)
    if projected != module.failure:
        found.append(f"acceptance-failure-state: checker {module.failure}, "
                     f"reference {projected} at cycle {cycle}")
    if reference.refuted:
        if cycle != reference.earliest:
            found.append(f"acceptance-earliest-cycle: checker {cycle}, "
                         f"reference {reference.earliest}")
    elif reference.closed:
        found.append(f"acceptance-verdict: checker refutes at cycle {cycle} with "
                     f"{module.reason}, reference closes")
    elif cycle < reference.horizon:
        found.append(f"acceptance-verdict: checker refutes at cycle {cycle} with "
                     f"{module.reason}, reference saw nothing within {reference.horizon}")
    else:
        limited = True
    return found, limited


def compare_completion(contract: RefContract,
                       conv: Conventions = EXACT) -> tuple[list[str], bool]:
    """Disagreements with phase_completion, and whether the horizon left a case open."""
    module = completion_check(to_module(contract))
    reference, limited = explore_resolved(contract, "completion", conv)
    found: list[str] = []
    failure = module_completion_state(module.failure) if module.failure else None
    if module.ordered is True:
        if module.drain_status != "finite" or module.quiescent_drain is None:
            found.append(f"completion-drain-status: closure reported "
                         f"{module.drain_status} with drain {module.quiescent_drain}")
        if reference.refuted:
            found.append(f"completion-verdict: checker closes, reference refutes at cycle "
                         f"{reference.earliest} with {sorted(reference.reasons)}")
        elif reference.closed:
            if module.quiescent_drain != reference.quiescent_drain:
                found.append(f"completion-quiescent-drain: checker {module.quiescent_drain}, "
                             f"reference {reference.quiescent_drain}")
        else:
            limited = True
        return found, limited

    # A refutation: `ordered` is false only for a completion-order inversion.
    expected_ordered = False if module.reason == "completion-order-inverted" else None
    if module.ordered is not expected_ordered:
        found.append(f"completion-ordered-flag: checker {module.ordered} for "
                     f"reason {module.reason}")
    if module.quiescent_drain is not None:
        found.append(f"completion-drain-status: refutation carries universal drain "
                     f"{module.quiescent_drain}")

    if module.reason is not None and module.reason.startswith("drain-"):
        if module.drain_status != "blocked":
            found.append(f"completion-drain-status: checker {module.drain_status} for "
                         f"reason {module.reason}")
        sit = replay_prefix(contract, module.trace, mode="completion")
        cycle = len(module.trace)
        if sit is None:
            found.append(f"completion-trace-invalid: prefix {module.trace} does not apply")
            return found, limited
        projected = completion_projection(contract, sit, cycle)
        if projected != failure:
            found.append(f"completion-failure-state: checker {failure}, "
                         f"reference {projected} at cycle {cycle}")
        cycles, blocked = drain(contract, cycle, sit, conv)
        if blocked is None or blocked.reason != module.reason or cycles != module.drain_cycles:
            found.append(f"completion-drain-replay: checker {module.reason} after "
                         f"{module.drain_cycles} cycles, reference "
                         f"{blocked.reason if blocked else None} after {cycles}")
            return found, limited
        current = sit
        for offset in range(cycles):
            forward = step(contract, cycle + offset, current, (), order_checks=False,
                           completion_checks=False)
            if isinstance(forward, Failure):
                found.append(f"completion-drain-replay: empty cycle {cycle + offset} "
                             f"blocked with {forward.reason} before the reported boundary")
                return found, limited
            current = forward
        projected_drain = completion_projection(contract, current, cycle + cycles)
        reported_drain = (module_completion_state(module.drain_failure)
                          if module.drain_failure else None)
        if projected_drain != reported_drain:
            found.append(f"completion-drain-failure-state: checker {reported_drain}, "
                         f"reference {projected_drain}")
    else:
        if module.drain_status != "not-evaluated":
            found.append(f"completion-drain-status: checker {module.drain_status} for "
                         f"reason {module.reason}")
        outcome, sit, cycle = replay(contract, module.trace, mode="completion")
        # phase_completion renames the acceptance-order inversion; nothing else moves.
        replayed = ("acceptance-order-inverted" if outcome and outcome.reason == "order-inverted"
                    else outcome.reason if outcome else None)
        if replayed != module.reason:
            found.append(f"completion-trace-invalid: checker {module.reason} on trace "
                         f"{module.trace}, replay {replayed} at cycle {cycle}")
            return found, limited
        projected = completion_projection(contract, sit, cycle)
        if projected != failure:
            found.append(f"completion-failure-state: checker {failure}, "
                         f"reference {projected} at cycle {cycle}")

    if reference.refuted:
        if cycle != reference.earliest:
            found.append(f"completion-earliest-cycle: checker {cycle}, "
                         f"reference {reference.earliest}")
    elif reference.closed:
        found.append(f"completion-verdict: checker refutes at cycle {cycle} with "
                     f"{module.reason}, reference closes")
    elif cycle < reference.horizon:
        found.append(f"completion-verdict: checker refutes at cycle {cycle} with "
                     f"{module.reason}, reference saw nothing within {reference.horizon}")
    else:
        limited = True
    return found, limited


def compare(contract: RefContract, conv: Conventions = EXACT) -> tuple[list[str], bool]:
    """Both checkers against the reference on one contract."""
    acceptance, acceptance_limited = compare_acceptance(contract, conv)
    completion, completion_limited = compare_completion(contract, conv)
    return acceptance + completion, acceptance_limited or completion_limited


# --------------------------------------------------------------------------
# Random contracts, the shape the campaign draws from
# --------------------------------------------------------------------------

def random_contract(rng: random.Random) -> RefContract:
    """A small contract, half the draws biased towards closure.

    An unbiased draw refutes early most of the time, usually on the grant, which
    exercises nothing past cycle zero. The biased flavour keeps each batch within
    its grant, uses distinct banks inside a batch and prefers short occupancies, so
    frame wrap, in-flight ordering, completion ordering and drain are reached.
    """
    biased = rng.random() < 0.5
    banks = rng.randint(1, 3)
    phases = rng.randint(1, 3)
    grants = tuple(rng.randint(0, 2) for _ in range(phases))
    max_hart = rng.choice([0, 0, 1, 1, 1])

    def request(exclude: set[int]) -> Request:
        choices = [bank for bank in range(banks) if bank not in exclude] or list(range(banks))
        bank = rng.choice(choices)
        occ = rng.choice([1, 1, 2, 3]) if biased else rng.randint(1, 3)
        if rng.random() < 0.5:
            return (bank, occ)
        return (bank, occ, rng.randint(0, max_hart))

    arrivals: list[tuple[Batch, ...]] = []
    for phase in range(phases):
        alternatives: list[Batch] = []
        for _ in range(rng.randint(1, 3)):
            if rng.random() < 0.35:
                alternatives.append(())
                continue
            size = rng.choice([1, 1, 1, 2, 2, 3])
            if biased:
                size = min(size, grants[phase])
            batch: list[Request] = []
            used: set[int] = set()
            for _ in range(size):
                drawn = request(used if biased else set())
                used.add(drawn[0])
                batch.append(drawn)
            alternatives.append(tuple(batch))
        arrivals.append(tuple(alternatives))

    paths: tuple[int, ...] = ()
    if rng.random() < 0.6:
        paths = tuple(rng.choice([0, 0, 1, 2]) for _ in range(banks))
    refresh: tuple[tuple[tuple[int, int], ...], ...] = ()
    if rng.random() < 0.35:
        table: list[tuple[tuple[int, int], ...]] = []
        for _ in range(phases):
            if rng.random() < 0.5:
                chosen = rng.sample(range(banks), k=rng.randint(1, banks))
                table.append(tuple((bank, rng.randint(1, 3)) for bank in chosen))
            else:
                table.append(())
        refresh = tuple(table)
    return RefContract(grants=grants, arrivals=tuple(arrivals), banks=banks,
                       refresh=refresh, paths=paths)


# --------------------------------------------------------------------------
# The verdicts the documents publish, pinned here as the reference's answer key
# --------------------------------------------------------------------------

# store-buffer.md, "Reproducible phase contracts": the verdict of each refuted fixture.
REFUTED_REASONS = {
    "average-gap-grant-2-0.json": "arrival-blocked",
    "joint-two-harts-one-bank.json": "arrival-blocked",
    "frame-wrap-final-write.json": "arrival-blocked",
    "multi-frame-residue.json": "arrival-blocked",
    "path-order-inversion.json": "order-inverted",
    "second-class-refresh-slot.json": "arrival-blocked",
    "shared-island-rotation.json": "arrival-blocked",
}

# phase_service.scenarios(), as test_phase_service.py states each one:
# closed or refuted, the refusal reason, and the fabric drain of a closed set.
SCENARIO_VERDICTS: dict[str, tuple[str, str | None, int | None]] = {
    "average-gap": ("refuted", "arrival-blocked", None),
    "joint-bank-conflict": ("refuted", "arrival-blocked", None),
    "frame-wrap": ("refuted", "arrival-blocked", None),
    "restricted-arrivals": ("closed", None, 0),
    "independent-banks": ("closed", None, 0),
    "refresh-arrival": ("refuted", "arrival-blocked", None),
    "refresh-write-overlap": ("refuted", "refresh-overlap", None),
    "refresh-wrap": ("refuted", "arrival-blocked", None),
    "refresh-quiet-window": ("closed", None, 0),
    "refresh-other-bank": ("closed", None, 0),
    "path-order": ("refuted", "order-inverted", None),
    "path-equal": ("closed", None, 1),
    "path-other-hart": ("closed", None, 2),
    "path-bank-busy": ("refuted", "path-blocked", None),
}

# completion-model.md and test_phase_completion.py, read as absolute cycle times.
HAND_COMPUTED: list[tuple[RefContract, str, str, str | None]] = [
    # The worked example: an occupancy-three operation at cycle zero and the same
    # hart's occupancy-one operation at cycle one complete in cycles two and one.
    (RefContract((1, 1, 0), ((((0, 3),),), (((1, 1),),), ((),)), banks=2),
     "acceptance", "closed", None),
    (RefContract((1, 1, 0), ((((0, 3),),), (((1, 1),),), ((),)), banks=2),
     "completion", "refuted", "completion-order-inverted"),
    # A shorter path to a later bank inverts one hart's acceptance order.
    (RefContract((1, 1), ((((0, 1),),), (((1, 1),),)), banks=2, paths=(2, 0)),
     "acceptance", "refuted", "order-inverted"),
    # A request that leaves the core and finds its bank taken is a fabric queue.
    (RefContract((1, 1), ((((0, 2),),), (((0, 1),),)), paths=(1,)),
     "acceptance", "refuted", "path-blocked"),
    # Refresh cannot preempt a write across frame wrap, even without arrivals.
    (RefContract((1, 1), (((),), ((), ((0, 2),))), refresh=(((0, 1),), ())),
     "acceptance", "refuted", "refresh-overlap"),
    # Drain must not invent a finite bound through a refresh collision.
    (RefContract((1, 0, 0), ((((0, 1),),), ((),), ((),)), paths=(2,),
                 refresh=((), (), ((0, 1),))),
     "completion", "refuted", "drain-path-blocked"),
]

# The quiescent drain each closed contract carries, quoted from test_phase_completion.py.
HAND_COMPUTED_DRAINS: list[tuple[RefContract, int]] = [
    # An occupied bank with no flight still has two residual cycles.
    (RefContract((1, 0, 0), ((((0, 3),),), ((),), ((),))), 2),
    # One occupied acceptance cycle completes before the next boundary.
    (RefContract((1,), ((((0, 1),),),)), 0),
    # Two remaining fabric cycles plus three occupancy cycles share acceptance.
    (RefContract((1, 0, 0, 0, 0), ((((0, 3),),), ((),), ((),), ((),), ((),)), paths=(2,)), 4),
    # A one-cycle path drains in one cycle.
    (RefContract((1,), ((((0, 1),),),), paths=(1,)), 1),
    # Perpetual refresh is maintenance, not issued workload that prevents drain.
    (RefContract((0,), (((),),), refresh=(((0, 1),),)), 0),
    # Refresh remains scheduled while the workload drains.
    (RefContract((1, 0, 0, 0, 0), ((((0, 2),),), ((),), ((),), ((),), ((),)), paths=(1,),
                 refresh=((), (), (), ((0, 2),), ())), 2),
    # Continuing refresh on another bank neither extends nor erases the drain.
    (RefContract((1, 0, 0), ((((0, 3),),), ((),), ((),)), banks=2,
                 refresh=(((1, 1),), ((1, 1),), ((1, 1),))), 2),
]

# The contract the perturbation control bends a convention on: one path-one request
# in a two-phase frame, which closes with exactly one cycle of fabric residue and
# one cycle of quiescent drain, so a one-cycle error in either convention shows.
CONTROL_CONTRACT = RefContract((1, 0), ((((0, 1),),), ((),)), paths=(1,))

# The two contracts whose reading the campaign had to adjudicate.
ADJUDICATED_PATH_BLOCKED = RefContract((1,), ((((0, 2),),),), paths=(1,))
ADJUDICATED_DRAIN_REFRESH = RefContract((1, 0), ((((0, 2),),), ((),)), paths=(1,),
                                        refresh=(((0, 1),), ()))


# --------------------------------------------------------------------------
# Cases
# --------------------------------------------------------------------------

def _tracked_fixtures() -> None:
    """The reference alone decides every tracked fixture as the comparison says."""
    for folder, expect_closed in (("closed", True), ("refuted", False)):
        files = sorted((FIXTURES / folder).glob("*.json"))
        ensure(bool(files), f"{folder} holds no contract for the reference to decide")
        if not expect_closed:
            ensure({path.name for path in files} == set(REFUTED_REASONS),
                   "every refuted fixture needs its published reason pinned here")
        for path in files:
            contract = from_json(path)
            result = explore(contract, default_horizon(contract), "acceptance")
            ensure(result.verdict == ("closed" if expect_closed else "refuted"),
                   f"{folder}/{path.name}: reference says {result.verdict}")
            if expect_closed:
                continue
            published = REFUTED_REASONS[path.name]
            ensure(published in result.reasons,
                   f"refuted/{path.name}: reference refuses with {sorted(result.reasons)}, "
                   f"not the published {published}")


def _scenarios() -> None:
    """The reference alone decides every scenario as the behavioral tests state it."""
    named = scenarios()
    ensure(set(named) == set(SCENARIO_VERDICTS),
           f"scenario set moved: {sorted(set(named) ^ set(SCENARIO_VERDICTS))}")
    for name, contract in named.items():
        expected, reason, fabric = SCENARIO_VERDICTS[name]
        reference = from_module(contract)
        result = explore(reference, default_horizon(reference), "acceptance")
        ensure(result.verdict == expected,
               f"{name}: reference says {result.verdict}, documents say {expected}")
        ensure(reason is None or reason in result.reasons,
               f"{name}: reference refuses with {sorted(result.reasons)}, not {reason}")
        ensure(fabric is None or result.fabric_drain == fabric,
               f"{name}: reference drain {result.fabric_drain}, documents say {fabric}")


def _hand_computed() -> None:
    """The worked examples decide by absolute cycle time, not by a state residue."""
    for contract, mode, expected, reason in HAND_COMPUTED:
        result = explore(contract, default_horizon(contract), mode)
        ensure(result.verdict == expected,
               f"{mode} {contract}: reference says {result.verdict}, not {expected}")
        ensure(reason is None or reason in result.reasons,
               f"{mode} {contract}: reasons {sorted(result.reasons)} omit {reason}")
    for contract, expected in HAND_COMPUTED_DRAINS:
        result = explore(contract, default_horizon(contract), "completion")
        ensure(result.closed and result.quiescent_drain == expected,
               f"{contract}: reference drains in {result.quiescent_drain}, not {expected}")


def _campaign() -> None:
    """A seeded differential campaign: both checkers against the reference.

    Every contract must agree on every field the reference can decide. The floors
    below keep a generator that stopped producing interesting contracts, or a
    horizon that stopped resolving them, from passing this vacuously.
    """
    rng = random.Random(CAMPAIGN_SEED)  # noqa: S311 - a fixed differential campaign, no secrets
    agreements = 0
    limited = 0
    closures = 0
    drains = 0
    disagreements: list[str] = []
    for index in range(CAMPAIGN_CONTRACTS):
        contract = random_contract(rng)
        found, horizon_limited = compare(contract)
        if found:
            disagreements.append(f"contract {index} {contract}: {found}")
            if len(disagreements) > 3:
                break
        elif horizon_limited:
            limited += 1
        else:
            agreements += 1
        result = completion_check(to_module(contract))
        if result.ordered is True:
            closures += 1
        if result.quiescent_drain is not None and result.quiescent_drain > 0:
            drains += 1
    ensure(not disagreements, "checker and reference disagree: " + "; ".join(disagreements))
    ensure(agreements == CAMPAIGN_CONTRACTS,
           f"{limited} of {CAMPAIGN_CONTRACTS} contracts stayed open at the reference horizon")
    ensure(closures > CAMPAIGN_CONTRACTS // 20,
           f"only {closures} of {CAMPAIGN_CONTRACTS} contracts closed: the campaign is "
           f"comparing refutations alone")
    ensure(drains > CAMPAIGN_CONTRACTS // 100,
           f"only {drains} contracts reached a nonzero quiescent drain")


def _perturbation_control() -> None:
    """A one-convention error in the reference must surface as a disagreement.

    Without this the campaign's silence would be evidence about nothing: a
    reference that agreed by construction would agree with a wrong checker too.
    """
    exact, limited = compare(CONTROL_CONTRACT)
    ensure(not exact and not limited,
           f"the control contract must agree exactly first: {exact}")
    transit, _ = compare(CONTROL_CONTRACT, Conventions(transit_bias=1))
    ensure(any(entry.startswith("acceptance-drain:") for entry in transit),
           f"an off-by-one transit count went unreported: {transit}")
    drain_shift, _ = compare(CONTROL_CONTRACT, Conventions(drain_bias=1))
    ensure(any(entry.startswith("completion-quiescent-drain:") for entry in drain_shift),
           f"an off-by-one quiescent drain went unreported: {drain_shift}")


def _adjudicated() -> None:
    """The two readings the campaign had to settle, pinned as regressions.

    Both turn on R7: a request issued in cycle zero over a one-cycle path accepts
    in cycle one, so it holds one transit cycle at boundary one and its bank
    through its occupancy from cycle one.
    """
    # A second request issued in cycle one reaches the bank in cycle two, where the
    # first request's occupancy still stands. The reference attributes the fabric
    # queue to cycle two, and carries one cycle of fabric residue on the way there.
    contract = ADJUDICATED_PATH_BLOCKED
    result = explore(contract, default_horizon(contract), "acceptance")
    ensure(result.verdict == "refuted" and result.earliest == 2
           and result.reasons == frozenset({"path-blocked"}) and result.fabric_drain == 1,
           f"path-blocked adjudication moved: {result}")
    module = acceptance_check(to_module(contract))
    ensure(not module.zero_wait and module.reason == "path-blocked"
           and len(module.trace) == 2 and module.drain is None,
           f"the checker no longer reads the path-blocked contract as adjudicated: {module}")
    ensure(not compare(contract)[0], "the adjudicated path-blocked contract must agree")

    # The refresh in phase zero of the next frame collides with the drain of the
    # request issued at cycle zero. The block is attributed to its source boundary,
    # cycle one, and reached after one empty-arrival cycle, at boundary two.
    contract = ADJUDICATED_DRAIN_REFRESH
    prefix = replay_prefix(contract, (((0, 2),),), mode="completion")
    ensure(prefix is not None, "the adjudicated drain contract's first cycle must apply")
    cycles, blocked = drain(contract, 1, prefix or EMPTY)
    ensure(blocked is not None and blocked.cycle == 1 and blocked.reached == 2
           and blocked.reason == "drain-refresh-overlap" and cycles == 1,
           f"drain attribution moved: {cycles} cycles, {blocked}")
    completion = completion_check(to_module(contract))
    ensure(completion.reason == "drain-refresh-overlap" and completion.drain_status == "blocked"
           and len(completion.trace) == 1 and completion.drain_cycles == 1
           and completion.drain_failure is not None and completion.drain_failure.phase == 0,
           f"the checker no longer reads the drain contract as adjudicated: {completion}")
    ensure(not compare(contract)[0], "the adjudicated drain contract must agree")


def cases() -> list[Case]:
    return [Case("tracked-fixtures", _tracked_fixtures), Case("scenarios", _scenarios),
            Case("hand-computed", _hand_computed),
            Case("perturbation-control", _perturbation_control),
            Case("adjudicated", _adjudicated), Case("campaign", _campaign)]
