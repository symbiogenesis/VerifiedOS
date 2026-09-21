# SPDX-License-Identifier: Apache-2.0
"""Declared global modes and their transitions over Q22e's finite phase-service model.

A `phase-schedule-v2` declaration names a set of modes, each a periodic table in
the v1 shape, the modes the machine may start in, and the directed transitions
between them: a switch may occur at the end of `from_phase` of mode `from`, and
mode `to` resumes at `to_phase`. The exploration is the product of mode, phase,
bank occupancy and requests in flight. A switch is a change of boundary label
with no fence and no queue: the boundary state is carried unchanged into the
target's next cycle, so a residual write, a running refresh or a request in
flight meets the target's table exactly as the continuation would have met the
source's. Each mode's cycle runs as `phase_service` and `phase_completion` run
it; the product checkers keep those checkers' state shapes and reason
vocabulary, extended only by the mode. A single-mode declaration with no
transitions emits and decides exactly as the v1 declaration of that table does.

The mode-transition mechanism, its dwell and budget, the executive's own switch
work, initial states other than empty and the edge certificates R-11-018 owns
are outside this model; docs/implementation/phase-service/mode-contract.md states
the scope and the gaps it records for the register's owner.
"""

import hashlib
import json
import re
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import cast

from vos import phase_schedule
from vos.jsonc import Json
from vos.phase_completion import Operation as CompletionOperation
from vos.phase_completion import State as CompletionState
from vos.phase_completion import _drain, _step
from vos.phase_schedule import (
    Extraction,
    _alternatives,
    _decode,
    _integer,
    _name,
    _object,
    _refresh,
    _resources,
    _rows,
    contract_bytes,
)
from vos.phase_service import Batch, Contract, Flight, _fields, _validate

SCHEMA = "phase-schedule-v2"
FIELDS = frozenset({"schema", "name", "resources_sha256", "modes", "initial", "transitions"})

# One trace step names the mode and phase whose cycle took the step's batch.
type Step = tuple[str, int]
# The acceptance state, `phase_service.State` with a leading mode name.
type ModeState = tuple[str, int, tuple[int, ...], tuple[Flight, ...]]
type Tables = dict[str, tuple[Contract, tuple[Batch, ...], tuple[int, ...]]]
type Switches = dict[tuple[str, int], tuple[tuple[int, str, int], ...]]


@dataclass(frozen=True)
class Transition:
    """One declared directed edge; `source` and `target` are the JSON `from` and `to`."""

    source: str
    from_phase: int
    target: str
    to_phase: int

    def to_json(self) -> dict[str, Json]:
        return {"from": self.source, "from_phase": self.from_phase,
                "to": self.target, "to_phase": self.to_phase}


@dataclass(frozen=True)
class ModeContract:
    """Every declared mode's v1 table, the initial modes and the transitions, in order."""

    initial: tuple[str, ...]
    modes: dict[str, Contract]
    transitions: tuple[Transition, ...] = ()


@dataclass(frozen=True)
class ModeInjectionExcess:
    mode: str
    phase: int
    alternative: int
    requests: int
    grant: int


@dataclass(frozen=True)
class ModeExtraction:
    name: str
    schedule_sha256: str
    resources_sha256: str
    bank_names: tuple[str, ...]
    hart_names: tuple[str, ...]
    operation_names: tuple[str, ...]
    injection_excesses: tuple[ModeInjectionExcess, ...]
    contract: ModeContract


@dataclass(frozen=True)
class ModeResult:
    """`phase_service.Result` with the mode of every step, the per-mode state counts
    and the declared transitions whose switch successor the exploration generated."""

    zero_wait: bool
    states: int
    trace: tuple[Batch, ...] = ()
    failure: ModeState | None = None
    reason: str | None = None
    drain: int | None = None
    trace_modes: tuple[Step, ...] = ()
    mode_states: dict[str, int] = field(default_factory=dict)
    transitions_taken: tuple[int, ...] = ()


@dataclass(frozen=True)
class ModeCompletionState:
    """`phase_completion.State` with a leading mode name."""

    mode: str
    phase: int
    maintenance: tuple[int, ...]
    operations: tuple[CompletionOperation, ...]


@dataclass(frozen=True)
class ModeCompletionResult:
    ordered: bool | None
    states: int
    trace: tuple[Batch, ...] = ()
    failure: ModeCompletionState | None = None
    reason: str | None = None
    quiescent_drain: int | None = None
    drain_status: str = "not-evaluated"
    drain_failure: ModeCompletionState | None = None
    drain_cycles: int | None = None
    trace_modes: tuple[Step, ...] = ()
    mode_states: dict[str, int] = field(default_factory=dict)
    transitions_taken: tuple[int, ...] = ()


def _tables(contract: ModeContract) -> Tables:
    """Refuse a malformed mode contract; return every mode's validated tables.

    The refusals are the contract's: an undeclared mode name, an out-of-range
    phase index, a duplicate transition or initial mode, a switch whose target is
    the source's own continuation, and a declared mode no initial mode reaches.
    """
    if not contract.modes:
        raise ValueError("a mode contract declares at least one mode")
    tables: Tables = {}
    for name, table in contract.modes.items():
        refresh, paths = _validate(table)
        tables[name] = (table, refresh, paths)
    if (len({table.banks for table, _, _ in tables.values()}) != 1
            or len({paths for _, _, paths in tables.values()}) != 1):
        raise ValueError("every mode must share one bank count and one path table")
    if not contract.initial or len(set(contract.initial)) != len(contract.initial):
        raise ValueError("initial must be a nonempty list of distinct mode names")
    for name in contract.initial:
        if name not in tables:
            raise ValueError(f"initial names an undeclared mode: {name}")
    seen: set[Transition] = set()
    for transition in contract.transitions:
        for name in (transition.source, transition.target):
            if name not in tables:
                raise ValueError(f"transition names an undeclared mode: {name}")
        length = len(tables[transition.source][0].grants)
        if not 0 <= transition.from_phase < length:
            raise ValueError(f"from_phase {transition.from_phase} is out of range for mode "
                             f"{transition.source}")
        if not 0 <= transition.to_phase < len(tables[transition.target][0].grants):
            raise ValueError(f"to_phase {transition.to_phase} is out of range for mode "
                             f"{transition.target}")
        if transition in seen:
            raise ValueError(f"duplicate transition: {transition.to_json()}")
        seen.add(transition)
        if (transition.source == transition.target
                and transition.to_phase == (transition.from_phase + 1) % length):
            raise ValueError(f"no-op transition into the source's own continuation: "
                             f"{transition.to_json()}")
    reachable = set(contract.initial)
    frontier = deque(contract.initial)
    while frontier:
        mode = frontier.popleft()
        for transition in contract.transitions:
            if transition.source == mode and transition.target not in reachable:
                reachable.add(transition.target)
                frontier.append(transition.target)
    unreachable = [name for name in tables if name not in reachable]
    if unreachable:
        raise ValueError(f"no initial mode reaches declared mode(s): {', '.join(unreachable)}")
    return tables


def _switches(contract: ModeContract) -> Switches:
    """The declared switches from each point, in declaration order with their indices."""
    switches: dict[tuple[str, int], list[tuple[int, str, int]]] = {}
    for index, transition in enumerate(contract.transitions):
        switches.setdefault((transition.source, transition.from_phase), []).append(
            (index, transition.target, transition.to_phase))
    return {point: tuple(edges) for point, edges in switches.items()}


def _counts(contract: ModeContract, modes: list[str]) -> dict[str, int]:
    """Every declared mode's distinct state count, zero for a mode never entered."""
    counts = dict.fromkeys(contract.modes, 0)
    for mode in modes:
        counts[mode] += 1
    return counts


def check(contract: ModeContract) -> ModeResult:
    """Explore the reachable product to closure, or to its earliest failing cycle.

    Every initial mode is seeded in declared order and the exploration proceeds
    breadth-first. At each dequeued state the alternatives are taken in declared
    order and, for each, the continuation successor is enqueued before the switch
    successors in transition declaration order, identical states merging on first
    discovery. A failure belongs to the mode whose cycle detected it.
    """
    tables = _tables(contract)
    switches = _switches(contract)
    banks = next(iter(tables.values()))[0].banks
    pending: deque[ModeState] = deque()
    history: dict[ModeState, tuple[tuple[Batch, ...], tuple[Step, ...]]] = {}
    for mode in contract.initial:
        initial: ModeState = (mode, 0, (0,) * banks, ())
        history[initial] = ((), ())
        pending.append(initial)
    taken: set[int] = set()
    drain = 0

    def failed(trace: tuple[Batch, ...], steps: tuple[Step, ...], state: ModeState,
               reason: str) -> ModeResult:
        return ModeResult(False, len(history), trace, state, reason, trace_modes=steps,
                          mode_states=_counts(contract, [known[0] for known in history]),
                          transitions_taken=tuple(sorted(taken)))

    while pending:
        state = pending.popleft()
        mode, phase, busy, flight = state
        table, refresh, paths = tables[mode]
        prefix, steps = history[state]
        drain = max([drain, *(remaining for _, remaining, _, _ in flight)])
        reserved = list(busy)
        for entry in refresh[phase]:
            if busy[entry[0]]:
                return failed(prefix, steps, state, "refresh-overlap")
            reserved[entry[0]] = entry[1]
        launched: list[Flight] = []
        for bank, remaining, occupancy, hart in flight:
            if remaining > 1:
                launched.append((bank, remaining - 1, occupancy, hart))
            elif reserved[bank]:
                return failed(prefix, steps, state, "path-blocked")
            elif any(other == hart for _, _, _, other in launched):
                return failed(prefix, steps, state, "order-inverted")
            else:
                reserved[bank] = occupancy
        for batch in table.arrivals[phase]:
            trace = (*prefix, batch)
            trace_steps = (*steps, (mode, phase))
            if len(batch) > table.grants[phase]:
                return failed(trace, trace_steps, state, "arrival-blocked")
            accepting = list(reserved)
            issued = list(launched)
            for request in batch:
                bank, occupancy, hart = _fields(request)
                if paths[bank]:
                    issued.append((bank, paths[bank], occupancy, hart))
                elif accepting[bank]:
                    return failed(trace, trace_steps, state, "arrival-blocked")
                elif any(other == hart for _, _, _, other in issued):
                    return failed(trace, trace_steps, state, "order-inverted")
                else:
                    accepting[bank] = occupancy
            carried = tuple(max(0, cycles - 1) for cycles in accepting)
            successors: list[ModeState] = [
                (mode, (phase + 1) % len(table.grants), carried, tuple(issued))]
            for index, target, to_phase in switches.get((mode, phase), ()):
                taken.add(index)
                successors.append((target, to_phase, carried, tuple(issued)))
            for successor in successors:
                if successor not in history:
                    history[successor] = (trace, trace_steps)
                    pending.append(successor)
    return ModeResult(True, len(history), drain=drain,
                      mode_states=_counts(contract, [known[0] for known in history]),
                      transitions_taken=tuple(sorted(taken)))


def _lift(mode: str, state: CompletionState) -> ModeCompletionState:
    return ModeCompletionState(mode, state.phase, state.maintenance, state.operations)


def check_completion(contract: ModeContract) -> ModeCompletionResult:
    """Run `phase_completion`'s cycle and drain over the product under the switch rule.

    Quiescent drain is taken at every reachable boundary of every mode, with
    arrivals stopped and the current mode's refresh continuing; no transition is
    taken during a drain. A closed result's bound is the maximum over every mode's
    boundaries. Base steps and drains are reused unchanged.
    """
    tables = _tables(contract)
    switches = _switches(contract)
    banks = next(iter(tables.values()))[0].banks
    pending: deque[tuple[str, CompletionState]] = deque()
    history: dict[tuple[str, CompletionState], tuple[tuple[Batch, ...], tuple[Step, ...]]] = {}
    for mode in contract.initial:
        initial = (mode, CompletionState(0, (0,) * banks, ()))
        history[initial] = ((), ())
        pending.append(initial)
    taken: set[int] = set()
    maximum = 0
    while pending:
        mode, state = pending.popleft()
        table, refresh, paths = tables[mode]
        prefix, steps = history[(mode, state)]
        duration, drain_failure, drain_reason = _drain(table, refresh, paths, state)
        if drain_failure is not None:
            return ModeCompletionResult(None, len(history), prefix, _lift(mode, state),
                                        f"drain-{drain_reason}", drain_status="blocked",
                                        drain_failure=_lift(mode, drain_failure),
                                        drain_cycles=duration, trace_modes=steps,
                                        mode_states=_counts(contract, [known for known, _ in history]),
                                        transitions_taken=tuple(sorted(taken)))
        maximum = max(maximum, duration)
        for batch in table.arrivals[state.phase]:
            successor, reason = _step(table, refresh, paths, state, batch, ordering=True)
            if successor is None:
                return ModeCompletionResult(
                    False if reason == "completion-order-inverted" else None, len(history),
                    (*prefix, batch), _lift(mode, state), reason,
                    trace_modes=(*steps, (mode, state.phase)),
                    mode_states=_counts(contract, [known for known, _ in history]),
                    transitions_taken=tuple(sorted(taken)))
            targets = [(mode, successor)]
            for index, target, to_phase in switches.get((mode, state.phase), ()):
                taken.add(index)
                targets.append((target, CompletionState(to_phase, successor.maintenance,
                                                        successor.operations)))
            for entry in targets:
                if entry not in history:
                    history[entry] = ((*prefix, batch), (*steps, (mode, state.phase)))
                    pending.append(entry)
    return ModeCompletionResult(True, len(history), quiescent_drain=maximum,
                                drain_status="finite",
                                mode_states=_counts(contract, [known for known, _ in history]),
                                transitions_taken=tuple(sorted(taken)))


def _table(node: Json, mode: str, resources: phase_schedule.Resources,
           bank_ids: dict[str, int], hart_ids: dict[str, int],
           excesses: list[ModeInjectionExcess]) -> Contract:
    """One mode's phase array, read exactly as the v1 reader reads `phases`."""
    grants: list[int] = []
    arrivals: list[tuple[Batch, ...]] = []
    refresh: list[Batch] = []
    for phase, member in enumerate(_rows(node, f"mode {mode} phases", nonempty=True)):
        row = _object(member, {"grant", "alternatives", "refresh"}, "phase")
        grant = _integer(row["grant"], "phase grant")
        alternatives = _alternatives(row["alternatives"], resources, bank_ids, hart_ids)
        grants.append(grant)
        arrivals.append(alternatives)
        refresh.append(_refresh(row["refresh"], resources, bank_ids))
        excesses.extend(ModeInjectionExcess(mode, phase, index, len(batch), grant)
                        for index, batch in enumerate(alternatives) if len(batch) > grant)
    return Contract(tuple(grants), tuple(arrivals), len(resources.banks), tuple(refresh),
                    tuple(bank.path_cycles for bank in resources.banks))


def _transition(node: Json) -> Transition:
    row = _object(node, {"from", "from_phase", "to", "to_phase"}, "transition")
    return Transition(_name(row["from"], "transition from"),
                      _integer(row["from_phase"], "transition from_phase"),
                      _name(row["to"], "transition to"),
                      _integer(row["to_phase"], "transition to_phase"))


def extract(schedule_raw: bytes, resources_raw: bytes) -> ModeExtraction:
    """Read a v2 declaration: every mode's table, the initial modes and the transitions."""
    data = _object(_decode(schedule_raw), set(FIELDS), "schedule")
    if data["schema"] != SCHEMA:
        raise ValueError(f"only {SCHEMA} is read as a mode declaration")
    name = _name(data["name"], "schedule name")
    expected = data["resources_sha256"]
    if not isinstance(expected, str) or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        raise ValueError("resources_sha256 must be a full lowercase SHA-256 digest")
    resources_sha256 = hashlib.sha256(resources_raw).hexdigest()
    if expected != resources_sha256:
        raise ValueError("resources_sha256 does not match the supplied resource bytes")
    resources = _resources(resources_raw)
    bank_ids = {bank.name: index for index, bank in enumerate(resources.banks)}
    hart_ids = {hart: index for index, hart in enumerate(resources.harts)}
    declared = data["modes"]
    if not isinstance(declared, dict) or not declared:
        raise ValueError("modes must be a nonempty object mapping mode names to tables")
    excesses: list[ModeInjectionExcess] = []
    modes: dict[str, Contract] = {}
    for mode, member in declared.items():
        _name(mode, "mode name")
        row = _object(member, {"phases"}, f"mode {mode}")
        modes[mode] = _table(row["phases"], mode, resources, bank_ids, hart_ids, excesses)
    initial = tuple(_name(value, "initial mode")
                    for value in _rows(data["initial"], "initial", nonempty=True))
    if len(set(initial)) != len(initial):
        raise ValueError("duplicate initial mode")
    transitions = tuple(_transition(member) for member in _rows(data["transitions"], "transitions"))
    contract = ModeContract(initial, modes, transitions)
    _tables(contract)
    return ModeExtraction(name, hashlib.sha256(schedule_raw).hexdigest(), resources_sha256,
                          tuple(bank_ids), tuple(hart_ids), resources.operations,
                          tuple(excesses), contract)


def read(schedule_raw: bytes, resources_raw: bytes) -> Extraction | ModeExtraction:
    """Read `schema` before any field-set check and dispatch on it.

    A v1 declaration goes through its existing reader unchanged; a v2 declaration
    through `extract`. An absent or unsupported schema is malformed input.
    """
    data = _decode(schedule_raw)
    if not isinstance(data, dict) or "schema" not in data:
        raise ValueError("schedule declares no schema")
    schema = data["schema"]
    if schema == "phase-schedule-v1":
        return phase_schedule.extract(schedule_raw, resources_raw)
    if schema == SCHEMA:
        return extract(schedule_raw, resources_raw)
    raise ValueError(f"unsupported schedule schema: {json.dumps(schema)}")


def single_mode(contract: ModeContract) -> Contract | None:
    """The one table of a declaration with one mode and no transitions, else None."""
    if len(contract.modes) == 1 and not contract.transitions:
        (table,) = contract.modes.values()
        return table
    return None


def mode_contract_json(contract: ModeContract) -> dict[str, Json]:
    """The mode contract: exactly `initial`, `modes` in the v1 shape and `transitions`."""
    return {"initial": list(contract.initial),
            "modes": {name: cast("Json", asdict(table)) for name, table in contract.modes.items()},
            "transitions": [cast("Json", transition.to_json())
                            for transition in contract.transitions]}


def mode_contract_bytes(contract: ModeContract) -> bytes:
    """Sorted, compact JSON with one final LF, which `phase-service --contract` refuses."""
    return (json.dumps(mode_contract_json(contract), sort_keys=True, separators=(",", ":"))
            + "\n").encode("utf-8")


def emitted_json(contract: ModeContract) -> dict[str, Json]:
    """What `--output-contract` writes: the v1 table for a single mode, else the mode contract."""
    table = single_mode(contract)
    if table is not None:
        return cast("dict[str, Json]", asdict(table))
    return mode_contract_json(contract)


def emitted_bytes(contract: ModeContract) -> bytes:
    table = single_mode(contract)
    if table is not None:
        return contract_bytes(table)
    return mode_contract_bytes(contract)


def receipt(extraction: ModeExtraction) -> dict[str, Json]:
    """The extraction's receipt fields, in the v1 report's names with the mode added."""
    return {"name": extraction.name, "schedule_sha256": extraction.schedule_sha256,
            "resources_sha256": extraction.resources_sha256,
            "bank_names": list(extraction.bank_names), "hart_names": list(extraction.hart_names),
            "operation_names": list(extraction.operation_names),
            "injection_excesses": [cast("Json", asdict(excess))
                                   for excess in extraction.injection_excesses],
            "contract": emitted_json(extraction.contract)}
