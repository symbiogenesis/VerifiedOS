# Graded dependent foundation

> Non-normative Q25a checking interfaces and schematic derivations. Start with the [primary Vela design and examples](verification-strategy.md). [Q25](../../../PLAN.md#q-assessment-actions) owns design gates; the [requirements register](../../requirements-register.md) remains authoritative. No implementation, checked metatheory, accepted axiom or qualified binary is supplied.

## Scope and research boundary

The [graded design](verification-strategy.md#graded-dependent-foundation) separates computation/type dependence, lawful extensible grades and CIC interpretation, preserving the [synchronous resource interpretation](core-design.md#judgments-and-interpretations). [Handlers](handlers-async.md) and [mutability](interior-mutability.md) consume the [resource interface](#resource-and-computation-interface); [Q25d](full-language-review.md) reviews composition and assigns missing implementation work.

Sources: Moon, Eades and Orchard's [GrTT v2](https://arxiv.org/pdf/2010.13163v2) and Gerty ESOP 2021 prototype; Choudhury, Eades, Eisenberg and Weirich's [GraD v2](https://arxiv.org/html/2011.04070v2); Abel, Danielsson and Eriksson's [ICFP 2023 erasure development](https://research.chalmers.se/en/publication/537991), [extended 30 April 2026](https://arxiv.org/abs/2603.29716). The [strategy](verification-strategy.md#reading-the-graded-type-claims) owns the wider comparison. No source/dependency is incorporated.

GrTT supplies two use vectors and dependency bookkeeping. Its call-by-name, restricted normalization result is pen-and-paper; the external-solver prototype is unverified against it. Neither establishes Vela's effectful call-by-value calculus. GraD motivates usage-aware soundness and shows Boolean grade one need not mean unique use; its selected syntactic mechanization and heap result supply no CHERI ownership theorem. The machine-checked Agda erasure donor restricts modalities/contexts, including weak-pair erased elimination, and proves extraction value preservation for natural-number programs under a restricted modality class. It trusts Agda's checker; the MIT repository covers several papers, so the tag identifies this artifact. Vela still owes CIC erasure/elimination and mutable-computation connections.

## Dimensions and lawful domains

Each judgment fixes `S`: qualified definitions, universe constraints, grade identities, primitive contracts, logic, representation and observation model. `Type i : Type (i+1)` uses CIC universe checking; cumulative conversion uses checked universe inequalities. No `Type : Type`, new conversion, global UIP, proof irrelevance or extensionality axiom is added. Transports require accepted terms and the existing assumption audit.

| Dimension | Meaning | Evidence it cannot replace |
| --- | --- | --- |
| Computation use `u` | Demand on stable values in the selected graded value semantics | Invocation counts, physical copies, exclusive permission or WCET |
| Type use `v` and dependency rows `M` | Demand in the result type and in every declaration's type | Runtime availability of an erased index |
| Phase and representation `p, rho` | Runtime, specification or proof; represented or erased at the selected ABI | Protocol disposal or secret zeroization |
| Resource context `Delta` | Live ownership, loans, restoration and other kinded authority under the selected logic | A generic numeric, effect or security annotation |
| Effects `E` | Allowed operation footprints, including transitive calls and captures | Permission to perform those operations |
| Trace contract `T` | Named source events, their order and exact counts or upper bounds | Surviving machine calls or instruction timing |
| Target bound `W` | The existing final-CFG cost judgment against pinned Sail timing | A source use or event count without its transport theorem |

A domain is a sealed CIC record, never an executable admission plugin. Its identity binds carrier universe, grade syntax, operations, equality/order proofs, structural permissions, certificate interpreter and semantics; clients cannot replace its dictionary behind a qualified signature.

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

`J(M; u; v; Gamma |- t:A)` is the pure judgment, with `S` implicit. `Gamma` is an ordered telescope of stable values/types, immutable snapshots and logical identities. Runtime handles are stable descriptors; permissions stay in `Delta`. Stability alone grants no permission to copy the referent, and indices never evaluate unsynchronized mutable reads.

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

Application type use is `b+r*z`: codomain substitution removes the domain demand `a`. Combined substitution/preservation remain debts below. Resource-carrying closures also record transitive environment and call mode; grade arithmetic alone cannot justify capture duplication.

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
pure values in `Box_q` below, after evaluation; a resource-carrying result still
needs its own capture and `Dup` evidence. An initializer's use grade cannot erase
its acquisition, cleanup or effects. These are design references, not a checked
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

Earlier rows stay fixed; `x`'s row disappears. Capture-avoiding substitution also updates types, motives, index-dependent grades, captures and exit predicates. Recheck the whole telescope: updating conclusion vectors alone leaves a later `y:B(x)` stale. `GF-substitution` owes simultaneous typing/well-formedness proofs; this is no unchecked solver rewrite, and computations cannot replace stable indices.

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

The common judgment is:

```text
S; M; Gamma; Delta_in |- c : Exit(A,Q)
  [use u; type-use v; captures C; effects E; trace T;
   phase p; representation rho; exit duties O]

Q(tag,value) = Delta_out for that represented exit
```

The judgment relates entry state, execution and every reachable exit. The chosen logic interprets `Delta` as ownership, loans/restoration, protocols, effect/security permissions; `Own(id,shape,snapshot)` is an interface, not a supplied CHERI predicate. Identity cannot construct authority. `Q` includes captures transferred in results/frames; branch-dependent owners retain their discriminant until a join/restoration proof removes it.

| Interface obligation | Required evidence |
| --- | --- |
| `Capture(C,Delta)` | The whole transitive retained environment, including handlers, tasks, stored continuations and cell fields, has identified kinded resources, lifetimes, effects and representation. Resources used only during evaluation are recorded separately. |
| `Dup(C,Delta)` | A semantic split supporting both uses under interference, lifetime and protocol conditions. Duplicable immutable snapshots qualify only under their actual representation; an exclusive owner, exclusive loan or single-use token has no default instance. |
| `Dispose(Delta,exit)` | An explicit terminal/resource-returning transition for every obligation. Ordinary affine permission discard does not discharge a protocol, must-erase value or mandatory examined verdict. |
| `Suspend(C,Delta,rho,O)` | Stable represented storage, live loan ancestry, closed invariants and a bounded restoration/cleanup path at the declared checkpoint; no escaping reference into a moved frame. |
| `Transfer(domain,Delta)` | Permission and representation transport to the receiving execution domain, preserving exclusivity, lifetime, publication ordering and the manifest join. |
| `Share(protocol,Delta)` | The declared concurrent operations preserve an invariant under actual interference and the pinned memory model. A shared handle grants only those operations. |

`Dispose` is an explicit computation with effects and, where relevant, writes; proof erasure does not zero machine registers or spill slots. Mandatory verdict elimination names the outcome as required by [R-05-097 through R-05-100](../../spec.md#r-05-097). Source ownership connects to the [exclusive-access and composition obligations](../../spec.md#r-05-096a); borrowing cannot derive an overlapping permission merely because it preserves a grade.

Sequencing composes outcome-indexed resource transitions and concatenates traces; effect sets take union. Repeating a callback or resumption needs its repeatable calling contract and fresh separated per-invocation inputs `Delta_i`. For `k` invocations, a per-call source-event law gives the corresponding sum or `k`-fold count. A grade on the callable does not supply that law, termination, invocation order or a claim about optimized machine calls. Multi-shot capture needs `Dup` for the entire retained continuation context even if each explicit argument is pure.

Mutation updates the owner's snapshot; shape changes consume the old owner and return an appropriately indexed one. Copied snapshots remain historical until newly related to current contents. Suspension/reentry with open cell invariants needs a stronger protocol. Grades authorize neither shared mutable capabilities nor unsupported atomics.

## Schematic derivations and invalid neighbors

These are hand derivations of proposed rules over inhabited pure inputs and explicit domains. Each negative preserves the positive's representations and unrelated resources; parsing failure or absent implementation does not establish its intended refusal.

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

The Q25 composed client retains its packet/frame owner and unique service allowance outside the pure handler's capture delimiter while a child updates a scalar atomic accepted-byte counter. Its `AddOnce(request,n)` allowance is a protocol token in `Delta`; `n` is represented, the overflow bound is erased evidence, and the service handle exposes only its proved atomic operation. Two resumptions of the pure callback continuation cannot capture the child update that consumes this allowance. The AMO transition and cancellation commit behavior belong to Q25c and Q25b. Replacing the callback environment with a cell retaining the owner fails `Dup`; declaring the surface callback unchanged cannot hide that transitive capture.

The Boolean presence calculation `1+1=1` accepts two pure uses as presence. Attempting the same contraction on `AddOnce` still requires a spatial/protocol split that its unique transition cannot provide. This is the invalid authority neighbor even when grade constraints succeed. Dropping the child verdict or must-erase data similarly fails `Dispose`; use/erasure annotations cannot manufacture terminal completion or wiping.

## Inference, specialization and admission

Bidirectional checking uses public domain identities, grade variables/constraints, call modes, captures, effects and representations. Rules infer local demands; CIC reconstructs grade equalities/orders and bounded arithmetic. Symbolic multiplication, dependent unification, arbitrary operations and recursors may leave explicit goals. No principal-grade inference or complete procedure for all domains is promised.

A constraint result binds its proposition, domain dictionary, substitutions and replayable certificate/term. Timeout, inconsistent model, unknown law or reconstruction failure leaves unresolved/refused evidence. Search cannot weaken exact declarations into bounds. Grade-polymorphic definitions check under explicit constraints, discharged at every public instantiation. Runtime natural indices stay represented even when indexing erased trace bounds; they cannot retrospectively select layout.

Specialization fixes phase, convention, layout and erasure before emission. Represented/erased grade instantiations need separately checked ABIs unless a uniform representation and erasure theorem is supplied. The device gains no runtime grade dictionary or open-term normalization. This source specialization does not authorize cloning at the separate composition-time singleton-call rewrite.

`SourcePackage` binds source/generated inputs, domain implementations/laws, elaborated constraints, reconstructed proofs, implicits/transports, representation and exact core computation. Parsing, resolution, instance selection and desugaring need correspondence; old core proofs cannot accept changed source. Erasure preserves results, control, effects, resource behavior and requested observations under that representation, relating retained behavior across instances differing only in erased proofs. Type-checking an irrelevant term is insufficient.

[R-05-132 through R-05-134](../../spec.md#r-05-132) keep the source/TAL boundary: compile source obligations into the existing admitted attributes where their actual rules suffice, and carry the remaining proved obligations as CIC terms. General source domains, dependent normalization and grade-polymorphic dictionaries do not become TAL attributes. A requested new attribute would need that requirement's amendment demonstration and the TAL's own extension conditions. This dossier proposes none. Final-source correspondence, ABI, optimization, timing, linking and Sail evidence remain with the existing compiler/admission owners.

## Q25d debts and acceptance boundary

These debt keys are neither Rocq constants, schedule cells nor assumptions. Q25d joins them with [Q21 packages](core-design.md#proof-obligations-and-proposed-work-packages) and the [foundation map](../../hardware/cheri-foundation-map.md), assigning owners, estimates and predicates in [pricing](full-language-review.md#reviewed-implementation-pricing) under its [frontend disposition](full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows). Unestablished foundation work stays explicitly `unpriced` when a responsible range is unavailable.

| Debt key | Required artifact and refusal predicate |
| --- | --- |
| `GF-domain` | Construct domain records, certificate interpreters and interpretation laws; reject Boolean-to-exact/ownership coercion and unsound order relaxation. Includes cross-domain compatibility rather than duplicating an event-count pilot. |
| `GF-substitution` | Mechanize telescope well-formedness, simultaneous substitution, both vector transformations, grade substitution and dependency-preserving structural rules. Reject a later declaration retaining an unsubstituted index. |
| `GF-elimination` | Prove dependent functions, pairs, boxes, indexed sums and admitted recursors preserve grades and well-formed motives. Construct positive asymmetric-field examples with their modality premises; refuse erased runtime discriminants. |
| `GF-cbv` | Connect pure demand semantics to explicitly sequenced call-by-value computations, captures and outcome-indexed exits. Prove usage-aware resource preservation, including zero-demand effectful arguments and repeated pure values. Ordinary progress/preservation alone is insufficient. |
| `GF-resource` | Instantiate spatial ownership, views, restoration and kinded authority on the selected logic/CHERI representation; construct inhabited packet entry states. Q2c retains concrete foundation ownership; these rules cannot assume its missing laws. |
| `GF-control-mutation` | Compose Capture/Dup/Dispose/Suspend/Transfer/Share with Q25b/Q25c, including repeated continuations, hidden cell captures, snapshots, cancellation and fresh per-resumption resources. Preserve the synchronous slice as a conservative restriction. |
| `GF-erasure-source` | Prove phase separation, representation-specific erasure and source/elaboration correspondence under checked CIC assumptions; qualify domain inference diagnostics and stale-source rejection. Reuse retained frontend/diagnostic duties once. |
| `GF-target` | Connect the selected source representation, event projections and obligations through the existing compiler route to actual TAL/Sail artifacts. No source count substitutes for final cost or arbitrary-context preservation. |

Q25a design acceptance requires the explicit rules, derivations, rejecting neighbors and debts, closing none of the debts or unimplemented negatives and claiming no soundness, estimate reduction or register amendment. Q25d's independent combined-client review and integrated document gates remain required for design credit.
