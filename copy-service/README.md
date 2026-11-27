# Copy service core

M7.1e's GC-free C core implements the ring declaration's reference world. The
build emits `copy_service_config.h` from [the declaration](../interfaces/ring-reference.json);
capacity, index span, batch, generation and operation payload limits have no
second maintained copy. The core uses caller-owned fixed arrays and no allocation,
recursion or garbage collector.

The accepted scalar backend lowers the same validation, staging and lifecycle C
used by the host comparison. [The target adapter](src/atomic_target.s) owns the
atomic entry boundaries and calls those compiled stages; the backend is not
asked to lower unsupported C11 atomics, volatile accesses or unchecked external
calls. The focused target campaign executes this member on the source-bound
model. The notification adapter performs actual interrupt-file stores and
ordinary pending loads. Completion and the composed boot checkpoint remain
separate joins. This C implementation does not discharge the deferred safe-Rust
obligation or establish CHERI-TAL ownership.

## Executable boundary

[The header](include/vos_copy_service.h) separates ordinary finite state helpers
from a payload ring whose head, tail and binary armed word have explicit atomic
interface types. The host defines those types with C11 atomics; the target keeps
them opaque to C and accesses them only in the assembly adapter.
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
The caller supplies accessible, disjoint buffers and keeps the source stable
during the copy. A concurrent source write would race the ordinary C11 byte
reads. Consumers and semantic validators use the staged bytes and length,
which remain independent of the external buffer after publication.

An undersized destination makes `take` refuse without advancing the tail or
changing outputs. On success, `take` copies the payload, finishes its reader
and reclaims the slot before publishing the new tail. The producer may reuse
the slot only after observing that release. Reset and reinitialization require
both endpoints to be quiescent.
`init_generation` refuses zero and installs the supplied four-byte generation;
the serialized kernel binding must advance the session generation before reuse
and refuse a value that cannot fit, never truncate its full-width epoch.

The payload ring selects `reset_at_the_signal`: successful publication exchanges
the armed word for zero and returns a binary signal request to the adapter. After
draining its admitted batch, the consumer calls `prepare_sleep`, which arms,
rechecks the head and allows a quiet yield only if empty. The adapter preserves a
pending signal across that boundary. R-07-031b has no notification syscall, and
the ring's sleep state means a poll-site yield, not a blocking wait. The producer
signals even if another activation has already
drained the work, which is permitted coalescing. Ordinary notification helpers
also exhibit `reset_at_the_drain` to compare both arms of the reference; that arm
is not the payload ring's policy.

Wire indices wrap modulo the declared span, and slots modulo capacity. The
configuration reader requires capacity to divide span and span to exceed
capacity, so the live window distinguishes full from empty across wrap. Its
32-bit arithmetic bound is checked before generating C. The host and target use
the declaration's one-byte physical wire indices.
The generation and notification words keep their separate four-byte storage.
The target layout check rejects any compiler layout incompatible with the
assembly adapter before running a request. The packed IDL descriptor encoding
and generated Narcissus parser remain distinct from this direct bounded C API.
The reference helpers'
`signals` and `drained` fields are bounded test observations, not shared event
counters. Both the index batch helper and the atomic payload `submit_batch`
report each enqueue independently and never roll back earlier success; a count
above the declared bound is refused before reading requests or touching outputs.
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
The tool refuses generated populations above 50,000 cases before expanding them;
this is a comparison resource limit, not an interface capacity requirement.

`python tools/run.py test --only test_copy_service` exercises the tool interface;
Linux additionally compiles and runs the fixed C controls. The proof gate remains
the authority for compiled proof acceptance. This finite comparison performs no
assumption audit, target run or composed boot.

## Scalar target comparison

After `copy-service check`, run `copy-service target --ccomp PATH
--ccomp-arg=-conf --ccomp-arg=CONFIG --simulator PATH --build-receipt FILE`.
The target driver refuses stale reference inputs or answers and a model receipt
that does not bind the current source population and simulator. Its report binds
the C producer, configuration, generated rows, emitted assembly, image, actual
trace and reference comparison. The compiled row consumer executes every answer
from the existing Gallina comparison; an altered answer must fail on target.
A separate executed mutant drops head publication and must be detected by the
payload controls. Both mutants must run to a control failure; a trap or failure
to assemble is not a kill.

The actual atomic entry controls cover empty/full/one-past-full, repeated wire
wrap, maximum payload, guard bytes, post-publication source mutation, overlong,
stale-generation and duplicate refusal, independent partial batch decisions,
and publication at every drain/arm/recheck/sleep boundary. Source, destination,
ring and row-table capabilities have separate power-of-two bounded extents.
The stack is bounded independently and no ring lives on it. Generation reset is
quiescent; runtime teardown must zero the actual owned ring/staging extent.

The adapter fences payload publication and consumption and the consumer's
arm-store to head-load edge. The producer clears `armed` with `amoswap.w.aqrl`.
The projected two-cell Ztso Store/Load experiment exhausts the event orders under
those edges and rejects a removed consumer fence with a lost-wakeup witness.
This finite projection is not a proof of the whole C/ISA refinement. A single-hart
emulator cannot establish cross-core ordering or the kernel's sticky pending
notification contract; the scalar integration checkpoint supplies the latter.
The adapter's source and all its linked instruction bytes remain in the receipt.

`copy_target.adapter(root)` returns the same assembly entry implementation and
its constants generated from the declaration for the integration owner. It uses
the scalar ABI and the public C signatures, restores `csp` and `cra`, and treats
all ordinary registers as caller-clobbered. Snapshot helpers are private stages
of these adapters, not independent untrusted service entry points.

## Standalone source preparation

`python tools/run.py copy-service prepare-package --output out/copy-package`
prepares a separate source snapshot for M7.1d's real-member producer handoff.
Add `--check` to replay the record and exact output population without publishing.
The [standalone recipe contract](../docs/implementation/contracts/fixed-packages.md#standalone-copy-service-source-recipe)
owns its acceptance boundary.

[The standalone unit](src/package_unit.c) compiles the complete existing core with
`VOS_COPY_TARGET` and [the shared target layout checks](src/target_layout.c).
It excludes `test/target_comparison.c`, the host harness and the shared scalar
supervisor/kernel wrapper. The atomic and notification adapters are included in
full; the declaration owners generate their constants and the C configuration
header. No functions are removed by this preparation. The existing target
comparison uses the same layout-check source.

The deterministic `source-record.json` binds the copied C/headers, declarations,
model layout inputs and generation helpers, plus every prepared output. Generation
reads captured declaration/model bytes, then rechecks the live input identities
before publication. Unexpected includes, aliases and drift refuse; replay also
refuses missing, substituted or extra outputs. Files are published atomically and
the record last; a partial publication is not a valid snapshot until replay passes.

The recorded compiler arguments identify the intended target mode and snapshot
include path. They invoke no compiler. Q39 still owes the qualified producer and
its standard-header/configuration identity, after which the entire emitted stream
and both runtime adapters must be retained. Installed activation roots, extents,
initializer, capability wiring, placement, final image and production proof inputs
remain open. This source record carries no native object or admission verdict.

`python tools/run.py copy-service check-package-syntax --prepared out/copy-package`
runs the strict native C17 syntax check in the guest. It replays the prepared
population, compiles a private snapshot of the checked bytes, then checks the
prepared population and compiler identity again. Its JSON on standard output
records the recipe digest, compiler bytes and version, command, exit status and
diagnostics. `python tools/run.py test --only test_copy_package` exercises the
source handoff and refusal controls, including the guest syntax command.

The [retained strict native standalone C syntax control](../docs/implementation/retained-evidence/copy-package-native-syntax-20261109/manifest.json),
SHA256 `1931dcd8df3b88980eb0e8e163c29de3790a346d13324dec2490b120c0efb16f`,
passes on the complete snapshot prepared from the real checkout. The source record
replays before and after compilation; the result binds that record, the resolved
native compiler's bytes and version, the exact C17 warning and syntax-only
arguments, exit status and diagnostics. The focused guest source-handoff controls
also pass. This closes the native C syntax checkpoint; qualified target emission,
installed entry and capability wiring, final-image mapping and production
admission retain their open predicates.

The [Q25bb standalone target execution envelope and static footprint](../docs/implementation/retained-evidence/holdfast-q25bb-target-envelope-20261126/manifest.json),
SHA256 `16ce192a39c57eaf622e8e090e149e090c5b9c1e781377887bf09c630b8d19f0`,
measures the frozen `498127d6` standalone compilation (5,436 service text bytes:
4,808 compiled C, 532 `src/atomic_target.s`, 96 `src/notification_target.s`)
and its Sail commit-trace per-entry retired-instruction, write-count, and
`x2`/`csp` stack-frame bounds across all eight public entries on both the
archived notification trace and an extended legal-plus-refusal workload. These
development measurements carry no qualified producer, installed entry or
capability wiring, or production admission.

The [Q25bb purecap HoldFast copy client target run and expanded controls (85b9462f)](../docs/implementation/retained-evidence/holdfast-q25bb-purecap-client-20261127/manifest.json),
SHA256 `766c81fb127658d869bafed075a7ff7b960ee76fecdad7bcef986afc43b86be1`,
executes HoldFast's purecap `holdfast_copy_trial` (`85b9462f`) against the
byte-identical `498127d6` copy-service text extents (5,436 service text bytes)
on the source-bound Sail simulator (`verdict: pass`, 9,490,563 commit-trace
records, 4,876,085 retired instructions; per-entry bounds across
`vos_copy_init_generation` [5 calls, 3–5,727 insns, 0–328 writes, 32 B stack],
`vos_copy_submit` [602 calls, 142–61,955 insns, 26–4,156 writes, 240 B stack],
and `vos_copy_take` [593 calls, 110–61,924 insns, 19–4,142 writes, 176 B stack]),
passes all eight target-side negative controls (`mutated-payload-limit` exit 14,
`mutated-snapshot-byte` exit 7, `mutated-suffix-clobber` exit 8,
`mutated-refusal-output` exit 2, `mutated-overlapping-views` exit 9,
`mutated-narrow-arena-cap` CHERI trap cause 28 / HTIF 284,
`mutated-read-only-arena-cap` CHERI trap cause 28 / HTIF 284, and
`mutated-untagged-arena-cap` CHERI trap cause 28 / HTIF 284), and confirms
host-native vs purecap-target exit-code parity via `holdfast-copy-trial` across
baseline and the four C controls. These development measurements carry no
qualified producer, installed entry or capability wiring, trial acceptance, or
production admission.

## Notification device adapter

`copy-service notification` accepts the same compiler and model arguments as
`target`. It executes actual ring publication, passes that call's signal request
to [the notification adapter](src/notification_target.s), and observes the
modeled interrupt-file pending word with ordinary loads. The validated
device-register declaration and current model composition own its offsets,
access width and identity bound. `copy_notification.adapter(root)` exposes the
same assembly and generated constant for composition.

The [notification header](include/vos_copy_notification.h) fixes its scalar ABI.
The sender gets an exact device-word data read/write capability; the doorbell's
device semantics make its read side return zero. The receiver gets an exact
read-only capability to the pending word. Neither carries capability-store or
system-register authority. `notify` rejects malformed identities and nonbinary
requests; a zero request performs no store. `poll` returns pending as a Boolean
or -1 for an invalid identity, and does not clear the word. The device's writeback
replaces the entire pending word, so unsynchronized read-modify-write clearing
would lose another sender's event and is not exposed by this adapter.

The target controls cover coalescing, reserved and out-of-range identities,
zero signal requests, pending across repeated polls, another identity's pending
bit and the copied payload. Executed lost-store and lost-load mutants must fail
the controls. Removing the sender's store permission must cause an actual
capability trap and is reported as authority refusal, not a mutant kill.
No new syscall, scheduler suspension or completion-ring semantics is introduced.

## Confined private activation

`copy-service partition` accepts the compiler and model arguments of `target`.
It enters the real compiled copy code with a bounded PCC without ASR, a private
stack inside its complete 524,288-byte owned allocation, byte-only payload
capabilities and exact notification words. Each activation transfers a payload,
observes its notification and faults at a named instruction. The trusted handler
saves all 33 capability slots, scrubs registers, clears and reads back the whole
owned allocation and saved/fresh images, then enters a fresh generation.

Executed controls omit tail, saved-image or resident cleanup, supply an ASR
entry, or retain a stale generation. These must fail the corresponding target
check. The receipt binds each image and trace and requires the positive trace's
entry, notification, fault and cleanup observations. The private allocation
remains continuously owned; this experiment does not claim physical ring
revocation, a public client endpoint, fixed scheduler timing or composed boot.

The C and Python files are original Apache-2.0 sources; this document is CC-BY-4.0
under [COPYRIGHT.md](../COPYRIGHT.md).
