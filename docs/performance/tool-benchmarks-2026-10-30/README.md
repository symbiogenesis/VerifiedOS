# Guardrail comparison evidence

The [comparison workflow](../../../.github/workflows/guardrail-performance.yml)
runs the [checker](../../../tools/ci/archive_scan_benchmark.py),
[runner](../../../tools/ci/runner_benchmark.py) and
[installed proof-context](../../../tools/ci/proof_identity_benchmark.py) comparisons
on GitHub Actions. Each raw record owns its source and corpus identities,
interpreter, platform, repetitions, worker count, elapsed time and peak memory.
Baseline and candidate read the same indexed corpus in fresh processes, in
alternating order. Parent-only RSS excludes descendants and does not describe a
full kernel check. The follow-through runner record also supplies sampled summed
process-tree RSS, child CPU time and actual parser worker counts. Shared pages may
be counted repeatedly, and scheduling delays or gaps between samples can miss
spikes; the requested interval and actual sample counts remain in the record.
These comparisons supply no Host or Guest CI verdict.

The [follow-through comparison](https://github.com/symbiogenesis/VerifiedOS/actions/runs/41160809136)
retains its [checker](41160809136-checker.json),
[runner](41160809136-runner.json) and
[proof-context](41160809136-proof-identity.json) records. Hoisting the initial
name boundary and specializing complete ASCII windows improve both complete
checker samples over both baseline samples with identical ordered reports and
similar peak worker memory. Bounded Markdown workers likewise improve both
complete command samples, including process startup, with identical reports and
no serial fallback. The Markdown gain uses more aggregate memory and slightly
more total CPU; the recorded worker cap and process-tree residency support that
tradeoff on the hosted runner. Both changes meet their runtime predicates.
Proof-header reports and exact source/template bytes remain equal, and their
timing difference supplies no additional speed factor. Installed proof-context
identities match and native cache controls pass; their timings also supply no
additional speed factor. The records bind the measured source and corpus;
subsequent evidence-only commits add no timing samples.

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
no paired speedup evidence. It motivated the direct-trie experiment evaluated
separately below; this diagnostic does not qualify that implementation.

The [direct-trie comparison](https://github.com/symbiogenesis/VerifiedOS/actions/runs/41152868322)
retains its [checker](41152868322-checker.json),
[runner](41152868322-runner.json) and
[proof-context](41152868322-proof-identity.json) records. Reports, source-byte
assertions and native cache controls match, and memory stays lower, but complete
checker time regresses further. That implementation is rejected. Its separate
profile attributes the new overhead to native pattern searches, with the byte
trie slower than the original byte scans.

The [word-skipping comparison](https://github.com/symbiogenesis/VerifiedOS/actions/runs/41155386340)
retains its [checker](41155386340-checker.json),
[runner](41155386340-runner.json) and
[proof-context](41155386340-proof-identity.json) records. Restoring the original
byte searches, anchoring the name scan and skipping duplicate candidate extraction
preserve complete reports and the memory reduction, but complete checker time
still does not improve. This runtime result is rejected. The subsequent refinement
skips separator runs and words with impossible initial characters before testing
the full name trie. Proof-header repair again improves with equal reports and
byte assertions; the proof-context timing difference remains inconclusive and
native cache controls pass.

The [first-character-filtered comparison](https://github.com/symbiogenesis/VerifiedOS/actions/runs/41156550085)
retains its [checker](41156550085-checker.json),
[runner](41156550085-runner.json) and
[proof-context](41156550085-proof-identity.json) records. Both candidate checker
samples improve over both baseline samples, with equal complete ordered reports
and substantially lower peak worker memory. This scanner implementation meets the
paired runtime predicate. The original byte searches remain selected.
Markdown and proof-header repair retain equal reports and byte assertions, with
lower median component times; the proof-header improvement repeats across runs.
Installed proof-context identities match, native cache controls pass and their timing
difference remains inconclusive. The raw records identify the measured source
revision; later evidence-only commits do not supply additional timing samples.

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
