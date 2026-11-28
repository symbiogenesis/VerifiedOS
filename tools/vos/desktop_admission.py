# SPDX-License-Identifier: Apache-2.0
"""Q34e-i desktop elastic-domain admission, pool exhaustion, and slot-geometry analyzer.

Executable exact `fractions.Fraction` reference matching
[DesktopAdmission.v](../../proofs/DesktopAdmission.v) (`R-07-037e`, `R-07-037g`,
`R-08-047d`, `R-11-006c`, `R-11-022a`, `R-18-004a`, `R-18-004c`).
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import Enum
from fractions import Fraction


class DesktopAdmissionError(ValueError):
    """A desktop pool operation, domain admission, or geometry comparison failed."""


def _require_nat(value: int, field: str, *, positive: bool = False) -> int:
    if type(value) is not int or value < int(positive):
        kind = "positive" if positive else "nonnegative"
        raise DesktopAdmissionError(f"{field}: {kind} integer required")
    return value


def _require_bool(value: bool, field: str) -> bool:
    if type(value) is not bool:
        raise DesktopAdmissionError(f"{field}: boolean required")
    return value


def _require_fraction(value: Fraction, field: str, *, positive: bool = False) -> Fraction:
    if type(value) is not Fraction:
        raise DesktopAdmissionError(f"{field}: exact Fraction required")
    if positive and value <= 0:
        raise DesktopAdmissionError(f"{field}: positive Fraction required")
    if not positive and value < 0:
        raise DesktopAdmissionError(f"{field}: nonnegative Fraction required")
    return value


def _ceil_div(numerator: int, denominator: int) -> int:
    if denominator == 0:
        return 0
    return (numerator + denominator - 1) // denominator if numerator > 0 else 0


# =========================================================================
# S1. Pool exhaustion ladder (`R-08-047d`, `R-07-037e`).
# =========================================================================


class LadderOutcome(Enum):
    """Finite outcome of a pool launch, allocation, or exhaustion ladder step."""

    GRANTED = "granted"
    REFUSE_REQUEST = "refuse_request"
    SHED_LOCAL = "shed_local"
    HIBERNATED = "hibernated"
    REFUSE_AT_CEILING = "refuse_at_ceiling"
    REFUSE_LAUNCH = "refuse_launch"


@dataclass(frozen=True)
class PoolMember:
    """One domain member's pool accounting and hibernation eligibility flags."""

    id: int
    floor_bytes: int
    extra_bytes: int
    sheddable_bytes: int
    live: bool
    hibernated: bool
    consent_bearing: bool
    mid_transaction: bool
    sacrificable: bool
    checkpointable: bool
    last_focus_tick: int

    @property
    def held_bytes(self) -> int:
        return self.floor_bytes + self.extra_bytes if self.live else 0


@dataclass(frozen=True)
class PoolState:
    """Domain-isolated pool state alongside unchanged external-domain footprints."""

    capacity_bytes: int
    quarantined_bytes: int
    focused_id: int | None
    fixed_tier_bytes: int
    other_domain_bytes: int
    members: tuple[PoolMember, ...]

    @property
    def used_bytes(self) -> int:
        return sum(m.held_bytes for m in self.members)

    @property
    def committed_bytes(self) -> int:
        return self.used_bytes + self.quarantined_bytes

    @property
    def free_bytes(self) -> int:
        return self.capacity_bytes - self.committed_bytes

    @property
    def sheddable_bytes(self) -> int:
        return sum(m.sheddable_bytes for m in self.members if m.live)


@dataclass(frozen=True)
class LadderResult:
    """Result of one pool operation or exhaustion ladder transition."""

    outcome: LadderOutcome
    state: PoolState
    victim_id: int | None = None


def validate_pool_state(state: PoolState) -> None:
    """Verify structural invariants of `state` (`pool_well_formed`)."""
    _require_nat(state.capacity_bytes, "pool.capacity_bytes")
    _require_nat(state.quarantined_bytes, "pool.quarantined_bytes")
    _require_nat(state.fixed_tier_bytes, "pool.fixed_tier_bytes")
    _require_nat(state.other_domain_bytes, "pool.other_domain_bytes")
    if state.focused_id is not None:
        _require_nat(state.focused_id, "pool.focused_id")
    seen_ids: set[int] = set()
    for m in state.members:
        _require_nat(m.id, "member.id")
        if m.id in seen_ids:
            raise DesktopAdmissionError(f"duplicate pool member id {m.id}")
        seen_ids.add(m.id)
        _require_nat(m.floor_bytes, f"member[{m.id}].floor_bytes")
        _require_nat(m.extra_bytes, f"member[{m.id}].extra_bytes")
        _require_nat(m.sheddable_bytes, f"member[{m.id}].sheddable_bytes")
        _require_nat(m.last_focus_tick, f"member[{m.id}].last_focus_tick")
        for flag_name, flag in (
            ("live", m.live),
            ("hibernated", m.hibernated),
            ("consent_bearing", m.consent_bearing),
            ("mid_transaction", m.mid_transaction),
            ("sacrificable", m.sacrificable),
            ("checkpointable", m.checkpointable),
        ):
            _require_bool(flag, f"member[{m.id}].{flag_name}")
        if m.sheddable_bytes > m.extra_bytes:
            raise DesktopAdmissionError(
                f"member[{m.id}]: sheddable_bytes ({m.sheddable_bytes}) > "
                f"extra_bytes ({m.extra_bytes})"
            )
    if state.committed_bytes > state.capacity_bytes:
        raise DesktopAdmissionError(
            f"pool committed ({state.committed_bytes}) > capacity ({state.capacity_bytes})"
        )


def _find_member(members: tuple[PoolMember, ...], member_id: int) -> PoolMember | None:
    for m in members:
        if m.id == member_id:
            return m
    return None


def launch_member(state: PoolState, member_id: int) -> LadderResult:
    """Reserve `floor_bytes` in free pool capacity at launch; refuse if unavailable."""
    validate_pool_state(state)
    _require_nat(member_id, "member_id")
    target = _find_member(state.members, member_id)
    if target is None or target.live or target.floor_bytes > state.free_bytes:
        return LadderResult(LadderOutcome.REFUSE_LAUNCH, state)
    updated = tuple(
        replace(
            m,
            extra_bytes=0,
            sheddable_bytes=0,
            live=True,
            hibernated=False,
        )
        if m.id == member_id
        else m
        for m in state.members
    )
    return LadderResult(LadderOutcome.GRANTED, replace(state, members=updated))


def alloc_chunk(state: PoolState, member_id: int, req_bytes: int) -> LadderResult:
    """Allocate `req_bytes` from free pool capacity, or return `CapacityExhausted` refusal."""
    validate_pool_state(state)
    _require_nat(member_id, "member_id")
    _require_nat(req_bytes, "req_bytes")
    target = _find_member(state.members, member_id)
    if target is None or not target.live or req_bytes > state.free_bytes:
        return LadderResult(LadderOutcome.REFUSE_REQUEST, state)
    updated = tuple(
        replace(m, extra_bytes=m.extra_bytes + req_bytes) if m.id == member_id else m
        for m in state.members
    )
    return LadderResult(LadderOutcome.GRANTED, replace(state, members=updated))


def shed_owner_local(state: PoolState) -> LadderResult:
    """Rung 2: shed owner-local state into quarantine (awaiting reuse barrier)."""
    validate_pool_state(state)
    shed_amt = state.sheddable_bytes
    if shed_amt == 0:
        return LadderResult(LadderOutcome.REFUSE_AT_CEILING, state)
    updated = tuple(
        replace(m, extra_bytes=m.extra_bytes - m.sheddable_bytes, sheddable_bytes=0)
        if m.live
        else m
        for m in state.members
    )
    return LadderResult(
        LadderOutcome.SHED_LOCAL,
        replace(
            state,
            quarantined_bytes=state.quarantined_bytes + shed_amt,
            members=updated,
        ),
    )


def hibernation_eligible(focused_id: int | None, member: PoolMember) -> bool:
    """Return True iff `member` is live, non-focused, and permitted for hibernation."""
    return (
        member.live
        and (focused_id is None or member.id != focused_id)
        and not member.consent_bearing
        and not member.mid_transaction
        and member.sacrificable
        and member.checkpointable
    )


def pick_lru_victim(
    focused_id: int | None, members: tuple[PoolMember, ...]
) -> PoolMember | None:
    """Select the least-recently-focused eligible member, or None at ceiling."""
    best: PoolMember | None = None
    for m in members:
        if hibernation_eligible(focused_id, m) and (
            best is None or m.last_focus_tick < best.last_focus_tick
        ):
            best = m
    return best


def hibernate_lru(state: PoolState) -> LadderResult:
    """Rung 3: hibernate the LRU eligible background member into quarantine."""
    validate_pool_state(state)
    victim = pick_lru_victim(state.focused_id, state.members)
    if victim is None:
        return LadderResult(LadderOutcome.REFUSE_AT_CEILING, state)
    reclaimed = victim.floor_bytes + victim.extra_bytes
    updated = tuple(
        replace(m, extra_bytes=0, sheddable_bytes=0, live=False, hibernated=True)
        if m.id == victim.id
        else m
        for m in state.members
    )
    return LadderResult(
        LadderOutcome.HIBERNATED,
        replace(
            state,
            quarantined_bytes=state.quarantined_bytes + reclaimed,
            members=updated,
        ),
        victim_id=victim.id,
    )


def complete_reuse_barrier(state: PoolState) -> PoolState:
    """Complete the sweep/reuse barrier, returning quarantined capacity to free."""
    validate_pool_state(state)
    return replace(state, quarantined_bytes=0)


def exhaustion_step(state: PoolState, member_id: int, req_bytes: int) -> LadderResult:
    """Execute one step of the finite pool exhaustion ladder."""
    alloc = alloc_chunk(state, member_id, req_bytes)
    if alloc.outcome == LadderOutcome.GRANTED:
        return alloc
    if state.sheddable_bytes > 0:
        return shed_owner_local(state)
    return hibernate_lru(state)


def run_exhaustion_campaign(
    state: PoolState, member_id: int, req_bytes: int
) -> tuple[LadderResult, ...]:
    """Walk the finite exhaustion ladder until granted or ceiling refusal (barrier-free)."""
    steps: list[LadderResult] = []
    cur = state
    for _ in range(len(state.members) + 3):
        alloc = alloc_chunk(cur, member_id, req_bytes)
        steps.append(alloc)
        if alloc.outcome == LadderOutcome.GRANTED:
            break
        if cur.sheddable_bytes > 0:
            shed = shed_owner_local(cur)
            steps.append(shed)
            cur = shed.state
            continue
        hib = hibernate_lru(cur)
        steps.append(hib)
        cur = hib.state
        if hib.outcome == LadderOutcome.REFUSE_AT_CEILING:
            break
    return tuple(steps)


# =========================================================================
# S2. Focus dispatch bound, minimum share, and >=8-member desktop roster.
# =========================================================================


@dataclass(frozen=True)
class MemberSpec:
    """Manifest and EEVDF declaration for one desktop elastic-domain member."""

    id: int
    app: int
    is_build: bool
    weight: int
    request: int
    min_share: Fraction
    floor_bytes: int


@dataclass(frozen=True)
class DomainSpec:
    """Desktop elastic-domain specification matching `DesktopAdmission.DomainSpec`."""

    label: int
    members: tuple[MemberSpec, ...]
    focus_weight: int
    focus_request: int
    call_interval: int
    yield_bound: int
    rotation_cost: int
    vmclear_cost: int
    poll_cost: int
    switch_cost: int
    opp_cycles_per_ms: int
    focus_exec_cycles: int
    scanout_period: int
    dispatch_deadline_ms: Fraction = Fraction(167, 10)
    response_deadline_ms: Fraction = Fraction(667, 10)
    peak_memory_bytes: int = 1024


@dataclass(frozen=True)
class SlotWindow:
    """One offline domain slot window within a major frame `[0, frame_period)`."""

    start: int
    width: int


@dataclass(frozen=True)
class SlotGeometry:
    """Offline frame and domain slot geometry matching `DesktopAdmission.SlotGeometry`."""

    frame_period: int
    reserved_band: int
    peer_width: int
    peer_service_floor: int
    domain_slots: tuple[SlotWindow, ...]
    admitted_member_service_floor: int
    peak_memory_bytes: int


@dataclass(frozen=True)
class AdmissionAnalysis:
    """Exact rational admission diagnostics for `(DomainSpec, SlotGeometry)`."""

    admitted: bool
    errors: tuple[str, ...]
    call_bound: int
    intra_step_cost: int
    boundary_need: int
    slot_entry_overhead: int
    unusable_tail_bound: int
    min_usable_slot_width: int
    total_domain_width: int
    total_usable_cycles: int
    min_slot_usable: int
    max_slot_gap: int
    worst_eevdf_interference: int
    focus_work_cycles: int
    focus_dispatch_cycles: int
    input_to_response_cycles: int
    focus_dispatch_ms: Fraction
    input_to_response_ms: Fraction
    domain_net_share: Fraction
    member_net_shares: dict[int, Fraction]


@dataclass(frozen=True)
class GeometryComparison:
    """Offline slot-geometry comparison verdict (`R-11-022a`)."""

    accepted: bool
    reasons: tuple[str, ...]
    baseline: AdmissionAnalysis
    candidate: AdmissionAnalysis


def call_bound(dom: DomainSpec) -> int:
    return dom.call_interval + dom.yield_bound


def intra_step_cost(dom: DomainSpec) -> int:
    return dom.rotation_cost + dom.vmclear_cost


def boundary_need(dom: DomainSpec) -> int:
    return call_bound(dom) + dom.yield_bound + intra_step_cost(dom)


def slot_entry_overhead(dom: DomainSpec) -> int:
    return dom.switch_cost + dom.vmclear_cost + dom.poll_cost


def unusable_tail_bound(dom: DomainSpec) -> int:
    return max(0, boundary_need(dom) - 1)


def min_usable_slot_width(dom: DomainSpec) -> int:
    return slot_entry_overhead(dom) + boundary_need(dom)


def slot_usable_cycles(dom: DomainSpec, width: int) -> int:
    if width >= min_usable_slot_width(dom):
        return width - slot_entry_overhead(dom) - unusable_tail_bound(dom)
    return 0


def slot_gaps(frame_period: int, slots: Sequence[SlotWindow]) -> tuple[int, ...]:
    if not slots:
        return (frame_period,)
    gaps = [
        slots[i + 1].start - (slots[i].start + slots[i].width)
        for i in range(len(slots) - 1)
    ]
    wrap = (frame_period - (slots[-1].start + slots[-1].width)) + slots[0].start
    gaps.append(wrap)
    return tuple(gaps)


def max_slot_gap(geom: SlotGeometry) -> int:
    return max(slot_gaps(geom.frame_period, geom.domain_slots), default=geom.frame_period)


def eff_request_member(dom: DomainSpec, m: MemberSpec) -> int:
    return m.request + call_bound(dom) + dom.yield_bound


def eff_request_focus(dom: DomainSpec) -> int:
    return dom.focus_request + call_bound(dom) + dom.yield_bound


def dispatches_ahead(dom: DomainSpec, m: MemberSpec) -> int:
    return 1 + (m.weight * eff_request_focus(dom)) // (
        dom.focus_weight * eff_request_member(dom, m)
    )


def member_eevdf_cost(dom: DomainSpec, m: MemberSpec) -> int:
    return dispatches_ahead(dom, m) * (eff_request_member(dom, m) + intra_step_cost(dom))


def eevdf_interference_for_focus(
    dom: DomainSpec, focus_id: int, live: Sequence[MemberSpec]
) -> int:
    return sum(member_eevdf_cost(dom, m) for m in live if m.id != focus_id)


def worst_eevdf_interference(dom: DomainSpec) -> int:
    return max(
        (eevdf_interference_for_focus(dom, f.id, dom.members) for f in dom.members),
        default=0,
    )


def focus_work_cycles(dom: DomainSpec) -> int:
    return boundary_need(dom) + worst_eevdf_interference(dom)


def min_slot_usable(dom: DomainSpec, geom: SlotGeometry) -> int:
    if not geom.domain_slots:
        return 0
    return min(slot_usable_cycles(dom, s.width) for s in geom.domain_slots)


def focus_dispatch_cycles(dom: DomainSpec, geom: SlotGeometry) -> int:
    u = min_slot_usable(dom, geom)
    if u == 0:
        return 0
    work = focus_work_cycles(dom)
    k = max(1, _ceil_div(work, u))
    tail = unusable_tail_bound(dom)
    return (
        tail
        + k * (max_slot_gap(geom) + slot_entry_overhead(dom))
        + (k - 1) * tail
        + work
    )


def exec_extra_cycles(dom: DomainSpec, geom: SlotGeometry) -> int:
    u = min_slot_usable(dom, geom)
    if u == 0 or dom.focus_exec_cycles == 0:
        return 0
    work = focus_work_cycles(dom)
    k_disp = max(1, _ceil_div(work, u))
    k_tot = max(1, _ceil_div(work + dom.focus_exec_cycles, u))
    per_extra_slot = (
        max_slot_gap(geom) + slot_entry_overhead(dom) + unusable_tail_bound(dom)
    )
    return (k_tot - k_disp) * per_extra_slot + dom.focus_exec_cycles


def input_to_response_cycles(dom: DomainSpec, geom: SlotGeometry) -> int:
    return focus_dispatch_cycles(dom, geom) + exec_extra_cycles(dom, geom) + dom.scanout_period


def total_weight_subset(
    dom: DomainSpec, focus_id: int | None, live: Sequence[MemberSpec]
) -> int:
    return sum(
        dom.focus_weight if (focus_id is not None and m.id == focus_id) else m.weight
        for m in live
    )


def worst_total_weight_against(dom: DomainSpec, member_id: int) -> int:
    base_w = total_weight_subset(dom, None, dom.members)
    return max(
        [base_w]
        + [
            total_weight_subset(dom, f.id, dom.members)
            for f in dom.members
            if f.id != member_id
        ]
    )


def member_eevdf_share(dom: DomainSpec, m: MemberSpec) -> Fraction:
    return Fraction(m.weight, worst_total_weight_against(dom, m.id))


def domain_net_share(dom: DomainSpec, geom: SlotGeometry) -> Fraction:
    usable = sum(slot_usable_cycles(dom, s.width) for s in geom.domain_slots)
    return Fraction(usable, geom.frame_period)


def member_step_efficiency(dom: DomainSpec, m: MemberSpec) -> Fraction:
    eff = eff_request_member(dom, m)
    return Fraction(eff, eff + intra_step_cost(dom))


def member_net_share(
    dom: DomainSpec, geom: SlotGeometry, m: MemberSpec
) -> Fraction:
    return (
        member_eevdf_share(dom, m)
        * domain_net_share(dom, geom)
        * member_step_efficiency(dom, m)
    )


def _validate_inputs(dom: DomainSpec, geom: SlotGeometry) -> list[str]:
    _require_nat(dom.label, "dom.label")
    _require_nat(dom.focus_weight, "dom.focus_weight", positive=True)
    _require_nat(dom.focus_request, "dom.focus_request", positive=True)
    _require_nat(dom.call_interval, "dom.call_interval")
    _require_nat(dom.yield_bound, "dom.yield_bound")
    _require_nat(dom.rotation_cost, "dom.rotation_cost")
    _require_nat(dom.vmclear_cost, "dom.vmclear_cost")
    _require_nat(dom.poll_cost, "dom.poll_cost")
    _require_nat(dom.switch_cost, "dom.switch_cost")
    _require_nat(dom.opp_cycles_per_ms, "dom.opp_cycles_per_ms", positive=True)
    _require_nat(dom.focus_exec_cycles, "dom.focus_exec_cycles")
    _require_nat(dom.scanout_period, "dom.scanout_period")
    _require_fraction(dom.dispatch_deadline_ms, "dom.dispatch_deadline_ms", positive=True)
    _require_fraction(dom.response_deadline_ms, "dom.response_deadline_ms", positive=True)
    _require_nat(dom.peak_memory_bytes, "dom.peak_memory_bytes")
    _require_nat(geom.frame_period, "geom.frame_period", positive=True)
    _require_nat(geom.reserved_band, "geom.reserved_band")
    _require_nat(geom.peer_width, "geom.peer_width")
    _require_nat(geom.peer_service_floor, "geom.peer_service_floor")
    _require_nat(geom.admitted_member_service_floor, "geom.admitted_member_service_floor")
    _require_nat(geom.peak_memory_bytes, "geom.peak_memory_bytes")

    errors: list[str] = []
    if len(dom.members) < 8:
        errors.append(
            f"R-18-004a(vi): desktop roster requires >= 8 members, found {len(dom.members)}"
        )
    if not any(m.is_build for m in dom.members):
        errors.append("R-18-004a(vi): desktop roster missing toolchain build member")

    seen_ids: set[int] = set()
    for m in dom.members:
        _require_nat(m.id, "member.id")
        _require_nat(m.app, "member.app")
        _require_bool(m.is_build, "member.is_build")
        _require_nat(m.weight, f"member[{m.id}].weight", positive=True)
        _require_nat(m.request, f"member[{m.id}].request", positive=True)
        _require_fraction(m.min_share, f"member[{m.id}].min_share")
        _require_nat(m.floor_bytes, f"member[{m.id}].floor_bytes")
        if m.id in seen_ids:
            errors.append(f"duplicate member id {m.id}")
        seen_ids.add(m.id)

    if not geom.domain_slots:
        errors.append("slot geometry declares no domain slots")
    pos = 0
    for idx, slot in enumerate(geom.domain_slots):
        _require_nat(slot.start, f"slot[{idx}].start")
        _require_nat(slot.width, f"slot[{idx}].width", positive=True)
        if slot.start < pos:
            errors.append(f"slot[{idx}] overlaps or is out of order (start={slot.start} < {pos})")
        pos = slot.start + slot.width
    if pos > geom.frame_period:
        errors.append(f"domain slots end at {pos} > frame_period {geom.frame_period}")
    return errors


def analyze_domain(dom: DomainSpec, geom: SlotGeometry) -> AdmissionAnalysis:
    """Compute exact rational admission diagnostics for `(dom, geom)`."""
    errors = _validate_inputs(dom, geom)
    tot_width = sum(s.width for s in geom.domain_slots)
    if tot_width + geom.reserved_band + geom.peer_width > geom.frame_period:
        errors.append(
            f"frame budget exceeded: {tot_width} + {geom.reserved_band} + "
            f"{geom.peer_width} > {geom.frame_period}"
        )

    min_w = min_usable_slot_width(dom)
    for idx, s in enumerate(geom.domain_slots):
        if s.width < min_w:
            errors.append(
                f"R-11-006c: slot[{idx}] width {s.width} < min_usable_slot_width {min_w}"
            )

    tot_usable = sum(slot_usable_cycles(dom, s.width) for s in geom.domain_slots)
    min_u = min_slot_usable(dom, geom)
    if min_u == 0:
        errors.append("shortest domain slot yields 0 usable cycles")
    if tot_usable < geom.admitted_member_service_floor:
        errors.append(
            f"usable domain cycles {tot_usable} < admitted floor "
            f"{geom.admitted_member_service_floor}"
        )

    shares: dict[int, Fraction] = {}
    if dom.members and len({m.id for m in dom.members}) == len(dom.members):
        for m in dom.members:
            net = member_net_share(dom, geom, m)
            shares[m.id] = net
            if net < m.min_share:
                errors.append(
                    f"R-07-037g: member {m.id} net share {net} < min_share {m.min_share}"
                )

    disp_cyc = focus_dispatch_cycles(dom, geom)
    resp_cyc = input_to_response_cycles(dom, geom)
    disp_ms = Fraction(disp_cyc, dom.opp_cycles_per_ms)
    resp_ms = Fraction(resp_cyc, dom.opp_cycles_per_ms)
    if min_u > 0 and disp_ms > dom.dispatch_deadline_ms:
        errors.append(
            f"R-11-006c/R-18-004a: focus dispatch {disp_ms} ms > {dom.dispatch_deadline_ms} ms"
        )
    if min_u > 0 and resp_ms > dom.response_deadline_ms:
        errors.append(
            f"R-11-022a/R-18-004a: input-to-response {resp_ms} ms > {dom.response_deadline_ms} ms"
        )

    return AdmissionAnalysis(
        admitted=not errors,
        errors=tuple(errors),
        call_bound=call_bound(dom),
        intra_step_cost=intra_step_cost(dom),
        boundary_need=boundary_need(dom),
        slot_entry_overhead=slot_entry_overhead(dom),
        unusable_tail_bound=unusable_tail_bound(dom),
        min_usable_slot_width=min_w,
        total_domain_width=tot_width,
        total_usable_cycles=tot_usable,
        min_slot_usable=min_u,
        max_slot_gap=max_slot_gap(geom),
        worst_eevdf_interference=worst_eevdf_interference(dom),
        focus_work_cycles=focus_work_cycles(dom),
        focus_dispatch_cycles=disp_cyc,
        input_to_response_cycles=resp_cyc,
        focus_dispatch_ms=disp_ms,
        input_to_response_ms=resp_ms,
        domain_net_share=domain_net_share(dom, geom),
        member_net_shares=shares,
    )


def admit_domain(dom: DomainSpec, geom: SlotGeometry) -> AdmissionAnalysis:
    """Verify `(dom, geom)` admission or raise `DesktopAdmissionError`."""
    analysis = analyze_domain(dom, geom)
    if not analysis.admitted:
        raise DesktopAdmissionError("; ".join(analysis.errors))
    return analysis


def compare_slot_geometries(
    dom: DomainSpec, base: SlotGeometry, cand: SlotGeometry
) -> GeometryComparison:
    """Compare offline `cand` against standing `base` holding `dom` fixed (`R-11-022a`)."""
    base_res = analyze_domain(dom, base)
    cand_res = analyze_domain(dom, cand)
    reasons: list[str] = []
    if not base_res.admitted:
        reasons.extend(f"baseline: {e}" for e in base_res.errors)
    if not cand_res.admitted:
        reasons.extend(f"candidate: {e}" for e in cand_res.errors)
    if cand.frame_period != base.frame_period:
        reasons.append(
            f"frame_period changed ({cand.frame_period} != {base.frame_period})"
        )
    if cand.reserved_band != base.reserved_band:
        reasons.append(
            f"reserved_band changed ({cand.reserved_band} != {base.reserved_band})"
        )
    if cand.peer_width != base.peer_width:
        reasons.append(f"peer_width changed ({cand.peer_width} != {base.peer_width})")
    if cand_res.total_domain_width != base_res.total_domain_width:
        reasons.append(
            f"total domain share changed ({cand_res.total_domain_width} != "
            f"{base_res.total_domain_width})"
        )
    if cand.peer_service_floor < base.peer_service_floor:
        reasons.append(
            f"peer service bound weakened ({cand.peer_service_floor} < "
            f"{base.peer_service_floor})"
        )
    if cand_res.total_usable_cycles < base.admitted_member_service_floor:
        reasons.append(
            f"member service bound weakened ({cand_res.total_usable_cycles} < "
            f"{base.admitted_member_service_floor})"
        )
    if cand.peak_memory_bytes > base.peak_memory_bytes:
        reasons.append(
            f"admitted peak memory increased ({cand.peak_memory_bytes} > "
            f"{base.peak_memory_bytes})"
        )
    if cand_res.focus_dispatch_ms >= base_res.focus_dispatch_ms:
        reasons.append(
            f"focus dispatch bound did not improve ({cand_res.focus_dispatch_ms} ms >= "
            f"{base_res.focus_dispatch_ms} ms)"
        )
    if cand_res.input_to_response_ms >= base_res.input_to_response_ms:
        reasons.append(
            f"input-to-response did not improve ({cand_res.input_to_response_ms} ms >= "
            f"{base_res.input_to_response_ms} ms)"
        )
    return GeometryComparison(
        accepted=not reasons,
        reasons=tuple(reasons),
        baseline=base_res,
        candidate=cand_res,
    )


def admit_slot_geometry_candidate(
    dom: DomainSpec, base: SlotGeometry, cand: SlotGeometry
) -> GeometryComparison:
    """Compare `cand` against `base` and raise `DesktopAdmissionError` if rejected."""
    comp = compare_slot_geometries(dom, base, cand)
    if not comp.accepted:
        raise DesktopAdmissionError("; ".join(comp.reasons))
    return comp


# =========================================================================
# Canonical reference witnesses matching `DesktopAdmission.v`.
# =========================================================================


def demo_domain_spec() -> DomainSpec:
    """Reference >=8-member desktop roster with toolchain build member."""
    return DomainSpec(
        label=3,
        members=(
            MemberSpec(0, 1, False, 4, 1, Fraction(1, 25), 128),
            MemberSpec(1, 2, True, 2, 1, Fraction(1, 50), 256),
            MemberSpec(2, 3, False, 1, 1, Fraction(1, 50), 64),
            MemberSpec(3, 4, False, 1, 1, Fraction(1, 50), 64),
            MemberSpec(4, 5, False, 1, 1, Fraction(1, 50), 64),
            MemberSpec(5, 6, False, 1, 1, Fraction(1, 50), 64),
            MemberSpec(6, 7, False, 1, 1, Fraction(1, 50), 64),
            MemberSpec(7, 8, False, 1, 1, Fraction(1, 50), 64),
        ),
        focus_weight=8,
        focus_request=1,
        call_interval=1,
        yield_bound=1,
        rotation_cost=0,
        vmclear_cost=1,
        poll_cost=1,
        switch_cost=0,
        opp_cycles_per_ms=10,
        focus_exec_cycles=16,
        scanout_period=160,
        dispatch_deadline_ms=Fraction(167, 10),
        response_deadline_ms=Fraction(667, 10),
        peak_memory_bytes=1024,
    )


def base_slot_geometry() -> SlotGeometry:
    """Standing 1-slot desktop geometry (120/200 domain share)."""
    return SlotGeometry(
        frame_period=200,
        reserved_band=20,
        peer_width=60,
        peer_service_floor=55,
        domain_slots=(SlotWindow(0, 120),),
        admitted_member_service_floor=100,
        peak_memory_bytes=1024,
    )


def two_slot_geometry() -> SlotGeometry:
    """Accepted 2-slot candidate halving max slot gap at identical 120/200 share."""
    return SlotGeometry(
        frame_period=200,
        reserved_band=20,
        peer_width=60,
        peer_service_floor=55,
        domain_slots=(SlotWindow(0, 60), SlotWindow(100, 60)),
        admitted_member_service_floor=100,
        peak_memory_bytes=1024,
    )


def fragmented_15slot_geometry() -> SlotGeometry:
    """Refuted 15-slot shorter-visit-period candidate whose overhead worsens service."""
    return SlotGeometry(
        frame_period=200,
        reserved_band=20,
        peer_width=60,
        peer_service_floor=55,
        domain_slots=tuple(SlotWindow(i * 13, 8) for i in range(15)),
        admitted_member_service_floor=100,
        peak_memory_bytes=1024,
    )


def demo_pool_state() -> PoolState:
    """Reference 8-member pool state matching `DesktopAdmission.demo_pool_state`."""
    return PoolState(
        capacity_bytes=1024,
        quarantined_bytes=64,
        focused_id=0,
        fixed_tier_bytes=2048,
        other_domain_bytes=512,
        members=(
            PoolMember(0, 128, 32, 16, True, False, False, False, True, True, 0),
            PoolMember(1, 256, 64, 16, True, False, False, False, False, True, 1),
            PoolMember(2, 64, 32, 8, True, False, True, False, True, True, 2),
            PoolMember(3, 64, 32, 8, True, False, False, True, True, True, 3),
            PoolMember(4, 64, 32, 8, True, False, False, False, True, False, 4),
            PoolMember(5, 64, 32, 8, True, False, False, False, True, True, 5),
            PoolMember(6, 64, 32, 8, True, False, False, False, True, True, 8),
            PoolMember(7, 64, 32, 8, False, False, False, False, True, True, 9),
        ),
    )


def demo_ceiling_pool_state() -> PoolState:
    """Reference pool state at ceiling where only focused/protected members remain live."""
    return PoolState(
        capacity_bytes=1024,
        quarantined_bytes=0,
        focused_id=0,
        fixed_tier_bytes=2048,
        other_domain_bytes=512,
        members=(
            PoolMember(0, 512, 0, 0, True, False, False, False, True, True, 0),
            PoolMember(1, 256, 0, 0, True, False, False, False, False, True, 1),
            PoolMember(2, 256, 0, 0, True, False, True, False, True, True, 2),
        ),
    )
