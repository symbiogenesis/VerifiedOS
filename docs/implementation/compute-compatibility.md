# Open compute compatibility

Status: **design and qualification contract; no implementation or conformance claim**.
This companion applies R-04-001a and R-13-018a through R-13-018c of the
[requirements register](../requirements-register.md). Those entries own the
obligations; this document explains their application and fixes the acceptance
boundary for [Q30](implementation-checklist.md#open-compute-qualification).
It adds no first-release capability to R-18-004a.

## Selected direction

Support the largest applicable open-standard surface that preserves the
[README guarantees](../../README.md#bug-classes-removed-by-construction).
Begin with OpenCL C kernels and applicable SPIR-V build inputs, compiled ahead
of time into ordinary certified V/M-class code. Preserve familiar OpenCL host
operations through bounded adapters where their semantics fit. Add HIP
source/API adaptation over that same execution path, qualifying libraries
separately. Prefer existing frontends, transformations, semantics, test corpora
and library interfaces over a new project-specific kernel language or a second
runtime. Reuse still needs licence review and the platform's proof chain.

OpenCL and SPIR-V are Khronos standards. [HIP](https://rocm.docs.amd.com/projects/HIP/en/latest/what_is_hip.html) is an
open-source portability API in the AMD ecosystem; open source does not make it an independently standardized
API. ROCm names a larger software stack, not a synonym for HIP kernel syntax.
Source compatibility, host API compatibility, portable IR support, stock binary
execution, library coverage and standards conformance each need their own claim.
The selected work targets the first three; it admits no stock GPU binary or
full ROCm stack. A conforming profile remains a qualification question.

## Prior art and what it establishes

Primary-source readings below are dated 2026-09-19. They are candidate and
feasibility evidence, not dependency pins or VerifiedOS qualification results.

| Source | Evidence and consequence for this design |
| --- | --- |
| [PoCL 7.2 release notes](https://portablecl.org/docs/html/notes_7_2.html) | Reports OpenCL 3.0 CTS passes on RV64GC and RVA22+RVV1.0 CPU devices in both OpenCL C and SPIR-V compilation modes, with conformance results submitted. This directly supports a RISC-V CPU/vector route; it supplies no CHERI-TAL or source-correspondence certificate for this machine. |
| [Codeplay oneAPI Construction Kit](https://developer.codeplay.com/products/oneapi/construction-kit/home/) and [RISC-V vector guide](https://developer.codeplay.com/products/oneapi/construction-kit/4.0.0/guides/modules/riscv) | Supplies a RISC-V reference implementation and vectorization tooling to evaluate before designing a new lowering. Its target profile and runtime are not this platform's admission or resource model. |
| [Vortex](https://github.com/vortexgpgpu/vortex) | Lists OpenCL, Vulkan and HIP support on a RISC-V GPGPU. It establishes another implementation route, but its SIMT hardware is outside R-15-243. Kernel/API reuse and importing its GPU architecture are separate decisions. |
| [chipStar](https://github.com/CHIP-SPV/chipStar) | Compiles and runs HIP/CUDA through SPIR-V with OpenCL or Level Zero backends. It makes HIP-to-non-AMD execution a concrete reuse candidate; its translator and runtime still owe every local proof and admission obligation. |
| [SiFive/AMD announcement, 2026-09-15](https://www.sifive.com/press/sifive-amd-rocm-riscv-datacenter-servers) | Describes a demonstration-only ROCm 10.0 system with SiFive P870-D RISC-V host CPUs and AMD Radeon AI PRO R9700 GPUs doing inference. It demonstrates host integration, not execution of AMD kernels on RVV. It does not remove the discrete-GPU and opaque-firmware conflicts in this design. |

No source is incorporated by this comparison. At incorporation, read the selected
revision's licence and dependency closure and record intended use and distribution
in [THIRD-PARTY.md](../../THIRD-PARTY.md), under the
[licensing rules](../../COPYRIGHT.md#terms-this-tree-does-not-carry).

## Compatibility boundary

The standard-facing adapter is a source library with explicit context and
manifest-delegated authority. It shares the existing native kernel execution
path; it does not add a device-discovery service with ambient authority, GPU
driver, shader-command processor or display command-stream validator. Calls may
bind slots in fixed pools and submit bounded work for already admitted workers.
No context creation creates a compartment or enlarges its memory or time share.

Compilation happens at a producer, including the resident toolchain in its
declared build mode. Every result is data for a successor generation. At runtime,
program/kernel handles name pre-admitted image entries; binding such a handle
does not load native code from a supplied source, IL or binary blob. An API that
expects arbitrary new programs to become executable within its current process
therefore has a real compatibility gap. Renaming compilation or returning a
handle cannot hide it.

The [OpenCL API specification](https://registry.khronos.org/OpenCL/specs/unified/html/OpenCL_API.html)
requires an online compiler for full-profile platforms and permits its absence
for embedded-profile platforms. Thus an AOT-only path cannot claim the full
profile. Embedded-profile eligibility still requires auditing every mandatory
operation, including binary/built-in program creation, numerical requirements
and reported capabilities. Optional features in OpenCL 3.x do not make an
arbitrary subset conformant. Until that audit and the required conformance work
pass, publish the supported source/API subset explicitly.

The feature record at Q30a uses these dispositions: **supported with preserved
semantics**, **conflicts with a named invariant**, **exceeds a measured declared
budget**, or **unimplemented with an owner and acceptance predicate**. It covers
every mandatory feature in any proposed profile and the optional features the
selected applications use. Unsupported standard behavior stays visibly
unsupported; a project extension or changed error is identified as such.

| Surface | Required mapping or question |
| --- | --- |
| Work-items and work-groups | Lower to scalar loops/RVV lanes and fixed workers. Preserve IDs, masks and cross-item behavior; size bounds are composition inputs, while launch sizes can vary within them. A standard work-item model does not require SIMT hardware. |
| Barriers and atomics | State memory scopes, ordering and progress, including divergent barriers and event dependencies. The ISA's missing general CAS/LR-SC does not itself prove that an API operation is impossible: assess a bounded semantics-preserving lowering, and record a conflict only if its required guarantees cannot be met. |
| Address spaces and pointers | Map global, local, private and constant storage to typed capability-bounded regions. Check aliasing, initialization and ownership transfers; a flat address space confers no shared authority. SVM/USM support needs a separate ownership/lifetime argument, never raw host pointer import. |
| Buffers, queues, events and handles | Charge backing, runtime occupancy, retention, quiescence, revocation, zeroization and restart to declared pools. Bound outstanding work and wait lists. Map the typed exhaustion result to a documented API error without implicit waiting or borrowing. |
| Scheduling and timing | Order work only within the owner's fixed workers and slots. Apply existing deadline and secrecy obligations to the actual workload; neither an API call nor a throughput benchmark establishes schedulability. Profiling/timer queries retain the platform's timing-authority limits. |
| Numerical semantics | Cover widths, overflow, rounding, NaNs, denormals, built-ins, reduction order and permitted approximation options. Missing scalar floating point and restricted rounding require analysis against the particular language operation; source compatibility does not follow from accepting its spelling. |
| Source, SPIR-V and specialization | Pin the input language and SPIR-V execution environment separately. Include all specialization decisions in the admitted closure. Check correspondence from the original source across each transform and final image construction, rather than treating translated IR as the user's original source. |
| Device-side launches, callbacks and graphs | Assess bounded data scheduling over a predeclared kernel/worker graph first. Runtime native-code loading, new authority edges and unbounded queues remain excluded; a missing bounded implementation is an owned gap. |
| Libraries and matrix acceleration | Qualify each named library operation and version, its layouts and numerical contract. GEMM lowering or a shared library backend must actually use the admitted M-class path before claiming its speed. Generic vectorization supplies no matrix-acceleration guarantee. |

Full ROCm's AMD-device route conflicts with the current hardware and driver
contract. That is not a blanket refusal of HIP sources or reusable library
interfaces. Q30c begins with one named BLAS GEMM interface. rocBLAS, MIOpen,
framework compatibility and their broader dependency closures remain separate
ports with separate evidence and owners; one successful kernel proves none of
them.

## Qualification contract

Q30a freezes exact source/API revisions, candidate implementation revisions,
feature dispositions, semantic interfaces, finite input domains and resource
bounds before pilot implementation. Its reviewed record names every missing
prerequisite and a separately priced implementation owner. M1's certifier and
source-correspondence work, the native admission/boot path, the V/M execution
work and the matrix margin contract retain their existing obligations. Q30
does not absorb those programs or treat a source survey as their completion.

Q30b's pilot is a reduction, a stencil with a work-group barrier, and GEMM,
expressed as OpenCL C and through the selected SPIR-V build route. Q30c repeats
the kernel cases through HIP and adds one declared BLAS GEMM operation. Both
consume one runtime and compare with equivalent direct V/M implementations.
The pilot resource and numerical thresholds are fixed by Q30a, not chosen after
measurements. Its implementation may begin only after the required translation
proof routes and dispatch/pool interfaces exist.

Acceptance requires all of the following:

1. **Complete admission:** original source/IR identities, options, manifests,
   certificates, final bytes and generation identity form one reproducible
   record. The ordinary checker and boot path accept the artifacts. The
   original-source correspondence and required tier proofs cover the adapters
   and libraries as well as arithmetic kernels. Removing or substituting a
   required certificate, closure member or kernel binding fails ordinary admission.
2. **Preserved computation:** reference comparisons cover the declared input
   domain, including zero/edge dimensions, non-vector multiples, synchronization,
   ordering and numerical corner cases. Use upstream suites and generated cases
   where a reference oracle exists; report passes, failures and exclusions.
   Tests are interoperability evidence, not substitutes for the proofs.
3. **Authority and lifecycle:** exercise out-of-range buffers, forbidden aliases,
   uninitialized reads, stale/released handles, pool exhaustion, cyclic waits,
   failed/cancelled work and restart with in-flight operations. Every case has
   its Q30a-defined error, rejection or bounded recovery result. Submission
   cannot name undelegated resources or execute a newly supplied object.
4. **Composition and cost:** show worker and storage bounds, applicable WCET and
   CT evidence, fixed-slot behavior and isolation under a hostile co-tenant.
   Measure code/proof/store footprint, scratch and private memory, adapter and
   dispatch overhead, throughput and latency against the direct implementation
   on the same composition. State simulated versus qualified-hardware results;
   host measurements do not establish target performance or the M-class margin.
5. **Honest deliverable:** publish the exact supported source/API/library set and
   remaining gaps. A pilot passes only for that set. A full or embedded OpenCL
   claim needs its separate complete-profile conformance evidence. A failed
   proof or resource bound returns an owned gap and never weakens a guarantee.

This work may broaden compatible software without changing the custom physical
machine. Any proposal to change that machine or its trusted execution contract
is a separate normative amendment, not an adapter implementation detail.
