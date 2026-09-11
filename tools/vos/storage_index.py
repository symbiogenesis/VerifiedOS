# SPDX-License-Identifier: Apache-2.0
"""Q22f: a finite index cost/semantics experiment, not a filesystem or WCET model."""

from collections import Counter
from dataclasses import asdict, dataclass
from itertools import product
from typing import Literal

BLOCK_BYTES = 4096
ENTRY_BYTES = 64
LEAVES = 16
KEYS_PER_LEAF = 48
KEYS = LEAVES * KEYS_PER_LEAF
BUFFER = 48
UPDATES = 192
BUDGETS = (4, 5, 6)
type Arm = Literal["cow-bplus", "buffered"]
type Message = tuple[int, int]
type Image = tuple[int, ...]
type Medium = tuple[Image, ...]
type Record = tuple[int, Image]


@dataclass(frozen=True)
class State:
    values: tuple[int, ...] = (0,) * KEYS
    messages: tuple[Message, ...] = ()

    def lookup(self, key: int) -> int:
        for message_key, value in reversed(self.messages):
            if message_key == key:
                return value
        return self.values[key]

    def medium(self) -> Medium:
        root = tuple(part for message in self.messages for part in message)
        return (root, *(self.values[start:start + KEYS_PER_LEAF]
                        for start in range(0, KEYS, KEYS_PER_LEAF)))


@dataclass(frozen=True)
class Transition:
    state: State
    changed: tuple[int, ...]
    pending_peak: int
    flush_scans: int

    @property
    def writes(self) -> int:
        return 2 * len(self.changed) + 2 if self.changed else 0


def advance(state: State, messages: tuple[Message, ...], arm: Arm,
            *, drain: bool = False) -> Transition:
    if arm not in ("cow-bplus", "buffered"):
        raise ValueError("unknown index arm")
    if len(messages) > 16 or any(not 0 <= key < KEYS for key, _ in messages):
        raise ValueError("outside the declared transaction/key domain")
    values = list(state.values)
    pending = list(state.messages)
    changed: set[int] = set()
    scans = 0
    if arm == "cow-bplus":
        if pending:
            raise ValueError("plain index cannot contain pending messages")
        for key, value in messages:
            values[key] = value
            changed.add(1 + key // KEYS_PER_LEAF)
    else:
        pending.extend(messages)
    peak = len(pending)
    while len(pending) > BUFFER or (drain and pending):
        scans += len(pending)
        counts = Counter(key // KEYS_PER_LEAF for key, _ in pending)
        selected = min(counts, key=lambda child: (-counts[child], child))
        keep: list[Message] = []
        for key, value in pending:
            if key // KEYS_PER_LEAF == selected:
                values[key] = value
            else:
                keep.append((key, value))
        scans += len(pending)
        pending = keep
        changed.add(1 + selected)
    if messages or changed:
        changed.add(0)
    return Transition(State(tuple(values), tuple(pending)), tuple(sorted(changed)),
                      peak, scans)


def redo(before: State, transition: Transition) -> tuple[Record, ...]:
    after = transition.state.medium()
    return tuple((slot, after[slot]) for slot in transition.changed)


def recover(previous: Medium, home: Medium, visible: tuple[Record, ...],
            seal: tuple[Record, ...] | None) -> Medium:
    """Ideal authenticated prefix redo; the seal is a symbolic commit, not crypto.

    Slot numbers name fresh candidate blocks within one generation. `previous`
    remains a distinct retained generation, even if logical slots have equal IDs.
    An intact marker binds the entire ordered redo; absent marker rolls back.
    """
    if seal is None:
        return previous
    if visible != seal or not visible:
        raise ValueError("committed payload does not authenticate")
    slots = [slot for slot, _ in visible]
    if len(set(slots)) != len(slots) or any(not 0 <= slot < len(home) for slot in slots):
        raise ValueError("invalid redo target")
    result = list(home)
    for slot, payload in visible:
        result[slot] = payload
    return tuple(result)


def materialize(medium: Medium) -> tuple[int, ...]:
    """Read serialized node images by ordered flat-map replay, without lookup()."""
    values = [value for leaf in medium[1:] for value in leaf]
    root = medium[0]
    for offset in range(0, len(root), 2):
        values[root[offset]] = root[offset + 1]
    return tuple(values)


def crash_checks(before: State, transition: Transition,
                 expected_map: tuple[int, ...]) -> int:
    """Every block-write prefix, plus interrupted/repeated replay and corruption."""
    records = redo(before, transition)
    if not records:
        return 0
    previous = before.medium()
    expected = transition.state.medium()
    old_map = materialize(previous)
    p = len(records)
    checked = 0
    # p redo writes, marker, p home writes, checkpoint; all durable prefixes.
    for cut in range(2 * p + 3):
        visible = records[:min(cut, p)]
        sealed = records if cut >= p + 1 else None
        home = list(previous)
        for slot, payload in records[:max(0, cut - p - 1)]:
            home[slot] = payload
        recovered = recover(previous, tuple(home), visible, sealed)
        wanted = expected if sealed is not None else previous
        if recovered != wanted:
            raise AssertionError("crash prefix changes committed node images")
        if materialize(recovered) != (expected_map if sealed is not None else old_map):
            raise AssertionError("recovery differs from independently replayed committed map")
        # Every interruption within replay keeps the same retained journal.
        if sealed is not None:
            for replay_cut in range(p + 1):
                replay_home = list(home)
                for slot, payload in records[:replay_cut]:
                    replay_home[slot] = payload
                if recover(previous, tuple(replay_home), visible, sealed) != wanted:
                    raise AssertionError("interrupted recovery changes its answer")
                checked += 1
        checked += 1
    for index, (slot, payload) in enumerate(records):
        for replacement in ((slot, (*payload, -1)), ((slot + 1) % len(previous), payload)):
            corrupt = (*records[:index], replacement, *records[index + 1:])
            try:
                recover(previous, previous, corrupt, records)
            except ValueError:
                checked += 1
            else:
                raise AssertionError("committed torn/misdirected record is accepted")
        try:
            recover(previous, previous, records[:index], records)
        except ValueError:
            checked += 1
        else:
            raise AssertionError("committed truncated log rolls back silently")
    return checked


@dataclass(frozen=True)
class Measurement:
    workload: str
    width: int
    arm: Arm
    updates: int
    block_writes: int
    barriers: int
    max_transaction_writes: int
    drain_writes: int
    max_transaction_reads: int
    max_pending_messages: int
    max_flush_message_scans: int
    max_query_message_checks: int

    @property
    def byte_amplification(self) -> float:
        return self.block_writes * BLOCK_BYTES / (self.updates * ENTRY_BYTES)

    def accepted(self, program_budget: int) -> bool:
        return (self.block_writes <= program_budget * self.updates
                and self.max_transaction_writes <= 36
                and self.max_transaction_reads <= 17
                and self.max_pending_messages <= BUFFER + 16
                and self.max_query_message_checks <= BUFFER
                and self.max_flush_message_scans <= 2 * LEAVES * (BUFFER + 16))


def measure(name: str, keys: tuple[int, ...], width: int, arm: Arm) -> Measurement:
    if not keys or len(keys) % width or width not in (1, 4, 16):
        raise ValueError("outside declared workload/transaction widths")
    state = State()
    snapshot = state.medium()
    # This oracle updates a flat map directly and never reads index messages.
    reference = [0] * KEYS
    writes = barriers = peak_writes = peak_reads = peak_pending = peak_scans = peak_query = 0
    for start in range(0, len(keys), width):
        messages = tuple((key, start + i + 1) for i, key in enumerate(keys[start:start + width]))
        transition = advance(state, messages, arm)
        for key, value in messages:
            reference[key] = value
        state = transition.state
        if tuple(state.lookup(key) for key in range(KEYS)) != tuple(reference):
            raise AssertionError("index lookup disagrees with direct committed-map replay")
        writes += transition.writes
        barriers += 3
        peak_writes = max(peak_writes, transition.writes)
        peak_reads = max(peak_reads, len(transition.changed))
        peak_pending = max(peak_pending, transition.pending_peak)
        peak_scans = max(peak_scans, transition.flush_scans)
        peak_query = max(peak_query, len(state.messages))
    drained = advance(state, (), arm, drain=True)
    if drained.state.values != tuple(reference) or drained.state.messages:
        raise AssertionError("quiescent drain changes committed map")
    if snapshot != State().medium():
        raise AssertionError("retained snapshot changed")
    return Measurement(name, width, arm, len(keys), writes + drained.writes,
                       barriers + (3 if drained.changed else 0),
                       max(peak_writes, drained.writes), drained.writes,
                       max(peak_reads, len(drained.changed)),
                       max(peak_pending, drained.pending_peak),
                       max(peak_scans, drained.flush_scans), peak_query)


def workloads() -> tuple[tuple[str, tuple[int, ...]], ...]:
    named = [("duplicate-hot-key", (0,) * UPDATES),
             ("hot-leaf", tuple(i % KEYS_PER_LEAF for i in range(UPDATES))),
             ("striped-leaves", tuple((i % LEAVES) * KEYS_PER_LEAF + i // LEAVES
                                      for i in range(UPDATES)))]
    named.extend((f"affine-{stride}-{offset}",
                  tuple((i * stride + offset) % KEYS for i in range(UPDATES)))
                 for stride, offset in product((1, 17, 47, 193), (0, 23)))
    return tuple(named)


def experiment() -> dict[str, object]:
    results = [measure(name, keys, width, arm)
               for name, keys in workloads() for width in (1, 4, 16)
               for arm in ("cow-bplus", "buffered")]
    # Exhaust all streams through six operations over duplicate/other-leaf keys.
    streams = 0
    crash_cases = 0
    for length in range(1, 7):
        for keys in product((0, 1, KEYS_PER_LEAF), repeat=length):
            for arm in ("cow-bplus", "buffered"):
                measure("exhaustive-small", keys, 1, arm)
            streams += 1
    # Every possible redo length, including maximum all-child final drain.
    for leaves in range(1, LEAVES + 1):
        before = State(messages=tuple((child * KEYS_PER_LEAF, child + 1)
                                      for child in range(leaves)))
        transition = advance(before, (), "buffered", drain=True)
        expected = [0] * KEYS
        for child in range(leaves):
            expected[child * KEYS_PER_LEAF] = child + 1
        if transition.state.values != tuple(expected):
            raise AssertionError("drain violates independently constructed map")
        crash_cases += crash_checks(before, transition, tuple(expected))
    crash_cases += crash_checks(State(), advance(State(), ((0, 1),), "buffered"),
                                (1, *((0,) * (KEYS - 1))))
    full = State(messages=tuple((i * KEYS_PER_LEAF, i + 1)
                               for i in range(LEAVES) for _ in range(3)))
    overflow = advance(full, ((0, 999),), "buffered")
    if overflow.state.lookup(0) != 999 or len(overflow.state.messages) > BUFFER:
        raise AssertionError("full-buffer duplicate precedence fails")
    expected_full = [0] * KEYS
    for child in range(LEAVES):
        expected_full[child * KEYS_PER_LEAF] = child + 1
    expected_full[0] = 999
    crash_cases += crash_checks(full, overflow, tuple(expected_full))
    # Static packing/reservation checks use actual declared dimensions.
    nodes = LEAVES + 1
    device_blocks = 3 * nodes + (nodes + 1) + 2 + 1
    ram_blocks = 2 * nodes + 2
    packed_root = 128 + LEAVES * 32 + BUFFER * ENTRY_BYTES
    if device_blocks > 72 or ram_blocks > 36 or packed_root > BLOCK_BYTES:
        raise AssertionError("declared capacity/memory envelope does not fit")
    rows = [{**asdict(row), "byte_amplification": row.byte_amplification,
             "accepted_program_budgets": [budget for budget in BUDGETS if row.accepted(budget)]}
            for row in results]
    dispositions: list[dict[str, object]] = []
    for budget in BUDGETS:
        counts: Counter[str] = Counter()
        for plain, buffered in zip(results[::2], results[1::2], strict=True):
            accepted = (plain.accepted(budget), buffered.accepted(budget))
            counts[{(True, True): "both", (True, False): "bplus-only",
                    (False, True): "buffered-only", (False, False): "reject-both"}[accepted]] += 1
        dispositions.append({"program_budget": budget, "cases": dict(sorted(counts.items()))})
    return {"scope": "synthetic-fixed-height-index-comparison", "passed": True,
            "production_adoption": "open", "disposition": "retain-incumbent-pending-target-composition",
            "parameters": {"block_bytes": BLOCK_BYTES, "entry_bytes": ENTRY_BYTES,
                           "leaves": LEAVES, "keys_per_leaf": KEYS_PER_LEAF,
                           "buffer_messages": BUFFER, "updates_per_workload": UPDATES,
                           "transaction_widths": [1, 4, 16], "program_budgets": list(BUDGETS),
                           "recovery_policy": "authenticated-prefix-redo",
                           "transaction_barriers": 3,
                           "nand_programs_per_block_write": "conditional-one; target-unknown"},
            "device_blocks_reserved": device_blocks, "ram_bytes_reserved": ram_blocks * BLOCK_BYTES,
            "useful_key_value_bytes": KEYS * ENTRY_BYTES,
            "root_packed_bytes": packed_root, "buffer_reserved_bytes": BUFFER * ENTRY_BYTES,
            "max_recovery_reads": nodes + 1 + 2, "max_recovery_writes": nodes + 1,
            "recovery_barriers": 2, "exhaustive_streams": streams, "crash_checks": crash_cases,
            "budget_dispositions": dispositions, "measurements": rows}
