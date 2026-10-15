# Production admission prerequisite handoff

This is the missing-prerequisite contract for M7.1c in the
[implementation checklist](../implementation-checklist.md). It connects existing
owners without defining another certificate language or commissioning their missing
proofs. M7.1c remains open until its executable checker and real-roster joins pass.

## Existing boundary and missing decisions

[The boot contract](boot-roster.md#production-composition-input-and-projections)
owns the composition, projections and produced-image binding.
[The admission reference](../../../tools/admission/README.md) already joins those
identities and records an honest production refusal.
[AdmissionPath.v](../../../proofs/AdmissionPath.v) decides discharge metadata;
its carrier contains no instruction typing or proof term. Neither a supplied
derivation digest nor a successful reference comparison supplies that evidence.
The [language status](../../languages/typed-assembly-language.md#15-status)
records the missing type system, checker and soundness proof.

Before implementation expands, the M7.1 integrator records these owner decisions:

| Owner | Decision and handoff needed by M7.1c |
| --- | --- |
| M7.1a with M7.1d | Select a real member's final installed objects and export their concrete layout, entry points, initializer, immutable tables and wiring from the same composition/build revision. Identify how that export corresponds to the harness image. |
| M7.1c, with the R-18-018(b) TAL workstream | Identify the pinned executable `cheri-rv64` profile, its machine-term/decoder identities, complete rule table and checked metatheory; assign and price absent construction before opening it. The language prose and the demo metadata are insufficient inputs. |
| Each roster member's executable owner, joined by M7.1a | Assign its actual tier, emit the canonical typing derivation for those installed objects, and provide its artifact-local source-correspondence theorem and required tier evidence. The member's producer owns missing derivation generation; M7.1c owns checking it. |
| M1.4 and Q2c's `artifact-admission` foundation owner | Resolve the covering-instrument decision and actual post-CompCert correspondence records. U-26 scopes a decision and one record's shape; it does not supply the producer or records. |
| M7.1c integrator | Select the composition-time CIC consumer for the actual correspondence/tier terms, including its committed environment, assumption audit and resource contract. An unrelated successful proof-gate receipt cannot stand for that check. |

The [unassigned proof map](../../assurance/unassigned-proof-map.md#8-mandatory-work-outside-the-priced-total)
keeps CHERI-TAL soundness and the correspondence producer outside the priced
total. This contract supplies neither an estimate nor authority to absorb them in
M7.1c's existing cell. M6.2b retains the deferred on-device CIC foundation and native
implementation; its qualification is not evidence that an offline consumer or a
TAL evaluator exists.

## Concrete producer and consumer handoff

The producer hands over the installed artifact and certificate described by
[the TAL certificate](../../languages/typed-assembly-language.md#81-the-certificate)
and [installed-artifact binding](../../languages/typed-assembly-language.md#9-binding-the-certificate-to-the-installed-artifact).
R-13-003's content-addressed capability image is the admission object. The current
boot/build join consumes a final ELF image. Its exact runtime bytes remain an
input; that join alone does not establish R-13-003's installed-object representation
or the export mapping. M7.1a/d identify that representation and byte-for-byte mapping
before M7.1c claims an image-bound production result.

The handoff identifies exact installed-object, source-closure, certificate,
profile and decoder bytes, together with the producing revisions and configuration.
Producer identities establish provenance only: the checker decides the artifact,
certificate and profile, as R-06-015b and TAL-071 require. A producer's success flag,
source theorem or instruction listing cannot replace the checker decoding the
installed executable extents and validating the transported local premises.

For CIC evidence the handoff also identifies the actual entry theorem, its
proposition, proof term and transitive environment. The consuming check establishes
that the proposition names this exact source closure and final installed artifact,
including the assembly, linking and image-construction connection R-05-023a and
R-05-026 require. Record the checked entry's native transitive assumptions, its
inhabited hypotheses and the applicable generation-declared resource limits.
An entry name, object hash or closed theorem about a different artifact is no
substitute. The [CIC qualification contract](../../assurance/cic-checker-qualification.md)
continues to own the deferred checker route and its serialization/resource proofs.

M7.1c consumes these inputs through the language's existing
[profile admission](../../languages/typed-assembly-language.md#58-profiles-are-frozen-and-versioned-like-the-theory),
[checker algorithm](../../languages/typed-assembly-language.md#102-the-algorithm)
and [verdict contract](../../languages/typed-assembly-language.md#104-acceptance-and-rejection).
Its implementation proof is R-06-015d's equivalence to the actual pinned judgment;
the profile's safety theorem is separately TAL-082 through TAL-085. Compilation
and GC-free C refinement retain the checklist's admission-checker route and
[C-refinement foundation qualification](../../assurance/c-refinement-foundation-qualification.md).
Finite comparisons are useful implementation evidence and discharge neither proof.

## First executable case and acceptance

1. Freeze one actual roster member's complete emitted instruction population,
   installed-object export, assigned tier and certificate inputs. Select the
   smallest available member whose whole population can be covered; a handwritten
   fixture or selected instructions from a larger member cannot be that case.
2. Review the profile/decoder/rule and proof-consumer handoff above. If a required
   rule, theorem, serializer connection or correspondence producer is absent,
   return that specific dependency to its named owner for a scoped implementation
   contract and estimate. Do not implement a permissive partial production checker.
3. On available foundations, run the real artifact through both admission consumers.
   Require the TAL verdict to agree with the pinned judgment, and require actual
   CIC checking of its artifact-local correspondence and applicable tier terms.
   Retain exact input, checker/toolchain and proof-environment identities.
4. Pair acceptance with semantic refusals: a changed installed object with the old
   certificate; a coherently rebound artifact whose invalid local transfer, edge
   refinement or citation the relevant rule rejects; and a correspondence term
   proving a different artifact or source closure. The coherent control distinguishes
   typing from hash matching. Use the language's requirement-indexed
   [conformance suite](../../languages/typed-assembly-language.md#13-conformance-and-adversarial-suites)
   for complete checker qualification, including malformed and over-limit inputs.
5. Expand only after that complete case. Join every real runtime member through
   the same composition, final installed image and graph; replay the record and
   refuse the generation when any member or required proof refuses. The boot
   consumer rejects a different final image. No fixture scope or saved refusal
   record is promoted to production acceptance.

The first case is a prerequisite checkpoint. M7.1c's complete acceptance still
requires the actual implementation/refinement, qualified profile and all-member
derivations, correspondence and tier evidence. Proof acceptance follows the
[portable proof workflow](../../assurance/proof-assistance.md#acceptance-boundary)
and the repository's hosted validation handoff; a pending hosted verdict is
recorded as pending.
