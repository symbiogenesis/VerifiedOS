# Assurance presets and evidence policy

> Non-normative Q25 policy proposal; no preset, report, frontend or diagnostic here is implemented. Start with the [primary Vela design and examples](verification-strategy.md). [Q25](../../../PLAN.md#q-assessment-actions) owns design gates, Q25d prices implementation, and the [requirements register](../../requirements-register.md) governs admission.

## Scope and the governing rule

One authoring surface and executable implementation support three assurance presets: **Safe**, **Contracted** and **Complete**. A preset selects the claims a build must establish; each retains the safety obligations of its operations and execution profile. Library proofs and automation may satisfy Complete for an application whose author writes no theorems, while a systems author may select Safe.

> **Omitting a claim is permitted. Treating an unestablished claim as established is not.**

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

The [metaprogramming contract](metaprogramming.md) applies the same policy to
generated definitions, specialized instances, descriptors and dependencies.
Generation alone establishes no optional contract. A generated theorem is usable
only with its checked evidence and current source/dependency correspondence;
an unestablished generated claim cannot justify optimization. Static evaluation
must not erase an effect, runtime check or mandatory result merely because a
generator or usage analysis does not need its value.

## The three presets

### Safe: ordinary programming without optional theorem obligations

Safe supports ordinary functions, records, collections, parsers, iteration and profile-compatible async interfaces. It establishes the supported fragment's enumerated type, ownership, initialization and permitted-effect obligations. Optional functional specifications, algorithmic loop invariants and named lemmas may be omitted; libraries hide their implementation proofs. Runtime bounds and validation checks are allowed when the profile permits their explicit failure behavior and resource cost.

Required type safety, public invariants, legal reuse and admission obligations remain mandatory. If automation fails, use a supported checked operation, simplify the implementation, prove the obligation or declare a permitted trust boundary. Assuming success is unavailable.

### Contracted: selected stronger claims become mandatory

Contracted adds selected functional, protocol or resource contracts to functions, modules or package interfaces. Every claim consumed by a client or optimization requires acceptable evidence, which inference, verified construction or a checked boundary may supply without handwritten proofs.

Unselected code retains its ordinary interface; linking beside verified code conveys no sortedness, resource, confidentiality or progress guarantee. The report names verified scope and assumptions. An open required goal blocks the stronger contract even if the program can build under an explicitly weaker interface.

### Complete: policy-complete verification over a declared boundary

Complete requires coverage of a release's specified requirements, executions, implementation closure, environment assumptions and evidence endpoint. Every resulting obligation is discharged; pending goals, unapproved axioms and unchecked dependency contracts cannot pass silently.

Helpers may be covered by enclosing proofs or automatic analysis. A service can intentionally run forever while proving progress of each admitted request. Timing, termination, deadlock freedom, safety and information flow remain separately named requirements. Approved assumptions remain visible, including the foundational/environmental trust base allowed by [R-05-164](../../spec.md#r-05-164); prohibiting project-added axioms does not establish zero trust.

### Default obligations

| Obligation or feature | Safe | Contracted | Complete |
| --- | --- | --- | --- |
| Baseline language and profile safety | Required | Required | Required |
| Handwritten theorems | Not routinely required | Where other evidence is insufficient | Not inherently required; every required goal is discharged |
| Optional functional specifications | May be omitted | Required in selected scope | Required to express release requirements |
| Unproved optional annotation | Visible as unestablished; unusable as a theorem | Cannot satisfy a selected contract | Blocks release where required |
| Runtime validation | Where the profile permits it | For explicitly checked boundary properties | Where requirements permit rejection and account for cost |
| Unsafe or foreign implementation | Explicit boundary and actual safety guarantees | Same, with transitive contract accounting | Meets release proof/assumption policy |
| Coverage report | Baseline and exported evidence | Selected claims and dependencies | Requirements, closure, assumptions and endpoint |

## Claim status, and what each status licenses

Evidence attaches to claims. Every exported claim has one machine-readable status.

| Status | Meaning | Permitted consumers |
| --- | --- | --- |
| Established | Accepted evidence proves the property under recorded assumptions | Proof search, elimination, proof-based optimization and dependent contracts |
| Checked on success | A verified boundary establishes a decidable predicate when successful; failure remains possible | Success branch only; failure behavior and cost remain accounted |
| Conditional | Result depends on a declared external assumption | Consumers carrying that assumption into their own reports |
| Unestablished | No accepted evidence | No proof search, safe elimination or proof-based optimization |

Tests and measurements establish no universal theorem. A solver timeout is no counterexample; unchecked unsatisfiability is no accepted proof. Checked success promises neither universal parsing nor inexhaustible allocation: invalid input and [bounded-pool exhaustion](../../spec.md#r-08-046) remain explicit outcomes.

An ordinary sorter may export an array without sortedness. An opaque sorted-array invariant requires a verified algorithm, verified validation or approved assumption; disabling verification cannot manufacture that stronger value through a safe interface. Mutable abstractions must also control invalidating writes. Validation of one snapshot licenses no later write or alias, under the [snapshot rules](interior-mutability.md#snapshots-and-dependent-indices). Verus's ignored code, external specifications and assumed contracts provide a trust-accounting precedent in [the survey](verification-strategy.md#what-the-rust-verifiers-contribute).

### Evidence beside the declaration

Generated API documentation, signature help and editor contract views display each
claim's status and evidence endpoint beside its source spelling. The status is
text, not just color or a package-wide assurance badge. `Conditional` names its
assumptions; `Checked on success` names the outcome that establishes the claim.
The linked evidence view supplies the assumptions and exact subject for an
`Established` claim. The same declaration can have different evidence across
builds without acquiring different execution semantics.

For example, the declaration below is authored normally; its final line is
generated API information for a build that has not established the postcondition:

```text
public void Sort(ref Span<Key> keys)
    ensures IsSorted(keys.Model);
    // Evidence: Unestablished; endpoint: source; unavailable to callers.
```

The display reads the [release and policy record](#erasure-compilation-and-the-release-record)
for the exact resolved claim, source closure and semantic dependencies, selected
build configuration and endpoint. A missing, stale or incompatible record shows
`Unestablished` with its reason. A declaration's name or unchanged source span
cannot preserve an old `Established` status after its dependencies change.
Exported documentation identifies the build it describes; an editor showing
changed source cannot present that historical verdict as current evidence.
Source-endpoint evidence stays visibly distinct from evidence about final bytes.
These are presentation requirements on the existing claim statuses; comments and
displayed badges confer no proof authority.

## Composition across mixed assurance

| Call boundary | Rule |
| --- | --- |
| Ordinary caller into verified library | Preconditions are inferred, proved or checked through the public interface; callers need not see the proof language. |
| Verified caller into ordinary implementation | Rely only on its established interface; stronger behavior needs evidence or a declared assumption. |
| Verified caller into validating wrapper | Rely on the exact success predicate, effects and failure behavior the wrapper establishes. |
| Any caller into unsafe/foreign implementation | State safety preconditions, ownership transfer, effects, failure behavior and transitive trust provenance. |
| Generic, callback or dynamic dispatch | Account for every permitted implementation or prove robustness against the declared external behavior. |

Postcondition validation cannot repair earlier memory corruption, disclosure or unbounded stalls. It substitutes for proof only where the predicate can be established at that boundary.

Unresolved editor/scratch annotations cannot influence accepted typing or compilation as facts: [typed holes stay outside accepted packages](verification-strategy.md#mechanically-produced-evidence). Explicit interface downgrades recheck dependents and remove unjustified theorem-dependent optimization or invariant elimination.

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

Application interfaces cover parsing, bounded collections, iteration, errors and structured async without unexpectedly exposing separation-logic resources or grade algebras. A parser returns a valid packet or explicit failure while its library accounts for bounds and backing ownership; loop/iterator interfaces supply routine bounds facts.

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

The [pricing table](full-language-review.md#reviewed-implementation-pricing) owns each stage's implementation owner, estimate and predicate. Its [frontend disposition](full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows) holds policy-semantics, ordinary-application and systems-boundary qualification. Complete-release and maintenance work stays with cited production owners and the uncommissioned workflow comparison; this dossier schedules none.

| Stage | Exercise | Acceptance |
| --- | --- | --- |
| Policy semantics | Claim status and mixed-assurance rules on bounded core | Reject invented invariants, unresolved safety goals, hidden assumptions and optimizations retained after verification is disabled |
| Ordinary application | Parser, collection and service using application interfaces alone | Strengthen assurance with executable reuse; record every code change and identify rewrites |
| Systems boundary | Arena and hardware-facing async operation through cancellation, late completion, errors and exhaustion | Establish when backing becomes reusable under cancellation and quiescence rules |
| Complete release | Requirements over declared closure and endpoint | Dependency changes, callbacks, foreign interfaces and generated code invalidate affected evidence in test |
| Maintenance | Representation change, concurrency, new failure path, replaced library | Separate executable/specification churn, proof repair, checking cost and target resources |

The existing `preset-policy` and `core-diagnostics` owners qualify
[evidence presentation](#evidence-beside-the-declaration) with all four statuses
in signature help and exported API views. Controls change a claim, its dependency,
the selected build configuration or the requested endpoint, and remove its evidence
record: none may retain an incompatible established verdict. Conditional assumptions
and success-only outcomes remain visible, and a historical documentation export
keeps its build identity when the editor's current source has changed.

Acceptance requires sound assurance boundaries and useful ordinary clients under composition/change, without a predetermined automatic-proof percentage.

## What this dossier does not establish

This proposal claims no usability, build-time, annotation-burden or search-scalability measurement; automatic proof of arbitrary programs; optimal compilation; proof-free unsafe primitives; or recovery of requirements from source. It amends no requirement or admission rule; changes must satisfy their normative owner's predicate.

SPARK's [usage scenarios](https://docs.adacore.com/spark2014-docs/html/ug/en/usage_scenarios.html), [Dafny's contracts and ghost material](https://dafny.org/dafny/DafnyRef/DafnyRef) and [Verus's trust accounting](https://verus-lang.github.io/verus/guide/tcb.html) supply adoption patterns and vocabulary, with wider assessment in the [research landscape](verification-strategy.md#research-landscape) and source/licence readings in the [proof inventory](../../assurance/proof-reuse.md). Their conclusions transfer only to the checked artifact when its premises match; performance experiments neither establish nor invalidate those logical results. No upstream is incorporated; incorporation requires the selected artifact's [licence reading](../../../THIRD-PARTY.md).
