# Adversarial retirement envelopes and release-to-reuse bounds

> Non-normative research for the [static-memory agenda](../background/static-memory-research.md).
> The [requirements register](../requirements-register.md) remains authoritative. This
> document accepts no requirement, proposes no register change and confers no
> implementation landing credit. It supplies a declared finite adversary over the
> [fixed reclamation calendar](static-memory-reclamation.md), closed-form bounds with
> their proofs, and bounded search evidence in that calendar's synthetic units.
> [Q22a](../assurance/revocation-qualification.md) owns the authority boundary, and
> nothing here changes its barrier, its predicates or any requirement they serve.

## Replay and artifact identity

Run `python tools/run.py static-memory envelope --json` for the full receipt and
`python tools/run.py test --only static_memory_envelope` for focused behavioral
checks. The receipt emits the adversary's declared budget, each sweep schedule's
bounds term by term, the complete search result per schedule, the comparison of
every search maximum against its bound, the named maximizing schedules, the
violated-premise witnesses and the obligations left open. Source hashes bind the
implementation, its tests, the imported calendar, Q22a's model and both explanatory
contracts. Git identity is supplied by the common research command. Figures stay in
the generated receipt rather than being maintained here as a second table.

The public Python entry point is `vos.static_memory_envelope.report(root)`. It
returns the receipt without writing files, selecting a production schedule or
consulting any target measurement. The command exits nonzero when a search maximum
leaves its bound, when an admitted schedule finds no zeroization slot, or when a
violated-premise witness stops reproducing.

## The service envelope is imported, not restated

The public request calendar, the fixed extent and payload per request, the result
phase, the permanent metadata charge, the fabric, workload and control reservations,
the padded containment interval, the pass-eligibility rule and the whole-slot FIFO
zeroization rule all come from the
[reclamation experiment](static-memory-reclamation.md) unchanged. This module adds
one thing: the moves an admitted workload may make inside that envelope, and the
bounds that survive every combination of them. Where the two disagree, the imported
calendar is the owner, and the focused tests hold the derived envelope equal to the
calendar's own whenever every adversary budget is zero.

## What the adversary may do, and what bounds it

Each move is an admitted limit of the composition rather than an observed rate. The
budget is stated per public period.

| Move | What it does to the calendar | Its declared budget |
| --- | --- | --- |
| Restart storm | Retires an admitted identity again inside its own window, at that identity's release phase, opening another containment pipeline on the fixed control grant | Extra retirements per period |
| Stalled endpoint | Delays the proxy or device acknowledgement to its deadline, so containment completes at `C + D` instead of exactly `C` | Ticks of acknowledgement delay |
| Grant loan outstanding at retirement | Pins the lender's extent from release until containment cancels the loan and clears its borrowed footprint | Loans per period |
| Saved-context retention | Pins a retained copy from release until the post-barrier pass sweeps its location | Retentions per period |
| Stale capability behind the cursor | Revokes a holder after the cursor passed its location, spoiling the pass in progress and forcing the next eligible one | Such events per period |

Four things stay outside the envelope and are not covered by any bound below:
arrival jitter, a release at a phase the fixed calendar does not carry, an unbounded
call whose loan containment cannot cancel, and any move above a declared budget. A
schedule that spends more than one budget is reported as leaving the service
envelope rather than credited with the same service.

## The bounds, and the argument for each

### The worst-case retirement envelope

`alpha(T)` is the largest charge entering release-to-reuse in any window of length
`T`, counted in the half-open window `(s, s + T]` so that a completion precedes an
acquisition at an equal timestamp. Every arrival instant is a release phase of some
public period, so a window meets each period in one contiguous piece and can hold
from that period exactly the phase instants inside the piece. Inside one period the
adversary spends at most its whole budget: one base retirement for each admitted
identity in the piece, its restarts, its loans and its retentions, each charged at
its own fixed extent. Summing those per-period maxima over the periods the window
meets is therefore an upper bound, and it is attained because different periods'
budgets are independent. The calculation enumerates window starts modulo the period,
which is complete because both the calendar and the budget are periodic with it.

The derivation is the reclamation calendar's own periodic-envelope shape with the
adversary's budget added to each period's term, and the focused tests hold the two
equal over a family of phase sets, sweep periods and window lengths whenever every
budget is zero. That equality is the check that this envelope extends the existing
owner's formula rather than replacing it with a second one.

### Release-to-reuse

Let an event release at `r`. Containment is padded to exactly `C`, and an admitted
stall adds at most `D`, so its barrier is no later than `r + C + D`. A pass eligible
for that event starts strictly after the barrier at the first schedule multiple
beyond it, which is no more than `W` later, where `W` is the largest such delay over
the barriers the adversary can reach. A holder revoked behind that pass's cursor
spoils it, because the pass in progress cannot supply the post-barrier coverage the
reuse gate requires, and the next eligible pass begins one sweep period later, which
is the `B` term. The pass itself takes `S`, and the whole extent consumes one whole
zeroization slot at a position no later than the largest cohort a pass can be forced
to serve, which is `Z`. So release-to-reuse is at most `C + D + W + S + Z + B`.

That is the reclamation document's `C + W + S + Z` with two adversarial terms: `D`
on the containment side and `B` on the wait side. The decomposition is deliberately
loose in one place the search exposes: `C + D + W` charges the longest stall and the
longest wait to one event, while the two trade off, since a stall tick that does not
cross a pass boundary buys nothing and one that crosses it spends the wait it just
bought. The module therefore reports the same quantity read once, over phase and
stall together, beside the decomposed shape, and checks the search against the
smaller reading. Neither reading covers an adversary that spoils the same event's
second pass as well; the model gives each event at most one behind-cursor event, and
a budget that allowed two would add another sweep period per extra spoiling.

### The peak retirement charge

Every byte this model charges enters retirement at a release and leaves it at reuse,
at containment for a loan, or at the end of the pass that sweeps it for a retained
context, and each of those is within the release-to-reuse bound of its own release.
So the charge standing at any tick arrived in the half-open window of that length
ending at that tick, and is at most `alpha` of the release-to-reuse bound from zero
initial backlog. An arbitrary initial backlog is an additional charge, as the
reclamation document already states for its own inclusion argument.

### Admissibility, which is a separate question

Two checks decide whether a sweep schedule is a service at all under the declared
adversary. The largest cohort the adversary can force must fit the reserved
zeroization slots, and the concurrent containment pipelines it can open must fit the
fixed control grant. Each declared schedule's zeroization reservation is sized at
exactly its own admitted cohort bound, which is what makes the restart budget
load-bearing rather than decorative: nothing is left over for a storm. A schedule
failing either check is refused with its reason, and no overflow slot is invented.

## What the finite search shows, and what it does not

The search enumerates the whole declared move space at a declared horizon and takes
the maximum of the bytes in retirement, the release-to-reuse latency, the retirement
arrivals at several window lengths, and the containment control demand, naming the
maximizing schedule for each. Two instances are enumerated exhaustively: the
reclamation document's whole public envelope over one window, and a reduced calendar
of the same shape over two windows, because the full envelope's two-window space
does not fit the declared budget. The reduced instance spends no retention budget
for the same reason and says so; retention is enumerated where the one-window
instance enumerates it.

Every enumerated maximum is compared against its closed-form bound, and a maximum
above a bound is an error that fails the command rather than a result. The focused
tests establish that this comparison bites, by shrinking each bound below the
observed maximum and by starving a zeroization reservation until an admitted cohort
overruns it; both must be reported. A separate tick machine rediscovers passes and
consumes zeroization grants without the next-pass formula, the cohort arithmetic or
the production record reader, and its placement must agree with the calendar's on
every sampled schedule.

The search is a lower-bound instrument on the adversary, so an attained bound is a
tightness witness and an unattained one leaves tightness open with its gap reported.
The control-grant demand and the short-window envelope are attained. The
release-to-reuse bound is not, and the search says why: zeroization is FIFO by
immutable request identity, so the identity with the longest wait is also the
earliest identity in its cohort and cannot hold the last zero slot, while the bound
charges both to one event. The long-window envelope is not attained at a one-window
horizon either, for the elementary reason that one window of arrivals cannot fill a
window spanning several periods. Neither observation is evidence that a tighter
bound exists in general; they are the gaps at these horizons.

What the search does not show is anything about a target. Horizons are small, units
are the imported synthetic bytes and ticks, no hardware sweep, zeroization or
containment rate is qualified, and no claim is made about a real binary's holder
set, which the holder-coverage work addresses separately. The move space itself is a
declared model: a restart shares its slot's endpoint and so carries that slot's
stall, and an adversary with independent endpoints per restart is not enumerated.

## Negative results and violated-premise witnesses

The deferred retirement calendar, in which every request releases at the result
phase, is refused outright: its four containment pipelines already saturate the
fixed control grant, so no admitted restart fits beside them. This is a result about
the schedule the reclamation experiment uses as its comparison baseline, and it is
reported rather than repaired by widening the grant.

A storm one restart beyond the admitted budget is enumerated whole over its restart
placements and stalls, and on every admitted schedule it leaves the admitted bound,
through the control grant, through the zeroization reservation, or both. The
declared limit is therefore load-bearing: removing it removes a bound rather than
costing a little more service.

A loan outstanding past containment reaches no containment event and no reuse, and
its lender's extent stays pinned for the whole observation. Q22a's own completion
predicate names the same defect at the authority boundary, and the receipt carries
its refusal beside the timing witness rather than restating it.

The stale capability behind the cursor is exercised through Q22a's predicates and
not through a label. The complete protocol refuses reuse with a resurrection
finding; a second full pass begun after the barrier clears it and reuse is accepted;
a state that reaches the barrier with no post-barrier pass at all is refused for
both the missing pass and the surviving raw tag; and clearing the affected bits
without that pass actually restores the stale saved root to usable authority, which
is what makes the refusal a telling one. A schedule that skips the completion wait
instead, leaving a proxy unacknowledged, is refused by the completion predicate, and
the unacknowledged peer's register still dereferences, so the wait is removing real
authority rather than a label.

## Boundary and remaining work

This experiment reads the register's obligations as premises and changes none of
them. R-08-006 supplies the containment event whose terms the `C` term prices, and
its device term lands at R-15-208a's ownership boundary, which the RTL consumer owes
and this model assumes. R-08-007 supplies the pass as an admitted background slot
rather than a rate, and R-08-007a supplies the reuse gate whose behind-cursor and
stale-copy refusals the witnesses exercise. The reserve a bound names is a
composition charge in R-08-045's sense and not a runtime allocation, and a pool that
cannot serve a binding answers with R-08-047's typed exhausted verdict rather than
with an implicit wait, which is the same discipline this model keeps when it refuses
a schedule instead of inventing a slot. Every term of every bound here is a
composition constant or a declared limit, so no bound reads a teardown rate, which
is what R-08-008a's second clause requires of any bound.

What remains open is what the receipt lists. Qualified sweep, zeroization and
containment service rates on a target are absent. The real composed holder set and
the admitted restart and acknowledgement deadlines a product would declare are
absent. The tightness of the cohort and behind-cursor terms beyond these horizons is
undecided, and the gaps reported are gaps at the enumerated instances rather than
proofs of slack. No statement here is mechanized, and a bounded exhaustive search
over a declared finite move space is not an all-executions theorem.
