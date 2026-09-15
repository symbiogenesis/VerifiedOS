# Composed-roster measurement instruments

This contract fixes the host-authorable instrumentation for M7.2 and M7.3 before
implementation. The [checklist](implementation-checklist.md)
owns their final acceptance: both still need M7.1's accepted composed roster and
its workload captures. The instruments analyze supplied observations; they do not
establish that a producer observed the machine completely or truthfully.

## Shared capture boundary

Each instrument reads a JSON capture and a separately supplied expected-identity
JSON object. The latter contains `roster_revision`, `image_sha256`,
`composition_sha256` and `capture_sha256`. The revision is a full Git object ID;
the digests are SHA-256 hex strings. The capture's `identity` contains the first
three fields and must match. Its actual file bytes must match `capture_sha256`.
The report preserves these identities and identifies its implementation inputs.
Hashes bind inputs; they do not establish producer authenticity or boot acceptance.

Both captures carry `schema_version: 1`, `complete: true`, and
`window: {start_tick, end_tick, tick_hz}`. The observation interval is half-open,
start inclusive and end exclusive, with positive duration and tick frequency.
Ticks, counts, bytes and costs are integers, never booleans, floats or negative
values. Objects have their declared fields only, and identifiers are nonempty.
Unknown fields, duplicate JSON keys, missing fields, repeated identifiers, invalid
domains and identities, and unfinished captures are refused. Completeness is a
producer assertion checked structurally, not an independent measurement.

The verdict distinguishes malformed input (exit 2), a well-formed capture exceeding
declared limits (exit 1), and a capture within the checked limits (exit 0).
Every report keeps milestone acceptance open and states its host-analysis scope.
Rates are exact numerator/denominator pairs; no rounded value decides a limit.
Fixtures are synthetic. No fixture becomes a member of the accepted roster.

## Allocation churn

The capture contains `domains`, `teardowns` and `sweep_quanta` arrays.

- A domain has `id`, `period_ticks`, `background_ticks_per_period` and
  `quarantine_capacity_bytes`. These positive composition constants define an
  independent accounting bucket, with background time at most its period. A
  producer aggregates domains sharing one reservation before supplying a bucket.
- A teardown has a unique `id`, `domain`, `retire_tick`, `reuse_tick`,
  `swept_capability_bytes` and `quarantined_bytes`. It records a kernel-mediated
  teardown and its attributed capability-bearing footprint. Both endpoints must
  be inside the observation boundary, allowing reuse at its exclusive end. A
  nonempty quarantined extent has a positive residence interval.
- A sweep quantum has `domain`, `start_tick` and `end_tick`, with positive duration
  entirely inside the observation boundary. Same-domain quanta cannot overlap.

Periods start at tick zero; both observation endpoints align with every supplied
domain's period. The capture begins and ends without outstanding quarantines and
includes all sweep service. Empty teardown and quantum arrays can represent zero
activity, but an absent accounting-domain set cannot.
Positive attributed swept bytes require at least one recorded sweep quantum in
that domain; this structural check does not establish coverage of those bytes.

The analyzer reports teardown counts and exact rates, total/mean/maximum attributed
swept bytes, and peak simultaneously quarantined bytes. Half-open residence
intervals release bytes before another retirement at the same tick. The footprint
is an attributed teardown measurement, not a charge for a second shared sweep.
Actual sweep time is counted once from the quanta, split across every period it
overlaps, and compared per period with the declared background reservation. A low
whole-window average cannot excuse an overfull period. Peak quarantine usage is
compared with the declared pool capacity.

Acceptance cases cover zero activity, exact capacity and time equality, overlapping
quarantines, adjacent release/retire boundaries, a quantum spanning periods, a
burst exceeding quarantine capacity, and per-period service excess hidden by a low
average. Malformed timing, open retirements, duplicate/unknown identities and
changed capture bytes must refuse. These measurements serve R-08-008a; they change
no containment bound, reservation or reuse rule under R-08-006 through R-08-008.
Observed reuse times supply no proof that retired authority is dead.

## Ring parameters

The capture additionally contains `declaration_sha256`,
`cost_unit: "declaration_units"`, and a nonempty `rings` array. The digest must match
the actual bytes of [the ring declaration](../../interfaces/ring-reference.json),
whose existing reader owns each world's capacity, batch and operation constants.
The analyzer reads these constants instead of restating a second table.

A ring has a unique `ring_id`, a declared `world`, and a nonempty `activations`
array. An activation has `tick`, `queue_high_water`, `notifications`,
`activation_overhead_cost` and `requests`. Ticks strictly increase within the
observation window. The high-water observation covers the interval from the window
start or previous activation through this activation; it is a producer-supplied
maximum, not a maximum reconstructed from sampled indices. Any tail after the last
activation is unmeasured and remains explicit in the report.

Each request has `operation`, `validation_cost`, `device_service_bound`,
`cancellation_cleanup_cost`, `completion_publication_cost`, `payload_bytes`,
`segment_count` and `notifications`. The operation names a declaration member;
its recorded charges, payload, segments and generated notifications are compared
individually with that member's declared bounds. The whole batch respects the
world's `max_batch_size` and every represented operation's `max_requests_drained`.
This conservative mixed-batch check claims no more concurrency than each record
allows. Queue high water respects the world's capacity.

Activation cost is the sum of the four recorded request charges and the activation
overhead charged once, compared with the declared slot budget. Empty drains are
permitted and still charge their overhead. Activation `notifications` records
observed hints for cadence independently of the per-request generated counts:
R-12-096 permits spurious and coalesced notifications. This instrument implements
no notification counter in the ring and proves no lost-wakeup property.
Each activation's observed count covers the interval ending at that activation,
starting at the prior activation or the window start. The rate denominator is the
observed span from window start to the last activation, exposed as
`observed_interval_ticks`. An observation only at the window's starting boundary
has no elapsed span and reports a null rate. An unmeasured tail cannot reduce the
reported observed cadence by entering its denominator.

The report gives per-ring queue/batch maxima, per-operation accounting, activation
costs and remaining budgets, observed notification totals and exact rates, and
activation gaps. Cost units are the declaration's abstract units; tick frequency
does not convert them into measured cycles or target WCET. R-12-101's composed
progress proof and executable capture producer remain separate obligations.

Acceptance cases cover declared-bound equality and one-past violations, mixed
operations, per-operation drain limits, payload/segment/cost/notification excess,
overhead that alone exceeds the slot, an empty spurious drain, strict chronology,
unknown worlds/operations, duplicate rings, and stale declaration/capture identity.
Observed maxima and cadence describe only the supplied finite capture.
