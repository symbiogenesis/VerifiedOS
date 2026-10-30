# Guardrail comparison evidence

The [comparison workflow](../../../.github/workflows/guardrail-performance.yml)
runs the [checker](../../../tools/ci/archive_scan_benchmark.py),
[runner](../../../tools/ci/runner_benchmark.py) and
[installed proof-context](../../../tools/ci/proof_identity_benchmark.py) comparisons
on GitHub Actions. Each raw record owns its source and corpus identities,
interpreter, platform, repetitions, worker count, elapsed time and peak memory.
Baseline and candidate read the same indexed corpus in fresh processes, in
alternating order. Worker RSS excludes descendants and does not describe a full
kernel check. These comparisons supply no Host or Guest CI verdict.

The [complete earlier run](https://github.com/symbiogenesis/VerifiedOS/actions/runs/41110964006)
retains its [checker](41110964006-checker.json),
[runner](41110964006-runner.json) and
[proof-context](41110964006-proof-identity.json) records. Checker reports matched
and peak memory fell substantially, but complete checker time regressed; that
runtime result is rejected as acceptance for the scanner. Markdown and proof-header
repair improved with identical reports and source-byte assertions. Installed
proof identities matched and native cache controls passed. The small proof-context
timing differences do not establish a repeatable speed factor.

The [boundary-matcher comparison](https://github.com/symbiogenesis/VerifiedOS/actions/runs/41113896269)
retains its [checker](41113896269-checker.json),
[runner](41113896269-runner.json) and
[proof-context](41113896269-proof-identity.json) records. Moving the streaming
presence predicate into native matching preserved outputs and the memory benefit,
but did not improve complete checker time. This scanner runtime result is also
rejected. Candidate-line collection still used the Python boundary loop in that
revision; the retained record does not measure its replacement. The complete
runner again preserves reports and byte assertions, with a repeatable proof-header
improvement and a smaller Markdown difference.

The [candidate-line comparison](https://github.com/symbiogenesis/VerifiedOS/actions/runs/41117791545)
retains its [checker](41117791545-checker.json),
[runner](41117791545-runner.json) and
[proof-context](41117791545-proof-identity.json) records. The native candidate-line
matcher alone also fails the complete checker runtime target, with equal reports
and the retained memory reduction. It supplies no accepted scanner speed factor.

The [possessive-ID and ASCII-glyph comparison](https://github.com/symbiogenesis/VerifiedOS/actions/runs/41118735840)
retains its [checker](41118735840-checker.json),
[runner](41118735840-runner.json) and
[proof-context](41118735840-proof-identity.json) records. These changes reduce the
earlier overhead but leave a smaller complete checker slowdown; runtime acceptance
remains open. Reports, source-byte assertions and native cache controls pass. The
separate profiler trace covers the locked launcher waiting for its child, so it
supplies no call-cost evidence for the checker. The revised diagnostic route
profiles the benchmark worker directly.

The [direct-worker diagnostic](https://github.com/symbiogenesis/VerifiedOS/actions/runs/41121547760)
retains its complete [structured profile and worker report](41121547760-profile.json),
including original artifact hashes. It profiles the actual checker and reports
no findings. Repeated per-name and per-lineage absence searches dominate its call
costs; native regex execution is small by comparison. Profiling overhead supplies
no paired speedup evidence. The bounded name and byte tries replace those repeated
searches; their complete comparison remains separate from this diagnostic.

The [initial attempt](https://github.com/symbiogenesis/VerifiedOS/actions/runs/41108543698)
retains [partial runner evidence](41108543698-runner.json) and its
[proof-context record](41108543698-proof-identity.json). Baseline source placement
outside the repository prevented imports from locating repository-owned data. The
checker failed before recording samples; the runner stopped before its complete
repair sweep. Partial Markdown samples supply no completed runner acceptance.
Later harnesses place archived baseline sources below the real ignored output
root, without patching repository discovery or the owners they read.

Native census replay remains unmeasured because the original three-root control
emission is unavailable pending migration. The
[descriptor](../../../tools/ci/census-benchmark-inputs.json) refuses incomplete
input, and [Q35q](../../../PLAN.md#native-sail-census-validation) retains its full
support, positive and corruption-control acceptance requirements.
