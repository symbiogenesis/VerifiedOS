# The Typed Assembly Language

> **What this is.**
> The specification of the typed machine-code language, and the check over it, that [VerifiedOS](verification-maximal-os.md) admits binaries with.
> It is factored out as a project in its own right because its dependency set is a machine semantics and a type theory and nothing else: no kernel, no storage stack, no authority model, and no hardware beyond the target's own instruction semantics.
>
> **Normative for the language; not a derived view.**
> The frozen profile, the absence contract, the crown-jewel inventory, and the coverage matrix are derived views of [requirements-register.md](requirements-register.md) and state no obligation of their own.
> This document is the opposite: it states the language's obligations, and VerifiedOS *depends* on one instantiation of it and pins a version.
> Where the two disagree about what VerifiedOS requires, the register wins; where they disagree about what the language is, this document wins.
>
> **The name is provisional and the instantiation keeps its own.**
> *Typed Assembly language* is descriptive rather than chosen.
> The CHERI-RISC-V instantiation is *CHERI-TAL* throughout the VerifiedOS corpus and stays so: this factoring renames nothing.
>
> **Nothing here is built.**
> The type system, the checker, and the soundness proof are all unwritten, and factoring the specification out relocates that work rather than reducing it.
> What it buys is a reviewable artifact whose correctness does not depend on any claim about an operating system, and a cost that more than one consumer could share.

---

## 1. What the language is

A **typed assembly language** in the Necula ⋈ Morrisett lineage: final machine code carrying a **typing derivation**, checked before the code is permitted to run.

Three commitments distinguish it from that lineage rather than one:

- **The check is certificate-directed dataflow validation, not proof checking.**
  What the checker decides is a fixed set of attributes over an already-typed control-flow graph, evaluated in one syntax-directed pass whose abstract state at every join is *supplied by the derivation* rather than discovered, so the consumer runs no fixpoint and reduces no open term.
  The exact precedent is **lightweight bytecode verification** (Rose, JAR 2003; Klein and Nipkow's verified account), where stack maps carry the abstract state at each merge and reduce the verifier from a dataflow solver to a checker of local transfer constraints (§9).
  The producer may run whatever fixpoint analysis it likes to *compute* those annotations; the no-fixpoint claim is about certificate consumption alone (§7).
  This is a *category* claim, and every other budget in this document is a consequence of it rather than a target set beside it.
- **The theory is frozen, and freezing it is the mechanism, not an austerity.**
  A line budget over an unspecified theory constrains nothing, because what makes a checker large is what it must decide (§3).
- **The target's own guarantees are a parameter, not an assumption.**
  A hardware invariant the machine already enforces is *cited* rather than re-proved, and which invariants those are is exactly what a target profile declares (§2).

The check is per-install, decidable, syntactically terminating, and local.
It is not a proof checker and cannot become one: obligations that do not fit descend to a consumer's own proof kernel as release-time proof terms (§4), which is the stratification's whole purpose.

---

## 2. The parameter: the machine profile

A target is described by a **machine profile** with two parts: the **machine semantics** the derivation is stated against, and the **cited invariant set**, the properties that semantics enforces at run time with no cooperation from the type system.

For every obligation in §4 a profile declares exactly one discharge route:

| Route | Meaning | Cost |
| --- | --- | --- |
| **Cited** | The machine enforces it; the derivation records which invariant it relies on and the checker inspects that reliance. | None at check time; no additional *software* check at run time, the machine's own checks still executing. |
| **Attributed** | The type system decides it statically as a §5 attribute. | Check time only. |
| **Inserted** | The producer emits an ordinary run-time check and the type system requires that check to dominate every access it guards. | Run time. |

The routes are ordered by preference and the ordering is the design: a cited invariant costs no software, an attributed one is paid once at admission, and an inserted one is paid on every execution forever.

**Two profiles are specified, and they differ by exactly one line of the table.**

- **`cheri-rv64`**, the profile VerifiedOS pins.
  Bounds, tags, monotone derivation, and sealed entry are architectural, so spatial memory safety and no-runtime-codegen are **cited**, capability integrity constrains which authority may be executed and where an entry may land, and the type system carries only the residual the hardware does not enforce: temporal safety, exclusive access, and typed control flow.
  Control-flow integrity is the easiest of these to overstate, and the split is worth naming: the machine bounds executable authority and entry, while the legal target set of an indirect transfer and the signature of the code it reaches stay **attributed**, a type match being a policy no instruction set states.
  This is the profile in which the language is small.
- **`bare-rv64`**, the profile with no capability hardware.
  Nothing is cited.
  Spatial safety becomes **inserted** (bounds checks the type system locates and requires) or, at the producer's option, a fat-pointer ABI in which a bounds pair is an ordinary aggregate the type fixes the representation of.
  Provenance survives as an **attributed** property, because the integer-to-capability deletion (§3) is already a type-system fact rather than a hardware one.

**A citation is a theorem about the machine, and citing carelessly is the likeliest way for everything downstream of it to be wrong.**
The capability literature is explicit about the qualifications, and a profile's declaration is defective if it does not carry them.
Compressed capability encodings admit **inexact bounds**, so a cited spatial-safety invariant holds up to the representable-region rounding the encoding defines rather than to the byte the source intended.
Monotone derivation has **privileged and transition cases**, the instructions and states in which authority is installed rather than narrowed, and a citation must name them rather than quantify over the whole machine.
Capability hardware does not by itself supply **temporal safety, exact callee sets, or ABI conformance**, and its immutable-code guarantee is conditional on an initial capability distribution from which no writable-and-executable authority is derivable, which is a property of the loader rather than of the instruction set.
`cheri-rv64` therefore declares, beside the four architectural facts above, the execution-mode, loader, privilege, and memory-permission assumptions under which they hold, and every one of those is a premise the profile's soundness instantiation (§6) discharges rather than assumes.

**What a bare profile does not recover, and the specification says so rather than implying otherwise.**
A cited invariant holds against *arbitrary co-resident code*, because the machine checks every access whoever issued it.
An attributed or inserted one holds only while everything in the address space is well-typed.
The guarantee is therefore **open-world** under `cheri-rv64` and **closed-world** under `bare-rv64`, and no amount of type-system work closes that gap: it is the difference between a machine that checks and a machine that was persuaded.
A consumer running unverified native code beside admitted code needs a cited profile or an isolation mechanism outside this language.

**The route that is refused.**
Spatial safety by **index refinement** (dependent or singleton types over lengths, the DTAL and Xanadu line) is not an admissible fourth route, because deciding it requires arithmetic constraint solving over open terms.
That would violate §3's absence (2) directly, turn the checker from an attribute evaluator into a solver, and falsify the category claim §1 rests on.
Refusing it is what keeps every profile's checker the same *kind* of artifact, differing in the size of its attribute set and never in what it must decide.

**Profiles are frozen and versioned like the theory.**
A profile is admitted only on a shown demonstration that every obligation has a route, that each cited invariant is a theorem of the machine semantics rather than a claim about an implementation, and that each inserted check has a stated placement rule the attribute evaluator can confirm.

---

## 3. The frozen theory

The type theory is fixed and closed by this document, and the four absences below are what make the check a dataflow validation rather than proof checking:

1. **Predicative, rank-1 prenex polymorphism.**
   Type variables are quantified only at the outermost position of a code type and instantiated only at monotypes: the classical TALx86 use (polymorphism over callee-saved registers and stack tails) and no more.
   Instantiation is first-order substitution, so there is no impredicative self-instantiation to justify and no rank-*n* inference to decide.
2. **No type-level computation.**
   Type equality is syntactic, α-equivalence over first-order terms, decided by structural comparison and not by conversion: no βδιζη-reduction, no normalizer, no evaluation of open terms, and therefore no strong-normalization premise inside the checker.
   This is the largest deletion and the one that makes termination syntactic rather than a metatheoretic side condition the admission axiom would have to carry.
3. **No universes and no universe polymorphism.**
   One sort of types, no cumulativity, no universe-constraint graph and no acyclicity solver.
4. **No user-extensible inductive definitions.**
   The type constructors are a fixed, closed vocabulary: capability or pointer types with their bounds, permissions, revocation colour, and initialization flag; code types as register-file preconditions carrying the callee set at indirect transfers; the aggregate and existential formers an ABI needs; the linear, affine, and relevance grades; the taint labels; and the cost annotations.
   There is no positivity check, no guard condition, and no eliminator generation, and the vocabulary grows by amendment to this document, never at install time.

**What makes the four load-bearing is what they delete from a checker.**
A term checker for a full calculus of inductive constructions spends its tens of thousands of lines on four hard structures: universe constraints, conversion, positivity, and the guard condition.
The absences above are precisely the deletion of those four, so what remains is not a small dependent-type checker but *not a dependent-type checker at all*, and the line budget is a consequence of that rather than a target an implementation is asked to hit.
What the checker does instead is evaluate a fixed attribute set over the already-typed control-flow graph (the type under structural equality, the threaded linear context, the taint lattice, the cost semiring, the callee set), taking the abstract state at each join from the derivation rather than computing it, and confirm each *local* constraint: tens of lines of evaluator per attribute.

**What the figure counts, so the budget is auditable rather than rhetorical.**
It counts the attribute evaluator, the derivation reader, and the image scan, together, in the shipped source of the checker.
It excludes the frozen type-constructor vocabulary and the attribute tables (data fixed by this document, whose size is bounded by amendment rather than by implementation), a consumer's own proof kernel (a separate checker with its own budget), and the metatheory.
A checker that met the figure by moving decisions into a generated table would fail the claim, the category fact being what the budget actually asserts.

**Every rider is shown to fit the theory rather than assumed to, which is the point of stating the theory at all.**
Memory safety and control-flow integrity are register-file preconditions over capability or pointer types, and first-order.
The linear and affine discipline and the relevance grading are context-splitting side conditions decided structurally.
Absence of ambient mutable state is decided by inspecting the image's static data for a set tag.
The callee set is a finite collection of first-order code labels whose membership test is structural set comparison, so it refines an existing former by amendment (absence (4)'s own reserved mechanism) rather than adding a grade axis.
The initialization flag is a two-point meet-semilattice riding the capability-type former over the slots the consumer's memory plan already fixes, the oldest attribute in the lineage and structurally the same table lookup, and taint is a join in a two-point lattice, another one.
The representation and provenance rules add no former and no grade at all, four of the five being *absences* the checker confirms by inspecting a derivation it already builds.
The three grade re-uses add nothing either: *use-once* is the linear grade the context-splitting side condition already runs, *must-erase* is its relevance polarity, and a *dimension* is a phantom parameter under absence (2)'s syntactic type equality, inhabited by no term and erased before code generation.

**The amendment rule.**
A proposed attribute is admitted only on a *shown* demonstration that it (1) has a finite semilattice or monoid domain decided with no open-term reduction and preserves syntactic type equality, (2) duplicates no existing grade or label axis, and (3) has a local, syntax-directed rule.
A feature that fails is not lost: it descends to the consumer's proof kernel as a release-time proof term, at the price of ceasing to be per-install checkable.

**One computation is permitted and its boundary is stated.**
Cost annotations require adding and comparing literal naturals along a max-path sum, and overflow side conditions require comparing literal bounds at each arithmetic rule.
Both are bounded-width arithmetic over *closed numerals* decided in constant time per node: computation, but not the reduction of open terms absence (2) forbids.
Anything needing the latter is not a type-level obligation, which is why overflow-freedom over a run-time-dependent bound descends rather than widening the theory to hold it.

**The theory binds the checker, not the producer.**
A certifying compiler may be written in, and reason with, whatever theory it likes; only the shipped derivation must be checkable in this one.

---

## 4. The obligations the language can carry

The language offers a **menu**, and a consumer requires a subset of it.
This document says what is expressible and decidable; the consumer's own specification says what it demands, so the two cannot come to disagree about a list.
VerifiedOS requires eleven of these, canonically enumerated at R-05-029 of its register.

Memory safety (spatial and temporal), definite initialization, data-race freedom, control-flow integrity in both its run-time and callee-set-enumeration halves, no-runtime-codegen, type and ABI conformance, examined verdicts (relevance grading), absence of ambient mutable state, representation and provenance conformance, secret-taint constant-time, and worst-case execution cost.

Two of these are boundary cases worth naming, because a reader who knows the literature will expect them to be proof obligations:

- **Constant-time** is a 2-safety hyperproperty, which a type system cannot state in general, but the CT-Wasm result makes it a **taint-typing** obligation for structured code: secret-labeled values the type system forbids from reaching a branch condition, a memory address, or a variable-latency operation.
  Only the genuinely unstructured residual descends to a relational proof.
  The guarantee is relative to the profile's declared **leakage model** rather than absolute, and it does not survive a lowering the type system never sees, which is exactly why the obligation is stated over final code rather than over a source or intermediate form (§8).
- **Worst-case cost** is a quantitative property, but for structured code it is a syntax-directed max-path sum over the already-typed control-flow graph (Shaw's timing schema), carried as a cost annotation rather than produced by a separate analyzer.
  The sum is sound only given supplied loop and recursion bounds, the path facts that exclude infeasible worst cases, and a machine cost model in which per-instruction costs actually compose: caches, pipelines, speculation, interrupts, and shared resources each falsify that composition, so a profile that neither deletes nor bounds them owes an inserted-route argument rather than an attributed one.

What the language does **not** carry, at any profile, is the deep tier: functional refinement, whole-system non-interference, cryptographic reduction security, and linearizability or liveness.
No decidable type system states these, and pretending otherwise is how a type system becomes a prover.

**The menu is not a routine consequence of having finite attribute domains, and the hard cases are known in advance.**
Temporal safety over a real allocator, data-race freedom under a weak memory model, cost over a genuinely unstructured control-flow graph, and constant-time preserved down to native code are the four places where the soundness argument is hard, independently of how small the checker is.
A profile or an instantiation that presents any of them as a small case of §5's move II has mislabeled its own difficulty, and the schedule that follows will be wrong in the same proportion.

---

## 5. The three moves

The checker handles the whole menu with exactly three moves, and the profile of §2 decides which obligations reach which:

| Move | What the checker does | Why it stays small |
| --- | --- | --- |
| **I. Cite a run-time invariant** | Confirms the derivation records reliance on an invariant the profile declares architectural. | It does not re-prove the machine's fact; it inspects the reliance. |
| **II. Evaluate an attribute** | Runs a local, syntax-directed attribute pass over the typed control-flow graph, taking the abstract state at each join from the derivation and confirming the linear contexts agree there. | Each attribute has a finite domain and a local rule, and the derivation supplies the joins a fixpoint would otherwise have to find. |
| **III. Confirm a deletion** | Checks that constructs which would make the static account lie are absent. | These are one-pass inspections of absences: no integer-to-pointer construction, no type punning, no variadic arity, no unbounded recursive former, no implicit conversion. |

Move I is empty in a profile that cites nothing, which is the precise sense in which a bare target is more expensive than a capability one: the same obligations survive, and they move rightward through the §2 table.

The word *attribute* is Knuth's, and the analogy is deliberately partial: an attribute grammar decorates a tree, while a machine-code control-flow graph is cyclic, which is precisely why the derivation carries the abstract state at every merge and the checker validates rather than solves (§1).

---

## 6. Soundness

The metatheorem is **well-typed implies safe**, stated over the machine semantics of a profile: a well-typed program's every execution satisfies the obligations its derivation claims, in the foundational-TAL, RustBelt, and WasmCert-Coq lineage.

It is **parameterized over the profile and discharged per instantiation**.
The core carries every proof obligation that does not mention the machine; a profile discharges the rest by supplying, for each cited invariant, a theorem of its own machine semantics, and for each inserted check, a domination argument.
So a second profile does not re-open the whole proof, but neither is it free: it owes exactly the machine-dependent cases, and a profile that cites an invariant its semantics does not actually enforce produces a proof about a machine nobody built.

The metatheorem is the language's *main trusted theorem*, and freezing the theory bounds its size just as it bounds the checker's: the two shrink together.
Calling it the single axiom would understate the base, and the honest list is short but longer than one: a consumer also trusts the machine semantics and its correspondence to the silicon that runs it, the profile's cited invariants, the decoder that recovers instructions from the image, the loader and initial-state model the derivation is stated against, and the implementation of the checker itself.
The claim worth making is that this list is small, fixed, and separately reviewable, not that it has one element.
A mis-stated typing rule admits an unsafe binary that type-checks perfectly, exactly as a wrong specification verifies perfectly, which is why this is a specification worth reviewing rather than a proof worth trusting.

---

## 7. Producers

**Admission gates on the derivation, never on the producer.**
Any producer of a well-typed binary is admissible by definition, and a consumer's reference compiler is a reference rather than a gate.

**A producer may be built on an existing unverified toolchain, and should be.**
The practical shape is **hinted mirroring**: the untrusted compiler records hints through lowering and a small trusted replayer reconstructs the derivation the checker re-validates.
That is a small replayer plus an arbitrary producer, not a whole-compiler preservation proof, and it is why an LLVM backend is a reasonable way to build one.
The precedent is Necula and Lee's certifying compiler and, closer to this shape, **Crellvm**, in which an untrusted optimizer emits hints a verified checker reconstructs and validates; Crellvm covered selected intermediate-representation optimizations rather than native code generation, so it supports the architecture without completing it (§9).

**What that does not buy is language-independence of the guarantee, and the distinction is the important one.**
A compiler intermediate representation carries none of the facts the derivation asserts: ownership, lifetime, exclusivity, initialization, taint, dimension, and callee sets come from the *source* type system, not from the lowering.
A fact the source never established cannot be preserved by anything downstream.

So a source language is admissible on one of three terms, and it is worth being explicit about which:

1. **It establishes the facts itself** (an ownership discipline, a synchronous dataflow language, a proof assistant's term language, or verified C with its own proofs), in which case the producer preserves them and the derivation is cheap.
2. **It accepts insertion**, in which case the producer emits run-time checks and the type system requires them, exactly as the `bare-rv64` profile does for bounds: the guarantee holds, and it is paid for on every execution.
3. **It ships a source-level proof** elaborated into a semantics the consumer already reviews.

A language that does none of the three is not admitted, and no backend choice changes that.
This is the same fact as §2's profile table seen from the other end: when an invariant is not supplied by the environment, the language must demand a proof or insert a check, and it makes no difference whether the environment that failed to supply it was the hardware or the source language.

---

## 8. What this is not

- **Not an isolation mechanism.** Its guarantee is over admitted code; a system that runs anything else needs hardware or a supervisor, and under a bare profile that is not optional (§2).
- **Not an intermediate representation.** It types final machine code against a machine semantics, so a target needs an ISA semantics of the quality of a Sail model before it can have a profile at all.
  That this is achievable rather than aspirational is the RockSalt and Islaris result: a decoded binary image checked against a machine model proved sound in a proof assistant, and binary machine code reasoned about against full Sail-derived semantics (§9).
- **Not a proof system.** The deep tier stays with a proof kernel (§4), and every proposal to move an obligation inward is decided by §3's amendment rule rather than by appetite.
- **Not a safety claim about a source language.** It carries facts; it does not manufacture them (§7).

---

## 9. Prior art

The design is a synthesis of several mature lines rather than an instance of any one of them, and the honest way to read it is as an assembly whose parts are each well precedented and whose *combination* is not.

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

**Final machine code.**
Morrisett et al., *RockSalt* (PLDI 2012); Sammler et al., *Islaris* (PLDI 2022); Armstrong et al., *ISA Semantics for ARMv8-A, RISC-V, and CHERI-MIPS* (POPL 2019).
RockSalt parses a real binary image and applies a generated checker proved sound against a machine model; Islaris verifies binary machine code against full Sail-derived Arm and RISC-V semantics.
Together they are the precedent for the seam this language stands on, final bytes against an authoritative machine semantics (§8).

**Capability machines.**
Watson et al., the CHERI ISA specification (University of Cambridge technical report); the CHERI-RISC-V Sail model; Nienhuis et al., *Rigorous Engineering for Hardware Security* (S&P 2020).
These are what a citing profile cites (§2): tagged capabilities, bounds, permissions, sealing, provenance validity, and guarded monotone derivation.
Their published qualifications, inexact compressed bounds and the privileged and transition cases of monotonicity, are what a profile's declaration must state rather than gloss.

**Linear control and ownership.**
Skorstengaard, Devriese, and Birkedal, *StkTokens* (POPL 2019); Crary, Walker, and Morrisett, *Typed Memory Management in a Calculus of Capabilities* (POPL 1999); Smith, Walker, and Morrisett, *Alias Types* (ESOP 2000); Jung et al., *RustBelt* (POPL 2018).
StkTokens is the direct precedent for a linear capability discipline proving well-bracketed control flow and stack encapsulation.
It does not establish general heap temporal safety on ordinary capability hardware, which is why the revocation discipline of §4 owes an allocator-and-reuse theorem of its own (§6) rather than inheriting one.

**Constant-time typing.**
Watt et al., *CT-Wasm* (POPL 2019); Barthe et al., *System-level Non-interference for Constant-time Cryptography* (CCS 2014); Almeida et al., *Verifying Constant-Time Implementations* (USENIX Security 2016).
CT-Wasm is the direct precedent for §4's taint-typing route, mechanized through semantics, checker, and soundness together, and its guarantee is relative to an explicit leakage model rather than absolute.

**Cost certificates.**
Shaw, *Reasoning About Time in Higher-Level Language Software* (TSE 1989); Li and Malik, implicit path enumeration (1995); Carbonneaux et al., *Automated Resource Analysis with Coq Proof Objects* (CAV 2017).
These support compositional timing annotations and independently checked resource bounds, under exactly the side conditions §4 states and not otherwise.

**Certifying compilation.**
Necula and Lee, *The Design and Implementation of a Certifying Compiler* (PLDI 1998); Kang et al., *Crellvm* (PLDI 2018); the translation-validation and CompCert lines.
Crellvm is the closest match to §7's hinted mirroring, over selected intermediate-representation optimizations rather than native code generation.

**What is not precedented is the assembly.**
Not typed assembly language, not proof-carrying code, not capability typing, not taint typing, and not resource certificates, each of which is someone else's result.
The combination is: a fixed, non-extensible certificate language carrying all of them at once, assigning every obligation an explicit cited, attributed, or inserted discharge against a *versioned machine profile*, and checking final decoded machine code without invoking a general proof kernel at install time.
That is a claim about the arrangement rather than about any component, and it is the part a reviewer should attack first.

---

## 10. Status and honest accounting

Unbuilt, in all three parts: the type system, the checker, and the soundness proof.
The prior art it stands on is real and mechanized and is set out in §9, so the *type-soundness discipline* is not a gamble; the instantiation is.
One caution about the closest mechanized soundness result of this shape: WasmCert-Coq mechanizes WebAssembly's semantics, binary format, typing, and type soundness, but for a *bytecode* rather than a native instruction set, and its published account left end-to-end work unfinished, so it is a template for the metatheorem's shape and not evidence that the same has been carried out over an ISA semantics.

Factoring it out of an operating-system specification changes three things and no others:

1. **The review surface improves.** The language can be reviewed, and its soundness proof read, by someone who has no opinion about capability operating systems.
2. **The cost becomes shareable.** A second consumer at a different profile pays for its own machine-dependent cases and shares the core.
3. **A version seam appears where a freeze used to be.** A theory frozen inside one document is frozen by that document's amendment process; a theory frozen in a dependency is frozen by a pin, and a consumer that fails to re-review on a version bump has silently widened its own axiom.

None of these is a reduction in the work, and the first consumer's schedule is unchanged by the factoring.
