# Replaying the static-memory research experiments

This host artifact starts the [static-memory research agenda](../background/static-memory-research.md).
The [baseline](static-memory-baseline.md) states the mathematical assumptions and
requirement gaps; the [corpus contract](static-memory-corpus.md) defines the byte
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
python tools/run.py static-memory scale --sizes 8 32 128 --max-nodes 100000 --q5-max-leaves 256 --json
python tools/run.py test --only static_memory
```

`corpus` emits the declared witness contracts, event snapshots, request diagnoses
and the bridge to Q5's existing exporter. `--case NAME` selects a witness named in
that output. `--contract FILE` selects a supplied research contract instead.
`check` reads a candidate list of `{id, arena, base}` objects, preserving the
contract's other fields; omitting `--candidate` checks the standing bases.
The input hash covers the same bytes that are parsed. Source hashes identify the
working-tree implementation beside its Git revision and dirty-state flag.

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
These quantities apply to that declared model; arbitrary CHERI representability,
bank selection, restricted base sets and all-execution lifetime extraction are
outside it.

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
No guest proof, compiled-service equivalence or target execution measurement is
claimed by these tests.

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
| `structure` | The [laminar constructor and deletion witnesses](static-memory-baseline.md#executable-construction-and-structural-witnesses), including an aligned counterexample checked by the exact oracle | Finite validation and an executable construction; the general mechanized theorem and source-lifetime bridge remain open |
| `transform` | An [executable bounded frame service](static-memory-transformations.md) with retention, fixed chunks, tiling and recomputation variants | Abstract work and explicit modeled storage; target code, physical costs and deadlines remain unqualified |
| `reclaim` | [Fixed sweep schedules and retirement phases](static-memory-reclamation.md), with Q22 barrier refusals and byte/service comparisons | Synthetic guaranteed service premises; qualified hardware rates and production holder coverage remain open |
| `scale` | [Larger deterministic families and the Q5 comparison](static-memory-scaling.md), with feasible spans, lower bounds, gaps and host times | Synthetic workloads and Q5's existing witness; the actual product roster remains absent |

`scale --sizes` selects positive object counts. `--max-nodes` bounds each research
search and `--q5-max-leaves` bounds the existing Q5 enumerator independently.
Increasing a budget changes the experiment; elapsed host time is a measurement,
not reproducible solver evidence. A best candidate does not replace the standing
plan on incomplete search. No action installs a plan or changes a requirement.

## Disposition of the remaining experiments

The baseline, witness corpus, ledger and oracle provide inputs for subsequent
research. Their existence does not close the broader agenda items that require
a representative service, a mechanized theorem or a real composed roster.

| Work | Evidence needed next | Existing consumer |
| --- | --- | --- |
| Reconcile the lifetime and peak-equality claims | An admitted-language lifetime extraction theorem and reviewed register wording, including the existing overlap-predicate inversion | Q5 and the memory-plan proof owner |
| Scale planning | A comparison on the actual composed roster and target constraints, following the synthetic scaling and Q5 witness comparison | Q5b |
| Regions, phases and bounded chunks | Target compilation and equivalence, complete authority/DMA obligations, and qualified physical costs for the executable service experiment | Q5b with the service owner |
| Rematerialization, tiling and fusion | Emitted-code worst-case work, traffic, image size and unchanged service deadlines | Q4, Q5b and Q8 |
| Reclamation scheduling | A complete holder and device barrier, a worst-case retirement envelope and qualified sweep and initialization service | Q22a, M4.4 and R2 |
| Restricted-lifetime complexity | A general algorithm and complexity proof, or a hardness reduction, under the baseline's binary input encoding | Research agenda |
| Relocation, phases or lending | A measured baseline limitation, an explicit changed-assumption record and authority, timing and information-flow proofs | Q22 and Q10 |
| Composition comparison | M7.1's actual roster and the same functional contract and product limits on both sides; ablations that charge each byte once | Q5b and Q10 |

The emitted-image half of the rematerialization row has no producer in this tree:
the Bedrock2 lowering loop stops at C and a plain RV64 assembly census, and the
corpus assembler reads this repository's own dialect rather than a C compiler's
output, so an image figure waits on M1.2f.

The research artifact remains local and replayable in the repository. External
publication, peer review, additional dependency incorporation and production
qualification are separate acts. No research hypothesis or architecture change
is accepted by a green host run.
