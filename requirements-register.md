# Atomic Requirements Register

*Normative. This register, not the prose, is the artifact the §5 independent-specification-review release gate audits. [verification-maximal-os.md](verification-maximal-os.md) is its rationale and commentary.*

**Status: complete. All eighteen normative sections are extracted.** Until coverage is complete the review gate cannot be claimed as met; see [Coverage](#coverage).

## How to read this

Each entry is one atomic obligation, individually reviewable, with an acceptance criterion that decides it without reference to the prose. Per [§5](verification-maximal-os.md#atomic-restatement-rule), *a normative claim that cannot be restated as an atomic, testable requirement is a spec defect, not prose to be admired*; claims that resisted restatement during extraction are booked in [Extraction defects](#extraction-defects) rather than silently dropped or paraphrased into something testable that the spec does not actually say.

```
**R-ss-nnn** MUST: the obligation, stated so that a reviewer can agree or disagree with it alone
· Accept: what a reviewer, auditor, or tool checks to decide the obligation is met
· Fail-closed: (where the obligation specifies a refusal) what stops, and what the stop costs
· RoT-fresh: (where the obligation places state under the monotonic counter) which state, and what advances it
· Trace: CJ-… (the crown-jewel spec it constrains) · [§n](verification-maximal-os.md#r-ss-nnn) (prose rationale)
```

**Two of those lines confer membership in a set another entry collects, and they exist because a collected set that certifies its own totality by inspection is a list that silently stops being the set.** This is the failure R-17-016 was repaired for, and the repair was conferral: membership asserted by each entry that has it, gathered in one place, and checked in both directions rather than by roll-call. `· Fail-closed:` confers membership in the §17 fail-closed seam register (R-17-030r) and `· RoT-fresh:` in the §10 freshness enumeration (R-10-013a), so a conferral no register collects and a register member no entry confers are both findings. What that closes is the register's disagreement with the requirements. It does not close completeness, because *fails closed* and *needs freshness* are judgments no tool decides; against that residue `tools/check.ps1` over-approximates the vocabulary of each and requires every entry it catches to be conferred or dispositioned, which makes the totality claim an agenda regenerated on every run rather than a reading nobody repeats.

**Traces are bookmarks, not line numbers.** Each entry names a `<a id="r-ss-nnn">` bookmark carried by the prose line it was extracted from, so editing the prose moves the target with the text and a trace cannot go stale. The display text is the prose section the bookmark sits in, and a second citation of the same requirement takes the suffix `-2`. A line number would be a derived fact restated in a second document with nothing checking it; a bookmark is not, which is why traces are symbolic. `tools/check.ps1` holds what a symbolic reference can still violate silently (R-05-151a).

**Derived facts are computed, not copied.** A line number is only the commonest case of a wider one: any count, table, or list some other artifact already determines is a derived fact, and restating it by hand is a re-synchronization burden that discharges itself silently in the wrong direction. Nothing of that kind is maintained here by care. `tools/check.ps1` recomputes every figure the documents assert (the coverage totals below, the per-section table, the crown-jewel status ratio, the absence and open-CSR row counts) from the artifact that owns it, reports drift, and rewrites the assertions under `-Fix`; the same tool holds the same discipline for the membership the derived views carry, and for the bookmarks the traces cite, those being one defect at three granularities. And where one entry needs a set another entry states, it **cites that entry rather than repeating it** (R-06-009 cites R-05-029's type-level obligations, R-13-012 cites the tier subset of the same list, R-17-046 cites R-06-011's axiom inventory), so a set stated in two places cannot come to disagree, which is the failure R-05-028 and R-17-016 were each repaired for.

**Modality.** `MUST`: obligation on the built system or its process. `MUST NOT`: prohibition; the acceptance criterion is an emptiness or absence check. `IS`: a definition or classification the rest of the register quantifies over; reviewable for correctness, not for compliance.

**IDs are permanent.** A retired requirement keeps its number and is struck, never reused. Renumbering breaks every review record that cites it.

**Order is the specification's, not the numbering's.** Entries appear in the order of the prose they extract, so a requirement added after its neighbours sits where its obligation belongs and not where its number would put it: §18.5 runs 031, 032, 034, 035, 033. A letter-suffixed ID (`R-05-022a`) is an obligation inserted between two existing ones; it is a full entry and is counted as one.

### Crown-jewel specs referenced

| ID | Spec |
| --- | --- |
| `CJ-T` | The apex theorem T: whole-system robust non-interference modulo declassification, on silicon (§5) |
| `CJ-SAIL` | The CHERI-RISC-V Sail model: ISA semantics, incl. its timing and leakage annotations (§15) |
| `CJ-RTL-SAIL` | RTL ⊑ Sail, functional and hyperproperty halves (§15, §18) |
| `CJ-TAL-SOUND` | CHERI-TAL soundness metatheorem: well-typed ⇒ safe and data-race-free over the Sail model (§5) |
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

## §1. Goals

**R-01-001** IS: G1: minimal attack surface.
· Accept: every element of the specification shrinks the TCB, deepens its proof, or contains the non-TCB (R-04-001).
· Trace: CJ-T · [§1](verification-maximal-os.md#r-01-001)

**R-01-002** IS: G2: defense in depth. Compromising any non-TCB component yields only its explicitly granted authority.
· Accept: the property is discharged by the compose-time capability topology plus CHERI containment; it is the quantifier over adversary sets *C* in theorem T (R-05-156).
· Trace: CJ-T, CJ-CERISE · [§1](verification-maximal-os.md#r-01-002)

**R-01-002a** IS: G2 has two premises in different conditions. Its software premise admits no interim: nothing executes that the certifying toolchain has not certified, so a missing certificate is a delivery failure and never a degraded admission (R-13-022, R-17-033). Its hardware premise admits one, because every isolation boundary rests on CHERI alone with no disjoint backstop retained (R-17-037, R-17-045) and the arrow beneath it is the least-built layer of the stack (R-18-010): until that arrow closes, the premise stands at *evidence tier* (rvfi conformance, Sail-generated SystemVerilog under commercial FEV, the structural netlist audit carrying the imported-core half of the absence contract) rather than at *theorem tier* (the Kami/Kôika Coq unbounded refinement).
· Accept: each tier is identified by its vehicles rather than by adjective, so which tier a core stands at is read off the artifacts admitted for that core; the two tiers partition the rungs R-18-010 stages, at the unbounded one.
· Trace: CJ-T, CJ-RTL-SAIL, CJ-CERISE · [§1](verification-maximal-os.md#r-01-002a)

**R-01-002b** MUST: A unit built before R-18-010's unbounded rung is admitted for its cores asserts G2 at evidence tier and no higher, as does every §3 defended entry answered by CHERI containment (R-03-006). The tier rises per core when that core's unbounded refinement is admitted, never at an intermediate rung, under the retirement discipline R-05-022 imposes on every interim non-Coq anchor.
· Accept: decided by inspecting two lists rather than by judgment, the rungs admitted for that core and the claims riding them (R-05-022a's shape). An attestation, datasheet, or conformance claim that asserts G2 without the tier it stands at is a review-gate finding, as is a tier raised on an intermediate rung.
· Trace: CJ-T, CJ-RTL-SAIL · [§1](verification-maximal-os.md#r-01-002b)

**R-01-003** IS: G3: end-to-end formal verification from abstract spec through source, binary, ISA, and modeled hardware to RTL, with RTL ⊑ Sail a named in-scope mechanization workstream rather than a bare trust assumption.
· Accept: the RTL of record is authored in Kami/Kôika, with riscv-formal/rvfi the bring-up gate and Isla the obligation bridge; below it, fabricated silicon versus verified RTL is the irreducible fab residual.
· Trace: CJ-RTL-SAIL · [§1](verification-maximal-os.md#r-01-003)

**R-01-004** IS: G4: stateless, atomic, transactional, rollback-friendly.
· Accept: discharged by the immutable content-addressed image plus enumerated mutable volumes (R-10-026) and the A/B transactor (R-11-001).
· Trace: CJ-DEVTREE · [§1](verification-maximal-os.md#r-01-004)

**R-01-005** IS: G5: reliability through fault isolation, crash-only components, and health-gated recovery.
· Accept: discharged by §16.
· Trace: CJ-KERNEL · [§1](verification-maximal-os.md#r-01-005)

**R-01-006** IS: Performance is subordinate to security and pessimism is free by axiom; this is the tie-break the no-tightening rule and the design-space exploration both invoke.
· Accept: every trade recorded as "spent on the free axis" cites this goal ordering.
· Trace: CJ-T · [§1](verification-maximal-os.md#r-01-006)

---

## §2. Non-Goals

**R-02-001** MUST NOT: There is no POSIX or Linux compatibility in any form: no `fork()`, no uid/gid, no ambient authority, no Linux-personality shim, and no legacy VM.
· Accept: software runs natively against the capability substrate or it does not run; there is no ambient-authority pocket universe anywhere on the machine.
· Trace: CJ-CERISE · [§2](verification-maximal-os.md#r-02-001)

**R-02-002** IS: There is no broad hardware support: a curated allowlist only.
· Accept: the allowlist collapses toward transducers and register slaves (R-04-009).
· Trace: CJ-CERISE · [§2](verification-maximal-os.md#r-02-002)

**R-02-003** IS: There is no fixed form factor: laptop, phone, IoT, workstation, and server instantiations share the principles and only the physical particulars vary. The reference instantiation is a mobile/laptop device.
· Accept: a form factor lacking a peripheral simply omits it; the privacy cutoffs are driven by lockout on every form factor and additionally by the away-gesture where one exists.
· Trace: CJ-DEVTREE · [§2](verification-maximal-os.md#r-02-003)

**R-02-004** IS: There is no performance parity: in-order cores, no SMT, no JIT, no dynamic speculation, no dynamic branch prediction. Throughput lands in 2010s-iGPU / early-NPU / LTE-class-modem territory by design.
· Accept: rendering, AI, and radio signal processing run on general-purpose vector and matrix cores under the same ISA and proofs; there is no fixed-function GPU, no discrete accelerator, and no opaque coprocessor.
· Trace: CJ-SAIL · [§2](verification-maximal-os.md#r-02-004)

**R-02-005** MUST: Instruction-level parallelism is bought only from static, exposed mechanisms (wide in-order issue, decoder-stage macro-op fusion, RVV), never from mechanisms creating hidden speculative microarchitectural state.
· Accept: consistent with R-15-010 and R-15-031.
· Trace: CJ-SAIL · [§2](verification-maximal-os.md#r-02-005)

**R-02-006** MUST NOT: There is no legacy: no BIOS/MBR, UEFI, ACPI, IPv4, 32-bit modes, or compressed-instruction ambiguity.
· Accept: each is absent from the profile and the model.
· Trace: CJ-SAIL · [§2](verification-maximal-os.md#r-02-006)

**R-02-007** MUST NOT: Proprietary firmware black boxes, named exhaustively in the §12 topology table, are excluded by platform mandate and not mitigated.
· Accept: the exclusion list is the topology table's fourth class (R-12-004).
· Trace: CJ-CERISE · [§2](verification-maximal-os.md#r-02-007)

---

## §3. Threat Model

**R-03-001** IS: The defended set is enumerated: remote network attackers including hostile radio infrastructure; hostile web content; malicious or compromised apps, servers, and drivers; malicious DMA peripherals and counterfeit or spoofed wired peripherals and cables; evil-maid physical access; forensic extraction of a device seized after at least one unlock; coerced unlock (duress); and software supply-chain attack in both its tampering and subversion forms.
· Accept: each defended item names the mechanism that answers it and the section that specifies it.
· Trace: CJ-T · [§3](verification-maximal-os.md#r-03-001)

**R-03-002** IS: Covert activation of the microphone, camera, or radios by compromised software or firmware, and use of the wired port in a deliberately-hostile environment, are additionally countered by user-controlled cutoffs beneath the capability-gated per-app access.
· Accept: the cutoffs are the sealed Hall-effect switches and the mechanical camera shutter (R-15-145, R-15-152).
· Trace: CJ-T · [§3](verification-maximal-os.md#r-03-002)

**R-03-003** IS: The electromagnetic environment is in scope: radiated and conducted EMI and electromagnetic fault injection are countered by the Faraday enclosure with residual faults caught by fixed-latency ECC and the fail-stop path; single-event upsets are deliberately *not* shielded but detected, corrected, or contained, with their rate cut at the source by a radiation-hardened realization where the deployment warrants.
· Accept: consistent with R-15-153 through R-15-157.
· Trace: CJ-T · [§3](verification-maximal-os.md#r-03-003)

**R-03-004** IS: The residual set is enumerated: timing channels beyond the transient-execution and DVFS classes; specification errors; the proof-tool trust base; protocol-level security above the scheme level (the composed session security of TLS 1.3, WireGuard, and the cellular AKA, which the §5 crypto assurance does not reach); invasive physical attack; malicious silicon fabrication; and carrier or certification-body acceptance of an open cellular stack.
· Accept: each maps to a §17 entry: the protocol-level entry to R-17-049, which is the exclusion R-05-078 states and the largest scope boundary the word *hyper-secure* crosses.
· Trace: CJ-T · [§3](verification-maximal-os.md#r-03-004)

**R-03-005** IS: Invasive physical attack is the only way to reach main memory at all, main memory being on-die, so delidding and probing is the entry price; the line is what scopes the memory path in §15, and drawing it elsewhere would make every on-die interface a defended one.
· Accept: the scope line is load-bearing and is booked as such (R-17-059).
· Trace: CJ-T · [§3](verification-maximal-os.md#r-03-005)

**R-03-006** MUST: The defended set enumerates scope, not strength: each entry is asserted at the discharge tier of the mechanism answering it (R-01-002a), so the entries answered by CHERI containment carry R-01-002b's tier until the RTL ⊑ Sail ladder reaches its unbounded rung.
· Accept: for each defended entry, the mechanism R-03-001 requires it to name is read against the tier definition, and no entry is asserted above the tier of its own mechanism; the containment mechanism most entries share reads as evidence tier for as long as R-18-010's unbounded rung is open.
· Trace: CJ-T, CJ-CERISE · [§3](verification-maximal-os.md#r-03-006)

**R-03-007** MUST: An adversary whose objective is to make the device stop is in scope, and the threat model states the disposition in both directions rather than omitting the objective: denial attempted *through* a boundary is defended, discharged by the `P-5` row of every boundary the coverage matrix enumerates, with forced-sweep denial priced to the aggressor (R-08-008) and reset-loop abuse bounded to downtime (R-16-007).
· Accept: the defended half is decidable against the matrix rather than against this sentence, every `P-5` cell being present and resting on a requirement per R-17-001b; a §3 that obliges availability at every boundary while declining to say whether a denial adversary is in scope at all is the defect this closes.
· Trace: CJ-T · [§3](verification-maximal-os.md#r-03-007)

**R-03-008** IS: Denial achieved by provoking the platform's own refusals is residual, and is residual as a *composition* rather than as any single mechanism: thermal trip, watchdog reset, containment of an attacked surface, admission refusal, the sealed cutoffs, the emergency path's coverage floor, and every fault detector's answer to detection are each individually correct and individually an availability cost, and their conjunction is the fail-closed seam register (R-17-030a).
· Accept: this residual maps to a §17 entry as R-03-004's do, and the entry it maps to is a register rather than a single item, because the object being booked is the conjunction; a member booked in its own section and absent from that register is a review-gate finding against R-17-030a, and R-17-030r is what decides it, this criterion having been discharged by inspection until then.
· Trace: CJ-T · [§3](verification-maximal-os.md#r-03-008)

**R-03-009** IS: Neither list claims a device-level availability guarantee. The invariant held across every fail-closed path is that none of them costs confidentiality, integrity, or authority, a refusal always being the safe direction; the platform does not promise that the device stays up, and the places where it deliberately may not are enumerated rather than left to be assembled.
· Accept: the invariant is checkable member by member against the R-17-030 seams, each of which must spend availability alone; a member whose refusal costs one of the other three properties belongs in R-03-004's residual set instead, and the enumeration is what makes that decidable. R-17-030o is the one member whose *weakening* would cost confidentiality, which is why it is retained as a refusal rather than repaired into a degraded mode.
· Trace: CJ-T, CJ-NI · [§3](verification-maximal-os.md#r-03-009)

---

## §4. Organizing Principle

**R-04-001** MUST: Every element of the specification must shrink the TCB, deepen its proof, or contain the non-TCB.
· Accept: an addition meeting none of the three is inadmissible.
· Trace: CJ-T · [§4](verification-maximal-os.md#r-04-001)

**R-04-002** IS: Two orthogonal security properties are both required: capabilities control *access* and information-flow control governs *propagation*, each blind to the other.
· Accept: static composition is the structural prerequisite for proving both: a fixed component graph has a fixed capability topology *and* a fixed flow policy, over which one non-interference theorem can be stated.
· Trace: CJ-NI, CJ-CERISE · [§4](verification-maximal-os.md#r-04-002)

**R-04-003** IS: A compartment is a bounded set of code and data holding exactly the capabilities its manifest grants and no others, isolated from every peer by CHERI capabilities alone, sharing the one physical address space with no ring, no MMU, and no separate address space.
· Accept: a boundary costs neither a page table nor a mode switch.
· Trace: CJ-CERISE · [§4](verification-maximal-os.md#r-04-003)

**R-04-004** MUST: The only path between two compartments is a sealed entry point through the switcher, which saves and restores the caller and, through the local/global capability discipline, bounds a delegated buffer to the call so authority cannot be captured past it.
· Accept: consistent with R-15-068 and R-15-074.
· Trace: CJ-CERISE · [§4](verification-maximal-os.md#r-04-004)

**R-04-005** IS: The structure is universal: the kernel is the sole privileged resident and every other thing on the machine is a compartment: every server, driver, and filesystem, the network and radio stacks, every app, and every browser origin, each pre-composed at build time.
· Accept: even the userland-resident TCB exceptions (powerbox, trusted-path agent) are confined like a server, and the verified HAL is a non-TCB compartment.
· Trace: CJ-CERISE · [§4](verification-maximal-os.md#r-04-005)

**R-04-006** IS: Compartments nest: an app is one least-authority compartment at its edge, and its manifest may declare an internal compartment graph whose library sub-compartments each carry their own sub-manifest. Nesting is not a second mechanism: a sub-compartment is one more node in the same flat, machine-checked component graph.
· Accept: no new object class appears for nesting.
· Trace: CJ-CERISE · [§4](verification-maximal-os.md#r-04-006)

**R-04-007** MUST: Every app is at least one memory-safe, capability-confined compartment; internal sub-compartmentalization is mandatory for any dependency that parses attacker-controlled input or is handed authority beyond pure compute, and available otherwise as compose-time authority minimization.
· Accept: the mandatory population is checked at admission against the manifest (R-13-024).
· Trace: CJ-CERISE · [§4](verification-maximal-os.md#r-04-007)

**R-04-008** MUST: Every compartment is fixed at composition: no compartment is created and no privilege minted at runtime, the one sanctioned runtime authority transfer being a powerbox declassification that extends the live edge set without adding a compartment or a privilege class.
· Accept: sandboxes, containers, enclaves, and permission subsystems are obviated by construction, not reimplemented.
· Trace: CJ-NI, CJ-KERNEL · [§4](verification-maximal-os.md#r-04-008)

**R-04-009** MUST: Heterogeneity lives in the datapath, never in the trust structure: every core class shares the base ISA, the purecap capability model, the kernel binary, and one parameterized formal model, differing only in datapath execution resources.
· Accept: anything that cannot be expressed as an ISA-visible, Sail-modeled, capability-checked extension of a core is not admitted as compute.
· Trace: CJ-SAIL · [§4](verification-maximal-os.md#r-04-009)

**R-04-010** MUST: No foreign computers: the platform contains exactly one computer, the multikernel die. Every function conventionally delegated to a firmware-running coprocessor is dissolved into software on disciplined cores, reduced to a fixed-geometry arithmetic unit, reduced to firmware-free device RTL behind capability-checked DMA, or reduced to a transducer or register slave.
· Accept: a component that fetches and executes instructions outside this discipline does not go on the die or the board.
· Trace: CJ-CERISE · [§4](verification-maximal-os.md#r-04-010)

**R-04-011** IS: The single tolerated exception is the eUICC, a carrier-mandated foreign trust domain contained as a register-slave crypto oracle with zero platform authority.
· Accept: the exception count is one (R-12-045).
· Trace: CJ-CERISE · [§4](verification-maximal-os.md#r-04-011)

**R-04-012** IS: The consequences are stated: the device allowlist collapses toward transducers, N vendor firmware-update channels collapse into the one proof-checked generation mechanism, and attestation coverage becomes total, radio included.
· Accept: each consequence is discharged by a named mechanism (R-11-003, R-09-025).
· Trace: CJ-DEVTREE · [§4](verification-maximal-os.md#r-04-012)

---

## §5. Languages & Verification

### 5.1 Trust, language, and compilation boundary

**R-05-001** MUST: The whole TCB is written in verified C and compiled by CHERI-CompCert under Coq.
· Accept: every object in the §6 TCB inventory appears in the CompCert build manifest with its correctness certificate; the set of TCB objects built by any other compiler is empty.
· Trace: CJ-COMPCERT · [§5](verification-maximal-os.md#r-05-001)

**R-05-002** MUST: The §6 admission checker is inside the TCB and is subject to R-05-001 without exemption.
· Accept: the checker appears in both the TCB inventory and the CompCert build manifest.
· Trace: CJ-COMPCERT · [§5](verification-maximal-os.md#r-05-002)

**R-05-003** MUST NOT: No TCB component enters the system as a checker-admitted artifact.
· Accept: (TCB inventory) ∩ (checker-admitted artifact set) = ∅.
· Trace: CJ-COMPCERT · [§5](verification-maximal-os.md#r-05-003)

**R-05-004** MUST: The crypto core's constant-time property is verified on the artifact against the §15 leakage model.
· Accept: each crypto binary carries artifact-level CT evidence (taint-typing derivation or relational proof term); no CT claim in the crypto core cites compiler preservation as its ground.
· Trace: CJ-CT-SOUND, CJ-LEAK · [§5](verification-maximal-os.md#r-05-004)

**R-05-005** MUST: The crypto core's field-arithmetic kernels are verified C compiled through CHERI-CompCert.
· Accept: every field-arithmetic object is in the CompCert build manifest; no field-arithmetic object is a checker-admitted assembly leaf.
· Trace: CJ-COMPCERT, CJ-CRYPTO-SPEC · [§5](verification-maximal-os.md#r-05-005)

**R-05-006** MUST NOT: Contained code never enters the TCB.
· Accept: no artifact produced by the certifying userspace toolchain appears in the TCB inventory.
· Trace: CJ-COMPCERT · [§5](verification-maximal-os.md#r-05-006)

**R-05-007** IS: Contained data-plane code is Rust by default; contained control-plane code is Coq-verified Lustre compiled by Vélus.
· Accept: each §12 server's control-plane logic is a Lustre node set; its data-plane logic is Rust.
· Trace: CJ-VELUS · [§5](verification-maximal-os.md#r-05-007)

**R-05-008** MUST NOT: Admission never gates on the source language or producer identity of a binary.
· Accept: source is read only as the hash-bound subject of a correspondence theorem; no source-language identifier or producer credential grants admission.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-008)

**R-05-009** MUST: Any memory-safe or formally-verified language that yields a well-typed binary and a kernel-checked elaboration into an existing semantic anchor, or that ships the required manual proofs, is admissible on the same terms as Rust.
· Accept: the admission rules contain no language allowlist; a non-Rust component meeting the binary-level and source-correspondence floors is admitted without exception or waiver.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-009)

**R-05-010** MUST NOT: A contained component's own foreign-prover verification never enters the trust base.
· Accept: the axiom and trust-base inventory attributes no entry to a contained component's F\*/Z3, EasyCrypt, or other foreign-prover pedigree; removing that pedigree changes no platform guarantee.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-010)

### 5.2 One prover

**R-05-011** IS: Exactly one proof checker exists in the trust base: the Coq (CIC) kernel.
· Accept: the trust-base inventory names one checker; no admitted artifact's acceptance depends on any other checker.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-011)

**R-05-012** MUST: The kernel is seL4's design re-proved end-to-end in Coq, not seL4's Isabelle proof adopted.
· Accept: no Isabelle artifact appears in the trust base; the kernel refinement proof is a Coq development.
· Trace: CJ-KERNEL · [§5](verification-maximal-os.md#r-05-012), [§5](verification-maximal-os.md#r-05-012-2)

**R-05-013** MUST: The kernel is compiled through CompCert/SECOMP.
· Accept: the kernel image's build manifest names the SECOMP-criterion CHERI backend.
· Trace: CJ-COMPCERT, CJ-SECOMP · [§5](verification-maximal-os.md#r-05-013)

**R-05-014** MUST: The non-interference theorem is a fresh Coq re-proof, and no part of it is inherited from seL4's existing NI proof.
· Accept: the NI development cites no l4v proof obligation as discharged elsewhere.
· Trace: CJ-NI · [§5](verification-maximal-os.md#r-05-014)

### 5.3 The single-prover rule binds the checker, not the producer

**R-05-015** MUST: Any prover, solver, or search procedure may produce a proof term, provided the Coq kernel re-checks the emitted term.
· Accept: for every externally-found proof, a kernel-checked term exists; the tool's own verdict is never the ground of acceptance.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-015)

**R-05-016** MUST NOT: No tool is admitted as a second checker.
· Accept: no artifact is accepted on the strength of a non-Coq checker's verdict.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-016)

**R-05-017** MUST: SMT results enter only via in-kernel reconstruction (SMTCoq-style witness import).
· Accept: every SMT-derived fact has a kernel-checked reconstruction; no `Axiom` records an SMT result.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-017)

**R-05-018** IS: Learned tactic synthesis and LLM-guided proof search are untrusted finders whose terms the kernel re-checks, and carry zero trust cost.
· Accept: removing every such tool from the pipeline invalidates no checked theorem.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-018)

### 5.4 The semantic-anchor budget

**R-05-019** IS: The load-bearing semantic anchors are frozen and exhaustively enumerated: Sail (ISA), CHERI-C/CompCert (verified-C memory model), Gallina/CIC, Radium (Rust fragment), Lustre/Vélus (synchronous dataflow), Kôika/Kami (hardware refinement), and the one Iris-over-Sail program logic with its four theories.
· Accept: the anchor list in the trust-base inventory is exactly these seven; any eighth is an amendment to this register.
· Trace: CJ-SAIL, CJ-RTL-SAIL · [§5](verification-maximal-os.md#r-05-019)

**R-05-019a** MUST: Each semantic anchor is one artifact, and every theorem that mentions it quantifies over that same term; an anchor re-transcribed once per consumer is a second anchor and is rejected under R-05-020's non-duplication condition.
· Accept: the trust-base inventory holds exactly one artifact per anchor, and every theorem citing an anchor resolves to that artifact rather than to a per-consumer copy of it.
· Trace: CJ-SAIL, CJ-T · [§5](verification-maximal-os.md#r-05-019a)

**R-05-019b** MUST: The Sail model enters the development as the Coq definitions Sail's own backend emits, and both the §13 Iris-over-Sail program logic and the §15 RTL ⊑ Sail refinement quantify over that one term.
· Accept: the binary-against-Sail obligations and the hardware refinement resolve to the same Coq definitions; neither tower carries its own transcription of the ISA model.
· Trace: CJ-SAIL, CJ-RTL-SAIL · [§5](verification-maximal-os.md#r-05-019b)

**R-05-019c** MUST NOT: No build step emits the Sail model from the development it anchors.
· Accept: the ISA model's provenance is the authored, frozen profile the R-05-150 gate reviews, and no build step produces it from a Coq artifact. Generation downstream of it, the Coq definitions its own backend emits, is proof transport under R-05-021 and is unaffected.
· Trace: CJ-SAIL · [§5](verification-maximal-os.md#r-05-019c)

**R-05-020** MUST: A new semantics, program logic, or translator is admitted only on a shown demonstration of all three conditions: Coq-native or mechanically bridged; non-duplicating of an existing anchor; and retiring an interim it replaces.
· Accept: each amendment record carries three arguments, one per condition, each shown rather than asserted.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-020)

**R-05-021** IS: A verified compiler is proof transport between two existing anchors, not an anchor, and is admitted freely.
· Accept: the anchor count is unchanged by adding a verified compilation step.
· Trace: CJ-COMPCERT, CJ-VELUS · [§5](verification-maximal-os.md#r-05-021)

**R-05-022** MUST: Every interim non-Coq anchor carries a named Coq-native destination and is governed by one stated retirement rule: an interim retires when its destination has passed admission for every consumer that currently rides the interim, and is struck from the trust-base inventory in that same generation.
· Accept: *retired* is decided by inspecting two lists (the interim's consumer set and the destination's admitted artifacts) rather than by judgment. The five entries (F\*/Z3 for libcrux/HACL\*, EasyCrypt's Why3/SMT, aiT, Binsec/Rel, Cranelift/Crocus's SMT) each carry a destination and a consumer list.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-022)

**R-05-022a** MUST: An interim whose consumer set grows without its destination advancing is a review-gate finding, not a silent extension.
· Accept: the *shrinking-interim* claim of §17 is measurable against the consumer lists rather than asserted.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-022a)

### 5.5 Compilation guarantees

**R-05-023** MUST: Translation validation against the RISC-V Sail model covers the assembly, link, and image-construction steps that fall outside CompCert's theorem.
· Accept: every trusted image has a validation record covering each post-CompCert step.
· Trace: CJ-SAIL, CJ-COMPCERT · [§5](verification-maximal-os.md#r-05-023)

**R-05-024** MUST: The CHERI-RISC-V CompCert backend satisfies a secure-compilation (robust-preservation) criterion: it preserves compartment isolation against an adversarial linked context, not merely refinement of well-defined whole-program behaviour.
· Accept: the backend's top-level theorem statement quantifies over an adversarial linked context.
· Trace: CJ-SECOMP · [§5](verification-maximal-os.md#r-05-024)

**R-05-025** IS: The compiler remains untrusted evidence-producing machinery under FPCC; R-05-024 strengthens its theorem, not its trust status.
· Accept: the compiler is absent from the consumer-side TCB inventory.
· Trace: CJ-SECOMP · [§5](verification-maximal-os.md#r-05-025)

### 5.6 Foundational proof-carrying code

**R-05-026** MUST: Every binary ships a machine-checkable proof of its assurance tier, stated at binary level against the CHERI-RISC-V Sail model, plus a source-correspondence theorem binding the final image to its exact content-addressed source closure.
· Accept: no binary is admitted without a tier-appropriate certificate and a theorem that every final-image behavior refines behavior permitted by the committed source through assembly, linking, and image construction.
· Trace: CJ-SAIL, CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-026)

**R-05-027** MUST: The certificate is checked at admission by the on-device checker.
· Accept: admission fails closed when the certificate is absent, malformed, or fails re-checking.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-027)

**R-05-028** MUST NOT: No trusted verification-condition generator exists; on the proof-carrying-code path the axioms are the proof kernel, the machine model, and the spec statements.
· Accept: the three classes are what PCC rests on; the platform's full axiom set is enumerated once in §6 (R-06-011) and is larger, adding the TAL type-checker, its soundness metatheorem, and the bootstrap root. This bullet no longer claims to state the whole set.
· Trace: CJ-T, CJ-SAIL · [§5](verification-maximal-os.md#r-05-028)

**R-05-029** IS: The type-level obligations are exactly: memory safety, definite initialization, data-race freedom, control-flow integrity, no-runtime-codegen, ABI/type conformance, examined verdicts, absent ambient state, representation-and-provenance conformance, constant-time, and WCET. This list is canonical: every other section cites it rather than restating it, and control-flow integrity carries both halves: the runtime *legal-here* the sentries enforce and its compose-time callee-set enumeration, which is the static shadow of the same fact and not a twelfth obligation.
· Accept: every admitted binary's derivation carries an attribute, citation, or deletion-check for each listed obligation, and no other section enumerates the obligations independently (R-06-009, R-13-012, and the move table at R-05-037/R-05-038 are citations of this entry).
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-029)

**R-05-030** IS: The obligations no type system states (Tier-0 refinement, non-interference, crypto reduction security, and the residual unstructured constant-time and WCET cases) remain proof terms for the CIC kernel.
· Accept: none of these appears as a TAL attribute; each has a release-time proof term.
· Trace: CJ-NI, CJ-REDUCTION · [§5](verification-maximal-os.md#r-05-030)

**R-05-031** MUST: The CHERI-TAL soundness metatheorem (well-typed ⇒ safe and data-race-free over the Sail model) is a single Coq proof.
· Accept: one theorem statement, one development; admission's appeal to type-checking cites it and nothing else.
· Trace: CJ-TAL-SOUND, CJ-SAIL · [§5](verification-maximal-os.md#r-05-031)

**R-05-032** MUST: The verified compiler runs in certifying mode: each Tier-0 build ships the composed theorem *this binary refines its abstract spec and robustly preserves compartment isolation*.
· Accept: every Tier-0 artifact carries a composed theorem with both conjuncts.
· Trace: CJ-SECOMP, CJ-KERNEL · [§5](verification-maximal-os.md#r-05-032)

**R-05-033** MUST: A secret-touching binary admitted through the Islaris-style Iris-over-Sail path (no verified compiler in the loop) carries a separate binary-level constant-time obligation.
· Accept: for each such binary, a CT artifact exists independent of the functional/safety proof.
· Trace: CJ-CT-SOUND · [§5](verification-maximal-os.md#r-05-033)

**R-05-034** MUST NOT: The compiler, extraction tooling, and build farm are absent from the consumer-side TCB.
· Accept: the consumer-side TCB inventory names none of them.
· Trace: CJ-COMPCERT · [§5](verification-maximal-os.md#r-05-034)

**R-05-035** IS: Every instruction has exactly one decoding, anchored to the fixed slot grid of a bundle-aligned fetch unit and independent of where decoding started, so binary-level proofs discharge no overlapping-stream interpretation and no reachable-entry-point argument.
· Accept: the §15 profile excludes the C extension (R-15-036) and encodes code in the fixed-rate dictionary format (R-15-036a); the TAL's decode relation is a function of bundle contents and slot index (R-15-036b).
· Trace: CJ-SAIL · [§5](verification-maximal-os.md#r-05-035); constrains R-15-*

### 5.7 The three checker moves

**R-05-036** IS: The checker discharges every type-level obligation by exactly three moves: (I) cite a runtime invariant CHERI enforces, (II) evaluate a Knuth-style attribute over the already-typed CFG, (III) confirm a deletion.
· Accept: each obligation in R-05-029 maps to exactly one move; the checker's implementation has no fourth mechanism.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-036)

**R-05-037** IS: Move I carries spatial memory safety, no-runtime-codegen, and CFI-runtime through sentry reachability.
· Accept: the derivation records the cited invariant; the checker inspects the citation.
· Trace: CJ-CERISE · [§5](verification-maximal-os.md#r-05-037)

**R-05-038** IS: Move II carries temporal memory safety, definite initialization, data-race freedom, examined verdicts, constant-time, WCET, callee-set enumeration, and type/ABI conformance.
· Accept: each has a finite attribute domain and a syntax-directed rule (see R-05-132). Callee-set enumeration is the compose-time half of R-05-029's CFI obligation, not a twelfth entry, so this row partitions the canonical eleven rather than extending them.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-038)

**R-05-039** IS: Move III carries representation-and-provenance conformance and absence of ambient mutable state, as one-pass inspections of absences.
· Accept: each is decided by a single pass over the image or derivation, with no fixpoint.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-039)

**R-05-040** MUST NOT: The checker never re-proves a hardware fact cited under move I.
· Accept: no move-I obligation has a checker-side decision procedure beyond confirming the citation.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-040)

**R-05-041** MUST: The soundness metatheorem is stated over the three moves against the four unary invariants, not over a flat list of eleven obligations.
· Accept: the theorem statement quantifies over move classes; adding an obligation within an existing move adds no new top-level case.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-041)

### 5.8 Verified parsers

**R-05-042** MUST: Every attacker-facing wire format is parsed by a verified copy-once Narcissus parser, explicitly including the ASN.1 UPER/aligned-PER grammars of cellular RRC/NAS and the 802.11 MLME element grammars.
· Accept: the wire-format inventory lists every attacker-facing format with its Narcissus descriptor; the set of hand-written attacker-facing parsers is empty except as permitted by R-05-050.
· Trace: CJ-FORMAT · [§5](verification-maximal-os.md#r-05-042)

**R-05-043** MUST: The Coq decoder reaches machine code by Fiat/Bedrock correct-by-construction synthesis to imperative Clight.
· Accept: no parser is extracted onto a managed runtime and none is hand-refined per grammar; the synthesis is counted as proof transport, not an anchor.
· Trace: CJ-FORMAT, CJ-COMPCERT · [§5](verification-maximal-os.md#r-05-043)

**R-05-044** MUST NOT: EverParse is not admitted as a shipped parser generator or checker.
· Accept: no shipped parser derives from an F\*/Z3 generator.
· Trace: CJ-FORMAT · [§5](verification-maximal-os.md#r-05-044)

**R-05-045** IS: EverParse is admissible as an untrusted differential oracle.
· Accept: its use appears only in the §18 test pipeline, never in the trust base.
· Trace: CJ-FORMAT · [§5](verification-maximal-os.md#r-05-045)

**R-05-046** IS: Each format descriptor is a crown-jewel spec: the parser proof is against the descriptor, not against the 3GPP or IEEE text.
· Accept: the descriptor set is enumerated in the crown-jewel inventory and is subject to independent review under R-05-150.
· Trace: CJ-FORMAT · [§5](verification-maximal-os.md#r-05-046)

**R-05-047** MUST: Memory safety of a parser holds unconditionally regardless of descriptor fidelity: a mis-transcribed grammar yields a semantic defect, never a memory-safety one.
· Accept: copy-once structure, `#![forbid(unsafe_code)]`, CHERI bounds, and §12/§13 compartment containment are each independently established for every parser.
· Trace: CJ-TAL-SOUND, CJ-CERISE · [§5](verification-maximal-os.md#r-05-047)

**R-05-048** MUST: NR RRC descriptors are compiled from the published machine-readable ASN.1 (3GPP TS 38.331) by a verified ASN.1 (X.691 UPER) → Narcissus front end, not hand-written.
· Accept: the RRC descriptor build reads the vendor ASN.1 modules as input; no hand-written RRC descriptor exists.
· Trace: CJ-FORMAT · [§5](verification-maximal-os.md#r-05-048)

**R-05-049** IS: The only trusted artifact on the parser path is the small ASN.1 → Narcissus compiler, and its output is Coq-checked.
· Accept: the trust-base inventory lists the compiler and no other parser-path artifact.
· Trace: CJ-FORMAT · [§5](verification-maximal-os.md#r-05-049)

**R-05-050** MUST: 5G-core NAS (TS 24.501, IEI/TLV, not ASN.1) keeps a hand-written grammar, and that grammar carries differential-oracle coverage as its residual-retirement mechanism.
· Accept: the NAS descriptor is flagged in the crown-jewel inventory as hand-transcribed and has a differential-oracle corpus result.
· Trace: CJ-FORMAT · [§5](verification-maximal-os.md#r-05-050)

**R-05-051** MUST: Differential oracles (asn1scc, asn1c, Wireshark dissectors, srsRAN/OpenAirInterface decoders) cross-check every derived parser on captured and fuzzed corpora and enter no trust base.
· Accept: a §18 corpus result exists per descriptor; no oracle appears in the trust-base inventory.
· Trace: CJ-FORMAT · [§5](verification-maximal-os.md#r-05-051)

**R-05-051a** MUST: Every format descriptor whose encoding is ever an input to a signature, a hash used as a name, a content address, a cache key, or an equality test carries a machine-checked **canonicity** theorem beside its Narcissus correctness pair: decode is injective on the admissible byte strings, so re-encoding a decoded input returns that input unchanged and no value has a second admissible encoding.
· Accept: the theorem is Coq-checked against the descriptor and quantifies over the whole admissible language rather than a corpus; the R-05-042 wire-format inventory records which descriptors carry it; and the correctness pair alone is never cited for this property, the two directions being separate theorems.
· Trace: CJ-FORMAT · [§5](verification-maximal-os.md#r-05-051a)

**R-05-051b** MUST: A descriptor carrying R-05-051a admits no encoding slack: one admissible length form, one presence encoding per optional field, fixed field order, no free padding or reserved bits, and no accept-and-ignore field. A non-canonical input is a decode failure and is never normalized into the canonical encoding of the same value.
· Accept: no decoder on an identity-bearing path maps two distinct admissible byte strings to one value; where the published grammar admits several encodings of one value, the descriptor pins one subset and the remainder fails to decode rather than being accepted and rewritten.
· Trace: CJ-FORMAT · [§5](verification-maximal-os.md#r-05-051b)

**R-05-051c** MUST NOT: No signature, content address, cache key, or equality decision is taken over an encoding whose descriptor carries no R-05-051a theorem; a format that cannot carry one is refused that role rather than used with a stated caveat.
· Accept: the set of identity-consuming sites resting on a descriptor without the theorem is empty, each site (the §13 pack reader R-13-009 and typed manifest R-13-003, the §10 content address R-10-005a, the §12 deterministic-reuse key R-12-024d) naming the descriptor it depends on rather than assuming one.
· Trace: CJ-FORMAT · [§5](verification-maximal-os.md#r-05-051c)

### 5.9 Verified synchronous control planes

**R-05-052** MUST: The control-plane logic of §12 servers (supervision trees, protocol state machines, and mode/timing sequencing) is written in Lustre and compiled by Vélus.
· Accept: each server's control plane is a Lustre node set; no control-plane logic is hand-written Rust or C.
· Trace: CJ-VELUS · [§5](verification-maximal-os.md#r-05-052)

**R-05-053** MUST: Vélus emits CompCert Clight and its correctness theorem composes with CompCert's.
· Accept: a single composed theorem covers Lustre source to CHERI machine code; no unproved gap sits between the two compilers.
· Trace: CJ-VELUS, CJ-COMPCERT · [§5](verification-maximal-os.md#r-05-053)

**R-05-054** IS: Control-tier WCET falls out of compilation (a Lustre node is a loop-free, statically-sized reaction) and does not consume the §5 syntax-directed cost annotation.
· Accept: no control-plane node carries a max-path cost attribute.
· Trace: CJ-WCET, CJ-VELUS · [§5](verification-maximal-os.md#r-05-054)

**R-05-055** MUST: Vélus's clock calculus rejects instantaneous cycles and fixes evaluation order, so the control tier exhibits no schedule-dependent behaviour.
· Accept: compilation fails on any instantaneous cycle; §15 admission-test-3 (*no hidden state survives a partition switch*) is discharged by construction for this tier.
· Trace: CJ-VELUS, CJ-NI · [§5](verification-maximal-os.md#r-05-055)

**R-05-056** IS: Control-tier state is statically allocated, making the §13 temporal-safety certificate trivial for this tier.
· Accept: no control-plane node allocates at runtime.
· Trace: CJ-VELUS · [§5](verification-maximal-os.md#r-05-056)

**R-05-057** MUST: Data-plane logic (bulk I/O, vector/matrix math, wire parsing) is `#![forbid(unsafe_code)]` Rust.
· Accept: every data-plane crate carries the attribute with no exception.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-057)

### 5.10 Crypto

**R-05-058** IS: Post-quantum primitives are the default: ML-KEM for key establishment, ML-DSA for signatures.
· Accept: no protocol in §12 negotiates a classical-only key establishment as its primary path.
· Trace: CJ-CRYPTO-SPEC · [§5](verification-maximal-os.md#r-05-058)

**R-05-059** MUST: Every crypto primitive carries all three assurance layers: functional correctness, constant-time, and reduction-level security.
· Accept: the crypto inventory has three evidence entries per primitive; a primitive missing any layer is not shipped.
· Trace: CJ-CRYPTO-SPEC, CJ-REDUCTION, CJ-CT-SOUND · [§5](verification-maximal-os.md#r-05-059)

**R-05-060** MUST: Classical field arithmetic is Fiat-Crypto (Coq-native).
· Accept: every field-arithmetic implementation traces to a Fiat-Crypto derivation.
· Trace: CJ-CRYPTO-SPEC · [§5](verification-maximal-os.md#r-05-060)

**R-05-061** IS: libcrux/HACL\* for PQ primitives is an explicitly interim F\*/Z3 widening with a named Coq-native destination, not an open-ended tolerance.
· Accept: the interim register entry (R-05-022) names the destination and the retirement condition.
· Trace: CJ-CRYPTO-SPEC · [§5](verification-maximal-os.md#r-05-061)

**R-05-062** MUST: Constant-time is a 2-safety hyperproperty verified directly on the binary for every secret-touching artifact, the crypto core included.
· Accept: CT evidence is per-binary; no CT claim rests on source-level review or on the producer's identity.
· Trace: CJ-CT-SOUND, CJ-LEAK · [§5](verification-maximal-os.md#r-05-062)

**R-05-063** MUST NOT: No verified-compiler constant-time route exists; CT is never inherited from a compiler theorem.
· Accept: the CHERI-CompCert theorem statement contains no CT conjunct, and no artifact cites one.
· Trace: CJ-COMPCERT, CJ-CT-SOUND · [§5](verification-maximal-os.md#r-05-063)

**R-05-064** MUST NOT: The CryptOpt-style route (untrusted superoptimizer plus a net-new Coq-verified assembly↔Fiat-Crypto equivalence checker) is deleted, not deferred. What goes with it is a net-new Coq equivalence-checker development, the checker-admitted-artifacts TCB category, and a §18 workstream, at the price of hand-assembly-grade ECC throughput. This list is canonical: every other section that observes the absence cites it rather than restating it.
· Accept: §18 carries no such workstream and the checker inventory contains no equivalence checker; the consequence list is stated once, so R-06-026 and R-18-022 cannot come to disagree with it.
· Trace: CJ-CRYPTO-SPEC · [§5](verification-maximal-os.md#r-05-064), [§5](verification-maximal-os.md#r-05-064-2)

**R-05-065** MUST NOT: Standing rule: any net-new verified artifact whose only yield is performance on a path already correct and already leak-free is inadmissible; the slower sound artifact is taken.
· Accept: every admitted net-new verified artifact has a stated yield other than performance.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-065)

**R-05-066** IS: The rule in R-05-065 targets *minting a checker*, not the asymmetric-trust pattern: an untrusted optimizer whose output the already-existing checkers re-validate is admissible and free to be arbitrarily aggressive.
· Accept: an optimizer is admissible iff its output is decided by an existing checker with no new checker introduced.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-066)

**R-05-067** MUST: Control-flow-heavy primitives (Keccak, AES, ChaCha, the ML-KEM/ML-DSA NTT and samplers) are written branchless on secrets using `Zicond` selects, hardened, and then verified on the artifact.
· Accept: each such binary passes the artifact-level CT check; no secret-dependent branch survives in the admitted binary.
· Trace: CJ-CT-SOUND, CJ-LEAK · [§5](verification-maximal-os.md#r-05-067)

**R-05-068** MUST: Where a lowering resists CT hardening, the fix is in the source; no hand-written or checker-admitted assembly leaf is introduced.
· Accept: the crypto build manifest contains no assembly leaf; a primitive that cannot be hardened is restructured or not shipped (fail-closed).
· Trace: CJ-CRYPTO-SPEC · [§5](verification-maximal-os.md#r-05-068)

**R-05-069** IS: Constant-time is carried by the move-II secret-taint attribute (a two-point lattice) where a type discipline suffices, and proved where it does not.
· Accept: each secret-touching binary is classified as type-decided or proof-discharged; both classes are non-empty only where the spec permits.
· Trace: CJ-CT-SOUND · [§5](verification-maximal-os.md#r-05-069)

**R-05-070** MUST: The CT type system rejects any secret-labeled value reaching a branch condition, a memory address, or a variable-latency operation outside the `Zkt`/`Zvkt` list.
· Accept: the typing rules enumerate the three rejection sites; the permitted-operation list is exactly the `Zkt`/`Zvkt` set from §15.
· Trace: CJ-CT-SOUND, CJ-LEAK · [§5](verification-maximal-os.md#r-05-070)

**R-05-071** MUST: The constant-time type-soundness metatheorem (CT-Wasm lineage) is restated in Coq over the §15 leakage model and joins the CHERI-TAL soundness proof.
· Accept: one Coq theorem; the TAL soundness statement includes the CT case.
· Trace: CJ-CT-SOUND, CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-071)

**R-05-072** MUST: The residual corner (unstructured secret-dependent code that does not type-check) is either branchless-hardened and re-typed, or discharged by a relational self-composition program logic over the leakage-annotated Sail semantics emitting a CIC-checked term.
· Accept: every non-type-checking secret path has one of the two dispositions recorded; none is waived.
· Trace: CJ-CT-SOUND, CJ-SAIL · [§5](verification-maximal-os.md#r-05-072)

**R-05-073** IS: Binsec/Rel is bounded symbolic-execution evidence and a bring-up gate, never the axiom; ct-verif is IR-level and does not satisfy the on-the-artifact statement.
· Accept: no CT claim's ground is a Binsec/Rel or ct-verif result.
· Trace: CJ-CT-SOUND · [§5](verification-maximal-os.md#r-05-073)

**R-05-074** IS: The CT obligation is scoped to secret-touching compartments, and the scope is defined by the *label on the material* rather than its channel of arrival: a compartment is secret-touching if it holds secret-labeled material however obtained: over an IDL confidentiality channel, through a capability-bounded DMA window or an RoT-latched re-delegated front end, or from a local entropy draw.
· Accept: the population includes the PIN and biometric paths §13's Tier-1 row names first, and it is exactly the population replay's entropy substitution is sound over (R-16-018). Narrower than the whole app population, wider than the IDL channel set.
· Trace: CJ-IDL, CJ-CT-SOUND · [§5](verification-maximal-os.md#r-05-074)

**R-05-075** MUST: Reduction-level security (IND-CCA for KEMs, EUF-CMA for signatures) is proved Coq-native in SSProve/FCF.
· Accept: each scheme has a Coq reduction; EasyCrypt results are accelerators with SSProve as the stated destination.
· Trace: CJ-REDUCTION · [§5](verification-maximal-os.md#r-05-075)

**R-05-076** IS: The three layers compose at the primitive's abstract functional specification, which is thereby a crown-jewel spec.
· Accept: each primitive's functional specification is in the crown-jewel inventory and is the shared object of the layer-1/2 refinement and the layer-3 game.
· Trace: CJ-CRYPTO-SPEC, CJ-REDUCTION · [§5](verification-maximal-os.md#r-05-076)

**R-05-077** IS: The reduction isolates and names the residual hardness assumptions (MLWE/MSIS; ECDLP/CDH) and cannot discharge them.
· Accept: each appears in the §17 axiom set `Ax`, not in the theorem set.
· Trace: CJ-REDUCTION · [§5](verification-maximal-os.md#r-05-077)

**R-05-077a** IS: The three layers carry a precondition on the entropy root rather than a conclusion about it: a reduction is stated over uniformly drawn keys, nonces, and blinding factors, and constant-time verification constrains a draw's observable behaviour and never its distribution, so a predictable root breaks IND-CCA and EUF-CMA while all three layers verify unchanged.
· Accept: the hypothesis is discharged where the root is (R-15-241a through R-15-241e, R-09-006a) rather than assumed by the reduction that consumes it, and its irreducible remainder is booked in R-17-049a; no crypto-layer claim states or implies that the root's quality follows from the layers.
· Trace: CJ-REDUCTION, CJ-CRYPTO-SPEC · [§5](verification-maximal-os.md#r-05-077a)

**R-05-078** MUST NOT: Protocol-level composition (TLS 1.3, WireGuard, the cellular AKA composition) is not claimed by the crypto layers.
· Accept: no crown-jewel theorem statement mentions a composed session-security property; the §3 Defended/Residual split records the exclusion.
· Trace: CJ-REDUCTION · [§5](verification-maximal-os.md#r-05-078)

### 5.11 Contained Rust and the verified HAL

**R-05-079** MUST: All Rust-authored app and server logic carries `#![forbid(unsafe_code)]` with no exception.
· Accept: the attribute is present in every contained crate; the exception count is zero.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-079)

**R-05-080** IS: The sole residual `unsafe` is in a minimal, formally verified HAL comprising the DMA, MMIO, and descriptor primitives.
· Accept: the set of `unsafe` blocks outside the HAL is empty.
· Trace: CJ-HAL · [§5](verification-maximal-os.md#r-05-080)

**R-05-081** MUST: The HAL's `unsafe` carries machine-checked memory-safety and hardware-contract proofs, not audit.
· Accept: each HAL primitive has a proof obligation discharged in Coq (or the equivalent FPCC discipline); no primitive is admitted on review alone.
· Trace: CJ-HAL · [§5](verification-maximal-os.md#r-05-081)

**R-05-082** MUST: A DMA or descriptor primitive returning a device-filled buffer establishes that buffer's *initialized* postcondition. The hardware contract the postcondition rests on is a crown-jewel spec: the HAL is proved against the contract and never against the device.
· Accept: every such primitive's contract contains the postcondition; the definite-initialization attribute (R-05-122) consumes it at the compartment edge.
· Trace: CJ-HAL, CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-082)

**R-05-082a** MUST: DMA submission consumes the caller's exclusive buffer capability and returns only a linear in-flight token; completion consumes that token and returns initialized CPU ownership, while a device-read transfer excludes CPU stores for the same interval.
· Accept: no HAL signature or CHERI-TAL derivation exposes CPU payload access while the corresponding device state owns the range, and no descriptor retains authority after completion.
· Trace: CJ-HAL, CJ-TAL-SOUND, CJ-RTL-SAIL · [§5](verification-maximal-os.md#r-05-082a)

**R-05-083** MUST: MMIO register field layouts are declared once in a register-description language, and the shift/mask field accessors are generated correct-by-construction and Coq-checked against that declaration.
· Accept: no hand-written bit-twiddling and no unverified template or macro layer appears in the HAL; every accessor traces to a declaration.
· Trace: CJ-HAL · [§5](verification-maximal-os.md#r-05-083)

**R-05-084** MUST: All contained Rust is compiled by the certifying userspace toolchain straight to native RV64+CHERI; the bare rustc/LLVM path is inadmissible.
· Accept: every admitted contained binary carries a certificate from the certifying toolchain.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-084)

**R-05-085** MUST NOT: Wasm/WASI is not an execution target anywhere in the system.
· Accept: no Wasm runtime, interpreter, or JIT exists in any image.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-085)

### 5.12 No ambient state

**R-05-086** MUST NOT: No module-level mutable state, no lazily-initialized statics, no thread-locals, and no hidden singletons.
· Accept: the checker's move-III scan finds no writable static reachable by name; interior-mutable statics and `thread_local!` are rejected at admission, not merely linted.
· Trace: CJ-TAL-SOUND, CJ-CERISE · [§5](verification-maximal-os.md#r-05-086)

**R-05-087** MUST: Every capability and every piece of mutable state a component uses is either a construction-time parameter or reachable only from a reference it was explicitly handed.
· Accept: the component's initial capability set, as recorded in the manifest, is the transitive root of all authority it exercises.
· Trace: CJ-CERISE · [§5](verification-maximal-os.md#r-05-087)

**R-05-088** IS: Immutable statics are untouched: `const` data and `static` of a type with no interior mutability are read-only-image data, covered by W^X.
· Accept: such statics reside in the read-only image and carry no tag.
· Trace: CJ-CERISE · [§5](verification-maximal-os.md#r-05-088)

**R-05-089** MUST: The binary-level statement is that a compartment's initial capability set is its whole authority: its static data section carries no tagged capability, and no writable object is reachable except from a capability the code was given.
· Accept: a one-pass scan of the image finds no tagged datum in the static data section; a set tag there is a type error.
· Trace: CJ-CERISE, CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-089)

**R-05-090** IS: Rust discharges the rule by `#![forbid(unsafe_code)]` plus a deny on interior-mutable statics and `thread_local!`; Lustre/Vélus discharges it by construction; the §12 IDL passes authority explicitly.
· Accept: each language path has a stated discharge; none relies on the source lint alone (R-05-089 is the binding check).
· Trace: CJ-VELUS, CJ-IDL · [§5](verification-maximal-os.md#r-05-090)

**R-05-091** MUST: The pre-admission boot substrate and M-mode firmware, being outside the admitted set, carry the no-ambient-state obligation as ordinary Tier-0 proof over their statically-planned state.
· Accept: the boot substrate's Tier-0 proof includes the obligation; it is not assumed to inherit the type-level rule.
· Trace: CJ-KERNEL · [§17](verification-maximal-os.md#r-05-091)

**R-05-092** IS: The rule forbids *re-manufacturing* a global and says nothing about *over-injecting* one: a component handed broad authority at construction and threading it everywhere is well-typed and over-privileged, and that residual is booked in §17.
· Accept: the §17 residual entry exists; no register requirement claims least-authority as a consequence of R-05-086.
· Trace: CJ-CERISE · [§5](verification-maximal-os.md#r-05-092), [§17](verification-maximal-os.md#r-05-092-2)

### 5.13 Certifying userspace compilation

**R-05-093** MUST: The userspace Rust→RV64+CHERI toolchain runs in certifying mode, emitting a machine-checkable memory-safety certificate with each binary.
· Accept: no contained binary is admitted without one.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-093)

**R-05-094** IS: That certificate is a CHERI-TAL typing derivation covering temporal safety, control-flow integrity, no-runtime-codegen, and ABI/type conformance, stated at binary level against the Sail model, and it is not full functional correctness.
· Accept: the certificate's four conjuncts are present; functional correctness remains a Tier-0/1 obligation.
· Trace: CJ-TAL-SOUND, CJ-SAIL · [§5](verification-maximal-os.md#r-05-094)

**R-05-095** IS: For admitted code, rustc and LLVM leave the intra-compartment memory-safety trust base.
· Accept: removing trust in rustc/LLVM invalidates no admitted binary's memory-safety claim.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-095)

### 5.14 Relevance grading: examined verdicts

**R-05-096** IS: Capabilities are linear/affine: contraction denied so authority cannot be duplicated, weakening allowed so it may be dropped.
· Accept: the TAL's context-splitting rules deny contraction on capability types.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-096)

**R-05-096a** MUST: Data-race freedom is an artifact-level exclusive-access theorem: for every non-atomic byte range, live writable authority excludes every overlapping load or store authority in another thread, compartment, or device state; duplicable aliases are read-only, and concurrently shared synchronization cells are explicitly atomic types.
· Accept: the CHERI-TAL soundness statement entails that no Sail execution of an admitted composition contains conflicting non-atomic accesses, so no sequence-counter retry, atomic `memcpy`, or byte-wise-atomic payload wrapper exists.
· Trace: CJ-TAL-SOUND, CJ-SAIL · [§5](verification-maximal-os.md#r-05-096a)

**R-05-096b** MUST: Exclusive access is checked compositionally: each binary's linear context proves its local splits and the manifest join rejects overlapping cross-compartment grants, with load/store typing requiring the matching capability permission and ownership state.
· Accept: an overlap fixture fails admission even when each component type-checks alone; a compromised admitted component has no well-typed instruction path that accesses a payload outside its ownership state.
· Trace: CJ-TAL-SOUND, CJ-CERISE · [§5](verification-maximal-os.md#r-05-096b)

**R-05-097** MUST: Fallible results are relevance-graded: weakening denied, contraction allowed, so every error verdict must be consumed at least once.
· Accept: a derivation that drops a relevance-graded value fails to type-check.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-097)

**R-05-098** IS: The scope of relevance grading is every result encoding whether an authority-, integrity-, or freshness-bearing action succeeded: attestation and appraisal verdicts, ECC and memory-authentication status, capability-derivation and revocation results, IDL call outcomes, admission-check verdicts, and storage-transaction commit results.
· Accept: each listed result type carries the grade in its IDL or ABI declaration; the list is closed by amendment to this register.
· Trace: CJ-IDL, CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-098)

**R-05-099** MUST: A wildcard bind on a relevance-graded type is a type error; discarding a verdict requires an explicit elimination that names the outcome.
· Accept: the typing rules reject `_`-binding at relevance-graded type; the typed discard form exists and is auditable.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-099)

**R-05-100** MUST NOT: There are no exceptions, no stack unwinding, and no `longjmp`: a typed absence in the TAL rather than a convention.
· Accept: the TAL has no unwinding construct; a failing compartment takes the §16 crash-only fail-stop and supervisor restart.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-100)

**R-05-101** IS: Relevance grading adds no runtime check, no silicon, no new semantic anchor, and no new crown jewel; it strengthens the statement of the CHERI-TAL soundness metatheorem.
· Accept: anchor count, crown-jewel count, and silicon area are unchanged by its adoption.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-101)

### 5.15 WCET

**R-05-102** MUST: WCET is derived syntax-directed as a max-path sum over the typed control-flow graph with loop bounds (Shaw's timing schema), carried as the move-II cost attribute (ℕ under max-and-plus).
· Accept: the bound is read off the typing derivation the on-device checker already validates; no separate analysis pass exists.
· Trace: CJ-WCET, CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-102)

**R-05-103** MUST: Per-instruction latency comes from the timing-annotated Sail model and is sound to the metal by RTL ⊑ Sail.
· Accept: every cost annotation traces to a Sail latency entry; no latency is asserted independently.
· Trace: CJ-WCET, CJ-RTL-SAIL · [§5](verification-maximal-os.md#r-05-103)

**R-05-104** MUST NOT: The Implicit Path Enumeration Technique and its LP solver are deleted, not retargeted.
· Accept: no ILP machinery exists in the toolchain or in §18.
· Trace: CJ-WCET · [§5](verification-maximal-os.md#r-05-104)

**R-05-105** MUST NOT: Standing no-tightening rule: any verified tool that exists only to tighten an already-sound bound is inadmissible; the trivial sound bound is taken.
· Accept: every admitted verified analysis tool has a yield other than tightness; pessimism is accepted without appeal.
· Trace: CJ-WCET, CJ-T · [§5](verification-maximal-os.md#r-05-105)

**R-05-106** IS: The rule in R-05-105 generalizes from bounds to artifacts, and the CryptOpt deletion (R-05-064) is the same rule applied to a tool rather than an estimate.
· Accept: both deletions cite one rule; neither is recorded as an independent judgment call.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-106)

**R-05-107** MUST: Loop bounds that resist syntactic inference are annotations discharged as Coq obligations against the source.
· Accept: each non-structural loop bound has a discharged obligation; none is asserted.
· Trace: CJ-WCET · [§5](verification-maximal-os.md#r-05-107)

**R-05-108** IS: Where code is produced by correct-by-construction relational compilation (Lustre/Vélus; Fiat/Bedrock/Rupicola synthesis), the per-node cost falls out of the compilation derivation, so the standalone max-path pass is needed only for hand-written imperative data-plane code.
· Accept: synthesized components carry costs from their derivations, not from a separate pass.
· Trace: CJ-WCET, CJ-VELUS · [§5](verification-maximal-os.md#r-05-108)

**R-05-109** IS: aiT is an unverified out-of-band cross-check only.
· Accept: no admitted bound cites aiT as its ground.
· Trace: CJ-WCET · [§5](verification-maximal-os.md#r-05-109)

**R-05-110** MUST NOT: MBPTA/EVT is inadmissible as the bound.
· Accept: no measurement-based statistic appears as a WCET input to §11 admission.
· Trace: CJ-WCET · [§5](verification-maximal-os.md#r-05-110)

**R-05-111** MUST: The standalone Coq-verified WCET estimator is retired from the §18 workstream list.
· Accept: §18 carries no such deliverable.
· Trace: CJ-WCET · [§5](verification-maximal-os.md#r-05-111)

### 5.16 Indirect control transfer and the typed callee set

**R-05-112** MUST: A call site reaches an indirect target only through a sentry capability it holds.
· Accept: the hardware permits no indirect transfer without a held sentry; under no-ambient-state, the sentries a site can name are exactly those wired to it or loaded from vtables it was given.
· Trace: CJ-CERISE · [§5](verification-maximal-os.md#r-05-112)

**R-05-113** MUST: Every indirect transfer's code type carries the finite set of labels its reachable sentries target, and the typing rule confirms the jump stays within that set.
· Accept: one subset check per indirect transfer in the derivation.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-113)

**R-05-114** MUST: The callee set is read off the sealed image at compose time, not over-approximated by a points-to analysis.
· Accept: with the on-device loader deleted and no dynamic linking, the address-taken set and the per-vtable impl set are fixed at compose time.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-114)

**R-05-114a** MUST: At composition, every indirect call with exactly one typed callee or cross-compartment manifest target is replaced by a direct call unless doing so would grow the admitted image, and its now-unused dispatch machinery is deleted, while sentry and seal/switch semantics are preserved; the transform MUST NOT clone, specialize, monomorphize, or duplicate.
· Accept: every singleton site is direct or has an image-size witness for remaining indirect; no rewritten cross-compartment edge bypasses its manifest-authorized sentry transition, and no rewrite creates a function-body or trampoline clone.
· Trace: CJ-TAL-SOUND, CJ-MEMPLAN · [§5](verification-maximal-os.md#r-05-114a)

**R-05-115** IS: Closures, function pointers, and `dyn Trait` survive unrestricted; a first-order source-language mandate and defunctionalization are rejected.
· Accept: no source-language restriction on higher-order constructs exists.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-115)

**R-05-116** IS: The load-bearing consumer of the callee set is bound *existence*, not tightness: without it, call-graph acyclicity is unprovable and neither the max-path sum nor the live-range colouring yields a bound at all.
· Accept: the tighter per-site cost is recorded as a byproduct; the no-tightening rule (R-05-105) governs it.
· Trace: CJ-MEMPLAN, CJ-WCET · [§5](verification-maximal-os.md#r-05-116)

**R-05-117** IS: Scope is per compartment: cross-compartment sentry edges stay outside the typed set and are governed by the manifest's import/export tables and the §12 IDL.
· Accept: no whole-program typing obligation exists; the system call graph is the composition of per-compartment graphs with manifest edges.
· Trace: CJ-IDL · [§5](verification-maximal-os.md#r-05-117)

**R-05-118** MUST: A compiler that cannot enumerate a site's callee set refuses the binary rather than under-declaring it.
· Accept: the failure mode is refusal; the completeness residual is booked in §17.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-118)

### 5.17 Definite initialization

**R-05-119** MUST: No load reads a slot before a store to it, decided at admission as a move-II attribute rather than trapped at runtime.
· Accept: the derivation carries an initialization flag per slot; a load whose premise is unmet fails to type-check.
· Trace: CJ-TAL-SOUND, CJ-MEMPLAN · [§5](verification-maximal-os.md#r-05-119)

**R-05-120** MUST NOT: No hardware Write-before-Read metadata plane exists.
· Accept: the §15 memory subsystem carries no initialization-tag plane, no associated DECTED coverage, no Sail invariant, and no RTL ⊑ Sail obligation for one.
· Trace: CJ-RTL-SAIL · [§5](verification-maximal-os.md#r-05-120), [§5](verification-maximal-os.md#r-05-120-2)

**R-05-121** IS: The attribute domain is the two-point lattice *uninitialized* ⊑ *initialized*, met at control-flow merges: a store sets its slot's flag, a load's typing premise is that the flag is set, and a merge takes the meet.
· Accept: the rule is local and syntax-directed; the domain is finite; no open-term reduction occurs.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-121)

**R-05-122** IS: Each slot's *uninitialized* point is §7's plan's own allocation point, not a runtime event.
· Accept: initialization is exactly as static as the slot plan.
· Trace: CJ-MEMPLAN · [§5](verification-maximal-os.md#r-05-122)

**R-05-123** MUST: Device-written memory is covered by the verified HAL's DMA and descriptor postconditions (R-05-082), not by a tag the fabric sets.
· Accept: every device-fill path terminates in a HAL primitive whose contract establishes *initialized*.
· Trace: CJ-HAL · [§5](verification-maximal-os.md#r-05-123)

**R-05-124** MUST: Initialization state crossing a compartment edge rides the §12 IDL message type and the manifest's import/export tables, with copy-once parsers writing their fixed destination buffers whole.
· Accept: no delegated buffer arrives without a declared initialization state.
· Trace: CJ-IDL, CJ-FORMAT · [§5](verification-maximal-os.md#r-05-124)

**R-05-125** IS: The outcome is fail-closed at admission (a type error refused), not fail-stop at runtime (a trap).
· Accept: no runtime uninitialized-read trap exists in the platform.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-125)

**R-05-126** MUST: Memory is eager-zeroized at allocation, so an unwritten slot reads a deterministic zero rather than residue.
· Accept: the §7 zeroize discipline covers every slot; `Zicboz` (`cbo.zero`) is in the §15 profile.
· Trace: CJ-MEMPLAN, CJ-SAIL · [§15](verification-maximal-os.md#r-05-126); constrains R-15-*

### 5.18 Use-once, must-erase, and dimension: three re-uses of the existing grades

**R-05-126a** IS: Three obligations ride the grades the CHERI-TAL already carries rather than new axes: a nonce is use-once (the linear grade), a secret is must-erase (the relevance grade), and a quantity carries its dimension (a phantom parameter under syntactic type equality).
· Accept: each is shown against R-05-132 clause 2 as a new use of an existing grade or of type equality; no grade or label axis is added, and each is decided at admission by the §6 type-checker.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-126a)

**R-05-126b** MUST: A nonce-typed value carries the linear grade: it is consumed by the operation that seals under it, and cannot be duplicated, stored for later, or reached twice.
· Accept: contraction is denied on nonce-typed values, so a binary that reaches one twice fails to type-check and is refused at admission.
· Trace: CJ-TAL-SOUND, CJ-CRYPTO-SPEC · [§5](verification-maximal-os.md#r-05-126b)

**R-05-126c** MUST: A restored checkpoint and a re-derived key each force a fresh draw, the linear obligation carrying the two cases rather than the §10 exclusion list being read.
· Accept: no admitted path reaches a nonce that a checkpoint restore or a key re-derivation reinstated.
· Trace: CJ-TAL-SOUND, CJ-CRYPTO-SPEC · [§5](verification-maximal-os.md#r-05-126c)

**R-05-126d** MUST: A secret-typed value carries the relevance grade: it must be consumed by an erasing operation, and the obligation is checked on the final binary so that it reaches scalar registers and compiler-introduced spill slots the partition switch does not clear.
· Accept: weakening is denied on secret-typed values; the check is stated over the emitted binary, not the source.
· Trace: CJ-TAL-SOUND, CJ-CT-SOUND · [§5](verification-maximal-os.md#r-05-126d)

**R-05-126e** IS: Restart discharges the erasure obligation wholesale, a crash-only compartment erasing its whole footprint, so the rule binds the path that returns while holding a secret.
· Accept: the obligation is stated over returning paths; a restarting compartment carries no separate scrub proof.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-126e)

**R-05-126f** MUST: Physical quantities carry their dimension as a phantom parameter on the existing type formers, decided by syntactic type equality and erased before code generation.
· Accept: the parameter is inhabited by no term, adds no runtime representation, and is decided by the same structural comparison R-05-129 fixes.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-126f)

**R-05-126g** MUST: The monotonic scheduler counter and the disciplined wall-clock view are distinct dimensions, as are cycles and microseconds, bytes and elements, and a slot index and a slot width; the §11 admission arithmetic consumes the dimensioned types.
· Accept: a §11 budget, frame, or deadline computation mixing two dimensions fails to type-check rather than yielding an unsound admission.
· Trace: CJ-WCET, CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-126g)

**R-05-126h** IS: The cost of the three is one further narrowing of the admitted library set: no runtime check, no silicon, no new semantic anchor, no new grade axis, and no new crown jewel, each adding one rule to the CHERI-TAL and one case to its soundness metatheorem.
· Accept: no §15 mechanism, Sail surface, or crown-jewel target is added; the three are shown to fit the frozen theory exactly as its other riders are.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-126h), [§5](verification-maximal-os.md#r-05-126h-2)

**R-05-126i** IS: A grade binds the label, never the judgment that assigned it: a value never typed as a nonce, a secret never labeled one, or a quantity given the wrong dimension is admitted with the obligation discharged and the property absent.
· Accept: the residual is booked in §17 as the wrong-label case, the same shape as the mislabeled-secret residual of the constant-time discipline; what the three delete is the unenforced-obligation class.
· Trace: CJ-TAL-SOUND · [§17](verification-maximal-os.md#r-05-126i)

### 5.19 The frozen checker theory, and the language it lives in

**R-05-127** IS: The on-device checker is an attribute-grammar evaluator, not a term checker, and its order-of-10³-line budget is a consequence of that category fact.
· Accept: the checker evaluates a fixed attribute set bottom-up over the already-typed CFG with no fixpoint over open terms anywhere, and the shipped source meets the counting rule [typed-assembly-language.md](typed-assembly-language.md) states, cited here rather than restated. A checker that met the figure by moving decisions into a generated table fails the claim, the category fact being what the budget asserts.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-127)

**R-05-128** MUST NOT: Absence (1): polymorphism is predicative and rank-1 prenex only: type variables quantified at the outermost position of a code type and instantiated only at monotypes.
· Accept: no impredicative self-instantiation and no rank-*n* inference appears in the theory.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-128)

**R-05-129** MUST NOT: Absence (2): no type-level computation. Type equality is syntactic (α-equivalence over first-order terms), with no βδιζη-reduction, no normalizer, and no evaluation of open terms.
· Accept: the checker's termination argument is syntactic; no strong-normalization premise lives inside it.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-129)

**R-05-130** MUST NOT: Absence (3): no universes and no universe polymorphism: one sort of types, no cumulativity, no universe-constraint graph.
· Accept: the checker contains no acyclicity solver.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-130)

**R-05-131** MUST NOT: Absence (4): no user-extensible inductive definitions. The type-constructor vocabulary is fixed and closed by the pinned language specification (R-05-135a), and grows only by amendment to it, never at install time.
· Accept: no positivity check, no guard condition, and no eliminator generation exists in the checker; the vocabulary is the closed set that specification fixes, cited here rather than restated, so the two cannot come to disagree.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-131)

**R-05-132** MUST: A proposed attribute is admitted only on a shown demonstration that it (1) has a finite semilattice/monoid domain decided with no open-term reduction and preserves syntactic type equality, (2) duplicates no existing grade or label axis, and (3) has a local syntax-directed rule.
· Accept: each attribute's amendment record carries three shown arguments.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-132)

**R-05-133** IS: A feature that fails R-05-132 descends to the CIC proof kernel as a release-time proof term rather than widening the theory, at the price of ceasing to be per-install checkable.
· Accept: the rejected feature appears in the release-time obligation set, not in the attribute set.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-133)

**R-05-134** IS: The frozen theory binds the checker, not the producer: the certifying compiler may be written in and reason with any theory, since only the shipped derivation must be checkable in this one.
· Accept: no constraint on producer-side theory appears in the admission rules.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-134)

**R-05-135** IS: The only computation the checker performs is bounded-width arithmetic over closed numerals (WCET literal sums and comparisons; overflow range side conditions), decided in constant time per node.
· Accept: no rule requires reduction of open terms; anything that would descends under R-05-133.
· Trace: CJ-TAL-SOUND, CJ-WCET · [§5](verification-maximal-os.md#r-05-135)

**R-05-135a** IS: The type theory (R-05-127 to R-05-135), the obligation menu, the machine-profile parameter, and the soundness statement are specified in [typed-assembly-language.md](typed-assembly-language.md), a target-parameterized language this platform *depends on* rather than a component of it. CHERI-TAL is that language's `cheri-rv64` instantiation, and the factoring renames nothing.
· Accept: the language document states the theory, the menu, and the profile rule; this register states which instantiation and which obligations this platform requires (R-05-029); neither restates the other's list.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-135a)

**R-05-135b** MUST: A generation is checked against a named, pinned version of the language specification and its profile, and a version bump is a review-gate event carrying a fresh reading of the soundness metatheorem, never a transparent upgrade.
· Accept: the generation names the language version and profile its checker implements, and a review record exists for that version; no generation is admitted against an unpinned or un-re-reviewed one.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-135b)

**R-05-135c** MUST: This platform's profile is `cheri-rv64`, which cites spatial memory safety, no-runtime-codegen, and the run-time half of control-flow integrity as architectural. No obligation of R-05-029 is discharged here by inserted run-time checks.
· Accept: every cited invariant is a theorem of the §15 Sail model rather than a claim about an implementation, and no admitted derivation carries an inserted-check discharge.
· Trace: CJ-TAL-SOUND, CJ-CERISE, CJ-SAIL · [§5](verification-maximal-os.md#r-05-135c)

**R-05-135d** IS: Factoring the language out relocates the work rather than reducing it, and substitutes a version seam for an amendment process: a theory frozen in this corpus is frozen by its own review gate, and a theory frozen in a dependency is frozen by R-05-135b's pin.
· Accept: the residual is booked in §17 as the dependency seam, and no §18 deliverable is reduced by the factoring.
· Trace: CJ-TAL-SOUND · [§17](verification-maximal-os.md#r-05-135d)

### 5.20 Representation and provenance: five deletions

**R-05-136** MUST NOT: (1) No integer→capability provenance: no integer-to-pointer cast, no address literal that becomes a capability, and no reconstruction of a capability from its bit pattern. The only capability-producing operations are the monotone derivations (bounds and permission restriction, sealing) applied to a capability already held.
· Accept: the checker finds no integer inhabiting a capability type; the derivation's capability-producing rules are exactly the monotone set.
· Trace: CJ-CERISE, CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-136)

**R-05-137** IS: The provenance disjunct is consequently deleted from the CHERI-C/CompCert memory model, which is left monotone with no exposed-address state.
· Accept: the verified-C memory model carries no PNVI-style provenance case.
· Trace: CJ-COMPCERT · [§5](verification-maximal-os.md#r-05-137)

**R-05-138** MUST: The verified HAL reaches a device register from a root device capability handed in at construction, never from a hard-coded physical address, so the RoT-attested devicetree is the sole origin of device authority.
· Accept: no physical-address literal appears in the HAL; every device capability traces to the devicetree.
· Trace: CJ-DEVTREE, CJ-HAL · [§5](verification-maximal-os.md#r-05-138)

**R-05-139** MUST NOT: (2) No unions and no type punning: no load at a type other than its store's.
· Accept: the load rule has exactly one case; the checker rejects any load whose type differs from its store's.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-139)

**R-05-140** MUST: The only admitted reinterpretation of bytes at a second type is a proved encode/decode pair derived from a declaration: the register-description language for MMIO, Narcissus for every wire format.
· Accept: every reinterpretation site traces to a generated accessor or a Narcissus codec.
· Trace: CJ-HAL, CJ-FORMAT · [§5](verification-maximal-os.md#r-05-140)

**R-05-141** MUST NOT: (3) No variadic functions: a TAL code type is a register-file precondition and a variadic has none, so the construct is untypable rather than discouraged.
· Accept: no code type has non-fixed arity.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-141)

**R-05-142** IS: Runtime format-string interpretation dies structurally with the variadic mechanism; the §16 bounded labeled crash record and the §12 diagnostics carry structured typed fields instead.
· Accept: no runtime format interpreter exists in any image.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-142)

**R-05-143** MUST: (4) Every recursive type former declares a length or depth bound: bounded vectors and bounded trees, no list of unknown length, no arbitrarily deep tree.
· Accept: the checker finds no recursive former lacking its bound; the declared bound is a sound existence condition and is not sharpened (R-05-105).
· Trace: CJ-MEMPLAN, CJ-WCET · [§5](verification-maximal-os.md#r-05-143)

**R-05-144** MUST NOT: (5) No implicit integer conversion: every width and signedness change is an explicit named operation.
· Accept: sign extension and truncation appear in the derivation, never in a compiler's promotion rules.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-144)

**R-05-145** MUST: Arithmetic is total by typing: neither trapping nor wrapping. Overflow-freedom rides as range side conditions on the existing arithmetic rules.
· Accept: no arithmetic operation traps; no operation wraps implicitly; each arithmetic rule carries its range side condition.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-145), [§5](verification-maximal-os.md#r-05-145-2)

**R-05-146** MUST: Overflow side conditions are decided in the §6 checker wherever the operands' bounds are closed numerals, and descend to the CIC proof kernel as a release-time obligation wherever a bound depends on a runtime value.
· Accept: each arithmetic site has one of the two dispositions recorded; none is waived.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-146)

**R-05-147** IS: Modular and saturating arithmetic survive as explicitly named operations; what is deleted is the implicit wrap.
· Accept: the operation vocabulary contains named wrapping and saturating forms.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-147)

**R-05-148** MUST: All five deletions are carried to the artifact, not left as source lints: each is decidable by inspection of the derivation.
· Accept: the checker decides all five without reference to source.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-148)

**R-05-149** IS: The cost of the five is one further narrowing of the admitted library set: no runtime check, no silicon, no new semantic anchor, no new grade axis, and no new crown jewel.
· Accept: anchor count, grade-axis count, crown-jewel count, and silicon area are unchanged.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-149)

**R-05-149a** MUST: Where a collection is one exact-bounded object whose elements share one authority, revocation domain, and lifetime, its admitted representation uses one exact-bounded base capability plus 32/64-bit indices rather than one capability per interior element, but only where doing so removes capability-valued fields without adding shadow metadata or a reconstruction table and without increasing generated code or data.
· Accept: source or the existing IDL/layout declaration contains one exact-bounded base capability; independently bounded, authorized, revocable, or lived objects remain separate; no auxiliary representation is introduced; generated code and data do not grow; and index arithmetic discharges R-05-145/R-05-146.
· Trace: CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-149a)

### 5.21 The review gate

**R-05-150** MUST: Independent specification review is a release gate.
· Accept: no release proceeds without a completed independent review of the register.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-150)

**R-05-151** MUST: A companion atomic-requirements register exists, in which each normative obligation is a numbered, individually-reviewable requirement with its acceptance criterion, traced to the crown-jewel spec it constrains and to the prose as rationale.
· Accept: **this document**. All eighteen normative sections are extracted; whether every obligation *within* them is captured is itself the first question the review gate asks, and the register is the artifact that makes the question answerable.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-151)

**R-05-151a** MUST: The register's traces to the prose are decided mechanically rather than by reading: every bookmark a trace cites resolves exactly once in the prose, every requirement carries a trace, every `r-*` bookmark in the prose names a live requirement, and the section a trace displays is the section its bookmark sits in.
· Accept: `tools/check.ps1` decides all four and exits non-zero on any finding. A symbolic reference cannot go *stale*, but it can be absent, misspelled, or duplicated, and a dangling Markdown anchor fails silently, so the check is what keeps the reference discipline honest rather than merely well-intentioned. Each property is negative-tested against a deliberately broken copy (a mistyped anchor, a duplicated bookmark id, a deleted trace line, a bookmark naming a retired ID, a display section disagreeing with its target), because a checker that has never failed is indistinguishable from one that cannot. It checks *reference*, not *fidelity*: a trace landing on prose that does not support its requirement is a review-gate finding against R-05-151.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-151)

**R-05-152** IS: The gate audits the register; the prose specification is commentary rather than the thing reviewed.
· Accept: the review record cites requirement IDs, not prose sections.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-152)

**R-05-153** MUST: A normative claim that cannot be restated as an atomic, testable requirement is treated as a spec defect.
· Accept: each such claim appears in [Extraction defects](#extraction-defects) with a disposition; none is carried as unregistered prose.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-153)

**R-05-154** MUST: Maintaining the register and its traceability to the Coq specifications and the Sail model is a §18 workstream.
· Accept: §18 lists it as a deliverable with an owner, R-18-034.
· Trace: CJ-T, CJ-SAIL · [§5](verification-maximal-os.md#r-05-154)

**R-05-155** MUST: The foundational-C separation-logic specifications (kernel, storage, HAL) are made runtime-testable in concrete execution under the Fulminate discipline for CN.
· Accept: each such specification has an executable form run against the implementation; a mis-transcribed specification is caught by execution and not by review alone.
· Trace: CJ-KERNEL, CJ-HAL · [§5](verification-maximal-os.md#r-05-155)

### 5.22 The apex theorem T

**R-05-156** IS: Theorem T: for the composed system image on the fabricated die, under the compose-time policy *P*, for every adversary controlling any set *C* of non-TCB compartments the graph permits, two whole-system inputs indistinguishable to *C* under *P* produce attacker-observations equal across value, timing, and the in-scope architectural channels, modulo the powerbox declassification set *D* and relative to the axiom set *Ax*. The statement is itself a crown-jewel spec: a proof of T establishes that T holds, never that T is the property wanted.
· Accept: one theorem statement exists with all four elements: the quantifier over *C*, the value-and-timing-and-architectural observation, the *modulo D* clause, and the *relative to Ax* clause.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-156)

**R-05-157** IS: T is the formal reading of *hyper-secure* (§1) and of G2; *on the fabricated die* is what makes it a statement about the machine rather than the model.
· Accept: §1's and §3's claims cite T; no stronger informal claim appears anywhere in the specification.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-157)

**R-05-158** MUST: T is discharged by transporting it down the refinement tower and closing the property seams across it, in the one Iris-over-Sail program logic.
· Accept: the tower is exactly source ⊑ spec ⋈ binary ⊑ source robustly ⋈ binary-against-Sail ⋈ RTL ⊑ Sail ⋈ die-matches-RTL, the last an axiom and the rest theorems.
· Trace: CJ-T, CJ-RTL-SAIL · [§5](verification-maximal-os.md#r-05-158)

**R-05-159** IS: Four unary invariants form the substrate every seam assumes: spatial safety (the Cerise universal contract), temporal safety (revocation ⋈ the CHERI-TAL linear-capability discipline), W^X (no write-and-execute capability in the derivation forest), and write-before-read (the definite-initialization attribute over eager-zeroized memory).
· Accept: each is separately stated and proved; the first three are carried by the substrate, the fourth by the admission type-check.
· Trace: CJ-CERISE, CJ-TAL-SOUND · [§5](verification-maximal-os.md#r-05-159)

**R-05-160** IS: The seam lemmas are exactly nine: NI ⋈ timing; WCET ⋈ isolation; CT ⋈ RTL ⊑ Sail; CHERI-TAL ⋈ Sail; AE ⋈ non-interference; liveness ⋈ schedulability; consent ⋈ declassification; crypto ⋈ hardness; attestation ⋈ capability safety.
· Accept: each appears as a §17 residual and as a lemma obligation; the list is closed by amendment to this register.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-160)

**R-05-161** MUST: The composition meta-lemma states that the four invariants and the seam lemmas, transported through the refinement tower, entail T, and carries its own coverage obligation: no attacker-observable channel, authorized flow, timing leak, liveness stall, or admitted binary escapes their union, and each seam's conclusion is stated in the vocabulary of the next's premise.
· Accept: the coverage argument is written and reviewed; each seam's interface types are shown to meet.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-161)

**R-05-162** MUST: T's boundary is stated rather than hidden: it holds modulo *D* and relative to *Ax*, the hardness conjectures, the die-matches-RTL fabrication gap, specification faithfulness, human consent correctness, and invasive physical attack.
· Accept: each boundary element is a §17 residual; everything outside *D* and *Ax* is inside T.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-162)

### 5.23 Proof-artifact hygiene

**R-05-163** MUST: Every shipped theorem's axiom and assumption set is enumerated mechanically from its proof term and compared against the declared set, and the build fails wherever the enumerated set is not exactly the declared one.
· Accept: an admitted lemma, an unresolved obligation, a locally declared parameter, or any axiom absent from the declared set fails the build rather than shipping green, and an extra axiom is a finding even where every theorem is true. The gate is a predicate over the proof term: it adds no semantic anchor (R-05-020), no runtime mechanism, and no Sail surface.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-163)

**R-05-164** MUST: The declared set is read from this register rather than from the development: it is the admission axioms of R-06-011, the bootstrap root of R-06-014, and the *Ax* boundary ledger of R-18-031.
· Accept: a proof needing an axiom the register does not carry is an amendment to R-06-011 or to the *Ax* ledger, decided at the review gate; adding a declaration inside the development to make R-05-163 pass is a review-gate finding against R-05-150.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-164)

**R-05-165** IS: A theorem can be true and empty in exactly three ways, each of which verifies perfectly: a premise nothing satisfies, a specification permissive enough that any implementation refines it, and a quantifier ranging over an uninhabited domain.
· Accept: this is the degenerate case of R-05-150's own reason for existing, and the case review is worst at catching, the defect lying in what the statement fails to exclude rather than in what it says.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-165)

**R-05-166** MUST: Every shipped theorem carries a non-vacuity witness: a machine-checked inhabitation witness for its hypotheses, plus, where it is a refinement or a policy statement, a distinguishing instance its specification rejects.
· Accept: vacuity is not decidable in general, so the obligation is per-theorem and constructive rather than a further checker; a theorem shipped without its witnesses is refused by the same build gate as R-05-163. The reference composition serves as the inhabitation witness wherever one exists.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-166)

**R-05-167** IS: R-05-163 and R-05-166 are preconditions on every claim the specification discharges by a machine-checked theorem, T included, rather than properties standing beside them.
· Accept: a theorem resting on an undeclared axiom has not established what its citation claims, and a vacuously true one has established nothing; citing a theorem that fails either gate as discharging an obligation is a review-gate finding.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-167)

**R-05-168** MUST: Both gates are day-one deliverables under R-18-003b and gate on nothing.
· Accept: the assumption gate is a predicate over whatever proof artifact exists, so it is wired ahead of the first closing theorem and grows with the development; the witness obligation is a specification act like the statement of T itself.
· Trace: CJ-T · [§5](verification-maximal-os.md#r-05-168)

---

## §6. Trusted Computing Base

### 6.1 The exhaustive inventory

**R-06-001** IS: The TCB is exhaustively enumerated as seven items: the capability microkernel; the verified crypto core; the system-integrity reader and A/B update transactor; minimal verified M-mode firmware; the open silicon RoT and its firmware; the two admission checkers; and the powerbox with the trusted-path agent.
· Accept: nothing outside the list is trusted; an eighth item is an amendment to this register.
· Trace: CJ-T · [§6](verification-maximal-os.md#r-06-001)

**R-06-002** IS: The capability microkernel is on the order of 10k LoC of verified C.
· Accept: the line count is a stated budget against the §7 target.
· Trace: CJ-KERNEL · [§6](verification-maximal-os.md#r-06-002)

**R-06-003** MUST: The verified crypto core (boot verification, attestation, sealing) is verified C end to end: compiled through CHERI-CompCert, constant-time verified on the artifact, field-arithmetic kernels compiled the same way, reductions Coq-native in SSProve/FCF.
· Accept: no component of the core is admitted as superoptimized assembly.
· Trace: CJ-CRYPTO-SPEC, CJ-COMPCERT · [§6](verification-maximal-os.md#r-06-003)

**R-06-004** MUST NOT: The TCB carries no *checker-admitted artifacts* category at all: the category is deleted with the kernels that motivated it rather than left unused.
· Accept: every TCB component is compiler-borne under the single Coq prover.
· Trace: CJ-COMPCERT · [§6](verification-maximal-os.md#r-06-004)

**R-06-005** MUST: The system-integrity reader runtime-verifies every read of the content-addressed base image against the signed, boot-attested root (Merkle read-verify), and the A/B transactor commits an update as an atomic two-slot root flip past the anti-rollback floor.
· Accept: the component is on the order of 10× smaller than a filesystem; no read of the base image bypasses the check.
· Trace: CJ-DEVTREE · [§6](verification-maximal-os.md#r-06-005)

**R-06-006** MUST: The entire four-layer storage stack is non-TCB, the read-only system image and the mutable user subvolumes alike, its journal and CoW B-tree serving bytes the reader re-verifies.
· Accept: a corrupt or hostile filesystem is caught by the signed root and is never trusted for integrity.
· Trace: CJ-DEVTREE · [§6](verification-maximal-os.md#r-06-006)

**R-06-007** IS: Minimal verified M-mode firmware and the open silicon RoT (OpenTitan-class, integrated on-die) with its firmware are TCB items.
· Accept: both appear in the inventory with their verification evidence.
· Trace: CJ-DEVTREE · [§6](verification-maximal-os.md#r-06-007)

### 6.2 The two admission checkers

**R-06-008** IS: Admission is two checkers, stratified: the CHERI-TAL type-checker runs on every install over typing derivations; the CIC proof kernel runs on every install for source correspondence and predominantly at release time over deep proof terms, whose result is bound into the measured-boot root.
· Accept: no third checker exists; every install invokes the CIC kernel for exactly the local correspondence proof plus any additional certificate the package carries (R-13-028).
· Trace: CJ-TAL-SOUND · [§6](verification-maximal-os.md#r-06-008)

**R-06-009** IS: The TAL type-checker decides **the eleven type-level obligations of R-05-029** (every move-(I) citation, move-(II) attribute, and move-(III) deletion) plus closed-numeral overflow side conditions and the memory/ABI half of Tier 1. This row cites R-05-029 rather than restating it.
· Accept: its ~10³-line budget is a consequence of the frozen theory (R-05-127), and its decided set is read off R-05-029 rather than enumerated here, so the two cannot disagree.
· Trace: CJ-TAL-SOUND · [§6](verification-maximal-os.md#r-06-009)

**R-06-010** IS: The CIC proof kernel decides every binary's source-correspondence theorem plus Tier-0 functional refinement, the non-interference theorem, crypto reductions, filesystem certificates, and residual unstructured constant-time and WCET cases.
· Accept: the per-install correspondence proof is artifact-local; seL4-scale composition proofs remain release-time work.
· Trace: CJ-NI, CJ-REDUCTION · [§6](verification-maximal-os.md#r-06-010)

**R-06-011** IS: The admission axioms are the two checkers, the spec and policy statements, the CHERI-TAL soundness metatheorem, and the Sail model they check against.
· Accept: the axiom inventory has exactly these entries plus the De Bruijn bootstrap root (R-06-014), and this is the specification's single statement of it: R-05-028 is scoped to the proof-carrying-code path and says so, so the two are no longer competing enumerations. R-05-163 is what decides agreement with the shipped proof artifacts mechanically rather than by inspection.
· Trace: CJ-TAL-SOUND, CJ-SAIL · [§6](verification-maximal-os.md#r-06-011)

**R-06-012** MUST: Both checkers are built like the rest of the TCB: the CIC kernel's MetaCoq-style Gallina checker and the TAL type-checker alike are refined to CompCert-C (VST/Iris) and compiled through CHERI-CompCert.
· Accept: neither is extracted via the unverified MetaCoq→Rust backend onto the untrusted userspace toolchain; that toolchain is admissible only for contained code whose binary a checker re-validates, and the checkers' own binaries are re-validated by nothing.
· Trace: CJ-COMPCERT · [§6](verification-maximal-os.md#r-06-012)

**R-06-013** IS: The checkers' compilation is not a fresh axiom: it rides the same CompCert already in the trust base.
· Accept: the axiom count is unchanged by their compilation.
· Trace: CJ-COMPCERT · [§6](verification-maximal-os.md#r-06-013)

**R-06-014** IS: The one irreducible residual is the bootstrap: the checkers are the admitters no admission certificate can cover, and they co-bootstrap with the CompCert that compiles them, so their binaries' trust rests on reproducible build plus DDC plus RoT measurement into the boot chain: the De Bruijn root, named as an axiom rather than hidden.
· Accept: the axiom is stated in §6 and §17, not implied.
· Trace: CJ-T · [§6](verification-maximal-os.md#r-06-014)

**R-06-015** IS: The toolchain is untrusted evidence-producing machinery: a compromised compiler cannot mint a valid proof of a property its output lacks, so at worst it emits a binary genuinely satisfying the spec, confining trojans to spec slack.
· Accept: this is why Tier-0 specs are full refinements (R-13-011).
· Trace: CJ-COMPCERT · [§6](verification-maximal-os.md#r-06-015)

### 6.3 The consent TCB

**R-06-016** IS: The powerbox is the sole runtime declassifier, and the trusted-path agent is the small component that owns its consent UI and drives the RoT secure-attention indicator.
· Accept: no other component mints a capability edge at runtime.
· Trace: CJ-NI · [§6](verification-maximal-os.md#r-06-016)

**R-06-017** MUST: Their load-bearing correctness obligation is exactly two clauses: mint only on witnessed consent, and bound the mint to the named object.
· Accept: both clauses are proved; the §8 non-interference theorem's *user-authorized* flows rest on them.
· Trace: CJ-NI · [§6](verification-maximal-os.md#r-06-017)

**R-06-018** IS: Their failure cannot be contained by CHERI the way an in-model memory fault can, a wrongful declassification being a legitimate capability operation; blast radius is minimized by attenuation, the powerbox holding only the authority from which grants are attenuated.
· Accept: the consent TCB is named in §6 rather than hidden in userland, and booked in §17.
· Trace: CJ-NI, CJ-CERISE · [§6](verification-maximal-os.md#r-06-018)

**R-06-019** MUST NOT: The touch driver stays outside the trusted set: the consent path takes RoT-latched ownership of the input front-end for the prompt's duration rather than trusting the compartment that normally holds it.
· Accept: what the trusted set gains at the input edge is a fixed threshold-and-centroid reducer, not a programmable touch DSP.
· Trace: CJ-DEVTREE · [§6](verification-maximal-os.md#r-06-019)

### 6.4 Stated non-members

**R-06-020** IS: The verified HAL is a contained, non-TCB artifact: it is proven, but verification is not TCB membership, and its failure is bounded by CHERI, capability-checked DMA, and capability confinement like any other compartment.
· Accept: it is listed in §6 only to state explicitly that it does not join the TCB.
· Trace: CJ-HAL · [§6](verification-maximal-os.md#r-06-020)

**R-06-021** IS: The entire radio stack (PHY, L2/L3, and key management) is contained compartments and none of it is TCB.
· Accept: the TCB inventory names no radio component.
· Trace: CJ-CERISE · [§6](verification-maximal-os.md#r-06-021)

**R-06-022** IS: The rollback-manager UI drives the trusted rollback path but is not part of it: the system-integrity reader, the A/B transactor, and the RoT enforce the signed-root check and the anti-rollback floor whatever the UI requests.
· Accept: a compromised manager can mislead its own display but never enact a rollback the transactor would refuse.
· Trace: CJ-DEVTREE · [§6](verification-maximal-os.md#r-06-022)

**R-06-023** IS: Everything else (drivers, filesystems, network, display, radio, userland) is outside the TCB and secured by containment; the sole userland-resident exception is the consent TCB.
· Accept: the inventory is closed by R-06-001.
· Trace: CJ-CERISE · [§6](verification-maximal-os.md#r-06-023)

### 6.5 Required but untrusted build artifacts

**R-06-024** MUST: Four artifacts are hard prerequisites and all are untrusted evidence-producing machinery: (1) CompCert with a CHERI-RISC-V backend satisfying the secure-compilation criterion; (2) a certifying Rust→RV64+CHERI compiler emitting per-binary memory-safety certificates; (3) a WCET cost-annotation pass in the certifying toolchain; (4) constant-time verification for every secret-touching binary.
· Accept: each appears in §18 as an in-scope workstream and in no consumer-side TCB inventory.
· Trace: CJ-COMPCERT, CJ-WCET, CJ-CT-SOUND · [§6](verification-maximal-os.md#r-06-024)

**R-06-025** IS: Artifact (1) does not exist yet and the platform is purecap-only, so nothing boots without it.
· Accept: the dependency is stated as blocking rather than aspirational.
· Trace: CJ-COMPCERT · [§6](verification-maximal-os.md#r-06-025)

**R-06-026** MUST NOT: A fifth entry, the CryptOpt-style verified translation-validation toolchain for the crypto core's field arithmetic, is deleted rather than deferred and is named in §6 so its absence is legible.
· Accept: the TCB inventory carries no checker-admitted-artifacts category and the required-but-untrusted build-artifact list has four entries rather than five (R-06-004, R-06-024); what the deletion costs is read off R-05-064 rather than enumerated here.
· Trace: CJ-CRYPTO-SPEC · [§6](verification-maximal-os.md#r-06-026)

**R-06-027** IS: Constant-time verification degrades gracefully: bounded Binsec/Rel evidence carries bring-up, and the taint-typing plus residual certificate close it.
· Accept: the bring-up path is evidence-tier and the closing path is proof-tier, with both recorded.
· Trace: CJ-CT-SOUND · [§6](verification-maximal-os.md#r-06-027)

---

## §7. Kernel

### 7.1 Object model and allocation

**R-07-001** MUST: The kernel is a verified capability microkernel taking seL4's endpoint model and non-interference statement, re-proved end-to-end in Coq, targeting ≤10k lines; the remainder of seL4's object model is deleted by R-07-002, R-07-002b, and R-08-004.
· Accept: the line count is measured against the shipped source; CertiKOS supplies the proof method, not the kernel.
· Trace: CJ-KERNEL · [§7](verification-maximal-os.md#r-07-001)

**R-07-002** MUST NOT: There is no untyped memory and no retype: zero kernel allocation after boot holds by the absence of any allocation primitive in the ABI rather than by delegation from userland, and kernel objects are placed by the §8 composition-time static memory plan.
· Accept: no allocator and no allocation primitive exist in the kernel; the allocator bug classes are absent rather than bounded, and kernel-object slot disjointness is decided by the same on-device type-check side condition as every other object (R-08-014).
· Trace: CJ-KERNEL · [§7](verification-maximal-os.md#r-07-002)

**R-07-002a** IS: The untyped and retype deletion is grounded in the absence of a caller: static composition fixes the graph (R-07-025), the sanctioned runtime authority transfers extend only edges the manifest already fixed (R-07-026), and the graph is complete before the first partition runs and never grows.
· Accept: the ground is the no-consumer parsimony that excluded `Zacas`, `Zifencei`, and `Sstc`, stated as such rather than as a preference.
· Trace: CJ-KERNEL · [§7](verification-maximal-os.md#r-07-002a)

**R-07-002b** MUST NOT: There is no capability space: no CNodes, no capability-address translation, and no guarded radix lookup. A capability is a hardware object carrying a validity tag, held directly in registers and tagged memory; sealing over a composition-fixed otype set supplies object typing and CHERI permissions supply the rights.
· Accept: one capability representation exists on the machine, not two; no kernel-managed capability record and no index-to-capability lookup appears in the ABI or the proof.
· Trace: CJ-KERNEL, CJ-CERISE · [§7](verification-maximal-os.md#r-07-002b)

### 7.2 Multikernel

**R-07-003** IS: The microkernel is one verified artifact instantiated once per core: identical text, verified once and duplicated per core, with strictly disjoint state, each instance owning its object region, scheduler, and partition contexts.
· Accept: duplication is for NUMA locality and bit-flip blast-radius containment.
· Trace: CJ-KERNEL · [§7](verification-maximal-os.md#r-07-003)

**R-07-004** MUST NOT: There is no shared mutable kernel data and there are no kernel locks: each instance's proof is the *sequential* proof, parametric over its resource assignment.
· Accept: verified fine-grained SMP is sidestepped, not attempted.
· Trace: CJ-KERNEL · [§7](verification-maximal-os.md#r-07-004)

**R-07-005** MUST: Physical memory and devices are statically partitioned among instances at composition, where disjointness is machine-checked.
· Accept: the disjointness check is a build-time artifact, not a review.
· Trace: CJ-KERNEL, CJ-MEMPLAN · [§7](verification-maximal-os.md#r-07-005)

**R-07-006** MUST: Composition-time disjointness is enforced at runtime by CHERI bounds: each core's kernel instance is delegated a root capability bounded to its own physical partition, and monotonicity lets it derive nothing outside that partition plus the statically declared shared windows.
· Accept: the root capability's bounds are the partition's.
· Trace: CJ-CERISE · [§7](verification-maximal-os.md#r-07-006)

**R-07-007** IS: Exactly three things cross cores: hardware IPIs signaling local notification objects; user-level rings over designated shared windows; and capability transfer along statically declared cross-core grant edges.
· Accept: a fourth cross-core mechanism is an amendment.
· Trace: CJ-KERNEL · [§7](verification-maximal-os.md#r-07-007)

**R-07-008** IS: A uniprocessor build remains the minimal-proof variant.
· Accept: the build is retained and provable independently.
· Trace: CJ-KERNEL · [§7](verification-maximal-os.md#r-07-008)

**R-07-009** IS: The multikernel is *not* the confidentiality-isolation boundary; what the share-nothing structure adds is fault containment, authority containment, and the deletion of cross-core lock-contention and shared-structure timing channels.
· Accept: spatial isolation is CHERI's, timing-channel deletion is the islands' and the microarchitecture's.
· Trace: CJ-CERISE, CJ-ISOL · [§7](verification-maximal-os.md#r-07-009)

**R-07-010** IS: The share-nothing kernel is *entailed* by the island memory partition, not merely permitted: across islands there is no shared mutable memory, so a shared-mutable-state kernel is not implementable.
· Accept: consistent with R-15-223.
· Trace: CJ-ISOL · [§7](verification-maximal-os.md#r-07-010)

**R-07-011** IS: As a backstop the structure is real but scoped: the shared-state-concurrency class of non-interference violations is architecturally absent, yet the structure is common-mode against a flaw in the shared Sail model, the CHERI semantics, the per-instance sequential proof, or the capability-distribution spec.
· Accept: the common-mode statement is recorded rather than implied.
· Trace: CJ-NI, CJ-SAIL · [§7](verification-maximal-os.md#r-07-011)

**R-07-012** IS: The kernel is scalar-only code: one binary runs unmodified on every core class, the per-instance proof parametric over resource assignment and datapath class, with the only class-visible obligation being gating vector/matrix state (`mstatus.VS/XS`) at partition setup.
· Accept: classes differ only below the ISA waterline the kernel occupies.
· Trace: CJ-KERNEL, CJ-SAIL · [§7](verification-maximal-os.md#r-07-012)

**R-07-013** MUST NOT: There is no dynamic migration between core classes; big.LITTLE-style HMP migration is rejected outright, and assignment is a composition-time decision.
· Accept: no mechanism exists to drag VLEN-scale register state across the die, so per-core uniprocessor schedulability analysis holds and no migration-timing channel exists.
· Trace: CJ-WCET, CJ-NI · [§7](verification-maximal-os.md#r-07-013)

### 7.3 Switch discipline

**R-07-014** MUST NOT: There is no lazy vector/matrix unit switching, ever: lazy unit-ownership trapping is a cross-domain timing channel.
· Accept: either a V/M-class core is statically pinned to a single domain, or partition switches perform eager zeroize of vector RF, vector CSRs, and scratchpad, WCET-accounted in the switch budget.
· Trace: CJ-NI, CJ-WCET · [§7](verification-maximal-os.md#r-07-014)

**R-07-014a** MUST NOT: The partition switch does not *save* vector or matrix state; it zeroizes it. Save-and-restore has exactly one consumer, a partition cut mid-computation and later resumed, and no such partition exists: asynchronous interrupt delivery is deleted (R-07-038), the slot-boundary timer is the core's only asynchronous trap so no path carries a preemption term (R-07-043), and admission proves each slot's WCET fits its slot (R-07-035, R-11-006). A boundary cut is therefore a broken WCET bound, restarted under the crash-only posture (R-01-005), never resumed.
· Accept: the *no consumer* deletion that took `Zacas` (R-15-026) and `Zifencei` (R-15-047), with the retained restore declined under *verify rather than hedge* (R-15-013) exactly as R-07-016 declines the register-file flush. The zeroize is unchanged and unconditional, so no isolation property moves; what is deleted is the per-partition save area, the kernel's V/M save and restore paths, and a resident copy of one domain's vector state between switches.
· Trace: CJ-NI, CJ-ISOL, CJ-KERNEL, CJ-WCET · [§7](verification-maximal-os.md#r-07-014a)

**R-07-014b** MUST: A computation that spans slots sinks its own vector and matrix working state to its own memory, in its own non-TCB code, under the compiler's sink-before-yield transformation; the kernel carries nothing across a switch on its behalf.
· Accept: the obligation is paid by the tasks that need it and sized to what is live, in place of a kernel paying the full worst-case save for every partition at every switch: a reduction, not a relocation, and the standing move of placing an obligation where a proof can discharge it (R-07-016, R-05-123).
· Trace: CJ-WCET, CJ-ISOL · [§7](verification-maximal-os.md#r-07-014b)

**R-07-015** MUST: The scalar and capability register restore is *total*: every general-purpose register, capability register, and CSR a partition can name is written by the switch before the successor partition's first instruction.
· Accept: residue is impossible rather than cleared; the register set is enumerated and argued closed, and a register outside the restore set is a proof failure.
· Trace: CJ-KERNEL, CJ-ISOL · [§7](verification-maximal-os.md#r-07-015)

**R-07-016** IS: That totality is the obligation that replaces register-file membership in the `fence.t` flush set, which §15 declines under *verify rather than hedge*.
· Accept: the guarantee is stated once, where the kernel proof discharges it, rather than twice (R-15-214).
· Trace: CJ-ISOL · [§7](verification-maximal-os.md#r-07-016)

**R-07-017** MUST: Power gating is permitted only when the remaining slot ≥ the gate's entry+exit WCET; operating-point changes occur only at partition switches from the composition-time assignment, their relock cost folded into the switch budget.
· Accept: the kernel never selects power states from load; there is no governor, in the kernel or anywhere else.
· Trace: CJ-WCET · [§7](verification-maximal-os.md#r-07-017)

### 7.4 Privilege

**R-07-018** IS: The platform runs Machine mode only: privileged authority (control/status registers, interrupt-enable, context-switch and sealing primitives) is gated by the access-system-registers permission on the executing PCC, not by a hardware ring.
· Accept: there is no S-mode and no U-mode.
· Trace: CJ-CERISE, CJ-KERNEL · [§7](verification-maximal-os.md#r-07-018)

**R-07-019** MUST: The boot/M-mode firmware runs first, establishes the initial capability distribution (deriving each core's partition-bounded root capability), then goes quiescent with no SMM-analog resident handler.
· Accept: no firmware code is resident after handoff.
· Trace: CJ-KERNEL · [§7](verification-maximal-os.md#r-07-019)

**R-07-020** IS: The microkernel is the sole resident code holding the system-register permission and the switch/seal authority: event-driven, with no kernel threads, executing on the caller's budget.
· Accept: no kernel thread exists in the object inventory.
· Trace: CJ-KERNEL · [§7](verification-maximal-os.md#r-07-020)

**R-07-021** MUST: The kernel is entered for exactly two reasons: a synchronous exception or syscall on the running instruction, and the slot-boundary timer.
· Accept: the kernel proof carries no *device-MSI-lands-mid-syscall* interleaving case at any entry point.
· Trace: CJ-KERNEL · [§7](verification-maximal-os.md#r-07-021)

**R-07-022** IS: The trap path carries capabilities, not integer addresses: taking a trap installs `MTCC` as the executing PCC, saves the interrupted PCC as `MEPCC`, and bootstraps the handler's authority from `MTDC`.
· Accept: consistent with R-15-073.
· Trace: CJ-CERISE · [§7](verification-maximal-os.md#r-07-022)

**R-07-023** MUST: Every compartment runs in the same Machine mode *without* the system-register permission, isolated by CHERI capabilities alone; a compartment cannot execute a privileged CSR access because its PCC lacks the permission, an unforgeable condition rather than a mode check.
· Accept: privilege escalation has no ring to target.
· Trace: CJ-CERISE · [§7](verification-maximal-os.md#r-07-023)

**R-07-024** MUST NOT: Nothing else is resident beside the kernel: no hypervisor tenant, no privileged daemon, and no power-management firmware.
· Accept: the resident-code inventory has one entry.
· Trace: CJ-KERNEL · [§7](verification-maximal-os.md#r-07-024)

### 7.5 Static composition

**R-07-025** MUST: The component graph and capability distribution are fixed and machine-checked at build time; there is no dynamic privilege creation in the base.
· Accept: what is fixed is the composed topology and the confidentiality-label lattice.
· Trace: CJ-NI, CJ-KERNEL · [§7](verification-maximal-os.md#r-07-025)

**R-07-026** IS: The one sanctioned runtime authority transfer is the powerbox declassification, which extends the *live* edge set at a single verified point without minting a new privilege class or a new label; the §12 supervision tree's restart re-grant only re-instantiates edges the manifest already fixed.
· Accept: neither operation adds a node or a label to the composed graph.
· Trace: CJ-NI · [§7](verification-maximal-os.md#r-07-026)

**R-07-027** MUST: The §12 IDL worlds and interfaces lower to a capDL-class capability-distribution spec: kernel-object-granular over endpoints, notifications, and partition contexts, re-homed to Coq, extended so cap edges carry CHERI-bounds grants, and stripped of the VSpace, page-table, and frame-mapping object classes together with the untyped and CNode classes R-07-002 and R-07-002b delete.
· Accept: the spec is a Coq artifact, not a documentation format, and its object classes are exactly those the kernel retains.
· Trace: CJ-IDL, CJ-KERNEL · [§7](verification-maximal-os.md#r-07-027)

**R-07-028** MUST: The capability-distribution spec carries an initialisation-refinement obligation: the M-mode firmware that installs the distribution is proved to instantiate exactly the composed cap graph as running kernel state.
· Accept: *machine-checked at build time* is joined by *machine-checked as installed*, closing the gap between the composed graph and the booted machine.
· Trace: CJ-KERNEL · [§7](verification-maximal-os.md#r-07-028)

### 7.6 IPC

**R-07-029** IS: IPC is synchronous endpoints plus notifications, with all capability transfer explicit; the kernel carries control, never bulk data, high-throughput I/O riding user-level rings.
· Accept: no bulk-data path traverses privileged code.
· Trace: CJ-KERNEL · [§7](verification-maximal-os.md#r-07-029)

**R-07-030** MUST NOT: No io_uring-style opcode surface re-enters privileged code.
· Accept: the kernel ABI admits no submission-queue opcode dispatch.
· Trace: CJ-KERNEL · [§7](verification-maximal-os.md#r-07-030)

**R-07-031** IS: The kernel ABI is the capability primitives alone: under a dozen invocations, formally specified and frozen with the proof; kernel messages are registers plus capability slots, never typed structured data.
· Accept: rich interfaces live one layer up in §12.
· Trace: CJ-KERNEL, CJ-IDL · [§7](verification-maximal-os.md#r-07-031)

**R-07-031a** MUST NOT: The kernel ABI carries no retype, no capability-space, and no derivation-tree invocation; the surface the frozen ABI specifies and the proof covers is the endpoint, notification, partition-context, and revocation set alone.
· Accept: the invocation list is enumerated and closed, and an invocation outside that set is a failure of the ABI freeze rather than an extension of it.
· Trace: CJ-KERNEL · [§7](verification-maximal-os.md#r-07-031a)

### 7.7 Scheduling

**R-07-032** MUST: Each core runs a table-driven static cyclic executive: a composition-time schedule of fixed, time-triggered slots, with no priorities, no scheduling-context capabilities, no budget donation, and no runtime scheduling decision.
· Accept: temporal authority is fixed at composition, not a runtime capability.
· Trace: CJ-WCET · [§7](verification-maximal-os.md#r-07-032), [§7](verification-maximal-os.md#r-07-032-2)

**R-07-033** IS: Temporal isolation *is* the slot: a partition runs only in its assigned slots and cannot overrun them, the timer switching at the boundary, so a spinning compartment wastes only its own time.
· Accept: overrun is prevented by mechanism, not convention.
· Trace: CJ-ISOL · [§7](verification-maximal-os.md#r-07-033)

**R-07-034** MUST: Aperiodic events get dedicated polling or sporadic slots sized into the frame, unless the cadence a deadline demands would make the partition-switch constant itself a dominant budget term, in which case the server leaves the slot wheel and is pinned to its own core.
· Accept: the radio PHY pair and the sentinel are instances of that general rule, not exceptions to it (R-15-114).
· Trace: CJ-WCET · [§7](verification-maximal-os.md#r-07-034)

**R-07-035** MUST NOT: seL4's MCS machinery is deleted: scheduling contexts, budget and period capabilities, passive-server donation, and timeout faults.
· Accept: §11 schedulability collapses from response-time analysis to an interval-arithmetic check: the slot WCETs fit the major frame, and each task's period is harmonic with it.
· Trace: CJ-WCET · [§7](verification-maximal-os.md#r-07-035)

**R-07-036** MUST: Across confidentiality boundaries the schedule is non-work-conserving: an idle slot stays idle rather than yielding, so no slack ever crosses a partition boundary.
· Accept: there is no donation mechanism for slack to leak through.
· Trace: CJ-NI, CJ-ISOL · [§7](verification-maximal-os.md#r-07-036)

**R-07-037** IS: Because the frame divides rather than shares, compartment population is a first-class schedule parameter: a partition's capacity *is* its slot width, and the number of compartments on one core's wheel is a composition constant with a hard ceiling rather than a soft degradation curve.
· Accept: §11 makes population its own schedule axis (a proved rung ladder, distinct from the global mode transition and deliberately not rare), and §17 books what the division costs and what the rung index leaks.
· Trace: CJ-WCET, CJ-NI · [§7](verification-maximal-os.md#r-07-037)

### 7.8 Interrupts

**R-07-038** MUST NOT: Asynchronous interrupt delivery does not exist: an MSI sets a pending bit and does nothing else, and no pending bit ever vectors the core to `MTCC`.
· Accept: no fetch is disturbed, no slot boundary moves, and no runtime scheduling decision is created.
· Trace: CJ-KERNEL, CJ-ISOL · [§7](verification-maximal-os.md#r-07-038)

**R-07-039** MUST: A partition consumes its pending bits by reading them, with ordinary loads at poll sites inside its own slots.
· Accept: the trap path is entered only synchronously or by the boundary timer.
· Trace: CJ-KERNEL · [§7](verification-maximal-os.md#r-07-039)

**R-07-040** IS: The slot-boundary timer is the machine's sole asynchronous trap, and it is irreducible and unmaskable: irreducible because it makes *a partition cannot overrun its slot* a mechanism rather than a convention, unmaskable because it needs no enable bit to protect it.
· Accept: the switch completes at the §15 padded constant and the timer does not re-arm until the handler reprograms `mtimecmp`.
· Trace: CJ-ISOL, CJ-WCET · [§7](verification-maximal-os.md#r-07-040)

**R-07-041** IS: Interrupt masking has nothing left to govern, so the interrupt-state sentry types and their statically-auditable bounded interrupt-disabled-window allow-list are deleted rather than audited.
· Accept: a bounded obligation (*is the mask window short enough?*) is traded for an absence checked structurally (R-15-070).
· Trace: CJ-SAIL · [§7](verification-maximal-os.md#r-07-041)

**R-07-042** IS: Worst-case device service latency is a schedule corollary, not an interrupt property: an event waits at most its owning server's slot period plus its in-slot handling WCET, and §11 sizes each device's poll cadence or sporadic slot to its deadline.
· Accept: the rule holds without exception.
· Trace: CJ-WCET · [§7](verification-maximal-os.md#r-07-042)

**R-07-043** IS: No WCET carries a preemption term at all, rather than carrying a bounded one: with no trap point at every instruction boundary, the remaining trap points are syntactic poll sites already in the typed control-flow graph.
· Accept: the derivation loses a term instead of bounding it.
· Trace: CJ-WCET · [§7](verification-maximal-os.md#r-07-043)

**R-07-044** MUST: Per-partition interrupt-file pending bits are statically identity-partitioned or swapped at the switch, in the switch budget, so no interrupt state is hidden or shared across a partition boundary.
· Accept: §15 admission test 3 is satisfied for interrupt state; there are no enable bits left to swap.
· Trace: CJ-ISOL · [§7](verification-maximal-os.md#r-07-044)

**R-07-045** IS: All interrupts are MSIs and wired level interrupts do not exist: the RoT watchdog's *bark* is an ordinary MSI into the sentinel's interrupt file, and only the *bite* and the RoT's reset and power-sequencing lines are non-MSI signals: resets, not interrupts, unmaskable by construction.
· Accept: nothing the watchdog or the boot chain depends on rides an interrupt-enable bit.
· Trace: CJ-DEVTREE · [§7](verification-maximal-os.md#r-07-045)

**R-07-046** MUST: The bark is read, not delivered, and is checked in the boundary-timer handler, bounding notice at one slot period; if even the boundary path is dead, the bite is the sub-slot backstop.
· Accept: the bark's purpose is to reach a core that is alive but wedged, which polling by definition cannot.
· Trace: CJ-DEVTREE · [§7](verification-maximal-os.md#r-07-046)

**R-07-047** IS: This is the one place the delivery deletion genuinely costs response time, and it is booked in §17 rather than absorbed.
· Accept: the residual entry exists.
· Trace: CJ-WCET · [§7](verification-maximal-os.md#r-07-047)

### 7.9 Purecap kernel and proof structure

**R-07-048** MUST: The kernel compiles to pure-capability code: its own pointers are hardware capabilities, so a flipped bit clears the validity tag or lands outside bounds and faults rather than resolving to a live address.
· Accept: the guarantee is the tag and bounds check itself; no encryption avalanche is credited, the memory path carrying none.
· Trace: CJ-CERISE · [§7](verification-maximal-os.md#r-07-048)

**R-07-049** IS: The purecap cost is that the proof runs over CHERI-C semantics, so the residual is the capability-widened CompCert memory model and this kernel's refinement over it rather than the CHERI-C semantics itself; kernel pointers double in width, and the kernel depends on the §6 CHERI backend.
· Accept: the residual is booked in §17 as a narrower spec-gap surface than a from-scratch mechanization.
· Trace: CJ-COMPCERT · [§7](verification-maximal-os.md#r-07-049)

**R-07-050** MUST: The trap, context-switch, and IPC fast path is verified directly at binary level against the Sail model in the one Iris-over-Sail program logic, not through the CHERI-C → CompCert-memory-model refinement.
· Accept: the fast path's proof mentions only the Sail operational semantics and the capability invariants, so the capability-widened CompCert memory model is off its trust path entirely.
· Trace: CJ-SAIL, CJ-KERNEL · [§7](verification-maximal-os.md#r-07-050)

**R-07-051** IS: The cold paths (setup, rare object operations) stay verified C through CHERI-CompCert, where the CHERI-C convenience is worth the seam.
· Accept: only the hot, tiny, most-critical path pays for a direct binary-level proof.
· Trace: CJ-COMPCERT · [§7](verification-maximal-os.md#r-07-051)

**R-07-052** MUST: Single address space: the kernel drops seL4's VSpace, page-table, and frame-mapping object classes entirely, and CHERI bounds are the sole in-core spatial isolation.
· Accept: the map/unmap invocations, the page-table walk, `satp` switching, and TLB-shootdown paths and their proofs are gone rather than verified; frames become capability-bounded physical ranges fixed by the §8 composition-time memory plan.
· Trace: CJ-KERNEL, CJ-CERISE · [§7](verification-maximal-os.md#r-07-052)

---

## §8. Authority Model

### 8.1 Capabilities as the sole authority

**R-08-001** MUST NOT: Capabilities are the sole authority: there is no ambient authority anywhere: no global namespaces, no uid/gid, no setuid, no `fork()`.
· Accept: no authority is reachable except through a held capability.
· Trace: CJ-CERISE · [§8](verification-maximal-os.md#r-08-001)

**R-08-002** IS: The layer rule is completed by §5's language rule deleting ambient *state*, because a language free to re-manufacture a global above the OS and hardware layers reintroduces the unaccounted authority path both deleted.
· Accept: R-05-086 is the discharge; the grading disciplines that reason over a typing context can see all authority.
· Trace: CJ-TAL-SOUND · [§8](verification-maximal-os.md#r-08-002)

**R-08-003** IS: At the hardware layer, CHERI capabilities backstop `unsafe` Rust and residual C, and this extends unchanged to V/M-class cores: vector and matrix memory operations are checked against explicit capability operands of the issuing context, per-element for indexed and gather-scatter access.
· Accept: accelerator-class compute inherits the full spatial-safety story rather than a device-side approximation.
· Trace: CJ-CERISE · [§8](verification-maximal-os.md#r-08-003)

### 8.2 Revocation

**R-08-004** MUST: The kernel layer provides object capabilities with first-class revocation, and the mechanism is the CHERI one alone: revocation epoch, budgeted sweep, and per-load filter. There is no capability derivation tree. Revocation runs within a guaranteed time bound, so time-to-containment is a bounded constant, including the distributed case, where capabilities delegated over cross-core grant edges revoke via a verified bounded-round protocol of local epoch advance plus proxy notification along the same static edges.
· Accept: the bound is stated per composition and enters the §11 schedule; exactly one revocation mechanism appears in the kernel spec and its proof.
· Trace: CJ-CERISE, CJ-WCET · [§8](verification-maximal-os.md#r-08-004)

**R-08-004a** MUST: Subtree revocation is retained and is a grant-layer property rather than a capability-format one. Cross-domain authority that must be independently revocable is delegated as a sealed grant handle and not as a bare capability: the kernel mints a grant slot in a kernel-owned grant table, stores the underlying capability in it, and hands the delegate a capability bounded to that slot and sealed with a composition-fixed otype (R-07-002b). Retiring the delegation sets the R-08-005a revocation bit for the *slot's* granule, not the object's.
· Accept: the one thing ancestry keying held over address keying was that a delegation had no address of its own; giving each delegation a slot supplies one, so revoking what one principal delegated leaves every other principal's capability to the same object untouched (a different address, a different bit), and the subtree case is decided by the existing load filter rather than by a kernel walk over a derivation tree. Retaining a tree beside it would be a hedge on a verified primary under R-15-013.
· Trace: CJ-CERISE · [§8](verification-maximal-os.md#r-08-004a)

**R-08-004b** MUST NOT: No revocation colour is stamped into any capability, and the capability format carries no colour field.
· Accept: this closes the bit budget rather than deferring it. R-15-007's format spends all 64 bits (36+4+5+5+8+6), so a colour could come only from the object type or a mantissa, where the cost would land on R-15-007c's 256-byte exactness threshold and therefore on the R-15-007e/R-15-007f admissibility argument for the capability indexed load/store. The grant table of R-08-004a spends no capability bit, adds no field, and reuses the R-08-005a sidecar, the R-08-007 sweep, and the R-08-008 quarantine rather than standing a second revocation mechanism beside them, which is what R-08-004's *exactly one mechanism* acceptance requires.
· Trace: CJ-CERISE, CJ-SAIL · [§8](verification-maximal-os.md#r-08-004b)

**R-08-004c** IS: The grant table's three costs are booked, not absorbed. (1) One kernel-mediated indirection on *cross-domain* authority use (the delegate invokes through the handle, and the kernel unseals the slot and yields the underlying capability for the duration of the call), and none on intra-domain loads, which stay bare capabilities. (2) Grant-table capacity is a composition-time constant charged against the R-15-002a SRAM budget by the R-08-010 static memory plan exactly as the R-08-005a bitmap payload is. (3) A bare capability handed across a domain boundary is revocable only with its object.
· Accept: the indirection is priced against the cross-domain call it rides and not against the load path; admission rejects a composition whose simultaneous live grant count exceeds the table, so exhaustion is a build-time rejection and never a runtime failure; and which cross-domain edges are grant-mediated is fixed at composition by the manifest and the R-05-159 linear-capability discipline, never chosen by a principal at runtime.
· Trace: CJ-CERISE, CJ-MEMPLAN, CJ-WCET · [§8](verification-maximal-os.md#r-08-004c)

**R-08-004d** IS: The grant table is not the capability space R-07-002b deletes.
· Accept: there is no capability-address translation, no index namespace, and no guarded radix lookup: the handle is a hardware capability whose *bounds* name the slot, so the kernel dereferences a capability it was handed rather than resolving a name, and the table is ordinary kernel-owned memory sited in an R-08-005a revocable interval, not a restored object class with invariants of its own.
· Trace: CJ-CERISE · [§8](verification-maximal-os.md#r-08-004d)

**R-08-005** MUST: *Freed ⇒ unreachable* holds at *access* time, not only at sweep completion: a per-load revocation check (load filter or barrier) invalidates a stale capability the moment it is loaded.
· Accept: the check is deterministic and architectural, fixed-latency, riding the load with no added memory traffic, so it passes the §15 admission test.
· Trace: CJ-CERISE, CJ-LEAK · [§8](verification-maximal-os.md#r-08-005)

**R-08-005a** MUST: The load filter is backed by a dedicated ECC-protected revocation bitmap over a composition-fixed union of 64-byte-aligned revocable SRAM intervals, with one architectural revocation bit per 8-byte capability granule: `0` is live and `1` is revoked. For covered intervals *I*, its payload is exactly Σ|*I*|/64 bytes; the static memory plan charges that payload, its ECC bits, and macro periphery against the §15 SRAM capacity budget, and admission rejects a composition that does not fit. The interval map and resulting bitmap size are attested-devicetree constants; ordinary compartments cannot address the bitmap, and only the kernel revocation path may update it.
· Accept: this is the CHERIoT non-MMU realization, not RVY `Svyrg`: the loaded capability's base selects the bit and a set bit clears its tag before architectural writeback. RVY's four-bit PTE state machine has no PTE in which to live here and is not silently compressed into one bit; epoch, sweep, and quarantine state remain in their separately specified protocol, while this array carries only the load-time live/revoked predicate. The covered union includes the R-08-004a grant table, whose per-slot bits carry the subtree case. The bitmap is a bank-side sidecar read with the data/tag access, not a second fabric or main-memory transaction.
· Trace: CJ-CERISE, CJ-WCET, CJ-SAIL · [§8](verification-maximal-os.md#r-08-005a)

**R-08-005b** MUST: The **load instruction's own definition** permits the revocation-driven tag clear: a capability-width load whose result is revoked writes the value back with its validity tag cleared, and that is a defined result of the load rather than an effect the filter's prose layers onto it.
· Accept: every capability-width load in the Sail model carries the revoked case as one of its defined results, at the single fixed latency R-08-005a and R-08-006 state, so the bank-side filter realizes an architectural result rather than acting outside the instruction that provoked it; a load definition admitting only an unmodified tag or a trap cannot express R-08-005's check at all. Both address-keyed cases rest on this clause and have no second mechanism, the object case and R-08-004a's delegation case each clearing the tag on the load with the revocation colour declined at R-08-004b.
· Trace: CJ-SAIL, CJ-CERISE · [§8](verification-maximal-os.md#r-08-005b)

**R-08-006** IS: Containment and reclamation split: containment is the revocation-epoch advance the load filter checks against (a register-write-class constant, microseconds), while the sweep is reclamation, milliseconds to seconds of memory traffic that no security property waits on.
· Accept: the bounded constant claimed in R-08-004 is the epoch flip, not sweep completion.
· Trace: CJ-CERISE · [§8](verification-maximal-os.md#r-08-006)

**R-08-007** MUST: The sweep runs as an incremental, preemptible kernel task in its own §11-admitted background slot class, per core, sized at composition, never in another partition's time.
· Accept: its completion latency is a derived per-domain constant: the domain's capability-bearing footprint over the per-frame sweep quantum.
· Trace: CJ-WCET · [§8](verification-maximal-os.md#r-08-007)

**R-08-007a** MUST: Nothing in the revocation protocol wraps, and no revocable resource is reused before it is dead. The epoch is a 64-bit monotone kernel counter naming containment events, advanced only on kernel-mediated teardown. A revocation bit and the granule under it return to service only once a full sweep pass has covered every revocable interval since the bit was set.
· Accept: at one advance per microsecond the epoch does not wrap in 5 × 10⁵ years, so wrap is not a reachable state and no reuse semantics are owed; reset is not a wrap, since the R-15-182 eager zeroize leaves no capability alive to be misread under a restarted counter. The reuse gate is the R-08-008 quarantine seen from the reuse side, and it is what makes the address key sound for R-08-004a's subtree case: a grant slot cannot be re-minted into while a stale handle bounded to it might still be loadable. The quarantine pool is composition-sized, so the set-to-reuse interval is a derived constant. The gate is a sweep and not a generation compare, on R-08-004b's ground: a generation discriminates only if the handle carries it and no field exists to carry it in, while a generation carried out of band as an integer presented at invocation is a bearer token a stale holder can guess, which is the forgery the capability substrate exists to remove. There is no colour space to exhaust and no retirement set to bound under R-08-004b; the grant-slot count that stands in its place exhausts as a capacity under R-08-004c, not as a namespace.
· Trace: CJ-CERISE, CJ-WCET · [§8](verification-maximal-os.md#r-08-007a)

**R-08-008** MUST: Forced-sweep denial of service is priced out structurally: revocation is triggered only by kernel-mediated teardown, so a compartment that churns grants forces sweeps only of its own footprint, paid from its own and the sweeper's fixed slots.
· Accept: the cost of queued sweeps is delayed reclamation of the *requester's* quarantined memory, bounded by the composition-sized quarantine pool, never schedule perturbation of any hard task.
· Trace: CJ-WCET, CJ-ISOL · [§8](verification-maximal-os.md#r-08-008)

**R-08-009** MUST NOT: The autonomous background engines a CHERI microcontroller ships for this purpose (CHERIoT-Ibex TBRE revocation-sweep and STKZ stack-zeroing) are declined as autonomous memory-touching walkers under admission test 5; only the deterministic load filter is imported and the sweep stays software.
· Accept: no engine walks memory on its own.
· Trace: CJ-SAIL · [§8](verification-maximal-os.md#r-08-009)

### 8.3 The static memory plan

**R-08-010** MUST: The heap is compiled, not allocated at runtime: a whole-program static memory plan replaces the online allocator, so at runtime allocation is the read of a pre-assigned slot.
· Accept: no allocator component exists; no online packing exists for Robson's worst case to act upon.
· Trace: CJ-MEMPLAN · [§8](verification-maximal-os.md#r-08-010)

**R-08-011** IS: Linear/affine ownership fixes each object's live range at compile time and region inference fixes its allocation and free points, expressed against the capability substrate as the calculus-of-capabilities region discipline whose static tokens this design realizes at runtime as CHERI capabilities. The resulting whole-program slot plan and its live-range colouring are a crown-jewel spec: the kernel refinement is stated against the plan, so a wrong plan yields a correct proof of the wrong layout.
· Accept: the compiler emits a static slot assignment carried in the CHERI-TAL derivation.
· Trace: CJ-MEMPLAN, CJ-TAL-SOUND · [§8](verification-maximal-os.md#r-08-011)

**R-08-012** IS: Fragmentation collapses at three points: external fragmentation is deleted rather than bounded, over-reservation collapses to the proven simultaneous peak by live-range colouring, and size-class internal fragmentation is deleted by exact-size slots.
· Accept: the footprint is peak-liveness, the minimum any non-moving scheme can use.
· Trace: CJ-MEMPLAN · [§8](verification-maximal-os.md#r-08-012)

**R-08-012a** MUST: The plan's objective is lexicographic: the peak-liveness footprint first, which locality may never worsen, then locality, whose three terms are co-location of objects the typed structure shows are reached together, field partitioning so frequently-reached fields share whole granules and rarely-reached ones leave them, and spreading concurrently-live objects across the island's own banks and macros.
· Accept: the degrees of freedom a peak-optimal colouring leaves over are recorded as spent on those three terms under a fixed tie-break rather than on an arbitrary one; with no cache on the die the plan is the machine's only placement mechanism, so an unspent degree of freedom is latency nothing else recovers.
· Trace: CJ-MEMPLAN, CJ-WCET · [§8](verification-maximal-os.md#r-08-012a), [§15](verification-maximal-os.md#r-08-012a-2)

**R-08-012b** MUST: Reach frequency is decided from artifacts the build already carries (the typed callee graph, the typed control-flow graph and its loop nesting, the §11 declared loop bounds, and the manifest's declared region types) under a fixed tie-break, with no PGO corpus, sampled frequency, learned weight, or runtime feedback.
· Accept: two builds of one source closure yield an identical placement map, so the map is reproducible and attestable and the plan is not a reactive feedback loop rebuilt in the toolchain; the discipline is R-10-034's, applied to data.
· Trace: CJ-MEMPLAN, CJ-DEVTREE · [§8](verification-maximal-os.md#r-08-012b), [§10](verification-maximal-os.md#r-08-012b-2)

**R-08-012c** MUST: Every slot the plan assigns lies inside the region the owning island's root capability bounds, and the bank/macro/tier→island map is read and never written, so no placement moves an island boundary, borrows another island's array, changes a bandwidth ceiling, or places two confidentiality domains in one granule.
· Accept: an out-of-island placement has no capability derivation rather than a new admission test to fail; consistent with R-07-006, R-15-226, R-15-228, and R-15-228a.
· Trace: CJ-MEMPLAN, CJ-ISOL · [§8](verification-maximal-os.md#r-08-012c)

**R-08-012d** MUST: Locality is a constrained objective, admissible only where no island's peak footprint and no admitted §11 bound is worse than in the plan it replaces, and it adds no admission test, no checker, no proof term, and no WCET input.
· Accept: R-08-014's interference side-condition, R-08-016's single pass, and R-11-015's derivation from the placed image are each unchanged; where the timing-annotated model prices two arrays alike the gain is on the average and the bound does not move, and where it prices them apart the derived bound improves.
· Trace: CJ-MEMPLAN, CJ-WCET, CJ-TAL-SOUND · [§8](verification-maximal-os.md#r-08-012d)

**R-08-012e** MUST: The plan's fourth lexicographic term, after footprint and locality, is domain concentration: minimizing, per global mode, the number of distinct gating domains (macros and tiers) an island's live set occupies, and emitting that per-mode occupancy map over gating domains for §15 to read as the mode's power vector.
· Accept: the map is a projection of the slot assignment and the bank/macro/tier→island map the plan already consumes (R-15-228a), so it is a reporting step and not a new analysis; a domain holding one live object cannot be collapsed, which is what makes the count the thing R-15-189a spends.
· Trace: CJ-MEMPLAN, CJ-WCET · [§8](verification-maximal-os.md#r-08-012e)

**R-08-012f** MUST: Domain concentration is a constrained objective under R-08-012d's rule exactly as locality is, and it is a build-step objective only: it stands in genuine tension with R-08-012a's bank spreading, and the runtime relocation pass that would be its dynamic form is declined with the rest of the reactive family (R-15-189h).
· Accept: no island's peak footprint and no admitted §11 bound is worse than in the plan concentration replaces, and the modes where it wins are the low-duty and standby modes where the leakage term dominates; compaction stays a build step, no relocation mechanism existing at runtime (R-08-020).
· Trace: CJ-MEMPLAN, CJ-WCET · [§8](verification-maximal-os.md#r-08-012f)

**R-08-013** IS: Offline is the whole game: online allocation carries Robson's Θ(log n) worst case, while the offline problem is NP-hard in general, constant-factor approximable, and exactly optimal in polynomial time for the nested, region-structured lifetimes a region discipline produces, all solved in build-time compute.
· Accept: static composition is what buys the move from the Robson-hard online setting to the near-optimal offline one.
· Trace: CJ-MEMPLAN · [§8](verification-maximal-os.md#r-08-013)

**R-08-014** MUST: The plan is checked, not trusted: slot disjointness over disjoint live ranges is a decidable interference side-condition of the on-device TAL type-check, so an overlap is a type error and a bad plan is rejected, never admitted unsafe.
· Accept: nothing joins the TCB and nothing runs at allocation time; there is no free-set proof to ship.
· Trace: CJ-TAL-SOUND, CJ-MEMPLAN · [§8](verification-maximal-os.md#r-08-014)

**R-08-015** MUST: Temporal safety at a slot's reuse points composes with the plan: the load filter and revocation epoch invalidate any capability to a slot's prior tenant before the next is installed.
· Accept: placement ⋈ temporal-safety, with the escape bounded by the same region and ownership discipline that fixed the live ranges.
· Trace: CJ-CERISE, CJ-MEMPLAN · [§8](verification-maximal-os.md#r-08-015)

**R-08-016** IS: Placement, disjointness, and initialization are three attributes over one interference structure, all checked in the same on-device pass and all rejecting a bad artifact rather than trapping a bad execution.
· Accept: each slot enters its live range uninitialized, eager-zeroize makes that state a deterministic zero, and the definite-initialization attribute decides that no load precedes a store within the range.
· Trace: CJ-TAL-SOUND, CJ-MEMPLAN · [§8](verification-maximal-os.md#r-08-016)

**R-08-017** IS: Memory-admissible ⟺ time-admissible: the peak-memory bound and the WCET bound are read off the same static facts, so the memory admission test is the space projection of the §11 schedulability certificate, not a second test.
· Accept: one static-boundedness certificate, two resources.
· Trace: CJ-WCET, CJ-MEMPLAN · [§8](verification-maximal-os.md#r-08-017)

**R-08-018** IS: The runtime-count-dependent case folds in as the degenerate plan: a bounded fan-out is N pre-coloured equal-size slots whose occupancy is 0..N, so the dynamism is *which* slots are live, never *where* an object lands.
· Accept: a zero-fragmentation pool, the degenerate interference graph of N mutually-live cells.
· Trace: CJ-MEMPLAN · [§8](verification-maximal-os.md#r-08-018)

**R-08-019** IS: The honest ceiling is a footprint statically bounded yet far above its average, met by the standing capacity-versus-determinism posture: bend capacity, restructure to a streamed bound, or refuse.
· Accept: it is the same ceiling every other subsystem meets, not a new one.
· Trace: CJ-MEMPLAN · [§8](verification-maximal-os.md#r-08-019)

**R-08-020** MUST NOT: Compaction and relocation never arise: there is nothing to move at runtime because the packing already happened at compile time.
· Accept: no relocation mechanism exists.
· Trace: CJ-MEMPLAN · [§8](verification-maximal-os.md#r-08-020)

### 8.4 Non-interference

**R-08-021** IS: The static capability topology defines the flow policy: a component at confidentiality level H may not influence a component at level L unless an explicit inter-level channel capability exists.
· Accept: the policy is read off the composed graph, not configured.
· Trace: CJ-NI · [§8](verification-maximal-os.md#r-08-021)

**R-08-022** MUST: The kernel's Coq proof is extended to a non-interference theorem over that fixed graph, over the multikernel composition, the purecap CHERI-C semantics, and the powerbox's robust declassification, and it is a *fresh* proof rather than an inherited one.
· Accept: what carries over from seL4-NI is the method of stating and discharging NI over a capability graph, not the proof's maturity; the freshness is booked in §17.
· Trace: CJ-NI · [§8](verification-maximal-os.md#r-08-022)

**R-08-023** IS: The theorem is about the existing structure, not a new mechanism.
· Accept: no runtime component is added to make it hold.
· Trace: CJ-NI · [§8](verification-maximal-os.md#r-08-023)

**R-08-024** IS: The theorem is non-interference *modulo robust, delimited declassification*: the fixed graph fixes the label lattice and the set of declassification points, not a frozen edge set for all time.
· Accept: the one point at which the live flow relation may extend past the compose-time manifest is the powerbox, a single component statically present in the graph.
· Trace: CJ-NI · [§8](verification-maximal-os.md#r-08-024)

**R-08-025** MUST: A user grant is modeled as a delimited release the theorem quantifies over, and the theorem's content is robust declassification: over *all* strategies of a compromised component, none can influence whether, what, or to whom the powerbox declassifies.
· Accept: that decision depends only on the unforgeable consent act and the powerbox's verified logic.
· Trace: CJ-NI · [§8](verification-maximal-os.md#r-08-025)

**R-08-026** MUST: The only permitted extension is a powerbox grant CHERI-bounded to the user-named object, so the granted channel carries that object alone and is no general H→L conduit.
· Accept: user-authorized flow is inside the theorem: neither near-vacuously admitted nor left outside it.
· Trace: CJ-NI, CJ-CERISE · [§8](verification-maximal-os.md#r-08-026)

**R-08-027** IS: The theorem covers explicit information flow; the timing side is closed separately by the formal isolation semantics of the §15 partitioning hardware, the two designed to compose into one partition-level guarantee.
· Accept: the seam is the NI ⋈ timing lemma (R-05-160).
· Trace: CJ-NI, CJ-ISOL · [§8](verification-maximal-os.md#r-08-027)

**R-08-027a** IS: The observation model includes *progress*: whether a component terminates and how far it gets before it does are observations the policy ranges over, not quantities quotiented out of it.
· Accept: the theorem is termination- and progress-sensitive; a proof stated over final values alone does not discharge it.
· Trace: CJ-NI · [§8](verification-maximal-os.md#r-08-027a)

**R-08-027b** MUST: A component's observable progress is a function of the schedule and not of any secret it holds: slot instants and widths are composition constants, the frame is non-work-conserving across confidentiality boundaries, and each slot's worst case is admitted to fit its width, so a diverging loop, an early return, a rejected input, or a fault moves no other partition's slot boundary.
· Accept: there is no donation, yield, or slack path by which one partition's progress can reach another's timing (R-07-032, R-07-036, R-11-006); the only progress quantity a compartment reads is its own slot width, which is the population-rung residual already booked (R-17-007) and not a second channel.
· Trace: CJ-NI, CJ-ISOL · [§8](verification-maximal-os.md#r-08-027b)

**R-08-027c** MUST: An exception, the fault class it raises, and the restart it causes are observations, so the fault path carries a confidentiality obligation and not only an availability one: a fault that is a function of secret-labeled data is a flow whether or not the machine survives it.
· Accept: the mechanism is R-16-002a and the residual is R-17-003a; a fault path treated only as a reliability event is a finding against this requirement.
· Trace: CJ-NI · [§8](verification-maximal-os.md#r-08-027c)

**R-08-028** IS: The security policy model, including the delimited-release bound and the robust-declassification statement, is a crown-jewel spec.
· Accept: it appears in the crown-jewel inventory and is subject to independent review.
· Trace: CJ-NI · [§8](verification-maximal-os.md#r-08-028)

**R-08-029** IS: Declassification is explicit capability use of exactly two kinds: the compose-time kind, manifest-declared as an edge in the capDL-class spec and covered by the base theorem directly; and the runtime kind, the powerbox grant, the sole source of an inter-level edge not in the manifest.
· Accept: no additional primitive is needed for either; capability use *is* declassification, already gated and auditable.
· Trace: CJ-NI, CJ-KERNEL · [§8](verification-maximal-os.md#r-08-029)

**R-08-030** MUST NOT: Dynamic information-flow control, if ever needed, is a Tier-1 server and never a kernel extension.
· Accept: the kernel tracks no labels; its trusted state does not grow.
· Trace: CJ-KERNEL · [§8](verification-maximal-os.md#r-08-030)

### 8.5 Authority over time and interrupts

**R-08-031** MUST: Clock read-out is authority: precision is granted through the time-service interface, coarse by default and nanosecond-capable only for a capability-authorized client; no compartment reads an architectural cycle, time, retirement, or performance counter.
· Accept: R-15-077 deletes the counters. There is **no clock-degradation mechanism**: a compartment without the time-service capability has no clock, and the finest interval it can observe is its own slot period, a composition-time constant. No value is fuzzed, nothing is drawn, and no component owns a degradation.
· Trace: CJ-NI · [§8](verification-maximal-os.md#r-08-031)

**R-08-031a** MUST NOT: Statistical clock degradation (jitter added to a counter read) is inadmissible on the same ground MTE and MBPTA/EVT are: it is recoverable by averaging over repeated reads, a statistic rather than a theorem.
· Accept: no admitted mechanism degrades a timing value probabilistically; the residual an untrusted compartment retains is the already-booked §11 population-rung channel (R-17-007), not a new exposure.
· Trace: CJ-NI · [§8](verification-maximal-os.md#r-08-031a)

**R-08-032** MUST: Interrupt-send is authority: an interrupt is a store to an interrupt file, so *who may interrupt whom* is a write capability in the static capability topology rather than a separate routing table. Interrupt-receive is a load from state the partition already owns and needs no separate authority.
· Accept: no interrupt-routing side table exists.
· Trace: CJ-CERISE · [§8](verification-maximal-os.md#r-08-032), [§8](verification-maximal-os.md#r-08-032-2)

**R-08-033** IS: There is no authority to *disable* interrupts, because there is no asynchronous delivery to disable: the attack the interrupt-state sentry discipline existed to stop is absent rather than bounded, and its two lemmas are vacuous rather than discharged.
· Accept: the boundary timer is unmaskable by construction, so the overhang is zero rather than capped (R-07-041).
· Trace: CJ-KERNEL · [§8](verification-maximal-os.md#r-08-033)

**R-08-034** MUST: Every app ships a capability manifest wired at compose time, and an app's manifest may declare an internal compartment graph with per-library sub-manifests, so least authority binds within an app and not only at its edge.
· Accept: the manifest is the authority record checked at admission (R-13-024).
· Trace: CJ-CERISE · [§8](verification-maximal-os.md#r-08-034)

### 8.6 The powerbox

**R-08-035** MUST: The powerbox holds only the authority from which grants are attenuated and nothing broader; an app never holds that authority and never renders its own consent UI.
· Accept: dynamic grants flow through the powerbox, not permission dialogs.
· Trace: CJ-NI · [§8](verification-maximal-os.md#r-08-035)

**R-08-036** MUST: A grant is an authenticated user act over the trusted consent path: a fresh selection of a specific object, on which the powerbox mints a capability CHERI-bounded to that object alone.
· Accept: no grant is minted without a witnessed consent act (R-06-017).
· Trace: CJ-NI, CJ-CERISE · [§8](verification-maximal-os.md#r-08-036)

**R-08-037** IS: A grant carries a temporal scope (one-shot, while-active, or persistent) enforced by the same first-class revocation, so *only this time* and *while using the app* are the capability model expressing itself, not a separate permission subsystem.
· Accept: no permission subsystem exists beside the capability model.
· Trace: CJ-CERISE · [§8](verification-maximal-os.md#r-08-037)

**R-08-038** MUST: While-active is a lease on a trusted clock, not a focus predicate with an untrusted evaluator, and is re-founded on three mechanisms so that the untrusted judgment can only ever *subtract*.
· Accept: neither obvious repair is taken: focus policy does not migrate into the consent TCB, and the scope does not collapse to one-shot.
· Trace: CJ-NI · [§8](verification-maximal-os.md#r-08-038)

**R-08-039** MUST: (1) The compositor's focus signal is wired revoke-only: it may assert *no longer active*, which kills the lease at once, and there is no channel by which it can assert *still active*.
· Accept: a compromised compositor's best play is premature revocation, an availability fault, never silent extension.
· Trace: CJ-NI · [§8](verification-maximal-os.md#r-08-039)

**R-08-040** MUST: (2) A trusted ceiling bounds the lease: the grant carries a maximum continued duration per resource class, measured on the kernel's trusted timebase and enforced by the powerbox through kernel-mediated grant expiry, past which only a fresh consent act restores authority.
· Accept: the worst case against a compromised compositor colluding with a compromised app is *bounded* continued access.
· Trace: CJ-NI, CJ-WCET · [§8](verification-maximal-os.md#r-08-040)

**R-08-041** MUST: (3) The unconditional cuts dominate the lease: the attested lock state and idle-lock, the away-gesture, the physical cutoffs, and the camera's mechanical shutter end a while-active grant whatever any software claims about focus.
· Accept: because a peripheral is electrically enabled only while a live grant holds it, a held-open grant is physically legible rather than silent (R-15-146).
· Trace: CJ-CERISE · [§8](verification-maximal-os.md#r-08-041)

**R-08-042** IS: The consent TCB does not grow to buy this: expiry is enforced by the powerbox and the kernel's revocation machinery, both already trusted, and the compositor keeps its focus policy outside the trusted set.
· Accept: the TCB inventory is unchanged by the lease mechanism.
· Trace: CJ-NI · [§8](verification-maximal-os.md#r-08-042)

**R-08-043** IS: What is given up is booked: while-active remains strictly weaker than one-shot, because the ceiling is a bound on exposure, not its absence.
· Accept: the §17 residual entry exists.
· Trace: CJ-NI · [§8](verification-maximal-os.md#r-08-043)

**R-08-044** IS: Sandboxing, portals, and container isolation are obviated by construction, not reimplemented.
· Accept: no such subsystem exists.
· Trace: CJ-CERISE · [§8](verification-maximal-os.md#r-08-044)

---

## §9. Boot & Root of Trust

### 9.1 The measured chain

**R-09-001** IS: The RoT is OpenTitan-class and integrated on-die, providing measured boot, key storage, TRNG, monotonic counters, and boot-attempt counting.
· Accept: it is the platform's only management processor (R-15-194).
· Trace: CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-001)

**R-09-002** MUST: The chain is RoT → verified M-mode firmware → per-core kernels of all classes → static image, with every stage measured and all signatures post-quantum (ML-DSA).
· Accept: no stage executes before its measurement is recorded.
· Trace: CJ-DEVTREE, CJ-CRYPTO-SPEC · [§9](verification-maximal-os.md#r-09-002)

**R-09-003** MUST: The first instruction executes from the RoT's on-die metal-mask boot ROM (immutable silicon in the attested mask set) with keys, lifecycle state, and anti-rollback counters in on-die OTP.
· Accept: there is no BIOS, no discrete SPI flash, and no socketed boot device.
· Trace: CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-003)

**R-09-004** MUST: The mutable boot payload lives in a fixed-physical-address boot region of raw NAND: reserved blocks at known addresses, A/B duplicated, written only by the A/B transactor at update commit.
· Accept: no FTL, no wear levelling, and no filesystem stands under boot; the ROM reads it through the same firmware-free ONFI PHY and fixed-function LDPC ECC engine the storage path uses.
· Trace: CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-004)

**R-09-005** MUST: The pre-kernel reader is not a parser: the boot payload is a flat measured image behind a fixed-layout, length-bounded header (offset, length, hash), verified by ML-DSA signature, checked against the monotonic anti-rollback floor, and measured before any byte of it executes.
· Accept: no interpreted container grammar and no followed offsets; a corrupt field fails the hash or signature check rather than steering a reader. The content-addressed store, the pack format, and the §13 verified reader come up only after the kernel and the FTL server, and stage zero never touches them.
· Trace: CJ-FORMAT, CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-005)

**R-09-006** MUST: The ROM's sequence is fixed and singular: verify and enter the RoT runtime firmware, walk the reset table, bring up the memory controller, pull both A/B headers, select per the boot-target latch and boot counting, place the verified M-mode image in main SRAM, and release the boot core into the measured chain.
· Accept: cold boot, deep-sleep wake, and the recovery generation all take this one path, so no second loader exists.
· Trace: CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-006)

**R-09-006a** MUST: The RoT's start-up entropy health tests (R-15-241b) complete before the first draw any measured stage can make, their verdict is measured into the chain, and on failure the RoT derives no key, unseals no material, and completes no attestation quote.
· Accept: the machine halts in a stated failure state rather than booting to a usable device on a weak root; the failure is a §16 fault class and not a boot-counting event, so the automatic A/B revert (R-09-028) is not its response and consumes no attempt.
· Trace: CJ-DEVTREE, CJ-CRYPTO-SPEC · [§9](verification-maximal-os.md#r-09-006a)

**R-09-007** MUST NOT: There is no UEFI, no SMM, no ACPI, and no option ROMs; a static devicetree instead declares core classes, islands, the NoC schedule, OPP tables, and radio calibration and limit values.
· Accept: the devicetree is attested (R-15-126).
· Trace: CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-007)

### 9.2 The RoT as TPM-without-TPM

**R-09-008** IS: The RoT realizes the TPM 2.0 *functional* surface (measured boot, seal/unseal, attestation quotes, monotonic anti-rollback counters) on the on-die RoT and verified crypto core, and not as a standardized TPM.
· Accept: the seal/unseal/quote surface is exposed to userspace as a capability-gated IPC service: a TPM's operations, never its command protocol.
· Trace: CJ-CRYPTO-SPEC · [§9](verification-maximal-os.md#r-09-008), [§9](verification-maximal-os.md#r-09-008-2)

**R-09-009** MUST NOT: A discrete TPM is declined as an unverified vendor black box over an external bus; a firmware TPM is declined for want of a foreign TEE; and running the RoT in TCG TPM 2.0 mode is declined on the command surface: a large, grammar-heavy register-slave command stream, an ambient send-commands interface rather than a capability-scoped typed IDL, with an algorithm-agility menu that readmits non-PQ primitives.
· Accept: the eUICC stays the only tolerated foreign trust domain.
· Trace: CJ-FORMAT, CJ-CERISE · [§9](verification-maximal-os.md#r-09-009)

### 9.3 Sleep and time

**R-09-010** MUST: Deep sleep is a boot-chain variant, not a resume path: suspend is seal-and-power-off of enumerated state, and wake re-executes the measured chain.
· Accept: the S3-trampoline/SMM-resume attack class has no analog because no resume path exists outside the measured chain.
· Trace: CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-010)

**R-09-011** IS: Cellular standby keeps the radio island continuously live at low duty cycle rather than resuming it from unmeasured state, so it adds no resume trampoline; islands that do power off still wake only through the measured chain.
· Accept: consistent with R-15-190.
· Trace: CJ-ISOL · [§9](verification-maximal-os.md#r-09-011)

**R-09-012** MUST NOT: The platform carries no persistent real-time clock: no coin cell, no always-powered RTC, and no CMOS-style non-volatile settings store.
· Accept: such a part would be the foreign always-on component the design refuses, and its reset-on-battery-removal is a liability.
· Trace: CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-012)

**R-09-013** IS: Nothing security-critical depends on wall-clock time: the RoT's monotonic counters are counters, not clocks, so a cold boot with unknown wall-clock time is safe: anti-rollback still holds and sealed keys stay sealed.
· Accept: the security core leans on counters and attestation nonces, never on time of day.
· Trace: CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-013)

**R-09-014** MUST: The device boots into an explicit *time-unknown* state and re-acquires calendar time from the network, trusting it only once authenticated, with Roughtime the bootstrap source.
· Accept: Roughtime is chosen over bare NTP (unauthenticated) and over NTS (whose TLS bootstrap needs a roughly-correct clock), establishing coarse trusted time from cold with no prior clock.
· Trace: CJ-CRYPTO-SPEC · [§9](verification-maximal-os.md#r-09-014)

**R-09-015** IS: Precision beyond that is a refinement on the same substrate, not a second clock: one time service disciplines a single wall-clock from cross-checked authenticated sources, and that wall-clock is a disciplined view over the scheduler's monotonic `mtime`, which stays a separate free-running counter.
· Accept: time-sync steering never perturbs scheduling or WCET.
· Trace: CJ-WCET · [§9](verification-maximal-os.md#r-09-015)

**R-09-016** MUST: A coarse monotonic time floor is persisted to non-volatile storage at controlled shutdown, at a write rate too low to wear the flash, so after reboot wall-clock time is known to be at least that floor and cannot be rolled back beneath it.
· Accept: Roughtime refines it upward to the true value.
· Trace: CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-016)

### 9.4 Lock state and duress

**R-09-017** IS: Lock state is attested key custody: Before First Unlock holds no per-profile user-data volume key resident, while the standby radio island keeps the device page-reachable.
· Accept: user data stays encrypted at rest in BFU.
· Trace: CJ-CRYPTO-SPEC · [§9](verification-maximal-os.md#r-09-017)

**R-09-018** MUST: The unlock credential drives a credential-gated BFU → AFU transition: the credential compartment matches it, the RoT rate-limits attempts, and only a correct match authorizes the crypto core to derive and hold the per-profile volume key and wake the application islands through the measured chain.
· Accept: no path derives the volume key without a correct primary-credential match.
· Trace: CJ-CRYPTO-SPEC, CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-018)

**R-09-019** MUST: On explicit lock or after a policy idle interval, the reverse runs as a scheduled RoT-attested global-mode transition: per-profile volume keys are zeroized in the crypto core and the application islands re-sealed, returning the device to BFU with the radio island still live.
· Accept: a device seized after unlock reverts to keys-not-resident at rest.
· Trace: CJ-CRYPTO-SPEC, CJ-ISOL · [§9](verification-maximal-os.md#r-09-019)

**R-09-020** MUST: Biometric match authority never survives a BFU transition: a cold or idle-locked device requires the primary credential.
· Accept: biometrics are strictly the AFU convenience factor, never the at-rest key-release root (R-12-019).
· Trace: CJ-CRYPTO-SPEC · [§9](verification-maximal-os.md#r-09-020)

**R-09-021** MUST: The attested lock state gates non-key authority too: lockout drops the microphone and camera and forces the USB data path charging-only, while the radio island stays page-reachable because the paging task still holds its capability.
· Accept: the cut is by grant revocation, not a special rule (R-15-147).
· Trace: CJ-CERISE · [§9](verification-maximal-os.md#r-09-021)

**R-09-022** MUST: A distinct duress credential, presented in place of the ordinary one, commands the RoT to crypto-erase rather than unlock: it destroys the sealing root wrapping the per-profile volume keys and the device-identity secret, rendering every user-data domain permanently unrecoverable in the time to zeroize a key.
· Accept: a key destruction rather than a bulk overwrite; SRAM volatility retains nothing across the power-down the erase forces.
· Trace: CJ-CRYPTO-SPEC · [§9](verification-maximal-os.md#r-09-022)

**R-09-023** IS: The erase is one-way and non-rollbackable, rooted in the RoT's monotonic-counter and sealing machinery, followed by an RoT reset, and indistinguishable to an observer from an ordinary failed attempt until it completes.
· Accept: the holder can be compelled to enter *a* credential, never the *right* one.
· RoT-fresh: the key-wrapping and sealing-root version (R-10-013), advancing on the duress erase and on key rotation.
· Trace: CJ-CRYPTO-SPEC · [§9](verification-maximal-os.md#r-09-023), [§9](verification-maximal-os.md#r-09-023-2)

**R-09-024** MUST: The erase is scoped to user-data key custody and not the system image, so the device is left clean rather than bricked: it re-derives a fresh identity from the RoT and boots the untouched signed generation into a clean first-run BFU state.
· Accept: erasing the reproducible system image would buy no confidentiality and would only signal resistance.
· Trace: CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-024)

### 9.5 Attestation and generation selection

**R-09-025** MUST: Attestation covers the chain *and* the admission discipline: checker version plus the spec and policy set every resident proof was checked against, plus the frozen ISA-profile version and the frozen radio-generation identity.
· Accept: the quote's vector is exactly this set.
· Trace: CJ-DEVTREE, CJ-SAIL · [§9](verification-maximal-os.md#r-09-025)

**R-09-026** MUST: Each signed generation emits a reference integrity manifest: the reference-value dual of the quote, covering the same vector, so a remote relying party can appraise evidence against expected values.
· Accept: it is per-generation and ML-DSA-signed, rides the A/B signed-generation machinery, and is served beside the quote by the sealing and attestation service; TCG RIM or IETF CoRIM encodings may be emitted for interop.
· Trace: CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-026)

**R-09-027** IS: What differs from a vendor RIM is the source of trust: because the base image is bit-for-bit reproducible from source, the reference values are *reproduced, not asserted*, and DDC bounds trusting-trust.
· Accept: any party regenerates the golden set from source; the manifest is trusted by reconstruction rather than by a manufacturer's signature over opaque blobs.
· Trace: CJ-T · [§9](verification-maximal-os.md#r-09-027)

**R-09-028** MUST: The platform carries A/B images, RoT boot counting with automatic revert, and a monotonic anti-rollback floor for security updates.
· Accept: all three are RoT duties.
· RoT-fresh: the base-image security-version floor (R-10-013), advancing on signed security updates.
· Trace: CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-028)

**R-09-029** MUST: User-selectable generation boot is a signed recovery generation, not a pre-kernel menu: a boot-time signal latched by the RoT into a one-bit boot-target register, measured into the chain like every other input, selects a minimal signed image whose sole role is to run the rollback-manager UI and the credential/unlock compartment.
· Accept: no unverified bootloader scripting, filesystem driver, or interactive environment runs before the kernel, so the recovery path adds no pre-kernel TCB surface.
· Trace: CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-029)

**R-09-030** MUST: Which generations are bootable is bounded by the monotonic anti-rollback floor: any retained generation at or above the floor may be selected, while generations below it stay visible in history and fully diffable but are not bootable.
· Accept: booting one would un-fix a shipped security update.
· Trace: CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-030)

**R-09-031** MUST: Selection is enacted by the system-integrity reader and A/B transactor as the same atomic two-slot flip an update takes, and authorizing it is credential-gated and consent-witnessed.
· Accept: a rollback cannot be triggered silently.
· Trace: CJ-NI, CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-031)

### 9.6 The lifecycle

**R-09-032** IS: The RoT lifecycle is a fixed enumeration of states held as one-way OTP fuse state (*raw*, *test*, *development*, *production*, *RMA*) under a fixed acyclic transition relation: raw to test, test to development or to production, development and production to RMA, and RMA terminal.
· Accept: exactly one state is readable at any time and it is a hardware input to the reset path rather than a software-writable register; no state outside the enumeration and no edge outside the relation exists in RTL or Sail, so development and production are siblings with no edge between them.
· Trace: CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-032)

**R-09-033** MUST: Lifecycle transitions are monotone: every transition burns OTP and advances along R-09-032's relation, and no reverse, reset, vendor-unlock, re-provisioning, or refurbishment path exists in any state.
· Accept: *no sequence of transitions re-enters a state the device has left* is a stated RTL ⊑ Sail obligation beside R-15-078's, discharged over the fuse state rather than over the provisioning flow.
· Trace: CJ-RTL-SAIL · [§9](verification-maximal-os.md#r-09-033)

**R-09-034** MUST: The transition out of the test state closes every manufacturing surface permanently: the Debug Module and trace (R-15-078), scan, BIST, the test straps, the manufacturing flash-programming path, and the provisioning interface, with no later transition re-opening any of them.
· Accept: test-mode re-entry, TAP unlock, and factory-mode escape name transitions R-09-032's relation does not carry, so each is an absent edge rather than a defeated check; every one of the surfaces is gated by the fuse state and not by a software check.
· Trace: CJ-RTL-SAIL, CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-034)

**R-09-035** MUST: RMA is the only edge out of production and is a forward transition: authenticated as R-15-079's debug entry is, preceded by that entry's crypto-erase before the Debug Module becomes live, re-opening no manufacturing surface (R-09-034), and terminal.
· Accept: a part in RMA holds no production key custody and has no transition back to production, so a debuggable part is never a fielded one.
· Trace: CJ-CRYPTO-SPEC, CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-035)

**R-09-036** MUST: The signature-verification roots the boot ROM accepts are diversified by lifecycle state as the sealing hierarchy is (R-15-079): in production the ROM accepts the production root alone, and no fuse, strap, or signed unlock token widens the accepted set.
· Accept: a development- or test-rooted image verifies in no production part, and the ROM carries no engineering-key or unlock-token path to be authorized.
· Trace: CJ-CRYPTO-SPEC · [§9](verification-maximal-os.md#r-09-036)

**R-09-037** MUST: The RoT extends the lifecycle state into the measured chain as its first extension, before the ROM verifies any payload, and the reference integrity manifest (R-09-026) carries the production value as the expected one.
· Accept: every later measurement is bound to the state it ran under and a relying party appraises a debuggable part from its quote rather than inferring it; R-09-025's vector is not widened, the state entering as a chain measurement rather than as a further field.
· Trace: CJ-DEVTREE · [§9](verification-maximal-os.md#r-09-037)

---

## §10. Storage & State

### 10.1 The verified stack

**R-10-001** MUST: The base is an immutable content-addressed Merkle-DAG image with a signed root, every read runtime-verified against the boot-attested root by the system-integrity reader, and bit-for-bit reproducible from source.
· Accept: no read of the base image bypasses the verification.
· Trace: CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-001)

**R-10-002** IS: The storage path is four verified layers on one prover: L0, the Perennial/GoJournal-lineage crash-safe write-ahead log in Iris/Coq; L1, the VeriBetrFS B^ε-tree *design* re-proved in Coq/Iris; L2, filesystem semantics following RefFS with (S)FSCQ; L3, the SFSCQ/DiskSec data-noninterference method.
· Accept: each layer's proof is a Coq artifact; no layer carries a foreign-prover proof into the trust base.
· Trace: CJ-T · [§10](verification-maximal-os.md#r-10-002)

**R-10-003** MUST: L1 is one parametric index, generic over key type, verified once and instantiated per object class.
· Accept: no per-object-class index proof exists.
· Trace: CJ-T · [§10](verification-maximal-os.md#r-10-003)

**R-10-004** IS: The B^ε buffered-update refinement is kept deliberately, its message-log batching cutting NAND write amplification and therefore device wear, an endurance gain, with a plain CoW B+ tree over the L0 journal as the strictly-smaller-proof fallback.
· Accept: because the design is re-proved in Coq/Iris it is not a non-Coq anchor.
· Trace: CJ-T · [§10](verification-maximal-os.md#r-10-004)

**R-10-005** IS: L2 represents inodes, dirents, extents, and xattrs as typed keys in one keyspace, with snapshots a version field *in* the key, giving O(1) writable snapshots.
· Accept: one keyspace, one index proof.
· Trace: CJ-T · [§10](verification-maximal-os.md#r-10-005)

**R-10-005a** MUST: Typed object metadata and queries are views of the existing L1/L2 keyspace, not a second database: an object is identified by its content address (the per-domain keyed plaintext digest for user data, the store's content hash for system-image objects) or, where mutable, by its filesystem object identity, and each carries a fork-and-frozen content-type identifier plus schema-bounded attributes.
· Accept: no independent metadata database, indexer, or crawler exists, and metadata identity forms no bare cross-domain content hash of user data, so R-10-016's cross-domain incomparability is preserved. The content address is taken over an encoding whose descriptor carries the R-05-051a canonicity theorem, per R-05-051c, so one object cannot present two addresses and two objects cannot present one.
· Trace: CJ-T, CJ-IDL · [§10](verification-maximal-os.md#r-10-005a)

**R-10-005b** MUST: Secondary metadata indexes are instantiations of the one parametric L1 index, keyed by confidentiality domain and a stable namespace *identifier* as well as typed attribute value and object identity, and update atomically with the object and metadata in the same L0 transaction.
· Accept: no capability is written into a key (a key is a persisted typed value; the presented namespace capability is checked at query admission against that identifier), no index spans confidentiality domains, and no query returns an object capability not derivable from the presented namespace capability.
· Trace: CJ-T, CJ-NI · [§10](verification-maximal-os.md#r-10-005b)

**R-10-005c** MUST: A live query is a bounded subscription whose ordered add/remove deltas are derived only after the committing L0 transaction and delivered over a bounded SPSC ring; overflow emits one rescan-required marker rather than buffering without bound or backpressuring commit.
· Accept: the subscription has a composition-time result and queue bound; a subscription is volatile and does not survive a crash, so recovery re-establishes it by rescan, and index and objects are never observed mismatched.
· Trace: CJ-T, CJ-WCET, CJ-NI · [§10](verification-maximal-os.md#r-10-005c)

**R-10-006** MUST: RefFS's machine-checked deadlock- and livelock-freedom (the MoLi dynamically-layered-definite-releases discipline) is a precondition for §11 temporal admission of any task that calls a shared storage server.
· Accept: a deadlocked or livelocked server is unbounded blocking no WCET bound survives; system-wide deadlock-freedom is the concurrent complement to §13's per-handler termination obligation.
· Trace: CJ-WCET · [§10](verification-maximal-os.md#r-10-006)

**R-10-007** MUST: The four verified layers are verified C compiled by CompCert and proved in Coq, running with no managed runtime: GoJournal's design and specification transfer, its Go and its Goose/GooseLang proofs do not.
· Accept: Dafny/Z3 and Yggdrasil's Z3/Rosette are declined as bases and retained only as unverified cross-checks.
· Trace: CJ-COMPCERT · [§10](verification-maximal-os.md#r-10-007)

**R-10-008** MUST: L0 is re-expressed from that design directly in Gallina and lowered GC-free through the CompCert-C + VST/Iris path, with CN + Fulminate as the CHERI-C reference that de-risks it and its SMT automation an untrusted oracle.
· Accept: no bespoke Goose-to-C translator is built; what is rebuilt for L0 is the refinement proof against the C, not an extraction tool.
· Trace: CJ-COMPCERT · [§10](verification-maximal-os.md#r-10-008)

**R-10-009** MUST: The four-layer stack is wholly non-TCB, holding the read-only content-addressed system image and the mutable per-profile user subvolumes alike; the only storage component in the TCB is the system-integrity reader and A/B transactor.
· Accept: the crash-safe journal and the write-optimized CoW B-tree leave the trust base entirely; the transactor commits by flipping the signed root past the anti-rollback floor, not by trusting the filesystem's journal.
· Trace: CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-009)

### 10.2 Mutable filesystem

**R-10-010** IS: Bcachefs-class semantics fall out of the unified CoW B-tree: reflinks are refcounted CoW extent sharing, snapshots are retained roots keyed by snapshot-version, dedup is content-addressed extent sharing addressed by a per-domain keyed plaintext digest, and checksums are the per-extent AEAD tags serving integrity alone.
· Accept: the immutable base image stays a content-addressed Merkle DAG; this CoW B-tree is the mutable user-data structure.
· Trace: CJ-T · [§10](verification-maximal-os.md#r-10-010)

**R-10-011** MUST NOT: The mutable user-data volume is deliberately not freshness-protected by the RoT monotonic counter, because sealing its root would advance the counter at CoW-commit frequency, which no OTP or hardware monotonic counter sustains.
· Accept: the decision is stated as a design choice with its consequence, not omitted.
· Trace: CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-011)

**R-10-012** IS: The mutable volume carries confidentiality and tamper-*detection* from the per-extent AEAD with volume keys resident only in the crypto core, so offline forgery or corruption is caught on the authenticate-then-return read path; only *freshness* is surrendered.
· Accept: a whole-volume rollback to an authenticated-but-stale state is a below-the-line availability/consistency event for the bulk class, not an integrity breach, since a physical adversary who can rewrite the disk can equally destroy it; the reading is scoped to that class rather than asserted of every stored byte, R-10-013b taking the security-bearing state out of it by declaration.
· Trace: CJ-CRYPTO-SPEC · [§10](verification-maximal-os.md#r-10-012)

**R-10-013** MUST: The RoT monotonic counter is spent only on low-rate security-critical state, and that set is enumerated: the base-image security-version floor, the key-wrapping/sealing-root and credential attempt-counter versions, and the durable-state freshness-epoch root, advancing on signed updates, key rotation, authentication attempts, or a sealed epoch, and never on a data commit.
· Accept: the enumeration is closed by conferral rather than by amendment (R-10-013a); it is what blocks downgrade to a vulnerable generation, un-revoking a key, resurrecting an old password, replaying the lockout counter, and replaying a spent payment, a superseded revocation list, or a consumed one-time operation.
· Trace: CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-013)

**R-10-013a** MUST: Membership in that enumeration is conferred entry by entry: a requirement placing state under the RoT monotonic counter confers the membership against itself, R-10-013 is where the conferrals are collected, and neither a member no requirement confers nor a conferral R-10-013 does not carry is admitted.
· Accept: R-10-013 names the attacks the set blocks and asserts nothing about the map from attack to counter-protected state being total, so a state that later needs freshness and does not get it is invisible to it; conferral closes the disagreement between the set and the requirements and does not close completeness, which is the same honest half R-17-030r claims for the fail-closed register.
· Accept: four requirements confer freshness, and a fifth conferral is not admitted until R-10-013 names the state it adds.
· Trace: CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-013a)

**R-10-013i** MUST: State deliberately left outside the enumeration is recorded as a decision rather than surviving as an absence, and a class taken back out of that exclusion is recorded the same way.
· Accept: R-10-011 is the exclusion and the mutable volume the state it holds out; R-10-013b is the class taken back. An exclusion carried by neither a requirement nor a stated decision is a review-gate finding against R-10-013a, an absence being indistinguishable from an oversight wherever nothing records it.
· Trace: CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-013i)

**R-10-013b** IS: The asset-class split under the RoT monotonic counter is three-way and not two: beside the low-rate platform state the counter keeps fresh and the bulk user data whose freshness is surrendered stands durable application state whose staleness is itself the security event, declared `Fresh` and carried by a freshness epoch rather than by the mutable volume's root.
· Accept: a spent payment record, a revocation or consumed-token list, a one-time operation's completion mark, and an application's own attempt counter are `Fresh` by declaration in a manifest admission prices, never by a per-feature runtime judgment.
· Trace: CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-013b)

**R-10-013c** MUST: The crypto core computes one root over the version of every `Fresh` region and the RoT advances a reserved counter and seals that root once per sealed epoch, never once per data commit; a `Fresh` write is acknowledged when its epoch seals, and an epoch that does not seal loses its writes rather than presenting them as fresh.
· Accept: the epoch root is a crypto-core operation beside seal/open and the keyed dedup digest, so the class widens an existing TCB interface and adds no trusted component and no §12 compartment; what the counter spends is set by the epoch rate and not by the write rate, which is the objection R-10-011 raises against sealing the volume root.
· RoT-fresh: the durable-state freshness-epoch root (R-10-013), advancing once per sealed epoch.
· Trace: CJ-CRYPTO-SPEC, CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-013c)

**R-10-013d** MUST: The sustained epoch ceiling is a composition constant computed from the monotonic counter's rated endurance and the target service life, each compartment declares the `Fresh` regions it owns and the commit rate it needs, and admission refuses a composition whose declared rates sum past that ceiling.
· Accept: a compartment committing faster than its admitted share blocks until its next epoch rather than advancing the counter out of turn, and the platform state R-10-013 enumerates holds a reserve no application rate can crowd out.
· Fail-closed: a composition whose declared freshness commit rates exceed the counter's rated endurance is refused at admission (R-17-030q); the cost lands on delivery rather than on a running unit.
· Trace: CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-013d)

**R-10-013e** MUST: A `Fresh` region whose version does not verify against the sealed epoch root is refused rather than returned, so a rolled-back volume denies that state instead of resurrecting it.
· Accept: the refusal is the property rather than a consequence of it, and the availability cost falls on exactly the class whose staleness would otherwise be a security event.
· Fail-closed: a `Fresh` read that cannot be proved fresh refuses (R-17-030s); a physical adversary with access to the storage thereby holds a permanent denial of that state.
· Trace: CJ-CRYPTO-SPEC, CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-013e)

**R-10-013f** IS: R-10-011's exclusion rests on a memory technology's wear budget rather than on the architecture, so it is a conditional lever: a RoT monotonic counter medium with no wear-out mechanism would collapse the epoch and its quota into a per-commit seal, and the named candidate is spin-orbit-torque MRAM, whose write current passes through a track beside the tunnel barrier rather than through it.
· Accept: the candidate is named so the condition is checkable rather than aspirational, the dielectric-breakdown mechanism producing the retention-versus-endurance trade in the spin-transfer-torque cell being absent from it rather than mitigated.
· Trace: CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-013f)

**R-10-013g** MUST: Reopening R-10-011 requires both that the medium's rated endurance cover a per-commit seal over the target service life with margin at full non-volatile retention rather than at the cache-lifetime retention the published back-end-integrated results assume, and that the tamper class the medium introduces be closed, by a medium carrying no net moment for a field to torque or by a field-and-temperature sentinel in the detector class.
· Accept: satisfying both retires R-10-013c and R-10-013d and reaches R-10-013e not at all, a region that cannot be proved fresh being refused whatever the counter is made of; until both hold the epoch stands, and an endurance figure quoted at cache retention discharges neither.
· Trace: CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-013g)

**R-10-013h** IS: Magnetoelectric antiferromagnetic memory is the medium that would close R-10-013g's second condition outright, carrying no net moment for a field to torque, and it is recorded at the maturity it has: prototype voltage-driven Néel-vector rotation in zero applied field, with no addressable array, no endurance or retention figure, no read margin at scale, and an ordering temperature close enough to the operating range that a thermal excursion becomes a question about the stored state.
· Accept: the electrical-switching literature it rests on carries published nulls, switching-shaped transport signatures reproduced in structures containing no antiferromagnet and scaling with substrate heat conduction, so the entry exists to stop *antiferromagnets are field-immune* being read as evidence that the memory exists.
· Trace: CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-013h)

**R-10-014** MUST: Secure erase is crypto-erase: the volume keys being RoT-sealed and core-resident, destroying the sealing root renders the encrypted user data unrecoverable in the time to zeroize a key.
· Accept: rolling the disk back yields only stale ciphertext an attacker cannot read and cannot pair with a resurrected key.
· Trace: CJ-CRYPTO-SPEC · [§10](verification-maximal-os.md#r-10-014)

**R-10-015** MUST: Dedup addresses on a per-domain keyed digest (a PRF/MAC of the plaintext under a dedup key domain-separated by KDF from the volume key) computed inside the crypto core and handed to the filesystem as an opaque tag beside the ciphertext and its integrity tag.
· Accept: keys never leave the core and the filesystem sees only ciphertext and tags.
· Trace: CJ-CRYPTO-SPEC · [§10](verification-maximal-os.md#r-10-015)

**R-10-016** MUST: Dedup never crosses a key or confidentiality domain: the digest is deterministic within a domain yet incomparable across domains and uncomputable without the domain key.
· Accept: cross-domain content-equality, a confirmation-of-file oracle, is impossible by construction, not forbidden by convention.
· Trace: CJ-NI · [§10](verification-maximal-os.md#r-10-016)

**R-10-017** MUST NOT: Convergent encryption (key = plaintext hash) is rejected *within* a domain for the same reason it is rejected across them: it would leak plaintext equality to anyone, not only holders of the domain key.
· Accept: no scheme derives a key from plaintext.
· Trace: CJ-NI · [§10](verification-maximal-os.md#r-10-017)

**R-10-018** MUST NOT: Filesystem compression is out of scope, and its removal is a security gain: it deletes the compress-then-encrypt ratio oracle and removes a decompressor from the read data path, which is authenticate-then-return.
· Accept: no decompressor exists on any read path.
· Trace: CJ-NI · [§10](verification-maximal-os.md#r-10-018)

**R-10-019** IS: The exclusion is scoped to *filesystem* compression and does not reach a single-owner, build-time-compressed signed image expanded once on the install or load path: one compressor, one trust domain, no runtime state, the decompressor below the integrity line, its expanded bytes hash-verified against the signed root.
· Accept: expansion is a bounded §11 task, never per read.
· Trace: CJ-WCET, CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-019)

**R-10-020** IS: Build-time compression buys *stored* bytes, never *resident* ones: every live byte is a capability-delegated SRAM byte with no swap, no overcommit, and no demand paging.
· Accept: it is not a capacity lever. The resident-code axis is a separate question with a separate answer, settled by the dictionary encoding (R-15-036a), which is the *resident* form rather than a stored one and so does touch the ceiling this requirement says artifact compression does not.
· Trace: CJ-MEMPLAN · [§10](verification-maximal-os.md#r-10-020)

**R-10-021** IS: Replication, erasure coding, tiering, the bucket allocator with copying garbage collector, and the host-side FTL server over raw NAND sit below the integrity line as contained block services trusted only for availability.
· Accept: a mis-placed or lost block is caught by the AEAD/Merkle-DAG layer above, never an undetected corruption.
· Trace: CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-021)

### 10.3 Authenticated encryption at rest

**R-10-022** MUST: Confidentiality and integrity of data at rest are one pass: per-extent AEAD with a per-extent nonce, the Poly1305/GHASH tag serving as the stored checksum, keyed per confidentiality domain, with keys resident only in the crypto core.
· Accept: the filesystem compartment handles ciphertext extents and tags and invokes seal/open, never raw key material, so the constant-time obligation lands on the crypto core rather than the filesystem.
· Trace: CJ-CRYPTO-SPEC, CJ-CT-SOUND · [§10](verification-maximal-os.md#r-10-022)

**R-10-023** MUST: The AEAD tag is the integrity checksum only and never the dedup address, so the nonce stays per-extent-random (semantic security intact) while the dedup address stays deterministic within a domain.
· Accept: the two properties are never conflated in the interface to the crypto core.
· Trace: CJ-CRYPTO-SPEC · [§10](verification-maximal-os.md#r-10-023)

**R-10-024** MUST: The cipher is frozen to AES-GCM via `Zvkned`/`Zvkg`, one cipher and not a menu; ChaCha20/Poly1305 is the frozen-out alternative, `Zvbb`/`Zvbc` remaining in the profile for Keccak and PQ rather than for a second filesystem cipher.
· Accept: carrying both would double the constant-time crown jewel and the filesystem-cipher Sail surface for no security gain.
· Trace: CJ-LEAK, CJ-CRYPTO-SPEC · [§10](verification-maximal-os.md#r-10-024)

**R-10-025** IS: The verifiable-encryption claim is a composition: the §5 three-layer crypto proof joined with the L3 data-noninterference theorem, *(the AE scheme is IND-CCA/INT-CTXT) ⋈ (the filesystem leaks nothing across domains)*, at the primitive's functional spec, itself a crown-jewel spec.
· Accept: this is the AE ⋈ non-interference seam lemma (R-05-160).
· Trace: CJ-REDUCTION, CJ-NI · [§10](verification-maximal-os.md#r-10-025)

### 10.4 Statelessness and generations

**R-10-026** IS: The running system is an immutable, signed, content-addressed image (OS, apps, and the compiled declarative config generation) plus enumerated mutable volumes; everything else is tmpfs, gone at reboot.
· Accept: the mutable-volume set is enumerated at composition.
· Trace: CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-026)

**R-10-027** MUST: System and user data are separated by subvolume and confidentiality domain, not by partition or separate filesystem: each user's mutable data is its own subvolume, its own confidentiality domain with a per-domain key, reached only through its own capability.
· Accept: subvolumes share one free-space pool, snapshot and reflink in O(1), and ride the single verified codebase.
· Trace: CJ-NI, CJ-CERISE · [§10](verification-maximal-os.md#r-10-027)

**R-10-028** MUST: System configuration is declarative and compiled into the generation rather than a mutable `/etc` overlay, so it is reproducible and attested rather than editable at runtime.
· Accept: no runtime-editable system configuration exists.
· Trace: CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-028)

**R-10-029** MUST NOT: No trusted component parses text configuration at runtime: config compiles to typed, signed objects per generation.
· Accept: no text-config parser appears in the TCB.
· Trace: CJ-FORMAT · [§10](verification-maximal-os.md#r-10-029)

**R-10-030** MUST: The generation history is a signed, diffable log: the platform retains the last N signed generation roots under a retain-K-plus-pinned policy, each point named by its signed root, with the change between any two computed as a structured diff of three signed inputs: image, config, and reference integrity manifest.
· Accept: every historical point and every diff is signed and reproducible from source, so the history cannot be forged and a diff is verifiable rather than merely reported.
· Trace: CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-030)

**R-10-031** IS: The diff is structured data surfaced through the rollback-manager service, and rolling back is selecting a prior root, bounded by the anti-rollback floor.
· Accept: the rollback-manager UI is outside the TCB (R-06-022).
· Trace: CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-031)

**R-10-032** MUST: FDE keys are sealed to the RoT and measured state; per-profile volume keys are resident only After First Unlock, released into the crypto core by the credential-gated unlock transition and zeroized on lock or idle timeout, so the Before-First-Unlock state holds no user-data key; memory is zeroized at shutdown.
· Accept: the BFU key inventory is empty.
· Trace: CJ-DEVTREE, CJ-CRYPTO-SPEC · [§10](verification-maximal-os.md#r-10-032)

**R-10-033** IS: Factory reset is discarding the volumes; device identity re-derives from the RoT.
· Accept: no identity material survives the reset outside the RoT.
· Trace: CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-033)

**R-10-034** MUST: Profile-free static layout orders functions from the admitted composition and typed-callee graph and basic blocks from the typed control-flow graph plus the backward-taken / forward-not-taken rule, using a fixed tie-break and recording the final order in the signed image.
· Accept: the build uses no PGO corpus, sampled frequency, learned weight, runtime feedback, or new mutable state; layout may reorder but never clone code or enlarge the image, and the resulting order feeds WCET directly.
· Trace: CJ-WCET · [§10](verification-maximal-os.md#r-10-034)

**R-10-035** MUST: A compartment declares its durable state as typed regions in its manifest, within the enumerated mutable volumes, and the platform checkpoints them into the owning confidentiality domain's subvolume under that domain's key; applications author no serializer, autosave loop, or recovery path.
· Accept: the durable path is the verified L0/L1/L2 stack, so per-application persistence inherits its crash-refinement theorem rather than each application's ad-hoc recovery being an unproved crash surface.
· Trace: CJ-DEVTREE, CJ-FORMAT · [§10](verification-maximal-os.md#r-10-035)

**R-10-035a** MUST: A declared durable region is either `Fresh` or rollbackable and its declared type carries the kind, the platform promoting or demoting no region between the two.
· Accept: a `Fresh` region is admitted against the epoch quota, commits on an epoch seal, and denies a read it cannot prove fresh, while every other region is the ordinary class whose restore point is the checkpoint before it; the explicit commit an externally visible or non-repeatable effect is told to take (R-17-043a) is this declaration and not an obligation handed back to the application.
· Trace: CJ-DEVTREE, CJ-FORMAT · [§10](verification-maximal-os.md#r-10-035a)

**R-10-036** MUST: A checkpoint is taken only at a declared quiescent point and committed as a single L0 journal transaction; restoring is never a resume but a measured boot, a manifest-reconstructed compartment, ordinary initialization, and only then a read of the durable regions.
· Accept: the checkpoint is an admitted slot rather than a preemption, no partially updated region is ever committed, and durable state is bound to its schema and image generation so an update supplies a checked migration or discards.
· Trace: CJ-WCET, CJ-DEVTREE · [§10](verification-maximal-os.md#r-10-036)

**R-10-037** MUST NOT: A checkpoint never contains execution state, capabilities or tags, keys, DRBG state or nonces, leases, consent grants or powerbox decisions, or connection, session, or device state.
· Accept: authority is re-derived at restart from the manifest and the current revocation epoch, so no restore resurrects an authority a revocation retired and storage is never a second origin of authority beside composition.
· Trace: CJ-CERISE, CJ-CRYPTO-SPEC · [§10](verification-maximal-os.md#r-10-037)

---

## §11. Updates

### 11.1 Update mechanism

**R-11-001** IS: Updates are image-based, atomic, and A/B, with health-gated auto-rollback; deltas fall out of content addressing and the running base is never mutated.
· Accept: no in-place mutation of a running generation exists.
· Trace: CJ-DEVTREE · [§11](verification-maximal-os.md#r-11-001)

**R-11-002** MUST: Rollback is pinning a prior signed root subject to the anti-rollback floor, by either the automatic health-gated path or the user-driven path, and both commit through the one trusted transactor.
· Accept: the UI only stages a target; the transactor and RoT enforce the signed-root check and the floor, and authorizing a user-driven rollback is credential-gated and consent-witnessed, so neither a compromised manager nor a malicious app can silently downgrade the device.
· Trace: CJ-DEVTREE, CJ-NI · [§11](verification-maximal-os.md#r-11-002)

**R-11-003** IS: Because no foreign computers exist, this is the update mechanism for the entire machine: there are no vendor firmware side-channels to update, and nothing updates outside a proof-checked generation.
· Accept: the update inventory covers radio, storage, display, and everything else.
· Trace: CJ-CERISE · [§11](verification-maximal-os.md#r-11-003)

**R-11-004** MUST: The radio generation is a separately versioned, attested artifact: patchable for security within the certified envelope, re-certified as a delta when its protocol behaviour changes.
· Accept: consistent with R-12-056.
· Trace: CJ-DEVTREE · [§11](verification-maximal-os.md#r-11-004)

**R-11-005** MUST: Proof-checked admission: the transactor commits a generation only after the on-device checker validates every new binary's proof against the current spec-set and Sail-model versions.
· Accept: proofs are generation-scoped, so revving either forces re-admission, and static composition is preserved.
· Trace: CJ-TAL-SOUND, CJ-SAIL · [§11](verification-maximal-os.md#r-11-005)

### 11.2 Temporal admission

**R-11-006** MUST: The task set admits only with a machine-checked schedulability proof: for the static cyclic executive an interval-arithmetic check in the same checker (the slot WCETs fit the major frame and each task's period is harmonic with it), not Prosa-style response-time analysis.
· Accept: the proof is a Coq artifact, not an analysis report.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-006)

**R-11-007** MUST: Monitor availability and watchdog-before-deadline ship as theorems; radio deadlines (HARQ feedback, ACK windows, idle-mode DRX paging reception, link-layer connection-event anchoring) are admitted hard tasks; the same proof yields the hardware watchdog's window parameters.
· Accept: one artifact yields all three.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-007)

**R-11-008** MUST: Two standing reservations are part of every admitted schedule rather than implied: the display-scanout reservation (its static TDM NoC slice, framebuffer bank binding, and line-period deadline) and the §8 revocation sweep's background slot class.
· Accept: neither the always-on display nor the containment machinery is an unbudgeted interference term.
· Trace: CJ-WCET, CJ-ISOL · [§11](verification-maximal-os.md#r-11-008)

**R-11-009** MUST: Admission counts the switch-duty ratio σ = C_switch / T_poll explicitly instead of absorbing it into slack: a task's real cost is its in-slot WCET plus the partition-switch constant times its visit rate.
· Accept: the ratio is recorded per task in the admission artifact.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-009)

**R-11-010** MUST: Lever (1), applied first: raise the cadence bound by buffering, not by relaxing the deadline. A device with a ring or FIFO of depth *D* need only be visited before *D* arrivals accumulate, so buffer depth is a scheduling parameter fixed at composition beside the slot widths.
· Accept: what it trades away is latency, bounded by the deadline half of the sizing rule, so the two halves constrain each other.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-010)

**R-11-011** MUST: Lever (2): where the deadline rather than the buffer sets the cadence, a device server whose admissible T_poll drives σ past the composition threshold is inadmissible as a slotted task and is statically pinned to a core of its class.
· Accept: pinning *deletes* rather than reduces the switching cost: a core running one partition performs no partition switch, so `fence.t`, zeroize, and OPP relock all leave its budget together.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-011)

**R-11-012** IS: This is the general rule the radio PHY pair and the sentinel were already instances of, now derived rather than assumed: any other device server failing σ is treated the same way instead of special-cased.
· Accept: consistent with R-15-114 and R-07-034.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-012)

**R-11-013** IS: The complementary half is that everything else gets long slots: with the high-rate servers off the slot wheel, the major frame carries few switches and the switch constant amortizes to a negligible fraction.
· Accept: the pinning rule and the long-slot property are one decision, both falling out of the recorded inequality.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-013)

**R-11-014** IS: Static core assignment reduces the heterogeneous-multiprocessor problem to independent per-core uniprocessor analyses, each against its class's WCET table.
· Accept: no global multiprocessor schedulability argument is required.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-014)

**R-11-014a** MUST: Each core's major frame carries a composition-fixed phase offset against one platform-wide origin, stated in spine cycles (R-15-195) and emitted in the admission artifact beside the slot widths, the OPP assignment, and the TDM NoC schedule.
· Accept: no per-core schedule is admitted without its offset, and the offsets are public constants of the generation exactly as the widths are, so the binding introduces no runtime decision and no new observable.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-014a)

**R-11-014b** MUST: The admission artifact carries a derived worst-case end-to-end bound for every cross-core chain the composition declares, computed from the frame offsets and the per-hop slot periods over the R-07-007 edges, a pinned core (R-11-011) contributing its poll-loop period in place of a frame offset; a chain whose derived bound exceeds the deadline its declaration carries fails admission.
· Accept: R-07-042 holds without exception where a hop is a core boundary rather than a slot boundary, and no admitted chain carries an underived latency.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-014b)

**R-11-014c** MUST: The composition tool chooses the offsets against the R-11-014b bounds as an objective, phasing a callee's slot behind its caller's and aligning the wheels of the several V-class cores one data-parallel task spans.
· Accept: the offsets are inputs the R-11-006 check re-reads, quantifying over widths and offsets and never occupants (R-11-023), so a poor choice costs latency and never soundness, the R-15-110 shape applied to the schedule as R-11-015a applies it to the bounds.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-014c)

**R-11-014d** MUST: Every rung of the R-11-021 ladder shares one major-frame length, subdividing the discretionary band rather than lengthening the frame (its reserved band being identical across rungs by R-11-020), so no rung swap shifts a frame origin.
· Accept: the R-11-014b bounds are proved once per generation rather than per rung; a global mode change (R-11-018) re-phases and carries its own offsets and chain bounds as part of being an independently admitted complete schedule.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-014d)

**R-11-015** MUST: WCET tables are derived, not asserted: each per-(class, operating-point) entry is a syntax-directed max-path sum over the binary's typed control-flow graph with the timing-annotated Sail model as its per-instruction latency table, riding as cost annotations on the CHERI-TAL derivation the on-device checker already validates.
· Accept: a wrong table cannot silently pass admission; only a wrong timing-annotation *statement* can, and that is a crown-jewel spec.
· Trace: CJ-WCET, CJ-SAIL · [§11](verification-maximal-os.md#r-11-015)

**R-11-015a** IS: A bound is a quantity the toolchain chooses and not merely one it reports: the frame being non-work-conserving, a task's billed width is its bound rather than its elapsed time, so each tightening the R-18-014c backends earn returns to this check as frame capacity to allocate (a longer discretionary band, a higher population rung, or a task set that would not otherwise admit).
· Accept: the direction is one-way and requires no trust in the producer, admission always consuming the bound re-derived from the shipped binary (R-11-015), so bad lowering costs capacity and never soundness, and a claimed tightening the derivation does not support fails admission rather than shipping a schedule that does not hold.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-015a)

**R-11-016** IS: The control tier's WCET is structural rather than estimated: Lustre/Vélus control planes compile to loop-free, statically-sized reactions, so the estimator's loop-bound and path analysis concentrate on the Rust data planes.
· Accept: consistent with R-05-054.
· Trace: CJ-VELUS, CJ-WCET · [§11](verification-maximal-os.md#r-11-016)

**R-11-017** MUST: WCET tables are per (class, operating point), and the admission proof selects each partition's OPP (the slowest point meeting deadlines), emitting the OPP assignment, the TDM NoC schedule, and the watchdog windows as one artifact, itself a crown-jewel spec: admission is decided against the schedule the artifact states, not against the machine that runs it.
· Accept: one artifact, three outputs.
· Trace: CJ-WCET, CJ-ISOL · [§11](verification-maximal-os.md#r-11-017)

**R-11-018** MUST: Global mode schedules are each independently admission-proved complete schedules, and switching between them is a rare, RoT-attested global transition on explicit authority, never load-following.
· Accept: consistent with R-15-189.
· Trace: CJ-NI · [§11](verification-maximal-os.md#r-11-018)

### 11.3 Compartment population as a schedule axis

**R-11-019** IS: Compartment population is a second schedule axis and deliberately not the global-mode one, because opening a browser tab changes no operating point, NoC schedule, or watchdog window, and folding the two into one transition class would make the honest mechanism unusable at the rate ordinary interaction demands.
· Accept: population is built from the same admission artifact and carries none of the attestation weight.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-019)

**R-11-020** MUST: (1) The major frame on every app-hosting core splits at composition into a reserved band and a discretionary band, and the reserved band (hard tasks, the display reservation, the sweep class, system servers) is identical across every rung.
· Accept: the hard-deadline half of the schedulability proof is discharged once and re-used, and no population change can move a deadline or perturb a hard task.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-020)

**R-11-021** MUST: (2) The discretionary band is subdivided by population rungs: a short geometric ladder, each rung an independently admission-proved complete schedule, every rung bound into the same signed generation and measured at boot.
· Accept: the ladder is a composition constant (4/8/16/32 per C-class core in the reference instantiation).
· Trace: CJ-WCET, CJ-DEVTREE · [§11](verification-maximal-os.md#r-11-021)

**R-11-022** MUST: (3) Within a rung the discretionary band is shaped as one focus slot plus (n−1) background slots, the focus slot taking a composition-fixed majority of the band.
· Accept: interactive latency does not divide by *n* even though aggregate share does.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-022)

**R-11-023** MUST: (4) Which compartment occupies which slot is a permutation, not a schedule: slot widths and offsets are fixed by the rung, and the compositor requests a focus rebinding at a major-frame boundary which the kernel enacts by permuting the slot→compartment map.
· Accept: every admission property is invariant under the permutation, the interval arithmetic quantifying over widths and offsets and never occupants; the untrusted compositor steers responsiveness without touching the admitted schedule, the same shape §8 gives its focus judgment.
· Trace: CJ-WCET, CJ-NI · [§11](verification-maximal-os.md#r-11-023)

**R-11-024** IS: (5) A rung change is a table swap at a major-frame boundary, not an admission event: it selects among schedules the generation already proved, so it is neither RoT-attested nor rare, costing one partition-switch constant plus the table load.
· Accept: it may fire every time the user opens or closes a tab.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-024)

**R-11-025** IS: (6) It is still not load-following: the rung index is a function of the count of live discretionary compartments, moving only on an explicit user-originated lifecycle event and never on utilization, queue depth, or any compartment's computation.
· Accept: what is given up is the *rarity*, not the *non-reactivity*, and the residual channel that buys is booked in §17.
· Trace: CJ-NI · [§11](verification-maximal-os.md#r-11-025)

**R-11-026** MUST: (7) The top rung is a hard ceiling: past it a new compartment receives no slot rather than a thinner one, and the owning population manager suspends a live compartment to retained state to make room.
· Accept: suspension keeps state and removes a slot; it is not termination, and it is the mechanism, not a heuristic.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-026)

**R-11-027** MUST: Tasks using vector or matrix instructions carry those units' bounded worst-case latencies into the WCET inputs, and eager vector/matrix zeroize costs enter the partition-switch terms (zeroize only: the switch saves nothing, R-07-014a, and a slot-spanning task's own sink is in-slot WCET, R-07-014b).
· Accept: the enabling properties are deterministic dataflow, in-order non-speculative issue, statically-predicted control flow, schedule-fixed frequency, and the fixed-latency divide/FPU/AMO mandates.
· Trace: CJ-WCET · [§11](verification-maximal-os.md#r-11-027)

---

## §12. System Servers

### 12.1 Server structure

**R-12-001** MUST: Each server is its own compartment with its own capability manifest, crash-only design, and supervised restart.
· Accept: no server shares a compartment with another.
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-001)

**R-12-002** MUST: Server logic splits by plane: the data plane (bulk I/O, ring processing, vector/matrix math, wire parsing) is `#![forbid(unsafe_code)]` safe Rust; the control plane (sequencing, supervision, protocol state machines, mode/timing control) is Lustre compiled by Vélus.
· Accept: any `unsafe` is confined to the verified HAL and never inlined into server logic.
· Trace: CJ-VELUS, CJ-HAL · [§12](verification-maximal-os.md#r-12-002)

**R-12-003** IS: The plane split names default languages, not a mandate: a server may instead be a formally-verified non-Rust lift, memory-safe at the binary level like any contained binary, its own verification bonus assurance.
· Accept: consistent with R-05-009.
· Trace: CJ-TAL-SOUND · [§12](verification-maximal-os.md#r-12-003)

**R-12-004** IS: Every function on the machine falls into one of four classes: software on cores (TCB), software on cores (non-TCB), matter, and excluded foreign computers; the class table is exhaustive.
· Accept: the matter tier is driven through capability-checked MMIO/DMA and carries no instruction fetch and no firmware; every function a conventional platform would delegate to a firmware-running coprocessor is dissolved, reduced, or banned.
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-004)

### 12.2 The ring data plane

**R-12-005** MUST: All bulk I/O rides bounded SPSC shared-memory rings with notification wakeups; the peer is a server, never the kernel, so a ring bug costs one compartment.
· Accept: no bulk-data path traverses the kernel (R-07-029).
· Trace: CJ-KERNEL · [§12](verification-maximal-os.md#r-12-005)

**R-12-006** MUST: Descriptors name only indices into a per-session table of pre-delegated capabilities, plus offset and length: no paths and no ambient references, with new authority arriving via control-plane IPC only.
· Accept: no descriptor field is dereferenceable as an address.
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-006)

**R-12-007** MUST: Ring pages are mapped without capability-store permission, so authority physically cannot cross the data plane.
· Accept: rings carry indices, never capabilities (R-15-026).
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-007)

**R-12-008** MUST: Both sides parse with verified copy-once parsers, using one canonical verified ring library proven against a Byzantine peer under Ztso with no fence in the ring algorithm, and, for rings crossing islands, proven over the shared SRAM window they occupy.
· Accept: release publication uses load→store and store→store ordering, acquire consumption uses load→load and load→store ordering, and Ztso supplies all four; the algorithm contains no store→later-load edge, and R-15-015a preserves the four supplied edges across the shared window.
· Trace: CJ-FORMAT, CJ-SAIL · [§12](verification-maximal-os.md#r-12-008)

**R-12-008a** MUST: Every ring payload slot follows a CHERI-TAL-checked ownership transition: producer-exclusive writable; release-published and producer-inaccessible; consumer-acquired immutable; completed and returned to producer ownership. Only head, tail, and notification cells are concurrently shared, and they are explicitly atomic types.
· Accept: the canonical ring proof rejects any path that reads a slot before acquire, writes it after publication, or restores producer write ownership before every consumer reader is consumed; the Byzantine-peer theorem assumes no protocol compliance beyond admission of the typed binary.
· Trace: CJ-TAL-SOUND, CJ-SAIL, CJ-FORMAT · [§12](verification-maximal-os.md#r-12-008a)

**R-12-009** IS: Service is metered on the session's schedule slot; zero-copy is a delegated memory capability the DMA engine presents and the fabric checks, torn down with the session.
· Accept: cross-service linked ops and any credential or personality registration are absent by design.
· Trace: CJ-WCET, CJ-CERISE · [§12](verification-maximal-os.md#r-12-009)

### 12.3 The interface layer

**R-12-010** MUST: All server protocols and capability manifests are expressed in one typed IDL profile, fork-and-frozen: resources map to capabilities, worlds map to manifests, and marshalling, the verified parsers, and Coq interface skeletons are all generated from the same types.
· Accept: the admission checker verifies each Tier-1 proof is stated against the matching skeleton.
· Trace: CJ-IDL · [§12](verification-maximal-os.md#r-12-010)

**R-12-011** MUST: Flow annotations are a first-class IDL concern for every cross-domain channel: each type carries confidentiality and integrity labels, the IDL-to-Coq generator emits the matching flow predicates, and Tier-1 proofs for cross-domain servers must include flow theorems against them.
· Accept: the labeling is what defines *secret-labeled material* for IDL-borne material, and is one source of the label rather than the definition of the population: R-05-074 scopes the constant-time obligation by the label however the material was obtained, so DMA-window, re-delegated-front-end, and locally-drawn secrets carry it without an IDL channel.
· Trace: CJ-IDL, CJ-NI · [§12](verification-maximal-os.md#r-12-011)

**R-12-012** MUST: The IDL profile is restricted: closed variants only, no recursion, and explicit bounds on every list and string.
· Accept: no IDL type admits an unbounded value (R-05-143).
· Trace: CJ-IDL · [§12](verification-maximal-os.md#r-12-012)

**R-12-013** IS: Two standing rules govern the IDL: its types are documentation of the contract and never the contract, enforcement remaining kernel capabilities plus CHERI plus the Coq specs; and the profile's wire-format mapping is itself a crown-jewel specification.
· Accept: the kernel is not an IDL endpoint.
· Trace: CJ-IDL · [§12](verification-maximal-os.md#r-12-013)

**R-12-013a** MUST: Object references, intents, and transformations use the existing IDL: an object is an out-of-band capability plus typed metadata identity, an intent is a closed variant rather than an executable name or command string, and a transformation declares bounded input/output types, resource limits, and its interface world.
· Accept: no desktop-specific wire protocol, open-ended intent string, or authority-bearing path is introduced.
· Trace: CJ-IDL · [§12](verification-maximal-os.md#r-12-013a)

### 12.4 Sealing, attestation, and credentials

**R-12-014** MUST: The sealing and attestation service is a crypto-core-backed compartment exposing seal/unseal, attestation quotes, reference-manifest retrieval, and monotonic-counter operations over rings, binding secrets to the RoT and measured state.
· Accept: keys never leave the crypto core; apps hold only sealed blobs and capability handles, so the constant-time obligation stays on the core.
· Trace: CJ-CRYPTO-SPEC, CJ-CT-SOUND · [§12](verification-maximal-os.md#r-12-014)

**R-12-015** MUST: A relying party retrieves the running generation's reference integrity manifest through the same service and appraises a quote against it, so remote verification needs no vendor-side golden database.
· Accept: the reference set is reproducible from source.
· Trace: CJ-DEVTREE · [§12](verification-maximal-os.md#r-12-015)

**R-12-015a** MUST: The sealing service is the sole broker of *protocol* credentials, distinct from the user-authenticating credential and unlock service (R-12-016), and returns only non-exportable credential capabilities bound to a typed protocol role, principal, peer/origin scope, permitted operation, transcript/domain separator, use count, and expiry.
· Accept: raw key export and unconstrained sign, decrypt, or derive operations are absent; each operation is a schema-bounded IDL request returning only the protocol result.
· Trace: CJ-CRYPTO-SPEC, CJ-CT-SOUND, CJ-IDL · [§12](verification-maximal-os.md#r-12-015a)

**R-12-015b** MUST: Credential delegation is monotone attenuation and any operation requiring fresh user approval uses the powerbox and trusted consent path rather than a client-rendered prompt.
· Accept: a client or delegated credential holder can neither widen protocol/scope/operation bounds nor manufacture approval.
· Trace: CJ-NI, CJ-CERISE, CJ-CRYPTO-SPEC · [§12](verification-maximal-os.md#r-12-015b)

**R-12-016** MUST: The credential and unlock service gates the Before-First-Unlock → After-First-Unlock transition: it matches the primary credential and runs biometric matching, with the biometric sensor a register slave streaming raw samples over a capability-bounded DMA interface block and the matcher ordinary contained safe Rust in its own sub-manifest.
· Accept: a correct match authorizes the crypto core and RoT to derive and hold the per-profile volume key.
· Trace: CJ-CRYPTO-SPEC, CJ-DEVTREE · [§12](verification-maximal-os.md#r-12-016)

**R-12-017** MUST: Attempt rate-limiting and a monotonic attempt counter are RoT duties, so a stolen device cannot brute-force the credential offline.
· RoT-fresh: the credential attempt-counter version (R-10-013), advancing on authentication attempts.
· Trace: CJ-DEVTREE · [§12](verification-maximal-os.md#r-12-017)

**R-12-018** MUST: The same compartment recognizes a distinct duress credential that, on match, commands an RoT crypto-erase instead of an unlock, indistinguishable from a normal attempt until it completes.
· Accept: the duress path is a match outcome, not a separate interface.
· Trace: CJ-CRYPTO-SPEC · [§12](verification-maximal-os.md#r-12-018)

**R-12-019** MUST: Biometric authority is a secondary factor only: it unlocks a live After-First-Unlock session but never releases keys from a cold or idle-locked Before-First-Unlock device, which always requires the primary credential.
· Accept: a spoofed or coerced biometric cannot substitute for the at-rest key-release root.
· Trace: CJ-CRYPTO-SPEC · [§12](verification-maximal-os.md#r-12-019)

**R-12-020** IS: The on-die path (this compartment, the crypto core, the RoT) is the platform's own authenticator; an external roaming hardware security key is declined as a foreign computer, at the cost of cross-device credential portability.
· Accept: the cost is booked rather than omitted.
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-020)

**R-12-021** IS: The rollback-manager service is a contained non-TCB compartment presenting the signed generation history and structured diffs; it drives but does not constitute the trusted rollback path.
· Accept: a below-floor or unsigned target is refused however the UI is compromised (R-06-022).
· Trace: CJ-DEVTREE · [§12](verification-maximal-os.md#r-12-021)

**R-12-022** MUST: Authorizing a rollback is a security action: it is gated by the credential/unlock service and witnessed through the trusted consent path, so no app can enact a rollback without unspoofable user consent.
· Accept: it rolls the system generation only; a user-data subvolume restore is a separate, clearly-labeled non-TCB operation carrying that path's surrendered-freshness caveat.
· Trace: CJ-NI, CJ-DEVTREE · [§12](verification-maximal-os.md#r-12-022)

### 12.5 Storage servers

**R-12-023** IS: The filesystem is the §10 four-layer verified stack, verified but wholly non-TCB and contained like any server, serving both the system-image and user-data subvolumes.
· Accept: a filesystem fault costs availability or a caught corruption, never a silent integrity breach.
· Trace: CJ-DEVTREE · [§12](verification-maximal-os.md#r-12-023)

**R-12-024** IS: Below the §10 integrity line the availability-only block services are ordinary `#![forbid(unsafe_code)]` Rust Tier-1 compartments; a bug or compromise costs availability, never integrity or confidentiality.
· Accept: the AEAD/Merkle-DAG layer catches corruption.
· Trace: CJ-CRYPTO-SPEC · [§12](verification-maximal-os.md#r-12-024)

**R-12-025** MUST: Raw NAND is exposed through a firmware-free on-die flash-interface block (ONFI PHY plus a fixed-function ECC engine), with the FTL a host-side Tier-1 server doing wear levelling, mapping, and garbage collection in safe Rust, trusted for availability only.
· Accept: SSD-controller firmware is deleted; NVMe/eMMC devices with vendor firmware are not on the allowlist.
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-025)

**R-12-026** MUST: Nonvolatile storage carries a soft-decision LDPC per-page code dimensioned for the worst-case cell type at end-of-retention, end-of-endurance bit-error rate, decoded with read-retry across multiple reference voltages.
· Accept: the correction margin is largest where the raw error rate is highest.
· Trace: CJ-SAIL · [§12](verification-maximal-os.md#r-12-026)

**R-12-027** MUST: Above the per-page code sits a die- and plane-level parity layer (RAISE/chipkill-class) so a whole failed die, plane, or block is reconstructed rather than merely detected.
· Accept: this is the nonvolatile counterpart of the volatile tier's whole-device ECC coverage.
· Trace: CJ-SAIL · [§12](verification-maximal-os.md#r-12-027)

**R-12-028** IS: The asymmetry is deliberate: storage keeps a full integrity-and-rollback story because persistent media leave the die and survive power-down, whereas volatile main memory keeps none because it does neither.
· Accept: consistent with R-15-199.
· Trace: CJ-T · [§12](verification-maximal-os.md#r-12-028)

**R-12-029** MUST: Retention and read-disturb are scrubbed, not tolerated: the availability-layer FTL runs background patrol reads informed by the ECC engine's soft-decision telemetry and rewrites any page whose error rate drifts toward the correction limit before it crosses it.
· Accept: the nonvolatile analog of SRAM scrubbing (R-15-177).
· Trace: CJ-SAIL · [§12](verification-maximal-os.md#r-12-029)

**R-12-030** MUST: All of this stays fixed-function hardware and safe-Rust management, never controller firmware, and the device ECC composes with rather than replaces the §10 integrity layer above it.
· Accept: a NAND failure is always a caught corruption or an availability event, never a silent integrity breach; corrected-error rates and uncorrectable events feed the sentinel.
· Trace: CJ-CERISE, CJ-CRYPTO-SPEC · [§12](verification-maximal-os.md#r-12-030)

### 12.6 The object fabric

**R-12-024a** IS: The object fabric is a contained non-TCB control plane over the existing filesystem, object store, IDL, and rings: the caller delegates its manifest-derived namespace capability for the duration of a session, and the service queries and resolves under that capability alone, returning object capabilities derived from it plus commit-ordered query deltas.
· Accept: no VFS, registry, metadata database, or launcher is added; the service holds no standing cross-caller namespace authority, each delegation ending with its session at the revocation epoch; and compromise costs correct routing or availability rather than authority confinement.
· Trace: CJ-NI, CJ-CERISE, CJ-IDL · [§12](verification-maximal-os.md#r-12-024a)

**R-12-024b** MUST: The handler and translator graph is a finite signed composition-time object compiled from installed packages' interface descriptors and rebuilt and re-signed with the generation an install composes (R-13-001a), never amended in a running one, with deterministic typed routing and no runtime registration, executable lookup, shell command, plugin load, or content sniffing.
· Accept: the graph is a typed signed configuration object carried by the generation root and admitted on the ordinary install path (R-13-001, R-13-002), and an intent naming no admitted edge fails closed.
· Trace: CJ-IDL, CJ-DEVTREE, CJ-NI · [§12](verification-maximal-os.md#r-12-024b)

**R-12-024c** MUST: One-shot translation and streaming media use the same static typed graph: streaming binds a composition-time template from pre-composed node and bounded-ring pools, with every node's WCET, memory, labels, and device reservation admitted under §11 before it may be bound, at release time for base-image nodes and at install time for package-supplied ones.
· Accept: runtime binding creates no code, compartment, edge type, or unbounded queue; outputs enter the caller's confidentiality domain as ordinary §10 typed objects in one metadata/index transaction.
· Trace: CJ-WCET, CJ-NI, CJ-IDL, CJ-T · [§12](verification-maximal-os.md#r-12-024c)

**R-12-024d** MUST: Deterministic translation reuse is confined to one confidentiality domain and keyed by the input's content address (the per-domain keyed digest for user data), admitted translator package identity and version, declared parameters, and output content type.
· Accept: mutable input identity, undeclared process state, filename, and caller-controlled handler naming affect neither the result nor cache selection; no cache key is a cross-domain content hash, so probing reveals nothing across domains.
· Trace: CJ-NI, CJ-T · [§12](verification-maximal-os.md#r-12-024d)

**R-12-024e** MUST: Routing has two distinct faces and mints nothing: *resolution* derives object capabilities only from the namespace capability the caller delegated for that session, and *handoff* passes the selected handler only that object capability plus caller-supplied local buffer capabilities, attenuated to the selected edge's declared bounds.
· Accept: a compromised router cannot reach a namespace no live session delegated to it, read an object it holds no read capability for, or launch a handler with authority absent from that handler's manifest.
· Trace: CJ-NI, CJ-CERISE · [§12](verification-maximal-os.md#r-12-024e)

**R-12-024f** MUST: Every content format a translator or media node parses is attacker-facing wire: it carries a §5 Narcissus copy-once verified parser and is enumerated in the wire-format inventory.
· Accept: the image, media, font, archive, and document formats the graph admits appear in the R-05-042 inventory on the same terms as the radio and USB grammars.
· Trace: CJ-FORMAT · [§12](verification-maximal-os.md#r-12-024f)

### 12.7 Network

**R-12-031** IS: The network is an IPv6-only single stack with verified parsers at every boundary, TLS 1.3 with hybrid PQ key exchange, WireGuard-style tunnels, DNS-over-TLS in its own compartment, and Roughtime-authenticated time.
· Accept: each compartment's attacker-facing wire parsing is held to the Narcissus discipline and its memory safety to the binary-level certificate.
· Trace: CJ-FORMAT, CJ-TAL-SOUND · [§12](verification-maximal-os.md#r-12-031)

**R-12-032** IS: For TLS 1.3 the trust-base-uniform target is a Rust-native hax-verified TLS in the Bertie lineage, with miTLS the more mature F\*/Z3 option; either way the protocol proof is *bonus* over the memory-safety floor and never trust base, and the crypto binds to the §5 verified core.
· Accept: no protocol proof enters the trust base (R-05-010, R-05-078).
· Trace: CJ-REDUCTION · [§12](verification-maximal-os.md#r-12-032)

**R-12-033** MUST: Where no Coq-native verified peer exists, mature verified artifacts in other provers serve as differential-test oracles that enter no trust base: IRONSIDES for the resolver, and SPARK-verified TCP with Huginn-TCP conformance for smoltcp.
· Accept: the oracle pattern matches R-05-051.
· Trace: CJ-FORMAT · [§12](verification-maximal-os.md#r-12-033)

**R-12-034** MUST: The NIC is reachable only by capability and its DMA is capability-checked by the fabric; the NIC itself is dissolved, with no Ethernet controller firmware and no PHY-management processor.
· Accept: only the line front end, the frozen-coefficient 1000BASE-T datapath, and the 1588 timestamp unit remain fixed-function matter (R-15-135).
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-034)

**R-12-035** MUST: Time synchronization is one capability-scoped service disciplining the wall-clock from three scope-graded sources (Roughtime, NTS, and secure PTP), cross-checking them so a lying or stalled source is caught by disagreement.
· Accept: time is handed to apps as a capability, coarse by default and high-precision only where the clock-read-out rule grants it.
· Trace: CJ-NI · [§12](verification-maximal-os.md#r-12-035)

**R-12-036** IS: The precision substrate is a fixed-function IEEE-1588 hardware timestamp unit and adjustable clock at the NIC, deterministic and firmware-free; the scheduler's monotonic `mtime` stays a separate free-running counter.
· Accept: the software servo computes offset without interrupt jitter.
· Trace: CJ-WCET · [§12](verification-maximal-os.md#r-12-036)

**R-12-037** MUST: Secure PTP runs in the most defensive profile the standard allows: the authentication TLV on every message, its key established through the platform's own NTS key establishment rather than manual pre-shared secrets, time-receiver-only, accepting no management or reconfiguration messages, and its framing held to the Narcissus discipline.
· Accept: no verified PTP peer exists, so it rides parser-plus-crypto discipline alone; the residual delay and path-asymmetry surface is booked in §17.
· Trace: CJ-FORMAT, CJ-CRYPTO-SPEC · [§12](verification-maximal-os.md#r-12-037)

### 12.8 Radio stack

**R-12-038** MUST: The radio is software-defined as ordinary contained compartments with no baseband processor anywhere: PHY servers run statically pinned on the radio V-class cores with the FEC units, and HARQ/subframe deadlines are §11-admitted hard tasks.
· Accept: cellular and Wi-Fi PHYs are separate compartments; GNSS (receive-only) is a third.
· Trace: CJ-CERISE, CJ-WCET · [§12](verification-maximal-os.md#r-12-038)

**R-12-039** MUST: Everything with protocol semantics stays in software: connection-event and slot scheduling, channel selection, framing/whitening/CRC, link-layer encryption via the crypto core, and the link-layer state machine as a Lustre control plane.
· Accept: only the turnaround timing is fixed-function (R-15-122).
· Trace: CJ-VELUS · [§12](verification-maximal-os.md#r-12-039)

**R-12-040** MUST: L2/L3 servers (MAC/RLC/PDCP/RRC/NAS; 802.11 MLME; BT L2CAP/GATT) are Tier-1 compartments behind verified ASN.1 UPER/PER and MLME element parsers.
· Accept: the zero-click baseband class lands in a verified parser inside a compartment instead of a proprietary RTOS with DMA.
· Trace: CJ-FORMAT · [§12](verification-maximal-os.md#r-12-040)

**R-12-041** MUST: The cellular stack implements only NR RRC and 5G-core NAS and their 6G successors: no 2G/3G/4G protocol state machine exists in it, so legacy attach, fallback, and silent downgrade are unexpressible rather than merely refused.
· Accept: the software floor matches the hardware generation floor (R-15-129).
· Trace: CJ-FORMAT · [§12](verification-maximal-os.md#r-12-041)

**R-12-042** MUST: Within 5G/6G a null or broken cipher is rejected and mutual authentication (5G-AKA) is required, so *no downgrade, no null cipher, mutual authentication* is a verified property of the L2/L3 servers for all non-emergency service, not a user toggle.
· Accept: emergency calling is a separate mode, not an exception carved into this property.
· Trace: CJ-CRYPTO-SPEC · [§12](verification-maximal-os.md#r-12-042)

**R-12-043** MUST: The data/control split runs through the radio stack: the wire parsers are the data plane and the protocol state machines (RRC/NAS/RLC sequencing, MLME, L2CAP/GATT and their T3xx-class timers) are Lustre control planes compiled by Vélus.
· Accept: causality and per-reaction WCET are structural on the most-attacked remote surface; flow theorems govern what crosses from radio to platform.
· Trace: CJ-VELUS, CJ-NI · [§12](verification-maximal-os.md#r-12-043)

**R-12-043a** MUST: Each admitted protocol has exactly one admissible configuration, fixed at composition: one ciphersuite, one protocol version, and no capability-driven fallback path.
· Accept: no control plane holds a variable whose value selects a cipher suite, protocol version, or feature set; an offered configuration other than the single admissible one terminates the association rather than selecting a second path, and the emergency mode (R-12-048) is a separate configuration entered by the local act R-12-049 requires rather than a negotiated fallback.
· Trace: CJ-VELUS · [§12](verification-maximal-os.md#r-12-043a)

**R-12-043b** MUST: Each named protocol control plane's sequencer is proved to refine a formal reference model of the standard's own state machine: NR RRC and 5G NAS including 5G-AKA, the 802.11 MLME including the WPA3/SAE handshake, and BT L2CAP/GATT pairing.
· Accept: one machine-checked refinement theorem per named control plane, stated over the Lustre node set R-05-052 mandates and against the reference model as its specification; a state, transition, or timer the model does not carry is unreachable in the sequencer rather than merely untested, and a control plane carrying no such theorem is a review-gate finding.
· Trace: CJ-VELUS · [§12](verification-maximal-os.md#r-12-043b)

**R-12-043c** MUST: Each protocol's reference state machine is a crown-jewel spec, conferred per protocol rather than per stack and enumerated individually in the crown-jewel inventory.
· Accept: the inventory carries one row per reference model, each subject to the R-05-150 independent specification review; a refinement claimed under R-12-043b against a model absent from the inventory is a review-gate finding.
· Trace: CJ-VELUS · [§12](verification-maximal-os.md#r-12-043c)

**R-12-043d** IS: R-12-043b claims conformance to the reference model, not security of the protocol: the model's faithfulness to the published standard is unverifiable, and the composed session security of the standard itself remains the residual R-03-004 enumerates.
· Accept: no requirement cites R-12-043b for a session-security property; the §17 protocol-composition residual is narrowed on its implementation half and is otherwise unchanged.
· Trace: CJ-VELUS · [§12](verification-maximal-os.md#r-12-043d)

**R-12-044** MUST: Cellular and Wi-Fi session keys live in crypto-core-backed compartments; the air-interface stack sees only the handles it needs.
· Accept: no session key is resident in an air-interface compartment.
· Trace: CJ-CRYPTO-SPEC · [§12](verification-maximal-os.md#r-12-044)

**R-12-045** IS: The eUICC is the one tolerated foreign computer, contained as a register-slave crypto oracle for network authentication with zero platform authority: no DMA, no interrupt beyond its mailbox, nothing to grant.
· Accept: its compromise costs cellular authentication and nothing else.
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-045)

**R-12-046** MUST: The eUICC's physical interface is a fixed-function ISO7816 interface block: host-generated card clock divided from the platform clock, bit-level framing and parity in hardware, a small bounded FIFO, and a mailbox MSI on completion, a block that moves bytes and interprets nothing.
· Accept: no DMA and no APDU semantics exist in silicon.
· Trace: CJ-SAIL · [§12](verification-maximal-os.md#r-12-046)

**R-12-047** MUST: APDU/TPDU traffic is parsed only in software by a Narcissus-derived verified copy-once reader in the AKA client compartment.
· Accept: the one tolerated foreign computer speaks to the platform only through a verified parser inside a zero-authority compartment.
· Trace: CJ-FORMAT · [§12](verification-maximal-os.md#r-12-047)

### 12.9 Emergency calling

**R-12-048** IS: Emergency service runs in a zero-authority emergency compartment holding no volume keys, no user data, and no persistent identity beyond the regulation-mandated IMEI and location, so its unauthenticated bearer can carry only what regulation already compels the device to disclose.
· Accept: the *no downgrade, no null cipher, mutual authentication* property is scoped to non-emergency service, and emergency calling is a distinct, separately-verified mode rather than a relaxation of it.
· Trace: CJ-NI · [§12](verification-maximal-os.md#r-12-048)

**R-12-049** MUST: Entry is an unspoofable, deliberate local act (the user placing the call over the trusted consent path, or a regulatory trigger) and never network-initiated, RoT-attested and surfaced through the secure-attention indicator.
· Accept: a rogue base station cannot bid the device into an unauthenticated emergency mode to strip its crypto.
· Trace: CJ-NI, CJ-DEVTREE · [§12](verification-maximal-os.md#r-12-049)

**R-12-050** IS: Because emergency registration attaches on the IMEI with no subscription secret, the mode needs no eUICC and works identically at Before First Unlock, after a duress crypto-erase, or with no eUICC provisioned; on call end the compartment is torn down and eager-zeroized.
· Accept: no state carries into normal operation; the 5G/6G coverage limit is booked in §15 and §17.
· Fail-closed: emergency service exists only inside 5G-SA or 6G coverage (R-17-030g); outside it the cost is the call itself.
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-050)

**R-12-051** MUST: The microphone reaches the emergency compartment by the ordinary rule, not an exception: the same unspoofable local act is the consent act on which the powerbox mints a microphone capability bounded to that compartment alone.
· Accept: no new minter and no ambient authority; the lock-state cut revokes grants and a peripheral no live grant holds falls dark (R-15-147).
· Trace: CJ-NI, CJ-CERISE · [§12](verification-maximal-os.md#r-12-051)

**R-12-052** IS: That grant is deliberately exempt from the while-active ceiling, its bound being the call's own lifetime, which teardown enforces.
· Accept: this is a stated exception to R-08-040 and the only one; the ceiling exists to force re-affirmation, and interrupting an emergency call to re-prompt would turn a safety mechanism into a hazard.
· Trace: CJ-NI · [§12](verification-maximal-os.md#r-12-052)

**R-12-053** MUST: The mode cannot serve as a covert microphone: entry lights the secure-attention indicator and a live grant drives the peripheral's hardware enable and in-use indication, so the microphone is never live without both being visible.
· Accept: both signals are RoT-driven.
· Trace: CJ-DEVTREE · [§12](verification-maximal-os.md#r-12-053)

**R-12-054** MUST: The sealed physical cutoffs still dominate and are not overridden: a thrown microphone switch yields a connected but mute emergency call, and a thrown radio switch yields none at all.
· Accept: a software path able to re-enable a sealed cutoff for emergencies is a software path able to re-enable it; the direction is booked in §17.
· Fail-closed: a thrown cutoff is not overridden, emergency calling included (R-17-030f); the cost is the sensor or radio the user sealed.
· Trace: CJ-T · [§12](verification-maximal-os.md#r-12-054)

### 12.10 Regulatory layering

**R-12-055** MUST: Compliance is enforced primarily by passive matter in three layers: the passive analog envelope (band-limited PA, fixed filters, fixed-gain final stage, narrowband antenna), OTP/RoT-latched limit registers, and the attested frozen radio generation.
· Accept: multi-band is a switched bank of pre-certified fixed paths, so every reachable RF configuration is one that passed certification; a fully compromised radio stack cannot exceed the envelope.
· Trace: CJ-DEVTREE · [§12](verification-maximal-os.md#r-12-055)

**R-12-056** IS: The design rule is that the emission envelope is physically or OTP-immutable while the protocol stack stays patchable per generation, behaviour changes going through delta re-certification.
· Accept: a fully fused radio could never patch its most-attacked surface.
· Trace: CJ-DEVTREE · [§12](verification-maximal-os.md#r-12-056)

### 12.11 Drivers, USB, and input

**R-12-057** MUST: There is one compartment per device; register and DMA access go through the verified HAL primitives, so driver logic is fully safe Rust, device registers reached through a typed register interface that is the safe-Rust face of the same register-description-language layout the HAL is generated and verified against.
· Accept: driver code never open-codes a shift or mask; DMA is only through explicit capability grants the fabric checks; drivers are restartable without reboot.
· Trace: CJ-HAL · [§12](verification-maximal-os.md#r-12-057)

**R-12-058** MUST: USB is fully in userland with per-device authorization, and the USB data path is gated on the attested lock state: a Before-First-Unlock or idle-locked device is charging-only, its DMA window unopened and any new-peripheral authorization deferred to post-unlock powerbox consent.
· Accept: juice-jacking and lock-screen wired extraction have no data path; the charging path stays live through the fixed-function power-delivery sequencer.
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-058)

**R-12-059** MUST: A user may force charging-only directly and independently of lock state through a physical restricted-mode control driving the fixed-function data-lane mux.
· Accept: because the cut is at the mux, the attacker device never reaches the USB stack's enumeration and descriptor-parse path (R-15-151).
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-059)

**R-12-060** IS: USB is profiled by capability, not specification version, on two rules that do not turn on which generation a port negotiates.
· Accept: a newer physical layer and FEC are admitted freely where throughput warrants, and lower-generation devices stay supported as data devices on the same terms.
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-060), [§12](verification-maximal-os.md#r-12-060-2)

**R-12-061** MUST: The floor is cryptographic device and cable authentication before a data role is granted, re-grounded on ML-DSA identities rather than the stock profile's ECDSA and carried by Narcissus-checked parsers; an unauthenticated device is held charging-only exactly as a locked one is.
· Accept: the DMA window stays unopened until a post-unlock powerbox consent admits it.
· Trace: CJ-CRYPTO-SPEC, CJ-FORMAT · [§12](verification-maximal-os.md#r-12-061)

**R-12-062** MUST NOT: The ceiling is no tunneling: the USB4 fabric's PCIe, DisplayPort, and USB tunnels, its connection manager, its Thunderbolt alternate mode, and its general vendor-defined-message extensions are declined together.
· Accept: no foreign PCIe topology, no DMA-over-USB endpoint, and no tunneling-protocol grammar is ever admitted; the one admitted alternate mode is output-only DisplayPort (R-15-233).
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-062)

**R-12-063** MUST: An external input device attaches as a USB HID-class device through the verified userland USB stack under per-device authorization, its report descriptor parsed copy-once by Narcissus.
· Accept: a HID-injection or BadUSB device is confined by that authorization plus capability containment rather than trusted as an ambient input path.
· Trace: CJ-FORMAT · [§12](verification-maximal-os.md#r-12-063)

**R-12-064** MUST NOT: There is no legacy input controller (no PS/2, i8042) and no legacy interrupt controller (no wired IRQ line, 8259-PIC, or ambient PLIC routing); all device servicing is time-triggered polling of latched pending bits in scheduled slots.
· Accept: the ambient device-interrupt interface is absent twice over: no routing surface, and no delivery path for one to route into.
· Trace: CJ-KERNEL · [§12](verification-maximal-os.md#r-12-064)

**R-12-065** MUST: Embedded-controller functions are dissolved: power sequencing and reset are RoT duties, battery gauging is on-die coulomb-counting read by a contained server, thermal sensing feeds the sentinel, and keyboard and touch are register-slave scan interfaces behind ordinary drivers.
· Accept: pure-analog pack protection remains off-die as non-programmable hardware; there is no EC firmware because there is no EC.
· Trace: CJ-DEVTREE · [§12](verification-maximal-os.md#r-12-065)

**R-12-066** MUST: USB-PD contract negotiation is a fixed-function bounded state machine over the CC-line messages, with negotiated voltage and current bounded by analog pack protection (primary) and RoT-latched PD limit registers (secondary).
· Accept: no bus and no arbitrary negotiation rides the power channel.
· Trace: CJ-DEVTREE · [§12](verification-maximal-os.md#r-12-066)

### 12.12 Sensors, camera, and the front-end doctrine

**R-12-067** MUST: Camera sensors are register slaves streaming raw Bayer over a capability-bounded DMA interface block, with the entire ISP pipeline (demosaic, 3A, tone mapping) software on V-class cores in the app's or camera server's compartment.
· Accept: no ISP firmware exists.
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-067)

**R-12-068** IS: The sensor front-end doctrine is one rule across the class: the analog front-end plus its scan, sample, or event sequencer is *matter*, while every stage carrying signal semantics is verified host software in the device's driver or server compartment.
· Accept: it applies uniformly to the radio transceiver, camera, fingerprint sensor, capacitive touch, the audio front-end, and IMU/motion sensors.
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-068)

**R-12-069** IS: The line is fixed-function versus programmable, not raw versus processed: an AFE may carry fixed-function analog and mixed-signal conditioning, which lowers sample rate and host DSP load, while the programmable, adaptive, policy-laden stage stays host software.
· Accept: because that conditioning is a fixed transfer function and not a writable state machine, it adds no programmable state to the Sail model: performance at no proof cost.
· Trace: CJ-SAIL · [§12](verification-maximal-os.md#r-12-069)

**R-12-070** IS: Readout may be event-driven rather than fixed-cadence, the comparator and the event pixel being matter, so the host DSP idles between events and only changes cross the boundary.
· Accept: event timing is data-dependent, and the no-timing-channel property is kept by confining event and wake traffic to the owning island's statically-partitioned NoC and memory budget.
· Trace: CJ-ISOL · [§12](verification-maximal-os.md#r-12-070)

**R-12-071** IS: On the confidentiality ledger the event-driven change is neutral-to-positive: the island partition restores the constant-from-outside property, and emitting only changes shrinks the exposed data, leaving a worst-case-bandwidth reservation as the sole residual, a power-margin cost, not a confidentiality one.
· Accept: an event-streaming DMA holds a bounded capability that honours the §8 revocation sweep like any other transfer.
· Trace: CJ-NI, CJ-CERISE · [§12](verification-maximal-os.md#r-12-071)

**R-12-072** IS: The raw-AFE silicon and its host-side DSP are a net-new co-design, and the continuous host-cycle and report-latency budget each consumes is a §11 scheduled task: the honest cost of dissolving the firmware the doctrine deletes.
· Accept: the §17 entry exists (R-15-142).
· Trace: CJ-WCET · [§12](verification-maximal-os.md#r-12-072)

### 12.13 Service manager

**R-12-073** MUST: The service manager is a static supervision tree with declarative units and no ambient authority, restarting with backoff and capability re-grant, realized as a synchronous Lustre state machine.
· Accept: its start-order, crash detection, restart-with-backoff, and capability re-grant have deterministic, bounded, hidden-state-free reactions by construction.
· Trace: CJ-VELUS · [§12](verification-maximal-os.md#r-12-073)

**R-12-074** MUST: Restart re-grant mints no new authority: it re-instantiates exactly the edges the capDL-class manifest already fixed, under the same initialisation-refinement obligation.
· Accept: the supervision tree is an authority re-instantiator, never a minter; the powerbox alone mints, and it alone joins the TCB.
· Trace: CJ-NI, CJ-KERNEL · [§12](verification-maximal-os.md#r-12-074)

### 12.14 Display, render, and the consent path

**R-12-075** MUST: Display and render use per-surface and per-input capabilities with no ambient observation of input or output, so keylogging and screen-scraping are unexpressible.
· Accept: capture requires per-window capabilities.
· Trace: CJ-NI, CJ-CERISE · [§12](verification-maximal-os.md#r-12-075)

**R-12-076** MUST: Consent for a powerbox grant is owned by a separate, small, verified trusted-path agent, not the compositor: it renders the consent surface into a region it holds by capability, is attested by an RoT-driven hardware secure-attention indicator the compositor cannot draw, and takes the response over the input front-end itself.
· Accept: the compositor can deny service, an availability fault, but cannot spoof a grant or capture a response.
· Fail-closed: a compositor or touch driver that fights the ownership transition reaches denial of the prompt (R-17-030i); the cost is the grant and never a forged one.
· Trace: CJ-NI, CJ-DEVTREE · [§12](verification-maximal-os.md#r-12-076)

**R-12-077** MUST NOT: The touch driver does not join the consent TCB: for the prompt's duration the touch front-end is re-delegated to the agent, its capability-bounded DMA window *and* its configuration MMIO leaving the driver together.
· Accept: front-end ownership is indivisible, because a driver holding the scan configuration could blind the agent, remap the scan so a touch outside the rendered button reads as inside it, or drive the gain so no press registers (R-15-143).
· Trace: CJ-DEVTREE · [§12](verification-maximal-os.md#r-12-077)

**R-12-078** MUST: The switch is RoT-latched and does not depend on the driver yielding: the front-end carries an ownership register latched by the RoT, unwritable by software while the latch holds, driven by the same RoT signal that lights the secure-attention indicator.
· Accept: the property is a hardware bi-implication (the indicator cannot be lit while the driver owns the front-end, and the agent cannot own the front-end without the indicator being lit) that the compositor, the driver, and a compromised kernel alike cannot separate.
· Trace: CJ-DEVTREE, CJ-NI · [§12](verification-maximal-os.md#r-12-078)

**R-12-079** MUST: What joins the consent TCB is a fixed threshold-and-centroid reduction over the region the agent rendered, with no adaptive state, its baseline snapshotted by the agent from its own first frames at prompt entry and held fixed.
· Accept: an externally-supplied baseline is refused as a security property, a chosen baseline being what turns an untouched panel into a press.
· Trace: CJ-NI · [§12](verification-maximal-os.md#r-12-079)

**R-12-080** IS: Two costs are accepted: touch is unavailable to applications while a prompt is up, and the driver's adaptive baseline goes stale across the prompt and re-converges on return.
· Accept: both are stated; the second is a latency artifact, not a correctness one.
· Trace: CJ-NI · [§12](verification-maximal-os.md#r-12-080)

**R-12-081** MUST: A consent response is accepted only from a front-end whose ownership the RoT can latch: the on-device register-slave front-ends qualify, and an external USB HID keyboard or pointer does not.
· Accept: a BadUSB or HID-injection device is not merely confined with respect to consent but unable to express a response; a prompt additionally requiring a credential is gated by the credential service over the fingerprint AFE on the same ownership terms.
· Trace: CJ-DEVTREE · [§12](verification-maximal-os.md#r-12-081)

**R-12-082** IS: Rendering is software on V-class cores: graphics acceleration is the general-purpose RVV datapath, so the render and compositor servers are the whole of the graphics driver.
· Accept: there is no GPU driver, no command-stream validator, and no shader-IR compiler in the display path.
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-082), [§12](verification-maximal-os.md#r-12-082-2)

**R-12-083** IS: The 2D and text substrate has safe-Rust start-froms, but there is no viable no-JIT software 3D, so the RVV software rasterizer for 3D is genuinely net-new engineering.
· Accept: llvmpipe JITs, which W^X forbids.
· Trace: CJ-TAL-SOUND · [§12](verification-maximal-os.md#r-12-083)

**R-12-084** IS: Surfaces are plain memory under CHERI; the only display device is the scanout controller, a firmware-free open-RTL DMA block behind a static capability-bounded DMA window over the framebuffer.
· Accept: consistent with R-15-229.
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-084)

### 12.15 Inference and telemetry

**R-12-085** IS: The inference server is an optional Tier-1 compartment exposing quantized-inference sessions over rings, with weights de-quantized and any microscaling block-scale applied in software on the M-class vector unit.
· Accept: models are content-addressed store objects; per-session memory is capability-delegated and zeroized on teardown.
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-085)

**R-12-085a** MUST: An autonomous agent is an ordinary contained compartment with a manifest, in no trusted set and holding no ambient authority: every capability it exercises arrives as a powerbox grant with an explicit temporal scope, witnessed on the trusted consent path.
· Accept: the agent's manifest confers no object, namespace, device, or network authority directly, and every such authority held in a live session traces to a recorded grant.
· Trace: CJ-NI · [§12](verification-maximal-os.md#r-12-085a)

**R-12-085b** MUST: An agent's tool surface is exactly the interfaces its manifest declares it may request, each answered by a live consent or a standing grant; model output is an untrusted proposal that reaches no object without a capability already granted for it.
· Accept: a tool call naming an interface absent from the manifest is refused before any consent prompt, and no code path derives authority from model output.
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-085b)

**R-12-085c** MUST: The agent's peer wire is the §12 typed IDL over a ring, started by the service manager and held to the §5 Narcissus discipline; there is no `fork`/`exec`, and running a command is a capability-delegated compartment.
· Accept: the wire appears in the §5 wire-format inventory, and no process-spawn primitive is reachable from an agent compartment.
· Trace: CJ-IDL, CJ-FORMAT · [§12](verification-maximal-os.md#r-12-085c)

**R-12-085d** IS: Inference is served either by the optional inference server or by a remote endpoint through the network compartment; the agent, not the model, is the principal that holds authority.
· Accept: no capability is held by, or delegated to, an inference session.
· Trace: CJ-CERISE · [§12](verification-maximal-os.md#r-12-085d)

**R-12-085e** MUST NOT: No agent compiles, certifies, or generates code on the device; an agent that edits source drives an off-device build-and-certify service, and the result re-enters through admission.
· Accept: the agent compartment holds no toolchain capability and no executable-memory authority, and every artifact it causes is admitted under §13 like any other.
· Trace: CJ-TAL-SOUND · [§12](verification-maximal-os.md#r-12-085e)

**R-12-086** MUST: The telemetry monitor is permanently resident on the dedicated S-class sentinel core, consuming the native sensor grid: CHERI validity-tag traps, slot-overrun faults, DMA capability-check denials, health heartbeats, ECC and NoC error telemetry, thermal sensors, and radio-limit-register violation traps.
· Accept: detection latency is a proved bound under any load, and responses (restart, revoke, roll back) run under the same guarantees.
· Trace: CJ-WCET, CJ-ISOL · [§12](verification-maximal-os.md#r-12-086)

---

## §13. Packaging & Supply Chain

### 13.1 The admitted artifact

**R-13-001** IS: A package is content plus its exact content-addressed source closure, a capability manifest, and a proof object; installation is proof check, store insertion, and capability wiring.
· Accept: source, generated inputs, dependency sources, configuration, and semantic-anchor version are hash-named in the closure; no other installation step exists.
· Trace: CJ-TAL-SOUND · [§13](verification-maximal-os.md#r-13-001)

**R-13-001a** MUST: An install is a generation, not an amendment to one: installing, removing, or reconfiguring a package composes a new signed generation over the resulting roster and commits it through the one A/B transactor (R-11-001, R-11-005), and that composition takes effect at the next boot. R-13-001's *capability wiring* is the construction of the new generation's initial distribution (R-07-019, R-13-006), never a mint into a running one, so R-04-008 and R-07-025 hold across the install path rather than carrying an exception for it.
· Accept: the install is therefore atomic, is an ordinary point in the signed diffable generation history (R-10-030), inherits health-gated auto-rollback so a package that wedges the boot is reverted with no user present (R-11-001), and takes the anti-rollback floor and the durable-state schema-migration rule already stated for a generation change (R-09-030, R-10-036) rather than a second set; no reachable state has some compartments running the old composition and some the new, and uninstalling is the same operation over a roster with the package removed rather than a distinct teardown path.
· Trace: CJ-DEVTREE, CJ-CERISE · [§13](verification-maximal-os.md#r-13-001a)

**R-13-001b** MUST NOT: There are no pre-proved empty compartment slots: no reservation is composed and admitted ahead of the content that would occupy it, and no package binds into one.
· Accept: such a reservation would have to carry banks in the per-mode occupancy map (R-08-012a, R-08-012e), a schedule slot with a WCET and a switch-duty ratio (R-11-006, R-11-009), a standing NoC reservation (R-11-008), and a share of the initial distribution (R-07-019), each sized for an occupant that does not exist yet, which is worst-case sizing plus a dynamic allocator wearing static syntax; and the whole-image dead and duplication passes read the composed roster (R-13-010a, R-13-010b), so an empty slot is precisely what they cannot see into. The composition-time template of R-12-024c is not this and survives unchanged: it binds nodes already composed and already admitted under §11, creating no compartment, no edge type, and no reservation.
· Trace: CJ-MEMPLAN, CJ-WCET · [§13](verification-maximal-os.md#r-13-001b)

**R-13-001c** MUST: The composer that turns a roster into a generation is an untrusted producer and is off-device with the rest of the certifying toolchain (R-13-010), because the whole-image passes emit new bytes and must emit the CHERI-TAL derivation and source-correspondence theorem covering them (R-13-010a, R-13-010b); the device names the roster it wants, fetches the objects it lacks (R-13-008), and admits the result through the ordinary checks (R-06-008, R-11-005).
· Accept: this is artifact-not-pedigree (R-13-013) applied to the composer, which accordingly joins no trust base and may be any party, the user's own machine included; a composer that gets the memory plan, schedule, wiring table, or handler graph wrong fails admission rather than shipping, which is R-17-033's completeness polarity arriving at composition rather than at a single artifact. What it costs is booked in R-17-035a.
· Trace: CJ-TAL-SOUND, CJ-DEVTREE · [§13](verification-maximal-os.md#r-13-001c)

**R-13-002** MUST NOT: There are no maintainer scripts, no post-install execution, and no runtime code fetching by system components.
· Accept: the installation path executes no package-supplied code.
· Trace: CJ-CERISE · [§13](verification-maximal-os.md#r-13-002)

**R-13-003** IS: The admitted artifact is a content-addressed capability image, not an ELF-style executable container: a set of content-addressed objects named by a small typed manifest: the immutable code-and-rodata image, a separate writable data-initializer, the exact source closure, the CHERI-TAL typing derivation and source-correspondence theorem, the capability-wiring table, and the capability manifest with its §12 interface descriptor.
· Accept: all parts are present; no interpreted, offset-linked container grammar is parsed on-device.
· Trace: CJ-TAL-SOUND, CJ-FORMAT · [§13](verification-maximal-os.md#r-13-003)

**R-13-004** MUST: Execute authority is wired only over the immutable code-and-rodata image, hash-verified against the signed root.
· Accept: no execute capability is derived over written memory.
· Trace: CJ-CERISE · [§13](verification-maximal-os.md#r-13-004)

**R-13-005** MUST: The writable data-initializer is a fresh allocation, eager-zeroized at its plan-assigned slots and *uninitialized* in the CHERI-TAL derivation until stored to, never conflated with the image.
· Accept: the definite-initialization attribute (R-05-119) governs it from its allocation point.
· Trace: CJ-MEMPLAN, CJ-TAL-SOUND · [§13](verification-maximal-os.md#r-13-005)

**R-13-006** IS: The capability-wiring table is the platform's relocation model: per capability slot, the source object, offset, bounds, and permission set, deriving monotonically from the initial distribution.
· Accept: no relocation entry constructs a capability (R-05-136).
· Trace: CJ-CERISE · [§13](verification-maximal-os.md#r-13-006)

**R-13-007** IS: The same objects live loose and deduplicated in the content-addressed store and serialize to one self-contained hash-indexed pack; a removable or portable image maps in place and executes from its hash-verified read-only region with no unpack step.
· Accept: single-file convenience and content addressing are the same objects in two containers, not a tradeoff.
· Trace: CJ-DEVTREE · [§13](verification-maximal-os.md#r-13-007)

**R-13-008** IS: Transfer between systems is a set difference: a content-aware copy or fetch writes and moves only the objects the destination lacks, each verified by hash on arrival, and the have/want exchange stays within a confidentiality domain.
· Accept: it is therefore not a cross-domain membership oracle, the transfer-time form of the §10 rule that dedup never crosses a domain.
· Trace: CJ-NI · [§13](verification-maximal-os.md#r-13-008)

**R-13-009** MUST: The on-device pack decoder is a Narcissus copy-once verified reader over a fixed-layout, schema-bounded format (header, flat hash-indexed object table, blob region) with every object independently hash-verified, so a corrupt index fails a hash check rather than driving a parser.
· Accept: the loader is never an attacker-facing grammar in the trust base; the format descriptor is a crown-jewel spec discharged by compiling it, not hand-writing it; and because every object here is named by its hash, the pack and manifest descriptors are identity-bearing in the sense of R-05-051c and carry the R-05-051a canonicity theorem, so an object has one encoding and its hash is an identity rather than one of several.
· Trace: CJ-FORMAT · [§13](verification-maximal-os.md#r-13-009)

**R-13-010** MUST NOT: ELF and any conventional executable container are off-device only: the certifying toolchain may emit ELF as build interchange, and package build transforms it into the pack at store-insertion time.
· Accept: the on-device loader is deleted rather than hardened.
· Trace: CJ-FORMAT · [§13](verification-maximal-os.md#r-13-010)

**R-13-010a** MUST: Package construction performs whole-image dead elimination before admission: from the frozen component graph, typed callee sets, manifest roots, interrupt and scheduled-entry roots, and capability-wiring table, existing LTO, section garbage collection, and linker stripping retain exactly the statically reachable closure and remove unreachable code, data, manifest entries, dispatch cases, and feature variants before hashing and signing.
· Accept: the source-correspondence theorem and CHERI-TAL derivation cover the stripped image itself; every retained object has a reachability root; and stripping changes no rooted symbol, capability edge, interface, or proof obligation.
· Trace: CJ-FORMAT, CJ-TAL-SOUND · [§13](verification-maximal-os.md#r-13-010a)

**R-13-010b** MUST: Package construction also performs whole-image **duplication** elimination over the reachable closure, available at a scale conventional systems cannot reach because whole-system static composition knows every compartment's closure at one time: identical-function merging across the composed roster, outlining and tail merging of recurring sequences, link-time specialization of call sites the frozen graph fixes, and one shared service compartment in place of a library statically linked into each consumer. Immutable code-and-rodata objects are mapped into multiple compartments through capabilities rather than copied, requiring no virtual memory and no coherence.
· Accept: authority is unchanged, each compartment still receiving only its declared sentry entries and a shared object conferring execute authority over the object and never over another holder's state; the source-correspondence theorem and CHERI-TAL derivation cover the **merged** image, and construction is rejected if a merge changes a rooted symbol, capability edge, interface, or proof obligation; the outlining and tail-merging half of this pass has its owner, its intra-compartment scope, its profitability rule, and its two-axis measurement at R-15-036o and R-15-036p.
· Trace: CJ-FORMAT, CJ-TAL-SOUND, CJ-MEMPLAN · [§13](verification-maximal-os.md#r-13-010b)

**R-13-010c** MUST NOT: Relocations, symbols, debug data, unwind metadata, and ELF-style container structure never occupy execution SRAM, and neither do source closures, derivations, or proof artifacts, which are resident in the authenticated store (§10) and consumed at admission rather than at run time.
· Accept: the resident image is code-and-rodata plus the capability-wiring table's product, nothing else; the largest single footprint reduction in R-13-010b is this removal rather than a merge.
· Trace: CJ-FORMAT, CJ-MEMPLAN · [§13](verification-maximal-os.md#r-13-010b)

**R-13-010d** MUST NOT: Link-time specialization may not specialize on a confidential value.
· Accept: the §15 dictionary encoding makes a specialized image's encoded length a function of what it was specialized on, so this is a scope condition of R-15-036g rather than a style preference; R-15-202's key containment and §13's admission rules already keep secrets out of images, and this states the consequence for the specialization pass.
· Trace: CJ-NI, CJ-LEAK · [§13](verification-maximal-os.md#r-13-010b)

**R-13-010e** IS: The duplication pass is **partly substitutive** with the §15 dictionary encoding rather than additive, each recurring sequence it removes also removing instances the dictionary would have covered.
· Accept: the two are measured composed and never multiplied, and this pass is ordered **first**, a dictionary selected against an unmerged image being selected against the wrong histogram (R-15-036i).
· Trace: CJ-MEMPLAN, CJ-FORMAT · [§13](verification-maximal-os.md#r-13-010b)

### 13.2 Assurance tiers

**R-13-011** IS: There are exactly three assurance tiers. **Tier 0** (TCB components): full functional refinement at binary level, robust preservation of compartment isolation, and the non-interference theorem over the full component graph, admitted by CIC proof terms mostly checked at release time. **Tier 1** (servers crossing confidentiality boundaries): binary-level policy proofs (memory/ABI conformance, handler termination, information-flow theorems from the IDL annotations, and constant-time for secret-labeled paths), admitted by CHERI-TAL taint typing where structured. **Tier 2** (apps and contained code): a mandatory binary-level memory-safety certificate, admitted by a typing derivation the on-device type-checker checks.
· Accept: every admitted artifact carries exactly one tier and its required evidence.
· Trace: CJ-TAL-SOUND, CJ-NI · [§13](verification-maximal-os.md#r-13-011)

**R-13-012** IS: The Tier-2 certificate carries the subset of R-05-029's eleven type-level obligations this tier requires (ABI/type well-formedness, no runtime codegen, temporal safety, definite initialization, data-race freedom, and CFI) plus manifest consistency, a tier-local admission check that is not one of the eleven. Full functional PCC is deliberately not required, because app intent is unspecified.
· Accept: admission is type-checking the artifact, not trusting the producer; and the certificate's content is read off R-05-029 with a stated tier scoping rather than enumerated independently, so a change to the canonical list has one place to be made.
· Trace: CJ-TAL-SOUND · [§13](verification-maximal-os.md#r-13-012)

**R-13-013** MUST NOT: There is no `#![forbid(unsafe_code)]` shortcut and no uncertified-admission path: Rust source discipline is one way to produce the Tier-2 derivation, and any producer of a well-typed binary is admitted identically.
· Accept: no admission rule reads a producer identity.
· Trace: CJ-TAL-SOUND · [§13](verification-maximal-os.md#r-13-013)

**R-13-014** IS: The hardware universal contract remains beneath every tier as defense in depth against a certifier or spec error, but it is a *refuse-uncertified-code* policy, not permission to run uncertified code.
· Accept: no admitted path runs code that failed a check.
· Trace: CJ-CERISE · [§13](verification-maximal-os.md#r-13-014)

**R-13-015** MUST NOT: The universal contract is deliberately not extended to initialization safety, because a hardware Write-before-Read plane would hedge the admission type-check itself.
· Accept: consistent with R-15-035 and R-05-119.
· Trace: CJ-CERISE · [§13](verification-maximal-os.md#r-13-015)

**R-13-016** MUST: The universal contract is stated over the CHERI-RISC-V Sail model, with Katamaran discharging the per-instruction separation-logic obligations between Isla and Islaris, and Cerisier extending the Cerise contract to attestation.
· Accept: capability safety plus local attestation is Coq-native prior art rather than an unmodeled seam.
· Trace: CJ-CERISE, CJ-SAIL · [§13](verification-maximal-os.md#r-13-016)

**R-13-017** IS: These are one Iris-over-Sail program logic with four theories, not five frameworks: unary safety, the Cerise/Cerisier universal contract, relational constant-time, and syntax-directed cost, all instantiating the same leakage- and cost-annotated Sail semantics, with StkTokens supplying the linear/affine stack discipline.
· Accept: the semantic-anchor budget counts one logic (R-05-019).
· Trace: CJ-SAIL, CJ-CT-SOUND · [§13](verification-maximal-os.md#r-13-017)

**R-13-018** IS: Code targeting V/M-class cores is ordinary Tier-2 or Tier-1 native code: a "shader" or "kernel" is AOT-compiled and certified off-device, then admitted like any other binary.
· Accept: there is no on-device compiler and no shader-IR compiler in any datapath.
· Trace: CJ-TAL-SOUND · [§13](verification-maximal-os.md#r-13-018)

**R-13-019** MUST: Apps needing `unsafe` are inadmissible at Tier 2 unless the `unsafe` routes through the verified HAL or the app ships a manual memory-safety proof.
· Accept: no third disposition exists.
· Trace: CJ-HAL, CJ-TAL-SOUND · [§13](verification-maximal-os.md#r-13-019)

**R-13-020** MUST: Any app receiving secret-labeled material carries the binary-level constant-time obligation; apps that touch no secrets carry no CT proof.
· Accept: the secret-touching set is derived from the label on the material, never from its channel of arrival (R-05-074), so it includes the §12 IDL-labeled flows and equally the capability-bounded DMA window, the RoT-latched front end re-delegated to a compartment, and the local entropy draw.
· Trace: CJ-CT-SOUND, CJ-IDL · [§13](verification-maximal-os.md#r-13-020)

### 13.3 Trust boundaries and supply chain

**R-13-021** IS: There are two trust boundaries: inter-compartment containment is compiler-independent at binary level (the universal contract), and intra-compartment memory safety is proven at binary level by the Tier-2 certificate rather than trusted to the Rust toolchain.
· Accept: the certificate removes a trusted dependency; it does not weaken containment, which is retained beneath it.
· Trace: CJ-TAL-SOUND, CJ-CERISE · [§13](verification-maximal-os.md#r-13-021)

**R-13-022** IS: There is no trusted-toolchain fallback: the certifying compiler is a hard prerequisite for *building* contained code, but the prerequisite is on the build, not on admission, which gates on the CHERI-TAL derivation and source-correspondence theorem.
· Accept: another producer emitting equivalent checked evidence is admitted identically; no uncertified app is ever admitted.
· Trace: CJ-TAL-SOUND · [§13](verification-maximal-os.md#r-13-022)

**R-13-023** MUST: Supply-chain defense is two mechanisms, not one: checked source correspondence against a *corrupted* artifact or trusting-trust injection absent from source, and compose-time confinement against a *subverted-but-memory-safe upstream* present in source.
· Accept: correspondence covers assembly, linking, and image construction but does nothing against a source-level logic backdoor carrying valid Tier-2 certificates, and the split is stated rather than blurred.
· Trace: CJ-CERISE · [§13](verification-maximal-os.md#r-13-023)

**R-13-024** MUST: The package manifest declares the app's internal compartment graph, each attacker-facing or third-party dependency taking a least-authority sub-manifest, so the seal/switch boundary confines a malicious dependency to the capabilities it was explicitly granted.
· Accept: the Tier-2 certificate handles the corruption dimension of a bad dependency; intra-app compartmentalization handles the authority dimension.
· Trace: CJ-CERISE · [§13](verification-maximal-os.md#r-13-024)

**R-13-025** IS: Proof-carrying code gates admission; it never relaxes runtime enforcement.
· Accept: no runtime check is elided on the strength of a certificate.
· Trace: CJ-CERISE · [§13](verification-maximal-os.md#r-13-025)

**R-13-026** MUST: Bit-for-bit reproducibility is mandatory only for the base image, whose exact regeneration underwrites the reference integrity manifest, and with DDC for the two checker binaries no admission certificate can cover; every other binary is admitted on source correspondence rather than reproducibility.
· Accept: a nondeterministic producer may be admitted when its final image carries a valid correspondence theorem; the base image and checker bootstrap remain reproducible and DDC-checked.
· Trace: CJ-T · [§13](verification-maximal-os.md#r-13-026)

**R-13-027** MUST: Compilation and proving both stay off-device: on-device admission type-checks the CHERI-TAL derivation, CIC-checks the artifact-local source-correspondence theorem, then performs capability wiring; the certifying toolchain is a build path, not an on-device service.
· Accept: proof objects may ship oracle-compressed.
· Trace: CJ-TAL-SOUND · [§13](verification-maximal-os.md#r-13-027)

**R-13-028** IS: Deep proofs are not cheap and are not per-device: Tier-0 functional refinement and non-interference are validated by the CIC kernel at release time over the base-image TCB and bound into the signed measured-boot root, while the lower-volume hyperproperty certificates an installed component carries (crypto reduction, constant-time, WCET) are CIC-checked when present, off the type-checking fast path.
· Accept: every install pays one local correspondence check; the CIC kernel validates large composed proofs at release time and additional hyperproperty certificates only where present.
· Trace: CJ-NI, CJ-KERNEL · [§13](verification-maximal-os.md#r-13-028)

**R-13-029** MUST: SBOM and proof artifacts ship with every release.
· Accept: both are present in the release manifest.
· Trace: CJ-T · [§13](verification-maximal-os.md#r-13-029)

---

## §14. Userland

**R-14-001** MUST: Core utilities are capability-native and reimplemented, not ported.
· Accept: no utility depends on an ambient-authority interface.
· Trace: CJ-CERISE · [§14](verification-maximal-os.md#r-14-001)

**R-14-002** MUST: System-wide W^X is a proven invariant, not a convention: CHERI capability monotonicity plus a machine-checked absence of Store∧Execute in the static initial capability distribution makes it an invariant of the entire capability derivation forest, object- and capability-granular, inside the Sail model.
· Accept: the absence is discharged **at the permission encoding**: R-15-007l admits no permission set holding both `Permit_Store` and `Permit_Execute`, so Store∧Execute is a combination the format cannot denote, and the machine-checked part is a finite check over the 32 codepoints rather than an enumeration of the composed distribution. The distribution check is retained as a redundant confirmation, and where it is run it is run over the composed distribution and not asserted per component.
· Trace: CJ-CERISE, CJ-SAIL · [§14](verification-maximal-os.md#r-14-002)

**R-14-003** IS: W^X subsumes the Harvard split, DEP, and the per-page no-execute bit, and supplies the *whole* of W^X rather than the necessary half: monotone derivation cannot mint execute authority over a writable region, so the writable-to-executable promotion primitive an NX bit must be paired with never exists.
· Accept: the coarse page-granular hedge is declined on the same grounds as the MMU and PMP.
· Trace: CJ-CERISE · [§14](verification-maximal-os.md#r-14-003)

**R-14-004** MUST NOT: The invariant admits no runtime-codegen exception: the sole way an executable region appears is install-time capability wiring deriving execute-only authority over read-only regions of the content-addressed image.
· Accept: newly compiled code (apps, servers, and V/M-class shaders alike) travels that same admitted-image path, so execute authority is never derived over written memory; nothing on the device JITs, interpreters run pure, and there is no kernel-mediated re-derivation primitive.
· Trace: CJ-CERISE · [§14](verification-maximal-os.md#r-14-004)

**R-14-005** IS: Apps are unverified *for functional correctness*, contained, and each a least-authority domain wired at compose time; app logic is memory-safe by construction, though not by default functionally proven.
· Accept: safe Rust by default, or any language whose binary carries the §13 memory-safety certificate.
· Trace: CJ-TAL-SOUND · [§14](verification-maximal-os.md#r-14-005)

**R-14-006** MUST: Intra-app library compartmentalization covers the authority dimension the memory-safety certificate does not: an app may partition itself into library compartments, each a node in the machine-checked component graph carrying its own least-authority sub-manifest, with cross-compartment calls mediated by the same seal/switch primitives that separate whole apps.
· Accept: no new mechanism, and the intra-app graph is fixed at build time, so it neither mints dynamic privilege nor escapes the §8 theorem.
· Trace: CJ-CERISE, CJ-NI · [§14](verification-maximal-os.md#r-14-006)

**R-14-007** MUST: Sub-compartmentalization is required where the authority gap bites: any dependency parsing attacker-controlled input, and any third-party library handed capabilities beyond pure compute.
· Accept: a compromised codec reaches only the buffer capabilities it was passed, and because those buffers are handed over as *local* capabilities it cannot retain them past the call to exfiltrate later.
· Trace: CJ-CERISE · [§14](verification-maximal-os.md#r-14-007)

**R-14-007a** MUST: Above the R-14-007 floor, discretionary compartment granularity is a budgeted composition-time quantity and not an inherited consequence of source factoring: the frame is non-work-conserving across confidentiality boundaries (R-07-036), so every live discretionary compartment is a divisor of the discretionary band and an idle one burns a slot no mechanism reclaims (R-17-004, R-17-006).
· Accept: the composition records its discretionary compartment count as a capacity decision against the §11 population rung (R-11-021); one compartment doing batched work is preferred to several waiting ones, and deep sets are held as retained state (R-14-011) rather than as live compartments. The lever recovers no scored row: the wall is a capacity statement rather than a percentage, so what the budget decides is where a composition sits against it.
· Trace: CJ-CERISE, CJ-WCET · [§14](verification-maximal-os.md#r-14-007a)

**R-14-007b** MUST NOT: No compartment boundary R-14-007 requires is merged to shrink the divisor.
· Accept: where the R-14-007a budget and R-14-007 conflict, R-14-007 wins; fewer compartments is less isolation, so the budget binds discretionary granularity only and is never a licence to flatten a mandated boundary.
· Trace: CJ-CERISE · [§14](verification-maximal-os.md#r-14-007b)

**R-14-008** MUST: The browser is maximally contained: per-origin compartments, no JIT, software rendering on C/V-class cores, and powerbox-only file and clipboard access.
· Accept: an origin RCE yields that origin's authority and nothing else.
· Trace: CJ-CERISE · [§14](verification-maximal-os.md#r-14-008)

**R-14-008a** MUST: Web-delivered JS and Wasm run in a pure interpreter, and every admitted performance-recovery lever on that path is ahead-of-time: threaded dispatch, superinstructions whose selection is computed off-device against a corpus and whose bodies are compiled AOT into the signed image, and data-plane inline caches.
· Accept: no on-device code generation exists anywhere on the path, so W^X (R-14-002, R-14-004) holds by construction rather than by interpreter policy.
· Trace: CJ-CERISE · [§14](verification-maximal-os.md#r-14-008a)

**R-14-008b** MUST: Superinstruction-set membership is a size-constrained selection against the corpus, bounded by the §15 SRAM capacity budget and the §7/§8 static memory plan, because each member costs its own interpreter body and buys dispatch reduction with image footprint.
· Accept: the frozen set is recorded as a constrained-objective selection whose footprint is charged against that budget; no set is admitted on the ground that it is data rather than generated code, which is a property W^X does not bound.
· Trace: CJ-MEMPLAN · [§14](verification-maximal-os.md#r-14-008b)

**R-14-008c** IS: An inline cache is compartment-private data under CHERI bounds inside one origin compartment, not microarchitecture: it crosses no confidentiality boundary, no §15 admission test applies to it, and the timing variance it introduces sits inside a discretionary slot whose width the §11 rung fixes, so it cannot move time between compartments; what it forfeits is intra-compartment timing determinism, which is not promised.
· Accept: the §8 non-interference statement is unchanged, and no cache state is shared between origin compartments or consulted across a partition switch.
· Trace: CJ-NI, CJ-WCET · [§14](verification-maximal-os.md#r-14-008c)

**R-14-008d** MUST: The inline-cache path carries a producer-side differential-testing obligation, test262 and the Wasm specification suite run against the same interpreter with caches disabled, discharged as engineering hygiene and never as a trust argument.
· Accept: the differential runs are off-device and no admission decision cites them; the residual is reliability rather than confidentiality, nothing on the device deciding Tier-2 functional correctness (R-14-005).
· Trace: CJ-TAL-SOUND · [§14](verification-maximal-os.md#r-14-008d)

**R-14-008e** MUST: The browser's own chrome, built-in libraries, and privileged JS are not downloaded content and are compiled natively through the §13 admission path rather than interpreted.
· Accept: no image-resident browser code runs on the interpreter, so the no-JIT cost falls only on network-delivered content.
· Trace: CJ-CERISE · [§14](verification-maximal-os.md#r-14-008e)

**R-14-008f** IS: There is no AOT route for web-delivered JS and Wasm, which are dynamic content and for which Wasm is no system execution target (R-14-013), so a faster interpreter narrows the no-JIT gap and no interpreter closes it; a web application shipped through the §13 install path is instead an ordinary native Tier-2 citizen paying none of that cost.
· Accept: the delivery-path cost stays booked as accepted in [performance-estimates.md](performance-estimates.md) rather than claimed recovered, and the install path is the only exit, taken by a product decision and not by a platform mechanism.
· Trace: CJ-TAL-SOUND · [§14](verification-maximal-os.md#r-14-008f)

**R-14-009** MUST: Origins come from a composition-fixed pool of *P* identical origin compartments (one manifest, one static memory plan) differing only in which origin is bound to them, because static composition admits no compartment minted at runtime.
· Accept: opening a tab binds a free pool member and raises the §11 population rung; closing one is an ordinary kernel-mediated session teardown whose capabilities die at the revocation epoch flip, which is what makes a member safe to rebind.
· Trace: CJ-CERISE, CJ-MEMPLAN · [§14](verification-maximal-os.md#r-14-009)

**R-14-010** MUST: Past the ceiling the browser evicts and the platform does not refuse: the (*P*+1)-th tab suspends a live origin and takes its member, the victim chosen by the browser among its own origins with no authority crossing.
· Accept: an unverifiable component decides which tab is slow and never how much time any tab gets, the §11 rung fixing the widths it may not touch.
· Trace: CJ-WCET, CJ-NI · [§14](verification-maximal-os.md#r-14-010)

**R-14-011** IS: Deep tab sets are retained state, not concurrent computation; the honest form of that statement, with numbers, is §17's population wall.
· Accept: consistent with R-17-002.
· Trace: CJ-WCET · [§14](verification-maximal-os.md#r-14-011)

**R-14-012** MUST NOT: There is no Linux-personality shim, ever, and no VM: faithful syscall translation is an ambient-authority emulator, and foreign binaries simply do not run.
· Accept: the only on-ramp is source-level recompilation against a WASI-shaped capability libc whose filesystem is a private, manifest-backed namespace; such ports are ordinary Tier-2 citizens.
· Trace: CJ-CERISE · [§14](verification-maximal-os.md#r-14-012)

**R-14-012a** IS: A private filesystem namespace is a typed view mechanically derived from the app's capability manifest, with paths only app-local aliases for object or service capabilities already present in the graph.
· Accept: build-time composition may deterministically join or shadow fragments, but runtime mount/bind/union mutation, a global service directory, path-based capability lookup, and namespace escape are absent.
· Trace: CJ-NI, CJ-CERISE · [§14](verification-maximal-os.md#r-14-012a)

**R-14-013** IS: *WASI-shaped* is API vocabulary, not substrate: everything compiles to native RV64+CHERI, and Wasm is not a system execution target. An app may embed an interpreter-mode Wasm engine as its private plugin mechanism, invisible to the architecture.
· Accept: no Wasm runtime exists in any system image (R-05-085).
· Trace: CJ-TAL-SOUND · [§14](verification-maximal-os.md#r-14-013)

---

## §15. Hardware Platform

### 15.1 ISA baseline

**R-15-001** IS: The ISA is RV64IMV + CHERI: base IM_Zicsr, `A` narrowed to `Zaamo`+`Zabha`, no scalar `F`/`D`, V supplying all floating point, no C extension (code density is carried instead by the fixed-rate dictionary encoding, R-15-036a, which is a fetch format and not an extension), purecap-only with no hybrid mode.
· Accept: the frozen profile (the artifact required by R-15-001a) enumerates exactly this extension set; any encoding outside it traps (R-15-014).
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-001)

**R-15-001a** MUST: The frozen profile exists as a single enumeration in one artifact, [isa-profile.md](isa-profile.md), rather than as an emergent property of the requirements that constrain it. The profile it enumerates is a crown-jewel spec: CHERI-CompCert, Cerise, and the CHERI-TAL are each proved against it, so a wrong profile is a correct proof about the wrong machine. The artifact is a *derived view*: it states no obligation of its own, cites the governing requirement for every row, and is defective, never authoritative, where it disagrees with this register.
· Accept: the artifact exists and its agreement with the register is *mechanically* checked in both directions: every ID it cites resolves, and every requirement in a profile-bearing subsection (§15.1, §15.3–§15.12) is carried by it. `tools/check.ps1` is that check and exits non-zero on either finding. The reverse direction is the one that earns its keep: a hand-maintained extraction silently drops rows, which is what makes a set stated in two places drift. The check tests *citation*, not *fidelity*: a row whose prose contradicts the requirement it cites is a review-gate finding against this entry.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-001a)

**R-15-001b** MUST: The surviving CSR bank is enumerated in that same view as the deletions are: register by register, each row citing the requirement that admits or excludes it. The enumeration closes the CSR address space (an address absent from the table is unallocated and traps under R-15-014, by that rule and not a second mechanism), so the "every CSR a partition can name" that the total restore quantifies over (R-07-015, R-15-214) is a list a reviewer can open.
· Accept: [isa-profile.md](isa-profile.md) carries the table; every row cites a governing requirement or is marked **open**, and every open row is booked in the extraction defects with a disposition. This entry states no membership of its own: it requires the enumeration to exist and to be closed, exactly as R-15-001a requires both for the extension set, and admits no CSR that the requirements its rows cite do not already admit.
· Trace: CJ-SAIL, CJ-KERNEL · [§15](verification-maximal-os.md#r-15-001b)

**R-15-002** IS: The platform is single-physical-address-space under CHERI: no MMU, `satp` fixed to Bare, no Sv39 translation.
· Accept: the Sail model carries no translation state; no page-table walker exists in any RTL.
· Trace: CJ-SAIL, CJ-KERNEL · [§15](verification-maximal-os.md#r-15-002), [§15](verification-maximal-os.md#r-15-002-2)

**R-15-002a** IS: That address space is architecturally **36 bits wide**. A capability's address field holds 36 bits, so no access above 2^36 is representable; integer registers stay 64-bit and no path runs from an out-of-range integer to an access, a purecap load or store taking no integer base (R-15-031b).
· Accept: the width is bounded by fabricable on-die SRAM rather than by architecture, which is what makes it safe to freeze permanently: the roster tops out at 16–32 GB laptop/desktop-class and at 1–2 GB in the single-planar-tier case (R-15-170, R-15-173a), main memory is on-die SRAM with no external bus and therefore no DRAM growth axis (R-15-158), and 64 GB is beyond any capacity this design plans for. It is not a window onto a wider space: no extension, segment, or bank register widens it, and the 36 bits are what put R-15-007's format inside 64 bits.
· Trace: CJ-SAIL, CJ-CERISE · [§15](verification-maximal-os.md#r-15-002a)

**R-15-002b** MUST: The physical address map is **dense**: every SRAM region and every MMIO aperture is placed inside the 36-bit space, with no aperture scattered at a wide power-of-two offset, and the placement is a stated constraint on the attested devicetree (R-09-007) and on the bank/macro/tier binding map (R-15-228).
· Accept: the address map is checked against the 36-bit bound at composition, so an aperture that does not fit is a composition failure rather than a runtime trap. A narrow space cannot absorb the scattering a 64-bit map tolerates, so the constraint is stated where the map is authored instead of being discovered when the first devicetree is composed.
· Trace: CJ-DEVTREE, CJ-ISOL · [§15](verification-maximal-os.md#r-15-002b)

**R-15-003** IS: There is a single privilege mode (Machine only). Privilege is a CHERI permission on the PCC (access-system-registers), not a ring.
· Accept: the S/U CSR banks, trap delegation (`medeleg`/`mideleg`), `sret`, and `Sstc`'s `stimecmp` are absent from the decode, the CSR bank, and the kernel proof.
· Trace: CJ-SAIL, CJ-KERNEL · [§15](verification-maximal-os.md#r-15-003), [§15](verification-maximal-os.md#r-15-003-2)

**R-15-004** IS: The architectural memory model is Ztso (RVTSO), adopted normatively in place of RVWMO.
· Accept: RVWMO is retained neither in hardware nor in proof reasoning; every ring proof is restated under Ztso.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-004), [§15](verification-maximal-os.md#r-15-004-2)

**R-15-005** MUST: There is exactly one Sail model, parameterized by core class (VLEN, matrix geometry), and exactly one capability encoding. That model's semantics are a crown-jewel spec: every architectural proof is stated against the model, and the model's faithfulness to what the profile intends is what no such proof checks.
· Accept: no second CHERI dialect (CHERIoT's compressed RV32 format included) exists; no second capability encoding forks the model, the RoT's scalar core included.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-005), [§14](verification-maximal-os.md#r-15-005-2), [§15](verification-maximal-os.md#r-15-005-3)

**R-15-006** MUST NOT: No hypervisor extension: the platform hosts no guests.
· Accept: the profile excludes H; the guest/VS interrupt-file machinery is absent (R-15-062).
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-006)

**R-15-007** MUST: The capability format is **re-parameterized CHERI Concentrate at 64+1 bits**, not a bespoke format: the bounds algorithm, the capability algebra, and the sentry and instruction semantics are the standard-track ones unchanged, and only the field widths change. The frozen parameterization is a 36-bit address (R-15-002a), a 4-bit object type, 5-bit encoded permissions (R-15-007b), a 5-bit exponent, and 8-bit base and 6-bit top mantissas with the top's high bits derived as CHERI Concentrate derives them, plus one validity tag bit outside the 64 (R-15-203). The object-type and permission space, the sentry mechanism, and the capability instruction set are frozen with the profile.
· Accept: encode, decode, bounds derivation, and every capability instruction are a re-parameterization of `sail-cheri-riscv`'s capability functions rather than a rewrite, so what the change owes is R-15-007a's representation-correctness proof and not a re-proof of CHERI. The re-pin to the ratified RVY base is **retired rather than deferred**: the dialect is permanently bespoke, no standards-track re-pin target is recorded for it, and the evidence that retirement spends is booked in §17 (R-17-048a).
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-007)

**R-15-007a** MUST: What the narrowing owes is a **representation-correctness proof**: encode/decode round-trip over the frozen field widths, field-extraction lemmas, and derivation of the represented base and top from the address, exponent, and two mantissas, each stated over the parameterized Sail capability functions. The proof states decode as a **total function** over the 19-bit bounds encoding (5-bit exponent, 8-bit base mantissa, 6-bit top mantissa) and **characterizes the malformed set at these widths**: which triples derive a represented top below their represented base is a property of the bounds algorithm at these mantissas and is established here rather than inherited.
· Accept: monotonicity, provenance, and non-forgeability are **inherited**, being statements about the algebra rather than the bit layout, and the algebra is preserved exactly (R-15-007b names the sole exception). A proof obligation that restates any of the three from scratch is evidence the change went past representation, and is a review-gate finding (R-18-034) rather than extra work. The capability encoding is accordingly authored rather than curated work on the Sail model, landing on the arrow R-17-039 names as the least built. The malformed-set clause is the whole of what capability integrity leaves owed here, the other two halves being discharged structurally: there is no reserved-field legality check, R-15-007 spending all 64 bits with no reserved field to police, and no legal-permissions invariant for tagged capabilities, R-15-007b's enumeration being total over its field where a one-bit-per-permission encoding validates 90 of 512. Bounds are what remain, because the reachable malformed set is a function of the mantissa widths and the narrowing changes them. A malformed capability is a legal held value faulting at its next dereference rather than a trap at construction, which is the side of the rule R-15-007h puts every failed derivation on, so it owes no CHERI cause code and no `mtval` case (R-15-073a). There is no optional half to the check: fault behaviour is a proof obligation and a §15 schedule term, so every integrity check the format carries is architectural, on the ground R-08-005 gives for the per-load tag check.
· Trace: CJ-SAIL, CJ-CERISE, CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-007a)

**R-15-007b** MUST: Permissions are a **non-orthogonal enumerated encoding**: the admitted permission sets are enumerated at freeze time as a lattice with its join and meet, and monotonicity is restated over that lattice rather than over independent bits. The enumeration is **total over the 5-bit field**, all 32 codepoints naming an admitted set with the residue taking the lattice's bottom element. Two combinations are excluded at the lattice rather than downstream of it, and each is stated in its own right: R-15-007o separates `Permit_Seal` from `Permit_Unseal`, and R-15-007l admits no set holding both `Permit_Store` and `Permit_Execute`.
· Accept: this is the one place the narrowing changes the algebra rather than the representation, so it is proved here rather than inherited: every derivation, `candperm` included, lands in the enumerated set, and no reachable instruction sequence produces a set outside it. Enumeration is available because the complete permission lattice and the full set of sealed-capability classes are known at composition time (R-15-005, R-13-001), and it is bounded: no permission the profile carries leaves the lattice, R-15-074's local/global and `store-local` and R-15-003's access-system-registers included. The evidence that a heavily compressed non-orthogonal permission field is buildable and compilable-against is **CHERIoT 1.0's 6-bit encoding of twelve permissions, and that is the sole shipped precedent**: RVY's RV64LYA spends **8 bits one-bit-per-permission** plus a pointer-mode bit and reserves the illegal combinations (90 valid of 512), and a compressed AP encoding was attempted during v0.9.9 review and **reverted**, leaving only a note that future capability encoding formats *may* compress. The requirement accordingly stands on the bit budget R-15-007 freezes and on one existence proof, not on a standards-track trend: RVY looked down this road and did not take it, which is recorded here so a later reader does not go looking for a convergence that is not there. Totality is what stands in place of an integrity check, and is why R-15-007a owes no legal-permissions invariant for tagged capabilities: a sparse encoding must reject the codepoints it does not use, a total one has none to reject, and the invariant becomes a property of the encoding rather than a check over it, with the residue assigned to the bottom element so the arbitrary part of the assignment fails closed.
· Trace: CJ-CERISE, CJ-TAL-SOUND · [§15](verification-maximal-os.md#r-15-007b)

**R-15-007n** MUST NOT: The permission encoding carries no software-defined permission bits, and no part of the capability format is left uninterpreted by hardware for software to give a meaning to; the composition-fixed object type is the ground on which a software class of capability is distinguished instead.
· Accept: **software-defined permission bits are declined, and the object type is the ground.** An SDP bit is uninterpreted by hardware, and its upstream consumer is a runtime distinguishing software classes of capability it did not itself create; classification here is composition-time and machine-enforced, the otype set being fixed at composition with no runtime type allocation (R-07-002b), and a sealed capability is unusable rather than merely marked: sixteen enforced classes where four advisory bits would sit. An SDP field would also have to come out of this one, the format having no spare bit (R-15-007), and it would be permission-shaped state outside the lattice's join and meet, which the monotonicity restatement would have to carry without interpreting. **RVY mandates a 4-bit SDP field for all encodings and CHERIoT carries them, so the absence is a divergence and not an omission**: that mandate binds RVY encodings, and this dialect is permanently bespoke with the re-pin retired (R-17-048a).
· Trace: CJ-CERISE, CJ-TAL-SOUND · [§15](verification-maximal-os.md#r-15-007n)

**R-15-007o** MUST NOT: No admitted permission set holds both `Permit_Seal` and `Permit_Unseal`, so the authority to mint a delegation and the authority to redeem one are never the same lattice element.
· Accept: **seal and unseal are separated because both consumers exist and are distinct paths.** The kernel mints a grant slot and hands out a handle sealed with a composition-fixed otype (R-08-004a), and unseals the slot for the duration of a cross-domain call (R-08-004c). A merged element would give the redeem path mint authority, and the redeem path runs on every cross-domain call while minting happens at delegation; mint authority over a grant otype is the authority to forge a delegation, which is the one thing the address-keyed revocation model assumes only the kernel creates (R-08-004b). The asymmetry upstream split for is accordingly sharper here, and separating makes it structural in R-14-002's sense (absent from the derivation forest by construction rather than true of one audited distribution) at a cost of one codepoint of thirty-two, which declining SDP is what leaves the field free to spend. R-15-007l applies the same instrument to Store∧Execute, where it is what makes W^X a property of the encoding and displaces CHERIoT's multi-rooted hierarchy. The split does not reach sentries: capability jump-and-link unseals a forward-edge sentry and seals the return as instruction semantics (R-15-068), holding neither permission.
· Trace: CJ-CERISE, CJ-TAL-SOUND · [§15](verification-maximal-os.md#r-15-007o)

**R-15-007c** IS: Mantissa width buys bounds precision and the narrowing **spends** it: bounds are byte-exact for objects up to 256 bytes, and above that the representable region rounds outward at a granularity of the length over 2^8, against a 128-bit format's exactness to roughly 4 KiB. This is a cost of the format, booked here, and not a prize claimed for it.
· Accept: the rounding is absorbed by the static memory plan (R-08-011) rather than at runtime, allocation on this machine being composition-time, so padding and alignment above the threshold are computed where the layout is decided and the representable-region-versus-requested-region reasoning does not reach the allocator's runtime path. What remains is dynamic subobject narrowing (`csetbounds` under the TAL), which carries the case exactly as it does today over a lower threshold, with padding bounded at one part in 256 of the object, and R-15-007k closes that residue at composition time as well rather than leaving it to a runtime instrument.
· Trace: CJ-MEMPLAN, CJ-TAL-SOUND · [§15](verification-maximal-os.md#r-15-007c)

**R-15-007d** MUST: The format width is a **permanent commitment**, not a composition parameter: every capability in the immutable image and every sealed blob is stored in it, so a later format break invalidates stored authority wholesale rather than costing a recompile.
· Accept: the width is frozen with the profile (R-15-014), carries no widening path and no re-pin target, and the margin that makes the commitment safe is argued once, in R-15-002a, against the SRAM capacity bound rather than against an expectation about future demand.
· Trace: CJ-SAIL, CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-007d)

**R-15-007e** IS: The frozen profile carries a **capability indexed load and store** in custom opcode space (`cld rd, cs1[rs2 << imm]` and its store form): bounds and permissions are checked on the authorizing capability at base plus scaled index and the access is performed there, with **no intermediate capability materialized** at any point.
· Accept: it is admitted on code size rather than on cycles, the offset-then-dereference pair it replaces being fused already (R-15-031b), so what it collects is the four bytes of image and of fetch bandwidth a fused pair still occupies, against the absent I-cache (R-15-164), the 33-43% no-C penalty (R-15-036), and the §15 SRAM capacity budget; it is the highest-frequency dereference sequence a purecap target emits, it carries full Sail semantics and is frozen with the proof like every other encoding the profile allocates (R-15-014), and its recorded re-pin target is **partial**: RVY places a capability shift-and-add (`YSH1ADD`…`YSH4ADD`) in `Zba`, which this profile adopts, so the address-formation half has a standards-track form, but that form materializes the intermediate capability R-15-007f turns on never constructing, and the fusion of check-at-base-plus-index with the access (which is the whole of the instruction) stays bespoke with the dialect (R-15-007d, R-17-048a).
· Trace: CJ-SAIL, CJ-CERISE · [§15](verification-maximal-os.md#r-15-007e)

**R-15-007f** IS: The instruction takes capability semantics **off** the dereference path rather than adding them: `cincoffset` may produce a capability outside the representable region, a case the Sail model, the CHERI-TAL soundness metatheorem, and the Cerise universal contract each carry, and a single indexed access never constructs that intermediate.
· Accept: what it adds is one Sail clause, one instruction-selection rule per production backend (R-18-014a), one case each in CJ-TAL-SOUND and CJ-CERISE, and one fixed-latency entry in the timing-annotated model that keeps it on the R-15-053 list; what it adds nowhere is architectural state, a `fence.t` flush-set member (R-15-214), an admission-test case (R-15-012), or a mutable microarchitectural structure the absence contract would newly police (R-15-100a). At R-15-007c's 256-byte exactness threshold the representability case is the common one rather than the large-object one, so the path the case leaves is the path it was hottest on.
· Trace: CJ-TAL-SOUND, CJ-CERISE, CJ-WCET · [§15](verification-maximal-os.md#r-15-007f)

**R-15-007g** MUST: The scale immediate is a composition-time parameter selected against the instruction mix this profile emits, by the discipline R-15-031a states for fusion-set membership, and frozen with the profile.
· Accept: whether the shift amount earns its encoding bits, or an unscaled index suffices because element strides are known where the slot plan is decided (R-08-011), is a recorded selection against a measured mix rather than a backend preference; the choice is frozen with the profile (R-15-014) and the Sail clause states one form.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-007g)

**R-15-007h** IS: Non-monotonic capability modification **clears the validity tag**; it does not raise an exception. A derivation that would widen bounds or add permissions yields an untagged result, so a failed derivation is a data result faulting at its next dereference rather than a control-flow event.
· Accept: this states which side of ISAv9's Morello-derived rule the "instruction semantics unchanged" of R-15-007 lands on, and the profile is committed to it already: R-15-007e and R-15-007f turn entirely on `cincoffset` producing a capability outside the representable region as a *carried* result rather than a trap. Nothing is owed to the trap path by it: no CHERI cause code and no `mtval` case (R-15-073a), and no failed derivation contributes a control-flow term to a §15 WCET entry. The tag clear is inherited semantics stated, not a divergence, so R-15-007a's representation-correctness proof is unaffected.
· Trace: CJ-SAIL, CJ-CERISE · [§15](verification-maximal-os.md#r-15-007h)

**R-15-007i** IS: The architectural register file is **merged**: one file of 32 registers of 64+1 bits, each holding a capability with its validity tag, an integer operand being that register's address field read as an integer. No separate capability register bank exists and no instruction moves a value between banks.
· Accept: the total restore of R-07-015 and R-15-214 therefore quantifies over **one** file of 32 × (64+1) bits together with the CSR bank R-15-001b encloses, not over an integer file and a capability file read as two, and that single set is what the totality obligation is stated against and what keeps the register files out of the `fence.t` flush set. ISAv9 makes the merged file normative for every CHERI architecture, so this is inherited rather than divergent, and the profile's silence was an omission rather than a choice.
· Trace: CJ-SAIL, CJ-KERNEL · [§15](verification-maximal-os.md#r-15-007i)

**R-15-007j** MUST: Where the frozen profile is **silent on the behaviour of a construct it carries**, ISAv9 (TR-987) semantics govern, and the profile's list of deviations from them is **exhaustive**. The clause runs over semantics and **not** over membership: nothing enters the profile by inheritance, what exists being decided by the enumerations alone (R-15-001a's extension set, R-15-001b's closed CSR bank, the exclusions named one by one, and R-15-014's trap on every unallocated encoding), so an ISAv9 construct the profile does not name is absent and is admitted only on a stated ground.
· Accept: this makes R-15-007's "re-parameterized rather than bespoke" usable rather than merely descriptive (an unstated behaviour is a lookup against the pin, never implementer latitude), and the residue it closes is behavioural in every case: an all-zeroes granule decodes as untagged NULL, which is what eager zeroize reads back (R-15-182, R-15-060); a sentry installed in `MEPCC` unseals on `mret` as it does when jumped to (R-15-073, R-07-022); and which cause code an unaligned base raises is ISAv9's answer rather than a choice this profile makes (R-15-073a, R-15-084). Each inherits over the *narrowed* fields, so R-15-007a's representation-correctness proof is what discharges the format-side cases at the frozen widths and no per-property clause is owed. The inheritance is version-pinned rather than tracking: ISAv10 is not a source and neither is the retired RVY line (R-17-048a), a published Cambridge release being an amendment that reruns the review gate (R-18-034). A behaviour later found to deviate without appearing in the list is a defect in the list, not latitude an implementation may keep.
· Trace: CJ-SAIL, CJ-CERISE · [§15](verification-maximal-os.md#r-15-007j)

**R-15-007k** MUST: **Every bounds narrowing the profile's code emits is exactly representable, and the obligation falls on the static memory plan rather than on an instruction.** The plan lays each object a CHERI-TAL derivation may narrow to at its representable alignment and at a granule-quantized length, and constrains a dynamic-length split of an array to that array's representable granule, so a `csetbounds` whose result rounds outward is a **defect in the slot plan** (R-08-011) rather than a runtime event. `CRAM`, `CRRL`, `CSetBoundsExact`, and RVY's `YAMASK` are accordingly **not admitted**, and no software computation of the exponent runs at runtime.
· Accept: `CRAM`/`CRRL`'s consumer upstream is a **runtime allocator** asking how far to round a request and how to align it, and R-08-010 deletes the online allocator: allocation here is the read of a pre-assigned slot. R-15-007c's residue does not restore that consumer, and this is what decides the cluster: a dynamically narrowed subobject's address is a composition-time slot base plus a composition-time offset plus a dynamic index times a composition-time stride, so its residue class modulo any composition-time alignment is known **where the layout is decided** even where the address itself is not known to the compartment holding it, and its length is its type. Exactness is therefore a statically decidable property of the slot plan, and `CRAM` computes at runtime a function of quantities the plan has already fixed. The question the instruction pair asks can only be answered by whoever owns the layout, and on this machine that is a composition-time tool that has answered it for every slot.
· Accept: **`CSetBoundsExact` is declined in the stronger direction, because inexactness is a leak of authority rather than a loss of precision.** An outward-rounded narrow grants the derived capability up to a 2^-8 fraction of the length beyond the subobject on each side, and under the linear/affine ownership the plan is built on (R-08-011), a narrow that *splits* ownership hands that excess to the recipient while the retainer keeps it. What is owed is accordingly that the leak be **impossible**, not that it be reported: a runtime assertion fires in production after the layout is already wrong, which is not where this platform discharges checks of this class. The exactness side condition sits in the CHERI-TAL narrowing rule and is discharged against the plan.
· Accept: **the exception code is refused a second time on its own ground.** R-15-007h puts every failed derivation on the tag-clear side, carrying no CHERI cause code, no `mtval` case (R-15-073a), and no control-flow term in a §15 WCET entry, and the cause codes are ISAv9's frozen with the profile (R-15-014). An inexact narrow is **monotone** (the fault `CSetBoundsExact` raises is on a derivation that succeeded), so admitting it would give the profile its only trap on a successful monotone derivation, and a cause code for the one event the rule above deletes everywhere else.
· Accept: the third answer, a **software computation of the exponent**, is not declined but relocated, and priced where it lands: it is R-08-011's own rounding, run once per slot by the tool that already computes padding and alignment above the threshold, costing no runtime instruction, no opcode, no Sail clause, and no admission-test case (R-15-012). What it does cost is padding, already booked by R-15-007c at one part in 256 of the object and zero below 256 bytes where bounds are byte-exact, plus the quantization of a dynamic slice boundary to the enclosing array's representable granule (the same one part in 256, and nothing at all for arrays at or under 256 bytes). **CHERI has carried `CRAM`/`CRRL` since ISAv7-A3 and RVY standardized `YAMASK` into its base ISA, so the absence is a recorded divergence rather than an omission**; that mandate binds RVY encodings, and this dialect is permanently outside them (R-17-048a).
· Trace: CJ-MEMPLAN, CJ-TAL-SOUND · [§15](verification-maximal-os.md#r-15-007k)

**R-15-007l** MUST: **No admitted permission set holds both `Permit_Store` and `Permit_Execute`**, so a W+X capability is *unrepresentable* rather than merely underivable, and R-14-002's absence of Store∧Execute is a property of the permission decode rather than of one audited distribution. CHERIoT's **multi-rooted capability hierarchy is declined as a mechanism**: no root capability register, root-selection CSR, or architectural root construct exists, and the disjointness of the composition-fixed roots is a **corollary** of the lattice rather than a structure the ISA carries.
· Accept: the lattice is the instrument the profile already owns and already uses this way (R-15-007b's enumeration is total over the 5-bit field and separates `Permit_Seal` from `Permit_Unseal` on exactly this reasoning), so the Store∧Execute exclusion spends **no codepoint, no bit, and no silicon**: declining a combination is declining to assign it, and the residue takes the lattice's bottom element, which is what makes the unassigned part fail closed. §4.1's field table is unchanged and the 64-bit budget is untouched (R-15-007).
· Accept: **the lattice exclusion is strictly stronger than root disjointness, and the difference is in what discharges it.** Disjoint roots give "nothing *derived from the roots* holds both", whose discharge quantifies over the derivation forest and rests on an audit that the root set is the whole of the ungenerated authority; the exclusion makes the combination denote nothing, so the obligation is a **finite check over 32 codepoints inside R-15-007a's decode**, holding for every capability in every reachable state whatever its provenance. Permission decode is total, so there is no malformed-permission case to except (R-15-007a leaves only the bounds half), and R-14-003's "monotone derivation cannot mint execute over a writable region" no longer needs monotonicity for the intra-capability half at all. It is also the only version of the property available for free here: this platform has no runtime loader for roots to be handed to, the initial distribution being composition-fixed (R-07-019, R-08-011), where CHERIoT's roots exist to seed a loader and RVY carries root-selection state its debug surface names.
· Accept: **the multi-rootedness falls out rather than being built.** R-07-006's per-core partition-bounded root capability cannot be one capability once W+X is unrepresentable, so composition hands each core a permission-split set over its partition (execute-side authority over the image's read-only text extents, store-side authority over its data), which is what R-14-004's install-time wiring already derives. That split is a fact about the composition-time distribution, checked by the tool that composes it, and not an ISA mechanism, so §5's closed CSR table (R-15-001b) and the admission tests (R-15-012) are untouched.
· Accept: **the bound is on capabilities and not on memory, and the limit is stated rather than left to a reader.** The same address may be writable through one capability and executable through another (equally true of CHERIoT's roots, which span one space with disjoint permissions), so what forbids the *temporal* case, writing a region and then obtaining execute authority over it, is R-14-004's absence of runtime code generation and the immutability of the content-addressed image, not the encoding. The ROM's placement of the verified M-mode image into SRAM (R-09-006) is that case, and it sits before the measured chain rather than inside this invariant.
· Trace: CJ-CERISE, CJ-SAIL, CJ-TAL-SOUND · [§15](verification-maximal-os.md#r-15-007l)

**R-15-007m** MUST NOT: A **capability subset test** (`CTestSubset` in ISAv8/v9, `YSS` in RVY's base ISA) is not admitted, and no instruction computes at runtime whether one capability's bounds and permissions are contained in another's. A capability that does not authorize an access made through it faults at that access under R-15-007h, and the containment relation the instruction would test is fixed at composition rather than reconstructed on the call path.
· Accept: **both upstream consumers are absent, and the second is the one that decides it.** The first is a garbage collector's pointer-inside-object test, and R-08-010 compiles the heap into a whole-program slot plan with neither a collector nor an online allocator to run it. The second is argument validation at a domain boundary, which this platform does have: R-04-004 gives the switcher save and restore and the local/global discipline, and what that discipline bounds is a delegated buffer's **lifetime**, enforced on the store path by R-15-074's permission rather than computed at the boundary. The buffer's **extent and rights** are fixed a phase earlier, by the §12 IDL message type and the manifest's import/export tables (R-05-124, R-05-117) over the composition-fixed initial distribution (R-07-019), with R-05-096b's join rejecting overlapping cross-compartment grants, so a caller cannot hand across more than the edge admits, and an edge that would is a composition-time join failure rather than a runtime branch.
· Accept: **no consumer of the two-operand form survives.** What remains at runtime is whether a delegated buffer is long enough and carries the rights an operation needs, a question about one capability that `cgetlen` and `cgetperm` answer against a composition-time constant, carried with the dialect R-15-007 pins. The containment form buys something only where the checking party already holds the enclosing capability, and the live case of that shape, a peer writing into a window its server owns, is closed by R-05-149a's indices against one exact-bounded base capability, which makes the containment the hardware's bounds check on the access the server derives. The failure disposition is fixed besides: the fault costs nothing on the path that succeeds, where a tested form spends a forward conditional under static-only prediction with a full mispredict penalty (R-15-019, R-15-054), in code the §11 budget charges to every cross-compartment call, to reach the fail-stop and supervised restart (R-12-001) the failing arm would take anyway.
· Accept: **the instruction is not the inheritance its presence in ISAv8/v9 suggests, and R-15-007j is why.** That clause inherits ISAv9 behaviour over *narrowed* fields; the permission field is not narrowed but re-encoded as R-15-007b's enumerated lattice, and `CTestSubset`'s permission half is a bitwise containment test over independent bits, of which the lattice has no reading. Restating it as the lattice order costs nothing in semantics, the enumerated meet already giving that order, but it makes the instruction **bespoke**: its own Sail clause, its own comparator over the bounds encoding decoded at 8 and 6 mantissa bits, and a stated agreement between the order tested and the monotonicity R-15-007b proves over the lattice, rather than an ISAv9 case admitted at narrowed widths. **CHERI has carried it since ISAv7's experimental appendix and RVY promoted it into the base, so the absence is a recorded divergence rather than an omission**; that mandate binds RVY encodings, and this dialect is permanently outside them (R-17-048a).
· Trace: CJ-SAIL, CJ-IDL · [§15](verification-maximal-os.md#r-15-007m)

**R-15-008** IS: The base sealed-entry and forward/backward-edge sentry semantics are the only sentry semantics the profile carries; the frozen dialect adds no sentry surface to the standard-track base.
· Accept: CHERIoT's interrupt-state sentry variants are absent (R-15-078).
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-008)

**R-15-009** IS: The bespoke matrix extension is fork-and-frozen with full Sail semantics until a ratified RISC-V matrix extension (AME/IME lineage) supersedes it, at which point it re-pins.
· Accept: the Sail model carries full matrix semantics; a re-pin obligation is recorded.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-009)

### 15.2 The five-part admission test

**R-15-010** MUST: An extension or feature is admissible only if it satisfies all five tests: (1) deterministic architectural semantics, a function of architectural state and Sail-expressible; (2) data-independent timing, discharged by operand-value-independent latency, by a proof that no secret-labeled operand reaches it, or by confinement of the data-dependence to the owning island's static NoC and memory partition, and by no other route; (3) no new hidden shared microarchitectural state surviving a partition switch un-flushed by `fence.t`, discharged by absence, by flushing, or by being provably constant across the switch interval, and by no other route; (4) no new authority path outside capabilities; (5) no autonomous behaviour: no hardware walkers, updaters, or feedback loops.
· Accept: each admitted feature carries five recorded dispositions, each naming which enumerated discharge form it takes; the case law of the event-driven sensor readout (R-12-070) and the frozen 1000BASE-T canceller (R-15-137) is now statute rather than precedent.
· Trace: CJ-SAIL, CJ-LEAK · [§15](verification-maximal-os.md#r-15-010)

**R-15-011** MUST NOT: Bare self-exclusion from the constant-time list is not a pass for test (2): the exclusion is itself the proof obligation, and a feature neither constant-time nor provably secret-unreachable is inadmissible.
· Accept: every off-list feature has a discharged flow-discipline obligation, not a declaration.
· Trace: CJ-LEAK, CJ-NI · [§15](verification-maximal-os.md#r-15-011)

**R-15-012** IS: Speculation fails tests (1)–(3); SMT fails (3) by construction; dynamic branch prediction fails (3); `Zalrsc` fails (3) and (1).
· Accept: each is excluded, with the failing test named.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-012)

**R-15-013** MUST: Defense-in-depth clause (*verify rather than hedge*): a redundant mechanism is admitted only if it is a genuinely disjoint failure domain the primary's own verification does not reach; where the primary is formally verified, the hedge is declined.
· Accept: neither roster is kept here. Every declined hedge cites *verify rather than hedge* at the point of decline and every admitted one cites it at the point of admission, so both sets are read off the citations and a hedge cannot be settled in the prose without the clause knowing. A decline shows the primary's own verification reaches the domain; an admission shows a genuinely disjoint failure domain and zero cost on the scarce axis.
· Trace: CJ-T · [§15](verification-maximal-os.md#r-15-013)

**R-15-014** MUST: The profile is frozen with the proof, and all reserved, custom, and unused encodings trap rather than silently executing.
· Accept: the decode traps every unallocated encoding; no encoding is a no-op by default.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-014)

**R-15-014a** MUST: The freeze R-15-014 names is reached in **two acts**, because several of its decisions are re-derived from measurement against generated output (R-15-036i, R-15-036k, R-15-036l, R-15-036n, R-15-067d) and no such output exists until a backend and a composed image do. The **provisional freeze** fixes everything not conditioned on that measurement and is a specification act with no build prerequisite: the extension set (R-15-001), the capability format and its permanent width (R-15-007d), the privilege, address, and memory models (R-15-003, R-15-002, R-15-004), the CSR bank (R-15-001b), the exclusions, and the encoding's structure (R-15-036a, R-15-036b). The **final freeze** is the act the proof is taken with, and the delta between the two is closed and enumerated: (i) the realized dictionary size, its entry selection, and the site-varying policy (R-15-036i, R-15-036k); (ii) the bundle, header, and slot widths carried as a DSE parameter (R-15-036a), the one structural item in the delta and one that changes no instruction semantics, the format allocating no opcode; (iii) whether the emitted call and global-address-materialization forms are PC-relative or composition-time absolute, with any absolute form's reachable-region parameter (R-15-036l); (iv) whether the single-check multi-register save and restore is carried, and at which register-list lengths (R-15-036n); (v) the bitfield pair's field-specifier form, whether its insert form is carried, and whether the pair is carried at all (R-15-067d), together with any further code-size candidate weighed in that same act (R-15-036n); (vi) the capability indexed load/store's scale immediate (R-15-007g); (vii) the frozen fusion set's membership (R-15-031a). A change outside that list at the final freeze is an amendment that reruns the review gate (R-18-034) and not a second-act decision.
· Accept: what sorts a decision into the second act is that it is conditioned on a measurement against generated output, not that it is merely open when the first act is taken, so an open question carrying no such conditioning (the permission-lattice enumeration, the dynamic-narrowing instructions, the trap-path residue) is decided at the provisional freeze or not at all. Every delta item has a **declining provisional value**, no admission, PC-relative forms, and an unselected dictionary, so the provisional profile is a total compilation target rather than a partial one and the toolchain, the Sail model, and the CompCert backend (R-18-003a) target it without waiting; each item admitted at the final freeze then costs one selection pattern, one Sail clause, and a dictionary regeneration, which extends that work rather than invalidating it. Permanence attaches to the second act only: no image encoded under the provisional dictionary is deployed or stored, so R-15-036i's wholesale-invalidation cost and R-15-007d's width commitment land where the proof does. The gating artifacts of the second act are R-18-003c's and are not restated here.
· Trace: CJ-SAIL, CJ-FORMAT · [§15](verification-maximal-os.md#r-15-014a)

### 15.3 Memory model

**R-15-015** IS: Ztso is implemented natively by in-order issue plus a FIFO store buffer, at essentially no microarchitectural cost.
· Accept: the only reordering the machine exhibits is store→later-load bypass through the store buffer.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-015)

**R-15-015a** MUST: Ztso is a system property whose structural discharge has three parts: the per-core FIFO store buffer (R-15-015), single-copy memory whose bank arbiter is the per-location order-determining point (R-15-087), and the NoC and memory controller preserving each hart's program order of memory requests across banks, macros, shared cross-island ring windows, **and device endpoints**. The third is not conferred by the store buffer's shape and is a named obligation in its own right.
· Accept: two stores from one hart to distinct banks reach their arbiters in issue order, and no later load returns a value the coherence order places before an earlier load's. Discharged either structurally, where per-hart request order is a static property of the composition-time TDM slot schedule and per-island arbitration and reordering is unrepresentable in the fabric (preferred), or by an ordering lemma over the NoC and memory-controller RTL. Bare per-core reasoning is not a discharge. The destination set includes device endpoints because R-15-015b's drain confers *issue* order only: an edge whose observer is a device rather than a hart (descriptor-before-doorbell, where the DMA engine reads the descriptor from SRAM after taking the doorbell) needs the descriptor visible at its bank arbiter before the endpoint can act, which is an arrival property across two independent fabric paths and not a property of the core.
· Trace: CJ-SAIL, CJ-ISOL · [§15](verification-maximal-os.md#r-15-015a), [§15](verification-maximal-os.md#r-15-015a-2)

**R-15-015b** MUST: The store buffer holds SRAM-space stores only: a device-space store does not enter it, issuing only once the buffer has drained and completing at the endpoint's accept before it retires. **Drained** means every prior buffered store has been issued into the fabric, not that it has reached its bank arbiter: the core confers issue order, and the arrival half of any edge whose observer is not the issuing hart is R-15-015a's obligation. The exclusion is forced by R-15-218, whose padded constant is stated over the class's depth and memory bandwidth and would otherwise be set by the slowest endpoint's accept latency (R-12-046's divided card clock being an on-die existence proof, and R-15-196's island-clock FIFO narrowing that to the common case without closing the full-FIFO backpressure worst case a pad must price); the drain-first half is forced by R-15-015, a device store leaving the core ahead of a buffered SRAM store being a store→store reordering Ztso does not permit.
· Accept: no device-space entry is representable in the buffer in the RTL, and the issue condition is one statically-decoded stall on one instruction class rather than the load-path bypass-correctness obligation R-15-018 ground (3) rejects. The two halves close, **at the core**, exactly the edges between requests the core itself sequences: device-store→device-store, serialized by the accept, and the MMIO read-back, the store having completed before the load issued. **Descriptor→doorbell is not one of them**: its observer is the DMA engine, which reads the descriptor from SRAM after taking the doorbell, so that edge is discharged by R-15-015a over device endpoints, the drain supplying its issue-order half and the fabric its arrival half. With both in place the `PI`/`PO` axis separates nothing. The endpoint's accept latency, evicted from R-15-218's constant, lands in the device store's own per-instruction latency in the timing-annotated model (R-05-103) with the full-FIFO crossing as its worst case, charged to the compartment that issues the store rather than to every partition switch. Cost is a drain plus an endpoint round-trip per device store, at rate only on the MSI send (R-15-064, R-08-032), mitigated by R-11-010's ring-depth amortization.
· Trace: CJ-SAIL, CJ-WCET, CJ-ISOL · [§15](verification-maximal-os.md#r-15-015b)

**R-15-015c** MUST: Device authority is provisioned by latency class in the attested devicetree (R-09-007): a compartment holds only endpoints whose worst-case accept is of the same order, and an endpoint whose full-FIFO crossing dominates sits behind its own thin driver compartment whose entire budget is that latency.
· Accept: no grant spans a fabric-rate register block and a divided-clock endpoint (R-12-046), so no compartment's MMIO is priced at a worst case it does not incur. The rule narrows an authority grant inside the sole origin of device authority (R-05-138), from which the verified HAL derives rather than fabricates: no mechanism, interface, or ordering rule changes and no proof obligation moves, R-15-015b pricing each store exactly as before. What is removed is the reachability that created the term, not the margin on it.
· Trace: CJ-CERISE, CJ-WCET · [§15](verification-maximal-os.md#r-15-015c)

**R-15-015d** MUST: The R-15-015c split is taken only where the slow endpoint's worst case dominates the compartment's §11 bound, never merely because two endpoints differ, because each additional driver compartment is one more tenant dividing the non-work-conserving frame (R-07-036) and one more slot against the population wall (R-17-004, R-17-006).
· Accept: a split that meaningfully shortens no slot is not admitted; where the slow endpoint does dominate, the split is taken, a slot width set by a divided card clock being the larger loss. This is the same trade R-14-007a states from the compartment-count side, and the two are arbitrated together rather than as independent preferences.
· Trace: CJ-WCET · [§15](verification-maximal-os.md#r-15-015d)

**R-15-016** MUST: The Ztso guarantee is an RTL-against-Sail proof obligation stated over the whole memory path: the store buffer provably exposes no ordering weaker than TSO, and the fabric beneath it provably preserves per-hart request order (R-15-015a).
· Accept: the obligation is a named bring-up gate alongside the `Zkt`/`Zvkt` timing obligation, and its statement covers the NoC and memory controller rather than the store buffer alone.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-016), [§15](verification-maximal-os.md#r-15-016-2)

**R-15-017** IS: Legal standard `fence` encodings collapse to two semantics: a normal `fence` drains the store buffer iff its predecessor set contains a write (`PW` or `PO`) and its successor set contains a read (`PR` or `PI`); every other predecessor/successor combination and `fence.tso` are semantic no-ops. Reserved `fm` values still trap. The drain remains available for userspace store→later-load synchronization; SPSC rings, cross-island rings, MMIO, and DMA-descriptor visibility are not consumers.
· Accept: the Sail model and Isla litmus oracle carry `drain | nop`, not the 256-case predecessor/successor lattice or separate `fm` semantics; all legal standard encodings remain accepted, the canonical ring algorithm contains no fence, and no cache-management instruction accompanies it.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-017)

**R-15-018** IS: Sequential consistency was evaluated and rejected on four platform-specific grounds, none of which carries a hart-count or issue-width term: single-copy memory (R-15-087) makes the deviation from SC local to each hart's own store buffer rather than coherence-borne, so there is no traffic term for hart count to scale, and wider issue deepens the buffer each load must wait out. SC is named in §18 as a question worth revisiting, not as a pending change.
· Accept: Ztso is the specified model; the §18 entry is a question, not a deliverable. The rejection is stated over the platform, not over a configuration of it, and ground (4)'s saving is the single store→later-load relaxation that single-copy memory leaves: one clause of the ordering relation, not the memory model.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-018), [§15](verification-maximal-os.md#r-15-018-2)

### 15.4 Control-flow prediction

**R-15-019** MUST: All branch prediction is static: backward-taken / forward-not-taken, a fixed function of the instruction encoding and displacement sign, with zero mutable predictor state.
· Accept: no BHT, BTB, RAS, or dynamic direction, target, or return predictor exists in any RTL.
· Trace: CJ-SAIL, CJ-ISOL · [§15](verification-maximal-os.md#r-15-019)

**R-15-020** IS: Deleting the predictor structures is strictly stronger than flushing them: nothing joins the `fence.t` flush set and no residual completeness obligation exists for them.
· Accept: the flush set contains no predictor entry.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-020)

**R-15-021** MUST: The predictor deletion is discharged structurally by the microarchitectural absence contract, not by RTL ⊑ Sail.
· Accept: predictor absence appears in the absence-contract register (R-15-100a, rows A-04 through A-06), not among the refinement obligations.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-021)

**R-15-022** IS: Fetch runs ahead only down the statically determined path, so wrong-path fetch is a deterministic function of the instruction stream and never of prior execution history.
· Accept: with no I-cache, fetch reads flat SRAM at fixed latency; the only run-ahead structure is the static-path fetch buffer (R-15-152).
· Trace: CJ-WCET, CJ-ISOL · [§15](verification-maximal-os.md#r-15-022)

**R-15-023** IS: The accepted cost is full pipeline-latency mispredict-equivalent penalties on forward conditional, indirect, and call/return dispatch, priced into WCET; the RAS is excluded despite its IPC value because it is per-core mutable return history.
· Accept: the WCET tables carry the penalty; no return-address prediction exists.
· Trace: CJ-WCET · [§15](verification-maximal-os.md#r-15-023)

### 15.5 Atomics

**R-15-024** IS: Only the unconditional atomic-RMW half of `A` is retained: `Zaamo` at word and doubleword width, extended by `Zabha` to byte and halfword. `Zacas` (including `amocas.q`) and `Zalrsc` are excluded.
· Accept: the profile lists `Zaamo`+`Zabha` and excludes both others.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-024)

**R-15-025** IS: `Zalrsc` is excluded because its per-hart reservation register is hidden inter-instruction state (test 3), SC may fail spuriously (test 1), and reservation-granule contention is a cross-hart channel.
· Accept: the Sail model carries no reservation set, no spurious-failure nondeterminism, and no constrained-LR/SC forward-progress rules.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-025), [§15](verification-maximal-os.md#r-15-025-2)

**R-15-026** IS: `Zacas` is excluded for want of a consumer: the multikernel is share-nothing with no kernel locks, rings are single-writer SPSC under Ztso, refcounts and status flags are single-instruction `Zaamo`, and no capability ever resides in shared mutable memory.
· Accept: no admitted software requires compare-and-swap; the 128-bit CAS coherence point is absent from the memory model.
· Trace: CJ-SAIL, CJ-KERNEL · [§15](verification-maximal-os.md#r-15-026)

**R-15-027** IS: `Zabha` supplies only the byte and halfword forms of the retained unconditional AMOs; sub-word compare-and-swap (`amocas.b`/`.h`) remains excluded with `Zacas`.
· Accept: the added encodings are width cases on the existing AMO semantics, adding no operation class.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-027)

**R-15-028** IS: `Zabha`'s justification is lowering-admissibility, not traffic volume: with `Zalrsc` and `Zacas` both deleted, sub-word atomic RMW has no admissible lowering (a wider aligned access would race on adjacent bytes; a lock-based `libatomic` call is forbidden).
· Accept: the justification does not depend on consumer count; the claimed consumers are exactly those §13 permits: atomic state that is constructor-injected or reachable only from a handed reference.
· Trace: CJ-SAIL, CJ-CERISE · [§15](verification-maximal-os.md#r-15-028)

**R-15-029** IS: `Zaamo` covers the atomic traffic that remains above a share-nothing kernel and an SPSC data plane, the dominant consumer being `Arc`'s strong and weak counts in contained Rust.
· Accept: narrowing the profile below `Zaamo` would delete `Arc` and the shared-ownership vocabulary §14's porting story rests on; that is recorded as the ground for retention.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-029)

**R-15-030** MUST: No retry loop of any kind contributes to any task's WCET bound: neither an LR/SC spurious-failure retry nor a CAS compare-fail retry exists.
· Accept: every atomic is one bounded memory transaction in the timing-annotated model.
· Trace: CJ-WCET · [§15](verification-maximal-os.md#r-15-030)

### 15.6 Macro-op fusion

**R-15-031** IS: The decoder may fuse a frozen set of adjacent instruction pairs (address formation and load-effective-address, compare-and-branch, short dependent-ALU chains) into a single internal operation.
· Accept: the fused set is enumerated and frozen with the proof. The dependent-ALU-chain class is **narrowed and not deleted** by R-15-067a on the same terms R-15-031b records for the capability pair: the shift-and-mask sequence stays legal, stays emitted where the field specifiers are not compile-time constants, and stays in the frozen set.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-031)

**R-15-031a** MUST: The frozen set's membership is selected against the instruction mix this profile emits (purecap-only, no C, no scalar `F`/`D`), as a composition-time parameter of the §15 design-space exploration, and is not inherited from the general RISC-V fusion literature.
· Accept: the frozen set is a recorded selection against a measured mix; no pair is carried solely because a conventional RV64GC target would fuse it.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-031a)

**R-15-031b** MUST: The set includes the capability-address-formation pairs, stated by function because purecap mnemonics vary by CHERI line (R-15-007): offset-then-dereference (`cincoffset` + load/store), PCC-relative materialization (`auipcc` + `cincoffset`), and address-then-narrow at allocation and compartment entry (`csetaddr` or `cincoffset`, then `csetbounds`, in that dependency order).
· Accept: each is enumerated in the frozen set or its exclusion is recorded against the measured mix. Base-plus-index `add`+load is not separately listed because a purecap load takes no integer base: it exists here only as the first pair. The first pair is **narrowed and not deleted** by R-15-007e, which expresses in one instruction the indexed dereferences it can reach: the sequence stays legal, stays emitted where the indexed form does not apply, and stays in the frozen set, R-15-031c pricing a retained pair at zero.
· Trace: CJ-SAIL, CJ-WCET · [§15](verification-maximal-os.md#r-15-031b)

**R-15-031c** IS: Widening the set toward capability arithmetic adds no admission-test case, no `fence.t` flush-set member, and no obligation beyond R-15-034: each added pair is admitted by the R-15-032 disposition and the R-15-033 transparency argument unchanged, and tightens rather than loosens every bound it appears in.
· Accept: membership is bounded by decoder area and the §15 proof-simplicity term, never by a safety, timing, or schedulability limit.
· Trace: CJ-RTL-SAIL, CJ-WCET · [§15](verification-maximal-os.md#r-15-031c)

**R-15-032** IS: Fusion is a combinational function of the static instruction encoding, holds no state surviving a partition switch, mints no authority, and runs no walker, so it passes all five admission tests.
· Accept: five recorded dispositions; nothing joins the `fence.t` flush set.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-032)

**R-15-033** IS: Fusion is architecturally transparent: a fused and an unfused execution reach identical architectural state, so it rides the existing functional refinement and disturbs no binary certificate, constant-time proof, or WCET table.
· Accept: a fused pair is one more fixed-latency entry in the timing-annotated model.
· Trace: CJ-RTL-SAIL, CJ-WCET · [§15](verification-maximal-os.md#r-15-033)

**R-15-034** MUST: The sole obligation on fusion is that the fused set is frozen with the proof and listed in the timing-annotated Sail model.
· Accept: no certificate, WCET bound, or constant-time statement is re-derived on its account.
· Trace: CJ-WCET · [§15](verification-maximal-os.md#r-15-034)

### 15.7 ISA exclusions

**R-15-035** MUST NOT: The initialization-tag plane (Mon CHÉRI-derived Write-before-Read as a second metadata plane) is excluded; the property is carried by the §5 definite-initialization attribute.
· Accept: one tag plane exists in the SRAM word, not two (R-15-165); the deletion recovers one bit per granule, its DECTED coverage, a Sail invariant, an RTL ⊑ Sail obligation, and a DSE parameter.
· Trace: CJ-RTL-SAIL, CJ-TAL-SOUND · [§15](verification-maximal-os.md#r-15-035)

**R-15-036** MUST NOT: The C (compressed) extension is excluded, and a restricted `VerifiedOS-C` profile with it; the code-size cost is no longer accepted but recovered by the dictionary encoding (R-15-036a), which is denser and deletes the ambiguity rather than mitigating it.
· Accept: no overlapping 16-bit-aligned decodings, no decode ambiguity for binary-level proofs (R-05-035), and no variable-length fetch, mid-instruction reinterpretation, or alignment-fragment machinery anywhere in the front end.
· Trace: CJ-SAIL, CJ-TAL-SOUND · [§15](verification-maximal-os.md#r-15-036)

**R-15-036a** MUST: Code is resident, fetched, and decoded in one fixed-rate **dictionary encoding**, the platform's only instruction-fetch format: a fixed-width bundle-aligned fetch unit carrying a fixed-width header and a fixed number of fixed-width slots, each slot either an index into an immutable ISA-fixed dictionary of complete canonical instructions or part of a two-slot escape carrying one canonical 32-bit instruction verbatim, with one escape-start bit per slot in the header. Reference instantiation: a 128-bit bundle, a 16-bit header, seven 16-bit slots, widths frozen with the profile as a DSE parameter.
· Accept: no mode bit, no second decoder path, no per-object format attribute; no adaptive coding, history, or runtime-populated table; reserved header bits and indices above the realized dictionary size trap under R-15-014.
· Trace: CJ-SAIL, CJ-FORMAT · [§15](verification-maximal-os.md#r-15-036a)

**R-15-036b** IS: Decode is a pure function of a bundle's contents and a slot index, so mid-instruction reinterpretation has no representation: entering at slot *k* yields exactly what a linear decode of that bundle yields from slot *k*, slot boundaries and escape marks being properties of the bundle rather than of decode history. This is strictly stronger than the entry-point argument RVC would require.
· Accept: no carried fragment between bundles, no alignment buffer, no decoder state of any kind; two composition-time placement rules hold it, an escape never straddling a bundle boundary (the encoder padding with the format's reserved `nop` index, R-15-036j) and every control-flow target being slot-aligned, so the architectural PC stays a byte address at the reference slot width and no capability-bounds, PC-arithmetic, or `MEPCC` rule changes.
· Trace: CJ-SAIL, CJ-TAL-SOUND · [§15](verification-maximal-os.md#r-15-036b)

**R-15-036c** IS: The obligation is a finite enumeration bounded at the decoder: the dictionary is a total function `Fin N → Instr` whose codomain is exactly the admitted instruction type, so `∀ i, exec(dict i) ≡ exec(canonical i)` discharges by reflection over N constant entries and nothing above the decoder moves.
· Accept: CHERI-TAL, Cerise, CompCert, constant-time, and non-interference obligations are stated over unchanged semantics; no expansion function performing field extraction, sign extension, immediate scaling, or register remapping enters the model, and no RVC reserved, hint, or illegal-immediate case is inherited.
· Trace: CJ-SAIL, CJ-RTL-SAIL, CJ-TAL-SOUND · [§15](verification-maximal-os.md#r-15-036c)

**R-15-036d** IS: The encoding clears all five gates of the ISA-amendment test rather than being excused from it: it wins on code size and not cycles; its dictionary is selected from the composed image's own instruction histogram (R-15-031a's discipline in its strongest instance); it adds no architectural state, flush-set member, admission-test case, or mutable microarchitectural structure, the dictionary being a ROM constant and the decoder stateless; it consumes no opcode space, being a container below the instruction level, so no collision and no re-pin obligation arises; and its cost is booked as the deletion it is.
· Accept: the amendment class recorded as closed in [Evaluated Architectural Alternatives](architectural-alternatives.md) reopens for this item and resolves in favour, on the gate as written.
· Trace: CJ-SAIL, CJ-FORMAT · [§15](verification-maximal-os.md#r-15-036d)

**R-15-036e** IS: Fetch timing is fixed per bundle: same latency, a fixed maximum instruction count, flat SRAM, no I-cache, no predictor, no decompression table, no data-dependent term. What changes in §11's inputs is a unit, a block's fetch cost becoming its bundle count rather than its instruction count.
· Accept: bundle count is a static property of the frozen encoding of a frozen image; no new WCET mechanism or variance term appears.
· Trace: CJ-WCET · [§15](verification-maximal-os.md#r-15-036e)

**R-15-036f** MUST: Constant-time balancing of secret-dependent arms is an obligation over **encoded bundle count**, not instruction count, two arms of equal instruction count being able to differ in escape density.
· Accept: discharged statically at composition, the encoding being deterministic and the layout frozen; a new case for the §5 constant-time checker, not a new mechanism, and no runtime behavior varies.
· Trace: CJ-CT-SOUND, CJ-NI · [§15](verification-maximal-os.md#r-15-036f)

**R-15-036g** MUST: The encoding's scope is exactly the immutable, freeze-committed code object and reaches no data, heap, stack, IPC buffer, filesystem extent, or memory-path granule; no compressor exists on any runtime path, the encoder being a composition-time transform and the resident artifact a hardware decoder in the fetch stage; and no secret may be a compile-time or composition-time input to an encoded image, so link-time specialization MUST NOT specialize on a confidential value.
· Accept: the compress-then-encrypt ratio oracle (R-10-018) needs attacker-influenced plaintext, a secret in the same compression context, and an observable re-provokable length, and none of the three exists here: a decoder consumes a length rather than producing one, W^X with no on-device codegen (§14) leaves no path to create a compressor, and the encoded image's hash is already public in the reference integrity manifest (§9, §10). R-10-018 and R-15-199 stand unchanged; R-15-202's key containment becomes load-bearing for this requirement.
· Trace: CJ-NI, CJ-LEAK, CJ-CRYPTO-SPEC · [§15](verification-maximal-os.md#r-15-036g)

**R-15-036h** IS: The density claim is a model with a measured input: for slot width *w*, *k* slots and an *h*-bit header per bundle, and dictionary hit rate *p*, an instruction occupies one slot on a hit and two on a miss, so encoded size per instruction is (*w* + *h*/*k*)·*p* + (2*w* + 2*h*/*k*)·(1 − *p*), i.e. (*w* + *h*/*k*)·(2 − *p*) bits, which at the reference instantiation is 36.6 − 18.3*p*. This term charges an instruction for the slots it occupies and not for the slots escape packing strands, which R-15-036j books; with that term the encoding is 60% to 70% of the canonical stream at hit rates of 0.95 down to 0.80, against the 70–75% RVC would give.
· Accept: *p* is measured against the composed image, stratified by operand class per R-15-036k, and the dictionary is selected from that measurement, never quoted from the general code-compression literature; the quoted percentage range is the packing-corrected one and not the bare slot model's.
· Trace: CJ-FORMAT, CJ-MEMPLAN · [§15](verification-maximal-os.md#r-15-036h)

**R-15-036i** IS: Two costs are booked. The §10/§13 duplication-removal levers are **partly substitutive** with the encoding rather than additive, each recurring sequence they remove also removing instances the dictionary would have covered, so the two are measured composed and never multiplied; and they are nonetheless ordered first, a dictionary selected against an unstripped image being selected against the wrong histogram. The dictionary is a **permanent freeze-time commitment** of the same class as the capability format (R-15-007d): every stored executable object is in this encoding, so a later change invalidates stored code wholesale rather than costing a recompile.
· Accept: selection happens after the stripping levers land and against the composed roster; the realized size is chosen with headroom and unallocated indices trap under R-15-014.
· Trace: CJ-MEMPLAN, CJ-FORMAT · [§15](verification-maximal-os.md#r-15-036i)

**R-15-036j** IS: Slots are not fungible and R-15-036h's slot term is not the whole size: an escape is two slots and is bundle-contained, the reference slot count is odd, and a bundle standing at one free slot must be closed with a padding slot, so encoded size per instruction is (*w* + *h*/*k*)·(2 − *p* + λ), for λ the expected padding slots per instruction under the greedy in-order packing the encoder cannot depart from. λ is zero at *p* = 1 for every *k*, is bounded above by (2 − *p*)/(*k* − 1), rises monotonically as *p* falls, and at the reference instantiation reaches 1/3 at *p* = 0, where a bundle holds three escapes and one padding slot for 42.67 bits per instruction against the bare model's 36.57, 17% understated.
· Accept: the padding slot is the format's reserved `nop` index and not a reserved encoding, one dictionary index being allocated by the format rather than selected by measurement, since sequential decode reaches the padding slot and a reserved encoding would trap under R-15-014; an escape is not pair-aligned, the per-slot escape-start bit letting it begin at any slot index, and exactly two header configurations are reserved and trap, an escape-start bit on a bundle's last slot and an escape-start bit on the second slot of an escape begun at the slot before it; the packing loss is deterministic at composition, so R-15-036e and R-15-036f are unchanged and no runtime mechanism appears.
· Trace: CJ-FORMAT, CJ-MEMPLAN · [§15](verification-maximal-os.md#r-15-036j)

**R-15-036k** MUST: *p* is measured stratified by operand class and an aggregate *p* is not quotable on its own. A dictionary entry is a complete canonical instruction, immediate included (R-15-036a), so instances of one opcode differing only in an immediate are distinct entries: **site-invariant** operands recur across the image and hit, while **site-varying** operands, chiefly the PC-relative displacements of `auipcc` + `cincoffset` materialization (R-15-031b), `cjal`, and forward branches, differ at every site by construction and miss. R-15-036's *recovered, not accepted* is exactly a claim about *p* and fails below *p* = 0.804 against the optimistic RVC figure once R-15-036j's term is booked, so the fraction of the stream in the site-varying class is the density model's dominant risk factor and an aggregate hides it.
· Accept: the R-15-036h measurement reports site-varying instances separately from site-invariant ones; and the R-15-036i selection procedure states a policy for the site-varying class, recording with the freeze whether selection is by instance count alone, which admits single-use entries whenever indices remain, or by a marginal-value rule reserving indices for recurring forms, the realized dictionary size being frozen with headroom and indices above it trapping (R-15-014).
· Trace: CJ-FORMAT, CJ-MEMPLAN · [§15](verification-maximal-os.md#r-15-036k)

**R-15-036l** MUST: Whether the emitted call and global-address-materialization forms are PC-relative or **composition-time absolute** is decided at the freeze from measurement, by the discipline R-15-031a states for fusion-set membership. The option exists because the address space is single, dense, physical, and 36 bits wide with `satp` Bare (R-15-002, R-15-002a) and the image is position-fixed and freeze-committed, so a call target is a composition-time constant and an absolute target is site-invariant, every call site to one callee sharing one dictionary entry where a displacement shares none; this is `Zcmt`'s insight without `Zcmt`'s mechanism.
· Accept: the delta is re-derived at the freeze from actual generated output in R-15-067d's style, an immaterial measured delta leaving the PC-relative forms in place rather than carrying an absolute form on the argument; any absolute form admitted remains one canonical 32-bit instruction, that being what a dictionary entry is (R-15-036a), so the reachable code region its immediate can name is a parameter recorded with the encoding and targets outside it fall back to materialize-then-`cjalr`; and it adds no architectural state, no CSR, no `fence.t` flush-set member, and no target-membership structure, R-15-008's sentry semantics and R-15-072's position being unchanged.
· Trace: CJ-SAIL, CJ-FORMAT · [§15](verification-maximal-os.md#r-15-036l)

**R-15-036m** MUST NOT: `Zcmp`'s compound multi-register save and restore (`cm.push`, `cm.pop`, `cm.popret`, `cm.popretz`) is excluded in its standards-track form, and on the amendment gate rather than on its win: that form's trap model is **restartable**, a trap partway through the sequence leaving the instruction to be resumed or re-run, and what keeps partial completion out of *architectural* state is a sequencer that survives the trap, which is exactly the mutable microarchitectural structure the absence contract would newly have to police (R-15-100a) and sequencing state in a front end whose decoder R-15-036b leaves stateless.
· Accept: the sequence-redundancy class it attacks is real, the dictionary being a total `Fin N → Instr` (R-15-036c) whose codomain cannot name an idiom at any hit rate, and the dictionary has nonetheless already collected the larger half of it: a stereotyped `csc cs_i, off(csp)` at a recurring register-and-offset pair is a site-invariant entry reused at every call site in the image (R-15-036k), so a *k*-register save already costs *k* slots rather than *k* canonical instructions and naming the sequence is worth (*k* − 1) slots and not (*k* − 1) instructions. That halving is the group's own measurement rather than a discount taken here, its published baseline being RVC-compressed code where the saves are already one 16-bit encoding apiece. One platform fact cuts the other way and is recorded rather than relied on: asynchronous interrupt delivery is deleted (R-15-070), so the hardest part of specifying a compound multi-access instruction in stock RISC-V, an interrupt boundary inside the sequence, does not arise here; what remains is the capability check, which can still fault partway, and R-15-036n's form answers that without restartability.
· Trace: CJ-SAIL, CJ-FORMAT · [§15](verification-maximal-os.md#r-15-036m)

**R-15-036n** MUST: If a multi-register stack save and restore is carried at all it takes exactly one form, **all-or-nothing with a single up-front check**: one bounds and permission check on the stack capability against the whole range [`csp` − adj, `csp`), then a fixed-count access sequence no member of which can fault on its own, so architectural state is either wholly updated or wholly unchanged and no partial completion exists to resume from. Whether it is carried is decided at the freeze from measurement in R-15-067d's style, in one act with R-15-036l's call and global-address forms, R-15-067d's `bfext`/`bfins`, and any further code-size candidate the freeze weighs, against the outlined corpus R-15-036p fixes, an immaterial measured delta dropping it rather than carrying it into the frozen profile on the argument.
· Accept: the admissibility argument is R-15-007f's and not a new one, *less* capability semantics on the path rather than more, one check where the sequence performs *k*; the range checked is against the one distinguished statically-known capability on the machine, only the stack carrying `store-local` (R-15-074), and one backend emits the sequence (R-18-014a), so there is one emitter to teach. It stays one canonical 32-bit instruction, that being what a dictionary entry is (R-15-036a), and its register list and stack adjustment are site-invariant operands, so each realized pair is one entry serving every site (R-15-036k). It is deterministic in architectural state at fixed operand-value-independent latency (R-15-010 test 1), its latency being a function of the static register-list operand, which puts it on the R-15-053 list at one entry per list length in the timing-annotated model (R-15-095); it holds no state across a partition switch (test 3, so nothing joins the R-15-214 flush set), adds no admission-test case (R-15-012), mints no authority (test 4) and runs no walker (test 5), the fixed-count sequencer it does add holding nothing at any instruction boundary because the instruction is architecturally atomic and no interrupt boundary exists inside it (R-15-070). It is carried as a candidate and not as a commitment: it competes for the same custom opcode space and the same freeze measurement as the two instructions already admitted on code size (R-15-007e, R-15-067a), and with the larger half of the residual already collected the expected outcome is that it is dropped.
· Trace: CJ-SAIL, CJ-CERISE, CJ-WCET · [§15](verification-maximal-os.md#r-15-036n)

**R-15-036o** MUST: The general sequence-redundancy residual, the recurring *region* neither a dictionary index (R-15-036c) nor a named idiom (R-15-036n) can reach, is taken in **software** and no further ISA instrument is admitted for it: the CHERI-CompCert backend (R-18-014a) performs **outlining** of recurring regions into called helpers and **tail merging** of shared epilogues, which are the §13 duplication transforms (R-13-010b) given an owner, and the pass owes the ordinary secure-compilation obligation (R-05-024) rather than a new kind of one. Two scope rules bind it: outlining is **intra-compartment**, a helper and every site calling it lying in one compartment, cross-compartment sharing staying on R-13-010b's own terms of a shared service compartment or an immutable object mapped through capabilities; and only regions needing **no frame of their own** are profitable, a helper that must save and restore re-incurring the sequence the pass exists to remove.
· Accept: no instruction is admitted, no opcode consumed, no architectural state, `fence.t` flush-set member, admission-test case, or decoder state added, and nothing new for the absence contract to police, so R-15-067c's bar fails to arise rather than being cleared; the merged image carries the proof obligations R-13-010b already states, an outlining that changes a rooted symbol, capability edge, interface, or proof obligation rejecting the construction; and a helper is never placed such that a call to it crosses a compartment boundary.
· Trace: CJ-FORMAT, CJ-SECOMP, CJ-MEMPLAN · [§15](verification-maximal-os.md#r-15-036o)

**R-15-036p** MUST: R-15-036o is measured on **two axes**, bytes removed and worst-case cycles added, and is the one code-size lever that may not be settled on the byte column alone: it fails clause 6 of the pure-win gate on the cycle axis, each outlined region trading inline instructions for a call and a return whose return is an indirect branch on a machine with no return-address stack (R-15-023), and a partition's capacity being its slot width under the static cyclic executive (R-07-032, R-07-037), so WCET inflation widens a slot or does not fit rather than degrading smoothly. The measurement is **ordered before** R-15-036l's and R-15-036n's per R-15-036i, and is taken jointly with R-15-036l: for a region of *n* instructions at *m* site-invariant sites the region costs *nm* slots inline against *n* + *m* + 1 outlined under a composition-time absolute call, whose one target is one shared dictionary entry, and *n* + 2*m* + 1 under a PC-relative one, whose per-site displacement is a site-varying two-slot escape (R-15-036k), so a two-instruction region pays from four sites under the first form and never under the second.
· Accept: the corpus R-15-036l, R-15-036n, and R-15-067d are measured against is generated by a backend that already outlines, the two levers being partly substitutive in R-15-036i's sense and outlining removing instances of exactly the stereotyped prologues the multi-save covers; the byte column counts R-15-036j's padding term and not the bare slot model's; and what is recorded with the freeze is a bytes-and-cycles pair per admitted region class.
· Trace: CJ-MEMPLAN, CJ-WCET, CJ-FORMAT · [§15](verification-maximal-os.md#r-15-036p)

**R-15-036q** MUST NOT: `Zcmt` table jumps (`cm.jt`, `cm.jalt`) and their jump-vector-table (JVT) mechanism are excluded independently of the `C` encoding-space collision: no JVT CSR, runtime target-table read, or table-derived branch target exists. The read would put an address-derived memory access in the branch path and require a capability authority rule for the table, while the CSR would add architectural state, a context-switch obligation, and a `fence.t` flush-set candidate.
· Accept: R-15-036l retains the useful operand-form insight by measuring a **direct composition-time absolute target** encoded in one canonical instruction; it performs no runtime data read and adds no CSR, table, target-membership structure, or flush-set member. Forward-edge authority therefore remains the sentry R-15-008 defines and target membership remains the typed callee set R-15-072 assigns to software; no JVT-specific PCC-bounds rule is introduced.
· Trace: CJ-SAIL, CJ-ISOL, CJ-FORMAT · [§15](verification-maximal-os.md#r-15-036q)

**R-15-037** MUST NOT: `Zkr` (entropy-source CSR) is excluded: the platform has exactly one entropy root, the RoT TRNG through the verified DRBG.
· Accept: no second entropy root exists in hardware or software.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-037)

**R-15-038** MUST NOT: Virtual memory is excluded entirely: `Sv39`/`Sv48`/`Sv57` and the `Svadu`/`Svade` A/D-update extensions, with the TLB, walk-cache state, `satp` translation, and A/D machinery.
· Accept: the sole autonomous hardware walker a RISC-V core would carry is deleted with the MMU rather than exempted from test 5.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-038)

**R-15-039** MUST NOT: Scalar floating point is excluded entirely: the `F`/`D` extensions, the `f0`–`f31` register file, and the dynamic rounding-mode CSR. All floating point is vector, computed as VL=1 RVV operations on the one FPU.
· Accept: the fixed-latency-including-subnormals contract and the `FDIV`/`FSQRT` carve-out are stated once, for the vector FPU; the `f`-register file is absent from the context-switch and `fence.t` sets.
· Trace: CJ-LEAK, CJ-SAIL · [§15](verification-maximal-os.md#r-15-039)

**R-15-039a** MUST NOT: The vector element-restart CSR `vstart` is excluded: no vector instruction carries element-restart state, and a vector operation is all-or-nothing.
· Accept: no resumable-trap consumer exists on the platform, each of the four cuts being absent or fatal: asynchronous interrupt delivery is absent (R-07-038), no MMU means no mid-instruction page fault (R-15-038), a capability fault is contained and restarted (R-16-001), and a slot-boundary cut is a broken admission bound §7 restarts rather than resumes (R-07-014a). Every vector instruction's Sail definition runs its element loop from zero with no base to read and no residue to write, `vle*ff` reports a short transfer in `vl`, and `vstart` is absent from the §7 zeroize set because it is absent from the machine.
· Trace: CJ-SAIL, CJ-ISOL · [§15](verification-maximal-os.md#r-15-039a)

**R-15-040** IS: Vector-FP-without-scalar-FP is a deliberate, Sail-modeled fork of standard RVV, admissible because the platform curates its own profile and formal model.
· Accept: the fork is recorded, with its ABI cost (a soft-float-register calling convention) accepted.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-040)

**R-15-040a** IS: `vstart`-free RVV is a second deliberate, Sail-modeled fork of standard RVV, admissible on the same ground as the vector-FP-without-scalar-FP fork.
· Accept: the fork is recorded, and unlike the scalar-FP fork it books no accepted cost: no calling convention names `vstart` and no compiler emits a write to it, so the residue is hand-written RVV assembly setting an element base, which admission rejects as an undefined instruction rather than miscompiling.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-040a)

**R-15-041** MUST NOT: The scalar AES and SHA-2 round instructions (`Zkne`/`Zknd`/`Zknh`) are excluded: the vector crypto suite computes them table-free, so the constant-time contract is stated once.
· Accept: no vectorless core requires a hardware AES or SHA-2 round unit; the S-class RoT hashes SHA-3/SHAKE in plain 64-bit integer with `Zbb` rotations and delegates AEAD and sealing to the crypto core.
· Trace: CJ-LEAK · [§15](verification-maximal-os.md#r-15-041)

**R-15-042** IS: The scalar crypto bit-manipulation extensions `Zbkb`/`Zbkc`/`Zbkx` are a distinct extension and are retained for software crypto on vectorless cores.
· Accept: they appear in the adopted list; they are not an AES/SHA-2 round datapath.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-042)

**R-15-043** MUST NOT: Pointer masking (`Ssnpm`/`Smnpm`) is excluded, obviated by CHERI.
· Accept: no top-byte-ignore mechanism exists.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-043)

**R-15-044** MUST NOT: `Zicfiss`/`Zicfilp` (shadow stacks / landing pads) are excluded: CFI is a theorem for verified code and CHERI-enforced for the rest, concretely by the forward/backward-edge sentries.
· Accept: the exactness landing pads would buy is taken as the CHERI-TAL typed callee set (R-05-113) at zero silicon.
· Trace: CJ-TAL-SOUND · [§15](verification-maximal-os.md#r-15-044), [§15](verification-maximal-os.md#r-15-044-2)

**R-15-045** MUST NOT: ARM MTE-class memory tagging is excluded: its detection is probabilistic (~93% on 4-bit tags over 16-byte granules), blind to intra-granule overflow, and a statistic rather than a theorem.
· Accept: spatial safety is CHERI's deterministic byte-granular bounds; temporal safety is budgeted revocation plus Rust ownership.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-045)

**R-15-046** MUST NOT: `Zicbop`/`Zihintntl` (prefetch / non-temporal hints) and `Zawrs` (reservation-set stall) are excluded.
· Accept: no prefetch request has a software origin; `Zawrs` would stall on a reservation set that does not exist.
· Trace: CJ-WCET · [§15](verification-maximal-os.md#r-15-046)

**R-15-047** MUST NOT: `Zifencei`/`fence.i` is excluded for want of a runtime consumer: under W^X with no on-device code generation, the instruction stream is immutable once the image is wired.
· Accept: execute-only capabilities are derived over the read-only content-addressed image, never over written memory; the one instruction-memory write (measured-boot image load) is ordered by the boot sequence and a plain `fence`.
· Trace: CJ-SAIL, CJ-CERISE · [§15](verification-maximal-os.md#r-15-047)

**R-15-048** MUST NOT: The ShangMi suites (`Zks*`/`Zvks*`) and `Zimop`/`Zcmop` are excluded as dead Sail surface on a frozen ISA.
· Accept: no unused encoding vocabulary appears in the model.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-048)

**R-15-049** MUST NOT: `Smstateen` is excluded: with no less-privileged mode its bits gate nothing reachable, and what it was meant to close is already closed by the frozen profile, the access-system-registers permission, and `mstatus.VS/XS` with eager zeroize.
· Accept: the CSR bank is absent.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-049)

**R-15-050** MUST NOT: `Ssqosid` / CBQRI-shaped memory-bandwidth partitioning is excluded: bandwidth is not a quantity this platform allocates at runtime.
· Accept: no `srmcfg` CSR, no RCID/MCID request tagging, no allocation or monitoring registers; each island's ceiling is read off the TDM NoC slot schedule and the bank/macro/tier binding by the §11 admission proof.
· Trace: CJ-ISOL, CJ-WCET · [§15](verification-maximal-os.md#r-15-050)

**R-15-051** IS: Removing the monitoring counters is part of the exclusion, because per-`MCID` bandwidth-usage counters are a cross-partition activity oracle.
· Accept: no per-partition bandwidth counter is readable by any compartment.
· Trace: CJ-NI · [§15](verification-maximal-os.md#r-15-051)

**R-15-052** MUST: `misa` is read-only: no runtime ISA morphing.
· Accept: writes to `misa` have no effect.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-052)

### 15.8 Adopted extensions

**R-15-053** IS: `Zkt` + `Zvkt` is the keystone: the architectural contract that a listed instruction set runs in data-independent latency. The leakage model it fixes is a crown-jewel spec: constant-time soundness is proved against the model, and a model weaker than the silicon verifies perfectly and leaks.
· Accept: the list is (a) the single leakage model constant-time verification is stated against and (b) an RTL-against-Sail proof obligation.
· Trace: CJ-LEAK, CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-053)

**R-15-054** IS: `Zicond` (czero.eqz/nez) is adopted as the branchless constant-time select, doubly load-bearing given static-only prediction.
· Accept: it is the mandated vehicle for branchless-on-secrets hardening (R-05-067).
· Trace: CJ-LEAK · [§15](verification-maximal-os.md#r-15-054)

**R-15-055** IS: Vector crypto `Zvkned`/`Zvknhb`/`Zvkg`/`Zvbb`/`Zvbc` and scalar crypto bit-manipulation `Zbkb`/`Zbkc`/`Zbkx` are adopted: table-free AES/SHA-2/GHASH on the vector unit.
· Accept: table-free primitives have no cache-timing substrate; `Zvbb`/`Zvbc` carry baseline Keccak while the NTT rides plain RVV.
· Trace: CJ-LEAK · [§15](verification-maximal-os.md#r-15-055)

**R-15-056** IS: A frozen Keccak-f[1600] permutation is adopted as a single vector instruction, moving the constant-time obligation for the dominant post-quantum hash onto a fixed-latency hardware permutation.
· Accept: it clears all five admission tests; its correctness is a Sail invariant (fixed theta/rho/pi/chi/iota rounds, no tables, no secret-dependent control flow) riding RTL ⊑ Sail.
· Trace: CJ-SAIL, CJ-LEAK · [§15](verification-maximal-os.md#r-15-056)

**R-15-056a** MUST: The frozen Keccak fork defines **both** round counts the re-pin target defines (Keccak-*p*[1600,24] for SHA-3/SHAKE and Keccak-*p*[1600,12] for TurboSHAKE/KangarooTwelve) under an immediate selector, so that the re-pin exchanges an encoding under unchanged semantics instead of widening them.
· Accept: the frozen Sail defines both round counts; both sit on the `Zvkt` fixed-latency list (R-15-053) and are covered by R-15-058's ACVP differential oracle; no round count is admitted to the frozen model at re-pin time.
· Trace: CJ-SAIL, CJ-LEAK · [§15](verification-maximal-os.md#r-15-056a)

**R-15-057** MUST: The Keccak unit is fork-and-frozen with full Sail semantics until the RISC-V PQC Task Group's instruction (RVG-84) ratifies, then re-pinned to it.
· Accept: a re-pin obligation is recorded, as for the matrix extension and CHERI's 'Y' line.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-057)

**R-15-057a** IS: The re-pin target is recorded concretely as `Zvknhk` / `vkeccak.vi`: one vector-immediate instruction, EGW 2048, EGS 32, SEW 64 only, dependent on `Zve64x`, mandating `Zvl128b`, round count immediate-selected with unassigned values illegal, and **data-independent execution latency mandatory in the extension itself** rather than deferred to a profile.
· Accept: the frozen fork's semantics are diffed against that shape at each PQC TG milestone (specification stabilized 2026-07-30, public review opening 2026-09-22, ratification target 2026-12-31), and any divergence is booked as a re-pin delta before ratification rather than discovered after it. R-15-053's keystone contract is thereby discharged architecturally for this instruction, not only locally.
· Trace: CJ-SAIL, CJ-LEAK · [§15](verification-maximal-os.md#r-15-057a)

**R-15-058** MUST: With no Coq-native Keccak proof to import, the fixed-permutation invariant is a fresh Sail proof disciplined against FIPS 202 and the NIST ACVP test vectors as differential oracle, with `Zvbb`/`Zvbc` software Keccak retained as the portable path and the differential reference.
· Accept: the oracle enters no trust base; the software path exists on every core lacking the unit.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-058)

**R-15-059** IS: The Keccak unit is placed on the vector-bearing cores and not on the vectorless S-class RoT; a hardware Keccak block on the RoT is declined on the global trade.
· Accept: the RoT's scalar software Keccak is already constant-time on the fixed-latency core; a block would add to the least-built RTL ⊑ Sail arrow at the boot-critical root; and RVG-84 is vector-only, so no ratified scalar Keccak instruction exists for the RoT to adopt in its place: the trade decides the bespoke block, not the import.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-059)

**R-15-059a** MUST: The C-class Keccak throughput and register-pressure figures are stated at the C-class **VLEN=256**, where the 2048-bit element group is LMUL=8 and one permutation occupies the whole architectural vector register file; they are not extrapolated from the V-class VLEN=4096.
· Accept: a C-class per-permutation cost and register-pressure figure exists at LMUL=8. This is a budget entry, not an admission entry: the five-part test (R-15-010) is indifferent to register pressure, so no admission verdict turns on it.
· Trace: CJ-WCET · [§15](verification-maximal-os.md#r-15-059a)

**R-15-060** IS: `Zicboz` (cbo.zero) is adopted, making the §7 eager-zeroize discipline nearly free per aligned block and carrying the disclosure half of Write-before-Read without any per-load check.
· Accept: an unwritten slot reads a deterministic zero rather than residue.
· Trace: CJ-MEMPLAN · [§15](verification-maximal-os.md#r-15-060)

**R-15-061** MUST NOT: `Zicbom` (cache-block clean/flush/invalidate) is not adopted: with no hardware caches it has no consumer, in the kernel or in any future userspace program.
· Accept: cross-island rings need neither cache management nor a fence; their release/acquire edges are native Ztso ordering preserved by R-15-015a.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-061)

**R-15-062** IS: `fence.t` is adopted as a fork-and-frozen platform-custom instruction with full Sail semantics, specified rather than invoked: enumerated flush set, mechanized completeness classification, and padded constant cost.
· Accept: see R-15-186 through R-15-194.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-062)

**R-15-063** IS: The M-mode timer (`mtimecmp`) is adopted and `Sstc` excluded: with one privilege mode the kernel programs the machine-timer compare directly.
· Accept: no S-mode timer exists.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-063)

**R-15-064** IS: AIA/IMSIC is adopted capability-read with static routing: an MSI is a store to an interrupt file, so interrupt-send authority is a write capability in the static capability topology rather than a side table.
· Accept: no PLIC exists; interrupt authority appears in the §7/§8 topology.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-064)

**R-15-065** MUST NOT: Only the machine-level interrupt files exist, and of those only the pending array: the supervisor and guest/VS machinery, and the delivery-enable, threshold, and top-pending-selection machinery, are dead Sail surface and are excluded.
· Accept: software reads pending bits with ordinary loads; arrival is latched pending state read in the owner's slot, never a trap and never a cross-partition preemption.
· Trace: CJ-SAIL, CJ-KERNEL · [§15](verification-maximal-os.md#r-15-065)

**R-15-066** IS: The platform is MSI-only and the curated device set makes that complete: every admitted device signals by an IMSIC store through the capability-checked fabric; the timer is core-local `mtimecmp`; the only non-MSI signals are the RoT's reset and watchdog-bite lines, which are resets outside the interrupt model.
· Accept: no wired level interrupt exists on the die.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-066)

**R-15-067** IS: `Zba`/`Zbb`/`Zbs` (fixed-latency bit-manipulation) and `Zvfbfwma` (M-class bf16) are adopted.
· Accept: they appear in the frozen profile with fixed-latency dispositions.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-067)

**R-15-067a** IS: The frozen profile carries a **multi-bit bitfield extract and insert** in custom opcode space, which `Zbs`'s single-bit `bext`/`bset`/`bclr` and the standards track do not supply: `bfext rd, rs1, lsb, len` zero-extends the `len` bits at `lsb` of `rs1` into `rd`, and `bfins rd, rs1, lsb, len` deposits the low `len` bits of `rs1` into `rd` at `lsb`, leaving the rest of `rd` unchanged.
· Accept: both carry full Sail semantics and are frozen with the profile like every other encoding it allocates (R-15-014); both reuse the I-type field layout, the two 6-bit specifiers packing into the 12-bit immediate the RV64 shift-immediate instructions already carry, so the decoder gains two opcodes and no instruction format; custom opcode space is uncontended, no C extension competing for 32-bit encodings (R-15-036).
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-067a)

**R-15-067b** IS: It is admitted on **code size** rather than on cycles, and re-derived from the mix this profile emits rather than from the general RISC-V literature: the extract collapses a shift-and-mask pair into one instruction and the insert collapses the four-to-six-instruction mask-materialize, clear, shift, and merge sequence into one.
· Accept: the two largest bodies of generated code on the machine are bitfield access in a loop, so the lowering is not a peephole: the bit-aligned wire formats, where Narcissus derives the encoder as well as the decoder from one format description and so gives the insert form a first-class consumer (R-05-042, R-05-048, R-12-040), and the generated MMIO register accessors, which are the whole device-driver surface (R-05-083). The bytes are spent against the absent I-cache (R-15-164), the 33-43% no-C penalty (R-15-036), and the §15 SRAM capacity budget. A cycle term survives on the insert form, whose dependent chain is longer than adjacent-pair fusion collapses; it is not what admits the instruction and is not scored.
· Trace: CJ-SAIL, CJ-FORMAT · [§15](verification-maximal-os.md#r-15-067b)

**R-15-067c** IS: It clears the five-part admission test as the adopted bit-manipulation extensions do, and adds nothing structural: no architectural state, no `fence.t` flush-set member, no admission-test case, and no mutable microarchitectural structure the absence contract would newly police.
· Accept: deterministic in architectural state (R-15-010 test 1) at fixed operand-value-independent latency, which puts it on the R-15-053 list and gives it one entry in the timing-annotated model (R-15-095); holding no state across a partition switch (test 3, so nothing joins the R-15-214 flush set), minting no authority (test 4), running no walker (test 5). What it adds beyond that is one instruction-selection rule per production backend (R-18-014a). Being bespoke it records no standards-track re-pin target, no general bitfield proposal existing to re-pin to. The short-dependent-ALU-chain fusion class (R-15-031) is **narrowed and not deleted**: the sequence stays legal, stays emitted where the field specifiers are not compile-time constants, and stays in the frozen set, R-15-031c pricing a retained pair at zero.
· Trace: CJ-SAIL, CJ-WCET · [§15](verification-maximal-os.md#r-15-067c)

**R-15-067d** MUST: The field-specifier form, whether the insert form is carried, and whether the pair is carried at all are re-derived at the freeze from actual generated output on at least the UPER RRC and IEI/TLV descriptors and the generated register accessors, by the discipline R-15-031a states for fusion-set membership, and recorded with the freeze (R-15-014).
· Accept: the instruction is admitted on an image-size delta, which is a claim about emitted code rather than about the literature, so the measurement is what decides it: a measured delta immaterial against the §15 capacity budget drops the instruction at the freeze rather than carrying it into the frozen profile on the argument alone. Whether the two 6-bit immediates earn their encoding bits, or a register-specified field suffices, is that same recorded selection.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-067d)

**R-15-067e** IS: The one **further code-size candidate** R-15-036n's single freeze act weighs is named rather than left open: a `csetbounds` taking a large immediate length, in CHERIoT's form. It is carried as a candidate and not as a commitment, decided by that measurement against R-15-036p's outlined corpus, and the expected outcome is that it is dropped.
· Accept: the consumer here is not the upstream one, allocation being composition-time, so a narrowing the backend emits takes its length from a type rather than from a request (R-15-007k), which makes the length a composition-time constant materialized immediately before the narrow. What that pair costs is halved by the encoding for R-15-036m's reason: a site-invariant constant materialization is one dictionary entry reused at every site narrowing to that length (R-15-036k), so the pair is already two slots and the immediate form collects one 16-bit slot rather than four bytes. It competes for the same custom opcode space and the same measurement as the instructions already admitted on code size (R-15-007e, R-15-067a), and an immaterial measured delta drops it rather than carrying it into the frozen profile on the argument.
· Trace: CJ-SAIL, CJ-FORMAT · [§15](verification-maximal-os.md#r-15-067e)

### 15.9 CHERI capability-ISA features

**R-15-068** IS: Capability jump-and-link carries the sentry unseal-and-seal semantics, so there is no separate call gate: it unseals a forward-edge sentry into the executing PCC and writes the return address already sealed as a backward-edge sentry.
· Accept: a single instruction is the hardware root of domain entry and of forward/backward-edge CFI, needing no trampoline or software dispatch.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-068)

**R-15-069** IS: The cross-compartment switcher is a specialization layered on that instruction, not a separate mechanism.
· Accept: its entry point is itself a sentry entered by the same instruction.
· Trace: CJ-KERNEL · [§15](verification-maximal-os.md#r-15-069)

**R-15-069a** IS: The frozen profile carries a **masked register clear** in custom opcode space: `cclear h, mask` clears the sixteen registers `mask` selects within the half `h` selects, writing each to the all-zeroes granule that decodes as untagged NULL, so two of them clear the merged file (R-15-007i). The compartment switch is what it exists for: the partition switch is covered structurally by the total restore (R-07-015, R-15-214), and the cross-compartment switcher's scrub of some two dozen registers per call and per return is covered by nothing.
· Accept: it carries full Sail semantics and is frozen with the profile like every other encoding it allocates (R-15-014); it reuses the **S-type field layout unchanged**, the sixteen mask bits and the half selector packing into the fields a store already carries, so the decoder gains one opcode and no instruction format and no destination register is named, the mask naming the destinations; the `x0` bit has the effect every other write to `x0` has, which is none; custom opcode space is uncontended, no C extension competing for 32-bit encodings (R-15-036).
· Trace: CJ-SAIL, CJ-ISOL · [§15](verification-maximal-os.md#r-15-069a)

**R-15-069b** IS: It is admitted on **cycles** where R-15-007e and R-15-067a are admitted on bytes, and the distinction is what makes it a separate decision from either: the dictionary encoding is a byte instrument, so the clears are already site-invariant dictionary slots (R-15-036k) and the image cost is collected before any instruction is added, while the issue cost is not: two dozen slots still issue two dozen times on the platform's only inter-compartment path (R-04-004), in code §11 charges to every cross-compartment call. What it removes it removes from the **bound** and not from the mean, the clear being unconditional and its worst case therefore its every case.
· Accept: deterministic in architectural state (R-15-010 test 1) at a latency independent of operand values and of the mask's population, which puts it on the R-15-053 list with one entry in the timing-annotated model (R-15-095); holding no state across a partition switch (test 3, so nothing joins the R-15-214 flush set); minting no authority (test 4), it being the one instruction on the machine that can only destroy authority, so monotonicity is trivial rather than argued; running no walker (test 5). It adds one instruction-selection rule in the switcher's emitter (R-18-014a) and nothing structural, being a masked synchronous clear on the register file rather than sixteen write ports, on the clear line a flop-based file already carries for reset. Its recorded re-pin target is **`ZcheriSanitary`**, research-stage today, the obligation opening if it ratifies; ISAv9's deletion of `CClearRegs` is not inherited, that deletion being of the split-file variants a merged register file makes meaningless and therefore a fact about the register file rather than about the need.
· Trace: CJ-SAIL, CJ-WCET, CJ-ISOL · [§15](verification-maximal-os.md#r-15-069b)

**R-15-069c** MUST NOT: The CHERIoT stack high-water-mark CSRs `mshwm`/`mshwmb` are excluded, and on the currency rather than on the mechanism: they buy a switch that zeroizes only the stack the callee touched, which is a saving in the **mean**, and the switcher's cost enters the §11 budget as a worst case that a callee using the whole of the stack its capability bounds already attains.
· Accept: spending the saving rather than padding it is worse than not having it, the switch's latency becoming a function of the callee's call-graph depth, which is a cross-domain timing channel of the class R-07-014 deletes lazy vector-unit switching for, with the caller as observer and the caller the party the switch protects. The cost side is two CSRs against the closed table R-15-001b enumerates (R-15-014), two more locations the total restore must name (R-07-015), and an architectural write on the store path accumulating a per-compartment usage figure that survives into the next compartment unless something clears it. The eager zeroize is unchanged and what makes it cheap is already carried at fixed latency (R-15-060, R-15-182); the other half of the same upstream optimization, the STKZ stack-zeroing engine, is refused separately under admission test 5 (R-08-009).
· Trace: CJ-NI, CJ-WCET · [§15](verification-maximal-os.md#r-15-069c)

**R-15-070** MUST NOT: Interrupt-state sentries (`enabled`/`disabled`/`inherit`) are excluded, the one CHERIoT capability feature the profile declines: with asynchronous interrupt delivery deleted, the three sentry types collapse to the one plain sealed entry.
· Accept: Sail loses the variant otype space and the interrupt-state capture-and-restore semantics; RTL loses the interrupt-state field, decode, and auto-restore path; the CHERI-TAL loses the interrupt-state index on sentry types; §8/§11 lose the bounded interrupt-disabled-window allow-list.
· Trace: CJ-SAIL, CJ-TAL-SOUND · [§15](verification-maximal-os.md#r-15-070)

**R-15-071** IS: The forward/backward-edge sentry split is the platform's coarse-grained CFI: a return capability may target only a return site, so a forged or replayed return address traps.
· Accept: the split survives the interrupt-state deletion, being a property of edge direction.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-071)

**R-15-072** IS: A sentry deliberately does not decide target *membership*; that residual is closed in software by the typed callee set, not in the ISA.
· Accept: no landing-pad surface is modeled in Sail or refined in RTL.
· Trace: CJ-TAL-SOUND · [§15](verification-maximal-os.md#r-15-072)

**R-15-073** IS: Capability trap registers `MTCC`/`MEPCC`/`MTDC` are adopted, reachable only with the access-system-registers permission.
· Accept: the single-Machine-mode trap path is expressible; a trap-data capability bootstraps the handler's authority on entry.
· Trace: CJ-KERNEL · [§15](verification-maximal-os.md#r-15-073)

**R-15-073a** IS: Capability exceptions report through the **existing trap-value CSR**: `mcause` and `mtval` are present, a CHERI capability violation raises one CHERI cause code in `mcause`, and `mtval` carries the violation's detail, being the capability cause type and the register or field that raised it. No bespoke CHERI cause or trap-value bank exists.
· Accept: the profile's CSR bank carries `mcause` and `mtval` as present rows citing this entry, and the extraction defect that booked them as undecided closes with it: R-07-022 and R-15-073 specify the trap path entirely in capability terms and name no cause register, which leaves a handler with a trap and no cause. The CHERI cause codes are ISAv9's and are frozen with the profile (R-15-014), so the encoding is not left to an implementation. Reusing one trap-value register rather than adding a bank is both the standards-track answer (ISAv8 settled it, ISAv9 keeps it, RVY's `Xtval2` confirms it from the other side) and the cheaper one.
· Trace: CJ-SAIL, CJ-KERNEL · [§15](verification-maximal-os.md#r-15-073a)

**R-15-073b** MUST NOT: No second saved-PC bank exists. `ErrorEPCC` (the MIPS-lineage CHERI register modeled on `ErrorEPC`) and `Smrnmi`'s `mnscratch`/`mnepc`/`mncause`/`mnstatus` are not admitted, and no architectural state saves a program counter, a capability, or a cause for a trap taken while the trap path is live.
· Accept: **a saved program counter exists to be returned to, and nothing returns.** The kernel is entered for exactly two reasons and both are the trap path (R-07-021), so a trap taken between that entry and the `mret` that leaves it is a **synchronous fault in kernel code** (a capability violation under R-15-073a, a misaligned access under R-15-084, or an unallocated encoding under R-15-014), which refutes the kernel proof rather than presenting a recovery arm, and whose disposition is the crash-only fail-stop and supervised restart the rest of the system takes (R-12-001, R-16-005). The bank costs a capability-width register and its tag, one more location the total restore must name (R-07-015) and the flush-set argument quantifies over (R-15-214), one Sail case, and one RTL location, against a resumption that does not happen.
· Accept: **the asynchronous classes the bank exists for are already off the trap path, so this is a decline rather than a hedge declined.** `ErrorEPC` and `mnepc` bank reset, NMI, machine check, and cache error; the platform is MSI-only with the timer core-local and its only non-MSI signals the RoT's reset and watchdog-bite lines, which are resets outside the interrupt model (R-07-045, R-15-066); an uncorrectable ECC or tag-integrity event is a fail-stop sentinel event and not a trap into `MTCC` (R-15-204); and the slot-boundary timer, the machine's sole asynchronous trap, is unmaskable by software precisely because it needs no enable bit, the trap path suppressing delivery and the timer not re-arming until the handler reprograms `mtimecmp` (R-07-040). The nesting the bank survives is not a state this machine reaches.
· Trace: CJ-SAIL, CJ-KERNEL · [§15](verification-maximal-os.md#r-15-073b)

**R-15-073c** MUST: A trap taken while the trap path is live does not vector to `MTCC` and does not write `MEPCC`, `mcause`, or `mtval`; the core latches a fail-stop to the RoT, taking the watchdog bite and the boot-counted recovery (R-16-005, R-16-007). The condition is **one bit of trap-path state and no software-visible field**: set when a trap installs `MTCC`, cleared by the `mret`, never read or written by software, so `mstatus` carries no `Smdbltrp` `MDT` bit and the CSR enumeration of R-15-001b is unchanged.
· Accept: **this is `Smdbltrp`'s disposition without `Smdbltrp`'s CSR field, and not writing is the half of `ErrorEPCC` worth keeping.** The first fault's report survives intact rather than being overwritten by the second, which is the post-mortem the bank was buying, readable in the development lifecycle state where the Debug Module is live (R-15-078, R-15-079), at the cost of an omitted write rather than a register.
· Fail-closed: a trap taken while the trap path is live stops the machine rather than being re-entered on a context it has already destroyed, composed at R-17-030n with the rest of the detector class; the cost is the running state, and the provocation needing no software access is the residual SEU that changes kernel control flow past ECC (R-15-197, R-15-204).
· Accept: **the bit clears the five admission tests by absence rather than by argument** (R-15-010): a deterministic function of architectural state in one Sail clause (1), at no operand-dependent latency (2), carrying nothing from one partition to the next, being clear at every partition's first instruction by construction (3), granting no authority (4), and running nothing (5). And it adds no WCET term, the path it takes ending execution rather than returning to it (R-07-043).
· Trace: CJ-SAIL, CJ-KERNEL · [§15](verification-maximal-os.md#r-15-073c)

**R-15-074** MUST: Local/global capabilities and the `store-local` permission (with `load-global`/`load-mutable` transitivity) are adopted: a local capability may be stored only through a capability bearing `store-local`, which by construction only the stack carries.
· Accept: a buffer handed to an untrusted codec cannot be retained past the call; the convention that authority cannot cross into long-lived shared memory is an ISA-enforced invariant.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-074)

### 15.10 No PMP

**R-15-075** MUST NOT: Physical memory protection is not implemented, and `Smepmp` is dropped with it: CHERI is the sole memory-protection mechanism.
· Accept: no PMP region registers exist; the three roles a locked-PMP backstop would serve (immutable text/W^X, per-core physical-partition bound, crown-jewel secret fencing) each map onto a named CHERI or crypto-core mechanism.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-075)

**R-15-076** IS: The CHERI-disjoint failure domain PMP uniquely offered is deliberately forgone; the hedge is CHERI's own formal verification, and the concentration is booked honestly in §17.
· Accept: the residual is the RTL ⊑ Sail arrow plus a Coq-native restatement of reachable-capability monotonicity over the CHERI-RISC-V Sail model.
· Trace: CJ-CERISE, CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-076)

### 15.11 Deleted counters and lifecycle-gated debug

**R-15-077** MUST NOT: `Zicntr` and `Zihpm` are implemented in no lifecycle state: their user and Machine counter CSRs, event selectors, inhibit state, and counter-read CHERI permission are absent.
· Accept: `mtime`/`mtimecmp` remains the kernel-owned scheduling device, and lifecycle-gated Debug Module trace supplies development WCET calibration; Sail and RTL contain no architectural performance-counter semantics or production timing oracle.
· Trace: CJ-NI · [§15](verification-maximal-os.md#r-15-077)

**R-15-078** MUST: The RISC-V Debug Module exists in silicon but is lifecycle-fused at the hardware level, never merely software-gated: in the production lifecycle state the RoT's OTP fuse holds its clock and reset gated off and its fabric port electrically quiesced.
· Accept: *no DM transaction reaches the fabric in the production state* is a stated RTL ⊑ Sail obligation, so the Sail model carries the gate rather than a model of the debugger; the state the fuse holds is monotone (R-09-033), so production is not a mode the device can be talked back out of.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-078)

**R-15-079** MUST: In development and RMA lifecycle states, DM entry is an RoT challenge-response (ML-DSA-signed, serial-bound), the RoT key hierarchy diversifies by lifecycle state, and moving a fielded device to a debuggable state crypto-erases first; trace rides the same fuse.
· Accept: a debuggable part cannot unseal production-sealed material, and the move that makes a fielded part debuggable is RMA, which is forward and terminal (R-09-035).
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-079)

### 15.12 Implementation timing contracts

**R-15-080** MUST: Integer DIV/REM completes at fixed worst-case latency always; early-out-on-small-operands dividers are forbidden.
· Accept: the timing-annotated model carries one latency; no operand-dependent divide path exists.
· Trace: CJ-LEAK, CJ-WCET · [§15](verification-maximal-os.md#r-15-080)

**R-15-081** MUST: The vector FPU is fixed-latency across all operand classes including subnormals.
· Accept: no subnormal slow path exists; the contract is stated once, for the one FP datapath.
· Trace: CJ-LEAK · [§15](verification-maximal-os.md#r-15-081)

**R-15-082** MUST: `vfdiv`/`vfsqrt` are either fixed-latency or off the constant-time list, the latter admissible only because the flow discipline proves no secret-labeled operand reaches them.
· Accept: the discharge is a proof obligation, not a self-declaration (R-15-011).
· Trace: CJ-LEAK, CJ-NI · [§15](verification-maximal-os.md#r-15-082)

**R-15-083** MUST: Floating-point rounding is static: the mode is encoded per-instruction (default round-to-nearest-even), never the dynamic `frm` CSR.
· Accept: no mutable rounding-mode state context-switches or joins the `fence.t` set.
· Trace: CJ-SAIL, CJ-ISOL · [§15](verification-maximal-os.md#r-15-083)

**R-15-084** MUST: Misaligned accesses trap and are never split in hardware.
· Accept: no line-crossing address-dependent latency exists; the granule-alignment rule is enforced rather than hoped.
· Trace: CJ-WCET · [§15](verification-maximal-os.md#r-15-084)

**R-15-085** MUST: `Zvkt`-listed vector operations execute in mask-independent time: an implementation may not skip memory accesses or cycles for masked-off elements.
· Accept: the mask is not observable through timing or memory traffic.
· Trace: CJ-LEAK · [§15](verification-maximal-os.md#r-15-085)

**R-15-085a** MUST: Vector memory operations split by whether their element-address pattern is fixed at compile time. Unit-stride, segment, and whole-register accesses are on the data-independent-timing list, their bank sequence being a function of the element width and a granule-aligned base alone. Indexed accesses (`vluxei`/`vloxei`/`vsuxei`/`vsoxei`) and runtime-strided accesses (`vlse`/`vsse`) are off it, their latency being an explicit function of how the element addresses distribute over the SRAM banks, and are admissible only because the flow discipline proves no secret-labeled value reaches an element address.
· Accept: the discharge is R-05-070's rejection of a secret-labeled value reaching a memory address, applied per element at the point the capability check already lands (R-15-115), under R-15-011's rule that a bare exclusion is not a pass; the vector crypto is table-free and the Keccak unit indexes nothing (R-15-055, R-15-056), so no admitted crypto kernel needs the excluded form, which is the `vfdiv`/`vfsqrt` discharge (R-15-082) read on the memory path.
· Trace: CJ-LEAK, CJ-NI · [§15](verification-maximal-os.md#r-15-085a)

**R-15-085b** MUST: The timing-annotated model carries the fully-conflicted bound for an off-list vector access, every element resolving to one bank, so an operation whose observed latency varies still has one sound latency in the WCET table.
· Accept: schedulability is proved against the conflicted bound and never against a typical pattern; because the schedule is time-triggered and the unspent remainder is burned rather than donated (R-07-036), the variation stays inside the issuing partition's own slot and reaches no observer across a partition boundary, which is the scope the flow obligation of R-15-085a has to cover.
· Trace: CJ-WCET, CJ-ISOL · [§15](verification-maximal-os.md#r-15-085b)

**R-15-086** MUST: Branch-resolution latency is a fixed function of the static rule, so fetch timing depends on architectural state only.
· Accept: no dynamic predictor state contributes to fetch timing.
· Trace: CJ-WCET · [§15](verification-maximal-os.md#r-15-086)

**R-15-087** MUST: `Zaamo` and `Zabha` AMOs complete as single bounded memory transactions with data-independent latency at the SRAM bank's serialization point, which is the whole of what a coherence point would otherwise name.
· Accept: no early-out on operand values; no reservation state or 128-bit CAS coherence-point stall contributes to timing.
· Trace: CJ-WCET, CJ-LEAK · [§15](verification-maximal-os.md#r-15-087)

**R-15-088** MUST: The store buffer's drain at a partition switch is data-independent because it is paid as the `fence.t` padded constant, not as a second budget term beside it.
· Accept: the partition-switch budget counts the drain once (R-15-193).
· Trace: CJ-WCET, CJ-ISOL · [§15](verification-maximal-os.md#r-15-088)

### 15.13 RTL-against-Sail refinement

**R-15-089** IS: Every obligation stated against the microarchitecture is discharged against a named vehicle, and the obligations split by whether the Sail model can express them at all.
· Accept: refinement obligations (`Zkt`/`Zvkt`, Ztso ordering, static-only fetch timing, fixed-latency DIV/FPU/AMO) ride RTL ⊑ Sail; absence obligations ride the separate contract and are not a rung on the ladder.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-089)

**R-15-090** IS: Sail-generated SystemVerilog plus commercial formal-equivalence verification is the day-one bring-up gate for imported cores: unbounded observational-correctness evidence at near-zero method cost, with the FEV tool trusted so it remains evidence, not the Coq close.
· Accept: every imported or modified core (CHERI-CVA6 front end, Ara, Gemmini) has an evidence path from first bring-up.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-090)

**R-15-091** MUST: Kami/Kôika Coq refinement is the primary closing vehicle, landing in the same single prover and adding no checker to the trust base.
· Accept: the refinement theorem is a Coq development.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-091)

**R-15-092** MUST: The net-new blocks with no legacy RTL to preserve (the capability- and tag-carrying DMA fabric, the TDM NoC, the fixed-function sequencers) are authored directly in Kôika/Kami, from which SystemVerilog is generated for synthesis.
· Accept: their RTL ⊑ Sail is discharged against the source the hardware is built from; the generated SystemVerilog is not a semantic anchor.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-092)

**R-15-093** IS: Proof over the shipped SystemVerilog is a deferred, budget-gated rung: it would introduce a Verilog-semantics anchor, admitted only if it retires the Sail-reference-plus-FEV evidence step it replaces.
· Accept: the anchor-budget conditions (R-05-020) govern its admission.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-093)

**R-15-094** IS: riscv-formal/rvfi is bounded-depth evidence and the cheapest bring-up gate; Isla is the bridge turning the frozen Sail model into concrete obligations and litmus tests, including the Ztso concurrency litmus.
· Accept: neither is the ground of any refinement claim.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-094)

**R-15-095** MUST: The timing and ordering obligations are hyperproperties stated and checked against a timing-annotated Sail model, not the bare functional one.
· Accept: `Zkt`/`Zvkt` is 2-safety, Ztso is an ordering property, static-prediction fetch timing is architectural-state-only; each is stated against the annotated model.
· Trace: CJ-RTL-SAIL, CJ-LEAK · [§15](verification-maximal-os.md#r-15-095)

**R-15-096** IS: That same timing-annotated model is the low-level input to WCET derivation, so sound per-instruction timing is a corollary of RTL ⊑ Sail rather than a separate analysis.
· Accept: the residual fetch and memory terms are a reproducible function of the signed deterministic-layout image, the flat SRAM, the TDM NoC schedule, and the WCET-exact scratchpads.
· Trace: CJ-WCET, CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-096)

**R-15-097** IS: Honest scope: no RTL ⊑ Sail artifact exists today for a full application-class core, let alone the heterogeneous topology; this is the least-built layer of the entire stack.
· Accept: §18 stages it per class; §17 books the residuals; below this arrow, fabricated silicon versus verified RTL remains the fab residual.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-097)

### 15.14 The microarchitectural absence contract

**R-15-098** IS: Sail models architectural state, so RTL ⊑ Sail cannot state, let alone discharge, *there is no branch predictor*; the two registers are therefore separated.
· Accept: ISA-visible removals are absences in the frozen Sail model and owe nothing further; microarchitectural removals owe the absence contract.
· Trace: CJ-SAIL, CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-098)

**R-15-099** IS: The ISA-visible removals are the MMU and its Sv39 walker, PMP, the S/U rings, `C`, `Zifencei`, `Zalrsc`/`Zacas`, scalar F/D, the dynamic `frm` state, the vector element-restart state `vstart` (R-15-039a), and asynchronous interrupt delivery.
· Accept: an RTL implementing any of them fails ordinary refinement.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-099)

**R-15-100** IS: The microarchitectural removals owed the absence contract are speculation, out-of-order issue, every dynamic direction/target/return predictor, prefetchers, SMT, the I- and D-caches and the tag cache, and DVFS/frequency control.
· Accept: each appears in the absence-contract register (the artifact required by R-15-100a) with a discharge.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-100)

**R-15-100a** MUST: The absence-contract register exists as a single enumerated artifact, [absence-contract.md](absence-contract.md), carrying one row per claimed absence with its ground, the netlist evidence sought, and its discharge form. Like the frozen profile it is a *derived view*: it states no obligation of its own, cites the governing requirement for every row, and is defective, never authoritative, where it disagrees with this register.
· Accept: the artifact exists, records both discharge forms (in-prover structural predicate for Kôika/Kami blocks per R-15-102; netlist state-enumeration plus synthesis-configuration provenance for imported cores per R-15-103), carries the table-freeness rule (R-15-104) and the `fence.t` four-class completeness map (R-15-217), and its agreement with this register is mechanically checked in both directions by `tools/check.ps1`. Because R-18-012 makes this the one part of the least-built layer buildable before that layer exists, the artifact is a day-one deliverable under R-18-003b(ii) and an absent one blocks it.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-100a)

**R-15-101** IS: The semantic content of the removals is one hyperproperty: cycle-level timing and memory traffic are a function of the instruction stream and architectural state alone, never of prior execution history.
· Accept: the contract discharges a sufficient structural condition for it (that the enumerated structures and their state elements do not exist) rather than proving it over a cycle-accurate model.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-101)

**R-15-102** MUST: For Kôika/Kami-authored blocks, absence is a structural predicate over the Coq term, checked in the same prover as the refinement and adding no semantic anchor.
· Accept: the predicate is over an existing artifact, not a new semantics.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-102)

**R-15-103** MUST: For imported SystemVerilog cores, absence is a state-enumeration and structural check over the elaborated netlist plus synthesis-configuration provenance, and is stated honestly as a structural audit, not a theorem.
· Accept: the check covers predictor arrays, reorder buffer and reservation stations, prefetch engine, cache data/tag/valid arrays, a second hardware thread context, and PLL/DVFS control paths.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-103)

**R-15-104** MUST: The prefetcher/fetch-buffer boundary is decided by table-freeness, not by size or run-ahead depth: a state element in the fetch path whose write data depends on a prior *execution* is a prefetcher and fails the contract; one whose contents are a function of the fetched stream is fetch pipelining and passes.
· Accept: the audit is a table search, not a judgment call.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-104)

**R-15-105** IS: Every microarchitectural removal converts a correctness obligation into an absence obligation, moving work out of the least-built arrow; this is the argument *for* the removals, not merely their consequence.
· Accept: deletion is preferred to partitioning even where partitioning would suffice.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-105)

**R-15-106** MUST: The `fence.t` completeness classification is discharged by the absence contract rather than by the refinement, since completeness is the claim that no unenumerated state exists, which the model cannot see.
· Accept: the temporal fence's residual scope collapses to pipeline drain, which is class (d) of R-15-217's four-class map, *stream-determined pipeline state*, rather than an unmapped remainder.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-106)

**R-15-107** IS: The absence contract is a distinct §18 bring-up gate and a named §17 residual: the one obligation class whose imported-core half closes on audit rather than on proof.
· Accept: both entries exist (R-18-012 is the §18 gate and R-17-040 the §17 residual) and both are recorded in the absence-contract register's disposition (R-15-100a).
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-107)

### 15.15 Parameter selection

**R-15-108** MUST: The frozen microarchitectural parameters are selected by a composition-time, pre-silicon design-space exploration whose utility function carries proof simplicity as a first-class term alongside performance, area, power, and WCET.
· Accept: the parameter set is VLEN per class, issue width and pipeline depth, SRAM bank/macro/tier-to-island assignment, scratchpad sizes, and the TDM-NoC schedule; there is no cache, way-colouring, or integrity-tree parameter to choose.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-108)

**R-15-109** MUST: The five-part admission test and the §8 non-interference / §11 WCET obligations are hard constraints on the search, not objectives.
· Accept: every candidate satisfies them to be admissible; the search optimizes strictly within the proven-safe envelope and widens no trust base.
· Trace: CJ-NI, CJ-WCET · [§15](verification-maximal-os.md#r-15-109)

**R-15-110** IS: The exploration tool is untrusted evidence-producing machinery; the proof-simplicity term is a proxy, so a poor proxy costs search quality, never soundness.
· Accept: its output is a single frozen, Sail-modeled, admission-checked configuration whose choice the per-class RTL ⊑ Sail proof then discharges.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-110)

### 15.16 Heterogeneous single-die topology

**R-15-111** MUST: All compute is on one die, under one base ISA, one kernel binary, and one parameterized formal model.
· Accept: no die-to-die link exists anywhere in the machine (R-15-146).
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-111)

**R-15-112** IS: Scalar front ends are one shared microarchitecture (CVA6-class, modified to static-only prediction) across all classes, so kernel-path WCET is a single analysis.
· Accept: one front-end model in the timing-annotated Sail.
· Trace: CJ-WCET · [§15](verification-maximal-os.md#r-15-112)

**R-15-113** IS: The core classes are C-class (control and application, VLEN=256), V-class (long-vector, VLEN=4096, 8 lanes, with a radio-pinned pair), M-class (systolic GEMM plus VLEN=1024 and a software-managed scratchpad), S-class (scalar sentinel), and the RoT (OpenTitan-class scalar RV64+CHERI in its own clock/power island). Counts are composition parameters, not architecture.
· Accept: every other section names a class and refers here; disjointness is machine-checked as in §7.
· Trace: CJ-SAIL, CJ-KERNEL · [§15](verification-maximal-os.md#r-15-113)

**R-15-114** IS: Pinning is an admission outcome, not a favour granted per device: a device server whose deadline-driven poll cadence would spend an inadmissible fraction of a core on partition switching is pinned instead of slotted, at which point its switch cost is deleted rather than budgeted.
· Accept: the radio-pinned V-class pair and the S-class sentinel are the current members of that class; any further server failing the §11 switch-duty inequality takes a core of its class by the same rule.
· Trace: CJ-WCET · [§15](verification-maximal-os.md#r-15-114)

**R-15-115** MUST NOT: V-class is vector, not fixed-function graphics and not SIMT: no rasterizer, no texture units, no ROPs, no command processor, and no hardware warp scheduler.
· Accept: CHERI stays a single-front-end problem; vector data carries no tags and checks land on scalar-issued vector memory ops, per-element for gather/scatter.
· Trace: CJ-CERISE, CJ-WCET · [§15](verification-maximal-os.md#r-15-115)

**R-15-115a** MUST: A vector store **clears the capability validity tag of every granule it overwrites**, partial-granule writes included.
· Accept: R-15-115's *vector data carries no tags* is a statement about what a vector store writes, not about the tag of what it replaces, and without this clause a vector store reads as leaving a stale tag standing over data it has overwritten, which is a forgery primitive rather than a residue. Every vector store's Sail definition carries the tag clear over the granules its access covers, so it is a defined architectural result and not an implementation choice; it adds no architectural state and no admission-test case (R-15-012), the tag write being the one a scalar store already performs.
· Trace: CJ-SAIL, CJ-CERISE · [§15](verification-maximal-os.md#r-15-115a)

**R-15-115b** MUST: Only an **active** element of a vector memory operation raises a capability exception. Where R-15-085's mask-independence contract requires the accesses and cycles of masked-off elements to be performed regardless, their capability checks are performed with them at the cost an active element's check takes, and the result is discarded rather than raised; a masked-off element whose check fails takes the bank cycle its access would have taken as a padded access presenting no address.
· Accept: the two contracts compose as *check every element, fault only on the active ones*, which is the only realization satisfying both rather than a compromise between them: skipping a masked-off element's check hands back cycles the timing contract holds and so leaks the mask through timing and memory traffic, while raising its fault leaks the mask through the trap and departs from the element-wise semantics R-15-115 defines the check against. Padding the failing masked-off access rather than issuing it keeps an address the domain holds no authority for off the fabric at no timing cost, an on-list access's bank sequence being a function of element width and a granule-aligned base alone (R-15-085a).
· Trace: CJ-SAIL, CJ-LEAK · [§15](verification-maximal-os.md#r-15-115b)

**R-15-116** MUST: The bespoke matrix extension is admitted only where it clears an order-of-magnitude sustained dense-GEMM margin (about 8–10× throughput, wider per-watt) over the same GEMM expressed as RVV on the M-class's own VLEN=1024 unit.
· Accept: dense int8/bf16 inference clears the bar and the extension is kept; small, irregular, or low-reuse GEMM does not and folds onto the vector unit.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-116)

**R-15-117** MUST: De-quantization and block-scale (microscaling) application are software on the M-class vector unit, not hardware: no ACE-style block-scale register and no Arm-FPMR-style scale field enters the frozen matrix ISA.
· Accept: the array consumes int8/bf16 only; the forgone native FP8 systolic density is accepted.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-117)

**R-15-118** MUST: The coprocessor line: every byte the matrix unit moves is core-issued with explicit capability operands: no independent DMA mastership, no translation context, no firmware. An accelerator needing any of those is a device.
· Accept: the matrix unit holds no DMA capability of its own.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-118)

**R-15-119** IS: FEC units are LDPC and polar decoders only (the 5G NR and 6G channel-code families) as fixed-geometry arithmetic with deterministic iteration bounds, core-issued capability-operand movement, and no firmware.
· Accept: the legacy turbo and convolutional decoders are absent from the die; belief propagation on a fixed graph is grammar-free arithmetic and does not breach the codec-block ban.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-119)

**R-15-120** IS: The RoT is integrated on-die; the cost is concentration (one mask set carries the RoT and everything it measures).
· Accept: the residual is booked in §17.
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-120)

### 15.17 Radio subsystem

**R-15-121** IS: The on-die transceiver is a register-slave datapath: direct-RF or zero-IF ADC/DAC chains with a digital front end, configured via capability-gated MMIO, streaming I/Q through capability-bounded DMA windows, with no instruction fetch and no sequencer firmware.
· Accept: no writable program exists in the transceiver.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-121)

**R-15-122** IS: One fixed-function link-layer timing sequencer is admitted for the sub-slot turnaround (BLE `T_IFS`, 802.11 SIFS, 802.15.4 turnaround): a hardware packet-end event starts a fixed timer that drives the RX/TX switch and gates a software-prepared buffer at the deadline.
· Accept: the buffer, channel/frequency word, and event schedule are loaded by the §12 control plane before the event, so the block makes no protocol decision; it carries no instruction fetch, no writable program, and no firmware.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-122)

**R-15-123** IS: This is the split-MAC/SoftMAC partition: the turnaround in fixed hardware, the link layer and everything above it in software; the distinction from a Bluetooth/Wi-Fi controller is the no-foreign-computers line.
· Accept: the turnaround is one more fixed-latency entry in the timing-annotated model, riding RTL ⊑ Sail like the rest of the transceiver.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-123)

**R-15-124** IS: Off-die analog (PA, LNA, filters, switches, antenna tuners) is the primary regulatory layer: a switched bank of pre-certified fixed paths whose passbands and power ceilings are physical properties no software can exceed.
· Accept: no software path exceeds the passive envelope.
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-124)

**R-15-125** MUST: Emission envelope registers are the secondary layer: TX power and spectrum-mask limits latched at boot from RoT-verified signed calibration, immutable until reset.
· Accept: no runtime write path to the limit registers exists.
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-125)

**R-15-126** MUST: Per-unit calibration originates in a factory trim step, is emitted as a typed schema-bounded manifest bound to the device serial, signed by the provisioning key, and anchored at personalization by the RoT under its monotonic-counter-protected state.
· Accept: post-factory substitution or downgrade of calibration fails attestation like any other measured input.
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-126)

**R-15-127** IS: The calibration manifest is the one per-device artifact reproducibility cannot reach: it is measured, not built, so the factory step joins the supply chain as a trusted measurement, bounded by construction so compromise degrades performance and availability, never integrity and never the regulatory ceiling. The manifest schema those bounds are stated over is a crown-jewel spec.
· Accept: emission stays inside the passive analog envelope whatever the trim says; limit values latch only at or below certified ceilings; SRAM assist mis-trim degrades margin that ECC and fail-stop catch; sensor mis-trim costs fidelity.
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-127)

**R-15-128** MUST NOT: Runtime closed-loop self-calibration is banned: trim targets are set at end-of-life, full-temperature worst case, and the forgone margin is paid in the design's standing currency.
· Accept: what remains admissible is in-band signal tracking in software (AFC, channel estimation, equalization, gain words as ordinary capability-gated register updates); re-trim is a rare, explicitly-entered, RoT-attested maintenance mode, never a loop.
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-128)

**R-15-129** MUST: Generation floor: 5G and 6G only. The RF path bank carries only 5G/6G bands and the FEC units decode only LDPC and polar, so 2G, 3G, and 4G cannot be received at all.
· Accept: the legacy turbo and convolutional decoders are not on the die; the downgrade-attack class is deleted outright.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-129)

**R-15-130** IS: The target is 5G standalone (its own 5G-AKA mutual authentication, no LTE anchor) and forthcoming 6G; 5G non-standalone is excluded.
· Accept: no LTE anchor path exists.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-130)

**R-15-131** IS: Emergency calling rides the generation floor rather than breaching it: E911/E112 is placed over 5G-standalone (and 6G) emergency registration, and a legacy emergency-only receiver is declined because that hardware would reopen the downgrade surface.
· Accept: where only legacy or 5G-non-standalone coverage offers an emergency path, the call cannot be placed, the coverage-for-security trade booked in §17.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-131)

**R-15-132** MUST NOT: No persistent link-layer identifier exists in hardware: the die carries no factory-burned MAC or OUI.
· Accept: every link-layer address (Wi-Fi, Bluetooth, wired) is a fresh draw from the RoT TRNG through the verified DRBG, with locally-administered and unicast bits forced, never derived from a stored secret or a software PRNG.
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-132)

**R-15-133** IS: The §12 network compartment chooses only *when* to rotate; MAC randomization is privacy by construction, tied to the entropy root rather than to a disable-able setting.
· Accept: the drawn address is recorded in the §16 replay nondeterminism record, in the public class.
· Trace: CJ-NI · [§15](verification-maximal-os.md#r-15-133)

**R-15-134** IS: Capacity honesty: two radio-pinned V-cores plus FEC units give LTE-class throughput via reduced-bandwidth NR; the scaling axis is core count, never a firmware processor.
· Accept: no firmware processor exists in the radio path.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-134)

### 15.18 Wired link

**R-15-135** IS: The wired NIC is split-MAC applied to copper: the line interface is an analog front end, the MAC and above is a §12 host compartment, and the DSP is ordinary long-vector code on the same V-class datapath and FEC units the radio PHY uses.
· Accept: no Ethernet controller firmware exists; the IEEE-1588 timestamp unit and adjustable clock sit in the block as fixed-function matter.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-135)

**R-15-136** IS: 100BASE-TX dissolves completely: the PCS is host software on an ordinary core at a poll cadence the §11 ring-depth amortization covers, with no fixed-function block beyond the front end.
· Accept: no PCS hardware exists for 100BASE-TX.
· Trace: CJ-WCET · [§15](verification-maximal-os.md#r-15-136)

**R-15-137** MUST: 1000BASE-T is met by a fixed-function PCS-and-canceller datapath whose coefficients are trained at link-up and then frozen for the link epoch (RoT-loadable, cleared on link-down), with the MAC, autonegotiation policy, and all protocol state staying host software.
· Accept: adaptation is confined to a bounded training phase with no traffic in flight, so admission test 3 is met per epoch rather than waived.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-137)

**R-15-138** IS: The stated cost of frozen coefficients is that marginal cable plant re-trains on a link bounce instead of adapting through it: a link-availability cost, not an integrity one.
· Accept: the residual is booked in §16/§17.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-138)

**R-15-139** MUST NOT: 10GBASE-T and above are declined and booked in §17 rather than left an unimplemented gap.
· Accept: no LDPC-plus-Tomlinson-Harashima datapath exists for a wired port.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-139)

### 15.19 Sensor and transducer front-ends

**R-15-140** MUST: Every sensor is a register-slave AFE: no per-sensor DSP core and no sensor firmware. Capacitive-touch, audio, image, IMU/motion, and fingerprint/biometric front-ends are fixed analog-front-end plus scan-, sample-, or event-sequencer blocks with capability-gated MMIO configuration and capability-bounded DMA windows.
· Accept: every programmable signal-processing stage is dissolved onto V-class cores in the device's §12 compartment; the AFE's fixed-function conditioning adds no writable state.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-140)

**R-15-141** IS: Readout is fixed-cadence by default but may be event-driven (a fixed-function threshold comparator, or temporal-contrast pixels), with the data-dependent event timing confined to the owning island's static NoC/memory partition so no cross-island channel opens.
· Accept: the test-2 disposition is containment within the island partition.
· Trace: CJ-ISOL, CJ-NI · [§15](verification-maximal-os.md#r-15-141)

**R-15-142** IS: Raw-AFE silicon and its host-side DSP are a net-new co-design, booked as the honest cost of the firmware the profile deletes.
· Accept: the §17 entry exists.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-142)

**R-15-143** MUST: A front-end's capability-bounded DMA window and its configuration MMIO are one indivisible ownership, granted and revoked together.
· Accept: no holder of configuration alone exists; a configuration-only holder could blind, coarsen, or remap the scan, which is control over what frames mean.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-143)

**R-15-144** MUST: For front-ends carrying a consent or credential act (touchscreen, buttons, fingerprint sensor), ownership sits in a register latched by the RoT, unwritable by software while the latch holds and driven by the same RoT signal that lights the secure-attention indicator.
· Accept: the trusted-path agent takes the front-end for a prompt's duration without the owning driver's cooperation; the driver's only recourse is to deny service.
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-144)

### 15.20 Physical peripheral cutoffs

**R-15-145** MUST: For the microphone, the radios, and the wired data port the platform provides physical cutoffs the user actuates directly: a sealed switch independent of all software and firmware that no compromised OS, firmware, or RoT can override.
· Accept: admitted under the defense-in-depth clause because a physical cutoff adds no modeled mechanism, no Sail surface, and no proof obligation, while covering a domain the gates' own verification does not reach.
· Trace: CJ-T · [§15](verification-maximal-os.md#r-15-145)

**R-15-146** MUST: A peripheral is electronically enabled only while a live, consented capability grant holds it, so the platform cuts by default whatever nothing is using.
· Accept: the enable is driven by grant liveness rather than software claim, and therefore carries an in-use indication no compromised component can suppress.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-146)

**R-15-147** MUST: The attested lock state always cuts the microphone, the camera, and the USB data lanes, while the radio stays page-reachable in standby because the paging task still holds its capability.
· Accept: entering emergency-call mode mints a microphone capability bounded to the zero-authority emergency compartment, so *cut on lockout* and *available to an emergency call at BFU* are one rule about grants, not a rule plus an exception.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-147)

**R-15-148** IS: The sealed manual cutoffs dominate every software enable electrically rather than by mediation: the break sits in the power, bias, or data-lane path with no firmware in the loop, so there is no enable for software to interpose on. **What a thrown switch costs is R-12-054's statement**, cited here rather than restated.
· Accept: the dominance is a property of where the break sits, read against R-15-150 and R-15-151; the emergency-service consequence is read off R-12-054 rather than enumerated here, so the two cannot disagree.
· Trace: CJ-T · [§15](verification-maximal-os.md#r-15-148), [§15](verification-maximal-os.md#r-15-148-2)

**R-15-149** IS: In the mobile form factor the phone is always ringable: the away-gesture keeps the minimal cellular paging and voice-call grant alive while revoking every other radio and modem grant; only an airplane or high-assurance policy, or the manual radio switch, revokes the cellular ring itself.
· Accept: the away-gesture is form-factor-specific (lid close, face-down, or lockout alone) and triggers lockout.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-149)

**R-15-150** IS: The microphone, radio, and USB-data cutoffs are sealed, gasketed Hall-effect (or reed) switches, preserving the ingress-protection rating with no chassis penetration; whether the break is a contact or a dominant FET is an implementation choice, auditable by IRIS inspection.
· Accept: the cut is a dominant load-switch on the power/bias rail, or the data-lane mux for USB.
· Trace: CJ-T · [§15](verification-maximal-os.md#r-15-150)

**R-15-151** MUST: The USB cutoff drives the fixed-function data-lane mux, cutting D+/D−, SuperSpeed, and SBU pairs at the connector while VBUS, CC, and the fixed-function power-delivery sequencer keep charging alive.
· Accept: the attacker device never reaches the USB stack's enumeration and descriptor-parse path; no firmware sits in the path.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-151)

**R-15-152** IS: The camera's hard cutoff is a mechanical shutter with no electronics and no ingress path; beneath it, sensor access is a powerbox-mediated per-app consent grant scoped in time and to the device.
· Accept: on lockout the camera cuts through capability revocation rather than the shutter; the camera needs no sealed Hall switch because the shutter is its natural occluder.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-152)

### 15.21 Enclosure, shielding, and radiation hardening

**R-15-153** MUST: The enclosure is a continuous grounded conductive Faraday shell bonded at every seam and referenced to the device's own ground plane, with board-level shield cans over the RoT, the crypto core, and the radio front end, and every aperture treated (waveguide-below-cutoff vents, filtered and shielded I/O).
· Accept: admitted under the defense-in-depth clause as spending nothing on the scarce axis.
· Trace: CJ-T · [§15](verification-maximal-os.md#r-15-153)

**R-15-154** IS: The antennas sit outside the shielded volume and the wanted signal crosses on a coaxial, bulkhead-bonded RF feed, so the boundary stays continuous to stray fields while remaining transparent to the intended link.
· Accept: the shield encloses compute and memory logic, not the radiating elements.
· Trace: CJ-T · [§15](verification-maximal-os.md#r-15-154)

**R-15-155** IS: The shield addresses radiated and conducted EMI, electromagnetic fault injection, ESD, and compromising emanations; residual injected faults are caught by fixed-latency ECC and the fail-stop SEU/glitch path rather than trusted to the shield.
· Accept: *hardness at the boundary, correctness in the logic* is the stated split.
· Trace: CJ-T · [§15](verification-maximal-os.md#r-15-155)

**R-15-156** MUST NOT: Mass radiation shielding is declined: it does nothing to secondary neutrons and muons and a thin added mass raises the local upset rate through spallation.
· Accept: single-event upsets are met in the logic by pervasive ECC, CHERI validity tags, the fail-stop sentinel, multikernel blast-radius containment, and the RoT watchdog.
· Trace: CJ-T · [§15](verification-maximal-os.md#r-15-156)

**R-15-157** IS: Radiation hardening (hardened cells, upset-tolerant flip-flops, error-hardened SRAM, latch-up-immune wells, wide environmental envelope) is graded to the deployment and is a property of the process and RTL cells, not the architecture.
· Accept: the Sail model is unchanged and RTL ⊑ Sail still holds; the memory tiers take bottom dielectric isolation and the logic tier its SOI substrate.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-157)

### 15.22 Memory subsystem

**R-15-158** MUST: Main memory is bespoke on-die SRAM on the same die as the cores, not DRAM.
· Accept: no refresh, no refresh management, and no charge-disturbance Rowhammer primitive exists; the accepted price is density and idle leakage.
· Trace: CJ-SAIL, CJ-WCET · [§15](verification-maximal-os.md#r-15-158)

**R-15-159** IS: Density and leakage are bought by static, transistor-level levers only: sequential 3D tiers, CFET-stacked cells, gate-all-around, High-NA EUV patterning; asymmetric-Vt cells, gate-length biasing, state-retentive sleep-transistor gating, fixed logic-tier body bias, and a fixed composition-time read/write assist.
· Accept: the dynamic, adaptive, or data-dependent variants (adaptive assist, workload- or temperature-tracking body bias, activity-driven power gating) are declined; sub-threshold operation is admitted only as near-threshold idle-bank retention.
· Trace: CJ-LEAK · [§15](verification-maximal-os.md#r-15-159), [§15](verification-maximal-os.md#r-15-159-2)

**R-15-160** MUST NOT: Backside power delivery is declined for the whole machine, because it would occlude the IRIS backside optical inspection path; the die keeps frontside power delivery.
· Accept: the leakage and IR-drop cost is booked against the static cell levers.
· Trace: CJ-T · [§15](verification-maximal-os.md#r-15-160)

**R-15-161** MUST: Gate-all-around and CFET are admitted for the upper memory tiers and declined for the bottom logic tier, so the tier IRIS most needs to resolve (RoT, cores, capability fabric, memory controller) stays on an infra-red-resolvable node.
· Accept: the reconciliation is one die graded by tier; upper tiers are passive arrays holding no logic.
· Trace: CJ-T · [§15](verification-maximal-os.md#r-15-161)

**R-15-162** MUST NOT: A chiplet realization and bonded die-stacking are both declined: a separately fabricated die is a second mask set, fab lot, and supply-chain entity.
· Accept: multi-tier capacity is taken monolithically by sequential 3D, sharing one mask set, one fab lot, one package, and one attested identity, with no die-to-die link anywhere.
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-162)

**R-15-163** IS: Three consequences of sequential 3D are normative: static body bias is a logic-tier lever only; the shared thermal budget caps upper-tier device quality and tightens sustained-power headroom; and that budget makes the vertical lever conditional on a materials result rather than graded by effort, a 6T cell being complementary while the back-end-survivable oxide semiconductors that reach array-grade device metrics are n-type.
· Accept: the first two are carried in the §16 thermal posture and the leakage story; the third is carried as the two-case exposure in R-15-173 and the discrete manufacturing risk in R-18-008.
· Accept: the materials state the condition names is **demonstrated but not industrialized**, not absent, and the requirement is stated against that reading rather than against an empty literature. Low-temperature p-type oxide devices exist (sputtered SnOx near 39 cm²/V·s hole mobility driving all-oxide CFET-like inverters with IGZO, and IGZO/SnO complementary circuits including SRAM cells), as does a complementary back-end silicon route (roll-transfer-printed single-crystal nanomembranes, junctionless devices, three tiers of inverters through SRAM, at a ≤400 °C process). What none of them yet supplies is an SRAM array's device budget: p-type oxide on/off ratio sits near 10³ against the 10⁶ and above a dense low-leakage cell needs, subthreshold swing near 240 mV/dec, and the demonstrated tiers carry hundreds of transistors rather than billions. The gate is therefore real and its ground is device quality and scale, not the non-existence of a device.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-163)

**R-15-163a** IS: The n-type limit binds the complementary cell rather than every back-end macro: a two-transistor magnetic cell selects and reads through n-type devices alone, so a back-end memory of that shape is not gated by the p-type result the SRAM tier waits on.
· Accept: it bears on the §10 freshness lever (R-10-013f) and does not reopen this one, whose argument is 6T bit density and which the observation does not touch.
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-163a)

**R-15-164** MUST NOT: There are no hardware caches: no L1, no L2, no last-level cache, and no cache-coherence protocol.
· Accept: the cache hierarchy is deleted, not partitioned; the coherence protocol and directory leave the Sail model; the way-partitioning apparatus is unneeded; the `fence.t` flush set shrinks toward the store buffer alone.
· Trace: CJ-SAIL, CJ-ISOL · [§15](verification-maximal-os.md#r-15-164)

**R-15-165** IS: The retained fast structures are not caches: the register files, the Ztso store buffer, the static-path fetch buffer, and the explicit software-managed scratchpads of the V- and M-class datapaths.
· Accept: each passes the test that its contents are a function of the program text or of an explicit software placement, never of access history; address-indexing describes the lookup, history-dependence the contents, and only the latter carries the channel.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-165)

**R-15-166** IS: A structure holding *recently-used* anything fails that test however it is indexed, which is one of the grounds on which the memory integrity tree's node buffer is declined.
· Accept: the flat-latency claim holds precisely because no structure of the kind is present.
· Trace: CJ-WCET · [§15](verification-maximal-os.md#r-15-166), [§15](verification-maximal-os.md#r-15-166-2)

**R-15-167** IS: Fast local memory, where a datapath needs it, is an explicit scratchpad: capability-governed plain memory at a fixed address range, WCET-exact and coherence-exempt, holding no reactive or hidden state.
· Accept: it adds no timing channel and no flush obligation beyond the eager zeroize already accounted at a partition switch.
· Trace: CJ-WCET, CJ-ISOL · [§15](verification-maximal-os.md#r-15-167)

**R-15-168** IS: Scalar cores carry no local memory tier: their hierarchy is register file to SRAM main memory, flat and uniform. A scalar scratchpad is admitted only as a design-space-exploration parameter where access is predictable and high-reuse enough for static staging to pay.
· Accept: irregular latency is recovered off-device by static layout, never by a hardware cache.
· Trace: CJ-WCET · [§15](verification-maximal-os.md#r-15-168)

**R-15-169** IS: A cacheless core is a fully conformant RISC-V profile choice, not a fork: the ISA names no cache level, Ztso is defined over ordering, and `Zicbom` is dropped for want of a consumer.
· Accept: no conformance exception is claimed on this account.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-169)

**R-15-170** IS: The capacity budget is arithmetic: ~30–50 Mb/mm² of macro, so one gigabyte is roughly 160–270 mm² of raw array and a flat 4 GB is on the order of a full reticle or more; the High-NA half field (~430 mm²) is the hard planar boundary, so capacity is bought vertically.
· Accept: the reference instantiation budgets ~4–8 GB phone-class (8–16 memory tiers) and 16–32 GB laptop/desktop-class, as composition-time constants in the attested devicetree; every figure above the single planar tier is contingent on R-15-173a and is not to be read as scheduled.
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-170)

**R-15-171** MUST: The roster is fit to the budget explicitly, and a workload that does not fit is refused at admission, not paged: there is no swap and no overcommit anywhere, every resident byte being a capability-delegated SRAM byte.
· Accept: browser origins take a composition-sized budget with crash-only eviction; the inference server serves the 1–4 B-parameter class on a phone and the 7 B-plus class on laptop/desktop.
· Fail-closed: a workload that does not fit the budget is refused at admission (R-17-030q); the cost is delivery of that workload.
· Trace: CJ-MEMPLAN · [§15](verification-maximal-os.md#r-15-171)

**R-15-172** IS: Island exclusivity is a booked capacity tax: whole-macro or whole-tier binding forfeits pooling, so each island is sized to its peak rather than the machine to the sum of averages.
· Accept: the fraction is composition-visible and netted out of the budget.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-172)

**R-15-173** MUST: Should the density levers under-deliver, the fallback bends capacity (fewer origins, smaller models, a leaner roster), never the mechanism: DRAM does not return and neither does a second die.
· Accept: the fallback is stated as a composition change, not an architectural one.
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-173), [§15](verification-maximal-os.md#r-15-173-2)

**R-15-173a** IS: The tier-count exposure is two-case rather than a continuum: where complementary back-end devices reach array-grade quality and manufacturable scale, tier count is an ordinary yield-and-cost question and R-15-173 runs as written; where they do not, the vertical lever is absent rather than reduced, capacity is the single planar tier at order 1–2 GB, and the phone envelope is unreachable rather than late.
· Accept: both cases bend the roster and neither returns a mechanism, so the disposition is unchanged; what the second case forbids is treating the 8-to-16-tier step as a schedule item, and the roster shown to close is the one-tier roster (R-18-030a).
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-173a)

**R-15-174** MUST NOT: Variable-rate compression of the memory path (a compressed pool or cache, runtime deduplication) is declined: it would make capacity data-dependent, latency operand-dependent, and the ratio a cross-compartment oracle.
· Accept: fixed-rate encodings chosen at composition time remain admissible as compartment-local data representations.
· Trace: CJ-NI, CJ-WCET · [§15](verification-maximal-os.md#r-15-174)

**R-15-175** MUST: Every SRAM array is ECC-protected and corrected, not merely detected: register files, vector register files, matrix scratchpads, the CHERI native tag bits, and the main-memory array alike.
· Accept: the floor is SECDED everywhere, with no structure left parity-only, because a scratchpad word or live register holds the only copy of its word.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-175)

**R-15-176** MUST: The error-detecting check travels *with* the word across the interconnect and the memory controller and is verified at the consumer, so a fault injected in transit is caught rather than masked by re-encoding at each hop.
· Accept: there is no die-to-die interface to protect; every hop is on-die. The one re-encoding point on the path, the memory controller's sub-granule read-modify-write stage (R-15-181), does not mask a transit fault, because the existing codeword's check is verified *before* the merge, so the stage catches a corrupt granule rather than laundering it into a fresh codeword.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-176)

**R-15-177** MUST: Physical bit-interleaving and background scrubbing are mandated, not optional: a multi-cell upset presents as separable SECDED-correctable single-bit errors, and a latent single-bit error never accumulates into an uncorrectable double.
· Accept: both are present on every array.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-177)

**R-15-178** MUST: The CHERI validity tag bits take the stronger DECTED code, because a flipped tag forges or destroys a capability.
· Accept: the tag plane's code is DECTED throughout.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-178)

**R-15-179** MUST: ECC correction is deterministic: a fixed data-independent latency folded into WCET, the corrected and uncorrected paths taking the same cycles.
· Accept: no variable slow path exists; every corrected error is reported to the sentinel as telemetry and every detected-but-uncorrectable error is a fail-stop sentinel event, never silently consumed.
· Trace: CJ-WCET, CJ-LEAK · [§15](verification-maximal-os.md#r-15-179)

**R-15-180** IS: ECC is the memory path's only integrity mechanism, deliberately: it answers the random bit flip, which is the threat main memory on this die actually faces.
· Accept: cryptographic memory constructions answer an interface this machine does not have (R-15-195).
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-180)

**R-15-181** MUST: No sub-granule write exists at the array: the atomic write unit is the ECC codeword with its validity tag bits, and every path that reaches the array writes whole units.
· Accept: a sub-granule store merges with the granule's existing codeword in a fixed read-modify-write stage at the memory controller, a constant pipeline term priced once, with the existing codeword's check **verified before the merge** and tag and check bits regenerated combinationally in the same pass. Cores may therefore issue sub-granule stores; what the whole-unit rule scopes is the controller-to-array path, not every path on the fabric, and the verify-before-merge obligation is what keeps this the one re-encoding point consistent with R-15-176.
· Trace: CJ-WCET · [§15](verification-maximal-os.md#r-15-181)

**R-15-182** MUST: `cbo.zero` allocates whole lines: zero data, cleared validity tags, and matching SECDED/DECTED codewords for data and tag plane alike, in one pass at one fixed per-line latency.
· Accept: one entry in the timing-annotated model.
· Trace: CJ-MEMPLAN · [§15](verification-maximal-os.md#r-15-182)

**R-15-183** MUST: Device DMA is granule-aligned by construction: windows are allocated at tag-granule (8-byte) alignment, interface FIFOs coalesce arrivals into granule-multiple bursts, and a trailing partial granule completes with zero fill inside the delegated buffer.
· Accept: a non-capability DMA write clears the validity tags of exactly the granules it wholly covers and can straddle nothing; the descriptor's length field, not the fill, delimits the payload.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-183)

**R-15-184** IS: Rowhammer and its RowPress variant have no charge-disturbance analog in SRAM, so the refresh-management apparatus (RFM cadence, PRAC counters, alert and back-off) is deleted, not tuned.
· Accept: no activation-counting or back-off mitigation is carried or re-tuned per disturbance variant; the residual is SRAM's own read/write-disturb and half-select modes, covered by the pervasive ECC and cell-level margin, with an uncorrectable event a fail-stop sentinel event.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-184)

**R-15-185** MUST NOT: Autonomous processing-in-memory is banned: compute placed inside the memory array is outside the ISA, capability model, Sail model, and attestation.
· Accept: the admitted densification path is deterministic digital compute-in-SRAM (bit-serial exact MACs, Sail-expressible) for the M-class, never an autonomous or analog one.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-185)

### 15.23 Power architecture

**R-15-186** MUST: Exactly five power mechanisms are admissible, and every banned mechanism (SMM PM handlers, Pcode/SCP/AOP PMU microcontrollers, reactive DVFS, turbo, autonomous throttling) is banned for sharing a hidden feedback loop from workload or temperature to performance state.
· Accept: the five are race-to-idle with in-slot gating; static per-partition operating points; pre-proved global mode schedules; deep sleep as a boot-chain variant; and composition-time gating of unallocated SRAM.
· Trace: CJ-ISOL, CJ-WCET · [§15](verification-maximal-os.md#r-15-186)

**R-15-187** MUST: In-slot clock/power gating is entered only when the remaining slot ≥ entry+exit WCET, and exit latency is a data-independent Sail-modeled constant.
· Accept: slot boundaries do not move; an idle core emits no shared-fabric traffic, so gating is cross-partition invisible.
· Trace: CJ-WCET, CJ-ISOL · [§15](verification-maximal-os.md#r-15-187)

**R-15-188** MUST: Each partition's operating point is selected by the §11 admission proof and is a composition-time constant, switched only at partition boundaries; shared resources (NoC, memory controller, main memory) never scale.
· Accept: data-independent, so Hertzbleed has no carrier; expect 2–3 coarse OPPs per class, floored by ECC/CHERI-tag integrity margin at low voltage.
· Trace: CJ-WCET, CJ-LEAK · [§15](verification-maximal-os.md#r-15-188)

**R-15-189** MUST: Global mode schedules are pre-proved and switched as rare RoT-attested global transitions on explicit authority, never load-following.
· Accept: log₂(#modes) bits per audited event; migration stays banned.
· Trace: CJ-NI · [§15](verification-maximal-os.md#r-15-189)

**R-15-189a** MUST: Power mechanism 5 is composition-time gating of unallocated SRAM: arrays holding nothing in a mode are retained or collapsed by the same RoT-attested transition that installs the mode (mechanism 3 applied to memory rather than to islands).
· Accept: never activity-driven and never demand-woken; the schedule, not an idle detector, decides.
· Trace: CJ-ISOL, CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-189a)

**R-15-189b** IS: Static allocation makes the unused array set knowable: with no allocator, no swap, no overcommit, and no demand growth, the whole-program memory plan's slot assignment is the complete and final statement of which bytes an admitted composition can touch, so its complement is a build constant.
· Accept: the conventional idle-timer bank-gating controller is refused as a reactive loop from access history to power state whose supply-current signature follows the tenant's access pattern; the saving it chases is taken statically instead.
· Trace: CJ-MEMPLAN, CJ-NI · [§15](verification-maximal-os.md#r-15-189b), [§15](verification-maximal-os.md#r-15-189b-2), [§15](verification-maximal-os.md#r-15-189b-3)

**R-15-189d** MUST: Each gating domain occupies exactly one of three states, ON, RETAINED (state-retentive, contents and tags preserved, not addressable), or OFF (rail collapsed, data, tag plane, and check bits destroyed), and transitions occur only at a global mode transition, commanded only by the RoT, from the mode's pre-proved descriptor.
· Accept: no edge in the lattice is traversable by an access, a timer, a counter, or a temperature; a domain's power state is a function of the mode schedule and the current mode index, never of access history, occupancy watermark, idle timer, or observed leakage.
· Trace: CJ-NI, CJ-WCET · [§15](verification-maximal-os.md#r-15-189d)

**R-15-189e** MUST: The gating domain is the macro or tier, never the bank, so that it coincides with the isolation domain; where low-sensitivity islands share a macro at bank granularity, its state is the conjunction over its bound islands' mode participation.
· Accept: shared power delivery is already the coupling that separates bank binding from whole-macro exclusivity (R-15-228), so no per-bank rail is claimed; the conjunction is over composition-time facts, so no island's runtime behavior reaches another island's rail.
· Trace: CJ-ISOL, CJ-NI · [§15](verification-maximal-os.md#r-15-189e)

**R-15-189f** MUST: Composition emits, per global mode, one {ON, RETAINED, OFF} entry per gating domain, a total function of the static memory plan, the bank/macro/tier→island map, and the mode's resident island set; the vector lands in the attested static devicetree and is hashed into the mode descriptor.
· Accept: a verifier learns which arrays were live in which mode; the transition stays a log₂(#modes)-bit audited event, the attestation surface growing by a named constant table and not by an open set of runtime decisions.
· Trace: CJ-DEVTREE, CJ-NI · [§15](verification-maximal-os.md#r-15-189f)

**R-15-189g** MUST: For every mode, the union of address ranges authorized by any capability reachable by any resident compartment is contained in the union of that mode's ON domains, decided by the same on-device pass that checks slot disjointness; a power vector that switches off a reachable array fails to type-check and is rejected at admission.
· Accept: hardware decode disable is a backstop only (an access decoding to a non-ON domain is a fail-stop sentinel event, never a floating read, a stall, or a wake); there is no wake-on-access anywhere in the mechanism, that being demand paging with a power rail.
· Fail-closed: a failed containment check rejects the composition (an availability outcome), never admits it with an unreachable-but-live array.
· Trace: CJ-CERISE, CJ-ISOL, CJ-WCET · [§15](verification-maximal-os.md#r-15-189g)

**R-15-189h** MUST NOT: Six adjacent forms are declined for rebuilding the loop: idle-timer, watermark, or access-counter bank gating; wake-on-access, demand power-up, or any cold-array slow path; runtime occupancy compaction with a relocation pass; leakage-, temperature-, or aging-sensing modulation of the retention rail; a power domain shared across islands participating in different modes; and per-domain voltage or frequency scaling following bandwidth demand.
· Accept: the static counterpart of compaction is admitted as a memory-plan objective (R-08-012e); the conjunction rule (R-15-189e) is the admitted alternative to a cross-island domain; shared resources never scale (R-15-188).
· Trace: CJ-NI, CJ-LEAK · [§15](verification-maximal-os.md#r-15-189h)

**R-15-189i** MUST: Rail collapse and restore are RoT-sequenced with fixed dwell times in a fixed staggered ramp order, both composition-time constants, and inrush is bounded by provisioning the power delivery network for the worst-case simultaneous-on set read off the power vectors.
· Accept: no current-sensing soft-start loop exists; per-domain transition latency is a data-independent modeled constant folded into the §11 mode-transition budget, adding a term to that budget and no variability to any partition's WCET.
· Trace: CJ-WCET, CJ-NI · [§15](verification-maximal-os.md#r-15-189i)

**R-15-189j** MUST: Every OFF→ON transition begins with an unconditional array clear (zero data, cleared validity tags, regenerated SECDED and DECTED codewords for both planes) at a fixed per-domain latency, completed before the domain is admitted to the mode.
· Accept: whatever survived the collapse (low-temperature retention, incomplete discharge, a glitched or held rail) is overwritten before any capability names the array, so a fault-injection attack that keeps a domain alive across a mode transition yields zeros; the latency is a modeled constant and the clear is never conditional on what the array holds.
· Trace: CJ-ISOL, CJ-CERISE · [§15](verification-maximal-os.md#r-15-189j)

**R-15-189n** MUST: The RoT gates that transition on a one-bit discharge confirmation, and collapse is thereby the strongest zeroize the platform has: it removes the charge rather than overwriting it, tag plane included, so island teardown at a mode boundary is a physical erasure and not a trusted write.
· Accept: the confirmation is one bit read once, never a retry loop and never a feedback path into timing; a domain that does not confirm does not enter the mode.
· Fail-closed: a rail that does not discharge latches a fail-stop rather than completing the transition, composed at R-17-030n with the rest of the detector class; the cost is the mode transition and, with it, the availability of the mode being entered.
· Trace: CJ-ISOL, CJ-CERISE · [§15](verification-maximal-os.md#r-15-189n)

**R-15-189k** MUST: Background scrubbing runs on ON domains only, so the retention voltage floor is set by DECTED tag-plane margin at the worst characterized corner, and any mode holding a domain RETAINED longer than the §16 accumulation bound must schedule a periodic ON scrub interval or perform a full verify-and-correct sweep on the exit path before admission.
· Accept: all three are composition-time constants, none a timer firing on an observed error rate; in standby the DRX period is the scrub period, the live island's bank returning to ON at every paging occasion.
· Trace: CJ-SAIL, CJ-WCET · [§15](verification-maximal-os.md#r-15-189k), [§15](verification-maximal-os.md#r-15-189k-2)

**R-15-189l** IS: Leakage is proportional to powered bitcell count, so island exclusivity becomes a capacity tax and not a leakage tax, a deployment pays leakage for the roster it composed rather than the capacity fabricated, and standby leaks in proportion to the retained tens of megabytes rather than the fabricated gigabytes.
· Accept: retention runs roughly an order of magnitude below active-voltage idle per bit and collapse one to two further orders below retention; absolute figures are per-process characterization inputs to the §11 and §16 budgets, the structure of the saving being what is normative; collapsed tiers also relieve sequential 3D's shared heat path and sustained-power headroom.
· Trace: CJ-DEVTREE, CJ-ISOL · [§15](verification-maximal-os.md#r-15-189l), [§15](verification-maximal-os.md#r-15-189l-2)

**R-15-189m** IS: A domain's power state is a function of the mode index alone, and the mode index is already a declared, RoT-attested, log₂(#modes)-bit public event, so an adversary observing supply current, di/dt, electromagnetic emission, or thermal signature learns the mode and nothing about any partition's data, access pattern, or occupancy.
· Accept: this is the property activity-driven gating cannot have, its operating principle being to make the rail a function of tenant behavior, and it is the whole of why one form is admitted and the other declined.
· Trace: CJ-NI, CJ-LEAK · [§15](verification-maximal-os.md#r-15-189m)

**R-15-190** MUST: Standby is a partial-power global mode (mechanism 3), not whole-machine deep sleep: exactly one island stays live at low duty cycle while every other island is sealed and powered off.
· Accept: the live set is enumerated as the radio island, its kernel instance, the cellular paging path, the DRX wake timer, the island's bound SRAM bank in low-leakage retention, and the RoT, a composition-time constant attested on entry.
· Trace: CJ-ISOL, CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-190), [§15](verification-maximal-os.md#r-15-190-2)

**R-15-190a** MUST: Outside standby's live set every macro and tier is collapsed outright rather than retained (R-15-189a).
· Accept: the sealed islands hold no live allocation to preserve across a mode whose exit re-measures them, so their OFF→ON clear on wake (R-15-189j) is subsumed by that re-measurement, and standby leaks in proportion to the live set alone (R-15-189l).
· Trace: CJ-ISOL, CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-190a)

**R-15-191** IS: The memory path needs no protection carve-out in the live set: it holds no key, no counter, and no root register, so the live set is ordinary static logic rather than an exception carved for a cryptographic invariant.
· Accept: the retained bank plus the TDM slice joining island to bank is the whole of it.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-191)

**R-15-192** MUST: The live island does not resume: it runs idle-mode DRX paging reception as a §11-admitted periodic hard task (period = the network's DRX cycle, deadline = the paging occasion), so no resume path outside the measured chain is created.
· Accept: deep-slept islands re-measure on wake; a page that escalates to a connection wakes the application islands through the boot-chain-variant path.
· Trace: CJ-WCET, CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-192)

**R-15-193** MUST: Thermal posture is fail-stop, not modulation: TDP-provisioned so throttling never engages normally, with critical temperature triggering a rare attested global transition (orderly halt or a proved low-power/recovery mode).
· Accept: a ~1-bit event rather than continuous throttling's data-dependent channel; temperature read-out is a gated capability.
· Fail-closed: thermal trip stops everything running (R-17-030b); the cost is the work in progress and nothing else.
· Trace: CJ-NI · [§15](verification-maximal-os.md#r-15-193)

**R-15-194** MUST: There is exactly one management processor, the RoT: power sequencing, reset, mode orchestration, and the watchdog are RoT duties, verified, in the TCB, never resident on or above the application cores.
· Accept: no embedded controller, PMU microcontroller, or SMM-class residency exists.
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-194)

### 15.24 Clocking, reset, and domain crossings

**R-15-195** MUST: All modeled islands run mesochronous from one clock spine: every core, fabric, memory, and device-block clock is an integer division of a common PLL hierarchy, so crossings inside the modeled machine are deterministic ratio synchronizers with fixed, Sail-modeled latency.
· Accept: the TDM NoC schedule is stated in spine cycles; an OPP change is a divider reprogram at a partition boundary whose relock is a fixed constant in the switch budget; no modeled path crosses between unrelated clocks.
· Trace: CJ-WCET, CJ-SAIL · [§15](verification-maximal-os.md#r-15-195)

**R-15-196** IS: The genuinely asynchronous boundaries are exactly three, each terminated and none modeled as fixed-latency: the RoT's independent slow clock, the external interface clocks, and reset itself.
· Accept: every theorem touching the RoT path uses one-sided bounds only; external interface clocks terminate in a bounded FIFO behind the capability-checked DMA window, contributing only a line-rate bound to the §11 bandwidth reservation; reset is synchronized per domain at its boundary.
· Trace: CJ-WCET, CJ-ISOL · [§15](verification-maximal-os.md#r-15-196)

**R-15-197** IS: Residual synchronizer failure is booked beside SEU as a physical fault class, not a modeled behaviour: rate engineered to negligible MTBF, consequences caught by ECC, fail-stop, and the watchdog.
· Accept: no modeled constant quantifies over a metastability resolution.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-197)

**R-15-198** MUST: Power-domain and reset sequencing is a fixed, composition-time sequence table in the attested devicetree, dependency-ordered, each step gated on a hardware ready indication under a watchdog-bounded timeout, executed by the verified RoT firmware as the only sequencer. The table is itself a crown-jewel spec.
· Accept: mode transitions, standby entry and exit, and deep-sleep wake are re-entries into suffixes of the same table, so there is one sequencing artifact to verify, a crown-jewel spec beside the NoC schedule; resets are hierarchical, and only the watchdog bite asserts the die.
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-198)

### 15.25 The memory path carries no cryptography

**R-15-199** MUST NOT: There is no memory encryption, no memory authentication, and no integrity or anti-replay tree on the memory path.
· Accept: main memory is on-die SRAM with no external bus, no removable module, and no die-to-die link, so the interface such a mechanism would protect does not exist.
· Trace: CJ-T · [§15](verification-maximal-os.md#r-15-199)

**R-15-200** IS: The benefits usually claimed are each discharged by something already present: shutdown zeroization by SRAM volatility plus the platform's own zeroize, the bus interposer by the absence of any bus, cold boot by the same volatility; what remains is invasive physical attack, out of scope by name.
· Accept: the exclusion cites the same *verify rather than hedge* ground as PMP, the IOMMU, MTE, and the Harvard split.
· Trace: CJ-T · [§15](verification-maximal-os.md#r-15-200)

**R-15-201** IS: The integrity and anti-replay tree is declined on two further grounds of its own: its node buffer would be a cache by this section's own test (failing test 3 and reintroducing the WCET-pessimism term), and its log-depth walk with a hit-or-miss distribution is exactly the term §11 must otherwise bound pessimistically on every access.
· Accept: the adversary it names can equally read the on-die root register the guarantee rests on.
· Trace: CJ-WCET, CJ-ISOL · [§15](verification-maximal-os.md#r-15-201)

**R-15-202** IS: Crown-jewel secret confidentiality rests on the crypto core's hardware boundary and the seal/switch primitives, not on encrypting memory: keys never leave the core, and what is resident outside it is a sealed blob plus a capability handle.
· Accept: the memory controller carries only the granule read-modify-write stage and the ECC encode-and-check: no key, no cipher, no counter, and no address-dependent latency class.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-202)

**R-15-203** MUST: CHERI tags are native SRAM bits, one validity tag per **64-bit** granule, one plane and not two, read and written in parallel with the data, with no separate table and no tag cache.
· Accept: the reserved-memory tag table and the partitioned tag cache are deleted, and with them a shared microarchitectural state element, its miss-and-walk latency term, its way-partitioning and `fence.t` membership, and its DSE parameter. The granule follows the capability width (R-15-007), and it moves the tag plane alone: the ECC codeword stays at 128 data bits and carries two tag bits instead of one (R-15-181), so no data-side check-bit area moves, tag-plane density doubles to 1.56% of the array, and the plane's DECTED area (R-15-178) doubles with it. Against that, capability-dense structures halve, so the net is computed against the roster (R-15-170) at composition rather than argued.
· Trace: CJ-CERISE, CJ-ISOL · [§15](verification-maximal-os.md#r-15-203)

**R-15-204** IS: Tag integrity is an ECC property, not a cryptographic one, because the tag bits never leave the die; a tag-integrity failure is an ECC event and a fail-stop sentinel event.
· Accept: non-capability transducer and DMA writes clear the corresponding tag bit by construction.
· Fail-closed: an uncorrectable ECC or tag-integrity event stops the machine (R-17-030n); the cost is the running state, against a silent integrity failure as the alternative.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-204)

### 15.26 Capability-checked DMA

**R-15-205** MUST NOT: Neither an IOMMU nor an IOPMP is on the die: device DMA is brought under CHERI rather than confined by a separate translation or region-protection unit.
· Accept: the device-side completion of the No-PMP decision; the IOMMU's translation is dead weight in one address space and only its protection is wanted, which CHERI supplies unforgeably and byte-granularly.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-205)

**R-15-206** MUST: Every DMA-capable block is one of exactly two capability-checked shapes: a core-issued capability-operand mover, or an autonomous streaming engine holding a delegated, bounds-checked, revocable capability for the lifetime of its window.
· Accept: the fabric checks each device access against a capability at the point of issue, default-deny, exactly as a core's load or store is checked; a device MSI is confined by the same check rather than an interrupt-remapping table.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-206)

**R-15-207** IS: The rule governs true devices only (NIC, flash interface, USB, scanout, audio, radio transceiver stream); V/M cores are cores and are already CHERI-governed.
· Accept: no device class falls outside the two shapes.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-207)

**R-15-208** MUST: In-flight-DMA revocation is an obligation, not a waiver: a capability held by a running transfer honours the §8 revocation sweep (a load-barrier / revocation-epoch check, or bounded per-window re-authorization) so time-to-containment stays the §8 bounded constant, its worst case entering the §11 budget.
· Accept: the mechanism is named and its cost budgeted.
· Trace: CJ-CERISE, CJ-WCET · [§15](verification-maximal-os.md#r-15-208)

**R-15-208a** MUST: DMA completion is an RTL-enforced ownership boundary: it cannot become visible until issue has stopped, all accepted writes have reached SRAM, and the delegated window is closed or re-authorized away from the device; no request under the old transfer capability may issue afterward.
· Accept: the RTL ⊑ Sail completion lemma proves quiescence, write visibility, and old-capability rejection before the completion event observed by software.
· Trace: CJ-RTL-SAIL, CJ-HAL · [§15](verification-maximal-os.md#r-15-208a)

**R-15-209** MUST: The interconnect is a capability- and tag-carrying fabric: it propagates capabilities, tags, and revocation state to the DMA blocks, while non-capability transducer writes clear tags by construction.
· Accept: this is new Sail-model and RTL ⊑ Sail surface, booked in §18.
· Trace: CJ-RTL-SAIL · [§15](verification-maximal-os.md#r-15-209)

**R-15-210** IS: The deletion is sound only because the device model is already curated register-slave / transducer / on-die RTL, with no foreign bus-master issuing raw physical addresses; the residual (no IOMMU-disjoint backstop) is booked in §17.
· Accept: both the precondition and the residual are recorded.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-210)

### 15.27 Temporal isolation and `fence.t`

**R-15-211** MUST: Temporal isolation is carried by `fence.t`-class flush at partition switches, SRAM bank/macro/tier partitioning, and TDM NoC arbitration with island separation, each carrying architecturally guaranteed non-interference semantics in the Sail model. The isolation model those semantics are stated in is a crown-jewel spec.
· Accept: a partition's timing behaviour is independent of another's activity, decided against the isolation model's non-interference statement rather than against the list of mechanisms above it; until that model is authored the obligation is stated and not discharged (R-17-003b).
· Trace: CJ-ISOL, CJ-NI · [§15](verification-maximal-os.md#r-15-211)

**R-15-212** IS: Bandwidth appears as a consequence of the NoC schedule and the bank binding, never as a regulated quantity; no bandwidth-allocation mechanism exists beside them.
· Accept: `Ssqosid`/CBQRI is excluded (R-15-050).
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-212)

**R-15-213** MUST: The `fence.t` flush set is a single structure: the store buffer, drained rather than merely fenced, so no old-partition store can land or become visible after the switch.
· Accept: the predictor-history, transient, and cache-state classes are absent by construction rather than flushed.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-213), [§15](verification-maximal-os.md#r-15-213-2)

**R-15-214** MUST: The register files are deliberately not in the flush set; what replaces flush-set membership is an obligation on the primary: the kernel's restore set is total over architectural register state, every general-purpose, capability, and CSR location a partition can name being written before the successor partition's first instruction.
· Accept: residue is impossible rather than cleared, and a register outside the restore set is a failure of the kernel proof.
· Trace: CJ-KERNEL, CJ-ISOL · [§15](verification-maximal-os.md#r-15-214)

**R-15-215** MUST: Nothing else joins the flush set, each would-be member being already absent or covered elsewhere: no predictor, no reservation, no prefetcher, no TLB or walk cache, no cache of any kind, no scalar-FP or rounding-mode state, the register files by total restore, and the vector/matrix and scratchpad state by the §7 eager zeroize.
· Accept: each is a distinct named mechanism, not the fence's job. With the V/M save deleted (R-07-014a) the last two converge: both are discharged by what the switch *writes* before the successor's first instruction, neither by a snapshot carried across, so R-15-217's class (a) has one sub-case rather than two.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-215)

**R-15-216** IS: `fence.t` does not touch state that is partitioned rather than time-shared (SRAM banks/macros/tiers, TDM NoC slots, per-partition interrupt-file state), and in-flight DMA is not its concern: device windows are torn down or re-authorized by the capability machinery at the boundary.
· Accept: flushing spatially-owned state would be a category error.
· Trace: CJ-ISOL, CJ-CERISE · [§15](verification-maximal-os.md#r-15-216)

**R-15-217** MUST: The completeness argument is mechanized: every stateful structure in the RTL is mapped, in the RTL ⊑ Sail refinement, to exactly one of four classes: architectural or context-switched; partition-owned; `fence.t`-flushed; or stream-determined pipeline state (the static-path fetch buffer and the decode and execute latches, emptied by the fence's pipeline drain); and a structure outside the map is a refinement failure.
· Accept: *did we flush everything* is discharged against the RTL state inventory rather than a hand-maintained list, and the fourth class is bounded by the same table-freeness test that separates fetch pipelining from a prefetcher (R-15-104).
· Trace: CJ-RTL-SAIL, CJ-ISOL · [§15](verification-maximal-os.md#r-15-217)

**R-15-218** MUST: `fence.t`'s cost is a padded per-class constant and the fence completes at that bound, never early.
· Accept: the worst case is the store buffer's drain latency at the class's depth and memory bandwidth, a data-independent entry in the timing-annotated model. The bound is over SRAM and holds because R-15-015b keeps device-space stores out of the buffer, so no endpoint's accept latency is inside it and the constant is a function of the class rather than of what the outgoing partition was last talking to.
· Trace: CJ-WCET, CJ-LEAK · [§15](verification-maximal-os.md#r-15-218), [§15](verification-maximal-os.md#r-15-218-2)

**R-15-219** IS: That constancy, not the draining, is why a plain `fence` cannot replace it: a `fence` completes when the buffer happens to empty, making its duration a function of the outgoing partition's store-buffer occupancy, a partition-switch-duration channel.
· Accept: the temporal fence makes the term data-independent, a property no ordering fence has.
· Trace: CJ-NI, CJ-WCET · [§15](verification-maximal-os.md#r-15-219)

**R-15-220** MUST: Partition-switch cost is three terms, not four: the `fence.t` padded constant (which *is* the store-buffer drain, counted once), eager vector/matrix zeroize (zeroize only; the switch saves nothing, R-07-014a), and OPP relock where operating points differ.
· Accept: listing the fence and the drain separately would inflate every switch bound feeding §11 by a full drain.
· Trace: CJ-WCET · [§15](verification-maximal-os.md#r-15-220), [§15](verification-maximal-os.md#r-15-220-2)

**R-15-221** IS: The flush-set statement is itself a crown-jewel spec, now over one structure rather than two.
· Accept: it appears in the crown-jewel inventory and is subject to independent review.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-221)

### 15.28 Interconnect and islands

**R-15-222** IS: Islands are confidentiality domains: a memory, NoC, and power partition (bound SRAM banks, macros, or tiers, TDM-NoC slots, and at the top rung its own clock and power domain), not a coherence domain.
· Accept: no cache-coherence protocol and no coherence directory exist within or across islands.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-222)

**R-15-223** MUST: Across islands there is no shared mutable memory at all: cross-island communication is only through designated ring windows in a shared SRAM region, whose release/acquire edges are made visible by Ztso plus R-15-015a without a fence.
· Accept: the cross-domain coherence-traffic channel is deleted structurally, there being no coherence traffic anywhere on the die.
· Trace: CJ-ISOL, CJ-NI · [§15](verification-maximal-os.md#r-15-223)

**R-15-224** MUST: The radio-pinned V-cores form their own island and take the top rung of every graded axis: a separate SRAM macro or tier, and their own clock/power island.
· Accept: the on-die power-delivery droop coupling a shared-die radio would leave is deleted on one die rather than by a second package.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-224)

**R-15-225** MUST: The NoC uses TDM arbitration with formal semantics, its schedule emitted by the §11 admission proof, and its non-interference is part of the Sail-level isolation model. Best-effort QoS is not admissible.
· Accept: no arbitration decision depends on another domain's activity.
· Trace: CJ-ISOL, CJ-NI · [§15](verification-maximal-os.md#r-15-225)

**R-15-226** MUST: The SRAM bank, macro, or tier is bound to the island as a graded spatial hierarchy: separate macro or stacked tier, then separate bank group, then bank within a macro, decreasing in isolation strength as sharing rises to a common macro.
· Accept: high-assurance islands take whole-macro (better, whole-tier) exclusivity; mid- and low-sensitivity islands take bank granularity, with residual macro-internal coupling narrowed by static per-island arbitration and `fence.t` and booked in R-17-003b rather than eliminated.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-226)

**R-15-226a** IS: Shared power delivery is what fixes the gating domain at the macro or tier rather than the bank, so an island holding whole-macro or whole-tier exclusivity owns its own memory power domain and takes the strongest form of composition-time gating as a consequence of the isolation it already bought.
· Accept: islands sharing a macro share its rail and take that macro's power state as the conjunction of their mode participation, a composition-time constant rather than a coupling either can drive (R-15-189e).
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-226a)

**R-15-227** MUST: Residual coupling is narrowed by scheduling, never by throttling: a rate regulator could only shape traffic whose arrival the TDM schedule already fixed, which is why none exists.
· Accept: consistent with R-15-050.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-227)

**R-15-228** MUST: The memory controller enforces the binding, its per-island arbitration carries TDM-NoC-class non-interference semantics in the Sail model, and the bank/macro/tier→island map lands in the attested static devicetree as a crown-jewel spec.
· Accept: each island's bandwidth ceiling quantizes to its assigned banks or macros and feeds §11 admission.
· Trace: CJ-ISOL, CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-228)

**R-15-228a** MUST: The bank/macro/tier→island map is an input to the §8 static memory plan and never an output of it: the plan distributes an island's own objects across the arrays the map already grants it, altering no binding, no arbitration, and no ceiling.
· Accept: the attested devicetree map is identical before and after placement; consistent with R-08-012c.
· Trace: CJ-ISOL, CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-228a)

### 15.29 Display and media

**R-15-229** IS: The scanout controller is the one graphics device: a small open-RTL firmware-free DMA block behind a static capability-bounded DMA window; audio I/O follows the same pattern.
· Accept: they are allowlisted peripherals, not accelerators.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-229)

**R-15-230** MUST: The §11 admission proof emits, with every mode schedule, the scanout engine's static TDM NoC slice, its framebuffer bank-group binding, and a line-buffer FIFO sized to the TDM service interval, so underrun cannot arise from contention by construction.
· Accept: the line period is the deadline and the FIFO depth the proved jitter bound; the framebuffer is ordinary main memory read through the same ECC-only path, with no cryptographic term on the scanned line.
· Trace: CJ-WCET · [§15](verification-maximal-os.md#r-15-230)

**R-15-231** MUST: Display underrun is a §16 sentinel fault class, not a load outcome: affected lines blank visibly as the presentation of a caught fail-stop, never a silent display of unauthenticated bytes.
· Accept: recovery is the ordinary §16 restart of the display path.
· Fail-closed: an underrun blanks the affected lines (R-17-030p); the cost is what the display was showing, a consent prompt included.
· Trace: CJ-ISOL · [§15](verification-maximal-os.md#r-15-231)

**R-15-232** IS: The internal display link is dedicated, fixed-function, and point-to-point (eDP for laptop-class, MIPI DSI for phone or tablet) with no hot-plug negotiation against an untrusted device.
· Accept: its security is minimal attack surface, not a cryptographic property.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-232)

**R-15-233** MUST: External display is output-only over DisplayPort Alternate Mode on USB-C or a dedicated DisplayPort connector: it carries the scanout controller's native DisplayPort lanes and opens no path into memory.
· Accept: alt-mode entry is a fixed-function sequencer (the DisplayPort alt mode alone, not general vendor-defined messages); USB4/Thunderbolt DisplayPort tunneling stays excluded.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-233)

**R-15-234** MUST: EDID is accepted only up to a tight, composition-time block cap sized to the 128–512-byte range real displays span, not the format's 32 KB maximum, and is parsed copy-once by the schema-bounded Narcissus decoder; anything beyond the cap is rejected.
· Accept: the cap is a composition constant; the parser is a §5 Narcissus artifact.
· Trace: CJ-FORMAT · [§15](verification-maximal-os.md#r-15-234)

**R-15-235** MUST: Enabling an external monitor is a powerbox-mediated act gated on user consent; multi-stream daisy-chaining, HDCP, DP++ dual-mode, and any Thunderbolt or USB4 tunnel stay excluded.
· Accept: single-stream display output only.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-235)

**R-15-236** MUST: The panel's timing controller is fixed-function with no programmable firmware: no smart-panel scaler or overdrive DSP blob. Scaling, colour management, and temporal processing are host software on the V-class cores.
· Accept: a fixed-function panel-self-refresh block is admissible on the sensor and radio fixed-function terms (no writable program).
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-236)

**R-15-236a** MUST: The panel's per-pixel uniformity correction is a static table fixed at manufacture, attested with the devicetree, and applied by fixed-function timing-controller logic or by the host colour pipeline. Per-pixel aging compensation, which integrates cumulative drive history into panel-resident writable memory, is excluded, so the emissive technology is free except of this constraint.
· Accept: no panel-resident writable store accumulates displayed-content statistics, and the correction table is a devicetree-attested constant.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-236a)

**R-15-236b** MUST: Refresh rate and pixel format are enumerated composition-time constants, and the scanout reservation (TDM slice, bank-group binding, line-buffer FIFO) is admitted at the fastest line period and widest pixel the profile carries, so slower rates and narrower formats run inside it as slack. Selecting among the enumerated rates is not a global mode change and re-assigns no operating point, TDM schedule, or watchdog window.
· Accept: one reservation, sized to the maximum mode, covers every admitted rate and format; the audited selection channel is log₂(#rates) bits per event.
· Trace: CJ-WCET, CJ-CERISE · [§15](verification-maximal-os.md#r-15-236b)

**R-15-236c** MUST NOT: Presentation timing is never a function of composition-completion time; Adaptive-Sync and any other variable-refresh mechanism is absent, because a frame period following render cost carries the cost of every composited surface to any holder of one surface's present callback and to an external monitor watching vertical blanking.
· Accept: no variable-refresh mechanism exists; the frame period is a constant of the selected rate.
· Trace: CJ-NI, CJ-CERISE · [§15](verification-maximal-os.md#r-15-236c)

**R-15-236d** IS: High dynamic range decomposes into a framebuffer format (a bandwidth term of R-15-236b's maximum), a transfer function and tone mapping that are colour management already assigned to host software by R-15-236, and static mastering metadata carried as a fixed-size block under R-15-234's bounded-EDID and Narcissus discipline.
· Accept: HDR adds no device, no on-panel program, and no parser, only a schema and a bandwidth figure.
· Trace: CJ-CERISE, CJ-FORMAT · [§15](verification-maximal-os.md#r-15-236d)

**R-15-236e** MUST NOT: No tone mapping or dimming decision is executed by the display: display-executed dynamic-metadata systems and panel-side content analysis driving a local-dimming zone array are excluded, and any zone values are computed host-side and shipped over the fixed-function link. A fixed-function luminance limiter holding no accumulated state remains admissible.
· Accept: the panel runs no program; the only content-derived values crossing the link are host-computed.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-236e)

**R-15-237** IS: The touchscreen is a projected-capacitive raw-capacitance AFE under the sensor doctrine: every baselining, rejection, touch, and gesture stage is host software, never a tuned-firmware touch controller. Resistive touch is not used.
· Accept: no touch-controller firmware exists.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-237)

**R-15-238** MUST NOT: No fixed-function codec blocks exist (unpatchable silicon parsers: grammar, not geometry); codecs run as contained software on V-class cores behind verified framing parsers.
· Accept: no codec block appears in the device inventory.
· Trace: CJ-FORMAT · [§15](verification-maximal-os.md#r-15-238)

**R-15-239** MUST NOT: The GPU command-processor surface class is deleted: there is no GPU, no GPU driver, and no separate graphics-driver trust surface. Work reaches V/M cores as ordinary capability-confined native code and ring-fed data.
· Accept: the render and compositor servers, safe Rust on RVV, are that driver.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-239)

### 15.30 Watchdog, entropy, and anti-features

**R-15-240** MUST: There is exactly one hardware watchdog and it is non-deletable: the RoT's always-on timer (bark/bite) on an independent slow clock, a failure domain disjoint from the cores, the main clock tree, and the scheduler.
· Accept: it is windowed (early pets fault as well as late) with bounds from the §11 schedule theorem; pets are RoT-nonce challenge-responses from a single capability holder; no external watchdog ICs and no PMIC watchdogs exist.
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-240)

**R-15-241** MUST: The TRNG is in the RoT and the verified DRBG in the crypto core; because a draw is internal and no input trace captures it, every draw is accounted for in the deterministic-replay nondeterminism record: verbatim where the drawn value is public, as a sealed commitment where it is secret.
· Accept: all firmware is open, reproducible, and measured; the device allowlist is collapsed toward transducers and register slaves.
· Trace: CJ-NI, CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-241)

**R-15-241a** IS: The single-root rule (R-15-037) concentrates the entropy risk rather than discharging it, so the root carries obligations of its own: no other mechanism covers the case where every proof holds and the drawn value is predictable, the reductions being conditional on uniform draws (R-05-077a), the constant-time discipline constraining a draw's observable behaviour and not its distribution, and the linear nonce type forcing freshness and not unpredictability (R-05-126b).
· Accept: R-15-241b through R-15-241e are the obligations this entry quantifies over; a predictable root is a stated failure of theirs rather than a case the register leaves to the crypto core.
· Trace: CJ-CRYPTO-SPEC, CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-241a)

**R-15-241b** MUST: The noise source runs start-up health tests over a fixed sample budget before its first output leaves the RoT and continuous on-line tests thereafter, sized against the source's stochastic model, and the sole failure action is fail-stop: the root latches a failure state reported as a §16 fault class.
· Accept: no reduced-rate, best-effort, or last-known-good output path exists in hardware or firmware, so a detected failure cannot become an undetected one by degrading.
· Fail-closed: a failed health test latches the noise source off with no degraded path (R-17-030o); the cost is every operation needing fresh randomness.
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-241b)

**R-15-241c** MUST: Raw source output reaches no consumer: it is conditioned in the RoT by a vetted non-keyed cryptographic conditioner whose input entropy rate is claimed from the source's stochastic model and whose output is full-entropy at the claimed rate, with the DRBG the only interface a consumer holds.
· Accept: the entropy estimate is a stated number backed by the model, reviewable and disputable as such; no path exposes unconditioned output, the excluded supplementary analog source of R-15-244 being an input to this conditioner and not an exception to it.
· Trace: CJ-CRYPTO-SPEC, CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-241c)

**R-15-241d** MUST: The verified DRBG is instantiated from conditioned root output at a stated seed length, reseeds on stated draw-count and interval bounds and on every RoT lifecycle or lock-state transition (R-09-017, R-15-078), and carries prediction resistance across a reseed and backtracking resistance across a draw.
· Accept: the DRBG's refinement statement takes this seeding discipline as an explicit hypothesis rather than assuming a uniform seed, so the hypothesis is discharged by this entry and R-15-241b through R-15-241e rather than assumed by R-05-075.
· Trace: CJ-CRYPTO-SPEC · [§15](verification-maximal-os.md#r-15-241d)

**R-15-241e** MUST: The root takes multiple independent noise sources spanning at least two physical mechanisms into the one conditioner, each separately health-tested, with no source reaching the conditioner unattributed.
· Accept: no single hardware source's death, sticking, or narrowed distribution silently repairs or silently corrupts the root's output; the RDRAND cautionary history R-15-037 cites is thereby answered as an argument against trusting a raw source and not only against a second root, with the undetectable-trim case booked in R-17-049a.
· Trace: CJ-DEVTREE · [§15](verification-maximal-os.md#r-15-241e)

**R-15-242** MUST NOT: The anti-feature set is excluded entirely: UEFI, SMM, ACPI/AML, ME/PSP-class coprocessors, SMT, speculation, dynamic branch prediction, LR/SC reservation state and general CAS, 32-bit modes, hybrid capability mode (no DDC), legacy boot, option ROMs, and the C extension.
· Accept: none appears in the profile, the Sail model, or any RTL.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-242)

**R-15-243** MUST NOT: Also excluded: foreign computers of every stripe; discrete/opaque GPUs and fixed-function accelerator coprocessors, including SIMT GPGPU cores and fixed-function codec blocks; reactive/autonomous power management; hardware caches and cache coherence entirely; and the RVWMO weak memory model.
· Accept: each is enumerated with its replacement mechanism named.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-243)

**R-15-244** MUST NOT: Analog compute-in-memory (memristor/RRAM/PCM crossbars) is excluded: no deterministic ISA semantics to Sail-model, non-volatile analog weights are an at-rest confidentiality regression, and it presents the richest possible data-dependent power channel with a reactive calibration loop.
· Accept: admissible only as deterministic binary ReRAM/PCM storage below the §10 integrity line, or as a supplementary entropy source into the RoT conditioner (not adopted).
· Trace: CJ-SAIL, CJ-LEAK · [§15](verification-maximal-os.md#r-15-244)

**R-15-245** MUST NOT: SGX-class enclaves, ASLR, shadow stacks, and CFI/landing-pads are excluded: their threat model inverts this design, or they are obviated by proof plus CHERI and fight reproducibility and schedulability.
· Accept: no manifest-invisible memory exists that the monitor cannot inspect.
· Trace: CJ-CERISE · [§15](verification-maximal-os.md#r-15-245)

**R-15-246** MUST: Speculation-derived and hidden-state ISA features are excluded generally, per the five-part admission test, which is the standing rule that decides future extensions.
· Accept: R-15-010 governs every future amendment.
· Trace: CJ-SAIL · [§15](verification-maximal-os.md#r-15-246)

---

## §16. Reliability

### 16.1 Fault containment

**R-16-001** MUST: Any driver or server crash is contained and supervisor-restarted, and the kernel is never implicated; eager-zeroize means no residue crosses the restart.
· Accept: a crashed render, inference, or radio compartment is restarted like any other.
· Trace: CJ-KERNEL, CJ-CERISE · [§16](verification-maximal-os.md#r-16-001)

**R-16-002** IS: A radio-stack crash costs connectivity until restart, never platform integrity.
· Accept: the radio stack is wholly non-TCB (R-06-021).
· Fail-closed: a radio-stack crash stops the stack (R-17-030j); the cost is connectivity until restart.
· Trace: CJ-CERISE · [§16](verification-maximal-os.md#r-16-002)

**R-16-002a** MUST: The fault path is held to the confidentiality policy on three mechanisms: an in-model fault is secret-independent wherever a constant-time obligation binds, since CT verification makes control flow and access sequence, hence the traps reachable, functions of public inputs; the restart is paid from the faulting partition's own slots, so it moves no peer's timing; and the fault class reaches the sentinel telemetry monitor as a labeled flow over a closed enumeration rather than an ambient log.
· Accept: each of the three is already required elsewhere (R-05-062, R-07-036, R-16-013) and is stated jointly here because separately none of them reads as a confidentiality claim; the obligation this discharges is R-08-027c and what it does not reach is R-17-003a.
· Trace: CJ-NI, CJ-CT-SOUND · [§16](verification-maximal-os.md#r-16-002a)

**R-16-003** MUST: Crash consistency on the integrity path is machine-checked; user data carries checksummed CoW plus patrol scrub; ECC telemetry spans cores, scratchpads, NoC, and the main-memory SRAM array.
· Accept: each is a named mechanism with an owner.
· Trace: CJ-DEVTREE · [§16](verification-maximal-os.md#r-16-003)

**R-16-004** IS: Display underrun is a named fault class, not a cosmetic mystery: the scanout reservation being static, starving its FIFO cannot arise from contention, so an underrun is evidence of a fault on the framebuffer path and the visible blank is a caught fail-stop.
· Accept: consistent with R-15-231.
· Trace: CJ-WCET · [§16](verification-maximal-os.md#r-16-004)

### 16.2 Watchdogs and escalation

**R-16-005** MUST: Watchdogs are layered: the sentinel-resident monitor responds surgically (restart, revoke, roll back) before escalation, and the RoT watchdog is the last resort, where bite equals reset, safe because state is transactional and nothing is lost but uncommitted work.
· Accept: the two tiers are distinct components with distinct failure domains.
· Fail-closed: watchdog bite is reset (R-17-030c); the cost is uncommitted work, bounded into a recovery state by R-16-007.
· Trace: CJ-DEVTREE · [§16](verification-maximal-os.md#r-16-005)

**R-16-006** IS: The bark's notice window is one slot, not trap latency, because asynchronous interrupt delivery does not exist: the bark sets a pending bit the boundary-timer handler reads, so a core alive but wedged is reached at its next slot boundary.
· Accept: the surgical tier is slot-granular and the sub-slot response is the bite alone, a deliberate narrowing of the escalation ladder's top rung, booked in §17 rather than absorbed (R-07-047).
· Trace: CJ-WCET · [§16](verification-maximal-os.md#r-16-006)

**R-16-007** MUST: Reset-loop abuse is bounded by boot counting into a minimal recovery state, so the worst case is bounded downtime, not permanent DoS; thermal fail-stop rides the same transactional safety.
· Accept: boot counting is an RoT duty (R-09-028).
· Trace: CJ-DEVTREE · [§16](verification-maximal-os.md#r-16-007)

**R-16-008** IS: Rollback is both automatic and user-driven, and the user-driven path adds recovery reach without adding trusted surface: the UI only stages, while the A/B transactor and RoT enforce the signed-root check, the anti-rollback floor, and the credential gate.
· Accept: the trust split is specified once, in §11 (R-11-002).
· Trace: CJ-DEVTREE · [§16](verification-maximal-os.md#r-16-008)

### 16.3 Injected faults

**R-16-008a** IS: An injected fault (voltage and clock glitching, laser injection, electromagnetic fault injection) puts the machine outside its own semantics, so no theorem stated over the Sail model reaches it and the platform's answer is detection and containment rather than shielding. The enclosure's attenuation of the electromagnetic variant is narrowing at the boundary and nothing below is claimed from it.
· Accept: no statement in this register discharges an injected fault by citing R-15-155's attenuation; the mode available to this class is *detected* and never *absent* or *proved*.
· Trace: CJ-SAIL · [§16](verification-maximal-os.md#r-16-008a)

**R-16-008b** IS: The mechanism catching each injection is enumerated rather than aggregated: a fault in stored state is corrected by the pervasive ECC and is a fail-stop event where uncorrectable (R-15-175, R-15-177); a fault corrupting a capability traps on the validity tag or the bounds check (R-15-204); a fault in live kernel state is confined to one partition by the multikernel and answered by crash-only restart (R-07-009, R-16-001); a wedged or runaway core is reached by the layered watchdogs (R-16-005, R-16-006). The two cases none of them reaches are R-16-008c's and R-16-008d's; the transient datapath strike is reached by neither and is booked at R-17-058b.
· Accept: every injection this entry lists names the requirement that catches it, and the cases named as unreached are exactly the two positions plus the booked residual, so the class carries no unattributed remainder.
· Trace: CJ-SAIL, CJ-KERNEL · [§16](verification-maximal-os.md#r-16-008b)

**R-16-008c** MUST: Three sequences carry a compiler-emitted running control-flow signature and no other sequence does: the measured-boot chain's per-stage verify-then-transfer, the credential comparison at the RoT gate, and the lifecycle transition over one-way fuse state. Each basic block of a protected region folds a compose-time constant into a signature register and the region's exit compares the accumulation against the value its control-flow graph predicts, a mismatch raising the fail-stop class an uncorrectable ECC event raises. The decision each sequence reaches is encoded so that omitting work refuses: acceptance is a multi-bit token computed from the comparison, which no fall-through, skipped branch, or truncated region produces, and the comparison is performed twice with the signature check between the two.
· Accept: the set is these three and extending it is an amendment, not a reading; the predicted value is derived from the region's control-flow graph rather than annotated by hand, so where the artifact passes admission the instrumentation is checked on the final binary with the other type-level obligations (R-05-029) and where it lives in the boot ROM it is fixed at tapeout and measured with the ROM (R-09-002); the emitted instructions are ordinary instructions and enter the syntax-directed WCET cost (R-05-102). Coverage is evidence and is booked at R-17-058b.
· Fail-closed: a control-flow signature mismatch raises the class an uncorrectable ECC event raises (R-17-030n); the cost is the protected sequence and the boot or credential decision it carried.
· Trace: CJ-COMPCERT, CJ-TAL-SOUND, CJ-WCET · [§16](verification-maximal-os.md#r-16-008c)

**R-16-008d** MUST: The S-class sentinel core is realized as a detection-only lockstepped pair presenting one architectural core: two instances execute the same instruction stream, a comparator checks their committed results and bus traffic, and a divergence latches a fail-stop reported to the RoT rather than to the sentinel, whose response is the watchdog bite R-16-005 already defines.
· Accept: the sentinel is the one core software redundancy cannot serve, because the pass would run on the core being doubted and the tier above catches a sentinel that stops (R-16-005) and not one that continues having suppressed an event; determinism (R-15-100, R-16-011) makes the comparison exact, so there is no false-divergence rate; the comparator holds no architectural state and changes no committed result, so the Sail model and R-18-010's refinement obligation are unchanged, on the ground R-15-157 states for radiation hardening.
· Fail-closed: a lockstep divergence latches a fail-stop to the RoT (R-17-030n); the cost is the sentinel, and with it the tier that watches the rest.
· Trace: CJ-RTL-SAIL, CJ-DEVTREE · [§16](verification-maximal-os.md#r-16-008d)

**R-16-008e** MUST NOT: No control-flow-signature hardware, no landing-pad or shadow-stack mechanism, and no ISA surface of any kind is added for R-16-008c, which is compiler-emitted instrumentation in three named regions; and no core other than the S-class pair is replicated, no comparator votes, and no third instance exists, so masking, its voting-correctness proof, and the explicit fault model such a proof needs are all absent.
· Accept: R-15-044 and R-15-245 stand unamended, the frozen profile gains no instruction and no CSR, and the core-class table carries replication for the S-class row alone; a request for masking is a G5 deployment question against the redundant-execution disposition, not a platform change.
· Trace: CJ-SAIL, CJ-RTL-SAIL · [§16](verification-maximal-os.md#r-16-008e)

### 16.4 Time-to-remediation

**R-16-009** MUST: Time-to-remediation is a first-class property budgeted separately from time-to-full-fix: a live remote exploit is answered at detection latency, the sentinel triggering an attested transition that revokes the compromised compartment's capabilities, withdraws its rings, and fails its surface closed.
· Accept: this needs no new proof, because narrowing authority is monotone and cannot violate a safety theorem; the §6 checker still gates any replacement code.
· Fail-closed: containment withdraws the compromised compartment's authority and runs the surface degraded until remediation (R-17-030d); the cost is that surface's duty cycle.
· Trace: CJ-CERISE, CJ-NI · [§16](verification-maximal-os.md#r-16-009)

**R-16-010** IS: Containment latency is therefore the §8 bounded-revocation constant, budgeted like detection latency, while the full proof-carrying fix follows off the critical path.
· Accept: the fast path degrades capability under proof and the slow path restores it with proof; neither ships unproven code.
· Trace: CJ-CERISE · [§16](verification-maximal-os.md#r-16-010)

### 16.5 Diagnosis by deterministic replay

**R-16-011** MUST: Deterministic builds give deterministic failure reproduction, and diagnostics are capability-scoped; schedule-fixed frequencies, fixed-latency divide/FPU and atomic RMW, static-only control-flow prediction, and Ztso ordering extend determinism to timing-sensitive failure reproduction.
· Accept: each enabling property is a §15 mandate.
· Trace: CJ-WCET, CJ-SAIL · [§16](verification-maximal-os.md#r-16-011)

**R-16-012** MUST NOT: No verbose logging mode exists: one that captured data-dependent runtime state would be an unlabeled cross-boundary channel the non-interference theorem forbids and a forensic surface on a seized device.
· Accept: capability use *is* declassification, so an ambient log has no lawful form.
· Trace: CJ-NI · [§16](verification-maximal-os.md#r-16-012)

**R-16-013** MUST: A fault raises a bounded, authenticated crash record through the sentinel telemetry monitor: fault class, faulting capability and program counter, compartment identity, the ECC or tag-trap cause, and a sealed input trace, schema-bounded like any §5 wire format, never free-form text.
· Accept: the record's schema is a Narcissus descriptor.
· Trace: CJ-FORMAT · [§16](verification-maximal-os.md#r-16-013)

**R-16-014** IS: Because the machine is deterministic, that trace re-runs bit-exact off-device on the same semantics the silicon is proven to refine, so verbosity moves off the device rather than streaming from it at runtime.
· Accept: off-device introspection is unbounded and carries no on-device confidentiality cost.
· Trace: CJ-SAIL, CJ-RTL-SAIL · [§16](verification-maximal-os.md#r-16-014)

**R-16-015** IS: Determinism holds *given the inputs and the recorded nondeterminism*, and the second half is enumerated as exactly four sources: every draw from the single entropy root (protocol nonces, IVs, ephemeral key material, blinding factors); the link-layer address draws behind MAC randomization; raw counter reads by holders of the fine-grained-time permission; and the physical event stream the sentinel consumes.
· Accept: the list is closed by amendment to this register; omitted, a replay diverges at the first draw. No degraded or fuzzed timing value appears among the four, there being no such mechanism to record (R-08-031a).
· Trace: CJ-NI · [§16](verification-maximal-os.md#r-16-015)

**R-16-016** MUST: Public nondeterminism is recorded verbatim: the drawn link-layer address, counter values, and the sentinel's physical-event stream.
· Accept: each discloses nothing the crash record does not already carry, and replay reproduces them exactly.
· Trace: CJ-NI · [§16](verification-maximal-os.md#r-16-016)

**R-16-017** MUST: Secret nondeterminism is recorded as a sealed commitment and never as a value: the trace carries a hash over the draw, sealed to the RoT, and off-device replay substitutes its own entropy.
· Accept: writing DRBG seeds or draws verbatim would place live key material into an artifact designed to leave the device.
· Trace: CJ-CRYPTO-SPEC, CJ-NI · [§16](verification-maximal-os.md#r-16-017)

**R-16-018** IS: Substitution is sound because the crypto is constant-time, not because the values are unimportant: every secret-touching binary is CT-verified, so its control flow and memory-access sequence are secret-independent by construction and a substituted draw reproduces the same instruction sequence, addresses, capability operations, and fault.
· Accept: the soundness of this clause is exactly as broad as the CT obligation's scope.
· Trace: CJ-CT-SOUND · [§16](verification-maximal-os.md#r-16-018)

**R-16-019** IS: The bit-exact claim is precise rather than weakened: replay is exact in control flow, capability operations, schedule, and fault reproduction everywhere, and exact in *values* everywhere outside the secret-entropy cone.
· Accept: the two scopes are stated separately.
· Trace: CJ-CT-SOUND · [§16](verification-maximal-os.md#r-16-019)

**R-16-020** MUST: Where a fault turns on one specific draw, the commitment lets a candidate value be checked rather than guessed, and unsealing the actual draw is a powerbox-mediated declassification gated behind the RoT lifecycle debug state.
· Accept: unsealing is never a property of the ordinary crash record.
· Trace: CJ-NI, CJ-DEVTREE · [§16](verification-maximal-os.md#r-16-020)

**R-16-021** MUST: On-device verbose detail, where genuinely needed, is a capability-scoped, confidentiality-labeled diagnostic sink gated behind RoT lifecycle state and fused off in production, so a dump crossing a confidentiality domain is a powerbox-mediated declassification and never an ambient spew.
· Accept: the gate is the same one debug and trace receive (R-15-078).
· Trace: CJ-NI · [§16](verification-maximal-os.md#r-16-021)

**R-16-022** IS: A crash record leaving the device carries the sealed trace against the reproducible base image's signed root, not a secret payload, so the fault reproduces for anyone without disclosing user data, at the cost, booked in §17, that a draw-dependent fault is not reproducible from the exported record alone.
· Accept: the two-class entropy record is what keeps this true.
· Trace: CJ-NI · [§16](verification-maximal-os.md#r-16-022)

---

## §17. Residual Risks

*§17 is a register of ceilings rather than obligations. Its entries are therefore mostly `IS`: each states a residual that must remain **stated**, and its acceptance criterion is that the residual is booked with its owner and scope rather than absorbed into a guarantee. A §17 entry silently dropped from a future revision is a spec defect in the same sense R-05-153 defines.*

### 17.1 The index

**R-17-001** IS: Residuals are grouped by trust source in an index table: proof gap (deferred, not assumed), spec gap (crown jewels), physical/fab gap, human consent, hardness assumption, and commercial acceptance.
· Accept: every §17 entry belongs to exactly one group, and every group's listed residuals have entries below.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-001)

**R-17-001a** MUST: Coverage is claimed top down rather than by enumerated archetype: every boundary this specification names carries, against every property in the coverage vocabulary, either a requirement that discharges it or a §17 residual that books it. A boundary-and-property pair carrying neither is a spec defect in the sense R-05-153 defines, not an omission left for a reader to notice, and the reader-facing inventory of removed bug classes is a summary of this argument rather than the argument itself.
· Accept: the boundaries and the properties are each enumerated exactly once, in the artifact R-17-001b requires and not in the prose that quantifies over them; every pair drawn from the two enumerations appears there exactly once; and every pair cites at least one live entry of this register. `tools/check.ps1` decides all three, so an uncovered pair is a failing check rather than a finding somebody has to make.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-001a)

**R-17-001b** MUST: The coverage matrix exists as a single enumerated artifact, [coverage-matrix.md](coverage-matrix.md), carrying the boundary enumeration, the property enumeration, and one row per pair of them with its construction, its discharge mode, and the requirements that carry it. Like the frozen profile, the absence contract, and the crown-jewel inventory it is a *derived view*: it states no obligation of its own, cites the governing requirements for every row, and is defective, never authoritative, where it disagrees with this register.
· Accept: the artifact exists; every requirement it cites resolves here; and the cell conditions of R-17-001a hold over its own two enumerations, so the coverage argument is computed from the register rather than restated beside it. Each row's discharge mode reports how its cited requirements carry the pair, and the view introduces no obligation and no vocabulary of its own.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-001b)

### 17.2 Timing and scheduling

**R-17-002** IS: The transient-execution, branch-predictor-state, LR/SC reservation-granule, DVFS/frequency, cross-domain coherence-traffic, and scheduler/slack channel classes are each *deleted* by a named construction rather than mitigated; the rest are narrowed by partitioning, `fence.t`, eager zeroize, gated clock resolution, and the fixed-latency timing mandates.
· Accept: each deletion names the construction that achieves it; no general timing guarantee is claimed, and budget/partition granularity scales with assurance tier.
· Trace: CJ-ISOL, CJ-LEAK · [§17](verification-maximal-os.md#r-17-002)

**R-17-003** IS: The NI ⋈ timing seam's residual is the composition proof itself, plus any channel below partitioning granularity.
· Accept: statically-predicted wrong-path fetch reads flat SRAM at fixed latency with no I-cache, so that residual footprint is deleted rather than partitioned.
· Trace: CJ-NI, CJ-ISOL · [§17](verification-maximal-os.md#r-17-003)

**R-17-003a** IS: The fault path's last case is booked rather than closed: a compartment holding no platform secret carries no constant-time obligation, so whether it faulted and in which class can be a function of its own data, and that class travels to the sentinel and onward in an exported crash record.
· Accept: what bounds the channel is the record's shape rather than a proof (a closed fault-class enumeration, a schema-bounded record, no free-form text, and no data-dependent payload, per R-16-013), so the disclosure is coarse and countable; the two mechanisms that do close their cases are R-16-002a's first and second.
· Trace: CJ-NI · [§17](verification-maximal-os.md#r-17-003a)

**R-17-003b** IS: The seam's spatial term is graded rather than uniform: disjoint macro or tier binding leaves no shared address or data path to contend for and no arbiter whose decision another island's activity could reach, while two low-sensitivity islands sharing a macro have their contention term scheduled away by the memory controller's static per-island arbitration and retain the macro's shared periphery, power delivery, and thermal mass, which is the physical residual (R-17-058) read on the memory array rather than on the crypto core. Neither case is carried by a theorem: the non-interference statement both are stated against is the NoC/island isolation model, which is not authored.
· Accept: the inventory row and the coverage cell read absent for the disjoint binding and residual for the shared macro, and neither reads proved while that model is unauthored (R-15-211, R-15-225, R-15-228); whole-macro or whole-tier exclusivity is mandatory for high-assurance islands (R-15-226), so no crown-jewel domain sits inside the shared-macro case, and the shared case is narrowed by scheduling rather than by throttling (R-15-227).
· Trace: CJ-ISOL, CJ-NI · [§17](verification-maximal-os.md#r-17-003b)

**R-17-004** IS: The population wall: a non-work-conserving frame divides rather than shares, so discretionary capacity is divided among live compartments and no scheduling work recovers the difference.
· Accept: the §11 population rungs change the *shape* of the division, not the fact of it.
· Trace: CJ-WCET · [§17](verification-maximal-os.md#r-17-004)

**R-17-005** IS: Cost (1): background share collapses as roughly 1/n and the absolute numbers are small: on the reference instantiation a background origin at the 32-rung holds on the order of one percent of one core, around four percent at the 8-rung. The foreground is fast and the background very nearly stopped.
· Accept: this is a materially different performance *shape* from a work-conserving machine that is merely slower, and it is stated as the shape to plan against.
· Fail-closed: the background floor is what the rest of the register degrades toward rather than a response of its own (R-17-030k); the cost is background progress.
· Trace: CJ-WCET · [§17](verification-maximal-os.md#r-17-005)

**R-17-006** IS: Cost (2): idle discretionary time is structurally unreclaimable and will remain so, because the donation mechanism that would reclaim it *is* the channel whose deletion the design is buying.
· Accept: the mixed-load figure in the performance companion scores idle-slot waste at low population and does not cover this; past a few discretionary compartments per core the division dominates.
· Trace: CJ-WCET, CJ-NI · [§17](verification-maximal-os.md#r-17-006)

**R-17-007** IS: Cost (3): the rung index is a residual channel: every discretionary compartment reads its own slot width, hence the rung, hence a log-coarse count of live discretionary compartments, and the focus permutation timestamps focus changes to the unfocused.
· Accept: both are user-originated, the state space is a handful of rungs, and the rate is bounded by human lifecycle actions, so it is a coarse low-bandwidth channel an origin can observe but not clock, a channel nonetheless, and the price of not making a tab an attested global transition.
· Trace: CJ-NI · [§17](verification-maximal-os.md#r-17-007)

**R-17-008** IS: The product-level statement belongs beside the §1 throughput trade rather than behind it: this is a few-active-things machine, retaining deep tab and app sets as state while running a small number at a time.
· Accept: the statement appears in the goals-adjacent material, not only here.
· Trace: CJ-WCET · [§17](verification-maximal-os.md#r-17-008)

### 17.3 Consent

**R-17-009** IS: For system-fixed flows the §8 theorem is absolute non-interference; for user-authorized flows it is non-interference *modulo* robust, delimited declassification, and that qualifier is where the ceiling sits.
· Accept: the release is delimited and robust, so the dominant real-world path is inside the proof rather than near-vacuously admitted or left outside it.
· Trace: CJ-NI · [§17](verification-maximal-os.md#r-17-009)

**R-17-010** IS: Cost (1): the consent TCB genuinely grows: the powerbox, the trusted-path agent, and the RoT secure-attention indicator are small and verified but genuinely trusted, against the delete-rather-than-defend grain, accepted for want of a way to gate authority-crossing consent without some trusted mediator.
· Accept: its input edge is bounded by RoT-latched front-end ownership, so the addition is a fixed threshold-and-centroid reducer plus a latched register rather than a programmable touch DSP, the smallest available closure, but an addition, and one shifting a share of consent-path integrity onto the RoT.
· Trace: CJ-NI, CJ-DEVTREE · [§17](verification-maximal-os.md#r-17-010)

**R-17-011** IS: The temporal scope of a grant is bounded, not evaluated: *while-active* stays strictly weaker than one-shot, a compromised compositor colluding with a compromised app retaining a sensitive grant up to the ceiling, bounded and physically legible rather than unbounded and silent, but retained.
· Accept: consistent with R-08-043.
· Trace: CJ-NI · [§17](verification-maximal-os.md#r-17-011)

**R-17-012** IS: Cost (2): the delimited-release bound and the robust-declassification statement are new crown-jewel specs: a release bound letting the powerbox mint wider than the user named verifies perfectly and leaks.
· Accept: both appear in the crown-jewel inventory.
· Trace: CJ-NI · [§17](verification-maximal-os.md#r-17-012)

**R-17-013** IS: Cost (3): the user is outside the theorem. An unspoofable, attested, correctly-bounded prompt still rests on the human granting the right authority; *the user consented to the wrong thing* is the irreducible ceiling no proof reaches.
· Accept: no claim elsewhere in the specification implies otherwise.
· Trace: CJ-NI · [§17](verification-maximal-os.md#r-17-013)

**R-17-013a** IS: The autonomous-agent residual: the §12 posture bounds what an agent may hold, and two costs remain that belong to the residual rather than to the mechanism.
· Accept: both are enumerated below, and neither is claimed to be closed.
· Trace: CJ-NI · [§17](verification-maximal-os.md#r-17-013a)

**R-17-013b** IS: Cost (1): prompt injection is not answerable at this layer. An agent reading attacker-influenced content can be induced to request authority it should not; confinement bounds what it may hold, never what it may be made to ask.
· Accept: the claim recorded for agents is containment and legibility of the request, not correctness of the request.
· Trace: CJ-NI · [§17](verification-maximal-os.md#r-17-013b)

**R-17-013c** IS: Cost (2): the consent ceiling of R-17-013 is exercised at machine rate, the human adjudicator being the scarce resource; standing grants relieve the fatigue by widening and lengthening the hold, which is where the bound weakens.
· Accept: no mechanism is claimed to decide the fatigue-versus-scope trade on the user's behalf.
· Trace: CJ-NI · [§17](verification-maximal-os.md#r-17-013c)

**R-17-013d** IS: No theorem is stated over the model's behavior: it runs off-platform or as data on the inference server, and the claim is bounded authority and attributable action, never sound judgment.
· Accept: no seam lemma or inventory entry quantifies over model output.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-013d)

### 17.4 Proof-gap residuals

**R-17-014** IS: The non-interference theorem is fresh (seL4-NI in method, not maturity) with three dimensions none of seL4's proof reaches: the multikernel composition, the purecap CHERI-C semantics, and robust delimited declassification.
· Accept: booked as freshness, not trust; its silent failure mode, a too-weak-but-faithful NI specification, is the crown-jewel risk the security-policy model already carries.
· Trace: CJ-NI · [§17](verification-maximal-os.md#r-17-014)

**R-17-015** IS: Deterministic replay is bit-exact modulo the secret-entropy cone, with two booked limits: a fault turning on one specific secret draw does not reproduce from the exported record alone, and the soundness of entropy substitution rests on the constant-time property rather than on anything replay establishes.
· Accept: replay is a *consumer* of the CT residual rather than an independent guarantee.
· Trace: CJ-CT-SOUND · [§17](verification-maximal-os.md#r-17-015)

**R-17-016** IS: Specification gap: proofs match the spec, never intent. The crown-jewel spec set is enumerated, and enumerated in exactly one place: status is *conferred* by the requirement that asserts it of a particular specification, and the enumeration those requirements quantify over is the inventory R-17-016a requires rather than a roll-call restated in this entry, which would be a second statement of membership free to drift from the first.
· Accept: the list is closed by amendment to this register; every crown jewel has a `CJ-` trace target used by the sections that constrain it; and the conferring requirements and the inventory are checked against each other in both directions by `tools/check.ps1`, so a specification granted the status without a row, or a row without a requirement, is a finding rather than a silent divergence.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-016)

**R-17-016a** MUST: The crown-jewel inventory exists as a single enumerated artifact, [crown-jewels.md](crown-jewels.md), carrying one row per crown-jewel specification with its `CJ-` trace target, the requirements that constrain it, and its authored/partial/not-authored status. Like the frozen profile and the absence contract it is a *derived view*: it states no obligation of its own, cites the governing requirements for every row, and is defective, never authoritative, where it disagrees with this register.
· Accept: the artifact exists; every requirement asserting crown-jewel status for a specification is cited by it; and every `CJ-` target in the trace-target table above is accounted for, each either as a specification row or as a theorem target whose premise is a specification row. `tools/check.ps1` checks all three conditions. The inventory is the §5 review gate's subject (R-05-150) and the specification workstream's work list, its status column the countable form of R-01-003's as-existing position.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-016a)

**R-17-016b** IS: Agreement gap: a verified decoder establishes that this platform accepts exactly the language its descriptor defines, and canonicity (R-05-051a) that a value leaves it under exactly one encoding, but neither reaches the language an independent implementation of the same format accepts. A parser differential is a disagreement between two parties, so no single-party proof has the quantifier to exclude it, however faithfully the descriptor is transcribed (R-05-046).
· Accept: the residual stays booked as evidence rather than absorbed: the differential oracles (R-05-045, R-05-051) are the instrument and enter no trust base, no requirement claims freedom from parser differentials, and canonicity is nowhere read as agreement. The consequence is bounded to the semantic class by the unconditional memory-safety property (R-05-047) and compartment containment, never reaching the memory-safety one.
· Trace: CJ-FORMAT · [§17](verification-maximal-os.md#r-17-016b)

### 17.5 The hardware seam register

**R-17-017** MUST: The hardware seams are a named register with owners rather than an emergent property, and a future mechanism's admission review walks this list *before* the five-part admission test's clauses, because at this design's maturity a gap is a seam, not a subsystem.
· Accept: a mechanism admitted alone is not admitted until its meetings are; the register below is the standing companion the five-part test lacked.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-017), [§17](verification-maximal-os.md#r-17-017-2)

**R-17-018** IS: Seam: **interrupts ⋈ the cyclic executive**, dissolved rather than reconciled: asynchronous delivery deleted, arrival latched state read by ordinary loads, the slot-boundary timer the sole asynchronous trap, service latency a schedule corollary, the residual a watchdog bark noticed at slot rather than trap latency.
· Accept: discharged by R-07-038 through R-07-047 and R-16-006.
· Trace: CJ-KERNEL · [§17](verification-maximal-os.md#r-17-018)

**R-17-019** IS: Seam: **`fence.t` ⋈ the state inventory**, the architectural / partition-owned / flushed / stream-determined four-class map discharged against the RTL, the store buffer alone in the flushed class, the register files in the context-switched class under the kernel's total restore, and the fetch buffer and pipeline latches in the stream-determined class the fence's drain empties.
· Accept: discharged by R-15-213 through R-15-217 and R-07-015, the four classes being exhaustive over the RTL state inventory so that an unmapped structure is a refinement failure rather than a silent remainder.
· Trace: CJ-ISOL, CJ-RTL-SAIL · [§17](verification-maximal-os.md#r-17-019)

**R-17-020** IS: Seam: **the memory path ⋈ power gating**, dissolved rather than reconciled: the memory path holds no key, counter, or root register, so nothing must stay powered across standby to preserve an invariant.
· Accept: discharged by R-15-191 and R-15-199.
· Trace: CJ-ISOL · [§17](verification-maximal-os.md#r-17-020)

**R-17-021** IS: Seam: **scanout ⋈ the TDM fabric**, a standing admitted reservation, underrun a §16 fault class, the scanned line crossing no cryptographic stage.
· Accept: discharged by R-11-008, R-15-230, and R-16-004.
· Trace: CJ-WCET · [§17](verification-maximal-os.md#r-17-021)

**R-17-022** IS: Seam: **the memory tiers ⋈ inspectability**, graded on one die, the logic tier imaged and the passive upper tiers un-imaged but incapable of execution.
· Accept: discharged by R-15-160, R-15-161, and R-17-061.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-022)

**R-17-023** IS: Seam: **revocation ⋈ the schedule**. Containment is the epoch flip, the sweep a sized background slot class.
· Accept: discharged by R-08-006, R-08-007, and R-11-008.
· Trace: CJ-CERISE, CJ-WCET · [§17](verification-maximal-os.md#r-17-023)

**R-17-024** IS: Seam: **the write path ⋈ the ECC and tag planes**: no sub-granule write reaches the array, the controller-to-array path being the scope of the whole-unit rule.
· Accept: discharged by R-15-181 through R-15-183, with the controller's read-modify-write stage the one re-encoding point and its verify-before-merge obligation what reconciles it with the end-to-end claim (R-15-176).
· Trace: CJ-SAIL · [§17](verification-maximal-os.md#r-17-024)

**R-17-025** IS: Seam: **clock domains ⋈ determinism**, mesochronous by construction, with three asynchronous boundaries terminated and unmodeled.
· Accept: discharged by R-15-195 through R-15-197.
· Trace: CJ-WCET · [§17](verification-maximal-os.md#r-17-025)

**R-17-026** IS: Seam: **boot ⋈ storage**, stage zero named: ROM, OTP, fixed-address NAND, no grammar.
· Accept: discharged by R-09-003 through R-09-006.
· Trace: CJ-DEVTREE · [§17](verification-maximal-os.md#r-17-026)

**R-17-027** IS: Seam: **calibration ⋈ attestation**, factory-measured, signed, envelope-bounded.
· Accept: discharged by R-15-126, R-15-127, and R-17-062.
· Trace: CJ-DEVTREE · [§17](verification-maximal-os.md#r-17-027)

**R-17-028** IS: Seam: **inspectability ⋈ density**, IRIS scoped to the logic die, the memory stack checked at runtime instead.
· Accept: discharged by R-15-160 and R-15-161.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-028)

**R-17-029** IS: Seam: **debug ⋈ lifecycle**, electrically fused absent in production, an RTL ⊑ Sail obligation.
· Accept: discharged by R-15-078 and R-15-079.
· Trace: CJ-RTL-SAIL · [§17](verification-maximal-os.md#r-17-029)

**R-17-030** IS: Seam: **eUICC ⋈ the platform**, a synchronous host-clocked interface block, its foreign grammar behind a verified parser.
· Accept: discharged by R-12-045 through R-12-047.
· Trace: CJ-FORMAT · [§17](verification-maximal-os.md#r-17-030)

### 17.6 The fail-closed seam register

**R-17-030a** MUST: The fail-closed seams are a named register with owners, on R-17-017's rule applied to the other axis: a refusal admitted alone is not admitted until its meetings are, because each refusal is booked honestly in its own section and the position their conjunction describes is stated in none of them.
· Accept: every mechanism whose failure action is to stop, refuse, erase, or cut appears below or is a review-gate finding; the composition is owed here rather than in the coverage matrix, which decomposes by boundary and cannot see a device silenced by mechanisms each behaving correctly at its own.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-030a)

**R-17-030b** IS: Fail-closed seam **thermal trip ⋈ the work in progress**: critical temperature triggers a rare attested global transition exempting nothing that is running (R-15-193), the correct trade against continuous throttling's data-dependent channel and nonetheless a denial the platform performs on itself.
· Accept: reachable by an adversary who can raise die temperature and by an ordinary hot enclosure, so it is not conditioned on an attacker being present.
· Trace: CJ-NI · [§17](verification-maximal-os.md#r-17-030b)

**R-17-030c** IS: Fail-closed seam **watchdog bite ⋈ restart cadence**: bite equals reset and is safe because state is transactional (R-16-005), with boot counting bounding the loop into a minimal recovery state so the worst case is bounded downtime (R-16-007).
· Accept: the one member already composed with its own abuse case before this register existed, and the shape the others are held to.
· Trace: CJ-DEVTREE · [§17](verification-maximal-os.md#r-17-030c)

**R-17-030d** IS: Fail-closed seam **containment ⋈ the attacked surface's duty cycle**: containment is fast and monotone while full remediation stays proof-gated, so the surface runs degraded between the two and that window is budgeted (R-16-009, R-17-035); what is budgeted is one window, and repeated forcing is visible only as windows per unit time.
· Accept: an adversary who can force the degraded subset on demand holds durable partial denial under cover of containment having worked, which R-16-009's per-incident budget cannot express; the obligation that makes it expressible is R-17-030m.
· Trace: CJ-CERISE · [§17](verification-maximal-os.md#r-17-030d)

**R-17-030e** IS: Fail-closed seam **admission refusal ⋈ delivery**: a certifier that cannot emit a derivation refuses a safe program (R-17-033), and because there is no interim weakening the cost lands on delivery rather than on a device in a user's hands (R-13-022); the same pass rejects a composition whose per-mode power vector would switch off an SRAM array some admitted capability can still reach (R-15-189g).
· Accept: the one member whose denial cannot reach a running unit, named so that the register is not read as uniformly a field risk.
· Trace: CJ-TAL-SOUND · [§17](verification-maximal-os.md#r-17-030e)

**R-17-030f** IS: Fail-closed seam **the sealed cutoffs ⋈ emergency calling**: a thrown microphone switch yields a connected but mute emergency call and a thrown radio switch yields none at all (R-12-054, R-15-145), deliberately not overridden.
· Accept: a software override for the emergency case is a software override, so it would hand every compromised stack the same lever; the refusal is retained and the cost is stated rather than narrowed.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-030f)

**R-17-030g** IS: Fail-closed seam **the coverage floor ⋈ emergency calling**: emergency service runs over 5G-SA or 6G and nothing else, the legacy generations a fallback would reach being absent from the silicon rather than refused in software (R-12-041, R-12-050), so outside that coverage the device places no emergency call at all.
· Accept: the sharpest member, because unlike a thrown switch it is a denial the user has not chosen and cannot see coming; R-12-050 books the coverage limit, and what this entry adds is that it composes with R-17-030b, R-17-030c, and R-17-030f into one life-safety case rather than three separate costs.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-030g)

**R-17-030h** IS: Fail-closed seam **duress erase ⋈ accidental entry**: the duress credential crypto-erases rather than unlocking, protecting future recoverability only and irreversible on the wrong side of a human protocol this design does not model (R-17-054).
· Accept: booked as a countermeasure rather than a guarantee, and carried here because irreversibility is an availability cost the user pays without an adversary needing to be present.
· Trace: CJ-CRYPTO-SPEC · [§17](verification-maximal-os.md#r-17-030h)

**R-17-030i** IS: Fail-closed seam **the untrusted compositor and driver ⋈ the consent path**: a compromised compositor's best play is premature revocation and a hostile touch driver's is to fight the ownership transition (R-12-076, R-12-082-2, R-17-010), so both reach denial of the prompt and neither reaches a forged or captured grant.
· Accept: the bound is deliberate and identical in both cases, and it is still a denial, which is what makes an authority the user cannot obtain indistinguishable at the surface from one the platform refused.
· Trace: CJ-NI · [§17](verification-maximal-os.md#r-17-030i)

**R-17-030j** IS: Fail-closed seam **the radio stack crash ⋈ connectivity**: a crash costs connectivity until restart and never platform integrity, the stack being wholly non-TCB (R-16-002).
· Accept: contained exactly as intended, and the containment is what makes the restart the user's whole experience of it.
· Trace: CJ-CERISE · [§17](verification-maximal-os.md#r-17-030j)

**R-17-030k** IS: Fail-closed seam **the background floor ⋈ degradation**: a background origin holds on the order of one percent of one core, the foreground fast and the background very nearly stopped (R-17-005).
· Accept: not itself a fail-closed response, and named here because it is the floor the rest of this register degrades toward, so a composition read against a work-conserving machine's idea of *degraded* reads the whole set too gently.
· Trace: CJ-WCET · [§17](verification-maximal-os.md#r-17-030k)

**R-17-030l** IS: Composed, the members above describe a device an adversary able to provoke faults, thermal events, or crash-restart loops can degrade or silence, whose refusals are individually correct and jointly a life-safety case: a user cannot place an emergency call because the platform fail-stopped, or is outside the only coverage its emergency path admits, or has a sealed switch closed that no software may reopen.
· Accept: three distinct causes for one outcome, which booking the members separately hides; each is retained on its own terms, and what changes is that the composition is stated where the claim is read (R-03-008) rather than assembled by a reader from §12, §15, §16, and three entries here. No mechanism is proposed against it, every candidate being the wrong trade in this design's own currency: a software override deletes the property the cutoff exists for, a legacy emergency fallback reintroduces the attach surface R-12-041 removed from the silicon, and continuing through a thermal event reopens the channel R-15-193 deleted.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-030l)

**R-17-030m** MUST: The degraded-subset *rate* is budgeted, not only the individual window: entries into containment are recorded as an attested, countable event class rather than absorbed as containment succeeding, so repeated forcing is observable in a quantity the per-incident budget does not carry.
· Accept: R-16-009 budgets one window and R-17-035 books its cost, and neither expresses windows per unit time; without this, an attacker holding a surface degraded indefinitely is reported by the platform as a mechanism working correctly, once per window, forever. The record is a §16 event class and adds no trusted component, the sentinel already driving the attested transition it counts.
· Trace: CJ-DEVTREE, CJ-WCET · [§17](verification-maximal-os.md#r-17-030m)

**R-17-030n** IS: Fail-closed seam **detector trip ⋈ continued operation**: every fault detector answers detection by stopping, an uncorrectable ECC event and a tag-integrity failure being fail-stop sentinel events (R-15-204, R-16-008b), a control-flow signature mismatch on the three protected sequences raising the same class (R-16-008c), a divergence on the sentinel's lockstepped pair latching a fail-stop to the RoT (R-16-008d), residual synchronizer failure landing in the same place (R-15-197), a gating domain whose rail fails its discharge confirmation at a mode transition latching the same class rather than completing the transition (R-15-189n), and a trap taken while the trap path is live latching it rather than vectoring a second time onto a context it has already destroyed (R-15-073c).
· Accept: the member whose provocation needs no software access, because the adversary it answers is the radiated-EMI and electromagnetic-fault-injection adversary in scope by name (R-03-003, R-15-155), so a probe held near the enclosure stops a correctly behaving device; each detector is right to stop and the composition is the finding, not any member of it.
· Trace: CJ-SAIL, CJ-RTL-SAIL · [§17](verification-maximal-os.md#r-17-030n)

**R-17-030o** IS: Fail-closed seam **entropy health-test failure ⋈ every operation needing fresh randomness**: the noise source's start-up and continuous on-line health tests have fail-stop as their sole failure action, with no reduced-rate, best-effort, or last-known-good path in hardware or firmware (R-15-241b), so key generation, sealing, attestation, and every protocol needing a fresh nonce stop with the source.
· Accept: the refusal is correct because every alternative turns a detected failure into an undetected one, which is the one member of this register whose weakening would cost confidentiality rather than availability; it is therefore stated as a member and not repaired into a degraded mode, and an adversary who can bias a source into tripping its own test denies more than the RoT.
· Trace: CJ-CRYPTO-SPEC, CJ-DEVTREE · [§17](verification-maximal-os.md#r-17-030o)

**R-17-030p** IS: Fail-closed seam **display underrun ⋈ the trusted path**: an underrun blanks the affected lines visibly as the presentation of a caught fail-stop rather than displaying unauthenticated bytes (R-15-231, R-16-004), and the consent surface a user must see to grant authority is drawn on the path that blanks.
· Accept: this member reaches denial of the prompt from a direction R-17-030i does not cover, needing no software compromise to produce; recovery is the ordinary restart of the display path, so the cost is availability of the prompt and never a forged or captured grant.
· Trace: CJ-ISOL, CJ-NI · [§17](verification-maximal-os.md#r-17-030p)

**R-17-030q** IS: Fail-closed seam **budget admission refusal ⋈ the roster**: a workload that does not fit the static budget is refused at admission rather than paged, there being no swap and no overcommit anywhere (R-15-171), and a composition whose declared freshness commit rates sum past the counter's rated endurance is refused on the same pass (R-10-013d), each a precondition of the argument it serves rather than a shortfall in it.
· Accept: the second delivery-side member beside R-17-030e, named because a refusal provoked by ordinary growth rather than by an adversary is still a refusal, and a register carrying only the adversary-provokable members would be a threat model rather than an inventory.
· Trace: CJ-MEMPLAN, CJ-WCET · [§17](verification-maximal-os.md#r-17-030q)

**R-17-030s** IS: Fail-closed seam **freshness refusal ⋈ durable application state**: a `Fresh` region that does not verify against the sealed epoch root is refused rather than returned (R-10-013e), so an adversary with physical access to the storage holds a permanent denial of that state and an exhausted commit quota holds a temporary one.
· Accept: the refusal is retained because every alternative presents a superseded state as current, which is what the class exists to prevent; the member is a denial an adversary provokes without software access, reached from a direction R-17-030n does not cover, and it is bounded to the declared class rather than to the volume.
· Trace: CJ-CRYPTO-SPEC, CJ-DEVTREE · [§17](verification-maximal-os.md#r-17-030s)

**R-17-030r** MUST: Membership in the fail-closed seam register is conferred entry by entry and never asserted in bulk: a requirement specifying a mechanism whose failure action is to stop confers the membership against itself, the R-17-030 entries collect the conferrals, and neither a member no requirement confers nor a conferral no member collects is admitted.
· Accept: this is R-17-016's repair applied to the other register, and it closes the register's disagreement with the requirements, which is the direction R-03-008 already calls a review-gate finding and nothing enforced; it does not close completeness, because *fails closed* is a judgment no tool decides, and claiming otherwise would be the same defect one level up.
· Accept: twenty-one requirements confer a refusal and fifteen seams collect them, both figures recomputed rather than maintained here.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-030r)

**R-17-030t** MUST: Against the completeness residue conferral cannot reach, `tools/check.ps1` over-approximates the vocabulary of refusal across every requirement body and requires each entry it catches to be conferred, collected, or dispositioned there by name with a reason.
· Accept: the instrument is lexical and proves no totality, so what it buys is that the totality claim is discharged against an agenda regenerated on every run rather than against a reading nobody repeats; R-17-030n, R-17-030o, R-17-030p, and R-17-030q were found by running it and not by inspection. A disposition is a decision and is recorded in the tool beside the rule rather than as a marker in the register, a marker taxing the vocabulary instead of the judgment.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-030t)

### 17.7 Admission and tooling seams

**R-17-031** IS: The compilation ⋈ robust-safety seam is closed at a price: the robust-preservation theorem is a heavier obligation than plain compiler correctness.
· Accept: discharged by R-05-024.
· Trace: CJ-SECOMP · [§17](verification-maximal-os.md#r-17-031)

**R-17-032** IS: The admission tradeoff is one-directional: raising the Tier-2 floor trades away *hardware bounds arbitrary unverified code* for deleting intra-compartment memory-unsafety as a bug class; containment is unchanged and only the admitted set narrows.
· Accept: the universal contract is retained beneath the certificate.
· Trace: CJ-TAL-SOUND · [§17](verification-maximal-os.md#r-17-032)

**R-17-033** IS: The certifying compiler's preservation theorem is off the trust path, a completeness property, not a soundness one: a buggy or adversarial certifying compiler can only fail to emit a valid derivation for a safe program, which is an availability failure, never a safety breach.
· Accept: the theorem ships tested-but-unproven and is backfilled as assurance against Radium; there is no interim weakening, so the residual is a *delivery* risk rather than degraded admission.
· Fail-closed: admission refuses a safe program the certifier could not derive (R-17-030e); the cost lands on delivery and not on a running unit.
· Trace: CJ-TAL-SOUND · [§17](verification-maximal-os.md#r-17-033)

**R-17-034** IS: The typed callee set is the sharpest instance of that completeness residual: a compiler that cannot enumerate a site emits no derivation and the binary is refused, and cannot mint one that type-checks yet under-declares.
· Accept: the population that resists enumeration is already excluded by no-runtime-codegen; because closure is per-compartment, a mis-stated manifest yields well-typed compartments wired wrong, the crown-jewel-spec failure mode in its usual place.
· Trace: CJ-TAL-SOUND · [§17](verification-maximal-os.md#r-17-034)

**R-17-035** IS: The remediation-window seam: containment is fast and needs no proof because it only removes authority, while full remediation stays proof-gated, so the affected functionality runs degraded between the two.
· Accept: the window is budgeted, not hidden, and deliberately preferred over a fast unverified hot-patch.
· Trace: CJ-CERISE · [§17](verification-maximal-os.md#r-17-035)

**R-17-035a** IS: The generation-boundary seam is that same window on the install path, and it has two halves. **Latency:** because an install is a generation (R-13-001a), adding a package costs a boot, and the atomicity, the whole-roster memory plan, the schedulability proof, and the cross-roster merge are all bought at the price of immediacy, with the reboot additionally discarding everything outside the enumerated mutable volumes (R-10-026). **Disclosure:** a generation is roster-specific, so composing one off-device (R-13-001c) tells the composer what the device has installed.
· Accept: both are stated rather than answered by a mechanism. The latency is the cost of refusing a running-system mutation, which is the same refusal R-17-035 pays for above and not a second one, and the discarded volatile state is exactly the class R-10-035's declared durable regions exist to take out of the discard. The disclosure narrows to nothing where the user composes locally, the composer being any party rather than a vendor (R-13-013), at the price of running the certifying toolchain themself; a device that will not do that discloses its roster, and no on-device composition path is offered instead, because one would have to certify what it emits (R-13-001c).
· Trace: CJ-DEVTREE, CJ-NI · [§17](verification-maximal-os.md#r-17-035a)

**R-17-036** IS: On-device verbose diagnostics remain an observation capability deliberately confined rather than eliminated, its confinement resting on the lifecycle-state gate and the sink's confidentiality label.
· Accept: discharged by R-16-021.
· Trace: CJ-NI · [§17](verification-maximal-os.md#r-17-036)

**R-17-037** IS: The single-mechanism concentration is booked in four parts: in-core spatial isolation rests on CHERI alone with no in-band disjoint backstop; application-class single-address-space purecap is the less battle-tested isolation model; privilege-as-capability is untested at application-class multicore scale; and device access rests on CHERI too, adding in-flight-DMA revocation and a capability/tag-carrying fabric as new obligations.
· Accept: the sole hedge against a CHERI logic fault is out-of-band (CHERI's own formal verification), leaving RTL ⊑ Sail and its Coq-native restatement as the residual, plus the fab residual beneath.
· Trace: CJ-CERISE, CJ-RTL-SAIL · [§17](verification-maximal-os.md#r-17-037)

**R-17-038** IS: The admission-checker stratification seam carries six named residuals: the CHERI-TAL soundness metatheorem as a new crown jewel; the net-new temporal-safety type discipline; relevance bounding the drop but never the response; no-ambient-state forbidding re-manufacture but not over-injection; the frozen theory buying the line-budget axiom by spending expressiveness one-directionally; and totalized arithmetic being per-install decidable only where bounds are closed.
· Accept: each is stated with its compensating fact and its scope boundary; least authority stays in the compose-time topology as a crown-jewel policy statement rather than a typing obligation.
· Trace: CJ-TAL-SOUND · [§17](verification-maximal-os.md#r-17-038)

**R-17-039** IS: The Sail ⋈ RTL seam is split rather than left as one undifferentiated trust residual: the Coq refinement is the sole unbounded close, the timing and ordering obligations are hyperproperties needing a timing-annotated model, and no such artifact exists at full-application-core scale, the least-built layer of the stack.
· Accept: it grows no privileged trust base; the design-space exploration narrows it at design time rather than merely booking it.
· Trace: CJ-RTL-SAIL · [§17](verification-maximal-os.md#r-17-039)

**R-17-040** IS: A fourth residual sits beside the arrow rather than on it: the microarchitectural absences Sail cannot express, booked against the separate absence contract, which also carries the `fence.t` flush-set completeness claim. The residual is not cost but *where it closes*: Kôika-authored blocks close it in-prover, while imported cores close it on a structural audit, not a theorem.
· Accept: the strongest microarchitectural claims about imported cores rest on the evidence tier, not the Coq close.
· Trace: CJ-RTL-SAIL · [§17](verification-maximal-os.md#r-17-040)

**R-17-041** IS: The WCET seam carries three residuals: the timing-annotated Sail model's latency *magnitudes* become a crown-jewel spec; WCET inherits the RTL ⊑ Sail residual; and composability without an interference term rests on the isolation model, so WCET soundness and timing-channel deletion share one non-interference proof.
· Accept: MBPTA/EVT stays rejected as the admitted bound and aiT stays the unverified cross-check.
· Trace: CJ-WCET, CJ-RTL-SAIL · [§17](verification-maximal-os.md#r-17-041)

**R-17-042** IS: The constant-time coverage seam carries four residuals: CT is typed where it can be and proved where it cannot; a stock compiler does not preserve CT so it is hardened then checked; Binsec/Rel is bounded evidence; and CT inherits the RTL ⊑ Sail residual.
· Accept: scope is a labeling obligation, so a secret reaching an un-CT-verified compartment is a spec or label error the flow theorems must catch, not a tooling gap.
· Trace: CJ-CT-SOUND · [§17](verification-maximal-os.md#r-17-042)

**R-17-043** IS: The verified-storage seam carries six residuals, all of a *verified but contained* stack: freshness rather than trust; L0 re-proved over C rather than ported by a bespoke tool; the AE ⋈ noninterference composition seam; the liveness ⋈ schedulability seam; the dedup keyed-digest interface and its domain-confined equality revelation; and bulk user-data freshness surrendered by design, the security-bearing class being taken out of the surrender by declaration rather than left inside it.
· Accept: the stack carries no TCB membership at all, so system integrity rides the small reader and transactor instead; the freshness exception widens the crypto-core interface exactly as the dedup digest does and adds no component to that set.
· Trace: CJ-NI, CJ-REDUCTION · [§17](verification-maximal-os.md#r-17-043)

**R-17-043a** IS: Declarative durable state books the storage seam's seventh residual: it buys the deletion of per-application persistence code at the price of the one state class that outlives the reboot which clears everything else, costing a rollback window between checkpoints, a standing schema-migration obligation across generations, and the only place on the machine where a defect can be durable.
· Accept: the class stays typed, per-domain, non-TCB, and discardable and is never extended to system or kernel state; externally visible or non-repeatable effects still take an explicit commit rather than riding the checkpoint, and that commit is the `Fresh` declaration of R-10-035a rather than an obligation handed back to the application.
· Trace: CJ-DEVTREE · [§17](verification-maximal-os.md#r-17-043a)

**R-17-044** IS: The synchronous-control-plane seam adds no fresh axiom (Vélus is Coq-verified) and carries two residuals: the Lustre program and the control/data boundary are crown-jewel specs, and the offset is a net shrink: WCET, the memory-safety certificate, and determinism become structural for the control tier.
· Accept: the rare adoption that lowers net tooling.
· Trace: CJ-VELUS · [§17](verification-maximal-os.md#r-17-044)

**R-17-045** IS: Definite initialization is carried by the type system alone, with three residual parts: the hedge is genuinely surrendered by decision; device-written memory leaves the derivation into the HAL's contract proofs; and delegated buffers leave it into the IDL and manifest tables.
· Accept: eager-zeroize keeps the *disclosure* consequence closed independently, so the uncaught case is a correctness bug reading zeros rather than a residue leak; the deletion is a net subtraction on every scarce axis.
· Trace: CJ-TAL-SOUND, CJ-HAL · [§17](verification-maximal-os.md#r-17-045)

**R-17-045a** IS: The object-model deletion (R-07-002, R-07-002b, R-08-004) spends the independent-scrutiny argument that carried the seL4 design choice: the deleted classes were the most scrutinized part of that specification, their CHERIoT-lineage replacements carry thinner published assurance, and less of seL4's executable model transfers through `hs-to-coq`, so a larger fraction of the Gallina specification is authored fresh.
· Accept: booked as a specification-scrutiny residual rather than a mechanism residual, nothing joining the trusted set; bounded by the authored artifact being a smaller oracle than the one it replaces, and offset by the retirement of the CDT revocation refinement the kernel-design disposition named as the route's early kill switch.
· Trace: CJ-KERNEL · [§17](verification-maximal-os.md#r-17-045a)

**R-17-046** IS: The proof trust base is the §6 axiom inventory (R-06-011) together with the interim non-Coq anchors (R-05-022), held here as a residual rather than restated: what this entry adds is the disposition, that the interims are explicitly shrinking rather than open-endedly tolerated.
· Accept: both lists are read off R-06-011 and R-05-022, so neither is enumerated twice and a change to either has one place to be made. The Coq-native crypto path adds no new prover, so an interim's surface retires as its consumer list empties (R-05-022a); the checkers' own binaries keep their named bootstrap as the De Bruijn root (R-06-014).
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-046)

**R-17-047** IS: Lean-as-checker is refused as the two-kernel cost and Lean-as-oracle has no mature transport today, so the answer stays Coq-native: a tooling-maturity cost the engineering-free axiom absorbs, not a reason to fork the checker.
· Accept: the single-prover-binds-the-checker rule governs (R-05-016).
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-047)

**R-17-048** IS: The heterogeneous die grows the Sail model along an enumerated list, and the profile's exclusions shrink the decode and state surface along another; the net is modeling-and-verification surface, not new privileged trust.
· Accept: both lists are stated rather than summarized.
· Trace: CJ-SAIL · [§17](verification-maximal-os.md#r-17-048)

### 17.8 Crypto, regulatory, and physical ceilings

**R-17-048a** IS: Retiring the RVY re-pin (R-15-007) spends **oracles rather than a badge**: `sail-cheri-riscv` becomes a model this platform parameterizes and maintains rather than one it inherits, and the CHERI half of the differential-testing surface degrades in **two terms rather than one**. The **algebraic** oracles (bounds encode/decode, the representable-region predicates, monotonicity) degrade in proportion to the parameterization, being statements over field widths this platform changes and an algebra it does not. The **instruction-level** oracles (Spike, QEMU, and the CHERI test suites) degrade in proportion only while they sit on the ISAv8/v9 lineage the format re-parameterizes, and closer to all at once as they track RVY, which shares with that lineage neither mnemonics (renamed into the `Y*` space), nor encodings (relocated wholesale into Custom-3), nor CSR names, nor sealing's carriage (moved to a CT field), nor the format's name (RV64LYA): there is no shared surface left to fail proportionally. What is not spent is the algebra: the Cambridge monotonicity, provenance, and non-forgeability results are statements about it, and they are inherited under R-15-007a.
· Accept: booked as an evidence loss rather than as trust growth, nothing joining the trusted set. The instrument spent is the one that reports spec-versus-intent divergence, which no proof covers (R-17-016), so the compensating obligations are named rather than assumed: the representation-correctness proof (R-15-007a), the enumerated permission lattice (R-15-007b), and the bounds-precision cost carried by the static memory plan (R-15-007c). The rule the case establishes for any later amendment is that conformance is worth what its oracles are worth, so the number of amendments to the frozen dialect is itself a quantity to keep small, and the second term is what makes that rule bind rather than advise, the proportionality that makes a short deviation list affordable being carried by the algebraic term alone.
· Trace: CJ-SAIL, CJ-RTL-SAIL · [§17](verification-maximal-os.md#r-17-048a)

**R-17-049** IS: Reductions isolate axioms but do not remove them: hardness assumptions (MLWE/MSIS, ECDLP/CDH) are irreducible, and the implementation ⋈ reduction seam joins at the primitive's functional specification, a crown-jewel spec neither side catches.
· Accept: hybrid PQ+classical key exchange is the standing hedge; protocol-level security is a further layer this guarantee does not reach.
· Trace: CJ-REDUCTION · [§17](verification-maximal-os.md#r-17-049)

**R-17-049a** IS: The entropy residual is subversion, not failure: a dead, stuck, biased, or dying source is a stated fault (R-15-241b, R-15-241e, R-09-006a), while a source trimmed at fabrication to a distribution that passes exactly the tests it will be given is the fab residual (R-17-060) read on the noise source rather than on the logic, and inherits its ceiling without narrowing it.
· Accept: the split is stated as detected failure against undetected subversion, the entropy root being a consumer of the silicon supply-chain residual rather than a mechanism outside it; open RTL does not describe an analog trim and IRIS images structure rather than distribution (R-17-061, R-17-063), so neither mitigation is claimed against this case.
· Trace: CJ-T, CJ-CRYPTO-SPEC · [§17](verification-maximal-os.md#r-17-049a)

**R-17-050** IS: The blocking regulatory risk has substantially cleared (FCC's settled SDR position; the EU radio-lockdown delegated act abandoned in January 2026), and the genuine residual is narrow and commercial: carrier, PTCRB, and GCF acceptance of an open cellular UE stack.
· Accept: mitigations are module certification with inheritance, RoT attestation giving stronger version binding than the industry norm, and private-network deployment as the lighter-certification first ring.
· Trace: CJ-DEVTREE · [§17](verification-maximal-os.md#r-17-050)

**R-17-051** IS: The 5G/6G-only generation floor narrows deployability, and emergency calling inherits it: emergency reach equals 5G/6G coverage reach, a coverage-for-security trade extended to E911/E112 by decision rather than by silence.
· Accept: the trade is stated in §15, §12, and here.
· Trace: CJ-SAIL · [§17](verification-maximal-os.md#r-17-051), [§17](verification-maximal-os.md#r-17-051-2)

**R-17-052** IS: The emergency-calling seam admits an unauthenticated, possibly null-ciphered session (the one place the radio's verified crypto posture is deliberately not in force), contained by non-interference and zero standing authority rather than excepted.
· Accept: it is also the one place a sensitive peripheral is granted at Before First Unlock, and the residual runs the *other* way: the sealed cutoffs are not overridden, because a software override for the emergency case is a software override.
· Trace: CJ-NI · [§17](verification-maximal-os.md#r-17-052)

**R-17-053** IS: The wired-link ceiling books two costs: 10GBASE-T and above are declined, and the 1000BASE-T canceller's coefficients are frozen per link epoch, so marginal cable plant re-trains on a link bounce, an availability cost, never an integrity or confidentiality one.
· Accept: discharged by R-15-137 through R-15-139.
· Trace: CJ-ISOL · [§17](verification-maximal-os.md#r-17-053)

**R-17-054** IS: The lock-state seam books three limits: at-rest security is bounded by the credential and its rate-limiter; the unlocked window is shortened but not closed; and duress crypto-erase is a countermeasure rather than a guarantee, protecting future recoverability only and being irreversible on accidental entry.
· Accept: biometrics are deliberately excluded from cold or idle-locked key release for exactly the false-accept and presentation-attack reason.
· Fail-closed: the duress credential erases rather than unlocking (R-17-030h); the cost is irreversible on accidental entry.
· Trace: CJ-CRYPTO-SPEC · [§17](verification-maximal-os.md#r-17-054)

**R-17-055** IS: Hardware-random link-layer addressing is necessary but not sufficient for unlinkability: RF fingerprinting, frame sequence numbers and timing, and higher-layer identifiers each re-link sessions a random address alone would separate; and because framing is SoftMAC the address is inserted by a memory-safe but not functionally-proven compartment.
· Accept: the guarantee is *no persistent identifier, randomness from the platform RNG root*, a privacy floor, not a complete unlinkability proof.
· Trace: CJ-NI · [§17](verification-maximal-os.md#r-17-055)

**R-17-056** IS: The USB authentication floor attests identity, not behaviour, and a mandatory floor is a coverage-for-security trade: most deployed peripherals do not implement authentication, so they are charging-only until a deliberate per-device exception, which weakens the floor to a consented prompt wherever the user chooses convenience.
· Accept: runtime containment carries what authentication cannot.
· Trace: CJ-CERISE · [§17](verification-maximal-os.md#r-17-056)

**R-17-057** IS: The trusted-time residual is availability, not integrity: a network adversary can deny or stall fresh time but not forge a chosen value, and secure PTP adds one facet: its authentication TLV protects origin and integrity but not the path-symmetry assumption its offset calculation rests on.
· Accept: a just-cold-booted offline device runs time-unknown until Roughtime succeeds; the PTP exposure exists only where PTP is used.
· Trace: CJ-CRYPTO-SPEC · [§17](verification-maximal-os.md#r-17-057)

**R-17-058** IS: Physical residuals: Rowhammer is dramatically reduced rather than mitigated; cold boot is countered by SRAM volatility with no encryption involved; TEMPEST-class emission is attenuated but not closed against a near-field probe; and macro-internal and sequential-3D thermal coupling are narrowed rather than eliminated. The analog channel out of the crypto core is not one of these: R-17-058a states it in its own right, because it is a decision about that core rather than a consequence of the invasive-attack scope line.
· Accept: each names the mechanism that narrows it and the scope line that bounds it.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-058)

**R-17-058a** IS: The crypto core carries no masking, and resistance to a probing adversary is not claimed: every constant-time obligation (R-05-004, R-05-062) is stated against the architectural §15 leakage model (`Zkt`/`Zvkt`, R-15-053), which covers instruction latency and emitted addresses and not instantaneous power draw or near-field electromagnetic emission, so differential and correlation power analysis and their electromagnetic equivalents are unaddressed by construction rather than narrowed. The shield cans and enclosure (R-15-153) and the RoT's own clock/power island (R-15-113) attenuate and separate; neither bounds what a measurement yields, and no claim rests on either.
· Accept: no row, mode, or theorem anywhere claims analog side-channel resistance, and a claim resting on the enclosure is a spec defect in the R-05-153 sense. The reversal is named and is four things together: a masked datapath in the crypto core; a probing-model leakage statement authored and conferred beside the `Zkt`/`Zvkt` one, carrying its own axiom because a physical leakage model is an assumption about the silicon in the R-06-011 sense; *d*-probing and composition theorems verified on the crypto artifacts as R-05-004 already requires of constant time; and per-operation randomness booked against the entropy root (R-15-241) and the crypto core's slot. Absent all four the residual stands, and adopting masking amends this entry rather than reinterpreting it.
· Trace: CJ-LEAK · [§17](verification-maximal-os.md#r-17-058a)

**R-17-058b** IS: Fault injection's detector positions (R-16-008c, R-16-008d) buy coverage and never a theorem, because the fault is the Sail model's hypothesis failing rather than a behavior it admits. Four limits are named: signature coverage is evidence, a divergence that lands the signature register on its predicted value being uncaught; a fault inside the compare-and-fail-stop epilogue is not caught by that epilogue, doubling raising the cost of the attempt rather than closing the case; lockstep is decided for the S-class core alone, so the C-, V-, and M-class cores and the RoT's continuous operation carry no comparator; and the transient datapath strike is unclaimed at consumer grade, its answer being deployment-graded software redundancy.
· Accept: no row, mode, or requirement states a detection *probability* or claims a mode above *detected* for this class; what would raise it is a stated fault model the silicon is claimed to satisfy plus a detection statement proved over it, the shape R-17-058a already uses for masking.
· Trace: CJ-T, CJ-SAIL · [§17](verification-maximal-os.md#r-17-058b)

**R-17-059** IS: The memory path is defended by the *absence of a surface* rather than by a mechanism, and the residual is the scope line itself: the honest statement is not "replay is undetected" but "the whole class is out of scope, and nothing on the memory path would detect it if it were in scope."
· Accept: there is no defence-in-depth layer beneath the package boundary on the memory path, so the invasive-attack scope line is load-bearing rather than conservative, and if it is ever judged wrong there is no second mechanism behind it. **This is the sharpest instance of *verify rather than hedge* applied to the design's own threat model.**
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-059)

**R-17-060** IS: Silicon supply chain is the largest residual once software is done, and single-die integration concentrates it: one mask set carries the RoT, all core classes, the NoC, the memory path, and the radio.
· Accept: mitigations are open RTL, multi-sourcing, and IRIS backside optical verification, none complete.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-060)

**R-17-060a** MUST: The residual's interval is split at the mask set, and the design-to-mask half is discharged as the source-to-binary half is (R-09-027, R-13-026), by regeneration and comparison rather than by trusting the producing tooling: the tapeout artifact is a deterministic function of the RTL of record, the pinned toolchain, and the pinned configuration, so an independent party re-runs the flow and compares digests exactly as it rebuilds the base image.
· Accept: determinism is an obligation on the flow rather than a property of the tools, since commercial synthesis and place-and-route are not deterministic by default; pinned versions and libraries, a fixed compute shape, seeded and ordered traversal, and a timestamp-free database are stated on the tapeout path (R-18-013a), and a step that cannot be made to meet them is a delivery finding rather than a caveat.
· Trace: CJ-T, CJ-RTL-SAIL · [§17](verification-maximal-os.md#r-17-060a)

**R-17-060b** IS: Reproducibility fixes the artifact and not its semantics: two parties agreeing on a layout database establishes that the flow was run as declared and never that it preserved what the RTL meant, and the vehicles carrying the semantic step (logic-equivalence checking against the synthesized netlist, layout-versus-schematic against the extracted one) are commercial tools whose verdict is trusted rather than re-checked in the prover.
· Accept: the step lands on the same evidence rung as the Sail-FEV gate and the imported cores' netlist audit (R-17-039, R-17-040), not on the Coq close: RTL ⊑ Sail closes above the netlist and nothing closes RTL-to-layout as a theorem, which is where the design-to-mask half is weaker than its software analogue rather than merely newer.
· Trace: CJ-RTL-SAIL · [§17](verification-maximal-os.md#r-17-060b)

**R-17-060c** IS: Reproduction is not identity, which is where the analogy to a compiled binary stops: optical proximity correction and mask data preparation are lossy resolution-driven transformations and the fab applies its own process-dependent corrections beneath them, so what reproduces bit-for-bit is the artifact at the agreed handoff and the relation back to the reviewed layout is a named, re-runnable transformation rather than an equality.
· Accept: the claim is stated as the weaker one it is, with every arrow below the handoff the fab's; a statement of bit-for-bit identity between the reviewed layout and the fabricated structure is a review-gate finding against this requirement.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-060c)

**R-17-060d** MUST: The tapeout artifact carries a digest, the digest is signed at handoff by the parties that reviewed the layout, and a fielded part's attested identity names the mask-set digest it claims to be, which is what gives R-09-003's *attested mask set* a referent rather than an assumption.
· Accept: a substitution between review and handoff is a digest mismatch rather than an invisible event, and a part claiming a mask set nobody reviewed is a claim a relying party can refuse rather than one it cannot evaluate; the obligations on the path are R-18-013a.
· Trace: CJ-DEVTREE, CJ-T · [§17](verification-maximal-os.md#r-17-060d)

**R-17-061** IS: IRIS claims evidence for the bottom logic tier (where every structure whose trust is structural lives and the only tier that computes) and does *not* claim it for the upper memory tiers, whose assurance is that they are passive arrays executing nothing, fabricated in the same lot from the same mask set.
· Accept: the honest statement is not "everything is imaged" but "everything that *acts* is imaged, and what is not imaged cannot act."
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-061)

**R-17-061a** IS: Where the tiers are realized by layer transfer, the transferred layer originates on a donor wafer, so the supply chain acquires a second wafer source while the trust structure does not acquire a second die: what arrives is blanket and unpatterned, carrying no mask set, no design content, and no separate attested identity, and is patterned in place in the same lot.
· Accept: the residual is materials provenance (substrate quality, contamination, dopant profile of an unpatterned film), not the design subversion of R-17-060, and is bounded as the tiers are: a donor-wafer adversary can corrupt stored bits, caught by ECC and fail-stop, and cannot introduce structure that computes; booked so that "the same lot" in R-17-061 does not overstate what the tiers' assurance rests on.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-061a)

**R-17-062** IS: Per-unit calibration manifests are booked in this residual: measured at the factory rather than reproduced from source, they are the one per-device artifact reproducible builds and DDC cannot cover, so the factory trim step is a named trusted measurement, narrow, but trust nonetheless.
· Accept: bounded in effect by the passive emission envelope and the ECC/fail-stop backstops.
· Trace: CJ-DEVTREE · [§17](verification-maximal-os.md#r-17-062)

**R-17-063** IS: The ceiling stays named: IRIS resolves coarser structure far better than the smallest features, it is evidence and not proof, and a fab-level adversary below its resolution remains in scope.
· Accept: none of the three mitigations is complete.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-063)

**R-17-063a** IS: The design-to-mask split buys a smaller thing for the evidence to carry rather than a narrower ceiling: the residual is one arrow instead of three, *the die may not match the mask set* rather than *the die may not match the design*, and a fab that deviates from the mask set is answered by the inspection evidence and by nothing in R-17-060a through R-17-060d.
· Accept: no requirement claims that the design-to-mask half reaches the fab, and none states a mode above *evidence* for the mask-to-die arrow; a claim of either is a review-gate finding.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-063a)

### 17.9 The composition obligation

**R-17-064** IS: The residual the whole list rolls up into is the composition meta-lemma: that the capability-safety substrate and the seam lemmas, transported down the refinement tower, entail T.
· Accept: it is the single largest verification deliverable and exists for no system of this scope; the single-prover discipline makes it literal proof composition rather than cross-tool glue, which is what makes it tractable, not what makes it done.
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-064)

**R-17-065** IS: T is true only modulo its stated boundary: the declassification set *D*, the axiom set *Ax*, the hardness conjectures, the die-matches-RTL fabrication gap, specification faithfulness, human consent correctness, and invasive physical attack, each a residual above.
· Accept: the theorem's honesty is that its own statement names them rather than absorbing them silently (R-05-162).
· Trace: CJ-T · [§17](verification-maximal-os.md#r-17-065)

---

## §18. Realization

### 18.1 Constraints and priority

**R-18-001** IS: Silicon is the binding constraint: RV64 application-class CHERI exists only as licensable IP and FPGA soft cores. Codasip's X730 is shipping evidence that application-class purecap silicon is real at sub-5% area cost, but its proprietary RTL enters as a reference and bring-up vehicle, never the trusted base.
· Accept: the RTL of record is authored in a formal-semantics HDL, so even open CVA6-CHERI enters as a functional reference.
· Trace: CJ-RTL-SAIL · [§18](verification-maximal-os.md#r-18-001)

**R-18-002** MUST: The platform is purecap-only: there is no non-CHERI host, no capability-degraded interim, and no plain-RV64 compilation target anywhere, so every stage enforces hardware capabilities from first bring-up.
· Accept: both staging phases are purecap and both gate on the CHERI toolchain.
· Trace: CJ-CERISE · [§18](verification-maximal-os.md#r-18-002)

**R-18-003** MUST: The certifying compilers are priority zero: no workstream that requires *executing system software* on any target (emulator, FPGA, or silicon) is scheduled ahead of them, because nothing runs a line of the system until they exist. Priority zero is this gating relation and not a total order over workstreams.
· Accept: no scheduled task whose completion requires running a system image precedes the functional certifying core; a reviewer checks the schedule for such a task rather than for a workstream ordering. The priority-zero deliverable is scoped to the *functional* core, the CHERI-CompCert backend (R-18-014) and the TAL producer plus on-device checker (R-18-020), and explicitly excludes the WCET cost-annotation extension of that same toolchain (R-18-024), which R-18-025 gates behind the timing-annotated Sail model.
· Trace: CJ-COMPCERT, CJ-TAL-SOUND · [§18](verification-maximal-os.md#r-18-003)

**R-18-003a** MUST: The frozen instruction-set profile (§15) is the root of the schedule rather than the toolchain: the toolchain, the Sail model, and the CompCert backend all target it, so freezing it precedes all three.
· Accept: the act with no build prerequisite is the **provisional** freeze, R-15-014a splitting the freeze in two and R-18-003c gating the measured act; R-18-006 already makes it part of the platform definition from first bring-up, and R-18-014's re-homing of SECOMP2CHERI has no target until it lands.
· Trace: CJ-SAIL, CJ-COMPCERT · [§18](verification-maximal-os.md#r-18-003a)

**R-18-003b** MUST: Five deliverables are day-one and gate on nothing, and are enumerated so that R-18-003 is not read as prohibiting all work until the compilers exist: (i) the provisional profile freeze and its Sail curation (R-18-003a, R-15-014a); (ii) the microarchitectural absence contract (R-18-012); (iii) the machine-checked statement of T and the seam lemmas (R-18-031(a), R-18-032); (iv) the atomic-requirements register (R-18-034); (v) the proof-artifact hygiene gates (R-05-163, R-05-166, per R-05-168).
· Accept: each of the five is stated elsewhere in the specification as available immediately, and none has a prerequisite that is itself unbuilt; three of the five attack the two least-built layers (R-17-039, R-17-064). A day-one deliverable found to have an unbuilt prerequisite is a review-gate finding against this requirement.
· Trace: CJ-T, CJ-RTL-SAIL · [§18](verification-maximal-os.md#r-18-003b)

**R-18-003c** MUST: The final freeze (R-15-014a) gates on three artifacts and on nothing else: the functional core of the CHERI-CompCert backend (R-18-014) with its outlining and tail-merging pass landed (R-15-036o), R-15-036p ordering that measurement first; a composed image over the roster taken after the §10 and §13 duplication-removal levers land (R-15-036i), against which *p* is measured stratified by operand class (R-15-036k); and the corpora R-15-067d fixes by name, the UPER RRC and IEI/TLV descriptors and the generated register accessors. No other workstream waits on it, every consumer of the profile targeting the provisional act, which is the schedule root R-18-003a names.
· Accept: the resulting order is acyclic, the provisional freeze and its Sail curation preceding the backend, the backend and the stripping levers preceding the corpus, and the corpus preceding the final freeze and the proof taken with it. Images built under the provisional baseline are measurement artifacts, neither deployed nor stored, so no item in R-15-014a's delta invalidates a shipped object; and no proof is taken with the provisional profile (R-15-014), so Coq and Sail work authored between the acts is re-checked against a closed delta rather than re-authored. A gating artifact absent from this list is a finding against this requirement, exactly as an unbuilt prerequisite is one against R-18-003b.
· Trace: CJ-SAIL, CJ-COMPCERT · [§18](verification-maximal-os.md#r-18-003c)

**R-18-004** IS: First release carries the radio roster whole (cellular, the eUICC, carrier certification, the HARQ hard-real-time class, and the 5G-AKA key hierarchy arrive with the first parts alongside 802.11 and Bluetooth), and the single roster deferral is the browser, the largest porting program.
· Accept: the radio program is staged inside the release, so FEC-unit bring-up (R-18-005) and carrier certification are on the critical path to first parts rather than behind them; the browser's deferral is not a design cut, its no-JIT per-origin design remaining in the specification.
· Trace: CJ-T · [§18](verification-maximal-os.md#r-18-004)

**R-18-005** IS: The heterogeneous die is staged class by class: C-class + RVV under CHERI → V-class → M-class → FEC units → islands and TDM NoC → capability-checked DMA engines and the capability/tag-carrying fabric.
· Accept: open RTL exists per class, but CHERI-purecap extension of each is new RTL and Sail work.
· Trace: CJ-RTL-SAIL · [§18](verification-maximal-os.md#r-18-005)

**R-18-006** MUST: The frozen instruction-set profile is part of the platform definition from the first FPGA bring-up: Ztso, static-only branch prediction, and Machine-mode-only are bring-up properties, not later additions.
· Accept: the CVA6-class front end is modified to static prediction and the store buffer proven TSO-exposing as part of first bring-up, alongside the `Zkt`/`Zvkt` obligation.
· Trace: CJ-SAIL, CJ-RTL-SAIL · [§18](verification-maximal-os.md#r-18-006)

**R-18-007** IS: The memory path is the first thing built and the smallest it can be: a granule read-modify-write stage, an ECC encode-and-check stage, the bank/macro/tier decode, and no cryptography of any kind.
· Accept: this matters disproportionately because every block deleted here is one that would have had to be authored in Kôika and proven against Sail from nothing.
· Trace: CJ-RTL-SAIL · [§18](verification-maximal-os.md#r-18-007)

**R-18-008** IS: The one sequential-3D dependency is a manufacturing risk, not a design one: if tier count under-delivers, capacity bends and the mechanism does not, the bonded-stack and chiplet alternatives being declined on trust grounds that a schedule pressure does not revisit.
· Accept: consistent with R-15-173.
· Trace: CJ-DEVTREE · [§18](verification-maximal-os.md#r-18-008)

**R-18-008a** IS: That risk is discrete, not gradual, and the plan is written against its worse branch: tier count is gated on complementary devices at the back-end thermal budget reaching array-grade quality and manufacturable scale, which they either do (tier count is then an ordinary yield-and-cost question) or do not (the machine is one planar tier at order 1–2 GB permanently, not as a first step). The branch point is that threshold and not the existence of a laboratory device, several of which are on record (R-15-163).
· Accept: a manufacturing dependency in both branches and a proof obligation in neither, so the §17 frontier is unmoved; what moves is R-18-030, which plans the multi-tier envelope as upside and must show the roster closing on the single tier.
· Trace: CJ-DEVTREE · [§18](verification-maximal-os.md#r-18-008a)

**R-18-009** IS: Two memory-path questions are named as open and explicitly *not* specified: a statically-placed instruction scratchpad (whose remaining motivation is port contention alone), and sequential consistency in place of Ztso (whose reach is narrower than it looks: `fence.t` and the `A` extension both survive it).
· Accept: each is open because the timing budget makes it worth revisiting, not because a change is pending; Ztso and the shared fetch path are what the specification states.
· Trace: CJ-SAIL · [§18](verification-maximal-os.md#r-18-009)

### 18.2 RTL-against-Sail

**R-18-010** MUST: RTL ⊑ Sail is a first-class workstream staged with the die and is the least-built layer of the stack: no full application-class core, and *a fortiori* no heterogeneous multi-class die, has been proven to refine its Sail model.
· Accept: the staging is rvfi first, then Sail-generated SystemVerilog plus commercial FEV, then Isla-generated obligations, then the Kami/Kôika Coq refinement as the closing goal.
· Trace: CJ-RTL-SAIL · [§18](verification-maximal-os.md#r-18-010)

**R-18-011** IS: The timing and ordering hyperproperties ride a timing-annotated model and are the hardest sub-goal: functional refinement alone does not establish them.
· Accept: consistent with R-15-095.
· Trace: CJ-RTL-SAIL, CJ-LEAK · [§18](verification-maximal-os.md#r-18-011)

**R-18-012** IS: The microarchitectural absence contract is a separate gate on this workstream rather than a stage of it, and it inverts the difficulty: it is buildable on day one and cheap, which is the whole argument for preferring removal to partitioning.
· Accept: it is the one part of the least-built layer that does not need the layer to exist first; its honest ceiling is that the imported-core half closes on audit, not theorem.
· Trace: CJ-RTL-SAIL · [§18](verification-maximal-os.md#r-18-012)

**R-18-013** IS: RTL ⊑ Sail degrades gracefully, unlike the certifying compilers: rvfi and Isla obligations ship long before the Coq refinement closes, so base bring-up is not blocked on the full proof; only the *unbounded* claim is.
· Accept: the disposition is stated per workstream rather than uniformly, and the tier it leaves a pre-close unit entitled to assert is carried by G2 and the defended set (R-01-002a, R-01-002b, R-03-006) rather than held only in this section.
· Trace: CJ-RTL-SAIL · [§18](verification-maximal-os.md#r-18-013)

**R-18-013a** MUST: The tapeout path continues that arrow below the RTL as a workstream rather than a handoff, carrying the design-to-mask half of R-17-060 as three deliverables: (a) a reproducible physical flow, with pinned tool versions and libraries, a fixed compute shape, seeded and ordered traversal, and no timestamp in the database; (b) the equivalence evidence carrying the RTL of record down to the layout, logic-equivalence checking against the synthesized netlist and layout-versus-schematic against the extracted one; (c) the mask-set digest and its attestation, signed at handoff by the parties that reviewed the layout and named in the part's attested identity.
· Accept: (a) is accepted on two independent runs on different hosts yielding one digest, with a step that resists determinism reported as a finding rather than absorbed; (b) is reported at the Sail-FEV evidence rung and never as a theorem (R-17-060b); (c) discharges R-17-060d and gives R-09-003's *attested mask set* a referent. Deliverables (a) and (c) need no silicon and gate on nothing above them.
· Trace: CJ-RTL-SAIL, CJ-DEVTREE · [§18](verification-maximal-os.md#r-18-013a)

**R-18-013b** IS: The tapeout path is the one place on this schedule where deferral is irreversible: a mask set not produced reproducibly and not digested at handoff cannot be made so afterwards, so the design-to-mask half is lost for that part permanently rather than backfilled the way a proof is.
· Accept: this is why R-18-013a's cheap deliverables are stated as early rather than as gated, unlike the graceful degradation R-18-013 allows the arrow above them.
· Trace: CJ-RTL-SAIL · [§18](verification-maximal-os.md#r-18-013b)

### 18.3 The toolchain

**R-18-014** MUST: Two certifying compilers gate the platform: the CHERI-CompCert backend for the TCB, and a certifying Rust→RV64+CHERI compiler emitting per-binary memory-safety certificates.
· Accept: the first re-homes SECOMP2CHERI and completes its robust-preservation theorem rather than authoring a capability backend fresh; the second is genuinely net-new and explicitly in scope.
· Trace: CJ-COMPCERT, CJ-SECOMP · [§18](verification-maximal-os.md#r-18-014)

**R-18-014a** MUST: Backend completeness is part of the two already-required compiler deliverables, not a separate performance workstream: every production lowering for a vector-bearing core class provides ordinary latency-aware scheduling, RVV autovectorization and SLP, legal register-arm `Zicond` if-conversion, fusion-aware selection and adjacency preservation for the frozen §15 pair set, and selection of the frozen §15 capability indexed load and store (R-15-007e) and bitfield extract and insert (R-15-067a) wherever the addressing or field-access pattern matches; every production link enables the standard CHERI/RISC-V address-materialization and direct-call relaxations supported by the frozen profile where their standard preconditions hold.
· Accept: backend tests contain one positive generated-code case for each lowering facility and a fusion-conflict case showing that a pair is broken only when the same block's static Sail cost is strictly lower; linker tests contain positive and blocked-precondition cases for each enabled standard relaxation, introduce no private relaxation semantics, and translation-validate the post-relaxation linked image against Sail under R-05-023; the work plan names no separate optimizer, analyzer, profile pipeline, search tool, verified artifact, or workstream for these duties.
· Trace: CJ-COMPCERT, CJ-TAL-SOUND, CJ-WCET · [§18](verification-maximal-os.md#r-18-014a)

**R-18-014b** MUST: The link-time step that already emits the static slot assignment implements the R-08-012a lexicographic objective from the R-08-012b profile-free inputs, with a determinism test (one source closure, two builds, one identical placement map) and a non-regression test (no island's peak footprint and no admitted §11 bound worse than under a footprint-only plan).
· Accept: the work plan names no separate placement tool, profile pipeline, optimizer, or workstream, and no consumer-side checker is added: the placed image is validated by the same TAL interference check and the same R-05-023 translation validation as before.
· Trace: CJ-COMPCERT, CJ-MEMPLAN, CJ-WCET · [§18](verification-maximal-os.md#r-18-014b)

**R-18-014c** MUST: Bound-directed lowering belongs to the same two compiler deliverables: where two lowerings are architecturally equivalent and both fit the §15 image budget, the backend emits the one whose R-18-024 cost annotation yields the smaller bound even where its expected-case cost is worse (expected-case cost is the tie-break, never the criterion), and it takes the legal transformations that replace a data-dependent trip count with a statically declared one or hoist variable-trip-count control flow out of a bounded region, so that R-11-015's loop-bound discharge succeeds syntactically rather than through its manual escape hatch. The R-18-014a `Zicond` if-conversion duty is the first instance of this rule, not a separate facility.
· Accept: backend tests contain a case where the bound-directed and average-directed choices differ and the emitted code is the bound-directed one, a loop-bound case discharging syntactically where the untransformed form needed the escape hatch, and a non-regression case in which no admitted §11 bound is worse and no island's image share exceeds its §15 budget; the work plan names no separate optimizer, analyzer, profile pipeline, search tool, or workstream for the duty, and no consumer-side machinery is added, admission still deciding against the bound re-derived from the shipped binary (R-11-015a).
· Trace: CJ-WCET, CJ-COMPCERT, CJ-TAL-SOUND · [§18](verification-maximal-os.md#r-18-014c)

**R-18-014d** MUST NOT: Image size is a constraint on that choice and not a term in it: a bound-directed lowering that would displace another admitted component from the §15 capacity budget is inadmissible however much it tightens.
· Accept: the same arbitration R-18-014b's non-regression test states on the data side; until the timing-annotated Sail model lands for a core class the rule runs against the bring-up measured table exactly as sound §11 admission does (R-18-025).
· Trace: CJ-WCET, CJ-COMPCERT · [§18](verification-maximal-os.md#r-18-014d)

**R-18-015** IS: The certifying Rust compiler's shape is a front end over safe-Rust MIR carrying the source type system's memory-safety fact through lowering and emitting a CHERI-TAL derivation; CHERI discharges spatial safety, so the preserved obligation is the temporal-safety and typed-control-flow residual.
· Accept: no per-app manual proof is required for pure-safe-Rust code.
· Trace: CJ-TAL-SOUND · [§18](verification-maximal-os.md#r-18-015)

**R-18-016** MUST: Relevance grading is the one obligation the front end cannot lift from the source type system, so the fallible-result types of the kernel ABI, the IDL, and the attestation and storage interfaces are declared relevance-graded *at their definition* and the front end propagates from there.
· Accept: the net-new work sits at the interface definitions rather than at every call site.
· Trace: CJ-TAL-SOUND, CJ-IDL · [§18](verification-maximal-os.md#r-18-016)

**R-18-017** MUST: The derivation is emitted by hinted mirroring: the untrusted compiler records hints through lowering and a small trusted Coq replayer reconstructs the typing derivation the on-device checker re-validates.
· Accept: the certifier is a small replayer plus an untrusted producer rather than a whole-compiler preservation megaproof, the concrete reason the preservation theorem sits off the trust path.
· Trace: CJ-TAL-SOUND · [§18](verification-maximal-os.md#r-18-017)

**R-18-018** IS: The toolchain sub-deliverables are enumerated: (a) the lowering emitting the TAL derivation, with its preservation statement a completeness property backfilled as assurance against Radium; (b) the CHERI-TAL and its soundness metatheorem, its type theory frozen to the §5 budget so the line budget and metatheorem size are consequences rather than targets; (c) integration with the on-device checker and oracle-compressed proof shipping; (d) the manual-proof escape hatch for HAL-adjacent `unsafe`, foundationally grounded via VerusBelt, plus a gate refusing app `unsafe` outside it.
· Accept: all four appear in the workstream list.
· Trace: CJ-TAL-SOUND, CJ-HAL · [§18](verification-maximal-os.md#r-18-018)

**R-18-019** MUST: A bug-finding oracle rides alongside the certifier and never as a second checker: Soteria-rust over the same MIR hunts UB in the HAL-adjacent `unsafe`, and the same framework instantiates for C to bug-find the CompCert/VST path.
· Accept: a Soteria finding shifts a bug left of admission rather than ever carrying it; the memory-safety obligation is discharged by CHERI ⋈ the TAL metatheorem regardless.
· Trace: CJ-TAL-SOUND · [§18](verification-maximal-os.md#r-18-019)

**R-18-020** IS: A producer of TAL derivations is a hard prerequisite with no trusted-toolchain fallback: no userspace app is built or admitted until the producer and the on-device checker exist, while the preservation proof is deliberately off that critical path.
· Accept: Cranelift with Crocus-verified lowerings is an SMT-trust reference point informing the lowering proofs, never the shipped certifier and never an admission path, of which there is none.
· Trace: CJ-TAL-SOUND · [§18](verification-maximal-os.md#r-18-020)

### 18.4 Crypto, WCET, storage, radio, memory

**R-18-021** MUST: Crypto verification carries exactly three deliverables and no codegen deliverable: layer-3 reduction proofs authored Coq-native in SSProve/FCF; the composition linking reductions to implementations at each primitive's functional specification; and constant-time verification for every secret-touching binary.
· Accept: the standalone CT verifier folds into the certifying-compiler/TAL workstream rather than being net-new, degrading gracefully with Binsec/Rel carrying bring-up.
· Trace: CJ-REDUCTION, CJ-CT-SOUND · [§18](verification-maximal-os.md#r-18-021)

**R-18-022** MUST NOT: The fourth candidate deliverable, the CryptOpt-style translation-validation toolchain, is deleted rather than deferred, because its whole yield is speed on an already-sound path.
· Accept: §18 carries three crypto deliverables rather than four (R-18-021), and this is the fourth's absence; what the deletion costs is read off R-05-064 rather than enumerated here.
· Trace: CJ-CRYPTO-SPEC · [§18](verification-maximal-os.md#r-18-022)

**R-18-023** IS: The formosa-crypto ML-KEM effort is the existence proof for what remains, so the reduction and composition deliverables are a Coq-native restatement of finished work rather than a from-scratch research program; an EasyCrypt reduction is admissible interim assurance exactly as libcrux/HACL\* is.
· Accept: the SSProve/FCF restatement is the trust-base-minimizing follow-through, not a boot blocker.
· Trace: CJ-REDUCTION · [§18](verification-maximal-os.md#r-18-023)

**R-18-024** MUST: WCET derivation folds into the certifying toolchain rather than a standalone estimator, with three sub-deliverables: the per-instruction latency table as a projection of the timing-annotated Sail model; the tree-sum cost annotation and loop-bound discharge integrated into the toolchain; and integration with the on-device checker.
· Accept: the standalone Coq-verified IPET estimator is retired as a workstream.
· Trace: CJ-WCET · [§18](verification-maximal-os.md#r-18-024)

**R-18-025** IS: WCET staging is gated behind the timing-annotated Sail model and thus per-class RTL bring-up, degrading gracefully: there is no *sound* §11 admission until the timing-annotated model lands for the core class, but the deriver is a cost-annotation pass rather than a separate verified estimator.
· Accept: aiT and Heptane stay unverified out-of-band cross-checks that flag a wrong timing annotation, never the bound.
· Trace: CJ-WCET, CJ-RTL-SAIL · [§18](verification-maximal-os.md#r-18-025)

**R-18-026** MUST: The verified filesystem carries four deliverables: L0 re-expressed in Gallina and verified over CompCert-C with VST/Iris; the VeriBetrFS B^ε-tree design re-proved in Coq/Iris; the L2 semantics with RefFS-style linearizability, crash, and liveness specs; and the L3 data-noninterference proof composed with the AEAD reduction.
· Accept: no bespoke Goose-to-C extractor is built; Yggdrasil and FSCQ are retained as cross-check and lineage, not bases.
· Trace: CJ-T · [§18](verification-maximal-os.md#r-18-026)

**R-18-027** MUST: Storage staging puts the small system-integrity reader and A/B transactor (the only storage TCB) on the critical path, with the four-layer filesystem following and below-the-line block services running availability-only from the start.
· Accept: the ordering reflects TCB membership, not layer count.
· Trace: CJ-DEVTREE · [§18](verification-maximal-os.md#r-18-027)

**R-18-028** IS: Radio staging does not wait for integration: an off-die register-slave SDR transceiver behind a certified analog front end gives the identical architecture today, with on-die RF later buying only physical and interface simplification.
· Accept: srsRAN/OpenAirInterface, openwifi, GNSS-SDR, and aff3ct anchor feasibility; openwifi's open-RTL low-MAC is the harvestable existence proof for the fixed-function link-layer timing sequencer.
· Trace: CJ-SAIL · [§18](verification-maximal-os.md#r-18-028)

**R-18-029** MUST: The radio parsers are generated, not hand-transcribed: a verified ASN.1 → Narcissus front end over the published 3GPP modules, with the IEI/TLV 5G-NAS grammar hand-written and differential-tested against four independent references.
· Accept: the crown-jewel grammar spec shrinks to one reusable oracle-checked codec rather than thousands of hand-copied pages (R-05-048, R-05-050).
· Trace: CJ-FORMAT · [§18](verification-maximal-os.md#r-18-029)

**R-18-030** IS: Memory staging is capacity-limited, not availability-limited: first parts are planar single-tier at order 1–2 GB, with the 4–8 GB phone envelope arriving if and only if sequential-3D tier counts reach 8–16.
· Accept: the interim is less capacity and a leaner roster, never a different mechanism; no deleted DRAM machinery returns, and neither bonded die-stacking nor an SRAM chiplet is held in reserve.
· Trace: CJ-DEVTREE · [§18](verification-maximal-os.md#r-18-030)

**R-18-030a** MUST: The multi-tier envelope is planned as upside, the single planar tier being the case the roster is shown to close on: the 1–2 GB fit carries the base system, servers, and compositor in hundreds of megabytes, a framebuffer in tens, a composition-sized origin budget with crash-only eviction, and an inference server admitting only the smallest quantized class or none.
· Accept: the gate is a materials result, not calendar time or yield learning (R-18-008a), so every capacity claim above the single tier is stated as contingent and no roster element depends on a tier that has not been built.
· Trace: CJ-DEVTREE · [§18](verification-maximal-os.md#r-18-030a)

### 18.5 The capstone

**R-18-031** MUST: The end-to-end composition proof is the capstone workstream, staged last because it consumes the others, with three sub-deliverables: the machine-checked *statement* of T and each seam lemma with interfaces aligned; the linking theorem discharged incrementally; and the boundary ledger of *D* and *Ax* maintained as an enumerated, reviewed artifact.
· Accept: sub-deliverable (a) is engineering-free and authored *now*, ahead of the proofs it will link, doubling as the coverage checklist.
· Trace: CJ-T · [§18](verification-maximal-os.md#r-18-031)

**R-18-032** IS: Like RTL ⊑ Sail this is a hard, currently-nonexistent deliverable for the strong form of G3, but its *statement* is available immediately and is the higher-value half: it turns "a dozen things are proven" into "the conjunction claims exactly this, and rests on exactly that", the review artifact the crown-jewel gate most needs.
· Accept: CompCert ⋈ CertiKOS layered refinement, DeepSpec, and seL4's own integration are the methodological anchors; none is at this scope, which is why the linking theorem is the deepest outstanding proof.
· Trace: CJ-T · [§18](verification-maximal-os.md#r-18-032)

**R-18-034** MUST: The atomic-requirements register is a §18 workstream with a named owner, not a by-product: extraction of every normative obligation with its acceptance criterion and its trace, plus traceability forward to the Coq specifications and the Sail model as those land, revved with every amendment to the specification and gating each release alongside the proofs.
· Accept: §18 lists it as a deliverable with an owner. Like the composition theorem's statement it is engineering-free and available now, ahead of the artifacts it will trace to, which is why it is a day-one deliverable under R-18-003b(iv). This discharges R-05-154.
· Trace: CJ-T, CJ-SAIL · [§18](verification-maximal-os.md#r-18-034)

**R-18-035** IS: The register's standing output is the extraction-defect list, which is the review gate's agenda rather than an appendix to it: an obligation with no requirement is unreviewed, and a requirement with no acceptance criterion is a spec defect by R-05-153's own rule.
· Accept: the defect list is carried in the register with a disposition per entry, and the gate's record cites it.
· Trace: CJ-T · [§18](verification-maximal-os.md#r-18-035)

**R-18-033** MUST: Two requirements never trade: the verified TCB, and capabilities as the sole authority. Everything else (ship date, core counts, radio bandwidth, acceleration) bends around them.
· Accept: any proposed change is checked against these two first.
· Trace: CJ-T, CJ-CERISE · [§18](verification-maximal-os.md#r-18-033)

---

## Coverage

All eighteen normative sections are extracted, at 1182 requirements. §19 is non-normative and yields none. Counts include the 260 letter-suffixed entries, each of which is a full entry and not a variant of the one it follows; the entries themselves are the list, and enumerating their IDs a second time here would be a derived fact restated where nothing checks it. Every figure in this section, the table included, is recomputed from the entries by `tools/check.ps1` rather than kept in step by hand. Section coverage is a precondition for the R-05-150 gate, not the gate itself: the review still has to decide, per section, whether the extraction is *complete*, which is the question the register exists to make askable.

| Section | Status | Entries |
| --- | --- | --- |
| **§1 Goals** | **extracted** | **8** |
| **§2 Non-Goals** | **extracted** | **7** |
| **§3 Threat Model** | **extracted** | **9** |
| **§4 Organizing Principle** | **extracted** | **12** |
| **§5 Languages & Verification** | **extracted** | **195** |
| **§6 Trusted Computing Base** | **extracted** | **27** |
| **§7 Kernel** | **extracted** | **57** |
| **§8 Authority Model** | **extracted** | **61** |
| **§9 Boot & Root of Trust** | **extracted** | **38** |
| **§10 Storage & State** | **extracted** | **50** |
| **§11 Updates** | **extracted** | **32** |
| **§12 System Servers** | **extracted** | **105** |
| **§13 Packaging & Supply Chain** | **extracted** | **37** |
| **§14 Userland** | **extracted** | **22** |
| **§15 Hardware Platform** | **extracted** | **340** |
| **§16 Reliability** | **extracted** | **28** |
| **§17 Residual Risks** | **extracted** | **108** |
| **§18 Realization** | **extracted** | **46** |

§19 is non-normative and yields no requirements.

## Extraction defects

Normative claims that resist atomic restatement, per R-05-153. This is the register's standing output and the review gate's agenda (R-18-035): an obligation with no requirement is unreviewed, and a requirement with no acceptance criterion is itself a spec defect by R-05-153's own rule. A claim booked here is a defect in [verification-maximal-os.md](verification-maximal-os.md) to be repaired there, never a register omission to be worked around here.

**Open defects: one, with six rows.**

**D-CSR: the surviving CSR bank is not decided register by register.** Sweep 1's class, found in a fourth list: §15 enumerates the deleted CSRs by name and states the residue nowhere, while R-07-015 and R-15-214 both quantify over "every CSR a partition can name." R-15-001b closes the *artifact* half (the enumeration now exists, in [isa-profile.md](isa-profile.md) §5) and this entry holds the rows the enumeration found that no requirement decides. Each is a defect in [verification-maximal-os.md](verification-maximal-os.md) §15 to be repaired there; the profile view carries the same rows marked **open** and decides none of them.

| Row | What is undecided | Indicated |
| --- | --- | --- |
| `mie` / `mip` | the machine-timer bits have a consumer (R-07-043, R-15-063); the external- and software-interrupt bits do not (R-15-065, R-15-066) | present, narrowed to the timer bits |
| `menvcfg` | R-15-049's ground against `Smstateen` applies word for word and is stated only for `Smstateen`; `Zicboz`'s `CBZE` bit is the case to check (R-15-060) | deletion |
| `mvendorid` / `marchid` / `mimpid` / `mconfigptr` | one Sail model frozen with the proof (R-15-005) has no runtime discovery consumer | hardwired zero |
| `mhartid` | one kernel binary across core classes needs hart identity (R-07-012); no requirement says so | present |
| `tselect` / `tdata1–3` | the lifecycle fuse is stated for the Debug Module and trace (R-15-078, R-15-079); the trigger module is not named, and its CSRs are M-mode-accessible in standard RISC-V: mutable hidden state surviving a partition switch, the shape admission test (3) rejects (R-15-010, R-15-012) | absent, or fused with the DM |
| `DDC` | purecap-only with no hybrid mode (R-15-001) leaves it without a consumer, but nothing retires it and the total restore would have to name it (R-07-015) | absent |

The `tselect` / `tdata` row is the one with a security consequence rather than a surface consequence, and it is the row that most repays being asked early.

An empty list is not the same as a swept one, which is what this entry turns on. Three sweeps run over the register, each finding instances the one before it could not see:

1. **What does a reviewer open to decide this?** Asked of one acceptance criterion at a time. Criteria that quantify over a list no artifact holds are the class this finds; it is closed for the three lists it found (the frozen profile, the absence contract, the crown-jewel inventory), each a derived view under R-15-001a, R-15-100a, and R-17-016a.
2. **What does the register restate that nothing checks?** The widened form of the same class, covering any claim held in a second place with no artifact checking the two agree. This is why traces are bookmarks rather than line numbers, and why the derived views are machine-checked in both directions rather than maintained by care.
3. **Which enumerations disagree?** Asked of every list stated more than once. The type-level obligations (R-05-029) and the axiom set (R-06-011) are each stated once and cited elsewhere.

The standing instruction is that sweep 2's question has not been asked exhaustively, so further instances should be assumed present rather than absent. `tools/check.ps1` decides the instances already found; a newly found one is a spec defect booked here with a disposition, and a repair whose correctness nothing checks is itself an instance of the class.
