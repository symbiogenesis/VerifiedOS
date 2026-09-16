# SPDX-License-Identifier: Apache-2.0
"""Completion and quiescence in the finite phase contract, not physical visibility.

An operation completes at the end of its last occupied cycle. States name cycle
boundaries before refresh and new arrivals. Fabric transit counts cycles from the
boundary after issue; occupancy includes the acceptance cycle. Maintenance keeps
running during drain but is not itself an issued operation that must complete.
"""

from collections import deque
from dataclasses import dataclass

from vos.phase_service import Batch, Contract, _fields, _validate


@dataclass(frozen=True)
class Operation:
    bank: int
    transit: int
    occupancy: int
    hart: int


@dataclass(frozen=True)
class State:
    phase: int
    maintenance: tuple[int, ...]
    operations: tuple[Operation, ...]


@dataclass(frozen=True)
class Result:
    ordered: bool | None
    states: int
    trace: tuple[Batch, ...] = ()
    failure: State | None = None
    reason: str | None = None
    quiescent_drain: int | None = None
    drain_status: str = "not-evaluated"
    drain_failure: State | None = None
    drain_cycles: int | None = None


def _step(contract: Contract, refresh: tuple[Batch, ...], paths: tuple[int, ...],
          state: State, batch: Batch, *, ordering: bool) -> tuple[State | None, str | None]:
    """One no-queue cycle; optionally enforce acceptance and completion ordering."""
    phase, operations = state.phase, state.operations
    occupied = list(state.maintenance)
    for op in operations:
        if op.transit == 0:
            occupied[op.bank] = op.occupancy
    maintenance = list(state.maintenance)
    for bank, duration in refresh[phase]:
        if occupied[bank]:
            return None, "refresh-overlap"
        occupied[bank] = duration
        maintenance[bank] = duration
    active: list[Operation] = []
    waiting_harts: set[int] = set()
    for op in operations:
        if op.transit > 1:
            active.append(Operation(op.bank, op.transit - 1, op.occupancy, op.hart))
            waiting_harts.add(op.hart)
        elif op.transit == 1:
            if occupied[op.bank]:
                return None, "path-blocked"
            if ordering and op.hart in waiting_harts:
                return None, "acceptance-order-inverted"
            occupied[op.bank] = op.occupancy
            active.append(Operation(op.bank, 0, op.occupancy, op.hart))
        else:
            active.append(op)
    if len(batch) > contract.grants[phase]:
        return None, "arrival-blocked"
    for request in batch:
        bank, duration, hart = _fields(request)
        transit = paths[bank]
        if transit:
            waiting_harts.add(hart)
        else:
            if occupied[bank]:
                return None, "arrival-blocked"
            if ordering and hart in waiting_harts:
                return None, "acceptance-order-inverted"
            occupied[bank] = duration
        active.append(Operation(bank, transit, duration, hart))
    unfinished_harts: set[int] = set()
    remaining: list[Operation] = []
    for op in active:
        if op.transit:
            remaining.append(op)
            unfinished_harts.add(op.hart)
        elif op.occupancy > 1:
            remaining.append(Operation(op.bank, 0, op.occupancy - 1, op.hart))
            unfinished_harts.add(op.hart)
        elif ordering and op.hart in unfinished_harts:
            return None, "completion-order-inverted"
    successor = State((phase + 1) % len(contract.grants),
                      tuple(max(0, duration - 1) for duration in maintenance),
                      tuple(remaining))
    return successor, None


def _drain(contract: Contract, refresh: tuple[Batch, ...], paths: tuple[int, ...],
           initial: State) -> tuple[int, State | None, str | None]:
    """Stop arrivals and retain refresh; only issued operations determine the end."""
    state = initial
    elapsed = 0
    while state.operations:
        successor, reason = _step(contract, refresh, paths, state, (), ordering=False)
        if successor is None:
            return elapsed, state, reason
        state = successor
        elapsed += 1
    return elapsed, None, None


def check(contract: Contract) -> Result:
    """Explore all joint alternatives and frame wraps, retaining each issued op.

    A finite drain is the maximum over all reachable boundaries, not a bound on
    accepted fabric requests alone. A failure carries no universal drain bound.
    Removing arrivals for drain is deliberate even if empty is not an admitted
    alternative: it models a boundary that stops issue, not another workload mode.
    """
    refresh, paths = _validate(contract)
    initial = State(0, (0,) * contract.banks, ())
    pending = deque([initial])
    history: dict[State, tuple[Batch, ...]] = {initial: ()}
    maximum = 0
    while pending:
        state = pending.popleft()
        prefix = history[state]
        duration, drain_failure, drain_reason = _drain(contract, refresh, paths, state)
        if drain_failure is not None:
            return Result(None, len(history), prefix, state,
                          f"drain-{drain_reason}", drain_status="blocked",
                          drain_failure=drain_failure, drain_cycles=duration)
        maximum = max(maximum, duration)
        for batch in contract.arrivals[state.phase]:
            successor, reason = _step(contract, refresh, paths, state, batch, ordering=True)
            if successor is None:
                return Result(False if reason == "completion-order-inverted" else None,
                              len(history), (*prefix, batch), state, reason)
            if successor not in history:
                history[successor] = (*prefix, batch)
                pending.append(successor)
    return Result(True, len(history), quiescent_drain=maximum, drain_status="finite")
