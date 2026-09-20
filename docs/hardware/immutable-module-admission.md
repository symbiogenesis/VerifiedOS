# Module admission and host containment candidate

This is the contract and statement work for Q24c and Q24d. It extends the
[immutable module contract](immutable-module-contract.md), whose grammar and
seven-state lifecycle remain the owner. A separate document keeps admission
evidence and proof scope apart from that interface. No module is enabled by this
candidate: R-12-085f still requires every implementation and physical artifact.

## Acceptance before implementation

The source artifact is `proofs/ModuleAdmission.v`. Its acceptance predicate is:
the locked prover checks every definition and theorem with no new trusted axiom;
each record has a closed witness; successful admission and delivery are inhabited;
the negative cases below compute to refusal; and general theorems establish the
stated binding and preservation properties. Native compilation, constant and
assumption enumeration, kernel rechecking, and adversarial review are required.
Fixture identifiers and bounds demonstrate decisions and select no device values.

Q24c's authorable statement separates three decisions. A bounded typed manifest
names graph, weights, arithmetic, tokenizer, vocabulary, circuit, implementation,
protocol/schema, private footprint and physical envelope identities. A certificate
is a bounded byte list. Generation admission consumes a trusted kernel receipt
bound to those subjects, host-selected propositions, permitted assumptions,
checker/profile and actual resource accounting. Card-supplied budget or success
assertions are never kernel receipts. Insertion uses the cached design decision
and authenticates one unit in the finite replacement set; it checks no new proof
and changes no policy. A serial string is not an authentication credential.

The session context binds both roles, endpoint, unit key, manifest/design and
model identity, generation policy, schedule, activation epoch, protocol/suite,
challenge and ephemeral contribution identities. Authenticated issuance is an
explicit trusted relation. The source proves the appraiser's binding against that
relation; it does not implement a signature, key exchange or session-key custody.
The construction follows [the qualified session interface](../assurance/session-binding-qualification.md)
and keeps its honest-issuer, protected-key and entropy premises. Protected freshness
evidence must cover reset as well as ordinary reconnect; a reset does not erase the
history against which the source decision refuses reuse. A real bounded freshness
construction and its computational proof remain Q24c implementation work and U-20.

The byte format those subjects are named in is `proofs/ModuleFormats.v`, over
ModuleAdmission.v's manifest record and a certificate container that carries it.
It fixes one canonical encoding for each: a total serializer and a total parser
over byte lists, with parse of serialize and serialize of parse both proved, so a
value has exactly one admissible encoding in R-05-051a's sense and a non-canonical
length form is refused rather than normalized. Every maximum it enforces is a
field of its bounds record, and it computes refusals for malformed bytes,
over-budget lengths, a trailing byte, a non-canonical length form, a subject
naming another design or model, and an assumption outside the permitted list. It
implements no cryptography and no proof checking: an identity is an opaque bounded
numeral, certificate evidence is opaque bytes the file bounds without inspecting,
and the kernel receipt stays a host input beside the parsed bytes. It is a
hand-authored reference codec, so the verified derived parser R-05-042 requires,
proved against its descriptor under R-05-046, and its correspondence to this
codec stay with U-12's inventory descriptors, U-14 keeps canonicity over the
derived decoder, and a format theorem admits no card.

Q24d's authorable statement gives the host an immutable composition containing its
schedule, reserved endpoint objects/buffers and ceilings. An arbitrary frame can
produce a bounded untrusted proposal only into the host-selected outstanding
destination. The socket cannot issue host-memory writes, create capabilities,
change the schedule or increase its quota. The broker checks a host-owned grant
against the requesting principal, unit, design/model, input objects, output
destination, operation, lifetime, session and activation epochs. Grant failure
disables delivery without granting authority to the model. Replacement clears
the route and outstanding operation; buffer reclamation separately requires the
host mover completion/revocation barrier. No card acknowledgement establishes it.

The reference operations are a typed boundary for the Sail-visible wrapper to
refine, not an implemented Sail device. The complete grammar transition comparison,
generated parser/accessors, Sail/Gallina join and RTL/mover refinement remain open.
In particular a theorem about this transition function is not yet the whole-path
host-containment theorem required for production admission.

## Required distinguishing cases

| Surface | Positive case | Refused neighbor |
| --- | --- | --- |
| Design | exact bounded manifest and matching checked receipt | malformed bytes, excessive evidence/cost, added assumption, different design/model, wrong subject or checker/profile |
| Unit | endorsed admitted unit with authenticated current context | copied identifier without a key, foreign unit, endorsement for another circuit, different model |
| Session | fresh challenge and ephemeral contributions, exact roles/context | replay, concurrent-context substitution, reset nonce or ephemeral reuse, wrong endpoint/generation/schedule/suite |
| Route | current scoped grant and host outstanding output | missing/revoked consent, wrong client/input/destination/operation, expiry, old activation/session |
| Frame | authenticated bounded in-window output in sequence | arbitrary address/capability request, stale or malformed frame, excessive count/quota, unsolicited output, second delivery |
| Replacement | explicit new authentication and grant | inherited grant, delayed old output, premature buffer reclamation |
| Compromise | honest authenticated-issuance relation | forged issuance can authenticate a false claim; this exhibits the premise rather than a protection |

## Electrical and physical boundary

Arbitrary-card quantification includes silence, arbitrary bytes and dishonest
current-session payloads only inside R-15-228i's qualified electrical envelope.
It assumes bounded detection and isolation delay; specified connector sequencing;
current/inrush, backfeed, short, overvoltage and thermal protection; independent
host rails and reset; and termination of module clocks at bounded endpoint FIFOs.
Faults inside that envelope cannot alter host storage or control except through
the modeled endpoint events. The host can isolate without a card response.
The reference theorem abstracts these as the interface to the digital transition
system. It establishes no numeric envelope, analog isolation, arbitrary-sabotage
protection, cold/hot-swap qualification or fabricated-circuit correspondence.

An accepted key, endorsement or circuit proof supplies no fabrication theorem.
The qualified implementation's confidentiality, clearing, cryptography and resource
guarantees remain distinct from arbitrary-card host containment. An authenticated
scrub acknowledgement alone proves no erasure. Q24e owns honest-card proofs,
Q24f the physical binding and limits, Q24g live replacement, and Q24h the complete
candidate verdict. U-10/U-12/U-14 retain register-layout, bounded canonical format
and encoding uniqueness work. The source candidate cannot discharge those owners.
