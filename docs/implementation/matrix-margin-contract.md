# M-class sustained GEMM comparison

This is M0.8c's measurement contract for R-15-116 and R-15-116a in the
[requirements register](../requirements-register.md), which takes precedence.
It prepares the instruction decision at R-15-014a (ix). The implemented
[scratchpad](../../model/model/unit_tests/test_matrix_scratchpad.sail) remains
the starting point; no matrix instruction or opcode is admitted by this contract.

## Measurement and denominator

Before collecting results, review and commit a campaign plan fixing the dense
int8 and bf16 GEMM cases, input bytes, dimensions, layouts, repetitions,
accumulation and rounding rules, and the reference output for each case.
Select the cases from the composed inference workload, including tile tails;
small, irregular and low-reuse controls remain RVV workloads under R-15-116.
Record their selection rationale. Fixtures and peak-MAC arithmetic cannot
replace the campaign's generated kernels and sustained measurements.

Both arms compute the same result from the same inputs on the M class's
VLEN=1024 configuration. The denominator is the strongest admitted RVV
expression, including R-15-067l's dot products if ratified and admitted at the
measurement date. Record the complete tested extension set, specification
revisions and status evidence, backend flags, and the comparison of applicable
RVV kernels. Equality of extension lists is necessary but cannot prove the
chosen kernel is the strongest one. That remains an attended review.

Bind the backend, composed image, memory plan, bank grants, scratchpad range,
matrix geometry, clock and energy model, and source revisions into the plan's
configuration identity. Retain both generated kernels and producer receipts.
An unadmitted matrix candidate may be evaluated off-model; its cost model is
untrusted evidence and installs no provisional opcode in Sail. Record the
candidate's state, memory, restart, arithmetic and rounding inventory, and the
AME, IME and VME comparison R-15-009 requires before selecting a surface.

Time the complete repeated GEMM, including operand movement, setup, tails and
drain, in common target-time ticks. Include energy over the same scope in common
energy quanta. State calibration, uncertainty and provenance for both units;
host emulator wall time and ideal array peaks are inadmissible. Report
de-quantization and block-scale application separately as the in-slot software
cost R-15-117 and R-15-117a require; retain the complete inference-path cost too.
Do not charge different work to the two GEMM arms or hide it in warm-up.

## Review representation

The planned host checker consumes two strict JSON files. Unknown or duplicate
keys, floats, booleans in integer fields, empty sets and duplicate members are
refused. Digests are full lowercase SHA-256 identities of retained artifacts.
They bind supplied bytes by identity; the checker does not authenticate receipts,
reproduce artifacts, or verify the producer's measurements.

The plan has exactly `schema` (`matrix-margin-plan-v1`), `configuration_sha256`,
`protocol_sha256`, `rvv_extensions`, and `cases`. The protocol digest identifies
the reviewed campaign material described above, including unit definitions and
the denominator review. `rvv_extensions` is a nonempty array of nonempty names.
Each case has exactly `id`, `dtype` (`int8` or `bf16`), `workload_sha256`, and
`output_sha256`. IDs are unique; both data types must have cases. The workload
digest binds input bytes, shape, layout, arithmetic and repetition count; the
output digest binds the independent reference result, using a protocol-fixed
canonical representation for bf16 outputs.

The report has exactly `schema` (`matrix-margin-report-v1`), `plan_sha256`,
`configuration_sha256`, `rvv_extensions`, and `cases`. `plan_sha256` hashes the
original plan file bytes, including whitespace. The configuration and extension
set must match the independently supplied plan. Each case has exactly `id`,
`workload_sha256`, `rvv`, and `matrix`. Each arm has exactly `ticks`,
`energy_quanta`, `output_sha256`, and `receipt_sha256`. Counts are positive
unsigned 64-bit integers. Receipt identities must differ between arms. Both
outputs must match the plan's reference output. The case sets must agree exactly;
a missing slow case cannot improve an aggregate.

## Acceptance of the instrument

For equal work, throughput margin is `rvv.ticks / matrix.ticks`; throughput per
watt margin is `rvv.energy_quanta / matrix.energy_quanta`. Evaluate these as
exact rational numbers. Publish both ratios for every case, including failures;
do not average a failing case away.

R-15-116 says approximately 8 to 10 times, without choosing an exact cutoff.
The checker therefore reports `below-band` for any throughput ratio below 8,
`review-band` when none is below 8 but some are below 10, and `clears-band`
when all are at least 10. It separately requires the energy margin to exceed
the throughput margin for every case, matching the wider per-watt requirement.
It chooses no cutoff inside the band. A weak energy margin is reported even
when throughput clears. A valid comparison returns success regardless of which
band it finds; malformed or mismatched evidence is a finding.

The instrument is accepted when generated ratio-boundary cases, altered
bindings, weaker extension sets, missing and duplicate cases, bad numeric types,
incorrect outputs and truncated JSON demonstrate these decisions. An ordinary
host gate and focused behavioral tests hold the implementation. Fixture results
establish only the instrument's behavior.

M0.8c remains open until the real campaign and attended review decide the margin.
A passing decision admits the instruction surface through the existing profile
gate before Sail implementation, capability checks and guest evidence. A failing
decision applies the register's deletion arm and updates its affected consumers.
An incomplete report or an unresolved cutoff authorizes neither outcome.
