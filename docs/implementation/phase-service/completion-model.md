# Finite completion and quiescence model

The [preparation contract](prerequisite-contract.md) calls for completion-aware
evidence in addition to the existing acceptance-only predicate. Run both on the
same declared contract with:

```console
python tools/run.py phase-service --contract docs/implementation/phase-service/closed/path-equal-length.json --completion --json
```

The existing `result` object is unchanged. The additional `completion` object
comes from [phase_completion.py](../../../../tools/vos/phase_completion.py).
Without `--completion`, command behavior remains acceptance-only. Completion
requires `--contract`; the fixed default regression assessment remains unchanged.
The command exits zero only when both requested analyses close, one on a
refutation, and two on malformed input. Raw contract, checker, test and
configuration byte identities are included in the receipt.

## Cycle and ordering conventions

Each state is the boundary before a cycle's refresh and new arrivals. It retains
every issued operation in issue order, with its bank, hart, remaining fabric
transit and remaining occupancy, plus each bank's maintenance occupancy.
Refresh reserves its bank first. Requests completing transit accept next, and
the current phase's joint batch issues last. The same bank cannot accept two
operations in one cycle. The fabric and bank never create a queue.

An operation accepted in cycle `t` with occupancy `n` occupies cycles `t` through
`t+n-1`, completing at that last cycle's end. Occupancy one therefore leaves no
residue at the next boundary. A fabric path `p` accepts an operation issued in
cycle `t` in cycle `t+p`. At the boundary immediately after issue its remaining
time to completion is `p+n-1`. Both terms include the same acceptance cycle;
adding another cycle would count it twice.

Batch order defines issue order within a cycle. For each hart, a later operation
may complete in the same cycle as an earlier operation, but never before it.
Different harts have no relative completion-order obligation. The exploration
retains operation residue across every frame wrap and takes every explicit joint
alternative, merging only identical states. Completion removes an operation;
its former place in the sequence cannot affect later completion ordering.

For example, an occupancy-three operation issued in cycle zero to bank zero and
an occupancy-one operation of the same hart issued in cycle one to bank one
both accept immediately, yet complete in cycles two and one respectively. A
three-cycle frame containing those two issues followed by silence closes the
acceptance predicate and refutes completion order. Equal completion cycles and
independent-hart versions are checked companions in the
[behavioral tests](../../../../tools/tests/test_phase_completion.py).

## Drain and reported scope

At each reachable boundary the checker stops all new arrivals and replays the
remaining operations to completion. This includes occupied banks with no request
in flight. Stopping arrivals is permitted for this analysis even when empty is
not one of the workload's listed alternatives. Scheduled refresh continues with
its original phase and occupancy; it cannot preempt an operation or hide a fabric
collision. Refresh itself is maintenance, not an issued workload operation, so
perpetual future refresh does not make the drain infinite.

`quiescent_drain` is the maximum cycle count over all reachable boundaries only
when the whole exploration closes. `drain_status` is `finite` for that result,
`blocked` when continuing refresh or a bank collision prevents the no-queue
drain, and `not-evaluated` for another refutation. A blocked result identifies
the source boundary, its admitted `trace`, the `drain_failure` boundary reached
after `drain_cycles` empty-arrival cycles, and the reason. No partial exploration
reports its observed maximum as a universal bound. The exploration visits
boundaries in cycle order and drains each before taking its arrivals, so the
reported failure is the earliest source boundary whose drain blocks, and a
blocked drain from an earlier boundary outranks a step failure at a later cycle.

`ordered` is true only on closure, false for a completion-order inversion, and
null when an acceptance or drain failure prevents the completion conclusion.
The ordinary `result.drain` still measures fabric transit only. Consumers must
select `completion.quiescent_drain` explicitly for total issued-operation drain.

This is finite declared-input evidence. Operation completion here means the end
of declared bank occupancy; it establishes neither architectural visibility nor
a physical partition-switch bound. The initial state is empty at phase zero;
all admitted boot, mode-transition and initial states, actual arbiter behavior,
qualified occupancy and refresh measurements, and the ordering refinement still
need their separate evidence. Q22e remains open.
