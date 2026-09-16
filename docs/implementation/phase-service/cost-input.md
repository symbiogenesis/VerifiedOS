# Declared workload cost arithmetic

`python tools/run.py phase-cost --input FILE --json` evaluates the arithmetic
portion of the [Q22e prerequisite contract](prerequisite-contract.md). It binds a
named workload to exact schedule bytes and compares declared baseline and candidate
costs. `target_comparison` is always `open`. Supplied numbers do not establish
workload completeness, WCET soundness, qualified measurements, ordering refinement
or correspondence to the implemented machine.

Each input covers **one serialized admission domain** at one common clock. Its
slots execute sequentially, so their cost sum is meaningful against its frame
budget. Parallel cores must not be placed in this slot list and summed as elapsed
frame time. Joining domains, confirming whole-image coverage and checking the
actual emitted schedule remain external obligations. The schedule is opaque to
this reader: a matching digest establishes identity, not admission validity.

## Exact input schema

The reader accepts strict JSON without comments, trailing commas, duplicate keys,
non-finite numbers or unknown fields, at every object level. Version is integer
`1`. Integer operands exclude booleans and floats. Identifiers are nonempty strings
without leading or trailing whitespace; slot identifiers are unique. The input
requires exactly the top-level fields below. Each object requires the stated
fields except numeric cost and budget operands: an omitted operand and `null`
both mean unknown. An explicit `[0, 0]` states a zero cost.

An interval is `[lower, upper]`, with non-negative integer endpoints and
`lower <= upper`, or `null`. All intervals denote bounds on the same workload,
scope, operating condition and accounting period. The caller must establish those
conditions; the arithmetic reader cannot qualify them.

| Field | Shape and meaning |
| --- | --- |
| `version` | `1` |
| `workload` | Workload identifier |
| `domain` | Object with `id` and `kind`; `kind` must be `"serial"` |
| `schedule` | Object with `id`, `path`, `sha256`; the path is relative to the input's directory unless absolute, and the digest is 64 lowercase hexadecimal characters |
| `clock` | Object with `id` and positive integer `hz`; all time operands already use cycles of this clock |
| `units` | Exactly `{"time":"cycles","area":"um2","power":"uW"}` |
| `slots` | Nonempty list of slot objects defined below |
| `boundary` | Object with interval operands `fence_t`, `d_pipe_completion`, `vmclear`, `opp_relock` |
| `budgets` | Object with interval operands `frame`, `area`, `power`, in the corresponding units |
| `area` | Object with interval operands `baseline`, `candidate`, covering the same declared implementation scope |
| `power` | Object with interval operands `baseline`, `candidate`, covering the same declared operating condition and averaging window |

Each slot has structural fields `id`, `switches`, `baseline`, `candidate`, and
the interval operand `deadline`. `switches` is a non-negative integer. The deadline
is the available duration for this slot, not an absolute timestamp. Both cost
objects accept exactly the interval operands `execution`, `stalls`,
`trap_per_switch`, and `other`. The first two are per-slot execution excluding the
separately reported costs, and service stall cycles. `other` is the total per-slot
remainder, including scalar context-save cost and any reservations or idle periods
that consume the declared budget. `trap_per_switch` is trap residency per boundary
visit, multiplied by `switches`. Every boundary visit must be included in that
count. Trap residency excludes the separately charged fence/drain, clear and
relock costs; the categories must not overlap.

The baseline boundary is `fence_t + vmclear + opp_relock`; the candidate boundary
is `d_pipe_completion + vmclear + opp_relock`. `d_pipe_completion` must bound
completion-aware pipeline and bank quiescence, not merely fabric acceptance.
This tool accepts the declared interval and does not prove that bound. Scalar
context save is included in `other` exactly as many times as the workload uses
it. All OPP effects must be converted conservatively to the named common clock
before entry, retaining relock cost. There is no implicit conversion or frequency
scaling, and fields that attempt to add another clock or mode are rejected.

## Arithmetic and verdicts

For each side, the slot cost is
`execution + stalls + other + switches * (trap_per_switch + boundary)`.
The frame cost is the sum of the slot costs. An interval sum adds endpoints;
baseline-minus-candidate is
`[baseline.lower - candidate.upper, baseline.upper - candidate.lower]`.
Integers have no fixed machine-width truncation. Unknown operands propagate;
zero times unknown contributes zero to a subtotal, but the missing operand remains
listed and prevents a favorable verdict.

The receipt reports the switch saving
`switches * (fence_t - d_pipe_completion)` separately from net saving. Shared
`vmclear` and `opp_relock` denote the same quantities on both sides and cancel in
the saving; their bounds remain in both total costs and budget comparisons. Other
baseline and candidate intervals are treated independently, even when their
endpoints happen to coincide. No favorable correlation is assumed.

A budget is `met` only when the cost's upper bound is at most the budget's lower
bound. It is `violated` only when cost's lower bound exceeds budget's upper bound.
Otherwise it is `uncertain`; absent operands produce `unknown`. Both baseline and
candidate budget statuses are always reported. Time comparison covers every slot
and the aggregate frame, so a slowdown in one slot is a tradeoff even when another
slot saves more. Area and power are independently compared with their baseline
and budget. They cannot compensate for a missed deadline.

The scoped arithmetic verdict has this precedence:

1. `refuted`: any known candidate slot, frame, area or power budget is definitely
   violated, including when another mandatory operand is unknown.
2. `open`: any mandatory numeric operand is unknown, with no definite candidate
   budget violation.
3. `inconclusive`: either side's feasibility is uncertain or the baseline violates
   a budget; or the comparison has interval overlap, regression, a tradeoff or no
   strict improvement. Baseline infeasibility cannot be hidden by candidate saving.
4. `favorable`: all budgets are met on both sides; every slot, the frame, area and
   power conservatively avoid regression; at least one has a strictly positive
   saving lower bound.

Exit status is `2` for malformed or unreadable input or a stale schedule digest,
`1` for `refuted`, and `0` for any other valid arithmetic verdict. Exit `0` therefore
does not imply a favorable comparison. Read `result.arithmetic_verdict`.
The receipt hashes the exact input bytes, exact schedule bytes and source files.
The schedule bytes are read once and hashed before arithmetic is reported.

## Runnable synthetic examples

All files in [cost-examples](cost-examples/) contain invented arithmetic operands.
Their [schedule](cost-examples/schedule.json) is only an identity fixture and is
not an admission emitter's output. Run, from the repository root:

```text
python tools/run.py phase-cost --input docs/implementation/phase-service/cost-examples/favorable.json --json
python tools/run.py phase-cost --input docs/implementation/phase-service/cost-examples/switch-stalls.json --json
python tools/run.py phase-cost --input docs/implementation/phase-service/cost-examples/deadline.json --json
python tools/run.py test --only phase_cost
```

The [favorable input](cost-examples/favorable.json) charges two boundary visits and
shows a scoped saving. [Extra stalls](cost-examples/switch-stalls.json) defeat that
switch saving; a [deadline miss](cost-examples/deadline.json),
[area-budget violation](cost-examples/area-budget.json) or
[power-budget violation](cost-examples/power-budget.json) refutes the candidate.
[Overlapping bounds](cost-examples/overlap.json) are inconclusive, an
[unknown execution operand](cost-examples/unknown.json) remains open, and an
[infeasible baseline](cost-examples/baseline-infeasible.json) prevents a favorable
comparison. Behavioral tests also exercise duplicate identifiers and keys,
stale schedule bytes, exact boundary accounting, large integers, and conservative
budget endpoints.
