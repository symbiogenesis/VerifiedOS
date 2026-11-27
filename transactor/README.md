# Object-store reader and A/B update transactor

[transactor.c](src/transactor.c) implements the bounded, GC-free C17 object-store
reader and A/B update transactor specified in
[ObjectTransactor.v](../proofs/ObjectTransactor.v) and
[the transactor contract](../docs/implementation/contracts/object-transactor.md).
[The public header](include/vos_transactor.h) defines the fixed capacities, status
codes, and entry points, linking against
[crypto_core.c](../storage/src/crypto_core.c) for SHA-256 and HMAC-SHA-256.

## Components and invariants

- **`vos_tx_path_read`**: Path-local root-to-object Merkle reader (`R-10-001`,
  `R-06-005`). Authenticates each visited node against its canonical `VOSTXOB1`
  SHA-256 hash (`payload_len`, `kid_count`, `payload`, ordered `kids`) before
  inspecting child links or descending along the supplied witness path. Refuses
  missing nodes, hash mismatches, unlinked children, wrong targets, cycles, and
  depth exhaustion (`walk_depth`), without reading or requiring unrelated sibling
  subtrees.
- **`vos_tx_select_root`**: Fixed-location dual-copy root selector (`R-10-001a`,
  `R-09-036a`). Scans all `>= 2` copies, ignores any untrusted slot pointer,
  verifies each candidate's `VOSTXRT1` SHA-256 checksum, enrolled key ID, and
  HMAC-SHA-256 signature on its own bytes, and selects the verifying candidate
  with the highest `version`.
- **`vos_tx_stage`**: Writes a candidate `SignedRoot` into the inactive A/B slot
  only, keeping the running generation immutable (`R-11-001`) while clearing any
  stale admission verdict and invalidating any retained predecessor.
- **`vos_tx_verify_and_flip`**: Enforces enrolled-root verification (`R-09-036a`),
  anti-rollback floor checks (`version >= rot_floor`, `version >= floor_version`,
  and `version >= declared_floor`, `R-09-030`), proof-checked admission bound to
  the candidate root (`R-11-005`), witness checkpoint acceptance/consistency/inclusion
  pinning (`R-13-023b`), and complete bounded DAG authentication (`vos_tx_dag_intact`)
  before recording `retained_predecessor`, pinning the offered checkpoint, and
  toggling the live slot. Never writes or reseals the RoT floor (`R-10-032`).
- **`vos_tx_health_check`**: Settles a healthy live generation (`staged = 0`,
  `admitted = 0`) or, on health failure, falls back to the retained predecessor
  only when not restaged, matching the retained record, re-verified on its own
  bytes, permitted by both the RoT and declared floors, proof-admitted, and backed
  by an intact DAG (`R-11-002`, `R-09-030`). Refuses fallback without changing
  the live slot when no permitted predecessor exists.

## Validation

Run `python tools/run.py test --only test_transactor` on Windows (pure-Python
oracle/model checks) and `python3 tools/run.py test --only test_transactor` in
WSL Linux (also compiling `src/transactor.c`, `../storage/src/crypto_core.c`,
and `test/test_transactor.c` with Clang C17 + ASan/UBSan and running the
compiled behavioral mutation controls).
