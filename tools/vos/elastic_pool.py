# SPDX-License-Identifier: Apache-2.0
"""Finite pool/heap reference and independent observable-history qualification.

The size-class plan is admitted once. Allocation does no bounds rounding. Holder
maps and barriers use the existing revocation reference. This is a host reference,
not a native pool service or a claim of source-to-binary correspondence.
"""

from dataclasses import dataclass, field
from itertools import product
from typing import Literal

from vos import revocation as rev
from vos.memplan import representable_granule

type Event = tuple[str, tuple[int, ...]]
type Phase = Literal["free", "live", "pending", "barrier", "sweeping"]


class PoolError(ValueError):
    """A request cannot be accepted within the declared pool."""


@dataclass(frozen=True)
class SizeClass:
    length: int
    alignment: int

    def exact(self) -> bool:
        # The shared plan owns compressed-bound arithmetic. This call runs at
        # composition admission, never in allocate().
        granule = representable_granule(self.length)
        return (self.length > 0 and self.alignment > 0
                and self.length % granule == 0 and self.alignment % granule == 0)


@dataclass(frozen=True)
class Plan:
    island: int
    memory_class: int
    base: int
    span: int
    classes: tuple[SizeClass, ...]
    slots: tuple[tuple[int, int], ...]  # (base, class index), fixed by composition
    quarantine_allowance: int

    def validate(self) -> None:
        if (min(self.island, self.memory_class, self.base) < 0 or self.span <= 0
                or not self.classes or not self.slots
                or self.quarantine_allowance < sum(self.classes[c].length
                                                  for _, c in self.slots
                                                  if 0 <= c < len(self.classes))):
            raise PoolError("pool shape or quarantine allowance")
        if not all(c.exact() for c in self.classes):
            raise PoolError("class is not exactly representable")
        extents: list[tuple[int, int]] = []
        for base, cls in self.slots:
            if not 0 <= cls < len(self.classes):
                raise PoolError("class is outside the composition table")
            kind = self.classes[cls]
            top = base + kind.length
            if base % kind.alignment or not self.base <= base < top <= self.base + self.span:
                raise PoolError("slot is unaligned or outside its arena")
            if any(base < hi and lo < top for lo, hi in extents):
                raise PoolError("composition slots overlap")
            extents.append((base, top))


@dataclass(frozen=True)
class Grant:
    holder: int
    slot: int
    base: int
    length: int
    serial: int
    issuer: object = field(repr=False)


@dataclass
class Slot:
    phase: Phase = "free"
    grant: Grant | None = None
    composition: rev.Composition | None = None
    retirement: rev.State | None = None
    child: Pool | None = None


@dataclass
class Pool:
    plan: Plan
    slots: list[Slot] = field(init=False)
    history: list[Event] = field(default_factory=list, init=False)
    memory: dict[int, int] = field(default_factory=dict, init=False)
    sweep_members: tuple[int, ...] | None = field(default=None, init=False)
    serial: int = field(default=0, init=False)
    epoch: int = field(default=0, init=False)
    issuer: object = field(default_factory=object, init=False, repr=False)
    parent: tuple[Pool, Grant] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.plan.validate()
        self.slots = [Slot() for _ in self.plan.slots]

    def allocate(self, holder: int, cls: int, launch_island: int) -> Grant:
        self.check_parent()
        if launch_island != self.plan.island:
            raise PoolError("foreign launch island")
        if holder < 0 or not 0 <= cls < len(self.plan.classes):
            raise PoolError("holder or class outside composition")
        for index, ((base, kind), slot) in enumerate(zip(self.plan.slots, self.slots, strict=True)):
            if kind == cls and slot.phase == "free":
                if self.serial == rev.MAX_EPOCH:
                    raise PoolError("allocation identity exhausted")
                self.serial += 1
                length = self.plan.classes[cls].length
                grant = Grant(holder, index, base, length, self.serial, self.issuer)
                for address in range(base, base + length):
                    self.memory[address] = 0
                self.history.extend([("Zero", (base, length)),
                                     ("Grant", (holder, cls, base, base, length))])
                slot.phase, slot.grant = "live", grant
                return grant
        raise PoolError("chunk class exhausted")

    def live(self, grant: Grant) -> Slot:
        self.check_parent()
        if grant.issuer is not self.issuer:
            raise PoolError("foreign grant issuer")
        if not 0 <= grant.slot < len(self.slots):
            raise PoolError("unknown grant")
        slot = self.slots[grant.slot]
        if slot.phase != "live" or slot.grant != grant:
            raise PoolError("stale or foreign grant")
        return slot

    def check_parent(self) -> None:
        if self.parent is not None:
            parent, grant = self.parent
            parent.live(grant)

    def write(self, grant: Grant, offset: int, value: int) -> None:
        if self.live(grant).child is not None:
            raise PoolError("chunk is owned by its heap")
        if not 0 <= offset < grant.length or not 0 <= value < 256:
            raise PoolError("write outside allocation or byte range")
        self.memory[grant.base + offset] = value
        self.history.append(("Write", (grant.base + offset, value)))

    def release(self, grant: Grant) -> None:
        slot = self.live(grant)
        cls = self.plan.slots[grant.slot][1]
        # Local abstract holder indices are used by the existing revocation
        # reference; the enclosing pool's island is checked at allocation.
        cap = rev.Capability(grant.base, grant.base + grant.length)
        holders = (rev.Holder("register", "live", 0, cap),
                   rev.Holder("saved", "saved", 0, cap),
                   rev.Holder("outside-copy", "memory", 0, cap))
        comp = rev.Composition(frozenset(h.name for h in holders),
                               frozenset({"saved", "outside-copy"}),
                               frozenset((0, address // rev.GRANULE)
                                         for address in range(grant.base,
                                                              grant.base + grant.length)),
                               frozenset({0}), frozenset())
        state = rev.State(holders, loans=frozenset(), pending_proxies=frozenset(),
                          accepted_transfers=0, device_issue_closed=True, epoch=self.epoch)
        published = rev.publish(comp, state)
        slot.phase, slot.composition = "pending", comp
        slot.retirement, self.epoch = published, published.epoch
        self.history.append(("Release", (grant.base, cls)))

    def clear_registers(self, index: int) -> None:
        self.check_parent()
        if not 0 <= index < len(self.slots):
            raise PoolError("slot index outside pool")
        slot = self.slots[index]
        if slot.phase != "pending" or slot.retirement is None:
            raise PoolError("no pending retirement")
        slot.retirement = rev.clear_core(slot.retirement, 0)

    def barrier(self) -> None:
        self.check_parent()
        pending = [slot for slot in self.slots if slot.phase == "pending"]
        if not pending:
            raise PoolError("no pending retirement")
        completed: list[rev.State] = []
        for slot in pending:
            if slot.composition is None or slot.retirement is None:
                raise PoolError("missing holder inventory")
            completed.append(rev.complete(slot.composition, slot.retirement))
        # Transactional: a retained register in any chunk changes no phases.
        for slot, state in zip(pending, completed, strict=True):
            slot.phase, slot.retirement = "barrier", state
        self.history.append(("BarrierDone", ()))

    def sweep_begin(self) -> None:
        self.check_parent()
        if self.sweep_members is not None:
            raise PoolError("sweep already active")
        members = tuple(i for i, s in enumerate(self.slots) if s.phase == "barrier")
        if not members:
            raise PoolError("no post-barrier quarantine")
        for index in members:
            slot = self.slots[index]
            if slot.composition is None or slot.retirement is None:
                raise PoolError("missing holder inventory")
            slot.retirement = rev.start_sweep(slot.composition, slot.retirement)
            slot.phase = "sweeping"
        self.sweep_members = members
        self.history.append(("SweepBegin", ()))

    def sweep_end(self) -> None:
        self.check_parent()
        if self.sweep_members is None:
            raise PoolError("no sweep active")
        for index in self.sweep_members:
            slot = self.slots[index]
            if slot.composition is None or slot.retirement is None:
                raise PoolError("missing holder inventory")
            state = slot.retirement
            for name in sorted(slot.composition.swept):
                state = rev.sweep(slot.composition, state, name)
            slot.retirement = rev.reuse(slot.composition, state)
            slot.phase, slot.grant, slot.child = "free", None, None
        self.sweep_members = None
        self.history.append(("SweepEnd", ()))

    def heap(self, grant: Grant, classes: tuple[SizeClass, ...],
             slots: tuple[tuple[int, int], ...]) -> Pool:
        slot = self.live(grant)
        if slot.child is not None:
            raise PoolError("chunk already has a heap owner")
        child = Pool(Plan(self.plan.island, self.plan.memory_class, grant.base,
                          grant.length, classes, slots, grant.length))
        child.parent = (self, grant)
        child.memory = self.memory
        slot.child = child
        return child


def history_errors(plan: Plan, history: list[Event]) -> frozenset[str]:
    """Independent history observer matching ElasticDomain's four predicates."""
    errors: set[str] = set()
    live: dict[int, int] = {}
    releases: list[tuple[int, int, int]] = []
    memory: dict[int, int] = {}
    barriers: list[int] = []
    passes: list[tuple[int, int]] = []
    started: int | None = None
    for position, (event, args) in enumerate(history):
        if event == "Grant":
            _, cls, base, cap_base, cap_length = args
            if not 0 <= cls < len(plan.classes):
                errors.add("bounds")
                continue
            kind = plan.classes[cls]
            top = base + kind.length
            if any(base < old + length and old < top for old, length in live.items()):
                errors.add("overlap")
            if (not kind.exact() or base % kind.alignment or cap_base != base
                    or cap_length != kind.length or base < plan.base
                    or top > plan.base + plan.span):
                errors.add("bounds")
            if any(memory.get(address, 19) != 0 for address in range(base, top)):
                errors.add("zero")
            for old, length, released in releases:
                if base < old + length and old < top and not any(
                        released < barrier < start < end < position
                        for barrier in barriers for start, end in passes):
                    errors.add("reuse")
            live[base] = kind.length
        elif event == "Release":
            base, cls = args
            live.pop(base, None)
            releases.append((base, plan.classes[cls].length, position))
        elif event == "Write":
            memory[args[0]] = args[1]
        elif event == "Zero":
            for address in range(args[0], args[0] + args[1]):
                memory[address] = 0
        elif event == "BarrierDone":
            barriers.append(position)
        elif event == "SweepBegin":
            started = position
        elif event == "SweepEnd" and started is not None:
            passes.append((started, position))
            started = None
    return frozenset(errors)


def fixture() -> Pool:
    return Pool(Plan(0, 0, 64, 64, (SizeClass(16, 16), SizeClass(32, 32)),
                     ((64, 0), (80, 0), (96, 1)), 64))


@dataclass
class DomainPools:
    """One composition-owned pool per occupied island and memory class."""
    pools: dict[tuple[int, int], Pool]
    launch_islands: dict[int, int]

    def __post_init__(self) -> None:
        if not self.pools or not self.launch_islands:
            raise PoolError("empty domain composition")
        islands = set(self.launch_islands.values())
        classes = {cls for _, cls in self.pools}
        if set(self.pools) != {(island, cls) for island in islands for cls in classes}:
            raise PoolError("missing per-island memory-class pool")
        for key, pool in self.pools.items():
            if key != (pool.plan.island, pool.plan.memory_class):
                raise PoolError("pool bound to a different island or class")

    def allocate(self, holder: int, memory_class: int, cls: int) -> Grant:
        if holder not in self.launch_islands:
            raise PoolError("member has no placed launch core")
        island = self.launch_islands[holder]
        if (island, memory_class) not in self.pools:
            raise PoolError("memory class outside composition")
        return self.pools[island, memory_class].allocate(holder, cls, island)


def generated_histories(depth: int = 4) -> list[list[Event]]:
    """Enumerate every bounded command word, retaining deterministic refusals."""
    if not 0 <= depth <= 5:
        raise PoolError("campaign depth outside finite budget")
    histories: list[list[Event]] = []
    for commands in product(range(7), repeat=depth):
        pool = fixture()
        for command in commands:
            try:
                if command < 2:
                    pool.allocate(1 + command, command, 0)
                elif command == 2:
                    grant = next(s.grant for s in pool.slots if s.phase == "live")
                    if grant is not None:
                        pool.write(grant, 0, 7)
                        pool.release(grant)
                elif command == 3:
                    for i, slot in enumerate(pool.slots):
                        if slot.phase == "pending":
                            pool.clear_registers(i)
                elif command == 4:
                    pool.barrier()
                elif command == 5:
                    pool.sweep_begin()
                else:
                    pool.sweep_end()
            except (PoolError, rev.RevocationError, StopIteration):
                pass
        histories.append(pool.history)
    return histories
