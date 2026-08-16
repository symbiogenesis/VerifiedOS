Report: Evaluated Alternatives & Lineage in the VerifiedOS Design Documents
Scope: architectural-alternatives.md ("AA") and inspirations.md ("IN"), with spot-checks against verification-maximal-os.md ("spec"). Both documents are non-normative by their own headers. Both files end mid-entry (draft truncation), noted where relevant.

1. Every radical architectural alternative evaluated and rejected/deferred, with stated reasons
Organized by the AA document's own section order. Section headings are quoted verbatim.

ISA / microarchitecture alternatives
"Belt / Mill-class architecture: deferred to a hypothetical gen-2" — Mill's protection model (turfs, portal calls, PLB) is "already subsumed by CHERI"; backless memory "fails the admission test" (data-dependent timing on allocate); the spiller is "inseparable from the belt" and a hardware shadow stack is excluded "as retrofit complexity"; the belt's real wins are ILP/register-file hygiene, not security. Gen-2 only, and EDGE/block-atomic preferred over belt "on transactional-coherence grounds."
"Itanium / EPIC / VLIW" — rejected as base direction. EPIC "abandons the RISC-V substrate … into a post-mortem ecosystem" (IA-64 discontinued 2021); the hoped-for simplification "runs backwards" ("the tax is the price of forbidding speculation, not of a removable mechanism"); "bespoke, microarchitecture-coupled binaries" are "the disqualifier" (forks the single-recompile-target premise, re-couples ISA to microarchitecture, re-mints every FPCC certificate). ALAT fails admission tests 2/3 (hidden history state, data-dependent aliasing signal); RSE fails test 5 (autonomous memory-writing engine); full predication rejected as ISA-surface inflation (Zicond is the admitted minimal form). Two atoms distilled and kept (non-normatively): NaR/NaT deferred-fault poison loads and wider in-order superscalar + verified static scheduling.
"Secure speculation via information-flow tracking: SecureBOOM, STT, DOLMA" — no import. Four grounds: UPEC is "a foreign prover … an oracle, never the closing axiom" (single-prover rule); it "maximally inflates the least-built arrow" (RTL ⊑ Sail over an OoO core); it "closes one of four blockers" (leak only — leaves WCET intractability, hidden predictor state surviving partition switches, and classical channels); weaker confidentiality scope (registers declared non-confidential).
"Non-speculative out-of-order and the invisible-speculation family" (NS-OoO, InvisiSpec, delay-on-miss, CleanupSpec, SafeBet, DAE, "deterministic time-based CPU") — rejected. The "decisive" reason: the latency wall OoO exists to hide "is deleted" by flat SRAM; real MLP requires memory-dependence speculation (a forbidden history-indexed predictor); the reorder window "collapses to the next unresolved branch" (≈5–7 instructions); dynamic scheduling is "data-dependent timing" (test 2) and breaks tree-sum WCET; ROB/RS/LSQ are new flush-set state (test 3) and inflate RTL ⊑ Sail. InvisiSpec family shares the SecureBOOM verdict; DAE "imports nothing the vector unit is not already."
"SEAM-V decoupled vector backend" — rejected: queue-occupancy-dependent completion breaks tree-sum WCET; backend-local instruction supply is "a second instruction-fetching computer"; request-bound prefetch is history-indexed hidden state; cross-packet hazard tracking is a dynamic scoreboard.
"Minimal-ISA extremes: OISC and transport-triggered architectures" — rejected: pays "the substrate-cost disqualifier in full … into a deader ecosystem"; TTA re-couples binary to microarchitecture; "minimal instruction count is not minimal proof surface" once capabilities/DMA/interrupts/timing are modeled (the verified compiler proof grows). Parsimony atom already banked inside RV64.
"Three further ISA amendments: all declined under the frozen-profile gate" — test-bit-and-branch (fails scarce-quantity gate); a bespoke base ISA (abandons Sail/CHERI/CompCert and the independent Spike/QEMU oracles); bespoke capability semantics (forfeits Cambridge monotonicity/provenance results, "turns representation proof into a fresh algebra proof").
"Zcmt table jumps: reject the JVT mechanism" — runtime address-derived memory read in the branch path; JVT CSR = architectural state + context-switch/flush rule; needs a new authority rule; moot because the image is position-fixed at composition.
"Self-timed datapath logic: rejected at the timing axiom" — completion time depends on operands (data-dependent latency the CT contract forbids); no fixed per-op latency for the §11 tables.
"Static-slot fine-grained multithreading" — the one partially admitted entry: fixed-slot barrel MT (CDC 6600/HEP/Tera/XMOS lineage) "passes the five-part admission test" and is logged as the first-choice gen-2 non-speculative throughput lever; dynamic-issue SMT and FlexPRET soft threads stay rejected (data-dependent contention). The entry explicitly says the SMT rejection "has been read too broadly."
"CHERI-Wasm as a hardware ISA" — rejected as ISA, sandbox target, and deployment format: no intra-module temporal safety/CFI; coarser than byte-granular CHERI; LEB128 stack machine forks the whole Sail/CHERI/compiler/Cerise/Islaris substrate; JIT = hidden translation state + W^X violation; Wasm threads = relaxed memory vs Ztso. Private embedded interpreters remain ordinary software.
"ELF as the on-device executable and package format: declined" — most ELF machinery serves excluded facilities (dynamic linking, PLT/GOT, W→X promotion); even a narrow profile leaves "an attacker-facing, offset-linked grammar" in the verified loader TCB; capability relocations want an authority-wiring relation, not legacy records. Juice slim binaries rejected (on-device codegen, compiler in TCB).
"High-level-language computer architectures (HLLCA)" (Lisp machines, B5000, iAPX 432 language axis, picoJava/Jazelle, graph-reduction machines, and "a machine that executes a proof language natively") — rejected: the safety atom "is already CHERI"; language-as-ISA is the substrate-cost disqualifier "verbatim"; semantic-gap closure "belongs to the verified compiler" (CHERI-TAL); hardware GC fails admission test 5 and §10; the 432's microcode-path checks were "ruinous in performance."
x86 ACE / Arm SME tile state ("not imported") — dedicated tile files/block-scale registers add large context and zeroization state, serialize low-precision ops, enlarge Sail/switch proofs; encodings not importable into RV64.
"Bespoke full-PQC and NTT instruction sets" (HORCRUX, PQCUARK) — declined: they target vectorless embedded cores; RVV already does straight-line, constant-time lattice arithmetic; new instructions would add Sail/Zvkt/refinement surface "without deleting a difficult proof."
"Mon CHÉRI conditional capabilities and an initialization tag plane" — rejected: opt-in, encoding change, stolen cursor bits, sequential-write assumption, store-linearization pass, non-monotonic permission regain; the init plane "would hedge a verified primary" (same disposition as PMP/IOMMU/MTE/shadow stacks).
"Programmable tag-policy engines: PUMP and software-defined metadata processing rejected" (SAFE, micro-policies, CoreGuard) — rule cache is hidden history-dependent state surviving a partition switch; miss latency depends on (secret) tags; runtime-loadable policy "inverts the frozen-with-the-proof discipline." SAFE's Coq metatheory kept as methodological evidence only.

OS-structure alternatives
"Language-based isolation as the sole mechanism, and in-place live evolution" (Singularity, Verve, Tock, Midori, Theseus) — rejected: one unsafe block/miscompilation/unverified binary gets unrestricted access (the case the hardware universal contract must bound); trusted runtime + GC excluded; Verve's Boogie/Z3 widens the trust base; Theseus-style live evolution mutates code outside measured boot and W^X.
"Oberon system mechanisms not imported" — six mechanisms declined: executable text (injection/confused-deputy classes), mark-and-sweep GC (pause behavior vs fixed WCET), load-time module linking/unloading (post-freeze executable mutation), Active Oberon AWAIT/condition monitors (data-dependent runtime scheduler), Juice (compiler in TCB), RISC5/Lola-2 (no RV64/CHERI/vector/atomics/mechanized-semantics substrate; "a small informal RTL is more proof work here than a larger existing formal model").
"Exokernel and unikernel structure: already converged" — no import: the design "sits between the two poles" (minimal capability multiplexer §7; secure bindings = capability/powerbox; single-purpose type-safe image = per-app compartment). Exokernel "leaves protection to the library OS; the platform proves it"; MirageOS is "OCaml on an unverified runtime with a GC."
"Decentralized-information-flow OS architectures: HiStar, Asbestos, Flume" — no import as an architecture: DIFC is already present as the §8/§13 flow-label/IFC machinery over a capability kernel + CHERI (byte-granular, exceeding HiStar's coarse containers); HiStar's minimal TCB is "a runtime reference monitor" where the platform's is "a proof"; DIFC owes the timing-channel story the profile discharges by construction; HiStar's Unix emulation is the POSIX ambient-authority surface the design deletes.
"HexFive MultiZone: already covered, strictly dominated" — every component maps onto a strictly stronger mechanism (PMP→CHERI+capability-DMA+islands; nanokernel→re-proved seL4-design kernel; messenger→verified rings; configurator→static composition + proof-checked admission). The inverse proposal (descend to M-mode + PMP-only, no CHERI) is rejected as the base: (1) granularity ceiling vs thousands of fine domains; (2) no intra-domain safety (Cerise Tier-2, W^X, per-element bounds lose hardware footing); (3) PMP-only "is not even sufficient" (DMA and timing still need capability-DMA/islands); (4) trap-and-emulate "reopens ambient authority." PMP also dropped even as a backstop ("verify rather than hedge").
"Historical capability-machine runtime machinery" (KeyKOS banks/meters/keepers, orthogonal persistence, single-level store) — declined: duplicates the static memory plan, cyclic schedule, and crash-only supervision; keepers reopen debugger/exception/continuation authority; whole-machine persistence conflicts with measured boot, eager zeroize, crash-only reinit, static composition ("storage would become a second origin of authority able to resurrect a capability after revocation").
"Object Memory Architecture" (iAPX 432, System/38→AS/400, MONADS, Rekursiv, Twizzler) — no import: the OID→location indirection "is the MMU this design deleted, generalized to per-object" (object TLB fails tests 2/3); CHERI is byte-granular/sub-object, OMA object-granular ("coarser"); the no-sweep temporal card is "a real trade, not a win" blunted by low allocation churn; single-level store/relocation/GC already declined or banned; object-as-ISA = substrate disqualifier. The "elegant synthesis" (identity ⋈ capability enforcement) is "already the design" via content-addressed objects + compose-time wiring.
"Enclave architectures: Sanctum, MI6, Keystone" (+ CHERI-TrEE, Tyche) — no import: enclaves "defend against the speculation and sharing this design already deleted"; Keystone's isolation is PMP; CHERI-TrEE's runtime create/grow/nest is "exactly the dynamic composition static build-time composition forbids"; Tyche is unverified, PMP-based, and exists to retrofit an untrusted commodity OS (foil). The attested compartment "is already the platform's compartment."

Device / peripheral / system alternatives
"External roaming hardware authenticators" (YubiKey/FIDO2) — declined: a "foreign computer" in the authentication path; CTAP over USB = attacker-facing wire + BadUSB impersonation; the function is already on-die and verified (RoT + crypto core + credential service = platform authenticator). Honest cost admitted: no cross-device credential portability.
"DIVA and general hardware lockstep/TMR" — DIVA rejected (checks what the core computed, not what it leaked); general lockstep/TMR deployment-deferred (ECC + CHERI fail-stop + multikernel containment cover the rest; G5-graded options only).
"Dedicated fixed-function GPU and uniform graphics on every core" — declined: a GPU is "a separately booted computer" (firmware, shader compiler, self-mastering DMA, data-dependent SIMT scheduler); uniform widening over-provisions scalar/control classes and assumes cross-class migration the static multikernel forbids.
"Vulkan and software GPU personalities" — declined: pipeline creation from shader IR = runtime codegen/W^X violation; command buffers = attacker-authored stream + validator; descriptor sets/queues/heaps/ICDs emulate a discrete device the machine lacks.
"OLED aging compensation and an unavailable micro-LED base" — declined: per-pixel correction state in panel electronics is "a foreign computer and a coarse integral of previously displayed content"; micro-LED supply at required sizes/yields doesn't exist.
"Adaptive-Sync and per-frame variable refresh" — declined: present callbacks leak timing influenced by surfaces the observer has no capability to inspect (cross-domain timing channel); honest cost is residual judder.
"Dedicated firmware-driven NPUs" — declined: "exactly the on-die foreign computer §4 excludes" (second core, firmware image, update path, DMA master); wrapping CHERI-unaware IP "would contain the same opaque engine rather than remove it."
"Physical bifurcation of the radio onto a second die" — declined: doesn't separate the mask-set threat (same die design reused); adds package/link/parser/CDC/two-die-attestation surface.
FullMAC radio controllers / Sora pure-software turnaround (in IN, "openwifi and the SoftMAC split") — FullMAC rejected as the §4-banned foreign firmware computer; Sora rejected as "spending the tightest real-time budget on the most jitter-sensitive path."

Memory-technology alternatives
"Memory encryption and the memory integrity tree: declined outright" — "memory cryptography protects an interface, and this machine has none" (no exposed DRAM bus; single die); every claimed benefit already discharged (volatility + zeroization, no bus interposer); the only residual adversary is invasive-physical, "out of scope by name"; the tree's node cache is history-indexed ("a data cache is address-indexed too"), failing admission test 3 and the flat-WCET claim. CHERI-Crypt capability-scoped encryption: lesson adopted, mechanism declined (transparent to the capability check; its only real customer is the out-of-scope physical adversary).
"SRAM chiplets and bonded die-stacking" — declined: each die is a mask set/fab lot/supply-chain entity needing correspondence evidence; die-to-die recreates the exposed hop.
"Dynamic/adaptive low-leakage SRAM techniques and active sub-threshold memory" — declined: feedback from data/activity to power/timing = correlation-power + data-dependent-latency surface; sub-threshold latency "reopens the gap the cacheless architecture relies on fast SRAM to close."
"Transparent variable-rate memory compression and runtime deduplication" — declined: data-dependent footprint/latency breaks composition-time capacity proofs and flat WCET; ratio oracle (CRIME/BREACH class); dedup creates authority edges from content coincidence; conflicts with fixed ECC/tag granule.
"Static code overlays" — deferred, not rejected: admissible security shape, substantial proof/TCB cost; re-open only when a measured composed roster fails the SRAM budget after all static levers; honest residual: the architecture "may reject an application whose resident image exceeds the fixed SRAM budget … an accepted capacity limit."
"Non-volatile main memory and unified SOT-MRAM storage" — the entry is truncated: the file ends inside the steelman (after citing IEDM 2024 and Nano Research 2026 endurance results). The rejection rationale for MRAM/FeRAM/ReRAM and the promised five-claim decomposition verdict are absent from the document.
"Delete the store buffer: sequential consistency by absence" — distinguished from rejected buffer-retained SC; not adopted, not rejected: clears gates 1/3/4/5, open on gate 2 (performance) pending the ρ ≥ 1 measurement; booked as a DSE question with an explicit falsifier ("sustained scalar store bursts … against a bank that cannot absorb them").
"Rejected profile simplifications" table — seven tempting deletions rejected as non-pure-wins: freeze vtype/fractional LMUL; SC with the store buffer retained; delete integer DIV/REM; delete vector masking; collapse three VLENs to one; delete indexed gather/scatter + segment load/store; any store-buffer bypass predictor/dynamic ordering optimization.

2. Rejections whose reasoning looks weak, circular, or premises-dependent
The single-prover (Coq-only) axiom underwrites a whole family of rejections — SecureBOOM/UPEC, GLIFT/SecVerilog, riscv-formal, EasyCrypt (Why3/SMT), HACL*/libcrux (F*/Z3), Verve (Boogie/Z3), VeriBetrFS/Perennial (Dafny/Z3, Go runtime), and above all the refusal to inherit seL4's Isabelle proof ("a first-order regression"). The premise — that two checkers in the TCB are strictly worse than one — is a value judgment, not a theorem; defense-in-depth via proof diversity is the standard counter-position, and IN's seL4/CertiKOS entry itself concedes "the two-checker alternative's edge is narrower than it looks" and that the inherited proofs don't cover this configuration anyway (so the maturity argument does little work). Every "foreign prover" rejection inherits this unproven premise.
"Verify rather than hedge" rests on a proof that does not yet exist. PMP-backstop, IOMMU, MTE, shadow-stack, and init-plane rejections are all justified by "CHERI is the mechanism the design verifies most deeply" — while the same documents repeatedly call RTL ⊑ Sail "the least-built arrow" (§17/§18) and record "no full application-class core had yet been proven to refine its ISA model." The disjoint-failure-domain hedge is thus dropped on the strength of a future artifact. Both documents book this as an "honest residual," but the rejection logic is hostage to it.
The NS-OoO rejection's "decisive, design-specific point" is hostage to the SRAM bet. "The latency wall it exists to hide is deleted" presumes flat, low-latency, multi-GB on-die SRAM — which IN's own Cerebras/all-SRAM entry admits rests on sequential-3D tier count, "the least mature lever in the design," with an "honest two-case reading" whose failure branch is "a single planar tier near 2 GB." If the memory bet degrades, the "dominant thing NS-OoO buys is absent" argument weakens accordingly.
The five-part admission test is self-referential. A large fraction of rejections (ALAT, RSE, PUMP, dynamic SMT, backless memory, node caches, self-timed logic, Svadu walkers) are decided by "fails admission test N" — but the test is the design's own §15 construct, written to encode the profile's prior commitments. Rejections via the test are only as strong as the test, which is never independently justified against alternatives (e.g., a flush-on-switch discipline — the document's own aside admits flushing would be needed "whether or not the secret leak is fenced" for OoO, i.e., the test presumes the deletionist posture).
The substrate-cost disqualifier leans on a partly aspirational ecosystem. EPIC, OISC/TTA, Wasm, HLLCA, and bespoke-ISAs are rejected because they forfeit "RISC-V Sail model, CHERI-CompCert backend, Islaris, Cerise, RVV" — yet the same documents admit the CHERI-CompCert backend is "priority-zero" (unbuilt), SECOMP2CHERI is "workshop-stage … not a finished secure-compilation proof," the CHERI-TAL soundness metatheorem "must be authored once in Coq," and the FPCC certificates a new ISA would "re-mint" do not yet exist to be minted. The asymmetry ("the ecosystem exists" vs "theirs doesn't") is real but smaller than stated.
The memory-encryption rejection rests on a scope line the document itself calls load-bearing. "Invasive physical attack, out of scope by name" does the work; the entry's own honest residual says "if that line is ever judged wrong, nothing sits behind it: there is no encryption to slow an attacker down and no freshness check to catch a replay." The "an attacker at that level would equally reach the keys" argument is asserted, not analyzed (separate-key-holder constructions exist precisely to complicate that).
"No foreign computers" has a judgment-call boundary. The rule rejects GPUs, NPUs, FullMAC radios, YubiKeys, and CapChecker-wrapped accelerators, while the fixed-function radio turnaround sequencer, FEC blocks, and USB-PD sequencer are admitted as "matter, not software." The line between "a timer plus a small FSM with no instruction fetch" (admitted) and a minimal MCU (foreign computer) is a continuum the documents draw by fiat; the eUICC is admitted as a named exception ("the zero-authority eUICC"), conceding the rule has exceptions.
The RISC5 rejection criterion is outcome-loaded. "The instruction set of record is chosen by whose semantics is already mechanized, not by whose instruction count is smaller" — i.e., RISC-V is chosen because RISC-V is already formalized. That is a path-dependency argument, not a complexity argument; it proves the incumbent wins any incumbent-favoring criterion.
Enclave rejection is premised on the profile's buildability. "The threats it fights are deleted, not defended" presumes an application-class, in-order, non-speculative, cacheless CHERI core exists — while AA's NS-OoO entry concedes there is "no off-the-shelf non-speculative application-class RISC-V core to start from," and IN books the all-SRAM capacity and single-privilege-mode-at-scale items as genuine extrapolations.
The OMA "low allocation churn blunts the sweep" argument assumes its conclusion. Static composition minimizing churn is asserted for a workload (a general consumer device with a browser) whose allocation behavior is not yet measured; the same document defers code overlays precisely because no measured roster exists — measurement is demanded there but waived here.
VLIW disqualifier count (2) is internal by construction. Rejecting VLIW because a bundle schedule violates §15's "one base ISA, one kernel binary, one parameterized model" property rejects a candidate for failing a rule the design wrote for itself; logically fine, but it means the property is doing unexamined work (the property was itself chosen to exclude exactly such couplings).

3. Places where the documents admit a simpler design would suffice for a subset of users/goals
The MultiZone/PMP-only entry is the bluntest admission (AA, "HexFive MultiZone"): PMP-only's appeal "is real and almost entirely about realization" — commodity cores, no CHERI silicon, mature plain-C CompCert — and it is "rejected as the base on the goal function, not the effort function"; "taking PMP-only as the goal would trade the platform's defining property … for buildability the spec deliberately declines to optimize." I.e., for users whose goal is less than maximal assurance, the simpler design suffices, and the documents say so.
KataOS as foil (IN, seL4 entry): KataOS "stops an assurance tier short on every axis it shares" — implicitly sufficient for users one assurance tier down, and it actually shipped.
GrapheneOS/secureblue as terminus of the mitigation road (IN): "GrapheneOS hardens the phone Android is; this design builds the phone that needs no hardening" — concedes the hardening lineage is what suffices on commodity hardware.
Static code overlays (AA): "the current architecture may reject an application whose resident image exceeds the fixed SRAM budget … that is an accepted capacity limit, not an implementation omission" — the design knowingly excludes a workload class; smaller rosters suffice.
All-SRAM capacity ceiling (IN, Cerebras/all-SRAM entry): "tens of gigabytes … not the hundreds of gigabytes to terabytes a DRAM design reaches: the density price stated plainly" — memory-hungry users unserved; DRAM design suffices for them.
Deployment grading (IN, DICE/radiation entry; AA, DIVA/lockstep): radiation hardening is "graded to the deployment" (consumer form factors get commercial-grade or none); lockstep/TMR are "graded G5 options" only where a safety case pays — simpler realizations are explicitly sufficient for less demanding deployments.
Barrel MT, NaR, wider superscalar (AA): all three ILP levers are deferred to gen-2 "should the in-order IPC tax bind" — i.e., if performance never binds, the simpler base suffices; if it does, the base was over-simplified.
Honest-cost admissions: Adaptive-Sync ("residual judder for unknown or varying non-divisor content rates"); no-GPU/no-Vulkan ("lower peak throughput of a no-JIT software renderer," "a native backend per toolkit"); no roaming keys (no credential portability); 5G/6G-only silicon (no legacy RAT coverage); no micro-LED mandate (procurement doesn't exist).
Scalar scratchpads (IN, cacheless entry): admitted only "where a class's access is predictable and high-reuse enough" — scalar cores default to none, accepting pointer-chasing performance loss ("the accepted price").

4. Contradictions / tensions with the main spec (spot-checked)
Register files and the fence.t flush set. IN's RVV/Zfinx entry calls the scalar f-register file "context-switch state and a fence.t flush-set member," while the spec states the flush set is "the store buffer alone" (verification-maximal-os.md, R-15-213 area, line 2071–2075) and that register-file membership in the flush set is declined under verify rather than hedge (R-07-016, line 556). The RVV entry's wording is stale or loose relative to the normative text. (AA's store-buffer entry is consistent with the spec: store buffer is "the sole member.")
The Oberon quiescent-point proposal vs §8's preemptible sweep. IN (Project Oberon entry) proposes binding revocation-sweep quanta to slot boundaries and explicitly notes it is "proposed here and not yet taken, since §8 currently specifies the preemptible form." The spec confirms the preemptible form (R-08-007, line 638: "incremental, preemptible kernel task"). So IN currently argues the normative spec carries a deletable proof obligation — a documented, unresolved tension, not an oversight.
Store buffer / memory model. AA's "Delete the store buffer" entry leaves Ztso + retained store buffer normative but books SC-by-absence as an open DSE question clearing 4 of 5 gates; the spec retains Ztso (R-15-004, R-15-088, line 1583). Consistent today, but AA enumerates a future spec-body change list — an acknowledged pending conflict.
R-08-004 wording. IN quotes R-08-004 as "first-class revocation (derivation-tree revoke + CHERI sweep)" and argues the CDT half is a duplicate. The spec's current R-08-004 (line 627) reads "the mechanism is the CHERI one alone," and line 628 adds "There is no capability derivation tree." So the spec has already absorbed the deletion IN argues for — meaning IN's quoted clause is stale (it quotes a prior revision against the current spec). A citation-drift contradiction between the two non-normative docs and the spec's current text.
No contradictions found (on the checked points) for: MCS deletion vs cyclic executive (spec lines 581–584 match IN), object-model deletions (spec lines 171, 514–522, 574, 579, 628 match IN's CHERIoT-shaped-object-model entry), asynchronous-interrupt deletion and sentry collapse (spec lines 548, 590–593, 602, 708–710, 1302, 1542 match IN's PRET entry), Zcmt rejection (spec R-15-036q exists and matches AA's disposition), macro-op fusion admitted (spec line 1446 matches AA's framing).
Truncation gaps: AA's MRAM entry has no disposition in-file (ends mid-steelman), and IN ends mid-list in the object-model entry — any downstream cross-references to those dispositions would currently dangle.

5. Lineage / inspiration, grouped by what was taken
Kernel & proof method
seL4 — the kernel design base: endpoints + notifications, first-class revocation (as a statement), non-interference theorem statement, zero post-boot kernel allocation; the 2024 multikernel (RFC-0170) and CHERI-seL4 engineering as live lineage; not the Isabelle proof, VSpace, MCS, untyped/retype, CSpace, CDT.
CertiKOS — proof method only: deep specifications, abstraction layers, CompCertX; VST as the sequential closing logic; not CCAL concurrency machinery ("dead weight" under share-nothing).
KataOS/CantripOS/Sparrow (Google) — convergent evidence the substrate is buildable; capDL capability-distribution spec as precedent; foil (containment-without-proof).
Barrelfish — the multikernel model itself (share-nothing cores, message passing); not the dynamic System Knowledge Base.
SemperOS (M³) — shape of distributed cross-core capability revocation; scaling evidence (70–78% at 576 cores); not code or proof (unverified, non-CHERI).
Akaros — evidence (from the performance pole) that spatial core partitioning + async shared-memory syscalls crush OS jitter; provisioning-vs-allocation mooted by static composition.
Compilation, languages, type systems
SECOMP / CompCert — secure-compilation method (robust preservation), SECOMP2CHERI as the CHERI backend start.
Vélus — Coq-verified Lustre for the control tier: structural WCET, no hidden state between activations, compiler-checked causality.
Necula PCC → Morrisett TAL → Appel/Crary foundational — the CHERI-TAL type-soundness half; decidable on-device checking; CT-Wasm (constant-time as taint types); StkTokens (linear/affine capability discipline); definite initialization as a type attribute; RustBelt/WasmCert as mechanized descendants.
Singularity/Verve/Midori/Theseus — language-safety discipline carried to the artifact; Midori's typed-error/fail-fast model; Theseus's state-spill analysis; not runtimes, GCs, Boogie/Z3, or live evolution.
Register-allocation/region/ML-compiler line (Chaitin coloring; Tofte–Talpin regions; Walker–Crary–Morrisett calculus of capabilities; XLA/TVM/TFLite-Micro static planning; Lobster/ASAP/Perceus/Mercury compile-time lifetime analysis; Robson's fragmentation bound; Gergov/Buchsbaum approximations) — the static memory plan replacing the runtime heap, checked as a TAL side condition.
Oberon (Wirth/Gutknecht) — whole-stack parsimony as method; the quiescent point (proposed for the sweep); the module key as load-time refusal; Oberon-07 as the deletion-gate precedent; Active Cells and Oberon-V as multikernel/vector convergences.
Crypto
Fiat-Crypto — Coq-native correct-by-construction field arithmetic.
HACL*/libcrux — interim verified primitives (F*/Z3 trust base, deliberately minimized).
SSProve/FCF — destination Coq-native game-based reductions (IND-CCA/EUF-CMA).
EasyCrypt/formosa-crypto — finished ML-KEM/ML-DSA reductions as pragmatic interim (SMT base acknowledged).
Capability hardware & CHERI ecosystem
CHERI programme (Cambridge/SRI, MSR, INRIA) — the substrate itself; Morello reachable-capability monotonicity (Bauereiss et al., ESOP 2022) as the machine-checked security property.
CheriOS — the single-address-space purecap thesis (existence proof for deleting the MMU); revocation/reservations discipline; not its retained MMU, nanokernel de-privileging (taken only scoped to crown jewels), or per-enclave foundations.
CHERIoT — privilege-as-PCC-permission (M-mode only), switcher + sentries, export/import table structure, the CNode-free object model, heap claims, deterministic load filter, the PMP-drop argument; not its encoding, unverified loader, or TBRE/STKZ autonomous sweep engines.
Markettos et al. (HASP 2020) + CHERI Alliance SoC guide — capability-checked DMA replacing the IOMMU; tag/revocation propagation discipline; CapChecker kept only as a feasibility datapoint.
CVA6-CHERI / COSMIC — the C-class scalar front end; ISA-conformance proof method (as bounded bring-up evidence); OpenTitan integration template; dual-core lockstep imported for the S-class sentinel only.
Codasip X730/A730 — commercial shipping evidence, licensable silicon path, CodAL curation flow; the A730 PMP-removal quote as precedent; not a trusted base.
CHERI-TrEE / Cerisier (PLDI 2026) — attestation-reasoning prior art over the Cerise contract; enclave primitives declined.
Tyche — convergent validation of capability-model/enforcement split and monotonic revocation; foil (unverified retrofit).

Systems & product patterns
systemd — declarative supervision shape; ambient authority stripped.
Fedora Atomic / OSTree — immutable base, content-addressed Merkle store, A/B + rollback discipline; not bootc/OCI packaging.
NixOS/Guix — purely functional build, config-as-derivation, generations, Guix's full-source bootstrap; input-addressing kept off-device only.
secureblue — the hardening ethos (→ G1/G2), carried from mitigation to proof.
GrapheneOS — the seized-device threat model: auto-reboot-to-BFU, USB data gated on lock state, duress credential crypto-erase, hardware-invariant MAC randomization, legacy-RAT absence taken to silicon.
ChromeOS + OpenTitan — verified-boot RoT product template, realized on-die; discrete TPM and TPM-2.0 command mode declined.
Fuchsia/FIDL — capability-IPC shipping evidence; the wire discipline (out-of-band handles, mandatory schema bounds, hardened decoders); WIT supplies the type layer (worlds/resources).
Plan 9 — private namespaces, Factotum key custody, Plumber intent routing, re-grounded; no 9P.
BeOS — typed attributes/live queries, translator graph, media graph, made transactional and static.
oo7/Secret Service — client vocabulary shape and the ambient-authority case study; no protocol or backends.
KeyKOS→EROS→CapROS — the typed-data-persistence payoff (no app-authored serializers); process/capability-graph persistence left behind, on the lineage's own concessions.
Cerebras — extreme-scale evidence for share-nothing all-SRAM; static mesh routing corroborates the TDM NoC; backpressure/sparsity/dataflow declined.
openwifi / mac80211 / Nordic nRF + Zephyr — the SoftMAC split and the radio start-from RTL.
PIC64-HPSC / Intel Starfire / RAD750 line — space-grade realization precedent (harden the process, not the architecture), deployment-graded.
PRET / time-triggered lineage — pollable events, the slot-boundary timer as sole asynchronous trap.
Wistoff et al. fence.t on CVA6 — the temporal-fence primitive (per the spec).
RVV/Zfinx — scalar FP folded onto the vector FPU; static rounding.
6. Redundant components or needless complexity in the chosen design — as admitted or implied by the documents
The kernel carried a duplicate revocation mechanism (IN, CHERIoT-shaped object model): R-08-004's "derivation-tree revoke + CHERI sweep" is called out in the document's own words — "the design has applied that rule [verify rather than hedge] against the initialization-tag plane, MTE, shadow stacks, PMP, and the IOMMU while leaving its own kernel carrying a duplicate." The fix (deleting CDT/CSpace/untyped+retype) is argued there and now reflected in the spec — an admitted, since-removed redundancy.
The store buffer is "the last piece of microarchitectural state … that never received R-15-105" (AA, store-buffer entry) — i.e., the design retains one structure that meets 4 of 5 deletion gates, kept only pending a measurement. By the design's own logic it is a candidate-for-deletion complexity currently carried.
The preemptible sweep carries a known-deletable proof obligation (IN, Oberon entry): rebinding sweep quanta to slot boundaries "buys not a mechanism but a deleted proof obligation … proposed here and not yet taken."
Temporal safety is triple-covered: the static memory plan (placement), CHERI-TAL linear/affine types (compile-time), and the load filter + budgeted sweep + quarantine (runtime) all address use-after-free. AA's OMA entry concedes the overlap ("the property … is already the design's, discharged by [all three]"; types leave revocation "only the runtime backstop for the residual"). The documents frame this as composition, but it is the largest standing stack of overlapping mechanisms for one property.
Two interface stacks: the §12 layer is "a deliberate hybrid" — WIT-derived type layer ⋈ FIDL/Zircon wire layer — plus flow labels "added as a first-class §12 concern." Deliberate, but two interface formalisms plus a label layer is real surface.
Contested complexity the documents refuse to delete (AA, rejected-simplifications table): fractional LMUL, three VLENs, vector masking, indexed gather/scatter + segment ops, hardware DIV/REM — each is retained only on performance arguments ("fails gate 2"), i.e., the documents admit these are surface-without-proof-benefit whose cost is measured in cycles, keeping them is a judgment call the table itself records as debatable ("enumerating configurations after measuring kernels may still be useful profile hygiene").
The scalar-FP fold buys a proof shrink with a non-standard ISA fork (IN, RVV entry): deleting F/D is "a fork of the base ISA" with a soft-float-register ABI and per-op vsetvli overhead — a self-inflicted ecosystem divergence whose net ("a net shrink") is modest and booked honestly.
Exceptions to the design's own parsimony rules: macro-op fusion is admitted "precisely because it is architecturally transparent" while other transparent-but-useless extensions are cut; the sentinel gets the design's only lockstepped core ("a detector cannot report its own corruption"); the eUICC is the sole admitted foreign computer. Each is justified in place, but each is an asymmetry a critic can point to.
Aesthetic reasoning appears as a decision input: EDGE preferred over the belt because block-atomic commit "rhymes with the rest of the architecture"; EPIC "rhymes with nothing." "Rhyming" is not an admission-test criterion, and its appearance in dispositions is a small but real methodological softness.
Deferred machinery still looms: static code overlays (loader + bank-lifecycle proofs) and generation-tag temporal safety are both preserved as options — each would re-introduce a mechanism family the design elsewhere deleted (a managed instruction store; a second metadata plane), so the "complexity deleted" ledger is partly contingent on capacity bets holding.
Caveats on the source material
Both files are drafts that end mid-entry (AA: SOT-MRAM disposition missing; IN: object-model "net simplification" list cut off at item (2)).
The documents are internally disciplined about booking "honest residuals" (§17) — most of the weaknesses in §2 above are acknowledged somewhere in the text; the critique is that the rejections nonetheless treat those premises as settled when citing them against alternatives.

---

Register issues:

Contradictions, overlaps, redundancies
Genuine disagreements / tensions:

R-05-094 vs R-13-012 — the strongest finding. R-05-094 says the Tier-2 certificate has four conjuncts (temporal safety, CFI, no-runtime-codegen, ABI/type conformance); R-13-012 says it carries six of the eleven (adding definite initialization and data-race freedom). R-13-012's own accept text claims the content is "read off R-05-029 ... rather than enumerated independently" while itself enumerating a different set than R-05-094 — a self-sourcing rule violated in the same entry, and exactly the class sweep 3 claims closed.
R-08-031 vs R-16-015 — R-08-031 states absolutely that "no compartment reads an architectural cycle, time, retirement, or performance counter"; R-16-015 lists "raw counter reads by holders of the fine-grained-time permission" as one of four replay-nondeterminism sources. Reconcilable only if the time-service's own reads are meant, but the absolute phrasing in R-08-031 contradicts the permission-holder population R-16-015 quantifies over.
R-08-040 vs R-12-052 — R-08-040 states unconditionally that every while-active grant carries a maximum-duration ceiling enforced through kernel expiry; R-12-052 declares the emergency-call microphone grant "deliberately exempt from the while-active ceiling ... and the only one." R-08-040 never mentions the exception.
R-16-012 vs R-16-021 — "No verbose logging mode exists" (MUST NOT, unqualified headline) vs a mandated capability-scoped verbose diagnostic sink gated on lifecycle state (MUST). The reconciliation (unlabeled/ambient vs labeled/lifecycle-gated) exists only in the accept text of R-16-012, not its statement.
R-05-022 vs R-05-109 / R-05-073 — R-05-022 counts aiT and Binsec/Rel among the five "interim non-Coq anchors" carrying retirement rules; R-05-109 and R-05-073 describe both as untrusted out-of-band evidence that enters no trust base. An artifact outside the trust base is not an anchor and needs no retirement, so the five-entry list has a category error.
R-15-177 vs R-15-189k — scrubbing "mandated ... on every array" vs "background scrubbing runs on ON domains only." R-15-189k contains the reconciliation; R-15-177's "every array" is unqualified.
R-17-058 vs R-15-184 — §17 says "Rowhammer is dramatically reduced rather than mitigated"; §15 says the charge-disturbance primitive "has no analog in SRAM" and the apparatus is "deleted, not tuned." Reconcilable via R-15-184's own accept (SRAM disturb modes as residual), but the two headlines disagree in strength.

Redundant restatements (aligned but stated 2–3×):

No-async-interrupt-delivery: R-07-038, R-08-033, R-15-065/R-15-070, R-12-064.
No MMU / single address space: R-04-003, R-07-052, R-15-002.
Biometrics never release BFU keys: R-09-020, R-12-019 (cross-cited).
Sealed cutoffs dominate, mute emergency call: R-12-054, R-15-148 (near-verbatim).
Lockout cuts mic/camera/USB, radio stays pageable: R-09-021, R-15-147.
Global mode transitions rare/RoT-attested/never load-following: R-11-018, R-15-189.
No link-time specialization on confidential values: R-15-036g, R-13-010d (acknowledged as a scope citation).
No POSIX/Linux shim: R-02-001, R-14-012; no dynamic speculation: R-02-004/R-02-005 vs R-15-019.
Self-documented repaired collisions: R-05-028 vs R-06-011 (competing axiom enumerations, repaired by scoping R-05-028); R-17-016 (crown-jewel roll-call drift, repaired by conferral + R-17-016a); R-05-029 (obligation list multiply stated, repaired by citation). These are presented as fixed, and the fix pattern is consistent.


3. §17 residuals — every entry
17.1 Index (3):

R-17-001 — §17 grouping rule: every residual in exactly one of six trust-source groups; IS.
R-17-001a — Top-down coverage claim: every boundary×property pair must carry a requirement or a residual; a pair with neither is a spec defect; tool-decided.
R-17-001b — coverage-matrix.md must exist as the derived view holding both enumerations and one row per pair; tool-checked both directions.
17.2 Timing/scheduling (9):

R-17-002 — Six timing-channel classes deleted by named constructions; the rest narrowed, no general timing guarantee.
R-17-003 — NI⋈timing seam residual is the composition proof itself plus sub-partition-granularity channels.
R-17-003a — Open: fault class of a non-CT compartment can depend on its own data and leaks (coarsely, schema-bounded) into exported crash records; bounded by record shape, not proof.
R-17-003b — Shared-macro island contention: unauthored NoC/island isolation model means neither disjoint nor shared bindings currently read "proved."
R-17-004 — Population wall: non-work-conserving frame divides capacity among live compartments; unrecoverable.
R-17-005 — Background share ~1% of a core at the 32-rung, ~4% at the 8-rung; the degradation floor.
R-17-006 — Idle discretionary time is structurally unreclaimable (reclaim = the deleted channel).
R-17-007 — Rung index leaks a log-coarse live-compartment count and focus-change timing; a real but coarse channel.
R-17-008 — Product-level honest statement: a few-active-things machine.

17.3 Consent (9):

R-17-009 — NI is absolute for fixed flows but only modulo declassification for user-authorized ones; the ceiling.
R-17-010 — Consent TCB genuinely grows (powerbox + trusted-path agent + indicator), partly shifted onto the RoT.
R-17-011 — While-active grants remain strictly weaker than one-shot: bounded, legible exposure.
R-17-012 — Delimited-release bound and robust-declassification are new crown jewels; a too-wide bound "verifies perfectly and leaks."
R-17-013 — The user is outside the theorem: consenting to the wrong thing is irreducible.
R-17-013a — Agent residual intro: two costs remain beyond §12's confinement.
R-17-013b — Prompt injection is not answerable at this layer; only request containment/legibility is claimed.
R-17-013c — Consent fatigue at machine rate: standing grants widen/weaken the bound.
R-17-013d — No theorem over model behavior; claim is bounded authority, not sound judgment.
17.4 Proof-gap (5):

R-17-014 — Fresh NI proof with three dimensions seL4-NI never reached; silent-failure mode is a too-weak-but-faithful NI spec.
R-17-015 — Replay is bit-exact modulo the secret-entropy cone; draw-dependent faults don't reproduce from exports; soundness rides CT, not replay.
R-17-016 — Spec-vs-intent gap: proofs match specs, never intent; crown-jewel status is conferred per-requirement, collected in R-17-016a's inventory.
R-17-016a — crown-jewels.md must exist as derived view, one row per jewel with authored/partial/not-authored status; tool-checked.
R-17-016b — Parser agreement gap: no single-party proof can exclude a differential with an independent implementation; oracles are evidence, never trust base.

17.5 Hardware seam register (14):

R-17-017 — The seam register itself: admission review walks this list before the five-part test.
R-17-018 — Interrupts⋈cyclic executive: dissolved by design; residual is slot-granular bark notice.
R-17-019 — fence.t⋈state inventory: four-class map discharged against RTL; store buffer alone flushed.
R-17-020 — Memory path⋈power gating: dissolved (no key/counter/root in the path).
R-17-021 — Scanout⋈TDM: standing reservation; underrun is a fault class.
R-17-022 — Memory tiers⋈inspectability: logic tier imaged, passive tiers can't execute.
R-17-023 — Revocation⋈schedule: epoch flip = containment; sweep = sized background slot.
R-17-024 — Write path⋈ECC/tag planes: whole-codeword writes; verify-before-merge at the one re-encode point.
R-17-025 — Clock domains⋈determinism: mesochronous; three asynchronous boundaries terminated, unmodeled.
R-17-026 — Boot⋈storage: ROM/OTP/fixed-address NAND, no grammar.
R-17-027 — Calibration⋈attestation: factory-measured, signed, envelope-bounded.
R-17-028 — Inspectability⋈density: IRIS scoped to logic die; memory stack checked at runtime.
R-17-029 — Debug⋈lifecycle: electrically fused in production, an RTL⊑Sail obligation.
R-17-030 — eUICC⋈platform: host-clocked register-slave block behind a verified parser.
17.6 Fail-closed seam register (18):

R-17-030a — The register's own rule: every stop/refuse/erase/cut mechanism must appear below; composition owed here.
R-17-030b — Thermal trip halts everything; reachable by attacker or hot enclosure alike.
R-17-030c — Watchdog bite = reset; bounded by boot counting into downtime.
R-17-030d — Containment leaves the attacked surface degraded until proof-gated remediation; per-incident budget can't express repeated forcing.
R-17-030e — Admission refusal costs delivery, never a fielded unit (also covers R-15-189g power-vector rejection).
R-17-030f — Sealed cutoffs override emergency calling; deliberately unoverridden.
R-17-030g — No legacy emergency coverage: outside 5G-SA/6G the device places no emergency call; sharpest member.
R-17-030h — Duress erase is irreversible on accidental entry; protects future recoverability only.
R-17-030i — Compromised compositor/driver can deny the consent prompt, never forge it.
R-17-030j — Radio-stack crash = connectivity loss until restart.
R-17-030k — The background floor: not a response, but the baseline all degradation reads against.
R-17-030l — Composition statement: three individually-correct refusals jointly form one life-safety case; no mechanism proposed.
R-17-030m — Degraded-subset rate must be budgeted as an attested countable event class, not per-window.
R-17-030n — Detector trip (ECC/tag/signature/lockstep/discharge) stops the machine; provocable by proximity EMI without software access.
R-17-030o — Entropy health-test failure stops all fresh-randomness operations; the one member whose weakening would cost confidentiality.
R-17-030p — Display underrun blanks the consent surface; prompt denial without any compromise.
R-17-030q — Budget admission refusal: ordinary growth, not adversary, still refuses.
R-17-030r — Conferral mechanism for the register; 18 conferrals / 14 seams, tool-recomputed; completeness explicitly not closed.
17.7 Admission/tooling seams (20):

R-17-031 — Robust-preservation compiler theorem is a heavier obligation than plain correctness.
R-17-032 — Tier-2 floor: narrows the admitted set; containment unchanged.
R-17-033 — Certifier preservation theorem is off the trust path (completeness, not soundness); ships tested-but-unproven; a delivery risk.
R-17-034 — Typed callee set is the sharpest completeness residual: refusal, never under-declaration.
R-17-035 — Remediation window: fast unproven containment, slow proven fix; degraded running between.
R-17-036 — Verbose diagnostics confined by lifecycle gate + label, not eliminated.
R-17-037 — CHERI single-mechanism concentration in four parts; only hedge is CHERI's own verification.
R-17-038 — Checker stratification seam: six residuals (new TAL crown jewel, temporal discipline, relevance bounds drop-not-response, no-ambient-state vs over-injection, frozen theory's one-directional expressiveness spend, totalized arithmetic decidable only on closed bounds).
R-17-039 — Sail⋈RTL is the least-built layer; no artifact at full-application-core scale.
R-17-040 — Absence contract: Kôika blocks close in-prover; imported cores close on audit, not theorem.
R-17-041 — WCET seam: latency magnitudes are a crown jewel; WCET inherits RTL⊑Sail; composability shares the NI proof.
R-17-042 — CT seam: typed-where-possible/proved-elsewhere split, no compiler CT preservation, bounded Binsec/Rel evidence, RTL⊑Sail inheritance.
R-17-043 — Verified-storage seam: six residuals (freshness, L0 re-proof, AE⋈NI, liveness⋈schedulability, dedup digest interface, surrendered user-data freshness).
R-17-043a — Durable state is the one defect class that can outlive reboot; costs rollback window + standing migration obligation.
R-17-044 — Lustre/Vélus seam: two residuals (program + boundary as crown jewels), net tooling shrink.
R-17-045 — Definite-init by type system alone: hedge surrendered; device and delegated-buffer paths exit the derivation.
R-17-045a — Object-model deletion spends seL4's independent scrutiny; replacements have thinner published assurance.
R-17-046 — Proof trust base = R-06-011 axioms + R-05-022 interims; disposition is "explicitly shrinking."
R-17-047 — Lean refused (two-kernel cost); answer stays Coq-native.
R-17-048 — Heterogeneous die grows Sail surface; exclusions shrink it; net is modeling work, not trust.
17.8 Crypto/regulatory/physical (25):

R-17-048a — Retiring the RVY re-pin spends differential oracles (Spike/QEMU/CHERI suites), not a badge; algebra results inherited.
R-17-049 — Hardness assumptions (MLWE/MSIS, ECDLP/CDH) irreducible; impl⋈reduction seam at the functional spec; protocol-level security unreached.
R-17-049a — Entropy subversion: a fab-trimmed source passing exactly the tests it's given is undetectable; inherits the fab ceiling.
R-17-050 — Regulatory residual narrowed to commercial: carrier/PTCRB/GCF acceptance of an open UE stack.
R-17-051 — 5G/6G-only floor narrows deployability including emergency calling.
R-17-052 — Emergency mode admits an unauthenticated, possibly null-ciphered session; contained by NI + zero authority.
R-17-053 — Wired ceiling: no ≥10GBASE-T; frozen 1000BASE-T coefficients cost link-bounce retraining.
R-17-054 — Lock-state limits: credential-bound at-rest security, shortened-not-closed unlocked window, irreversible duress.
R-17-055 — Randomized MAC is a privacy floor, not unlinkability (RF fingerprinting, sequence numbers, timing re-link).
R-17-056 — USB auth floor attests identity not behavior; most peripherals fail it → consented exceptions weaken the floor.
R-17-057 — Trusted-time residual is availability not integrity; PTP's path-symmetry assumption unprotected.
R-17-058 — Physical: Rowhammer reduced-not-mitigated (sic, vs §15's "deleted"), cold boot via volatility, TEMPEST attenuated-not-closed, macro/3D thermal coupling narrowed.
R-17-058a — No masking/DPA resistance in the crypto core, unaddressed by construction; the four-part reversal (masked datapath, probing-model jewel, composition theorems, per-op randomness) named.
R-17-058b — Fault-injection detectors buy coverage, never a theorem; four limits named (signature collision, epilogue fault, S-class-only lockstep, unclaimed transient datapath strike).
R-17-059 — Memory path defended by absence-of-surface; the scope line is load-bearing with nothing behind it.
R-17-060 — Silicon supply chain is the largest residual; single die concentrates it.
R-17-060a — Design-to-mask half discharged by reproducible deterministic flow + digest comparison.
R-17-060b — Reproducibility fixes the artifact, not semantics: LEC/LVS verdicts are trusted, at evidence tier.
R-17-060c — Reproduction ≠ identity below the handoff (OPC, fab corrections); bit-identity claims are findings.
R-17-060d — Mask-set digest signed at handoff and named in attested identity.
R-17-061 — IRIS evidences only the logic tier: "everything that acts is imaged; what is not imaged cannot act."
R-17-061a — Layer-transfer donor wafers add a materials-provenance residual (blanket, unpatterned, so no design subversion).
R-17-062 — Factory calibration manifests: the one per-device trusted measurement.
R-17-063 — IRIS resolution ceiling: sub-resolution fab adversary remains in scope.
R-17-063a — The residual shrinks to one arrow (die-vs-mask), evidence-tier only.
17.9 Composition (2):

R-17-064 — The composition meta-lemma: largest deliverable, exists for no system of this scope.
R-17-065 — T's boundary: D, Ax, hardness, die-vs-RTL, spec faithfulness, human consent, invasive physical.

4. Open extraction defect D-CSR
What it is: the surviving CSR bank was never decided register by register — §15 enumerates deleted CSRs by name but states the residue nowhere, while R-07-015 and R-15-214 both quantify over "every CSR a partition can name" (the total-restore obligation) without the underlying list existing. Rows: 7 — (1) mcause/mtval (capability-exception cause encoding unspecified); (2) mie/mip (timer bits have consumers, external/software bits don't); (3) menvcfg (R-15-049's anti-Smstateen argument applies verbatim but was never stated for it; the CBZE bit); (4) mvendorid/marchid/mimpid/mconfigptr (no discovery consumer); (5) mhartid (R-07-012's one-binary-across-classes needs it, no requirement says so); (6) tselect/tdata1–3 (trigger module unnamed — the only row with a security consequence: M-mode mutable state surviving partition switches, the admission-test-3 shape); (7) DDC (purecap-only leaves it consumerless but nothing retires it). Why unresolved: the register's discipline books defects for repair in verification-maximal-os.md rather than fixing them in the register; R-15-001b closed only the artifact half (isa-profile.md §5 now holds the enumeration with these rows marked open), and no requirement yet decides membership. It's also the register's exhibit for its own "standing instruction": three enumeration-closing sweeps ran, and the standing assumption that a fourth list existed is what found this one.

5. Untestable / circular / self-referential acceptance criteria
Approximate counts by section (judgment-based, of criteria that are documentation-presence checks, "consistent with" citations, tautologies, or existence-of-a-booking checks rather than decision procedures):

§	≈ weak	Examples
1	5	R-01-001 (accept = R-04-001 restated, mutual citation), R-01-004/005 ("discharged by §16"), R-01-006 ("cites this goal ordering")
2	2	R-02-002 ("collapses toward" — directional, unmeasurable)
3	4	R-03-003 ("consistent with R-15-153 through R-15-157"), R-03-008 (admits "discharged by inspection until then")
4	3	R-04-012 (consequences "discharged by a named mechanism")
5	~20	R-05-165 (purely a remark on vacuity, no criterion), R-05-151 ("Accept: this document"), R-05-106/116/134
6	~8	R-06-002/005 ("order of 10k", "10× smaller" budgets), R-06-018/020 (named-in-§6 bookings)
7	~10	R-07-009/010/011 (consistency/booking), R-07-047 ("the residual entry exists")
8	~10	R-08-013 (NP-hardness argument), R-08-043 ("the §17 residual entry exists"), R-08-033 ("lemmas are vacuous rather than discharged")
9	3	mostly crisp; R-09-013-style absence claims
10	~6	R-10-011 ("stated as a design choice with its consequence")
11	4	R-11-013/016/019 (consistency citations)
12	~12	R-12-068–072 (doctrine entries: "applies uniformly", "the §17 entry exists")
13	4	R-13-023 ("stated rather than blurred")
14	4	R-14-011 ("consistent with R-17-002")
15	~30	R-15-040/040a ("the fork is recorded"), R-15-097 (honest scope), R-15-120/138/142 (bookings), R-15-189l
16	~9	R-16-011 ("each enabling property is a §15 mandate")
17	~70	By design: the preamble declares acceptance = "booked with its owner and scope rather than absorbed" — nearly every IS entry's criterion is a presence-of-text check
18	~10	R-18-009 (open questions "named"), R-18-023/028 (existence-proof citations)
Total ≈ 200 (~18%). Explicitly self-referential/circular: R-05-151 (this document is its own acceptance), R-01-001↔R-04-001 (each is the other's check), R-03-008↔R-17-030r (each names the other as the decider; R-17-030r concedes its half is "a review-gate finding and nothing enforced"), and the "the §17 residual entry exists" pattern (R-07-047, R-08-043, R-12-072, R-15-120, R-15-138, R-15-142, R-05-118, R-05-092) where existence-of-a-booking is the criterion — sound as bookkeeping but content-free about the underlying claim. §17 is honest about this; the §1/§3 goal/threat entries are not.

6. The conferral mechanism
Counts (stated, tool-recomputed): 18 requirements carry · Fail-closed: conferring into R-17-030r's register, collected by 14 seams (R-17-030b–q minus the composition entry 030l and the rate obligation 030m). 3 requirements carry · RoT-fresh: (R-09-023, R-09-028, R-12-017) conferring into R-10-013a's enumeration. I verified the 18 fail-closed conferrals against the text — the count matches exactly.

Soundness: structurally sound for its stated goal — bidirectional checking (unconferred member or uncollected conferral both fail the build) genuinely closes register-vs-requirements drift, which is the demonstrated failure mode (R-17-016's repair). It is explicitly not a completeness mechanism: "fails closed" and "needs freshness" are admitted as undecidable judgments, and tools/check.ps1 over-approximates by refusal-vocabulary scan with forced disposition.

Gameable in two admitted ways: (1) vocabulary evasion — a refusal phrased in words the over-approximation doesn't catch confers nothing and passes; R-17-030r says its own n–q members "were found by running it and not by inspection," which both evidences the scan works and proves the scan is the only backstop; (2) self-conferral — nothing forces an author adding a new refusal mechanism to write the line, other than the vocabulary scan and the review gate. R-10-013a's rule ("a fourth conferral is not admitted until R-10-013 names the state it adds") is additionally backwards-looking: the collector gates the conferral rather than the conferral driving the collector, which is conservative but means a legitimate freshness need blocks on editing one specific entry. Net: honest and well-built for drift-detection, deliberately incomplete, and it says so.

7. Needless complexity / over-engineering in the register machinery
The entry grammar is violated by the register itself. The header specifies one · Accept: line per entry; R-08-012e has three, R-15-190 two, R-15-189j three, R-10-013a three, R-17-030r three — it is undefined which bullet decides the requirement, in a document whose entire premise is one-decidable-criterion-per-obligation.
"Order is the specification's, not the numbering's" buys prose-order insertion at the cost of permanently non-monotonic IDs (its own example: §18.5 runs 031, 032, 034, 035, 033) — every future reader pays a sorting tax forever so that diffs stay prose-local. Combined with permanent IDs + letter suffixes, 213 of 1135 entries (19%) are post-hoc insertions, which suggests the numbering discipline is fighting the edit rate rather than serving review stability.
Derived numbers embedded in normative prose the doc admits nothing checks by hand: "eighteen requirements confer a refusal and fourteen seams collect them, both figures recomputed" (R-17-030r), the 1135/213/per-section table — all correct today, all silently rotten if check.ps1 isn't run; the mechanism assumes its own tooling as a permanent precondition, which is a build dependency the register never books as one.
The "derived view" boilerplate paragraph ("states no obligation of its own, cites the governing requirement for every row, and is defective, never authoritative...") is restated near-verbatim four times (R-15-001a, R-15-100a, R-17-001b, R-17-016a) — ironic in a register whose own sweep 3 exists to kill exactly this pattern; it should be one requirement cited four times, per the register's own rule.
checker-theater risk at the meta level: R-05-151a mandates negative-testing the trace checker against five deliberately-broken copies ("a checker that has never failed is indistinguishable from one that cannot") and check.ps1 -Fix rewrites the normative document it checks — a self-modifying artifact relationship that is powerful but is itself an unbooked trust seam (the tool that edits the register is not in any TCB inventory or axiom set).
Residual-memoir density: entries like R-15-036j (a closed-form λ padding analysis with a p=0 bound), the three-sweeps narrative, and multi-paragraph accept texts that re-argue the design (R-15-036m/n/p read as design documents) blur the register's stated normative role; roughly the §15.7 dictionary-encoding block alone (R-15-036a–q, 17 entries) is a specification masquerading as requirements.
The coverage matrix's full bipartite product (R-17-001a: every boundary × every property, one row each) is the heaviest single machinery piece; it's tool-checked so it's consistent, but it manufactures a large derived artifact whose maintenance cost is perpetual and whose failure mode (a pair citing a requirement that doesn't actually carry it) is exactly the fidelity gap R-05-151a already admits it doesn't check.