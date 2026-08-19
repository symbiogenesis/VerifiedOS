# The Typed Assembly Language

> **What this is.**
> This document specifies the typed machine-code language, and its admission check, that [VerifiedOS](spec.md) uses to admit binaries.
> It is factored into a project of its own because it depends only on a machine semantics and a type theory. It does not depend on a kernel, storage stack, authority model, or hardware beyond the target's instruction semantics.
>
> **Normative for the language; not a derived view.**
> The [frozen instruction-set profile](isa-profile.md), the [absence contract](absence-contract.md), the [crown-jewel inventory](crown-jewels.md), and the [coverage matrix](coverage-matrix.md) are derived views of [requirements-register.md](requirements-register.md) and state no obligation of their own.
> This document is different: it states the language's obligations, as numbered requirements carrying acceptance criteria. VerifiedOS depends on one instantiation and pins its version.
> If this document and the register disagree about VerifiedOS requirements, the register governs. If they disagree about the language itself, this document governs.
>
> **How to read it.**
> Sections 1 to 15 are normative. Every obligation is a numbered `TAL-` requirement; the prose around them is rationale and binds nothing.
> Appendices A to D are not normative: they record where the design comes from, what it cites, what the artifact landscape looked like on a stated date, and the order in which the normative content must be settled.
> A reference of the form §n names a section *of this document*. References to other documents are links.
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

This is a **typed assembly language** in the Necula and Morrisett lineage: final machine code carries a **typing derivation**, which is checked before the code may run.

Three commitments distinguish this language from that lineage.

- **The check is certificate-directed dataflow validation, not proof checking.**
  The checker decides a fixed set of attributes over an already-typed control-flow graph. The derivation supplies the abstract state at every join, so certificate consumption requires neither fixpoint computation nor reduction of open terms.
  A producer may use any fixpoint analysis it chooses to compute those annotations; the no-fixpoint property is a property of consumption alone (§12).
  This is a claim about the *kind* of checker being specified. The complexity contract (§10.3) and the audit budget (§10.6) follow from that classification rather than standing as independent targets.
- **The theory is frozen, and freezing it is the mechanism.**
  A line budget does not constrain an unspecified theory. What the checker must decide is fixed in §7, and the cost of deciding it follows.
- **The target's own guarantees are a parameter, not an assumption.**
  A machine profile declares which machine-enforced invariants the derivation may *cite* instead of re-proving (§5).

**TAL-001** IS: The admission check is a total, deterministic decision procedure over an installed artifact and a certificate, returning accept or reject.
· Accept: the checker returns exactly one verdict on every input, including malformed ones; two runs over identical inputs return identical verdicts and identical rejection sites.
· Trace: §10.4, §10.2

**TAL-002** IS: The check is per-install, decidable, syntactically terminating, and local: every rule mentions one instruction, one edge, or one declared record, and no rule quantifies over executions.
· Accept: every rule in §8.4, §8.5, and §8.6 has premises drawn from a bounded neighbourhood fixed by the rule, and termination follows from the traversal order in §10.2 without a well-foundedness argument about types.
· Trace: §8.4, §10.2

**TAL-003** MUST NOT: The checker is not a proof checker and may not acquire the capability to become one: it performs no unification, no constraint solving, no search, and no reduction of open terms.
· Accept: the shipped checker contains no solver, no normalizer, and no backtracking; every decision is a table lookup, a structural comparison, or bounded-width arithmetic over closed numerals (§7.6).
· Trace: §7.1, §10.3

**TAL-004** IS: Obligations that do not fit the frozen theory are not carried by this language; they descend to the consumer's proof kernel as release-time proof terms.
· Accept: §4.5's deep tier appears in no profile's route table, and every amendment rejected under §7.5 is recorded as descending rather than as lost.
· Trace: §4.5, §7.5

---

## 2. Normative form

### 2.1 Requirements

**TAL-005** IS: Every obligation of this document is a numbered requirement of the form `**TAL-nnn** MUST | MUST NOT | IS:` followed by one `· Accept:` acceptance criterion and one `· Trace:` line naming the formal rules or sections that carry it.
· Accept: no normative obligation appears in unnumbered prose; every numbered requirement carries both tail lines.
· Trace: §2.2

**TAL-006** IS: Requirement identifiers are permanent and independent of section numbering. A retired requirement is struck in place and its identifier is never reused.
· Accept: no identifier names two statements across versions; renumbering a section renumbers no requirement.
· Trace: §2.3

**TAL-007** IS: `MUST` and `MUST NOT` state obligations on an implementation, a profile, or a certificate. `IS` states a definitional fact of the language that other requirements cite rather than restate.
· Accept: no `IS` entry imposes an obligation that no `MUST` entry also states, and no list is enumerated in two places.
· Trace: §4.1

### 2.2 Roles

The specification names five roles, and every requirement binds one of them.

| Role | What it is | What binds it |
| --- | --- | --- |
| **Producer** | Whatever emits an artifact and its certificate | §12 |
| **Consumer** | Whatever runs the checker and decides admission policy | §5.5, §11.2 |
| **Checker** | The shipped admission program | §10 |
| **Profile** | The machine parameter: semantics, cited set, rule table, limits, ledger | §5 |
| **Certificate** | The producer-supplied derivation and its bindings | §8 |

### 2.3 Versioning and precedence

**TAL-008** MUST: A certificate names the version of this specification and the version of the profile it was produced against, and a checker rejects a certificate naming a version it does not implement.
· Accept: version fields are mandatory in the certificate header (§8.1); no checker accepts an unpinned or unknown version.
· Trace: §8.1, §9.4

**TAL-009** MUST: An amendment to this document, to a profile, or to a rule table is a version bump that invalidates no prior verdict and revalidates no prior artifact: a consumer that bumps a version re-checks every artifact it admits under the new version.
· Accept: verdicts record the version pair they were produced under; no verdict is carried across a bump.
· Trace: §7.5, §9.4

---

## 3. Definitions

The terms below are load-bearing in the soundness statement, so each is fixed here rather than left to its intuitive reading. Appendix A records the literature these readings come from.

**TAL-010** IS: The definitions of this section are the meanings every other section uses.
· Accept: no requirement elsewhere redefines a term defined here.
· Trace: §3

- **Artifact.** The installed bytes: the code-and-rodata image, its data initializer, its layout, its entry-point set, and the immutable tables the profile names. Admission is over the artifact, never over an assembly listing or an intermediate representation (§9.3).
- **Certificate.** The producer-supplied record binding a typing derivation to one artifact (§8.1).
- **Derivation.** The typing content of a certificate: types, block entry states, guard records, loop and call structure, and citations.
- **Facet.** An atomic obligation, the unit that carries exactly one discharge route (§4.2).
- **Route.** How a facet is discharged: cited, attributed, or inserted (§5.2).
- **Move.** What the checker does about a facet: cite an invariant, evaluate an attribute, or confirm a deletion (§10.1).
- **Well-typed.** The checker accepts the artifact and certificate under a profile. *Safe* is not a synonym: an artifact is safe with respect to the facets its profile routes and the ledger its profile consumes, and with respect to nothing else (§11.5).
- **Memory safety.** Two facets, never one. *Spatial*: every memory access lies within the bounds and permissions of the authority it derives from. *Temporal*: no access uses authority over a storage object outside that object's lifetime.
- **Control-flow integrity.** Two facets. *Run-time*: every control transfer targets authority the profile declares executable and lands at a valid entry. *Callee set*: every realized target of an indirect transfer is a member of the finite set the derivation declares at that transfer site.
- **Constant-time.** Non-interference of a declared leakage model from secret-labeled inputs: no secret-labeled value reaches a branch condition, a memory address, or an operand of a variable-latency operation. The obligation is relative to the profile's declared leakage model and to nothing stronger.
- **Local (of a rule).** Its premises mention only the instruction being typed, the states the certificate records for that instruction's block and its successors, and records the certificate declares for that site.
- **Structured (of code).** Its control-flow graph is reducible, every back edge names a header the certificate declares, and every loop carries a trip bound (§8.5).
- **Open-world (of a guarantee).** It holds against arbitrary co-resident code, subject only to the machine premises its ledger names.
- **Address-space-closed.** It holds while every instruction stream with authority over the same objects is admitted under this language.
- **Image-local.** It is a property of the admitted bytes alone and is unaffected by what else executes.
- **Premise.** A statement the checker validates the form of and does not decide, exposed in the verdict (§5.5, §8.7).

---

## 4. The obligation menu and its facets

### 4.1 The menu

The language defines a **menu** of obligations; each consumer selects the subset it requires.
This document says what is expressible and decidable; the consumer's own specification says what it demands, so the two cannot come to disagree about a list.

**TAL-011** IS: The menu is exactly these eleven obligations:

1. Memory safety, spatial and temporal.
2. Definite initialization.
3. Data-race freedom.
4. Control-flow integrity, run-time and callee-set.
5. No run-time code generation.
6. Type and ABI conformance.
7. Examined verdicts through relevance grading.
8. Absence of ambient mutable state.
9. Representation and provenance conformance.
10. Secret-taint constant-time behavior.
11. Worst-case execution cost.

· Accept: no other section of this document enumerates the menu; §4.2 partitions it and cites this entry.
· Trace: §4.2

VerifiedOS requires all eleven, canonically enumerated at R-05-029 of its register, and its lower assurance tier scopes a stated subset of the same list rather than a list of its own.

### 4.2 The facets

The eleven rows are the user-facing grouping. They are not the unit of routing, because a profile may discharge the halves of one row differently: on capability hardware the machine enforces spatial safety and not temporal safety, and enforces where an indirect transfer may land but not which callee is legal there.

**TAL-012** IS: The unit of routing is the **facet**. The fifteen facets below partition the eleven menu rows; no facet belongs to two rows, and every row has at least one facet.

| Facet | Row | Statement |
| --- | --- | --- |
| `mem.spatial` | 1 | Every memory access lies within the bounds and permissions of the authority it derives from. |
| `mem.temporal` | 1 | No access uses authority over a storage object outside that object's lifetime. |
| `init.definite` | 2 | No read observes a location that no preceding write on the same path has written. |
| `race.freedom` | 3 | No two concurrent accesses to one location, at least one a write, occur without the profile's declared ordering between them. |
| `cfi.runtime` | 4 | Every control transfer targets authority the profile declares executable and lands at a valid entry. |
| `cfi.callee-set` | 4 | Every realized target of an indirect transfer is in the finite callee set the derivation declares at that site. |
| `codegen.none` | 5 | No byte that was writable after admission is ever executed, and no authority is both writable and executable. |
| `abi.conform` | 6 | At every transfer the register file, stack, and argument layout satisfy the target's declared code type. |
| `verdict.relevance` | 7 | No value of a relevance-graded type is discarded without the use its grade requires. |
| `ambient.static-authority` | 8 | The image embeds no authority in static data. |
| `ambient.rooted-mutability` | 8 | Every writable object any execution reaches is reachable from the enumerated initial capability set and mutable-root table. |
| `repr.conform` | 9 | Representation is fixed by type: no punning, no implicit conversion, no variadic arity, no unbounded recursive former. |
| `prov.integrity` | 9 | No pointer or capability arises except by monotone derivation from one already held. |
| `ct.taint` | 10 | No secret-labeled value reaches a branch condition, a memory address, or a variable-latency operand, under the profile's leakage model. |
| `cost.wcet` | 11 | Every entry point's execution cost is at most the derivation's declared bound under the profile's cost model. |

· Accept: fifteen facets, each naming one of the eleven rows; the profile matrix (§6) has one line per facet per profile and no line for a row.
· Trace: §6.2, §6.3

**TAL-013** MUST: A profile declares exactly one route for every facet of every row its consumer selects. A row is never routed; its facets are.
· Accept: a profile whose route table has a row-level entry, a missing facet, or two entries for one facet is inadmissible under §5.8.
· Trace: §5.2, §5.8

**TAL-014** MUST: Facets are the unit of amendment as well as of routing. Splitting a facet, merging two facets, or adding one is a version bump under TAL-009 and requires every profile to restate its routes for the affected facets.
· Accept: no profile is carried across a facet change without restating the affected rows of its matrix.
· Trace: §7.5

### 4.3 Two obligations that need explanation

The literature usually treats these two as proof obligations rather than as type-level ones, so the ground for carrying them here is stated.

- **Constant-time** is a 2-safety hyperproperty, which a type system cannot state in general, but the CT-Wasm result makes it a **taint-typing** obligation for structured code: secret-labeled values the type system forbids from reaching a branch condition, a memory address, or a variable-latency operation.
  Only the genuinely unstructured residual descends to a relational proof.
  The guarantee is relative to the profile's declared leakage model rather than absolute, and it does not survive a lowering the type system never sees, which is why the obligation is stated over final code rather than over a source or intermediate form (§14).
- **Worst-case cost** is a quantitative property, but for structured code it is a max-path sum over the certificate's declared loop nest (Shaw's timing schema), carried as a cost attribute rather than produced by a separate analyzer.
  The sum is sound only given the declared trip and depth bounds of §8.7 and a machine cost model in which per-instruction costs compose: caches, pipelines, speculation, interrupts, and shared resources each falsify that composition, so a profile that neither deletes nor bounds them owes an interference premise in its ledger (§5.5) rather than silence.

### 4.4 What the language does not admit as evidence

**TAL-015** MUST NOT: No facet is discharged by a path-feasibility fact, an infeasible-path exclusion, or any other input whose only effect is to tighten an already-sound result.
· Accept: no rule in §8 consumes a path fact; the cost attribute reads trip bounds and call-depth bounds and nothing else. This is the language-level form of the consumer-side no-tightening rule at R-05-105.
· Trace: §8.7, §10.3

**TAL-016** MUST NOT: No facet is discharged by producer identity, by a signature over the artifact, by a build record, or by any property of the pipeline that produced it.
· Accept: the checker reads the artifact, the certificate, and the profile, and nothing else; removing every producer attestation changes no verdict.
· Trace: §12

### 4.5 The deep tier stays out

**TAL-017** IS: No profile routes functional refinement, whole-system non-interference, cryptographic reduction security, linearizability, or liveness. These are outside the decidable type system and remain proof obligations for a consumer's proof kernel.
· Accept: no route table names them; each appears in the consumer's release-time obligation set.
· Trace: §4.4, §7.5

### 4.6 The hard cases are named in advance

The menu is not a routine consequence of having finite attribute domains.
Temporal safety over a real allocator, data-race freedom under a weak memory model, cost over a genuinely unstructured control-flow graph, and constant-time preserved down to native code are the four places where the soundness argument is hard, independently of how small the checker is.
A profile or an instantiation that presents any of them as a small case of move II has mislabeled its own difficulty, and the schedule that follows will be wrong in the same proportion.

---

## 5. The parameter: the machine profile

### 5.1 What a profile contains

**TAL-018** MUST: A profile supplies all nine parts: machine semantics, decode function, cited invariant set, per-facet route table, instruction rule table, resource limits, leakage model, cost model, and assumption ledger.
· Accept: a profile missing any part is inadmissible under §5.8; §5.6 fixes the schema.
· Trace: §5.6, §5.8

| Part | What it fixes | Consumed by |
| --- | --- | --- |
| Machine semantics | The transition relation the soundness theorem is stated over | §11 |
| Decode function | Bytes to instructions, as a function of image content and position | §9.2 |
| Cited invariant set | The machine theorems a derivation may cite | §10.1 move I |
| Route table | One route per facet | §5.2 |
| Instruction rule table | The typing rule for each decoded instruction form | §8.4 |
| Resource limits | The declared maxima the checker enforces before evaluating | §8.9 |
| Leakage model | What an adversary observes, for `ct.taint` | §3, §6 |
| Cost model | Per-instruction latencies and the interference premise | §4.3, §8.5 |
| Assumption ledger | Every premise the guarantee rests on, classified | §5.5 |

### 5.2 The three routes

| Route | Meaning | Check-time cost | Run-time cost |
| --- | --- | --- | --- |
| **Cited** | The machine enforces the facet. The derivation records the invariant it relies on, and the checker validates the citation. | One citation-record inspection per reliance site, constant per site. | None added by this language. The machine's own checks execute. |
| **Attributed** | The type system decides the facet statically, as an attribute (move II) or as a deletion (move III). | Bounded work per instruction and per edge (§10.3). | None. |
| **Inserted** | The producer emits an ordinary run-time check, and the checker requires a certificate-supplied guard record proving that check reaches every access it guards. | Guard-record validation, one attribute among the others. | The check executes on every guarded access. |

The route order is intentional. A cited facet adds no software enforcement; an attributed facet is decided once at admission; an inserted facet is paid on every execution.

**TAL-019** IS: Route and move are different axes. Cited is discharged by move I. Attributed is discharged by move II or move III. Inserted is discharged by move II over a guard record (§8.6), plus a run-time check that the machine executes.
· Accept: the matrix in §6 carries a route column and a move column, and every line's pair is one of the four combinations named here.
· Trace: §10.1, §8.6

**TAL-020** MUST NOT: There is no fourth route and no fourth move. A facet a profile can route in none of the three ways is not carried by that profile, and the profile is inadmissible until the facet is dropped from its consumer's selection or the profile is amended.
· Accept: no profile's matrix carries a route or move outside the two fixed vocabularies.
· Trace: §5.8

### 5.3 What each route requires of a profile

**TAL-021** MUST: For every cited facet, the profile names an invariant that is a theorem of its machine semantics, states the instruction classes and machine states over which the theorem holds, and names its exceptions explicitly rather than quantifying over the whole machine.
· Accept: each cited invariant has a proof obligation in §11.3 and an applicability class the checker tests each reliance site against.
· Trace: §11.3, §10.2

**TAL-022** MUST: For every inserted facet, the profile fixes the instruction pattern of the check, the failure transfer the check performs, and the guard-record form the derivation must supply.
· Accept: the checker recognizes the pattern structurally; a guarded access whose guard token is absent from its block's validated entry state is rejected.
· Trace: §8.6, §10.5

**TAL-023** MUST: For every attributed facet, the profile's rule table assigns a transfer rule to every decoded instruction form the artifact may contain, including the forms the language forbids, which the table maps to rejection.
· Accept: the rule table is total over the decode function's image; an instruction form with no rule is a profile defect, not a permissive default.
· Trace: §8.4, §10.2

### 5.4 Guarantee scope is per facet

A cited facet holds against *arbitrary co-resident code*, because the machine checks every access regardless of who issued it.
An attributed or inserted facet holds only while every instruction stream with authority over the same objects is admitted. No amount of type-system work closes that gap: it is the difference between a machine that checks and a machine that was persuaded.

**TAL-024** IS: Guarantee scope is a per-facet property with three values: `open-world`, `address-space-closed`, and `image-local` (§3).
· Accept: every line of every profile matrix carries a scope value; no profile states a single scope for itself.
· Trace: §6.2, §6.3

**TAL-025** IS: A profile's composed guarantee is the conjunction of its per-facet guarantees, and is therefore mixed-scope whenever its facets are.
· Accept: §6.2's summary states the composed scope as a partition of facets by scope, not as one word.
· Trace: §6.2

**TAL-026** MUST: A consumer that admits code under any facet whose scope is `address-space-closed` supplies the closure premise as consumer premise C1 of the profile's ledger, or supplies an isolation mechanism outside this language.
· Accept: the ledger names the premise, and the verdict exposes it; a consumer running unverified native code with authority over the same objects has not discharged it.
· Trace: §5.5, §11.2

### 5.5 The assumption ledger

**TAL-027** MUST: A profile publishes an assumption ledger classifying every dependency of its guarantee into exactly one of six classes.

| Class | Meaning | Discharged by |
| --- | --- | --- |
| **M** | A theorem of the machine semantics | The profile's soundness instantiation (§11.3) |
| **L** | A theorem of the loader and initial-state model | The profile's instantiation, against a stated loader model |
| **C** | A premise the consumer supplies | The consumer, outside this language |
| **S** | Correspondence between the semantics and the silicon | Nothing here; it is an assumption and is named as one |
| **O** | An operational condition on how the artifact is run | The consumer's deployment |
| **P** | A premise the certificate declares (§8.7) | The consumer's release-time proofs, per its own policy |

· Accept: every ledger entry has a class, a statement, and a discharge owner; no entry is unclassified, and no requirement elsewhere calls an S or O entry discharged.
· Trace: §11.2, §11.3

**TAL-028** MUST: The soundness statement of §11.1 names the ledger it consumes, and the checker's verdict reproduces the ledger entries of the profile it ran plus the premises the certificate declared.
· Accept: a verdict without a ledger is malformed; a consumer can read the whole assumption set off one accepted verdict.
· Trace: §10.4, §11.1

### 5.6 The profile schema

A profile is data, not prose. The narrative descriptions of §6 are generated from it.

```
profile        ::= id version semantics decode cited routes rules limits leakage cost ledger
cited          ::= (invariant-id statement applicability exceptions)*
routes         ::= (facet route move evidence scope lemma failure)*
rules          ::= (instruction-form judgment-id premises)*
limits         ::= (limit-id numeral)*
ledger         ::= (entry-id class statement owner)*
leakage        ::= (observable-class)*
cost           ::= (instruction-form latency)* interference-premise
```

**TAL-029** MUST: A profile is published in this schema, and its narrative form is derived from it rather than written beside it.
· Accept: the matrix in §6 and the profile data agree line for line, mechanically.
· Trace: §6.1

### 5.7 The route that is refused

Spatial safety by **index refinement** (dependent or singleton types over lengths, the DTAL and Xanadu line) is not an admissible fourth route, because deciding it requires arithmetic constraint solving over open terms.
That would violate §7.1's absence (2) directly, turn the checker from an attribute evaluator into a solver, and falsify the classification §1 rests on.

**TAL-030** MUST NOT: No profile routes a facet to index refinement, constraint entailment, or any discipline whose decision procedure reasons about open terms, however bounded.
· Accept: no rule table premise mentions a constraint, an entailment, or a solver call.
· Trace: §7.1, §7.5

This refusal is deliberate despite the existence of a bounded form. Wasm-precheck [GFB24] places an indexed-type discipline inside a linear-pass validator without an SMT solver. This language still declines that approach because even restricted constraint entailment decides propositions over open terms; the distinction is one of checker kind, not solver size.

### 5.8 Profiles are frozen and versioned like the theory

**TAL-031** MUST: A profile is admitted only on a shown demonstration that every facet has exactly one route, that each cited invariant is a theorem of the machine semantics rather than a claim about an implementation, that each inserted check has a stated placement rule the guard-record validator can confirm, that its rule table is total, and that its ledger is complete.
· Accept: five demonstrations exist per profile, and the conformance suite of §13 runs against it.
· Trace: §13, §11.3

---

## 6. The profile matrix

### 6.1 How to read it

Each profile has two tables over the same fifteen facets: what the checker consumes, and what the soundness argument owes. Together they are the profile's whole routing content; the paragraphs after them are qualifications, not additional routes.

**TAL-032** IS: This document specifies two profiles, `cheri-rv64` and `bare-rv64`. They differ only in routing: every facet cited by `cheri-rv64` moves to a lower route under `bare-rv64`, and no other line changes.
· Accept: the two matrices differ exactly on the lines whose `cheri-rv64` route is Cited.
· Trace: §6.2, §6.3

### 6.2 `cheri-rv64`

The profile VerifiedOS pins. Bounds, tags, monotone derivation, and sealed entry are architectural, so the type system carries only the residual the hardware does not enforce.

| Facet | Route | Move | Certificate evidence | Scope |
| --- | --- | --- | --- | --- |
| `mem.spatial` | Cited | I | Reliance record naming M1 at each access site's authority | open-world |
| `mem.temporal` | Attributed | II | Linear and affine grades on capability types; revocation colour in the type | address-space-closed |
| `init.definite` | Attributed | II | Initialization flag on each capability type, joined at block entry states | address-space-closed |
| `race.freedom` | Attributed | II | Exclusive-access grade threaded through the linear context | address-space-closed |
| `cfi.runtime` | Cited | I | Reliance record naming M3 and M4 at each transfer | open-world |
| `cfi.callee-set` | Attributed | II | Declared callee set at each indirect transfer, and rank in the call order | address-space-closed |
| `codegen.none` | Cited | I | Reliance record naming M4 | open-world, on L1 |
| `abi.conform` | Attributed | II | Code type at every label; register-file state at every transfer | address-space-closed |
| `verdict.relevance` | Attributed | II | Relevance grade in the linear context | image-local |
| `ambient.static-authority` | Attributed | III | Static-data extent table in the certificate | image-local |
| `ambient.rooted-mutability` | Attributed | III | Mutable-root table plus initial capability set, with a provenance chain per store site | address-space-closed |
| `repr.conform` | Attributed | III | Absence of the five forbidden forms in the decoded image and derivation | image-local |
| `prov.integrity` | Attributed | III | Every capability-producing site is a monotone derivation | image-local |
| `ct.taint` | Attributed | II | Taint labels in types; leakage-model class per instruction | address-space-closed |
| `cost.wcet` | Attributed | II | Loop nest, trip bounds, call order, per-block cost | address-space-closed, on P and O2 |

| Facet | Machine theorem or check pattern | Soundness lemma | Failure behavior |
| --- | --- | --- | --- |
| `mem.spatial` | M1: every capability-authorized access lies within the capability's representable bounds and permissions | SL-spatial-cited | Machine trap to the declared failure state |
| `mem.temporal` | None; the type system carries it | SL-temporal | Admission rejection |
| `init.definite` | None | SL-init | Admission rejection |
| `race.freedom` | None | SL-race | Admission rejection |
| `cfi.runtime` | M3: a transfer through a sealed entry lands at its declared entry offset; M4: no reachable authority is both writable and executable | SL-cfi-runtime | Machine trap to the declared failure state |
| `cfi.callee-set` | None | SL-callee | Admission rejection |
| `codegen.none` | M4, under loader premise L1 | SL-codegen | Machine trap to the declared failure state |
| `abi.conform` | None | SL-abi | Admission rejection |
| `verdict.relevance` | None | SL-relevance | Admission rejection |
| `ambient.static-authority` | Image scan: no tagged datum in any static data extent | SL-ambient-static | Admission rejection |
| `ambient.rooted-mutability` | Root enumeration plus provenance chains | SL-ambient-rooted | Admission rejection |
| `repr.conform` | Absence scan | SL-repr | Admission rejection |
| `prov.integrity` | M2: no capability arises except by monotone derivation from one held, outside the named privileged and transition cases | SL-prov | Admission rejection |
| `ct.taint` | None; relative to the declared leakage model | SL-ct | Admission rejection |
| `cost.wcet` | Cost model plus interference premise O2 | SL-cost | Admission rejection |

**Composed scope.** Three facets are open-world (`mem.spatial`, `cfi.runtime`, `codegen.none`, the last on loader premise L1); four are image-local (`verdict.relevance`, `ambient.static-authority`, `repr.conform`, `prov.integrity`); the remaining eight are address-space-closed. The composed guarantee is that partition and not a single word.

**Ledger.**

| Entry | Class | Statement |
| --- | --- | --- |
| M1 | M | Bounds and permission enforcement on every capability-authorized access |
| M2 | M | Tag integrity and monotone derivation, outside the named privileged and transition instructions |
| M3 | M | Sealed-entry transfer lands at the declared entry offset |
| M4 | M | No reachable authority carries both write and execute permission |
| L1 | L | The initial capability distribution contains no writable-and-executable authority and none over another compartment's objects |
| L2 | L | The image is loaded at the layout the certificate names, with the entry state the derivation declares |
| S1 | S | The silicon implements the machine semantics |
| O1 | O | Admitted code executes in the declared mode, never in a mode where M2 has an exception |
| O2 | O | Interference from caches, interrupts, and other bus masters is bounded by the cost model's declared interference bound |
| O3 | O | No bus master holds authority outside its declared capabilities |
| C1 | C | Every instruction stream with authority over the same objects is admitted under this language |
| C2 | C | The declared leakage model covers the microarchitecture's observable channels |
| P | P | The trip and depth bounds the certificate declares (§8.7) |

**The qualifications a citing profile must state.**
A citation is a theorem about the machine, and an unsound citation invalidates everything that depends on it.
Compressed capability encodings permit **inexact bounds**, so M1 holds for the rounded representable region defined by the encoding, not necessarily for the exact byte range the source intended; `mem.spatial` is stated over the representable region accordingly.
Monotone derivation has **privileged and transition cases**, the instructions and states in which authority is installed rather than narrowed, and M2 names them rather than quantifying over the whole machine.
Capability hardware alone provides no **temporal safety, exact callee set, or ABI conformance**, which is why those three facets are attributed here.
Its immutable-code guarantee rests on an initial capability distribution from which no writable-and-executable authority can be derived, which is a loader property, and appears as L1 rather than as a machine theorem.

### 6.3 `bare-rv64`

The profile with no capability hardware. It cites no invariant, so move I is empty and its checker is the same kind of artifact with a larger attribute set.

| Facet | Route | Move | Certificate evidence | Scope |
| --- | --- | --- | --- | --- |
| `mem.spatial` | Inserted | II | Guard record per access: guard site, guarded site, guard token in the entry state | address-space-closed |
| `mem.temporal` | Attributed | II | Linear and affine grades over the fat-pointer representation | address-space-closed |
| `init.definite` | Attributed | II | Initialization flag on each pointer type | address-space-closed |
| `race.freedom` | Attributed | II | Exclusive-access grade in the linear context | address-space-closed |
| `cfi.runtime` | Attributed | II | Typed jump at every transfer; no store site typed against a code region | address-space-closed, on L3 |
| `cfi.callee-set` | Attributed | II | Declared callee set and call order | address-space-closed |
| `codegen.none` | Attributed | II and III | No store typed against a code region; no code region writable in the layout | address-space-closed, on L3 |
| `abi.conform` | Attributed | II | Code type at every label | address-space-closed |
| `verdict.relevance` | Attributed | II | Relevance grade in the linear context | image-local |
| `ambient.static-authority` | Attributed | III | Static-data extent table; no static pointer datum outside the root table | image-local |
| `ambient.rooted-mutability` | Attributed | III | Mutable-root table plus a provenance chain per store site | address-space-closed |
| `repr.conform` | Attributed | III | Absence of the five forbidden forms | image-local |
| `prov.integrity` | Attributed | III | Every pointer-producing site is a derivation from a held pointer | image-local |
| `ct.taint` | Attributed | II | Taint labels; the profile's own leakage model | address-space-closed |
| `cost.wcet` | Attributed | II | Loop nest, trip bounds, call order, per-block cost | address-space-closed, on P and O2 |

| Facet | Machine theorem or check pattern | Soundness lemma | Failure behavior |
| --- | --- | --- | --- |
| `mem.spatial` | Inserted pattern: compare against the bounds pair of the fat pointer, branch to the failure state on violation | SL-spatial-inserted | Run-time transfer to the declared failure state |
| `mem.temporal` | None | SL-temporal | Admission rejection |
| `init.definite` | None | SL-init | Admission rejection |
| `race.freedom` | None | SL-race | Admission rejection |
| `cfi.runtime` | None; typed transfers plus loader premise L3 | SL-cfi-runtime | Admission rejection |
| `cfi.callee-set` | None | SL-callee | Admission rejection |
| `codegen.none` | None; loader premise L3 supplies the read-execute mapping | SL-codegen | Admission rejection |
| `abi.conform` | None | SL-abi | Admission rejection |
| `verdict.relevance` | None | SL-relevance | Admission rejection |
| `ambient.static-authority` | Image scan over static extents | SL-ambient-static | Admission rejection |
| `ambient.rooted-mutability` | Root enumeration plus provenance chains | SL-ambient-rooted | Admission rejection |
| `repr.conform` | Absence scan | SL-repr | Admission rejection |
| `prov.integrity` | Absence of integer-to-pointer construction | SL-prov | Admission rejection |
| `ct.taint` | None | SL-ct | Admission rejection |
| `cost.wcet` | Cost model plus interference premise O2 | SL-cost | Admission rejection |

**Ledger difference.** `bare-rv64` carries no M entries. It adds L3: the loader maps code regions read-execute and data regions non-executable, and no mapping is changed after admission. Its C1 premise is load-bearing for eleven facets rather than eight, because nothing here is enforced by the machine.

**The fat-pointer representation is not a route.** A bounds pair carried as an ordinary aggregate is how the inserted check obtains the bounds it compares against; the discharge is still the check that executes, and `repr.conform` fixes the layout the check reads.

**What a bare profile does not recover.** Every open-world line of §6.2 becomes address-space-closed here. A consumer that runs unverified native code beside admitted code under `bare-rv64` has no guarantee at all from those facets, which is why TAL-026 makes the closure premise explicit rather than implied.

---

## 7. The frozen theory

### 7.1 The four absences

This document fixes and closes the type theory. The following four absences are what make checking a dataflow validation rather than proof checking.

1. **Predicative, rank-1 prenex polymorphism.**
   Type variables are quantified only at the outermost position of a code type and instantiated only at monotypes: the classical TALx86 use (polymorphism over callee-saved registers and stack tails) and no more.
   Instantiation is first-order substitution, so there is no impredicative self-instantiation to justify and no rank-*n* inference to decide.
2. **No type-level computation.**
   Type equality is syntactic, alpha-equivalence over first-order terms, decided by structural comparison and not by conversion: no reduction, no normalizer, no evaluation of open terms, and therefore no strong-normalization premise inside the checker.
   This is the largest deletion and the one that makes termination syntactic rather than a metatheoretic side condition the trusted base would have to carry.
3. **No universes and no universe polymorphism.**
   There is one sort of types, with no cumulativity, universe-constraint graph, or acyclicity solver.
4. **No user-extensible inductive definitions.**
   The type constructors are the fixed, closed vocabulary of §8.2. The checker performs no positivity check, guard check, or eliminator generation. The vocabulary grows only by amendment to this document, never at install time.

**TAL-033** MUST: The four absences hold of every profile, every rule table, and every amendment.
· Accept: no rule anywhere in this document or in a profile's rule table requires higher-rank instantiation, conversion, a universe constraint, or a user-supplied former.
· Trace: §8.2, §7.5

**Why they are load-bearing.** A term checker for a full calculus of inductive constructions spends its tens of thousands of lines on four hard structures: universe constraints, conversion, positivity, and the guard condition. Absences (2), (3), and (4) delete exactly those four, and absence (1) removes the instantiation and inference problems higher-rank polymorphism would reintroduce. What remains is not a small dependent-type checker but a different kind of program: an attribute evaluator over an already-typed control-flow graph.

### 7.2 Attribute domains

**TAL-034** IS: Every attribute has a carrier of exactly one of two kinds.

| Kind | Carrier | Bound on representation | Bound on operations |
| --- | --- | --- | --- |
| **Profile-fixed** | A finite set fixed by this document or by the profile, independent of the artifact | A constant | Constant time per node |
| **Certificate-bounded** | A finitely represented family whose size is bounded by a declared limit of §8.9 | The declared limit | Stated per operation, in terms of that limit |

· Accept: each attribute in §8.5 names its kind, its carrier, and, if certificate-bounded, the limit that bounds it and the complexity of its join and transfer.
· Trace: §8.5, §8.9

Profile-fixed carriers: the initialization flag (a two-point meet-semilattice), the taint label (a two-point join lattice), the grades (a fixed four-point set), the leakage class of an instruction.
Certificate-bounded carriers: the callee set (bounded by the declared maximum cardinality), the linear context (bounded by the declared maximum live-slot count), the guard-token set (bounded by the declared maximum), the cost numeral (bounded-width, saturating, §7.6), the type term itself (bounded depth and size).

**TAL-035** MUST: A certificate-bounded carrier's limit is checked before any attribute is evaluated, and exceeding it is a rejection rather than a slow path.
· Accept: §10.2 phase 1 rejects on limit violation; no attribute evaluator contains an unbounded loop or an unbounded allocation.
· Trace: §10.2, §10.3

### 7.3 Every rider fits the theory

Memory safety and control-flow integrity are register-file preconditions over capability or pointer types, and first-order.
The linear and affine discipline and the relevance grading are context-splitting side conditions decided structurally.
The callee set is a finite collection of first-order code labels whose membership test is structural set comparison, so it refines an existing former rather than adding a grade axis.
The initialization flag rides the capability-type former over the slots the consumer's memory plan already fixes, and taint is a join in a two-point lattice.
The representation and provenance rules add no former and no grade: they are the five deletions of move III, four of them absences the checker confirms by inspecting a derivation it already reads.
The three grade re-uses add nothing either: *use-once* is the linear grade the context-splitting side condition already runs, *must-erase* is its relevance polarity, and a *dimension* is a phantom parameter under absence (2)'s syntactic type equality, inhabited by no term and erased before code generation.

### 7.4 What the vocabulary contains

The closed vocabulary is the grammar of §8.2 and nothing beside it. A former not in that grammar does not exist for any profile, and a profile may not extend it.

**TAL-036** MUST NOT: A profile adds no type former, no grade, and no label. A profile chooses routes, rules, limits, models, and a ledger, and nothing else.
· Accept: two profiles' rule tables range over the same type grammar; a profile-local former is a specification defect.
· Trace: §8.2, §5.6

### 7.5 The amendment rule

**TAL-037** MUST: A proposed attribute is admitted only after a demonstration of all six properties: (1) its carrier is profile-fixed or certificate-bounded under §7.2, with a stated representation bound; (2) every operation on it, transfer and join alike, has a stated complexity in terms of that bound; (3) it is decided without reduction of open terms and preserves syntactic type equality; (4) it duplicates no existing grade or label axis; (5) it has a local, syntax-directed rule; (6) it comes with a soundness lemma against the machine semantics of at least one profile and with the negative tests of §13.
· Accept: each attribute's amendment record carries six shown arguments; a record carrying only algebraic shape and locality is incomplete. This strengthens the three-part criterion the consumer register states at R-05-132, and does not weaken it.
· Trace: §7.2, §13

**TAL-038** IS: A feature that fails the amendment rule is not lost: it descends to the consumer's proof kernel as a release-time proof term, at the price of ceasing to be per-install checkable.
· Accept: the rejected feature appears in the consumer's release-time obligation set, not in the attribute set.
· Trace: §4.5

### 7.6 The one permitted computation

**TAL-039** IS: The only computation the checker performs is bounded-width arithmetic over closed numerals: cost sums and comparisons along a max-path, and overflow range side conditions at arithmetic rules. Each is decided in constant time per node.
· Accept: no rule reduces an open term; every numeral in a certificate is closed and within the declared width.
· Trace: §8.5

**TAL-040** MUST: Cost arithmetic saturates rather than wraps, and saturation is a rejection: an addition or a multiplication that would exceed the declared width fails admission at that site.
· Accept: the cost carrier is the declared-width naturals with a top element that no accepted certificate reaches; a certificate whose cost overflows is rejected with the site named.
· Trace: §8.5, §10.4

### 7.7 The theory binds the checker, not the producer

**TAL-041** IS: A certifying compiler may be written in, and reason with, whatever theory it likes. Only the shipped derivation must be checkable in this one.
· Accept: no admission rule constrains producer-side theory.
· Trace: §12

---

## 8. The formal core

This section is the language proper. The prose of §1 to §7 is its index.

### 8.1 The certificate

```
certificate ::= header binding limits typedecls blocks edges joins guards loops calls
                statics roots chains citations premises
header      ::= "tal" spec-version profile-id profile-version decoder-id decoder-version
binding     ::= image-hash layout entry-points wiring-hash initializer-hash table-hash*
limits      ::= (limit-id numeral)*
typedecls   ::= (type-name type)*
blocks      ::= (block-id first-index instr-count entry-state)*
edges       ::= (block-id successor-block-id edge-kind)*
joins       ::= (block-id exit-state)*
guards      ::= (guard-token guard-site guarded-site pattern-id)*
loops       ::= (loop-id header-block parent-loop trip-bound)*
calls       ::= (site-id callee-set rank)*
statics     ::= (extent-start extent-length mutability tagged)*
roots       ::= (root-id extent-id authority-type)*
chains      ::= (store-site head-root-or-param derivation-step*)*
citations   ::= (site-id invariant-id)*
premises    ::= (premise-id class statement numeral evidence-tag)*
```

**TAL-042** MUST: A certificate carries all fifteen parts. A missing, duplicated, or out-of-order part is malformed and rejected before any typing rule runs.
· Accept: the parse is a single forward pass over a canonical encoding; no part is optional and no default is supplied.
· Trace: §8.8, §10.2

### 8.2 Types

```
w   ::= 8 | 16 | 32 | 64 | 128                    machine widths the profile declares
g   ::= un | aff | lin | rel                      grades: unrestricted, affine, linear, relevant
l   ::= pub | sec                                 taint labels
i   ::= uninit | init                              initialization flag
t   ::= int w                                     integer of width w
      | ptr b p k i                               pointer or capability: bounds b, permissions p,
                                                  grant binding k (bare or a grant-slot handle),
                                                  initialization flag i
      | code G c                                  code label: register-file precondition G,
                                                  callee-set tag c
      | < t1 ... tn >                             aggregate with a layout the profile fixes
      | exists a . t                              existential over a monotype
      | forall a . code G c                       prenex, rank-1, code types only
      | a                                         type variable
G   ::= { r1 : t1 g1 l1 , ... }                   register-file type
```

**TAL-043** IS: This grammar is the whole type vocabulary. Type equality is alpha-equivalence over these terms, decided structurally.
· Accept: the checker's equality routine is one structural comparison with no conversion case.
· Trace: §7.1

**TAL-044** MUST: Every type in a certificate is well-formed: bounds and permissions are drawn from the profile's declared sets, aggregate layouts match the profile's layout rules, existential and universal binders are closed under the declared depth limit, and no type variable is free at a block entry state.
· Accept: well-formedness is decided in one pass over the type declarations before any block is visited.
· Trace: §10.2

### 8.3 The decoded image and the control-flow graph

**TAL-045** MUST: The checker decodes the artifact itself, using the profile's decode function, and does not read an instruction stream the certificate supplies.
· Accept: removing every instruction field from the certificate changes no verdict; the certificate supplies types and structure, never code. For the VerifiedOS instantiation the decode function is the slot-indexed function of R-15-036b.
· Trace: §9.2

**TAL-046** MUST: The certificate's block table partitions the decoded instructions of every executable extent exactly: every decoded instruction belongs to exactly one block, blocks do not overlap, and every declared entry point is the first instruction of some block.
· Accept: a coverage pass over the block table detects any gap, overlap, or misaligned entry, and rejects.
· Trace: §10.2

**TAL-047** MUST: The edge table is exact: for every instruction that transfers control, the successors the profile's rule table assigns to that instruction form are precisely the declared edges of its block, and an indirect transfer's edges are precisely its declared callee set.
· Accept: the checker recomputes each block's successor kinds from its final instruction and compares; a missing or extra edge rejects.
· Trace: §8.5

### 8.4 Judgments

```
|- t ok                        well-formed type
|- G ok                        well-formed register-file type
S ::= (G, L, T, K, N, c)       abstract state: register-file type, linear context, taint
                               environment, guard-token set, callee constraint, cost numeral
S |- instr => S'               instruction transfer, from the profile's rule table
S' <= S                        state refinement, componentwise (§8.5)
|- block b : S -> S'           block transfer, the composition of its instruction transfers
|- image ok                    the move-III image judgments (§8.6)
|- cert |> artifact : verdict  admission (§10.4)
```

**TAL-048** IS: The transfer judgment is supplied per instruction form by the profile's rule table; this document fixes the judgment's shape, its state components, and the refinement relation, and the profile fixes the rules.
· Accept: every rule in a rule table has the shape above, premises drawn from the instruction's own operands, the profile's declared sets, and the certificate's records for that site.
· Trace: §5.3, §8.5

A representative rule shape, which every rule table instantiates rather than extends:

```
load:     G(rs) = ptr b p k init      read in p      offset within b      G' = G[rd := t]
          taint: T(rd) := T(rs) join T(mem-class)
          linear: L unchanged if grade(G(rs)) = un, else rs consumed and rebound
          cost:  c' = c + latency(load)
          -----------------------------------------------------------------------
          (G, L, T, K, N, c) |- load rd, rs, off => (G', L', T', K, N, c')
```

The clauses of a rule are exactly the attributes of §8.5, one clause each; a rule with a clause outside that set is a profile defect.

### 8.5 Attributes, transfer, and joins

**TAL-049** IS: The state has six components, and every attribute is one of them.

| Component | Carrier kind | Join direction | Cost of one join |
| --- | --- | --- | --- |
| Register-file type G | Certificate-bounded (type size) | Syntactic equality, except the initialization flag, which meets | Linear in the declared type size |
| Linear context L | Certificate-bounded (live-slot limit) | Exact equality of the multiset | Linear in the limit |
| Taint environment T | Profile-fixed (two points per slot) | Pointwise join, `pub` below `sec` | Linear in register count |
| Guard-token set K | Certificate-bounded (token limit) | Intersection | Linear in the limit |
| Callee constraint N | Certificate-bounded (callee-set limit) | Union, then containment in the declared set | Linear in the limit |
| Cost numeral c | Certificate-bounded (declared width) | Maximum, saturating | Constant |

· Accept: no attribute exists outside this table; adding one is an amendment under §7.5.
· Trace: §7.2, §7.5

**TAL-050** IS: State refinement `S' <= S` is the componentwise order of the table: types equal up to the initialization meet, linear contexts equal, taint pointwise below, guard sets superset, callee constraint subset, cost below.
· Accept: refinement is decided in one pass over the state, with no search.
· Trace: §10.3

**TAL-051** MUST: The checker validates, for every edge, that the exit state the certificate records for the source refines the entry state the certificate records for the target. It computes no entry state and iterates to no fixpoint.
· Accept: every edge is visited exactly once; a certificate whose entry state is unjustified by some predecessor is rejected at that edge, with the edge named.
· Trace: §10.2, §10.3

**TAL-052** MUST: Cost is not evaluated as a dataflow attribute over cycles. It is evaluated over the certificate's declared loop nest: back edges are removed, the residual graph is required to be acyclic in the declared block order, and a loop contributes its body cost multiplied by its declared trip bound to its parent.
· Accept: the loop table is validated locally (each back edge's target is its declared header; each header's parent is an enclosing loop; nesting depth is within the declared limit) and the cost of each region is computed in one pass over blocks in the declared order.
· Trace: §8.7, §10.2

**TAL-053** MUST: Interprocedural cost and stack depth rest on a declared call order: every call site's callees have strictly lower rank than the caller, so the call graph induced by the declared callee sets is acyclic, or the certificate declares a recursion-depth premise for the component that is not.
· Accept: rank comparison is one integer test per call site; a cyclic component with no declared depth premise is rejected.
· Trace: §8.7

**TAL-054** MUST: The taint rule rejects any secret-labeled value that reaches a branch condition, a memory address operand, or an operand the profile's leakage model classes as variable-latency.
· Accept: the three sink classes are declared per instruction form in the rule table; a secret-labeled operand at any of them rejects, with the site named.
· Trace: §5.1

### 8.6 Deletions, guard records, and rooted mutability

**TAL-055** IS: Move III decides five absences by inspection: no integer-to-pointer construction, no type punning, no variadic arity, no unbounded recursive former, and no implicit conversion.
· Accept: each is a structural test on a decoded instruction form or on a declared type; none requires a state.
· Trace: §10.1

**TAL-056** MUST: The inserted route is validated through the guard-token attribute, not through a dominance computation. A guard site adds its token to K; a join intersects; a guarded access is well-typed only if its token is in the validated entry state of its block and the recorded guard record names that access and the profile's declared check pattern.
· Accept: no dominator tree is built and no ancestor query is performed; the dominance fact is a consequence of the intersection join over validated entry states.
· Trace: §8.5, §11.3

**TAL-057** MUST: The run-time behavior of an inserted check on failure is the profile's declared failure state, and the soundness statement is conditioned on it: an execution either satisfies the facet or is in that state.
· Accept: the failure transfer is part of the declared check pattern; a check that falls through on failure does not match the pattern and rejects.
· Trace: §10.5, §11.1

**TAL-058** MUST: `ambient.static-authority` is decided by an image scan over the declared static extents: on a citing profile no tagged datum may appear in any static extent, and on a non-citing profile no static datum of pointer type may hold an address outside the declared root table.
· Accept: the scan visits every byte of every declared static extent once, and the extent table is checked to cover the image's data regions exactly.
· Trace: §10.2

**TAL-059** MUST: `ambient.rooted-mutability` is decided as a whole-image predicate, not by the static scan alone. The certificate enumerates every mutable root and every initial capability, and records for every store site a provenance chain whose head is one of those roots or a parameter of the enclosing code type and whose steps are the monotone derivations `prov.integrity` already validates.
· Accept: the chain records are inspected in one pass with no state and no fixpoint, which is why this facet stays a move-III deletion rather than becoming a second attribute; a writable extent absent from the root table rejects; a store whose chain is missing, mis-headed, or contains a step that is not a validated derivation rejects; a module-level mutable static, a lazily initialized static, a thread-local, or a hidden singleton is exactly the case this rejects, and the tag scan alone does not decide it. This is the binding form of the consumer-side statement at R-05-089 and R-05-086, and it keeps the move assignment of R-05-039.
· Trace: §4.2, §10.2

### 8.7 Declared premises

Some facets need a number the checker cannot infer and must not guess: a trip bound for a loop whose count is not structural, a depth bound for a recursive component. The language admits these as premises rather than pretending to decide them, and refuses to admit anything else that way.

**TAL-060** IS: A declared premise is a certificate record carrying a class, a statement, a closed numeral, and an evidence tag naming the consumer-side obligation that discharges it. The checker validates the record's form and that the profile permits its class, and treats the numeral as given.
· Accept: premises are the only certificate content the checker does not decide, and each appears in the verdict.
· Trace: §10.4, §5.5

**TAL-061** MUST: The only permitted premise classes are trip bounds and recursion-depth bounds. No other premise class exists, and in particular no premise asserts a path, a feasibility, an aliasing fact, or a safety property.
· Accept: a certificate declaring any other class is rejected; the checker's premise vocabulary is closed.
· Trace: §4.4

**TAL-062** MUST: A structurally inferable bound is inferred, never declared. A premise whose statement the checker could decide from the loop's own instruction sequence is a rejection, not a shortcut.
· Accept: the rule table marks the structural loop forms; a premise at such a loop rejects. For the VerifiedOS instantiation the discharge of a non-structural bound is R-05-107's Coq obligation against source.
· Trace: §4.4

### 8.8 Canonical serialization

**TAL-063** MUST: The certificate has exactly one accepted byte encoding for each derivation: fields in the declared order, integers in the declared minimal form, sets in the declared sort order, no unknown fields, no trailing bytes.
· Accept: the checker re-serializes what it parsed and compares, or parses with a canonicality-checking reader; a non-canonical encoding rejects.
· Trace: §9.1

**TAL-064** MUST NOT: The parser follows no offset, resolves no reference by search, and interprets no length it has not bounds-checked against the certificate's own size.
· Accept: parsing is a single forward pass with a bounded working set.
· Trace: §10.3

### 8.9 Resource limits and malformed input

**TAL-065** MUST: A profile declares a maximum for each of: callee-set cardinality, live linear slots per state, guard tokens per image, type-term depth, type-term size, numeral width, loop-nest depth, block count, edge count, static-extent count, root count, provenance-chain length, and certificate size.
· Accept: thirteen limits, each a numeral in the profile, each checked in phase 1 of §10.2.
· Trace: §10.2

**TAL-066** MUST: Every malformed input is rejected, never accepted and never diverged on: a parse failure, a limit violation, a non-canonical encoding, a binding mismatch, an unknown version, an undecodable byte in an executable extent, or a rule-table gap.
· Accept: the checker terminates on every input by construction of §10.2's traversal, and its rejection carries the first failing rule identifier and site.
· Trace: §10.4

---

## 9. Binding the certificate to the installed artifact

A derivation about bytes that are not the installed bytes proves nothing about what runs. This is the seam at which annotated assembly can silently differ from an installed image, and the binding below is what closes it.

### 9.1 The commitment

**TAL-067** MUST: The certificate commits to all eight: the content hash of the code-and-rodata image, the layout (base address and extent map), the entry-point set, the content hash of the data initializer, the content hashes of the immutable tables the profile names, the capability-wiring or relocation table's hash, the decoder identity and version, and the profile identity and version.
· Accept: all eight fields are present in the binding part; the checker recomputes each hash over the installed bytes and rejects on any mismatch before decoding.
· Trace: §8.1, §10.2

**TAL-068** MUST: Admission is over the post-link, post-layout, post-encoding installed artifact. No pre-layout, relocatable, or symbolically addressed form is an admissible input.
· Accept: the checker requires a concrete layout and refuses a certificate whose binding names unresolved addresses. For the VerifiedOS instantiation the artifact is the content-addressed capability image of R-13-003, and the wiring table of R-13-006 is the relocation state the binding covers.
· Trace: §3

### 9.2 Decode binding

**TAL-069** MUST: The decoder is named by identity and version in the binding, and a checker whose decode function differs from the named one rejects rather than proceeding.
· Accept: decoder identity is compared before decoding; a mismatch is a rejection with the named decoder reported.
· Trace: §8.3

**TAL-070** MUST: Decode is a function of image content and position alone, so that entering an executable extent at any declared entry yields the same instruction sequence a linear decode of that extent yields from that position.
· Accept: the profile states this as a theorem of its decode function; a profile whose encoding permits mid-instruction reinterpretation owes an additional reachable-entry argument, and states it in its ledger.
· Trace: §5.1

### 9.3 What is not an admissible input

**TAL-071** MUST NOT: An assembly listing, an object file, an intermediate representation, a debug record, or any producer-side artifact other than the certificate participates in admission.
· Accept: the checker's input is the artifact, the certificate, and the profile; a checker that reads a fourth input is non-conforming.
· Trace: §4.4

### 9.4 Versions

**TAL-072** MUST: The verdict records the specification version, profile version, decoder version, and the artifact's content hash, and a consumer treats a verdict for a different tuple as no verdict.
· Accept: verdicts are keyed by the tuple; a version bump invalidates the key rather than the artifact.
· Trace: §2.3

---

## 10. The checker

### 10.1 The three moves

| Move | What the checker does | Why it stays small |
| --- | --- | --- |
| **I. Cite a run-time invariant** | Confirms the derivation records reliance on an invariant the profile declares, and that the reliance site is in that invariant's applicability class. | It does not re-prove the machine's fact; it inspects the reliance. |
| **II. Evaluate an attribute** | Runs a local, syntax-directed transfer over the typed control-flow graph, taking each block's entry state from the derivation and validating every edge's refinement. | Each attribute has a bounded carrier and a local rule, and the derivation supplies the joins a fixpoint would otherwise have to find. |
| **III. Confirm a deletion** | Checks that constructs which would make the static account lie are absent. | These are one-pass inspections of absences over the decoded image and the derivation. |

**TAL-073** MUST: The checker has exactly these three moves and no fourth mechanism. The inserted route is move II over a guard record plus a run-time check the machine executes; it is not a fourth move.
· Accept: every line of every profile matrix names a move from this table; the shipped checker's structure is the six phases of §10.2 and nothing else. This is the language-level form of the consumer-side statement at R-05-036.
· Trace: §5.2, §8.6

Move I is empty for a profile that cites no invariants. In that precise sense a bare target is more expensive than a capability target: the facets remain, and move to lower routes.

The word *attribute* is Knuth's, and the analogy is deliberately partial: an attribute grammar decorates a tree, while a machine-code control-flow graph is cyclic, which is precisely why the derivation carries the abstract state at every merge and the checker validates rather than solves.

### 10.2 The algorithm

**TAL-074** MUST: The checker runs these six phases in this order, and rejects at the first failure.

| Phase | What it does | Traversals |
| --- | --- | --- |
| 0. Bind | Recompute the eight commitments of §9.1 over the installed bytes; compare versions | One pass over the artifact's bytes |
| 1. Parse and limit | Parse the certificate canonically; check the twelve limits of §8.9 | One forward pass over the certificate |
| 2. Decode and structure | Decode every executable extent; check the block partition, the edge table, the loop nest, the call order, and the static-extent cover | One pass over decoded instructions, one over the tables |
| 3. Deletions (move III) | The five absences, the static-authority scan, the root table's cover, and the provenance chains | One pass over decoded instructions, one over static extents, one over the chain records |
| 4. Citations (move I) | Each reliance site against the profile's cited set and applicability class | One pass over the citation table |
| 5. Attributes (move II) | Per block in declared order: apply transfers, validate every out-edge's refinement, accumulate cost over the loop nest | One pass over instructions, one over edges |

· Accept: six phases, each with the traversal count stated; no phase revisits a block, and no phase iterates to convergence.
· Trace: §10.3

### 10.3 The complexity contract

**TAL-075** MUST: Total work is linear in the size of the decoded image plus the size of the certificate, with per-instruction and per-edge work bounded by the profile's declared limits: `O(|I| * (d + s + p) + |E| * (s + k + n) + |C|)`, where `|I|` is decoded instructions, `|E|` edges, `|C|` certificate bytes, `d` the type-depth limit, `s` the live-slot limit, `p` the provenance-chain-length limit, `k` the guard-token limit, and `n` the callee-set limit.
· Accept: the bound is stated per phase in §10.2 and is demonstrated for the shipped implementation; no operation's cost depends on a quantity the limits do not bound.
· Trace: §8.9, §10.2

**TAL-076** MUST: Peak working memory is bounded by the size of one block's state plus the certificate's index structures: `O(s + k + n + d + |B|)`, where `|B|` is the block count. The checker holds no per-instruction state after the block containing it is validated.
· Accept: a streaming implementation exists; memory does not grow with path count or with the number of edges validated.
· Trace: §10.2

**TAL-077** MUST NOT: No phase performs a fixpoint iteration, a dominator computation, an ancestor query, a transitive-closure computation, or a search over paths.
· Accept: the four are absent from the implementation; the guard-token attribute replaces dominance, and the declared call order replaces reachability over the call graph.
· Trace: §8.6, §8.5

### 10.4 Acceptance and rejection

**TAL-078** IS: Acceptance is the conjunction of the six phases. The verdict is `accept(artifact-hash, spec-version, profile-version, decoder-version, ledger, premises)` or `reject(rule-id, site)`.
· Accept: an accepting verdict names every premise and ledger entry it consumed; a rejecting verdict names one requirement and one site.
· Trace: §5.5, §9.4

**TAL-079** MUST: Rejection is total and silent about repair: the checker offers no partial admission, no warning tier, and no override.
· Accept: the verdict is binary; no configuration admits an artifact that fails a rule.
· Trace: §10.4

### 10.5 Run-time failure behavior

**TAL-080** MUST: A profile declares one failure state, reached by a machine trap for cited facets and by the inserted check's failure transfer for inserted facets, and the soundness statement is conditioned on it (§11.1).
· Accept: one declared failure state per profile; every failure path in every matrix line names it.
· Trace: §11.1, §8.6

### 10.6 The audit budget

**TAL-081** IS: The line budget is a secondary audit figure, not the contract. The contract is §10.3. The budget counts the shipped source of the attribute evaluator, the derivation reader, the binding check, and the image scan, on the order of a thousand lines, and excludes the frozen vocabulary and attribute tables (data fixed by this document), a consumer's proof kernel, and the metatheory.
· Accept: the figure is reported with its exclusions stated; an implementation that met a line figure by moving decisions into a generated table fails §10.3 and therefore fails the claim, whatever its line count.
· Trace: §10.3

---

## 11. Soundness

### 11.1 The statement

**TAL-082** IS: The metatheorem is *well-typed implies safe*, stated per profile: for every artifact and certificate the checker accepts under profile P, every execution of that artifact from a state satisfying P's loader and operational ledger entries either satisfies every facet P routes, or is in P's declared failure state.
· Accept: the statement quantifies over executions of the decoded artifact under P's machine semantics; the failure-state disjunct is present; the facet set is the profile's route table and not a prose list.
· Trace: §6, §10.5

**TAL-083** MUST: The theorem is parameterized over the profile and its ledger, and no instantiation may quietly strengthen the conclusion beyond the facets its route table carries.
· Accept: the mechanized statement takes the ledger as a hypothesis record; each conjunct of the conclusion traces to one matrix line.
· Trace: §5.5

### 11.2 The ledger it consumes

**TAL-084** IS: The theorem discharges M and L entries and assumes C, S, O, and P entries. A profile that presents an S or O entry as discharged is defective.
· Accept: the mechanized statement's hypotheses are exactly the C, S, O, and P entries of the profile's ledger; its proof obligations are exactly the M and L entries.
· Trace: §5.5

### 11.3 What a profile must discharge

**TAL-085** MUST: A profile's instantiation supplies, for each cited invariant, a theorem of its own machine semantics with the stated applicability and exceptions; for each inserted check, a lemma that the guard-token attribute implies the check executes before every guarded access on every path; and for each attributed facet, the soundness lemma its matrix line names.
· Accept: every matrix line's lemma name resolves to a proved statement in that profile's development; a lemma citing an invariant absent from the semantics is a defect that invalidates the instantiation.
· Trace: §6.2, §6.3

**TAL-086** IS: The core carries every proof obligation that does not mention the machine, so a second profile does not reopen the whole development; it discharges every machine-dependent case, which is not free.
· Accept: the development is factored into a machine-independent core and per-profile instantiations, and the factoring is visible in the proof structure.
· Trace: §11.1

### 11.4 The trusted base

The metatheorem is the language's main trusted theorem, and freezing the theory bounds its size as it bounds the checker's.
Calling it the single axiom would understate the base. A consumer also trusts the machine semantics and its correspondence to the silicon (ledger entry S1), the profile's cited invariants, the decoder that recovers instructions from the image, the loader and initial-state model, and the implementation of the checker.
The claim worth making is that this list is small, fixed, separately reviewable, and enumerated in one place, not that it has one element.

**TAL-087** MUST: The trusted base is enumerated as the profile's ledger plus the checker implementation plus the metatheorem, and a consumer can read it off an accepted verdict.
· Accept: the verdict's ledger plus two named artifacts is the whole base; no element of the base is discoverable only from prose.
· Trace: §10.4

### 11.5 What soundness does not say

A mis-stated typing rule admits an unsafe binary that type-checks perfectly, exactly as a wrong specification verifies perfectly, which is why this is a specification worth reviewing rather than a proof worth trusting.

**TAL-088** IS: The theorem says nothing about facets a profile does not route, about properties outside the menu, about the artifact's functional behavior, or about executions from a state violating the ledger's L and O entries.
· Accept: no consumer document claims a guarantee that no matrix line carries.
· Trace: §4.5

---

## 12. Producers

**TAL-089** IS: Admission depends on the derivation, never on producer identity: any producer of a well-typed binary is admissible by definition, and a consumer's reference compiler is a reference rather than a gate.
· Accept: the checker reads no producer attestation (TAL-016).
· Trace: §4.4

**A producer may be built on an existing unverified toolchain, and should be.**
The practical shape is **hinted mirroring**: the untrusted compiler records hints through lowering, and a replayer reconstructs the derivation the checker re-validates. This requires a replayer beside an arbitrary producer, not a whole-compiler preservation proof, so an LLVM backend is a reasonable implementation path.

**TAL-090** IS: The replayer is untrusted. It produces evidence the checker revalidates in full, so a replayer defect yields a rejected artifact or a derivation the checker still validates on its own terms, never an unsound admission.
· Accept: the replayer appears in no consumer's trusted base (§11.4); removing it and hand-writing a certificate changes no admission rule.
· Trace: §11.4

**This does not make guarantees independent of the source language.**
A compiler intermediate representation carries none of the facts the derivation asserts: ownership, lifetime, exclusivity, initialization, taint, dimension, and callee sets come from the *source* type system, not from the lowering. Downstream tooling cannot preserve a fact the source never established.

**TAL-091** IS: A source language is admissible on one of exactly three grounds:

1. **It establishes the facts itself** (an ownership discipline, a synchronous dataflow language, a proof assistant's term language, or verified C with its own proofs), in which case the producer preserves them and the derivation is cheap.
2. **It accepts insertion**, in which case the producer emits run-time checks and the checker requires the guard records of §8.6: the guarantee holds, and it is paid for on every execution.
3. **It ships a source-level proof** elaborated into a semantics the consumer already reviews, *and* transports the proved fact to final code.

· Accept: a language satisfying none of the three is not admitted, and choosing a different backend does not change that result.
· Trace: §12

**TAL-092** MUST: Ground 3 is not a bypass of the artifact-level rule. A source-level proof yields admission only when the producer either emits a derivation whose local premises the checker validates for the affected facets, or reduces the fact to a declared premise of a class §8.7 permits. A proved source fact with no transport to final code discharges nothing.
· Accept: no artifact is admitted with a facet unrouted or a route unsupported by certificate evidence, whatever exists at source.
· Trace: §8.7, §5.2

This is §5.2's route table seen from the other end: when an invariant is not supplied by the environment, the language demands evidence or a check, and it makes no difference whether the environment that failed to supply it was the hardware or the source language.

---

## 13. Conformance and adversarial suites

**TAL-093** MUST: Every requirement of this document with an operational acceptance criterion has at least one positive and one negative test in the language conformance suite, and a checker is conforming only against the whole suite.
· Accept: the suite indexes tests by requirement identifier; an unindexed requirement is a suite defect.
· Trace: §2.1

**TAL-094** MUST: The adversarial suite includes at least these thirteen classes, each with an artifact that a defective checker would accept:

1. A join state unjustified by some predecessor edge.
2. A linear context that differs across two predecessors of one block.
3. A tagged datum in a static extent, and a writable extent absent from the root table.
4. A store whose target authority has no provenance chain to a root or a parameter.
5. An access whose bounds are exact at source and inexact under the encoding.
6. A transfer into a privileged or transition case a cited invariant excludes.
7. A callee set that under-declares a realized target.
8. A guarded access whose guard token is absent on one incoming path.
9. A secret-labeled value reaching a branch, an address, and a variable-latency operand.
10. A cost accumulation that overflows the declared width.
11. A loop with a declared premise where the bound is structurally inferable.
12. A certificate whose bytes are canonical but whose image hash names a different artifact.
13. An executable extent with a byte sequence the decode function rejects, and one whose block partition leaves a gap.

· Accept: thirteen classes, each with at least one artifact per profile; the suite runs in every profile admission under §5.8.
· Trace: §5.8

**TAL-095** MUST: A profile ships its own conformance suite: one artifact per matrix line exercising the routed discharge, and one negative artifact per cited invariant exercising its stated exceptions.
· Accept: the per-profile suite covers all fifteen facets and every cited invariant.
· Trace: §6

---

## 14. What this is not

- **Not an isolation mechanism.** Its guarantees apply to admitted code. A system that also runs other code needs hardware isolation or a supervisor; under a profile with no cited facets that requirement is mandatory (TAL-026).
- **Not an intermediate representation.** It types final machine code against a machine semantics, so a target needs an ISA semantics of the quality of a Sail model before it can have a profile at all.
- **Not a proof system.** The deep tier stays with a proof kernel (TAL-017), and every proposal to move an obligation inward is decided by the amendment rule (TAL-037) rather than by appetite.
- **Not a safety claim about a source language.** It carries facts; it does not manufacture them (§12).
- **Not a guarantee of what it does not route.** A facet no profile routes is not covered by anything here (TAL-088).

---

## 15. Status

All three parts remain unbuilt: the type system, the checker, and the soundness proof.
The general type-soundness discipline is established and is inherited rather than gambled on; this instantiation is not, and the risk is located precisely: being first to instantiate the discipline over an ISA-scale semantics rather than an idealized machine.

Factoring the language out of the operating-system specification changes exactly three things:

1. **The review surface improves.** The language can be reviewed, and its soundness proof read, by someone who has no opinion about capability operating systems.
2. **The cost becomes shareable.** A second consumer at a different profile pays for its own machine-dependent cases and shares the core.
3. **A version seam appears where a freeze used to be.** A theory frozen inside one document is frozen by that document's amendment process; a theory frozen in a dependency is frozen by a pin, and a consumer that fails to re-review on a version bump has silently widened its own axiom set.

None reduces the work, and the factoring does not change the first consumer's schedule.

---

## Appendix A. Where the design comes from (non-normative)

This appendix is rationale. It binds nothing, and a change in the literature's status is not an amendment to §1 to §15. Citation keys resolve in Appendix B. Broader system lineage lives in [inspirations.md](inspirations.md).

**Typed assembly language.** [MWCG99], [TALx86], [Crary03] supply polymorphic code-pointer types, register-file preconditions, stack polymorphism, initialization tracking, typed indirect jumps, and producer-supplied derivations, which is most of §8.2's vocabulary. Two boundaries in that lineage are the ones this document has to cross: TALx86 checked annotated assembly rather than independently decoded bytes, which §9 answers, and foundational TAL separates abstract-machine soundness from the correspondence with a concrete architecture, which §5 and §11 make a profile's obligation.

**Proof-carrying code.** [Necula97], [Appel01], [Hamid02]. Proof-carrying code already covers binary machine code from an untrusted producer checked against a consumer-defined policy; the foundational account makes decoding, machine semantics, and the safety predicate foundational; and the syntactic account factors a certificate into a typing derivation plus a reusable soundness proof, which is this document's split between §4 and §11.

**Certificate-directed checking.** [Rose03], [KleinNipkow]. This is the closest precedent for §1's architecture and the reason the no-fixpoint property is stated of consumption rather than of the pipeline. Stack maps carry the abstract state at each merge, reducing verification from dataflow solving to checking local transfer constraints, which is §8.5 with a smaller attribute set. The counter-experiment is on the record too: [VeriWasm] re-derived the safety of compiled native code by analysis rather than certificate, and could not keep pace with the compiler, which is the analyzer-rot failure mode a shipped derivation does not have.

**Typed admission in production.** [Move], [WasmCallRef]. A publish-time verifier for linear resources, definite initialization, and a borrow discipline, and a load-time-checked typed callee set, are production precedent for most of §4.2's attribute classes; taint alone has none. Both are fixpoint analyzers rather than certificate consumers, and [MoveBug]'s unreachable-code soundness defect is the concrete argument for a checker small enough to verify.

**Final machine code.** [RockSalt], [Islaris], [SailISA], [MorelloCerise]. A decoded binary image checked against a machine model proved sound in a proof assistant, binary machine code reasoned about against full Sail-derived semantics, and encapsulation proved for a shipped capability machine against its authoritative semantics: together the precedent for the seam §9 stands on.

**Capability machines.** [CHERIISA], [CHERISail], [Nienhuis20]. These are what a citing profile cites: tagged capabilities, bounds, permissions, sealing, provenance validity, and guarded monotone derivation, with the published qualifications §6.2 requires a profile to state rather than gloss.

**Capability-machine logics and universal contracts.** [Cerise], [Katamaran], [Morello]. This is the road the field took instead of typed assembly: a program logic whose logical relation gives arbitrary code a universal contract, which is the mechanized form of what a citing profile cites, and defense in depth beneath a checker or metatheorem error. Each is idealized or in another prover, and none yields a per-binary certificate; the distance between a universal contract over all code and a derivation about this binary is exactly the language.

**Linear control and ownership.** [StkTokens], [CapCalc], [AliasTypes], [RustBelt]. StkTokens is the direct precedent for a linear capability discipline proving well-bracketed control flow and stack encapsulation. It does not establish general heap temporal safety on ordinary capability hardware, which is why `mem.temporal` owes an allocator-and-reuse theorem of its own.

**Constant-time typing.** [CTWasm], [Barthe14], [Almeida16], [SecSep], [Jasmin]. CT-Wasm is the direct precedent for the taint route, mechanized through semantics, checker, and soundness together, with a guarantee relative to an explicit leakage model. A taint-typed assembly language for cryptographic code, with annotations inferred by a producer and re-checked over final assembly, carries exactly this obligation and no other; the structured-leakage line transports constant-time and cost facts together through compilation as proved leakage transformers, the nearest mechanized metatheory to hold §4.3's two boundary cases in one frame.

**Cost certificates.** [Shaw89], [LiMalik95], [Carbonneaux17], [MRG], [CerCo], [CraryWeirich00]. These support compositional timing annotations and independently checked resource bounds under exactly the side conditions §4.3 states. The certificate form has one shipped ancestor and one typed one, both defunct, so the attribute's precedent is method rather than code.

**Certifying compilation.** [NeculaLee98], [Crellvm], [CompCert]. Crellvm is the closest match to §12's hinted mirroring, over selected intermediate-representation optimizations rather than native code generation, so it supports the architecture without completing it.

**The combination is the novel part.** Not typed assembly language, not proof-carrying code, not capability typing, not taint typing, and not resource certificates, each of which is someone else's result. The combination is a fixed, non-extensible certificate language carrying all of them at once, assigning every facet an explicit cited, attributed, or inserted discharge against a versioned machine profile, and checking final decoded machine code without invoking a general proof kernel at install time. That is a claim about the arrangement, and it is the part a reviewer should attack first.

---

## Appendix B. Bibliography (non-normative)

Keys are document-local and stable across versions of this document; they assert no external identifier.

| Key | Reference |
| --- | --- |
| [Almeida16] | Almeida et al., *Verifying Constant-Time Implementations*, USENIX Security 2016 |
| [AliasTypes] | Smith, Walker, and Morrisett, *Alias Types*, ESOP 2000 |
| [Appel01] | Appel, *Foundational Proof-Carrying Code*, LICS 2001 |
| [Barthe14] | Barthe et al., *System-level Non-interference for Constant-time Cryptography*, CCS 2014 |
| [CapCalc] | Crary, Walker, and Morrisett, *Typed Memory Management in a Calculus of Capabilities*, POPL 1999 |
| [Carbonneaux17] | Carbonneaux et al., *Automated Resource Analysis with Coq Proof Objects*, CAV 2017 |
| [CerCo] | The CerCo project, certified complexity through a verified compiler in Matita, 2013 |
| [Cerise] | Georges et al., *Cerise*, JACM 2024 |
| [CHERIISA] | Watson et al., the CHERI ISA specification, University of Cambridge technical report |
| [CHERISail] | The CHERI-RISC-V Sail model |
| [CompCert] | Leroy et al., the CompCert verified compiler |
| [Crary03] | Crary, *Toward a Foundational Typed Assembly Language*, POPL 2003 |
| [CraryWeirich00] | Crary and Weirich, *Resource Bound Certification*, POPL 2000 |
| [Crellvm] | Kang et al., *Crellvm*, PLDI 2018 |
| [CTWasm] | Watt et al., *CT-Wasm*, POPL 2019 |
| [GFB24] | Geller, Frank, and Bowman, *Wasm-precheck*, POPL 2024 |
| [Hamid02] | Hamid et al., *A Syntactic Approach to Foundational Proof-Carrying Code*, LICS 2002 |
| [Islaris] | Sammler et al., *Islaris*, PLDI 2022 |
| [Jasmin] | Barthe et al., structured leakage and the Jasmin compiler, CCS 2021 |
| [Katamaran] | Huyghebaert, Keuchel, De Roover, and Devriese, *ISA Security Guarantees as Universal Contracts*, CCS 2023 |
| [KleinNipkow] | Klein and Nipkow, *Verified Lightweight Bytecode Verification* |
| [LiMalik95] | Li and Malik, implicit path enumeration, 1995 |
| [Morello] | Bauereiss et al., *Verified Security for the Morello Capability-enhanced Prototype Arm Architecture*, ESOP 2022 |
| [MorelloCerise] | Morello-Cerise, encapsulation for the shipped Morello machine, PLDI 2025 |
| [Move] | The Move bytecode verifier |
| [MoveBug] | Zellic, the Move unreachable-code reference-safety defect, 2023 |
| [MRG] | Mobile Resource Guarantees (Hofmann, Jost, Aspinall et al.), circa 2004 |
| [MWCG99] | Morrisett, Walker, Crary, and Glew, *From System F to Typed Assembly Language*, TOPLAS 1999 |
| [Necula97] | Necula, *Proof-Carrying Code*, POPL 1997 |
| [NeculaLee98] | Necula and Lee, *The Design and Implementation of a Certifying Compiler*, PLDI 1998 |
| [Nienhuis20] | Nienhuis et al., *Rigorous Engineering for Hardware Security*, S&P 2020 |
| [RockSalt] | Morrisett et al., *RockSalt*, PLDI 2012 |
| [Rose03] | Rose, *Lightweight Bytecode Verification*, JAR 2003 |
| [RustBelt] | Jung et al., *RustBelt*, POPL 2018 |
| [SailISA] | Armstrong et al., *ISA Semantics for ARMv8-A, RISC-V, and CHERI-MIPS*, POPL 2019 |
| [SecSep] | Song et al., *SecSep*, CCS 2025 |
| [Shaw89] | Shaw, *Reasoning About Time in Higher-Level Language Software*, TSE 1989 |
| [StkTokens] | Skorstengaard, Devriese, and Birkedal, *StkTokens*, POPL 2019 |
| [TALx86] | Morrisett et al., *TALx86: A Realistic Typed Assembly Language*, WCSSS 1999 |
| [VeriWasm] | VeriWasm, analysis-based safety re-derivation for compiled native code |
| [WasmCallRef] | WebAssembly typed function references and `call_ref` |
| [WasmCert] | WasmCert-Coq |

---

## Appendix C. Dated evidence note (non-normative)

**As of 2026-08-18.** Everything in this appendix is a claim about the state of external artifacts on that date. It is evidence for schedule and start-from decisions, not a premise of any requirement, and it goes stale without amending anything.

**What the founding lineage leaves to inherit: nothing executable.** The TALx86 toolset survives as a 2002 all-rights-reserved download; the Twelf mechanization of foundational TAL and Princeton's LTAL checker were never publicly released; the Necula-line certifying compilers died closed-source. Appendix A's first two groups therefore contribute design and metatheory only, with the foundational-PCC trusted-base accounting (a sub-thousand-line C checker over a fixed logic signature) the closest published relative of §10.6's audit budget.

**What a `cheri-rv64` instantiation stands on today.** The CHERI-RISC-V Sail model's generated Coq is the one existing route to theorems over the real ISA, and no published development has yet proved anything over it, so the profile instantiation is a first rather than a repetition. Katamaran is an actively developed contract verifier over a Sail-like embedding with a capability-machine case study, the natural engine for per-instruction lemmas and cited-invariant premises. WasmCert-Coq is a maintained skeleton for a checker verified sound and complete against its type system, though for a bytecode rather than a native instruction set, and its published account left end-to-end work unfinished. The Isla-trace route of Islaris and Morello-Cerise is the current means of taming a full model. CT-Wasm's extracted verified checker is the taint attribute's port target, its artifact pinned to a 2017 Isabelle.

**Deployment and revival evidence for the certificate architecture.** The JVM's split verifier (stack-map frames, mandatory since class-file version 51) is this architecture in production at large scale, its type-checking core a few thousand lines over a richer vocabulary than §8.2's. Klein and Nipkow's account is re-checked against every Isabelle release in the Archive of Formal Proofs. CertrBPF (CAV 2022) is a Coq-verified admission checker extracted to C and shipped in an embedded operating system. BCF (SOSP 2025) has the Linux eBPF verifier accept load-time certificates proved in user space and checked by a small kernel-side checker.

**Adjacent active lines.** Universal contracts and secure calling conventions on CHERI-RISC-V, and taint-typed assembly for cryptographic code, each approach one slice of the menu; none approaches the assembly language.

---

## Appendix D. Change control (non-normative)

The order in which the normative content above must be settled, and the order any future amendment should follow, because each step changes the theorem the next one must prove:

1. Routing granularity and per-facet guarantee scope (§4.2, §5.4).
2. How inserted checks map to the moves (§5.2, §8.6).
3. The profile matrix and the assumption ledger (§6, §5.5).
4. Certificate-to-artifact binding and the checker's formal input (§9, §8).
5. The checker algorithm and its complexity contract (§10.2, §10.3).
6. The typing rules and the soundness theorem (§8.4, §11).
7. The conformance suites (§13), and only then an implementation.
