# Session-attestation qualification

This document carries one part per selected attestation-session construction under
R-12-015c, each a named member of the crown-jewel row that entry confers. A part
states its construction, its binding, its assumptions beside what they exclude, and
the finite classifications [the model](../../tools/vos/session_binding.py) decides;
none states a protocol theorem, and the parts share one command and one receipt.

## The TLS 1.3 application binding

Q22c qualifies a candidate binding for the TLS 1.3 service already admitted by
R-12-031/R-12-032. The disposition is to retain this candidate for the separately
priced realization and proof work in M6.9. The executable assessment demonstrates
finite examples of R-12-015c's required relation; the protocol reference model,
machine-checked theorem and implementation connection remain open. The status of
`CJ-ATTEST` remains unauthored in the [crown-jewel inventory](crown-jewels.md).

The [register](../requirements-register.md) owns the obligations: R-12-014/R-12-015
own key custody, quotes and source-reproducible reference manifests; R-12-015a owns
bounded credential operations; R-12-015c owns session binding; R-09-025a separates
software and device measurements; R-17-030y retains service refusal. This assessment
does not narrow R-05-078/R-17-049's TLS composition residual or add an M8a service.

### Selected protocol and application boundary

The candidate uses a complete, server-authenticated TLS 1.3 connection with the
composition-fixed hybrid key-exchange profile required by R-12-031. It sends an
attestation challenge and evidence as application data before opening the protected
application service. It changes no TLS handshake message. Resumption, early data,
post-handshake client authentication and multiplexed authentication instances are
outside this bounded profile; they receive no inherited qualification.

The channel identifier is RFC 9266's `tls-exporter`: label
`EXPORTER-Channel-Binding`, empty context and 32 output bytes, obtained from the
TLS exporter after handshake completion. It is public channel-binding data, never
a secret or an application-record authentication key. RFC 9266 permits only one
authentication mechanism instance per connection and requires closing the connection
when its upper-layer protocol concludes. This candidate therefore gives one
attested application lifecycle one connection, closes it at completion or refusal,
and refuses reauthentication on that connection. These constraints belong to the
[channel-binding standard](https://www.rfc-editor.org/rfc/rfc9266.html#section-2).
The exporter construction itself is the
[TLS standard's responsibility](https://www.rfc-editor.org/rfc/rfc8446.html#section-7.5).

The relying party also acts as verifier in this fixture. It authenticates the
evidence's origin and appraises its generation against a retrieved, authenticated,
source-reproducible reference manifest under its fixed policy. Evidence and its
appraisal are separate judgments, following the
[RATS roles](https://www.rfc-editor.org/rfc/rfc9334.html#section-4.1).
The fixture abstracts manifest authentication and the attestation trust chain as
an ideal authenticated-evidence ledger. A ledger lookup is no implementation of
those judgments, and a successful Python comparison supplies no cryptographic
assumption discharge.

### Claim, freshness and custody

The relying party challenges the client after the full handshake. The challenge
contains a fresh nonce, the relying-party origin, the requested software or unit
scope, and the fixed attestation application/domain identifier. The local sealing
broker emits authenticated evidence containing that challenge, the actual measured
generation, the compartment principal and client-attester role, the local TLS
exporter, and an origin-scoped alias only for unit appraisal.

The credential operation receives a protected local TLS-context handle, not a
caller-supplied exporter or public key. The broker checks that the credential and
context have the same local unit and compartment principal, that the peer origin,
role, operation, scope and domain agree, and that its use and expiry bounds hold.
The broker reads the measured generation and exporter from those protected services;
the application cannot substitute either field. An issued quote consumes one use.
M6.3b owns the handle interface, while M6.9b owes the connection that makes these
protected reads and ownership checks true in the implementation.

The appraiser checks authenticated evidence, exact challenge/context equality,
equality with its own TLS exporter, the allowed generation and principal/role, and
the selected identity scope. Acceptance opens only that connection's application
service. An invalid or absent value closes the attempt and provides no weaker peer
claim. The public exporter supplies connection equality; the issuer's protected
local ownership relation is what connects that equality to the measured key holder.
A credential's role alone supplies neither relation.

Freshness uses a nonce and one outstanding attempt with a monotonic deadline,
following the nonce approach described by
[RATS freshness](https://www.rfc-editor.org/rfc/rfc9334.html#section-10.2).
No security decision needs calendar time, consistent with R-09-013. A production
nonce comes from the approved entropy path; failure follows R-15-241b/R-17-030o.
The issuer authenticates the measured state and the challenge together, and the
relying party accepts at most once before the deadline. Reconnect and restart erase
pending state and require a new full TLS context and fresh challenge. The fixture's
small integer ticks and nonce symbols are experimental inputs, not nonce-length,
collision-probability, deadline or capacity recommendations.

### Peer and compromise assumptions

The intended peer is the client compartment owning the live TLS traffic-key context
on the appraised generation. It is neither the nearest network hop nor necessarily
the person operating the device. The relying party and its appraisal policy are
honest. Server authentication binds the requested origin under the composition's
authorized server-key policy; a time-unknown certificate-validation implementation
is not supplied by this fixture.

In the honest model, TLS creates distinct connection exporter values, authenticates
the server, and keeps client traffic-key custody inside its local context. Evidence
authenticators cannot be forged; attestation trust anchors, measurements, issuer
code and key custody are uncompromised. The credential/context objects and ledger
are abstract trusted state with already typed inputs, not Python security boundaries
or malformed-input parsers. One-shot authentication state belongs to the local
connection context, so reconstructing the appraiser cannot reopen that context.
The attacker may open parallel connections, copy public exporters, relay or withhold traffic, move valid
quotes between connections, and run the same approved generation on another unit.
The experiment's separate event provenance records the actual issuer context; the
verifier does not consult that ghost unit identity when accepting a quote.

Software appraisal accepts any endpoint whose authenticated generation satisfies
the policy, including another correctly measured unit. It omits a unit alias and
therefore authenticates no particular die. Unit appraisal additionally requires an
opaque alias enrolled for that relying-party origin, authenticated in the evidence.
Aliases for different origins are independently assigned in the model; they are
not a global die identifier or a hash of one. Enrollment is an additional trust
premise, not evidence inferred from an approved generation. The claim format alone
does not establish privacy of the endorsement chain, certificate identifiers,
enrollment flow or network metadata. M6.9a/M6.9c must select and qualify those parts
before claiming that their realization preserves the modeled scope.

The accepted relation is point-in-time: the measured holder produces evidence for
the challenged connection and keeps the protected key authority in the stated
threat model. It does not detect a runtime exploit in correctly measured code,
prevent that code from relaying application plaintext, or prove a human's intent.
Compromise after appraisal, key exposure, or a state transition that should retire
the context breaks a premise; M6.9b must connect teardown to those platform events.

### Executable experiment and refusal cases

[The model](../../tools/vos/session_binding.py) enumerates every delivery of its
authentic quote population to its connection, origin, challenge and policy
population. Approved units A and B and unapproved unit X each have parallel TLS
contexts. Software and unit policies differ, and nonce symbols deliberately repeat
across distinct connections so parallel-session rejection must use the channel
binding. The independent event-level oracle checks whether an accepted quote
actually originates at that connection's approved holder and, when requested,
the enrolled unit. It checks both directions, so rejecting every session also fails.
Each delivery trial forks a fresh pre-appraisal context; within the trial, every
completed appraisal receives a repeated delivery and an attempted reconstruction
of the appraiser on that same context. Both must refuse.

| Case | Required classification in this assessment |
| --- | --- |
| Approved generation and its own live context | Accept under software policy; accept under unit policy when the origin enrollment matches |
| Replayed evidence or a completed attempt | Refuse a different challenge, expired deadline or repeated decision |
| Valid quote delivered to a parallel context | Refuse unequal local channel binding, even when nonce and generation match |
| Another correctly measured unit | Accept software policy; refuse an alias different from the enrolled unit |
| Transparent network relay | Accept when the same intended client remains the TLS key holder; the relay acquires no key authority |
| Two TLS legs terminated by an intermediary | The healthy unit cannot quote the intermediary's protected TLS context; copying the public exporter alone supplies no local ownership |
| Caller-supplied exporter accepted by a broken issuer | Accepting the forged ownership claim is the counterexample; this interface cannot implement the selected construction |
| Attestation issuer or signing authority compromised | False measured-state evidence can be accepted; the quote's trust premise is lost |
| Client traffic key exposed after honest appraisal | An attacker gains application-record authority; the accepted quote cannot establish continued exclusive custody |
| Runtime exploit using a legitimate measured key holder | The authorized holder's records remain acceptable; measurement is no behavioral proof |
| Missing, changed, unapproved or late evidence | Refuse the attestation-authenticated service and retain R-17-030y's availability cost |

The traffic-record model distinguishes possession of directional client key
authority from knowledge of a public exporter. Its key-exposure case first refuses
an attacker record, adds that attacker to the secret-key holders, then accepts the
record after an otherwise honest appraisal. The broken-issuer cases deliberately
alter the trusted evidence ledger and are outside the honest finite relation.
Their acceptance is the measured failure of a premise, not a successful protection.
The transparent-relay case is the direct transcript with unchanged endpoints; no
network distance or topology is modeled.

Run the experiment and the focused behavioral checks through the shared entry point:

```console
python tools/run.py session-binding --json
python tools/run.py test --only session_binding
```

The JSON output owns population counts, classifications and SHA-256 identities of
the model, CLI, tests and this assessment. Exit zero means the finite classifications
match, while
`production_adoption` remains `open`. The tests also collapse distinct exporters
deliberately and require the event-level oracle to expose the resulting substitution.
They cover credential attenuation boundaries, deadline equality, failure consumption,
scope disagreement, ineligible TLS states and service teardown. This is finite host
evidence with ideal cryptography, no TLS packets, computational reduction, prover,
target execution or WCET measurement.

### Separately owned adoption work

The [checklist](../implementation/implementation-checklist.md) owns the estimates and
entry conditions. All of the following remain open, after the M8a gate, and none
is absorbed by M6.3b's credential-handle predicate:

| Child | Required completion predicate |
| --- | --- |
| M6.9a, protocol realization | Select the precise TLS/attestation revisions and read their licenses before incorporation; implement bounded canonical challenge/evidence parsing, authenticated reference-manifest appraisal, origin authentication and scoped enrollment; fix nonce/deadline/capacity policy and single-connection lifecycle; refuse absent prerequisites, resumption and early-data shortcuts; demonstrate the positive and refusal transcripts against the selected TLS implementation |
| M6.9b, implementation connection | Connect M6.3b's attenuated handle to the actual measured principal and non-exportable local TLS context; read the exporter and measurement through that context with no caller override; connect appraisal, service opening and teardown atomically across close, restart, generation/lifecycle transition and expiry; reject cross-unit, cross-principal and stale handles; bind target evidence and applicable refinement obligations to the exact artifact |
| M6.9c, protocol model and theorem | Author the selected construction's `CJ-ATTEST` model with peer/role/origin, challenge, generation, trust-chain and key-custody events; construct nonvacuous acceptance and attack witnesses; prove exactly the session-agreement relation under explicit TLS, hybrid-crypto, attestation, entropy and compromise assumptions; connect imported proof scope to the chosen revisions and retain model-faithfulness, privacy and compromise residuals |

The theorem child belongs to hardening. Missing primitive proofs, enrollment
mechanisms, protocol artifacts or target interfaces are entry failures to price
with their owners; assigning these children does not make those foundations exist.
Production adoption requires their applicable evidence together. Withholding the
exchange can always deny this service, and software attestation cannot promise
particular-unit identity, arbitrary relay prevention or continuous uncompromised
execution. Those boundaries remain part of the selected contract.

## The ensemble link session

Q23c authors the second member of the same inventory row: the construction R-12-015d
states for an ensemble link (R-15-228b) joining two members of one ensemble
(R-02-003a). Its appraisal is unit-specific by choice, because a second unit running
the same image is exactly the substitution an ensemble exists to exclude. The
disposition matches the TLS part's: the construction is retained for realization and
proof work that has not started, and `CJ-ATTEST` stays unauthored in the
[crown-jewel inventory](crown-jewels.md). R-17-049d's record stays open, this design
having no upstream symbolic analysis of this protocol to curate from.

The [register](../requirements-register.md) owns the obligations. R-12-015c owns
session binding and R-12-015d this construction; R-09-025a splits the generation and
device registers; R-13-001d fixes the ensemble identity at composition and R-09-007's
attested devicetree carries each end's expectation of its peer; R-11-017a owns the
slot tables whose digests the session binds; R-12-043a admits one key-establishment
configuration and R-17-049b states what the hedge does instead of negotiating;
R-15-202 and R-05-070 keep the keys and the cipher in the crypto core; R-15-228d and
R-15-228e own the frame and its tag; R-17-030z books what a refusal costs. Nothing
here narrows any of them, and R-15-132 is read against this part and unmoved: what
crosses the wire is attestation evidence processed by this construction, never a
persistent link-layer address.

### The selected construction and its boundary

Two members establish one session per link. Each end appraises the other on both of
R-09-025a's registers: the generation register for the running generation and the
ensemble identity the composition fixed, the device register for the unit, each
against the constants its own attested devicetree names for that endpoint. Each end
supplies its own fresh challenge, so the relation is mutual and one accepted
direction is not a link. Key establishment takes the composition-fixed hybrid
configuration; a second offered configuration terminates establishment rather than
selecting a path.

Two open siblings bound what this part states. Q23b owns the link contract, so this
part names no frame field, no width, no public padding and no cadence, and takes a
frame as its associated-data triple (the link, the session epoch, and the schedule's
count of that link's slots since the epoch began) over a payload the crypto core
seals. Q23d owns the slot tables and the composer's self-check, so this part takes
each end's table as an opaque digest and states only where the digest check decides.
Establishment traffic, re-establishment cadence and the bounded handler that consumes
handshake frames belong to those two items and are not qualified here.

The model reads the device register for the unit identity alone. Which further parts
of R-09-037's device-register shape a link appraisal should require is not decided by
any entry this part cites, and is not decided here.

### The device-identity binding, and why it is stated first

The construction's first obligation is that the identity a quote is signed under is
the identity rooted in that unit's device-identity secret, the secret R-09-022 names
and R-10-033 re-derives from the root of trust. It is stated as an obligation and not
as a claim, because the register decides no construction that discharges it: R-09-008
gives the root of trust the quote surface, R-12-014 the sealing and attestation
service, R-09-022 names the secret only as what the duress erase destroys, and
R-10-033 says device identity re-derives from the root of trust. No entry states a
layered derivation, an endorsed per-boot alias, non-exportability of that signing
key, or whether it survives the erase. Choosing among those is a register act nobody
owns, and this part takes none of them.

What the model does instead is name the premise and make the obligation decide. The
premise is that exactly one signing identity speaks for one unit's device-identity
secret, and that a member can present that identity or an alias rooted in no secret,
never another unit's. The appraiser therefore checks the presented identity against
the unit the device register names before it reads any other claim. Two scenarios
make the check load-bearing rather than decorative: a quote signed under an alias is
refused by name, and an appraiser that takes the binding on faith accepts a unit the
composition never named, asserting a device register it cannot sign for. Without the
obligation the device register is an assertion any endpoint can make, and the
unit-specific appraisal the whole construction rests on decides nothing. Realizing
the binding is owed, and the model credits no realization.

### Mutual claim, freshness, custody and anti-replay

Each end opens its own challenge and decides once. An authentic quote answers exactly
that challenge over that link, so a quote answering an earlier challenge is refused,
and a decided attempt is not reopened. The session's context binds the digest of the
link's slot table each end holds, so two ends holding different tables are refused
before any payload crosses. That check decides where a table is substituted or
mis-emitted; where one composition act emits both views, Q23d's composer self-check
is the honest side's owner and the digest agrees by construction, so this part claims
nothing there.

The session keys live in the crypto core, which seals and verifies every frame and
has no export path; the endpoint holds no key and no cipher and moves frames only. A
frame's associated data is the link, the session epoch and the schedule's own count
of that link's slots, a value both ends derive from the schedule and neither from the
wire. A frame therefore verifies only in the slot named for it: one replayed or
reordered into another slot fails its tag and fail-stops the link, while delay inside
its own slot leaves the count unadvanced and the tag valid. The receive window admits
at most one frame per slot. The counterexample for the schedule-derived clause is an
endpoint that reads the count from the frame instead: it accepts the replay, which is
why the count is not a wire field and why the frame grammar Q23b authors carries
none.

### Endpoint, wire and compromise assumptions

The intended peer is the appraised member's crypto core and kernel, at the unit and
the ensemble identity the composition named for that link endpoint. It is not the
cable, not the chassis and not the operator.
The local end and its appraisal policy are honest, and each end's devicetree
constants are the attested ones.

The wire is untrusted, with no assumption about it beyond delivery of bytes. An
adversary holding the cable may drop, delay, reorder, replay, inject and cut. Under
R-17-030z what that spends is availability, on that link alone: no member yields a
weaker peer claim, delivers an unverified frame, or changes what it executes, and the
member boots and runs its own generation while the link stays down. Re-establishment
is a scheduled act at the composition-fixed cadence, never an on-demand one.

Three compromise cases are accepted attacks outside the honest relation rather than
protections, and the experiment records each accepting. Exposure of a unit's
device-identity secret reproduces the identity the first obligation rests on, so the
appraisal admits whoever holds it. A compromised root of trust or issuance path
authenticates false registers, evidence being a premise here and not a result.
Exposure of the session keys after establishment yields frame authority an accepted
appraisal cannot revoke, the relation being point-in-time. Beside them, a relay that
forwards between the two intended ends is not endpoint substitution: it acquires
neither core's keys and its own frame fails the tag, while an intermediary
terminating both legs is a unit the composition does not name.

The fixture's ideal tag, its opaque digests, its symbolic identities and its small
integer slot counts are experimental inputs. They are not a cipher, a key schedule, a
slot-count width, a guard band or a cadence recommendation, and no Python object here
is a security boundary.

### The ensemble experiment and its refusal cases

[The model](../../tools/vos/session_binding.py) enumerates every delivery of its
quote population to both ends of the link at every candidate challenge. The issuance
population carries the composition's two members, a third unit running the right
software, the same unit at the previous composition, a member of another ensemble, an
unapproved generation, a mismatched slot table, and the substitution that asserts
another unit's device register under an alias. The independent event-level oracle
reads the die that actually signed and its actual registers, where the appraiser has
only authenticated claims and its own devicetree constants; it decides in both
directions, so refusing every establishment fails the experiment as accepting a
substitution does. The command reports the two counters the construction's check
asks for: every delivery whose issuing member is not the unit the target's devicetree
names, and every delivery at an ensemble identity other than the composition's, each
refused.

| Case | Required classification in this assessment |
| --- | --- |
| Both ends at the composition's units and ensemble identity | Establish, each end accepting the other on both registers |
| A peer of the right software on another unit | Refuse on the device register |
| A peer at another ensemble identity | Refuse on the generation register |
| The right unit still at the previous composition | Refuse until it boots its own new generation |
| An unapproved generation | Refuse on policy, an authentic quote being no admitted one |
| A quote signed under an identity rooted in no device-identity secret | Refuse by name, the model's first obligation deciding |
| An appraiser taking that binding on faith | Accept a substituted unit; this interface cannot carry the construction |
| Two ends holding different slot-table digests | Refuse at establishment, before any payload crosses |
| A quote answering an earlier challenge | Refuse; each direction supplies its own fresh challenge |
| One direction accepting and the other refusing | Refuse the link; one-sided acceptance establishes nothing |
| Withheld evidence | Refuse, with no weaker peer claim and no fallback |
| A second key-establishment configuration offered | Terminate establishment rather than select a path |
| A quote carrying a configuration other than the admissible one | Refuse on the key configuration |
| A frame replayed or reordered into another slot | Fail its tag and fail-stop the link |
| A frame delayed inside its own slot | Keep a valid tag; the schedule's count has not advanced |
| A second frame in one slot | Refuse at the receive window |
| An endpoint taking the count from the frame | Accept the replay; the counterexample for the schedule-derived clause |
| A transparent relay between the two intended ends | Establish; the relay holds neither core's keys and its own frame fails the tag |
| An intermediary terminating both legs | Refuse as a unit the composition does not name |
| Frames withheld or cut on the wire | Refuse the link and spend availability alone; the member runs its own generation |
| The device-identity secret exposed | Accept; the first obligation's premise is lost |
| The root of trust or its issuance compromised | Accept false registers; authenticated evidence is a premise |
| Session keys exposed after establishment | Accept the attacker's frames; appraisal revokes no frame authority |

Run this part with the TLS part, through the shared entry point:

```console
python tools/run.py session-binding --json
python tools/run.py test --only session_binding
```

The JSON output owns the population counts, the two counters and the classifications
under its `ensemble` key. Exit zero means both parts' finite classifications match,
while `production_adoption` stays `open`. This is finite host evidence with ideal
cryptography: no frames, no key exchange, no computational reduction, no prover and
no target execution.

### Separately owned model, theorem and foundation work

No protocol proof is claimed here and none is attempted. M6.9a owns protocol
realization, M6.9b the implementation connection and M6.9c the model and theorem for
each selected construction, this one as for TLS; their predicates are the checklist's
and they are not restated here. The proof foundation those children need is the
[unassigned proof map](unassigned-proof-map.md)'s U-20, and no library the locked
prover admits is installed today. Until the theorem lands, R-17-049d's open record
stands and this construction's session security rests where R-17-049 leaves it,
unnarrowed above the primitive reductions.

Two further things are owed before a stronger claim is available. The construction
that binds a quote's signing identity to the device-identity secret is undecided in
the register, so an entry deciding it, or explicit M6.9-series scope for the choice,
is owed before the first obligation can be discharged rather than assumed. The link
contract and the slot tables are Q23b's and Q23d's, so the frame grammar, the public
fields, the establishment path and the tables this part abstracts must exist before
an implementation can be connected to any of it.
