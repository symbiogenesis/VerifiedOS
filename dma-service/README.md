# DMA Ring Service

GC-free ISO C17 implementation of the `ring_dma` world declared in
[ring-reference.json](../interfaces/ring-reference.json) and specified in
[RingContract.v](../proofs/RingContract.v) (`RingDma`) and
[CopyRingService.v](../proofs/CopyRingService.v).

## Files

- [vos_dma_service.h](include/vos_dma_service.h): public types and entry
  points using explicit caller-owned slots, segment buffers, session table,
  and configuration descriptor with no heap allocation or recursion.
- [dma_service.c](src/dma_service.c): direction-permission authorization,
  pre-transfer whole-extent and per-segment validation without reinterpretation,
  commit-point cancellation (`VOS_DMA_CANCELED` vs `VOS_DMA_TOO_LATE`),
  terminal capability release, quiescence-bound fail-stop enforcement, session
  reset across all lifecycle states, and stale-generation refusal.
- [test_dma_service.c](test/test_dma_service.c): host C17 control suite
  consuming build-lane `dma_service_config.h` emitted dynamically from
  [ring-reference.json](../interfaces/ring-reference.json), executed under
  ASan/UBSan and compiled mutation controls via
  `python3 tools/run.py test --only test_dma_service`.

## Scope and boundaries

- **Single-owner configuration (`K-68`)**: neither the C headers/sources nor
  the test runner duplicate `ring_dma` bounds by hand. `test_dma_service.py`
  parses [ring-reference.json](../interfaces/ring-reference.json) with
  `unique_object` and emits `dma_service_config.h` into the build lane.
- **Pre-transfer validation without reinterpretation (`R-12-100`)**:
  `vos_dma_submit` checks generation, ring capacity, duplicate live request
  IDs, direction permissions (`to_server -> load`, `to_client -> store`),
  per-segment ceilings and capability bounds, and total extent length, then
  snapshots the validated descriptor and segment array into the private slot.
  Subsequent `accept`, `complete`, and `reclaim` stages read only that
  snapshot.
- **Cancellation, terminal release, and reset (`R-12-097`, `R-12-099`, `R-12-100`)**:
  cancellation before `commit_index` transitions to `VOS_DMA_TERMINAL` and
  releases capabilities immediately (`VOS_DMA_CANCELED`); at or past
  `commit_index` returns `VOS_DMA_TOO_LATE`. Normal completion releases held
  capabilities at `VOS_DMA_TERMINAL` before reclamation. Session reset checks
  quiescence across every lifecycle state, fail-stops on missing or expired
  quiescence, advances the session generation on success, and refuses stale
  generations.
