# Same-session application host

Status: **contract authored; implementation, proofs and target measurements open**.
The normative owners are R-14-013e through R-14-013h in the
[requirements register](../../requirements-register.md). Q34f owns the host and
qualification; Q34g owns the interpreter and its refinement, and Q34h owns
the resident guest compiler and bundle producer. Native builds use
the [editor compatibility contract](compatibility.md) and successor generations.

## Execution and guarantee boundary

An elastic pool supplies resident data backing. It does not supply permission
to turn newly written bytes into machine instructions. The measured-boot loader
remains the only writer of executable memory. A precomposed native interpreter
therefore runs a newly built Wasm bundle during the current session, and an
already admitted native service can perform work for it through a bounded import.
Changing that interpreter, service or native interface requires a successor boot.

The native host retains CHERI-TAL, W^X, authority, initialization and scheduling
obligations. The guest inherits the interpreter's pinned-semantics refinement
and confinement to its private arena and explicitly granted imports. Core Wasm
does not identify the source program's allocation boundaries or lifetimes:
arena confinement alone permits an overflow between guest objects and reuse of
a guest pointer after its source-level free. A safe source language, successful
compilation, bundle digest or publisher signature is not a proof that those
properties survived compilation. Stronger guest claims need checked evidence
for the exact artifact and property under R-14-005. Platform secrets remain
outside the ordinary guest interface.

The interpreter's implementation must also distinguish a language failure from
a host failure. The curated subset of the [Wasm 3.0 memory instruction semantics](https://webassembly.github.io/spec/core/exec/instructions.html#memory-instructions)
governs guest growth failure and trapping accesses. R-14-013b pins its exact
revision, enabled features and numeric profile. Host resource limits do not
license a different successful language result. The implementation can suspend
a long internal operation between bounded native steps only when its refinement
preserves the guest-visible semantics and no import observes partial state.

## Operations

All operations use existing composed roles, bounded request/result storage and
activation-scoped handles. No operation accepts a filesystem path as authority.

| Operation | Authority and checked input | Result and failure boundary |
| --- | --- | --- |
| Build guest | Granted immutable source closure, chosen resident compiler and supported guest profile, bounded output reservation | Immutable bundle closure or bounded diagnostics; output has no native execute authority and must pass host validation |
| Prepare | Exact closure and descriptor, compatible host/import ABI, candidate resource reservations | Host-owned validation result; malformed, incomplete, unsupported or oversized inputs release partial preparation and leave the current app running |
| Launch | Prepared closure, free composed host instance, current profile and explicit initial/import grants | Fresh activation binding and first useful response; no host or capacity gives a typed refusal |
| Invoke import | Binding-scoped handle, operation and bounded arguments | Checked typed result or refusal; the native service checks scope independently and a reply names the requesting epoch |
| Replace | Exact prepared replacement and authorized commit, required consent, transition reservations and declared durable-state policy | Retire the old binding before activating the new one; failure before commit leaves the old app usable, failure after commit leaves it closed with acknowledged durable work |
| Cancel or close | Current activation and authorized lifecycle request | Stop guest execution and ingress, complete or cancel outstanding work, contain, sweep and sanitize before reuse |
| Restore | Authenticated semantic checkpoint, exact compatible bundle/profile/ABI/schema and current grants | Revalidated fresh activation; no old grant, tagged memory, register image or session key is restored |

Preparation runs without executing guest start functions or spending newly
requested grants. A candidate's start function runs only after activation and
is subject to cancellation like every other guest instruction. Any failure
after activation follows the same retirement protocol. A declared bundle
digest and a UI label are distinct: trusted consent identifies the exact
binding; a guest-controlled name cannot authenticate its caller or publisher.

A launch record is private profile data used by the shell to open a bundle.
It does not register a format handler or rewrite the signed routing graph.
The separate packaged-web profile remains R-14-008h's contract; the same-session
host does not silently inherit a browser, DOM, WASI namespace or native bridge.

## Capacity, scheduling and reuse

Composition declares host count and supported profiles, initial floors and
maxima, and all R-14-013g structures under R-08-046. Each instance is a distinct
application group even where engine code is shared, ensuring inter-app clearing.
Capacity qualification includes simultaneous unrelated guests, two instances
of the same bundle, preparation beside a live app, and old quarantined memory
beside replacement reservations. Immutable code is counted once; mutable state
and transition peaks are counted for every live allocation.

The initial linear memory is backed at launch; its maximum limits later growth
without requiring the whole maximum to be reserved. Successful growth first
obtains resident, zeroed backing. Segmented backing can avoid requiring a single
maximum-sized physical extent, provided the verified accessor implements the
pinned flat guest memory and handles crossing a segment boundary. No page fault,
demand paging, overcommit or native capability relocation is introduced.

Every native host path satisfies the checked yield/call bound. This includes
hashing and validation, IR preparation, data initialization, start functions,
memory/table bulk operations, stack handling, imports, cancellation, checkpoint
and retirement. Guest instruction counts or cooperative guest calls cannot
replace that evidence. Imported operations either complete within their checked
bound or use the existing bounded asynchronous request/completion protocol.
No guest may extend its envelope or export an elastic-pool capability to a
fixed-tier service; copy or transfer uses its composed tag-free transport.

Epoch exhaustion retires the affected handle namespace without wrapping.
Closing a guest retires mutable caches and pending requests as well as memory.
Replacement and crash recovery must never combine one bundle's grants with
another bundle's execution or acknowledged state. A post-commit failure
does not promise automatic rollback: relaunching retained old bytes is a fresh
activation with current grants and compatible durable state.

## Performance and evidence

Start with R-14-013h's permitted decoded IR, indirect dispatch, AOT
superinstructions, bounded caches and proved SIMD. All used transformations
remain inside the interpreter's refinement and the host's yield proof.
Persisted cached IR is untrusted input; a matching key alone cannot bypass
validation. Within a running host, immutable results of verified validation can
be reused with the full artifact/profile identity and fresh authority checks.

Native service batching can remove per-element interpreter and IPC work.
Qualification includes argument validation, batching delay, copy/transfer,
service execution and result delivery. It preserves the same operation scope,
results, confidentiality and service capacity as the comparison. Bulk guest
backing normally uses the second memory class; a bounded first-class working
set is allowed when its measured gain pays its explicitly charged capacity.
No claim depends on a JIT or a newly loaded native helper.

Q34f fixes the workload before candidate measurements. It reports cold and
reused preparation, launch to first useful response and edit through changed
response under the concurrent desktop workload, with build, validation,
preparation, retirement, grant wait, execution and bridge costs separate.
Report both user elapsed time and time excluding explicit consent wait.
The [product gate](product-gate.md) owns limits and evidence tiers; host seconds
cannot become a device latency claim. No timing result exists in this contract.

The [Wasm execution contract](wasm-execution.md) selects the compact indexed
representation and sets its aliasing, trap, cache invalidation, reclamation and
poll obligations. Q34g owns those within the single interpreter's existing
proofs; Q34f owns the ablation and end-to-end comparisons, including regressions.
Published interpreter speedups are research inputs, not target measurements.

Acceptance exercises malformed closure/descriptor/module, incompatible ABI,
cache tampering or stale identity, forged/cross-instance/old handles, pending
consent during replacement, late service replies, nonterminating start functions,
bulk-operation maxima, deep guest stacks, memory growth failure, full staging
and host pools, cancellation, and crashes on each side of replacement commit.
It must show the old app survives pre-commit refusal, post-commit recovery
selects one compatible durable state, reuse never outruns its complete gate,
and unaffected guests and fixed-tier deadlines continue. Successful examples
include offline local build/run/change, fetched bundles under identical checks,
concurrent guests and explicit use of an existing native service.
