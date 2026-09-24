# Wasm execution and optimization contract

Status: **design selected; executable interpreter, proofs and target measurements open**.
R-14-013h in the [requirements register](../../requirements-register.md) owns
the execution profile. The [application-host contract](application-host.md)
owns activation, authority, replacement and resource failure. Q34g implements
this profile inside the one platform interpreter and proves it; Q34f qualifies
the complete application path; Q34h produces its guest bundles. These are
existing implementation owners, not completed work or additional engines.

## Research selection

Primary sources reviewed on 2026-09-23 are below. A source is a design or
experimental reference, never admission evidence. No source code, dependency
or runtime from this survey is incorporated. At incorporation, read the selected
revision's own licence closure and record it in THIRD-PARTY.md.

| Source | Useful result | Decision under this platform's requirements |
| --- | --- | --- |
| [Wasmi 2.0 engineering, 2026-09-01](https://wasmi-labs.github.io/blog/posts/wasmi-v2.0/) and [tagged changelog](https://github.com/wasmi-labs/wasmi/blob/v2.0.0/CHANGELOG.md) | Accumulators, compact value storage and simpler instance access reduce work; execution gains were measured on conventional processors | Use these representation ideas inside Q34g. The [bring-up reading](../userspace-porting.md#the-bring-up-wasm-interim-the-pin-and-what-its-ranking-reads-as-here) already pins this release; selecting it again earns no extra speedup. Do not copy its defaults, pointer calling convention or validation-disable option. |
| [WAMR fast-interpreter design, 2021](https://www.intel.com/content/www/us/en/developer/articles/technical/webassembly-interpreter-design-wasm-micro-runtime.html) and [WasmKit register-machine design](https://github.com/swiftwasm/WasmKit/blob/main/Documentation/RegisterMachine.md) | Translating stack operands into slots removes provider dispatches; local overwrites and branch joins need preservation moves | Use a bounded preparation pass and explicit alias/join cases in the same interpreter's refinement. An upstream implementation's test results do not prove this translation. |
| [Pulley accepted RFC](https://github.com/bytecodealliance/rfcs/blob/main/accepted/pulley.md) | Register bytecode, compact operands and superinstructions trade preparation cost for execution cost | Adopt the data-format principles. Do not import Cranelift as a trusted translator, deserialize an unchecked executable artifact or claim its proposed startup time. Preparation and reused launch remain separate measurements. |
| [Titzer, A Fast In-Place Interpreter for WebAssembly, OOPSLA 2022](https://arxiv.org/abs/2205.01183) | Direct execution with side metadata can reduce preparation and representation space | Keep as a startup/space comparison. A second shipping interpreter would conflict with the single-engine scope and add proof work; no automatic tier or extra production engine is selected. |
| [Lowther, Jacob and Singer, CHERI Performance Enhancement for a Bytecode Interpreter, 2023](https://arxiv.org/abs/2308.05076) | Pointer-size assumptions can create large interpreter overhead on Morello | Audit numeric cells, metadata and capability traffic on the actual purecap lowering. Morello's measurements are not this ISA's forecast. Never compress authority into an integer to recover space. |
| [Silverfir-nano source and feature matrix](https://github.com/mbbill/Silverfir-nano) | A current project offers separate interpreter and native-code engines with different feature coverage | Its native-code results cannot price pure interpretation; its current interpreter excludes SIMD. No replacement for the single proved engine or the pinned subset is selected. |
| [weval, Partial Evaluation, Whole-Program Compilation, PLDI 2025](https://cfallin.org/pubs/pldi2025_weval.pdf) and [producer interface](https://github.com/bytecodealliance/weval) | Specialization removes an inner interpreter by producing Wasm from Wasm | Select an untrusted guest-producer path under Q34h: specialize guest-language interpreters into ordinary validated Wasm, still executed by the one pure platform engine. Its reported SpiderMonkey gains use a different outer engine and are not this target's forecast. No guest-to-native output or new verified specialization tool is admitted. |
| [Wasm 3.0 release](https://webassembly.org/news/2025-09-17-wasm-3.0/), [standard profiles](https://webassembly.github.io/spec/core/appendix/profiles.html) and [implementation limits](https://webassembly.github.io/spec/core/appendix/implementation.html) | Typed references, tail calls and managed guest objects can avoid emulated language machinery; the standard permits implementation resource limits | Select 3.0 as the reference with a generation-fixed proved subset. Guest GC is eligible under the existing bounded-arena contract; upstream support is not evidence that this engine implements or proves it. |
| [Denis, Performance of WebAssembly runtimes in 2026](https://00f.net/2026/06/23/webassembly-runtimes-2026/) | Reproducible workload comparisons distinguish runtime modes and enabled language features | The WAMR result uses AOT and some variants use features outside the freeze. Neither is a pure-interpreter target estimate; use the comparison discipline, not its numbers. |

This design spends engineering on the already required interpreter's
representation, host binding and proof. It does not add a trusted optimizer,
new equivalence checker, prover or admission path to obtain speed. If a candidate
needs such an artifact solely for performance, R-05-065 excludes it. R-14-013b
selects the Wasm 3.0 reference and a generation-fixed allowlist; no threads and
R-14-013d's SIMD curation condition remain. The existing [proof-reuse assessment](../../assurance/proof-reuse/parsers.md#wasmcert-coq-type-safety-and-interpreter-refinement-with-concrete-boundaries)
still owns the unverified binary-parser, concrete numeric/SIMD and host-proof gaps.

## Wasm 3.0 inside the existing boundary

Q34g publishes a feature matrix naming the exact upstream definitions, concrete
executable cases, both theorem cases, resource limits and negative tests for
each enabled construct. Missing curation leaves a construct disabled. The
initial proved subset may be smaller than 3.0; the version name never enables
an upstream engine's defaults. All module and prepared-data identities include
the feature and numeric profile. A changed engine/profile enters at successor boot.

Typed references may remove redundant type checks when validation and the
runtime reference invariant prove them unnecessary; null checks and current
import authority still apply. Tail calls reuse bounded guest frames but still
poll on cycles. Recursive-type validation and exception unwinding use bounded
worklists. Memory64/table64 use logical indices over declared resident limits;
they add neither physical address bits nor overcommit. Multiple memories remain
separately bounded, including copies between them. Reference casts, exceptions
and externrefs cannot disclose native capabilities or bypass binding lifetimes.

For guest GC, select a nonmoving, binding-local mark/sweep arena with bounded
size classes (or proved bounded array representation), object counts, total
bytes, roots, mark bits and traversal storage. Cycles are traced within that
arena. Collection pauses the guest mutator, advances through bounded resumable
steps and yields to the host scheduler; it does not promise a short guest pause.
Host-held guest references are registered roots, frozen or updated under the
same proved protocol while collection is suspended. The proof covers reachable
object preservation, identity, complete root enumeration, sweep/reuse and every
root publication/removal, including outstanding callbacks. An allocation
failure has a declared bounded outcome. No emergency unbounded collection,
cross-binding tracing or resurrection of a retired import is permitted. This
implements R-14-015 rather than adding a managed native base.

The standard deterministic profile is a curation target, not an already proved
artifact. When admitted, it fixes generated NaNs and relaxed-vector choices;
growth failures still depend on resources. Strict instructions keep their own
results. Neither GC nor a numeric profile establishes source correctness,
linear-memory object safety or constant-time execution of secrets.

## Selected execution representation

1. **Prepare once, interpret data.** Validate the exact immutable module and
   prepare compact opcode/slot records, decoded immediates and resolved guest
   branch offsets. Record instruction boundaries and typed block results.
   Neither a branch offset nor a function index is a native PC. Bound the pass's
   work, scratch, record widths and expansion before allocating; malformed,
   oversized or unrepresentable input follows the existing typed refusal.
   Preparation executes no guest instruction or import. Persisted IR is
   untrusted and requires reconstruction or verified validation of both its
   structure and its correspondence to the exact validated module.
2. **Keep numeric values cheap without losing authority types.** Use numeric
   accumulators where the certifying backend can keep them live, compact scalar
   slots, and paired slots for admitted vector values. Guest references use
   checked logical indices into binding-owned metadata. Native capabilities
   stay in separately typed host state, never in numeric or float cells. This
   target has no scalar F/D register file to inherit an upstream calling
   convention from; any RVV use obeys the existing sink and context-clear rules.
   Measure spills and preservation moves at joins and calls.
3. **Dispatch through the fixed image.** An index reaches the immutable,
   composition-enumerated typed handler table. Select bounded fused forms
   such as local/immediate arithmetic and result stores against the frozen
   corpus; emit only references to existing handlers during preparation.
   The image-size budget includes every fused body and SIMD handler. The
   certifying lowering must establish constant native stack use across
   dispatch; an upstream tail-call feature or host optimizer is not evidence.
   Direct-threaded runtime code-pointer buffers keep the porting guide's
   unresolved TAL typing obligation and are not selected.
4. **Shorten metadata paths within a binding.** Resolve immutable local
   function metadata and instance-layout offsets during preparation/binding.
   Mutable tables and imported functions retain dynamic type, target and
   binding checks. A guard miss performs the ordinary checked operation.
   Cache entries carry the current dependency identity; every relevant table
   write, memory growth, host callback, suspension and replacement either
   invalidates that fact or proves it remains valid. No cache learns across
   labels or carries grants into another activation.
5. **Release what was prepared.** Module-owned storage may remain at a stable
   address while in use without being append-only for the host's lifetime.
   Guest data records hold checked offsets/indices, and host roots retain
   bounded ownership. Reclamation waits for all frames, suspended work, calls
   and permitted sharers, then follows containment, sweep and sanitization.
   Eviction affects only unused immutable data. Peak accounting includes old
   quarantined storage beside the replacement; it assumes no moving live
   native capabilities and no unbounded reference count or epoch wrap.

## Semantic and scheduling obligations

The preparation-to-execution relation is part of R-14-013a's existing
interpreter refinement. It relates guest state to slots, accumulators, control
records and private resumable state, including preservation moves when a local
is overwritten while its previous value is still needed. All shipped handler
configurations satisfy that relation and robust confinement; a baseline proof
beside an unproved optimized path is insufficient.

Fusion cannot reorder an import, suppress a trap, publish a store after an
earlier trapping instruction or expose unfinished bulk state. Integer division
and conversion traps, NaNs, signed zero, lane order and overlapping memory/table
copies retain the pinned semantics. A handler may use several native
instructions for one vector opcode; no fast-math or relaxed-SIMD substitution
is allowed. A vector path remains unavailable until its curated semantics and
concrete execution are both covered.

Each load/store checks the guest's current byte length with non-wrapping
effective-address arithmetic before accessing backing. A fast same-segment
case and a cross-segment case implement the same flat memory; a reserved or
rounded host extent is not extra guest memory. Proved redundant-check removal
must preserve the exact trap and preceding effects. Hoisting a check over an
effect or using a CHERI exception as an ordinary Wasm trap is not justified by
arena confinement. Memory growth refreshes cached backing and length before
any access; failed growth preserves the pinned failure result.

The cost certificate covers native work between polls, including dispatch,
fusion, spills, helper calls and cache misses. Every cycle in the guest control
graph still reaches a poll within the native bound. Preparation, long bulk
operations and cleanup also yield through private resumable state. Guest fuel
may account for guest work, but does not replace this certificate. Mutable
state cannot become observable through an import while an operation is only
partly performed.

## Coarse native services and placement

### Whole-loop handlers in the interpreter

Select a finite set of typed integer map/reduction and byte-scan loop forms
against Q34f's frozen corpus. This extends the existing AOT superinstruction
mechanism from a few opcodes to a complete recognized loop. A fixed handler
uses data operands, a count and checked memory descriptors; it performs a
bounded chunk of work per poll without dispatching each original instruction.
Recognition is a translation case of the original interpreter refinement, not
a new trusted optimizer. Unmatched loops remain ordinary guest instructions.

The theorem must establish the exact source loop behavior, including induction
overflow, zero trips, overlapping operands, early exits, aliasing, traps and
effects before a trap. A guard selects the slow path before any effect; it
cannot partially execute then restart. A check that would trap on a later
iteration cannot be hoisted ahead of earlier stores. Resumption re-establishes
mutable facts; private progress state records exactly the guest steps already
performed. Floating reductions receive no reassociation. Fixed code, pattern
count and expanded IR are budgeted; no guest-specific native code or handler
registration exists. Q34g proves recognition and execution together.

### Remove a nested language interpreter at Build

Q34h selects a weval-style Wasm-to-Wasm specialization route for closed guest
programs where an inner language interpreter otherwise runs inside the outer
Wasm interpreter. Known program bytes drive partial evaluation; unresolved
dynamic code keeps the original inner-interpreter behavior inside the guest.
Specialized functions and guest table entries remain Wasm data, never host PCs.
The producer is untrusted for guest semantics and confinement: the existing
validator and proved interpreter supply the latter, while source correspondence
needs separate R-14-005 evidence. Keep both outputs in the qualification corpus.

On-device specialization may itself run as a guest tool under the same engine,
avoiding a new verified speed-only tool. Closed-program initialization happens
during Build with declared immutable inputs, no live application grants and
bounded work/output, using the pure interpreter. An upstream Wizer path that
uses native compilation is not the on-device implementation. Serialize only
guest data; reject captured capabilities, handles or host snapshots. Prepare
still runs no guest start function. A fetched result gets the same full
validation and fresh grants as any other untrusted bundle. Charge compilation,
initialization, output growth and fallback execution separately.

### Explicit service batches

The largest workload-specific gains can come from making an existing native
service do a bounded batch instead of interpreting a per-element guest loop.
Q34f uses explicit typed imports with the same results, operation scope and
current grants. It charges argument checks, serialization, copying, queue and
batch-fill delay, native execution and result delivery. A new service interface
is a successor-generation change; a runtime operation cannot supply machine
code, choose an arbitrary native target or grow the fixed-tier reservation.
Keep secrets out of ordinary guest imports under R-14-013f.

For numeric guest work, Q34h may produce fixed-width SIMD only inside the
actually admitted subset. Q34g compiles its fixed interpreter handler bodies
through the ordinary native toolchain; guest modules remain interpreted data.
It does not expand the guest dialect to match an upstream default.
Do not count SIMD and native offload on the same removed guest work twice.

Keep interpreter bodies in the first memory class and bulk backing in the
second. Compare explicitly reserved first-class IR or hot numeric state with
the default placement, charging bytes and bank grants in the complete desktop
composition. A module-dependent working set never causes automatic migration
or a change to another application's reservation.

## Qualification and refutations

Q34f freezes modules, sources, inputs, expected observable results, compiler
flags, handler set, feature profile, import grants and composition before
measurement. Its cases include scalar arithmetic, branch-heavy code, local
aliasing/joins, direct and mutable indirect calls, numeric arrays, bulk memory,
a small startup-dominated app and a realistic edit/build/run workflow. The
selected native-service case includes small and large batches. Include
concurrent unrelated guests and repeated instances of one module.

Measure a minimal configuration of the same proved engine and isolate each
selected representation, fusion, whole-loop, specialization, cache, SIMD,
batching and placement change. Freeze the unspecialized and specialized guest
programs together; check their observable outputs and dynamic fallback cases.
Report whole-loop coverage and all residual interpreter work, not just a
matched microkernel. Include GC-heavy cyclic graphs, retained host roots,
maximum type graphs, tail-call cycles, exception unwinding, memory64 overflow
and multi-memory aliasing whenever their feature is enabled.
These are qualification builds; a composed image still ships one engine artifact.
Keep workload, guest language, authority and results fixed; report unsupported
cases rather than silently removing them. A service comparison includes the
guest frontend on both paths. Record individual regressions and distribution
tails as well as any geometric mean. A source reading or host benchmark is
research evidence; target-model cycles and qualified silicon retain the
[product gate's](product-gate.md) distinct evidence tiers.

Besides the application-host lifecycle campaign, the acceptance set includes:

- IR operands outside their slot bounds, branches into operands or with wrong
  result arity, unknown handler indices and stale format/handler identities;
- old local values consumed after overwrite, multi-result joins, call returns,
  scalar/vector slot overlap and attempts to treat guest data as a capability;
- overflowed addresses, exact-end and cross-segment accesses, grow success and
  failure, overlapping copies and a store preceding a later trap;
- mutated indirect-call tables, wrong signatures, stale imports and guard
  invalidation during host calls or suspension;
- full IR/cache budgets, eviction while another instance is using data,
  cancellation inside a fused loop and reclamation with a live continuation;
- maximum native work between polls, including an infrequent slow path, and
  the same fixed-tier deadlines under concurrent preparation and execution.

Q34g supplies machine-checked refinement, confinement and exact assumption
audits for these behaviors; differential and negative tests supplement them.
Q34f records preparation, first response, repeated execution, replacement,
maximum poll interval, dispatch/native-instruction counts, memory traffic,
shared/private/transition bytes and total frontend/service cost. The
[performance estimates](../../performance/performance-estimates.md#wasm-recovery-evidence-and-estimates)
state conditional planning ranges; no implementation milestone or target
performance verdict is closed by this contract.
