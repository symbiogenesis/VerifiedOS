# Useful slack versus private demand: a two-run lending experiment

> Non-normative research for the [static-memory agenda](../background/static-memory-research.md).
> The [requirements register](../requirements-register.md) remains authoritative.
> This experiment confers no landing credit and accepts no requirement. Cross-owner
> borrowing is excluded today by [R-08-012c](../spec.md#r-08-012c) and
> [R-08-047](../spec.md#r-08-047); nothing here proposes admitting it. What the
> experiment measures is one cost of the excluded branch, so that the open tradeoff
> in the agenda has a finite, replayable answer instead of an intuition.

## Replay and artifact identity

Run `python tools/run.py static-memory lending --json` for the full receipt and
`python tools/run.py test --only static_memory_lending` for focused behavioral
checks. The command emits the observation model, the public calendar, one analysis
per lending policy, both headroom sweeps, the minimal distinguishing pairs, a
black-box probe of what each rule grants, the return-capacity verdicts, and the
counterexample calendars that bound what the fixture's own results may be read to
say. Source hashes bind the implementation, its tests and this
contract; Git identity comes from the common research command. Figures are left in
the generated receipt rather than maintained a second time here.

The public Python entry point is `vos.static_memory_lending.report(root)`. It
writes no files, runs no solver and selects no policy.

## The observation model and its boundary

Two owners hold fixed pools: the **lender** holds `L` equal slots and the
**borrower** holds fewer. Time is a finite sequence of scheduler ticks.

Public inputs are the two pool sizes, the borrower's request calendar, and the
lender's declared occupancy commitment together with the instants at which it
declares a new segment of that commitment. A borrower request names a fixed hold
length and an ordered tuple of declared attempt instants: the request takes its own
pool where the whole hold window fits, takes a loan where the whole window fits
under the policy's capacity, and otherwise waits for its next declared instant.
There is no implicit wait. A request that exhausts its declared attempts carries a
typed refusal, which is the shape [R-08-047](../spec.md#r-08-047) requires of a full
pool and the reason the retry calendar is public rather than a blocking queue.

The secret is the lender's per-tick occupancy trace, drawn from the finite set its
own declared commitment admits. The borrower observes, per request, the verdict
(own-pool fit, borrowed fit, or refusal with its reason) and the completion tick.
Which attempt actually served a request is a fact of the run and not an
observation, because a borrower that read it would see straight through a padded
completion. Low-equivalence between two secret traces is equality of the
declassified label, and the label is empty unless an analysis states otherwise, so
by default nothing about the lender's occupancy is public.

The boundary matters more than the result. A tick is the scheduler frame instant;
the model has nothing below it. Sub-tick timing, cache and predictor state, fabric
and bank contention, energy, and the ownership transition itself are outside the
model, so a leak below that granularity is not one this experiment can see or
exclude. The pools are counts of equal slots, not placed bytes. Every quantity is
a synthetic slot or an ordinal tick; none is a measured size or a measured time.
The frame that keeps slot timing public across a confidentiality boundary is
[R-07-036](../spec.md#r-07-036)'s non-work-conserving schedule, and
[R-08-027b](../spec.md#r-08-027b) states the progress obligation this model is a
finite instance of. This experiment does not re-derive either; it borrows their
shape for memory capacity and reports what changes.

## The policies and what each one costs

The rules below are enumerated over the same public calendar and the same admitted
secret set.

| Policy | What it lends | What the enumeration finds |
| --- | --- | --- |
| None | nothing | Trivially noninterferent: the observation never reads the secret. Every request the borrower's own pool cannot hold is refused |
| Lend any idle slot | the lender's observed idle capacity | Distinguishing on two separate channels, each from a one-tick difference in the secret |
| Lend any idle slot, with completions padded to declared instants | the same capacity, with every completion delayed to the first declared release instant at or after it | On this calendar the timing channel closes and the refusal channel stays open, so the policy is still refuted. The closure belongs to the calendar and not to padding: the receipt carries one whose declared instants leave the padded timing channel open. Padding moves no verdict and buys nothing in slack; the borrower pays for it in latency |
| Reserved headroom `h`, subtracted from observed idle capacity | observed idle capacity above `h` | What it grants moves with the secret at every reserve that lends anything. On this calendar that is observable too, and the least safe reserve is the whole lender pool, which lends nothing; the receipt carries a calendar on which the same family grants on the secret, stays safe and still lends |
| Reserved headroom `h`, held against the declared commitment | a constant `L - h` slots | Noninterferent at every `h`, because the capacity never reads the secret. The binding constraint is return capacity, not information flow |
| Lend only at declared release points | `L` minus the declared ceiling of the current segment | Noninterferent, and the observation recomputes from public inputs alone. Strictly more useful than the flat reserve on this calendar |

The declassifying rule is enumerated twice to separate the two questions. Reading
the lender's actual occupancy **at the declared release instants only** is
distinguishing when nothing is public, and noninterferent when those instants are
declassified labels. That is what a deliberate declassification buys and what it
costs: the lender publishes its occupancy at a fixed, public, composition-time set
of instants, and the borrower's observations then reveal nothing beyond them.

### Leakage through refusal and through timing are different channels

The receipt reports them separately, because a design can close one and leave the
other open. A **refusal** witness is a pair of admitted traces with equal labels
whose verdict sequences differ with a refusal on one side: the borrower learns that
the lender was busy because its own request was declined. A **timing** witness is a
pair whose verdict sequences are identical and whose completion ticks differ: every
request is served, and the lender's demand is still readable from when. A third
naming, **verdict**, covers a difference between own-pool and borrowed service with
no refusal on either side. A difference confined to the refusal reason is named a
refusal and not a timing difference, since a reason that moves with the secret is a
refusal leak whatever the verdicts do. Each witness is the least over every label
class in the number of ticks at which the two secret traces differ, then in
enumeration order, so the receipt shows how small a difference in private demand is
already observable.

Padding is the separate countermeasure that shows why the two channels are worth
naming apart. Delaying every completion to the first declared release instant at or
after it makes the timing witness vanish on this calendar and leaves the refusal
witness exactly where it was, so a lend-any-idle rule with padding is still refuted.

That closure is a property of the calendar rather than of padding, and the receipt
says so by carrying a counterexample rather than leaving the reader to assume the
general rule. A completion already sitting on a declared instant is not moved at
all, so padding confuses two completions only where both fall strictly inside one
declared segment; where the declared instants are spaced against the completions the
padded rule leaks through timing as well. What padding does establish on any
calendar is the asymmetry: it changes no verdict, which is both why it cannot reach
the refusal channel and why it costs the borrower latency rather than capacity, the
receipt reporting the same slack with and without it. A design reaching for padding
alone is closing the channel it can see, and only where its own schedule lets it.

### The two headroom families answer to different obligations

The two reserves are not two settings of one knob, and telling them apart is what
the agenda's question needed a model for rather than a judgement.

A reserve subtracted from the lender's *observed* idle capacity grants an amount
that moves with the secret at every reserve that lends anything, since an empty
lender is admitted at every tick here and only reserving the entire pool clamps the
grant to zero. The receipt reports that grant separately from the noninterference
verdict, by probing the rule over the whole admitted set, because the first does not
imply the second: what the borrower observes is what its own requests reach, and a
request that never reaches the ticks at which the grant moves observes nothing. On
this calendar the borrower does reach them, and the enumeration finds the least safe
reserve to be the whole pool, with no useful slack left at it. That is a fact about
this calendar, and the receipt carries another on which the same family grants on
the secret, stays noninterferent at every reserve and still lends. Nothing here
supports a general claim that an idle-subtracted reserve must choose between lending
and hiding.

A reserve held against the lender's *declared commitment* never reads the secret at
all, so its capacity is fixed by the public calendar by construction and the
enumeration finds it noninterferent at every level. What limits it is a different
obligation entirely: a loan granted beyond the lender's committed peak can still be
outstanding when the lender's own admitted demand arrives. The receipt reports that
as an overcommit with the ticks at which it happens, and the least reserve that is
both noninterferent and return-safe is the lender's committed peak. The useful slack
that remains is the gap between the pool and that peak, which is exactly the
capacity the lender has publicly promised never to need.

The declared-release rule improves on the flat reserve without weakening either
verdict, by letting the commitment vary over time: after the lender declares a lower
ceiling, more of the pool is lendable, and the borrower's observations still
recompute from public inputs alone. A label about the lender's *past* occupancy does
not do the same work. The declassified variant is safe relative to its labels and
still overcommits, because occupancy declared at one instant says nothing about the
demand arriving at the next one.

## What this does not establish

**No universal impossibility is asserted.** A policy with no distinguishing pair
here is not proved noninterferent; it has survived one finite calendar, one finite
admitted set and one granularity, which is a great deal less. A policy with a
distinguishing pair is refuted outright by an exhibited counterexample, and that
asymmetry is the evidential value of the enumeration: the negative results are the
strong ones.

**A result belongs to the calendar that produced it.** The same asymmetry applies to
the experiment's own summaries, so where the fixture invites a general reading the
receipt carries the calendar that refutes it: one on which padding leaves the timing
channel open, and one on which an observed-idle reserve grants on the secret and is
observed by nobody. Neither replaces a proof about the general shape, and neither is
offered as one; they mark where the fixture's answer stops.

**A relational result is not an admission argument.** Noninterference over these
observations is one obligation out of several the excluded branch owes, and the
experiment already exhibits a policy that passes it and fails another. The
[research agenda](../background/static-memory-research.md) names the rest: the
branch owes a proved ownership transition, reserved return capacity, and the
authority proofs that make a loaned slot safe to reclaim.
[R-08-012c](../spec.md#r-08-012c) refuses a placement outside the owning island's
root capability by having no derivation for it rather than by failing a test, so a
loan is not a scheduling decision that a policy argument could settle; it is a
capability derivation that does not exist.
[R-08-045](../spec.md#r-08-045) charges every physical byte to the signed
composition and admits no runtime path to unplanned storage, so a lending mechanism
would have to be charged at admission, not discovered at run time. Nothing in this
experiment supplies any of that, and a green replay supplies none of it either.

**The declassification here is a modeling device, not a mechanism.** Where the
system has a sanctioned declassifier it is the powerbox, under
[R-08-024](../spec.md#r-08-024) and [R-08-025](../spec.md#r-08-025): a delimited
release the theorem quantifies over. This experiment's public labels are a
composition-time constant in a finite model, and no claim is made that they would
compose with that statement.

**The numbers stay in the receipt.** How many traces the admitted set holds, how
many of them overcommit, which pair is minimal and how much slack each policy leaves
are outputs of the replay command, not figures maintained in this prose.

## Checks and remaining work

The focused tests decide the enumeration against a direct pairwise checker that
compares every label-equal pair with no grouping step, and decide the simulator
against an independent recomputation from held intervals and slot identities rather
than per-tick counters. They check that each reported witness is least over every
label class rather than inside one, is label-equal, and actually distinguishes, on
the overall verdict and on each channel separately; that mutating a safe policy into
one that reads the secret is caught, on the enumeration and on the independent
checker; that a reserve below the committed peak keeps noninterference and loses
return capacity; that padding closes the timing channel on the fixture, actually
delays a completion, leaves the refusal channel open, and does not close the timing
channel on the calendars whose declared instants are spaced against it; that an
observed-idle reserve granting on the secret can still be noninterferent and still
lend, which is what bounds the fixture's own headroom result; that refusal typing
survives every policy and trace, with service only at a declared attempt instant;
and that malformed models and oversized secret spaces are refused rather than
truncated.

What remains open is everything the model deliberately excludes. The observation
set is coarse and a finer one may distinguish policies this enumeration cannot.
The calendar is synthetic and small; a representative service, its real request
shape and its real hold lengths are not available here. The ownership transition,
the revocation of a returned loan's authority, and the admission-time charge for a
lending mechanism are unmodeled and remain the branch's principal obligations. The
agenda's architecture item stays unselected: this is a measurement of an excluded
branch's cost, and it argues for no change to the register.
