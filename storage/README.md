# Storage executable boundary

[node_image.c](src/node_image.c) supplies M5.3d's first concrete node-image codec.
It serializes a bounded unsigned-64-bit key/value instance of
[ExecutableIndex.v](../proofs/ExecutableIndex.v)'s `ENode`: a leaf contains ordered
key/value entries, while a branch contains separators and child arena addresses.
The codec preserves their order; it does not decide key ordering, separator
ranges, balance, cycles or tree-wide admission. Those checks belong to the index
and its eventual checked decoder integration.

[The public header](include/vos_node_image.h) owns the bounds and API. Composition
supplies fanout, arena capacity and an exact block length large enough for a full
leaf. Empty leaves and single-child branches preserve the reference's local
shape, which has no minimum occupancy. Child addresses and node identity must fit
the declared arena. Encoding and decoding refuse before changing output. Callers
supply disjoint input and output objects.

The canonical format begins with `VOSNODE1`, followed by little-endian kind and
count (`uint32`), node identity and generation (`uint64`). A leaf stores each
key followed by its value; a branch stores its separators followed by its child
addresses. These payload words are little-endian `uint64`. Unused block bytes are
zero and a decoder refuses nonzero padding, an unknown format, wrong length,
wrong expected identity or generation, invalid shape or out-of-arena references.
Unused decoded array cells are zero. In-memory unused cells do not enter the
encoding. `vos_node_derive_nonce` and `vos_node_decode_nonce` provide the
canonical 96-bit (12-byte) coordinate-derived AES-GCM nonce bijection over
`(domain_epoch, kind, node_id, generation)` (R-10-022a), packing the 64-bit
generation, 24-bit arena node identity, 7-bit domain epoch and 1-bit node kind
so parent branch slots need not store a separate 12-byte nonce per child.

The identity checks in `node_image.c` alone provide no cryptographic
authentication: a storage caller must authenticate each block against its
independent parent/root evidence before using it, as implemented by
[crypto_core.c](src/crypto_core.c) and [storage_publish.c](src/storage_publish.c)
below. The numeric key/value instance remains bring-up source rather than the
final variable-width object-key representation, and purecap Sail target execution
and full Gallina index-refinement closure remain open under
[the recovery contract](../docs/implementation/storage-recovery-policy.md).

`python tools/run.py test --only storage_node_image` discovers the focused
behavioral module. Its native C cases run on Linux, including Host CI's Ubuntu
runner; Windows still checks the pure byte oracle. The
[native seam](host/node_image.c) lets that module compare encoded bytes with an
independent Python byte oracle, decode independently generated blocks, and check
malformed inputs without changing caller outputs. Compiled behavioral mutations
must fail their specified controls; a compile failure supplies no mutation kill.

[The tree-image reader](src/tree_image.c) now joins those blocks to bounded
numeric lookup under [its read contract](tree-image.md). `vos_tree_lookup`
checks the entire reachable tree before returning a value or a true miss,
including key ordering, strict separators, child ranges, exact shared leaf depth
and finite work limits; `vos_tree_lookup_path` provides the $O(\log_B N)$
runtime query path (R-10-022a), validating only the root-to-leaf path (`height + 1`
node decodes) and its inherited `[lower, upper)` brackets without walking
off-route subtrees.
Retained roots can share nodes with different expected generations. Empty leaves
and single-child branches retain the reference's local shape; repeated empty
children remain admissible within the declared reference-visit budget. Structural
refusal and key absence have distinct results, and refusal preserves caller
output even when a valid query branch was already visited.

The caller still authenticates and freezes each reachable block and its expected
generation before use. This C seam supplies no authentication, update algorithm,
refinement theorem, publication/reopen or executable compartment product.
`python tools/run.py test --only storage_tree_image` runs its independent byte
and routing witness on both platforms; Linux also runs the compiled map,
retained-root and refusal campaign and executed behavioral controls. The native
campaigns run on Host CI's Ubuntu runner.

[The numeric copy-on-write updater](src/tree_update.c) adds insertion,
replacement, leaf/internal/root splits, single-pass sorted-batch CoW updates
(`vos_tree_insert_batch`, R-10-004), Rodeh-style lazy CoW deletion
(`vos_tree_delete`, R-10-010), path-local $O(\log_B N)$ CoW updates
(`vos_tree_insert_path`, `vos_tree_insert_batch_path`, `vos_tree_delete_path`,
R-10-022a), canonical history-independent bottom-up compaction
(`vos_tree_compact`, R-10-021), and $O(1)$ birth-generation snapshot-reclamation
checks and deadlist partitioning (`vos_tree_can_reclaim_node`,
`vos_tree_classify_reclaim`, R-10-010) under
[its candidate-update contract](tree-update.md), mirroring
[ExecutableIndex.v](../proofs/ExecutableIndex.v)'s proved `insert_gate`,
`delete_gate`, `insert_batch_gate` and history-independent `compact_gate`. It
fully admits the retained tree before appending, checks the candidate tree
before returning its root, and preserves every byte and expected generation in
the prior allocated prefix. Arena exhaustion, depth or visit limits and invalid
input refuse without publishing a root. Failed appends may occupy the unused
suffix until its next attempt. The caller still owns authentication, stable
inputs and actual publication. Relational C-to-Gallina lowering, durable nonce
and checkpoint ordering on target, persistent target reopen and two-instance
target integration remain open.

`python tools/run.py test --only storage_tree_update` checks an independent
full-width byte boundary and C-to-Gallina `VOSNODE1` translation unit on both
platforms. Linux additionally compares generated insertions, replacements,
splits, lazy deletions, sorted-batch updates, retained snapshots and
history-independent compaction with independent maps, translates the compiled C
updater's `VOSNODE1` arena bytes directly into Gallina (`ExecutableIndexComparison.v`)
to verify exact structural and logical-map agreement (`eq_refl` and `rocqchk`)
with [ExecutableIndex.v](../proofs/ExecutableIndex.v)'s `published`, `read_gate`,
`insert_gate`, `delete_gate`, `insert_batch_gate` and `compact_gate` (plus a
tampered-value negative control), exercises split/resource refusals and executes
compiled behavioral controls.

[The crypto-core compartment](src/crypto_core.c) and
[its public header](include/vos_crypto_core.h) implement the self-contained C11
cryptographic primitives required by M5.3d and Q44: FIPS 180-4 SHA-256,
FIPS 198-1 HMAC-SHA-256, FIPS 197 AES-128/192/256, NIST SP 800-38D AES-GCM
96-bit-nonce authenticated encryption and constant-time tag verification
(matching [Sha256.v](../proofs/Sha256.v) and [AesGcm.v](../proofs/AesGcm.v)),
domain-separated purpose-key derivation (`aead_key`, `dedup_key`, `commit_key`,
R-10-015, R-10-023), deterministic within-domain `vos_crypto_core_keyed_digest`
with cross-domain incomparability (R-10-016), RoT monotonic `Fresh` epoch
sealing and verification (`vos_crypto_core_seal_epoch`,
`vos_crypto_core_verify_epoch`, R-10-013c, R-10-013e), and BFU/lock/crypto-erase
key zeroization (`vos_crypto_core_lock_domain`, `vos_crypto_core_crypto_erase`,
R-10-014, R-10-032).

[The early publication and reopen producer](src/storage_publish.c) and
[its public header](include/vos_storage_publish.h) join `node_image.c`,
`tree_image.c`, `tree_update.c`, `resident_reads.c` and `crypto_core.c` under
[the recovery policy's early executable publication checkpoint](../docs/implementation/storage-recovery-policy.md#early-executable-publication-checkpoint):

- `vos_storage_reserve` persists the monotonic key-wide nonce reservation record
  before any node block or journal frame is sealed with that generation's
  coordinate-derived AES-GCM nonce (R-10-022a, F-458), refusing exhaustion
  without wrapping or rolling back consumed reservations.
- `vos_storage_stage` authenticates the retained arena prefix, executes the
  bounded CoW B+ tree candidate update (`insert`, `insert_batch`, `delete` or
  `compact`) alongside snapshot-aware deadlist classification, and seals each
  allocated node block and redo journal frame with coordinate-derived AES-GCM
  and domain-separated keyed digests without mutating the committed root.
- `vos_storage_publish` binds the ordered redo payload manifest, per-block AEAD
  metadata, root digest and optional `Fresh` epoch seal into the HMAC-signed
  checkpoint before acknowledgment or journal reuse (R-10-002a, R-10-013c),
  supporting deterministic crash-cut injection (`VOS_STORAGE_CUT_AFTER_RESERVE`,
  `VOS_STORAGE_CUT_MID_PAYLOAD`, `VOS_STORAGE_CUT_BEFORE_CHECKPOINT`,
  `VOS_STORAGE_CUT_BEFORE_EPOCH_SEAL`, `VOS_STORAGE_CUT_BEFORE_ACK`).
- `vos_storage_reopen` discards volatile store state, verifies the durable nonce
  floor, checkpoint MAC and `Fresh` epoch root (R-10-013e), rolls back unsealed
  `Fresh` checkpoints (R-10-013c), replays complete committed redo prefixes
  idempotently while discarding uncommitted suffixes and refusing torn/corrupted
  committed frames (F-460), and reconstructs the authenticated arena.
- `vos_storage_verify_resident` supplies Q44's real `vos_resident_verifier`
  callback for `vos_resident_complete` (R-10-006a, R-10-006b, R-10-001),
  checking the domain-separated object digest and verifying `(object_id, root, version)`
  membership in the store's authenticated B+ tree without mutating common
  owner state.
- `vos_storage_encode_blkdev_medium`, `vos_storage_decode_blkdev_medium`,
  `vos_storage_encode_blkdev_image`, `vos_storage_decode_blkdev_image`,
  `vos_storage_reopen_blkdev_image` and `vos_storage_apply_block_tear` map
  `struct vos_storage_medium` onto the modeled block device's 8192-byte
  (`64` blocks of `128` bytes) medium and 32-byte `"VOSBLK01"` persistent image
  header ([interfaces/block-device-contract.md](../interfaces/block-device-contract.md)),
  with [the C++ `blkdev::image` join harness](host/storage_blkdev_join.cpp)
  linking `storage_publish.c` and `crypto_core.c` directly to
  [model/c_emulator/blkdev_image.cpp](../model/c_emulator/blkdev_image.cpp).

`python tools/run.py test --only storage_publish` checks the Python SHA-256,
HMAC-SHA-256 and domain-KDF oracle on both platforms; Linux additionally builds
and runs [the native C harness](host/storage_publish.c) and
[the `blkdev::image` join harness](host/storage_blkdev_join.cpp) across NIST
test vectors, all five crash cuts, `"VOSBLK01"` image header/geometry
validation, `verifiedos-blkdev-receipt-2` SHA-256 chaining across writer close
and reader open, non-prefix reset bit tears (`(old & ~m) | (new & m)`),
swap/rollback refusals, two-instance (`system-integrity` and `user-data`)
execution over the shared L1 index body (R-10-003), and Q44 resident-read
completion with zero common per-read writes, and kills eight compiled behavioral
mutants across `crypto_core.c` and `storage_publish.c`. Target purecap/Sail
execution and Gallina refinement of the extended tree operations remain open.
