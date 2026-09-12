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

## Disposition of the remaining experiments

The baseline, witness corpus, ledger and oracle provide inputs for subsequent
research. Their existence does not close the broader agenda items that require
a representative service, a mechanized theorem or a real composed roster.

| Work | Evidence needed next | Existing consumer |
| --- | --- | --- |
| Reconcile the lifetime and peak-equality claims | An admitted-language lifetime extraction theorem and reviewed register wording, including the existing overlap-predicate inversion | Q5 and the memory-plan proof owner |
| Scale planning | Larger identified inputs and a useful build-time comparison against the existing Q5 enumeration | Q5b |
| Regions, phases and bounded chunks | One executable service with equivalent outputs, explicit alias and DMA contracts, and all descriptor and staging costs | Q5b with the service owner |
| Rematerialization, tiling and fusion | Emitted-code worst-case work, traffic, image size and unchanged service deadlines | Q4, Q5b and Q8 |
| Reclamation scheduling | A complete holder and device barrier, a worst-case retirement envelope and qualified sweep and initialization service | Q22a, M4.4 and R2 |
| Restricted-lifetime complexity | A general algorithm and complexity proof, or a hardness reduction, under the baseline's binary input encoding | Research agenda |
| Relocation, phases or lending | A measured baseline limitation, an explicit changed-assumption record and authority, timing and information-flow proofs | Q22 and Q10 |
| Composition comparison | M7.1's actual roster and the same functional contract and product limits on both sides; ablations that charge each byte once | Q5b and Q10 |

The research artifact remains local and replayable in the repository. External
publication, peer review, additional dependency incorporation and production
qualification are separate acts. No research hypothesis or architecture change
is accepted by a green host run.
