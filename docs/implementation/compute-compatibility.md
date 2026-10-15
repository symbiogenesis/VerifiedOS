# Open compute compatibility

Status: **standards and pilot semantic contract frozen for review; no implementation or conformance claim**.
This companion applies R-04-001a and R-13-018a through R-13-018c of the
[requirements register](../requirements-register.md). Those entries own the
obligations; this document explains their application and fixes the acceptance
boundary for [Q30](implementation-checklist.md#open-compute-qualification).
It adds no first-release capability to R-18-004a.

The Q30a record comprises the [feature and full/embedded profile audit](compute-feature-map.md),
[source-to-ISA and bounded-resource contract](contracts/compute-semantic.md), and
[exact-revision source, license and dependency review](compute-upstream-review.md).
The audit distinguishes proposed mappings from implemented support and retains
every missing foundation with its checklist owner. Q30b/Q30c prepare adapters
and fixtures against reviewed interfaces beside their foundation work; admitted
target execution joins only after correspondence, lowering and dispatch land.

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
The graphics assessment prefers established application interfaces over a new
public graphics API. Ordinary Vulkan compatibility for named workloads and
Vulkan SC are separate frontend candidates over the same internal native path;
OpenGL enters only as producer-side source. The [graphics API surface](#graphics-api-surface)
owns their selection, porting costs and distinct compatibility claims.

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
The [candidate review](compute-upstream-review.md) selects exact source revisions
and records the component-level license and dependency readings behind Q30a.

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

Q30b owns one frozen reduction, barrier-stencil and GEMM corpus, numerical
results, negative controls and result schema for the source routes. Q30c and
Q30e consume it and add their distinct source/API/target cases. The
[supplementary source review](compute-upstream-review.md#supplementary-pilot-instruments)
assigns Oclgrind to host diagnostics, CLBlast to a bounded GEMM reference and
TestFloat to operation-level inputs. None is a proof or independent oracle by
name alone. Source, option, representation and target changes invalidate affected
evidence; unchanged cases do not need a second harness or duplicate authoring.

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

## Graphics API surface

Status: **assessed direction for Q30g's slice selection; no graphics slice
selected, priced, implemented or claimed conformant**. Primary-source readings
for the start-froms are dated 2026-09-20; the frontend and clean-slate assessment
is dated 2026-10-14. These are feasibility evidence, not dependency pins or
qualification results, and no source is incorporated by this section.

### Application interfaces and internal execution

R-04-001a makes an established standard interface the preferred application
entry point wherever its semantics preserve the platform guarantees. The
candidate path is an application calling a Vulkan or Vulkan SC frontend,
which uses Q30f's bounded native dispatch and the R-12-083 renderer, then hands
surfaces to the compositor. The small native interface is an internal
implementation boundary; applications are not required to adopt a novel public
graphics API. Direct certified native code remains available on the same path.

The shared frontend is a linked source library or contained service using the
existing typed service messages. It owns the selected standard's objects,
descriptors, command recording, synchronization and errors. Runtime API calls translate to
bounded native operations; shader translation, specialization and certification
finish at the producer before generation admission. This distinction permits
runtime command recording and changing data without a shader compiler in the
display path, a hardware command processor or a second execution stack.
The frontend is substantial adapter and driver engineering, shared across
ports. Its implementation, proofs and maintenance need pricing alongside the
application-specific build integration and any residual source changes.

Ordinary Vulkan accepts SPIR-V and pipeline creation at runtime. For a named
application with a complete shader inventory, the candidate frontend can
preserve supported calls while resolving pipeline creation to pre-admitted
implementations. Vulkan SC already requires offline pipeline compilation, but
it is a separate API variant, not drop-in ordinary Vulkan support; Khronos's
[comparison](https://www.khronos.org/blog/vulkan-sc-overview) describes that
distinction. Either frontend owes its own feature audit and qualification.
Preserved calls after rebuilding do not establish a stock-binary or ABI claim.

The [Vulkan pipeline specification](https://docs.vulkan.org/spec/latest/chapters/pipelines.html)
owns ordinary pipeline behavior. A Vulkan pipeline cache or a captured run does
not establish a complete inventory. The producer must cover every permitted
shader, specialization and pipeline-state combination, or prove that a shared
admitted implementation preserves those combinations with runtime data.
Previously unknown runtime-generated shaders remain a porting gap under
R-13-018a. No interpreter, runtime compiler or admission-policy exception is
selected here. An ordinary Vulkan cache miss is not permission to reject
otherwise supported behavior: an admission-only miss needs an explicit
adapter diagnostic and is recorded as a compatibility divergence. The
SC-only no-match result below must not be presented as an ordinary Vulkan error.

### Internal simplification and its limits

[Aaltonen's No Graphics API](https://www.sebastianaaltonen.com/blog/no-graphics-api)
motivates typed memory access, fewer persistent objects and simpler dependency
expression. Its 150-line API sketch covers a limited feature set; it retains
CPU/GPU address distinctions, memory classes, barriers and signal/wait operations.
[Khronos's subsystem-replacement approach](https://www.khronos.org/blog/simplifying-vulkan-one-subsystem-at-a-time)
provides a standard-facing route to similar simplification; its descriptor-heap
work was developed over roughly three years. Neither source establishes this
machine's renderer correctness or performance.

The native design uses ordinary typed capability-bounded data, admitted entry
identities and bounded completion. Resource tables are scoped to a delegated
session; a bindless index grants no new authority, and ring payloads never
carry capabilities. State parameters may remain runtime data when their
admitted code and resource contracts permit it, reducing executable variants
without on-demand compilation. Removing GPU-specific binding or cache machinery
does not remove initialization, aliasing, happens-before, exclusive borrows,
completion, cancellation, revocation or safe-reuse obligations. Assess the
simplification by total implementation state, porting effort and proof obligations.

Modern GPU rasterizers, samplers and cache hierarchies are not the V-class RVV
software renderer. Its image and sampler semantics, bandwidth, latency and
energy costs remain qualification work. Dynamic rendering, shader objects and
descriptor heaps are assessed only when the selected workload needs them;
their existence neither requires their adoption nor proves their local mapping.

### Vulkan SC mapping candidate

[Vulkan SC](https://www.khronos.org/vulkansc/) provides a standardized offline
pipeline object model suited to this assessment. Khronos's [overview of its differences](https://www.khronos.org/blog/vulkan-sc-overview)
states that it is based on Vulkan 1.2, that "Vulkan SC does not support
online pipeline compilation, and thus all pipelines must be compiled offline"
by a pipeline cache compiler from SPIR-V and a JSON description of every
pipeline's state, that "VkShaderModule objects are not used in Vulkan SC",
that device creation must supply `VkDeviceObjectReservationCreateInfo` naming
the maximum simultaneous count of every object type, that sparse resources,
memory freeing and pipeline-cache merging are removed, and that faults are
reported through a registered callback and a query. At runtime a pipeline is
named by identifier through [`VkPipelineOfflineCreateInfo`](https://registry.khronos.org/VulkanSC/specs/1.0-extensions/man/html/VkPipelineOfflineCreateInfo.html),
and a pipeline absent from the cache fails with the standard
[`VK_ERROR_NO_PIPELINE_MATCH`](https://registry.khronos.org/VulkanSC/specs/1.0-extensions/man/html/VkResult.html).
That is the shape the [semantic contract](contracts/compute-semantic.md)
already gives OpenCL: a program handle names a pre-admitted image entry, a
well-formed binary absent from this generation is an explicit adapter
divergence, and every object binds a slot in a fixed pool with a typed
exhaustion result. Vulkan SC has a standard result for the case the OpenCL
adapter must document as a divergence. Read against R-04-001a, it fits at
least as well as the OpenCL embedded profile and better than the full
profile, whose online compiler is mandatory.

| Surface | Required mapping or question |
| --- | --- |
| Pipeline creation | A lookup of an admitted kernel by closure identity; a miss is the standard no-match result, never a compile. The pipeline cache compiler's JSON description and SPIR-V are producer inputs to the same `ComputeClosure` the semantic contract defines. |
| Shader modules and SPIR-V | Producer input in the `Shader` execution model with `Logical` addressing, pinned as a second SPIR-V environment beside the frozen `Kernel` one. Every access passes through a bound descriptor with declared bounds, which suits the capability lowering better than `Physical64` pointers; physical storage buffers and buffer device addresses are excluded for the reason the feature map excludes physical pointer authority. Derivative instructions need quad execution, which the logical work-item model can carry as masked lanes. |
| Descriptor sets and pipeline layouts | Indices into a pre-delegated per-session table, the shape ring payloads already take; a descriptor never carries a capability. |
| Device memory and object reservation | Fixed pools declared at composition. The object reservation structure maps onto the pilot's slot limits, and `VK_ERROR_OUT_OF_DEVICE_MEMORY` onto the typed exhaustion result. |
| Command buffers | Data naming admitted pipelines and delegated resources, so recording at runtime is permitted. Indirect draw and dispatch counts stay under a declared maximum, which is the bounded data scheduling over a predeclared kernel graph the boundary table names for device-side launches. |
| Fences, semaphores and events | The queued, submitted, running, completed and error states Q30f already owns, with timeline semaphores, where enabled, as bounded counters. |
| Queries and timestamps | The timing-authority limits of the profiling row; presentation feedback stays within R-15-236c. |
| Swapchain and presentation | A thin layer over compositor surface handoff under the display contract R-12-082 states; the compositor, not the adapter, owns scanout. |
| Loader, ICDs and layers | Absent. There is no dynamic linking, so the adapter is linked or reached as a compartment, and enumeration reflects the manifest as the OpenCL discovery row does. The [Khronos loader's](https://github.com/KhronosGroup/VulkanSC-Loader) own README states it is for development environments and not for production. |
| Sparse binding, ray tracing, mesh shading, device-generated commands | Excluded, or a named-invariant conflict recorded at selection. |

Three implementation surfaces are assessed separately. Any selection applies
R-13-018c's claim discipline and amends R-13-018a's interface enumeration before
implementation; the ordinary Vulkan and Vulkan SC frontend claims stay distinct:

1. **Compute pipelines** are nearly the pilot's path: ahead-of-time SPIR-V,
   fixed pools and work-groups lowered to RVV. Adding the `Shader` execution
   model beside the `Kernel` model is a Q30g slice candidate whose
   correspondence and lowering owners are Q30d and Q30e.
2. **The standard-facing host object model** over Q30f's dispatch is adapter
   work, audited command family by command family as the feature map audits
   OpenCL. Ordinary Vulkan call preservation and the SC-shaped model are
   distinct candidates; the mapping table describes the latter, not ordinary
   Vulkan conformance. Each shares the same native foundations.
3. **Graphics pipelines** wait on the R-12-083 renderer and on the image and
   sampler audit the pilot disables. The frontend reuses that renderer; its
   interface/semantic work and the renderer need separate prices. The porting
   plan lists the renderer among the net-new artifacts the userland gates on,
   and no checklist cell yet prices it. Larrabee's [prior-art entry](../background/inspirations.md#larrabee-the-software-renderer-on-general-cores-the-one-industrial-run-of-the-v-class-thesis-and-the-sampler-its-own-team-kept)
   records the compatibility burden that bounded call preservation leaves open.

OpenGL is online by contract: it accepts shader text at runtime, and its
pipeline set depends on state known only at draw time, which is why Zink
compiles asynchronously. It enters this platform only as a producer-side
source dialect, GLSL and each named application's enumerated state
combinations translated at the producer into SC-shaped pipelines. There is no
runtime GL personality and no GL conformance claim, for the reason the OpenCL
full profile is barred. The claim is GLSL source compatibility for named
applications, parallel to HIP's. An application's complete pipeline
inventory is part of its source closure; runtime-generated variants remain
the porting gap the [porting discipline](userspace-porting.md#the-porting-discipline-five-obstacles-every-target-meets)
records.

### Frontend selection and porting acceptance

Q30g starts with one named application or toolkit workload and its required
API revision, features, extensions and complete shader/pipeline inventory.
Compare an ordinary Vulkan frontend, Vulkan SC adaptation and direct native
execution on that same workload. Freeze the supported domain, output and
numerical oracle, error cases, resource limits and finite acceptance thresholds
before implementation. Pin the applicable standard and conformance-corpus
revisions; a workload subset is reported as a subset even if its tests pass.

The selection record separates shared frontend/renderer implementation and
proof costs from per-application source edits, producer/build integration,
pipeline inventory maintenance and unsupported behavior. It accounts for all
mandatory requirements of any claimed profile, feature discovery, object and
descriptor lifetime, command ordering, memory visibility, presentation and
errors. Standard objects may be implemented differently internally only while
preserving their supported observable semantics. Features not selected remain
unsupported or unimplemented with a reason and owner, rather than silently
receiving weaker semantics.

Qualification exercises preserved calls and output, permitted runtime pipeline
choices, undelegated resources, stale descriptors/handles, pool exhaustion,
ordering errors, cancellation, restart and a shader absent from the admitted
closure. Record the expected result and any standard divergence for each.
Compare code/proof/storage footprint, internal state and adapter latency with
direct native execution using identical workers, schedules and memory placement;
retain applicable deadline, CT and isolation evidence. Target throughput,
bandwidth and energy claims need their own evidence. Missing renderer, image/sampler,
semantic or proof foundations receive separate estimates before dependent
implementation; this comparison does not enlarge Q30g's conditional allowance.

### Start-froms and what each establishes

| Source | Evidence and consequence for this design |
| --- | --- |
| [Vulkan SC emulation layer and pipeline cache compiler](https://github.com/KhronosGroup/VulkanSC-Emulation) | Khronos's emulation ICD and mock pipeline cache compiler define the offline pipeline JSON and cache format concretely. They are the reference for the producer-side pipeline closure, not a runtime: the emulation layer runs over a stock Vulkan driver and is excluded from any admitted image. |
| [Vulkan SC conformance tests](https://github.com/KhronosGroup/VK-GL-CTS) | VK-GL-CTS carries Vulkan SC tests as the `deqp-vksc` target. It is the conformance corpus candidate for claim 2; Q30g pins its revision and configuration before any result is quoted, as the feature map requires for OpenCL. |
| [glslang](https://github.com/KhronosGroup/glslang) | The Khronos reference GLSL/ESSL front end with SPIR-V generation under both Vulkan and OpenGL target semantics. It is the producer candidate for GL-dialect source; its SPIR-V is a translated input owing the same original-source correspondence as PoCL's or Vecz's output. |
| [naga](https://github.com/gfx-rs/wgpu/blob/trunk/naga/README.md) | wgpu's Rust shader translator: WGSL fully validated, GLSL 440 and later under Vulkan semantics only, SPIR-V in and out. It is the producer candidate on the porting plan's Rust route and the path for wgpu-based toolkits whose shader sets are fixed at build time. |
| [rust-gpu](https://github.com/Rust-GPU/rust-gpu) | Compiles Rust to SPIR-V shaders and states it is at an early stage and not production-ready. Here a shader written in Rust is ordinary certified native code and needs no SPIR-V; rust-gpu matters only for source that must also target other platforms. |
| [clspv](https://github.com/google/clspv) | Compiles a subset of OpenCL C 1.2 to Vulkan compute-shader SPIR-V through LLVM passes. It is evidence that the `Kernel` and `Shader` dialects are bridgeable, so one certified-kernel path can serve both, and its passes are candidate producer transforms owing the same correspondence obligations as PoCL's. |
| [SPIRV-Tools](https://github.com/KhronosGroup/SPIRV-Tools) | The validator checks the rules of the SPIR-V specification with one-sided error, reporting a violation only for the rules it implements. It is a producer-side precheck; the semantic contract already denies a frontend validator the role of trust root. |
| [Fossilize](https://github.com/ValveSoftware/Fossilize) | Captures Vulkan pipeline state for replay and precompilation ahead of a run. It is evidence that application pipeline inventories are enumerable ahead of time and a capture-based route to an application's closure; a capture proves only the pipelines it saw, so a closure claim rests on the application's own enumeration. |
| [llvmpipe](https://docs.mesa3d.org/drivers/llvmpipe.html) and lavapipe | Mesa's software rasterizer "uses LLVM to do runtime code generation", and [lavapipe](https://www.collabora.com/news-and-blog/blog/2021/06/14/zink-summer-2021-update/) is the Vulkan implementation reusing its rasterizer that runs Zink in Mesa's CI. Together they show the whole GL-on-Vulkan-on-CPU stack working in software, and they confirm R-12-083: the working software 3D paths JIT. Their structure is a reference; their code is not a start-from. |
| [SwiftShader](https://github.com/google/swiftshader) | A CPU implementation of Vulkan with stated Vulkan 1.3 conformance, carrying the Subzero and LLVM code generators in its tree. The same disposition as llvmpipe: evidence that a complete software Vulkan exists, structure without code. |
| [OpenSWR](https://www.openswr.org/) | Intel's CPU rasterizer built on LLVM and targeting AVX, AVX2 and AVX-512, removed from mainline Mesa after 21.3. It is the nearest later industrial run of software rasterization on wide vector units after Larrabee, and the same disposition applies: wide-vector coverage and binning as design reference, its LLVM-compiled stages replaced by certified code. |
| Mesa softpipe | Listed on Mesa's [platforms page](https://docs.mesa3d.org/systems.html) as "a reference Gallium driver with a shader interpreter". It is a working no-JIT GL implementation, slow by design; it serves as a semantic reference for pipeline behavior and not as a renderer. |
| [euc](https://github.com/zesterer/euc) | A Rust CPU rasterizer whose vertex, fragment and blend stages are methods of a pipeline trait compiled by rustc, with no JIT, plus depth buffers, textures and samplers, MSAA, multithreading and `no_std`. It is small, but it is the one start-from whose shader model is literally R-13-018's: a shader is ordinary compiled code. |

None of these carries a licence or dependency-closure reading here. Q30g's
candidate selection records exact revisions, licence files and closures as the
[upstream review](compute-upstream-review.md) did for Q30a, and nothing is
vendored, pinned or trusted before that record exists.

## Mathematical candidates for later proof work

The [arithmetic research handoff](contracts/compute-semantic.md#arithmetic-research-handoff)
routes MCSP, restricted PIT, Strong Descartes, matrix-multiplication and finite
Hadamard leads to Q30d's source correspondence, Q30e's lowering and Q30g's
later-slice selection. These are non-normative candidates, not new pilot scope.
No algebraic theorem substitutes for the frozen numeric/effect semantics, and no
asymptotic operation count establishes target performance. Candidate source or
proof reuse still needs exact statement/dependency review and the incorporation
licence reading before adoption. Workload-dependent graph and data-structure
leads remain with the [Wasm workload handoff](contracts/wasm-execution.md#mathematical-research-handoff);
the [inference handoff](../performance/inference-demand.md#research-handoff-to-unwritten-inference-proofs)
retains the finite demand and quality decision.

## Qualification contract

The Q30a record fixes exact source/API revisions, candidate implementation
revisions, feature dispositions, semantic interfaces, finite input domains and
resource bounds before pilot implementation. Q30d/Q30e/Q30f own the bounded
correspondence, V/M lowering and native dispatch/pool foundations; Q30g selects
and prices the next standards/library slice, including the newer standard's
delta audit. These are conditional pilot or slice costs, not a blanket estimate
for full conformance or the entire compiler proof program. M1's certifier and
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
