# Static-memory research baseline

> Non-normative definitions and proof arguments for the [research agenda](../background/static-memory-research.md). The [requirements register](../requirements-register.md) remains authoritative. The arguments here have human-readable proofs, and the laminar placement theorem also has a [mechanized statement](#mechanized-statement). They supply no target measurement or change to admission. Q5 owns the placement comparison and Q22a supplies the qualified reuse interface.

## Executions, objects and physical charge

An admitted execution has an ordered sequence of events and a declared mapping from those events to schedule time. Event order decides interference; schedule time prices service. An integer lifetime endpoint has no unit until that mapping is supplied. Simultaneous events use a fixed order: completed reuse and release of a reservation precede a successor's acquisition and initialization. Equal timestamps alone never prove completion.

An object means one incarnation of a bounded allocation, with an identity, owner, arena, fixed base, charged extent, and lifecycle. Repeated uses of one pool slot are different incarnations. A program variable, an allocation site, and a slot are different identities: a bounded loop can produce several simultaneous objects at one site. The identity-to-slot binding policy is part of the model, including whether one layout must serve every admitted execution or a finite family of prechecked bindings is allowed.

An arena is a contiguous address interval within one owner's permitted island and one memory class, with a declared legal-position predicate. It may have further pool, bank and exact-capability-bounds restrictions. Arena boundaries are inputs. Capacity in another arena does not enter a request's legal placement set. A noncontiguous physical region is modeled as separate arenas or with an explicit legal-extent predicate; its holes are not allocatable bytes.

For object `i`, let `w_i > 0` be its charged contiguous extent and `0 <= p_i(t) <= w_i` its useful resident payload at time `t`. Charge slot rounding and in-slot metadata inside `w_i`; charge out-of-slot descriptors, bitmap storage, tags, ECC and recovery workspaces in their own declared lines. Useful payload includes state the service promises to retain, even when its application is not running. A buffer's last computation is not necessarily the end of its payload obligation.

The bounded research lifecycle uses the following ordered endpoints:

```text
start <= payload_end <= authority_end <= sweep_end <= reuse
J_i = [start_i, reuse_i)
```

| Endpoint | Meaning and required evidence |
| --- | --- |
| `start` | Reservation acquisition, including any preparation before payload becomes usable. The complete extent is unavailable to another incarnation from this event. |
| `payload_end` | Logical release and entry to Quiescing in the simple fixture. No promised useful payload remains, but retired authority may remain. |
| `authority_end` | Successful containment under R-08-006, including publication, live and saved roots, loans, proxy acknowledgements and accepted device transfers. An epoch increment or timeout is insufficient. |
| `sweep_end` | Completion of a full sweep begun after that barrier, with every relevant representation removed and no source able to repopulate a passed location. |
| `reuse` | Authorized handoff after the authority gate and required zeroization or initialization service. The next tenant's definite-initialization discipline still applies to its own accesses. |

The fixture simplifies useful payload to one declared subextent before `payload_end`. A real exporter must represent delayed initial filling, intermittent use and retained state, or conservatively reserve them throughout. If last useful computation precedes logical release, the gap remains charged; it cannot be erased by renaming last use as release. Initialization may overlap safe reclamation work only under a proof of that overlap; the serial ordering above takes no such credit.

Let `J_i` cover every instant at which the old incarnation can prevent a new one from occupying its extent. This is a reservation lifetime, not merely source-language liveness. A certificate for program lifetimes must establish that all executions' reservation intervals fit the exported interference relation. The placement checker cannot infer this fact from endpoints it receives.

For one arena and one fixed execution, define:

```text
L_payload = max_t sum_i p_i(t)
L_charge  = max_t sum_{i : t in J_i} w_i
OPT       = minimum legal fixed contiguous placement span
P         = span of the emitted legal placement, measured from the arena base

L_payload <= L_charge <= OPT <= P
```

The first inequality assumes payload is counted only while its incarnation reserves storage. The second follows because simultaneous reservations must occupy disjoint byte intervals. The last follows because the emitted placement is a candidate in the same optimization problem. If no legal placement exists, `OPT` is infinite and there is no feasible `P`. Permanent reservations participate as always-live objects or as a disjoint fixed charge, never both.

`OPT - L_charge` is the unavoidable gap for the declared placement model; `P - OPT` is planner suboptimality. `P - L_charge` therefore combines two causes. Moving bases with fixed extents and endpoints changes neither live-load quantity. Changing payload lifetime, release time or sweep service changes the instance and must be reported as such.

A whole-image capacity report sums each arena's required reservation and each disjoint external charge once. Its conservative sum of arena peaks need not equal the peak of the whole machine's useful payload. Tags, ECC and macro periphery also need a physical-capacity convention consistent with the [product gate](product-gate-contract.md); payload-address span is not die area. A diagnostic ledger partitions charged bytes by one primary state at each time and adds non-additive explanation labels. A quarantined padded byte belongs to one primary charge, even if both quarantine and padding explain it.

## The interference predicate and the existing artifacts

For nonempty half-open reservation intervals `J_i = [b_i,e_i)` and extents `X_i = [a_i,a_i+w_i)`, the placement obligation is:

```text
for every distinct i,j:
  (b_i < e_j and b_j < e_i)
    implies (a_i + w_i <= a_j or a_j + w_j <= a_i)
```

An actually empty reservation contributes no interference and is removed before this predicate is applied; a zero-payload object with initialization or delayed reuse is not empty. The arena, bounds, alignment, owner and other legal-position predicates are additional conjunctions. Interference feasibility does not establish optimality, source-lifetime soundness, successful revocation, or correct runtime binding. A source-to-plan theorem must join those separate obligations.

The [memory-plan statement](../../proofs/MemoryPlan.v) supplies `live_from`, `live_to`, `base_of`, `length_of`, an island map, and `colouring_ok`. Its `colouring_ok_sound` connects the Boolean predicate to `NoInterference`, which has the same overlapping-lifetime antecedent above. Its gap e records the missing time-order interpretation; gap f records R-08-014's inverted word. A proof of this Boolean implication does not establish that the input lifetimes describe all admitted execution paths or that the placement reaches the live-load lower bound.

The [placement-search contract](placement-search.md) keeps lifetimes and lengths fixed. Its footprint is the peak calculated from those inputs, its span is the highest slot endpoint relative to the island base, and its padding is bytes below that endpoint covered by no slot at any lifetime. Padding is not instantaneous idle capacity and is not all of `P - L_charge`. The exporter declares owner, bank, reserved size and the slot's timing bound absent; research annotations must retain that provenance rather than invent production values. The current enumeration's optimum is only over its declared grid.

## A complete laminar special case

**Theorem.** Consider finitely many positive integer extents and nonempty, fixed, half-open reservation intervals. Suppose every pair of intervals is disjoint or one contains the other. There is one arena with origin zero, every nonnegative integer base is legal, alignment is one, no object is pinned, and no additional ownership, bank, guard-space or bounds constraint applies. A fixed contiguous placement exists with span exactly `L_charge`.

**Construction.** Group equal intervals and give each group the sum of its member extents. Strict containment makes the groups a forest: each group has the smallest strict containing interval as parent, if one exists. Its distinct children are disjoint in time. For each group, place its members consecutively beginning at the sum of the weights of its strict ancestors. Roots begin at zero. Sibling subtrees may reuse the same addresses because their intervals do not overlap. A deterministic identity order fixes the within-group order.

**Feasibility proof.** Two intervals that overlap lie in one ancestor chain or in the same group. Within a group their extents are consecutive. A descendant begins at or above the end of every member of its ancestor group. Thus every simultaneously reserved pair has disjoint extents. All bases are nonnegative integers and there is no other legality condition to violate.

**Span proof.** The top of a group is the sum of the weights on its root-to-group path. Pick a time inside the group's nonempty interval. Every group on that path is live then, so this sum is at most `L_charge`. Every placed endpoint is therefore at most `L_charge`. Conversely any legal placement needs at least `L_charge` by the simultaneous-load argument. The constructed placement is legal and reaches equality, proving `OPT = L_charge`.

**Algorithmic scope.** Sorting endpoints by increasing start and decreasing end permits grouping equal intervals and building or rejecting the containment forest with a stack. Sorting, comparison and ancestor-weight addition use time polynomial in the binary input length; no enumeration over the numerical address-space size is needed. Equal lifetimes require the grouping step: strict ancestors alone would otherwise put equal-interval objects at the same base. Empty intervals can be removed before this theorem; an object needing initialization or quarantine is not empty merely because it has no useful payload.

A common alignment `g` preserves the argument if the arena origin, every extent and every permitted stack boundary are multiples of `g`, and no other restriction applies: divide lengths and bases by `g`, apply the theorem, then rescale. Arbitrary per-object alignment does not satisfy this premise.

The theorem concerns actual reservation lifetimes. A language may supply a proof that its exported intervals are laminar, but ownership alone and nested lexical region names do not supply it. Extending intervals to region exit can produce laminar reservations while increasing `L_charge` above the original payload peak. This remains an optimal placement of a more retentive model.

### Executable construction and structural witnesses

`python tools/run.py static-memory structure --json` replays the construction in
[static_memory_structure.py](../../tools/vos/static_memory_structure.py). It sorts
reservation intervals by increasing start, decreasing end and identity, places
each object above the active ancestor stack, and refuses crossing intervals.
Equal intervals nest in identity order, giving their objects consecutive extents.
The independent placement checker then verifies every emitted binding, and its
span is compared with the separately computed charged live-load bound.

The constructor never enumerates addresses. Its binary-magnitude witness uses
extents and endpoints far beyond a practical integer address grid. Sorting and
stack construction have the algorithmic scope of the argument above; the current
independent placement replay also performs a quadratic pair scan. Neither result
certifies the target's legal-address constraints or the source lifetime bridge.

The receipt also enumerates interval-deletion subsets within an explicit budget.
Removing an endpoint of every crossing pair is exactly what makes the remaining
family laminar. Completed smaller cardinalities give a lower bound on the minimum
deletion count; a cutoff retains that bound and reports `incomplete`, with no
claimed minimum. This finite diagnostic neither solves general placement at that
parameter nor gives a fixed-parameter tractability or hardness result.

`python tools/run.py test --only static_memory_structure` compares the constructor
against an independent byte-at-a-time oracle on generated small interval and size
families, and the deletion result against enumeration of retained subsets. It
checks equal intervals, adjacent endpoints, input permutation, unsupported
alignment and arena premises, insufficient capacity, and incomplete search.
The aligned equal-lifetime counterexample also carries the existing exact
oracle's independent optimality replay. These are executable checks of finite
instances, not a machine-checked general proof.

### Mechanized statement

[StaticMemoryLaminar.v](../../proofs/StaticMemoryLaminar.v) states the laminar theorem
above in Rocq and proves it outright, with no admitted step, axiom or parameter;
`python tools/run.py proofs` compiles it with the other shipped artifacts and reports
every constant closed under the global context. It is a companion to this research
document: it changes no admission criterion, accepts no requirement and confers no
landing credit, and the [requirements register](../requirements-register.md) remains
authoritative.

Its model is the theorem's. An object is an identity, a positive weight and a half-open
interval `[lo, hi)` with `lo < hi` over the natural numbers; a family is a finite list of
objects with distinct identities; the family is laminar when every pair of intervals is
disjoint or nested, equal intervals included; a placement maps identities to natural
bases, is feasible when distinct objects with overlapping intervals have disjoint
extents, and spans up to its largest extent top. One arena at origin zero, unit
alignment, every natural number a legal base, no pinning and no further constraint are
the premises, and the fixed intervals are inputs. The file proves that the charged load
over start endpoints bounds the load at every instant; that the construction, which
places each object at the total weight of the objects preceding it in the (start
ascending, end descending, identity) order whose intervals contain its own, is feasible
on a laminar family; that its span is at most the load on any well-formed family; that
every feasible placement spans at least the load; and therefore that on a laminar family
the construction spans exactly the load and no feasible placement spans less.

A bridge section reads a [memory-plan](../../proofs/MemoryPlan.v) `Plan`'s `live_from`,
`live_to` and `length_of` fields over the regions below `region_count` as a family and
proves, where that family is well formed and laminar, that the constructed `Placement`
satisfies `NoInterference` with span equal to the load, and that every `Placement`
satisfying `NoInterference` spans at least the load. The bridge speaks to
`NoInterference` alone: the plan's island containment, quantization, class placement and
placement-list charge are neither assumed nor concluded, and nothing is said about the
plan's own `base_of`.

The witnesses follow the [proof-artifact discipline](../../README.md#the-proof-artifacts-themselves).
The constructor's `equal-nested-disjoint` family, with numeric identities in the
receipt's identity order, has its bases, span and load computed by `vm_compute` and
checked by reflexivity, and the general theorem is instantiated at it; a two-object
crossing family is refused by the laminar predicate and collides under the construction;
a padded placement of the laminar family is feasible with span above its load; and the
memory plan's own reference plan is checked to satisfy the bridge's hypotheses, its
constructed placement passing `colouring_ok`. A seven-object crossing family, found
by a scratch search and confirmed with `python tools/run.py static-memory compare`
over an unshipped hand-written contract, has an
optimum strictly above its load: the file enumerates every placement whose bases lie
below the load, refuses each by computation, proves that every placement of span at
most the load is in that enumeration, and exhibits a feasible placement one unit above
it. The laminar premise therefore has content, and the lower bound is not attained in
general. This is one finite instance; it is not a hardness or a parameterized result.

What the file does not prove is what this document leaves open: the source-lifetime
bridge from admitted executions to the exported intervals, alignment, islands,
quantization, pinning, multiple executions and any complexity claim. The stack replay in
`static_memory_structure.py` is not mechanized; its agreement with the closed-form
construction is checked only at the concrete family, whose numeric identities preserve
the replay's string ordering. The mechanization proves the theorem under the stated
premises through filtered ancestor sums; it does not mechanize the prose's forest
construction or its complexity argument.

## Small witnesses for disputed implications

These are local constructions with synthetic units, not a product workload. Minimality claims below are limited to the stated number of objects or phases and the particular implication; none is a classification of general storage-allocation instances.

### Ownership does not bound size, count or elapsed lifetime

One exclusively owned vector appends one element for every input symbol until end-of-input. At every step it has a unique owner. Without an input bound, neither its maximum size nor an equivalent list's simultaneous node count has a finite bound. This already refutes the implication with one owned collection.

One exclusively owned buffer is released when a reply arrives. Two executions with different reply times have different release endpoints, although their ownership discipline is identical. If a deadline forces cancellation, its bound and the cancellation proof supply a finite reservation envelope; ownership does not supply that premise. A compile-time point in control flow can be fixed while its elapsed time and iteration instance vary.

### Nested region scopes do not establish exact object liveness

Inside one lexical region `[0,5)`, object A is used in `[1,3)` and object B in `[2,4)`. Their payload lifetimes cross. One region is already a laminar region family, yet its objects' payload intervals are not laminar. Two objects are necessary to violate pairwise laminarity.

If the region instead retains both objects to exit, use A only in `[1,2)` and B only in `[2,3)`, each of size one. Payload peak is one; reservations `[1,5)` and `[2,5)` overlap and have charged peak two. Region-stack placement is optimal for these reservations and still does not attain payload peak. Reclaiming A earlier changes the lifetime proof and its authority obligations.

### Laminarity does not remove legal-position restrictions

Two unit objects both reserve `[0,1)` in one origin-zero arena, with every base constrained to be even. Their lifetimes are equal and hence laminar; charged peak is two. Their distinct legal bases differ by at least two, so any placement spans at least three. Bases zero and two attain three. This is minimal in object count under these alignment-only rules: one unit object can use base zero and span one.

This witness makes no claim that the target capability format imposes this particular constraint on unit objects. It shows why an exact theorem must state alignment assumptions instead of treating quantized placement as interchangeable with unit alignment.

### One layout across modes costs more than each mode's peak

Three unit object identities A, B and C each have one immutable offset. The admitted modes activate AB, AC or BC, and never all three. Each execution's charged peak is two. Every pair must nevertheless have different offsets in the common layout, so its span is at least three, attained by offsets zero, one and two. Three identities are minimal for this gap: two identities either coexist, making peak two, or may share their one offset.

This is a multi-execution interference example, not a counterexample to the single-trace laminar theorem. Generic reusable slots with checked binding may change its fixed-identity premise. Such a change needs a binding proof, not a claim that the original common layout attains each mode's peak.

### Idle capacity in one owner does not meet another's reservation

Two owners each have an unconditional one-unit reservation in disjoint arenas. A service rule runs only one owner at a time. Total reservation is two while peak active payload can be one. The arena charge remains necessary even if the inactive owner's bytes contain no retained state: the unconditional own-arena guarantee reserves them. With `n` such owners and reservation `B`, disjointness gives `n * B`. Lending, public ownership transfer or a weaker guarantee changes a premise.

### The inverted interference condition rejects reuse and misses collision

Two unit objects with lifetimes `[0,1)` and `[1,2)` safely share base zero after the required reuse barrier. Requiring slots to be disjoint when lifetimes are disjoint rejects this legal sharing. Conversely, two unit objects both live in `[0,1)` at base zero violate physical safety, but the inverted antecedent is false and places no constraint on that pair. Both defects require only two objects. R-08-014's correction must change the antecedent, not strengthen the checker to prohibit all sharing.

## Scope disposition for the register and its prose

These dispositions identify what a normative repair must say. They do not silently weaken the existing register. Each row is read with the [static-memory-plan prose](../spec.md#r-08-010), the statement artifact and the search contract.

| Entry | Established part and unresolved scope | Required disposition |
| --- | --- | --- |
| R-08-011 | A static slot assignment can be checked. Ownership does not establish exact size, multiplicity, elapsed time, or the all-executions reservation intervals. `MemoryPlan.v` takes the intervals as inputs. | State the explicit bounds and event-order model, distinguish source allocation sites from incarnations, and require the compiler/TAL proof that actual reservation and safe-reuse behavior refines the exported relation. Retain fixed composition as the intended contract without attributing the missing premises to ownership alone. |
| R-08-012 | `L_charge` is a lower bound. Equality follows from the laminar theorem's full premises, not from merely planning offline or checking interference. Alignment and multi-mode witnesses already invalidate unqualified equality in broader models. Exact payload size also does not remove representability padding or fixed-pool slack. | Separate eliminated online placement from physical layout gaps; state `L_charge <= OPT <= P` generally and peak equality only for a proved special case. Account for R-08-018b's size classes and R-15-007k's quantization explicitly. A universal exact-peak criterion remains unsupported. |
| R-08-013 | The proof above establishes polynomial exact planning for fixed laminar reservation intervals under its stated constraints. It establishes no theorem that every region-disciplined program supplies them. | Qualify the nested special case by the actual lifetime and legal-placement premises. Keep external general-complexity results within their cited model; this artifact asserts no new general hardness or approximation bound. |
| R-08-014 | `colouring_ok` already checks disjoint extents for overlapping intervals. The normative line and corresponding prose invert that predicate. | Change both to overlapping live ranges, preserve half-open boundary semantics and the R-08-015 reuse join, and retain the statement's gap until the owning artifacts are repaired together. Feasibility remains distinct from optimality. |

R-08-012a's objective also needs the quantity it minimizes to be explicit when the normative scope is repaired: for fixed lifetimes and extents, peak load cannot move under a base search. The present search's span/padding objective reports a different movable quantity. Resolving that naming does not authorize changing islands, sampling profiles or adding solver machinery.

## Reclamation as a bounded capacity obligation

The [Q22a qualification](../assurance/revocation-qualification.md) distinguishes publication, successful containment, full post-barrier sweep and reuse. Its finite host fixture gives interface evidence, not an implementation or measured target latency. In particular, it gives a bounded failure decision for an unresponsive peer, not a finite successful-reclamation bound for that failure.

For one arena, let a release `i` arrive at `r_i = payload_end_i` with charge `w_i`, including padding. Let `u_i = reuse_i`. Define cumulative released charge over a half-open window and a worst-case arrival envelope:

```text
A(s,t] = sum_{i : s < r_i <= t} w_i
alpha(T) >= sup_s A(s,s+T]
Q(t) = sum_{i : r_i <= t < u_i} w_i
```

The envelope ranges over every admitted execution, including legal restart and retraction bursts, and each repeated retirement is a fresh event. Reports observe the state after reuse completions and arrivals at timestamp `t`; the window includes the arrivals at its right endpoint. A positive-duration envelope therefore includes simultaneous release bursts. With zero-delay reuse there is no outstanding charge.

**Envelope bound.** If every release succeeds and `u_i - r_i <= T` for one fixed `T > 0`, then `Q(t) <= alpha(T)`, after any unmodeled initial backlog has cleared. To prove this, take any summand of `Q(t)`. Since `t < u_i <= r_i + T`, its release satisfies `t-T < r_i <= t`; it is one of the arrivals counted by `A(t-T,t]`. Summing gives the inequality. If the model begins with backlog, add its still-unreusable charge explicitly until it clears. Releases whose bytes share a physical slot cannot be outstanding simultaneously in a legal execution; counting release events does not license double-booking backing.

This bound covers Quiescing before containment as well as quarantine and required zeroization. A bound counting only the interval after `authority_end` omits pre-barrier retention. The physical arena must also fit its simultaneously useful reservations and permanent charges; `alpha(T)` is a sufficient separate retirement reserve, not the entire capacity equation or necessarily a tight reserve. Joint liveness analysis may prove that their separate maxima cannot coexist.

### What can supply a finite reuse delay

Let `C` bound release-to-successful-containment, `W` bound the wait from containment to the start of the next eligible full sweep pass, `S` bound that pass from its start, and `Z` bound any required post-pass initialization/zeroization service. Under the lifecycle and guaranteed service premises, a conservative bound is:

```text
u_i - r_i <= C + W + S + Z
T = C + W + S + Z
```

`C` includes publication, scheduled cleanup of all live roots, safe restoration of saved roots, bounded loan return or forced cancellation, proxy notification/acknowledgement, and accepted-transfer completion. No component waits on untrusted cooperation. Schedule-independent jobs may overlap only where the composition proves that overlap; summing their bounds is conservative. Sweep progress and an average teardown rate do not enter containment.

`W` matters for an incremental global pass. A pass already in progress when the barrier completes cannot serve as the required pass begun after it. Waiting for the next pass and completing that pass are distinct costs. A design that starts a new full pass immediately must supply a scheduler and progress bound that remains valid under repeated releases; restarting a cursor on every teardown can destroy that guarantee.

Q22a's illustrative sweep uses frame period `F`, sweep-slot width `Q_s`, complete-group cost `G`, and covered group count `N`. Reserving one lost group at a cut yields guaranteed progress `q = floor(Q_s/G) - 1`; `q <= 0` refuses that schedule. Its conservative fresh-pass bound is `ceil(N/q) * F + Q_s`. This is a schedule formula over declared inputs, not a measured magnitude, and a production use must additionally settle `W`, holder coverage and any shared-service contention. Every capability-bearing source must be swept or proved unable to retain or recreate the authority; counting only the object's address extent is insufficient.

Initialization needs its own admitted work and service guarantee. A pass's authority-clear result does not by itself establish data erasure or the next tenant's initialized contents. The fixture's `sweep_end` and `reuse` endpoints keep this cost visible even where an implementation proves some work can overlap.

If releases can enter failed containment and remain quarantined, the uniform successful-delay premise is false. Keep those bytes in a separate `Q_failed(t)` term or use the finite pool's total capacity as the structural bound. Repeated failures can exhaust that pool and invoke its declared refusal; the short failure-decision deadline does not justify recycling it. A target-wide small-traffic claim remains open under R-08-008a until the composed roster supplies evidence.

### Minimal failed reuse rules

| Proposed shortcut | Small execution that defeats it | Required premise |
| --- | --- | --- |
| Reuse at the public phase boundary | A device write is accepted for A before its phase ends, B is initialized at the same address in the next phase, and the accepted write completes afterward. B is corrupted even though A's software is inactive. | Completion of every accepted transfer under the old authority, with the R-15-208a ownership postcondition, before reuse. Fixed phase labels alone supply no completion event. |
| Publication means containment | A live register holds A's capability, the bitmap is set, and a scalar access uses that resident authorizer without reloading it. | The R-08-006 complete live-root barrier. The load filter cannot substitute for it. |
| A filtered saved restore makes storage reusable | A saved capability retains its raw tag while its bit is set. Clear the bit and reuse A's address; loading the saved value now passes the filter. | The post-barrier sweep includes the saved representation or proves its destruction. Temporary unusability while the bit is set does not establish safe bit clearing. |
| Finishing the current sweep suffices | The sweep visits a holder before publication; it retains A's then-live tag. Publication and containment happen later, and the same pass finishes without revisiting that holder. | A full pass begun after containment, with complete coverage. A pass-complete counter without its start event is insufficient. |
| Cursor coverage alone proves reuse | A live root stores a stale capability into a location after the sweep has passed it. The cursor then reaches the end. | Containment prevents repopulation, and every remaining trusted writer preserves that invariant. Q22a's raw-tag check exposes this violation in its bounded fixture. |
| Retiring a grant slot retires every borrowed copy | A callee keeps an underlying object capability while the grant-slot bit is marked. The object remains live for another grant. | Bounded return or cancellation clears the complete borrowed footprint; the slot's bit is not the object's bit. |
| Average retirement throughput bounds backlog | A burst retires the whole pool, followed by a long idle period. The long-run average can be arbitrarily small while the instantaneous unreusable charge fills the pool. | A worst-case burst envelope and guaranteed service, including restart storms and failed-containment policy. |

## Structural questions left open

For the agenda's parameterized problem, keep positive integer sizes and endpoints encoded in binary, one origin-zero arena, unit alignment, unrestricted nonnegative integer bases and no pinning. Let `k` be the minimum number of intervals whose deletion makes the remaining reservation family laminar, with equal intervals allowed. The construction above settles `k = 0`. Whether exact placement has running time `f(k) * poly(input length)`, or is hard for some fixed small `k`, remains open here.

An enumeration bounded polynomially in numerical span is not such a result when the span is binary encoded. Supplying a deletion set instead of asking the algorithm to find one is a different problem variant. Added alignment, owner, bank, multiple-execution or segment constraints also need separately stated parameters; the small witnesses identify failed extensions of peak equality, not hardness proofs for these variants.

A feasibility certificate needs the extents, bindings, legal-position predicates and sound reservation interference. An optimality certificate additionally needs a matching lower bound or a complete infeasibility argument for every smaller span in the same candidate set. Small exhaustive witnesses can refute a proposed universal rule. They cannot establish a parameterized complexity theorem, universal temporal safety, a production demand bound or a composition-level capacity improvement.

The remaining join is concrete: a compiler or composed exporter supplies the sound lifetime and holder premises, Q5 compares placements and transformations over the same service, and the Q22a consumers supply actual containment, sweep and initialization service. Until those artifacts exist, the inequalities, scoped laminar proof and counterexamples are the result; the larger research backlog stays open.
