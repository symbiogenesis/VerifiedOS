# SPDX-License-Identifier: Apache-2.0
"""Finite revocation qualification, with architectural loads and protocol barriers.

This is a host experiment, not an interpreter for Sail or a runtime implementation.
`retired` and `loan` are observer/ownership annotations, never capability bits. The
architectural load and dereference functions do not consult those annotations.
"""

from contextlib import suppress
from dataclasses import dataclass, replace
from hashlib import sha256
from itertools import permutations
from pathlib import Path
from typing import Literal

GRANULE = 8
MAX_EPOCH = (1 << 64) - 1
type Place = Literal["live", "saved", "memory"]
type Bit = tuple[int, int]


@dataclass(frozen=True)
class Capability:
    base: int
    top: int
    island: int = 0
    tag: bool = True
    retired: bool = True
    loan: str = ""


def dereference(cap: Capability, address: int) -> bool:
    """Resident authority is not revalidated against the bitmap at dereference."""
    return cap.tag and cap.base <= address < cap.top


def load(cap: Capability, bits: frozenset[Bit], loading_island: int = 0) -> Capability:
    # island is an abstract address-region annotation, not a capability field.
    # A foreign address is outside this loader's covered union and stays live.
    revoked = (cap.island == loading_island
               and (loading_island, cap.base // GRANULE) in bits)
    return replace(cap, tag=cap.tag and not revoked)


@dataclass(frozen=True)
class Holder:
    name: str
    place: Place
    core: int
    cap: Capability
    filtered_restore: bool = True


@dataclass(frozen=True)
class Composition:
    """Finite exhaustive holder map and affected base set, supplied by admission.

    The map includes trusted-stack, PCC/MEPCC, grant storage and outside-interval
    copies. Loan names denote the complete no-capture ownership footprint. The
    experiment checks that supplied states stay inside this map, not its relation
    to a compiled image. M4.4/R2 must prove that relation.
    """
    holders: frozenset[str]
    swept: frozenset[str]
    targets: frozenset[Bit]
    cores: frozenset[int]
    proxies: frozenset[int]


@dataclass(frozen=True)
class State:
    holders: tuple[Holder, ...]
    bits: frozenset[Bit] = frozenset()
    loans: frozenset[str] = frozenset({"call"})
    pending_proxies: frozenset[int] = frozenset({1})
    accepted_transfers: int = 1
    device_issue_closed: bool = False
    invocations_closed: bool = False
    epoch: int = 0
    clock: int = 0
    barrier: int | None = None
    sweep_started: int | None = None
    swept: frozenset[str] = frozenset()
    failed: bool = False


class RevocationError(ValueError):
    """An attempted transition lacks its required evidence."""


def map_errors(comp: Composition, state: State) -> list[str]:
    names = [h.name for h in state.holders]
    errors: list[str] = []
    if len(set(names)) != len(names) or frozenset(names) != comp.holders:
        errors.append("holder-map")
    storage = frozenset(h.name for h in state.holders if h.place != "live")
    if storage != comp.swept:
        errors.append("sweep-map")
    if any(h.core not in comp.cores or h.cap.base >= h.cap.top
           or h.cap.base < 0 or h.cap.island < 0 for h in state.holders):
        errors.append("holder-shape")
    if any(h.cap.island != h.core for h in state.holders):
        errors.append("loading-island")
    if not comp.targets or 0 not in comp.cores or comp.proxies != comp.cores - {0}:
        errors.append("composition-shape")
    if not state.pending_proxies <= comp.proxies:
        errors.append("proxy-map")
    return errors


def exposed(state: State, core: int | None = None) -> tuple[str, ...]:
    """Independent authority observer: try a dereference or a restore/load.

    A nonempty retired capability is conservatively considered usable: this
    forgets seals and permissions, so cannot gain a pass from those abstractions.
    """
    found: list[str] = []
    for holder in state.holders:
        if core is not None and holder.core != core:
            continue
        cap = holder.cap
        if holder.place == "memory" or (holder.place == "saved"
                                        and holder.filtered_restore):
            cap = load(cap, state.bits, holder.core)
        if cap.retired and dereference(cap, cap.base):
            found.append(holder.name)
    return tuple(found)


def completion_errors(comp: Composition, state: State) -> list[str]:
    errors = map_errors(comp, state)
    if state.failed:
        errors.append("acknowledgement-failure")
    if not comp.targets <= state.bits:
        errors.append("publication")
    if not state.invocations_closed:
        errors.append("new-invocation")
    errors.extend("authority:" + name for name in exposed(state))
    if state.loans:
        errors.append("outstanding-loan")
    if state.pending_proxies:
        errors.append("remote-acknowledgement")
    if state.accepted_transfers or not state.device_issue_closed:
        errors.append("device-completion")
    return errors


def advance(state: State) -> State:
    # Kept local to make ordering explicit: every accepted event occupies a tick.
    return replace(state, clock=state.clock + 1)


def publish(comp: Composition, state: State) -> State:
    if not 0 <= state.epoch < MAX_EPOCH or state.barrier is not None or state.failed:
        raise RevocationError("epoch exhaustion or protocol already terminal")
    return replace(advance(state), bits=state.bits | comp.targets,
                   invocations_closed=True, epoch=state.epoch + 1)


def clear_core(state: State, core: int) -> State:
    """Scrub the entire live root set, including special registers, on this core."""
    return replace(advance(state), holders=tuple(
        replace(h, cap=replace(h.cap, tag=False))
        if h.core == core and h.place == "live" else h for h in state.holders))


def cancel_loan(state: State, loan: str) -> State:
    """Scrub the admission-proved complete footprint, including captured copies."""
    return replace(advance(state), holders=tuple(
        replace(h, cap=replace(h.cap, tag=False)) if h.cap.loan == loan else h
        for h in state.holders), loans=state.loans - {loan})


def acknowledge(comp: Composition, state: State, core: int) -> State:
    if core not in comp.proxies or exposed(state, core) or not comp.targets <= state.bits:
        raise RevocationError("proxy has not established its local postcondition")
    if any(h.core == core and h.cap.loan in state.loans for h in state.holders):
        raise RevocationError("proxy has an outstanding call")
    if state.accepted_transfers or not state.device_issue_closed:
        raise RevocationError("proxy cannot acknowledge an incomplete device boundary")
    return replace(advance(state), pending_proxies=state.pending_proxies - {core})


def acknowledgement_timeout(state: State) -> State:
    """The admitted deadline expires: retain quarantine and refuse completion.

    This decision does not claim the missing peer has physically stopped. The
    runtime's escalation/isolation reaction remains an M4.4/R2 obligation.
    """
    return replace(advance(state), failed=True, invocations_closed=True)


def finish_device(state: State) -> State:
    if not state.invocations_closed:
        raise RevocationError("device cannot close before publication stops new grants")
    return replace(advance(state), accepted_transfers=0, device_issue_closed=True)


def complete(comp: Composition, state: State) -> State:
    errors = completion_errors(comp, state)
    if errors:
        raise RevocationError(", ".join(errors))
    return replace(advance(state), barrier=state.clock + 1)


def start_sweep(comp: Composition, state: State) -> State:
    if state.barrier is None or completion_errors(comp, state):
        raise RevocationError("a sweep for reuse must start after semantic completion")
    return replace(advance(state), sweep_started=state.clock + 1, swept=frozenset())


def sweep(comp: Composition, state: State, name: str) -> State:
    if state.sweep_started is None or name not in comp.swept:
        raise RevocationError("no post-barrier pass or location outside its footprint")
    return replace(advance(state), holders=tuple(
        replace(h, cap=load(h.cap, state.bits, h.core)) if h.name == name else h
        for h in state.holders), swept=state.swept | {name})


def reuse_errors(comp: Composition, state: State) -> list[str]:
    errors = completion_errors(comp, state)
    if (state.barrier is None or state.sweep_started is None
            or state.sweep_started <= state.barrier or state.swept != comp.swept):
        errors.append("post-barrier-full-pass")
    # Unlike completion, examine raw tags. Clearing the bitmap would resurrect a
    # stored tag even if today's filtered load cannot use it. This also detects a
    # write behind the sweep cursor, regardless of the cursor's claimed progress.
    if any(h.cap.retired and h.cap.tag for h in state.holders):
        errors.append("reuse-resurrection")
    return errors


def reuse(comp: Composition, state: State) -> State:
    errors = reuse_errors(comp, state)
    if errors:
        raise RevocationError(", ".join(errors))
    return replace(advance(state), bits=state.bits - comp.targets)


@dataclass(frozen=True)
class Job:
    """One admitted service slot: period and width include all scheduling costs."""
    period: int
    width: int
    work: int

    def bound(self) -> int:
        if not 0 < self.work <= self.width <= self.period:
            raise RevocationError("job has no admitted finite slot")
        return self.period + self.work


@dataclass(frozen=True)
class Budget:
    publication: tuple[Job, ...]
    barriers: tuple[Job, ...]
    cancellations: tuple[Job, ...]
    proxy_edges: tuple[Job, ...]
    devices: tuple[Job, ...]
    sweep_period: int
    sweep_width: int
    group_cost: int
    groups: int

    def bounds(self, comp: Composition, initial: State) -> dict[str, int]:
        errors = map_errors(comp, initial)
        if initial.clock or initial.bits or initial.invocations_closed:
            errors.append("budget requires the initial composition state")
        expected_loans = frozenset(h.cap.loan for h in initial.holders if h.cap.loan)
        if expected_loans != initial.loans or initial.pending_proxies != comp.proxies:
            errors.append("initial obligation inventory")
        # Tuple positions are the sorted island/core/loan/proxy inventory. Each
        # proxy has two positions (notify, ACK); this slice has one device window.
        sizes = (("publication", len(self.publication), len({i for i, _ in comp.targets})),
                 ("core", len(self.barriers), len(comp.cores)),
                 ("loan", len(self.cancellations), len(initial.loans)),
                 ("proxy", len(self.proxy_edges), 2 * len(comp.proxies)),
                 ("device", len(self.devices), int(not initial.device_issue_closed
                                                   or initial.accepted_transfers > 0)),
                 ("sweep", self.groups, len(comp.swept)))
        errors.extend(f"{name} service inventory" for name, got, want in sizes if got != want)
        if errors:
            raise RevocationError(", ".join(errors))
        if not self.publication or not self.barriers or self.groups < 1:
            raise RevocationError("empty publication, barrier, or sweep inventory")
        mark = sum(job.bound() for job in self.publication)
        # Serial sum is conservative even when unrelated admitted slots overlap.
        # The ledger has a notification and an acknowledgement job for every
        # static edge of the rooted star; no cyclic retry or untrusted wait.
        barrier = mark + sum(job.bound() for jobs in (
            self.barriers, self.cancellations, self.proxy_edges, self.devices)
            for job in jobs)
        if not 0 < self.group_cost <= self.sweep_width <= self.sweep_period:
            raise RevocationError("sweep service is absent or unbounded")
        # Reserve a whole discarded group on every cut. Zero progress is refusal.
        progress = self.sweep_width // self.group_cost - 1
        if progress < 1:
            raise RevocationError("sweep slot cannot guarantee a completed group")
        frames = (self.groups + progress - 1) // progress
        sweep_bound = frames * self.sweep_period + self.sweep_width
        return {"bitmap_mark": mark, "semantic_completion": barrier,
                "ack_failure_detection": barrier, "post_barrier_sweep": sweep_bound,
                "set_to_reuse": barrier + sweep_bound,
                "guaranteed_groups_per_frame": progress}


def fixture(width: int = 3) -> tuple[Composition, State]:
    if not 1 <= width <= 8:
        raise RevocationError("qualification fixture width must be between one and eight")
    cap = Capability(64, 64 + width * GRANULE)
    remote = replace(cap, island=1)
    loan = Capability(512, 520, loan="call")
    holders = [Holder("register", "live", 0, cap),
               Holder("mepcc", "live", 0, cap),
               Holder("saved", "saved", 0, cap),
               Holder("trusted-stack", "saved", 0, cap),
               Holder("grant-storage", "memory", 0, cap),
               Holder("outside-interval-copy", "memory", 0, cap),
               Holder("callee", "live", 0, loan),
               Holder("loan-copy", "saved", 0, loan),
               Holder("remote-register", "live", 1, remote),
               Holder("proxy-slot", "memory", 1, remote),
               Holder("unrelated-grant", "memory", 0,
                      Capability(512, 520, retired=False))]
    holders.extend(Holder(f"interior-{i}", "memory", 0,
                          replace(cap, base=64 + i * GRANULE)) for i in range(width))
    comp = Composition(frozenset(h.name for h in holders),
                       frozenset(h.name for h in holders if h.place != "live"),
                       frozenset((island, 8 + i) for island in (0, 1)
                                 for i in range(width)), frozenset({0, 1}), frozenset({1}))
    return comp, State(tuple(holders))


def ready(comp: Composition, state: State) -> State:
    state = publish(comp, state)
    for core in sorted(comp.cores):
        state = clear_core(state, core)
    state = cancel_loan(state, "call")
    state = finish_device(state)
    for core in sorted(comp.proxies):
        state = acknowledge(comp, state, core)
    return state


def reclaimed(comp: Composition, state: State) -> State:
    state = start_sweep(comp, complete(comp, ready(comp, state)))
    for name in sorted(comp.swept):
        state = sweep(comp, state, name)
    return state


def replace_holder(state: State, name: str, holder: Holder) -> State:
    return replace(state, holders=tuple(holder if h.name == name else h
                                        for h in state.holders))


def counterexamples() -> list[tuple[str, list[str]]]:
    """Generated corruptions at the completion and reuse boundaries."""
    result: list[tuple[str, list[str]]] = []
    for width in (1, 2, 3):
        comp, initial = fixture(width)
        safe = ready(comp, initial)
        for name, kind in (("register", "resident-register"), ("mepcc", "resident-register"),
                           ("callee", "callee-loan"),
                           ("remote-register", "remote-delegate")):
            old = next(h for h in initial.holders if h.name == name)
            bad = replace_holder(safe, name, old)
            result.append((f"{kind}/w{width}/{name}", completion_errors(comp, bad)))
        saved = next(h for h in safe.holders if h.name == "saved")
        result.append((f"saved-context/w{width}", completion_errors(
            comp, replace_holder(safe, "saved", replace(saved, filtered_restore=False)))))
        # Publish just the original base, retaining a legitimately narrowed base.
        if width > 1:
            bad = replace(safe, bits=frozenset({(0, 8), (1, 8)}))
            incomplete = replace(comp, targets=bad.bits)
            result.append((f"narrowed-capability/w{width}",
                           completion_errors(incomplete, bad)))
        result.append((f"callee-loan/w{width}/pending-call",
                       completion_errors(comp, replace(safe, loans=frozenset({"call"})))))
        result.append((f"remote-delegate/w{width}/missing-ack",
                       completion_errors(comp, replace(safe, pending_proxies=frozenset({1})))))
        result.append((f"device-transfer/w{width}",
                       completion_errors(comp, replace(safe, accepted_transfers=1))))
        swept = reclaimed(comp, initial)
        for name in ("saved", "outside-interval-copy", "grant-storage"):
            old = next(h for h in initial.holders if h.name == name)
            bad = replace_holder(swept, name, old)
            result.append((f"reuse-resurrection/w{width}/{name}", reuse_errors(comp, bad)))
        result.append((f"reuse-resurrection/w{width}/pre-barrier-pass",
                       reuse_errors(comp, replace(swept, sweep_started=0))))
        result.append((f"remote-delegate/w{width}/ack-timeout",
                       completion_errors(comp, replace(safe, failed=True))))
    return result


def interleavings() -> tuple[int, list[str]]:
    """Every ordering of independent cleanup actions, with guarded proxy ACKs."""
    count = 0
    errors: list[str] = []
    for width in (1, 2, 3):
        comp, initial = fixture(width)
        for order in permutations(("core0", "core1", "loan", "device", "ack")):
            state = publish(comp, initial)
            for action in order:
                if action == "core0":
                    state = clear_core(state, 0)
                elif action == "core1":
                    state = clear_core(state, 1)
                elif action == "loan":
                    state = cancel_loan(state, "call")
                elif action == "device":
                    state = finish_device(state)
                else:
                    with suppress(RevocationError):
                        state = acknowledge(comp, state, 1)
                    # A refused ACK stays pending; the scheduled retry is below.
            state = acknowledge(comp, state, 1)
            try:
                state = start_sweep(comp, complete(comp, state))
                for name in sorted(comp.swept):
                    state = sweep(comp, state, name)
                state = reuse(comp, state)
                if exposed(state):
                    errors.append(f"authority resurrected at {width}/{order}")
                unrelated = next(h for h in state.holders if h.name == "unrelated-grant")
                if not dereference(unrelated.cap, 512):
                    errors.append("unrelated grant was destroyed")
            except RevocationError as exc:
                errors.append(f"positive schedule refused: {width}/{order}: {exc}")
            count += 1
    return count, errors


SOURCES = (
    "model/model/core/revocation.sail",
    "model/model/core/addr_checks.sail",
    "model/model/core/cap_regs.sail",
    "model/model/extensions/CHERI/cheri_mem.sail",
    "model/model/extensions/CHERI/cheri_insts.sail",
    "model/model/extensions/CHERI/cheri_custom.sail",
    "model/model/extensions/I/base_insts.sail",
    "model/model/exceptions/sys_exceptions.sail",
    "proofs/PartitionContext.v",
)


def qualify(root: Path) -> dict[str, object]:
    examples = counterexamples()
    count, errors = interleavings()
    errors.extend(f"counterexample accepted: {name}" for name, reasons in examples
                  if not reasons)
    budget = Budget((Job(10, 4, 2), Job(10, 4, 2)),
                    (Job(20, 8, 4), Job(20, 8, 4)), (Job(20, 6, 4),),
                    (Job(30, 5, 3), Job(30, 5, 3)), (Job(16, 4, 4),),
                    40, 12, 3, len(fixture()[0].swept))
    return {"scope": "bounded host qualification; no Sail refinement or product timing",
            "model_sha256": sha256((root / "tools/vos/revocation.py").read_bytes()).hexdigest(),
            "positive_interleavings": count, "refusal_cases": len(examples),
            "counterexamples": [{"case": name, "reasons": reasons}
                                for name, reasons in examples],
            "illustrative_bounds": budget.bounds(*fixture()),
            "sources_sha256": {path: sha256((root / path).read_bytes()).hexdigest()
                               for path in SOURCES},
            "errors": errors}
