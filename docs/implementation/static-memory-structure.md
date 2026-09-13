# Static-memory structure: the deletion parameter

> Non-normative research. The [requirements register](../requirements-register.md)
> remains authoritative; nothing here changes an admission criterion, and research
> outputs confer no landing credit and accept no requirement. The proofs below are
> human-readable arguments over the baseline's finite integer model, not
> machine-checked theorems. Each claim is labelled as a peer-reviewed citation, an
> elementary argument proved here, a finite executable outcome, or an open question.

The [baseline](static-memory-baseline.md#structural-questions-left-open) leaves one
parameterized question open: with `k` the least number of reservation intervals whose
deletion makes the family laminar, is exact placement solvable in time `f(k)` times a
polynomial of the binary input length, or hard for some small fixed `k`? This
document settles the parameter itself, extends the exact solution from `k = 0` to
every family whose crossing graph is bipartite, refutes four candidate decompositions
by small witnesses at the least object counts its arguments and bounded sweeps admit,
states what an exact algorithm structured around the deleted objects can and cannot
rely on, and records the precise question that stays open.

## Problem statement and input encoding

An instance has `n` objects. Object `i` has a positive integer extent `w_i` and a
nonempty half-open reservation interval `J_i = [b_i, e_i)` with integer endpoints;
extents and endpoints are encoded in binary, so the input length is the sum of their
bit lengths and is unrelated to their magnitudes. There is one arena with origin
zero, every nonnegative integer base is legal, alignment is one, nothing is pinned,
and no owner, bank, bounds or multiple-execution constraint applies. A placement
assigns each object a base `a_i`; it is legal when any two objects whose intervals
intersect have disjoint extents `[a_i, a_i + w_i)`. `L_charge` is the largest sum of
extents live at one instant and `OPT` the least span of a legal placement, so
`L_charge <= OPT` by the [baseline's inequality](static-memory-baseline.md#executions-objects-and-physical-charge).

Two intervals **cross** when they intersect and neither contains the other, which
with half-open integer intervals is the strict interlacing `b_i < b_j < e_i < e_j`
or its mirror. Equal intervals contain each other and do not cross; adjacent
intervals such as `[0, 2)` and `[2, 3)` are disjoint. The **crossing graph** has the
objects as vertices and the crossing pairs as edges. A family is laminar exactly
when this graph has no edge, and the **deletion number** `k` is the least number of
vertices whose removal deletes every edge.

## Replay and identity

From the host checkout:

```console
python tools/run.py static-memory structure --json
python tools/run.py test --only static_memory_structure
python tools/run.py test --only static_memory_structure --slow
```

The command calls [`report`](../../tools/vos/static_memory_structure.py), whose
receipt keeps every field of the earlier structural report and adds, per case, the
dynamic programme's deletion set, the crossing graph's two-colouring or odd cycle,
and the justified exact search; it adds the evaluated decomposition contracts, their
witnesses, a sweep over every small interval shape, and a seeded random sample of
larger families. The enclosing experiment receipt binds the source bytes of the module
and of this document. The measured figures, that is the optima, deletion numbers,
bounds, node counts and the tallies of the sweep and the sample, live in that receipt
and are not restated here; this document names the inputs that define a family or a
domain and argues each outcome qualitatively.

## The deletion number is polynomial

**Peer-reviewed source.** The crossing relation is the overlap relation on intervals:
two intervals are adjacent when they intersect without nesting. Gavril proved that
overlap graphs of interval families are exactly the circle graphs and gave
polynomial algorithms for a maximum clique and a maximum independent set of a
circle graph given its representation: F. Gavril, [*Algorithms for a maximum clique
and a maximum independent set of a circle graph*, Networks 3 (1973), pages 261 to
273](https://onlinelibrary.wiley.com/doi/10.1002/net.3230030305). The identification
of the crossing graph with an overlap graph, and of a minimum deletion set with the
complement of a maximum independent set, are elementary and stated here rather than
attributed to that paper, which works with chord representations and says nothing
about this repository's equal-interval convention.

**Elementary argument proved here.** Let `c_0 < ... < c_m` be the distinct
endpoints, so `m + 1 <= 2n`. Write `I(s, t)` for the intervals `[c_p, c_q)` with
`s <= p < q <= t`, write `w(s, t)` for the number of intervals equal to `[c_s, c_t)`,
and let `F(s, t)` be the size of a largest laminar subfamily of `I(s, t)`. Then
`F(s, s) = 0` and, for `s < t`:

```text
F(s, t) = w(s, t) + max( F(s + 1, t),  max over s < q < t of  F(s, q) + F(q, t) )
```

*Proof.* Every interval of `I(s, t)` nests in `[c_s, c_t)`, so the `w(s, t)` equal
copies join any laminar subfamily of the rest without creating a crossing; a largest
subfamily therefore contains them, and the recurrence counts them once. Let `S'` be
the remaining members of a largest subfamily. If no member of `S'` starts at `c_s`,
then `S'` lies in `I(s + 1, t)`. Otherwise let `q` be the largest end index among
members of `S'` starting at `c_s`; then `q < t`. Any member `[c_p, c_q')` of `S'` with
`p < q < q'` would have `p > s` by the choice of `q` and would cross `[c_s, c_q)`, so
every other member lies in `I(s, q)` or in `I(q, t)`, which gives the upper bound.
Conversely a laminar family in `I(s, q)` and one in `I(q, t)` are jointly laminar
because every interval of the first ends by `c_q` and every interval of the second
starts at or after `c_q`, so they are disjoint; and a laminar family in
`I(s + 1, t)` is one in `I(s, t)`. Hence equality. The maximum laminar subfamily is
`F(0, m)`, its complement is a minimum deletion set, and `k = n - F(0, m)`, because
any deletion set that leaves a laminar family has a laminar complement. The table
has at most `4 n^2` cells and each is filled by at most `2n` additions of counts, after
one sort of the endpoints; the magnitudes of the endpoints are only compared. The
work is therefore polynomial in the binary input length.

**Finite outcome.** [`maximum_laminar_subfamily`](../../tools/vos/static_memory_structure.py)
implements the recurrence with equal intervals grouped by their compressed endpoint
pair, reconstructs the kept set, and checks that the removed set hits every crossing
pair. The focused tests compare its minimum with the existing subset enumeration on
every three-interval family over four coordinates and on seeded random families, and
check equal intervals, adjacent endpoints, the empty family and input permutation.

## Two laminar stacks attain the charged load

**Theorem, proved here.** If the objects split into two laminar subfamilies, which
is exactly the case that the crossing graph is bipartite, then `OPT = L_charge`, and a
placement attaining it is constructed by sorting and two stack passes.

*Proof.* Place the first subfamily by the [baseline construction](static-memory-baseline.md#a-complete-laminar-special-case):
at any instant its live objects form a chain of nested groups placed consecutively
from the origin, so they occupy exactly `[0, load_1(t))`. Place the second subfamily
by the same construction and reflect it, giving each object the base
`L_charge - base - extent`; at instant `t` it occupies exactly
`[L_charge - load_2(t), L_charge)`. Because `load_1(t) + load_2(t) <= L_charge` at every
instant, the two occupied bands never meet, every base is a nonnegative integer, and
the span is at most `L_charge`, which is also a lower bound. The bases are computed by
the constructor's sorting and stack, so the construction is polynomial and enumerates
no addresses.

**Corollaries.** Deletion number at most one leaves a laminar family plus one
object, which is a split into two laminar subfamilies, so every family with `k <= 1`
has `OPT = L_charge`; the open question begins at `k = 2`. More generally the theorem
applies whenever some minimum deletion set is itself laminar, and to families with
arbitrarily large `k` whose crossing graph happens to be bipartite. Bipartiteness is
decided by a breadth-first two-colouring of the crossing graph; when it fails, the
two equally coloured neighbours close an odd cycle of crossing pairs, which the
receipt carries as the certificate. The converse of the theorem is false: the
canonical-remainder witness below has a triangle in its crossing graph and still
attains its load, so the theorem is a sufficient condition and not a
characterization.

**Finite outcome.** [`two_stack_placement`](../../tools/vos/static_memory_structure.py)
builds the placement, passes it through the independent checker, and refuses a
non-laminar half, a non-partition, non-unit alignment and a capacity below the load.
The tests replay the placement cell by cell, independently of the module's checker,
compare its span with the address-enumerating oracle's optimum on seeded random
bipartite families, and check that every non-bipartite family's certificate is a
simple odd cycle of crossing pairs whose deletion number is at least two.

## Decompositions refuted by small witnesses

Each contract below is a natural way to reduce placement to the deleted objects and
the laminar remainder. Each is stated so that a single family can refute it, is
evaluated by [`decomposition_values`](../../tools/vos/static_memory_structure.py)
for every minimum deletion set of that family, and is refuted by a named contract in
the report whose optimum the existing exact oracle establishes and independently
replays. The stated object count is the least at which the contract is known to fail:
for each smaller count the table gives either an argument that no family of that size
can refute the contract or the bounded sweep that found none, the module's `CONTRACTS`
table repeats that reasoning, and the report's sweep fails if it ever finds a
refutation below the stated count. Where the reasoning is a bounded sweep, a family
outside its extent bound could still fail the contract at the smaller count.

| Contract | Statement | Fails at | Why not earlier |
| --- | --- | --- | --- |
| `bottom-block` | For some minimum deletion set, placing the deleted objects optimally on their own at the origin and stacking the laminar remainder above that block is optimal | three objects | Two objects with `k = 1` cross, so they coexist and every placement spans both extents |
| `signature` | The optimal span is a function of the remainder's charged load and the multiset of deleted extents | a pair of families with three and two objects | With two objects the span is the sum of both extents, which the signature determines |
| `band` | For some minimum deletion set, the optimum is the larger of the load and the deleted objects' own optimal span plus the remainder's largest load during their lifetimes | four objects | `k <= 1` is settled by the two-stack theorem; the only three-object family with `k = 2` is three mutually crossing intervals, which share an instant, so every stack of them is optimal |
| `canonical-remainder` | For some minimum deletion set, the constructor's placement of the remainder at the origin extends to an optimal placement by choosing bases for the deleted objects alone | five objects | A laminar deletion set is handled by the two-stack theorem, the only three-object crossing graph without one is a triangle whose intervals share an instant, and the slow test's sweep exhausts every four-object shape with extents at most two |

The witnesses, with intervals written `[start, reuse)` and unit extents unless stated:

- **`bottom-block-witness`.** `a = [0, 1)` with extent two, `b = [1, 3)`, `c = [2, 4)`.
  Only `b` and `c` cross, so either alone is a minimum deletion set. Whichever is
  deleted, `a` stays in the remainder and its extent alone is the family's load, so
  the block decomposition stacks the deleted object above that load; the whole family
  nevertheless fits within the load, because `a` fills it while alone and `b` and `c`
  share it afterwards.
- **`signature-pair-small` and `signature-pair-large`.** The small family is
  `a = [0, 2)` and `b = [1, 3)` with extent two; deleting `a` leaves a remainder whose
  load is `b`'s extent, with `a`'s extent deleted, and the two objects coexist, so the
  span is the sum of both extents. The large family is `a = [0, 1)`, `b = [0, 2)`,
  `c = [1, 3)`; deleting `c` leaves a remainder of the same load, since `a` and `b`
  coexist, with the same deleted extent, yet the family fits within its load because
  `a` and `c` never coexist and `c` takes `a`'s cell. Equal signatures, different
  optima.
- **`band-witness`.** `a = [0, 2)`, `b = [0, 4)`, `c = [1, 3)`, `d = [3, 5)` with extent
  two. The crossing pairs are `a` with `c` and `b` with `d`, which share no object, so
  a minimum deletion set takes one object from each pair; for every such set the band
  bound exceeds the optimum, which equals the load. The bound prices the deleted
  objects as one block above the remainder's peak, although the member that makes the
  block tall and the remainder's peak never coincide.
- **`canonical-remainder-witness`.** `r1 = [0, 2)`, `r = [0, 3)`, `d1 = [1, 4)`,
  `d2 = [2, 5)`, `r2 = [4, 6)` with extent two. The crossing pairs are `d1` with `d2`,
  `r1` and `r`, and `d2` with `r` and `r2`, so `{d1, d2}` is the only minimum deletion
  set and the crossing graph contains the triangle `d1, d2, r`. The constructor
  places `r` below `r1` and `r2` at the origin; every cell below the load except the
  top one is then occupied while `d1` starts and again while `d2` ends, and `d1` and
  `d2` coexist, so within the load both would need that top cell and the canonical
  remainder forces a span above the load. A placement at the load exists in which
  `r2` sits above `d2`: the remainder is not placed canonically in any optimal
  placement of this family.

**What stays unrefuted within the searched space.** The default report sweeps every
interval shape with at most three objects and extents at most two, and the slow test
sweeps every shape with four objects at the same extent bound, both against the
exact oracle. Within those domains no family with a nonzero deletion number has an
optimum above its charged load, and no four-object family refutes the
canonical-remainder contract. The report also draws a seeded random sample of families
larger than the sweep exhausts, whose seed, size and domain are fields of the receipt,
and decides each by the justified search: a placement returned at the load certifies
attainment independently of the search's completeness, because the checker accepts
the placement and the load is a lower bound, while a completed search above the load
would be a candidate counterexample that the receipt records with the oracle's replay.
The sample reaches non-bipartite families with deletion number at least two and
contains no family above its load; that is finite evidence about the sampled families
and nothing more. That such families exist is a peer-reviewed result the
[research agenda](../background/static-memory-research.md#live-payload-is-a-lower-bound-not-a-placement-theorem)
already cites, whose constructions are asymptotic. The least deletion number of a
family with `OPT > L_charge` is therefore unknown here, and in particular whether
`k = 2` already forces `OPT = L_charge` is an open question that the finite evidence
neither settles nor suggests strongly.

## An exact search without address enumeration

**Lemma, proved here (left-justification).** For every legal placement there is a
legal placement of no greater span in which every base is zero or equals the top of
an interfering object whose extent lies below it.

*Proof.* While some object violates the condition, lower it by one. The only
interfering objects it can newly meet are those whose top equals its old base, and
the condition says there are none; objects above it move no closer. The span never
grows, the sum of bases decreases and is bounded below by zero, so the process stops
at a placement satisfying the condition.

**Completeness, proved here.** Sort such a placement by base, breaking ties by
identity. Each object's supporting neighbour has a smaller base and so precedes it.
A search that places objects in nondecreasing base order, with identity ties, and
offers each object only base zero and the tops of already placed interfering
objects, therefore visits every left-justified placement of a given height.
[`justified_exact`](../../tools/vos/static_memory_structure.py) runs that search as a
feasibility test, remembering placed sets whose completion failed because the
remaining subproblem depends only on the placed set, and finds the least feasible
height by binary search between the load, below which the load bound refuses every
height, and a feasible upper bound. The upper bound is the laminar remainder stacked
at the origin with the deleted objects placed consecutively above it, which is legal
because deleted objects then occupy their own address bands; when it exceeds the
capacity the search is first run at the capacity, and an infeasible result there is a
complete infeasibility. A bipartite crossing graph skips the search entirely.

**Scope.** Candidate bases are sums of extents and heights are compared, never
scanned, so the search runs unchanged on the receipt's binary-scale families where
the address-enumerating oracle cannot. The number of heights tested is logarithmic
in the sum of extents, hence polynomial in the input length; each feasibility test is
exponential in the object count in the worst case, so this is an exact algorithm and
not a parameterized one. A work-budget cutoff reports `incomplete` with the proved
bounds and no optimum. The tests compare its span with the existing oracle on seeded
random families, check its certificate, cutoff, capacity, refusal and permutation
behaviour, and solve the canonical-remainder witness by search at its load.

## Why this is not yet a parameterized algorithm

An algorithm parameterized by the deleted objects would fix their bases from a small
candidate set and then place the laminar remainder around them. Two facts proved
here show what such a scheme cannot assume.

**Candidate bases are subset sums.** In a left-justified optimal placement each
deleted object rests on a chain of supporting objects, so its base is a sum of extents
along that chain. The chain may run through remainder objects, and the number of
distinct sums is bounded by the number of subsets of the family, not by any function
of `k`. Left-justification alone therefore does not yield a candidate set of size
`f(k)` times a polynomial.

**The remainder around fixed obstacles is hard, proved here by reduction.** Given
positive integers `w_1, ..., w_n` with even sum `S`, PARTITION asks whether some subset
sums to `S / 2`; it is NP-complete under binary encoding, a peer-reviewed classical
result: R. M. Karp, [*Reducibility among combinatorial problems*, in Complexity of
Computer Computations, Plenum Press, 1972, pages 85 to 103](https://doi.org/10.1007/978-1-4684-2001-2_9).
Take `n` remainder objects, all with interval `[0, 1)` and extents `w_i`, which are
equal intervals and hence laminar, one obstacle of extent one fixed at base `S / 2`
during `[0, 1)`, and height `S + 1`. The free cells are the two bands below and above
the obstacle, each of capacity `S / 2`; the extents sum to `S`, so a legal placement
covers every free cell, each contiguous extent lies within one band, and the bands
are a partition. Conversely a partition places the objects. Deciding whether a
laminar remainder has a legal placement of a given height around one fixed obstacle
is therefore NP-hard under binary encoding, already for a single obstacle and a
remainder of equal intervals. This says nothing under unary encoding and nothing
about the original problem: the reduction's whole family is laminar with `k = 0`, so
the constructor places it at its load without fixing any base in advance, and the
obstacle's base at `S / 2` is the adversary's choice, whereas a placement with the
obstacle at zero is already optimal for this family. It shows that the remainder
subproblem cannot serve as a polynomial oracle for arbitrary candidate bases; a
parameterized algorithm of this shape must restrict the candidates and prove the
remainder tractable for those candidates together.

**The blocking sub-question, stated precisely.** Does every instance admit an
optimal placement in which each deleted object's base lies in a set of size at most
`f(k)` times a polynomial of `n`, computable in polynomial time, such that placing
the laminar remainder around deleted objects fixed at any of those bases is
polynomial? The two facts above refute the naive answers to each half separately.
The smallest open case is `k = 2` with the two deleted objects crossing each other
and the crossing graph containing a triangle; the canonical-remainder witness is
such a family, its optimum is its load, and the finite sweeps found no such family
whose optimum exceeds its load. No fixed-parameter tractability and no hardness for
any fixed `k` is claimed here.

## What remains open

- The parameterized question for `k >= 2` with a non-bipartite crossing graph, in
  either direction, as stated above.
- The least deletion number of a family with `OPT > L_charge`, and whether `k = 2`
  already forces equality.
- A machine-checked statement of the deletion-number recurrence, the two-stack
  theorem and the left-justification lemma; the arguments here are human-readable.
- Every extension the baseline names: non-unit alignment, restricted positions,
  owner, bank and multiple-execution constraints need their own parameters and
  encodings, and the alignment counterexample in the report already breaks
  peak equality for constrained bases.
- The source-lifetime bridge: none of this establishes that a compiler exports
  reservation intervals with a small deletion number, or any interval family at all.

The [research agenda's structural item](../background/static-memory-research.md#research-todo-list)
remains open under its full acceptance conditions; this document supplies the
polynomial parameter, the bipartite extension, the refutations and the exact
magnitude-independent search, and names the question it does not answer.
