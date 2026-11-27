// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_BACKUP_H
#define VOS_BACKUP_H

#include <stddef.h>
#include <stdint.h>

#include "vos_crypto_core.h"

enum {
    VOS_BK_KEY_BYTES = VOS_CRYPTO_KEY_BYTES_256,
    VOS_BK_RECOVERY_HEX_CHARS = 64u,
    VOS_BK_NONCE_BYTES = VOS_CRYPTO_NONCE_BYTES,
    VOS_BK_TAG_BYTES = VOS_CRYPTO_TAG_BYTES,
    VOS_BK_DIGEST_BYTES = VOS_CRYPTO_DIGEST_BYTES,
    VOS_BK_MAGIC_BYTES = 8u,
    VOS_BK_VERSION = 1u,
    VOS_BK_DEFAULT_PROFILE_ID = 1u,
    VOS_BK_DEFAULT_CHUNK_SIZE = 64u,
    VOS_BK_MAX_CHUNK_SIZE = 256u,
    VOS_BK_MAX_REGIONS = 16u,
    VOS_BK_MAX_FRESH = 8u,
    VOS_BK_MAX_TOKENS = 16u,
    VOS_BK_MAX_CHUNKS = 64u,
    VOS_BK_MAX_MERKLE_DEPTH = 6u,
    VOS_BK_MAX_REGION_PAYLOAD = 2048u,
    VOS_BK_MAX_OBJECT_BYTES = 32768u,
    VOS_BK_ENVELOPE_PREFIX_BYTES = 40u,
    VOS_BK_REGION_WIRE_BYTES = 28u,
    VOS_BK_MANIFEST_FIXED_BYTES = 56u,
    VOS_BK_CHUNK_HEADER_BYTES = 20u
};

enum vos_bk_status {
    VOS_BK_OK = 0,
    VOS_BK_ERR_INVALID = -1,
    VOS_BK_ERR_AUTH = -2,
    VOS_BK_ERR_HEX_FORMAT = -3,
    VOS_BK_ERR_ENVELOPE = -4,
    VOS_BK_ERR_MANIFEST_TAG = -5,
    VOS_BK_ERR_MANIFEST_FORMAT = -6,
    VOS_BK_ERR_PROFILE_MISMATCH = -7,
    VOS_BK_ERR_UNSUPPORTED_SCHEMA = -8,
    VOS_BK_ERR_CHUNK_AUTH = -9,
    VOS_BK_ERR_MERKLE_PROOF = -10,
    VOS_BK_ERR_CHUNK_GEOMETRY = -11,
    VOS_BK_ERR_CAPACITY = -12,
    VOS_BK_ERR_STATE = -13,
    VOS_BK_ERR_FRESH_DENIED = -14,
    VOS_BK_ERR_ENTROPY = -15
};

enum vos_bk_region_kind {
    VOS_BK_KIND_ROLLBACKABLE = 0u,
    VOS_BK_KIND_FRESH = 1u,
    VOS_BK_KIND_CONSENT_STORE = 2u,
    VOS_BK_KIND_KEY_HANDLE = 3u,
    VOS_BK_KIND_CREDENTIAL_HANDLE = 4u,
    VOS_BK_KIND_SEALED_OBJECT = 5u
};

enum vos_bk_schema_class {
    VOS_BK_SCHEMA_DATA_ONLY = 0u,
    VOS_BK_SCHEMA_POINTER = 1u,
    VOS_BK_SCHEMA_CAPABILITY = 2u,
    VOS_BK_SCHEMA_KEY = 3u,
    VOS_BK_SCHEMA_NONCE_STATE = 4u,
    VOS_BK_SCHEMA_EXEC_STATE = 5u,
    VOS_BK_SCHEMA_CONN_STATE = 6u,
    VOS_BK_SCHEMA_SEALED_HANDLE = 7u,
    VOS_BK_SCHEMA_CREDENTIAL_HANDLE = 8u
};

enum vos_bk_fresh_class {
    VOS_BK_FRESH_SPENT_PAYMENT = 0u,
    VOS_BK_FRESH_CONSUMED_TOKEN = 1u,
    VOS_BK_FRESH_ONE_TIME_OP = 2u,
    VOS_BK_FRESH_ATTEMPT_COUNTER = 3u,
    VOS_BK_FRESH_REVOCATION_LIST = 4u,
    VOS_BK_FRESH_OTHER = 5u
};

enum vos_bk_restore_phase {
    VOS_BK_PHASE_IDLE = 0u,
    VOS_BK_PHASE_AUTHORIZED = 1u,
    VOS_BK_PHASE_MANIFEST_AUTH = 2u,
    VOS_BK_PHASE_PLANNED = 3u,
    VOS_BK_PHASE_STAGING = 4u,
    VOS_BK_PHASE_COMPLETE = 5u,
    VOS_BK_PHASE_COMMITTED = 6u,
    VOS_BK_PHASE_DISCARDED = 7u
};

enum vos_bk_plan_arm {
    VOS_BK_PLAN_SAME_SCHEMA = 0u,
    VOS_BK_PLAN_MIGRATE = 1u,
    VOS_BK_PLAN_DISCARD = 2u,
    VOS_BK_PLAN_UNSUPPORTED = 3u
};

enum vos_bk_operation {
    VOS_BK_OP_EXPORT = 1u,
    VOS_BK_OP_RESTORE = 2u
};

struct vos_bk_region_slot {
    uint32_t region_id;
    enum vos_bk_region_kind kind;
    enum vos_bk_schema_class schema_class;
    uint32_t schema_id;
    uint32_t schema_gen;
    uint32_t payload_len;
    uint8_t payload[VOS_BK_MAX_REGION_PAYLOAD];
};

struct vos_bk_fresh_slot {
    uint32_t region_id;
    enum vos_bk_fresh_class fresh_class;
    uint32_t has_initializer;
    uint32_t enrolled;
    uint32_t reconciled;
    uint64_t scope_epoch;
    uint32_t attempts_remaining;
    uint32_t spent_count;
    uint64_t spent_tokens[VOS_BK_MAX_TOKENS];
};

struct vos_bk_namespace {
    uint32_t profile_id;
    uint64_t generation;
    uint32_t region_count;
    struct vos_bk_region_slot regions[VOS_BK_MAX_REGIONS];
    uint32_t fresh_count;
    struct vos_bk_fresh_slot fresh[VOS_BK_MAX_FRESH];
    uint32_t consent_grant_count;
};

struct vos_bk_device_store {
    uint32_t active_idx;
    uint32_t staging_valid;
    uint32_t staging_idx;
    struct vos_bk_namespace slots[2];
    uint64_t write_counter;
    uint64_t rot_anti_rollback_floor;
    uint64_t continuing_platform_counter;
    uint64_t next_epoch;
};

struct vos_bk_consent {
    uint32_t valid;
    uint32_t consumed;
    uint32_t unlocked;
    uint32_t credential_verified;
    enum vos_bk_operation op;
    uint32_t source_profile;
    uint32_t target_profile;
    uint32_t allow_profile_mapping;
    uint32_t allow_discard;
};

struct vos_bk_schema_rule {
    uint32_t region_id;
    uint32_t source_schema_id;
    uint32_t source_schema_gen;
    enum vos_bk_plan_arm arm;
    uint32_t target_schema_id;
    uint32_t target_schema_gen;
    uint8_t migrate_xor_mask;
};

struct vos_bk_restore_policy {
    uint32_t expected_source_profile;
    uint32_t local_profile_id;
    uint32_t chunk_size;
    uint32_t allow_profile_mapping;
    uint32_t rule_count;
    struct vos_bk_schema_rule rules[VOS_BK_MAX_REGIONS];
};

struct vos_bk_region_desc {
    uint32_t region_id;
    uint32_t schema_id;
    uint32_t schema_gen;
    uint64_t payload_len;
    uint32_t first_chunk;
    uint32_t chunk_count;
};

struct vos_bk_manifest {
    uint64_t export_gen;
    uint32_t source_profile;
    uint32_t region_count;
    struct vos_bk_region_desc regions[VOS_BK_MAX_REGIONS];
    uint32_t chunk_size;
    uint32_t chunk_count;
    uint8_t merkle_root[VOS_BK_DIGEST_BYTES];
};

struct vos_bk_drbg {
    uint32_t healthy;
    uint64_t counter;
    uint8_t seed[VOS_BK_KEY_BYTES];
};

struct vos_bk_byte_sink {
    uint8_t *buf;
    size_t capacity;
    size_t length;
};

struct vos_bk_byte_source {
    const uint8_t *buf;
    size_t length;
};

struct vos_bk_restore_ctx {
    enum vos_bk_restore_phase phase;
    uint32_t staged_chunks;
    uint64_t total_extent;
    uint32_t merkle_depth;
    uint8_t manifest_key[VOS_BK_KEY_BYTES];
    uint8_t chunk_key[VOS_BK_KEY_BYTES];
    uint8_t catalog_ctx_digest[VOS_BK_DIGEST_BYTES];
    struct vos_bk_manifest manifest;
    enum vos_bk_plan_arm region_arms[VOS_BK_MAX_REGIONS];
    uint32_t region_target_schema_id[VOS_BK_MAX_REGIONS];
    uint32_t region_target_schema_gen[VOS_BK_MAX_REGIONS];
    uint8_t region_migrate_xor[VOS_BK_MAX_REGIONS];
    uint32_t staged_region_idx[VOS_BK_MAX_REGIONS];
    uint32_t region_bytes_written[VOS_BK_MAX_REGIONS];
};

void vos_bk_device_store_init(struct vos_bk_device_store *store,
                              uint32_t profile_id,
                              uint64_t generation,
                              uint64_t rot_floor,
                              uint64_t platform_counter);

const struct vos_bk_namespace *vos_bk_active_namespace(
    const struct vos_bk_device_store *store);

enum vos_bk_status vos_bk_add_region(struct vos_bk_device_store *store,
                                     uint32_t region_id,
                                     enum vos_bk_region_kind kind,
                                     enum vos_bk_schema_class schema_class,
                                     uint32_t schema_id,
                                     uint32_t schema_gen,
                                     const uint8_t *payload,
                                     uint32_t payload_len);

enum vos_bk_status vos_bk_add_fresh_slot(struct vos_bk_device_store *store,
                                         uint32_t region_id,
                                         enum vos_bk_fresh_class fresh_class,
                                         uint32_t has_initializer,
                                         uint32_t enrolled,
                                         uint32_t reconciled,
                                         uint64_t scope_epoch,
                                         uint32_t attempts_remaining,
                                         uint64_t spent_token);

enum vos_bk_status vos_bk_encode_recovery_secret(const uint8_t key[VOS_BK_KEY_BYTES],
                                                 char out_hex[VOS_BK_RECOVERY_HEX_CHARS + 1u]);

enum vos_bk_status vos_bk_decode_recovery_secret(const char *hex,
                                                 size_t hex_len,
                                                 uint8_t out_key[VOS_BK_KEY_BYTES]);

void vos_bk_derive_subkeys(const uint8_t object_key[VOS_BK_KEY_BYTES],
                           uint8_t manifest_key_out[VOS_BK_KEY_BYTES],
                           uint8_t chunk_key_out[VOS_BK_KEY_BYTES]);

void vos_bk_chunk_nonce(uint32_t chunk_index,
                        uint8_t nonce_out[VOS_BK_NONCE_BYTES]);

uint32_t vos_bk_merkle_depth(uint32_t chunk_count);

enum vos_bk_status vos_bk_drbg_draw_key(struct vos_bk_drbg *drbg,
                                        uint8_t key_out[VOS_BK_KEY_BYTES],
                                        uint8_t manifest_nonce_out[VOS_BK_NONCE_BYTES]);

enum vos_bk_status vos_bk_export(const struct vos_bk_device_store *store,
                                 struct vos_bk_consent *consent,
                                 struct vos_bk_drbg *drbg,
                                 uint32_t profile_id,
                                 uint32_t chunk_size,
                                 struct vos_bk_byte_sink *sink,
                                 uint8_t object_key_out[VOS_BK_KEY_BYTES]);

void vos_bk_restore_init(struct vos_bk_restore_ctx *ctx);

enum vos_bk_status vos_bk_restore_authorize(struct vos_bk_restore_ctx *ctx,
                                            struct vos_bk_consent *consent,
                                            uint32_t expected_source_profile,
                                            uint32_t local_profile_id,
                                            const uint8_t object_key[VOS_BK_KEY_BYTES]);

enum vos_bk_status vos_bk_restore_auth_manifest(struct vos_bk_restore_ctx *ctx,
                                                const struct vos_bk_byte_source *src,
                                                uint32_t expected_profile_id,
                                                uint32_t expected_chunk_size,
                                                size_t *chunks_offset_out);

enum vos_bk_status vos_bk_restore_plan(struct vos_bk_restore_ctx *ctx,
                                       struct vos_bk_device_store *store,
                                       const struct vos_bk_restore_policy *policy,
                                       const struct vos_bk_consent *consent);

enum vos_bk_status vos_bk_restore_stage_next_chunk(struct vos_bk_restore_ctx *ctx,
                                                   struct vos_bk_device_store *store,
                                                   const struct vos_bk_byte_source *src,
                                                   size_t *cursor_io);

enum vos_bk_status vos_bk_restore_complete(struct vos_bk_restore_ctx *ctx,
                                           const struct vos_bk_byte_source *src,
                                           size_t cursor);

enum vos_bk_status vos_bk_restore_commit(struct vos_bk_restore_ctx *ctx,
                                         struct vos_bk_device_store *store,
                                         struct vos_bk_consent *consent);

void vos_bk_restore_discard(struct vos_bk_restore_ctx *ctx,
                            struct vos_bk_device_store *store);

enum vos_bk_status vos_bk_restore_stream(struct vos_bk_device_store *store,
                                         struct vos_bk_consent *consent,
                                         const struct vos_bk_restore_policy *policy,
                                         const uint8_t object_key[VOS_BK_KEY_BYTES],
                                         const struct vos_bk_byte_source *src);

enum vos_bk_status vos_bk_fresh_check_token(const struct vos_bk_device_store *store,
                                            uint32_t region_id,
                                            uint64_t token);

enum vos_bk_status vos_bk_fresh_check_attempt(const struct vos_bk_device_store *store,
                                              uint32_t region_id);

#endif
