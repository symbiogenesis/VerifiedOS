# Graded dependent foundation

> Non-normative Q25a rule dossier. These are proposed checking interfaces and schematic derivations, not an implemented language, checked metatheory, accepted axiom or qualified binary. [Q25](../implementation/implementation-checklist.md#q-assessment-actions) owns the design gates; the [requirements register](../requirements-register.md) remains authoritative.

## Scope and research boundary

The [full-language commitment](verification-strategy.md#graded-dependent-foundation) selects separate computation and type dependence, lawful extensible grades and CIC interpretation. This dossier makes that choice concrete while retaining the [synchronous core's resource interpretation](core-design.md#judgments-and-interpretations). Q25b and Q25c consume the [resource interface](#resource-and-computation-interface). Q25d reviews their combination and assigns missing implementation work; no implementation gate opens here.

The source identities are Moon, Eades and Orchard, [Graded Modal Dependent Type Theory, arXiv:2010.13163v2](https://arxiv.org/pdf/2010.13163v2), and its Gerty ESOP 2021 prototype; Choudhury, Eades, Eisenberg and Weirich, [GraD, arXiv:2011.04070v2](https://arxiv.org/html/2011.04070v2); and Abel, Danielsson and Eriksson, [ICFP 2023, DOI 10.1145/3607862](https://research.chalmers.se/en/publication/537991). The [existing comparison](verification-strategy.md#reading-the-graded-type-claims) owns the wider survey. No source or dependency is incorporated.

GrTT supplies the two use vectors and dependent context bookkeeping behind the pure rules below. Its operational presentation is call by name; its restricted normalization result does not establish Vela's effectful call-by-value calculus. GraD motivates a separate usage-aware soundness obligation; Boolean addition demonstrates that grade one need not mean unique use. Its heap result supplies no CHERI ownership theorem. The Agda erasure development restricts modalities and contexts, including erased elimination of weak dependent pairs. Vela owes its own erasure and elimination connection to CIC and mutable computations.

## Dimensions and lawful domains

Each judgment fixes a semantic environment `S`: qualified definitions, universe constraints, grade-domain identities, primitive contracts, logic instance, representation and requested observation model. `Type i : Type (i+1)` uses CIC's existing universe checking; cumulative conversion uses checked universe inequalities. There is no `Type : Type`, new kernel conversion rule, global UIP, proof irrelevance or extensionality axiom. Explicit transports use accepted proof terms and the existing assumption audit.

| Dimension | Meaning | Evidence it cannot replace |
| --- | --- | --- |
| Computation use `u` | Demand on stable values in the selected graded value semantics | Invocation counts, physical copies, exclusive permission or WCET |
| Type use `v` and dependency rows `M` | Demand in the result type and in every declaration's type | Runtime availability of an erased index |
| Phase and representation `p, rho` | Runtime, specification or proof; represented or erased at the selected ABI | Protocol disposal or secret zeroization |
| Resource context `Delta` | Live ownership, loans, restoration and other kinded authority under the selected logic | A generic numeric, effect or security annotation |
| Effects `E` | Allowed operation footprints, including transitive calls and captures | Permission to perform those operations |
| Trace contract `T` | Named source events, their order and exact counts or upper bounds | Surviving machine calls or instruction timing |
| Target bound `W` | The existing final-CFG cost judgment against pinned Sail timing | A source use or event count without its transport theorem |

A library-defined domain is a sealed CIC record, not an arbitrary executable plugin in admission. Its public identity binds the carrier universe, grade-expression syntax, operations, equality/order and their proofs, structural permissions, constraint-certificate interpreter and semantic interpretation. Clients cannot replace the domain dictionary behind a qualified signature.

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

`q <=D q'` means that demand `q` is admitted by advertised allowance `q'`; this orientation is part of the record. Equality remains available when approximation would lose an exact-use claim. The displayed rules require commuting multiplication so promotion and dependent motive scaling agree; admitting a noncommutative domain requires separately reviewed ordered-action rules under `GF-domain`. A custom operation needs its own composition law. Incomparable branch demands use a proved upper bound or a result-indexed contract, never an assumed join. A product domain requires a common subject/trace interpretation and compatibility laws, not merely componentwise arithmetic.

The first exact domain is `NatExact`: natural addition/multiplication and equality as the admission order. `NatBound` uses the same carrier with the ordinary order, so `0 <= 1` permits a bound of one to cover zero uses and cannot mean exactly once. An idempotent presence domain has Boolean `or`/`and`; `1 + 1 = 1` and its result means presence, not cardinality. These are design instances whose record proofs and interpretation still require construction.

Stronger conclusions require additional evidence. Zero-use erasure needs a theorem that zero excludes relevant observation in this interpretation; nontriviality, positivity and absence of zero divisors alone do not prove that theorem for Vela. Exact cardinality needs a faithful count interpretation and an order that cannot relax zero or two to exact one. Unique memory authority additionally needs the spatial exclusivity and representation theorem. Security domains require relational observations including control and address dependence. Grade `1` in an idempotent domain supplies none of those extra results.

## Stable telescope and dependency bookkeeping

Write `J(M; u; v; Gamma |- t : A)` for the pure graded judgment, with `S` implicit. `Gamma` is an ordered telescope of stable values, types, immutable snapshots and logical identities. Runtime handles may occur there as stable descriptors; access permissions remain in `Delta`. Stability does not confer a permission to copy the represented referent. No index evaluates an unsynchronized mutable read.

`M[i]` is a row over exactly the declarations preceding `Gamma[i]`, recording their use in that declaration's type. `u` and `v` have one component per declaration: use in `t` and in `A`, respectively. They are distinct from `M`, and `v` is not the sum of all declaration rows. Every row carries a well-formed type derivation. Zero-padded rows and vectors always refer to the same ordered telescope.

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

These equations retain codomain substitution: application type use is `b+r*z`, not the sum of the function's entire type use and the argument's type use. The domain annotation `a` no longer occurs in the resulting type. They specify the intended pure fragment; substitution and preservation in the combined language remain the debts below. A resource-carrying closure additionally records its transitive environment and call mode; the arithmetic cannot validate duplicated captures.

Vela computations evaluate left to right by value. Elaborate an effectful argument as `bind x <- c; call f x`: evaluate `c` once, record its trace/effects and resource exit, then apply the value rule to `x`. Parameter use zero does not erase `c`'s effects, failures or mandatory result. Parameter use two does not execute `c` twice. Moving this bind across a handler, mutation or cancellation checkpoint needs an explicit preservation proof.

### Substitution and structural rules

For a pure value substitution `Gamma, x:A, Xi |- t:B` with `Gamma |- v:A`, let `z` be the subject-use vector of `v`. For any demand row `d=(d_G,d_x,d_X)` after `x`, define:

```text
substDemand(d,x,z) = (d_G + d_x*z, d_X)
Gamma, x:A, Xi   becomes   Gamma, Xi[v/x]
u               becomes   substDemand(u,x,z)
v_type          becomes   substDemand(v_type,x,z)
each later M row becomes   substDemand(that row,x,z)
```

Earlier rows stay fixed and the row for `x` disappears. All affected types, motives, grade expressions that depend on stable indices, captures and exit predicates undergo capture-avoiding substitution too. Rechecking the substituted telescope is required: changing only the conclusion vectors can leave a later `y:B(x)` carrying the old dependency row. This is a proposed simultaneous-substitution law, with its typing and well-formedness theorem assigned to `GF-substitution`; it is not a solver rewrite accepted without a derivation. Effectful computations are not substituted for stable indices.

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

It relates one entry state, the actual execution and each reachable exit state. `Delta` uses the chosen separation logic, with predicates such as `Own(id,shape,snapshot)`, a loan with restoration obligation, protocol state, effect permission or security permission. These names are interfaces, not supplied CHERI predicates. Stable identity alone cannot construct one. `Q` also accounts for captures transferred in returned values and frames. A branch-dependent owner requires a retained discriminant until an explicit join/restoration proof removes that difference.

| Interface obligation | Required evidence |
| --- | --- |
| `Capture(C,Delta)` | The whole transitive retained environment, including handlers, tasks, stored continuations and cell fields, has identified kinded resources, lifetimes, effects and representation. Resources used only during evaluation are recorded separately. |
| `Dup(C,Delta)` | A semantic split supporting both uses under interference, lifetime and protocol conditions. Duplicable immutable snapshots qualify only under their actual representation; an exclusive owner, exclusive loan or single-use token has no default instance. |
| `Dispose(Delta,exit)` | An explicit terminal/resource-returning transition for every obligation. Ordinary affine permission discard does not discharge a protocol, must-erase value or mandatory examined verdict. |
| `Suspend(C,Delta,rho,O)` | Stable represented storage, live loan ancestry, closed invariants and a bounded restoration/cleanup path at the declared checkpoint; no escaping reference into a moved frame. |
| `Transfer(domain,Delta)` | Permission and representation transport to the receiving execution domain, preserving exclusivity, lifetime, publication ordering and the manifest join. |
| `Share(protocol,Delta)` | The declared concurrent operations preserve an invariant under actual interference and the pinned memory model. A shared handle grants only those operations. |

`Dispose` is an explicit computation with effects and, where relevant, writes; proof erasure does not zero machine registers or spill slots. Mandatory verdict elimination names the outcome as required by [R-05-097 through R-05-100](../spec.md#r-05-097). Source ownership connects to the [exclusive-access and composition obligations](../spec.md#r-05-096a); borrowing cannot derive an overlapping permission merely because it preserves a grade.

Sequencing composes outcome-indexed resource transitions and concatenates traces; effect sets take union. Repeating a callback or resumption needs its repeatable calling contract and fresh separated per-invocation inputs `Delta_i`. For `k` invocations, a per-call source-event law gives the corresponding sum or `k`-fold count. A grade on the callable does not supply that law, termination, invocation order or a claim about optimized machine calls. Multi-shot capture needs `Dup` for the entire retained continuation context even if each explicit argument is pure.

Mutation changes `Own(id,shape,snapshot)` to a new snapshot under the operation contract. A shape-changing transition consumes the old owner and returns an appropriately indexed one. A copied snapshot remains historical after a write; using it as current requires a newly justified relation. Suspending or reentering with an open cell invariant is refused absent the specific stronger protocol. Neither this foundation nor its grades authorize shared mutable capabilities or an unsupported atomic instruction.

## Schematic derivations and invalid neighbors

These examples use supported mathematical syntax, explicit domain identity and inhabited pure inputs. They are hand derivations of proposed rules, not executed acceptance/rejection tests. A negative keeps its positive's representations and unrelated resource premises; a parser failure or absent implementation is not its intended refusal.

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

Checking is bidirectional. Public signatures name domain identities, quantified grade variables and constraints, call modes, captures, effects and representations. Infer local demand expressions from rules; reconstruct grade equalities/order proofs and the synchronous slice's bounded arithmetic in CIC. Natural expressions with symbolic multiplication, dependent unification, arbitrary domain operations and general recursor constraints may remain explicit goals. No principal-grade inference or complete decision procedure for all library domains is promised.

A constraint result carries the exact proposition, domain dictionary, substitutions and a replayable certificate/proof term. A timeout, inconsistent solver model, unknown domain law or failed reconstruction is unresolved/refused evidence, never an assumed equality. Proof search cannot change an exact declaration into an upper bound. Grade-polymorphic definitions check under explicit constraints; every public instantiation discharges them. Runtime-discovered natural indices remain values even where they parameterize an erased trace bound; they do not choose layout retrospectively.

Specialization fixes phase, calling convention, field layout and erasure before code emission. A grade-polymorphic function whose argument might be represented at one instantiation and erased at another produces separately checked ABI instances, unless one uniform representation and its erasure theorem are supplied. No runtime grade dictionary or open-term normalization is added to the device. Source specialization is distinct from the restricted composition-time singleton-call rewrite; it must not be claimed as authorization to clone at that later boundary.

The `SourcePackage` binds source and generated inputs, domain implementations and laws, elaborated grade constraints, reconstructed proofs, implicit arguments/transports, representation choices and the exact core computation. Parsing, resolution, instance selection and desugaring need correspondence; a well-typed old core term does not accept changed source. Erasure preserves runtime results, control decisions, effects, resource-observable behavior and requested observations under the same representation. Two well-formed instances differing only in erased proof data must have related retained behavior; proving an irrelevant term well typed is insufficient.

[R-05-132 through R-05-134](../spec.md#r-05-132) keep the source/TAL boundary: compile source obligations into the existing admitted attributes where their actual rules suffice, and carry the remaining proved obligations as CIC terms. General source domains, dependent normalization and grade-polymorphic dictionaries do not become TAL attributes. A requested new attribute would need that requirement's amendment demonstration and the TAL's own extension conditions. This dossier proposes none. Final-source correspondence, ABI, optimization, timing, linking and Sail evidence remain with the existing compiler/admission owners.

## Q25d debts and acceptance boundary

These keys name missing obligations, not Rocq constants, new schedule cells or accepted assumptions. Q25d must merge overlapping work with the [Q21 retained packages](core-design.md#proof-obligations-and-proposed-work-packages) and [Q2c foundation map](../hardware/cheri-foundation-map.md), assign one reviewed implementation owner/estimate/predicate to each selected debt, and resolve R-05-020 before frontend implementation. A responsible price unavailable at that review remains an explicit blocker.

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

Q25a's design acceptance is the explicit rules, bounded derivations, rejecting neighbors and named debts above. It does not close any debt, qualify an unimplemented negative, lower an existing estimate, amend the register or claim that the combined calculus is sound. Q25d's independent combined-client review and the integrated document gates remain necessary before this design batch is credited.
