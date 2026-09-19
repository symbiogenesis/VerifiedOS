# Deterministic-replay nondeterminism record

This is S6's record contract, a view of R-15-241 and R-16-015 through
R-16-022 in the [requirements register](../../requirements-register.md). The
register wins wherever this view disagrees. The contract specifies the logical
record and its acceptance cases, and qualifies the producer adapters below against
them. It does not claim an operational recorder, authenticated export, or replay.

The [host fixtures](../../../tools/vos/replay_record.py) implement structural decoding,
a demand cursor, and bounded callback capture. Run
`python tools/run.py test --only replay_record` for the
[reader controls](../../../tools/tests/test_replay_record.py) and
[recorder controls](../../../tools/tests/test_replay_record_recorder.py).
The supplied identities, counts and endpoint profiles are independent fixture
inputs; these checks supply no authentication or production replay evidence.

## Sources and existing interfaces

The source tags below implement R-16-015's closed set. Adding a source requires
amending the register first. An ordinary received input stays in the input trace;
these records account for the values that input trace cannot supply.

| Source tag | Required representation | Existing surface and missing adapter |
| --- | --- | --- |
| `entropy` | Opaque RoT-sealed commitment to each secret draw; never the draw, seed, or an exposed hash | [rot_draw](../../../model/model/sys/rot.sail) returns a conditioned word or refuses. The RoT's `ROT_TRNG_DRAW` door in [platform.sail](../../../model/model/sys/platform.sail) calls it; the watchdog calls it internally too, so observing MMIO alone misses draws. This is an emulation stand-in. The synchronous root observer exposes every draw to a trusted harness callback. The production DRBG, commitment writer and sealing primitive remain absent. |
| `link_address` | Drawn address bytes verbatim | MAC randomization is specified; no producing link-address interface or replay adapter exists in the model or host tools. |
| `time_read` | Returned time-service bytes verbatim at the client's granted precision | R-08-031 grants precision through the time service. [platform.sail](../../../model/model/sys/platform.sail) has the platform timer, which is not an implemented capability-authorized time-service reply. That service and its adapter are absent. |
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

## Host fixture producer interface

`FixtureRecorder` fixes a single-caller callback interface for bounded synthetic
capture. Its constructor receives a binding, limits, and endpoint profiles,
plus one semantic validator for each public endpoint. It snapshots both mappings;
changing the caller's dictionaries cannot change a capture already admitted.
The supplied validators decide a fixture's public byte language. Their presence
does not implement a time-service precision grant, address format, or sentinel
schema, and there is no entropy validator that purports to authenticate a seal.

`record(point, interface, produce)` takes its source classification from the
endpoint profile. It checks the coordinates, endpoint, and event capacity, then
reserves the endpoint's maximum payload length as hex plus the exact compact JSON
overhead before invoking `produce`. The body bound includes its binding, array
commas, and closing delimiters. A maximum reservation may refuse an operation
whose eventual smaller value would fit: reading that value to decide admission
would already consume it. After success, actual encoded size determines the room
available to later operations; unused reservation does not remain charged.

The callback returns immutable bytes: the public value at that fixture boundary,
or opaque entropy-commitment bytes whose actual production is still absent.
Public bytes must satisfy the endpoint validator before an event is appended or
returned. The callback may instead return `None` only under the explicit adapter
promise that it consumed no source value and owes no nondeterminism event; that
outcome consumes neither a sequence index nor capacity. The host cannot verify
that promise inside an arbitrary callback. A future real adapter owes it for
each failed request and must route its fault through the existing fault path.

Any refusal, invalid callback result, or callback or validator exception latches
the entire capture unusable. Exceptions propagate, while finalization of the
uncertain prefix remains refused. Recording or finalizing from inside a callback
is also a refusal; swallowing that nested exception cannot make the outer call
succeed. No event or body is returned from a failed operation. Earlier successful
events are provisional and cannot supply a finalized partial body after refusal.
This host latch does not implement R-16-023's reserved terminal fault path.

`finish(expected, expected_events)` checks the independent expected binding and
capture-window count through the existing structural reader before returning
body bytes. Success closes the recorder, and any refusal permanently prevents
retry with a weaker binding or count. These fixture inputs establish only the
declared fixture window; actual execution coverage, input-trace authentication,
and interception of every source remain the production adapter's obligations.

## Producer adapters over the composed model

[replay_adapter.py](../../../tools/vos/replay_adapter.py) is the producer half, and
it states no address, offset, width or draw site of its own. A window's base and
extent are read from [the composition](../../../model/config/verifiedos.json), a door's
offset from the `let ROT_*` declaration in [rot.sail](../../../model/model/sys/rot.sail)
and its admitted access width from the arm's own `'n ==` guard,
the window-to-handler routing from `mmio_read` and `mmio_write` in
[platform.sail](../../../model/model/sys/platform.sail), and whether a door reaches the
entropy root from the model's own call graph. Run
`python tools/run.py test --only replay_adapter` for the
[controls](../../../tools/tests/test_replay_adapter.py), which state what the model
carries now, so a door added, an offset moved or a third caller of the root fails
there rather than quietly changing what a record accounts for.

A door stands in one of three relations to the root. A read whose handler calls
the root in its own body returns the drawn word, so a commit trace carries it and
the adapter seals it into an entropy event. A write whose handler reaches the root
only through a call carries nothing across the fabric, and its store retires `Ok`
whether the call drew or not. Every other door adds no event, the adapter
attributing an event to a draw and never to a later read of its result, which is
what keeps a capture's entropy events the draws rather than the RoT traffic around
them. `ROT_WDT_NONCE` is such a read, and is treated below. An access at a width
the arm does not admit is no access of that door at all, having reached the
handler's fault arm. A handler that reaches the root with no offset arm to
attribute the draw to is refused rather than adapted.

### The root observer and the limits of a bus trace

The model's two non-test callers of the root are the `ROT_TRNG_DRAW` door read and
`watchdog_issue_nonce`. The second is the draw S6 is asked to intercept beside the
MMIO draws, and it cannot be inferred from a bus trace for a structural reason
rather than for want of effort. The nonce is issued inside the RoT with no bus
transaction accompanying it, and the [commit-trace
schema](../../assurance/differential-corpus.md) carries retires, register and CSR
writes, data reads and writes, and traps, so an internal draw is not a record that
dialect can express. Neither is the outcome that would let one be inferred:
`watchdog_pet` draws only on its accepted arm and `watchdog_arm` only where the
bite has not latched. A reader of a trace sees that the site was reached, and
never whether it drew or what it drew.

The adapter therefore refuses. A write to the pet or arm door with no
independently supplied account of the internal draw refuses the whole capture and
names the site. The operational form of that case, this contract's injected
unrecorded watchdog draw, waits on a real producer. An account may be supplied on
the same footing as the binding and the expected count, and it may decline, which
is the recorder's existing promise that no value was consumed; the host verifies
neither answer. The [entropy-root observer](entropy-observer.md) supplies
the missing observation boundary: every root invocation synchronously reports
its outcome to the C++ callback interface, including internal watchdog draws.
`RootProducer` in [replay_adapter.py](../../../tools/vos/replay_adapter.py) seals
successful callback values through an injected primitive and submits them to the
bounded recorder. Refusals add no event; capture failure latches. The root
producer replaces the bus-derived entropy producer for that capture, so the
same MMIO draw is not recorded twice. The native callback harness exercises
actual generated Sail callers. A production seal, writer, authenticated capture
envelope and paired replay are still owed.

The nonce is a secret-class draw at its source and stays one although
`ROT_WDT_NONCE` reads it back, the classification being the source's and never the
consumer's, and R-16-015 naming protocol nonces among the root's draws. A replay
value comparison would therefore have to exclude that door, its bytes being
readable and inside R-16-019's secret-entropy cone. Nothing in this tree decides
that scope, there being no comparator here for it to bound.

## Reuse and security boundary

The existing [commit-trace grammar](../../assurance/differential-corpus.md) and
[trace reader](../../../tools/vos/trace.py) provide local retired-instruction anchors
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
and security primitives exist, fixture tests discharge only the reader's stated
predicate, the callback recorder's admission and refusal behavior, and the
adapters' derivation and refusals. S6 remains open as owner of operational
recording and of integration against this contract. The completed firmware and
crypto statements supply dependencies, not operational recording or sealing
credit; S6 owes their actual implementations before claiming replay.

## Operational qualification

Clause by clause, against the requirements this contract views. Discharged means
a check in this tree decides it now; open names the artifact owed and its owner,
never a date.

| Clause | Discharged | Open, and owed by |
| --- | --- | --- |
| R-15-241, every draw accounted for | The model's draw sites are read from its call graph rather than listed, so a site it gains is a failing check; the site whose word crosses the bus produces a sealed event, and the site that does not refuses the capture. | The synchronous root callback supplies internal-draw observation. Operational accounting still needs the trusted callback binding, the RoT firmware's record writer (M3.2) and the sealing primitive (M3.4). |
| R-16-015, the closed four-source set | The reader admits exactly the four tags; the adapter refuses a request naming a source whose production interface is absent instead of synthesizing a value, and its one producer refuses any endpoint the composition does not class as entropy, so no caller selects a source by choosing an identity. | Three of the four have no producer. The slow-clock phase question below is a register act, not a tool's. |
| R-16-016, public nondeterminism verbatim | The reader preserves public bytes exactly, and the recorder puts them through the endpoint's own validator before admitting an event. | Every public producer, and the interface schemas that would give those validators a meaning. |
| R-16-017, secret nondeterminism as a sealed commitment | An entropy payload is opaque at the reader and at the producer. The trace-driven producer hands the drawn word to an injected primitive and records only its result; a control asserts the drawn word is absent from the finished bytes, a producer with no primitive injected produces nothing, and one aimed at a public endpoint is refused before it can seat sealed bytes in a `value`. | The primitive itself (M3.4), and any evidence that opaque bytes are sealed, which shape cannot supply. |
| R-16-018, substituted entropy preserving the CT-scope observations | The two-class split that makes substitution possible is enforced at both ends of the body. | The substitution and the run that would exercise it. |
| R-16-019, the exactness scopes | n/a: nothing in this tree decides an exactness scope, there being no comparator for a scope to bound. | The classification of the nonce door, which is stated above and by nothing that checks it, and the paired run that would compare anything at all. |
| R-16-020, candidate check and gated declassification | The body carries no recoverable draw, and the adapter retains the drawn word nowhere after handing it to the seal. | Both facilities, with the powerbox and lifecycle gates the entry states. |
| R-16-021, the on-device verbose sink | n/a: nothing here is on-device. | The sink and its lifecycle gate, entirely. |
| R-16-022, the exported record against the signed root | The binding names the base-image root, composition and input trace, and the reader compares it against an independently supplied identity rather than a self-declared one. | The authenticating envelope. A well-shaped binding is not authentication, and the nonce readback named below is the envelope's to exclude or to seal. |

**R-16-015's closed set names no source for the RoT's independent slow clock.**
`ROT_WDT_TICKS` exposes its phase and a windowed pet outcome turns on it. In the
model the counter is deterministic because nothing advances it, but on the composed
die R-15-196 makes that clock one of the genuinely asynchronous boundaries, none of
them modeled as fixed-latency. Either the tick door is a source the closed set
admits by amendment, or R-16-019 states that it is outside the replayed scope. The
register decides that; no adapter may, and none here does.

## What is still owed, and by whom

- **Binding the root observer to the operational recorder.** The synchronous
  [observer and its acceptance](entropy-observer.md) expose every draw;
  a capture must install the trusted callback and provide the sealed writer and
  its independently authenticated schedule point.
- **The sealing primitive** (M3.4) and **the RoT firmware's record writer** (M3.2),
  the second being the side that can see an internal draw and state it.
- **Real recording against a running model.** No command persists a commit trace
  today, and the adapter's controls are written trace text exercising real adapter
  decisions. Whether a refused draw leaves any record is a question only a run
  settles.
- **Public interface validation**, which waits on the three absent production
  interfaces the source table already names and on the schemas that would give a
  validator its meaning.
- **Paired Sail replay.** None is attempted here and none is claimed.
- **S5's source characterization**, which R-15-241b's sample budget and
  R-15-241c's claimed entropy rate are sized against.
- **A producer for `point.slot`.** The adapter takes it as the caller's declared
  input because R-11-017's composed operating point, TDM schedule and watchdog
  windows are one artifact that does not exist yet.
- **A statement about the nonce readback**, owed by the authenticating envelope.
  R-16-015 names protocol nonces among the root's draws, so `ROT_WDT_NONCE` returns
  a secret-class value over the fabric. R-16-017 keeps it out of this body, which
  carries a commitment and never a value, but whether an artifact bound beside the
  body under `input_trace` may carry that readback verbatim is what R-16-022's
  *without a secret payload* decides, and no artifact in this tree produces one yet.
  The obligation is named here before it can bite rather than discovered in an
  export.
- **A register act on the slow-clock phase**, as stated above.
