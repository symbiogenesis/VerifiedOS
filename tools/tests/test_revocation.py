# SPDX-License-Identifier: Apache-2.0
"""Adversarial authority observations and schedule boundaries for Q22a."""

from collections.abc import Callable
from dataclasses import replace

from tests.harness import Case, ensure
from vos import revocation as r


def refused(fn: Callable[[], object], reason: str) -> None:
    try:
        fn()
    except r.RevocationError as exc:
        ensure(reason in str(exc), f"wrong refusal: {exc}")
    else:
        raise AssertionError(f"accepted without {reason}")


def mark_does_not_revalidate_resident_authority() -> None:
    comp, initial = r.fixture()
    state = r.publish(comp, initial)
    cap = initial.holders[0].cap
    ensure(r.dereference(cap, 64), "mark silently revalidated a resident capability")
    ensure(not r.load(cap, state.bits).tag, "reload escaped the bitmap")
    refused(lambda: r.complete(comp, state), "authority:register")


def narrowing_changes_the_base_key() -> None:
    cap = r.Capability(72, 88)
    ensure(r.load(cap, frozenset({(0, 8)})).tag, "original-base mark killed an interior base")
    ensure(not r.load(cap, frozenset({(0, 9)})).tag, "interior base ignored its own bit")
    # The annotation cannot act as an architectural generation/colour check.
    ensure(r.load(replace(cap, retired=False), frozenset({(0, 9)})).tag is False,
           "load consulted ghost retirement state")


def foreign_bitmap_cannot_filter_a_local_load() -> None:
    cap = r.Capability(64, 72, island=1)
    bits = frozenset({(1, 8)})
    ensure(r.load(cap, bits, 0).tag, "loader reached a foreign bitmap")
    ensure(not r.load(cap, bits, 1).tag, "owner island did not filter its own base")
    comp, initial = r.fixture()
    state = r.ready(comp, initial)
    old = next(h for h in state.holders if h.name == "saved")
    bad = r.replace_holder(state, "saved", replace(old, cap=cap))
    refused(lambda: r.complete(comp, bad), "loading-island")
    ensure("saved" in r.exposed(bad), "foreign load was silently filtered")


def saved_and_outside_copies_block_reuse() -> None:
    comp, initial = r.fixture()
    complete = r.complete(comp, r.ready(comp, initial))
    ensure(not r.exposed(complete), "filtered storage is usable after the barrier")
    refused(lambda: r.reuse(comp, complete), "reuse-resurrection")
    state = r.reclaimed(comp, initial)
    ensure(not r.reuse_errors(comp, state), "a completed pass cannot reuse")
    for name in ("saved", "outside-interval-copy"):
        old = next(h for h in initial.holders if h.name == name)
        bad = r.replace_holder(state, name, old)
        ensure(not r.exposed(bad), "marked stale storage should remain un-loadable")
        refused(lambda bad=bad: r.reuse(comp, bad), "reuse-resurrection")
        resurrected = replace(bad, bits=frozenset())
        ensure(name in r.exposed(resurrected), "the witness did not actually resurrect")


def loan_is_not_revoked_by_the_slot_bit() -> None:
    comp, initial = r.fixture()
    state = r.publish(comp, initial)
    callee = next(h for h in state.holders if h.name == "callee")
    ensure(r.load(callee.cap, state.bits).tag, "slot mark revoked the shared object")
    state = r.cancel_loan(state, "call")
    ensure(all(not h.cap.tag for h in state.holders if h.cap.loan == "call"),
           "cancellation left a borrowed copy")
    other = next(h for h in state.holders if h.name == "unrelated-grant")
    ensure(other.cap.tag, "cancelling a loan revoked an unrelated grant")


def acknowledgement_is_evidence_not_a_timer() -> None:
    comp, initial = r.fixture()
    state = r.publish(comp, initial)
    refused(lambda: r.acknowledge(comp, state, 1), "local postcondition")
    failed = r.acknowledgement_timeout(state)
    # Even cleaning everything up and delivering a late ACK cannot turn this
    # terminated attempt into a completed event.
    for core in comp.cores:
        failed = r.clear_core(failed, core)
    failed = r.cancel_loan(failed, "call")
    failed = r.finish_device(failed)
    failed = r.acknowledge(comp, failed, 1)
    refused(lambda: r.complete(comp, failed), "acknowledgement-failure")
    refused(lambda: r.reuse(comp, failed), "acknowledgement-failure")
    ensure(failed.bits == comp.targets, "timeout cleared quarantine marks")


def missing_holder_is_not_an_empty_proof() -> None:
    comp, initial = r.fixture()
    state = r.ready(comp, initial)
    missing = replace(state, holders=state.holders[1:])
    refused(lambda: r.complete(comp, missing), "holder-map")
    omitted = replace(comp, swept=comp.swept - {"outside-interval-copy"})
    refused(lambda: r.complete(omitted, state), "sweep-map")


def counterexamples_all_have_a_deciding_refusal() -> None:
    examples = r.counterexamples()
    for prefix in ("resident-register", "saved-context", "narrowed-capability",
                   "callee-loan", "remote-delegate", "reuse-resurrection", "device-transfer"):
        selected = [(name, why) for name, why in examples if name.startswith(prefix)]
        ensure(bool(selected), f"no generated {prefix} witness")
        ensure(all(why for _, why in selected), f"an accepted {prefix} witness")


def all_generated_cleanup_orders_reach_safe_reuse() -> None:
    count, errors = r.interleavings()
    ensure(count == 3 * 120 and not errors, f"incomplete or failing enumeration: {count}/{errors}")


def deadlines_and_sweep_service_are_separate() -> None:
    holders = tuple(r.Holder(f"s{i}", "memory", 0, r.Capability(64, 72)) for i in range(7))
    names = frozenset(h.name for h in holders)
    comp = r.Composition(names, names, frozenset({(0, 8)}), frozenset({0}), frozenset())
    initial = r.State(holders, loans=frozenset(), pending_proxies=frozenset())
    base = r.Budget((r.Job(10, 3, 2),), (r.Job(20, 5, 4),), (), (),
                    (r.Job(16, 4, 4),), 40, 12, 3, 7)
    bound = base.bounds(comp, initial)
    ensure(bound["bitmap_mark"] == 12 and bound["semantic_completion"] == 56,
           f"publication and barrier costs were conflated: {bound}")
    ensure(bound["post_barrier_sweep"] == 132 and bound["set_to_reuse"] == 188,
           f"preemption reserve or post-barrier pass was omitted: {bound}")
    more = tuple(r.Holder(f"s{i}", "memory", 0, r.Capability(64, 72)) for i in range(100))
    more_names = frozenset(h.name for h in more)
    larger = replace(base, groups=100).bounds(
        replace(comp, holders=more_names, swept=more_names), replace(initial, holders=more))
    ensure(larger["semantic_completion"] == bound["semantic_completion"]
           and larger["post_barrier_sweep"] > bound["post_barrier_sweep"],
           "containment depends on sweep footprint")
    refused(lambda: replace(base, sweep_width=3).bounds(comp, initial), "completed group")
    refused(lambda: r.Job(10, 3, 4).bound(), "admitted finite slot")
    refused(lambda: replace(base, devices=()).bounds(comp, initial), "device service inventory")
    full_comp, full = r.fixture()
    budget = r.Budget((r.Job(10, 4, 2),) * 2, (r.Job(20, 8, 4),) * 2,
                      (r.Job(20, 6, 4),), (r.Job(30, 5, 3),) * 2,
                      (r.Job(16, 4, 4),), 40, 12, 3, len(full_comp.swept))
    for name in ("publication", "barriers", "cancellations", "proxy_edges", "devices"):
        missing = replace(budget, **{name: ()})
        refused(lambda missing=missing: missing.bounds(full_comp, full), "service inventory")


def no_epoch_wrap_or_pre_barrier_reclamation() -> None:
    comp, state = r.fixture()
    refused(lambda: r.publish(comp, replace(state, epoch=r.MAX_EPOCH)), "epoch exhaustion")
    refused(lambda: r.start_sweep(comp, r.ready(comp, state)), "semantic completion")
    final = r.reclaimed(comp, state)
    refused(lambda: r.reuse(comp, replace(final, sweep_started=final.barrier)),
            "post-barrier-full-pass")


def cases() -> list[Case]:
    return [Case(fn.__name__, fn) for fn in (
        mark_does_not_revalidate_resident_authority,
        narrowing_changes_the_base_key,
        foreign_bitmap_cannot_filter_a_local_load,
        saved_and_outside_copies_block_reuse,
        loan_is_not_revoked_by_the_slot_bit,
        acknowledgement_is_evidence_not_a_timer,
        missing_holder_is_not_an_empty_proof,
        counterexamples_all_have_a_deciding_refusal,
        all_generated_cleanup_orders_reach_safe_reuse,
        deadlines_and_sweep_service_are_separate,
        no_epoch_wrap_or_pre_barrier_reclamation,
    )]
