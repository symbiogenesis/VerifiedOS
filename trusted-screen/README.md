# Backup and migration trusted screens

[trusted_screen.c](src/trusted_screen.c) implements the bounded, GC-free C17
trusted-path backup export, user-data restore, and device-migration screen
controllers specified in [BackupTrustedScreen.v](../proofs/BackupTrustedScreen.v)
and [the backup and migration contract](../docs/implementation/contracts/backup-migration.md).
[The public header](include/vos_trusted_screen.h) defines the distinct flows,
caveat acknowledgments, one-use consent witnesses, and screen state machines,
linking against [backup.c](../backup/src/backup.c) for canonical `RecoverySecret-v1`
coding and [crypto_core.c](../storage/src/crypto_core.c) for SHA-256 and
HMAC-SHA256.

## Components and invariants

- **Distinct trusted flows and gate** (`vos_ts_trusted_path_set_gate`,
  `vos_ts_issue_witness`, `vos_ts_verify_and_consume_witness`): Requires an
  unlocked device, active trusted-path hardware latch, live primary credential
  (plus receiver credential for migration), and non-app origination, refusing
  `VOS_TS_FLOW_SYSTEM_ROLLBACK` (`R-10-038`, `R-10-040`).
- **One-time `RecoverySecret-v1` display and canonical entry**
  (`vos_ts_format_recovery_display`, `vos_ts_export_show_secret_once`,
  `vos_ts_restore_enter_recovery_secret`, `vos_ts_wipe`): Renders 16 uppercase
  4-digit hex groups (79 chars + NUL) once per export, rejects redisplay,
  decodes strictly canonical 64-char uppercase hex via
  `vos_bk_decode_recovery_secret` without an app parser, and clears display
  and secret buffers via volatile writes on completion, cancel, lock, or fault
  (`BM-KEY`, `BA-DISPLAY`).
- **Mandatory caveats and non-truncated root confirmation**
  (`vos_ts_export_authorize`, `vos_ts_restore_authorize`,
  `vos_ts_migration_present_roots`, `vos_ts_migration_confirm`): Enforces the
  `R-17-054a` off-device trade warning on export (`BA-RESIDUAL`), surrendered
  freshness and explicit discard-loss warnings on restore (`BA-SCHEMA`), and
  complete non-truncated quoted receiver-root rendering and confirmation after
  mutual appraisal (`BA-MIGRATE`).
- **One-use bound HMAC consent witnesses** (`vos_ts_trusted_path_lock`,
  `vos_ts_trusted_path_restart`, `vos_ts_witness_to_bk_consent`): Binds each
  witness to flow, unlocked profile, device generation, object/snapshot,
  destination, plan, discard flag, and receiver-root digest under HMAC-SHA256,
  expiring on lock, restart, binding change, or consumption (`BA-CONSENT`).

## Validation

Run `python tools/run.py test --only test_backup_trusted_screen` on Windows
(pure-Python reference oracle and proof-surface checks) and
`python3 tools/run.py test --only test_backup_trusted_screen` in WSL Linux
(additionally compiling [src/trusted_screen.c](src/trusted_screen.c),
[backup.c](../backup/src/backup.c), [crypto_core.c](../storage/src/crypto_core.c),
and [test/test_trusted_screen.c](test/test_trusted_screen.c) under GCC C17
ASan/UBSan and Clang strict C17, and executing 12 compiled behavioral mutants).
