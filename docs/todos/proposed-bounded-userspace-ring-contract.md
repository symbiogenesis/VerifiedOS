# Proposed Revision: Bounded Userspace Ring Contract

Status: Proposed for later review; non-normative until adopted  
Proposed target: `spec.md` §12 system-server ring data plane, with corresponding additions to `requirements-register.md`  
Baseline references: `spec.md` R-12-005 through R-12-009; `requirements-register.md` R-07-029 through R-07-031 and R-12-009 through R-12-013  
Disposition: No change to the kernel ABI and no admission of an `io_uring`-style privileged opcode surface

## 1. Summary

This revision defines the contract currently implied by the platform’s “secure io_uring”: bounded single-producer/single-consumer shared-memory rings between a client compartment and a user-level server, with notification wakeups and capability-checked zero-copy DMA where delegated.

The proposal does not add a generic asynchronous syscall engine. It keeps the kernel limited to capability primitives, synchronous endpoints, and notifications. Operation vocabularies remain typed, service-specific, closed, and generated from the platform IDL. Rich dispatch occurs only in the server compartment that implements the relevant interface.

The revision makes five areas explicit:

* submission and completion descriptor structure
* queue-capacity and backpressure behavior
* cancellation, timeout, and restart behavior
* notification and lost-wakeup rules
* WCET, batching, and admission accounting

## 2. Motivation

The current specification establishes the important security shape but leaves interoperability and proof-relevant behavior distributed across several clauses. It states that bulk I/O uses bounded SPSC rings, that descriptors reference pre-delegated capabilities, that authority cannot cross ring pages, that payload ownership is typestate-checked, and that linked cross-service operations are absent. It does not yet collect the operational consequences into one reviewable contract.

Without a closed contract, independently implemented clients and servers could disagree on queue-full behavior, notification suppression, cancellation races, restart recovery, or completion ownership while each still appears to implement “the ring.” Those disagreements are specification defects rather than implementation details because they affect safety, progress, WCET, and the interface proofs generated from the IDL.

## 3. Design goals

The ring contract shall:

* preserve the existing kernel ABI and the prohibition on privileged submission-queue opcode dispatch
* keep all operation vocabularies outside the kernel
* make memory ownership and authority transfer explicit and mechanically checkable
* bound every queue, batch, payload extent, timeout, and amount of work
* define deterministic behavior for full queues, empty queues, cancellation races, peer restart, and notification coalescing
* permit amortization through bounded batching without admitting linked cross-service programs
* support zero-copy DMA only through capabilities delegated for the session
* expose enough structure for CHERI-TAL safety, Coq interface, and WCET obligations

## 4. Non-goals

This revision does not provide:

* a generic kernel opcode table
* arbitrary syscall submission through a ring
* cross-service linked operations or dependency graphs
* dynamically registered credentials, personalities, files, paths, or ambient object names
* unbounded queues, payloads, batches, retries, or completion retention
* dynamic queue resizing
* authority transfer through ring memory
* work-conserving scheduling, priority donation, or runtime scheduling decisions
* implicit recovery of operations after a server restart

## 5. Proposed normative text for `spec.md` §12

### 5.1 Ring instance and memory layout

Each client–server session MAY contain one request ring and one completion ring per direction declared by its interface world. Every ring is SPSC, has a composition-time constant capacity, and occupies a statically assigned shared-memory region.

A ring header contains only:

* a monotonically wrapping producer index
* a monotonically wrapping consumer index
* a notification state word
* a session-generation identifier

Header fields are fixed-width atomics. Descriptor and payload bytes are non-atomic and are accessed only under the slot-ownership transitions defined below. Ring capacity, index width, descriptor size, alignment, and maximum batch size are constants in the generated interface artifact.

Indices MUST be interpreted modulo the declared capacity while retaining sufficient sequence information to distinguish full from empty. An implementation MUST NOT infer validity from descriptor contents.

### 5.2 Descriptor schema

Every submitted descriptor contains exactly:

* an operation tag from the interface’s closed variant
* a client-selected request identifier unique among that session’s live requests
* bounded operation-specific scalar metadata generated from the IDL
* zero or more buffer references, each consisting of a session-table index, offset, length, direction, and declared content type
* an optional relative deadline drawn from the finite deadline classes admitted for that interface
* flags from a closed, interface-specific bit set

A descriptor MUST NOT contain a path, raw address, capability encoding, executable command name, unbounded list, recursive value, dynamically interpreted opcode, or reference outside the session table.

The server resolves each buffer reference only through the session’s pre-delegated capability table. Resolution MUST check bounds, permissions, direction, content type, and session generation before the operation becomes eligible to execute.

Unknown operation tags, reserved flags, malformed bounds, duplicate live request identifiers, and stale session generations produce a defined refusal completion. They MUST NOT extend the operation vocabulary or trigger fallback interpretation.

### 5.3 Completion schema

Every terminal completion contains exactly:

* the corresponding request identifier
* a terminal status from a closed variant
* bounded operation-specific result metadata
* the number of input and output bytes consumed or produced, where applicable
* a server-generation identifier

The common terminal status set is:

* `ok`
* `refused`
* `invalid`
* `cancelled`
* `deadline_expired`
* `peer_restarted`
* `device_fault`
* `resource_exhausted`

An interface MAY refine these statuses with a closed operation-specific result variant but MUST NOT replace their common lifecycle meaning.

Exactly one terminal completion is published for every accepted request unless the session itself is torn down. Session teardown is represented out of band by revocation plus a generation change, after which all formerly live requests have the logical result `peer_restarted` even if their terminal completions were not observable.

### 5.4 Ownership state machine

Each request slot follows this state machine:

1. `free`: owned exclusively by the producer for allocation.
2. `writing`: owned exclusively by the producer; descriptor and producer-owned payload may be mutated.
3. `submitted`: immutable to the producer after release publication.
4. `accepted`: consumed by the server; referenced buffers are held under the permissions declared by the operation.
5. `terminal`: the terminal completion has been release-published.
6. `reclaimed`: the client has acquire-consumed the completion and all operation-held references have been released, permitting the request identifier and slots to be reused.

Publication consumes writable ownership and yields immutable published ownership. Reclamation MUST NOT restore writable ownership until every reader and DMA holder associated with the operation has completed or been revoked.

A malformed request may move directly from `submitted` to `terminal` with a refusal status. It MUST NOT acquire device authority or begin payload mutation before validation completes.

### 5.5 Queue capacity and backpressure

Ring capacity is an admission parameter. Producers MUST test available capacity before reserving slots and MUST NOT overwrite an unconsumed descriptor or completion.

When a request ring is full, submission has the sole result `would_block`; it does not enqueue partial work. The client may retry only in a later assigned slot or after observing a completion notification. Busy-waiting outside the client’s own scheduled slot is impossible under the scheduler and MUST NOT be treated as a progress mechanism.

When a completion ring is full, the server MUST stop accepting additional requests for that session before it would exceed the completion capacity required to report their terminal states. Admission MUST establish one of the following:

* completion capacity is at least the maximum number of simultaneously accepted requests; or
* the server reserves completion credit before accepting each request.

A server MUST NOT drop or overwrite a terminal completion to recover space.

### 5.6 Bounded batching

A producer MAY publish multiple adjacent descriptors before one notification, up to the interface’s composition-time maximum batch size. A consumer MAY drain multiple available descriptors in one activation, up to the smaller of:

* the published count
* the declared maximum batch size
* the work admitted for that scheduled slot

A batch is an amortization unit, not a transaction. Each request is validated, accepted, cancelled, completed, and accounted independently. Failure of one request MUST NOT implicitly cancel, commit, or roll back another.

Descriptors MUST NOT name predecessor requests or encode cross-request control flow. An interface requiring an atomic compound operation MUST define that operation as one bounded typed variant with one proof and one WCET bound, rather than as linked ring entries.

### 5.7 Notifications and lost-wakeup avoidance

Notifications are hints that ring state may have changed; indices remain the source of truth. Correctness MUST NOT depend on receiving one notification per descriptor or completion.

The producer follows this protocol:

1. write all descriptor or completion bytes under exclusive ownership
2. release-publish the producer index
3. atomically mark notification-needed state and signal only when the consumer may otherwise sleep

The consumer follows this protocol:

1. acquire-read and drain available entries within its admitted budget
2. arm its notification state before concluding that the ring is empty
3. acquire-read the producer index again
4. sleep only if the second read still shows no work

A producer racing with the consumer’s transition to sleep therefore either observes the armed state and signals, or publishes work that the consumer observes during its final recheck. Notification coalescing is permitted; notification loss as an unmodeled event is not.

Spurious notifications are permitted and produce only an empty drain attempt bounded by the interface’s poll cost. Notification counters and flags MUST have defined wrap and reset behavior.

### 5.8 Cancellation

Cancellation is a typed control-plane request to the same server, not mutation of a submitted descriptor. It identifies the target by session generation and request identifier.

Cancellation has deterministic race semantics:

* if the target is still `submitted`, the server completes it as `cancelled` without beginning the operation
* if the target is `accepted` and the interface declares a bounded cancellation point, the server reaches that point and completes it as `cancelled`
* if the operation has crossed its declared non-cancellable commit point, cancellation returns `too_late` and the original operation completes normally
* if the target is already terminal or unknown in the current generation, cancellation returns `not_live`

Every cancellable operation MUST declare its cancellation points, cleanup bound, DMA-quiescence rule, and maximum time to terminal completion after cancellation is accepted. Operations without such a declaration are non-cancellable.

Cancellation MUST NOT revoke authority independently of session teardown. It releases only the operation’s held references after its cleanup obligation is complete.

### 5.9 Deadlines and timeouts

A deadline is selected from a finite interface-specific set of relative deadline classes. Arbitrary timestamps are not accepted through the ring.

Expiration is evaluated only at declared server decision points using the platform’s scheduled time base. An expired request either:

* has not begun and completes as `deadline_expired`; or
* has begun and follows the interface’s declared cancellation rule.

Timeout does not imply instantaneous preemption, scheduler donation, or device reset. Admission MUST account for the maximum interval from expiry observation to terminal completion, including cleanup and DMA quiescence.

A client-side wait timeout changes only the client’s willingness to wait. It does not cancel the server operation unless the client also submits and receives acceptance of a cancellation request.

### 5.10 Session teardown and peer restart

Every ring and descriptor is bound to a session generation. Restarting either peer, resetting a device, or revoking the session increments or replaces that generation before the ring can be reused.

On teardown:

* new submissions are refused
* DMA capabilities are revoked or allowed to quiesce under the session’s declared bound
* outstanding output buffers remain unreadable by the server after revocation
* no descriptor from the old generation may be accepted
* ring indices and notification state are reinitialized before the new generation becomes live
* operations are not replayed implicitly

Retry after restart is an interface-level client decision. An interface claiming idempotent retry MUST identify the operation subset, the stable request identity used for deduplication, the retention bound for deduplication state, and the proof obligation establishing that duplicate execution has the stated effect.

### 5.11 Zero-copy and DMA

Zero-copy is permitted only when the session table contains a delegated capability with permissions matching the descriptor’s declared direction. The DMA engine presents that capability to the fabric for every access.

The server MUST validate the complete extent before starting DMA. A device or server MUST NOT reinterpret an offset or length after validation, extend an extent through scatter metadata not covered by the descriptor schema, or retain a capability past terminal completion.

Scatter/gather MAY be admitted only as a bounded list whose maximum segment count is fixed by the interface. Every segment is checked independently, and the operation’s WCET includes the maximum segment count even when fewer segments are supplied where the constant-time policy requires that treatment.

A non-capability DMA write clears capability tags for every granule it overwrites, consistently with the platform memory-write rules.

### 5.12 Scheduling and WCET

Ring service runs only in the server’s assigned slots or on a core statically pinned to that server under the existing switch-duty rule. Ring occupancy MUST NOT cause priority changes, donated budget, opportunistic execution in another partition’s slot, or work-conserving schedule changes.

For each operation variant, the interface artifact records:

* validation cost
* maximum payload and segment counts
* maximum device-service cost or the fixed bound imported from the device contract
* maximum cancellation cleanup cost
* maximum completion-publication cost
* maximum notifications generated
* maximum requests drained per activation

Composition proves that request capacity, completion credit, batch size, polling cadence, slot budget, and device latency jointly prevent overwrite and meet the declared progress bound. If the required polling cadence would make partition switching dominant, the existing rule applies: deepen the ring to amortize the cadence or pin the server to an appropriate core.

### 5.13 Error containment

A ring-library defect or server opcode-dispatch defect is confined to the client or server compartments and authority already delegated to that session. The kernel is not an IDL endpoint and does not parse ring descriptors.

Invalid descriptors are refused before device action. Repeated invalid submissions consume only the submitting client’s admitted service allocation and MUST NOT enlarge another partition’s work or timing observation beyond the static schedule.

Uncorrectable ring-memory ECC, impossible ownership transitions, generation mismatches after acceptance, and DMA that fails to quiesce within its declared bound are fail-stop conditions for the affected session or server according to the existing supervision policy.

## 6. Proposed additions to `requirements-register.md`

The final identifiers should be allocated by the register-maintenance process. Temporary proposal identifiers are used below.

### PR-12-RING-001

MUST: Every userspace I/O ring has a composition-time fixed capacity, fixed descriptor layout, fixed maximum batch size, and session generation; only indices and notification words are concurrently shared atomics.

Accept: The generated interface artifact enumerates those constants, and the CHERI-TAL derivation rejects concurrent non-atomic access to descriptor or payload bytes.

Trace: `CJ-IDL`, `CJ-TAL-SOUND`, `CJ-WCET`

### PR-12-RING-002

MUST: Every operation descriptor is a member of a closed service-specific IDL variant and refers to memory only through bounded entries in the session’s pre-delegated capability table.

Accept: Unknown tags and reserved flags produce refusal completions; no descriptor field admits a path, raw address, capability encoding, recursive value, or unbounded collection.

Trace: `CJ-IDL`, `CJ-CERISE`

### PR-12-RING-003

MUST: Request and payload ownership follows the six-state `free` → `writing` → `submitted` → `accepted` → `terminal` → `reclaimed` protocol, with publication and reclamation expressed as capability-consuming typestate transitions.

Accept: No admitted execution can mutate a published descriptor, reuse a live request identifier, reclaim a buffer held by a reader or DMA engine, or accept a request before validation.

Trace: `CJ-TAL-SOUND`, `CJ-HAL`

### PR-12-RING-004

MUST: Queue-full behavior is fail-closed and non-overwriting; servers reserve completion credit before accepting requests.

Accept: A full request queue returns `would_block`; no request is partially enqueued; no terminal completion can be dropped or overwritten; the composition proof establishes adequate completion capacity or a credit invariant.

Trace: `CJ-IDL`, `CJ-WCET`, `CJ-TAL-SOUND`

### PR-12-RING-005

MUST: Notification correctness follows the arm–recheck protocol; notifications are coalescible hints and ring indices are the source of truth.

Accept: The ring proof covers producer publication racing with consumer sleep, permits spurious and coalesced notifications, and contains no execution in which published work remains indefinitely hidden by a lost wakeup.

Trace: `CJ-TAL-SOUND`, `CJ-WCET`

### PR-12-RING-006

MUST: Cancellation and deadlines use closed interface-defined semantics with bounded decision points, cleanup, and DMA quiescence; a local wait timeout does not implicitly cancel an operation.

Accept: Every cancellable operation declares cancellation points, a commit point, cleanup bound, and terminal-completion bound; every deadline comes from an admitted finite class.

Trace: `CJ-IDL`, `CJ-WCET`, `CJ-HAL`

### PR-12-RING-007

MUST: Batching is bounded and non-transactional; linked requests and cross-service dependency graphs are absent.

Accept: A batch cannot exceed its declared maximum; every member validates and completes independently; compound atomic behavior exists only as one typed operation carrying one proof and WCET bound.

Trace: `CJ-IDL`, `CJ-WCET`

### PR-12-RING-008

MUST: Session teardown changes the generation, prevents acceptance of stale descriptors, revokes or boundedly quiesces DMA, and never replays operations implicitly.

Accept: Restart tests show that descriptors from the prior generation are refused, old capabilities cannot be used, and retry occurs only through an explicitly documented interface policy.

Trace: `CJ-HAL`, `CJ-CERISE`, `CJ-WCET`

### PR-12-RING-009

MUST NOT: No ring operation vocabulary, descriptor parser, cancellation dispatcher, timeout engine, or retry policy enters the kernel ABI.

Accept: The frozen kernel invocation list remains unchanged and contains no submission-queue dispatch operation.

Trace: `CJ-KERNEL`

## 7. Crown-jewel and proof impact

This proposal should not create a new crown-jewel specification if adopted as part of the existing IDL wire-format mapping and verified HAL contracts. It enlarges the required content of two existing inventory rows:

* the IDL wire-format mapping must include common ring headers, lifecycle statuses, ownership transitions, notification semantics, and generated service-specific descriptor variants
* the verified HAL contracts must include DMA extent validation, capability presentation, cancellation cleanup, quiescence, completion credit, and restart-generation behavior

The proposal also consumes the existing static slot plan, timing-annotated Sail latency magnitudes, capability-distribution specification, and CHERI-TAL soundness statement. Review should confirm that no clause silently confers crown-jewel status on a new standalone “ring semantics” artifact. If the semantics cannot be housed unambiguously in the IDL mapping, the inventory should gain a dedicated row rather than leaving the contract split across prose.

Required proof obligations include:

* SPSC memory safety and race freedom under Ztso
* arm–recheck lost-wakeup exclusion
* request and completion capacity invariants
* completion-credit preservation
* typestate preservation across publication, cancellation, completion, and reclamation
* stale-generation rejection
* DMA authority, extent, and quiescence invariants
* per-operation WCET and bounded cleanup
* containment of malformed or adversarial descriptors
* interface conformance between generated client, server, parser, and Coq skeleton

## 8. Compatibility and migration

Because this proposal freezes behavior that was previously implicit, adoption may reveal incompatible ring users. Migration should therefore be staged:

1. Author the common ring schema and lifecycle model in the IDL profile.
2. Generate reference client/server bindings and the Coq interface skeleton.
3. Port one existing service with no DMA and establish the SPSC, notification, and credit proofs.
4. Port one DMA service and establish extent, cancellation, teardown, and quiescence proofs.
5. Measure queue depth, batching, notification, and slot-budget parameters on a representative composed roster.
6. Allocate final requirement identifiers and amend `spec.md`, the register, and affected crown-jewel rows together.

Existing services are not grandfathered. A service that cannot state finite capacities, lifecycle semantics, cleanup bounds, and per-operation WCET is not admitted through this ring profile.

## 9. Review questions

Review should decide:

* whether deadline classes belong in the common ring header or only in service-specific variants
* whether cancellation should always use synchronous control-plane IPC or may use a dedicated typed cancellation ring for high-rate services
* whether common terminal statuses are sufficient or need a separate `server_unavailable` status distinct from `peer_restarted`
* whether completion credit must always equal request capacity, accepting memory cost for a simpler invariant, or may be reserved dynamically within the fixed capacities
* whether idempotent retry is worth admitting at all, given the state and proof surface required for deduplication
* whether notification counters are preferable to a binary armed flag for wrap analysis and diagnostics
* whether the common ring semantics remain part of `CJ-IDL` or deserve a separately conferred crown-jewel row

## 10. Recommended disposition

Adopt the contract in principle, but do not merge it directly into the normative specification until two executable examples exist: one copy-based service and one capability-checked DMA service. Use those examples to validate descriptor size, completion credit, notification behavior, cancellation bounds, and the generated-proof interfaces.

Retain the existing categorical prohibition on an `io_uring`-style kernel opcode surface. The proposed revision adds precision and reusable userspace machinery, not a new privileged mechanism.
