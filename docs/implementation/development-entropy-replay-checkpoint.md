# Development entropy replay checkpoint

This 2026-10-10 record qualifies the bounded
[development contract](contracts/development-entropy-replay.md) over actual
generated Sail calls. S6 remains open. The contract's delegated scope decision
records why this checkpoint is useful without awarding implementation-checklist
completion credit.

## Retained evidence

The public-only receipt
[`/root/build/lane-checklist-20261010-a/entropy-runtime/receipt.json`](retained-evidence/root/build/lane-checklist-20261010-a/entropy-runtime/receipt.json)
has SHA-256
`8846408f9ab6df2026a80436c55e35ab47c67d2f3d934c8153b594c8dc3f5392`.
It records exact controller, test, generated executable, composition, affected
source and locked Sail input hashes, plus the resolved Sail, C++ compiler, CMake,
Ninja and ccache executable hashes. These identities describe the local checkpoint;
they supply no hosted-gate verdict or reusable production image signature.

The finite campaign records exactly the direct draw, actual MMIO draw, watchdog
arm and accepted-pet draw. Initial root refusal, latched root refusal and rejected
pet produce no event. Coordinates identify the composed RoT core, with retirement
zero and explicit call slots; no instruction retirement is claimed.

Paired replay supplies independently generated development words and compares
only the receipt's named public Boolean observations. Token values and opaque
commitments are absent from those observations. A separate zero-word control
preserves the same classes because the watchdog normalizes zero challenges and
rejects zero pet responses. General draw-dependent branches and faults remain
unsupported outside this comparison.

The receipt lists authentication, expected-binding, origin, exact-input,
endpoint, draw-point and count refusal controls. Actual preflight capacity
refusals report unchanged source state; declined commitments after conditioning
report source advancement and prevent direct recorder finalization. EOF from an
interrupted actual model and an altered actual preflight frame latch both
recorder and replay cursor refusal and close the child processes and private
pipes. Invalid or throwing fresh-word callbacks latch cursor refusal too.
Production, declassification and actual-draw requests refuse before model launch.
Non-pipe standard output refuses before initialization, and the trusted harness
disables core dumps before holding model state.

No original draws, effective secret words, keys, envelopes or raw private frames
are retained in this record. The private-pipe controller discards transient frames
on close and converts protocol and callback failures to fixed safe diagnostics.

## Focused validation

The isolated checkout is
`C:\Users\symbi\source\repos\VerifiedOS\.worktrees\checklist-20261010-a`;
its native lane is `/root/build/lane-checklist-20261010-a`. Strict candidate
typechecking passed with locked Sail 0.20.3 and the existing strict flags. The
new C++ roots use explicit `--c-preserve` exports without changing acceptance
flags or existing tests.

The local commands were:

```text
python tools/run.py model emit
cmake --build /root/build/lane-checklist-20261010-a/verifiedos-model --target entropy_capture entropy_observer -j2
/root/build/lane-checklist-20261010-a/verifiedos-model/test/unit_tests/entropy_observer
python tools/run.py test --only replay
python3 tools/run.py test --only replay_runtime --slow --jobs 1
```

The emit and focused build passed. The unchanged observer harness passed all its
original direct, refused-root, watchdog, ordering, callback-abort and ordinary
fallback checks. The focused host replay selection passed; the focused guest
runtime campaign passed with its host controls and actual model executions.
Scoped `ty` checks on Linux and Windows targets and `ruff` passed for the changed
Python files using the repository configurations from `tools/`.

Complete model tests, host gates, guest gates and benchmarks were not run locally.
The integrator owns generated-bundle freshness and hosted validation of the
settled main revision.

## Inputs still required for S6

The checkpoint does not implement production DRBG discipline, the trusted
production commitment writer or RoT sealing/export authentication. The
capability-authorized time-service reply, public link-address producer and
complete sentinel-event producer remain absent. Complete machine capture,
signed reproducible-image binding, production fault reproduction and the
applicable CT/noninterference proof scope remain open under the
[operational record contract](contracts/replay-record.md). Its complete predicate,
rather than this call-level evidence, determines S6 completion.
