# Constant signed floor division

## Scope and ownership

[Ben Joffe's algorithm](https://www.benjoffe.com/fast-floordiv) supplies
constant-divisor signed floor division by choosing a reciprocal multiplier,
a shift and a sign-dependent correction. The integration is developer tooling:
a parameter planner, exact evaluator and branch-free RV64 assembly candidate.
[M1.3](../../../PLAN.md#m1-toolchain-spine-incl-the-cheri-compcert-prerequisite)
owns eventual compiler adoption. No existing target floor-division caller has
been identified, and the reference does not complete that compiler item.

The selected reference is `benjoffe/fastdiv` revision
`608fda7a6ea7322a55b9fb848be5ab252a341194`, whose
[algorithm](https://github.com/benjoffe/fastdiv/blob/608fda7a6ea7322a55b9fb848be5ab252a341194/algorithms/benjoffe.hpp)
and [MIT license](https://github.com/benjoffe/fastdiv/blob/608fda7a6ea7322a55b9fb848be5ab252a341194/LICENSE)
were read on 2026-10-30. The adapted planner retains those terms;
[THIRD-PARTY.md](../../../THIRD-PARTY.md#constant-floor-division-reference)
owns incorporation and distribution details.

This transform applies only to a source operation explicitly specifying floor
division, or one whose nonnegative range proof makes flooring and truncation
equal. C signed division and RV64 `div`/`divw` continue to truncate toward zero,
including their existing exceptional behavior. Python's unbounded integer
division remains the independent oracle, not a target optimization consumer.

## Arithmetic contract

Widths are 8, 16, 32 and 64 bits. A divisor is a nonzero signed value at the
selected width, known before evaluating any dividend. Each dividend lies in
that width's signed range. The result is the mathematical `floor(x / d)`.
Zero divisors, unsupported widths and out-of-range inputs are refused.
`INT_MIN / -1` is refused as overflow; no wrapped result is accepted.

Positive powers of two use arithmetic right shift. Negative powers of two
use an exact widened identity, or quotient plus a nonzero-low-bits correction,
without negating `INT_MIN` at its original width. The most negative divisor
is included. Modulus is outside the first interface; deriving it later as
`x - q*d` needs widening or a separately justified modular calculation.

For other divisors, search shifts from the word width through twice the width
minus one for upward and downward reciprocal rounding. A multiplier must fit
in the signed word; sign selection must leave both chosen multipliers in
range. Use the article's strict worst-case inequalities, including its
`INT_MIN` endpoint qualification, before selecting a candidate. Sampled
agreement alone cannot qualify parameters. If neither direction qualifies,
report a failure rather than emit an unchecked fallback.

The execution variants are sign-selected multiplier, rounded-up multiplier
with a dividend correction, and rounded-down multiplier with a saturating
dividend correction. Both divisor signs are supported. Planner choice is
deterministic and independent of the host architecture. Prefer a word-sized
shift when available, then sign selection when both directions qualify;
this is a candidate-selection policy, not a claim about target speed.
The evaluator uses an exact double-width product and arithmetic right shift.
Parameter records are validated before evaluation or emission, including
records constructed or modified by callers.

## Developer interface and target candidate

`python tools/run.py floor-div --width W --divisor D` prints the selected
parameters as JSON. Repeat `--value X` to evaluate checked inputs.

```console
python tools/run.py floor-div --width 64 --divisor 86400 --value -1 --value -86400
python tools/run.py floor-div --width 64 --divisor 86400 --assembly
```

The Python interface is `vos.floordiv.plan(width, divisor)`, followed by
`evaluate(parameters, value)` or `assembly(parameters)`. Its immutable `Plan`
records are checked against the canonical qualified selection on consumption.

`--assembly` emits a straight-line RV64 fragment only at width 64. Its input
and result are signed integers in `x10`; scratch registers `x5`, `x6` and `x7`
are clobbered. The caller reserves those registers as integer temporaries;
integer writes also destroy any capability tags they previously held in the
merged register file. The fragment accesses no memory and uses no capability,
stack or control-transfer instruction. Constant materialization uses the
existing assembler's `li` expansion.
Nontrivial variants use signed `mulh` and an arithmetic shift of its result.
Comparisons produce integer bits; no dividend-dependent branch or lookup is
permitted. Register and instruction choices are fixed by the divisor.

The assembly interface refuses divisor `-1`: its unrepresentable dividend
needs a caller-level checked failure contract, which this fragment cannot
provide. The evaluator still supports all representable inputs for that
divisor. Other negative powers of two use the correction above.
Emission is an experimental arithmetic fragment, not an admitted function,
compiler pass, source-to-byte proof or target constant-time verdict.

## Acceptance predicate

The reference is accepted when all of these checks hold:

- Generated comparisons exhaust every signed dividend and nonzero divisor at
  width 8, distinguishing the single overflow case from arithmetic results.
- Wider generated cases cover both signed extrema, zero, units, exact multiples
  and their neighbors near the extrema and origin, every signed power of two
  and its neighbors, positive and negative non-power divisors, and deterministic
  pseudorandom cases. Expected values come directly from exact integer division.
  Finite wider campaigns are reported as samples, never universal proofs.
- Every nontrivial variant is exercised. Controls corrupt a multiplier, shift
  and variant/correction and demonstrate refusal or a wrong-result witness.
  Zero, out-of-range inputs and overflow are tested through the public interface.
- Generated RV64 fragments assemble through the repository assembler. A bounded
  independent instruction interpreter checks the emitted arithmetic, including
  signed high multiplication, constant expansion and negative powers of two,
  against the exact oracle. It refuses unknown instructions. This host check
  establishes arithmetic in that interpreter, not Sail execution or timing.
- The CLI exposes these scopes and refusals, and its tests are discovered by
  the ordinary hosted behavioral gate. Host CI passes on Windows and Ubuntu
  for the settled revision; every Guest CI lane is dispatched at that revision
  without waiting for its result.

Local feedback is limited to focused host tests, typing and import preparation.
Complete suites, proof gates and benchmarks remain hosted.

## Compiler adoption predicate

M1.3 selects a real source floor-division operation and proves the transform
over its declared word semantics before compiler integration. It preserves
overflow/refusal behavior and discharges parameter correctness, source
correspondence, final-byte admission, secret-flow and resource obligations
through the existing route. Checked failures must be compatible with that
caller's public-input policy; a secret-dependent exception cannot be hidden
by branch-free arithmetic.

Compare complete linked sequences, including constant materialization,
live ranges, spills and any required erasure, with the existing lowering's
encoded size and worst-case cycles on each relevant core class. A register-sized
host result or the article's ARM/x86 measurements supplies no RV64 saving.
No new instruction or divider implementation is required by this reference.
