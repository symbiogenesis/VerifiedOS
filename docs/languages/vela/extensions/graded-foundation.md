# Graded dependent foundation

> Non-normative Q25a checking interfaces and schematic derivations. Start with the [primary Vela design and examples](../verification-strategy.md). [Q25](../../../../PLAN.md#q-assessment-actions) owns design gates; the [requirements register](../../../requirements-register.md) remains authoritative. No implementation, checked metatheory, accepted axiom or qualified binary is supplied.

## Scope and research boundary

The [first supported release](../first-release.md#release-boundary) uses fixed
unrestricted, affine, relevant-verdict and linear-obligation cases, stable
dependent indices and explicit runtime/erased phases. Its ownership, restoration,
trace and target-cost laws remain mandatory; arbitrary grade algebras do not
replace them. This dossier specifies the separately gated extension to lawful
computation/type-use domains. Its generic demand vectors, domain inference and
multi-shot composition are not prerequisites for the first synchronous product.
A named client must justify the extension against the fixed discipline under
the [delivery plan](../../../../PLAN.md#vela-first-release-delivery) and the
[selection protocol](#extension-selection-and-qualification) below.

The [graded design](../verification-strategy.md#graded-dependent-foundation)
separates computation/type dependence, lawful extensible grades and CIC
interpretation, preserving the
[synchronous resource interpretation](../core-design.md#judgments-and-interpretations).
[Handlers](handlers-async.md) and [mutability](interior-mutability.md) consume the
[resource interface](#resource-and-computation-interface) when their own increments
are selected; [Q25d](full-language-review.md) records composition obligations.

Every law in this dossier must be proved about the elaboration's image in an
existing anchor, under [the untrusted-elaboration boundary](../../../spec.md#r-05-020a).
The displayed judgments describe proposed syntax-directed evidence construction.
They carry no independent source evaluation or admission authority. Substitution
and structural-rule theorems relate the interpreted images of the original and
transformed syntax, using the selected CIC/resource interpretation; preservation
and erasure quantify over that interpretation's computation and observations.
The source-correspondence relation must bind the actual parsed/resolved source,
generated term and reconstructed evidence. Merely renaming a source calculus or
kernel-checking an unrelated term establishes none of those laws. Their proofs
and the required concrete resource instance remain outstanding.

Sources: Moon, Eades and Orchard's [GrTT v2](https://arxiv.org/pdf/2010.13163v2) and Gerty ESOP 2021 prototype; Choudhury, Eades, Eisenberg and Weirich's [GraD v2](https://arxiv.org/html/2011.04070v2); Abel, Danielsson and Eriksson's [ICFP 2023 erasure development](https://research.chalmers.se/en/publication/537991), [extended 30 April 2026](https://arxiv.org/abs/2603.29716). The [strategy](../verification-strategy.md#reading-the-graded-type-claims) owns the wider comparison. No source/dependency is incorporated.

GrTT supplies two use vectors and dependency bookkeeping. Its call-by-name, restricted normalization result is pen-and-paper; the external-solver prototype is unverified against it. Neither establishes Vela's effectful call-by-value calculus. GraD motivates usage-aware soundness and shows Boolean grade one need not mean unique use; its selected syntactic mechanization and heap result supply no CHERI ownership theorem. The machine-checked Agda erasure donor restricts modalities/contexts, including weak-pair erased elimination, and proves extraction value preservation for natural-number programs under a restricted modality class. It trusts Agda's checker; the MIT repository covers several papers, so the tag identifies this artifact. Vela still owes CIC erasure/elimination and mutable-computation connections.

## Extension selection and qualification

The [delivery plan](../../../../PLAN.md#vela-first-release-delivery) selects a
concrete client after the synchronous resource discipline qualifies. Freeze its
behavior, resource/representation contract, evidence endpoint, toolchain, positive
cases and semantic refusals independently of the proposed grading API. Compare the following
increments in order; stop when the smaller supported account meets the client's
needs without a material benefit from the next increment.

| Candidate | Comparison and admission evidence |
| --- | --- |
| Fixed use modes and checked library contracts | Baseline: state-indexed operations and natural-valued exact or bounded trace judgments, using the existing ownership and phase rules. Retain the client's actual proof and maintenance obligations. |
| A bounded `NatExact`/`NatBound` extension | Identify the repeated-use or composition obligation that source grading improves. Qualify the selected boxes, polymorphism and arithmetic with checked domain laws, usage-aware call-by-value interpretation and exact-source correspondence. Connect value demand to the requested trace property explicitly; grade arithmetic alone is not an invocation-count theorem. |
| General domains or separate type-use accounting | Select each independently. For domains, demonstrate an analysis the qualified fixed instances cannot conveniently express and prove its interpretation/composition laws. For type use, compare the proposed vectors and dependency rows with the simplest sound dependency account meeting the same contract; identify the additional dependency or parametricity guarantee, or measured authoring benefit, that warrants the extra machinery. |

Before a trial, freeze material-benefit thresholds and budgets for annotations,
proof/review/repair effort, diagnostic quality, checking time and memory. Separate
demand reconstruction, constraint search and certificate/kernel replay; record
fresh and changed-input runs, unresolved goals and budget refusals. Keep the same
behavior, preconditions and assurance endpoint across candidates, and account for
setup and maintenance separately from recurring benefit. Run benchmarks and proof
acceptance through the [hosted validation handoff](../../../../AGENTS.md#tool-execution-and-validation).
Absent benefit, missing prerequisite laws or exhausted budgets retain the smaller
qualified discipline; none permits weakening a client contract or treating
unsupported syntax as a semantic rejection.

Gerty's [substitution-skipping experiment](../verification-strategy.md#reading-the-graded-type-claims)
is a separate optional optimization. It requires a proved zero-type-use
irrelevance condition for the selected domain, agreement with ordinary checked
substitution, and measured total checking benefit including any new solver calls.
Evaluate it within an already justified graded implementation; this does not
commission a separate verification tool solely for speed.
Retaining that optimization is not a prerequisite for adopting useful type-use
reasoning, and its donor measurements establish no Vela speedup.

### Conditional usability producers

Granule's [derived distributive combinators](https://arxiv.org/abs/2112.14966)
move a modality through a data type in supported directions, reducing manual
composition code. Its [grade-directed synthesis](https://doi.org/10.1007/978-3-031-57262-3_4)
uses resource constraints to narrow program search. These are separate candidate
producers of ordinary checked terms, not consequences of accepting grade syntax.
Their published implementations supply no Vela compatibility or correctness
evidence, and no donor source is incorporated here.

A named library client must first demonstrate repetitive conversions or a useful
bounded synthesis task against ordinary proved combinators or existing proof
search. Derivation fixes the supported type constructors, conversion direction
and grade premises; it cannot assume `Box_q (F A)` and `F (Box_q A)` are always
interchangeable. Synthesis fixes the grammar, component library, intended behavior
and search budget; grades alone need not determine behavior or evaluation order.
Failed search supplies no proof that the requested program is impossible.
Both retain transitive capture, ownership, phase and effect premises and produce
inspectable terms with replayable evidence under the unchanged assumption audit.
Qualification includes a valid client, an invalid domain/duplication premise,
changed source/dependency/domain bindings, a well-typed but behaviorally wrong candidate and
bounded failure with no accepted partial result. Measure recurring client benefit
and total evidence-checking cost before retention.

The existing [frontend and soundness owners](full-language-review.md#existing-owners-and-where-each-decision-is-taken)
own selected grading increments. Derived combinators reuse
[`vela-meta`'s generation boundary](metaprogramming.md#qualification); bounded
synthesis retains the same untrusted-producer and source-correspondence rules.
Each selected producer needs its own priced checklist predicate before work;
existing Q25 design credit and conditional estimates commission neither producer.
All selected increments still owe the applicable [GF obligations](#q25d-debts-and-acceptance-boundary).

## Dimensions and lawful domains

Each evidence-construction judgment fixes `S`: qualified definitions, universe constraints, grade identities, primitive contracts, logic, representation and observation model. Its conclusion names the term whose image is checked. `Type i : Type (i+1)` uses CIC universe checking; cumulative conversion uses checked universe inequalities. No `Type : Type`, new conversion, global UIP, proof irrelevance or extensionality axiom is added. Transports require accepted terms and the existing assumption audit.

| Dimension | Meaning | Evidence it cannot replace |
| --- | --- | --- |
| Computation use `u` | Demand on stable values in the selected graded value semantics | Invocation counts, physical copies, exclusive permission or WCET |
| Type use `v` and dependency rows `M` | Demand in the result type and in every declaration's type | Runtime availability of an erased index |
| Phase and representation `p, rho` | Runtime, specification or proof; represented or erased at the selected ABI | Protocol disposal or secret zeroization |
| Resource context `Delta` | Live ownership, loans, restoration and other kinded authority under the selected logic | A generic numeric, effect or security annotation |
| Effects `E` | Allowed operation footprints, including transitive calls and captures | Permission to perform those operations |
| Trace contract `T` | Named source events, their order and exact counts or upper bounds | Surviving machine calls or instruction timing |
| Target bound `W` | The existing final-CFG cost judgment against pinned Sail timing | A source use or event count without its transport theorem |

In the extensible proposal, a domain is a sealed CIC record, never an executable admission plugin. Its identity binds carrier universe, grade syntax, operations, equality/order proofs, structural permissions, certificate interpreter and interpretation in the existing anchor; clients cannot replace its dictionary behind a qualified signature. The first release does not accept arbitrary domain dictionaries or require their general inference procedure.

```text
q ::= 0_D | 1_D | named_constant_D | alpha_D | q +_D q | q *_D q
    | certified_domain_operation_D(q, ...)

Domain D:
  carrier Q : Type i; equivalence =D; preorder <=D
  additive commutative monoid (+,0); multiplicative commutative monoid (*,1)
  left/right distributivity; multiplicative zero annihilation
  congruence and monotonicity of both operations
  admissible weakening/contraction/scaling relations with proved meanings
  InterpretUse, InterpretTypeUse, CheckCertificate and soundness obligations
```

`q <=D q'` admits demand `q` under allowance `q'`; exact-use claims may require equality. These rules require commuting multiplication for promotion/motive scaling. Noncommutative domains need reviewed ordered-action rules under `GF-domain`; custom operations need composition laws. Incomparable branch demands require proved bounds or result-indexed contracts, never assumed joins. Products need compatible subject/trace interpretations as well as component arithmetic.

`NatExact` uses natural addition/multiplication and equality as admission order. `NatBound` uses ordinary order: `0 <= 1` permits zero uses under a one-use bound, not exact-once use. Boolean presence uses `or`/`and`, so `1+1=1` records presence rather than cardinality. These proposed instances still need record/interpretation proofs.

Zero-use erasure needs a theorem excluding relevant observations; nontriviality, positivity and no zero divisors alone do not prove it. Exact cardinality needs faithful count semantics and an order that cannot relax zero/two to exact one. Unique authority additionally needs spatial exclusivity and representation; security needs relational control/address observations. Idempotent grade `1` supplies none of these.

## Stable telescope and dependency bookkeeping

`J(M; u; v; Gamma |- t:A)` is the proposed pure evidence-construction interface, with `S` implicit: it must elaborate `t`, `A` and the demand interpretation to checked terms and a theorem about their image. `Gamma` is an ordered telescope of stable values/types, immutable snapshots and logical identities. Runtime handles are stable descriptors; permissions stay in `Delta`. Stability alone grants no permission to copy the referent, and indices never evaluate unsynchronized mutable reads.

`M[i]` records preceding declarations' use in `Gamma[i]`'s type, with a well-formed derivation. Vectors `u` and `v` have one component per declaration, recording use in `t` and `A`; `v` is not a sum of declaration rows. All zero-padded rows/vectors refer to the same ordered telescope.

```text
CTX-EXT: J(M; a; 0; Gamma |- A : Type i)
         implies WF(M appended with a; Gamma, x:A).

VAR:     WF(M; Gamma), Gamma[i] = x:A
         implies J(M; unit_vector(i); padded(M[i]); Gamma |- x:A).

UNIV:    WF(M; Gamma)
         implies J(M; 0; 0; Gamma |- Type i : Type (i+1)).
```

A runtime variable rule also requires a represented binding in `rho`; a specification variable rule has no permission to become a runtime operand. Tracked resources never enter the duplicable pure context by embedding their propositions in a record. Their names may index predicates there; the predicates' ownership interpretation stays spatial.

### Functions and application

The following rules describe pure values and type expressions. `Pi x:(s,r) A. B` advertises use `s` of `x` by the function body and use `r` of `x` in `B`. Let the domain type have demand `a`, and the codomain have demand `(b,r)` under `Gamma,x:A`.

```text
PI:  J(M; a; 0; Gamma |- A : Type i)
     J(M,a; (b,r); 0; Gamma,x:A |- B : Type j)
     ---------------------------------------------------------
     J(M; a+b; 0; Gamma |- Pi x:(s,r) A.B : Type max(i,j))

LAM: J(M,a; (w,s); (b,r); Gamma,x:A |- t:B), with PI premises
     ---------------------------------------------------------
     J(M; w; a+b; Gamma |- lambda x.t : Pi x:(s,r) A.B)

APP: J(M; w; a+b; Gamma |- f : Pi x:(s,r) A.B)
     J(M; z; a; Gamma |- v:A), with PI premises
     ---------------------------------------------------------
     J(M; w+s*z; b+r*z; Gamma |- f v : B[v/x])
```

Application type use is `b+r*z`: codomain substitution removes the domain demand `a`. The producer must reconstruct this equation and its meaning for the elaborated application; it is not an extra kernel conversion rule. Combined substitution/preservation of interpreted images remain debts below. Resource-carrying closures also record transitive environment and call mode; grade arithmetic alone cannot justify capture duplication.

Vela computations evaluate left to right by value. Elaborate an effectful argument as `bind x <- c; call f x`: evaluate `c` once, record its trace/effects and resource exit, then apply the value rule to `x`. Parameter use zero does not erase `c`'s effects, failures or mandatory result. Parameter use two does not execute `c` twice. Moving this bind across a handler, mutation or cancellation checkpoint needs an explicit preservation proof.

Torczon et al.'s [Effects and Coeffects in Call-by-Push-Value](https://doi.org/10.1145/3689750)
(OOPSLA 2024; [extended paper](https://arxiv.org/abs/2311.11795v2)) mechanizes
effect/coeffect soundness and CBV/CBN translations in Coq for clock effects and
variable-use accounting. Its resource semantics preserves evaluation of effectful
computations whose results are unused. This supports the value/computation split
above; dependent indices, mutable ownership and handlers remain Vela's
`GF-cbv` and `GF-control-mutation` debts. The artifact's proof terms are not read
or replayed here, and no source is incorporated.

Lorenzen et al.'s [Oxidizing OCaml with Modal Memory Management, §5.1](https://antonlorenzen.de/papers/oxidizing-ocaml-modal-memory-management.pdf)
(ICFP 2024) gives the complementary promotion counterexample: a repeatedly usable
file-opening function and argument do not make the returned file repeatedly
usable. Their value-only promotion blocks that derivation. Vela likewise promotes
pure values in `Box_q` below, after evaluation; duplicating a resource-carrying
result still needs its own capture and `Dup` evidence. An initializer's use grade
cannot erase its acquisition, cleanup or effects. These are design references, not a checked
metatheory for Vela.

### Substitution and structural rules

For a pure value substitution `Gamma, x:A, Xi |- t:B` with `Gamma |- v:A`, let `z` be the subject-use vector of `v`. For any demand row `d=(d_G,d_x,d_X)` after `x`, define:

```text
substDemand(d,x,z) = (d_G + d_x*z, d_X)
Gamma, x:A, Xi   becomes   Gamma, Xi[v/x]
u               becomes   substDemand(u,x,z)
v_type          becomes   substDemand(v_type,x,z)
each later M row becomes   substDemand(that row,x,z)
```

Earlier rows stay fixed; `x`'s row disappears. Capture-avoiding substitution also updates types, motives, index-dependent grades, captures and exit predicates. Recheck the whole telescope: updating conclusion vectors alone leaves a later `y:B(x)` stale. `GF-substitution` owes simultaneous typing/well-formedness and interpretation-agreement proofs for the elaborated images before and after substitution; this is no unchecked solver rewrite, and computations cannot replace stable indices.

| Structural operation | Admissibility condition |
| --- | --- |
| Extend an unused declaration | Construct its type row, pad subsequent rows and both demand vectors with zero; retain all prior dependencies. |
| Remove a declaration | Its demand is zero in the term, result type and every retained declaration row, or substitute a checked stable witness throughout. `u[x]=0` alone is insufficient. |
| Exchange declarations | A dependency-preserving permutation with all rows, identities and captures renamed; no exchange across an actual dependency. |
| Contract pure descriptors | Add their demands and reindex the dependent telescope using checked equality. Any operation through them still needs the live spatial permission. |
| Weaken an advertised bound | Supply the domain's order proof; exact-use declarations admit only equality. No implicit coercion to an approximate domain. |
| Drop, duplicate or scale a resource | Supply `Dispose`, `Dup` or the relevant repeated-use protocol below; no generic telescope rule transforms `Delta`. |

### Dependent data and elimination

`Sigma x:^r A. B` binds `x` only in the second component's type. Its formation uses the same `a,b,r` premises as `PI`. Pair introduction requires component derivations with subject demands `z,w`, and the second component's type demand exactly `b+r*z`; the conclusion has subject demand `z+w` and type demand `a+b`.

A tensor-style dependent eliminator has an explicit motive `C(p)` and cannot independently invent how an opaque pair's demand splits between its fields:

```text
p : Sigma x:^r A.B                  subject demand z
C(p) : Type k under Gamma,p         demand (c,kappa)
body : C((x,y)) under Gamma,x:A,y:B  subject (w,s,s)
                                    type (c,kappa,kappa)
----------------------------------------------------------------
match p as (x,y) in body : C(p)      subject w+s*z
                                    type c+kappa*z
```

The premise includes the full well-formed telescope, in particular the dependency `r` of `y`'s type on `x`, and the checked motive substitution. A desired asymmetric use of fields needs explicit graded modalities or another separately proved eliminator. An erased weak pair cannot supply a runtime witness, tag or projection. Constructor inspection at runtime always needs a represented scrutinee; a domain where zero denotes a security level cannot authorize erased matching.

`Box_q A` packages a pure value for demand `q`. Introduction scales the value's subject vector by `q` and leaves the type vector fixed. Elimination uses a body with bound-variable subject demand `q`; if the motive depends on the box with demand `kappa`, the body's type demand for its unboxed variable is `q*kappa`. Eliminating a box of demand `z` adds `z` to the body's remaining subject vector and `kappa*z` to its remaining type vector. Promotion cannot hide evaluation effects or manufacture `Dup` for captured owners. Field representations and box erasure remain explicit in `rho`.

Finite sums use an explicit motive and branch-specific resource predicates. Each branch checks the same advertised demand under the selected order, with constructor-field dependencies substituted. Exact unequal branch counts must remain result-indexed or use a separately advertised bound; adding mutually exclusive branch counts claims the wrong trace. Bounded iteration supplies an inductive invariant, grade recurrence and termination measure. General inductive eliminators require a checked constructor/motive resource rule; CIC's acceptance of an ungraded recursor alone supplies no graded elimination theorem.

## Resource and computation interface

The common evidence-construction interface is:

```text
S; M; Gamma; Delta_in |- c : Exit(A,Q)
  [use u; type-use v; captures C; effects E; trace T;
   phase p; representation rho; exit duties O]

Q(tag,value) = Delta_out for that represented exit
```

Its generated theorem relates entry state, execution of the elaborated image and every reachable exit under the existing anchor. The chosen logic interprets `Delta` as ownership, loans/restoration, protocols, effect/security permissions; `Own(id,shape,snapshot)` is an interface, not a supplied CHERI predicate. Identity cannot construct authority. `Q` includes captures transferred in results/frames; branch-dependent owners retain their discriminant until a join/restoration proof removes it. The first release consumes the synchronous resource portion through its fixed use discipline; `Suspend`, concurrent `Share` and multi-shot `Dup` compose only in separately selected extensions.

| Interface obligation | Required evidence |
| --- | --- |
| `Capture(C,Delta)` | The whole transitive retained environment, including handlers, tasks, stored continuations and cell fields, has identified kinded resources, lifetimes, effects and representation. Resources used only during evaluation are recorded separately. |
| `Dup(C,Delta)` | A semantic split supporting both uses under interference, lifetime and protocol conditions. Duplicable immutable snapshots qualify only under their actual representation; an exclusive owner, exclusive loan or single-use token has no default instance. |
| `Dispose(Delta,exit)` | An explicit terminal/resource-returning transition for every obligation. Ordinary affine permission discard does not discharge a protocol, must-erase value or mandatory examined verdict. |
| `Suspend(C,Delta,rho,O)` | Stable represented storage, live loan ancestry, closed invariants and a bounded restoration/cleanup path at the declared checkpoint; no escaping reference into a moved frame. |
| `Transfer(domain,Delta)` | Permission and representation transport to the receiving execution domain, preserving exclusivity, lifetime, publication ordering and the manifest join. |
| `Share(protocol,Delta)` | The declared concurrent operations preserve an invariant under actual interference and the pinned memory model. A shared handle grants only those operations. |

`Dispose` is an explicit computation with effects and, where relevant, writes; proof erasure does not zero machine registers or spill slots. Mandatory verdict elimination names the outcome as required by [R-05-097 through R-05-100](../../../spec.md#r-05-097). Source ownership connects to the [exclusive-access and composition obligations](../../../spec.md#r-05-096a); borrowing cannot derive an overlapping permission merely because it preserves a grade.

Sequencing composes outcome-indexed resource transitions and concatenates traces; effect sets take union. Repeating a callback or resumption needs its repeatable calling contract and fresh separated per-invocation inputs `Delta_i`. For `k` invocations, a per-call source-event law gives the corresponding sum or `k`-fold count. A grade on the callable does not supply that law, termination, invocation order or a claim about optimized machine calls. Multi-shot capture needs `Dup` for the entire retained continuation context even if each explicit argument is pure.

Mutation updates the owner's snapshot; shape changes consume the old owner and return an appropriately indexed one. Copied snapshots remain historical until newly related to current contents. Suspension/reentry with open cell invariants needs a stronger protocol. Grades authorize neither shared mutable capabilities nor unsupported atomics.

## Schematic derivations and invalid neighbors

These are hand derivations for the proposed extensible producer over inhabited pure inputs and explicit domains. They specify equations and interpretation obligations that a selected implementation would reconstruct and check; no independent source metatheory or executed verdict is supplied. Each negative preserves the positive's representations and unrelated resources; parsing failure or absent implementation does not establish its intended refusal. The exact type-demand identity below is an extension qualification case, not a required annotation for ordinary first-release identity functions.

### Pure dependent identity

In `NatExact`, take `Gamma = a:Type i, x:a`. Context rows are `M=((),(1))`. `VAR` yields `u=(0,1)` and `v=(1,0)` for `x:a`. `LAM` over `x` gives `lambda x.x : Pi x:(1,0) a.a`, subject use of `a` zero and type use `1+1=2`. Abstracting `a` yields:

```text
id : Pi a:(0,2) Type i. Pi x:(1,0) a.a
id = lambda a. lambda x. x
```

Choose `a=Byte`, `x=7` for an inhabited runtime specialization: the type argument is erased and the byte remains represented. Changing the type-use annotation of `a` from two to one fails the final abstraction's `2=1` equality. Changing `x`'s computation grade to zero fails `1=0`; changing it to two fails `1=2`. No claim about owning byte storage follows from these scalar examples.

For an inhabited dependent value, take the pure constructors `nil:Vec Byte 0` and `cons:Byte -> Vec Byte k -> Vec Byte (k+1)` with their explicit index/element modalities. Pair introduction checks `(2,cons 7 (cons 9 nil)) : Sigma k:Nat.Vec Byte k`: substitution reduces the second component's expected index to two, matching its constructor derivation. Packing that same vector under three fails the index equality `2=3`. The admitted constructor grades and their preservation theorem are `GF-elimination` duties, so this hand derivation supplies no executed recursor qualification.

### Runtime-dependent packet

Fix capacity `N=4`, represented immutable length `n=2` and a private initialized buffer containing bytes `7,9,0,0`. Entry resources supply exclusive `Own(r,4,[7,9,0,0])`; a checked extent/view contract supplies a represented descriptor `h:Handle(r,n)` permitting the selected two-byte prefix while retaining the appropriate parent/restoration state. No arbitrary exact CHERI narrowing is assumed: the actual capability extent and source footprint belong to that contract.

In `Gamma=r:Identity,n:Nat,h:Handle(r,n)`, the `h` declaration has a type dependency on both `r` and `n`. Pair introduction forms `(n,h):Sigma k:Nat.Handle(r,k)`. Its subject demand has one `n` and one `h`; checking `h` substitutes `n` in the second component's type. The result hides `n` existentially while retaining it physically. An erased proof of `n<=N` attaches through an explicit erased field modality and contributes no runtime operand.

A once-only match binds represented `k` and descriptor `p` and repacks `(k,p)` with the same resource view. Both field demands are one, so the dependent eliminator applies with `s=1`; the result's resource predicate retains `r` and the loan/restoration obligation. A subsequent bounded reader uses the retained length under its own demand recurrence and consumes/returns permission exactly as declared, rather than inheriting a once-use count for its loop. The concrete read/view/restoration lemmas remain `GF-resource` entry debts.

Changing only `n` to erased while keeping the reader's runtime bound fails the phase/representation premise. Packing `h:Handle(r,2)` behind index three fails dependent pair checking without a valid transport. In the `h:Handle(r,n)` variable subderivation, computation use of `n` is zero; deleting `n` from that telescope nevertheless leaves the retained `h` type unformed. Resizing under a different operation and retaining the old current-length refinement fails that transition's output predicate.

### Graded callback and shared service join

A pure callback over an immutable copied two-byte snapshot has a shared-call contract and no owned mutable capture. A total bounded client invokes it twice in declared order. The source trace law gives `CallCount(callback)=1+1=2`; a `NatExact` callable allowance of two supports the two value uses, while `Dup` handles its immutable environment. Allowance one fails `2=1`. A branch invoking it once must either return an indexed count or advertise a bound; silently keeping exact two fails its trace contract.

The deferred Q25 composition fixture retains its packet/frame owner and unique service allowance outside the pure handler's capture delimiter while a child updates a scalar atomic accepted-byte counter. Its `AddOnce(request,n)` allowance is a protocol token in `Delta`; `n` is represented, the overflow bound is erased evidence, and the service handle exposes only its proved atomic operation. Two resumptions of the pure callback continuation cannot capture the child update that consumes this allowance. The AMO transition and cancellation commit behavior belong to Q25c and Q25b. Replacing the callback environment with a cell retaining the owner fails `Dup`; declaring the surface callback unchanged cannot hide that transitive capture. This fixture preserves a future interaction test; it is not the first software milestone or evidence that those extensions are needed.

The Boolean presence calculation `1+1=1` accepts two pure uses as presence. Attempting the same contraction on `AddOnce` still requires a spatial/protocol split that its unique transition cannot provide. This is the invalid authority neighbor even when grade constraints succeed. Dropping the child verdict or must-erase data similarly fails `Dispose`; use/erasure annotations cannot manufacture terminal completion or wiping.

## Inference, specialization and admission

The [staging contract](metaprogramming.md#evaluation-and-phase-boundaries) keeps
compile-time availability independent of computation use, type use, phase and
representation. A ghost binder or a zero grade does not make a runtime value
known during generation. Conversely, a static constant may be materialized in the
runtime representation when execution needs it. Describing a graded type or
copying generated syntax supplies no `Dup`, `Dispose` or ownership premise;
generated resource uses undergo this dossier's ordinary checks.

The first release uses bidirectional checking with its fixed use modes, explicit call modes/captures and a bounded refinement tier. In the separately selected extensible proposal, public domain identities and grade variables/constraints additionally enter those interfaces. Rules propose local demands; checked CIC terms establish grade equalities/orders and their interpretation. Symbolic multiplication, dependent unification, arbitrary operations and recursors may leave explicit goals. No principal-grade inference or complete procedure for all domains is promised.

A constraint result binds its proposition, domain dictionary, substitutions and replayable certificate/term. Timeout, inconsistent model, unknown law or reconstruction failure leaves unresolved/refused evidence. Search cannot weaken exact declarations into bounds. Grade-polymorphic definitions check under explicit constraints, discharged at every public instantiation. Runtime natural indices stay represented even when indexing erased trace bounds; they cannot retrospectively select layout.

Specialization fixes phase, convention, layout and erasure before emission. Represented/erased grade instantiations need separately checked ABIs unless a uniform representation and erasure theorem is supplied. The device gains no runtime grade dictionary or open-term normalization. This source specialization does not authorize cloning at the separate composition-time singleton-call rewrite.

`SourcePackage` binds source/generated inputs, domain implementations/laws, elaborated constraints, reconstructed proofs, implicits/transports, representation and exact core computation. Parsing, resolution, instance selection and desugaring need correspondence; old core proofs cannot accept changed source. Erasure preserves results, control, effects, resource behavior and requested observations under that representation, relating retained behavior across instances differing only in erased proofs. Type-checking an irrelevant term is insufficient.

[R-05-132 through R-05-134](../../../spec.md#r-05-132) keep the source/TAL boundary: compile source obligations into the existing admitted attributes where their actual rules suffice, and carry the remaining proved obligations as CIC terms. General source domains, dependent normalization and grade-polymorphic dictionaries do not become TAL attributes. A requested new attribute would need that requirement's amendment demonstration and the TAL's own extension conditions. This dossier proposes none. Final-source correspondence, ABI, optimization, timing, linking and Sail evidence remain with the existing compiler/admission owners.

## Q25d debts and acceptance boundary

These debt keys are neither Rocq constants, schedule cells nor assumptions. Q25d joins them with [Q21 packages](../core-design.md#proof-obligations-and-proposed-work-packages) and the [foundation map](../../../hardware/cheri-foundation-map.md), recording owner and estimate boundaries in [pricing](full-language-review.md#reviewed-implementation-pricing). All theorem subjects below are elaborated images in the selected existing anchor. The [first-release plan](../../../../PLAN.md#vela-first-release-delivery) selects the fixed resource/phase/correspondence obligations it actually uses; it does not commission every generic-domain or control/mutation debt. Unestablished foundation work stays explicitly `unpriced` when a responsible range is unavailable.

| Debt key | Required artifact and refusal predicate |
| --- | --- |
| `GF-domain` | Construct domain records, certificate interpreters and interpretation laws; reject Boolean-to-exact/ownership coercion and unsound order relaxation. Includes cross-domain compatibility rather than duplicating an event-count pilot. |
| `GF-substitution` | Mechanize telescope well-formedness, simultaneous substitution, both vector transformations, grade substitution and dependency-preserving structural rules as checked interpretation theorems relating the elaborated images. Reject a later declaration retaining an unsubstituted index; no independent source reduction supplies a theorem premise. |
| `GF-elimination` | Prove dependent functions, pairs, boxes, indexed sums and admitted recursors preserve grades and well-formed motives. Construct positive asymmetric-field examples with their modality premises; refuse erased runtime discriminants. |
| `GF-cbv` | Connect the selected demand interpretation to explicitly sequenced call-by-value images, captures and outcome-indexed exits in the anchor. Prove usage-aware resource preservation, including zero-demand effectful arguments and repeated pure values. Ordinary progress/preservation alone is insufficient. |
| `GF-resource` | Instantiate spatial ownership, views, restoration and kinded authority on the selected logic/CHERI representation; construct inhabited packet entry states. Q2c retains concrete foundation ownership; these rules cannot assume its missing laws. |
| `GF-control-mutation` | Compose Capture/Dup/Dispose/Suspend/Transfer/Share with Q25b/Q25c, including repeated continuations, hidden cell captures, snapshots, cancellation and fresh per-resumption resources. Preserve the synchronous slice as a conservative restriction. |
| `GF-erasure-source` | Prove phase separation, representation-specific erasure and source/elaboration correspondence under checked CIC assumptions; qualify domain inference diagnostics and stale-source rejection. Reuse retained frontend/diagnostic duties once. |
| `GF-target` | Connect the selected source representation, event projections and obligations through the existing compiler route to actual TAL/Sail artifacts. No source count substitutes for final cost or arbitrary-context preservation. |

Q25a design acceptance requires the explicit rules, derivations, rejecting neighbors and debts, closing none of the debts or unimplemented negatives and claiming no soundness, estimate reduction or register amendment. Q25d's independent combined-client review and integrated document gates remain required for design credit.
