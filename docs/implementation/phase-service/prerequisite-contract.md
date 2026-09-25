# Executable preparation for the Q22e comparison

This contract owns the bounded host preparation for the open
[store-buffer comparison](../comparisons/store-buffer.md). It does not commission
silicon characterization or implement the U-03 arbiter, U-05 admission emitter,
U-08 timing projection or U-09 RTL measurement rig. Their target correspondence
and qualification remain required. The work below makes their eventual outputs
usable and rejects errors which would otherwise survive an arithmetic comparison.

## Completion and quiescence

Keep the existing acceptance-only phase predicate compatible. Add a separate
completion analysis over the same finite contract, tracking issued operations
through bank occupancy as well as fabric transit. For each hart, an operation
issued later must not complete before an earlier operation; equal-cycle
completion is permitted. Explore reachable state across every frame wrap, with
the original joint arrival alternatives and refresh reservations intact. Report
a counterexample for completion inversion even when acceptance order closes.

Report the maximum cycles from any reachable cycle boundary until every issued
operation has completed after stopping new arrivals. Count residual bank
occupancy and fabric transit, including their off-by-one convention. Continue
scheduled refresh while draining; do not count perpetual future maintenance as
an issued operation to drain. Distinguish a blocked drain from a finite bound.
This is a bound in the declared model, not a physical switch or visibility proof.
Do not replace the old acceptance drain with the new bound silently.

Acceptance requires regression cases for a long first write and shorter later
write to independent banks, equal completions, independent harts, occupied banks
with no request in flight, fabric plus bank drain, refresh, and frame wrap.
Retain the three load-bearing Q22e counterexamples and the existing CLI behavior.

## Schedule and resource extraction

Add a host command which maps an explicitly enumerated, single periodic schedule
and joint traffic alternatives into the existing phase contract. Give banks,
harts and operation classes stable names; resolve each request through its bank
and operation occupancy from a separate resource declaration. Check per-hart
issue limits and aggregate phase injection, including simultaneous requests.
Preserve every declared alternative and its order. Refuse a violated per-hart
issue restriction as an inconsistent input; preserve traffic exceeding aggregate
grants so the phase predicate can refute it. Never delete an alternative or
combine individually legal requests in place of the declared joint alternatives.
Represent refresh and paths without losing frame-wrap state.

Read resource bytes once and check their expected SHA-256 from the schedule.
Bind both source byte identities and the generated contract in the receipt.
Unknown fields, duplicate JSON keys or names, missing references, invalid numbers,
unsupported modes or transitions, and malformed or stale resources are errors.
No boolean supplied by a caller can promote this extraction into qualification.
An emitted finite contract remains declared-input evidence; mapping from the
actual instruction streams, arbiter and all initial/mode states remains open.

The non-normative [schedule-synthesis handoff](../contracts/schedule-record.md#research-handoff-for-schedule-synthesis)
connects pinwheel and transfer-coloring results to that missing correspondence.
Their endpoint or unit-service abstractions must be compared with the full joint
traffic and completion model here. A colored transfer set that still collides at
a routed resource or retains bank occupancy is a useful rejected candidate; a
combinatorial schedule alone does not establish the extraction's target premises.

Acceptance requires a checked extraction which reproduces the grant-gap,
same-bank joint and final-cycle occupancy refutations, a closed companion,
per-hart over-issue refusal, resource-hash mismatch, missing names and unsupported
mode refusal. Publish the exact input schema and runnable synthetic examples.

## Workload and implementation cost arithmetic

Add a host command for a named workload and schedule identity with baseline and
candidate inputs. Use non-negative integer intervals and exact conservative
arithmetic, with explicit units and a common clock domain for cycle comparisons.
Missing operands stay unknown. Bind the schedule bytes by an expected SHA-256;
bind the comparison's own bytes in the receipt. Refuse malformed input, duplicate
keys and identifiers, stale identities and ambiguous units.

For each declared slot, account for execution, service stalls, trap residency
and other costs, plus the boundary cost exactly once per declared switch. The
baseline boundary contains `fence_t`; the candidate contains the completion-aware
pipeline drain. Both retain `vmclear` and any OPP relock. Compare the resulting
intervals with the slot deadline and frame budget. Report the switch-saving
interval separately from net execution saving so a positive switch term cannot
conceal a deadline miss. Compare area and power intervals and declared budgets
without treating absent values as zero or exchanging a power violation for time.

A conservative favorable arithmetic result requires all declared candidate
budgets met and no regression in time, area or power, with a strict improvement
in at least one. Overlapping intervals or tradeoffs are inconclusive; a definite
budget violation is a refusal. Unknown mandatory operands keep the result open.
These are scoped arithmetic verdicts, never Q22e completion: workload completeness,
WCET soundness, qualification, ordering refinement and physical correspondence
are separate evidence, even when every number is supplied.

Acceptance requires cases for a favorable comparison, a switch saving defeated
by stalls, a missed deadline, interval overlap, unknown operands, area and power
budget violations, duplicate identities, stale schedule bytes and once-only
boundary accounting. Publish the exact schema and synthetic examples.

## Integration acceptance

An orchestration command joins the three instruments against the same exact
schedule bytes, name and resource declaration. It checks that the cost input's
schedule path, hash and identity match the extracted schedule, and that the
candidate's declared completion-drain interval is no smaller than the finite
completion bound. A missing bound remains open; an acceptance or completion
refutation is not turned into a positive result by favorable arithmetic. The
zero-wait orchestration branch cannot price a waiting candidate: such a case is
bounded by `phase-stall` under [the stalled-transition contract](stall-contract.md),
whose arrival analysis stays open. Its verdict
therefore names this narrower scope and leaves the target comparison open.
Tests exercise a complete synthetic join, a stale or mismatched schedule, an
understated drain and an arithmetic success with a service refutation.

Each instrument has focused behavioral tests through `tools/run.py`. The
integrator registers commands, updates the comparison and tool guide, reviews
source receipts and runs `python tools/run.py --check --tests` on the settled
tree. Synthetic examples must remain visibly synthetic. This preparation leaves
Q22e and the physical and proof prerequisites open.
