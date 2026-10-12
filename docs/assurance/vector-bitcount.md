# Vector bit-count repair and qualification

## Scope and owners

The frozen `Zvbb` adoption (R-15-055), its data-independent-latency contract
(R-15-053), and the curated Sail instruction clauses own the meaning of
`vclz.v`, `vctz.v` and `vcpop.v`. This repair adds no instruction, architectural
state or permission. The kernel remains scalar-only under R-07-012.

The active lane of `vcpop.v` must start its count at zero, independently of the
undefined active-lane placeholder returned by `init_masked_result`. Masked and
tail lanes retain the existing vector policies. This is a source-level model
repair; a backend choosing zero for an undefined value can conceal the defect.

The independent generator, `tools/vos/vector_bitcount.py`, owns the bounded
case domain and expected results. It emits a Sail unit-test source and a decoded
instruction corpus member from the same cases. Expected counts are computed
from fixed-width integer mathematics, not from the Sail count helpers or the
instruction under test. `vector-bitcount emit` regenerates both artifacts;
`vector-bitcount check` refuses missing or changed output. The generated-artifact
checker holds those bytes against their generator.

The Sail adapter selects expected counts by an explicit operation match. It has
no positional expectation vector whose index meaning depends on Sail's descending
literal order. `vector-bitcount smoke` compiles that same generated selector to
SMT and checks every supported width and operation with distinguishable answers;
its counterexample control reproduces the descending-index mismatch for zero at
SEW=16. It builds no complete model. Generated comparison failures name the
operation, width, input, destination aliasing, expected and observed values.

## Acceptance predicate

The repair is accepted only when all of these observations hold:

- Each active popcount lane is explicitly initialized before accumulation;
  zero returns zero and all ones returns the element width.
- The generated cases cover every supported element width, zero, all ones,
  every single-bit position, high and low runs, and alternating patterns.
  The smallest width is exhausted; larger-width domains remain bounded samples.
- All three instructions agree with the independent expected counts. The
  additional identity `ctz(x) = popcount((x - 1) & ~x)` uses arithmetic modulo
  the element width and includes zero. It supplements direct expected answers.
- Architectural cases exercise zero, short and full vector lengths, masked and
  tail-undisturbed results, separate and in-place destinations, and supported
  integer and fractional LMUL geometry. `vstart` is absent in this profile and
  is not a test parameter.
- The generated corpus uses the frozen mnemonics and the repository assembler,
  so it reaches decoded instruction words as well as the unit tests' direct
  `execute` calls. A deliberately wrong expected answer is refused by the actual
  simulator; a compilation failure supplies no behavioral control verdict.
- Generator tests reject byte drift in each output and check oracle landmarks.
  The hosted adapter check refuses missing properties, undecided answers and a
  missing counterexample for the original indexing defect.
  Strict Sail compilation succeeds; the changed model bytes, project registration,
  generated bundle, dialect and corpus manifest are consistent.
- Host CI passes on Windows and Ubuntu for the settled main revision. Every
  Guest CI lane is dispatched for that revision; the unit tests, model and proof
  gates remain hosted, and a pending guest verdict is recorded as pending.

Local feedback is limited to focused host tests, strict Sail typechecking,
the small adapter check, simulator-only building, and this corpus member and its
negative control.
Complete model builds that also execute the bundled test suite, complete gate
suites and every benchmark remain CI-only. These checks establish a bounded
regression campaign, not a universal bit-count theorem or silicon timing proof.

## Compiler and service follow-up

[The vectorized CLZ/CTZ article](https://purplesyringa.moe/blog/vectorized-clz-and-ctz/)
provides software fallbacks for machines without the native vector counts.
VerifiedOS already carries those operations. M1.3's existing primitive and
RVV-autovectorization duties should qualify direct bit-count primitives and
vectorized loops against the native forms, preserving the source language's
zero semantics and the existing worst-case cost and image-size constraints.
The floating-point and x86 shuffle fallbacks add no required profile surface.
`Zvkt` does not override R-15-055's restriction on secret-labeled operands.

[Andy Chiu's LPC 2026 kernel-vectorization experiments](https://lpc.events/event/20/contributions/2455/attachments/2183/4910/LPC2026%20Andy%20%283%29.pdf)
identify block operations and bounded loops as candidates, with partial vector
context saves, entry/IRQ exclusions and hardware-dependent regressions. Their
Linux percentages are not VerifiedOS performance evidence. R-07-012's single
scalar kernel binary and R-07-014a's zeroize-without-save discipline retain their
existing contracts; enabling kernel vectors would create caller-state
preservation, privileged spill/cleanup and class-specific timing obligations.

A narrow candidate for M1.3 is the ordinary-byte staging loop in
[`vos_copy_stage`](../../copy-service/src/copy_service.c), under the
[copy service's](../../copy-service/README.md) guarded length, disjoint extents
and source-quiescence contract. A strip-mined implementation can use a chunk/index
invariant and pointwise byte equivalence. Acceptance still requires zero length,
short and final partial vectors, exact source-read coverage without overreads,
capability bounds and tag effects, and unchanged publication/refusal behavior.
Vector stores clear overwritten capability tags (R-15-115a), so this experiment
must not generalize to capability-bearing copies or pointer-field SLP.

Compare final linked scalar and vector forms using the declared core-class timing
annotation, encoded size, stack/spill and required sink/erasure costs. Keep the
existing compiler/admission route and its final-artifact evidence. This is a
candidate within the deferred M1.3 owner, not a new optimizer workstream or a
claim that whole C/ISA refinement is already available.

## Focused qualification evidence

[The recorded focused evidence](vector-bitcount-evidence.json) binds its recorded model,
profile, generator and corpus bytes to successful simulator execution and the
wrong-count, fractional-tail and masked-lane controls. The corpus manifest owns
the measured trace size and digest. Strict Sail checking includes the registered
unit source; complete unit execution remains a Guest CI obligation. Generator
and related tool tests, Python typing on Windows and Linux, and the two new
generated-artifact rows' dedicated drift probes passed.

The retained Host CI run supplies a failed verdict for its recorded revision,
with incomplete contained-compiler provenance in the firmware crypto and chain
target manifests. This focused record supplies no passing Host CI or Guest CI
verdict and does not authorize bypassing either gate.
