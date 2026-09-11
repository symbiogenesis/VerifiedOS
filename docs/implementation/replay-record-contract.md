# Deterministic-replay nondeterminism record

This is S6's record contract, a view of R-15-241 and R-16-015 through
R-16-022 in the [requirements register](../requirements-register.md). The
register wins wherever this view disagrees. The contract specifies the logical
record and its acceptance cases before a producer or replay adapter implements
them. It does not claim an operational recorder, authenticated export, or replay.

## Sources and existing interfaces

The source tags below implement R-16-015's closed set. Adding a source requires
amending the register first. An ordinary received input stays in the input trace;
these records account for the values that input trace cannot supply.

| Source tag | Required representation | Existing surface and missing adapter |
| --- | --- | --- |
| `entropy` | Opaque RoT-sealed commitment to each secret draw; never the draw, seed, or an exposed hash | [rot_draw](../../model/model/sys/rot.sail) returns a conditioned word or refuses. The RoT's `ROT_TRNG_DRAW` door in [platform.sail](../../model/model/sys/platform.sail) calls it; the watchdog calls it internally too, so observing MMIO alone misses draws. This is an emulation stand-in. The verified DRBG, commitment producer, sealing primitive, and interception of every draw are absent. |
| `link_address` | Drawn address bytes verbatim | MAC randomization is specified; no producing link-address interface or replay adapter exists in the model or host tools. |
| `time_read` | Returned time-service bytes verbatim at the client's granted precision | R-08-031 grants precision through the time service. [platform.sail](../../model/model/sys/platform.sail) has the platform timer, which is not an implemented capability-authorized time-service reply. That service and its adapter are absent. |
| `physical_event` | Public sentinel event bytes verbatim | The model contains fault causes and architectural health state, but no complete sentinel event producer or replay adapter. ECC corrections, tag traps, thermal and voltage telemetry belong to this source. Capacity events retain R-16-028's bounded, labeled record rather than acquiring a free-form payload. |

The classification is fixed by the source, never selected by a caller. An entropy
draw underlying a public link-address draw remains accounted for at its entropy
boundary; the published address has its own public record at its consumption
boundary. This records both boundaries without putting the secret draw in the
public one. Raw noise samples are internal to conditioning, not extra sources
or consumer draws. Failed entropy requests return no value and cannot be replaced
by a last-known-good value; their fault belongs to the existing fault/input path.

## Logical body and bindings

`replay-record-v1` is a bounded JSON review representation of the logical body
before sealing. It is not the production wire format or an exportable crash
record. The production envelope must authenticate and seal this body and the
ordinary input trace against the reproducible base image's signed root under
R-16-013 and R-16-022. Its cryptographic encoding is owed to the sealing primitive;
a host validator cannot infer authentication from well-shaped bytes.

The body has exactly `schema`, `binding`, and `events`. `schema` is
`replay-record-v1`. `binding` has exactly these fields:

| Field | Meaning |
| --- | --- |
| `base_image_root` | Nonempty lowercase hex encoding of the opaque signed-root identity, whose format and width belong to the image owner. The reader compares its exact bytes; it does not prescribe a production hash or verify a signature. |
| `composition` | Full lowercase SHA-256 host artifact digest of the composed schedule, interface schemas, precision grants, source endpoints, and capture origin, including the reset epoch from which event coordinates count. This host digest does not choose the production identity format. |
| `input_trace` | Full lowercase SHA-256 host artifact digest over the exact ordinary input-trace bytes bound into the same authenticated envelope. |

The consumer receives the expected binding independently; agreement with a
self-declared binding alone is not acceptance. The authenticated input trace
and capture origin fix the initial execution state and observation window.
Authentication of these identities remains an operational prerequisite.

`events` is an ordered array. Each element has exactly `seq`, `point`, `source`,
`interface`, and `payload`. `seq` is the zero-based, contiguous event index.
`point` has exactly `slot`, `core`, `retire`, and `ordinal`, all unsigned 64-bit
integers. These identify the absolute logical schedule slot from the capture
origin, core identity, local retired-instruction count, and the event's ordinal
at that boundary. An event may occur before any instruction retires, or while
no instruction retires; `retire` then names the current count, including zero,
without claiming an instruction caused the event. `slot` and `ordinal` are
logical ordering coordinates, not clock values exposed to a compartment.
Events are strictly ordered by the tuple
`(slot, core, retire, ordinal)`; the composed adapter defines this total order
for simultaneous independent events before execution. A reset needs a new
capture origin; a local retire counter silently returning to zero is invalid.

`interface` is the full lowercase SHA-256 identity of the composition-fixed
interface schema and endpoint. The consumer supplies an allowlist mapping that
identity to its source and maximum payload length. Public payloads have exactly
`value`, a nonempty, lowercase, even-length hex string encoding the consumed
bytes verbatim. Secret payloads have exactly `sealed_commitment`, the opaque
nonempty hex encoding of the RoT-sealed hash over the draw. There is no generic
metadata, seed, secret value, unsealed hash, diagnostic dump, or extension field.
An opaque field's shape proves neither that its bytes are sealed nor that they
contain only a commitment; only the producer and sealing contract decide that.

The interface schema owns the meaning of public bytes: an address's actual
format, the time reply and granted precision, or the sentinel's closed event
type. No host fixture invents those missing production ABIs. Its validator must
check that meaning before a replay adapter releases a value. The host schema
reader only checks the envelope shape, source membership, bindings, ordering,
allowlisted interfaces, and declared byte bounds. Its result is structural
acceptance, never permission to replay or export.

Limits are inputs from the composition, not fields a record may increase:
maximum encoded body bytes, event count, and per-interface payload bytes. The
consumer also receives an independently expected event count for the declared
capture window; the array's own length cannot certify completeness. At capacity
the producer stops admitting further record-dependent operations and
uses the reserved terminal fault path under R-16-023. It does not evict an old
event, wrap a sequence, continue with a partial capture, or consume a value it
cannot account for. An explicitly bounded capture is complete only for its
declared window. The consumer rejects exhaustion before a required event and
leftover events after the declared window. A structurally valid prefix does not
establish complete capture; completeness needs the actual execution adapter.

## Reuse and security boundary

The existing [commit-trace grammar](../assurance/differential-corpus.md) and
[trace reader](../../tools/vos/trace.py) provide local retired-instruction anchors
for development fixtures. A local adapter may recognize `I` records with
`COMMIT_RE`, preserving their order. `normalize_commit` deliberately removes
that order, and `digest` deliberately truncates SHA-256 for regression reporting;
neither operation supplies this record's event ordering or authenticated identity.

Commit traces contain register and memory values. They cannot be relabeled as
ordinary exportable input traces, and filtering only entropy reads cannot remove
their secret-derived effects. The nondeterminism body adds a distinct record
dialect beside that infrastructure. No change to the existing commit grammar,
corpus digest, or normalizer makes an unimplemented producer appear to exist.

R-16-017's ordinary off-device path substitutes locally obtained entropy for a
secret draw. The substitute has the requested shape and respects the DRBG's
seeding and reseeding discipline; a seeded PRNG configuration is not evidence
that original draws were recorded. R-16-018 and R-16-019 give exact instruction
sequence, addresses, capability operations, schedule, and fault reproduction
only within the CT-verified scope. Values are exact outside the secret-entropy
cone. A fault depending on a particular draw is not reproduced from export
alone, and comparing every commit-trace value would make the wrong claim.

R-16-020's candidate check and actual-draw declassification are separate gated
facilities. A hash commitment cannot recover the draw. This body carries no
recoverable draw and does not imply a secret archive elsewhere. Any future
facility providing the actual draw owes its own confidentiality, retention,
capability, powerbox, and RoT lifecycle-debug gates. R-16-021's on-device verbose
sink is capability-scoped and confidentiality-labeled, gated by lifecycle and
fused off in production. A record flag, caller assertion, or host option cannot
grant either facility.

## Acceptance fixed before implementation

The structural reader accepts a bounded synthetic body containing each source,
with known bindings and interfaces, public bytes preserved exactly, an opaque
secret commitment, and ordered consumption coordinates. It refuses each of:

- Unknown schema, field, source, interface, or source/interface pairing;
  duplicate JSON keys; a non-object or non-array where the schema requires one;
  booleans, floats, negatives, or oversized integers in coordinate fields.
- Any extra secret value, seed, unsealed hash, dump, or metadata field; a public
  payload on `entropy`, or a commitment payload on a public source.
- Malformed digest or byte encoding, empty payload, a binding differing from
  the independently expected one, or any body/event/payload capacity exceeded.
- Repeated, missing, or reordered sequence numbers and repeated or regressing
  coordinates. It must reject the whole body rather than return an accepted
  prefix or silently drop a malformed event.

Operational acceptance additionally requires real producers at every boundary,
public interface validation, sealing and authentication refusal tests, and a
consumer that matches the requested endpoint and point before consuming each
event. Tests must remove an event, request a different draw or precision, run
past the record, leave a trailing event, inject an unrecorded watchdog draw,
and exhaust recording capacity before a draw is consumed. Missing input bytes,
a wrong signed root, a wrong capture origin, failed authentication, or a
production request for declassification must all refuse.

A paired Sail run must then reproduce the public values and the observations
within the proved CT scope using independently substituted secret entropy.
A draw-dependent fault is an explicit unsupported result without the separately
gated evidence, never successful reproduction. Until those producers, proofs,
and security primitives exist, structural fixture tests discharge only the
reader's stated predicate. S6 remains open as owner of recording, adapters,
and integration qualification against this contract. The completed firmware and
crypto statements supply dependencies, not operational recording or sealing
credit; S6 owes their actual implementations before claiming replay.
