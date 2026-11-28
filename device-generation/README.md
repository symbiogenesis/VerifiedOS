# On-device generation coordinator

[device_gen.c](src/device_gen.c) implements the bounded, GC-free C17 on-device
generation composition, trusted-path minting, offline scoped inclusion, and
fixed-package reuse coordinator specified in
[DeviceGeneration.v](../proofs/DeviceGeneration.v) and
[the fixed-packages contract](../docs/implementation/contracts/fixed-packages.md).
[The public header](include/vos_device_gen.h) defines the fixed capacities,
status codes, and entry points, linking against
[crypto_core.c](../storage/src/crypto_core.c) via
[vos_crypto_core.h](../storage/include/vos_crypto_core.h) for SHA-256 and
HMAC-SHA-256.

## Components and invariants

- **`vos_dgen_core_export_key`, `vos_dgen_trusted_path_mint` (`R-13-027b`)**:
  Holds the local generation signing key inside `vos_dgen_crypto_core` with no
  export path (`VOS_DGEN_ERR_EXPORT_FORBIDDEN`), denies key or mint access to
  the composer compartment (`VOS_DGEN_ERR_COMPOSER_PRIVILEGED`), displays the
  exact roster hash and generation root in `vos_dgen_prompt`, and gates every
  HMAC-SHA-256 mint on a one-use credential-authenticated consent act bound to
  `(roster_hash, gen_root, nonce)`.
- **`vos_dgen_mode_enter`, `vos_dgen_mode_exit` (`R-11-018`)**: Enforces
  admission-checked mode-edge entry preconditions (edge certificate, runtime
  guard, dwell bound, reserved recovery state) and restores normal mode with
  zero lingering privilege on both completion and failure.
- **`vos_dgen_audit_offline_package` (`R-13-023b`, `R-13-027`)**: Runs with
  no network reachable; locally authored closures carry no publisher, whereas
  any fetched member inside a local build lacking a logged checkpoint name or
  consistent inclusion proof refuses installation.
- **`vos_dgen_compose_and_admit` (`R-13-028`, `R-13-026`, `R-06-015a`)**:
  Authenticates the prior `vos_dgen_checked_set` root HMAC, verifies object
  digests and base-image bit-for-bit reproducibility, reuses matching
  package-local verdicts without re-checking unchanged packages, bounds fresh
  CIC checks by `step_budget` and `workset_budget`, always requires fresh
  concrete-layout TAL and global wiring/resource checks, stages into the
  inactive A/B slot only, and commits the successor root and checked set
  together while recording occupancy.
- **`vos_dgen_health_check`**: Settles a healthy live generation or rolls back
  to the retained predecessor within the anti-rollback floor.

## Validation

Run `python tools/run.py test --only test_device_generation` on Windows
(pure-Python oracle and C17/SPDX/proof checks) and
`python3 tools/run.py test --only test_device_generation` in WSL Linux (also
compiling [device_gen.c](src/device_gen.c),
[crypto_core.c](../storage/src/crypto_core.c), and
[test_device_gen.c](test/test_device_gen.c) under Clang strict C17 and GCC C17
ASan/UBSan and running all compiled behavioral mutation controls).
