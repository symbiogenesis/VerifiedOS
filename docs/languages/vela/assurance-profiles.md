# Assurance presets and evidence policy

> Non-normative Q25 policy proposal; no preset, report, frontend or diagnostic here is implemented. Start with the [primary Vela design and examples](verification-strategy.md). [Q25](../../../PLAN.md#q-assessment-actions) owns design gates, Q25d prices implementation, and the [requirements register](../../requirements-register.md) governs admission.

## Scope and the governing rule

One authoring surface and executable implementation support three assurance presets: **Safe**, **Contracted** and **Complete**. All require operation safety and evidence for every authored exported contract; stronger presets add properties and coverage. Library proofs and automation may satisfy Complete without application-authored theorems; systems code may select Safe.

> **Optional specifications may be omitted. An exported promise must be discharged before its interface is accepted.**

The policy first applies to the [bounded synchronous release](first-release.md#release-boundary).
Async, general handlers, extensible grade domains and other extensions need their
own consumer and qualification; presets cannot enable unsupported features.

Presets classify source-closure evidence off device. The platform's [numeric assurance tiers](../../spec.md#r-13-011) instead classify binary admission at install according to code's trust role; [landing tiers](../../../PLAN.md#checklist-conventions) classify document review. A preset confers no admission authority and changes no [refuse-uncertified-code policy](../../spec.md#r-13-014).

## Four concerns that one strictness setting conflates

| Concern | Question | Owner |
| --- | --- | --- |
| Authoring experience | Which concepts does the developer manipulate? | Application, systems and optional proof interfaces within [one language](verification-strategy.md#feature-decisions) |
| Assurance policy | Which properties must this build establish? | The preset's explicit obligation set below |
| Execution profile | Which operations and resource behavior are permitted? | A target profile and its [required guarantee theorems](verification-strategy.md#required-guarantees-not-feature-flags); VerifiedOS's bounded profile is the first instance. A preset cannot introduce excluded GC, threads, exceptions or dynamic allocation. A hosted target is a separate deliverable. |
| Evidence endpoint | Which representation does the claim concern? | [Source-verified, artifact-connected or production-qualified](verification-strategy.md#expected-developer-experience), with explicit assumptions |

A build reports properties, scope, assumptions and endpoint. Source-level Complete supplies no machine-code theorem; a safety-certified executable need not prove every aspect of application intent.

Shared constructs retain their semantics across presets: overflow, evaluation order, ownership, exits and cancellation belong to the [language rules](verification-strategy.md#feature-decisions). A checked operation retains its failure behavior; eliminating its check requires preservation on every admitted input.

Under the [metaprogramming contract](metaprogramming.md), generated definitions,
specialized instances, descriptors and dependencies need the same evidence.
Generated theorems require checked evidence and current source/dependency
correspondence before use, including optimization. Static evaluation cannot erase
effects, runtime checks or mandatory results merely because a generator or usage
analysis does not need their values.

## The three presets

### Safe: ordinary programming without optional theorem obligations

Safe supports ordinary functions, records, collections, parsers and iteration within the qualified fragment, establishing its enumerated type, ownership, initialization and permitted-effect obligations. Functional specifications, algorithmic loop invariants and named lemmas are optional when required obligations are otherwise discharged; libraries hide implementation proofs. Authored exported contracts remain mandatory. The profile must permit runtime bounds/validation checks, their explicit failures and resource costs. Async requires separate qualification.

Required type safety, public invariants, legal reuse and admission obligations remain mandatory. If automation fails, use a supported checked operation, simplify the implementation, prove the obligation or declare a permitted trust boundary. Assuming success is unavailable.

### Contracted: selected stronger claims become mandatory

Contracted adds selected functional, protocol or resource specifications at function, module or package interfaces. Every authored exported contract still needs evidence, which inference, verified construction or a checked boundary may supply without handwritten proofs.

Unselected code retains its ordinary interface; linking beside verified code conveys no sortedness, resource, confidentiality or progress guarantee. The report names verified scope and assumptions. An open required goal blocks that interface. Building a weaker interface requires an explicit source/interface change and rechecking its dependents; selecting Safe cannot silently discard an authored clause.

### Complete: policy-complete verification over a declared boundary

Complete requires coverage of a release's specified requirements, executions, implementation closure, environment assumptions and evidence endpoint. Every resulting obligation is discharged; pending goals, unapproved axioms and unchecked dependency contracts cannot pass silently.

Helpers may be covered by enclosing proofs or automatic analysis. A service can intentionally run forever while proving progress of each admitted request. Timing, termination, deadlock freedom, safety and information flow remain separately named requirements. Approved assumptions remain visible, including the foundational/environmental trust base allowed by [R-05-164](../../spec.md#r-05-164); prohibiting project-added axioms does not establish zero trust.

### Default obligations

| Obligation or feature | Safe | Contracted | Complete |
| --- | --- | --- | --- |
| Baseline language and profile safety | Required | Required | Required |
| Handwritten theorems | Not routinely required | Where other evidence is insufficient | Not inherently required; every required goal is discharged |
| Optional functional specifications | May be omitted | Required in selected scope | Required to express release requirements |
| Authored exported `requires`/`ensures` | Required | Required | Required |
| Unproved scratch conjecture | Editor/scratch only; no exported promise | Editor/scratch only; no selected-contract credit | No release evidence |
| Runtime validation | Where the profile permits it | For explicitly checked boundary properties | Where requirements permit rejection and account for cost |
| Unsafe or foreign implementation | Explicit boundary and actual safety guarantees | Same, with transitive contract accounting | Meets release proof/assumption policy |
| Coverage report | Baseline and exported evidence | Selected claims and dependencies | Requirements, closure, assumptions and endpoint |

## Exported contracts and scratch claims

Public `requires` and `ensures` clauses belong to the accepted interface under
every preset. Callers establish the precondition; the implementation establishes
the postcondition and safety/resource duties under it. The precondition need not
hold for every input, but independent review requires satisfiable entry witnesses
and telling negatives to reject vacuous service contracts.

A checked boundary may establish a precondition or result property on an explicit
success branch. Its failure branch, effects and cost remain in the interface;
there is no implicit runtime assertion, trap or unchecked assumption. An external
interface instead names its assumption and provenance explicitly in the resolved
declaration and evidence record, within the platform's existing permitted trust
policy. A preset cannot turn an unproved implementation into such an interface.

Exploratory propositions use a non-exported scratch/conjecture channel with source
context and `Unestablished` status. They cannot use executable `requires`/`ensures`
spelling, enter interfaces, act as elaboration/optimization facts or automatically
become runtime checks. An editor may propose a proof or source edit; promotion
requires the edit, normal checking and current evidence. The current parser and
mathematical prototype implement no conjecture syntax.

## Claim status, and what each status licenses

Evidence attaches to claims. Each claim record, including unfinished editor work,
has one machine-readable status. An accepted exported contract has applicable
evidence; `Unestablished` is never an accepted contract status.

| Status | Meaning | Permitted consumers |
| --- | --- | --- |
| Established | Accepted evidence proves the property under recorded assumptions | Proof search, elimination, proof-based optimization and dependent contracts |
| Checked on success | A verified boundary establishes a decidable predicate when successful; failure remains possible | Success branch only; failure behavior and cost remain accounted |
| Conditional | Result depends on a declared external assumption | Consumers carrying that assumption into their own reports |
| Unestablished | No accepted evidence; scratch or unfinished build only | No accepted exported contract or use as a proof premise, safe-elimination justification or optimization fact |

Tests and measurements establish no universal theorem. A solver timeout is no counterexample; unchecked unsatisfiability is no accepted proof. Checked success promises neither universal parsing nor inexhaustible allocation: invalid input and [bounded-pool exhaustion](../../spec.md#r-08-046) remain explicit outcomes.

An ordinary sorter may export an array without sortedness. An opaque sorted-array invariant requires a verified algorithm, verified validation or approved assumption; disabling verification cannot manufacture that stronger value through a safe interface. Mutable abstractions must also control invalidating writes. Validation of one snapshot licenses no later write or alias, under the [snapshot rules](interior-mutability.md#snapshots-and-dependent-indices). Verus's ignored code, external specifications and assumed contracts provide a trust-accounting precedent in [the survey](verification-strategy.md#what-the-rust-verifiers-contribute).

### Evidence beside the declaration

API documentation, signature help and editor contract views show each claim's
status as text and its endpoint beside the source spelling. `Conditional` names
assumptions; `Checked on success` names the establishing outcome; `Established`
links to assumptions and exact subject. Unfinished snapshots may lack evidence;
accepted builds must discharge the declaration's contract.

For example, this exported declaration requires its postcondition in every
accepted build; the final line illustrates generated API information for one
source-verified build:

```text
public Unit Sort(ref Span<Key> keys)
    ensures IsSorted(keys.Model);
    // Evidence: Established; endpoint: source; exact build and assumptions linked.
```

While its proof is unfinished, an editor shows `Unestablished` and the package
cannot export this declaration as accepted. A developer exploring sortedness
without taking on that interface obligation keeps it in the separate scratch
channel and exports a declaration with no sortedness clause.

The display reads the [release and policy record](#erasure-compilation-and-the-release-record)
for the resolved claim, source closure, semantic dependencies, build configuration
and endpoint. Missing, stale or incompatible records show `Unestablished` with a
reason and block exported-contract acceptance. Stable names/spans cannot preserve
verdicts across dependency changes. Documentation identifies its build; editors
cannot present historical verdicts as current after source changes. Source and
final-byte evidence remain visibly distinct; comments and badges confer no proof
authority.

## Composition across mixed assurance

| Call boundary | Rule |
| --- | --- |
| Ordinary caller into verified library | Preconditions are inferred, proved or checked through the public interface; callers need not see the proof language. |
| Verified caller into ordinary implementation | Rely only on its established interface; stronger behavior needs evidence or a declared assumption. |
| Verified caller into validating wrapper | Rely on the exact success predicate, effects and failure behavior the wrapper establishes. |
| Any caller into unsafe/foreign implementation | State safety preconditions, ownership transfer, effects, failure behavior and transitive trust provenance. |
| Generic, callback or dynamic dispatch | Account for every permitted implementation or prove robustness against the declared external behavior. |

Postcondition validation cannot repair earlier memory corruption, disclosure or unbounded stalls. It substitutes for proof only where the predicate can be established at that boundary.

Unresolved editor/scratch annotations cannot influence accepted typing or compilation as facts: [typed holes stay outside accepted packages](verification-strategy.md#mechanically-produced-evidence). Explicit interface downgrades are source/interface changes that recheck dependents and remove unjustified theorem-dependent optimization or invariant elimination. A build flag cannot perform that downgrade.

## What complete coverage must mean

Complete requires property-by-boundary coverage, following the platform's [coverage matrix](../../assurance/coverage-matrix.md), rather than an annotation percentage. Each cell cites discharge evidence; an empty discharge fails. [Coverage changes](../../assurance/coverage-matrix.md#4-how-to-read-a-cell-and-how-to-change-one) start from requirements.

| Dimension | Example requirement | Easily missed obligation |
| --- | --- | --- |
| Functional behavior | Specified request response | Express intent independently of implementation |
| Safety | No invalid access on admitted inputs | Include foreign calls, callbacks, generated code, aliases and failures |
| Resources | Admitted memory budget | Count stack, frames, metadata, retained buffers and reclamation delay |
| Progress | Allowed terminal result per admitted request | Establish scheduler/device premises; fairness is no deadline |
| Security | Policy confines authority and information | Functional equivalence and memory safety imply neither guarantee |
| Executable correspondence | Source properties hold of shipped image | Connect lowering, optimization, linkage and runtime |

The closure includes reachable implementations, generic instantiations, dynamic selections, dependencies, generated code and relevant runtime components. Exclusions require explicit environmental/boundary models; plugins or foreign implementations must satisfy them or trigger requalification. Requirement IDs map to formal statements and evidence. Review checks inconsistent preconditions, unreachable success and vacuity; its judgment remains a [recorded residual](../../spec.md#17-residual-risks-the-honest-ceiling). Witnesses and negatives do not prove requirement completeness, and a specification generated from code proves no intent.

## Meanings no preset may reinterpret

| Distinction | Owner | Forbidden inference |
| --- | --- | --- |
| Use count, memory permission, information-flow label, cost | [Graded foundation](graded-foundation.md#dimensions-and-lawful-domains) | Cost/security grants ownership; idempotent use means single use |
| Transitive continuation captures | [Handler rules](handlers-async.md#handler-lookup-capture-and-return) | Storage duplicates an exclusive loan/token or permits dropping cleanup/erasure duties |
| Cancellation request, terminal result, safe reuse | [Cancellation](handlers-async.md#cancellation-commit-and-all-exits), [typed protocol](../../spec.md#r-12-097) | `cancelled` frees backing before device/participant access ends |
| Historical snapshot, current contents | [Mutability](interior-mutability.md#snapshots-and-dependent-indices) | An observed refinement survives arbitrary interference |
| Ghost data, runtime witnesses | [Erasure](graded-foundation.md#inference-specialization-and-admission) | Erase execution-needed indices or make bounds checks/dynamic indexing free |
| Pool capacity | [Bounded pools](../../spec.md#r-08-046) | Treat exhaustion as impossible |

Mutable dependencies require stable snapshots or invariant protocols under every preset. Continuations, frames, queues and cleanup still fit the resource/scheduling model; hiding proofs behind an API hides no obligation.

## A simple subset that stays simple when libraries compose

Initial application interfaces cover parsing, bounded collections, iteration and errors without unexpectedly exposing separation-logic resources or grade algebras. Later structured async interfaces must meet the same ordinary-use criterion. A parser returns a valid packet or explicit failure while its library accounts for bounds and backing ownership; loop/iterator interfaces supply routine bounds facts. The [ownership-library contract](first-release.md#ownership-libraries) defines the first client-facing initialization and borrowing cases.

Limits remain visible: collections fill, views cannot outlive storage, and closures retain captures. Diagnostics name the developer's operation and values and distinguish rule violation, refuted contract, unknown/timeout, unsupported feature and profile refusal. Checking proceeds through ordinary checking, a declared automatic refinement fragment, domain automation and contextual proof goals. The [proof-interaction contract](verification-strategy.md#language-product-contract) measures that ladder; it promises no automatic-proof percentage or unbounded search at every keystroke.

## Static-memory claims stay separate

A syntax- and CHERI-independent planner consumes ordinary instances and returns offsets. A verified frontend must additionally connect its instance to every execution the contracts admit.

| Claim | Establishes | Leaves open |
| --- | --- | --- |
| Extraction | Executions respect coexistence and safe-reuse constraints | Layout validity cannot validate the extraction |
| Placement | Offsets satisfy sizes, alignment, pools, aliases, fixed locations and conflicts | Feasibility implies no optimality |
| Optimality/approximation | Objective relation to the specified feasible set | A conservative graph's optimum may differ from the program's |
| Preservation | Lowering/deployment preserve lifetime, representation and resources | Packing removes no retained authority, nonborrowable reservations or workload-bound duty |

The [research agenda](../../background/static-memory-research.md) owns capacity questions, certificate checking, constraint encoding, source relation and deployment connections. These integrations need not wait for the complete language.

## Erasure, compilation and the release record

Ghost data cannot influence runtime results through unaccounted dependencies; execution-needed witnesses stay represented. Erasure, optimization and physical-resource preservation need separate theorems: source equivalence proves no stack, constant-time or capability-reuse bound. The [compiler obligations](verification-strategy.md#mechanically-produced-evidence) retain these boundaries and validation costs.

The existing release evidence binds source closure, contracts, target semantics, compiler configuration, artifact and accepted evidence. Semantic dependency changes reopen affected obligations even with stable names/goal IDs. Policy adds the preset, expanded obligations and each exported claim's status. Digests identify bytes and prove no behavior.

## The policy record

Proposed configuration pseudocode; names resolve to separately versioned definitions.

```text
[authoring]
api_surface = "application"        # does not restrict the eventual assurance

[assurance]
preset = "complete"
scope = "release-implementation-closure"
requirements = "spec/service-requirements"
required_properties = ["memory-safety", "functional", "bounded-memory"]
pending_required_goals = "reject"
project_added_axioms = "reject"
approved_environment = "spec/environment-assumptions"

[execution]
profile = "verifiedos-bounded"
profile_definition = "profiles/verifiedos-bounded"
runtime_validation = "explicit-and-budgeted"

[evidence]
endpoint = "production-qualified-image"
assumptions_manifest = "assurance/assumptions"
coverage_manifest = "assurance/coverage"
replay = "pinned-toolchain"
```

Complete refuses missing specifications/evidence for mandatory dimensions; it never fills them with trivial properties. Safe authoring can feed a Complete release when libraries and automation discharge its obligations.

## Qualification protocol

The [first-release delivery plan](../../../PLAN.md#vela-first-release-delivery) orders foundation, complete software path and independent-client qualification. The [pricing table](full-language-review.md#reviewed-implementation-pricing) retains conditional wider-language estimates; the [frontend disposition](full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows) owns interpretation and concrete-law prerequisites. Complete-release and maintenance work stays with cited production owners. This dossier supplies acceptance criteria without commissioning an implementation.

| Stage | Exercise | Acceptance |
| --- | --- | --- |
| Policy semantics | Claim status and mixed-assurance rules on bounded core | Reject an unproved exported clause under every preset, a flag-only contract downgrade, scratch claims used as facts, invented invariants, unresolved safety goals, hidden assumptions and unjustified optimizations |
| Ordinary application | Parser, collection and service using application interfaces alone | Strengthen assurance with executable reuse; record every code change and identify rewrites |
| Later systems boundary | Separately commissioned arena and hardware-facing async operation through cancellation, late completion, errors and exhaustion | Establish when backing becomes reusable under cancellation and quiescence rules; this extension is no first synchronous-release dependency |
| Complete release | Requirements over declared closure and endpoint | Dependency changes, callbacks, foreign interfaces and generated code invalidate affected evidence in test |
| Maintenance | Representation change, concurrency, new failure path, replaced library | Separate executable/specification churn, proof repair, checking cost and target resources |

The `preset-policy` and `core-diagnostics` owners qualify
[evidence presentation](#evidence-beside-the-declaration) for all four statuses in
signature help and review views. Accepted API views exclude unestablished promises.
Controls change the claim, dependency, build configuration or endpoint, or remove
evidence: incompatible established verdicts must disappear. Keep conditional
assumptions, success-only outcomes and historical documentation's build identity
visible. Preset changes cannot discharge unresolved exported clauses. Prove
validating wrappers' success predicates with errors/resource behavior retained;
reject external assumptions lacking permitted provenance.

Acceptance requires sound assurance boundaries and useful ordinary clients under composition/change, without a predetermined automatic-proof percentage.

## What this dossier does not establish

This proposal claims no usability, build-time, annotation-burden or search-scalability measurement; automatic proof of arbitrary programs; optimal compilation; proof-free unsafe primitives; or recovery of requirements from source. It amends no requirement or admission rule; changes must satisfy their normative owner's predicate.

SPARK's [usage scenarios](https://docs.adacore.com/spark2014-docs/html/ug/en/usage_scenarios.html), [Dafny's contracts and ghost material](https://dafny.org/dafny/DafnyRef/DafnyRef) and [Verus's trust accounting](https://verus-lang.github.io/verus/guide/tcb.html) supply adoption patterns and vocabulary, with wider assessment in the [research landscape](verification-strategy.md#research-landscape) and source/licence readings in the [proof inventory](../../assurance/proof-reuse.md). Their conclusions transfer only to the checked artifact when its premises match; performance experiments neither establish nor invalidate those logical results. No upstream is incorporated; incorporation requires the selected artifact's [licence reading](../../../THIRD-PARTY.md).
