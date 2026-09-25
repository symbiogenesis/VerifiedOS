# Bounded compute pilot semantic contract

This is the Q30a interface accepted for implementation planning alongside the
[feature audit](../compute-feature-map.md). Q30b and Q30c remain blocked on their
listed foundations. All sizes and performance cutoffs here are prospective
qualification thresholds, not measurements. This document neither admits an
instruction nor changes R-13-018a through R-13-018c.

## Producer and certifier interface

The immutable `ComputeClosure` contains the original source closure or original
SPIR-V bytes, frozen language/environment identifiers, included headers,
preprocessor definitions, all compiler/linker options, library source identities,
entry signatures, specialization values, pass witnesses, generated object/image
digests and generation identity. For a source build, retaining translated IR
alone is insufficient. HIP adaptation and library substitution are additional
correspondence edges, not exemptions. An original-IR package claims IR
correspondence, not correspondence to source it never supplied.

Each `KernelContract` binds that closure to the entry's argument types and
address spaces, readable/writable ranges, alias policy, initialization facts,
permitted dimensions/offsets, group geometry, local/private peaks, logical
barrier phases, atomic actors, numerical function, observable errors and
worker/schedule identity. Each lowering edge supplies a checked refinement of
this contract. The endpoint is the ordinary final-image derivation and tier
evidence; a frontend validator or test suite cannot act as a new trust root.

The certifier checks both terminating output and the trace: memory effects,
atomic returned values, barrier ordering, host-visible event transitions and
errors. Source undefined behavior must be excluded by the admitted preconditions.
Translation cannot justify an unsupported source construct by assigning it an
arbitrary result. Secret-dependent branches, addresses, loops, optional work
and resource failures retain the existing binary CT obligation. Public pilot
inputs do not establish secret-data qualification.

Q30d owns correspondence/checker integration only for the exact pilot source
subset and these interfaces. Existing compiler/source semantics and certifier
metatheory retain their M/U-series owners. Discovering a missing semantic
foundation or new trusted parser/proof assumption reopens the plan before
implementation; the bounded Q30d estimate cannot absorb a new proof program.

## Execution and memory interface

Work-items are logical states, not physical lanes. A scalar loop or RVV packet
may implement them when the simulation preserves IDs, masks and visible effects
for all permitted vector lengths. Work-groups execute on a fixed owned worker;
groups may be serialized. Launch geometry cannot change a worker assignment,
capability edge or slot budget. Global offsets are checked with overflow-free
arithmetic before deriving IDs.

| Space | Capability and lifetime contract |
| --- | --- |
| Global | Manifest-delegated buffer/sub-buffer ranges, with explicit reader or exclusive writer borrows held through completion. Host access cannot race a queued writer. No capability can be reconstructed from a numeric SPIR-V address. |
| Constant | Read-only closure data or a read-only borrowed argument. Any producer/global alias still lacks write authority while this borrow is live. |
| Local | One zeroed group scratch region, shared only by that group's logical work-items. A new group receives a fresh lifetime; all prior references are dead before reuse. |
| Private | Per-item registers and bounded spills, with disjoint logical ownership even when physical storage is reused. Initialization is proved before each read. |

Address-space casts preserve these restrictions. The pointer representation at
the SPIR-V input is a typed producer representation, not a 64-bit capability
ABI. The checked lowering introduces the platform's actual purecap type and
bounds, preserving all allowed aliases; it rejects a pointer escape or integer
cast that would require authority not held. Width/layout correspondence is
part of the witness, not inferred from `Physical64`.

For a barrier, all work-items reach the same dynamic barrier instance before
any crosses it. The producer proves uniform phase participation for every
declared input; a divergent barrier is an admission failure. Local/global fence
flags induce the corresponding happens-before/visibility edges over the actual
target memory model. An inactive tail item still participates in every required
barrier and merely suppresses its out-of-range data operation. No host spin
loop or cross-group rendezvous supplies an unproved progress assumption.

Legacy 32-bit atomics are lowered as indivisible operations over a bounded
serialized owner. The actor set includes every permitted work-item, work-group,
queue and host participant, not only one selected kernel. Pilot buffers forbid
concurrent host access and have one owning worker; a change in either condition
reopens the proof. The simulation chooses a standard-allowed serial order,
preserves old-value results and memory edges, and proves every admitted request
finishes within its scheduled bound. Merely placing an ordinary load/store
inside one work-item is not an atomic implementation. Device/system-scope C11
atomics remain outside the pilot until their complete actor model is qualified.

## Handles, submission and lifetime

A handle is a checked tuple of pool kind, slot, non-wrapping lifetime identity
and owner. Its generation is part of the comparison. Slots move through free,
bound, queued, running, terminal, retiring and zeroed/free states. Retained
references and in-flight borrows delay retirement. Cancellation is a platform
containment action, not a claimed standard OpenCL cancel API: it makes affected
events terminal with an error, drains the owned worker, revokes borrows,
zeroizes private/local state and only then permits reuse. Restart invalidates
all old handles and cannot relabel failed work as successful.

Submitting validates the kernel identity, argument capabilities, checked
dimension arithmetic, wait-list graph, pool reservation and fixed schedule
before publishing a queue entry. Either the full reservation commits or no
visible partial submission remains. Acyclic wait dependencies and bounded
declared external producers establish progress. An arbitrary user event may
remain pending under standard semantics; an operation promising a deadline
may depend only on a producer whose completion/error deadline is admitted.

Program creation never grants executable authority. Runtime source objects may
hold source data, but build/compile reports the absent compiler. A program
binding selects an immutable admitted entry by closure identity. A malformed
binary gets `CL_INVALID_BINARY`; a well-formed compatible binary absent from
this generation gets the adapter's `ProgramNotAdmitted`, mapped to
`CL_INVALID_OPERATION` with that diagnostic. The latter is an explicit
standard-API divergence, not a claim that valid bytes are malformed. HIP module
loading and runtime compilation receive `hipErrorNotSupported` for the same
case. A producer can build a successor generation using the ordinary install
path. A newly returned data handle cannot run in the current generation.

### Error and negative-case contract

Standard parameter checks follow the selected API's precedence. The table
fixes isolated one-fault qualification cases; multiple invalid parameters do
not justify inventing a precedence the standard leaves unspecified.

| Condition | Observable result | Required state afterward |
| --- | --- | --- |
| Backing allocation pool full | Native typed exhaustion; `CL_MEM_OBJECT_ALLOCATION_FAILURE`, `hipErrorOutOfMemory`, or `HIPBLAS_STATUS_ALLOC_FAILED` at creation | No object/borrow published; existing work unaffected. |
| Queue/event/metadata capacity full | Native typed exhaustion; `CL_OUT_OF_RESOURCES` / `hipErrorOutOfMemory`; diagnostic names the exhausted pool | No hidden wait, fallback allocation or foreign-pool borrowing. |
| Stale/released/wrong-owner handle | Appropriate `CL_INVALID_CONTEXT`, `CL_INVALID_MEM_OBJECT`, `CL_INVALID_KERNEL`, `CL_INVALID_EVENT` or `CL_INVALID_COMMAND_QUEUE`; HIP invalid resource handle; BLAS invalid/not-initialized handle as specified | No dereference or capability derivation from the supplied handle. |
| Bad range, shape, alignment, argument or overlapping copy | Applicable standard invalid-value/size/argument/alignment/overlap result | No out-of-bounds access or partial command publication. |
| Forbidden input/output alias or cycle | Producer rejection when static; runtime adapter diagnostic `AliasConflict` / `WaitCycle`, mapped to `CL_INVALID_OPERATION` / `hipErrorInvalidValue` | Explicit compatibility restriction; no silent serial execution with different semantics. |
| Uninitialized input, nonuniform barrier or unbounded loop | Admission rejection identifying the failed precondition | No runnable entry is produced. |
| Failed dependency / containment with work in flight | OpenCL negative event state and wait-list execution error; HIP asynchronous failure visible at query/synchronize, never `hipSuccess` | Dependent work suppressed; retained resources released only after drain/revocation. |
| Tampered source/options/library/certificate/image/program binding | Ordinary admission rejection | No adapter-specific bypass or successful executable handle. |
| Unsupported feature or numeric mode | Producer diagnostic names feature and owner; runtime optional-feature request uses its standard absence error | No degraded numeric mode, ignored flag, new thread or new authority. |

## Fixed resource and benchmark domain

One pilot compartment delegates one logical compute device and one worker at a
time. Use the V class for the baseline. An M-class comparison requires the
separate matrix admission gate and its checked operation; running an RVV loop
on an M-class core is not matrix acceleration. Both source/IR routes and HIP
share this device, dispatch path and backing plan.

| Resource | Pilot limit and accounting rule |
| --- | --- |
| Contexts/queues/programs/kernels | 1 context, 2 host in-order queues, 4 program handles, 8 kernel handles. Programs point to immutable admitted entries. |
| Buffers | 16 live object slots, each at most 8 MiB, aggregate backing at most 32 MiB. Sub-buffer metadata consumes an object slot and aliases existing backing. |
| Commands/events/waits | 16 outstanding commands across queues, 32 live events, 8 predecessors per command. Retained terminal objects still count. |
| Group and geometry | At most 3 dimensions, local product at most 64, each global dimension at most 4096, checked total work-items at most 2^20. C 1.2 global dimensions are divisible by local dimensions; tails use padded launches plus logical bounds. |
| Local/private/arguments | 16 KiB local scratch per active group, 1 KiB private spill per logical work-item, 1 KiB argument packet. Reject excess at admission; include padding and cleanup storage. |
| Metadata and callbacks | At most 1 MiB aggregate for adapter metadata, callback records, error records and staging; no uncharged recursion, variable stack or string growth. |
| Executable/store/proof | Additional executable bytes at most 8 MiB and source/certificate/store closure at most 64 MiB, measured against the direct implementation with identical kernels and composition. Ordinary proof-checking budgets still apply separately. |

The composer calculates the actual simultaneous peak from these owners;
adding limits is not a new manually maintained memory-plan total. A bound
cannot be reduced after seeing a failing result to call the same case a pass.
Failure returns a named gap or a newly reviewed, explicitly smaller claim.

### Kernels, numeric oracle and operations

All source variants use the same specified operation order. Default build
disables fast relaxed math, unsafe reassociation, finite-only assumptions and
implicit contraction; explicit `fma` is fused. FP32 uses round-to-nearest,
ties-to-even, gradual underflow, infinities, quiet NaNs and signed zeros.
Signaling NaNs may be quieted without a payload-equality claim. Hardware lacking
one of these behaviors needs a certified helper with its own time/storage bound;
scalar floating point is not inferred from vector support.

The primary comparator is **bit equality** to an independent software
implementation of the stated FP32 step sequence for finite results, infinities
and signed zeros; all NaNs compare by NaN classification, with no fixed payload.
The whole-kernel numerical tolerance is therefore zero ULP for that reference
sequence. An analytic/high-precision result is supplementary error reporting,
not permission to reassociate a source program. Each arithmetic built-in must
also satisfy its selected standard's own error rule. A different algorithm or
reduction tree is a different, separately admitted entry and reference.

| Pilot | Frozen algorithm, domain and benchmark shapes | Observable |
| --- | --- | --- |
| Reduction | `uint32` modular sum and FP32 sum, with the exact two-stage tree and empty result defined below. Lengths 0, 1, 63, 64, 65, 255, 256, 257, 4096. | Exact integer bits and FP32 sequence result. Include a separate 32-bit atomic-add count fixture with 64 work-items; old-value multiset 0..63 and final count 64. |
| Barrier stencil | One-dimensional three-point Jacobi step: output interior `fma(0.25f,left,fma(0.5f,center,0.25f*right))`; copy endpoints unchanged. Group width 64 loads a tile plus halo into local scratch, all lanes barrier, active lanes store. Lengths 0, 1, 2, 63, 64, 65, 257, 4096; 1 and 4 iterations with alternating disjoint buffers. | Exact bytes for unchanged endpoints and comparator result elsewhere; tail lanes contribute no illegal read/write and still synchronize. |
| GEMM kernels | FP32 `C = alpha*A*B + beta*C`, column-major. For k>0, dot product starts +0 and visits k in increasing order using explicit `fma`; epilogue computes `fma(alpha,dot,beta*C)` with a separately rounded multiplication. The k=0 source branch is defined below. Transpose combinations NN/NT/TN/TT. `(m,n,k)` = (0,7,5), (1,1,1), (7,5,3), (16,16,16), (31,33,17), (64,64,64), (256,256,256), (7,5,0). Alpha/beta pairs (1,0), (1,1), (-1,0.5), (0,1). Leading dimensions are minimal and minimal+3. | Exact source-sequence result, untouched padding, no A/B/C alias. Zero output dimension is no work; k=0 uses the explicit branch rather than the k>0 epilogue. |
| Named BLAS operation | `hipblasSgemm` with the same shape/transpose/layout set, `HIPBLAS_POINTER_MODE_HOST`, FP32 default math, and alpha/beta copied before submission. The operation uses the API's BLAS semantics, including cases that do not reference A/B or C. Its direct comparator implements those semantics rather than blindly evaluating an unused operand. | Zero-ULP to the frozen admitted implementation sequence on the finite benchmark domain; exceptional cases obey the pinned BLAS contract. No wider BLAS accuracy or library coverage claim. |

The reduction domain is 0 <= N <= 4096. For N>0 there are G = ceil(N/64)
groups numbered 0 through G-1. Group g initializes a 64-element tile in
increasing input order: tile[i] is input[64*g+i] for 0 <= i < 64 when
that index is below N, otherwise integer zero or FP32 **+0** (bits 0x00000000).
For each level, form a new array with half as many elements by
next[j] = add(previous[2*j], previous[2*j+1]), in that operand order. Addition
is modulo 2^32 for `uint32` and one RNE FP32 addition for float. The levels
have widths 64, 32, 16, 8, 4, 2, 1, with all 64 work-items participating in
the barrier between levels; storage must preserve the complete previous level
until its reads finish. There is no odd-element carry rule: the initial tile
is always padded to 64 before pairing. Its final element is partial[g].

The second stage always applies that same 64-to-1 tree to partials in increasing
group order, padding the unused positions with the same positive zero, even
when only one group produced a partial. For N=0, the host writes integer zero
or FP32 +0 as the reduction result and enqueues no kernel. These padding and
empty rules are part of the source and the bit-level reference; in particular,
an input -0 is not promised to survive additions with padded +0.

For nonempty GEMM output with k=0, both source kernels and their reference
take an explicit branch: each result is the single RNE FP32 multiplication
`beta*C`, with no subsequent `fma` and no reference to alpha, A or B. Thus
beta=1 and C=-0 produces -0. This source branch reads C even when beta=0;
BLAS has its separate no-reference cases and must not inherit that behavior.
For k>0, the source always evaluates the stated dot and epilogue, including
when alpha or beta is zero. Empty m or n performs no data access in either
source branch. These distinctions must be represented in the original source,
the admitted preconditions and the independent reference, not repaired only
inside the test comparator.

Generated numeric vectors include signed zeros, unit values, alternating signs,
largest/smallest finite values, smallest normal and subnormal values, infinities
and quiet NaNs, with deterministic seed 0x51333061. General FP cases qualify the
V route. For a proposed M substitution, a separate exact-representability subset
uses integral FP32 operands from -2 through 2, with alpha=1 and beta=0 or 1;
all benchmark accumulations fit exactly in FP32 and bf16 inputs represent these
operands exactly. The witness must prove every conversion, accumulation and
tail agrees with the source. This restricted M case cannot justify narrowing
general SGEMM inputs. If no admitted M operation implements it, Q30b/Q30c's
matrix comparison remains open; the [matrix margin contract](matrix-margin.md)
and M0.8c/M10 keep their independent gates and estimates.

The HIP kernel repeats these reduction/stencil/GEMM definitions using
`threadIdx`, `blockIdx`, `blockDim`, `gridDim`, `__shared__`, `__syncthreads`,
32-bit `atomicAdd` and explicit FP32 arithmetic. No warp-size, shuffle, texture,
cooperative-group or dynamic-parallelism assumption enters the pilot.

The complete HIP host operation set is `hipGetDeviceCount`, `hipGetDevice`,
`hipSetDevice`, `hipGetDeviceProperties`, `hipMalloc`, `hipFree`, `hipMemcpy`,
`hipMemcpyAsync`, `hipMemset`, `hipMemsetAsync`, `hipStreamCreate`,
`hipStreamDestroy`, `hipStreamSynchronize`, `hipStreamWaitEvent`,
`hipEventCreateWithFlags` (timing disabled), `hipEventRecord`, `hipEventQuery`,
`hipEventSynchronize`, `hipEventDestroy`, `hipLaunchKernel`, `hipGetLastError`,
`hipPeekAtLastError` and `hipDeviceSynchronize`, plus the `hipLaunchKernelGGL`
source macro. Device selection binds only the one delegated device; allocations
bind pool slots; copies retain capability borrows; streams/events share the
OpenCL state machine. Default-stream ordering and per-thread-default-stream
options must be frozen in the closure: the pilot uses the legacy default
stream ordering and one host submitter. Every function is U(f) with T/A/P/S/W;
launch also needs U(d,e) and N. Query/synchronize exposes asynchronous failures.

BLAS additionally exposes `hipblasCreate`, `hipblasDestroy`, `hipblasSetStream`,
`hipblasGetStream`, `hipblasSetPointerMode`, `hipblasGetPointerMode` and
`hipblasSgemm`. One BLAS handle consumes a declared metadata slot and shares its
HIP stream; setting an unsupported pointer/math mode is an explicit unsupported
result, not an ignored flag. U(d,e,f) owns this pilot adaptation. Other BLAS
functions, device pointer mode, batched/ex GEMM and broader HIP APIs are U(g),
with no current support claim. chipStar's ability to compile such calls is not
evidence that this bounded adapter implements them.

### Measurement verdict

Compare direct native, OpenCL-source, original-SPIR-V and HIP variants in the
same composed image, with identical worker grants, memory placements, inputs,
algorithm and mandatory evidence. Run one cold call and 30 subsequent calls
per nonempty benchmark case; retain every latency, not just an average. Report
target ticks, achieved throughput, per-class memory peak, scratch/spills,
executable/source/proof/store bytes and complete producer/admission identity.

The qualification cutoff for each nonempty case is total adapter-route target
ticks at most 1.10 times the direct route plus one owned scheduling period;
steady-state throughput must be at least 90% of direct throughput. Compare
integer inequalities over total repeated-work ticks, including transfers,
setup, waits and drain. Cold latency is separately bounded by direct cold
latency plus two owned scheduling periods. Each case must pass, including
small and irregular controls. These are adapter-overhead thresholds, not a
target absolute throughput promise or the M-class margin.

Exercise a hostile co-tenant filling its own queues and buffers: the subject's
admitted service/WCET bound and capability isolation must remain unchanged.
Record public versus secret labels and prove applicable CT on final bytes;
timing samples alone prove neither. Qualified target hardware or the accepted
timing model supplies target ticks; host/emulator wall time is a separate
engineering measurement and leaves the target verdict open.

## Arithmetic research handoff

These are non-normative inputs to Q30d/Q30e's future proof work and Q30g's
selection of a later slice. The [mathematical survey](../../background/open-math-conjectures.md)
owns source status and research claims. No candidate below changes the frozen
pilot sequence, numeric comparator, assumptions or acceptance thresholds.

| Research input | Connection to the unwritten proof and selection boundary |
| --- | --- |
| [Minimum Circuit Size Problem](../../background/open-math-conjectures.md#minimum-circuit-size-problem) | A truth-table-sized finite Boolean kernel could admit a smaller candidate circuit. First identify that workload; polynomial cost in the complete truth table may still be exponential in its input-bit count. Q30d would need exact equivalence to the original operation, and Q30e the executable lowering. Gate count supplies neither delay nor scratch, energy or proof cost. The open complexity classification is no premise of either theorem. |
| [Polynomial identity testing](../../background/open-math-conjectures.md#deterministic-polynomial-time-polynomial-identity-testing) | Compare the deterministic read-4 formula result only when the exact representation is a non-multilinear read-4 formula over characteristic zero or at least five. Record degree and field/bit-operation costs and the white-box versus black-box interface. An identity or candidate filter is useful only before the existing exact correspondence proof; it does not prove FP32 order, overflow, traps or memory effects. The general circuit problem remains open and the frozen FP32 pilots are not automatically such a formula workload. |
| [Strong Descartes' Rule](../../background/open-math-conjectures.md#strong-descartes-rule-over-finite-fields) | A future exponentiation-circuit filter would first need the proposed prime-field/subgroup and sparse-exponent premises. The conjectural soundness bound cannot become a checked equivalence premise. Even a qualified randomized filter leaves Q30d's exact source correspondence and Q30e's numerical/effect refinement owed; no such filter is selected for the pilots. |
| [Matrix multiplication](../../background/open-math-conjectures.md#matrix-multiplication-exponent-equals-two) | A finite candidate requires the construction and certificates themselves, exact rectangular shapes, arithmetic domain, scratch and transfer bounds. Q30d/Q30e would prove the candidate's declared operation and executable lowering, including conversions and tails. A different reduction order is a separately admitted entry/reference, not a zero-ULP implementation of this pilot by algebraic identity alone. An announced exponent or unreproduced optimization certificate supplies no local proof or throughput. |
| [Hadamard matrices](../../background/open-math-conjectures.md#hadamard-matrix-conjecture) | For a later transform slice selected by Q30g, a concrete finite sign matrix and checked `H*H^T = n*I` certificate establish the algebraic premise. The lowering still needs normalization, scaling, rounding, overflow, padding, layout and WCET proofs against that slice's semantics. The [Bonsai rotation handoff](../../performance/bonsai2-assessment.md#finite-rotation-proof-handoff) already has a power-of-two consumer independent of the universal conjecture; it is outside the current GEMM pilot. |

Candidate generation may remain untrusted. Selection needs a finite input and
resource contract before a new implementation is priced; the existing pilot
proofs proceed without solving any of these conjectures. Q30b/Q30c reuse their
shared oracle and adversarial corpus for a selected candidate, with target cost
and exact assumption evidence still separate from successful tests.

## Foundation handoff and review boundary

Q30d receives the source/closure and refinement interfaces; Q30e receives the
logical work-item, address-space, synchronization and numerical interfaces;
Q30f receives fixed pools, handles, event/borrow lifecycle and error mappings.
Their planned work is bounded to these pilots. The existing compiler,
admission/boot, memory-plan, timing/CT and V/M hardware/proof programs are
prerequisites with their existing owners, not deliverables hidden inside Q30.

Q30g owns selecting and pricing the next standards/library slice, including
3.1 deltas, nonpilot mandatory operations and optional application features.
Its estimate covers one explicitly frozen slice, never all OpenCL conformance
or HIP/ROCm production support. Before that slice starts, it must name the
feature entries it closes, source/test revisions, all foundation owners and
the acceptance predicate. A discovery needing new foundations is separately
priced before implementation. This preserves the endpoint while making the
pilot's remaining work decidable.

The integrator records the certifier and V/M interface review in Q30a's
completion evidence, including any rejected assumption. A survey cannot mark
Q30a landed without that review and the checklist's owned/priced handoffs.
