# Implementation Checklist

> Execution tracker for [implementation-plan.md](implementation-plan.md).
> Non-normative twice over: the plan stays the authority on *what and why*, and this file records only *what is done, in flight, and next*, with the evidence for every checked box written beside it.
> Tasks here are split and reprioritized as implementation teaches, that is this file's job; a split never changes a milestone's meaning, and any finding that would belongs in the plan or the register, not here.
> Later milestones are deliberately coarse, one box per deliverable; each is split into tasks like M0's on entry, not before, so the decomposition reflects what bring-up has actually taught by the time it is needed.
> Milestones M0 to M7 are the software track and R1 to R3 the RTL track, meeting at M8 (plan §12).

## M0, Hardware reference

- [x] **M0.1, Pin the upstream start-froms.**
  Done: `upstream/sail-riscv` pinned at `8f91355e` (the model's current home `riscv/sail-riscv`, formerly rems-project, 2026-08-14) and `upstream/sail-cheri-riscv` pinned at `bb07488d` (CTSRD-CHERI, 2025-07-10), both as git submodules; the checker's sweep excludes submodule paths, upstream prose answering to its own repository.
  Finding, booked as M0.5: the CHERI model embeds its *own* `sail-riscv` submodule pinned to an older rems-project baseline, so the plan's join of the two models starts from two different bases to reconcile, not one tree to configure.
- [x] **M0.2, Stand up the Sail toolchain.**
  Done: the build environment is WSL (Ubuntu 24.04; the Windows host carries no OCaml toolchain): opam 2.1.5, switch `default` on the system OCaml 4.14.1, `opam install sail` landing Sail 0.20.2 with z3 4.8.12 beside it. 0.20.2 is exactly the floor the pinned model's `cmake/sail_required_version.txt` demands, the requirement tracking Sail's newest release, and it is the pinned compiler version the generated emulator's fidelity is claimed against, recorded here beside the M0.1 model pins.
- [x] **M0.3, Baseline build, stock sail-riscv.**
  Done: the pinned model built unmodified with the M0.2 toolchain into `sail_riscv_sim` (out-of-tree on the WSL filesystem, the submodule working tree untouched) and its bundled suite runs 664 of 664 green under `ctest`: the 2026-06-10 `sail-riscv-tests` ELFs across rv32 and rv64, the first-party tests, the SMT property checks discharged by z3, and the unit tests; this artifact is the baseline every curation diff is measured from. One environment finding, standing for every later regeneration of the model: Sail 0.20.2's C++ emission overflows the default 8MB OCaml stack on the full model, twice reproduced, and raising the limit (`ulimit -s 131072`) before the build is the fix, baked into the build script.
- [x] **M0.4, Baseline build, stock sail-cheri-riscv.**
  Done: `cheri_riscv_sim_RV64` built from `bb07488d` against the embedded `sail-riscv` at `b748a82` (a 0.5-era baseline, `0.5-211-gb748a823`, fetched from the pre-move `rems-project/sail-riscv`), and all 229 bundled rv64 `riscv-tests` ELFs pass under the repository's own protocol (the `run_tests.sh` C-emulator half: `-p`, 5s timeout, `SUCCESS` grep); the OCaml-emulator half was not exercised. CHERI-executing by construction, no CHERI test binaries being bundled upstream, the capability-level corpus being M0.12's deliverable. Two findings: Sail 0.20.2 compiles this model unmodified, so the one toolchain switch serves both baselines, the repository's CI having installed whatever sail opam then carried rather than pinning; and the Makefile builds in-tree, so the baseline was built from a copy on the WSL filesystem, the pinned submodule working tree untouched and the Windows checkout's CRLF normalized in the copy.
- [x] **M0.5, Reconcile the two baselines.**
  Done, both halves settled. The join's base is the current `sail-riscv` at `8f91355e`, and the CHERI model contributes the capability layer as a transplant rather than a base: the trees are too far apart for a patch-level rebase (the 0.5-era flat file list became the extensions tree with a project file, a JSON config system, and the C++ backend), so the join is semantic, the capability files carried into the new structure. The grounds: the profile's adopted surface exists only on the current base (ratified RVV for the V-class, `Zicond`, `Zicboz`, `Zabha`, the `Zvk*` vector-crypto rows; AIA, first listed here too, turns out to exist on *neither* base, the current tree carrying only a TODO comment for it, so it is fresh surface either way and moves to M0.6g without touching the decision), and the plan's own start-from note, `Zabha` "already present in sail-riscv", is true of `8f91355e` and false of the 2022 embedded base, so curation stays the subtractive act plan §1 designs rather than a backporting program; the M0.10 golden emulator, the M0.12 trace schema, and the prover generation ride the current base's toolchain; and the transplant is smaller than the raw CHERI diff because the profile deletes the invasive share outright (no MMU so `cheri_pte`/`cheri_ptw` never port, no hybrid mode, no `DDC`, no S-mode bank), leaving the capability algebra, the merged register file, the machine-mode trap plumbing, the load/store checks, and tag memory. The capability lineage rides R-15-007's own text: the format is a re-parameterization of `sail-cheri-riscv` with R-17-048a retiring the RVY re-pin, so the CTSRD model is the base, and a standard-lineage Sail model would import the named divergences the register refuses (SDP, CT-field sealing, `YBLD`, the Custom-3 opcode relocation, `misa.Y`). The M0.4 composite stands as the running capability-semantics oracle the transplant is differentially checked against.
- [ ] **M0.6, Curate to the frozen profile.**
  Make the joined model agree with [isa-profile.md](isa-profile.md): base and ABI mode, adopted extensions in, excluded extensions out, CHERI feature set, CSR bank. Overwhelmingly subtractive (plan §1); split on entry into the tasks below, the row groups being the profile's own sections, ordered subtractive-first so every diff lands on a green build and the M0.5 transplant lands on an already-narrowed base. One entry finding shapes the split: the current base's JSON config system expresses a large share of the §2/§6 rows as per-extension `supported` booleans (plus `physaddr_bits`, PMP entry count, S/U toggles, misaligned-trap behavior, read-only `misa`), but a config-disabled extension is dead Sail surface still in the build, and curation's point is surface that never has to be modeled again, so configuration is the *measurement pass* that produces the source-deletion worklist, not the curation itself.
  - [ ] **M0.6a, Stand up the curated tree.**
    `model/`, vendored verbatim from the pinned `sail-riscv` at `8f91355e` via git blobs (LF bytes, `-text` in `.gitattributes`, so the WSL build reads it directly), provenance recorded here; the checker's markdown sweep extended to exclude it on the submodule rationale, vendored upstream prose answering to its own repository; a WSL out-of-tree build script under `tools/` carrying the `ulimit -s 131072` fix. Exit: build and ctest parity with the M0.3 baseline, after which every curation diff is a tracked commit against a green tree.
  - [ ] **M0.6b, Configuration-level curation, the measurement pass.**
    A profile configuration expressing every row the config system carries: xlen 64, `physaddr_bits` 36, PMP count 0, S and U off, the `Zc*` family off, F and D off, `Zaamo` on with `Zalrsc`/`Zacas`/`Zawrs` off, the §2 adopted rows on, the §6 config-expressible exclusions off, V on at the C-class VLEN first (per-class parameterization stays M0.8), misaligned accesses trapping, `writable_misa` false, vendor/arch/imp ids zero. Deliverable: the sim runs the profile-subset tests green under this configuration, and the recorded residue of rows configuration cannot express (`mie`/`mip` field narrowing, unallocated-CSR trap totality, `vstart` deletion, AIA scope, counter deletion, Ztso) becomes c's and d's worklist.
  - [ ] **M0.6c, Source-level subtraction, §6 exclusions and §1 base rows.**
    Delete the excluded Sail surface outright: extension directories out of the project file with their decode clauses and config hooks, the S/U privilege machinery, translation (`satp`, `Sv*`, the PTW), PMP, the counter bank, the `vstart` term in every vector definition. Split further per row group as it proceeds; build and profile-subset tests green at every step.
  - [ ] **M0.6d, CSR bank to the closed table, §5.**
    Present rows narrowed as specified (`mie`/`mip` to the machine-timer bits, ids hardwired zero, `misa` read-only), absent rows deleted by name, an unallocated CSR address trapping as an unallocated encoding does (R-15-014).
  - [ ] **M0.6e, The CHERI transplant, §4 adopted rows from `bb07488d`.**
    Carry the capability layer into the curated tree as its own extensions-tree entry: capability type and CHERI Concentrate functions, the merged register file, tag memory, PCC and the sentry types with `cjalr`, the `MTCC`/`MEPCC`/`MTDC` trap plumbing, the load/store checks, ISAv9 cause codes into `mcause`/`mtval`; differentially checked against the M0.4 composite, the running capability-semantics oracle M0.5 names.
  - [ ] **M0.6f, Re-parameterize the format to 64+1 and take the §4 exclusions.**
    Field widths per §4.1 (address 36, otype 4, permissions 5, exponent 5, mantissas 8 and 6, tag outside), the permission field a total decode over 32 enumerated codepoints, all-zeroes decoding to untagged NULL; no `DDC`, no hybrid mode, no SDP bits, no reconstruction ops (`CBuildCap` family), no `CRAM`/`CRRL`/`CSetBoundsExact`, no `CTestSubset`, no `CClearTags`, no colour field. The representation-correctness obligation (R-15-007a) is booked for the proof track, not discharged here.
  - [ ] **M0.6g, Profile rows with no upstream form.**
    The §4 adopted rows needing fresh Sail (`cmovz`/`cmovn`, `cloadtags`, the revocation load filter and its sidecar bitmap), §3's unconditionally admitted scalar customs (`fence.t` as specified surface, the capability indexed load/store, `cclear`), and the AIA machine-level pending array at its §2 scope, a memory-mapped device beside the CLINT rather than CSR machinery, which exists on neither upstream base (the entry finding under M0.5). The measurement-conditioned rows (`bfext`/`bfins`, the multi-save, the `csetbounds` immediate, the realized dictionary) stay at their declining provisional values per profile §11 and are not modeled here.
- [ ] **M0.7, Ztso and static-only prediction as model properties** (plan §1); the store-buffer deletion stays the open DSE question [architectural-alternatives.md](architectural-alternatives.md) books, not closed here.
- [ ] **M0.8, Parameterize by core class.**
  V-class RVV (VLEN=4096), the M-class fork-and-frozen matrix extension, and the FEC and optional Keccak units as capability-checked, core-issued operations; C-class scalar first per the staging rule (plan §10), split per class on entry.
- [ ] **M0.9, Timing annotations as a documented layer**, checked by measurement in bring-up (plan §1).
- [ ] **M0.10, Generate and freeze the golden emulator.**
  The curated single-core RV64IMV+CHERI emulator, ISA tests green: the executable ISA reference everything downstream runs against.
- [ ] **M0.11, Profile-freeze measurement contract** (plan §0): corpus manifest, generated-source inputs, composition recipe, admitted region classes, per-choice acceptance thresholds, emitter-provenance schema, and the one report format.
- [ ] **M0.12, Differential corpus and commit-trace schema.**
  Version the shared test corpus and the capability-widened RVFI-style commit-trace schema every later executor emits (plan §10).

## M1, Toolchain spine

- [ ] **M1.1, Locate and pin the SECOMP2CHERI artifact** (the CompCert-through-CHERI backend the prerequisite re-homes, plan §0); its availability and state are unverified, so the first subtask is obtaining it and recording what it actually carries.
- [ ] **M1.2, Re-home the backend to the §15 purecap profile**, functional and differential-tested against the M0 emulator; the correctness proof stays deferred hardening.
- [ ] **M1.3, Baseline target support and the bound-directed lowering rule** in the same deliverable (R-18-014a, R-18-014c), the rule running against the emulator-measured table until the WCET pass lands.
- [ ] **M1.4, Frozen-dialect assembler, linker, and image composer**: LLVM MC and `lld` re-homed to the profile, reproducible composition (plan §0).
- [ ] **M1.5, Host-side CertiCoq → Wasm oracle** running a trivial Gallina program on a stock engine.
- [ ] **M1.6, GC-free on-device lowering routes stood up**: the CompCert-C path, and the MetaCoq → Rust arena path onto the Rust → CHERI compiler.
- [ ] **M1.7, Purecap hello-world from Gallina boots on the M0 emulator**, the milestone's exit test.
- [ ] **M1.8, Profile-freeze instrument built and wired** (plan §0): the analyzer under `tools/`, the backend's operand-class and region-class sidecars, and the ordered report against the generated corpus.

## M2, Fast emulator (gates on M0, parallel to M1)

- [ ] **M2.1, Fork CHERI-QEMU and narrow `cheri-compressed-cap`** to the frozen 64+1-bit fields.
- [ ] **M2.2, Frozen decode surface and machine type**: custom instructions in, excluded extensions out, MMU path deleted, one bespoke machine modeling exactly the harness device list, no virtio, no PCI.
- [ ] **M2.3, VLEN=4096 RVV datapath and matrix/FEC units** with per-element capability checks.
- [ ] **M2.4, Corpus lockstep green against the M0 emulator**, and M1's purecap hello-world boots: the exit test, after which this fork is the daily driver.

## M3, Boot chain

- [ ] **M3.1, RoT Sail core and peripherals** (scalar RV64+CHERI profile, OTP, TRNG-as-PRNG, counters, watchdog, plan §2).
- [ ] **M3.2, RoT firmware in Gallina**: measured boot, seal/unseal, attestation quote, anti-rollback.
- [ ] **M3.3, M-mode firmware in Gallina** (plan §3): initial capability distribution and boot handoff, written fresh against the OpenSBI checklist.
- [ ] **M3.4, Crypto module in Gallina** (plan §4): hash, AEAD, ML-KEM, ML-DSA, DRBG, known-answer tests green via Wasm.
- [ ] **M3.5, Both emulators reach the Machine-mode kernel** through the measured-boot chain.

## M4, Kernel

- [ ] **M4.1, Take or drop the revocation-sweep-quanta call** before authoring begins (plan §5, the [inspirations.md](inspirations.md) proposal against R-08-007's incremental form).
- [ ] **M4.2, Translate the seL4 executable spec's surviving object types to Gallina via `hs-to-coq`**, revocation authored fresh against the CHERI epoch/grant-table/load-filter model.
- [ ] **M4.3, Exercise host-side via Wasm**: capability lifecycle, IPC round-trips, slot-overrun faults.
- [ ] **M4.4, C bring-up from CHERI-seL4/Microkit through CHERI-CompCert**, one instance per emulated core, strictly disjoint state.

## M5, Storage and objects

- [ ] **M5.1, L0 journal and L1 CoW B-tree index in Gallina** (plan §7).
- [ ] **M5.2, L2 semantics and L3 confidentiality composed**, exercised host-side against an in-memory disk.
- [ ] **M5.3, System-integrity instance on-emulator against the modeled block device**, then the user-data instance on the same codebase.
- [ ] **M5.4, Object store and update transactor** (plan §6): content addressing, read-verify, A/B commit, anti-rollback floor.

## M6, Userland spine

- [ ] **M6.1, Init supervision tree in Lustre via Vélus**, with the Gallina reference model as Wasm oracle (plan §8).
- [ ] **M6.2, Admission checkers refined to CompCert-C** (plan §9): the CIC kernel against MetaCoq, the CHERI-TAL type-checker against its metatheorem, derivations thin until the proofs exist.
- [ ] **M6.3, Package composer and contained object router** exercising the plan's M6 surface.

## M7, Full system, emulated

- [ ] **M7.1, The composed stack boots in the §9 order on the fast emulator**, the plan's intermediate goal, with the Sail emulator re-running the boot in CI.
- [ ] **M7.2, Allocation-churn measurement** over the composed roster, booked here by the plan.

## R-track, RTL (parallel from the M0 freeze)

- [ ] **R1, Scalar RTL curation**: CVA6-CHERI re-parameterized to the 64+1-bit dialect per profile and absence contract, plus RoT core, tag-carrying interconnect, boot ROM, UART, block device; absence-contract evidence recorded at first elaboration.
- [ ] **R2, Corpus green in co-simulation** under Verilator with the commit-trace diff, `rvfi` the hook, and the riscv-formal-style BMC smoke (R-15-094).
- [ ] **R3, Image boot in co-simulation**; the RTL artifact of record versioned and published.

## M8 to M10, and after

- [ ] **M8, the MVP gate**: M7 and R3 together.
- [ ] **M9, FPGA scalar, purecap**: the R3 artifact synthesized and booting the golden-model images, differentially tested against M7.
- [ ] **M10, CHERI V/M/FEC datapath** extended to capability checks across all classes.
- [ ] **Post-M10 opening obligations, stated before the hardening program runs**: the RTL ⊑ Sail fallback position for the hedge deletions (R-17-037, R-17-039); the R-17-058d reduction-theorem verification plan beside the masking obligations; and the R-15-053a bring-up characterization rehearsed on FPGA, executed at first silicon.
