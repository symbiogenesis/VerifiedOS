# Implementation Checklist and Estimates

Execution tracker for [implementation-plan.md](implementation-plan.md). The plan defines scope and rationale; this file records status, evidence, dependencies, and estimates.

## Conventions

* Checked items include concise completion evidence.
* Open-item estimates are attended agent-session hours and are re-priced when split. Percentages are rounded shares of the 782.9 h grand total.
* `Parallel` means the item can proceed in a separate worktree and build directory.
* Later milestones remain deliverable-level until entry.
* The software track is M0–M7, the RTL track is R1–R3, and both meet at M8.

## Current summary

* Completed: M0.1–M0.5, M0.6a, M0.6b, M0.6c/c1, and the initial check/emit/FAST tooling.
* Current serial path: c2 → c3 alongside M0.6d → M0.6e → M0.6f → M0.6g → M0.10 C-class freeze.
* Available parallel work: c4, M0.6e staging, M0.7, M0.11, M0.12 drafting, M1.1, M1.5, M2.1, and M4.1.
* Total estimate: 782.9 h midpoint, approximately 439–1,113 h.
* Progress by estimate: 5.9 of 782.9 h complete (0.8%); 777.0 h remaining (99.2%).
* M8 estimate after planned optimizations: approximately 626–661 h total, with a 340–380 h critical chain.

## M0 · Hardware reference

### Baselines

* [x] **M0.1 · Pin upstream models** · 0.4 h actual · 0.1%
  * `sail-riscv` pinned at `8f91355e`; `sail-cheri-riscv` pinned at `bb07488d`.
  * Finding: the CHERI tree embeds older `sail-riscv` commit `b748a82`; reconciliation therefore requires a semantic transplant, not configuration of one shared base.

* [x] **M0.2 · Stand up the Sail toolchain** · 0.5 h actual · 0.1%
  * WSL Ubuntu 24.04, opam 2.1.5, OCaml 4.14.1, Sail 0.20.2, and z3 4.8.12.
  * Sail 0.20.2 is the required and fidelity-pinned compiler version.

* [x] **M0.3 · Build stock `sail-riscv` baseline** · 0.6 h actual · 0.1%
  * `sail_riscv_sim` built out of tree; 664/664 tests pass.
  * Build scripts raise the OCaml stack limit with `ulimit -s 131072`.

* [x] **M0.4 · Build stock `sail-cheri-riscv` baseline** · 0.5 h actual · 0.1%
  * `cheri_riscv_sim_RV64` built against embedded commit `b748a82`; 229/229 bundled RV64 tests pass under the repository’s C-emulator protocol.
  * This build remains the capability-semantics oracle; no upstream CHERI test corpus is bundled.

* [x] **M0.5 · Reconcile the baselines** · 0.2 h actual · 0.0%
  * Use current `sail-riscv` as the base and transplant the CTSRD capability layer.
  * Rationale: the current base contains required modern extensions and tooling, while excluded CHERI features substantially reduce the transplant surface.
  * AIA exists on neither base and is fresh work under M0.6g.

### M0.6 · Curate the frozen profile

* [x] **M0.6a · Stand up the curated tree** · 0.5 h actual · 0.1%
  * Vendored `model/` byte-identically from `8f91355e` with LF normalization fixed.
  * `tools/build-model.sh` builds out of tree with the larger OCaml stack.
  * Exit evidence: build green; 664/664 tests pass.

* [x] **M0.6b · Measure configuration-level curation** · 0.4 h actual · 0.1%
  * `model/config/verifiedos.json` captures all profile rows supported by the config schema.
  * Profile run: 132/134 adopted-family physical tests pass; both failures are expected profile refusals.
  * Source-level residue: scalar F/D coupling, CSR narrowing and trap totality, `vstart`, and AIA.
  * Decision: configuration identifies the deletion worklist but does not substitute for source removal.

* [ ] **M0.6c · Remove excluded source surface**
  * For every removed extension, update the project file, extension directory, extension registry, config schema, test lists, and stray config readers.
  * Require `tools/check-model.sh`, full build, schema validation, and profile-subset tests after each batch.

  * [x] **c1 · Leaf extensions** · 1.9 h actual · 0.2%
    * Removed unentangled excluded modules, obsolete reservation-size declarations, entropy hooks, dormant targets, and the virtual-memory test half made unusable by removing `FENCE.I`.
    * Net change: 3,079 lines removed and 77 added across 50 files.
    * Exit evidence: build green; 352/352 tests pass; generated and profile config keys match exactly.
    * Expected profile refusals: 26 of 199 physical-variant tests.
    * Reservation plumbing remains for c3.

  * [ ] **c2 · Entangled extensions** · 3 h, range 2–4 · 0.4%
    * Remove `C`, `Zicbom`, `Zicbop`, pointer masking, `Stateen`, CFI/`Zicfilp`, `Smcntrpmf`, and `Zicntr`, including their core and system hooks.

  * [ ] **c3 · Privilege and translation batch** · 6 h, range 4–8 · 0.8%
    * Remove S/U modes, delegation, `satp`, `Sv*` walkers, PMP, reservation plumbing, counters, and remaining virtual-memory tests.

* [ ] **M0.6d · Close the CSR bank** · 3 h, range 2–4 · 0.4%
  * Narrow `mie`/`mip`, hardwire IDs to zero, make `misa` read-only, delete absent CSRs, and trap on unallocated CSR addresses.
  * Implement in the same source pass as c3 where practical, but retain separate completion and estimate tracking.

  * [ ] **c4 · Vector fork** · 3 h, range 2–4 · 0.4% · Parallel with c2
    * Remove `vstart` from vector definitions and decouple vector FP from scalar F/D validation.

* [ ] **M0.6e · Transplant CHERI capability semantics** · 18 h, range 12–24 · 2.3%
  * Port capability types and compression, merged registers, tag memory, PCC/sentries, machine trap capabilities, load/store checks, and ISAv9 trap causes.
  * Differentially compare RVFI-style traces with the M0.4 oracle.
  * Parallel staging now: map old flat files into the extension tree and stand up the differential harness; land after c3.

* [ ] **M0.6f · Re-parameterize to 64+1 bits** · 12 h, range 8–16 · 1.5%
  * Implement the §4.1 field widths and total 32-codepoint permission decode; all-zeroes must decode to untagged NULL.
  * Remove hybrid mode, DDC, SDP, reconstruction operations, exact-bounds operations, subset tests, tag clearing, and colour fields.
  * Representation correctness remains a proof-track obligation.

* [ ] **M0.6g · Add profile rows absent upstream** · 15 h, range 10–20 · 1.9%
  * Add `cmovz`/`cmovn`, `cloadtags`, revocation filtering and bitmap, `fence.t`, capability indexed load/store, `cclear`, and the machine-level AIA pending array.
  * Do not model measurement-conditioned provisional rows yet. The single-check multi-register save is struck from the freeze set (R-15-036n) and is not modeled at all.

* [ ] **M0.6h · Add the three determinations instructions** · 6 h, range 4–8 · 0.8%
  * Add `vmclear` (R-15-069d), `creclaim` (R-15-007s), and `cbo.scrub` (R-15-177a) per [the hardware-acceleration determinations](todos/hardware_acceleration_determinations.md): one Sail clause each, fixed-latency, on the constant-time list.
  * `vmclear` clears vector RF, vector CSRs, matrix state, and scratchpad per class; `creclaim` composes the load's revoked case with the `cloadtags` group read; `cbo.scrub` is architecturally a fixed-latency block pass with telemetry and fail-stop hooks.
  * Depends on M0.6g's revocation bitmap and CBO plumbing; lands after it.

### Remaining M0 deliverables

* [ ] **M0.7 · Model Ztso and static-only prediction** · 3 h, range 2–4 · 0.4% · Parallel
* [ ] **M0.8 · Parameterize by core class** · 28 h, range 20–36 · 3.6%
  * Freeze C-class first; defer roughly 26 h of V/M/FEC work until needed before M2.3.
* [ ] **M0.9 · Add documented timing annotations** · 4.5 h, range 3–6 · 0.6% · Parallel
* [ ] **M0.10 · Generate and freeze the C-class golden emulator** · 2 h, range 1–3 · 0.3%
  * Exit: curated single-core emulator with ISA tests green.
* [ ] **M0.11 · Define the profile-freeze measurement contract** · 6 h, range 4–8 · 0.8% · Parallel
  * Include corpus manifest, generation inputs, composition recipe, admitted regions, thresholds, emitter provenance, and report format.
* [ ] **M0.12 · Version the differential corpus and capability trace schema** · 4.5 h, range 3–6 · 0.6% · Parallel draft
  * Reuse preserved RVFI plumbing and finalize after M0.6e–g.

**M0 subtotal:** 119 h · 15%; approximately 5 h complete.

## M1 · Toolchain spine

* [ ] **M1.1 · Locate and pin SECOMP2CHERI** · 2 h, range 1–3 · 0.3% · Parallel now
  * Record availability, provenance, condition, and carried features.
* [ ] **M1.2 · Re-home the backend to the purecap profile** · 37.5 h, range 25–50 · 4.8%
  * Functional and differential testing required; add 20–40 h if the artifact is unusable.
* [ ] **M1.3 · Add baseline target support and bound-directed lowering** · 12 h, range 8–16 · 1.5%
* [ ] **M1.4 · Re-home LLVM MC/`lld` and compose static images** · 22.5 h, range 15–30 · 2.9%
  * Exclude general dynamic linking.
* [ ] **M1.5 · Run the CertiCoq-to-Wasm oracle** · 3.5 h, range 2–5 · 0.5% · Parallel
* [ ] **M1.6 · Stand up GC-free lowering routes** · 18.5 h, range 12–25 · 2.4% · Parallel with M1.4
* [ ] **M1.7 · Boot purecap Gallina hello-world on the M0 emulator** · 9 h, range 6–12 · 1.2%
* [ ] **M1.8 · Build and wire the profile-freeze analyzer** · 11.5 h, range 8–15 · 1.5% · Parallel

**M1 subtotal:** 116.5 h · 15%.

## M2 · Fast emulator

Gate M2.2–M2.3 on measured Sail-emulator performance. If Sail is sufficient through M6, defer approximately 35 h beyond M8.

* [ ] **M2.1 · Fork CHERI-QEMU and narrow compressed capabilities** · 7.5 h, range 5–10 · 1.0% · Parallel
* [ ] **M2.2 · Implement the frozen decode surface and bespoke machine** · 12 h, range 8–16 · 1.5%
* [ ] **M2.3 · Add VLEN=4096 RVV, matrix, and FEC datapaths** · 30 h, range 20–40 · 3.9%
* [ ] **M2.4 · Reach corpus lockstep with M0 and boot M1 hello-world** · 9 h, range 6–12 · 1.2%

**M2 subtotal:** 58.5 h · 8%.

## M3 · Boot chain

* [ ] **M3.1 · Add RoT configuration and peripherals to the curated Sail tree** · 18 h, range 12–24 · 2.3%
  * Reuse the same model tree with a scalar `verifiedos-rot.json`; do not fork another model.
* [ ] **M3.2 · Implement RoT firmware in Gallina** · 22.5 h, range 15–30 · 2.9%
* [ ] **M3.3 · Implement M-mode firmware in Gallina** · 18 h, range 12–24 · 2.3%
* [ ] **M3.4 · Integrate verified cryptographic artifacts** · 26.5 h, range 18–35 · 3.4%
  * Prefer pinned upstream verified implementations over fresh authoring.
* [ ] **M3.5 · Reach the machine-mode kernel through measured boot on both emulators** · 11.5 h, range 8–15 · 1.5%

**M3 subtotal:** 96.5 h · 12%.

## M4 · Kernel

* [ ] **M4.1 · Decide revocation sweep quanta** · 1.5 h, range 1–2 · 0.2% · Parallel
* [ ] **M4.2 · Translate surviving seL4 executable-spec objects to Gallina** · 22.5 h, range 15–30 · 2.9%
  * Time-box `hs-to-coq` recovery to eight hours, then hand-translate if necessary.
* [ ] **M4.3 · Exercise capability lifecycle, IPC, and slot faults through Wasm** · 9 h, range 6–12 · 1.2%
* [ ] **M4.4 · Bring up one isolated C instance per emulated core** · 26.5 h, range 18–35 · 3.4%

**M4 subtotal:** 59.5 h · 8%.

## M5 · Storage and objects

* [ ] **M5.1 · Implement the L0 journal and L1 CoW B-tree in Gallina** · 21.5 h, range 15–28 · 2.8%
* [ ] **M5.2 · Compose L2 semantics and L3 confidentiality host-side** · 14 h, range 10–18 · 1.8%
* [ ] **M5.3 · Run system-integrity and user-data instances on the emulator** · 12 h, range 8–16 · 1.5%
* [ ] **M5.4 · Implement the object store and update transactor** · 18 h, range 12–24 · 2.3% · Parallel where possible

**M5 subtotal:** 65.5 h · 8%.

## M6 · Userland spine

* [ ] **M6.1 · Build the init supervision tree in Lustre via Vélus** · 15 h, range 10–20 · 1.9%
* [ ] **M6.2 · Refine admission checkers to CompCert-C** · 26.5 h, range 18–35 · 3.4%
* [ ] **M6.3 · Build the package composer and contained object router** · 15 h, range 10–20 · 1.9%

**M6 subtotal:** 56.5 h · 7%.

## M7 · Full emulated system

* [ ] **M7.1 · Boot the composed stack on the fast emulator and rerun it under Sail in CI** · 22.5 h, range 15–30 · 2.9%
* [ ] **M7.2 · Measure allocation churn across the composed roster** · 4.5 h, range 3–6 · 0.6%

**M7 subtotal:** 27 h · 3%.

## RTL track

* [ ] **R1 · Curate scalar CVA6-CHERI RTL and required platform devices** · 45 h, range 30–60 · 5.8%
  * Re-parameterize the dialect, enforce the absence contract, and include RoT, tag-carrying interconnect, ROM, UART, and block device.
* [ ] **R2 · Reach corpus-green Verilator co-simulation with trace diff and BMC smoke** · 22.5 h, range 15–30 · 2.9%
* [ ] **R3 · Boot the image in co-simulation and publish the versioned RTL artifact** · 15 h, range 10–20 · 1.9%

**RTL subtotal:** 82.5 h · 11%.

## M8–M10 and later

* [ ] **M8 · MVP gate: M7 and R3 complete** · 3 h, range 2–4 · 0.4%
* [ ] **M9 · Synthesize and boot scalar purecap on FPGA** · 30 h, range 20–40 · 3.9%
* [ ] **M10 · Extend CHERI checks across V/M/FEC datapaths** · 45 h, range 30–60 · 5.8%
* [ ] **Post-M10 · Publish opening hardening obligations** · 8 h, range 6–10 · 1.0%
  * State the RTL-to-Sail fallback, reduction-theorem verification plan, masking obligations, and first-silicon characterization plan.

**M8–M10 subtotal:** 86 h · 11%.

## Build-loop instruments

These items are outside milestone estimates except where explicitly included. Every change must be benchmarked before adoption; canonical `-O2` RelWithDebInfo remains the exit criterion.

* [x] **Initial check/emit/FAST tooling** · 0.9 h actual · 0.1%
* [ ] **I1 · Move sources to WSL ext4 and uncap local parallelism**
  * Move the checkout to `~/src/VerifiedOS`, use Remote-WSL, set `ctest -j$(nproc)`, and avoid cache-hostile WSL memory reclamation.
* [ ] **I2 · Use one shared content-keyed SMT memo cache**
* [ ] **I3 · Benchmark a current z3 binary on a cold emission**
* [ ] **I4 · Add shared ccache, then emit only when generated output changes**
* [ ] **I5 · Benchmark generated-TU flags, clang versus gcc, and mold**
* [ ] **I6 · Benchmark the same Sail 0.20.2 binary built with flambda**
* [ ] **I7 · Run canonical builds in the background and standardize worktree lanes**
* [ ] **I8 · Optionally move quick checks to push CI and canonical tests to nightly CI**

**Instrument subtotal:** 15.4 h · 2%, including 0.9 h complete; open range 8–21 h.

## Estimate and schedule basis

* Completed estimates are actual elapsed session intervals with overlapping build waits apportioned approximately.
* Open work classes:
  * A · pinning, configuration, and mechanical curation
  * B · semantic porting and tool re-homing with differential tests
  * C · fresh systems authoring with functional tests
  * D · RTL and FPGA work
* Confidence ranges: M0.6 approximately ±50%; M1–M3 approximately 2×; later work approximately 2.5×.
* Grand total: 782.9 h midpoint, approximately 439–1,113 h.
* Planned optimizations remove roughly 32 h from the midpoint; measured gating may move another approximately 35 h beyond M8.
* At 10–20 attended hours per week across two or three lanes, M8 is approximately 5–10 months away. Review capacity, not lane count, is the constraint beyond three lanes.
