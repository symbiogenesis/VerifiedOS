# Evaluated Alternatives, Lineage, and Register Review

*Scope: `architectural-alternatives.md` (AA) and `inspirations.md` (IN), spot-checked against `verification-maximal-os.md` and `requirements-register.md`. AA and IN are non-normative by their own headers. Entries move between the two documents as the material settles, so subjects below are named rather than attributed to a file.*

*References are symbolic: requirement IDs and section headings, never line numbers, per the register's **traces are bookmarks, not line numbers** rule. Counted figures the register owns (entry totals, conferral counts) are not restated here; `tools/check.ps1` recomputes them from the artifact that owns them, and a copy in this document would be a derived fact with nothing checking it.*

---

## 1. Alternatives evaluated and declined

**ISA and microarchitecture.** Belt/Mill-class deferred to a hypothetical gen-2 (protection model already subsumed by CHERI; backless memory fails the admission test on allocate-time data-dependent timing; the spiller is inseparable from the belt), with EDGE/block-atomic preferred over the belt if the lever is ever taken. Itanium/EPIC/VLIW rejected as base direction: it abandons the RISC-V substrate for a post-mortem ecosystem, the hoped-for simplification runs backwards, and microarchitecture-coupled binaries fork the single-recompile-target premise. Secure speculation via information-flow tracking (SecureBOOM, STT, DOLMA) imports nothing: a foreign prover, maximal inflation of the least-built arrow, and it closes only one of four blockers. Non-speculative out-of-order and the invisible-speculation family are rejected on the design-specific ground that the latency wall OoO exists to hide is deleted by flat SRAM. SEAM-V decoupled vector backend, OISC and transport-triggered architectures, test-bit-and-branch, a bespoke base ISA, bespoke capability semantics, `Zcmt` table jumps, and self-timed datapath logic are each declined with a stated ground. Fixed-slot barrel multithreading is the one partially admitted entry, logged as the first-choice gen-2 non-speculative throughput lever, with dynamic-issue SMT still rejected; the entry notes explicitly that the SMT rejection had been read too broadly.

**Execution and metadata substrates.** CHERI-Wasm as a hardware ISA rejected as ISA, sandbox target, and deployment format. ELF as the on-device executable and package format declined, most of its machinery serving excluded facilities and the residue leaving an attacker-facing offset-linked grammar inside the verified loader. High-level-language computer architectures rejected, the safety atom already being CHERI and the semantic-gap closure belonging to the verified compiler. Tile-state extensions (x86 ACE, Arm SME) not imported. Bespoke full-PQC and NTT instruction sets declined, RVV already giving straight-line constant-time lattice arithmetic. Mon CHÉRI conditional capabilities and an initialization tag plane rejected. Programmable tag-policy engines (PUMP, SAFE micro-policies, CoreGuard) rejected: the rule cache is hidden history-dependent state surviving a partition switch, and runtime-loadable policy inverts the frozen-with-the-proof discipline.

**OS structure.** Language-based isolation as the *sole* mechanism (Singularity, Verve, Tock, Midori, Theseus) rejected, one unsafe block or miscompilation getting unrestricted access. Six Oberon mechanisms declined individually. Exokernel and unikernel structure recorded as already converged rather than imported. Decentralized-information-flow architectures (HiStar, Asbestos, Flume) not imported as an architecture, DIFC already being present over a capability kernel and CHERI at finer granularity. MultiZone mapped component by component onto strictly stronger mechanisms, with the inverse proposal (M-mode plus PMP only, no CHERI) rejected as the base on four grounds. Historical capability-machine runtime machinery (KeyKOS banks, meters, keepers; orthogonal persistence; single-level store) declined, whole-machine persistence conflicting with measured boot and eager zeroize, and storage otherwise becoming a second origin of authority able to resurrect a capability after revocation. Object Memory Architecture not imported, the OID-to-location indirection being the deleted MMU generalized to per-object. Enclave architectures (Sanctum, MI6, Keystone, CHERI-TrEE, Tyche) not imported, defending against speculation and sharing this design already deletes.

**Devices and peripherals.** External roaming authenticators, DIVA, dedicated fixed-function GPUs, uniform graphics widening, Vulkan and software GPU personalities, OLED aging compensation, Adaptive-Sync, firmware-driven NPUs, physical bifurcation of the radio onto a second die, and FullMAC radio controllers are each declined. General lockstep and TMR are deployment-deferred rather than rejected, available as graded options where a safety case pays for them.

**Memory technology.** Memory encryption and the integrity tree declined outright, memory cryptography protecting an interface this machine does not have. SRAM chiplets and bonded die-stacking declined, each die being a separate mask set and supply-chain entity. Dynamic and adaptive low-leakage SRAM techniques, active sub-threshold memory, transparent variable-rate compression, and runtime deduplication declined. Non-volatile main memory and unified SOT-MRAM storage carries a full five-claim decomposition and a disposition: reject the wholesale all-CAAC-IGZO, all-SOT-MRAM single-level store as the base, keeping bespoke volatile SRAM normative. Static code overlays are deferred behind a measured trigger rather than rejected. Deleting the store buffer for sequential consistency by absence clears four of five gates and is booked as an open design-space question with an explicit falsifier.

---

## 2. Rejections whose reasoning is premise-dependent

These are not errors. Each is a place where a disposition rests on something the documents themselves book as unfinished, and the disposition is stated with more finality than its premise supports.

**The single-prover axiom underwrites a whole family of rejections.** SecureBOOM/UPEC, GLIFT/SecVerilog, riscv-formal, EasyCrypt, HACL\*/libcrux, Verve, VeriBetrFS/Perennial, and above all the refusal to inherit seL4's Isabelle proof all turn on it. That two checkers in the trust base are strictly worse than one is a value judgment rather than a theorem, and proof diversity is the standard counter-position. The seL4 entry concedes the two-checker alternative's edge is narrower than it looks and that the inherited proofs would not cover this configuration anyway, which means the maturity argument does little work either way. Every foreign-prover rejection inherits the premise.

**Verify rather than hedge rests on a proof that does not yet exist.** The PMP-backstop, IOMMU, MTE, shadow-stack, and initialization-plane rejections are justified by CHERI being the mechanism the design verifies most deeply, while R-17-039 records the Sail-to-RTL layer as the least-built and notes no artifact at full-application-core scale. The disjoint-failure-domain hedge is dropped on the strength of a future artifact. R-17-037 books the concentration honestly; the rejection logic is nonetheless hostage to it.

**The out-of-order rejection is hostage to the memory bet.** *The latency wall it exists to hide is deleted* presumes flat, low-latency, multi-gigabyte on-die SRAM, and R-15-163 makes the vertical tier count conditional on a low-temperature p-type device result that is demonstrated in the laboratory and not at array quality or manufacturable scale, rather than graded by effort. If the memory bet degrades toward a single planar tier, the argument weakens in proportion.

**The five-part admission test is self-referential.** A large fraction of dispositions are decided by *fails admission test N*, where the test is the design's own construct encoding prior commitments. The rejections are exactly as strong as the test, which is never independently justified against alternatives.

**The substrate-cost disqualifier leans on a partly aspirational ecosystem.** EPIC, OISC and TTA, Wasm, HLLCA, and bespoke ISAs are declined for forfeiting the Sail model, the CHERI-CompCert backend, Islaris, Cerise, and RVV, while the same documents record the CHERI-CompCert backend as priority-zero and unbuilt, SECOMP2CHERI as workshop-stage, and the CHERI-TAL soundness metatheorem as yet to be authored. The asymmetry is real and smaller than stated.

**The memory-encryption rejection rests on a scope line the documents call load-bearing.** R-17-059 states it plainly: the memory path is defended by absence of surface, and if that line is ever judged wrong there is no encryption to slow an attacker and no freshness check to catch a replay. The claim that an attacker at that level would equally reach the keys is asserted rather than analyzed, and separate-key-holder constructions exist precisely to complicate it.

**No foreign computers has a judgment-call boundary.** The rule declines GPUs, NPUs, FullMAC radios, and external authenticators while admitting the radio turnaround sequencer, FEC blocks, and the USB-PD sequencer as matter rather than software. The line between a timer plus a small state machine and a minimal microcontroller is a continuum drawn by fiat, and the zero-authority eUICC is admitted as a named exception, which concedes the rule takes exceptions.

**Two further criteria are outcome-loaded by construction.** Choosing the instruction set of record by whose semantics is already mechanized is a path-dependency argument rather than a complexity one, and it returns the incumbent under any incumbent-favoring criterion. Rejecting VLIW for violating the one-base-ISA, one-kernel-binary property rejects a candidate for failing a rule written to exclude exactly such couplings. Both are logically fine and neither is evidence.

**The low-allocation-churn argument assumes its conclusion.** Static composition minimizing churn is asserted for a general consumer device whose allocation behavior is not yet measured, while code overlays are deferred precisely because no measured roster exists. Measurement is demanded in one place and waived in the other.

---

## 3. Where the documents admit a simpler design suffices

The MultiZone entry is the bluntest: PMP-only's appeal is real and almost entirely about realization, and it is rejected as the base *on the goal function, not the effort function*. For a goal short of maximal assurance, the simpler design suffices, and the document says so. KataOS is used as a foil that stops an assurance tier short on every shared axis and actually shipped. GrapheneOS is recorded as the terminus of the hardening road on commodity hardware. Static code overlays concede that the architecture may reject an application whose resident image exceeds the fixed SRAM budget, an accepted capacity limit rather than an omission. The all-SRAM capacity ceiling states the density price plainly, leaving memory-hungry workloads to a DRAM design. Radiation hardening and lockstep are graded to the deployment. Barrel multithreading, deferred-fault poison loads, and wider superscalar are all deferred to gen-2 should the in-order tax bind, which is the same admission from the other side: if performance never binds the simpler base suffices, and if it does the base was over-simplified. Honest costs are booked for residual judder, no-GPU throughput, absent credential portability, no legacy radio coverage, and scalar cores without scratchpads.

---

## 4. Tensions with the normative specification

**The register-file flush-set wording is stale in IN.** The RVV/Zfinx entry calls the scalar f-register file a `fence.t` flush-set member, while R-15-213 makes the store buffer the sole member and R-07-016 declines register-file membership under *verify rather than hedge*. The AA store-buffer entry is consistent with the normative text; the RVV entry is loose against it.

**The Oberon quiescent-point proposal is an open, documented tension.** IN proposes binding revocation-sweep quanta to slot boundaries and says explicitly that it is proposed and not taken, since R-08-007 specifies the incremental preemptible form. IN is arguing that the normative spec carries a deletable proof obligation. That is unresolved by design rather than by oversight.

**The store-buffer entry enumerates a pending change list.** `Ztso` with a retained store buffer stays normative (R-15-004, R-15-088), and AA books sequential-consistency-by-absence as an open question with a future spec-body change list attached. Consistent today, conflicting on resolution.

No contradictions were found on the checked points for the MCS deletion against the cyclic executive, the object-model deletions, the asynchronous-interrupt deletion and sentry collapse, the `Zcmt` rejection (R-15-036q), or admitted macro-op fusion.

---

## 5. Lineage, grouped by what was taken

**Kernel and proof method.** seL4 supplies the kernel design base (endpoints and notifications, first-class revocation as a statement, the non-interference theorem statement, zero post-boot kernel allocation) and the 2024 multikernel work as live lineage, but not the Isabelle proof, VSpace, MCS, untyped and retype, CSpace, or the derivation tree. CertiKOS supplies proof method only (deep specifications, abstraction layers, CompCertX), with VST as the sequential closing logic and the concurrency machinery left behind. KataOS/Sparrow is convergent evidence and a foil. Barrelfish supplies the multikernel model without the dynamic knowledge base. SemperOS supplies the shape of distributed cross-core capability revocation and its scaling evidence, not code or proof. Akaros supplies evidence from the performance pole that spatial core partitioning removes OS jitter.

**Compilation, languages, type systems.** SECOMP and CompCert supply robust preservation and the CHERI backend start. Vélus supplies Coq-verified Lustre for the control tier. The Necula-to-Morrisett-to-Appel line supplies the CHERI-TAL type-soundness half, with CT-Wasm for constant-time as taint types, StkTokens for the linear and affine capability discipline, and definite initialization as a type attribute. The language-safety lineage (Singularity, Verve, Midori, Theseus) supplies discipline carried to the artifact, not runtimes, collectors, or live evolution. The register-allocation, region-inference, and static-planning line supplies the static memory plan that replaces the runtime heap. Oberon supplies whole-stack parsimony as method, the module key as load-time refusal, and the quiescent point as a proposal.

**Crypto.** Fiat-Crypto for correct-by-construction field arithmetic; HACL\*/libcrux and EasyCrypt/formosa-crypto as deliberately minimized interims; SSProve/FCF as the Coq-native destination for game-based reductions.

**Capability hardware.** The CHERI programme supplies the substrate and Morello reachable-capability monotonicity as the machine-checked security property. CheriOS supplies the single-address-space purecap thesis and the existence proof for deleting the MMU. CHERIoT supplies privilege-as-PCC-permission, the switcher and sentries, the CNode-free object model, heap claims, the deterministic load filter, and the PMP-drop argument, but not its encoding, loader, or autonomous sweep engines. Capability-checked DMA replaces the IOMMU. CVA6-CHERI and COSMIC supply the scalar front end and conformance method; Codasip supplies commercial shipping evidence and the PMP-removal precedent; CHERI-TrEE and Tyche supply attestation-reasoning prior art and a foil respectively.

**Systems and product patterns.** systemd for declarative supervision shape; OSTree for the immutable content-addressed base with A/B rollback; Nix and Guix for purely functional build and full-source bootstrap; secureblue for the hardening ethos carried from mitigation to proof; GrapheneOS for the seized-device threat model taken to silicon; ChromeOS and OpenTitan for the verified-boot root of trust as a product template; Fuchsia and FIDL for capability IPC and wire discipline, with WIT supplying the type layer; Plan 9 for private namespaces and intent routing; BeOS for typed attributes and translator graphs made static; the KeyKOS lineage for typed data persistence without app-authored serializers; Cerebras for extreme-scale share-nothing all-SRAM evidence; openwifi and Zephyr for the SoftMAC split; the space-grade line for deployment-graded realization; PRET for pollable events and the slot-boundary timer as sole asynchronous trap.

---

## 6. Redundancy and complexity the documents admit

**There is no duplicate revocation mechanism.** A derivation tree would be a second mechanism for a property the CHERI machinery delivers over strictly more of the machine, and R-08-004 carries the CHERI mechanism alone. IN records the argument rather than the duplication, which is the right residue: the exclusion is the load-bearing half of taking the CHERIoT-shaped object model.

**The store buffer meets four of five deletion gates and is retained pending a measurement.** By the design's own logic it is a structure currently carried as a candidate for deletion.

**The preemptible sweep carries a proof obligation the documents believe is deletable.** Rebinding sweep quanta to slot boundaries buys a deleted obligation rather than a mechanism, and is proposed and not taken.

**Temporal safety is covered at three layers.** The static memory plan fixes placement, the CHERI-TAL linear and affine discipline covers compile time, and the load filter with its budgeted sweep and quarantine covers runtime. The documents frame this as composition, and R-05-159 states it as a conjunction rather than a hedge, but it remains the largest standing stack of overlapping mechanisms for one property.

**Two interface formalisms plus a label layer.** A WIT-derived type layer joined to a FIDL-derived wire layer, with flow labels as a first-class concern, is deliberate and is still real surface.

**Five retained instruments are kept on performance arguments alone.** Fractional LMUL, three VLENs, vector masking, indexed gather/scatter with segment operations, and hardware divide and remainder each fail the deletion gate on cycles rather than on proof benefit. The rejected-simplifications table records these as judgment calls.

**Three asymmetries a critic can name.** Macro-op fusion is admitted precisely because it is architecturally transparent while other transparent extensions are cut; the sentinel gets the only lockstepped core, since a detector cannot report its own corruption; the eUICC is the sole admitted foreign computer. Each is justified in place.

**Aesthetic reasoning appears as a decision input.** EDGE is preferred over the belt because block-atomic commit *rhymes with* the rest of the architecture. Rhyming is not an admission-test criterion, and its appearance in a disposition is a small methodological softness.

**Deferred machinery still looms.** Static code overlays and generation-tag temporal safety are both preserved as options, and each would reintroduce a mechanism family deleted elsewhere, so the complexity-deleted ledger is partly contingent on the capacity bets holding.

---

## 7. Register: contradictions and overlaps

**R-16-015 against R-08-031** is the strongest finding, with the defect on R-16-015's side rather than R-08-031's. R-08-031 says no compartment reads an architectural cycle, time, retirement, or performance counter, and its accept cites R-15-077, which deletes the counters outright. R-16-015 nonetheless lists *raw counter reads by holders of the fine-grained-time permission* among four replay-nondeterminism sources. Since the counters do not exist, the loose phrase is R-16-015's; what it means is time-service reads at granted precision.

**R-08-040 against R-12-052.** R-08-040 states unconditionally that every while-active grant carries a maximum-duration ceiling enforced through kernel expiry. R-12-052 declares the emergency-call microphone grant deliberately exempt and the only such exemption. R-08-040 never mentions it.

**R-16-012 against R-16-021.** An unqualified *no verbose logging mode exists* against a mandated capability-scoped, lifecycle-gated diagnostic sink. The reconciliation (unlabeled and ambient versus labeled and gated) lives only in R-16-012's accept text, not in its statement.

**R-05-022 against R-05-109 and R-05-073.** R-05-022 counts aiT and Binsec/Rel among five interim non-Coq anchors carrying retirement rules, while R-05-109 says no admitted bound cites aiT as its ground and R-05-073 says Binsec/Rel is never the axiom. An artifact outside the trust base is not an anchor and needs no retirement, so the five-entry list mixes two categories.

**R-15-177 against R-15-189k.** Scrubbing is accepted as present *on every array*, while R-15-189k runs background scrubbing on powered domains only. R-15-189k carries the reconciliation; R-15-177's accept is unqualified.

**R-17-058 against R-15-184.** Rowhammer is *dramatically reduced rather than mitigated* in one place and has *no charge-disturbance analog in SRAM*, apparatus *deleted rather than tuned*, in the other. Reconcilable through R-15-184's own residual on SRAM disturb modes, but the two headlines disagree in strength.

**Aligned restatements**, stated two or three times each and worth citing rather than repeating: no asynchronous interrupt delivery; no MMU and a single address space; biometrics never releasing at-rest keys; sealed cutoffs dominating emergency call; lockout cutting microphone, camera, and USB while the radio stays pageable; global mode transitions being rare and never load-following; no link-time specialization on confidential values; no POSIX shim; no dynamic speculation. Three earlier collisions are self-documented as repaired (competing axiom enumerations scoped, crown-jewel roll-call drift closed by conferral, the obligation list replaced by citation), and the repair pattern is consistent.

---

## 8. Register: the open extraction defect

The surviving CSR bank was never decided register by register. Deleted CSRs are enumerated by name while the residue is stated nowhere, and both R-07-015 and R-15-214 quantify the total-restore obligation over *every CSR a partition can name* without that list existing. R-15-001b closed only the artifact half, `isa-profile.md` §5.3 now holding the enumeration with its rows marked open; no requirement yet decides membership.

Of the open rows, the trigger module is the one with a security consequence rather than a documentation one: in standard RISC-V its CSRs are machine-mode accessible and therefore reachable in the production lifecycle state, and a trigger is mutable hidden state that fires on an address or data match and survives a partition switch, which is the shape admission test 3 rejects. The remaining rows are cause and trap-value reporting, the interrupt-enable and pending bits, `menvcfg`, the identification registers, `mhartid`, and `DDC`.

The defect is also the register's own exhibit for its standing instruction: three enumeration-closing sweeps ran, and the assumption that a fourth list existed is what surfaced this one.

---

## 9. Register: weak acceptance criteria

Roughly a fifth of acceptance criteria are documentation-presence checks, consistency citations, tautologies, or existence-of-a-booking checks rather than decision procedures. The distribution is uneven and mostly explicable:

| Where | Character |
| --- | --- |
| §17 | Weakest by design, and honest about it: the preamble declares acceptance to be *booked with its owner and scope rather than absorbed*, so nearly every entry's criterion is a presence-of-text check |
| §15, §12, §5 | Largest absolute counts, mixing crisp mandates with bookings and scope statements |
| §1, §3 | Weak without §17's excuse: goal and threat entries whose criteria restate their own premises |
| §9, §11, §13, §14 | Mostly crisp |

Explicitly circular cases are worth separating from merely weak ones. R-05-151's criterion is the document containing it. R-01-001 and R-04-001 are each the other's check. R-03-008 and R-17-030r each name the other as decider, and R-17-030r concedes its half is a review-gate finding with nothing enforced. The recurring *the §17 residual entry exists* pattern is sound bookkeeping and content-free about the underlying claim.

---

## 10. Register: the conferral mechanism

Requirements carrying `· Fail-closed:` confer into R-17-030r's seam register, and those carrying `· RoT-fresh:` confer into R-10-013a's freshness enumeration, with both directions checked: an unconferred member and an uncollected conferral each fail the build. Spot-checking the fail-closed conferrals against the text found them consistent with the collector.

The mechanism is structurally sound for its stated goal, which is drift detection between register and requirements, the demonstrated failure mode it was built to repair. It is explicitly not a completeness mechanism, *fails closed* and *needs freshness* being admitted as undecidable judgments over which `tools/check.ps1` over-approximates by vocabulary scan with forced disposition.

Two gaps are admitted rather than hidden. A refusal phrased in words the over-approximation does not catch confers nothing and passes, and R-17-030r notes several of its own members were found by running the scan rather than by inspection, which evidences both that the scan works and that it is the only backstop. Nothing forces an author adding a refusal to write the conferral line except that scan and the review gate. R-10-013a's rule that a further conferral is not admitted until R-10-013 names the state it adds is additionally backwards-looking: the collector gates the conferral rather than the conferral driving the collector, which is conservative and means a legitimate freshness need blocks on editing one specific entry.

---

## 11. Register: machinery cost

**The entry grammar is violated by the register itself.** The header specifies one `· Accept:` line per entry. R-08-012e, R-10-013a, and R-17-030r carry three each; R-15-190 and R-15-189j carry two. Which bullet decides the requirement is undefined, in a document whose premise is one decidable criterion per obligation. This is the clearest and cheapest fix in this section.

**The derived-view boilerplate is restated near-verbatim four times**, in R-15-001a, R-15-100a, R-17-001b, and R-17-016a. It should be one requirement cited four times, which is the register's own rule for a set stated in more than one place, and the pattern its third sweep exists to remove.

**The tooling is an unbooked precondition.** Derived figures embedded in normative prose are correct today and silently rotten if the checker is not run, so the register assumes its own tooling permanently. More sharply, `check.ps1 -Fix` rewrites the normative document it checks, and the tool that edits the register appears in no trust-base inventory or axiom set. R-05-151a already mandates negative-testing the trace checker against deliberately broken copies on the ground that a checker that has never failed is indistinguishable from one that cannot fail; the same reasoning applies to the tool's authority to write.

**Letter-suffix density is a signal worth reading.** Roughly a fifth of entries are post-hoc insertions. Prose-order numbering with permanent IDs is a deliberate and defensible choice, and this is not an argument against it; the density is evidence about edit rate against review stability, which is a different question the register does not ask.

**Two blocks read as specification rather than as requirements.** The dictionary-encoding entries and several multi-paragraph accept texts re-argue the design in place. This blurs the register's normative role, and it is the same content-versus-container question the derived-view rule settles elsewhere.

**The coverage matrix is the heaviest single machinery piece.** A full bipartite product of boundaries against properties, one row each, is tool-checked and therefore consistent, but it manufactures a large derived artifact with perpetual maintenance cost, and its failure mode is a pair citing a requirement that does not actually carry it, which is precisely the fidelity gap the checker admits it does not close.

---

## 12. The work list

*Distilled from the sections above; non-normative like the rest of this document. Items are grouped by what closing one costs, not by where it was found: **A** is a text edit whose answer the documents already contain, **B** is a call somebody has to make, **C** needs work that does not exist yet: a measurement, an argument, or a reading of the outside world. Each item names the requirements it lands on.*

**Convention.** When an item lands, delete the bullet. No departure notes, no strikethroughs: git history is the narrative, and what stands here is the open agenda.

### A. Defects: the answer is already in the documents

1. **Retire the raw-counter phrase from R-16-015.** The counters do not exist (R-15-077, R-08-031); the replay-nondeterminism source is time-service reads at granted precision.
2. **Name the exemption in R-08-040.** The emergency-call microphone grant (R-12-052) is the sole grant without a kernel-enforced duration ceiling, and R-08-040 currently states the ceiling unconditionally.
3. **Move R-16-012's reconciliation into its statement.** *No verbose logging mode exists* means no unlabeled ambient sink; the capability-scoped, lifecycle-gated diagnostic sink of R-16-021 is not one, and only the accept text says so.
4. **Split R-05-022's five-entry anchor list.** aiT and Binsec/Rel are outside the trust base by R-05-109 and R-05-073, so they are not anchors and carry no retirement rule.
5. **Qualify R-15-177's scrubbing claim** to powered domains, matching R-15-189k, which already carries the reconciliation.
6. **Align the Rowhammer headline.** R-17-058's *dramatically reduced rather than mitigated* against R-15-184's *no charge-disturbance analog, apparatus deleted*, with R-15-184's residual SRAM disturb modes as the qualifier on whichever wording survives.
7. **Fix the flush-set wording in the RVV/`Zfinx` entry.** The store buffer is the sole `fence.t` flush-set member (R-15-213), and register-file membership is declined (R-07-016).
8. **Restore one `· Accept:` per entry.** R-08-012e, R-10-013a, and R-17-030r carry three; R-15-190 and R-15-189j carry two. Either fold each set into one criterion or amend the header grammar to say which bullet decides; silence on that point is the actual defect.
9. **Collapse the derived-view boilerplate.** R-15-001a, R-15-100a, R-17-001b, and R-17-016a state it near-verbatim; one requirement cited four times is the register's own rule.
10. **Break the circular acceptance criteria.** R-05-151 (its criterion is the document containing it), R-01-001 against R-04-001, and R-03-008 against R-17-030r, whose own half is conceded to be a review-gate finding with nothing enforced.
11. **Give §1 and §3 criteria a decision procedure or §17's preamble.** Goal and threat entries currently restate their premises without §17's explicit *booked with its owner and scope rather than absorbed* excuse.

### B. Decisions: someone has to make the call

12. **Decide the surviving CSR bank register by register.** `isa-profile.md` §5.3 holds the enumeration with rows open, and no requirement decides membership, while R-07-015 and R-15-214 quantify total-restore over *every CSR a partition can name*. The trigger module leads: machine-mode-accessible in standard RISC-V, reachable in the production lifecycle state, and mutable hidden state surviving a partition switch, which is the shape admission test 3 rejects. Then cause and trap-value reporting, interrupt-enable and pending, `menvcfg`, the identification registers, `mhartid`, and `DDC`.
13. **Resolve the store buffer.** Four of five deletion gates clear; the fifth is a measurement. Take it, then either delete the buffer and execute the attached spec-body change list or close sequential-consistency-by-absence against its own falsifier, leaving `Ztso` normative (R-15-004, R-15-088).
14. **Take or drop the quiescent point.** Binding revocation-sweep quanta to slot boundaries deletes a proof obligation; R-08-007 specifies the incremental preemptible form. The proposal is unresolved by design and should stop being so.
15. **Book the tooling.** `tools/check.ps1 -Fix` writes the normative document it checks and appears in no trust-base inventory or axiom set, and derived figures in normative prose rot silently when it is not run. R-05-151a's negative-testing reasoning applies to the fixer's write authority, not only to the trace checker.
16. **Decide whether the register argues or cites.** The dictionary-encoding entries and several multi-paragraph accept texts re-argue the design in place; the derived-view rule already settles the same content-versus-container question elsewhere.
17. **Price the coverage matrix.** A full bipartite product is tool-checked and therefore consistent, but its failure mode, a pair citing a requirement that does not carry it, is the fidelity gap the checker admits it does not close. Decide whether the maintenance cost buys anything the per-requirement traces do not.
18. **Decide the conferral's direction and its forcing function.** Nothing makes an author writing a refusal add the `· Fail-closed:` line except the vocabulary scan and the review gate, and R-10-013a's rule that R-10-013 must name the state first makes the collector gate the conferral rather than the reverse.
19. **State the *no foreign computers* criterion.** The radio turnaround sequencer, FEC blocks, and the USB-PD sequencer are admitted as matter while GPUs, NPUs, FullMAC radios, and external authenticators are declined, with the zero-authority eUICC a named exception. Write the line, or record it as a judgment call taken case by case.
20. **Settle the admission test's standing.** Either justify the five parts against alternatives once, or restate the dispositions that turn on *fails admission test N* as consequences of prior commitments rather than as independent grounds. The same applies to choosing the ISA of record by whose semantics is already mechanized, and to rejecting VLIW for violating a rule written to exclude such couplings: both are sound and neither is evidence.
21. **Replace the aesthetic ground in the EDGE-over-belt preference.** *Rhymes with the rest of the architecture* is not an admission-test criterion; give the disposition a criterion or mark the ground explicitly non-deciding.

### C. Analysis and research: work that does not exist yet

22. **Argue the single-prover axiom, or narrow what it decides.** It underwrites SecureBOOM/UPEC, GLIFT/SecVerilog, riscv-formal, EasyCrypt, HACL\*/libcrux, Verve, VeriBetrFS/Perennial, and the refusal to inherit seL4's Isabelle proof, and *two checkers are worse than one* is a value judgment against a standard counter-position. Needs a written argument against proof diversity, including current practice outside this project, or a restatement of the dependent rejections on grounds that survive without it.
23. **State the fallback if the Sail-to-RTL layer does not scale.** R-17-039 records it as least-built with no artifact at full-application-core scale, and R-17-037 books the concentration; the PMP-backstop, IOMMU, MTE, shadow-stack, and initialization-plane rejections all spend that future artifact. Write what each becomes if it lands late or partially.
24. **Grade the memory bet, and state what degrades with it.** R-15-163 makes vertical tier count conditional on a low-temperature p-type result demonstrated in the laboratory rather than at array quality or manufacturable scale. Needs a current reading of that device line, and a stated position on the out-of-order rejection under a single-planar-tier outcome, since *the latency wall is deleted* weakens in proportion.
25. **Analyze the separate-key-holder constructions against R-17-059.** The memory-encryption rejection asserts that an attacker at that level equally reaches the keys; the constructions that exist to complicate exactly that claim are not addressed, and R-17-059 already calls the scope line load-bearing.
26. **Restate the substrate-cost disqualifier at honest maturity.** The CHERI-CompCert backend is priority-zero and unbuilt, SECOMP2CHERI is workshop-stage, and the CHERI-TAL soundness metatheorem is unauthored, while EPIC, OISC and TTA, Wasm, HLLCA, and bespoke ISAs are declined for forfeiting them. The asymmetry is real and smaller than stated; the restatement wants a periodic refresh of upstream status.
27. **Measure allocation churn or defer the claim.** Static composition minimizing churn is asserted for a device whose allocation behavior is unmeasured, while static code overlays are deferred precisely for want of a measured roster. Run the measurement, or put the churn argument behind the same trigger.
28. **Make the deferred-machinery contingency visible.** Static code overlays and generation-tag temporal safety each reintroduce a mechanism family deleted elsewhere, so the complexity-deleted ledger is contingent on the capacity bets holding. Name which families, in the ledger.

---

*The documents are internally disciplined about booking honest residuals, and most of the weaknesses in section 2 are acknowledged somewhere in the text. The critique is that the dispositions cite those premises as settled when arguing against alternatives.*
