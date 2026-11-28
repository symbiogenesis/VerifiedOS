# Deterministic-Replay Nondeterminism Record (`replay/`)

`replay/` implements the bounded, GC-free C17 deterministic-replay
nondeterminism recorder, HMAC-SHA256 commitment sealer seam, canonical binary
(`VOSRR01`) and `replay-record-v1`-shape structural validators, and strict
demand-cursor verifier for S6, aligned with
[ReplayRecord.v](../proofs/ReplayRecord.v),
[the replay-record contract](../docs/implementation/contracts/replay-record.md),
[the authored C language profile](../docs/implementation/c-language-profile.md),
and [the host fixtures](../tools/vos/replay_record.py).

[The public header](include/vos_replay_record.h) defines the closed four-source
enum (`VOS_RR_SRC_ENTROPY`, `VOS_RR_SRC_LINK_ADDRESS`, `VOS_RR_SRC_TIME_READ`,
`VOS_RR_SRC_PHYSICAL_EVENT`), fixed bounds, status codes, and `vos_rr_*` entry
points. [replay_record.c](src/replay_record.c) links against
[crypto_core.c](../storage/src/crypto_core.c) via
[vos_crypto_core.h](../storage/include/vos_crypto_core.h) for HMAC-SHA256
commitment sealing.

## Enforced invariants

- **Closed four-source set & fixed classification (`R-16-015`, `R-16-016`, `R-16-017`)**:
  `vos_rr_classify_source` binds `VOS_RR_SRC_ENTROPY` exclusively to
  `VOS_RR_CLASS_SECRET_COMMITMENT` and the three public sources exclusively to
  `VOS_RR_CLASS_PUBLIC_VERBATIM`. `vos_rr_recorder_record` reads the source from
  the snapshotted endpoint allowlist rather than caller input.
- **HMAC-SHA256 commitment seam (`R-16-017`, `R-16-020`)**:
  `vos_rr_seal_entropy_draw` seals raw entropy draw bytes with domain tag
  `VOSRRCM1` over `(composition, input_trace, point, interface_id, raw_draw)`
  and wipes stack scratch buffers, so raw entropy draw bytes never appear in
  finished records.
- **Monotonic coordinates & contiguous `seq` (`R-15-241`)**:
  `vos_rr_point_lt` enforces strict lexicographic order over
  `(slot, core, retire, ordinal)`, per-core `retire` monotonicity prevents local
  counter regression, and `seq` must be contiguous and 0-based.
- **Pre-invocation worst-case reservation & sticky failure latch (`R-16-013`, `R-16-023`)**:
  `vos_rr_recorder_record` reserves `84 + max_payload_bytes` before invoking the
  producer callback, releases unused margin only after an accepted event (or
  declined draw), refuses reentrancy, and latches `failed = 1` / `fault_routed = 1`
  so an uncertain prefix cannot be finalized by `vos_rr_recorder_finish`.
- **Independent binding & strict demand cursor (`R-16-018`, `R-16-019`, `R-16-022`)**:
  `vos_rr_decode_wire`, `vos_rr_decode_json`, and `vos_rr_recorder_finish`
  verify the record against an independently supplied `(base_image_root,
  composition, input_trace)` binding and expected event count. `vos_rr_cursor_consume`
  and `vos_rr_cursor_finish` require exact `(point, source, interface_id)`
  matches and refuse both premature exhaustion and trailing events.

## Validation

Run `python tools/run.py test --only test_replay_record_c` on Windows (pure-Python
reference oracle and `ReplayRecord.v` proof-surface checks) and
`python3 tools/run.py test --only test_replay_record_c` in WSL Linux (also
compiling [test_replay_record.c](test/test_replay_record.c) with strict Clang
C17, GCC C17 ASan/UBSan, and executing all compiled behavioral mutants in
[test_replay_record_c.py](../tools/tests/test_replay_record_c.py)).
