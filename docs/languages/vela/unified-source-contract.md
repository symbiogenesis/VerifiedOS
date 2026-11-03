# Vela Whole-System Authoring Contract

> Non-normative replacement criteria extending the [primary Vela design and examples](verification-strategy.md).
> [PLAN.md](../../../PLAN.md#vela-whole-system-authoring-proposal) owns proposal stages;
> the [requirements register](../../requirements-register.md) governs admission until
> explicit amendments accept replacements. This contract supplies no implementation
> or agreement theorem.

## Authoring end state

Vela is intended to author software, contracts, proofs, machine semantics and
hardware. Qualified replacements may retire maintained Gallina, Sail, C and VST
sources. Generated Rocq terms, Clight, machine code and RTL remain valid products;
proved libraries may remain dependencies behind Vela interfaces. Rewriting a
library's syntax earns no qualification credit.

Declare the source closure: firmware, kernel, storage, services, bootstrap and
ISA/ABI primitives, plus compiler, proof automation and generators when claiming
toolchain authorship. Remaining first-party handwritten C, Gallina, VST or Sail
must stay visible. Generated instruction/assembly stubs are permitted, with
primitive meaning from the admitted machine and required source/binary evidence;
inline assembly and foreign stubs grant no semantic exception. Retained libraries
and imported RTL need explicit dependency boundaries and qualification records.

Each accepted component has one maintained operational definition, reviewed
contract, representation and proofs. Its software reference and production
executable derive from that definition with exact-final-image correspondence;
manual optimized rewrites and generated-output repairs are excluded. Authored
algorithm/layout choices need refinement evidence. Arbitrary Gallina computations
are not presumed efficiently lowerable.

The language has distinct interpretations for total pure definitions/proofs,
effectful explicit-storage software, architectural transitions and cycle-level
hardware. Module interfaces state phase/target restrictions. Unbounded mathematics
needs proved finite runtime representations; ghost data supplies no runtime branch,
allocation, encoding or circuit state.

The [metaprogramming contract](metaprogramming.md) adds explicit static computation,
opt-in structural descriptions and hygienic checked generation within those
interpretations. Generated definitions, proof terms, specialization inputs and
descriptor dictionaries belong to the declared source/dependency closure.
Generator removal and final-code cost have separate acceptance predicates;
static generation supplies no software, machine or hardware refinement theorem.
Compiler services expose the same source identities and elaborated meanings to
tools without adding an admission path or runtime evaluator.

Contracts retain independent review and telling rejected behaviors. Architecture
and processor implementation remain distinct theorem subjects even when sharing
arithmetic/decoding definitions; an implementation cannot define its own correctness.

## Software and proof boundary

Initially elaborate into admitted interpretations, reconstruct evidence in
Rocq/CIC and lower supported explicit-memory code through the selected compiler;
generated Clight is permitted. Replacing the required verified-C or Rust producer
needs duty-by-duty register/prose amendments under the
[compiler replacement contract](compiler-route-contract.md#conditional-amendment-and-reviewer-requirements).
Language unification and source-neutral admission alone retire neither.

The following evidence is needed before handwritten C and component VST scripts
can retire:

- Checked correspondence from the authored source closure through parsing,
  resolution, implicit insertion, elaboration and erasure to the interpreted
  program and contract. A valid proof about another program is insufficient.
- Concrete representation and ownership laws for layout, initialization, CHERI
  tags, bounds, provenance, permissions, frame preservation and every supported
  exit, including failure, cancellation and device quiescence where applicable.
- Composed lowering, optimization, ABI, assembly, linking and image evidence for
  the final bytes. Hidden allocation or runtime support must meet the same
  declared resource and admission obligations as explicit code.
- Separate statements and proofs for functional behavior, termination or reactive
  progress, adversarial-context isolation, permitted leakage and resource bounds
  wherever the component's accepted claim includes them.

The [foundation map](../../hardware/cheri-foundation-map.md#required-connections)
owns missing concrete laws; generic separation logic or surface syntax supplies
no CHERI instance. VST may remain internal. Its replacement needs sound rules and
connections to the admitted machine logic, preserving every discharged obligation.

Full proof authoring needs inductive/coinductive reasoning where used, universes,
quantified mathematics, logical relations and compiler/hardware metatheory. Retain
Rocq fallbacks until actual clients express and replay in Vela. Reconstruction and
dependency/assumption audits remain kernel checked. Solvers/AI may propose code,
invariants, lemmas or optimizations; they confer no acceptance authority, and AI
availability is no theorem premise.

Rocq/CIC may remain the checker after handwritten Rocq retires; replacing its
implementation is a separate qualification decision. The
[frontend disposition](full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows)
governs the calculus's interpretation commitment and admission.

## Native verified compiler and self-hosting

The long-term goal is a verified, self-hosting Vela-authored compiler using
Vela-owned IRs to emit target code without mandatory Clight/CompCert or LLVM.
Interim backends and retained-producer interoperation remain available during
qualification/migration. This goal commissions no implementation or changed duty.

Development uses the [Menhir route](verification-strategy.md#development-parser-and-grammar)
with a reviewed grammar and located AST, preserving separate lexer, parsing,
elaboration and source-correspondence duties. The eventual Vela compiler includes
its parser; verified bootstrap accounts for Menhir development/seed dependencies
until retirement preserves accepted grammar and source meaning.

The toolchain also supplies [LSP, DAP and DWARF interoperability](tooling-protocols.md).
Editor services consume the compiler's located and resolved source state and
preserve batch-only proof acceptance. Native compilation carries source, type,
scope, variable-location and unwind mappings through optimization and final
image construction into separately stored DWARF information. DAP consumes a
matching debug artifact and a qualified execution backend, preserving lifecycle
authorization and CHERI authority. These interfaces have separate plan owners;
compiler correctness and self-hosting alone do not qualify them.

### Optimization stages and evidence

Native compilation stages optimization across intermediate representations;
direct emission removes the mandatory C stage, not the intermediate languages.
Keep structured control flow and established type, alias, effect and contract
facts available for specialization, inlining and justified check elimination.
Selected loop, layout and vector transformations need concrete memory and target
information; instruction selection, allocation, scheduling and local rewrites
use the appropriate target representations. The scoped compiler package selects
and qualifies its IRs and pass families.

Runtime erasure may remove proof values while retaining checked compiler facts.
Each later transformation must transport or re-establish the premises it uses
in its current IR; an earlier source annotation alone supplies no such premise.
An interim C/Clight backend may consume already optimized output, with checked
representation transport and backend evidence through to the final artifact.
Bypassing C alone establishes no optimization benefit.

Each IR has a reviewed interpretation and retains or discharges later passes'
ownership, CHERI authority, layout, initialization, effect, protocol, leakage and
resource premises. Compiler/hardware proofs resolve the generation's canonical
machine, Sail or its qualified successor; native compilation adds no private ISA.

Compose reusable correctness theorems for elaboration, erasure, representation,
optimization, instruction selection, allocation, calling conventions, assembly,
linking and image construction, carrying source evidence to exact bytes without
reproving each transform from its output. Functional refinement, termination/progress,
authority, robust isolation, relational leakage and resource bounds remain distinct
where claimed; functional optimization correctness supplies neither CT nor cost.

Independently kernel-check evidence, audit dependencies/assumptions and bind source
and final image. Pass-theorem reuse needs the checked revision, premises and actual
application. R-05-023a decompilation/final validation remains required until a
register/prose amendment admits composed substitutes; compiler assertions cannot
certify output.

AI/search/scheduling heuristics may propose transforms, but a proved checker or
reconstructed proof establishes their premises and required preservation. Missing
support/certificates or failed checks admit no optimized artifact; any fallback
independently meets the same contract. Search implementations remain untrusted.

### Bootstrap and qualification

Verified self-hosting connects executable compiler bytes to the proved definition.
Record the seed compiler, interpreter or proof-grounded evaluation route, exact
sources/tools, target/ABI, bootstrap stages, assumptions and final compiler image.
The compiler must compile its declared Vela closure into a successor with checked
compiler correspondence; reproducible stages are an additional check. Resident
compiler/helpers meet storage, runtime and admission rules. Declare initial
checker/bootstrap trust boundaries; self-compilation alone proves no soundness.

Qualify competitive optimization separately on representative systems/compute
clients, including held-out ones, at identical semantics, security, target and
resources. Measure final code size, stack, allocation, traffic, target cost,
compile/proof cost and maintenance. Aim to match/improve qualified routes where
their optimizations are admissible. Native/self-hosting compilation implies no
LLVM-wide parity or universal superiority; scope and price optimization machinery
and proofs before implementation.

Qualify commercial use, distribution and resident rebuilding for the complete
source/proof/helper/runtime closure. Independent infrastructure may use project
terms; adapted passes retain their terms. CompCert/LLVM independence and removal
of non-commercial dependencies require closure audit and consumer retirement under
the [compiler replacement duties](compiler-route-contract.md#conditional-amendment-and-reviewer-requirements).

## Machine model

The machine subset aims to replace Sail authoring and required consumers, beyond
permanent Sail generation. Its independently reviewed architecture elaborates
into the accepted kernel theory upstream of compiler/hardware validation. A compiler
cannot derive its target semantics from its output or the checked implementation.

Its scope covers the frozen profile's architectural state and all operations
reachable in a shipped composition: finite-width integer and floating-point
behavior, instruction encoding/decoding, register and memory effects, traps,
misalignment and invalid instructions, CHERI metadata and authority, atomics and
memory ordering, device interactions, interrupts, reset and boot behavior. Its
trace interface also carries the applicable timing, cost and leakage observations.
Unsupported operations and configurations require explicit refusal or a separately
reviewed scope decision; silently omitting a difficult operation is no replacement.

Supply one admitted machine closure, parameterized by actual platform variation,
with explicit configuration, core class and hart identities. Every consumer resolves
that closure and declared instances, without private transcriptions. Resolve the
[canonical term's open configuration question](../../assurance/canonical-machine-term.md#2-generation-identity)
before migration: a term fixed to one hart cannot stand for all compositions.

Prove full-selected-scope agreement with pinned Sail-generated definitions, with
explicit state/observation maps and behavior preservation both ways: failures,
nondeterminism and required termination/progress. One-way behavior loss/addition
fails. Stuttering simulation must preserve progress/observations; functional-output
agreement cannot erase timing/leakage. Review architectural changes separately
from semantics-preserving migration.

Separately transport relational security, preserving public/secret entries,
admissible contexts, independent executions and permitted observations. Coupling
choices to hide leakage is invalid. Cost bounds and hardware refinement also need
checked transport at their claimed scope. Immediate stopping fails required progress.

Reference-emulator compilation needs correspondence evidence and a recorded
host-runtime boundary. Differential/litmus/mutation samples establish no model
equivalence. Resolve unavailable Sail definitions/external operations or explicitly
review them as premises; neither side may hide missing semantics.

## Hardware

A hardware subset may author state, registers, concurrent rules and cycles/schedules.
Its semantics/compiler need checked connections to the admitted hardware interpretation
and exact synthesis input. Initial Kami/Kôika elaboration or RTL generation is
permitted; generation alone meets neither connection. The
[RTL boundary](../../assurance/rtl-correspondence-boundary.md) distinguishes source
circuit theorems from synthesized artifacts.

Simulator/RTL may share hardware definitions, and architecture/hardware may share
pure helpers. Processor refinement still connects cycles to architecture through
explicit state maps, commits, progress and applicable timing/leakage. Shared
generation supplies neither that theorem nor independent executor checks. Imported
cores retain their qualification path until replacement covers the actual artifact.

Physical implementation, fabrication and device measurement remain separate, with
claims bounded by their artifacts' evidence/theorem tier. Structural-absence and
netlist audits keep independent artifact checks; circuit theorems imply no physical absence.

## Migration and retirement

The [proposal ownership](../../../PLAN.md#vela-whole-system-authoring-proposal)
orders the work. Its technical transition criteria are:

1. Establish the software/proof route over the existing machine term. Qualify
   representative systems and mathematical clients, including a held-out client,
   before claiming the general authoring endpoint. Keep required current routes
   available until each consumer has an accepted replacement.
2. Construct and kernel-check the candidate machine definition and its full-scope
   agreement evidence under a reviewed comparison scope. During comparison, the
   pinned Sail term remains the authoritative subject of current claims; parallel
   candidate artifacts confer no replacement credit by themselves.
3. Rebind and recheck every affected consumer: compiler/primitive meanings, binary
   refinement and admission, TAL soundness, the machine logic and its relational
   and cost theories, emulator/oracle and generated tooling, and hardware evidence
   and refinement. The migration inventory is generated from actual dependencies,
   checked for completeness, and records each consumer's revision and verdict.
4. Promote the replacement and retire Sail only when all required destination
   artifacts are admitted, all consumers use the replacement closure, and no
   accepted claim still depends on an unqualified route. Rebuild and revalidate
   affected images and evidence for the promoted semantics; preserve old model
   identities for retained historical results. Remove active dual maintenance and
   update provenance, gates and the trust-base inventory in the same transition.

The amendment dossier follows [the register amendment process](../../spec.md#r-18-034).
It reviews the anchor identity and provenance rules R-05-019 through R-05-019c,
R-05-020's replacement conditions, and all affected source-correspondence,
primitive, binary-validation and hardware obligations. In particular it accounts
for R-05-023/R-05-023a/R-05-023b/R-05-026, R-13-017 and the R-15-090 through
R-15-092 hardware routes; this is an impact starting point, not an exhaustive
consumer inventory. It amends the register and its paired specification prose,
updates derived coverage and resolves co-reads before relying on the new route.

Sail, VST and Kami/Kôika remain required until substitute evidence and explicit
amendments authorize retirement. Vela receives no exception or weakened guarantee;
current admission gates remain unchanged.

## Qualification cases

Use independently reviewed expected behavior and inhabited premises. These
well-formed changes must fail at their intended obligations:

| Candidate change | Evidence that must fail |
| --- | --- |
| An elaborator resolves a source operation or contract to the wrong definition | Authored-source correspondence, even if the resulting kernel term checks |
| Erasure removes a runtime discriminant or lowering changes failure cleanup | Phase, operational or all-exits refinement |
| A spill loses a capability tag, or bounds/provenance/permissions change | Concrete representation, machine execution or binary admission relation |
| A widened or vectorized load crosses the readable or initialized extent while preserving returned values on nontrapping inputs | Concrete access, initialization and trap preservation, including admitted inputs on which the widened access newly faults |
| An optimizer preserves outputs but changes a required leakage observation or resource bound | The composed security or resource obligation for that transformation |
| An optimization certificate names another pass revision, source or output image | Transformation-premise checking and source/final-image binding |
| A self-compiled binary reproduces stage output but lacks a connection to the proved compiler definition | Verified-bootstrap acceptance; reproducibility alone earns no compiler-correctness claim |
| A decoder changes an exceptional result, admits an excluded encoding or drops a device event | Full-scope model agreement and the affected consumer theorem |
| A comparison omits one core configuration or changes allowed concurrent traces | Configuration coverage or behavioral agreement |
| Functional values agree but a secret changes branches, addresses or permitted latency | Relational leakage or cost/timing agreement |
| A processor or generated RTL retains correct outputs while violating its commit/progress relation | Hardware refinement or synthesis-input correspondence |
| A model change leaves an old binary or hardware certificate marked current | Dependency invalidation and exact-revision evidence binding |

Separate malformed, noncompiling and unsupported variants from semantic rejections.
A required survivor blocks replacement. Independent contracts, distinguishing
inputs and alternative paths address shared-definition errors; generated-artifact
agreement alone is insufficient.
