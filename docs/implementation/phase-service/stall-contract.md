# Stalled transition model for the Q22e cost branch

This contract owns the stalled transition model of the pair the
[store-buffer comparison](../comparisons/store-buffer.md) names as missing: a
candidate that waits at issue needs a bounded stall cost before the `stalls`
interval of [the cost input](cost-input.md) means anything, and no instrument
turns a declared program and resource declaration into that bound. The arrival
analysis named beside it stays open: arrivals here are declared gaps, and the
proof that a binary presents no other sequence is the admission toolchain's, as
the closing section states. It adds one host instrument,
`tools/vos/phase_stall.py`, to the [preparation contract](prerequisite-contract.md).
It does not implement the U-03 arbiter, extract traffic from a binary, qualify
an occupancy or close Q22e.

Two assumptions bound every result below relative to the machine rather than to
the declared inputs. A hart is silent outside its declared slots, so every
partition scheduled on a declared hart must be declared as a slot or its
contention is missing. A program cut at its slot end, at a held request or at a
request whose shifted issue falls after the end, never issues its tail in the
model; the report counts that tail as `cut_max`, and the correspondence
certificate the closing section names covers every resumption point, the next
occurrence's alternatives including the tail the binary resumes with.

## Program input

The input is a new document kind, `phase-program-v1`, read beside the existing
`phase-resources-v1` declaration of [the schedule format](schedule-input.md),
not a new mode of `phase-schedule`: a schedule phase lists joint arrivals at
absolute cycles, a program lists one hart's requests with relative gaps whose
placement is an output of the exploration, and one `mode` field carrying both
would give one document two semantics. The object has exactly `schema`, `name`,
`resources_sha256`, `phases` and `harts`. The digest binds the resource bytes
as the schedule does; the program's own name and bytes are what a cost input
binds, so no further identity field exists. `phases` is a nonempty array of
objects with exactly `grant`, a nonnegative integer, and `refresh`, an array of
distinct declared bank names, possibly empty, one object per cycle of the major
frame, both carrying the schedule format's meanings unchanged: `grant` is the
maximum requests accepted at issue in that phase and `refresh` names the banks
whose reservation starts there. A phase withheld from every requester at every
bank is a zero grant, as the shared-island fixture declares it. `harts` maps
exactly the declared hart names, a silent hart to an empty array, each to an
array of slots with exactly `id`, `start`, `length` and `alternatives`:
`start` is a phase index, `length` a positive
integer with `start + length` at most the phase count, one hart's slots do not
overlap, and `id` is unique in the document and is what a cost input's slot
names. `alternatives` is a nonempty array of programs, each an array of
requests, an empty program being an explicit alternative. A request has
exactly `bank`, `operation` and `gap`, a nonnegative integer: for the first
request the offset of its earliest issue from the slot start, for a later one
the cycles from the acceptance at issue of the request it follows to this one's
earliest issue, zero meaning the same cycle. A maximal run joined by zero gaps
presents together and may not exceed the hart's `issue_limit`; a program whose
gaps sum to the slot length or more leaves its slot under zero wait and is
refused. Duplicate JSON keys, names or ids, floats, booleans in integer fields,
unknown fields, missing references, an unsupported operation at a bank,
refresh of a bank declaring `null` and a stale resource digest are errors, and
no supplied field promotes the declaration into qualification.

## Expansion to the zero-wait contract

Under the zero-wait hypothesis every gap is absolute, so each alternative places
its requests at fixed phases. The expansion builds the existing `Contract`: each
phase's joint alternatives are the product over harts of what each hart's
alternatives place in that phase, a hart outside any slot contributing the
empty batch, in hart order and then declared order, with grants, refresh and
paths unchanged. The product loses the per-hart correlation across phases, so
closure of the expanded contract is sound for the positive claim while its
refutation trace is only a candidate counterexample. A trace is realizable
when for every hart and every slot occurrence the trace enters, one declared
alternative places, in each phase of that occurrence the trace covers, exactly
the requests the trace took there; phases after the trace's last cycle are
unconstrained. The instrument checks this: a realizable trace is the zero-wait
refutation, and an unrealizable one is reported as `expansion: unrealizable`
with its trace, never as a refutation. Because the search stops at its first
refutation and a merged state keeps one history, an unrealizable trace does not
establish that no realizable refutation exists: `unrealizable` is inconclusive
for the expanded contract only, and the verdict on the declared program
language is the stalled exploration's own `program_zero_wait` below.

## Stalled semantics without a queue

The candidate is an in-order hart with no store buffer. Each cycle refresh
reserves first, requests completing transit accept next, and each hart then
presents its next request, or its zero-gap run, at the memory-issue stage. A
zero-path request accepted at issue is accepted at its bank in the same cycle;
a nonzero-path request accepted at issue enters the fabric and is accepted at
its bank `path` cycles later, in the flight representation of
[phase_service.py](../../../tools/vos/phase_service.py): a request issued in
cycle `t` with path `p` has remaining `p` at the boundary after `t` and is
accepted at its bank in cycle `t+p`. A request that cannot be accepted at
issue, because its zero-path bank is occupied, the phase grant is exhausted,
the order interlock below holds it or the arbiter chose another contender,
holds the hart: it is re-presented every following cycle until accepted, the
hart presents nothing else while held, and because every later request's gap
is measured from the acceptance at issue of the request it follows, every later
request shifts by the accumulated stall. A presented run is accepted by prefix
in issue order: the arbiter may accept its first members and refuse the rest,
the held suffix is re-presented alone in the next cycle together with any
zero-gap successor it then reaches, and a cycle in which any presented request
of a hart is refused adds one to that hart's stall whatever the run's width. A
zero-gap member's earliest issue is the acceptance cycle of the request it
follows, so a member refused beside a refused predecessor is not itself held
until that predecessor is accepted. There is no queue anywhere: a nonzero-path
request that finds its bank occupied on arrival remains the `path-blocked`
refusal the existing predicate reports, and pipeline backpressure stays
unmodeled.

One hart's requests are accepted at their banks in issue order, under the
in-step reading of the existing predicate's transit: the hart waits at issue
until every earlier request of its own still in transit after this cycle's
transit acceptances, a member earlier in the same presented run included, has
cycles remaining until bank acceptance, counted after this cycle's transit
step, at most this request's path. Acceptance within one cycle counts as
ordered, so these waits coincide exactly with the expansion's `order-inverted`
refutations; a request with a longer path issued one cycle earlier gives zero
wait, and every counted wait is a refused cycle of the hart. That interlock
orders acceptance and not completion: as
[the completion conventions](completion-model.md) show, a later request to a
shorter-occupancy bank may still complete first. The program analysis therefore
also runs the completion-order predicate over the same exploration and reports
`ordered` beside the stall bounds; a completion inversion sets `ordered` false,
refutes the program contract with its trace at exit 1 and leaves the
exploration running to closure, so the stall bounds stay complete, whereas
`path-blocked` and `refresh-overlap` stop it at the step.

Every structure this presupposes is one the candidate carries: the held-request
register, holding the run suffix, and its re-presentation; the same-cycle
refusal indication from bank port, grant counter and arbiter back to the hart;
the per-hart record of requests in transit with remaining path, which is the
order interlock; and the per-phase grant counter. Each owes a class in the
absence contract's
[flush-set map](../../hardware/absence-contract.md#6-the-fencet-completeness-claim)
under R-15-217, where a structure outside the map is a refinement failure, and
a fetch-path member owes
[the table-freeness rule](../../hardware/absence-contract.md#5-the-decision-rule-table-freeness).
The held-request register and the in-transit record are per-core mutable state
that [admission test (3)](../../hardware/absence-contract.md#3-the-register),
no hidden microarchitectural state surviving a partition switch un-flushed by
`fence.t`, ranges over, so their class and their `fence.t` treatment are owed
there; their area and power are R-15-108's exploration. The absence contract
prices nothing.

## Arbiter choice and injection grants

Among contenders for one bank in one cycle, and for the last units of a phase
grant, the winner is nondeterministic and the exploration takes every choice:
each cycle branches over every maximal set of presented requests that respects
one acceptance per bank, the phase grant and per-hart issue order. A reported
bound is therefore an upper bound for every arbiter that refuses a contender
only for a busy zero-path bank, an exhausted phase grant or a same-cycle
conflict with another contender, and accepts every contender it can. That
class is refresh-blind: an arbiter that withholds acceptance ahead of a
scheduled reservation is an unmodeled refinement, and an overlap reached by
accepting a held request whose occupancy runs into a reservation is a
`refresh-overlap` refutation. R-15-222a's rotation is a per-bank, per-core
withholding, non-work-conserving in R-07-036's sense and outside the
maximal-arbiter class this analysis bounds: it refuses a sole contender in a
cycle belonging to another core, so its waiting is not bounded here. The scalar
phase grant withholds a cycle from every requester at every bank, so a rotation
is representable here only in the single-hart form the shared-island fixtures
take, with the peer core's traffic absent. A multi-hart rotation needs a
per-hart, per-bank grant refinement this document does not add, the next
authorable extension, and its bound stays owed to U-03 until then. A
re-presented request counts against the grant of the cycle it is finally
accepted at issue in and no other: R-15-108 admits `w_inj` as the requests a
hart can inject per granted slot, what the fabric supplies, distinct from the
memory-issue width, what the hart can present; a refused request injected
nothing, so charging every presented cycle would turn the grant into a
presentation limit and fold the two parameters the entry keeps apart.

## State, closure and slot boundaries

A state is the boundary before a cycle's refresh: the phase, each bank's
remaining occupancy including maintenance, the requests in transit, and per
hart its slot occurrence, chosen alternative, program position, held run suffix
with the cycles its head has waited, and the stall accumulated in this
occurrence. Programs restart at their slot's start phase every frame with the
alternative chosen afresh, so every counter is bounded and the state space is
finite. The exploration starts empty at phase zero, carries occupancy and
transit across every frame wrap and slot boundary, takes every alternative and
arbiter choice and merges identical states, exactly as the existing checkers
do; a `path-blocked` or `refresh-overlap` step stops the exploration and
refutes the program contract with its trace, and a completion inversion refutes
it without stopping it. A request still held at its slot's end is
a boundary-outstanding fact for that (hart, slot), neither dropped nor counted
twice. This contract models a request presented and refused at issue at the
slot end as an irrevocable operation, the conservative choice for the
comparison: it lengthens H, keeps contending with other harts after the slot
end and keeps the join open unless a declared H covers it. R-07-040 fixes that
an irrevocable operation completes inside the residency prefix and that no new
instruction issues, and R-15-015b places a device store's outstanding accept in
that prefix, but whether the candidate's refused memory-issue request is
irrevocable or squashed and replayed is a decision of the ordered-path design
that its refinement must state; a squashing candidate has a shorter boundary
and a replayed head the next occurrence's alternatives must cover. Under this
contract's reading the hart presents no further request of that program, the
held request keeps being presented until accepted, and its cycles after the
slot end through its completion are boundary residency, not slot stall. A
request still held when the same hart's next slot occurrence begins is a
`residency-overrun` refutation, reported with the hart, the slot, the residency
reached and the trace. Requests accepted but incomplete at the end of residency
are drain.

## Outputs and receipts

On closure the report carries, per (hart, slot), three disjoint terms whose
serial sum is the modeled tail of an occurrence. `stalls` counts the cycles up
to and including the slot's last cycle in which the hart's presented request is
refused; `stall_total_max` is its maximum over all reachable histories and
arbiter choices, and `stall_single_max` the longest one request was held,
counted from its earliest issue to its acceptance at issue and truncated at the
slot end. `boundary_outstanding` is true when a request is held at the slot
end, with the shortest witnessing trace. Boundary residency runs from the first
cycle after the slot end through the held request's completion: its refused
cycles after the slot end plus its occupancy, occupancy including the
acceptance cycle, which is where R-07-040's prefix and the cost input's H end,
at entry of the boundary handler; `boundary_residency_max` is that length, and
`d_pipe_completion` covers only what is still outstanding at that completion.
`drain_max` has a single origin, the first cycle after the end of residency,
the slot end when no request was held there, and counts the cycles from that
origin inclusive until the last operation the hart issued in that occurrence
completes under [the completion conventions](completion-model.md), refresh
continuing and the other harts still running; when nothing is outstanding it is
zero. Because `ordered` requires every earlier operation of a hart to complete
no later than a later one, a boundary-outstanding occurrence that closes has
`drain_max` zero, its earlier operations completing inside residency; the term
is defined for every occurrence because its origin is. `cut_max` counts the
requests of the chosen alternative that an occurrence neither accepted nor
holds at its slot end, whether shifted past the end by accumulated stall or
refused beside a held head; it is zero whenever `stall_total_max` is, and a
nonzero count names an occurrence whose tail the assumption above cuts. Beside
these the report carries `ordered`, the completion-order verdict; `zero_wait`,
the existing acceptance predicate's verdict on the expanded contract;
`expansion`, reading `closed`, `refuted` or `unrealizable`; and
`program_zero_wait`, the stalled exploration's own verdict on the declared
program language, closed exactly when every stall bound is zero, no slot is
boundary-outstanding and no `path-blocked`, `refresh-overlap` or
`residency-overrun` step occurred; it does not read `ordered`, which stands
beside it as `ordered` stands beside `zero_wait`. Every trace lists each cycle's presented requests in hart order and
then declared order, the order the expansion uses. The tests hold consistency
both ways: a closed expansion requires `program_zero_wait`, and
`program_zero_wait` requires that the expansion is not refuted by a realizable
trace. The receipt binds the program, resource and cost bytes and the
instrument, its CLI, its tests and this document by SHA-256, keeps
`target_comparison` equal to `open`, and names what the analysis does not
establish: the actual arbiter, pipeline backpressure, mode changes and initial
states, instruction-stream correspondence, qualified occupancies and refresh,
and WCET.

One synthetic, hand-computed occurrence fixes these conventions. Its resource
declaration, shared by the fixtures of the acceptance table, has harts `X`
(`issue_limit` 2) and `Y` (`issue_limit` 1) and banks `b0` (path 0, `rd`
occupancy 1, `wr` occupancy 3, refresh occupancy 2), `b1` (path 0, `rd`
occupancy 1, no refresh) and `f2` (path 2, `rd` occupancy 1, no refresh). The
program has eight phases of grant 1 with no refresh; `X` has slot `sx` at
phases 0 to 2 with the one alternative `[{f2, rd, 0}, {b0, wr, 0}]`, a
zero-gap run, and `Y` has slot `sy` at phases 1 to 2 with `[{b0, wr, 0}]`. The
run is refused at every cycle it is presented in this occurrence, so no arbiter
choice arises and the history is unique.

| Cycle | `X` | `Y` | `sx` term | `sy` term |
| --- | --- | --- | --- | --- |
| 0 | presents the run: `f2 rd` accepted at issue, two cycles of transit; `b0 wr` refused, the grant exhausted and `f2 rd` two cycles from acceptance against path 0 | silent, outside `sy` | stalls, 1 | n/a |
| 1 | re-presents `b0 wr`: refused, `f2 rd` one cycle from acceptance against path 0 | presents `b0 wr`: accepted, occupying cycles 1 to 3 | stalls, 2 | in slot, accepted |
| 2 | `f2 rd` accepted at `f2` and complete at the cycle's end; `b0 wr` refused, `b0` busy; last cycle of `sx` | program complete; last cycle of `sy` | stalls, 3 | in slot, nothing presented |
| 3 | `b0 wr` refused, `b0` busy | `b0 wr` completes at the cycle's end | residency, 1 | drain, 1 |
| 4 to 6 | `b0 wr` accepted at 4, occupying cycles 4 to 6 | silent | residency, 2 to 4 | n/a |
| 7 | nothing outstanding at the drain origin | silent | drain, 0 | n/a |

The occurrence reports, for `sx`, `stall_total_max` 3, `stall_single_max` 3
(the `b0 wr`, whose earliest issue is cycle 0, held through cycle 2),
`boundary_outstanding` true, `boundary_residency_max` 4 and `drain_max` 0, a
modeled tail of 3 + 4 + 0 = 7 cycles from cycle 0 through cycle 6; for `sy`,
`stall_total_max` 0, `stall_single_max` 0, `boundary_outstanding` false,
`boundary_residency_max` 0 and `drain_max` 1; and `ordered` true, `X`'s `f2 rd`
completing at cycle 2 before its `b0 wr` at cycle 6. The next frame begins at
cycle 8 with both banks free, so the exploration closes with these bounds.

## Cost join

With `--costs` the instrument reads a `phase-cost` input. Its `schedule` object
(`id`, `path`, `sha256`) must name the program document itself: the program's
`name`, its path and its exact bytes; a mismatch is a stale-input refusal at
exit 2. Each cost slot id must name a program slot, an unknown id being an
error. The named slots must belong to harts of one serial admission domain,
which the instrument cannot check and the receipt states; program slots the
cost input does not name act as contention only and are reported unjoined. For
each named slot the candidate `stalls` interval is compared with
`stall_total_max` by `phase-evaluate`'s three-way rule: an upper bound below it
refutes the join, a lower bound below it is inconclusive, and otherwise the
term is covered. The candidate `trap_per_switch` is compared with
`boundary_residency_max` by the same rule; for a boundary-outstanding slot an
unknown operand keeps the join open with reason
`boundary-outstanding-uncovered`, and the receipt states that this compares
declared intervals at the model's boundaries and verifies no residency
coverage, the join having no timer or handler model and no way to detect an
input measured at other boundaries. The single document-level
`boundary.d_pipe_completion` must cover the maximum `drain_max` over the named
slots by the same rule; it is a per-switch boundary operand, not a per-slot
term, so drain cycles are assigned to the boundary charge and never to a slot
field. The join verdict is `refuted` when any compared term or the arithmetic
is refuted, else `open` when any compared operand is unknown or the arithmetic
is open, else `inconclusive` when any term overlaps or the arithmetic is
inconclusive, and otherwise the arithmetic verdict; only `refuted` exits 1,
favorable arithmetic never outweighs a refutation, and `phase-evaluate` keeps
its zero-wait scope and verdicts.

## Acceptance cases

Acceptance requires behavioral tests through
`python tools/run.py test --only phase_stall`. The quantitative cases are
synthetic fixtures the landing authors under `program-examples/`, each binding
the resource declaration of the worked occurrence above; the numbers below are
computed by hand from the semantics of this document, and the fixtures must
remain visibly synthetic.

| Fixture | Program | Expected result |
| --- | --- | --- |
| `refresh-stall.json` | `X` alone; phases `[1, 1, 1]` with `b0` refreshed at phase 0; `sx` at phases 0 to 2 with `[{b0, rd, 0}]` | The reservation holds `b0` through cycle 1 and the read is accepted at 2: `stall_total_max` 2, `stall_single_max` 2, `drain_max` 0, `program_zero_wait` false, `zero_wait` refuted by a realizable trace. |
| `joint-loser.json` | `X` and `Y`; six phases of grant 2; `sx` and `sy` at phases 0 to 5, each `[{b0, wr, 0}]` | Either hart wins cycle 0 and the other is accepted at 3: `stall_total_max` 3 and `stall_single_max` 3 for both slots, the loser's bound equal to the winner's occupancy, `drain_max` 0. |
| `split-run.json` | `X` alone; phases `[1, 1]`; `sx` at phases 0 to 1 with `[{b0, rd, 0}, {b1, rd, 0}]` | The run splits against grant 1, `b0 rd` accepted at 0 and `b1 rd` at 1: `stall_total_max` 1, `stall_single_max` 1, `drain_max` 0. |
| `path-wait.json` | `X` alone; phases `[1, 1, 1]`; `sx` at phases 0 to 2 with `[{f2, rd, 0}, {b0, rd, 1}]` | `b0 rd` waits at cycle 1 for `f2 rd` and both are accepted at 2, completing together: `stall_total_max` 1, `stall_single_max` 1, `ordered` true, `drain_max` 0. |
| `boundary-outstanding.json` | `X` alone; eight phases of grant 1 with `b0` refreshed at phase 1; `sx` at phases 0 to 1 with `[{b0, wr, 1}]` | Refused at cycles 1 and 2, accepted at 3 and occupying 3 to 5: `stall_total_max` 1, `stall_single_max` 1, `boundary_outstanding` true, `boundary_residency_max` 4, `drain_max` 0. |
| `worked-tail.json` | the worked occurrence above | `sx`: `stall_total_max` 3, `stall_single_max` 3, `boundary_outstanding` true, `boundary_residency_max` 4, `drain_max` 0; `sy`: 0, 0, false, 0, `drain_max` 1; `ordered` true. |

The remaining cases are decidable relations: the grant gap `[2, 0]`, the joint
two harts on one bank and the final-cycle write across frame wrap, each
yielding a finite stall bound while `zero_wait` stays refuted by a realizable
trace; equal paths, and a path-2 request followed one cycle later by a path-1
request, each giving zero wait; a nonzero-path arrival at a busy bank staying
`path-blocked`; a held request whose acceptance runs into a reservation
refuted as `refresh-overlap`; an occupancy-three request followed by a
shorter one to another bank refuted as a completion inversion with its trace
and `ordered` false; a `residency-overrun` reporting hart, slot, residency
reached and trace; an alternative whose expanded refutation is unrealizable,
reported inconclusive while `program_zero_wait` decides the program language;
a cut tail reported as `cut_max` one, both for a later request shifted past the
slot end and for a zero-gap successor refused beside a held head;
a per-hart issue-limit violation, a program leaving its slot, a stale resource
digest, an unknown field, a cost input naming an unknown slot id and a cost
input whose schedule object does not name the program, each refused; a
consistency case where every bound is zero, `program_zero_wait` holds and the
acceptance predicate closes; and the join refuted by an understated `stalls`
interval, refuted by a `trap_per_switch` upper bound below the residency,
inconclusive on overlap, open on an unknown `trap_per_switch` at an outstanding
slot, and refuted by a `d_pipe_completion` upper bound below the largest
`drain_max`.

## Command and scope

The instrument is the new command `phase-stall PROGRAM RESOURCES --json` with
optional `--costs COSTS`, registered as a further phase command rather than as
an option of `phase-service`, which reads a `Contract`, or of `phase-evaluate`,
whose verdict names the zero-wait branch: one command reading two input kinds
would carry two verdict vocabularies. Exit 0 means the stalled exploration
closed with finite bounds, whatever `zero_wait` reports, and the join, if
requested, is not refuted; 1 a program-contract refutation, `path-blocked`,
`refresh-overlap`, a completion inversion or `residency-overrun`, or a refuted
join; and 2 malformed or stale input. Read the named verdicts, not the exit
code alone. The landing owes its consumers: the command table of
[the tool guide](../../../tools/README.md) gains a `phase-stall` row,
`tools/vos/cli/__init__.py` registers the command, `phase-evaluate`'s
refutation reason is re-worded from "stalled execution is unmodeled" to name
`phase-stall`, the comparison's missing-model sentence becomes a pointer to
this document while its arrival and WCET halves stay open, and
[the document index](../../README.md) indexes this page.

A stall bound over declared programs is not a WCET: it bounds memory-issue
waiting for the declared request sequences at the declared occupancies under a
maximal arbiter, with no backpressure, mode change or initial state other than
empty. The per-hart program form is the shape the checked code/schedule
certificate named in [the work list](../../background/critique.md#the-work-list)
must take: a proof that the admitted binary on that hart in that slot presents
no request sequence outside the slot's declared alternatives with their
declared gaps. That correspondence is owed by the admission toolchain, R-11-006
and R-11-017's artifact under R-11-018's per-mode instances, read off the
R-05-102 and R-18-024 cost derivation, and by the proof map's U-03, which maps
the emitted schedule into the contract seam, U-05, which holds the schedule
record, and U-28, which states WCET over U-08's projection with U-09's
magnitudes. Occupancies remain R-15-247m's, widths R-15-108's, and the fence
and drain constants R-17-041's. Q22e stays open.
