# SPDX-License-Identifier: Apache-2.0
"""Finite synthetic issue-acceptance model for Q22e; no target qualification.

Each phase lists every permitted joint request set. A request is (bank, occupancy),
where occupancy includes its issue cycle. Banks accept at most one request per
cycle; phase grants bound total injection. Empty arrivals are explicit alternatives.
The initial state is phase zero with empty banks. No queue or stalled transition
is modeled: the first permitted set that cannot issue refutes universal zero wait.
"""

from collections import deque
from dataclasses import dataclass

type Request = tuple[int, int]
type Batch = tuple[Request, ...]
type State = tuple[int, tuple[int, ...]]


@dataclass(frozen=True)
class Contract:
    grants: tuple[int, ...]
    arrivals: tuple[tuple[Batch, ...], ...]
    banks: int = 1


@dataclass(frozen=True)
class Result:
    zero_wait: bool
    states: int
    trace: tuple[Batch, ...] = ()
    failure: State | None = None


def check(contract: Contract) -> Result:
    """Explore to closure, or return a shortest failing arrival trace.

    A successful result covers arbitrarily many frames of this finite contract,
    including all nondeterministic arrival histories, not just one frame replay.
    """
    if (contract.banks < 1 or not contract.grants
            or len(contract.grants) != len(contract.arrivals)
            or any(grant < 0 for grant in contract.grants)):
        raise ValueError("invalid bank count or phase grants")
    for alternatives in contract.arrivals:
        if not alternatives:
            raise ValueError("each phase needs an explicit arrival alternative")
        for batch in alternatives:
            if any(bank < 0 or bank >= contract.banks or duration < 1
                   for bank, duration in batch):
                raise ValueError("invalid bank or occupancy")
    initial: State = (0, (0,) * contract.banks)
    pending = deque([initial])
    paths: dict[State, tuple[Batch, ...]] = {initial: ()}
    while pending:
        state = pending.popleft()
        phase, busy = state
        for batch in contract.arrivals[phase]:
            trace = (*paths[state], batch)
            banks = [bank for bank, _ in batch]
            if (len(batch) > contract.grants[phase] or len(set(banks)) != len(banks)
                    or any(busy[bank] for bank in banks)):
                return Result(False, len(paths), trace, state)
            residue = [max(0, remaining - 1) for remaining in busy]
            for bank, duration in batch:
                residue[bank] = duration - 1
            successor = ((phase + 1) % len(contract.grants), tuple(residue))
            if successor not in paths:
                paths[successor] = trace
                pending.append(successor)
    return Result(True, len(paths))


def scenarios() -> dict[str, Contract]:
    one: Batch = ((0, 1),)
    write: Batch = ((0, 2),)
    return {
        "average-gap": Contract((2, 0), (((), one), ((), one))),
        "joint-bank-conflict": Contract((2,), ((one, (*one, *one)),)),
        "frame-wrap": Contract((1, 1), (((), one), ((), write))),
        "restricted-arrivals": Contract((1, 1), (((),), ((), write))),
        "independent-banks": Contract((2,), (((), ((0, 1), (1, 1))),), banks=2),
    }
