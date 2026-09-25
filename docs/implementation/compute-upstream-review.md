# Compute candidate source and dependency review

Q30a readings dated 2026-09-19. These are reproducible survey revisions, not
gitlink pins, installed toolchains or incorporated source. No candidate is
trusted by the admission checker. [COPYRIGHT.md](../../COPYRIGHT.md#terms-this-tree-does-not-carry)
and [THIRD-PARTY.md](../../THIRD-PARTY.md) govern any later incorporation;
the selected build and distribution closure must be recorded there before use.

## Candidate decisions

| Candidate and exact revision | Source and dependency reading | Decision for the bounded pilot |
| --- | --- | --- |
| PoCL 7.2, `888c9774b94590fff1afef003154ca2c0ea66605` | [Workgroup.cc](https://github.com/pocl/pocl/blob/888c9774b94590fff1afef003154ca2c0ea66605/lib/llvmopencl/Workgroup.cc) builds a work-group wrapper; [WorkitemLoops.cc](https://github.com/pocl/pocl/blob/888c9774b94590fff1afef003154ca2c0ea66605/lib/llvmopencl/WorkitemLoops.cc) constructs work-item loops around synchronization phases. [CMakeLists.txt](https://github.com/pocl/pocl/blob/888c9774b94590fff1afef003154ca2c0ea66605/CMakeLists.txt) and [LLVM.cmake](https://github.com/pocl/pocl/blob/888c9774b94590fff1afef003154ca2c0ea66605/cmake/LLVM.cmake) select LLVM/Clang, optional SPIR-V translation, host threading, ICD/headers and optional math/device libraries. | First reference route for source/IR equivalence and work-group lowering, including an independently generated scalar reference. Extract pass boundaries for correspondence checking. Existing runtime compilation, cache/loading, allocation and threading are not the native runtime contract. No PoCL output is admitted merely because upstream reports CTS success. |
| Codeplay oneAPI Construction Kit 4.0.0, `538093a2ecdb490ae0dc56ffd97c7ca785564e86` | [README](https://github.com/codeplaysoftware/oneapi-construction-kit/blob/538093a2ecdb490ae0dc56ffd97c7ca785564e86/README.md) describes the RISC-V reference target and LLVM/Clang/lld prerequisites. [Vecz design](https://github.com/codeplaysoftware/oneapi-construction-kit/blob/538093a2ecdb490ae0dc56ffd97c7ca785564e86/doc/modules/vecz/vecz.md) exposes a standalone IR vectorizer, builtin replacement and target-specific memory builders. Barrier IDs must survive vectorization and the work-item-loop join. | Compare Vecz against PoCL's lowering at Q30e before authoring a new transformation. Its explicit barrier correspondence and memory hooks are useful witness seams. Neither supplies a CHERI-TAL proof, target timing theorem or matrix instruction. Choose by retained semantics and certificate feasibility for the frozen kernels; no unmeasured speed ranking is asserted. |
| chipStar 1.2.1, `3bd6515ebe2a84f2f6d17bee53ed14a5d19a0856` | [CMakeLists.txt](https://github.com/CHIP-SPV/chipStar/blob/3bd6515ebe2a84f2f6d17bee53ed14a5d19a0856/CMakeLists.txt), [FindLLVM.cmake](https://github.com/CHIP-SPV/chipStar/blob/3bd6515ebe2a84f2f6d17bee53ed14a5d19a0856/cmake/FindLLVM.cmake) and [usage guide](https://github.com/CHIP-SPV/chipStar/blob/3bd6515ebe2a84f2f6d17bee53ed14a5d19a0856/docs/Using.md) expose HIP-to-SPIR-V, OpenCL/Level Zero backends, LLVM/Clang/translator requirements, runtime module compilation and SVM/USM allocation choices. [.gitmodules](https://github.com/CHIP-SPV/chipStar/blob/3bd6515ebe2a84f2f6d17bee53ed14a5d19a0856/.gitmodules) names HIP/HIPCC/device libraries/tests and optional H4I libraries. | Reuse candidate for HIP producer adaptation, not a second runtime. Preserve HIP source semantics through checked SPIR-V translation, then use the same native dispatch as OpenCL. Replace runtime module loading/allocation authority with pre-admitted entries and pools. Exclude Level Zero/AMD drivers, lazy JIT, USM and H4I/MKL from the proposed pilot closure. |

PoCL and Codeplay are complementary candidate transformations over existing
source semantics. The first bounded experiment compares the same barrier
stencil and tails at their IR seams, including rejected transformations; the
winner is not fixed by a popularity or language-design claim. If neither can
emit checkable witnesses, Q30d/Q30e return a priced correspondence/lowering gap
before authoring replacement machinery. Source/IR pass re-use confers no right
to replace the original-source theorem with a theorem beginning after parsing.

chipStar's selected HIP gitlink is **not** the separately selected ROCm 6.3.0
API revision. Its implementation candidate and the compatibility target have
different identities. Q30d must compare the exact pilot declarations, launch
lowering, error values and stream behavior against the target headers before
reuse; mismatches are adapter work, never an assumed version equivalence.

## License and closure findings

The readings include the selected revision's own license files, not repository
badges or inferred project lineage. The intended reuse is a build-time producer
and separately qualified bounded adapter; no current distribution is proposed.

| Component | Exact source reading and disposition |
| --- | --- |
| PoCL | [LICENSE](https://github.com/pocl/pocl/blob/888c9774b94590fff1afef003154ca2c0ea66605/LICENSE) points to [COPYING](https://github.com/pocl/pocl/blob/888c9774b94590fff1afef003154ca2c0ea66605/COPYING), whose grant is MIT. [LICENSE.with.3rdparty](https://github.com/pocl/pocl/blob/888c9774b94590fff1afef003154ca2c0ea66605/LICENSE.with.3rdparty) separately identifies pthread-barrier code, Level Zero, OpenCL headers, SLEEF, hwloc and LLVM. Read the actual component files before selecting builtins; the [libclc ROCm notice](https://github.com/pocl/pocl/blob/888c9774b94590fff1afef003154ca2c0ea66605/lib/kernel/libclc/ROCM_LICENSE.txt) carries University of Illinois/NCSA terms, so calling all included code MIT would be false. |
| Construction Kit / Vecz | [Top-level license](https://github.com/codeplaysoftware/oneapi-construction-kit/blob/538093a2ecdb490ae0dc56ffd97c7ca785564e86/LICENSE.txt) and [Vecz license](https://github.com/codeplaysoftware/oneapi-construction-kit/blob/538093a2ecdb490ae0dc56ffd97c7ca785564e86/modules/compiler/vecz/LICENSE.txt) state Apache-2.0 with LLVM exceptions. The top-level inventory separately names fetched OpenCL headers/ICD/intercept layer, SPIR-V headers, googletest/benchmark, cargo-derived utilities, generators, musl and Spike-derived examples/loaders. A scoped Vecz producer selection must trace which of these actually link or contribute generated bytes; neither an example driver nor a simulator is automatically shipped. |
| chipStar | [LICENSE](https://github.com/CHIP-SPV/chipStar/blob/3bd6515ebe2a84f2f6d17bee53ed14a5d19a0856/LICENSE) carries MIT terms and additional origin notices, including NVIDIA-supplied code. [spdlog's license](https://github.com/CHIP-SPV/chipStar/blob/3bd6515ebe2a84f2f6d17bee53ed14a5d19a0856/include/spdlog/LICENSE) is MIT; its bundled [fmt notice](https://github.com/CHIP-SPV/chipStar/blob/3bd6515ebe2a84f2f6d17bee53ed14a5d19a0856/include/spdlog/fmt/bundled/LICENSE.rst) carries a two-clause redistribution grant. Per-file notices still need inclusion-closure review; the top-level label cannot clear every dependency. |
| chipStar's HIP fork | Gitlink `a3670d2b094606bf000cea3503756d45d5feaaf7`; its own [LICENSE.txt](https://github.com/CHIP-SPV/HIP/blob/a3670d2b094606bf000cea3503756d45d5feaaf7/LICENSE.txt) carries MIT terms. The fork is a candidate producer dependency, not the compatibility revision. |
| chipStar's HIPCC fork | Gitlink `5885607ac632a0165bddbe6aca1507e7629abdb9`; its [LICENSE.txt](https://github.com/CHIP-SPV/HIPCC/blob/5885607ac632a0165bddbe6aca1507e7629abdb9/LICENSE.txt) carries MIT terms. A build recipe must bind the wrapper as well as clang. |
| chipStar's device libraries | Gitlink `f5ad181fd97ede7973466b292219ebe9d0a7f4d6`; its [LICENSE.TXT](https://github.com/CHIP-SPV/ROCm-Device-Libs/blob/f5ad181fd97ede7973466b292219ebe9d0a7f4d6/LICENSE.TXT) carries University of Illinois/NCSA terms. Any embedded helper becomes part of source correspondence, final-byte identity and the distribution notice closure. |
| HIP and hipBLAS target headers | The selected [HIP license](https://github.com/ROCm/HIP/blob/2451439986f64bf39677e25201367a59457e1991/LICENSE.txt) carries MIT terms. The selected [hipBLAS license](https://github.com/ROCm/hipBLAS/blob/e75831fa5e92638c8473bd01aea65a3df181d041/LICENSE.md) includes MIT and additional LAPACK-origin redistribution conditions. The [runtime declarations](https://github.com/ROCm/HIP/blob/2451439986f64bf39677e25201367a59457e1991/include/hip/hip_runtime_api.h) and [BLAS declarations](https://github.com/ROCm/hipBLAS/blob/e75831fa5e92638c8473bd01aea65a3df181d041/library/include/hipblas.h) define the selected interface; they do not license or qualify an entire AMD runtime by association. |

These direct dependency/source readings are sufficient for candidate selection,
not a completed incorporation audit. Q30d must freeze actual compiler and
translator versions, build flags, fetched/vendor source hashes, generated
builtins, link dependencies and notices for the selected producer slice.
Q30c must do the same for any shipped adapter/library bytes. Optional H4I
libraries, MKL, tests and GPU backends are outside that slice; adding any requires
its own exact-revision reading and revised closure. No installation, source
import, gitlink or distribution permission is implied by this document.

## Reference tests and what they establish

### Supplementary pilot instruments

Readings dated 2026-09-24 add these candidates without incorporating source.

[Oclgrind](https://github.com/jrprice/Oclgrind/blob/5597a379b4f7d74c4af5532260df0366c277259f/README.md)
provides host-side invalid-access, data-race and divergent-barrier diagnostics
over LLVM IR. Its [licence](https://github.com/jrprice/Oclgrind/blob/5597a379b4f7d74c4af5532260df0366c277259f/LICENSE)
is BSD-3-Clause; this edition requires LLVM/Clang 18 or later and C++17.
Q30b qualifies it on a positive kernel and seeded defects before expanding
the population. It is an untrusted development instrument, not target semantics,
an admission checker or a correctness theorem. Stop adaptation at the cell's
qualification allowance and return a priced gap if the frozen IR is unsupported.

[CLBlast 1.7.0's direct GEMM](https://github.com/CNugteren/CLBlast/blob/ca2fc3cb09d4917cc72d4ca661d30296865a4afc/doc/details_gemm.md)
supplies an implementation/case reference including incomplete tiles and
transposes. Its [licence](https://github.com/CNugteren/CLBlast/blob/ca2fc3cb09d4917cc72d4ca661d30296865a4afc/LICENSE)
is Apache-2.0. Q30c reads selected kernel/test notices and compares one frozen
configuration with the exact pilot arithmetic and no-reference cases. Runtime
tuning, indirect-GEMM pre/postprocessing and a whole BLAS runtime are outside
that experiment. A semantic mismatch rejects the implementation candidate;
useful test cases can remain references without changing the frozen contract.

[Berkeley TestFloat 3e](https://www.jhauser.us/arithmetic/TestFloat-3/doc/TestFloat-general.html)
separates operation-level case generation from result checking. Source
`a9c849f1b0eb0264b626d9686ffae167d996e3be` has
[BSD-3-Clause terms](https://github.com/ucb-bar/berkeley-testfloat-3/blob/a9c849f1b0eb0264b626d9686ffae167d996e3be/COPYING.txt).
Q30e may reuse its inputs; Q34g can consume the same source under its different
numeric profile. Adapt rounding, NaNs and target invocation explicitly. The
default oracle uses SoftFloat, already in Sail's dependency closure, so it is
not an independent arithmetic implementation. These incomplete operation tests
prove neither whole-kernel ordering nor target refinement. Consumers retain
qualification costs, with no further estimate discount for this lead.

GPUVerify's [Ms-PL source terms](https://github.com/mc-imperial/gpuverify/blob/master/LICENSE.TXT)
are not MIT; its corpus is not selected for copying under the current
tracked-tree policy. No license conclusion about a parent project replaces
the selected files' incorporation audit.

### Existing conformance sources

The reference corpus candidates are [OpenCL-CTS at e7dcbda5a32cd90ed7dd54189ffda68624c04d2b](https://github.com/KhronosGroup/OpenCL-CTS/tree/e7dcbda5a32cd90ed7dd54189ffda68624c04d2b),
the selected PoCL runtime/compiler tests and Vecz lit tests, and chipStar's
`hip-tests` gitlink `bbbfe89edb2386664395677cff46b59abed2904d` and
`hip-testsuite` gitlink `9b9ebd18fb504a467a5e13a5a3c0a0f926197292`.
The corpus licenses/dependency closure must be read before incorporation or
execution; naming the references copies none of their tests. Pin the exact
selected cases and generated-input seed in the pilot evidence. Run results are
currently **not run**, with no pass, fail or exclusion count claimed. Tests
provide compatibility evidence and negative controls; they do not discharge
the source-correspondence, safety, progress, CT or WCET proof obligations.
