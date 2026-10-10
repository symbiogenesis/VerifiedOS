# Backup and device-migration contract

This is Q42's contract for [R-10-038 through R-10-040](../../spec.md#r-10-038).
It defines the object, export and restore boundary, holder actions and selected
migration construction. The [register](../../requirements-register.md) owns the
obligations. No backup service, trusted screen, Narcissus descriptor, migration
implementation or migration protocol theorem is accepted by this document.

The implementation owners are Q42a (object and export/restore service), Q42b
(trusted screens) and Q42c (migration session). Their entry and exit predicates
are in section 8; their sole estimate cells belong in the
[checklist](../implementation-checklist.md). M5.3d retains the verified storage
and user-data-instance join, the credential and consent owners retain their
existing mechanisms, and M6.9 retains its TLS and attestation foundations.

## 1. Export boundary and fixed-tier placement

**BM-EXPORT.** A backup exports one explicitly selected source profile at one
committed quiescent checkpoint, through the verified L0/L1/L2 path. The source
generation's manifest supplies a finite ordered catalog of typed rollbackable
durable regions. The export snapshot fixes their schema identities, generation
and lengths together; a live partially updated region is never sampled. The
holder chooses the untrusted destination through an attenuated storage handle;
the destination receives one opaque sealed object and no plaintext region.
An interrupted destination write can leave an unusable opaque prefix, never a
backup reported as complete. Applications supply no serializer or recovery code.

The conceptual source interface is:

```text
ExportView<profile, generation> =
  finite catalog of SnapshotRead<Rollbackable, DataOnly<schema>>
encode_regions : ExportView -> CanonicalRegionBytes
seal_backup : BackupKeyHandle x CanonicalRegionBytes -> OpaqueBackup
```

`DataOnly` is closed recursively over bounded scalars, byte arrays, products,
closed variants and bounded collections. It has no pointer, capability, validity
tag, sealed-handle, credential-handle, key, nonce-state, execution-state or
connection/device-state constructor. A manifest's region kind and schema, rather
than a runtime field filter, determine the view. The catalog construction has no
operation for `SnapshotRead<Fresh, _>` and no store capability for the
consent-record store. Integer names never become authority on restore. A schema
claiming `DataOnly` while interpreting its bytes as one of the excluded classes
fails manifest/schema review and admission; retyping excluded state as bytes is
not an escape from [R-10-037](../../spec.md#r-10-037).

The service's composition graph grants region reads only through this view and
grants the crypto core a separate, bounded backup-key operation. The serializer
has no transitive capability path into the crypto core's keys, protocol-credential
broker, RoT/measured-state sealed objects, consent store or any `Fresh` region.
Its proof and installed-holder audit quantify over schema nesting, imports,
aliases and every delegated read path. The key handle is never an element of the
view or the serialized object. Passing that handle to the sealing operation does
not authorize a key read by the exporter.

The required implementation mutant is **`backup-export-reads-fresh`**: add a
`SnapshotRead<Fresh, _>` to the catalog or a transitive read of a `Fresh` region.
Admission/type checking must refuse that executable candidate; a separately
constructed bypass control must make the behavioral campaign detect the leaked
fresh-state sentinel. Compilation refusal is recorded as a stillborn mutant,
not as a behavioral kill. Equivalent controls cover credentials, consent records
and sealed objects. The positive control exports an ordinary rollbackable edit.

**BM-PLACE.** The export/restore service, backup-key custodian, migration endpoint
and trusted screens occupy the fixed tier under
[R-07-037f](../../spec.md#r-07-037f). They hold a platform secret, serve storage or
network sessions, or belong to the trusted path. The key remains crypto-core
resident except for the explicit holder recovery display or protected recipient
transfer in section 3. Manifests declare served labels, secrets, deadline classes,
device authority, maximum object/region extent, staging capacity and scheduled
work bounds. Composition refuses an elastic placement or insufficient whole-object
authentication/staging capacity; it does not borrow another label's memory or
slack. Per-label service instances or a reviewed cross-label non-interference
interface retain the ordinary storage confidentiality boundary.

## 2. Object descriptor and canonicity

**BM-FORMAT.** `BackupObject-v1` names a Narcissus descriptor family, presently
absent, to be realized by Q42a after the parser prerequisites qualify. It has the
following nonrecursive forms. The fixed order shown is part of the grammar.

| Id | Fields in wire order | Bounds and interpretation |
| --- | --- | --- |
| `backup-envelope-v1` | magic, version, descriptor-profile identity, ciphertext length, fresh sealing nonce, ciphertext, authentication tag | Magic and version have one literal encoding; profile selects one composition-fixed descriptor and AES-GCM configuration, never cipher negotiation; exact total extent and no trailing bytes |
| `backup-plaintext-v1` | exporting generation identity, source profile identity, region count, region records | One source profile and one exporting generation; count and total size bounded by the composed profile |
| `backup-region-v1` | region identity, schema identity, schema generation identity, payload length, canonical typed payload | Records strictly ordered by region identity, no duplicate; schema generation equals the exporting generation's declared catalog entry; payload exactly the schema extent |

All scalars have one fixed unsigned big-endian representation. Identity widths,
count/length widths and maxima are constants of the descriptor profile emitted
by the admitted generation, not numbers accepted from a remote manifest. Each
schema identity binds its canonical bounded serializer and the source manifest's
declaration. This contract fixes the grammar shape; choosing concrete widths and
limits, compiling the descriptor and proving their fit is Q42a's entry artifact
before service code, not an invented production profile here. No optional field,
reserved flag, extension bag, padding, path, raw address or executable image occurs.
Different descriptor-profile versions are different grammars and are never
interpreted by fallback.

The AEAD plaintext is the complete `backup-plaintext-v1`. Associated data is a
domain separator for `BackupObject-v1` and the complete canonical envelope prefix
through the nonce. Every identity, region position, schema and payload is thereby
authenticated. The nonce is newly generated sealing metadata, never a restored
source nonce or exported DRBG state. AES-GCM uses a newly drawn 256-bit key for
each object and one sealing invocation; a retry gets a new key and nonce, never
reseals changed bytes under a reused pair. Limits meet the selected AEAD's bounds.
The tag's wire width and nonce width are fixed by the at-rest crypto profile;
Q42a must bind the actual crypto-core interface and refuse absent parameters.

Q42a owes the correctness pair and, independently, whole-admissible-language
canonicity for the envelope, plaintext, records and identity-consuming nested
schemas. For each descriptor `D`, the checked statement includes
`decode_D(encode_D(v)) = Some(v)`, and for every accepted complete byte string
`b`, `encode_D(decode_D(b)) = b`; consequently two accepted byte strings decoding
to one value are identical. Ciphertext and nonce bytes are part of the envelope
value; the theorem does not identify two randomized encryptions as the same
envelope. Alternate length forms, record permutations, duplicate identifiers,
ignored tails and noncanonical nested schema encodings fail decoding. A decoder
does not normalize them. Authentication does not substitute for canonicity.

The descriptor is a `CJ-FORMAT` member under R-05-046, enumerated in the authored
[wire-format inventory source](../../../interfaces/wire-formats.json) under
`backup-object`, with descriptor status `absent`, owner `Q42a` and an owed
canonicity theorem. Its generated inventory entry must link here and enumerate
the three forms above. The contract and descriptor receive independent
R-05-150 review. [The parser workflow](../../assurance/proof-reuse/parsers.md)
and [U-13/U-14](../../assurance/unassigned-proof-map.md) retain locked-prover
qualification, correctness, assumptions and copy-once Fiat/Bedrock-to-Clight
lowering. A hand-written reference codec cannot be promoted to a shipped parser.

## 3. Backup key and trusted holder actions

**BM-KEY.** The platform's approved DRBG supplies 256 bits with at least 256 bits
of entropy to the crypto core's new-object key operation. Entropy-path failure
refuses export; no credential, object hash, time or user-chosen phrase substitutes
for the draw. The primary credential gates the act, never derives the key. No
vendor, service or escrow party receives a share or opening capability.

For the display route, `RecoverySecret-v1` represents all 32 key bytes as exactly
64 uppercase hexadecimal digits, shown in sixteen four-digit groups on the
trusted path. The spaces are display separators; the data encoding is the exact
64-digit string, with no alternate case, Unicode lookalikes or omitted leading
zeroes. Q42a owns its bounded Narcissus descriptor and correctness/canonicity
pair, inventoried as `backup-recovery-secret`; Q42b uses that decoder on the
trusted entry path. An app-supplied string parser cannot replace it. Restore
entry validates the exact syntax and length; the object tag detects a wrong key.
Encoding supplies no additional entropy
and no human phrase is hashed into a key. The trusted agent shows it once per
new object after credential verification and consent, supports explicit recording
and confirmation in that one display lifetime, and clears the display and secret
buffers on completion, cancellation, lock or fault. It has no later redisplay,
clipboard, screenshot, app callback, diagnostic log or network-output API.
Loss of the secret without an enrolled recipient means loss of recovery.

For the enrolled-device route, the holder unlocks both devices and enrolls a
second RoT through a protected, recipient-scoped context. Q42c's construction
below uses the distinct `backup-key-enrollment` role and an enrolled recipient
identity policy, with source-side confirmation of the authenticated quoted roots.
The source crypto core transfers the key only inside that accepted session to the
receiving crypto core. The second RoT wraps it under its own local sealing policy,
binding the enrolled recipient, object identity and use `backup-restore`; the
protocol broker exposes only that bounded import/open operation. The resulting
sealed handle stays on the second device and is excluded from every backup.
No capsule carrying the key is emitted alongside the object to untrusted storage.
The delivered key is an explicit recovery channel, not an exported protocol
credential or source volume key. A generic public-key signature or caller-supplied
recipient key does not enroll a RoT. Real recipient identity, wrapping, custody
and lifecycle bindings remain Q42c's acceptance obligations.

**BM-CONSENT.** Export and restore separately require a live primary-credential
verification and a one-use trusted consent witness bound to operation, unlocked
local profile, source object or snapshot identity, destination selection and
discard/migration plan. Witnesses expire on lock, restart, profile/generation
change or completion and cannot be replayed or supplied by an application.
The screens clearly label backup, user-data restore and device migration as
separate acts from system-generation rollback. Restore explicitly warns that
rollbackable edits return to the selected checkpoint and surrender freshness.
Export states R-17-054a's off-device trade before consent. Cancellation before
the commit point leaves the profile unchanged. Storage selection and protocol
connection alone never manufacture consent.

## 4. Authenticate, plan, then write beside existing state

**BM-RESTORE.** The receiver starts from its own measured boot, manifest-built
compartments and ordinary initialization. It does not resume saved execution,
install the exporting generation or change the receiving RoT's roots, lifecycle,
anti-rollback floor, credentials or monotonic counters. Credential/unlock gating
and consent precede import; possession of the recovery secret alone cannot enact
a restore on a locked device.

The restore state machine is `Idle -> Authorized -> Authenticated -> Planned ->
Staged -> Committed`, with failure/cancellation going to `Discarded`. Before
`Planned` there is no region-store write authority. Complete untrusted bytes may
be held in bounded volatile quarantine, not persistent import storage. First
validate the bounded canonical envelope extent and fixed profile, then authenticate
the whole ciphertext, then decode the complete plaintext and region catalog, and
then validate every schema and the complete destination plan. No streaming prefix
is installed and no authenticated prefix authorizes a region write.

The intended source profile and object identity are supplied by the holder's
trusted selection, not learned as authorization from untrusted object fields.
After authentication the named profile must match that intent. An explicit
trusted source-to-local profile mapping permits a holder's same profile to move
to a newly personalized device; it is bound into the consent witness and imports
no profile credential or authority. A foreign-profile object or destination
substitution without that binding is refused. A correctly authenticated older
backup of the intended profile may be chosen deliberately; the format supplies
no off-device freshness claim.

For each region, the receiving generation's immutable plan chooses exactly one:

| Plan arm | Decision before staging | Result |
| --- | --- | --- |
| Same schema | Exact supported schema/generation mapping and canonical typed decode | Copy typed data into a new receiving namespace |
| Checked migration | Receiving generation carries admitted code and a checked source-to-target schema relation; bounded migration succeeds | Write the new typed schema beside the old |
| Discard | Receiving generation explicitly declares this unknown/obsolete schema discardable and the holder confirms its listed data loss | Import no bytes for that region; use ordinary initial state |
| Unsupported | No exact codec, checked migration or explicit approved discard plan | Refuse the entire attempt; zero region writes |

An unknown schema initially takes `Unsupported`. The implementation cannot silently
discard it to convert a negative case into success. The holder may start a new,
clearly labeled attempt with an explicit receiving-generation discard plan; that
plan identifies the authenticated region/schema and skips its bounded opaque bytes
without reinterpreting them. This reconciles R-10-038's migrate-or-discard rule
with the requirement that the original unsupported-schema attempt writes nothing.
All source schemas and dispositions are decided before any region is staged.

Staging writes the complete new profile state beside the current state in the
verified stack, preserving the prior namespace, root and index byte for byte.
Publication is one L0 journal transaction. The commit witness binds the source
object, receiving generation, profile map and complete plan, and is consumed
exactly once. Crash cuts before publication reopen the original profile; after
publication they reopen the complete new profile. A migration, allocation,
authentication or publication failure cannot expose a partly restored profile.
Unpublished staging is unreachable and removed by the existing crash-safe cleanup
path; it never overwrites existing state. Failed cryptographic/schema/profile
cases never reach staging and perform zero region writes at all. Target campaigns
must distinguish those zero-write refusals from a later failure that abandons
unpublished staging while preserving all existing reachable bytes.

## 5. Fresh initialization and authority after restore

**BM-FRESH.** Every receiving manifest declares an admitted fresh-install
initializer and activation condition for every `Fresh` region. The catalog below
covers R-10-013b's examples and R-10-039's superseded revocation list; it is not
a closed feature list. Each row applies to a region its manifest declares `Fresh`;
the construction never promotes a rollbackable region or demotes a Fresh one.
An additional `Fresh` region without an initializer and
its denial case fails composition. Initializers read no backup bytes, stay within
the receiving epoch quota and become visible only under the receiving device's
freshness seal. Existing low-rate platform state and the credential/unlock service's
attempt limiter are not replaced by profile restore.

| Fresh state class | Fresh-install state on the receiving device | Required denial case |
| --- | --- | --- |
| Spent-payment ledger | Unenrolled payment namespace with no spend authority; a newly enrolled relying party must reconcile authoritative account state before spending | A restored balance or pending payment cannot confer value or resend a payment |
| Consumed-token/revocation list | New unenrolled token namespace, no accepted old token; authenticate current relying-party state before activation | An old token, including one absent from the new empty ledger, is refused |
| One-time operation completion marks | New operation namespace, no inherited completion or retry authority; reconcile external effects before enabling a repeatable action | A rollbackable pending job cannot replay its previous non-repeatable effect |
| Application attempt counter | Owner's locked, unenrolled fresh-install state; retries disabled until new enrollment establishes the receiving policy | Restore cannot reset an existing identity's limiter or admit another guess under it |
| Superseded revocation list | No authoritative list until a current authenticated source supplies one under the newly enrolled scope | Missing/currently unverified revocation state denies the operation rather than accepting the backed-up list |
| Other owner-declared Fresh state | Exact manifest-declared fresh-install state with a new scope or a deny-until-reconciled activation guard appropriate to its staleness property | The owner's concrete spent/revoked/limited witness remains refused after restore |

These are obligations on the receiving initializer, not a claim that an empty
list proves past tokens unspent. Existing-profile restore replaces only the
selected rollbackable regions and constructs new profile-owned fresh state under
these guards; it does not zero a continuing platform counter or turn a previously
spent external identity into a fresh identity. If the owner cannot construct that
safe fresh-install scope, restore refuses before publication. Recovery of old
external account continuity requires the relying party's current state, never
the backup. Protocol credentials are re-enrolled with their relying parties;
the portability cost [R-12-020](../../spec.md#r-12-020) remains.

The consent-record store is independently excluded from backup: under R-10-037a
it is neither a checkpoint nor capability-bearing state, and R-10-013b separately
classifies it Fresh by declaration. A restored profile has an empty new-profile
consent store, no imported decision and no grant in force. Ephemeral grant
authority is re-derived or withheld, not classified as a Fresh durable region.
The receiving revocation epoch stays current and new grants require new trusted
consent; an old record, decision or revoked grant cannot restore access. Fresh
initialization/staging must keep all prior receiving Fresh versions verifiable
until publication, including when a new namespace is abandoned, and reserve the
required epoch quota and staging extents at composition. Advancing the seal must
not invalidate the untouched current profile or reset a continuing counter.

Manifest authority is re-derived as on restart, from the receiving manifest and
current revocation epoch. The excluded consent store restores no past act, so
the persistent-grant exception of R-10-037a cannot authorize an imported grant.
No backup contains execution state, capabilities/tags, keys, DRBG state or source
nonces, leases, consent grants/powerbox decisions, connection/session/device state,
protocol credentials or anything sealed to RoT/measured state.

## 6. Selected device-migration session and reference model

**BM-SESSION.** `MutualMigrationTLS-v1` is the selected construction under
R-12-015c, with reference-model specification `MigrationSession` in this section.
It extends the [Q22c TLS application binding](../../assurance/session-binding-qualification.md)
to mutual appraisal and a source-side receiver-root confirmation. Q42c must
realize and mechanize this member of `CJ-ATTEST`. The existing
[AttestedSession.v](../../../proofs/AttestedSession.v) proves a conditional
one-direction symbolic relation, not this mutual migration contract or its
cryptographic realization. The migration model/theorem and implementation
connection are open until their own evidence lands.

Use one full server-authenticated TLS 1.3 connection in the composition-fixed
hybrid configuration. No resumption, early data, renegotiation of the configuration
or multiplexed attestation lifecycle is admitted. Its initial receiver origin
and trust policy come from the trusted enrollment/selection ceremony; discovery
traffic supplies no origin authority. Each endpoint challenges the other only
after handshake completion, with its own approved-DRBG nonce and a bounded
monotonic deadline, accepting each challenge once. Domain and roles are
`device-migration`, `migration-source` and `migration-receiver`; recovery-key
enrollment uses its distinct role and receives no region-transfer permission.

The complete challenge/evidence/confirmation transcript binds both roles and
principals, origin, both fresh challenges, the protected local TLS exporter, both
running-generation identities, authenticated reference-manifest identities, the
source-profile identity, receiving profile map and schema-plan identity, and the
receiver's quoted enrolled root set. The exchange order is fixed: exchange bounded
challenges and proposed schema/profile catalogs with no region payload; obtain
the receiver's protected quote of its own measured generation and roots; appraise
it on the source; obtain the source's protected quote of its own measured
generation plus the accepted receiver-quote identity and context; appraise it on
the receiver; exchange channel-authenticated mutual acceptance; then confirm the
roots on the source before granting transfer. Local measurements are read from
the issuing context rather than guessed from a peer announcement. The final
transfer authorization binds both accepted quote identities and the complete
mutual context, so the stages cannot be mixed between attempts.
The source must authenticate the roots as the receiver's current device-register
claim, not trust a text list or a source-generated label. The source's trusted
screen shows the complete quoted set (stable key fingerprints and authenticated
names where available), its generation and the selected receiving profile.
The holder confirms that exact set and channel on the source and presents a
primary credential on both devices. Every required root remains inspectable; an
unbounded/unrenderable set refuses rather than truncating the confirmation.

The broker reads generation, roots, principal and exporter only from the
protected local measured/TLS context. A caller cannot supply an exporter, arbitrary
key or measurement; its bounded credential operation is role-, peer-, scope-,
transcript-, use- and expiry-bound as R-12-015a requires. Public exporter equality
alone is no key custody. Crypto-core ownership of that actual TLS traffic-key
context, protected quote issuance and authenticated appraisal jointly bind each
accepted measured peer to the session key holder.

The migration policy appraises software plus the authenticated current root-set
claim; it does not require a globally linkable unit identifier and does not
identify a particular die from software alone. An alternative correctly measured
device with acceptable roots may pass that policy only if the holder confirms
its actual quoted roots on this channel. For a previously enrolled recovery-key
recipient, the policy additionally checks the recipient-scoped enrolled identity.
This is an explicit unit policy choice and requires its enrollment premise.

### MigrationSession state and event relation

The model's endpoints are the two measured fixed-tier migration principals and
their crypto-core contexts, not a cable or the human. The wire is adversarial.
The state is a finite set of attempts keyed by protected connection identity;
each carries endpoint/role/policy/generation, the two challenge values and
deadlines, authenticated evidence and issuance events, the receiver root set,
holder credential witnesses, one-use source consent witness, the immutable
schema/profile plan, transfer key ownership and restore phase.

| Event | Preconditions and transition |
| --- | --- |
| `Open` | Full admitted TLS context and selected origin; create fresh pending challenges; no payload authority |
| `Quote` | Correct local protected context and bounded credential operation; read actual measured fields/exporter, consume one credential use |
| `Appraise` | Authentic issuance, exact fresh challenge/role/context, timely one-use decision, allowed running generation/reference manifest and declared identity scope; decide once in each direction |
| `ConfirmRoots` | Both appraisals succeeded; source trusted path obtains holder consent to the authenticated receiver roots, connection and transfer plan, with credential verified on both devices |
| `Transfer` | Both appraisals, both credential witnesses and exact live confirmation hold; mint one object key, send sealed `BackupObject-v1` and key on this connection only |
| `PrepareRestore` | Authenticate the whole object and all schemas/profile/plan; take section 4's zero-write refusal or prepare the complete new namespace |
| `Publish` | Complete staged state and all current witnesses match; atomic restore commit; consume transfer authorization |
| `Close` | Completion, any failed check, deadline, cancellation, lock, restart, generation/roots/lifecycle change or key-context retirement; clear transient bytes/keys and revoke all attempt authority |

The target relation is: every `Transfer` has distinct prior authentic issuance
and successful appraisal for both live connection holders at the stated running
generations, unconsumed fresh challenges, primary-credential witnesses for both
and a source holder's confirmation of exactly the receiving context's roots and
plan. Every `Publish` additionally has a whole-object authenticated complete
schema plan and the atomic preservation property of BM-RESTORE. The model must
construct an inhabited successful joint trace as well as traces rejected by each
precondition; a model that refuses all migrations fails acceptance.

The backup key is a separate confidential control message bound to this transfer,
not plaintext in the backup payload, not a protocol credential and never a
recovery screen. The complete sealed object can reside only in reserved volatile
transfer buffers before authenticated restore. No backup object, key capsule or
recovery secret is written to source, destination or intermediary storage; the
destination's normal authenticated durable regions after commit are the intended
result, not a retained migration object. A composition unable to reserve the
bounded volatile extent refuses; it does not spool the object to storage.

### Qualification and explicit premises

Q42c's independent event oracle reads actual issuance/context provenance, never
a claimed peer field, and compares success and refusal against the relation.
Required cases are replayed/expired evidence, challenge reuse after restart,
parallel sessions (including repeated nonce symbols), reflected source/receiver
roles, a substituted exporter or roots list, another unit with identical software,
wrong enrolled recipient, a transparent relay and a relay terminating two TLS
legs. Transparent forwarding to the same authenticated holders may succeed and
confers no key authority on the relay. Endpoint substitution must fail unless the
declared software policy and the holder's actual confirmation authorize that
endpoint. Root confirmation alone cannot waive failed appraisal.

Named premises are the selected TLS and hybrid-crypto security, exporter integrity,
fresh entropy, evidence/manifest authenticity, faithful measurement and root-set
reporting, protected local context ownership, honest trusted-path/credential
services and uncompromised keys for the claimed interval. Attestation is a
point-in-time claim: runtime compromise of a legitimate measured holder, exposed
session keys, a compromised RoT/issuer or a compelled mistaken confirmation can
produce an accepted attack outside the honest premise conjunction. Q42c records
those attacks rather than claiming to block them; the model's privacy and
faithfulness and implementation-to-model connection remain review obligations.
Missing evidence or binding closes the attempt with no weaker fallback, while
both devices continue running their own generations. Withholding traffic denies
the migration service and nothing here prevents that availability cost.

## 7. Acceptance cases and requirement mapping

The following are implementation acceptance cases, not results of this contract
landing. Each refusal observes both a zero region-write trace and unchanged
current-profile root/index/bytes unless the row explicitly describes post-staging
failure. A destination-storage prefix from failed export is never reported valid.

| Case | Concrete witness and required observation | Owner |
| --- | --- | --- |
| `BA-EXPORT` | Two rollbackable regions at one quiescent committed checkpoint round-trip with exact profile, generation, schema and values; untrusted destination sees only one opaque AES-GCM object | Q42a |
| `BA-TYPE` | Installed export graph and recursive DataOnly schema reach only rollbackable regions; Fresh-reading, key/credential, sealed-object and consent-store controls are refused at admission or detected by the bypass campaign | Q42a |
| `BA-FORMAT` | Narcissus pair and independent whole-language canonicity, bounded copy-once target decoder and exact inventory binding; alternate encodings/duplicate records/trailing bytes are rejected | Q42a |
| `BA-KEY` | DRBG/crypto interface constructs the full-entropy 256-bit one-object key; entropy failure stops export, credential-only derivation and escrow paths are absent; retries never reuse the key/nonce | Q42a |
| `BA-DISPLAY` | Exact leading-zero recovery secret round-trips; one trusted display lifetime, credential plus one-use consent, cancellation/lock clear; no app-visible secret/log/output | Q42b |
| `BA-WRAP` | Both unlocked enrolled devices accept the protected recipient context, import one backup key and retain only the recipient-bound locally sealed handle; unenrolled/wrong recipient or unconfirmed roots receive no key | Q42c |
| `BA-OBJECT-REFUSE` | Truncate at each field boundary; permute records; substitute profile, generation, schema, payload or tag; append a tail; change descriptor profile; use a wrong key or a valid foreign-profile object | Q42a: zero region writes |
| `BA-SCHEMA` | Unsupported source schema with no checked migration or explicit discard plan refuses with zero writes; a new confirmed discard attempt imports no bytes for that region; a checked migration and unchanged-schema arm each succeed | Q42a/Q42b |
| `BA-ATOMIC` | Target crash/failure at every staging/publication cut; prior state remains byte-identical before commit, complete new state after; post-staging failure leaves only unreachable cleanup state | Q42a |
| `BA-FRESH` | Each section 5 initializer has a successful receiving-device witness and its old spent/revoked/token/attempt replay witness; no old authority activates, platform counters stay current and missing initializer refuses | Q42a with each manifest owner |
| `BA-CONSENT` | Missing/wrong credential, forged/replayed/expired consent, locked device, profile/plan change and app-rendered prompt refuse before region writes; user-data restore labels and caveats are visible | Q42b |
| `BA-MIGRATE` | Inhabited mutual-appraisal/dual-credential/confirmed-roots trace transfers the same excluded-state-free sealed object and key, restores atomically, displays no secret and retains no object on storage | Q42c/Q42a/Q42b |
| `BA-TARGET-REFUSE` | Target evidence absent, invalid, stale or not appraised; roots substituted, changed, truncated or not confirmed; source appraisal fails or either credential missing | Q42c: no region or key transfer and zero receiving region writes |
| `BA-SESSION` | Section 6 replay, concurrency, role reflection, endpoint and relay cases plus broken-premise/key-compromise witnesses classified against the explicit relation; exact implementation context/bytes match the model | Q42c |
| `BA-RESIDUAL` | Export consent states the off-device protection boundary; restore of an old authorized rollbackable backup remains possible after source lock or erase given the secret | Q42b/Q42a |

| Register criterion | Contract clause | Acceptance case |
| --- | --- | --- |
| R-10-038 main: unlocked holder; rollbackable typed profile regions; verified stack; one opaque object on chosen untrusted storage | BM-EXPORT, BM-PLACE, BM-CONSENT | BA-EXPORT, BA-TYPE, BA-CONSENT |
| R-10-038 main: whole-object authentication and every-schema check before writing, beside existing state, failure preservation | BM-FORMAT, BM-RESTORE | BA-OBJECT-REFUSE, BA-SCHEMA, BA-ATOMIC |
| R-10-038 key acceptance: DRBG entropy, once-displayed or enrolled-RoT-wrapped recovery, no credential-only derivation or escrow | BM-KEY, BM-CONSENT | BA-KEY, BA-DISPLAY, BA-WRAP |
| R-10-038 format acceptance: descriptor/canonicity/inventory; exporting generation/profile/every schema; truncate/reorder/substitute/foreign-profile refusal; migrate or discard | BM-FORMAT, BM-RESTORE | BA-FORMAT, BA-OBJECT-REFUSE, BA-SCHEMA |
| R-10-038 retained-replica acceptance: at-rest AES-GCM, 256-bit symmetric key, stored-secret horizon, off-device residual | BM-KEY, section 9 | BA-KEY, BA-RESIDUAL |
| R-10-039 main and construction acceptance: full checkpoint exclusions plus protocol credentials, sealed objects, consent store and Fresh excluded by reachability | BM-EXPORT, BM-FRESH | BA-TYPE, BA-FRESH |
| R-10-039 restore acceptance: fresh-install state, no spent/token/attempt/grant/revocation resurrection, authority re-derived and protocol credentials re-enrolled | BM-FRESH, BM-RESTORE | BA-FRESH, BA-ATOMIC |
| R-10-040 main: mutually appraised running generations, named construction/model, holder credential on both, key inside session, no recovery secret or stored object | BM-SESSION, BM-CONSENT | BA-MIGRATE, BA-SESSION |
| R-10-040 target acceptance: appraisal plus holder confirmation of quoted enrolled roots; identical sealing/schema/exclusion boundary | BM-SESSION, BM-FORMAT, BM-EXPORT, BM-RESTORE | BA-TARGET-REFUSE, BA-MIGRATE, BA-TYPE, BA-SCHEMA |

## 8. Implementation-owner predicates

**Q42a · Implement the backup object and export/restore service. Start:** this
contract and a concrete bounded descriptor profile; accepted Narcissus
qualification and U-14's measured descriptor path; the typed manifest/checkpoint
and schema-migration interfaces, the at-rest crypto core and M5.3d user-data
instance. Missing parser, crypto, freshness or storage foundations retain their
existing owners and estimates. **Owns:** this object's descriptors/pairs/canonicity
and lowering, the closed export view and holder audit, one-object key/nonce
interface, bounded fixed-tier export/restore state machine, schema/discard plan,
fresh initializer joins and crash-safe atomic publication. **Check:** BA-EXPORT,
BA-TYPE, BA-FORMAT, BA-KEY, BA-OBJECT-REFUSE, BA-SCHEMA, BA-ATOMIC and BA-FRESH
on the real bounded source and target path, with exact source/configuration/image
identities, required proof/assumption/kernel evidence and negative controls;
reference serialization alone does not pass. **Join:** M5.3d, manifest owners,
Q42b and Q42c, then Q10's product judgment.

**Q42b · Implement the backup and migration trusted screens. Start:** this
contract, existing credential/unlock and trusted consent services, and Q42a's
operation/profile/plan identities. **Owns:** separate backup/restore/migration
flows, canonical recovery-secret entry and one-time display, explicit discard
loss and surrendered-freshness caveats, source confirmation of the exact quoted
root set, and one-use operation witnesses. **Check:** BA-DISPLAY, BA-CONSENT,
BA-RESIDUAL and its side of BA-SCHEMA/BA-MIGRATE with real trusted-path input and
output, spoof/replay/cancel/lock controls and no secret reaching an app or log.
**Join:** Q42a and Q42c through the existing trusted consent path's owner; no
new screen is accepted from a mockup or a textual consent record alone.

**Q42c · Realize and prove the migration session. Start:** this contract's
MigrationSession relation, accepted bounded TLS/attestation/credential/context
interfaces and M6.9/U-20 cryptographic foundations; Q42a's complete volatile
object extent and Q42b's channel-bound witnesses. **Owns:** canonical bounded
migration/challenge/evidence/key-transfer record descriptors, mutual protocol
realization, the MigrationSession mechanization and inhabited success/refutation
witnesses, exact conditional session-agreement theorem, computational argument
at the already owned foundations, receiver enrollment/key wrapping and actual
context/custody/teardown/restore joins. Its descriptor entries remain absent until
their individual proof and parser evidence exists; upstream TLS evidence alone
does not cover these new application records. **Check:** BA-WRAP, BA-MIGRATE,
BA-TARGET-REFUSE and BA-SESSION on the exact protocol and target artifacts,
including the declared relay and compromise cases, complete assumption audit
and kernel gate, and storage-write observations proving no retained migration
object. **Join:** Q42a/Q42b, the M6.9 context/attestation implementation and
proof owners, and the CJ-ATTEST inventory. An inherited one-direction symbolic
theorem or a finite host fixture alone closes none of this predicate.

## 9. Off-device residual and evidence scope

[R-17-054a](../../spec.md#r-17-054a) is booked, never closed here. The duress
erase cannot reach an exported copy; device lock and the credential rate limiter
do not defend it. Anyone who obtains the recovery secret can open everything the
backup carries, including through coercion or careless custody, with the chosen
storage supplying its own protection and availability. Taking a backup trades
future irrecoverability after device erase for recovery after loss; taking none
retains the original limits. Credential gating and consent limit who exports,
not who later opens a copy. Recovery-secret encoding and strong random keys
provide no coercion or holder-intent theorem.

The retained replica uses the at-rest AES-GCM stack under its 256-bit symmetric
key over R-17-049g's stored-secret horizon; opening that opaque object requires
no public-key operation. The enrolled-recipient/session route has its separately
stated TLS, attestation and wrapping assumptions and does not erase them by
describing the object as symmetric. This contract supplies design and acceptance
predicates only. Implementations, target campaigns, descriptor/protocol theorems,
physical key custody and independent specification review remain with the named
owners and their existing gates.
