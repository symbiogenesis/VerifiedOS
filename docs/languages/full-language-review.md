# Full-language composition review

> Non-normative Q25d integration record. The requirements register remains
> authoritative. The source rules are design proposals; no implemented language,
> checked metatheory, target execution or production qualification follows from
> this review. It carries Q25d's implementation accounting, its frontend-admission
> disposition and its runtime-occupancy classification; the two register acts those
> last two name are proposed here and taken by their own amendment gates.

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

## The representation the composed duties are stated over

The duties that projection must commute with compose over one representation and
not over a family of them, and the choice is made here rather than deferred
to whichever instance a later lane reaches for. The representation is the
byte-and-capability carrier: every source resource is a
region of machine memory and a tagged capability value over the Coq definitions
Sail's own backend emits (R-05-019b); grades, proof data and counter allowances
carry nothing at runtime in it; and the bounded reaction graph's frames, child
slots, continuation storage and completion records are ordinary storage in that
same carrier. It is [Q2c's](../hardware/cheri-foundation-map.md#foundation-ownership-ledger)
`byte-instance` extended by its `scoped-resources` interpretation. Selecting it
here fixes the subject each duty is about and supplies no law of it.

| Composed duty | What it states over that carrier | The missing constant that would discharge it |
| --- | --- | --- |
| Simultaneous substitution with dependency reindexing | A substituted telescope's resource account is the substitution of its account: reindexing a dependency moves no footprint, changes no tag, and leaves the disjoint audit and payload fields where they were. | `byte-instance`'s memory-frame law over the disjoint footprints the substitution preserves. |
| Resource preservation across a step | Each step carries the entry account to the exit account of its outcome, with every returned owner, loan, mandatory result, continuation and terminal obligation still separately owned. | `scoped-resources`' disjoint split and join, shared and exclusive reborrow, suspended-parent access and restoration entailments. |
| Erasure | Erasing grade, proof and allowance data leaves the carrier's bytes, tags, initialization predicate and observations unchanged, and two instances differing only in erased data have related retained behaviour. | `byte-instance`'s initialization, write and tag-effect laws, which decide that erasure moves no initialized byte. |
| Interference | A snapshot's proposition survives exactly the writes the cell's invariant admits, and the counter's committed value and outstanding allowances are conserved across the atomic update. | `machine-logic`'s invariant and mask machinery, with the pinned term's own clause for the atomic operation. |
| Each exit of the path table above | Every ready, pending, cancelled, `too_late`, capacity and failure exit restores the account that path names, and the frame is released only after terminal collection. | `scoped-resources`' restoration entailments and `byte-instance`'s write law for the reserved completion record. |

None of `machine-logic`, `byte-instance` and `scoped-resources` resolves to a
checked constant in this repository, which is the state Q2c's ledger records,
pricing `machine-logic`'s full establishment as unbounded, accepting no numeric
estimate for `byte-instance` before the logic and representation are selected,
and holding `scoped-resources`' missing instance inside the rejected foundation
commissioning. **This review therefore constructs no inhabitant of that
carrier.** The entry witness above stays at the source level and says so, and
what naming the carrier buys is that each duty's missing constant is nameable
rather than the whole composition being owed to an unnamed prerequisite. A duty
proved over a different carrier is a different theorem and does not transfer by
sharing a predicate name.

## Existing owners, and where each decision is taken

| Obligation | Existing owner, and the decision taken |
| --- | --- |
| Source calculus, dependency substitution and erasure | Q21a's proposed `core-soundness` package is the bounded baseline, and the graded, control and mutation extensions are scoped and priced as their own rows at [the pricing table](#reviewed-implementation-pricing). The old restricted-fragment price funds none of them. |
| Concrete CHERI resources, invariants and canonical machine interpretation | Q2c's `byte-instance`, `scoped-resources`, `machine-logic` and `context-preservation` map retains the subject. The three rows reaching those keys carry `unpriced` beside the decision that blocks them rather than a number, U-22 owning the breakdown that would replace it. |
| Elaboration, grade reconstruction and source correspondence | Q21a's proposed `core-frontend` boundary is the extension point, and domain evidence, handler capture, bounded async lowering and cell protocols are priced once at [the pricing table](#reviewed-implementation-pricing). Q19 tooling qualification supplies no such frontend. |
| Representation, compiler, linkage and final bytes | Q2b, M1 and Q21b retain their existing duties and Q20c owns final-artifact promotion, so the bridge, admission and preservation rows carry citations to those owners and no second cost. |
| Diagnostics and qualification clients | Q19's existing-tool scope and Q20's frozen development and held-out protocol stand, and the added source diagnostics and the combined client are priced as rows of their own beside them. |
| Translator admission | Taken at [the admission subsection](#r-05-009-r-05-020-and-what-holds-the-frontend-rows), and the disposition is arm-dependent rather than flat: R-05-009 reaches the frontend in arm one and R-05-020 refuses it in arm two, where the design as written sits. No frontend is commissioned here. |
| Runtime-occupancy classification | Taken at [the occupancy subsection](#r-08-046-and-what-the-languages-runtime-varying-storage-is): the classification is performed against the current inventory and every manifest field, its verdict is that a new class is required, and the amendment that verdict implies is proposed rather than taken. |
| Changed platform behavior | No target control, synchronization, memory or TAL extension is proposed: the scalar counter and the static reaction graph reuse current mechanisms, and a design intention is not target-correspondence evidence. An extension proposed later names its exact normative owner and completes that owner's amendment predicate first. |
| Assurance-preset policy and mixed-assurance linking | The [preset dossier](assurance-profiles.md) states the claim statuses, composition rules and coverage dimensions this client is selected under, and its policy semantics, status reporting and mixed-assurance interface checks are priced at the same table against the same frontend and evidence-package owners. A claim status is a build output and supplies no source calculus, machine interpretation or admission rule. |

Published donors bear on three of those rows and discharge none of them. For the
source-calculus and erasure row, the machine-checked graded erasure development
and VerusBelt's semantic soundness proof for a subset of a proof-oriented type
system are the closest published shapes for the erasure statement owed, and both
are also its warning: the first proves extraction sound only for a restricted
class of modalities and context conditions, and the second leaves its own tool's
erasure pass trusted and outside the model. For the representation, compiler and
final-bytes row, Dargent is the closest published result, a declarative bit-level
layout language whose generated accessors ship with generated proofs that they
realize the declared layout, per compilation rather than once for the compiler,
in Isabelle with a trusted C parser and no capability account. For the diagnostics
and qualification-clients row, Quiver's completion of a specification sketch with
a checked proof of the completion is the shape a residual obligation should take,
with no theorem that an inferred specification is the intended one. The concrete
CHERI resources row has no donor: every logic surveyed is about another modeled
language, which is why its missing laws stay where they are. [The strategy's
research map](verification-strategy.md#research-landscape) records each donor's
kind, boundary and licence; naming one here prices no row, retires no interim and
closes no debt.

### Reviewed implementation pricing

Every missing law the three rule dossiers name, every frontend component this
design adds, every target connection it needs and every stage
[the preset dossier](assurance-profiles.md#qualification-protocol) lists has one
row below, one implementation owner, one estimate and one acceptance predicate.
The estimate column keeps these rules.

* **An estimate is exactly one of three values**: a range with an authority
  class; a citation to the owner that already carries the work, which prices
  nothing a second time; or `unpriced` beside the decision that blocks it. No row
  is blank, zero or a bare dash, which is the rule Q2c's ledger and
  [the unassigned proof map](../assurance/unassigned-proof-map.md#how-to-read-a-row)
  already keep. **A range is stated by its ends alone**, the midpoint being the
  mean of them at whatever cell eventually carries the row, so no figure derived
  from a range is written down here.
* **Existing work is charged once.** Q2c's foundation keys, Q21a's proposed
  packages and the duties Q2b, Q21b, Q20b, Q20c and M1 already carry keep their
  owners. A row reaching one of them carries the citation and prices only the
  increment this design adds, or nothing where it adds none.
* **A language-side range is over Q25a's parameterised resource interface.**
  Instantiating any of those rows at the carrier named above is `byte-instance`
  and `scoped-resources`' work and is inside no range here.
* **The authority classes are [the checklist's own](../implementation/implementation-checklist.md#checklist-conventions)**,
  `I` where the authority a row realizes is inside this repository and `X` where
  it is outside, and every class-X range's upper end is at least twice its lower
  end. That document's width test reads its own cells, so these rows are held to
  it by hand.
* **No total is stated.** These rows commission nothing and enter no schedule
  until a cell is placed for them, and a sum over conditional ranges is a figure
  for nothing.

| Key or component | Implementation owner | Estimate and class | Acceptance predicate, and what fails it |
| --- | --- | --- | --- |
| `GF-domain` | `core-soundness`, extended | 24–56 h · X | Domain records, certificate interpreters and interpretation laws check, and cross-domain composition is a law rather than a convention. Fails where an idempotent or Boolean domain admits an exact-use or ownership conclusion, where an order relaxation is accepted without its interpretation, or where a constraint procedure returns a verdict with no reconstructable certificate. |
| `GF-substitution` | `core-soundness`, extended | 28–68 h · X | Telescope well-formedness, simultaneous substitution, both vector transformations and grade substitution are theorems about the interpretation's image. Fails on a later declaration retaining an unsubstituted index, and fails against R-05-019 where the statement quantifies over a source reduction relation not defined as that image. |
| `GF-elimination` | `core-soundness`, extended | 22–58 h · X | Dependent functions, pairs, boxes, indexed sums and the admitted recursors preserve grades and well-formed motives, with an inhabited asymmetric-field example carrying its modality premise. Fails where a runtime discriminant is erased, and fails where the positive example is well typed but its hypotheses have no inhabitant, which is R-05-166's case. |
| `GF-cbv` | `core-soundness`, extended | 32–80 h · X | Demand semantics connects to explicitly sequenced call-by-value computation with usage-aware resource preservation, covering zero-demand effectful arguments and repeated pure values. Fails where a zero-demand effectful argument executes, where a repeated pure value is charged twice, and where ordinary progress and preservation are offered in place of the usage statement. This is F-353's open case. |
| `GF-resource` | Q2c's `scoped-resources` over `byte-instance` | `unpriced`; blocked by Q2c's declined foundation commissioning, whose reviewed breakdown is U-22's deliverable | Spatial ownership, views, restoration and kinded authority are interpreted at the carrier and a packet entry state is inhabited by a checked constant. Fails on any statement assuming a law the foundation has not supplied. No range is defensible before the logic and the representation are selected, and a number here would be one. |
| `GF-control-mutation` | `core-soundness`, extended | 36–92 h · X | Capture, `Dup`, `Dispose`, `Suspend`, `Transfer` and `Share` compose with the control and cell rules over repeated continuations, hidden cell captures, snapshots, cancellation and fresh per-resumption resources, and the synchronous slice stays a conservative restriction. Fails where a resumption reuses a resource a sibling resumption consumed, and fails where the projection admits a derivation the core judgment does not. |
| `GF-erasure-source` | `core-soundness`, extended | 26–70 h · X | Phase separation and representation-specific erasure are proved under an assumption set declared per R-05-164 and audited against the proof term by R-05-163. Fails where two instances differing only in erased data have unrelated retained behaviour. The elaboration-correspondence and diagnostic halves of this key are charged at the frontend rows below and carry no number here. |
| `GF-target` | Q21b's compiler-route comparison | Cited: each route's source-to-IR bridge and machine simulation are that comparison's, priced at its own trial | The selected source representation, its event projections and its obligations reach actual TAL and Sail artifacts. Fails where a source-level count stands in for final cost, and fails where arbitrary-context preservation is assumed rather than carried by `context-preservation`. |
| `HA-capture-substitution` | `core-soundness`, extended | 26–70 h · X | Moving a transitive resource context into a represented frame preserves graded dependencies, separation, capabilities and loans, and substituting a reply preserves each deep, shallow and forwarding contract through nested handler environments and explicit forwarding adapters. Fails where a forwarding adapter's reply contract is read off the lexical handler rather than off the capture's recorded context. |
| `HA-resume-dispose` | `core-soundness`, extended | 22–58 h · X | One-shot use transfers once, `Dup` yields separated invocations with fresh inputs and compositional traces, and zero-shot disposal closes erasure, restoration, mandatory verdicts and protocols on every branch, continuations stored through mutable interfaces included. Fails where storing a continuation in a cell duplicates an exclusive loan or a single-use token. |
| `HA-suspend-scope` | `core-soundness`, extended | 22–58 h · X | Every activation preserves the frame's typed representation, its stable addresses and its loan tree, and no parent owner or frame is released before each child's indexed terminal resources and returning views are discharged. Fails where a ready result is read as removing the checkpoint duty, and fails where address stability is asserted of the frame rather than derived from the carrier's law, which is `byte-instance`'s and is outside this range. |
| `HA-cancel-progress` | `core-soundness`, extended | 26–70 h · X | The local sticky-bit and commit machine relates to R-12-097's declared service decisions with exactly one terminal result, a finite masked distance and explicit delivery, child and quiescence terms, and cleanup failure preserves safety without assuming source cleanup runs after a fail-stop. Fails where the bound is a maximum over outcome suffixes that omits the path carrying both a decision delay and a committed suffix, which is F-355's case. |
| `HA-lowering-erasure` | Q21b's compiler-route comparison | Cited: the explicit-graph lowering, its cost and its storage are that route's artifact obligations | The graph simulates the source checkpoints, handler return transformations and indexed exits, and erasure preserves discriminants and effects. Fails where an effect is cloned or moved across a checkpoint, a commit or a handler boundary without its own preservation law, and fails where graph cost is asserted rather than derived from the TAL derivation and the pinned model. |
| `HA-combined-embedding` | `core-repair-trial`, extended | 22–58 h · X | Q25a's resource interface and Q25c's counter and guard protocol are instantiated with the packet client, each intended negative fails at its stated premise, and the no-handler and no-suspension restriction retains the synchronous core's behaviour and exit predicates. Fails where a negative is refused by parsing, an unsupported construct or an unrelated theorem failure rather than at the premise it was built to miss. |
| `MUT-CELL` | `core-soundness`, extended | 26–70 h · X | Sealed cell predicates, invariant masks, unique opening and closing debts and frame preservation are stated over the parameterised interface, with the local replacement, take, put and scoped-callback rules proved. Fails where an invariant stays open across a suspension or a capturing effect, and fails where the sealed predicate is discharged by a wrapper rather than by the closing rule. |
| `MUT-BORROW` | `core-soundness`, extended | 22–58 h · X | Represented borrow-state correspondence, bounded guard capacity, alias exclusion, exact release and every source exit are proved, nested capture checks included. Fails where a guard survives an exit path, and fails where the typed conflict result is produced by a runtime check no type rule required. |
| `MUT-SNAPSHOT` | `core-soundness`, extended | 18–46 h · X | Observation-to-snapshot introduction, stability under interference, invalidation of current predicates and dependent shape transport are proved. Fails where a refinement about an observed value is reused as a proposition about storage another operation may have written, which is the neighbour the client already refuses. |
| `MUT-SHARE` | `core-soundness`, extended | 22–58 h · X | Transitive capture and the composition of the sharing operations through sealed representations, task frames and handlers are proved. Fails where a local cell becomes concurrently shared through a wrapper. That no capability resides in shared mutable memory is a premise R-15-026's `Zacas` exclusion rests on rather than a theorem that entry owns, and the source-side half of it is this row's; establishing it at the target is named in the TAL row's predicate below. |
| `MUT-ATOMIC` | Q2c's `machine-logic` | `unpriced`; blocked by the same declined commissioning, U-22 being the priced decision that would state its breakdown | The counter invariant and history, the one-use allowance interpretation, exact atomic linearization, absence of overflow and the width, alignment, permission and physical-attribute conditions are proved against the pinned Sail subject. Fails where atomicity stands in for a multi-step functional contract, and fails where a second memory semantics appears beside the pinned term. |
| `MUT-PUBLISH` | Q2c's `machine-logic`, over the existing ring owners | `unpriced`; the ordering half rests on that same blocked key, and the algorithm is [RingContract.v](../../proofs/RingContract.v)'s rather than re-authored | Immutable packet and completion publication instantiates the existing single-producer proof with actual ordering, reader and device quiescence and generation retirement. Fails where a counter-only atomic update is read as publishing a payload, and fails where a second ring algorithm appears. |
| `MUT-EXIT` | `core-soundness`, extended | 22–58 h · X | Cancellation arbitration, checkpoint masking, no-replay receipt storage, child terminal records and reset join the control rules, and each outcome preserves cell and frame resources and its terminal bound. Fails where a cancelled unstarted child's frame is returned before terminal collection, which is F-356's case, and fails where an unused allowance is returned after the commit point. |
| `MUT-OBSERVE` | Q2c's `context-preservation` | Cited: Q2c records its establishment and an alternate route's preservation join as unpriced, and M1's backend estimates exclude it | The chosen counter and packet information-flow contract survives optimization and final bytes over the declared leakage model and the actual artifact. Fails where scalar atomicity or a security grade is offered as the relational statement, and fails where an instance with a secret length exposes its count without a different observation contract. |
| `MUT-CLIENT` | `core-repair-trial`, extended | 18–46 h · I | The combined client's supported positives and negatives replay, the accepted-byte contract is independently reviewed, and each entry state is inhabited at the level the review claims for it. Fails where an entry witness is called concrete without a checked inhabitant of the carrier; the concrete witnesses and the connection to the exact final representation are `byte-instance`'s and `artifact-admission`'s and are outside this range. |
| Elaboration, domain evidence and grade reconstruction | `core-frontend`, extended | 40–104 h · X · held in arm two | Public signatures resolve domain identities, quantified grade variables, constraints, call modes, captures, effects and representations, and every unresolved constraint stays an explicit goal carrying its proposition, dictionary, substitutions and replayable certificate. Fails where a timeout, an inconsistent solver model or a failed reconstruction is recorded as an established equality, and fails where proof search turns an exact declaration into an upper bound. |
| Handler capture and bounded async lowering | `core-frontend`, extended | 36–92 h · X · held in arm two | The frontend emits the checked capture boundary, the callback demand and the reaction graph's explicit state and syntactic poll sites from the derivation. Fails where a capture boundary is inferred from lexical variable names, and fails where lowering introduces an internal thread, a run queue or an inner scheduler, which R-07-037a refuses. |
| Cell, borrow and snapshot protocol checking | `core-frontend`, extended | 22–58 h · X · held in arm two | Sealed-interface, borrow-state and snapshot obligations are checked at the source, and transfer and sharing eligibility is derived structurally through fields, closures, tasks and stored continuations. Fails where a getter or a callback with a hidden transitive effect passes with an exclusive guard open. |
| `SourcePackage` correspondence, specialization and stale-source rejection | `core-frontend`, extended | 26–70 h · X · held in arm two | Parsing, resolution, instance selection and desugaring carry a correspondence to the exact core computation, specialization fixes phase, calling convention, layout and erasure before emission, and every result carries the generation it was produced at. Fails where a well-typed old core term is accepted for changed source, and fails where one grade-polymorphic function yields one ABI instance across a represented and an erased instantiation with no uniform-representation erasure theorem. |
| Source diagnostics for the added rules | `core-diagnostics`, extended | 22–58 h · X · held in arm two | Diagnostics locate the first unsatisfied obligation in the developer's own operation and values and distinguish a violated rule, a refuted contract, an unknown or timed-out goal, an unsupported feature and a profile refusal. Fails where a stale or unfinished result is presented as accepted evidence, and fails where a semantic edit leaves the reported obligation unchanged. |
| Preset selection, obligation expansion and the claim-status engine | `preset-policy`, a new package | 26–70 h · I · held in arm two | A build expands its preset into explicit obligations and gives every exported claim exactly one status, with an unestablished claim unavailable to proof search, elimination and proof-based optimization alike. Fails where a strictness setting moves the meaning of a construct two presets share, and fails where a release policy lacking the specification a declared dimension needs is completed by default rather than refused. |
| Mixed-assurance linking and closure declaration | `preset-policy`, a new package | 24–56 h · I · held in arm two | Each call boundary carries its stated rule, the declared closure names the reachable implementations, instantiations, dependencies, generated code and runtime components, and a downgraded interface rechecks its dependents. Fails where ordinary code inherits a property from being linked beside verified code, and fails where compiling with verification disabled retains a theorem-dependent optimization whose justification has gone. |
| Source representation and IR bridge for the added constructs | Q21b | Cited: each route's bridge and machine simulation are that comparison's, and Q2b owns the device lowering | The graded, handler and cell constructs reach the selected representation with their resource account intact. Fails where a route claims the bridge by naming the constructs rather than by carrying their representation obligations. |
| Attribute projection under R-05-132 through R-05-134 | The CHERI-TAL owner, which [the unassigned map](../assurance/unassigned-proof-map.md#8-mandatory-work-outside-the-priced-total) records as carrying no cell | Cited, and `unpriced` at that owner | Source grades and protocol laws project into the existing admitted attributes where their actual rules suffice, and the remainder is carried as separately checked kernel terms; the target-side statement that no capability resides in shared mutable memory, which R-15-026's `Zacas` exclusion assumes rather than proves, is one of those terms and is carried here. Fails where a general source domain, dependent normalization or a grade dictionary is asked of an attribute, which is a requested new attribute owing that requirement's own admissibility demonstration. |
| Final-byte admission and source correspondence under R-05-023a and R-05-026 | Q2c's `artifact-admission` | Cited, and unpriced at that owner; Q20c prices promotion of supplied evidence and not the construction of this logic | The final image's behaviour refines behaviour the committed source permits through assembly, linking and image construction, with the tier certificate re-checked at admission. Fails where a digest match is offered as a semantic theorem. |
| Arbitrary-context preservation under R-05-024 and R-05-032 | Q2c's `context-preservation` | Cited, and unpriced at that owner | The top-level statement quantifies over an adversarial linked context and composes with the exact final artifact. Fails where a theorem about known generated code fills the slot, and fails where finite emission is offered as the quantifier. |
| Reaction-graph cost and schedule admission under R-07-037a and R-11-006 | U-28's soundness statement over [the schedule record](../../proofs/CyclicExecutive.v) U-05 owns | Cited at those slices | An admitted reaction graph's cycles are bounded by a max-path sum over its typed graph with loop bounds, and its masked-cancellation distance is a term of that same bound. Fails where an unbounded cleanup retry, forwarding cycle or ready-task selection queue appears, and fails where a bound is asserted rather than derived from the annotated term. |
| Qualification: policy semantics | `preset-policy`, a new package | 14–34 h · I · held in arm two | The negative cases reject an invented invariant, an unresolved safety goal, a hidden external assumption and a proof-dependent optimization retained after verification is disabled. Fails where a rejection comes from an unsupported construct rather than from the policy rule under test. |
| Qualification: ordinary application | `preset-policy`, a new package | 14–34 h · I · held in arm two | One parser, collection and service example written against application interfaces alone strengthens its assurance while reusing the executable implementation, with every required code change recorded. Fails where a rewrite is reported as the same program. |
| Qualification: systems boundary | `core-repair-trial`, extended | 18–46 h · I · held in arm two | An explicit arena and an asynchronous hardware-facing operation establish the point at which the backing becomes reusable, against the cancellation and quiescence rules, over cancellation, late completion, error paths and exhaustion. Fails where reusability is taken at the terminal status rather than established at the release gate. |
| Qualification: complete release | Q20c | Cited: that cell owns the declared requirement set over the implementation closure and the selected endpoint, with its evidence-invalidation cases | A dependency change, a callback, a foreign interface and generated code each invalidate the affected evidence in test. Fails where a preset's source-endpoint coverage report is accepted as a statement about the promoted image. |
| Qualification: maintenance | Q20b | Cited: that cell already measures a representation change, proof repair, checking cost and replay on a held-out client | Executable churn, specification churn, proof repair, checking cost and target resource consequences are reported separately. Fails where proof rediscovery and saved-term replay are reported as one figure. |

### R-05-009, R-05-020, and what holds the frontend rows

**R-05-020 is not the first entry a producer for a new source language meets, and
reading it alone gets this frontend wrong.** R-05-008 forbids admission gating on
the source language or producer identity of a binary. R-05-009 makes any
memory-safe or formally-verified language that yields a well-typed binary and a
kernel-checked elaboration into an existing semantic anchor admissible on the
same terms as Rust, and its criterion adds *without exception or waiver*.
[The specification's delivery prose](../spec.md#r-05-026) states the same route in
as many words: a producer for another language supplies a kernel-checked
elaboration into one of the reviewed anchors, so admission stays language-neutral
without making an arbitrary source parser or frontend trusted, which is why
[the strategy](verification-strategy.md#refactoring-without-expanding-trust)
already records a frontend elaborator as untrusted machinery whose proposed
proofs are rechecked. R-05-020 governs what enters the anchor budget and the
trust base. Whether this design's frontend does is what the two arms decide, so
the arms come first and the conditions are read inside one of them.

**The two arms, and the predicate that keeps a design in the first.** In arm one
the calculus's meaning is its elaboration's image in the kernel's own theory, and
every law above is a theorem about that image. In arm two the calculus carries
its own judgment and reduction relation that the laws quantify over. The
discriminating predicate is that no theorem quantifies over a source term or a
source step whose meaning is not that image. **As the three rule dossiers state
them the laws name a source judgment and a source reduction**, so the design as
written sits in arm two, which is why the `GF-substitution` row above carries
that clause rather than leaving it to a later tidying. Moving to arm one is a
design act this review does not take on the dossiers' behalf: it restates every
law over the elaboration's image, and doing it by assertion here would leave the
three rule dossiers saying the opposite.

**Arm one: R-05-009 reaches the frontend and R-05-020 does not engage.** The
elaborator is then exactly the kernel-checked elaboration R-05-009's premise
names, its anchor is Gallina/CIC, the anchor count stays at R-05-019's frozen
seven, and nothing it emits is trusted, the kernel re-checking every term.
Neither a semantics, nor a program logic, nor a second checker enters the trust
base, so R-05-020 has no subject at this frontend; and refusing it anyway would
be the exception and waiver R-05-009's criterion forbids, for the case that
entry exists to admit. What is owed in arm one is the demonstration and not the
admission: the `SourcePackage` correspondence priced above is what shows the
kernel-checked half, and the arm-one interpretation commitment is what makes the
premise true.

**Arm two: R-05-009's premise is unmet and R-05-020 engages.** A source judgment
and a source reduction the laws quantify over are an eighth anchor, so there is
no elaboration into an *existing* anchor to be R-05-009's premise, R-05-019's
freeze is an amendment owed before any of this opens, and R-05-019a additionally
rejects the per-consumer re-transcription such a design would need. R-05-020's
three conditions then read:

| Condition | Reading in arm two | Verdict |
| --- | --- | --- |
| Coq-native or mechanically bridged | The elaborator emits kernel terms the kernel re-checks and introduces no second checker; what would show it is the `SourcePackage` correspondence priced at the frontend rows above. | Satisfiable, and not yet shown. |
| Non-duplicating of an existing anchor | An eighth anchor for a domain Gallina/CIC already covers is the duplication the entry names, and R-05-019a reaches the re-transcription beside it. | Refuted in this arm. |
| Retires an interim it replaces | R-05-022 carries exactly three interims, F\*/Z3 for libcrux and HACL\*, EasyCrypt's Why3 and SMT route, and Cranelift and Crocus's SMT, each with a named Coq-native destination and a consumer list. A Vela anchor is none of those destinations and removes no consumer from any of those lists, so it stands beside the three rather than retiring one, which is the case the prose this entry is read with names in as many words. | Refuted. |

**R-05-021 does not reach the case either.** It admits a verified compiler as
proof transport between two existing anchors. In arm two the source end is an
anchor this register has not admitted, and in arm one the source end is not an
independent semantic object at all, so on neither arm are there two existing
anchors and the entry's own premise is unmet on both. The wider reading, that an
unanchored source end puts a translation outside R-05-020 rather than inside it,
is not self-defeating and is not refuted here: R-05-020's translator clause still
reaches a translation whose source end *is* an anchor, R-13-016's owed
Sail-to-μSail translation of the profile's instruction subset being one such
candidate in this repository. The case against the wider reading has to be made
on [the anchor-budget prose](../spec.md#r-05-020)'s *rather than standing beside
it*, and it is not needed for the disposition below, which turns on R-05-009's
premise rather than on R-05-021's exemption.

**Q27a is the nearest precedent and it distinguishes rather than supports a flat
refusal.** [That disposition](../implementation/implementation-checklist.md#q-assessment-actions)
applies the first and third conditions to three outside certificate checkers,
each of which would enter the trust base as a second checker deciding a verdict
on its own acceptance. That is the case R-05-020 governs. An untrusted
elaborator the kernel re-checks is the opposite case, and reading the third
condition onto it would make R-05-009 unsatisfiable for every new language,
since no new language retires an interim.

**What holds the rows, and the register act that is owed.** The ten rows marked
above are held in arm two, which is where the design as written sits: seven of
them commission an elaborator, a diagnostic engine or a preset engine for a
calculus whose anchor is refused, and the three qualification stages exercise a
language whose frontend is not commissioned, so none of the ten opens on its own
ground. Their scope is priced so the decision is taken against a number rather
than against an unknown. What releases them is the arm-one interpretation
commitment recorded in the three rule dossiers, and the register act that should
land with it is a new lettered entry beside R-05-020 stating in terms that the
translator clause governs what enters the trust base, so that an untrusted
elaborator whose output the kernel re-checks is R-05-009's route rather than a
translator under that entry. That act carries its own criterion line, its trace,
the sentence of the specification's anchor-budget prose it is read with, and the
co-read pair it moves. It is a clarification rather than a change of disposition,
its substance being already decided by R-05-008, R-05-009 and the delivery prose
above; it is named because the relation between those entries and R-05-020 is
currently settled by reading, and a reading in a non-normative dossier is not
where dependent implementation should be authorized from.

### R-08-046, and what the language's runtime-varying storage is

R-08-046 requires every resource whose backing storage is static and whose
occupancy varies at runtime to be a declared bounded pool with a complete
manifest entry, and makes an unclassified counter, arena, queue or table
that can influence admission or forward progress a review-gate finding. The design's storage kinds are below; the classification is
performed here and its answer is negative.

| Storage kind | Covered by a member of R-08-046's current inventory? |
| --- | --- |
| Task frame, the represented storage a dormant or suspended computation occupies | No. The nearest members, protocol control blocks and checkpoint transaction slots, are bound to a named protocol or transaction rather than to a source-level computation. |
| Child slot, a scope's declared child capacity | No, and its exhaustion is the capacity verdict the path table above already requires. |
| Scope record, the registered structured scope itself | No. |
| Continuation storage | No, and a captured continuation's occupancy varies with resumption and disposal rather than with a session or a grant. |
| Completion record, the pre-reserved terminal capacity a child's outcome is written into | No. |
| Dynamic-borrow guard slot | No. |
| The accepted-byte counter with its outstanding allowances | Not a pool, and this is a classification rather than an exclusion: its backing is one scalar of fixed width whose members are never bound and released, so the subject R-08-046 names has no referent here. R-08-045's charge covers the scalar, the conservation of committed value against outstanding allowances is a source-level invariant, and overflow is `MUT-ATOMIC`'s law rather than a capacity verdict. |

Each kind the table leaves unplaced owes R-08-046's own field set, and the design
supplies some of that set in kind and none of it in values.

| Manifest field | Supplied by this design? |
| --- | --- |
| Owning compartment | Owed. A composition fixes it. |
| Element type | Supplied in kind by the rule dossiers, one type per kind above. |
| Fixed capacity | Owed. The design requires one to exist and names no value. |
| Derivation source of the contents | Supplied in kind: the declared task family the specialization lowers to a reaction graph. The exact typed key is owed. |
| Bind authority and release authority | Supplied in kind: the owning scope binds, and its join or its typed cleanup releases. The compartment-level authority is owed. |
| The binding and release state machine over the monotone member lifecycle | **Owed, and this is the substantive work.** The design's own lifecycle runs from request through the cancelled or committed decision to a terminal result and then to safe reuse; that it refines the register's declared member lifecycle is a claim no document makes, and it is what an amendment would have to show rather than assert. |
| Low threshold and exhausted threshold | Owed. |
| Maximum time from release request to Reusable | Owed as a value. The control rules bound cleanup, quiescence and collection symbolically, and this review establishes no numeric target. |
| Exhaustion action | Supplied in kind: R-08-047's typed capacity verdict, which the path table already requires and which no implicit wait may replace. |
| Recovery reserve | Owed, and this design proposes none. |
| Confidentiality label of occupancy and telemetry | Owed as a value. Occupancy is an observation the leakage obligation already names, and the witness's own values are public, which cannot establish the stronger case. |
| Restart semantics | Owed. Fail-stop and restart follow the platform's revocation and containment obligations, and the pool's own restart behaviour is not stated by that. |
| Generation-migration semantics | Owed. |

**The verdict is that a new class is required**, which makes this an amendment to
R-08-046's inventory and to the prose it is read with rather than a classification
under an existing member. This review proposes that amendment and does not take
it, for two reasons that are the same reason twice: its predicate is a
commissioned frontend, which the arm-two disposition above holds, and
inventorying a pool class that no admitted design instantiates lands a row that
is false on the day it lands. The
act is therefore ordered behind the R-05-020 act, and F-354's classification duty
is answered here while the amendment it names stays owed before dependent runtime
implementation opens.

## What this review establishes and what it does not

The assignment above is a design act. It establishes that every missing law,
frontend component, target connection and qualification stage has one owner, one
estimate and one predicate, and that nothing Q2c, Q21a, Q21b, Q2b, Q20b,
Q20c or M1 already carries is priced a second time. **Design acceptance here
claims no executed language, no checked metatheory theorem and no qualified
binary**: what it claims is the reviewed rule set, the composed client, the named
representation and this accounting. Integrated document gates and the required
co-reads close this review, and mechanization, frontend admission, target
execution and timing qualification each keep their own acceptance predicate and
their own gate.

Two register acts are left owed rather than taken, in this order: the lettered
R-05-020 act that records which entry reaches an untrusted elaborator, and the
R-08-046 inventory act that would let a declared frame, slot, scope,
continuation, completion or guard pool exist. Each follows R-18-034 with its
co-read pair and its cited prose, and neither belongs inside a dossier this one's
own header calls non-normative. **A frontend row also needs what no register act
supplies**, the arm-one interpretation commitment restated across the three rule
dossiers, so the act alone opens nothing.
