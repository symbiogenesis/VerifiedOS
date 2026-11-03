# Vela compile-time metaprogramming

> Non-normative language contract refining the [primary design](verification-strategy.md#language-product-contract). The [plan](../../../PLAN.md#vela-whole-system-authoring-proposal) owns implementation stages; the [requirements register](../../requirements-register.md) governs admission. This contract supplies no implementation, new semantic anchor, kernel extension or accepted performance result.

## Product and scope

The [first supported release](first-release.md#release-boundary) uses ordinary
total pure computation for required-static constants and finite specialization.
Its bounded software path needs no general reflection API, user-defined grade
algebra or contextual code generator. A narrowly scoped derivation may be selected
only for an actual library client, with an independently fixed input/output
contract and separately priced acceptance work.

Broader typed introspection, boilerplate derivation and hygienic construction of
definitions/evidence are later options. Their admission requires a named consumer,
measured authoring or maintenance benefit over ordinary libraries, and the
composition proofs for the features actually used. Ordinary clients call generated
APIs like other library APIs; generation stays visible through navigation,
diagnostics and inspectable output. The rules below constrain a selected extension
without making the entire extension a first-release dependency.

The [mathematical prototype](elaboration-prototype.md#supported-mathematical-increment)
already exercises type-valued parameters, computed types and bounded definitional
computation. Those mechanisms alone do not expose arbitrary types' constructors,
fields or source declarations. General introspection, generation and their
composition with ownership, effects and grades remain proposed work. The
[frontend prerequisites](full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows)
and applicable [software acceptance](unified-source-contract.md#software-and-proof-boundary)
remain in force; parser support is separately commissioned in the
[surface grammar](surface-grammar.md).

## Evaluation and phase boundaries

Reuse ordinary total pure functions for mathematical computation, type functions,
static values and generator libraries. Generic definitions check symbolically
under declared static requirements. At each demanded instantiation, required-static
inputs must resolve to admissible closed values before emitting its specialization;
an unavailable input leaves a located obligation or refusal, never an implicit
runtime fallback. Infer routine static arguments from a declared interface; public
requirements remain explicit. Typed constant declarations use
[`const T Name = EXPR;`](surface-grammar.md#required-static-constants) as the
required-static value interface. The same keyword marks a constant-compatible
function, `const T F(...)`, or a required-static value parameter,
`T F(const U configuration, V value)`. The function remains callable at runtime;
the parameter makes its configuration available during compilation. A local
constant can require a configuration-derived plan during specialization while
the surrounding function processes runtime data. No separate compile-time-only
function category or constant-expression wrapper is needed. Generic static
parameter binders and generation forms retain their own frontend prerequisites.

Static parameter requirements belong to callable interfaces, including dependent
function telescopes and contextual or explicitly typed lambdas. Partial
application preserves the requirements on remaining inputs. Replacing such an
interface with an ordinary runtime-parameter function type is refused when that
would permit a caller to omit a required static argument.

```text
public const Nat Square(Nat value) => value * value;
public Nat ApplyGain(const Nat gain, Nat sample) {
    const Nat multiplier = Square(gain);
    return multiplier * sample;
}
public const Nat Gain = 4;
public Nat Process(Nat sample) => ApplyGain(gain: Gain, sample: sample);
```

`Process` uses the computed multiplier with runtime samples. Passing its runtime
sample as `gain` is refused even if another helper would ignore that input.
Ordinary admitted total pure helpers remain usable by constant initializers;
the function modifier states an explicit checked capability. Qualification of
the current scalar fragment supplies no implementation of text parsing,
aggregate freezing or a production specialization backend.

Required-static availability is independent of the
[foundation's dimensions](graded-foundation.md#dimensions-and-lawful-domains):

| Distinction | Rule |
| --- | --- |
| Stable versus static | An immutable runtime length is stable enough to index a result, but unavailable to a build-time layout calculation. |
| Static versus erased | A computed table can be retained at runtime; an erased proof cannot supply a runtime value. `ghost` alone neither requests nor establishes static evaluation. |
| Static versus graded | A use allowance constrains its interpreted demand, not when a value becomes available. Grade zero does not erase an argument's effects. |
| Static versus owned | A type or resource description conveys no live memory permission, CHERI capability or protocol token. |
| Definition versus generated program | The generator's evaluation is distinct from executing the program it constructs. Quoted or constructed target operations are not performed by inspecting their syntax. |

Kernel conversion executes only admitted total pure definitions, retaining CIC's
universe and equality rules. Introspection queries obtain explicit metadata from
the frontend; they add no reflective primitive to kernel conversion. General
proof search and untrusted procedural generation may run with bounded failure
outside conversion and propose terms for ordinary checking. A timeout supplies no
equality, inequality or proof; an unfinished result cannot enter an accepted build.

Static computation uses declared mathematical or target-specific integer
semantics. Target widths, endianness, layouts, capability formats and ABI come from
the selected target description, never the build host's pointer width or memory
layout. Static constants used at runtime require checked finite representations.
Unbounded mathematical values do not acquire a runtime encoding by specialization.

## Typed introspection and derivation

Provide typed descriptions of the supported type and declaration forms, with
qualified identities, universe levels, parameters, constructor/field structure
and the relevant public contracts, grades, effects and capture requirements.
Each descriptor binds the exact declaration and interpretation it describes.
Descriptors are data for ordinary computation; a generic type parameter alone
grants no structural inspection or assumption that every type has a finite schema.
Obtain a descriptor through explicit compiler reification or an opt-in schema
dictionary, checked against that declaration. This is not a CIC function that
eliminates arbitrary `Type` into syntax, decides function equality or reflects
universes by adding an axiom.

Introspection obeys module boundaries. A defining module can derive over its own
representation and export the resulting abstract API and laws. A client sees only
the published description or an explicit derivation interface; opting into a
derivation does not export otherwise private fields. Opaque types remain opaque.
Describing a nominal type cannot reconstruct another type with its identity, prove
arbitrary type equality, or introduce a representation-changing cast.

Derivations use coherent qualified library implementations and explicit format or
policy descriptions. Adding an unrelated import must not change the selected
implementation. Equality, visitors, optics, codecs and finite registries expose
their generated definitions and requested laws through the normal module system.
Declaring a derivation does not make its laws definitionally true or established.
Mandatory safety judgments and the selected
[assurance policy](assurance-profiles.md#claim-status-and-what-each-status-licenses)
apply exactly as they do to handwritten code. Every generated exported contract
must be discharged before its interface is accepted. Exploratory unproved claims
stay in the separate non-exported scratch channel; they cannot justify
optimization, a caller's proof or an accepted `requires`/`ensures` declaration.

The following is a library API sketch inside a generation context. The names and
context are illustrative, unimplemented interfaces, not additions to the current
grammar or executable examples. Its generic call uses the selected
[familiar authoring syntax](surface-grammar.md#familiar-authoring-migration):

```text
let schema = Meta.SchemaOf<Packet<Capacity>>();
let codec = Meta.DeriveCodec(schema, wireFormat);
let specialized = Meta.Specialize(copyDefinition, Capacity);
```

Here `Capacity` and `wireFormat` are declared static inputs. A packet's discovered
length remains represented in the generated program. The format description fixes
the encoding independently of record layout. The codec must establish its requested
bounds, failure and correspondence laws, and specialization must establish its
preservation obligations. This sketch authorizes no alternate production parser:
the [required Narcissus lowering](../../spec.md#r-05-043) and
[independent descriptor review](../../spec.md#r-05-046) retain their subjects and
amendment conditions.

## Hygienic construction and composition

Provide scoped typed construction of expressions, declarations and proof terms.
Typed quotation/splicing may be an ergonomic frontend to these builders after its
syntax and laws qualify; textual substitution is insufficient. Each open fragment
records its binder telescope, expected type, stage, representation, effects,
transitive captures and resource entry/exit obligations. Substitution preserves
binding, dependency, universes and those obligations. Generated names are fresh
and deterministic; intentional references use resolved qualified identities.

Open code may describe an operation requiring a linear input at execution. It
does not possess that input while being generated. Duplicating syntax is valid
only when checking the resulting program establishes the actual use, capture and
resource account. A generator cannot embed a build-process pointer, live owner,
loan, continuation or target capability as a runtime constant. Closed constants
cross stages only through admitted representations and provenance checks.

| Interaction | Required preservation |
| --- | --- |
| Dependent types and universes | Construction/substitution preserves ordered telescopes, motives, universe constraints and explicit transports. No arbitrary solver result extends conversion. |
| Grades and erasure | Generated demand uses the selected lawful domain and its interpretation. Runtime indices/discriminants remain represented; proof erasure creates no disposal or zeroization operation. |
| Ownership and loans | Every generated use and transitive capture respects exclusive permission, lifetime, restoration and mandatory outcomes on every exit. Duplication of a descriptor grants no duplication of its referent. |
| Effects and evaluation | Preserve explicitly sequenced call-by-value evaluation. A zero-use parameter does not skip an effectful argument, and repeated use does not repeat its once-performed evaluation. |
| Handlers and async | Preserve handler delimiters, resumption allowances, checkpoint/commit placement, invariant closure, terminal collection and cleanup. Moving or cloning work across those boundaries needs the corresponding preservation laws. |
| Mutation and dependency | Depend on stable snapshots with justified validity. A generated accessor or cached fact cannot retain a claim about current mutable state after its validity ends. |
| Security and resources | Preserve requested relational observations, cost and storage bounds as well as functional results; specialization is not permission to declassify or drop failure paths. |
| Machine and hardware authorship | Generated state, schedules and RTL retain their admitted architectural/cycle interpretations, finite representations and independent refinement subjects. Shared generation supplies no hardware theorem. |

Qualification must state these obligations over the admitted interpretation chosen
under the [frontend disposition](full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows).
The selected extension must prove its laws about the checked elaboration image
in that existing anchor and supply the required source correspondence; neither
the interpretation commitment nor a register clarification supplies those proofs. The
[composition review](full-language-review.md#the-representation-the-composed-duties-are-stated-over)
still owns missing concrete CHERI laws. An intrinsically typed builder or a valid
CIC output term supplies neither those laws nor checked source correspondence.

## Reproducibility, evidence and diagnostics

A generation request seals its source closure, generator and library definitions,
descriptors, selected instances, static arguments, target/ABI, options, declared
external input bytes and relevant tool identities. No ambient filesystem, network,
clock, randomness, environment lookup or runtime service execution is available
inside static evaluation. Import external data through explicit build inputs
before generation. Bound source/input sizes, evaluation steps, recursion, memory,
generated declarations and output bytes; exhaustion fails with the bounded cause.
Publishing is atomic only after complete checking of the selected output boundary.

A separately scoped procedural producer may use bounded local scratch storage
when its accepted result is deterministic over the sealed inputs. Such storage
supplies no target authority and cannot cross stages as a pointer or host-dependent
representation. That producer's operational implementation stays outside kernel
conversion; effectful target code remains constructed data during generation.

Record resolved dependencies and the generated terms, representation decisions,
proof obligations and source maps in the
[source evidence package](verification-strategy.md#mechanically-produced-evidence).
Cache identities bind that complete closure; changed private layouts invalidate
their derivations even when an exported name is unchanged. Cyclic generation,
unresolved instances and recursive specialization without a justified finite
closure remain unresolved/refused. Record input and output confidentiality where
static specialization exposes information in artifacts or diagnostics.

Generated APIs remain navigable to both the invocation and the generator/library
definition. Diagnostics identify the original invocation, expansion path, static
arguments and first failed typing/resource/proof premise; retain the complete
generated subject for inspection. Stale editor previews cannot become current
build evidence. A generator shared with an oracle creates common-mode risk;
independently reviewed intent, telling negative examples and the independent
canonical machine subject retain their existing roles.

## Runtime cost

The intended zero-cost property means compile-time evaluator, introspection and
construction machinery have no required runtime representation or dispatch.
Erasure and specialization must establish this for the emitted artifact. Explicitly
requested runtime schemas, registries or dictionaries are ordinary represented
data with declared size, authority and execution costs. They do not silently appear
as a fallback when static resolution fails.

Generated algorithms still execute, use storage and can be inefficient. Compare
equivalent generated and independently authored baselines on the same target:
final code size, stack, allocation, memory traffic and execution/WCET where claimed.
Report compilation, generation and proof-replay costs separately. Bound code-size
growth and use checked sharing or specialization policies; unrolling everything
is not a performance guarantee. Final-byte correspondence, constant-time and
resource evidence remain the [compiler's duties](unified-source-contract.md#native-verified-compiler-and-self-hosting).

## Compiler services and runtime information

Compile-time derivation covers many finite serialization, dispatch and registry
uses of runtime reflection. Data or schemas first discovered during execution
need explicit runtime descriptors, a confined interpreter or a later build; no
compile-time construct makes unknown information available earlier. The
[native admission rules](../../spec.md#r-02-008) still govern executable updates.

Compiler services expose located syntax, resolved symbols, types, elaboration,
dependencies, generated definitions and diagnostics to analyzers and tools. They
complement static generation: refactoring and navigation also operate on partial
source and whole workspaces. Reuse the same frontend services for the
[inspection and interoperability interfaces](tooling-protocols.md#compiler-inspection-api),
with versioned concrete, resolved/typed, elaborated, analysis/proof and lowering
views, bounded queries/exports and source/image identities. That contract owns
public schemas, snapshot-scoped handles, partial-result status and consumer
qualification. LSP, SARIF and SCIP consume projections of the same facts;
compiler remarks and traces consume their actual pass/phase producers.
Introspection grants no editor
workspace access, runtime debug permission or additional proof acceptance path.

## Design references

These references guide the intended interfaces. Each mechanism still needs Vela's
own interpretation, source correspondence and composition evidence; no source or
dependency is incorporated, feature parity claimed or implementation commissioned.

| Reference | Design use |
| --- | --- |
| Zig 0.15.2 [compile-time evaluation](https://ziglang.org/documentation/0.15.2/#comptime) and [type reflection](https://ziglang.org/documentation/0.15.2/#typeInfo) | Ordinary functions at compile time and the `@typeInfo`/`@Type` metadata/reification interface inform static computation and explicit descriptors. Their availability establishes no CIC or ownership theorem. |
| Idris 2 [elaborator reflection](https://idris-lang.org/Idris2/base/docs/Language.Reflection.html) | Checking, quotation, declaration and fresh-name operations inform scoped generation and discoverable library APIs. Vela retains its own dependent, graded and resource-aware construction obligations. |
| Roslyn [compiler API model](https://learn.microsoft.com/en-us/dotnet/csharp/roslyn-sdk/compiler-api-model) | Syntax, symbols, semantic analysis, diagnostics and workspace services inform the shared tool interface. These services complement compile-time generation. |

## Qualification

The [delivery plan](../../../PLAN.md#vela-first-release-delivery) qualifies static
computation with the initial software clients. Select later descriptor,
construction or cross-feature rows only when a named consumer needs them; a
synchronous derivation does not owe handler/async or hardware generation before
it can be useful. General generation, compiler-service schema breadth and
extensible graded interaction retain separately scoped budgets and stop decisions.

Qualify each advertised fragment with inhabited clients and independent, well-formed
negative neighbors using the same supported mechanisms. A parse failure or missing
feature supplies no semantic rejection. Retain exact source, tools, target, generated
subjects and verdicts; documentation examples alone supply no executed evidence.

| Client | Required positive result and telling negative neighbor |
| --- | --- |
| Static computation and types | Compute a type family, table and finite specialization with declared target semantics; refuse a runtime-dependent layout, host-width substitution and over-budget computation without runtime fallback. |
| Indexed tagged-union codec | Derive over a bounded payload with represented runtime length, independently chosen wire bytes, failure cases and round-trip/canonicality obligations; detect an incorrect field order, missing length check and mutually agreeing but incorrect encoder/decoder. Preserve the required parser route. |
| Stages, grades and erasure | Retain a static table while erasing its proof; keep a discovered length represented. Refuse using `ghost`, zero demand or an idempotent grade to conjure a static operand, skip effects or duplicate authority. |
| Binding and abstraction | Generate nested dependent binders with qualified instances and an abstract module's permitted derivation; reject captured/escaping binders, private-field inspection, forged nominal identity and ambiguous selection. An unrelated import preserves the selected meaning. |
| Ownership and control | Generate bounded code with one owner, checked callback demand and cleanup across a handler/async path; reject duplicated captures, a lost mandatory verdict, repeated effectful evaluation and moved checkpoints/commits. |
| Freshness and tooling | Replay after a harmless local rename, then invalidate changed generator, private layout, format, instance, input and target dependencies; reject late editor results, stale output and forged source maps. |
| Artifact costs and runtime metadata | Show the evaluator/descriptors absent when not requested and account for explicitly retained metadata; detect hidden boxing, runtime derivation fallback, unjustified code growth and changed final bytes reusing old evidence. |
| Proof and machine boundary | Replay generated exported laws under every preset with exact assumptions and independent intended behavior; refuse unestablished exported clauses, scratch claims consumed as facts, unchecked holes, extra axioms and a disconnected source/output claim. A selected hardware extension retains independent architecture/refinement checks. |

| Existing owner | Work retained at that boundary |
| --- | --- |
| `core-soundness` | Phase separation, descriptor interpretation, hygienic substitution, dependent/graded resource composition and erasure laws. |
| `core-frontend` | Introspection and construction interfaces, required-static checking, coherent resolution, bounded generation and checked source/output correspondence. |
| `core-diagnostics` | Expansion provenance, inspectable output, semantic invalidation and the positive/negative client corpus. |
| Compiler/representation and whole-system stages | Static target semantics, finite specialization, growth bounds, exact artifact costs and final-byte/hardware preservation. |
| Editor/debug protocol stages | Versioned compiler-service consumption, generated-source navigation and exact-image mappings under the existing interoperability contract. |

These rows partition duties, not estimates or implementation commissions. The
[plan](../../../PLAN.md#vela-whole-system-authoring-proposal) and
[reviewed pricing](full-language-review.md#reviewed-implementation-pricing) own
scope, budgets and holds. Land the selected syntax/semantic contract and priced
acceptance item before implementation. Complete the repository's
[validation handoff](../../../AGENTS.md#tool-execution-and-validation) for settled
changes; hosted acceptance and generated-term checking establish only their stated
boundaries, never automatic equivalence with another language's entire feature set.
