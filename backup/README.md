# Backup object and streaming export/restore service

[backup.c](src/backup.c) implements the bounded, GC-free C17 streaming export
and restore service specified in [BackupObject.v](../proofs/BackupObject.v) and
[the backup and migration contract](../docs/implementation/contracts/backup-migration.md).
[The public header](include/vos_backup.h) defines the fixed capacities, status
codes, state-machine phases, and entry points, linking against
[crypto_core.c](../storage/src/crypto_core.c) for SHA-256 and AES-256-GCM.

## Components and invariants

- **`RecoverySecret-v1`** (`vos_bk_encode_recovery_secret`, `vos_bk_decode_recovery_secret`):
  Encodes 32 key bytes as exactly 64 uppercase ASCII hex digits with leading-zero
  preservation, rejecting lowercase hex, non-hex characters, and alternate or
  trailing lengths (`R-10-038`, `R-05-051a`, `R-05-051b`).
- **`ExportView` and domain-separated sealing** (`vos_bk_export`, `vos_bk_derive_subkeys`,
  `vos_bk_chunk_nonce`): Exports only `VOS_BK_KIND_ROLLBACKABLE` regions whose
  schema is `VOS_BK_SCHEMA_DATA_ONLY` in strict ascending `region_id` order (`R-10-039`),
  derives distinct manifest and chunk AES-256 keys via `SHA-256("VOSBK-MANIFEST" || key)`
  and `SHA-256("VOSBK-CHUNK" || key)`, assigns injective 96-bit chunk nonces
  `"VOSCHK01" || be32(chunk_index)`, and commits a Merkle root over
  `(chunk_index, ciphertext, tag)`.
- **Staged restore state machine** (`vos_bk_restore_authorize`,
  `vos_bk_restore_auth_manifest`, `vos_bk_restore_plan`,
  `vos_bk_restore_stage_next_chunk`, `vos_bk_restore_complete`,
  `vos_bk_restore_commit`): Enforces `Idle -> Authorized -> ManifestAuthenticated ->
  Planned -> Staging -> Complete -> Committed | Discarded`. Refuses bad tags,
  profile mismatches, trailing bytes, missing `Fresh` initializers, or
  `Unsupported` schemas before staging with zero region writes; authenticates
  every chunk's Merkle proof and AEAD tag into an unreachable staging slot while
  preserving the active namespace byte-for-byte until atomic commit.
- **Fresh initializers** (`vos_bk_fresh_check_token`, `vos_bk_fresh_check_attempt`):
  Constructs unenrolled post-restore `Fresh` scopes across all six contract classes
  so stale/spent tokens and guess counters remain denied (`R-10-039`).

## Validation

Run `python tools/run.py test --only test_backup_service` on Windows (pure-Python
oracle/model checks) and `python3 tools/run.py test --only test_backup_service` in
WSL Linux (also compiling `src/backup.c`, `../storage/src/crypto_core.c`, and
`test/test_backup.c` with Clang C17 strict and GCC C17 ASan/UBSan, and running
12 compiled behavioral mutation controls including `backup-export-reads-fresh`).
