# Full-language composition review

> Non-normative Q25d integration record. The requirements register remains
> authoritative. The source rules are design proposals; no implemented language,
> checked metatheory, target execution or production qualification follows from
> this review. Q25d remains open on its complete implementation accounting and
> frontend-admission decision.

## Inputs and common boundary

The [graded foundation](graded-foundation.md), [control and async rules](handlers-async.md)
and [interior-mutability rules](interior-mutability.md) share stable dependent
values, separately accounted computation and type use, and an independent
resource interpretation. A source grade cannot create a memory permission.
Outcome-indexed resource transitions account for every returned owner, loan,
mandatory result, continuation and terminal-completion obligation.

The [bounded core](core-design.md) and [foundation map](../hardware/cheri-foundation-map.md)
retain their missing concrete CHERI laws. The [compiler-route contract](compiler-route-contract.md)
retains its unqualified source-to-machine connections. Q25 adds design obligations
to those boundaries; it does not supply an instance of any missing law or reopen
the rejected implementation trials by changing their names.

## Composed client and inhabited entry

Consider one declared child slot, one private packet frame, and the scalar
accepted-byte counter described by the mutation dossier. At the source level,
the packet has a runtime length `n`, storage capacity `N`, and an immutable
snapshot `xs` with evidence `length(xs) = n` and `n <= N`. The child holds the
packet owner, a live frame identity and generation, a request identity, and a
linear counter allowance for adding `n`. Other children, if admitted, hold
disjoint frames and disjoint allowances. No capability is stored in the shared
counter.

An entry witness chooses `N = 4`, `n = 2`, `xs = [1, 2]`, a free declared child
slot, private initialized backing `[1,2,0,0]`, a zero counter and an allowance of
two. These are example inputs, not profile constants. The counter invariant reserves enough unused range for all
outstanding allowances; an admitted increment consumes its allowance. A pure
callback `f(xs,b)` takes the snapshot and a represented public Boolean and returns
the sum of the snapshot's elements, independently of that Boolean. Its captured
snapshot is stable and its environment has a separately justified duplication
law; no packet owner, dynamic-borrow guard or single-use verdict is captured.
Its computation-use budget is two invocations, with type dependencies accounted
through the foundation's separate context rules.

The source example executes a bounded choice-handler computation that invokes
`f` in two resumptions, with `false` then `true`, and returns the pair of results. Each resumption carries only
the duplicable snapshot environment; the caller's exclusive packet/frame owner
stays outside the captured delimiter. The capture boundary and callback demand
must be proved by the control and grade rules, rather than inferred from lexical
variable names. For the witness both results are three. The child then reaches
a cancellation checkpoint and, if still live and uncancelled, performs its
single admitted counter increment. The atomic update is the commit point.
Terminal publication and scope join follow the control dossier's separate
completion protocol.

This entry is inhabited in the proposed source-level data and protocol model.
It supplies no inhabitant of the missing concrete CHERI separation-logic
interpretation. The witness exposes that remaining obligation instead of
assuming the language's machine soundness in order to test it.

## Paths the join must preserve

| Path | Required source outcome and resource account |
| --- | --- |
| Ready result, no cancellation | The ready await still performs its semantic checkpoint. Both callback uses are accounted; the counter increment consumes the allowance once; the parent releases the private frame only after observing the terminal result and discharging held references. |
| Pending result | The bounded frame stores represented state and the declared continuation point, then returns at a syntactic poll site. Only the admitted reaction graph can resume it. The counter and allowance remain unchanged before commit. |
| Cancel before start | The registered scope still owns the dormant child's captured packet and allowance. Typed cleanup returns or disposes of them and publishes `cancelled`; a request alone does not free the frame. |
| Cancellation observed at a pre-commit checkpoint | The checkpoint selects cleanup. The counter is unchanged, the unused allowance is returned, and the cancellation result is observed before safe reuse. |
| Request arrives after the last pre-commit checkpoint | Arrival alone does not accept cancellation. If the bounded commit region reaches the atomic update before the request is handled, the post-commit observation returns `too_late` and follows normal completion. |
| Cancel after commit | The operation answers `too_late` and finishes its normal terminal protocol. The counter is not decremented; the consumed allowance is not returned as unused. |
| Full child/frame pool | Binding returns the mandatory capacity verdict and the unstarted computation's resources. No implicit wait or borrowing from another pool occurs. |
| Child failure or cleanup failure | The owning scope observes the declared result. A fail-stop/restart path uses the platform's revocation and containment obligations; safety cannot depend on running ordinary source cleanup after a crash. |

The parent-child order, time to a checkpoint, cleanup, outstanding device
quiescence and terminal publication contribute to the control dossier's bound.
That bound includes decision delay before either the cancelled or committed
suffix, and separately bounds ordinary execution without cancellation.
No numeric target time is established by the example. Confidential inputs
add a separate observation/constant-time obligation; the witness's values and
schedule decisions are public and therefore cannot establish that stronger case.

## Well-formed neighbors and their judging premise

These are proposed semantic judgments, not results from an executable frontend.
Each neighbor retains the client's supported syntax and well-typed ordinary
data while changing the stated resource premise.

| Neighbor | Required refusal |
| --- | --- |
| Hide the packet owner in the callback or a stored continuation | The transitive captured-resource duplication premise fails before a multi-shot continuation can be copied. Idempotent analysis grades cannot repair it. |
| Permit two resumptions but supply a one-call exact budget | Computation-use reconstruction cannot establish the required demand. The callback's duplicable memory environment does not duplicate its declared usage budget. |
| Reuse an old cell snapshot as a proposition about its current value | The operation lacks the current invariant/snapshot agreement premise. A stable historical value is not evidence that interference has not occurred. |
| Suspend or perform a capturing effect with a dynamic exclusive guard open | The suspension/capture rule lacks a closed invariant and transferable exit account. A ready result does not remove that checkpoint duty. |
| Release the parent frame on cancellation acknowledgment | The terminal/quiescence and outstanding-reference premises remain unfulfilled. `too_late` does not imply completion. |
| Ignore the child failure or capacity verdict | The branch cannot eliminate its mandatory outcome obligation. Affine ownership disposal supplies no verdict-elimination rule. |
| Replace the scalar increment by conditional capability CAS | The operation lacks an admitted primitive and violates the shared-mutable-capability restriction. No source wrapper authorizes it. |
| Return an allowance as unused after the atomic increment | The counter invariant loses conservation of committed value and outstanding allowances. Cancellation cannot roll back the commit point. |

## Conservative connection to the synchronous slice

Restrict the proposed source language to the [core design's](core-design.md)
syntax and representations: no handler, async task, cancellation or concurrent
cell; stable data, flow-sensitive loans, explicit exits and the existing callback
contracts remain. Choose the source domain and structural rules that express
those actual use constraints, with no weakening of the independent resource
context. Erasure preserves runtime lengths, branch tags and represented values.

The required conservativity theorem maps derivations of this restriction to the
core judgment with the same entry/exit interpretation, effects and observations,
and maps execution back without introducing control or memory operations. A
projection that forgets an outstanding loan or mandatory result does not qualify.
Substitution, dependency reindexing, resource preservation, erasure, interference
and every exit must commute with this projection. No such theorem is checked by
this document. Q21a's unavailable concrete returned-view law remains unavailable
in the restricted fragment as well.

## Remaining implementation and amendment decisions

| Obligation | Existing owner and remaining Q25d decision |
| --- | --- |
| Source calculus, dependency substitution and erasure | Reuse Q21a's proposed `core-soundness` package as the bounded baseline. The graded/control/mutation extensions need a reviewed incremental scope and estimate; the old restricted-fragment price cannot fund them implicitly. |
| Concrete CHERI resources, invariants and canonical machine interpretation | Reuse Q2c's `byte-instance`, `scoped-resources`, `machine-logic` and `context-preservation` map. Select the real subject and checked laws or responsibly price their missing implementation before opening dependent work. |
| Elaboration, grade reconstruction and source correspondence | Reuse Q21a's proposed `core-frontend` boundary. Price the extension for domain evidence, handler capture, bounded async lowering and cell protocols once; Q19 tooling qualification does not supply that frontend. |
| Representation, compiler, linkage and final bytes | Q2b, M1 and Q21b retain their existing duties; Q20c owns final-artifact promotion. Identify and price any new primitive/representation bridge without moving their existing costs into Q25 a second time. |
| Diagnostics and qualification clients | Retain Q19's existing-tool scope and Q20's frozen development/held-out protocol. Price new source diagnostics and this combined client separately from those existing trials. |
| Translator admission | R-05-020 still requires shown Coq-native/bridged, nonduplication and retiring-interim arguments. A source calculus interpreted in CIC supplies no automatic nonduplication or retirement decision. No frontend is commissioned here. |
| Runtime-occupancy classification | Classify task, scope, continuation and completion storage under R-08-046's inventory, with all manifest fields, or amend that exact entry and its cited prose before implementing a new pool class. Static backing alone does not settle classification. |
| Changed platform behavior | Any target control, synchronization, memory or TAL extension first names its exact normative owner and completes that owner's amendment predicate. The proposed scalar counter and static reaction graph seek to reuse current mechanisms; a design intention is not target correspondence evidence. |

Q25d's acceptance requires a complete reviewed owner/estimate/predicate assignment
and the frontend-admission disposition. The rows above identify the remaining
work but deliberately supply neither speculative implementation budgets nor a
replacement for Q2c/Q21's recorded decisions. The item therefore remains open.
