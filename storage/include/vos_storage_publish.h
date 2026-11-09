// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_STORAGE_PUBLISH_H
#define VOS_STORAGE_PUBLISH_H

#include <stddef.h>
#include <stdint.h>

#include "vos_crypto_core.h"
#include "vos_node_image.h"
#include "vos_resident_reads.h"
#include "vos_tree_image.h"
#include "vos_tree_update.h"

enum {
    VOS_STORAGE_MAX_ARENA_NODES = 64u,
    VOS_STORAGE_MAX_BLOCK_BYTES = 128u,
    VOS_STORAGE_MAX_JOURNAL_FRAMES = 32u,
    VOS_STORAGE_MAX_SNAPSHOTS = 8u,
    VOS_STORAGE_MAX_DEADLIST = 64u,
    VOS_STORAGE_MAX_FRESH_KEYS = 64u,
    VOS_STORAGE_MAX_BATCH = VOS_TREE_MAX_BATCH,
    VOS_STORAGE_BLKDEV_BLOCK_BYTES = 128u,
    VOS_STORAGE_BLKDEV_BLOCK_COUNT = 64u,
    VOS_STORAGE_BLKDEV_MEDIUM_BYTES =
        VOS_STORAGE_BLKDEV_BLOCK_BYTES * VOS_STORAGE_BLKDEV_BLOCK_COUNT,
    VOS_STORAGE_BLKDEV_HEADER_BYTES = 32u,
    VOS_STORAGE_BLKDEV_IMAGE_BYTES =
        VOS_STORAGE_BLKDEV_HEADER_BYTES + VOS_STORAGE_BLKDEV_MEDIUM_BYTES,
    VOS_STORAGE_BLKDEV_MAX_ARENA_NODES = 16u,
    VOS_STORAGE_BLKDEV_MAX_JOURNAL_FRAMES = 7u,
    VOS_STORAGE_BLKDEV_MAX_DEADLIST = 16u
};

enum vos_storage_op_kind {
    VOS_STORAGE_OP_INSERT = 1u,
    VOS_STORAGE_OP_INSERT_BATCH = 2u,
    VOS_STORAGE_OP_DELETE = 3u,
    VOS_STORAGE_OP_COMPACT = 4u
};

enum vos_storage_commit_mode {
    VOS_STORAGE_COMMIT_ROLLBACKABLE = 0u,
    VOS_STORAGE_COMMIT_FRESH = 1u
};

enum vos_storage_cut_point {
    VOS_STORAGE_CUT_NONE = 0u,
    VOS_STORAGE_CUT_AFTER_RESERVE = 1u,
    VOS_STORAGE_CUT_MID_PAYLOAD = 2u,
    VOS_STORAGE_CUT_BEFORE_CHECKPOINT = 3u,
    VOS_STORAGE_CUT_BEFORE_EPOCH_SEAL = 4u,
    VOS_STORAGE_CUT_BEFORE_ACK = 5u
};

struct vos_storage_nonce_record {
    uint64_t domain_id;
    uint64_t key_epoch;
    uint64_t reserved_generation;
    uint64_t max_generation;
    uint8_t mac[VOS_CRYPTO_DIGEST_BYTES];
};

struct vos_storage_block_auth {
    uint32_t valid;
    uint32_t kind;
    uint64_t generation;
    uint8_t tag[VOS_CRYPTO_TAG_BYTES];
};

struct vos_storage_journal_frame {
    uint32_t occupied;
    uint32_t frame_index;
    uint32_t kind;
    uint64_t tx_generation;
    uint64_t target_node_id;
    uint8_t ciphertext[VOS_STORAGE_MAX_BLOCK_BYTES];
    uint8_t tag[VOS_CRYPTO_TAG_BYTES];
    uint8_t content_digest[VOS_CRYPTO_DIGEST_BYTES];
    uint8_t frame_mac[VOS_CRYPTO_DIGEST_BYTES];
};

struct vos_storage_dead_entry {
    uint64_t node_id;
    uint64_t birth_generation;
};

struct vos_storage_checkpoint {
    uint32_t committed;
    uint32_t commit_mode;
    uint64_t domain_id;
    uint64_t key_epoch;
    uint64_t generation;
    uint64_t root;
    uint32_t height;
    uint64_t used;
    uint32_t frame_count;
    uint64_t fresh_region_id;
    uint64_t fresh_region_version;
    uint64_t sealed_epoch;
    uint8_t epoch_root[VOS_CRYPTO_DIGEST_BYTES];
    uint8_t root_digest[VOS_CRYPTO_DIGEST_BYTES];
    uint8_t fresh_state_digest[VOS_CRYPTO_DIGEST_BYTES];
    uint8_t payload_manifest_digest[VOS_CRYPTO_DIGEST_BYTES];
    uint32_t fresh_key_count;
    uint64_t fresh_keys[VOS_STORAGE_MAX_FRESH_KEYS];
    struct vos_storage_block_auth auth[VOS_STORAGE_MAX_ARENA_NODES];
    uint32_t snapshot_count;
    uint64_t snapshots[VOS_STORAGE_MAX_SNAPSHOTS];
    uint32_t dead_count;
    struct vos_storage_dead_entry deadlist[VOS_STORAGE_MAX_DEADLIST];
    uint8_t checkpoint_mac[VOS_CRYPTO_DIGEST_BYTES];
};

struct vos_storage_medium {
    struct vos_node_geometry geometry;
    struct vos_tree_limits limits;
    struct vos_storage_nonce_record nonce_record;
    uint8_t arena_ciphertext[VOS_STORAGE_MAX_ARENA_NODES * VOS_STORAGE_MAX_BLOCK_BYTES];
    uint32_t journal_count;
    uint32_t journal_reusable;
    struct vos_storage_journal_frame journal[VOS_STORAGE_MAX_JOURNAL_FRAMES];
    struct vos_storage_checkpoint checkpoint;
    uint32_t has_fallback;
    struct vos_storage_checkpoint fallback_checkpoint;
};

/* Trusted serialized durability seam; success means the supplied medium is
 * persistent. The callback may not mutate the store, crypto core or medium. */
typedef int (*vos_storage_persistor)(void *opaque, const struct vos_storage_medium *medium);

struct vos_storage_tx_spec {
    uint32_t op_kind;
    uint32_t commit_mode;
    uint64_t key;
    uint64_t value;
    size_t entry_count;
    struct vos_tree_entry entries[VOS_STORAGE_MAX_BATCH];
    uint64_t fresh_region_id;
    uint64_t fresh_region_version;
};

struct vos_storage_attempt {
    uint32_t reserved;
    uint32_t staged;
    uint64_t caller_domain;
    uint64_t generation;
    uint64_t base_used;
    struct vos_storage_tx_spec spec;
    struct vos_tree_update_result result;
    uint8_t staged_plaintext[VOS_STORAGE_MAX_ARENA_NODES * VOS_STORAGE_MAX_BLOCK_BYTES];
    uint64_t staged_generations[VOS_STORAGE_MAX_ARENA_NODES];
    struct vos_storage_block_auth staged_auth[VOS_STORAGE_MAX_ARENA_NODES];
    uint32_t staged_dead_count;
    struct vos_storage_dead_entry staged_deadlist[VOS_STORAGE_MAX_DEADLIST];
    uint32_t frame_count;
    struct vos_storage_journal_frame frames[VOS_STORAGE_MAX_JOURNAL_FRAMES];
};

struct vos_storage_store {
    uint32_t open;
    uint32_t crypto_slot;
    uint64_t domain_id;
    uint64_t key_epoch;
    uint64_t committed_generation;
    uint64_t committed_root;
    uint32_t committed_height;
    uint64_t committed_used;
    struct vos_storage_medium *medium;
    struct vos_crypto_core *crypto;
    vos_storage_persistor persist;
    void *persistence;
    uint8_t plain_arena[VOS_STORAGE_MAX_ARENA_NODES * VOS_STORAGE_MAX_BLOCK_BYTES];
    uint64_t plain_generations[VOS_STORAGE_MAX_ARENA_NODES];
    struct vos_storage_attempt attempt;
    uint32_t active_checkpoint_valid;
    uint32_t active_crypto_slot;
    const struct vos_storage_medium *active_medium;
    const struct vos_crypto_core *active_crypto;
    uint8_t active_checkpoint_bytes[sizeof(struct vos_storage_checkpoint)];
    uint64_t active_key_context;
    uint8_t active_geometry_bytes[sizeof(struct vos_node_geometry)];
    uint8_t active_limits_bytes[sizeof(struct vos_tree_limits)];
};

/* Private to the serialized storage owner. Admission authenticates membership
 * once; a changed checkpoint requires fresh admission. Mutable host bytes are
 * still authenticated at completion. Discard receipts when reopening/replacing
 * their store or crypto-core object. Never accept a caller-authored receipt. */
struct vos_storage_resident_receipt {
    const struct vos_storage_store *store;
    uint64_t key_context;
    struct vos_storage_checkpoint checkpoint;
    struct vos_resident_identity identity;
    size_t length;
    uint32_t valid;
};

int vos_storage_format(struct vos_storage_medium *medium,
                       struct vos_storage_store *store,
                       struct vos_crypto_core *crypto,
                       uint32_t crypto_slot,
                       uint64_t domain_id,
                       uint64_t key_epoch,
                       const struct vos_node_geometry *geometry,
                       const struct vos_tree_limits *limits,
                       uint64_t initial_generation,
                       uint64_t max_generation);

int vos_storage_reserve(struct vos_storage_store *store,
                        uint64_t caller_domain,
                        const struct vos_storage_tx_spec *spec);

int vos_storage_attach_persistence(struct vos_storage_store *store,
                                    vos_storage_persistor persist, void *opaque);

int vos_storage_stage(struct vos_storage_store *store,
                      uint64_t caller_domain);

int vos_storage_publish(struct vos_storage_store *store,
                        uint64_t caller_domain,
                        uint32_t cut_point,
                        uint64_t *acknowledged_generation);

int vos_storage_reopen(struct vos_storage_medium *medium,
                       struct vos_storage_store *store,
                       struct vos_crypto_core *crypto,
                       uint32_t crypto_slot,
                       uint64_t expected_domain_id);

int vos_storage_lookup(const struct vos_storage_store *store,
                       uint64_t caller_domain,
                       uint64_t key,
                       uint64_t *value_out);

int vos_storage_retain_snapshot(struct vos_storage_store *store,
                                uint64_t caller_domain,
                                uint64_t generation);

int vos_storage_object_digest(const struct vos_storage_store *store,
                              const uint8_t *bytes,
                              size_t length,
                              uint8_t digest_out[VOS_CRYPTO_DIGEST_BYTES]);

int vos_storage_bind_resident_identity(const struct vos_storage_store *store,
                                       uint64_t owner_id,
                                       uint64_t object_key,
                                       uint64_t version,
                                       uint32_t resident_kind,
                                       const uint8_t *bytes,
                                       size_t length,
                                       uint64_t *tree_value_out,
                                       struct vos_resident_identity *identity_out);

int vos_storage_verify_resident(void *verification,
                                const struct vos_resident_identity *identity,
                                const uint8_t *bytes,
                                size_t length);

int vos_storage_admit_resident(const struct vos_storage_store *store,
                               const struct vos_resident_identity *identity,
                               const uint8_t *bytes, size_t length,
                               struct vos_storage_resident_receipt *receipt);

int vos_storage_verify_admitted_resident(void *verification,
                                         const struct vos_resident_identity *identity,
                                         const uint8_t *bytes, size_t length);

int vos_storage_encode_blkdev_medium(
    const struct vos_storage_medium *medium,
    uint8_t medium_bytes[VOS_STORAGE_BLKDEV_MEDIUM_BYTES]);

int vos_storage_decode_blkdev_medium(
    const uint8_t medium_bytes[VOS_STORAGE_BLKDEV_MEDIUM_BYTES],
    struct vos_storage_medium *medium_out);

int vos_storage_encode_blkdev_image(
    const struct vos_storage_medium *medium,
    uint8_t image_bytes[VOS_STORAGE_BLKDEV_IMAGE_BYTES]);

int vos_storage_decode_blkdev_image(
    const uint8_t image_bytes[VOS_STORAGE_BLKDEV_IMAGE_BYTES],
    struct vos_storage_medium *medium_out);

int vos_storage_reopen_blkdev_image(
    const uint8_t image_bytes[VOS_STORAGE_BLKDEV_IMAGE_BYTES],
    struct vos_storage_medium *medium,
    struct vos_storage_store *store,
    struct vos_crypto_core *crypto,
    uint32_t crypto_slot,
    uint64_t expected_domain_id);

void vos_storage_apply_block_tear(
    uint8_t medium_bytes[VOS_STORAGE_BLKDEV_MEDIUM_BYTES],
    uint32_t block_index,
    const uint8_t old_block[VOS_STORAGE_BLKDEV_BLOCK_BYTES],
    const uint8_t new_block[VOS_STORAGE_BLKDEV_BLOCK_BYTES],
    const uint8_t tear_mask[VOS_STORAGE_BLKDEV_BLOCK_BYTES]);

#endif
