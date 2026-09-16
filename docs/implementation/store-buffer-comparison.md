# Store-buffer deletion comparison

Status: **open cost comparison**. This artifact evaluates Q22e against the
[architectural alternative](../background/architectural-alternatives.md).
It does not select a new memory-ordering implementation or change the register.

## Baseline and candidate

The baseline retains the bounded store buffer and the current Ztso contract.
Its switch cost includes the class-padded `fence.t` drain exactly once, followed
by `vmclear` and any required OPP relock (R-15-218, R-15-220). Device accesses
use the separately ordered path in R-15-015b. Their endpoint latency is not a
hidden term in the SRAM buffer drain.

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
| Preserve the architectural ordering contract | n/a | Refinement from the proposed ordered path to the current ordering, fence, exception and device rules |
| Represent every permitted joint arrival | Finite joint arrival alternatives are enumerated | A sound extraction from the actual schedule, routes and instruction streams, including the RoT's independently serviced traffic |
| Accept each joint arrival in one legal transition, or charge its wait | The phase-service checker rejects unavailable injection, conflicting bank use and occupied destinations | Qualified per-slot injection and issue limits and all applicable arbitration resources; lockstep partners are not extra requesters |
| Carry resource state through frame wrap and close the reachable transition set | The checker explores phase, busy-bank and in-flight states from empty startup until closure | A justification that real startup and every permitted mode or schedule transition are covered by those initial states and transitions |
| Respect ordered arrival along the path | The checker detects within-hart order inversion and path contention | A correspondence between the finite paths and the actual fabric; queues, backpressure and shared resources absent from the model require an extended model |
| Bound quiescent drain and switch saving | The checker reports longest in-flight time until bank acceptance | The physical pipeline drain and bank completion bounds; the reported bound excludes completion of bank occupancy |
| Meet every deadline with the candidate's extra stalls | n/a | Whole-image WCET and schedule analysis using qualified costs, including trap residency and the padded boundary in admission duty |
| Establish a favorable implementation cost | n/a | Measured or qualified area, service stalls, maintenance and switch operands, with stated uncertainty and workload coverage |

The synthetic checker is executable evidence about its finite contract. It is
not a proof that an arbitrary RTL implementation, arrival language, or physical
memory satisfies that contract. Unsupported modes must remain outside a
positive receipt until their transitions and resources are represented.

## Reproducible phase contracts

Run `python tools/run.py phase-service --json` for the composition receipt.
Run an individual fixture with
`python tools/run.py phase-service --contract <path> --json`.
Paths below are relative to [phase-service/](phase-service/).
Exit 0 means closure for the supplied model; exit 1 means refutation; exit 2
means an invalid or unreadable contract. Only `grants`, `arrivals`, `banks`,
`refresh` and `paths` are supported; unknown fields are refused, including mode
transitions the model cannot check. The receipt binds the composition's bytes
and, for a supplied contract, the exact bytes parsed, by SHA-256. A failing trace
reaches the earliest failing cycle; failures before that cycle's arrivals carry
only the accepted prefix. The behavioral suite reads every tracked fixture:
`python tools/run.py test --only phase_service`.

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

## Cost operands and present verdict

The comparison starts from
`switch saving = n_switch * (fence_t - d_pipe)` and subtracts the candidate's
additional service stalls and other applicable execution costs. A positive
switch term alone cannot waive a deadline. R-11-009's admission duty includes
trap residency and the padded boundary; it is not merely the switch term.

The missing operands have explicit owners: actual slot positions in R-11-017;
`w_inj`, `w_issue` and `m_pipe` in R-15-108; bank mapping and roster in
R-15-228; qualified occupancies in R-15-247m; the concrete schedule's switch
count; and R-17-041's frozen timing evidence. The composition receipt reports
unqualified first-class memory, unqualified second-class memory, unqualified
timing, an absent schedule and unfrozen C/V/M/S/RoT inputs. Its synthetic cases
pass, while `target_comparison` remains `open`. Unknown operands stay unknown;
no numeric break-even or area saving is claimed here.

The [composition](../../model/config/verifiedos.json) labels its memory and timing
figures as placeholders and explicitly states that the schedule is unauthored.
The [cyclic-executive proof](../../proofs/CyclicExecutive.v) supplies symbolic
bounds and demonstration witnesses, not that emitted composition. The
[macro qualification protocol](../hardware/macro-qualification-protocol.md)
supplies R5's measurement procedure, not qualified specimens or measurements.
Those artifacts cannot supply the missing operands by substituting their example
values. The [unassigned proof map](../assurance/unassigned-proof-map.md) proposes
the arbiter/schedule and timing work at U-03, U-05, U-08 and U-09; these remain
proposals rather than available producers.

Even a closed finite contract leaves completion and visibility unresolved. For
example, independent banks can accept one hart's long write followed by its short
write without waiting, while the later write's occupancy ends first. With zero
fabric latency the reported `drain` is zero even while a bank is busy. The
behavioral suite preserves this scope distinction: neither result supplies an
ordering proof or the physical quiescent bound needed by the cost comparison.

## Joint register act needed for second-class stores

R-15-015b admits only SRAM stores to the buffer, while R-15-218 justifies the
padded drain using SRAM service. Second-class memory is not resolved by calling
it a device. Before including second-class stores, choose and co-read one of
these joint amendments. The following text is a proposal, not an adopted
requirement.

| Arm | Proposed addition to R-15-015b | Proposed addition to R-15-218 |
| --- | --- | --- |
| Buffered second-class stores | Second-class stores may enter the bounded store buffer only when admission supplies a qualified bound for completion through every permitted refresh phase and fabric state; otherwise they are refused. Device stores remain excluded. | The class-padded drain includes the worst permitted refresh wait, routing and bank completion for every buffered second-class store at the declared maximum depth. Missing qualification or an unbounded phase causes admission refusal. The pad does not complete early. |
| Unbuffered second-class stores | Second-class stores use an explicitly ordered unbuffered path after prior buffered stores have drained, with instruction service charged against a qualified bound covering refresh, routing and bank completion. Device ordering remains separately applicable. | The store-buffer drain remains SRAM-only. Outstanding unbuffered second-class operations must reach the defined quiescent boundary before the switch, with their worst-case cost charged explicitly and exactly once; the switch pad may not assume they have already completed. Missing bounds cause admission refusal. |

Each arm also needs its corresponding specification text, timing inputs,
admission evidence and coverage review. Selecting an arm here would conceal a
normative decision; neither is included in the present baseline cost.

## Acceptance predicate

The authorable Q22e comparison is acceptable when the refuted and closed
fixtures have reproducible verdicts, the three required
counterexamples remain load-bearing tests, each deletion clause names its
evidence and missing inputs, and the second-class baseline dependency is
explicit. This predicate accepts the synthetic comparison artifact only;
Q22e's checklist completion still requires a declared target workload and
schedule satisfying the full deletion predicate or yielding a reasoned refusal.
Missing coefficients leave Q22e open. Architecture adoption remains open until
the ordered-path proof, joint register act where applicable, qualified
coefficients, whole-image WCET and favorable cost comparison all hold for the
selected target.
