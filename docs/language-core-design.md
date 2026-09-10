# Bounded language core and qualification contract

> Non-normative Q21a design record. The decision declines commissioning the present core qualification under its missing foundation and translator-admission prerequisites. The bounded design below supplies no implemented frontend, proved metatheory or production qualification. The [requirements register](requirements-register.md) remains authoritative. [The strategy](verification-language-strategy.md#a-compositional-core) states the wider objective; [the implementation checklist](implementation-checklist.md#q-assessment-actions) owns scheduling.

## Decision and boundary

Retain a synchronous core with stable dependent values, explicitly sequenced computations, resource-indexed exits, fixed representations and a finite loan tree as the conditional design. Its proposed qualification covers fallthrough, ordinary return, `Result` propagation, branch-sensitive returned shared loans, bounded loops with `break` and `continue`, statically disjoint fields and nested reborrowing. These are design cases, unavailable as a Vela implementation today. Q19's callback pilot establishes none of this flow analysis by itself.

**Decision: decline commissioning this qualification.** The [foundation map's review decision](cheri-foundation-map.md#review-decision) leaves its concrete resource interpretation and machine connection without checked laws or responsibly bounded implementation cells. In particular, the composed returned-view exit below needs concrete split, suspension and restoration laws that its proposed syntax rules cannot provide. The general frontend also lacks the retiring interim required for translator admission. This is a rejection under Q21a's present prerequisite predicate, with [specific reopening evidence](#decision-and-reopening-evidence); it establishes neither an inconsistent calculus nor an infeasible language product. Q19a/Q19b, the conditional library pilot and the existing realization route retain their own entry conditions.

The runtime fragment admits machine integers, bytes, fixed records, finite tagged sums, statically sized buffers, explicit parameters and statically resolved calls. Public capacities and layouts specialize before emission; runtime lengths and result discriminants remain represented. A statically known total shared-call callback may specialize with its immutable environment and a proved representation. General higher-order runtime functions, recursive heap data and dynamic dispatch are outside this qualification. Dependent families and total pure functions remain available for specifications and proofs when their accepted Rocq terms and assumptions permit them; that availability does not make every such type representable at runtime.

There is no source allocation, implicit boxing, unwinding, suspension, cancellation, effect handler, concurrent interior mutation or loan crossing a service activation in this fragment. Its loops terminate; an unbounded service loop requires a separate progress contract. Revocation, DMA, publication ordering and arbitrary adversarial contexts remain obligations at their existing owners. A sequential memory theorem cannot replace them. Kernel conversion, universe rules and the assumption ledger are unchanged.

The general frontend has no identified retiring interim, so [R-05-020's translator admission](spec.md#r-05-020) remains unresolved. Rocq-native output alone does not satisfy semantic nonduplication and retirement. Implementation packages below require that decision before opening; documenting a core interpretation does not make it a new semantic anchor.

## Inputs and their actual subjects

The source inspection uses repository revision
`4aeaceedf4626ef64583a4680c19da29a469df4f`; Q20a's historical comparison
inputs retain the identities in its own record. The
[foundation map](cheri-foundation-map.md) records available constants and missing
connections; the [workflow contract](language-workflow-contract.md) owns the
pilot comparison, and the [compiler-route contract](compiler-route-contract.md)
owns its separate full-artifact comparison.

| Input | Inspected subject | Design use and limit |
| --- | --- | --- |
| [DescriptorCheck.v](../tools/bedrock2-lowering/DescriptorCheck.v) | `Descriptor.descriptor_check`, `spec_of_descriptor_check`, `descriptor_check_br2fn_ok` | The header check reads bytes within declared length, returns a status word and preserves its byte-array footprint and frame. Its relation uses `BasicC64Semantics`; it neither copies bytes nor proves a CHERI memory rule. Request identifiers, offsets, lengths and session permissions remain validated at use. |
| [RingContract.v](../proofs/RingContract.v) | Generated layouts, operation declarations and status/lifecycle definitions | An extension evaluates layout constants from this owner. The core creates no competing wire enumeration or ring lifecycle. |
| [CopyRingService.v](../proofs/CopyRingService.v) | `svc_op_record`, `service_conjuncts`, `the_staging_buffer_holds_the_declared_payload`, `every_held_reference_is_released_at_cleanup` | These constrain declared capacity and released-reference accounting. The file supplies no byte copying, memory implementation or Ztso refinement. Private staging is a reserved independent consumer, not an implementation baseline. |
| [Q19/Q20](implementation-checklist.md#q-assessment-actions) | Concrete-law entry gate and initial/held-out comparison | Parser destination initialization develops the pilot; staging stays held out until interface freeze. Missing consumer implementations belong to Q2b/M7.1. Eventual-core cases are separate from that callback workflow. |

The proposed parser-derived extension initializes its fixed private destination whole, copies each admitted input byte once into it and validates that private copy. This development contract exercises [the initialization obligation](spec.md#r-05-124), with failure behavior specified below. It does not make the existing header check a complete decoder or make copying an atomic snapshot of a concurrently mutable source.

## Reuse decisions

These decisions consume the [strategy's research comparison](verification-language-strategy.md#type-theory-and-elaboration-reuse); they incorporate no upstream artifact and report no new qualification result.

| Mechanism considered | Selected bounded use | Missing evidence |
| --- | --- | --- |
| Dependent value/computation separation and bidirectional elaboration | Stable pure indices; state change in computations; declared public signatures | Substitution, coherent elaboration and interpretation for the combined fragment |
| Aeneas/Creusot-style borrow-end reasoning and flow-sensitive analysis | Finite parent/child loan tree with restoration predicates; infer ends from uses within a control-flow region | Parent suspension, returned branches and loop joins over the actual logic; no inherited Rust soundness claim |
| DeepSEA/Sepref representation and scoped refinement | One explicit entry/exit representation shared by implementation and functional contract | Actual Rocq/CHERI laws and transport at Q2c/Q2b |
| Equations, Rocq-Elpi and binding generators | Qualify dependent definitions through Q19b; compare suitable generated binding operations before new frontend implementation | Computation, equations and exact assumptions for the selected tuple; generated laws do not extend conversion |
| Modal effects and affine handlers | Closed synchronous summaries only, with one effect presentation | Polymorphism, scoped discharge and handlers remain later extensions |
| RefinedC/Flux-style refinements and Rocq arithmetic automation | Declared arithmetic fragment, checked reconstruction and visible residuals | Correct translation between words, logical integers and target representation |

## Judgments and interpretations

This notation specifies future formal interfaces. It is neither executable Rocq syntax nor a declaration of axioms.

```text
Sigma ; Gamma |- A : Type(u)
Sigma ; Gamma ; Delta |- v : A [phase p, usage q, captures C, representation rho]
Sigma ; Gamma ; Delta |- c : Exit(A, Q) ! E
```

`Sigma` fixes resolution, primitive contracts, the logic instance and representation definitions. `Gamma` contains stable duplicable values, region identities and pure facts. A region identity identifies storage but grants no access. `Delta` contains owned represented values, access permissions, suspended parents and restoration obligations. A shared view can appear in `Gamma` carrying its loan identity; an operation through it still requires that loan's live permission in `Delta`. Duplicating the descriptor neither creates ownership nor extends its lifetime.

`Exit(A,Q)` maps each reachable exit tag to a result and resource predicate, possibly dependent on a represented result tag or scalar. Its interpretation relates the same entry state, execution and exit state under the same representation. `E` bounds operation footprints and named external events. Runtime evaluation is left to right and by value; short-circuiting is explicit control flow. Getters, conversions and callbacks cannot execute outside this judgment.

Resource splitting requires the selected logic's separating conjunction and frame rule, with checked entailments. Pure propositions in Rocq can be duplicated: a proposition-valued token field cannot enforce linearity. The interpreter, context analysis and resource derivation together owe that result. A schematic `Own(region, contents)` is not an accepted memory predicate until its concrete interpretation and operation laws exist.

| Dimension | Interpretation | Refused implicit conversion |
| --- | --- | --- |
| Phase | Runtime, specification and proof; compile-time generators emit checked terms | Specification data cannot supply an unspecialized runtime operand; proof scripts cannot execute target operations. |
| Usage | Unrestricted stable values, affine resources with proved discard, linear restoration/protocol obligations | Affine weakening cannot abandon a required restoration or terminal operation. |
| Capture | Kinded transitive identities; authorities used while evaluating are distinct from those retained by the result | Removing a direct free variable does not remove authority retained through another closure. |
| Representation | Explicit runtime layout or erased checked evidence, fixed at specialization | Erasure cannot remove a runtime length, result tag or represented handle needed by execution. |
| Dependence | Stable values and justified entry/exit snapshots | Mutable cell contents do not become stable type indices; mutation updates a resource predicate. |

A closure exposes shared-call, exclusive-call or consuming-call mode, environment representation, captures, effects and per-call contract. The admitted callback is shared-call, total and immutable. Its invocation count authorizes neither copying a consuming environment nor inferring a machine call count after optimization. Mutable or escaping callbacks require additional transition and representation rules.

### Kinded authority

| Authority | Required interpretation | Consequence |
| --- | --- | --- |
| Memory loan | Spatial access, exclusivity/sharing, lifetime and restoration under frame laws | A pointer alone does not permit access. |
| Hardware capability | Tag, bounds, permissions, provenance and applicable temporal state in the selected CHERI interpretation | A logical identity or flat integer cannot discharge the premise. |
| Effect permission | Permission to request a named operation under its actual contract | A write footprint does not create writable storage. |
| Security permission | Separately proved release/declassification or observation policy | Hardware permissions and effect allowances grant no declassification. |
| Resource budget | Named trace/cost interpretation and composition theorem | A loop count grants neither ownership nor target WCET. |

The fixture requests memory access and closed effects, then proves an observation relation under explicit public inputs. It introduces no declassification operation. A variant requesting one must provide its separate security-policy premise. Removing a requested guarantee theorem while retaining operation laws leaves that request unresolved; no profile flag supplies the missing proof.

### Dependency and joins

A pure dependent function has type `Pi x:A. B(x)` with Rocq-checked universes. A runtime result can have type `Sigma n:RuntimeLength. Payload(n)`, pairing a real scalar with erased evidence. A dependent match retains its discriminant while refining branch facts and resources. An erased existential witness cannot decide executable control flow.

Writing a byte changes `Own(r,xs)` to `Own(r,update(xs,i,b))` under a fixed capacity. A shape-changing operation would consume the old owner and return a differently indexed one under a proved transition; arbitrary resizing is outside this trial. Initialization is a state transition witnessed by writes, never a cast. An entry snapshot is an immutable mathematical value justified by the entry representation and permits no access while its owner is lent out.

Branches join through checked entailments to one common resource predicate or through an indexed sum retaining the alternatives. `Ready(view of dst)` and `Rejected(owner restored)` cannot silently join into `owner restored`. Equality beyond conversion requires a checked transport; runtime equality requires a decision operation and its correctness law. No global UIP, proof irrelevance or extensionality axiom is introduced.

## Loans and control flow

A loan record names parent, footprint, mode, captures and restoration predicate. An exclusive loan suspends overlapping parent access. A reborrow suspends its overlapping parent until descendants end; statically proved-disjoint fields remain accessible. Every shared descendant ends before exclusive access resumes. Ending a loan consumes its restoration obligation once and re-establishes the parent's predicate with the final contents.

The first analysis infers last use within a finite control-flow region and explicit call contracts. Unknown overlap leaves a disjointness proof goal or an explicit unsupported pattern. No iteration-local loan crosses a loop back edge. Borrowed parameters and stable enclosing permissions remain available across iterations, while each iteration closes its local descendants. This restriction does not claim general loop-carried borrow inference.

| Exit | Required result |
| --- | --- |
| Fallthrough or return | End nonescaping loans; return declared owners and linear tokens. |
| `Result` propagation | Elaborate to a match with the error exit's restoration/cleanup proof; no hidden escape rule. |
| Returned shared loan | Transfer the loan and restoration obligation to the caller; suspend overlapping owner access. The caller supplies the owner and outlives the view. |
| Error beside returned-loan success | Return no loan and restore the owner on that branch. A runtime tag identifies its resource predicate. |
| `continue` or back edge | Close local loans, restore the invariant and decrease the termination measure. |
| `break` | Close local loans and establish the exit predicate and represented reason. |
| Cleanup | A total non-failing operation consumes the exact token and preserves the frame. Fallible cleanup is unsupported pending its extra exit rule. |
| Abort, panic or target fault | No source abort/unwind primitive. Operations owe absence of unexpected traps under entry premises; environmental faults retain the target contract's classification. |

The only escaping local loan is a shared view into one statically named borrowed parameter or field. Local-stack loans, dynamically untracked owners, self-referential owners and cyclic captures are outside the fragment. The caller ends the view before resuming exclusive access; inference may insert that proof step at last use without source-level manual restoration.

## Refinement, effects and staging

Automatic refinement covers quantifier-free linear integer arithmetic over bounded scalars, equality/disequality, finite discriminants and congruence to a positive specialization-time alignment constant. Multiplication is by a known constant. Variable products, general nonlinear arithmetic and quantified mathematics remain explicit goals. Machine words enter through checked representability/no-overflow lemmas; intentional modular arithmetic uses explicit word lemmas. Initialization and typestate facts rely on resource rules. Sequence updates and content equality use domain lemmas rather than silently enlarging the arithmetic fragment.

Checking uses conversion, resource/capture rules, reconstructed arithmetic, domain automation and explicit proof in that order. Timeout, unsupported formulas or failed reconstruction leave goals unresolved. [R-05-017](spec.md#r-05-017) keeps its reconstruction duty. Proof search proves the chosen contract and cannot weaken it to close a goal.

Effects are closed read/write/call footprints with no allocation, including transitive callees and environments. Sequential footprints take union; named event counts add. Alternative exact counts must agree or become a proved bound or result-indexed count. Stack slots and specialized environments retain size/layout obligations. Effect variables, general grades and handler discharge are deferred.

A generator records its inputs, environment and outputs, which undergo typing, proof and source-correspondence checks. Only total pure definitions execute in type conversion. A compile-time constant can choose a specialized layout; a runtime length cannot retroactively specialize it. Erasure preservation covers runtime results, effects, control decisions and required observations under the same representation; checking an erased proof term alone supplies no such theorem.

## Composed qualification fixture

`PrepareAndInspect` develops the parser-derived private-copy extension. Its notation is illustrative, with no available API claimed. `Workspace` contains statically disjoint `bytes : Buffer(N)` and `audit : Cell(word)` fields. Capacity `N` specializes to a representable bound; requested input length `n` and available source extent `s` remain represented. Entry grants an initialized immutable source of extent `s`, with `n` a representable nonnegative request; it does not assume `n <= s` or `n <= N`. The program checks both before source access or request-derived pointer arithmetic. Input stays immutable during this sequential fixture under its entry permissions; no concurrent snapshot is claimed.

This eventual-core fixture is separate from Q20a's frozen callback client P. P's zero-fill callback and fully restored owner on every exit remain its comparison contract. This fixture retains that fill use and adds an inspection phase, a repeatable copy callback, explicit control-flow loans and the returned-view success alternative. It is compared only with an independently reviewed baseline implementing this same extended behavior. Its success cannot substitute for P's comparison, and its development does not use or redesign Q20a's held-out staging client S.

An abstract linear `PreparationOpen` fixture token models ordinary cleanup. A total non-failing `finish` consumes it and returns `PreparationClosed`, preserving memory. These experiment-local states do not replace the ring lifecycle. Their concrete interpretation and implementation are prerequisites; assuming a `finish` law cannot open the trial.

```text
PrepareAndInspect(ref workspace, in input[s], runtime n, in controls[N],
                  runtime keep_view,
                  in total_shared_callback, tracked PreparationOpen)
  -> Ready(Sigma length. View(workspace.bytes, length), PreparationClosed)
   | Rejected(reason, PreparationClosed)

check n <= s and n <= N, retaining the represented validity result
initialize the entire fixed destination to zero in a bounded loop
  use the total repeatable zero-byte callback with its scoped destination loan
set the disjoint audit field to zero
if n > s: finish; return Rejected(source_too_short)
if n > N: finish; return Rejected(too_large)
copy input[0..n) once into destination[0..n)
  invoke the total shared callback once per copied byte
  callback captures disjoint immutable values; its result does not alter copying
check Descriptor.descriptor_check on the private prefix and represented n
if invalid: finish; return Rejected(invalid_header)

inspect the initialized private prefix in a bounded loop
  create an exclusive bytes-field loan, then a read reborrow
  let reader be a shared-call closure transitively retaining the read reborrow
  call reader; end its last use and the read reborrow
  update only the disjoint audit field under its own loan
  close local loans before continue, break or the next iteration
  loop choices use declared public inspection input

finish
if keep_view: return Ready(n, a shared prefix loan into the caller's workspace)
else: return Rejected(view_not_requested)
```

Inspection controls are separate from header validity. A break never denotes a successfully partial copy. Both callbacks are total and effect-free, with disjoint captured representation; the copy callback's unused result cannot alter the intended bytes. Audit begins at zero and counts inspected indices, including the iteration that takes a break. Each iteration increments its cursor exactly once before any continue, and the bound `n <= N` proves the audit increment representable. Break/continue controls are supplied in a public immutable buffer of fixed capacity `N`, with its own grant; only the admitted prefix of length `n` is inspected. Its grant supplies no source-byte authority. Continue skips no required copy or initialization work, which precedes inspection.

The source trace records `ReadInput(i,b)`, `WriteDestination(i,b)`, `FillCallback(i)` and `CopyCallback(i)`. On an admitted length, each input index below `n` is read exactly once, in order, and no other input index is read. Every destination index receives its fill write before any copy write; fill and copy callbacks have their respective loop counts. Validation/inspection read only the private destination. These are explicit functional/trace obligations in addition to set-valued effects. Transport to machine observations remains the route's proof obligation, and an optimized implementation need not retain source helper-call events as actual machine calls.

On `source_too_short` or `too_large`, the entire destination is initialized to zero and no input byte is read or copied. If both bounds fail, `source_too_short` takes precedence. Otherwise the destination holds the input prefix followed by zeros. `invalid_header` corresponds exactly to the header check's invalid answer on that private prefix; both `Ready` and `view_not_requested` require its valid answer. Audit is zero on pre-inspection failures and otherwise equals the inspected-index count. `Ready` retains real `n` with evidence `n <= s` and `n <= N`, with no decoder consumed-length claim. All exits return `PreparationClosed`, preserve input and unrelated storage, and restore workspace ownership except for the returned prefix loan on `Ready`.

The prefix loan is a logical access footprint with represented base and length. The representation must state the hardware authority actually retained: it cannot claim exactly narrowed CHERI bounds for every runtime length without its narrowing theorem and representability check. Source loan rules permit access only within the prefix; arbitrary linked machine code needs the separately required artifact and contextual guarantees. Disjoint tail and audit access use proved splitting, with no claim that ending an empty prefix loan creates or enlarges authority.

| Point | Required resource predicate |
| --- | --- |
| Entry | Exclusive workspace, initialized immutable source of represented extent `s`, independent represented request `n`, disjoint repeatable callbacks, `PreparationOpen`, effect permissions and satisfiable representation |
| Fill loop | Prefix below cursor initialized to zero; remainder retains initial initialization state; audit/input frame preserved |
| Copy loop | Whole destination initialized; copied prefix equals input; remainder and tail zero; iteration-local loans closed at back edges |
| Inspection loop | Destination unchanged, initialized and header-valid; audit equals pure visited-index summary; no iteration-local loan at back edges |
| Rejected return | Restored workspace with branch-specific contents, no returned loan, preserved frame and `PreparationClosed` |
| Ready return | Shared prefix view, real length and valid-header evidence; parent prefix suspended, disjoint audit restored, frame preserved and `PreparationClosed` |
| Caller match | Use/end the view before prefix mutation on `Ready`; mutate immediately on `Rejected`. Retain branch distinction until checked restoration permits a common join. |

To exercise propagation, give header-result conversion the same two exit predicates and run an equivalent fixture with `Result` propagation at that site. Functional, resource and observation statements stay unchanged. A frontend supporting only explicit return reports propagation unavailable.

The independent behavior review freezes inhabited cases before proof or baseline adaptation: each length refusal (including both invalid bounds), empty and full spans, every declared valid/invalid header family, both final result alternatives, ordinary loop completion, `break`, `continue`, and explicit versus propagated errors. A valid `Ready` witness needs a capacity/source and declared encoding for which the header check succeeds; `n <= N` alone does not establish one. Include distinguishable source bytes, nonzero destination residue, adjacent disjoint fields and an unrelated initialized frame. Expected destination/audit bytes and status are computed from the declared format and specified control vector independently of the candidate. Unexecutable symbolic overflow cases retain proof obligations and no target-measurement claim.

### Intended negative neighbors

Each negative preserves parsing, resolution, supported syntax and unrelated premises of an accepted fixture. Its well-formed operation graph reaches the stated obligation. Missing implementation, parse failure, unrelated theorem failure and timeout are not intended rejection evidence. This record contains no executed negative result.

| Fixture change | First refusing obligation |
| --- | --- |
| Make the copy guard inclusive with the same invariant | Read/write bounds at index `n`; choose admitted `n = s = N` so both extents expose the offending index |
| Drop the source-extent guard but retain the capacity check | Source read at a request satisfying `s < n <= N`; the original `source_too_short` refusal remains required |
| Store into a neighboring location or omit tail initialization | Functional byte relation or initialized-whole exit predicate |
| Read external input again during validation | Copy-once trace contract and private-source refinement |
| Use overlapping parent while reborrow/reader remains live | Parent suspension and transitive capture liveness |
| Return a local-buffer view or mutate parent with returned view live | Capture lifetime or exclusive-access premise |
| Restore owner on `Ready` while retaining its view | Branch exit resource predicate |
| Retain an iteration-created shared view in an enclosing represented option at `continue`, or propagate error with `PreparationOpen` | The no-local-loan back-edge rule or error cleanup predicate; an automatically ended unused loan is not a failing case |
| Call `finish` twice or omit it on `too_large` | Linear consumption or required exit token |
| Repeatedly invoke a consuming callback or capture a mutable-output alias | Calling mode, disjointness or effects |
| Treat an entry content snapshot as current after a write | Updated spatial predicate and snapshot relation |
| Erase `n` or a result tag used by execution | Phase/representation and erasure preservation |
| Present hardware authority at an explicit security-policy premise | Kinded authority with its distinct interpretation |
| Remove an observation guarantee while retaining operation laws | Requested guarantee instantiation |
| Substitute an unchecked solver answer or global UIP axiom | Reconstruction or exact assumption audit |
| Alter desugaring/resolution while replaying the old core proof | Source correspondence and dependency identity |

The observation relation treats input bytes, lengths, inspection controls and status as public. Equal public inputs and related frames require equal specified branch/address/termination and external-event observations, including the callback's contract. Its concrete representation and observation projection state whether addresses are compared literally or through related region placements. This modest relation still needs proof; it supplies neither adversarial-context isolation nor target timing. The secret-dependence probe starts with an otherwise accepted, unused secret scalar parameter and equal public inputs, then uses that scalar to select an observable branch. It must fail the unchanged relation on two represented secret values producing different observations. Reclassifying it public changes the independently reviewed contract and invalidates the comparison.

## Source and compiler boundary

Both routes consume one interpreted computation and representation contract: a sequenced graph with explicit branches, bounded-loop invariants, entry/exit predicates, calls, captures, effects, runtime layouts and requested guarantees. The boundary carries input/output traces and observations, ordinary refusals, target-trap classifications and the theorem excluding unexpected traps under entry premises. It is neutral between block/CFG and SSA implementations. Sharing this interface does not equate workloads: the compiler comparison still pairs P with P and S with S under Q20a; adopting `PrepareAndInspect` requires its own reviewed baseline and trial scope.

A `SourcePackage` binds source/generated-input content, independent contract, parse tree or checked parse validation, qualified names and instances, inserted implicits/transports, desugaring, core graph, derivations and source locations. Interpretation and representation name that same graph and contract. A location map cannot prove correspondence, and a valid theorem about a different graph cannot accept current source.

Lowering, capability-correct selection, optimization, stack/ABI relations, typed linkage and final-byte judgments over pinned Sail remain route obligations. Pointer-to-integer substitution needs its own correct relation; a flat array proof supplies no tag/provenance preservation. Erasing loan bookkeeping cannot erase machine authority. A route may abstract source helper-call events only under an explicit proved projection that preserves every requested externally visible observation and exact input-read/write relation. Functional simulation alone cannot transport relational observations or arbitrary-context guarantees. [Existing compiler duties](verification-language-strategy.md#compiler-amendment-obligations) remain binding.

The shared trial identity records source/contract closure, generated inputs, Rocq/tool/library tuple and flags, actual assumptions, interface/instance, representation/erasure, compiler/assembler/linker/composer revisions, layout, target profile, Sail term/configuration, memory-placement inputs, final image and evidence digests. Unavailable artifacts remain explicit. Hashes identify subjects without proving behavior. Q20a owns equivalent-baseline measurement and Q21b owns the route trial; this core creates no competing benchmark or admission format.

## Typed holes and invalidation

A hole records source expression, semantic environment, expected type/proposition, stable locals, snapshots, branch facts, active/suspended loan tree, kinded captures, call mode, representation, effects, reachable exit predicates and the first missing operation/guarantee premise. Show the source operation and failed rule before raw prover state; retain the full state for inspection.

At the inclusive copy guard, show `0 <= i <= n <= N`, required `i < n` and `i < N`, destination loan and copy-prefix invariant. At failed error propagation, show outstanding `PreparationOpen` and expected `PreparationClosed`. At a post-match mutation, show retained `Ready` view and suspended parent. These are different diagnostics even if downstream search fails at one final theorem.

Status distinguishes current unresolved, refuted with checked evidence where available, unsupported, timed out, stale and accepted by fresh batch gates. Interactive/rendered feedback supplies no acceptance under [R-05-018a](spec.md#r-05-018a). A stable goal identity aids navigation; semantic changes make its status stale even when its displayed identifier is unchanged.

Every result also carries its source/dependency generation and judgment scope. An accepted subgoal does not mark the component accepted while another required obligation remains open. A semantic edit withdraws the previous generation's acceptance before asynchronous replay begins; a late successful response for that generation remains stale. The diagnostic trial exercises this ordering with an old result arriving after a changed bound. Failed proof search means unresolved or timed out, never a refutation without checked evidence. The first missing premise follows the deterministic checking order above and can change after repair; unrelated downstream failures cannot be credited as the intended negative's result.

| Edit | Invalidated evidence |
| --- | --- |
| Rename/formatting | Rebuild source identity, correspondence and maps; reuse terms only after validating unchanged semantic dependencies |
| Bound, failure behavior or operation | Affected typing, termination, functional/resource/effect/observation derivations, then artifact evidence |
| Contract weakening or public/secret classification | Contract review, independent behavior check and dependent guarantees; replay alone cannot approve intent |
| Imported lemma, instance, hints or tool flags | Qualified environment, selected definitions/proofs and assumptions; withdraw stale feedback |
| Representation, layout, ABI or erasure | Instance/representation/erasure proofs and affected resource interpretation, linkage and bytes |
| Parsing, insertion or desugaring | Source correspondence even if the old core proof remains valid |
| Target, compiler flag, relocation or bytes | Affected transport/admission/measurements; host proof timing supplies no replacement |

Record actual semantic inputs rather than filenames alone. Until precise dependency analysis is qualified, invalidate the component closure conservatively. Repair tools propose edits and replay; contract changes require independent review. Semantic edits, semantics-preserving refactors and representation changes are separate measurements. A cache hit or generated proof cannot itself demonstrate reduced review effort.

## Proof obligations and proposed work packages

The following owner keys are proposals, not schedule IDs or proof constants. Each selected package needs a reviewed checklist cell and entry predicate before implementation dispatch. Estimates are prospective attended-work design judgments, not measured agent-session results or conversions of the strategy's person-month bands. They exclude the unbounded foundation work and therefore do not establish a complete implementation price. Keep eventual human attended work, summed agent-session wall time and machine time in separate ledgers under Q20a. The general-logic and machine connections remain [Q2c's prerequisites](implementation-checklist.md#q-assessment-actions); its rejection supplies neither an implementation budget nor a law.

| Proposed owner | Estimate | Work and acceptance boundary |
| --- | --- | --- |
| `core-soundness` | 160 h, range 80-240 | Define judgments/interpreter and prove substitution, phase separation, preservation, loan/exit restoration and kinded authority/effect composition for this fragment over actual supplied logic laws. Excludes concrete CHERI primitive discovery, frontend and backend. |
| `core-frontend` | 140 h, range 80-200 | Restricted parsing/resolution, bounded flow analysis, reconstructed arithmetic, checked elaboration/SourcePackage correspondence and erasure preservation. Excludes general dependent inference, effect polymorphism, kernel, backend and editor. |
| `core-diagnostics` | 64 h, range 40-88 | Adapt the qualified interaction path to frontend derivations, typed holes, status and invalidation; demonstrate the specified source residuals. Excludes Q19a's existing-tool qualification and a new language server. |
| `core-repair-trial` | 48 h, range 32-64 | Author and qualify the combined fixture/negative neighbors and its concrete `PreparationOpen`/`finish` interpretation using the supplied resource laws, then measure semantic/refactor/representation replay and review. Excludes discovering those laws, a repair service and Q20's held-out staging adaptation. |

| Obligation | Existing evidence or missing prerequisite | Owner |
| --- | --- | --- |
| Stable dependent values, universes and resource interpretation | Rocq checks its own terms, not this resource calculus's metatheory | `core-soundness` |
| Byte representations, read/write/frame, initialization and concrete loan laws | `DescriptorCheck` uses another memory model; `CopyRingService` is a statement artifact. No concrete CHERI instance exists in this record. | Q2c's `byte-instance` and `scoped-resources` review obligations remain unpriced after its rejection. Q2b/M7.1 implement consumers; no new core package discovers these foundations within its estimate. |
| Fixture cleanup token | No checked `PreparationOpen`/`finish` interpretation is supplied; its state is not the ring lifecycle | `core-repair-trial` constructs the token and total transition from supplied laws; `core-soundness` proves its usage rules. Failure to construct an inhabited instance blocks the fixture. |
| Loop/return/reborrow/capture analysis | Callback combinators do not supply the selected flow-sensitive rules | `core-soundness` proves rules; `core-frontend` emits checked derivations |
| Parsing, coherent resolution, dependent insertion and source identity | SourcePackage remains a design interface | `core-frontend` |
| Refinement reconstruction and erasure | Existing arithmetic/equality mechanisms need client qualification; combined translation is unauthored | Q19b qualifies reuse; `core-frontend` handles this translation |
| Observation, cost and robust guarantees | An annotation or closed effect set supplies no theorem | `core-soundness` composes supplied laws; Q2c's `machine-logic` and `context-preservation` obligations and Q21b retain concrete connections. These are unpriced obligations, not funded packages; a missing law blocks its requested case. |
| Contextual diagnostics | Q19a concerns existing Rocq clients only | `core-diagnostics` |
| Composed fixture and repair | All cases above are unexecuted | `core-repair-trial`, with independent intended-behavior review |
| Device lowering, optimization, linkage and bytes | Actual producer state and missing connections are Q21b's inventory | Q2b and existing M1/TAL owners retain their booked work. Q2c's `source-transport` and `artifact-admission` review obligations and any route extension need separately reviewed cells for additional work. |

Source syntax composition belongs to `core-soundness`; concrete permissions, disjoint split/join and parent restoration belong to Q2c's `scoped-resources` obligation. SourcePackage checking and frontend erasure belong to `core-frontend`; each route's source-to-IR representation bridge and machine simulation remain at Q2b/Q21b. Shared work is charged once at its actual implementation owner. Giving these obligations keys does not satisfy the missing-law price condition. A source-only qualification requires the concrete laws and guarantees its contract actually uses, without adding every production theory to that entry gate; arbitrary-context preservation and final admission remain required at their stronger endpoints.

## Decision and reopening evidence

The unresolved composed obligation is the `Ready` exit after nested inspection loans: close every reader descendant, preserve the copied bytes and frame, consume the concrete preparation token once, return a shared prefix permission with its restoration obligation, and restore disjoint audit/tail access while overlapping parent access remains suspended. The selected byte/loan representation must establish that entailment over the admitted CHERI machine interpretation, and every rejected exit must instead restore the full owner. Existing descriptor and ring theorems do not have that subject. No checked constant or separately priced implementation cell supplies the missing entailments. This is an unavailable premise, not an executed counterexample to the proposed rules.

Q21a therefore takes its reasoned-rejection arm for commissioning the present qualification. The conditional estimates above cover syntax, frontend, diagnostics and a fixture only after that premise is met; they cannot absorb the unpriced foundation. The R-05-020 admission record additionally needs a demonstrated semantic nonduplication/retirement route before the new frontend opens. Rocq-native output and a SourcePackage design alone decide neither condition. This decision changes no requirement, cancels no existing implementation owner and makes no productivity or compiler-route claim.

Reopening requires a reviewed foundation package selecting the actual representation and Sail-generated term, naming checked laws or separately priced implementation cells with acceptance predicates for each missing connection, and assigning the fixture's additional scoped-resource obligations without charging Q2b/M7.1 twice. It also requires the frontend's R-05-020 admission disposition and a joint review of this source/IR boundary against Q20a and Q21b. If a narrower fixture removes returned loans or other obligations, give it its own independently reviewed contract, costs and comparison scope before implementation; it cannot inherit acceptance for the cases it removes.

Tier-A review decides this bounded design disposition and its explicit missing premises, followed by integrated document gates. The document checker decides corpus rules, not metatheory. A reopened execution additionally requires positive cases replaying at the admitted assumption set, well-formed negatives failing at intended premises, satisfiable entry witnesses, independent behavior checks and current diagnostics after edits. Unavailable cases stay unavailable. Production qualification retains Q20c's stronger endpoint and actual prerequisites.
