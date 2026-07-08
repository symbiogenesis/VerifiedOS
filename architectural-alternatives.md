# Evaluated Architectural Alternatives (non-normative)

> Externalized from [verification-maximal-os.md](verification-maximal-os.md).
> This document records evaluated architectural alternatives and their disposition; it is **not** part of the normative spec.
> Cross-references of the form §N point to sections of that specification.

It exists so the living document carries the reasoning behind what was *not* adopted.

## Belt / Mill-class architecture — deferred to a hypothetical gen-2, on one ground

Mill's security features were run through the §15 admission test and the import discipline:
- **Protection ≠ translation, turfs, portal calls (PLB separate from TLB)** — Mill's headline model is **already subsumed by CHERI**, and more generally: capabilities bound memory irrespective of page tables, and sealed-capability domain crossing is the portal. The spec converges on Mill's single-address-space-with-per-domain-protection vision from a substrate that has a formal model (Sail, Cerise) Mill lacks — a convergence the base makes literal by deleting the MMU outright (below), so protection is by capability alone and there is no translation to separate from.
- **Backless memory / implicit zero-on-allocate** — elegant, but *fails the admission test*: read latency depends on whether a page has been written (a data-dependent timing signal about allocation state).
  The security goal (no uninitialized-memory disclosure) is already met by eager-zeroize + `cbo.zero`; importing the mechanism would add a channel the spec forbids.
  Its rejection is the admission test working correctly.
- **The spiller (secure call/return; return addresses unreachable by code — structural anti-ROP)** — a genuine win, but **inseparable from the belt**; the RISC-V analog is a hardware shadow stack, which §15 excludes as retrofit complexity.
  Logged as an intrinsic belt advantage, not a base import.
  (Note the static-prediction/no-RAS decision makes call/return relatively more expensive on the base, marginally sharpening the spiller's *performance* appeal — but not its importability.)
- **The belt itself** contributes less security than the framing implies: its wins are ILP and register-file-elimination hygiene, while the *security* comes from turfs (→ CHERI) and the spiller.

**Net for the base spec:** nothing imports into the normative body — the relevant *security* ideas are already present via CHERI, and the rest is inseparable from the belt.

**The one non-redundant gen-2 argument is ILP without speculation.**
The in-order scalar cores pay a large IPC tax for the no-speculation guarantee (and an additional forward/indirect-branch and call/return tax for the no-dynamic-prediction guarantee).
A Mill-style machine recovers wide ILP through exposed, statically-scheduled parallelism plus **metadata speculation** — NaR ("Not a Result") poison values let loads be hoisted and only fault when consumed, giving speculative *scheduling* benefit with **no microarchitectural rollback and therefore no transient-execution class**: the same security posture at higher ILP.
Counterweights: (1) even ignoring verification *effort*, a belt gen-2 means rebuilding the entire substrate this spec depends on — RISC-V Sail model, CHERI-CompCert backend, Islaris, Cerise, RVV — none of which transfers; "ignore verification effort" does not make the ecosystem exist.
(2) If leaving RISC-V anyway, the belt may not be the most spec-coherent target: **EDGE / block-atomic execution** (TRIPS/EDGE lineage) issues dataflow blocks that **commit atomically as a unit** — instruction-level transactionality, a direct downward extension of G4 and §11 all the way into the pipeline.
A belt is a clever operand-lifetime trick; block-atomic execution *rhymes* with the rest of the architecture.
EDGE is even less mature than Mill, so it is a research program, not a spec.

**Disposition:** gen-2 candidate iff ILP-without-speculation becomes the binding constraint and a formal/toolchain ecosystem can be built around the target; **block-atomic (EDGE) is the preferred "abandon the register file" direction** over the belt for this design, on transactional-coherence grounds.
Both remain non-normative.

---

## Itanium / EPIC / VLIW — ILP without a belt, but the substrate cost *is* the belt's; the one importable atom is already NaR

"Itanium-style VLIW" is not one mechanism but four separable ones, and the import discipline resolves them individually against the §15 admission test — the same decomposition that logged the belt's spiller while rejecting its backless memory.
The premise — recover in-order ILP without a belt and without leaving RISC-V — is only half-answerable: **EPIC is a distinct ISA, not a RISC-V extension**, so its bundle substrate abandons the platform exactly as the belt does, and into a *deader* ecosystem — IA-64 was discontinued in 2021 and dropped from the Linux kernel, so there is no Sail model, no CHERI-IA64, no verified CompCert backend, no Cerise, no RVV analog to inherit.
The counterweight (1) written against the belt — "rebuilding the entire substrate this spec depends on" — applies verbatim and harder: a belt is at least live research; EPIC's ecosystem is post-mortem.

Run the four ingredients through the admission test:
- **Static bundling (the VLIW core — template/stop bits, explicit issue groups)** — the genuine ILP source, and microarchitecturally it *passes* on the no-hidden-state axis (no rename, no reorder buffer, no scoreboard).
  But it is a new instruction encoding, not an extension of RV64 — the substrate cost above is entirely this bullet's — and its scheduling dividend is *already banked* by the base being in-order: the §15 C-class is **in-order single/dual-issue** already, so widening in-order issue and letting the bespoke CompCert/SECOMP scheduler pack independent operations recovers most of the ILP **with zero ISA change and zero substrate cost**.
  VLIW's distinctive hardware win over an in-order superscalar (deleting the interlock/scoreboard) is marginal, and does not survive its own binary-portability curse (below).
- **NaT / control speculation (deferred-fault poison loads)** — **the one importable atom, and the belt entry already banked it under another name: NaR.**
  Itanium's NaT bit *is* metadata speculation — hoist a load, and on a deferred exception set poison and trap only at consumption, with **no microarchitectural rollback and therefore no transient-execution class**.
  It *passes* all five (architecturally-visible poison, deterministic, Sail-expressible, no hidden shared state, no autonomous behavior), and — the load being architecturally completed — carries data-independent latency, clearing test (2) besides.
  Crucially it is **separable from the bundle**: NaR/NaT can be a *small* RV64 extension (a poison tag bit + a speculative-load + a check/consume op), lifted out of both the belt and EPIC and dropped straight into RISC-V.
  Its residual is exactly the one already accepted for wrong-path static fetch (§15, "Control-flow prediction"): a hoisted load's cache footprint is a deterministic function of the compiler-fixed instruction stream, not of learned history, so it falls in the cache-partitioning/`fence.t` bucket — the sole caveat being that a *secret-dependent* speculative address is an ordinary `Zkt`/`Zvkt` flow-label obligation, no different from any load.
- **ALAT / data speculation (advanced loads hoisted over possibly-aliasing stores)** — **fails the admission test, twice.**
  The ALAT is a hidden microarchitectural table whose occupancy records which speculative loads are outstanding and whether a later store aliased them — new hidden shared state surviving a partition switch (test 3) and a data-dependent load↔store aliasing signal (test 2).
  It is the same shape as the LR/SC reservation set and the dynamic predictors §15 *deletes* rather than flushes; its rejection is the admission test working correctly.
- **Full predication (predicate register file, near-universal guarding)** — double-edged, and the spec already took the admitted half.
  Converting branches to predicated dataflow *would* erase the forward/indirect-branch and call/return penalty the static-only-prediction posture pays, and predicated-off timing is fixed (constant-time-friendly) — but full predication is an enormous ISA-surface addition to a profile that *deleted the C extension* purely to buy unambiguous 4-byte decode, and it would inflate the Sail model, the RTL ⊑ Sail proof, and CHERI integration.
  The **minimal** form of exactly this idea is already adopted — `Zicond` (branchless select), "doubly load-bearing" for precisely this reason; full predication is its un-admitted maximal cousin.
- **Register rotation + the Register Stack Engine (RSE)** — **fails hardest.**
  The RSE spills and fills the register stack to memory *autonomously* at data-dependent moments — an autonomous memory-writing engine (test 5 — the same ground the `Svadu` page-walker updater is excluded on, and the MMU deleted with it, below) whose unpredictable traffic falsifies the per-(class, OPP) WCET tables the entire §11/§13 temporal-admission edifice consumes.
  Reject outright; software-pipelined loops fall back to the compiler's static allocation.

**Nothing gets deleted — the load-bearing misconception.**
The hoped-for simplification runs backwards.
The IPC tax the base pays is not the cost of *owning* a verifiable speculation engine VLIW would let it remove — the base is *already* in-order, *already* forbids speculation, *already* forbids dynamic prediction (§15).
**The tax is the price of *forbidding* speculation, not of a removable mechanism.**
VLIW deletes nothing here; it *adds* a mechanism to claw performance back under the forbiddance, and that mechanism *enlarges* the verified surface at every layer — a bigger Sail model (bundles, poison, predication, rotation), a bigger RTL ⊑ Sail proof (already the least-built arrow, §17), CHERI re-integrated against a new encoding, and, decisively, a **verified trace scheduler for EPIC's predicated, poison-tagged, rotating-register bundles** — which Chamois/KVX-CompCert's verified bundle scheduling and software pipelining do not reach, targeting only the far simpler Kalray VLIW — net-new, hard proof.
VLIW's famous dividend, moving scheduling out of hardware into the compiler, is already spent: an in-order core has no hardware scheduler to move.
And the sting compounds — EPIC's own ILP mechanisms (ALAT, RSE) make WCET *worse*, so importing them *costs* §11 determinism.
By the platform axiom this is the wrong trade in the wrong direction: spending the scarce currency (trust, proof surface) to buy the free one (performance).

**Bespoke, microarchitecture-coupled binaries — the disqualifier, not an inconvenience.**
The instinct that VLIW needs specially compiled binaries is right, and it is fatal, on three compounding counts.
(1) VLIW bundles are a distinct encoding, so standard RV64IMV+CHERI binaries do not run — forking the single-recompile-target premise of [userspace-porting.md](userspace-porting.md) (certifying Rust → RV64+CHERI) into two.
(2) VLIW's classic curse: a schedule encodes the *specific* issue width and operation latencies it was packed for, so a pipeline change forces a recompile — re-coupling ISA to microarchitecture, the exact thing RISC-V's abstract contract exists to prevent, and violating §15's "one base ISA, one kernel binary, one parameterized model; classes differ only in datapath" property (a bundle schedule is not portable across the C/V/M scalar front ends).
(3) Every FPCC artifact — the binary-level proofs, memory-safety certificates, and constant-time certificates of §5/§6/§13 — is stated *at binary level against the CHERI-RISC-V Sail model*, so a new ISA means restating the Sail model and re-minting every certificate, retargeting the whole Tier-1/2 toolchain.
The bespoke-binary requirement thus re-imports precisely the microarchitecture-in-the-binary coupling RISC-V's abstract ISA was chosen to delete.

**Where EPIC ranks among the "abandon RISC-V for ILP" targets.**
The belt entry already ordered EDGE ≻ belt on transactional-coherence grounds (block-atomic commit *rhymes* with G4 and §11).
EPIC ranks **below both**: its one edge over Mill and TRIPS is that it *shipped* — but it shipped and *died*, so the ecosystem advantage is negative; its ILP recipe leans on ALAT and RSE, which fail the admission test where the belt's spiller and EDGE's block commit do not; and it *rhymes* with nothing in the architecture.
A belt is a clever operand-lifetime trick and EDGE a transactional pipeline; EPIC is a compiler-scheduling bet whose hardware crutches this spec forbids.

**Disposition:** rejected as a base direction — EPIC abandons the RISC-V substrate as fully as the belt (into a post-mortem ecosystem), *inverts* the hoped-for simplification (the in-order IPC tax is the price of forbidding speculation, not a removable engine; VLIW only adds verified surface), and mandates bespoke, microarchitecture-coupled binaries that fork both the ecosystem and the proof base.
**Two non-redundant atoms are distilled and kept inside RISC-V:** (1) **NaR/NaT deferred-fault poison loads** — separable from both belt and bundle, admissible as a *small* extension, the genuine "ILP without speculation" lever, logged here as the sharper form of the belt entry's metadata-speculation argument and the first candidate should that constraint bind; and (2) **wider in-order superscalar + verified static scheduling on plain RV64** — already licensed by §15's *in-order single/dual-issue* C-class and ideally served by the bespoke compiler, the actual answer to "the in-order path is slow," strictly *before* any ISA fork.
Both remain non-normative; **VLIW as a whole imports nothing**, and ranks below both the belt and EDGE as an abandon-the-register-file target.

---

## CHERI-Wasm as a hardware ISA — the interface half is already imported (WIT → §12), the execution half is the substrate §14 deletes

"Should the hardware natively target CHERI-based Wasm" bundles three separable proposals, resolved individually against the §15 admission test and the import discipline — the same decomposition that logged the belt's spiller and EPIC's NaR while rejecting the rest.
(1) **Wasm-as-ISA** — the machine's instruction set *is* Wasm bytecode, a structured stack machine executed in silicon; (2) **CHERI-as-Wasm-sandbox** — capabilities enforce a module's linear-memory bound in hardware, deleting the per-access bounds check; (3) **Wasm-as-substrate** — the system's portable deployment/execution format is (CHERI-hardened) Wasm.
Proposal (3) is **already dispositioned**: §14 states *"'WASI-shaped' is API vocabulary, not substrate: everything compiles to native RV64+CHERI… Wasm is not a system execution target,"* and §5 repeats it (*"Wasm/WASI is not an execution target anywhere in the system"*) — so lifting Wasm into *silicon* is the maximal form of a decision already made twice, and the only live questions are (1) and (2).

**The steelman — Wasm's three real cards.**
Unlike the belt/EPIC targets, Wasm is not ILP bait; its appeal is orthogonal and genuine.
(a) **It is one of the best-formalized ISAs in existence, and its semantics live in *Coq*** — WasmCert-Coq (with WasmCert-Isabelle) carries full machine-checked type soundness, so a single-Coq-prover design that calls specifications the crown jewels (§5) is looking at a target already mechanized in its own prover.
(b) **Linear memory is capability-shaped** — a module's heap is exactly `base + length`, i.e. one CHERI capability, so bounding the sandbox with a cap and deleting the software bounds check is a real, published CHERI-Wasm result.
(c) **Sandbox-by-construction** for untrusted code with no custom silicon.

**Why it fails for *this* design — four load-bearing objections.**
- **Wasm secures the host from the module, never the module from itself.**
  Its sandbox is *coarse, inter-module* isolation and supplies **zero intra-module memory safety** — a C-to-Wasm heap overflow is fully exploitable *inside* the linear memory (Lehmann/Kinder/Pradel, "Everything Old is New Again: Binary Security of WebAssembly," USENIX Security 2020).
  So the Tier-2 **temporal-safety + control-flow-integrity certificate** (§13) is *still owed on top* of Wasm: it interposes a bytecode/validator/stack-machine layer without retiring a single proof obligation.
  And CHERI already delivers **byte-granular** safety for *every* pointer, not merely the heap base — so card (b), the one hardware-relevant Wasm idea, is **already fully banked by purecap RV64**.
- **The substrate cost is the EPIC disqualifier, verbatim.**
  A stack-machine bytecode is a *distinct ISA*, not an RV64 extension, so it forks the RISC-V Sail model, the CHERI-CompCert backend, Cerise, and Islaris, and **re-mints every FPCC, memory-safety, and constant-time certificate** — all of them stated *at binary level against the CHERI-RISC-V Sail model* (§5, §6, §13).
  This is exactly the cost the Itanium/EPIC entry ruled fatal: *"a new ISA means restating the Sail model and re-minting every certificate."*
  It spends the scarce currency (trust, proof surface) to buy cross-ISA portability the **Goals declare a non-goal** ("no requirement for broad software or hardware compatibility"; §2).
- **It fights the decode, WCET, and memory-model discipline head-on.**
  The C extension was deleted *purely* to buy unambiguous 4-byte decode (§15); Wasm's binary format is **variable-length, byte-aligned, LEB128-immediate, with structured control-flow blocks** — a strictly *worse* decode surface for the binary-level proofs.
  A hardware stack machine then faces a forced choice, both branches inadmissible for the performant case: **JIT** the bytecode to an internal register form — hidden translation-cache microarchitectural state surviving a partition switch (fails admission test 3) and runtime codegen the W^X invariant forbids (§14) — or **interpret** it, slow *and* still carrying the decode/validation surface.
  Wasm threads, moreover, ride a **relaxed memory model** (C++/JS-derived), colliding with the normatively adopted **Ztso** that deletes RVWMO (§15).
- **The one admissible realization is the one §14 already allows — in software.**
  A *pure software interpreter* over Wasm is not a hardware feature at all: it is ordinary contained code on native RV64+CHERI, and §14 already permits exactly that — *"an app may embed an interpreter-mode Wasm engine as its private plugin mechanism… invisible to the architecture"* — its linear memory hardened by the surrounding CHERI process for free.
  Moving it into silicon buys only **speed** — the single currency the platform spends freely (*performance deliberately subordinated to security*) — while enlarging every scarce one.

**The distilled atoms — both already banked, so nothing new imports.**
Following the belt→spiller / EPIC→NaR discipline, the non-redundant ideas are extracted and found *already present*: (1) **Wasm's interface/type calculus is already imported** — the §12 IDL is **"WIT-derived, fork-and-frozen"** (worlds → manifests, resources → capabilities), so the design took the Component Model's *type layer* and deliberately dropped its *bytecode/linear-memory execution model*; hardware-Wasm would re-adopt precisely the discarded half.
(2) **Linear-memory-as-capability is already CHERI** — byte-granular and universal, strictly exceeding Wasm's single-heap sandbox.
The enviable third property — the **Coq-mechanized semantics** — buys nothing the design lacks: the CHERI-RISC-V Sail model ⋈ FPCC already give a Coq-checkable *binary-level* story, and Wasm's theorem is *type* soundness (sandbox integrity), not the functional-refinement, constant-time, and WCET properties this stack proves.

**Where it ranks among "abandon RISC-V" targets — off the scale, because the motivation differs.**
The belt and EPIC entries ranked EDGE ≻ belt ≻ EPIC on *ILP-without-speculation* and transactional-coherence grounds.
Wasm does not enter that ranking: those targets trade the substrate for **ILP** (a real if non-binding constraint), whereas Wasm trades it for **portability + sandboxing** — a declared non-goal and a property CHERI already exceeds, respectively.
It is rejected on *motivation*, one level above the cost argument that sinks EPIC.

**Disposition:** rejected as a hardware ISA, as a CHERI-sandbox target, and as a substrate — the execution substrate stays **native RV64+CHERI + FPCC**, itself the *stronger* "portable safe target" (a machine-checked proof travels with the artifact, not merely a sandbox claim).
Both distillable atoms already sit in the design (WIT → §12 IDL; linear-memory = capability → CHERI), so **nothing imports**.
Wasm's sole admissible role is the §14 **contained interpreter-mode plugin engine** — software, not silicon, an application-internal choice the spec already sanctions.
Non-normative; no spec-body change.

---

## HexFive MultiZone — already covered, strictly dominated, nothing to import

MultiZone is a policy-driven separation kernel: a small nanokernel orchestrating standard RISC-V **PMP** to isolate zones, a no-shared-memory messenger between zones, and a configurator fusing linked zone binaries + policy + kernel into a signed image (running unmodified code by trap-and-emulate of privileged instructions).
Each component maps onto a strictly stronger mechanism already mandated here: PMP zones → **CHERI + capability-checked DMA + coherence islands** (byte-granular, unforgeable, formally modeled vs. a handful of coarse power-of-two regions); nanokernel → the **seL4-design capability microkernel** (re-proved in Coq, §5) with a completed refinement + non-interference proof (MultiZone advertises "formally verifiable," not a finished machine-checked proof); messenger → the **verified ring data plane** under Ztso; configurator → **static composition + signed generation + proof-checked admission**.
Its distinctive selling point — zero hardware change, zero code change, commodity cores — is the pragmatic *inverse* of a spec that mandates custom CHERI silicon and native capability code, and its trap-and-emulate method opposes the no-ambient-authority stance.
**There is no clean pure-win to extract; it is a lightweight point on the same design axis already taken to the maximum.**

**The inverse question — descend the base to MultiZone rather than import it upward.**
The symmetric proposal is not to lift a MultiZone idea into this spec but to collapse the isolation substrate *down* to MultiZone's: an **M-mode + U-mode processor** (no S-mode; the trusted kernel resident in M-mode), no Sv39 MMU, no CHERI, isolation by **PMP alone**.
The appeal is real and almost entirely about *realization*: PMP ships in every commodity RISC-V core, so the binding CHERI-silicon and CHERI-CompCert dependencies (§6, §18) evaporate; the proof stack drops to mature plain-C CompCert with no CHERI-C mechanization gap (§7, §17); and shedding a privilege mode plus the MMU is a genuine silicon- and Sail-surface reduction that even rhymes with static composition (§7), since a stateless single-address-space design leaves most MMU machinery idle.

**Rejected as the *base* on the goal function, not the effort function.**
Four objections are load-bearing.
(1) **Granularity ceiling:** PMP is a handful of coarse power-of-two/TOR regions per hart, whereas the design names thousands of fine domains — per-origin, per-session ring table, per-surface/per-input, per-element gather/scatter (§8, §12, §14) — a count and byte-granularity PMP structurally cannot express, gutting G1/G2 least-authority.
(2) **No intra-domain safety:** PMP isolates domains but does nothing *inside* one, so memory-safe-by-construction apps (§5, §14), the Cerise universal contract that bounds *wholly unverified* code (§13 Tier-2), the W^X capability-monotonicity invariant (§14), and per-element vector bounds (§8) lose their hardware footing and fall back onto the Rust toolchain — enlarging the very containment trust FPCC exists to remove.
(3) **"PMP only" is not even sufficient:** malicious DMA still needs capability-checked DMA and cross-domain timing/coherence still needs the islands and TDM NoC (§3, §15), so PMP retires no other mechanism — it is a weaker spatial layer, not a one-mechanism simplification.
(4) **It reopens ambient authority:** MultiZone's trap-and-emulate of privileged instructions is exactly the ambient-authority pocket §2/§14 forbid.
The defect is the trap-and-emulate model and PMP-as-primary, *not* Machine-mode kernel residence itself — which the platform embraces under capability-gated privilege (the single-privilege-mode entry below): once CHERI governs privilege as a PCC permission, a Machine-mode kernel is confined by unforgeable capabilities, whereas MultiZone's M-mode code is confined by nothing finer than coarse PMP.
"More robust" is genuinely two-sided: PMP is more mature *today*, but CHERI is the stronger, more *uniform* guarantee once built (subsuming MMU-split, shadow stacks, and software W^X into one monotone mechanism), covering the same ground with fewer orthogonal parts.

**Disposition:** the M-mode/PMP-only design is **rejected as the base, not a stage the plan passes through** — the platform is purecap from first bring-up (§18) with no capability-degraded instantiation to descend to, and "trust is the scarce resource, engineering is free" resolves the base toward CHERI's smaller, deeper, byte-granular story.
Taking PMP-only as the *goal* would trade the platform's defining property — hardware that bounds arbitrary unverified code — for buildability the spec deliberately declines to optimize.

**PMP is dominated in both roles — and dropped entirely.**
The domination verdict above is specific to PMP as a *primary, fine-grained compartmentalization* mechanism, where CHERI + capability-checked DMA + islands strictly exceed it.
A tempting alternative *banks* PMP in a *secondary, coarse, sub-kernel backstop* role (immutable-text/W^X, per-core partition bound, crown-jewel secret fencing) on the ground that, being CHERI-disjoint, it would hedge a CHERI *logic* fault no in-band mechanism otherwise could.
**That backstop is dropped too** (the drop-PMP entry below): with CHERI formally verified (the Oxford/Google CHERIoT-Ibex conformance proof; the RTL ⊑ Sail workstream, §18) and application-class silicon removing PMP on exactly this ground (Codasip's A730 — PMP *"can be removed and replaced by more power- and area-efficient circuits"*), the disjoint hedge is judged redundant Sail surface, and the three roles collapse onto CHERI monotonicity (§7, §14), the crypto core's hardware boundary, and TME (§15).
So the full disposition is unqualified: nothing of MultiZone's *architecture* imports, the base does not descend to it, and PMP is not retained even as a backstop — CHERI is the sole in-band spatial mechanism, hedged by its own verification rather than by a coarse subset of itself.

---

## Delete the MMU — purecap single-address-space, CHERI is the sole in-core spatial mechanism

The proposal is to remove **Sv39 and the MMU entirely** and run the die as a **single physical address space** under CHERI, with `satp` fixed to Bare and no translation anywhere.
The claim is redundancy: **CHERI + capability-checked DMA + coherence islands** (§8, §15) already supply the three things an MMU is kept for — byte-granular in-core spatial isolation, a physical-reach bound, and DMA confinement — so Sv39 is a *second, in-band* isolation mechanism bought at the price of the page-table walker, the TLB and walk-cache state, the entire kernel VM subsystem (VSpace / page-table / frame-mapping objects, map/unmap, `satp` management, TLB shootdown), and their share of the Sail model.

**The spec had already converged here without taking the step.**
The Mill entry (above) records that the design *"converges on Mill's single-address-space-with-per-domain-protection vision"* because *"capabilities bound memory irrespective of page tables"*; the MultiZone descend-the-base analysis (above) concedes that *"a stateless single-address-space design leaves most MMU machinery idle"*; and the §13 hardware universal contract is stated as **CHERI + caps + capability-checked DMA** — the MMU already absent from it.
Deleting Sv39 makes the base what the rest of the document already describes.

**It resolves the walker contradiction outright rather than by exemption.**
Admission test 5 (§15) bans *"hardware walkers, updaters, or feedback loops,"* and Sv39's page-table walker is exactly that — an autonomous, address-dependent memory-reader with TLB and walk-cache state that the fence.t flush-set, the WCET model, and the partitioning story never booked (the same ground `Svadu`'s A/D-update walker was excluded on).
The choices were to *state an exemption principle* for the read-side walker or to *delete it*; deleting the MMU takes the second and stronger horn, so test 5 stands with **no in-profile exception**, the flush-set and WCET tables shed the walk terms, and the composition-frozen-page-table fallback (a fixed-table walker that still needs that exemption, and TLB state that still joins the flush-set) is subsumed — deleting the walker is strictly stronger than freezing what it reads.

**The honest counterargument — and why it does not hold at the base.**
Sv39 would give an **MMU-disjoint intra-core isolation layer** that could still separate compartments if CHERI itself had a logic fault; deleting it concentrates in-core spatial isolation on one mechanism.
Three things answer this.
(1) The coarse **PMP backstop** that could supply a CHERI-disjoint failure domain is itself dropped (the drop-PMP entry below): rather than hedge a CHERI *logic* fault with a second in-band mechanism, the platform hedges it with the **formal verification of CHERI** (RTL ⊑ Sail §18; the Oxford/Google CHERIoT-Ibex conformance proof; Codasip's app-class deployment) — *verify rather than hedge*.
(2) In the single-address-space model the design already converges on (the Mill entry above), the MMU **never supplied a per-compartment second layer to begin with**: intra-core compartments are separated by CHERI bounds over one shared map, so the page tables would be an identity-shaped translation, not the disjoint per-compartment isolation the fault argument imagines — the "second layer" was largely notional. (3) Keeping it would mean **carrying an admission-test-5 violation** (the autonomous walker) as standing defense-in-depth — trading the profile's own determinism rule for a layer whose fine-grained disjointness the SAS design does not actually instantiate.

**The bet, stated.**
Single-address-space CHERI at *application-class* scale rests on **CheriOS** and **CHERIoT** as existence proofs, and both are small-scale; app-class SAS-purecap is the wager this takes.
It is bounded, not blind: CHERI is the **primary, byte-granular, formally-modeled** mechanism the whole design already leans on (§8, §13); capability-checked DMA and coherence-island separation cover the device-access and cross-domain-timing residuals a page table never addressed anyway (physical-reach resting on CHERI partition bounds, PMP dropped — the drop-PMP entry below); and because the kernel is **bespoke** (seL4's capability / IPC *design* re-proved in Coq, not stock seL4's C), it is built single-address-space-native — dropping the VSpace object classes — rather than retrofitting SAS onto a page-table kernel.

**This is not the descend-to-PMP-only move.**
The rejected MultiZone descent (above) shed the MMU *and CHERI*, falling back on coarse PMP as the primary mechanism; this sheds **only** the MMU and keeps CHERI as the byte-granular primary.
The two share a silhouette (no Sv39) and nothing else: one deletes the redundant second layer and keeps the strong first, the other deletes the strong first and keeps the weak second.

**Where it ranks, and its relation to kernel-in-gateware.**
This lands one of the three simplifications the kernel-in-gateware entry (below) names as its kernel-shrink terminus — **single-address-space CHERI isolation deleting the VM subsystem** — as a *base* move rather than a gen-2 one, and it subsumes the composition-frozen-page-table fallback (there are no tables left to freeze).
The remaining kernel-shrink simplification the terminus names — the table-driven cyclic executive replacing MCS — is **also adopted** (§7, §11).

**Disposition (adopted; normative in §7, §8, §14, §15).**
The MMU is **deleted**: `satp` is Bare, there is no Sv39 / Sv48 / Sv57 and no `Svadu` / `Svade` A/D machinery (§15), the kernel drops seL4's VSpace / page-table / frame-mapping object classes for a single physical address space (§7), and **CHERI is the sole in-core spatial mechanism** (with PMP dropped too — the drop-PMP entry below — so no disjoint in-band backstop remains), capability-checked DMA + coherence islands (§15) the device-access and timing boundaries.
The platform axiom decides it as ever — *trust is the scarce resource, engineering is free, delete rather than defend*: the MMU is a second in-band mechanism whose fine-grained defense-in-depth the SAS design does not instantiate, purchased with a walker the admission test bans and a kernel subsystem the proof must carry.
**Honest residual (§17):** in-core spatial isolation rests on CHERI alone (a logic fault has no in-band fallback — the coarse PMP backstop is dropped too, below — only CHERI's own verification), and application-class single-address-space purecap is less battle-tested than page-table isolation (CheriOS/CHERIoT are small-scale) — offset against a net deletion of the walker, the TLB/walk-cache state, the VM subsystem, and their Sail surface.

---

## Single privilege mode — Machine mode only, capability-gated privilege (CHERIoT-lineage)

The proposal is to delete **Supervisor and User modes** and run the die in **Machine mode only**, expressing privilege as a **CHERI permission on the program-counter capability** (the access-system-registers permission, CHERIoT-style) rather than a hardware privilege ring.
The claim is the same redundancy the MMU-deletion took one step earlier: once CHERI is *"the sole in-core spatial mechanism"* (§15), the S/U ring is a *second, in-band* privilege mechanism — a compartment is already confined by the capabilities it holds, so gating privileged operations (CSR access, interrupt-enable, context switch, sealing) by a **permission** rather than a **mode** removes the ring, its CSR bank (`sstatus`/`stvec`/`sepc`/…/`scounteren`), trap delegation (`medeleg`/`mideleg`), `sret`, and `Sstc` — and the mode-transition reasoning from the kernel proof — while losing nothing CHERI was not already enforcing.

**CHERIoT is the existence proof, and it has silicon.**
CHERIoT (Microsoft/lowRISC, contributed to the RISC-V standardization effort) is Machine-mode only by design — *"hierarchical privilege modes are unnecessary, so CHERIoT CPUs support only Machine Mode"* — with privilege carried by *"a permission that allows access to certain control and status registers … when a capability with that permission is installed as the program counter capability."*
Its trusted **switcher** (~300 instructions, seL4-scale) mediates cross-compartment and cross-thread transitions holding one reserved register, is itself CHERI-constrained, and is under formal verification (Oxford against the Sail model; Google on the switcher's isolation properties); first CHERIoT silicon taped out in early 2026.
The single-Machine-mode model is thus a verified, fabricated one — the privilege-architecture analog of the CheriOS/CHERIoT single-address-space existence proof the MMU deletion already leans on.

**The spec had already converged here.**
The per-core inventory (§7) had M-mode *"quiescent after boot"* and the kernel as the sole S-mode occupant with U-mode *"everything else"* — three rings for what is really *one trusted kernel beside many CHERI-confined compartments*.
The powerbox, the capability manifests, the ring data plane, and W^X are already **capability** statements, not ring statements.
Collapsing to one mode makes the enforcement substrate match the design the rest of the document already describes: authority is a capability, top to bottom.

**The honest counterargument — and why it holds at the base.**
The S/U ring gave (a) a hardware-privilege boundary preventing an app from executing privileged instructions regardless of CHERI, and (b) the privilege-layering that let the **PMP backstop** sit *below* the kernel.
Both are answered.
(1) In the CHERIoT model, privileged instructions are gated by the **PCC system-register permission**, which no compartment's PCC carries — so a compartment cannot execute a privileged CSR access for the same reason it cannot forge a pointer: the authorizing capability is *absent*, an unforgeable condition, not a mode bit an exploit might flip.
(2) The crown-jewel backstop role needs **no privilege ring** — and, as the drop-PMP entry below records, no PMP either: immutable-text/W^X, the per-core partition bound, and crown-jewel secret fencing rest on CHERI monotonicity (§7, §14), the crypto core's hardware boundary, and TME (§15), with the CHERI-*logic*-fault hedge being CHERI's own verification, not a coarse disjoint layer.
The boot/M-mode firmware still runs first, establishes the initial capability distribution, and goes quiescent; the microkernel is the resident Machine-mode holder of the system-register permission; nothing else holds it.

**The bet, stated.**
CHERIoT is **single-core, microcontroller-scale** (2–7-stage pipelines, tens of KiB–MiB), and its own multicore is future work; this platform is an **application-class multikernel** on multicore.
Single-privilege-mode purecap at that scale is a genuine extrapolation — the privilege-architecture sibling of the single-address-space bet (§17).
It is bounded, not blind: privilege-as-capability is *more* fine-grained and *more* uniform than the ring it replaces (CHERIoT's whole thesis), verified CHERI is the safety net (the coarse PMP backstop is dropped too — the drop-PMP entry below), the kernel is verified, and the in-order non-speculative core is exactly the target CHERIoT's permission/sentry model was designed for (the source notes it *"would be difficult on very large out-of-order cores"* — which this platform is not).

**This is not the descend-to-PMP-only move.**
The rejected MultiZone descent (above) shed the MMU, the S-mode ring, **and CHERI**, falling back on coarse PMP as the *primary* mechanism with trap-and-emulate ambient authority.
This sheds the rings and keeps **CHERI as the byte-granular primary**, with PMP only the locked coarse backstop.
The two again share a silhouette (a Machine-mode kernel) and nothing else: one governs privilege with unforgeable capabilities, the other with a handful of coarse regions and instruction emulation.

**Disposition (adopted; normative in §7, §8, §15).**
Supervisor and User modes are **deleted**: the platform runs Machine mode only, privilege is the CHERIoT-lineage access-system-registers permission on the PCC, the S-mode CSR bank / trap delegation / `sret` / `Sstc` are removed (§15), and the microkernel is the resident Machine-mode holder of the system-register and switch/seal authority (§7); PMP itself is dropped too (the drop-PMP entry below), so CHERI is the sole in-band spatial mechanism and no disjoint backstop remains.
The platform axiom decides it as ever — *trust is the scarce resource, engineering is free, delete rather than defend*: the S/U ring is a second in-band privilege mechanism, and its one non-redundant service (the sub-kernel backstop) is itself dropped as redundant against verified CHERI (below).
**Honest residual (§17):** privilege rests on CHERI alone (PMP dropped too, below) with no privilege-ring or disjoint-backstop redundancy, and single-privilege-mode purecap is unproven at application-class multicore scale (CHERIoT is single-core microcontroller) — offset against the deletion of the mode-transition machinery, the S-mode CSR bank, and trap delegation from the microarchitecture and the kernel proof.

---

## Drop PMP — CHERI is the sole memory-protection mechanism, verified rather than hedged

The proposal is to remove **physical memory protection (PMP)** — and `Smepmp` with it — leaving **CHERI as the only memory-protection mechanism on the die**.
It completes the arc the MMU deletion and the mode collapse began: PMP is a *third* in-band spatial mechanism (after Sv39 and the S/U ring, both likewise deleted), and RISC-V PMP provides a **strict subset** of CHERI's protection at coarse (≈16-region) granularity, so once CHERI is present and formally modeled, PMP is redundant Sail surface.

**The industry has already taken this step at application-class scale.**
CHERIoT drops PMP outright (*"the RISC-V PMP provides a subset of the protections of a CHERI system and so it, too, can be removed"*).
More tellingly for a platform of this class, **Codasip's A730** — a dual-issue *application* core, not a microcontroller — removes the PMP unit on exactly this ground: *"Most RISC-V cores included a physical memory protection (PMP) unit… both costly in area and power hungry.
With the fine-grained protection and compartmentalization of CHERI this unit can be removed and replaced by more power- and area-efficient circuits."*
The CHERI research program (Cambridge/SRI, with Microsoft Research and INRIA) and the Oxford/Google formal verification against the Sail model are the assurance base that makes dropping the coarse hedge defensible.

**Where PMP's three backstop roles go.**
A locked-PMP backstop (weighed in the MultiZone entry above) would serve three coarse crown-jewel roles, each of which instead collapses onto a mechanism already present: (a) **immutable-text / W^X** on kernel and firmware text and the read-only content-addressed image is the CHERI capability-monotonicity invariant of §14 — no writable capability to those regions is ever derived, so there is nothing for a second mechanism to re-enforce; (b) the **per-core physical-partition bound** is CHERI — each core's kernel instance is delegated a root capability bounded to its partition, and monotonicity (§7) lets it derive nothing outside it; (c) **crown-jewel secret fencing** is the crypto core's own hardware boundary plus TME (§15) — keys never leave the core, and anything resident outside it is ciphertext.

**The honest counterargument — the one thing genuinely lost.**
PMP's unique value is that it is **disjoint from CHERI**: an independent failure domain that would still bound each core if the CHERI machinery itself had a *logic* fault.
Dropping it means in-core spatial isolation, W^X, and the partition bound rest on **one** mechanism with no in-band redundancy.
This is answered the way the whole platform answers single-mechanism concentration — not with a second mechanism but with **proof**: CHERI is the mechanism the design verifies most deeply (the RTL ⊑ Sail workstream §18, the Oxford/Google CHERIoT-Ibex conformance result, Codasip's shipping app-class core), so the hedge against a CHERI implementation fault is the *verification* of CHERI, not a coarse subset of it running alongside.
And the residual that actually persists — fabricated silicon vs. verified RTL — is unchanged by keeping or dropping PMP (both share the one mask set, §17), so PMP bought no protection against it.

**The bet, stated.**
Resting all in-core spatial protection on CHERI is the same wager as single-address-space and single-privilege-mode, with no coarse fallback at all.
It is bounded, not blind: CHERI is byte-granular, formally modeled, and the most-scrutinized mechanism on the die; capability-checked DMA still confines device access and the coherence islands still bound cross-domain timing (neither was ever PMP's job); and the disjoint hedge is replaced by the strongest assurance the project has.
If a future analysis judged the CHERI-logic-fault residual intolerable, the composition-static locked-PMP backstop is the cheapest thing to re-admit (subtractive, static, Sail-modeled) — but it is not carried by default.

**Disposition (adopted; normative in §7, §14, §15).**
PMP and `Smepmp` are **removed**: CHERI is the sole memory-protection mechanism, W^X and the per-core partition bound rest on CHERI monotonicity (§7, §14), crown-jewel secrets on the crypto core's boundary and TME (§15), and device DMA on capability-checked DMA (§15).
The platform axiom decides it as ever — *trust is the scarce resource, engineering is free, delete rather than defend* — with the twist the whole design turns on: what lets a **single** mechanism replace a defense-in-depth stack is that this one is **formally verified**, so *delete rather than defend* becomes *verify rather than hedge*.
**Honest residual (§17):** in-core spatial isolation, W^X, and the partition bound rest on CHERI alone with no in-band disjoint backstop; the sole hedge against a CHERI logic fault is CHERI's own verification (RTL ⊑ Sail, Oxford/Google, Codasip), the fab residual unchanged.

---

## Drop the IOMMU — capability-checked DMA, CHERI as the sole spatial mechanism system-wide

The proposal is to remove the **IOMMU** — and to decline its device-side-PMP cousin the **IOPMP** with it — confining device DMA by **CHERI capabilities carried into the interconnect** rather than by an address-translation unit or a region-protection table.
It is the device-side completion of the arc the MMU deletion, the mode collapse, and the PMP drop began: the IOMMU is to the DMA path what the MMU is in-core — an address-translation unit with a page-table walker, translation caches (IOATC), and in-memory device/context structures — and in the single physical address space this platform already adopts (the MMU-deletion entry above), its *translation* is unused; only its *protection* is wanted, and CHERI supplies that unforgeably and byte-granularly.

**The mechanism, and why it is not merely IOPMP.**
Every DMA-capable block becomes one of two capability-checked shapes: a **core-issued capability-operand mover** (the §15 coprocessor-line discipline the matrix and FEC units already follow — no independent mastership), or an **autonomous streaming engine holding a delegated, bounds-checked, revocable capability** for its window (scanout, transceiver-I/Q, NIC), with the fabric checking each access against a capability at the point of issue.
This both **deletes translation** and is stronger than switching to an **IOPMP**: the IOPMP would confine DMA, but as a coarse, ambient, per-source-ID region table **disjoint from CHERI** — the device-side PMP, rejected on the identical ground the in-core PMP is (the drop-PMP entry above).
Adopting IOPMP would trade the IOMMU's translation weight for a *second ambient spatial mechanism*; adopting capability-checked DMA *unifies* the device path onto the one mechanism the die already carries, so "who may DMA where" is a capability in the static topology (§7/§8), not a side table — *verify rather than hedge* taken to the device edge, and a device MSI (a store to an interrupt file, §8) confined by the same check rather than an interrupt-remapping table.

**The prior art is proposed and prototyped, not hoped for.**
The Cambridge/SRI position paper **"Defending Direct Memory Access with CHERI Capabilities"** (Markettos, Baldwin, Bukin, Neumann, Moore, Watson; HASP 2020) proposes exactly a capability-configured DMA controller that bounds-checks accesses from malicious peripherals — pluggable and SoC-embedded alike — and contrasts it with the IOMMU's nested-page-table translation.
The **CHERI Alliance "CHERI at SoC Level"** guide (2025) specifies passing **capabilities, tags, and revocation** between CHERI-enabled IP blocks of varying CHERI-awareness, clearing tags on non-capability IP writes — the SoC-integration discipline this needs.
Capability-holding DMA is demonstrated at **CHERIoT** scale (first silicon 2026).
The deletion is sound *only because* the device model is already curated register-slave / transducer / on-die RTL (§4, §12): there is no foreign PCIe bus-master ecosystem issuing raw physical addresses the IOMMU exists to catch.

**The honest counterargument — the two obligations it names.**
Dropping the IOMMU removes the one DMA-side mechanism *disjoint* from CHERI, so device access now rests on CHERI too — the single-mechanism concentration the PMP drop books, extended to the device edge, hedged the same way (CHERI's own verification: RTL ⊑ Sail §18, the Oxford/Google CHERIoT-Ibex result).
Two obligations are genuinely new relative to a translation-IOMMU and are booked in §17: (1) **in-flight-DMA revocation** — a capability held by a running transfer must honour the §8 revocation sweep so time-to-containment stays bounded (a load-barrier / revocation-epoch check, Cornucopia-Reloaded-lineage, or bounded re-authorized windows); (2) a **capability- and tag-carrying fabric** — the interconnect must propagate capabilities, tags, and revocation state to the DMA blocks (new Sail / RTL ⊑ Sail surface, §15/§18).
Application-class capability-DMA at NIC / scanout / radio-I/Q bandwidth is net-new (§18); microcontroller-scale is the existence proof.

**Disposition (adopted; normative in §4, §12, §15).**
The IOMMU is **deleted** and the IOPMP **declined**: device DMA is capability-checked by the fabric, every DMA-capable block is a core-issued capability-operand mover or a delegated-capability-holding streamer, and CHERI becomes the sole spatial mechanism **system-wide** — cores and devices alike.
The platform axiom decides it as ever — *trust is the scarce resource, engineering is free, delete rather than defend* → *verify rather than hedge*: the IOMMU is a second, device-side spatial mechanism (carrying a walker and caches the profile bans in-core), redundant once the fabric carries capabilities, and the IOPMP is the coarse subset of CHERI it is in-core.
**Honest residual (§17):** device access rests on CHERI alone with no IOMMU-disjoint backstop; in-flight-DMA revocation and a capability/tag-carrying fabric are new obligations (Markettos-2020 and the CHERI-at-SoC-Level guide anchor feasibility, Cornucopia-Reloaded the revocation), and application-class capability-DMA is net-new (§18), microcontroller-scale the existence proof.

---

## Delete scalar floating-point — fold all float onto the vector FPU, static rounding

The proposal is to remove the **scalar `F`/`D` floating-point extensions** — the `f0`–`f31` register file, the scalar FP instruction set, and the dynamic rounding-mode CSR — and route **all** floating point through the **RVV floating-point unit every core already carries**.
It is the profile-parsimony move the MMU deletion, the mode collapse, and the PMP drop made, applied to the largest remaining orphaned *datapath* rather than a protection mechanism: the profile is RV64IM**V**, and even the C-class control cores carry VLEN=256 vector (§15), so scalar `F`/`D` is a *second* FP datapath behind a vector FPU that can already do everything it does.

**What is redundant, and what is not.**
The vector FPU performs the same IEEE-754 arithmetic; a "scalar" float is just a single-element (VL=1) vector operation on it.
So the scalar instruction class, the `f`-register file (context-switch state and a fence.t flush-set member), and — decisively — the *scalar* fixed-latency-FPU-including-subnormals timing contract plus the scalar `FDIV`/`FSQRT` constant-time carve-out are all redundant.
That last item is the prize: it is **one of the two floating-point timing crown jewels** (§15), and folding onto the vector unit *deletes* it rather than re-proving it — the contract is stated once, for the one FPU, not twice.
What does **not** vanish is the FP arithmetic itself (adders, multipliers, subnormal handling, divide/sqrt): it lives on the retained vector FPU, which still owes the fixed-latency-including-subnormals contract.
This is a consolidation-and-deletion of the *scalar wrapper*, honestly, not an elimination of floating point.

**Static rounding falls out for free.**
With no scalar FP, the only remaining rounding-mode consumer is vector FP, and mandating **static rounding** (the mode encoded per-instruction, default round-to-nearest-even) deletes the dynamic `frm` CSR — a mutable field that would otherwise context-switch and join the fence.t set — exactly the determinism the profile already imposes on branch prediction and atomics (no hidden mutable state surviving a partition switch).

**The honest counterargument — and why the axiom overrides it.**
Two things are genuinely given up.
(1) **Ubiquity of scalar float.**
Ported userspace (UI layout, coordinate math, general numerics; §12/[userspace-porting.md](userspace-porting.md)) uses scalar float pervasively, and the standard RISC-V `lp64d` ABI passes it in `f` registers; folding it onto VL=1 vector ops means a **soft-float-register ABI** and per-operation `vsetvli`/`vmv` setup.
(2) **A non-standard ISA.**
The application-class `V` extension formally *requires* `F`/`D` (it depends on `Zve64d`, which depends on `D`), so vector-FP-without-scalar-FP is a **fork** of the base ISA, carrying its own Sail surface for the integer-register-to-vector-FP move path.
Both costs land on the axes the platform spends freely — *engineering is free; performance is subordinated* (§1) — and buy down the scarce one: a deleted timing crown jewel, a deleted register file, and deleted rounding-mode state, on a Sail model and toolchain the project already curates from scratch.

**The bet, stated.**
Vector-FP-without-scalar-FP at application scale is uncommon (most RVV cores keep scalar `F`/`D` for exactly the ABI reasons above), so this is a bounded extrapolation like the single-address-space and single-privilege-mode bets — bounded because the vector FPU is the *same* IEEE-754 unit, the fold is a mechanical compiler lowering (VL=1 ops in the `Zfinx`-adjacent idiom of sourcing FP operands outside a scalar-FP register file), and nothing about correctness changes, only where the operands live and what they cost per op.

**Disposition (adopted; normative in §15).**
Scalar `F`/`D`, the `f`-register file, and the dynamic rounding-mode CSR are **removed**; all floating point is vector (VL=1 for scalars), rounding is static, and the ABI is soft-float-register.
The FP timing contract is stated once, for the vector FPU (§15).
The platform axiom decides it as ever — *trust is the scarce resource, engineering is free, delete rather than defend*: a redundant FP datapath and one of the two FP timing crown jewels are deleted for an ABI change and a per-op vector-setup cost the subordinated-performance goal absorbs.
**Honest residual (§17):** floating point rests on the single vector FPU under a non-standard vector-FP-without-scalar-FP profile (a small new Sail surface for the operand-move path, an uncommon configuration at application scale) — offset against the deleted scalar datapath, `f`-register file, scalar FP timing contract, and dynamic rounding-mode state; a net shrink, booked in §17's proof-trust-base accounting.

---

## Mon CHÉRI conditional capabilities — reject the binary-side extension, adopt Write-before-Read as a transparent initialization-tag plane

Where the trilogy above *deletes* mechanisms down to CHERI, this entry weighs *extending* CHERI.
**Mon CHÉRI** (Gülmez/Englund/Mühlberg/Nyman, IEEE S&P '25) adds **conditional permissions** to the capability model — a permission conferred only once a prior operation has occurred (a write, after which read or execute is granted) — tracked by an **operation-specific bound (OB)** recording the sub-range of a capability's bounds a given operation has already covered.
The flagship policy is **Write-before-Read** ("no read of memory that has not been the subject of at least one write"); the paper defines seven such permissions (the Write-before-{Read,Execute} family with their exactly-once "-Only" variants, plus Write-Once, Read-Once, Execute-Once).
It targets the one memory-safety class CHERI leaves open: Microsoft's CHERI-ISA analysis found that ~12% of its assessed vulnerabilities need uninitialized-memory protection that spatial capabilities and revocation-based temporal safety do not provide.
The prototype is a CHERI-Flute64 FPGA softcore plus a CHERI-LLVM toolchain — ~3.5% CoreMark overhead over purecap (~2% area), 100% detection with ~1% false positives on the Juliet CWE-457 suite.
The steer — "implement even a subset; a small part might be transparent to the compiler and run on normal CHERI binaries; write-then-read is a universal requirement" — decomposes, in this document's manner, into three separable questions: (a) the general conditional-permission / operation-bound machinery; (b) Write-before-Read specifically; (c) the *transparent, always-on, stock-binary* reading of it.

**The steelman — four real cards.**
(1) **A genuine gap.**
The platform has concentrated all in-core spatial safety on CHERI and its temporal safety on revocation (§8, the drop-PMP entry above), and uninitialized-memory *use* is the one memory-safety class neither covers — the Tier-2 certificate (§13) proves *spatial + temporal* safety and is silent on initialization.
(2) **The encoding is admission-test-clean.**
Mon CHÉRI keeps the write-progress state *in the capability itself* (16 bits stolen from the top of the cursor), not in shadow memory — so it passes all five parts of the §15 admission test for the same reason the design likes CHERI: the state is the architecturally-visible capability, not hidden per-address metadata surviving a partition switch, and the OB advances only as the direct writeback of an executed store, not as an autonomous walker.
(3) **It extends the one hedge the platform deliberately keeps.**
The CHERI universal contract (Cerise-style, §13) is retained *beneath* the Tier-2 certificate as defense-in-depth; Write-before-Read is the initialization sibling of that spatial backstop.
(4) **It abandons no substrate** — a backward-compatible CHERI-RISC-V extension the bespoke CHERI (§1) could absorb, unlike the belt/EPIC/Wasm targets.

**What is rejected, and what is adopted — the binary encoding versus the property.**
The steer resolves it: *no bespoke CHERI extension on the binary side, but a custom microarchitecture that runs stock CHERI binaries is fine, ideally Coq-verified.*
That line runs exactly between Mon CHÉRI's two halves.
- **The binary-side conditional-capability *encoding* is rejected — it is the bespoke binary extension the platform declines.**
  Mon CHÉRI is **opt-in per capability** (the default disables enforcement; the allocator or compiler must emit a `CSetOpBounds`-family instruction such as `csetwbrbound`), **needs a store-linearization compiler pass** (21% false positives without it, because the operation-bound rides *in* the capability and ordinary codegen spills and duplicates capabilities into stale copies), **assumes sequential writes**, and steals capability-cursor bits — a change to the capability format and to the compiled instruction stream, i.e. special binaries.
  That is precisely what the steer rules out, and it enlarges the CHERI-RISC-V Sail model, the RTL ⊑ Sail refinement, CHERI-CompCert, and the CHERI-TAL soundness metatheorem (non-monotonic permission *regain* against the linear/affine capability discipline).
- **But the *property* separates from the encoding, and the separated form is transparent — this is adopted (§15).**
  Move the write-progress state out of the capability and into an **address-indexed initialization-tag plane** — a sibling of the CHERI validity tag, reset to *uninitialized* by eager-zeroize (`cbo.zero`, §7), set by any ordinary store, checked on data loads — and Write-before-Read runs on **stock CHERI binaries** with **no capability-encoding change, no new instruction the binary emits, and no store-linearization** (any store to the granule discharges its obligation, so correct code never false-faults; the false-positive problem that forced Mon CHÉRI's compiler pass was an artifact of the in-capability encoding).
  It is a custom microarchitecture, not a binary-side change — exactly the deviation the steer permits — and it rides the *existing* validity-tag datapath, so it is cheap in silicon and in proof.
  The compiler-transparent alternative Mon CHÉRI's authors themselves float — a shadow-memory "written" bitmap — is a *separate, hidden* per-address structure; the tag-plane form instead extends the metadata plane CHERI already maintains and reasons about, keeping it architectural state reset by eager-zeroize, not hidden microarchitectural state.
- **The value is scoped by what is already discharged — which is why the mechanism is defense-in-depth, not a universal fault.**
  Disclosure is already the platform's position (eager-zeroize + `Zicboz`, §7/§15); the exploitable *pointer* case is already the validity tag (an uninitialized granule bears no tag) plus the absence of ASLR under the single address space (§7); and uninitialized *use* in trusted and contained code is proven or enforced absent (safe-Rust definite-initialization, verified C, Lustre, §5).
  So the tag plane's marginal guarantee is fail-stop on uninitialized *data* use in `unsafe` blocks and wholly-unverified code — strengthening the hardware universal contract (§13) exactly where hardware is the only guarantee, which is consistent with *verify rather than hedge* (it hedges no verified mechanism, it adds a guarantee for code with no proof), not a breach of it.

**The distilled atom — Write-before-Read, and its verified vehicle is already in the trust base.**
Of the seven conditional permissions, **Write-before-Read is the one non-redundant atom** for this platform: Write-before-Execute and Execute-Only/XOM are already covered by W^X under CHERI monotonicity (no writable-then-executable capability is ever derived, §14), Execute-Once anti-code-reuse by no-runtime-codegen + CFI + CHERI (§13, §14), and Write-Once/Read-Once are niche.
Two facts make the atom unusually cheap to re-home.
First, the store-linearization obligation the paper carries as an LLVM pass is a *linearity* problem, and the paper's own future work observes it is simpler in borrow-checked languages, Rust the prominent example — the platform's contained code *is* safe Rust carrying **CHERI-TAL** linear/affine capability types (below), so the compiler half is largely already discharged.
Second, and decisively, the **Coq-verified vehicle already sits in the trust base**: Georges et al.'s *uninitialized capabilities* (POPL '21) mechanize exactly Write-before-Read in the **Iris/Cerise** capability-machine logic the platform already relies on for its universal contract (§13).
The adopted mechanism re-homes onto that verified lineage — the **address-indexed sibling** of its theorem, proved in the one prover — the same move this document makes elsewhere (adopt the *design*, re-home the *proof* onto Coq: seL4 below, VeriBetrFS in §10), here applied to a capability *extension*.
Mon CHÉRI's own LLVM/Bluespec prototype is unverified and finer-grained (sub-object, stack and heap, FPGA-real); the platform trades that precision for the transparent, verified, tag-plane form.

**Where it ranks.**
It is the **most importable of the "change the ISA" entries** — it abandons no substrate and fuses nothing — and, once the property is decoupled from the binary encoding, it is not merely importable but **imported**: the transparent tag-plane form is the rare CHERI *extension* that costs almost nothing on the scarce axes (one bit on an existing plane, one invariant in the existing prover) while running stock binaries.

**Disposition (adopted in part; normative in §15).**
The **property** — Write-before-Read — is adopted as a **transparent, address-indexed initialization-tag plane** (a sibling of the CHERI validity tag, reset by eager-zeroize), enforced on **stock CHERI binaries** by microarchitecture and verified in the one prover as the address-indexed sibling of the Coq-verified Iris/Cerise uninitialized-capabilities result (§15).
Mon CHÉRI's **binary-side conditional-capability *encoding*** — the per-capability operation-bound, its `CSetOpBounds` instructions, and the store-linearization it forces — is **rejected**: it is the bespoke binary-side CHERI change the platform declines, and its extra precision is not worth special binaries plus the Sail / RTL / toolchain / CHERI-TAL surface.
The other six conditional permissions do not import (already covered by W^X, by no-codegen + CFI, or niche).
**Honest residual (§17):** the tag plane is the one place the profile *adds* a mechanism rather than deleting one — booked as cheap defense-in-depth (granule-granular, heap/static-first, stack precision an optional compiler assist), strengthening the universal contract where hardware is the only guarantee, consistent with *verify rather than hedge*.

---

## Link-layer timing — a fixed-function turnaround sequencer, not a Bluetooth/Wi-Fi controller

The dissolved-modem thesis (§4, §12) puts the whole radio stack in contained software on the pinned V-cores, but one class of deadline is too tight for software under interrupt jitter: the sub-slot *turnaround*, where a device must flip the RX/TX path and be transmitting within a fixed inter-frame gap of the previous packet — the BLE inter-frame space (`T_IFS` = 150 µs ± 2 µs), the 802.11 short interframe space (SIFS = 10/16 µs), the 802.15.4 turnaround (~192 µs).
This is the gap the critique flags — BLE link-layer timing "arguably harder than LTE HARQ" — and it is real: a general-purpose core's interrupt-and-schedule path cannot reliably hit a ±2 µs window, which is exactly why every shipping radio implements this turnaround below the software line.

**Three ways to meet it, and the fork the axiom forces.**
(a) A **Bluetooth/Wi-Fi controller** runs the entire link layer/MAC as firmware on a hidden core — the industry's *FullMAC* — meeting the timing trivially but as precisely the "Wi-Fi/BT controller firmware" §4 bans: an opaque processor with its own DMA, the largest foreign computer the radio architecture exists to delete.
Rejected.
(b) **Pure software on dedicated cores** meets the turnaround by pinning a core and precomputing the response — the Microsoft *Sora* approach (NSDI '09), which used core-dedication and lookahead to hit Wi-Fi SIFS in software.
It keeps everything in the trust structure but spends the tightest real-time budget on the most jitter-sensitive path; it is the critique's "harder than HARQ" horn, and at 150 µs / 16 µs it is fragile.
(c) A **fixed-function timing sequencer in the register-slave transceiver datapath** (§15) — a hardware packet-end event starting a fixed timer that drives the RX/TX switch and gates a software-prepared buffer out at the exact deadline, with no instruction fetch, no writable program, no firmware, and no protocol decision.
This is the *SoftMAC / split-MAC* partition — time-critical turnaround in fixed hardware, the link layer and everything above it in software — and it is what the platform adopts.

**The line between (a) and (c) is the "no foreign computers" line itself.**
A controller is a processor running firmware; the sequencer is a timer plus a small finite state machine, fully described in RTL, Sail-modeled, capability-gated — the FEC-unit / digital-front-end category, "matter, not software," the same tolerance the design already extends to the DFE, the FEC blocks, and the I/Q-streaming DMA.
It passes the five-part §15 admission test the way those do: deterministic; a fixed 150 µs constant independent of packet contents, so no data-timing channel; bounded FSM/timer state reset per event, architectural not hidden; a register slave with no authority beyond its capability-bounded DMA window; and its autonomy is the scheduled-DMA kind (a timer firing a pre-designated buffer), not the address-dependent memory walker admission-test 5 bans.

**Prior art — the partition is standard; the firmware-free realization is the part that is imported.**
The SoftMAC/FullMAC split is the mainstream Wi-Fi architecture: Linux's `mac80211` SoftMAC stack runs the timing-critical MAC (ACK/SIFS/backoff) in hardware and the management MAC in host software — exactly this decomposition.
On the exact protocol, **Nordic's nRF radios with Zephyr's open Link Layer** meet BLE `T_IFS` with a hardware *tIFS timer* (dedicated capture/compare registers) while the LL state machine, L2CAP, and GATT run in software.
The closest match to the *no-firmware* form the platform needs is **openwifi** (open FPGA RTL, already the §18 radio start-from): its "DCF low-MAC layer in FPGA" meets the 10 µs SIFS ACK in Verilog, not on a core — the firmware-free, open-RTL existence proof for exactly the fixed-function turnaround block, harvestable under the open-RTL mandate.
None of these is formally verified or Sail-modeled; consistent with the platform's thesis, the split is off-the-shelf and the *verified, capability-gated, firmware-free* realization is the contribution.

**Disposition (adopted; normative in §12, §15).**
The sub-slot turnaround (BLE `T_IFS`, 802.11 SIFS, 802.15.4) is met by a fixed-function timing sequencer inside the register-slave transceiver datapath — a hardware timer + FSM, no instruction fetch, no firmware, one more fixed-latency entry in the timing-annotated Sail model (§11) riding the RTL ⊑ Sail refinement.
Everything with protocol semantics — connection-event/slot scheduling (a §11 software hard task), channel selection, framing/whitening/CRC, link-layer encryption via the crypto core, and the link-layer state machine as a Lustre control plane — stays in software (§12).
A Bluetooth/Wi-Fi *controller* (FullMAC firmware) is rejected as a §4 foreign computer; pure-software turnaround (Sora-style) is rejected as spending the tightest real-time budget on the most jitter-sensitive path.
This is the same "hardness at the boundary, patchable software above it" rule the regulatory layering (§12) applies to the emission envelope, applied to timing.
**Honest residual (§17):** the sequencer is a small fixed-function block folded into the transceiver datapath already in the Sail model (§17 "grows the Sail model") — no firmware, no new trust axiom, its correctness and its 150 µs latency riding the existing transceiver RTL ⊑ Sail and WCET obligations; no new residual bullet, since the block is within the register-slave-datapath category the radio subsystem already books.

**Generalization — the same partition is the standing sensor-front-end doctrine (§12, §15).**
The split-MAC line drawn here is not radio-specific; it is the platform's rule for every transducer.
The analog front-end plus a fixed-cadence scan/sample sequencer stays *matter* — a register-slave AFE streaming raw samples over a capability-bounded DMA window, no per-sensor DSP core and no firmware — while all signal processing dissolves onto the host V-cores.
Capacitive touch (raw capacitance → host touch DSP), the audio front-end (microphone/speaker converters → host filtering, echo-cancellation, and beamforming), the image sensor (raw Bayer → the software ISP), IMU/motion (raw reads → host fusion), and the fingerprint/biometric AFE (raw frames → the host matcher) are all instances.
The one honesty the radio case does not carry: sensor front-ends have no off-the-shelf firmware-free part — commodity touch, audio, and image controllers co-design the AFE with tuned DSP firmware — so the raw-AFE silicon and its host-side DSP are a genuine net-new co-design, booked in §17; that booking is the resolution of the capacitive-touch gap the critique flags.

---

## seL4 vs. CertiKOS — re-examined; seL4's *design* retained, re-proved end-to-end in Coq

The §5/§7 choice of a **CertiKOS-lineage** kernel proof over **seL4** rested, as written, on *one prover, Coq*.
The first pass (bullets below, kept as the reasoning trail) concluded "no pure-win substitution — a trade of the single-checker TCB for maturity."
Promoting seL4's 2024 program — a verified **multikernel** on multicore, and **CHERI-seL4** — to in-scope, and spending the platform's own axiom (*engineering is free; trust is the scarce resource*), overturns that conclusion.
A **third option dominates both**: keep seL4's *design* and re-prove it **end-to-end in Coq**, compiled through **CompCert/SECOMP**.

- **Direction of travel — the "simplification" is seL4's own, not CertiKOS's.** seL4 remains on **Isabelle/HOL** (l4v), with no migration to Coq and none to CertiKOS's method.
  CertiKOS's distinctive contribution is the *opposite* of a simplification: **Certified Concurrent Abstraction Layers** (Coq, CompCertX) verifying a *fine-grained concurrent, shared-memory* kernel (mC2). seL4's multicore roadmap is the **multikernel** — one verified single-core instance per core, **zero shared kernel state**, inter-kernel IPIs (seL4 RFC-0170), concurrency pushed to user level *explicitly "for better verification."*
  That share-nothing, per-core-sequential model **is already this spec's §7 architecture** (capability/memory lineage: Barrelfish → seL4).
  **CertiKOS's one distinctive asset — proven shared-memory concurrency — is therefore dead weight here:** the multikernel forbids the shared mutable kernel state it verifies.

- **The spec already *is* seL4 in all but the prover.**
  Untyped memory / zero post-boot kernel allocation (§7), synchronous endpoints + notifications (§7), derivation-tree (CDT) revocation (§8), and the non-interference theorem (§8) are seL4's model in every particular; "CertiKOS" named only the **Coq proof engine**.
  "CertiKOS-lineage kernel proof" was always shorthand for *verify this (seL4) design in Coq* — a label on the method, not a second kernel.
  The coherent artifact is a Coq proof **of the seL4 design already written down here**, not an import of CertiKOS's different kernel.

- **The two decisive objections bind the prover, not the design — and dissolve on re-proof.**
  (1) **Trust-base fragmentation:** *adopting* seL4's Isabelle proof puts **Isabelle *and* Coq** — two proof checkers — permanently in a TCB whose §6 story is one self-verifying checker; a first-order regression.
  (2) **Compilation seam:** seL4's shipped binary-correctness is a *different* toolchain (decompilation + SMT translation validation), not the §5–§6 CompCert/SECOMP/Islaris/Cerise path.
  Both are artifacts of *inheriting seL4's existing proof*; **redoing the proof in Coq on CompCert/SECOMP erases the first and inverts the second into native composition.**

- **CHERI is a wash, with an implementation to verify against.**
  CHERI-seL4 builds purecap (Morello + CHERI-RISC-V, sel4test/sel4bench passing) but is **not verified** — CHERI serves *user-level* safety, and seL4's existing functional-correctness proof does not extend to the capability hardware.
  The design mandates a **verified purecap kernel** (§7), so the CHERI-C mechanization gap (§7/§17) is net-new under *either* kernel.
  Promoting the 2024 CHERI-seL4 work in-scope supplies the purecap *implementation and bring-up* to verify against; it does not supply the proof.

**The third option, stated.
Methodology is portable; maturity is not.**
The design chose CertiKOS for a *portable* property — a Coq proof method (deep specifications, abstraction layers, CompCertX-style verified compilation) — at the price of an *intrinsic* one: a mature, deployed, exhaustively specified, independently reviewed kernel design.
With labor priced at zero, the move is forced: **carry the portable property to the design with the better intrinsic property.**
Apply Coq/CompCert/SECOMP to seL4's design rather than accept CertiKOS's thinner, concurrency-oriented, here-unused kernel for the sake of a method that travels.
By the platform's *own* decision criterion — smallest trusted set, deepest proof — the result wins on both axes: an identical single-prover trust base (Coq), over a design carrying the broader proved-property set (functional correctness + integrity + availability + confidentiality/NI + binary-level) and the longer-scrutinized specification — and §5 calls specifications "the crown jewels," of which seL4's has had the most independent eyes of any kernel spec in existence.

**The honest residual — freshness, not trust.**
What transfers from seL4's maturity is the **design, ABI, C implementation, abstract specification, and the in-scope multikernel/CHERI engineering** — *not the proof.*
A Coq re-verification is a **fresh** proof and spec-mechanization, as unbattle-tested as CertiKOS's, and a faithful re-proof may pull the code marginally off mainline seL4 (spending a sliver of the very battle-testing invoked).
The search for an existing Coq artifact to inherit comes back empty: seL4 is **Isabelle-only, and actively so** — the `l4v` proof and every current extension (MCS, multicore, the seL4 Core Platform) stay in Isabelle/HOL — so the route is genuinely greenfield in Coq: design, spec, and C carry across, but there is no proof to port.
The freshness that bites is therefore **not** the authored refinement proofs, which fail *loudly* when they are wrong, but the **silent** kind — a mis-transcribed specification verifies perfectly (§5's crown-jewel failure mode).
Bound it by transcribing the spec **mechanically, not by hand**: seL4's executable model is Haskell, and **hs-to-coq** (Gallina from Haskell) carries the scrutinized prototype into Coq without a paraphrase pass, so the artifact that earned the independent eyes is *preserved*, not re-typed; only the abstract spec and the refinement are authored fresh.
That fresh abstract spec is not unmoored: it is **disciplined by the refinement against the hs-to-coq executable model** — any *divergence* fails the proof loudly, so the sole silent residual is a *too-weak-but-faithful* abstract spec, the **generic crown-jewel risk seL4 already carries in Isabelle** (§5), not one the Coq move introduces.
And the two-checker alternative's edge is narrower than it looks: the proofs it would let you *inherit* do **not** cover this platform's purecap-CHERI kernel or the multikernel configuration — both unverified in seL4 today — so that proof mass is **fresh under either option**, and what the maturity actually buys is the *design and specification*, not a discharged proof of the configuration shipped here.
That is a real cost — but a *labor-and-freshness* cost, the class the engineering-free axiom exists to absorb, not a *trust* cost: the trusted set does not grow.
The claim is thus conditional and honest — **superior iff (a) engineering is free and (b) seL4's 2024 completion is in-scope**, both stipulated.

**Disposition:** adopt seL4's **design**, re-proved **end-to-end in Coq** and compiled via **CompCert/SECOMP** (§5, §7); **CertiKOS is demoted from kernel to proof-method lineage** — deep specifications, certified abstraction layers, CompCertX-style verified compilation — supplying the *how* while seL4 supplies the *what*.
What transfers from that lineage is the abstraction-layer discipline, the deep-specification method, CompCertX-style verified compilation, and the generic lower-layer proofs (physical-memory management — the single-address-space design carries no paging layer) any kernel needs — **not** CCAL's *concurrency* machinery, which the share-nothing multikernel (above) makes dead weight; for a per-core *sequential* kernel, plain **VST** (sequential separation logic over CompCert) is the more parsimonious closing logic.
The make-or-break subproof, never yet done in Coq for an seL4-class capability model, is **CDT revocation** (the hardest part of the l4v corpus) — so it is the piece to attempt *first*, the early kill-switch on the route.
**Importing seL4's Isabelle proof wholesale stays rejected** (the two-prover TCB).
The earlier "no pure-win" verdict is **superseded**: it held only under the unstated assumption of *inheriting* seL4's proof; the engineering-free axiom licenses lifting that assumption, and the Coq-re-proved seL4 then dominates.

---

## Kernel-in-gateware — the benefit needs the whole kernel, the safety only a frozen subset; the one separable primitive worth fusing is already CHERI

The proposal is to express the capability/endpoint/scheduler machine **directly in a formal-semantics HDL** (Kôika/Kami) rather than as Machine-mode software, so the kernel's correctness proof folds into the **RTL ⊑ Sail** refinement already in scope (§18) and the Machine-mode software TCB on application cores collapses toward zero.
Its strongest premise is real and already in the spec: the kernel ABI is *"on the order of a dozen invocations… frozen with the proof"* (§7), and a per-core multikernel instance is share-nothing, sequential, event-driven, with **zero post-boot allocation** (§7) — architecturally a synthesizable object.
It is best read as the **terminus of the kernel-shrinking directions** — the **table-driven cyclic executive in place of MCS** (§7, §11) atop the **single-address-space CHERI isolation that deletes the VM subsystem** (the MMU-deletion entry above), the two base simplifications collapsing the kernel to exactly that frozen state machine.

**The steelman, and the prior art.**
RTOS primitives *are* synthesizable and deterministic: the RealFast **RTU / Sierra** line (the Mälardalen real-time-unit work) put scheduling, IPC, semaphores, flags, and timers into VHDL behind memory-mapped registers, reporting large system-call speedups and, tellingly, **timing independent of waiter count** — the determinism dividend a hardware control plane offers over a software one.
If the kernel spec were genuinely frozen forever, fusing it would merge the kernel proof into the hardware refinement at no new prover.

**Why it fails as a base move — five load-bearing objections, and narrowing to "the most-proven subset of the most battle-tested spec" sharpens two of them rather than escaping them.**
- **The benefit/safety scissor — decisive.**
  The payoff (software TCB → 0) requires fusing the **whole** kernel; the part that is *safe* to fuse — proven **and** frozen — is only a **subset**.
  Fuse the subset and the software kernel remnant (cyclic-executive scheduling, multikernel coordination, capability management, the powerbox/re-grant paths §8/§12) stays in Machine mode, so the TCB does not collapse — it is **split across a hardware/software boundary with a new verified seam added**.
  This is precisely the RTU pattern: RTU keeps its host RTOS (µC/OS-II) in software and offloads hot paths, so even the canonical hardware-microkernel product never collapsed the software TCB.
  Partial fusion *adds* surface; only whole fusion pays off, and whole fusion needs the whole spec frozen.
- **The most-proven subset is not the kernel this platform runs.** seL4's deepest guarantees hold for a **unicore, non-MCS, static-partition** configuration: functional correctness there, and the **non-interference proof only for non-MCS, unicore, static-partition configurations** — the least-maintained layer of l4v.
  This platform is a **multikernel** on multicore, **purecap CHERI-C** — and although dropping MCS for a static cyclic executive (§7) moves the *scheduling* dimension back toward the non-MCS static-partition one seL4's proof covers, the multikernel and purecap-CHERI dimensions keep its non-interference a *fresh* theorem wearing an old name.
  "Fuse the proven subset" therefore fuses a kernel you do not deploy; the configuration you *do* deploy is the unfrozen one.
- **Pedigree does not transfer across the prover or the transcription.** seL4's battle-testing is a property of the **Isabelle** proof, the C implementation, and fifteen years of deployment; the design is Isabelle-only and greenfield in Coq (seL4 vs. CertiKOS, above).
  Fusing to Kôika produces a **new** artifact — RTL — whose correctness is a **new** Coq proof (RTL ⊑ a fresh Coq transcription of the spec), riding the **least-built arrow in the whole stack** (RTL ⊑ Sail, §18).
  The independent eyes were on the Isabelle artifact, not the gateware, so fusion inherits the *design* and re-proves *fresh* on the hardest tooling — strictly worse than the software re-proof, which at least rides the more-mature CompCert/VST path.
- **The radio/MTTR self-defeat softens under narrowing but survives.**
  Restricting to the most-scrutinized subset genuinely lowers P(functional defect) — the crown-jewel doctrine (§5) working as designed.
  But the defect classes fusion forecloses response to are **uncorrelated with the functional proof**: **timing channels** (outside seL4's functional *and* non-interference proofs — time protection is a separate, still-maturing, hardware-dependent effort), hardware-model drift, assumption-boundary violations, and errata interactions.
  Scrutiny buys none of those down, and fusion concentrates its cost exactly there — on the **highest-privilege layer**, where the spec's own rule bites hardest: *"a fully fused radio could never patch its most-attacked surface"* (§12), so patch latency becomes fab latency.
  Lower P(defect) × maximal-severity-and-zero-remediation is still a bad tail trade.
- **There is nothing left to accelerate.**
  RTU's motivation is performance, the currency this platform spends freely (performance deliberately subordinated to security, §2).
  And the overhead it removes is already gone: the **table-driven cyclic executive** (the base scheduler, §7) makes the schedule a compile-time constant (no dynamic decision to offload), **SPSC single-writer rings** (§12) replace the semaphore/flag mailbox, the M-mode timer (`mtimecmp`) gives deterministic timers, and the §11 WCET tables already assume fixed latency.
  RTU accelerates the *dynamism* out of a dynamic RTOS; this kernel has the dynamism designed out — so even the accelerator reading buys nothing.

**The distilled atom — already banked, following the belt→spiller / EPIC→NaR discipline.**
The non-redundant idea is *a single genuinely-frozen, cleanly-separable primitive as a verified hardware block*, and it is **already present**: the highest-value such primitive — **spatial capability enforcement** (bounds, tags, monotonicity) — is in gateware as **CHERI**, with its own Sail semantics and RTL ⊑ Sail obligation (§1, §18), reached **not** by fusing seL4 but by a hardware capability model.
A verified **Kôika scheduler/timer block** is admissible *in principle* (a cyclic-executive table lookup, a windowed timer) but is far too small to deliver the proposal's TCB-collapse and is orthogonal to the capability/endpoint machine it actually names.
So the separable primitive worth fusing is already fused; the rest is **control-plane sequencing best kept patchable, in software, in the same prover as everything else**.

**Where it ranks.**
Unlike the belt, EPIC, and Wasm targets, kernel-in-gateware does **not** abandon the RISC-V substrate — it keeps the substrate and moves the *kernel* into it — so it is off that ranking.
It is the terminus of the kernel-shrink path (the adopted cyclic executive ⋈ the adopted single-address-space MMU-deletion, above, which subsumes the frozen-page-table step), coherent only **after** those simplifications land — as the base has them — **and** the seL4-in-Coq specification and proof are complete and frozen — a gen-2 direction contingent on spec-freeze, in the same "iff the binding constraint appears" slot as the belt, not a base move.

**Disposition:** the fusion of the **capability/endpoint/scheduler machine** is **rejected as a base direction** — the benefit needs the whole kernel while the proven-and-frozen safety covers only a subset (the scissor), the proven subset is not this platform's multikernel/purecap configuration, the maturity lives in Isabelle and does not transfer to a fresh Coq → Kôika → RTL artifact on the least-built arrow, and fusion forecloses remediation of the timing/assumption/errata defect classes the functional proof never covered, on the most-privileged layer.
It is logged as a **spec-freeze-contingent gen-2 direction** (terminus of the adopted cyclic-executive and MMU-deletion simplifications, above).
The one distilled atom — a verified hardware block for a genuinely-frozen separable primitive — is **already banked as CHERI** (§1); a verified **Kôika scheduler/timer** block is admissible in principle but too small to be the proposal, and stays non-normative.
The **RealFast RTU / Sierra** line is a functional reference that RTOS-in-gates is real and deterministic, **not** an admissible artifact — unverified VHDL, a dynamic-priority/semaphore shape the §15 admission test deletes, and an accelerator that keeps the software kernel rather than replacing it.
Non-normative; no spec-body change.

---

## Crypto verification depth — implementation-correct is not reduction-secure

Functional correctness plus constant-time (Fiat-Crypto + libcrux/HACL\*, §5) cover two of the three properties a verified cryptosystem needs and leave the third unstated — the reverse of this spec's "deepest proof over the smallest trusted set" criterion.

- **The missing layer.**
  Functional correctness says the code computes ML-KEM; constant-time says it leaks nothing through timing.
  **Neither says the scheme is secure.**
  IND-CCA (KEM) and EUF-CMA (signatures) are *game-based* properties established by **reduction** to a hardness assumption — proofs about the *scheme*, not the *code*.
  Proving the implementation while assuming the cryptography inverts the priority: the most consequential property — that the primitive is actually hard to break — was the one left unproven.
- **The widening must be minimized, not merely accepted.**
  §5 elsewhere *minimizes* F\*/Z3 by construction, picking **Narcissus over EverParse** for parsers purely on trust-base uniformity.
  Merely accepting the crypto widening — "ports don't exist yet" — would leave the largest attacker-facing trust widening un-attacked.

The tools, each run through the §5 trust-base test, close both gaps:

- **CompCert-CT + CryptOpt translation validation (layers 1–2).**
  Constant-time is carried by **CompCert-CT preservation** on the verified-C path — one verified compiler, the same Coq prover — replacing "trust a C compiler to preserve constant-time" with a *mechanized* preservation theorem.
  The performance-critical **field-arithmetic kernels** are then recovered by **CryptOpt**: an *untrusted* randomized-search superoptimizer emits assembly faster than GCC/Clang at top optimization (at times beating hand-written asm), admitted by a **Coq-verified program-equivalence checker** back to its **Fiat-Crypto** functional spec — so the trusted artifact is a *small verified checker*, not a second optimizing backend, and hand-assembly-grade speed and Coq-checkable correctness are both had at **zero trust-base fragmentation** (the crypto instantiation of the artifact-not-pedigree / CHERI-TAL discipline below).
  Costs, and why it is a *deferrable* recovery rather than a hard dependency: **CryptOpt targets x86-64 today**, so the CHERI-RISC-V retarget of the equivalence checker over the one Sail model is a §18 workstream beside CHERI-CompCert — but the crypto core is already correct *and* constant-time on CompCert-CT alone (Fiat-Crypto's field arithmetic is straight-line), so this only buys back speed on the hot path and can be deferred.
  Two honest asterisks: CryptOpt's headline results come from randomized search **benchmarked on real silicon**, which does not exist here yet — the fitness function must ride the timing-annotated Sail model or the FPGA (§11), though the in-order fixed-latency profile (§15) makes that cost model *transparent* rather than the opaque superscalar it fights on x86; and its scope is *straight-line field arithmetic*, so control-flow-heavy primitives (Keccak, AES, ChaCha, the ML-KEM/ML-DSA NTT and samplers) stay on the CompCert-CT verified-C path — acceptable with performance subordinated.
- **SSProve / FCF (layer 3).**
  Coq-native game-based reduction frameworks.
  Choosing them for the security proofs is the **identical decision** §5 made choosing Narcissus over EverParse: the reduction rides the one Coq kernel (§6) at **zero new trust base**.
  This is the spec-coherent home for the missing layer.
- **EasyCrypt (layer 3, mature complement).**
  The standard game-based prover and the one carrying the **formosa-crypto** ML-KEM/ML-DSA reductions — the fastest path to a *finished* proof.
  But it discharges via **Why3/SMT**, a trust base distinct from Coq; by this spec's own logic it is a widening of the same character as the libcrux/HACL\* F\*/Z3 one — **adopted as pragmatic interim assurance, SSProve/FCF the destination.**

**Disposition (adopted; normative in §5).**
Crypto assurance becomes **three composed layers** — functional correctness (Fiat-Crypto; libcrux/HACL\* interim) ⋈ constant-time (CompCert-CT preservation, with CryptOpt-checked field-arithmetic kernels) ⋈ reduction-level security (SSProve/FCF Coq-native, EasyCrypt mature complement) — joined at each primitive's functional specification, which joins the crown-jewel spec list.
The platform axiom decides the toolchain exactly as it did for seL4: **methodology is portable, maturity is not** — carry the Coq-native property (CompCert-CT preservation, CryptOpt equivalence-checking to Fiat-Crypto, SSProve/FCF) to the mature artifacts (formosa-crypto, Fiat-Crypto/CryptOpt), spending engineering to shrink the trusted set.
**Honest residual (§17):** a reduction *isolates and names* the hardness assumptions (MLWE/MSIS; ECDLP/CDH) but cannot prove them — the irreducible cryptographic axiom; the implementation ⋈ reduction join is a new seam at the functional spec; EasyCrypt-borne reductions carry an SMT base until restated Coq-native; and scheme-level IND-CCA/EUF-CMA is still below protocol-level security (TLS/AKA), a further layer.
What this buys is the deepest-available crypto proof — from "correct, constant-time code for a scheme we *assume* is secure" to "the scheme is IND-CCA/EUF-CMA under a named, minimal hardness assumption, implemented by constant-time code a verified compiler preserves and a verified checker admits" — with the residual pushed down to conjectures no proof system can discharge.

---

## Sound WCET derivation — the analyzer the timing discipline was built for

§11 checks *schedulability given WCET numbers* — for the static cyclic executive an interval-arithmetic check (§7), not Prosa-style response-time analysis — but on its own names **no vehicle to derive those numbers soundly** — the whole temporal-admission edifice (OPP/mode selection, TDM NoC schedule, watchdog windows) and much of the §17 timing-channel argument rested on WCET inputs a wrong value silently falsifies.
Sound, mechanized WCET is barely a field: **aiT (AbsInt)** is the commercial gold standard but unverified, and there is no widely-used Coq-native WCET analyzer.
The irony the gap sharpens: the design's **in-order + static-only-prediction + fixed-latency** posture exists precisely to make WCET tractable, yet the tool computing it would otherwise go unnamed.

- **The layer decomposes exactly as RTL ⊑ Sail does — a functional part ⋈ a hyperproperty part.**
  WCET analysis is classically two halves: a **low-level micro-architectural model** (per-basic-block timing — aiT's abstract interpretation over pipeline and cache state) and a **high-level path analysis** (loop bounds + IPET over the CFG).
  On this platform the two halves land in two *already-present* layers, so almost nothing is net-new theory.
- **The low-level model is not a new artifact — it is the timing-annotated Sail model (§15).**
  The timing discipline the profile adopted for other reasons — in-order issue, static-only prediction (no predictor-state variance), fixed-latency DIV/FPU/AMO, Ztso, cache/DRAM/NoC partitioning, TDM NoC, WCET-exact scratchpads, deterministic profile-guided layout (§10) — *collapses* the low-level model from aiT's pipeline-and-cache abstract interpretation to a **per-(class, OPP) latency table** plus reproducible cache/fetch/memory terms, sound to the metal by RTL ⊑ Sail (Kami/Kôika).
  The non-speculative posture is itself a WCET-soundness argument.
- **The high-level model is a Coq-verified IPET estimator** (Blazy/Pichardie/Maroneze/Puaut lineage, on CompCert) — the existence proof that a Coq-native WCET analyzer *does* exist.
  Its ILP solution is a certificate, so the LP solver is untrusted evidence-producing machinery, and the whole estimator rides the one Coq prover alongside the §11 interval-arithmetic schedulability check at zero new trust base.
- **Measurement-based / probabilistic WCET (MBPTA/EVT) — rejected as the bound.**
  Extreme-value-theory tail estimates give a *probabilistic* bound; that is a statistic, not a theorem — the same disposition as MTE's ~93% (§15), antithetical to the proof-based determinism (G3/G4).
  Admissible only as an out-of-band cross-check that flags a wrong timing annotation, never as the admitted WCET.

**Disposition (adopted; normative in §5, §11).**
Name the layer, split it functional ⋈ hyperproperty like RTL ⊑ Sail, put the low-level half *inside* the timing-annotated Sail model (discharged by the RTL ⊑ Sail proof already in scope) and the high-level half in a Coq-verified IPET estimator emitting FPCC WCET certificates.
**aiT** is the unverified complement; **MBPTA** an out-of-band cross-check only.
The platform axiom decides the toolchain as ever — *methodology is portable, maturity is not*: carry the Coq-native property to the verified-IPET artifact and the timing-annotated model, spending engineering to keep WCET on the single prover.
**Honest residual (§17):** WCET is only as sound as the timing-annotated model's latency magnitudes (crown-jewel specs) and inherits the RTL ⊑ Sail residual — no sound bound before that least-built arrow closes — while composability across partitions rests on the §15 isolation non-interference the timing-channel story already needs.

---

## Binary-level constant-time verification — CT as a property of the artifact, not its pedigree

Establishing **constant-time (CT)** by **preservation** alone — CompCert-CT-class for the verified-C path, the crypto core included — carries CT from a source-level proof through a *verified compiler* and therefore reaches only binaries built that way.
The FPCC discipline's own principle is *"verification is a property of the artifact, not its pedigree"* (§5); preservation-only CT is the one place that principle goes unmet, remaining a fact about **which compiler produced the binary**.

- **The uncovered set is not exotic — it is most secret-touching code.**
  Two paths carry no verified compiler: the FPCC **Islaris "no verified compiler in the loop"** path (§5), and — the larger one — **every Tier-1/2 binary**, because the certifying userspace toolchain (§5, §13) emits a *memory-safety* certificate but preserves nothing about timing.
  A key-handling server (the radio key hierarchy, §12) or a PIN-handling app compiled by that toolchain gets memory-safety PCC and **no CT**.
  This is the exact shape of the gap the memory-safety certificate already avoids (§13) — trusted-by-pedigree where it should be proven-on-artifact — one property later.
- **Artifact-level CT decomposes as RTL ⊑ Sail and WCET do: functional ⋈ hyperproperty.**
  Constant-time is a **2-safety hyperproperty** (it relates two executions differing only in secrets), which a *functional* program logic does not carry.
  So the bare Islaris/Iris-over-Sail refinement that discharges functional/safety obligations cannot state CT; it must be extended with a **relational** layer.
- **The Coq-native closing vehicle — a relational program logic over the leakage-annotated Sail model.**
  Self-composition / relational-Hoare reasoning (ReLoC-in-Iris lineage) over the Sail semantics *instrumented with the §15 `Zkt`/`Zvkt` leakage model* proves the leakage trace (load addresses, branch conditions, variable-latency operands) independent of secrets, **at binary level, in the one Coq prover** — the binary-level sibling of the source-level CompCert-CT proof, and the vehicle that also discharges CT for the off-path CryptOpt field-arithmetic kernels.
  It emits an FPCC **constant-time certificate** the §6 checker validates at zero new trust base.
- **Binsec/Rel — the better-fit mature tool, run through the §5 trust-base test.**
  Binsec/Rel does exactly the binary-level job: **relational symbolic execution for constant-time and secret-erasure, directly on the binary against a leakage model**, and it scales to production crypto (BearSSL, OpenSSL, HACL\*, libsodium — finding real violations).
  It is the better-fit tool for this path because the FPCC statement is *binary-level against the Sail model* and Binsec/Rel is binary-level.
  But it is **not Coq** (OCaml + SMT) and is **path-bounded** symbolic execution — so, exactly like **riscv-formal BMC** and **aiT**, it is adopted as the **unverified complement / bring-up gate**, bounded evidence and untrusted evidence-producing machinery, with the relational-Sail-logic certificate the unbounded close.

---

## CHERI-TAL admission — type-check the artifact where a type system suffices, prove it where it does not

The proposal is to replace the bespoke per-property certificate formats with a **typed assembly language (TAL) for RV64+CHERI**: Tier-2 admission becomes **type-checking annotated binaries**, compilers **emit typing derivations rather than proof terms**, the on-device checker shrinks to a decidable type-checker, and the certifying-compiler workstream (§18) collapses to *"target the TAL."*
This is the **Necula → Morrisett arc** — proof-carrying code narrowed to a type discipline (TALx86, then foundational TAL) — and it is the proposed structural fix to the two admission contradictions the spec still carries: the checker-size claim (a ~10³-line *CIC term* checker does not exist — MetaCoq's is tens of kLoC and axiomatizes guard/termination) and the pedigree seam (§5 calls verification a property of the artifact yet mandates the build path).
It lands unusually cleanly here because **CHERI already discharges spatial safety in hardware**, so the type system need not encode bounds proofs — the capability *is* the bound.

**The decomposition — and why the whole certificate scheme does not collapse into types.**
The assurance obligations split along a line this document already draws three times (RTL ⊑ Sail, WCET, CT — each a *functional ⋈ hyperproperty* split):
- The **type-level, 1-safety** obligations — memory safety (temporal + spatial), control-flow integrity, no-runtime-codegen (W^X, §14), ABI/type conformance — are exactly what a TAL type system *decides*.
  These are the whole of Tier-2 and the structural half of Tier-1.
- The **deep** obligations — Tier-0 functional refinement (the binary refines the seL4 abstract spec), whole-graph non-interference (§8), crypto **reduction** security (IND-CCA/EUF-CMA, §5), **constant-time** (2-safety, §5), **WCET** (quantitative, §5), filesystem linearizability + liveness (§10) — are **not typing judgments**.
  No decidable type system states "this binary refines the abstract kernel" or "leakage is secret-independent"; those need a full higher-order logic and a proof term.

So the TAL does not *replace* the certificate scheme — it **stratifies** it, taking the tier where a type system is complete and leaving the tier where only a proof will do.
This is the crypto/WCET/CT move run in reverse: those dispositions showed the *hyperproperties* need more than a functional logic; the TAL shows the *type-level* properties need less than a proof kernel.

**What CHERI buys the type system.**
TALx86 had to encode array-bounds and initialization proofs into its types because x86 had no hardware notion of a bound; on a purecap machine the bound, the tag, and monotonicity are architectural, so the CHERI-TAL types shrink to the *residual* CHERI does not enforce at runtime — **temporal** safety (linear/affine capability types; a revocation-coloured heap in the CHERIoT lineage) and **typed control flow** (well-typed jump targets *are* CFI).
And that residual is precisely what safe Rust's ownership discipline already establishes at source (§5): the TAL is the vehicle that *carries those source types down to the binary as a checkable derivation*, turning §5's "the compiler preserves and certifies rather than re-discovers" from a promise into a concrete artifact format — the memory-safety analog of CompCert-CT carrying constant-time to the metal.

- **It fixes the checker-size contradiction — by splitting the checker, not by shrinking a CIC checker.**
  A TAL type-checker is decidable, syntactic, obviously terminating (no guard/termination side-condition to axiomatize), and genuinely on the order of 10³ lines — so the **on-device admission checker** that runs on every install and sits in the boot TCB *is* that type-checker, and the ~10³-line claim, false for a CIC term checker, is **true for this one**.
  The full **CIC proof kernel** (MetaCoq-lineage, honestly tens of kLoC) does not vanish — it validates the deep Tier-0/hyperproperty proofs — but it moves to where those proofs actually live: **release-time, over the fixed base-image TCB**, its result bound into the signed measured-boot root (§9), not a per-install on-device cost.
  "Checking is cheap and local" becomes *literally true* for the TAL admission path and is **honestly retracted** for Tier-0 (an seL4-scale refinement is machine-hours to check).
  Both horns the contradiction offered — "a genuinely tiny logic" and "a larger checker named as the axiom" — are taken, each in its proper tier.
- **It fixes the pedigree contradiction — admission gates on the derivation, not the producer.**
  Once the certificate *is* a typing derivation the checker re-checks, **any** producer of a well-typed CHERI-TAL binary is admissible by definition; the certifying Rust→CHERI compiler (§18) becomes the *reference producer*, not a gate.
  The "mandatory build path" language conflated "we ship one reference toolchain" with "only its output is admitted" — the TAL drops the second, making admission genuinely language- and pedigree-agnostic (§5), while the hardware universal contract (Cerise, §13) stays beneath as defense-in-depth against a checker or TAL-soundness error.
- **The one new axiom is the TAL's soundness metatheorem — a crown jewel, paid once.**
  Type-checking is only as sound as the theorem *"well-typed CHERI-TAL ⇒ the safety properties hold over the Sail model"* — a foundational-TAL syntactic-soundness proof (WasmCert-Coq / RustBelt lineage), authored once in Coq against the §15 model.
  It joins the crown-jewel specs (§5): a mis-stated typing rule admits an unsafe binary that type-checks perfectly.
  But it is a *smaller and more scrutable* axiom than "a hand-built ~10³-line CIC checker is correct," which is the trade the contradiction was pushing for.

**Prior art, and where it ranks.**
The lineage is real and mechanized — Necula's PCC, Morrisett's TALx86, Appel's foundational PCC, Crary's foundational TAL, and on the memory-safety-type side RustBelt (Iris) and WasmCert-Coq (mechanized type soundness) — so nothing here gambles on the *type-soundness* half; the net-new work is the CHERI-RISC-V *instantiation* (the temporal-safety type discipline over capabilities) and the compiler emitting derivations, which is a **refactor of the §18 certifying-compiler deliverable, not a new one** — its certificate format changes from ad-hoc Islaris terms to TAL derivations and its checker shrinks.
Unlike the belt/EPIC/Wasm targets this abandons no substrate choice (RV64 + CHERI + FPCC all stay); it changes only the *shape of the evidence* on the type-level tier, so it is off that ranking — a structural refinement of the admission discipline, not an alternative to it.

**Disposition (adopted in part; normative in §5, §6, §13).**
Admission is **stratified into two checkers along this document's own functional ⋈ hyperproperty line**.
A small, decidable **CHERI-TAL type-checker** is the on-device admission checker for the **type-level** obligations — Tier-2 in full (temporal + spatial memory safety, CFI, no-codegen, ABI/type conformance) and the memory/ABI-conformance half of Tier-1 — with the certifying compiler *targeting the TAL* and certificates carried as **typing derivations**, so admission is genuinely pedigree-independent and the ~10³-line / "cheap and local" claim is true of it.
The **CIC proof kernel** is retained for the **deep** obligations no type system states — Tier-0 functional refinement + non-interference (§8), crypto reduction security, constant-time, WCET, filesystem linearizability/liveness — validated predominantly **at release time over the base-image TCB** and bound into the measured root (§9).
The platform axiom decides this exactly as it did for seL4 and crypto — **methodology is portable, the smallest trusted set wins**: spend the engineering to make the per-install admission checker a type-checker whose soundness is one Coq theorem, rather than a general proof checker no one can hold to 10³ lines.
**Honest residual (§17):** the CHERI-TAL soundness metatheorem is a new crown-jewel spec; the deep-proof CIC kernel is *named* as the larger admission axiom rather than hidden inside a 10³-line claim (so "checking is cheap" holds only for the TAL tier); and the temporal-safety type discipline over CHERI capabilities is the net-new instantiation the certifying-compiler workstream (§18) carries in place of a bespoke certificate format.

---

## Synchronous control planes via Vélus — the sequencing logic is already dataflow; write it where determinism, WCET, and causality are structural

The proposal takes the observation that the platform has already imposed every precondition of the **synchronous-dataflow** model — TDM schedules, static composition (§7), bounded IDL (§12), non-work-conserving partitioning (§11), crash-only servers with explicit re-initializable state (§12, §16) — and draws the conclusion: the **control planes** of §12 (the sequencing, supervision, and protocol state-machine logic, as opposed to the bulk **data planes** that move bytes) are *morally* Lustre programs already, written the long way in imperative Rust.
**Vélus** is a **Coq-verified compiler for Lustre** (Bourke/Pouzet lineage, PLDI'17 and after) that emits **CompCert Clight** and whose correctness theorem *composes with CompCert's* — so writing a control plane in Lustre and compiling it through Vélus → CompCert buys **verified compilation, structural WCET, and causality/determinism by construction, at zero new prover**, with Rust retained for the data planes.
Of the rearchitecture candidates this is the only one that *reduces* net-new tooling rather than trading one workstream for another.

**The control/data split the section already draws.**
§12 is written around exactly this line without naming it: the **ring data plane** moves bulk bytes over SPSC rings and "authority physically cannot cross" it, while "new authority arrives via **control-plane IPC** only."
The data planes — ring processing, the PHY long-vector math, wire parsing (Narcissus, §5), the crypto core (§5) — are throughput code over unbounded streams and stay safe Rust / verified C.
The control planes are **reactive state machines over bounded events**: the service manager's supervision tree (start-order, crash detection, restart-with-backoff, capability re-grant), the protocol sequencers (RRC/NAS/MLME/L2CAP-GATT/PDCP-RLC state and their T3xx-class timers — the *control* half of the L2/L3 servers whose *data* half stays Narcissus-parsed Rust), the power/mode/DRX/HARQ timing controllers (§11, §15), and the sentinel's detection→response logic (§12).
These are the textbook domain of Lustre/SCADE — the language family that certifies avionics and nuclear-reactor control (DO-178C) precisely because a synchronous program is *deterministic and bounded by construction*.

**What the synchronous model makes structural — three obligations this document works hard for elsewhere:**
- **WCET is structural, not derived.**
  A Lustre node compiles to a **loop-free, statically-bounded reaction** — one activation is a fixed amount of computation over a statically-sized state, no dynamic allocation, no unbounded loop.
  So the control tier's worst-case execution time falls out of Vélus compilation *by construction*, not from the Coq-verified IPET estimator (§5, §11) an arbitrary Rust CFG needs; the estimator's harder loop-bound/path work is left to the data planes.
  This is a direct **shrink** of the §11 WCET surface, and it is why the critique names *structural WCET* the headline dividend.
- **No hidden state survives an activation.**
  A synchronous node's entire state is the explicit, statically-sized Lustre memory; there is nothing latent between ticks.
  This is admission-test-3 (*no hidden state survives a partition switch*, §15) discharged by construction for the control tier, and it makes **crash-only** re-initialization (§12) a well-defined state reset rather than an audit of imperative heap.
- **Determinism and causality are compiler-checked.**
  Vélus's clock calculus rejects instantaneous cycles and fixes evaluation order, so a control plane is deterministic and causally well-formed *before* it compiles — feeding the non-interference-over-a-fixed-graph theorem (§8) a control tier with no schedule-dependent behavior to reason about, and the memory-safety certificate (§13) a body whose static allocation makes the temporal-safety obligation trivial.

**Why this is not a third language.**
The realization plan's discipline is *"two languages, one machine"* — Sail and Coq/Gallina — and Lustre could look like a violation.
It is not, at the level that matters: **Vélus's Lustre semantics *and* its compiler correctness are both formalized in Coq**, and it emits Clight into the CompCert (→ CHERI-CompCert, §6) pipeline already in the trust base.
So Lustre is not a new *trust base* — it is a **Coq-verified domain-specific generator emitting Clight**, exactly the shape of **Narcissus** (Coq-native parser DSL) and **Fiat-Crypto** (Coq-native field-arithmetic DSL) already relied on in §5; the two trust languages stay Sail + Coq.
Vélus is in fact the *strongest* member of that family, because unlike a synthesis tactic it is a *whole verified compiler* whose theorem chains with CompCert's rather than terminating at a synthesized term.

**Prior art, and where it ranks.**
The lineage is mature and mechanized — Lustre/SCADE in certified avionics, and Vélus itself a published Coq artifact that compiles a real Lustre subset — nodes, reset, control blocks, and **state machines** (POPL'23) — through CompCert with an end-to-end correctness proof, the state-machine result landing exactly on the protocol-sequencer use case.
Unlike the belt/EPIC/Wasm targets this **abandons no substrate** (RV64 + CHERI + FPCC + the Rust data planes all stay) and unlike kernel-in-gateware it fuses nothing; it changes only the *source language of one tier of one non-TCB layer*, so it is off that ranking — a structural refinement of how §12 control logic is written, and the rare one that *removes* tooling (the control tier's WCET and memory-safety obligations become structural) rather than adding it.

**Disposition (adopted; normative in §5, §11, §12).**
The **control-plane** logic of §12 servers — supervision/sequencing, protocol state machines, mode/timing control — is written in **Lustre and compiled by Vélus** (Coq-verified, → Clight → CHERI-CompCert), a Coq-verified DSL alongside Narcissus and Fiat-Crypto (§5); the **data planes** stay `#![forbid(unsafe_code)]` safe Rust.
Scope is honest: the adoption covers the logic that *is* reactive dataflow, and Rust is retained wherever a control path is genuinely imperative request/response rather than a state machine — a mis-drawn boundary is a spec error, not a silent failure.
The platform axiom decides it as ever — *methodology is portable, the smallest trusted set wins, and engineering is the free axis*: spend the engineering to move sequencing onto a language where determinism, causality, and WCET are theorems of the compiler rather than fresh per-server proof obligations.
**Honest residual (§17):** Vélus enters the build path as a new front end — Coq-verified, so it adds *no fresh axiom* and rides the already-priority-zero CHERI-CompCert backend (§18), but its Lustre-semantics faithfulness joins the crown-jewel specs and the **control/data boundary is a new crown-jewel interface**; offset against this, the control tier's structural WCET (§11), structural memory-safety certificate (§13), and by-construction determinism (§8, §15) are a net reduction in proof surface.
- **ct-verif — the IR-level sibling, not the binary-level answer.** ct-verif verifies CT by product programs over **LLVM IR** (SMT-discharged).
  It is real and usable, but IR-level: on the verified-compiler path CompCert-CT already gives CT by construction, and on the *no-compiler* path there is no trusted IR to check — the binary is the artifact.
  So ct-verif is the sibling to note, Binsec/Rel the complement to adopt — analogous to **EverParse** being noted-but-not-adopted for parsing (§5), though here the mismatch is level-of-abstraction, not trust base.
- **Scope is a labeling obligation, not a blanket tax.**
  CT is required only of compartments that receive **secret-labeled** material over an IDL confidentiality channel (§12); ordinary apps that touch no secrets carry no CT obligation.
  This matches the profile's *"tighter guarantees sharpen the holder's stopwatch"* scaling (§17) and hooks CT into the existing IFC/flow-label machinery (§8, §13) rather than inventing a new trigger — a secret reaching an un-CT-verified compartment is a *flow-label* error the Tier-1 flow theorems must catch.

**Disposition (adopted; normative in §5, §13, §15).**
Verify CT **on the artifact** against the one `Zkt`/`Zvkt` leakage model for every secret-touching binary off the preservation path; split it functional ⋈ hyperproperty like RTL ⊑ Sail, with the **relational-Sail-logic constant-time certificate** the Coq-native close and **Binsec/Rel** the mature bounded complement (**ct-verif** the IR-level sibling).
The platform axiom decides the toolchain as ever — *methodology is portable, maturity is not*: carry the Coq-native property to Binsec/Rel's demonstrated binary-level capability, spending engineering to keep CT on the single prover and make it *artifact*-borne.
**Honest residual (§17):** Binsec/Rel is path-bounded evidence (the certificate is the unbounded close); CT verification inherits the RTL ⊑ Sail residual (the leakage model is sound only once that arrow closes) and leans on the `Zkt`/`Zvkt` leakage-model statement as a shared crown-jewel spec; and correctness of *scope* rests on the flow labels (§8, §12, §13), so a mislabeled secret is a spec error no CT proof catches.
Like WCET it **degrades gracefully** — bounded Binsec/Rel evidence carries bring-up, the certificate closes it — so it gates *strong* CT assurance, not boot.
