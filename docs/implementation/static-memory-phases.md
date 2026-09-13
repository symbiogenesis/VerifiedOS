# Compositional reuse under public phases

> Non-normative research for the [static-memory agenda](../background/static-memory-research.md).
> The [requirements register](../requirements-register.md) remains authoritative.
> This experiment supplies a finite model, refuted candidate rules, reduced
> counterexamples and one conjecture with explicit premises. It is not a theorem, a
> barrier implementation, a leakage model or a measurement; it confers no
> implementation landing credit and accepts no requirement. The
> [revocation qualification](../assurance/revocation-qualification.md) owns the
> completion and reuse predicates, and the
> [baseline](static-memory-baseline.md) owns the lifecycle order this model refines.

The agenda's open proof problem asks whether per-component phase certificates can
establish global non-overlap and bounded reuse without enumerating every
combination of component states. The baseline already refutes reuse at the public
phase boundary with a late device completion. This artifact turns that single row
into a model, three candidate rules, a compositional checker, an exhaustive search
that can refute a rule, and the witnesses that separate them.

## Replay and artifact identity

Run `python tools/run.py static-memory phases --json` for the full receipt and
`python tools/run.py test --only static_memory_phases` for the focused behavioral
checks. The command emits the compositions, every certificate, the compositional
verdict and the exhaustive verdict for each rule and each certificate summary, the
counterexamples with the reduction search each one is put through, the adversarial
out-of-window timings, the secret-phase witness, the conjecture with its premises,
and the open obligations. Each composition's row carries its outstanding-completion
bound as declared and as recomputed, beside the compositional checker's own costs.
Source hashes bind the implementation and this contract; Git identity comes from the
common research command. Figures stay in the generated receipt rather than being
maintained here a second time.

The public Python entry point is `vos.static_memory_phases.report(revision)` in
[static_memory_phases.py](../../tools/vos/static_memory_phases.py). It writes no
file, runs no solver and selects no schedule. Ticks, extents and phase indices are
synthetic model quantities; none is a measured time, an address or a target
schedule.

## The finite model

A component has a fixed public phase schedule: strictly increasing boundaries on a
tick axis shared by every component, one public label per phase. Phase boundaries
are composition constants, which is what makes them public.

Each object binds one global extent for a contiguous run of phases. Its occupancy
runs from the start of its first live phase to the end of its last live phase, or
to the end of a later retention phase when the component retains its state past the
public live boundary. An object may also carry a retained capability-bearing
representation: a holder that can still write the extent until a full pass removes
it. Those two are the halves of the retained set, and they fail differently.

A component may accept asynchronous device transfers. Each transfer names the
object whose authority it carries, the phase in which it is accepted, and a
declared bounded completion window. A transfer may instead be accepted on another
transfer's completion, which is how a chained acceptance enters the model: its
acceptance is then no longer a public phase boundary.

A per-component certificate is exactly the phase schedule, the per-phase live set,
the retained set, and the outstanding-completion bound. The bound appears in the
two forms the candidate rules read: the maximum per-transfer completion window, and
the latest tick past an object's occupancy end at which a transfer under its
authority can still complete. The certificate carries no acceptance time, no
completion time and no other component's state. `certificate` projects a component
onto it, so what the compositional checker can see is decided by a function and not
by a convention.

The outstanding-completion bound is the one certificate field the barrier rule's
soundness rests on, so the model recomputes it from the composition's own transfers,
chained acceptance resolved in order, and refuses a component that declares less
than its transfers admit. A declaration above the recomputed value is admitted: it
costs reuse and cannot make an acceptance unsound. An honest certificate here is
therefore a checked property of the composition rather than a label attached to it.
For in-window timings (`delta=0`), this validation premise makes an honest R2
acceptance sound by construction in the declared model: the completion bound
covers all admitted transfers and the reuse rule adds the clearing services. The
finite enumeration checks that the implementations agree on those premises; it
does not independently establish a completion contract for a real device.

The global plan is one reuse chain per extent: the ordered objects that bind it. A
successor binds its extent at its declared public start. This model has no runtime
gate that could delay that binding, which matches a design with no online placement
and is the reason a violated certificate shows up here as corruption rather than as
a late start.

Three hazards are modeled, each an old-authority event landing on an extent bound
to a later object:

| Hazard | What happens | What removes it |
| --- | --- | --- |
| `occupancy-overlap` | The predecessor's retained state is still resident when the successor's declared start arrives | A certificate whose retained set is complete, and a plan that respects it |
| `device-completion` | A transfer accepted under the old authority completes after the extent is re-bound | Completion of every accepted transfer under the old authority, with R-15-208a's ownership postcondition |
| `stale-representation` | A retained capability-bearing holder writes the extent after it is re-bound | R-08-006's barrier followed by R-08-007a's full post-barrier pass |

The authority barrier is the composition's two service constants: clearing the live
and saved roots, and the full pass begun after that barrier. Neither is implemented
here. The model assumes the barrier does what Q22a's predicates say it does, and
the experiment's subject is what a rule and a certificate decide given that
assumption.

## The candidate rules

| Rule | Earliest reuse | Status in this fixture |
| --- | --- | --- |
| R0 | The public phase boundary | Refuted: it accepts compositions the enumeration corrupts |
| R1 | That boundary plus the component's declared maximum completion window | Refuted: a window bound names no barrier and no pass, and a chained acceptance escapes it |
| R2 | Only after the barrier: every accepted transfer completed under the old authority, live roots cleared, and a full post-barrier pass | Not refuted here, and not vacuous: it accepts compositions the enumeration finds safe |

Two mutants of R2 are carried beside them, because a rule that is right and an
implementation that is right are different claims. `R2-skip-device` computes its
barrier without waiting for outstanding completions; `R2-skip-pass` reuses at the
barrier without the pass. Each is a rule in the same sense as R2 and is measured
the same way.

## What the bounded enumeration decides

The compositional checker reads the certificates and the chains alone. For each
adjacent pair on a chain it derives the predecessor's earliest reuse tick from that
predecessor's own certificate and compares it with the successor's declared start.
The certificates and the chains are its whole argument list, so no product of
component states is reachable from it; what the receipt reports is therefore two
counts it measured, the comparisons made and the certificates consulted, beside the
number of timings the exhaustive search enumerates for the same composition.

The exhaustive search enumerates every completion timing inside the declared
windows, resolving chained acceptances in order, and looks for any of the three
hazards. Its verdict is over that enumeration and that model only.

The soundness comparison classifies every composition, rule and summary into four
cells: a sound acceptance, an unsound acceptance, a necessary refusal and a
conservative refusal. The requirement the experiment holds is one-sided: a
compositional acceptance must never stand where the exhaustive search exhibits a
hazard. Under honest certificates R2 has no unsound acceptance in this fixture, and
under honest certificates every refusal in this fixture is necessary, so the
comparison is not passing by refusing everything. A conservative refusal appears
only where a summary overstates a bound, which is the remaining cell and is not a
safety failure. That second reading comes from the census of the four cells the
receipt reports for the honest rows, and not from the experiment's own invariants,
which hold the one-sided requirement and the non-vacuity alone: a later fixture
that refused conservatively under an honest certificate would move the census
without turning the command red, because conservatism costs reuse and not safety.

R0's unsound acceptance reproduces the baseline's failed-rule row as an executable
witness: the transfer is accepted before the phase ends, the successor is
initialized at the same extent at the next boundary, and the completion lands on
it. R1 is refuted twice and for two different reasons. A retained representation
survives a window bound entirely, because R1 names no clearing service at all; and
a chained acceptance completes past the boundary-plus-own-window tick, because the
acceptance that the window is measured from is another component's completion.

The barrier mutants are caught by the compositions that discriminate them.
`R2-skip-device` accepts where a long outstanding window lands a completion on the
successor. `R2-skip-pass` accepts where a retained representation writes between
the barrier and the pass that was skipped. Neither is caught by every composition,
which is why the fixture carries more than one.

An adversarial family completes one transfer outside its declared window while the
others take their declared worst case. A violated certificate voids the conclusion
for R1 and for R2 alike: in this model the successor binds at a composition
constant, so the late completion corrupts it. That is a property of the model's
static binding, not a claim that R2 has no defence. An implementation that gates
the binding on the observed completion event converts this corruption into a missed
declared start, and the receipt records the largest such shortfall over each
enumeration. This model does not represent that gate, so the shortfall is a
reported quantity and not an outcome it simulates. Inside the declared windows the
shortfall is zero wherever the search calls an enumeration safe. It is positive on a
safe enumeration only in the adversarial family, and there what pushes the release
past the declared start is the overrun rather than any conservatism in the rule.

## Naive summaries and their counterexamples

A summary is a lossy projection of the certificates that the compositional checker
consumes. Three are carried, each with the composition that refutes it. How small a
refutation has to be is then decided by a reduction search rather than asserted. The
search removes one thing at a time under a declared set of reductions: fold two
components onto the union of their schedules, drop a transfer together with
everything whose acceptance waited on it, shorten a window, drop a retention, drop a
retained representation. Every candidate also retightens the per-component window
and outstanding-completion certificates against its remaining transfers. A fold
preserves every start, occupancy end and acceptance tick the enumeration reads;
certificate retightening can change the lossy summary's answer. A step survives
only when the honest certificate still refuses, the summary still accepts, and
the enumeration still exhibits a hazard.

Two of the three defects turn out to need no composition at all: each folds onto a
single component holding two objects on one extent, where the summary's acceptance
is still unsound. The chained fixture's reduction stops with a composition boundary
under this operator set and order. That is a bounded reduction result, not a
necessary feature of the defect: two transfers under the same object's authority
can chain within one component, and a separate focused counterexample reproduces
that case. The receipt carries each search's starting shape, the reductions it
applied and the shape it reached.

What that establishes is irreducibility under those reductions, not minimality. No
reduction here removes an object or rewrites a schedule, and nothing outside the
reduction order is searched; calling a witness minimal would be a claim about every
composition, which this artifact does not establish.

| Summary | What it drops | Composition the search starts from |
| --- | --- | --- |
| Drop the retained set | Presumes the object dead at its public live boundary | A component that retains its state through a later phase, and a successor that binds the extent inside that retention. The honest certificate refuses; the summary accepts; the enumeration exhibits both a residency overlap and a late completion |
| Drop the completion bound | Presumes no transfer outstanding past the occupancy end | A component whose accepted transfer has a window far longer than the barrier and pass service. The honest certificate refuses; the summary accepts; the completion lands on the successor |
| A window bound that chains across components | Adds a component's own window to its own public boundary while its acceptance waits on another component's completion | Three components: the first accepts a transfer, the second accepts one on that completion, the third binds the second's extent. The honest bound is absolute and refuses; the local-window summary accepts; the chained completion lands on the third |

The three defeat the compositional check in the same way and are worth keeping
apart because the repairs differ. The first is a modeling obligation on the
component: the retained set must carry what the component actually holds. The
second is an obligation on the device interface: an accepted transfer has a bound
or the composition is refused. The third is an obligation on the certificate's
shape: an outstanding-completion bound is absolute against the public schedule, not
a duration measured from an event another component decides.

## The surviving conjecture

Under the premises below, the per-component certificates and the per-extent chain
decide global non-overlap and bounded reuse without enumerating component states.

1. Public phase schedules are composition constants shared by every component.
2. Each certificate's retained set carries occupancy retention and every
   capability-bearing representation of the object.
3. Each outstanding-completion bound is an absolute latest completion relative to
   the component's own public schedule and depends on no other component's events.
4. Every extent carries one declared reuse chain whose successor start is a
   composition constant.
5. Reuse follows R2, and the barrier and the post-barrier pass are actually
   realized.
6. The modeled hazards are the only ones.

This is a conjecture with bounded executable evidence over one finite fixture. It
is not a theorem, it says nothing about compositions outside that fixture, and it
claims no completeness: a refusal shown necessary here is not proved necessary in
general.

A proof would need three things this artifact does not have. It would need Q22a's
barrier realization, meaning an implementation of publication, root clearing,
bounded loan cancellation, proxy acknowledgement and the post-barrier pass, with
the containment and pass bounds R-08-006 and R-08-007a require. It would need
R-15-208a's RTL-enforced completion postcondition, which this model assumes as the
meaning of a completion event and which alone makes premise 3 a fact about hardware
rather than a declaration. And it would need a declared leakage model before any
premise about phase selection becomes an information-flow claim. The admitted
language must also supply the per-phase live and retained sets; the baseline's open
lifetime bridge is the same obligation seen from the placement side.

## Secret-dependent phase selection

Two runs share one public phase schedule and one label sequence and differ only in
the branch a secret selects: one retains its object through the idle phase and
accepts a transfer there, the other does not. The tick at which the old authority's
own reuse service finishes differs between them, so an implementation that released
the extent on that event rather than at the declared bound would show which branch
ran to anyone who could time the release. That separation is in a tick the receipt
reports and the model does not simulate as a binding: both runs bind the successor
at the same declared public start, which is why this is an argument about an
event-gated implementation and not an observation of this enumeration. Equal public
labels therefore do not give non-interference, and a certificate published per run
leaks the same secret, because the retained set and the outstanding bound are
exactly what differs.

Publishing one conservative certificate covering both branches, and padding reuse
to its declared bound instead of to the observed events, makes that one observation
equal in both runs; the receipt replays both runs under the padded discipline and
both are safe. Equality under padding is a property of publishing one certificate
and not a measurement, and the receipt separates the two: it names which of its
booleans are guarantees of how the runs are built and which are computed outcomes.
What is computed is that the published certificate is a join covering each branch's
own bound, that the event-gated ticks differ, and that both padded runs survive the
enumeration. The price is visible in the same model: the run that needed nothing
holds its extent to the declared bound anyway, which is capacity spent on
indistinguishability.

This witness concerns one observation and two runs. It is not a leakage model, not
a non-interference proof, and no evidence about any other observation. A real
statement needs the observation set declared first, including refusals, completion
reports and anything a peer can time.

## Boundary and remaining work

Nothing here changes admission or any requirement. R-08-018a is unchanged, and it is
its criterion that this artifact must leave standing: colocating one compartment's
pools in the one interference structure owes the R-08-015 temporal-safety discipline
any slot reuse owes, and this artifact adds to that discipline no credit and no
exemption. R-08-015 is where the barrier and the reuse gate already compose at a
slot's reuse point, and R-08-006's containment completion, R-08-007's sweep service
and R-08-007a's reuse gate remain the normative statements. The rules here are
candidate research formulations measured against a finite model, and R2 is a
restatement of those obligations rather than a new one.

The focused tests compare the enumeration's verdict against a tick-by-tick oracle
written beside it. The oracle resolves acceptance, extent ownership and the clearing
service each rule names on its own, walking the services forward from its own
rule-to-service table rather than reading the checker's intervals, so a rule wired
to the wrong service disagrees instead of being confirmed twice. What it does not
make independent is the definition of the three hazards, which is the model itself
and which no second implementation of the same model would vary. The tests also
count the admitted timing space apart from the function that builds it, reproduce
each counterexample and each reduced witness, check that both barrier mutants are
caught, check that the compositional checker's answer does not move when a
composition's hidden timing detail changes under a fixed certificate, check that a
certificate its own transfers falsify is refused, and exercise the model's other
refusals. These are bounded executable checks of finite instances, not verification.

What remains open is what the conjecture's premises name: the barrier
implementation and its bounds, the device completion postcondition in RTL, the
leakage model, the admitted-language derivation of live and retained sets, and a
machine-checked compositional theorem taking those premises as hypotheses. Until
those exist, the refuted rules, the counterexamples and the conjecture are the
result.
