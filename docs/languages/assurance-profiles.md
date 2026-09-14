# Assurance presets and evidence policy

> Non-normative Q25 policy dossier. These are proposed policy semantics, claim statuses and reporting rules, not an implemented preset, a checked metatheory or an admission authority. [Q25](../implementation/implementation-checklist.md#q-assessment-actions) owns the design gates and Q25d prices what this dossier leaves open; the [requirements register](../requirements-register.md) remains authoritative.

## Scope and the governing rule

The [full-language commitment](verification-strategy.md#full-language-design-commitments) is one authoring surface over one executable implementation. This dossier states the assurance policy that surface is selected under: which claims a build must establish, what an unestablished claim may be used for, and what a build reports about the difference. Every rule below is an instance of one:

> **Omitting a claim is permitted. Treating an unestablished claim as established is not.**

Three presets, **Safe**, **Contracted** and **Complete**, are strictness settings over one language. They are not three languages, three runtime semantics or three classes of author: a systems author may build under Safe, and an application written against the simplest library interfaces may satisfy Complete through automatic checking and previously verified libraries. Each retains every safety obligation its operations and its execution profile require. Most application authors write no theorems; the preset decides which claims the build owes, not who is trusted to write them.

**The preset names are deliberately disjoint from the platform's numeric labels.** [The three assurance tiers](../spec.md#r-13-011) classify what the device admits, are decided at install over a binary and its certificate, and scope obligations by the code's position in the trust structure. A preset classifies what a build establishes about a source closure and is decided off device. A preset is therefore never an admission input, confers nothing at admission, and leaves [the refuse-uncertified-code policy](../spec.md#r-13-014) exactly where it stands. The same disjointness holds of [the plan's landing tiers](../implementation/implementation-checklist.md#checklist-conventions), which grade a reading of this repository's own documents.

## Four concerns that one strictness setting conflates

| Concern | Question it answers | Where it is decided |
| --- | --- | --- |
| Authoring experience | Which concepts must this developer manipulate? | Application interfaces, systems interfaces and optional proof-authoring tools under [the feature decisions](verification-strategy.md#feature-decisions). These are surfaces of one language, not mutually exclusive dialects. |
| Assurance policy | Which properties must this build establish? | Safe, Contracted or Complete, expanded into explicit obligations by the rules below. |
| Execution profile | Which operations and resource behavior are permitted? | A named target profile and the [required guarantee theorems](verification-strategy.md#required-guarantees-not-feature-flags) it supplies, the bounded VerifiedOS profile being the first instance. No preset selection adds an operation that profile excludes: garbage collection, arbitrary threads, exceptions and dynamic allocation do not enter it through an assurance setting, and a conventional hosted target would be a separate deliverable rather than a preset. |
| Evidence endpoint | About which representation is the claim established? | The existing [source-verified, artifact-connected and production-qualified split](verification-strategy.md#expected-developer-experience), with the assumptions each result names. |

A single strictness number is not an assurance report. A build reports the expanded property set, the scope it ranges over, the assumptions it rests on and the endpoint it is about. A source-level Complete result is not a machine-code theorem; conversely a safety-certified executable need not carry a functional proof of every aspect of application intent.

**Presets share the meaning of every construct they share.** Selecting a stronger preset cannot silently change integer overflow behavior, evaluation order, ownership, exit behavior or cancellation semantics: those meanings belong to [the feature decisions](verification-strategy.md#feature-decisions) and to the rule dossiers, and a policy setting that moved one would make two builds of the same source two programs. An explicitly selected checked operation keeps its failure behavior, and a proof that removes its check owes the argument that behavior is preserved on every admitted input.

## The three presets

### Safe: ordinary programming without optional theorem obligations

Safe makes useful programming possible through ordinary functions, records, collections, parsers, iteration and profile-compatible asynchronous interfaces. The build establishes the baseline type, ownership, initialization and permitted-effect obligations of the supported fragment. That baseline is part of the language and profile specification and is enumerated there; it is not an assumption that every desirable property follows from calling the fragment memory-safe.

Authors need not supply optional functional contracts, loop invariants for optional algorithmic claims or named lemmas, and libraries hide their implementation proofs behind ordinary interfaces. Bounds and validation checks may establish suitable properties during execution where their failure behavior and resource cost are explicit and the profile permits them.

Safe waives no obligation that is necessary for type safety, a public invariant, legal resource reuse or deployment admission. Where automation cannot discharge such an obligation the available moves are a supported checked operation, a simpler implementation, an explicit proof, or a declared and permitted trust boundary. There is no assume-success switch, and a preset that offered one would be the whole policy's counterexample.

### Contracted: selected stronger claims become mandatory

Contracted verifies selected functional, protocol or resource properties without demanding a requirements-level specification of the whole application. Authors opt specific functions, modules or package interfaces into stronger contracts, and every selected claim that a client or an optimization consumes as a fact carries acceptable evidence. Callers may still need no handwritten proofs, where inference, verified construction or a checked boundary operation suffices.

Unselected code keeps its ordinary interface. It inherits no sortedness, resource bound, confidentiality guarantee or progress property from being linked beside verified code. The build reports the verified scope and the assumptions the selected claims depend on, and a remaining required goal blocks publication of that stronger contract even where the rest of the program still builds under a separately selected weaker interface.

### Complete: policy-complete verification over a declared boundary

Complete lets a release owner mandate complete coverage of a specified requirement set over a specified implementation boundary. The release policy identifies the required properties, the relevant executions, the implementation closure, the environment assumptions and the evidence endpoint; every resulting obligation is discharged, and no pending goal, unapproved axiom or unchecked dependency contract is silently accepted.

Complete does not mean that every helper carries a handwritten theorem or that the system terminates. A helper may be covered by an enclosing proof or by automatic analysis, and a service may require progress of each admitted request while intentionally running forever. Timing, termination, deadlock freedom, memory safety and information flow stay distinct requirements, each named or absent rather than implied.

An approved external assumption remains an assumption. A policy may prohibit every project-added axiom while retaining a declared foundational and environmental trust base, which is the shape [the declared assumption set](../spec.md#r-05-164) already takes for shipped proofs, and its report says exactly that rather than claiming zero trust.

### Default obligations

| Obligation or feature | Safe | Contracted | Complete |
| --- | --- | --- | --- |
| Baseline language and profile safety | Required | Required | Required |
| Handwritten theorems | Not routinely required | Only where other evidence is insufficient | Still not inherently required; every required goal is discharged |
| Optional functional specifications | May be omitted | Required in the selected scope | Required as far as the release requirements need expressing |
| An unproved optional annotation | Visible as unestablished, unusable as a theorem | Cannot satisfy a selected contract | Blocks release where the property is required |
| Runtime validation | Allowed where the profile permits it | Allowed for explicitly checked boundary properties | Allowed where the requirements permit checked rejection and account for its cost |
| Unsafe or foreign implementation | Explicit boundary, no invented safety guarantee | The same, with transitive contract accounting | Meets the release's proof or assumption policy |
| Coverage report | The baseline and the actual exported evidence | The selected claims and their dependencies | Requirements mapping, implementation closure, assumptions and endpoint |

## Claim status, and what each status licenses

Evidence attaches to claims, never to the developer who wrote them. Every exported claim carries one machine-readable status.

| Status | What it says | What may consume it |
| --- | --- | --- |
| Established | Accepted evidence proves the stated property under the recorded assumptions | Proof search, elimination rules, proof-based optimization and dependent contracts |
| Checked on success | A verified boundary operation establishes a decidable predicate when it returns success; failure remains possible | The success branch only, with the failure branch's behavior and cost accounted |
| Conditional | The result holds under an explicitly declared external assumption | Any consumer that carries the assumption forward into its own report |
| Unestablished | No accepted evidence | Nothing: not proof search, not a safe elimination rule, not a proof-based optimization |

Tests and measurements may accompany a claim and never convert into universal proof evidence. A solver timeout is not a counterexample, and an unchecked unsatisfiability answer is not an accepted theorem. Checked on success is not a claim that a function always succeeds: a parser certifies a valid result without promising that every byte sequence parses, and a bounded allocation interface makes exhaustion explicit rather than claiming that arbitrary workloads fit, which is the discipline [the declared bounded pool](../spec.md#r-08-046) already imposes on the platform.

**The invariant boundary is where progressive verification differs from an unchecked promise.** An ordinary sorting function may return an array and export no sortedness contract. A function that exports an opaque sorted-array invariant establishes it by a verified algorithm, by a verified validation step, or by an explicitly approved assumption, and a caller cannot disable verification and manufacture that stronger value through the ordinary safe interface. Where the array is mutable, the abstraction also controls the mutations that would invalidate the invariant: a validation result about one snapshot licenses nothing about later writes or about another alias, which is the rule [the mutability dossier](interior-mutability.md#snapshots-and-dependent-indices) states for snapshots generally. Verus's separation of ignored code, external specifications and assumed contracts is the closest precedent for recording what each of these moves costs in trust, and [the existing survey](verification-strategy.md#what-the-rust-verifiers-contribute) owns that reading.

## Composition across mixed assurance

| Call boundary | Rule |
| --- | --- |
| Ordinary caller into a verified library | The public interface is the whole surface. Preconditions are inferred, proved or explicitly checked, and the library's proof language is not exposed. |
| Verified caller into an ordinary implementation | Only the established interface may be relied on. Stronger functional behavior needs additional evidence or a declared assumption. |
| Verified caller into a validating wrapper | Exactly the property the wrapper establishes on success may be relied on, together with its effects and its failure behavior. |
| Any caller into unsafe code or a foreign interface | Safety preconditions, ownership transfer, effects, failure behavior and trust provenance are explicit and transitive. |
| A generic, callback or dynamic-dispatch boundary | Every permitted implementation is accounted for, or a boundary contract is proved robust against the declared external behavior. |

A runtime postcondition check cannot retroactively repair memory corruption, an unauthorized disclosure or an earlier unbounded stall. Validation is useful exactly where the claimed predicate can be established at that boundary, and is not a general substitute for proof.

Unresolved annotations may live in an editor or a scratch build. They may not influence executable typing or compilation as though they held, which is the existing rule that [typed holes stay outside accepted packages](verification-strategy.md#mechanically-produced-evidence). Downgrading an exported interface is explicit and rechecks its dependents. Compiling with verification disabled retains no theorem-dependent optimization or invariant elimination that has lost its justification.

## What complete coverage must mean

Complete expands a release policy into a property-by-boundary coverage table, not a percentage of functions carrying an annotation. The platform's own [coverage matrix](../assurance/coverage-matrix.md) is the shape: one cell per boundary-and-property pair, each citing what discharges it, so a pair discharged by nothing is a failing check rather than a gap somebody has to notice, and [changing a cell](../assurance/coverage-matrix.md#4-how-to-read-a-cell-and-how-to-change-one) starts from the requirement rather than the cell.

| Dimension | Example requirement | The separate obligation it is easiest to lose |
| --- | --- | --- |
| Functional behavior | A request produces the specified response | The specification expresses intended behavior, not a restatement of what the implementation already does |
| Safety | No invalid access under admitted inputs | Foreign calls, callbacks, generated code, aliases and failure paths are inside the covered set |
| Resources | The service fits its admitted memory budget | Stack, frames, metadata, retained buffers and reclamation delay are counted, not only payload |
| Progress | Every admitted request reaches an allowed terminal result | The scheduler and device premises support the claim; fairness alone is not a deadline |
| Security | Authority and information flow stay inside policy | Functional equivalence and memory safety establish neither confidentiality nor authority confinement |
| Executable correspondence | The required source properties hold of the shipped image | Lowering, optimization, linkage and runtime components carry their own connection |

The declared closure names the reachable implementations, generic instantiations, dynamically selected implementations, library dependencies, generated code and relevant runtime components. An excluded component carries an explicit environmental or boundary model, and a new plugin or foreign implementation either satisfies that model or forces requalification. Requirement identifiers map to formal statements and to checked evidence, and the review that reads them also looks for inconsistent preconditions, unreachable success cases and vacuous specifications, which is the residue the platform's own proof-artifact gates already book in [the residual-risks section](../spec.md#17-residual-risks-the-honest-ceiling) as a person's judgment rather than a build check. Witnesses and negative tests expose mistakes and do not themselves establish that the requirement set is complete, and a specification generated from code can support correspondence while establishing nothing about intent.

## Meanings no preset may reinterpret

A strictness setting selects obligations. It never re-reads a distinction the rule dossiers draw.

| Distinction | Owner | What a preset may not do with it |
| --- | --- | --- |
| Use count, memory permission, information-flow label and cost budget | [The graded foundation](graded-foundation.md#dimensions-and-lawful-domains) | Let a cost or security grade confer exclusive ownership, or read an idempotent domain as single use |
| A captured continuation's transitive resource context | [The handler rules](handlers-async.md#handler-lookup-capture-and-return) | Duplicate an exclusive loan or a single-use token by storing the continuation, or discard a continuation without discharging its cleanup and erasure obligations |
| Requesting cancellation, reaching a terminal state, and becoming safe to reuse | [The cancellation rules](handlers-async.md#cancellation-commit-and-all-exits) and [the typed cancellation protocol](../spec.md#r-12-097) | Read `cancelled` as immediately reusable, or release a frame while a device operation or another participant retains access |
| A justified snapshot against current contents | [The mutability rules](interior-mutability.md#snapshots-and-dependent-indices) | Reuse a dependent refinement about an observed value as a proposition about storage another operation may have written |
| Ghost data against runtime-needed witnesses | [The erasure obligations](graded-foundation.md#inference-specialization-and-admission) | Erase an index or witness execution needs, or read erasure as making a bounds check or dynamic index free |
| A bounded pool's capacity verdict | [The declared bounded pool](../spec.md#r-08-046) | Treat exhaustion as an impossible case rather than a declared result the caller observes |

A dependent proposition over mutable data still needs a stable snapshot or an invariant protocol under every preset: observing a value once does not freeze concurrent storage. Continuations, task frames, queues and cleanup execution still fit the admitted resource and scheduling model, and an application-facing interface that hides those proofs hides the proof and not the obligation.

## A simple subset that stays simple when libraries compose

The application-facing library covers parsing, bounded collections, iteration, error handling and structured asynchronous operations inside the selected profile, and a program combining them does not unexpectedly require its author to manipulate separation-logic resources or grade algebras. A parse operation returning a valid packet or an explicit failure exposes exactly that, while the library accounts for bounds and for the ownership of the backing storage; loop and iterator interfaces make routine bounds facts available without an authored lemma.

This is an interface objective and not a claim that the limits vanish. A bounded collection fills, a borrowed view cannot outlive its storage, and a closure retains what it captures. Diagnostics carry those consequences back in terms of the developer's own operation and values, and distinguish at least a violated rule, a refuted contract, an unknown or timed-out goal, an unsupported feature and an operation the selected profile forbids. Unbounded theorem search does not become part of every keystroke: the predictable ladder is ordinary checking, a declared automatic refinement fragment, domain-specific automation and then a contextual proof goal, which is the [proof-interaction commitment](verification-strategy.md#language-product-contract) measured rather than promised as a percentage.

## Static-memory claims stay separate

A planning interface is independent of Vela syntax and of CHERI: a conventional client supplies an ordinary planning instance and consumes ordinary offsets, and a verified frontend additionally establishes that the instance models every execution its contracts admit. Four claims stay apart, and no preset merges them.

| Claim | What it establishes | What it does not |
| --- | --- | --- |
| Extraction | The permitted executions respect the declared coexistence and safe-reuse constraints | A checked layout is no evidence that the instance models the program |
| Placement | The returned offsets satisfy sizes, alignment, pools, aliases, fixed locations and conflicts | Feasibility is not optimality |
| Optimality or approximation | The returned objective has the claimed relation to the specified feasible set | An optimum for a conservative conflict graph need not be an optimum for the source program |
| Preservation | Lowering and deployment preserve the relevant lifetime, representation and resource properties | Optimal packing removes neither retained authority, nor nonborrowable reservations, nor a missing workload bound |

[The static-memory research agenda](../background/static-memory-research.md) owns the capacity questions and the certificate-checking route; the encoding of memory constraints, its relation to source behavior and its connection to deployment remain the separate obligations named there. These integrations do not wait on the complete language.

## Erasure, compilation and the release record

Ghost data does not reach a runtime result through an unaccounted dependency, and a witness or index that execution needs stays represented. Erasing evidence makes no runtime validation step, bounds check or dynamic index free, and source equivalence alone establishes no stack bound, constant-time behavior or safe capability reuse: erasure, optimization and physical-resource preservation are separate theorems at separate boundaries, which is the split [the compiler obligations](verification-strategy.md#mechanically-produced-evidence) already record.

The release record belongs to that existing evidence package, which binds the source closure, contracts, target semantics, compiler configuration, generated artifact and accepted evidence, and reopens affected obligations when a semantic dependency changes even where names and goal identities are stable. The policy adds exactly three members to it: the selected preset, the obligations that preset expanded into, and the status of every exported claim. A digest still identifies bytes and proves nothing about behavior.

## The policy record

The following is proposed configuration pseudocode, not implemented syntax or existing options. Every profile and endpoint name resolves to a separately versioned definition.

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

Selecting Complete fills no absent requirement with a trivially satisfied property. A release policy whose declared mandatory dimensions lack the necessary specification or evidence is refused rather than completed by default. A Safe authoring workflow may feed such a release, where library proofs and automation discharge every required obligation.

## Qualification protocol

These stages are proposed qualification work under Q25's design gates. Each carries its one reviewed implementation owner, its one estimate and its one acceptance predicate in [the composition review's pricing table](full-language-review.md#reviewed-implementation-pricing), which also states why the policy lane stays closed until that review's admission disposition moves; none is scheduled by this dossier.

| Stage | What it exercises | What decides it |
| --- | --- | --- |
| Policy semantics | Claim statuses and mixed-assurance interface rules on a bounded core | Negative cases reject an invented invariant, an unresolved safety goal, a hidden external assumption and a proof-dependent optimization retained after verification is disabled |
| Ordinary application | One parser, collection and service example written against application interfaces alone | Strengthening its assurance reuses the executable implementation wherever possible, and every required code change is recorded rather than a rewrite being called the same program |
| Systems boundary | An explicit arena and an asynchronous hardware-facing operation, with cancellation, late completion, error paths and exhaustion | The point at which the backing becomes reusable is established rather than assumed, against the cancellation and quiescence rules |
| Complete release | A declared requirement set over the implementation closure and the selected endpoint | Dependency changes, callbacks, foreign interfaces and generated code each invalidate the affected evidence in test |
| Maintenance | A representation change, added concurrency, a new failure path and a replaced library implementation | Executable churn, specification churn, proof repair, checking cost and target resource consequences are reported separately |

The acceptance criterion is not a predetermined automatic-proof percentage. It is a sound assurance boundary and a useful implementation whose ordinary clients stay ordinary under realistic composition and change.

## What this dossier does not establish

No preset, report, frontend or diagnostic described here is implemented, and no measurement of usability, build time, annotation burden or proof-search scalability is claimed. The policy promises no automatic proof of arbitrary programs, no optimal compilation, no proof-free implementation of an unsafe primitive and no discovery of a requirement set from source code. It adds no requirement, amends none, and changes no admission rule: an amendment would name its normative owner and complete that owner's predicate first. The precedents it reads, progressive assurance in SPARK's [usage scenarios](https://docs.adacore.com/spark2014-docs/html/ug/en/usage_scenarios.html), executable code with contracts and ghost material in [the Dafny reference](https://dafny.org/dafny/DafnyRef/DafnyRef), and explicit trust accounting in [the Verus guide](https://verus-lang.github.io/verus/guide/tcb.html), supply adoption patterns and vocabulary, not a proof that this combination is sound or usable; [the research landscape](verification-strategy.md#research-landscape) owns their wider assessment and [the proof inventory](../assurance/proof-reuse.md) owns source and licence readings. A donor's logical conclusions hold without a performance experiment and transfer only where its premises are matched and the intended artifact is the one checked, which is integration work rather than a citation. No upstream is incorporated here, and any incorporation reads the selected artifact's licence under [the third-party discipline](../../THIRD-PARTY.md) first.
