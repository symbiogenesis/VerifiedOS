# Fixed-schedule reclamation and capacity experiment

> Non-normative research for the [static-memory agenda](../background/static-memory-research.md).
> This experiment supplies synthetic calendar arithmetic and finite host observations.
> It qualifies no hardware service rate, executable workload, source-holder map or theorem.
> The [requirements register](../requirements-register.md) remains authoritative: this
> experiment accepts no requirement, and its outputs confer no landing credit.
> [Q22a](../assurance/revocation-qualification.md) owns the authority boundary, and the
> [baseline](static-memory-baseline.md) states the release-to-reuse model.

## Replay and artifact identity

Run `python tools/run.py static-memory reclaim --json` for the full receipt and
`python tools/run.py test --only static_memory_reclaim` for focused behavioral
checks. The command emits the input envelope, each policy, fixed service grants,
per-request lifecycle events, a disjoint byte timeline, precomputed slot bindings,
conditional bounds, the holder class map with the calendar terms it derives, every
Q22a counterexample at the stage this schedule refuses it, and rejected neighbors.
Source hashes bind the implementation, tests and explanatory contract. Git identity
is supplied by the common research command. Figures below are intentionally left in
the generated receipt rather than maintained as a second table.

The public Python entry point is `vos.static_memory_reclaim.report(root)`, whose
optional second argument replaces the declared holder class map so a drifted map
can be replayed. It returns the receipt without writing files, running a solver or
selecting a production schedule. The tool takes no target contract as input; this
is a replayable constructed witness.

## One external service contract

`Envelope` supplies a public periodic request calendar, a fixed extent and useful
payload per request, a result-delivery phase, permanent metadata/outbox backing,
and per-tick fabric, workload and control reservations. Each period permits any
subset of its fixed request identities. The full calendar dominates those subsets.
The experiment excludes arrival jitter and extra restarts from this envelope;
neither is hidden inside an average request rate.

Each request owns one input slot. Four independent pure tasks occupy fixed
one-tick compute phases and copy their results to the permanently charged outbox.
Results remain externally visible only at the fixed delivery phase. The deferred
policy retains all input slots until delivery. The eager policy releases each
input after its own task. Both rely on the explicit premise that the outbox is
sufficient and no task, output reader or asynchronous operation still needs that
input. This is an abstract service-equivalence premise, not a proof about emitted
code. A real service must establish it before using this schedule freedom.

Permanent backing is the same in every policy. Each live slot is partitioned
into useful payload and slot slack. After release its entire charged extent,
including slack, belongs to exactly one of Quiescing, quarantine, zeroization or
failed retention. The receipt also reports total occupied backing. An unused
portion of a fixed workload grant stays reserved: faster sweeping cannot treat
it as free service.

## The calendar and its conditional bound

Successful containment takes the synthetic `C` ticks exactly, padding early
completion. `C` pays the protocol obligations that belong to no holder class
(publication, proxy notification, accepted DMA completion and proxy
acknowledgement), then the declared charge of every holder class it retires. Each
serial job has an explicit synthetic byte cost. The maximum concurrent control
pipelines over the periodic calendar must fit the fixed control reservation. This
complete cost assumption is not extracted from Q22's event counter or a measurement
of the target. Missing or failed evidence takes the failure path.

A sweep starts only at composition-fixed multiples of its period. The start must
be strictly later than the containment timestamp. A pass already running cannot
qualify. Every pass covers the same complete authority-source map, including
saved representations and copies outside retired data. `S` charges each holder
class that map contains once, at its declared cost and the pass's fixed service
rate, rather than counting a fixed number of groups. The next section states what
that coverage is coverage of. The mapping to admitted code and the invariant
preventing repopulation remain premises.

Each pass has a separate fixed zeroization window after its full sweep. A whole
retired extent consumes one zero slot in immutable request-identity order. No
partial-slot completion is reusable. The bound calculation enumerates one
hyperperiod of the external and sweep calendars, maps every containment to its
eligible pass, and checks the largest cohort against that pass's zero slots.
Mapping pass starts modulo the hyperperiod includes cohorts crossing its cut.
An overfull cohort is refused; replay retains overflow without inventing service.

Let `W` be the largest containment-to-next-pass delay over that calendar, `S` the
complete pass duration, and `Z` the largest cohort's whole-slot zero duration.
Under successful containment, complete coverage, no repopulation and the checked
service reservations, the conservative release-to-reuse bound is `C + W + S + Z`.
The unphased bound on `W` is one sweep period. The phase-specific calculation can
be smaller. Because removal of an optional request only removes work from its
fixed cohort, this conditional argument covers every subset of the same infinite
periodic calendar. It covers no other admission envelope and no failed endpoint.

`retirement_envelope` derives `alpha(T)` directly from the infinite release
calendar, not from the displayed finite run. Split `T` into whole periods and a
remainder: whole periods contribute their complete charged batch; enumerate every
possible window start modulo the period for the maximum remainder charge. Events
are counted in `(s, s+T]`, and reuse completion precedes acquisition at equal time.
The baseline's inclusion argument gives `Q(t) <= alpha(C + W + S + Z)` from zero
initial backlog under those successful premises. Arbitrary initial backlog is an
additional charge. Separate peak useful backing and peak retirement reserve need
not coexist; adding them supplies a conservative budget, not an optimum.

The finite timeline independently reports actual peak occupied backing and
quarantine for its declared horizon. A cyclic request-id-to-slot assignment is
replayed at both its required slot count and the smaller fixed comparison capacity.
No placement search or runtime borrowing rescues a request whose assigned slot is
still retained. The finite peak is an observation. The conditional delay/envelope
argument is a separate statement with its own premises; neither is a mechanized
all-executions capacity theorem.

## Holder coverage, and what it is coverage of

Coverage here means coverage of [Q22a](../assurance/revocation-qualification.md)'s
own fixture holder map and its admitted shapes. It is not coverage of a production
binary: nothing in this experiment discovers a root, a saved image or a derived
base in emitted code, and a green coverage result confers no such discovery.

Every holder the qualification fixture supplies is classified into a holder class,
and each class is assigned the lifecycle stage that retires it. Containment clears
the live root set on each core, cancels the admission-proved loan footprint, and
awaits proxy acknowledgement and the device completion boundary. The post-barrier
full pass reaches the saved and memory representations that survive containment.
A class neither stage reaches is unaccounted, and an unaccounted class refuses the
calendar rather than deriving a term from it.

| Holder class | Fixture holders | Stage that retires it | Why that stage |
| --- | --- | --- | --- |
| `live-general-root` | `register` | Containment | Core cleanup clears the whole live root set, so no raw tag survives the barrier |
| `live-special-root` | `mepcc` | Containment | The same cleanup covers the executable and sentry roots the merged register view omits |
| `borrowed-live-root` | `callee` | Containment | Core cleanup and loan cancellation both reach a live borrowed root |
| `remote-delegate-root` | `remote-register` | Containment | The proxy core's cleanup precedes the acknowledgement the barrier waits for |
| `loan-copy` | `loan-copy` | Containment, and the pass visits it | Loan cancellation clears the stored copy; the pass still covers its storage |
| `saved-context` | `saved` | Post-barrier pass | Filtered restore hides it before the barrier; only the pass destroys the raw tag |
| `trusted-stack-root` | `trusted-stack` | Post-barrier pass | The same, for the trusted stack's saved roots |
| `grant-storage` | `grant-storage` | Post-barrier pass | Capability-bearing memory is swept, not scrubbed at containment |
| `outside-interval-copy` | `outside-interval-copy` | Post-barrier pass | The load filter keys on the capability's base, not on where the representation sits |
| `proxy-slot` | `proxy-slot` | Post-barrier pass | The remote island's capability-bearing memory |
| `unrelated-grant` | `unrelated-grant` | Post-barrier pass | The pass visits it and must leave it usable |
| `interior-representation` | `interior-<n>` | Post-barrier pass | One representation at each admitted interior granule base |

The table is checked against Q22a's model rather than asserted beside it. For each
class the experiment replays containment from the qualification's own primitives,
asks whether the raw tag is gone, and asks whether the holder sits inside the
composition's swept footprint. A declared stage that the model does not perform,
a declared structural signature that contradicts the fixture holder's own fields,
a holder no class matches, and a class charged at neither stage are each a refusal.

The charge is per class and not per holder. A wider retired object adds holders to
`interior-representation` and moves neither term; a composition that introduces a new
kind of saved context lengthens `S` and the `C + W + S + Z` bound with it. The
receipt reports both, with the derived terms and the bound for each variant, so the
movement is replayed rather than restated here. Q22a's own illustrative sweep
ledger charges one group per mapped holder: that is a different accounting from
this one, and neither is a measurement of a target. A synthetic per-class cost is
not a scrub time.

One variant is a negative result worth naming. Adding a class that containment must
retire lengthens `C`, but in this phase-aligned calendar the containment timestamp
moves inside the same sweep period, so `W` shrinks by what `C` gained and the bound
does not move. That cancellation is a property of this fixed calendar, not a general
one: it fails as soon as the longer containment crosses a pass boundary.

## Results that distinguish the costs

The receipt compares deferred/eager retirement against slower/faster sweep
calendars, including both individual changes as ablations. In the constructed
witness, the joint change completes reuse before the next request burst and the
smaller fixed backing admits the same public request calendar. Neither individual
change achieves that result. The improvement is reduced overlap between the old
incarnation and the next admission; the separate peak quarantined charge does
not shrink. Calling the recovered backing a reduction of peak quarantine would
misdescribe this result.

An additional faster reservation overlaps sweep and zero traffic enough to remove
required workload grants. It is rejected even though a reclamation-only model
could call it faster. A restart-stress input doubles the retirement burst: this
changes the external envelope and exceeds the zero window. It is explicitly
refused rather than credited as the original service. A real restart contract
must price those arrivals and any simultaneous recovery workspace before deriving
a reserve; this experiment's positive comparison excludes them.

For failed containment, the model reports the bounded failure decision, keeps
the affected slots retained, and refuses later requests at their fixed bindings.
There is no successful reuse bound. Time passing or a cursor reaching its end
does not clear that state. A finite pool limits failed-retention capacity
structurally, at the cost of exhausting service.

## Boundary checks and remaining work

The experiment calls Q22's existing predicates for saved-context restoration,
resident and special registers, loans, missing proxies, delayed accepted DMA,
narrowed bases and post-barrier full passes. It also reintroduces a raw saved tag
behind a completed cursor and actually observes restored authority after premature
bit clearing. This is a telling rejected neighbor, not merely an invalid label.
The positive fixture reuses safely while retaining its unrelated grant.

Every one of Q22a's generated counterexamples is routed through this schedule by
its own refusal reasons, and each is refused at the stage those reasons name. A
completion refusal never reaches a barrier, so the schedule issues no pass and the
extent stays charged from the failure decision onward. A reuse refusal reaches its
post-barrier pass, the schedule pays for that pass and keeps the request's reserved
cohort position, and reuse is still withheld, so the extent stays charged from the
end of the pass. Neither refusal recovers backing as time passes. The routing is a
replay of Q22a's decisions in the calendar, not a second qualification of them.

Focused tests compare the optimized periodic-envelope calculation against direct
sliding-window enumeration. A separate tick machine discovers eligible passes,
enqueues their zero work and consumes individual service ticks. It checks the
production schedule over small phase choices and optional request subsets. Byte
enumeration checks occupied backing, and explicit bad neighbors exercise traffic
overcommit, zero overflow, failure retention and equal-timestamp sweep starts. The
holder classes are checked against a containment replay built from Q22's primitives
rather than from its own helper; a new holder class is shown to refuse the calendar
until it is mapped and to lengthen the pass term once it is; and a drifted class map
refuses the whole receipt instead of re-deriving a calendar from it.
These are bounded independent checks, not formal verification.

What holder coverage still does not supply is the production side of the same
question. Admission owes the discovery of holders in a real binary: every root,
saved image, capability-bearing location and admitted derived base must be shown to
be represented in the supplied map, and this experiment reads that map rather than
building it. R2 owes the bounded graph traversal for a topology other than this
fixture's rooted star, so a class count taken over one proxy per non-root core is
not a bound for a general static graph. M4.4 owes the relation between a sanitized
saved image and the context-restore proof, which is what would let a `saved-context`
or `trusted-stack-root` class stand for a real saved partition rather than a fixture
holder. Until those land, a class is a kind of holder Q22a admits, not a kind of
holder a compiled service is known to have.

Q22's implementation owners still owe successful barrier realization, containment
scheduling and no-repopulation proofs. The workload owner
owes result equivalence, code and outbox sizing, admitted worst-case execution,
device ownership, power and tag/ECC traffic. A product comparison also needs the
real composed roster, all failure/restart arrivals, permanent and recovery charges,
and the target's qualified service rates. The research TODO therefore advances
with a joint scheduling experiment and negative results; its full acceptance
conditions remain open.
