# Static-memory capacity corpus and byte ledger

The [research agenda](../background/static-memory-research.md) asks which physical
reservations are unavoidable and which program or placement changes improve useful
capacity. [static_memory_corpus.py](../../tools/vos/static_memory_corpus.py) supplies
replayable synthetic inputs and a diagnostic ledger for that question. The
[requirements register](../requirements-register.md) remains authoritative. These
fixtures supply no measured product roster, execution-cost certificate, new
admission rule or runtime telemetry mechanism.

## Reproducible inputs

`corpus(source_revision)` emits independent case dictionaries. The named parser,
session, ring, saved-state, frame and inference examples are bounded model traces,
not implementations of those services. Crossing lifetimes, uneven aligned extents,
simultaneous retirement and delayed device completion exercise particular limits.
The generator has no randomness or runtime demand inputs. Its literal byte sizes
and ordinal event ticks are deliberately small model quantities; neither is a
measurement of the named service.

Every case records its source revision, the generator's actual SHA-256, a manifest
identity, a demand envelope, cost assumptions, telemetry label, service-contract
label and reuse assumptions. The manifest hashes its schema, generator path, case
name, mode, arena declarations, object declarations and diagnostic requests. The
source digest binds the generator contents even when its checkout has uncommitted
edits. Labels identify the evidence's scope; they do not authenticate a workload or
prove that a source revision is a deployed image.

The demand envelope describes a finite declared trace and its bounded object
occurrences and horizon. It explicitly declines an all-execution bound. Target
cycles, bandwidth and energy are unknown. Emitted code, descriptors and other
metadata, bank traffic, deadlines and complete image reservations remain unmodeled
costs. A comparison over these inputs cannot claim that an actual service fits a
product budget or that a transformation preserves its deadlines.

## Model shape

A case supplies `name`, `provenance`, `mode`, `arenas` and `objects` to the
[independent placement model](../../tools/vos/static_memory.py). Root metadata is
documentary. Arena and object records have exact fields so that a supplied
placement constraint cannot silently disappear as an ignored annotation.

Each arena has `id`, `owner` and positive integer `capacity`. Its address interval
is `[0, capacity)`. Different arenas have separate physical backing even if their
relative offsets are equal; their capacities cannot be borrowed or combined to
satisfy a request to one arena.

Each object has `id`, `arena`, `size`, `payload`, `alignment`, `base`, `start`,
`payload_end`, `authority_end`, `sweep_end` and `reuse`. `size` is its entire charged
contiguous slot, and `payload` is a useful prefix no longer than that slot. The
base satisfies the declared integer alignment and the complete slot stays in its
arena. Those generic alignment inputs do not establish CHERI bounds
representability, an island or bank assignment, or admission.

The ordered timeline is:

```text
start <= payload_end <= authority_end <= sweep_end <= reuse
```

The slot occupies physical storage throughout `[start, reuse)`. Equal boundaries
use half-open intervals: an end event precedes a new start at that tick. The
fixture assumes each declared completion event succeeds. A timestamp is not the
[Q22 completion and reuse predicate](../assurance/revocation-qualification.md):
real reuse needs the complete resident, saved, borrowed, proxy and device authority
barrier, a full sweep started after that barrier, and required initialization.
These inputs represent none of those proof witnesses.

Useful saved state remains payload while its application is inactive. In this
simple model `payload_end` also starts release and Quiescing; a richer service may
need distinct last-computation, logical-release and retained-state endpoints.
`event_times(case)` returns the boundaries at which a charge can change, including
the final idle state.

## Disjoint physical charges

`ledger(case, time, alignment)` first checks the standing placement. It partitions
every arena by physical interval and assigns each byte exactly one charge:

- `useful_payload` is the useful prefix of a live object before `payload_end`.
- `slot_slack` is the remainder of that live object's slot during the same phase.
- `retained` charges the whole slot from `payload_end` through `authority_end`.
- `quarantined` charges the whole slot from `authority_end` through `sweep_end`.
- `initializing` charges the whole slot from `sweep_end` through `reuse`.
- `idle_reserved` covers declared slot backing with no current occupant.
- `layout_gaps` covers undeclared bytes below the maximum reserved end.
- `unreserved_tail` covers the remaining arena bytes above that end.

Retired phases include their slot padding, so adding live slack to a retained or
quarantined slot would count the same bytes twice. Slots overlaid at disjoint times
contribute their physical union to `reserved_backing`, not the sum of their object
lengths. `reserved_span` is the maximum declared slot end; it includes interior
layout gaps. These descriptive quantities are not additional additive charges.

For every owner, arena, mode and time, the report includes the physical segments,
all disjoint charges, occupied bytes, unreusable retired bytes, payload utilization
and capacity conservation. Occupancy includes payload, slack, retention, quarantine
and initialization. The report preserves the input provenance and telemetry
labels. Total physical charges may be summed for reporting, while the arena-local
capacity restrictions remain in force.

## Geometric fit and typed refusals

The report distinguishes `largest_free_aligned_extent`, a geometric interval after
rounding its free starting offset to the query alignment, from
`largest_idle_declared_slot_extent`, an existing wholly idle slot whose fixed base
satisfies that alignment. Free geometry can include layout gaps and unreserved
tail; it does not create a declared runtime slot.

`diagnose_request(case, time, owner, arena, size, alignment)` checks an instantaneous
request against those existing slots. Its typed refusal reasons distinguish an
unknown arena, foreign ownership, an inadequate slot size, incompatible slot-base
alignment, occupied slots and pending safe reuse. Idle bytes belonging to another
owner cannot turn a refusal into a fit. The report also exposes free physical
bytes, so a size-class refusal can be seen beside its stranded capacity.

A `fits-at-instant` result supplies only slot geometry. It carries no requested end
time, future non-overlap argument, binding certificate or semantic completion
witness and explicitly grants no runtime permission. Such a result cannot
authorize online placement or allow a new tenant to outlive the next declared
occupant. Sample requests are diagnostics and do not change the trace's demand.

## Q5 bridge and validation

`q5_bridge(root, source_revision)` calls the existing
[Q5 reader and exporter](placement-search.md), preserves that export whole, and
reports its standing refusals and per-island scores. It hashes the actual proof
source and participating tools. Its proof-witness provenance is separate from
the synthetic service labels.

The bridge deliberately leaves the operational ledger unavailable. The exported
plan lacks an owner and the payload, authority-completion, sweep and initialization
endpoints this ledger needs. Its live intervals cannot be relabeled as safe-reuse
proofs. A real composed roster and complete demand and cost contracts remain inputs
owed by the [implementation plan](implementation-checklist.md), including Q5b's
product comparison.

The focused `python tools/run.py test --only static_memory_corpus` checks
conservation against an independent byte-at-a-time oracle at every fixture tick,
refusal boundaries, retained saved state, delayed device authority, equal-time
rebinding, aligned free extents and preservation of Q5's missing fields. These
checks validate the diagnostic instrument against its bounded model. Equivalent
service measurements, alternative service promises and product admission evidence
remain separate outputs.
