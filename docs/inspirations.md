# Inspirations & Prior Art (non-normative)

> Companion to [spec.md](spec.md).
> This document records the **existing systems and research artifacts this design descends from**: what each contributed, where it lands in the spec, and how the design transforms it.
> It is **not** part of the normative spec; cross-references of the form §N point to sections of that specification.
> Architectural alternatives *evaluated and rejected* live in [architectural-alternatives.md](architectural-alternatives.md), not here; this page is the roads **taken**.

The lineage splits along the platform's own axiom: *engineering is free; trust is the scarce resource* (§4, §17).
Two kinds of ancestor recur, and most entries below are one or the other:

- **Designs imported and re-grounded.** seL4, Barrelfish, CheriOS, the Microkit/LionsOS/sDDF stack, bcachefs, the FSCQ family, and the CVA6-CHERI core contribute an *architecture* the spec adopts wholesale and then re-homes onto its single prover (Coq) or its capability substrate, keeping the design, shedding the incidental trust base (Isabelle, HOL4 and Viper/SMT, Dafny/Z3, a managed runtime, a non-Coq conformance prover).
  This is the *"methodology is portable, maturity is not"* move the spec body makes repeatedly (§5).
- **Patterns imported and mechanisms superseded.** systemd, Fedora Atomic, NixOS, OSTree, secureblue, GrapheneOS, ChromeOS, and Fuchsia/FIDL contribute a *product pattern* (declarative supervision, image immutability, functional/reproducible build, hardening, transactional rollback, a hardware root of trust, capability IPC) whose *intent* the spec keeps while replacing the *mechanism* with a stronger one: probabilistic mitigation becomes proof (§17), ambient-authority orchestration becomes capabilities (§8), a convenient content-addressed image becomes a boot-attested Merkle image (§9, §10), an input-addressed, reproducible-by-convention build becomes a content-addressed, proof-carrying one (§10, §13), and an unverified capability-IPC wire becomes a copy-once-verified one (§5, §12).

## seL4: the kernel design, stripped and re-proved in Coq as a bespoke minimal capability core

seL4 is the foundational import.
Its capability design is the base (§5, §7): a capability-based microkernel with zero post-boot kernel allocation, synchronous **endpoints + notifications**, first-class revocation (§8), and the **seL4-NI** non-interference lineage (§8), each of them seL4's model in every particular; with several mechanisms deliberately dropped as this platform's own simplifications: the **VSpace/paging objects** (single-address-space, no MMU, §7), the **MCS scheduler** (a table-driven cyclic executive replaces it, §7, §11, moving the scheduling configuration back toward the non-MCS static-partition one seL4's NI proof actually covers), and, per the object-model deletion, **untyped memory and retype**, **the capability space**, and **the derivation tree**, each redundant with the CHERI tag plane or the static composition (§7, §8), so what is taken from seL4 is the endpoint model and the non-interference statement rather than the object model entire.
Of the four retained, zero post-boot allocation and first-class revocation are re-grounded by the CHERIoT-shaped object-model transformation below, without disturbing the prover argument.

**Why the proof is re-homed rather than inherited.**
seL4 ships on **Isabelle/HOL** (l4v) and stays there: there is no migration to Coq, and none to CertiKOS's method either.
Inheriting that proof costs twice.
(1) **Trust-base fragmentation:** adopting it puts **Isabelle *and* Coq**, two proof checkers, permanently in a TCB whose §6 story is one self-verifying checker, a first-order regression.
(2) **Compilation seam:** seL4's shipped binary-correctness is a *different* toolchain (decompilation + SMT translation validation), not the §5–§6 CompCert/SECOMP/Islaris/Cerise path.
Both are artifacts of *inheriting seL4's existing proof*, and **redoing the proof in Coq on CompCert/SECOMP erases the first and inverts the second into native composition**.
So the spec re-proves seL4's design **end-to-end in Coq** via CompCert/SECOMP, as a **bespoke minimal capability core**, and importing seL4's Isabelle proof wholesale stays rejected.

**The design lineage is live, and its direction is the share-nothing multikernel.**
seL4's own 2024 direction is the **share-nothing multikernel** (RFC-0170) and **CHERI-seL4**, so the import is of a *live* design, not a frozen one.
The multikernel is one verified single-core instance per core, **zero shared kernel state**, and inter-kernel IPIs, with concurrency pushed to user level explicitly *"for better verification"*; and that share-nothing, per-core-sequential model **is already this spec's §7 architecture** (capability/memory lineage: Barrelfish → seL4, below).

**CertiKOS supplies the proof method that carries it**, and is demoted from kernel to *method* lineage precisely so that it can: what transfers is the **abstraction-layer discipline**, the **deep-specification** style, **CompCertX**-style verified compilation, and the generic lower-layer proofs (physical-memory management: the single-address-space design carries no paging layer) any kernel needs, giving the *how* while seL4 gives the *what*.
"CertiKOS-lineage kernel proof" is therefore shorthand for *verify this (seL4) design in Coq*, a label on the method and not a second kernel: the coherent artifact is a Coq proof **of the seL4 design already written down here**, not an import of CertiKOS's different kernel.

**What does not transfer is CertiKOS's distinctive asset**, the **Certified Concurrent Abstraction Layers** (Coq, CompCertX) verifying a fine-grained concurrent shared-memory kernel, mC2, which is the *opposite* of a simplification: the share-nothing multikernel forbids the shared mutable kernel state CCAL exists to verify, so proven shared-memory concurrency is dead weight here, and for a per-core *sequential* kernel plain **VST** (sequential separation logic over CompCert) is the more parsimonious closing logic.

**Methodology is portable; maturity is not.**
CertiKOS offers a *portable* property (a Coq proof method: deep specifications, abstraction layers, CompCertX-style verified compilation); seL4 offers an *intrinsic* one, a mature, deployed, exhaustively specified, independently reviewed kernel design.
With labor priced at zero, the move is forced: **carry the portable property to the design with the better intrinsic property.**
Apply Coq/CompCert/SECOMP to seL4's design rather than accept CertiKOS's thinner, concurrency-oriented, here-unused kernel for the sake of a method that travels.
By the platform's *own* decision criterion (smallest trusted set, deepest proof) the result wins on both axes: an identical single-prover trust base (Coq), over a design carrying the broader proved-property set (functional correctness + integrity + availability + confidentiality/NI + binary-level) and the longer-scrutinized specification; and §5 calls specifications "the crown jewels," of which seL4's has had the most independent eyes of any kernel spec in existence.
The combination is preferable only because the platform re-proves the design rather than inheriting seL4's Isabelle proof; under that condition it keeps the one-prover trust base while retaining seL4's mature specification.

**CHERI engineering transfers; its proof does not.**
CHERI-seL4 builds purecap (Morello + CHERI-RISC-V, sel4test/sel4bench passing) but is **not verified**: CHERI serves *user-level* safety there, and seL4's existing functional-correctness proof does not extend to the capability hardware.
The design mandates a **verified purecap kernel** (§7), so the CHERI-C mechanization gap (§7, §17) is net-new under *either* kernel.
Promoting the 2024 CHERI-seL4 work in-scope supplies the purecap *implementation and bring-up* to verify against; it does not supply the proof.

**Honest residual: a Coq re-proof is fresh (§17).**
What transfers from seL4's maturity is the **retained object-model design, the ABI, the C implementation, the long-scrutinized abstract specification, and the in-scope multikernel and CHERI engineering**, not the proof.
A Coq re-verification is a fresh proof and spec-mechanization, as unbattle-tested as CertiKOS's, and a faithful re-proof may pull the code marginally off mainline seL4, spending a sliver of the very battle-testing invoked.
The search for an existing Coq artifact to inherit comes back empty: seL4 is **Isabelle-only, and actively so**, with the `l4v` proof and every current extension (MCS, multicore, the seL4 Core Platform) staying in Isabelle/HOL, so the route is genuinely greenfield in Coq: design, spec, and C carry across, but there is no proof to port.
The freshness that bites is therefore **not** the authored refinement proofs, which fail *loudly* when they are wrong, but the **silent** kind, a mis-transcribed specification that verifies perfectly (§5's crown-jewel failure mode).
What bounds it is **not** a mechanical transcription: seL4's executable model is Haskell and `hs-to-coq` would carry that scrutinized prototype into Gallina without a paraphrase pass, but the kernel-specification provenance fork forecloses that carriage on licence grounds, so the executable Gallina model is authored beside the abstract spec and the refinement. What stands in its place is that **the design being transcribed is written down here and reviewed here**, an artifact this repository states and reviews rather than one it reads across a licence boundary.
The fresh specification is not unmoored: it is **disciplined by the refinement against the executable Gallina model**, since any *divergence* fails the proof loudly, so the silent residual is a *too-weak-but-faithful* specification, the generic crown-jewel risk seL4 already carries in Isabelle (§5) rather than one the Coq move introduces.
And the two-checker alternative's edge is narrower than it looks: the proofs it would let you *inherit* do not cover this platform's purecap-CHERI kernel or the multikernel configuration, both unverified in seL4 today, so that proof mass is **fresh under either option**, and what the maturity actually buys is the *design and specification*, not a discharged proof of the configuration shipped here.
That is a real cost, but a *labor-and-freshness* cost, the class the engineering-free axiom exists to absorb, not a *trust* cost: the trusted set does not grow.
The claim is thus conditional and honest: **superior iff (a) engineering is free and (b) seL4's 2024 completion is in-scope**, both stipulated.

**The stripped capability core.**
The platform commits to a specific set of deletions: the MMU with its VSpace and paging objects, MCS, SMP, the S/U privilege ring, and PMP with the IOMMU (the CheriOS, CHERIoT, and capability-checked-DMA entries below; §7, §15).
These preferentially remove the *proof-heaviest* layer of `l4v` (the arch-specific VM refinement) and its *least-maintained* ones (MCS, and the SMP concurrency the multikernel never incurs).
The starting seL4 architecture-independent core contains untyped memory, retype, the capability space, the CDT and its revocation, endpoints, and notifications; the CHERIoT-shaped object-model import below removes the first four, leaving endpoints, notifications, and the non-interference statement, and those survivors join the single-address-space CHERI isolation CheriOS demonstrates (below), the CHERIoT-lineage switcher and sealing, and the table-driven cyclic executive (§7, §11, §15).
The artifact is therefore a **synthesis, not a transcription**: seL4's object model ⋈ the CheriOS/CHERIoT CHERI-SAS realization ⋈ Barrelfish's multikernel composition ⋈ a static cyclic executive.
Reading the route as "re-prove seL4" *overstates* the maturity that transfers (the deployed kernel is a heavily-forked minimal variant, not mainline seL4) while *understating* the genuinely novel proof: the purecap CHERI-C *kernel refinement* (the CHERI-C language semantics itself now mechanized in Coq, Zaliva et al. ASPLOS 2024, so the novelty is this kernel's proof over it, not the semantics), the multikernel non-interference composition, and the switcher and sentries, none of which any base supplies.
Naming it a **bespoke minimal capability core** sizes the effort correctly and frees the object model to be designed for *minimum proof surface* rather than inheriting seL4's hooks for the features this platform deleted.
It also **relocates the decision**: with the kernel this small, the dominant fresh proof mass is no longer *in* the kernel but in the CHERI-C kernel refinement over the now-mechanized CHERI-C semantics (§7, §17), the multikernel non-interference composition (§8, §17), and the switcher and sentry verification against the Sail model, so the seL4-versus-CertiKOS-versus-CheriOS basis question is second-order to getting those right.

**The kill-switch subproof moves with the object model.**
The make-or-break subproof for a route keeping seL4's object model entire would be **CDT revocation**, the hardest part of the `l4v` corpus and never yet done in Coq for an seL4-class capability model, the natural early kill-switch on that route.
The CHERIoT-shaped object-model import below retires that subproof rather than scheduling it, the CDT being redundant with the CHERI revocation machinery, so the kill-switch role passes to the purecap CHERI-C kernel refinement and the multikernel non-interference composition.

**Convergent sibling:** Google Research's **KataOS** (its **CantripOS** userland) and its **Sparrow** reference platform independently assemble almost this exact substrate (seL4, a near-entirely-Rust userland, statically-composed CAmkES components, and an OpenTitan RoT on RISC-V), reached not as an ancestor this design descends from but as a *convergent* one that stops an assurance tier short on every axis it shares.
It rides seL4's Isabelle proof as-is (the two-prover base §5 declines) rather than re-proving in Coq, its Rust is memory-safe *by borrow-checker alone*: the "app safety leans on the toolchain" posture the artifact-level memory-safety certificate and CHERI supersede (§5, §13); its CAmkES graph is "statically-defined and analyzable" short of machine-checked static composition (§7); though its **capDL** capability-distribution spec and its Rust rewrite of seL4's **capdl-loader** rootserver are the sharper precedent §7 lowers onto (the CAmkES → capDL → verified-system-initialisation toolchain, whose live successor is the Microkit line immediately below, ridden here on Isabelle and in service of *dynamic* loading rather than re-homed to Coq and frozen static); and its third-party apps are **dynamically loaded and confined by seL4 capabilities alone**, reaching services only through its **SDKRuntime**, a runtime-validated interposer standing in for authority a compartment here simply never holds: exactly the containment-without-proof road §7's static composition and §11 proof-checked admission decline.
KataOS is thus at once the seL4 line's **shipping evidence** that the whole substrate is buildable (the Fuchsia "shipping evidence, not the proof" move (below) one layer down) and its **foil**, the same substrate secured by containment-plus-mitigation that this design takes to proof; and a *frozen* foil at that: the public AmbiML release is archived, relocated to Google's **OpenSecura** (2026), so where the seL4 and COSMIC imports track live designs, this one is shipping evidence gone static.

**The proof-hygiene lineage transfers with the design**, and three of its practices surface in the apex statement itself (§5): the **verified-system-initialisation** theorem of the capDL line above is the precedent for the §7 initialisation refinement riding the apex vocabulary as a named premise of the attestation seam, so *the graph the proofs are about* and *the graph the booted machine runs* are bound rather than assumed equal (seL4 needed that theorem as a separate deliverable, and static composition makes this platform's version easier, never free); l4v's discipline of **per-theorem assumption sets**, the security theorems resting on strictly more than the functional ones, is the precedent for the *Ax* ledger being indexed by claim class rather than pooled; and the **noninfluence** strengthening of seL4's non-interference statement is the precedent for reading T at a victim-shaped adversary set, the influence direction carried by the same quantifier rather than by a second theorem.

---

## Microkit, LionsOS, and sDDF: the living whole-system relative, its composition tooling harvested and its verification re-homed

seL4 supplies the kernel design (above); **Microkit, LionsOS, and the sDDF** (Trustworthy Systems, the same group) supply the one existing *whole system* built in the shape §7 and §12 describe, which is why R-12-005 names the stack in the spec body rather than only here: static composition plus rings, running, on real devices, now.
The **seL4 Microkit** is CAmkES's successor and the composition layer: a system is a fixed set of single-purpose, event-driven **protection domains** joined by **channels** and **shared memory regions**, written once in a **system description** that a build tool turns into a bootable image with every capability created before the first instruction runs and none creatable after: §7's static-composition mandate with a shipping tool behind it.
The **sDDF** is the data plane: bounded lock-free **SPSC queues** of buffer descriptors in shared memory with notification wakeups, splitting each device into a driver, one or more **virtualisers** that share it among clients, and the clients, which is §12's "the peer is a server, never the kernel: a ring bug costs one compartment" with the multiplexer named.
**LionsOS** is the OS over both, and its stated rule, *use-case-specific policies rather than universal ones*, with components simple enough to be swapped rather than configured at runtime, is §7's posture reached from the systems-engineering side rather than the proof side; its published systems (a point-of-sale device, a fifteen-domain firewall) are the evidence that the shape carries a product.

**This is therefore the entry where the import is tooling rather than technique** (§18): the composition tool and its system-description-to-capability-distribution path, the sDDF interface set and driver templates, and the CHERI Alliance's already-purecap **CHERI-seL4 / CHERI-Microkit** port are the start-from for §7's composition tooling and §12's ring library, a substantial body of engineering the design does not author.

**What is re-grounded is the verification, and the widening it avoids is unusually wide.**
Microkit's system-description-to-**capDL** mapping is verified push-button by SMT (the capDL lineage the seL4 entry above already credits, here with a modern front end); LionsOS aims its components at automated SMT proof with model checkers for the inter-component protocols; and **Pancake**, the group's driver language, carries a verified compiler in the CakeML/**HOL4** lineage while proving driver code by transpilation to **Viper** and SMT, with a verified Ethernet driver as the demonstration.
Counting the kernel's Isabelle that is four trust bases in one system, and §5's whole argument is that a TCB checked by one self-verifying kernel (§6) beats a stack of individually strong, jointly unrelated ones.
So the platform takes the structure and re-homes each layer to Coq: the queue becomes the one canonical ring library proved against a Byzantine peer under Ztso (§12, §15), wire parsing becomes Narcissus, the reactive halves of drivers and protocol servers become Vélus/Lustre (above), and Pancake's role, *a verified-compiler DSL owning one tier*, is filled by exactly the family already inside the Coq base.
The convergence is architectural and the disagreement is only over which kernel checks the result.

**Three mechanisms are superseded rather than imported.**
- **MCS.** Microkit is defined over seL4's MCS configuration: scheduling contexts, budgets, priorities, and a protected-procedure call whose callee must outrank its caller, with MCS's own proof still landing (RISC-V targeted 2026, AArch64 2027). §7 deletes the class entire for a table-driven cyclic executive with no priorities and no runtime scheduling decision, the same move back toward the static-partition configuration seL4's non-interference proof actually covers (above); service is metered on the session's slot (R-12-009), never by rank, and the priority-inversion side conditions that shape Microkit's PPC rule have nothing to constrain.
- **The shared mapping.** sDDF's queues are ordinary pages mapped into both peers, so "authority does not cross the data plane" holds because descriptors carry no references worth following. Here ring pages are mapped **without capability-store permission** (R-12-007), making it architectural rather than a property of the payload, and each slot is a CHERI-TAL-checked ownership typestate rather than memory both peers may touch concurrently (R-12-008a).
- **Convention as contract.** The sDDF queue discipline is shared by convention between peers built from the same headers, which is precisely the gap R-12-091 closes: capacity, index width, the four-word header, queue-full refusal, notification arming, cancellation races, and restart recovery through a generation word are specified content of the generated interface artifact, because two independently built peers can each "implement the ring" and still disagree in ways that cost progress, a WCET bound, or the interface proof.

**And one is refused outright.** LionsOS's pragmatic answer to legacy device support is the **Linux driver VM**, an unverified commodity kernel in a guest driving hardware nobody will re-implement, its I/O re-exported over sDDF queues. That is excluded twice here: the machine has no MMU and no virtualisation (§7, §15), and an unverified kernel holding device authority is the foreign-computer category §4 exists to delete (§12's dissolved-modem thesis is the same refusal at the radio). The platform therefore pays in full the cost the driver VM exists to avoid, writing every driver fresh against the verified HAL, and the escape hatch its nearest relative keeps is unavailable by construction.

Honest residual (§17): sDDF's performance results are measured on commodity MMU-and-cache hardware, so they are evidence that *the structure is not slow* rather than a bound that transfers to a cacheless single-address-space machine, whose costs §11 re-derives from its own schedule; the harvested code is unverified C and enters as engineering, never as assurance, exactly like the openwifi and smoltcp start-froms (below, §12); and unlike KataOS (above), this relative is **live**, so the start-from is a moving target, which cuts favorably here, since its CHERI port and its verification work are both moving toward this design rather than away from it.

---

## HACMS and SMACCM: a verified kernel flown, red-teamed, and not broken, and the component layer above it

DARPA's **High-Assurance Cyber Military Systems** programme (2012 to 2017) is the strongest whole-system delivery evidence outside Trustworthy Systems' own line, and its value here is evidentiary rather than technical.
The air team, **SMACCM** (Rockwell Collins, Galois, NICTA, Boeing, Minnesota), put seL4 on the mission computer of a quadcopter and then of Boeing's optionally-piloted Unmanned Little Bird, enforcing the partition between untrusted mission software and the flight-critical path.
The red-team result is the citation, and it is worth stating in the narrow form that survives scrutiny rather than the wide one that circulates: the red team was given full access to the non-critical camera compartment and **handed the keys to crash it**, and could not cross into the flight mission; the exercise was repeated in flight with two test pilots aboard and failed again.
The claim is that an attacker *starting inside a granted compartment* could not cross a machine-checked boundary. It is not that the aircraft is unhackable, and the discipline of naming the compartment the attacker starts in and the boundary that held is itself the import: it is how §3 and §17 should state every security claim they make.

**Galois's Tower is the other import, and it is a static composition that shipped.**
Tower is an embedded language layered over Ivory that describes concurrent tasks and the channels between them ahead of time and generates the connecting code, which is the same move §7 makes when it fixes the component graph at build time and derives the IPC surface from it; SMACCMPilot, some fifty thousand lines of Ivory, is the artifact that flew.
What is declined is Ivory's assurance argument.
Ivory generates memory-safe C by construction of its embedding, with the guarantee carried by Haskell's type system and by the generator, neither of which is machine-checked and neither of which leaves a proof object, so there is nothing to re-home and the guarantee is a strong engineering discipline that §5's rule does not count as verification.
The two-board split is declined as an architecture for the reason it existed: separating a real-time microcontroller from a mission board is the answer available when the mission software is untrusted legacy, and a static composition under a cyclic executive puts both on one die under one proof (§7, §15).

---

## SECOMP: the secure-compilation method, and the CHERI-CompCert backend the TCB compiles through

seL4 supplies the kernel *design*; **SECOMP** (the MPI-SP secure-compilation project) supplies the *compilation method* that carries it, and the rest of the verified C, to metal.
SECOMP extends **CompCert** with **compartments** and proves not merely functional correctness but **secure compilation**: **robust preservation**, the guarantee that a component stays protected even when linked against a fully adversarial context, all machine-checked in Coq/Rocq.
That criterion is §5's requirement for the TCB's compiler (§5, §6): the compiler-side complement to the **Cerise** universal contract the same spec uses for unknown code (§13), so "the TCB is correctly compiled" and "the hardware bounds everything else" compose under one robust-safety framework rather than joining unproven.
Its CHERI backend, **SECOMP2CHERI** (PriSC 2023), already carries CompCert from CompCert C down to its formalized RISC-V assembly onto a CHERI capability machine, so the platform's **priority-zero CHERI-CompCert backend** (§6, §18) starts from it rather than authoring one fresh.
What is re-grounded is not the prover: SECOMP and CompCert are Coq-native, so nothing foreign is shed (unlike the Isabelle and Dafny re-homings above); it is the CHERI *variant*, re-homed to the §15 purecap profile on the one Sail model, and the *completion* of the robust-preservation theorem for that profile.
Honest residual: SECOMP2CHERI is workshop-stage (PriSC), its published sibling's primary backend targets a tagged architecture, and the robust-preservation theorem for this profile is deferred hardening (§5, §17); what transfers now is the functional CompCert-to-CHERI-RISC-V engineering, not a finished secure-compilation proof.

---

## Vélus: the Coq-verified Lustre compiler, and the control planes written where determinism, WCET, and causality are structural

SECOMP supplies the compiler the TCB's C descends through; **Vélus** (Bourke and Pouzet lineage, PLDI'17 and after) supplies the one a whole *tier* of §12 is written for.
It is a **Coq-verified compiler for Lustre** that emits **CompCert Clight** and whose correctness theorem *composes with CompCert's*, so a control plane written in Lustre and compiled through Vélus → CompCert buys **verified compilation, structural WCET, and causality and determinism by construction, at zero new prover** (§5, §11, §12).
Of everything weighed as a rearchitecture, it is the only import that *reduces* net-new tooling rather than trading one workstream for another.

**The control/data split it lands on** is one §12 already draws without naming: the **ring data plane** moves bulk bytes over SPSC rings and "authority physically cannot cross" it, while "new authority arrives via **control-plane IPC** only."
The data planes (ring processing, the PHY long-vector math, wire parsing via Narcissus, the crypto core) are throughput code over unbounded streams and stay safe Rust and verified C.
The control planes are **reactive state machines over bounded events**: the service manager's supervision tree (start-order, crash detection, restart-with-backoff, capability re-grant), the protocol sequencers (RRC/NAS/MLME/L2CAP-GATT/PDCP-RLC state and their T3xx-class timers, the *control* half of the L2/L3 servers whose *data* half stays Narcissus-parsed Rust), the power/mode/DRX/HARQ timing controllers (§11, §15), and the sentinel's detection→response logic (§12).
These are the textbook domain of Lustre/SCADE, the language family that certifies avionics and nuclear-reactor control (DO-178C) precisely because a synchronous program is *deterministic and bounded by construction*.

**Three obligations the synchronous model makes structural, each of which this design works hard for elsewhere:**
- **WCET is structural, not derived.**
  A Lustre node compiles to a **loop-free, statically-bounded reaction**: one activation is a fixed amount of computation over a statically-sized state, with no dynamic allocation and no unbounded loop.
  So the control tier's worst-case execution time falls out of Vélus compilation *by construction*, not from the syntax-directed WCET cost annotation (§5, §11) an arbitrary Rust control-flow graph needs, leaving that harder loop-bound and path work to the data planes: a direct **shrink** of the §11 WCET surface, and the headline dividend.
- **No hidden state survives an activation.**
  A synchronous node's entire state is the explicit, statically-sized Lustre memory, with nothing latent between ticks: admission-test-3 (*no hidden state survives a partition switch*, §15) discharged by construction for the control tier, which makes **crash-only** re-initialization (§12) a well-defined state reset rather than an audit of imperative heap.
- **Determinism and causality are compiler-checked.**
  Vélus's clock calculus rejects instantaneous cycles and fixes evaluation order, so a control plane is deterministic and causally well-formed *before* it compiles, feeding the non-interference-over-a-fixed-graph theorem (§8) a control tier with no schedule-dependent behavior to reason about, and the memory-safety certificate (§13) a body whose static allocation makes the temporal-safety obligation trivial.

**Why it is not a third language.**
The realization plan's discipline is *"two languages, one machine"* (Sail and Coq/Gallina), and Lustre could look like a violation.
It is not, at the level that matters: **Vélus's Lustre semantics *and* its compiler correctness are both formalized in Coq**, and it emits Clight into the CompCert (→ CHERI-CompCert, §6) pipeline already in the trust base.
Lustre is therefore not a new *trust base* but a **Coq-verified domain-specific generator emitting Clight**, exactly the shape of **Narcissus** (Coq-native parser DSL) and **Fiat-Crypto** (Coq-native field-arithmetic DSL) already relied on in §5; the two trust languages stay Sail and Coq.
Vélus is in fact the *strongest* member of that family, because unlike a synthesis tactic it is a *whole verified compiler* whose theorem chains with CompCert's rather than terminating at a synthesized term.

The family's other half is worth naming exactly, because SCADE is usually cited as though it were Lustre alone: **SCADE 6 is Lustre plus Esterel**, and Esterel contributes what dataflow does not, first-class **preemption** (`abort` and its weak and strong forms) and a **constructive** causality analysis, Berry's Must/Can fixpoint, where Lustre's clock calculus rejects instantaneous cycles syntactically. Esterel has its own Coq lineage, Berry and Rieg's mechanized development of the logical, constructive and state semantics with a novel microstep semantics between them, but it stops short of both the loop construct and a verified compiler, so it stays a semantics to read rather than a vehicle to ride: the preemption idiom is what transfers, into control planes that must abandon a reaction rather than complete it.
The lineage is mature and mechanized: Lustre and SCADE in certified avionics, and Vélus itself a published Coq artifact compiling a real Lustre subset (nodes, reset, control blocks, and **state machines**, POPL'23) through CompCert with an end-to-end correctness proof, the state-machine result landing exactly on the protocol-sequencer use case.
What the import does **not** do is abandon a substrate or fuse anything: RV64, CHERI, FPCC, and the Rust data planes all stay, and it changes only the *source language of one tier of one non-TCB layer*.
Scope is honest: the adoption covers the logic that *is* reactive dataflow, and Rust is retained wherever a control path is genuinely imperative request/response rather than a state machine; a mis-drawn boundary is a spec error, not a silent failure.
Honest residual (§17): Vélus enters the build path as a new front end, Coq-verified so it adds *no fresh axiom* and rides the already-priority-zero CHERI-CompCert backend (§18), but its Lustre-semantics faithfulness joins the crown-jewel specs and the **control/data boundary is a new crown-jewel interface**; offset against this, the control tier's structural WCET (§11), structural memory-safety certificate (§13), and by-construction determinism (§8, §15) are a net reduction in proof surface.

---

## The verified-crypto stack: Fiat-Crypto, HACL\*/libcrux, formosa-crypto, and the Coq-native reduction layer, from implementation to reduction

A verified cryptosystem needs three properties, and the field supplies mature artifacts for each: **functional correctness** (the code computes ML-KEM), **constant-time** (it leaks nothing through timing), and **reduction-level security** (the *scheme* is IND-CCA or EUF-CMA under a named hardness assumption).
Functional correctness plus constant-time (Fiat-Crypto + libcrux/HACL\*, §5) cover the first two and leave the third unstated, and **neither says the scheme is secure**: IND-CCA (KEM) and EUF-CMA (signatures) are *game-based* properties established by **reduction** to a hardness assumption, proofs about the *scheme*, not the *code*.
The third is the one most stacks leave unstated, and proving the implementation while assuming the cryptography inverts this design's own priority: the most consequential property, that the scheme is actually hard to break, is the one left unproven, which is the reverse of the spec's "deepest proof over the smallest trusted set" criterion.
So §5 composes all three, importing a different artifact at each layer and re-homing each toward the one prover.

**Trust-base minimization is why each layer's artifact is chosen rather than merely accepted.**
§5 elsewhere *minimizes* F\*/Z3 by construction, picking **Narcissus over EverParse** for parsers purely on trust-base uniformity; merely accepting the crypto widening ("ports don't exist yet") would leave the largest attacker-facing trust widening un-attacked.
Every tool below is run through the §5 trust-base test, and one of them, CryptOpt, is **rejected by that same test**, which is what the test is for.

- **Fiat-Crypto** supplies correct-by-construction field arithmetic from a Coq specification, and is the *native* member of the set: it is a Coq-native domain-specific generator in exactly the sense Narcissus and Vélus are (above), so it enters at zero new trust base and its output is compiled as ordinary verified C through CHERI-CompCert.
- **HACL\* and libcrux** supply the functionally-verified primitives themselves, and are the standing **interim**: they discharge via **F\*/Z3**, a trust base distinct from Coq, and §5 minimizes that widening deliberately rather than accepting it (the same reasoning that picks Narcissus over EverParse for parsers, on trust-base uniformity alone).
- **SSProve and FCF** supply the missing third layer, Coq-native game-based reduction frameworks in which IND-CCA and EUF-CMA are proved by reduction to a hardness assumption.
  Choosing them is the identical decision made for Narcissus: the reduction rides the one Coq kernel (§6) at **zero new trust base**, which is why they are the destination rather than the complement.
- **EasyCrypt and formosa-crypto** supply the *finished* ML-KEM and ML-DSA reductions, and so are the fastest path to a real proof, but EasyCrypt discharges via **Why3/SMT**, so by this design's own logic it is a widening of the same character as the F\*/Z3 one: **adopted as pragmatic interim assurance, with SSProve/FCF the destination.**
- **Three Rocq-native routes point at the implementation layer and not one of them is an implementation**, which is why the two post-quantum schemes are authored rather than imported.
  A verified **number-theoretic transform** is specified in Rocq and *derives* complete and incomplete NTTs for several schemes, which is the largest component ML-KEM and ML-DSA share and is still a component rather than a scheme.
  **hax** carries a Rocq backend over the Rust that libcrux's ML-KEM is written in, and its own project grades that backend **experimental** where the F\* one is stable, which places it below the bar an admitted artifact clears.
  And the **Jasmin-to-SSProve** translation composes the Jasmin compiler's correctness theorem into the destination framework named above, having carried AES against a machine-readable specification.
  The third is the one that bears on the shape of this section, because it is a route *into* SSProve from a verified implementation rather than a second reduction: the destination layer turns out to be reachable from an artifact and not only from a paper proof.
  What it does not establish is that it is reachable from *this* artifact. Jasmin's target is AMD64, which is not a machine this platform has; the ML-KEM instance's functional correctness presently assumes its SHA-3; and the specification the proof is stated against is EasyCrypt's transcription of FIPS 203 rather than FIPS 203, which is the widening the row above books rather than an escape from it.

**Constant-time is verified on the artifact, which closes layers 1 and 2 and decides what may join them.**
CT is *not* taken from any of these by preservation; it is verified **directly on the binary** against the §15 leakage model for every secret-touching artifact, the verified-C crypto core and its field-arithmetic kernels included, exactly as for every other secret-touching binary.
There is **no verified-compiler CT route**, so a single CHERI-CompCert carries the whole toolchain, "trust a C compiler to preserve constant-time" is replaced by the binary-level lineage, **CompCert-CT remains a declined alternative**, and no artifact is admitted on the strength of which compiler produced it.
The **field-arithmetic kernels** are verified C through that same compiler, which is what closes layers 1 and 2 for them: functional correctness from CompCert's theorem, and constant-time *structurally*, since straight-line code has no secret-dependent branch or address for the stock lowering to introduce.

**What does not transfer: CryptOpt.**
The mechanism is genuinely attractive, which is why the comparison is recorded in full: an *untrusted* randomized-search superoptimizer emits assembly faster than GCC/Clang at top optimization (at times beating hand-written asm), admitted by a **Coq-verified program-equivalence checker** back to its **Fiat-Crypto** functional spec, so the trusted artifact is a *small verified checker* rather than a second optimizing backend, the crypto instantiation of the asymmetric-trust pattern the platform runs everywhere.
**What decides against it is the paragraph above.**
Once the field arithmetic is verified C through CHERI-CompCert it is *already functionally correct* and, being straight-line, *already constant-time* on that compiler's stock output as verified on the artifact.
So the equivalence checker's entire remaining yield is **throughput on a path that is already correct and already leak-free**, and §5's standing rule, illustrated again by the WCET lineage below, reads on artifacts as well as bounds: a net-new verified artifact bought for speed alone spends the scarce currency to buy the free one.
CryptOpt is therefore excluded rather than retained as a deferred workstream: deferral would keep its checker and code-generation dependencies on the §6/§18 plan for a throughput-only gain.
**What the deletion removes** is a net-new Coq equivalence-checker development over the CHERI-RISC-V Sail model (CryptOpt targets x86-64, so the retarget would be net-new), the *checker-admitted artifacts* TCB category (§6, a category only these kernels would populate), the §18 crypto-codegen workstream, and the *checker-admitted assembly leaf* escape hatch the CT story would otherwise lean on.
Two further asterisks point the same way: CryptOpt's headline results come from randomized search **benchmarked on real silicon** that does not exist here yet (the fitness function would have to ride the timing-annotated Sail model or the FPGA, §11), and its scope is *straight-line field arithmetic* only, so the control-flow-heavy primitives it never covered (Keccak, AES, ChaCha, the ML-KEM/ML-DSA NTT and samplers) were always verified C, branchless-hardened and constant-time-verified on the artifact.
**Cost, stated plainly:** hand-assembly-grade ECC and big-integer throughput is surrendered; the classical-crypto hot path runs at verified-C codegen speed, with performance subordinate (§1) and the engineering-free axiom offering no relief here because the cost is *trust*, not labor.

**What the platform takes.**
The composition is the contribution: crypto assurance becomes **three composed layers** (functional correctness (Fiat-Crypto; libcrux/HACL\* interim) ⋈ constant-time (verified on the artifact, the field-arithmetic kernels included and compiled as verified C like everything else) ⋈ reduction-level security (SSProve/FCF Coq-native, EasyCrypt/formosa-crypto the mature complement)), joined at each primitive's functional specification, which is itself promoted to the crown-jewel spec list (§5).
**CryptOpt translation validation is rejected**: the whole core is compiler-borne, so **no crypto artifact is checker-admitted and no crypto-codegen workstream survives.**
The toolchain choice is the seL4 move once more, *methodology is portable, maturity is not*: carry the Coq-native property (on-artifact constant-time verification, SSProve/FCF reductions) to the mature artifacts (formosa-crypto, Fiat-Crypto), spending engineering to shrink the trusted set, and decline even a mature, verified-checker-admitted artifact where its only remaining yield would be *speed* on a path already correct and already leak-free.

Honest residual (§17): a reduction *isolates and names* the hardness assumptions (MLWE/MSIS, ECDLP/CDH) but cannot prove them, which is the irreducible cryptographic axiom; the implementation ⋈ reduction join is a new seam at the functional spec; EasyCrypt-borne reductions carry an SMT base until restated Coq-native; and scheme-level IND-CCA and EUF-CMA still sit below protocol-level security (TLS, AKA), a further layer again.
What the stack buys is the deepest-available crypto proof, the move from *"correct, constant-time code for a scheme we assume is secure"* to *"the scheme is IND-CCA or EUF-CMA under a named, minimal hardness assumption, implemented by constant-time code verified on the artifact"*, with the residual pushed down to conjectures no proof system can discharge.

---

## The masking and fault-countermeasure lineage: DOM to MATCHI, the netlist-level discharge, and the theorem shapes the two axioms import

The masked crypto core (§5, §15, §17) is curation at every layer but one, and the one is not hidden: the Coq objects are priced in the plan's four post-M10 cells. The gadget theory is settled: domain-oriented masking (Groß et al.), the robust probing model (Faust et al.), PINI composition (Cassiers/Standaert), and the HPC gadget families give glitch-robust, trivially composable construction at arbitrary order, with COMPRESS and AGEMA as generators and SMAesH as the parametric-order masked-AES existence proof. The verification tooling is mature and layered: SILVER exact at gadget scale, PROLEAD statistical at full-cipher scale under glitch- and transition-extended probing, MATCHI compositional over full masked hardware, and the one published end-to-end pipeline (formal verification, then tapeout, then physical evaluation: the TCHES 2026 prime-field-masking-on-silicon study) executes exactly the verify-then-characterize discipline R-15-053a mandates. Two results anchor the axiom's narrowing: Coco-class execution-aware verification checks masked software against the executing core's gate-level netlist, the discharge R-15-053a's accept requires, and the share-slicing and MIRACLE measurement campaigns are why nothing weaker is accepted, masked software on ordinary cores being refuted at ISA-level reasoning. OpenTitan's masked AES and KMAC carry the production randomness architecture this design inherits with its RoT lineage: a stream-cipher expansion (Bivium-class, hundreds of fresh bits per cycle) between the entropy root and the gadgets, which is where R-05-004a's named DRBG assumption comes from, an LFSR's output cancellation being a proven way to void a probing proof. What is not curation is stated plainly: no proof-assistant-checked masking development exists in Coq (EasyCrypt and Lean only, and none artifact-level), and no masked realization of a vector crypto extension exists at any width or order. **That second absence is now a disposition rather than an obligation**: R-05-004a narrows the secret path to a dedicated masked datapath of the parametric-order lineage, so what this repository owes is a realization of an arm with published prior art rather than a first of its kind, and the vector crypto units stay in the profile for work that carries no secret. The Coq objects are what remains original, and they are priced in the plan's four post-M10 cells. The Lean half of that clause now has a shape worth naming, because the shape decides which obligation it touches: the 2026 development carries **PINI-class composition over prime fields**, the renewal argument for fresh masking between pipeline stages, its k-stage generalization, and the Barrett-reduction bounds beneath them, stated with no admitted goals and instantiated against a published post-quantum accelerator to diagnose a real flaw in its masking. That is the lattice half of the composition theorem, in the wrong prover and released as an MIT-licensed sorry-free artifact against pinned Lean and Mathlib revisions (read 2026-08-23, R-18-001a), which makes it a transcription source rather than an import and a better one than a paper would be; it is first-order by its own stated scope where the obligation is *d*-th order, the Boolean half the AES and Keccak datapaths need remains EasyCrypt's, and R-17-058d's ineffective-fault reduction is touched by neither.

The fault half imports the same way. The protected-sequence idioms descend from Moro et al.'s model-checked single-skip-tolerant sequences and their compiler-emitted successors (Barry's LLVM pass, CompaSeC on RISC-V secure boot); the theorem shape R-16-008f mandates, every in-model fault detected or without observable effect, is mechanized in Coq at CompCert's RTL level (Pesin et al., CPP 2025), one level above where this design states it; Islaris is the proof-engineering template for theorems over Sail-derived machine code; and SailFAIL derives fault-injection simulators from Sail models with CHERI-RISC-V case studies, the natural validation harness beside FISSC's hardened-comparison corpus. The sentinel's lockstep position is OpenTitan's own, and its formal treatment (k-fault-resistant partitioning, TCHES 2024) both proves the detection guarantee and found the two bypass classes R-16-008d closes by construction: the comparator-enable path inside the fail-stop boundary, and the fixed cycle skew against common-mode transients, the standard dual-core-lockstep mitigation. The combined-adversary booking (R-17-058c) is the SIFA literature taken at its word: a single ineffective-fault filter defeats masking plus detection regardless of order (ASIACRYPT 2018), the composable combined-secure gadget families were broken a year after publication (CCS 2023), and the verification tooling for the class (VERICA, FIVER) exists outside any prover, which is why the entry books the gap open instead of quoting the two axioms together. The raise is now exercised by selection (R-17-058d), and the selection follows the same literature: the countermeasure lineage, masked implementations on permutation building blocks with fine-grained detection or error correction (Daemen, Dobraunig, Eichlseder, Gross, Mendel, Primas; TCHES 2020), withstands single-fault SIFA by making every in-model fault either detected or confined to one share, which is exactly the reduction to the two stated axioms the design can verify without adopting a third; the embedded-verification family carrying its own combined model, CAPA's tile-probe-and-fault construction (CRYPTO 2018) and M&M's masks-and-MACs successor (TCHES 2019), and the CINI-class composable notions behind the broken-and-refurbished gadgets are declined as the pin and retained, with VERICA and FIVER, as producer-side evidence and design vocabulary.

---

## Proof-carrying code and typed assembly: the Necula → Morrisett arc, RustBelt and StkTokens, and CHERI-TAL admission stratified by proof strength

The admission discipline descends from one of the field's cleanest arcs: **Necula's proof-carrying code** (a proof travels with the artifact and the consumer re-checks it locally), narrowed by **Morrisett's TALx86** into a *type discipline* (the certificate is a typing derivation and checking it is decidable type-checking), then given foundations by **Appel's foundational PCC** and **Crary's foundational TAL** (the type system's soundness proved down to the machine semantics rather than assumed).
On the memory-safety-type side the mechanized descendants are **RustBelt** (Iris) and **WasmCert-Coq**, and on the capability side **StkTokens** (Skorstengaard, Devriese, Birkedal, POPL 2019) supplies the linear and affine discipline in the same capability-machine-logic lineage as Cerise.
So the whole *type-soundness* half of the platform's CHERI-TAL (§5, §6, §13) is inherited rather than gambled on.
What the PCC-to-TAL lineage supplies concretely is a **typed assembly language for RV64+CHERI**: Tier-2 admission type-checks annotated binaries, compilers emit typing derivations rather than general proof terms, and the on-device checker is a small decidable type-checker while deeper theorems remain CIC proofs.
That is the structure that makes two admission commitments honest at once: the ~10³-line on-device checker (a *CIC term* checker at that size does not exist, MetaCoq's being tens of kLoC and axiomatizing guard and termination) and verification as a property of the artifact rather than of a mandated build path (§5).

**What CHERI changes about the inheritance is the size of the type system.**
CHERI already discharges spatial safety in hardware, so the type system need not encode bounds proofs: the capability *is* the bound.
TALx86 had to encode array-bounds and initialization proofs into its types because x86 had no hardware notion of a bound; on a purecap machine the bound, the tag, and monotonicity are *architectural*, so the imported types shrink to exactly the residual CHERI does not enforce at runtime: **temporal** safety (linear and affine capability types over a revocation-coloured heap, the StkTokens discipline in the CHERIoT lineage below) and **typed control flow**, where a well-typed jump target simply *is* control-flow integrity.
That residual is precisely what safe Rust's ownership discipline already establishes at source (§5), which makes the TAL the vehicle that carries source types down to the binary as a checkable derivation, turning *"the compiler preserves and certifies rather than re-discovers"* from a promise into a concrete artifact format: the memory-safety analog of carrying constant-time to the binary as a checkable certificate (§5).

**Two further type-level imports ride the same checker**, each replacing a mechanism the design would otherwise have built: **CT-Wasm** (Watt et al.) shows constant-time decidable as a **taint-type discipline** for structured code, so CT becomes a type-check rather than a proof term wherever the code is structured (§5); and definite initialization arrives as a move-(II) type attribute (§5) descending from TAL's own founding per-field initialization flags, which is why the Write-before-Read property is taken as a type attribute over §7's static slot plan instead of as the tag plane the hardware proposal wanted.
The **typed callee set** (§5, §13) is the same move once more, refining the code type already in the vocabulary rather than adding a grade beside it.

**Why two checkers, not one.**
The assurance obligations split along a line this document already draws three times (RTL ⊑ Sail, WCET, CT: each a *functional ⋈ hyperproperty* split):
- The **type-level obligations** (memory safety (temporal + spatial), control-flow integrity, no-runtime-codegen (W^X, §14), ABI/type conformance, the **constant-time** of structured secret code (a taint-type discipline), and the **WCET** of structured code (a syntax-directed cost annotation)) are exactly what a TAL type system *decides*.
  These are the whole of Tier-2, the structural half of Tier-1, and (for the structured population) the constant-time and worst-case-timing obligations that would otherwise be release-time proof terms.
- The **deep** obligations (Tier-0 functional refinement, the binary refines the seL4 abstract spec, whole-graph non-interference (§8), crypto **reduction** security (IND-CCA/EUF-CMA, §5), filesystem linearizability + liveness (§10)) are **not typing judgments**: no decidable type system states "this binary refines the abstract kernel", so those need a full higher-order logic and a proof term.
  **Constant-time and WCET are the boundary cases, and for structured code they *do* type-check.**
  CT is a 2-safety hyperproperty, but the CT-Wasm lineage makes it a taint-typing obligation for structured code (a Coq restatement here); structured-code WCET is likewise a syntax-directed max-path sum over the typed control-flow graph (Shaw's timing schema).
  So both **join the type-level tier for the structured population** the obligations actually cover (the straight-line field-arithmetic kernels, the structured Tier-1 secret paths), leaving only the genuinely unstructured CT/WCET residual as proof terms: the relational-Sail 2-safety logic shrinks from *the* CT vehicle to a corner case (§5).

So the TAL does not *replace* the certificate scheme, it **stratifies** it, taking the tier where a type system is complete and leaving the tier where only a proof will do.
The crypto, WCET, and CT lineages show that hyperproperties need more than a functional logic; the TAL lineage shows that type-level properties need less than a general proof kernel.

- **It makes the checker-size commitment honest by splitting the checker, not by shrinking a CIC checker.**
  A TAL type-checker is decidable, syntactic, obviously terminating (no guard or termination side-condition to axiomatize), and genuinely on the order of 10³ lines: so the **on-device admission checker** that runs on every install and sits in the boot TCB *is* that type-checker, and the ~10³-line claim, false for a CIC term checker, is **true for this one**.
  The full **CIC proof kernel** (MetaCoq-lineage, honestly tens of kLoC) does not vanish: it validates the deep Tier-0 and hyperproperty proofs, but it moves to where those proofs actually live, **release-time, over the fixed base-image TCB**, its result bound into the signed measured-boot root (§9), not a per-install on-device cost (§6).
  "Checking is cheap and local" is *literally true* of the TAL admission path and deliberately **not claimed** for Tier-0 (an seL4-scale refinement is machine-hours to check).
  The two options a single checker would force a choice between ("a genuinely tiny logic" and "a larger checker named openly as the axiom") are both taken, each in its proper tier.
- **It makes admission pedigree-independent: gating on the derivation, not the producer.**
  Once the certificate *is* a typing derivation the checker re-checks, **any** producer of a well-typed CHERI-TAL binary is admissible by definition; the certifying Rust→CHERI compiler (§18) becomes the *reference producer*, not a gate.
  "We ship one reference toolchain" and "only its output is admitted" are different claims: the TAL keeps the first and drops the second, making admission genuinely language- and pedigree-agnostic (§5), while the hardware universal contract (Cerise, §13) stays beneath as defense-in-depth against a checker or TAL-soundness error.
  This is the point at which *"verification is a property of the artifact, not its pedigree"* (§5) stops being aspirational.
- **The one new axiom is the TAL's soundness metatheorem: a crown jewel, paid once.**
  Type-checking is only as sound as the theorem *"well-typed CHERI-TAL ⇒ the safety properties hold over the Sail model"*, a foundational-TAL syntactic-soundness proof (WasmCert-Coq / RustBelt lineage), authored once in Coq against the §15 model.
  It joins the crown-jewel specs (§5): a mis-stated typing rule admits an unsafe binary that type-checks perfectly.
  But it is a *smaller and more scrutable* axiom than "a hand-built ~10³-line CIC checker is correct" would have been.

**Lineage.**
Necula's PCC, Morrisett's TALx86, Appel's and Crary's foundational work, RustBelt, WasmCert-Coq, and StkTokens make the type-soundness half inherited rather than speculative; the net-new work is the CHERI-RISC-V instantiation and the compiler's emitted derivations.
Unlike the belt/EPIC/Wasm targets this abandons no substrate choice (RV64 + CHERI + FPCC all stay); it changes only the *shape of the evidence* on the type-level tier, so it is off that ranking: a structural refinement of the admission discipline, not an alternative to it.

**Where the language lives, and why that is a separate decision from adopting it.**
Everything above settles the *shape of the evidence* and nothing about who owns the type system.
Its dependency set is a machine semantics and a type theory and nothing else, which makes it the one part of this platform whose correctness argument mentions no operating system, so it is specified separately, in [typed-assembly-language.md](typed-assembly-language.md), with this platform depending on its `cheri-rv64` instantiation and pinning a version (§5).
Two things follow, and only two.
The **target's guarantees become a parameter**: a profile declares, per obligation, whether the machine *cites* it, the type system *attributes* it, or a producer *inserts* a run-time check, so a bare non-capability target becomes expressible without weakening the profile this platform pins, and the reason it is weaker is stated rather than left implicit: a cited invariant binds arbitrary co-resident code because the machine checks every access, an attributed one binds only code that was type-checked, so a citing profile is open-world and a bare one closed-world.
The **freeze becomes a pin**: the vocabulary grows by amendment to that specification and reaches this platform when the pin moves, a stronger review surface for the language and a new seam for the consumer (§17).
What does not follow is a smaller §18, the factoring relocating the work and making its cost shareable rather than reducing it.

**What the platform takes.**
Admission is **stratified into two checkers along this document's own functional ⋈ hyperproperty line**.
A small, decidable **CHERI-TAL type-checker** is the on-device admission checker for the **type-level** obligations: Tier-2 in full (temporal + spatial memory safety, CFI, no-codegen, ABI/type conformance) and the memory and ABI-conformance half of Tier-1; with the certifying compiler *targeting the TAL* and certificates carried as **typing derivations**, so admission is genuinely pedigree-independent and the ~10³-line, "cheap and local" claim is true of it.
The **CIC proof kernel** is retained for the **deep** obligations no type system states (Tier-0 functional refinement + non-interference (§8), crypto reduction security, the *residual unstructured* constant-time and WCET, filesystem linearizability/liveness): validated predominantly **at release time over the base-image TCB** and bound into the measured root (§9).
The platform axiom decides this exactly as it did for seL4 and crypto (**methodology is portable, the smallest trusted set wins**): spend the engineering to make the per-install admission checker a type-checker whose soundness is one Coq theorem, rather than a general proof checker no one can hold to 10³ lines.

**Honest residual (§17):** the net-new work is the **CHERI-RISC-V instantiation**, namely the temporal-safety type discipline over CHERI capabilities and the compiler emitting derivations, which the certifying-compiler workstream (§18) carries in place of a bespoke certificate format; the **CHERI-TAL soundness metatheorem** (*well-typed CHERI-TAL implies the safety properties hold over the Sail model*), authored once in Coq against the §15 model, is a new crown-jewel spec, since a mis-stated typing rule admits an unsafe binary that type-checks perfectly; the deep-proof CIC kernel is *named* as the larger admission axiom rather than hidden inside a 10³-line claim, so "checking is cheap" holds only for the TAL tier; and the language being pinned rather than contained, an amendment to its theory reaches this platform only when the pin moves.
It is nonetheless a smaller and more scrutable axiom than a hand-built proof checker would have been, and the Cerise universal contract (§13) stays beneath it as defense-in-depth against exactly that failure.

---

## Singularity, Verve, Midori, and Theseus: language safety carried to the artifact, with CHERI beneath it

The software-isolation lineage contributes the contained-code discipline without becoming the sole isolation mechanism.
Singularity's software-isolated processes show how a type-safe language and checked channels can remove conventional address-space machinery; Verve contributes the verified typed-assembly nucleus; Tock and Theseus demonstrate GC-free Rust systems that push invariants into the language.
The platform takes those properties as safe Rust, Vélus and verified C at source, then carries them to the final binary through CHERI-TAL (§5, §13).
CHERI remains beneath that proof to bound arbitrary code and compiler or certificate residuals, so language safety and hardware capabilities compose rather than substitute for one another.

Midori contributes the **error model**: recoverable failures are typed results, while a violated program invariant causes fail-fast abandonment of the isolated component.
That becomes the fail-stop, fail-closed, crash-only discipline (§16), strengthened by proving defects absent at admission where possible and using abandonment only for the residual.
Theseus contributes the analysis of **state spill**, the coupling created when one component holds state on another's behalf.
The share-nothing multikernel, explicit crash-only state, and static composition minimize that spill structurally (§7, §12, §16).
Theseus-style in-place live evolution is not part of the import: code changes arrive as measured, signed A/B generations under W^X (§9, §11, §14).

The original systems' trusted runtimes, garbage collectors, Boogie/Z3 proof base, and language-only confinement are not inherited.
What transfers is the source-safety discipline, TAL carrier, typed error model, and state-spill criterion, each re-homed onto the one Coq and CHERI substrate.

---

## Barrelfish: the multikernel: share-nothing cores, capabilities as the lineage

Barrelfish (ETH Zürich / Microsoft Research) originated the **multikernel**: treat a multicore machine not as a shared-memory multiprocessor but as a *network of independent cores*, each running its own kernel instance, sharing **no** kernel state and communicating only by explicit message passing, with per-core replicas kept consistent by agreement rather than by locks over shared structures.
§7's **heterogeneous multikernel** is exactly that model (one verified kernel artifact instantiated once per core, strictly disjoint state, no shared mutable kernel data, no kernel locks), so each instance's proof is the *sequential* proof, sidestepping verified fine-grained SMP (the field's hardest artifact).
Barrelfish also carried a capability system in the seL4 lineage, so the **capability + multikernel** pairing this platform rests on is the *Barrelfish → seL4* line made verifiable.
What the spec does **not** take is Barrelfish's dynamic, discovery-driven System-Knowledge-Base personality: composition here is **static and machine-checked at build time** (§7), cores are statically assigned to classes with no dynamic migration (§7), and the message-passing plane becomes the bounded-SPSC **verified ring** (§12) proven under Ztso (§15).

---

## SemperOS: distributed capabilities across non-coherent cores; the multikernel revocation the proof must still discharge

SemperOS (Hille, Asmussen, Bhatotia, Härtig; TU Dresden / Barkhausen Institut, USENIX ATC '19) carries the *Barrelfish → seL4* capability-multikernel one step past where §7 rests: it manages **capabilities distributed across many non-coherent, heterogeneous cores**, coordinated by multiple microkernel instances over a hardware/software co-designed capability system (the M³ lineage, cores reached through a per-tile communication unit rather than by cache coherence).
Its contribution is precisely the seam this design exposes and then defers to its proof: it analyzes the *pitfalls of concurrent distributed capability operations* and builds the protocols to match, the hardest being **revocation** that must reach every kernel holding a derived copy, and it shows the result scales (a parallel efficiency of 70–78% across 576 cores).
That is the closest existing engineering art for the one mechanism §8 asserts but does not itself detail, the **bounded-round cross-core revocation protocol** by which a capability delegated over a static grant edge is withdrawn, and for the part of the non-interference theorem §17 books as *fresh*, the **multikernel composition** of per-instance single-core proofs into one system theorem.

It is a **convergent** entry, not an ancestor this design imports: the protocol itself is unverified (M³/C++), non-CHERI, and bound to a specific hardware communication unit, so what transfers is the *evidence* that capability systems scale to non-coherent cores and the *shape* of the distributed-revocation problem, not code or proof.
SemperOS is thus to the multikernel capability layer what Barrelfish (above) is to the multikernel itself and seL4 to the single kernel: shipping evidence that the substrate is buildable, with the proof deliberately the platform's own to supply (§8, §17); the delta claimed over it is exactly the thing it leaves undone, **verifying** the distributed protocol.
The design also *shrinks* the problem before inheriting it: because its capability graph is **static and machine-checked at build time** (§7), the dynamic delegate/obtain races that dominate SemperOS's concurrency analysis are largely designed out, leaving cross-core **revocation** (sentinel- and kill-switch-driven, §8, §16) as the residual distributed operation whose race-freedom the fresh proof must establish.

---

## KeyKOS → EROS → CapROS: transparent checkpointing, with the persistence of *data* taken and the persistence of *processes* left behind

The KeyKOS line's most distinctive runtime idea is **orthogonal global persistence**: the system takes a periodic consistent snapshot of all user state (pages, capabilities, and running processes alike), so a restart resumes the machine as of the last checkpoint and an application does nothing whatever to be persisted or recovered.
The engineering held up: dirty pages are marked copy-on-write and written in the background rather than stop-the-world (the naive multi-second snapshot is what gave checkpointing its bad name), the snapshot lands in a write-ahead checkpoint log before migrating to home locations, most migrations never happen because the page is re-dirtied first, and the reported steady-state overhead is a fraction of one percent.
Its claimed payoff is the one this design cares about: applications stop containing save/load code at all, and a capability system additionally escapes the awkward startup question of where a freshly started program gets its authority.

**What is taken is the payoff, not the mechanism.**
§10's **declarative durable state** keeps the property that no application authors a serializer, an autosave loop, or a recovery path, and drops everything that made the property *transparent*: a compartment declares typed durable regions in its manifest (§13), the platform checkpoints them at a verified quiescent point (§7) as one transaction through the already-verified storage stack (§10), and a restart is a measured boot into a freshly initialized compartment that then *reads* its regions (§9).
The deletion is therefore of **code**, which is what the design wants (one verified persistence path instead of N unverified ones, the move already made for the allocator and the configuration parser), without the resume, which is what the design forbids.
The security argument is the code-deletion argument, not the convenience one: a hand-rolled per-application serializer is an encoder and a parser over attacker-reachable bytes, and the platform's standing answer to N of those is to replace them with one artifact under proof (§5).

**What is left behind, and why the line's own history says so.**
Resuming execution state contradicts the crash-only posture (§12, §16) and the rule that no resume path exists outside the measured chain (§9); restoring a saved capability graph would make storage a second origin of authority beside static composition (§7, §13), able to resurrect what a revocation epoch retired (§8); and keys, nonces, and DRBG state must not survive a reboot at all (§5, §9).
The line reached compatible conclusions under pressure, which is why the exclusions are enumerated rather than judged.
**CapROS** had to make the page-fault handler and most drivers **non-persistent** by necessity, split its objects into persistent and non-persistent classes, **rescind on restart** every capability a persistent object held to a non-persistent one, and warn that I/O may be half-completed across a checkpoint; **EROS** had to add an explicit **journaling capability** beside transparent persistence, because a database's durability cannot ride a checkpoint interval.
Both concessions are load-bearing here: the first is the argument that the *typed-data* half is the separable atom, and the second is why an externally visible or non-repeatable effect still takes an explicit commit (§17).
Honest residual: the tradition's own warning that in a persistent system a defect is written down and read back, so damaged state outlives the reboot that would otherwise have cleared it, is booked in §17 and bounded by keeping the durable class typed, per-domain, non-TCB, and discardable, and by never extending it to system or kernel state.

---

## Plan 9: private namespaces, Factotum, and Plumber re-grounded on capabilities and typed IPC

Plan 9 contributes three ideas that become one object-fabric control plane in §12 and §14.
Its **per-process namespace** supplies the usability model for presenting each program a different coherent view of files and services; here the view is derived at composition time from the program's capability manifest, and a path is only a local alias for an object or service capability already granted, so namespace composition never becomes an authority mechanism (§14).
Its **Factotum** supplies the separation between protocol implementation and key custody; here the existing sealing and attestation service and crypto core return non-exportable, attenuable credential capabilities bound to protocol role, peer or origin, operation, transcript, use count, and expiry, with no raw-key export or generic signing/decryption oracle (§12).
Its **Plumber** supplies typed intent routing between applications; here intents are closed IDL variants, objects travel as out-of-band capabilities with §10 typed metadata, and a contained router selects only among a signed composition-time graph of already-admitted handlers and translators, rebuilt at package install (§12, §13).

The transformation is the point.
Plan 9's universal file protocol and mutable `mount`/`bind` namespace are not imported: forcing every service through byte-stream file operations would discard the platform's typed IDL, bounded rings, capability control plane, and generated proof skeletons, while runtime namespace mutation and global service discovery would reopen ambient path authority.
No 9P compatibility layer exists; the platform takes the private-view, key-custody, and message-routing ideas and realizes each through mechanisms it already verifies.

---

## BeOS: typed attributes, live queries, translators, and media graphs made transactional and static

BeOS contributes the object-facing half of the same fabric.
Its filesystem **typed attributes, indexed queries, and live queries** become typed metadata records and secondary-key instantiations in §10's one verified B^ε-tree, scoped by confidentiality domain and namespace capability and updated in the same journal transaction as the object; commit-ordered live deltas use §12's bounded SPSC rings, with overflow reduced to a rescan marker rather than an unbounded event queue.
Its **Translation Kit** becomes the finite typed translator graph: content type and intent are frozen IDL types, every translator is an admitted static compartment, and conversion output returns to the content-addressed store as an ordinary typed object (§10, §12, §13, §14).
Its **Media Kit** becomes the streaming form of that graph: composition-time templates bind pre-composed decoder, converter, mixer, renderer, and output nodes with bounded rings and §11-admitted WCET, memory, label, and device reservations (§12).

The dynamic BeOS mechanisms are deliberately declined.
There is no runtime-loaded translator add-on, codec plugin, handler registration, content-sniffing dispatch, global query index, or best-effort media graph assembled after admission; those would add executable mutability, cross-domain metadata oracles, parser ambiguity, and scheduling states the static package closure and cyclic executive exist to remove.
The result keeps BeOS's unusually coherent object and media programming model while moving persistence into the existing verified store, authority into CHERI capabilities, interchange into the existing IDL, isolation into static compartments, and timing into the existing admission proof.

---

## TRON: the document part as the user-visible primitive and therefore the unit of grant, and µITRON's static configuration as the deployment record

The TRON project (Ken Sakamura, University of Tokyo, 1984) is five sub-architectures under one architecture: **ITRON** for embedded real-time kernels, **BTRON** for the workstation, **CTRON** for switching and mainframes, **MTRON** for coordination among them, and **STRON** for the kernel realized in silicon, that last one judged on its own merits in [architectural-alternatives.md](architectural-alternatives.md) where the hardware-kernel question already lives.
Two of the five contribute here, and they contribute from opposite ends: BTRON supplies a **granularity** the object fabric does not currently name, and µITRON supplies the largest deployment record any statically-configured kernel has.

**BTRON: the primitive the user manipulates is a typed part rather than a file, and the design's own grant rule then reaches further than it currently does.**
BTRON's organizing construct is the **real object / virtual object model** (実身/仮身, *jisshin*/*kashin*): user data is an arbitrary directed graph of typed real objects rather than a directory tree, a virtual object is a reference to one embedded inside another, and the interchange format (**TAD**, the TRON Application Databus) is a typed segment stream rather than an application's private file layout, so a document *contains* a drawing instead of naming a file some application knows how to open.
The BeOS entry above already takes typed metadata, indexed and live queries, and the translator graph; what it does not take, because BeOS does not offer it, is the further claim that the **application is not a unit of user-visible structure at all** and therefore should not be a unit of authority either.
That claim lands on machinery already built rather than asking for new machinery. A powerbox grant is *"CHERI-bounded to that object alone"* (§8), the object fabric's handoff passes a selected handler *"only that object capability plus the local buffer capabilities the caller supplied"* (§12), and object identity is a content address or a filesystem object identity with a typed metadata record beside it (§10): none of the three says how large an object is.
Taking BTRON's primitive makes a part an object in exactly that sense, and the consequence is the **least-authority open dialog**: consenting to edit an embedded spreadsheet hands the spreadsheet compartment a capability to *the part*, not to the document enclosing it, and the closed intent variants the fabric already routes (*view*, *edit*, *convert-to(type)*, §12) acquire a subject small enough that the grant is worth the consent act it costs.
No mechanism is added; a granularity is chosen, and it is chosen at the one point §8 says the user's own authority enters the system.
The model reached a shipping implementation rather than remaining a specification (Personal Media's B-right/V line, the R2 release of 1999 running in 16 MB on a 486-class machine), and the decomposition showed up in its applications: the mail client bundled with it was built as *"a group of miniature applications that are started up as necessary"* instead of as one program, which is the part-as-primitive claim reaching the application layer as a factoring the static compartment graph (§7) would express as ordinary nodes.

**What is not taken is the edge, because in BTRON authoring a link is granting authority.**
A *kashin* is dereferenced by the system on the user's behalf, so a real object reachable through the graph is reachable, and the document graph and the authority graph are one graph.
Here they are two. An embedded reference is a **name**, under the rule §14 already states for paths (*"a path is only an app-local alias for an object or service capability already present in the graph, never authority in its own right"*), and the fabric's resolution/handoff split (§12) is what holds it to that: a reference resolves only under the namespace capability the caller delegated for the session, so following one to a part outside that namespace is a fresh consent act at the powerbox rather than a dereference.
Without the inversion a hypermedia store is a confused deputy with a document editor for a front end, since attacker-authored content that embeds a reference would be authoring an edge in the authority graph: precisely what static composition (§7) and a single runtime minter (§8) exist to deny.
This is the Plan 9 transformation above applied to a second naming layer, and it is the reason the part-as-object idea is safe to take at all.

**µITRON: the deployment record for composition-time object graphs, reached from the unit-cost pole.**
The µITRON 4.0 specification defines a **Static API**: tasks, semaphores, event flags, mailboxes and their attributes are declared in a system configuration file, a configurator emits the tables, and identifiers are fixed at build time, so a Standard Profile kernel creates no object after boot and carries no runtime creation-failure path to handle.
That is §7's static composition and §13's compose-time graph, reached not from a proof obligation but from ROM cost and interrupt-latency determinism on small parts, carried into an enormous deployed embedded population and then into a standard (**IEEE 2050-2018**, derived from µITRON 4.0).
It is the Akaros move, **evidence rather than code**, and the evidence is of a different kind than Akaros's: not a research system demonstrating that the static shape performs, but an industry that chose it on cost and stayed with it for three decades.
The inversion runs opposite to every other entry here, and is the more instructive half.
Sakamura's stated method is **loose standardization**: the specification deliberately admits implementation variance and leaves adaptation to the hardware to the implementer, on the argument that a real-time kernel's portability is worth less than its fit.
That bought ubiquity with the one thing this design will not sell, a single frozen semantics mechanized once (§18) against which conformance is a theorem instead of a checklist.
µITRON therefore contributes its **conclusion** (declare the objects at build time) and none of its **method** (let each vendor mean something slightly different by them), and the residual it exhibits is the one the profile freeze exists to avoid: a family of kernels sharing an API and not a semantics is a family no single proof reaches.

**TRON Code is declined, and it is the sharpest foil in the entry.**
BTRON's character encoding refused Han unification and reached 1,500,400 codepoints as 31 planes of 48,400, selected by **language specifier codes** carried in the data stream from 0xFE21 upward, and those codes are overloaded rather than simple: one code selects the plane, declares the script group, and declares the language, three of a four-layer hierarchy (font, script, group, language) whose last two layers the shipping implementation, Personal Media's B-right/V R2 (1999), never implemented.
The coverage argument was real and, for about a decade, correct, and the mechanism is nevertheless what §5's parser discipline exists to exclude, twice over: escape-switched planes are **stateful decoding**, so a byte's meaning depends on history and a copy-once verified parser carries state that a truncated or spliced stream can desynchronize; and an in-band control code with three declared functions, two of them unimplemented, is an underspecified grammar no verified decoder can be written against, since conformance has no referent.
**The decisive objection is not a parsing objection at all, and this design would meet it immediately.**
Refusing unification was deliberate, and it means the same character exists on several planes at once, so the encoding admits **many representations of one text and defines no canonical form**.
On a machine whose objects are named by *"the per-domain keyed plaintext digest"* (§10), and whose conversion cache identity is keyed on that content address (§12), a non-canonicalizing text encoding silently separates byte identity from semantic identity: two identical documents become two objects, deduplication and cache reuse fail as false negatives rather than wrong answers, and no verification recovers a canonical form the format declines to define.
The failure is therefore in capacity and determinism rather than in correctness, which is exactly the class §15's capacity budget and §17's population wall are least able to absorb.
What transfers is only the smaller observation, that a unification is a lossy transformation applied at the encoding layer and therefore un-appealable above it, and it is already discharged: content types are frozen IDL types (§12) and typed metadata is schema-bounded (§10), so a lossy normalization is a translator edge with a declared output type rather than a property of the character set.

**The deployment lesson, recorded because this design has BTRON's shape and not ITRON's.**
Of the five sub-architectures the one that reached ubiquity is the one a single vendor could adopt inside a single product with nobody's cooperation, and the one that failed is the one that needed the state, the manufacturers, and the application authors to move together.
BTRON's proximate shock is usually told as the 1989 U.S. Trade Representative process, and the record is narrower than the telling: BTRON was raised as a market-access concern, that year's priority designations under the provision were supercomputers, satellites, and forest products, no sanction ever attached, and the listing did not survive the year.
What followed was manufacturers withdrawing from a coordinated adoption that had lost its coordination, against an installed base already moving elsewhere.
The lesson is about the shape of the dependency rather than about the trade action: a stack whose value requires simultaneous adoption at several layers has a failure mode no technical argument addresses, and a stack with one layer adoptable alone does not.
This platform is whole-stack down to its own ISA profile, which is BTRON's exposure precisely, and §18's realization is where the ITRON-shaped counterpart belongs: some layer usable inside one product without the rest of the stack coming with it.

---

## Capsicum, E, and the powerbox: the object-capability lineage, the term's actual origin, and the patterns that do not survive the move into hardware

The powerbox is load-bearing across §8, §12 and §14 and has never been attributed, which is worth repairing precisely because the attribution corrects a common error.
The term is **Marc Stiegler's**, from CapDesk and the DARPA-funded DarpaBrowser work at Combex, not from Miller's thesis: a powerbox is "the software module that mediates the granting of authorities to a capability confined application from the user", and its operative principle is **designation as authorization**, that the user's ordinary act of pointing at a thing *is* the grant, so no separate permission decision and therefore **no permission dialog** is required.
Polaris carried it to Windows XP on exactly that principle, inferring the authority to grant by detecting the user's acts of designation.
**Sandstorm** is the most complete implementation and the sharpest rhyme with this design: a grain requests a *type* through a `PowerboxDescriptor`, the user picks the *instance* from capabilities they already hold, and a claim token bound to the session is exchanged for access.
That shape imports with one restriction Sandstorm did not have and §7 supplies for free: the set of grantable capability *types* is fixed at composition time, so what is user-chosen at run time is which instance and never what kind, which makes the whole grantable surface statically auditable.
The Cambridge group's KDE powerbox over Capsicum is worth naming as the only one built over an operating-system capability model rather than a language one.

**Capsicum is in the design's own ancestry, by the Cambridge group's own account.**
The CHERI FAQ says plainly that protecting pointers in registers and memory is "a technique inspired by our earlier work on Capsicum, a hybrid capability-system model for UNIX", and Capsicum (`cap_enter`, rights-masked file descriptors, `pdfork`) is its canonical example of hybridisation.
What transferred is the **hybrid adoption strategy** rather than the mechanism: Capsicum's thesis was that a capability system succeeds only by extending the incumbent API so compartmentalisation can be incremental, and CHERI's hybrid C and hybrid compartmentalisation are that thesis moved from the system-call boundary down to the ISA.
This design declines the hybrid half deliberately, being clean-slate, which is worth stating rather than leaving as an omission: the incrementalism that made CHERI adoptable is a cost this platform does not pay and a compatibility story it does not get.

**The tradition's patterns split on one line, and the line is sharp.**
Patterns about what a reference **is** transfer to CHERI; patterns about what happens **when** a reference is used need a runtime that can interpose.
Transferring: unforgeability and designation-equals-authorization, which is the tag plane's definition and is stronger in hardware than in a language because there is no reflection and no `eval` to subvert; **no ambient authority**, where Miller's four sources of connectivity reduce to composition-time endowment plus introduction over typed channels, parenthood having no referent at all when nothing is created at run time; **attenuation**, which is CHERI derivation's monotone narrowing of bounds and permissions; the **facet**, a derived capability or a sentry over a narrowed entry point; the **sealer/unsealer pair**, where CHERIoT sealing is E's `makeBrandPair` in silicon and the correspondence is one-to-one; **sentries**, a jump-only capability being a closure over state the caller cannot read, which is the ocap object in hardware; and Redell's **caretaker** in effect, since a sentry over an epoch checked against a global epoch is a revocable forwarder and the load filter generalizes it to revoking every reference derived from a grant with no forwarder at all (§8).
Not transferring, and the reason is structural rather than a matter of effort: **transparent membranes** require intercepting every reference crossing a boundary, recursively and in both directions, and a capability in a register is used by an instruction with no software in the path, so a membrane needs either a proxy per object (a region and a sentry each, which destroys both the transparency and the cost model) or a trap per dereference, which is not a thing the architecture offers; **promise pipelining** (Cap'n Proto's, itself CapTP-derived) needs first-class promises and an answer table, is implementable over typed channels as an application protocol, and exists to collapse network round trips that do not exist on one die; **rights amplification** in general, as opposed to the sealing special case; and **capability-value equality across mutually suspicious parties**, since two capabilities to one object are distinguishable values, equality of values is not equality of authority, and neither is decidable from the values alone.
The epoch-and-load-filter design should therefore be read as buying the membrane's *purpose*, transitive severance of a reference set, while declining its mechanism, and as revoking by **grant** rather than by **graph**, which are different equivalence classes and should not be elided.
The general rule underneath: an ocap language gives capabilities at *object* granularity where a wrapper costs an allocation, and CHERI gives them at *region and entry-point* granularity where a wrapper costs a region, a sentry, and a composition entry; every pattern that survives is one needing no per-object wrapper, and every pattern that dies is one that does.

**The formal half of this lineage is already Coq, already Iris, and already in the corpus under other names.**
Swasey, Garg and Dreyer's **OCPL** (OOPSLA 2017) is the language-level mechanization, verifying the standard pattern catalogue including the caretaker and membranes; the machine-level branch is the **Cerise** line (JACM 2024) that §13 already rides, whose device is the one worth naming here explicitly, a **logical relation that is simultaneously the definition of capability safety and the reasoning principle for unknown code**, which is the existing formal answer to what it means that a composed component cannot exceed its endowment whatever its code does, with **StkTokens** and **Cerisier** the well-bracketed-control-flow and attestation extensions of the same line.
The live descendants of the language branch (Agoric's Hardened JavaScript and Endo, Spritely's Goblins and the OCapN work, Moddable's XS) are recorded as convergent evidence that the discipline is alive and are imported in no part: each is a language runtime enforcing at run time what §7 fixes at composition time.

---

## oo7 and the freedesktop Secret Service: the desktop keyring, and the escape hatch from it that argues the capability case

oo7 is a Rust implementation of the freedesktop **Secret Service**, the interface behind the Linux desktop keyring: a client library, a daemon replacing `gnome-keyring-daemon`, a portal backend for sandboxed applications, a `secret-tool`-equivalent CLI, a `git` credential helper, PAM integration, and a KWallet parser kept only to migrate secrets *out* of one.
It is the closest shipping analogue of what the sealing and attestation service does for userland here (§12), and it converges on three of the same conclusions: that secret custody belongs in one service rather than in every application, that the credential-helper surface is what makes such a service reach anything at all, and that the C daemon underneath is worth replacing with memory-safe code.

The divergence is the interesting half, because the incumbent interface is **ambient by construction**.
Any client that can address the session bus may ask the service for items, mediated by a prompt rather than by possession of a capability, and oo7's own documentation states the remedy plainly: a sandboxed application should abandon the shared service for a per-application encrypted file, *because the shared one exposes its secrets to everything else that can talk to the bus*.
That is the ambient-authority diagnosis in the ecosystem's own words, and the per-application file is a weaker approximation of what §8 supplies by construction, there being no bus to address and no ambient name to ask for: an application reaches the store only through a capability it was granted, and holds nothing else.

Three further inversions follow from that one.
The interface is a **retrieval** API that hands the secret bytes back to the caller, where the protocol-credential broker returns a non-exportable credential capability bound to protocol role, peer, operation, transcript, use count, and expiry, so the credential never crosses the boundary at all (§12: the Factotum split above, carried one step further).
The file backend puts the application in charge of its own encryption under a master secret a portal hands it, where keys never leave the crypto core (§5), an application holds only sealed blobs (§12), and per-domain keys with per-extent AEAD already hold them in its own namespace (§10, §14).
And the unlock prompt is rendered by the service itself with nothing to distinguish it from a spoof, precisely the seam the trusted-path agent under the RoT-driven secure-attention indicator exists to close (§6, §9), while the transport the specification negotiates (a plaintext mode, or 1024-bit Diffie-Hellman with AES-128-CBC) is the pre-quantum floor everything here binds to the §5 core to avoid.

What transfers is therefore vocabulary and evidence, not code, and certainly not the protocol: no Secret Service server and no compatibility layer for one exists here, for the same reason no 9P one does.
The client **shape** (an item as a label, an attribute map, an opaque secret and a content type, searched by attribute rather than by path, with locked and unlocked stores distinguished in the type system behind an explicit backend seam) is the vocabulary the platform's own secret-store client takes, both of oo7's backends being deleted along with the assumptions that motivate them and one typed IDL ring to the sealing service put in their place; and its credential helpers are the concrete shape of the compartments the version-control port already calls for and does not specify.

---

## Akaros: application-directed core partitioning and the asynchronous syscall, reached from the datacenter-performance pole

Akaros (Barret Rhoden, Kevin Klues, and colleagues at UC Berkeley; a Plan 9 derivative) is a manycore operating system built for *"parallel and high-performance applications in the datacenter"*, whose organizing goals are **application-directed resource management** and *"100% isolation from other jobs running on the system."*
It converges, from the opposite pole, on three commitments this design also makes.
Its **Many-Core Process** hands whole cores to a process and stops time-slicing them, so a job owns its cores outright: the spatial-partitioning, no-preemption posture §7's per-core multikernel and static cyclic executive reach by another route; its **asynchronous system-call interface** submits calls through shared-memory rings and collects results out-of-band instead of trapping synchronously, matching the shape of §12's bounded SPSC rings and their data/control-plane split; and its headline result, *an order of magnitude less OS noise than Linux with better CPU isolation*, is the jitter-and-determinism dividend §11 claims from designing that dynamism out.

It is a **convergent foil**, not an ancestor this design imports, and because it converges from the *performance* pole where this design comes from the *verification* one, the mechanisms invert exactly where it matters.
Akaros grants cores **dynamically at runtime** and lets each process schedule its own user threads on them (the two-level `vcore`/`uthread` model), whereas this platform fixes the schedule at **composition time** (§7, §11), deleting the very runtime core-granting the Many-Core Process exists to exploit.
Its one distinctive concept (**provisioning versus allocation**, separating the *right* to a resource from the *holding* of it) is machinery for arbitrating dynamic grants, which a static composition-time schedule makes moot (the memory-side analogue: the CHERI line's runtime reservation-and-claim bookkeeping, which the static memory plan below moots the same way).
And it is unverified C, monolithic, and Plan 9-derived, with neither capabilities nor CHERI nor a proof: the performance-maximal antipode of a verification-maximal kernel, so nothing crosses into the trust base.
What transfers is therefore **evidence, not code**: shipping demonstration that spatial core partitioning, no time-slicing, and asynchronous shared-memory syscalls together crush OS jitter and buy isolation, the empirical case for the determinism posture (§11), and the clean contrast that sharpens *why* the static, proven form is chosen over the dynamic, measured one.

---

## Cerebras: the wafer-scale all-SRAM manycore, convergent evidence for share-nothing and a foil for its dataflow

The Cerebras Wafer-Scale Engine (Cerebras Systems) is a single-wafer AI processor: on the order of a million small cores, each with its own private SRAM, communicating only by message passing over a statically-configured 2D mesh, with no DRAM and no cache hierarchy anywhere on the die.
Set its two headline properties aside (the wafer-scale integration this platform does not pursue, and the all-on-die main memory it independently adopts, §15), and the rest converges, from the AI-accelerator pole, on three further commitments this design also makes: cores that share **no memory and run no cache-coherence protocol**, communicating by explicit messages (the share-nothing multikernel and its coherence-free islands, §7, §15); **flat, uniform-latency on-die memory** as the whole of it, which this design takes in two fixed-latency classes rather than one where Cerebras takes one (the no-DRAM-channel, no-cache subsystem, §15); and a **statically-configured interconnect** whose routes are fixed ahead of time rather than arbitrated dynamically, each router holding pre-programmed routes per virtual channel (the TDM NoC, §15, its schedule emitted by the §11 admission proof).
It is the largest-scale existence proof that a share-nothing, coherence-free, message-passing manycore is buildable, the role Barrelfish (above) plays for the model itself and SemperOS (above) for its distributed capabilities.

It is a **convergent foil**, not an ancestor this design imports, and the divergence is the sharp part: precisely the mechanisms that make Cerebras fast are the data-dependent, reactive, hidden-state class this platform deletes by construction.
Its **dataflow execution** fires work on operand arrival, so timing tracks the data, against the static cyclic executive and the fixed-latency WCET tables (§7, §11); its celebrated **sparsity harvesting** skips zero operands, a data-dependent timing, power, and interconnect-traffic channel of exactly the kind the constant-time mandate forbids (the `Zkt`/`Zvkt` leakage model, §15, the same class as variable-latency division and analog compute-in-memory); its mesh runs on **hardware backpressure**, a busy receiver stalling its upstream sender, which is the cross-domain contention timing channel the **TDM arbitration deletes** by construction (a partition's slot does not move because a neighbor is busy, §15); and because its cores are dataflow-driven they idle between events, a data-dependent activity profile, where this platform draws power on the static schedule alone (§15).
The interconnect comparison is thus two-sided in one artifact, take the static routing and decline the backpressure, and the compute comparison likewise, keep the flat SRAM and decline the sparsity that would leak through it.
What transfers is therefore **evidence, not code**: the demonstration at extreme scale that the share-nothing, no-coherence, all-SRAM substrate works, and the clean illustration of *why* its performance tricks are the ones a verification-maximal design must leave on the table, since each buys throughput with a channel.
The fabric corroborates the static-routing choice at scale rather than proposing a new one, so the concrete 2D-mesh topology is at most an input to the proof-aware design-space exploration (§15), never a mandate.

---

## Mungi, Opal, Angel, and Nemesis: the classic single-address-space line, its own published critique, and the one thing none of them did

The single-address-space ancestry recorded below CheriOS is entirely modern, and the older line is worth having for three reasons: one of its members is the direct ancestor of the kernel §7 imports, its proponents wrote the best critique of it themselves, and the thing every one of them failed to do is precisely what §15 does.

**Mungi** (UNSW; Heiser, Elphinstone, Vochteloo, Russell and Liedtke) is the purest of them and the closest to home, being Gernot Heiser's own single-address-space capability system built over a from-scratch 64-bit L4 before the group's centre of gravity moved to the kernel this design descends from.
Its capabilities are **sparse password capabilities**, a 64-bit object base paired with a 64-bit password, presented implicitly through a user-level *active protection domain* and validated lazily at page-fault time against a system-wide object table.
Two things import and neither is the mechanism.
The **active protection domain** is the right shape for a component's endowment, an explicitly held set of authorities that a call carries rather than an ambient identity the system looks up, and Mungi's **protected procedure call** is the same object §7's sealed-capability domain entry is.
Everything underneath is declined at once, and the list is worth stating because it shows how much of the classic design was load-bearing on machinery this platform deletes: enforcement is by MMU, validation happens on a **page fault**, the object table is **global mutable kernel state** that a share-nothing multikernel forbids, and the bank-and-rent accounting is run-time allocation.
The sharpest decline is the capability itself: a password capability is unforgeable *in a statistical sense*, which is a probabilistic claim, and §5's theorem cannot rest on one any more than R-08-031a's jitter can (the encrypted-name prohibition Nickel states above is the same refusal reached from the interface side).

**Opal** (Washington; Chase, Levy, Feeley and Lazowska) contributes the sentence the whole line rests on, that **addressability and access are independent**, and one mechanism worth naming: **portals**, unforgeable global names for protected entry points at fixed addresses, which is a statically composed call edge described two decades early.
It also contributes the **canonical critique of single-address-space systems, written by its own proponents**: virtual contiguity, conservation of address space, the impossibility of `fork` (their own conclusion that Unix could not be built above a native Opal kernel), and the loss of copy-on-write where pointers would need relocating.
That critique is the one a reviewer will bring, and the honest answer separates two mechanisms this document otherwise risks conflating.
**CHERI neutralizes exactly one of those complaints**, the page granularity of protection; and, worth recording as live evidence, µFork (SOSP 2025) makes even `fork` newly tractable by using CHERI tags to relocate references.
Everything else on the list, address-space exhaustion, dangling references, revocation cost, no copy-on-write, is neutralized here by **static composition rather than by CHERI**, because every one of them is a consequence of allocating at run time (§7, §8).
**Angel** (City University London) is kept as the negative example: it was first, in 1992, and it had **no explicit protection system at all**, resting on names an attacker was assumed unable to guess, which is the shape [absence-contract.md](absence-contract.md) exists to make impossible to ship by accident.
**Grasshopper** is recorded to correct a common misfiling: it is routinely listed as a SASOS and its own designers explicitly **rejected** the single flat address space for a partitioned container store, on checkpointing, protection-immaturity and store-management grounds. That is free independent prior art for a decision [architectural-alternatives.md](architectural-alternatives.md) already took: it is the controlled experiment where orthogonal persistence and a single address space were pursued together and **persistence won**, and this design makes the opposite trade knowingly rather than by not having noticed.

**Nemesis** (Cambridge) is the strongest contact of the five and it lands on §11 rather than §8.
Its structure is **vertical**: neither the kernel nor a server performs work on an application's behalf, so every resource an application consumes is charged to the application that caused it, and the pathology that structure exists to delete has a name better than the one used here, **QoS crosstalk**, which arrives with a literature attached.
Its protection is a software-emulated protection lookaside buffer, a global translation shared by every domain plus a per-domain rights array indexed by **stretch**, a contiguous range with uniform permissions whose rights are ORed in at TLB fill: a page-granular ancestor of a capability, and the closest the classic line came to separating protection from translation.
Its mechanisms are declined wholesale because they are all run-time memory management (self-paging, stretch drivers, the frames allocator, guaranteed and optimistic frames), and its **Atropos** scheduler is a direct foil rather than an ancestor, buying its guarantees from a run-time admission test over slice-and-period reservations where §7 buys them from a build-time table, which is the family [architectural-alternatives.md](architectural-alternatives.md) declines.
One caution against a tempting sentence: the path from Nemesis to CHERI is **institutional and not technical**, its people carrying into Xen while CHERI came out of a different group and programme, so no descent should be claimed in the specification.

**The finding that matters most is a negative one, and it sharpens §15's own claim.**
**No classic single-address-space system ever protected without an MMU.** Opal used Mach's page tables, Mungi mapped and validated at fault time, Nemesis ORed rights in at TLB fill, Grasshopper based all access control on page-oriented virtual memory, Angel had nothing, and even the protection-lookaside-buffer proposal that separated protection from translation was still a hardware protection table.
The modern members do not close it either: **CheriOS retains an MMU for performance while not using it for protection**, and Theseus retains virtual memory for convenience.
So the deletion here is not the last step of a well-trodden path but the step nobody took, which is an argument to make as a **subtraction from the trusted base and from the Coq model** (§6, §7) rather than as a performance claim, and a reason to expect no prior art to lean on at exactly that point.
Honest residual: Heiser's own published retrospective on why the line stopped could not be located, the 1998 conclusions remain positive about the concept, and the surviving artifact of the Mungi decade is the 64-bit L4 rather than the address-space model; so the reason the line ended is recorded here as **unestablished** rather than assigned.

---

## CheriOS: the single-address-space CHERI microkernel, the existence proof for the deleted MMU

CheriOS (Lawrence Esswood's Cambridge microkernel, CTSRD-CHERI, a clean-slate design outlined by Robert Watson) is the working demonstration that **CHERI capabilities alone can carry a microkernel's entire spatial isolation in a single address space**: compartments share one address space and are separated by capability bounds, not page tables, and it runs a real workload there: multicore, a filesystem, an LWIP network stack, an NGINX webserver.
It is the app-class precedent for the normative deletion of the MMU (with CHERIoT the fully MMU-less microcontroller-scale sibling): the evidence that *"CHERI is the sole in-core spatial mechanism"* (§15) is buildable.
What the platform imports is the **thesis** (a single-address-space purecap system works and CHERI subsumes the MMU's isolation role), then takes one step further: `satp` is fixed to Bare, Sv39/Sv48/Sv57 and `Svadu`/`Svade` are absent, and the kernel has no VSpace, page-table, frame-mapping, map/unmap, TLB-shootdown, or demand-paging subsystem (§7, §8, §14, §15).

The deletion is a proof and timing simplification, not merely a memory-layout choice.
CHERI supplies byte-granular in-core spatial isolation and the physical-reach bound; capability-checked DMA and islands supply device confinement and cross-domain timing isolation.
Keeping Sv39 would therefore retain a second in-band mechanism whose page-table walker is an autonomous, address-dependent memory reader, directly conflicting with §15's ban on hardware walkers, updaters, and feedback loops.
Deleting it rather than exempting it removes the walker, TLB and walk-cache state, their `fence.t` and WCET terms, the VM subsystem, and their share of the Sail model; a composition-frozen page table would still keep the walker and its hidden state and is therefore not the same simplification.

The defense-in-depth trade is explicit.
An MMU could in principle provide a failure domain disjoint from CHERI, but this single-address-space design would use identity-shaped translation rather than per-compartment page tables, so that second layer would be largely notional while the walker cost remained real.
The platform instead verifies CHERI deeply (the RTL ⊑ Sail workstream, the CHERIoT-Ibex conformance result, and application-class CHERI evidence) and accepts that in-core spatial isolation has no in-band fallback: *verify rather than hedge*.
This is distinct from the rejected PMP-only descent: that design deletes CHERI and keeps a coarse mechanism; this one keeps the byte-granular primary and deletes only the redundant translation layer.

- **The kernel is verified, not de-privileged.**
  CheriOS's signature move is a **nanokernel**: a tiny trusted layer beneath the OS exposing integrity, confidentiality, and attestation primitives so that *"processes exist in mutual distrust with the OS they run on"*: an application need not trust the kernel with its secrets.
  This platform takes the opposite route to the same end; it **verifies** the kernel (seL4's design re-proved in Coq, §7) so it *can* be trusted, rather than architecting around distrusting it.
  CheriOS's de-privileging survives only as **defense-in-depth**, and scoped: the crypto core holds key material a compromised kernel *"can still only invoke… never exfiltrate"* (§15), fenced from the kernel by the crypto core's own hardware boundary and the seal/switch primitives (§7, §12, no PMP); the nanokernel's confidentiality applied to the crown jewels, not generalized, because the platform's primary lever is proof, not distrust.
- **Attestation is the RoT, not per-enclave foundations.**
  CheriOS's **foundations** are measured, hash-identified code enclaves carrying nanokernel-issued sealing/signing keys: *local* attestation among mutually-distrusting compartments with no central authority.
  The platform provides the same operations (measure, seal, attest) through the on-die RoT and the §12 sealing & attestation service (§9), anchored on the one inspectable trust root the "no foreign computers" die already has (§4), rather than a decentralized per-enclave primitive.
- **It deletes the MMU that CheriOS keeps.**
  CheriOS is single-address-space but **retains an MMU for demand paging and swap**; its point is only that the MMU is *not* the isolation mechanism.
  This platform removes the MMU **outright** (§15), which its **stateless, no-swap design** (§10: running system = immutable image + tmpfs + enumerated volumes, no demand paging) is what makes possible: with nothing to page, the paging role CheriOS's MMU still serves is gone too.
  So CheriOS proves CHERI-as-sole-*isolation*; statelessness is what lets this design drop the MMU as a *mechanism*, with CHERIoT the fully MMU-less proof at the small end; and, past the MMU, **CHERIoT is equally the existence proof for the platform's single privilege mode** (Machine-mode only, privilege carried by a CHERI permission on the PCC rather than an S/U ring), the privilege-architecture analog of the single-address-space thesis this entry imports, with first silicon and the completed CHERIoT-Ibex conformance proof behind it.

Convergent where it counts: CheriOS is **unverified purecap C** whose memory model pairs **CHERI-revocation temporal safety** (freed memory is revoked in a shared address space) with a novel temporally-safe **stack** and **Reservations**: private memory a component allocates *without trusting the allocator* (an integrity/confidentiality primitive, not a placement mechanism); its microcontroller sibling CHERIoT adds heap **claims** (a hold that keeps a shared allocation alive against the holder's quota) and the deterministic load filter: the same *temporal-safety-in-a-shared-address-space* discipline this platform reaches through the composition-time memory plan (§7, §8) ⋈ budgeted CHERI revocation (§8) ⋈ the `#![forbid(unsafe_code)]` source rule and the binary-level temporal-safety certificate (§5, §13).
CheriOS has the mechanism; this has the mechanism **and** the proof: the bcachefs/FSCQ relationship one layer down, in the kernel.
The honest residual is the other side of that deletion: in-core spatial isolation rests on CHERI alone, and application-class single-address-space purecap remains less battle-tested than page-table isolation because the strongest existence proofs are smaller systems.
CheriOS is the standing evidence that the road can be taken; the net deletion of the walker, translation state, VM subsystem, and proof surface is why this design takes it.

---

## CHERIoT: privilege as a capability on the PCC, memory protection by CHERI alone, the switcher and sentries, and the object model that needs no CNodes

If CheriOS is the app-class evidence for the deleted MMU, **CHERIoT** (Microsoft and lowRISC, contributed to the RISC-V standardization effort) is the import that reaches furthest into the running system: it is the source of the platform's privilege architecture, its domain-crossing mechanism, its loading structure, its memory-protection disposition, and, after the object-model deletion, its kernel object model.
It is also the most *fabricated* of the CHERI ancestors, with first silicon taped out in early 2026 and formal verification on two fronts (Oxford against the Sail model, completed for CHERIoT-Ibex; Google on the switcher's isolation properties, underway), which is why the platform is willing to rest so much on it.

**The existence proof has silicon.**
CHERIoT supplies the Machine-mode-only design, the PCC permission, the small switcher, sentries, and export/import tables in a fabricated system under active formal verification.
It is the privilege-architecture sibling of CheriOS's single-address-space result: the imported mechanism exists rather than being inferred from CHERI in the abstract.

- **Privilege as a permission, not a ring.**
  CHERIoT is Machine-mode only by design (*"hierarchical privilege modes are unnecessary, so CHERIoT CPUs support only Machine Mode"*), carrying privilege as *"a permission that allows access to certain control and status registers … when a capability with that permission is installed as the program counter capability."*
  This is the whole of §15's single privilege mode: a compartment cannot execute a privileged CSR access for the same reason it cannot forge a pointer, the authorizing **access-system-registers permission** being one no compartment's PCC carries, an unforgeable *absence* rather than a mode bit an exploit might flip (§7, §8, §15).
  The platform carries that model to application-class multicore, where a compartment is already confined by the capabilities it holds, so the S/U ring would be a second in-band privilege mechanism beside CHERI; gating CSR access, context switching, and sealing by an unforgeable PCC permission removes the S-mode CSR bank, trap delegation, `sret`, and `Sstc` together with their mode-transition reasoning from the kernel proof.
- **The switcher and sentries.**
  Its trusted **switcher** (~300 instructions, seL4-scale) mediates cross-compartment and cross-thread transitions holding one reserved register and is itself CHERI-constrained; its **sentries** are sealed entry points making domain entry an unforgeable jump rather than a mode transition.
  Both are imported directly (§7, §8, §15), and the in-order non-speculative core is exactly the target the permission-and-sentry model was designed for, the source noting it *"would be difficult on very large out-of-order cores"*, which this platform is not.
- **Compartment export and import tables in place of a container format.**
  CHERIoT replaces container-style loading with export and import tables and entry points sealed by a loader, and the platform adopts that **structure** for its content-addressed capability image (§13) while re-grounding it on this platform's own RV64 capability format and a verified Narcissus reader, **rejecting** CHERIoT's encoding and its unverified loader: the same adopt-the-structure, reject-the-encoding move the ISA profile makes for the rest of CHERIoT. The platform's format is itself narrowed (64+1 bits over a 36-bit address space, R-15-007), which makes the point sharper rather than softer: what is rejected is a *second* encoding forking the model (R-15-005), not the idea of narrowing one.
- **PMP dropped, on CHERIoT's own argument.**
  It drops PMP outright (*"the RISC-V PMP provides a subset of the protections of a CHERI system and so it, too, can be removed"*), its coarse region checks being a strict subset of CHERI's byte-granular protection, and that is the precedent §15 follows: once virtual-memory translation and privilege rings are gone, PMP would be a third in-band spatial mechanism and redundant Sail surface.
  More tellingly for a platform of this class, **Codasip's A730**: a dual-issue *application* core, not a microcontroller; removes the PMP unit on exactly this ground: *"Most RISC-V cores included a physical memory protection (PMP) unit… both costly in area and power hungry.
  With the fine-grained protection and compartmentalization of CHERI this unit can be removed and replaced by more power- and area-efficient circuits."*
  The CHERI research program (Cambridge/SRI, with Microsoft Research and INRIA) is the assurance base that makes dropping the coarse hedge defensible rather than reckless: CHERI's fundamental architectural security property, **reachable-capability monotonicity**, is *already machine-checked over a full-scale CHERI ISA* (Bauereiss et al., *Verified Security for the Morello Capability-enhanced Prototype Arm Architecture*, ESOP 2022, in Isabelle, via an abstraction that holds for arbitrary CHERI ISAs), so what remains for this profile is the **RTL ⊑ Sail** arrow (the least-built layer, §18) and a Coq-native restatement over the CHERI-RISC-V model, with the Oxford/Google CHERIoT-Ibex conformance proof the microcontroller-scale bring-up evidence and Codasip's shipping app-class core the evidence at this platform's own scale.
- **An object model with no CNodes, which is what let seL4's runtime layer go.**
  Capabilities live in registers and tagged memory, objects are named by **sealed capabilities**, and revocation is by **epoch and address-keyed load filter** rather than by a derivation tree.
  That answer is what makes untyped memory, retype, the capability space, and the CDT deletable once the object graph is fixed at composition (§7, §8), and §5 had already conceded the direction, describing what is proved as *"more precisely a CHERIoT-class static separation kernel that borrows seL4's object vocabulary"*; the deletion finishes that sentence by dropping the vocabulary too.
  Its heap **claims** (a hold keeping a shared allocation alive against the holder's quota) and its deterministic load filter are the same temporal-safety-in-a-shared-address-space discipline noted under CheriOS above.

**What transfers.**
A ringed per-core inventory would have M-mode *"quiescent after boot"* and the kernel as the sole S-mode occupant with U-mode *"everything else"* (§7): three rings for what is really *one trusted kernel beside many CHERI-confined compartments*.
The powerbox, the capability manifests, the ring data plane, and W^X are already **capability** statements, not ring statements.
Collapsing to one mode makes the enforcement substrate match the design the rest of the document already describes: authority is a capability, top to bottom.

**Contrast with PMP-only systems.**
MultiZone-style systems share the silhouette of a Machine-mode kernel but shed CHERI and fall back on coarse PMP plus trap-and-emulate authority.
The CHERIoT line does the opposite: it removes the rings while retaining CHERI as the byte-granular primary and governs privilege through unforgeable capabilities.

**Where PMP's three roles go.**
A MultiZone-style locked-PMP backstop would serve three coarse crown-jewel roles, each of which instead collapses onto a mechanism already present: (a) **immutable-text / W^X** on kernel and firmware text and the read-only content-addressed image is the CHERI capability-monotonicity invariant of §14: no writable capability to those regions is ever derived, so there is nothing for a second mechanism to re-enforce; (b) the **per-core physical-partition bound** is CHERI, each core's kernel instance is delegated a root capability bounded to its partition, and monotonicity (§7) lets it derive nothing outside it; (c) **crown-jewel secret fencing** is the crypto core's own hardware boundary plus **sealed capabilities** (§8), keys never leave the core, and what is resident outside it is reached only through a seal (blanket TME would discharge the role by taxing all of memory to protect key schedules; the capability-scoped form is the same move the design makes everywhere else, and is also exactly the scope of the stacked realization's link encryption, §15).

**Residual: one privilege mechanism.**
The S/U ring gave (a) a hardware-privilege boundary preventing an app from executing privileged instructions regardless of CHERI, and (b) the privilege-layering that let the **PMP backstop** sit *below* the kernel.
Both are answered.
(1) In the CHERIoT model, privileged instructions are gated by the **PCC system-register permission** no compartment's PCC carries: the unforgeable absence above, not a mode bit an exploit might flip.
(2) The crown-jewel backstop role needs **no privilege ring** and, as the three re-homed roles above record, no PMP either: its roles rest on mechanisms already present, while the hedge against a CHERI logic fault is CHERI's verification rather than a coarse disjoint layer.
The boot/M-mode firmware still runs first, establishes the initial capability distribution, and goes quiescent; the microkernel is the resident Machine-mode holder of the system-register permission; nothing else holds it.

**Residual: loss of a disjoint failure domain.**
PMP's unique value is that it is **disjoint from CHERI**: an independent failure domain that would still bound each core if the CHERI machinery itself had a *logic* fault.
Dropping it means in-core spatial isolation, W^X, and the partition bound rest on **one** mechanism with no in-band redundancy.
This is answered the way the whole platform answers single-mechanism concentration: not with a second mechanism but with **proof**: CHERI is the mechanism the design verifies most deeply (the RTL ⊑ Sail workstream §18, the Oxford/Google CHERIoT-Ibex conformance result, Codasip's shipping app-class core), so the hedge against a CHERI implementation fault is the *verification* of CHERI, not a coarse subset of it running alongside.
And the residual that actually persists: fabricated silicon vs. verified RTL; is unchanged by keeping or dropping PMP (both share the one mask set, §17), so PMP bought no protection against it.

**Scope and re-admission boundary.**
Resting all in-core spatial protection on CHERI is the same wager as single-address-space and single-privilege-mode, with no coarse fallback at all.
It is bounded, not blind: CHERI is byte-granular, formally modeled, and the most-scrutinized mechanism on the die; capability-checked DMA still confines device access and the islands still bound cross-domain timing (neither was ever PMP's job); and the disjoint hedge is replaced by the strongest assurance the project has.
If a future analysis judged the CHERI-logic-fault residual intolerable, the composition-static locked-PMP backstop is the cheapest thing to re-admit (subtractive, static, Sail-modeled): but it is not carried by default.

Two further corroborations arrive from the same source without being imports: **CHERIoT-Ibex is cacheless**, running from tightly-coupled SRAM, which is standing evidence that a cacheless core is a conformant RISC-V profile choice rather than a fork (§15); and **capability-holding DMA is demonstrated at CHERIoT scale**, which is the microcontroller-scale existence proof beneath the capability-checked DMA fabric that replaces the IOMMU (§15).
What is declined is its **autonomous sweep engines** (the TBRE and STKZ background walkers), which are exactly the autonomous memory-touching engines admission test 5 excludes (§8), so revocation here is budgeted and scheduled rather than engine-driven.

**What the platform takes.**
Supervisor and User modes are **deleted**: the platform runs Machine mode only, privilege is the CHERIoT-lineage access-system-registers permission on the PCC, the S-mode CSR bank / trap delegation / `sret` / `Sstc` are removed (§15), and the microkernel is the resident Machine-mode holder of the system-register and switch/seal authority (§7); the S/U ring's one non-redundant service, a sub-kernel backstop, is itself dropped as redundant against verified CHERI.
PMP and `Smepmp` are **removed** with them: CHERI is the sole memory-protection mechanism, W^X and the per-core partition bound rest on CHERI monotonicity (§7, §14), crown-jewel secrets on the crypto core's boundary and the seal/switch primitives (§7, §12), and device DMA on capability-checked DMA (§15), so CHERI is the sole in-band spatial mechanism and no disjoint backstop remains.
The platform axiom decides it as ever, with the twist the whole design turns on: what lets a **single** mechanism replace a defense-in-depth stack is that this one is **formally verified**, so *delete rather than defend* becomes *verify rather than hedge*.

**Honest residual (§17):** privilege, in-core spatial isolation, W^X, and the per-core partition bound all rest on CHERI alone, with no privilege ring, no PMP, and no in-band disjoint backstop, so the sole hedge against a CHERI logic fault is CHERI's own verification (the machine-checked monotonicity result above), leaving the **RTL ⊑ Sail** arrow (§18) the residual and the fab residual unchanged; that concentration is offset against the deletion of the mode-transition machinery, the S-mode CSR bank, and trap delegation from both the microarchitecture and the kernel proof.
The second residual is scale: CHERIoT is **single-core and microcontroller-scale** (2–7-stage pipelines, tens of KiB to MiB) and its own multicore is future work, while this platform is an **application-class multikernel** on multicore, so single-privilege-mode purecap is unproven at application-class multicore scale and every one of the imports above is a genuine extrapolation of scale, the privilege-architecture sibling of the single-address-space bet.
It is bounded rather than blind: privilege-as-capability is *more* fine-grained and *more* uniform than the ring it replaces, which is CHERIoT's whole thesis; the extrapolation is carried by a verified kernel and verified CHERI and lands on an in-order non-speculative core of the kind CHERIoT's permission and sentry model was designed for rather than a large out-of-order machine; and the model it ships is the one being extrapolated, not a paper design.

---

## Capability-checked DMA: the Cambridge/SRI proposal and the CHERI-at-SoC-Level integration discipline at the device edge

Deleting the IOMMU (§15) needs something to take its place at the device edge, and the replacement is not invented here: it is proposed and prototyped in the CHERI programme's own SoC-facing work, which extends capability protection from the cores out into the interconnect.
The platform takes that extension instead of an IOMMU or an **IOPMP**: in a single physical address space translation is unused, while CHERI supplies the protection role unforgeably and at byte granularity without a second page-table walker or region table.

**A unified spatial mechanism, not device-side PMP.**
Every DMA-capable block becomes one of two capability-checked shapes: a **core-issued capability-operand mover** (the §15 coprocessor-line discipline the matrix and FEC units already follow: no independent mastership), or an **autonomous streaming engine holding a delegated, bounds-checked, revocable capability** for its window (scanout, transceiver-I/Q, NIC), with the fabric checking each access against a capability at the point of issue.
This both **deletes translation** and is stronger than switching to an IOPMP: the IOPMP would confine DMA, but as a coarse, ambient, per-source-ID region table **disjoint from CHERI**, the device-side version of the in-core PMP the CHERIoT precedent already drops (above).
Adopting IOPMP would trade the IOMMU's translation weight for a *second ambient spatial mechanism*; adopting capability-checked DMA *unifies* the device path onto the one mechanism the die already carries, so "who may DMA where" is a capability in the static topology (§7/§8), not a side table: *verify rather than hedge* taken to the device edge, and a device MSI (a store to an interrupt file, §8) confined by the same check rather than an interrupt-remapping table.

**The prior art is proposed and prototyped, not hoped for.**
**"Defending Direct Memory Access with CHERI Capabilities"** (Markettos, Baldwin, Bukin, Neumann, Moore, Watson; Cambridge and SRI, HASP 2020) proposes exactly a **capability-configured DMA controller** that bounds-checks accesses from malicious peripherals, pluggable and SoC-embedded alike, and contrasts it directly with the IOMMU's nested-page-table translation, which is the argument §15 makes when it declines translation and keeps only protection.
The **CHERI Alliance's "CHERI at SoC Level"** guide (2025) then supplies the integration discipline the mechanism actually requires: passing **capabilities, tags, and revocation** between CHERI-enabled IP blocks of varying CHERI-awareness, and clearing tags on writes from non-capability IP.
Capability-holding DMA is demonstrated at **CHERIoT** scale with first silicon in 2026 (above), so the small end is built even though the application-class bandwidths for NIC, scanout, and radio I/Q are net-new (§18).

**The deletion is sound only because of a precondition this design supplies and a general-purpose machine cannot.**
The device model is already curated register-slave, transducer, and on-die RTL (§4, §12), so there is **no foreign PCIe bus-master ecosystem issuing raw physical addresses** for an IOMMU to catch in the first place.

**What does not transfer: retrofitting opaque accelerators.**
A newer result from the same group, **CapChecker** (*"Adaptive CHERI Compartmentalization for Heterogeneous Accelerators"*; Cheng, Markettos et al., ISCA 2025), takes the converse tack to the native path above: it interposes a capability-checking unit at the memory interface of a **CHERI-*unaware*** accelerator, so unmodified (often third-party or opaque) accelerator IP gains fine-grained protection cheaply.
That is exactly the road §4's no-foreign-computers mandate forecloses: the unaware, self-mastering, opaque accelerator is the category it excludes by name, and the coprocessor line (§15) makes the compute units (V/M-class, FEC) CHERI-native, core-issued capability-operand movement, no independent mastership, so no unaware self-mastering block remains to wrap.
Its checking *function* is in any case what the capability-checked fabric above already performs at the point of issue: for the curated firmware-free streaming engines the platform does keep, the fabric *is* the checker, and a CapChecker shim would be the hedge *verify rather than hedge* declines.
What survives the mandate is CapChecker as a **feasibility datapoint**, boundary capability-checking on real heterogeneous accelerators at low single-digit overhead (quantified in performance-estimates.md), corroborating that the capability- and tag-carrying-fabric obligation below is cheap, rather than as a reason to admit the CHERI-unaware accelerator it was built to rescue.

**New obligations introduced.**
Dropping the IOMMU removes the one DMA-side mechanism *disjoint* from CHERI, so device access now rests on CHERI too: the single-mechanism concentration the PMP drop books, extended to the device edge, hedged the same way (CHERI's own verification: RTL ⊑ Sail §18, the Oxford/Google CHERIoT-Ibex result).
Two obligations are genuinely new relative to a translation-IOMMU and are booked in §17: (1) **in-flight-DMA revocation**: a capability held by a running transfer must honour the §8 revocation sweep so time-to-containment stays bounded (a load-barrier / revocation-epoch check, Cornucopia-Reloaded-lineage, or bounded re-authorized windows); (2) a **capability- and tag-carrying fabric**: the interconnect must propagate capabilities, tags, and revocation state to the DMA blocks (new Sail / RTL ⊑ Sail surface, §15/§18).
Application-class capability-DMA at NIC / scanout / radio-I/Q bandwidth is net-new (§18); microcontroller-scale is the existence proof.

**What the platform takes.**
The IOMMU is **deleted** and the IOPMP **declined**: device DMA is capability-checked by the fabric, every DMA-capable block is a core-issued capability-operand mover or a delegated-capability-holding streamer, and CHERI becomes the sole spatial mechanism **system-wide**: cores and devices alike.
The platform axiom decides it as ever: the IOMMU is a second, device-side spatial mechanism (carrying a walker and caches the profile bans in-core), redundant once the fabric carries capabilities, and the IOPMP is the coarse subset of CHERI it is in-core.
**Honest residual (§17):** device access rests on CHERI alone with no IOMMU-disjoint backstop; in-flight-DMA revocation and a capability/tag-carrying fabric are new obligations (Markettos-2020 and the CHERI-at-SoC-Level guide anchor feasibility, Cornucopia-Reloaded the revocation), and application-class capability-DMA is net-new (§18), microcontroller-scale the existence proof.

---

## Register allocation, region inference, and static memory planning: the heap deleted as a runtime mechanism, the way the MMU was

The CHERI OS line keeps a **runtime heap allocator** and makes it *temporally safe*: CheriOS and CHERIoT revoke freed memory in a shared address space (above), CHERIoT adding heap claims and a deterministic load filter so a dynamic heap can be reused safely across mutually-distrusting compartments.
This platform keeps that temporal-safety machinery (§8 imports exactly the load filter and revocation epoch) but moves on a *different* axis: it deletes the **allocator itself**, the runtime component that decides *where* an object lands, and replaces it with a whole-program **static memory plan** the compiler computes ahead of time.
The move is therefore orthogonal to CHERI's temporal-safety story and composes with it (placement ⋈ temporal-safety, §8), not a supersession of it: what the platform still owes the freed-then-reused slot is the same revocation the CHERI line already supplies.
Five independent lines converge on that static-planning move, none of them an OS and none of them CHERI, so the import is method, not code, exactly the *"methodology is portable, maturity is not"* pattern this document opens with (§5).

- **Register allocation via graph coloring** (Chaitin et al., 1981, and the field since) is the origin move: a whole-procedure static analysis builds an **interference graph** (nodes are values, an edge joins two whose live ranges overlap) and colors it with the finite register set, deciding every placement **once, ahead of time**, so nothing at runtime searches for a free slot.
  The platform's static memory plan (§8) is this exact algorithm re-targeted from a small register file to SRAM: objects are the nodes, CHERI-bounded slots are the colors, and the certifying compiler's linear/affine ownership tracking (§5, §13) supplies the live ranges register allocation gets from SSA.
- **Region-based memory management** (Tofte and Talpin, 1997; carried into systems form by Cyclone's region types, Grossman/Morrisett) supplies the half graph coloring alone does not: *where do live ranges come from, and how is freeing proved sound*.
  Regions are managed by a type-and-effect discipline, stack-discipline nested (a *laminar* lifetime structure, the tractable corner of the offline problem below), with **dangling-pointer-freedom a machine-checked theorem** and no garbage collector; **Typed Memory Management in a Calculus of Capabilities** (Walker, Crary, and Morrisett, 1999, hereafter WCM) sharpens it to non-lexical region lifetimes governed by **static capabilities**: compile-time tokens, checked and then *erased*, that authorize access and deallocation with no runtime representation at all.
  That is exactly where the platform's own step lands: it keeps the region discipline but gives the static capability a **runtime** realization as a CHERI capability, so one word now spans the compile-time token WCM checks and the hardware token that bounds the slot at runtime: the coincidence the design is built on, and a re-homing WCM does not itself make (its capabilities are erased, not enforced in silicon).
- **Static memory planning in ML compilers** (XLA's ahead-of-time buffer assignment; Apache TVM's Unified Static Memory Planning; TensorFlow Lite Micro's fully precomputed, allocator-free arena) is the deployed-at-scale existence proof: production compilers already do **liveness-driven buffer assignment**, sharing one buffer among tensors whose live ranges provably never overlap, over gigabyte-scale graphs, and TFLite Micro pushes the same technique down to a **heap-free microcontroller runtime** with no allocator at all.
  What transfers is the evidence that the technique scales in both directions the platform needs it to: desktop-scale graphs and microcontroller-scale absence of any allocator at all.
- **Pony's reference capabilities and Project Verona's regions** supply the same argument from the concurrency side, and one citation in particular is the cleanest statement of the whole pattern: Pony's **ORCA** collector needs neither read nor write barriers *because* the deny-capability type system (six reference capabilities, of which `iso`, `val` and `tag` are sendable) already guarantees data-race freedom, so a static discipline deletes a runtime mechanism outright rather than optimizing it. Verona carries the idea to a coarser and more relevant unit, the **region** as the thing owned rather than the object, which is independent evidence for the granularity §8's plan already chose; it remains a research language, its authors saying plainly it is not ready outside research, and its centre of gravity has moved to applying regions to Python. One caution travels with both, because the register's readers will otherwise mis-hear the word: **"capability" means three different things** across this literature, an unforgeable authority-conferring reference in the E sense, a bounded and permissioned handle in the CHERI and Capsicum sense, and an alias-permission annotation in the Pony and Verona sense, which is closer to a Rust borrow than to either. Any citation that puts them in one sentence disambiguates or misleads.
- **Compile-time reference counting and lifetime analysis in shipping languages** is the same move proven at *language* scale rather than inside an ML compiler.
  **Lobster** (van Oortmerssen) picks a single owner for each allocation and demotes the rest to borrows, eliding **~95% of runtime reference-count operations at compile time** and allocating `struct` values inline with no heap (Nim's ARC descends from it); **ASAP** (Proust, *As Static As Possible*, Cambridge, 2017) is the fully-automatic, annotation-free limit, a static analysis that inserts each deallocation the instant a block is provably dead; and the compile-time-garbage-collection line (Mercury's structure reuse, Mazur et al.; Koka's **Perceus** reuse analysis, PLDI 2021) drives the same liveness facts into in-place reuse.
  Each shows ownership/lifetime analysis *already* moving most memory management to compile time; what none takes is the limit this platform does: they keep a runtime allocator (Lobster's fast heap, ASAP's inserted frees) for the residual, where the platform deletes it and checks the resulting *placement* on-device (below).
- **Robson's fragmentation bound** (Robson, 1974 and 1977) is the impossibility result that motivates leaving the online allocator out rather than tuning it: any *non-relocating, online* allocator can be forced to a footprint a **factor of Θ(log n)** above the peak simultaneously-live bytes, where **n is the ratio of the largest to the smallest block size** (not the number of allocations), by an adversarial or merely unlucky request sequence, a bound no packing heuristic escapes because the sequence is chosen after the strategy is fixed (first-fit meets it to within a constant; best-fit is *almost as bad as any strategy could be*, which is the 1977 paper's actual result).
  The platform does not import Robson's allocators (first-fit, best-fit); it imports the **boundary the theorem draws**, and steps to the *offline* side of it, where the whole allocation sequence is known in advance: no free lunch either, since general offline placement is **NP-hard** (Garey–Johnson's *dynamic storage allocation*), but it is **constant-factor approximable** (Gergov's 3-approximation, Buchsbaum et al.'s 2 + ε) and **exactly optimal in polynomial time for the nested, region-structured lifetimes** a region discipline produces (a laminar family, where stack allocation is optimal), and every part of it is paid in **build-time compute, the platform's cheapest currency** (§15).

None of these five is a CHERI or capability-OS artifact, and none is convergent evidence for an *operating system*: they are compiler, language, and PL-theory results the platform re-homes onto its own capability substrate, the same transformation the document performs on Chaitin's coloring, Tofte/Talpin's regions, and TVM's planner in turn.
The synthesis is what none of the five states alone: a whole-program static plan, expressed in ownership and region types, realized at runtime as CHERI capabilities, and admitted onto the device as a **decidable interference side-condition of the on-device TAL type-check** (§6) rather than as trusted allocator bookkeeping: an overlapping plan is a *type error*, rejected (an availability outcome), never admitted unsafe, so the deletion is checked, not merely engineered.
That last step is itself lifted, not invented: the on-device checker is a **Typed Assembly Language** type-checker (Morrisett, Walker, Crary, and Glew, *From System F to Typed Assembly Language*, 1998), which re-verifies a type-annotated binary independently of the compiler that emitted it, and the calculus of capabilities above is exactly the region-memory discipline that *compiles to* such an assembly (its stack-typed variant, Morrisett/Crary/Glew/Walker 1998, is the laminar case rendered in the machine); so *"checked, not trusted"* is the standing TAL **soundness metatheorem** (well-typed ⇒ safe, §6), not a fresh assertion this design must originate.
Honest residual: none of these sources targets a capability machine or a formally verified admission checker, so the interference-coloring-as-TAL-side-condition step is net-new to this design and unproven at the scale a real device's whole-program allocation graph would present; and forgoing the runtime heap is itself long-standing safety-critical practice rather than an invention here (MISRA C bans dynamic allocation outright; TFLite Micro ships allocator-free), so what is novel is not abstaining from `malloc` but *synthesizing* the plan and *checking* it on-device.
The counter-evidence is booked too: **Vale** (Ovadia) reaches memory safety by *runtime* generational references and is only now adding region borrowing to elide them, a modern language concluding that full static placement is hard enough to make a runtime check the pragmatic default: so the platform is making the harder bet, that whole-program static composition (§7) is the setting where the static side wins.
Like every static, compose-time-checked mechanism in this document, its soundness is then only as good as the ownership/region typing it is built on (§5, §13), the same residual the certifying compiler's other obligations already carry.

---

## Project Oberon: whole-stack parsimony as a method, the quiescent point for deferred bulk work, and the module key as load-time admission

Oberon is the one ancestor in this document that co-designed the **whole stack under a single axiom**, and the only one whose axiom is this platform's own with the currency changed.
Wirth and Gutknecht's system (1987, on the NS32032 Ceres workstation) is at once a language, an operating system, a compiler, and a graphical environment; the 2013 re-implementation adds the machine underneath it, a **RISC5 processor of fourteen instructions and sixteen registers in a few hundred lines of Verilog** (later restated in Wirth's own **Lola-2** logic-description language), and publishes the entire result, gates to graphical user interface, as one readable book.
Every other entry here contributes a layer: seL4 a kernel, SECOMP a compiler, CVA6-CHERI a core, Cerebras a fabric.
Oberon contributes the *posture* of holding all of them at once, and it is the only prior art that has actually done so.

**The axiom, and the currency it must be changed into.**
*A Plea for Lean Software* (1995) argues that complexity is routinely mistaken for sophistication, that the incomprehensible should draw suspicion rather than admiration, and that **a system not understood in its entirety by a single individual should probably not be built**.
Read literally that is a rule this platform breaks deliberately: §4 spends engineering without limit, and the Sail model, the Coq development, and the RTL will not fit in one head between them.
What survives the translation is that Wirth's scarce resource was *implementation effort* while this one's is *review*: §5's independent-specification review gate, the crown-jewel specifications it audits, and the atomic-requirements register are all audits performed by people, and a corpus too large to audit fails **silently**, by being approved unread, where a corpus too large to build fails loudly.
So the rule imports in the only form the platform can act on: the size of the *audited* artifact is a budget like any other, and the import still owed is to publish it as a per-layer ledger tracked by the same tool that holds every other derived count (§5), so that an unreviewable corpus is a failing check rather than something a reviewer has to notice at the gate.

**The quiescent point: evaluated here and declined.**
Oberon's collector is an ordinary unsynchronized mark-and-sweep, and it is cheap and precise for a structural reason rather than an algorithmic one: it runs as a background task the central loop schedules only when **no command is executing**, so no procedure activation exists, the stack holds nothing to trace, and the root set is exactly the module-level pointer variables.
Wirth did not make the collector safe against a mutator; he made concurrency with the mutator **impossible**, and paid for it in the one currency he had, latency between commands.
The rule was proposed here for §8's revocation sweep, binding its quanta to the **slot boundaries of the domain being swept** rather than letting them interleave with compartments holding live capabilities, on the ground that what it buys is not a mechanism but a **deleted proof obligation**, which is the currency §17 counts.
It is declined, and the reason is worth keeping in this document rather than only in the register of declinations: **the obligation it offers to delete is one this design deleted another way, and the artifact it acts on does not exist here.**
There is no root set to make static, because R-08-004 deleted the capability derivation tree and the traversal with it: the revocation bitmap *is* the mark, one architectural bit per granule written by the kernel at teardown, and `creclaim` is a linear pass over granule groups rather than a reachability trace.
And the overlap argument the quiescent point exists to remove is one this design never has to make, because R-08-005 puts *freed ⇒ unreachable* at **access** time: a per-load filter invalidates a stale capability the moment it is loaded, whether or not a sweep quantum was running beside it.
Oberon needed the quiescent point because it had no load barrier to buy instead.
The full evaluation, its two smaller grounds, and the one result that would reopen it are in [Evaluated Architectural Alternatives](architectural-alternatives.md).

**The module key: interface consistency as a load-time refusal.**
Oberon compiles a module's interface into a **symbol file** carrying a key, compiles every client against that key, and has the loader **refuse** a client whose recorded key does not match the module actually present: no negotiation, no version range, no compatibility shim, no partial link.
It is the oldest working instance of the discipline §13 states as safety being a property of the artifact rather than of its pedigree, and it makes the check at **load** time rather than trusting the build to have been consistent, which is the same relocation of trust the content-addressed source closure and the CHERI-TAL admission pass make (§10, §13).
The one refinement ETH Oberon later added, fine-grained interface fingerprinting so a module's interface can be *extended* without invalidating its clients, is deliberately not taken: here a changed interface changes the content address, the old binary is a different artifact, and admission has no notion of a compatible change to be lenient about.

**Oberon-07 as the precedent for the deletion gate.**
The language was revised in 2007 and again in 2008, 2011, 2013, 2014, 2015, and 2016, almost entirely by **removal**: `WITH`, `LOOP`, and `EXIT` deleted outright, `RETURN` confined to the end of a function, implicit numeric conversion replaced by explicit `FLOOR` and `FLT`, imported variables and structured value parameters made read-only.
Wirth's criterion was compiler cost; the criterion here is proof cost, and §15's frozen profile together with the *rejected profile simplifications* table in [architectural-alternatives.md](architectural-alternatives.md) runs precisely that gate over an instruction set instead of a grammar.
The transferable part is that the deletions kept arriving for nine years after the design was nominally finished, which is the posture a frozen profile has to hold if freezing is not to mean fossilizing (§15, §18).

**Two convergences, from the parts of the family that went this platform's way.**

- **Active Cells** (Gutknecht's group at ETH) maps Active Oberon *cells* onto separate processors of a system-on-chip built on an FPGA, wired by explicit channels and composed statically before anything runs: the multikernel arrived at from the language side, where Barrelfish arrives at it from the operating-system side (above) and Cerebras from the fabric side (above).
  Three independent derivations of share-nothing plus explicit messages is the strongest form the convergence argument takes anywhere in this document.
- **Oberon-V**, earlier *Seneca* (Griesemer, ETH, 1990 to 1993), is the family's vector dialect: whole-array operations and an `ALL` statement whose semantics are **order-independent by construction**, so vectorizability is a syntactic property the program states rather than a conclusion a dependence analyzer has to recover.
  That is the source-level shape the V-class graphics and machine-learning work wants (§15), and it rhymes exactly with §11's syntax-directed WCET derivation: both refuse to let a compiler *discover* a property the program could have *declared*, because a discovered property is one an analyzer can lose.

**Where Oberon is a counter-example rather than an ancestor.**
The Oberon system has no protection of any kind: one address space, no processes, no rings, no capabilities, and a command that can reach any exported variable of any loaded module.
Its safety is entirely the language's, resting on the premise that every instruction came from the trusted compiler and that nobody reached for the `SYSTEM` escape, which is the **language-based-isolation pole** the alternatives document rejects as a sole mechanism and the exact reason CHERI is kept for the unverified residual.
The rest of the family's system mechanisms (executable text, the collector, load-time module linking, Active Oberon's condition monitors, Juice's syntax-tree mobile code, and RISC5 as a candidate substrate) are weighed one at a time in [architectural-alternatives.md](architectural-alternatives.md), and none of them imports.
What imports is the method, the quiescent point, and the module key.

---

## Muen: the policy compiled into the system, the cyclic executive already shipping, and the generator theorem that is the right shape

**Muen** (codelabs GmbH, originally HSR Rapperswil; Buerki and Rueegsegger) is an x86-64 separation kernel of some three to four thousand lines of SPARK 2014, and it is the closest living relative of this platform's composition story and of its scheduler.
Its system is an XML **policy** stating the hardware, the subjects, their memory, their channels and events, their device assignments, and their schedule; the toolchain compiles that policy into SPARK sources, the physical memory layout, the page tables, and a per-CPU kernel running the specified schedule, and the compiled policy then sits in read-only memory that no subject can reach.
Nothing is allocated after boot and no subject is created at run time.
Its schedule is a **fixed cyclic executive**: minor frames grouped into major frames that synchronize the CPUs, driven by the VMX preemption timer, needing no preemption to hold.
And it ships: secunet's BSI-certified Communicator H and Nitrokey's NetHSM both stand on it, which makes it the existence proof that a table-driven executive survives contact with a product.

**The import is the generator theorem, because that is the shape this platform's own composition claim has to take.**
Haque, D'Souza, Habeeb, Kundu and Babu (ATVA 2020) observed that Muen is not a system but a *generator*, so the object worth verifying is neither the built image nor the toolchain's forty-one thousand lines: they prove by **conditional parametric refinement** that for every input policy meeting stated side conditions the generated system refines an abstract specification carrying the separation property.
That is the difference between an image whose correctness is a fresh informal argument each time and a composition compiler carrying a theorem quantified over admissible compositions, which is what §7's static composition needs if the graph the proofs are about is to be the graph the machine runs.
It is the strongest precedent in existence for that move and it is still weaker than the obligation here in four ways it states about itself: post-facto rather than co-developed, discharged by Z3, CVC4 and Alt-Ergo rather than by a proof object a second checker can replay, demonstrated on twelve configurations, and resting on the assumption that page-table translation and the VMX instructions behave as modelled.

**What the project ships as proved is narrower than its reputation, and the distinction is worth stating once.**
GNATprove discharges **absence of run-time errors at source level** and nothing beyond it; the project itself calls verification of kernel properties ongoing.
Absence of run-time errors is memory safety plus totality over the SPARK subset, which CHERI and a verified compiler give this platform at the binary rather than the source and more cheaply (§5, §13); it is not separation, not noninterference, and not functional correctness.
So the sentence "Muen is a formally verified separation kernel", read as a separation claim, overstates the shipped artifact by a wide margin, and the honest reading of the whole branch is the one §7 already implies: the certified and near-certified systems have the static composition and the cyclic executive without a security theorem, while seL4 has the security theorem only by assuming the static partition schedule those systems ship (the seL4 entry above), with timing channels outside it either way.

**What is declined beyond the prover.**
Separation by VT-x and VT-d is coarse-grained and rests on an enormous undocumented microarchitecture, which the ATVA assumption list makes literal: the hardware model is assumed rather than verified, where §15's in-order, non-speculative, cacheless profile exists precisely so that the model can be the artifact and §18 can close RTL against Sail.

---

## Verisoft and VAMP: pervasive verification's first attempt, and the communication chapter the TDM interconnect deletes

Where Oberon held the whole stack in one head, **Verisoft** (2003 to 2007, Paul's group at Saarbrücken, with VerisoftXT after) is the earliest ancestor to hold the whole stack under *proof*: **pervasive verification**, the insistence that applications, kernel, compiler, and processor be verified as one stack with no informally-trusted seam between layers, stated as a program two decades before end-to-end composition became the field's ambition.
Its **VAMP** processor was verified at the gate level in PVS (Tomasulo out-of-order execution, precise interrupts, floating point, a TLB); above it sat a verified compiler, the VAMOS microkernel, and application programs.
What it contributes here is the *shape of the obligation* rather than an artifact: no VAMP-lineage code or proof imports, and two of its findings land in this design as structure rather than as work.

- **The hardest chapter is deleted rather than inherited.**
  Verisoft's deepest result was the automotive stack: a gate-level FlexRay-like bus, processor correctness, program correctness, and worst-case execution time fused into one unified mathematical theory, *because bus arbitration made interconnect latency input-dependent* and the composed timing claim could not be stated per-component.
  The §15 TDM NoC makes interconnect latency a compose-time constant, so the §11 admission artifact (R-11-017) needs no communication theory at all: the one prior art for a multikernel-shaped composed timing claim wrote that chapter the hard way, and a hardware choice here buys its absence.
- **Devices are the determinism boundary.**
  Verisoft modeled devices as concurrently-operating objects beside the processor, precisely because folding them into a deterministic step function is where external timing silently disappears.
  This design does fold them, execution being a function of the whole-system input (§5), and the fold is honest only because R-05-156a defines the input to carry every device arrival's content and cycle timing and obliges the §8 policy model to name which of those observations it equates: the concurrency Verisoft modeled explicitly is pushed into the input vocabulary visibly rather than lost.

The cautionary half is the prover story: the stack was split across PVS and Isabelle, so the one theorem pervasive verification aimed at never closed as a single machine-checked object.
That is the precise failure mode the single-prover discipline (§5, §13) exists to preclude, and the reason the apex statement lives in one Coq file rather than a federation.

---

## Fedora Atomic: immutability as the base-image discipline

Fedora Atomic (rpm-ostree; Silverblue / Kinoite / CoreOS) is the desktop-scale demonstration that the base OS can be an **immutable, versioned, atomically-updated, rollback-capable image** rather than a mutable pile of packages, layered on the content-addressed libostree object store the **OSTree** entry below covers.
§10's **immutable base** and §11's **image-based atomic A/B updates with health-gated auto-rollback** are that discipline, and §10's **statelessness** (running system = immutable image + compiled config + enumerated mutable volumes, everything else tmpfs) is its logical endpoint.
The spec then hardens it past what a Linux image can offer: the image is **content-addressed Merkle, signed, and runtime-verified against the boot-attested root** (§9, §10), reproducible bit-for-bit, with the **anti-rollback floor sealed to the RoT monotonic counter** (§9, §11).
Fedora Atomic's *user-facing* rollback (prior deployments in the GRUB menu, `rpm-ostree` package diffs) is taken further and re-grounded: the **rollback-manager UI** (§12) presents a signed, version-control-style history whose every point and diff (changed image objects, typed config to/from changes, reference-manifest versions) is **reproducible and signed** (§9, §10), bounded by the anti-rollback floor and gated by the unlock credential (§9), and the boot-time selector is a **measured boot into a signed recovery generation**, not GRUB's unverified pre-kernel menu.
Immutability stops being a *deployment convenience* and becomes an *attestable integrity property*.

---

## secureblue: the hardening ethos, carried from mitigation to proof

secureblue is a security-focused, hardened derivative of the Fedora Atomic base: a hardened allocator, kernel-hardening flags, attack-surface reduction, GrapheneOS-influenced defaults.
It contributes the *ethos* the spec elevates to a goal (**G1** minimal attack surface, **G2** defense in depth) and the specific stance that a desktop should be aggressively hardened **and** immutable at once, with the browser (the largest attack surface) **maximally contained** (§14).
Where the design parts company is on the *nature of the guarantee*: secureblue composes **probabilistic mitigations** on a fundamentally memory-unsafe substrate, and this spec's own admission logic rejects mitigation-as-security wherever a proof is available: ASLR, stack canaries, CFI/landing-pads, and MTE-style tagging are **obviated by CHERI + proof and explicitly excluded**, on the *"~93% catch rate is a statistic, not a theorem"* disposition (§15, §17). secureblue is therefore the hardening ancestor whose *direction* the spec follows to its terminus: **delete the bug class by construction**, rather than raise the cost of exploiting it.

---

## GrapheneOS: the mobile hardening ethos, and the seized-device threat model it names

GrapheneOS is the reference **security- and privacy-hardened mobile OS**: an AOSP derivative that carries phone hardening further than any shipping alternative: a hardened memory allocator (`hardened_malloc`), hardware memory tagging (MTE) on by default, a hardened kernel and libc, exec-based app spawning, sandboxed Google Play run as an ordinary unprivileged app, the Vanadium browser with its JIT disabled, and a permission model stock Android lacks: per-app **Network** and **Sensors** toggles, and **Storage / Contact Scopes** that hand an app a curated view while it believes it has full access.
It is the project **secureblue's** *"GrapheneOS-influenced defaults"* (above) descend from, so its **exploit-mitigation, sandboxing, and permission** contributions land at *secureblue's terminus*: the memory-corruption class is deleted by CHERI ⋈ revocation ⋈ the CHERI-TAL's definite-initialization attribute rather than raised in cost by `hardened_malloc` and MTE (MTE is explicitly excluded as CHERI-redundant, §15); the JIT-free contained browser is §14's per-origin, software-rendered one, already harder than Vanadium; exec-spawning and zygote ASLR are moot with no `fork` and a single address space (§8, §15); and the permission model is **obviated by construction**: an app holding no network or sensor capability cannot reach the resource (§8), and *"the filesystem is a private, manifest-backed namespace"* (§14) **is** Storage Scopes without a compatibility shim, a contacts service handing out attenuated capabilities **is** Contact Scopes.

Where GrapheneOS is genuinely **additive** is the axis it contributes to §3's evil-maid-plus-remote model: **operational security for a device physically in an adversary's hands.**
The dominant forensic-extraction target is a powered-on phone unlocked at least once, its per-profile volume keys decrypted and resident in the crypto core (*After First Unlock*, the Cellebrite/GrayKey case), a case the powered-off evil-maid defense (measured boot + FDE) does not itself cover.
That distinction is **adopted**, importing the first and load-bearing GrapheneOS answer: **auto-reboot to the Before-First-Unlock state after an idle interval**: a scheduled RoT-attested transition (§9) that evicts the per-profile volume keys from the crypto core and re-seals the application islands, so a device seized after unlock returns to keys-not-resident at rest (§3, §10, §15) while the standby radio island stays page-reachable (§15).
Its credential/unlock path also gives **biometric matching** its §12 compartment, and unlock-attempt rate-limiting extends the RoT's existing boot-attempt counting (§9).
A second answer is imported alongside it: **USB data gated on the lock state**: a charging-only Before-First-Unlock device leaves its USB data lanes' capability-bounded DMA window (§15) unopened and defers new-peripheral authorization to post-unlock powerbox consent (§8), so juice-jacking and lock-screen wired extraction have no data path (§12); and because charging must outlive the lock, **USB-PD contract negotiation is specified as a fixed-function sequencer** (no firmware, the radio link-layer timing-block pattern, §12), which settles USB-PD in passing.
A third answer follows: a **duress credential that crypto-erases on entry**: presented instead of the ordinary one, it commands the RoT to destroy the sealing root so every user-data domain becomes unrecoverable in the time it takes to zeroize a key (*lose the key = erase memory*, §15), the coerced-unlock countermeasure booked as a defended case (§3, §9, §12).
The last operational-security answer is imported too, and as a **hardware invariant**: **per-connection MAC randomization** is tied to the platform's cryptographic RNG root: the die carries no persistent factory MAC and every link-layer address is a fresh draw from the RoT TRNG through the verified DRBG (§15, §16), so it is privacy by construction rather than a disable-able setting, GrapheneOS's per-connection randomization taken from a software default to a property of the entropy source.
The last GrapheneOS radio idea is **adopted and taken further**: where GrapheneOS disables 2G with a software toggle, here 2G, 3G, and 4G are **absent from the silicon**: the FEC units decode only the 5G/6G channel codes and the RF bank carries only 5G/6G bands (§15), so the target is **5G standalone and 6G** and downgrade to the broken-crypto legacy generations is physically impossible rather than merely refused (§3); atop that, the verified-from-scratch L2/L3 stack (§12) makes *no null cipher, mutual authentication required* a provable property rather than a setting; mitigation carried past theorem to matter, secureblue's move applied to the most-attacked surface.

GrapheneOS hardens the phone Android *is*; this design builds the phone that needs no hardening (a memory-safe, capability, verified substrate that refuses the AOSP/Linux base, the managed runtime, and the ambient-authority permissions GrapheneOS must retrofit) while **inheriting GrapheneOS's account of what an attacker holding the unlocked device can still do.**

---

## Qubes OS, Genode, and Xous: the compartmentalized-desktop family, the cost of its unit, and the sibling project that shares this one's premise

**Qubes OS** is the missing member of the product-pattern family above, and it is the one that argues hardest for the mechanism substitution.
Its principle is the same one §14 states, that a user's activities should be separated rather than merely permissioned, and its unit is a Xen virtual machine: dom0 holds no networking, the network and USB stacks are exiled into IOMMU-fenced driver VMs, a GUI daemon composites every window onto one desktop and paints each frame in its qube's **label colour**, and inter-qube calls run over `qrexec` against a policy naming *(source, target, service)* triples.
Two of those are worth taking.
The qrexec triple is the right shape for a static IPC authorization table, being exactly what a composition edge is; and the coloured frame is the cheapest known answer to "which compartment produced this pixel", which is an obligation §12's display path has whether or not there is a window manager.
The Admin API's lesson is the third: the management domain and the only trusted domain must be separable.

**What is declined is the unit, and the cost of the unit is now measured rather than argued.**
De Gregorio's 2026 longitudinal study of 109 Qubes Security Bulletins finds **87 of them, 79.8 percent, attributable to Xen, CPU microarchitecture, or upstream integration** rather than to Qubes' own logic, with transient execution alone accounting for 31.5 percent of post-2018 bulletins; the project's own FAQ puts its trusted base "on the order of hundreds of thousands of lines of C code", against seL4's roughly 8,700 lines of C.
So the composition of that base is worse than its size: most of the risk arrives from code the project does not write and cannot verify, and a third of the recent risk is a microarchitectural class §15 deletes by construction.
What Qubes buys with it is the thing this design categorically does not have, **unmodified legacy software**, which is the single reason it is usable as a daily desktop and the honest half of the comparison (§2, §14).
**Genode** is the same family's framework member and the closest existing relative of static composition: its recursive structure has every component created by a parent out of the parent's own quota, receiving only explicitly delegated capabilities, so a component's world is exactly the sessions routed to it.
The difference is when the rule is evaluated, at run time there and at build time here, and its vocabulary (sessions, routes, quota) is worth reading as a checklist against what the composition language must be able to say; its recursion is declined, since a cyclic executive over a fixed component set has nowhere to put a child that did not exist at composition time, and its licence is a fact to note early rather than late, AGPLv3 making any vendored component a commitment this repository would have to read at the milestone proposing it (see [THIRD-PARTY.md](../THIRD-PARTY.md)).
**Xous** is the nearest thing to a sibling project: a pure-Rust microkernel for an FPGA RISC-V SoC built on bunnie Huang's thesis that you can only trust hardware you can inspect, which is the same thesis §18 cites IRIS for, with a message discipline worth recording as precedent, since a Memory message carries Borrow, MutableBorrow or Move and thereby lifts Rust's ownership across a process boundary with the kernel as enforcer.
Its FPGA substrate is declined, inspectability there being bought with area, power and clock rate that IRIS obtains on hard silicon instead, and its assurance argument is declined on the ground §5 applies to every Rust system here: unsafe-free Rust is a memory-safety claim and not a machine-checked one, and Xous carries no proof to re-home.

---

## systemd: async init orchestration, minus the ambient authority

systemd contributed the *shape* of modern service management: **declarative units** with dependency-ordered, parallelized ("async") bring-up, and **supervision**: crash detection, restart policy, backoff.
§12's **service manager** keeps precisely this (a static supervision tree, declarative units, restarts with backoff) and §16 keeps the crash-only / health-gated posture.
But systemd's *mechanism* is the thing this platform is built to refuse: it runs with root **ambient authority**, parses text unit files at runtime, and accretes a large privileged surface (socket activation, D-Bus, cgroup control).
Here units are **compiled to typed, signed configuration objects per generation** (no trusted component parses text config at runtime, §10), admitted by proof (§13); the supervisor holds **no ambient authority** and re-grants capabilities on restart (§8, §12); and socket-activation's "hand the service its connection" idea is subsumed by the **capability ring data plane** (§12), where authority arrives only over the control plane and *physically cannot cross* the data plane. systemd is thus the orchestration *pattern* ancestor, with its ambient-authority substrate swapped out for capabilities.

---

## greetd: the privilege-separated login surface, and the greeter nobody here may replace

greetd contributed the *shape* of a minimal login manager: a privileged daemon owning authentication and session start, an **unprivileged greeter** owning nothing but the conversation surface, and a small IPC protocol between them; it enters this design's orbit as a member of the COSMIC closure (`cosmic-greeter` is a libcosmic greetd greeter, its companion daemon driving PAM), where [userspace-porting.md](userspace-porting.md) gives it its disposition.
The *split* is kept and sharpened: the credential authority is the credential & unlock service (§9, §12), matching against the crypto core and RoT with no PAM conversation in between, and the surface that collects the credential holds no credential logic, exactly greetd's division of labor with a typed IDL ring in place of the socket.
The *mechanism* is refused at every layer: PAM deletes with the ambient user database beneath it (§2, §8), session start becomes the service manager's static supervision tree behind the measured Before-First-Unlock → After-First-Unlock transition (§9, §12), and locking stops being a session state at all, becoming key eviction back to Before First Unlock (§9).
The defining feature is *inverted* rather than ported: greeter-agnosticism, any unprivileged program may be the greeter, is a spoofing surface by construction, and the trusted-path agent under the RoT secure-attention indicator (§6, §9, §12) exists precisely so that nothing can imitate or substitute for the surface that takes the credential.
greetd is thus the login pattern's nearest ancestor and its cleanest foil: the same three-piece decomposition, with the piece greetd lets anyone supply made the one piece nobody may.

---

## NixOS: the purely functional build: reproducible from source, config as a derivation

NixOS (with **Guix** its Guile-Scheme sibling on the same store model) is the demonstration of **purely functional software deployment** (Dolstra's model): every package is built by a hermetic function of its *complete declared input closure* (source, compiler, flags, patches, dependencies), with undeclared inputs structurally unavailable at build time, so the build is reproducible *from source* and a package's identity hashes its **recipe**, not merely its bytes.
Two properties land directly in the spec.
**(1) Reproducibility-from-source** is §10's "bit-for-bit reproducible from source" and the ground under §13's DDC / trusting-trust bound: Nix contributes the *functional build* that lets independent rebuilders confirm an artifact was honestly produced from given sources.
**(2) Declarative-config-as-derivation** is §10's "compiled declarative config generation": NixOS evaluates one declarative expression into the whole system (package set, service units, `/etc`, activation) as a single versioned artifact, exactly the spec's "config compiles to typed, signed objects per generation; no trusted component parses text config at runtime" (§10).
The Nix purity discipline (**no maintainer scripts, no post-install execution, installation = store insertion**) is likewise §13's packaging model (always more Nix than bootc).
Where the design parts company is *addressing and trust*: classic Nix is **input-addressed** (the store path hashes the recipe, not the output), while the device here only ever sees **content-addressed** artifacts verified against a signed Merkle root (§10; the OSTree entry below), so the functional/input side stays entirely **off-device** as a build-and-audit property (§13, "proving stays off-device") and runtime integrity comes from the content-addressed store: the fusion the spec wants, *a functional build with content-addressed outputs*, is Nix's own experimental content-addressed-derivations direction, here made mandatory and joined to a **machine-checked proof object and least-authority capability manifest** per package (§8, §13) that no functional package manager carries.
NixOS also contributes the **generation** (a versioned, atomically-switched, rollback-capable whole system), but the spec's **statelessness** (§10) deletes Nix's mutable profiles, symlink farms, and imperative activation: there is no live system to reconcile, only an immutable signed image re-derived each boot.
Guix's distinctive sharpening (a **full-source bootstrap** shrinking the trusted binary seed toward a tiny stage0) is the *reduce-the-seed* complement to §13's *detect-by-DDC* answer to trusting-trust, the one Guix-specific idea worth carrying even though the imported model is Nix's.

---

## OSTree: the content-addressed Merkle object store

libostree (*"git-for-binaries"*) is the **content-addressed Merkle object store** beneath Fedora Atomic (above), rpm-ostree, and bootc: a Merkle-DAG file store keyed by content hash, with deduplicated deltas, atomic A/B deployments, and rollback as first-class operations.
This is the one mechanism the spec takes from that lineage, and it is the *output-side* complement to NixOS's *input-side* functional build (above): where Nix gives a verifiable path *from source to artifact*, OSTree gives a verifiable *artifact*: an identifier that hashes the bytes, so **every read is runtime-verified against the boot-attested signed root** (§9, §10), which classic input-addressed Nix does not provide.
It underwrites two sections: the **content-addressed Merkle image** (§10), and **image-based atomic A/B updates whose deltas fall out of content addressing**, with rollback = pin a prior signed root (§11).
What the spec **does not** take is the *product layer* over the store: neither bootc's **OCI-container packaging of the OS** nor rpm-ostree's RPM composition: packaging here is the functional, proof-carrying model of NixOS + §13, not an image or a package format.
The spec's addition over the bare store is the *proof* and the *authority*: admission is gated by the on-device checker validating each binary's proof against the current spec/Sail-model versions (§11), and every object carries a **least-authority capability manifest** wired at compose time (§8, §13).
Content-addressed transactional storage: proof-checked and capability-scoped.

---

## Unison: identity as the hash of the normalized definition, and acceleration that preserves it by construction

**Unison** (Chiusano and Bjarnason; 1.0 shipped November 2025, MIT) takes content addressing one level below where OSTree and Nix stop.
A definition's identity is the hash of its **normalized syntax tree**, with names stripped to metadata, so a rename is a metadata edit that recompiles nothing, two definitions that differ only in variable spelling are the same definition, and the dependency diamond dissolves because there is no version to disagree about, only a hash.
There is no build step, since a definition is either already in the store under its hash or is not.
The import is not the runtime and not the language: it is the **normalization pass before the hash**, which is what makes hash-identity a statement about meaning rather than about bytes, and it is the discipline §13's import tables and §10's content-addressed image want stated explicitly, since a whitespace-sensitive digest names a text where a normalized digest names a program.

The deeper point is one the ocap survey turns up as a rule and Unison is the only member to satisfy: **everyone who froze a substrate had to unfreeze it for performance.**
Urbit froze Nock and recovered its speed with jets; Dis froze a portable VM and recovered its speed with a JIT; Unison froze definitions by hash and recovered its speed with a compilation cache that is sound *because* the cache key is derived from the identity rather than asserted alongside it.
Only the last keeps its correctness story intact under the optimization, and the reason is that its acceleration is identity-preserving by construction.
That is the standard §5's curated interpreter is held to: any acceleration lives inside the verified artifact, or carries a machine-checked equivalence, or is absent.

---

## Transparency logs: Certificate Transparency, the Go checksum database, and Pixel binary transparency; the one property a proof cannot have

A proof and a log answer different questions, and the design has only ever answered the first.
A proof establishes a property of **the artifact in front of you**, quantified over all its executions: it satisfies its specification.
A transparency log establishes a property of **the population**: this artifact was committed to publicly, so if it is special it is publicly special.
The sharpest published statement of the second is the Go checksum database's, which does not merely use the word correctness but *defines* it, guaranteeing that a particular download is correct where correctness means **"the same code everyone else downloads"**; the most quotable is Mozilla's binary-transparency page, whose whole purpose is that a user's copy of the browser "is the same one that we gave to everyone else, and not a special copy just for them".
Neither property implies the other, and the direction that matters here is the one the design is exposed on.

**Why proof-carrying admission does not subsume the log, stated as an attack.**
The specification an image is proved against is itself an artifact.
An adversary with build-path access who cannot forge a proof can still build *this device* a distinct image satisfying a weaker but still admissible specification, or select per device among several genuinely admissible images with different behaviour, or work in whatever gap stands between what the specification constrains and what the code does outside that scope.
Each of those produces an image whose proof checks on arrival, so §11's admission gate passes and §9's measured root attests exactly what was installed, which is the point: attestation binds the machine to the image it runs, and says nothing about whether that image is the one anybody else got.
None of them survives a requirement that the image root appear in a public append-only log with an inclusion proof, because the adversary must then publish the targeted image, and publication is the one cost a targeting attack cannot pay.
Conversely a log subsumes no proof at all: Rekor, `sum.golang.org` and Pixel binary transparency each log malicious artifacts faithfully, and each says so in its own documentation.

**The mechanism is small, self-contained, and exactly the kind of thing this project should own outright.**
Certificate Transparency (RFC 6962, RFC 9162) is a Merkle tree over an append-only entry list whose state is published as a signed tree head, with three checkable objects over it: an **inclusion proof** that a leaf is in the tree, a **consistency proof** that an older head's tree is a prefix of a newer one, and a **checkpoint** a client can pin.
Two deployment lessons come with it.
First, the split-view problem, a log serving two histories to two populations, was to be solved by client gossip and in practice never was; the modern answer is a **witness network** (the C2SP `tlog-witness` shape), where independent parties co-sign a checkpoint only after checking it against every checkpoint they have signed before, so a client demanding K-of-N witness signatures gets split-view resistance without talking to any peer.
Second, the **tile** format (C2SP `tlog-tiles`, as used by Trillian Tessera, Rekor v2 and Pixel) serves the tree as fixed-size chunks over plain static storage, so there is no live log server in the trust path and a device can be served proofs by a mirror it does not trust.
That is what makes the property reachable offline: the inclusion proof and the witnessed checkpoint travel *inside* the image manifest and are checked at admission, and a verified Merkle-inclusion checker is a few hundred lines of the sort §5's vehicle handles comfortably.

**The two deployed systems closest to this design each hold one half of it.**
**Pixel binary transparency** logs the device's own VBMeta digest, which is the root of the hash tree over the images, so the object in the log is the same object the device can measure and read out, which is precisely the relation §9's measured root has to §10's image; what it proves underneath is verified boot against a vendor key rather than a property of the code, and Google extended the same machinery to the Android application layer in May 2026.
**Apple's Private Cloud Compute** holds the other half, and holds it in the posture worth copying: every node presents a signed measurement of the image it is running, the images are published for inspection within a bounded window, and the client **refuses to proceed** unless the measurement appears in the log, which is enforcement before the fact where almost every other transparency deployment is detection after it.
What PCC puts underneath the log is human review of published binaries, which is exactly the labour proof-carrying admission replaces.
So the combination this design is one publish step away from, proof-carrying admission checked on the device over a content-addressed image whose root sits in a witnessed log, appears to be unoccupied: PCC has the posture without the proof, Pixel has the object without the proof, BT2X (Fraunhofer, 2024) has the constrained-device plumbing and tiered audit levels without either, and proof-carrying code has never been deployed with a log at all.

**Honest residual.** Non-targeting is not a property any requirement in the register currently holds, and no amount of proof will produce it, so the entry records a gap rather than a lineage: the mechanism is mature, the citations exist, and the obligation is unwritten.
What is declined is narrower: the signed-certificate-timestamp *promise* of future inclusion, since a device that verifies offline should demand a real inclusion proof against a witnessed checkpoint rather than a merge-delay promise, and the blockchain substrate (Contour, 2018) that buys split-view resistance at the price of a consensus protocol and a liveness dependency at install time, where a witness quorum buys it with neither.

---

## TUF and Uptane: the staleness a proof cannot detect, and the two-repository intersection

**The Update Framework** (NYU; Samuel, Mathewson, Cappos and Cappos, CCS 2010) is the best key-management design in the field, and it is here for one primitive rather than for its role model.
TUF separates four roles with their own keys and thresholds: root (offline trust anchor), targets (what the files are), snapshot (one consistent repository state), and a short-lived timestamp; against that structure it names and defeats rollback, mix-and-match, fast-forward, and, the one that matters here, **freeze**.
A freeze attack serves a stale but perfectly valid view indefinitely, and it is defeated by **metadata expiry** rather than by any signature check, which is why timestamp metadata is re-signed constantly.
**This is the supply-chain attack a proof-carrying image is completely blind to**: an old image whose proof checks against a specification since strengthened is a valid image, an admissible image, and a live vulnerability, and neither §11's checker nor §9's measured root has any way to notice, because nothing about it is wrong except its age.
Uptane adds the second half a shipped device needs: **secure time**, since expiry is the primitive and a device that has been offline for a year is the freeze attacker's ideal victim.
TUF's snapshot role, by contrast, this design already has for free and should say so: one Merkle root pins the whole image, so mix-and-match is structurally impossible rather than defended.

**Uptane** (IEEE-ISTO 6100, standard 2.1.0 of June 2023) is TUF specialized for vehicles, and it is the only widely standardized answer to attested updates on a shipped device with heterogeneous constrained processors, which makes it the closest existing relative of §11's problem.
Its structural idea is the **two-repository intersection**: an *image* repository, offline-keyed, vendor-curated, slow, holding every image the fleet may ever run, and a *director* repository, online and per-device, instructing this device which of the catalogued images to install; a fully verifying unit installs only what **both** attest.
Compromise the online director alone and an attacker can deny service or steer a device to an older catalogued image, but cannot mint a new one.
Read against this design the mapping is exact and the conclusion is that the gates are three rather than one: an image is admissible because **its proof checks** (the catalogue side, where a theorem replaces the vendor's curation and is strictly stronger), it is not targeted because **its root is in the witnessed log** (the entry above), and the directive naming it is **fresh** (this entry).
Those are three independent properties and no one of them implies another, which is what Uptane's two repositories and the reproducible-builds `reproduced+https://` transport both demonstrate in deployed code: an install path that refuses what it cannot corroborate is ordinary engineering, and the corroborations must be conjunctive.

What is declined is the trust-in-keys-about-semantics that the rest of TUF's model rests on.
Targets metadata is a claim about *which* file, never about whether it is admissible, so it demotes here to naming and freshness; delegation trees solve a multi-namespace problem a single-vendor image does not have; and Uptane's **partial verification** tier, where a constrained secondary checks only a signature and the current time, is exactly the posture §5 refuses.
The tiering *question* it answers is real, since an on-die root of trust and a peripheral core cannot run the same checker, but the answer here is that a core which cannot run the checker receives its image through one that can, rather than verifying less.

---

## Bootstrappable builds and Diverse Double-Compiling: shrinking the unproven root until a theorem about it is feasible

The trusting-trust attack is the De Bruijn root seen from the compiler, and it stopped being a thought experiment in 2025: Russ Cox recovered Thompson's original backdoor, ran it under a V6 Unix simulator, and reproduced the same attack shape against a modern Go compiler, reporting the whole of it at **99 lines of code plus a 20-line shell script**.
Two lines of countermeasure exist and they leave different residuals, which is what makes them worth recording together.

**Diverse Double-Compiling** (Wheeler's 2009 dissertation) is the one with a proof.
Compile the compiler's putative source with a second, independently produced compiler, compile the source *again* with the result, and compare that second-stage output bit-for-bit with the binary under test; the second compilation is the load-bearing one, since it cancels the trusted compiler's own code-generation idiosyncrasies and leaves both artifacts as outputs of the same semantics.
What it concludes is exactly one theorem, `source_corresponds_to_executable`, and Wheeler is explicit about the rest: a trusted diverse compiler binary must exist, along with trusted environments, a trusted comparer, trusted acquisition of the inputs, and determinism of the compiler the source defines, and DDC says nothing about whether the source itself is malicious.
So its residual is *another unverified binary plus a human reading source*, and its argument is diversity, a wager that two independently produced compilers do not carry the same backdoor.
The binary-level proof of the admission checkers over Sail that [architectural-alternatives.md](architectural-alternatives.md) defers concludes something different in kind, that *this machine code on this modelled machine has this behaviour*, and its residual is a **checkable computation**: a proof checker whose failure mode is refusal rather than silent compromise, and which a second independently written checker can replay.
Neither eliminates a bottom binary; the difference is what the bottom binary must be trusted to do, and non-malice is unfalsifiable where proof-checking is not.
DDC is therefore recorded as complementary rather than superseded: it is the countermeasure available to everyone who cannot write the theorem, and a cheap independent cross-check for anyone who can.

**The bootstrappable-builds line** attacks the same root from the other end, by shrinking the unauditable seed rather than diversifying it.
`stage0-posix` roots a chain in **hex0**, a hex-to-binary translator of a few hundred bytes (256 or 357 depending on architecture and revision, so the number is never quoted without the qualifier), and climbs through hex1, hex2, the M0 macro assembler, a minimal C compiler, M1, M2-Planet, GNU Mes, TinyCC and musl into modern GCC; `live-bootstrap` documents that climb in 182 stages and trusts exactly two binaries, `hex0-seed` and `kaem-optional-seed`.
Two facts land directly on this project.
The seed set already covers **RISC-V 32 and 64**, so a hand-auditable root exists for the exact ISA this design builds on.
And the NixOS entry above needs reading with a date attached: `minimal-bootstrap` merged to nixpkgs staging on 28 January 2026, replacing the 130 MB prebuilt `bootstrap-tools` bundle with a hex0 chain for x86-64 and i686, which moves NixOS onto the trajectory Guix reached in April 2023.
Guix's own residual is the instructive one and it generalizes past Guix: the *package graph* is rooted in 357 bytes while the shipped bootstrap binaries still include a 25 MiB static Guile driver, which is the seed you advertise differing from the seed you depend on, and the discipline it demands here is to state per artifact what is actually in the trusted set (§6) rather than any figure that is true of the graph and false of the set.

What is declined is the line's terminal argument rather than any of its machinery.
"Small enough to read" is a human-review claim, and human review of binaries is precisely what this design exists to replace; the right posture, and the contribution this project can make back to that line, is that bootstrappable builds shrink the unproven root to a size at which **a theorem about it becomes feasible**, and then the theorem is written.
The chain's endpoint is declined for the same reason: it climbs toward a modern C compiler, where the endpoint wanted here is a verified checker, and every C compiler on the way is scaffolding rather than a destination.

---

## bcachefs: the CoW filesystem featureset, made verifiable

bcachefs is the direct model for the mutable filesystem: an *elegant* copy-on-write filesystem whose whole architecture is **"everything is a b-tree,"** with per-extent checksumming, encryption, replication (RAID), erasure coding, tiering/caching, O(1) snapshots and reflinks, and a write-ahead journal. §10 adopts the featureset almost entire and makes it **verifiable**: the **L1 unified CoW B-tree with buffered updates** (bcachefs's log-structured nodes *are* a B^ε-tree), **snapshots as a version field in the key** (bcachefs-subvolume style), reflink/dedup as refcounted CoW extent sharing, replication/EC/tiering/copygc pushed **below the integrity line** as availability-only block services (§10, §12), and the journal as the **L0** crash-safety trunk. bcachefs's sharpest idea, **the checksum *is* the MAC**, becomes §10's **per-extent AEAD** (the Poly1305/GHASH tag serving as the stored checksum), joined to a machine-checked proof: *bcachefs has the mechanism; this has the mechanism **and** the theorem*: the crypto reduction (scheme is IND-CCA/INT-CTXT) ⋈ the storage data-noninterference, at the extent's functional spec (§5, §10).
The one deliberate subtraction is **compression**, dropped as a *security gain*: it deletes the compress-then-encrypt ratio oracle (CRIME/BREACH class) and removes a decompressor from the read path (§10).

---

## FSCQ and its descendants: the verified-filesystem method

FSCQ (MIT) was the first filesystem with a machine-checked proof that its implementation meets its specification *including across crashes* (the **Crash Hoare Logic** method), extracted to Haskell and run sequentially.
Its family is the entire L0–L3 methodology of §10: **SFSCQ / DiskSec** contribute machine-checked **data non-interference** (one domain's data provably cannot influence another's: the L3 confidentiality layer); **RefFS** contributes concurrent **linearizability + crash safety *and* liveness**: machine-checked deadlock- and livelock-freedom (Coq) via its **MoLi** *dynamically layered definite releases* framework, the safety-**plus-progress** successor to the same group's safety-only **AtomFS** (MoLi also caught a real deadlock in the Linux VFS locking scheme with no code proof); **VeriBetrFS** contributes the write-optimized **B^ε-tree** index design (L1); and **Perennial / GoJournal** contribute the concurrent crash-safe write-ahead **journal** (Iris/Coq: the L0 trunk), with **DaisyNFS** the top-half-transaction-over-journal *layering template*.
The spec's move on this lineage is **trust-base uniformity and no managed runtime**: designs that ship on Dafny/Z3 or a Go runtime (VeriBetrFS, Perennial) are **re-proved in Coq/Iris and re-homed onto CompCert-C** (§5, §10, §18), keeping FSCQ itself and Yggdrasil as lineage and cross-check rather than bases.
FSCQ is the existence proof *that a filesystem can be verified at all*: the ground the four-layer stack is built on.

---

## TigerBeetle: static allocation and paced background work at the throughput pole, and the rule about where a checksum lives

**TigerBeetle** is a production single-writer OLTP database whose engineering doctrine, **TigerStyle**, is NASA's Power of Ten carried into a commercial system: *"All memory must be statically allocated at startup. No memory may be dynamically allocated (or freed and reallocated) after initialization"*, no recursion, a fixed upper bound on every loop, hard limits on every queue, explicitly-sized integer types, and zeroed padding *"to prevent buffer bleeds"*.
It enters for two distinct reasons that should not be run together: one **mechanism** §10 takes, and a body of **convergent evidence** for disciplines this design reaches from a proof budget rather than from a latency target.
Its own trust argument is assertion density and deterministic simulation rather than proof, and none of its code is imported (Apache-2.0 Zig, a language with neither a verified compiler nor a mechanized semantics, so it is outside §5's single-prover, CompCert-C vehicle by construction).

**The mechanism is where a checksum lives, and it is the one thing an internal checksum cannot do.**
A TigerBeetle grid block is addressed by a pair of block index and `u128` checksum, and a reader always knows the checksum *before* the read, from the parent block or from the superblock, because *"one failure mode for disks is to store correct data at a wrong offset, a failure which cannot be detected using only internal checksums"*.
The Merkle DAG of the immutable base already has this property by construction (a parent holds its child's hash), but the mutable side did not state it, and the per-extent AEAD makes the omission consequential rather than cosmetic: an extent sealed and stored with its own tag verifies perfectly when a device returns it from the wrong place, because it is internally consistent and merely wrong.
So R-10-022a states the placement: the nonce and tag live in the index node that references the extent, never beside the ciphertext, which is what holds the below-the-line block services (replication, tiering, copygc, the FTL) to their availability-only role by a check the *reader* performs rather than by their own bookkeeping (R-10-021).
The root gets the same treatment for the opposite reason.
TigerBeetle writes **four copies of the superblock and starts from the newest present in at least two**, and it is the one structure storing its own checksum internally *because nothing references it*; R-10-001a is that argument re-grounded, and the re-grounding is real rather than cosmetic, since every root here is ML-DSA-signed and security-versioned, so authenticity is decided by the signature and never by a vote among copies: redundancy buys only that a torn or misdirected write of one copy costs a copy instead of the generation, and the selection rule (verify every candidate, take the highest version that verifies) replaces a stored pointer naming the current slot with a decision derived from the candidates themselves.

**The pacing is convergent, and it is the answer to the question an LSM or a CoW tree would otherwise ask of a cyclic executive.**
Compaction runs one tick immediately after each commit at `beat = op % lsm_compaction_ops`, split into half-bars by level parity, with at most ⌈levels/2⌉ compactions live, free-set reservations taken only at half-bar boundaries, and the invariant that *"at the end of every beat, there is space in mutable table for the next beat"*: background maintenance amortized into a fixed per-operation quantum instead of a thread that runs when it likes.
That is structurally the discipline §8 already imposes on the revocation sweep (an incremental pass in its own composition-sized background slot class, R-08-007) and §15 on the scrubber (*a scheduled task issuing one instruction, never an engine walking on its own*, R-15-177a), reached independently by a system with no WCET obligation at all.
What transfers is only the pacing: the **index** stays the B^ε / CoW B-tree of §10, so the forest, the level geometry, the manifest log, and the move-table optimization stay behind with the LSM they belong to.

**The static-allocation evidence is the entry's other half, and it lands where the design is usually conceded a niche.**
The heap deletion (§8) is argued here from proof budget and from Robson's bound (above), which is a safety-critical argument, and the standing objection is that it belongs to safety-critical systems and does not survive contact with general throughput work.
TigerBeetle is the counterexample: the same rule, adopted for tail latency and for deleting use-after-free, in a database whose whole product claim is throughput, which is the datapoint [architectural-alternatives.md](architectural-alternatives.md) and [critique.md](critique.md) want at that objection, in the shape the Akaros and Cerebras entries already use.
Two smaller doctrinal echoes come with it: the zeroed-padding rule is §10's representation-padding obligation and §5's definite initialization seen from a systems-hygiene angle, and *"assertions downgrade catastrophic correctness bugs into liveness bugs"* is §16's *detect, correct, or contain, never shield* stated by a database.
The assertion discipline itself does **not** transfer wholesale, because proofs discharge what assertions sample; what it reaches here is the axiom boundary, where there is no theorem to have (the probing model, the single-fault model, the fabricated-silicon residual, §17).

**Determinism is the last import, and it is method rather than mechanism.**
Because replaying operations reproduces bit-identical in-memory and on-disk state, recovery is a restart from the last superblock and a re-derivation rather than a resume, which is R-10-036's *restore is never a resume* arrived at from durability instead of from authority.
The **VOPR** simulator then spends that determinism: real cluster code under injected network, storage, and process faults at accelerated time.
The method is not TigerBeetle's own and the inventor should be named where it is used: **FoundationDB** originated it, writing the database in **Flow**, a C++ dialect whose same source produces both the production binary and a build running the entire cluster as a deterministic single-threaded simulation, injecting connection failures, machine degradation, shutdowns and reboots at deliberately brutal rates, at a reported cumulative scale near a trillion CPU-hours, with Apple's own documentation saying it seems unlikely the system could have been built without it.
**Antithesis** generalizes it below the guest, its Determinator being a bhyve fork that virtualizes every time source against instruction counts read from performance counters, pins each instance to one core, and channels all input and output through a single instruction, so that execution can be snapshotted, branched, and any violating path replayed exactly.
The structural rule under both is the transferable part and this platform gets it for free: simulation is possible exactly when **all** nondeterminism enters through one interface the harness owns, which FoundationDB had to invent a language to obtain and an in-order, non-speculative, cacheless, share-nothing machine under a static schedule has by construction (§15).
The hypervisor is declined for the same reason: manufacturing determinism for a nondeterministic x86 guest is an achievement this machine does not need, whose ISA-level semantics are already mechanized in Sail and executable (§18), and a closed commercial platform whose failure to find a bug is not a proof is not a trust-base member in any case.
This platform makes the whole *machine* deterministic (no speculation, flat memory latency, a static schedule, no runtime allocation), so a simulator of that kind is unusually faithful here and is the natural validation lane for the layers that will not carry a theorem soon: the unauthored NoC model, the drivers, the radio control planes (§12, §17).
It enters at the tier aiT, Binsec/Rel, and the bounded-property tools enter at, **complementary evidence and never a closing axiom** (§5, §17).

What stays behind is everything that follows from having peers: Viewstamped Replication, view changes, quorum durability, protocol-aware recovery, and gray-failure detection answer a fault model a single device does not have.
So do `io_uring` and `O_DIRECT`, which presuppose a host kernel to bypass, where here there is nothing beneath the verified stack to be bypassed.
The **multiversion binary** is declined outright rather than merely unused: bundling past releases in `.tb_mvh` / `.tb_mvb` sections and `exec`ing into one is exactly the on-device executable-format parser and loader §10 deletes, and A/B signed roots with health-gated revert (§11) already own the job it does.
One sharpening is admired and not adopted: fixed-width 128-byte records with reserved fields that must be zero make the internal formats canonical by construction and delete the parser rather than verifying it, which is the trivial case of the canonicity theorem R-05-051a demands; the platform's descriptors are IDL- and Narcissus-generated and carry that theorem the harder way, so the observation is recorded as a design pressure on new internal formats rather than as an obligation on the existing ones.

---

## Hubris and Humility: the static task set shipped in a product, the lease as a revocable loan, and the generation number that makes restart safe

**Hubris** (Oxide Computer Company, MPL-2.0, Cliff Biffle principal) is this architecture running in a commercial product rather than in a paper: it is the operating system of the service processor and of the separate root-of-trust microcontroller in Oxide's rack.
An `app.toml` names every task that may ever run, its priority, its memory sizes, the peripherals it owns, and its interrupt-to-notification mapping; kernel and tasks link into a single image and no task is ever updated piecewise, so only tested combinations ship; the address space is physical and single, the kernel's task and region tables are static arrays sized from the manifest, and peak memory is therefore a compile-time quantity rather than a load-dependent one.
It enters at the tier TigerBeetle enters at (above) and for the same reason: convergent evidence that the discipline ships, with none of its code imported and none of its assurance argument accepted.

**Three mechanisms transfer, and the first answers a question the heap deletion leaves open.**
The IPC is synchronous `send`/`recv`/`reply` with inline messages capped at 256 bytes, and everything larger moves as a **lease**: a bounded read, write, or read-write loan of the sender's own memory, reached by the recipient through borrow syscalls rather than through a mapping, capped at 255 per send, and revoked atomically at reply.
That is Rust's borrow discipline carried across a protection boundary with no allocation on either side, which is what a static memory plan (§8) needs where a conventional system reaches for a shared buffer pool; here the loan is a CHERI capability whose bounds and permissions *are* the loan, so revocation-at-reply is a property of the ring rather than a kernel bookkeeping step, and the lease ceiling is a composition-time constant rather than a runtime limit.
Second, **no interrupt handler code exists anywhere in the system**: one generic kernel ISR posts a notification bit and masks the source, and the owning task collects it at its next receive, so an interrupt is an event pulled at a known instruction and never an asynchronous entry into task code.
§7 reaches the same shape from the WCET side, where an ISR at an arbitrary instant is the preemption term a derivation loses rather than bounds; Hubris reaches it from robustness, and the convergence is the point.
Third, the **generation number**: a fault does not reach kernel policy, the kernel records it, bumps the dead task's generation, and notifies an unprivileged supervisor task that calls `reinit_task`, while peers blocked on the dead task receive a dead code carrying the new generation, so a protocol resynchronizes rather than wedges.
That is crash-only restart (§16) with no allocation and no stale identifier surviving it, which is the part an ordinary supervision story leaves to convention.
**Humility**, the out-of-band SWD debugger that reads DWARF and takes ELF core dumps, is §16's posture in a tool: a shipped device has no console and cannot be assumed able to phone home, so postmortem analysis happens off the machine and the shipped image carries no debug service.

**What is declined is the whole assurance argument, and Oxide claims none.**
Hubris carries no formal verification of any kind: the manifest compiler is unverified, the MPU region tables it emits are not proved to realize the isolation the manifest declares, and the kernel is not proved to respect them.
The guarantee is Rust plus MPU plus review, which stops at every `unsafe` block, at the linker script, and at the build system, and it is the "app safety leans on the toolchain" posture §5 and §13 supersede.
Its scheduler is fixed-priority preemptive with no schedulability and no timing-channel claim, which is the family [architectural-alternatives.md](architectural-alternatives.md) declines.
And an MPU region bounds a *task* where a capability bounds a *pointer*, which is what lets this platform's composition edges be capabilities a component actually holds, so the graph's realization is checked by reachability instead of trusted from a table.
One datapoint travels with it and lands in §9 rather than §7: Oxide has published several silicon and ROM vulnerabilities in the LPC55S69 its own root of trust runs on, which is the vendor-ROM-is-in-your-trusted-base argument (§6) made by the people who had to find them.

---

## ChromeOS: the verified-boot root of trust, realized as on-die OpenTitan

ChromeOS is the mass-deployment proof that a consumer OS can stand on a **hardware root of trust with verified boot, a read-only rootfs, and A/B updates with automatic rollback**: its trust anchored in a discrete security chip (the Google Titan / H1 lineage) whose open-silicon descendant is **OpenTitan**.
§9 is that chain, sharpened: an **OpenTitan-class RoT** provides measured boot, key storage, TRNG, monotonic counters, and boot-attempt counting, with the chain RoT → verified M-mode firmware → per-core kernels → static image, every stage measured and every signature post-quantum (ML-DSA), plus A/B images with RoT boot-counting auto-revert and a monotonic anti-rollback floor (§9, §11).
§15 then goes past ChromeOS by **integrating the OpenTitan block on-die** as the platform's *only* management processor (removing the discrete-RoT interposer/probing surface and making attestation coverage total), the "no foreign computers" mandate (§4) applied to the root of trust itself.
ChromeOS supplies the verified-boot product template; OpenTitan supplies the open, inspectable silicon that lets the template become a *TCB* rather than a vendor black box.
The same move **retires the discrete or firmware TPM and declines OpenTitan's own TPM-2.0 command mode**: the RoT provides the TPM's *operations* (measured boot, sealing, attestation quotes, monotonic counters), verified and on-die (§9), but not as an unverified black box on an external bus (§15) nor through the TCG command *protocol* (a grammar-heavy register-slave surface, §5, §12) with its non-PQ attestation; software reaches those operations through the §12 sealing & attestation service that secure-vault apps build on.
(Google's **Sparrow**, the KataOS reference platform (seL4 entry above), is a second datapoint for OpenTitan-as-integrated-RoT-on-RISC-V, corroborating the silicon bet even as it keeps a separate ML-accelerator core rather than making the die the platform's *only* computer, §4/§15.)

---

## coreboot, oreboot, LinuxBoot: the open-firmware line, and the trade oreboot made independently

The blob prohibition is usually read as this design's most aggressive choice, and the open-firmware line is the evidence that it is instead the only choice that has ever worked.
**coreboot** is the baseline and the cautionary half: its stage decomposition (bootblock, then a romstage running out of cache-as-RAM before DRAM is trained, then a ramstage once memory exists) is what a DRAM-bearing platform is *forced* into, and it is exactly the stage where the closed core lives.
On modern Intel parts the Firmware Support Package supplies FSP-T, FSP-M and FSP-S as binaries performing the silicon and memory initialization romstage cannot otherwise do; coreboot documents FSP bugs it works around **because it cannot patch them**, Intel does not publish the bug list, the proprietary components sit in separate repositories, and the June 2026 release records a part shipping with dummy FSP headers until real ones exist.
The management engine is not removable at all.
So coreboot is open firmware around a closed core, and the closed core is where memory training lives.
**oreboot** is the entry's point: coreboot with the C removed, and, far more importantly, a project rule that it will "only target truly open systems requiring no binary blobs, meaning no x86 for now".
That is the same trade §15 makes, reached independently and paid for at the same price, and it is the citation [absence-contract.md](absence-contract.md) wants beside its own refusals, because a firmware project that gave up an entire architecture rather than accept a blob is stronger evidence than any argument that the refusal is coherent.
The concrete reason this design can hold the line where coreboot cannot is worth stating in one clause: with on-die SRAM and no DRAM interface (§15) there is no memory training, therefore no cache-as-RAM romstage, therefore no place an FSP-M could live.
**LinuxBoot** and **u-root** are declined outright: replacing the UEFI driver phase with a Linux kernel and a Go userland shrinks the closed part of the firmware by moving millions of lines of unverified code and a garbage-collected runtime into the boot path, which is the opposite of a proof-carrying install path rooted in an on-die root of trust (§9, §11), and it leaves the vendor's own pre-DRAM phase underneath it untouched.

---

## COSMIC / CVA6-CHERI: the open application-class CHERI core, and its ISA-conformance proof

**CVA6-CHERI** (Capabilities Limited, on the OpenHW Foundation's CVA6) is the open, 64-bit, application-class CHERI core the design already builds on as its **C-class scalar front end** (§15): the compute-substrate complement to the ChromeOS/OpenTitan root of trust (above).
Its live realization is the **COSMIC** project (lowRISC + Capabilities Limited; DSIT/InnovateUK, 2025–28), which delivers the two things the design most needs from that substrate: it **hardens the core to commercial quality** on OpenTitan IP (so the on-die RoT-integration template of §9/§15 arrives with it) and, the load-bearing part, it **formally verifies that the core's instruction execution conforms to its ISA specification**, the application-class successor to the Oxford/Melham proof that established the same for **CHERIoT-Ibex**.
That conformance result is the existence proof for the design's hardest, *least-built* arrow (**RTL ⊑ Sail**, §15, §18), where the spec itself records that no full application-class core had yet been proven to refine its ISA model.
The design **re-grounds** the import on its own axioms, three ways.
*Trust-base uniformity*: COSMIC's verification is OpenTitan-style staged design-and-verification sign-off, namely UVM simulation plus **bounded formal-property (FPV)** assertions, three-reviewer per-block checklists, and first sign-offs targeted at RC-1 (Dec 2026). That is *why* it enters here as **riscv-formal / Isla-class bounded bring-up evidence** rather than a rival to the single-Coq mandate (§5, §6): the mature complement, never the closing axiom, with the unbounded **Kami/Kôika** Coq refinement still the vehicle that discharges G3, exactly as aiT, EasyCrypt, and Binsec/Rel are complements, not axioms, elsewhere (§17).
*Profile freeze*: the stock front end is **modified to static-only prediction and a TSO store buffer** and stripped to the §15 profile (no C extension, `Zaamo`/`Zabha` for atomics, no CAS, no LR/SC), re-homing the core onto the no-hidden-state, deterministic-timing axioms.
*Purecap-only*: no capability-degraded interim (§15).
What the design pointedly does **not** import is COSMIC's *product framing*: COSMIC is a **secure enclave beside a rich OS**, exercised with **Linux**, whereas §4's "no foreign computers" makes the **whole die** the trusted computer and §2/§14 reject a Linux personality outright; so the core RTL, the OpenTitan integration, and the conformance-proof *method* transfer, while the enclave pattern and the software stack do not.
The transfer boundary is sharper still on virtual memory: **Mocha** (COSMIC's MVP-2 bring-up platform on CVA6-CHERI) fields an application-class core **precisely to give enclave OSes an MMU** (its rationale for CVA6 over a real-time core), yet this profile **deletes the MMU** (single-address-space, `satp` Bare, §15), so the CVA6-CHERI datapath is imported while the MMU that motivates Mocha's core choice is curated away, its conformance evidence thereby covering a virtual-memory path the platform never runs.
Two live-design notes mirror seL4's "a live design, not a frozen one" (above): CHERI is being standardized as the **RISC-V 'Y' extension** the frozen §15 profile tracks, and COSMIC's **dual-core lockstep** is a hardware fault-*detection* complement to §7's per-core kernel duplication for bit-flip blast-radius: fault detection beside fault containment, **imported for one core and logged for G5 everywhere else**: the S-class sentinel is realized as a detection-only lockstepped pair (§16) because a detector cannot report its own corruption and a software redundancy pass would run on the core being doubted, which spends the doubling on the smallest core on the die, while the general case stays deferred at the cost the design weighs (it doubles core area).

---

## Codasip X730: the first commercial CHERI-RISC-V application core, shipping evidence and a silicon path, not the base

The **X730** (Codasip) is the first commercially licensable CHERI-RISC-V processor: a 64-bit, in-order, nine-stage, dual-issue application core whose register file and selected CSRs widen to 129 bits to hold a 128-bit capability and its tag, with a capability-checking unit that every instruction issues to alongside another execution unit, their outputs combined at commit.
It is the CHERI variant of the **A730** the drop-PMP argument already cites (§15), on a shared codebase that reports the CHERI version at a **sub-5% area delta** and the same maximum frequency: shipping commercial evidence for the design's own thesis that application-class purecap CHERI is real and cheap, at the scale where CheriOS and CHERIoT are only microcontroller-class existence proofs (§17).
What it offers beyond the open designs sits on the *engineering-is-free* axis, never the scarce trust axis: it is the most direct answer to §18's binding constraint (application-class CHERI exists only as licensable IP and FPGA soft cores), and its CodAL / Codasip Studio single-source flow regenerates RTL, an LLVM toolchain, and a verification environment from one description, an accelerator for curating the frozen, MMU-less, static-prediction profile (§15).
What the design does **not** take is the X730 as its trusted base: the RTL is proprietary and authored in CodAL, and Codasip's UVM-plus-formal sign-off is riscv-formal / Isla-class bring-up evidence, a complement and never the closing axiom (§6), so it cannot carry the load-bearing **RTL ⊑ Sail** refinement (§15, §18) that an open core re-expressible into a formal-semantics HDL can; and as shipped it is the general-purpose MMU-on, S/U-mode, Linux-booting configuration the profile curates away.
So the X730 is a licensed **reference, bring-up, and possible silicon vehicle**: the commercial complement to the open **CVA6-CHERI / COSMIC** track (above), which stays the C-class front end precisely because it is open, re-expressible, and on a conformance-proof path.

---

## openwifi, mac80211, and Nordic's nRF: the firmware-free low-MAC, and the partition that keeps the radio out of the foreign-computer category

The dissolved-modem thesis (§4, §12) puts the whole radio stack in contained software on the pinned V-cores, and runs into one deadline software cannot hold: the sub-slot **turnaround**, where the radio must flip the RX/TX path and be transmitting within a fixed inter-frame gap (BLE `T_IFS` at 150 µs ± 2 µs, 802.11 SIFS at 10 or 16 µs, 802.15.4 at ~192 µs).
BLE link-layer timing is arguably harder than LTE HARQ's, and the hardness is real: a general-purpose core's interrupt-and-schedule path cannot reliably hit a ±2 µs window, which is why every shipping radio puts that turnaround below the software line. The question is only *what* sits below it.

Three answers exist and the design takes the third.
A **FullMAC controller** runs the entire link layer and MAC as firmware on a hidden core, meeting the timing trivially and being exactly the "Wi-Fi/BT controller firmware" §4 bans, an opaque processor with its own DMA and the largest foreign computer the radio architecture exists to delete: **rejected**.
**Pure software on dedicated cores** meets the turnaround by pinning a core and precomputing the response, which is Microsoft's **Sora** (NSDI '09), core-dedication and lookahead hitting Wi-Fi SIFS in software: it keeps everything inside the trust structure and spends the tightest real-time budget on the most jitter-sensitive path, which at 150 µs and 16 µs is fragile, so it too is **rejected**.
A **fixed-function timing sequencer inside the register-slave transceiver datapath** (§15) meets it with a hardware packet-end event starting a fixed timer that drives the RX/TX switch and gates a software-prepared buffer out at the exact deadline, with no instruction fetch, no writable program, no firmware, and no protocol decision.
That third answer is the **SoftMAC / split-MAC** partition, time-critical turnaround in fixed hardware and the link layer and everything above it in software, and it is the mainstream Wi-Fi architecture rather than an invention here.
Three artifacts supply it:

- **Linux's `mac80211`** is the reference decomposition, running the timing-critical MAC (ACK, SIFS, backoff) in hardware and the management MAC in host software, which is precisely the line §12 draws.
- **Nordic's nRF radios with Zephyr's open Link Layer** demonstrate it on the exact hardest protocol, meeting BLE `T_IFS` with a hardware *tIFS timer* (dedicated capture/compare registers) while the link-layer state machine, L2CAP, and GATT run in software.
- **openwifi** is the closest match to the form actually needed, and is already the §18 radio start-from: its *"DCF low-MAC layer in FPGA"* meets the 10 µs SIFS ACK **in Verilog rather than on a core**, which is the firmware-free, open-RTL existence proof for the fixed-function turnaround block, harvestable under the open-RTL mandate.

**The hardware/software boundary is the whole distinction, and it is a mechanism test rather than a size one.**
A controller is a processor running firmware; the sequencer is a timer plus a small finite state machine, fully described in RTL, Sail-modeled, and capability-gated: the FEC-unit and digital-front-end category, *matter, not software*, the same tolerance §4's line already extends to the DFE, the FEC blocks, and the I/Q-streaming DMA.
It passes the five-part §15 admission test the way those do: deterministic; a fixed 150 µs constant independent of packet contents, so no data-timing channel; bounded FSM and timer state reset per event, architectural rather than hidden; a register slave with no authority beyond its capability-bounded DMA window; and its autonomy is the scheduled-DMA kind, a timer firing a pre-designated buffer, not the address-dependent memory walker admission test 5 bans.

The transformation is the usual one: **the split is off-the-shelf and the verified realization is the contribution.**
None of the three artifacts is formally verified or Sail-modeled, so what the platform builds is that sequencer as one more fixed-latency entry in the timing-annotated Sail model, riding the existing transceiver RTL ⊑ Sail and WCET obligations (§11, §15).
Everything carrying protocol semantics stays in software (§12): connection-event and slot scheduling as a §11 software hard task, channel selection, framing, whitening and CRC, link-layer encryption through the crypto core, and the link-layer state machine as a Lustre control plane.
This is the same "hardness at the boundary, patchable software above it" rule the regulatory layering (§12) applies to the emission envelope, applied to timing.

The doctrine's one tolerated exception, the carrier-mandated eUICC (§4, §12), has field evidence for its zero-authority framing: a GSMA consumer certificate was extracted from a certified production eUICC in 2025 (the Kigen disclosure, root-caused to publicized test-profile keysets and patched over the air), so a certified secure element failing is an observed event rather than a hypothetical, and the containment that makes it non-lethal here (a register-slave crypto oracle with no DMA and nothing to grant) is doing real work.

**The partition generalizes past the radio into the standing sensor-front-end doctrine (§12, §15), which is the platform's rule for every transducer.**
The analog front end plus a fixed-cadence scan or sample sequencer stays matter: a register-slave AFE streaming raw samples over a capability-bounded DMA window, no per-sensor DSP core and no firmware, while all signal processing dissolves onto the host V-cores.
Capacitive touch (raw capacitance to a host touch DSP), the audio front end (microphone and speaker converters to host filtering, echo cancellation, and beamforming), the image sensor (raw Bayer to the software ISP), IMU and motion (raw reads to host fusion), and the fingerprint AFE (raw frames to the host matcher) are all instances.

Honest residual (§17): the sequencer itself books no new bullet, being a small fixed-function block folded into the transceiver datapath already in the Sail model (§17's *grows the Sail model*), with no firmware and no new trust axiom, its correctness and its 150 µs latency riding the transceiver RTL ⊑ Sail and WCET obligations the register-slave-datapath category already carries.
The generalization does book one: the radio case has an off-the-shelf firmware-free part to point at and the sensor cases do not, since commodity touch, audio, and image controllers co-design the AFE with tuned DSP firmware, so the raw-AFE silicon and its host-side DSP are a genuine net-new co-design.

---

## PIC64-HPSC, Starfire, and DICE cells: space-grade realization, radiation hardening as a manufacturing choice and not an architecture

The **PIC64-HPSC** (Microchip, for NASA's **High-Performance Spaceflight Computing** program) is the space-grade instance of the design's own substrate class: a 64-bit **application-class RISC-V** multiprocessor built around **eight SiFive X280 cores** carrying the **vector extension**, made **radiation-hardened and fault-tolerant** (pervasive ECC, lockstep options, a wide operating-temperature range), the RISC-V successor to the PowerPC **RAD750** that has flown NASA's spacecraft for two decades.
It is the existence proof that **application-class RISC-V with vectors, hardened against the space radiation environment, is a real and funded product class** rather than a research aspiration, and it validates three of the design's own choices on hardened silicon: the **RV64 plus vector** compute shape (§15), the **reliability posture** the memory subsystem and enclosure already mandate (pervasive ECC, fault containment, wide-temperature tolerance, §15, §16), and lockstep as a hardware **fault-detection** complement to §7's per-core kernel duplication for fault containment (the same G5 note the COSMIC entry logs, above).

**The faults this axis answers sit outside every model's reach.**
Single-event upsets from cosmic-ray secondaries and other radiation, total-ionizing-dose drift, latch-up, and the environmental extremes of temperature, pressure, vacuum, and vibration are met by a **space-grade realization** of the design, never by a change to the computation.
This is the outermost layer of a reliability story the spec already tells in two: the Faraday enclosure attenuates the electromagnetic-interference rate at the boundary (§15), the pervasive ECC and the multikernel's blast-radius containment catch the residual in the logic (§15, §16), and radiation-hardened silicon closes the gap between them by reducing the single-event-upset rate **at the source, the transistor**, the one lever the enclosure explicitly cannot pull (mass shielding being counterproductive through secondary showers, §15).
The space-grade part class in general also extends the operating envelope (temperature, pressure, vacuum, and vibration) well beyond commercial ranges.

**Intel's Starfire brackets the same axis from the opposite end**, and is worth recording beside the PIC64-HPSC for the contrast rather than as a second import.
An 18A space-grade SoC for the US government with samples due Q3 2026, it pushes a **leading-edge commercial-class part** (RibbonFET and backside power, an eight-core CPU with an on-die NPU) into orbit by **design-level hardening** rather than by a mature radiation-tolerant node, across a minus-55 to 125 Celsius junction range.
Where the PIC64-HPSC hardens a conservative design, Starfire hardens an aggressive one, and both make the move this design makes: **harden a commercial-class design rather than invent a space architecture**, the two of them bracketing the realization axis from its conservative and leading-edge ends and establishing between them that a modern vector machine can be carried into the space environment at all.

**Why the lineage transfers.**
Space-grade is a property of the **process and the RTL cells, orthogonal to the instruction set**, so it costs nothing on the scarce trust axis and everything it costs on the free engineering axis, the same reference-not-base split used for Codasip X730 and the CVA6-CHERI silicon (above).
A single-event-hardened flip-flop (a DICE or triple-modular-redundant latch), an error-hardened SRAM cell, and a latch-up-immune process hold and compute the **same architectural state** as their commercial equivalents, so the Sail model is unchanged and **RTL ⊑ Sail still holds**, the hardened cell refining the very model its commercial sibling does: no new mechanism, no new Sail surface, no proof obligation, and no guarantee lowered.
It is therefore admitted on **exactly the ground ECC and the Faraday enclosure are** (§15): a physical reliability measure the verification cannot itself provide because the fault is physical, categorically distinct from a declined security hedge like PMP or the IOMMU (those duplicate a spatial mechanism CHERI already verifies, so *verify rather than hedge* declines them; radiation hardening duplicates nothing, it hardens the substrate every verified mechanism runs on, so the same axiom **admits** it).

**Radiation qualification is a physical-layer evidence obligation, not a datasheet number.**
The lesson Starfire teaches *by contrast* is what a space-grade part must actually publish: not cores, TOPS, temperature, or lifetime, but its **total-ionizing-dose limit, single-event-latch-up threshold, and single-event-effect cross-section**, established by a radiation test campaign.
The PIC64-HPSC1000-RH publishes 200 krad(Si) and latch-up immunity to 78 MeV·cm²/mg; Starfire's are still under evaluation, which is the honest tell that it is not yet radiation-qualified.
Those numbers come from physical test campaigns rather than from a formal model, so they are **evidence about the physical realization that no formal proof can reach**, the radiation-environment analog of the bounded bring-up evidence this design already leans on (commercial FEV and riscv-formal for RTL conformance, IRIS backside inspection for the fab residual): they discharge a qualification obligation by testing and enter no proof-checker trust base, exactly as those complements do not.

**The correction layer already carries the load hardening only lightens.**
This design is better placed than a bet on the process alone, since it detects, corrects, or contains upsets pervasively (SECDED and DECTED ECC on every array, multikernel blast-radius containment, fail-stop, §15, §16): it does not need a hardened node to force the raw upset rate down to a commercial fault model's tolerance the way an unhardened commercial part flown to orbit must, so the leading-edge susceptibility that makes Starfire's bet hard is a load the correction layer already carries and hardening only lightens.

**Deployment grading.**
Radiation-hardened processes lag commercial nodes in density, frequency, and unit cost and run at low volume, so a hard *universal* mandate would tax the consumer form factors the design also targets (§2, no fixed form factor).
The realization is therefore **graded to the deployment**: full radiation-hardening by design for the spaceflight, avionics, and critical-infrastructure cases whose environment demands it; radiation-tolerant commercial-grade, or none, where it does not.
Because the choice changes no computation, a deployment moves along this axis **without re-verifying anything**: the proof obligations are identical for the hardened and commercial realizations of the same RTL.

**What is imported, and what is not.**
Only the **hardening realization** transfers, onto the design's own RV64+CHERI profile: the radiation-hardened-by-design process (single-event-hardened cells, latch-up immunity, the wide temperature range), the fault-tolerance features, and the demonstration that a modern RISC-V vector machine survives the environment at all.
The space-grade parts themselves are **reference, not base**, and the architecture is what does not transfer: the PIC64-HPSC is **RV64GC** (the C compressed extension the profile drops and the scalar floating-point it folds onto the vector unit, §15), it carries an **MMU** and boots a conventional operating system (the profile deletes the MMU for a single address space, `satp` Bare, §15), it is **not CHERI** (the spine of the whole design), and its SiFive cores are third-party RTL whose vendor verification is bring-up evidence, never the closing **RTL ⊑ Sail** axiom (§6, §15).
Starfire's packaging points the other way as well: it is a **Foveros multi-die stack** (18A CPU and NPU tiles over an Intel 3 GPU tile), whereas this design integrates on a single die; the multi-die mechanism is not part of the import.
So the design hardens the manufacturing and the RTL of the machine it already specifies, rather than adopting a space processor's architecture: changing no computation and lowering no guarantee.

**Relationship to execution redundancy.**
This is the physical-hardening sibling of the redundant-execution entry: where lockstep, TMR, and DIVA spend **area on replication** to detect or mask faults (declined by default here in favor of the multikernel's asymmetric-trust containment, lockstep logged for G5), radiation hardening spends **process and cell margin** to reduce the fault rate at the source, and the two compose cleanly.
Hardening lowers the upset rate the ECC and containment logic must absorb, so it **strengthens that entry's bet** (that ECC ⋈ fault containment ⋈ a verified core with no design faults covers the random-fault case without N-modular redundancy) rather than competing with it: fewer upsets to catch, and a G5 lockstep option still available on top where a safety case wants masking too.

**What the platform takes.**
Radiation-hardened, wide-envelope silicon is a **realization axis graded to the deployment**, changing no computation and lowering no guarantee; its normative footprint is the §15 instruction to harden the process and RTL of the specified design where the environment requires it.
This is the *engineering-is-free, trust-is-scarce* axiom reading a physical-reliability measure the way it reads ECC and the enclosure: **admit the mechanism that costs only engineering and reduces a physical fault rate the verification cannot reach.**
It books **no new §17 residual** (it lowers a physical fault rate and adds no trusted surface) and does not touch the fab residual either: a radiation-hardened die is still a fabricated die whose correspondence to the verified RTL rests on the same evidence (§17).

---

## Fuchsia OS: the capability-IPC model (handles out-of-band, bounds in the schema)

Google's Fuchsia is the shipping demonstration that a **from-scratch capability microkernel** (Zircon) can carry a real consumer device OS with **no ambient authority**: every resource is an unforgeable **handle**, a component receives only the capabilities its **manifest** declares, and there is no POSIX-by-default, no global namespace, no `fork`.
That posture is §8 (capabilities as the sole authority) and §12/§13 (per-compartment capability manifests) at product scale: the same ground seL4 (above) supplies as *proof* and Fuchsia supplies as *shipping evidence*.
But the load-bearing import is **FIDL**, Fuchsia's interface-definition language, and its **Zircon-channel** wire model, the exemplar sitting *beneath* the §12 interface layer: a FIDL message travels as **bytes plus out-of-band handles** over a channel, exactly §12's rule that a ring descriptor "names only indices into a per-session table of pre-delegated capabilities, plus offset/length" with **authority arriving over the control plane, never across the data plane**: a Zircon channel is what the §12 data plane structurally *is*.
FIDL also carries the two disciplines the §12 IDL profile has to *add* to its WIT-derived type layer: **mandatory schema bounds** (`vector<T>:N`, `string:N`, `array<T,N>`: no unbounded wire object) and **decoders hardened at a trust boundary**, both native to FIDL because it was built for **mutually distrusting compartments** across a capability kernel: this platform's exact setting (§12, §16).
So the interface stack is a deliberate **hybrid**: the *type/interface* layer is WIT-derived (worlds → manifests, resources → capabilities; §12, §13), while the *wire/data-plane* layer is FIDL/Zircon-channel.
Where the design parts company is the usual mechanism swap: FIDL and Zircon are **unverified C++**, so marshalling becomes the **Narcissus copy-once verified parser** (§5), Zircon **handles and their rights become seL4/CHERI capabilities** (the taxonomy re-mapped, not inherited; §8, §15), FIDL's missing **world** concept is why the *type* layer is WIT rather than FIDL, and FIDL's missing **information-flow labels** are added as a first-class §12 concern.
Fuchsia supplies the shipping proof that capability IPC scales to a real OS; FIDL supplies the wire discipline (bounded, handle-passing, distrust-hardened) that the §12 data plane adopts and the copy-once parsers then make a theorem.

---

## PRET-style cyclic execution: pollable events and one asynchronous boundary timer

PRET-style timing and the platform's cyclic executive make device service latency a schedule property rather than an interrupt-priority property.
An interrupt arrival therefore remains an IMSIC store setting architectural pending state, but software consumes that state with ordinary loads at syntactically determined poll points; the **slot-boundary timer is the sole asynchronous trap**.
This carries the time-triggered lineage through event delivery instead of retaining a preemptive-OS interrupt path beside it.

**What remains asynchronous.**
The trap path itself does **not** go away.
The boundary timer must stay asynchronous, because the cyclic executive's entire temporal-isolation claim is that a partition "cannot overrun its slot" (§7) against a compartment that declines to yield; a cooperative-poll boundary would rest slot enforcement on the compartment's own good behavior, which is not a mechanism.
So `MTCC`/`MEPCC`/`MTDC`, the capability trap vector, and the save/restore sequence all remain (§7, §15): the imported design does not delete the trap path, it **narrows the asynchronous trap set from {boundary timer, every device MSI, watchdog bark} to {boundary timer}**.
What that narrowing buys is not the trap machinery; it is everything built to *govern* the trap machinery.

**Consequences across the ISA, TAL, and kernel proof.**
(a) **The interrupt-state sentry triple dies.** The CHERIoT lineage's `enabled`/`disabled`/`inherit` forward- and backward-edge sentries exist to make interrupt masking structured and lexically scoped, with the caller's state captured in the return capability and restored automatically on return (§8, §15).
With the boundary timer the only asynchronous trap, and with masking it precisely the cross-partition attack §8 defends against, **interrupt-enable state has nothing left to govern**: the three sentry types collapse to one plain sentry.
That removes sentry-otype space and the interrupt-state capture-and-restore semantics of capability jump-and-link from the Sail model; the interrupt-state field of the return capability and its decode and auto-restore path from the RTL; the interrupt-state index on sentry types from the **CHERI-TAL**, where the on-device checker's order-of-10³-line budget is a hard constraint on the metatheory and not merely on the implementation (§17); and it makes the two lemmas the discipline exists to prove (*no compartment leaves interrupts masked past a return*, *cross-compartment calls force interrupts enabled*) **vacuous rather than discharged**.
(b) **The bounded-interrupt-disabled-window allow-list is deleted, not bounded.** A maskable-interrupt design carries a statically-auditable per-compartment allow-list of interrupt-disabled entry points with worst-case durations priced into the partition-switch budget (§8, §11).
With nothing maskable the list is empty; the kernel's own boundary handler remains non-interruptible, but that is *one* region inside verified kernel code, discharged by the switch's padded constant cost (§15), not a per-compartment audit surface.
Nor does the boundary timer itself need a mask: the switch completes at a padded constant far shorter than any slot, and the timer does not re-arm until the handler reprograms `mtimecmp`.
(c) **The kernel loses a case split at every entry point.** §7 makes the kernel event-driven with no kernel threads, "executing only on trap/syscall/interrupt on the caller's budget"; deleting asynchronous device delivery leaves exactly two entry reasons, synchronous syscall/exception and the boundary timer, so the interleaving question *can a device MSI land mid-syscall* stops being a case in the Coq kernel proof.
(d) **The AIA delivery-selection surface goes.** The IMSIC's delivery enable, threshold, and top-pending-selection machinery exists solely to choose *which* pending bit to deliver; under polling software reads the pending array directly.
This is the same trim §15 already performed once on the AIA (dropping the supervisor and guest/VS interrupt files as dead Sail surface under the single Machine mode), applied a second time in the same direction.

A fifth, smaller gain is worth naming because it runs the other way from most subtractions: **WCET improves rather than costing.**
Asynchronous delivery puts a potential trap point at every instruction boundary, so any code region carries a preemption term, bounded by the allow-list but present.
Polling makes trap points **syntactic** (they are poll sites, already nodes in the typed control-flow graph the §5 syntax-directed max-path sum walks), so the derivation **loses a term instead of bounding one**.
Against a design that deliberately takes the trivial sound bound and forbids tools that only tighten it (§5), this is the rare subtraction that tightens the bound for free.

**What does not transfer from conventional ISR systems.**
The intuition is that a hardware interrupt reaches a handler in tens of cycles where a poll loop reaches it in a poll period, and that this is a real capability worth ISA surface.
The intuition is correct about *hardware* and wrong about *this machine*, and the reason is not the trap path at all: **the cyclic executive had already made low-latency service a schedule property rather than an ISR property.**
§7 already states it twice: aperiodic events get "dedicated polling or sporadic slots sized into the frame," and worst-case device service latency is "a *schedule corollary, not an interrupt property*," with latched-until-slot meaning an event waits at most its owning server's slot period plus in-slot handling WCET.
A keypress on the current design does not preempt anything.
It sets a pending bit that the owning driver's slot consumes, and end-to-end latency remains bounded by the slot period.

**The residual latency benefit forgone.**
If the device's owning partition happens already to be running when the bit sets, asynchronous delivery reaches the handler in trap latency rather than at the next poll site.
Against a major frame measured in hundreds of microseconds, that difference is noise; and it applies only when the owner is the currently-scheduled partition, which for a human-input device is by construction the uncommon case.
The deeper reason the PS/2 intuition does not transfer is that it is an intuition from a **preemptive priority-scheduled** OS: an interrupt is fast there because it can *promote* work into the CPU ahead of what was running.
Here there is no priority to preempt into.
An interrupt can set a bit sooner, but **nothing can run sooner**, because *what runs now* is a composition-time constant (§7), and time never crosses a partition boundary even when donated (§7, non-work-conserving by construction).

**Sub-slot deadlines remain fixed-function.**
The sub-slot radio turnaround (BLE `T_IFS` 150 µs ± 2 µs, 802.11 SIFS 10/16 µs, 802.15.4 ~192 µs) is met by the fixed-function SoftMAC turnaround sequencer described above, whose own justification is that a general-purpose core's interrupt-and-schedule path cannot reliably hit a ±2 µs window.
HARQ feedback and DRX paging occasions get sporadic slots sized to their deadlines (§7).
The design has therefore already concluded, on its tightest path, that the interrupt path is *not* the low-latency mechanism: anything tighter than a slot is RTL, and anything a slot can hold is a schedule parameter.
Deleting asynchronous delivery removes nothing from either category.

**Residuals.**
(1) **Watchdog bark degrades to slot granularity.** §7 makes the RoT watchdog's bark an ordinary MSI into the sentinel's interrupt file, and its value is precisely to reach a core that is *alive but wedged*, which polling by definition cannot.
The answer is that the bark check folds into the retained boundary-timer handler: the boundary trap fires regardless of what the compartment is doing, so the sentinel observes a bark within one slot, and if even the boundary path is dead the **bite** (a reset line, outside the interrupt model and unmaskable by construction, §7, §16) is the backstop it was always specified to be.
Bark latency thus moves from trap latency to one slot period; that is a genuine degradation of the surgical-response window (§16) and is booked, not denied.
(2) **A driver that would have slept mid-slot now sleeps to the boundary.** Race-to-idle with in-slot clock and power gating (§15) would, under asynchronous delivery, let a gated core wake on delivery; under polling it wakes on the boundary timer it would take anyway, so a device serviceable mid-slot is instead serviced one slot later.
This is a latency-for-energy trade already inside the schedule's own bound and sized by §11.
(3) **Polling consumes the slot it polls in.** The cost is energy rather than throughput, because slack was never recoverable in the first place: the schedule is non-work-conserving across confidentiality boundaries, an idle slot staying idle because donated time is a timing channel (§7).
A fourth item is sometimes offered as a loss and is not one: per-device poll cadence must now be sized explicitly, but §7 **already** requires exactly that sizing, so this strengthens a standing obligation rather than creating one.

**Why the static-schedule lineage makes this possible.**
Asynchronous delivery is not *inadmissible* under the five-part test (§15): it is deterministic, and per-partition interrupt state is identity-partitioned or swapped at the switch, so it does not fail test (3) the way a predictor or an LR/SC reservation does.
It falls instead to the **defense-in-depth companion clause** (§15) read in the subtractive direction: its function (getting a device serviced within its deadline) is already covered *in full* by the static schedule, so it is a second mechanism for a job one mechanism already does, and the primary is the one the design proves.
And the shape of the win is the platform's most-used argument, transplanted: **deleting asynchronous delivery is strictly stronger than bounding the mask windows**, exactly as deleting the branch predictor was strictly stronger than flushing it (§15) and deleting `Zalrsc` was strictly stronger than clearing its reservation (§15).
In each case a *bounded* obligation ("is the mask window short enough?", "did we flush the predictor completely?", "was the reservation cleared?") becomes an **absence** obligation, and the absence is checked structurally rather than discharged.
That is also why this lands where it is worth the most: an absence obligation is a structural check on the RTL, and RTL ⊑ Sail is the least-built layer of the stack (§17, §18).

**Scope.**
The system gives up the ability to reach code that is running but not polling, and keeps exactly one mechanism that can: a timer that fires at a composition-time-known instant.
That is acceptable only because the schedule is static: every deadline the machine owes is a slot parameter fixed at compose time, so there is no event whose *arrival* the machine needs to react to faster than the slot it was scheduled into.
A design with any dynamic scheduling, any priority, or any admission of runtime-arriving work could not take this deletion; this one can, and the price is a bark window that widens from microseconds to one slot.

**What the platform takes.**
Asynchronous interrupt delivery is **deleted**: interrupt arrival remains a store to an interrupt file setting architectural pending state, consumed by ordinary loads at poll sites inside the owner's slot, and the **slot-boundary timer is the sole asynchronous trap on the machine**.
The interrupt-state sentry types (`enabled`/`disabled`/`inherit`) are removed from the CHERI profile and the CHERI-TAL with the masking discipline they carried; the bounded-interrupt-disabled-window allow-list (§8, §11) is deleted rather than audited; the AIA delivery-selection machinery is trimmed to the pending array; and the watchdog bark is checked in the boundary handler.
The platform axiom decides it as ever, with the local twist that the feature's headline benefit (low-latency device service) **was not present to lose**: the cyclic executive had already made service latency a schedule corollary, so what asynchronous delivery still bought was a sub-slot tail, paid for in ISA surface, RTL, typing rules, kernel case splits, and a WCET preemption term.
**Honest residual (§17):** the watchdog bark's surgical-response window widens from trap latency to one slot period, leaving **bite** as the only sub-slot response to a wedged sentinel; a device serviceable mid-slot is serviced at the next poll site or the next slot, so §11's per-device cadence sizing becomes load-bearing for every aperiodic device rather than for the radio paths alone; and poll-site placement becomes a WCET-visible source-level obligation on driver code (cheap, since poll sites are already CFG nodes the §5 cost annotation walks, but no longer implicit).

---

## RVV and Zfinx lineage: scalar floating point folded onto the vector FPU

RVV already supplies IEEE-754 arithmetic on every vector-bearing core, while the Zfinx family demonstrates the broader idea of sourcing floating-point operands outside a dedicated scalar FP register file.
The platform combines those precedents by treating a scalar float as a VL=1 vector operation: the `f0`–`f31` register file, scalar FP instruction class, and dynamic rounding CSR become a redundant second wrapper around an FPU the cores already carry.

**What is redundant, and what is not.**
The vector FPU performs the same IEEE-754 arithmetic; a "scalar" float is just a single-element (VL=1) vector operation on it.
So the scalar instruction class, the `f`-register file (context-switch state, one more term in the total-restore obligation that stands in place of flush-set membership, R-15-214), and, decisively, the *scalar* fixed-latency-FPU-including-subnormals timing contract plus the scalar `FDIV`/`FSQRT` constant-time carve-out are all redundant.
That last item is the prize: it is **one of the two floating-point timing crown jewels** (§15), and folding onto the vector unit *deletes* it rather than re-proving it: the contract is stated once, for the one FPU, not twice.
What does **not** vanish is the FP arithmetic itself (adders, multipliers, subnormal handling, divide/sqrt): it lives on the retained vector FPU, which still owes the fixed-latency-including-subnormals contract.
This is a consolidation-and-deletion of the *scalar wrapper*, honestly, not an elimination of floating point.

**Static rounding falls out for free.**
With no scalar FP, the only remaining rounding-mode consumer is vector FP, and mandating **static rounding** (the mode encoded per-instruction, default round-to-nearest-even) deletes the dynamic `frm` CSR: a mutable field that would otherwise context-switch under that same total-restore obligation; exactly the determinism the profile already imposes on branch prediction and atomics (no hidden mutable state surviving a partition switch).

**Residuals: ABI, setup cost, and profile divergence.**
Two things are genuinely given up.
(1) **Ubiquity of scalar float.**
Ported userspace (UI layout, coordinate math, general numerics; §12/[userspace-porting.md](userspace-porting.md)) uses scalar float pervasively, and the standard RISC-V `lp64d` ABI passes it in `f` registers; folding it onto VL=1 vector ops means a **soft-float-register ABI** and per-operation `vsetvli`/`vmv` setup.
(2) **A non-standard ISA.**
The application-class `V` extension formally *requires* `F`/`D` (it depends on `Zve64d`, which depends on `D`), so vector-FP-without-scalar-FP is a **fork** of the base ISA, carrying its own Sail surface for the integer-register-to-vector-FP move path.
Both costs land on the axes the platform spends freely (*engineering is free; performance is subordinated*, §1) and buy down the scarce one: a deleted timing crown jewel, a deleted register file, and deleted rounding-mode state, on a Sail model and toolchain the project already curates from scratch.

**Scale and precedent.**
Vector-FP-without-scalar-FP at application scale is uncommon (most RVV cores keep scalar `F`/`D` for exactly the ABI reasons above), so this is a bounded extrapolation like the single-address-space and single-privilege-mode bets: bounded because the vector FPU is the *same* IEEE-754 unit, the fold is a mechanical compiler lowering (VL=1 ops in the `Zfinx`-adjacent idiom of sourcing FP operands outside a scalar-FP register file), and nothing about correctness changes, only where the operands live and what they cost per op.

**What the platform takes.**
Scalar `F`/`D`, the `f`-register file, and the dynamic rounding-mode CSR are **removed**; all floating point is vector (VL=1 for scalars), rounding is static, and the ABI is soft-float-register.
The FP timing contract is stated once, for the vector FPU (§15).
The platform axiom decides it as ever: a redundant FP datapath and one of the two FP timing crown jewels are deleted for an ABI change and a per-op vector-setup cost the subordinated-performance goal absorbs.
**Honest residual (§17):** floating point rests on the single vector FPU under a non-standard vector-FP-without-scalar-FP profile (a small new Sail surface for the operand-move path, an uncommon configuration at application scale): offset against the deleted scalar datapath, `f`-register file, scalar FP timing contract, and dynamic rounding-mode state; a net shrink, booked in §17's proof-trust-base accounting.

---

## Cerebras and all-SRAM machines: main memory without refresh management, RowHammer counting, or PRAC

Cerebras supplies the large-scale existence proof for an all-SRAM, cacheless machine; embedded tightly-coupled-memory systems supply the smaller precedent.
This platform applies that lineage to **on-die main memory on the same die as the cores**, accepting far lower capacity in exchange for flat latency, high bandwidth, and deletion of the DRAM control mechanisms.
Where it departs from the lineage is that it takes **two** static latency classes rather than one, bespoke 6T SRAM for the scalar working set and oxide-semiconductor gain-cell decks for bulk (§15), which is a second constant and not a second *tier*: placement is fixed at composition, and no cache, migration, or promotion moves anything between them.
DRAM, an SRAM/DRAM hybrid, and non-volatile working memory do not transfer, because each restores a runtime mechanism or a remanence property the two-class model removes: a hybrid restores the reactive placement decision, and non-volatility restores at-rest plaintext as a designed property rather than as a bounded window.

**Proof-surface and timing-channel reduction.**
DRAM stores each bit as charge on a capacitor that leaks and must be refreshed, and that same charge-disturbance physics is the RowHammer primitive: repeated activation of an aggressor row flips bits in a victim row.
SRAM stores each bit in a bistable cross-coupled latch: no leakage, no refresh, and no remote charge-disturbance primitive on the class it carries (SRAM has its own far weaker, local read/write-disturb and half-select modes at aggressive nodes, covered by ECC and cell margin, not a remote flip).
And there is nothing to *manage* on either class: the entire deterministic-refresh-management (RFM) cadence, the per-row-activation-counting (PRAC) counters, and their alert-and-back-off feedback loop are **deleted, not merely tuned**, the bulk class's refresh being a composition-time schedule that reads no access pattern (R-15-184).
That loop is a load-reactive coupling on the most-shared resource, the very thing a DRAM design must demote to a fail-stop tripwire and book as a §17 residual; removing it removes that residual, shrinks the proof surface (no refresh-cadence or PRAC crown-jewel spec, no reactive-refresh timing channel to argue closed, and the DRAM channel and sub-channel structure with its row-buffer state gone from the Sail model, so the worst-case memory-access latency is a flat SRAM constant rather than a pessimistic row-miss bound), and cleans the graded memory-tier isolation hierarchy: the sub-channel sharing a DRAM design must grade as *weaker* (two sub-channels of a die share its refresh and PRAC) has no such coupling to grade around when the memory is SRAM (§15).
SRAM's higher speed also *improves* performance (lower latency, higher bandwidth, no activate, precharge, or refresh stalls), a rare case where the security-motivated choice is not on the subordinated performance axis.

**Capacity cost and engineering mitigation.**
An SRAM cell is far larger than a DRAM cell, so capacity is much smaller per unit area and static leakage (idle power) higher: the honest, and only, downside.
Both are bought back by static, transistor-level levers that add *no runtime behavior* (so none disturbs the admission tests): **sequential (monolithic) 3D tiers** and **CFET-stacked cells** raise density, **High-NA EUV** patterning raises per-tier density and yield, and **asymmetric-threshold (asymmetric-Vt)** cells cut leakage and raise stability statically.
**Backside power delivery** would improve the power grid and free front-side routing, and is nonetheless refused, because its opaque metal occludes the backside optical path IRIS images through and a single-die machine has nowhere else to put it (§17).
A **chiplet** realization and its vertical bonded-die form do not transfer, so the vertical capacity lever is sequential monolithic 3D on the one die.

**The capacity this yields, at the reticle limit.**
Fix the footprint at one reticle field (about 858 mm² full-field, or about 430 mm² on a High-NA half-field scanner, the largest a normal, non-wafer-scale chip reaches) and leave the bottom logic tier to the cores and the rest of the non-memory system: main memory is then what the *sequential-3D* SRAM tiers above it hold, on the same die, with the cacheless hierarchy described next.
Usable capacity runs well under the raw cell, because roughly half of it is spent before it is addressable: a 2 nm gate-all-around high-density cell reaches about 38 Mb/mm² (4.75 MB/mm²) of raw macro, but the SECDED-to-DECTED ECC, the native CHERI tag bits, and the tier's assist, redundancy, and island-partition floorplan leave about 2.6 MB/mm², near 2 GB, per full-reticle tier (and near 1 GB per High-NA half-field tier, which is why tier count rather than tier area is the lever that has to deliver).
No cryptographic metadata appears in that budget, the memory path carrying neither counters nor authentication tags; the separately evaluated memory-cryptography mechanism is not part of this lineage.
Scaled by the accepted 3D stacking, that is about 2 GB at a single tier and roughly 16 GB at an aggressive eight-high memory stack on 2 nm; a denser 0.7 nm-class CFET cell (extrapolated near 4 MB/mm² usable) carries a comparable stack into the low tens of GB and a sixteen-high extreme toward 64 GB.
The recorded maximum main memory for a normal-sized, reticle-limited, non-wafer chip is therefore **tens of gigabytes, of order 16 to 64 GB at the best nodes**, not the hundreds of gigabytes to terabytes a DRAM design reaches: the density price stated plainly, and the accepted cost of the deletion above (§15, §17).

**Assist circuits: the static form only.**
SRAM read/write *assist* circuits (negative bitline, wordline underdrive, VDD collapse, and the like) recover low-voltage margin and can lower operating voltage further.
Only a **fixed, composition-time-configured** assist is admitted; the dynamic, adaptive, or data-dependent assist that would add runtime state or a data-timing channel is declined, on the same *verify rather than hedge* grounds that keep the whole microarchitecture static and reactive-mechanism-free (§15): the exploitable, complex form is exactly what a design that ranks simplicity, reliability, and security above capacity should refuse, and asymmetric-Vt plus backside power carry most of the same low-voltage benefit statically.

**What this decision does *not* buy: a reason to encrypt memory.**
On-die memory sits within the physical boundary, exactly like the on-die scratchpads, so putting main memory on the compute die removes the interface that memory encryption and an integrity tree exist to protect, rather than merely shrinking it.
Both are therefore absent, and the memory controller carries no key material at all (§15).
The one clean simplification the bespoke SRAM buys here is **native tag bits**: a tag-less DRAM forces CHERI validity tags into a reserved-memory tag table behind a partitioned tag cache, but SRAM is widened to carry the tags *in the word*, deleting the table, the cache, and with them a whole element of shared microarchitectural state and its admission-test bookkeeping (§15).

**What the platform takes.**
Main memory is bespoke SRAM on the same die as the cores; refresh, RFM, PRAC, self-refresh, and DRAM-side autonomous power modes are absent; RowHammer narrows to the per-class residual R-15-184 states; CHERI tags are native SRAM bits; and the density and leakage response is static process and circuit design rather than a reactive controller.

**Honest residual (§17):** capacity is materially lower than a DRAM design's, the accepted price, and lower still than a chiplet or bonded-stack SRAM design would reach, the price of a singular trust structure; idle leakage is higher, mitigated but not erased by the static levers; and the capacity figure now rests on **sequential-3D tier count**, the least mature lever in the design and the one with no verification-effort substitute.
That dependency is **discrete rather than graded**: tier count is gated on complementary devices at a back-end thermal budget reaching array quality and manufacturable scale, which low-temperature p-type has not, so the honest two-case reading is a working vertical lever with tier count as an ordinary cost question, or no vertical lever and a single planar tier near 2 GB at a full reticle; §18's staging is written against the one-tier case.
The gate is a scale-and-quality threshold rather than an empty literature, and stating it the other way would date badly. Four families are on record at the back-end budget: classical p-type oxides whose mobility and off-state anti-correlate and whose complementary circuits stop at single 6T cells, Se-alloyed tellurium suboxide at 10⁶–10⁷ on/off and ~15 cm²/V·s below 250 °C from a single group, complementary 2D channels on 300 mm at a 50 nm pitch with the p-contact one and a half to two orders behind the n-side, and a complementary back-end silicon route with the strongest device figures of the four (full CMOS at 400 °C by nanosecond laser anneal meeting industrial figures of merit; roll-transfer-printed single-crystal nanomembranes through three tiers to working 6T cells). What keeps every one of them short of a memory array's budget is scale and pull together: no complementary pair at the back-end budget exceeds the single cell while the n-type-only side has crossed to a 275-megabit array, and every industrial back-end-transistor program is architected n-type-only, so the application that industrializes back-end devices exerts no pull on this gate (§15).
The vertical lever costs no inspectability, the two density levers that would occlude it being graded by tier rather than by die, which is the tier-graded process decision below (§17).

---

## Cacheless RISC-V and explicit scratchpads: flat SRAM removes the hierarchy caches hide

Cacheless RISC-V cores running from tightly coupled SRAM establish that caches are optional to the ISA, while Cerebras demonstrates the same choice at the opposite scale.
Once main memory is flat, low-latency, high-bandwidth on-die SRAM, there is no slow tier for L1/L2/L3 to hide; a cache hierarchy would add history-dependent timing, flush rules, and coherence without restoring a missing memory technology.

**What the deletion buys, on the scarce axis.**
A cache exists to bridge the latency and bandwidth gap between a fast core and slow DRAM, and the on-die main memory above removes that gap: there is no slow tier left to cache, each class being one flat constant rather than a hit-or-miss distribution.
What is deleted is not merely area but a *hidden, reactive, stateful* mechanism, a feedback loop from access history to placement and timing, the exact class the profile deletes everywhere else (the MMU, the dynamic branch predictor, the reactive refresh loop, dynamic DVFS): a cache is that pattern in the memory path, and deleting it is *strictly stronger than partitioning and flushing it*.
The dividend is concentrated where this design spends most.
The dominant WCET-pessimism term is gone: every access is the flat SRAM latency, not the hit-or-miss distribution an abstract-interpretation analyzer (aiT-class) must bound, so WCET's residual memory term is a constant (§11, §15).
The entire cache-timing side-channel class, the canonical microarchitectural channel and the substrate of the transient-execution family, is deleted *at the source* rather than closed by way-coloring and `fence.t`: admission tests 2 and 3 are satisfied on that axis by absence, the wrong-path fetch I-cache footprint a static-prediction design still had to partition is gone, and the `fence.t` flush set shrinks toward the store buffer alone (§15).
The cache-coherence protocol and its directory leave the Sail model, within an island and across islands alike, so the isolation story simplifies to memory, NoC, and power partitioning under Ztso consistency, and the way-partitioning apparatus is unneeded (§15).

**The cache-versus-scratchpad distinction is the whole point.**
Deleting the *cache* is the scarce-axis win; it is not the same decision as deleting *fast local memory*.
The retained fast structures are not caches and carry none of the cost: the register files; the Ztso store buffer (ordering, drained at a switch); a static-path fetch buffer down the statically determined path (deterministic, not history-indexed); and the explicit software-managed scratchpads of the V- and M-class datapaths.
The test each passes is that its contents are a function of the program text or an explicit software placement, never of access history: address-indexing describes the lookup, history-dependence describes the contents, and only the latter carries the channel.
The test rules out the structure a memory integrity tree would need, a buffer of *recently-used* nodes, on exactly this ground: a data cache is address-indexed too, so being address-indexed excuses nothing, and that is one reason the separately evaluated memory-integrity tree does not transfer.
An explicit scratchpad is capability-governed plain memory at a fixed address range, WCET-exact and coherence-exempt, holding no reactive or hidden state, so it adds no timing channel, no flush obligation beyond the eager zeroize already accounted at a partition switch (§7), and no WCET pessimism: it is *far cheaper on the proof axis than a cache* (a modeled memory region and its partition-switch zeroize, not a dynamic reactive structure carrying a timing channel, a flush-completeness obligation, and coherence), though not literally free, which is exactly why the V- and M-class carry one (their datapath throughput, systolic-GEMM and vector-operand reuse, rests on it, not merely its latency, so it is architecturally intrinsic, not a substitute cache).

**Scalar cores carry no local memory tier, and the reason is two-sided, not a wash.**
A scalar scratchpad is *purely* a performance structure, but it is not free on the scarce axis: it adds a modeled memory region, its partition-switch zeroize state, and RTL ⊑ Sail surface (far below a cache's dynamic, reactive cost, yet not zero), so dropping it *is* a small proof-shrink, the design's standing trade of subordinated performance (§2) for a smaller model.
It is also a poor performance bet for the case that motivates it: a scratchpad is *statically* managed, capturing only what the compiler can place ahead of time, not the unpredictable working set of irregular, pointer-chasing code, which is precisely what a cache captures dynamically and a scratchpad cannot.
So scalar cores default to *none* (the irregular-code latency is recovered off-device by the mandatory static layout: the §10 code order and the §8 memory plan's locality objective (R-08-012a), never a hardware cache), and a scalar scratchpad is admitted only as a design-space-exploration parameter where a class's access is predictable and high-reuse enough for static staging to pay.
The depth, such as it is, sits entirely in the *cache*, deleted unconditionally; the *scratchpad* is a modest, static, workload-specific tool, kept where a datapath's reuse earns it (V- and M-class) and dropped where irregular access would not be served by it anyway.

**RISC-V does not couple the caches in: it is among the least cache-coupled ISAs.**
Caches are microarchitecturally transparent in RISC-V: the ISA names no cache level, exposes no architectural cache state, and requires no cache at all (cacheless cores running from tightly-coupled SRAM are standard at the embedded scale, CHERIoT-Ibex among them), so a cacheless core is a fully conformant profile choice, not a fork.
The Ztso memory model is defined over ordering, not caches, and gets *simpler* (coherence is trivial with a single copy per location).
The one place that looks like coupling dissolves: `Zicbom` (`cbo.clean`/`flush`/`inval`) is *dropped outright*, because its only reasons to exist, cleaning or invalidating a cache line against memory, flushing to a persistence domain, or synchronizing an instruction cache for self-modifying code, are each absent by construction (no cache, volatile SRAM with durability only via the storage-device path, and W^X with no `fence.i` and no runtime codegen), so a `cbo` has nothing to manage and no consumer in the kernel or in any future userspace program; cross-island ring release/acquire ordering is native Ztso and needs neither a `cbo` nor a fence (§15).
`Zicboz` (`cbo.zero`) is unrelated and retained (a fast aligned-block zero, the eager-zeroize primitive, which is also what keeps the disclosure half of Write-before-Read closed with no per-load check, §5/§15), and the `Zicbop` prefetch and non-temporal hints were already excluded (§15).

**Objection: general-purpose, irregular workloads are what caches serve.**
Cerebras is an AI-dataflow engine with predictable, streaming access, where a cacheless all-SRAM design is a natural fit; a general OS and application core runs irregular, pointer-chasing code whose locality a cache exploits.
The honest answer is that this costs performance, deliberately: a large multi-megabyte SRAM main memory is not single-cycle (a big array has real access latency), so latency-bound scalar code that would have hit a small L1 pays main-memory latency on an in-order core that cannot hide it.
But the cost is *bounded* by the first class's low latency, a small multiple, not the order-of-magnitude a cacheless *DRAM* design would pay; the throughput-critical vector and matrix paths keep their explicit scratchpads; and the loss is on the free axis (recovered off-device by static layout, the design's standard trade) against a large gain on the scarce one.
The second class does not widen this objection, because it is where the scalar working set is not: hard-task code and hot code are placed on the first class by rule, and second-class placement carries an admission-visible WCET delta rather than a hope (§15).
This is the same posture as every other deletion in the profile: spend performance, buy proof surface.

**The interconnect divides the same way**, and the Cerebras entry above makes that comparison in full: take the static routing, decline the backpressure, the isolation-relevant half being declined on the same ground best-effort QoS is, timing that depends on another domain's activity.

**What the platform takes.**
There are no hardware caches or cache-coherence protocol; fast local memory is an explicit, WCET-exact, software-managed scratchpad where a datapath needs it and absent on scalar cores by default; `Zicbom` is dropped and `Zicboz` retained; cross-island rings use shared SRAM windows with no cache-management traffic.

**Honest residual (§17):** latency-bound, pointer-chasing scalar workloads that would have fit a conventional cache lose performance, bounded by the first class's low latency and partly recovered off-device; the accepted price of trading the cache's reactive complexity for a flat, statically-analyzable memory path.

---

## Nickel: noninterference by construction, and six interface rules that hold whatever the prover

**Nickel** (Sigurbjarnarson, Nelson, Castro-Karney, Bornholt, Torlak and Wang, OSDI 2018) is the strongest published statement of a thesis §8 should adopt in full while declining the tooling that carries it: a covert channel in an **interface** is a design defect no implementation can repair, so noninterference is cheap when the interface is designed so that it holds and expensive in every other case.
The evidence is not rhetorical.
Nickel formalized the ARINC 653 inter-partition communication interface from the standard's own pseudocode and **reproduced all three known covert channels** in it, a missing permission check, identifier allocation in a shared namespace, and leaking error codes, in one week by one author; and swapping its own kernel's scheduler for a round-robin one produced both a counterexample and a *measurable* channel that vanished when the design was restored.

**The six rules are the import, they are prover-independent, and each is separately auditable.**
- **Check the flow before validating the parameters.** Once the flow check has passed, an operation may return as many distinct error codes as it likes without leaking, which buys back the debuggability that collapsing every failure into one code destroys.
- **Partition names among domains.** Any shared namespace, thread identifiers, page numbers, port numbers, is a channel; every name is a pair of domain and local name. On a single-address-space CHERI machine this is cheaper and stronger than it was for Nickel, since a capability already *is* a per-domain name with no ambient authority, and the rule reduces to a searchable one: no interface operation accepts or returns a bare integer index into a global table (§8).
- **Do not encrypt names as a substitute.** HiStar, Asbestos and Flume hand back encrypted sequential identifiers from a 64-bit space, which Nickel notes technically violates noninterference and would require probabilistic reasoning; partitioning keeps the theorem in the logic, and that is the whole reason to prefer it.
- **Account quotas exactly, and never with an infinity.** The root quota is the physical page count fixed at composition time rather than unbounded, and each object is owned by exactly one accounting node so that a node's quota equals the sum of its objects'. Static composition makes this strictly easier here than the dynamic container hierarchy Nickel needed: the whole quota tree is fixed at build time and the sum invariant is proved once (§8, §15).
- **Admit no nondeterminism in the observer's view**, with the three sanctioned repairs: make the choice an explicit parameter, specify the algorithm exactly in the interface, or push the nondeterminism below the interface where it is unobservable. This is the most expensive rule to retrofit and therefore the most valuable to adopt at design time, and the price is measured: of the 51 person-months seL4 spent on its information-flow proof, roughly **23 went to making the abstract specification more deterministic**, nearly half the security budget paid for a property Nickel makes a precondition.
- **Let nothing flow *to* the scheduler.** A scheduler that reads domains' state and whose decisions they observe is a transitive channel between any two of them. A static predetermined schedule satisfies the rule outright, which is what §7's cyclic executive is and what seL4's partition scheduler was built to be; where dynamism is wanted, Nickel's **quantum** design is the pattern, a time slice as a first-class labelled object such that the donor must be able to write it and the recipient to read it, whose composition implies the donor may flow to the recipient, closing the channel by construction rather than by analysis.
Two more follow from reading the unwinding conditions as guidance: an action's output depends only on state its domain may read, and a newly created object never exceeds its creator's authority.

**The proof architecture imports too, and it is already Coq.**
Nickel discharges noninterference by an **unwinding** argument over a developer-supplied state invariant and observational equivalence, both of which are **untrusted**, since any pair satisfying the conditions establishes the theorem and a wrong guess fails loudly; that is the shape §8's apex proof should have, and it is exactly how seL4 proceeds.
Two of Nickel's refinements of the definition are worth restating Coq-native as sanity properties of this design's own: the **state-dependent** domain function, which degenerates to classical noninterference when the dependence is dropped, and the monotonicity check that noninterference for a policy implies it for any more permissive one.
Its refinement theorem is the caution: noninterference is not preserved by refinement in general, and Nickel buys preservation with a restriction (same actions, same domains, policy refining pointwise), so the seam from this design's abstract specification down to the CHERI machine either meets that restriction or states why the stronger noninfluence formulation survives where plain noninterference would not (§5, §8).
Nickel's own metatheory being 1,215 lines of Coq is what makes all of this importable rather than merely admirable: the theorems are on the right side of the line and only the automation is on the wrong one, which [architectural-alternatives.md](architectural-alternatives.md) records.

---

## CHERIoT-shaped object model: sealed capabilities and static composition replace CNodes and the CDT

After VSpace, page tables, MCS, SMP, and the S/U rings are removed, mainline seL4 still supplies untyped memory and retype, the capability space, the CDT and its revocation, endpoints, and notifications.
CHERIoT supplies the more natural object model for a statically composed purecap machine: capabilities live directly in registers and tagged memory, object types are sealed, and revocation is by colour and epoch under a load filter.
The platform therefore retains seL4's endpoints, notifications, and non-interference statement while replacing its dynamic capability-management layer with CHERIoT's hardware-backed representation.

**Untyped memory and retype have no post-boot caller.**
Their entire purpose is creating kernel objects at runtime under an explicit resource-ownership discipline.
This platform creates none: R-07-025 fixes the component graph and capability distribution at build time with no dynamic privilege creation, R-07-026 confines the two sanctioned runtime authority transfers (the powerbox grant and the supervision tree's restart re-grant) to edges the manifest already fixed, and R-07-028 has the M-mode firmware **install** the composed cap graph as running kernel state under an initialisation-refinement proof.
The object graph is therefore complete before the first partition runs and never grows.
Where the objects *live* is likewise already decided by a mechanism that is not the kernel's: §8's whole-program static memory plan compiles the heap rather than allocating it, colouring live ranges into physical SRAM slots at composition and checking slot disjointness as a decidable side condition of the on-device TAL type-check (R-08-010 through R-08-014).
Kernel objects are objects.
They take slots in that plan like everything else, and the plan's checker rejects a bad placement as a type error rather than trusting an allocator's bookkeeping.
So *zero kernel allocation after boot* survives verbatim and gets stronger: it held because userland had to delegate the memory, and it now holds because **no allocation primitive exists in the ABI at all**.
This is the no-consumer parsimony that excluded `Zacas`, `Zifencei`, and `Sstc` (§15), applied for the first time to a kernel object rather than an instruction.

**The capability space is the software emulation of the tag plane.**
seL4 needs CNodes because a capability on a conventional machine is a kernel-managed record that unprivileged code must not be able to forge, so it must live in kernel memory and be named indirectly, by index, through a guarded radix structure the kernel walks on every invocation.
On this machine that problem does not arise: a capability is a hardware object with a validity tag, monotonicity is enforced by the datapath, and unprivileged code already holds capabilities directly in registers and tagged memory because that is the *only* way it holds anything (§15).
Retaining CSpace beside the tag plane is therefore two capability representations, two namespaces, two forgery arguments, and two proofs, for one authority relation.
What CNodes supply beyond storage is **typing** (this capability names an endpoint, not a byte range) and **rights**, and both are already present in the hardware: CHERI **sealing** with a composition-fixed otype set distinguishes an object capability from a memory capability unforgeably, and CHERI permissions carry the rights.
This is not a substitution proposed here; it is what the CHERIoT lineage this design already follows does, and §7's own switcher, sealing, and sentries are imported from it.
The spec has in fact already conceded the point in §5: what is proved is *"more precisely a CHERIoT-class static separation kernel that borrows seL4's object vocabulary."*
The deletion finishes that sentence, dropping the vocabulary along with the machinery, because CHERIoT has no CNodes.

**A CDT would be a second revocation mechanism for a property the CHERI machinery already delivers, which is why R-08-004 carries the CHERI mechanism alone and states that no capability derivation tree exists.**
The argument is recorded here because the exclusion is the load-bearing half of taking the CHERIoT-shaped object model.
The CHERI side is fully specified and load-bearing on its own: the epoch advance is the bounded containment constant, the per-load filter makes *freed implies unreachable* hold at access time rather than at sweep completion, the sweep is sized background reclamation in its own admitted slot class, and the quarantine pool prices forced-sweep denial of service to the aggressor (R-08-005 through R-08-009).
It also covers strictly more than the CDT ever could, because it reaches every capability on the machine, including the userland capabilities in registers and tagged memory that no kernel derivation tree records.
The one thing ancestry keying buys over address keying is **subtree** revocation, revoking what one principal delegated without disturbing capabilities to the same object derived by another, and the reason address keying seems unable to express it is narrower than it looks: a *delegation* has no address of its own, so two principals' capabilities to one object key the same granule.
The authority model gives it one. Independently revocable cross-domain authority is delegated as a sealed capability bounded to a kernel-owned **grant slot**, so retiring the delegation sets the sidecar bit for the slot's granule and not the object's, and the subtree case falls out of the same load filter at hardware speed rather than a kernel walk over a tree (R-08-004a, R-08-004b).
Two mechanisms, one property, one of them verified hardware and the other the most expensive software proof in the plan: that is precisely the shape *verify rather than hedge* (R-15-013) exists to reject, and the rule had already been applied against the initialization-tag plane, MTE, shadow stacks, PMP, and the IOMMU, so applying it inside the kernel was the consistent move rather than a new one.

**Proof surface removed.**
Under seL4's object model entire, **CDT revocation**, the hardest part of the l4v corpus, would be the combined seL4/CertiKOS route's early kill-switch proof.
Deleting the CDT retires that subproof outright rather than scheduling it, and the untyped and CSpace deletions retire the retype invariants and the capability-space lookup refinement, which are the two largest remaining blocks of the l4v burden after the VM layer this design had already dropped.
It is the rare change that shrinks the obligation ledger instead of growing it.
The residual kernel proof is what §7 already says is the genuinely novel work and is unaffected: the purecap CHERI-C refinement, the multikernel non-interference composition, and the switcher and sentry verification against the Sail model.

**Why this is a net simplification.**
(1) **Surface:** deletes three object classes and their invariants from the kernel spec, the retype and capability-space invocations from the frozen ABI, the CDT refinement and its revocation theorem from the proof programme, and the corresponding object classes from the capDL-class distribution spec.
(2) **Performance:** a gain, and on the hot path.
Capability transfer in IPC becomes a register operand the hardware validates, with no CSpace lookup and no guarded radix walk, which is the kernel's most frequent operation and one of the two paths R-07-050 verifies at binary level.
(3) **Security:** nothing shed.
Confinement was CHERI's before this change (R-07-006, R-08-003); revocation was already specified end to end on the CHERI side, and the grant slot covers the ancestry case; typing and rights move from CNode fields to sealing and permissions, which are unforgeable in hardware rather than in a proof.
(4) **Grounds:** no-consumer parsimony for untyped and retype, *verify rather than hedge* for the CDT, *delete rather than defend* for the capability space.
(5) **Relocation:** none.
The composition tool already emits the graph, the firmware already installs it under an existing proof obligation, and the static memory plan already places and checks the slots.
No obligation moves into software that was not already there and already discharged.

**What does not transfer from seL4's maturity.**
Two things are genuinely given up.
(1) **Object-model maturity.**
The seL4 lineage supplies a design and specification with more independent scrutiny than any kernel spec in existence, and the object model is its most scrutinized part.
Deleting three of its five surviving classes spends that scrutiny rather than banking it, and the replacement is a CHERIoT-shaped model whose published assurance is far thinner.
The mitigating fact is that the platform was already a synthesis with a CHERIoT realization joined to an seL4 object model, and it is the seam between those two, not either one, that carried the novelty.
Deleting the seL4 half of the seam removes the seam.
(2) **The mechanical-carriage answer is not available.**
The combined route's answer to specification freshness was to carry seL4's Haskell executable model into Coq mechanically, so the scrutinized artifact is preserved rather than re-typed.
The kernel-specification provenance fork forecloses that carriage on licence grounds and this deletion removes the most scrutinized part of what it could have carried, so the whole Gallina state machine is authored fresh, which is exactly the silent failure mode §5 names as the crown-jewel risk.
The offset is that the fresh artifact is dramatically smaller: an authored specification for endpoints, notifications, partition contexts, and the switch is a far smaller oracle to get right than an authored specification of untyped, retype, CSpace, and the CDT, and the *count* of things that must be stated correctly falls even as the fraction that is authored rises.
Both costs land on labour and freshness, the axis the engineering-free axiom exists to absorb, and neither adds a member to the trusted set.

**Scope of extrapolation.**
The extrapolation assumes that the CHERIoT lineage's answer (capabilities in registers and tagged memory, objects named by sealed capabilities, revocation by epoch under an address-keyed load filter) is sufficient for a kernel whose object graph is fixed at composition, and that nothing in seL4's dynamic object machinery is load-bearing once that graph cannot change.
It is a bounded extrapolation of the same kind as the single-address-space and single-privilege-mode bets, and bounded for the same reason: CHERIoT ships this model, the design has already imported its switcher, sealing, and sentries, and what changes is which mechanism names an object, never what authority the object confers.

**What the platform takes.**
Untyped memory and retype, the capability space and its CNodes, and the capability derivation tree with its revocation are **removed**.
Kernel objects are placed by §8's composition-time memory plan and installed by the §9 boot firmware under R-07-028's existing initialisation-refinement obligation; they are named by sealed CHERI capabilities over a composition-fixed otype set; revocation is the CHERI epoch, colour, sweep, and load filter alone.
Endpoints, notifications, and the non-interference theorem are retained from seL4 unchanged.
The kernel ABI loses its retype, capability-space, and derivation-tree invocations.
**Honest residual (§17):** the object model is now CHERIoT-shaped rather than seL4-shaped, so the independent-scrutiny argument is weaker, and the Gallina specification is authored in whole, no part of it being mechanically transcribed; offset against three deleted object classes, a deleted ABI surface, the deleted CDT refinement, and retirement of the former kill-switch subproof, this is a net shrink of both specification surface and proof programme.

---

## Shaw's timing schema and aiT: WCET by composition rather than estimator trust

Shaw's syntax-directed timing schema supplies the high-level WCET lineage, while **aiT (AbsInt)** supplies the mature unverified cross-check.
The platform's in-order, static-prediction, fixed-latency profile makes the combination unusually direct: the low-level costs come from the timing-annotated Sail model and the high-level bound is a max-path sum over the typed control-flow graph, so schedulability does not rest on trusting a standalone estimator.

- **Two-layer decomposition.**
  WCET analysis is classically two halves: a **low-level micro-architectural model** (per-basic-block timing: aiT's abstract interpretation over pipeline and cache state) and a **high-level path analysis** (loop bounds + IPET over the CFG).
  On this platform the two halves land in two *already-present* layers, so almost nothing is net-new theory.
- **Low-level model: timing-annotated Sail (§15).**
  The timing discipline the profile adopted for other reasons: in-order issue, static-only prediction (no predictor-state variance), fixed-latency DIV/FPU/AMO, Ztso, cache/memory/NoC partitioning, TDM NoC, WCET-exact scratchpads, deterministic profile-guided layout (§10); *collapses* the low-level model from aiT's pipeline-and-cache abstract interpretation to a **per-(class, OPP) latency table** plus reproducible cache/fetch/memory terms, sound to the metal by RTL ⊑ Sail (Kami/Kôika).
  The non-speculative posture is itself a WCET-soundness argument.
- **High-level model: syntax-directed max-path sum, not IPET.**
  On an in-order, fixed-latency, statically-predicted core there is no pipeline overlap, timing anomaly, or dynamic predictor for the Implicit Path Enumeration Technique to resolve, so structured-code WCET reduces to **Shaw's timing schema**: a syntax-directed max over the control-flow graph with loop bounds.
  That CFG is **already typed** by the CHERI-TAL, so the bound rides as **cost annotations on the typing derivation** the on-device checker validates, and the **ILP / LP-solver machinery is deleted, not retargeted**: IPET exists only to *tighten* pessimism the deleted microarchitecture never introduces, and the standing rule is *take the trivial sound bound* (§5), so a whole net-new verified estimator is deleted with it.
- **What does not transfer: MBPTA/EVT as the admitted bound.**
  Extreme-value-theory tail estimates give a *probabilistic* bound; that is a statistic, not a theorem, the same evidentiary status as MTE's ~93% (§15) and antithetical to the proof-based determinism (G3/G4).
  Admissible only as an out-of-band cross-check that flags a wrong timing annotation, never as the admitted WCET.

**What the platform takes.**
Put the low-level half *inside* the timing-annotated Sail model (discharged by the RTL ⊑ Sail proof already in scope) and derive the high-level half **syntax-directed** (Shaw's timing schema) as cost annotations on the CHERI-TAL typing derivation: **no IPET, no LP solver, no standalone estimator** (deleted by *take the trivial sound bound*, §5).
**aiT** stays the unverified complement; **MBPTA** an out-of-band cross-check only.
The general rule this case establishes, written into §5: **any verified tool that exists only to *tighten* an already-sound bound is inadmissible, take the trivial bound** (pessimism is free by axiom, performance subordinate, §1).
Its reach is not confined to bounds: read on *artifacts* the same rule excludes the **CryptOpt** equivalence checker over already-correct, already-constant-time field arithmetic, so IPET and CryptOpt are one rule applied twice rather than two separate judgment calls.
**Honest residual (§17):** WCET is only as sound as the timing-annotated model's latency magnitudes (crown-jewel specs) and inherits the RTL ⊑ Sail residual (no sound bound before that least-built arrow closes); composability across partitions rests on the §15 isolation non-interference the timing-channel story already needs.

---

## CT-Wasm, ReLoC, and Binsec/Rel: constant-time as a property of the binary

**Constant-time (CT)** is discharged **directly on the binary** for every secret-touching artifact, the verified-C crypto core included: there is no verified-compiler CT route, so CT is a property of the artifact rather than compiler pedigree.
Where the code is **structured** (the straight-line field-arithmetic kernels, the Tier-1 secret paths) that discharge is a **decidable taint-type check in the CHERI-TAL** (CT-Wasm lineage, per-install), and only genuinely unstructured secret-dependent code falls to a relational proof (below).
The FPCC discipline's own principle is *"verification is a property of the artifact, not its pedigree"* (§5); carrying CT by *preservation* would be the one place that principle goes unmet, leaving CT a fact about **which compiler produced the binary**, so the platform declines the preservation route and verifies CT on the binary instead.

- **Coverage.**
  No path carries a CT-preserving compiler: the crypto core is compiled by the stock CHERI-CompCert, the FPCC **Islaris "no verified compiler in the loop"** path (§5) has none in the loop, and **every Tier-1/2 binary** goes through the certifying userspace toolchain (§5, §13), which emits a *memory-safety* certificate but preserves nothing about timing: so every secret-touching binary is verified on the artifact.
  A key-handling server (the radio key hierarchy, §12) or a PIN-handling app compiled by that toolchain gets memory-safety PCC and **no CT**.
  This is the exact shape of the gap the memory-safety certificate already avoids (§13): trusted-by-pedigree where it should be proven-on-artifact; one property later.
- **Structured code: a type-level obligation.**
  Constant-time is a **2-safety hyperproperty** (it relates two executions differing only in secrets), which a *functional* program logic does not carry.
  But **CT-Wasm** (Watt et al.) shows it decidable as a **taint-type discipline** (secret-labeled values the type system forbids from reaching a branch, an address, or a variable-latency op), with mechanized type-soundness: so for structured code CT is a **type-checking obligation in the CHERI-TAL**, not a proof term, and the bare Islaris/Iris-over-Sail refinement need be extended with a **relational** layer only for the unstructured residual.
- **Unstructured code: relational 2-safety over Sail.**
  For the unstructured code the taint discipline cannot type, self-composition / relational-Hoare reasoning (ReLoC-in-Iris lineage) over the Sail semantics *instrumented with the §15 `Zkt`/`Zvkt` leakage model* proves the leakage trace (load addresses, branch conditions, variable-latency operands) independent of secrets, **at binary level, in the one Coq prover** (the 2-safety theory of the §13 Iris-over-Sail base): the corner-case vehicle after the taint-type check, covering the crypto core, its field-arithmetic kernels, and the structured Tier-1 paths where a lowering resists typing.
  It emits an FPCC **constant-time certificate** the §6 checker validates at zero new trust base.
- **Binsec/Rel: the better-fit mature tool, run through the §5 trust-base test.**
  Binsec/Rel does exactly the binary-level job: **relational symbolic execution for constant-time and secret-erasure, directly on the binary against a leakage model**, and it scales to production crypto (BearSSL, OpenSSL, HACL\*, libsodium: finding real violations).
  It is the better-fit tool for this path because the FPCC statement is *binary-level against the Sail model* and Binsec/Rel is binary-level.
  So, exactly like **riscv-formal BMC** and **aiT**, it is adopted as the **unverified complement / bring-up gate**, bounded evidence and untrusted evidence-producing machinery, with the relational-Sail-logic certificate the unbounded close.
- **ct-verif: the IR-level sibling, not the binary-level answer.** ct-verif verifies CT by product programs over **LLVM IR** (SMT-discharged).
  It is real and usable, but IR-level: the platform verifies CT **on the binary** for every secret-touching artifact (no verified-compiler CT path), and there is no trusted IR to check at that point: the binary is the artifact.
  So ct-verif is the sibling to note, Binsec/Rel the complement to adopt: analogous to **EverParse** being noted-but-not-adopted for parsing (§5), though here the mismatch is level-of-abstraction, not trust base.
- **Scope is a labeling obligation, not a blanket tax.**
  CT is required only of compartments that receive **secret-labeled** material over an IDL confidentiality channel (§12); ordinary apps that touch no secrets carry no CT obligation.
  This matches the profile's *"tighter guarantees sharpen the holder's stopwatch"* scaling (§17) and hooks CT into the existing IFC/flow-label machinery (§8, §13) rather than inventing a new trigger: a secret reaching an un-CT-verified compartment is a *flow-label* error the Tier-1 flow theorems must catch.

**What the platform takes.**
Verify CT **on the artifact** against the one `Zkt`/`Zvkt` leakage model for every secret-touching binary (there is no verified-compiler CT route); split it functional ⋈ hyperproperty like RTL ⊑ Sail, with the **relational-Sail-logic constant-time certificate** the Coq-native close and **Binsec/Rel** the mature bounded complement (**ct-verif** the IR-level sibling).
The platform axiom decides the toolchain as ever: carry the Coq-native property to Binsec/Rel's demonstrated binary-level capability, spending engineering to keep CT on the single prover and make it *artifact*-borne.
**Honest residual (§17):** Binsec/Rel is path-bounded evidence (the certificate is the unbounded close); CT verification inherits the RTL ⊑ Sail residual (the leakage model is sound only once that arrow closes) and leans on the `Zkt`/`Zvkt` leakage-model statement as a shared crown-jewel spec; and correctness of *scope* rests on the flow labels (§8, §12, §13), so a mislabeled secret is a spec error no CT proof catches.
Like WCET it **degrades gracefully**, bounded Binsec/Rel evidence carries bring-up, the certificate closes it, so it gates *strong* CT assurance, not boot.

---

## WIT, CHERIoT import tables, and slim-image lineage: typed interfaces and the content-addressed capability image

The platform takes the **type and interface half** of WebAssembly's Component Model while declining Wasm as an execution substrate.
Its IDL is **WIT-derived, fork-and-frozen**: worlds become manifests, resources become capabilities, and the bytecode, linear-memory sandbox, relaxed memory model, and runtime pipeline are absent (§12, §13).
CHERI already supplies the hardware form of the useful Wasm sandbox idea, a bounded reference, at byte and sub-object granularity rather than once per module heap.

CHERIoT's export/import tables and sealed entry points supply the loading structure, while the content-addressed systems lineage (OSTree, Nix, Fuchsia archives, IPFS CAR, Git packfiles, and `fs-verity`) supplies the object model.
The resulting admitted artifact is a **content-addressed capability image**, not ELF: a fixed-layout manifest names immutable code and rodata, writable initializers, the CHERI-TAL derivation, and an explicit monotone capability-wiring table (§10, §13, §14).
It also serializes as one hash-indexed pack for distribution without giving the device an ELF interpreter, dynamic linker, relocation grammar, or runtime loader.
ELF remains off-device build interchange only.

Code density follows the same static rule.
The resident instruction stream uses the **fixed-rate dictionary encoding** at R-15-036a, and composition-time absolute call/global targets are measured under R-15-036l so repeated destinations can share dictionary entries without a JVT, CSR, runtime table read, or authority rule.
This is the adopted form of the indexed-target insight: resolve once at composition, then delete the runtime mechanism.

---

## RLBox and wasm2c: ahead-of-time WebAssembly with no JIT anywhere, and the obligation on a returned value that bounds do not discharge

**RLBox** (UCSD, Texas, Stanford and Mozilla; USENIX Security 2020) retrofits fine-grained isolation onto third-party C libraries inside Firefox, and it enters for two things, one of which closes an objection and one of which opens a gap.

**The objection it closes is that WebAssembly implies a just-in-time compiler.**
Firefox shipped RLBox with the Graphite font shaper in Firefox 74, and Mozilla's production configuration moved to **wasm2c**: the library is compiled to WebAssembly, the WebAssembly is compiled to C, and the C is compiled ahead of time to native, with no run-time code generation anywhere in the path.
That is precisely the configuration §5's pinned guest semantics needs, running in a browser at scale, and it is the answer whenever the pinned-Wasm choice is read as smuggling in a JIT.
The follow-on performance work (Segue, ASPLOS 2025) is instructive in the other direction, since what it recovers is bounds-masking cost by borrowing an x86-64 segment base, and it documents a ceiling of sixteen concurrent sandboxes for the memory-protection-key alternative: both are workarounds for the absence of hardware-enforced spatial bounds on every pointer, which CHERI supplies architecturally, so the isolation mechanism itself imports in no part, and Native Client's load-time validator over an instruction subset is declined outright as an alternative to capabilities that its own vendor withdrew.

**The gap it opens is real and hardware bounds do not touch it.**
RLBox's central finding is that *isolating the library was not sufficient*, because the application still consumes whatever the sandbox returns; so every value crossing out is wrapped in `tainted<T>`, a type that will not implicitly convert, forcing the developer to copy it into application memory and validate it before use, and turning every omission into a compile error rather than a latent bug.
CHERI says nothing about this.
A capability handed back across a compartment boundary is a perfectly valid capability with perfectly valid bounds, and it can still carry a length field that lies, an index out of range for the *caller's* array, an enumeration outside its domain, or a pointer legitimately inside the callee's bounds and semantically meaningless to the caller: confused-deputy and semantic-corruption bugs, which spatial integrity does not reach.
The obligation that follows is a **taint-or-validate duty on every value crossing a compartment boundary**, discharged at composition time by the interface language or on the install path by the checker (§11, §12, §13), and it belongs in [coverage-matrix.md](coverage-matrix.md) as a cell distinct from the CHERI bounds argument rather than folded into it.
Reading "CHERI covers it" onto this class would leave it uncovered, and the entry exists to say so.

---

## The V8 heap sandbox: a shipping browser giving up on the MMU for its own object graph

Chrome's JavaScript engine reached this design's diagnosis of the MMU under production pressure rather than as an architectural argument, which is why it is recorded: it is the same conclusion arriving from the opposite direction.
Having already put each site in its own process, V8 found the page the wrong granularity for the boundary that mattered next, the one *between the objects of a single heap*, where an attacker who has corrupted one object is already inside the process the MMU was drawing around it.
Its heap sandbox therefore stops asking hardware for that boundary at all and confines the engine's own object graph to one pre-reserved region, replacing raw pointers with offsets a corrupted heap cannot make point outside it.
§7 deletes the MMU on the argument that the page is the wrong shape for the boundaries this system draws; here is a browser vendor reaching that verdict about the boundaries *it* draws, while keeping the MMU for the ones it still fits.

**The mechanism imports in no part, for the reason the entry above already gives.**
An offset checked against a region is a bounded reference emulated in software, and CHERI supplies one in hardware on every pointer at byte granularity rather than once per heap, so the masking cost Segue borrows a segment base to recover and the reservation V8 sizes its region with are alike workarounds for what this substrate has architecturally.
The threat models separate the two more sharply than the cost does: the sandbox takes arbitrary corruption *inside* its region as its starting assumption and defends only that region's edge, so every object in a heap shares one boundary and none has a boundary of its own, which is exactly the interior a per-pointer bound leaves nowhere to exist.

**The reservation half does not import either, and there this platform is the one that pays.**
The region is sized by reserving virtual address space and committing it lazily, the lever `satp` fixed to Bare removes (§15), so the platform interpreter's guest arena is a composition-time size rather than a reservation (§14) and what an engine treats as headroom is here a declared ceiling carrying a stated exhaustion arm.
[userspace-porting.md](userspace-porting.md) states the consequence on the side that meets it, the browser's.

---

## WasmCert, Iris-Wasm, and SpecTec: the platform interpreter's theorems bought by curation, with every agreement instrument kept untrusted

The §14 platform interpreter (R-14-013a) is the one place the platform executes a guest language it did not define, and its assurance is bought the way the kernel's and the parsers' were: adopt the mechanized lineage whose theorems already exist, curate it into the one prover, and let nothing ecosystem-facing enter the trust base.

- **WasmCert-Coq and its certified interpreters: the executable core.**
  The Rocq mechanization of WebAssembly (Watt, Bodin, Gardner, Pichon-Pharabod, Rao; FM 2021 onward) carries type safety, a sound-and-complete type checker, instantiation soundness, and an extracted interpreter proved against the relational semantics, with the successor interpreter carrying soundness *and* progress through erasable certificates (POPL 2025).
  This is the artifact the R-14-013b curation names first: the semantics and the interpreter arrive with their theorems attached, in the platform's own prover, which is what lets the crown jewel be *curated rather than authored*.
- **Iris-Wasm: the confinement statement worth citing.**
  The robust-safety logical relation (PLDI 2023, on WasmCert-Coq) states exactly the property R-14-013a's second theorem claims: adversarial code influences other modules only through the functions it was explicitly given.
  Its MSWasm extension (OOPSLA 2024) mechanizes the handle vocabulary, CHERI-shaped capabilities inside the guest, and is retained as design vocabulary for lowering guest handles onto real capabilities, not as an admitted dialect.
- **SpecTec: the upstream that stops mechanization drift.**
  The W3C-adopted mechanized specification format authors the official Wasm standard from one formal source with a Rocq backend, so the pinned semantics tracks a mechanized upstream rather than transcribing prose, the failure mode the hand-transcribed NAS grammar (R-05-050) exists to manage.
- **WasmRef-Isabelle and the conformance suite: the oracle, untrusted.**
  A second verified interpreter, refined in a different prover and deployed industrially as a fuzzing oracle, plus the official conformance suite, are the differential instruments of R-14-013b's fidelity posture: producer-side evidence against the agreement gap, entering no trust base, the exact stance R-17-016b takes for wire formats.
- **CertrBPF, Cedar, and Microvium-on-CHERIoT: the shipped pattern this generalizes.**
  Every fielded verified evaluator for untrusted content pairs a deliberately small language with an install-time check and a verified evaluator, and the one shipped interpreter-in-a-compartment precedent on capability hardware ran unmodified inside a compartment.
  The platform interpreter is that pattern with the platform's own admission and manifest machinery as the checker half.

**What the platform takes.** One pure-interpreter engine as a §13 library compartment, its soundness and confinement theorems consumed from the WasmCert/Iris-Wasm lineage against the R-14-013b pinned semantics; SpecTec as tracked upstream; conformance and differential execution as untrusted producer-side evidence; the MSWasm handle model as vocabulary only.
**Honest residual (§17).** The fidelity of the pinned semantics to the Wasm the world compiles to is the R-17-016b agreement gap on a language, booked and never claimed closed; the theorems say nothing about what an embedding chooses to expose to its guest, which stays the transferred obligation's surviving edge; and no verified JS engine exists to extend the offer to the browser's other half, a declination R-14-013c records.

---

## Tamarin at the radio: the session-security half of the reference machines, bought by curation

The four radio reference state machines (R-12-043c, inventory rows 19–22) are the second place the platform curates a mechanized upstream rather than authoring one, and the reason is the same as the interpreter's: the theorems already exist, in a lineage that has spent a decade being checked against the deployed world, and an original reading of a prose standard would discard them. R-12-043e names the lineages; this entry records the artifacts and what each one demonstrated.

- **The 5G authentication lineage: the analyzed model that corrected the standard.**
  The first full Tamarin model of 5G-AKA (Basin, Dreier, Hirschi, Radomirović, Sasse, Stettler; CCS 2018) extracted precise security goals from TS 33.501 and fed underspecification findings back to 3GPP before the standard froze; the component-based successor (Cremers, Dehnel-Wild; NDSS 2019) modeled every party the specification defines and showed the protocol's security resting on unstated channel assumptions, with a race a provider can implement "correctly" and insecurely, and a session-confusion misbinding.
  That is the exact class a curated upstream keeps out of a transcribed reference model: the flaw lives in a defensible reading of the prose, and only a model that has been adversarially analyzed knows which readings are wrong.
- **The RRC layer: the handover analyses, and the thinnest lane named as such.**
  The Tamarin analysis of the 5G handover protocols (Peltonen, Sasse, Basin; WiSec 2021) models the RRC-layer procedures and derives for each the minimal assumption set under which its goals hold.
  RRC coverage in the literature is thinner than AKA coverage, which the row records rather than smooths over: a procedure no published analysis reaches is transcribed from the prose under the R-05-050 hand-transcription posture, the fallback the curation rule leaves for exactly this case.
- **The 802.11 model detailed enough to catch KRACK.**
  The Tamarin WPA2 model (Cremers, Kiesl, Medinger; USENIX Security 2020) carries the four-way handshake, the group-key handshake, WNM sleep mode, and the data-confidentiality protocol with their interactions, is the first model detailed enough to exhibit the key-reinstallation attacks, and gives the first security argument in any formalism that the patched protocol meets its claims.
  Key reinstallation on a handshake replay is R-12-043b's named class verbatim, and this artifact is why the MLME row's upstream is a model rather than a reading.
- **SAE and its adversarial complement.**
  WPA3's SAE handshake carries machine-checked symbolic analyses in ProVerif whose findings fed revisions of the 802.11 specification, while Dragonblood's timing and cache attacks on the same handshake sit outside the symbolic boundary by construction.
  The pair marks the division of labor the import makes explicit: the symbolic model checks the message-level protocol, and the side-channel class it cannot see lands on the §5 constant-time discipline, which is this platform's own obligation and nobody's import.
- **Bluetooth: the pairing-confusion lineage.**
  The Tamarin sweep of the Bluetooth key-agreement protocols across BR/EDR, BLE, and Mesh (ESORICS 2023) surfaced two practical pairing-confusion attacks, validated against off-the-shelf devices and registered as CVEs by the Bluetooth SIG, and the BLE Secure Connections pairing analysis with machine-checked patches (USENIX Security 2023) covers the machine row 22 transcribes.
  Pairing-method confusion is the second of R-12-043b's named classes, found by exactly the instrument the rows now pin.

**What the platform takes.** The analyzed model as each row's version-pinned tracked upstream (R-12-043e); the reference machine as its transcription into the one prover, reviewed formal-to-formal, clause against clause; the analyses' security statements as producer-side evidence composing with the R-12-043b refinement, so the machine the device provably runs is the machine the field analyzed; and the analyses' attack findings as the review gate's checklist of wrong readings.
**Honest residual (§17).** The R-12-043f remainder, none of it claimed closed: faithfulness of the analyzed models to the prose 3GPP, IEEE, and Bluetooth SIG standards, the R-17-016b-class agreement gap on a protocol, permanent because the upstream is prose and capping every implementer identically; the symbolic abstraction, whose composition with the §5 scheme-level reductions is assumed rather than proved, no computational-soundness theorem being claimed; the Tamarin and ProVerif provers standing outside the one-prover discipline, so the imported statements enter no trust base and no Ax class; and the standards' own motion beneath the pins, carried as ordinary curation drift the way SpecTec's upstream is.

---

## PRET, PATMOS/T-CREST, and FlexPRET: timing as an architectural property

The deterministic timing profile converges on the **precision-timed architecture** lineage from the real-time side.
PRET makes timing a first-class controllable property; PATMOS/T-CREST pairs time-predictable cores with the Argo TDM NoC; FlexPRET demonstrates the same discipline on RISC-V.
Their adopted contribution is methodological and structural: fixed-latency operations, static issue and prediction, explicit scratchpads, a timing-annotated machine model, and TDM interconnect make the §11 WCET calculation and temporal isolation architectural facts rather than measurements.
T-CREST's Argo NoC is particularly direct prior art for §15's static TDM fabric.

The lineage also motivates a still-non-normative candidate, fixed-slot fine-grained multithreading, but that mechanism is not part of the base and remains evaluated in [architectural-alternatives.md](architectural-alternatives.md).

---

## Lingua Franca, Ptolemy II, and PTIDES: the coordination half of the same program, and the theorem that stops at the code generator

The PRET import above takes one half of a single research program and the corpus has never named the other.
Edward Lee is an author of PRET, of **Ptolemy II**, of **PTIDES**, and of **Lingua Franca**, and the halves have converged repeatedly without once being proved together.
Ptolemy II supplies the frame: a model's semantics is not the framework's but a **director**'s, each director implementing a model of computation, and different levels of one hierarchy carrying different directors, so heterogeneity is expressed by composing semantics rather than by weakening one.
**Lingua Franca** is the live descendant, and it is a coordination language rather than a runtime: **reactors** with declared ports and reactions, communicating on connections fixed at composition time and spanning at most one level of hierarchy, over a **superdense** logical time whose tag is a pair of a time value and a microstep.
Its determinism has a mechanized proof, and the shape of that proof is the reason this entry is here rather than in the alternatives: Rossel, Lin, Lohstroh, Castrillon and Goens (VSTTE 2023) give the reactor model its first formal operational semantics and prove **progress and determinism** in **Lean**.

**Four things import, and the first gives the schedule a denotation.**
The **tag as a pair** is the right semantic account of what a frame boundary means: a §7 frame is a logical instant and the order of components dispatched inside it is the microstep axis, which turns "the schedule is the semantics" from a slogan into a statement with a model behind it.
**Connections declared rather than created**, at most one hierarchy level wide, is the same discipline as static channels reached independently and for the same reason, that a topology known at build time is a topology schedulable at build time.
LF's **`after` rule**, which legalizes a feedback loop only when some edge carries a logical delay, is the precedent for making a cycle-breaking delay a declaration the checker enforces rather than a property an implementation happens to have, and a TDM slot boundary is exactly that delay here.
And **`reactor-uc`**, LF's no-heap statically allocated runtime for microcontrollers, has been ported to **Patmos**: the coordination half already runs on the PRET half this design imports, which is the most concrete evidence available that the two compose.
One citation travels with them for the sceptical reader, since the standing objection to everything in this family is that determinism costs throughput: on the Savina benchmarks LF outruns Akka by 1.86x and CAF by 1.42x, its authors' point being that determinacy costs neither expressivity nor speed.

**What is declined is the guarantee, and the ground is the object the theorem is about.**
The Lean proof concerns the **model of computation**; the artifact a user runs is emitted by `lfc`, an unverified Java code generator, linked against an unverified C, C++, Rust or embedded runtime, compiled by an unverified target compiler, onto a machine with no timing contract, and nothing connects the theorem to the binary.
That is the characteristic failure of this whole category, and it is not weak theorems but theorems about the wrong object: of everything surveyed beside it, only **Vélus** (above) carries a determinism result all the way to machine code, and it does so by riding CompCert, which is precisely why Vélus and not LF holds the §12 control-plane slot.
Three mechanisms are declined with it.
The **event-queue runtime**, which advances time by popping a priority queue of tagged events, cannot be what a WCET-by-composition argument sums over, where a dispatch table can (§11).
**Physical actions and physical connections** are LF's own admitted nondeterminism and are load-bearing in real programs, because they are how external input arrives; here input enters at a scheduled sampling point, so the arrival instant is quantized by the schedule rather than by a clock read.
And **deadlines**, which LF detects at run time where §11 proves they cannot be missed: different products that should not share a word.
Federated coordination is declined as solving a removed problem, since both LF modes assume a network, the centralized one an RTI's grant-and-advance handshake and the decentralized one PTIDES-style clock synchronization under a bounded-delay assumption, where an on-chip TDM interconnect has the bound by construction from its slot table.

**The time-triggered relatives are the same idea at the interconnect.**
Giotto and TDL fix a task's logical execution time so that outputs appear at instants independent of how long the computation took; Kopetz's time-triggered architecture and TTEthernet, and IEEE 802.1Qbv's scheduled traffic, do the same for the wire.
They are recorded here rather than imported because §15's TDM fabric already *is* that answer inside one die, and the standards exist to obtain it across a bus this design does not have.

---

## occam and the transputer, and XMOS xCORE: static channels in silicon, and the boundary every rendezvous machine stops at

The share-nothing multikernel over a static channel graph had a commercial machine forty years ago, and both its achievement and its limit are precisely documented.
**occam** on the **INMOS transputer** put Hoare's CSP into an ISA: processes, `PAR`, `ALT`, and channels as first-class objects with hardware links between chips, with the scheduler itself in microcode.
Its compile-time discipline is the part worth reading closely, because it is the ancestor of three later answers to one question.
occam enforced a **single-name rule** (one name per datum per scope), **abbreviation validity**, **procedure parameter distinctness checked at every call site** (which is what made per-procedure checking modular and sound), **parallel disjointness** (a variable written in one `PAR` branch is untouchable by the others, channels single-reader single-writer), and no pointers and no dynamic allocation at all.
It was also **incomplete by design**, and the honest version of the lineage claim depends on saying so: for abbreviations at variable subscripts the alias checker inserted `overlapcheck` nodes and the test happened at run time under a per-program error mode.
So occam solved the decidable fragment and fell back to a dynamic check for the rest; Rust makes the aliasing structure part of the type; a capability machine makes the bound part of the pointer and checks it in hardware; and this design takes a fourth road, forbidding at composition time the construct that makes the question undecidable.
The transputer's other legacy is the FPU: the T800's floating-point unit was specified in Z, its algorithms proved in occam and refined to microcode, work that took the Queen's Award in 1990, was reported as *cheaper* than the informal route, and found both an ambiguity in IEEE 754 and a bug in a competitor's part.
That is the strongest historical precedent for this project's whole premise and it deserves citing wherever the proof-cost argument is made (§17).
A second citation belongs beside it, from the compiler half of the same lineage rather than the datapath half: Börger and Durdanović's correctness proof for compiling occam to transputer code (*The Computer Journal* 39(1), 1996), which refines the compilation itself through a chain of abstract state machines.
So the precedent covers both of the halves this project has to pay for, the datapath and the translation onto it, rather than one lucky arithmetic unit.

**The scheduler is where the transputer is usually misremembered, and the distinction is the entry's point.**
Two priority levels in microcode gave a *bounded* dispatch latency, typically 19 cycles and a published maximum of 53 at high priority, with low priority round-robin at roughly a millisecond and a worst case of `2n - 2` slices for `n` processes.
Bounded, fast, and published is more than a modern operating system offers, and it is still not what §7 needs: what runs next is decided by a queue whose contents depend on when communications completed, so the gap is bounded while the order and the instants are not predetermined.
The transputer bounded the gap; the table determines the sequence.

**Workspace-pointer switching is the one mechanism here that tempts, and it does not import.**
Three data registers behaved as an evaluation stack over a workspace pointer into a memory stack, so a context switch was a pointer change rather than a register save, and the evaluation stack was not preserved across the instructions at which a switch could happen, `Jump` among them.
That speaks straight to the total restore R-07-015 states and to the merged-file argument that makes the restore quantify over one file of 32 registers (R-15-007i), the same argument that deleted `f0`–`f31`.
What blocks the import is not the idea but its substrate and its accounting: a different ISA pays the substrate-cost disqualifier in full ([architectural-alternatives.md](architectural-alternatives.md)), and the state does not vanish under a workspace pointer, it moves into memory, where the masked clear and the eager zeroize have to reach it instead of the register file (§7, §15).
The useful half is already banked under another name, since run-to-completion over syntactic poll sites (R-07-037a) with asynchronous delivery deleted (R-08-033) makes the switch points syntactic here too, so live state at a switch is a static quantity for the same reason it was one there.

**XMOS xCORE is the living commercial foil, founded by the transputer's own architect.**
Its instruction timing is deterministic by construction in the way §15 is: no forwarding, no speculation, no branch prediction, unified SRAM in place of caches, almost every instruction single-cycle, and a hardware limit of one issue per core per five cycles that guarantees the previous instruction has retired, with the published contract stated as an issue rate against the number of awake cores.
It ships a real WCET tool, the XMOS Timing Analyzer, which enumerates paths through object code and times them.
And its limit is the finding that generalizes to everything in this category: **XTA reports "unknown" at any instruction that can pause**, a channel input, a timer read, a port wait, because the pause is a function of a peer's progress, and it assumes zero pause on top of instruction execution, on the strength of hand-written pragmas that have demonstrably been wrong in the vendor's own libraries.
Every system here bounds **computation** and none bounds **communication**, because in all of them communication is a rendezvous.
A composition-time TDM slot table is a different answer rather than a better estimate: the transfer instant is not analyzed, it is scheduled, and a peer's progress becomes a scheduling constraint discharged at build time instead of a term in a WCET expression (§11, §15).

**Boot over links is the entry's anti-precedent, and it is the concrete shape of what §9 gives up.**
With `BootFromROM` deasserted a part waits for bytes on any link, reads the first byte as a length, copies that many bytes into low memory and jumps into them; the reserved lengths 0 and 1 are POKE and PEEK, so an unbooted part's memory can be written and read word by word by whatever is on the other end of a wire.
The loader's shape is almost the one §9 keeps, a fixed-layout length-bounded header ahead of a flat image (R-09-005), and everything that makes that shape safe is what is missing: nothing authenticates the bytes, nothing measures them before they execute, and no monotonic floor stops an old payload from being replayed.
The debug half is the sharper anti-precedent, since PEEK and POKE are a standing read/write authority into a neighbour reached from a wire, where the Debug Module here is lifecycle-fused off in production and an ML-DSA challenge-response anywhere else, with a crypto-erase before a fielded part becomes debuggable at all (R-15-078, R-15-079).
Tens of milliseconds on the cold path (R-09-005a) is what refusing that convenience costs here, and this is where the thing being refused can be read at full size rather than imagined.

**One cost of the same lineage lands on this design's own bill, and the receipt is forty years old.**
The transputer had no MMU and no virtual memory, and the price showed up exactly where it would be expected: it inhibited porting mainstream Unix, which is why the machine got a native operating system rather than a ported one.
§7's single address space takes the same position deliberately, and [userspace-porting.md](userspace-porting.md) is where the bill is itemized: every entry a source-level re-target rather than a binary that runs, with ambient POSIX authority re-expressed as explicit capabilities one obstacle at a time.
The lineage offers no discount, only the confirmation that the cost is real and that it lands in porting labour rather than in mechanism.

**Three cautionary trajectories close the entry, and the first two are the same trajectory twice.**
occam's second act, occam-pi, re-added mobile channels, run-time process creation and mobile processes, which is exactly the dynamism the first act existed to exclude; XMOS is currently moving `par`, `chan` and timed ports out of a language its compiler understands and into a C library it does not, with XC maintained but no longer preferred.
Static structure decays into dynamic API wherever nothing forces it to stay static, which is the argument for keeping the composition rules in [requirements-register.md](requirements-register.md) and [absence-contract.md](absence-contract.md), where a proof obligation and an auditor's search hold them, rather than in a runtime that can be extended by anyone in a hurry.

**The third is the same decay one layer down, in silicon, and it is the strongest of the three because the experiment finished.**
The T9000 answered the demand for performance with a 16 KB cache under random replacement, a five-stage pipeline, a *grouper* collecting instructions into packages of up to eight bytes for superscalar issue, and virtual-channel routing that freed a program from knowing the physical link layout.
The cache under random replacement, the grouper's dynamic packing, and the virtual-channel multiplexing are the hidden-state, data-dependent class the §15 admission test refuses, and two of them put another party into this program's timing: a replacement draw the program does not make, and a peer's traffic sharing its link.
The pipeline is the one ingredient that would pass, being the in-order kind this design also has.
What they bought is the point: the part never reached its goal of ten times the T800, stood at roughly 36 MIPS at 50 MHz, and was cancelled.
That is the EPIC entry's *nothing gets deleted* argument ([architectural-alternatives.md](architectural-alternatives.md)) confirmed by a machine that ran the experiment rather than argued it: what was added to claw performance back was exactly the surface a deterministic machine then has to argue about, and it did not deliver the performance either.

---

## The Cell Broadband Engine: the software-managed local store shipped at consumer volume, and the instruction-set heterogeneity that buried it

Cell (IBM, Sony and Toshiba; in the PlayStation 3 from 2006) is the closest shipped relative of the **explicit software-managed local store**, where XMOS above is the closest one of the cacheless machine at large, and it is two-sided in the way Cerebras and the transputer are: one structure it got right at a volume nothing else in this document reaches, and five it got wrong in exactly the places the profile deletes.
It also completes the entry above from the other end. The T9000 added a cache to claw performance back and was cancelled with the performance undelivered; Cell deleted the cache outright, delivered its throughput, and lost its market anyway, to a cause the next paragraphs name, so the pair is the controlled experiment that separates *the cacheless choice was the fatal one* from what actually was.
It pairs one PowerPC **PPE** with eight **SPEs**, and the SPE is the part that matters: a 256 KB **local store** that is not a cache, addressed directly by ordinary loads and stores, with main memory reachable only through explicit DMA issued to the SPE's own **memory flow controller**.
That is the discipline R-15-165 states and the cacheless entry above argues, software-managed local memory in place of a hierarchy, running in tens of millions of consumer machines two decades ago.

**What it is evidence for, and where the evidence stops.**
The local store is the largest-volume existence proof available that a general programmable core can carry **no cache anywhere in its own memory path** and still be programmed for shipped work rather than for a benchmark, which is the objection the cacheless entry above answers on its own terms and can now answer with a machine.
It is deliberately **not** cited as evidence for the flat latency constant, because the SPE has no such constant: the local store is **single-ported**, so instruction fetch, DMA, and the load/store unit contend for one port, DMA winning it, fetch taking idle cycles behind a 32-instruction buffer and an explicit instruction that forces an inline fetch where starvation threatens.
Cell therefore removed the cache's abstract-interpretation problem and put an arbitration problem in its place, and §15 differs at exactly that point rather than inheriting it: per-island banks and macros, static per-island memory-controller arbitration, and a fabric whose slot does not move because another agent is busy (R-15-211, R-15-212), so the flat constant is bought by the partitioning and not by the absence of the cache.
The corroboration is thus **one half of the §11 claim and not both**: deleting the cache deletes the hierarchy term an aiT-class analyzer must bound, and it does not on its own deliver a constant, which is why the two are separate decisions here and why this entry supports only the first.
**Honest residual:** whether a hard-real-time WCET literature grew on the SPEs *because* the local store removed that term is recorded as **unestablished** rather than asserted; the searchable record carries Cell scheduling and performance-analysis work and no timing-analysis line of the kind PATMOS and XMOS carry, so what corroborates here is the shipped artifact and its structure, not a body of published bounds.

**The one candidate atom, and its price.**
The SPU has no dynamic branch predictor and takes **compiler-inserted branch hints** instead: an instruction naming a branch and its target ahead of the branch, prefetching up to 32 instructions from the target so that a correctly hinted taken branch costs nothing against an 18-cycle miss.
That answers the tax R-15-023 accepts with *more* information rather than less and at zero learned state, so it is not refused on the ground dynamic prediction is refused (R-15-012), and it is worth pricing rather than dismissing.
It is priced in [architectural-alternatives.md](architectural-alternatives.md), where it completes the family the static-callee-set fetch redirect and the branch-target latch open, and it is declined there on three grounds of which only the last is about hints as such: the SPU's default is not-taken for *every* branch, so the atom's largest customer is the loop back-edge R-15-019 already predicts correctly; a statically biased forward conditional is expressed by inverting the branch and swapping the blocks under R-10-034's layout, at no encoding at all; and under the dictionary encoding a hint costs a **dictionary entry per branch form carrying it** rather than a spare bit (R-15-036a, R-15-014a (i)), which is the scarce quantity the recovery gate's sixth clause protects.

**Where it is the foil, and the first of the five is the one this document has no other source for.**

- **Cell is the counter-example R-15-111 exists to prevent.** The PPE is PowerPC and the SPU is an unrelated SIMD instruction set with its own compiler, its own toolchain, and its own binaries, so a Cell program is two programs. Here the C-, V-, and M-classes are all RV64IMV+CHERI under one parameterized Sail model, one kernel binary, and one scalar front-end microarchitecture (R-15-111, R-15-112), and the classes differ in **datapath alone**, which is the entry below on Ara and Gemmini read from the other side. Cell's reputation for being hard to program is very largely that difference rather than the local store, and holding the two apart is the whole value of the case: heterogeneity in datapath is cheap, and heterogeneity in instruction set is what buried it. One ISA across classes is therefore a **usability** argument as well as a proof-surface one, and it is the one decision in the profile where those two point the same way with a shipped machine behind them.
- **The MFC carries its own MMU and TLB**, translating the effective addresses a DMA descriptor names. That is hidden translation state plus an autonomous memory-touching engine, failing admission tests (3) and (5) together, and it is the Sv39 walker's own failure (R-15-002, R-15-038) reached at the device edge instead of at the core. Capability-checked DMA gets the identical function with the authority in the descriptor rather than in a translation, which is the entry above.
- **The PPE is 2-way SMT**, which R-15-012 already names as failing test (3) by construction, in the same package and beside the same local stores.
- **The EIB is four token-arbitrated rings**, so a transfer's time is a function of its neighbours' traffic: the cross-domain contention channel the TDM NoC deletes, and the same ground on which the Cerebras entry above takes the static routing and declines the backpressure.
- **SPE isolation mode is an enclave**, a locked local store running an authenticated image, and it is the structure [architectural-alternatives.md](architectural-alternatives.md) declines once across the academic and industrial families alike: §4 obviates the mechanism by making every compartment attested and isolated already, and R-15-013 declines the hedge where the primary is verified CHERI.

What transfers is therefore **evidence, not code**: the shipped, consumer-volume demonstration that software-managed local memory replaces a cache in a programmable core, and, from the five foils together, an unusually clean lesson about which heterogeneity a machine can afford to carry. Cell put one convergent structure and five deleted mechanisms in a single package, which is why it belongs here rather than in the alternatives: the one earns the entry and the five sharpen it.

---

## Larrabee: the software renderer on general cores, the one industrial run of the V-class thesis, and the sampler its own team kept

Larrabee (Intel, disclosed at SIGGRAPH 2008, cancelled as a consumer graphics part in 2010, and shipped as the Knights Corner and Knights Landing accelerators from 2012) is the only industrial machine built on the thesis the entry below states: rasterization, interpolation, blending, and the pipeline's own scheduling written as **software on programmable cores with a wide vector unit**, with the fixed-function stages deleted rather than accelerated.
Its cores are in-order and dual-issue with a 16-wide 512-bit vector unit each, four hardware threads apiece, and coherent L2 slices on a bidirectional ring.
R-15-115's prohibition list reads almost as a description of what Larrabee deleted: no rasterizer, no ROPs, no command processor, and no hardware warp scheduler, the vector unit sitting as a coprocessor beside an ordinary scalar core rather than as a SIMT machine with a scheduler of its own.
The entry below states that arrangement as a design; this one is the machine that ran it, and it is two-sided in the Cell entry's way, with one structure adopted, four mechanisms refused, and a fifth that prices a prohibition rather than confirming it.

**What transfers is the renderer's structure, and R-12-083 is where it lands.**
The register books the RVV software rasterizer as genuinely net-new engineering, the 2D and text substrate having safe-Rust start-froms where 3D has none, and Larrabee is the nearest thing to one that exists: a **sort-middle binned pipeline**, a geometry front end sorting primitives into per-tile bins, tiles sized so a tile's render target stays in core-local memory for the whole of its shading, and coverage evaluated hierarchically as vector masks rather than as per-pixel tests.
The structure is portable and none of the code is, so it enters as engineering and never as assurance, exactly as the openwifi and smoltcp start-froms do (§12).
The tile-sizing decision is the part worth reading against §15 rather than copying: what Larrabee reached by sizing a tile to a coherent L2 is here a bank no other agent shares (R-15-165), and binning is what makes the render working set a **composition-time quantity** rather than a hit rate hoped for at run time, which is the conversion the memory plan performs everywhere else.

**Four mechanisms are the foil, and the first two arrive together for a reason.**
- **Four-way SMT per core.** R-15-012 refuses the class by construction, failing admission test (3), which is where the Cell PPE lands too. Here it is load-bearing rather than incidental: the threads exist to cover the memory latency the cache hierarchy could not hide, so a machine keeping that hierarchy needs them, and refusing the hierarchy is what makes refusing them affordable. The pair is one decision seen twice.
- **Coherent L2 slices on a bidirectional ring.** Cross-core cache coherence is the shared mutable state the share-nothing multikernel forbids (§7), and the ring is the neighbour-traffic contention channel the Cell entry above already names, answered the same way by a TDM schedule whose slot does not move because another core is busy (§11, §15).
- **A dynamic software scheduler.** Larrabee distributed the pipeline's stages across cores by work stealing, which is what let the renderer scale and what makes its timing a function of every other core's progress. That is the transputer distinction of the entry above restated at the granularity of a frame: bounded is not predetermined, and the table determines the sequence rather than bounding the gap (§11).
- **The texture sampler, retained.** It is the one fixed-function block the design kept, and the paragraph below is why.

**The sampler is the one place a source prices a prohibition of this profile instead of corroborating it.**
Larrabee's designers deleted every other fixed-function stage and kept texture filtering, on measurement: filtering written for their own vector unit came out roughly an order of magnitude short of the dedicated one, a gap wide enough that keeping a block was cheaper than widening the machine.
R-15-115 forbids texture units regardless, and [architectural-alternatives.md](architectural-alternatives.md) books the honest cost as the lower peak throughput of a no-JIT software renderer, which [performance-estimates.md](performance-estimates.md) already carries as a range against a real GPU.
What this entry adds is **attribution inside that range rather than a new cost**: its largest single term is the one stage the thesis's own advocates could not write in software at parity.
Two things bound that, and neither retracts it.
The work §12 gives the V-class is compositing, 2D and text, codecs, and the ISP, none of them filtering-bound the way a 2008 game rasterizer was, so the clause's largest customer is smaller here than it was there; and a texture unit is an autonomous memory-touching engine with address generation of its own, so admitting one is the admission-test-5 question the codec block and the bitstream engine already answer negatively ([architectural-alternatives.md](architectural-alternatives.md)) and not a free trade of area for throughput.

**Why it stopped, and why that cause is not on this machine's bill.**
The consumer part was cancelled on the compatibility contract rather than on the architecture: it had to be conformant and competitive at DirectX and OpenGL against parts whose fixed-function stages it was emulating in software, and the same cores then shipped for years as Knights Corner and Knights Landing once no graphics API stood in the way.
This platform never signs that contract, exposing no GL, Vulkan, Metal, wgpu, software ICD, command-buffer personality, or runtime shader compiler at all, with direct dispatch of certified kernels over capability-scoped buffers as the interface instead (§12, §13), and paying in the other currency, a native backend per toolkit, at the line the alternatives entry books it on.
The transferable lesson is therefore not that software rendering works, which Larrabee only half demonstrated, but that **the API burden and the rendering thesis are separable**, so the machine that declines the first is not the machine that was cancelled.

**One ISA, reached for and not quite held.**
x86 was chosen for R-15-111's own reason, one instruction set and one toolchain across the machine, which makes this the positive form of the argument the Cell entry supplies negatively.
It did not fully arrive: LRBni was a new vector extension present on no host part, so a Larrabee binary was not a host binary, only the scalar half of the toolchain carried across, and the extension reached general-purpose parts as AVX-512 years afterwards.
Vector length is a **class parameter** here rather than a second instruction set, the C-, V-, and M-classes differing in VLEN and datapath under one parameterized Sail model and one kernel binary (R-15-111, R-15-112) because the vector ISA is length-agnostic by construction, so what Larrabee reached for is what the profile actually holds, and that clause now has a shipped machine on each side of it.

---

## Ara, Gemmini, and tensor-core lineage: V-class graphics and M-class inference under one ISA

The graphics and AI topology takes the useful datapaths of a GPU and an NPU while declining their separate computers.
The **V-class** is an Ara-lineage, wide-RVV core class dedicated by static composition to software rasterization, compositing, codecs, the ISP, and other long-vector work (§12, §15).
It is neither a fixed-function GPU nor uniform RVV spread over every core: scalar and control classes are not over-provisioned, tasks do not migrate dynamically between classes, and the render and compositor compartments are the whole graphics driver.
The only display device is firmware-free scanout DMA over a capability-bounded window.
The entry above is the one industrial machine that ran this thesis, and it is read there for what its renderer demonstrates, for the four mechanisms it kept that the profile deletes, and for the one it kept on a measurement.

**SEAM-V** (a decoupled RVV-backend design, rejected as such in [architectural-alternatives.md](architectural-alternatives.md)) sharpens one admissible performance lesson without transferring that backend.
Its **static execute-packet packing and same-packet hazard suppression** are the vector form of wider in-order issue plus verified static scheduling: independent vector operations are packed ahead of time, issue remains core-driven and deterministic, and no backend-local instruction stream, prefetcher, or dynamic cross-packet scoreboard is introduced.
The Ara-shaped tightly coupled baseline is therefore the adopted datapath form, with packet packing a compiler and issue-width concern rather than a second processor.

The **M-class** is the tensor-core pattern integrated into the ordinary core: a Gemmini-lineage systolic int8/bf16 array beside a VLEN=1024 vector unit and software-managed scratchpad, issued by the same RV64+CHERI front end under the same Sail model (§15).
The array is retained only for dense GEMM that clears the order-of-magnitude throughput threshold over RVV; small or irregular matrix work stays vector code.
Arbitrary low-bit quantized formats are unpacked in software on the vector unit, and MX-style block scales are applied there as ordinary per-element operations, so no architectural tile file or block-scale register joins the context, zeroization, or proof surface.

Model and shader flexibility is kept off-device: shaders and models compile and certify ahead of time into capability-confined kernels.
There is no Vulkan/GL/Metal/wgpu runtime personality, SPIR-V pipeline compiler, shader JIT, command-buffer validator, accelerator firmware, or separately booted control core.
The adopted API is direct dispatch of certified kernels over capability-scoped buffers (§12, §13).

The same threshold admits one post-quantum primitive: the frozen **Keccak-f[1600]** vector instruction, which serves ML-KEM, ML-DSA, SHAKE, and SLH-DSA while collapsing a substantial constant-time software burden (§15).
The NTT, modular reduction, and samplers remain ordinary constant-time RVV software; a general PQC coprocessor would enlarge the ISA and RTL proof for throughput the vector unit already provides.

---

## Display lineage: static demura, fixed refresh sets, and a firmware-free timing controller

The display requirement is deliberately technology-neutral but not mechanism-neutral.
The timing controller is fixed-function and firmware-free; scaling, colour management, and temporal processing run on the V-class (§15).
An **AMLCD** is the current instantiation because it is procurable and carries no per-pixel aging history.
**Micro-LED** is the preferred future emitter when a five-to-seventeen-inch panel exists at the required density *in procurable volume*, with its factory demura delivered as a static table and with a gradable backplane, driver, and link; prototype and automotive-grade panels in that band exist already, and the outstanding condition is mass-transfer yield rather than the panel itself.
That swap changes no requirement and re-verifies nothing: static calibration is an attested device constant applied by the host colour pipeline.

The rule excludes OLED implementations whose panel-side compensator integrates each pixel's drive and thermal history into persistent mutable state.
That state is both a foreign computer and a low-resolution record of prior display content outside the capability system.
Being a rule about mechanism, it excludes the same loop in a micro-LED panel, and admits an OLED panel whose correction is in-pixel and per-frame over a factory table.
Radiation qualification remains a backplane, driver, and packaging obligation rather than a reason to prefer one emitter by name.

Refresh timing follows the same static discipline.
The compositor chooses from an **enumerated fixed-rate set** at content boundaries (rates such as 48 or 120 Hz, chosen to share common multiples with content cadences), while §11 reserves the fastest mode.
Adaptive-Sync and per-frame variable refresh are absent because completion time would reveal the slowest composed surface to other compartments and to an external sink.
The fixed set keeps most cadence benefits while presentation timing remains a composition-time constant.

---

## Mon CHÉRI and foundational TAL: Write-before-Read moved from a tag plane into the type system

Mon CHÉRI identified a genuine residual in capability safety: spatial bounds and temporal revocation do not by themselves prevent use of an uninitialized scalar value.
The property survives, but neither proposed hardware vehicle does.
The platform adopts **Write-before-Read as the CHERI-TAL definite-initialization attribute** over the static slot plan (§5, §7, §13), descending from Morrisett-style per-field initialization flags and the Coq/Iris uninitialized-capabilities lineage.
A store advances a two-point attribute, a load requires the initialized state, and a control-flow merge takes the meet; partial fields and stack frames are handled at type granularity and a violation is refused at admission rather than trapped in service.

This avoids both Mon CHÉRI's operation-bound capability encoding and a transparent address-indexed initialization plane.
Eager zeroization still closes disclosure, native capability tags close the uninitialized-pointer case, and §13 admits no uncertified code population for which a new plane would provide an independent guarantee.
Device-filled buffers therefore establish initialization as a verified HAL postcondition, and delegated-buffer state rides the IDL and manifest seam.
The honest residual is deliberate: no hardware mechanism catches a checker or metatheorem error.

The same TAL line carries the **typed callee set**.
At every indirect transfer, a code type names the finite labels that site may target; sealing and static composition make the set exhaustive, and cross-compartment sentry edges are joined through manifest import/export tables.
This closes target membership without banning Rust closures, function pointers, or trait objects and without adding `Zicfilp` or a landing-pad ISA.

---

## Static physical realization: radio isolation, SRAM circuits, and tier-graded process technology

Several physical evaluations converge on one rule: use static, composition-time structure and decline adaptive or separately trusted machinery.
The radio remains on the single die but takes the top on-die isolation rung: its own clock/power island and a separate SRAM macro or tier, with a floorplan keep-out narrowing thermal coupling (§15).
A second radio die is not used because it would add a package, SerDes protocol, clock-domain boundary, second attestation problem, and second object for supply-chain inspection while sharing the same mask-set risk.

Clocking follows a **globally asynchronous, locally synchronous (GALS)** discipline.
Islands may use independent clocks and operating points and communicate across ordinary synchronized boundaries over the TDM fabric, while each island remains internally synchronous and fixed-latency.
This takes system-level timing-domain separation without making datapath completion a function of operands; the CDC synchronizer is the bounded boundary obligation, never a self-timed execution unit.

SRAM leakage is reduced by **static** cell and circuit choices: a high-Vt storage core with low-Vt periphery, gate-length biasing, state-retentive sleep-transistor gating, a low-leakage process flavour, and fixed reverse body bias where the substrate permits it.
Near-threshold retention is allowed for idle banks; sub-threshold active memory, workload-tracking body bias, activity-driven gating, and adaptive assist are not.
**The bitcell itself stays 6T, and the transistor-count question is settled on the security axis rather than left open on it.**
The decoupled-read multi-port cells (8T, 9T, 10T, Schmitt-trigger, dual- and two-port) remain a per-tier and per-structure density and stability choice, with static write assist where required, and they are taken where multiple ports are functionally required, at the vector register files and matrix scratchpads rather than at main memory.
They are taken on **no** side-channel ground: the read-decoupled cell's single-ended read buffer makes the fetched word's Hamming weight a first-order term in read current, where the 6T differential read is comparatively balanced, and the leakage-power-analysis literature measures the canonical Schmitt-trigger 10T as very nearly separable between storing a zero and a one, building its symmetric 12T countermeasure on top of that cell rather than out of it.
The genuinely security-oriented cells are a different family ordered differently by count (a 7T for the dynamic write channel, a 12T for the static one), and they are declined as platform mechanisms alongside the cheaper periphery randomization unit, at the same test §17 sets for every analog countermeasure, the one the crypto core's masking passes and they do not: their deliverable is a measured attenuation factor rather than a statement over the leakage model the theorems are stated in.
The residual this leaves is leakage power analysis against arrays held in long retention, which is a different exposure window from the crypto core's operating analog channel.

Process technology is graded by tier.
The bottom logic tier uses an IRIS-resolvable **silicon-on-insulator** process with frontside power: the buried oxide gives a repeatable backside reveal stop, latch-up isolation, a smaller upset volume, and static body bias.
**The member of that family is named rather than left to the family, because three constraints already stated admit exactly one: a planar, thin-buried-oxide, fully-depleted SOI wafer with a backplane beneath the channel.**
The static body bias §15 admits on this tier is a *back-gate* lever, which needs a thin buried oxide with a backplane under it, so partially-depleted and thick-oxide SOI cannot carry it; gate-all-around is declined on this tier for infra-red resolution and a fin on insulator would forfeit the back gate in any case, so the tier is planar; and the buried oxide serving that back gate is the same layer that stops the backside reveal, which is why one substrate serves inspectability, the static low-power lever, and radiation hardness together instead of trading them against each other.
Two consequences are owned here rather than discovered later.
The choice **places the logic tier's node well behind the tiers above it, and the substrate is not what holds it there**: fully-depleted SOI runs in production from 28 nm down to 18 nm ([GlobalFoundries 22FDX](https://gf.com/gf-press-release/globalfoundries-launches-industrys-first-22nm-fd-soi-technology-platform/), Samsung 28FDS, and [STMicroelectronics' 18 nm line](https://newsroom.st.com/media-center/press-item.html/p4733.html), whose first microcontroller shipped in 2025), 12 nm is roadmapped, and a European pilot line is chartered for 10 nm and 7 nm, so what actually bounds this tier is §17's infra-red-resolvable-node constraint rather than the availability of the wafer.
Sitting several nodes back is affordable precisely because logic density is not this tier's constraint, and it is the same deliberate decade-back posture the compute throughput already takes.
And the wafer is an **engineered substrate bought from a supplier rather than grown by the fab**, layer transfer being the volume route to it, which puts a materials-provenance source outside the fab underneath the one tier that computes; §17 books that residual beside the donor-wafer one it matches.
The discipline has a production-scale existence proof: bunnie Huang's Baochip-1x shipped as the DEF CON 34 badge (2026) on a 22 nm frontside-power process packaged specifically for IRIS backside inspection, end users verifying transistor patterns against the published RTL with a camera modification on the order of $180.
Optically checkable silicon at production volume is practicable, not aspirational.
Gate-all-around and later CFET density are confined to upper passive SRAM tiers, where they cannot execute and sit outside the backside optical path; backside power delivery is refused because opaque metal would block that path.
Sequential monolithic 3D is admitted for those passive tiers, with Nano-CT, acoustic microscopy, thermography, dark-field inspection, virtual metrology, and BIST as defect evidence, never as a replacement for IRIS on the acting logic tier.
Silicon-carbide-on-insulator, 2D-material logic, tunnel FETs, carbon-nanotube FETs, bonded logic stacking, and chiplets remain outside the base.

---

## Fixed-rate compressed-domain representations: capacity as composition-time arithmetic

The capacity response to all-SRAM memory is not transparent compression but **fixed-rate representation**.
Quantized weights and KV caches, fixed-rate block-compressed textures, succinct indexes, fixed-pattern structured sparsity, bounded sketches, compiler outlining and identical-code folding, and the resident fixed-rate dictionary instruction encoding all have a ratio known at composition time (§10, §12, §15, §16).
They preserve affine addressing, fixed access latency, native CHERI tags, the fixed granule write path, and an admission budget that is arithmetic rather than statistical.

Variable-rate main-memory compression, compressed caches, deduplication, and background compaction are absent.
Their footprint and latency depend on content, their pool is history-dependent state, their ratio is a cross-domain oracle, and deduplication creates sharing from content coincidence rather than delegated authority.
Build-time single-owner artifact compression remains admissible where it saves storage, but it does not count toward resident SRAM capacity unless the encoded form is executed directly, as the instruction dictionary is.

---

## Zero-authority emergency service: local entry without a legacy downgrade target

Emergency calling is a separate **zero-authority mode**, not a fallback negotiated from ordinary authenticated service (§12, §15, §17).
Entry is an unspoofable local act; the compartment holds no user keys or data and exposes only regulation-mandated identity and location, so an unauthenticated or null-cipher bearer cannot be used to bid ordinary service down.
The supported bearer is 5G-standalone or 6G emergency registration.
No legacy emergency-only receiver, turbo/convolutional decoder, or old-generation RF path exists, and the honest cost is no emergency call where only legacy or 5G-non-standalone coverage is available.
Regulation runs the same direction rather than against it: no jurisdiction requires a handset legacy fallback, the EU's NG eCall makes packet-switched IMS eCall mandatory for new vehicle types from 2026 with circuit-switched no longer accepted for type approval, and Australian rules have carriers block handsets that cannot complete a VoLTE emergency call.
The mandate pressure is toward packet-switched emergency.
The cost is sharper than SA coverage alone states: an SA-only emergency call needs IMS emergency over VoNR, which lags SA radio deployment (roughly 85 operators in 47 countries have launched SA while commercial VoNR remains a short list), so the honest bound is VoNR availability, not SA coverage.

---

## Translation validation and source correspondence: artifact identity through the final image

Translation validation is already part of the adopted proof path, but in a bounded role.
CompCert handles verified C compilation; validation against the CHERI-RISC-V Sail semantics covers assembly, linking, stripping, capability wiring, dictionary encoding, and image construction outside that theorem (§5, §13).
Every package carries a source-correspondence theorem binding the final installed bytes to the exact content-addressed source closure, so a build-farm corruption or trusting-trust injection not permitted by that source is rejected regardless of producer pedigree.
Islaris-style direct binary proof covers paths with no verified compiler in the loop.
The instrument is normative rather than open: R-05-023a fixes the record's production as decompilation into logic over the pinned Sail term, checked as refinement in the one §13 logic, so the validation records and the §7 fast-path proof are theorems of the same logic.

The whole-compiler seL4-style alternative remains a fallback if CHERI-CompCert proves intractable, not the primary route.
Per-build proof search and SMT reconstruction are less reusable than one compiler theorem and do not themselves establish robust preservation against every adversarial linked context; CHERI and Cerise recover much of the practical boundary at runtime, but not the compiler-level hyperproperty.

---
