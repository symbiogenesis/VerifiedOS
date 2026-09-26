# SPDX-License-Identifier: Apache-2.0
"""Pool allocation, heap lifetime, exact bounds and quarantine controls."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from tests.harness import Case, ensure
from vos import elastic_pool as p
from vos import elastic_pool_campaign
from vos import revocation as rev


def refused(call: Callable[[], object], reason: str) -> None:
    try:
        call()
    except (p.PoolError, rev.RevocationError) as exc:
        ensure(reason in str(exc), f"wrong refusal: {exc}")
    else:
        raise AssertionError(f"accepted without {reason}")


def reclaimed(pool: p.Pool, grant: p.Grant) -> None:
    pool.release(grant)
    pool.clear_registers(grant.slot)
    pool.barrier()
    pool.sweep_begin()
    pool.sweep_end()


def composition_exactness_and_allowance() -> None:
    for size, alignment, expected in ((127, 1, True), (128, 2, True),
                                      (129, 2, False), (192, 1, False),
                                      (192, 2, True), (384, 4, True),
                                      (512, 8, True), (1024, 16, True)):
        ensure(p.SizeClass(size, alignment).exact() == expected,
               f"wrong exactness at {size}/{alignment}")
    plan = p.fixture().plan
    refused(lambda: p.Pool(replace(plan, quarantine_allowance=63)), "allowance")
    refused(lambda: p.Pool(replace(plan, slots=((64, 0), (64, 0)))), "overlap")
    refused(lambda: p.Pool(replace(plan, slots=((65, 0),))), "unaligned")
    refused(lambda: p.Pool(replace(plan, classes=(p.SizeClass(129, 2),),
                                  quarantine_allowance=1000)),
            "representable")


def exhaustion_zeroing_and_stale_handles() -> None:
    pool = p.fixture()
    first = pool.allocate(1, 0, 0)
    second = pool.allocate(2, 0, 0)
    refused(lambda: pool.allocate(3, 0, 0), "exhausted")
    ensure(pool.allocate(3, 1, 0).length == 32, "exhaustion leaked across classes")
    pool.write(first, 0, 255)
    pool.release(first)
    refused(lambda: pool.allocate(3, 0, 0), "exhausted")
    refused(lambda: pool.write(first, 0, 1), "stale")
    refused(lambda: pool.release(first), "stale")
    pool.clear_registers(first.slot)
    pool.barrier()
    pool.sweep_begin()
    refused(lambda: pool.allocate(3, 0, 0), "exhausted")
    pool.sweep_end()
    new = pool.allocate(3, 0, 0)
    ensure(new.base == first.base and new.serial > first.serial,
           "reuse lost allocation identity")
    ensure(pool.memory[new.base] == 0, "previous tenant bytes leaked")
    refused(lambda: pool.write(first, 0, 1), "stale")
    pool.live(second)
    ensure(not p.history_errors(pool.plan, pool.history), "reuse history failed")


def release_during_sweep_waits_for_next_pass() -> None:
    pool = p.fixture()
    first = pool.allocate(1, 0, 0)
    second = pool.allocate(2, 0, 0)
    pool.release(first)
    pool.clear_registers(first.slot)
    pool.barrier()
    pool.sweep_begin()
    pool.release(second)
    pool.clear_registers(second.slot)
    pool.barrier()
    pool.sweep_end()
    ensure(pool.slots[second.slot].phase == "barrier", "release joined old pass")
    pool.allocate(3, 0, 0)
    refused(lambda: pool.allocate(4, 0, 0), "exhausted")
    pool.sweep_begin()
    pool.sweep_end()
    ensure(pool.allocate(4, 0, 0).base == second.base, "next pass did not reclaim")
    ensure(not p.history_errors(pool.plan, pool.history), "sweep ordering failed")


def stale_register_blocks_the_semantic_barrier() -> None:
    pool = p.fixture()
    grants = [pool.allocate(i, 0, 0) for i in (1, 2)]
    for grant in grants:
        pool.release(grant)
    pool.clear_registers(grants[0].slot)
    before = pool.history.copy()
    refused(lambda: pool.clear_registers(-1), "index")
    refused(lambda: pool.clear_registers(len(pool.slots)), "index")
    refused(pool.barrier, "authority:register")
    ensure(pool.history == before and all(s.phase == "pending" for s in pool.slots[:2]),
           "failed barrier partially committed")
    pool.clear_registers(grants[1].slot)
    pool.barrier()
    ensure(pool.epoch == 2, "retirement counter reset across chunks")


def island_and_issuer_separation() -> None:
    local = p.fixture()
    remote = p.Pool(replace(local.plan, island=1, base=128,
                            slots=((128, 0), (144, 0), (160, 1))))
    domain = p.DomainPools({(0, 0): local, (1, 0): remote}, {1: 0, 2: 1})
    before = remote.history.copy()
    grant = domain.allocate(1, 0, 0)
    ensure(remote.history == before, "local allocation changed remote pool")
    refused(lambda: domain.allocate(9, 0, 0), "launch")
    refused(lambda: local.allocate(1, 0, 1), "island")
    other = p.fixture()
    other.allocate(1, 0, 0)
    refused(lambda: other.release(grant), "issuer")
    refused(lambda: p.DomainPools({(0, 0): local}, {1: 0, 2: 1}), "missing")


def independently_revocable_slots_do_not_share_a_bit() -> None:
    unsafe = p.Plan(0, 0, 64, 8, (p.SizeClass(4, 4),), ((64, 0), (68, 0)), 8)
    # This is an architectural negative control: publication for bytes 64..67
    # clears a live capability based at 68, even though the allocations share
    # no byte. Plan admission must reject that layout before any grant.
    neighbor = rev.Capability(68, 72, retired=False)
    ensure(not rev.load(neighbor, frozenset({(0, 64 // rev.GRANULE)})).tag,
           "negative control lost the shared-granule interference")
    refused(lambda: p.Pool(unsafe), "revocation granule")
    single = p.Pool(replace(unsafe, slots=((64, 0),)))
    ensure(single.allocate(1, 0, 0).length == 4, "small exact class was banned")

    safe = p.Pool(replace(unsafe, span=16, slots=((64, 0), (72, 0))))
    first, second = safe.allocate(1, 0, 0), safe.allocate(2, 0, 0)
    safe.release(first)
    state = safe.slots[first.slot].retirement
    ensure(state is not None, "release failed to publish")
    if state is None:
        return
    neighbor = rev.Capability(second.base, second.base + second.length, retired=False)
    ensure(rev.load(neighbor, state.bits).tag, "retiring one slot revoked its live sibling")
    safe.write(second, 0, 42)
    safe.clear_registers(first.slot)
    safe.barrier()
    safe.sweep_begin()
    safe.sweep_end()
    safe.allocate(3, 0, 0)
    safe.live(second)
    ensure(safe.memory[second.base] == 42, "reusing one slot changed its live sibling")


def physical_pool_extents_are_disjoint() -> None:
    local = p.fixture()
    same_address = p.Pool(replace(local.plan, island=1))
    refused(lambda: p.DomainPools({(0, 0): local, (1, 0): same_address}, {1: 0, 2: 1}),
            "physical pool extents overlap")
    other_class = p.Pool(replace(local.plan, memory_class=1))
    refused(lambda: p.DomainPools({(0, 0): local, (0, 1): other_class}, {1: 0}),
            "physical pool extents overlap")
    # Allocatable slots do not overlap, but the second pool's owned leading
    # gap does. Pool roots reserve their entire composition-fixed extents.
    gap = p.Pool(replace(local.plan, island=1, base=120, span=72,
                         slots=((128, 0), (144, 0), (160, 1))))
    refused(lambda: p.DomainPools({(0, 0): local, (1, 0): gap}, {1: 0, 2: 1}),
            "physical pool extents overlap")


def heap_narrowing_and_lifetime_are_exclusive() -> None:
    pool = p.fixture()
    root = pool.allocate(1, 1, 0)
    classes = (p.SizeClass(8, 8),)
    layout = ((root.base, 0), (root.base + 8, 0))
    heap = pool.heap(root, classes, layout)
    refused(lambda: pool.heap(root, classes, layout), "already")
    first = heap.allocate(1, 0, 0)
    ensure(first.length == 8 and first.length < root.length, "chunk-wide heap grant")
    heap.write(first, 0, 83)
    ensure(pool.memory[first.base] == 83 and heap.memory is pool.memory,
           "heap did not share parent backing bytes")
    refused(lambda: pool.write(root, 0, 2), "owned by its heap")
    grandchild = heap.heap(first, (p.SizeClass(4, 4),), ((first.base, 0),))
    grandchild.allocate(1, 0, 0)
    reclaimed(heap, first)
    refused(lambda: grandchild.allocate(1, 0, 0), "stale")
    heap.allocate(1, 0, 0)
    reclaimed(pool, root)
    refused(lambda: heap.allocate(1, 0, 0), "stale")
    ensure(not p.history_errors(heap.plan, heap.history), "heap reuse failed")


def bounded_sequences_satisfy_the_four_observers() -> None:
    histories = p.generated_histories(4)
    ensure(len(histories) == 7 ** 4, "generator omitted a command word")
    for history in histories:
        ensure(not p.history_errors(p.fixture().plan, history),
               f"generated history violated its contract: {history}")


def each_named_refutation_is_detected() -> None:
    pool = p.fixture()
    grant = pool.allocate(1, 0, 0)
    pool.write(grant, 0, 7)
    reclaimed(pool, grant)
    pool.allocate(2, 0, 0)
    good = pool.history
    ensure(not p.history_errors(pool.plan, good), "baseline rejected")
    overlap = [*good[:2], ("Grant", (2, 0, 64, 64, 16))]
    wide = good.copy()
    wide[1] = ("Grant", (1, 0, 64, 64, 32))
    unzeroed = good[:-2] + good[-1:]
    early = [event for event in good if event[0] != "SweepEnd"]
    presweep = good.copy()
    presweep[4], presweep[5] = presweep[5], presweep[4]
    for history, error in ((overlap, "overlap"), (wide, "bounds"),
                           (unzeroed, "zero"), (early, "reuse"), (presweep, "reuse")):
        ensure(p.history_errors(pool.plan, history) == frozenset({error}),
               f"refutation did not isolate {error}")


def no_counter_wrap() -> None:
    pool = p.fixture()
    grant = pool.allocate(1, 0, 0)
    pool.epoch = rev.MAX_EPOCH
    refused(lambda: pool.release(grant), "epoch exhaustion")
    pool.live(grant)
    pool.serial = rev.MAX_EPOCH
    refused(lambda: pool.allocate(2, 0, 0), "identity exhausted")


def generated_gallina_is_current() -> None:
    artifact = Path(__file__).resolve().parents[2] / "proofs/ElasticPoolCampaign.v"
    ensure(artifact.read_text(encoding="utf-8") == elastic_pool_campaign.render(),
           "regenerate ElasticPoolCampaign.v from vos.elastic_pool_campaign.render")


def cases() -> list[Case]:
    return [Case(fn.__name__, fn) for fn in (
        composition_exactness_and_allowance,
        exhaustion_zeroing_and_stale_handles,
        release_during_sweep_waits_for_next_pass,
        stale_register_blocks_the_semantic_barrier,
        island_and_issuer_separation,
        independently_revocable_slots_do_not_share_a_bit,
        physical_pool_extents_are_disjoint,
        heap_narrowing_and_lifetime_are_exclusive,
        bounded_sequences_satisfy_the_four_observers,
        each_named_refutation_is_detected,
        no_counter_wrap,
        generated_gallina_is_current,
    )]
