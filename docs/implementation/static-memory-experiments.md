# Replaying the static-memory research experiments

This host artifact starts the [static-memory research agenda](../background/static-memory-research.md).
The [baseline](static-memory-baseline.md) states the mathematical assumptions and
remaining source-to-plan obligations; the [corpus contract](static-memory-corpus.md) defines the byte
accounting and synthetic workload premises. The results are development evidence
for Q5 and Q22, not a new admission path or a product-capacity measurement.

## Inputs and replay

Run from the repository through its ordinary host entry point:

```console
python tools/run.py static-memory corpus --json
python tools/run.py static-memory compare --max-nodes 100000 --json
python tools/run.py static-memory check --contract case.json --candidate candidate.json --json
python tools/run.py static-memory structure --json
python tools/run.py static-memory transform --json
python tools/run.py static-memory reclaim --json
python tools/run.py static-memory modes --json
python tools/run.py static-memory scale --sizes 8 32 128 --max-nodes 100000 --q5-max-leaves 256 --json
python tools/run.py static-memory repr --json
python tools/run.py static-memory mutants --json
python tools/run.py static-memory envelope --json
python tools/run.py static-memory phases --json
python tools/run.py static-memory lending --json
python tools/run.py static-memory manifest --replay --json
python tools/run.py test --only static_memory
```

`corpus` emits the declared witness contracts, event snapshots, request diagnoses
and the bridge to Q5's existing exporter. Each contract also carries the agenda
families it witnesses, the coverage table computed from those labels, its own cost
assumptions and a demand series projecting each arena's charged load, its peak and
the standing span. `--case NAME` selects a witness named in
that output. `--contract FILE` selects a supplied research contract instead.
`check` reads a candidate list of `{id, arena, base}` objects, preserving the
contract's other fields; omitting `--candidate` checks the standing bases.
The input hash covers the same bytes that are parsed. Source hashes identify the
working-tree implementation beside its Git revision and dirty-state flag.

An explicit `--max-nodes` is supported only by `compare` and `scale`. Other actions
must reject it as a usage error before running an experiment or reading input files;
they must not report a search budget they never use. Both supported actions retain
positive-budget validation and their existing defaults when the option is omitted.

The contract contains an explicit mode, owner-bound arenas and object lifetimes.
It models one finite schedule per case. Independently solving two modes does not
produce one fixed layout valid for both: a global-mode interference relation or
an admitted family of bindings is a separate input and proof obligation. Byte
units and time units in synthetic cases come from their own assumptions. Neither
stands for measured hardware cycles, ECC storage or a product manifest.

Q5's exporter remains the reader of `MemoryPlan.v`. Its bridge reports fields
that the proof artifact omits instead of inventing owners, payload occupancy or
authority-completion times. The synthetic checker is a separate small-instance
model for investigating the research questions. It does not replace the
[placement-search admission predicates](placement-search.md).

## Walkthrough: three kinds of unavailable capacity

Replay these small witnesses individually:

```console
python tools/run.py static-memory corpus --case bounded-sessions --json
python tools/run.py static-memory corpus --case split-free-extents --json
python tools/run.py static-memory corpus --case delayed-device-completion --json
```

In each receipt, open `cases[0]`. Its `standing_errors` should be empty even when
its `requests` contain refusals: the standing placement is valid, and the requests
are hypothetical diagnostics. Read each request's `request`, `verdict` and
`reason` beside `contract.objects` and `timeline`. The timeline contains only
charge-changing instants; for a request between them, use the last snapshot at
or before `request.time`.

Within `timeline[*].rows[*]`, keep the `owner` and `arena` attached to each result:

- `free_physical_bytes` counts all free bytes; `free_extents` shows where they
  lie, and `largest_free_aligned_extent` measures contiguous free geometry.
- `largest_idle_declared_slot_extent` measures an available declared slot at the
  query alignment. Free geometry can exceed it without creating a larger slot.
- `unreusable_retired_bytes` sums `charges.retained`, `charges.quarantined` and
  `charges.initializing`. Follow `segments` and the object's `payload_end`,
  `authority_end`, `sweep_end` and `reuse` to distinguish those phases.

Read the witnesses in this order:

1. **Cross-owner stranded capacity (`bounded-sessions`).** The request to
   `a-pool` reports `slot-occupied` while `b-pool` has idle reserved backing.
   Asking for that backing as `owner-a` reports `foreign-owner`. The foreign-owner
   refusal omits geometry fields; inspect the timeline's `b-pool` row to see the
   idle capacity that cannot serve the requesting owner.
2. **Separated free extents and slot size (`split-free-extents`).** While the
   middle object is live, total free bytes exceed the largest free extent. The
   smaller request reports `fits-at-instant`; the larger reports `slot-size`.
   After the middle object's reuse boundary, free geometry coalesces but the
   larger request still reports `slot-size`: no declared slot grew. This witnesses
   the standing layout, without establishing an unavoidable offline placement gap.
3. **Delayed safe reuse (`delayed-device-completion`).** The earlier request
   reports `reuse-pending` while the device buffer is retained and restart work
   occupies the other slot. The later request reports `fits-at-instant` while
   unreusable retired bytes remain. Match its `slot_witnesses` base and size to
   `restart-workspace` in `contract.objects`: that slot has completed reuse while
   `device-buffer` is quarantined. Continue through the device buffer's
   initialization and reuse events to see its backing become idle.

Every request retains `runtime_permission: false`, including a fit. The
[corpus contract](static-memory-corpus.md#geometric-fit-and-typed-refusals) scopes
this to instantaneous geometry; the declared completion times assume successful
barriers and do not supply target safe-reuse evidence.

## What comparison decides

The deterministic heuristic candidates move bases within each arena. The exact
search enumerates bounded integer layouts with the same extents, alignment and
release-to-reuse intervals. It records `charged_load_lower_bound`, `best_span`,
`proven_lower_bound`, `optimality_gap` and `best_span_over_load` separately for
each arena. The optimality gap is the best span minus the proved lower bound;
it is zero for a completed optimum even when the best span exceeds live load.
That excess is `best_span_over_load`, and at an optimum it is unavoidable under
the declared constraints. An incomplete run conservatively retains the live-load
lower bound. Gaps are null when no feasible candidate exists. The per-arena
figures refer to `best_placement`, which can differ from the preserved standing
`placement` on a cutoff.
These quantities apply to the declared model. The optional
[legal-position layer](static-memory-representability.md) adds the frozen format's
representability granule. Remaining format predicates, bank selection, other
restricted base sets and all-execution lifetime extraction stay outside it.

A placement certificate is checked independently of the search order. An
optimality claim also needs its lower bound: equality with charged live load
or completed enumeration below the claimed span. The replay verifier checks
that evidence independently, checks that the primary placement matches the
optimum witness, and checks each arena's owner and derived bound fields. The
replay result states this scope; search traces and timing are not replayed.
Its own work budget can expire, leaving replay
incomplete even when the producer finishes. Search time is measured by the host
clock and identified as a varying measurement; candidate order and node budgets
are reproducible settings.

An exhausted search budget reports `incomplete`, preserves the valid standing
placement and keeps any candidate improvement separately. It never reports
infeasibility from missing work. An invalid candidate exits with a refusal;
malformed or unreadable input is a distinct failure. A successful command can
report an incomplete experiment, so downstream consumers inspect the receipt's
status before claiming optimality. No command installs or rewrites a plan.

The focused tests include independent finite enumeration and mutations of the
contract and candidate boundaries. The full host gate checks integration.
These host tests establish no compiled-service equivalence or target measurement.
The separate guest proof gate checks [laminar placement](static-memory-baseline.md#mechanized-statement)
and [list-functional service equivalence](static-memory-transformations.md#mechanized-equivalence);
their correspondence to the Python and emitted implementations remains scoped separately.

## Structural, transformation, reclamation and scaling experiments

These actions use declared research fixtures. They reject `--case`, `--contract`
and `--candidate` instead of silently substituting a built-in input for a supplied
one. Their outer `static-memory-experiment-v1` receipt records the action, Git
revision, working-tree state and source hashes; `experiment` contains the action's
own schema, inputs and results. A failed invariant returns a nonzero exit status;
an unfavorable comparison or explicitly incomplete bounded search is still a
valid research result.

| Action | Replay and result | Scope boundary |
| --- | --- | --- |
| `structure` | [Laminar placement](static-memory-baseline.md#executable-construction-and-structural-witnesses), [deletion-parameter algorithms and refuted decompositions](static-memory-structure.md) | The laminar theorem is mechanized separately; source extraction, general implementation correspondence and the remaining complexity question stay open |
| `transform` | [Frame-service variants and their list-functional equivalence](static-memory-transformations.md) | The theorem concerns functional models; interpreter and target refinement, physical costs and deadlines remain open |
| `reclaim` | [Holder-signature calendar terms and fixed reclamation schedules](static-memory-reclamation.md) | Synthetic service premises; target holder coverage and qualified rates remain open |
| `scale` | [Larger families, span bounds, checked candidates and Q5 comparison](static-memory-scaling.md) | Reports work completeness and remaining gaps; actual-roster and target comparisons remain open |
| `modes` | [Per-mode optima, one common layout and checked binding families](static-memory-modes.md) | Declared synthetic mode sets and switch premises; admitted mode extraction and a switch implementation remain open |
| `repr` | [Placement under the frozen representability granule](static-memory-representability.md) | Remaining encoding predicates, island and bank assignment, permissions and admission stay outside |
| `mutants` | [Placement and false-certificate mutation sweep](static-memory-mutants.md), with weakened-clause controls | Constructed finite violations; unmodeled target constraints remain unmutated |
| `envelope` | [Retirement envelopes and release-to-reuse bounds](static-memory-envelope.md), checked by bounded adversarial search | Declared finite budgets and horizons; actual service qualification remains open |
| `phases` | [Compositional phase certificates and minimized counterexamples](static-memory-phases.md) | Finite evidence and a conjecture; general soundness, barrier implementation and target timing remain open |
| `lending` | [Two-run lending and observation comparisons](static-memory-lending.md) | Finite slot/tick model; no ownership transition or cross-owner admission is implemented |
| `manifest` | [Computed artifact inventory and completeness](static-memory-artifact.md), with optional action replay | Completeness alone supplies no proof or product qualification |

`scale --sizes` selects positive object counts. `--max-nodes` bounds each research
search and `--q5-max-leaves` bounds the existing Q5 enumerator independently.
The span-bound scan carries its own deterministic limits and completion fields;
a valid partial lower bound is distinct from a completed scan.
Increasing a budget changes the experiment; elapsed host time is a measurement,
not reproducible solver evidence. A best candidate does not replace the standing
plan on incomplete search. No action installs a plan or changes a requirement.

The [compiled census](static-memory-census.md) uses the
[Bedrock2 lowering loop](../../tools/bedrock2-lowering/README.md) in the guest,
rather than a `static-memory` action. Its plain-RV64 instruction counts are a proxy
and do not qualify the platform's target code or timing.

## Disposition of the remaining experiments

The baseline, witness corpus, ledger and oracle provide inputs for subsequent
research. Their existence does not close the broader agenda items that require
a representative service, further mechanized refinement or a real composed roster.

| Work | Evidence needed next | Existing consumer |
| --- | --- | --- |
| Apply the reviewed baseline to admitted programs | An admitted-language lifetime extraction theorem joining the reconciled event-order and interference requirements to emitted plans | Q5 and the memory-plan proof owner |
| Scale planning | A coupled-search candidate compared against the deterministic heuristics and exact reference; a later product comparison uses the actual composed roster and target constraints | Q5b |
| Regions, phases and bounded chunks | Target compilation, refinement to the proved list-functional models, complete authority/DMA obligations and qualified physical costs | Q5b with the service owner |
| Rematerialization, tiling and fusion | Emitted-code worst-case work, traffic, image size and unchanged service deadlines | Q4, Q5b and Q8 |
| Reclamation scheduling | Target holder and device coverage, admitted restart and acknowledgement budgets, and qualified sweep and initialization service | Q22a, M4.4 and R2 |
| Restricted-lifetime complexity | A general algorithm and complexity proof, or a hardness reduction, for the remaining non-bipartite crossing case under the baseline's binary input encoding | Research agenda |
| Choosing the model across modes | An artifact stating which model it supplies, with the compiler or composition exporter's evidence that a declared mode set is the admitted one and that a switch barrier exists | Q5 and the memory-plan proof owner |
| Relocation, phases or lending | A measured baseline limitation, an explicit changed-assumption record and authority, timing and information-flow proofs | Q22 and Q10 |
| Capacity corpus | A roster carrying the per-pool manifest entries R-08-018b and R-08-018c presuppose; the declared families are synthetic witnesses and cover no measured instance | Q5b and M7.1 |
| Composition comparison | M7.1's actual roster and the same functional contract and product limits on both sides; ablations that charge each byte once | Q5b and Q10 |

The emitted-image half of the rematerialization row has no path in this tree.
The Bedrock2 lowering loop stops at C and a plain RV64 assembly census, and the
one image path that exists reads this repository's own frozen dialect through
the corpus assembler rather than a C compiler's output, so an image figure
waits on M1.2f, which the plan makes the item where generated C through
`ccomp` to `asm.py` and `image.py` closes.

The research artifact remains local and replayable in the repository. External
publication, peer review, additional dependency incorporation and production
qualification are separate acts. No research hypothesis or architecture change
is accepted by a green host run.
