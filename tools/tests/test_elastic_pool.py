# SPDX-License-Identifier: Apache-2.0
"""Pool allocation, heap lifetime, exact bounds and quarantine controls."""

from collections.abc import Callable, MutableMapping
from dataclasses import FrozenInstanceError, replace
from itertools import product
from operator import setitem
from pathlib import Path
from typing import cast

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


def composition_numeric_operands_are_naturals() -> None:
    plan = p.fixture().plan
    for name in ("island", "memory_class", "base", "span", "quarantine_allowance"):
        value = getattr(plan, name)
        for invalid in (float(value), False, -1, "0"):
            refused(lambda name=name, invalid=invalid: p.Pool(replace(plan, **{name: invalid})), "shape")
    for base, cls in ((64.0, 0), (64, 0.0), (True, 0), (64, False), (64, -1)):
        refused(lambda base=base, cls=cls: p.Pool(replace(plan, slots=((base, cls),))), "shape")
    for length, alignment in ((16.0, 16), (16, 16.0), (True, 1), (1, True)):
        kind = p.SizeClass(cast(int, length), cast(int, alignment))
        ensure(not kind.exact(), "non-integer class claimed exact bounds")
        refused(lambda kind=kind: p.Pool(replace(plan, classes=(kind,), slots=((64, 0),))),
                "representable")
    pool = p.fixture()
    for invalid in (0.0, False, -1):
        ident = cast(int, invalid)
        refused(lambda ident=ident: p.DomainPools({(ident, 0): pool}, {0: 0}), "identifiers")
        refused(lambda ident=ident: p.DomainPools({(0, ident): pool}, {0: 0}), "identifiers")
        refused(lambda ident=ident: p.DomainPools({(0, 0): pool}, {ident: 0}), "identifiers")
        refused(lambda ident=ident: p.DomainPools({(0, 0): pool}, {0: ident}), "identifiers")
    # Zero is a legitimate natural identity, class and launch island.
    ensure(p.DomainPools({(0, 0): pool}, {0: 0}).allocate(0, 0, 0).holder == 0,
           "exact-integer admission excluded a zero identity")


def malformed_allocation_preserves_the_pool_state() -> None:
    pool = p.fixture()
    domain = p.DomainPools({(0, 0): pool}, {0: 0, 1: 0})
    before = (pool.serial, pool.epoch, pool.history.copy(), pool.memory.copy(),
              [(slot.phase, slot.grant) for slot in pool.slots])
    for field in range(3):
        for invalid in (0.0, 1.5, False, True, -1, "0", float("nan")):
            operands = [1, 0, 0]
            operands[field] = cast(int, invalid)
            refused(lambda operands=operands: pool.allocate(*operands), "nonnegative integers")
            after = (pool.serial, pool.epoch, pool.history, pool.memory,
                     [(slot.phase, slot.grant) for slot in pool.slots])
            ensure(after == before, "malformed allocation changed serial, bytes or ownership")
            refused(lambda operands=operands: domain.allocate(*operands), "nonnegative integers")
            after = (pool.serial, pool.epoch, pool.history, pool.memory,
                     [(slot.phase, slot.grant) for slot in pool.slots])
            ensure(after == before, "numeric domain alias changed the pool state")
    grant = pool.allocate(0, 0, 0)
    ensure(grant.serial == 1 and grant.slot == 0 and not p.history_errors(pool.plan, pool.history),
           "refused allocation consumed the next valid allocation identity")


def numeric_handle_and_write_aliases_are_refused() -> None:
    pool = p.fixture()
    grant = pool.allocate(0, 0, 0)
    before = (pool.epoch, pool.history.copy(), pool.memory.copy())
    for name in ("holder", "slot", "base", "length", "serial"):
        alias = replace(grant, **{name: float(getattr(grant, name))})
        # Numeric equality alone would admit these forged record fields.
        ensure(alias == grant, "numeric alias stopped testing dataclass equality")
        refused(lambda alias=alias: pool.live(alias), "nonnegative integers")
        refused(lambda alias=alias: pool.write(alias, 0, 7), "nonnegative integers")
        refused(lambda alias=alias: pool.release(alias), "nonnegative integers")
    for name in ("holder", "slot", "serial"):
        alias = replace(grant, **{name: bool(getattr(grant, name))})
        ensure(alias == grant, "boolean alias stopped testing dataclass equality")
        refused(lambda alias=alias: pool.release(alias), "nonnegative integers")
    for offset, value in ((0.0, 7), (False, 7), (0, 7.0), (0, True)):
        refused(lambda offset=offset, value=value:
                pool.write(grant, cast(int, offset), cast(int, value)), "byte range")
    ensure((pool.epoch, pool.history, pool.memory) == before,
           "invalid handle or byte operand changed the live allocation")
    pool.live(grant)
    pool.write(grant, 0, 0)
    pool.release(grant)
    state = pool.slots[grant.slot].retirement
    for invalid in (0.0, False, "0"):
        refused(lambda invalid=invalid: pool.clear_registers(cast(int, invalid)), "index")
        ensure(pool.slots[grant.slot].retirement == state,
               "numeric slot alias cleared a retained register")
    pool.clear_registers(0)
    pool.barrier()
    pool.sweep_begin()
    pool.sweep_end()
    ensure(not p.history_errors(pool.plan, pool.history), "valid integer retirement failed")


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


def domain_admission_owns_fixed_composition_bindings() -> None:
    local = p.fixture()
    remote = p.Pool(replace(local.plan, island=1, base=128,
                            slots=((128, 0), (144, 0), (160, 1))))
    pools = {(0, 0): local, (1, 0): remote}
    launches = {1: 0, 2: 1}
    domain = p.DomainPools(pools, launches)
    first = domain.allocate(1, 0, 0)
    overlapping = p.Pool(replace(local.plan, island=1))
    # Input maps belong to the caller. Replacing an admitted arena must not
    # manufacture a second live grant over the first arena's physical bytes.
    pools[1, 0] = overlapping
    launches[1] = 1
    second = domain.allocate(2, 0, 0)
    third = domain.allocate(1, 0, 0)
    ensure(first.base == 64 and second.base == 128 and third.base == 80,
           "caller map mutation redirected an admitted allocation")
    ensure(not overlapping.history, "unadmitted replacement arena was used")
    pools.clear()
    launches.clear()
    ensure(domain.pools[0, 0] is local and domain.pools[1, 0] is remote
           and dict(domain.launch_islands) == {1: 0, 2: 1},
           "caller map removal changed the admitted composition")

    # Deliberately try mutable interfaces against the public read-only views.
    edits: tuple[Callable[[], object], ...] = (
        lambda: setitem(cast(MutableMapping[tuple[int, int], p.Pool], domain.pools),
                        (1, 0), overlapping),
        lambda: setitem(cast(MutableMapping[int, int], domain.launch_islands), 1, 1),
    )
    for edit in edits:
        try:
            edit()
        except TypeError:
            pass
        else:
            raise AssertionError("admitted mapping accepted a new binding")
    for name, replacement in (("pools", {(1, 0): overlapping}),
                              ("launch_islands", {1: 1})):
        try:
            setattr(domain, name, replacement)
        except FrozenInstanceError:
            pass
        else:
            raise AssertionError(f"admitted composition allowed {name} rebinding")

    # Freezing the bindings must preserve the service's ordinary mutable state.
    local.write(first, 0, 77)
    reclaimed(local, first)
    reused = domain.allocate(1, 0, 0)
    ensure(reused.base == first.base and reused.serial > first.serial
           and local.memory[reused.base] == 0,
           "fixed composition bindings prevented zeroed runtime reuse")
    remote.live(second)
    ensure(not p.history_errors(local.plan, local.history)
           and not p.history_errors(remote.plan, remote.history),
           "fixed-composition control failed the history contract")


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
    small = p.Pool(p.Plan(0, 0, 64, 4, (p.SizeClass(4, 4),), ((64, 0),), 4))
    adjacent = p.Pool(replace(small.plan, memory_class=1, base=68, slots=((68, 0),)))
    refused(lambda: p.DomainPools({(0, 0): small, (0, 1): adjacent}, {1: 0}),
            "revocation granule")
    separated = p.Pool(replace(adjacent.plan, base=72, slots=((72, 0),)))
    domain = p.DomainPools({(0, 0): small, (0, 1): separated}, {1: 0})
    first, second = domain.allocate(1, 0, 0), domain.allocate(1, 1, 0)
    small.release(first)
    state = small.slots[first.slot].retirement
    ensure(state is not None, "release failed to publish")
    if state is not None:
        capability = rev.Capability(second.base, second.base + second.length, retired=False)
        ensure(rev.load(capability, state.bits).tag, "retirement crossed a pool boundary")


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


def forked_prefixes_replay_each_word() -> None:
    # The generator runs each prefix once and forks the pool it left; every word's
    # history must still be the one replaying the word on a fresh fixture records, in
    # the words' lexicographic order, refusals included.
    for depth in (0, 1, 4):
        replayed: list[list[p.Event]] = []
        for word in product(range(p.COMMANDS), repeat=depth):
            pool = p.fixture()
            for command in word:
                p.apply_command(pool, command)
            replayed.append(pool.history)
        ensure(p.generated_histories(depth) == replayed,
               f"a forked prefix changed a depth-{depth} history or its order")


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
        composition_numeric_operands_are_naturals,
        malformed_allocation_preserves_the_pool_state,
        numeric_handle_and_write_aliases_are_refused,
        exhaustion_zeroing_and_stale_handles,
        release_during_sweep_waits_for_next_pass,
        stale_register_blocks_the_semantic_barrier,
        island_and_issuer_separation,
        domain_admission_owns_fixed_composition_bindings,
        independently_revocable_slots_do_not_share_a_bit,
        physical_pool_extents_are_disjoint,
        heap_narrowing_and_lifetime_are_exclusive,
        bounded_sequences_satisfy_the_four_observers,
        forked_prefixes_replay_each_word,
        each_named_refutation_is_detected,
        no_counter_wrap,
        generated_gallina_is_current,
    )]
