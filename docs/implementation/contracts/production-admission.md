# Production admission prerequisite handoff

This is the missing-prerequisite contract for M7.1c in the
[project plan](../../../PLAN.md). It connects existing
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
| Each roster member's executable owner, joined by M7.1a | Assign its actual tier, emit the canonical typing derivation for those installed objects, and provide its fixed-artifact source-correspondence theorem, placement contract and required tier evidence. The member's producer owns missing derivation generation; M7.1c owns concrete-layout and package-local checking. |
| M1.4 and Q2c's `artifact-admission` foundation owner | Resolve the covering-instrument decision and actual post-CompCert correspondence records. U-26 scopes a decision and one record's shape; it does not supply the producer or records. |
| M7.1c integrator | Select the composition-time CIC consumer for actual correspondence/tier terms and the trusted current-state adapter for authenticated verdict reuse, including their committed environment, assumption audit and resource contract. An unrelated successful proof-gate receipt cannot stand for that check or supply a prior-state root. |

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

## Fixed artifacts and authenticated checking reuse

[The fixed-package contract](fixed-packages.md) is R-13-028's default construction
boundary. Its artifact identity hashes a canonical manifest containing the actual
output-object digests, source and interface/resource contract, and versions.
An input/build key, transport path or successful producer invocation cannot
identify or admit the output on its own.

The package-local correspondence theorem is over those exact bytes and the
contract's typed premises. The fresh composition evidence must connect it to the
concrete installed objects, actual capability wiring and generation checks under
R-05-026. The first placement path translates every package region by one common
base, preserving relative geometry; its theorem must cover the emitted code and
initializer at that placement. Independently movable regions require the
separately proved capability-relative ABI. The producer must not replace this
connection with a claim that arbitrary code is position independent. TAL-067 and
TAL-068 still bind and check the derivation at every concrete layout.

Every generation checks fresh modular linkage or instantiation evidence that
discharges those premises for its exact installed layout and wired capabilities.
The selected consumer must connect the reused package theorem to the final
generation's source-correspondence claim, including assembly, linking and image
construction. A package-local cache hit does not waive this check. Hash agreement,
TAL acceptance or a theorem about another placement cannot replace it.

For package-local CIC reuse, the trusted adapter obtains the prior checked-set
root from the current admitted generation, then authenticates the complete saved
set against it. The candidate package, composer, fetched receipt and successor
signature cannot choose that trust anchor. The reuse key includes the exact
artifact/proof/source/contract identities and spec/model/profile/decoder,
checker, committed CIC environment, transitive assumptions, tier, policy and
resource context. Equality is exact. A missing entry or changed member requires
the actual package checker; an unavailable checker refuses rather than inventing
a successful entry. Rehashing the objects remains mandatory even on a match.

The trusted checker/policy adapter supplies the current expected context for each
artifact. An untrusted request cannot select an older context to reuse a stale
verdict. The coordinator checks this agreement before and after all consumers run.

New successful package verdicts remain private candidates until fresh TAL,
wiring, handler-graph, placement/initialization, scheduling and global resource
checks all pass. Failure or interruption publishes no successor checked state.
The authenticated generation transaction commits its root with the other
generation roots; rollback and recovery apply to that root as well. A returned
candidate set is not independently admitted state. This state interface and its
native refinement are M7.1c/M6.10 joins; a host coordinator with fixture checker
callbacks supplies neither the actual checker nor production acceptance.

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
   Exhibit the same fixed package at two permitted translated layouts with fresh
   concrete TAL bindings. Commit and restore authenticated checked state across
   a boot, then show unchanged package-local verdicts reused while the fresh
   layout and generation checks still execute. Changing one package or any reuse
   context member invokes actual package checking again; a forged prior set,
   wrong root or interrupted generation cannot publish a reusable verdict.
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
