# Merged upstream opportunities

Review dated **2026-10-22 (America/Chicago)** against VerifiedOS
`7a183c2b9d1ca41e1df2c8b470a4781cf815dac0`. The recent-past window is
**2026-07-22 through 2026-10-22**. The [PR tracker](upstream-prs.md) owns
contributions and open watches; this review owns the retrospective adoption
judgments below. It changes no dependency pin, implementation estimate or
acceptance predicate.

[PLAN.md](../../PLAN.md#upstream-adoption-recommendations) owns adoption execution.
The [bounded adoption contract](upstream-adoption.md) owns the selected changes'
technical acceptance and validation scope. The findings below retain their stated
review revision.

The scope is every direct upstream gitlink, the additional projects named by the
tracker, and the relevant compiler, proof, compute and host-tool donors named by
their local owners. Evidence comes from first-party commit histories, merged PR
diffs, release notes and local consumers. Direct commits are included: a useful
change need not have a PR. High-volume projects received topical source review;
this is not a claim to have semantically audited every upstream diff or the
entire transitive package graph. No upstream build, test, proof replay or benchmark
was executed for this survey. A selected reference pin and a qualified executable
consumer are different facts.

## Recommended order

[PLAN.md](../../PLAN.md#upstream-adoption-recommendations) owns the recommended
order and the execution actions associated with the evidence below.

## Model and hardware

| Available upstream change | Present local use and opportunity |
| --- | --- |
| **Indexed segment-store overlap legality.** [sail-riscv #1990](https://github.com/riscv/sail-riscv/pull/1990), merged 2026-10-09, `94139d1b7413cdbe517a80dcdb8b365b2189af0e`, checks every segment field's source overlap. | The reference pin includes it, but `execute VSXSEGTYPE` in [vext_mem_insts.sail](../../model/model/extensions/V/vext_mem_insts.sail) still calls the non-segmented `valid_src_overlap`. This is an actual curated-source adoption gap, separate from tracker candidate 33's legality-before-assertion issue. |
| **A smaller vector-length representation.** [sail-riscv #2026](https://github.com/riscv/sail-riscv/pull/2026), merged 2026-10-19, `cd3f185e3a40cd402632d78a2bc213d62ae6f753`, narrows `vl` to `bits(vlen_exp + 1)`. | The current gitlink is that change; [vext_regs.sail](../../model/model/extensions/V/vext_regs.sail) still declares `vl : xlenbits`. A bounded representation can remove impossible states and reduce generated state/term size. No size or speed improvement is measured here. |
| **Assertion controls that cannot be switched off by the design.** [Verilator #8086](https://github.com/verilator/verilator/pull/8086), merged 2026-08-12, `44fe96b2da73e6ea9cd45e7ac00bb616efbcb85a`, adds `+verilator+assert+lock`. | The locked Verilator 5.052 already has this facility. [_verilate](../../tools/vos/cli/testrig.py) builds the frame fixture without `--assert`, and its simulator launch does not lock assertion controls. Existing explicit fixture self-checks remain useful; the opportunity concerns assertions in a real attached core. |
| **AXI request, response and completion observation.** Mocha's [event-port addition](https://github.com/lowRISC/mocha/commit/35d5ebc383ac20ad0b918a5fd30db11047ca2805) and [same-ID ordering repair](https://github.com/lowRISC/mocha/commit/7a654caed0e1121e9ad405038ea40f9a0840a49d) landed 2026-10-21, after the selected `f9bacf5d` reference. | The [co-simulation contract](../assurance/rtl-cosimulation-harness.md#8-the-revocation-join) still proposes a device-completion monitor. Existing donor transaction collection and scoreboards could supply its AXI observation layer. |
| **Failing explicitly on unlowered formal checks.** Yosys [b7b8ea97846f6d3f8509187a5f6c71c458f74e15](https://github.com/YosysHQ/yosys/commit/b7b8ea97846f6d3f8509187a5f6c71c458f74e15) landed 2026-08-13 and refuses residual `$check` cells in the SMT2/BTOR path. | The [R2 contract](../assurance/rtl-cosimulation-harness.md) already requires retained properties and failing controls, but no local qualified Yosys pin establishes this behavior. |
| **Concurrency-interface v2.** [sail-riscv #1871](https://github.com/riscv/sail-riscv/pull/1871), landed commit `4f8ce828fcacd6f392cb4f9be9046d46ce4bec07`, dated 2026-10-01, adds byte-vector memory requests, architecture access classifiers and explicit address-space/tag-count fields. | The curated [physical-memory interface](../../model/model/core/phys_mem_interface.sail) uses the older request API and standalone tag primitives. The new framework is relevant to a future Q35r/Q35s port. |

## Proof interfaces and compiler construction

| Available upstream change | Present local use and opportunity |
| --- | --- |
| **Broader Rocq dependent-pair emission.** [Sail #1794](https://github.com/rems-project/sail/pull/1794), merged 2026-10-22, `57fd0cef057bb90ed58208599056439edee22e60`. | Q35o's retained backend trial predates it. The model uses existential tuples and width-multiplied bitvector payloads, making witness inference relevant. No current canonical failure is attributed to this exact defect. |
| **Reject inconsistent instantiated configurations.** [Sail #1780](https://github.com/rems-project/sail/pull/1780), landed commit `9a6b307658ce6fd77788937d192185746cac2d9e`, dated 2026-10-16, adds `Frontend.check_instantiated_constraints`. | The acceptance compiler remains 0.20.3. The model has configuration-selected abstract values and global constraints, alongside its authored [configuration validation](../../model/model/postlude/validate_config.sail). Compiler-level refusal can complement that layer before emission. |
| **A common Stdlib-bits word theory across the lowering stack.** September 14–18 landed work in [coqutil #187](https://github.com/mit-plv/coqutil/pull/187), [riscv-coq #54](https://github.com/mit-plv/riscv-coq/pull/54), [bedrock2 #565](https://github.com/mit-plv/bedrock2/pull/565) and [Rupicola #226](https://github.com/mit-plv/rupicola/pull/226) replaces the older word interfaces; [riscv-coq #60](https://github.com/mit-plv/riscv-coq/pull/60) and [bedrock2 #572](https://github.com/mit-plv/bedrock2/pull/572) update byte-group load/store interfaces. | The Rupicola reference already contains the migration, while the runnable [lowering snapshot](../../tools/opam/rupicola.lock) and actual [DescriptorCheck client](../../tools/bedrock2-lowering/DescriptorCheck.v) use the older release/typeclass interfaces. This is a coordinated API reuse opportunity beyond the already-recorded warning-compatibility repairs. |
| **Reasoning about known M-mode code through a universal contract.** [Katamaran #76](https://github.com/katamaran-project/katamaran/pull/76), merged 2026-10-21, `3229c62ba0c424a0f6346d622907238c94885bb2`. | The selected `8b953fe8` reference predates it. Q35's [machine-logic work](../assurance/machine-logic-breakdown.md) needs a universal capability contract, making its separation of known and adversarial code a useful proof-organization reference. |
| **ANF assumptions and a Wasm invariant bridge.** [CertiRocq #158](https://github.com/CertiRocq/certirocq/pull/158), merged 2026-09-04, `906241771e0ac0088403dec12a0027213f114dd1`, repairs unprovable LambdaBox-to-ANF assumptions; [#164](https://github.com/CertiRocq/certirocq/pull/164), merged 2026-10-20, `9b1740d1cd06db5c3b686bf80f157c1a0c680e23`, derives backend `NoDup` from middle-end `unique_bindings`. | The host-side Wasm oracle remains on the qualified release and separately deferred compatibility work. These are concrete theorem-interface improvements to assess when that oracle next moves. |
| **C-implemented constants and box duplication.** [CertiRocq #170](https://github.com/CertiRocq/certirocq/pull/170), merged 2026-10-22, `ab10dd8686d2d44e3b901d7a521a81bd76ea9cff`. | Potential functional repairs for future C-FFI or bootstrap consumers. The upstream change explicitly includes unverified passes and admitted correctness obligations. |
| **Capability-aware Rust calling conventions and named authority interfaces.** [cheri-rust #244](https://github.com/CHERIoT-Platform/cheri-rust/pull/244), merged 2026-07-27, adds experimental library/compartment conventions; [#245](https://github.com/CHERIoT-Platform/cheri-rust/pull/245), merged 2026-07-30, adds `cheriot_mmio`; [#253](https://github.com/CHERIoT-Platform/cheri-rust/pull/253), merged 2026-08-12, adds `cheriot_shared_object` and permission checks. | These changes are already in selected `e6026b48`. The [donor survey](../assurance/proof-reuse/languages.md#cheriot-rust-selected-functional-capability-aware-compiler-baseline) inventories their source implementation. They are reuse candidates without a pin update. |
| **Use address width in pointer simplification.** Rust [56fede178c18d18ea3cda56c33217f8c718157d0](https://github.com/CHERIoT-Platform/cheri-rust/commit/56fede178c18d18ea3cda56c33217f8c718157d0), 2026-10-22, corrects `simplify_binary_inner` in GVN. | This is newer than selected `e6026b48`. The certifying Rust producer must distinguish pointer address bits from the full capability representation; the donor correction is a specific adaptation input. |

## Wasm, cryptography and compute

| Available upstream change | Present local use and opportunity |
| --- | --- |
| **Official relaxed-SIMD and interpreter repairs.** WebAssembly/spec [#2252](https://github.com/WebAssembly/spec/pull/2252) and [#2273](https://github.com/WebAssembly/spec/pull/2273), merged 2026-10-09, repair relaxed-dot pairwise-result choices and NaN propagation rules; [#2296](https://github.com/WebAssembly/spec/pull/2296), merged 2026-10-21, repairs madd rounding and following DET; [#2295](https://github.com/WebAssembly/spec/pull/2295), merged that day, repairs UTF-8 handling. | The [source survey](../assurance/proof-reuse/parsers.md#other-source-leads) reads `95dffb694` from September. [Q34g's execution contract](contracts/wasm-execution.md) needs full Core 3.0 and generation-fixed DET choices, with one shared feature-mapped corpus. No implemented local interpreter is diagnosed by these upstream fixes. |
| **A legal boundary-slice evaluation case.** SpecTec [f4f22691f9345d8ff795839fed77eab48474ab36](https://github.com/WebAssembly/spec/commit/f4f22691f9345d8ff795839fed77eab48474ab36), 2026-10-20, changes a slice-bound comparison from `<` to `<=` in the SpecTec IL evaluator. | Relevant to tracker candidate 44's SpecTec concerns and to generated-semantics qualification, rather than a guest Wasm slicing operation. |
| **A verified P256 inversion implementation.** [Fiat-Crypto #2444](https://github.com/mit-plv/fiat-crypto/pull/2444), landed 2026-10-14, verifies `src/Bedrock/P256/modinv/beeu_modinv.v`; subsequent refactoring is already present in selected `1e721c6f`. | The [emission contract](fiat-crypto-emission.md) deliberately covers C field arithmetic/serialization and makes no divstep or inversion claim. The Bedrock implementation is a concrete separate candidate when a P256 inversion consumer is required. |
| **Basic BF16 arithmetic and signaling-NaN classification.** SoftFloat [#44](https://github.com/ucb-bar/berkeley-softfloat-3/pull/44), merged 2026-10-20, `73e3f397e84d6d2a34bded52b0a77af3f4062ac2`, fixes `isNaNBF16UI`; [#45](https://github.com/ucb-bar/berkeley-softfloat-3/pull/45), merged 2026-10-21, `32eb3295a3c814c1551f94ebc29eed1dec3cb3b1`, adds basic BF16 routines. | The vendored `a0c6494c` edition has conversions, while the current ISA already admits selected BF16 conversion/widening operations. The new routines offer additional host-side reference cases; their presence is not a reason to expand the ISA. |
| **Correct integer div/rem lowering.** PoCL [#2349](https://github.com/pocl/pocl/pull/2349), merged 2026-10-09, `9448868fd8056b3f44fb866141247d8df9ebe988`, fixes `x/x` folding; [#2397](https://github.com/pocl/pocl/pull/2397), merged 2026-10-16, `2fbe734a389d256efd8e2678d9eab27bd055d04a`, constructs signed minima with exact-width `APInt`. | [Q30a's PoCL 7.2 reading](compute-upstream-review.md) predates these corrections. Q30b/Q30e need defined integer edge cases and faithful scalar/vector lowering, although no running local compute implementation is diagnosed. |
| **More discriminating compute conformance results.** OpenCL-CTS [#2806](https://github.com/KhronosGroup/OpenCL-CTS/pull/2806), merged 2026-09-22, `aca427c16ffad0666a248753886369d14686965a`, makes zero comparisons sign-aware; [#2815](https://github.com/KhronosGroup/OpenCL-CTS/pull/2815), merged 2026-09-29, `9feccbb8fcb8eefeebf86a48036173a8155f9d21`, reports an all-selected-tests-skipped result. | Both postdate Q30a's `e7dcbda5` corpus reading. They improve a comparison's ability to distinguish wrong-sign zero and absent execution. |
| **Explicit subgroup-width assumptions.** chipStar [#1721](https://github.com/CHIP-SPV/chipStar/pull/1721), merged 2026-10-01, and [#1934](https://github.com/CHIP-SPV/chipStar/pull/1934), merged 2026-10-14, control per-kernel subgroup size and report actual runtime `warpSize`. | The [local compute feature map](compute-feature-map.md) explicitly excludes subgroups. This is a conditional design reference, not a missing supported feature. |

## Proof inspection and host tools

| Available upstream change | Present local use and opportunity |
| --- | --- |
| **Round-trip checked printing.** [Rocq #22283](https://github.com/rocq-prover/rocq/pull/22283), merged 2026-09-09, `b976bec796825da1faf5519618dd4fca79ae8f92`, adds `Printing Reversible Up To Conversion` and weaker modes. | Q35q and the [proof-reading route](../../tools/vos/cli/proof_reading.py) depend on faithful native declaration output. Re-elaborating printed terms and checking strict conversion is a useful additional producer control. |
| **Inspection and size limits.** [Rocq #22570](https://github.com/rocq-prover/rocq/pull/22570), merged 2026-10-08, `a3b64e002ac87695881c1679717b8128b8ab7e57`, repairs an opaque-module assumptions lookup; [#22512](https://github.com/rocq-prover/rocq/pull/22512), merged 2026-09-21, `f24ba391d0d23cfeb9de97d4f2265dc541c676f1`, reads large marshal headers in `rocqchk`. | Both are useful qualification cases for the current native proof tooling and Q35b's still-owed compiled-term size. No present object-size failure is attributed to the header limit. |
| **Conversion-height control and diagnostics.** [Rocq #22528](https://github.com/rocq-prover/rocq/pull/22528), merged 2026-10-17, `48f0eb1ffac685abe1d4887cdfd578c170481441`, adds the height heuristic and `Print Height(s)`. | The proof route already records conversion settings. This provides another way to investigate expensive conversion on a large canonical term. |
| **Replayable SMT proof interfaces.** Z3 [#11224](https://github.com/Z3Prover/z3/pull/11224), merged 2026-10-19, `c9e327fec716ff5419c15800d072515bb7855381`, extends Lean reconstruction for UF/integer/linear arithmetic; [#11264](https://github.com/Z3Prover/z3/pull/11264), merged 2026-10-22, `d6810210a52cf3b37bfc07c20bfa9811b8d278c4`, adds opt-in clausal SMT search proofs and F* checking. | The [finite placement check](../../tools/vos/cli/placement.py) reports solver evidence; the separate [memory certificate route](static-memory/certificates.md) uses LRAT and does not replay individual certificates in Rocq. These new interfaces are optional research candidates for richer per-instance explanations. |
| **Unsigned CLI rejection.** [CLI11 #1472](https://github.com/CLIUtils/CLI11/pull/1472), merged 2026-10-14, `08ca3298f6704bfe652f5b85e1bc22dc2800ac5f`, refuses negative payloads after binary/octal prefixes. | [CLI11 2.7.2](../../model/dependencies/CLI11/CMakeLists.txt) predates it, and [the emulator CLI](../../model/c_emulator/cli_options.cpp) binds instruction limits and watchdog periods to unsigned values. This is a concrete maintenance candidate, not a new machine feature. |
| **Already-installed capabilities and immature additions.** Recent uv cooldown handling, zizmor's improved worktree/PowerShell analysis, action updates and opam/OCaml refreshes largely match the current tool owners. zizmor [#2461](https://github.com/zizmorcore/zizmor/pull/2461), merged 2026-10-18, adds lockfile plumbing but explicitly leaves audit integration unfinished. | The project already uses a relative uv release cooldown, strict workflow analysis and pinned actions. New plumbing alone supplies no dependency audit. [setup-uv 10.3.1](https://github.com/astral-sh/setup-uv/releases/tag/v10.3.1) handles concurrent cache conflicts more cleanly. |

## Coverage and dispositions without new adoption work

The ledger records what was examined and why a project does or does not produce
an action above. An absence of a relevant delta is a survey disposition, not a
proof that the upstream has no useful code. Commit histories and selected PR
diffs complement each other; the PR-search census was incomplete for some large
repositories, including OpenTitan, Verilator and Yosys.

| Upstream scope | Disposition |
| --- | --- |
| `riscv/sail-riscv` | Curated-versus-reference comparison identifies the segment-store and `vl` opportunities above. Earlier widening-accumulate overlap and ELF-loader bounds repairs are already carried. The concurrency-v2/event framework requires a separate semantic decision; it is not a drop-in replacement for the fixed single-hart canonical anchor. |
| `CTSRD-CHERI/sail-cheri-riscv`, `sail-cheri-riscv-verif`, `TestRIG`, `cheri-compressed-cap`, `qemu` | Retained semantics, properties and comparison/instrument roles inspected. No additional bounded adoption is selected; the helper properties are already transcribed, and generic QEMU/hardware additions do not supply frozen-ISA correspondence. |
| `lowRISC/mocha`, `cva6-cheri`, `opentitan`, `ibex`; `microsoft/cheriot-ibex`; `Capabilities-Limited/axi_cheri_tagcontroller` | AXI observation is actionable above. Maintained Ibex CHERIoT/TRVK integration is already distinguished from the older Microsoft donor in the third-party ledger. New platform wiring and upstream privilege/cache facilities do not relax the absence contract or qualify physical sensors. |
| `YosysHQ/riscv-formal`, `YosysHQ/yosys`, `verilator/verilator` | Assertion locking and fail-closed frontend qualification above. Existing signed division, xperm and REMUW watches remain unresolved, and Zicond still needs generator-backed models. Temporal-assertion fixes after locked Verilator need qualification if the selected core uses those constructs. |
| `rems-project/sail`, `rems-project/coq-sail` | Dependent-pair emission above. Merged top-level monadic-value PR 1790 is already recorded in candidate 18; it does not settle notation ownership or tag outcomes. Eqdep/optional-real and strict-source proposals retain their tracker scope. |
| `rocq-prover/rocq`, `rocq-prover/stdlib`, `tchajed/coq-record-update` | New producer/checker controls above; soundness backports and merged checker/module-printing work are already tracked. New stdlib list/string lemmas are potential conveniences without an identified local blocker; no broad rewrite is proposed. Record-update compatibility remains open. |
| `secure-compilation/SECOMP` | Current reference changes do not close the robust-security theorem or back-translation defects. Candidates 23/24/35/36 and Q39/U-25 retain ownership; a compiler reference refresh supplies no soundness acceptance. |
| `katamaran-project/katamaran`, `sail-backend`; `logsem/cerise`, `cerisier`, `machine_utils` | Universal-contract work above. The merged unused-import repair is already selected for the compatibility continuation. Unchanged donors do not close strict notation or licensing refusals. |
| `mit-plv/rupicola`, `bedrock2`, `coqutil`, `riscv-coq` | The coherent Stdlib-bits migration above is additional to the warning-compatibility gap already recorded by the [opam owner](../../tools/opam/README.md). A newer reference alone does not move the runnable lowering switch or close its target transport. |
| Iris, stdpp and VST | Iris [time receipts](https://gitlab.mpi-sws.org/iris/iris/-/commit/f447c1b786e098101a2aee2dfbb1c394350d8d83), [generic later credits](https://gitlab.mpi-sws.org/iris/iris/-/commit/4bfd6a2edbf5e2d6820d554e11668b615cc4f5f3) and step-index changes are future proof-carrier references; receipts for logical laters do not establish physical cycle-cost upper bounds. Development Rocq compatibility does not remove local blockers. VST's [CompCert regeneration](https://github.com/PrincetonUniversity/VST/pull/870) is already covered; its [larger `WITH` binder limit](https://github.com/PrincetonUniversity/VST/pull/871) has no identified local client. |
| QuickChick, ExtLib and simple-io | Recent default-branch work is compatibility/CI maintenance, with an additional [RunIO expression repair](https://github.com/Lysxia/rocq-simple-io/commit/5c70625af00af6182817e490d93247cdefbed2e1). The authored current harnesses use no `RunIO` command. The [opam owner's qualified-pin policy](../../tools/opam/README.md) already covers moving this separate instrument closure; no current failing consumer or new required feature is established. |
| `CertiRocq/certirocq`, CertiCoq and its Wasm library | The ANF/invariant bridges above are additional inputs. Bootstrap/compatibility and Docker fixes are already tracked or deliberately deferred; the retrospective does not resume that deferred adoption. |
| `llvm/llvm-project`, `CHERIoT-Platform/cheri-rust` | Targeted capability, pointer, calling-convention, vector and proof-producer seams inspected. Rust findings above are concrete. Generic LLVM optimizations, new target support and intrinsics do not establish capability preservation, CT/WCET or a verified frontend. |
| `WebAssembly/spec`/SpecTec, WasmCert-Coq, Iris-Wasm and Wasm/component reference candidates | Official fixtures and interpreter fixes above. WasmCert's inconsistent-axiom cleanup and guard are already covered by the October dependency reading; their merged status does not erase the remaining parser, concrete numeric/SIMD, array and host-correspondence obligations. |
| `logsem/iriswasm`, `tyfkda/xcc`, `false-schemers/wcpl` | No recent default-branch change in Iris-Wasm or WCPL. xcc's newer [diswasm execution](https://github.com/tyfkda/xcc/commit/631e318432aeaaf72d6d2dfc93085766934314a2) and [stream flushing](https://github.com/tyfkda/xcc/commit/9eea241c1331d54730b9173cfb11c4dea7c893a4) fixes are inputs to Q34h's eventual producer/tool qualification, without a demonstrated current local consumer failure. The existing native wcc starting point and WCPL fallback remain separately scoped. |
| `mit-plv/fiat-crypto`, `hacl-star/hacl-star`, `formosa-crypto/libjade`, OpenSSL | Inversion is a scoped future recipe input above. Existing emitted field routines and the OpenSSL 3.5.9 oracle already have owner-bound refresh evidence; no further HACL*/Libjade feature is selected. Zig or donor-architecture constant-time checks do not prove local target constant time. |
| PoCL, oneAPI Construction Kit/Vecz, chipStar, SPIRV-Tools and OpenCL-CTS | Use existing barrier/tail, subgroup and arithmetic regression work at Q30's common pilot seams. Existing donor transformations and conformance sources are already selected research inputs; no complete runtime or generic CTS pass becomes local admission. |
| CLI11, Asio, jsoncons, ELFIO, SoftFloat and sail-riscv-tests | CLI/BF16 opportunities above. ELFIO is already at the reviewed development source; newer Asio scheduling/reactor features and jsoncons CSV/CBOR/JSONPath work have no identified current consumer. The newer privileged/hypervisor test-suite support is outside the frozen profile. |
| Z3, opam, OCaml, Python, uv, ty, Ruff, zizmor, actionlint and the pinned GitHub Actions | Certificate research and focused maintenance above. Existing modern interpreter/tool pins already expose the relevant basic patterns. No unmeasured switch from process isolation to subinterpreters, automatic toolchain upgrade or new workflow trust is proposed. |
| `cappadokes/idealloc`, `lammich/lrat_isa`, `arminbiere/cadical` | No commits in the selected recent-past histories. Existing optional candidate and LRAT integration remain the concrete reuse paths; no second solver/checker integration is justified by this survey. |

## Consume upstream and contribute the portable remainder

Adoption comparisons run in both directions. Prefer consuming the upstream
implementation when it meets the local contract, preserving any demonstrably
stronger local behavior. If that remaining behavior is useful beyond VerifiedOS,
prepare the smallest upstream change and a distinguishing regression. A local
fork, stricter policy or different architecture is not by itself evidence of a
better implementation.

The comparison actions and their existing tracker owners are in
[PLAN.md](../../PLAN.md#upstream-adoption-recommendations).

No new upstream submission is created by this review. The concrete generic
contribution opportunities identified here already have tracker owners; a newly
demonstrated residual should be added there with evidence and acceptance scope.

## Follow-through

Each action returns to its named implementation/qualification owner. Re-read the
selected upstream license and dependency closure before incorporation; a source
link here copies no implementation and establishes no new distribution decision.
Model/Sail and proof changes retain their portable assistance workflows. Focused
local checks may guide implementation, while complete gates and all benchmarks
remain on GitHub Actions. Changes to normative scope require the register before
coverage or implementation changes.

Future tracker reviews should pair forward watches with a retrospective comparison
against both the selected reference and the source/executable actually consumed.
Record merge time separately from commit time, retain useful direct commits, and
classify a candidate as newly available, present but unused, already adopted,
already tracked/deferred, or inapplicable. That avoids mistaking pin freshness for
adoption and prevents repeatedly proposing work the donor already supplies.
