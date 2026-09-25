# Wasm execution and optimization contract

Status: **design selected; executable interpreter, proofs and target measurements open**.
R-14-013h in the [requirements register](../../requirements-register.md) owns
the execution profile. The [application-host contract](application-host.md)
owns activation, authority, replacement and resource failure. Q34g implements
this profile inside the one platform interpreter and proves it; Q34f qualifies
the complete application path; Q34h produces its guest bundles. These are
existing implementation owners, not completed work or additional engines.

## Research selection

Primary sources reviewed on 2026-09-24 are below. A source is a design or
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
| [Silverfir-nano source and feature matrix](https://github.com/mbbill/Silverfir-nano) | A current project offers separate interpreter and native-code engines with different feature coverage | Its native-code results cannot price pure interpretation; its interpreter excludes SIMD and GC. Use its fixed register-window/local-cache and fusion ideas as references, with no upstream runtime substitution or transferred JIT score. |
| [weval, Partial Evaluation, Whole-Program Compilation, PLDI 2025](https://cfallin.org/pubs/pldi2025_weval.pdf) and [producer interface](https://github.com/bytecodealliance/weval) | Specialization removes an inner interpreter by producing Wasm from Wasm | Select an untrusted guest-producer path under Q34h: specialize guest-language interpreters into ordinary validated Wasm, still executed by the one pure platform engine. Its reported SpiderMonkey gains use a different outer engine and are not this target's forecast. No guest-to-native output or new verified specialization tool is admitted. |
| [Wasm 3.0 release](https://webassembly.org/news/2025-09-17-wasm-3.0/), [standard profiles](https://webassembly.github.io/spec/core/appendix/profiles.html) and [implementation limits](https://webassembly.github.io/spec/core/appendix/implementation.html) | Typed references, tail calls and managed guest objects can avoid emulated language machinery; the standard permits implementation resource limits | Require the full Core 3.0 binary language. Standard quantitative limits and explicit imports preserve the host boundary; missing proofs block release, not features in the advertised language. |
| [Denis, Performance of WebAssembly runtimes in 2026](https://00f.net/2026/06/23/webassembly-runtimes-2026/) | Reproducible workload comparisons distinguish runtime modes and enabled language features | The WAMR result uses AOT and some variants use features outside the freeze. Neither is a pure-interpreter target estimate; use the comparison discipline, not its numbers. |

This design spends engineering on the already required interpreter's
representation, host binding and proof. It does not add a trusted optimizer,
new equivalence checker, prover or admission path to obtain speed. If a candidate
needs such an artifact solely for performance, R-05-065 excludes it. R-14-013b
requires the complete Core 3.0 binary language. The [proof-reuse assessment](../../assurance/proof-reuse/parsers.md#wasmcert-coq-type-safety-and-interpreter-refinement-with-concrete-boundaries)
still owns the parser, numeric/SIMD, GC and host-proof gaps; they block completion.

## Mathematical research handoff

The [mathematical survey](../../background/open-math-conjectures.md#computational-performance-and-wasm-workloads)
supplies candidate algorithms and conditional limits for future Q34f/Q34h workload
selection. It supplies no interpreter theorem or throughput credit. The leads below
are deferred unless a frozen application or producer workload contains the named
operation and profiling exposes its cost. They add no feature or proof obligation
to the selected Core 3.0 engine. If a candidate enters the existing engine,
Q34g's refinement covers it; a native service retains its own refinement owner
and Q34d's applicable yield evidence. A guest-library change remains ordinary
validated Wasm and claims no source correspondence without its own evidence.

| Research input | Prospective use and missing connection |
| --- | --- |
| [ETH and SETH](../../background/open-math-conjectures.md#exponential-time-hypothesis-and-strong-exponential-time-hypothesis) | Use only to explain a selected exact-search workload's conditional scaling limit. Record the reduction, variable/instance-size parameter and deterministic or randomized model before transferring a lower bound. Neither hypothesis is an admission premise or a proof that a bounded search instance is infeasible; preprocessing, refusal and cancellation remain measured work. |
| [Orthogonal Vectors](../../background/open-math-conjectures.md#orthogonal-vectors-conjecture), [weighted APSP](../../background/open-math-conjectures.md#weighted-all-pairs-shortest-paths-hypothesis) and [3SUM](../../background/open-math-conjectures.md#modern-3sum-conjecture) | For a selected string, graph or geometry workload, freeze dimension, weight/number representation, approximation tolerance and actual reduction. OnlineOV and preprocessed-universe 3SUM have separate preprocessing/query models; the August 3SUM tradeoff improves reusable storage/query costs while retaining quadratic preprocessing. Charge construction and resident storage across the declared query count. Prediction-assisted APSP also needs prediction-production cost and the worst permitted error; good predictions supply no unconditional deadline. Ordinary matrix products do not supply min-plus APSP. No matching workload or general interpreter lower bound is established here. |
| [Online Boolean matrix-vector multiplication](../../background/open-math-conjectures.md#online-boolean-matrix-vector-multiplication-conjecture) | A bounded-VC-dimension dynamic graph is a possible restricted consumer. Establish that dimension bound, Boolean-semiring semantics and output-before-next-input order; charge preprocessing, total work and worst per-operation poll interval separately. Numerical inference and a fully known composition do not satisfy the same online problem. |
| [Dynamic BST optimality](../../background/open-math-conjectures.md#dynamic-optimality-of-binary-search-trees) | Compare a bounded in-label map only after freezing the access sequence model and initial state. A competitive or amortized result leaves individual traversal/rebalance costs, resumability, exhaustion and native yields unproved. The persistent storage index has different costs and is not selected for replacement. |
| [Hashing advances](../../background/open-math-conjectures.md#hashing-beyond-the-uniform-probing-conjecture) | For a fixed-capacity application table, separate successful/unsuccessful search, insertion, deletion, tombstones, resizing and rebuilding. The relaxed probe-order theorem and the `opthash-rs` implementation have different scopes. A qualified implementation still needs a representation invariant, complete operation semantics, finite backing and worst-case bounded chunks; expected probes supply no native WCET. |
| [Static dictionaries and dynamic ordered indexes](../../background/open-math-conjectures.md#compact-static-dictionaries-and-dynamic-ordered-indexes) | Immutable prepared metadata is a possible static consumer; a clustered guest index is a separate dynamic one. Establish the word width, universe, payload and density/gap-entropy premises, and include construction workspace, randomized seeds and auxiliary tables. Prove decoded lookup/update correctness and charge purecap representations. Worst-case word-RAM static lookup and expected amortized dynamic operations each still need target costs and poll bounds. |
| [Dynamic entropy-encoded arrays](../../background/open-math-conjectures.md#dynamic-entropy-encoded-arrays) | The FOCS 2026 accepted result is a candidate for a selected compressible symbol array, with a proved encode/decode/update relation and qualification of its resizable-buffer simulation over finite physical backing. Charge metadata, capabilities, initialization, failure and cancellation; expose content-dependent size only inside the authorized observation model. High-probability bounds do not establish deterministic capacity or per-phase time, and hardware virtual memory is not itself a prerequisite. |
| [Directed shortest paths](../../background/open-math-conjectures.md#directed-shortest-paths-below-the-sorting-barrier) | For an identified nonnegative-weight SSSP kernel, compare concrete sizes before importing a construction. A local proof would connect encoded weights and overflow, graph representation, every density/fallback branch, scratch and charged operations to executable behavior. The C-HD Lean artifact's formal density branch and exact-real RAM model do not establish its broader paper range, linear space, target cycles or a local Rocq theorem; supplied replay records are not local acceptance. |
| [Catalytic memory](../../background/open-math-conjectures.md#the-power-of-catalytic-memory) and [graph/sequence algorithms](../../background/open-math-conjectures.md#catalytic-graph-and-sequence-algorithms) | Compiler graphs, including general-graph maximum matching, or text processing are potential private-region experiments. Freeze clean and catalytic storage, input replay count and the selected algorithm's field/program model. A useful local refinement covers exact restoration, capability tags and object invariants, quiescence, cancellation/fault behavior and all restoration work. Polynomial-time catalytic matching does not remove the catalyst's physical capacity charge; multi-pass results give no one-pass space saving. The withdrawn tree-evaluation claim supplies no premise. No region is lent or physical capacity reduced by this reading. |
| [Integer multiplication](../../background/open-math-conjectures.md#optimal-bit-complexity-of-integer-multiplication) | Consider only after a large exact-arithmetic guest or producer workload is identified. Compare finite operand sizes with simpler algorithms and prove limb representation, carries, output, scratch and bounded execution. The bit-model upper bound, open matching lower bound and conditional transposition route do not choose a fixed-width kernel or confer secret-data timing evidence. |

Q34f owns any selected end-to-end comparison, including preparation, the complete
guest frontend and residual dispatch; Q34h owns producer-side integration. An
unselected lead stays in this table rather than expanding their priced scope.
The [compute research handoff](compute-semantic.md#arithmetic-research-handoff)
owns algebraic rewrite candidates, and the [inference handoff](../../performance/inference-demand.md#research-handoff-to-unwritten-inference-proofs)
owns attention and matrix-kernel demand implications.

## Wasm 3.0 inside the existing boundary

Full Core 3.0 is the release target, including all prior features, fixed/relaxed
SIMD, recursive GC types, subtyping, typed references, tail calls, exceptions,
extended constant expressions, multiple memories and memory64/table64. Q34g's
inventory maps every standard case and feature interaction to its upstream
definition, executable path, both theorem cases and positive/negative tests.
An unimplemented or unproved case keeps the engine incomplete. Development
subsets may assist construction but cannot satisfy the release gate. SIMD may
use exact scalar fallbacks; it cannot disappear to accommodate a backend.

The upstream [implementation-limit rules](https://webassembly.github.io/spec/core/appendix/implementation.html)
permit finite resources but explicitly forbid dropping individual features.
Publish quantitative limits, qualify them on unchanged independently produced
modules and prohibit zero/unusable limits that hide an omitted feature. Guest
struct and array layouts are derived from validated types within these limits,
not selected from a composition-time list of permitted guest types. The host
can wrap raw `.wasm` bytes locally without modifying them or requiring a source
compiler, custom section or vendor signature. Its descriptor supplies resource
policy and explicit import grants. Full Core support is distinct from WASI,
the Component Model, JavaScript/DOM and thread/shared-memory proposals. A valid
module needing an absent host API gets an import diagnosis; Core conformance
cannot manufacture that API or authorize it.

The numeric implementation uses the standard DET choices while accepting every
Core 3.0 instruction. These are results permitted by the full language and need
no producer changes. The exact semantics, numeric choices and engine identity
remain generation-fixed; changed engines enter through successor admission.

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

The complete deterministic numeric implementation remains open proof work.
It fixes generated NaNs and relaxed-vector choices;
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
   Preparation executes no guest instruction or import. The first implementation
   persists the raw immutable module and reconstructs IR through verified
   validation/preparation after restart. It never restores persisted prepared
   records. Within the running host, reuse its own immutable validated results
   under the full identity and fresh-grant checks. This selects R-14-013h's
   reconstruction arm and avoids a second persisted-IR format, parser and
   correspondence proof. A later restoration path needs measured cold-start
   benefit and separately priced qualification before it is implemented.
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

## Automatic execution of unchanged modules

The selected stronger execution path keeps several live values in actual native
registers across handler dispatch, rather than merely calling memory slots
"registers". Its initial design budget is four numeric operand cells and two
frequently used numeric locals, with paired cells for `v128` and separate typed
reference/root state. Q34g may choose a smaller window after backend/size
qualification; reducing it earns no assumed gain. Handler variants name these
fixed locations, so fused expressions need no dynamic slot loads for internal
values. Local-use counts weighted by bounded loop depth choose candidates at
Prepare; no runtime hardware predictor or per-app native code is added.

Bounded preparation folds providers into consumers, propagates constants and
copies only across proved effect-free regions, and chooses arithmetic/address/
compare-branch templates plus their register-state variants. All templates and
transitions are native image code compiled before admission. A template miss,
large index, deep operand stack or exhausted optimization budget emits the
same engine's general record forms. Those forms support the entire language;
optimization success is never a compatibility condition. This needs neither
source nor a special producer flag. Whole-loop recognition is another automatic
case, while explicit service imports and weval remain optional producer paths.

Spill/fill, join permutations and call/exception transitions re-establish one
exact guest state. References are published to complete root maps before any
GC/helper/yield that can inspect them; numeric bits never substitute for roots
or native capabilities. Cache aliases cannot outlive overwritten locals.
Exceptions preserve payloads and frames, and fallback never repeats an effect.
GC, imports, growth and suspension remain barriers for invalidatable facts.
Every fused body preserves original trap order and strict floating results.
Instruction-pointer updates may be combined within a fixed fused body, with
explicit source positions for traps and resumes. No speculative load,
runtime handler copying, executable patching or code emission is selected.

The existing certifying backend must prove a constant-stack intra-engine
calling convention that keeps the window live, under the native TAL and context
clear rules. This is backend work, not a request to trust LLVM `musttail` or
`preserve_none`. If generated native code spills the window at every dispatch,
the purported gain disappears and Q34f records the failure. Each precompiled
variant consumes image capacity; the handler selector has a finite work budget.
The preparation relation and every variant belong to the original engine's two
theorems, without a separate trusted performance optimizer or checker.

Sources and limits of the inference:

- [Silverfir's recorded interpreter design](https://github.com/mbbill/Silverfir-nano/blob/f3f5c20f49dc85fdbb5866d4abb895c2734c64a1/mcts_mem/silverfir/compiler.alt/fast-interpreter/dispatch.md)
  and [local-cache notes](https://github.com/mbbill/Silverfir-nano/blob/f3f5c20f49dc85fdbb5866d4abb895c2734c64a1/mcts_mem/silverfir/compiler.alt/fast-interpreter/hot-local-cache.md)
  distinguish physical register residence from slot IR and show why fusion and
  caching must be evaluated jointly. These are historical design notes, not a
  claim that its current engine or our backend implements this exact path.
- [Deegen, OOPSLA 2026](https://fredrikbk.com/publications/deegen.pdf)
  demonstrates offline generation and register pinning in fast interpreters.
  Its Lua interpreter reports 1.31 times LuaJIT's interpreter on its corpus;
  its JIT results and missing GC implementation supply no evidence here.
- [Ertl and Paysan, ECOOP 2024](https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ECOOP.2024.14)
  isolates instruction-pointer dependencies. Its OoO-dependent gains and
  runtime code-copying context are not transferred; only fixed-body update
  coalescing is a candidate here.

Q34f measures this path jointly against the short-fusion/single-accumulator
configuration, as well as ablating its pieces. The scalar planning target in
[performance estimates](../../performance/performance-estimates.md#automatic-scalar-execution-target)
is incremental over that already optimized reference. No target measurement
currently establishes it, and no unmatched module is dropped from the corpus.

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
is allowed. Every vector path needs curated semantics and concrete execution proofs;
missing coverage blocks the full-engine gate.

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

For numeric guest work, Q34h may produce standard fixed-width SIMD for the full
Core 3.0 target. Q34g compiles its fixed interpreter handler bodies
through the ordinary native toolchain; guest modules remain interpreted data.
Its private execution records are not a guest dialect or an input requirement.
Do not count SIMD and native offload on the same removed guest work twice.

Keep interpreter bodies in the first memory class and bulk backing in the
second. Compare explicitly reserved first-class IR or hot numeric state with
the default placement, charging bytes and bank grants in the complete desktop
composition. A module-dependent working set never causes automatic migration
or a change to another application's reservation.

## Qualification and refutations

### Shared upstream corpus

Source readings here are dated 2026-09-24; these are candidate revisions,
not incorporated dependencies or local qualification evidence.

- [Official Core tests and generators](https://github.com/WebAssembly/spec/tree/608711107b7f1edb13efd57b7d79b49477462d36/test/core)
  and the [reference interpreter](https://github.com/WebAssembly/spec/tree/608711107b7f1edb13efd57b7d79b49477462d36/interpreter)
  supply test syntax, expected behavior and SIMD case generation. The selected
  [test licence](https://github.com/WebAssembly/spec/blob/608711107b7f1edb13efd57b7d79b49477462d36/test/LICENSE)
  and [interpreter licence](https://github.com/WebAssembly/spec/blob/608711107b7f1edb13efd57b7d79b49477462d36/interpreter/LICENSE)
  are Apache-2.0. Filter the exact Core 3.0 snapshot explicitly; a newer tree
  is not the pinned semantic edition merely because its tests run.
- [wasm-tools](https://github.com/bytecodealliance/wasm-tools/tree/fe12b7d36b0ec7c79ff6a51e838617a0a2ae25cc)
  supplies `json-from-wast`, `smith`, `mutate` and `shrink`, avoiding a new test
  syntax reader, random module generator and reducer. Its
  [MIT option](https://github.com/bytecodealliance/wasm-tools/blob/fe12b7d36b0ec7c79ff6a51e838617a0a2ae25cc/LICENSE-MIT)
  is available beside its Apache offers. Pin feature configuration, seeds,
  imports and resource limits; disable threads, components and proposals outside
  the selected Core 3.0 language without disabling its GC, SIMD, exceptions or
  64-bit index features. Record unsupported generator cases explicitly.

Q34g owns one fixture manifest, upstream-to-local runner and failure reducer.
Each fixture binds module bytes, feature, expected validation/result/trap,
numeric profile, imports, resource limits and provenance. Q34f consumes those
identities and adds lifecycle/host cases; Q34h adds source/output identities
and producer-specific cases. No consumer implements another core validator or
duplicates the core conformance campaign. Host tools remain untrusted test
producers, never native admission dependencies. Their agreement establishes
neither complete coverage nor either engine theorem. Qualification, feature
mapping, local refusal cases and full semantic proofs remain charged to their
existing owners; SpecTec and WasmCert receive no second reuse discount.

### Target measurements

Q34f freezes modules, sources, inputs, expected observable results, compiler
flags, handler set, feature profile, import grants and composition before
measurement. Its cases include scalar arithmetic, branch-heavy code, local
aliasing/joins, direct and mutable indirect calls, numeric arrays, bulk memory,
a small startup-dominated app and a realistic edit/build/run workflow. The
selected native-service case includes small and large batches. Include
concurrent unrelated guests and repeated instances of one module.

Measure a minimal configuration of the same proved engine and isolate each
selected representation, fusion, register-resident execution, whole-loop,
specialization, cache, SIMD,
batching and placement change. Freeze the unspecialized and specialized guest
programs together; check their observable outputs and dynamic fallback cases.
Report whole-loop coverage and all residual interpreter work, not just a
matched microkernel. Include GC-heavy cyclic graphs, retained host roots,
maximum type graphs, tail-call cycles, exception unwinding, memory64 overflow
and multi-memory aliasing as required full-language cases, including feature
combinations.
These are qualification builds; a composed image still ships one engine artifact.
Use the minimal baseline, the selected combined configuration and one-at-a-time
removals of each selected mechanism. Add targeted combinations where effects
interact, especially fusion/register state, GC/host roots and suspension/cache
invalidation; do not run the Cartesian product of every performance toggle.
The full semantic interaction campaign and proof of the combined configuration
remain required. One versioned target capture may feed several analyses only
when module, engine, profile, workload and composition identities match.
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
