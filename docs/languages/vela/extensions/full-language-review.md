# Full-language composition review

> Non-normative Q25d integration review: composed client, representation, implementation pricing, frontend disposition and runtime-storage classification. Start with the [primary Vela design and examples](../verification-strategy.md). The [requirements register](../../../requirements-register.md) governs; [workflow commissioning](../workflow-contract.md#commissioning-disposition) retains canceled trials and re-entry conditions. No implementation, checked metatheory or target qualification is supplied. R-05-020a records the checked-interpretation classification; the later runtime-storage amendment remains a prerequisite to the features that need it.

## Inputs and common boundary

The [first-release contract](../first-release.md#release-boundary) selects synchronous software with fixed usage modes. General graded demand, async, handlers and concurrent mutation need separate commissioning. The [graded foundation](graded-foundation.md), [control/async](handlers-async.md) and [mutability](interior-mutability.md) dossiers state proof obligations about elaborated terms in existing semantic anchors, without defining independent source semantics.

Grades create no memory permission. Each possible outcome must account for its owners, loans, mandatory results, continuations and terminal-completion duties.

The [core](../core-design.md) and [foundation map](../../../hardware/cheri-foundation-map.md) still lack concrete CHERI laws, and [compiler routes](../compiler-route-contract.md) lack qualified source-to-machine connections. Q25's added design duties supply none of those prerequisites and reopen no rejected trial.

## Composed client and inhabited entry

This multi-shot/async/counter client is a retained extension-interaction probe,
not the first-release acceptance client. The [delivery sequence](../../../../PLAN.md#vela-first-release-delivery)
first uses a concrete synchronous buffer operation and an independent package.
The later [service qualification](handlers-async.md#qualification) must exercise
ordinary sequential async composition and one child before any optional cloning
or concurrent-counter demonstration is commissioned. All tables in this section
retain their conditional research scope.

The client uses one declared child slot, a private packet frame and the mutability dossier's scalar accepted-byte counter. Its packet has represented length `n`, capacity `N`, and immutable `xs` satisfying `length(xs)=n` and `n<=N`. The child owns the packet, live frame identity/generation, request identity and a linear allowance to add `n`. Other children require disjoint frames/allowances. The counter stores no capability.

A source-level witness chooses `N=4`, `n=2`, `xs=[1,2]`, initialized backing `[1,2,0,0]`, a free slot, zero counter and allowance two. These are examples, not profile constants. The counter reserves range for all outstanding allowances; each increment consumes its allowance. A pure callback `f(xs,b)` sums the snapshot independently of its represented public Boolean. Its stable environment requires a separate duplication law, captures no packet owner, borrow guard or single-use verdict, and permits two invocations under the foundation's separate type-dependency rules.

A bounded choice handler resumes with `false` then `true`, producing `(3,3)` for this witness. Each resumption retains only the duplicable snapshot; the exclusive packet/frame owner stays outside the delimiter. Control and grade proofs must establish capture and demand, beyond lexical free-variable analysis. The child then reaches a cancellation checkpoint and, if live and uncancelled, performs its one atomic increment: the commit point. Terminal publication and scope join follow the control protocol.

The witness inhabits only the proposed source data/protocol model. No checked inhabitant of the concrete CHERI separation-logic interpretation is supplied.

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

The control bound includes parent-child order, checkpoint delay, cleanup, device quiescence and terminal publication, covering decision delay plus the selected cancelled/committed suffix and separately ordinary execution. This example supplies no numeric target. Public witness values and schedule choices establish no confidential-input observation or constant-time result.

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

Restrict syntax/representation to the [core](../core-design.md): stable data, flow-sensitive loans, explicit exits and existing callback contracts, without handlers, async, cancellation or concurrent cells. Select domains/structural rules for those uses without weakening `Delta`; preserve runtime lengths, tags and represented values through erasure.

Conservativity must map derivations and executions to the core with identical entry/exit interpretation, effects and observations, introducing no control/memory operations or lost loan/verdict duties. Substitution, reindexing, preservation, erasure, interference and every exit must commute with the projection. That theorem and Q21a's concrete returned-view law remain unavailable.

## The representation the composed duties are stated over

All composed duties use one byte-and-capability carrier: memory regions and tagged capabilities over the Coq definitions emitted by Sail (R-05-019b). Grades, proofs and counter allowances are erased; frames, child slots, continuations and completion records occupy ordinary storage. This selects [Q2c's](../../../hardware/cheri-foundation-map.md#foundation-ownership-ledger) `byte-instance` plus `scoped-resources`, fixing theorem subjects without supplying their laws.

| Composed duty | What it states over that carrier | The missing constant that would discharge it |
| --- | --- | --- |
| Simultaneous substitution with dependency reindexing | A substituted telescope's resource account is the substitution of its account: reindexing a dependency moves no footprint, changes no tag, and leaves the disjoint audit and payload fields where they were. | `byte-instance`'s memory-frame law over the disjoint footprints the substitution preserves. |
| Resource preservation across a step | Each step carries the entry account to the exit account of its outcome, with every returned owner, loan, mandatory result, continuation and terminal obligation still separately owned. | `scoped-resources`' disjoint split and join, shared and exclusive reborrow, suspended-parent access and restoration entailments. |
| Erasure | Erasing grade, proof and allowance data leaves the carrier's bytes, tags, initialization predicate and observations unchanged, and two instances differing only in erased data have related retained behaviour. | `byte-instance`'s initialization, write and tag-effect laws, which decide that erasure moves no initialized byte. |
| Interference | A snapshot's proposition survives exactly the writes the cell's invariant admits, and the counter's committed value and outstanding allowances are conserved across the atomic update. | `machine-logic`'s invariant and mask machinery, with the pinned term's own clause for the atomic operation. |
| Each exit of the path table above | Every ready, pending, cancelled, `too_late`, capacity and failure exit restores the account that path names, and the frame is released only after terminal collection. | `scoped-resources`' restoration entailments and `byte-instance`'s write law for the reserved completion record. |

Q2c records no checked constant for `machine-logic`, `byte-instance` or `scoped-resources`. Full logic establishment is unbounded; the byte instance has no responsible price before logic/representation selection; scoped resources remain inside the declined foundation commissioning. This review constructs no concrete carrier inhabitant. Naming the carrier identifies missing constants; a proof over another carrier cannot transfer merely by sharing predicate names.

## Existing owners, and where each decision is taken

| Obligation | Existing owner, and the decision taken |
| --- | --- |
| Source calculus, dependency substitution and erasure | Q21a's proposed `core-soundness` package is the bounded baseline, and the graded, control and mutation extensions are scoped and priced as their own rows at [the pricing table](#reviewed-implementation-pricing). The old restricted-fragment price funds none of them. |
| Concrete CHERI resources, invariants and canonical machine interpretation | Q2c's `byte-instance`, `scoped-resources`, `machine-logic` and `context-preservation` map retains the subject. The three rows reaching those keys carry `unpriced` beside the decision that blocks them rather than a number, U-22 owning the breakdown that would replace it. |
| Elaboration, grade reconstruction and source correspondence | Q21a's proposed `core-frontend` boundary is the extension point, and domain evidence, handler capture, bounded async lowering and cell protocols are priced once at [the pricing table](#reviewed-implementation-pricing). Q19 tooling qualification supplies no such frontend. |
| Representation, compiler, linkage and final bytes | Q2b, M1 and Q21b retain their existing duties and the existing M1/M6 production owners retain final-artifact duties; the canceled Q20c comparison owns no implementation, so the bridge, admission and preservation rows carry citations to those owners and no second cost. |
| Diagnostics and qualification clients | Q19's existing-tool scope and Q20's frozen development and held-out protocol stand, and the added source diagnostics and the combined client are priced as rows of their own beside them. |
| Translator admission | [R-05-020a](../../../spec.md#r-05-020a) and the dossiers select checked interpretation in existing anchors. The [admission subsection](#r-05-009-r-05-020-and-what-holds-the-frontend-rows) retains concrete-law, source-correspondence, representation and commissioning prerequisites; no implementation follows from classification. |
| Runtime-occupancy classification | Taken at [the occupancy subsection](#r-08-046-and-what-the-languages-runtime-varying-storage-is): the classification is performed against the current inventory and every manifest field, its verdict is that a new class is required, and the amendment that verdict implies is proposed rather than taken. |
| Changed platform behavior | No target control, synchronization, memory or TAL extension is proposed: the scalar counter and the static reaction graph reuse current mechanisms, and a design intention is not target-correspondence evidence. An extension proposed later names its exact normative owner and completes that owner's amendment predicate first. |
| Assurance-preset policy and mixed-assurance linking | The [preset dossier](assurance-profiles.md) states the claim statuses, composition rules and coverage dimensions this client is selected under, and its policy semantics, status reporting and mixed-assurance interface checks are priced at the same table against the same frontend and evidence-package owners. A claim status is a build output and supplies no source calculus, machine interpretation or admission rule. |

Donors guide these duties without discharging them. The machine-checked graded erasure work restricts modalities/contexts; VerusBelt's subset soundness model leaves its tool's erasure trusted. Dargent's declarative bit-layout accessors carry per-compilation layout proofs in Isabelle, with a trusted C parser and no capability account. Quiver completes specification sketches with checked proofs but cannot establish intended specifications. Every surveyed logic models another language, leaving concrete CHERI laws open. The [research map](../verification-strategy.md#research-landscape) owns boundaries/licences; donor citations price no work, retire no interim and close no debt.

### Reviewed implementation pricing

The retained extension estimates below price parameterized obligations, not the first release or a complete delivery. [The first-release sequence](../../../../PLAN.md#vela-first-release-delivery) commissions only its finite foundation investigation before repricing from actual prerequisites. Each missing law, frontend component, target connection and [policy qualification stage](assurance-profiles.md#qualification-protocol) has one row, owner, estimate and predicate below.

The [receiver rule](../verification-strategy.md#permanent-language-exclusions)
refines `core-frontend`'s existing resolution and loan obligations: qualify a named
view receiver, once-only evaluation and an overlapping later argument; ordinary
arguments still require their loan modifiers. `core-diagnostics` and
`preset-policy` implement the [claim presentation](assurance-profiles.md#evidence-beside-the-declaration)
with its freshness and conditional/success-scope controls.
The [handler summaries](handlers-async.md#compositional-handler-summaries) refine
`HA-resume-dispose`'s compositional traces, `HA-suspend-scope`'s live-frame
accounting and `HA-lowering-erasure`'s target transport. These are acceptance
details of the existing owners; their implementation holds remain in force.

- Estimates are a range with authority class, a citation to work already owned elsewhere, or `unpriced` with its blocker; never blank, zero or a bare dash. Follow [the proof map](../../../assurance/unassigned-proof-map.md#how-to-read-a-row).
- Range ends are authored; eventual checklist cells derive their midpoint. Existing Q2c/Q21a/Q2b/Q21b/Q20b/Q20c/M1 duties are charged once, with only added work priced here.
- Language ranges assume Q25a's parameterized interface. Concrete carrier instantiation remains `byte-instance`/`scoped-resources` work outside them.
- [Authority classes](../../../../PLAN.md#checklist-conventions) are `I` for internal and `X` for external authority; X upper bounds are at least twice their lower bounds, reviewed here by hand.
- No total or scheduling commission follows from these conditional ranges; implementation requires checklist cells.

| Key or component | Implementation owner | Estimate and class | Acceptance predicate, and what fails it |
| --- | --- | --- | --- |
| `GF-domain` | `core-soundness`, extended | 24–56 h · X | Domain records, certificate interpreters and interpretation laws check, and cross-domain composition is a law rather than a convention. Fails where an idempotent or Boolean domain admits an exact-use or ownership conclusion, where an order relaxation is accepted without its interpretation, or where a constraint procedure returns a verdict with no reconstructable certificate. |
| `GF-substitution` | `core-soundness`, extended | 28–68 h · X | Telescope well-formedness, simultaneous substitution, both vector transformations and grade substitution are theorems about the interpretation's image. Fails on a later declaration retaining an unsubstituted index, and fails against R-05-019 where the statement quantifies over a source reduction relation not defined as that image. |
| `GF-elimination` | `core-soundness`, extended | 22–58 h · X | Dependent functions, pairs, boxes, indexed sums and the admitted recursors preserve grades and well-formed motives, with an inhabited asymmetric-field example carrying its modality premise. Fails where a runtime discriminant is erased, and fails where the positive example is well typed but its hypotheses have no inhabitant, which is R-05-166's case. |
| `GF-cbv` | `core-soundness`, extended | 32–80 h · X | Demand semantics connects to explicitly sequenced call-by-value computation with usage-aware resource preservation, covering zero-demand effectful arguments and repeated pure values. Fails where zero parameter demand erases the argument's evaluation, effects, failures or mandatory result, where repeated use reexecutes that evaluation instead of using its once-evaluated value, or where ordinary progress/preservation replaces usage-aware resource accounting. This is F-353's open case. |
| `GF-resource` | Q2c's `scoped-resources` over `byte-instance` | `unpriced`; blocked by Q2c's declined foundation commissioning, whose reviewed breakdown is U-22's deliverable | Spatial ownership, views, restoration and kinded authority are interpreted at the carrier and a packet entry state is inhabited by a checked constant. Fails on any statement assuming a law the foundation has not supplied. No range is defensible before the logic and the representation are selected, and a number here would be one. |
| `GF-control-mutation` | `core-soundness`, extended | 36–92 h · X | Capture, `Dup`, `Dispose`, `Suspend`, `Transfer` and `Share` compose with the control and cell rules over repeated continuations, hidden cell captures, snapshots, cancellation and fresh per-resumption resources, and the synchronous slice stays a conservative restriction. Fails where a resumption reuses a resource a sibling resumption consumed, and fails where the projection admits a derivation the core judgment does not. |
| `GF-erasure-source` | `core-soundness`, extended | 26–70 h · X | Phase separation and representation-specific erasure are proved under an assumption set declared per R-05-164 and audited against the proof term by R-05-163. Fails where two instances differing only in erased data have unrelated retained behaviour. The elaboration-correspondence and diagnostic halves of this key are charged at the frontend rows below and carry no number here. |
| `GF-target` | Q21b's compiler-route comparison | Cited: each route's source-to-IR bridge and machine simulation are that comparison's, priced at its own trial | The selected source representation, its event projections and its obligations reach actual TAL and Sail artifacts. Fails where a source-level count stands in for final cost, and fails where arbitrary-context preservation is assumed rather than carried by `context-preservation`. |
| `HA-capture-substitution` | `core-soundness`, extended | 26–70 h · X | Moving a transitive resource context into a represented frame preserves graded dependencies, separation, capabilities and loans, and substituting a reply preserves each deep, shallow and forwarding contract through nested handler environments and explicit forwarding adapters, a shallow segment's delimiter hole resolving to the handler its rehandle installs. Under the lexical-scope premise no operation argument, reply, cell read or spawned child reaches a handler frame through a capability out of scope, and an operation argument lending the clause part of the body's own frames ends before `k` is resumed, cloned, rehandled or disposed. Fails where a forwarding adapter's reply contract is read off the handler the capability names at the adapter rather than off the capture's recorded context. |
| `HA-resume-dispose` | `core-soundness`, extended | 22–58 h · X | One-shot use transfers once, `Dup` yields separated invocations with fresh inputs and compositional traces, each clone's reinstalled handlers and internal references denoting its own frames and a handler capability duplicating as a shared loan that authorizes only performing through it, and zero-shot disposal closes erasure, restoration, mandatory verdicts and protocols on every branch, continuations stored through mutable interfaces included. Fails where storing a continuation in a cell duplicates an exclusive loan or a single-use token. |
| `HA-suspend-scope` | `core-soundness`, extended | 22–58 h · X | Every activation preserves the frame's typed representation, its stable addresses and its loan tree, and no parent owner or frame is released before each child's indexed terminal resources and returning views are discharged. Fails where a ready result is read as removing the checkpoint duty, and fails where address stability is asserted of the frame rather than derived from the carrier's law, which is `byte-instance`'s and is outside this range. |
| `HA-cancel-progress` | `core-soundness`, extended | 26–70 h · X | The local sticky-bit and commit machine relates to R-12-097's declared service decisions with exactly one terminal result, a finite masked distance and explicit delivery, child and quiescence terms, covering owner-only registration and children registered already marked after the latch so that the child terms sum over the scope's child set fixed once cleanup begins, and cleanup failure preserves safety without assuming source cleanup runs after a fail-stop. Fails where the bound is a maximum over outcome suffixes that omits the path carrying both a decision delay and a committed suffix, which is F-355's case. |
| `HA-lowering-erasure` | Q21b's compiler-route comparison | Cited: the explicit-graph lowering, its cost and its storage are that route's artifact obligations | The graph simulates the source checkpoints, capability selection by slot access, handler return transformations and indexed exits, every reference a handled body holds to its own frames being stored relative to the delimiter's frame from handler entry so that resolving it against a clone's invocation frame or a shallow rehandle's fresh incarnation, performs dispatching over the finite rehandler set specialization fixes, simulates the source clone or rehandle, and erasure preserves discriminants and effects. Fails where an effect is cloned or moved across a checkpoint, a commit or a handler boundary without its own preservation law, and fails where graph cost is asserted rather than derived from the TAL derivation and the pinned model. |
| `HA-combined-embedding` | `core-repair-trial`, extended | 22–58 h · X | Q25a's resource interface and Q25c's counter and guard protocol are instantiated with the packet client, each intended negative fails at its stated premise, and the no-handler and no-suspension restriction retains the synchronous core's behaviour and exit predicates. Fails where a negative is refused by parsing, an unsupported construct or an unrelated theorem failure rather than at the premise it was built to miss. |
| `MUT-CELL` | `core-soundness`, extended | 26–70 h · X | Sealed cell predicates, invariant masks, unique opening and closing debts and frame preservation are stated over the parameterised interface, with the local replacement, take, put and scoped-callback rules proved. Fails where an invariant stays open across a suspension or a capturing effect, and fails where the sealed predicate is discharged by a wrapper rather than by the closing rule. |
| `MUT-BORROW` | `core-soundness`, extended | 22–58 h · X | Represented borrow-state correspondence, bounded guard capacity, alias exclusion, exact release and every source exit are proved, nested capture checks included. Fails where a guard survives an exit path, and fails where the typed conflict result is produced by a runtime check no type rule required. |
| `MUT-SNAPSHOT` | `core-soundness`, extended | 18–46 h · X | Observation-to-snapshot introduction, stability under interference, invalidation of current predicates and dependent shape transport are proved. Fails where a refinement about an observed value is reused as a proposition about storage another operation may have written, which is the neighbour the client already refuses. |
| `MUT-SHARE` | `core-soundness`, extended | 22–58 h · X | Transitive capture and the composition of the sharing operations through sealed representations, task frames and handlers are proved. Fails where a local cell becomes concurrently shared through a wrapper. That no capability resides in shared mutable memory is a premise R-15-026's `Zacas` exclusion rests on rather than a theorem that entry owns, and the source-side half of it is this row's; establishing it at the target is named in the TAL row's predicate below. |
| `MUT-ATOMIC` | Q2c's `machine-logic` | `unpriced`; blocked by the same declined commissioning, U-22 being the priced decision that would state its breakdown | The counter invariant and history, the one-use allowance interpretation, exact atomic linearization, absence of overflow and the width, alignment, permission and physical-attribute conditions are proved against the pinned Sail subject. Fails where atomicity stands in for a multi-step functional contract, and fails where a second memory semantics appears beside the pinned term. |
| `MUT-PUBLISH` | Q2c's `machine-logic`, over the existing ring owners | `unpriced`; the ordering half rests on that same blocked key, and the algorithm is [RingContract.v](../../../../proofs/RingContract.v)'s rather than re-authored | Immutable packet and completion publication instantiates the existing single-producer proof with actual ordering, reader and device quiescence and generation retirement. Fails where a counter-only atomic update is read as publishing a payload, and fails where a second ring algorithm appears. |
| `MUT-EXIT` | `core-soundness`, extended | 22–58 h · X | Cancellation arbitration, checkpoint masking, no-replay receipt storage, child terminal records and reset join the control rules, and each outcome preserves cell and frame resources and its terminal bound. Fails where a cancelled unstarted child's frame is returned before terminal collection, which is F-356's case, and fails where an unused allowance is returned after the commit point. |
| `MUT-OBSERVE` | Q2c's `context-preservation` | Cited: Q2c records its establishment and an alternate route's preservation join as unpriced, and M1's backend estimates exclude it | The chosen counter and packet information-flow contract survives optimization and final bytes over the declared leakage model and the actual artifact. Fails where scalar atomicity or a security grade is offered as the relational statement, and fails where an instance with a secret length exposes its count without a different observation contract. |
| `MUT-CLIENT` | `core-repair-trial`, extended | 18–46 h · I | The combined client's supported positives and negatives replay, the accepted-byte contract is independently reviewed, and each entry state is inhabited at the level the review claims for it. Fails where an entry witness is called concrete without a checked inhabitant of the carrier; the concrete witnesses and the connection to the exact final representation are `byte-instance`'s and `artifact-admission`'s and are outside this range. |
| Elaboration, domain evidence and grade reconstruction | `core-frontend`, extended | 40–104 h · X · uncommissioned; concrete prerequisites owed | Public signatures resolve domain identities, quantified grade variables, constraints, call modes, captures, effects and representations, and every unresolved constraint stays an explicit goal carrying its proposition, dictionary, substitutions and replayable certificate. Fails where a timeout, an inconsistent solver model or a failed reconstruction is recorded as an established equality, and fails where proof search turns an exact declaration into an upper bound. |
| Handler capture and bounded async lowering | `core-frontend`, extended | 36–92 h · X · uncommissioned; concrete prerequisites owed | The frontend emits the checked capture boundary, the callback demand and the reaction graph's explicit state and syntactic poll sites from the derivation. Fails where a capture boundary is inferred from lexical variable names, and fails where lowering introduces an internal thread, a run queue or an inner scheduler, which R-07-037a refuses. |
| Cell, borrow and snapshot protocol checking | `core-frontend`, extended | 22–58 h · X · uncommissioned; concrete prerequisites owed | Sealed-interface, borrow-state and snapshot obligations are checked at the source, and transfer and sharing eligibility is derived structurally through fields, closures, tasks and stored continuations. Fails where a getter or a callback with a hidden transitive effect passes with an exclusive guard open. |
| `SourcePackage` correspondence, specialization and stale-source rejection | `core-frontend`, extended | 26–70 h · X · uncommissioned; concrete prerequisites owed | Parsing, resolution, instance selection and desugaring carry a correspondence to the exact core computation, specialization fixes phase, calling convention, layout and erasure before emission, and every result carries the generation it was produced at. Fails where a well-typed old core term is accepted for changed source, and fails where one grade-polymorphic function yields one ABI instance across a represented and an erased instantiation with no uniform-representation erasure theorem. |
| Source diagnostics for the added rules | `core-diagnostics`, extended | 22–58 h · X · uncommissioned; concrete prerequisites owed | Diagnostics locate the first unsatisfied obligation in the developer's own operation and values and distinguish a violated rule, a refuted contract, an unknown or timed-out goal, an unsupported feature and a profile refusal. Fails where a stale or unfinished result is presented as accepted evidence, and fails where a semantic edit leaves the reported obligation unchanged. |
| Preset selection, obligation expansion and the claim-status engine | `preset-policy`, a new package | 26–70 h · I · uncommissioned; concrete prerequisites owed | A build expands its preset into explicit obligations and requires every authored exported contract under every preset, keeping unestablished claims in unfinished editor/scratch evidence and unavailable to accepted interfaces, proof search, elimination or optimization. Fails where a strictness setting moves the meaning of a construct two presets share, and fails where a release policy lacking the specification a declared dimension needs is completed by default rather than refused. |
| Mixed-assurance linking and closure declaration | `preset-policy`, a new package | 24–56 h · I · uncommissioned; concrete prerequisites owed | Each call boundary carries its stated rule, the declared closure names the reachable implementations, instantiations, dependencies, generated code and runtime components, and a downgraded interface rechecks its dependents. Fails where ordinary code inherits a property from being linked beside verified code, and fails where compiling with verification disabled retains a theorem-dependent optimization whose justification has gone. |
| Source representation and IR bridge for the added constructs | Q21b | Cited: each route's bridge and machine simulation are that comparison's, and Q2b owns the device lowering | The graded, handler and cell constructs reach the selected representation with their resource account intact. Fails where a route claims the bridge by naming the constructs rather than by carrying their representation obligations. |
| Attribute projection under R-05-132 through R-05-134 | The CHERI-TAL owner, which [the unassigned map](../../../assurance/unassigned-proof-map.md#8-mandatory-work-outside-the-priced-total) records as carrying no cell | Cited, and `unpriced` at that owner | Source grades and protocol laws project into the existing admitted attributes where their actual rules suffice, and the remainder is carried as separately checked kernel terms; the target-side statement that no capability resides in shared mutable memory, which R-15-026's `Zacas` exclusion assumes rather than proves, is one of those terms and is carried here. Fails where a general source domain, dependent normalization or a grade dictionary is asked of an attribute, which is a requested new attribute owing that requirement's own admissibility demonstration. |
| Final-byte admission and source correspondence under R-05-023a and R-05-026 | Q2c's `artifact-admission` | Cited, and unpriced at that owner; Q20c prices promotion of supplied evidence and not the construction of this logic | The final image's behaviour refines behaviour the committed source permits through assembly, linking and image construction, with the tier certificate re-checked at admission. Fails where a digest match is offered as a semantic theorem. |
| Arbitrary-context preservation under R-05-024 and R-05-032 | Q2c's `context-preservation` | Cited, and unpriced at that owner | The top-level statement quantifies over an adversarial linked context and composes with the exact final artifact. Fails where a theorem about known generated code fills the slot, and fails where finite emission is offered as the quantifier. |
| Reaction-graph cost and schedule admission under R-07-037a and R-11-006 | U-28's soundness statement over [the schedule record](../../../../proofs/CyclicExecutive.v) U-05 owns | Cited at those slices | An admitted reaction graph's cycles are bounded by a max-path sum over its typed graph with loop bounds, and its masked-cancellation distance is a term of that same bound. Fails where an unbounded cleanup retry, forwarding cycle or ready-task selection queue appears, and fails where a bound is asserted rather than derived from the annotated term. |
| Qualification: policy semantics | `preset-policy`, a new package | 14–34 h · I · uncommissioned; concrete prerequisites owed | The negative cases reject an invented invariant, an unresolved safety goal, a hidden external assumption and a proof-dependent optimization retained after verification is disabled. Fails where a rejection comes from an unsupported construct rather than from the policy rule under test. |
| Qualification: ordinary application | `preset-policy`, a new package | 14–34 h · I · uncommissioned; concrete prerequisites owed | One parser, collection and service example written against application interfaces alone strengthens its assurance while reusing the executable implementation, with every required code change recorded. Fails where a rewrite is reported as the same program. |
| Qualification: systems boundary | `core-repair-trial`, extended | 18–46 h · I · uncommissioned; concrete prerequisites owed | An explicit arena and an asynchronous hardware-facing operation establish the point at which the backing becomes reusable, against the cancellation and quiescence rules, over cancellation, late completion, error paths and exhaustion. Fails where reusability is taken at the terminal status rather than established at the release gate. |
| Qualification: complete release | Existing compiler, admission and image-validation owners; Q20a retains the comparison contract | Required implementation-closure evidence remains with its production owners. Canceled Q20c owns no release qualification; a future language comparison needs a newly priced owner | A dependency change, a callback, a foreign interface and generated code each invalidate the affected evidence in test. Fails where a preset's source-endpoint coverage report is accepted as a statement about the promoted image. |
| Qualification: maintenance | Uncommissioned workflow comparison under Q20a | Canceled Q20b supplied no maintenance measurement. A future proposal must price and record representation change, proof repair, checking cost and held-out replay | Executable churn, specification churn, proof repair, checking cost and target resource consequences are reported separately. Fails where proof rediscovery and saved-term replay are reported as one figure. |

### Metaprogramming and compiler-service extension

The [metaprogramming dossier](metaprogramming.md) refines the intended language
with required-static evaluation, opt-in descriptions and contextual checked
generation. The existing combined client does not exercise these mechanisms.
The [qualification cases](metaprogramming.md#qualification) add inhabited
generation clients and well-formed negative neighbors; they supply no executed
verdict. Current prototype normalization and computed types establish neither
general reflection nor composition with graded ownership, handlers and async.

The [plan's `vela-meta` and `vela-compiler-services` stages](../../../../PLAN.md#vela-whole-system-authoring-proposal)
own additional implementation scope. Their costs remain `unpriced` pending
selection of a supported slice and its interpretation, descriptor protocol and
source-correspondence boundary. Existing ranges above are unchanged and fund no
general evaluator, reflection API, staged calculus or public compiler-service
implementation. The [tooling contract](../tooling-protocols.md#compiler-inspection-api)
extends these joins to concrete/typed/elaborated/analysis/lowering inspection,
syntax assets, SARIF/SCIP, build integration, remarks and compiler traces. Their
separate proposal owners, conditional debugger protocols and generated-output maps
remain unpriced; the existing ranges and Q25n's bounded LSP increment fund none
of those additional adapters or missing semantic/backend producers. Price shared
work once at the following joins:

| Duty | Existing join and additional acceptance |
| --- | --- |
| Static evaluation, dependent reindexing and generated resource uses | `core-soundness`: preserve the graded/resource interpretation and kernel-compatible conversion; no static knowledge follows from erasure or a grade. |
| Description, hygiene and generated-source correspondence | `core-frontend`: bind descriptor dictionaries, declaration identities, scoped generated terms, target/ABI and the exact resulting computation; no arbitrary elimination of `Type` or trusted generator result. |
| Diagnostics, claims and tooling | `core-diagnostics` and `preset-policy`: preserve source provenance and current evidence status; `vela-compiler-services` exposes shared versioned views, and LSP/SARIF/SCIP consume projections. Syntax assets follow the canonical grammar; build, remarks and trace adapters consume their actual producers. No second semantic implementation or proof-acceptance path. |
| Lowering and runtime-cost qualification | Existing compiler, admission and hardware owners: retain effects, exits, leakage, representation and final-artifact evidence; inspect removal of generator machinery and measure residual code, descriptors and specialization growth. |

These optional joins retain the concrete-law, checked-correspondence and commissioning prerequisites below. R-05-020a classifies the interpreted producer; it supplies none of the missing implementation or proof artifacts.

### R-05-009, R-05-020, and what holds the frontend rows

[R-05-020a](../../../spec.md#r-05-020a) selects R-05-009's untrusted,
kernel-rechecked elaboration route. The graded, control and mutation dossiers
commit to a reviewed interpretation in existing anchors. Their judgments and
step notation state constraints and theorems about the elaboration image;
substitution, dependency, ownership, exits and erasure preserve that image's
interpretation. They do not grant an independently meaningful source reduction
authority beside Gallina/CIC or the one Iris-over-Sail logic.

The boundary still requires source correspondence. A producer can emit a
well-typed theorem about the wrong computation. Parsing or parse validation,
resolution, instance selection, implicit insertion and desugaring must connect
exact source and generated inputs to the checked term. A stale source binding,
a changed dependency or a well-typed replacement operation must fail the same
correspondence obligation. Kernel checking and hashes alone do not establish it.

The classification decision is settled; production frontend rows remain
uncommissioned until their actual prerequisites and scoped acceptance exist.
[Q25w and the delivery stages](../../../../PLAN.md#vela-first-release-delivery)
first investigate concrete buffer laws, then commission the selected synchronous
implementation. Existing bounded mathematical, syntax and diagnostic prototypes
keep their declared evidence endpoints. This amendment supplies no primitive
law, metatheory theorem, backend, trusted checker or binary admission verdict.

A future independent semantics or accepting checker takes R-05-020's full
amendment route. Machine-model replacement additionally retains the
[canonical-model migration](unified-source-contract.md#migration-and-retirement)
duties. The optional whole-system goal grants no exception.

### R-08-046, and what the language's runtime-varying storage is

R-08-046 requires declared bounded pools and complete manifests for static backing with variable occupancy; unclassified counters, arenas, queues or tables affecting admission/progress are review findings. Comparing this design with the current inventory gives the following classification.

| Storage kind | Covered by a member of R-08-046's current inventory? |
| --- | --- |
| Task frame, the represented storage a dormant or suspended computation occupies | No. The nearest members, protocol control blocks and checkpoint transaction slots, are bound to a named protocol or transaction rather than to a source-level computation. |
| Child slot, a scope's declared child capacity | No, and its exhaustion is the capacity verdict the path table above already requires. |
| Scope record, the registered structured scope itself | No. |
| Continuation storage | No, and a captured continuation's occupancy varies with resumption and disposal rather than with a session or a grant. |
| Completion record, the pre-reserved terminal capacity a child's outcome is written into | No. |
| Dynamic-borrow guard slot | No. |
| The accepted-byte counter with its outstanding allowances | Not a pool, and this is a classification rather than an exclusion: its backing is one scalar of fixed width whose members are never bound and released, so the subject R-08-046 names has no referent here. R-08-045's charge covers the scalar, the conservation of committed value against outstanding allowances is a source-level invariant, and overflow is `MUT-ATOMIC`'s law rather than a capacity verdict. |

Every unplaced kind owes R-08-046's full manifest. This design supplies some field kinds, no concrete values.

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

**A new class is required before the later runtime extension.** The synchronous first release introduces none of these task/continuation/guard pools. Before their implementation, a selected service must supply a concrete manifest and lifecycle refinement, followed by the R-08-046 inventory/prose amendment and co-read. R-05-020a settles producer classification but supplies no pool law or capacity. This review answers F-354's classification duty; the runtime amendment remains owed.

## What this review establishes and what it does not

This design review supplies rules, a composed source-level client, a named representation and owner/estimate/predicate accounting without duplicating existing Q2c/Q21a/Q21b/Q2b/Q20b/Q20c/M1 work. Integrated document gates and required co-reads decide design acceptance. Mechanization, frontend admission, target execution and timing retain separate acceptance predicates; none is established here.

R-05-020a and the interpretation commitments settle the source-classification act. R-08-046's runtime-storage extension remains conditional on a concrete later service and complete lifecycle manifests. The first-release delivery gate retains all missing concrete laws, checked correspondence, implementation and artifact evidence; neither a design decision nor a parameterized theorem price closes them.
