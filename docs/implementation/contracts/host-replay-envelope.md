# Bounded host replay authentication

This is the acceptance contract for S6a in the
[implementation checklist](../implementation-checklist.md). It adds an executable
host integrity boundary around the existing [replay body](replay-record.md).
It is not S6's production export envelope, a device key service, image-signature
verification, entropy sealing, source-completeness evidence or paired replay.
Those obligations remain open at S6 and its named prerequisites.

The [host module](../../../tools/vos/replay_envelope.py) implements creation and
verification; its [independent oracle and refusal campaign](../../../tools/tests/test_replay_envelope.py)
exercise the acceptance boundary below.

## Inputs and trust boundary

The caller supplies a development authentication key of at least 32 bytes outside
the artifact. Neither serialization nor returned evidence contains that key.
HMAC-SHA-256 authenticates a domain-separated, versioned, length-prefixed encoding
of the exact capture-origin, input-trace and replay-body bytes. The framing has
one interpretation, a fixed-length tag and no accepted trailing bytes. A shared
development key provides authentication between its holders, not provenance
against another holder of the same key or an asymmetric signature.

Verification receives the expected image-root identity, composition digest,
input-trace digest, nonempty capture origin, event count, capacities and interface profiles
independently. It compares the input trace's SHA-256 with the independently expected
digest and uses the existing replay-body decoder to check the binding, event count,
source/interface pairing and capacities. Matching a root identity does not verify
an image signature. An explicit empty input trace is distinct from missing bytes.

The caller supplies only development data appropriate for this host. The module
cannot infer that trace bytes contain no secrets and supplies no encryption,
redaction or export authorization. It has no production, declassification or
verbose-device mode. A future production consumer cannot obtain those permissions
by selecting this format.

## Processing and resource contract

The public operations accept immutable bytes and reject malformed external
parameters, including booleans masquerading as integer capacities. Independent
limits bound total envelope, origin, input trace, body and event count. Check the
total size and fixed framing before allocating or decoding variable fields; reject
declared lengths beyond the provided bytes or independent limits. Verification
compares the full tag using the standard constant-time comparison primitive before
decoding the body or returning any authenticated payload. This library-level use
is not a constant-time proof of the Python runtime or the device.

Creation applies the same binding, trace-digest and body validation before producing
an envelope. Verification returns the exact authenticated bytes and decoded record
only after every check succeeds. Every failure is a whole-artifact refusal, never
a decoded prefix, recovered field, weaker retry or best-effort authentication.
The API does not persist a key, accept an authentication-success callback, or
reuse the regression trace digest as cryptographic identity.

## Acceptance before implementation

The focused host suite must establish:

- A positive round trip preserving exact bytes and an independently constructed
  complete envelope, plus a published HMAC-SHA-256 known-answer vector.
- Refusal after mutation of each authenticated framing/payload region or the tag,
  and after use of a wrong, missing or short key.
- Refusal for wrong expected root, composition, origin, event count or input-trace
  digest, including a validly authenticated artifact carrying a wrong binding.
- Refusal for truncation, appended bytes, unknown format version, oversized lengths,
  invalid external capacities and each exceeded capacity, at and beyond boundaries.
- Refusal for a valid tag over a structurally invalid body. Invalid authentication
  must not invoke the body decoder, and no refusal returns payload bytes.

Use `python tools/run.py test --only replay_envelope` for focused evidence and the
integrator's host wave for tool acceptance. This is an executable host artifact
predicate. Passing it supplies no operational producer, CT scope proof, signed-root
trust, machine recording or replay verdict. Its remaining runtime consumers retain
the [replay contract's operational acceptance](replay-record.md#acceptance-fixed-before-implementation).
