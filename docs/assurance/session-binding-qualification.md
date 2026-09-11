# Session-attestation qualification

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

## Selected protocol and application boundary

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

## Claim, freshness and custody

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

## Peer and compromise assumptions

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

## Executable experiment and refusal cases

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

## Separately owned adoption work

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
