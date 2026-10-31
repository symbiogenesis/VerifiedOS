# Vela Whole-System Authoring Contract

> Non-normative extension of the [language strategy](verification-strategy.md).
> This contract specifies the proposed endpoint and the evidence needed to replace
> existing authoring routes, including Sail. It implements no language, proves no
> agreement theorem and amends no requirement. The [proposal ownership](../../PLAN.md#vela-whole-system-authoring-proposal)
> stays in PLAN.md; the [requirements register](../requirements-register.md)
> governs every admitted artifact until a replacement amendment lands.

## Authoring end state

Vela is intended to author the project's software, behavioral contracts, proofs,
machine semantics and hardware designs. Repository-owned Gallina, Sail, C and
VST scripts can retire as maintained sources when their replacements meet this
contract. Generated Rocq terms, Clight, machine code and RTL remain acceptable
build products. Existing proved libraries can remain dependencies behind Vela
interfaces; reproducing their source in new syntax is no qualification result.

The whole-system source closure includes firmware, the kernel, storage and system
services, their bootstrap code, and low-level ISA/ABI primitives. Generated
instruction and assembly stubs are acceptable; a primitive takes its meaning from
the admitted machine definition and carries the required source and binary
evidence. Inline assembly or a foreign stub supplies no semantic escape hatch.
Retained upstream libraries and imported RTL have explicit dependency boundaries
and qualification records. A complete authoring claim identifies its source
closure and cannot conceal remaining first-party handwritten C, Gallina, VST or
Sail inside it. Claims covering the toolchain's own authorship also include its
compiler, proof automation and generators in that closure.

An accepted component has one maintained operational definition, its reviewed
contract, representation information and proofs. The production executable and
software reference are outputs of that definition, with correspondence to the
exact final image. No manual optimized rewrite or repair of generated output
belongs between that source and promotion. Explicit algorithm or layout choices
may be authored in Vela and must carry their refinement evidence; arbitrary
Gallina computations are not presumed efficiently lowerable.

One language supports distinct interpretations: total pure definitions and proofs,
effectful software with explicit storage, architectural transition systems, and
cycle-level hardware. Phase and target restrictions are part of each module's
interface. A specification may use unbounded mathematical values while its runtime
representation needs proved finite bounds. Ghost data supplies no runtime branch,
allocation, instruction encoding or circuit state.

Contracts retain independent review and telling rejected behaviors. Sharing a
language does not make an implementation its own correctness criterion. The
architectural model and a processor implementation remain distinct theorem
subjects even where their arithmetic or decoding definitions are shared.

## Software and proof boundary

The initial software route elaborates Vela into existing admitted interpretations,
reconstructs its evidence in Rocq/CIC, and lowers supported explicit-memory code
through the selected compiler. Clight is an acceptable generated intermediate.
The [compiler-route contract](compiler-route-contract.md#conditional-amendment-and-reviewer-requirements)
owns a changed backend's replacement duties. Language unification alone retires
neither the verified-C producer nor the separately required Rust producer.
Displacing either needs a duty-by-duty register and specification amendment;
source-language-neutral admission does not itself cancel a required producer.

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

The [CHERI foundation map](../hardware/cheri-foundation-map.md#required-connections)
owns the missing concrete laws; a surface feature or generic separation-logic
theorem supplies no CHERI instance by itself. VST may initially remain an internal
proof mechanism. Replacing it requires sound replacement rules and connections to
the admitted machine logic, rather than removal of the obligations it discharged.

Full Vela proof authoring additionally needs inductive and coinductive reasoning
where used, universes, quantified mathematics, logical relations and the
metatheory of the compiler and hardware paths. Existing Rocq fallbacks remain
until these actual clients can be expressed and replayed. Proof reconstruction
and dependency/assumption audits stay kernel checked; a solver or AI service may
propose code, invariants, lemmas or optimizations and supplies no acceptance
authority. AI availability is no premise of an accepted theorem.

Rocq/CIC can remain the checker for the completed authoring endpoint. Replacing
its implementation is a separate checker-qualification decision and is not
required to eliminate handwritten Rocq. The [frontend disposition](full-language-review.md#r-05-009-r-05-020-and-what-holds-the-frontend-rows)
still governs the existing calculus's interpretation commitment and admission.

## Machine model

Vela's machine-description subset is intended to replace Sail source and its
required consumers, rather than remain a frontend that permanently regenerates
Sail. The replacement is an independently reviewed architectural definition
elaborated into the accepted kernel theory. It is upstream of compiler and
hardware validation: no compiler derives its correctness target from its own
emitted instructions or from the implementation it is meant to check.

Its scope covers the frozen profile's architectural state and all operations
reachable in a shipped composition: finite-width integer and floating-point
behavior, instruction encoding/decoding, register and memory effects, traps,
misalignment and invalid instructions, CHERI metadata and authority, atomics and
memory ordering, device interactions, interrupts, reset and boot behavior. Its
trace interface also carries the applicable timing, cost and leakage observations.
Unsupported operations and configurations require explicit refusal or a separately
reviewed scope decision; silently omitting a difficult operation is no replacement.

The replacement supplies one admitted machine-definition closure, parameterized
where the platform actually varies, with explicit selected configuration, core
class and hart identities. All consumers resolve that same closure and their
declared instances. The [canonical-term record](../assurance/canonical-machine-term.md#2-generation-identity)
shows why a term fixed to one hart cannot silently stand for all compositions;
its open configuration question must receive a decision before migration relies
on it. Per-consumer transcriptions are prohibited.

Acceptance requires a checked relation to the pinned Sail-generated definitions
for the complete selected scope, with state and observation mappings stated
explicitly. The relation preserves the permitted behaviors in both directions,
including failures, nondeterminism and termination or progress; a one-way relation
that drops behaviors or admits extra ones is insufficient. A proved simulation
with stuttering must also establish the relevant progress and observation clauses.
Timing and leakage cannot disappear under an observation projection merely because
functional output values agree. An intended architectural change is reviewed as
such, outside the semantics-preserving migration claim.

Unary behavioral agreement alone does not transport the relational security
theories. Their transport preserves the public/secret entry relation, admissible
contexts, independently chosen executions and the permitted observation relation;
coupling two executions' choices to conceal a leak is invalid. Cost bounds and
hardware refinement likewise need their own checked transport at their claimed
scope. A model that immediately stops cannot satisfy the required progress clauses.

Compilation of the reference emulator from this definition needs its own
correspondence evidence and recorded host-runtime boundary. Differential tests,
litmus tests and mutation controls remain useful checks, but agreement over a
sample does not establish model equivalence. Unavailable Sail definitions or
assumed external operations must be resolved or carried as explicitly reviewed
premises; neither side of an agreement theorem may hide the missing semantics.

## Hardware

A Vela hardware subset may author state, registers, concurrent rules and explicit
cycle/schedule behavior. Its semantics and compiler need checked connections to
the admitted hardware interpretation and the exact synthesis input. Vela may
initially elaborate to Kami/Kôika or generate RTL; emitting RTL alone establishes
neither connection. The [RTL correspondence boundary](../assurance/rtl-correspondence-boundary.md)
owns the distinction between a source circuit theorem and the artifact synthesized.

Simulator and RTL generation may share a hardware definition, and architecture
and hardware may share pure helpers. The processor still needs a refinement
theorem from its cycle-level behavior to the architectural model, with explicit
state mapping, commit observations, progress and applicable timing/leakage claims.
Shared generation does not discharge that theorem or make two generated executors
independent checks. Imported cores retain their existing qualification path until
an accepted replacement covers the actual imported artifact.

Physical implementation, fabrication and measured-device obligations remain
outside what source-language unification can prove. Each claim retains the
evidence or theorem tier its admitted artifacts establish.
Structural absence and netlist audits retain their independent artifact-bound
checks; a generated circuit theorem does not imply the required physical absence.

## Migration and retirement

The [proposal ownership](../../PLAN.md#vela-whole-system-authoring-proposal)
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

The amendment dossier follows [the register amendment process](../spec.md#r-18-034).
It reviews the anchor identity and provenance rules R-05-019 through R-05-019c,
R-05-020's replacement conditions, and all affected source-correspondence,
primitive, binary-validation and hardware obligations. In particular it accounts
for R-05-023/R-05-023a/R-05-023b/R-05-026, R-13-017 and the R-15-090 through
R-15-092 hardware routes; this is an impact starting point, not an exhaustive
consumer inventory. It amends the register and its paired specification prose,
updates derived coverage and resolves co-reads before relying on the new route.

Current names such as Sail, VST and Kami/Kôika identify the required incumbents;
they do not make equivalent replacements an impossible long-term design goal.
Retirement requires the above substitute evidence and explicit amendments, rather
than a permanent exception for Vela or deletion of a required guarantee. This
contract changes none of the current admission gates.

## Qualification cases

Qualification exercises supported mechanisms with independently reviewed expected
behavior and inhabited premises. The candidate must reject the following
well-formed changes at their intended obligations:

| Candidate change | Evidence that must fail |
| --- | --- |
| An elaborator resolves a source operation or contract to the wrong definition | Authored-source correspondence, even if the resulting kernel term checks |
| Erasure removes a runtime discriminant or lowering changes failure cleanup | Phase, operational or all-exits refinement |
| A spill loses a capability tag, or bounds/provenance/permissions change | Concrete representation, machine execution or binary admission relation |
| A decoder changes an exceptional result, admits an excluded encoding or drops a device event | Full-scope model agreement and the affected consumer theorem |
| A comparison omits one core configuration or changes allowed concurrent traces | Configuration coverage or behavioral agreement |
| Functional values agree but a secret changes branches, addresses or permitted latency | Relational leakage or cost/timing agreement |
| A processor or generated RTL retains correct outputs while violating its commit/progress relation | Hardware refinement or synthesis-input correspondence |
| A model change leaves an old binary or hardware certificate marked current | Dependency invalidation and exact-revision evidence binding |

Malformed, noncompiling or unsupported variants are reported separately and supply
no successful rejection evidence for a semantic obligation. A surviving required
negative prevents the corresponding replacement claim. Independently reviewed
contracts, distinguishing inputs and alternative execution paths address common
errors in shared definitions; agreement of generated artifacts alone is insufficient.
