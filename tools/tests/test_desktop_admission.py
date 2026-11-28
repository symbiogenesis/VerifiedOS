# SPDX-License-Identifier: Apache-2.0
"""Q34e-i desktop admission, pool exhaustion ladder, and slot-geometry comparison tests."""

import re
from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

from tests.harness import Case, ensure
from vos import desktop_admission as da

INDEPENDENT_CASES = True


def _refused(call: Callable[[], object], fragment: str) -> None:
    try:
        call()
    except da.DesktopAdmissionError as exc:
        ensure(fragment in str(exc), f"unexpected refusal {exc!r} (expected {fragment!r})")
    else:
        raise AssertionError(f"accepted without {fragment!r}")


def pool_floor_reservation_and_exhausted_launch() -> None:
    pool = da.demo_pool_state()
    ensure(pool.free_bytes == 0, f"expected 0 free bytes, got {pool.free_bytes}")
    ensure(pool.quarantined_bytes == 64, "expected 64 quarantined bytes behind barrier")

    # Exhausted-floor launch MUST refuse even though 64 bytes sit behind the reuse barrier.
    refused = da.launch_member(pool, 7)
    ensure(refused.outcome == da.LadderOutcome.REFUSE_LAUNCH, f"unexpected {refused}")
    ensure(refused.state == pool, "refused launch mutated pool state")
    ensure(refused.state.fixed_tier_bytes == 2048, "fixed tier touched")
    ensure(refused.state.other_domain_bytes == 512, "other domain touched")

    # Completing reuse barrier releases quarantined bytes, allowing floor reservation.
    cleared = da.complete_reuse_barrier(pool)
    ensure(cleared.free_bytes == 64, f"expected 64 free bytes after barrier, got {cleared.free_bytes}")
    launched = da.launch_member(cleared, 7)
    ensure(launched.outcome == da.LadderOutcome.GRANTED, f"expected grant, got {launched}")
    ensure(launched.state.free_bytes == 0, "floor reservation did not consume free bytes")
    ensure(launched.state.used_bytes == cleared.used_bytes + 64, "floor not reserved")
    ensure(launched.state.fixed_tier_bytes == 2048 and launched.state.other_domain_bytes == 512,
           "external domains modified on launch")


def pool_focused_protection_and_lru_hibernation() -> None:
    pool = da.demo_pool_state()
    # Member 0 is focused with oldest tick (0); members 1..4 are protected/uncheckpointable;
    # member 5 (tick 5) and member 6 (tick 8) are eligible, so LRU must pick member 5.
    res = da.hibernate_lru(pool)
    ensure(res.outcome == da.LadderOutcome.HIBERNATED, f"expected hibernation, got {res}")
    ensure(res.victim_id == 5, f"expected LRU eligible victim 5, got {res.victim_id}")
    ensure(res.state.quarantined_bytes == pool.quarantined_bytes + 96,
           "reclaimed bytes bypassed reuse barrier")
    ensure(res.state.free_bytes == 0, "free bytes grew ahead of reuse barrier")
    ensure(res.state.fixed_tier_bytes == 2048 and res.state.other_domain_bytes == 512,
           "external domains touched by hibernation")

    # Next hibernation picks member 6 (tick 8), never focused member 0 (tick 0).
    res2 = da.hibernate_lru(res.state)
    ensure(res2.outcome == da.LadderOutcome.HIBERNATED and res2.victim_id == 6,
           f"expected victim 6, got {res2}")

    # Now only focused (0) and protected/uncheckpointable (1..4) remain -> ceiling refusal.
    res3 = da.hibernate_lru(res2.state)
    ensure(res3.outcome == da.LadderOutcome.REFUSE_AT_CEILING,
           f"expected ceiling refusal, got {res3}")
    ensure(res3.state == res2.state, "ceiling refusal mutated pool state")


def pool_exhaustion_ladder_campaign_and_ceiling() -> None:
    pool = da.demo_pool_state()
    # Requesting 16 bytes triggers: refuse request -> shed local (72 bytes) -> still in quarantine
    # -> hibernate 5 -> hibernate 6 -> ceiling refusal (since reuse barrier has not run).
    steps = da.run_exhaustion_campaign(pool, member_id=0, req_bytes=16)
    outcomes = [s.outcome for s in steps]
    ensure(outcomes[0] == da.LadderOutcome.REFUSE_REQUEST, f"expected initial refusal, {outcomes}")
    ensure(outcomes[1] == da.LadderOutcome.SHED_LOCAL, f"expected local shed, {outcomes}")
    ensure(outcomes[-1] == da.LadderOutcome.REFUSE_AT_CEILING,
           f"expected ceiling refusal before barrier, {outcomes}")
    for s in steps:
        ensure(s.state.fixed_tier_bytes == 2048 and s.state.other_domain_bytes == 512,
               "exhaustion campaign modified external domains")

    ceiling = da.demo_ceiling_pool_state()
    c_steps = da.run_exhaustion_campaign(ceiling, member_id=0, req_bytes=8)
    ensure(
        [s.outcome for s in c_steps]
        == [da.LadderOutcome.REFUSE_REQUEST, da.LadderOutcome.REFUSE_AT_CEILING],
        f"unexpected ceiling campaign {c_steps}",
    )


def desktop_roster_8_members_build_and_bounds() -> None:
    dom = da.demo_domain_spec()
    base = da.base_slot_geometry()
    ensure(len(dom.members) >= 8, "expected >= 8 live members")
    ensure(any(m.is_build for m in dom.members), "expected build member")

    res = da.admit_domain(dom, base)
    ensure(res.admitted, f"expected baseline admission, got {res.errors}")
    ensure(res.boundary_need == 4, f"expected boundary_need 4, got {res.boundary_need}")
    ensure(res.focus_dispatch_cycles == 124, f"expected 124 cycles, got {res.focus_dispatch_cycles}")
    ensure(res.focus_dispatch_ms == Fraction(124, 10), f"bad dispatch ms {res.focus_dispatch_ms}")
    ensure(res.input_to_response_ms == Fraction(300, 10),
           f"bad response ms {res.input_to_response_ms}")
    ensure(res.focus_dispatch_ms <= Fraction(167, 10), "exceeds 16.7 ms gate")
    ensure(res.input_to_response_ms <= Fraction(667, 10), "exceeds 66.7 ms gate")

    # Reject roster with < 8 members or without build member.
    small_dom = replace(dom, members=dom.members[:7])
    _refused(lambda: da.admit_domain(small_dom, base), ">= 8 members")
    no_build_dom = replace(
        dom, members=tuple(replace(m, is_build=False) for m in dom.members)
    )
    _refused(lambda: da.admit_domain(no_build_dom, base), "build member")


def minimum_share_and_eevdf_exact_accounting() -> None:
    dom = da.demo_domain_spec()
    two = da.two_slot_geometry()
    res = da.admit_domain(dom, two)
    # Member 2 has weight 1, worst total weight 19, domain net share 110/200, step eff 4/5 -> 11/475.
    ensure(res.member_net_shares[2] == Fraction(11, 475),
           f"unexpected member 2 net share {res.member_net_shares[2]}")
    ensure(res.member_net_shares[2] >= Fraction(1, 50), "member 2 below min share")

    # Raising member 2's declared min_share above 11/475 fails admission.
    demanding = replace(
        dom,
        members=tuple(
            replace(m, min_share=Fraction(1, 40)) if m.id == 2 else m for m in dom.members
        ),
    )
    _refused(lambda: da.admit_domain(demanding, two), "R-07-037g: member 2 net share")


def slot_geometry_two_slot_accepted() -> None:
    dom = da.demo_domain_spec()
    base = da.base_slot_geometry()
    two = da.two_slot_geometry()
    comp = da.admit_slot_geometry_candidate(dom, base, two)
    ensure(comp.accepted, f"expected acceptance, got {comp.reasons}")
    ensure(comp.baseline.total_domain_width == comp.candidate.total_domain_width == 120,
           "domain share not preserved")
    ensure(comp.candidate.max_slot_gap == 40 < comp.baseline.max_slot_gap == 80,
           "max slot gap did not halve")
    ensure(comp.candidate.focus_dispatch_ms == Fraction(84, 10)
           < comp.baseline.focus_dispatch_ms == Fraction(124, 10),
           "focus dispatch did not improve")
    ensure(comp.candidate.input_to_response_ms == Fraction(260, 10)
           < comp.baseline.input_to_response_ms == Fraction(300, 10),
           "input-to-response did not improve")


def slot_geometry_shorter_visit_period_and_invariant_refutations() -> None:
    dom = da.demo_domain_spec()
    base = da.base_slot_geometry()
    frag = da.fragmented_15slot_geometry()

    comp = da.compare_slot_geometries(dom, base, frag)
    ensure(not comp.accepted, "fragmented 15-slot candidate unexpectedly accepted")
    ensure(comp.candidate.total_domain_width == comp.baseline.total_domain_width == 120,
           "expected identical share in fragmented refutation")
    ensure(comp.candidate.total_usable_cycles == 45 < base.admitted_member_service_floor,
           f"expected collapsed usable cycles, got {comp.candidate.total_usable_cycles}")
    ensure(comp.candidate.focus_dispatch_ms == Fraction(117, 5) > Fraction(167, 10),
           f"expected dispatch > 16.7 ms, got {comp.candidate.focus_dispatch_ms}")
    _refused(
        lambda: da.admit_slot_geometry_candidate(dom, base, frag),
        "usable domain cycles 45 < admitted floor 100",
    )

    # Peer service bound weakened -> refused.
    weak_peer = replace(da.two_slot_geometry(), peer_service_floor=50)
    _refused(
        lambda: da.admit_slot_geometry_candidate(dom, base, weak_peer),
        "peer service bound weakened",
    )

    # Admitted peak memory increased -> refused.
    bloated_mem = replace(da.two_slot_geometry(), peak_memory_bytes=1280)
    _refused(
        lambda: da.admit_slot_geometry_candidate(dom, base, bloated_mem),
        "admitted peak memory increased",
    )

    # Shortest slot < min_usable_slot_width -> refused.
    too_short = replace(
        base,
        domain_slots=tuple(da.SlotWindow(i * 10, 5) for i in range(20)),
    )
    _refused(lambda: da.admit_domain(dom, too_short), "min_usable_slot_width")


def desktop_admission_proof_surface() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "proofs" / "DesktopAdmission.v").read_text(encoding="utf-8")
    for token in (
        "(* SPDX-License-Identifier: Apache-2.0 *)",
        "(*| BEGIN derived: cited entries |*)",
        "(*| END derived |*)",
        "Require ProofSupport.",
        "witness_PoolMember",
        "witness_PoolState",
        "witness_LadderResult",
        "witness_MemberSpec",
        "witness_DomainSpec",
        "witness_SlotWindow",
        "witness_SlotGeometry",
        "witness_GeometryComparison",
        "launch_reserves_floor",
        "exhausted_floor_launch_refused",
        "focused_and_protected_flags_prevent_hibernation",
        "pick_lru_victim_selects_least_recently_focused",
        "reuse_barrier_blocks_premature_reuse_and_restores_on_clear",
        "ceiling_refuses_cleanly",
        "ladder_preserves_external_domains",
        "eevdf_interference_monotone_in_live_set",
        "minimum_share_preserved_under_all_admissible_loads",
        "admitted_desktop_meets_16_7ms_and_66_7ms_with_8_members_and_build",
        "slot_geometry_comparison_iff",
        "demo_baseline_and_two_slot_admitted",
        "refute_shorter_visit_period_candidate",
        "refute_focused_member_eviction_picks_lru_eligible_background",
        "refute_exhausted_floor_launch",
    ):
        ensure(token in text, f"DesktopAdmission.v missing expected declaration {token!r}")
    for forbidden in (
        r"\bAdmitted\b",
        r"\bAxiom\b",
        r"\bParameter\b",
        r"\bCoInductive\b",
        r"\bCoFixpoint\b",
        r"\bcofix\b",
        r"\bSection\b",
        r"\bModule\s+Type\b",
    ):
        ensure(not re.search(forbidden, text), f"DesktopAdmission.v matched forbidden {forbidden}")


def cases() -> list[Case]:
    return [
        Case(fn.__name__, fn)
        for fn in (
            pool_floor_reservation_and_exhausted_launch,
            pool_focused_protection_and_lru_hibernation,
            pool_exhaustion_ladder_campaign_and_ceiling,
            desktop_roster_8_members_build_and_bounds,
            minimum_share_and_eevdf_exact_accounting,
            slot_geometry_two_slot_accepted,
            slot_geometry_shorter_visit_period_and_invariant_refutations,
            desktop_admission_proof_surface,
        )
    ]
