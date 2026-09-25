# Copy service core

M7.1e's GC-free C core implements the ring declaration's reference world. The
build emits `copy_service_config.h` from [the declaration](../interfaces/ring-reference.json);
capacity, index span, batch, generation and operation payload limits have no
second maintained copy. The core uses caller-owned fixed arrays and no allocation,
recursion or garbage collector.

**The target roster member is unbuilt.** The accepted M1.2f backend, its C11 atomic
lowering, M4.4's notification/wait adapter and M7.1a's composed member remain open.
Host agreement does not establish CHERI-TAL slot ownership or refinement under
Ztso. This C implementation does not discharge the deferred safe-Rust obligation.

## Executable boundary

[The header](include/vos_copy_service.h) separates ordinary finite state helpers
from a payload ring whose head, tail and binary armed word have C11 atomic types.
The payload ring supports exactly one producer and one consumer. Publication and
return of ownership use sequentially consistent stores, including release;
observations use sequentially consistent loads, including acquire. The stronger
order also covers the head/armed sleep race. Payload and lifecycle fields are
accessed only while their side owns a slot; duplicate checking reads
producer-written identifiers within the acquired live window, never a consumer's
mutable lifecycle state.

`submit` validates generation, operation, live identifier, ring space and both
length bounds before reading any payload. It copies bytes once into private
staging before publishing. Scalar length/extent inputs are snapshots by value.
Consumers only read staging; changing the external buffer after publication
cannot change its length or bytes. Accessible, disjoint source/destination bounds
are caller obligations. A concurrently modified source can yield mixed bytes;
this is no atomic snapshot guarantee, and semantic validation must use staging.
`take` refuses an insufficient destination without advancing or changing output
arguments, then accepts, consumes all readers, completes and reclaims the slot
before releasing the tail. Reuse begins a fresh Free-to-Writing lifecycle only
after that release. Reset/reinitialization requires both endpoints quiescent.

The payload ring selects `reset_at_the_signal`: successful publication exchanges
the armed word for zero and returns a binary signal request to the adapter. After
draining its admitted batch, the consumer calls `prepare_sleep`, which arms,
rechecks the head and allows sleep only if empty. The adapter must preserve a
pending signal across the check-to-wait boundary; a host Boolean is no kernel
wait operation. The producer signals even if another activation has already
drained the work, which is permitted coalescing. Ordinary notification helpers
also exhibit `reset_at_the_drain` to compare both arms of the reference; that arm
is not the payload ring's policy.

Wire indices wrap modulo the declared span, and slots modulo capacity. The
configuration reader requires capacity to divide span and span to exceed
capacity, so the live window distinguishes full from empty across wrap. Its
32-bit arithmetic bound is checked before generating C. The reference helpers'
`signals` and `drained` fields are bounded test observations, not shared event
counters. The batch helper reports each enqueue independently and never rolls
back earlier success; a count above the declared bound is refused untouched.
Wire descriptor encoding, segment descriptors, operation semantics, per-operation
WCET admission and the completion-ring adapter remain separate work.

## Focused comparison

`python tools/run.py copy-service check` compiles the native C harness and binds
its answers to exact expressions from [CopyRingService.v](../proofs/CopyRingService.v)
and [RingContract.v](../proofs/RingContract.v). Python generates input domains and
Gallina syntax, not reference verdicts. Domains cover every wire base at empty,
single, almost-full and full occupancy, every batch count and remaining space up
to the declared batch, the entire state/event/reader/validation product, payload
boundaries, and publication at every consumer-chain boundary under both reset
owners and with backlog. A changed C answer must be refused by reference
conversion in a separate negative control.

Fixed consumer controls separately check all transferred bytes, guard bytes,
source mutation after publication, duplicate/stale/overlong refusals, output
preservation, full then one-past-full, repeated wrap, held-reader reclamation,
partial batch and invalid finite indices. These controls execute the atomic ring
sequentially; they are neither a concurrent stress campaign nor a memory-model
proof. The report binds source, declaration, generated header, binary, answers,
comparison and compiler/prover identities. Native artifacts remain in the assigned
lane under `/root/build` and logs under `/root/logs`.

`python tools/run.py test --only test_copy_service` exercises the tool interface;
Linux additionally compiles and runs the fixed C controls. The proof gate remains
the authority for compiled proof acceptance. This finite comparison performs no
assumption audit, target run or composed boot.

The C and Python files are original Apache-2.0 sources; this document is CC-BY-4.0
under [COPYRIGHT.md](../COPYRIGHT.md).
