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
| M7.1a with M7.1d | Select a real post-bootstrap member eligible for checker admission and export its final installed objects, concrete layout, entry points, initializer, immutable tables and wiring from the same composition/build revision. Identify how that export corresponds to the harness image. Pre-admission firmware remains a boot/release-proof input under R-05-091, not the first admitted member. |
| M7.1c, with the R-18-018(b) TAL workstream | Identify the pinned executable `cheri-rv64` profile, its machine-term/decoder identities, complete rule table and checked metatheory; assign and price absent construction before opening it. The language prose and the demo metadata are insufficient inputs. |
| Each eligible admitted member's executable owner, joined by M7.1a | Assign its actual tier, emit the canonical typing derivation for those installed objects, and provide its fixed-artifact source-correspondence theorem, placement contract and required tier evidence. The member's producer owns missing derivation generation; M7.1c owns concrete-layout and package-local checking. Bootstrap/TCB members retain their release-proof route. |
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

## Complete retained M-mode export checkpoint

The retained firmware byte-export candidate is the complete normal `mmode-firmware` stage
from [the retained chain](../../../firmware/chain/target/manifest.json), owned by
M3.5 and selected through M7.1d's
[retained-product adapter](../../../tools/composer/README.md#retained-boot-producer-adapter).
This selection makes no smallest-member claim. The signed `kernel` population is
[the kernel-entry fixture](../../../firmware/chain/kernel_stage.s), so it cannot
replace a real member. The supervisor/copy component reports likewise do not
establish standalone installed objects for those members.

M7.1a/d's bounded export uses the existing historical staged-input validator and
[complete M-mode construction](../../../tools/vos/chain_mmode.py#mmode_image).
It includes the hand-lowered entry, the entire compiled stream and embedded
kernel-verification root, with no reachable-function pruning. The exporter
records the exact text and data extents, entry, zero-filled inter-extent gap,
slot-A tag and the stack span outside the signed payload. Reconstructing those
extents, gap and tag must equal the retained normal `mmode-a` signed payload
byte for byte, using its declared header boundary. The signed envelope remains
transport/authentication data rather than executable code. All emitted text,
including alignment bytes, remains in the executable population for the future
installed-artifact decoder; assembler sites are producer observations only.

This is an offline byte export, not R-13-003's admitted capability image.
[The existing main-die composer](../../../tools/vos/chain_mmode.py#compose_main)
loads the entire M-mode window as writable and executable. The export preserves
that actual harness permission observation and reports the installed-object
mapping as unresolved; it must not silently claim the split text/data permissions
are those of the loaded window. M7.1a/d must supply a real immutable-image and
initializer mapping, entry/wiring distribution and final-image connection for
the firmware boot/release-proof handoff. R-05-091 places M-mode firmware outside
the admitted set: completing that mapping cannot make it the first checker-admitted
member. M3.5 retains actual firmware integration and its Tier-0 proof; Q39 retains
compiler qualification. The [installed-authority disposition](fixed-packages.md#retained-boot-firmware-and-installed-authority)
separates loaded permissions from the actual reset and handoff authority.

`composer export-staged-mmode SOURCE --products CATALOG --output REPORT` replays
the existing historical candidate and product catalog, selecting only the
`mmode-firmware-artifact` slot's normal `mmode` unit. It publishes one canonical
JSON byte-bearing report under `out/` and changes no retained input. Its closed
root has `schema_version: 1`, `kind: historical-mmode-byte-export`, `member`,
`source`, `catalog`, `bindings`, `compiler_provenance_status`, `entry`, `regions`,
`payload`, `stack`, `harness_window`, `installed_mapping`,
`production_admission: false` and `final_target_acceptance: false`. References
use the existing `path`/`sha256` shape; bindings include construction helpers'
local Python import closure and their non-Python inputs. Region records carry
`kind`, `address`, `length`, `sha256` and `hex`, in text, zero-gap, initializer,
slot-tag order. Payload records its address, length and digest. Stack records
its address, length and external zeroing owner; harness window records actual
address, length and writable/executable booleans. The installed mapping is
`unresolved-rwx-window`. Addresses and lengths are nonnegative JSON integers;
hex strings encode exactly the recorded bytes, including the zero gap.
The exporter binds inputs before and after reconstruction and rechecks all
bindings and output containment/aliases at atomic publication.
It supplies no assigned tier, typing certificate, correspondence theorem,
checked-state root or successful admission flag. Missing profile/rules and
metatheory return to R-18-018(b); the concrete certificate returns to the member
producer; artifact-local correspondence returns to M1.4/Q2c; the actual CIC
consumer and authenticated current-state adapter remain M7.1c's named decisions.
No one of those absences becomes an empty accepted object.

Acceptance for this export is the unchanged complete normal stage and exact
payload equality. Refusal controls cover a missing or substituted staged unit,
source or helper drift during reconstruction/publication, altered root, text,
initializer, zero gap or slot tag, a truncated or mismatched payload, a wrong
entry or extent, substituted loaded-window permissions, and an output aliasing
any consumed input, including a hardlink.
Every refusal preserves the previous output and historical bytes. A repeat export
of unchanged inputs is byte-identical. These finite host checks establish the
export only; decoded instruction coverage, concrete TAL/CIC checking, production
mapping and qualified target acceptance retain the preceding owners.

## First-case eligibility and consumer disposition

The first checker-admitted case must come from the post-bootstrap admitted set.
[R-05-091](../../requirements-register.md#512-no-ambient-state) explicitly puts the
pre-admission boot substrate and M-mode firmware outside that set, carrying the
no-ambient-state obligation as ordinary Tier-0 proof over statically planned
state. [The TCB boundary](../../spec.md#6-trusted-computing-base-exhaustive)
likewise excludes a checker-admitted TCB category (R-06-004, R-06-015c). This does
not remove firmware's binary-level release proofs, source correspondence or
universal capability restrictions. The complete retained export remains useful
for its boot and image-construction obligations; its byte availability does not
supply eligibility for install-path admission.

The [production input join](../../../tools/admission/README.md#production-input-join)
currently projects every runtime roster member, including boot/TCB members, into
its metadata request. [Its record constructor](../../../tools/vos/admission_production.py#make_record)
always emits a refused generation, and even a supplied derivation never becomes
a checked proof. That refusal is valid input-binding evidence; the projected
runtime census is not a definition of the checker-admitted set. The
[proof-route contract](#production-proof-route-record) separates these obligations
without changing the existing fixture/reference decisions or request schema.

The next actual runtime export request is `copy-service`, owned by M7.1e with
M7.1a/d owning the standalone installed-object and image join. Its
[source inventory](../../../tools/composer/packages/copy-service.json) identifies
the existing core and target adapters, and its
[executable boundary](../../../copy-service/README.md#executable-boundary)
retains the caller-owned ring and authority obligations. This is a request for
that member's missing producer handoff, not selection of an available admitted
package or a smallest-member claim. The
[scalar join](../../../tools/vos/scalar_join.py#source) embeds the compiled copy
stream, atomic/notification adapters and partition entry in a shared kernel and
supervisor image. The
[compiled unit](../../../copy-service/test/target_unit.c) also includes the target
comparison implementation. A symbol-delimited slice of that harness, the source
inventory alone or a successful component replay does not establish a standalone
member's complete installed executable population.

Before selecting it as the first case, M7.1e supplies the complete emitted
member under a declared standalone build recipe, with an explicit disposition of
comparison-only code and all required runtime adapters. Lawful producer-side dead
elimination remains permitted by the fixed-package construction contract; the
export must cover that recipe's entire emitted population rather than select a
reachable slice of the shared harness after the fact.
M7.1a/d connect that product's entire code/rodata and initializer extents, entry
set, immutable tables and initial capability wiring to the final installed image,
with its source closure and actual producer identity. The same artifact must
have a supported placement contract before a translated-layout claim is made.
The composition owner assigns the real assurance tier; the fixture tiers in
`AdmissionPath.v` supply no assignment. Missing output returns to these owners
before certificate generation or a production verdict is attempted.

The available consumers have the following concrete boundaries:

| Required input | Source reading and disposition | Next owner |
| --- | --- | --- |
| Executable TAL profile, decoder, rule table and metatheory | [The language status](../../languages/typed-assembly-language.md#15-status) leaves the type system, checker and soundness proof unbuilt. [The certificate carrier](../../../proofs/AdmissionPath.v#Cert) contains versions, an artifact binding and judgment/move/facet/site metadata; [the host decision](../../../tools/vos/admission.py#decide) checks that metadata. [The assembler](../../../tools/vos/dialect.py#encode) encodes selected mnemonic rows; [the excluded-mnemonic matcher](../../../tools/vos/decode.py#encoder_rows) does not decode installed bytes. None supplies TAL-045's independent decoder or the rule-table judgment. | R-18-018(b) owns construction and its estimate before M7.1c consumes it. |
| Concrete member certificate and source correspondence | The inventory and shared-harness product above contain no canonical TAL derivation or theorem connecting the complete installed member to its exact source closure. [The artifact-admission foundation](../../assurance/unassigned-proof-map.md#5-the-closing-proofs) leaves the post-CompCert instrument and per-image records with their named owners; U-26's proposed record shape is not a producer. | M7.1e supplies the member derivation; M1.4/Q2c's artifact-admission owner supplies the correspondence instrument and record; M7.1a/d supply the actual installed mapping. |
| Actual CIC consumer for package and fresh linkage terms | [The reuse coordinator](../../../tools/vos/package_admission.py#Checkers) receives package, layout, linkage, generation and current-context checks as caller callbacks. [The CIC corpus reader](../../../tools/vos/cic_corpus.py#Constant) records queried declaration metadata and is no proof-term consumer. [The CIC qualification](../../assurance/cic-checker-qualification.md) retains the actual checker, serialized-term connection, assumptions and bounded-refinement requirements. A normal repository proof-gate receipt does not check the required artifact-local proposition on this install path. | M7.1c selects and binds the actual composition-time consumer; M6.2b retains its deferred checker-foundation and native implementation duties. |
| Authenticated current-state reuse | [CurrentGeneration](../../../tools/vos/package_admission.py#CurrentGeneration) is a protocol for an externally supplied protected root. [Restoration](../../../tools/vos/package_admission.py#restore) verifies saved bytes against that supplied root; it does not obtain the root from an admitted generation or commit a successor transaction. The callbacks and root exercised in the host tests are fixtures. | M7.1c/M6.10 supply the trusted current-generation and authenticated transaction adapters. |

These readings return specific missing inputs. They do not commission the TAL
foundation, a new proof consumer or a permissive production checker under M7.1c's
existing integration estimate. The first-case selection stays open until an
eligible complete member and those consumers are available.

## Production proof-route record

M7.1c's bounded schema connection is a version-2 refusal record over the complete
runtime request. A fixed authored
[JSON policy](../../../tools/admission/production-population.json) owns the reviewed route declaration
for each member; callers cannot select a different policy. Each declaration names
the member, one route and the requirements supporting that judgment. The record
binds the exact policy and [requirements register](../../requirements-register.md)
bytes alongside the already checked roster, products and request. A citation
records the review's grounds; hashing that source does not mechanically decide
TCB membership, prove a classification correct or assign an assurance tier.

The closed routes are `bootstrap-release`, `tcb-release`, `checker-admitted` and
`unresolved`. Bootstrap and TCB members retain their missing release-time
source/binary correspondence, functional-refinement and measured-boot evidence;
they do not acquire install-path certificate or admission-tier obligations.
Checker-admitted members retain the tier, derivation and actual TAL/CIC consumer
obligations. An unresolved member carries an explicit missing-route blocker and
cannot disappear from the generation's obligations. Existing request tier and
derivation fields remain bound declarations in the record, including when they
do not apply to the selected route; their presence changes no route or verdict.

The initial policy follows R-05-091 and R-06-007 for the two firmware members and
R-06-001/R-06-004 for the kernel and crypto core. The first-case request above and
R-06-023 support the copy service's contained route. The supervisor's contained
route follows the concrete role decision below. The storage slot remains
unresolved until its installed integrity-reader and filesystem boundaries are
identified; the names of its two volume instances do not decide that split.
No declaration grants an exemption, accepted executable status or completion credit.

Before implementing this connection, land this predicate: the fixed policy has a
closed versioned shape, unique declarations and exact runtime-request membership;
missing, extra, duplicate or unknown-route declarations refuse before publication.
Every runtime artifact remains in the record, with route-specific missing-evidence
blockers and its executable owner. Every route still refuses, and the generation
always has `production_admission: false`, `generation_accepted: false` and
`decision: refused`. No policy entry, complete fixture metadata, executable status
or supplied success flag creates a passing release or admission check. Replaying
an older schema requires regeneration rather than interpreting it as admission.

Focused acceptance uses the existing synthetic complete product/build fixture.
It checks all four routes, inapplicable certificate/tier declarations on release
members, explicit unresolved members, full census preservation and deterministic
replay. Independent missing/extra/duplicate/unknown-role controls must preserve a
prior output. Policy/register substitutions and drift after the build join or
before publication must invalidate the record; policy/register output aliases,
including hardlinks, must preserve consumed bytes. A forged route, blocker or
success flag in a saved record must fail exact recomputation. These controls
qualify input binding and obligation routing only. Actual release proofs, complete
standalone products, the role split, TAL/CIC checking, source correspondence,
authenticated current state and final target/image acceptance remain open.

### Contained supervisor and trusted lifecycle split

The `supervisor` declaration uses `checker-admitted` for the non-ASR request
publisher specified by [R-12-073 and R-12-074](../../requirements-register.md#1213-service-manager),
with R-06-001/R-06-023 closing TCB membership. Its trusted lifecycle effects remain
part of the `kernel` declaration's `tcb-release` route. The
[context-slot contract](supervisor-context.md#placement-and-publication) fixes
the authority boundary: the publisher can write its scalar request slots and
read the separate acknowledgment, snapshot and immutable manifest, without
holding saved contexts, roots or kernel-private lifecycle state.

The [declared supervisor source inventory](../../../tools/composer/packages/supervisor.json)
contains the planning core and
[nonblocking publisher](../../../supervisor/src/context.c#vos_supervisor_context_step)
with their headers. The publisher writes scalar start/retire requests; it does
not call trusted effect callbacks. The
[kernel decoder](../../../kernel/src/lifecycle.c#vos_kernel_lifecycle_prepare)
validates those requests before
[kernel-owned retirement](../../../kernel/src/effects.c#vos_kernel_retire) and
root installation. The existing
[component image constructor](../../../tools/vos/lifecycle_target.py#source)
places kernel and supervisor streams in separate bounded text regions, gives
only the kernel system-register authority, and supplies the publisher with
read-only manifest/acknowledgment capabilities and a writable request capability.
These source and component boundaries support the route decision; they are not
a proof of the final installed package's contents or authority.

Before production admission, M7.1a/b/d must export the complete contained
supervisor population and its actual installed authority with that same split.
The privileged boundary consumer and the synchronous effects comparison seam
cannot be relabeled as contained supervisor code. A shared component image is
not a standalone supervisor artifact. M7.1c still requires its assigned tier,
actual derivation and TAL/CIC consumers, source correspondence and final-image
binding. A missing or violated boundary withholds acceptance; it cannot move
the supervisor into the exhaustive TCB or extend the kernel's release verdict.

For this bounded policy change, acceptance requires the reviewed policy to route
the supervisor to `checker-admitted` and the kernel to `tcb-release`, retain
every runtime member, and preserve the existing whole-generation refusal.
The existing complete-metadata and missing-evidence controls must now exercise
the supervisor's admission blockers as well as the copy service's, while saved
records with the old policy or forged release routes fail exact replay.
This completes the route decision only; installed-boundary evidence remains a
producer join rather than a new policy success flag.

### Storage role decision still owed

R-06-005 assigns the small system-integrity reader and A/B transactor to the TCB;
R-06-006 leaves the entire four-layer filesystem outside it for both system and
user data. Consequently `system-integrity` versus `user-data` is not the
trusted/untrusted boundary. Both volumes' filesystem implementations remain
contained, and a volume label alone cannot exempt either implementation from
admission.

The [current combined source inventory](../../../tools/composer/packages/storage.json)
and [publication checkpoint](../storage-recovery-policy.md#early-executable-publication-checkpoint)
join node/tree codecs, updates, recovery and resident verification. The
[resident verifier](../../../storage/src/storage_publish.c#vos_storage_verify_resident)
checks a digest and membership through its store and crypto context; that
context does not establish an independently protected signed boot-root reader.
The inventory's transactor statement likewise supplies no separate installed
transactor. M5.3d/M5.4 and M7.1a/d must identify complete installed populations,
entries, roots and call/wiring boundaries for the contained filesystem and
trusted integrity-reader/transactor, with the latter's independent signed-root
and anti-rollback enforcement. M7.1c then reviews their individual proof routes
and evidence obligations. Missing implementation or separation returns to those
owners for scope and pricing before construction. Until that handoff exists,
the combined `storage` slot retains `unresolved` and its explicit blocker.

## First executable case and acceptance

1. Freeze one eligible post-bootstrap roster member's complete emitted instruction
   population, installed-object export, assigned tier and certificate inputs. Select the
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
