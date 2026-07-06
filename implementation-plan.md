# Golden-Model Implementation Plan — Two Languages, One Machine

> Companion to [verification-maximal-os.md](verification-maximal-os.md). This is the **bring-up realization** of §18: how to stand the whole verified stack up as a *fast, executable golden model* generated **directly from the two verification languages**, before any of the optimized/production workstreams exist. It is non-normative; §N references point at the specification. Where the spec describes the *hardened* artifact (CompCert-CHERI *robust preservation*, Jasmin/CT, RTL ⊑ Sail, WCET certificates), this document describes the *reference* artifact that comes first and that everything else is later checked against.

## 0. The discipline: two languages, two golden models

The entire base system is written in exactly two languages, and each yields an executable reference by extraction/generation rather than by hand-porting:

- **Hardware — Sail.** One Sail model of the machine (ISA + datapath + modeled devices), parameterized by core class (§15). Its **C backend generates the golden-model emulator** — the executable ISA reference. The *same* Sail source later feeds the RTL tools (Kami/Kôika, PipelineGen) and the proof tools (Sail → Coq, Isla); none of that is on the bring-up path.
- **Software — Rocq/Coq (Gallina).** Every TCB and base-system component is written in Gallina and lowered by **CertiCoq**. Two extraction targets, both *directly from Coq*:
  - **CertiCoq → Wasm** — the fast **host-side** functional reference. Run each component on a stock Wasm engine (wasmtime/Wasmtime-class) to iterate on OS *logic* at native-ish speed before the ISA emulator is fast enough or complete. This is the "is CertiCoq-to-Wasm fast enough?" bet; if a component is too slow or the backend too immature, fall back to CertiCoq → Clight → native or standard `Extraction` to OCaml for that component only.
  - **CertiCoq → Clight → CHERI-CompCert → RV64GV+CHERI (purecap) image** — the **full-system** reference: real *purecap* machine code that boots on the Sail emulator. The one piece of new compiler work this needs — a *functional* CHERI-RISC-V backend for CompCert, plus a purecap-clean CertiCoq runtime — is built **first, as priority zero** (below), so the software golden model is purecap from the start with no stop-gap. Only the backend's *secure-compilation criterion* (robust preservation, §5) is deferred, not the backend itself. The source language stays Coq; the CHERI backend is plumbing.

**The two golden models are validated independently first, then composed.** The Sail-C emulator is exercised by assembly/ISA tests; the Gallina components are exercised as Wasm host-side; then the components are extracted to purecap RV64+CHERI and run *on* the emulator for the composed, full-system golden model.

### The one prerequisite (built first): a functional CHERI-CompCert backend

Because the platform is **purecap-only** (§15) and this plan is **purecap end to end**, the single enabling piece of new compiler work is front-loaded *before* Emulation (§10) and FPGA (§11): a **functionally-correct CHERI-RISC-V backend for CompCert** (memory model widened to capabilities + provenance), sitting under CertiCoq, plus a **purecap-clean CertiCoq runtime/GC**. This is engineering, not a new axiom — the *working* backend, **differential-tested against the Sail golden model**, not yet its own Coq correctness proof and *not* the §5 secure-compilation (robust-preservation) theorem, both of which are hardening (below). The spec already lists this backend as a hard prerequisite — *"nothing boots without it"* (§6) — so front-loading it — **priority zero, ahead of any Emulation (§10) or FPGA (§11) work** — is the spec-consistent choice. Once it exists every component below compiles straight to purecap RV64GV+CHERI, and the *same* binaries run on the emulator (§10) and the FPGA (§11).

### Explicit scope cut (what this plan deliberately does **not** build yet)

Per the mandate to produce a fast golden model rather than the optimized variants, the following §5/§6/§18 workstreams are **out of scope for bring-up** and are named here only so their absence is honest:

- the CHERI-CompCert **secure-compilation criterion** (robust preservation, §5) — the *functional* backend is the prerequisite above and **is** built; only its heavier robust-preservation *theorem* is deferred, so golden-model software is purecap but not yet proven to preserve compartment isolation against an adversarial linked context;
- the **Jasmin** CHERI backend and binary-level **constant-time** verification (§5) — crypto is a Gallina *functional* reference only, no CT guarantee yet;
- the **certifying Rust → RV64+CHERI** toolchain and the Tier-2 memory-safety certificate (§5, §13) — no contained-Rust userspace in the golden model; base components that the spec assigns to safe Rust are written in Gallina for the reference (see §Init, §Object system);
- **RTL ⊑ Sail** refinement (Kami/Kôika) and **VST** proofs — the golden model is *correct by extraction/generation*, not by refinement proof; differential testing against Sail stands in until refinement is built;
- the **Coq-verified WCET estimator** and **Prosa** schedulability (§5, §11) — timing is measured on the emulator, not certified.

None of these is discarded; each is the *hardening* layer that later replaces a golden-model component in place. The golden model is the oracle they are all checked against.

---

## 1. The processor — the fusion SoC (Sail)

The "fusion processor with an on-die iGPU" is, in this architecture, a single die on which the GPU/accelerator role is **dissolved into ISA-visible cores in one Sail model** (§15): there is no fixed-function GPU. The "iGPU" is the **V-class** long-vector cores (software rasterization, compositing, codecs, ISP) and the **M-class** matrix cores (GEMM/AI); both share the scalar front end and differ only in U-mode datapath (VLEN, matrix geometry). One model, parameterized by class.

- **Language** — Sail.
- **Toolchain** — the Sail compiler's **C emulator backend** (`sail -c`) for the golden model; the OCaml backend for a quick interpreter; Sail → Coq and **Isla** (symbolic Sail) reserved for the proof/obligation side (deferred).
- **Start from** — `rems-project/sail-riscv` (the official RISC-V golden model) merged with `CTSRD-CHERI/sail-cheri-riscv` (the CHERI-RISC-V capability model). These already give a booting RV64 + CHERI ISA emulator; the work is *curation and extension*, not greenfield.
- **Compiler target** — Sail-C emits portable C; compile with host `clang`/`gcc` to a native `x86-64`/`arm64` emulator binary. The *emulated* ISA is **RV64GV + CHERI, purecap**, curated to the §15 profile.
- **Plan** —
  1. **Curate to the §15 profile.** Remove the C/compressed extension (unique 4-byte decode); narrow `A` to `Zaamo` + `Zacas`, delete `Zalrsc` (reservation state); adopt the crypto/bit extensions (`Zkne/Zknd/Zknh`, `Zbkb/Zbkc/Zbkx`, `Zvkned/Zvknhb/Zvkg/Zvbb/Zvbc`, `Zicond`, `Zba/Zbb/Zbs`, `Zicboz/Zicbom`), `Smstateen`, `Sstc`, `Svade`; make `misa` read-only; trap all reserved/custom encodings.
  2. **Adopt Ztso and static-only prediction as model properties** (§15): the memory model is RVTSO; there is no dynamic predictor state to model at all (deleting it is *less* Sail, not more).
  3. **Parameterize by core class.** Add the RVV long-vector datapath (V-class, VLEN=4096) and a **fork-and-frozen matrix extension** (M-class, systolic GEMM geometry) as ISA-visible, capability-checked operations in the *same* model; capability checks land on scalar-issued vector/matrix memory ops (per-element for gather/scatter). Model the **FEC units** (LDPC/polar) and the optional Keccak unit as fixed-geometry, core-issued, capability-operand instructions — no DMA, no firmware.
  4. **Add the timing annotations** the spec's §15 mandates name (fixed-latency DIV/FPU/AMO, mask-independent vector timing, static-fetch timing) as an annotated layer on the model, so the *same* Sail source is ready for later WCET/CT/Ztso obligations — but treat them as documentation in bring-up, checked by measurement.
  5. **Generate the emulator** and freeze it as the executable ISA reference. Every software image below runs on this.

---

## 2. Root of Trust (Sail scalar RV64+CHERI core + Coq firmware)

The RoT is an on-die OpenTitan-class block with its own scalar RV64+CHERI control core, TRNG, OTP/key store, monotonic counters, and the watchdog (§9, §15) — the platform's only management processor. Its capability format is the main die's purecap format (§1) in a minimal scalar profile (no V/M, no C), so the one Sail model and the one CHERI-CompCert backend cover it — *not* CHERIoT's distinct compressed encoding. Two advantages past that uniformity fix the choice: as the **root of the capability derivation tree** the RoT mints and measures the very RV64 capabilities the main die executes under — which a 32-bit CHERIoT core could not even represent, so the boot handoff would otherwise cross a capability-format seam — and as the sole management processor its **64-bit reach** addresses the whole multi-GiB die directly, keeping measured boot clear of the 4 GiB windowing a 32-bit RoT would need in the measured path. In the golden model it is a *second, smaller Sail core* plus a *Gallina firmware*.

- **Language** — Sail (the scalar RV64+CHERI core + its modeled peripherals) and Coq/Gallina (the RoT firmware).
- **Toolchain** — Sail-C for the core; **CertiCoq** for the firmware (→ scalar RV64+CHERI (purecap) image via Clight/CHERI-CompCert, or → Wasm for host-side testing of the measure/seal logic).
- **Start from** — `lowRISC/opentitan` and the **Ibex** core as the functional/RTL reference, with **CHERIoT-Ibex** (the Sonata core) as the existence proof for CHERI on an Ibex-class core; the control core itself is the `sail-cheri-riscv` base configured to a minimal **scalar RV64IMC+CHERI → RV64IM+CHERI** profile (no C, no V/M) in the main die's purecap capability format (not CHERIoT's separate encoding). Model OTP, TRNG (as a seeded PRNG in emulation), monotonic counters, and the windowed watchdog as Sail memory-mapped devices.
- **Compiler target** — scalar RV64+CHERI (purecap, no V/M) for the RoT firmware image, via the same CHERI-CompCert backend (§0) the main die uses; the RoT core emulator is Sail-C on the host.
- **Plan** — model the RoT as a minimal scalar RV64+CHERI Sail core with its peripherals; write the **measured-boot / seal-unseal / attestation-quote / anti-rollback-counter** logic in Gallina (functional reference; PQ signatures via the crypto core of §4 below). In the composed emulator the RoT core boots first, measures the M-mode firmware image, and releases the main die — the §9 chain realized as one emulator driving another.

---

## 3. M-mode firmware (Coq)

Minimal verified M-mode firmware, quiescent after boot, all traps delegated (§6, §7) — no SMM-analog resident handler.

- **Language** — Coq/Gallina.
- **Toolchain** — CertiCoq → Clight → CHERI-CompCert → RV64GV+CHERI (the §0 prerequisite backend).
- **Start from** — *no port.* Use **OpenSBI** only as a functional checklist of what M-mode must do (PMP setup, trap delegation, boot handoff); write the behavior fresh in Gallina. The surface is small.
- **Compiler target** — RV64GV+CHERI (M-mode), purecap.
- **Plan** — specify in Gallina: the **`Smepmp` self-lockdown** and the **static subtractive PMP backstop** (§15) — immutable-text/W^X, per-core physical-partition bounds, crown-jewel secret windows — programmed once and locked; trap delegation to S-mode; the boot handoff that launches one kernel instance per core. Extract to purecap RV64+CHERI; it is the first image the die emulator executes after the RoT releases it.

---

## 4. Verified crypto core (Coq)

Boot verification, attestation, sealing, and the AEAD used by storage (§6 item 2, §10). The spec's production form is Jasmin + SSProve/FCF; the **golden-model form is a Gallina functional reference** with no constant-time or reduction guarantee yet.

- **Language** — Coq/Gallina.
- **Toolchain** — CertiCoq → Wasm (fast test vectors) and → purecap RV64+CHERI (on the emulator).
- **Start from** — **Fiat-Crypto** (already Coq-native) for classical field arithmetic; for **ML-KEM / ML-DSA** and **SHA-2/3, AES-GCM / ChaCha20-Poly1305**, write Gallina functional specs (reference implementations), using the FIPS 203/204/205 vectors and `libcrux`/`HACL*` behavior as the oracle. No `F*`/Z3 dependency enters the golden model — these are *reference* implementations, correctness-by-testing now, reduction/CT proofs later.
- **Compiler target** — RV64GV+CHERI purecap (and Wasm host-side for KATs).
- **Plan** — assemble a Gallina crypto module exposing hash, AEAD seal/open, ML-KEM encaps/decaps, ML-DSA sign/verify, and a DRBG seeded from the RoT TRNG. Validate against known-answer tests via the Wasm build. This module is a dependency of the RoT (§2), the object system (§6), and the filesystem (§7). **Constant-time is explicitly not claimed** in the golden model; swapping in the Jasmin core is the later hardening step.

---

## 5. Kernel (Coq)

The capability microkernel — seL4's design, re-expressed in Gallina — instantiated once per core (multikernel, §7): untyped memory, endpoints + notifications, MCS scheduling contexts, CDT revocation.

- **Language** — Coq/Gallina.
- **Toolchain** — CertiCoq → Wasm (fast functional exercise of the capability/IPC state machine) and → purecap RV64+CHERI (the real per-core kernel on the emulator).
- **Start from** — seL4's **Haskell executable specification** as the design template (it is the same artifact seL4 uses to generate its Isabelle spec), hand-translated to Gallina; reuse the seL4 ABI and object model verbatim. This is the §5/§7 "seL4's design, re-proved in Coq" — but for bring-up we only need the *executable* Gallina model, not yet the proof.
- **Compiler target** — RV64GV+CHERI (S-mode), purecap — the §7 purecap kernel, enabled by the prerequisite CHERI-CompCert backend (§0); every stage is purecap.
- **Plan** —
  1. Translate the seL4 executable spec's object types, capability derivation tree, endpoint/notification IPC, and MCS scheduling into Gallina as an executable state machine.
  2. Exercise it host-side via the Wasm build (create/derive/revoke capabilities, IPC round-trips, budget exhaustion faults) — the fastest way to shake out the logic.
  3. Extract to purecap RV64+CHERI and boot **one instance per emulated core** with strictly disjoint state (the multikernel is the *sequential* kernel duplicated, §7), physical partitions enforced by the M-mode PMP backstop (§3).
  4. Defer only the *proofs*: the functional refinement and the non-interference theorem (§8), layered on later without changing the Gallina source. Purecap compilation is **not** deferred — the §0 prerequisite backend means the kernel is purecap from first boot.

---

## 6. OSTree-style object system + update transactor (Coq)

The content-addressed Merkle-DAG object store (§10, the OSTree inspiration) plus the **atomic update transactor** (§6 item 3) — the system-integrity path: runtime read-verify against the boot-attested signed root, A/B generations, monotonic anti-rollback.

- **Language** — Coq/Gallina.
- **Toolchain** — CertiCoq → Wasm (store/verify logic) and → purecap RV64+CHERI.
- **Start from** — `libostree` as the *conceptual* model only (content-addressed store, A/B deploy, rollback); write the store + transactor in Gallina. Hashing/signature checks call the §4 crypto module. This overlaps the storage L0/L1 layers (§7 filesystem) and shares their journal.
- **Compiler target** — RV64GV+CHERI purecap (and Wasm).
- **Plan** — implement in Gallina: content addressing (object = hash of bytes, Merkle-DAG links), **read-verify against the signed root** on every access, the **A/B atomic-commit transactor** (stage → verify → flip → fall back on health failure), and the **anti-rollback floor** sealed to the RoT counter (§9, §11). In the golden model the transactor's "proof-checked admission" (§11) is stubbed to a signature/hash check; the on-device *proof* checker is §9 below.

---

## 7. Filesystem (Coq)

The four-layer verified storage stack (§10): L0 journal, L1 CoW B-tree index, L2 FS semantics, L3 confidentiality — assembled as Gallina modules. The spec's production form is CompCert-C + VST/Iris with no managed runtime; the **golden-model form extracts the Gallina directly**, skipping the Goose-for-C / VST re-homing (deferred).

- **Language** — Coq/Gallina.
- **Toolchain** — CertiCoq → Wasm (fast FS-logic exercise against an in-memory disk model) and → purecap RV64+CHERI (on the emulator, against a modeled block device).
- **Start from** — the artifacts that are *already Coq*: **RefFS** (L2 concurrent linearizability + crash + liveness/MoLi) and **SFSCQ / DiskSec** (L3 data-noninterference). Re-express the **VeriBetrFS** B^ε-tree design (Dafny today) as the L1 CoW index in Gallina, and write the **Perennial/GoJournal** journal *design* (its proof is Coq, its code is Go via Goose) directly in Gallina for L0. Per-extent **AEAD** calls the §4 crypto module.
- **Compiler target** — RV64GV+CHERI purecap (and Wasm).
- **Plan** — compose L0 (journal) ⋈ L1 (parametric CoW B-tree, one index instantiated per object class) ⋈ L2 (typed keys, snapshot-version-in-key, RefFS semantics) ⋈ L3 (per-domain AEAD, noninterference) as Gallina modules; exercise host-side via Wasm against an in-memory disk; extract to purecap RV64+CHERI to run on the emulator against a modeled block device. Build the **system-integrity instance first** (it is the transactor's backing store, §6), then the **user-data (bcachefs-class) instance** on the same codebase (§10). Below-the-line availability services (replication/EC/tiering/copygc/FTL) are *not* built in the golden model — they are the safe-Rust workstream (deferred).

---

## 8. Init system — the static supervision tree (Coq)

The service manager: a static supervision tree with declarative units, no ambient authority, capability re-grant on restart (§12, §16). The spec assigns this to contained safe Rust; for the **single-language golden model it is written in Gallina** like the rest of the base.

- **Language** — Coq/Gallina.
- **Toolchain** — CertiCoq → Wasm and → purecap RV64+CHERI.
- **Start from** — *no port.* The design references are systemd's unit/supervision *shape* minus ambient authority (§12) and Erlang/OTP supervisor semantics (static tree, restart strategy, backoff); write it fresh in Gallina over the **compiled, typed, signed configuration objects** of §10 (no runtime text parsing).
- **Compiler target** — RV64GV+CHERI purecap (and Wasm).
- **Plan** — model in Gallina: the static component graph loaded from the signed config generation, ordered capability-granting bring-up, crash detection, restart-with-backoff, and capability re-grant on restart. It consumes the object system (§6) for its config generation and the kernel (§5) for capability operations. In the golden model it is the first S-mode/U-mode process the kernel starts, and it brings up the remaining (reference) components.

---

## 9. Admission checker (Coq / MetaCoq)

The foundational proof checker (§6 item 6) — order-10³ lines, the on-device axiom that validates every binary's proof against the spec/Sail-model versions. This is the one component whose *golden model is essentially its production form*.

- **Language** — Coq/Gallina (the checker is a proof-term type-checker).
- **Toolchain** — CertiCoq → purecap RV64+CHERI (on-device) and → Wasm (host-side checking during development).
- **Start from** — **MetaCoq**'s verified checker (the "MetaCoq-style self-verification target" of §6) — a Coq-implemented type-checker for Coq terms — extracted via CertiCoq.
- **Compiler target** — RV64GV+CHERI purecap (and Wasm).
- **Plan** — extract the MetaCoq checker as the admission oracle; in bring-up the packages it checks are the golden-model components themselves (proof objects are thin/stubbed until the Tier-0/1/2 proofs exist). Its role hardens *in place* as real proofs arrive — the checker does not change, only the proofs it is handed.

---

## 10. Emulating the hardware

The hardware golden model *is* the Sail-C emulator of §1; "emulating the hardware" is standing up the whole-machine emulator around it and booting the extracted software on it.

- **Single-core ISA emulator (day one).** `sail -c` on the curated model (§1) gives a fast single-core RV64GV+CHERI emulator. Drive it with hand-written and randomly-generated ISA tests; this validates the *hardware* reference independently of any software.
- **Whole-machine harness.** Wrap the Sail-generated core with a thin host-C system harness that provides: **multiple core instances** (C-class ×N, V-class, M-class, the S-class sentinel, and the RoT RV64 core of §2), **physical memory** with the modeled ECC/TME behavior as no-ops-with-latency, and the **modeled devices** — IOMMU (default-deny window checks), the register-slave transceiver stream, the scanout DMA block, and the RoT peripherals. Devices are modeled either as Sail memory-mapped regions (preferred, keeps them in the one language) or as C shims in the harness where that is faster to iterate. The **NoC/coherence islands** are modeled as a simple address-routing layer in bring-up (the TDM schedule and non-interference semantics are §15 hardening, not needed for functional emulation).
- **Composed full-system golden model.** Boot the stack in the spec's §9 order on the harness: RoT core + firmware (§2) → M-mode firmware (§3) → one kernel instance per core (§5) → init (§8) → object system/transactor (§6), filesystem (§7), crypto core (§4), checker (§9) — every image produced by **CertiCoq → CHERI-CompCert → RV64GV+CHERI (purecap)** via the §0 prerequisite backend. This is the reference machine: verified-by-extraction *purecap* software on the verified-by-generation ISA.
- **Fast software-only reference (parallel track).** For OS-logic iteration that does not need the ISA in the loop, run the *same* Gallina components as **CertiCoq → Wasm** on a host Wasm engine. This is the "is Wasm fast enough?" lever: it is the quick inner loop; the RV64-on-Sail path is the faithful outer loop. Both come from one source, so a bug found in either is fixed once.
- **Test generation and differential testing.** Use **Isla** (symbolic execution over the Sail model) to derive ISA test vectors and the concurrency/Ztso litmus set from the frozen model. Keep the emulator as the **differential-testing oracle** for everything downstream (the FPGA in §11 is checked against it).
- **Staging.** C-class scalar emulator + software rendering first; add the V-class vector datapath, then M-class matrix, then FEC, then multi-core + islands — mirroring §18, each class extending the *same* Sail model and re-generating the emulator.

---

## 11. Building an FPGA from it all

The golden model is Sail, not RTL, so an FPGA needs RTL. Per the two-language ideal, the RTL is obtained *from* the golden model — either **generated** from it (the "one language" dream extended to hardware) or **brought up from open cores and differentially tested against it** — with the formal RTL ⊑ Sail refinement deferred (§18).

- **Two routes to RTL.**
  - **(a) Generate from the golden ISA description** — feed the Sail/ISA spec into **PipelineGen** (pipeline generation from the ISA description) and/or **Sail → Kôika/Kami** (Coq hardware DSLs) to emit a microarchitecture that is correct-by-construction against the golden model. This is the path that keeps Sail the single hardware source; its RTL ⊑ Sail obligation is *discharged by generation* rather than by after-the-fact proof.
  - **(b) Bring up open cores + differential-test** — take the open RTL substrate per class and validate it against the Sail emulator (§10) as the oracle. This is the pragmatic near-term path and matches the "fast golden model, defer the proofs" mandate: no RTL ⊑ Sail *proof* is required for the FPGA milestone, only differential agreement with the golden model.
- **Open RTL substrate (route b), per class (§18).** For the **C-class scalar** front end an *existing CHERI RV64 soft core* — **CHERI-CVA6** (Bristol / lowRISC / OpenHW) or the Bluespec **CHERI-Flute / Piccolo / Toooba** (CTSRD) — *modified to static-only prediction* and a TSO store buffer per §15; **Ara** (PULP) for the V-class vector unit; **Gemmini** (Berkeley, Chisel) for the M-class matrix unit; open **LDPC/polar** cores for FEC; and for the **RoT**, **Ibex** + `lowRISC/opentitan` as the functional reference and **CHERIoT-Ibex** (Sonata) as the CHERI-on-Ibex reference — the on-die core itself a small **scalar RV64+CHERI** purecap core in the main die's capability format (§1), not CHERIoT's separate encoding. All are SystemVerilog/Chisel — synthesizable today. The **CHERI-CVA6** option specifically now has a commercial-quality, formally-verified open track: the lowRISC / Capabilities Limited **COSMIC** project (2025–28) hardens it on OpenTitan IP and proves its instruction execution conforms to its ISA spec — the application-class successor to the CHERIoT-Ibex conformance proof — directly de-risking the *"RV64 application-class CHERI exists only as soft cores"* binding constraint (§18) and handing the RTL ⊑ Sail bring-up gate a real application-class artifact (see [inspirations.md](inspirations.md)).
- **Concrete bring-up artifact — CHERI Mocha (COSMIC MVP-2, `lowRISC/mocha` v0.1.0).** That COSMIC track is already shipping a tagged, FPGA-synthesizable **secure-enclave SoC** — the CVA6-CHERI application core plus OpenTitan peripherals — that boots to a terminal prompt on a **Genesys 2 (Kintex-7)** board. It is a **Start-from** for the C-class-scalar-plus-RoT bring-up here: the application core is the C-class front end above; the bundled **entropy source, KMAC, ROM controller, and SPI host** are functional-reference RTL for the RoT and its measured-boot chain — the **KMAC** (Keccak/SHA-3) doubling as a reference for the SHAKE-heavy PQ crypto core — and the bare-metal **HAL** (`sw/device/lib/hal`) is a Start-from for the verified DMA/MMIO/descriptor HAL, to be re-homed onto Verus/Prusti/Aeneas. It stays a *reference*, not an admitted artifact — unverified RTL under the same route-(b) disposition as every core above, its **RTL ⊑ ISA conformance proof still pending** (§18) (MVP-2 is a maturity milestone, not a verification one). Two pieces are pointedly *not* imported. The **debug module** — a development-visibility backdoor into the enclave — is admissible only where §15 already puts external debug: **gated behind RoT lifecycle state**, fused-off in production, never a shipping surface. And Mocha's headline **CHERI-Linux boot** is the enclave-beside-Linux framing the design refuses (§14, *no Linux-personality shim*): the core, peripheral, and HAL RTL transfer as references; the operating system does not.
- **CHERI runs on FPGA, and purecap software is ready for it — no stop-gap.** CHERI *runs on FPGA today*: the scalar CHERI RV64 soft cores above make the **C-class FPGA purecap from the start**, and because the **functional CHERI-CompCert backend is a prerequisite** (§0), the purecap golden-model images boot on it directly — purecap from first bring-up, with no capability-degraded interim. The genuinely new RTL + Sail work (§18) is CHERI for the **V-class and M-class** — Ara and Gemmini are not capability-aware, so extending their vector/matrix memory ops to per-element capability checks is the real hardware effort, *not* the scalar core. The only *silicon* gate (§18) is fabricating a CHERI **ASIC** for a shippable product — irrelevant to emulation and FPGA.
- **Profile curation in RTL.** Enforce the §15 profile in hardware: no C extension, `Zaamo`+`Zacas` and no LR/SC reservation logic, adopted crypto/bit units, static fetch, Ztso store buffer, fixed-latency DIV/FPU/AMO. Each is *less* hardware than the stock core, not more.
- **Synthesis + bring-up staging.** Target a large FPGA (Xilinx/AMD UltraScale+ or Versal class, or an open board where capacity allows). Bring up **C-class scalar first** (boots the same M-mode firmware → kernel → init stack from §10), then **V → M → FEC → NoC → coherence islands**, class by class, each differentially tested against the Sail golden model. The **S-class sentinel** and RoT are small and come early.
- **Deferred hardening (named, not built here).** The **riscv-formal/rvfi** BMC bring-up gate, the **Isla**-generated obligations, and the closing **Kami/Kôika** RTL ⊑ Sail refinement (§15, §18) are the path from "differentially agrees with the golden model" to "proven to refine it." They are explicitly out of scope for the FPGA milestone and layered on afterward — the golden model remains the reference they target.

---

## 12. Build order and milestones

Bottom-up, each milestone runnable against the prior one:

1. **M0 — Hardware reference.** Curated Sail model (§1) → single-core RV64GV+CHERI emulator; ISA tests green.
2. **M1 — Toolchain spine, incl. the CHERI-CompCert prerequisite.** Build the *functional* CHERI-RISC-V CompCert backend (+ purecap-clean CertiCoq runtime) **first**, then bring up both paths — CertiCoq → Wasm (host-side) and CertiCoq → Clight → CHERI-CompCert → RV64GV+CHERI (purecap) — producing runnable artifacts from a trivial Gallina program on the M0 emulator. Every later milestone is purecap from here.
3. **M2 — Boot chain.** RoT core + firmware (§2), M-mode firmware (§3), crypto core (§4) → the emulator reaches S-mode.
4. **M3 — Kernel.** Gallina microkernel (§5), one instance per emulated core; capability/IPC tests green host-side (Wasm) and on-emulator (RV64).
5. **M4 — Storage + objects.** Journal/index/FS (§7) and the content-addressed object store + transactor (§6); system-integrity instance first, then user-data.
6. **M5 — Userland spine.** Init/supervision tree (§8) brings up the reference components; admission checker (§9) validates the package set.
7. **M6 — Full-system golden model.** The composed emulator (§10) boots the whole stack; the Wasm track runs the same components fast for iteration.
8. **M7 — FPGA scalar (purecap).** Bring up an existing CHERI RV64 scalar soft core (§11); the purecap golden-model images (M1–M6) boot on it directly, differentially tested against M6; CHERI ISA tests from the Sail model green.
9. **M8 — CHERI V/M/FEC datapath.** Extend the V/M/FEC datapaths to capability checks (the genuine new RTL, §18) — the scalar core and purecap software are already in hand from M1/M7, so the FPGA then matches the golden model across all core classes.

Everything past M8 — the CHERI-CompCert **secure-compilation criterion** (robust preservation; the *functional* backend already landed in M1), Jasmin/CT, certifying Rust, VST, WCET, and RTL ⊑ Sail refinement — is the hardening program of §5/§6/§18, each piece replacing a golden-model component *in place* and checked against the reference this plan produces.
