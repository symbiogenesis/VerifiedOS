# Atomic Requirements Register

*Normative. This register — not the prose — is the artifact the §5 independent-specification-review release gate audits. [verification-maximal-os.md](verification-maximal-os.md) is its rationale and commentary.*

**Status: complete. All eighteen normative sections are extracted.** Until coverage is complete the review gate cannot be claimed as met — see [Coverage](#coverage).

## How to read this

Each entry is one atomic obligation, individually reviewable, with an acceptance criterion that decides it without reference to the prose. Per [§5](verification-maximal-os.md#L413), *a normative claim that cannot be restated as an atomic, testable requirement is a spec defect, not prose to be admired*; claims that resisted restatement during extraction are booked in [Extraction defects](#extraction-defects) rather than silently dropped or paraphrased into something testable that the spec does not actually say.

```
**R-ss-nnn** MUST — the obligation, stated so that a reviewer can agree or disagree with it alone
· Accept: what a reviewer, auditor, or tool checks to decide the obligation is met
· Trace: CJ-… (the crown-jewel spec it constrains) · Lnnn (prose rationale)
```

**Modality.** `MUST` — obligation on the built system or its process. `MUST NOT` — prohibition; the acceptance criterion is an emptiness or absence check. `IS` — a definition or classification the rest of the register quantifies over; reviewable for correctness, not for compliance.

**IDs are permanent.** A retired requirement keeps its number and is struck, never reused. Renumbering breaks every review record that cites it.

### Crown-jewel specs referenced

| ID | Spec |
| --- | --- |
| `CJ-T` | The apex theorem T: whole-system robust non-interference modulo declassification, on silicon (§5) |
| `CJ-SAIL` | The CHERI-RISC-V Sail model: ISA semantics, incl. its timing and leakage annotations (§15) |
| `CJ-RTL-SAIL` | RTL ⊑ Sail, functional and hyperproperty halves (§15, §18) |
| `CJ-TAL-SOUND` | CHERI-TAL soundness metatheorem: well-typed ⇒ safe over the Sail model (§5) |
| `CJ-CT-SOUND` | Constant-time type-soundness metatheorem over the §15 leakage model (§5) |
| `CJ-LEAK` | The `Zkt`/`Zvkt` leakage model (§15) |
| `CJ-WCET` | The timing-annotated Sail model and the derived per-(class, operating-point) bounds (§5, §11, §15) |
| `CJ-COMPCERT` | CHERI-CompCert correctness (§5, §6) |
| `CJ-SECOMP` | Robust preservation of compartment isolation by the verified compiler (§5) |
| `CJ-KERNEL` | Kernel functional refinement: seL4's design re-proved in Coq (§7) |
| `CJ-NI` | Explicit-flow non-interference over the capability topology (§8) |
| `CJ-CERISE` | The Cerise universal contract (§13) |
| `CJ-MEMPLAN` | §7's static whole-program slot plan and its live-range colouring |
| `CJ-CRYPTO-SPEC` | Each primitive's abstract functional specification (§5) |
| `CJ-REDUCTION` | The IND-CCA / EUF-CMA reductions (§5) |
| `CJ-FORMAT` | The Narcissus format descriptors (§5, §12) |
| `CJ-VELUS` | Vélus correctness and the Lustre control programs (§5, §12) |
| `CJ-HAL` | The verified HAL's hardware contracts and DMA/descriptor postconditions (§5, §12) |
| `CJ-IDL` | The §12 IDL wire-format mapping |
| `CJ-DEVTREE` | The RoT-attested devicetree (§9) |
| `CJ-ISOL` | The formal isolation semantics of the §15 partitioning hardware |

---

## §1 — Goals

**R-01-001** IS — G1: minimal attack surface.
· Accept: every element of the specification shrinks the TCB, deepens its proof, or contains the non-TCB (R-04-001).
· Trace: CJ-T · [L22](verification-maximal-os.md#L22)

**R-01-002** IS — G2: defense in depth — compromising any non-TCB component yields only its explicitly granted authority.
· Accept: the property is discharged by the compose-time capability topology plus CHERI containment; it is the quantifier over adversary sets *C* in theorem T (R-05-156).
· Trace: CJ-T, CJ-CERISE · [L23](verification-maximal-os.md#L23)

**R-01-003** IS — G3: end-to-end formal verification from abstract spec through source, binary, ISA, and modeled hardware to RTL, with RTL ⊑ Sail a named in-scope mechanization workstream rather than a bare trust assumption.
· Accept: the RTL of record is authored in Kami/Kôika, with riscv-formal/rvfi the bring-up gate and Isla the obligation bridge; below it, fabricated silicon versus verified RTL is the irreducible fab residual.
· Trace: CJ-RTL-SAIL · [L24–25](verification-maximal-os.md#L24)

**R-01-004** IS — G4: stateless, atomic, transactional, rollback-friendly.
· Accept: discharged by the immutable content-addressed image plus enumerated mutable volumes (R-10-026) and the A/B transactor (R-11-001).
· Trace: CJ-DEVTREE · [L26](verification-maximal-os.md#L26)

**R-01-005** IS — G5: reliability through fault isolation, crash-only components, and health-gated recovery.
· Accept: discharged by §16.
· Trace: CJ-KERNEL · [L27](verification-maximal-os.md#L27)

**R-01-006** IS — Performance is subordinate to security and pessimism is free by axiom; this is the tie-break the no-tightening rule and the design-space exploration both invoke.
· Accept: every trade recorded as "spent on the free axis" cites this goal ordering.
· Trace: CJ-T · [L22–27](verification-maximal-os.md#L22)

---

## §2 — Non-Goals

**R-02-001** MUST NOT — There is no POSIX or Linux compatibility in any form: no `fork()`, no uid/gid, no ambient authority, no Linux-personality shim, and no legacy VM.
· Accept: software runs natively against the capability substrate or it does not run; there is no ambient-authority pocket universe anywhere on the machine.
· Trace: CJ-CERISE · [L118–119](verification-maximal-os.md#L118)

**R-02-002** IS — There is no broad hardware support: a curated allowlist only.
· Accept: the allowlist collapses toward transducers and register slaves (R-04-009).
· Trace: CJ-CERISE · [L120](verification-maximal-os.md#L120)

**R-02-003** IS — There is no fixed form factor: laptop, phone, IoT, workstation, and server instantiations share the principles and only the physical particulars vary. The reference instantiation is a mobile/laptop device.
· Accept: a form factor lacking a peripheral simply omits it; the privacy cutoffs are driven by lockout on every form factor and additionally by the away-gesture where one exists.
· Trace: CJ-DEVTREE · [L121–122](verification-maximal-os.md#L121)

**R-02-004** IS — There is no performance parity: in-order cores, no SMT, no JIT, no dynamic speculation, no dynamic branch prediction. Throughput lands in 2010s-iGPU / early-NPU / LTE-class-modem territory by design.
· Accept: rendering, AI, and radio signal processing run on general-purpose vector and matrix cores under the same ISA and proofs; there is no fixed-function GPU, no discrete accelerator, and no opaque coprocessor.
· Trace: CJ-SAIL · [L123–125](verification-maximal-os.md#L123)

**R-02-005** MUST — Instruction-level parallelism is bought only from static, exposed mechanisms — wide in-order issue, decoder-stage macro-op fusion, RVV — never from mechanisms creating hidden speculative microarchitectural state.
· Accept: consistent with R-15-010 and R-15-031.
· Trace: CJ-SAIL · [L126](verification-maximal-os.md#L126)

**R-02-006** MUST NOT — There is no legacy: no BIOS/MBR, UEFI, ACPI, IPv4, 32-bit modes, or compressed-instruction ambiguity.
· Accept: each is absent from the profile and the model.
· Trace: CJ-SAIL · [L127](verification-maximal-os.md#L127)

**R-02-007** MUST NOT — Proprietary firmware black boxes, named exhaustively in the §12 topology table, are excluded by platform mandate and not mitigated.
· Accept: the exclusion list is the topology table's fourth class (R-12-004).
· Trace: CJ-CERISE · [L128](verification-maximal-os.md#L128)

---

## §3 — Threat Model

**R-03-001** IS — The defended set is enumerated: remote network attackers including hostile radio infrastructure; hostile web content; malicious or compromised apps, servers, and drivers; malicious DMA peripherals and counterfeit or spoofed wired peripherals and cables; evil-maid physical access; forensic extraction of a device seized after at least one unlock; coerced unlock (duress); and software supply-chain attack in both its tampering and subversion forms.
· Accept: each defended item names the mechanism that answers it and the section that specifies it.
· Trace: CJ-T · [L134](verification-maximal-os.md#L134)

**R-03-002** IS — Covert activation of the microphone, camera, or radios by compromised software or firmware, and use of the wired port in a deliberately-hostile environment, are additionally countered by user-controlled cutoffs beneath the capability-gated per-app access.
· Accept: the cutoffs are the sealed Hall-effect switches and the mechanical camera shutter (R-15-145, R-15-152).
· Trace: CJ-T · [L135](verification-maximal-os.md#L135)

**R-03-003** IS — The electromagnetic environment is in scope: radiated and conducted EMI and electromagnetic fault injection are countered by the Faraday enclosure with residual faults caught by fixed-latency ECC and the fail-stop path; single-event upsets are deliberately *not* shielded but detected, corrected, or contained, with their rate cut at the source by a radiation-hardened realization where the deployment warrants.
· Accept: consistent with R-15-153 through R-15-157.
· Trace: CJ-T · [L137](verification-maximal-os.md#L137)

**R-03-004** IS — The residual set is enumerated: timing channels beyond the transient-execution and DVFS classes; specification errors; the proof-tool trust base; invasive physical attack; malicious silicon fabrication; and carrier or certification-body acceptance of an open cellular stack.
· Accept: each maps to a §17 entry. **See [D-05](#d-05).**
· Trace: CJ-T · [L139](verification-maximal-os.md#L139)

**R-03-005** IS — Invasive physical attack is the only way to reach main memory at all, main memory being on-die, so delidding and probing is the entry price; the line is what scopes the memory path in §15, and drawing it elsewhere would make every on-die interface a defended one.
· Accept: the scope line is load-bearing and is booked as such (R-17-059).
· Trace: CJ-T · [L139](verification-maximal-os.md#L139)

---

## §4 — Organizing Principle

**R-04-001** MUST — Every element of the specification must shrink the TCB, deepen its proof, or contain the non-TCB.
· Accept: an addition meeting none of the three is inadmissible.
· Trace: CJ-T · [L145–146](verification-maximal-os.md#L145)

**R-04-002** IS — Two orthogonal security properties are both required: capabilities control *access* and information-flow control governs *propagation*, each blind to the other.
· Accept: static composition is the structural prerequisite for proving both — a fixed component graph has a fixed capability topology *and* a fixed flow policy, over which one non-interference theorem can be stated.
· Trace: CJ-NI, CJ-CERISE · [L148–152](verification-maximal-os.md#L148)

**R-04-003** IS — A compartment is a bounded set of code and data holding exactly the capabilities its manifest grants and no others, isolated from every peer by CHERI capabilities alone, sharing the one physical address space with no ring, no MMU, and no separate address space.
· Accept: a boundary costs neither a page table nor a mode switch.
· Trace: CJ-CERISE · [L154–156](verification-maximal-os.md#L154)

**R-04-004** MUST — The only path between two compartments is a sealed entry point through the switcher, which saves and restores the caller and, through the local/global capability discipline, bounds a delegated buffer to the call so authority cannot be captured past it.
· Accept: consistent with R-15-068 and R-15-074.
· Trace: CJ-CERISE · [L157](verification-maximal-os.md#L157)

**R-04-005** IS — The structure is universal: the kernel is the sole privileged resident and every other thing on the machine is a compartment — every server, driver, and filesystem, the network and radio stacks, every app, and every browser origin — each pre-composed at build time.
· Accept: even the userland-resident TCB exceptions (powerbox, trusted-path agent) are confined like a server, and the verified HAL is a non-TCB compartment.
· Trace: CJ-CERISE · [L158–160](verification-maximal-os.md#L158)

**R-04-006** IS — Compartments nest: an app is one least-authority compartment at its edge, and its manifest may declare an internal compartment graph whose library sub-compartments each carry their own sub-manifest. Nesting is not a second mechanism — a sub-compartment is one more node in the same flat, machine-checked component graph.
· Accept: no new object class appears for nesting.
· Trace: CJ-CERISE · [L161–163](verification-maximal-os.md#L161)

**R-04-007** MUST — Every app is at least one memory-safe, capability-confined compartment; internal sub-compartmentalization is mandatory for any dependency that parses attacker-controlled input or is handed authority beyond pure compute, and available otherwise as compose-time authority minimization.
· Accept: the mandatory population is checked at admission against the manifest (R-13-024).
· Trace: CJ-CERISE · [L164–165](verification-maximal-os.md#L164)

**R-04-008** MUST — Every compartment is fixed at composition: no compartment is created and no privilege minted at runtime, the one sanctioned runtime authority transfer being a powerbox declassification that extends the live edge set without adding a compartment or a privilege class.
· Accept: sandboxes, containers, enclaves, and permission subsystems are obviated by construction, not reimplemented.
· Trace: CJ-NI, CJ-KERNEL · [L166–168](verification-maximal-os.md#L166)

**R-04-009** MUST — Heterogeneity lives in the datapath, never in the trust structure: every core class shares the base ISA, the purecap capability model, the kernel binary, and one parameterized formal model, differing only in datapath execution resources.
· Accept: anything that cannot be expressed as an ISA-visible, Sail-modeled, capability-checked extension of a core is not admitted as compute.
· Trace: CJ-SAIL · [L170–172](verification-maximal-os.md#L170)

**R-04-010** MUST — No foreign computers: the platform contains exactly one computer, the multikernel die. Every function conventionally delegated to a firmware-running coprocessor is dissolved into software on disciplined cores, reduced to a fixed-geometry arithmetic unit, reduced to firmware-free device RTL behind capability-checked DMA, or reduced to a transducer or register slave.
· Accept: a component that fetches and executes instructions outside this discipline does not go on the die or the board.
· Trace: CJ-CERISE · [L174–177](verification-maximal-os.md#L174)

**R-04-011** IS — The single tolerated exception is the eUICC, a carrier-mandated foreign trust domain contained as a register-slave crypto oracle with zero platform authority.
· Accept: the exception count is one (R-12-045).
· Trace: CJ-CERISE · [L178](verification-maximal-os.md#L178)

**R-04-012** IS — The consequences are stated: the device allowlist collapses toward transducers, N vendor firmware-update channels collapse into the one proof-checked generation mechanism, and attestation coverage becomes total, radio included.
· Accept: each consequence is discharged by a named mechanism (R-11-003, R-09-025).
· Trace: CJ-DEVTREE · [L179](verification-maximal-os.md#L179)

---

## §5 — Languages & Verification

### 5.1 Trust, language, and compilation boundary

**R-05-001** MUST — The whole TCB is written in verified C and compiled by CHERI-CompCert under Coq.
· Accept: every object in the §6 TCB inventory appears in the CompCert build manifest with its correctness certificate; the set of TCB objects built by any other compiler is empty.
· Trace: CJ-COMPCERT · [L186](verification-maximal-os.md#L186)

**R-05-002** MUST — The §6 admission checker is inside the TCB and is subject to R-05-001 without exemption.
· Accept: the checker appears in both the TCB inventory and the CompCert build manifest.
· Trace: CJ-COMPCERT · [L186](verification-maximal-os.md#L186)

**R-05-003** MUST NOT — No TCB component enters the system as a checker-admitted artifact.
· Accept: (TCB inventory) ∩ (checker-admitted artifact set) = ∅.
· Trace: CJ-COMPCERT · [L187](verification-maximal-os.md#L187)

**R-05-004** MUST — The crypto core's constant-time property is verified on the artifact against the §15 leakage model.
· Accept: each crypto binary carries artifact-level CT evidence (taint-typing derivation or relational proof term); no CT claim in the crypto core cites compiler preservation as its ground.
· Trace: CJ-CT-SOUND, CJ-LEAK · [L187](verification-maximal-os.md#L187)

**R-05-005** MUST — The crypto core's field-arithmetic kernels are verified C compiled through CHERI-CompCert.
· Accept: every field-arithmetic object is in the CompCert build manifest; no field-arithmetic object is a checker-admitted assembly leaf.
· Trace: CJ-COMPCERT, CJ-CRYPTO-SPEC · [L187](verification-maximal-os.md#L187)

**R-05-006** MUST NOT — Contained code never enters the TCB.
· Accept: no artifact produced by the certifying userspace toolchain appears in the TCB inventory.
· Trace: CJ-COMPCERT · [L188](verification-maximal-os.md#L188)

**R-05-007** IS — Contained data-plane code is Rust by default; contained control-plane code is Coq-verified Lustre compiled by Vélus.
· Accept: each §12 server's control-plane logic is a Lustre node set; its data-plane logic is Rust.
· Trace: CJ-VELUS · [L189](verification-maximal-os.md#L189)

**R-05-008** MUST NOT — Admission never gates on the source language of a binary.
· Accept: the §6 checker's inputs are the binary and its CHERI-TAL derivation only; no checker decision reads a source-language identifier.
· Trace: CJ-TAL-SOUND · [L191](verification-maximal-os.md#L191)

**R-05-009** MUST — Any memory-safe or formally-verified language that yields a well-typed binary, or that ships a manual §13 memory-safety proof, is admissible on the same terms as Rust.
· Accept: the admission rules contain no language allowlist; a non-Rust component meeting the binary-level floor is admitted without exception or waiver.
· Trace: CJ-TAL-SOUND · [L191](verification-maximal-os.md#L191)

**R-05-010** MUST NOT — A contained component's own foreign-prover verification never enters the trust base.
· Accept: the axiom and trust-base inventory attributes no entry to a contained component's F\*/Z3, EasyCrypt, or other foreign-prover pedigree; removing that pedigree changes no platform guarantee.
· Trace: CJ-TAL-SOUND · [L192–193](verification-maximal-os.md#L192)

### 5.2 One prover

**R-05-011** IS — Exactly one proof checker exists in the trust base: the Coq (CIC) kernel.
· Accept: the trust-base inventory names one checker; no admitted artifact's acceptance depends on any other checker.
· Trace: CJ-T · [L194](verification-maximal-os.md#L194)

**R-05-012** MUST — The kernel is seL4's design re-proved end-to-end in Coq, not seL4's Isabelle proof adopted.
· Accept: no Isabelle artifact appears in the trust base; the kernel refinement proof is a Coq development.
· Trace: CJ-KERNEL · [L195](verification-maximal-os.md#L195), [L199](verification-maximal-os.md#L199)

**R-05-013** MUST — The kernel is compiled through CompCert/SECOMP.
· Accept: the kernel image's build manifest names the SECOMP-criterion CHERI backend.
· Trace: CJ-COMPCERT, CJ-SECOMP · [L195](verification-maximal-os.md#L195)

**R-05-014** MUST — The non-interference theorem is a fresh Coq re-proof, and no part of it is inherited from seL4's existing NI proof.
· Accept: the NI development cites no l4v proof obligation as discharged elsewhere.
· Trace: CJ-NI · [L198](verification-maximal-os.md#L198)

### 5.3 The single-prover rule binds the checker, not the producer

**R-05-015** MUST — Any prover, solver, or search procedure may produce a proof term, provided the Coq kernel re-checks the emitted term.
· Accept: for every externally-found proof, a kernel-checked term exists; the tool's own verdict is never the ground of acceptance.
· Trace: CJ-T · [L202](verification-maximal-os.md#L202)

**R-05-016** MUST NOT — No tool is admitted as a second checker.
· Accept: no artifact is accepted on the strength of a non-Coq checker's verdict.
· Trace: CJ-T · [L205](verification-maximal-os.md#L205)

**R-05-017** MUST — SMT results enter only via in-kernel reconstruction (SMTCoq-style witness import).
· Accept: every SMT-derived fact has a kernel-checked reconstruction; no `Axiom` records an SMT result.
· Trace: CJ-T · [L203](verification-maximal-os.md#L203)

**R-05-018** IS — Learned tactic synthesis and LLM-guided proof search are untrusted finders whose terms the kernel re-checks, and carry zero trust cost.
· Accept: removing every such tool from the pipeline invalidates no checked theorem.
· Trace: CJ-T · [L204](verification-maximal-os.md#L204)

### 5.4 The semantic-anchor budget

**R-05-019** IS — The load-bearing semantic anchors are frozen and exhaustively enumerated: Sail (ISA), CHERI-C/CompCert (verified-C memory model), Gallina/CIC, Radium (Rust fragment), Lustre/Vélus (synchronous dataflow), Kôika/Kami (hardware refinement), and the one Iris-over-Sail program logic with its four theories.
· Accept: the anchor list in the trust-base inventory is exactly these seven; any eighth is an amendment to this register.
· Trace: CJ-SAIL, CJ-RTL-SAIL · [L209](verification-maximal-os.md#L209)

**R-05-020** MUST — A new semantics, program logic, or translator is admitted only on a shown demonstration of all three conditions: Coq-native or mechanically bridged; non-duplicating of an existing anchor; and retiring an interim it replaces.
· Accept: each amendment record carries three arguments, one per condition, each shown rather than asserted.
· Trace: CJ-T · [L210](verification-maximal-os.md#L210)

**R-05-021** IS — A verified compiler is proof transport between two existing anchors, not an anchor, and is admitted freely.
· Accept: the anchor count is unchanged by adding a verified compilation step.
· Trace: CJ-COMPCERT, CJ-VELUS · [L211](verification-maximal-os.md#L211)

**R-05-022** MUST — Every interim non-Coq anchor carries a named Coq-native destination and is governed by one stated retirement rule: an interim retires when its destination has passed admission for every consumer that currently rides the interim, and is struck from the trust-base inventory in that same generation.
· Accept: *retired* is decided by inspecting two lists — the interim's consumer set and the destination's admitted artifacts — rather than by judgment. The five entries (F\*/Z3 for libcrux/HACL\*, EasyCrypt's Why3/SMT, aiT, Binsec/Rel, Cranelift/Crocus's SMT) each carry a destination and a consumer list.

**R-05-022a** MUST — An interim whose consumer set grows without its destination advancing is a review-gate finding, not a silent extension.
· Accept: the *shrinking-interim* claim of §17 is measurable against the consumer lists rather than asserted.
· Trace: CJ-T · [L212](verification-maximal-os.md#L212)

### 5.5 Compilation guarantees

**R-05-023** MUST — Translation validation against the RISC-V Sail model covers the assembly, link, and image-construction steps that fall outside CompCert's theorem.
· Accept: every trusted image has a validation record covering each post-CompCert step.
· Trace: CJ-SAIL, CJ-COMPCERT · [L214](verification-maximal-os.md#L214)

**R-05-024** MUST — The CHERI-RISC-V CompCert backend satisfies a secure-compilation (robust-preservation) criterion: it preserves compartment isolation against an adversarial linked context, not merely refinement of well-defined whole-program behaviour.
· Accept: the backend's top-level theorem statement quantifies over an adversarial linked context.
· Trace: CJ-SECOMP · [L215–216](verification-maximal-os.md#L215)

**R-05-025** IS — The compiler remains untrusted evidence-producing machinery under FPCC; R-05-024 strengthens its theorem, not its trust status.
· Accept: the compiler is absent from the consumer-side TCB inventory.
· Trace: CJ-SECOMP · [L219](verification-maximal-os.md#L219)

### 5.6 Foundational proof-carrying code

**R-05-026** MUST — Every binary ships a machine-checkable proof of its assurance tier, stated at binary level against the CHERI-RISC-V Sail model.
· Accept: no binary is admitted without a tier-appropriate certificate; the certificate's statement quantifies over the Sail model, not over source.
· Trace: CJ-SAIL, CJ-TAL-SOUND · [L221](verification-maximal-os.md#L221)

**R-05-027** MUST — The certificate is checked at admission by the on-device checker.
· Accept: admission fails closed when the certificate is absent, malformed, or fails re-checking.
· Trace: CJ-TAL-SOUND · [L221](verification-maximal-os.md#L221)

**R-05-028** MUST NOT — No trusted verification-condition generator exists; on the proof-carrying-code path the axioms are the proof kernel, the machine model, and the spec statements.
· Accept: the three classes are what PCC rests on; the platform's full axiom set is enumerated once in §6 (R-06-011) and is larger, adding the TAL type-checker, its soundness metatheorem, and the bootstrap root. This bullet no longer claims to state the whole set.
· Trace: CJ-T, CJ-SAIL · [L222](verification-maximal-os.md#L222)

**R-05-029** IS — The type-level obligations are exactly: memory safety, definite initialization, control-flow integrity, no-runtime-codegen, ABI/type conformance, examined verdicts, absent ambient state, representation-and-provenance conformance, constant-time, and WCET. **See [D-03](#d-03).**
· Accept: every admitted binary's derivation carries an attribute, citation, or deletion-check for each listed obligation.
· Trace: CJ-TAL-SOUND · [L224](verification-maximal-os.md#L224)

**R-05-030** IS — The obligations no type system states — Tier-0 refinement, non-interference, crypto reduction security, and the residual unstructured constant-time and WCET cases — remain proof terms for the CIC kernel.
· Accept: none of these appears as a TAL attribute; each has a release-time proof term.
· Trace: CJ-NI, CJ-REDUCTION · [L225](verification-maximal-os.md#L225)

**R-05-031** MUST — The CHERI-TAL soundness metatheorem (well-typed ⇒ safe over the Sail model) is a single Coq proof.
· Accept: one theorem statement, one development; admission's appeal to type-checking cites it and nothing else.
· Trace: CJ-TAL-SOUND, CJ-SAIL · [L226](verification-maximal-os.md#L226)

**R-05-032** MUST — The verified compiler runs in certifying mode: each Tier-0 build ships the composed theorem *this binary refines its abstract spec and robustly preserves compartment isolation*.
· Accept: every Tier-0 artifact carries a composed theorem with both conjuncts.
· Trace: CJ-SECOMP, CJ-KERNEL · [L227](verification-maximal-os.md#L227)

**R-05-033** MUST — A secret-touching binary admitted through the Islaris-style Iris-over-Sail path (no verified compiler in the loop) carries a separate binary-level constant-time obligation.
· Accept: for each such binary, a CT artifact exists independent of the functional/safety proof.
· Trace: CJ-CT-SOUND · [L227](verification-maximal-os.md#L227)

**R-05-034** MUST NOT — The compiler, extraction tooling, and build farm are absent from the consumer-side TCB.
· Accept: the consumer-side TCB inventory names none of them.
· Trace: CJ-COMPCERT · [L228](verification-maximal-os.md#L228)

**R-05-035** IS — Every instruction has exactly one 4-byte-aligned decoding, so binary-level proofs discharge no overlapping-stream interpretation.
· Accept: the §15 profile excludes the C extension; the TAL's decode relation is a function.
· Trace: CJ-SAIL · [L230](verification-maximal-os.md#L230); constrains R-15-*

### 5.7 The three checker moves

**R-05-036** IS — The checker discharges every type-level obligation by exactly three moves: (I) cite a runtime invariant CHERI enforces, (II) evaluate a Knuth-style attribute over the already-typed CFG, (III) confirm a deletion.
· Accept: each obligation in R-05-029 maps to exactly one move; the checker's implementation has no fourth mechanism.
· Trace: CJ-TAL-SOUND · [L233–239](verification-maximal-os.md#L233)

**R-05-037** IS — Move I carries spatial memory safety, no-runtime-codegen, and CFI-runtime through sentry reachability.
· Accept: the derivation records the cited invariant; the checker inspects the citation.
· Trace: CJ-CERISE · [L237](verification-maximal-os.md#L237)

**R-05-038** IS — Move II carries temporal memory safety, definite initialization, examined verdicts, constant-time, WCET, callee-set enumeration, and type/ABI conformance.
· Accept: each has a finite attribute domain and a syntax-directed rule (see R-05-132).
· Trace: CJ-TAL-SOUND · [L238](verification-maximal-os.md#L238)

**R-05-039** IS — Move III carries representation-and-provenance conformance and absence of ambient mutable state, as one-pass inspections of absences.
· Accept: each is decided by a single pass over the image or derivation, with no fixpoint.
· Trace: CJ-TAL-SOUND · [L239](verification-maximal-os.md#L239)

**R-05-040** MUST NOT — The checker never re-proves a hardware fact cited under move I.
· Accept: no move-I obligation has a checker-side decision procedure beyond confirming the citation.
· Trace: CJ-TAL-SOUND · [L237](verification-maximal-os.md#L237)

**R-05-041** MUST — The soundness metatheorem is stated over the three moves against the four unary invariants, not over a flat list of ten obligations.
· Accept: the theorem statement quantifies over move classes; adding an obligation within an existing move adds no new top-level case.
· Trace: CJ-TAL-SOUND · [L242](verification-maximal-os.md#L242)

### 5.8 Verified parsers

**R-05-042** MUST — Every attacker-facing wire format is parsed by a verified copy-once Narcissus parser, explicitly including the ASN.1 UPER/aligned-PER grammars of cellular RRC/NAS and the 802.11 MLME element grammars.
· Accept: the wire-format inventory lists every attacker-facing format with its Narcissus descriptor; the set of hand-written attacker-facing parsers is empty except as permitted by R-05-050.
· Trace: CJ-FORMAT · [L243](verification-maximal-os.md#L243)

**R-05-043** MUST — The Coq decoder reaches machine code by Fiat/Bedrock correct-by-construction synthesis to imperative Clight.
· Accept: no parser is extracted onto a managed runtime and none is hand-refined per grammar; the synthesis is counted as proof transport, not an anchor.
· Trace: CJ-FORMAT, CJ-COMPCERT · [L245](verification-maximal-os.md#L245)

**R-05-044** MUST NOT — EverParse is not admitted as a shipped parser generator or checker.
· Accept: no shipped parser derives from an F\*/Z3 generator.
· Trace: CJ-FORMAT · [L246](verification-maximal-os.md#L246)

**R-05-045** IS — EverParse is admissible as an untrusted differential oracle.
· Accept: its use appears only in the §18 test pipeline, never in the trust base.
· Trace: CJ-FORMAT · [L253](verification-maximal-os.md#L253)

**R-05-046** IS — Each format descriptor is a crown-jewel spec: the parser proof is against the descriptor, not against the 3GPP or IEEE text.
· Accept: the descriptor set is enumerated in the crown-jewel inventory and is subject to independent review under R-05-150.
· Trace: CJ-FORMAT · [L248–250](verification-maximal-os.md#L248)

**R-05-047** MUST — Memory safety of a parser holds unconditionally regardless of descriptor fidelity: a mis-transcribed grammar yields a semantic defect, never a memory-safety one.
· Accept: copy-once structure, `#![forbid(unsafe_code)]`, CHERI bounds, and §12/§13 compartment containment are each independently established for every parser.
· Trace: CJ-TAL-SOUND, CJ-CERISE · [L249](verification-maximal-os.md#L249)

**R-05-048** MUST — NR RRC descriptors are compiled from the published machine-readable ASN.1 (3GPP TS 38.331) by a verified ASN.1 (X.691 UPER) → Narcissus front end, not hand-written.
· Accept: the RRC descriptor build reads the vendor ASN.1 modules as input; no hand-written RRC descriptor exists.
· Trace: CJ-FORMAT · [L251](verification-maximal-os.md#L251)

**R-05-049** IS — The only trusted artifact on the parser path is the small ASN.1 → Narcissus compiler, and its output is Coq-checked.
· Accept: the trust-base inventory lists the compiler and no other parser-path artifact.
· Trace: CJ-FORMAT · [L252](verification-maximal-os.md#L252)

**R-05-050** MUST — 5G-core NAS (TS 24.501, IEI/TLV, not ASN.1) keeps a hand-written grammar, and that grammar carries differential-oracle coverage as its residual-retirement mechanism.
· Accept: the NAS descriptor is flagged in the crown-jewel inventory as hand-transcribed and has a differential-oracle corpus result.
· Trace: CJ-FORMAT · [L251](verification-maximal-os.md#L251)

**R-05-051** MUST — Differential oracles (asn1scc, asn1c, Wireshark dissectors, srsRAN/OpenAirInterface decoders) cross-check every derived parser on captured and fuzzed corpora and enter no trust base.
· Accept: a §18 corpus result exists per descriptor; no oracle appears in the trust-base inventory.
· Trace: CJ-FORMAT · [L252](verification-maximal-os.md#L252)

### 5.9 Verified synchronous control planes

**R-05-052** MUST — The control-plane logic of §12 servers — supervision trees, protocol state machines, and mode/timing sequencing — is written in Lustre and compiled by Vélus.
· Accept: each server's control plane is a Lustre node set; no control-plane logic is hand-written Rust or C.
· Trace: CJ-VELUS · [L254–255](verification-maximal-os.md#L254)

**R-05-053** MUST — Vélus emits CompCert Clight and its correctness theorem composes with CompCert's.
· Accept: a single composed theorem covers Lustre source to CHERI machine code; no unproved gap sits between the two compilers.
· Trace: CJ-VELUS, CJ-COMPCERT · [L255](verification-maximal-os.md#L255)

**R-05-054** IS — Control-tier WCET falls out of compilation (a Lustre node is a loop-free, statically-sized reaction) and does not consume the §5 syntax-directed cost annotation.
· Accept: no control-plane node carries a max-path cost attribute.
· Trace: CJ-WCET, CJ-VELUS · [L257](verification-maximal-os.md#L257)

**R-05-055** MUST — Vélus's clock calculus rejects instantaneous cycles and fixes evaluation order, so the control tier exhibits no schedule-dependent behaviour.
· Accept: compilation fails on any instantaneous cycle; §15 admission-test-3 (*no hidden state survives a partition switch*) is discharged by construction for this tier.
· Trace: CJ-VELUS, CJ-NI · [L257](verification-maximal-os.md#L257)

**R-05-056** IS — Control-tier state is statically allocated, making the §13 temporal-safety certificate trivial for this tier.
· Accept: no control-plane node allocates at runtime.
· Trace: CJ-VELUS · [L257](verification-maximal-os.md#L257)

**R-05-057** MUST — Data-plane logic (bulk I/O, vector/matrix math, wire parsing) is `#![forbid(unsafe_code)]` Rust.
· Accept: every data-plane crate carries the attribute with no exception.
· Trace: CJ-TAL-SOUND · [L258](verification-maximal-os.md#L258)

### 5.10 Crypto

**R-05-058** IS — Post-quantum primitives are the default: ML-KEM for key establishment, ML-DSA for signatures.
· Accept: no protocol in §12 negotiates a classical-only key establishment as its primary path.
· Trace: CJ-CRYPTO-SPEC · [L260](verification-maximal-os.md#L260)

**R-05-059** MUST — Every crypto primitive carries all three assurance layers: functional correctness, constant-time, and reduction-level security.
· Accept: the crypto inventory has three evidence entries per primitive; a primitive missing any layer is not shipped.
· Trace: CJ-CRYPTO-SPEC, CJ-REDUCTION, CJ-CT-SOUND · [L261](verification-maximal-os.md#L261)

**R-05-060** MUST — Classical field arithmetic is Fiat-Crypto (Coq-native).
· Accept: every field-arithmetic implementation traces to a Fiat-Crypto derivation.
· Trace: CJ-CRYPTO-SPEC · [L263](verification-maximal-os.md#L263)

**R-05-061** IS — libcrux/HACL\* for PQ primitives is an explicitly interim F\*/Z3 widening with a named Coq-native destination, not an open-ended tolerance.
· Accept: the interim register entry (R-05-022) names the destination and the retirement condition.
· Trace: CJ-CRYPTO-SPEC · [L263](verification-maximal-os.md#L263)

**R-05-062** MUST — Constant-time is a 2-safety hyperproperty verified directly on the binary for every secret-touching artifact, the crypto core included.
· Accept: CT evidence is per-binary; no CT claim rests on source-level review or on the producer's identity.
· Trace: CJ-CT-SOUND, CJ-LEAK · [L265](verification-maximal-os.md#L265)

**R-05-063** MUST NOT — No verified-compiler constant-time route exists; CT is never inherited from a compiler theorem.
· Accept: the CHERI-CompCert theorem statement contains no CT conjunct, and no artifact cites one.
· Trace: CJ-COMPCERT, CJ-CT-SOUND · [L265](verification-maximal-os.md#L265)

**R-05-064** MUST NOT — The CryptOpt-style route (untrusted superoptimizer plus a net-new Coq-verified assembly↔Fiat-Crypto equivalence checker) is deleted, not deferred.
· Accept: §18 carries no such workstream; the checker inventory contains no equivalence checker.
· Trace: CJ-CRYPTO-SPEC · [L266](verification-maximal-os.md#L266), [L285](verification-maximal-os.md#L285)

**R-05-065** MUST NOT — Standing rule: any net-new verified artifact whose only yield is performance on a path already correct and already leak-free is inadmissible; the slower sound artifact is taken.
· Accept: every admitted net-new verified artifact has a stated yield other than performance.
· Trace: CJ-T · [L267](verification-maximal-os.md#L267)

**R-05-066** IS — The rule in R-05-065 targets *minting a checker*, not the asymmetric-trust pattern: an untrusted optimizer whose output the already-existing checkers re-validate is admissible and free to be arbitrarily aggressive.
· Accept: an optimizer is admissible iff its output is decided by an existing checker with no new checker introduced.
· Trace: CJ-TAL-SOUND · [L268](verification-maximal-os.md#L268)

**R-05-067** MUST — Control-flow-heavy primitives (Keccak, AES, ChaCha, the ML-KEM/ML-DSA NTT and samplers) are written branchless on secrets using `Zicond` selects, hardened, and then verified on the artifact.
· Accept: each such binary passes the artifact-level CT check; no secret-dependent branch survives in the admitted binary.
· Trace: CJ-CT-SOUND, CJ-LEAK · [L271](verification-maximal-os.md#L271)

**R-05-068** MUST — Where a lowering resists CT hardening, the fix is in the source; no hand-written or checker-admitted assembly leaf is introduced.
· Accept: the crypto build manifest contains no assembly leaf; a primitive that cannot be hardened is restructured or not shipped (fail-closed).
· Trace: CJ-CRYPTO-SPEC · [L271](verification-maximal-os.md#L271)

**R-05-069** IS — Constant-time is carried by the move-II secret-taint attribute (a two-point lattice) where a type discipline suffices, and proved where it does not.
· Accept: each secret-touching binary is classified as type-decided or proof-discharged; both classes are non-empty only where the spec permits.
· Trace: CJ-CT-SOUND · [L272–273](verification-maximal-os.md#L272)

**R-05-070** MUST — The CT type system rejects any secret-labeled value reaching a branch condition, a memory address, or a variable-latency operation outside the `Zkt`/`Zvkt` list.
· Accept: the typing rules enumerate the three rejection sites; the permitted-operation list is exactly the `Zkt`/`Zvkt` set from §15.
· Trace: CJ-CT-SOUND, CJ-LEAK · [L273](verification-maximal-os.md#L273)

**R-05-071** MUST — The constant-time type-soundness metatheorem (CT-Wasm lineage) is restated in Coq over the §15 leakage model and joins the CHERI-TAL soundness proof.
· Accept: one Coq theorem; the TAL soundness statement includes the CT case.
· Trace: CJ-CT-SOUND, CJ-TAL-SOUND · [L273](verification-maximal-os.md#L273)

**R-05-072** MUST — The residual corner (unstructured secret-dependent code that does not type-check) is either branchless-hardened and re-typed, or discharged by a relational self-composition program logic over the leakage-annotated Sail semantics emitting a CIC-checked term.
· Accept: every non-type-checking secret path has one of the two dispositions recorded; none is waived.
· Trace: CJ-CT-SOUND, CJ-SAIL · [L275](verification-maximal-os.md#L275)

**R-05-073** IS — Binsec/Rel is bounded symbolic-execution evidence and a bring-up gate, never the axiom; ct-verif is IR-level and does not satisfy the on-the-artifact statement.
· Accept: no CT claim's ground is a Binsec/Rel or ct-verif result.
· Trace: CJ-CT-SOUND · [L277](verification-maximal-os.md#L277)

**R-05-074** IS — The CT obligation is scoped to secret-touching compartments, and the scope is defined by the *label on the material* rather than its channel of arrival: a compartment is secret-touching if it holds secret-labeled material however obtained — over an IDL confidentiality channel, through a capability-bounded DMA window or an RoT-latched re-delegated front end, or from a local entropy draw.
· Accept: the population includes the PIN and biometric paths §13's Tier-1 row names first, and it is exactly the population replay's entropy substitution is sound over (R-16-018). Narrower than the whole app population, wider than the IDL channel set.
· Trace: CJ-IDL, CJ-CT-SOUND · [L278](verification-maximal-os.md#L278)

**R-05-075** MUST — Reduction-level security (IND-CCA for KEMs, EUF-CMA for signatures) is proved Coq-native in SSProve/FCF.
· Accept: each scheme has a Coq reduction; EasyCrypt results are accelerators with SSProve as the stated destination.
· Trace: CJ-REDUCTION · [L281–282](verification-maximal-os.md#L281)

**R-05-076** IS — The three layers compose at the primitive's abstract functional specification, which is thereby a crown-jewel spec.
· Accept: each primitive's functional specification is in the crown-jewel inventory and is the shared object of the layer-1/2 refinement and the layer-3 game.
· Trace: CJ-CRYPTO-SPEC, CJ-REDUCTION · [L283](verification-maximal-os.md#L283)

**R-05-077** IS — The reduction isolates and names the residual hardness assumptions (MLWE/MSIS; ECDLP/CDH) and cannot discharge them.
· Accept: each appears in the §17 axiom set `Ax`, not in the theorem set.
· Trace: CJ-REDUCTION · [L284](verification-maximal-os.md#L284)

**R-05-078** MUST NOT — Protocol-level composition (TLS 1.3, WireGuard, the cellular AKA composition) is not claimed by the crypto layers. **See [D-05](#d-05).**
· Accept: no crown-jewel theorem statement mentions a composed session-security property; the §3 Defended/Residual split records the exclusion.
· Trace: CJ-REDUCTION · [L284](verification-maximal-os.md#L284)

### 5.11 Contained Rust and the verified HAL

**R-05-079** MUST — All Rust-authored app and server logic carries `#![forbid(unsafe_code)]` with no exception.
· Accept: the attribute is present in every contained crate; the exception count is zero.
· Trace: CJ-TAL-SOUND · [L286](verification-maximal-os.md#L286)

**R-05-080** IS — The sole residual `unsafe` is in a minimal, formally verified HAL comprising the DMA, MMIO, and descriptor primitives.
· Accept: the set of `unsafe` blocks outside the HAL is empty.
· Trace: CJ-HAL · [L287](verification-maximal-os.md#L287)

**R-05-081** MUST — The HAL's `unsafe` carries machine-checked memory-safety and hardware-contract proofs, not audit.
· Accept: each HAL primitive has a proof obligation discharged in Coq (or the equivalent FPCC discipline); no primitive is admitted on review alone.
· Trace: CJ-HAL · [L288](verification-maximal-os.md#L288)

**R-05-082** MUST — A DMA or descriptor primitive returning a device-filled buffer establishes that buffer's *initialized* postcondition.
· Accept: every such primitive's contract contains the postcondition; the definite-initialization attribute (R-05-122) consumes it at the compartment edge.
· Trace: CJ-HAL, CJ-TAL-SOUND · [L288](verification-maximal-os.md#L288)

**R-05-083** MUST — MMIO register field layouts are declared once in a register-description language, and the shift/mask field accessors are generated correct-by-construction and Coq-checked against that declaration.
· Accept: no hand-written bit-twiddling and no unverified template or macro layer appears in the HAL; every accessor traces to a declaration.
· Trace: CJ-HAL · [L288](verification-maximal-os.md#L288)

**R-05-084** MUST — All contained Rust is compiled by the certifying userspace toolchain straight to native RV64+CHERI; the bare rustc/LLVM path is inadmissible.
· Accept: every admitted contained binary carries a certificate from the certifying toolchain.
· Trace: CJ-TAL-SOUND · [L289](verification-maximal-os.md#L289)

**R-05-085** MUST NOT — Wasm/WASI is not an execution target anywhere in the system.
· Accept: no Wasm runtime, interpreter, or JIT exists in any image.
· Trace: CJ-TAL-SOUND · [L289](verification-maximal-os.md#L289)

### 5.12 No ambient state

**R-05-086** MUST NOT — No module-level mutable state, no lazily-initialized statics, no thread-locals, and no hidden singletons.
· Accept: the checker's move-III scan finds no writable static reachable by name; interior-mutable statics and `thread_local!` are rejected at admission, not merely linted.
· Trace: CJ-TAL-SOUND, CJ-CERISE · [L293](verification-maximal-os.md#L293)

**R-05-087** MUST — Every capability and every piece of mutable state a component uses is either a construction-time parameter or reachable only from a reference it was explicitly handed.
· Accept: the component's initial capability set, as recorded in the manifest, is the transitive root of all authority it exercises.
· Trace: CJ-CERISE · [L293](verification-maximal-os.md#L293)

**R-05-088** IS — Immutable statics are untouched: `const` data and `static` of a type with no interior mutability are read-only-image data, covered by W^X.
· Accept: such statics reside in the read-only image and carry no tag.
· Trace: CJ-CERISE · [L294](verification-maximal-os.md#L294)

**R-05-089** MUST — The binary-level statement is that a compartment's initial capability set is its whole authority: its static data section carries no tagged capability, and no writable object is reachable except from a capability the code was given.
· Accept: a one-pass scan of the image finds no tagged datum in the static data section; a set tag there is a type error.
· Trace: CJ-CERISE, CJ-TAL-SOUND · [L299–300](verification-maximal-os.md#L299)

**R-05-090** IS — Rust discharges the rule by `#![forbid(unsafe_code)]` plus a deny on interior-mutable statics and `thread_local!`; Lustre/Vélus discharges it by construction; the §12 IDL passes authority explicitly.
· Accept: each language path has a stated discharge; none relies on the source lint alone (R-05-089 is the binding check).
· Trace: CJ-VELUS, CJ-IDL · [L301](verification-maximal-os.md#L301)

**R-05-091** MUST — The pre-admission boot substrate and M-mode firmware, being outside the admitted set, carry the no-ambient-state obligation as ordinary Tier-0 proof over their statically-planned state.
· Accept: the boot substrate's Tier-0 proof includes the obligation; it is not assumed to inherit the type-level rule.
· Trace: CJ-KERNEL · [L1907](verification-maximal-os.md#L1907)

**R-05-092** IS — The rule forbids *re-manufacturing* a global and says nothing about *over-injecting* one: a component handed broad authority at construction and threading it everywhere is well-typed and over-privileged, and that residual is booked in §17.
· Accept: the §17 residual entry exists; no register requirement claims least-authority as a consequence of R-05-086.
· Trace: CJ-CERISE · [L303](verification-maximal-os.md#L303), [L1904](verification-maximal-os.md#L1904)

### 5.13 Certifying userspace compilation

**R-05-093** MUST — The userspace Rust→RV64+CHERI toolchain runs in certifying mode, emitting a machine-checkable memory-safety certificate with each binary.
· Accept: no contained binary is admitted without one.
· Trace: CJ-TAL-SOUND · [L305](verification-maximal-os.md#L305)

**R-05-094** IS — That certificate is a CHERI-TAL typing derivation covering temporal safety, control-flow integrity, no-runtime-codegen, and ABI/type conformance, stated at binary level against the Sail model, and it is not full functional correctness.
· Accept: the certificate's four conjuncts are present; functional correctness remains a Tier-0/1 obligation.
· Trace: CJ-TAL-SOUND, CJ-SAIL · [L305–306](verification-maximal-os.md#L305)

**R-05-095** IS — For admitted code, rustc and LLVM leave the intra-compartment memory-safety trust base.
· Accept: removing trust in rustc/LLVM invalidates no admitted binary's memory-safety claim.
· Trace: CJ-TAL-SOUND · [L307](verification-maximal-os.md#L307)

### 5.14 Relevance grading: examined verdicts

**R-05-096** IS — Capabilities are linear/affine: contraction denied so authority cannot be duplicated, weakening allowed so it may be dropped.
· Accept: the TAL's context-splitting rules deny contraction on capability types.
· Trace: CJ-TAL-SOUND · [L311](verification-maximal-os.md#L311)

**R-05-097** MUST — Fallible results are relevance-graded: weakening denied, contraction allowed, so every error verdict must be consumed at least once.
· Accept: a derivation that drops a relevance-graded value fails to type-check.
· Trace: CJ-TAL-SOUND · [L312–313](verification-maximal-os.md#L312)

**R-05-098** IS — The scope of relevance grading is every result encoding whether an authority-, integrity-, or freshness-bearing action succeeded: attestation and appraisal verdicts, ECC and memory-authentication status, capability-derivation and revocation results, IDL call outcomes, admission-check verdicts, and storage-transaction commit results.
· Accept: each listed result type carries the grade in its IDL or ABI declaration; the list is closed by amendment to this register.
· Trace: CJ-IDL, CJ-TAL-SOUND · [L319](verification-maximal-os.md#L319)

**R-05-099** MUST — A wildcard bind on a relevance-graded type is a type error; discarding a verdict requires an explicit elimination that names the outcome.
· Accept: the typing rules reject `_`-binding at relevance-graded type; the typed discard form exists and is auditable.
· Trace: CJ-TAL-SOUND · [L321](verification-maximal-os.md#L321)

**R-05-100** MUST NOT — There are no exceptions, no stack unwinding, and no `longjmp`: a typed absence in the TAL rather than a convention.
· Accept: the TAL has no unwinding construct; a failing compartment takes the §16 crash-only fail-stop and supervisor restart.
· Trace: CJ-TAL-SOUND · [L315](verification-maximal-os.md#L315)

**R-05-101** IS — Relevance grading adds no runtime check, no silicon, no new semantic anchor, and no new crown jewel; it strengthens the statement of the CHERI-TAL soundness metatheorem.
· Accept: anchor count, crown-jewel count, and silicon area are unchanged by its adoption.
· Trace: CJ-TAL-SOUND · [L322](verification-maximal-os.md#L322)

### 5.15 WCET

**R-05-102** MUST — WCET is derived syntax-directed as a max-path sum over the typed control-flow graph with loop bounds (Shaw's timing schema), carried as the move-II cost attribute (ℕ under max-and-plus).
· Accept: the bound is read off the typing derivation the on-device checker already validates; no separate analysis pass exists.
· Trace: CJ-WCET, CJ-TAL-SOUND · [L323–324](verification-maximal-os.md#L323)

**R-05-103** MUST — Per-instruction latency comes from the timing-annotated Sail model and is sound to the metal by RTL ⊑ Sail.
· Accept: every cost annotation traces to a Sail latency entry; no latency is asserted independently.
· Trace: CJ-WCET, CJ-RTL-SAIL · [L325](verification-maximal-os.md#L325)

**R-05-104** MUST NOT — The Implicit Path Enumeration Technique and its LP solver are deleted, not retargeted.
· Accept: no ILP machinery exists in the toolchain or in §18.
· Trace: CJ-WCET · [L326](verification-maximal-os.md#L326)

**R-05-105** MUST NOT — Standing no-tightening rule: any verified tool that exists only to tighten an already-sound bound is inadmissible; the trivial sound bound is taken.
· Accept: every admitted verified analysis tool has a yield other than tightness; pessimism is accepted without appeal.
· Trace: CJ-WCET, CJ-T · [L327](verification-maximal-os.md#L327)

**R-05-106** IS — The rule in R-05-105 generalizes from bounds to artifacts, and the CryptOpt deletion (R-05-064) is the same rule applied to a tool rather than an estimate.
· Accept: both deletions cite one rule; neither is recorded as an independent judgment call.
· Trace: CJ-T · [L328](verification-maximal-os.md#L328)

**R-05-107** MUST — Loop bounds that resist syntactic inference are annotations discharged as Coq obligations against the source.
· Accept: each non-structural loop bound has a discharged obligation; none is asserted.
· Trace: CJ-WCET · [L329](verification-maximal-os.md#L329)

**R-05-108** IS — Where code is produced by correct-by-construction relational compilation (Lustre/Vélus; Fiat/Bedrock/Rupicola synthesis), the per-node cost falls out of the compilation derivation, so the standalone max-path pass is needed only for hand-written imperative data-plane code.
· Accept: synthesized components carry costs from their derivations, not from a separate pass.
· Trace: CJ-WCET, CJ-VELUS · [L329](verification-maximal-os.md#L329)

**R-05-109** IS — aiT is an unverified out-of-band cross-check only.
· Accept: no admitted bound cites aiT as its ground.
· Trace: CJ-WCET · [L330](verification-maximal-os.md#L330)

**R-05-110** MUST NOT — MBPTA/EVT is inadmissible as the bound.
· Accept: no measurement-based statistic appears as a WCET input to §11 admission.
· Trace: CJ-WCET · [L330](verification-maximal-os.md#L330)

**R-05-111** MUST — The standalone Coq-verified WCET estimator is retired from the §18 workstream list.
· Accept: §18 carries no such deliverable.
· Trace: CJ-WCET · [L331](verification-maximal-os.md#L331)

### 5.16 Indirect control transfer and the typed callee set

**R-05-112** MUST — A call site reaches an indirect target only through a sentry capability it holds.
· Accept: the hardware permits no indirect transfer without a held sentry; under no-ambient-state, the sentries a site can name are exactly those wired to it or loaded from vtables it was given.
· Trace: CJ-CERISE · [L334](verification-maximal-os.md#L334)

**R-05-113** MUST — Every indirect transfer's code type carries the finite set of labels its reachable sentries target, and the typing rule confirms the jump stays within that set.
· Accept: one subset check per indirect transfer in the derivation.
· Trace: CJ-TAL-SOUND · [L336](verification-maximal-os.md#L336)

**R-05-114** MUST — The callee set is read off the sealed image at compose time, not over-approximated by a points-to analysis.
· Accept: with the on-device loader deleted and no dynamic linking, the address-taken set and the per-vtable impl set are fixed at compose time.
· Trace: CJ-TAL-SOUND · [L337–338](verification-maximal-os.md#L337)

**R-05-115** IS — Closures, function pointers, and `dyn Trait` survive unrestricted; a first-order source-language mandate and defunctionalization are rejected.
· Accept: no source-language restriction on higher-order constructs exists.
· Trace: CJ-TAL-SOUND · [L339](verification-maximal-os.md#L339)

**R-05-116** IS — The load-bearing consumer of the callee set is bound *existence*, not tightness: without it, call-graph acyclicity is unprovable and neither the max-path sum nor the live-range colouring yields a bound at all.
· Accept: the tighter per-site cost is recorded as a byproduct; the no-tightening rule (R-05-105) governs it.
· Trace: CJ-MEMPLAN, CJ-WCET · [L340–342](verification-maximal-os.md#L340)

**R-05-117** IS — Scope is per compartment: cross-compartment sentry edges stay outside the typed set and are governed by the manifest's import/export tables and the §12 IDL.
· Accept: no whole-program typing obligation exists; the system call graph is the composition of per-compartment graphs with manifest edges.
· Trace: CJ-IDL · [L343](verification-maximal-os.md#L343)

**R-05-118** MUST — A compiler that cannot enumerate a site's callee set refuses the binary rather than under-declaring it.
· Accept: the failure mode is refusal; the completeness residual is booked in §17.
· Trace: CJ-TAL-SOUND · [L344](verification-maximal-os.md#L344)

### 5.17 Definite initialization

**R-05-119** MUST — No load reads a slot before a store to it, decided at admission as a move-II attribute rather than trapped at runtime.
· Accept: the derivation carries an initialization flag per slot; a load whose premise is unmet fails to type-check.
· Trace: CJ-TAL-SOUND, CJ-MEMPLAN · [L346](verification-maximal-os.md#L346)

**R-05-120** MUST NOT — No hardware Write-before-Read metadata plane exists.
· Accept: the §15 memory subsystem carries no initialization-tag plane, no associated DECTED coverage, no Sail invariant, and no RTL ⊑ Sail obligation for one.
· Trace: CJ-RTL-SAIL · [L347](verification-maximal-os.md#L347), [L359](verification-maximal-os.md#L359)

**R-05-121** IS — The attribute domain is the two-point lattice *uninitialized* ⊑ *initialized*, met at control-flow merges: a store sets its slot's flag, a load's typing premise is that the flag is set, and a merge takes the meet.
· Accept: the rule is local and syntax-directed; the domain is finite; no open-term reduction occurs.
· Trace: CJ-TAL-SOUND · [L348–349](verification-maximal-os.md#L348)

**R-05-122** IS — Each slot's *uninitialized* point is §7's plan's own allocation point, not a runtime event.
· Accept: initialization is exactly as static as the slot plan.
· Trace: CJ-MEMPLAN · [L351](verification-maximal-os.md#L351)

**R-05-123** MUST — Device-written memory is covered by the verified HAL's DMA and descriptor postconditions (R-05-082), not by a tag the fabric sets.
· Accept: every device-fill path terminates in a HAL primitive whose contract establishes *initialized*.
· Trace: CJ-HAL · [L356](verification-maximal-os.md#L356)

**R-05-124** MUST — Initialization state crossing a compartment edge rides the §12 IDL message type and the manifest's import/export tables, with copy-once parsers writing their fixed destination buffers whole.
· Accept: no delegated buffer arrives without a declared initialization state.
· Trace: CJ-IDL, CJ-FORMAT · [L357](verification-maximal-os.md#L357)

**R-05-125** IS — The outcome is fail-closed at admission (a type error refused), not fail-stop at runtime (a trap).
· Accept: no runtime uninitialized-read trap exists in the platform.
· Trace: CJ-TAL-SOUND · [L354](verification-maximal-os.md#L354)

**R-05-126** MUST — Memory is eager-zeroized at allocation, so an unwritten slot reads a deterministic zero rather than residue.
· Accept: the §7 zeroize discipline covers every slot; `Zicboz` (`cbo.zero`) is in the §15 profile.
· Trace: CJ-MEMPLAN, CJ-SAIL · [L1236](verification-maximal-os.md#L1236); constrains R-15-*

### 5.18 The frozen checker theory

**R-05-127** IS — The on-device checker is an attribute-grammar evaluator, not a term checker, and its order-of-10³-line budget is a consequence of that category fact. **See [D-02](#d-02).**
· Accept: the checker evaluates a fixed attribute set bottom-up over the already-typed CFG with no fixpoint over open terms anywhere.
· Trace: CJ-TAL-SOUND · [L362–365](verification-maximal-os.md#L362)

**R-05-128** MUST NOT — Absence (1): polymorphism is predicative and rank-1 prenex only — type variables quantified at the outermost position of a code type and instantiated only at monotypes.
· Accept: no impredicative self-instantiation and no rank-*n* inference appears in the theory.
· Trace: CJ-TAL-SOUND · [L367](verification-maximal-os.md#L367)

**R-05-129** MUST NOT — Absence (2): no type-level computation. Type equality is syntactic (α-equivalence over first-order terms), with no βδιζη-reduction, no normalizer, and no evaluation of open terms.
· Accept: the checker's termination argument is syntactic; no strong-normalization premise lives inside it.
· Trace: CJ-TAL-SOUND · [L368–369](verification-maximal-os.md#L368)

**R-05-130** MUST NOT — Absence (3): no universes and no universe polymorphism — one sort of types, no cumulativity, no universe-constraint graph.
· Accept: the checker contains no acyclicity solver.
· Trace: CJ-TAL-SOUND · [L370](verification-maximal-os.md#L370)

**R-05-131** MUST NOT — Absence (4): no user-extensible inductive definitions. The type-constructor vocabulary is fixed and closed by this specification, and grows only by amendment to it, never at install time.
· Accept: no positivity check, no guard condition, and no eliminator generation exists in the checker; the vocabulary is capability types (bounds, permissions, revocation colour, initialization flag), code types (register-file preconditions carrying the callee set), the aggregate and existential formers the ABI needs, the linear/affine and relevance grades, the CT taint labels, and the WCET cost annotations.
· Trace: CJ-TAL-SOUND · [L371](verification-maximal-os.md#L371)

**R-05-132** MUST — A proposed attribute is admitted only on a shown demonstration that it (1) has a finite semilattice/monoid domain decided with no open-term reduction and preserves syntactic type equality, (2) duplicates no existing grade or label axis, and (3) has a local syntax-directed rule.
· Accept: each attribute's amendment record carries three shown arguments.
· Trace: CJ-TAL-SOUND · [L376](verification-maximal-os.md#L376)

**R-05-133** IS — A feature that fails R-05-132 descends to the CIC proof kernel as a release-time proof term rather than widening the theory, at the price of ceasing to be per-install checkable.
· Accept: the rejected feature appears in the release-time obligation set, not in the attribute set.
· Trace: CJ-TAL-SOUND · [L377](verification-maximal-os.md#L377)

**R-05-134** IS — The frozen theory binds the checker, not the producer: the certifying compiler may be written in and reason with any theory, since only the shipped derivation must be checkable in this one.
· Accept: no constraint on producer-side theory appears in the admission rules.
· Trace: CJ-TAL-SOUND · [L378](verification-maximal-os.md#L378)

**R-05-135** IS — The only computation the checker performs is bounded-width arithmetic over closed numerals (WCET literal sums and comparisons; overflow range side conditions), decided in constant time per node.
· Accept: no rule requires reduction of open terms; anything that would descends under R-05-133.
· Trace: CJ-TAL-SOUND, CJ-WCET · [L373–374](verification-maximal-os.md#L373)

### 5.19 Representation and provenance: five deletions

**R-05-136** MUST NOT — (1) No integer→capability provenance: no integer-to-pointer cast, no address literal that becomes a capability, and no reconstruction of a capability from its bit pattern. The only capability-producing operations are the monotone derivations (bounds and permission restriction, sealing, revocation-colour assignment) applied to a capability already held.
· Accept: the checker finds no integer inhabiting a capability type; the derivation's capability-producing rules are exactly the monotone set.
· Trace: CJ-CERISE, CJ-TAL-SOUND · [L384–385](verification-maximal-os.md#L384)

**R-05-137** IS — The provenance disjunct is consequently deleted from the CHERI-C/CompCert memory model, which is left monotone with no exposed-address state.
· Accept: the verified-C memory model carries no PNVI-style provenance case.
· Trace: CJ-COMPCERT · [L386](verification-maximal-os.md#L386)

**R-05-138** MUST — The verified HAL reaches a device register from a root device capability handed in at construction, never from a hard-coded physical address, so the RoT-attested devicetree is the sole origin of device authority.
· Accept: no physical-address literal appears in the HAL; every device capability traces to the devicetree.
· Trace: CJ-DEVTREE, CJ-HAL · [L387](verification-maximal-os.md#L387)

**R-05-139** MUST NOT — (2) No unions and no type punning: no load at a type other than its store's.
· Accept: the load rule has exactly one case; the checker rejects any load whose type differs from its store's.
· Trace: CJ-TAL-SOUND · [L388–389](verification-maximal-os.md#L388)

**R-05-140** MUST — The only admitted reinterpretation of bytes at a second type is a proved encode/decode pair derived from a declaration: the register-description language for MMIO, Narcissus for every wire format.
· Accept: every reinterpretation site traces to a generated accessor or a Narcissus codec.
· Trace: CJ-HAL, CJ-FORMAT · [L391–392](verification-maximal-os.md#L391)

**R-05-141** MUST NOT — (3) No variadic functions: a TAL code type is a register-file precondition and a variadic has none, so the construct is untypable rather than discouraged.
· Accept: no code type has non-fixed arity.
· Trace: CJ-TAL-SOUND · [L393–394](verification-maximal-os.md#L393)

**R-05-142** IS — Runtime format-string interpretation dies structurally with the variadic mechanism; the §16 bounded labeled crash record and the §12 diagnostics carry structured typed fields instead.
· Accept: no runtime format interpreter exists in any image.
· Trace: CJ-TAL-SOUND · [L396](verification-maximal-os.md#L396)

**R-05-143** MUST — (4) Every recursive type former declares a length or depth bound: bounded vectors and bounded trees, no list of unknown length, no arbitrarily deep tree.
· Accept: the checker finds no recursive former lacking its bound; the declared bound is a sound existence condition and is not sharpened (R-05-105).
· Trace: CJ-MEMPLAN, CJ-WCET · [L397–399](verification-maximal-os.md#L397)

**R-05-144** MUST NOT — (5) No implicit integer conversion: every width and signedness change is an explicit named operation.
· Accept: sign extension and truncation appear in the derivation, never in a compiler's promotion rules.
· Trace: CJ-TAL-SOUND · [L401–402](verification-maximal-os.md#L401)

**R-05-145** MUST — Arithmetic is total by typing: neither trapping nor wrapping. Overflow-freedom rides as range side conditions on the existing arithmetic rules.
· Accept: no arithmetic operation traps; no operation wraps implicitly; each arithmetic rule carries its range side condition.
· Trace: CJ-TAL-SOUND · [L401](verification-maximal-os.md#L401), [L403–404](verification-maximal-os.md#L403)

**R-05-146** MUST — Overflow side conditions are decided in the §6 checker wherever the operands' bounds are closed numerals, and descend to the CIC proof kernel as a release-time obligation wherever a bound depends on a runtime value.
· Accept: each arithmetic site has one of the two dispositions recorded; none is waived.
· Trace: CJ-TAL-SOUND · [L404](verification-maximal-os.md#L404)

**R-05-147** IS — Modular and saturating arithmetic survive as explicitly named operations; what is deleted is the implicit wrap.
· Accept: the operation vocabulary contains named wrapping and saturating forms.
· Trace: CJ-TAL-SOUND · [L406](verification-maximal-os.md#L406)

**R-05-148** MUST — All five deletions are carried to the artifact, not left as source lints: each is decidable by inspection of the derivation.
· Accept: the checker decides all five without reference to source.
· Trace: CJ-TAL-SOUND · [L407](verification-maximal-os.md#L407)

**R-05-149** IS — The cost of the five is one further narrowing of the admitted library set: no runtime check, no silicon, no new semantic anchor, no new grade axis, and no new crown jewel.
· Accept: anchor count, grade-axis count, crown-jewel count, and silicon area are unchanged.
· Trace: CJ-TAL-SOUND · [L408](verification-maximal-os.md#L408)

### 5.20 The review gate

**R-05-150** MUST — Independent specification review is a release gate.
· Accept: no release proceeds without a completed independent review of the register.
· Trace: CJ-T · [L411](verification-maximal-os.md#L411)

**R-05-151** MUST — A companion atomic-requirements register exists, in which each normative obligation is a numbered, individually-reviewable requirement with its acceptance criterion, traced to the crown-jewel spec it constrains and to the prose as rationale.
· Accept: **this document**. All eighteen normative sections are extracted; whether every obligation *within* them is captured is itself the first question the review gate asks, and the register is the artifact that makes the question answerable.
· Trace: CJ-T · [L412](verification-maximal-os.md#L412)

**R-05-152** IS — The gate audits the register; the prose specification is commentary rather than the thing reviewed.
· Accept: the review record cites requirement IDs, not prose sections.
· Trace: CJ-T · [L412](verification-maximal-os.md#L412)

**R-05-153** MUST — A normative claim that cannot be restated as an atomic, testable requirement is treated as a spec defect.
· Accept: each such claim appears in [Extraction defects](#extraction-defects) with a disposition; none is carried as unregistered prose.
· Trace: CJ-T · [L413](verification-maximal-os.md#L413)

**R-05-154** MUST — Maintaining the register and its traceability to the Coq specifications and the Sail model is a §18 workstream.
· Accept: §18 lists it as a deliverable with an owner. **See [D-06](#d-06).**
· Trace: CJ-T, CJ-SAIL · [L413](verification-maximal-os.md#L413)

**R-05-155** MUST — The foundational-C separation-logic specifications (kernel, storage, HAL) are made runtime-testable in concrete execution under the Fulminate discipline for CN.
· Accept: each such specification has an executable form run against the implementation; a mis-transcribed specification is caught by execution and not by review alone.
· Trace: CJ-KERNEL, CJ-HAL · [L414](verification-maximal-os.md#L414)

### 5.21 The apex theorem T

**R-05-156** IS — Theorem T: for the composed system image on the fabricated die, under the compose-time policy *P*, for every adversary controlling any set *C* of non-TCB compartments the graph permits, two whole-system inputs indistinguishable to *C* under *P* produce attacker-observations equal across value, timing, and the in-scope architectural channels — modulo the powerbox declassification set *D* and relative to the axiom set *Ax*.
· Accept: one theorem statement exists with all four elements: the quantifier over *C*, the value-and-timing-and-architectural observation, the *modulo D* clause, and the *relative to Ax* clause.
· Trace: CJ-T · [L417–418](verification-maximal-os.md#L417)

**R-05-157** IS — T is the formal reading of *hyper-secure* (§1) and of G2; *on the fabricated die* is what makes it a statement about the machine rather than the model.
· Accept: §1's and §3's claims cite T; no stronger informal claim appears anywhere in the specification.
· Trace: CJ-T · [L419](verification-maximal-os.md#L419)

**R-05-158** MUST — T is discharged by transporting it down the refinement tower and closing the property seams across it, in the one Iris-over-Sail program logic.
· Accept: the tower is exactly source ⊑ spec ⋈ binary ⊑ source robustly ⋈ binary-against-Sail ⋈ RTL ⊑ Sail ⋈ die-matches-RTL, the last an axiom and the rest theorems.
· Trace: CJ-T, CJ-RTL-SAIL · [L420–421](verification-maximal-os.md#L420)

**R-05-159** IS — Four unary invariants form the substrate every seam assumes: spatial safety (the Cerise universal contract), temporal safety (revocation ⋈ the CHERI-TAL linear-capability discipline), W^X (no write-and-execute capability in the derivation forest), and write-before-read (the definite-initialization attribute over eager-zeroized memory).
· Accept: each is separately stated and proved; the first three are carried by the substrate, the fourth by the admission type-check.
· Trace: CJ-CERISE, CJ-TAL-SOUND · [L422](verification-maximal-os.md#L422)

**R-05-160** IS — The seam lemmas are exactly nine: NI ⋈ timing; WCET ⋈ isolation; CT ⋈ RTL ⊑ Sail; CHERI-TAL ⋈ Sail; AE ⋈ non-interference; liveness ⋈ schedulability; consent ⋈ declassification; crypto ⋈ hardness; attestation ⋈ capability safety.
· Accept: each appears as a §17 residual and as a lemma obligation; the list is closed by amendment to this register.
· Trace: CJ-T · [L423](verification-maximal-os.md#L423)

**R-05-161** MUST — The composition meta-lemma states that the four invariants and the seam lemmas, transported through the refinement tower, entail T, and carries its own coverage obligation: no attacker-observable channel, authorized flow, timing leak, liveness stall, or admitted binary escapes their union, and each seam's conclusion is stated in the vocabulary of the next's premise.
· Accept: the coverage argument is written and reviewed; each seam's interface types are shown to meet.
· Trace: CJ-T · [L424](verification-maximal-os.md#L424)

**R-05-162** MUST — T's boundary is stated rather than hidden: it holds modulo *D* and relative to *Ax*, the hardness conjectures, the die-matches-RTL fabrication gap, specification faithfulness, human consent correctness, and invasive physical attack.
· Accept: each boundary element is a §17 residual; everything outside *D* and *Ax* is inside T.
· Trace: CJ-T · [L426](verification-maximal-os.md#L426)

---

## §6 — Trusted Computing Base

### 6.1 The exhaustive inventory

**R-06-001** IS — The TCB is exhaustively enumerated as seven items: the capability microkernel; the verified crypto core; the system-integrity reader and A/B update transactor; minimal verified M-mode firmware; the open silicon RoT and its firmware; the two admission checkers; and the powerbox with the trusted-path agent.
· Accept: nothing outside the list is trusted; an eighth item is an amendment to this register.
· Trace: CJ-T · [L432–453](verification-maximal-os.md#L432)

**R-06-002** IS — The capability microkernel is on the order of 10k LoC of verified C.
· Accept: the line count is a stated budget against the §7 target.
· Trace: CJ-KERNEL · [L432](verification-maximal-os.md#L432)

**R-06-003** MUST — The verified crypto core (boot verification, attestation, sealing) is verified C end to end: compiled through CHERI-CompCert, constant-time verified on the artifact, field-arithmetic kernels compiled the same way, reductions Coq-native in SSProve/FCF.
· Accept: no component of the core is admitted as superoptimized assembly.
· Trace: CJ-CRYPTO-SPEC, CJ-COMPCERT · [L433](verification-maximal-os.md#L433)

**R-06-004** MUST NOT — The TCB carries no *checker-admitted artifacts* category at all: the category is deleted with the kernels that motivated it rather than left unused.
· Accept: every TCB component is compiler-borne under the single Coq prover.
· Trace: CJ-COMPCERT · [L434](verification-maximal-os.md#L434)

**R-06-005** MUST — The system-integrity reader runtime-verifies every read of the content-addressed base image against the signed, boot-attested root (Merkle read-verify), and the A/B transactor commits an update as an atomic two-slot root flip past the anti-rollback floor.
· Accept: the component is on the order of 10× smaller than a filesystem; no read of the base image bypasses the check.
· Trace: CJ-DEVTREE · [L435](verification-maximal-os.md#L435)

**R-06-006** MUST — The entire four-layer storage stack is non-TCB — the read-only system image and the mutable user subvolumes alike — its journal and CoW B-tree serving bytes the reader re-verifies.
· Accept: a corrupt or hostile filesystem is caught by the signed root and is never trusted for integrity.
· Trace: CJ-DEVTREE · [L435](verification-maximal-os.md#L435)

**R-06-007** IS — Minimal verified M-mode firmware and the open silicon RoT (OpenTitan-class, integrated on-die) with its firmware are TCB items.
· Accept: both appear in the inventory with their verification evidence.
· Trace: CJ-DEVTREE · [L436–437](verification-maximal-os.md#L436)

### 6.2 The two admission checkers

**R-06-008** IS — Admission is two checkers, stratified: the CHERI-TAL type-checker runs on every install over typing derivations; the CIC proof kernel runs predominantly at release time over deep proof terms, its result bound into the measured-boot root.
· Accept: no third checker exists; no per-install path invokes the CIC kernel except for the few certificate-carrying installs (R-13-028).
· Trace: CJ-TAL-SOUND · [L438–443](verification-maximal-os.md#L438)

**R-06-009** IS — The TAL type-checker decides Tier-2 memory safety, CFI, no-codegen, ABI/type conformance, relevance-graded verdicts, absence of an ambient tagged static capability, representation and provenance absences, closed-numeral overflow side conditions, and the memory/ABI half of Tier 1. **See [D-03](#d-03).**
· Accept: its ~10³-line budget is a consequence of the frozen theory (R-05-127).
· Trace: CJ-TAL-SOUND · [L442](verification-maximal-os.md#L442)

**R-06-010** IS — The CIC proof kernel decides Tier-0 functional refinement, the non-interference theorem, crypto reductions, filesystem certificates, and residual unstructured constant-time and WCET cases.
· Accept: it is intentionally larger — universes, inductives, guard, and conversion — because seL4-scale proofs are not per-install admission work.
· Trace: CJ-NI, CJ-REDUCTION · [L443](verification-maximal-os.md#L443)

**R-06-011** IS — The admission axioms are the two checkers, the spec and policy statements, the CHERI-TAL soundness metatheorem, and the Sail model they check against. **See [D-10](#d-10).**
· Accept: the axiom inventory has exactly these entries.
· Trace: CJ-TAL-SOUND, CJ-SAIL · [L445](verification-maximal-os.md#L445)

**R-06-012** MUST — Both checkers are built like the rest of the TCB: the CIC kernel's MetaCoq-style Gallina checker and the TAL type-checker alike are refined to CompCert-C (VST/Iris) and compiled through CHERI-CompCert.
· Accept: neither is extracted via the unverified MetaCoq→Rust backend onto the untrusted userspace toolchain; that toolchain is admissible only for contained code whose binary a checker re-validates, and the checkers' own binaries are re-validated by nothing.
· Trace: CJ-COMPCERT · [L446](verification-maximal-os.md#L446)

**R-06-013** IS — The checkers' compilation is not a fresh axiom: it rides the same CompCert already in the trust base.
· Accept: the axiom count is unchanged by their compilation.
· Trace: CJ-COMPCERT · [L447](verification-maximal-os.md#L447)

**R-06-014** IS — The one irreducible residual is the bootstrap: the checkers are the admitters no admission certificate can cover, and they co-bootstrap with the CompCert that compiles them, so their binaries' trust rests on reproducible build plus DDC plus RoT measurement into the boot chain — the De Bruijn root, named as an axiom rather than hidden.
· Accept: the axiom is stated in §6 and §17, not implied.
· Trace: CJ-T · [L448](verification-maximal-os.md#L448)

**R-06-015** IS — The toolchain is untrusted evidence-producing machinery: a compromised compiler cannot mint a valid proof of a property its output lacks, so at worst it emits a binary genuinely satisfying the spec, confining trojans to spec slack.
· Accept: this is why Tier-0 specs are full refinements (R-13-011).
· Trace: CJ-COMPCERT · [L449](verification-maximal-os.md#L449)

### 6.3 The consent TCB

**R-06-016** IS — The powerbox is the sole runtime declassifier, and the trusted-path agent is the small component that owns its consent UI and drives the RoT secure-attention indicator.
· Accept: no other component mints a capability edge at runtime.
· Trace: CJ-NI · [L450](verification-maximal-os.md#L450)

**R-06-017** MUST — Their load-bearing correctness obligation is exactly two clauses: mint only on witnessed consent, and bound the mint to the named object.
· Accept: both clauses are proved; the §8 non-interference theorem's *user-authorized* flows rest on them.
· Trace: CJ-NI · [L451](verification-maximal-os.md#L451)

**R-06-018** IS — Their failure cannot be contained by CHERI the way an in-model memory fault can, a wrongful declassification being a legitimate capability operation; blast radius is minimized by attenuation, the powerbox holding only the authority from which grants are attenuated.
· Accept: the consent TCB is named in §6 rather than hidden in userland, and booked in §17.
· Trace: CJ-NI, CJ-CERISE · [L451–452](verification-maximal-os.md#L451)

**R-06-019** MUST NOT — The touch driver stays outside the trusted set: the consent path takes RoT-latched ownership of the input front-end for the prompt's duration rather than trusting the compartment that normally holds it.
· Accept: what the trusted set gains at the input edge is a fixed threshold-and-centroid reducer, not a programmable touch DSP.
· Trace: CJ-DEVTREE · [L453](verification-maximal-os.md#L453)

### 6.4 Stated non-members

**R-06-020** IS — The verified HAL is a contained, non-TCB artifact: it is proven, but verification is not TCB membership, and its failure is bounded by CHERI, capability-checked DMA, and capability confinement like any other compartment.
· Accept: it is listed in §6 only to state explicitly that it does not join the TCB.
· Trace: CJ-HAL · [L455–456](verification-maximal-os.md#L455)

**R-06-021** IS — The entire radio stack — PHY, L2/L3, and key management — is contained compartments and none of it is TCB.
· Accept: the TCB inventory names no radio component.
· Trace: CJ-CERISE · [L457](verification-maximal-os.md#L457)

**R-06-022** IS — The rollback-manager UI drives the trusted rollback path but is not part of it: the system-integrity reader, the A/B transactor, and the RoT enforce the signed-root check and the anti-rollback floor whatever the UI requests.
· Accept: a compromised manager can mislead its own display but never enact a rollback the transactor would refuse.
· Trace: CJ-DEVTREE · [L458](verification-maximal-os.md#L458)

**R-06-023** IS — Everything else — drivers, filesystems, network, display, radio, userland — is outside the TCB and secured by containment; the sole userland-resident exception is the consent TCB.
· Accept: the inventory is closed by R-06-001.
· Trace: CJ-CERISE · [L460](verification-maximal-os.md#L460)

### 6.5 Required but untrusted build artifacts

**R-06-024** MUST — Four artifacts are hard prerequisites and all are untrusted evidence-producing machinery: (1) CompCert with a CHERI-RISC-V backend satisfying the secure-compilation criterion; (2) a certifying Rust→RV64+CHERI compiler emitting per-binary memory-safety certificates; (3) a WCET cost-annotation pass in the certifying toolchain; (4) constant-time verification for every secret-touching binary.
· Accept: each appears in §18 as an in-scope workstream and in no consumer-side TCB inventory.
· Trace: CJ-COMPCERT, CJ-WCET, CJ-CT-SOUND · [L462](verification-maximal-os.md#L462)

**R-06-025** IS — Artifact (1) does not exist yet and the platform is purecap-only, so nothing boots without it.
· Accept: the dependency is stated as blocking rather than aspirational.
· Trace: CJ-COMPCERT · [L462](verification-maximal-os.md#L462)

**R-06-026** MUST NOT — A fifth entry, the CryptOpt-style verified translation-validation toolchain for the crypto core's field arithmetic, is deleted rather than deferred and is named in §6 so its absence is legible.
· Accept: with it go a net-new Coq development, the checker-admitted-artifacts TCB category, and a §18 workstream.
· Trace: CJ-CRYPTO-SPEC · [L463](verification-maximal-os.md#L463)

**R-06-027** IS — Constant-time verification degrades gracefully: bounded Binsec/Rel evidence carries bring-up, and the taint-typing plus residual certificate close it.
· Accept: the bring-up path is evidence-tier and the closing path is proof-tier, with both recorded.
· Trace: CJ-CT-SOUND · [L462](verification-maximal-os.md#L462)

---

## §7 — Kernel

### 7.1 Object model and allocation

**R-07-001** MUST — The kernel is a verified capability microkernel, seL4's design re-proved end-to-end in Coq, targeting ≤10k lines.
· Accept: the line count is measured against the shipped source; CertiKOS supplies the proof method, not the kernel.
· Trace: CJ-KERNEL · [L470](verification-maximal-os.md#L470)

**R-07-002** MUST — Untyped memory: there is zero kernel allocation after boot, and all kernel-object memory is delegated from userland via capabilities.
· Accept: no allocator exists in the kernel; the allocator bug classes are absent rather than bounded.
· Trace: CJ-KERNEL · [L471–472](verification-maximal-os.md#L471)

### 7.2 Multikernel

**R-07-003** IS — The microkernel is one verified artifact instantiated once per core: identical text, verified once and duplicated per core, with strictly disjoint state — each instance owning its capability tables, scheduler, and untyped pool.
· Accept: duplication is for NUMA locality and bit-flip blast-radius containment.
· Trace: CJ-KERNEL · [L473](verification-maximal-os.md#L473)

**R-07-004** MUST NOT — There is no shared mutable kernel data and there are no kernel locks: each instance's proof is the *sequential* proof, parametric over its resource assignment.
· Accept: verified fine-grained SMP is sidestepped, not attempted.
· Trace: CJ-KERNEL · [L474](verification-maximal-os.md#L474)

**R-07-005** MUST — Physical memory and devices are statically partitioned among instances at composition, where disjointness is machine-checked.
· Accept: the disjointness check is a build-time artifact, not a review.
· Trace: CJ-KERNEL, CJ-MEMPLAN · [L475](verification-maximal-os.md#L475)

**R-07-006** MUST — Composition-time disjointness is enforced at runtime by CHERI bounds: each core's kernel instance is delegated a root capability bounded to its own physical partition, and monotonicity lets it derive nothing outside that partition plus the statically declared shared windows.
· Accept: the root capability's bounds are the partition's.
· Trace: CJ-CERISE · [L476](verification-maximal-os.md#L476)

**R-07-007** IS — Exactly three things cross cores: hardware IPIs signaling local notification objects; user-level rings over designated shared windows; and capability transfer along statically declared cross-core grant edges.
· Accept: a fourth cross-core mechanism is an amendment.
· Trace: CJ-KERNEL · [L477](verification-maximal-os.md#L477)

**R-07-008** IS — A uniprocessor build remains the minimal-proof variant.
· Accept: the build is retained and provable independently.
· Trace: CJ-KERNEL · [L478](verification-maximal-os.md#L478)

**R-07-009** IS — The multikernel is *not* the confidentiality-isolation boundary; what the share-nothing structure adds is fault containment, authority containment, and the deletion of cross-core lock-contention and shared-structure timing channels.
· Accept: spatial isolation is CHERI's, timing-channel deletion is the islands' and the microarchitecture's.
· Trace: CJ-CERISE, CJ-ISOL · [L479–484](verification-maximal-os.md#L479)

**R-07-010** IS — The share-nothing kernel is *entailed* by the island memory partition, not merely permitted: across islands there is no shared mutable memory, so a shared-mutable-state kernel is not implementable.
· Accept: consistent with R-15-223.
· Trace: CJ-ISOL · [L485](verification-maximal-os.md#L485)

**R-07-011** IS — As a backstop the structure is real but scoped: the shared-state-concurrency class of non-interference violations is architecturally absent, yet the structure is common-mode against a flaw in the shared Sail model, the CHERI semantics, the per-instance sequential proof, or the capability-distribution spec.
· Accept: the common-mode statement is recorded rather than implied.
· Trace: CJ-NI, CJ-SAIL · [L486](verification-maximal-os.md#L486)

**R-07-012** IS — The kernel is scalar-only code: one binary runs unmodified on every core class, the per-instance proof parametric over resource assignment and datapath class, with the only class-visible obligation being gating vector/matrix state (`mstatus.VS/XS`) at partition setup.
· Accept: classes differ only below the ISA waterline the kernel occupies.
· Trace: CJ-KERNEL, CJ-SAIL · [L487–489](verification-maximal-os.md#L487)

**R-07-013** MUST NOT — There is no dynamic migration between core classes; big.LITTLE-style HMP migration is rejected outright, and assignment is a composition-time decision.
· Accept: no mechanism exists to drag VLEN-scale register state across the die, so per-core uniprocessor schedulability analysis holds and no migration-timing channel exists.
· Trace: CJ-WCET, CJ-NI · [L490–491](verification-maximal-os.md#L490)

### 7.3 Switch discipline

**R-07-014** MUST NOT — There is no lazy vector/matrix unit switching, ever: lazy unit-ownership trapping is a cross-domain timing channel.
· Accept: either a V/M-class core is statically pinned to a single domain, or partition switches perform eager save-and-zeroize of vector RF, vector CSRs, and scratchpad, WCET-accounted in the switch budget.
· Trace: CJ-NI, CJ-WCET · [L492–494](verification-maximal-os.md#L492)

**R-07-015** MUST — The scalar and capability register restore is *total*: every general-purpose register, capability register, and CSR a partition can name is written by the switch before the successor partition's first instruction.
· Accept: residue is impossible rather than cleared; the register set is enumerated and argued closed, and a register outside the restore set is a proof failure.
· Trace: CJ-KERNEL, CJ-ISOL · [L495–498](verification-maximal-os.md#L495)

**R-07-016** IS — That totality is the obligation that replaces register-file membership in the `fence.t` flush set, which §15 declines under *verify rather than hedge*.
· Accept: the guarantee is stated once, where the kernel proof discharges it, rather than twice (R-15-214).
· Trace: CJ-ISOL · [L497](verification-maximal-os.md#L497)

**R-07-017** MUST — Power gating is permitted only when the remaining slot ≥ the gate's entry+exit WCET; operating-point changes occur only at partition switches from the composition-time assignment, their relock cost folded into the switch budget.
· Accept: the kernel never selects power states from load; there is no governor, in the kernel or anywhere else.
· Trace: CJ-WCET · [L499–502](verification-maximal-os.md#L499)

### 7.4 Privilege

**R-07-018** IS — The platform runs Machine mode only: privileged authority (control/status registers, interrupt-enable, context-switch and sealing primitives) is gated by the access-system-registers permission on the executing PCC, not by a hardware ring.
· Accept: there is no S-mode and no U-mode.
· Trace: CJ-CERISE, CJ-KERNEL · [L503–505](verification-maximal-os.md#L503)

**R-07-019** MUST — The boot/M-mode firmware runs first, establishes the initial capability distribution (deriving each core's partition-bounded root capability), then goes quiescent with no SMM-analog resident handler.
· Accept: no firmware code is resident after handoff.
· Trace: CJ-KERNEL · [L506](verification-maximal-os.md#L506)

**R-07-020** IS — The microkernel is the sole resident code holding the system-register permission and the switch/seal authority: event-driven, with no kernel threads, executing on the caller's budget.
· Accept: no kernel thread exists in the object inventory.
· Trace: CJ-KERNEL · [L507](verification-maximal-os.md#L507)

**R-07-021** MUST — The kernel is entered for exactly two reasons: a synchronous exception or syscall on the running instruction, and the slot-boundary timer.
· Accept: the kernel proof carries no *device-MSI-lands-mid-syscall* interleaving case at any entry point.
· Trace: CJ-KERNEL · [L507](verification-maximal-os.md#L507)

**R-07-022** IS — The trap path carries capabilities, not integer addresses: taking a trap installs `MTCC` as the executing PCC, saves the interrupted PCC as `MEPCC`, and bootstraps the handler's authority from `MTDC`.
· Accept: consistent with R-15-073.
· Trace: CJ-CERISE · [L508](verification-maximal-os.md#L508)

**R-07-023** MUST — Every compartment runs in the same Machine mode *without* the system-register permission, isolated by CHERI capabilities alone; a compartment cannot execute a privileged CSR access because its PCC lacks the permission, an unforgeable condition rather than a mode check.
· Accept: privilege escalation has no ring to target.
· Trace: CJ-CERISE · [L509–510](verification-maximal-os.md#L509)

**R-07-024** MUST NOT — Nothing else is resident beside the kernel: no hypervisor tenant, no privileged daemon, and no power-management firmware.
· Accept: the resident-code inventory has one entry.
· Trace: CJ-KERNEL · [L511](verification-maximal-os.md#L511)

### 7.5 Static composition

**R-07-025** MUST — The component graph and capability distribution are fixed and machine-checked at build time; there is no dynamic privilege creation in the base.
· Accept: what is fixed is the composed topology and the confidentiality-label lattice.
· Trace: CJ-NI, CJ-KERNEL · [L513–514](verification-maximal-os.md#L513)

**R-07-026** IS — The one sanctioned runtime authority transfer is the powerbox declassification, which extends the *live* edge set at a single verified point without minting a new privilege class or a new label; the §12 supervision tree's restart re-grant only re-instantiates edges the manifest already fixed.
· Accept: neither operation adds a node or a label to the composed graph.
· Trace: CJ-NI · [L514](verification-maximal-os.md#L514)

**R-07-027** MUST — The §12 IDL worlds and interfaces lower to a capDL-class capability-distribution spec: kernel-object-granular, re-homed to Coq, extended so cap edges carry CHERI-bounds grants, and stripped of the VSpace, page-table, and frame-mapping object classes.
· Accept: the spec is a Coq artifact, not a documentation format.
· Trace: CJ-IDL, CJ-KERNEL · [L515](verification-maximal-os.md#L515)

**R-07-028** MUST — The capability-distribution spec carries an initialisation-refinement obligation: the M-mode firmware that installs the distribution is proved to instantiate exactly the composed cap graph as running kernel state.
· Accept: *machine-checked at build time* is joined by *machine-checked as installed*, closing the gap between the composed graph and the booted machine.
· Trace: CJ-KERNEL · [L516](verification-maximal-os.md#L516)

### 7.6 IPC

**R-07-029** IS — IPC is synchronous endpoints plus notifications, with all capability transfer explicit; the kernel carries control, never bulk data, high-throughput I/O riding user-level rings.
· Accept: no bulk-data path traverses privileged code.
· Trace: CJ-KERNEL · [L517–518](verification-maximal-os.md#L517)

**R-07-030** MUST NOT — No io_uring-style opcode surface re-enters privileged code.
· Accept: the kernel ABI admits no submission-queue opcode dispatch.
· Trace: CJ-KERNEL · [L518](verification-maximal-os.md#L518)

**R-07-031** IS — The kernel ABI is the capability primitives alone: on the order of a dozen invocations, formally specified and frozen with the proof; kernel messages are registers plus capability slots, never typed structured data.
· Accept: rich interfaces live one layer up in §12.
· Trace: CJ-KERNEL, CJ-IDL · [L519–520](verification-maximal-os.md#L519)

### 7.7 Scheduling

**R-07-032** MUST — Each core runs a table-driven static cyclic executive: a composition-time schedule of fixed, time-triggered slots, with no priorities, no scheduling-context capabilities, no budget donation, and no runtime scheduling decision.
· Accept: temporal authority is fixed at composition, not a runtime capability.
· Trace: CJ-WCET · [L521–522](verification-maximal-os.md#L521), [L529](verification-maximal-os.md#L529)

**R-07-033** IS — Temporal isolation *is* the slot: a partition runs only in its assigned slots and cannot overrun them, the timer switching at the boundary, so a spinning compartment wastes only its own time.
· Accept: overrun is prevented by mechanism, not convention.
· Trace: CJ-ISOL · [L523](verification-maximal-os.md#L523)

**R-07-034** MUST — Aperiodic events get dedicated polling or sporadic slots sized into the frame, unless the cadence a deadline demands would make the partition-switch constant itself a dominant budget term, in which case the server leaves the slot wheel and is pinned to its own core.
· Accept: the radio PHY pair and the sentinel are instances of that general rule, not exceptions to it (R-15-114).
· Trace: CJ-WCET · [L523](verification-maximal-os.md#L523)

**R-07-035** MUST NOT — seL4's MCS machinery is deleted: scheduling contexts, budget and period capabilities, passive-server donation, and timeout faults.
· Accept: §11 schedulability collapses from response-time analysis to an interval-arithmetic check — the slot WCETs fit the major frame, and each task's period is harmonic with it.
· Trace: CJ-WCET · [L524](verification-maximal-os.md#L524)

**R-07-036** MUST — Across confidentiality boundaries the schedule is non-work-conserving: an idle slot stays idle rather than yielding, so no slack ever crosses a partition boundary.
· Accept: there is no donation mechanism for slack to leak through.
· Trace: CJ-NI, CJ-ISOL · [L526](verification-maximal-os.md#L526)

**R-07-037** IS — Because the frame divides rather than shares, compartment population is a first-class schedule parameter: a partition's capacity *is* its slot width, and the number of compartments on one core's wheel is a composition constant with a hard ceiling rather than a soft degradation curve.
· Accept: §11 makes population its own schedule axis — a proved rung ladder, distinct from the global mode transition and deliberately not rare — and §17 books what the division costs and what the rung index leaks.
· Trace: CJ-WCET, CJ-NI · [L527–528](verification-maximal-os.md#L527)

### 7.8 Interrupts

**R-07-038** MUST NOT — Asynchronous interrupt delivery does not exist: an MSI sets a pending bit and does nothing else, and no pending bit ever vectors the core to `MTCC`.
· Accept: no fetch is disturbed, no slot boundary moves, and no runtime scheduling decision is created.
· Trace: CJ-KERNEL, CJ-ISOL · [L530–532](verification-maximal-os.md#L530)

**R-07-039** MUST — A partition consumes its pending bits by reading them, with ordinary loads at poll sites inside its own slots.
· Accept: the trap path is entered only synchronously or by the boundary timer.
· Trace: CJ-KERNEL · [L533](verification-maximal-os.md#L533)

**R-07-040** IS — The slot-boundary timer is the machine's sole asynchronous trap, and it is irreducible and unmaskable: irreducible because it makes *a partition cannot overrun its slot* a mechanism rather than a convention, unmaskable because it needs no enable bit to protect it.
· Accept: the switch completes at the §15 padded constant and the timer does not re-arm until the handler reprograms `mtimecmp`.
· Trace: CJ-ISOL, CJ-WCET · [L534](verification-maximal-os.md#L534)

**R-07-041** IS — Interrupt masking has nothing left to govern, so the interrupt-state sentry types and their statically-auditable bounded interrupt-disabled-window allow-list are deleted rather than audited.
· Accept: a bounded obligation (*is the mask window short enough?*) is traded for an absence checked structurally (R-15-070).
· Trace: CJ-SAIL · [L535](verification-maximal-os.md#L535)

**R-07-042** IS — Worst-case device service latency is a schedule corollary, not an interrupt property: an event waits at most its owning server's slot period plus its in-slot handling WCET, and §11 sizes each device's poll cadence or sporadic slot to its deadline.
· Accept: the rule holds without exception.
· Trace: CJ-WCET · [L536](verification-maximal-os.md#L536)

**R-07-043** IS — No WCET carries a preemption term at all, rather than carrying a bounded one: with no trap point at every instruction boundary, the remaining trap points are syntactic poll sites already in the typed control-flow graph.
· Accept: the derivation loses a term instead of bounding it.
· Trace: CJ-WCET · [L537](verification-maximal-os.md#L537)

**R-07-044** MUST — Per-partition interrupt-file pending bits are statically identity-partitioned or swapped at the switch, in the switch budget, so no interrupt state is hidden or shared across a partition boundary.
· Accept: §15 admission test 3 is satisfied for interrupt state; there are no enable bits left to swap.
· Trace: CJ-ISOL · [L538](verification-maximal-os.md#L538)

**R-07-045** IS — All interrupts are MSIs and wired level interrupts do not exist: the RoT watchdog's *bark* is an ordinary MSI into the sentinel's interrupt file, and only the *bite* and the RoT's reset and power-sequencing lines are non-MSI signals — resets, not interrupts, unmaskable by construction.
· Accept: nothing the watchdog or the boot chain depends on rides an interrupt-enable bit.
· Trace: CJ-DEVTREE · [L539–540](verification-maximal-os.md#L539)

**R-07-046** MUST — The bark is read, not delivered, and is checked in the boundary-timer handler, bounding notice at one slot period; if even the boundary path is dead, the bite is the sub-slot backstop.
· Accept: the bark's purpose is to reach a core that is alive but wedged, which polling by definition cannot.
· Trace: CJ-DEVTREE · [L541–542](verification-maximal-os.md#L541)

**R-07-047** IS — This is the one place the delivery deletion genuinely costs response time, and it is booked in §17 rather than absorbed.
· Accept: the residual entry exists.
· Trace: CJ-WCET · [L543](verification-maximal-os.md#L543)

### 7.9 Purecap kernel and proof structure

**R-07-048** MUST — The kernel compiles to pure-capability code: its own pointers are hardware capabilities, so a flipped bit clears the validity tag or lands outside bounds and faults rather than resolving to a live address.
· Accept: the guarantee is the tag and bounds check itself; no encryption avalanche is credited, the memory path carrying none.
· Trace: CJ-CERISE · [L544–546](verification-maximal-os.md#L544)

**R-07-049** IS — The purecap cost is that the proof runs over CHERI-C semantics, so the residual is the capability-widened CompCert memory model and this kernel's refinement over it rather than the CHERI-C semantics itself; kernel pointers double in width, and the kernel depends on the §6 CHERI backend.
· Accept: the residual is booked in §17 as a narrower spec-gap surface than a from-scratch mechanization.
· Trace: CJ-COMPCERT · [L547](verification-maximal-os.md#L547)

**R-07-050** MUST — The trap, context-switch, and IPC fast path is verified directly at binary level against the Sail model in the one Iris-over-Sail program logic, not through the CHERI-C → CompCert-memory-model refinement.
· Accept: the fast path's proof mentions only the Sail operational semantics and the capability invariants, so the capability-widened CompCert memory model is off its trust path entirely.
· Trace: CJ-SAIL, CJ-KERNEL · [L548–550](verification-maximal-os.md#L548)

**R-07-051** IS — The cold paths (setup, rare object operations) stay verified C through CHERI-CompCert, where the CHERI-C convenience is worth the seam.
· Accept: only the hot, tiny, most-critical path pays for a direct binary-level proof.
· Trace: CJ-COMPCERT · [L551](verification-maximal-os.md#L551)

**R-07-052** MUST — Single address space: the kernel drops seL4's VSpace, page-table, and frame-mapping object classes entirely, and CHERI bounds are the sole in-core spatial isolation.
· Accept: the map/unmap invocations, the page-table walk, `satp` switching, and TLB-shootdown paths and their proofs are gone rather than verified; frames become capability-bounded physical ranges delegated from untyped memory.
· Trace: CJ-KERNEL, CJ-CERISE · [L552–555](verification-maximal-os.md#L552)

---

## §8 — Authority Model

### 8.1 Capabilities as the sole authority

**R-08-001** MUST NOT — Capabilities are the sole authority: there is no ambient authority anywhere — no global namespaces, no uid/gid, no setuid, no `fork()`.
· Accept: no authority is reachable except through a held capability.
· Trace: CJ-CERISE · [L562–563](verification-maximal-os.md#L562)

**R-08-002** IS — The layer rule is completed by §5's language rule deleting ambient *state*, because a language free to re-manufacture a global above the OS and hardware layers reintroduces the unaccounted authority path both deleted.
· Accept: R-05-086 is the discharge; the grading disciplines that reason over a typing context can see all authority.
· Trace: CJ-TAL-SOUND · [L564](verification-maximal-os.md#L564)

**R-08-003** IS — At the hardware layer, CHERI capabilities backstop `unsafe` Rust and residual C, and this extends unchanged to V/M-class cores: vector and matrix memory operations are checked against explicit capability operands of the issuing context, per-element for indexed and gather-scatter access.
· Accept: accelerator-class compute inherits the full spatial-safety story rather than a device-side approximation.
· Trace: CJ-CERISE · [L565–566](verification-maximal-os.md#L565)

### 8.2 Revocation

**R-08-004** MUST — The kernel layer provides object capabilities with first-class revocation (derivation-tree revoke plus CHERI sweep) running within a guaranteed time bound, so time-to-containment is a bounded constant — including the distributed case, where capabilities delegated over cross-core grant edges revoke via a verified bounded-round protocol.
· Accept: the bound is stated per composition and enters the §11 schedule.
· Trace: CJ-CERISE, CJ-WCET · [L567–568](verification-maximal-os.md#L567)

**R-08-005** MUST — *Freed ⇒ unreachable* holds at *access* time, not only at sweep completion: a per-load revocation check (load filter or barrier) invalidates a stale capability the moment it is loaded.
· Accept: the check is deterministic and architectural, fixed-latency, riding the load with no added memory traffic, so it passes the §15 admission test.
· Trace: CJ-CERISE, CJ-LEAK · [L569](verification-maximal-os.md#L569)

**R-08-006** IS — Containment and reclamation split: containment is the revocation-epoch advance the load filter checks against — a register-write-class constant, microseconds — while the sweep is reclamation, milliseconds to seconds of memory traffic that no security property waits on.
· Accept: the bounded constant claimed in R-08-004 is the epoch flip, not sweep completion.
· Trace: CJ-CERISE · [L570–571](verification-maximal-os.md#L570)

**R-08-007** MUST — The sweep runs as an incremental, preemptible kernel task in its own §11-admitted background slot class, per core, sized at composition, never in another partition's time.
· Accept: its completion latency is a derived per-domain constant — the domain's capability-bearing footprint over the per-frame sweep quantum.
· Trace: CJ-WCET · [L572](verification-maximal-os.md#L572)

**R-08-008** MUST — Forced-sweep denial of service is priced out structurally: revocation is triggered only by kernel-mediated teardown, so a compartment that churns grants forces sweeps only of its own footprint, paid from its own and the sweeper's fixed slots.
· Accept: the cost of queued sweeps is delayed reclamation of the *requester's* quarantined memory, bounded by the composition-sized quarantine pool, never schedule perturbation of any hard task.
· Trace: CJ-WCET, CJ-ISOL · [L573](verification-maximal-os.md#L573)

**R-08-009** MUST NOT — The autonomous background engines a CHERI microcontroller ships for this purpose (CHERIoT-Ibex TBRE revocation-sweep and STKZ stack-zeroing) are declined as autonomous memory-touching walkers under admission test 5; only the deterministic load filter is imported and the sweep stays software.
· Accept: no engine walks memory on its own.
· Trace: CJ-SAIL · [L574](verification-maximal-os.md#L574)

### 8.3 The static memory plan

**R-08-010** MUST — The heap is compiled, not allocated at runtime: a whole-program static memory plan replaces the online allocator, so at runtime allocation is the read of a pre-assigned slot.
· Accept: no allocator component exists; no online packing exists for Robson's worst case to act upon.
· Trace: CJ-MEMPLAN · [L575–578](verification-maximal-os.md#L575)

**R-08-011** IS — Linear/affine ownership fixes each object's live range at compile time and region inference fixes its allocation and free points, expressed against the capability substrate as the calculus-of-capabilities region discipline whose static tokens this design realizes at runtime as CHERI capabilities.
· Accept: the compiler emits a static slot assignment carried in the CHERI-TAL derivation.
· Trace: CJ-MEMPLAN, CJ-TAL-SOUND · [L577–578](verification-maximal-os.md#L577)

**R-08-012** IS — Fragmentation collapses at three points: external fragmentation is deleted rather than bounded, over-reservation collapses to the proven simultaneous peak by live-range colouring, and size-class internal fragmentation is deleted by exact-size slots.
· Accept: the footprint is peak-liveness, the minimum any non-moving scheme can use.
· Trace: CJ-MEMPLAN · [L579](verification-maximal-os.md#L579)

**R-08-013** IS — Offline is the whole game: online allocation carries Robson's Θ(log n) worst case, while the offline problem is NP-hard in general, constant-factor approximable, and exactly optimal in polynomial time for the nested, region-structured lifetimes a region discipline produces — all solved in build-time compute.
· Accept: static composition is what buys the move from the Robson-hard online setting to the near-optimal offline one.
· Trace: CJ-MEMPLAN · [L580–582](verification-maximal-os.md#L580)

**R-08-014** MUST — The plan is checked, not trusted: slot disjointness over disjoint live ranges is a decidable interference side-condition of the on-device TAL type-check, so an overlap is a type error and a bad plan is rejected, never admitted unsafe.
· Accept: nothing joins the TCB and nothing runs at allocation time; there is no free-set proof to ship.
· Trace: CJ-TAL-SOUND, CJ-MEMPLAN · [L583–584](verification-maximal-os.md#L583)

**R-08-015** MUST — Temporal safety at a slot's reuse points composes with the plan: the load filter and revocation epoch invalidate any capability to a slot's prior tenant before the next is installed.
· Accept: placement ⋈ temporal-safety, with the escape bounded by the same region and ownership discipline that fixed the live ranges.
· Trace: CJ-CERISE, CJ-MEMPLAN · [L585](verification-maximal-os.md#L585)

**R-08-016** IS — Placement, disjointness, and initialization are three attributes over one interference structure, all checked in the same on-device pass and all rejecting a bad artifact rather than trapping a bad execution.
· Accept: each slot enters its live range uninitialized, eager-zeroize makes that state a deterministic zero, and the definite-initialization attribute decides that no load precedes a store within the range.
· Trace: CJ-TAL-SOUND, CJ-MEMPLAN · [L586](verification-maximal-os.md#L586)

**R-08-017** IS — Memory-admissible ⟺ time-admissible: the peak-memory bound and the WCET bound are read off the same static facts, so the memory admission test is the space projection of the §11 schedulability certificate, not a second test.
· Accept: one static-boundedness certificate, two resources.
· Trace: CJ-WCET, CJ-MEMPLAN · [L587–588](verification-maximal-os.md#L587)

**R-08-018** IS — The runtime-count-dependent case folds in as the degenerate plan: a bounded fan-out is N pre-coloured equal-size slots whose occupancy is 0..N, so the dynamism is *which* slots are live, never *where* an object lands.
· Accept: a zero-fragmentation pool, the degenerate interference graph of N mutually-live cells.
· Trace: CJ-MEMPLAN · [L589](verification-maximal-os.md#L589)

**R-08-019** IS — The honest ceiling is a footprint statically bounded yet far above its average, met by the standing capacity-versus-determinism posture: bend capacity, restructure to a streamed bound, or refuse.
· Accept: it is the same ceiling every other subsystem meets, not a new one.
· Trace: CJ-MEMPLAN · [L590](verification-maximal-os.md#L590)

**R-08-020** MUST NOT — Compaction and relocation never arise: there is nothing to move at runtime because the packing already happened at compile time.
· Accept: no relocation mechanism exists.
· Trace: CJ-MEMPLAN · [L591](verification-maximal-os.md#L591)

### 8.4 Non-interference

**R-08-021** IS — The static capability topology defines the flow policy: a component at confidentiality level H may not influence a component at level L unless an explicit inter-level channel capability exists.
· Accept: the policy is read off the composed graph, not configured.
· Trace: CJ-NI · [L592–593](verification-maximal-os.md#L592)

**R-08-022** MUST — The kernel's Coq proof is extended to a non-interference theorem over that fixed graph, over the multikernel composition, the purecap CHERI-C semantics, and the powerbox's robust declassification, and it is a *fresh* proof rather than an inherited one.
· Accept: what carries over from seL4-NI is the method of stating and discharging NI over a capability graph, not the proof's maturity; the freshness is booked in §17.
· Trace: CJ-NI · [L594](verification-maximal-os.md#L594)

**R-08-023** IS — The theorem is about the existing structure, not a new mechanism.
· Accept: no runtime component is added to make it hold.
· Trace: CJ-NI · [L595](verification-maximal-os.md#L595)

**R-08-024** IS — The theorem is non-interference *modulo robust, delimited declassification*: the fixed graph fixes the label lattice and the set of declassification points, not a frozen edge set for all time.
· Accept: the one point at which the live flow relation may extend past the compose-time manifest is the powerbox, a single component statically present in the graph.
· Trace: CJ-NI · [L596–597](verification-maximal-os.md#L596)

**R-08-025** MUST — A user grant is modeled as a delimited release the theorem quantifies over, and the theorem's content is robust declassification: over *all* strategies of a compromised component, none can influence whether, what, or to whom the powerbox declassifies.
· Accept: that decision depends only on the unforgeable consent act and the powerbox's verified logic.
· Trace: CJ-NI · [L598](verification-maximal-os.md#L598)

**R-08-026** MUST — The only permitted extension is a powerbox grant CHERI-bounded to the user-named object, so the granted channel carries that object alone and is no general H→L conduit.
· Accept: user-authorized flow is inside the theorem — neither near-vacuously admitted nor left outside it.
· Trace: CJ-NI, CJ-CERISE · [L599](verification-maximal-os.md#L599)

**R-08-027** IS — The theorem covers explicit information flow; the timing side is closed separately by the formal isolation semantics of the §15 partitioning hardware, the two designed to compose into one partition-level guarantee.
· Accept: the seam is the NI ⋈ timing lemma (R-05-160).
· Trace: CJ-NI, CJ-ISOL · [L600](verification-maximal-os.md#L600)

**R-08-028** IS — The security policy model, including the delimited-release bound and the robust-declassification statement, is a crown-jewel spec.
· Accept: it appears in the crown-jewel inventory and is subject to independent review.
· Trace: CJ-NI · [L601](verification-maximal-os.md#L601)

**R-08-029** IS — Declassification is explicit capability use of exactly two kinds: the compose-time kind, manifest-declared as an edge in the capDL-class spec and covered by the base theorem directly; and the runtime kind, the powerbox grant, the sole source of an inter-level edge not in the manifest.
· Accept: no additional primitive is needed for either; capability use *is* declassification, already gated and auditable.
· Trace: CJ-NI, CJ-KERNEL · [L602–606](verification-maximal-os.md#L602)

**R-08-030** MUST NOT — Dynamic information-flow control, if ever needed, is a Tier-1 server and never a kernel extension.
· Accept: the kernel tracks no labels; its trusted state does not grow.
· Trace: CJ-KERNEL · [L607–608](verification-maximal-os.md#L607)

### 8.5 Authority over time and interrupts

**R-08-031** MUST — Clock read-out is authority: a compartment reads the cycle and time counters only if its PCC carries the access-to-system-registers permission, and the monitor gets nanoseconds.
· Accept: the permission gate is R-15-077. There is **no clock-degradation mechanism**: a compartment without the permission has no counter, so its only time source is the time service over a ring serviced in its own slot, and the finest interval it can observe is its own slot period — a composition-time constant. No value is fuzzed, nothing is drawn, and no component owns a degradation.
· Trace: CJ-NI · [L609–611](verification-maximal-os.md#L609)

**R-08-031a** MUST NOT — Statistical clock degradation (jitter added to a counter read) is inadmissible on the same ground MTE and MBPTA/EVT are: it is recoverable by averaging over repeated reads, a statistic rather than a theorem.
· Accept: no admitted mechanism degrades a timing value probabilistically; the residual an untrusted compartment retains is the already-booked §11 population-rung channel (R-17-007), not a new exposure.
· Trace: CJ-NI · [L609–611](verification-maximal-os.md#L609)

**R-08-032** MUST — Interrupt-send is authority: an interrupt is a store to an interrupt file, so *who may interrupt whom* is a write capability in the static capability topology rather than a separate routing table. Interrupt-receive is a load from state the partition already owns and needs no separate authority.
· Accept: no interrupt-routing side table exists.
· Trace: CJ-CERISE · [L612](verification-maximal-os.md#L612), [L616](verification-maximal-os.md#L616)

**R-08-033** IS — There is no authority to *disable* interrupts, because there is no asynchronous delivery to disable: the attack the interrupt-state sentry discipline existed to stop is absent rather than bounded, and its two lemmas are vacuous rather than discharged.
· Accept: the boundary timer is unmaskable by construction, so the overhang is zero rather than capped (R-07-041).
· Trace: CJ-KERNEL · [L613–615](verification-maximal-os.md#L613)

**R-08-034** MUST — Every app ships a capability manifest wired at compose time, and an app's manifest may declare an internal compartment graph with per-library sub-manifests, so least authority binds within an app and not only at its edge.
· Accept: the manifest is the authority record checked at admission (R-13-024).
· Trace: CJ-CERISE · [L617](verification-maximal-os.md#L617)

### 8.6 The powerbox

**R-08-035** MUST — The powerbox holds only the authority from which grants are attenuated and nothing broader; an app never holds that authority and never renders its own consent UI.
· Accept: dynamic grants flow through the powerbox, not permission dialogs.
· Trace: CJ-NI · [L618–619](verification-maximal-os.md#L618)

**R-08-036** MUST — A grant is an authenticated user act over the trusted consent path: a fresh selection of a specific object, on which the powerbox mints a capability CHERI-bounded to that object alone.
· Accept: no grant is minted without a witnessed consent act (R-06-017).
· Trace: CJ-NI, CJ-CERISE · [L620](verification-maximal-os.md#L620)

**R-08-037** IS — A grant carries a temporal scope — one-shot, while-active, or persistent — enforced by the same first-class revocation, so *only this time* and *while using the app* are the capability model expressing itself, not a separate permission subsystem.
· Accept: no permission subsystem exists beside the capability model.
· Trace: CJ-CERISE · [L621](verification-maximal-os.md#L621)

**R-08-038** MUST — While-active is a lease on a trusted clock, not a focus predicate with an untrusted evaluator, and is re-founded on three mechanisms so that the untrusted judgment can only ever *subtract*.
· Accept: neither obvious repair is taken — focus policy does not migrate into the consent TCB, and the scope does not collapse to one-shot.
· Trace: CJ-NI · [L622–625](verification-maximal-os.md#L622)

**R-08-039** MUST — (1) The compositor's focus signal is wired revoke-only: it may assert *no longer active*, which kills the lease at once, and there is no channel by which it can assert *still active*.
· Accept: a compromised compositor's best play is premature revocation — an availability fault — never silent extension.
· Trace: CJ-NI · [L626–628](verification-maximal-os.md#L626)

**R-08-040** MUST — (2) A trusted ceiling bounds the lease: the grant carries a maximum continued duration per resource class, measured on the kernel's trusted timebase and enforced by the powerbox through kernel-mediated grant expiry, past which only a fresh consent act restores authority.
· Accept: the worst case against a compromised compositor colluding with a compromised app is *bounded* continued access.
· Trace: CJ-NI, CJ-WCET · [L629–630](verification-maximal-os.md#L629)

**R-08-041** MUST — (3) The unconditional cuts dominate the lease: the attested lock state and idle-lock, the away-gesture, the physical cutoffs, and the camera's mechanical shutter end a while-active grant whatever any software claims about focus.
· Accept: because a peripheral is electrically enabled only while a live grant holds it, a held-open grant is physically legible rather than silent (R-15-146).
· Trace: CJ-CERISE · [L631](verification-maximal-os.md#L631)

**R-08-042** IS — The consent TCB does not grow to buy this: expiry is enforced by the powerbox and the kernel's revocation machinery, both already trusted, and the compositor keeps its focus policy outside the trusted set.
· Accept: the TCB inventory is unchanged by the lease mechanism.
· Trace: CJ-NI · [L632](verification-maximal-os.md#L632)

**R-08-043** IS — What is given up is booked: while-active remains strictly weaker than one-shot, because the ceiling is a bound on exposure, not its absence.
· Accept: the §17 residual entry exists.
· Trace: CJ-NI · [L633](verification-maximal-os.md#L633)

**R-08-044** IS — Sandboxing, portals, and container isolation are obviated by construction, not reimplemented.
· Accept: no such subsystem exists.
· Trace: CJ-CERISE · [L635](verification-maximal-os.md#L635)

---

## §9 — Boot & Root of Trust

### 9.1 The measured chain

**R-09-001** IS — The RoT is OpenTitan-class and integrated on-die, providing measured boot, key storage, TRNG, monotonic counters, and boot-attempt counting.
· Accept: it is the platform's only management processor (R-15-194).
· Trace: CJ-DEVTREE · [L641](verification-maximal-os.md#L641)

**R-09-002** MUST — The chain is RoT → verified M-mode firmware → per-core kernels of all classes → static image, with every stage measured and all signatures post-quantum (ML-DSA).
· Accept: no stage executes before its measurement is recorded.
· Trace: CJ-DEVTREE, CJ-CRYPTO-SPEC · [L642–643](verification-maximal-os.md#L642)

**R-09-003** MUST — The first instruction executes from the RoT's on-die metal-mask boot ROM — immutable silicon in the attested mask set — with keys, lifecycle state, and anti-rollback counters in on-die OTP.
· Accept: there is no BIOS, no discrete SPI flash, and no socketed boot device.
· Trace: CJ-DEVTREE · [L644–645](verification-maximal-os.md#L644)

**R-09-004** MUST — The mutable boot payload lives in a fixed-physical-address boot region of raw NAND: reserved blocks at known addresses, A/B duplicated, written only by the A/B transactor at update commit.
· Accept: no FTL, no wear levelling, and no filesystem stands under boot; the ROM reads it through the same firmware-free ONFI PHY and fixed-function LDPC ECC engine the storage path uses.
· Trace: CJ-DEVTREE · [L646](verification-maximal-os.md#L646)

**R-09-005** MUST — The pre-kernel reader is not a parser: the boot payload is a flat measured image behind a fixed-layout, length-bounded header (offset, length, hash), verified by ML-DSA signature, checked against the monotonic anti-rollback floor, and measured before any byte of it executes.
· Accept: no interpreted container grammar and no followed offsets; a corrupt field fails the hash or signature check rather than steering a reader. The content-addressed store, the pack format, and the §13 verified reader come up only after the kernel and the FTL server, and stage zero never touches them.
· Trace: CJ-FORMAT, CJ-DEVTREE · [L647](verification-maximal-os.md#L647)

**R-09-006** MUST — The ROM's sequence is fixed and singular: verify and enter the RoT runtime firmware, walk the reset table, bring up the memory controller, pull both A/B headers, select per the boot-target latch and boot counting, place the verified M-mode image in main SRAM, and release the boot core into the measured chain.
· Accept: cold boot, deep-sleep wake, and the recovery generation all take this one path, so no second loader exists.
· Trace: CJ-DEVTREE · [L648](verification-maximal-os.md#L648)

**R-09-007** MUST NOT — There is no UEFI, no SMM, no ACPI, and no option ROMs; a static devicetree instead declares core classes, islands, the NoC schedule, OPP tables, and radio calibration and limit values.
· Accept: the devicetree is attested (R-15-126).
· Trace: CJ-DEVTREE · [L649](verification-maximal-os.md#L649)

### 9.2 The RoT as TPM-without-TPM

**R-09-008** IS — The RoT realizes the TPM 2.0 *functional* surface — measured boot, seal/unseal, attestation quotes, monotonic anti-rollback counters — on the on-die RoT and verified crypto core, and not as a standardized TPM.
· Accept: the seal/unseal/quote surface is exposed to userspace as a capability-gated IPC service: a TPM's operations, never its command protocol.
· Trace: CJ-CRYPTO-SPEC · [L650–651](verification-maximal-os.md#L650), [L656](verification-maximal-os.md#L656)

**R-09-009** MUST NOT — A discrete TPM is declined as an unverified vendor black box over an external bus; a firmware TPM is declined for want of a foreign TEE; and running the RoT in TCG TPM 2.0 mode is declined on the command surface — a large, grammar-heavy register-slave command stream, an ambient send-commands interface rather than a capability-scoped typed IDL, with an algorithm-agility menu that readmits non-PQ primitives.
· Accept: the eUICC stays the only tolerated foreign trust domain.
· Trace: CJ-FORMAT, CJ-CERISE · [L652–655](verification-maximal-os.md#L652)

### 9.3 Sleep and time

**R-09-010** MUST — Deep sleep is a boot-chain variant, not a resume path: suspend is seal-and-power-off of enumerated state, and wake re-executes the measured chain.
· Accept: the S3-trampoline/SMM-resume attack class has no analog because no resume path exists outside the measured chain.
· Trace: CJ-DEVTREE · [L657–659](verification-maximal-os.md#L657)

**R-09-011** IS — Cellular standby keeps the radio island continuously live at low duty cycle rather than resuming it from unmeasured state, so it adds no resume trampoline; islands that do power off still wake only through the measured chain.
· Accept: consistent with R-15-190.
· Trace: CJ-ISOL · [L660](verification-maximal-os.md#L660)

**R-09-012** MUST NOT — The platform carries no persistent real-time clock: no coin cell, no always-powered RTC, and no CMOS-style non-volatile settings store.
· Accept: such a part would be the foreign always-on component the design refuses, and its reset-on-battery-removal is a liability.
· Trace: CJ-DEVTREE · [L661–662](verification-maximal-os.md#L661)

**R-09-013** IS — Nothing security-critical depends on wall-clock time: the RoT's monotonic counters are counters, not clocks, so a cold boot with unknown wall-clock time is safe — anti-rollback still holds and sealed keys stay sealed.
· Accept: the security core leans on counters and attestation nonces, never on time of day.
· Trace: CJ-DEVTREE · [L663–664](verification-maximal-os.md#L663)

**R-09-014** MUST — The device boots into an explicit *time-unknown* state and re-acquires calendar time from the network, trusting it only once authenticated, with Roughtime the bootstrap source.
· Accept: Roughtime is chosen over bare NTP (unauthenticated) and over NTS (whose TLS bootstrap needs a roughly-correct clock), establishing coarse trusted time from cold with no prior clock.
· Trace: CJ-CRYPTO-SPEC · [L665–666](verification-maximal-os.md#L665)

**R-09-015** IS — Precision beyond that is a refinement on the same substrate, not a second clock: one time service disciplines a single wall-clock from cross-checked authenticated sources, and that wall-clock is a disciplined view over the scheduler's monotonic `mtime`, which stays a separate free-running counter.
· Accept: time-sync steering never perturbs scheduling or WCET.
· Trace: CJ-WCET · [L667](verification-maximal-os.md#L667)

**R-09-016** MUST — A coarse monotonic time floor is persisted to non-volatile storage at controlled shutdown, at a write rate too low to wear the flash, so after reboot wall-clock time is known to be at least that floor and cannot be rolled back beneath it.
· Accept: Roughtime refines it upward to the true value.
· Trace: CJ-DEVTREE · [L668](verification-maximal-os.md#L668)

### 9.4 Lock state and duress

**R-09-017** IS — Lock state is attested key custody: Before First Unlock holds no per-profile user-data volume key resident, while the standby radio island keeps the device page-reachable.
· Accept: user data stays encrypted at rest in BFU.
· Trace: CJ-CRYPTO-SPEC · [L669–670](verification-maximal-os.md#L669)

**R-09-018** MUST — The unlock credential drives a credential-gated BFU → AFU transition: the credential compartment matches it, the RoT rate-limits attempts, and only a correct match authorizes the crypto core to derive and hold the per-profile volume key and wake the application islands through the measured chain.
· Accept: no path derives the volume key without a correct primary-credential match.
· Trace: CJ-CRYPTO-SPEC, CJ-DEVTREE · [L671](verification-maximal-os.md#L671)

**R-09-019** MUST — On explicit lock or after a policy idle interval, the reverse runs as a scheduled RoT-attested global-mode transition: per-profile volume keys are zeroized in the crypto core and the application islands re-sealed, returning the device to BFU with the radio island still live.
· Accept: a device seized after unlock reverts to keys-not-resident at rest.
· Trace: CJ-CRYPTO-SPEC, CJ-ISOL · [L672](verification-maximal-os.md#L672)

**R-09-020** MUST — Biometric match authority never survives a BFU transition: a cold or idle-locked device requires the primary credential.
· Accept: biometrics are strictly the AFU convenience factor, never the at-rest key-release root (R-12-019).
· Trace: CJ-CRYPTO-SPEC · [L673](verification-maximal-os.md#L673)

**R-09-021** MUST — The attested lock state gates non-key authority too: lockout drops the microphone and camera and forces the USB data path charging-only, while the radio island stays page-reachable because the paging task still holds its capability.
· Accept: the cut is by grant revocation, not a special rule (R-15-147).
· Trace: CJ-CERISE · [L674](verification-maximal-os.md#L674)

**R-09-022** MUST — A distinct duress credential, presented in place of the ordinary one, commands the RoT to crypto-erase rather than unlock: it destroys the sealing root wrapping the per-profile volume keys and the device-identity secret, rendering every user-data domain permanently unrecoverable in the time to zeroize a key.
· Accept: a key destruction rather than a bulk overwrite; SRAM volatility retains nothing across the power-down the erase forces.
· Trace: CJ-CRYPTO-SPEC · [L675–676](verification-maximal-os.md#L675)

**R-09-023** IS — The erase is one-way and non-rollbackable, rooted in the RoT's monotonic-counter and sealing machinery, followed by an RoT reset, and indistinguishable to an observer from an ordinary failed attempt until it completes.
· Accept: the holder can be compelled to enter *a* credential, never the *right* one.
· Trace: CJ-CRYPTO-SPEC · [L677](verification-maximal-os.md#L677), [L680](verification-maximal-os.md#L680)

**R-09-024** MUST — The erase is scoped to user-data key custody and not the system image, so the device is left clean rather than bricked: it re-derives a fresh identity from the RoT and boots the untouched signed generation into a clean first-run BFU state.
· Accept: erasing the reproducible system image would buy no confidentiality and would only signal resistance.
· Trace: CJ-DEVTREE · [L678–679](verification-maximal-os.md#L678)

### 9.5 Attestation and generation selection

**R-09-025** MUST — Attestation covers the chain *and* the admission discipline: checker version plus the spec and policy set every resident proof was checked against, plus the frozen ISA-profile version and the frozen radio-generation identity.
· Accept: the quote's vector is exactly this set.
· Trace: CJ-DEVTREE, CJ-SAIL · [L681](verification-maximal-os.md#L681)

**R-09-026** MUST — Each signed generation emits a reference integrity manifest: the reference-value dual of the quote, covering the same vector, so a remote relying party can appraise evidence against expected values.
· Accept: it is per-generation and ML-DSA-signed, rides the A/B signed-generation machinery, and is served beside the quote by the sealing and attestation service; TCG RIM or IETF CoRIM encodings may be emitted for interop.
· Trace: CJ-DEVTREE · [L682–687](verification-maximal-os.md#L682)

**R-09-027** IS — What differs from a vendor RIM is the source of trust: because the base image is bit-for-bit reproducible from source, the reference values are *reproduced, not asserted*, and DDC bounds trusting-trust.
· Accept: any party regenerates the golden set from source; the manifest is trusted by reconstruction rather than by a manufacturer's signature over opaque blobs.
· Trace: CJ-T · [L686](verification-maximal-os.md#L686)

**R-09-028** MUST — The platform carries A/B images, RoT boot counting with automatic revert, and a monotonic anti-rollback floor for security updates.
· Accept: all three are RoT duties.
· Trace: CJ-DEVTREE · [L688](verification-maximal-os.md#L688)

**R-09-029** MUST — User-selectable generation boot is a signed recovery generation, not a pre-kernel menu: a boot-time signal latched by the RoT into a one-bit boot-target register, measured into the chain like every other input, selects a minimal signed image whose sole role is to run the rollback-manager UI and the credential/unlock compartment.
· Accept: no unverified bootloader scripting, filesystem driver, or interactive environment runs before the kernel, so the recovery path adds no pre-kernel TCB surface.
· Trace: CJ-DEVTREE · [L689–691](verification-maximal-os.md#L689)

**R-09-030** MUST — Which generations are bootable is bounded by the monotonic anti-rollback floor: any retained generation at or above the floor may be selected, while generations below it stay visible in history and fully diffable but are not bootable.
· Accept: booting one would un-fix a shipped security update.
· Trace: CJ-DEVTREE · [L692](verification-maximal-os.md#L692)

**R-09-031** MUST — Selection is enacted by the system-integrity reader and A/B transactor as the same atomic two-slot flip an update takes, and authorizing it is credential-gated and consent-witnessed.
· Accept: a rollback cannot be triggered silently.
· Trace: CJ-NI, CJ-DEVTREE · [L693](verification-maximal-os.md#L693)

---

## §10 — Storage & State

### 10.1 The verified stack

**R-10-001** MUST — The base is an immutable content-addressed Merkle-DAG image with a signed root, every read runtime-verified against the boot-attested root by the system-integrity reader, and bit-for-bit reproducible from source.
· Accept: no read of the base image bypasses the verification.
· Trace: CJ-DEVTREE · [L699](verification-maximal-os.md#L699)

**R-10-002** IS — The storage path is four verified layers on one prover: L0, the Perennial/GoJournal-lineage crash-safe write-ahead log in Iris/Coq; L1, the VeriBetrFS B^ε-tree *design* re-proved in Coq/Iris; L2, filesystem semantics following RefFS with (S)FSCQ; L3, the SFSCQ/DiskSec data-noninterference method.
· Accept: each layer's proof is a Coq artifact; no layer carries a foreign-prover proof into the trust base.
· Trace: CJ-T · [L700–709](verification-maximal-os.md#L700)

**R-10-003** MUST — L1 is one parametric index, generic over key type, verified once and instantiated per object class.
· Accept: no per-object-class index proof exists.
· Trace: CJ-T · [L704](verification-maximal-os.md#L704)

**R-10-004** IS — The B^ε buffered-update refinement is kept deliberately, its message-log batching cutting NAND write amplification and therefore device wear — an endurance gain — with a plain CoW B+ tree over the L0 journal as the strictly-smaller-proof fallback.
· Accept: because the design is re-proved in Coq/Iris it is not a non-Coq anchor.
· Trace: CJ-T · [L705](verification-maximal-os.md#L705)

**R-10-005** IS — L2 represents inodes, dirents, extents, and xattrs as typed keys in one keyspace, with snapshots a version field *in* the key, giving O(1) writable snapshots.
· Accept: one keyspace, one index proof.
· Trace: CJ-T · [L706](verification-maximal-os.md#L706)

**R-10-006** MUST — RefFS's machine-checked deadlock- and livelock-freedom (the MoLi dynamically-layered-definite-releases discipline) is a precondition for §11 temporal admission of any task that calls a shared storage server.
· Accept: a deadlocked or livelocked server is unbounded blocking no WCET bound survives; system-wide deadlock-freedom is the concurrent complement to §13's per-handler termination obligation.
· Trace: CJ-WCET · [L708](verification-maximal-os.md#L708)

**R-10-007** MUST — The four verified layers are verified C compiled by CompCert and proved in Coq, running with no managed runtime: GoJournal's design and specification transfer, its Go and its Goose/GooseLang proofs do not.
· Accept: Dafny/Z3 and Yggdrasil's Z3/Rosette are declined as bases and retained only as unverified cross-checks.
· Trace: CJ-COMPCERT · [L710–711](verification-maximal-os.md#L710)

**R-10-008** MUST — L0 is re-expressed from that design directly in Gallina and lowered GC-free through the CompCert-C + VST/Iris path, with CN + Fulminate as the CHERI-C reference that de-risks it and its SMT automation an untrusted oracle.
· Accept: no bespoke Goose-to-C translator is built; what is rebuilt for L0 is the refinement proof against the C, not an extraction tool.
· Trace: CJ-COMPCERT · [L712](verification-maximal-os.md#L712)

**R-10-009** MUST — The four-layer stack is wholly non-TCB, holding the read-only content-addressed system image and the mutable per-profile user subvolumes alike; the only storage component in the TCB is the system-integrity reader and A/B transactor.
· Accept: the crash-safe journal and the write-optimized CoW B-tree leave the trust base entirely; the transactor commits by flipping the signed root past the anti-rollback floor, not by trusting the filesystem's journal.
· Trace: CJ-DEVTREE · [L713–715](verification-maximal-os.md#L713)

### 10.2 Mutable filesystem

**R-10-010** IS — Bcachefs-class semantics fall out of the unified CoW B-tree: reflinks are refcounted CoW extent sharing, snapshots are retained roots keyed by snapshot-version, dedup is content-addressed extent sharing addressed by a per-domain keyed plaintext digest, and checksums are the per-extent AEAD tags serving integrity alone.
· Accept: the immutable base image stays a content-addressed Merkle DAG; this CoW B-tree is the mutable user-data structure.
· Trace: CJ-T · [L716–718](verification-maximal-os.md#L716)

**R-10-011** MUST NOT — The mutable user-data volume is deliberately not freshness-protected by the RoT monotonic counter, because sealing its root would advance the counter at CoW-commit frequency, which no OTP or hardware monotonic counter sustains.
· Accept: the decision is stated as a design choice with its consequence, not omitted.
· Trace: CJ-DEVTREE · [L719–720](verification-maximal-os.md#L719)

**R-10-012** IS — The mutable volume carries confidentiality and tamper-*detection* from the per-extent AEAD with volume keys resident only in the crypto core, so offline forgery or corruption is caught on the authenticate-then-return read path; only *freshness* is surrendered.
· Accept: a whole-volume rollback to an authenticated-but-stale state is a below-the-line availability/consistency event, not an integrity breach, since a physical adversary who can rewrite the disk can equally destroy it.
· Trace: CJ-CRYPTO-SPEC · [L721](verification-maximal-os.md#L721)

**R-10-013** MUST — The RoT monotonic counter is spent only on low-rate security-critical state, and that set is enumerated: the base-image security-version floor, and the key-wrapping/sealing-root and credential attempt-counter versions — advancing on signed updates, key rotation, or authentication attempts, and never on a data commit.
· Accept: the enumeration is closed by amendment to this register; it is what blocks downgrade to a vulnerable generation, un-revoking a key, resurrecting an old password, and replaying the lockout counter.
· Trace: CJ-DEVTREE · [L722](verification-maximal-os.md#L722)

**R-10-014** MUST — Secure erase is crypto-erase: the volume keys being RoT-sealed and core-resident, destroying the sealing root renders the encrypted user data unrecoverable in the time to zeroize a key.
· Accept: rolling the disk back yields only stale ciphertext an attacker cannot read and cannot pair with a resurrected key.
· Trace: CJ-CRYPTO-SPEC · [L723](verification-maximal-os.md#L723)

**R-10-015** MUST — Dedup addresses on a per-domain keyed digest — a PRF/MAC of the plaintext under a dedup key domain-separated by KDF from the volume key — computed inside the crypto core and handed to the filesystem as an opaque tag beside the ciphertext and its integrity tag.
· Accept: keys never leave the core and the filesystem sees only ciphertext and tags.
· Trace: CJ-CRYPTO-SPEC · [L724–726](verification-maximal-os.md#L724)

**R-10-016** MUST — Dedup never crosses a key or confidentiality domain: the digest is deterministic within a domain yet incomparable across domains and uncomputable without the domain key.
· Accept: cross-domain content-equality — a confirmation-of-file oracle — is impossible by construction, not forbidden by convention.
· Trace: CJ-NI · [L727](verification-maximal-os.md#L727)

**R-10-017** MUST NOT — Convergent encryption (key = plaintext hash) is rejected *within* a domain for the same reason it is rejected across them: it would leak plaintext equality to anyone, not only holders of the domain key.
· Accept: no scheme derives a key from plaintext.
· Trace: CJ-NI · [L728](verification-maximal-os.md#L728)

**R-10-018** MUST NOT — Filesystem compression is out of scope, and its removal is a security gain: it deletes the compress-then-encrypt ratio oracle and removes a decompressor from the read data path, which is authenticate-then-return.
· Accept: no decompressor exists on any read path.
· Trace: CJ-NI · [L729](verification-maximal-os.md#L729)

**R-10-019** IS — The exclusion is scoped to *filesystem* compression and does not reach a single-owner, build-time-compressed signed image expanded once on the install or load path: one compressor, one trust domain, no runtime state, the decompressor below the integrity line, its expanded bytes hash-verified against the signed root.
· Accept: expansion is a bounded §11 task, never per read.
· Trace: CJ-WCET, CJ-DEVTREE · [L730](verification-maximal-os.md#L730)

**R-10-020** IS — Build-time compression buys *stored* bytes, never *resident* ones: every live byte is a capability-delegated SRAM byte with no swap, no overcommit, and no demand paging.
· Accept: it is not a capacity lever and recovers none of the C extension's code size.
· Trace: CJ-MEMPLAN · [L731](verification-maximal-os.md#L731)

**R-10-021** IS — Replication, erasure coding, tiering, the bucket allocator with copying garbage collector, and the host-side FTL server over raw NAND sit below the integrity line as contained block services trusted only for availability.
· Accept: a mis-placed or lost block is caught by the AEAD/Merkle-DAG layer above, never an undetected corruption.
· Trace: CJ-DEVTREE · [L732–733](verification-maximal-os.md#L732)

### 10.3 Authenticated encryption at rest

**R-10-022** MUST — Confidentiality and integrity of data at rest are one pass: per-extent AEAD with a per-extent nonce, the Poly1305/GHASH tag serving as the stored checksum, keyed per confidentiality domain, with keys resident only in the crypto core.
· Accept: the filesystem compartment handles ciphertext extents and tags and invokes seal/open, never raw key material, so the constant-time obligation lands on the crypto core rather than the filesystem.
· Trace: CJ-CRYPTO-SPEC, CJ-CT-SOUND · [L735–736](verification-maximal-os.md#L735)

**R-10-023** MUST — The AEAD tag is the integrity checksum only and never the dedup address, so the nonce stays per-extent-random (semantic security intact) while the dedup address stays deterministic within a domain.
· Accept: the two properties are never conflated in the interface to the crypto core.
· Trace: CJ-CRYPTO-SPEC · [L737](verification-maximal-os.md#L737)

**R-10-024** MUST — The cipher is frozen to AES-GCM via `Zvkned`/`Zvkg`, one cipher and not a menu; ChaCha20/Poly1305 is the frozen-out alternative, `Zvbb`/`Zvbc` remaining in the profile for Keccak and PQ rather than for a second filesystem cipher.
· Accept: carrying both would double the constant-time crown jewel and the filesystem-cipher Sail surface for no security gain.
· Trace: CJ-LEAK, CJ-CRYPTO-SPEC · [L738](verification-maximal-os.md#L738)

**R-10-025** IS — The verifiable-encryption claim is a composition: the §5 three-layer crypto proof joined with the L3 data-noninterference theorem — *(the AE scheme is IND-CCA/INT-CTXT) ⋈ (the filesystem leaks nothing across domains)* — at the primitive's functional spec, itself a crown-jewel spec.
· Accept: this is the AE ⋈ non-interference seam lemma (R-05-160).
· Trace: CJ-REDUCTION, CJ-NI · [L739–740](verification-maximal-os.md#L739)

### 10.4 Statelessness and generations

**R-10-026** IS — The running system is an immutable, signed, content-addressed image — OS, apps, and the compiled declarative config generation — plus enumerated mutable volumes; everything else is tmpfs, gone at reboot.
· Accept: the mutable-volume set is enumerated at composition.
· Trace: CJ-DEVTREE · [L741–742](verification-maximal-os.md#L741)

**R-10-027** MUST — System and user data are separated by subvolume and confidentiality domain, not by partition or separate filesystem: each user's mutable data is its own subvolume, its own confidentiality domain with a per-domain key, reached only through its own capability.
· Accept: subvolumes share one free-space pool, snapshot and reflink in O(1), and ride the single verified codebase.
· Trace: CJ-NI, CJ-CERISE · [L743–744](verification-maximal-os.md#L743)

**R-10-028** MUST — System configuration is declarative and compiled into the generation rather than a mutable `/etc` overlay, so it is reproducible and attested rather than editable at runtime.
· Accept: no runtime-editable system configuration exists.
· Trace: CJ-DEVTREE · [L745](verification-maximal-os.md#L745)

**R-10-029** MUST NOT — No trusted component parses text configuration at runtime: config compiles to typed, signed objects per generation.
· Accept: no text-config parser appears in the TCB.
· Trace: CJ-FORMAT · [L747](verification-maximal-os.md#L747)

**R-10-030** MUST — The generation history is a signed, diffable log: the platform retains the last N signed generation roots under a retain-K-plus-pinned policy, each point named by its signed root, with the change between any two computed as a structured diff of three signed inputs — image, config, and reference integrity manifest.
· Accept: every historical point and every diff is signed and reproducible from source, so the history cannot be forged and a diff is verifiable rather than merely reported.
· Trace: CJ-DEVTREE · [L748–750](verification-maximal-os.md#L748)

**R-10-031** IS — The diff is structured data surfaced through the rollback-manager service, and rolling back is selecting a prior root, bounded by the anti-rollback floor.
· Accept: the rollback-manager UI is outside the TCB (R-06-022).
· Trace: CJ-DEVTREE · [L751](verification-maximal-os.md#L751)

**R-10-032** MUST — FDE keys are sealed to the RoT and measured state; per-profile volume keys are resident only After First Unlock, released into the crypto core by the credential-gated unlock transition and zeroized on lock or idle timeout, so the Before-First-Unlock state holds no user-data key; memory is zeroized at shutdown.
· Accept: the BFU key inventory is empty.
· Trace: CJ-DEVTREE, CJ-CRYPTO-SPEC · [L752](verification-maximal-os.md#L752)

**R-10-033** IS — Factory reset is discarding the volumes; device identity re-derives from the RoT.
· Accept: no identity material survives the reset outside the RoT.
· Trace: CJ-DEVTREE · [L746](verification-maximal-os.md#L746)

**R-10-034** IS — Deterministic layout is a proof input: because control-flow prediction is static, hot-path fall-through layout is a reproducible property of the signed image rather than runtime-learned predictor state.
· Accept: it feeds WCET and reproducibility without introducing per-core learned history.
· Trace: CJ-WCET · [L753–754](verification-maximal-os.md#L753)

---

## §11 — Updates

### 11.1 Update mechanism

**R-11-001** IS — Updates are image-based, atomic, and A/B, with health-gated auto-rollback; deltas fall out of content addressing and the running base is never mutated.
· Accept: no in-place mutation of a running generation exists.
· Trace: CJ-DEVTREE · [L760](verification-maximal-os.md#L760)

**R-11-002** MUST — Rollback is pinning a prior signed root subject to the anti-rollback floor, by either the automatic health-gated path or the user-driven path, and both commit through the one trusted transactor.
· Accept: the UI only stages a target; the transactor and RoT enforce the signed-root check and the floor, and authorizing a user-driven rollback is credential-gated and consent-witnessed, so neither a compromised manager nor a malicious app can silently downgrade the device.
· Trace: CJ-DEVTREE, CJ-NI · [L761–762](verification-maximal-os.md#L761)

**R-11-003** IS — Because no foreign computers exist, this is the update mechanism for the entire machine: there are no vendor firmware side-channels to update, and nothing updates outside a proof-checked generation.
· Accept: the update inventory covers radio, storage, display, and everything else.
· Trace: CJ-CERISE · [L763](verification-maximal-os.md#L763)

**R-11-004** MUST — The radio generation is a separately versioned, attested artifact: patchable for security within the certified envelope, re-certified as a delta when its protocol behaviour changes.
· Accept: consistent with R-12-056.
· Trace: CJ-DEVTREE · [L764](verification-maximal-os.md#L764)

**R-11-005** MUST — Proof-checked admission: the transactor commits a generation only after the on-device checker validates every new binary's proof against the current spec-set and Sail-model versions.
· Accept: proofs are generation-scoped, so revving either forces re-admission, and static composition is preserved.
· Trace: CJ-TAL-SOUND, CJ-SAIL · [L765–766](verification-maximal-os.md#L765)

### 11.2 Temporal admission

**R-11-006** MUST — The task set admits only with a machine-checked schedulability proof: for the static cyclic executive an interval-arithmetic check in the same checker — the slot WCETs fit the major frame and each task's period is harmonic with it — not Prosa-style response-time analysis.
· Accept: the proof is a Coq artifact, not an analysis report.
· Trace: CJ-WCET · [L767](verification-maximal-os.md#L767)

**R-11-007** MUST — Monitor availability and watchdog-before-deadline ship as theorems; radio deadlines (HARQ feedback, ACK windows, idle-mode DRX paging reception, link-layer connection-event anchoring) are admitted hard tasks; the same proof yields the hardware watchdog's window parameters.
· Accept: one artifact yields all three.
· Trace: CJ-WCET · [L768](verification-maximal-os.md#L768)

**R-11-008** MUST — Two standing reservations are part of every admitted schedule rather than implied: the display-scanout reservation (its static TDM NoC slice, framebuffer bank binding, and line-period deadline) and the §8 revocation sweep's background slot class.
· Accept: neither the always-on display nor the containment machinery is an unbudgeted interference term.
· Trace: CJ-WCET, CJ-ISOL · [L769](verification-maximal-os.md#L769)

**R-11-009** MUST — Admission counts the switch-duty ratio σ = C_switch / T_poll explicitly instead of absorbing it into slack: a task's real cost is its in-slot WCET plus the partition-switch constant times its visit rate.
· Accept: the ratio is recorded per task in the admission artifact.
· Trace: CJ-WCET · [L770–772](verification-maximal-os.md#L770)

**R-11-010** MUST — Lever (1), applied first: raise the cadence bound by buffering, not by relaxing the deadline. A device with a ring or FIFO of depth *D* need only be visited before *D* arrivals accumulate, so buffer depth is a scheduling parameter fixed at composition beside the slot widths.
· Accept: what it trades away is latency, bounded by the deadline half of the sizing rule, so the two halves constrain each other.
· Trace: CJ-WCET · [L774–775](verification-maximal-os.md#L774)

**R-11-011** MUST — Lever (2): where the deadline rather than the buffer sets the cadence, a device server whose admissible T_poll drives σ past the composition threshold is inadmissible as a slotted task and is statically pinned to a core of its class.
· Accept: pinning *deletes* rather than reduces the switching cost — a core running one partition performs no partition switch, so `fence.t`, save-and-zeroize, and OPP relock all leave its budget together.
· Trace: CJ-WCET · [L776](verification-maximal-os.md#L776)

**R-11-012** IS — This is the general rule the radio PHY pair and the sentinel were already instances of, now derived rather than assumed: any other device server failing σ is treated the same way instead of special-cased.
· Accept: consistent with R-15-114 and R-07-034.
· Trace: CJ-WCET · [L777](verification-maximal-os.md#L777)

**R-11-013** IS — The complementary half is that everything else gets long slots: with the high-rate servers off the slot wheel, the major frame carries few switches and the switch constant amortizes to a negligible fraction.
· Accept: the pinning rule and the long-slot property are one decision, both falling out of the recorded inequality.
· Trace: CJ-WCET · [L778](verification-maximal-os.md#L778)

**R-11-014** IS — Static core assignment reduces the heterogeneous-multiprocessor problem to independent per-core uniprocessor analyses, each against its class's WCET table.
· Accept: no global multiprocessor schedulability argument is required.
· Trace: CJ-WCET · [L779](verification-maximal-os.md#L779)

**R-11-015** MUST — WCET tables are derived, not asserted: each per-(class, operating-point) entry is a syntax-directed max-path sum over the binary's typed control-flow graph with the timing-annotated Sail model as its per-instruction latency table, riding as cost annotations on the CHERI-TAL derivation the on-device checker already validates.
· Accept: a wrong table cannot silently pass admission; only a wrong timing-annotation *statement* can, and that is a crown-jewel spec.
· Trace: CJ-WCET, CJ-SAIL · [L780](verification-maximal-os.md#L780)

**R-11-016** IS — The control tier's WCET is structural rather than estimated: Lustre/Vélus control planes compile to loop-free, statically-sized reactions, so the estimator's loop-bound and path analysis concentrate on the Rust data planes.
· Accept: consistent with R-05-054.
· Trace: CJ-VELUS, CJ-WCET · [L781](verification-maximal-os.md#L781)

**R-11-017** MUST — WCET tables are per (class, operating point), and the admission proof selects each partition's OPP — the slowest point meeting deadlines — emitting the OPP assignment, the TDM NoC schedule, and the watchdog windows as one artifact.
· Accept: one artifact, three outputs.
· Trace: CJ-WCET, CJ-ISOL · [L782](verification-maximal-os.md#L782)

**R-11-018** MUST — Global mode schedules are each independently admission-proved complete schedules, and switching between them is a rare, RoT-attested global transition on explicit authority, never load-following.
· Accept: consistent with R-15-189.
· Trace: CJ-NI · [L783](verification-maximal-os.md#L783)

### 11.3 Compartment population as a schedule axis

**R-11-019** IS — Compartment population is a second schedule axis and deliberately not the global-mode one, because opening a browser tab changes no operating point, NoC schedule, or watchdog window, and folding the two into one transition class would make the honest mechanism unusable at the rate ordinary interaction demands.
· Accept: population is built from the same admission artifact and carries none of the attestation weight.
· Trace: CJ-WCET · [L784–786](verification-maximal-os.md#L784)

**R-11-020** MUST — (1) The major frame on every app-hosting core splits at composition into a reserved band and a discretionary band, and the reserved band — hard tasks, the display reservation, the sweep class, system servers — is identical across every rung.
· Accept: the hard-deadline half of the schedulability proof is discharged once and re-used, and no population change can move a deadline or perturb a hard task.
· Trace: CJ-WCET · [L787](verification-maximal-os.md#L787)

**R-11-021** MUST — (2) The discretionary band is subdivided by population rungs: a short geometric ladder, each rung an independently admission-proved complete schedule, every rung bound into the same signed generation and measured at boot.
· Accept: the ladder is a composition constant (4/8/16/32 per C-class core in the reference instantiation).
· Trace: CJ-WCET, CJ-DEVTREE · [L788](verification-maximal-os.md#L788)

**R-11-022** MUST — (3) Within a rung the discretionary band is shaped as one focus slot plus (n−1) background slots, the focus slot taking a composition-fixed majority of the band.
· Accept: interactive latency does not divide by *n* even though aggregate share does.
· Trace: CJ-WCET · [L789](verification-maximal-os.md#L789)

**R-11-023** MUST — (4) Which compartment occupies which slot is a permutation, not a schedule: slot widths and offsets are fixed by the rung, and the compositor requests a focus rebinding at a major-frame boundary which the kernel enacts by permuting the slot→compartment map.
· Accept: every admission property is invariant under the permutation, the interval arithmetic quantifying over widths and offsets and never occupants; the untrusted compositor steers responsiveness without touching the admitted schedule, the same shape §8 gives its focus judgment.
· Trace: CJ-WCET, CJ-NI · [L790](verification-maximal-os.md#L790)

**R-11-024** IS — (5) A rung change is a table swap at a major-frame boundary, not an admission event: it selects among schedules the generation already proved, so it is neither RoT-attested nor rare, costing one partition-switch constant plus the table load.
· Accept: it may fire every time the user opens or closes a tab.
· Trace: CJ-WCET · [L791](verification-maximal-os.md#L791)

**R-11-025** IS — (6) It is still not load-following: the rung index is a function of the count of live discretionary compartments, moving only on an explicit user-originated lifecycle event and never on utilization, queue depth, or any compartment's computation.
· Accept: what is given up is the *rarity*, not the *non-reactivity*, and the residual channel that buys is booked in §17.
· Trace: CJ-NI · [L792](verification-maximal-os.md#L792)

**R-11-026** MUST — (7) The top rung is a hard ceiling: past it a new compartment receives no slot rather than a thinner one, and the owning population manager suspends a live compartment to retained state to make room.
· Accept: suspension keeps state and removes a slot; it is not termination, and it is the mechanism, not a heuristic.
· Trace: CJ-WCET · [L793](verification-maximal-os.md#L793)

**R-11-027** MUST — Tasks using vector or matrix instructions carry those units' bounded worst-case latencies into the WCET inputs, and eager vector/matrix save-and-zeroize costs enter the partition-switch terms.
· Accept: the enabling properties are deterministic dataflow, in-order non-speculative issue, statically-predicted control flow, schedule-fixed frequency, and the fixed-latency divide/FPU/AMO mandates.
· Trace: CJ-WCET · [L794](verification-maximal-os.md#L794)

---

## §12 — System Servers

### 12.1 Server structure

**R-12-001** MUST — Each server is its own compartment with its own capability manifest, crash-only design, and supervised restart.
· Accept: no server shares a compartment with another.
· Trace: CJ-CERISE · [L800](verification-maximal-os.md#L800)

**R-12-002** MUST — Server logic splits by plane: the data plane (bulk I/O, ring processing, vector/matrix math, wire parsing) is `#![forbid(unsafe_code)]` safe Rust; the control plane (sequencing, supervision, protocol state machines, mode/timing control) is Lustre compiled by Vélus.
· Accept: any `unsafe` is confined to the verified HAL and never inlined into server logic.
· Trace: CJ-VELUS, CJ-HAL · [L801–802](verification-maximal-os.md#L801)

**R-12-003** IS — The plane split names default languages, not a mandate: a server may instead be a formally-verified non-Rust lift, memory-safe at the binary level like any contained binary, its own verification bonus assurance.
· Accept: consistent with R-05-009.
· Trace: CJ-TAL-SOUND · [L803](verification-maximal-os.md#L803)

**R-12-004** IS — Every function on the machine falls into one of four classes — software on cores (TCB), software on cores (non-TCB), matter, and excluded foreign computers — and the class table is exhaustive.
· Accept: the matter tier is driven through capability-checked MMIO/DMA and carries no instruction fetch and no firmware; every function a conventional platform would delegate to a firmware-running coprocessor is dissolved, reduced, or banned.
· Trace: CJ-CERISE · [L805–812](verification-maximal-os.md#L805)

### 12.2 The ring data plane

**R-12-005** MUST — All bulk I/O rides bounded SPSC shared-memory rings with notification wakeups; the peer is a server, never the kernel, so a ring bug costs one compartment.
· Accept: no bulk-data path traverses the kernel (R-07-029).
· Trace: CJ-KERNEL · [L814–816](verification-maximal-os.md#L814)

**R-12-006** MUST — Descriptors name only indices into a per-session table of pre-delegated capabilities, plus offset and length: no paths and no ambient references, with new authority arriving via control-plane IPC only.
· Accept: no descriptor field is dereferenceable as an address.
· Trace: CJ-CERISE · [L817](verification-maximal-os.md#L817)

**R-12-007** MUST — Ring pages are mapped without capability-store permission, so authority physically cannot cross the data plane.
· Accept: rings carry indices, never capabilities (R-15-026).
· Trace: CJ-CERISE · [L818](verification-maximal-os.md#L818)

**R-12-008** MUST — Both sides parse with verified copy-once parsers, using one canonical verified ring library proven against a Byzantine peer under Ztso with fences included, and — for rings crossing islands — proven over the shared SRAM window they occupy.
· Accept: one ring library, one proof, restated under Ztso (R-15-004).
· Trace: CJ-FORMAT, CJ-SAIL · [L819](verification-maximal-os.md#L819)

**R-12-009** IS — Service is metered on the session's schedule slot; zero-copy is a delegated memory capability the DMA engine presents and the fabric checks, torn down with the session.
· Accept: cross-service linked ops and any credential or personality registration are absent by design.
· Trace: CJ-WCET, CJ-CERISE · [L820–822](verification-maximal-os.md#L820)

### 12.3 The interface layer

**R-12-010** MUST — All server protocols and capability manifests are expressed in one typed IDL profile, fork-and-frozen: resources map to capabilities, worlds map to manifests, and marshalling, the verified parsers, and Coq interface skeletons are all generated from the same types.
· Accept: the admission checker verifies each Tier-1 proof is stated against the matching skeleton.
· Trace: CJ-IDL · [L823–824](verification-maximal-os.md#L823)

**R-12-011** MUST — Flow annotations are a first-class IDL concern for every cross-domain channel: each type carries confidentiality and integrity labels, the IDL-to-Coq generator emits the matching flow predicates, and Tier-1 proofs for cross-domain servers must include flow theorems against them.
· Accept: the labeling is what defines *secret-labeled material* elsewhere in the specification. **See [D-04](#d-04).**
· Trace: CJ-IDL, CJ-NI · [L825](verification-maximal-os.md#L825)

**R-12-012** MUST — The IDL profile is restricted: closed variants only, no recursion, and explicit bounds on every list and string.
· Accept: no IDL type admits an unbounded value (R-05-143).
· Trace: CJ-IDL · [L826](verification-maximal-os.md#L826)

**R-12-013** IS — Two standing rules govern the IDL: its types are documentation of the contract and never the contract, enforcement remaining kernel capabilities plus CHERI plus the Coq specs; and the profile's wire-format mapping is itself a crown-jewel specification.
· Accept: the kernel is not an IDL endpoint.
· Trace: CJ-IDL · [L827–828](verification-maximal-os.md#L827)

### 12.4 Sealing, attestation, and credentials

**R-12-014** MUST — The sealing and attestation service is a crypto-core-backed compartment exposing seal/unseal, attestation quotes, reference-manifest retrieval, and monotonic-counter operations over rings, binding secrets to the RoT and measured state.
· Accept: keys never leave the crypto core; apps hold only sealed blobs and capability handles, so the constant-time obligation stays on the core.
· Trace: CJ-CRYPTO-SPEC, CJ-CT-SOUND · [L829–831](verification-maximal-os.md#L829)

**R-12-015** MUST — A relying party retrieves the running generation's reference integrity manifest through the same service and appraises a quote against it, so remote verification needs no vendor-side golden database.
· Accept: the reference set is reproducible from source.
· Trace: CJ-DEVTREE · [L832](verification-maximal-os.md#L832)

**R-12-016** MUST — The credential and unlock service gates the Before-First-Unlock → After-First-Unlock transition: it matches the primary credential and runs biometric matching, with the biometric sensor a register slave streaming raw samples over a capability-bounded DMA interface block and the matcher ordinary contained safe Rust in its own sub-manifest.
· Accept: a correct match authorizes the crypto core and RoT to derive and hold the per-profile volume key.
· Trace: CJ-CRYPTO-SPEC, CJ-DEVTREE · [L833–835](verification-maximal-os.md#L833)

**R-12-017** MUST — Attempt rate-limiting and a monotonic attempt counter are RoT duties, so a stolen device cannot brute-force the credential offline.
· Accept: the counter is one of the enumerated RoT-fresh items (R-10-013).
· Trace: CJ-DEVTREE · [L835](verification-maximal-os.md#L835)

**R-12-018** MUST — The same compartment recognizes a distinct duress credential that, on match, commands an RoT crypto-erase instead of an unlock, indistinguishable from a normal attempt until it completes.
· Accept: the duress path is a match outcome, not a separate interface.
· Trace: CJ-CRYPTO-SPEC · [L836](verification-maximal-os.md#L836)

**R-12-019** MUST — Biometric authority is a secondary factor only: it unlocks a live After-First-Unlock session but never releases keys from a cold or idle-locked Before-First-Unlock device, which always requires the primary credential.
· Accept: a spoofed or coerced biometric cannot substitute for the at-rest key-release root.
· Trace: CJ-CRYPTO-SPEC · [L837](verification-maximal-os.md#L837)

**R-12-020** IS — The on-die path (this compartment, the crypto core, the RoT) is the platform's own authenticator; an external roaming hardware security key is declined as a foreign computer, at the cost of cross-device credential portability.
· Accept: the cost is booked rather than omitted.
· Trace: CJ-CERISE · [L838](verification-maximal-os.md#L838)

**R-12-021** IS — The rollback-manager service is a contained non-TCB compartment presenting the signed generation history and structured diffs; it drives but does not constitute the trusted rollback path.
· Accept: a below-floor or unsigned target is refused however the UI is compromised (R-06-022).
· Trace: CJ-DEVTREE · [L840–842](verification-maximal-os.md#L840)

**R-12-022** MUST — Authorizing a rollback is a security action: it is gated by the credential/unlock service and witnessed through the trusted consent path, so no app can enact a rollback without unspoofable user consent.
· Accept: it rolls the system generation only; a user-data subvolume restore is a separate, clearly-labeled non-TCB operation carrying that path's surrendered-freshness caveat.
· Trace: CJ-NI, CJ-DEVTREE · [L843–845](verification-maximal-os.md#L843)

### 12.5 Storage servers

**R-12-023** IS — The filesystem is the §10 four-layer verified stack, verified but wholly non-TCB and contained like any server, serving both the system-image and user-data subvolumes.
· Accept: a filesystem fault costs availability or a caught corruption, never a silent integrity breach.
· Trace: CJ-DEVTREE · [L846–847](verification-maximal-os.md#L846)

**R-12-024** IS — Below the §10 integrity line the availability-only block services are ordinary `#![forbid(unsafe_code)]` Rust Tier-1 compartments; a bug or compromise costs availability, never integrity or confidentiality.
· Accept: the AEAD/Merkle-DAG layer catches corruption.
· Trace: CJ-CRYPTO-SPEC · [L848](verification-maximal-os.md#L848)

**R-12-025** MUST — Raw NAND is exposed through a firmware-free on-die flash-interface block (ONFI PHY plus a fixed-function ECC engine), with the FTL a host-side Tier-1 server doing wear levelling, mapping, and garbage collection in safe Rust, trusted for availability only.
· Accept: SSD-controller firmware is deleted; NVMe/eMMC devices with vendor firmware are not on the allowlist.
· Trace: CJ-CERISE · [L849–851](verification-maximal-os.md#L849)

**R-12-026** MUST — Nonvolatile storage carries a soft-decision LDPC per-page code dimensioned for the worst-case cell type at end-of-retention, end-of-endurance bit-error rate, decoded with read-retry across multiple reference voltages.
· Accept: the correction margin is largest where the raw error rate is highest.
· Trace: CJ-SAIL · [L852–853](verification-maximal-os.md#L852)

**R-12-027** MUST — Above the per-page code sits a die- and plane-level parity layer (RAISE/chipkill-class) so a whole failed die, plane, or block is reconstructed rather than merely detected.
· Accept: this is the nonvolatile counterpart of the volatile tier's whole-device ECC coverage.
· Trace: CJ-SAIL · [L854](verification-maximal-os.md#L854)

**R-12-028** IS — The asymmetry is deliberate: storage keeps a full integrity-and-rollback story because persistent media leave the die and survive power-down, whereas volatile main memory keeps none because it does neither.
· Accept: consistent with R-15-199.
· Trace: CJ-T · [L855](verification-maximal-os.md#L855)

**R-12-029** MUST — Retention and read-disturb are scrubbed, not tolerated: the availability-layer FTL runs background patrol reads informed by the ECC engine's soft-decision telemetry and rewrites any page whose error rate drifts toward the correction limit before it crosses it.
· Accept: the nonvolatile analog of SRAM scrubbing (R-15-177).
· Trace: CJ-SAIL · [L856](verification-maximal-os.md#L856)

**R-12-030** MUST — All of this stays fixed-function hardware and safe-Rust management, never controller firmware, and the device ECC composes with rather than replaces the §10 integrity layer above it.
· Accept: a NAND failure is always a caught corruption or an availability event, never a silent integrity breach; corrected-error rates and uncorrectable events feed the sentinel.
· Trace: CJ-CERISE, CJ-CRYPTO-SPEC · [L857–859](verification-maximal-os.md#L857)

### 12.6 Network

**R-12-031** IS — The network is an IPv6-only single stack with verified parsers at every boundary, TLS 1.3 with hybrid PQ key exchange, WireGuard-style tunnels, DNS-over-TLS in its own compartment, and Roughtime-authenticated time.
· Accept: each compartment's attacker-facing wire parsing is held to the Narcissus discipline and its memory safety to the binary-level certificate.
· Trace: CJ-FORMAT, CJ-TAL-SOUND · [L860–861](verification-maximal-os.md#L860)

**R-12-032** IS — For TLS 1.3 the trust-base-uniform target is a Rust-native hax-verified TLS in the Bertie lineage, with miTLS the more mature F\*/Z3 option; either way the protocol proof is *bonus* over the memory-safety floor and never trust base, and the crypto binds to the §5 verified core.
· Accept: no protocol proof enters the trust base (R-05-010, R-05-078).
· Trace: CJ-REDUCTION · [L862](verification-maximal-os.md#L862)

**R-12-033** MUST — Where no Coq-native verified peer exists, mature verified artifacts in other provers serve as differential-test oracles that enter no trust base: IRONSIDES for the resolver, and SPARK-verified TCP with Huginn-TCP conformance for smoltcp.
· Accept: the oracle pattern matches R-05-051.
· Trace: CJ-FORMAT · [L863](verification-maximal-os.md#L863)

**R-12-034** MUST — The NIC is reachable only by capability and its DMA is capability-checked by the fabric; the NIC itself is dissolved, with no Ethernet controller firmware and no PHY-management processor.
· Accept: only the line front end, the frozen-coefficient 1000BASE-T datapath, and the 1588 timestamp unit remain fixed-function matter (R-15-135).
· Trace: CJ-CERISE · [L864–865](verification-maximal-os.md#L864)

**R-12-035** MUST — Time synchronization is one capability-scoped service disciplining the wall-clock from three scope-graded sources — Roughtime, NTS, and secure PTP — cross-checking them so a lying or stalled source is caught by disagreement.
· Accept: time is handed to apps as a capability, coarse by default and high-precision only where the clock-read-out rule grants it.
· Trace: CJ-NI · [L867–868](verification-maximal-os.md#L867)

**R-12-036** IS — The precision substrate is a fixed-function IEEE-1588 hardware timestamp unit and adjustable clock at the NIC, deterministic and firmware-free; the scheduler's monotonic `mtime` stays a separate free-running counter.
· Accept: the software servo computes offset without interrupt jitter.
· Trace: CJ-WCET · [L869](verification-maximal-os.md#L869)

**R-12-037** MUST — Secure PTP runs in the most defensive profile the standard allows: the authentication TLV on every message, its key established through the platform's own NTS key establishment rather than manual pre-shared secrets, time-receiver-only, accepting no management or reconfiguration messages, and its framing held to the Narcissus discipline.
· Accept: no verified PTP peer exists, so it rides parser-plus-crypto discipline alone; the residual delay and path-asymmetry surface is booked in §17.
· Trace: CJ-FORMAT, CJ-CRYPTO-SPEC · [L870–871](verification-maximal-os.md#L870)

### 12.7 Radio stack

**R-12-038** MUST — The radio is software-defined as ordinary contained compartments with no baseband processor anywhere: PHY servers run statically pinned on the radio V-class cores with the FEC units, and HARQ/subframe deadlines are §11-admitted hard tasks.
· Accept: cellular and Wi-Fi PHYs are separate compartments; GNSS (receive-only) is a third.
· Trace: CJ-CERISE, CJ-WCET · [L873–875](verification-maximal-os.md#L873)

**R-12-039** MUST — Everything with protocol semantics stays in software: connection-event and slot scheduling, channel selection, framing/whitening/CRC, link-layer encryption via the crypto core, and the link-layer state machine as a Lustre control plane.
· Accept: only the turnaround timing is fixed-function (R-15-122).
· Trace: CJ-VELUS · [L876–880](verification-maximal-os.md#L876)

**R-12-040** MUST — L2/L3 servers (MAC/RLC/PDCP/RRC/NAS; 802.11 MLME; BT L2CAP/GATT) are Tier-1 compartments behind verified ASN.1 UPER/PER and MLME element parsers.
· Accept: the zero-click baseband class lands in a verified parser inside a compartment instead of a proprietary RTOS with DMA.
· Trace: CJ-FORMAT · [L881](verification-maximal-os.md#L881)

**R-12-041** MUST — The cellular stack implements only NR RRC and 5G-core NAS and their 6G successors: no 2G/3G/4G protocol state machine exists in it, so legacy attach, fallback, and silent downgrade are unexpressible rather than merely refused.
· Accept: the software floor matches the hardware generation floor (R-15-129).
· Trace: CJ-FORMAT · [L882](verification-maximal-os.md#L882)

**R-12-042** MUST — Within 5G/6G a null or broken cipher is rejected and mutual authentication (5G-AKA) is required, so *no downgrade, no null cipher, mutual authentication* is a verified property of the L2/L3 servers for all non-emergency service, not a user toggle.
· Accept: emergency calling is a separate mode, not an exception carved into this property.
· Trace: CJ-CRYPTO-SPEC · [L882](verification-maximal-os.md#L882)

**R-12-043** MUST — The data/control split runs through the radio stack: the wire parsers are the data plane and the protocol state machines (RRC/NAS/RLC sequencing, MLME, L2CAP/GATT and their T3xx-class timers) are Lustre control planes compiled by Vélus.
· Accept: causality and per-reaction WCET are structural on the most-attacked remote surface; flow theorems govern what crosses from radio to platform.
· Trace: CJ-VELUS, CJ-NI · [L883–884](verification-maximal-os.md#L883)

**R-12-044** MUST — Cellular and Wi-Fi session keys live in crypto-core-backed compartments; the air-interface stack sees only the handles it needs.
· Accept: no session key is resident in an air-interface compartment.
· Trace: CJ-CRYPTO-SPEC · [L885](verification-maximal-os.md#L885)

**R-12-045** IS — The eUICC is the one tolerated foreign computer, contained as a register-slave crypto oracle for network authentication with zero platform authority: no DMA, no interrupt beyond its mailbox, nothing to grant.
· Accept: its compromise costs cellular authentication and nothing else.
· Trace: CJ-CERISE · [L886–887](verification-maximal-os.md#L886)

**R-12-046** MUST — The eUICC's physical interface is a fixed-function ISO7816 interface block: host-generated card clock divided from the platform clock, bit-level framing and parity in hardware, a small bounded FIFO, and a mailbox MSI on completion — a block that moves bytes and interprets nothing.
· Accept: no DMA and no APDU semantics exist in silicon.
· Trace: CJ-SAIL · [L888](verification-maximal-os.md#L888)

**R-12-047** MUST — APDU/TPDU traffic is parsed only in software by a Narcissus-derived verified copy-once reader in the AKA client compartment.
· Accept: the one tolerated foreign computer speaks to the platform only through a verified parser inside a zero-authority compartment.
· Trace: CJ-FORMAT · [L889](verification-maximal-os.md#L889)

### 12.8 Emergency calling

**R-12-048** IS — Emergency service runs in a zero-authority emergency compartment holding no volume keys, no user data, and no persistent identity beyond the regulation-mandated IMEI and location, so its unauthenticated bearer can carry only what regulation already compels the device to disclose.
· Accept: the *no downgrade, no null cipher, mutual authentication* property is scoped to non-emergency service, and emergency calling is a distinct, separately-verified mode rather than a relaxation of it.
· Trace: CJ-NI · [L890–893](verification-maximal-os.md#L890)

**R-12-049** MUST — Entry is an unspoofable, deliberate local act — the user placing the call over the trusted consent path, or a regulatory trigger — and never network-initiated, RoT-attested and surfaced through the secure-attention indicator.
· Accept: a rogue base station cannot bid the device into an unauthenticated emergency mode to strip its crypto.
· Trace: CJ-NI, CJ-DEVTREE · [L894](verification-maximal-os.md#L894)

**R-12-050** IS — Because emergency registration attaches on the IMEI with no subscription secret, the mode needs no eUICC and works identically at Before First Unlock, after a duress crypto-erase, or with no eUICC provisioned; on call end the compartment is torn down and eager-zeroized.
· Accept: no state carries into normal operation; the 5G/6G coverage limit is booked in §15 and §17.
· Trace: CJ-CERISE · [L895](verification-maximal-os.md#L895)

**R-12-051** MUST — The microphone reaches the emergency compartment by the ordinary rule, not an exception: the same unspoofable local act is the consent act on which the powerbox mints a microphone capability bounded to that compartment alone.
· Accept: no new minter and no ambient authority; the lock-state cut revokes grants and a peripheral no live grant holds falls dark (R-15-147).
· Trace: CJ-NI, CJ-CERISE · [L896–899](verification-maximal-os.md#L896)

**R-12-052** IS — That grant is deliberately exempt from the while-active ceiling, its bound being the call's own lifetime, which teardown enforces.
· Accept: this is a stated exception to R-08-040 and the only one; the ceiling exists to force re-affirmation, and interrupting an emergency call to re-prompt would turn a safety mechanism into a hazard.
· Trace: CJ-NI · [L900](verification-maximal-os.md#L900)

**R-12-053** MUST — The mode cannot serve as a covert microphone: entry lights the secure-attention indicator and a live grant drives the peripheral's hardware enable and in-use indication, so the microphone is never live without both being visible.
· Accept: both signals are RoT-driven.
· Trace: CJ-DEVTREE · [L901](verification-maximal-os.md#L901)

**R-12-054** MUST — The sealed physical cutoffs still dominate and are not overridden: a thrown microphone switch yields a connected but mute emergency call, and a thrown radio switch yields none at all.
· Accept: a software path able to re-enable a sealed cutoff for emergencies is a software path able to re-enable it; the direction is booked in §17.
· Trace: CJ-T · [L902–903](verification-maximal-os.md#L902)

### 12.9 Regulatory layering

**R-12-055** MUST — Compliance is enforced primarily by passive matter in three layers: the passive analog envelope (band-limited PA, fixed filters, fixed-gain final stage, narrowband antenna), OTP/RoT-latched limit registers, and the attested frozen radio generation.
· Accept: multi-band is a switched bank of pre-certified fixed paths, so every reachable RF configuration is one that passed certification; a fully compromised radio stack cannot exceed the envelope.
· Trace: CJ-DEVTREE · [L904–913](verification-maximal-os.md#L904)

**R-12-056** IS — The design rule is that the emission envelope is physically or OTP-immutable while the protocol stack stays patchable per generation, behaviour changes going through delta re-certification.
· Accept: a fully fused radio could never patch its most-attacked surface.
· Trace: CJ-DEVTREE · [L914](verification-maximal-os.md#L914)

### 12.10 Drivers, USB, and input

**R-12-057** MUST — There is one compartment per device; register and DMA access go through the verified HAL primitives, so driver logic is fully safe Rust, device registers reached through a typed register interface that is the safe-Rust face of the same register-description-language layout the HAL is generated and verified against.
· Accept: driver code never open-codes a shift or mask; DMA is only through explicit capability grants the fabric checks; drivers are restartable without reboot.
· Trace: CJ-HAL · [L915](verification-maximal-os.md#L915)

**R-12-058** MUST — USB is fully in userland with per-device authorization, and the USB data path is gated on the attested lock state: a Before-First-Unlock or idle-locked device is charging-only, its DMA window unopened and any new-peripheral authorization deferred to post-unlock powerbox consent.
· Accept: juice-jacking and lock-screen wired extraction have no data path; the charging path stays live through the fixed-function power-delivery sequencer.
· Trace: CJ-CERISE · [L916](verification-maximal-os.md#L916)

**R-12-059** MUST — A user may force charging-only directly and independently of lock state through a physical restricted-mode control driving the fixed-function data-lane mux.
· Accept: because the cut is at the mux, the attacker device never reaches the USB stack's enumeration and descriptor-parse path (R-15-151).
· Trace: CJ-CERISE · [L917–918](verification-maximal-os.md#L917)

**R-12-060** IS — USB is profiled by capability, not specification version, on two rules that do not turn on which generation a port negotiates.
· Accept: a newer physical layer and FEC are admitted freely where throughput warrants, and lower-generation devices stay supported as data devices on the same terms.
· Trace: CJ-CERISE · [L919–920](verification-maximal-os.md#L919), [L925](verification-maximal-os.md#L925)

**R-12-061** MUST — The floor is cryptographic device and cable authentication before a data role is granted, re-grounded on ML-DSA identities rather than the stock profile's ECDSA and carried by Narcissus-checked parsers; an unauthenticated device is held charging-only exactly as a locked one is.
· Accept: the DMA window stays unopened until a post-unlock powerbox consent admits it.
· Trace: CJ-CRYPTO-SPEC, CJ-FORMAT · [L921](verification-maximal-os.md#L921)

**R-12-062** MUST NOT — The ceiling is no tunneling: the USB4 fabric's PCIe, DisplayPort, and USB tunnels, its connection manager, its Thunderbolt alternate mode, and its general vendor-defined-message extensions are declined together.
· Accept: no foreign PCIe topology, no DMA-over-USB endpoint, and no tunneling-protocol grammar is ever admitted; the one admitted alternate mode is output-only DisplayPort (R-15-233).
· Trace: CJ-CERISE · [L922–924](verification-maximal-os.md#L922)

**R-12-063** MUST — An external input device attaches as a USB HID-class device through the verified userland USB stack under per-device authorization, its report descriptor parsed copy-once by Narcissus.
· Accept: a HID-injection or BadUSB device is confined by that authorization plus capability containment rather than trusted as an ambient input path.
· Trace: CJ-FORMAT · [L926–927](verification-maximal-os.md#L926)

**R-12-064** MUST NOT — There is no legacy input controller (no PS/2, i8042) and no legacy interrupt controller (no wired IRQ line, 8259-PIC, or ambient PLIC routing); all device servicing is time-triggered polling of latched pending bits in scheduled slots.
· Accept: the ambient device-interrupt interface is absent twice over — no routing surface, and no delivery path for one to route into.
· Trace: CJ-KERNEL · [L928–930](verification-maximal-os.md#L928)

**R-12-065** MUST — Embedded-controller functions are dissolved: power sequencing and reset are RoT duties, battery gauging is on-die coulomb-counting read by a contained server, thermal sensing feeds the sentinel, and keyboard and touch are register-slave scan interfaces behind ordinary drivers.
· Accept: pure-analog pack protection remains off-die as non-programmable hardware; there is no EC firmware because there is no EC.
· Trace: CJ-DEVTREE · [L931–934](verification-maximal-os.md#L931)

**R-12-066** MUST — USB-PD contract negotiation is a fixed-function bounded state machine over the CC-line messages, with negotiated voltage and current bounded by analog pack protection (primary) and RoT-latched PD limit registers (secondary).
· Accept: no bus and no arbitrary negotiation rides the power channel.
· Trace: CJ-DEVTREE · [L933](verification-maximal-os.md#L933)

### 12.11 Sensors, camera, and the front-end doctrine

**R-12-067** MUST — Camera sensors are register slaves streaming raw Bayer over a capability-bounded DMA interface block, with the entire ISP pipeline (demosaic, 3A, tone mapping) software on V-class cores in the app's or camera server's compartment.
· Accept: no ISP firmware exists.
· Trace: CJ-CERISE · [L935](verification-maximal-os.md#L935)

**R-12-068** IS — The sensor front-end doctrine is one rule across the class: the analog front-end plus its scan, sample, or event sequencer is *matter*, while every stage carrying signal semantics is verified host software in the device's driver or server compartment.
· Accept: it applies uniformly to the radio transceiver, camera, fingerprint sensor, capacitive touch, the audio front-end, and IMU/motion sensors.
· Trace: CJ-CERISE · [L937–939](verification-maximal-os.md#L937)

**R-12-069** IS — The line is fixed-function versus programmable, not raw versus processed: an AFE may carry fixed-function analog and mixed-signal conditioning, which lowers sample rate and host DSP load, while the programmable, adaptive, policy-laden stage stays host software.
· Accept: because that conditioning is a fixed transfer function and not a writable state machine, it adds no programmable state to the Sail model — performance at no proof cost.
· Trace: CJ-SAIL · [L940](verification-maximal-os.md#L940)

**R-12-070** IS — Readout may be event-driven rather than fixed-cadence, the comparator and the event pixel being matter, so the host DSP idles between events and only changes cross the boundary.
· Accept: event timing is data-dependent, and the no-timing-channel property is kept by confining event and wake traffic to the owning island's statically-partitioned NoC and memory budget. **See [D-08](#d-08).**
· Trace: CJ-ISOL · [L941–943](verification-maximal-os.md#L941)

**R-12-071** IS — On the confidentiality ledger the event-driven change is neutral-to-positive: the island partition restores the constant-from-outside property, and emitting only changes shrinks the exposed data, leaving a worst-case-bandwidth reservation as the sole residual — a power-margin cost, not a confidentiality one.
· Accept: an event-streaming DMA holds a bounded capability that honours the §8 revocation sweep like any other transfer.
· Trace: CJ-NI, CJ-CERISE · [L943–944](verification-maximal-os.md#L943)

**R-12-072** IS — The raw-AFE silicon and its host-side DSP are a net-new co-design, and the continuous host-cycle and report-latency budget each consumes is a §11 scheduled task: the honest cost of dissolving the firmware the doctrine deletes.
· Accept: the §17 entry exists (R-15-142).
· Trace: CJ-WCET · [L946](verification-maximal-os.md#L946)

### 12.12 Service manager

**R-12-073** MUST — The service manager is a static supervision tree with declarative units and no ambient authority, restarting with backoff and capability re-grant, realized as a synchronous Lustre state machine.
· Accept: its start-order, crash detection, restart-with-backoff, and capability re-grant have deterministic, bounded, hidden-state-free reactions by construction.
· Trace: CJ-VELUS · [L947–948](verification-maximal-os.md#L947)

**R-12-074** MUST — Restart re-grant mints no new authority: it re-instantiates exactly the edges the capDL-class manifest already fixed, under the same initialisation-refinement obligation.
· Accept: the supervision tree is an authority re-instantiator, never a minter; the powerbox alone mints, and it alone joins the TCB.
· Trace: CJ-NI, CJ-KERNEL · [L949–950](verification-maximal-os.md#L949)

### 12.13 Display, render, and the consent path

**R-12-075** MUST — Display and render use per-surface and per-input capabilities with no ambient observation of input or output, so keylogging and screen-scraping are unexpressible.
· Accept: capture requires per-window capabilities.
· Trace: CJ-NI, CJ-CERISE · [L951](verification-maximal-os.md#L951)

**R-12-076** MUST — Consent for a powerbox grant is owned by a separate, small, verified trusted-path agent, not the compositor: it renders the consent surface into a region it holds by capability, is attested by an RoT-driven hardware secure-attention indicator the compositor cannot draw, and takes the response over the input front-end itself.
· Accept: the compositor can deny service — an availability fault — but cannot spoof a grant or capture a response.
· Trace: CJ-NI, CJ-DEVTREE · [L952–954](verification-maximal-os.md#L952)

**R-12-077** MUST NOT — The touch driver does not join the consent TCB: for the prompt's duration the touch front-end is re-delegated to the agent, its capability-bounded DMA window *and* its configuration MMIO leaving the driver together.
· Accept: front-end ownership is indivisible, because a driver holding the scan configuration could blind the agent, remap the scan so a touch outside the rendered button reads as inside it, or drive the gain so no press registers (R-15-143).
· Trace: CJ-DEVTREE · [L955–959](verification-maximal-os.md#L955)

**R-12-078** MUST — The switch is RoT-latched and does not depend on the driver yielding: the front-end carries an ownership register latched by the RoT, unwritable by software while the latch holds, driven by the same RoT signal that lights the secure-attention indicator.
· Accept: the property is a hardware bi-implication — the indicator cannot be lit while the driver owns the front-end, and the agent cannot own the front-end without the indicator being lit — that the compositor, the driver, and a compromised kernel alike cannot separate.
· Trace: CJ-DEVTREE, CJ-NI · [L960–963](verification-maximal-os.md#L960)

**R-12-079** MUST — What joins the consent TCB is a fixed threshold-and-centroid reduction over the region the agent rendered, with no adaptive state, its baseline snapshotted by the agent from its own first frames at prompt entry and held fixed.
· Accept: an externally-supplied baseline is refused as a security property, a chosen baseline being what turns an untouched panel into a press.
· Trace: CJ-NI · [L964–967](verification-maximal-os.md#L964)

**R-12-080** IS — Two costs are accepted: touch is unavailable to applications while a prompt is up, and the driver's adaptive baseline goes stale across the prompt and re-converges on return.
· Accept: both are stated; the second is a latency artifact, not a correctness one.
· Trace: CJ-NI · [L968](verification-maximal-os.md#L968)

**R-12-081** MUST — A consent response is accepted only from a front-end whose ownership the RoT can latch: the on-device register-slave front-ends qualify, and an external USB HID keyboard or pointer does not.
· Accept: a BadUSB or HID-injection device is not merely confined with respect to consent but unable to express a response; a prompt additionally requiring a credential is gated by the credential service over the fingerprint AFE on the same ownership terms.
· Trace: CJ-DEVTREE · [L969–971](verification-maximal-os.md#L969)

**R-12-082** IS — Rendering is software on V-class cores: graphics acceleration is the general-purpose RVV datapath, so the render and compositor servers are the whole of the graphics driver.
· Accept: there is no GPU driver, no command-stream validator, and no shader-IR compiler in the display path.
· Trace: CJ-CERISE · [L972](verification-maximal-os.md#L972), [L975](verification-maximal-os.md#L975)

**R-12-083** IS — The 2D and text substrate has safe-Rust start-froms, but there is no viable no-JIT software 3D, so the RVV software rasterizer for 3D is genuinely net-new engineering.
· Accept: llvmpipe JITs, which W^X forbids.
· Trace: CJ-TAL-SOUND · [L973](verification-maximal-os.md#L973)

**R-12-084** IS — Surfaces are plain memory under CHERI; the only display device is the scanout controller, a firmware-free open-RTL DMA block behind a static capability-bounded DMA window over the framebuffer.
· Accept: consistent with R-15-229.
· Trace: CJ-CERISE · [L974](verification-maximal-os.md#L974)

### 12.14 Inference and telemetry

**R-12-085** IS — The inference server is an optional Tier-1 compartment exposing quantized-inference sessions over rings, with weights de-quantized and any microscaling block-scale applied in software on the M-class vector unit.
· Accept: models are content-addressed store objects; per-session memory is capability-delegated and zeroized on teardown.
· Trace: CJ-CERISE · [L976](verification-maximal-os.md#L976)

**R-12-086** MUST — The telemetry monitor is permanently resident on the dedicated S-class sentinel core, consuming the native sensor grid: CHERI validity-tag traps, slot-overrun faults, DMA capability-check denials, health heartbeats, ECC and NoC error telemetry, thermal sensors, and radio-limit-register violation traps.
· Accept: detection latency is a proved bound under any load, and responses (restart, revoke, roll back) run under the same guarantees.
· Trace: CJ-WCET, CJ-ISOL · [L977–979](verification-maximal-os.md#L977)

---

## §13 — Packaging & Supply Chain

### 13.1 The admitted artifact

**R-13-001** IS — A package is content plus a capability manifest plus a proof object; installation is proof check, store insertion, and capability wiring.
· Accept: no other installation step exists.
· Trace: CJ-TAL-SOUND · [L985–986](verification-maximal-os.md#L985)

**R-13-002** MUST NOT — There are no maintainer scripts, no post-install execution, and no runtime code fetching by system components.
· Accept: the installation path executes no package-supplied code.
· Trace: CJ-CERISE · [L987](verification-maximal-os.md#L987)

**R-13-003** IS — The admitted artifact is a content-addressed capability image, not an ELF-style executable container: a set of content-addressed objects named by a small typed manifest — the immutable code-and-rodata image, a separate writable data-initializer, the CHERI-TAL typing derivation, the capability-wiring table, and the capability manifest with its §12 interface descriptor.
· Accept: no interpreted, offset-linked container grammar is parsed on-device.
· Trace: CJ-TAL-SOUND, CJ-FORMAT · [L988–989](verification-maximal-os.md#L988)

**R-13-004** MUST — Execute authority is wired only over the immutable code-and-rodata image, hash-verified against the signed root.
· Accept: no execute capability is derived over written memory.
· Trace: CJ-CERISE · [L989](verification-maximal-os.md#L989)

**R-13-005** MUST — The writable data-initializer is a fresh allocation, eager-zeroized at its plan-assigned slots and *uninitialized* in the CHERI-TAL derivation until stored to, never conflated with the image.
· Accept: the definite-initialization attribute (R-05-119) governs it from its allocation point.
· Trace: CJ-MEMPLAN, CJ-TAL-SOUND · [L989](verification-maximal-os.md#L989)

**R-13-006** IS — The capability-wiring table is the platform's relocation model: per capability slot, the source object, offset, bounds, and permission set, deriving monotonically from the initial distribution.
· Accept: no relocation entry constructs a capability (R-05-136).
· Trace: CJ-CERISE · [L989](verification-maximal-os.md#L989)

**R-13-007** IS — The same objects live loose and deduplicated in the content-addressed store and serialize to one self-contained hash-indexed pack; a removable or portable image maps in place and executes from its hash-verified read-only region with no unpack step.
· Accept: single-file convenience and content addressing are the same objects in two containers, not a tradeoff.
· Trace: CJ-DEVTREE · [L990–992](verification-maximal-os.md#L990)

**R-13-008** IS — Transfer between systems is a set difference: a content-aware copy or fetch writes and moves only the objects the destination lacks, each verified by hash on arrival, and the have/want exchange stays within a confidentiality domain.
· Accept: it is therefore not a cross-domain membership oracle — the transfer-time form of the §10 rule that dedup never crosses a domain.
· Trace: CJ-NI · [L993](verification-maximal-os.md#L993)

**R-13-009** MUST — The on-device pack decoder is a Narcissus copy-once verified reader over a fixed-layout, schema-bounded format (header, flat hash-indexed object table, blob region) with every object independently hash-verified, so a corrupt index fails a hash check rather than driving a parser.
· Accept: the loader is never an attacker-facing grammar in the trust base; the format descriptor is a crown-jewel spec discharged by compiling it, not hand-writing it.
· Trace: CJ-FORMAT · [L994](verification-maximal-os.md#L994)

**R-13-010** MUST NOT — ELF and any conventional executable container are off-device only: the certifying toolchain may emit ELF as build interchange, and package build transforms it into the pack at store-insertion time.
· Accept: the on-device loader is deleted rather than hardened.
· Trace: CJ-FORMAT · [L995](verification-maximal-os.md#L995)

### 13.2 Assurance tiers

**R-13-011** IS — There are exactly three assurance tiers. **Tier 0** (TCB components): full functional refinement at binary level, robust preservation of compartment isolation, and the non-interference theorem over the full component graph, admitted by CIC proof terms mostly checked at release time. **Tier 1** (servers crossing confidentiality boundaries): binary-level policy proofs — memory/ABI conformance, handler termination, information-flow theorems from the IDL annotations, and constant-time for secret-labeled paths — admitted by CHERI-TAL taint typing where structured. **Tier 2** (apps and contained code): a mandatory binary-level memory-safety certificate, admitted by a typing derivation the on-device type-checker checks.
· Accept: every admitted artifact carries exactly one tier and its required evidence.
· Trace: CJ-TAL-SOUND, CJ-NI · [L998–1003](verification-maximal-os.md#L998)

**R-13-012** IS — The Tier-2 certificate's content is enumerated: ABI/type well-formedness, no runtime codegen, manifest consistency, temporal safety, definite initialization, and CFI. Full functional PCC is deliberately not required, because app intent is unspecified.
· Accept: admission is type-checking the artifact, not trusting the producer.
· Trace: CJ-TAL-SOUND · [L1003](verification-maximal-os.md#L1003)

**R-13-013** MUST NOT — There is no `#![forbid(unsafe_code)]` shortcut and no uncertified-admission path: Rust source discipline is one way to produce the Tier-2 derivation, and any producer of a well-typed binary is admitted identically.
· Accept: no admission rule reads a producer identity.
· Trace: CJ-TAL-SOUND · [L1005](verification-maximal-os.md#L1005)

**R-13-014** IS — The hardware universal contract remains beneath every tier as defense in depth against a certifier or spec error, but it is a *refuse-uncertified-code* policy, not permission to run uncertified code.
· Accept: no admitted path runs code that failed a check.
· Trace: CJ-CERISE · [L1006](verification-maximal-os.md#L1006)

**R-13-015** MUST NOT — The universal contract is deliberately not extended to initialization safety, because a hardware Write-before-Read plane would hedge the admission type-check itself.
· Accept: consistent with R-15-035 and R-05-119.
· Trace: CJ-CERISE · [L1007](verification-maximal-os.md#L1007)

**R-13-016** MUST — The universal contract is stated over the CHERI-RISC-V Sail model, with Katamaran discharging the per-instruction separation-logic obligations between Isla and Islaris, and Cerisier extending the Cerise contract to attestation.
· Accept: capability safety plus local attestation is Coq-native prior art rather than an unmodeled seam.
· Trace: CJ-CERISE, CJ-SAIL · [L1008](verification-maximal-os.md#L1008)

**R-13-017** IS — These are one Iris-over-Sail program logic with four theories, not five frameworks: unary safety, the Cerise/Cerisier universal contract, relational constant-time, and syntax-directed cost, all instantiating the same leakage- and cost-annotated Sail semantics, with StkTokens supplying the linear/affine stack discipline.
· Accept: the semantic-anchor budget counts one logic (R-05-019).
· Trace: CJ-SAIL, CJ-CT-SOUND · [L1009](verification-maximal-os.md#L1009)

**R-13-018** IS — Code targeting V/M-class cores is ordinary Tier-2 or Tier-1 native code: a "shader" or "kernel" is AOT-compiled and certified off-device, then admitted like any other binary.
· Accept: there is no on-device compiler and no shader-IR compiler in any datapath.
· Trace: CJ-TAL-SOUND · [L1010](verification-maximal-os.md#L1010)

**R-13-019** MUST — Apps needing `unsafe` are inadmissible at Tier 2 unless the `unsafe` routes through the verified HAL or the app ships a manual memory-safety proof.
· Accept: no third disposition exists.
· Trace: CJ-HAL, CJ-TAL-SOUND · [L1011](verification-maximal-os.md#L1011)

**R-13-020** MUST — Any app receiving secret-labeled material carries the binary-level constant-time obligation; apps that touch no secrets carry no CT proof.
· Accept: the secret-touching set is derived from the §12 labeling. **See [D-04](#d-04).**
· Trace: CJ-CT-SOUND, CJ-IDL · [L1012](verification-maximal-os.md#L1012)

### 13.3 Trust boundaries and supply chain

**R-13-021** IS — There are two trust boundaries: inter-compartment containment is compiler-independent at binary level (the universal contract), and intra-compartment memory safety is proven at binary level by the Tier-2 certificate rather than trusted to the Rust toolchain.
· Accept: the certificate removes a trusted dependency; it does not weaken containment, which is retained beneath it.
· Trace: CJ-TAL-SOUND, CJ-CERISE · [L1013–1016](verification-maximal-os.md#L1013)

**R-13-022** IS — There is no trusted-toolchain fallback: the certifying compiler is a hard prerequisite for *building* contained code, but the prerequisite is on the build, not on admission, which gates on the derivation itself.
· Accept: mandating the toolchain is not pedigree enforcement; no uncertified app is ever admitted.
· Trace: CJ-TAL-SOUND · [L1017–1018](verification-maximal-os.md#L1017)

**R-13-023** MUST — Supply-chain defense is two mechanisms, not one: build-integrity (reproducible builds, DDC, and the proof object) against a *corrupted* artifact or a trusting-trust compiler, and compose-time confinement against a *subverted-but-memory-safe upstream*.
· Accept: the first does nothing against a logic backdoor that compiles cleanly and carries a valid Tier-2 certificate — the xz/liblzma archetype — and the split is stated rather than blurred.
· Trace: CJ-CERISE · [L1019–1020](verification-maximal-os.md#L1019)

**R-13-024** MUST — The package manifest declares the app's internal compartment graph, each attacker-facing or third-party dependency taking a least-authority sub-manifest, so the seal/switch boundary confines a malicious dependency to the capabilities it was explicitly granted.
· Accept: the Tier-2 certificate handles the corruption dimension of a bad dependency; intra-app compartmentalization handles the authority dimension.
· Trace: CJ-CERISE · [L1021–1022](verification-maximal-os.md#L1021)

**R-13-025** IS — Proof-carrying code gates admission; it never relaxes runtime enforcement.
· Accept: no runtime check is elided on the strength of a certificate.
· Trace: CJ-CERISE · [L1023](verification-maximal-os.md#L1023)

**R-13-026** MUST — Bit-for-bit reproducibility stays mandatory and DDC bounds trusting-trust, their role confined to what proofs do not cover — chiefly Tier-2 functional correctness, memory safety and CFI being proven and app intent not.
· Accept: every release is reproducible and DDC-checked.
· Trace: CJ-T · [L1024](verification-maximal-os.md#L1024)

**R-13-027** MUST — Compilation and proving both stay off-device: the on-device admission fast path is type-checking the CHERI-TAL derivation plus install-time capability wiring, and the certifying toolchain is a build path, not an on-device service.
· Accept: proof objects may ship oracle-compressed.
· Trace: CJ-TAL-SOUND · [L1025](verification-maximal-os.md#L1025)

**R-13-028** IS — Deep proofs are not cheap and are not per-device: Tier-0 functional refinement and non-interference are validated by the CIC kernel at release time over the base-image TCB and bound into the signed measured-boot root, while the lower-volume hyperproperty certificates an installed component carries (crypto reduction, constant-time, WCET) are CIC-checked when present, off the type-checking fast path.
· Accept: on-device admission is the TAL type-check plus wiring, with the CIC kernel reserved for the base image and the few certificate-carrying installs.
· Trace: CJ-NI, CJ-KERNEL · [L1026–1027](verification-maximal-os.md#L1026)

**R-13-029** MUST — SBOM and proof artifacts ship with every release.
· Accept: both are present in the release manifest.
· Trace: CJ-T · [L1028](verification-maximal-os.md#L1028)

---

## §14 — Userland

**R-14-001** MUST — Core utilities are capability-native and reimplemented, not ported.
· Accept: no utility depends on an ambient-authority interface.
· Trace: CJ-CERISE · [L1034](verification-maximal-os.md#L1034)

**R-14-002** MUST — System-wide W^X is a proven invariant, not a convention: CHERI capability monotonicity plus a machine-checked absence of Store∧Execute in the static initial capability distribution makes it an invariant of the entire capability derivation forest, object- and capability-granular, inside the Sail model.
· Accept: it is checked over the composed distribution, not asserted per component.
· Trace: CJ-CERISE, CJ-SAIL · [L1035–1036](verification-maximal-os.md#L1035)

**R-14-003** IS — W^X subsumes the Harvard split, DEP, and the per-page no-execute bit, and supplies the *whole* of W^X rather than the necessary half: monotone derivation cannot mint execute authority over a writable region, so the writable-to-executable promotion primitive an NX bit must be paired with never exists.
· Accept: the coarse page-granular hedge is declined on the same grounds as the MMU and PMP.
· Trace: CJ-CERISE · [L1037–1042](verification-maximal-os.md#L1037)

**R-14-004** MUST NOT — The invariant admits no runtime-codegen exception: the sole way an executable region appears is install-time capability wiring deriving execute-only authority over read-only regions of the content-addressed image.
· Accept: newly compiled code — apps, servers, and V/M-class shaders alike — travels that same admitted-image path, so execute authority is never derived over written memory; nothing on the device JITs, interpreters run pure, and there is no kernel-mediated re-derivation primitive.
· Trace: CJ-CERISE · [L1043–1046](verification-maximal-os.md#L1043)

**R-14-005** IS — Apps are unverified *for functional correctness*, contained, and each a least-authority domain wired at compose time; app logic is memory-safe by construction, though not by default functionally proven.
· Accept: safe Rust by default, or any language whose binary carries the §13 memory-safety certificate.
· Trace: CJ-TAL-SOUND · [L1047](verification-maximal-os.md#L1047)

**R-14-006** MUST — Intra-app library compartmentalization covers the authority dimension the memory-safety certificate does not: an app may partition itself into library compartments, each a node in the machine-checked component graph carrying its own least-authority sub-manifest, with cross-compartment calls mediated by the same seal/switch primitives that separate whole apps.
· Accept: no new mechanism, and the intra-app graph is fixed at build time, so it neither mints dynamic privilege nor escapes the §8 theorem.
· Trace: CJ-CERISE, CJ-NI · [L1049–1051](verification-maximal-os.md#L1049)

**R-14-007** MUST — Sub-compartmentalization is required where the authority gap bites: any dependency parsing attacker-controlled input, and any third-party library handed capabilities beyond pure compute.
· Accept: a compromised codec reaches only the buffer capabilities it was passed, and because those buffers are handed over as *local* capabilities it cannot retain them past the call to exfiltrate later.
· Trace: CJ-CERISE · [L1052–1053](verification-maximal-os.md#L1052)

**R-14-008** MUST — The browser is maximally contained: per-origin compartments, no JIT, software rendering on C/V-class cores, and powerbox-only file and clipboard access.
· Accept: an origin RCE yields that origin's authority and nothing else.
· Trace: CJ-CERISE · [L1054–1055](verification-maximal-os.md#L1054)

**R-14-009** MUST — Origins come from a composition-fixed pool of *P* identical origin compartments — one manifest, one static memory plan — differing only in which origin is bound to them, because static composition admits no compartment minted at runtime.
· Accept: opening a tab binds a free pool member and raises the §11 population rung; closing one is an ordinary kernel-mediated session teardown whose capabilities die at the revocation epoch flip, which is what makes a member safe to rebind.
· Trace: CJ-CERISE, CJ-MEMPLAN · [L1056–1058](verification-maximal-os.md#L1056)

**R-14-010** MUST — Past the ceiling the browser evicts and the platform does not refuse: the (*P*+1)-th tab suspends a live origin and takes its member, the victim chosen by the browser among its own origins with no authority crossing.
· Accept: an unverifiable component decides which tab is slow and never how much time any tab gets, the §11 rung fixing the widths it may not touch.
· Trace: CJ-WCET, CJ-NI · [L1059](verification-maximal-os.md#L1059)

**R-14-011** IS — Deep tab sets are retained state, not concurrent computation; the honest form of that statement, with numbers, is §17's population wall.
· Accept: consistent with R-17-002.
· Trace: CJ-WCET · [L1060](verification-maximal-os.md#L1060)

**R-14-012** MUST NOT — There is no Linux-personality shim, ever, and no VM: faithful syscall translation is an ambient-authority emulator, and foreign binaries simply do not run.
· Accept: the only on-ramp is source-level recompilation against a WASI-shaped capability libc whose filesystem is a private, manifest-backed namespace; such ports are ordinary Tier-2 citizens.
· Trace: CJ-CERISE · [L1061–1064](verification-maximal-os.md#L1061)

**R-14-013** IS — *WASI-shaped* is API vocabulary, not substrate: everything compiles to native RV64+CHERI, and Wasm is not a system execution target. An app may embed an interpreter-mode Wasm engine as its private plugin mechanism, invisible to the architecture.
· Accept: no Wasm runtime exists in any system image (R-05-085).
· Trace: CJ-TAL-SOUND · [L1065–1067](verification-maximal-os.md#L1065)

---

## §15 — Hardware Platform

### 15.1 ISA baseline

**R-15-001** IS — The ISA is RV64IMV + CHERI: base IM_Zicsr, `A` narrowed to `Zaamo`+`Zabha`, no scalar `F`/`D`, V supplying all floating point, no C/compressed, purecap-only with no hybrid mode.
· Accept: the frozen profile enumerates exactly this extension set; any encoding outside it traps (R-15-014).
· Trace: CJ-SAIL · [L1075](verification-maximal-os.md#L1075)

**R-15-002** IS — The platform is single-physical-address-space under CHERI: no MMU, `satp` fixed to Bare, no Sv39 translation.
· Accept: the Sail model carries no translation state; no page-table walker exists in any RTL.
· Trace: CJ-SAIL, CJ-KERNEL · [L1075](verification-maximal-os.md#L1075), [L1170–1172](verification-maximal-os.md#L1170)

**R-15-003** IS — There is a single privilege mode (Machine only). Privilege is a CHERI permission on the PCC (access-system-registers), not a ring.
· Accept: the S/U CSR banks, trap delegation (`medeleg`/`mideleg`), `sret`, and `Sstc`'s `stimecmp` are absent from the decode, the CSR bank, and the kernel proof.
· Trace: CJ-SAIL, CJ-KERNEL · [L1075](verification-maximal-os.md#L1075), [L1174–1176](verification-maximal-os.md#L1174)

**R-15-004** IS — The architectural memory model is Ztso (RVTSO), adopted normatively in place of RVWMO.
· Accept: RVWMO is retained neither in hardware nor in proof reasoning; every ring proof is restated under Ztso.
· Trace: CJ-SAIL · [L1095–1096](verification-maximal-os.md#L1095), [L1767](verification-maximal-os.md#L1767)

**R-15-005** MUST — There is exactly one Sail model, parameterized by core class (VLEN, matrix geometry), and exactly one capability encoding.
· Accept: no second CHERI dialect (CHERIoT's compressed RV32 format included) exists; no second capability encoding forks the model, the RoT's scalar core included.
· Trace: CJ-SAIL · [L1076](verification-maximal-os.md#L1076), [L1081](verification-maximal-os.md#L1081), [L1363](verification-maximal-os.md#L1363)

**R-15-006** MUST NOT — No hypervisor extension: the platform hosts no guests.
· Accept: the profile excludes H; the guest/VS interrupt-file machinery is absent (R-15-062).
· Trace: CJ-SAIL · [L1077](verification-maximal-os.md#L1077)

**R-15-007** MUST — CHERI is version-pinned like every other extension: the 128-bit purecap encoding, the object-type and permission space, the sentry mechanism, and the capability instruction set are frozen with the profile and tracked to the RISC-V 'Y' line.
· Accept: the profile records a pin; as 'Y' ratifies, the frozen dialect re-pins to the ratified RVY base rather than a private snapshot.
· Trace: CJ-SAIL · [L1078–1079](verification-maximal-os.md#L1078)

**R-15-008** IS — The base sealed-entry and forward/backward-edge sentry semantics are the only sentry semantics the profile carries; the frozen dialect adds no sentry surface to the standard-track base.
· Accept: CHERIoT's interrupt-state sentry variants are absent (R-15-078).
· Trace: CJ-SAIL · [L1080](verification-maximal-os.md#L1080)

**R-15-009** IS — The bespoke matrix extension is fork-and-frozen with full Sail semantics until a ratified RISC-V matrix extension (AME/IME lineage) supersedes it, at which point it re-pins.
· Accept: the Sail model carries full matrix semantics; a re-pin obligation is recorded.
· Trace: CJ-SAIL · [L1076](verification-maximal-os.md#L1076)

### 15.2 The five-part admission test

**R-15-010** MUST — An extension or feature is admissible only if it satisfies all five tests: (1) deterministic architectural semantics, a function of architectural state and Sail-expressible; (2) data-independent timing, discharged by operand-value-independent latency, by a proof that no secret-labeled operand reaches it, or by confinement of the data-dependence to the owning island's static NoC and memory partition, and by no other route; (3) no new hidden shared microarchitectural state surviving a partition switch un-flushed by `fence.t`, discharged by absence, by flushing, or by being provably constant across the switch interval, and by no other route; (4) no new authority path outside capabilities; (5) no autonomous behaviour — no hardware walkers, updaters, or feedback loops.
· Accept: each admitted feature carries five recorded dispositions, each naming which enumerated discharge form it takes; the case law of the event-driven sensor readout (R-12-070) and the frozen 1000BASE-T canceller (R-15-137) is now statute rather than precedent.
· Trace: CJ-SAIL, CJ-LEAK · [L1086](verification-maximal-os.md#L1086)

**R-15-011** MUST NOT — Bare self-exclusion from the constant-time list is not a pass for test (2): the exclusion is itself the proof obligation, and a feature neither constant-time nor provably secret-unreachable is inadmissible.
· Accept: every off-list feature has a discharged flow-discipline obligation, not a declaration.
· Trace: CJ-LEAK, CJ-NI · [L1086](verification-maximal-os.md#L1086)

**R-15-012** IS — Speculation fails tests (1)–(3); SMT fails (3) by construction; dynamic branch prediction fails (3); `Zalrsc` fails (3) and (1).
· Accept: each is excluded, with the failing test named.
· Trace: CJ-SAIL · [L1087](verification-maximal-os.md#L1087)

**R-15-013** MUST — Defense-in-depth clause (*verify rather than hedge*): a redundant mechanism is admitted only if it is a genuinely disjoint failure domain the primary's own verification does not reach; where the primary is formally verified, the hedge is declined.
· Accept: every declined hedge (PMP, IOMMU/IOPMP, MTE, shadow stacks, Harvard split, initialization-tag plane, memory cryptography) cites this clause; every admitted one (crypto core's hardware boundary, on-die ECC, the RoT, physical cutoffs, the Faraday enclosure) shows disjointness and zero cost on the scarce axis.
· Trace: CJ-T · [L1090–1093](verification-maximal-os.md#L1090)

**R-15-014** MUST — The profile is frozen with the proof, and all reserved, custom, and unused encodings trap rather than silently executing.
· Accept: the decode traps every unallocated encoding; no encoding is a no-op by default.
· Trace: CJ-SAIL · [L1088](verification-maximal-os.md#L1088)

### 15.3 Memory model

**R-15-015** IS — Ztso is implemented natively by in-order issue plus a FIFO store buffer, at essentially no microarchitectural cost.
· Accept: the only reordering the machine exhibits is store→later-load bypass through the store buffer.
· Trace: CJ-SAIL · [L1097](verification-maximal-os.md#L1097)

**R-15-016** MUST — The Ztso guarantee is an RTL-against-Sail proof obligation: the store buffer provably exposes no ordering weaker than TSO.
· Accept: the obligation is a named bring-up gate alongside the `Zkt`/`Zvkt` timing obligation.
· Trace: CJ-RTL-SAIL · [L1109](verification-maximal-os.md#L1109), [L1287](verification-maximal-os.md#L1287)

**R-15-017** IS — `fence` instructions remain present and semantically modeled for I/O and device ordering (MMIO, DMA-descriptor visibility) and for cross-island ring ordering over shared SRAM.
· Accept: the Sail model retains `fence`; no cache-management instruction accompanies it.
· Trace: CJ-SAIL · [L1099](verification-maximal-os.md#L1099)

**R-15-018** IS — Sequential consistency was evaluated and rejected on four platform-specific grounds, and is named in §18 as a question worth revisiting, not as a pending change.
· Accept: Ztso is the specified model; the §18 entry is a question, not a deliverable.
· Trace: CJ-SAIL · [L1100–1103](verification-maximal-os.md#L1100)

### 15.4 Control-flow prediction

**R-15-019** MUST — All branch prediction is static: backward-taken / forward-not-taken, a fixed function of the instruction encoding and displacement sign, with zero mutable predictor state.
· Accept: no BHT, BTB, RAS, or dynamic direction, target, or return predictor exists in any RTL.
· Trace: CJ-SAIL, CJ-ISOL · [L1112–1113](verification-maximal-os.md#L1112)

**R-15-020** IS — Deleting the predictor structures is strictly stronger than flushing them: nothing joins the `fence.t` flush set and no residual completeness obligation exists for them.
· Accept: the flush set contains no predictor entry.
· Trace: CJ-ISOL · [L1115](verification-maximal-os.md#L1115)

**R-15-021** MUST — The predictor deletion is discharged structurally by the microarchitectural absence contract, not by RTL ⊑ Sail.
· Accept: predictor absence appears in the absence-contract register, not among the refinement obligations.
· Trace: CJ-RTL-SAIL · [L1116](verification-maximal-os.md#L1116)

**R-15-022** IS — Fetch runs ahead only down the statically determined path, so wrong-path fetch is a deterministic function of the instruction stream and never of prior execution history.
· Accept: with no I-cache, fetch reads flat SRAM at fixed latency; the only run-ahead structure is the static-path fetch buffer (R-15-152).
· Trace: CJ-WCET, CJ-ISOL · [L1117](verification-maximal-os.md#L1117)

**R-15-023** IS — The accepted cost is full pipeline-latency mispredict-equivalent penalties on forward conditional, indirect, and call/return dispatch, priced into WCET; the RAS is excluded despite its IPC value because it is per-core mutable return history.
· Accept: the WCET tables carry the penalty; no return-address prediction exists.
· Trace: CJ-WCET · [L1118](verification-maximal-os.md#L1118)

### 15.5 Atomics

**R-15-024** IS — Only the unconditional atomic-RMW half of `A` is retained: `Zaamo` at word and doubleword width, extended by `Zabha` to byte and halfword. `Zacas` (including `amocas.q`) and `Zalrsc` are excluded.
· Accept: the profile lists `Zaamo`+`Zabha` and excludes both others.
· Trace: CJ-SAIL · [L1122–1123](verification-maximal-os.md#L1122)

**R-15-025** IS — `Zalrsc` is excluded because its per-hart reservation register is hidden inter-instruction state (test 3), SC may fail spuriously (test 1), and reservation-granule contention is a cross-hart channel.
· Accept: the Sail model carries no reservation set, no spurious-failure nondeterminism, and no constrained-LR/SC forward-progress rules.
· Trace: CJ-SAIL · [L1124–1126](verification-maximal-os.md#L1124), [L1167](verification-maximal-os.md#L1167)

**R-15-026** IS — `Zacas` is excluded for want of a consumer: the multikernel is share-nothing with no kernel locks, rings are single-writer SPSC under Ztso, refcounts and status flags are single-instruction `Zaamo`, and no capability ever resides in shared mutable memory.
· Accept: no admitted software requires compare-and-swap; the 128-bit CAS coherence point is absent from the memory model.
· Trace: CJ-SAIL, CJ-KERNEL · [L1127–1128](verification-maximal-os.md#L1127), [L1131](verification-maximal-os.md#L1131)

**R-15-027** IS — `Zabha` supplies only the byte and halfword forms of the retained unconditional AMOs; sub-word compare-and-swap (`amocas.b`/`.h`) remains excluded with `Zacas`.
· Accept: the added encodings are width cases on the existing AMO semantics, adding no operation class.
· Trace: CJ-SAIL · [L1132–1133](verification-maximal-os.md#L1132)

**R-15-028** IS — `Zabha`'s justification is lowering-admissibility, not traffic volume: with `Zalrsc` and `Zacas` both deleted, sub-word atomic RMW has no admissible lowering (a wider aligned access would race on adjacent bytes; a lock-based `libatomic` call is forbidden).
· Accept: the justification does not depend on consumer count; the claimed consumers are exactly those §13 permits — atomic state that is constructor-injected or reachable only from a handed reference.
· Trace: CJ-SAIL, CJ-CERISE · [L1134–1136](verification-maximal-os.md#L1134)

**R-15-029** IS — `Zaamo` covers the atomic traffic that remains above a share-nothing kernel and an SPSC data plane, the dominant consumer being `Arc`'s strong and weak counts in contained Rust.
· Accept: narrowing the profile below `Zaamo` would delete `Arc` and the shared-ownership vocabulary §14's porting story rests on; that is recorded as the ground for retention.
· Trace: CJ-SAIL · [L1223–1224](verification-maximal-os.md#L1223)

**R-15-030** MUST — No retry loop of any kind contributes to any task's WCET bound: neither an LR/SC spurious-failure retry nor a CAS compare-fail retry exists.
· Accept: every atomic is one bounded memory transaction in the timing-annotated model.
· Trace: CJ-WCET · [L1130](verification-maximal-os.md#L1130)

### 15.6 Macro-op fusion

**R-15-031** IS — The decoder may fuse a frozen set of adjacent instruction pairs (address formation and load-effective-address, compare-and-branch, short dependent-ALU chains) into a single internal operation.
· Accept: the fused set is enumerated and frozen with the proof.
· Trace: CJ-SAIL · [L1142](verification-maximal-os.md#L1142)

**R-15-032** IS — Fusion is a combinational function of the static instruction encoding, holds no state surviving a partition switch, mints no authority, and runs no walker, so it passes all five admission tests.
· Accept: five recorded dispositions; nothing joins the `fence.t` flush set.
· Trace: CJ-SAIL · [L1143](verification-maximal-os.md#L1143)

**R-15-033** IS — Fusion is architecturally transparent: a fused and an unfused execution reach identical architectural state, so it rides the existing functional refinement and disturbs no binary certificate, constant-time proof, or WCET table.
· Accept: a fused pair is one more fixed-latency entry in the timing-annotated model.
· Trace: CJ-RTL-SAIL, CJ-WCET · [L1144](verification-maximal-os.md#L1144)

**R-15-034** MUST — The sole obligation on fusion is that the fused set is frozen with the proof and listed in the timing-annotated Sail model.
· Accept: no certificate, WCET bound, or constant-time statement is re-derived on its account.
· Trace: CJ-WCET · [L1145](verification-maximal-os.md#L1145)

### 15.7 ISA exclusions

**R-15-035** MUST NOT — The initialization-tag plane (Mon CHÉRI-derived Write-before-Read as a second metadata plane) is excluded; the property is carried by the §5 definite-initialization attribute.
· Accept: one tag plane exists in the SRAM word, not two (R-15-165); the deletion recovers one bit per granule, its DECTED coverage, a Sail invariant, an RTL ⊑ Sail obligation, and a DSE parameter.
· Trace: CJ-RTL-SAIL, CJ-TAL-SOUND · [L1149–1161](verification-maximal-os.md#L1149)

**R-15-036** MUST NOT — The C (compressed) extension is excluded; the accepted cost is ~25–30% code size.
· Accept: unique 4-byte-aligned decode, no overlapping 16-bit-aligned decodings, no decode ambiguity for binary-level proofs (R-05-035).
· Trace: CJ-SAIL, CJ-TAL-SOUND · [L1163–1165](verification-maximal-os.md#L1163)

**R-15-037** MUST NOT — `Zkr` (entropy-source CSR) is excluded: the platform has exactly one entropy root, the RoT TRNG through the verified DRBG.
· Accept: no second entropy root exists in hardware or software.
· Trace: CJ-SAIL · [L1169](verification-maximal-os.md#L1169)

**R-15-038** MUST NOT — Virtual memory is excluded entirely: `Sv39`/`Sv48`/`Sv57` and the `Svadu`/`Svade` A/D-update extensions, with the TLB, walk-cache state, `satp` translation, and A/D machinery.
· Accept: the sole autonomous hardware walker a RISC-V core would carry is deleted with the MMU rather than exempted from test 5.
· Trace: CJ-SAIL · [L1170–1172](verification-maximal-os.md#L1170)

**R-15-039** MUST NOT — Scalar floating point is excluded entirely: the `F`/`D` extensions, the `f0`–`f31` register file, and the dynamic rounding-mode CSR. All floating point is vector, computed as VL=1 RVV operations on the one FPU.
· Accept: the fixed-latency-including-subnormals contract and the `FDIV`/`FSQRT` carve-out are stated once, for the vector FPU; the `f`-register file is absent from the context-switch and `fence.t` sets.
· Trace: CJ-LEAK, CJ-SAIL · [L1178–1182](verification-maximal-os.md#L1178)

**R-15-040** IS — Vector-FP-without-scalar-FP is a deliberate, Sail-modeled fork of standard RVV, admissible because the platform curates its own profile and formal model.
· Accept: the fork is recorded, with its ABI cost (a soft-float-register calling convention) accepted.
· Trace: CJ-SAIL · [L1183](verification-maximal-os.md#L1183)

**R-15-041** MUST NOT — The scalar AES and SHA-2 round instructions (`Zkne`/`Zknd`/`Zknh`) are excluded: the vector crypto suite computes them table-free, so the constant-time contract is stated once.
· Accept: no vectorless core requires a hardware AES or SHA-2 round unit; the S-class RoT hashes SHA-3/SHAKE in plain 64-bit integer with `Zbb` rotations and delegates AEAD and sealing to the crypto core.
· Trace: CJ-LEAK · [L1185–1189](verification-maximal-os.md#L1185)

**R-15-042** IS — The scalar crypto bit-manipulation extensions `Zbkb`/`Zbkc`/`Zbkx` are a distinct extension and are retained for software crypto on vectorless cores.
· Accept: they appear in the adopted list; they are not an AES/SHA-2 round datapath.
· Trace: CJ-SAIL · [L1190](verification-maximal-os.md#L1190)

**R-15-043** MUST NOT — Pointer masking (`Ssnpm`/`Smnpm`) is excluded, obviated by CHERI.
· Accept: no top-byte-ignore mechanism exists.
· Trace: CJ-CERISE · [L1191](verification-maximal-os.md#L1191)

**R-15-044** MUST NOT — `Zicfiss`/`Zicfilp` (shadow stacks / landing pads) are excluded: CFI is a theorem for verified code and CHERI-enforced for the rest, concretely by the forward/backward-edge sentries.
· Accept: the exactness landing pads would buy is taken as the CHERI-TAL typed callee set (R-05-113) at zero silicon.
· Trace: CJ-TAL-SOUND · [L1192](verification-maximal-os.md#L1192), [L1258](verification-maximal-os.md#L1258)

**R-15-045** MUST NOT — ARM MTE-class memory tagging is excluded: its detection is probabilistic (~93% on 4-bit tags over 16-byte granules), blind to intra-granule overflow, and a statistic rather than a theorem.
· Accept: spatial safety is CHERI's deterministic byte-granular bounds; temporal safety is budgeted revocation plus Rust ownership.
· Trace: CJ-CERISE · [L1193–1196](verification-maximal-os.md#L1193)

**R-15-046** MUST NOT — `Zicbop`/`Zihintntl` (prefetch / non-temporal hints) and `Zawrs` (reservation-set stall) are excluded.
· Accept: no prefetch request has a software origin; `Zawrs` would stall on a reservation set that does not exist.
· Trace: CJ-WCET · [L1197–1198](verification-maximal-os.md#L1197)

**R-15-047** MUST NOT — `Zifencei`/`fence.i` is excluded for want of a runtime consumer: under W^X with no on-device code generation, the instruction stream is immutable once the image is wired.
· Accept: execute-only capabilities are derived over the read-only content-addressed image, never over written memory; the one instruction-memory write (measured-boot image load) is ordered by the boot sequence and a plain `fence`.
· Trace: CJ-SAIL, CJ-CERISE · [L1199–1202](verification-maximal-os.md#L1199)

**R-15-048** MUST NOT — The ShangMi suites (`Zks*`/`Zvks*`) and `Zimop`/`Zcmop` are excluded as dead Sail surface on a frozen ISA.
· Accept: no unused encoding vocabulary appears in the model.
· Trace: CJ-SAIL · [L1203](verification-maximal-os.md#L1203)

**R-15-049** MUST NOT — `Smstateen` is excluded: with no less-privileged mode its bits gate nothing reachable, and what it was meant to close is already closed by the frozen profile, the access-system-registers permission, and `mstatus.VS/XS` with eager save-and-zeroize.
· Accept: the CSR bank is absent.
· Trace: CJ-SAIL · [L1204–1206](verification-maximal-os.md#L1204)

**R-15-050** MUST NOT — `Ssqosid` / CBQRI-shaped memory-bandwidth partitioning is excluded: bandwidth is not a quantity this platform allocates at runtime.
· Accept: no `srmcfg` CSR, no RCID/MCID request tagging, no allocation or monitoring registers; each island's ceiling is read off the TDM NoC slot schedule and the bank/macro/tier binding by the §11 admission proof.
· Trace: CJ-ISOL, CJ-WCET · [L1207–1213](verification-maximal-os.md#L1207)

**R-15-051** IS — Removing the monitoring counters is part of the exclusion, because per-`MCID` bandwidth-usage counters are a cross-partition activity oracle.
· Accept: no per-partition bandwidth counter is readable by any compartment.
· Trace: CJ-NI · [L1212](verification-maximal-os.md#L1212)

**R-15-052** MUST — `misa` is read-only: no runtime ISA morphing.
· Accept: writes to `misa` have no effect.
· Trace: CJ-SAIL · [L1214](verification-maximal-os.md#L1214)

### 15.8 Adopted extensions

**R-15-053** IS — `Zkt` + `Zvkt` is the keystone: the architectural contract that a listed instruction set runs in data-independent latency.
· Accept: the list is (a) the single leakage model constant-time verification is stated against and (b) an RTL-against-Sail proof obligation.
· Trace: CJ-LEAK, CJ-RTL-SAIL · [L1218–1219](verification-maximal-os.md#L1218)

**R-15-054** IS — `Zicond` (czero.eqz/nez) is adopted as the branchless constant-time select, doubly load-bearing given static-only prediction.
· Accept: it is the mandated vehicle for branchless-on-secrets hardening (R-05-067).
· Trace: CJ-LEAK · [L1220–1221](verification-maximal-os.md#L1220)

**R-15-055** IS — Vector crypto `Zvkned`/`Zvknhb`/`Zvkg`/`Zvbb`/`Zvbc` and scalar crypto bit-manipulation `Zbkb`/`Zbkc`/`Zbkx` are adopted: table-free AES/SHA-2/GHASH on the vector unit.
· Accept: table-free primitives have no cache-timing substrate; `Zvbb`/`Zvbc` carry baseline Keccak while the NTT rides plain RVV.
· Trace: CJ-LEAK · [L1227–1229](verification-maximal-os.md#L1227)

**R-15-056** IS — A frozen Keccak-f[1600] permutation is adopted as a single vector instruction, moving the constant-time obligation for the dominant post-quantum hash onto a fixed-latency hardware permutation.
· Accept: it clears all five admission tests; its correctness is a Sail invariant (fixed theta/rho/pi/chi/iota rounds, no tables, no secret-dependent control flow) riding RTL ⊑ Sail.
· Trace: CJ-SAIL, CJ-LEAK · [L1230–1231](verification-maximal-os.md#L1230)

**R-15-057** MUST — The Keccak unit is fork-and-frozen with full Sail semantics until the RISC-V PQC Task Group's instruction (RVG-84) ratifies, then re-pinned to it.
· Accept: a re-pin obligation is recorded, as for the matrix extension and CHERI's 'Y' line.
· Trace: CJ-SAIL · [L1232](verification-maximal-os.md#L1232)

**R-15-058** MUST — With no Coq-native Keccak proof to import, the fixed-permutation invariant is a fresh Sail proof disciplined against FIPS 202 and the NIST ACVP test vectors as differential oracle, with `Zvbb`/`Zvbc` software Keccak retained as the portable path and the differential reference.
· Accept: the oracle enters no trust base; the software path exists on every core lacking the unit.
· Trace: CJ-SAIL · [L1233](verification-maximal-os.md#L1233)

**R-15-059** IS — The Keccak unit is placed on the vector-bearing cores and not on the vectorless S-class RoT; a hardware Keccak block on the RoT is declined on the global trade.
· Accept: the RoT's scalar software Keccak is already constant-time on the fixed-latency core; a block would add to the least-built RTL ⊑ Sail arrow at the boot-critical root.
· Trace: CJ-RTL-SAIL · [L1234–1235](verification-maximal-os.md#L1234)

**R-15-060** IS — `Zicboz` (cbo.zero) is adopted, making the §7 eager-zeroize discipline nearly free per aligned block and carrying the disclosure half of Write-before-Read without any per-load check.
· Accept: an unwritten slot reads a deterministic zero rather than residue.
· Trace: CJ-MEMPLAN · [L1236](verification-maximal-os.md#L1236)

**R-15-061** MUST NOT — `Zicbom` (cache-block clean/flush/invalidate) is not adopted: with no hardware caches it has no consumer, in the kernel or in any future userspace program.
· Accept: cross-island ring ordering is a plain `fence` over shared SRAM.
· Trace: CJ-SAIL · [L1237](verification-maximal-os.md#L1237)

**R-15-062** IS — `fence.t` is adopted as a fork-and-frozen platform-custom instruction with full Sail semantics, specified rather than invoked: enumerated flush set, mechanized completeness classification, and padded constant cost.
· Accept: see R-15-186 through R-15-194.
· Trace: CJ-ISOL · [L1238–1239](verification-maximal-os.md#L1238)

**R-15-063** IS — The M-mode timer (`mtimecmp`) is adopted and `Sstc` excluded: with one privilege mode the kernel programs the machine-timer compare directly.
· Accept: no S-mode timer exists.
· Trace: CJ-SAIL · [L1240](verification-maximal-os.md#L1240)

**R-15-064** IS — AIA/IMSIC is adopted capability-read with static routing: an MSI is a store to an interrupt file, so interrupt-send authority is a write capability in the static capability topology rather than a side table.
· Accept: no PLIC exists; interrupt authority appears in the §7/§8 topology.
· Trace: CJ-CERISE · [L1241–1242](verification-maximal-os.md#L1241)

**R-15-065** MUST NOT — Only the machine-level interrupt files exist, and of those only the pending array: the supervisor and guest/VS machinery, and the delivery-enable, threshold, and top-pending-selection machinery, are dead Sail surface and are excluded.
· Accept: software reads pending bits with ordinary loads; arrival is latched pending state read in the owner's slot, never a trap and never a cross-partition preemption.
· Trace: CJ-SAIL, CJ-KERNEL · [L1242–1244](verification-maximal-os.md#L1242)

**R-15-066** IS — The platform is MSI-only and the curated device set makes that complete: every admitted device signals by an IMSIC store through the capability-checked fabric; the timer is core-local `mtimecmp`; the only non-MSI signals are the RoT's reset and watchdog-bite lines, which are resets outside the interrupt model.
· Accept: no wired level interrupt exists on the die.
· Trace: CJ-SAIL · [L1244](verification-maximal-os.md#L1244)

**R-15-067** IS — `Zba`/`Zbb`/`Zbs` (fixed-latency bit-manipulation) and `Zvfbfwma` (M-class bf16) are adopted.
· Accept: they appear in the frozen profile with fixed-latency dispositions.
· Trace: CJ-SAIL · [L1245](verification-maximal-os.md#L1245)

### 15.9 CHERI capability-ISA features

**R-15-068** IS — Capability jump-and-link carries the sentry unseal-and-seal semantics, so there is no separate call gate: it unseals a forward-edge sentry into the executing PCC and writes the return address already sealed as a backward-edge sentry.
· Accept: a single instruction is the hardware root of domain entry and of forward/backward-edge CFI, needing no trampoline or software dispatch.
· Trace: CJ-CERISE · [L1247–1249](verification-maximal-os.md#L1247)

**R-15-069** IS — The cross-compartment switcher is a specialization layered on that instruction, not a separate mechanism.
· Accept: its entry point is itself a sentry entered by the same instruction.
· Trace: CJ-KERNEL · [L1250](verification-maximal-os.md#L1250)

**R-15-070** MUST NOT — Interrupt-state sentries (`enabled`/`disabled`/`inherit`) are excluded, the one CHERIoT capability feature the profile declines: with asynchronous interrupt delivery deleted, the three sentry types collapse to the one plain sealed entry.
· Accept: Sail loses the variant otype space and the interrupt-state capture-and-restore semantics; RTL loses the interrupt-state field, decode, and auto-restore path; the CHERI-TAL loses the interrupt-state index on sentry types; §8/§11 lose the bounded interrupt-disabled-window allow-list.
· Trace: CJ-SAIL, CJ-TAL-SOUND · [L1251–1254](verification-maximal-os.md#L1251)

**R-15-071** IS — The forward/backward-edge sentry split is the platform's coarse-grained CFI: a return capability may target only a return site, so a forged or replayed return address traps.
· Accept: the split survives the interrupt-state deletion, being a property of edge direction.
· Trace: CJ-CERISE · [L1255–1257](verification-maximal-os.md#L1255)

**R-15-072** IS — A sentry deliberately does not decide target *membership*; that residual is closed in software by the typed callee set, not in the ISA.
· Accept: no landing-pad surface is modeled in Sail or refined in RTL.
· Trace: CJ-TAL-SOUND · [L1258](verification-maximal-os.md#L1258)

**R-15-073** IS — Capability trap registers `MTCC`/`MEPCC`/`MTDC` are adopted, reachable only with the access-system-registers permission.
· Accept: the single-Machine-mode trap path is expressible; a trap-data capability bootstraps the handler's authority on entry.
· Trace: CJ-KERNEL · [L1259–1260](verification-maximal-os.md#L1259)

**R-15-074** MUST — Local/global capabilities and the `store-local` permission (with `load-global`/`load-mutable` transitivity) are adopted: a local capability may be stored only through a capability bearing `store-local`, which by construction only the stack carries.
· Accept: a buffer handed to an untrusted codec cannot be retained past the call; the convention that authority cannot cross into long-lived shared memory is an ISA-enforced invariant.
· Trace: CJ-CERISE · [L1261–1263](verification-maximal-os.md#L1261)

### 15.10 No PMP

**R-15-075** MUST NOT — Physical memory protection is not implemented, and `Smepmp` is dropped with it: CHERI is the sole memory-protection mechanism.
· Accept: no PMP region registers exist; the three roles a locked-PMP backstop would serve (immutable text/W^X, per-core physical-partition bound, crown-jewel secret fencing) each map onto a named CHERI or crypto-core mechanism.
· Trace: CJ-CERISE · [L1265–1269](verification-maximal-os.md#L1265)

**R-15-076** IS — The CHERI-disjoint failure domain PMP uniquely offered is deliberately forgone; the hedge is CHERI's own formal verification, and the concentration is booked honestly in §17.
· Accept: the residual is the RTL ⊑ Sail arrow plus a Coq-native restatement of reachable-capability monotonicity over the CHERI-RISC-V Sail model.
· Trace: CJ-CERISE, CJ-RTL-SAIL · [L1270–1271](verification-maximal-os.md#L1270)

### 15.11 Gated features and debug

**R-15-077** MUST — Performance counters (`Zicntr`/`Zihpm`) are unreadable unless the accessing compartment's PCC carries the counter-read permission; hpm events are sentinel-only.
· Accept: clock read-out is gated authority; with one privilege mode there is no `mcounteren`/`scounteren` ring to gate through.
· Trace: CJ-NI · [L1274](verification-maximal-os.md#L1274)

**R-15-078** MUST — The RISC-V Debug Module exists in silicon but is lifecycle-fused at the hardware level, never merely software-gated: in the production lifecycle state the RoT's OTP fuse holds its clock and reset gated off and its fabric port electrically quiesced.
· Accept: *no DM transaction reaches the fabric in the production state* is a stated RTL ⊑ Sail obligation, so the Sail model carries the gate rather than a model of the debugger.
· Trace: CJ-RTL-SAIL · [L1275–1278](verification-maximal-os.md#L1275)

**R-15-079** MUST — In development and RMA lifecycle states, DM entry is an RoT challenge-response (ML-DSA-signed, serial-bound), the RoT key hierarchy diversifies by lifecycle state, and moving a fielded device to a debuggable state crypto-erases first; trace rides the same fuse.
· Accept: a debuggable part cannot unseal production-sealed material.
· Trace: CJ-DEVTREE · [L1277](verification-maximal-os.md#L1277)

### 15.12 Implementation timing contracts

**R-15-080** MUST — Integer DIV/REM completes at fixed worst-case latency always; early-out-on-small-operands dividers are forbidden.
· Accept: the timing-annotated model carries one latency; no operand-dependent divide path exists.
· Trace: CJ-LEAK, CJ-WCET · [L1281](verification-maximal-os.md#L1281)

**R-15-081** MUST — The vector FPU is fixed-latency across all operand classes including subnormals.
· Accept: no subnormal slow path exists; the contract is stated once, for the one FP datapath.
· Trace: CJ-LEAK · [L1282](verification-maximal-os.md#L1282)

**R-15-082** MUST — `vfdiv`/`vfsqrt` are either fixed-latency or off the constant-time list, the latter admissible only because the flow discipline proves no secret-labeled operand reaches them.
· Accept: the discharge is a proof obligation, not a self-declaration (R-15-011).
· Trace: CJ-LEAK, CJ-NI · [L1282](verification-maximal-os.md#L1282)

**R-15-083** MUST — Floating-point rounding is static: the mode is encoded per-instruction (default round-to-nearest-even), never the dynamic `frm` CSR.
· Accept: no mutable rounding-mode state context-switches or joins the `fence.t` set.
· Trace: CJ-SAIL, CJ-ISOL · [L1283](verification-maximal-os.md#L1283)

**R-15-084** MUST — Misaligned accesses trap and are never split in hardware.
· Accept: no line-crossing address-dependent latency exists; the granule-alignment rule is enforced rather than hoped.
· Trace: CJ-WCET · [L1284](verification-maximal-os.md#L1284)

**R-15-085** MUST — `Zvkt`-listed vector operations execute in mask-independent time: an implementation may not skip memory accesses or cycles for masked-off elements.
· Accept: the mask is not observable through timing or memory traffic.
· Trace: CJ-LEAK · [L1285](verification-maximal-os.md#L1285)

**R-15-086** MUST — Branch-resolution latency is a fixed function of the static rule, so fetch timing depends on architectural state only.
· Accept: no dynamic predictor state contributes to fetch timing.
· Trace: CJ-WCET · [L1286](verification-maximal-os.md#L1286)

**R-15-087** MUST — `Zaamo` and `Zabha` AMOs complete as single bounded memory transactions with data-independent latency at the SRAM bank's serialization point, which is the whole of what a coherence point would otherwise name.
· Accept: no early-out on operand values; no reservation state or 128-bit CAS coherence-point stall contributes to timing.
· Trace: CJ-WCET, CJ-LEAK · [L1288](verification-maximal-os.md#L1288)

**R-15-088** MUST — The store buffer's drain at a partition switch is data-independent because it is paid as the `fence.t` padded constant, not as a second budget term beside it.
· Accept: the partition-switch budget counts the drain once (R-15-193).
· Trace: CJ-WCET, CJ-ISOL · [L1287](verification-maximal-os.md#L1287)

### 15.13 RTL-against-Sail refinement

**R-15-089** IS — Every obligation stated against the microarchitecture is discharged against a named vehicle, and the obligations split by whether the Sail model can express them at all.
· Accept: refinement obligations (`Zkt`/`Zvkt`, Ztso ordering, static-only fetch timing, fixed-latency DIV/FPU/AMO) ride RTL ⊑ Sail; absence obligations ride the separate contract and are not a rung on the ladder.
· Trace: CJ-RTL-SAIL · [L1291–1293](verification-maximal-os.md#L1291)

**R-15-090** IS — Sail-generated SystemVerilog plus commercial formal-equivalence verification is the day-one bring-up gate for imported cores: unbounded observational-correctness evidence at near-zero method cost, with the FEV tool trusted so it remains evidence, not the Coq close.
· Accept: every imported or modified core (CHERI-CVA6 front end, Ara, Gemmini) has an evidence path from first bring-up.
· Trace: CJ-RTL-SAIL · [L1295–1297](verification-maximal-os.md#L1295)

**R-15-091** MUST — Kami/Kôika Coq refinement is the primary closing vehicle, landing in the same single prover and adding no checker to the trust base.
· Accept: the refinement theorem is a Coq development.
· Trace: CJ-RTL-SAIL · [L1298–1299](verification-maximal-os.md#L1298)

**R-15-092** MUST — The net-new blocks with no legacy RTL to preserve (the capability- and tag-carrying DMA fabric, the TDM NoC, the fixed-function sequencers) are authored directly in Kôika/Kami, from which SystemVerilog is generated for synthesis.
· Accept: their RTL ⊑ Sail is discharged against the source the hardware is built from; the generated SystemVerilog is not a semantic anchor.
· Trace: CJ-RTL-SAIL · [L1300](verification-maximal-os.md#L1300)

**R-15-093** IS — Proof over the shipped SystemVerilog is a deferred, budget-gated rung: it would introduce a Verilog-semantics anchor, admitted only if it retires the Sail-reference-plus-FEV evidence step it replaces.
· Accept: the anchor-budget conditions (R-05-020) govern its admission.
· Trace: CJ-RTL-SAIL · [L1302–1304](verification-maximal-os.md#L1302)

**R-15-094** IS — riscv-formal/rvfi is bounded-depth evidence and the cheapest bring-up gate; Isla is the bridge turning the frozen Sail model into concrete obligations and litmus tests, including the Ztso concurrency litmus.
· Accept: neither is the ground of any refinement claim.
· Trace: CJ-RTL-SAIL · [L1305–1307](verification-maximal-os.md#L1305)

**R-15-095** MUST — The timing and ordering obligations are hyperproperties stated and checked against a timing-annotated Sail model, not the bare functional one.
· Accept: `Zkt`/`Zvkt` is 2-safety, Ztso is an ordering property, static-prediction fetch timing is architectural-state-only; each is stated against the annotated model.
· Trace: CJ-RTL-SAIL, CJ-LEAK · [L1309–1311](verification-maximal-os.md#L1309)

**R-15-096** IS — That same timing-annotated model is the low-level input to WCET derivation, so sound per-instruction timing is a corollary of RTL ⊑ Sail rather than a separate analysis.
· Accept: the residual fetch and memory terms are a reproducible function of the signed deterministic-layout image, the flat SRAM, the TDM NoC schedule, and the WCET-exact scratchpads.
· Trace: CJ-WCET, CJ-RTL-SAIL · [L1312](verification-maximal-os.md#L1312)

**R-15-097** IS — Honest scope: no RTL ⊑ Sail artifact exists today for a full application-class core, let alone the heterogeneous topology; this is the least-built layer of the entire stack.
· Accept: §18 stages it per class; §17 books the residuals; below this arrow, fabricated silicon versus verified RTL remains the fab residual.
· Trace: CJ-RTL-SAIL · [L1313–1314](verification-maximal-os.md#L1313)

### 15.14 The microarchitectural absence contract

**R-15-098** IS — Sail models architectural state, so RTL ⊑ Sail cannot state, let alone discharge, *there is no branch predictor*; the two registers are therefore separated.
· Accept: ISA-visible removals are absences in the frozen Sail model and owe nothing further; microarchitectural removals owe the absence contract.
· Trace: CJ-SAIL, CJ-RTL-SAIL · [L1316–1321](verification-maximal-os.md#L1316)

**R-15-099** IS — The ISA-visible removals are the MMU and its Sv39 walker, PMP, the S/U rings, `C`, `Zifencei`, `Zalrsc`/`Zacas`, scalar F/D, the dynamic `frm` state, and asynchronous interrupt delivery.
· Accept: an RTL implementing any of them fails ordinary refinement.
· Trace: CJ-SAIL · [L1320](verification-maximal-os.md#L1320)

**R-15-100** IS — The microarchitectural removals owed the absence contract are speculation, out-of-order issue, every dynamic direction/target/return predictor, prefetchers, SMT, the I- and D-caches and the tag cache, and DVFS/frequency control.
· Accept: each appears in the absence-contract register with a discharge.
· Trace: CJ-RTL-SAIL · [L1321](verification-maximal-os.md#L1321)

**R-15-101** IS — The semantic content of the removals is one hyperproperty: cycle-level timing and memory traffic are a function of the instruction stream and architectural state alone, never of prior execution history.
· Accept: the contract discharges a sufficient structural condition for it — that the enumerated structures and their state elements do not exist — rather than proving it over a cycle-accurate model.
· Trace: CJ-ISOL · [L1324–1326](verification-maximal-os.md#L1324)

**R-15-102** MUST — For Kôika/Kami-authored blocks, absence is a structural predicate over the Coq term, checked in the same prover as the refinement and adding no semantic anchor.
· Accept: the predicate is over an existing artifact, not a new semantics.
· Trace: CJ-RTL-SAIL · [L1328](verification-maximal-os.md#L1328)

**R-15-103** MUST — For imported SystemVerilog cores, absence is a state-enumeration and structural check over the elaborated netlist plus synthesis-configuration provenance, and is stated honestly as a structural audit, not a theorem.
· Accept: the check covers predictor arrays, reorder buffer and reservation stations, prefetch engine, cache data/tag/valid arrays, a second hardware thread context, and PLL/DVFS control paths.
· Trace: CJ-RTL-SAIL · [L1329](verification-maximal-os.md#L1329)

**R-15-104** MUST — The prefetcher/fetch-buffer boundary is decided by table-freeness, not by size or run-ahead depth: a state element in the fetch path whose write data depends on a prior *execution* is a prefetcher and fails the contract; one whose contents are a function of the fetched stream is fetch pipelining and passes.
· Accept: the audit is a table search, not a judgment call.
· Trace: CJ-ISOL · [L1331–1334](verification-maximal-os.md#L1331)

**R-15-105** IS — Every microarchitectural removal converts a correctness obligation into an absence obligation, moving work out of the least-built arrow; this is the argument *for* the removals, not merely their consequence.
· Accept: deletion is preferred to partitioning even where partitioning would suffice.
· Trace: CJ-RTL-SAIL · [L1337–1339](verification-maximal-os.md#L1337)

**R-15-106** MUST — The `fence.t` completeness classification is discharged by the absence contract rather than by the refinement, since completeness is the claim that no unenumerated state exists, which the model cannot see.
· Accept: the temporal fence's residual scope collapses to pipeline drain. **See [D-07](#d-07).**
· Trace: CJ-ISOL · [L1340](verification-maximal-os.md#L1340)

**R-15-107** IS — The absence contract is a distinct §18 bring-up gate and a named §17 residual: the one obligation class whose imported-core half closes on audit rather than on proof.
· Accept: both entries exist.
· Trace: CJ-RTL-SAIL · [L1341](verification-maximal-os.md#L1341)

### 15.15 Parameter selection

**R-15-108** MUST — The frozen microarchitectural parameters are selected by a composition-time, pre-silicon design-space exploration whose utility function carries proof simplicity as a first-class term alongside performance, area, power, and WCET.
· Accept: the parameter set is VLEN per class, issue width and pipeline depth, SRAM bank/macro/tier-to-island assignment, scratchpad sizes, and the TDM-NoC schedule; there is no cache, way-colouring, or integrity-tree parameter to choose.
· Trace: CJ-RTL-SAIL · [L1343–1345](verification-maximal-os.md#L1343)

**R-15-109** MUST — The five-part admission test and the §8 non-interference / §11 WCET obligations are hard constraints on the search, not objectives.
· Accept: every candidate satisfies them to be admissible; the search optimizes strictly within the proven-safe envelope and widens no trust base.
· Trace: CJ-NI, CJ-WCET · [L1347](verification-maximal-os.md#L1347)

**R-15-110** IS — The exploration tool is untrusted evidence-producing machinery; the proof-simplicity term is a proxy, so a poor proxy costs search quality, never soundness.
· Accept: its output is a single frozen, Sail-modeled, admission-checked configuration whose choice the per-class RTL ⊑ Sail proof then discharges.
· Trace: CJ-RTL-SAIL · [L1348–1349](verification-maximal-os.md#L1348)

### 15.16 Heterogeneous single-die topology

**R-15-111** MUST — All compute is on one die, under one base ISA, one kernel binary, and one parameterized formal model.
· Accept: no die-to-die link exists anywhere in the machine (R-15-146).
· Trace: CJ-SAIL · [L1353](verification-maximal-os.md#L1353)

**R-15-112** IS — Scalar front ends are one shared microarchitecture (CVA6-class, modified to static-only prediction) across all classes, so kernel-path WCET is a single analysis.
· Accept: one front-end model in the timing-annotated Sail.
· Trace: CJ-WCET · [L1354](verification-maximal-os.md#L1354)

**R-15-113** IS — The core classes are C-class (control and application, VLEN=256), V-class (long-vector, VLEN=4096, 8 lanes, with a radio-pinned pair), M-class (systolic GEMM plus VLEN=1024 and a software-managed scratchpad), S-class (scalar sentinel), and the RoT (OpenTitan-class scalar RV64+CHERI in its own clock/power island). Counts are composition parameters, not architecture.
· Accept: every other section names a class and refers here; disjointness is machine-checked as in §7.
· Trace: CJ-SAIL, CJ-KERNEL · [L1357–1363](verification-maximal-os.md#L1357)

**R-15-114** IS — Pinning is an admission outcome, not a favour granted per device: a device server whose deadline-driven poll cadence would spend an inadmissible fraction of a core on partition switching is pinned instead of slotted, at which point its switch cost is deleted rather than budgeted.
· Accept: the radio-pinned V-class pair and the S-class sentinel are the current members of that class; any further server failing the §11 switch-duty inequality takes a core of its class by the same rule.
· Trace: CJ-WCET · [L1365–1367](verification-maximal-os.md#L1365)

**R-15-115** MUST NOT — V-class is vector, not fixed-function graphics and not SIMT: no rasterizer, no texture units, no ROPs, no command processor, and no hardware warp scheduler.
· Accept: CHERI stays a single-front-end problem; vector data carries no tags and checks land on scalar-issued vector memory ops, per-element for gather/scatter.
· Trace: CJ-CERISE, CJ-WCET · [L1368–1370](verification-maximal-os.md#L1368)

**R-15-116** MUST — The bespoke matrix extension is admitted only where it clears an order-of-magnitude sustained dense-GEMM margin (about 8–10× throughput, wider per-watt) over the same GEMM expressed as RVV on the M-class's own VLEN=1024 unit.
· Accept: dense int8/bf16 inference clears the bar and the extension is kept; small, irregular, or low-reuse GEMM does not and folds onto the vector unit.
· Trace: CJ-SAIL · [L1371–1374](verification-maximal-os.md#L1371)

**R-15-117** MUST — De-quantization and block-scale (microscaling) application are software on the M-class vector unit, not hardware: no ACE-style block-scale register and no Arm-FPMR-style scale field enters the frozen matrix ISA.
· Accept: the array consumes int8/bf16 only; the forgone native FP8 systolic density is accepted.
· Trace: CJ-SAIL · [L1375–1379](verification-maximal-os.md#L1375)

**R-15-118** MUST — The coprocessor line: every byte the matrix unit moves is core-issued with explicit capability operands — no independent DMA mastership, no translation context, no firmware. An accelerator needing any of those is a device.
· Accept: the matrix unit holds no DMA capability of its own.
· Trace: CJ-CERISE · [L1381–1382](verification-maximal-os.md#L1381)

**R-15-119** IS — FEC units are LDPC and polar decoders only (the 5G NR and 6G channel-code families) as fixed-geometry arithmetic with deterministic iteration bounds, core-issued capability-operand movement, and no firmware.
· Accept: the legacy turbo and convolutional decoders are absent from the die; belief propagation on a fixed graph is grammar-free arithmetic and does not breach the codec-block ban.
· Trace: CJ-SAIL · [L1383–1386](verification-maximal-os.md#L1383)

**R-15-120** IS — The RoT is integrated on-die; the cost is concentration (one mask set carries the RoT and everything it measures).
· Accept: the residual is booked in §17.
· Trace: CJ-DEVTREE · [L1387–1388](verification-maximal-os.md#L1387)

### 15.17 Radio subsystem

**R-15-121** IS — The on-die transceiver is a register-slave datapath: direct-RF or zero-IF ADC/DAC chains with a digital front end, configured via capability-gated MMIO, streaming I/Q through capability-bounded DMA windows, with no instruction fetch and no sequencer firmware.
· Accept: no writable program exists in the transceiver.
· Trace: CJ-CERISE · [L1392–1393](verification-maximal-os.md#L1392)

**R-15-122** IS — One fixed-function link-layer timing sequencer is admitted for the sub-slot turnaround (BLE `T_IFS`, 802.11 SIFS, 802.15.4 turnaround): a hardware packet-end event starts a fixed timer that drives the RX/TX switch and gates a software-prepared buffer at the deadline.
· Accept: the buffer, channel/frequency word, and event schedule are loaded by the §12 control plane before the event, so the block makes no protocol decision; it carries no instruction fetch, no writable program, and no firmware.
· Trace: CJ-SAIL · [L1394–1398](verification-maximal-os.md#L1394)

**R-15-123** IS — This is the split-MAC/SoftMAC partition: the turnaround in fixed hardware, the link layer and everything above it in software; the distinction from a Bluetooth/Wi-Fi controller is the no-foreign-computers line.
· Accept: the turnaround is one more fixed-latency entry in the timing-annotated model, riding RTL ⊑ Sail like the rest of the transceiver.
· Trace: CJ-RTL-SAIL · [L1399–1400](verification-maximal-os.md#L1399)

**R-15-124** IS — Off-die analog (PA, LNA, filters, switches, antenna tuners) is the primary regulatory layer: a switched bank of pre-certified fixed paths whose passbands and power ceilings are physical properties no software can exceed.
· Accept: no software path exceeds the passive envelope.
· Trace: CJ-DEVTREE · [L1401](verification-maximal-os.md#L1401)

**R-15-125** MUST — Emission envelope registers are the secondary layer: TX power and spectrum-mask limits latched at boot from RoT-verified signed calibration, immutable until reset.
· Accept: no runtime write path to the limit registers exists.
· Trace: CJ-DEVTREE · [L1402](verification-maximal-os.md#L1402)

**R-15-126** MUST — Per-unit calibration originates in a factory trim step, is emitted as a typed schema-bounded manifest bound to the device serial, signed by the provisioning key, and anchored at personalization by the RoT under its monotonic-counter-protected state.
· Accept: post-factory substitution or downgrade of calibration fails attestation like any other measured input.
· Trace: CJ-DEVTREE · [L1403–1404](verification-maximal-os.md#L1403)

**R-15-127** IS — The calibration manifest is the one per-device artifact reproducibility cannot reach: it is measured, not built, so the factory step joins the supply chain as a trusted measurement, bounded by construction so compromise degrades performance and availability, never integrity and never the regulatory ceiling.
· Accept: emission stays inside the passive analog envelope whatever the trim says; limit values latch only at or below certified ceilings; SRAM assist mis-trim degrades margin that ECC and fail-stop catch; sensor mis-trim costs fidelity.
· Trace: CJ-DEVTREE · [L1405](verification-maximal-os.md#L1405)

**R-15-128** MUST NOT — Runtime closed-loop self-calibration is banned: trim targets are set at end-of-life, full-temperature worst case, and the forgone margin is paid in the design's standing currency.
· Accept: what remains admissible is in-band signal tracking in software (AFC, channel estimation, equalization, gain words as ordinary capability-gated register updates); re-trim is a rare, explicitly-entered, RoT-attested maintenance mode, never a loop.
· Trace: CJ-DEVTREE · [L1406–1407](verification-maximal-os.md#L1406)

**R-15-129** MUST — Generation floor: 5G and 6G only. The RF path bank carries only 5G/6G bands and the FEC units decode only LDPC and polar, so 2G, 3G, and 4G cannot be received at all.
· Accept: the legacy turbo and convolutional decoders are not on the die; the downgrade-attack class is deleted outright.
· Trace: CJ-SAIL · [L1408–1411](verification-maximal-os.md#L1408)

**R-15-130** IS — The target is 5G standalone (its own 5G-AKA mutual authentication, no LTE anchor) and forthcoming 6G; 5G non-standalone is excluded.
· Accept: no LTE anchor path exists.
· Trace: CJ-SAIL · [L1412](verification-maximal-os.md#L1412)

**R-15-131** IS — Emergency calling rides the generation floor rather than breaching it: E911/E112 is placed over 5G-standalone (and 6G) emergency registration, and a legacy emergency-only receiver is declined because that hardware would reopen the downgrade surface.
· Accept: where only legacy or 5G-non-standalone coverage offers an emergency path, the call cannot be placed — the coverage-for-security trade booked in §17.
· Trace: CJ-SAIL · [L1413](verification-maximal-os.md#L1413)

**R-15-132** MUST NOT — No persistent link-layer identifier exists in hardware: the die carries no factory-burned MAC or OUI.
· Accept: every link-layer address (Wi-Fi, Bluetooth, wired) is a fresh draw from the RoT TRNG through the verified DRBG, with locally-administered and unicast bits forced, never derived from a stored secret or a software PRNG.
· Trace: CJ-DEVTREE · [L1414–1416](verification-maximal-os.md#L1414)

**R-15-133** IS — The §12 network compartment chooses only *when* to rotate; MAC randomization is privacy by construction, tied to the entropy root rather than to a disable-able setting.
· Accept: the drawn address is recorded in the §16 replay nondeterminism record, in the public class.
· Trace: CJ-NI · [L1417–1418](verification-maximal-os.md#L1417)

**R-15-134** IS — Capacity honesty: two radio-pinned V-cores plus FEC units give LTE-class throughput via reduced-bandwidth NR; the scaling axis is core count, never a firmware processor.
· Accept: no firmware processor exists in the radio path.
· Trace: CJ-SAIL · [L1420](verification-maximal-os.md#L1420)

### 15.18 Wired link

**R-15-135** IS — The wired NIC is split-MAC applied to copper: the line interface is an analog front end, the MAC and above is a §12 host compartment, and the DSP is ordinary long-vector code on the same V-class datapath and FEC units the radio PHY uses.
· Accept: no Ethernet controller firmware exists; the IEEE-1588 timestamp unit and adjustable clock sit in the block as fixed-function matter.
· Trace: CJ-CERISE · [L1424–1427](verification-maximal-os.md#L1424)

**R-15-136** IS — 100BASE-TX dissolves completely: the PCS is host software on an ordinary core at a poll cadence the §11 ring-depth amortization covers, with no fixed-function block beyond the front end.
· Accept: no PCS hardware exists for 100BASE-TX.
· Trace: CJ-WCET · [L1428–1429](verification-maximal-os.md#L1428)

**R-15-137** MUST — 1000BASE-T is met by a fixed-function PCS-and-canceller datapath whose coefficients are trained at link-up and then frozen for the link epoch (RoT-loadable, cleared on link-down), with the MAC, autonegotiation policy, and all protocol state staying host software.
· Accept: adaptation is confined to a bounded training phase with no traffic in flight, so admission test 3 is met per epoch rather than waived. **See [D-08](#d-08).**
· Trace: CJ-ISOL · [L1430–1434](verification-maximal-os.md#L1430)

**R-15-138** IS — The stated cost of frozen coefficients is that marginal cable plant re-trains on a link bounce instead of adapting through it: a link-availability cost, not an integrity one.
· Accept: the residual is booked in §16/§17.
· Trace: CJ-ISOL · [L1435](verification-maximal-os.md#L1435)

**R-15-139** MUST NOT — 10GBASE-T and above are declined and booked in §17 rather than left an unimplemented gap.
· Accept: no LDPC-plus-Tomlinson-Harashima datapath exists for a wired port.
· Trace: CJ-SAIL · [L1436](verification-maximal-os.md#L1436)

### 15.19 Sensor and transducer front-ends

**R-15-140** MUST — Every sensor is a register-slave AFE: no per-sensor DSP core and no sensor firmware. Capacitive-touch, audio, image, IMU/motion, and fingerprint/biometric front-ends are fixed analog-front-end plus scan-, sample-, or event-sequencer blocks with capability-gated MMIO configuration and capability-bounded DMA windows.
· Accept: every programmable signal-processing stage is dissolved onto V-class cores in the device's §12 compartment; the AFE's fixed-function conditioning adds no writable state.
· Trace: CJ-CERISE · [L1440–1441](verification-maximal-os.md#L1440)

**R-15-141** IS — Readout is fixed-cadence by default but may be event-driven (a fixed-function threshold comparator, or temporal-contrast pixels), with the data-dependent event timing confined to the owning island's static NoC/memory partition so no cross-island channel opens.
· Accept: the test-2 disposition is containment within the island partition. **See [D-08](#d-08).**
· Trace: CJ-ISOL, CJ-NI · [L1442–1443](verification-maximal-os.md#L1442)

**R-15-142** IS — Raw-AFE silicon and its host-side DSP are a net-new co-design, booked as the honest cost of the firmware the profile deletes.
· Accept: the §17 entry exists.
· Trace: CJ-RTL-SAIL · [L1444](verification-maximal-os.md#L1444)

**R-15-143** MUST — A front-end's capability-bounded DMA window and its configuration MMIO are one indivisible ownership, granted and revoked together.
· Accept: no holder of configuration alone exists; a configuration-only holder could blind, coarsen, or remap the scan, which is control over what frames mean.
· Trace: CJ-CERISE · [L1445–1446](verification-maximal-os.md#L1445)

**R-15-144** MUST — For front-ends carrying a consent or credential act (touchscreen, buttons, fingerprint sensor), ownership sits in a register latched by the RoT, unwritable by software while the latch holds and driven by the same RoT signal that lights the secure-attention indicator.
· Accept: the trusted-path agent takes the front-end for a prompt's duration without the owning driver's cooperation; the driver's only recourse is to deny service.
· Trace: CJ-DEVTREE · [L1447–1448](verification-maximal-os.md#L1447)

### 15.20 Physical peripheral cutoffs

**R-15-145** MUST — For the microphone, the radios, and the wired data port the platform provides physical cutoffs the user actuates directly: a sealed switch independent of all software and firmware that no compromised OS, firmware, or RoT can override.
· Accept: admitted under the defense-in-depth clause because a physical cutoff adds no modeled mechanism, no Sail surface, and no proof obligation, while covering a domain the gates' own verification does not reach.
· Trace: CJ-T · [L1452–1455](verification-maximal-os.md#L1452)

**R-15-146** MUST — A peripheral is electronically enabled only while a live, consented capability grant holds it, so the platform cuts by default whatever nothing is using.
· Accept: the enable is driven by grant liveness rather than software claim, and therefore carries an in-use indication no compromised component can suppress.
· Trace: CJ-CERISE · [L1458–1459](verification-maximal-os.md#L1458)

**R-15-147** MUST — The attested lock state always cuts the microphone, the camera, and the USB data lanes, while the radio stays page-reachable in standby because the paging task still holds its capability.
· Accept: entering emergency-call mode mints a microphone capability bounded to the zero-authority emergency compartment, so *cut on lockout* and *available to an emergency call at BFU* are one rule about grants, not a rule plus an exception.
· Trace: CJ-CERISE · [L1460–1461](verification-maximal-os.md#L1460)

**R-15-148** IS — The sealed manual cutoffs dominate every software enable: a thrown microphone switch yields a connected but mute emergency call, and no software path re-opens it.
· Accept: the cutoff state dominates any firmware or software enable, with no firmware in the loop.
· Trace: CJ-T · [L1462](verification-maximal-os.md#L1462), [L1469](verification-maximal-os.md#L1469)

**R-15-149** IS — In the mobile form factor the phone is always ringable: the away-gesture keeps the minimal cellular paging and voice-call grant alive while revoking every other radio and modem grant; only an airplane or high-assurance policy, or the manual radio switch, revokes the cellular ring itself.
· Accept: the away-gesture is form-factor-specific (lid close, face-down, or lockout alone) and triggers lockout.
· Trace: CJ-CERISE · [L1463–1465](verification-maximal-os.md#L1463)

**R-15-150** IS — The microphone, radio, and USB-data cutoffs are sealed, gasketed Hall-effect (or reed) switches, preserving the ingress-protection rating with no chassis penetration; whether the break is a contact or a dominant FET is an implementation choice, auditable by IRIS inspection.
· Accept: the cut is a dominant load-switch on the power/bias rail, or the data-lane mux for USB.
· Trace: CJ-T · [L1466–1469](verification-maximal-os.md#L1466)

**R-15-151** MUST — The USB cutoff drives the fixed-function data-lane mux, cutting D+/D−, SuperSpeed, and SBU pairs at the connector while VBUS, CC, and the fixed-function power-delivery sequencer keep charging alive.
· Accept: the attacker device never reaches the USB stack's enumeration and descriptor-parse path; no firmware sits in the path.
· Trace: CJ-CERISE · [L1471–1474](verification-maximal-os.md#L1471)

**R-15-152** IS — The camera's hard cutoff is a mechanical shutter with no electronics and no ingress path; beneath it, sensor access is a powerbox-mediated per-app consent grant scoped in time and to the device.
· Accept: on lockout the camera cuts through capability revocation rather than the shutter; the camera needs no sealed Hall switch because the shutter is its natural occluder.
· Trace: CJ-CERISE · [L1475–1479](verification-maximal-os.md#L1475)

### 15.21 Enclosure, shielding, and radiation hardening

**R-15-153** MUST — The enclosure is a continuous grounded conductive Faraday shell bonded at every seam and referenced to the device's own ground plane, with board-level shield cans over the RoT, the crypto core, and the radio front end, and every aperture treated (waveguide-below-cutoff vents, filtered and shielded I/O).
· Accept: admitted under the defense-in-depth clause as spending nothing on the scarce axis.
· Trace: CJ-T · [L1483–1485](verification-maximal-os.md#L1483)

**R-15-154** IS — The antennas sit outside the shielded volume and the wanted signal crosses on a coaxial, bulkhead-bonded RF feed, so the boundary stays continuous to stray fields while remaining transparent to the intended link.
· Accept: the shield encloses compute and memory logic, not the radiating elements.
· Trace: CJ-T · [L1486–1489](verification-maximal-os.md#L1486)

**R-15-155** IS — The shield addresses radiated and conducted EMI, electromagnetic fault injection, ESD, and compromising emanations; residual injected faults are caught by fixed-latency ECC and the fail-stop SEU/glitch path rather than trusted to the shield.
· Accept: *hardness at the boundary, correctness in the logic* is the stated split.
· Trace: CJ-T · [L1490–1492](verification-maximal-os.md#L1490)

**R-15-156** MUST NOT — Mass radiation shielding is declined: it does nothing to secondary neutrons and muons and a thin added mass raises the local upset rate through spallation.
· Accept: single-event upsets are met in the logic by pervasive ECC, CHERI validity tags, the fail-stop sentinel, multikernel blast-radius containment, and the RoT watchdog.
· Trace: CJ-T · [L1493–1497](verification-maximal-os.md#L1493)

**R-15-157** IS — Radiation hardening (hardened cells, upset-tolerant flip-flops, error-hardened SRAM, latch-up-immune wells, wide environmental envelope) is graded to the deployment and is a property of the process and RTL cells, not the architecture.
· Accept: the Sail model is unchanged and RTL ⊑ Sail still holds; the memory tiers take bottom dielectric isolation and the logic tier its SOI substrate.
· Trace: CJ-RTL-SAIL · [L1498–1502](verification-maximal-os.md#L1498)

### 15.22 Memory subsystem

**R-15-158** MUST — Main memory is bespoke on-die SRAM on the same die as the cores, not DRAM.
· Accept: no refresh, no refresh management, and no charge-disturbance Rowhammer primitive exists; the accepted price is density and idle leakage.
· Trace: CJ-SAIL, CJ-WCET · [L1554–1555](verification-maximal-os.md#L1554)

**R-15-159** IS — Density and leakage are bought by static, transistor-level levers only: sequential 3D tiers, CFET-stacked cells, gate-all-around, High-NA EUV patterning; asymmetric-Vt cells, gate-length biasing, state-retentive sleep-transistor gating, fixed logic-tier body bias, and a fixed composition-time read/write assist.
· Accept: the dynamic, adaptive, or data-dependent variants (adaptive assist, workload- or temperature-tracking body bias, activity-driven power gating) are declined; sub-threshold operation is admitted only as near-threshold idle-bank retention.
· Trace: CJ-LEAK · [L1556](verification-maximal-os.md#L1556), [L1563](verification-maximal-os.md#L1563)

**R-15-160** MUST NOT — Backside power delivery is declined for the whole machine, because it would occlude the IRIS backside optical inspection path; the die keeps frontside power delivery.
· Accept: the leakage and IR-drop cost is booked against the static cell levers.
· Trace: CJ-T · [L1557–1559](verification-maximal-os.md#L1557)

**R-15-161** MUST — Gate-all-around and CFET are admitted for the upper memory tiers and declined for the bottom logic tier, so the tier IRIS most needs to resolve (RoT, cores, capability fabric, memory controller) stays on an infra-red-resolvable node.
· Accept: the reconciliation is one die graded by tier; upper tiers are passive arrays holding no logic.
· Trace: CJ-T · [L1560–1561](verification-maximal-os.md#L1560)

**R-15-162** MUST NOT — A chiplet realization and bonded die-stacking are both declined: a separately fabricated die is a second mask set, fab lot, and supply-chain entity.
· Accept: multi-tier capacity is taken monolithically by sequential 3D, sharing one mask set, one fab lot, one package, and one attested identity, with no die-to-die link anywhere.
· Trace: CJ-DEVTREE · [L1564–1566](verification-maximal-os.md#L1564)

**R-15-163** IS — Two consequences of sequential 3D are normative: static body bias is a logic-tier lever only, and the shared thermal budget caps upper-tier device quality and tightens sustained-power headroom.
· Accept: both are carried in the §16 thermal posture and the leakage story.
· Trace: CJ-RTL-SAIL · [L1567](verification-maximal-os.md#L1567)

**R-15-164** MUST NOT — There are no hardware caches: no L1, no L2, no last-level cache, and no cache-coherence protocol.
· Accept: the cache hierarchy is deleted, not partitioned; the coherence protocol and directory leave the Sail model; the way-partitioning apparatus is unneeded; the `fence.t` flush set shrinks toward the store buffer alone.
· Trace: CJ-SAIL, CJ-ISOL · [L1570–1573](verification-maximal-os.md#L1570)

**R-15-165** IS — The retained fast structures are not caches: the register files, the Ztso store buffer, the static-path fetch buffer, and the explicit software-managed scratchpads of the V- and M-class datapaths.
· Accept: each passes the test that its contents are a function of the program text or of an explicit software placement, never of access history; address-indexing describes the lookup, history-dependence the contents, and only the latter carries the channel.
· Trace: CJ-ISOL · [L1574–1576](verification-maximal-os.md#L1574)

**R-15-166** IS — A structure holding *recently-used* anything fails that test however it is indexed — which is one of the grounds on which the memory integrity tree's node buffer is declined.
· Accept: the flat-latency claim holds precisely because no structure of the kind is present.
· Trace: CJ-WCET · [L1577](verification-maximal-os.md#L1577), [L1675](verification-maximal-os.md#L1675)

**R-15-167** IS — Fast local memory, where a datapath needs it, is an explicit scratchpad: capability-governed plain memory at a fixed address range, WCET-exact and coherence-exempt, holding no reactive or hidden state.
· Accept: it adds no timing channel and no flush obligation beyond the eager save-and-zeroize already accounted at a partition switch.
· Trace: CJ-WCET, CJ-ISOL · [L1578](verification-maximal-os.md#L1578)

**R-15-168** IS — Scalar cores carry no local memory tier: their hierarchy is register file to SRAM main memory, flat and uniform. A scalar scratchpad is admitted only as a design-space-exploration parameter where access is predictable and high-reuse enough for static staging to pay.
· Accept: irregular latency is recovered off-device by static layout, never by a hardware cache.
· Trace: CJ-WCET · [L1579–1582](verification-maximal-os.md#L1579)

**R-15-169** IS — A cacheless core is a fully conformant RISC-V profile choice, not a fork: the ISA names no cache level, Ztso is defined over ordering, and `Zicbom` is dropped for want of a consumer.
· Accept: no conformance exception is claimed on this account.
· Trace: CJ-SAIL · [L1583](verification-maximal-os.md#L1583)

**R-15-170** IS — The capacity budget is arithmetic: ~30–50 Mb/mm² of macro, so one gigabyte is roughly 160–270 mm² of raw array and a flat 4 GB is on the order of a full reticle or more; the High-NA half field (~430 mm²) is the hard planar boundary, so capacity is bought vertically.
· Accept: the reference instantiation budgets ~4–8 GB phone-class (8–16 memory tiers) and 16–32 GB laptop/desktop-class, as composition-time constants in the attested devicetree.
· Trace: CJ-DEVTREE · [L1585–1588](verification-maximal-os.md#L1585)

**R-15-171** MUST — The roster is fit to the budget explicitly, and a workload that does not fit is refused at admission, not paged: there is no swap and no overcommit anywhere, every resident byte being a capability-delegated SRAM byte.
· Accept: browser origins take a composition-sized budget with crash-only eviction; the inference server serves the 1–4 B-parameter class on a phone and the 7 B-plus class on laptop/desktop.
· Trace: CJ-MEMPLAN · [L1590](verification-maximal-os.md#L1590)

**R-15-172** IS — Island exclusivity is a booked capacity tax: whole-macro or whole-tier binding forfeits pooling, so each island is sized to its peak rather than the machine to the sum of averages.
· Accept: the fraction is composition-visible and netted out of the budget.
· Trace: CJ-ISOL · [L1591](verification-maximal-os.md#L1591)

**R-15-173** MUST — Should the density levers under-deliver, the fallback bends capacity (fewer origins, smaller models, a leaner roster), never the mechanism: DRAM does not return and neither does a second die.
· Accept: the fallback is stated as a composition change, not an architectural one.
· Trace: CJ-DEVTREE · [L1589](verification-maximal-os.md#L1589), [L1592](verification-maximal-os.md#L1592)

**R-15-174** MUST NOT — Variable-rate compression of the memory path (a compressed pool or cache, runtime deduplication) is declined: it would make capacity data-dependent, latency operand-dependent, and the ratio a cross-compartment oracle.
· Accept: fixed-rate encodings chosen at composition time remain admissible as compartment-local data representations.
· Trace: CJ-NI, CJ-WCET · [L1593](verification-maximal-os.md#L1593)

**R-15-175** MUST — Every SRAM array is ECC-protected and corrected, not merely detected: register files, vector register files, matrix scratchpads, the CHERI native tag bits, and the main-memory array alike.
· Accept: the floor is SECDED everywhere, with no structure left parity-only, because a scratchpad word or live register holds the only copy of its word.
· Trace: CJ-SAIL · [L1594–1598](verification-maximal-os.md#L1594)

**R-15-176** MUST — The error-detecting check travels *with* the word across the interconnect and the memory controller and is verified at the consumer, so a fault injected in transit is caught rather than masked by re-encoding at each hop.
· Accept: there is no die-to-die interface to protect; every hop is on-die. **See [D-09](#d-09).**
· Trace: CJ-SAIL · [L1596–1597](verification-maximal-os.md#L1596)

**R-15-177** MUST — Physical bit-interleaving and background scrubbing are mandated, not optional: a multi-cell upset presents as separable SECDED-correctable single-bit errors, and a latent single-bit error never accumulates into an uncorrectable double.
· Accept: both are present on every array.
· Trace: CJ-SAIL · [L1599](verification-maximal-os.md#L1599)

**R-15-178** MUST — The CHERI validity tag bits take the stronger DECTED code, because a flipped tag forges or destroys a capability.
· Accept: the tag plane's code is DECTED throughout.
· Trace: CJ-CERISE · [L1600](verification-maximal-os.md#L1600)

**R-15-179** MUST — ECC correction is deterministic: a fixed data-independent latency folded into WCET, the corrected and uncorrected paths taking the same cycles.
· Accept: no variable slow path exists; every corrected error is reported to the sentinel as telemetry and every detected-but-uncorrectable error is a fail-stop sentinel event, never silently consumed.
· Trace: CJ-WCET, CJ-LEAK · [L1601–1602](verification-maximal-os.md#L1601)

**R-15-180** IS — ECC is the memory path's only integrity mechanism, deliberately: it answers the random bit flip, which is the threat main memory on this die actually faces.
· Accept: cryptographic memory constructions answer an interface this machine does not have (R-15-195).
· Trace: CJ-SAIL · [L1603](verification-maximal-os.md#L1603)

**R-15-181** MUST — No sub-granule write exists at the array: the atomic write unit is the ECC codeword with its validity tag bit, and every path that reaches the array writes whole units.
· Accept: a sub-granule store merges with the granule's existing codeword in a fixed read-modify-write stage at the memory controller, a constant pipeline term priced once, with tag and check bits regenerated combinationally in the same pass. **See [D-09](#d-09).**
· Trace: CJ-WCET · [L1604–1606](verification-maximal-os.md#L1604)

**R-15-182** MUST — `cbo.zero` allocates whole lines: zero data, cleared validity tags, and matching SECDED/DECTED codewords for data and tag plane alike, in one pass at one fixed per-line latency.
· Accept: one entry in the timing-annotated model.
· Trace: CJ-MEMPLAN · [L1607](verification-maximal-os.md#L1607)

**R-15-183** MUST — Device DMA is granule-aligned by construction: windows are allocated at tag-granule (16-byte) alignment, interface FIFOs coalesce arrivals into granule-multiple bursts, and a trailing partial granule completes with zero fill inside the delegated buffer.
· Accept: a non-capability DMA write clears the validity tags of exactly the granules it wholly covers and can straddle nothing; the descriptor's length field, not the fill, delimits the payload.
· Trace: CJ-CERISE · [L1608](verification-maximal-os.md#L1608)

**R-15-184** IS — Rowhammer has no charge-disturbance analog in SRAM, so the refresh-management apparatus (RFM cadence, PRAC counters, alert and back-off) is deleted, not tuned.
· Accept: the residual is SRAM's own read/write-disturb and half-select modes, covered by the pervasive ECC and cell-level margin, with an uncorrectable event a fail-stop sentinel event.
· Trace: CJ-SAIL · [L1610–1614](verification-maximal-os.md#L1610)

**R-15-185** MUST NOT — Autonomous processing-in-memory is banned: compute placed inside the memory array is outside the ISA, capability model, Sail model, and attestation.
· Accept: the admitted densification path is deterministic digital compute-in-SRAM (bit-serial exact MACs, Sail-expressible) for the M-class, never an autonomous or analog one.
· Trace: CJ-SAIL · [L1615–1616](verification-maximal-os.md#L1615)

### 15.23 Power architecture

**R-15-186** MUST — Exactly four power mechanisms are admissible, and every banned mechanism (SMM PM handlers, Pcode/SCP/AOP PMU microcontrollers, reactive DVFS, turbo, autonomous throttling) is banned for sharing a hidden feedback loop from workload or temperature to performance state.
· Accept: the four are race-to-idle with in-slot gating; static per-partition operating points; pre-proved global mode schedules; and deep sleep as a boot-chain variant.
· Trace: CJ-ISOL, CJ-WCET · [L1620–1634](verification-maximal-os.md#L1620)

**R-15-187** MUST — In-slot clock/power gating is entered only when the remaining slot ≥ entry+exit WCET, and exit latency is a data-independent Sail-modeled constant.
· Accept: slot boundaries do not move; an idle core emits no shared-fabric traffic, so gating is cross-partition invisible.
· Trace: CJ-WCET, CJ-ISOL · [L1623–1625](verification-maximal-os.md#L1623)

**R-15-188** MUST — Each partition's operating point is selected by the §11 admission proof and is a composition-time constant, switched only at partition boundaries; shared resources (NoC, memory controller, main memory) never scale.
· Accept: data-independent, so Hertzbleed has no carrier; expect 2–3 coarse OPPs per class, floored by ECC/CHERI-tag integrity margin at low voltage.
· Trace: CJ-WCET, CJ-LEAK · [L1626–1630](verification-maximal-os.md#L1626)

**R-15-189** MUST — Global mode schedules are pre-proved and switched as rare RoT-attested global transitions on explicit authority, never load-following.
· Accept: log₂(#modes) bits per audited event; migration stays banned.
· Trace: CJ-NI · [L1631–1632](verification-maximal-os.md#L1631)

**R-15-190** MUST — Standby is a partial-power global mode (mechanism 3), not whole-machine deep sleep: exactly one island stays live at low duty cycle while every other island is sealed and powered off.
· Accept: the live set is enumerated as the radio island, its kernel instance, the cellular paging path, the DRX wake timer, the island's bound SRAM bank in low-leakage retention, and the RoT — a composition-time constant attested on entry.
· Trace: CJ-ISOL, CJ-DEVTREE · [L1636–1642](verification-maximal-os.md#L1636)

**R-15-191** IS — The memory path needs no protection carve-out in the live set: it holds no key, no counter, and no root register, so the live set is ordinary static logic rather than an exception carved for a cryptographic invariant.
· Accept: the retained bank plus the TDM slice joining island to bank is the whole of it.
· Trace: CJ-ISOL · [L1639–1641](verification-maximal-os.md#L1639)

**R-15-192** MUST — The live island does not resume: it runs idle-mode DRX paging reception as a §11-admitted periodic hard task (period = the network's DRX cycle, deadline = the paging occasion), so no resume path outside the measured chain is created.
· Accept: deep-slept islands re-measure on wake; a page that escalates to a connection wakes the application islands through the boot-chain-variant path.
· Trace: CJ-WCET, CJ-DEVTREE · [L1643–1645](verification-maximal-os.md#L1643)

**R-15-193** MUST — Thermal posture is fail-stop, not modulation: TDP-provisioned so throttling never engages normally, with critical temperature triggering a rare attested global transition (orderly halt or a proved low-power/recovery mode).
· Accept: a ~1-bit event rather than continuous throttling's data-dependent channel; temperature read-out is a gated capability.
· Trace: CJ-NI · [L1648–1651](verification-maximal-os.md#L1648)

**R-15-194** MUST — There is exactly one management processor, the RoT: power sequencing, reset, mode orchestration, and the watchdog are RoT duties, verified, in the TCB, never resident on or above the application cores.
· Accept: no embedded controller, PMU microcontroller, or SMM-class residency exists.
· Trace: CJ-DEVTREE · [L1653–1655](verification-maximal-os.md#L1653)

### 15.24 Clocking, reset, and domain crossings

**R-15-195** MUST — All modeled islands run mesochronous from one clock spine: every core, fabric, memory, and device-block clock is an integer division of a common PLL hierarchy, so crossings inside the modeled machine are deterministic ratio synchronizers with fixed, Sail-modeled latency.
· Accept: the TDM NoC schedule is stated in spine cycles; an OPP change is a divider reprogram at a partition boundary whose relock is a fixed constant in the switch budget; no modeled path crosses between unrelated clocks.
· Trace: CJ-WCET, CJ-SAIL · [L1657–1660](verification-maximal-os.md#L1657)

**R-15-196** IS — The genuinely asynchronous boundaries are exactly three, each terminated and none modeled as fixed-latency: the RoT's independent slow clock, the external interface clocks, and reset itself.
· Accept: every theorem touching the RoT path uses one-sided bounds only; external interface clocks terminate in a bounded FIFO behind the capability-checked DMA window, contributing only a line-rate bound to the §11 bandwidth reservation; reset is synchronized per domain at its boundary.
· Trace: CJ-WCET, CJ-ISOL · [L1661](verification-maximal-os.md#L1661)

**R-15-197** IS — Residual synchronizer failure is booked beside SEU as a physical fault class, not a modeled behaviour: rate engineered to negligible MTBF, consequences caught by ECC, fail-stop, and the watchdog.
· Accept: no modeled constant quantifies over a metastability resolution.
· Trace: CJ-RTL-SAIL · [L1662](verification-maximal-os.md#L1662)

**R-15-198** MUST — Power-domain and reset sequencing is a fixed, composition-time sequence table in the attested devicetree, dependency-ordered, each step gated on a hardware ready indication under a watchdog-bounded timeout, executed by the verified RoT firmware as the only sequencer.
· Accept: mode transitions, standby entry and exit, and deep-sleep wake are re-entries into suffixes of the same table, so there is one sequencing artifact to verify, a crown-jewel spec beside the NoC schedule; resets are hierarchical, and only the watchdog bite asserts the die.
· Trace: CJ-DEVTREE · [L1663–1664](verification-maximal-os.md#L1663)

### 15.25 The memory path carries no cryptography

**R-15-199** MUST NOT — There is no memory encryption, no memory authentication, and no integrity or anti-replay tree on the memory path.
· Accept: main memory is on-die SRAM with no external bus, no removable module, and no die-to-die link, so the interface such a mechanism would protect does not exist.
· Trace: CJ-T · [L1666–1669](verification-maximal-os.md#L1666)

**R-15-200** IS — The benefits usually claimed are each discharged by something already present: shutdown zeroization by SRAM volatility plus the platform's own zeroize, the bus interposer by the absence of any bus, cold boot by the same volatility; what remains is invasive physical attack, out of scope by name.
· Accept: the exclusion cites the same *verify rather than hedge* ground as PMP, the IOMMU, MTE, and the Harvard split.
· Trace: CJ-T · [L1670–1672](verification-maximal-os.md#L1670)

**R-15-201** IS — The integrity and anti-replay tree is declined on two further grounds of its own: its node buffer would be a cache by this section's own test (failing test 3 and reintroducing the WCET-pessimism term), and its log-depth walk with a hit-or-miss distribution is exactly the term §11 must otherwise bound pessimistically on every access.
· Accept: the adversary it names can equally read the on-die root register the guarantee rests on.
· Trace: CJ-WCET, CJ-ISOL · [L1673–1676](verification-maximal-os.md#L1673)

**R-15-202** IS — Crown-jewel secret confidentiality rests on the crypto core's hardware boundary and the seal/switch primitives, not on encrypting memory: keys never leave the core, and what is resident outside it is a sealed blob plus a capability handle.
· Accept: the memory controller carries only the granule read-modify-write stage and the ECC encode-and-check — no key, no cipher, no counter, and no address-dependent latency class.
· Trace: CJ-CERISE · [L1677–1679](verification-maximal-os.md#L1677)

**R-15-203** MUST — CHERI tags are native SRAM bits, one validity tag per 128-bit granule, one plane and not two, read and written in parallel with the data, with no separate table and no tag cache.
· Accept: the reserved-memory tag table and the partitioned tag cache are deleted, and with them a shared microarchitectural state element, its miss-and-walk latency term, its way-partitioning and `fence.t` membership, and its DSE parameter.
· Trace: CJ-CERISE, CJ-ISOL · [L1680–1681](verification-maximal-os.md#L1680)

**R-15-204** IS — Tag integrity is an ECC property, not a cryptographic one, because the tag bits never leave the die; a tag-integrity failure is an ECC event and a fail-stop sentinel event.
· Accept: non-capability transducer and DMA writes clear the corresponding tag bit by construction.
· Trace: CJ-CERISE · [L1682–1683](verification-maximal-os.md#L1682)

### 15.26 Capability-checked DMA

**R-15-205** MUST NOT — Neither an IOMMU nor an IOPMP is on the die: device DMA is brought under CHERI rather than confined by a separate translation or region-protection unit.
· Accept: the device-side completion of the No-PMP decision; the IOMMU's translation is dead weight in one address space and only its protection is wanted, which CHERI supplies unforgeably and byte-granularly.
· Trace: CJ-CERISE · [L1685–1689](verification-maximal-os.md#L1685)

**R-15-206** MUST — Every DMA-capable block is one of exactly two capability-checked shapes: a core-issued capability-operand mover, or an autonomous streaming engine holding a delegated, bounds-checked, revocable capability for the lifetime of its window.
· Accept: the fabric checks each device access against a capability at the point of issue, default-deny, exactly as a core's load or store is checked; a device MSI is confined by the same check rather than an interrupt-remapping table.
· Trace: CJ-CERISE · [L1687–1688](verification-maximal-os.md#L1687)

**R-15-207** IS — The rule governs true devices only (NIC, flash interface, USB, scanout, audio, radio transceiver stream); V/M cores are cores and are already CHERI-governed.
· Accept: no device class falls outside the two shapes.
· Trace: CJ-CERISE · [L1690](verification-maximal-os.md#L1690)

**R-15-208** MUST — In-flight-DMA revocation is an obligation, not a waiver: a capability held by a running transfer honours the §8 revocation sweep (a load-barrier / revocation-epoch check, or bounded per-window re-authorization) so time-to-containment stays the §8 bounded constant, its worst case entering the §11 budget.
· Accept: the mechanism is named and its cost budgeted.
· Trace: CJ-CERISE, CJ-WCET · [L1692](verification-maximal-os.md#L1692)

**R-15-209** MUST — The interconnect is a capability- and tag-carrying fabric: it propagates capabilities, tags, and revocation state to the DMA blocks, while non-capability transducer writes clear tags by construction.
· Accept: this is new Sail-model and RTL ⊑ Sail surface, booked in §18.
· Trace: CJ-RTL-SAIL · [L1692](verification-maximal-os.md#L1692)

**R-15-210** IS — The deletion is sound only because the device model is already curated register-slave / transducer / on-die RTL, with no foreign bus-master issuing raw physical addresses; the residual (no IOMMU-disjoint backstop) is booked in §17.
· Accept: both the precondition and the residual are recorded.
· Trace: CJ-CERISE · [L1693](verification-maximal-os.md#L1693)

### 15.27 Temporal isolation and `fence.t`

**R-15-211** MUST — Temporal isolation is carried by `fence.t`-class flush at partition switches, SRAM bank/macro/tier partitioning, and TDM NoC arbitration with island separation, each carrying architecturally guaranteed non-interference semantics in the Sail model.
· Accept: a partition's timing behaviour is provably independent of another's activity.
· Trace: CJ-ISOL, CJ-NI · [L1695–1697](verification-maximal-os.md#L1695)

**R-15-212** IS — Bandwidth appears as a consequence of the NoC schedule and the bank binding, never as a regulated quantity; no bandwidth-allocation mechanism exists beside them.
· Accept: `Ssqosid`/CBQRI is excluded (R-15-050).
· Trace: CJ-ISOL · [L1696](verification-maximal-os.md#L1696)

**R-15-213** MUST — The `fence.t` flush set is a single structure: the store buffer, drained rather than merely fenced, so no old-partition store can land or become visible after the switch.
· Accept: the predictor-history, transient, and cache-state classes are absent by construction rather than flushed.
· Trace: CJ-ISOL · [L1698](verification-maximal-os.md#L1698), [L1702](verification-maximal-os.md#L1702)

**R-15-214** MUST — The register files are deliberately not in the flush set; what replaces flush-set membership is an obligation on the primary: the kernel's restore set is total over architectural register state, every general-purpose, capability, and CSR location a partition can name being written before the successor partition's first instruction.
· Accept: residue is impossible rather than cleared, and a register outside the restore set is a failure of the kernel proof.
· Trace: CJ-KERNEL, CJ-ISOL · [L1703–1704](verification-maximal-os.md#L1703)

**R-15-215** MUST — Nothing else joins the flush set, each would-be member being already absent or covered elsewhere: no predictor, no reservation, no prefetcher, no TLB or walk cache, no cache of any kind, no scalar-FP or rounding-mode state, the register files by total restore, and the vector/matrix and scratchpad state by the §7 eager save-and-zeroize.
· Accept: each is a distinct named mechanism, not the fence's job. **See [D-07](#d-07).**
· Trace: CJ-ISOL · [L1705](verification-maximal-os.md#L1705)

**R-15-216** IS — `fence.t` does not touch state that is partitioned rather than time-shared (SRAM banks/macros/tiers, TDM NoC slots, per-partition interrupt-file state), and in-flight DMA is not its concern: device windows are torn down or re-authorized by the capability machinery at the boundary.
· Accept: flushing spatially-owned state would be a category error.
· Trace: CJ-ISOL, CJ-CERISE · [L1706](verification-maximal-os.md#L1706)

**R-15-217** MUST — The completeness argument is mechanized: every stateful structure in the RTL is mapped, in the RTL ⊑ Sail refinement, to exactly one of four classes — architectural or context-switched; partition-owned; `fence.t`-flushed; or stream-determined pipeline state (the static-path fetch buffer and the decode and execute latches, emptied by the fence's pipeline drain) — and a structure outside the map is a refinement failure.
· Accept: *did we flush everything* is discharged against the RTL state inventory rather than a hand-maintained list, and the fourth class is bounded by the same table-freeness test that separates fetch pipelining from a prefetcher (R-15-104).
· Trace: CJ-RTL-SAIL, CJ-ISOL · [L1707](verification-maximal-os.md#L1707)

**R-15-218** MUST — `fence.t`'s cost is a padded per-class constant and the fence completes at that bound, never early.
· Accept: the worst case is the store buffer's drain latency at the class's depth and memory bandwidth, a data-independent entry in the timing-annotated model.
· Trace: CJ-WCET, CJ-LEAK · [L1708](verification-maximal-os.md#L1708)

**R-15-219** IS — That constancy, not the draining, is why a plain `fence` cannot replace it: a `fence` completes when the buffer happens to empty, making its duration a function of the outgoing partition's store-buffer occupancy — a partition-switch-duration channel.
· Accept: the temporal fence makes the term data-independent, a property no ordering fence has.
· Trace: CJ-NI, CJ-WCET · [L1709](verification-maximal-os.md#L1709)

**R-15-220** MUST — Partition-switch cost is three terms, not four: the `fence.t` padded constant (which *is* the store-buffer drain, counted once), eager vector/matrix save-and-zeroize, and OPP relock where operating points differ.
· Accept: listing the fence and the drain separately would inflate every switch bound feeding §11 by a full drain.
· Trace: CJ-WCET · [L1699](verification-maximal-os.md#L1699), [L1710](verification-maximal-os.md#L1710)

**R-15-221** IS — The flush-set statement is itself a crown-jewel spec, now over one structure rather than two.
· Accept: it appears in the crown-jewel inventory and is subject to independent review.
· Trace: CJ-ISOL · [L1710](verification-maximal-os.md#L1710)

### 15.28 Interconnect and islands

**R-15-222** IS — Islands are confidentiality domains: a memory, NoC, and power partition (bound SRAM banks, macros, or tiers, TDM-NoC slots, and at the top rung its own clock and power domain), not a coherence domain.
· Accept: no cache-coherence protocol and no coherence directory exist within or across islands.
· Trace: CJ-ISOL · [L1713–1715](verification-maximal-os.md#L1713)

**R-15-223** MUST — Across islands there is no shared mutable memory at all: cross-island communication is only through designated ring windows in a shared SRAM region, made visible by ordinary Ztso-ordered stores and fences.
· Accept: the cross-domain coherence-traffic channel is deleted structurally, there being no coherence traffic anywhere on the die.
· Trace: CJ-ISOL, CJ-NI · [L1716–1717](verification-maximal-os.md#L1716)

**R-15-224** MUST — The radio-pinned V-cores form their own island and take the top rung of every graded axis: a separate SRAM macro or tier, and their own clock/power island.
· Accept: the on-die power-delivery droop coupling a shared-die radio would leave is deleted on one die rather than by a second package.
· Trace: CJ-ISOL · [L1719](verification-maximal-os.md#L1719)

**R-15-225** MUST — The NoC uses TDM arbitration with formal semantics, its schedule emitted by the §11 admission proof, and its non-interference is part of the Sail-level isolation model. Best-effort QoS is not admissible.
· Accept: no arbitration decision depends on another domain's activity.
· Trace: CJ-ISOL, CJ-NI · [L1720–1721](verification-maximal-os.md#L1720)

**R-15-226** MUST — The SRAM bank, macro, or tier is bound to the island as a graded spatial hierarchy: separate macro or stacked tier, then separate bank group, then bank within a macro, decreasing in isolation strength as sharing rises to a common macro.
· Accept: high-assurance islands take whole-macro (better, whole-tier) exclusivity; mid- and low-sensitivity islands take bank granularity, with residual macro-internal coupling narrowed by static per-island arbitration and `fence.t` and §17-listed rather than eliminated.
· Trace: CJ-ISOL · [L1722–1725](verification-maximal-os.md#L1722)

**R-15-227** MUST — Residual coupling is narrowed by scheduling, never by throttling: a rate regulator could only shape traffic whose arrival the TDM schedule already fixed, which is why none exists.
· Accept: consistent with R-15-050.
· Trace: CJ-ISOL · [L1726](verification-maximal-os.md#L1726)

**R-15-228** MUST — The memory controller enforces the binding, its per-island arbitration carries TDM-NoC-class non-interference semantics in the Sail model, and the bank/macro/tier→island map lands in the attested static devicetree as a crown-jewel spec.
· Accept: each island's bandwidth ceiling quantizes to its assigned banks or macros and feeds §11 admission.
· Trace: CJ-ISOL, CJ-DEVTREE · [L1728–1729](verification-maximal-os.md#L1728)

### 15.29 Display and media

**R-15-229** IS — The scanout controller is the one graphics device: a small open-RTL firmware-free DMA block behind a static capability-bounded DMA window; audio I/O follows the same pattern.
· Accept: they are allowlisted peripherals, not accelerators.
· Trace: CJ-CERISE · [L1732–1733](verification-maximal-os.md#L1732)

**R-15-230** MUST — The §11 admission proof emits, with every mode schedule, the scanout engine's static TDM NoC slice, its framebuffer bank-group binding, and a line-buffer FIFO sized to the TDM service interval, so underrun cannot arise from contention by construction.
· Accept: the line period is the deadline and the FIFO depth the proved jitter bound; the framebuffer is ordinary main memory read through the same ECC-only path, with no cryptographic term on the scanned line.
· Trace: CJ-WCET · [L1734](verification-maximal-os.md#L1734)

**R-15-231** MUST — Display underrun is a §16 sentinel fault class, not a load outcome: affected lines blank visibly as the presentation of a caught fail-stop, never a silent display of unauthenticated bytes.
· Accept: recovery is the ordinary §16 restart of the display path.
· Trace: CJ-ISOL · [L1735](verification-maximal-os.md#L1735)

**R-15-232** IS — The internal display link is dedicated, fixed-function, and point-to-point (eDP for laptop-class, MIPI DSI for phone or tablet) with no hot-plug negotiation against an untrusted device.
· Accept: its security is minimal attack surface, not a cryptographic property.
· Trace: CJ-CERISE · [L1736–1737](verification-maximal-os.md#L1736)

**R-15-233** MUST — External display is output-only over DisplayPort Alternate Mode on USB-C or a dedicated DisplayPort connector: it carries the scanout controller's native DisplayPort lanes and opens no path into memory.
· Accept: alt-mode entry is a fixed-function sequencer (the DisplayPort alt mode alone, not general vendor-defined messages); USB4/Thunderbolt DisplayPort tunneling stays excluded.
· Trace: CJ-CERISE · [L1738–1739](verification-maximal-os.md#L1738)

**R-15-234** MUST — EDID is accepted only up to a tight, composition-time block cap sized to the 128–512-byte range real displays span, not the format's 32 KB maximum, and is parsed copy-once by the schema-bounded Narcissus decoder; anything beyond the cap is rejected.
· Accept: the cap is a composition constant; the parser is a §5 Narcissus artifact.
· Trace: CJ-FORMAT · [L1739](verification-maximal-os.md#L1739)

**R-15-235** MUST — Enabling an external monitor is a powerbox-mediated act gated on user consent; multi-stream daisy-chaining, HDCP, DP++ dual-mode, and any Thunderbolt or USB4 tunnel stay excluded.
· Accept: single-stream display output only.
· Trace: CJ-CERISE · [L1740](verification-maximal-os.md#L1740)

**R-15-236** MUST — The panel's timing controller is fixed-function with no programmable firmware: no smart-panel scaler or overdrive DSP blob. Scaling, colour management, and temporal processing are host software on the V-class cores.
· Accept: a fixed-function panel-self-refresh block is admissible on the sensor and radio fixed-function terms (no writable program).
· Trace: CJ-CERISE · [L1742](verification-maximal-os.md#L1742)

**R-15-237** IS — The touchscreen is a projected-capacitive raw-capacitance AFE under the sensor doctrine: every baselining, rejection, touch, and gesture stage is host software, never a tuned-firmware touch controller. Resistive touch is not used.
· Accept: no touch-controller firmware exists.
· Trace: CJ-CERISE · [L1744–1745](verification-maximal-os.md#L1744)

**R-15-238** MUST NOT — No fixed-function codec blocks exist (unpatchable silicon parsers: grammar, not geometry); codecs run as contained software on V-class cores behind verified framing parsers.
· Accept: no codec block appears in the device inventory.
· Trace: CJ-FORMAT · [L1746–1747](verification-maximal-os.md#L1746)

**R-15-239** MUST NOT — The GPU command-processor surface class is deleted: there is no GPU, no GPU driver, and no separate graphics-driver trust surface. Work reaches V/M cores as ordinary capability-confined native code and ring-fed data.
· Accept: the render and compositor servers, safe Rust on RVV, are that driver.
· Trace: CJ-CERISE · [L1748–1749](verification-maximal-os.md#L1748)

### 15.30 Watchdog, entropy, and anti-features

**R-15-240** MUST — There is exactly one hardware watchdog and it is non-deletable: the RoT's always-on timer (bark/bite) on an independent slow clock, a failure domain disjoint from the cores, the main clock tree, and the scheduler.
· Accept: it is windowed (early pets fault as well as late) with bounds from the §11 schedule theorem; pets are RoT-nonce challenge-responses from a single capability holder; no external watchdog ICs and no PMIC watchdogs exist.
· Trace: CJ-DEVTREE · [L1751–1754](verification-maximal-os.md#L1751)

**R-15-241** MUST — The TRNG is in the RoT and the verified DRBG in the crypto core; because a draw is internal and no input trace captures it, every draw is accounted for in the deterministic-replay nondeterminism record — verbatim where the drawn value is public, as a sealed commitment where it is secret.
· Accept: all firmware is open, reproducible, and measured; the device allowlist is collapsed toward transducers and register slaves.
· Trace: CJ-NI, CJ-DEVTREE · [L1755–1758](verification-maximal-os.md#L1755)

**R-15-242** MUST NOT — The anti-feature set is excluded entirely: UEFI, SMM, ACPI/AML, ME/PSP-class coprocessors, SMT, speculation, dynamic branch prediction, LR/SC reservation state and general CAS, 32-bit modes, hybrid capability mode (no DDC), legacy boot, option ROMs, and the C extension.
· Accept: none appears in the profile, the Sail model, or any RTL.
· Trace: CJ-SAIL · [L1759](verification-maximal-os.md#L1759)

**R-15-243** MUST NOT — Also excluded: foreign computers of every stripe; discrete/opaque GPUs and fixed-function accelerator coprocessors, including SIMT GPGPU cores and fixed-function codec blocks; reactive/autonomous power management; hardware caches and cache coherence entirely; and the RVWMO weak memory model.
· Accept: each is enumerated with its replacement mechanism named.
· Trace: CJ-SAIL · [L1760–1767](verification-maximal-os.md#L1760)

**R-15-244** MUST NOT — Analog compute-in-memory (memristor/RRAM/PCM crossbars) is excluded: no deterministic ISA semantics to Sail-model, non-volatile analog weights are an at-rest confidentiality regression, and it presents the richest possible data-dependent power channel with a reactive calibration loop.
· Accept: admissible only as deterministic binary ReRAM/PCM storage below the §10 integrity line, or as a supplementary entropy source into the RoT conditioner (not adopted).
· Trace: CJ-SAIL, CJ-LEAK · [L1768–1770](verification-maximal-os.md#L1768)

**R-15-245** MUST NOT — SGX-class enclaves, ASLR, shadow stacks, and CFI/landing-pads are excluded: their threat model inverts this design, or they are obviated by proof plus CHERI and fight reproducibility and schedulability.
· Accept: no manifest-invisible memory exists that the monitor cannot inspect.
· Trace: CJ-CERISE · [L1771–1772](verification-maximal-os.md#L1771)

**R-15-246** MUST — Speculation-derived and hidden-state ISA features are excluded generally, per the five-part admission test, which is the standing rule that decides future extensions.
· Accept: R-15-010 governs every future amendment.
· Trace: CJ-SAIL · [L1773](verification-maximal-os.md#L1773)

---

## §16 — Reliability

### 16.1 Fault containment

**R-16-001** MUST — Any driver or server crash is contained and supervisor-restarted, and the kernel is never implicated; eager-zeroize means no residue crosses the restart.
· Accept: a crashed render, inference, or radio compartment is restarted like any other.
· Trace: CJ-KERNEL, CJ-CERISE · [L1779–1780](verification-maximal-os.md#L1779)

**R-16-002** IS — A radio-stack crash costs connectivity until restart, never platform integrity.
· Accept: the radio stack is wholly non-TCB (R-06-021).
· Trace: CJ-CERISE · [L1781](verification-maximal-os.md#L1781)

**R-16-003** MUST — Crash consistency on the integrity path is machine-checked; user data carries checksummed CoW plus patrol scrub; ECC telemetry spans cores, scratchpads, NoC, and the main-memory SRAM array.
· Accept: each is a named mechanism with an owner.
· Trace: CJ-DEVTREE · [L1782](verification-maximal-os.md#L1782)

**R-16-004** IS — Display underrun is a named fault class, not a cosmetic mystery: the scanout reservation being static, starving its FIFO cannot arise from contention, so an underrun is evidence of a fault on the framebuffer path and the visible blank is a caught fail-stop.
· Accept: consistent with R-15-231.
· Trace: CJ-WCET · [L1783](verification-maximal-os.md#L1783)

### 16.2 Watchdogs and escalation

**R-16-005** MUST — Watchdogs are layered: the sentinel-resident monitor responds surgically — restart, revoke, roll back — before escalation, and the RoT watchdog is the last resort, where bite equals reset, safe because state is transactional and nothing is lost but uncommitted work.
· Accept: the two tiers are distinct components with distinct failure domains.
· Trace: CJ-DEVTREE · [L1784](verification-maximal-os.md#L1784)

**R-16-006** IS — The bark's notice window is one slot, not trap latency, because asynchronous interrupt delivery does not exist: the bark sets a pending bit the boundary-timer handler reads, so a core alive but wedged is reached at its next slot boundary.
· Accept: the surgical tier is slot-granular and the sub-slot response is the bite alone — a deliberate narrowing of the escalation ladder's top rung, booked in §17 rather than absorbed (R-07-047).
· Trace: CJ-WCET · [L1785–1786](verification-maximal-os.md#L1785)

**R-16-007** MUST — Reset-loop abuse is bounded by boot counting into a minimal recovery state, so the worst case is bounded downtime, not permanent DoS; thermal fail-stop rides the same transactional safety.
· Accept: boot counting is an RoT duty (R-09-028).
· Trace: CJ-DEVTREE · [L1787–1788](verification-maximal-os.md#L1787)

**R-16-008** IS — Rollback is both automatic and user-driven, and the user-driven path adds recovery reach without adding trusted surface: the UI only stages, while the A/B transactor and RoT enforce the signed-root check, the anti-rollback floor, and the credential gate.
· Accept: the trust split is specified once, in §11 (R-11-002).
· Trace: CJ-DEVTREE · [L1789–1791](verification-maximal-os.md#L1789)

### 16.3 Time-to-remediation

**R-16-009** MUST — Time-to-remediation is a first-class property budgeted separately from time-to-full-fix: a live remote exploit is answered at detection latency, the sentinel triggering an attested transition that revokes the compromised compartment's capabilities, withdraws its rings, and fails its surface closed.
· Accept: this needs no new proof, because narrowing authority is monotone and cannot violate a safety theorem; the §6 checker still gates any replacement code.
· Trace: CJ-CERISE, CJ-NI · [L1792–1793](verification-maximal-os.md#L1792)

**R-16-010** IS — Containment latency is therefore the §8 bounded-revocation constant, budgeted like detection latency, while the full proof-carrying fix follows off the critical path.
· Accept: the fast path degrades capability under proof and the slow path restores it with proof; neither ships unproven code.
· Trace: CJ-CERISE · [L1794–1795](verification-maximal-os.md#L1794)

### 16.4 Diagnosis by deterministic replay

**R-16-011** MUST — Deterministic builds give deterministic failure reproduction, and diagnostics are capability-scoped; schedule-fixed frequencies, fixed-latency divide/FPU and atomic RMW, static-only control-flow prediction, and Ztso ordering extend determinism to timing-sensitive failure reproduction.
· Accept: each enabling property is a §15 mandate.
· Trace: CJ-WCET, CJ-SAIL · [L1796–1797](verification-maximal-os.md#L1796)

**R-16-012** MUST NOT — No verbose logging mode exists: one that captured data-dependent runtime state would be an unlabeled cross-boundary channel the non-interference theorem forbids and a forensic surface on a seized device.
· Accept: capability use *is* declassification, so an ambient log has no lawful form.
· Trace: CJ-NI · [L1798–1799](verification-maximal-os.md#L1798)

**R-16-013** MUST — A fault raises a bounded, authenticated crash record through the sentinel telemetry monitor: fault class, faulting capability and program counter, compartment identity, the ECC or tag-trap cause, and a sealed input trace — schema-bounded like any §5 wire format, never free-form text.
· Accept: the record's schema is a Narcissus descriptor.
· Trace: CJ-FORMAT · [L1800](verification-maximal-os.md#L1800)

**R-16-014** IS — Because the machine is deterministic, that trace re-runs bit-exact off-device on the same semantics the silicon is proven to refine, so verbosity moves off the device rather than streaming from it at runtime.
· Accept: off-device introspection is unbounded and carries no on-device confidentiality cost.
· Trace: CJ-SAIL, CJ-RTL-SAIL · [L1801](verification-maximal-os.md#L1801)

**R-16-015** IS — Determinism holds *given the inputs and the recorded nondeterminism*, and the second half is enumerated as exactly four sources: every draw from the single entropy root (protocol nonces, IVs, ephemeral key material, blinding factors); the link-layer address draws behind MAC randomization; raw counter reads by holders of the fine-grained-time permission; and the physical event stream the sentinel consumes.
· Accept: the list is closed by amendment to this register; omitted, a replay diverges at the first draw. Clock fuzz left this enumeration when the mechanism was deleted (R-08-031a) — the list shrank rather than acquiring a parameter.
· Trace: CJ-NI · [L1802–1805](verification-maximal-os.md#L1802)

**R-16-016** MUST — Public nondeterminism is recorded verbatim: the drawn link-layer address, counter values, and the sentinel's physical-event stream.
· Accept: each discloses nothing the crash record does not already carry, and replay reproduces them exactly.
· Trace: CJ-NI · [L1806](verification-maximal-os.md#L1806)

**R-16-017** MUST — Secret nondeterminism is recorded as a sealed commitment and never as a value: the trace carries a hash over the draw, sealed to the RoT, and off-device replay substitutes its own entropy.
· Accept: writing DRBG seeds or draws verbatim would place live key material into an artifact designed to leave the device.
· Trace: CJ-CRYPTO-SPEC, CJ-NI · [L1807](verification-maximal-os.md#L1807)

**R-16-018** IS — Substitution is sound because the crypto is constant-time, not because the values are unimportant: every secret-touching binary is CT-verified, so its control flow and memory-access sequence are secret-independent by construction and a substituted draw reproduces the same instruction sequence, addresses, capability operations, and fault.
· Accept: the soundness of this clause is exactly as broad as the CT obligation's scope. **See [D-04](#d-04).**
· Trace: CJ-CT-SOUND · [L1808](verification-maximal-os.md#L1808)

**R-16-019** IS — The bit-exact claim is precise rather than weakened: replay is exact in control flow, capability operations, schedule, and fault reproduction everywhere, and exact in *values* everywhere outside the secret-entropy cone.
· Accept: the two scopes are stated separately.
· Trace: CJ-CT-SOUND · [L1809](verification-maximal-os.md#L1809)

**R-16-020** MUST — Where a fault turns on one specific draw, the commitment lets a candidate value be checked rather than guessed, and unsealing the actual draw is a powerbox-mediated declassification gated behind the RoT lifecycle debug state.
· Accept: unsealing is never a property of the ordinary crash record.
· Trace: CJ-NI, CJ-DEVTREE · [L1810](verification-maximal-os.md#L1810)

**R-16-021** MUST — On-device verbose detail, where genuinely needed, is a capability-scoped, confidentiality-labeled diagnostic sink gated behind RoT lifecycle state and fused off in production, so a dump crossing a confidentiality domain is a powerbox-mediated declassification and never an ambient spew.
· Accept: the gate is the same one debug and trace receive (R-15-078).
· Trace: CJ-NI · [L1811](verification-maximal-os.md#L1811)

**R-16-022** IS — A crash record leaving the device carries the sealed trace against the reproducible base image's signed root, not a secret payload, so the fault reproduces for anyone without disclosing user data — at the cost, booked in §17, that a draw-dependent fault is not reproducible from the exported record alone.
· Accept: the two-class entropy record is what keeps this true.
· Trace: CJ-NI · [L1812](verification-maximal-os.md#L1812)

---

## §17 — Residual Risks

*§17 is a register of ceilings rather than obligations. Its entries are therefore mostly `IS` — each states a residual that must remain **stated**, and its acceptance criterion is that the residual is booked with its owner and scope rather than absorbed into a guarantee. A §17 entry silently dropped from a future revision is a spec defect in the same sense R-05-153 defines.*

### 17.1 The index

**R-17-001** IS — Residuals are grouped by trust source in an index table: proof gap (deferred, not assumed), spec gap (crown jewels), physical/fab gap, human consent, hardness assumption, and commercial acceptance.
· Accept: every §17 entry belongs to exactly one group, and every group's listed residuals have entries below.
· Trace: CJ-T · [L1818–1827](verification-maximal-os.md#L1818)

### 17.2 Timing and scheduling

**R-17-002** IS — The transient-execution, branch-predictor-state, LR/SC reservation-granule, DVFS/frequency, cross-domain coherence-traffic, and scheduler/slack channel classes are each *deleted* by a named construction rather than mitigated; the rest are narrowed by partitioning, `fence.t`, eager zeroize, gated clock resolution, and the fixed-latency timing mandates.
· Accept: each deletion names the construction that achieves it; no general timing guarantee is claimed, and budget/partition granularity scales with assurance tier.
· Trace: CJ-ISOL, CJ-LEAK · [L1829–1831](verification-maximal-os.md#L1829)

**R-17-003** IS — The NI ⋈ timing seam's residual is the composition proof itself, plus any channel below partitioning granularity.
· Accept: statically-predicted wrong-path fetch reads flat SRAM at fixed latency with no I-cache, so that residual footprint is deleted rather than partitioned.
· Trace: CJ-NI, CJ-ISOL · [L1832–1833](verification-maximal-os.md#L1832)

**R-17-004** IS — The population wall: a non-work-conserving frame divides rather than shares, so discretionary capacity is divided among live compartments and no scheduling work recovers the difference.
· Accept: the §11 population rungs change the *shape* of the division, not the fact of it.
· Trace: CJ-WCET · [L1834–1836](verification-maximal-os.md#L1834)

**R-17-005** IS — Cost (1): background share collapses as roughly 1/n and the absolute numbers are small — on the reference instantiation a background origin at the 32-rung holds on the order of one percent of one core, around four percent at the 8-rung. The foreground is fast and the background very nearly stopped.
· Accept: this is a materially different performance *shape* from a work-conserving machine that is merely slower, and it is stated as the shape to plan against.
· Trace: CJ-WCET · [L1837](verification-maximal-os.md#L1837)

**R-17-006** IS — Cost (2): idle discretionary time is structurally unreclaimable and will remain so, because the donation mechanism that would reclaim it *is* the channel whose deletion the design is buying.
· Accept: the mixed-load figure in the performance companion scores idle-slot waste at low population and does not cover this; past a few discretionary compartments per core the division dominates.
· Trace: CJ-WCET, CJ-NI · [L1838](verification-maximal-os.md#L1838)

**R-17-007** IS — Cost (3): the rung index is a residual channel — every discretionary compartment reads its own slot width, hence the rung, hence a log-coarse count of live discretionary compartments, and the focus permutation timestamps focus changes to the unfocused.
· Accept: both are user-originated, the state space is a handful of rungs, and the rate is bounded by human lifecycle actions, so it is a coarse low-bandwidth channel an origin can observe but not clock — a channel nonetheless, and the price of not making a tab an attested global transition.
· Trace: CJ-NI · [L1839](verification-maximal-os.md#L1839)

**R-17-008** IS — The product-level statement belongs beside the §1 throughput trade rather than behind it: this is a few-active-things machine, retaining deep tab and app sets as state while running a small number at a time.
· Accept: the statement appears in the goals-adjacent material, not only here.
· Trace: CJ-WCET · [L1840](verification-maximal-os.md#L1840)

### 17.3 Consent

**R-17-009** IS — For system-fixed flows the §8 theorem is absolute non-interference; for user-authorized flows it is non-interference *modulo* robust, delimited declassification, and that qualifier is where the ceiling sits.
· Accept: the release is delimited and robust, so the dominant real-world path is inside the proof rather than near-vacuously admitted or left outside it.
· Trace: CJ-NI · [L1841–1843](verification-maximal-os.md#L1841)

**R-17-010** IS — Cost (1): the consent TCB genuinely grows — the powerbox, the trusted-path agent, and the RoT secure-attention indicator are small and verified but genuinely trusted, against the delete-rather-than-defend grain, accepted for want of a way to gate authority-crossing consent without some trusted mediator.
· Accept: its input edge is bounded by RoT-latched front-end ownership, so the addition is a fixed threshold-and-centroid reducer plus a latched register rather than a programmable touch DSP — the smallest available closure, but an addition, and one shifting a share of consent-path integrity onto the RoT.
· Trace: CJ-NI, CJ-DEVTREE · [L1844–1845](verification-maximal-os.md#L1844)

**R-17-011** IS — The temporal scope of a grant is bounded, not evaluated: *while-active* stays strictly weaker than one-shot, a compromised compositor colluding with a compromised app retaining a sensitive grant up to the ceiling — bounded and physically legible rather than unbounded and silent, but retained.
· Accept: consistent with R-08-043.
· Trace: CJ-NI · [L1846](verification-maximal-os.md#L1846)

**R-17-012** IS — Cost (2): the delimited-release bound and the robust-declassification statement are new crown-jewel specs — a release bound letting the powerbox mint wider than the user named verifies perfectly and leaks.
· Accept: both appear in the crown-jewel inventory.
· Trace: CJ-NI · [L1847](verification-maximal-os.md#L1847)

**R-17-013** IS — Cost (3): the user is outside the theorem. An unspoofable, attested, correctly-bounded prompt still rests on the human granting the right authority; *the user consented to the wrong thing* is the irreducible ceiling no proof reaches.
· Accept: no claim elsewhere in the specification implies otherwise.
· Trace: CJ-NI · [L1848](verification-maximal-os.md#L1848)

### 17.4 Proof-gap residuals

**R-17-014** IS — The non-interference theorem is fresh — seL4-NI in method, not maturity — with three dimensions none of seL4's proof reaches: the multikernel composition, the purecap CHERI-C semantics, and robust delimited declassification.
· Accept: booked as freshness, not trust; its silent failure mode, a too-weak-but-faithful NI specification, is the crown-jewel risk the security-policy model already carries.
· Trace: CJ-NI · [L1849–1853](verification-maximal-os.md#L1849)

**R-17-015** IS — Deterministic replay is bit-exact modulo the secret-entropy cone, with two booked limits: a fault turning on one specific secret draw does not reproduce from the exported record alone, and the soundness of entropy substitution rests on the constant-time property rather than on anything replay establishes.
· Accept: replay is a *consumer* of the CT residual rather than an independent guarantee. **See [D-04](#d-04).**
· Trace: CJ-CT-SOUND · [L1854–1858](verification-maximal-os.md#L1854)

**R-17-016** IS — Specification gap: proofs match the spec, never intent. The crown-jewel spec set is enumerated — policy model, IDL wire-format mapping, frozen matrix-extension semantics, NoC/island isolation model, the bank/macro/tier→island binding map, the native tag-bit layout, the memory controller's non-interference semantics, radio grammars, OPP/mode schedule statements, the frozen ISA-profile definition, the `Zkt`/`Zvkt` leakage-model statement, the Ztso and static-prediction fetch statements, the `fence.t` flush-set statement, the reset/power sequence table, and the calibration-manifest schema.
· Accept: the list is closed by amendment to this register, and every crown jewel here has a `CJ-` trace target used by the sections that constrain it.
· Trace: CJ-T · [L1859–1862](verification-maximal-os.md#L1859)

### 17.5 The hardware seam register

**R-17-017** MUST — The hardware seams are a named register with owners rather than an emergent property, and a future mechanism's admission review walks this list *before* the five-part admission test's clauses, because at this design's maturity a gap is a seam, not a subsystem.
· Accept: a mechanism admitted alone is not admitted until its meetings are; the register below is the standing companion the five-part test lacked.
· Trace: CJ-T · [L1863](verification-maximal-os.md#L1863), [L1865](verification-maximal-os.md#L1865)

**R-17-018** IS — Seam: **interrupts ⋈ the cyclic executive**, dissolved rather than reconciled — asynchronous delivery deleted, arrival latched state read by ordinary loads, the slot-boundary timer the sole asynchronous trap, service latency a schedule corollary, the residual a watchdog bark noticed at slot rather than trap latency.
· Accept: discharged by R-07-038 through R-07-047 and R-16-006.
· Trace: CJ-KERNEL · [L1864](verification-maximal-os.md#L1864)

**R-17-019** IS — Seam: **`fence.t` ⋈ the state inventory** — the architectural / partition-owned / flushed trichotomy discharged against the RTL, the store buffer alone in the flushed class and the register files in the context-switched class under the kernel's total restore.
· Accept: discharged by R-15-213 through R-15-217 and R-07-015. **See [D-07](#d-07).**
· Trace: CJ-ISOL, CJ-RTL-SAIL · [L1864](verification-maximal-os.md#L1864)

**R-17-020** IS — Seam: **the memory path ⋈ power gating**, dissolved rather than reconciled — the memory path holds no key, counter, or root register, so nothing must stay powered across standby to preserve an invariant.
· Accept: discharged by R-15-191 and R-15-199.
· Trace: CJ-ISOL · [L1864](verification-maximal-os.md#L1864)

**R-17-021** IS — Seam: **scanout ⋈ the TDM fabric** — a standing admitted reservation, underrun a §16 fault class, the scanned line crossing no cryptographic stage.
· Accept: discharged by R-11-008, R-15-230, and R-16-004.
· Trace: CJ-WCET · [L1864](verification-maximal-os.md#L1864)

**R-17-022** IS — Seam: **the memory tiers ⋈ inspectability** — graded on one die, the logic tier imaged and the passive upper tiers un-imaged but incapable of execution.
· Accept: discharged by R-15-160, R-15-161, and R-17-061.
· Trace: CJ-T · [L1864](verification-maximal-os.md#L1864)

**R-17-023** IS — Seam: **revocation ⋈ the schedule** — containment is the epoch flip, the sweep a sized background slot class.
· Accept: discharged by R-08-006, R-08-007, and R-11-008.
· Trace: CJ-CERISE, CJ-WCET · [L1864](verification-maximal-os.md#L1864)

**R-17-024** IS — Seam: **the write path ⋈ the ECC and tag planes** — no sub-granule fabric write exists.
· Accept: discharged by R-15-181 through R-15-183. **See [D-09](#d-09).**
· Trace: CJ-SAIL · [L1864](verification-maximal-os.md#L1864)

**R-17-025** IS — Seam: **clock domains ⋈ determinism** — mesochronous by construction, with three asynchronous boundaries terminated and unmodeled.
· Accept: discharged by R-15-195 through R-15-197.
· Trace: CJ-WCET · [L1864](verification-maximal-os.md#L1864)

**R-17-026** IS — Seam: **boot ⋈ storage** — stage zero named: ROM, OTP, fixed-address NAND, no grammar.
· Accept: discharged by R-09-003 through R-09-006.
· Trace: CJ-DEVTREE · [L1864](verification-maximal-os.md#L1864)

**R-17-027** IS — Seam: **calibration ⋈ attestation** — factory-measured, signed, envelope-bounded.
· Accept: discharged by R-15-126, R-15-127, and R-17-062.
· Trace: CJ-DEVTREE · [L1864](verification-maximal-os.md#L1864)

**R-17-028** IS — Seam: **inspectability ⋈ density** — IRIS scoped to the logic die, the memory stack checked at runtime instead.
· Accept: discharged by R-15-160 and R-15-161.
· Trace: CJ-T · [L1864](verification-maximal-os.md#L1864)

**R-17-029** IS — Seam: **debug ⋈ lifecycle** — electrically fused absent in production, an RTL ⊑ Sail obligation.
· Accept: discharged by R-15-078 and R-15-079.
· Trace: CJ-RTL-SAIL · [L1864](verification-maximal-os.md#L1864)

**R-17-030** IS — Seam: **eUICC ⋈ the platform** — a synchronous host-clocked interface block, its foreign grammar behind a verified parser.
· Accept: discharged by R-12-045 through R-12-047.
· Trace: CJ-FORMAT · [L1864](verification-maximal-os.md#L1864)

### 17.6 Admission and tooling seams

**R-17-031** IS — The compilation ⋈ robust-safety seam is closed at a price: the robust-preservation theorem is a heavier obligation than plain compiler correctness.
· Accept: discharged by R-05-024.
· Trace: CJ-SECOMP · [L1866–1867](verification-maximal-os.md#L1866)

**R-17-032** IS — The admission tradeoff is one-directional: raising the Tier-2 floor trades away *hardware bounds arbitrary unverified code* for deleting intra-compartment memory-unsafety as a bug class; containment is unchanged and only the admitted set narrows.
· Accept: the universal contract is retained beneath the certificate.
· Trace: CJ-TAL-SOUND · [L1868–1870](verification-maximal-os.md#L1868)

**R-17-033** IS — The certifying compiler's preservation theorem is off the trust path — a completeness property, not a soundness one: a buggy or adversarial certifying compiler can only fail to emit a valid derivation for a safe program, which is an availability failure, never a safety breach.
· Accept: the theorem ships tested-but-unproven and is backfilled as assurance against Radium; there is no interim weakening, so the residual is a *delivery* risk rather than degraded admission.
· Trace: CJ-TAL-SOUND · [L1872–1875](verification-maximal-os.md#L1872)

**R-17-034** IS — The typed callee set is the sharpest instance of that completeness residual: a compiler that cannot enumerate a site emits no derivation and the binary is refused, and cannot mint one that type-checks yet under-declares.
· Accept: the population that resists enumeration is already excluded by no-runtime-codegen; because closure is per-compartment, a mis-stated manifest yields well-typed compartments wired wrong — the crown-jewel-spec failure mode in its usual place.
· Trace: CJ-TAL-SOUND · [L1876–1878](verification-maximal-os.md#L1876)

**R-17-035** IS — The remediation-window seam: containment is fast and needs no proof because it only removes authority, while full remediation stays proof-gated, so the affected functionality runs degraded between the two.
· Accept: the window is budgeted, not hidden, and deliberately preferred over a fast unverified hot-patch.
· Trace: CJ-CERISE · [L1879–1881](verification-maximal-os.md#L1879)

**R-17-036** IS — On-device verbose diagnostics remain an observation capability deliberately confined rather than eliminated, its confinement resting on the lifecycle-state gate and the sink's confidentiality label.
· Accept: discharged by R-16-021.
· Trace: CJ-NI · [L1882–1883](verification-maximal-os.md#L1882)

**R-17-037** IS — The single-mechanism concentration is booked in four parts: in-core spatial isolation rests on CHERI alone with no in-band disjoint backstop; application-class single-address-space purecap is the less battle-tested isolation model; privilege-as-capability is untested at application-class multicore scale; and device access rests on CHERI too, adding in-flight-DMA revocation and a capability/tag-carrying fabric as new obligations.
· Accept: the sole hedge against a CHERI logic fault is out-of-band — CHERI's own formal verification — leaving RTL ⊑ Sail and its Coq-native restatement as the residual, plus the fab residual beneath.
· Trace: CJ-CERISE, CJ-RTL-SAIL · [L1884–1894](verification-maximal-os.md#L1884)

**R-17-038** IS — The admission-checker stratification seam carries six named residuals: the CHERI-TAL soundness metatheorem as a new crown jewel; the net-new temporal-safety type discipline; relevance bounding the drop but never the response; no-ambient-state forbidding re-manufacture but not over-injection; the frozen theory buying the line-budget axiom by spending expressiveness one-directionally; and totalized arithmetic being per-install decidable only where bounds are closed.
· Accept: each is stated with its compensating fact and its scope boundary; least authority stays in the compose-time topology as a crown-jewel policy statement rather than a typing obligation.
· Trace: CJ-TAL-SOUND · [L1895–1916](verification-maximal-os.md#L1895)

**R-17-039** IS — The Sail ⋈ RTL seam is split rather than left as one undifferentiated trust residual: the Coq refinement is the sole unbounded close, the timing and ordering obligations are hyperproperties needing a timing-annotated model, and no such artifact exists at full-application-core scale — the least-built layer of the stack.
· Accept: it grows no privileged trust base; the design-space exploration narrows it at design time rather than merely booking it.
· Trace: CJ-RTL-SAIL · [L1917–1922](verification-maximal-os.md#L1917)

**R-17-040** IS — A fourth residual sits beside the arrow rather than on it: the microarchitectural absences Sail cannot express, booked against the separate absence contract, which also carries the `fence.t` flush-set completeness claim. The residual is not cost but *where it closes* — Kôika-authored blocks close it in-prover, while imported cores close it on a structural audit, not a theorem.
· Accept: the strongest microarchitectural claims about imported cores rest on the evidence tier, not the Coq close.
· Trace: CJ-RTL-SAIL · [L1923–1929](verification-maximal-os.md#L1923)

**R-17-041** IS — The WCET seam carries three residuals: the timing-annotated Sail model's latency *magnitudes* become a crown-jewel spec; WCET inherits the RTL ⊑ Sail residual; and composability without an interference term rests on the isolation model, so WCET soundness and timing-channel deletion share one non-interference proof.
· Accept: MBPTA/EVT stays rejected as the admitted bound and aiT stays the unverified cross-check.
· Trace: CJ-WCET, CJ-RTL-SAIL · [L1930–1937](verification-maximal-os.md#L1930)

**R-17-042** IS — The constant-time coverage seam carries four residuals: CT is typed where it can be and proved where it cannot; a stock compiler does not preserve CT so it is hardened then checked; Binsec/Rel is bounded evidence; and CT inherits the RTL ⊑ Sail residual.
· Accept: scope is a labeling obligation, so a secret reaching an un-CT-verified compartment is a spec or label error the flow theorems must catch, not a tooling gap. **See [D-04](#d-04).**
· Trace: CJ-CT-SOUND · [L1938–1944](verification-maximal-os.md#L1938)

**R-17-043** IS — The verified-storage seam carries six residuals, all of a *verified but contained* stack: freshness rather than trust; L0 re-proved over C rather than ported by a bespoke tool; the AE ⋈ noninterference composition seam; the liveness ⋈ schedulability seam; the dedup keyed-digest interface and its domain-confined equality revelation; and user-data freshness surrendered by design.
· Accept: the stack carries no TCB membership at all, so system integrity rides the small reader and transactor instead.
· Trace: CJ-NI, CJ-REDUCTION · [L1945–1954](verification-maximal-os.md#L1945)

**R-17-044** IS — The synchronous-control-plane seam adds no fresh axiom (Vélus is Coq-verified) and carries two residuals: the Lustre program and the control/data boundary are crown-jewel specs, and the offset is a net shrink — WCET, the memory-safety certificate, and determinism become structural for the control tier.
· Accept: the rare adoption that lowers net tooling.
· Trace: CJ-VELUS · [L1955–1959](verification-maximal-os.md#L1955)

**R-17-045** IS — Definite initialization is carried by the type system alone, with three residual parts: the hedge is genuinely surrendered by decision; device-written memory leaves the derivation into the HAL's contract proofs; and delegated buffers leave it into the IDL and manifest tables.
· Accept: eager-zeroize keeps the *disclosure* consequence closed independently, so the uncaught case is a correctness bug reading zeros rather than a residue leak; the deletion is a net subtraction on every scarce axis.
· Trace: CJ-TAL-SOUND, CJ-HAL · [L1960–1969](verification-maximal-os.md#L1960)

**R-17-046** IS — The proof trust base is enumerated: the two admission checkers, the CHERI-TAL soundness metatheorem, the Sail model, the spec and policy statements, and — as explicitly shrinking interims — F\*/Z3 for PQ primitives and EasyCrypt's Why3/SMT wherever a layer-3 reduction rides it. **See [D-10](#d-10).**
· Accept: the Coq-native crypto path adds no new prover, so those surfaces retire as primitives migrate; the checker's own binary keeps its named bootstrap as the De Bruijn root.
· Trace: CJ-T · [L1970–1974](verification-maximal-os.md#L1970)

**R-17-047** IS — Lean-as-checker is refused as the two-kernel cost and Lean-as-oracle has no mature transport today, so the answer stays Coq-native: a tooling-maturity cost the engineering-free axiom absorbs, not a reason to fork the checker.
· Accept: the single-prover-binds-the-checker rule governs (R-05-016).
· Trace: CJ-T · [L1973](verification-maximal-os.md#L1973)

**R-17-048** IS — The heterogeneous die grows the Sail model along an enumerated list, and the profile's exclusions shrink the decode and state surface along another; the net is modeling-and-verification surface, not new privileged trust.
· Accept: both lists are stated rather than summarized.
· Trace: CJ-SAIL · [L1975–1976](verification-maximal-os.md#L1975)

### 17.7 Crypto, regulatory, and physical ceilings

**R-17-049** IS — Reductions isolate axioms but do not remove them: hardness assumptions (MLWE/MSIS, ECDLP/CDH) are irreducible, and the implementation ⋈ reduction seam joins at the primitive's functional specification, a crown-jewel spec neither side catches.
· Accept: hybrid PQ+classical key exchange is the standing hedge; protocol-level security is a further layer this guarantee does not reach. **See [D-05](#d-05).**
· Trace: CJ-REDUCTION · [L1977–1985](verification-maximal-os.md#L1977)

**R-17-050** IS — The blocking regulatory risk has substantially cleared (FCC's settled SDR position; the EU radio-lockdown delegated act abandoned in January 2026), and the genuine residual is narrow and commercial: carrier, PTCRB, and GCF acceptance of an open cellular UE stack.
· Accept: mitigations are module certification with inheritance, RoT attestation giving stronger version binding than the industry norm, and private-network deployment as the lighter-certification first ring.
· Trace: CJ-DEVTREE · [L1986–1992](verification-maximal-os.md#L1986)

**R-17-051** IS — The 5G/6G-only generation floor narrows deployability, and emergency calling inherits it: emergency reach equals 5G/6G coverage reach, a coverage-for-security trade extended to E911/E112 by decision rather than by silence.
· Accept: the trade is stated in §15, §12, and here.
· Trace: CJ-SAIL · [L1993](verification-maximal-os.md#L1993), [L1999](verification-maximal-os.md#L1999)

**R-17-052** IS — The emergency-calling seam admits an unauthenticated, possibly null-ciphered session — the one place the radio's verified crypto posture is deliberately not in force — contained by non-interference and zero standing authority rather than excepted.
· Accept: it is also the one place a sensitive peripheral is granted at Before First Unlock, and the residual runs the *other* way: the sealed cutoffs are not overridden, because a software override for the emergency case is a software override.
· Trace: CJ-NI · [L1994–1998](verification-maximal-os.md#L1994)

**R-17-053** IS — The wired-link ceiling books two costs: 10GBASE-T and above are declined, and the 1000BASE-T canceller's coefficients are frozen per link epoch, so marginal cable plant re-trains on a link bounce — an availability cost, never an integrity or confidentiality one.
· Accept: discharged by R-15-137 through R-15-139.
· Trace: CJ-ISOL · [L2000–2003](verification-maximal-os.md#L2000)

**R-17-054** IS — The lock-state seam books three limits: at-rest security is bounded by the credential and its rate-limiter; the unlocked window is shortened but not closed; and duress crypto-erase is a countermeasure rather than a guarantee, protecting future recoverability only and being irreversible on accidental entry.
· Accept: biometrics are deliberately excluded from cold or idle-locked key release for exactly the false-accept and presentation-attack reason.
· Trace: CJ-CRYPTO-SPEC · [L2004–2008](verification-maximal-os.md#L2004)

**R-17-055** IS — Hardware-random link-layer addressing is necessary but not sufficient for unlinkability: RF fingerprinting, frame sequence numbers and timing, and higher-layer identifiers each re-link sessions a random address alone would separate; and because framing is SoftMAC the address is inserted by a memory-safe but not functionally-proven compartment.
· Accept: the guarantee is *no persistent identifier, randomness from the platform RNG root* — a privacy floor, not a complete unlinkability proof.
· Trace: CJ-NI · [L2009–2012](verification-maximal-os.md#L2009)

**R-17-056** IS — The USB authentication floor attests identity, not behaviour, and a mandatory floor is a coverage-for-security trade: most deployed peripherals do not implement authentication, so they are charging-only until a deliberate per-device exception, which weakens the floor to a consented prompt wherever the user chooses convenience.
· Accept: runtime containment carries what authentication cannot.
· Trace: CJ-CERISE · [L2013–2016](verification-maximal-os.md#L2013)

**R-17-057** IS — The trusted-time residual is availability, not integrity: a network adversary can deny or stall fresh time but not forge a chosen value, and secure PTP adds one facet — its authentication TLV protects origin and integrity but not the path-symmetry assumption its offset calculation rests on.
· Accept: a just-cold-booted offline device runs time-unknown until Roughtime succeeds; the PTP exposure exists only where PTP is used.
· Trace: CJ-CRYPTO-SPEC · [L2017–2020](verification-maximal-os.md#L2017)

**R-17-058** IS — Physical residuals: Rowhammer is dramatically reduced rather than mitigated; cold boot is countered by SRAM volatility with no encryption involved; power analysis persists at probe level; TEMPEST-class emission is attenuated but not closed against a near-field probe; and macro-internal and sequential-3D thermal coupling are narrowed rather than eliminated.
· Accept: each names the mechanism that narrows it and the scope line that bounds it.
· Trace: CJ-T · [L2021–2033](verification-maximal-os.md#L2021)

**R-17-059** IS — The memory path is defended by the *absence of a surface* rather than by a mechanism, and the residual is the scope line itself: the honest statement is not "replay is undetected" but "the whole class is out of scope, and nothing on the memory path would detect it if it were in scope."
· Accept: there is no defence-in-depth layer beneath the package boundary on the memory path, so the invasive-attack scope line is load-bearing rather than conservative, and if it is ever judged wrong there is no second mechanism behind it. **This is the sharpest instance of *verify rather than hedge* applied to the design's own threat model.**
· Trace: CJ-T · [L2024–2029](verification-maximal-os.md#L2024)

**R-17-060** IS — Silicon supply chain is the largest residual once software is done, and single-die integration concentrates it: one mask set carries the RoT, all core classes, the NoC, the memory path, and the radio.
· Accept: mitigations are open RTL, multi-sourcing, and IRIS backside optical verification, none complete.
· Trace: CJ-T · [L2034–2036](verification-maximal-os.md#L2034)

**R-17-061** IS — IRIS claims evidence for the bottom logic tier — where every structure whose trust is structural lives and the only tier that computes — and does *not* claim it for the upper memory tiers, whose assurance is that they are passive arrays executing nothing, fabricated in the same lot from the same mask set.
· Accept: the honest statement is not "everything is imaged" but "everything that *acts* is imaged, and what is not imaged cannot act."
· Trace: CJ-T · [L2038–2045](verification-maximal-os.md#L2038)

**R-17-062** IS — Per-unit calibration manifests are booked in this residual: measured at the factory rather than reproduced from source, they are the one per-device artifact reproducible builds and DDC cannot cover, so the factory trim step is a named trusted measurement — narrow, but trust nonetheless.
· Accept: bounded in effect by the passive emission envelope and the ECC/fail-stop backstops.
· Trace: CJ-DEVTREE · [L2046](verification-maximal-os.md#L2046)

**R-17-063** IS — The ceiling stays named: IRIS resolves coarser structure far better than the smallest features, it is evidence and not proof, and a fab-level adversary below its resolution remains in scope.
· Accept: none of the three mitigations is complete.
· Trace: CJ-T · [L2047](verification-maximal-os.md#L2047)

### 17.8 The composition obligation

**R-17-064** IS — The residual the whole list rolls up into is the composition meta-lemma: that the capability-safety substrate and the seam lemmas, transported down the refinement tower, entail T.
· Accept: it is the single largest verification deliverable and exists for no system of this scope; the single-prover discipline makes it literal proof composition rather than cross-tool glue, which is what makes it tractable, not what makes it done.
· Trace: CJ-T · [L2048–2051](verification-maximal-os.md#L2048)

**R-17-065** IS — T is true only modulo its stated boundary: the declassification set *D*, the axiom set *Ax*, the hardness conjectures, the die-matches-RTL fabrication gap, specification faithfulness, human consent correctness, and invasive physical attack — each a residual above.
· Accept: the theorem's honesty is that its own statement names them rather than absorbing them silently (R-05-162).
· Trace: CJ-T · [L2052–2053](verification-maximal-os.md#L2052)

---

## §18 — Realization

### 18.1 Constraints and priority

**R-18-001** IS — Silicon is the binding constraint: RV64 application-class CHERI exists only as licensable IP and FPGA soft cores. Codasip's X730 is shipping evidence that application-class purecap silicon is real at sub-5% area cost, but its proprietary RTL enters as a reference and bring-up vehicle, never the trusted base.
· Accept: the RTL of record is authored in a formal-semantics HDL, so even open CVA6-CHERI enters as a functional reference.
· Trace: CJ-RTL-SAIL · [L2059–2060](verification-maximal-os.md#L2059)

**R-18-002** MUST — The platform is purecap-only: there is no non-CHERI host, no capability-degraded interim, and no plain-RV64 compilation target anywhere, so every stage enforces hardware capabilities from first bring-up.
· Accept: both staging phases are purecap and both gate on the CHERI toolchain.
· Trace: CJ-CERISE · [L2061–2062](verification-maximal-os.md#L2061)

**R-18-003** MUST — The certifying compilers are priority zero, built ahead of any emulator, FPGA, or silicon work, because nothing runs a line of the system until they exist.
· Accept: the toolchain workstream precedes all hardware workstreams in the schedule.
· Trace: CJ-COMPCERT, CJ-TAL-SOUND · [L2063](verification-maximal-os.md#L2063)

**R-18-004** IS — First release is scoped to prove the thesis, not complete the roster: Wi-Fi-only, deferring the eUICC, cellular certification, the HARQ hard-real-time class, and the 5G-AKA key hierarchy; the browser is likewise deferred as the largest porting program.
· Accept: neither is a design cut — full cellular and the browser remain in the specification, sequenced behind the smaller surface that proves the core claims.
· Trace: CJ-T · [L2065–2068](verification-maximal-os.md#L2065)

**R-18-005** IS — The heterogeneous die is staged class by class: C-class + RVV under CHERI → V-class → M-class → FEC units → islands and TDM NoC → capability-checked DMA engines and the capability/tag-carrying fabric.
· Accept: open RTL exists per class, but CHERI-purecap extension of each is new RTL and Sail work.
· Trace: CJ-RTL-SAIL · [L2070–2072](verification-maximal-os.md#L2070)

**R-18-006** MUST — The frozen instruction-set profile is part of the platform definition from the first FPGA bring-up: Ztso, static-only branch prediction, and Machine-mode-only are bring-up properties, not later additions.
· Accept: the CVA6-class front end is modified to static prediction and the store buffer proven TSO-exposing as part of first bring-up, alongside the `Zkt`/`Zvkt` obligation.
· Trace: CJ-SAIL, CJ-RTL-SAIL · [L2073](verification-maximal-os.md#L2073)

**R-18-007** IS — The memory path is the first thing built and the smallest it can be: a granule read-modify-write stage, an ECC encode-and-check stage, the bank/macro/tier decode, and no cryptography of any kind.
· Accept: this matters disproportionately because every block deleted here is one that would have had to be authored in Kôika and proven against Sail from nothing.
· Trace: CJ-RTL-SAIL · [L2075–2077](verification-maximal-os.md#L2075)

**R-18-008** IS — The one sequential-3D dependency is a manufacturing risk, not a design one: if tier count under-delivers, capacity bends and the mechanism does not, the bonded-stack and chiplet alternatives being declined on trust grounds that a schedule pressure does not revisit.
· Accept: consistent with R-15-173.
· Trace: CJ-DEVTREE · [L2079–2080](verification-maximal-os.md#L2079)

**R-18-009** IS — Two memory-path questions are named as open and explicitly *not* specified: a statically-placed instruction scratchpad (whose remaining motivation is port contention alone), and sequential consistency in place of Ztso (whose reach is narrower than it looks — `fence.t` and the `A` extension both survive it).
· Accept: each is open because the timing budget makes it worth revisiting, not because a change is pending; Ztso and the shared fetch path are what the specification states.
· Trace: CJ-SAIL · [L2082–2095](verification-maximal-os.md#L2082)

### 18.2 RTL-against-Sail

**R-18-010** MUST — RTL ⊑ Sail is a first-class workstream staged with the die and is the least-built layer of the stack: no full application-class core, and *a fortiori* no heterogeneous multi-class die, has been proven to refine its Sail model.
· Accept: the staging is rvfi first, then Sail-generated SystemVerilog plus commercial FEV, then Isla-generated obligations, then the Kami/Kôika Coq refinement as the closing goal.
· Trace: CJ-RTL-SAIL · [L2097–2099](verification-maximal-os.md#L2097)

**R-18-011** IS — The timing and ordering hyperproperties ride a timing-annotated model and are the hardest sub-goal: functional refinement alone does not establish them.
· Accept: consistent with R-15-095.
· Trace: CJ-RTL-SAIL, CJ-LEAK · [L2100](verification-maximal-os.md#L2100)

**R-18-012** IS — The microarchitectural absence contract is a separate gate on this workstream rather than a stage of it, and it inverts the difficulty: it is buildable on day one and cheap, which is the whole argument for preferring removal to partitioning.
· Accept: it is the one part of the least-built layer that does not need the layer to exist first; its honest ceiling is that the imported-core half closes on audit, not theorem.
· Trace: CJ-RTL-SAIL · [L2101–2104](verification-maximal-os.md#L2101)

**R-18-013** IS — RTL ⊑ Sail degrades gracefully, unlike the certifying compilers: rvfi and Isla obligations ship long before the Coq refinement closes, so base bring-up is not blocked on the full proof — only the *unbounded* claim is.
· Accept: the disposition is stated per workstream rather than uniformly.
· Trace: CJ-RTL-SAIL · [L2105](verification-maximal-os.md#L2105)

### 18.3 The toolchain

**R-18-014** MUST — Two certifying compilers gate the platform: the CHERI-CompCert backend for the TCB, and a certifying Rust→RV64+CHERI compiler emitting per-binary memory-safety certificates.
· Accept: the first re-homes SECOMP2CHERI and completes its robust-preservation theorem rather than authoring a capability backend fresh; the second is genuinely net-new and explicitly in scope.
· Trace: CJ-COMPCERT, CJ-SECOMP · [L2107–2109](verification-maximal-os.md#L2107)

**R-18-015** IS — The certifying Rust compiler's shape is a front end over safe-Rust MIR carrying the source type system's memory-safety fact through lowering and emitting a CHERI-TAL derivation; CHERI discharges spatial safety, so the preserved obligation is the temporal-safety and typed-control-flow residual.
· Accept: no per-app manual proof is required for pure-safe-Rust code.
· Trace: CJ-TAL-SOUND · [L2110](verification-maximal-os.md#L2110)

**R-18-016** MUST — Relevance grading is the one obligation the front end cannot lift from the source type system, so the fallible-result types of the kernel ABI, the IDL, and the attestation and storage interfaces are declared relevance-graded *at their definition* and the front end propagates from there.
· Accept: the net-new work sits at the interface definitions rather than at every call site.
· Trace: CJ-TAL-SOUND, CJ-IDL · [L2111](verification-maximal-os.md#L2111)

**R-18-017** MUST — The derivation is emitted by hinted mirroring: the untrusted compiler records hints through lowering and a small trusted Coq replayer reconstructs the typing derivation the on-device checker re-validates.
· Accept: the certifier is a small replayer plus an untrusted producer rather than a whole-compiler preservation megaproof — the concrete reason the preservation theorem sits off the trust path.
· Trace: CJ-TAL-SOUND · [L2112](verification-maximal-os.md#L2112)

**R-18-018** IS — The toolchain sub-deliverables are enumerated: (a) the lowering emitting the TAL derivation, with its preservation statement a completeness property backfilled as assurance against Radium; (b) the CHERI-TAL and its soundness metatheorem, its type theory frozen to the §5 budget so the line budget and metatheorem size are consequences rather than targets; (c) integration with the on-device checker and oracle-compressed proof shipping; (d) the manual-proof escape hatch for HAL-adjacent `unsafe`, foundationally grounded via VerusBelt, plus a gate refusing app `unsafe` outside it.
· Accept: all four appear in the workstream list.
· Trace: CJ-TAL-SOUND, CJ-HAL · [L2113](verification-maximal-os.md#L2113)

**R-18-019** MUST — A bug-finding oracle rides alongside the certifier and never as a second checker: Soteria-rust over the same MIR hunts UB in the HAL-adjacent `unsafe`, and the same framework instantiates for C to bug-find the CompCert/VST path.
· Accept: a Soteria finding shifts a bug left of admission rather than ever carrying it; the memory-safety obligation is discharged by CHERI ⋈ the TAL metatheorem regardless.
· Trace: CJ-TAL-SOUND · [L2114](verification-maximal-os.md#L2114)

**R-18-020** IS — A producer of TAL derivations is a hard prerequisite with no trusted-toolchain fallback: no userspace app is built or admitted until the producer and the on-device checker exist, while the preservation proof is deliberately off that critical path.
· Accept: Cranelift with Crocus-verified lowerings is an SMT-trust reference point informing the lowering proofs, never the shipped certifier and never an admission path — of which there is none.
· Trace: CJ-TAL-SOUND · [L2116–2118](verification-maximal-os.md#L2116)

### 18.4 Crypto, WCET, storage, radio, memory

**R-18-021** MUST — Crypto verification carries exactly three deliverables and no codegen deliverable: layer-3 reduction proofs authored Coq-native in SSProve/FCF; the composition linking reductions to implementations at each primitive's functional specification; and constant-time verification for every secret-touching binary.
· Accept: the standalone CT verifier folds into the certifying-compiler/TAL workstream rather than being net-new, degrading gracefully with Binsec/Rel carrying bring-up.
· Trace: CJ-REDUCTION, CJ-CT-SOUND · [L2120–2121](verification-maximal-os.md#L2120)

**R-18-022** MUST NOT — The fourth deliverable an earlier revision carried, the CryptOpt-style translation-validation toolchain, is deleted rather than deferred, because its whole yield was speed on an already-sound path.
· Accept: deleting it retires a net-new Coq equivalence-checker development, the checker-admitted-artifacts TCB category, and this workstream, at the price of hand-assembly-grade ECC throughput.
· Trace: CJ-CRYPTO-SPEC · [L2122–2124](verification-maximal-os.md#L2122)

**R-18-023** IS — The formosa-crypto ML-KEM effort is the existence proof for what remains, so the reduction and composition deliverables are a Coq-native restatement of finished work rather than a from-scratch research program; an EasyCrypt reduction is admissible interim assurance exactly as libcrux/HACL\* is.
· Accept: the SSProve/FCF restatement is the trust-base-minimizing follow-through, not a boot blocker.
· Trace: CJ-REDUCTION · [L2125–2126](verification-maximal-os.md#L2125)

**R-18-024** MUST — WCET derivation folds into the certifying toolchain rather than a standalone estimator, with three sub-deliverables: the per-instruction latency table as a projection of the timing-annotated Sail model; the tree-sum cost annotation and loop-bound discharge integrated into the toolchain; and integration with the on-device checker.
· Accept: the standalone Coq-verified IPET estimator is retired as a workstream.
· Trace: CJ-WCET · [L2128–2131](verification-maximal-os.md#L2128)

**R-18-025** IS — WCET staging is gated behind the timing-annotated Sail model and thus per-class RTL bring-up, degrading gracefully: there is no *sound* §11 admission until the timing-annotated model lands for the core class, but the deriver is a cost-annotation pass rather than a separate verified estimator.
· Accept: aiT and Heptane stay unverified out-of-band cross-checks that flag a wrong timing annotation, never the bound.
· Trace: CJ-WCET, CJ-RTL-SAIL · [L2132–2133](verification-maximal-os.md#L2132)

**R-18-026** MUST — The verified filesystem carries four deliverables: L0 re-expressed in Gallina and verified over CompCert-C with VST/Iris; the VeriBetrFS B^ε-tree design re-proved in Coq/Iris; the L2 semantics with RefFS-style linearizability, crash, and liveness specs; and the L3 data-noninterference proof composed with the AEAD reduction.
· Accept: no bespoke Goose-to-C extractor is built; Yggdrasil and FSCQ are retained as cross-check and lineage, not bases.
· Trace: CJ-T · [L2135–2139](verification-maximal-os.md#L2135)

**R-18-027** MUST — Storage staging puts the small system-integrity reader and A/B transactor — the only storage TCB — on the critical path, with the four-layer filesystem following and below-the-line block services running availability-only from the start.
· Accept: the ordering reflects TCB membership, not layer count.
· Trace: CJ-DEVTREE · [L2140](verification-maximal-os.md#L2140)

**R-18-028** IS — Radio staging does not wait for integration: an off-die register-slave SDR transceiver behind a certified analog front end gives the identical architecture today, with on-die RF later buying only physical and interface simplification.
· Accept: srsRAN/OpenAirInterface, openwifi, GNSS-SDR, and aff3ct anchor feasibility; openwifi's open-RTL low-MAC is the harvestable existence proof for the fixed-function link-layer timing sequencer.
· Trace: CJ-SAIL · [L2142–2146](verification-maximal-os.md#L2142)

**R-18-029** MUST — The radio parsers are generated, not hand-transcribed: a verified ASN.1 → Narcissus front end over the published 3GPP modules, with the IEI/TLV 5G-NAS grammar hand-written and differential-tested against four independent references.
· Accept: the crown-jewel grammar spec shrinks to one reusable oracle-checked codec rather than thousands of hand-copied pages (R-05-048, R-05-050).
· Trace: CJ-FORMAT · [L2144](verification-maximal-os.md#L2144)

**R-18-030** IS — Memory staging is capacity-limited, not availability-limited: first parts are planar single-tier at order 1–2 GB, with the 4–8 GB phone envelope arriving as sequential-3D tier counts reach 8–16.
· Accept: the interim is less capacity and a leaner roster, never a different mechanism; no deleted DRAM machinery returns, and neither bonded die-stacking nor an SRAM chiplet is held in reserve.
· Trace: CJ-DEVTREE · [L2147–2150](verification-maximal-os.md#L2147)

### 18.5 The capstone

**R-18-031** MUST — The end-to-end composition proof is the capstone workstream, staged last because it consumes the others, with three sub-deliverables: the machine-checked *statement* of T and each seam lemma with interfaces aligned; the linking theorem discharged incrementally; and the boundary ledger of *D* and *Ax* maintained as an enumerated, reviewed artifact.
· Accept: sub-deliverable (a) is engineering-free and authored *now*, ahead of the proofs it will link, doubling as the coverage checklist.
· Trace: CJ-T · [L2152–2154](verification-maximal-os.md#L2152)

**R-18-032** IS — Like RTL ⊑ Sail this is a hard, currently-nonexistent deliverable for the strong form of G3, but its *statement* is available immediately and is the higher-value half: it turns "a dozen things are proven" into "the conjunction claims exactly this, and rests on exactly that" — the review artifact the crown-jewel gate most needs.
· Accept: CompCert ⋈ CertiKOS layered refinement, DeepSpec, and seL4's own integration are the methodological anchors; none is at this scope, which is why the linking theorem is the deepest outstanding proof.
· Trace: CJ-T · [L2155–2156](verification-maximal-os.md#L2155)

**R-18-033** MUST — Two requirements never trade: the verified TCB, and capabilities as the sole authority. Everything else — ship date, core counts, radio bandwidth, acceleration — bends around them.
· Accept: any proposed change is checked against these two first.
· Trace: CJ-T, CJ-CERISE · [L2158–2159](verification-maximal-os.md#L2158)

---

## Coverage

All eighteen normative sections are extracted, at 901 requirements. §19 is non-normative and yields none. Section coverage is a precondition for the R-05-150 gate, not the gate itself: the review still has to decide, per section, whether the extraction is *complete* — which is the question the register exists to make askable.

| Section | Status | Entries |
| --- | --- | --- |
| **§1 Goals** | **extracted** | **6** |
| **§2 Non-Goals** | **extracted** | **7** |
| **§3 Threat Model** | **extracted** | **5** |
| **§4 Organizing Principle** | **extracted** | **12** |
| **§5 Languages & Verification** | **extracted** | **162** |
| **§6 Trusted Computing Base** | **extracted** | **27** |
| **§7 Kernel** | **extracted** | **52** |
| **§8 Authority Model** | **extracted** | **44** |
| **§9 Boot & Root of Trust** | **extracted** | **31** |
| **§10 Storage & State** | **extracted** | **34** |
| **§11 Updates** | **extracted** | **27** |
| **§12 System Servers** | **extracted** | **86** |
| **§13 Packaging & Supply Chain** | **extracted** | **29** |
| **§14 Userland** | **extracted** | **13** |
| **§15 Hardware Platform** | **extracted** | **246** |
| **§16 Reliability** | **extracted** | **22** |
| **§17 Residual Risks** | **extracted** | **65** |
| **§18 Realization** | **extracted** | **33** |

§19 is non-normative and yields no requirements.

## Extraction defects

Normative claims that resisted atomic restatement, per R-05-153. Each is a spec defect to be repaired in [verification-maximal-os.md](verification-maximal-os.md), not a register omission.

**Status: all eleven repaired.** Nine were editorial — the specification already meant the repaired thing and had said it inconsistently, so none changed a mechanism. Two needed a decision, and both were resolved by *deleting* rather than specifying:

- **D-01** is closed by one generic rule in §5 rather than five per-entry forecasts: an interim retires when its Coq-native destination has passed admission for every consumer riding the interim. Testable today against two lists.
- **D-11** is closed by **deleting the fuzzed clock**, not specifying it. Jitter on a counter is recoverable by averaging, which makes it a statistical mitigation of exactly the kind §15 already refuses when it excludes MTE ("a statistic, not a theorem") and MBPTA/EVT. Specifying a distribution would have made a statistic normative in a document that admits none. What replaces it was already true: with the counters permission-gated, an untrusted compartment's only time source is a ring-serviced call, so its finest observable interval is its own slot period — a composition-time constant. The mechanism, its owner question, its distribution parameter, and its entry in §16's nondeterminism enumeration all leave together; the residual is the §11 rung channel already booked at R-17-007.

Entries below are retained with their original diagnosis so the review record shows what was wrong and why.

<a id="d-01"></a>**D-01 — The interim-anchor retirement conditions are asserted, not enumerated.**
[L212](verification-maximal-os.md#L212) states that each interim non-Coq anchor "carries a Coq-native destination and a retirement," but no interim's retirement *condition* is written down. R-05-022's acceptance criterion is therefore unfalsifiable as the spec stands: a reviewer cannot decide whether libcrux/HACL\*'s retirement is met without a stated condition. **Repaired** by one generic rule in §5 rather than five per-entry forecasts: an interim retires when its named Coq-native destination has passed admission for every consumer that currently rides the interim, and is struck from the trust-base inventory in that same generation. *Retired* is then decided by inspecting two lists rather than by judgment, and an interim whose consumer set grows while its destination does not is a review-gate finding (R-05-022a) — which makes §17's *shrinking-interim* claim measurable instead of asserted.

<a id="d-02"></a>**D-02 — The order-of-10³-line checker budget has no measurement rule.**
[L362–365](verification-maximal-os.md#L362) makes the line budget a *consequence* of the checker being an attribute-grammar evaluator, which is the right move, but the budget is still stated in lines and nothing says what is counted: the evaluator alone, or the attribute tables, the type-constructor vocabulary, the derivation parser, and the image scanner too. R-05-127's acceptance criterion tests the category fact, which is checkable; the line count is not. **Repair:** either state the counting rule, or drop the line figure and let the category fact carry the claim alone.

<a id="d-03"></a>**D-03 — The ten type-level obligations and the three-move partition do not have the same membership.**
[L224](verification-maximal-os.md#L224) enumerates ten obligations; the move table at [L237–239](verification-maximal-os.md#L237) partitions them across the three moves but lists **callee-set enumeration** as a move-II obligation, and it is not among the ten. (Memory safety splitting into spatial under move I and temporal under move II is consistent, and is not the discrepancy.) Either the list is eleven, or the callee set is a sub-obligation of CFI and should say so.

A **third** list makes the mismatch worse. §6's checker table ([L442](verification-maximal-os.md#L442)) enumerates what the TAL type-checker decides as "Tier-2 memory safety, CFI, no-codegen, ABI/type conformance, relevance-graded verdicts, no ambient tagged static capability, representation/provenance absences, closed-numeral overflow side conditions, and the memory/ABI half of Tier 1" — which **omits definite initialization, constant-time, and WCET**, all three of which §5 assigns to move II as per-install decidable, and §13 requires definite initialization in the Tier-2 certificate ([L1003](verification-maximal-os.md#L1003)). §6's CIC row saying "*residual unstructured* constant-time and WCET cases" confirms the structured ones are meant to be the checker's, so the omission is an incomplete list rather than a narrower claim. R-05-029 (ten), R-05-038 (seven for move II), R-06-009 (nine), and R-13-012 (six) are four enumerations of overlapping sets, and no two agree. **Repair:** state the obligation list once, normatively, and have §6's and §13's tables cite it rather than restate it.

<a id="d-04"></a>**D-04 — The constant-time obligation has two incompatible scopes.**
[L265](verification-maximal-os.md#L265) states CT is verified "for *every* secret-touching artifact, the crypto core included" — a property of the artifact. [L278](verification-maximal-os.md#L278) scopes the obligation to "secret-touching compartments (those receiving secret-labeled material over an IDL confidentiality channel)". The second is narrower than the first and misses secrets that are not *received over IDL*.

**Extracting §12 and §13 confirms this is a real hole, not a wording slip.** §12 defines the labeling that makes *secret-labeled* meaningful — flow annotations carried on IDL types for cross-domain channels ([L825](verification-maximal-os.md#L825)) — and §13's Tier-1 row explicitly names "key-schedule, **PIN**, session-key, and radio-key paths" as carrying the constant-time obligation ([L1002](verification-maximal-os.md#L1002)). But the PIN does not arrive over an IDL channel. It reaches the credential and unlock service as raw frames from a register-slave AFE over a capability-bounded DMA window ([L834](verification-maximal-os.md#L834)), and during a consent prompt over the RoT-latched front-end re-delegated to the trusted-path agent ([L958](verification-maximal-os.md#L958)) — neither is an IDL confidentiality channel. So the §5 scoping clause excludes precisely the path §13 names first. The same gap covers RoT-derived keys and material a compartment generates from a local entropy draw. **§16 raises the severity, because a second theorem rests on the CT obligation's scope.** Deterministic replay substitutes its own entropy for secret draws, and the soundness argument for that substitution is explicitly *not* that the values are unimportant but that "every secret-touching binary is CT-verified … so its control flow and memory-access sequence are independent of the secret by construction" ([L1808](verification-maximal-os.md#L1808)). If the CT population is scoped by IDL channel of arrival, a compartment handling a locally-sourced secret — the PIN path above — is outside it, and replay's bit-exactness claim ([L1809](verification-maximal-os.md#L1809)) does not hold for that compartment: a substituted draw could take a different branch and reproduce a different fault. R-16-018 therefore inherits this defect directly. **Repair:** define *secret-touching* once, by label rather than by channel of arrival, and make the label attach to DMA-window and re-delegated-front-end sources as well as IDL types.

<a id="d-05"></a>**D-05 — The protocol-composition exclusion is stated only where it will not be read.**
[L284](verification-maximal-os.md#L284) correctly declines to claim protocol-level composition (TLS/AKA), and §17 books it, but §3's Defended/Residual split — the place a reader looks to learn what the system does and does not defend — does not carry it. This is the largest scope boundary the word *hyper-secure* crosses without a proof behind it. R-05-078's acceptance criterion requires the §3 entry, which does not currently exist. **Repair:** add the exclusion to §3.

<a id="d-06"></a>**D-06 — The register's own §18 workstream is unverified.**
[L413](verification-maximal-os.md#L413) makes maintaining this register and its traceability "the review-gate workstream (§18)". R-05-154's acceptance criterion requires §18 to list it with an owner; §18 has not been extracted, so the criterion is untested. **Repair:** confirm on §18 extraction, or add the deliverable.

<a id="d-07"></a>**D-07 — The three-class `fence.t` mapping has no class for the pipeline, and the fetch buffer is the visible instance.**
[L1707](verification-maximal-os.md#L1707) requires *every* stateful structure in the RTL to map to exactly one of three classes — architectural/context-switched, partition-owned, or `fence.t`-flushed — and makes a structure outside the map a refinement failure. [L1702](verification-maximal-os.md#L1702) then fixes the flush set at "a single structure: the store buffer", and [L1705](verification-maximal-os.md#L1705) enumerates the would-be members that stay out. The static-path fetch buffer ([L1574](verification-maximal-os.md#L1574), [L1333](verification-maximal-os.md#L1333)) is a stateful structure that is none of the three: it is not architectural, not partition-owned, and not in the flush set. [L1340](verification-maximal-os.md#L1340) separately describes the fence's "residual scope" as *pipeline drain*, which would place it — but pipeline drain is never stated as flush-set membership, so R-15-213, R-15-215, and R-15-217 cannot all be satisfied as written. The security argument is unaffected (the buffer's contents are a function of the instruction stream, so it carries no cross-partition history), but the mapping obligation is a *completeness* claim and completeness with an unmapped structure is exactly the failure the clause defines. **Repair:** state whether pipeline state (fetch buffer, decode and execute latches) is class (a) by drain, or add a fourth class for structures whose contents are stream-determined and therefore carry nothing across the switch.

<a id="d-08"></a>**D-08 — The five-part admission test acquires new discharge forms case by case, without amending the test.**
[L1086](verification-maximal-os.md#L1086) states test (2) with exactly two discharges — operand-value-independent latency, or a flow-discipline proof that no secret-labeled operand reaches the feature — and explicitly rules out self-exclusion as a third. Test (3) is stated as *no new hidden shared microarchitectural state that survives a partition switch un-flushed by `fence.t`*. Two admitted features are then discharged by routes neither test names:

- the event-driven sensor readout ([L1443](verification-maximal-os.md#L1443)) passes test (2) by *island containment* — data-dependent event timing confined to the owning island's static NoC/memory partition — which is neither constant-time nor a secret-unreachability proof;
- the 1000BASE-T frozen-coefficient canceller ([L1433](verification-maximal-os.md#L1433)) passes test (3) *per epoch*, with coefficient state that does survive partition switches un-flushed, on the ground that it is constant for the epoch.

Both dispositions are defensible on their merits, and neither is a contradiction. But R-15-010 asks a reviewer to confirm five recorded dispositions against a stated test, and two features are recorded against clauses the test does not contain — so the test as written under-specifies what it admits. **Repair:** amend tests (2) and (3) to enumerate their discharge forms (constant-time; secret-unreachability; partition-confined data-dependence — and for (3): absent; flushed; or provably constant over the switch interval), so the case law is statute, as the defense-in-depth clause already was at [L1093](verification-maximal-os.md#L1093).

<a id="d-09"></a>**D-09 — The end-to-end ECC claim and the granule read-modify-write stage are not reconciled.**
[L1596](verification-maximal-os.md#L1596) makes the end-to-end claim strict: the check "travels *with* the word … and is verified at the consumer, so a fault injected in transit … is caught rather than **masked by re-encoding at each hop**." [L1606](verification-maximal-os.md#L1606) then specifies that a sub-granule store merges with the granule's existing codeword in a read-modify-write stage at the memory controller, "with tag bits and check bits **regenerated combinationally in the same pass**." Regeneration is re-encoding, and it happens at a hop. The stage is almost certainly sound — the read half can be checked before the merge, so a corrupt existing codeword is caught rather than laundered — but the spec does not say so, and R-15-176 and R-15-181 as written are in tension: one forbids re-encoding at a hop, the other mandates one. (A lesser wording issue rides along: [L1604](verification-maximal-os.md#L1604) says "no sub-granule write exists on the fabric" while [L1606](verification-maximal-os.md#L1606) has cores issuing sub-granule stores that the *controller* merges — consistent only if "fabric" means controller-to-array.) **Repair:** state the RMW stage's check obligation explicitly — the existing codeword is verified before merge and the merged word re-encoded — and scope "no sub-granule write" to the controller-to-array path.

<a id="d-10"></a>**D-10 — The axiom set is stated twice, with different membership.**
[L222](verification-maximal-os.md#L222) states it as three classes: "only the proof kernel, the machine model, and the spec statements are axioms." [L445](verification-maximal-os.md#L445) states it as five: "the admission axioms are these two checkers, the spec/policy statements, the CHERI-TAL soundness metatheorem, and the Sail model they check against" — adding the TAL type-checker and its soundness metatheorem, which are genuinely additional axioms, not instances of the three. [L464](verification-maximal-os.md#L464) repeats the five-item version, so §6 is self-consistent and §5 is the outlier. R-05-028's acceptance criterion ("the axiom inventory has exactly these three classes") fails against R-06-011 as written. The axiom set is the single most review-critical enumeration in the document — it is what an independent reviewer checks the whole trust argument against — so two incompatible statements of it is the highest-severity defect the extraction found. **Repair:** state the axiom set once, in §6, as the five entries plus the De Bruijn bootstrap root ([L448](verification-maximal-os.md#L448)); rewrite §5's FPCC sentence to make its narrower claim explicitly about the *proof-carrying-code path* rather than about the platform's axioms.

<a id="d-11"></a>**D-11 — The fuzzed clock is normative and has no owner.**
[L611](verification-maximal-os.md#L611) states "the monitor gets nanoseconds; untrusted compartments get coarsened, fuzzed time," and the property is load-bearing enough that §15 cites it as the model for MAC randomization ("the link-layer analog of the fuzzed clock", [L1417](verification-maximal-os.md#L1417)). But §15's counter gate is binary — a compartment either holds the counter-read permission on its PCC or it does not ([L1274](verification-maximal-os.md#L1274)) — so *coarsened, fuzzed time* cannot come from the hardware path. It must be a service, and no component owns it: §12's server roster has a time-synchronization compartment that disciplines the wall-clock from Roughtime/NTS/PTP ([L867–871](verification-maximal-os.md#L867)) and hands time out "coarse by default", but coarse-by-default is not the same as *fuzzed*, no fuzz distribution or quantum is specified anywhere, and no requirement says which component applies it. R-08-031 therefore has an acceptance criterion a reviewer cannot check: there is no artifact to inspect. This matters more than a missing parameter, because a timing-channel countermeasure with an unspecified distribution is not reviewable at all — the whole question is *how much* jitter and against what observer. **Extracting §16 makes the gap load-bearing rather than cosmetic.** The deterministic-replay record enumerates its nondeterminism sources and includes "the **clock fuzz** added to the coarsened time handed to untrusted compartments" ([L1804](verification-maximal-os.md#L1804)), recording "the fuzz offsets already delivered to the compartments that read them" as public nondeterminism ([L1806](verification-maximal-os.md#L1806)). So a second subsystem now depends on the mechanism: replay cannot record fuzz offsets without a component that applies them at a known point. R-16-015 and R-16-016 inherit R-08-031's unfalsifiability. **Repaired, by deletion rather than specification.** Naming an owner and a distribution would have been the wrong fix: jitter on a counter is recoverable by averaging over repeated reads, which makes it precisely the statistical mitigation §15 refuses when it excludes MTE (*a ~93% mitigation is a statistic, not a theorem*) and MBPTA/EVT. The mechanism is therefore struck. With the counters permission-gated, an untrusted compartment has no clock at all: its only time source is the time service over a ring serviced in its own slot, so the finest interval it can observe is its own slot period, a composition-time constant rather than a degraded value. The distribution question, the owner question, the crown-jewel statement about sufficiency, and the §16 nondeterminism entry all disappear together; the residual is the §11 population-rung channel already booked at R-17-007.
