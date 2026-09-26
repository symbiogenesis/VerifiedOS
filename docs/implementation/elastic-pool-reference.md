# Pool and heap reference

This is executable reference work toward [Q34c](implementation-checklist.md),
under the existing [elastic-domain contract](contracts/elastic-domain.md).
Q34c remains open: the finite allocator needs its universal refinement to the
history contract, and the native service/library producer and its admission are
absent. The history-producer theorem and generated finite traces do not establish
that missing correspondence.

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
The finite producer's barrier uses the explicit holder checks described above,
but no universal theorem yet connects those transitions, its ownership metadata
or its parent/child lifetime checks to the Gallina producer. The history-indexed
producer also has no bounded runtime memory or cost claim.

[elastic_pool_campaign.py](../../tools/vos/elastic_pool_campaign.py) generates
actual finite allocator histories, including all command words of length four,
repeated reuse at both classes and both barrier orderings during an active sweep.
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
