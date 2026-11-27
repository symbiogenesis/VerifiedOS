# Pool and heap reference

This is the executable reference and Gallina formalization for [Q34c](../../PLAN.md),
under the existing [elastic-domain contract](contracts/elastic-domain.md).
[ElasticPool.v](../../proofs/ElasticPool.v) completes `Q34c-i`'s Gallina proofs
(185 declared checkable symbols all `Closed under the global context` under `Print Assumptions`,
and `rocqchk -silent -o` passing locally on `ElasticPool` and `ElasticPoolCampaign` with
`Axioms: <none>`): universal refinement from the finite 5-phase, two-generation
quarantine metadata state machine (`meta_init`, `meta_step`, `meta_run`) to
`PoolGuarantees`, `HeapNarrows`, and `HeapZeroedAtHandoff` (`HeapGuarantees`) over any
admitted layout, the composition-fixed size-class table and granule-exact narrowed-length
theorems, per-island pool disjointness and launch-island binding, holder-map/revocation-barrier
linking (`LinkedMetaState`), parent/child descendant lifetime invalidation (`NestedHeapState`),
and exhausted-class refusal (`meta_alloc_class`). What `Q34c-ii` retains is realizing the
native C/assembly pool service and default heap library, connecting M4.4/R2's runtime
barrier and sweep implementation, and completing cold Guest CI acceptance.

[elastic_pool.py](../../tools/vos/elastic_pool.py) implements composition-fixed
size classes, fixed disjoint slots, per-island/memory-class pool selection, exact
grants, zeroing, release and reuse. Admission uses the existing
`vos.memplan.representable_granule`; allocation selects a declared class without
runtime rounding. Slot capacity partitions the pool by class. A free larger
class does not satisfy an exhausted smaller class, and no compaction or splitting
changes the admitted layout. The quarantine allowance covers all declared slots.
This deliberately conservative layout establishes no fragmentation or latency
measurement for the desktop workload.

Independently revocable sibling slots also have disjoint eight-byte revocation
granule footprints. Byte-disjoint small allocations cannot share a bitmap bit:
retiring one would clear a stored capability to its still-live neighbor. Small
size classes remain admitted when their placed slots leave the required gaps.
`DomainPools` checks whole arena extents for overlap across all island and memory
class keys, including unused arena gaps, and prevents two arenas sharing a
revocation granule at a byte-disjoint boundary. These are addresses in the platform's
single physical address space, not coordinates local to an island.
The [physical-address contract](../spec.md#r-15-002) and
[ElasticDomain.v](../../proofs/ElasticDomain.v)'s `extents_separate` predicate
own that interpretation; issuer identities cannot make overlapping physical
storage independent.

Plan admission and public allocation, write and retirement indices require exact
integers. Boolean and fractional aliases receive `PoolError` before changing
allocation identities, memory, histories or retirement state.

`DomainPools` snapshots the caller's pool and launch-island maps at admission and
exposes immutable bindings. Mutating or clearing the input maps cannot replace
an admitted arena or redirect a placed member; the public bindings cannot be
edited or rebound. The bound pool objects still carry mutable allocation and
retirement state. Their plans and parent relationships are trusted reference
state, not an adversarial Python object boundary.

The mutable slot phases are `free`, `live`, `pending`, `barrier` and `sweeping`.
Release publishes revocation and enters pending quarantine. A retained register
copy prevents the semantic barrier. Successful barrier completion moves only
pending slots into the barrier generation; a pass snapshots that generation.
Only its snapshot reaches free at pass completion. A release during the pass
waits for another barrier and a later full pass, including when its barrier
completes before the first pass ends. This is the two-generation quarantine
shape: incoming retirements never join the pass already in progress.

The reference reuses [revocation.py](../../tools/vos/revocation.py)'s publication,
register clearing, completion, sweep and reuse decisions. Its explicit local
holder fixture contains a live register, filtered saved context and a stored
copy outside the allocation. The existing revocation qualification owns broader
loan, proxy and device cases. Relating a composition's complete holder map to
compiled code and real registers, memory and devices is the M4.4/R2 join; the
three-holder reference is not evidence that a real domain has only three roots.
The epoch never wraps and its advancement alone cannot complete the barrier.

A chunk has one child heap owner. Child allocation uses the same phase machine
and returns a capability of exactly one child class. Nested heaps share the
parent's backing bytes; direct parent writes to a heap-owned chunk are refused.
Every child operation
validates its parent grant, recursively for descendants. Parent release makes
the old subtree unusable through the reference API, including after the parent's
storage is reallocated. Issuer identities separate pools with identical layouts
and allocation serials. These Python identities model trusted service handles;
they are not capability tags or a proof of adversarial Python object isolation.

Histories are recorded per pool level. A descendant's writes change the shared
backing but are not copied into its ancestors' event lists. The generated Gallina
campaign checks top-level histories; composing all descendant observations and
the real initial backing with those histories remains part of the refinement
join. The finite implementation zeroes each allocation before every grant,
independently of the observer's reconstruction of previous bytes.

[ElasticPool.v](../../proofs/ElasticPool.v) proves that an executable
history-indexed event producer preserves `PoolGuarantees` for every requested
event sequence. It checks only the new event. The prefix proof establishes that
extending a history cannot change a previous grant's disjointness, exact bounds,
handoff bytes or completed reuse gate. Its heap corollary establishes the exact
`HeapNarrows` conjunction. A successful cycle constructs allocation, nonzero
write, release, barrier, sweep and zeroed reuse; rejected witnesses cover overlap,
wide bounds, unzeroed handoff, early reuse and a pass begun before the barrier.

The history producer does not implement the semantic barrier. It consumes the
contract's `BarrierDone`, `SweepBegin` and `SweepEnd` observations. In particular,
its theorem cannot distinguish a falsely reported completion from a real one.
The history-indexed producer also has no bounded runtime memory or cost claim.

To close the metadata-quarantine gap for a single pool level,
[ElasticPool.v](../../proofs/ElasticPool.v) also defines the finite metadata
state machine (`SlotPhase`, `SlotLayout`, `MetaSlot`, `MetaState`, `MetaOp`,
`meta_init`, `meta_step`, `meta_run`) modeling `elastic_pool.py`'s 5-phase,
two-generation quarantine transitions without calling `pool_event`'s history
filter. Under `layout_admitted` (exact size classes, alignment, arena bounds,
and `extents_separate`-shaped pairwise byte-disjointness, which the Python
reference strengthens with 8-byte revocation-granule separation), `meta_init_inv`
and `meta_step_preserves_inv` preserve `meta_inv`, and
`meta_run_refines_pool_guarantees`, `meta_run_refines_heap_narrows`,
`meta_run_refines_heap_zeroed_at_handoff`, and `meta_run_refines_heap_guarantees` prove
universally across all admitted layouts and arbitrary operation lists that the
emitted history satisfies `PoolGuarantees`, `HeapNarrows`, and eager sub-allocation zeroing
(`HeapZeroedAtHandoff`, closing `F-783` alongside `unzeroed_reuse_satisfies_heap_narrows_but_not_zeroed`).
Executable witnesses (`meta_two_gen_quarantine_refuses_early_alloc` and
`meta_two_gen_quarantine_reuses_after_second_sweep`) demonstrate that a slot
released while `ms_sweep_active = true` stays quarantined after `OpBarrier` and
`OpSweepEnd`, refusing `OpAlloc` until a second `OpSweepBegin` and `OpSweepEnd`
pass completes.

Beyond the single-level state machine, [ElasticPool.v](../../proofs/ElasticPool.v) proves all
five remaining `Q34c-i` Gallina extensions with explicit refutations and closed `witness_<Record>`
definitions (`185` symbols closed under `Print Assumptions`, `0` axioms):

- **Size-class table and granule-exact narrowed length (`R-15-007c`, `R-15-007k`, `R-08-047b`, closing `F-782`)**:
  `std_size_classes_discharge_r15_007k` discharges `all_of class_exact std_size_classes = true`
  across the composition-fixed table (`16`–`65536` bytes), and
  `requested_length_granule_exact` / `narrowed_grant_preserves_bounded_exactly` prove that
  rounding a positive request up to its class granule yields a narrowed length whose representable
  granule divides both the class-aligned base and the rounded length without runtime `CRRL`/`CRAM`
  rounding.
- **Per-island pool disjointness (`R-08-047a`, `R-08-005a`)**:
  `island_pools_disjoint_bytes_and_granules` and `member_binds_launch_island_pool` prove
  pairwise distinct keys, byte disjointness, 8-byte revocation-granule separation, and 64-byte
  aligned revocable-union containment across `DomainIslandPools`, while `shared_granule_pools_refused`
  refutes a shared-granule boundary.
- **Holder-map / revocation-barrier linking (`R-08-006`, `R-08-007a`)**:
  `LinkedMetaState` (`linked_init`, `linked_step`, `linked_run`) gates `OpBarrier` on
  `no_holder_for_pending`; `linked_run_refines_pool_guarantees`, `linked_run_refines_heap_narrows`,
  and `linked_run_refines_heap_zeroed_at_handoff` transfer invariants across arbitrary holder clears
  and additions, while `stale_register_copy_blocks_barrier_and_reuse`,
  `stale_holder_any_kind_blocks_barrier_and_reuse`, and
  `linked_clear_register_enables_barrier_and_reuse` prove that stale `HReg`/`HSavedCtx`/`HStoredCell`
  holders block barrier completion and slot reuse until cleared.
- **Descendant lifetime refinement**:
  `NestedHeapState` (`nested_init`, `nested_step`, `nested_run`) gates child heap actions on
  parent slot phase and monotonic generation; `nested_run_refines_parent_and_child_guarantees`
  preserves `PoolGuarantees` and `HeapGuarantees` at both levels, and
  `parent_release_invalidates_descendant_forever` /
  `parent_realloc_at_next_gen_keeps_old_descendant_dead` prove that parent release permanently
  invalidates bound child operations even after parent slot reallocation at the next generation.
- **Exhausted-class refusal (`R-08-047`)**:
  `exhausted_class_refuses_allocation` and `exhausted_class_cannot_borrow_witness` prove that
  exhausting one size class refuses allocation without borrowing from larger free classes and leaves
  slots, event histories, and memory bytes unchanged.

`Q34c-ii` retains the native C/assembly realization of the pool service and default heap
library, M4.4/R2 runtime holder-map and sweep integration, and cold Guest CI acceptance.

[elastic_pool_campaign.py](../../tools/vos/elastic_pool_campaign.py) generates
actual finite allocator histories, including all command words of length four,
repeated reuse at both classes and both barrier orderings during an active sweep.
Campaign depth is an exact integer from zero through five; booleans, fractional
values and other malformed budgets are refused before pool creation or recursion.
It checks an independent Python observer, deduplicates identical histories and
emits [ElasticPoolCampaign.v](../../proofs/ElasticPoolCampaign.v). Each generated
history is checked directly against `PoolGuarantees`; it is not passed through
the history producer's event filter. The arena starts with nonzero byte value
19 in both observers, so zeroing is required for initial grants as well as reuse.
The tests also require each named negative history to fail exactly its intended
guarantee. These are detected finite controls, not a mutation-score claim about
compiled native code.

Run focused feedback with `python tools/run.py test --only elastic_pool`.
K-88 and the focused test compare the generated source byte for byte with
`render()` from the campaign module, so changed producer histories require
regeneration through `python tools/run.py check --fix`. The shared Host CI
and cold Guest CI proof lanes own the settled checks; a focused compile does not
supply their acceptance verdict.

The authored implementation incorporates no allocator source. No CheriBSD code
or other upstream allocator code was read or adapted for this reference.
