# Bounded language core and qualification contract

> Non-normative synchronous-core design. Start with the [primary Vela design and examples](verification-strategy.md) and the [first-release contract](first-release.md). The Q21a fixture retains its [missing prerequisites](#decision-and-reopening-evidence); the [first-release delivery plan](../../../PLAN.md#vela-first-release-delivery) selects bounded work separately. No frontend, metatheory or production qualification is supplied. The [workflow disposition](workflow-contract.md#commissioning-disposition) governs canceled trials; the [requirements register](../../requirements-register.md) governs obligations.

## Decision and boundary

This synchronous core supplies the design boundary for the
[first supported software release](first-release.md#release-boundary): stable
dependent values, sequenced computations, resource-indexed exits, fixed
representations and a finite loan tree. It covers fallthrough/return, `Result`
propagation, branch-sensitive returned shared loans, bounded loops with
`break`/`continue`, disjoint fields and nested reborrowing. Q19's callback pilot
establishes none of that flow analysis. Fixed ownership/use modes and erased
proofs suffice for this slice; arbitrary grade algebras, handlers, async and
concurrent interior mutation are separately selected extensions. Their future
rules must preserve this core's contracts rather than become prerequisites for
its first useful component.

**The concrete foundation remains a prerequisite.** The
[foundation decision](../../hardware/cheri-foundation-map.md#review-decision)
does not supply the complete resource/machine laws for this fixture. The
returned-view exit needs actual split, suspension and restoration laws; syntax
cannot supply them. The selected interpretation is the elaboration's image in
an existing anchor under [R-05-020a](../../spec.md#r-05-020a). Every law below is
a theorem to be checked about that image and its resource interpretation, with
source correspondence binding the exact authored computation. This interpretation
commitment supplies no proof of those laws and admits no independent source reduction.
The [delivery plan](../../../PLAN.md#vela-first-release-delivery) scopes an actual
first consumer, a finite foundation investigation and conditional construction;
it does not reopen the canceled generic pilot or assert that its foundations
are now established.

Runtime types are machine integers, bytes, fixed records, finite sums and statically sized buffers. Parameters are explicit and calls resolve statically. Capacities and layouts specialize before emission; runtime lengths and discriminants remain represented. A known total shared-call callback may specialize with its immutable environment and proved representation. General runtime higher-order functions, recursive heap data and dynamic dispatch are excluded.

Specifications and proofs may use dependent families and total pure functions under the accepted Rocq terms and assumptions. That expressiveness does not establish a runtime representation.

The fixture has no source allocation, implicit boxing, unwinding, suspension, cancellation, handler, concurrent interior mutation or loan across service activations. Loops terminate; unbounded service loops need a separate progress contract. Revocation, DMA, publication ordering and adversarial-context obligations retain their existing owners; a sequential theorem cannot discharge them. Kernel conversion, universes and the assumption ledger are unchanged. Each selected package starts only at its landed entry predicate; its checked interpretation introduces no additional semantic anchor.

## Inputs and their actual subjects

Inspection revision: `4aeaceedf4626ef64583a4680c19da29a469df4f`. The [foundation map](../../hardware/cheri-foundation-map.md) records constants and missing connections; [workflow](workflow-contract.md) owns the pilot comparison and [compiler routes](compiler-route-contract.md) the full-artifact comparison.

| Input | Inspected subject | Design use and limit |
| --- | --- | --- |
| [DescriptorCheck.v](../../../tools/bedrock2-lowering/DescriptorCheck.v) | `Descriptor.descriptor_check`, `spec_of_descriptor_check`, `descriptor_check_br2fn_ok` | The header check reads bytes within declared length, returns a status word and preserves its byte-array footprint and frame. Its relation uses `BasicC64Semantics`; it neither copies bytes nor proves a CHERI memory rule. Request identifiers, offsets, lengths and session permissions remain validated at use. |
| [RingContract.v](../../../proofs/RingContract.v) | Generated layouts, operation declarations and status/lifecycle definitions | An extension evaluates layout constants from this owner. The core creates no competing wire enumeration or ring lifecycle. |
| [CopyRingService.v](../../../proofs/CopyRingService.v) | `svc_op_record`, `service_conjuncts`, `the_staging_buffer_holds_the_declared_payload`, `every_held_reference_is_released_at_cleanup` | These constrain declared capacity and released-reference accounting. The file supplies no byte copying, memory implementation or Ztso refinement. Private staging is a reserved independent consumer, not an implementation baseline. |
| [Q19/Q20](../../../PLAN.md#q-assessment-actions) | Concrete-law entry gate and initial/held-out comparison | Parser destination initialization develops the pilot; staging stays held out until interface freeze. Missing consumer implementations belong to Q2b/M7.1. Eventual-core cases are separate from that callback workflow. |

The proposed parser-derived extension initializes its fixed private destination whole, copies each admitted input byte once into it and validates that private copy. This development contract exercises [the initialization obligation](../../spec.md#r-05-124), with failure behavior specified below. It does not make the existing header check a complete decoder or make copying an atomic snapshot of a concurrently mutable source.

## Reuse decisions

Reuse follows the [strategy's comparison](verification-strategy.md#type-theory-and-elaboration-reuse); no upstream artifact is incorporated or newly qualified.

| Mechanism considered | Selected bounded use | Missing evidence |
| --- | --- | --- |
| Dependent value/computation separation and bidirectional elaboration | Stable pure indices; state change in computations; declared public signatures | Substitution, coherent elaboration and interpretation for the combined fragment |
| Aeneas/Creusot-style borrow-end reasoning and flow-sensitive analysis | Finite parent/child loan tree with restoration predicates; infer ends from uses within a control-flow region | Parent suspension, returned branches and loop joins over the actual logic; no inherited Rust soundness claim |
| DeepSEA/Sepref representation and scoped refinement | One explicit entry/exit representation shared by implementation and functional contract | Actual Rocq/CHERI laws and transport at Q2c/Q2b |
| Equations, Rocq-Elpi and binding generators | Qualify dependent definitions through Q19b; compare suitable generated binding operations before new frontend implementation | Computation, equations and exact assumptions for the selected tuple; generated laws do not extend conversion |
| Modal effects and affine handlers | Closed synchronous summaries only, with one effect presentation | Polymorphism, scoped discharge and handlers remain later extensions |
| RefinedC/Flux-style refinements and Rocq arithmetic automation | Declared arithmetic fragment, checked reconstruction and visible residuals | Correct translation between words, logical integers and target representation |

## Judgments and interpretations

This notation specifies future evidence-construction interfaces. It is neither
executable Rocq syntax nor a declaration of axioms. A judgment proposes an
elaboration and evidence whose subject is its image in the existing anchor.
Substitution, phase separation, loan/exit preservation and erasure must be proved
for those images under the same source-correspondence relation. There is no
independently meaningful source transition system behind the notation.

```text
Sigma ; Gamma |- A : Type(u)
Sigma ; Gamma ; Delta |- v : A [phase p, usage q, captures C, representation rho]
Sigma ; Gamma ; Delta |- c : Exit(A, Q) ! E
```

`Sigma` fixes resolution, primitive contracts, logic and representation. `Gamma` contains stable duplicable values, region identities and pure facts; identity grants no access. `Delta` contains represented owners, permissions, suspended parents and restoration duties. A shared descriptor in `Gamma` names a loan whose live permission remains in `Delta`; descriptor duplication creates no ownership or lifetime.

`Exit(A,Q)` maps each reachable exit of the interpreted image to a result and resource predicate, possibly indexed by a represented tag/scalar, relating the same entry, execution, exit and representation. `E` bounds footprints and named external events. The image evaluates left-to-right by value, short-circuiting is explicit control flow, and getters/conversions/callbacks remain inside the checked interpretation.

Splitting uses the selected separation logic's frame rule, separating conjunction and checked entailments. Duplicable Rocq propositions cannot enforce linearity through token fields; interpretation, context analysis and derivations must do so. `Own(region,contents)` needs concrete operation laws before it denotes accepted memory ownership.

| Dimension | Interpretation | Refused implicit conversion |
| --- | --- | --- |
| Phase | Runtime, specification and proof; compile-time generators emit checked terms | Specification data cannot supply an unspecialized runtime operand; proof scripts cannot execute target operations. |
| Usage | Unrestricted stable values, affine resources with proved discard, linear restoration/protocol obligations | Affine weakening cannot abandon a required restoration or terminal operation. |
| Capture | Kinded transitive identities; authorities used while evaluating are distinct from those retained by the result | Removing a direct free variable does not remove authority retained through another closure. |
| Representation | Explicit runtime layout or erased checked evidence, fixed at specialization | Erasure cannot remove a runtime length, result tag or represented handle needed by execution. |
| Dependence | Stable values and justified entry/exit snapshots | Mutable cell contents do not become stable type indices; mutation updates a resource predicate. |

Closures expose call mode (shared/exclusive/consuming), environment representation, transitive captures, effects and per-call contract. This fixture admits total immutable shared-call callbacks. A source invocation count licenses neither consuming-environment duplication nor optimized machine-call counts; mutable/escaping callbacks need further transition and representation rules.

### Kinded authority

| Authority | Required interpretation | Consequence |
| --- | --- | --- |
| Memory loan | Spatial access, exclusivity/sharing, lifetime and restoration under frame laws | A pointer alone does not permit access. |
| Hardware capability | Tag, bounds, permissions, provenance and applicable temporal state in the selected CHERI interpretation | A logical identity or flat integer cannot discharge the premise. |
| Effect permission | Permission to request a named operation under its actual contract | A write footprint does not create writable storage. |
| Security permission | Separately proved release/declassification or observation policy | Hardware permissions and effect allowances grant no declassification. |
| Resource budget | Named trace/cost interpretation and composition theorem | A loop count grants neither ownership nor target WCET. |

The fixture requests memory access, closed effects and an observation relation under public inputs. It has no declassification; a variant must supply a separate security-policy premise. Operation laws cannot replace a missing requested guarantee theorem.

### Dependency and joins

A pure dependent function has type `Pi x:A. B(x)` with Rocq-checked universes. A runtime result can have type `Sigma n:RuntimeLength. Payload(n)`, pairing a real scalar with erased evidence. A dependent match retains its discriminant while refining branch facts and resources. An erased existential witness cannot decide executable control flow.

A write transforms `Own(r,xs)` into `Own(r,update(xs,i,b))` at fixed capacity. Shape changes would consume the old owner and return a newly indexed one under a proved transition; this trial excludes resizing. Initialization needs writes, never a cast. Bulk prefix relocation between vacant-slot buffers (`Slots<T, capacity>`) separates physical representation copying from logical ownership transfer: `CopyRepresentation` copies bytes and CHERI capability tags into logically vacant destination storage (`Vacant<T>`), leaving the destination unowned and establishing a revision-bound representation-equality fact without arming destructors or duplicating linear resources, and the erased operation `TransferType<T>` consumes that representation-equality fact with the initialized source prefix and vacant destination prefix to transition source `[0..count)` to vacant and destination `[0..count)` to live `T` in one capacity-independent range step. Entry snapshots are immutable values justified by the entry representation and grant no access while ownership is lent.

Branches join through checked entailments to one common resource predicate or through an indexed sum retaining the alternatives. `Ready(view of dst)` and `Rejected(owner restored)` cannot silently join into `owner restored`. Equality beyond conversion requires a checked transport; runtime equality requires a decision operation and its correctness law. No global UIP, proof irrelevance or extensionality axiom is introduced.

## Loans and control flow

A loan records parent, footprint, mode, captures and restoration predicate. Exclusive loans suspend overlapping parent access; reborrows suspend overlapping ancestors until descendants end, while proved-disjoint fields stay accessible. All shared descendants end before exclusive access resumes. Ending a loan consumes its restoration duty once and restores the parent's final-content predicate.

Analysis infers last use within finite control-flow regions and explicit call contracts. Unknown overlap yields a disjointness goal or unsupported pattern. Each iteration closes its local descendants before back edges; borrowed parameters and stable enclosing permissions may persist. General loop-carried borrow inference is excluded.

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

The [ownership library contract](first-release.md#ownership-libraries) supplies
the practical presentation: bounded iteration and spans, fixed `out`
initialization on every normal return, named `invariant Clause: ...` conjuncts
with selective `open (ref ...) lifts Clause, ... { ... }` invariant lifting
(opening only the named conjuncts into a linear `CloseDebt` in `Delta`, keeping
unlifted conjuncts active across disjoint or non-invalidating field writes,
refusing early exits, suspension or whole-receiver calls while the debt is open,
and re-proving only the lifted clauses at block exit), two-step
`CopyRepresentation`/`TransferType<T>` bulk relocation over vacant-slot storage,
and distinct fallible-builder protocols
with explicit partial initialization and rollback. The simple receiver-loan
order remains selected, with footprint diagnostics and a checked snapshot
suggestion where valid. These clients qualify ordinary use of the rules; no
two-phase receiver analysis or unchecked initialization escape is assumed.

### Borrow-analysis promotion

The [loan diagnostic](loan-analysis.md) proposes ends over supplied acyclic
graphs. Promoting that experiment into source checking requires the existing
`core-frontend` and `core-soundness` joins below, using actual concrete resource
laws. A conflict-free diagnostic report supplies none of those joins. Its
[analysis cost and comparison boundary](loan-analysis.md#conditional-borrowing-comparison)
also remains distinct from the production algorithm choice.

| Join | Evidence for the selected source fragment |
| --- | --- |
| Source facts | Checked correspondence relates resolved places, field partitions, control edges, call effects and transitive captures to the exact elaborated computation. Unknown overlap remains a proof goal; names, pointer inequality and library spelling create no separation fact. |
| Loan ends and exits | Checked derivations discharge split, parent suspension and restoration at every reachable exit. Independent source cases cover returned-view success versus restored-owner error, nested reborrows, moved captures, disjoint fields and premature parent reuse. Each invalid neighbor reaches its resource rule after parsing and with an inhabited entry state. |
| Mutation and dependent facts | Writes and transitive call effects transform the current resource predicate. Reusing a current-content fact requires a checked preservation or re-establishment step; immutable historical snapshots stay stable without granting current access. Fresh authorized reads after a value-changing overwrite succeed, a stale equality fails, and a proved-disjoint field fact survives. For a selected library operation that changes represented length at fixed capacity, an old length-three bound used at index two after shortening to one fails; an unsupported operation supplies no semantic negative. This row states the release rule; the extension's [snapshot and invalidation design](extensions/interior-mutability.md#snapshots-and-dependent-indices) develops it for cells, and selecting Ante-style local aliases still requires that separately gated extension. |
| Control and demand | Bounded loops establish their invariant at entry and every back edge, closing local descendants as specified above; acyclic unrolling supplies no loop evidence. Transitive capture checking respects the selected fixed usage modes. General grade checking, suspension, cyclic captures and broader loan escape retain their extension boundaries and require their own checked rules before support is claimed. |

The [first-release qualification](first-release.md#qualification) consumes these
joins on its actual clients. Record unsupported source patterns, unresolved
proofs and exhausted analysis budgets separately from semantic rejection and
checked acceptance. The [independent package trial](../../../PLAN.md#vela-first-release-delivery)
owns any commissioned ergonomic or cost comparison; neither feature coverage
nor a diagnostic's path precision establishes superiority to another checker.

## Refinement, effects and staging

Automatic refinement covers quantifier-free linear integer arithmetic over bounded scalars, equality/disequality, finite discriminants and congruence to a positive specialization-time alignment constant. Multiplication is by a known constant. Variable products, general nonlinear arithmetic and open quantified mathematics remain explicit goals. The [first-release primitive contract](first-release.md#primitive-semantics) fixes source operations and their target binding. Machine words enter through checked representability/no-overflow lemmas; intentional modular arithmetic uses explicit word lemmas. Initialization and typestate facts rely on resource rules. Bounded predicates and subrange projections over finite sequences on `.Model`—`Seq<T>.All(x => ...)`, `.Any(x => ...)`, `.Contains(x)`, `.Take(n)`, `.Skip(n)`, `.Slice(a, b)` and `.Count` when the element predicate stays within the supported fragment—together with sequence updates, vacant-slot prefix/suffix range splits (`[0..length)` and `[length..capacity)`) and content equality use pre-proved standard-library domain lemmas in the refinement/domain tier rather than open `forall`/`exists` quantifier instantiation or silently enlarging the arithmetic fragment. Sparse range obligations stay symbolic in static capacity `capacity` without per-element unfolding, and [qualification](first-release.md#qualification) checks capacity invariance ($N = 4$ versus $N = 10^9$).

Checking uses conversion, resource/capture rules, reconstructed arithmetic, domain automation and explicit proof in that order. Timeout, unsupported formulas or failed reconstruction leave goals unresolved. [R-05-017](../../spec.md#r-05-017) keeps its reconstruction duty. Proof search proves the chosen contract and cannot weaken it to close a goal.

Effects are closed read/write/call footprints with no allocation, including transitive callees and environments. Sequential footprints take union; named event counts add. Alternative exact counts must agree or become a proved bound or result-indexed count. Stack slots and specialized environments retain size/layout obligations. Effect variables, general grades and handler discharge belong to Q25's gated extension designs and are outside this synchronous fixture's qualification.

Generators record inputs, environment and outputs for typing, proof and
source-correspondence checks. Conversion executes only total pure definitions.
The [staged metaprogramming contract](extensions/metaprogramming.md) separates required-static
inputs from ghost/erased indices and use grades, and requires generated terms to
retain their dependent context, captures, effects and exit resources. Its broader
reflection and generation facilities are outside this synchronous fixture's
qualification. Compile-time constants may specialize layouts; runtime lengths
cannot. Erasure must preserve results, effects, control and observations under the
same representation, beyond merely type-checking the erased proof.

## Composed qualification fixture

`PrepareAndInspect` retains the richer parser-derived private-copy regression
contract. The first-release plan starts with its selected real buffer consumer
and actual carrier before qualifying this combined fixture. Selecting this
fixture additionally needs an actual format and valid-header witness; the
symbolic API below supplies neither. `Workspace` contains statically disjoint
`bytes : Buffer(N)` and `audit : Cell(word)` fields. Capacity `N` specializes to a
representable bound; requested input length `n` and available source extent `s`
remain represented. Entry grants an initialized immutable source of extent `s`,
with `n` a representable nonnegative request; it does not assume `n <= s` or
`n <= N`. The program checks both before source access or request-derived pointer
arithmetic. Input stays immutable during this sequential fixture under its entry
permissions; no concurrent snapshot is claimed.

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

Each negative keeps accepted syntax, resolution and unrelated premises, and reaches its stated obligation in a well-formed graph. Missing implementation, parse failure, unrelated theorem failure and timeout supply no intended rejection evidence. All negatives remain unexecuted.

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

The observation relation treats input bytes, lengths, inspection controls, `keep_view`, capture values used by the admitted callbacks, and status as public. Equal public inputs and related frames require equal specified branch/address/termination and external-event observations, including the callback's contract. Its concrete representation and observation projection state whether addresses are compared literally or through related region placements. This modest relation still needs proof; it supplies neither adversarial-context isolation nor target timing. The secret-dependence probe starts with an otherwise accepted, unused secret scalar parameter and equal public inputs, then uses that scalar to select an observable branch. It must fail the unchanged relation on two represented secret values producing different observations. Reclassifying it public changes the independently reviewed contract and invalidates the comparison.

## Source and compiler boundary

Both routes consume the same interpreted sequenced graph and representation contract: branches, bounded-loop invariants, entry/exit predicates, calls, captures, effects, layouts and requested guarantees. It includes traces, observations, ordinary refusals, trap classifications and exclusion of unexpected traps under entry premises. CFG/block and SSA implementations are permitted. Q20a still compares P with P and S with S; `PrepareAndInspect` requires its own reviewed baseline and scope.

`SourcePackage` binds source/generated-input contents, independent contract, parsed or validated syntax, resolved names/instances, implicits/transports, desugaring, core graph, derivations and locations. Interpretation and representation name that same graph/contract. Locations and a proof about another graph cannot establish current-source correspondence.

Lowering, capability-correct selection, optimization, stack/ABI relations, typed linkage and final-byte judgments over pinned Sail remain route obligations. Pointer-to-integer substitution needs its own correct relation; a flat array proof supplies no tag/provenance preservation. Erasing loan bookkeeping cannot erase machine authority. A route may abstract source helper-call events only under an explicit proved projection that preserves every requested externally visible observation and exact input-read/write relation. Functional simulation alone cannot transport relational observations or arbitrary-context guarantees. [Existing compiler duties](verification-strategy.md#compiler-amendment-obligations) remain binding.

Trial identity binds source/contract closure, generated inputs, Rocq/tool/library tuple and flags, actual assumptions, interface/instance, representation/erasure, compiler/assembler/linker/composer revisions, layout, target, Sail term/configuration, placement inputs, final image and evidence digests. Missing artifacts stay explicit; hashes prove no behavior. Q20a owns equivalent-baseline measurement and Q21b the route trial; no competing benchmark/admission format is introduced.

## Typed holes and invalidation

A hole records source expression, semantic environment, expected type/proposition, stable locals, snapshots, branch facts, active/suspended loan tree, kinded captures, call mode, representation, effects, reachable exit predicates and the first missing operation/guarantee premise. Show the source operation and failed rule before raw prover state; retain the full state for inspection.

At the inclusive copy guard, show `0 <= i <= n <= N` and `n <= s`, required `i < n`, `i < s` and `i < N`, destination loan and copy-prefix invariant. At failed error propagation, show outstanding `PreparationOpen` and expected `PreparationClosed`. At a post-match mutation, show retained `Ready` view and suspended parent. These are different diagnostics even if downstream search fails at one final theorem.

Statuses distinguish unresolved, checked refutation where available, unsupported, timeout, stale and fresh-batch acceptance. [R-05-018a](../../spec.md#r-05-018a) admits no interactive/rendered acceptance. Stable goal IDs aid navigation without preserving acceptance after semantic edits.

Every result carries its source/dependency generation and judgment scope. Open required goals block component acceptance. Semantic edits withdraw old acceptance before asynchronous replay; late old-generation successes stay stale. The diagnostic trial sends such a response after a bound change. Failed search is unresolved/timeout unless checked evidence refutes the claim. Report the first missing premise in the deterministic checking order; it may change after repair, and unrelated downstream failure does not count as the intended negative.

| Edit | Invalidated evidence |
| --- | --- |
| Rename/formatting | Rebuild source identity, correspondence and maps; reuse terms only after validating unchanged semantic dependencies |
| Bound, failure behavior or operation | Affected typing, termination, functional/resource/effect/observation derivations, then artifact evidence |
| Contract weakening or public/secret classification | Contract review, independent behavior check and dependent guarantees; replay alone cannot approve intent |
| Imported lemma, instance, hints or tool flags | Qualified environment, selected definitions/proofs and assumptions; withdraw stale feedback |
| Representation, layout, ABI or erasure | Instance/representation/erasure proofs and affected resource interpretation, linkage and bytes |
| Parsing, insertion or desugaring | Source correspondence even if the old core proof remains valid |
| Target, compiler flag, relocation or bytes | Affected transport/admission/measurements; host proof timing supplies no replacement |

Record semantic inputs, not filenames alone; conservatively invalidate the component closure until precise dependency analysis is qualified. Repair tools propose/replay; independent review approves contract changes. Measure semantic edits, preserving refactors and representation changes separately. Cache hits and generated proofs do not demonstrate review savings.

## Proof obligations and proposed work packages

The proposed packages and their estimates are maintained in
[PLAN.md](../../../PLAN.md#language-core-proposals). The obligation matrix below
records the technical prerequisites and ownership boundaries for that work.

| Obligation | Existing evidence or missing prerequisite | Owner |
| --- | --- | --- |
| Stable dependent values, universes and resource interpretation | Rocq checks its own terms; the source-bound elaboration-image and resource laws still need construction and checking | `core-soundness` |
| Byte representations, read/write/frame, initialization and concrete loan laws | `DescriptorCheck` uses another memory model; `CopyRingService` is a statement artifact. No concrete CHERI instance exists in this record. | Q2c's `byte-instance` and `scoped-resources` review obligations remain unpriced after its rejection. Q2b/M7.1 implement consumers; no new core package discovers these foundations within its estimate. |
| Fixture cleanup token | No checked `PreparationOpen`/`finish` interpretation is supplied; its state is not the ring lifecycle | `core-repair-trial` constructs the token and total transition from supplied laws; `core-soundness` proves its usage rules. Failure to construct an inhabited instance blocks the fixture. |
| Loop/return/reborrow/capture analysis | Callback combinators do not supply the selected flow-sensitive rules | `core-soundness` proves rules; `core-frontend` emits checked derivations |
| Parsing, coherent resolution, dependent insertion and source identity | SourcePackage remains a design interface | `core-frontend` |
| Refinement reconstruction and erasure | Existing arithmetic/equality mechanisms need client qualification; combined translation is unauthored | Q19b qualifies reuse; `core-frontend` handles this translation |
| Observation, cost and robust guarantees | An annotation or closed effect set supplies no theorem | `core-soundness` composes supplied laws; Q2c's `machine-logic` and `context-preservation` obligations and Q21b retain concrete connections. These are unpriced obligations, not funded packages; a missing law blocks its requested case. |
| Contextual diagnostics | Q19a concerns existing Rocq clients only | `core-diagnostics` |
| Composed fixture and repair | All cases above are unexecuted | `core-repair-trial`, with independent intended-behavior review |
| Device lowering, optimization, linkage and bytes | Actual producer state and missing connections are Q21b's inventory | Q2b and existing M1/TAL owners retain their booked work. Q2c's `source-transport` and `artifact-admission` review obligations and any route extension need separately reviewed cells for additional work. |

`core-soundness` owns checked interpretation of syntax composition; Q2c's `scoped-resources` owns concrete permissions, split/join and restoration. `core-frontend` owns SourcePackage checking and frontend erasure; Q2b/Q21b retain source-to-IR bridges and machine simulation. Charge shared work once. Keys do not price missing laws. Source-only qualification requires its actual concrete laws/guarantees, while stronger endpoints additionally retain contextual preservation and final admission.

## Decision and reopening evidence

The blocking `Ready` entailment must close nested readers, preserve copied bytes/frame, consume the preparation token once, return a shared prefix and restoration duty, and restore disjoint audit/tail access while overlapping parent access stays suspended. Rejected exits restore full ownership. The selected byte/loan representation must prove these over the admitted CHERI interpretation; descriptor/ring theorems address different subjects. No checked constant or separately priced cell supplies them. This is an unavailable premise, not an executed counterexample.

Q21a's broad trial remains uncommissioned. Its conditional
syntax/frontend/diagnostic/fixture estimates exclude this unpriced foundation.
The interpretation commitment now selects checked elaboration into the existing
anchor; the [composition review](extensions/full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows)
records its acceptance boundary. Rocq output or a SourcePackage sketch supplies
no concrete law or source correspondence. The
[first-release delivery plan](../../../PLAN.md#vela-first-release-delivery) owns
the finite investigation and any separately accepted narrower component. It
claims no productivity result or new compiler-route choice.

Qualifying this fixture needs a reviewed foundation package selecting the
representation and Sail-generated term, supplying checked laws or separately
priced cells and predicates for every connection, and assigning extra
scoped-resource work without duplicating Q2b/M7.1. The image-interpretation and
source-correspondence laws must be checked, with joint review at the actual
compiler/workflow interfaces. A narrower first component excluding returned
loans or other cases needs its own reviewed contract, budget and comparison
scope; it inherits no acceptance for omitted cases. A failed bounded foundation
investigation records its missing premise and stop decision rather than opening
more general frontend implementation.

Tier-A review and integrated document gates decide this design disposition, not metatheory. Reopened execution additionally needs positive replay under admitted assumptions, well-formed negatives rejected at intended premises, inhabited entry states, independent behavior checks and current diagnostics after edits. Unavailable cases remain so; production retains Q20c's stronger endpoint and prerequisites.
