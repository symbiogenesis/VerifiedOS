# Static-memory capacity corpus and byte ledger

The [research agenda](../background/static-memory-research.md) asks which physical
reservations are unavoidable and which program or placement changes improve useful
capacity. [static_memory_corpus.py](../../tools/vos/static_memory_corpus.py) supplies
replayable synthetic inputs and a diagnostic ledger for that question. This document
is non-normative and the [requirements register](../requirements-register.md) remains
authoritative: nothing here confers implementation landing credit or accepts a
requirement. These fixtures supply no measured product roster, execution-cost
certificate, new admission rule or runtime telemetry mechanism.

## Reproducible inputs

`corpus(source_revision)` emits independent case dictionaries. The named parser,
session, ring, saved-state, frame and inference examples are bounded model traces,
not implementations of those services. Crossing lifetimes, uneven aligned extents,
simultaneous retirement and delayed device completion exercise particular limits.
Further contracts deepen stresses the agenda names within those families: a clustered
retirement across several owners, an accepted device transfer holding authority for a
declared completion window, saved state carried across separated phases, a rotating
activation set beside a fixed resident weight set, and a crossing family whose exact
optimum exceeds its charged load. The generator has no randomness or runtime demand
inputs. Its literal byte sizes and ordinal event ticks are deliberately small model
quantities; neither is a measurement of the named service.

Every case records its source revision, the generator's actual SHA-256, a manifest
identity, its agenda coverage, a demand envelope and computed demand series, cost
assumptions, telemetry label, service-contract label and reuse assumptions. The
manifest hashes its schema, generator path, case name, mode, arena declarations,
object declarations and diagnostic requests. The source digest binds the generator
contents even when its checkout has uncommitted edits. Labels identify the evidence's
scope; they do not authenticate a workload or prove that a source revision is a
deployed image.

The demand envelope describes a finite declared trace and its bounded object
occurrences and horizon. It explicitly declines an all-execution bound. Target
cycles, bandwidth and energy are unknown. Emitted code, descriptors and other
metadata, bank traffic, deadlines and complete image reservations remain unmodeled
costs. A comparison over these inputs cannot claim that an actual service fits a
product budget or that a transformation preserves its deadlines.

## Agenda coverage

Each contract declares in its `covers` field which of the agenda's corpus families it
witnesses. The vocabulary is closed: `family_labels` refuses a label the agenda does
not name, refuses a repeated one and refuses a contract declaring none, so a mistyped
label fails to parse instead of quietly dropping a family from the table.
`family_audit` aggregates those labels into the coverage table the receipt carries:
every declared family, the contracts witnessing each, the families with no witness,
and the provenances the contracts actually carry. The table is computed from the
labels alone, so withdrawing a family's only witness moves that family into the
uncovered list rather than leaving a stale note beside it. Every contract carries the
same computed table, so a receipt selected with `--case` still states the whole
coverage position rather than one contract's corner of it.

A covered family is a witness at one finite declared trace. It is not a service
implementation, an admitted workload, or evidence that a real instance of that family
fits any budget. Two contracts covering one family exercise different stresses inside
it; they are not one measurement taken twice, and the count of contracts against a
family is not a coverage metric.

## Cost assumptions

The shared cost model fixes the storage and time units, the payload and size
conventions, the target costs that are unknown, and the charges that stay unmodeled.
Beside it each contract states three assumptions of its own: how its per-object useful
payload relates to its charged slot, what its alignment premise is, and why its arena
capacity is what it is.

They are stated because a bounded fixture's quantities otherwise read as arbitrary. A
capacity above the reserved span is a deliberate choice to keep free geometry visible
beside a refusal; a capacity equal to that span is a deliberate choice to remove it.
An alignment premise belongs at the contract because it is the premise peak equality
loses first, and because a reader separating a representation cost from a packing cost
needs to know which one a span is paying. A payload-versus-size note keeps declared
slot slack from being read as measured internal waste. None of these is a measured
target size, a capability representability rule or an admitted reservation.

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
and initialization. The report preserves the input provenance, coverage and telemetry
labels. Total physical charges may be summed for reporting, while the arena-local
capacity restrictions remain in force.

## The demand envelope of one contract

`demand_series` is the computed companion to the declared envelope. Per arena it
carries the charged load as a step function over the instants at which a charge can
change, that function's peak, the arena's capacity and the standing placement's span.
Per contract it carries the useful payload beside the retained, quarantined and
initializing bytes at those same instants, so retention is read against payload rather
than inferred from occupancy.

Every figure is projected from `ledger`, `event_times`, `peak_load` and
`placement_spans`, and nothing is accounted a second time. The peak is checked against
the separately swept charged-load bound before the series is reported, so a step
function disagreeing with that bound raises instead of being published as demand. A
contract whose standing span exceeds that peak says so through this series and through
the exact oracle; neither makes the standing plan wrong, and the
[baseline's inequalities](static-memory-baseline.md#executions-objects-and-physical-charge)
own the distinction between an unavoidable gap and planner suboptimality.

The series is a charged step function for one declared finite trace. Its peak is that
trace's charged live load, which is a lower bound on any legal span and is not itself a
placement. It is not a measured demand, not an envelope over admitted executions, and
not a statement that the declared capacity is sufficient for any real instance of the
family the contract witnesses.

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

## The absent roster, by inspection

No tracked artifact carries a real composed roster at this revision, and the corpus is
synthetic by that fact rather than by preference. The register already presupposes the
artifact that would supply one. R-08-018a records in a pool's manifest entry a live
range the admitted frame does not separate; R-08-018b records there the pool's chosen
size-class set and the internal waste that choice declares; R-08-018c decides
duplication by comparing two manifest entries' derivation source and element type
across owning compartments. Each of those entries reads per-pool manifest entries, and
nothing in this tree carries them: the memory plan's statement artifact declares by
name the fields it does not carry, the owner among them, and the
[scaling experiment's](static-memory-scaling.md) projection of that plan declares its
further operational inputs absent by name rather than inventing them.

The Q5 projection therefore remains the only bridge from a tracked artifact to this
ledger, and it reaches a placement grid rather than an operational demand. The coverage
table states the same position from the other side: every contract's provenance is the
synthetic witness one, none is a composed roster, and no generated contract may claim
otherwise. Until a roster exists, a coverage claim here is a claim about witnesses, and
the [agenda's corpus item](../background/static-memory-research.md) stays open on its
roster half by inspection rather than by an unfinished search.

The focused `python tools/run.py test --only static_memory_corpus` checks
conservation against an independent byte-at-a-time oracle at every fixture tick,
refusal boundaries, retained saved state, delayed device authority, equal-time
rebinding, aligned free extents and preservation of Q5's missing fields. It also
pins each earlier contract's manifest and parsed-contract digests, so a contract other
lanes already read cannot change while new ones append; refuses an unknown, repeated or
missing coverage label; checks the coverage table against a withdrawn label; replays
each arena's charged step function against an independent sweep of the declared
extents; reproduces the completion-window refusal at every instant of the declared lag;
reads the burst's deferred reuse out of the ledger; and checks that the crossing
witness's excess over charged load follows from its alignment premise by relaxing that
premise alone.

`python tools/run.py static-memory compare --case NAME` puts one contract through the
bounded exact oracle and its independent optimality replay. These checks validate the
diagnostic instrument against its bounded model. Equivalent service measurements,
alternative service promises and product admission evidence remain separate outputs.
