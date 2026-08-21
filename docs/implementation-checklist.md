# Golden-Model Implementation Plan and Checklist: Two Languages, One Machine

> Companion to [spec.md](spec.md).
> Execution state is tracked in §12, where each milestone is split into checkable tasks as it is entered; §0–§11 stay the authority on what each milestone means and why.
> This is the **bring-up realization** of §18: how to stand the whole verified stack up as a *fast, executable golden model* generated **directly from the two verification languages**, before any of the optimized/production workstreams exist.
> It is non-normative; §N references point at the specification.
> Where the spec describes the *hardened* artifact (CompCert-CHERI *robust preservation*, on-artifact constant-time verification, RTL ⊑ Sail, WCET certificates), this document describes the *reference* artifact that comes first and that everything else is later checked against.
> Two executors run everything it builds: the Sail-generated **golden emulator**, the reference, and a **CHERI-QEMU fork** curated to the same frozen profile, the fast untrusted vehicle (§10).
> The plan's most important milestone (§12, M8) is the full stack running on the second, cross-checked against the first, with the **matching scalar RTL artifact** already in hand and corpus-green in co-simulation (§11).

## 0. The discipline: two languages, two golden models

The entire base system is written in exactly two languages, and each yields an executable reference by extraction, refinement, or generation rather than by hand-porting:

- **Hardware, Sail.**
  One Sail model of the machine (ISA + datapath + modeled devices), parameterized by core class (§15).
  Its **C backend generates the golden-model emulator**, the executable ISA reference.
  Beside it runs a second executor of the same frozen profile, the **CHERI-QEMU fork** of §10, **untrusted evidence-producing machinery** like the compilers and analyzers (main-spec §6): the whole-machine iteration vehicle and the differential rig's second implementation, never the reference, every divergence adjudicated against the Sail model.
  The *same* Sail source later feeds the RTL flow (the **net-new blocks authored in Kôika/Kami** with the imported cores given Sail-generated-SystemVerilog-plus-commercial-FEV evidence, PipelineGen as scaffolding, SystemVerilog generated for synthesis, main-spec §15) and the proof tools (Sail → Coq, Isla, and the **one Iris-over-Sail program logic** with its four theories, Islaris/Cerise/Katamaran among them, main-spec §13), whose deferred proofs are discharged with the modern Coq automation stack (SMTCoq, **Diaframe**-class Iris automation, learned tactic synthesis) as re-checked oracles (main-spec §5); none of that is on the bring-up path.
- **Software, Rocq/Coq (Gallina).**
  Every TCB and base-system component is written in Gallina from one source, then lowered two different ways for two different roles, and **the on-device lowering carries no garbage collector.**
  The main spec's storage rule, *"no managed runtime … the GC runtime is banned"* (§10), is the discipline for the *whole* base here, not just the filesystem: a tracing GC is inadmissible twice over, putting an unverified runtime in the TCB and, with its unbounded pauses, breaking the WCET real-time path (§11).
  So `CertiCoq → Clight` (which emits a GC) is used **host-side only**, never in a shipped image:
  - **Host-side functional oracle, CertiCoq → Wasm.**
    Run each component on a stock Wasm engine (wasmtime/Wasmtime-class, **standard Wasm, not CHERI-Wasm**) to iterate on OS *logic* at native-ish speed before a component is even lowered; whole-*machine* speed is the §10 fork's job, so this leg's standing value is needing no toolchain, no image, and no machine model at all.
    This leg tests logic and values, not capability *enforcement*, enforcement is validated on the purecap-on-Sail path below, so no CHERI semantics are needed here (Wasm is a system execution target nowhere in this design, §14; a research-grade CHERI-Wasm engine would only forfeit the mature host tooling that justifies this leg).
    Here a GC is harmless, it rides the host engine, is never shipped, never enters the TCB, never touches a timing bound, so this stays the quick inner loop *and* the differential-testing spec-oracle for the path below; if a component is too slow or the backend too immature, fall back to standard `Extraction` to OCaml for that component only.
  - **On-device purecap artifact, GC-free, by the component's memory behavior.**
    The real *purecap* machine code that boots on the Sail emulator is produced with no managed runtime, by whichever Coq-native GC-free route fits, each already inside the trust base, so no garbage collector and no new prover ever enters the image:
    - **Refine the Gallina spec to CompCert-C (VST/Iris), through CHERI-CompCert**, for the kernel (§5), the low-level M-mode firmware (§3), and the heap-churning storage layers (§6 object store, §7 filesystem).
      This *is* the spec's stated end-state (seL4's design via CompCert/SECOMP, §5; verified C with no managed runtime, §10) and the CertiKOS/VST method the plan already cites; for the golden model the GC-free C comes first and its full refinement *proof* is deferred (below).
    - **GC-free extraction with region/arena allocation**, for the allocation-light, arena-shaped components (the static init tree §8; **not** the admission checker §9, which is TCB whose binary nothing re-checks, so it takes the verified-compilation route above): **MetaCoq → Rust with `bumpalo` arenas** onto the certifying Rust→RV64+CHERI compiler (a priority-zero item the spec already commits to, §18), with **MCQC** (Gallina→C++, RAII, MIT-PDOS lineage, the group behind the §7 SFSCQ/DiskSec work) the standing precedent that push-button GC-free Gallina extraction exists.
    - **Fiat/Bedrock correct-by-construction synthesis to imperative Clight**, where explicit-memory code is wanted directly; already the platform's method for wire parsers (Narcissus, §5) and field arithmetic (Fiat-Crypto, §4).
    - **Vélus (Lustre → Clight)**, for the §12 server *control planes* (supervision trees, protocol state machines, mode/timing sequencing): a **Coq-verified** synchronous-dataflow compiler emitting CompCert Clight, so control-plane logic rides the same CHERI-CompCert path as the verified C, statically allocated (**no GC by construction**), with WCET, determinism, and causality structural (§5, §12).
      Like Narcissus and Fiat-Crypto it is a Coq-verified DSL, **not a third trust language**, the two languages are the trust bases (Sail + Coq), and Lustre's meaning *and* its compilation are both Coq objects.

**The two golden models are validated independently first, then composed.**
The Sail-C emulator is exercised by assembly/ISA tests; the Gallina components are exercised as Wasm host-side; then the components are lowered **GC-free** to purecap RV64+CHERI (above) and run *on* the emulated machine for the composed, full-system golden model.
Day to day that composed system runs on the **fast emulator** (the CHERI-QEMU fork, §10), with the Sail-generated emulator re-running the same boots in CI, so iteration speed and reference fidelity are two machines rather than one compromise.

**One toolchain contract, stated once for every Gallina component below.**
Unless an entry notes otherwise, each base-system component is written in **Gallina**, exercised host-side on the **CertiCoq → Wasm** oracle, lowered on-device **GC-free** by one of the four routes above, and compiled to purecap **RV64IMV+CHERI**, the *same* binary running on both emulators (§10), the RTL in co-simulation, and the FPGA (§11).
So each entry below gives only its **Toolchain** (the GC-free route, and why the component's allocation behavior fits it), its **Start-from**, and its **Plan**, showing Language or Compiler-target only where a component genuinely differs (the Sail cores of §1 and §2, the Lustre control plane of §8, the two-checker split of §9).
The Wasm oracle and the standing ban on the GC'd `CertiCoq → Clight` path are this section's rule, not repeated per component.

### The one prerequisite (built first): a functional CHERI-CompCert backend

Because the platform is **purecap-only** (§15) and this plan is **purecap end to end**, the one piece of compiler work that gates the whole stack is front-loaded *before* Emulation (§10) and FPGA (§11): a **functionally-correct CHERI-RISC-V backend for CompCert** (memory model widened to capabilities + provenance).
It is not built from scratch: **SECOMP2CHERI** (Thibault, Azevedo de Amorim et al., PriSC 2023) already carries CompCert through every pass, from CompCert C down to its formalized RISC-V assembly, onto a CHERI-RISC-V capability machine in Coq/Rocq, and the capability-and-provenance C memory model it targets is itself mechanized in Coq (Zaliva et al., a CHERI-C semantics adapting Cerberus, ASPLOS 2024), so the prerequisite is to **re-home that backend to the §15 purecap profile and complete it**, not to devise either a backend or a semantics.
This is engineering, not a new axiom: the *working* backend, **differential-tested against the Sail golden model**, comes first, while its own Coq correctness proof and the §5 secure-compilation (robust-preservation) theorem are deferred hardening (below); and because SECOMP2CHERI is itself a *secure-compilation* backend, that same artifact is the vehicle for the §5 theorem, so completing it later discharges the deferral rather than starting over.
The spec already lists this backend as a hard prerequisite, *"nothing boots without it"* (§6), so front-loading it, **priority zero, ahead of any Emulation (§10) or FPGA (§11) work**, is the spec-consistent choice.
Completing the backend includes the main spec's R-18-014a baseline target support in the same deliverable: ordinary latency-aware scheduling, RVV autovectorization and SLP, legal register-arm `Zicond` if-conversion and its capability arm on the conditional capability move, and fusion-pair emission and adjacency preservation; none is a separate optimization workstream or deferred hardening item.
The same deliverable carries **R-18-014c's bound-directed lowering** (of two architecturally equivalent lowerings that both fit the image budget, emit the one whose cost annotation yields the tighter bound, average cost being the tie-break only), which is a *choice rule inside the backend* rather than a pass to build, and which is gated on its input rather than on itself: the WCET cost-annotation pass is scope-cut for bring-up (below), so until it lands the rule runs against the emulator-measured table, exactly as sound §11 admission does (main spec R-18-025).
The deliverable is bounded below by the compiler, not by the image, so the same milestone carries the rest of the binary path: an **assembler, linker, and image composer for the frozen dialect**.
CompCert emits assembly, and no stock binutils assembles a 64+1-bit purecap dialect (isa-profile §4.1), so LLVM's MC layer and `lld` are re-homed to the profile as the untrusted assembler/linker, the slot GNU `as`/`ld` occupy under stock CompCert, and the image composer emits the position-fixed image whose composition-time-absolute call and address forms the profile's code-size decisions quantify over (R-15-036l), reproducibly, reproducible build being part of the checkers' bootstrap-root story (§9).
Verified assembly, linking, and image construction are deferred hardening exactly like the backend's own proof, they are what the §5 source-correspondence theorem later covers, and the covering instrument is now named rather than open (R-05-023a: decompilation into logic over the pinned Sail term, checked in the §13 logic); the *working* binary path ships inside M1, because nothing downstream links without it.
Once it exists every C-path component below compiles straight to purecap RV64IMV+CHERI, and the *same* binaries run on both emulators (§10), the RTL in co-simulation, and the FPGA (§11).
**No purecap CertiCoq GC is on this critical path**, because the on-device lowering is GC-free (above), CertiCoq's collector is only ever exercised host-side on the stock Wasm engine, so it never has to be ported to purecap; the discipline *removes* a priority-zero deliverable rather than adding one.
The arena-extraction route that targets Rust (MetaCoq→Rust, §8) instead rides the certifying Rust→RV64+CHERI compiler, itself already priority zero in the spec (§18).

### The profile-freeze measurement instrument

The profile's code-size choices depend on generated artifacts that do not exist before bring-up, so their common measurement instrument is built as part of this plan rather than tracked as an open import question.
It is one deliverable with two milestones:

1. **M0 defines the measurement contract with the profile.**
   Name and version the freeze corpus, its generated-source inputs, the composition recipe, the admitted region classes, and the acceptance threshold for every choice; define the emitter-provenance schema that labels operand classes before assembly; and establish one report format that records the realized dictionary, bytes, and Sail-model worst-case cycles.
   The corpus includes the composed base image; generated Narcissus UPER RRC and IEI/TLV codecs; generated MMIO accessors; and the generated prologues, epilogues, calls, and global-address materializations in that image.
   The contract is authored as the [profile-freeze measurement contract](freeze-measurement-contract.md), which is the authority on every corpus member, recipe step, provenance stratum, region class, threshold, report column, and CI predicate the two paragraphs here name; this section stays the authority on what the deliverable is and why it is split across two milestones.
2. **M1 builds and wires the instrument into the functional CHERI-CompCert backend.**
   Add an ELF/link-map/provenance analyzer under `tools/`, make the backend emit the operand-class and region-class sidecars it consumes, and take cycle deltas from §1's Sail timing table rather than host timing.
   Run the report in this fixed order: compose and merge first (R-15-036i); select and report the dictionary with hit rate stratified by operand class (R-15-036h, R-15-036k); measure outlining and tail merging as a bytes-and-worst-case-cycles pair per admitted region class (R-15-036o, R-15-036p); then measure PC-relative versus composition-time-absolute call/address forms (R-15-036l), `bfext`/`bfins` forms (R-15-067d), the one further code-size candidate the same act weighs (R-15-067e), the indexed load/store scale immediate (R-15-007g), and the emitted adjacency histogram the frozen fusion set is selected against (R-15-031a), whose admission is the §15 exploration's rather than the report's.
   The single-check multi-register save/restore is a **nil row**: it is struck ahead of the freeze (R-15-036n), so the report carries the strike and leaves its byte and cycle columns empty, and a measured row against it is an amendment rather than a freeze.
   One choice in that act is measured on cycles rather than bytes and so takes a corpus of its own: `rcstep`'s carriage is decided by the decoder's worst-case cycles per frame over the conformance streams, against the slot and the decode ceiling the media server is admitted at (R-15-067h, R-15-238c), and it is reported in the same freeze report with the byte columns left empty rather than in a second one.
   Publish the corpus manifest, tool version, thresholds, per-extension deltas, and realized choices with the profile freeze; CI rejects a freeze whose report omits a required corpus member, provenance stratum, region class, byte column, or worst-case-cycle column.

### Explicit scope cut (what this plan deliberately does **not** build yet)

Per the mandate to produce a fast golden model rather than the optimized variants, the following §5/§6/§18 workstreams are **out of scope for bring-up** and are named here only so their absence is honest:

- the CHERI-CompCert **secure-compilation criterion** (robust preservation, §5): the *functional* backend is the prerequisite above and **is** built; only its heavier robust-preservation *theorem* is deferred, with **SECOMP2CHERI** as its vehicle (secure compilation being its whole point), so golden-model software is purecap but not yet proven to preserve compartment isolation against an adversarial linked context;
- binary-level **constant-time** verification (§5), crypto is a Gallina *functional* reference only, no CT guarantee yet (the CryptOpt-style field-arithmetic translation-validation toolchain is not listed here because it is **deleted** in the spec, not deferred to a later phase: §5's rule against a net-new verified artifact bought for speed alone, so the field arithmetic is verified C on both the reference and the hardened path);
- the **certifying Rust → RV64+CHERI** toolchain's *certificate* mode and the Tier-2 memory-safety certificate (§5, §13), no contained-Rust userspace in the golden model; base components the spec assigns to safe Rust are written in Gallina for the reference (see §Init, §Object system).
  Its *functional* Rust→CHERI lowering is still used as the target of the GC-free MetaCoq→Rust arena extraction above, but that backend is a spec-committed priority-zero item (§18), not a bring-up prerequisite this plan newly invents;
- **RTL ⊑ Sail** refinement (Kami/Kôika) and the **full VST(Iris) refinement proofs** for the kernel and storage stack (§5, §6, §7), the on-device code is written GC-free in the CompCert-C shape those proofs target (the §10 no-managed-runtime form), but its machine-checked *"artifact ⊑ Gallina spec"* proof is deferred; differential testing against the Wasm oracle and the Sail emulator stands in until it is built;
- the **WCET cost-annotation pass** (syntax-directed over the typed control-flow graph, folded into the certifying toolchain, no standalone estimator, main-spec §5/§11) and the **interval-arithmetic cyclic-executive schedulability check**, timing is measured on the emulator, not certified;

None of these is discarded; each is the *hardening* layer that later replaces a golden-model component in place.
The golden model is the oracle they are all checked against.

---

## 1. The processor: the fusion SoC (Sail)

The "fusion processor with an on-die iGPU" is, in this architecture, a single die on which the GPU/accelerator role is **dissolved into ISA-visible cores in one Sail model** (§15): there is no fixed-function GPU.
The "iGPU" is the **V-class** long-vector cores (software rasterization, compositing, codecs, ISP) and the **M-class** matrix cores (GEMM/AI); both share the scalar front end and differ only in datapath (VLEN, matrix geometry).
One model, parameterized by class.

- **Language**, Sail.
- **Toolchain**, the Sail compiler's **C emulator backend** (`sail -c`) for the golden model; the OCaml backend for a quick interpreter; Sail → Coq and **Isla** (symbolic Sail) reserved for the proof/obligation side (deferred).
- **Start from**, `rems-project/sail-riscv` (the official RISC-V golden model) merged with `CTSRD-CHERI/sail-cheri-riscv` (the CHERI-RISC-V capability model).
  These already give a booting RV64 + CHERI ISA emulator; the work is *curation and extension*, not greenfield.
- **Compiler target**, Sail-C emits portable C; compile with host `clang`/`gcc` to a native `x86-64`/`arm64` emulator binary.
  The *emulated* ISA is **RV64IMV + CHERI, purecap**, curated to the §15 profile.
- **Plan:**
  1. **Curate to the §15 profile.**
    The frozen profile is the root of the schedule and is enumerated once, in the [frozen instruction-set profile](isa-profile.md): base and ABI mode, the adopted extensions, the exclusions with their grounds, the CHERI feature set, the custom and fork-and-frozen units, and the CSR bank, every row citing the requirement that admits or excludes it.
    Curation is the mechanical act of making `sail-riscv` ⋈ `sail-cheri-riscv` agree with that table; restating the table here would be a second copy of it to keep true, and the profile is precisely what §18 gates the rest of the schedule on.
    One fact belongs here rather than there, being about the start-from and not the profile: `Zabha` needs no new modeling, already present in `sail-riscv` as extension-gated byte and halfword width cases inside the `Zaamo` AMO instruction file, so it arrives as a width case of a modeled operation rather than as a new mechanism.
    The work is overwhelmingly subtractive, which is the point: every removal is Sail surface that never has to be modeled, refined, or reasoned about again.
  2. **Adopt Ztso and static-only prediction as model properties** (§15): the memory model is RVTSO; there is no dynamic predictor state to model at all (deleting it is *less* Sail, not more).
     Curation proceeds under Ztso as specified; the store-buffer deletion, *sequential consistency by absence*, remains the DSE question [architectural-alternatives.md](architectural-alternatives.md) books, evaluated in the exploration below rather than closed by this step.
  3. **Parameterize by core class.**
     Add the RVV long-vector datapath (V-class, VLEN=4096) and a **fork-and-frozen matrix extension** (M-class, systolic GEMM geometry) as ISA-visible, capability-checked operations in the *same* model; capability checks land on scalar-issued vector/matrix memory ops (per-element for gather/scatter).
     Model the **FEC units** (LDPC/polar) and the optional Keccak unit as fixed-geometry, core-issued, capability-operand instructions, no DMA, no firmware.
  4. **Add the timing annotations** the spec's §15 mandates name (fixed-latency DIV/FPU/AMO, mask-independent vector timing, static-fetch timing) as an annotated layer on the model, so the *same* Sail source is ready for later WCET/CT/Ztso obligations, but treat them as documentation in bring-up, checked by measurement.
  5. **Generate the emulator** and freeze it as the executable ISA reference.
     Every software image below runs on this.

### Choosing the frozen parameters: a proof-aware design-space exploration

The class parameters above (VLEN per class, matrix geometry) and the platform's other frozen microarchitectural knobs, core count per class, issue width and pipeline depth, the SRAM bank/macro/tier-to-island map, software-scratchpad sizes, and the TDM-NoC schedule, are not guessed (there are no hardware caches to size and no integrity-tree structure to size, main-spec §15).
They are chosen by a **design-space exploration (DSE)** run off-model, ahead of RTL and silicon, whose utility function is **multi-objective: performance, area, power, WCET, and, as a first-class term, *proof simplicity*** (main-spec §15).
One knob is not the search's to turn: the vertical tier count is bounded by R-15-163's conditional materials grading, a reading of the outside world rather than a point in the space, so the DSE ranges under whatever bound that grading returns.

- **Proof simplicity is an explicit objective, not an afterthought.**
  A smaller, more regular microarchitecture is a smaller Sail model and a cheaper **RTL ⊑ Sail** refinement (the FPGA/silicon arrow of §11; deferred, main-spec §18, the least-built layer of the stack), so the DSE that improves performance can *reduce* the verification surface at the same time.
  The term is a proxy, estimated Sail-surface size, decode/state complexity, and per-candidate refinement effort, cheap to score inside the search loop.
- **The admission test is a hard constraint, not an objective.**
  Every candidate must clear the five-part admission test and the non-interference / schedulability obligations (main-spec §15, §8, §11) to enter the Pareto front; infeasible points are pruned, so the search ranges only over the proven-safe envelope.
  Its output is one frozen configuration that the per-class RTL ⊑ Sail proof then actually discharges, the proxy costs search quality, never soundness.
- **Tooling and staging.**
  An off-the-shelf multi-objective optimizer (NSGA-II-class) or an SMT/ILP feasibility oracle wrapping the admission predicate, over a parameterized cost model, **untrusted evidence-producing machinery, like the compilers and analyzers**: its output is re-modeled in Sail and re-checked, so it joins no trust base (§0, main-spec §6).
  Deferred like the other hardening (§11): bring-up runs on hand-chosen parameters, and the DSE is layered on once the Sail cost model and per-class RTL exist.
  It is the concrete home of the *"search over the instantiation, never the specification"* discipline.
- **Three questions the exploration answers by name, so none closes by default.**
  First the store buffer: [architectural-alternatives.md](architectural-alternatives.md) books *sequential consistency by absence* as a DSE question that clears four of five deletion gates and turns on a single quantity, whether **ρ ≥ 1** (guaranteed per-hart memory-issue opportunities over that hart's static peak memory-op issue rate) is affordable on every class.
  The DSE evaluates that admission condition per class and either fires the entry's stated falsifier or returns the deletion affordable, which triggers the spec-body change list the entry enumerates; and because an affirmative answer reaches back into the frozen profile (the `fence` and memory-model rows), the evaluation starts as early as its inputs exist, the savings half being static-schedule arithmetic that needs no RTL, rather than waiting for the full search.
  Second the product decision, a precondition rather than an output: the performance objective has no floor a candidate can fail until the first release is either named a fixed-capacity secure appliance or given a measurable mobile acceptance criterion, so the parameter freeze is gated on that recorded decision; its costs are already booked (R-15-162, R-15-163, R-18-004).
  Third the masked instance, the same precondition shape: R-05-004a's accept books the fork between a first-of-kind masked realization of the vector crypto units and a secret path narrowed to a dedicated masked datapath of the parametric-order HPC lineage, no masked vector crypto extension existing anywhere to import, so the freeze records that call rather than closing it by default (critique work-list item 28); the choice moves area, the randomness-expansion rate, and which datapath the *d*-probing theorems are stated over, all DSE quantities, and every candidate is evaluated with the R-17-058d ineffective-fault countermeasure's redundancy included rather than retrofitted.

---

## 2. Root of Trust (Sail scalar RV64+CHERI core + Coq firmware)

The RoT is an on-die OpenTitan-class block with its own scalar RV64+CHERI control core, TRNG, OTP/key store, monotonic counters, and the watchdog (§9, §15), the platform's only management processor.
Its capability format is the main die's purecap format (§1) in a minimal scalar profile (no V/M, no C), so the one Sail model and the one CHERI-CompCert backend cover it, *not* CHERIoT's distinct compressed encoding.
Two advantages past that uniformity fix the choice: as the **root of the capability forest** the RoT mints and measures the very RV64 capabilities the main die executes under, which a 32-bit CHERIoT core could not even represent, so the boot handoff would otherwise cross a capability-format seam, and as the sole management processor its **64-bit reach** addresses the whole multi-GiB die directly, keeping measured boot clear of the 4 GiB windowing a 32-bit RoT would need in the measured path.
In the golden model it is a *second, smaller Sail core* plus a *Gallina firmware*.

- **Language**, Sail for the scalar RV64+CHERI control core and its peripherals (emulated by Sail-C on the host), Gallina for the firmware.
- **Toolchain**, GC-free CompCert-C through CHERI-CompCert; this small, mostly-static firmware has no heap, and it targets the **scalar** RV64+CHERI subset (no V/M) rather than the main-die RV64IMV.
- **Start from**, `lowRISC/opentitan` and the **Ibex** core as the functional/RTL reference, with **CHERIoT-Ibex** (the Sonata core) as the existence proof for CHERI on an Ibex-class core; the control core itself is the `sail-cheri-riscv` base configured to a minimal **scalar RV64IMC+CHERI → RV64IM+CHERI** profile (no C, no V/M) in the main die's purecap capability format (not CHERIoT's separate encoding).
  Model OTP, TRNG (as a seeded PRNG in emulation), monotonic counters, and the windowed watchdog as Sail memory-mapped devices.
- **Plan**, model the RoT as a minimal scalar RV64+CHERI Sail core with its peripherals; write the **measured-boot / seal-unseal / attestation-quote / anti-rollback-counter** logic in Gallina (functional reference; PQ signatures via the crypto core of §4 below).
  In the composed emulator the RoT core boots first, measures the M-mode firmware image, and releases the main die, the §9 chain realized as one emulator driving another.

---

## 3. M-mode firmware (Coq)

Minimal verified M-mode firmware, quiescent after boot (§6, §7), no trap delegation (single Machine mode; traps are taken by the Machine-mode kernel), no SMM-analog resident handler.

- **Toolchain**, GC-free **CompCert-C through CHERI-CompCert** (§0); this firmware is tiny, quiescent, low-level register programming with no heap, so it never wants a managed runtime.
- **Start from**, *no port.*
  Use **OpenSBI** only as a functional checklist of what M-mode must do (initial capability distribution, boot handoff, no PMP setup, §15); write the behavior fresh in Gallina.
  The surface is small.
- **Plan**, specify in Gallina: the **initial capability distribution**, deriving each core's partition-bounded root capability and the read-execute-only capabilities for kernel and firmware text (CHERI W^X, §14), with **no PMP or `Smepmp`** (CHERI is the sole memory-protection mechanism, §15); the boot handoff that launches one Machine-mode kernel instance per core (single privilege mode, no trap delegation).
  Lower GC-free to purecap RV64+CHERI; it is the first image the die emulator executes after the RoT releases it.

---

## 4. Verified crypto core (Coq)

Boot verification, attestation, sealing, and the AEAD used by storage (§6 item 2, §10).
The spec's production form is verified C compiled through CHERI-CompCert **end to end, the field-arithmetic kernels included** (the CryptOpt route is deleted by §5's rule, not a later phase), with constant-time verified on the artifact, the secret-handling datapath **masked** with *d*-probing and composition theorems verified on the artifact against the probing-model statement (R-05-004a, R-15-053a), and SSProve/FCF reductions (§5); the **golden-model form is a Gallina functional reference** with no constant-time, masking, or reduction guarantee yet.

- **Toolchain**, GC-free **CompCert-C through CHERI-CompCert** (or GC-free extraction), the *same* route the hardened form uses for the field arithmetic, so no crypto component changes producer between the reference and the end-state; constant-time is **not** claimed in the golden model, on-artifact CT verification of the crypto core being the deferred end-state (§5).
- **Start from**, **Fiat-Crypto** (already Coq-native) for classical field arithmetic; for **ML-KEM / ML-DSA** and **SHA-2/3, AES-GCM / ChaCha20-Poly1305**, write Gallina functional specs (reference implementations), using the FIPS 203/204/205 vectors and `libcrux`/`HACL*` behavior as the oracle.
  No `F*`/Z3 dependency enters the golden model, these are *reference* implementations, correctness-by-testing now, reduction/CT proofs later.
- **Plan**, assemble a Gallina crypto module exposing hash, AEAD seal/open, ML-KEM encaps/decaps, ML-DSA sign/verify, and a DRBG seeded from the RoT TRNG.
  Validate against known-answer tests via the Wasm build.
  This module is a dependency of the RoT (§2), the object system (§6), and the filesystem (§7).
- **Masked end-state**, deferred with the other hardening rather than a golden-model property.
  Start from the parametric-order HPC lineage (SMAesH, COMPRESS, and the OpenTitan first-order DOM AES/KMAC blocks with their stream-cipher randomness expansion) for the datapath, and run the tool ensemble (SILVER exact per gadget, PROLEAD statistical on the composed implementation, MATCHI compositional, and Coco-class execution-aware verification against the core's netlist, the R-15-053a discharge) as **untrusted evidence-producing machinery, like the compilers and analyzers**; the datapath additionally carries the R-17-058d ineffective-fault countermeasure, the permutation-based fine-grained-detection lineage, selected with the masking rather than after it, with VERICA/FIVER-class combined verification joining the same untrusted ensemble; the load-bearing artifact is the Coq statement, and that half imports nothing: no proof-assistant masking development exists in Coq, so the probing model, a PINI-class composition theorem, and the R-17-058d reduction theorem beside them are original formalization whose nearest start-froms are the pen-and-paper theorems and the EasyCrypt gadget proofs to transcribe ([inspirations.md](inspirations.md), critique work-list item 29).
  The module's DRBG carries the R-05-004a expansion role, its computational security a named assumption rather than a silence, and ML-DSA signs hedged on this path (R-05-004a).

---

## 5. Kernel (Coq)

A **bespoke minimal capability core**, seL4's endpoint and non-interference model as the design base (not a transcription of mainline seL4), instantiated once per core (multikernel, §7): endpoints + notifications, partition contexts, a static cyclic-executive schedule (no MCS), CHERI epoch-and-load-filter revocation over a kernel-owned grant table (§8), the CHERIoT-lineage switcher/sealing and interrupt sentries (§15), **single address space, no VSpace/page-table objects** (the MMU is deleted, §7/§15), and **no untyped memory, no capability space, and no derivation tree** (§7, §8).
The stripped design is what makes the greenfield Coq proof feasible: the deletions (VM, MCS, SMP, S/U modes, PMP/IOMMU) remove the proof-heaviest and least-maintained layers of `l4v`, and the object-model deletion removes the retype invariants, the capability-space lookup refinement, and the CDT revocation proof that were the largest blocks remaining after them, leaving the novel CHERI pieces no base supplies (the seL4/CertiKOS and object-model rationale in [inspirations.md](inspirations.md)).

- **Toolchain**, **GC-free CompCert-C refined against the Gallina spec through CHERI-CompCert**, the seL4/CertiKOS/VST method the spec mandates (CompCert/SECOMP, §5).
  seL4 does **zero post-boot allocation** (§7), so the running kernel needs neither a collector nor even a heap; extracting it through a GC would wrap an allocation-free design in a managed runtime, exactly backwards.
- **Start from**, seL4's **Haskell executable specification** as the design template (it is the same artifact seL4 uses to generate its Isabelle spec), **mechanically translated to Gallina via `hs-to-coq`** rather than hand-transcribed, the scrutinized prototype is carried across by tool, not paraphrased, so a silent spec-transcription error cannot slip in (the abstract spec and refinement proofs are still authored fresh); reuse the seL4 ABI and object model for the **surviving object types only**, authoring the spec without the VSpace/paging and MCS classes rather than transcribing then stripping them, and cross-check the CHERI single-address-space and temporal-safety realization against CheriOS's reservation/claim model and CHERIoT's revocation (§15).
  This is the §5/§7 bespoke minimal capability core, seL4's design re-proved in Coq, but for bring-up we only need the *executable* Gallina model, not yet the proof.
- **Plan:**
  1. Translate the seL4 executable spec's surviving object types (dropping the VSpace/page-table/frame-mapping classes, single-address-space, §7; the MCS scheduling-context classes, a static cyclic executive replaces them, §7/§11; and the untyped, retype, capability-space, and derivation-tree classes the object-model deletion removes, §7/§8), endpoint/notification IPC, the partition context, and the cyclic-executive schedule into Gallina as an executable state machine, with revocation authored fresh against the CHERI epoch, grant-table, and load-filter model rather than translated.
     One call gates that authoring: [inspirations.md](inspirations.md)'s open proposal to bind revocation-sweep quanta to the slot boundaries of the domain being swept, against the incremental preemptible form R-08-007 specifies. The two differ in code shape, and the proposal's whole payoff, a deleted proof obligation (the sweep never overlaps its own mutator, and its root set becomes a composition-time artifact), is purchasable only before the incremental form is written; the call is taken or dropped before this step begins.
  2. Exercise it host-side via the Wasm build (create/derive/revoke capabilities, IPC round-trips, slot-overrun faults), the fastest way to shake out the logic.
  3. Refine the Gallina spec to GC-free CompCert-C (the CHERI-Alliance **CHERI-seL4 / CHERI-Microkit** release is the existing purecap C to start from, already building and running on CHERI-RISC-V against the draft-standard CHERI extension the §15 profile targets, so the C bring-up starts from maintained code and only its functional-correctness proof is fresh), compile through CHERI-CompCert, and boot **one instance per emulated core** with strictly disjoint state (the multikernel is the *sequential* kernel duplicated, §7), physical partitions enforced by **CHERI capability bounds**, each instance's partition-bounded root capability (§7), no PMP.
  4. Defer only the *proofs*: the functional-refinement proof (C ⊑ Gallina spec) and the non-interference theorem (§8), layered on later without changing the Gallina spec or the C; when they begin, the **purecap CHERI-C kernel refinement leads as the early kill-switch** (no CDT revocation proof stands in that role, there being no derivation tree; the object-model rationale is in [inspirations.md](inspirations.md)), leaving the refinement over CHERI-C semantics and the multikernel non-interference composition as the novel proofs that validate or falsify the route first.
     Purecap, GC-free compilation is **not** deferred, the §0 prerequisite backend means the kernel is purecap and managed-runtime-free from first boot.

---

## 6. OSTree-style object system + update transactor (Coq)

The content-addressed Merkle-DAG object store (§10, the OSTree inspiration) plus the **atomic update transactor** (§6 item 3), the system-integrity path: runtime read-verify against the boot-attested signed root, A/B generations, monotonic anti-rollback.

- **Toolchain**, **GC-free CompCert-C (VST/Iris) through CHERI-CompCert**, the §10 no-managed-runtime storage form, on the same codebase as the §7 filesystem below.
- **Start from**, `libostree` as the *conceptual* model only (content-addressed store, A/B deploy, rollback); write the store + transactor in Gallina.
  Hashing/signature checks call the §4 crypto module.
  This overlaps the storage L0/L1 layers (§7 filesystem) and shares their journal.
- **Plan**, implement in Gallina: content addressing (object = hash of bytes, Merkle-DAG links), **read-verify against the signed root** on every access, the **A/B atomic-commit transactor** (stage → verify → flip → fall back on health failure), and the **anti-rollback floor** sealed to the RoT counter (§9, §11).
  In the golden model the transactor's "proof-checked admission" (§11) is stubbed to a signature/hash check; the on-device *proof* checker is §9 below.

---

## 7. Filesystem (Coq)

The four-layer verified storage stack (§10): L0 journal, L1 CoW B-tree index, L2 FS semantics, L3 confidentiality, assembled as Gallina modules.
The spec's production form is CompCert-C + VST/Iris with no managed runtime (§10); the golden-model form keeps that **GC-free CompCert-C shape**, a managed runtime is banned here exactly as in the spec, and defers only the full VST *proof*, standing in differential testing against the Wasm oracle while the CompCert-C + VST/Iris re-homing is built.

- **Toolchain**, **GC-free CompCert-C (VST/Iris) through CHERI-CompCert**, against a modeled block device, per §10.
- **Start from**, the artifacts that are *already Coq*: **RefFS** (L2 concurrent linearizability + crash + liveness/MoLi) and **SFSCQ / DiskSec** (L3 data-noninterference).
  Re-express the **VeriBetrFS** B^ε-tree design (Dafny today) as the L1 CoW index in Gallina, and write the **Perennial/GoJournal** journal *design* (its proof is Coq, its code is Go via Goose) directly in Gallina for L0.
  Per-extent **AEAD** calls the §4 crypto module.
- **Plan**, compose L0 (journal) ⋈ L1 (parametric CoW B-tree, one index instantiated per object class) ⋈ L2 (typed keys, snapshot-version-in-key, RefFS semantics) ⋈ L3 (per-domain AEAD, noninterference) as Gallina modules; exercise host-side via Wasm against an in-memory disk; lower GC-free (CompCert-C/VST through CHERI-CompCert) to purecap RV64+CHERI to run on the emulator against a modeled block device.
  Instantiate typed object-metadata and secondary-index keys in that same L1 module, update object, metadata, and indexes through one L0 transaction, and derive bounded live-query deltas from committed typed-key changes; test confidentiality-domain and namespace-capability scoping, crash atomicity, ordered delivery, and overflow-to-rescan behavior.
  Build the **system-integrity instance first** (it is the transactor's backing store, §6), then the **user-data (bcachefs-class) instance** on the same codebase (§10).
  Below-the-line availability services (replication/EC/tiering/copygc/FTL) are *not* built in the golden model, they are the safe-Rust workstream (deferred).

---

## 8. Init system: the static supervision tree (Lustre via Vélus)

The service manager: a static supervision tree with declarative units, no ambient authority, capability re-grant on restart (§12, §16).
The spec assigns this **control plane to Lustre compiled by the Coq-verified Vélus compiler** (§5, §12), a synchronous state machine whose WCET, determinism, and causality are structural. Because Vélus is Coq-verified and emits CompCert Clight, it rides the golden model's Coq/Clight discipline directly (Vélus → Clight → CHERI-CompCert, §0), with a Gallina model of the same machine kept host-side as the differential-testing oracle.

- **Language**, Lustre for the control plane (the one exception to the Gallina contract of §0), with a Gallina reference model of the same state machine kept as the Wasm-oracle.
- **Toolchain**, **Vélus (Lustre → Clight) → CHERI-CompCert**: a synchronous node is statically allocated, so it is **GC-free by construction**, no arena or managed runtime.
- **Start from**, *no port.*
  The design references are systemd's unit/supervision *shape* minus ambient authority (§12) and Erlang/OTP supervisor semantics (static tree, restart strategy, backoff), a natural fit for a synchronous state machine; write it fresh in Lustre over the **compiled, typed, signed configuration objects** of §10 (no runtime text parsing).
- **Plan**, model as a Lustre state machine (with a Gallina reference): the static component graph loaded from the signed config generation, ordered capability-granting bring-up, crash detection, restart-with-backoff, and capability re-grant on restart.
  It consumes the object system (§6) for its config generation and the kernel (§5) for capability operations.
  In the golden model it is the first process the kernel starts, and it brings up the remaining (reference) components.

---

## 9. Admission checkers (CHERI-TAL type-checker ⋈ Coq/MetaCoq proof kernel)

**Two checkers, stratified** (main-spec §5/§6/§13).
The **on-device admission checker** is a *CHERI typed-assembly-language type-checker*, order-10³ lines, decidable, the small on-device axiom that validates every installed binary's **typing derivation** (Tier-2 memory safety, CFI, no-codegen, ABI/type conformance) against the spec/Sail-model versions.
The **CIC proof kernel** (MetaCoq-lineage, honestly larger) validates every installed binary's artifact-local source-correspondence theorem, and validates the deep Tier-0/hyperproperty proofs (functional refinement, non-interference, crypto reduction, the *residual unstructured* constant-time and WCET, filesystem) predominantly at release time over the base-image TCB, the structured constant-time and WCET cases being type-level in the CHERI-TAL (main-spec §5).
Both are the component class whose *golden model is essentially its production form*.

- **Language**, Coq/Gallina both: the CIC kernel is a proof-term type-checker; the CHERI-TAL checker is a typed-assembly type-checker whose **soundness metatheorem** (well-typed ⇒ safe over the Sail model; foundational-TAL / RustBelt / WasmCert-Coq lineage) is proved once in Coq.
- **Toolchain**, **VST-refined CompCert-C through CHERI-CompCert**, the same verified-compilation route as the kernel (§5) and storage (§6/§7), for **both** checkers: they are TCB, so unlike the contained components they may **not** ride the unverified MetaCoq→Rust extraction backend and the untrusted Rust→CHERI userspace toolchain (§0), that route is admissible only where the emitted binary is itself re-checked, and nothing re-checks the checkers.
  Arena/region allocation stays the memory discipline (type-check one proof term in a bump arena, then wipe it whole), but expressed as the explicit-memory CompCert-C the VST refinement covers, not GC'd, not unverified-extracted.
  **CertiCoq is *not* used on-device either**, its verified extraction still emits a GC, an unverified runtime inside the one axiomatic component (§0).
  The now-published **CertiCoq → Clight → CompCert** pipeline (MetaRocq's correct-and-complete checker extracted through CertiCoq, with **VeriFFI** the verified Coq↔C boundary and **CertiGC** the verified collector) *is* a real assemble-not-build route to a verified CIC checker, and it is **declined for the on-device axiomatic component deliberately**: even a verified GC is a runtime carve-out inside the one component whose binary nothing re-checks, and *engineering is free while trust is scarce*, so the VST refinement spends proof labor to keep the collector out of the axiom rather than bank the shortcut (*verify rather than hedge*, main-spec §15).
  It is retained host-side (the same slot as CertiCoq → Wasm) and stands as the documented fallback should the VST refinement of the full CIC kernel prove intractable; VeriFFI is then the wiring proof for *that* fallback, not for the on-device checker, which is refined to C and so has no Coq↔C boundary to prove.
- **Start from**, for the **CIC kernel**, **MetaCoq**'s verified checker (the "MetaCoq-style self-verification target" of §6), a Coq-implemented type-checker for Coq terms, as the Gallina *specification* the on-device C kernel is refined against (VST), inheriting MetaCoq's in-Coq soundness rather than re-deriving it through unverified tooling.
  For the **CHERI-TAL type-checker**, the foundational-TAL / RustBelt / WasmCert-Coq type-soundness lineage, its type system the CHERI-RISC-V instantiation carrying the temporal-safety + typed-control-flow residual CHERI leaves (main-spec §5/§18), the language it instantiates being specified separately in [typed-assembly-language.md](typed-assembly-language.md).
  The capability-machine program logic the soundness metatheorem builds on is already mechanized in Coq/Iris, **Cerise** (the universal contract for a capability machine, §13), its attestation extension **Cerisier**, and **StkTokens** (linear/affine stack capabilities), with **Katamaran** (semi-automatic separation-logic contracts over its μSail embedding of an ISA, a translation from the pinned Sail model that R-13-016 books as owed) available to discharge the per-instruction obligations, so the metatheorem extends a mechanized foundation rather than starting from scratch.
- **Plan**, refine both checkers to CompCert-C (the CIC kernel against the MetaCoq Gallina spec; the CHERI-TAL type-checker against its soundness metatheorem) and compile through CHERI-CompCert as the admission oracle; each package carries the exact hash-named source closure plus a correspondence proof through assembly, linking, and image construction, while in bring-up the packages they check are the golden-model components themselves (proof objects and typing derivations are thin/stubbed until the Tier-0/1/2 proofs exist).
  Their role hardens *in place* as real proofs arrive, the checkers do not change, only the derivations and proofs they are handed.
  **The checkers' own binaries are the bootstrap root** (§6 item 6 of the main spec): no package certificate can cover the admitters, so their trust rests on reproducible build + DDC + the RoT measuring them into the measured-boot chain, not on any admission proof of themselves.

---

## 10. Emulating the hardware: the golden emulator and the fast emulator

The hardware golden model *is* the Sail-C emulator of §1; "emulating the hardware" is standing up two whole machines around the same frozen profile, the golden one generated from Sail and the fast one forked from CHERI-QEMU, and booting the GC-free purecap software (§0) on both.

- **Single-core ISA emulator (day one).**
  `sail -c` on the curated model (§1) gives a fast single-core RV64IMV+CHERI emulator.
  Drive it with hand-written and randomly-generated ISA tests; this validates the *hardware* reference independently of any software.
- **Whole-machine harness.**
  Wrap the Sail-generated core with a thin host-C system harness that provides: **multiple core instances** (C-class ×N, V-class, M-class, the S-class sentinel, and the RoT RV64 core of §2), **physical memory** with the modeled ECC behavior as no-ops-with-latency (there is no memory cryptography to model, §15), and the **modeled devices**: a UART console (modeled first, nothing is debuggable before output exists), the block device the storage stack (§7) mounts, capability-checked DMA (default-deny capability-bounds checks on device transfers), the register-slave transceiver stream (with its fixed-function link-layer timing sequencer, §15), the scanout DMA block, and the RoT peripherals.
  Devices are modeled either as Sail memory-mapped regions (preferred, keeps them in the one language) or as C shims in the harness where that is faster to iterate.
  The **NoC and islands** are modeled as a simple address-routing layer in bring-up (the TDM schedule and non-interference semantics are §15 hardening, not needed for functional emulation).
- **Composed full-system golden model.**
  Boot the stack in the spec's §9 order on the harness: RoT core + firmware (§2) → M-mode firmware (§3) → one kernel instance per core (§5) → init (§8) → object system/transactor (§6), filesystem (§7), crypto core (§4), checker (§9), every image **GC-free purecap RV64IMV+CHERI**, produced by the §0 on-device routes (CompCert-C/VST through CHERI-CompCert, or arena extraction through the Rust→CHERI compiler), *never* the GC'd `CertiCoq → Clight` path.
  This is the reference machine: purecap, managed-runtime-free software on the verified-by-generation ISA.
- **The fast whole-machine emulator: a CHERI-QEMU fork (the daily driver).**
  A Sail-generated interpreter is faithful, not fast; the machine the stack is *developed on* is a **fork of CHERI-QEMU** curated to the same frozen profile, which buys TCG JIT speed, a GDB stub, deterministic `icount` execution, snapshots and record-replay, and mature machine/device scaffolding on day one.
  It is **untrusted evidence-producing machinery** (§0, main-spec §6), like the compilers and analyzers: it joins no trust base, is never the reference, and every divergence is adjudicated against the Sail golden model, so the only possible outcomes are a fixed fork or a genuine spec-versus-intent finding, the error class no proof covers (R-17-016).
  The fork is a re-parameterization, not a checkout, because the dialect is bespoke (R-15-007): stock CHERI-QEMU implements the ISAv8/v9 128-bit lineage, so the work is narrowing its `cheri-compressed-cap` library (already carrying 64- and 128-bit instantiations) to the §4.1 fields, implementing the frozen decode surface (the custom and fork-and-frozen instructions in, the excluded extensions out), deleting the MMU path (`satp` Bare, no S/U modes), adding the VLEN=4096 RVV datapath and the matrix/FEC units with per-element capability checks, and defining one machine type that models exactly the harness's device list above, no virtio, no PCI, no stock `virt` zoo.
  RVTSO is honored by construction in bring-up: deterministic round-robin `icount` execution is sequentially consistent, every behavior it exhibits is TSO-legal, and the weak outcomes an SC executor cannot exhibit belong to Isla's litmus exploration, not to this vehicle.
  This is exactly the instrument R-17-048a prices: the bespoke dialect degrades the stock instruction-level oracles (Spike, QEMU, the CHERI test suites), and the fork is the compensating purchase, a second implementation of the profile from an independent code lineage, maintained alongside the Sail model, so spec-versus-intent divergence always has two executors to disagree.
  The plan's **intermediate goal** is the full §9-order boot on this fork; the composed Sail emulator re-runs the same boot in CI as the golden cross-check.
- **Three loops, one source.**
  For OS-logic iteration that needs no ISA in the loop at all, run the *same* Gallina components as **CertiCoq → Wasm** on a host Wasm engine: the inner loop, no toolchain, image, or machine model required.
  The QEMU fork is the middle loop, the whole machine at JIT speed; the Sail-C emulator is the outer loop, the reference every divergence returns to.
  All three execute artifacts of one source, so a bug found in any loop is fixed once.
- **Test generation and differential testing: one corpus, one trace format, three executors.**
  Use **Isla** (symbolic execution over the Sail model) to derive ISA test vectors and the concurrency/Ztso litmus set from the frozen model, normalizing every legal `fence` encoding to the profile's two outcomes (`drain | nop`) rather than generating predecessor/successor-set cases.
  The rig is a named deliverable rather than a habit: the corpus is versioned at M0, and its executions are compared through one **capability-widened RVFI-style commit trace** (PC, instruction, register and memory effects, plus tag, bounds, permissions, and seal state) emitted by the Sail emulator, the QEMU fork, and the RTL (via its `rvfi` port, §11; R-15-094 already names `rvfi` the cheapest bring-up evidence).
  One CI runner diffs the trace per-instruction over the corpus, and per-boot (console, event, and final-state digests) over the composed images where instruction lockstep is too slow.
  The Sail emulator stays the **oracle** for everything downstream; the QEMU fork and the FPGA are both checked against it, never against each other alone.
- **Staging.**
  C-class scalar emulator + software rendering first; add the V-class vector datapath, then M-class matrix, then FEC, then multi-core + islands, mirroring §18, each class extending the *same* Sail model and re-generating the emulator.
  Each class lands in the Sail model first, then in the fork, then in RTL (§11's ordering rule), so every executor is brought up against an already-validated predecessor.

---

## 11. Building an FPGA from it all

The golden model is Sail, not RTL, so an FPGA needs RTL.
Per the two-language ideal and the semantic-anchor budget (main-spec §5), RTL ⊑ Sail is discharged along a **three-route ladder** (main-spec §15), detailed just below: net-new blocks **authored in a formal-semantics HDL** and proven against the Sail source, imported cores given **Sail-SV + commercial-FEV** observational-equivalence evidence, and open cores kept as **differentially-tested functional references** for the early milestone, with the closing Coq refinement layered on afterward (§18).

- **Three routes to RTL, laddered by what each buys.**
  - **(a) Author the net-new blocks in Kôika/Kami** (Coq hardware DSLs): the blocks with no legacy RTL to preserve (the capability/tag-carrying DMA fabric, TDM NoC, and fixed-function sequencers) are written in the formal-semantics HDL and proven to refine the Sail golden model, with **PipelineGen** and **Sail → Kôika/Kami** generation as scaffolding rather than the design of record.
    This is the closing path and keeps the hardware on the single prover; **Erbsen et al.** (PLDI 2021, Bedrock2 + Kami) is the existence proof that an end-to-end software ⋈ hardware theorem rides exactly this spine, with no SystemVerilog in the trusted path (SystemVerilog is generated output for synthesis).
  - **(b) Give the imported cores Sail-SV + commercial-FEV evidence**: Sail's SystemVerilog backend emits a reference model from the ISA and a commercial FEV tool (Jasper-class) proves the imported CHERI-CVA6 (and Ara/Gemmini) RTL observationally equivalent to it, the published CHERIoT-Ibex conformance methodology at application-class scale, unbounded observational-correctness evidence at near-zero method-development cost though the FEV tool is trusted (main-spec §6/§15).
    Their Coq close is deferred: author-in-Kôika where a block is being rebuilt anyway, or a proof over the shipped SystemVerilog if a foundational Verilog-semantics account matures.
  - **(c) Bring up open cores as functional references + differential-test**, take the open RTL substrate per class and validate it against the Sail emulator (§10) as the oracle for the *early* FPGA milestone.
    This is the pragmatic near-term path and matches the "fast golden model, defer the proofs" mandate: no RTL ⊑ Sail *proof* is required for the FPGA milestone, only differential agreement with the golden model, and the open cores are the differential-test reference substrate on which route (b)'s stronger FEV evidence is layered, while route (a) supplies the authored, proven net-new blocks.
- **Open RTL substrate (route b), per class (§18).**
  For the **C-class scalar** front end an *existing CHERI RV64 soft core*, **CHERI-CVA6** (Bristol / lowRISC / OpenHW) or the Bluespec **CHERI-Flute / Piccolo / Toooba** (CTSRD), *modified to static-only prediction* and a TSO store buffer per §15; **Ara** (PULP) for the V-class vector unit; **Gemmini** (Berkeley, Chisel) for the M-class matrix unit; open **LDPC/polar** cores for FEC; and for the **RoT**, **Ibex** + `lowRISC/opentitan` as the functional reference and **CHERIoT-Ibex** (Sonata) as the CHERI-on-Ibex reference, the on-die core itself a small **scalar RV64+CHERI** purecap core in the main die's capability format (§1), not CHERIoT's separate encoding.
  All are SystemVerilog/Chisel, synthesizable today.
  The **CHERI-CVA6** option specifically has a commercial-quality, formally-verified open track: the lowRISC / Capabilities Limited **COSMIC** project (2025–28) hardens it on OpenTitan IP and proves its instruction execution conforms to its ISA spec, the application-class successor to the CHERIoT-Ibex conformance proof, directly de-risking the *"RV64 application-class CHERI exists only as soft cores"* binding constraint (§18) and handing the RTL ⊑ Sail bring-up gate a real application-class artifact (see [inspirations.md](inspirations.md)).
- **Concrete bring-up artifact, CHERI Mocha (COSMIC MVP-2, `lowRISC/mocha` v0.1.0).**
  That COSMIC track is already shipping a tagged, FPGA-synthesizable **secure-enclave SoC**, the CVA6-CHERI application core plus OpenTitan peripherals, that boots to a terminal prompt on a **Genesys 2 (Kintex-7)** board.
  It is a **Start-from** for the C-class-scalar-plus-RoT bring-up here: the application core is the C-class front end above; the bundled **entropy source, KMAC, ROM controller, SPI host, and mailbox** are functional-reference RTL for the RoT, its measured-boot chain, and the RoT-to-die control handoff, the **KMAC** (Keccak/SHA-3) doubling as a reference for the SHAKE-heavy PQ crypto core, and the bare-metal **HAL** (`sw/device/lib/hal`) is a Start-from for the verified DMA/MMIO/descriptor HAL, to be re-homed onto Verus/Prusti/Aeneas.
  Its **AXI tag controller** is the concrete functional reference for the one interconnect piece the purecap design most needs and the spec already owes (§17): the **capability- and tag-carrying fabric** that must propagate tags and revocation state, realized in Mocha as one CHERI tag bit per 128-bit region carried on the bus user bits, tags held in a separate memory block from the data (this platform's granule is 64 bits, R-15-203, so the reference is a shape to follow rather than a parameterization to copy). That separate tag block is the same tag-plane shape the validity plane takes (§15), which is the only tag plane the design carries: Write-before-Read is a type attribute, not a second plane (§5).
  Its top-level **OTP-backed rollback counter** port is likewise a reference for the anti-rollback monotonic floor (main-spec §9).
  Its **memory-encryption-key** ports have no counterpart here and are left unused: the memory path carries no key material, no cipher, and no integrity construction (§15), so there is no memory-crypto block to bring up, and that is the single largest reduction in net-new Kôika RTL on the whole plan.
  It stays a *reference*, not an admitted artifact, unverified RTL under the same route-(b) disposition as every core above. Its verification today is OpenTitan-style staged design-and-verification sign-off: UVM simulation plus bounded formal-property (FPV) assertions, three-reviewer per-block checklists, and first sign-offs targeted at RC-1 (Dec 2026). This is not the unbounded **RTL ⊑ ISA conformance proof** the golden model wants (§18), so MVP-2 is a maturity milestone, not a verification one.
  Two pieces are pointedly *not* imported.
  The **debug module**, a development-visibility backdoor into the enclave, is admissible only where §15 already puts external debug: **gated behind RoT lifecycle state**, fused-off in production, never a shipping surface; its trace is the sole development cycle-measurement path after `Zicntr`/`Zihpm` are deleted.
  And Mocha's headline **CHERI-Linux boot** is the enclave-beside-Linux framing the design refuses (§14, *no Linux-personality shim*): the core, peripheral, and HAL RTL transfer as references; the operating system does not.
  The divergence is architectural, not merely the software stack: Mocha fields an **application-class core precisely to give enclave OSes an MMU** and virtual memory (its stated rationale for CVA6 over a real-time core), whereas this profile **deletes the MMU** outright (single-address-space, `satp` Bare, §15).
  So the CVA6-CHERI *datapath* is the Start-from, but the MMU-on, virtual-memory configuration that is Mocha's whole reason for an application-class core is curated away, and Mocha's conformance evidence for that path covers hardware the platform never runs.
- **CHERI runs on FPGA, and purecap software is ready for it, no stop-gap.**
  CHERI *runs on FPGA today*: the scalar CHERI RV64 soft cores above make the **C-class FPGA purecap from the start**, and because the **functional CHERI-CompCert backend is a prerequisite** (§0), the purecap golden-model images boot on it directly, purecap from first bring-up, with no capability-degraded interim.
  The genuinely new RTL + Sail work (§18) is CHERI for the **V-class and M-class**, Ara and Gemmini are not capability-aware, so extending their vector/matrix memory ops to per-element capability checks is the real hardware effort, *not* the scalar core.
  The only *silicon* gate (§18) is fabricating a CHERI **ASIC** for a shippable product, irrelevant to emulation and FPGA.
- **Profile curation in RTL.**
  Two documents decide this and neither is restated here: the [frozen instruction-set profile](isa-profile.md) says what the hardware must implement, and the [microarchitectural absence contract](absence-contract.md) says what it must not contain and what evidence an auditor searches the elaborated netlist for.
  The second runs *during* FPGA bring-up rather than waiting on it: the imported cores exist today, so the contract's state enumeration and its synthesis-configuration provenance are recorded at the moment a core is first elaborated, which is also the moment the disabling parameters are chosen.
  Each row of either document is *less* hardware than the stock core, not more.
  One item is a re-parameterization rather than a removal, and it paces the scalar milestone: the imported cores implement the ISAv8/v9 128-bit capability lineage while the frozen dialect is 64+1-bit (isa-profile §4.1), so the CVA6-CHERI datapath's capability format is **re-parameterized, not configured**.
  The bespoke format is thus implemented three times across the plan, Sail first (the definition), the QEMU fork second (the fast oracle), RTL last (the implementation), landed in that order so each implementation is brought up against an already-validated predecessor.
- **Co-simulation is the RTL gate; the board is not.**
  The deliverable the MVP names (§12, M8) is an **RTL artifact of record**: a versioned, lint-clean, elaborated SoC top, the curated C-class scalar core, the RoT core and its peripherals, the tag-carrying interconnect, boot ROM, UART, and block device, generated SystemVerilog where authored and curated SystemVerilog where imported, published with its synthesis-configuration provenance and absence-contract evidence recorded at first elaboration (above).
  It is *matching* when, under **Verilator co-simulation**, its capability-widened `rvfi` commit trace (§10) agrees with the golden model across the shared corpus, CVA6's existing `rvfi`/tracer port being the hook, and the composed purecap image boots to the same console and event digests as both emulators.
  Every clause in that sentence runs in CI with no hardware attached, so *a solid RTL file in hand* is a software-visible, reproducible claim; FPGA synthesis afterward validates timing closure and resource fit, not function.
- **Synthesis + bring-up staging.**
  Synthesis follows the co-simulation gate: the artifact that boots in Verilator is the one synthesized.
  Target a large FPGA (Xilinx/AMD UltraScale+ or Versal class, or an open board where capacity allows).
  Bring up **C-class scalar first** (boots the same M-mode firmware → kernel → init stack from §10), then **V → M → FEC → NoC → islands**, class by class, each differentially tested against the Sail golden model.
  The **S-class sentinel** and RoT are small and come early.
- **Deferred hardening (named, not built here).**
The **riscv-formal/rvfi** BMC bring-up gate (on the generated SystemVerilog), the **Sail-SV + commercial-FEV** observational-equivalence evidence for the imported cores (route b), the **Isla**-generated obligations, and the closing **Kami/Kôika** RTL ⊑ Sail refinement over the **authored** net-new blocks (route a; §15, §18) are the path from "the reference cores differentially agree with the golden model" to "the shipped RTL is proven to refine it."
  They are explicitly out of scope for the FPGA milestone and layered on afterward, the golden model remaining the reference they target.

---

## 12. Build order, milestones, and execution state

Bottom-up, each milestone runnable against the prior one; the software track (M-numbers) and the RTL track (R-numbers) proceed in parallel after M0 and meet at the MVP gate, M8.

The order records a sequencing decision rather than an accident: realization is **scalar-first**, the V/M/FEC datapaths arriving last (M10), and the staging discipline of *add a unit only after a measured need* applies to the units alone, never to the capability width. R-15-007d freezes the width with the profile at M0, permanently, every capability in the immutable image and every sealed blob stored in the frozen format, so no later measurement can reopen it without invalidating stored authority wholesale; the width is decided once, at the freeze, and only the units are staged.

The milestones are also the review gate's clock: a crown-jewel row a milestone flips to `authored` enters R-05-150's independent specification review at the flip, not in a release-time batch, so each specification is read at the edition the proofs will be stated against rather than re-read from a corpus that has moved on.

One crown-jewel row retires off this clock: the pinned Wasm guest semantics (inventory row 25, R-14-013b) gates no M-milestone, because the platform interpreter it serves ships with the §18-deferred application program rather than the base system, and its curation is scheduled there: it is the inventory's cheapest retirement, a version-pin of the mechanized WasmCert lineage whose soundness and confinement theorems arrive with the artifact, so the authoring cost is the pin, the subset cut, and the review, not a formalization. The M1 CertiCoq → Wasm host-side oracle is unrelated to it: that is build-farm machinery on the host, and R-05-085's device claim is untouched by it.

Four more rows take their upstreams off this clock while their authoring rides the release program: the radio reference state machines (inventory rows 19–22) arrive with the roster the first release carries whole (R-18-004), and under R-12-043e each begins as a version-pin of the machine-checked symbolic analysis of its protocol, a transcription into the one prover, and a formal-to-formal review, not an original reading of the prose standard. The pinning sweep, deciding which edition of each Tamarin or ProVerif artifact serves as the row's upstream, is the first task of each row's authoring and the cheapest part of it, the analyses' security statements arriving with the artifacts as producer-side evidence; the RRC row additionally names which procedures fall outside the published analyses and take the R-05-050 hand-transcription posture instead, so the thin lane is scoped before it is walked.

### Checklist conventions

* Checked items include concise completion evidence.
* **Every item carries one estimate cell, and only what is inside it is authored.** An open item reads `· 6 h, range 4–8 · 0.7%`, a completed one `· 1.9 h actual · 0.2%`; the range and the actual are the estimates, in attended agent-session hours, and are re-priced when split. The rest is arithmetic: the midpoint is the mean of the range ends, and the percentage is that midpoint's share of the grand total. An item whose children carry the estimates carries none of its own.
* **Every subtotal, the grand total, its range, and the progress figures are sums over those cells**, recomputed by `tools/check.py` (`-Fix` rewrites them), so a re-priced item moves everything resting on it in the same edit.
* `Parallel` means the item can proceed in a separate worktree and build directory.
* Later milestones remain deliverable-level until entry.

### Current summary

* Completed: M0.1–M0.5, M0.6a, M0.6b, M0.6c (c1–c4), M0.6d, M0.6e (e1–e5), M0.6f, M0.11, M1.1, M1.5, and the build-loop instruments I0 and the initial check/emit/FAST tooling.
* Current serial path: M0.6g → M0.6h → M0.10 C-class freeze.
* Available parallel work: M0.7, M0.12 drafting, M2.1, and M4.1. M0.12 is the batch that most wants doing: the model's own `$[test]` harness is the whole of the regression corpus until purecap programs exist.
* Total estimate: 797.5 h midpoint, range 548–1,047 h.
* Progress by estimate: 41 of 797.5 h complete (5.1%); 756.5 h remaining (94.9%).
* M8 gate: 714.5 h of the 797.5 h midpoint falls at or before it, everything but M9, M10, and the post-M10 obligations. Planned optimizations remove roughly 32 h from that and measured gating may defer a further 35 h past the gate; the critical chain through it is approximately 361–422 h, a serial-path figure no sum gives.

### M0 · Hardware reference

Curated Sail model (§1) → single-core RV64IMV+CHERI emulator; ISA tests green. Define the profile-freeze measurement contract (§0): versioned corpus manifest, emitter-provenance schema, report schema, admitted region classes, and per-choice acceptance thresholds. Publish the shared differential-testing corpus and the capability-widened commit-trace schema (§10) that every later executor emits.

#### Baselines

* [x] **M0.1 · Pin upstream models** · 0.7 h actual · 0.1%
  * `sail-riscv` pinned at `6266b40c`; `sail-cheri-riscv` pinned at `bb07488d`. The vendoring baseline is `8f91355e` (M0.6a); the pin tracks the edition the curation is reconciled against, so advancing it is the act of carrying an upstream change across rather than a record of where the tree came from.
  * Finding: the CHERI tree embeds older `sail-riscv` commit `b748a82`; reconciliation therefore requires a semantic transplant, not configuration of one shared base.
  * Upstream carriage is a **disposition per commit**, not a merge: the curated tree has deleted most of what upstream touches, so each change is either applied, or refused with the deletion that makes it inapplicable. Against `8f91355e..6266b40c`: the `Zvknh` predicate grouping (#1881) **applies**, a missing parenthesis that let `zvknhab_check_encdec` guard only the `Zvknhb` disjunct, and lands in `zvknhab_insts.sail`; the `config_file` build dependency (#1885) **applies** to the two prover-backend rules that survive, SMT and Rocq, the three `rmem` rules it also fixed having gone with the dormant targets in c1; and the WFI external-interrupt wake (#1868) is **inapplicable**, its bug being that `MEIP`/`SEIP` are not held in `mip` so a bare read hides them, where M0.6d deleted the fields, their sources, and `read_mip` itself, leaving `mip` carrying `MTI` alone and `shouldWakeForInterrupt`'s bare read total.

* [x] **M0.2 · Stand up the Sail toolchain** · 0.5 h actual · 0.1%
  * WSL Ubuntu 26.04, opam 2.5.0, OCaml 5.4.0, Sail 0.20.2, and z3 5.1.0.
  * Sail 0.20.2 is the required and fidelity-pinned compiler version, and the OCaml the switch is built on stays the distribution's and moves with it, because fidelity is a property of the emitter. The solver is now pinned too, and on a weaker ground that is worth stating rather than eliding: soundness is not a property of which sound solver answered, so no version here is *owed*. What the pin buys is that the solver is one this tree names instead of one the archive happens to carry, checked before the move by typechecking the model under 4.13.3, 4.16.0, and 5.1.0 for the same verdict. What it costs is the distribution's patching, which becomes this tree's to carry.

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

#### M0.6 · Curate the frozen profile

* [x] **M0.6a · Stand up the curated tree** · 0.5 h actual · 0.1%
  * Vendored `model/` byte-identically from `8f91355e` with LF normalization fixed.
  * `tools/model.py build` builds out of tree with the larger OCaml stack.
  * Exit evidence: build green; 664/664 tests pass.

* [x] **M0.6b · Measure configuration-level curation** · 0.4 h actual · 0.1%
  * `model/config/verifiedos.json` captures all profile rows supported by the config schema.
  * Profile run: 132/134 adopted-family physical tests pass; both failures are expected profile refusals.
  * Source-level residue: scalar F/D coupling, CSR narrowing and trap totality, `vstart`, and AIA.
  * Decision: configuration identifies the deletion worklist but does not substitute for source removal.

* [x] **M0.6c · Remove excluded source surface**
  * For every removed extension, update the project file, extension directory, extension registry, config schema, test lists, and stray config readers.
  * Require `tools/model.py typecheck`, full build, schema validation, and profile-subset tests after each batch.

  * [x] **c1 · Leaf extensions** · 1.9 h actual · 0.2%
    * Removed unentangled excluded modules, obsolete reservation-size declarations, entropy hooks, dormant targets, and the virtual-memory test half made unusable by removing `FENCE.I`.
    * Net change: 3,079 lines removed and 77 added across 50 files.
    * Exit evidence: build green; 352/352 tests pass; generated and profile config keys match exactly.
    * Expected profile refusals: 26 of 199 physical-variant tests.
    * Reservation plumbing remained for c3, which took it.

  * [x] **c2 · Entangled extensions** · 1.9 h actual · 0.2%
    * Removed `C` (`Zca`, `Zcb`, `Zcf`, `Zcd`), `Zicbom`, `Zicbop`, pointer masking, `Stateen`, CFI/`Zicfilp`, `Smcntrpmf`, and `Zicntr` with their core and system hooks: the `cacheop` union narrowed to `CB_zero` alone and its arms dropped from the PMA, PMP, page-table, and fault-type matches; `mseccfg` deleted outright; `MPELP`/`SPELP`/`LPE`/`PMM`/`CBIE`/`CBCFE` gone from `mstatus`, `sstatus`, and the `envcfg` pair; `misa[C]` hardwired to zero with the `ext_veto_disable_C` hook and its file; the landing-pad checks out of the step function; and `transform_effective_address` reduced to the identity.
    * Net change: 2,494 lines removed and 69 added across 47 files, 19 of them deleted.
    * Exit evidence: build green; 346/346 tests pass; `verifiedos.json` validates against the regenerated schema with key sets consistent.
    * Expected profile refusals: 27 of 199 physical-variant tests, every one explained: the three c1 cuts, the standing M0.6b pair, nine supervisor and PMP tests c3 takes, ten `Zfh` tests the profile excludes, plus `zicntr` with `instret_overflow` and `uc-p-rvc` from this batch. The sweep now caps each run at ten seconds, which books `rv64si-p-dirty`, whose handler never terminates with S off, as a refusal rather than a hang.
    * Three findings. Fixed-width fetch is a *deletion of gating*, not of the 16-bit path: the parcel check stays, because ILEN=32 makes a 16-bit parcel an illegal instruction rather than a misaligned fetch, so `C_ILLEGAL` and the compressed decode mapping are load-bearing with zero real clauses behind them. The alignment relaxation lives in four places, not one, `fetch`, `rvfi_fetch`, `jump_to`, and the `xepc` legalization pair, and only the first two are obvious from the extension registry. And the Lean emulator's handwritten register initializer was already stale from c1 (it wrote `stimecmp`, deleted with `Sstc`), which the typechecker cannot see because that target is dormant; it and the two `SAIL_MODULES` lists naming deleted modules are corrected here.

  * [x] **c3 · Privilege and translation batch** · 4 h actual · 0.5%
    * Removed S and U modes with delegation and the whole S-mode CSR bank, `satp` with the `Sv*` walkers, TLB and `sfence.vma`, PMP, the reservation plumbing, and the performance counters. The privilege *type* goes with the modes: `Privilege`, `cur_privilege`, and the privilege parameter threaded through `is_CSR_accessible`, `mem_read`, `mem_write_*` and `pmaCheck` all had exactly one reachable value. `mstatus` narrows to the extension-context gate, `mret` restores the interrupt-enable stack and nothing else, `sret` is gone, `mip`/`mie` keep only their machine bits, `translateAddr` collapses into the identity `physical_address`, and `menvcfg`/`senvcfg` go with the mode their every bit gated.
    * Net change: 5,006 lines removed and 742 added across 68 files, seven deleted outright and three renamed as their surviving content moved (`vmem_types.sail` → `mem_access_types.sail`, `vmem_utils.sail` → `mem_access.sail` with `vmem_read`/`vmem_write` → `data_read`/`data_write`, and the `mstatus` SXL/UXL unit test replaced by one over the properties this batch establishes).
    * Exit evidence: build green; 329/329 tests pass; `verifiedos.json` validates against the regenerated schema with key sets consistent.
    * Expected profile refusals: 28 of 199 physical-variant tests, every one explained: ten `Zfh` tests the profile excludes, the three c1 cuts, the three c2 cuts, the standing M0.6b pair, and this batch's ten, being the seven supervisor tests, `pmpaddr`, `ssvnapot-p-napot`, and the RV64 machine-CSR test. Under the max configuration the same cut excludes 17 tests, the RV32 and RV64 halves of the supervisor family and `pmpaddr` plus the two RV64-only rows; the RV32 machine-CSR test still passes and is not excluded.
    * Four findings. `minstret` had a consumer that is not architectural, RVFI's `order` field, so deleting the counter would have deleted the differential rig's instruction ordering with it; a model-internal `retire_count` register with no CSR address replaces it. The reservation flag on the memory API was never only a reservation flag: `res`/`con` selected the reserved-read and conditional-write kinds of the concurrency interface, and after `Zalrsc` its one caller is the AMO, whose two halves are exactly those, so the parameter is *derived* from `is_amo_access(access)` rather than deleted, and stops being passable independently of the access it describes. Two tests hang rather than fail and so cannot be left to a ctest timeout: `rv32si-p-dirty` and `rv64si-p-dirty`, whose handlers wait on a page-table A/D update that never comes with S off, which is the same behaviour c2 booked as a profile refusal now appearing where it blocks. And `pagesize_bits` survives the walker: PMA regions are still required to be 4 KiB-aligned so a PMA property cannot change inside one access, so the constant is renamed `pma_granule_bits` rather than deleted, under a name that no longer implies pages.

  * [x] **c4 · Vector fork** · 3.5 h actual · 0.4%
    * Removed `vstart` and, with scalar floating point, the whole coupling it was named beside: the `f0`–`f31` register file, `fcsr`/`frm`/`fflags`, `mstatus.FS`, the `F`/`D`/`Zfh`/`Zfhmin`/`Zfa`/`Zfinx`/`Zdinx`/`Zhinx`/`Zhinxmin` extensions with their instruction files, and the scalar half of the bf16 converts. The two forks the profile books (R-15-040, R-15-040a) are now the model's shape rather than a residue in its configuration: `Zve32f` no longer requires `F` and `Zve64d` no longer requires `D`, and the validator rule that demanded them is gone.
    * The vector unit keeps every floating-point form it had. The scalar operand of a `.vf` instruction is the low SEW bits of an **integer** register, which is where a soft-float-register calling convention already puts a floating-point scalar (R-15-039, R-15-040, [spec.md](spec.md) §15); `vfmv.f.s` writes its element zero-extended into one rather than NaN-boxed, there being no wider register to box into; and rounding is the static RNE of R-15-083, since RVV encodes no rounding-mode field and the conversions that name round-toward-zero pass it themselves.
    * Net change: 5,448 lines removed and 430 added across 56 files, nine deleted outright. The `c_emulator` harness is in that count: the GDB stub's floating-point annex, the `--trace-fpr` option, and the `freg`/`fcsr` accessors and write callback all named registers that no longer exist.
    * Exit evidence: build green; 261/261 tests pass; `verifiedos.json` validates against the regenerated schema and its key set agrees with the generated max configuration at 129 keys ([tools/model.py config-keys](../tools/model.py)), 29 fewer than M0.6d's 158.
    * Expected profile refusals: 53 of 199 physical-variant tests, 52 refusals and the standing `rv64si-p-dirty` hang. This batch adds 24 to M0.6d's 29: eleven `rv64uf`, twelve `rv64ud`, and one more `rv64uzfh`, the test that had passed on F/D register moves while the residue stood. The ctest suite loses the same three families in both XLENs, 66 tests, which is the whole of 327 → 261.
    * Four findings. **The `.vf` forms had to be re-homed, not deleted**: ten instruction families name an `f` register upstream, and deleting the register file leaves the encodings needing a source, so the operand moves to the integer file and no encoding changes; the cost is that `vfmv.v.f` and `vfmv.s.f` become bit-for-bit duplicates of `vmv.v.x` and `vmv.s.x`, and `vfmv.f.s` differs from `vmv.x.s` only in zero- versus sign-extension, which is three encodings the freeze can reclaim and not a curation batch's call. **`fflags` has no destination and two comparisons still read it**: 44 accrual sites go, and the softfloat interface's flag half is discarded everywhere except `fp_gt`/`fp_ge`, where the invalid-operation flag *is* the result (a quiet comparison answers false on a NaN), so it is read where the interface returns it; the software-visible consequence is that no sticky IEEE flag is readable and a program that must detect an invalid or inexact result tests the result. **The scalar files were carrying the vector unit's classification predicates**, 33 of them (`f_is_*_{H,S,D}`) plus `negate_{H,S,D}`, and the Sail float library's width-generic `float_is_*` are the same tests, so each three-way dispatch collapses to one line and the negate to a sign-bit flip; only `canonical_NaN` and three flag constructors had to move, to [float_classify.sail](../model/model/core/float_classify.sail). And **the `vstart` cut deleted an implementation-compatibility hack**: the four scalar-move instructions computed an LMUL-based element count only to match the bound other implementations chose for the `vstart` check, so the count, the LMUL read, and the question go together; the whole-register load and store lose their partial-register prologue, and the vector-crypto element-group start collapses to zero.
    * Two residues, both booked rather than closed. R-15-039a states that a vector operation is all-or-nothing, and the model writes elements as it goes, so a fault at element *i* leaves the elements before it written with nothing recording where; on this machine that is a fail-stop program error rather than a resumable trap, but whether the register-group write should be buffered to make the claim literal is a question for the capability-fault path M0.6e authors and is settled there. And the dormant first-party test harness (`FIRST_PARTY_TESTS` is off) now names scalar-FP surface too, `test_bf16_nan_boxing.S` and the hard-float ISA strings every test compiles with, joining the PMP, `satp`, `minstret`, and LR/SC tests c1–c3 left stale; the Lean emulator's initializer is corrected here as c2 corrected it, but the first-party set wants one pass of its own.

* [x] **M0.6d · Close the CSR bank** · 2.5 h actual · 0.3%
  * Narrowed `mie`/`mip` to the machine-timer bits, hardwired the implementation identifiers to zero, made `misa` read-only, and deleted `Sdtrig`'s `tselect`. `MEIE`/`MEIP` and `MSIE`/`MSIP` are gone as *fields*: the `Minterrupts` bitfield carries `MTI` alone, so the unnamed bits of the underlying `xlenbits` are the hardwiring and no legalization can set them. `mip` becomes read-only outright, its one writer the timer comparator.
  * Net change: 455 lines removed and 135 added across 19 files, three deleted outright. Two stragglers of c3's delegation cut go with them, both dead rather than wrong: a CMake variable holding the delegatable-bits mask nothing has read since `mideleg` left, and the `WFI` comment stating an exemption over a register that no longer exists.
  * Exit evidence: build green; 327/327 tests pass; `verifiedos.json` validates against the regenerated schema and its key set agrees with the generated max configuration at 158 keys ([tools/model.py config-keys](../tools/model.py)).
  * Expected profile refusals: 29 of 199 physical-variant tests, every one explained: ten `Zfh` tests the profile excludes, the three c1 cuts, the three c2 cuts, the standing M0.6b pair, c3's ten, and this batch's one, `mi-p-breakpoint`, which opens by writing `tselect` to count the triggers it may use. The sweep is now a repository instrument rather than a per-batch shell loop ([tools/model.py sweep](../tools/model.py)), which is also what classifies a hang as a refusal that blocks rather than leaving it to a ctest timeout.
  * Four findings. The trap on an unallocated CSR address was already total and needed no work: `is_CSR_accessible` defaults to false in `csr_end.sail`, so `check_CSR` rejects every address no clause claims, and c3's exclusion of `mi-p-pmpaddr` for trapping rather than reading zero is the standing evidence; what this batch adds to it is four more addresses, `tselect` and `tdata1-3`, whose name-map rows went with the register. Deleting the two interrupt *fields* deletes their two sources with them: the Simple Interrupt Generator device existed only to drive `MEIP`/`MSIP` and is gone entirely, and the CLINT's `msip` door with it, which leaves the CLINT as the machine timer and nothing else. The external-interrupt bit was also the sole reason `mip` read one value into `rd` and a different one into its own read-modify-write, so its deletion collapses `doCSR`'s two-value split into one and takes the platform-interrupt OR, the `XipReadType` enum, and `read_mip` with it. And two enumerations follow the same one-reachable-value rule c3 applied to `Privilege`: `InterruptType` keeps `I_M_Timer` alone, and `breakpoint_cause` goes entirely, `ebreak` being the only breakpoint source once the trigger module is deleted, which also removes a non-injective mapping whose two arms both encoded cause 3.

* [x] **M0.6e · Transplant CHERI capability semantics**
  * Port capability types and compression, merged registers, tag memory, PCC/sentries, machine trap capabilities, load/store checks, and ISAv9 trap causes.
  * Differentially compare RVFI-style traces with the M0.4 oracle.
  * The transplant carries ISAv9's **128-bit** parameterization rather than the frozen one, and that is the batch's shape rather than a delay: the M0.4 oracle is the differential reference, it is a reference only while the two models agree on the format, and what this batch owes M0.6f is an algebra whose field widths are the only thing that has to move (R-15-007a).
  * The extension hooks the transplant hangs off (`ext_data_get_addr`, `ext_control_check_pc`, `ext_fetch_check_pc`, `ext_check_CSR`) have been in their final, privilege-free shape since c3.

  * [x] **e1 · Fix XLEN at 64** · 1.2 h actual · 0.2%
    * `xlen` stops being a configuration key and becomes the constant 64, and the RV32 configuration goes with it: the generated `rv32*` configurations, the `--rv32` default and its embedded JSON, the RV32 test lanes in all three corpora, and the RV32 prover-backend target. The base is RV64 (R-15-001), no plain-RV32 target exists anywhere on the platform (R-18-002), and there is one model of one machine (R-15-005).
    * Net change: 385 lines removed and 254 added across 40 files. Deleted with the base: `mstatush`, which is the RV32 high half of `mstatus` and whose address is now unallocated and therefore trapping (R-15-014); the `Architecture` enumeration with its two-bit encoding and the `architecture()` and `in32BitMode()` queries over it, `misa.MXL` becoming the constant `0b10`; `Zbkb`'s RV32-only `zip` and `unzip`; the RV32 encodings of `zext.h` and `rev8`; the RV32 arms of the `Zbs` mask computation; and `asidlen`, left over from address translation. Thirty-seven vacuous `xlen == 64` guards collapse with them.
    * Exit evidence: build green; 150/150 tests pass; `verifiedos.json` validates against the regenerated schema and its key set agrees with the generated max configuration at 128 keys ([tools/model.py config-keys](../tools/model.py)), one fewer than c4's 129, the key being `base.xlen`. The RV64 profile sweep is unchanged at 53 of 199, 52 refusals and the standing `rv64si-p-dirty` hang, which is the point of running it: the freeze removes no RV64 surface, and 261 ctest cases become 150 because the corpus carried an `rv32*` half for a machine this model can no longer be asked for.
    * Four findings. **The transplant forces this cut rather than merely profiting from it.** A register is a capability whose address field is the register width (R-15-007i), and the 128-bit encoding e2 ports has no 32-bit instantiation in this tree, so an RV32 configuration would be a machine with no capability format to run under; the first act of the transplant is therefore a deletion M0.6c did not reach. **Fixing XLEN changes the generated C++ interface, not only the model.** A configuration-dependent `bits(xlen)` is emitted as the length-carrying `sbits`, and a static one as a native `uint64_t`, so sixteen callback signatures in the emulator harness follow it, and the physical-address ones follow too because `physaddrbits_len` was conditional on XLEN as well; register, CSR, and PC values reach the harness as machine integers rather than as length-carrying structures. **`in32BitMode` was already unreachable and the enumeration under it nearly so**, which is the one-reachable-value rule c3 applied to `Privilege` and M0.6d to `InterruptType`, arriving here from the configuration rather than from a deleted mode. And **the RV32 half of the corpus was never evidence for this profile**: it exercised a base the profile does not have, so its removal costs no coverage, and every excluded RV64 row is still excluded for the reason it was.

  * [x] **e2 · Port the capability format and algebra** · 0.5 h actual · 0.1%
    * [cap_format.sail](../model/model/core/cap_format.sail) carries the field widths and the packed encoding; [cap_common.sail](../model/model/core/cap_common.sail) carries CHERI Concentrate over them: decode and encode, the null-capability memory transform, bounds, permissions, sealing, and the monotone derivations with their representability checks. 638 lines of Sail across three new files, the third being the unit test below, with the upstream licence vendored as `model/LICENCE.cheri` because the port derives from a BSD-2-Clause artifact this repository otherwise holds only as a submodule.
    * The capability layer lands in `core/` rather than under `extensions/`: the machine is purecap-only (R-15-001, R-18-002), so the capability *is* the register type, there is no hybrid mode to gate, and an extension gate would be a configuration key with one admitted value. The extension directory takes the instruction surface in e5.
    * Exit evidence: build green; 150/150 tests pass, and the eight properties in [test_capability.sail](../model/model/unit_tests/test_capability.sail) pass in the model's own `$[test]` harness: the all-zeroes granule decodes as untagged NULL and NULL stores back as all zeroes (R-15-182, R-15-060), encode and decode round-trip, the reset capability spans the address space, an aligned narrowing is exact and reads back, a five-byte narrowing is byte-exact (R-15-007c), an unrepresentable address move yields an untagged result rather than a trap (R-15-007h), sealing changes only the object type, and permissions round-trip.
    * Two findings. **The relocation guards are dead at the source and are not carried across.** `have_cheri_relocation` is a constant `false` upstream and both the PCC and DDC relocation paths hang off it, so the port folds them out rather than transplanting unreachable branches into a model that has no DDC to relocate. And **the tag plane needs no new machinery.** Sail 0.20's concurrency interface already carries a capability tag on its read and write requests, and the runtime the emulator links implements `emulator_read_tag` and `emulator_write_tag` behind it, so e3's tag memory is a parameter of the memory interface the curated tree already instantiates rather than the hand-wired side channel the upstream model carries.

  * [x] **e3 · Merge the register file and stand up the tag plane** · 0.5 h actual · 0.1%
    * `regtype` becomes `Capability`, so the file is merged by construction (R-15-007i): `X(r)` reads the address field, `C(r)` reads the whole register, and an integer write yields an untagged capability at that address, which is the merged file's discipline and the reason no capability is reconstructed from a bit pattern (R-05-136). Reset writes the null capability into all 31, because a machine whose registers hold authority cannot leave them undefined the way the base ISA leaves the integer file.
    * The validity tag becomes the metadata every physical access carries, keyed per granule, and the memory path needed no new plumbing for it: the modern tree already splits `mem_read_meta` from `mem_read` and `mem_write_value_meta` from `mem_write_value`, with the plain forms passing `default_meta`, so a data write clears the tag of every granule it covers for free, which is tag clearing as a property of the write path rather than an instruction (R-15-007r, R-15-115a).
    * Net change: 118 lines added over five files. Exit evidence: build green; 150/150 tests pass; four more properties in the model's `$[test]` harness, that an integer write clears the authority, that the two readings are one register, that `x0` reads null whatever is written to it, and that the tag plane is granule-keyed and cleared across a wide write.
    * Finding: **the granule keying is the model's to do.** The Sail runtime stores one tag per address it is handed, and the concurrency interface's own tag field is keyed by the access address, so nothing below the model rounds an address to a granule. `__WriteRAM_Meta` shifts the address down by the capability size and writes every granule the access spans, which is what makes a tag belong to a granule rather than to a byte, and what makes a wide vector store clear all of them rather than one.

  * [x] **e4 · Port the checks, PCC and sentries, and the trap capabilities** · 0.7 h actual · 0.1%
    * PCC authorises every fetch and control transfer and the base register authorises every data access, so no unchecked path remains. `MTCC`, `MEPCC` and `MTDC` are the architectural trap state (R-15-073): a trap installs MTCC as the executing PCC and saves the interrupted PCC in MEPCC, `mret` unseals a sentry out of MEPCC into the executing PCC (R-15-008, R-15-071), and the integer `mtvec` and `mepc` CSRs become views of those two addresses. A capability violation raises ISAv9's cause 28 and reports the violation type and the register that raised it in `mtval` (R-15-073a). Privilege becomes the capability: `ext_check_CSR` and the `mret` check both read the access-system-registers permission off PCC (R-15-003).
    * Net change: 402 lines added and 131 removed over 13 files, two of them new. The page-table-walk accumulator and its error types go with them: they described a walker deleted in c3.
    * Exit evidence: build green; 150/150 tests pass; the profile sweep is unchanged at 53 of 199; four more `$[test]` properties, that a trap saves PCC into MEPCC and installs MTCC, that `mret` unseals a sentry, that a fetch outside PCC's bounds and a fetch under an untagged PCC each raise their own violation, and that a store without store permission and a load through an untagged base register each fault where the access is rather than where the value was made.
    * Two findings. **The transplant cannot delete DDC on its own schedule, and the corpus is why.** Every test in `riscv-tests` addresses memory with an integer base register, so on a machine with no default data capability every load and store in the corpus faults at its base: the first build with DDC deleted hung five machine-mode tests on exactly that. Hybrid mode and DDC therefore stay until M0.6f, where the plan already puts their deletion, and the capability-mode arm beside them is the profile's own data path. What that schedules with it is M0.6f's exit criterion: after the cut, `riscv-tests` is not a corpus this machine can run, so the batch is gated on purecap test programs (M0.12) rather than on the suite that gates every batch before it. **The trap raise has to sit in the postlude.** A check is core surface because it reads PCC, but raising a trap calls the exception machinery in `sys`, which is compiled after `core`, so the three `ext_handle_*_error` hooks and the two privilege-failure hooks move to `postlude/cap_traps.sail`, the first point at which both halves are in scope.
  * [x] **e5 · Port the instruction surface and stand up the differential harness** · 3 h actual · 0.4%
    * The ISAv9 capability instructions land in `extensions/CHERI/`, ungated as the format and algebra in `core` are: the capability-mode control transfers (`auipcc`, `cjal`, `cjalr`) behind a second decode mapping, the two mode-independent jumps and `cinvoke`, the eleven inspection instructions, the monotone derivations with the three `csetbounds` forms sharing one narrowing, `cclear`, `cspecialrw` over the bank the profile keeps, the explicit-authority data loads and stores, the capability loads and stores, and `cloadtags`. 999 lines of Sail across two new files, plus the plumbing the second decode needs.
    * Three ISAv9 groups are **not** carried across, each because the machine no longer has what they act on rather than because the profile excludes them: `FPClear` clears a scalar floating-point file c4 deleted; `LoadRes*`, `StoreCond*`, and the sub-word `lr`/`sc` decodings ISAv9 adds to the base need a reservation c3 deleted with `Zalrsc`; and `AMOSwapCap` is a capability-width atomic swap where `A` is narrowed to `Zaamo` + `Zabha` at byte, halfword, word, and doubleword (R-15-024), so the width it names is not one the adopted atomic surface carries.
    * The differential rig is [tools/model.py](../tools/model.py) `trace-diff`, over the trace dialects and adjudication [tools/vos/trace.py](../tools/vos/trace.py) holds: either executor's dialect becomes one record stream, the two are aligned on the first program counter the curated model retires, and the report names where they stop agreeing. The record set is the intersection of what the two print today, a retire, a register-write address, and a data read.
    * Net change: 1,940 lines added and 35 removed across 13 files, six of them new.
    * Exit evidence: build green; 150/150 tests pass; the profile sweep is unchanged at 53 of 199; the ten new properties in [test_cheri_insts.sail](../model/model/unit_tests/test_cheri_insts.sail) pass, bringing the model's own harness to 28; and the rig runs the 54-member `rv64ui-p-*` corpus with an agreeing prefix of 97 records on every member.
    * Four findings. **The read path was discarding the tag.** e3 keyed the tag plane by granule and wired it into the write path, but `checked_mem_read` returned `default_meta` unconditionally, an upstream `TODO` about folding metadata across splits, so no capability could ever be loaded with its tag set; e5 is the first batch with an instruction that reads one, which is what surfaced it. The fold is now the conjunction over the splits, which for an unsplit access is that granule's tag exactly and for a split one is the conservative answer at the same polarity as the write path's clearing of every granule it covers. **`lc` collides with `cbo.zero`.** ISAv9 puts the capability load at MISC-MEM `funct3` 010 and the cache-block operations are there too, separated only by a zero destination and a small immediate; upstream never meets them because it does not implement `Zicboz`, which the profile adopts (R-15-060). The destination separates them here, a capability load into the null register discarding what it loaded, and the frozen dialect re-encodes this anyway (R-15-007), so what is owed at the freeze is a decision and not a repair. **The two executors neither start at the same instruction nor report a register write at the same width.** The oracle enters through a reset-vector ROM at 0x1000 this platform has no counterpart for, so the streams align on the first PC the curated model retires rather than on the step number; and the oracle prints the whole capability on a register write where this side prints the address alone, which [core/regs.sail](../model/model/core/regs.sail) already books as M0.12's to widen. The store side of the memory trace is not comparable at all, the oracle emitting no store line. And **`riscv-tests` cannot reach agreement past its own prologue, which is a fact about the corpus rather than about the transplant.** Each test points `mtvec` at the end of a group and then writes `medeleg`, which is an illegal instruction on a machine c3 stripped of delegation, so the trap skips the group the oracle retires and both machines reach the same result by different routes. The prefix is 97 on all 54 members, so the regression the rig carries today is that it must not *shorten*, which `--floor` enforces; a corpus both executors run in lockstep is M0.12's.
    * One refactor the surface forced, and it removes a duplicate rather than adding one: the explicit-authority loads and stores name their own authority where an ordinary access lets the mode pick it, so [core/addr_checks.sail](../model/model/core/addr_checks.sail) splits into `cap_mode_auth`, which selects, and `cap_data_checks`, which decides, with `ext_data_get_addr` composing the two.

* [x] **M0.6f · Re-parameterize to 64+1 bits** · 5 h actual · 0.6%
  * The format is [isa-profile.md](isa-profile.md) §4.1's and spends the 64 bits exactly: a 36-bit address in the low bits, a 4-bit object type, a 5-bit permission field, a 5-bit exponent, and 8- and 6-bit mantissas with the top's high two derived, the validity tag outside them and the tag plane's granule narrowing with the capability to 64 bits (R-15-007, R-15-002a, R-15-203). No reserved field, no software-defined permission field, no capability-mode flag, and no revocation colour appears, each needing a bit the table has already spent (R-15-007n, R-15-001c, R-08-004b).
  * **Permissions become an enumerated lattice rather than one bit per permission**, which is the one place the narrowing changes the algebra (R-15-007b). Bit 4 of the field is local versus global, orthogonal to authority; the other four name sixteen shapes, from the bottom element through the read and read-write data shapes, the three transitivity levels a capability load passes on, the stack's `store-local`, the execute shapes, the privileged code root, and the two sealing authorities. The decode is **total**, so the field has no illegal encoding to reject; the two lattice exclusions are finite checks over the table rather than properties of one distribution, no admitted set holding both store and execute (R-15-007l) and none holding both seal and unseal (R-15-007o); and what software sees is an *expanded* 12-bit bitmap, which is what lets `candperm`'s mask stay an ordinary bitwise operand over a non-orthogonal field, its result the largest admitted set inside the intersection. R-15-074's `load-global` and `load-mutable` transitivity arrives with the permissions that express it, applied on the load path and exact rather than rounded: the read half of every admitted set is itself an admitted set.
  * Removed with hybrid mode: `DDC` and its `cspecialrw` number, its `mtval` register index, the capability-mode flag with the second decode mapping and its `NOT_CAPMODE` wildcard, `cgetflags`/`csetflags`, the four explicit-authority data forms and the four explicit-authority capability forms, ISAv9's `cclear`, and the two mode-independent jumps. Removed on their own grounds: the reconstruction group (`cbuildcap`, `ccopytype`, `ccseal`, and the `cgethigh`/`csethigh` pair), the runtime bounds-rounding group (`cram`, `crrl`, `csetboundsexact`), `ctestsubset`, `ccleartag`, `cinvoke`, and the software-defined permission field. Six cause codes go with the mechanisms they named.
  * Net change: 1,125 lines added and 1,255 removed across 23 files, one deleted outright, `extensions/I/jalr_seq.sail`, whose one clause was the integer reading of `jalr`.
  * Exit evidence: build green; `verifiedos.json` validates against the regenerated schema and its key set agrees with the generated max configuration at 128 keys, unchanged, the re-parameterization touching no configuration key; and the model's own `$[test]` harness passes at **36 properties against 28**, thirteen of them new, covering the field budget, decode's totality over the encoding, the permission enumeration's totality and its two exclusions, narrowing's monotonicity over every codepoint and every single-bit mask, the split root set, the frozen object-type space, the out-of-range address, the sentry split at `cjalr`, and the load's transitivity.
  * Five findings.
    **The exponent field carries the case flag, because the table leaves no bit beside it.** CHERI Concentrate spends a bit saying whether the exponent is stored inside the mantissas; here the exponent is an explicit five-bit field, so the flag rides the field itself, IEEE-754 fashion: zero is the denormal case and *k* + 1 is the normalized case at effective exponent *k*. The effective exponent tops out at 30, so *k* + 1 tops out at 31 and the five bits are spent exactly. The packing is forced by the field table rather than chosen, and it costs no mantissa bits where upstream's costs three.
    **The byte-exact threshold the frozen widths deliver is 128 bytes and the padding above it is one part in 64 per side.** The exponent is chosen so the decoder knows the length mantissa's top two bits, which is exactly what lets the top mantissa be stored in six bits and derived into eight, so an exponent of zero reaches half the mantissa's span rather than all of it. R-15-007c's 256 bytes and one-part-in-256 read off the mantissa width alone and the normalization costs the factor. The model states what the widths give and holds it as a property; the figures are the register's to settle.
    **An integer register is 64 bits and an address is 36, so a register's integer reading is its whole 64 data bits.** The address field is their low 36, which is what keeps "an integer operand is that register's address field" true of every integer that *is* an address (R-15-007i, R-15-002a) and leaves the rest of the width to RV64I's arithmetic; the alternative reading would truncate every integer write to 36 bits and make the base RV36I. The null-capability transform the memory interface applies is applied to the register reading too, so `x0` reads integer zero and a register stored with `sd` and reloaded with `lc` is the capability it was. The one root is likewise a **pair**: W+X being unrepresentable, reset hands PCC the execute side and `c1` the store side, and the store side carries `store-local` because `candperm` can only remove (R-15-007p).
    **The corpus goes with DDC, and it goes entirely rather than family by family.** Every program in `riscv-tests` addresses memory with an integer base register, which a purecap machine reads as an untagged capability and faults on, so eleven extension-by-extension filters collapse into one ground and the suite is excluded from registration. The profile sweep, which asks a different question, still runs it and now returns 199 refusals of 199 against 53. The differential rig loses its second executor at the same edge and for the same reason M0.6e booked: an oracle is a reference only where it implements the same machine, and the prefix falls from 97 to 67 on all 54 members, which is the prologue's first load. The rig outlives the oracle; its standing second executor is M2's CHERI-QEMU fork and its corpus is M0.12's.
    **Membership is by enumeration, which reaches four instructions and one otype decision this item's own list does not name.** Nothing enters the profile by inheritance (R-15-007j), so `cinvoke` goes with the call gate `cjalr` replaces (R-15-068), ISAv9's `cclear` with the split file its two quadrants address (R-15-069b), and the two mode-independent jumps with the second mode that gave them a reason. The same rule decides the object-type space, which is frozen here: three of the sixteen codepoints are reserved, the unsealed one and **two** sentry edges, because R-15-071's forward/backward split is a reservation in that space and not a later amendment to it. `cjalr` enforces the split by role, a jump that writes a link entering only a forward edge and a return address reachable only by one that writes none, and `csealentry` mints the forward edge alone, so a return capability is never software's to forge.

* [ ] **M0.6g · Add profile rows absent upstream** · 15 h, range 10–20 · 1.9%
  * Add `cmovz`/`cmovn`, `cloadtags`, revocation filtering and bitmap, `fence.t`, capability indexed load/store, `cclear`, and the machine-level AIA pending array.
  * Do not model measurement-conditioned provisional rows yet. The single-check multi-register save is struck from the freeze set (R-15-036n) and is not modeled at all.

* [ ] **M0.6h · Add the three bespoke block instructions** · 6 h, range 4–8 · 0.8%
  * Add `vmclear` (R-15-069d), `creclaim` (R-15-007s), and `cbo.scrub` (R-15-177a): one Sail clause each, fixed-latency, on the constant-time list.
  * `vmclear` clears vector RF, vector CSRs, matrix state, and scratchpad per class; `creclaim` composes the load's revoked case with the `cloadtags` group read; `cbo.scrub` is architecturally a fixed-latency block pass with telemetry and fail-stop hooks.
  * None of the three is inherited from `sail-riscv` or `sail-cheri-riscv`, so each is net-new model surface with no upstream oracle; the differential harness takes the software equivalent instead, which each admission was shaped to leave trivial: a `cbo.zero` plus `cclear` loop for `vmclear`, `cloadtags` plus a capability load per tagged granule for `creclaim`, and ordinary loads through the ECC check for `cbo.scrub`.
  * Depends on M0.6g's revocation bitmap and CBO plumbing; lands after it.

#### Remaining M0 deliverables

* [ ] **M0.7 · Model Ztso and static-only prediction** · 3 h, range 2–4 · 0.4% · Parallel
* [ ] **M0.8 · Parameterize by core class** · 28 h, range 20–36 · 3.5%
  * Freeze C-class first; defer roughly 26 h of V/M/FEC work until needed before M2.3.
* [ ] **M0.9 · Add documented timing annotations** · 4.5 h, range 3–6 · 0.6% · Parallel
* [ ] **M0.10 · Generate and freeze the C-class golden emulator** · 2 h, range 1–3 · 0.3%
  * Exit: curated single-core emulator with ISA tests green.
* [x] **M0.11 · Define the profile-freeze measurement contract** · 2.5 h actual · 0.3%
  * [docs/freeze-measurement-contract.md](freeze-measurement-contract.md): six corpus members (`FM-1` to `FM-6`), a seven-step composition recipe, five operand classes and five admitted region classes with four enumerated refusal reasons, nine decisions (`FD-1` to `FD-9`) each carrying question, corpus, unit, procedure, threshold, default, and report columns, one report in two renderings generated from one record, eight declared parameters, and twelve CI predicates (`G-1` to `G-12`). Registered as a view in `tools/check.py`, so the requirements it must carry are checked in both directions.
  * Three methodological rules do the work, and each closes a way the measurement could be true and useless: bytes are **measured** on the encoder's output with R-15-036h/j reported beside them as a residual check rather than in place of them; the dictionary is **re-selected inside every variant**, a candidate instrument changing the histogram it would be scored against; and a **closing pass** at the admitted configuration produces the realized dictionary, so the frozen one is the machine's and not the sweep's.
  * Thresholds are derived where the register fixes the quantity and declared where it does not. Derived: 22.4 encoded bits per instruction, the optimistic `C` counterfactual at 70% of a 32-bit stream, which is R-15-036k's *p* = 0.804 expressed through the axis actually observed; **zero slot widenings** for outlining, since a partition's capacity is its slot width (R-07-032, R-07-037, R-15-036p); and for `rcstep`, that it move at least one tuple from refused to admitted, a decode ceiling being refused above rather than degraded through (R-15-238c). Declared, and collected in one table: two materiality floors keyed on what the choice costs, 0.5% of encoded text where it consumes custom opcode space and 0.1% where it only selects among forms of admitted instructions.
  * Three findings against §0's ordered act, all now corrected there. It named the single-check multi-register save/restore as a measured row, which R-15-036n strikes ahead of the freeze, so it is a nil row and a measured row against it is an amendment (`G-5`). It omitted two rows R-15-014a's closed delta carries, R-15-067e's further code-size candidate and R-15-031a's fusion set; the second is the one row whose admission is the deferred §15 exploration's, so the instrument owes it the emitted adjacency histogram and the report carries it as pending.
  * One narrowing of a delta item, stated rather than swept: R-15-036a carries the slot width as a DSE parameter, but a two-slot escape holding one canonical 32-bit instruction verbatim forces `2w ≥ 32`, and any wider slot wastes escape bits and buys index space above the profile's own 2^16 dictionary bound, so `w` = 16 and the knob is the `(h, k)` pair at `bundle = h + 16k` with `h ≥ k`. The delta item is unchanged; the search is smaller, and a report sweeping `w` is recognizable as covering a space the format does not admit.
* [ ] **M0.12 · Version the differential corpus and capability trace schema** · 4.5 h, range 3–6 · 0.6% · Parallel draft
  * Reuse preserved RVFI plumbing and finalize after M0.6e–g.

**M0 subtotal:** 93.6 h · 12% · 30.6 h complete · open range 43–83 h.

### M1 · Toolchain spine (incl. the CHERI-CompCert prerequisite)

Build the *functional* CHERI-RISC-V CompCert backend **first** (no purecap CertiCoq GC is needed, the on-device path is GC-free, §0), then bring up both roles, the host-side **CertiCoq → Wasm** oracle and the **GC-free on-device lowering** (CompCert-C/VST through CHERI-CompCert; arena extraction via MetaCoq→Rust onto the Rust→CHERI compiler for the allocation-light components), producing runnable purecap artifacts from a trivial Gallina program on the M0 emulator.
Ship the frozen-dialect **assembler, linker, and image composer** (§0) in the same milestone; nothing downstream links without them.
Build the profile-freeze analyzer and backend provenance outputs (§0), then publish its ordered dictionary, outlining, operand-form, bitfield, stack-save, and indexed-address reports against the generated corpus.
Every later milestone is purecap and managed-runtime-free from here.

* [x] **M1.1 · Locate and pin SECOMP2CHERI** · 0.5 h actual · 0.1%
  * `upstream/SECOMP` pinned at `5c20b839` (`ccs-main` head): the PriSC'23 abstract's `secure-compilation/CompCert` link redirects here (GitHub rename), so SECOMP2CHERI and the CCS 2024 SECOMP artifact are one repository, a CompCert **3.12** fork on the 64-bit RISC-V backend, permanently archived at DOI `10.5281/zenodo.11007678`; license is CompCert's (INRIA non-commercial for the core), a provenance fact the fork inherits.
  * Condition: alive, not abandoned (pushed June 2026; blame merged March 2026). Compartment-aware CompCert holds through every pass with the correctness proof adapted (admits confined to `Stackingproof.v` pending recent changes); recomposition and blame proofs complete; back-translation complete on `ccs-backtranslation`; the top-level RSCC theorem is formalized in `security/RSC.v` but not yet integrated with those three. Builds with Rocq 9.1 / OCaml 5.2.1 / Menhir.
  * Carried features, the CHERI half: the capability backend lives in-tree under `cheririscV/` (33 files: `CapAsm.v`, `CapAsmgen.v`, `CapAsmgenproof*.v`, capability memory model `CapMemory.v`, Georges-et-al calling convention with uninitialized/directed capabilities), emitted via `-dcapasm` with an admittedly incomplete pretty-printer; per the abstract it is "for the most part also implemented in Coq, but not yet fully integrated with CompCert and not verified". Branch `fix-cap-backend` (`1881ed0f`, June 2024) is 15 commits of unmerged backend work ahead; the 2022 `cheri-backend` branch is superseded.
  * Implication for M1.2: the artifact is usable, so the +20–40 h contingency is not triggered; the re-homing's real gap is the unverified, unintegrated capability backend and its ISAv8-lineage capability model versus the §4.1 64+1-bit purecap dialect, exactly the residual [inspirations.md](inspirations.md) states.
* [ ] **M1.2 · Re-home the backend to the purecap profile** · 37.5 h, range 25–50 · 4.7%
  * Functional and differential testing required; add 20–40 h if the artifact is unusable.
* [ ] **M1.3 · Add baseline target support and bound-directed lowering** · 12 h, range 8–16 · 1.5%
* [ ] **M1.4 · Re-home LLVM MC/`lld` and compose static images** · 22.5 h, range 15–30 · 2.8%
  * Exclude general dynamic linking.
* [x] **M1.5 · Run the CertiCoq-to-Wasm oracle** · 3 h actual · 0.4%
  * The loop closes end to end in a container ([tools/wasm-oracle/](../tools/wasm-oracle/)): `demo.v`'s `Nat.eqb (fib 20) 6765` compiled by `CertiRocq Compile Wasm` and run on stock Node prints `true`, the §0 inner loop with no cross-toolchain, no image, and no machine model involved.
  * Pin and condition: CertiRocq main carries the merged CPP 2025 CertiCoq-Wasm backend (`theories/CodegenWasm`, proven against WasmCert-Coq) that the 0.9 opam release predates, but its tip tracks the *unreleased* MetaRocq 9.1 branch on both sides of released 1.5.1, so the oracle pins the last pre-drift commit `4f53ca97` plus a two-site compat patch (the erasure inlining toggle moved into `unsafe_passes`). Rocq is 9.1.1 by CertiRocq's own `< 9.2~` constraint, not staleness, and it is the same prover version SECOMP states, so M1.2 shares this environment.
  * Environment findings, booked for later lanes: the oracle rides a container for the prover rather than for privilege. CertiRocq pins Rocq 9.1.1, and the host gate has since been moved onto that same version: [tools/proof-gate.py](../tools/proof-gate.py) compiled the shipped proofs with the distribution's Coq 8.20.1 until the `rocq-9.1.1` opam switch replaced it, so one prover version now serves the container and the gate. It is a switch of its own rather than a package in the Sail one because `rocq-core` caps dune below the version the Sail packages are built against; the two therefore still sit in separate places rather than on one PATH, which is why [tools/vos/env.py](../tools/vos/env.py) resolves the prover instead of assuming it. The privilege and toolchain gap that first argued for a container has since closed, the distribution carrying gcc 15.2.0 and running as root with no login user for `sudo` to matter to, and no container runtime is installed on this box in either the guest or the host, so a lane that wants one stands it up rather than finds it; the WSL VM idled out between commands and took containers with it, which turned out to be the stock WSL2 `vmIdleTimeout` (60 s after every instance stops) and not a runtime problem at all; the switch that disables it, `[wsl2] vmIdleTimeout=-1`, exists only in `%USERPROFILE%\.wslconfig`, global to every distribution and permanent until a human deletes it, so on 2026-08-19 the fix was scoped into the repository instead: every loop in [tools/model.py](../tools/model.py) starts a detached, idempotent, self-expiring keepalive (8 h default, `VOS_KEEPALIVE_HOURS=0` opts out, `model.py keepalive --stop` ends one early), which holds one instance up so the timer never starts and leaves nothing behind when it lapses; the Docker lanes take the same lease directly (`wsl -u root -e python3 tools/model.py keepalive`), and the `certicoq-oracle` container keeps `--restart unless-stopped` for teardowns that happen anyway; and Cisco Umbrella re-signs `release-assets.githubusercontent.com`, so the Windows-exported proxy root CA must be installed into any Linux trust store that fetches GitHub release assets.
  * WSL Containers (`wslc.exe`) evaluated and declined on 2026-08-19, revisit at GA: Microsoft's in-box container runtime is Docker-shaped, unlicensed, and runs in its own session VM whose memory returns to the host, but it needs WSL ≥ 2.9.3 from the pre-release channel (this box is 2.7.11), it is public preview with GA targeted for fall 2026, and it moves the wrong finding. The idle-out was never a runtime problem, and on the proxy it regresses: [microsoft/WSL#40945](https://github.com/microsoft/WSL/issues/40945) (open, filed 2026-06-29 against 2.9.3) reports the `wslc` backend session VM receives *no* proxy environment, `wslc system session run env` returns only `PATH` where an ordinary distro at least gets `http_proxy`, and Windows root CAs still do not propagate into any Linux store, so the registry pull happens in a session VM this lane cannot reach with the Umbrella CA and the documented workaround is to pull in a distro and `wslc load` the tar. Preview also lacks Compose and `build --platform`, and does not support build contexts on the WSL filesystem (immaterial here: [tools/wasm-oracle/](../tools/wasm-oracle/) builds from the Windows side). The live reason to revisit is idle memory, not container lifecycle.
* [ ] **M1.6 · Stand up GC-free lowering routes** · 18.5 h, range 12–25 · 2.3% · Parallel with M1.4
* [ ] **M1.7 · Boot purecap Gallina hello-world on the M0 emulator** · 9 h, range 6–12 · 1.1%
* [ ] **M1.8 · Build and wire the profile-freeze analyzer** · 11.5 h, range 8–15 · 1.4% · Parallel

**M1 subtotal:** 114.5 h · 14% · 3.5 h complete · open range 74–148 h.

### M2 · Fast emulator

The CHERI-QEMU fork (§10), curated to the frozen profile: corpus-lockstep green against the M0 emulator, and booting M1's purecap hello-world as its exit test.
It gates on M0, not M1, so it proceeds in parallel with the toolchain spine; from here it is the daily driver and the Sail emulator is the CI cross-check.

Gate M2.2–M2.3 on measured Sail-emulator performance. If Sail is sufficient through M6, defer approximately 35 h beyond M8.

* [ ] **M2.1 · Fork CHERI-QEMU and narrow compressed capabilities** · 7.5 h, range 5–10 · 0.9% · Parallel
* [ ] **M2.2 · Implement the frozen decode surface and bespoke machine** · 12 h, range 8–16 · 1.5%
* [ ] **M2.3 · Add VLEN=4096 RVV, matrix, and FEC datapaths** · 30 h, range 20–40 · 3.8%
* [ ] **M2.4 · Reach corpus lockstep with M0 and boot M1 hello-world** · 9 h, range 6–12 · 1.1%

**M2 subtotal:** 58.5 h · 7% · open range 39–78 h.

### M3 · Boot chain

RoT core + firmware (§2), M-mode firmware (§3), crypto core (§4) → both emulators reach the Machine-mode kernel.

* [ ] **M3.1 · Add RoT configuration and peripherals to the curated Sail tree** · 18 h, range 12–24 · 2.3%
  * Reuse the same model tree with a scalar `verifiedos-rot.json`; do not fork another model.
* [ ] **M3.2 · Implement RoT firmware in Gallina** · 22.5 h, range 15–30 · 2.8%
* [ ] **M3.3 · Implement M-mode firmware in Gallina** · 18 h, range 12–24 · 2.3%
* [ ] **M3.4 · Integrate verified cryptographic artifacts** · 26.5 h, range 18–35 · 3.3%
  * Prefer pinned upstream verified implementations over fresh authoring.
* [ ] **M3.5 · Reach the machine-mode kernel through measured boot on both emulators** · 11.5 h, range 8–15 · 1.4%

**M3 subtotal:** 96.5 h · 12% · open range 65–128 h.

### M4 · Kernel

Gallina microkernel (§5), one instance per emulated core; capability/IPC tests green host-side (Wasm) and on-emulator (RV64, both machines).

* [ ] **M4.1 · Decide revocation sweep quanta** · 1.5 h, range 1–2 · 0.2% · Parallel
* [ ] **M4.2 · Translate surviving seL4 executable-spec objects to Gallina** · 22.5 h, range 15–30 · 2.8%
  * Time-box `hs-to-coq` recovery to eight hours, then hand-translate if necessary.
* [ ] **M4.3 · Exercise capability lifecycle, IPC, and slot faults through Wasm** · 9 h, range 6–12 · 1.1%
* [ ] **M4.4 · Bring up one isolated C instance per emulated core** · 26.5 h, range 18–35 · 3.3%

**M4 subtotal:** 59.5 h · 7% · open range 40–79 h.

### M5 · Storage and objects

Journal/index/FS (§7) and the content-addressed object store + transactor (§6); system-integrity instance first, then user-data.

* [ ] **M5.1 · Implement the L0 journal and L1 CoW B-tree in Gallina** · 21.5 h, range 15–28 · 2.7%
* [ ] **M5.2 · Compose L2 semantics and L3 confidentiality host-side** · 14 h, range 10–18 · 1.8%
* [ ] **M5.3 · Run system-integrity and user-data instances on the emulator** · 12 h, range 8–16 · 1.5%
* [ ] **M5.4 · Implement the object store and update transactor** · 18 h, range 12–24 · 2.3% · Parallel where possible

**M5 subtotal:** 65.5 h · 8% · open range 45–86 h.

### M6 · Userland spine

Init/supervision tree (§8) brings up the reference components; admission checker (§9) validates the package set; the package composer emits the finite typed handler/translator graph and pre-admitted media templates, and the contained object router exercises private namespaces, intents, live queries, deterministic translation caching, and protocol-bound credential handles over the existing IDL and rings.
The ring data plane is brought up in its contract order: the common ring schema and lifecycle authored in the IDL profile with the reference client/server bindings and Coq interface skeleton generated from it, then one copy-based service carrying the SPSC, notification, and capacity proofs, then one DMA service adding the extent, cancellation, teardown, and quiescence proofs, so the contract's constants and generated-proof interfaces are validated on two real services before every other server rides them. No service is grandfathered: one that cannot state its finite capacities, lifecycle semantics, cleanup bounds, and per-operation WCET is not admitted through the ring profile.

* [ ] **M6.1 · Build the init supervision tree in Lustre via Vélus** · 15 h, range 10–20 · 1.9%
* [ ] **M6.2 · Refine admission checkers to CompCert-C** · 26.5 h, range 18–35 · 3.3%
* [ ] **M6.3 · Build the package composer and contained object router** · 15 h, range 10–20 · 1.9%
* [ ] **M6.4 · Author the ring-contract schema and generate the reference bindings** · 9 h, range 6–12 · 1.1%
  * The common ring schema and lifecycle in the IDL profile (R-12-091 through R-12-101), with the reference client/server bindings and the Coq interface skeleton generated from it.
* [ ] **M6.5 · Port one copy-based and one DMA service through the ring contract** · 22.5 h, range 15–30 · 2.8%
  * The copy-based service carries the SPSC, notification, and capacity proofs; the DMA service adds extent, cancellation, teardown, and quiescence; together they validate descriptor sizes, completion capacity, and the generated-proof interfaces (R-18-037) before other servers ride the contract.

**M6 subtotal:** 88 h · 11% · open range 59–117 h.

### M7 · Full emulated system

The composed stack boots in the spec's §9 order on the **fast emulator**, the plan's intermediate goal; the composed Sail emulator (§10) re-runs the same boot as the golden cross-check; the Wasm track keeps running the same components host-side for iteration.
The composed system is also the first artifact able to measure **allocation churn**, so the measurement is booked here: the static-composition low-churn argument and the static-code-overlay deferral both wait on the same measured roster, and the elective applications widen the measurement later rather than gating it.
The same roster carries the ring-parameter measurement: queue depths, batch sizes, notification cadence, and slot budgets are read off the composed system against the §12 per-operation accounting, so the contract's constants are chosen from a measured roster rather than estimated per service.

* [ ] **M7.1 · Boot the composed stack on the fast emulator and rerun it under Sail in CI** · 22.5 h, range 15–30 · 2.8%
* [ ] **M7.2 · Measure allocation churn across the composed roster** · 4.5 h, range 3–6 · 0.6%
* [ ] **M7.3 · Measure ring parameters across the composed roster** · 4.5 h, range 3–6 · 0.6%
  * Queue depths, batch sizes, notification cadence, and slot budgets read off the composed system against the §12 per-operation accounting.

**M7 subtotal:** 31.5 h · 4% · open range 21–42 h.

### RTL track

The RTL track, in parallel from the M0 freeze:

* [ ] **R1 · Curate scalar CVA6-CHERI RTL and required platform devices** · 45 h, range 30–60 · 5.6%
  * CVA6-CHERI re-parameterized to the 64+1-bit dialect and curated per the profile and absence contract (§11: MMU deleted, static-only prediction, TSO store buffer), plus the RoT core, tag-carrying interconnect, boot ROM, UART, and block device; absence-contract state enumeration and synthesis-configuration provenance recorded at first elaboration.
* [ ] **R2 · Reach corpus-green Verilator co-simulation with trace diff and BMC smoke** · 22.5 h, range 15–30 · 2.8%
  * The shared corpus passes under Verilator with the commit-trace diff against the golden model, `rvfi` the hook; a riscv-formal-style BMC smoke on the curated scalar core runs here as cheap bring-up evidence (R-15-094), distinct from the deferred FEV and refinement work.
* [ ] **R3 · Boot the image in co-simulation and publish the versioned RTL artifact** · 15 h, range 10–20 · 1.9%
  * The composed purecap image (M7's) boots on the RTL in Verilator to the same console and event digests as both emulators; the **RTL artifact of record** (§11) is versioned and published.

**RTL subtotal:** 82.5 h · 10% · open range 55–110 h.

### M8–M10 and later

* [ ] **M8 · MVP gate: M7 and R3 complete** · 3 h, range 2–4 · 0.4%
  * M7 and R3 together: the whole base system running in emulation, and the RTL artifact of record in hand, corpus-green and booting the same images in co-simulation.
  * This is the plan's most important milestone; everything after it is hardware realization and hardening.
* [ ] **M9 · Synthesize and boot scalar purecap on FPGA** · 30 h, range 20–40 · 3.8%
  * Synthesize the R3 artifact for the board (§11); the purecap golden-model images (M1–M7) boot on it directly, differentially tested against M7; CHERI ISA tests from the Sail model green on the FPGA.
* [ ] **M10 · Extend CHERI checks across V/M/FEC datapaths** · 45 h, range 30–60 · 5.6%
  * Extend the V/M/FEC datapaths to capability checks (the genuine new RTL, §18), the scalar core and purecap software are already in hand from M1/M9, so the FPGA then matches the golden model across all core classes.

Everything past M10, the CHERI-CompCert **secure-compilation criterion** (robust preservation; the *functional* backend already landed in M1), the **R-05-023a validation instrument** (the decompilation-into-logic producer of the §5 post-CompCert records, whose first non-fast-path artifact also opens the checker-binary question booked in [architectural-alternatives.md](architectural-alternatives.md)), the binary-level constant-time verifier, the masking obligations (the *d*-probing and composition theorems on the crypto artifacts with the Coco-class netlist discharge, R-05-004a, R-15-053a, §4), the R-16-008f detection theorem, the certifying-Rust *certificate* mode, the full VST refinement proofs, WCET, and RTL ⊑ Sail refinement, is the hardening program of §5/§6/§18, each piece replacing a golden-model component *in place* and checked against the reference this plan produces.
One statement is owed at that program's opening rather than inside it: the RTL ⊑ Sail arrow is the least-built layer of the stack (R-17-039) and the hedge deletions spend it (R-17-037), so the program starts by writing the fallback position, what each of the PMP-backstop, IOMMU, MTE, shadow-stack, and initialization-plane rejections becomes if the refinement lands late or partially, so the schedule risk is stated where it is spent.
Two more are owed at the same opening: the combined-adversary route is already selected (R-17-058d, the ineffective-fault countermeasure carried into the masked datapath, its combined claim a reduction theorem spending the two stated axioms), so what the opening states is that theorem's verification plan beside the masking obligations rather than a choice (critique work-list item 29 carries the remaining Coq costing); and the R-15-053a bring-up characterization, its stated limits and per-structure micro-benchmarks, is rehearsed on the FPGA and executed at first silicon, the rehearsal validating the harness and never the axiom, an FPGA's leakage being the wrong silicon.

* [ ] **Post-M10 · Publish opening hardening obligations** · 8 h, range 6–10 · 1.0%
  * State the RTL-to-Sail fallback, reduction-theorem verification plan, masking obligations, and first-silicon characterization plan.

**M8–M10 subtotal:** 86 h · 11% · open range 58–114 h.

## Build-loop instruments

These items sit outside the milestone subtotals but inside the grand total, and each carries its own estimate cell like any other item. Every change must be benchmarked before adoption; canonical `-O2` RelWithDebInfo remains the exit criterion.

* [x] **Initial check/emit/FAST tooling** · 0.9 h actual · 0.1%
* [x] **I0 · Standardize the tools on one language** · 6 h actual · 0.8%
  * Every tool in [tools/](../tools/) is Python 3.14, the one interpreter both lanes carry: the host has no `bash` and the WSL guest no `pwsh`, so three languages could not be reduced any other way. The shell prelude's two load-bearing tricks survive the move and improve: the OCaml stack the Sail emission needs is `resource.setrlimit` in the parent rather than `ulimit -s`, and a stage's cost is `os.wait4` on the child that was asked about rather than `/usr/bin/time` reporting the running maximum over every child so far.
  * Shared parses move into `tools/vos/` and the checker's fifty rules into one module per group, so no fact is parsed twice; the entry points collapse from sixteen to five, the four model loops and the trace rig becoming subcommands of [tools/model.py](../tools/model.py). [tools/README.md](../tools/README.md) states the lane rule, the conventions, and the three edits a new rule costs.
  * Exit evidence: the checker's output is unchanged line for line except where it now names the package rather than a file, and it runs in 0.95 s against 2.2 s; the mutation selftest kills all 50 mutants in 19 s against 129 s; `model.py build` is green at 150/150 with the same `ALL_DONE` marker; `sweep` returns the same 146/52/1 of 199; `trace-diff --corpus` returns the same 54 prefixes at 97 in 2.2 s against 7.1 s; and the proof gate returns the same 19 constants closed.
* [ ] **I1 · Move sources to WSL ext4 and uncap local parallelism** · 2 h, range 1–3 · 0.3%
  * Move the checkout to `~/src/VerifiedOS`, use Remote-WSL, set `ctest -j$(nproc)`, and avoid cache-hostile WSL memory reclamation.
* [ ] **I2 · Use one shared content-keyed SMT memo cache** · 2.5 h, range 1–4 · 0.3%
* [ ] **I3 · Benchmark a current z3 binary on a cold emission** · 1.5 h, range 1–2 · 0.2%
  * The choice half has now landed twice: the toolchain ran z3 **4.13.3** as Ubuntu 26.04 ships it, where the item was written against 4.8.12, and runs a pinned **5.1.0** since M0.2. The measurement half is answered for the typecheck and still open for the emission. A cold typecheck of the curated model is 44.5 s and 48.2 s over two repeats under 4.13.3, against 46.9 s and 59.3 s under 5.1.0; warm, 5.7 s and 8.0 s against 5.5 s and 5.8 s. All four runs are green and the caches are stable at 92 KB and 76 KB. The spread between repeats of one solver is wider than the gap between the two, so the honest reading is that this workload does not separate them and no time is bought either way: the move stands on the pin, not on speed. The ~25 min cold against ~2 min warm that [tools/model.py](../tools/model.py) quotes was taken under 4.8.12, and no cold *emission* has been timed under either current solver.
* [ ] **I4 · Add shared ccache, then emit only when generated output changes** · 2 h, range 1–3 · 0.3%
  * The ccache half has landed, and like I3's it was the half that was a choice rather than a measurement: the binary is installed and [tools/vos/env.py](../tools/vos/env.py) puts the two compiler launchers on every configure when it finds one, against a `CCACHE_DIR` shared by every build tree, with no `CCACHE_SLOPPINESS` set on purpose, a false hit in a build whose output is a verification oracle not being worth the hit rate. What is open is the second clause, which is the larger one: a regeneration that produces byte-identical C++ still pays for the compile that follows it, and that compile is the 150 s single-threaded unit the emission's critical path already ends in.
* [ ] **I5 · Benchmark generated-TU flags, clang versus gcc, and mold** · 2 h, range 1–3 · 0.3%
* [ ] **I6 · Benchmark the same Sail 0.20.2 binary built with flambda** · 1.5 h, range 1–2 · 0.2%
* [ ] **I7 · Run canonical builds in the background and standardize worktree lanes** · 1.5 h, range 1–2 · 0.2%
* [ ] **I8 · Optionally move quick checks to push CI and canonical tests to nightly CI** · 1.5 h, range 1–2 · 0.2%

**Instrument subtotal:** 21.4 h · 3% · 6.9 h complete · open range 8–21 h.

## Estimate and schedule basis

* Completed estimates are actual elapsed session intervals with overlapping build waits apportioned approximately.
* Open work classes:
  * A · pinning, configuration, and mechanical curation
  * B · semantic porting and tool re-homing with differential tests
  * C · fresh systems authoring with functional tests
  * D · RTL and FPGA work
* Confidence: every open item's range spans roughly a factor of two about its midpoint, and a class believed softer is priced by widening its own items' ranges rather than by a second figure stated over the total.
* Grand total: the sum of the item cells, 797.5 h midpoint over a 548–1,047 h range.
* Planned optimizations remove roughly 32 h from the midpoint; measured gating may move another approximately 35 h beyond M8.
* At 10–20 attended hours per week across two or three lanes, M8 is approximately 5–10 months away. Review capacity, not lane count, is the constraint beyond three lanes.
