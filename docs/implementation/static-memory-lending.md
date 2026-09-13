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
per lending policy, both headroom sweeps, the minimal distinguishing pairs and the
return-capacity verdicts. Source hashes bind the implementation, its tests and this
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
Low-equivalence between two secret traces is equality of the declassified label,
and the label is empty unless an analysis states otherwise, so by default nothing
about the lender's occupancy is public.

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

Five rules are enumerated over the same public calendar and the same admitted
secret set.

| Policy | What it lends | What the enumeration finds |
| --- | --- | --- |
| None | nothing | Trivially noninterferent: the observation never reads the secret. Every request the borrower's own pool cannot hold is refused |
| Lend any idle slot | the lender's observed idle capacity | Distinguishing on two separate channels, each from a one-tick difference in the secret |
| Reserved headroom `h`, subtracted from observed idle capacity | observed idle capacity above `h` | Distinguishing at every reserve that lends anything; the least safe reserve is the whole lender pool, which lends nothing |
| Reserved headroom `h`, held against the declared commitment | a constant `L - h` slots | Noninterferent at every `h`, because the capacity never reads the secret. The binding constraint is return capacity, not information flow |
| Lend only at declared release points | `L` minus the declared ceiling of the current segment | Noninterferent, and the observation recomputes from public inputs alone. Strictly more useful than the flat reserve on this calendar |

A sixth rule is enumerated twice to separate the two questions: a policy that reads
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
no refusal on either side. Each witness is minimal in the number of ticks at which
the two secret traces differ, then in enumeration order, so the receipt shows how
small a difference in private demand is already observable.

### The two headroom families give opposite answers

This is the experiment's sharpest result and the reason the agenda's question needed
a model rather than a judgement. A reserve subtracted from the lender's *observed*
idle capacity leaves the granted amount a function of the secret at every reserve
that does not clamp it to zero for the whole admitted set, and since an empty lender
is admitted at every tick here, only reserving the entire pool clamps it. The
enumeration finds exactly that: the least safe reserve is the whole pool and the
useful slack there is zero, so in this model shape an idle-subtracted reserve either
lends or hides and never both. A reserve held against the
lender's *declared commitment* never reads the secret at all, so it is
noninterferent at every level, and what limits it is a different obligation
entirely: a loan granted beyond the lender's committed peak can still be
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
than per-tick counters. They check that each reported witness is minimal, is
label-equal, and actually distinguishes; that mutating a safe policy into one that
reads the secret is caught, on the enumeration and on the independent checker;
that a reserve below the committed peak keeps noninterference and loses return
capacity; that refusal typing survives every policy and trace, with service only at
a declared attempt instant; and that malformed models and oversized secret spaces
are refused rather than truncated.

What remains open is everything the model deliberately excludes. The observation
set is coarse and a finer one may distinguish policies this enumeration cannot.
The calendar is synthetic and small; a representative service, its real request
shape and its real hold lengths are not available here. The ownership transition,
the revocation of a returned loan's authority, and the admission-time charge for a
lending mechanism are unmodeled and remain the branch's principal obligations. The
agenda's architecture item stays unselected: this is a measurement of an excluded
branch's cost, and it argues for no change to the register.
