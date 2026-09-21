# Stalled transition model for the Q22e cost branch

This contract owns the stalled transition model the
[store-buffer comparison](../comparisons/store-buffer.md) names as missing: a
candidate that waits at issue needs a bounded stall cost before the `stalls`
interval of [the cost input](cost-input.md) means anything, and no instrument
turns a declared schedule and resource declaration into that bound. It adds one
host instrument, `tools/vos/phase_stall.py`, to the
[preparation contract](prerequisite-contract.md). It does not implement the
U-03 arbiter, extract traffic from a binary, qualify an occupancy or close Q22e.

## Program input

The input is a new document kind, `phase-program-v1`, read beside the existing
`phase-resources-v1` declaration of [the schedule format](schedule-input.md),
not a new mode of `phase-schedule`: a schedule phase lists joint arrivals at
absolute cycles, a program lists one hart's requests with relative gaps whose
placement is an output of the exploration, and one `mode` field carrying both
would give one document two semantics. The object has exactly `schema`, `name`,
`resources_sha256`, `phases` and `harts`. The digest binds the resource bytes
as the schedule does. `phases` is a nonempty array of objects with exactly
`grant` and `refresh`, one per cycle of the major frame; a phase withheld from
every requester is a zero grant, as the shared-island fixture declares it.
`harts` maps each declared hart name to an array of slots with exactly `id`,
`start`, `length` and `alternatives`: `start` is a phase index, `length` a
positive integer with `start + length` at most the phase count, one hart's
slots do not overlap, and `id` is unique in the document and is what a cost
input's slot names. `alternatives` is a nonempty array of programs, each an
array of requests, an empty program being an explicit alternative. A request
has exactly `bank`, `operation` and `gap`, a nonnegative integer: for the first
request the offset of its earliest issue from the slot start, for a later one
the cycles from the previous request's acceptance at issue to this one's
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
when for every hart and slot occurrence one declared alternative places exactly
the requests the trace took in each phase of that occurrence. The instrument
checks this: a realizable trace is the zero-wait refutation, and an
unrealizable one is reported as `expansion: unrealizable` with its trace, never
as a refutation.

## Stalled semantics without a queue

The candidate is an in-order hart with no store buffer. Each cycle refresh
reserves first, requests completing transit accept next, and each hart then
presents its next request, or its zero-gap run, at the memory-issue stage. A
request that cannot be accepted at issue, because its zero-path bank is
occupied, the phase grant is exhausted or the arbiter chose another contender,
holds the hart: it is re-presented every following cycle, the hart presents
nothing else while held, and every later request shifts by the accumulated
stall, gaps being measured from the acceptance that ends the hold. There is no
queue anywhere: a nonzero-path request that finds its bank occupied on arrival
remains the `path-blocked` refusal the existing predicate reports, and pipeline
backpressure stays unmodeled. One hart's requests are accepted in issue order:
with unequal paths the hart waits at issue until each earlier request of its
own in transit has remaining transit no greater than this request's path,
acceptance within one cycle counting as ordered, and that wait is a counted
stall. Every structure this presupposes is one the candidate carries and the
[absence contract](../../hardware/absence-contract.md) and R-15-108 must price:
the held-request register and its re-presentation; the same-cycle refusal
indication from bank port, grant counter and arbiter back to the hart; the
per-hart record of requests in transit with remaining path, which is the order
interlock; and the per-phase grant counter.

## Arbiter choice and injection grants

Among contenders for one bank in one cycle, and for the last units of a phase
grant, the winner is nondeterministic and the exploration takes every choice, so
a reported bound is an upper bound for every arbiter that accepts at most one
request per bank per cycle and accepts every contender it legally can.
R-15-222a's fixed per-core rotation refines the choice among contenders and can
only lower the bound; its withheld phases are declared as zero grants, and a
declared rotation order is an optional refinement refused until specified. A
re-presented request counts against the grant of the cycle it is finally
accepted in and no other: R-15-108 admits `w_inj` as the requests a hart can
inject per granted slot, what the fabric supplies, distinct from the
memory-issue width, what the hart can present; a refused request injected
nothing, so charging every presented cycle would turn the grant into a
presentation limit and fold the two parameters the entry keeps apart.

## State, closure and slot boundaries

A state is the boundary before a cycle's refresh: the phase, each bank's
remaining occupancy including maintenance, the requests in transit, and per
hart its slot occurrence, chosen alternative, program position, held request
with cycles waited, and the stall accumulated in this occurrence. Programs
restart at their slot's start phase every frame with the alternative chosen
afresh, so every counter is bounded and the state space is finite. The
exploration starts empty at phase zero, carries occupancy and transit across
every frame wrap and slot boundary, takes every alternative and arbiter choice
and merges identical states, exactly as the existing checkers do; a
`path-blocked` or `refresh-overlap` step refutes the program contract with its
trace. A request still held at its slot's end is a boundary-outstanding fact
for that (hart, slot), neither dropped nor counted twice. Following R-07-040 it
is the outstanding operation of the residency prefix: the hart presents no
further request of that program, the held request keeps being presented, and
its cycles from the slot end to acceptance are boundary residency, not slot
stall. A request still held when the same hart's next slot occurrence begins is
a `residency-overrun` refutation. Requests accepted but incomplete at the slot
end are drain.

## Outputs and receipts

On closure the report carries, per (hart, slot): `stall_total_max`, the maximum
over all reachable histories and arbiter choices of the stall accumulated in
one occurrence; `stall_single_max`, the longest one request was held;
`boundary_outstanding`, with the shortest witnessing trace when true;
`boundary_residency_max`; and `drain_max`, the maximum cycles from the slot end,
or from a held request's acceptance, until every operation the hart issued in
that occurrence completes under [the completion conventions](completion-model.md),
refresh continuing and the other harts still running. It carries `zero_wait`,
the existing acceptance predicate's verdict on the expanded contract, beside
`expansion` reading `closed`, `refuted` or `unrealizable`. The tests hold
consistency both ways: a closed expansion requires every `stall_total_max` zero
and no boundary-outstanding slot, and that condition requires a closed or
unrealizable expansion. The receipt binds the program, resource and cost bytes
and the instrument, its CLI, its tests and this document by SHA-256, keeps
`target_comparison` equal to `open`, and names what the analysis does not
establish: the actual arbiter, pipeline backpressure, mode changes and initial
states, instruction-stream correspondence, qualified occupancies and refresh,
and WCET.

## Cost join

With `--costs` the instrument reads a `phase-cost` input whose slot ids name
program slots and joins per slot. The candidate `stalls` interval must have an
upper bound no smaller than `stall_total_max`: a smaller upper bound refutes the
join, a lower bound below it is inconclusive. `d_pipe_completion` must cover
`drain_max` the same way. A boundary-outstanding slot keeps the join open with
reason `boundary-outstanding-uncovered` unless `trap_per_switch` is known with
a lower bound at least `boundary_residency_max`; even then the receipt states
that this compares declared intervals at the model's boundaries and verifies no
residency coverage, the join having no timer or handler model and no way to
detect an input measured at other boundaries. Each modeled cycle belongs to
exactly one term: held before the slot end is `stalls`, held from the slot end
to acceptance is residency in `trap_per_switch`, and from acceptance or the
slot end to completion is `d_pipe_completion`. Unknown operands stay open,
favorable arithmetic never outweighs a refutation, and `phase-evaluate` keeps
its zero-wait scope.

## Acceptance cases

Acceptance requires behavioral tests through
`python tools/run.py test --only phase_stall` for: a single hart stalled by a
refresh reservation with the exact bound; two harts contending for one bank
with the nondeterministic loser's bound reported; the grant gap `[2, 0]`, the
joint two harts on one bank and the final-cycle write across frame wrap, each
yielding a finite stall bound while `zero_wait` stays refuted by a realizable
trace; the path-order inversion becoming a counted wait, with equal paths
giving zero; a nonzero-path arrival at a busy bank staying `path-blocked`; a
boundary-outstanding slot with its residency, and a `residency-overrun`; an
alternative whose expanded refutation is unrealizable; a per-hart issue-limit
violation, a program leaving its slot, a stale resource digest and an unknown
field each refused; a consistency case where every bound is zero and the
acceptance predicate closes; and the join refuted by an understated stall
interval, inconclusive on overlap and open on an uncovered outstanding slot.
Synthetic examples must remain visibly synthetic.

## Command and scope

The instrument is the new command `phase-stall PROGRAM RESOURCES --json` with
optional `--costs COSTS`, registered beside the existing four rather than as an
option of `phase-service`, which reads a `Contract`, or of `phase-evaluate`,
whose verdict names the zero-wait branch: one command reading two input kinds
would carry two verdict vocabularies. Exit 0 means the program contract closed,
1 a service, zero-wait or join refutation, and 2 malformed or stale input; read
the named verdicts, not the exit code alone.

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
