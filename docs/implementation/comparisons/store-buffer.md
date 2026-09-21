# Store-buffer deletion comparison

Status: **open cost comparison**. This artifact evaluates Q22e against the
[architectural alternative](../../background/architectural-alternatives.md).
It does not select a new memory-ordering implementation or change the register.

## Baseline and candidate

The baseline retains the bounded store buffer and the current Ztso contract.
Its switch cost includes the class-padded `fence.t` drain exactly once, followed
by `vmclear` and any required OPP relock (R-15-218, R-15-220). Device accesses
use the separately ordered path in R-15-015b. Their endpoint latency is not a
hidden term in the SRAM buffer drain. Second-class stores also use an ordered
unbuffered path under that entry. Both paths owe qualified instruction service
and a bound on any operation still outstanding at timer expiry. The full
admitted boundary includes that complete residency prefix and context
restoration, beyond the three platform terms.

The candidate deletes the store buffer and uses an ordered path with bounded
pipeline drain. It owes preservation of the architectural ordering contract,
including load/store interactions, fences, exceptions and device accesses.
Phase service must account for the actual requests that can occur together,
their route and bank occupancy, refresh, and state carried between frames.
A grant rate averaged over a frame cannot establish immediate acceptance.

The arbitrary-stream zero-wait branch is closed for every second-class bank
because refresh reserves service, and for every island hosting multiple domains
because domain rotation interrupts service. A single-domain first-class island
still needs a proved occupancy bound or a checked arrival restriction. These
facts leave a cost comparison; they do not establish that deletion is cheaper.

## Deletion predicate and evidence boundary

Deletion requires all of the following clauses.

| Clause | Existing decision procedure | Remaining input or evidence |
| --- | --- | --- |
| Preserve the architectural ordering contract | n/a | Refinement from the proposed ordered path to the current ordering, fence, exception and device rules, plus the register and absence-contract amendments the alternatives entry's disposition lists: the memory-model and fence requirements, the buffer and flush dependencies, the ISA-profile rows and an explicit §11 service obligation |
| Represent every permitted joint arrival | `phase-schedule` resolves named banks, harts and operations into finite joint alternatives from digest-bound schedule and resource inputs | A sound extraction from the actual schedule, routes and instruction streams, including the RoT's independently serviced traffic |
| Accept each joint arrival in one legal transition, or charge its wait | The phase-service checker rejects unavailable injection, conflicting bank use and occupied destinations | Qualified per-slot injection and issue limits and all applicable arbitration resources; lockstep partners are not extra requesters |
| Carry resource state through frame wrap and close the reachable transition set | The checker explores phase, busy-bank and in-flight states from empty startup until closure; on a `phase-schedule-v2` declaration `phase-schedule` explores the product of declared modes, phases, occupancy and flights under the [mode-transition extension](../phase-service/mode-contract.md), each switch carrying boundary state unchanged | A justification that real startup and every permitted mode or schedule transition are covered by those initial states and declared transitions, and the actual instant, dwell and cost of a mode change |
| Respect ordered arrival along the path | The checker detects within-hart order inversion and path contention | A correspondence between the finite paths and the actual fabric; queues, backpressure and shared resources absent from the model require an extended model |
| Bound quiescent drain and switch saving | The optional completion analysis carries operations through bank occupancy and checks same-hart completion order; the cost evaluator distinguishes switch saving from net saving | The physical pipeline drain and bank completion bounds and their correspondence to modeled completion |
| Meet every deadline with the candidate's extra stalls | `phase-stall` bounds the candidate's issue waiting over declared per-hart programs and joins that bound to a declared `stalls` interval, and `phase-cost` checks supplied per-slot and frame cost intervals, including stalls, with the platform boundary and residency charged once per declared switch and the context term a caller-declared part of `other` that the reader cannot count | Whole-image WCET soundness and schedule analysis using qualified costs, including the padded boundary in admission duty |
| Establish a favorable implementation cost | `phase-cost` compares time, area and power intervals and budgets without substituting zero for missing operands | Measured or qualified area, service stalls, maintenance and switch operands, with stated uncertainty and workload coverage |

The synthetic checker is executable evidence about its finite contract. It is
not a proof that an arbitrary RTL implementation, arrival language, or physical
memory satisfies that contract. Declared mode transitions enter through the
mode-transition extension; a mode change's actual instant, dwell and cost, and
any field no instrument represents, remain outside a positive receipt.

## Reproducible phase contracts

Run `python tools/run.py phase-service --json` for the composition receipt.
Run an individual fixture with
`python tools/run.py phase-service --contract <path> --json`.
Paths below are relative to [phase-service/](../phase-service/).
Exit 0 means closure for the supplied model; exit 1 means refutation; exit 2
means an invalid or unreadable contract. Only `grants`, `arrivals`, `banks`,
`refresh` and `paths` are supported; unknown fields are refused, and declared
mode transitions are read by `phase-schedule` from a `phase-schedule-v2`
declaration, never by this reader. The receipt binds the composition's bytes
and, for a supplied contract, the exact bytes parsed, by SHA-256. A failing trace
reaches the earliest failing cycle; failures before that cycle's arrivals carry
only the accepted prefix. The behavioral suite reads every tracked fixture:
`python tools/run.py test --only phase_service`. A second module,
[test_phase_reference.py](../../../tools/tests/test_phase_reference.py), carries
an independent bounded-horizon reference written from the documented
conventions rather than from the checkers; it decides every tracked fixture and
named scenario on its own before comparing both checkers against it on a seeded
campaign of random contracts, and a deliberate one-convention perturbation of
the reference is asserted to surface as a disagreement:
`python tools/run.py test --only phase_reference`. The stalled exploration has
its own such reference,
[test_phase_stall_reference.py](../../../tools/tests/test_phase_stall_reference.py),
written from the stalled-transition contract's text: it compares every reported
bound with `phase-stall` over the program fixtures, the relation cases and a
seeded campaign of generated programs, and runs under
`python tools/run.py test --only phase_stall`.

| Refuted contract | Verdict | Closed companion contract |
| --- | --- | --- |
| `refuted/average-gap-grant-2-0.json` | `arrival-blocked`: a grant in another phase cannot accept this arrival | `closed/average-gap-even-grants.json` |
| `refuted/joint-two-harts-one-bank.json` | `arrival-blocked`: the simultaneous set exceeds one bank's service | `closed/joint-independent-banks.json` and `closed/joint-restricted-arrivals.json` |
| `refuted/frame-wrap-final-write.json` | `arrival-blocked`: final-phase occupancy survives frame wrap | `closed/frame-wrap-restricted.json` |
| `refuted/multi-frame-residue.json` | `arrival-blocked`: occupancy can survive multiple frames | `closed/frame-wrap-restricted.json` |
| `refuted/path-order-inversion.json` | `order-inverted`: unequal paths reorder a hart's requests | `closed/path-equal-length.json` |
| `refuted/second-class-refresh-slot.json` | `arrival-blocked`: refresh reserves the destination | `closed/second-class-refresh-restricted.json` |
| `refuted/shared-island-rotation.json` | `arrival-blocked`: the other domain's slot is unavailable | `closed/shared-island-restricted.json` |

The restricted companions prove only their explicitly restricted arrival
languages. They do not turn the arbitrary-stream zero-wait branch into a
positive result. Tests check the expected closure verdict, require a refusal
reason on each negative case and a drain bound on each positive case. An
opposite verdict or malformed fixture fails the suite.

## Executable prerequisite preparation

The [preparation contract](../phase-service/prerequisite-contract.md) fixes the scope
and acceptance of three host instruments, and the
[stalled-transition contract](../phase-service/stall-contract.md) adds a fourth:

- [Schedule extraction](../phase-service/schedule-input.md) resolves named joint
  arrivals against a separate resource declaration whose exact bytes the schedule
  binds. Its emitted contract can be passed directly to `phase-service`. The
  extractor preserves conflicting arrivals so the phase checker can refute them;
  a per-hart issue restriction is checked rather than assumed.
- [Completion analysis](../phase-service/completion-model.md), selected with
  `phase-service --completion` or `phase-schedule --completion`, checks same-hart
  completion order and drain through bank completion. `drain` measures in-flight
  time to bank acceptance; the completion result reports its own bound and status.
- [Stalled-transition bounds](../phase-service/stall-contract.md), `phase-stall`,
  expand declared per-hart programs into the contract and bound a waiting
  candidate's stalls, boundary residency, drain and cut tail under a maximal
  arbiter; `--costs` joins those bounds against the cost input's intervals.
- [Cost arithmetic](../phase-service/cost-input.md) binds a named workload to exact
  schedule bytes and compares baseline and candidate intervals. Favorable
  arithmetic requires conservative budget compliance and no regression in time,
  area or power, with a strict improvement in at least one. Overlap and tradeoffs
  remain inconclusive, and missing operands remain explicit.

The schema pages include runnable synthetic examples. Source hashes bind the
receipts to their inputs and implementations. These instruments do not extract
instruction traffic from binaries, prove an arbiter, measure a macro or establish
WCET. Their target comparison stays open independently of a synthetic verdict.

`python tools/run.py phase-evaluate SCHEDULE RESOURCES --costs COSTS --json`
joins the instruments for the declared zero-wait branch. The cost input must bind
the same schedule path, exact bytes and name. Its completion-drain interval must
cover at least the model's quiescent bound; a wholly smaller interval refutes the
join and an overlapping interval is inconclusive. The cost input's common clock
also applies to the phase contract's cycles. This is a declared unit convention,
not measured clock correspondence. The cost frame covers one serial admission
domain; the service period is not itself a task frame or a certificate of its
visit counts. A whole-image join across cores and modes remains owed.

Run the synthetic joined example with:

```console
python tools/run.py phase-evaluate docs/implementation/phase-service/schedule-examples/closed-companion.json docs/implementation/phase-service/schedule-examples/resources.json --costs docs/implementation/phase-service/schedule-examples/costs.json --json
```

The command returns 1 for a refuted branch, 2 for invalid or mismatched inputs,
and 0 for a completed analysis whose verdict may be favorable, inconclusive or
open; read `branch_verdict`, not the exit code alone. It always reports
`target_comparison: open` and lists the mode-transition budget in
`terms_not_carried` as a term the join does not carry; the two register acts
the [mode-transition extension](../phase-service/mode-contract.md) records,
R-11-018 fixing no exit instant of the source schedule for an edge and no entry
stating whether a mode change is a visit of R-11-009's partition-switch
boundary or whether the mode-transition budget enters this comparison, stay
owed to their owners. Refuting zero wait does not refute every deleting
candidate: a candidate that waits at issue is bounded by the
[stalled-transition contract](../phase-service/stall-contract.md) over declared
per-hart programs, and the arrival correspondence and WCET halves of that
analysis stay open. No successful cost comparison supplies either half.

## Cost operands and present verdict

The comparison starts from
`switch saving = n_switch * (fence_t - d_pipe)` and subtracts the candidate's
additional service stalls and other applicable execution costs. A positive
switch term alone cannot waive a deadline. R-11-009's admission duty includes
trap residency and the padded boundary; it is not merely the switch term.

The missing operands have explicit owners: actual slot positions in R-11-017;
`w_inj`, `w_issue` and `m_pipe` in R-15-108; bank mapping in R-15-228 and the
core roster in R-15-052b; qualified occupancies in R-15-247m; the concrete schedule's switch
count; and R-17-041's frozen timing evidence. The composition receipt reports
unqualified first-class memory, unqualified second-class memory, unqualified
timing, an absent schedule and unfrozen C/V/M/S/RoT inputs. Its synthetic cases
pass, while `target_comparison` remains `open`. Unknown operands stay unknown;
no numeric break-even or area saving is claimed here.

The [composition](../../../model/config/verifiedos.json) labels its memory and timing
figures as placeholders and explicitly states that the schedule is unauthored.
The [cyclic-executive proof](../../../proofs/CyclicExecutive.v) supplies symbolic
bounds and demonstration witnesses, not that emitted composition. The
[macro qualification protocol](../../hardware/macro-qualification-protocol.md)
supplies R5's measurement procedure, not qualified specimens or measurements.
Those artifacts cannot supply the missing operands by substituting their example
values. The [unassigned proof map](../../assurance/unassigned-proof-map.md) proposes
the arbiter/schedule and timing work at U-03, U-05, U-08 and U-09; these remain
proposals rather than available producers.

The current Sail executor cannot supply these measurements by running the
comparison workloads: [RAM access](../../../model/model/sys/mem.sail) is
synchronous, [fence.t](../../../model/model/extensions/platform/fence_t.sail) has no
modeled store buffer to drain, and the [timing annotations](../../../model/model/core/timing.sail)
do not execute memory-service cycles. U-03 needs a schedule and cycle-aware
execution connection before a functional run becomes arbiter evidence. A real
refresh schedule also needs a tractable interval or symbolic representation;
expanding each cycle of the declared bulk-memory refresh period into the host
checker's literal phase list is not an established target extraction.

Acceptance closure alone leaves completion and visibility unresolved. For
example, independent banks can accept one hart's long write followed by its short
write without waiting, while the later write's occupancy ends first. With zero
fabric latency the reported `drain` is zero even while a bank is busy. The
completion analysis detects that inversion and accounts for residual occupancy;
its finite model still supplies neither a visibility/refinement proof nor a
qualified physical quiescent bound.

## Second-class baseline and the timer boundary

The [boundary contract](../phase-service/boundary-contract.md) selects the unbuffered
baseline in R-15-015b and retains R-15-218's SRAM-only buffer bound. A second-class
store waits for prior buffered stores to enter the fabric, completes the bank's
atomic data/tag/ECC commit before retirement, and cannot be overtaken by a later
memory operation. R-15-015a still owns cross-path arrival and visibility order.
Keeping the existing SRAM FIFO avoids adding second-class refresh to every
buffer drain; it makes no claim that the complete boundary is cheaper. Qualified
instruction-service and residency bounds remain required.

R-07-040 derives residency H over complete reachable timer-to-handler prefixes.
These include an outstanding operation and any consequent synchronous fault
path, or the remainder of an already live kernel path. Service after timer expiry
must remain scheduled without borrowing a peer's grant. A missing finite bound
refuses admission. The boundary is H plus the platform and context switch costs;
R-11-009 charges it once per visit. Separately maximized WCET and boundary costs
may conservatively reserve unused capacity, but no second operation or handler
charge is appended to H for the same work. Successful paths are padded to the
same release instant; fatal faults retain fail-stop.

[BoundaryCost.v](../../../proofs/BoundaryCost.v) makes this arithmetic explicit:
each declared prefix adds its remaining operation and handler, H bounds their
finite case list, and the full boundary adds platform and context costs.
[CyclicExecutive.v](../../../proofs/CyclicExecutive.v)'s `slot_fits` consumes that
boundary and refuses an empty case list. Its slot theorem covers every declared
prefix; padding and component monotonicity are proved separately. The rung-change
cost consumes the full switch plus its table load, with residency kept in the
boundary. Refutations exercise omitted context, omitted residual operation and
the incorrect maximum of two sequential segments.

The declared-prefix arithmetic does not prove coverage of real executions.
The memory-service model, actual emitted schedule, qualified bounds and their
refinement still owe that connection. In particular, the candidate's total
operation drain cannot be counted both in its residency H and again as the
replacement fence term. Each side must state the timing boundary at which its
drain is measured and assign every remaining operation to one term.

## Acceptance predicate

The authorable Q22e comparison is acceptable when the refuted and closed
fixtures have reproducible verdicts, the three required
counterexamples remain load-bearing tests, each deletion clause names its
evidence and missing inputs, and the second-class baseline and its outstanding
qualification are explicit. This predicate accepts the synthetic comparison artifact only;
Q22e's checklist completion still requires a declared target workload and
schedule satisfying the full deletion predicate or yielding a reasoned refusal.
Missing coefficients leave Q22e open. Architecture adoption remains open until
the ordered-path proof, qualified
coefficients, whole-image WCET and favorable cost comparison all hold for the
selected target.
