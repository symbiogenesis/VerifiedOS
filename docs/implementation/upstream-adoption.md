# Bounded upstream adoption

This contract selects implementation work from the
[merged-upstream review](upstream-merged-review.md). It preserves the frozen ISA,
capability fault ordering, toolchain versions and existing qualification duties.
The work introduces no new normative property or proof foundation.

## Selected changes and acceptance

| Change | Implementation boundary | Acceptance predicate |
| --- | --- | --- |
| Indexed segmented-store source overlap | Adapt sail-riscv PR 1990's segment-aware source-overlap check and focused regressions to the curated model. Preserve decoding, assembly, legal non-segmented cases, capability checks and instruction-fault ordering. | Strict locked-Sail typecheck; distinguish illegal overlap with a later segment from valid same-width and disjoint cases; exercise ordered and unordered encodings and a capability-fault-ordering control. The old check must fail the distinguishing regression. Regenerate the bundle through its owner. Build and focused behavioral checks supply development evidence; Guest CI supplies complete model/RTL/proof evidence. |
| Assertion-enabled, locked frame simulation | Compile the existing frame simulator with assertions and pass the locked assertion-control option already supported by Verilator 5.052. Add a focused assertion-policy control without changing the frame protocol or claiming a real-core attachment. | Existing frame round trips and writer controls retain their decisions. An assertion that passes must run successfully; an intentionally failing assertion must fail even after RTL attempts to disable it. An unlocked negative control must demonstrate the attempted disable. Compilation failures are not successful detections. Focused host tests bind the actual build/runtime arguments; native controls exercise the locked elaborator. |
| CLI11 unsigned numeric refusal | Consume an immutable upstream source revision carrying PR 1472, using its own license and an integrity-bound download. Retain current emulator options and valid unsigned input behavior. | The actual emulator option parser refuses prefixed negative unsigned values, including binary and octal forms, while accepting zero, positive prefixes and the maximum unsigned value where allowed. Controls distinguish a parse failure from model initialization or unrelated argument errors. Build against the selected source and retain focused parser regressions in the model's normal test/build plumbing; a fresh hosted model build remains required. |
| SoftFloat BF16 NaN predicate | Adapt PR 44's correction to the vendored `isNaNBF16UI` macro, retaining all other library bytes and the existing local platform configuration. Add no BF16 arithmetic operation or ISA extension. | A focused native test checks every 16-bit representation against the format's independent exponent/fraction predicate, with an explicit signaling-NaN case. The preceding macro must fail that test while infinities and finite values remain correctly classified. The test is registered in ordinary CTest and can run alone locally; full model acceptance remains hosted. This establishes the helper's classification, without asserting a demonstrated executed-model defect. |

The integrator owns shared documentation, licensing/provenance records and generated
artifact repair. Workers own only the assigned authored source and focused checks.
Upstream licensing is re-read at the exact selected source before incorporation.
The bounded Sail journal and existing source-byte rules apply to the model repair.
No shared switch or host/guest tool binary is changed for this batch.

## Validation handoff

Run focused local checks appropriate to each changed consumer and record their
scope and verdict. Complete host and guest suites and all benchmarks remain on
GitHub Actions. Integrate through `run.py fanout`, publish only `main`, require
Host CI on Windows and Ubuntu, and dispatch every Guest CI lane for the settled
revision. Finish with Guest CI pending and no claim of its success. Checks outside
those workflows retain their separate acceptance requirements.

## Local qualification

The focused development checks on 2026-10-22 establish the following results:

| Consumer | Result and distinguishing control |
| --- | --- |
| Indexed segmented stores | The generated-model harness passes ordered and unordered cases at VLEN256 and the shipped V-class VLEN4096, including legal overlap/disjoint and capability-fault-ordering controls. Restoring the old guard compiles successfully and makes both instruction forms fail specifically at the later-segment overlap expectation. The corrected source is restored byte-for-byte and its focused runs pass again. Strict Sail typechecking also passes on the final authored bytes. |
| Frame writer | Pinned Verilator 5.052 passes the frame round trip and existing writer-mutant controls. The assertion-policy fixture passes its active positive control, detects the intended failure after RTL disables assertions under the runtime lock, and suppresses that failure without the lock. Focused tool tests bind the compiler/runtime arguments and preserve all reported outcomes. |
| Emulator CLI | A native target linking the actual option parser passes its isolated CTest, including prefixed negatives, whitespace, overflow, valid prefixes and unsigned maxima. The hash-verified preceding 2.7.2 amalgamated header fails the same regression by accepting `--inst-limit 0b-1` as the maximum unsigned value. |
| BF16 classifier | The standalone native target passes its isolated CTest and checks every 16-bit representation. The preceding vendored header compiles with the same test and fails specifically on signaling NaN `0x7f81`. |

The Sail checks use locked Sail 0.20.3. The local expected Z3 5.3.1 prefix is
absent, so the front door reports a PATH-solver fallback; the bounded journal
retains the actual tools and diagnostics. Complete qualification therefore remains
with Guest CI's pinned bootstrap and model evidence sweep. No complete suite or
benchmark is run locally. Host CI and the Guest CI dispatch for the settled revision
are recorded by the fan-out handoff and reported with the delivery.

The source review's broader toolchain migrations, new proof interfaces, optional
certificate backends and unimplemented compute/runtime consumers remain with
their existing owners; this contract selects none of them.
