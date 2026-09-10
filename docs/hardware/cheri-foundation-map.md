# CHERI component foundation map

This is Q2c's prerequisite inspection for parser destination initialization and
copy-service private staging. It supplies the existing-route input to Q21b's
[compiler comparison](../languages/compiler-route-contract.md) and identifies what Q19c would
need to instantiate a generic bounded operation. The inspection baseline is
repository revision `4aeaceedf4626ef64583a4680c19da29a469df4f`.

The map records source subjects and existing measurement records. It does not
report a fresh prover run, a byte-memory implementation or an accepted target
connection. Q2c takes its reasoned-rejection arm: commissioning the missing
foundation for the bounded generic experiment is declined on the evidence below.
The existing realization route and mandatory hardening obligations retain their
owners. Q19c remains unopened; this decision supplies no checked primitive law.

## Available artifacts

| Artifact and actual constant | Subject available at the inspection baseline | Limit at the consumer boundary |
| --- | --- | --- |
| [DescriptorCheck.v](../../tools/bedrock2-lowering/DescriptorCheck.v), `Descriptor.descriptor_check`, `Descriptor.spec_of_descriptor_check`, `Descriptor.descriptor_check_br2fn_ok` | A read-only descriptor check over `BasicC64Semantics`, a `listarray_value AccessByte` footprint and a separating frame. The specification preserves the trace and footprint and returns the functional check's result; the derivation ends in `Qed`. | Its pointer is a Bedrock2 word, its memory is byte memory, and its source never copies a descriptor. Neither a tagged capability representation nor destination initialization follows from that statement. |
| [Q2a's recorded experiment](../../tools/bedrock2-lowering/README.md#build-and-run) | A recorded closed-context derivation, reproducible C emission and measurements at the revisions the report names. | This inspection does not refresh that evidence. The C printer is outside the checked relation; the report's older backend measurement does not describe every subsequent compiler revision. |
| [CopyRingService.v](../../proofs/CopyRingService.v), `copy_once`, `the_copy_once_service_stays_inside_the_validated_extent`, `the_copy_once_service_reads_the_source_once`, `the_copy_once_service_does_not_vary_with_the_second_image`, `the_copy_once_service_refuses_an_overlong_length` | A model with `buffer` containing natural-valued length and datum, and `copy_run` recording reads, staged datum and bytes. The theorems express extent, single-read, second-image independence and refusal properties of that model. | No theorem here interprets the datum as a concrete byte array, executes a CHERI load/store or establishes a concurrent atomic snapshot. A model read count is not an instruction trace. |
| [CopyRingService.v](../../proofs/CopyRingService.v), `publish_keeps_the_invariant`, `take_keeps_the_invariant`, `the_invariant_survives_every_interleaving` | Preservation of the `ring_view` ordering and capacity invariant over the specified index transitions. | This is an index algebra. It supplies neither hardware publication ordering nor a byte-memory frame rule. |
| [MemoryPlan.v](../../proofs/MemoryPlan.v), `spec_narrow_ok`, `the_specification_narrowing_check_admits_only_exact_narrowings` | A narrowing predicate and theorem over the authored slot-plan arithmetic. | M1.2e connects the backend's emitted narrowing to the model's bounds behavior; this theorem alone is not that connection or a pointer-advance rule. |
| [cap_common.sail](../../model/model/core/cap_common.sail), `inCapBounds`, `setCapAddrChecked`, `setCapOffsetChecked`; [CHERI instructions](../../model/model/extensions/CHERI/cheri_insts.sail) | Operational source definitions in the curated ISA model. | These are semantic inputs, not Rocq primitive-law constants. R-05-019b requires Sail's own emitted definitions as the common theorem subject. |

Reproduce the source inspection with `git show <baseline>:<path>` and inspect each
named declaration through its complete statement and proof. Use
`git ls-files -s upstream` for the pinned artifact inventory. A gitlink proves what
is pinned, not that its theorem has been instantiated for this machine. The
[third-party record](../../THIRD-PARTY.md) and the
[strategy's capability-aware comparison](../languages/verification-strategy.md#capability-aware-and-parametric-verification)
keep upstream results and their semantic subjects separate from local connections.
No upstream code is incorporated by this map.

## Required connections

The following are required proof obligations, not assumed interface axioms. A
consumer may accept their names only after they resolve to checked constants over
the selected representation and semantic subject.

| Needed law or connection | Required statement and discriminating evidence | Current owner and readiness |
| --- | --- | --- |
| Canonical machine term and logic | Identify Sail's emitted Rocq term and its complete generation identity. Establish the R-13-017 logic over that exact term, including the connection needed by R-05-023a. A substitute deep embedding needs an agreement theorem and the applicable R-05-020 admission. | `machine-logic` below; Q2b consumes the connection. No checked local logic instance or translation-agreement constant is identified. |
| Buffer and pointer representation | Relate byte sequences, lengths, initialization and disjoint footprints to tagged capabilities, permissions, bounds, validity and permitted provenance. Distinguish capabilities stored in memory from ordinary byte contents. State live ownership and representation on every ordinary exit. | `byte-instance`; M1.2b/M1.2g retain compiler encoding and tagged value/memory carriers. Those compiler structures alone do not establish a component memory logic. |
| Read | A valid readable capability and an initialized in-bounds index return the represented byte, preserving the source and disjoint frame. Specify the exact modeled trace and invalid-access behavior. A same-type wrong-offset read must fail the required relation. | `byte-instance`; Q2b consumes the parser instance. The Bedrock2 footprint theorem is available only at its own subject; its CHERI instance is missing. |
| Write and initialization | A valid writable capability permits the specified byte update, preserves other bytes and the disjoint frame, and advances the initialization predicate precisely. Account for the model's tag effects on byte stores. Wrong-store and incomplete-fill variants must fail the intended postcondition. | `byte-instance`; Q2b owns the parser's fixed destination; M7.1 owns service private staging. No concrete byte implementation is identified for either copying client. |
| Bounded advance and narrowing | Address arithmetic stays representable without wrap, preserves the permitted provenance and permissions, and never silently enlarges authority. Distinguish a legal end pointer from a legal dereference. Cover empty spans, the last byte and overflowing length/offset combinations. | `byte-instance`; M1.2e retains backend narrowing and M1.2d its emission use. Slot-plan arithmetic is an input, not a proved load/store contract. |
| Frame and scoped restoration | Disjoint storage remains unchanged; scoped loans suspend the affected owner and return it with the correct contents and initialization state. Error exits return their declared resources. A false or missing restoration law must leave the requesting client unprovable. | `byte-instance` supplies memory framing; `scoped-resources` supplies its loan interpretation. Q19c factors checked laws only after its entry gate. Q21a's language design does not provide the concrete instance. |
| Source to imperative code and Clight | Connect the authoritative operation and representation to the generated imperative implementation and the Clight waypoint R-05-043 requires. Cover the selected preamble/foreign primitives and success, failure, footprint and trace behavior; printer output alone cannot witness this theorem. | `source-transport`, owned by Q2b for the existing route. The existing `Derive` reaches Bedrock2 only; any extension beyond Q2b's priced scope requires its own cell before implementation. |
| Compiler, ABI and final bytes | Connect capability-correct lowering and call/return/spill behavior through assembly, linking and image composition. Bind R-05-023a validation to exact bytes and the canonical Sail term. Keep R-18-014's verified-C and certifying-Rust duties and R-05-026's admission obligations. | M1 owns compiler realization; `artifact-admission` owns the remaining proof endpoint. Q2b and Q3b join component/artifact evidence. Functional bring-up and production proof are different acceptance endpoints. |
| Stronger contextual guarantees | State the guarantees the selected consumer actually requires and supply the corresponding logic, preservation and arbitrary-context results. Retaining operation laws while removing a required guarantee theorem must fail at that guarantee. | `context-preservation`; Q21b compares equivalent duties. A finite emission vocabulary or a sequential copy theorem waives none of the required obligations. |

### Foundation ownership ledger

These keys identify obligations and their owning deliverables, not Rocq constants
or commissioned checklist cells. The rejected experiment creates no implementation
budget. An unbounded entry is an unknown cost, never zero or a cost silently
absorbed by Q19c, Q20 or M1's functional-bring-up cells.

| Key and owning deliverable | Inputs and scope boundary | Evidence required before a dependent implementation opens | Cost disposition |
| --- | --- | --- | --- |
| `machine-logic`: the R-13-017 Iris-over-Sail hardening deliverable | Canonical Sail-emitted definitions under R-05-019b, leakage/cost interpretation and chosen reusable logic. The current R-13-016 route also owes the Katamaran/μSail translation-agreement theorem; replacing that route needs the applicable reviewed amendment. | Named checked logic and adequacy constants over the exact generation identity, declared assumptions and constructed entry states; a translated instruction cannot acquire a second meaning. | Full establishment is unbounded by the inspected clients and is not commissioned. Its hardening owner must supply a reviewed implementation breakdown before construction. |
| `byte-instance`: the concrete CHERI foundation deliverable consumed by Q2b/Q19c | `machine-logic`, the selected capability/value/memory representation and Sail read/store/address clauses. Owns byte representation, initialization, read, write, bounded advance and memory frame laws. | Checked constants with satisfiable tagged entry states; empty, boundary, partial-initialization and overflow cases; well-formed wrong-read/wrong-store failures and exact tag effects. | Conditional component scope is identified, but no numeric estimate is accepted before the logic and representation are selected. Q2c does not book a new foundation implementation. |
| `scoped-resources`: the concrete resource interpretation consumed by Q21a/Q19c | `byte-instance` and actual permission/loan interpretation. Owns disjoint-field split/join, shared/exclusive reborrow, suspended-parent access and restoration entailments. | Actual entailment constants, including refusal to restore a parent with a live child and preservation of the disjoint audit field. Branch joins and loop induction compose these laws at the language owner. | Missing concrete instance remains part of rejected foundation commissioning. Q21a's separately priced abstract rules do not pay for it. |
| `source-transport`: Q2b's decoder-to-device relation | Authoritative decoder operation, byte representation, selected imperative route and Clight. Owns the connection absent between `Derive` and emitted C, including its preamble. | Source-to-imperative/Clight constants preserving success/refusal, initialized destination, frame and declared trace; source identity includes representation and foreign contracts. | Existing Q2b work is charged once. A new printer proof, port or component extension requires a separately estimated child if it exceeds that scope; none is commissioned by this rejection. |
| `context-preservation`: the R-05-024/R-05-032 secure-compilation hardening deliverable | Compartment/interface contract, CHERI lowering and ABI, the universal-contract interpretation in `machine-logic`. | Top-level statements quantify over an adversarial linked context and compose with the exact final artifact. A theorem about only known generated code cannot fill this slot. | Existing M1 backend estimates explicitly exclude this hardening proof. Its full establishment and an alternate route's distinct preservation join remain unpriced; Q21b cannot claim a saving by omitting either. |
| `artifact-admission`: the R-05-023a validation and R-05-026 admission hardening deliverables | `machine-logic`, final image and source closure, actual TAL producer/checker and soundness artifacts, component tier and required observation/cost contracts. | Kernel-checked final-byte refinement and source correspondence plus the applicable admission artifacts, refreshed after assembly, linking and image composition; required guarantee removal fails at that guarantee. | Existing hardening obligations retain their owners. Q20c prices promotion of supplied evidence, not construction of this missing logic, validator or TAL foundation. |

`machine-logic` precedes its concrete byte instance; that instance precedes its
resource interpretation and the generic clients. Source transport joins the
selected representation and compiler, while contextual preservation and admission
join the common machine term and final artifact. The source-level generic pilot
requires the actual operation laws it uses; this map does not add every production
theory as a new entry gate for a sequential source theorem. The full endpoint
still owes the R-13-017 theories and tier-specific guarantees, with their costs
retained in the compiler comparison.

### Source and representation boundary

Q21a and Q21b share an explicitly sequenced computation graph with entry and
exit-indexed resources, represented runtime lengths/results, closed effects and
trace/observation contracts. The concrete instance interprets those resources as
one byte memory and capability state. Abstract source derivations and producer
simulation both name that instance; agreement cannot be inferred from matching
predicate names or from successful parsing of the same source text.

For Q21a's disjoint `bytes` and `audit` fields, the concrete laws justify splitting
ownership, lending only the selected field and rejoining it with its actual final
contents. A shared reborrow keeps the overlapping parent suspended through every
transitive capture until the last live child ends. The language's `core-soundness`
package owns composition at ordinary returns, branch-returned views, loop back
edges, `break` and `continue`; the foundation owns the entailments those rules use.
No law turns a logical region name into a tagged hardware capability.

The experiment-local `PreparationOpen`/`finish` protocol belongs to Q21a's
`core-repair-trial` fixture and its soundness package. Its representation, terminal
transition and preservation proof must be supplied there before the fixture runs.
It is not a CHERI primitive or a revision of the ring lifecycle. A fixture-only
cleanup theorem supplies no service-release, secure-erasure or fault theorem.
This keeps the concrete memory interpretation separate from a protocol invented
to exercise source cleanup, without pricing either twice.

## Ownership and entry

Q2b owns a copy-once parser extension that initializes its fixed destination under
R-05-124. The implementation baseline must state its success/error outputs,
whole-destination initialization policy, overflow refusals and allowed effects.
The read-only `DescriptorCheck` is the development reference, not that baseline.
M7.1 owns the executable copy-service private staging operation under the existing
roster-realization clause. Its baseline must refine the abstract copy service and
define the concrete byte representation, accepted lengths, refusal state and
staging lifetime. If either realization exceeds that owner's existing scope,
Q2c must insert and price an extension before work opens.

The bounded generic pilot uses sequential, stable source memory and a disjoint
private destination. It does not acquire an atomic snapshot of a Byzantine peer's
concurrently changing buffer. The service owner must separately establish how its
copy-once policy relates to the delegated source and staging lifetime. SPSC
publication, DMA, revocation, secure erasure and fault-model guarantees retain
their existing owners and cannot be inferred from this bounded pilot.

The [workflow contract](../languages/workflow-contract.md) reserves parser destination
initialization for development and service private staging for held-out reuse.
Freeze the qualified generic interface before the staging adaptation. Designing
that interface from the reserved client's implementation consumes its independence
and requires a replacement consumer and reviewed protocol. Charge the shared
adaptation once between Q19c and Q20b.

Q21a owns source-language rules and their qualification design. Q21b owns a fair
comparison of compiler routes. Neither can fill a missing primitive-law slot by
adding an abstract signature. Q19a/Q19b may qualify existing proof clients, and
the current M1/M7 realization route remains independent of these experiments.

## Review decision

**Decline commissioning the missing CHERI foundation for this bounded generic
experiment.** This is Q2c's reasoned-rejection result. The map gives the next
hardening and component owners concrete obligations, but does not turn an owner
name into an implementation estimate. The mandatory machine logic, compiler,
decoder and admission obligations remain in force; the current M1/Q2b/M7.1
realization route continues. Q19c remains unopened until its actual checked-law
entry condition is met by separately accepted work.

The decision follows from the theorem subjects and scope, rather than an assumed
cost for an unfamiliar tool. `Descriptor.descriptor_check_br2fn_ok` preserves an
untyped byte-array footprint at `BasicC64Semantics`. A CHERI store must additionally
account for capability permission, tag, provenance and initialization behavior;
those premises are absent from that relation. `copy_once` records one abstract
read of a natural-valued datum, so its extent and second-image theorems cannot
serve as the missing byte operation or snapshot law. The available narrowing
theorem decides slot-plan arithmetic, not the load/store relation. No one of
these statements can be instantiated into the required concrete instance by
renaming its pointer argument.

The missing work also crosses the experiment's cost boundary. R-05-019b and
R-13-017 require a shared canonical machine subject and logic; R-05-023a's final
validator depends on it. R-05-024 and R-05-032 require preservation against an
adversarial linked context. Their proof scope is not bounded by the parser's
generated instruction census or by a sequential copy operation. The checklist
explicitly keeps these proof instruments in the hardening program and prices
M1's current cells for functional bring-up. A stopping cap for a read/write
prototype would measure an incomplete experiment, not bound establishment of
these required theorems. The named consumers supply no measured amortization of
that establishment, and Q20a's source-level reuse threshold cannot supply it.

Local absence does not imply upstream impossibility. The pinned capability
results and the strategy's comparisons remain candidates for reuse at their
stated semantic subjects. Selecting their concrete connection, assumptions and
dependency closure is missing work. This decision makes no fresh claim about
their maintenance state and imports no upstream implementation. Finite emission
lemmas remain a Q21b comparison mechanism; they cannot replace the shared logic
or arbitrary-context obligation by a proof over only generated programs.

The following decisions make the boundary independently reviewable. These are
statement-level counterexamples to claimed reuse, not executed mutation results.

| Proposed shortcut | Decision and discriminating case |
| --- | --- |
| Use the existing descriptor theorem as the CHERI read instance | Refused: two entries with identical address bytes but different capability validity or permission satisfy the same flat-byte predicate, while the modeled CHERI access can distinguish them. The required representation premise is missing. |
| Use the abstract copy theorem as byte-store or snapshot evidence | Refused: a realization can report the abstract datum and read count while storing a wrong destination byte. A concrete refinement must reject it. Stable-source sequential copying must not be presented as one atomic read of a racing peer. |
| Obtain concrete source loans from hardware bounds alone | Refused: an in-bounds write through a suspended parent can preserve spatial bounds while violating the live child's exclusive or shared loan. The concrete resource interpretation and source rules must exclude it. |
| Replace a contextual theorem by a closed emission simulation | Refused: the theorem quantifies only over producer output and supplies no conclusion for a linked adversarial context outside that grammar. The required universal quantifier is absent even if every emitted operation is correct. |
| Mark the generic pilot ready because this map has owners | Refused: an instance requiring read/write/frame laws still lacks actual Rocq constants. Removing a required guarantee while retaining operation laws must leave that guarantee unresolved. |
| Implement parser destination or service staging under Q19c | Refused: Q2b and M7.1 already own those realizations. Their entry reviews identify any extension beyond existing scope and price it there; the generic proof and held-out adaptation are charged once at Q19c/Q20b. |

### Re-entry evidence

A later proposal reuses this map and must change the evidence that decided the
rejection. It supplies the canonical term/generation identity, chosen concrete
representation, available constants and assumption audit, plus an implementation
breakdown for every remaining obligation with Start, Owns, Check and Join. The
hardening owner prices logic establishment and contextual preservation explicitly;
the compiler comparison accounts for any route-specific transport and its ongoing
repair. Q2b and M7.1 confirm their concrete parser and staging realization scopes,
including any separately priced extension. Existing costs are credited once.

Independent review then checks satisfiable entry states, intended wrong-read and
wrong-store cases, failure restoration and the missing-guarantee case at the
actual selected subject. A source-level pilot may reopen only with the checked
laws its contract requires. A full artifact trial additionally needs all its
production endpoint evidence and complete establishment/maintenance accounting.
Neither reopening can rely on a reused completion label, an unchecked interface
signature or a numerical prototype cap.

The document checker verifies references and corpus consistency. It cannot
establish metatheory, theorem adequacy or affordability. This decision changes no
proof, model, register or generated interface source.
