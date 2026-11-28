# Resident toolchain admissibility and bootstrap coordinator

[resident_tc.c](src/resident_tc.c) implements the bounded, GC-free C17 resident
toolchain admissibility, resumable activation, residency scoring, and
bootstrap-reproduction coordinator specified in
[ResidentToolchain.v](../proofs/ResidentToolchain.v) for
[toolchain residency](../docs/performance/toolchain-residency.md) and
[userspace porting](../docs/implementation/userspace-porting.md).
[The public header](include/vos_resident_tc.h) defines the fixed capacities,
status codes, and entry points, linking against
[crypto_core.c](../storage/src/crypto_core.c) via
[vos_crypto_core.h](../storage/include/vos_crypto_core.h) for SHA-256 artifact
and bootstrap-receipt digests.

## Components and invariants

- **`vos_rtc_screen_license` (`R-18-004e`)**: Refuses shipping a non-commercial
  external pass without an explicit commercial redistribution grant, an
  independent implementation, or strict restriction to the enumerated
  dual-licensed subset; requires license terms to be read at incorporation.
- **`vos_rtc_audit_closure` (`R-13-027`, `R-13-027a`)**: Audits `unsafe` sites,
  ambient authority, and host assumptions (`Filesystem`, `Subprocess`,
  `HostAllocator`), forcing unresolved host assumptions into named estimated
  sub-ports and never `unsafe` exceptions.
- **`vos_rtc_check_compartment_caps`, `vos_rtc_check_smallest_loop_first`,
  `vos_rtc_run_activation` (`R-08-046`, `R-13-027a`)**: Enforces
  smallest-loop-first order (type-checker over admitted artifact before
  compilers), denies execute/sealing/wiring authority over outputs, tracks
  per-pass step budgets and peak bytes/RSS, and refuses pool exhaustion while
  preserving the running generation.
- **`vos_rtc_pools_can_share`, `vos_rtc_check_residency` (`R-08-014`,
  `R-08-018a`, `R-18-004e`)**: Distinguishes per-mode `ReadingA` from
  one-layout `ReadingB` and forbids compiler/prover pool sharing without
  non-co-occurrence proof over disjoint live ranges.
- **`vos_rtc_compare_bootstrap_receipts` (`R-13-027`, `R-06-014`)**: Compares
  the on-device self-build artifact and admission receipt against the
  locked-switch host receipt (`Reproduced` vs named `Diverged` cause), while
  requiring `R-06-014`'s De Bruijn bootstrap root to remain `Relocated`.

## Validation

Run `python tools/run.py test --only test_resident_toolchain` on Windows
(pure-Python oracle and C17/SPDX/proof checks) and
`python3 tools/run.py test --only test_resident_toolchain` in WSL Linux (also
compiling [resident_tc.c](src/resident_tc.c),
[crypto_core.c](../storage/src/crypto_core.c), and
[test_resident_tc.c](test/test_resident_tc.c) under Clang strict C17 and GCC C17
ASan/UBSan and running all compiled behavioral mutation controls).
