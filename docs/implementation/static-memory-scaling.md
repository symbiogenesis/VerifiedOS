# Static-memory scaling experiments

> Non-normative host research. The [requirements register](../requirements-register.md)
> controls admission. These generated traces and the Q5 proof witness contain no
> measured product roster, qualified lifecycle service rate, target execution cost,
> or certificate for a composed image.

The [research agenda](../background/static-memory-research.md)'s scaling experiment
compares checked placements on explicitly identified synthetic families. The
[generator and report](../../tools/vos/static_memory_scale.py) own their formulas,
settings and result fields. The [placement oracle](../../tools/vos/static_memory.py)
owns feasibility and bounded exact search; the [lower bounds](../../tools/vos/static_memory_bounds.py)
own what no legal placement can undercut; the [existing Q5 exporter and enumerator](../../tools/vos/memplan.py)
retain their own candidate set and admission predicates.

## Replay and receipt

Run from the host checkout:

```console
python tools/run.py static-memory scale --json
python tools/run.py static-memory scale --sizes 8 32 128 512 1024 --max-nodes 100000 --q5-max-leaves 256 --json
python tools/run.py static-memory scale --sizes 8 --max-nodes 1 --q5-max-leaves 1 --json
python tools/run.py test --only static_memory_scale
python tools/run.py test --only static_memory_bounds
```

The default sizes are the generator's `DEFAULT_SIZES`; `--sizes` replaces that set,
with the generator's `MAX_SIZE` bounding each requested object count. The independent
Q5 leaf limit prevents its search from inheriting the research oracle's candidate-base
budget. Q5 counts whole-plan leaves and pruned assignments separately: a leaf limit
does not bound visits to prefixes or wall time, and a heavily pruned island can still
cost more than the synthetic families. The bounds carry a third limit with its own
unit, one subset-enumeration transition or one live set examined per arena, so a
heuristic budget cannot decide how far a bound gets. These limits are deterministic
work limits, not a hard real-time scheduler.

The report keeps `reproducible` results separate from `host_measurements`.
Reproducible input includes each full contract, its hash, source revision and source
byte hashes, family, size and work settings. Candidate witnesses, per-arena spans,
every bound with the live sets it read, remaining gaps, exact-search status and
optimality replay are included. Each arena reports its charged load, the strongest
proved lower bound with the bound that supplied it, the best feasible span with the
candidate that attained it, and the remaining gap between the last two.
`result_sha256` binds this reproducible block; elapsed time is outside that digest.
Host elapsed seconds include checking, bounds and search, exclude synthetic
generation, and measure neither target execution nor a target image build.
Concurrent host work can change them.

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
- `two-instant-witness` repeats one gadget whose two charged instants share a single
  reservation and whose other objects are never charged together. It is a witness for
  the [two-instant bound](#the-two-instant-bound) rather than a scaling family: its
  difficulty does not grow with its object count, because its gadgets are sequential
  in time and reuse the same addresses.

The small cases are compared with bounded integer enumeration and independent
optimality replay. Every case, at any size, also carries the
[proved lower bounds](#proved-lower-bounds), which need no search and reach arenas
whose object count the exact search declines. A feasible span equal to the strongest
proved bound establishes span optimality for the fixed trace, and a span equal to the
charged load is the special case of that. A positive remaining gap only bounds the
unknown optimum: it can include both a placement restriction and heuristic
suboptimality. An unreplayed exact claim never raises the report's trusted comparison
bound.

The assembled best witness selects the smallest complete, checked placement for
each independent arena and passes through the checker again. Interrupted or failed
heuristics retain their standing placements. An incomplete exact search retains its
standing primary placement and does not contribute a partial search candidate to
the assembled best witness. A completed heuristic from the same run can still
supply a checked candidate. The comparison's `selected_placement` remains the
standing plan until exact search and independent optimality replay complete;
`best_feasible_placement` and
`best_candidate_matches_standing` describe candidate evidence separately.

## Proved lower bounds

A bound here answers one question about one arena: no legal placement of its objects
has a smaller span. [The bounds module](../../tools/vos/static_memory_bounds.py)
computes four, each by restricting an arbitrary legal placement rather than by
searching for a good one, so a bound can be used to judge a search without trusting
it. Each is arithmetic over the declared finite integer model. None is a machine
checked theorem, none reads a candidate placement, and none accepts a requirement or
confers landing credit.

Two facts carry every proof below. Restricting a legal placement to a subset of the
objects leaves a legal placement of that subset, because each constraint that remains
is one the subset already carried. Deleting objects never raises a span, the span
being a maximum over the objects that remain. Together: the least span of a restricted
problem is at most the least span of the whole arena. Alignment is an input constraint
throughout; none of this certifies CHERI bounds, and every arena is bounded on its own
because bytes in different arenas are not interchangeable.

### Charged load

The oracle's own [peak charged load](../../tools/vos/static_memory.py) is the first
bound and is imported rather than recomputed. Objects charged at one instant occupy
pairwise disjoint extents, so the span is at least their total size, and the bound is
the maximum of that total over the trace. The bounds module cross-checks the value by
naming the live set that attains it: a live set only grows at an object's start, so
the charged peak is attained at one of the starts the module enumerates, and a load no
live set attains is reported as a finding rather than passed over.

### The alignment block bound

Fix an alignment `A` that divides at least one live object's alignment and let `G` be
the live objects whose alignment is a multiple of `A`. Each member of `G` starts at a
multiple of `A`, so the `A`-sized blocks its extent meets belong to it alone: the next
member of `G` above it starts at or above its end and at a multiple of `A`, hence at
or above the end of its last block. Let `t` be the live object with the highest base.
Every other live object ends at or below `base(t)`, being disjoint from `t` and based
below it. Two counts of `base(t)` follow. The block count: when `t` is in `G`, its
base is a multiple of `A` and the blocks of the other members of `G` lie wholly below
it, so `base(t)` is at least `A` times their block count; when `t` is outside `G` the
highest member of `G` may straddle `base(t)`, and one block is given up. The byte
count: the sizes of all other live objects lie below `base(t)`, and so does the block
padding inside `G` that no live object outside `G` can cover, which is at least the
total padding less the total size of those objects. The bound is the larger count plus
`t`'s own size, minimized over the choice of `t`, which is unknown, and maximized over
`A`. It needs no search, so it is the bound that survives a live set too large to
enumerate, and it is at least the charged load by construction.

### The exact live-set bound

Sort the objects of one live set by base in a legal placement. Let `e(0)` be zero and
`e(k)` be the least multiple of the `k`-th object's alignment at or above `e(k-1)`,
plus that object's size. By induction the `k`-th base is at least `e(k-1)`, being at
or above the previous end, and is a multiple of its own alignment, so it is at least
that rounded-up value and its end is at least `e(k)`. The span is therefore at least
`e(n)`. Stacking the objects in any order at exactly those values is legal, so the
least span of the live set is the minimum of `e(n)` over the orders, and that is what
the module computes: it enumerates subsets, keeping for each the least end reachable,
which is the minimum over the orders of that subset. The result is exact for the live
set, and exponential in its size, so the report enumerates a live set only when its
known cost fits the remaining budget and withholds the bound otherwise.

### The two-instant bound

Two instants sharing objects constrain more than either alone, because a shared object
occupies the same extent at both. Keep the objects charged at either of two instants,
keep the disjointness each instant requires, and forget every other interference. A
relaxation of a restriction is still a lower bound. Objects charged at both instants
are disjoint from everything kept, two objects charged at only the first are disjoint
from each other, likewise two charged at only the second, and one of each may share
bytes. Sorting a placement by base again, each object starts at or above the highest
end already placed in each set it belongs to, and lowering it to exactly that aligned
front never raises a later object's front. What a partial placement leaves behind is
therefore a pair of fronts, a pair no smaller in both coordinates than another can
complete no better, and enumerating subsets while keeping the least such pairs is
exact for the relaxation. One instant is the case where every object is charged at
both, so a single enumeration serves this bound and the one above it.

The relaxation can exceed both single-instant bounds, and the focused tests require at
least one instance where it does among the small ones they generate. It can also equal
them, or be skipped where a bound in hand already exceeds what stacking the pair's
objects attains, and on the other four families one of those two happens. The receipt names the bound that supplied each
arena's strongest value, so a bound that decided nothing there is visible rather than
implied. The `two-instant-witness` family is where it decides: its charged load and
its exact live-set bound both fall below the span every candidate attains, and this
bound settles that span as optimal.

### What a bound is held to

A bound above an exact optimum is a defect, not a stronger result.
[The focused tests](../../tools/tests/test_static_memory_bounds.py) generate small
instances, take the bounded exact search's optimum wherever it completes, and refuse
any bound above it; they hold the live-set enumeration against an independent
enumeration of orders, the two-instant enumeration against an independent search over
aligned bases, and the block bound against a span that stacking attains. The
comparison itself refuses a bound above a span some checked placement already reached.
Budget exhaustion withholds a bound and never invents one: an exhausted arena reports
the charged load alone and says which bound it gave up. The bounds are also invariant
under the order the objects arrive in, which the tests hold by permutation.

R-05-104's criterion says no ILP machinery exists in the toolchain, its own subject
being the deleted implicit path enumeration technique and its LP solver. Nothing here
adds any: every bound is a counting argument or a bounded enumeration over subsets,
and every candidate is a deterministic single pass. R-05-105 is the rule to read
before proposing any of this for admission, a verified tool whose only yield is
tightening an already sound bound being inadmissible there. These bounds are host
research and are not proposed as an admitted analysis. Their yield in this experiment
is an optimality verdict about a checked placement, which decides whether further
search on that arena is worth anything, rather than a smaller number in a budget.

## Deterministic candidates and the lowering pass

The comparison keeps the [oracle's three first-fit orderings](../../tools/vos/static_memory.py),
by start time, by size descending and by retained lifetime descending, and adds three
in [the scaling module](../../tools/vos/static_memory_scale.py): by alignment
descending then size descending, by charged area descending, and by safe-reuse time
ascending. Each places every object at its lowest feasible base given those already
placed, which is zero or the aligned end of an interfering extent: a feasible base
that is neither is one alignment step above an infeasible base, so some interfering
extent ends inside that step and its aligned end is the base itself. The added
orderings reproduce the oracle's candidates exactly on the three orderings both
carry, which is what the focused tests hold them to, so the two statements of the
placement rule cannot drift apart silently.

The lowering pass re-places each object at its lowest feasible base given all the
others and repeats until nothing moves. A base only ever falls, the standing base
being among the candidates, so the sum of bases strictly decreases between passes and
the fixed point arrives in finite work. Interruption leaves a legal placement, every
accepted move preserving disjointness. The operator moves one object at a time and
cannot exchange two, so its fixed point is a local one and not an optimum. On these
families it improves the deliberately padded standing plan and finds every first-fit
candidate already at its fixed point; the receipt carries a row for a pass that moved
something and records `lowering_moved` on every source row that was already settled.

Every candidate goes through the independent checker before it enters the comparison,
the assembled best witness is checked again, and the standing plan remains the
selection until exact search and independent replay complete. The added candidates
change none of that discipline: they enlarge the set of checked witnesses the best
feasible span is taken over, and the receipt names which candidate supplied it.

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

## What closes, and what the remaining gap is made of

A gap closes when a proved bound and a checked placement meet at the same span, and
the receipt says which of each did it. That now happens on every laminar and burst
arena, where the charged load is attained; on the witness family, where only the
two-instant bound reaches the attained span; and on the heterogeneous aligned arenas
at the smallest size and on one arena above it, where an alignment bound rises above
the charged load to meet a candidate. Where a gap narrows without closing, both sides
moved: the alignment bounds rise above the charged load wherever alignments differ
within a live set, and the added orderings lower the best span on one heterogeneous
arena. None of this is a claim about optimality where the gap stays open, and none of
it is a target measurement.

Two kinds of gap remain, and they are not the same problem. Where alignment is uniform
across a family, as in `crossing`, every bound here collapses to the charged load,
because with unit alignment there is no padding to count and the live-set enumeration
returns the live set's own total. A small residual gap stays open there, and the
peer-reviewed separation between the optimum and the load that the
[research agenda](../background/static-memory-research.md) cites means neither the
candidate nor the bound is known to be the weak side. Where the live sets are larger
than the enumeration limit, as in the heterogeneous aligned family at its largest
size, the exact live-set and two-instant bounds are withheld and only the counting
bounds remain. Raising the budget does not settle that: the enumeration is exponential
in the size of one live set, so what is wanted is a stronger argument, not a longer
run.

This experiment supplies scalable synthetic comparisons, four proved lower bounds and
a Q5 bridge. It does not add a solver, change schedules or lifetimes, move ownership,
establish a parameterized-complexity theorem, or close the research agenda's
coupled-search and actual-roster tasks. A bound proved here concerns one arena of one
fixed synthetic trace under the declared integer model, with no pinning, bank, owner
or capability-representation constraint that a real placement would carry, and the
actual roster is still absent. Target build time, admitted-workload improvement and
composition-level costs remain open.
