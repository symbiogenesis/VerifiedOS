# Compute feature and profile audit

This is Q30a's authored decision record, read with the
[compatibility boundary](compute-compatibility.md) and
[semantic contract](contracts/compute-semantic.md). It freezes inputs for Q30b/Q30c,
not implemented support. **Every execution feature below is unimplemented.**
An intended semantics-preserving mapping is not a qualification verdict.
R-04-001a and R-13-018a through R-13-018c remain the normative owners.

## Frozen inputs and claim scope

| Input | Exact selection and reason |
| --- | --- |
| OpenCL API, C and SPIR-V environment | [OpenCL-Docs v3.0.19, commit 85da0d12c298ffa9eefd2adb1864f2c8193cbe3e](https://github.com/KhronosGroup/OpenCL-Docs/tree/85da0d12c298ffa9eefd2adb1864f2c8193cbe3e). The API and environment audit uses this complete 3.0 snapshot. The pilot source mode is OpenCL C 1.2, with its definitions read from this unified C specification. |
| Portable IR | SPIR-V 1.0, `Kernel` execution model, `Physical64` addressing and `OpenCL` memory model; the selected OpenCL environment's SPIR-V 1.0 rules apply. No Vulkan/Shader environment, physical pointer authority, vendor instruction or extension is implied. |
| HIP | [ROCm/HIP rocm-6.3.0, commit 2451439986f64bf39677e25201367a59457e1991](https://github.com/ROCm/HIP/tree/2451439986f64bf39677e25201367a59457e1991). C++14 kernel source and the explicitly listed runtime functions only. HIP is a vendor portability interface, not an independently standardized API. |
| BLAS | [ROCm/hipBLAS rocm-6.3.0, commit e75831fa5e92638c8473bd01aea65a3df181d041](https://github.com/ROCm/hipBLAS/tree/e75831fa5e92638c8473bd01aea65a3df181d041): `hipblasSgemm` and its listed handle/stream operations. No rocBLAS, MIOpen, CUDA binary, AMD device or full ROCm claim. |

The 1.2 source mode is the common mandatory language base useful to the pilot
and both surveyed OpenCL routes; it does not discard the later API or optional
language features from the audit. 3.0.19 is a reproducible qualification target,
not a claim to be the newest standard. The upstream tags read on 2026-09-19
also include [3.1.2 at 219be24fc8947c68ee45b4d25b55a92b8f799f29](https://github.com/KhronosGroup/OpenCL-Docs/tree/219be24fc8947c68ee45b4d25b55a92b8f799f29).
Q30g owns a clause/API/capability delta audit before a 3.1 claim or next feature
slice: retain every applicable addition, assign its proof and resource work,
and explain any rejection against a requirement or measured limit. The pilot
does not establish a reason to cap eventual support at 3.0 or at C 1.2.

## Reading the dispositions

`U(d)`, `U(e)`, `U(f)` and `U(g)` mean unimplemented, owned respectively by
Q30d (source correspondence), Q30e (V/M lowering), Q30f (dispatch/pools) and
Q30g (remaining profile/library qualification). Their acceptance predicates
and estimates live in the checklist. `C` is a concrete invariant conflict;
it always names that invariant. `O` means optional and disabled for the pilot,
with an implementation owner rather than a claim of incompatibility.
There is no measured-budget rejection in this record: no target measurements
exist. A fixed pilot budget is an experiment input, not a measured limit.

The obligations referred to below are:

| Obligation | Acceptance interface |
| --- | --- |
| T | Original-source/IR-to-final-image correspondence, all options and libraries included, R-13-018a. |
| A | Capability bounds, initialization, lifetime, aliasing, authority and tier admission, R-13-018b. |
| P | Fixed pools, retention and reclamation peaks, overflow/exhaustion and restart, R-08-046/R-08-047. |
| S | Work-item trace, synchronization, atomicity and bounded progress for every permitted actor. |
| N | Exact operation-level numeric semantics and declared whole-kernel tolerance. |
| W | Fixed worker/schedule and WCET where required; binary constant-time for secret data under R-13-020. |

The source locators below refer to files at the frozen OpenCL-Docs commit.
All commands in a row inherit its disposition, observable and obligations;
overloads, query parameters, flags, invalid-argument cases and conditional
requirements belong to that row, not an unexamined default. The
[registry's core feature blocks](https://github.com/KhronosGroup/OpenCL-Docs/blob/85da0d12c298ffa9eefd2adb1864f2c8193cbe3e/xml/cl.xml)
are the API enumeration source. Extension commands are outside a profile
unless explicitly enabled; the optional table records those considered here.

## Host API and mandatory baseline

`F/E` means audit for both full and embedded profiles. Conditional rows do not
become advertised support merely because their entry points exist. Deprecated
entry points retain their contract when exposed. All successful pilot calls
also carry T/A/P/W; the last column adds the row's distinguishing obligation.

| Surface and exact command family | Profile/disposition | Observable and remaining proof |
| --- | --- | --- |
| Discovery: `clGetPlatformIDs`, `clGetPlatformInfo`, `clGetDeviceIDs`, `clGetDeviceInfo`, `clGetExtensionFunctionAddress`, `clGetExtensionFunctionAddressForPlatform` | F/E U(f,g) | Enumerate only delegated devices; every query reflects the admitted manifest and qualified limits. Unknown/unavailable extension lookup returns null; no discovery grants authority. Validate all queried sizes, version strings, feature dependencies and minimum limits. A/P |
| Device partition: `clCreateSubDevices`, `clRetainDevice`, `clReleaseDevice` | F/E U(f,g), O for partitioning | Empty partition-property support in pilot; unsupported partition request gets `CL_INVALID_VALUE`; root device retain/release follows standard semantics. A future subdevice selects existing worker subsets, never new slots. A/W |
| Context: `clCreateContext`, `clCreateContextFromType`, `clRetainContext`, `clReleaseContext`, `clGetContextInfo`, `clSetContextDestructorCallback` | F/E U(f) | Bind fixed context slots for a declared device set; retain/release and destructor callbacks observe live references, with bounded callback records. Invalid device/context rejected, exhaustion mapped below. A/P/S |
| Host queues: `clCreateCommandQueue`, `clCreateCommandQueueWithProperties`, `clRetainCommandQueue`, `clReleaseCommandQueue`, `clGetCommandQueueInfo`, `clSetCommandQueueProperty` | F/E U(f); O for out-of-order mode | In-order pilot. Unsupported queue property gives `CL_INVALID_QUEUE_PROPERTIES`; preserved deprecated behavior requires separate tests if exposed. Q30g owns optional out-of-order dependency scheduling. P/S/W |
| Buffer creation: `clCreateBuffer`, `clCreateBufferWithProperties`, `clCreateSubBuffer` | F/E U(f) | Bind preplaced backing; preserve flags, alignment, host-pointer lifetime and subrange identity. Host pointer must already be an authorized capability, not an integer import. `USE_HOST_PTR` lifetime and map exclusivity need proof, not unconditional copying. A/P |
| Buffer transfers: `clEnqueueReadBuffer`, `clEnqueueWriteBuffer`, `clEnqueueCopyBuffer`, `clEnqueueReadBufferRect`, `clEnqueueWriteBufferRect`, `clEnqueueCopyBufferRect`, `clEnqueueFillBuffer` | F/E U(f) | Preserve byte/row/slice extents, blocking/event order, fill-pattern repetition and overlap errors. Transfer ownership persists until completion, even after API return. A/P/S |
| Images: `clCreateImage`, `clCreateImageWithProperties`, `clCreateImage2D`, `clCreateImage3D`, `clGetSupportedImageFormats`, `clGetImageInfo`, `clEnqueueReadImage`, `clEnqueueWriteImage`, `clEnqueueCopyImage`, `clEnqueueFillImage`, `clEnqueueCopyImageToBuffer`, `clEnqueueCopyBufferToImage`, `clEnqueueMapImage` | F/E conditional, O U(g) | Pilot reports image support false, zero image limits and no formats; image creation/commands return the specified unsupported-image error. Before enabling: all required image types, formats, channel conversions, addressing/filter modes, pitches, dimensional limits and access qualifiers need one complete conditional audit. A/P/N/S |
| Memory lifetime: `clRetainMemObject`, `clReleaseMemObject`, `clGetMemObjectInfo`, `clSetMemObjectDestructorCallback`, `clEnqueueMapBuffer`, `clEnqueueUnmapMemObject`, `clEnqueueMigrateMemObjects` | F/E U(f) | Reference counts and map count are visible; a map grants a bounded borrow, unmap returns it, migration changes readiness/ownership without changing physical authority. Destructor follows last live/in-flight reference; no early reuse. A/P/S |
| Samplers: `clCreateSampler`, `clCreateSamplerWithProperties`, `clRetainSampler`, `clReleaseSampler`, `clGetSamplerInfo` | F/E conditional, O U(g) | No image feature or sampler objects in pilot. Enabling images brings normalized coordinates, addressing/filter rules and sampler lifetime together. A/P/N |
| Source program: `clCreateProgramWithSource`, `clBuildProgram`, `clCompileProgram`, `clLinkProgram`, `clUnloadCompiler`, `clUnloadPlatformCompiler` | F C; E U(f,g) | Full-profile online compiler/linker cannot make new code executable without violating R-02-008/R-13-001a. An embedded no-compiler route may retain bounded source data and return `CL_COMPILER_NOT_AVAILABLE`/`CL_LINKER_NOT_AVAILABLE`; unload is harmless. Producer compilation creates only a successor-generation artifact. T/A/P |
| Binary/built-in/IL programs: `clCreateProgramWithBinary`, `clCreateProgramWithBuiltInKernels`, `clCreateProgramWithIL` | F/E U(f,g), C for execution of newly supplied objects | A built-in or binary identity can select already admitted code. A standard-valid executable absent from this generation is refused by a documented adapter divergence, not disguised as invalid bytes; embedded conformance therefore remains open. IL is producer input only. T/A |
| Program lifecycle: `clRetainProgram`, `clReleaseProgram`, `clGetProgramInfo`, `clGetProgramBuildInfo`, `clSetProgramReleaseCallback`, `clSetProgramSpecializationConstant` | F/E U(f,g) | Programs expose exact source/binary/options/build-log identity; no phantom successful build. Specialization fixed in the admitted closure; runtime mutation cannot select unproved code. Release callbacks retained and invoked once after quiescence. T/P/S |
| Kernel objects: `clCreateKernel`, `clCreateKernelsInProgram`, `clCloneKernel`, `clRetainKernel`, `clReleaseKernel`, `clSetKernelArg`, `clGetKernelInfo`, `clGetKernelArgInfo`, `clGetKernelWorkGroupInfo` | F/E U(f) | Bind named immutable entries; clone copies argument binding into a separately charged slot. Argument kinds, bounds, alignment, local scratch and required group size checked before enqueue. Query values describe the actual compiled entry. A/P/S |
| Kernel commands: `clEnqueueNDRangeKernel`, `clEnqueueTask`, `clEnqueueNativeKernel` | F/E U(e,f); native kernels O U(g) | IDs, offsets, dimensions, masks and outputs follow the input program. Legacy task is a one-item launch. No `CL_EXEC_NATIVE_KERNEL` support advertised; native enqueue returns `CL_INVALID_OPERATION`. A/S/W |
| Events: `clCreateUserEvent`, `clSetUserEventStatus`, `clWaitForEvents`, `clGetEventInfo`, `clRetainEvent`, `clReleaseEvent`, `clSetEventCallback` | F/E U(f) | Preserve queued/submitted/running/completed/error states and callback trigger; wait on failed dependencies gives `CL_EXEC_STATUS_ERROR_FOR_EVENTS_IN_WAIT_LIST`. No success event after failure; retained waits keep their objects live. P/S/W |
| Ordering: `clEnqueueMarker`, `clEnqueueWaitForEvents`, `clEnqueueBarrier`, `clEnqueueMarkerWithWaitList`, `clEnqueueBarrierWithWaitList`, `clFlush`, `clFinish` | F/E U(f) | Markers/barriers establish queue edges; flush schedules eligible work in owned slots; finish waits for that queue, never borrows slots. Cycle rejection is a declared adapter restriction. P/S/W |
| Timing: `clGetEventProfilingInfo`, `clGetDeviceAndHostTimer`, `clGetHostTimer` | F/E U(f,g) | Profiling-disabled queue returns `CL_PROFILING_INFO_NOT_AVAILABLE`; timer entry points obey support queries and standard absence errors. Authorized profiling needs coherent monotonic timestamps with declared resolution and information-flow review; fabricated time is forbidden. W |
| Device queues: `clSetDefaultDeviceCommandQueue` | F/E optional, O U(g) | No device enqueue capability or device queue in pilot; unsupported calls fail under the standard capability conditions. Bounded graph lowering remains an implementation question, not a hardware conflict. S/P/W |
| Pipes: `clCreatePipe`, `clGetPipeInfo` | F/E optional, O U(g) | Report pipe support false and reject creation as unsupported; a future implementation needs fixed packet/reservation pools and progress semantics. A/P/S |
| SVM: `clSVMAlloc`, `clSVMFree`, `clSetKernelArgSVMPointer`, `clSetKernelExecInfo`, `clEnqueueSVMFree`, `clEnqueueSVMMemcpy`, `clEnqueueSVMMemFill`, `clEnqueueSVMMap`, `clEnqueueSVMUnmap`, `clEnqueueSVMMigrateMem` | F/E optional, O U(g) | Capability bits zero; allocation returns null and unsupported operations fail per API conditions. Future coarse/fine/system sharing and atomic scope require ownership/lifetime proofs across all host/device actors. Raw pointer import cannot confer authority. A/P/S |
| Subgroups: `clGetKernelSubGroupInfo` | F/E optional, O U(g) | No subgroup support advertised; query returns its unsupported-operation error. A future subgroup model must match the selected logical grouping rather than assume RVV lanes equal hardware warps. S/N |

Source locators: `api/opencl_platform_layer.asciidoc` owns platform/device/context
queries, `api/opencl_runtime_layer.asciidoc` owns command behavior and error
precedence, `api/embedded_profile.asciidoc` owns embedded exceptions. An adapter
must use the selected specification's valid parameter-dependent error rather
than return one generic error for every case in a family.

## Language, environment and optional surface

The following is the feature-level audit of the entire C baseline, not only
the arithmetic used by the pilots. It follows the headings of
[OpenCL_C.txt](https://github.com/KhronosGroup/OpenCL-Docs/blob/85da0d12c298ffa9eefd2adb1864f2c8193cbe3e/OpenCL_C.txt).
Unlisted optional/vendor extensions are disabled and return a producer
diagnostic naming the extension; Q30g owns evaluation when an application needs
one. Unknown capabilities are never accepted on the strength of frontend parsing.

| Feature family | Disposition and observable | Obligations |
| --- | --- | --- |
| Scalar `bool`, signed/unsigned integer widths, `size_t`, `ptrdiff_t`, `intptr_t`, `uintptr_t`, `void`, float, stored half; vector widths 2/3/4/8/16, padding/alignment/literals/swizzles | U(d,e). Preserve C widths and layout, including three-component padding; plain `char` signedness frozen to signed. Half storage/conversion is distinct from half arithmetic. Unsupported optional scalar type diagnosed. | T/A/N |
| 64-bit integers | U(d,e). Retain for the full-profile baseline and the chosen embedded route; no hardware or effort rationale for dropping native-width integer semantics. | T/N |
| Implicit and explicit conversions, saturation, `_rte/_rtz/_rtp/_rtn`, `as_type`, unions and pointer casts | U(d,e). Numeric bits obey selected rules; pointer casts never create capabilities. Every permitted conversion rounding mode needs a checked lowering, including software. Undefined source behavior is not an admitted result. | T/A/N |
| Arithmetic, bitwise, logical, relational, shift, vector select, assignment, indirection and expression evaluation | U(d,e). Integer wrap where defined, checked preconditions for undefined cases; vector masks and boolean widths follow source semantics. | T/A/N |
| Global/local/constant/private address spaces, qualifiers, storage duration, access qualifiers and alias rules | U(d,e,f). Separate typed capability regions and local/private lifetimes; constant remains read-only; no cross-group local alias or uninitialized read. | T/A/P |
| Kernel/functions, required/hinted work-group/vector attributes, type/variable attributes, language restrictions and preprocessing/macros | U(d). Closed includes/macros/options and all declarations are part of source identity; unsupported feature diagnostics are deterministic; required attributes constrain admission. | T/A/W |
| Work-item built-ins: dimensions, global/local/group IDs and sizes, group count and global offset | U(e). IDs are source-visible integers independent of physical RVV width; work-group assignment preserves multidimensional linearization. | T/S |
| Math, integer, common, geometric, relational, vector load/store and shuffle built-ins | U(d,e) for pilot operations; U(g) for remaining overloads. Standard-defined output/accuracy/edge cases, including half conversion, are the oracle; no blanket fast-math tolerance. | T/A/N |
| Work-group barrier, local/global memory fences, asynchronous work-group copy, wait-group events and prefetch | U(e) for barrier/fence; U(g) for async copy/prefetch. All participating work-items reach each barrier instance, visibility spans the specified address spaces; async-copy event lifetime and collective participation need their own proof. Prefetch has no authority effect. | T/A/P/S |
| Legacy global/local 32-bit base and extended atomics, including exchange, compare/exchange, increment/decrement, min/max and bitwise operations | U(e). Bounded owner serializes every permitted conflicting actor at operation granularity; preserve returned old values and allowed ordering. No CAS instruction requirement inferred. | T/A/S/W |
| `printf`, compiler options, pragmas and diagnostic behavior | U(g). Formatted result/return semantics and a charged output buffer with admitted sink; full/embedded buffer minima still apply. Producer options cannot silently weaken numerical or CT contracts. | T/P/N/W |
| Floating-point compliance, rounding/exception/denormal rules, image addressing/filtering appendix | U(e,g). Numeric operation witnesses bind bits, rounding and special-value handling. The image appendix remains a complete prerequisite if images enabled. | T/N |
| 3.0 feature macros: `__opencl_c_3d_image_writes`, `__opencl_c_images`, `__opencl_c_read_write_images`, `__opencl_c_fp64`, `__opencl_c_atomic_order_acq_rel`, `__opencl_c_atomic_order_seq_cst`, `__opencl_c_atomic_scope_device`, `__opencl_c_atomic_scope_all_devices`, `__opencl_c_device_enqueue`, `__opencl_c_generic_address_space`, `__opencl_c_pipes`, `__opencl_c_program_scope_global_variables`, `__opencl_c_subgroups`, `__opencl_c_work_group_collective_functions` | O U(g). Disabled in pilot. Before enabling one, qualify the corresponding complete type/builtin/API feature and dependent macros. Generic address spaces and program globals need provenance/lifetime; atomic scopes need every participant; collectives need exact group membership. `__opencl_c_int64` follows the retained integer support when C 3.0 is enabled. | T/A/P/S/N/W |
| Considered extensions: fp16 arithmetic, fp64, int64 atomics, integer dot product, extended bit operations, subgroup shuffle/ballot/vote/reduction, command buffers/graphs, external memory/semaphores, GL/Vulkan sharing, USM | O U(g). No advertised extension or borrowed hardware semantics. Retain bounded AOT/graph alternatives for assessment; external handles cannot bypass manifest authority. Matrix use is a backend proof, not a new source language. | T/A/P/S/N/W |
| Extension feature macros for packed/unpacked 4x8-bit integer dot products, device/work-group/sub-group kernel clocks, extended 2_101010/10x6_12x4_14x2 image formats | O U(g). The remaining feature-table entries are disabled with their owning extensions; clock features need timing authority, dot products exact arithmetic witnesses, and image formats complete conversion evidence. | T/A/N/W |
| SPIR-V module structure, types, instructions, decorations, storage classes, execution modes and environment validation | U(d,e). Validate the selected environment, version, ID bounds, entries and memory model before translation. Preserve `Addresses`, `Float16Buffer`, `Int64`, `Int16`, `Int8`, `Kernel`, `Linkage`, `Vector16` baseline capabilities; a capability's complete semantics remain U(g) outside pilot operations. Resolve linkage and every specialization at production. | T/A/N/S |
| SPIR-V optional `DeviceEnqueue`, `GenericPointer`, `Groups`, `Pipes`, `ImageBasic` and dependent image capabilities, `Float64` | O U(g). Reject unless that complete OpenCL feature has separately qualified evidence; the [environment capability dependencies](https://github.com/KhronosGroup/OpenCL-Docs/blob/85da0d12c298ffa9eefd2adb1864f2c8193cbe3e/env/required_capabilities.asciidoc) control the dependency closure. | T/A/P/S/N |

## Full and embedded verdicts

**Neither profile is qualified.** Full profile has the online compilation
conflict. Embedded removes that requirement, but does not remove binary/built-in
program behavior, the language/host baseline, resources, numerics or conformance
evidence. The admitted-program restriction and unimplemented mandatory features
are visible remaining gaps, not an embedded-profile claim.

The device-query audit includes every parameter in the frozen full and embedded
query tables, including type, valid value, minimum maximum, consistency with
optional support, reference count and error behavior. Q30g must compare an
actual manifest to those tables before any profile claim. The pilot deliberately
does **not** claim those minima: its 8 MiB maximum buffer is below the full-table
32 MiB floor, which also applies to embedded absent an overriding exception.
That choice is an experiment size, not a physical or admitted-machine limit.
Other mandatory minimum families include allocation/global/local/constant
memory, argument storage/count, work dimensions, timer resolution, alignment,
vector widths and `printf` buffering. All are U(f,g); none is waived by a
small benchmark passing.

The embedded exception audit additionally covers optional 64-bit integers and
their double-precision dependency; permitted basic-FP rounding and special-value
behavior; half conversion denormal treatment; image channel conversion accuracy
and endpoints; image argument/dimension/format/sampler minima; parameter bytes;
constant storage/arguments; local memory; compiler/linker reporting; device-queue
and `printf` buffers. Pre-2.0-only relaxations of 3D images, image-array writes
and linear floating-image filtering do not authorize a 3.0 exception. The
[embedded source](https://github.com/KhronosGroup/OpenCL-Docs/blob/85da0d12c298ffa9eefd2adb1864f2c8193cbe3e/api/embedded_profile.asciidoc)
is the owner of those exceptions. The pilot selects FP32 RNE and complete
special/subnormal handling rather than using embedded relaxations to hide a gap.

No CTS execution has occurred. Q30g must pin the conformance corpus and
configuration at execution, report every pass/failure/exclusion and complete
the applicable Khronos conformance process before using a conformance claim.
Q30b/Q30c use upstream tests as references but cannot substitute their narrow
kernel results for that separate verdict.

## Reproducing command-inventory coverage

Fetch the unmodified `xml/cl.xml` at the frozen OpenCL-Docs commit into an
ignored output directory, then run `python tools/run.py compute-audit PATH --json`.
The [inventory checker](../../tools/vos/compute_audit.py) verifies its exact byte
digest, derives core command membership from every 1.0-through-3.0 feature block
and compares it with explicit identifiers in the host table's subject cells.
It rejects missing, duplicate or unknown command coverage; shorthand in another
column cannot satisfy membership. Keep the JSON result with the dated review
evidence. The result establishes enumeration coverage only: the full/embedded
conditions, numeric rules, observables and proof judgments still require the
attended Q30a review. No upstream source is vendored by this operation.
