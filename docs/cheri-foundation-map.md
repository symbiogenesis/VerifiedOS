# CHERI component foundation map

This is Q2c's prerequisite inspection for parser destination initialization and
copy-service private staging. It supplies the existing-route input to Q21b's
[compiler comparison](compiler-route-contract.md) and identifies what Q19c would
need to instantiate a generic bounded operation. The inspection baseline is
repository revision `e6391c6aacb5a89141250d133f8875efa41a994e`.

The map records source subjects and existing measurement records. It does not
report a fresh prover run, a byte-memory implementation or an accepted target
connection. Q2c remains open until the missing foundation has reviewed, separately
estimated implementation cells or the decision takes its reasoned-rejection arm.

## Available artifacts

| Artifact and actual constant | Subject available at the inspection baseline | Limit at the consumer boundary |
| --- | --- | --- |
| [DescriptorCheck.v](../tools/bedrock2-lowering/DescriptorCheck.v), `Descriptor.descriptor_check`, `Descriptor.spec_of_descriptor_check`, `Descriptor.descriptor_check_br2fn_ok` | A read-only descriptor check over `BasicC64Semantics`, a `listarray_value AccessByte` footprint and a separating frame. The specification preserves the trace and footprint and returns the functional check's result; the derivation ends in `Qed`. | Its pointer is a Bedrock2 word, its memory is byte memory, and its source never copies a descriptor. Neither a tagged capability representation nor destination initialization follows from that statement. |
| [Q2a's recorded experiment](../tools/bedrock2-lowering/README.md#build-and-run) | A recorded closed-context derivation, reproducible C emission and measurements at the revisions the report names. | This inspection does not refresh that evidence. The C printer is outside the checked relation; the report's older backend measurement does not describe every subsequent compiler revision. |
| [CopyRingService.v](../proofs/CopyRingService.v), `copy_once`, `the_copy_once_service_stays_inside_the_validated_extent`, `the_copy_once_service_reads_the_source_once`, `the_copy_once_service_does_not_vary_with_the_second_image`, `the_copy_once_service_refuses_an_overlong_length` | A model with `buffer` containing natural-valued length and datum, and `copy_run` recording reads, staged datum and bytes. The theorems express extent, single-read, second-image independence and refusal properties of that model. | No theorem here interprets the datum as a concrete byte array, executes a CHERI load/store or establishes a concurrent atomic snapshot. A model read count is not an instruction trace. |
| [CopyRingService.v](../proofs/CopyRingService.v), `publish_keeps_the_invariant`, `take_keeps_the_invariant`, `the_invariant_survives_every_interleaving` | Preservation of the `ring_view` ordering and capacity invariant over the specified index transitions. | This is an index algebra. It supplies neither hardware publication ordering nor a byte-memory frame rule. |
| [MemoryPlan.v](../proofs/MemoryPlan.v), `spec_narrow_ok`, `the_specification_narrowing_check_admits_only_exact_narrowings` | A narrowing predicate and theorem over the authored slot-plan arithmetic. | M1.2e connects the backend's emitted narrowing to the model's bounds behavior; this theorem alone is not that connection or a pointer-advance rule. |
| [cap_common.sail](../model/model/core/cap_common.sail), `inCapBounds`, `setCapAddrChecked`, `setCapOffsetChecked`; [CHERI instructions](../model/model/extensions/CHERI/cheri_insts.sail) | Operational source definitions in the curated ISA model. | These are semantic inputs, not Rocq primitive-law constants. R-05-019b requires Sail's own emitted definitions as the common theorem subject. |

Reproduce the source inspection with `git show <baseline>:<path>` and inspect each
named declaration through its complete statement and proof. Use
`git ls-files -s upstream` for the pinned artifact inventory. A gitlink proves what
is pinned, not that its theorem has been instantiated for this machine. The
[third-party record](../THIRD-PARTY.md) and the
[strategy's capability-aware comparison](verification-language-strategy.md#capability-aware-and-parametric-verification)
keep upstream results and their semantic subjects separate from local connections.
No upstream code is incorporated by this map.

## Required connections

The following are required proof obligations, not assumed interface axioms. A
consumer may accept their names only after they resolve to checked constants over
the selected representation and semantic subject.

| Needed law or connection | Required statement and discriminating evidence | Current owner and readiness |
| --- | --- | --- |
| Canonical machine term and logic | Identify Sail's emitted Rocq term and its complete generation identity. Establish the R-13-017 logic over that exact term, including the connection needed by R-05-023a. A substitute deep embedding needs an agreement theorem and the applicable R-05-020 admission. | Q2c scopes; Q2b joins the selected machine connection. No checked local foundation is identified by this inspection; implementation scope and estimate remain unresolved. |
| Buffer and pointer representation | Relate byte sequences, lengths, initialization and disjoint footprints to tagged capabilities, permissions, bounds, validity and permitted provenance. Distinguish capabilities stored in memory from ordinary byte contents. State live ownership and representation on every ordinary exit. | Q2c scopes the missing laws; M1.2b/M1.2g own compiler encoding and tagged value/memory carriers. Those compiler structures alone do not establish a component memory logic. |
| Read | A valid readable capability and an initialized in-bounds index return the represented byte, preserving the source and disjoint frame. Specify the exact modeled trace and invalid-access behavior. A same-type wrong-offset read must fail the required relation. | Q2b consumes the parser instance. The Bedrock2 footprint theorem is available only at its own subject; its CHERI instance is missing. |
| Write and initialization | A valid writable capability permits the specified byte update, preserves other bytes and the disjoint frame, and advances the initialization predicate precisely. Account for the model's tag effects on byte stores. Wrong-store and incomplete-fill variants must fail the intended postcondition. | Q2c scopes; Q2b owns the parser's fixed destination; M7.1 owns service private staging. No concrete byte implementation is identified for either copying client. |
| Bounded advance and narrowing | Address arithmetic stays representable without wrap, preserves the permitted provenance and permissions, and never silently enlarges authority. Distinguish a legal end pointer from a legal dereference. Cover empty spans, the last byte and overflowing length/offset combinations. | M1.2e owns backend narrowing, M1.2d its emission use; Q2c scopes the component law and its machine connection. Slot-plan arithmetic is an input, not a proved load/store contract. |
| Frame and scoped restoration | Disjoint storage remains unchanged; scoped loans suspend the affected owner and return it with the correct contents and initialization state. Error exits return their declared resources. A false or missing restoration law must leave the requesting client unprovable. | Q2c scopes concrete laws; Q19c factors checked laws only after its entry gate. Q21a's language design does not provide the concrete instance. |
| Source to imperative code and Clight | Connect the authoritative operation and representation to the generated imperative implementation and the Clight waypoint R-05-043 requires. Cover the selected preamble/foreign primitives and success, failure, footprint and trace behavior; printer output alone cannot witness this theorem. | Q2b owns route selection and the device relation; Q2c assigns extra proof work before implementation. The existing `Derive` reaches Bedrock2 only. |
| Compiler, ABI and final bytes | Connect capability-correct lowering and call/return/spill behavior through assembly, linking and image composition. Bind R-05-023a validation to exact bytes and the canonical Sail term. Keep R-18-014's verified-C and certifying-Rust duties and R-05-026's admission obligations. | M1 owns compiler realization; Q2b and Q3b join component/artifact evidence. Functional bring-up and production proof are different acceptance endpoints. |
| Stronger contextual guarantees | State the guarantees the selected consumer actually requires and supply the corresponding logic, preservation and arbitrary-context results. Retaining operation laws while removing a required guarantee theorem must fail at that guarantee. | Q2c scopes the foundation; Q21b compares equivalent duties. A finite emission vocabulary or a sequential copy theorem waives none of the required obligations. |

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

The [workflow contract](language-workflow-contract.md) reserves parser destination
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

The source-level boundary inventory is available for review. The full foundation
is not yet responsibly priced: a bounded read/write client does not bound the
cost of the canonical program logic, its machine connection or the required
contextual preservation argument. This inspection therefore supplies no estimate
for that work and opens no implementation lane. Giving the missing theorem an
owner name would not complete Q2c's acceptance predicate.

To close Q2c by acceptance, select the actual representation and semantic route,
then attach a separately estimated implementation cell to each missing connection
above, with its Start, Owns, Check and Join. Charge existing M1/Q2b/M7.1 realization
work once; identify any additional parser or staging realization explicitly.
Review the estimates against the named consumers and the unchanged artifact
endpoint. If that review cannot bound or justify the foundation, record Q2c's
reasoned rejection and leave Q19c unopened. The present map neither rejects the
existing compiler route nor declares the generic trial executable.

The document checker verifies references and corpus consistency. It cannot
establish that a theorem expresses its cited requirement or that a proposed
foundation is affordable. No proof, model, register or generated interface source
changes as part of this inspection.
