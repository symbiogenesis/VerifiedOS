# The Typed Assembly Language

> **What this is.**
> This document specifies the typed machine-code language—and its admission check—that [VerifiedOS](spec.md) uses to admit binaries.
> It is factored into a project of its own because it depends only on a machine semantics and a type theory. It does not depend on a kernel, storage stack, authority model, or hardware beyond the target's instruction semantics.
>
> **Normative for the language; not a derived view.**
> The [frozen instruction-set profile](isa-profile.md), the [absence contract](absence-contract.md), the [crown-jewel inventory](crown-jewels.md), and the [coverage matrix](coverage-matrix.md) are derived views of [requirements-register.md](requirements-register.md) and state no obligation of their own.
> This document is different: it states the language's obligations. VerifiedOS depends on one instantiation and pins its version.
> If this document and the register disagree about VerifiedOS requirements, the register governs. If they disagree about the language itself, this document governs.
>
> **The name is provisional and the instantiation keeps its own.**
> *Typed Assembly Language* is descriptive rather than chosen.
> The VerifiedOS corpus continues to call the CHERI-RISC-V instantiation *CHERI-TAL*; this factoring changes no name.
>
> **Nothing here is built.**
> The type system, checker, and soundness proof have not been written. Factoring out this specification relocates that work; it does not reduce it.
> The benefit is a reviewable artifact whose correctness is independent of operating-system claims, together with an implementation cost that multiple consumers could share.

---

## 1. What the language is

This is a **typed assembly language** in the Necula ⋈ Morrisett lineage: final machine code carries a **typing derivation**, which is checked before the code may run.

Three additional commitments distinguish this language from that lineage:

- **The check is certificate-directed dataflow validation, not proof checking.**
  The checker decides a fixed set of attributes over an already-typed control-flow graph. The derivation supplies the abstract state at every join, so certificate consumption requires neither fixpoint computation nor reduction of open terms.
  The closest precedent is **lightweight bytecode verification** (Rose, JAR 2003; Klein and Nipkow's verified account). There, stack maps carry the abstract state at each merge, reducing verification from dataflow solving to checking local transfer constraints (§9).
  A producer may use any fixpoint analysis it chooses to compute those annotations. The no-fixpoint claim applies only to certificate consumption (§7).
  This is a claim about the kind of checker being specified. Every budget below follows from that classification; the budgets are not independent targets.
- **The theory is frozen, and freezing it is the mechanism, not an austerity.**
  A line budget does not constrain an unspecified theory: checker size is driven by what the checker must decide (§3).
- **The target's own guarantees are a parameter, not an assumption.**
  A target profile declares which machine-enforced invariants the derivation may *cite* instead of re-proving (§2).

The check is per-install, decidable, syntactically terminating, and local.
It is not—and may not become—a proof checker. Obligations that do not fit are discharged by the consumer's proof kernel as release-time proof terms (§4); that separation is the purpose of the stratification.

---

## 2. The parameter: the machine profile

A **machine profile** has two parts: the **machine semantics** againstwhich the derivation is stated, and the **cited invariant set** containing the properties those semantics enforce at run time without help from the type system.

For every obligation in §4 a profile declares exactly one discharge route:

| Route | Meaning | Cost |
| --- | --- | --- |
| **Cited** | The machine enforces it. The derivation records the invariant on which it relies, and the checker validates that citation. | Citation validation at check time; no additional *software* run-time check. The machine's own checks still execute. |
| **Attributed** | The type system decides it statically as a §5 attribute. | Check time only. |
| **Inserted** | The producer emits an ordinary run-time check and the type system requires that check to dominate every access it guards. | Run time. |

The route order is intentional. A cited invariant adds no software enforcement; an attributed invariant is checked once at admission; an inserted invariant is checked on every execution.

**This document specifies two profiles. They differ only in routing: every obligation cited by `cheri-rv64` moves to a lower route under `bare-rv64`; all other routes remain unchanged.**

- **`cheri-rv64`**, the profile VerifiedOS pins.
  Bounds, tags, monotone derivation, and sealed entry are architectural, so spatial memory safety, no-runtime-codegen, and the run-time half of control-flow integrity (which authority may be executed, and where an entry may land) are **cited**, and of that cluster the type system carries only the residual the hardware does not enforce: temporal safety, exclusive access, and typed control flow.
  Control-flow integrity requires particular care. The machine bounds executable authority and valid entry points; the legal target set of each indirect transfer and the signature of the target remain **attributed**, because an instruction set does not define that policy.
  This is the profile in which the language is small.
- **`bare-rv64`**, the profile with no capability hardware.
  This profile cites no invariant.
  Spatial safety becomes **inserted** (bounds checks the type system locates and requires) or, at the producer's option, a fat-pointer ABI in which a bounds pair is an ordinary aggregate the type fixes the representation of.
  No-runtime-codegen and the run-time half of control-flow integrity become **attributed**: with every store and every indirect transfer typed, the classical TAL account (no writable authority over code, typed jumps) decides statically what the hardware no longer checks, and both halves of control flow then rest on one attribute.
  Provenance remains **attributed** because the integer-to-pointer deletion (§5, move III) is a type-system fact, not a hardware fact.

**A citation is a theorem about the machine. An unsound citation invalidates everything that depends on it.**
The capability literature states important qualifications; a profile that omits them is defective.
Compressed capability encodings permit **inexact bounds**. A cited spatial-safety invariant therefore holds for the rounded representable region defined by the encoding, not necessarily for the exact byte range intended by the source.
Monotone derivation has **privileged and transition cases**, the instructions and states in which authority is installed rather than narrowed, and a citation must name them rather than quantify over the whole machine.
Capability hardware alone does not provide **temporal safety, exact callee sets, or ABI conformance**. Its immutable-code guarantee also depends on an initial capability distribution from which no writable-and-executable authority can be derived—a loader property, not an instruction-set property.
`cheri-rv64` therefore declares, beside the four architectural facts above, the execution-mode, loader, privilege, and memory-permission assumptions under which they hold, and every one of those is a premise the profile's soundness instantiation (§6) discharges rather than assumes.

**What a bare profile does not recover.**
A cited invariant holds against *arbitrary co-resident code* because the machine checks every access, regardless of who issued it.
An attributed or inserted invariant holds only while all code in the address space is well-typed.
The guarantee is therefore **open-world** under `cheri-rv64` and **closed-world** under `bare-rv64`, and no amount of type-system work closes that gap: it is the difference between a machine that checks and a machine that was persuaded.
A consumer running unverified native code beside admitted code needs a cited profile or an isolation mechanism outside this language.

**The route that is refused.**
Spatial safety by **index refinement** (dependent or singleton types over lengths, the DTAL and Xanadu line) is not an admissible fourth route, because deciding it requires arithmetic constraint solving over open terms.
That would violate §3's absence (2) directly, turn the checker from an attribute evaluator into a solver, and falsify the category claim §1 rests on.
This refusal is deliberate despite the existence of a bounded form. Wasm-precheck (Geller, Frank, and Bowman, POPL 2024) places an indexed-type discipline inside a linear-pass validator without an SMT solver. This language still declines that approach because even restricted constraint entailment decides propositions over open terms; the distinction is one of checker kind, not solver size.
Refusing it is what keeps every profile's checker the same *kind* of artifact, differing in the size of its attribute set and never in what it must decide.

**Profiles are frozen and versioned like the theory.**
A profile is admitted only on a shown demonstration that every obligation has a route, that each cited invariant is a theorem of the machine semantics rather than a claim about an implementation, and that each inserted check has a stated placement rule the attribute evaluator can confirm.

---

## 3. The frozen theory

This document fixes and closes the type theory. The following four absences make checking a dataflow validation rather than proof checking:

1. **Predicative, rank-1 prenex polymorphism.**
   Type variables are quantified only at the outermost position of a code type and instantiated only at monotypes: the classical TALx86 use (polymorphism over callee-saved registers and stack tails) and no more.
   Instantiation is first-order substitution, so there is no impredicative self-instantiation to justify and no rank-*n* inference to decide.
2. **No type-level computation.**
   Type equality is syntactic, α-equivalence over first-order terms, decided by structural comparison and not by conversion: no βδιζη-reduction, no normalizer, no evaluation of open terms, and therefore no strong-normalization premise inside the checker.
   This is the largest deletion and the one that makes termination syntactic rather than a metatheoretic side condition the trusted base (§6) would have to carry.
3. **No universes and no universe polymorphism.**
   There is one sort of types, with no cumulativity, universe-constraint graph, or acyclicity solver.
4. **No user-extensible inductive definitions.**
   The type constructors are a fixed, closed vocabulary: capability or pointer types with their bounds, permissions, grant binding (bare, or a handle to a grant slot), and initialization flag; code types as register-file preconditions carrying the callee set at indirect transfers; the aggregate and existential formers an ABI needs; the linear, affine, and relevance grades; the taint labels; and the cost annotations.
   The checker performs no positivity check, guard check, or eliminator generation. The vocabulary may grow only by amendment to this document, never at install time.

**Why the four absences are load-bearing.**
A term checker for a full calculus of inductive constructions spends its tens of thousands of lines on four hard structures: universe constraints, conversion, positivity, and the guard condition.
Absences (2), (3), and (4) delete exactly those four, and absence (1) removes the instantiation and inference problems higher-rank polymorphism would reintroduce, so what remains is not a small dependent-type checker but *not a dependent-type checker at all*, and the line budget (on the order of a thousand lines of shipped checker) is a consequence of that rather than a target an implementation is asked to hit.
What the checker does instead is evaluate a fixed attribute set over the already-typed control-flow graph (the type under structural equality, the threaded linear context, the taint lattice, the cost semiring, the callee set), taking the abstract state at each join from the derivation rather than computing it, and confirm each *local* constraint: tens of lines of evaluator per attribute.

**What the figure counts, so the budget is auditable rather than rhetorical.**
The figure includes the shipped source for the attribute evaluator, derivation reader, and image scan.
It excludes the frozen type-constructor vocabulary and the attribute tables (data fixed by this document, whose size is bounded by amendment rather than by implementation), a consumer's own proof kernel (a separate checker with its own budget), and the metatheory.
A checker that met the figure by moving decisions into a generated table would fail the claim, the category fact being what the budget actually asserts.

**Every rider is shown to fit the theory rather than assumed to, which is the point of stating the theory at all.**
Memory safety and control-flow integrity are register-file preconditions over capability or pointer types, and first-order.
The linear and affine discipline and the relevance grading are context-splitting side conditions decided structurally.
Absence of ambient mutable state is decided by inspecting the image's static data for a set tag.
The callee set is a finite collection of first-order code labels whose membership test is structural set comparison, so it refines an existing former by amendment (absence (4)'s own reserved mechanism) rather than adding a grade axis.
The initialization flag is a two-point meet-semilattice riding the capability-type former over the slots the consumer's memory plan already fixes, the oldest attribute in the lineage and structurally the same table lookup, and taint is a join in a two-point lattice, another one.
The representation and provenance rules add no former and no grade at all: they are the five deletions move III of §5 enumerates, four of them *absences* the checker confirms by inspecting a derivation it already reads.
The three grade re-uses add nothing either: *use-once* is the linear grade the context-splitting side condition already runs, *must-erase* is its relevance polarity, and a *dimension* is a phantom parameter under absence (2)'s syntactic type equality, inhabited by no term and erased before code generation.

**The amendment rule.**
A proposed attribute is admitted only after a demonstration that it (1) has a finite semilattice or monoid domain, is decided without open-term reduction, and preserves syntactic type equality; (2) duplicates no existing grade or label axis; and (3) has a local, syntax-directed rule.
A feature that fails is not lost: it descends to the consumer's proof kernel as a release-time proof term, at the price of ceasing to be per-install checkable.

**One computation is permitted and its boundary is stated.**
Cost annotations require adding and comparing literal naturals along a max-path sum, and overflow side conditions require comparing literal bounds at each arithmetic rule.
Both are bounded-width arithmetic over *closed numerals* decided in constant time per node: computation, but not the reduction of open terms absence (2) forbids.
Anything needing the latter is not a type-level obligation, which is why overflow-freedom over a run-time-dependent bound descends rather than widening the theory to hold it.

**The theory binds the checker, not the producer.**
A certifying compiler may be written in, and reason with, whatever theory it likes; only the shipped derivation must be checkable in this one.

---

## 4. The obligations the language can carry

The language defines a **menu** of obligations; each consumer selects the subset it requires.
This document says what is expressible and decidable; the consumer's own specification says what it demands, so the two cannot come to disagree about a list.
The menu is the eleven obligations below; VerifiedOS requires all eleven, canonically enumerated at R-05-029 of its register, and its lower assurance tier scopes a stated subset of the same list rather than a list of its own.

1. Memory safety, including spatial and temporal safety.
2. Definite initialization.
3. Data-race freedom.
4. Control-flow integrity, including its run-time and callee-set-enumeration halves.
5. No run-time code generation.
6. Type and ABI conformance.
7. Examined verdicts through relevance grading.
8. Absence of ambient mutable state.
9. Representation and provenance conformance.
10. Secret-taint constant-time behavior.
11. Worst-case execution cost.

Two obligations require explanation because the literature usually treats them as proof obligations:

- **Constant-time** is a 2-safety hyperproperty, which a type system cannot state in general, but the CT-Wasm result makes it a **taint-typing** obligation for structured code: secret-labeled values the type system forbids from reaching a branch condition, a memory address, or a variable-latency operation.
  Only the genuinely unstructured residual descends to a relational proof.
  The guarantee is relative to the profile's declared **leakage model** rather than absolute, and it does not survive a lowering the type system never sees, which is exactly why the obligation is stated over final code rather than over a source or intermediate form (§8).
- **Worst-case cost** is a quantitative property, but for structured code it is a syntax-directed max-path sum over the already-typed control-flow graph (Shaw's timing schema), carried as a cost annotation rather than produced by a separate analyzer.
  The sum is sound only given supplied loop and recursion bounds, the path facts that exclude infeasible worst cases, and a machine cost model in which per-instruction costs actually compose: caches, pipelines, speculation, interrupts, and shared resources each falsify that composition, so a profile that neither deletes nor bounds them owes an inserted-route argument rather than an attributed one.

No profile carries the deep tier: functional refinement, whole-system non-interference, cryptographic reduction security, linearizability, or liveness.
These are outside the decidable type system and remain proof obligations.

**The menu is not a routine consequence of having finite attribute domains, and the hard cases are known in advance.**
Temporal safety over a real allocator, data-race freedom under a weak memory model, cost over a genuinely unstructured control-flow graph, and constant-time preserved down to native code are the four places where the soundness argument is hard, independently of how small the checker is.
A profile or an instantiation that presents any of them as a small case of §5's move II has mislabeled its own difficulty, and the schedule that follows will be wrong in the same proportion.

---

## 5. The three moves

The checker handles the menu using exactly three moves. The profile in §2 determines how obligations are routed to them:

| Move | What the checker does | Why it stays small |
| --- | --- | --- |
| **I. Cite a run-time invariant** | Confirms the derivation records reliance on an invariant the profile declares architectural. | It does not re-prove the machine's fact; it inspects the reliance. |
| **II. Evaluate an attribute** | Runs a local, syntax-directed attribute pass over the typed control-flow graph, taking the abstract state at each join from the derivation and confirming the linear contexts agree there. | Each attribute has a finite domain and a local rule, and the derivation supplies the joins a fixpoint would otherwise have to find. |
| **III. Confirm a deletion** | Checks that constructs which would make the static account lie are absent. | These are one-pass inspections of absences: no integer-to-pointer construction, no type punning, no variadic arity, no unbounded recursive former, no implicit conversion. |

Move I is empty for a profile that cites no invariants. In that precise sense, a bare target is more expensive than a capability target: the obligations remain, but move to lower routes in the §2 table.

The word *attribute* is Knuth's, and the analogy is deliberately partial: an attribute grammar decorates a tree, while a machine-code control-flow graph is cyclic, which is precisely why the derivation carries the abstract state at every merge and the checker validates rather than solves (§1).

---

## 6. Soundness

The metatheorem is **well-typed implies safe**, stated over a profile's machine semantics: every execution of a well-typed program satisfies the obligations claimed by its derivation. This follows the foundational-TAL, RustBelt, and WasmCert-Coq lineage.

It is **parameterized over the profile and discharged per instantiation**.
The core carries every proof obligation that does not mention the machine; a profile discharges the rest by supplying, for each cited invariant, a theorem of its own machine semantics, and for each inserted check, a domination argument.
A second profile therefore need not reopen the entire proof, but it is not free: it must discharge every machine-dependent case. If it cites an invariant absent from its semantics, the resulting proof describes a machine that does not exist.

The metatheorem is the language's *main trusted theorem*, and freezing the theory bounds its size just as it bounds the checker's: the two shrink together.
Calling it the single axiom would understate the base, and the honest list is short but longer than one: a consumer also trusts the machine semantics and its correspondence to the silicon that runs it, the profile's cited invariants, the decoder that recovers instructions from the image, the loader and initial-state model the derivation is stated against, and the implementation of the checker itself.
The claim worth making is that this list is small, fixed, and separately reviewable, not that it has one element.
A mis-stated typing rule admits an unsafe binary that type-checks perfectly, exactly as a wrong specification verifies perfectly, which is why this is a specification worth reviewing rather than a proof worth trusting.

---

## 7. Producers

**Admission depends on the derivation, never on producer identity.**
Any producer of a well-typed binary is admissible by definition, and a consumer's reference compiler is a reference rather than a gate.

**A producer may be built on an existing unverified toolchain, and should be.**
The practical shape is **hinted mirroring**: the untrusted compiler records hints through lowering and a small trusted replayer reconstructs the derivation the checker re-validates.
This architecture requires a small replayer beside an arbitrary producer, not a whole-compiler preservation proof. An LLVM backend is therefore a reasonable implementation path.
The precedent is Necula and Lee's certifying compiler and, closer to this shape, **Crellvm**, in which an untrusted optimizer emits hints a verified checker reconstructs and validates; Crellvm covered selected intermediate-representation optimizations rather than native code generation, so it supports the architecture without completing it (§9).

**This does not make guarantees independent of the source language.**
A compiler intermediate representation carries none of the facts the derivation asserts: ownership, lifetime, exclusivity, initialization, taint, dimension, and callee sets come from the *source* type system, not from the lowering.
Downstream tooling cannot preserve a fact that the source never established.

A source language is therefore admissible on one of three grounds:

1. **It establishes the facts itself** (an ownership discipline, a synchronous dataflow language, a proof assistant's term language, or verified C with its own proofs), in which case the producer preserves them and the derivation is cheap.
2. **It accepts insertion**, in which case the producer emits run-time checks and the type system requires them, exactly as the `bare-rv64` profile does for bounds: the guarantee holds, and it is paid for on every execution.
3. **It ships a source-level proof** elaborated into a semantics the consumer already reviews.

A language satisfying none of these conditions is not admitted; choosing a different backend does not change that result.
This is the same fact as §2's profile table seen from the other end: when an invariant is not supplied by the environment, the language must demand a proof or insert a check, and it makes no difference whether the environment that failed to supply it was the hardware or the source language.

---

## 8. What this is not

- **Not an isolation mechanism.** Its guarantees apply to admitted code. A system that also runs other code needs hardware isolation or a supervisor; under a bare profile, that requirement is mandatory (§2).
- **Not an intermediate representation.** It types final machine code against a machine semantics, so a target needs an ISA semantics of the quality of a Sail model before it can have a profile at all.
  That this is achievable rather than aspirational is the RockSalt and Islaris result: a decoded binary image checked against a machine model proved sound in a proof assistant, and binary machine code reasoned about against full Sail-derived semantics (§9).
- **Not a proof system.** The deep tier stays with a proof kernel (§4), and every proposal to move an obligation inward is decided by §3's amendment rule rather than by appetite.
- **Not a safety claim about a source language.** It carries facts; it does not manufacture them (§7).

---

## 9. Prior art

The design synthesizes several mature lines of work rather than instantiating any one of them. Its components have precedent; their *combination* does not.

**Typed assembly language.**
Morrisett, Walker, Crary, and Glew, *From System F to Typed Assembly Language* (TOPLAS 1999); Morrisett et al., *TALx86: A Realistic Typed Assembly Language* (WCSSS 1999); Crary, *Toward a Foundational Typed Assembly Language* (POPL 2003).
These supply polymorphic code-pointer types, register-file preconditions, stack polymorphism, initialization tracking, typed indirect jumps, and producer-supplied derivations, which is most of §3's vocabulary.
Two boundaries in that lineage are exactly the ones this document has to cross: TALx86 checked *annotated assembly* rather than independently decoded executable bytes, and foundational TAL separates its abstract-machine soundness from the correspondence with a concrete architecture that a profile here must supply (§2, §6).

**Proof-carrying code.**
Necula, *Proof-Carrying Code* (POPL 1997); Appel, *Foundational Proof-Carrying Code* (LICS 2001); Hamid et al., *A Syntactic Approach to Foundational Proof-Carrying Code* (LICS 2002).
Proof-carrying code already covers binary machine code from an untrusted producer checked against a consumer-defined policy; the foundational account makes decoding, machine semantics, and the safety predicate foundational; and the syntactic account factors a certificate into a typing derivation plus a reusable soundness proof, which is precisely this document's split between §4 and §6.

**Certificate-directed checking.**
Rose, *Lightweight Bytecode Verification* (JAR 2003); Klein and Nipkow, *Verified Lightweight Bytecode Verification*.
This is the closest precedent for §1's architecture, and the reason the no-fixpoint claim is stated as a property of certificate *consumption* rather than as an absence of analysis anywhere in the pipeline.
It is also the one piece of the design with a planetary-scale deployment and a live revival on both flanks: the JVM's split verifier (JSR 202's stack-map frames, mandatory since class-file version 51) is this architecture in production, its type-checking core a few thousand lines over a richer vocabulary than §3's, and Klein and Nipkow's account is *maintained*, re-checked against every Isabelle release in the Archive of Formal Proofs; CertrBPF (Yuan et al., CAV 2022) is a Coq-verified admission checker extracted to C and shipped in an embedded operating system; and BCF (Sun and Su, SOSP 2025) has the Linux eBPF verifier accept load-time certificates proved in user space and checked by a small checker in the kernel.
The counter-experiment is on the record too: VeriWasm re-derived the safety of compiled native code by analysis rather than certificate, and its revival was abandoned when the analysis could not keep pace with the compiler, which is the analyzer-rot failure mode a shipped derivation does not have.

**Typed admission in production.**
The Move bytecode verifier checks linear resources, definite initialization, and a borrow discipline at publish time on chains that hold real value, and WebAssembly's shipped type system makes an indirect call through `call_ref` a load-time-checked typed callee set, so most of §4's attribute classes have a production admission precedent, taint alone having none anywhere.
Both are fixpoint analyzers rather than certificate consumers, and Move's unreachable-code soundness bug (Zellic, 2023: code in unreachable blocks evading the reference-safety passes on every deployed chain at once) is the concrete argument for a checker small enough to verify.

**Final machine code.**
Morrisett et al., *RockSalt* (PLDI 2012); Sammler et al., *Islaris* (PLDI 2022); Armstrong et al., *ISA Semantics for ARMv8-A, RISC-V, and CHERI-MIPS* (POPL 2019).
RockSalt parses a real binary image and applies a generated checker proved sound against a machine model; Islaris verifies binary machine code against full Sail-derived Arm and RISC-V semantics.
Together they are the precedent for the seam this language stands on, final bytes against an authoritative machine semantics (§8).
The seam has since been re-walked at full architectural scale: Morello-Cerise (PLDI 2025) proves strong encapsulation for the shipped Morello machine against its authoritative Sail semantics through Isla-generated traces, which is the current state of the bridge a profile's soundness instantiation (§6) must cross.

**Capability machines.**
Watson et al., the CHERI ISA specification (University of Cambridge technical report); the CHERI-RISC-V Sail model; Nienhuis et al., *Rigorous Engineering for Hardware Security* (S&P 2020).
These are what a citing profile cites (§2): tagged capabilities, bounds, permissions, sealing, provenance validity, and guarded monotone derivation.
Their published qualifications, inexact compressed bounds and the privileged and transition cases of monotonicity, are what a profile's declaration must state rather than gloss.

**Capability-machine logics and universal contracts.**
Georges et al., *Cerise* (JACM 2024); Huyghebaert, Keuchel, De Roover, and Devriese, *ISA Security Guarantees as Universal Contracts* (CCS 2023, on the Katamaran verifier); Bauereiss et al., *Verified Security for the Morello Capability-enhanced Prototype Arm Architecture* (ESOP 2022).
This is the road the field took instead of typed assembly: a program logic whose logical relation gives *arbitrary* code a universal contract, which is the mechanized form of exactly what a citing profile cites (§2) and the defense in depth beneath a checker or metatheorem error.
Each member is idealized (Cerise's machine, Katamaran's MinimalCaps case study) or in another prover (the Morello monotonicity proof is Isabelle), and none yields a per-binary certificate; the distance between a universal contract over all code and a derivation about this binary is exactly the language.

**Linear control and ownership.**
Skorstengaard, Devriese, and Birkedal, *StkTokens* (POPL 2019); Crary, Walker, and Morrisett, *Typed Memory Management in a Calculus of Capabilities* (POPL 1999); Smith, Walker, and Morrisett, *Alias Types* (ESOP 2000); Jung et al., *RustBelt* (POPL 2018).
StkTokens is the direct precedent for a linear capability discipline proving well-bracketed control flow and stack encapsulation.
It does not establish general heap temporal safety on ordinary capability hardware, which is why the temporal-safety obligation of §4 owes an allocator-and-reuse theorem of its own (§6) rather than inheriting one.

**Constant-time typing.**
Watt et al., *CT-Wasm* (POPL 2019); Barthe et al., *System-level Non-interference for Constant-time Cryptography* (CCS 2014); Almeida et al., *Verifying Constant-Time Implementations* (USENIX Security 2016).
CT-Wasm is the direct precedent for §4's taint-typing route, mechanized through semantics, checker, and soundness together, and its guarantee is relative to an explicit leakage model rather than absolute.
Two recent results confirm the route from either end: SecSep (Song et al., CCS 2025) is a literal taint-typed assembly language for x86-64 cryptographic code, annotations inferred by a producer and re-checked over the final assembly, carrying exactly this obligation and no other; and the structured-leakage line in the Jasmin compiler (Barthe et al., CCS 2021) transports constant-time and cost facts together through compilation as Coq-proved leakage transformers, the nearest mechanized metatheory to hold §4's two boundary cases in one frame.

**Cost certificates.**
Shaw, *Reasoning About Time in Higher-Level Language Software* (TSE 1989); Li and Malik, implicit path enumeration (1995); Carbonneaux et al., *Automated Resource Analysis with Coq Proof Objects* (CAV 2017).
These support compositional timing annotations and independently checked resource bounds, under exactly the side conditions §4 states and not otherwise.
The certificate form itself has one shipped ancestor and one typed one, both defunct: the Mobile Resource Guarantees project (Hofmann, Jost, Aspinall et al., ~2004) made the resource-typing derivation the certificate a consumer replays over JVM bytecode, CerCo (2013) carried exact per-block machine costs through a verified compiler in Matita, and Crary and Weirich's *Resource Bound Certification* (POPL 2000) put the clock in a TAL's types on paper alone; the attribute's precedent is therefore method rather than code, and §10 counts it so.

**Certifying compilation.**
Necula and Lee, *The Design and Implementation of a Certifying Compiler* (PLDI 1998); Kang et al., *Crellvm* (PLDI 2018); the translation-validation and CompCert lines.
Crellvm is the closest match to §7's hinted mirroring, over selected intermediate-representation optimizations rather than native code generation.

**The combination is the novel part.**
Not typed assembly language, not proof-carrying code, not capability typing, not taint typing, and not resource certificates, each of which is someone else's result.
The combination is: a fixed, non-extensible certificate language carrying all of them at once, assigning every obligation an explicit cited, attributed, or inserted discharge against a *versioned machine profile*, and checking final decoded machine code without invoking a general proof kernel at install time.
That is a claim about the arrangement rather than about any component, and it is the part a reviewer should attack first.

---

## 10. Status and honest accounting

All three parts remain unbuilt: the type system, checker, and soundness proof.
Section 9 identifies the relevant prior art and mechanizations. The general *type-soundness discipline* is established; this instantiation is not.
One caution about the closest mechanized soundness result of this shape: WasmCert-Coq mechanizes WebAssembly's semantics, binary format, typing, and type soundness, but for a *bytecode* rather than a native instruction set, and its published account left end-to-end work unfinished, so it is a template for the metatheorem's shape and not evidence that the same has been carried out over an ISA semantics.

**The artifact landscape, so the start-from is named rather than presumed.**
The founding lineage yields no code to inherit: the TALx86 toolset survives as a 2002 all-rights-reserved download, the Twelf mechanization of foundational TAL and Princeton's LTAL checker were never publicly released, and the Necula-line certifying compilers died closed-source, so §9's first two groups contribute design and metatheory only, with the FPCC trusted-base accounting (a sub-thousand-line C checker over a fixed logic signature) the closest published relative of §3's budget claim.
What a `cheri-rv64` instantiation stands on today is short and live: the CHERI-RISC-V Sail model's generated Coq, the one existing route to theorems over the real ISA and one over which no published development has yet proved anything, so the profile instantiation is a first rather than a repetition; Katamaran, the actively developed contract verifier over a Sail-like embedding with a capability-machine case study, the natural engine for the per-instruction lemmas and cited-invariant premises; WasmCert-Coq as the maintained skeleton for a checker verified sound and complete against its type system; the Isla-trace route of Islaris and Morello-Cerise for taming a full model; and CT-Wasm's extracted verified checker as the taint attribute's port target, its artifact pinned to a 2017 Isabelle.
Every mechanized relative of the metatheorem chose an idealized machine to stay tractable, which locates the risk precisely: not in the discipline, which is inherited, but in being first to instantiate it over an ISA-scale semantics.
The nearest active lines (universal contracts and secure calling conventions on CHERI-RISC-V at KU Leuven and VUB, taint-typed assembly at MIT) are each approaching one slice of the menu, none the assembly.

Factoring the language out of the operating-system specification changes exactly three things:

1. **The review surface improves.** The language can be reviewed, and its soundness proof read, by someone who has no opinion about capability operating systems.
2. **The cost becomes shareable.** A second consumer at a different profile pays for its own machine-dependent cases and shares the core.
3. **A version seam appears where a freeze used to be.** A theory frozen inside one document is frozen by that document's amendment process; a theory frozen in a dependency is frozen by a pin, and a consumer that fails to re-review on a version bump has silently widened its own axiom set.

None reduces the work, and the factoring does not change the first consumer's schedule.
