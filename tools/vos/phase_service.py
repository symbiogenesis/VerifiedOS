# SPDX-License-Identifier: Apache-2.0
"""Finite synthetic issue-acceptance model for Q22e; no target qualification.

Each phase lists every permitted joint request set. A request is (bank, occupancy)
or (bank, occupancy, hart), where occupancy includes the acceptance cycle and the
hart defaults to zero. Banks accept at most one request per cycle; phase grants
bound total injection at issue. Empty arrivals are explicit alternatives. The
initial state is phase zero with empty banks and nothing in flight. No queue or
stalled transition is modeled: the first permitted set that cannot issue, or that
cannot be accepted when it reaches its bank, refutes universal zero wait.

Refresh reservations start before arrivals in their phase and occupy whole banks
for the stated duration, including that cycle. They must start on idle banks;
neither refresh nor requests may preempt a residual operation. Refresh uses no
injection grant in this synthetic contract; shared refresh ports are not modeled.

A bank's path is the number of cycles a request spends in the fabric between issue
and acceptance at that bank, zero meaning acceptance in the issue cycle. Requests
in flight reach their banks ahead of the phase's own batch, in issue order, and a
request that finds its bank taken on arrival is a queue in the fabric, which the
predicate forbids. One hart's requests must be accepted in issue order, batch order
standing for issue order within a cycle and acceptance within one cycle counting as
ordered: with no queue, a shorter path to a later bank either inverts that order or
costs a wait, and the model reports the inversion rather than inventing the wait.
The drain bound is the longest any reachable state keeps a request in flight ahead
of its acceptance, the residue a partition switch still waits out once the buffer
is gone; occupancy after acceptance is the bank's and is carried as a wait instead.
"""

from collections import deque
from dataclasses import dataclass

# A request is (bank, occupancy) or (bank, occupancy, hart); `check` refuses any
# other length, so the width is a validated fact rather than a type.
type Request = tuple[int, ...]
type Batch = tuple[Request, ...]
# One request in the fabric: bank, cycles until acceptance, occupancy, hart.
type Flight = tuple[int, int, int, int]
type State = tuple[int, tuple[int, ...], tuple[Flight, ...]]


@dataclass(frozen=True)
class Contract:
    grants: tuple[int, ...]
    arrivals: tuple[tuple[Batch, ...], ...]
    banks: int = 1
    refresh: tuple[Batch, ...] = ()
    paths: tuple[int, ...] = ()


@dataclass(frozen=True)
class Result:
    zero_wait: bool
    states: int
    trace: tuple[Batch, ...] = ()
    failure: State | None = None
    reason: str | None = None
    drain: int | None = None


def _fields(request: Request) -> tuple[int, int, int]:
    """(bank, occupancy, hart), the hart defaulting to zero."""
    bank, occupancy, *rest = request
    return bank, occupancy, rest[0] if rest else 0


def _validate(contract: Contract) -> tuple[tuple[Batch, ...], tuple[int, ...]]:
    """Refuse a malformed contract; return the refresh and path tables in full."""
    phases = len(contract.grants)
    if (contract.banks < 1 or not phases or len(contract.arrivals) != phases
            or any(grant < 0 for grant in contract.grants)):
        raise ValueError("invalid bank count or phase grants")
    for alternatives in contract.arrivals:
        if not alternatives:
            raise ValueError("each phase needs an explicit arrival alternative")
        for batch in alternatives:
            for request in batch:
                if len(request) not in (2, 3):
                    raise ValueError("a request is (bank, occupancy) or (bank, occupancy, hart)")
                bank, occupancy, hart = _fields(request)
                if bank < 0 or bank >= contract.banks or occupancy < 1 or hart < 0:
                    raise ValueError("invalid bank, occupancy or hart")
    refresh = contract.refresh or ((),) * phases
    if len(refresh) != phases:
        raise ValueError("refresh must cover every phase")
    for batch in refresh:
        if (len({entry[0] for entry in batch}) != len(batch)
                or any(len(entry) != 2 or entry[0] < 0 or entry[0] >= contract.banks
                       or entry[1] < 1 for entry in batch)):
            raise ValueError("invalid refresh bank or occupancy")
    paths = contract.paths or (0,) * contract.banks
    if len(paths) != contract.banks or any(path < 0 for path in paths):
        raise ValueError("paths must state one non-negative fabric latency per bank")
    return refresh, paths


def check(contract: Contract) -> Result:
    """Explore to closure, or return a shortest failing arrival trace.

    A successful result covers arbitrarily many frames of this finite contract,
    including all nondeterministic arrival histories, not just one frame replay.
    """
    refresh, paths = _validate(contract)
    initial: State = (0, (0,) * contract.banks, ())
    pending: deque[State] = deque([initial])
    history: dict[State, tuple[Batch, ...]] = {initial: ()}
    drain = 0
    while pending:
        state = pending.popleft()
        phase, busy, flight = state
        prefix = history[state]
        drain = max([drain, *(remaining for _, remaining, _, _ in flight)])
        reserved = list(busy)
        for entry in refresh[phase]:
            if busy[entry[0]]:
                return Result(False, len(history), prefix, state, "refresh-overlap")
            reserved[entry[0]] = entry[1]
        launched: list[Flight] = []
        for bank, remaining, occupancy, hart in flight:
            if remaining > 1:
                launched.append((bank, remaining - 1, occupancy, hart))
            elif reserved[bank]:
                return Result(False, len(history), prefix, state, "path-blocked")
            elif any(other == hart for _, _, _, other in launched):
                return Result(False, len(history), prefix, state, "order-inverted")
            else:
                reserved[bank] = occupancy
        for batch in contract.arrivals[phase]:
            trace = (*prefix, batch)
            if len(batch) > contract.grants[phase]:
                return Result(False, len(history), trace, state, "arrival-blocked")
            accepting = list(reserved)
            issued = list(launched)
            for request in batch:
                bank, occupancy, hart = _fields(request)
                if paths[bank]:
                    issued.append((bank, paths[bank], occupancy, hart))
                elif accepting[bank]:
                    return Result(False, len(history), trace, state, "arrival-blocked")
                elif any(other == hart for _, _, _, other in issued):
                    return Result(False, len(history), trace, state, "order-inverted")
                else:
                    accepting[bank] = occupancy
            successor: State = ((phase + 1) % len(contract.grants),
                                tuple(max(0, cycles - 1) for cycles in accepting),
                                tuple(issued))
            if successor not in history:
                history[successor] = trace
                pending.append(successor)
    return Result(True, len(history), drain=drain)


def scenarios() -> dict[str, Contract]:
    one: Batch = ((0, 1),)
    write: Batch = ((0, 2),)
    far: Batch = ((0, 1),)
    near: Batch = ((1, 1),)
    return {
        "average-gap": Contract((2, 0), (((), one), ((), one))),
        "joint-bank-conflict": Contract((2,), ((one, (*one, *one)),)),
        "frame-wrap": Contract((1, 1), (((), one), ((), write))),
        "restricted-arrivals": Contract((1, 1), (((),), ((), write))),
        "independent-banks": Contract((2,), (((), ((0, 1), (1, 1))),), banks=2),
        "refresh-arrival": Contract((1,), (((), one),), refresh=(one,)),
        "refresh-write-overlap": Contract((1, 1), (((),), ((), write)),
                                          refresh=(one, ())),
        "refresh-wrap": Contract((1, 1), (((), one), ((),)), refresh=((), write)),
        "refresh-quiet-window": Contract((1, 1, 1), (((),), ((),), ((), one)),
                                         refresh=(write, (), ())),
        "refresh-other-bank": Contract((1,), (((), ((1, 1),)),), banks=2,
                                       refresh=(one,)),
        "path-order": Contract((1, 1), ((far,), (near,)), banks=2, paths=(2, 0)),
        "path-equal": Contract((1, 1), ((far,), (near,)), banks=2, paths=(1, 1)),
        "path-other-hart": Contract((1, 1), ((((0, 1, 0),),), (((1, 1, 1),),)),
                                    banks=2, paths=(2, 0)),
        "path-bank-busy": Contract((1, 1), ((write,), (one,)), paths=(1,)),
    }
