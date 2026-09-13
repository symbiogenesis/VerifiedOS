# Compositional reuse under public phases

> Non-normative research for the [static-memory agenda](../background/static-memory-research.md).
> The [requirements register](../requirements-register.md) remains authoritative.
> This experiment supplies a finite model, refuted candidate rules, minimal
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
counterexamples, the adversarial out-of-window timings, the secret-phase witness,
the conjecture with its premises, and the open obligations. Source hashes bind the
implementation and this contract; Git identity comes from the common research
command. Figures stay in the generated receipt rather than being maintained here a
second time.

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
Its work is one comparison per adjacent pair; it forms no product of component
states, and the receipt reports both that comparison count and the number of
timings the exhaustive search enumerates for the same composition.

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
safety failure.

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
reported quantity and not an outcome it simulates. The same quantity is positive on
enumerations the search still calls safe, because R2's declared bound is
conservative for an object that retains no representation.

## Naive summaries and their minimal counterexamples

A summary is a lossy projection of the certificates that the compositional checker
consumes. Three are carried, each with the composition that refutes it. Each
counterexample uses two components and one extent, except the chained one, which
needs three because the defect is a dependency between components.

| Summary | What it drops | Minimal counterexample |
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
accepts a transfer there, the other does not. Their event-gated reuse ticks differ,
so an observer who can see when the successor's extent becomes usable learns which
branch ran. Equal public labels therefore do not give non-interference, and a
certificate published per run leaks the same secret, because the retained set and
the outstanding bound are exactly what differs.

Publishing one conservative certificate covering both branches, and padding reuse
to its declared bound instead of to the observed events, makes that one observation
equal in both runs; the receipt replays both runs under the padded discipline and
both are safe. The price is visible in the same model: the run that needed nothing
holds its extent to the declared bound anyway, which is capacity spent on
indistinguishability.

This witness concerns one observation and two runs. It is not a leakage model, not
a non-interference proof, and no evidence about any other observation. A real
statement needs the observation set declared first, including refusals, completion
reports and anything a peer can time.

## Boundary and remaining work

Nothing here changes admission or any requirement. R-08-018a's same-owner reuse
rule is unchanged: colocating one compartment's pools in the one interference
structure still owes the temporal-safety discipline any slot reuse owes, and this
artifact adds to that discipline no credit and no exemption. R-08-006's containment
completion, R-08-007's sweep service and R-08-007a's reuse gate remain the
normative statements; the rules here are candidate research formulations measured
against a finite model, and R2 is a restatement of those obligations rather than a
new one.

The focused tests compare the compositional verdict against an independent
tick-by-tick oracle over the same enumeration, reproduce each counterexample, check
that both barrier mutants are caught, check that the compositional checker's answer
does not move when a composition's hidden timing detail changes under a fixed
certificate, and exercise the model's refusals. These are bounded executable checks
of finite instances, not verification.

What remains open is what the conjecture's premises name: the barrier
implementation and its bounds, the device completion postcondition in RTL, the
leakage model, the admitted-language derivation of live and retained sets, and a
machine-checked compositional theorem taking those premises as hypotheses. Until
those exist, the refuted rules, the counterexamples and the conjecture are the
result.
