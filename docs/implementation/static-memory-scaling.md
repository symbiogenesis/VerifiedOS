# Static-memory scaling experiments

> Non-normative host research. The [requirements register](../requirements-register.md)
> controls admission. These generated traces and the Q5 proof witness contain no
> measured product roster, qualified lifecycle service rate, target execution cost,
> or certificate for a composed image.

The [research agenda](../background/static-memory-research.md)'s scaling experiment
compares checked placements on explicitly identified synthetic families. The
[generator and report](../../tools/vos/static_memory_scale.py) own their formulas,
settings and result fields. The [placement oracle](../../tools/vos/static_memory.py)
owns feasibility and bounded exact search; the [existing Q5 exporter and enumerator](../../tools/vos/memplan.py)
retain their own candidate set and admission predicates.

## Replay and receipt

Run from the host checkout:

```console
python tools/run.py static-memory scale --json
python tools/run.py static-memory scale --sizes 8,32,128,512,1024 --max-nodes 100000 --q5-max-leaves 256 --json
python tools/run.py static-memory scale --sizes 8 --max-nodes 1 --q5-max-leaves 1 --json
python tools/run.py test --only static_memory_scale
```

The default sizes are the generator's `DEFAULT_SIZES`; `--sizes` replaces that set,
with the generator's `MAX_SIZE` bounding each requested object count. The independent
Q5 leaf limit prevents its search from inheriting the research oracle's candidate-base
budget. Q5 counts whole-plan leaves and pruned assignments separately: a leaf limit
does not bound visits to prefixes or wall time, and a heavily pruned island can still
cost more than the synthetic families. These limits are deterministic work limits,
not a hard real-time scheduler.

The report keeps `reproducible` results separate from `host_measurements`.
Reproducible input includes each full contract, its hash, source revision and source
byte hashes, family, size and work settings. Candidate witnesses, per-arena spans,
lower bounds, remaining gaps, exact-search status and optimality replay are included.
`result_sha256` binds this reproducible block; elapsed time is outside that digest.
Host elapsed seconds include checking and search, exclude synthetic generation,
and measure neither target execution nor a target image build. Concurrent host work
can change them.

## Families and charged lifetimes

Each object receives a deliberately padded, globally disjoint standing address
within its arena. This supplies an independently checked fallback even when a
search has no work budget. Its capacity is part of the synthetic contract, not a
device-memory recommendation.

- `laminar` uses entry and exit times from a finite binary tree. Sizes vary, alignment
  is unrestricted, and children can reuse storage after their subtrees end.
- `crossing` uses a moving window of overlapping lifetimes. Its width grows with
  object count, making the conflict density grow rather than keeping a constant
  toy working set at every size.
- `heterogeneous-aligned` varies sizes, alignments, start times and durations across
  separate arenas with distinct synthetic owners. An improvement in one arena
  cannot compensate for growth in another.
- `burst-safe-reuse` supplies burst arrivals with distinct payload death, authority
  release, sweep completion and reuse milestones. Placement charges the entire
  physical extent through reuse. These supplied milestones exercise accounting;
  they do not establish that a real containment or sweep implementation meets them.

The small cases are compared with bounded integer enumeration and independent
optimality replay. Larger cases retain the independently computed peak charged load
as a lower bound. A feasible span equal to that load establishes span optimality for
the fixed trace even when the exact search declines its object count. A positive
remaining gap only bounds the unknown optimum: it can include both a placement
restriction and heuristic suboptimality. An unreplayed exact claim never raises
the report's trusted comparison bound.

The assembled best witness selects the smallest complete, checked placement for
each independent arena and passes through the checker again. Interrupted or failed
heuristics retain their standing placements. An incomplete exact search retains its
standing primary placement and does not contribute a partial search candidate to
the assembled best witness. A completed heuristic from the same run can still
supply a checked candidate. The comparison's `selected_placement` remains the
standing plan until exact search and independent optimality replay complete;
`best_feasible_placement` and
`best_candidate_matches_standing` describe candidate evidence separately.

## Q5 comparison

The report includes Q5's actual export and declared grid. The research projection
uses addresses relative to each island and the same candidate step. Opaque island
labels identify partitions; the projection does not infer security owners. Q5's
live-end field is copied into the placement model's completion fields solely to
compare its mathematical placement problem. The missing owner and operational
completion contracts remain explicit in the receipt.

Every heuristic candidate is translated back to absolute Q5 bases and rechecked
by Q5's original whole-plan predicates. The Q5 candidate scores remain distinct
from the research projection's placement acceptance. A refusal preserves the Q5
standing bases and makes the report fail. Enumeration retains standing bases when
truncated or when no better candidate is found; its best observed feasible span is
still reported as research evidence. A load-equality span certificate can coexist
with incomplete enumeration: it settles that span without claiming the candidate
set has been exhausted. A complete enumeration certificate concerns the declared
grid, not every alignment-legal address outside it.

## Scaling improvement and remaining work

The existing first-fit heuristics consider zero and aligned ends of interfering
objects. Rechecking every interfering extent for every candidate can perform cubic
work in a dense lifetime family. The conflict scan now sorts blockers once for each
object and moves one cursor forward as candidate bases increase. A blocker ending
at or before a candidate is discarded; the earliest remaining blocker decides
whether any occupied extent overlaps it. Later blockers cannot start earlier.
This preserves candidate order, tie breaks and work-budget accounting while reducing
this part of placement to quadratic-logarithmic worst-case work over a dense family.
Independent placement checking remains separate and quadratic.

The [focused tests](../../tools/tests/test_static_memory_scale.py) compare this scan
with a direct pairwise reference, including interrupted and capacity-refused attempts,
and exercise small exact optima, large lower bounds, Q5 rechecking and receipt replay.
The finite crossing comparisons preserve the prior heuristic results; host timing
can measure the implementation improvement but is not an algorithmic guarantee.

This experiment supplies scalable synthetic comparisons and a Q5 bridge. It does
not add a solver, change schedules or lifetimes, move ownership, establish a
parameterized-complexity theorem, or close the research agenda's coupled-search and
actual-roster tasks. The heterogeneous aligned family exposes remaining gaps that
need stronger lower bounds or better placement before any such conclusion. Target
build time, admitted-workload improvement and composition-level costs remain open.
