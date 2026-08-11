# Inspirations & Prior Art (non-normative)

> Companion to [verification-maximal-os.md](verification-maximal-os.md).
> This document records the **existing systems and research artifacts this design descends from**: what each contributed, where it lands in the spec, and how the design transforms it.
> It is **not** part of the normative spec; cross-references of the form §N point to sections of that specification.
> Architectural alternatives that were *evaluated and rejected* live in [architectural-alternatives.md](architectural-alternatives.md), not here; this page is the roads **taken**.

The lineage splits along the platform's own axiom: *engineering is free; trust is the scarce resource* (§4, §17).
Two kinds of ancestor recur, and most entries below are one or the other:

- **Designs imported and re-grounded.** seL4, Barrelfish, CheriOS, bcachefs, the FSCQ family, and the CVA6-CHERI core contribute an *architecture* the spec adopts wholesale and then re-homes onto its single prover (Coq) or its capability substrate, keeping the design, shedding the incidental trust base (Isabelle, Dafny/Z3, a managed runtime, a non-Coq conformance prover).
  This is the *"methodology is portable, maturity is not"* move the spec body makes repeatedly (§5).
- **Patterns imported and mechanisms superseded.** systemd, Fedora Atomic, NixOS, OSTree, secureblue, GrapheneOS, ChromeOS, and Fuchsia/FIDL contribute a *product pattern* (declarative supervision, image immutability, functional/reproducible build, hardening, transactional rollback, a hardware root of trust, capability IPC) whose *intent* the spec keeps while replacing the *mechanism* with a stronger one: probabilistic mitigation becomes proof (§17), ambient-authority orchestration becomes capabilities (§8), a convenient content-addressed image becomes a boot-attested Merkle image (§9, §10), an input-addressed, reproducible-by-convention build becomes a content-addressed, proof-carrying one (§10, §13), and an unverified capability-IPC wire becomes a copy-once-verified one (§5, §12).

## seL4: the kernel design, adopted nearly whole and re-proved in Coq as a bespoke minimal capability core

seL4 is the foundational import.
Its capability design is the base (§5, §7): a capability-based microkernel with zero post-boot kernel allocation, synchronous **endpoints + notifications**, first-class revocation (§8), and the **seL4-NI** non-interference lineage (§8); with several mechanisms deliberately dropped as this platform's own simplifications: the **VSpace/paging objects** (single-address-space, no MMU, §7), the **MCS scheduler** (a table-driven cyclic executive replaces it, §7, §11, moving the scheduling configuration back toward the non-MCS static-partition one seL4's NI proof actually covers), and, per the object-model deletion, **untyped memory and retype**, **the capability space**, and **the derivation tree**, each redundant with the CHERI tag plane or the static composition (§7, §8), so what is taken from seL4 is the endpoint model and the non-interference statement rather than the object model entire.
The proof, too, is deliberately not inherited: seL4 ships on Isabelle/HOL (l4v), and putting Isabelle *and* Coq in a TCB whose §6 story is a single self-verifying checker would be a first-order regression; so the spec re-proves seL4's design **end-to-end in Coq** via CompCert/SECOMP, as a **bespoke minimal capability core**: seL4's object model shorn of the VSpace and MCS objects this platform deletes, joined to the CHERI single-address-space realization (CheriOS/CHERIoT, below) and the multikernel composition (Barrelfish, below), a synthesis rather than a transcription (the full disposition: why CertiKOS is demoted to a proof-*method* lineage, why the 2024 multikernel and CHERI-seL4 work is promoted in-scope, and why the stripped design makes the greenfield proof feasible, is in [architectural-alternatives.md](architectural-alternatives.md)).
That seL4's own 2024 direction is the **share-nothing multikernel** (RFC-0170) and **CHERI-seL4** means the import is of a *live* design, not a frozen one.

**CertiKOS supplies the proof method that carries it**, and is demoted from kernel to *method* lineage precisely so that it can: what transfers is the **abstraction-layer discipline**, the **deep-specification** style, **CompCertX**-style verified compilation, and the generic lower-layer proofs any kernel needs, giving the *how* while seL4 gives the *what*.
What does **not** transfer is CertiKOS's distinctive asset, the **Certified Concurrent Abstraction Layers** verifying a fine-grained concurrent shared-memory kernel: the share-nothing multikernel forbids the shared mutable kernel state CCAL exists to verify, so for a per-core *sequential* kernel plain **VST** (sequential separation logic over CompCert) is the more parsimonious closing logic.
Honest residual: a Coq re-proof is fresh (as unbattle-tested as any), so what transfers from seL4's maturity is the **retained object-model design**, ABI, C implementation, and long-scrutinized specification, not the proof (§17).
The freshness that bites is not the authored refinement proofs, which fail *loudly* when wrong, but the silent kind, a mis-transcribed specification that verifies perfectly; the answer is to transcribe **mechanically rather than by hand**, since seL4's executable model is Haskell and **hs-to-coq** carries that scrutinized prototype into Gallina without a paraphrase pass, leaving only the abstract spec and the refinement authored fresh.
Convergent sibling: Google Research's **KataOS** (its **CantripOS** userland) and its **Sparrow** reference platform independently assemble almost this exact substrate (seL4, a near-entirely-Rust userland, statically-composed CAmkES components, and an OpenTitan RoT on RISC-V), reached not as an ancestor this design descends from but as a *convergent* one that stops an assurance tier short on every axis it shares.
It rides seL4's Isabelle proof as-is (the two-prover base §5 declines) rather than re-proving in Coq, its Rust is memory-safe *by borrow-checker alone*: the "app safety leans on the toolchain" posture the artifact-level memory-safety certificate and CHERI supersede (§5, §13); its CAmkES graph is "statically-defined and analyzable" short of machine-checked static composition (§7); though its **capDL** capability-distribution spec and its Rust rewrite of seL4's **capdl-loader** rootserver are the sharper precedent §7 lowers onto (the CAmkES → capDL → verified-system-initialisation toolchain, ridden here on Isabelle and in service of *dynamic* loading rather than re-homed to Coq and frozen static); and its third-party apps are **dynamically loaded and confined by seL4 capabilities alone**, reaching services only through its **SDKRuntime**, a runtime-validated interposer standing in for authority a compartment here simply never holds: exactly the containment-without-proof road §7's static composition and §11 proof-checked admission decline.
KataOS is thus at once the seL4 line's **shipping evidence** that the whole substrate is buildable (the Fuchsia "shipping evidence, not the proof" move (below) one layer down) and its **foil**, the same triad secured by containment-plus-mitigation that this design takes to proof; and a *frozen* foil at that: the public AmbiML release is archived, relocated to Google's **OpenSecura** (2026), so where the seL4 and COSMIC imports track live designs, this one is shipping evidence gone static.

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

The lineage is mature and mechanized: Lustre and SCADE in certified avionics, and Vélus itself a published Coq artifact compiling a real Lustre subset (nodes, reset, control blocks, and **state machines**, POPL'23) through CompCert with an end-to-end correctness proof, the state-machine result landing exactly on the protocol-sequencer use case.
What the import does **not** do is abandon a substrate or fuse anything: RV64, CHERI, FPCC, and the Rust data planes all stay, and it changes only the *source language of one tier of one non-TCB layer*.
Scope is honest: the adoption covers the logic that *is* reactive dataflow, and Rust is retained wherever a control path is genuinely imperative request/response rather than a state machine; a mis-drawn boundary is a spec error, not a silent failure.
Honest residual (§17): Vélus enters the build path as a new front end, Coq-verified so it adds *no fresh axiom* and rides the already-priority-zero CHERI-CompCert backend (§18), but its Lustre-semantics faithfulness joins the crown-jewel specs and the **control/data boundary is a new crown-jewel interface**; offset against this, the control tier's structural WCET (§11), structural memory-safety certificate (§13), and by-construction determinism (§8, §15) are a net reduction in proof surface.

---

## The verified-crypto stack: Fiat-Crypto, HACL\*/libcrux, formosa-crypto, and the Coq-native reduction layer

A verified cryptosystem needs three properties, and the field supplies mature artifacts for each: **functional correctness** (the code computes ML-KEM), **constant-time** (it leaks nothing through timing), and **reduction-level security** (the *scheme* is IND-CCA or EUF-CMA under a named hardness assumption).
The third is the one most stacks leave unstated, and proving the implementation while assuming the cryptography inverts this design's own priority, so §5 composes all three, importing a different artifact at each layer and re-homing each toward the one prover.

- **Fiat-Crypto** supplies correct-by-construction field arithmetic from a Coq specification, and is the *native* member of the set: it is a Coq-native domain-specific generator in exactly the sense Narcissus and Vélus are (above), so it enters at zero new trust base and its output is compiled as ordinary verified C through CHERI-CompCert.
- **HACL\* and libcrux** supply the functionally-verified primitives themselves, and are the standing **interim**: they discharge via **F\*/Z3**, a trust base distinct from Coq, and §5 minimizes that widening deliberately rather than accepting it (the same reasoning that picks Narcissus over EverParse for parsers, on trust-base uniformity alone).
- **SSProve and FCF** supply the missing third layer, Coq-native game-based reduction frameworks in which IND-CCA and EUF-CMA are proved by reduction to a hardness assumption.
  Choosing them is the identical decision made for Narcissus: the reduction rides the one Coq kernel (§6) at **zero new trust base**, which is why they are the destination rather than the complement.
- **EasyCrypt and formosa-crypto** supply the *finished* ML-KEM and ML-DSA reductions, and so are the fastest path to a real proof — but EasyCrypt discharges via **Why3/SMT**, so by this design's own logic it is a widening of the same character as the F\*/Z3 one: **adopted as pragmatic interim assurance, with SSProve/FCF the destination.**

The composition is the contribution: three layers joined at each primitive's functional specification, which is itself promoted to the crown-jewel spec list (§5).
Constant-time is *not* taken from any of these by preservation; it is verified **on the binary** against the §15 leakage model for every secret-touching artifact, the field-arithmetic kernels included, so a single CHERI-CompCert carries the whole toolchain and no artifact is admitted on the strength of which compiler produced it.
The toolchain choice is the seL4 move once more, *methodology is portable, maturity is not*: carry the Coq-native property to the mature artifacts, spending engineering to shrink the trusted set, and — as the rejected CryptOpt superoptimizer shows in the [crypto-verification-depth disposition](architectural-alternatives.md) — decline even a mature, verified-checker-admitted artifact where its only remaining yield would be *speed* on a path already correct and already leak-free.

Honest residual (§17): a reduction *isolates and names* the hardness assumptions (MLWE/MSIS, ECDLP/CDH) but cannot prove them, which is the irreducible cryptographic axiom; the implementation-to-reduction join is a new seam at the functional spec; EasyCrypt-borne reductions carry an SMT base until restated Coq-native; and scheme-level IND-CCA and EUF-CMA still sit below protocol-level security (TLS, AKA), a further layer again.
What the stack buys is the move from *"correct, constant-time code for a scheme we assume is secure"* to *"the scheme is secure under a named, minimal assumption, implemented by constant-time code verified on the artifact"*, with the residual pushed down to conjectures no proof system can discharge.

---

## Proof-carrying code and typed assembly: the Necula → Morrisett arc, and the checker it lets the device actually run

The admission discipline descends from one of the field's cleanest arcs: **Necula's proof-carrying code** (a proof travels with the artifact and the consumer re-checks it locally), narrowed by **Morrisett's TALx86** into a *type discipline* (the certificate is a typing derivation and checking it is decidable type-checking), then given foundations by **Appel's foundational PCC** and **Crary's foundational TAL** (the type system's soundness proved down to the machine semantics rather than assumed).
On the memory-safety-type side the mechanized descendants are **RustBelt** (Iris) and **WasmCert-Coq**, and on the capability side **StkTokens** (Skorstengaard, Devriese, Birkedal, POPL 2019) supplies the linear and affine discipline in the same capability-machine-logic lineage as Cerise.
So the whole *type-soundness* half of the platform's CHERI-TAL (§5, §6, §13) is inherited rather than gambled on.

**What CHERI changes about the inheritance is the size of the type system.**
TALx86 had to encode array-bounds and initialization proofs into its types because x86 had no hardware notion of a bound; on a purecap machine the bound, the tag, and monotonicity are *architectural*, so the imported types shrink to exactly the residual CHERI does not enforce at runtime: **temporal** safety (linear and affine capability types over a revocation-coloured heap, the StkTokens discipline in the CHERIoT lineage above) and **typed control flow**, where a well-typed jump target simply *is* control-flow integrity.
That residual is what safe Rust's ownership discipline already establishes at source (§5), which makes the TAL the vehicle that carries source types down to the binary as a checkable derivation — turning *"the compiler preserves and certifies rather than re-discovers"* from a promise into a concrete artifact format.

**Two further type-level imports ride the same checker**, each replacing a mechanism the design would otherwise have built: **CT-Wasm** (Watt et al.) shows constant-time decidable as a **taint-type discipline** for structured code, so CT becomes a type-check rather than a proof term wherever the code is structured (§5); and definite initialization arrives as the founding move-(II) attribute of the TAL lineage itself, which is why the Write-before-Read property is taken as a type attribute over §7's static slot plan instead of as the tag plane the hardware proposal wanted.
The **typed callee set** (§5, §13) is the same move once more, refining the code type already in the vocabulary rather than adding a grade beside it.

The payoff is structural, and it is what makes the on-device story honest: a TAL type-checker is decidable, syntactic, obviously terminating, and genuinely of order 10³ lines, so the checker that runs at every install and sits in the boot TCB can be *that*, while the full CIC proof kernel (tens of kLoC, MetaCoq-lineage) retreats to release time over the fixed base image, where the deep refinement and hyperproperty proofs actually live (§6, §9).
Admission then gates on the **derivation, not the producer**: any producer of a well-typed CHERI-TAL binary is admissible by definition, and the reference certifying compiler becomes a reference rather than a gate — the point at which *"verification is a property of the artifact, not its pedigree"* (§5) stops being aspirational.
The full stratification argument is the [CHERI-TAL admission disposition](architectural-alternatives.md).

Honest residual (§17): the net-new work is the **CHERI-RISC-V instantiation** — the temporal-safety type discipline over capabilities, and the compiler emitting derivations — and the **soundness metatheorem** (*well-typed CHERI-TAL implies the safety properties hold over the Sail model*) must be authored once in Coq against the §15 model, joining the crown-jewel specs, since a mis-stated typing rule admits an unsafe binary that type-checks perfectly.
It is nonetheless a smaller and more scrutable axiom than a hand-built proof checker would have been, and the Cerise universal contract (§13) stays beneath it as defense-in-depth against exactly that failure.

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
Set its two headline properties aside (the wafer-scale integration this platform does not pursue, and the all-SRAM main memory it independently adopts, §15), and the rest converges, from the AI-accelerator pole, on three further commitments this design also makes: cores that share **no memory and run no cache-coherence protocol**, communicating by explicit messages (the share-nothing multikernel and its coherence-free islands, §7, §15); **flat, uniform-latency on-die SRAM** as the whole of memory (the no-DRAM, no-cache subsystem, §15); and a **statically-configured interconnect** whose routes are fixed ahead of time rather than arbitrated dynamically (the TDM NoC, §15).
It is the largest-scale existence proof that a share-nothing, coherence-free, message-passing manycore is buildable, the role Barrelfish (above) plays for the model itself and SemperOS (above) for its distributed capabilities.

It is a **convergent foil**, not an ancestor this design imports, and the divergence is the sharp part: precisely the mechanisms that make Cerebras fast are the data-dependent, reactive, hidden-state class this platform deletes by construction.
Its **dataflow execution** fires work on operand arrival, so timing tracks the data, against the static cyclic executive and the fixed-latency WCET tables (§7, §11); its celebrated **sparsity harvesting** skips zero operands, a data-dependent timing, power, and interconnect-traffic channel of exactly the kind the constant-time mandate forbids (the `Zkt`/`Zvkt` leakage model, §15, the same class as variable-latency division and analog compute-in-memory); its mesh runs on **hardware backpressure**, a busy receiver stalling its upstream sender, which is the cross-domain contention timing channel the **TDM arbitration deletes** by construction (a partition's slot does not move because a neighbor is busy, §15); and because its cores are dataflow-driven they idle between events, a data-dependent activity profile, where this platform draws power on the static schedule alone (§15).
The interconnect comparison is thus two-sided in one artifact, take the static routing and decline the backpressure, and the compute comparison likewise, keep the flat SRAM and decline the sparsity that would leak through it.
What transfers is therefore **evidence, not code**: the demonstration at extreme scale that the share-nothing, no-coherence, all-SRAM substrate works, and the clean illustration of *why* its performance tricks are the ones a verification-maximal design must leave on the table, since each buys throughput with a channel.

---

## CheriOS: the single-address-space CHERI microkernel, the existence proof for the deleted MMU

CheriOS (Lawrence Esswood's Cambridge microkernel, CTSRD-CHERI, a clean-slate design outlined by Robert Watson) is the working demonstration that **CHERI capabilities alone can carry a microkernel's entire spatial isolation in a single address space**: compartments share one address space and are separated by capability bounds, not page tables, and it runs a real workload there: multicore, a filesystem, an LWIP network stack, an NGINX webserver.
It is the app-class precedent the [MMU-deletion disposition](architectural-alternatives.md) rests on (with CHERIoT the fully MMU-less microcontroller-scale sibling): the evidence that *"CHERI is the sole in-core spatial mechanism"* (§15) is buildable.
What the platform imports is the **thesis** (a single-address-space purecap system works and CHERI subsumes the MMU's isolation role), re-grounded three ways.

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
  So CheriOS proves CHERI-as-sole-*isolation*; statelessness is what lets this design drop the MMU as a *mechanism*, with CHERIoT the fully MMU-less proof at the small end; and, past the MMU, **CHERIoT is equally the existence proof for the platform's single privilege mode** (Machine-mode only, privilege carried by a CHERI permission on the PCC rather than an S/U ring; the [single-privilege-mode disposition](architectural-alternatives.md)), the privilege-architecture analog of the single-address-space thesis this entry imports, with first silicon and an Oxford/Google completed formal-verification behind it.

Convergent where it counts: CheriOS is **unverified purecap C** whose memory model pairs **CHERI-revocation temporal safety** (freed memory is revoked in a shared address space) with a novel temporally-safe **stack** and **Reservations**: private memory a component allocates *without trusting the allocator* (an integrity/confidentiality primitive, not a placement mechanism); its microcontroller sibling CHERIoT adds heap **claims** (a hold that keeps a shared allocation alive against the holder's quota) and the deterministic load filter: the same *temporal-safety-in-a-shared-address-space* discipline this platform reaches through the composition-time memory plan (§7, §8) ⋈ budgeted CHERI revocation (§8) ⋈ the `#![forbid(unsafe_code)]` source rule and the binary-level temporal-safety certificate (§5, §13).
CheriOS has the mechanism; this has the mechanism **and** the proof: the bcachefs/FSCQ relationship one layer down, in the kernel.
It is the roads-taken counterpart to the rejected-alternative MMU analysis: the disposition argues CHERI *should* be the sole in-core spatial mechanism; CheriOS is the standing evidence it *can*.

---

## CHERIoT: privilege as a capability, the switcher and sentries, and the object model that needs no CNodes

If CheriOS is the app-class evidence for the deleted MMU, **CHERIoT** (Microsoft and lowRISC, contributed to the RISC-V standardization effort) is the import that reaches furthest into the running system: it is the source of the platform's privilege architecture, its domain-crossing mechanism, its loading structure, and, after the object-model deletion, its kernel object model.
It is also the most *fabricated* of the CHERI ancestors, with first silicon taped out in early 2026 and formal verification underway on two fronts (Oxford against the Sail model, Google on the switcher's isolation properties), which is why the platform is willing to rest so much on it.

- **Privilege as a permission, not a ring.**
  CHERIoT is Machine-mode only by design (*"hierarchical privilege modes are unnecessary, so CHERIoT CPUs support only Machine Mode"*), carrying privilege as *"a permission that allows access to certain control and status registers … when a capability with that permission is installed as the program counter capability."*
  This is the whole of §15's single privilege mode: a compartment cannot execute a privileged CSR access for the same reason it cannot forge a pointer, the authorizing capability being *absent*, an unforgeable condition rather than a mode bit an exploit might flip (§7, §8, §15; the [single-privilege-mode disposition](architectural-alternatives.md)).
- **The switcher and sentries.**
  Its trusted **switcher** (~300 instructions, seL4-scale) mediates cross-compartment and cross-thread transitions holding one reserved register and is itself CHERI-constrained; its **sentries** are sealed entry points making domain entry an unforgeable jump rather than a mode transition.
  Both are imported directly (§7, §8, §15), and the in-order non-speculative core is exactly the target the permission-and-sentry model was designed for, the source noting it *"would be difficult on very large out-of-order cores"*, which this platform is not.
- **Compartment export and import tables in place of a container format.**
  CHERIoT replaces container-style loading with export and import tables and sealed entry points sealed by a loader, and the platform adopts that **structure** for its content-addressed capability image (§13) while re-grounding it on RV64 128-bit capabilities and a verified Narcissus reader, **rejecting** the compressed encoding and the unverified loader: the same adopt-the-structure, reject-the-encoding move the ISA profile makes for the rest of CHERIoT.
- **PMP dropped, on CHERIoT's own argument.**
  It drops PMP outright (*"the RISC-V PMP provides a subset of the protections of a CHERI system and so it, too, can be removed"*), which is the precedent §15 follows, with the CHERIoT-Ibex conformance result and Codasip's shipping app-class core as the assurance that makes dropping the coarse hedge defensible rather than reckless (the [drop-PMP disposition](architectural-alternatives.md)).
- **An object model with no CNodes, which is what let seL4's runtime layer go.**
  Capabilities live in registers and tagged memory, objects are named by **sealed capabilities**, and revocation is by **colour and epoch under a load filter** rather than by a derivation tree.
  That answer is what makes untyped memory, retype, the capability space, and the CDT deletable once the object graph is fixed at composition (§7, §8), and §5 had already conceded the direction, describing what is proved as *"more precisely a CHERIoT-class static separation kernel that borrows seL4's object vocabulary"*; the deletion finishes that sentence by dropping the vocabulary too.
  Its heap **claims** (a hold keeping a shared allocation alive against the holder's quota) and its deterministic load filter are the same temporal-safety-in-a-shared-address-space discipline noted under CheriOS above.

Two further corroborations arrive from the same source without being imports: **CHERIoT-Ibex is cacheless**, running from tightly-coupled SRAM, which is standing evidence that a cacheless core is a conformant RISC-V profile choice rather than a fork (§15); and **capability-holding DMA is demonstrated at CHERIoT scale**, which is the microcontroller-scale existence proof beneath the capability-checked DMA fabric that replaces the IOMMU (§15).
What is declined is its **autonomous sweep engines** (the TBRE and STKZ background walkers), which are exactly the autonomous memory-touching engines admission test 5 excludes (§8), so revocation here is budgeted and scheduled rather than engine-driven.

Honest residual (§17): CHERIoT is **single-core and microcontroller-scale** (2–7-stage pipelines, tens of KiB to MiB) and its own multicore is future work, while this platform is an application-class multikernel on multicore, so every one of the imports above is a genuine extrapolation of scale, the privilege-architecture sibling of the single-address-space bet.
It is bounded rather than blind: privilege-as-capability is *more* fine-grained and *more* uniform than the ring it replaces, which is CHERIoT's whole thesis, and the model it ships is the one being extrapolated, not a paper design.

---

## Capability-checked DMA: the Cambridge/SRI proposal and the CHERI-at-SoC-Level integration discipline

Deleting the IOMMU (§15) needs something to take its place at the device edge, and the replacement is not invented here: it is proposed and prototyped in the CHERI programme's own SoC-facing work.
**"Defending Direct Memory Access with CHERI Capabilities"** (Markettos, Baldwin, Bukin, Neumann, Moore, Watson; Cambridge and SRI, HASP 2020) proposes exactly a **capability-configured DMA controller** that bounds-checks accesses from malicious peripherals — pluggable and SoC-embedded alike — and contrasts it directly with the IOMMU's nested-page-table translation, which is the argument §15 makes when it declines translation and keeps only protection.
The **CHERI Alliance's "CHERI at SoC Level"** guide (2025) then supplies the integration discipline the mechanism actually requires: passing **capabilities, tags, and revocation** between CHERI-enabled IP blocks of varying CHERI-awareness, and clearing tags on writes from non-capability IP.
Capability-holding DMA is demonstrated at **CHERIoT** scale with first silicon in 2026 (above), so the small end is built even though the application-class bandwidths — NIC, scanout, radio I/Q — are net-new (§18).

What makes the deletion sound is a precondition this design supplies and a general-purpose machine cannot: the device model is already curated register-slave, transducer, and on-die RTL (§4, §12), so there is **no foreign PCIe bus-master ecosystem issuing raw physical addresses** for an IOMMU to catch in the first place.

One result from the same group is *declined* and worth recording for why.
**CapChecker** (*"Adaptive CHERI Compartmentalization for Heterogeneous Accelerators"*; Cheng, Markettos et al., ISCA 2025) interposes a capability-checking unit at the memory interface of a **CHERI-unaware** accelerator, so unmodified third-party or opaque IP gains fine-grained protection cheaply.
That is precisely the road §4's no-foreign-computers mandate forecloses — the unaware, self-mastering, opaque accelerator is the category it excludes by name — and the checking function is in any case what the capability-checked fabric already performs at the point of issue, so the shim would be the hedge *verify rather than hedge* declines.
What survives is CapChecker as a **feasibility datapoint**: boundary capability-checking on real heterogeneous accelerators at low single-digit overhead, corroborating that the capability- and tag-carrying fabric is cheap, rather than as a reason to admit the accelerator it was built to rescue (the [drop-IOMMU disposition](architectural-alternatives.md)).

---

## Register allocation, region inference, and static memory planning: the heap deleted as a runtime mechanism, the way the MMU was

The CHERI OS line keeps a **runtime heap allocator** and makes it *temporally safe*: CheriOS and CHERIoT revoke freed memory in a shared address space (above), CHERIoT adding heap claims and a deterministic load filter so a dynamic heap can be reused safely across mutually-distrusting compartments.
This platform keeps that temporal-safety machinery (§8 imports exactly the load filter and revocation epoch) but moves on a *different* axis: it deletes the **allocator itself**, the runtime component that decides *where* an object lands, and replaces it with a whole-program **static memory plan** the compiler computes ahead of time.
The move is therefore orthogonal to CHERI's temporal-safety story and composes with it (placement ⋈ temporal-safety, §8), not a supersession of it: what the platform still owes the freed-then-reused slot is the same revocation the CHERI line already supplies.
Five independent lines converge on that static-planning move, none of them an OS and none of them CHERI, so the import is method, not code, exactly the *"methodology is portable, maturity is not"* pattern this document opens with (§5).

- **Register allocation via graph coloring** (Chaitin et al., 1981, and the field since) is the origin move: a whole-procedure static analysis builds an **interference graph** (nodes are values, an edge joins two whose live ranges overlap) and colors it with the finite register set, deciding every placement **once, ahead of time**, so nothing at runtime searches for a free slot.
  The platform's static memory plan (§8) is this exact algorithm re-targeted from a small register file to SRAM: objects are the nodes, CHERI-bounded slots are the colors, and the certifying compiler's linear/affine ownership tracking (§5, §13) supplies the live ranges register allocation gets from SSA.
- **Region-based memory management** (Tofte and Talpin, 1997; carried into systems form by Cyclone's region types, Grossman/Morrisett) supplies the half graph coloring alone does not: *where do live ranges come from, and how is freeing proved sound*.
  Regions are managed by a type-and-effect discipline, stack-discipline nested (a *laminar* lifetime structure, the tractable corner of the offline problem below), with **dangling-pointer-freedom a machine-checked theorem** and no garbage collector; **Typed Memory Management in a Calculus of Capabilities** (Walker, Crary, and Morrisett, 1999) sharpens it to non-lexical region lifetimes governed by **static capabilities**: compile-time tokens, checked and then *erased*, that authorize access and deallocation with no runtime representation at all.
  That is exactly where the platform's own step lands: it keeps the region discipline but gives the static capability a **runtime** realization as a CHERI capability, so one word now spans the compile-time token WCM checks and the hardware token that bounds the slot at runtime: the coincidence the design is built on, and a re-homing WCM does not itself make (its capabilities are erased, not enforced in silicon).
- **Static memory planning in ML compilers** (XLA's ahead-of-time buffer assignment; Apache TVM's Unified Static Memory Planning; TensorFlow Lite Micro's fully precomputed, allocator-free arena) is the deployed-at-scale existence proof: production compilers already do **liveness-driven buffer assignment**, sharing one buffer among tensors whose live ranges provably never overlap, over gigabyte-scale graphs, and TFLite Micro pushes the same technique down to a **heap-free microcontroller runtime** with no allocator at all.
  What transfers is the evidence that the technique scales in both directions the platform needs it to: desktop-scale graphs and microcontroller-scale absence of any allocator at all.
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

**The load-bearing import: the quiescent point.**
Oberon's collector is an ordinary unsynchronized mark-and-sweep, and it is cheap and precise for a structural reason rather than an algorithmic one: it runs as a background task the central loop schedules only when **no command is executing**, so no procedure activation exists, the stack holds nothing to trace, and the root set is exactly the module-level pointer variables.
Wirth did not make the collector safe against a mutator; he made concurrency with the mutator **impossible**, and paid for it in the one currency he had, latency between commands.
§8's budgeted revocation sweep is deferred bulk work of the same shape over a graph of the same kind, and it is specified to run as an incremental, preemptible task in its own §11-admitted background slot class, which means its quanta interleave with compartments holding live capabilities in registers and frames, and its correctness must be argued against them.
The Oberon rule says to bind those quanta instead to the **slot boundaries of the domain being swept**, where `fence.t` has already run and the live capability root set is the statically enumerated one §11's stack-depth and callee-graph analysis computes anyway: the sweep then never overlaps its own mutator, and its root set becomes a composition-time artifact rather than a runtime scan.
What that buys is not a mechanism but a **deleted proof obligation**, which is the currency §17 counts; it is proposed here and not yet taken, since §8 currently specifies the preemptible form.

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

Where GrapheneOS is genuinely **additive** is one axis §3's evil-maid-plus-remote model did not originally name: **operational security for a device physically in an adversary's hands.**
The dominant forensic-extraction target is a powered-on phone unlocked at least once, its per-profile volume keys decrypted and resident in the crypto core (*After First Unlock*, the Cellebrite/GrayKey case), which §3 did not distinguish from the powered-off evil-maid it already defends (measured boot + FDE).
That distinction is **adopted**, importing the first and load-bearing GrapheneOS answer: **auto-reboot to the Before-First-Unlock state after an idle interval**: a scheduled RoT-attested transition (§9) that evicts the per-profile volume keys from the crypto core and re-seals the application islands, so a device seized after unlock returns to keys-not-resident at rest (§3, §10, §15) while the standby radio island stays page-reachable (§15).
Its credential/unlock path also gives **biometric matching** the §12 compartment the spec had left unassigned, and unlock-attempt rate-limiting extends the RoT's existing boot-attempt counting (§9).
A second answer is imported alongside it: **USB data gated on the lock state**: a charging-only Before-First-Unlock device leaves its USB data lanes' capability-bounded DMA window (§15) unopened and defers new-peripheral authorization to post-unlock powerbox consent (§8), so juice-jacking and lock-screen wired extraction have no data path (§12); and because charging must outlive the lock, **USB-PD contract negotiation is specified as a fixed-function sequencer** (no firmware, the radio link-layer timing-block pattern, §12), closing the platform's former USB-PD gap in passing.
A third answer follows: a **duress credential that crypto-erases on entry**: presented instead of the ordinary one, it commands the RoT to destroy the sealing root so every user-data domain becomes unrecoverable in the time it takes to zeroize a key (*lose the key = erase memory*, §15), the coerced-unlock countermeasure booked as a defended case (§3, §9, §12).
The last operational-security answer is imported too, and as a **hardware invariant**: **per-connection MAC randomization** is tied to the platform's cryptographic RNG root: the die carries no persistent factory MAC and every link-layer address is a fresh draw from the RoT TRNG through the verified DRBG (§15, §16), so it is privacy by construction rather than a disable-able setting, GrapheneOS's per-connection randomization taken from a software default to a property of the entropy source.
The last GrapheneOS radio idea is **adopted and taken further**: where GrapheneOS disables 2G with a software toggle, here 2G, 3G, and 4G are **absent from the silicon**: the FEC units decode only the 5G/6G channel codes and the RF bank carries only 5G/6G bands (§15), so the target is **5G standalone and 6G** and downgrade to the broken-crypto legacy generations is physically impossible rather than merely refused (§3); atop that, the verified-from-scratch L2/L3 stack (§12) makes *no null cipher, mutual authentication required* a provable property rather than a setting; mitigation carried past theorem to matter, secureblue's move applied to the most-attacked surface.

GrapheneOS hardens the phone Android *is*; this design builds the phone that needs no hardening (a memory-safe, capability, verified substrate that refuses the AOSP/Linux base, the managed runtime, and the ambient-authority permissions GrapheneOS must retrofit) while **inheriting GrapheneOS's account of what an attacker holding the unlocked device can still do.**

---

## systemd: async init orchestration, minus the ambient authority

systemd contributed the *shape* of modern service management: **declarative units** with dependency-ordered, parallelized ("async") bring-up, and **supervision**: crash detection, restart policy, backoff.
§12's **service manager** keeps precisely this (a static supervision tree, declarative units, restarts with backoff) and §16 keeps the crash-only / health-gated posture.
But systemd's *mechanism* is the thing this platform is built to refuse: it runs with root **ambient authority**, parses text unit files at runtime, and accretes a large privileged surface (socket activation, D-Bus, cgroup control).
Here units are **compiled to typed, signed configuration objects per generation** (no trusted component parses text config at runtime, §10), admitted by proof (§13); the supervisor holds **no ambient authority** and re-grants capabilities on restart (§8, §12); and socket-activation's "hand the service its connection" idea is subsumed by the **capability ring data plane** (§12), where authority arrives only over the control plane and *physically cannot cross* the data plane. systemd is thus the orchestration *pattern* ancestor, with its ambient-authority substrate swapped out for capabilities.

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

## ChromeOS: the verified-boot root of trust, realized as on-die OpenTitan

ChromeOS is the mass-deployment proof that a consumer OS can stand on a **hardware root of trust with verified boot, a read-only rootfs, and A/B updates with automatic rollback**: its trust anchored in a discrete security chip (the Google Titan / H1 lineage) whose open-silicon descendant is **OpenTitan**.
§9 is that chain, sharpened: an **OpenTitan-class RoT** provides measured boot, key storage, TRNG, monotonic counters, and boot-attempt counting, with the chain RoT → verified M-mode firmware → per-core kernels → static image, every stage measured and every signature post-quantum (ML-DSA), plus A/B images with RoT boot-counting auto-revert and a monotonic anti-rollback floor (§9, §11).
§15 then goes past ChromeOS by **integrating the OpenTitan block on-die** as the platform's *only* management processor (removing the discrete-RoT interposer/probing surface and making attestation coverage total), the "no foreign computers" mandate (§4) applied to the root of trust itself.
ChromeOS supplies the verified-boot product template; OpenTitan supplies the open, inspectable silicon that lets the template become a *TCB* rather than a vendor black box.
The same move **retires the discrete or firmware TPM and declines OpenTitan's own TPM-2.0 command mode**: the RoT provides the TPM's *operations* (measured boot, sealing, attestation quotes, monotonic counters), verified and on-die (§9), but not as an unverified black box on an external bus (§15) nor through the TCG command *protocol* (a grammar-heavy register-slave surface, §5, §12) with its non-PQ attestation; software reaches those operations through the §12 sealing & attestation service that secure-vault apps build on.
(Google's **Sparrow**, the KataOS reference platform (seL4 entry above), is a second datapoint for OpenTitan-as-integrated-RoT-on-RISC-V, corroborating the silicon bet even as it keeps a separate ML-accelerator core rather than making the die the platform's *only* computer, §4/§15.)

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
The transfer boundary is sharper still on virtual memory: Mocha fields an application-class core **precisely to give enclave OSes an MMU** (its rationale for CVA6 over a real-time core), yet this profile **deletes the MMU** (single-address-space, `satp` Bare, §15), so the CVA6-CHERI datapath is imported while the MMU that motivates Mocha's core choice is curated away, its conformance evidence thereby covering a virtual-memory path the platform never runs.
Two live-design notes mirror seL4's "a live design, not a frozen one" (above): CHERI is being standardized as the **RISC-V 'Y' extension** the frozen §15 profile tracks, and COSMIC's **dual-core lockstep** is a hardware fault-*detection* complement to §7's per-core kernel duplication for bit-flip blast-radius: fault detection beside fault containment, logged for **G5** but not yet imported (it doubles core area, a cost the design would weigh).

---

## Codasip X730: the first commercial CHERI-RISC-V application core, shipping evidence and a silicon path, not the base

The **X730** (Codasip) is the first commercially licensable CHERI-RISC-V processor: a 64-bit, in-order, nine-stage, dual-issue application core whose register file and selected CSRs widen to 129 bits to hold a 128-bit capability and its tag, with a capability-checking unit that every instruction issues to alongside another execution unit, their outputs combined at commit.
It is the CHERI variant of the **A730** the drop-PMP argument already cites (§15), on a shared codebase that reports the CHERI version at a **sub-5% area delta** and the same maximum frequency: shipping commercial evidence for the design's own thesis that application-class purecap CHERI is real and cheap, at the scale where CheriOS and CHERIoT are only microcontroller-class existence proofs (§17).
What it offers beyond the open designs sits on the *engineering-is-free* axis, never the scarce trust axis: it is the most direct answer to §18's binding constraint (application-class CHERI exists only as licensable IP and FPGA soft cores), and its CodAL / Codasip Studio single-source flow regenerates RTL, an LLVM toolchain, and a verification environment from one description, an accelerator for curating the frozen, MMU-less, static-prediction profile (§15).
What the design does **not** take is the X730 as its trusted base: the RTL is proprietary and authored in CodAL, and Codasip's UVM-plus-formal sign-off is riscv-formal / Isla-class bring-up evidence, a complement and never the closing axiom (§6), so it cannot carry the load-bearing **RTL ⊑ Sail** refinement (§15, §18) that an open core re-expressible into a formal-semantics HDL can; and as shipped it is the general-purpose MMU-on, S/U-mode, Linux-booting configuration the profile curates away.
So the X730 is a licensed **reference, bring-up, and possible silicon vehicle**: the commercial complement to the open **CVA6-CHERI / COSMIC** track (above), which stays the C-class front end precisely because it is open, re-expressible, and on a conformance-proof path.

---


## openwifi and the SoftMAC split: the firmware-free low-MAC, and the partition that keeps the radio out of the foreign-computer category

The dissolved-modem thesis (§4, §12) puts the whole radio stack in contained software on the pinned V-cores, and runs into one deadline software cannot hold: the sub-slot **turnaround**, where the radio must flip the RX/TX path and be transmitting within a fixed inter-frame gap (BLE `T_IFS` at 150 µs ± 2 µs, 802.11 SIFS at 10 or 16 µs, 802.15.4 at ~192 µs).
A general-purpose core's interrupt-and-schedule path cannot reliably hit a ±2 µs window, which is why every shipping radio puts that turnaround below the software line — and the question is only *what* sits below it.

The industry answer this design **rejects** is the **FullMAC controller**: the entire link layer and MAC as firmware on a hidden core, which is exactly the "Wi-Fi/BT controller firmware" §4 bans, the largest foreign computer the radio architecture exists to delete.
The answer it **takes** is the mainstream alternative: the **SoftMAC / split-MAC** partition, in which time-critical turnaround is fixed hardware and the link layer and everything above it are software.
Three artifacts supply it:

- **Linux's `mac80211`** is the reference decomposition, running the timing-critical MAC (ACK, SIFS, backoff) in hardware and the management MAC in host software, which is precisely the line §12 draws.
- **Nordic's nRF radios with Zephyr's open Link Layer** demonstrate it on the exact hardest protocol, meeting BLE `T_IFS` with a hardware *tIFS timer* (dedicated capture/compare registers) while the link-layer state machine, L2CAP, and GATT run in software.
- **openwifi** is the closest match to the form actually needed, and is already the §18 radio start-from: its *"DCF low-MAC layer in FPGA"* meets the 10 µs SIFS ACK **in Verilog rather than on a core**, which is the firmware-free, open-RTL existence proof for the fixed-function turnaround block, harvestable under the open-RTL mandate.

Also weighed and set aside is Microsoft's **Sora** (NSDI '09), which hit Wi-Fi SIFS in *pure software* by core-dedication and lookahead: it keeps everything inside the trust structure, but spends the tightest real-time budget on the most jitter-sensitive path, which at 150 µs and 16 µs is fragile (the [link-layer-timing disposition](architectural-alternatives.md) carries the three-way comparison).

The transformation is the usual one: **the split is off-the-shelf and the verified realization is the contribution.**
None of these artifacts is formally verified or Sail-modeled, so what the platform builds is a fixed-function timing sequencer inside the register-slave transceiver datapath — a hardware timer and small finite state machine with no instruction fetch, no writable program, no firmware, and no protocol decision — Sail-modeled and capability-gated, one more fixed-latency entry riding the existing transceiver RTL ⊑ Sail and WCET obligations (§11, §15).
That is what keeps it on the *matter, not software* side of §4's line, alongside the digital front end, the FEC blocks, and the I/Q-streaming DMA.

The partition generalizes past the radio into the standing **sensor-front-end doctrine** (§12, §15): the analog front end plus a fixed-cadence scan or sample sequencer stays matter, streaming raw samples over a capability-bounded DMA window, while all signal processing dissolves onto the host V-cores — capacitive touch, the audio front end, the image sensor's raw Bayer path, IMU and motion, and the fingerprint AFE alike.
Honest residual (§17): the radio case has an off-the-shelf firmware-free part to point at and the sensor cases do not, since commodity touch, audio, and image controllers co-design the AFE with tuned DSP firmware, so the raw-AFE silicon and its host-side DSP are a genuine net-new co-design.

---

## PIC64-HPSC: space-grade application-class RISC-V, radiation hardening as a manufacturing choice, not an architecture

The **PIC64-HPSC** (Microchip, for NASA's **High-Performance Spaceflight Computing** program) is the space-grade instance of the design's own substrate class: a 64-bit **application-class RISC-V** multiprocessor built around **eight SiFive X280 cores** carrying the **vector extension**, made **radiation-hardened and fault-tolerant** (pervasive ECC, lockstep options, a wide operating-temperature range), the RISC-V successor to the PowerPC **RAD750** that has flown NASA's spacecraft for two decades.
It is the existence proof that **application-class RISC-V with vectors, hardened against the space radiation environment, is a real and funded product class** rather than a research aspiration, and it validates three of the design's own choices on hardened silicon: the **RV64 plus vector** compute shape (§15), the **reliability posture** the memory subsystem and enclosure already mandate (pervasive ECC, fault containment, wide-temperature tolerance, §15, §16), and lockstep as a hardware **fault-detection** complement to §7's per-core kernel duplication for fault containment (the same G5 note the COSMIC entry logs, above).

The design **re-grounds** the import on its own axioms exactly as it does the Codasip X730 and CVA6-CHERI silicon (above), and the split is unusually clean because **space-grade is a property of the process and the RTL, not of the instruction set**.
What transfers is the **realization**: the radiation-hardened-by-design process (single-event-hardened cells, latch-up immunity, the wide temperature range), the fault-tolerance features, and the demonstration that a modern RISC-V vector machine survives the environment at all.
What does **not** transfer is the architecture: the PIC64-HPSC is **RV64GC** (the C compressed extension the profile drops and the scalar floating-point it folds onto the vector unit, §15), it carries an **MMU** and boots a conventional operating system (the profile deletes the MMU for a single address space, `satp` Bare, §15), it is **not CHERI** (the spine of the whole design), and its SiFive cores are third-party RTL whose vendor verification is bring-up evidence, never the closing **RTL ⊑ Sail** axiom (§6, §15).
So the platform imports the **radiation-hardened realization onto its own RV64+CHERI profile** rather than taking the PIC64-HPSC as a base: harden the manufacturing and the RTL of the design that already exists, changing no computation and lowering no guarantee, the source-side upset-rate reduction the Faraday enclosure cannot itself provide (§15).

**Intel's Starfire brackets the same axis from the opposite end**, and is worth recording beside it for the contrast rather than as a second import.
An 18A space-grade SoC for the US government with samples due Q3 2026, it pushes a **leading-edge commercial-class part** (RibbonFET and backside power, an eight-core CPU with an on-die NPU) into orbit by **design-level hardening** rather than by a mature radiation-tolerant node, across a minus-55 to 125 Celsius junction range.
Where the PIC64-HPSC hardens a conservative design, Starfire hardens an aggressive one, and both make the move this design makes — harden a commercial-class design rather than invent a space architecture.
The lesson Starfire teaches *by contrast* is what a space-grade part must actually publish: not cores, TOPS, temperature, or lifetime, but its **total-ionizing-dose limit, single-event-latch-up threshold, and single-event-effect cross-section**, established by a radiation test campaign.
The PIC64-HPSC1000-RH publishes 200 krad(Si) and latch-up immunity to 78 MeV·cm²/mg; Starfire's are still under evaluation, which is the honest tell that it is not yet radiation-qualified.
Those numbers are **evidence about the physical realization that no formal proof can reach**, the radiation-environment analog of the bounded bring-up evidence this design already leans on (commercial FEV and riscv-formal for RTL conformance, IRIS backside inspection for the fab residual), so they discharge a qualification obligation by testing and enter no trust base, exactly as those complements do not.
This design is also better placed than a bet on the process alone, since it detects, corrects, or contains upsets pervasively (SECDED and DECTED ECC on every array, multikernel blast-radius containment, fail-stop, §15, §16): it does not need a hardened node to force the raw upset rate down to a commercial fault model's tolerance the way an unhardened commercial part flown to orbit must, so the leading-edge susceptibility that makes Starfire's bet hard is a load the correction layer already carries and hardening only lightens.

The fuller treatment of the space-grade realization axis (radiation, temperature, pressure, and vacuum) is in [Evaluated Architectural Alternatives](architectural-alternatives.md).

---

## Fuchsia OS: the capability-IPC model (handles out-of-band, bounds in the schema)

Google's Fuchsia is the shipping demonstration that a **from-scratch capability microkernel** (Zircon) can carry a real consumer device OS with **no ambient authority**: every resource is an unforgeable **handle**, a component receives only the capabilities its **manifest** declares, and there is no POSIX-by-default, no global namespace, no `fork`.
That posture is §8 (capabilities as the sole authority) and §12/§13 (per-compartment capability manifests) at product scale: the same ground seL4 (above) supplies as *proof* and Fuchsia supplies as *shipping evidence*.
But the load-bearing import is **FIDL**, Fuchsia's interface-definition language, and its **Zircon-channel** wire model, the exemplar sitting *beneath* the §12 interface layer: a FIDL message travels as **bytes plus out-of-band handles** over a channel, exactly §12's rule that a ring descriptor "names only indices into a per-session table of pre-delegated capabilities, plus offset/length" with **authority arriving over the control plane, never across the data plane**: a Zircon channel is what the §12 data plane structurally *is*.
FIDL also carries the two disciplines the §12 IDL profile has to *add* to its WIT-derived type layer: **mandatory schema bounds** (`vector<T>:N`, `string:N`, `array<T,N>`: no unbounded wire object) and **decoders hardened at a trust boundary**, both native to FIDL because it was built for **mutually distrusting compartments** across a capability kernel: this platform's exact setting (§12, §16).
So the interface stack is a deliberate **hybrid**: the *type/interface* layer is WIT-derived (worlds → manifests, resources → capabilities; §12, §13), while the *wire/data-plane* layer is FIDL/Zircon-channel.
Where the design parts company is the usual mechanism swap: FIDL and Zircon are **unverified C++**, so marshalling becomes the **Narcissus copy-once verified parser** (§5), Zircon **handles and their rights become seL4/CHERI capabilities** (the taxonomy re-mapped, not inherited; §8, §15), FIDL's missing **world** concept is why the *type* layer is WIT rather than FIDL, and FIDL's missing **information-flow labels** are added as a first-class §12 concern.
Fuchsia supplies the shipping proof that capability IPC scales to a real OS; FIDL supplies the wire discipline (bounded, handle-passing, distrust-hardened) that the §12 data plane adopts and the copy-once parsers then make a theorem.
