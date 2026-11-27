// SPDX-License-Identifier: Apache-2.0
#include "vos_storage_publish.h"

static void zero_bytes(uint8_t *dst, size_t length)
{
    if (dst == NULL) {
        return;
    }
    for (size_t i = 0u; i < length; ++i) {
        dst[i] = 0u;
    }
}

static void copy_bytes(uint8_t *dst, const uint8_t *src, size_t length)
{
    for (size_t i = 0u; i < length; ++i) {
        dst[i] = src[i];
    }
}

static int equal_bytes_ct(const uint8_t *a, const uint8_t *b, size_t length)
{
    uint8_t diff = 0u;
    for (size_t i = 0u; i < length; ++i) {
        diff |= (uint8_t)(a[i] ^ b[i]);
    }
    return diff == 0u;
}

static void put_le32(uint8_t *dst, uint32_t value)
{
    for (uint32_t i = 0u; i < 4u; ++i) {
        dst[i] = (uint8_t)(value >> (8u * i));
    }
}

static void put_le64(uint8_t *dst, uint64_t value)
{
    for (uint32_t i = 0u; i < 8u; ++i) {
        dst[i] = (uint8_t)(value >> (8u * i));
    }
}

static uint64_t get_le64(const uint8_t *src)
{
    uint64_t result = 0u;
    for (uint32_t i = 0u; i < 8u; ++i) {
        result |= (uint64_t)src[i] << (8u * i);
    }
    return result;
}

#define VOS_SP_COMMA ,

static void write_tag8(uint8_t *dst, const char tag[8])
{
    for (size_t i = 0u; i < 8u; ++i) {
        dst[i] = (uint8_t)tag[i];
    }
}

static int compare_untyped_keys(const uint64_t *a, const uint64_t *b)
{
    return (*a > *b) - (*a < *b);
}

static int valid_geometry_and_limits_common(const struct vos_node_geometry *geometry,
                                            const struct vos_tree_limits *limits,
                                            uint64_t max_arena_nodes,
                                            size_t entry_bytes,
                                            size_t max_block_bytes)
{
    return geometry != NULL && limits != NULL &&
           geometry->fan >= 2u && geometry->fan <= VOS_NODE_MAX_FAN &&
           geometry->arena_nodes >= 2u &&
           geometry->arena_nodes <= max_arena_nodes &&
           geometry->block_bytes >= VOS_NODE_HEADER_BYTES +
               (size_t)geometry->fan * entry_bytes &&
           geometry->block_bytes <= max_block_bytes &&
           limits->height <= limits->depth_limit &&
           limits->depth_limit <= VOS_TREE_MAX_DEPTH &&
           limits->visit_limit > 0u &&
           limits->visit_limit <= VOS_TREE_MAX_VISITS;
}

static int valid_geometry_and_limits(const struct vos_node_geometry *geometry,
                                     const struct vos_tree_limits *limits)
{
    return valid_geometry_and_limits_common(
        geometry, limits, VOS_STORAGE_MAX_ARENA_NODES, 16u,
        VOS_STORAGE_MAX_BLOCK_BYTES);
}

static void build_node_aad_common(const char tag[8],
                                  uint64_t domain_id, uint64_t key_epoch,
                                  uint64_t node_id, uint64_t generation,
                                  uint32_t kind, uint8_t aad[48])
{
    write_tag8(aad, tag);
    put_le64(aad + 8u, domain_id);
    put_le64(aad + 16u, key_epoch);
    put_le64(aad + 24u, node_id);
    put_le64(aad + 32u, generation);
    put_le32(aad + 40u, kind);
    put_le32(aad + 44u, 0u);
}

static int fresh_region_allows(uint32_t commit_mode,
                               uint64_t cp_region_id, uint64_t cp_region_version,
                               uint64_t spec_region_id, uint64_t spec_region_version)
{
    return !(commit_mode == VOS_STORAGE_COMMIT_FRESH &&
             cp_region_version != 0u &&
             (spec_region_id != cp_region_id || spec_region_version <= cp_region_version));
}

static int seal_node_block_crypto(const char aad_tag[8],
                                  const struct vos_crypto_core *crypto,
                                  uint32_t slot,
                                  uint64_t domain_id,
                                  uint64_t key_epoch,
                                  const struct vos_node_geometry *geometry,
                                  uint64_t node_id,
                                  uint64_t generation,
                                  uint32_t kind,
                                  const uint8_t *plain_block,
                                  uint8_t *cipher_out,
                                  uint8_t tag_out[VOS_CRYPTO_TAG_BYTES],
                                  uint8_t digest_out[VOS_CRYPTO_DIGEST_BYTES])
{
    const struct vos_node_nonce coords = {
        .domain_epoch = (uint32_t)key_epoch,
        .kind = kind,
        .node_id = node_id,
        .generation = generation
    };
    uint8_t nonce[VOS_CRYPTO_NONCE_BYTES];
    uint8_t aad[48];
    if (!vos_node_derive_nonce(geometry, &coords, nonce)) {
        return 0;
    }
    build_node_aad_common(aad_tag, domain_id, key_epoch, node_id, generation, kind, aad);
    return vos_crypto_core_seal(crypto, slot, nonce, aad, sizeof(aad),
                                plain_block, geometry->block_bytes,
                                cipher_out, tag_out) &&
           vos_crypto_core_keyed_digest(crypto, slot, plain_block,
                                        geometry->block_bytes, digest_out);
}

static int open_node_block_crypto(const char aad_tag[8],
                                  const struct vos_crypto_core *crypto,
                                  uint32_t slot,
                                  const struct vos_node_geometry *geometry,
                                  uint64_t domain_id,
                                  uint64_t key_epoch,
                                  uint64_t node_id,
                                  const struct vos_storage_block_auth *auth,
                                  const uint8_t *cipher_block,
                                  uint8_t *plain_out)
{
    if (auth == NULL || !auth->valid) {
        return 0;
    }
    const struct vos_node_nonce coords = {
        .domain_epoch = (uint32_t)key_epoch,
        .kind = auth->kind,
        .node_id = node_id,
        .generation = auth->generation
    };
    uint8_t nonce[VOS_CRYPTO_NONCE_BYTES];
    uint8_t aad[48];
    if (!vos_node_derive_nonce(geometry, &coords, nonce)) {
        return 0;
    }
    build_node_aad_common(aad_tag, domain_id, key_epoch, node_id,
                          auth->generation, auth->kind, aad);
    return vos_crypto_core_open(crypto, slot, nonce, aad, sizeof(aad),
                                cipher_block, geometry->block_bytes,
                                auth->tag, plain_out);
}

static int valid_domain_init_args(const void *medium, const void *store,
                                  const struct vos_crypto_core *crypto,
                                  uint32_t crypto_slot, uint64_t domain_id,
                                  uint64_t key_epoch, uint64_t initial_generation,
                                  uint64_t max_generation)
{
    return medium != NULL && store != NULL && crypto != NULL &&
           crypto_slot < VOS_CRYPTO_MAX_DOMAINS &&
           crypto->domains[crypto_slot].provisioned &&
           crypto->domains[crypto_slot].domain_id == domain_id &&
           crypto->domains[crypto_slot].key_epoch == key_epoch &&
           domain_id != 0u && key_epoch <= VOS_NODE_NONCE_MAX_DOMAIN &&
           initial_generation != 0u && initial_generation <= max_generation;
}

static int valid_domain_reopen_args(const void *medium, const void *store,
                                    const struct vos_crypto_core *crypto,
                                    uint32_t crypto_slot, uint64_t expected_domain_id)
{
    return medium != NULL && store != NULL && crypto != NULL &&
           crypto_slot < VOS_CRYPTO_MAX_DOMAINS &&
           crypto->domains[crypto_slot].provisioned &&
           crypto->domains[crypto_slot].domain_id == expected_domain_id;
}

static int verify_epoch_if_needed(const struct vos_crypto_core *crypto,
                                  uint32_t crypto_slot,
                                  uint32_t commit_mode,
                                  uint64_t sealed_epoch,
                                  uint64_t fresh_region_id,
                                  uint64_t fresh_region_version,
                                  const uint8_t fresh_state_digest[VOS_CRYPTO_DIGEST_BYTES],
                                  const uint8_t epoch_root[VOS_CRYPTO_DIGEST_BYTES])
{
    if ((crypto->epoch_sealed_mask & (1u << crypto_slot)) == 0u &&
        commit_mode != VOS_STORAGE_COMMIT_FRESH &&
        sealed_epoch == 0u) {
        return 1;
    }
    return vos_crypto_core_verify_epoch(crypto, crypto_slot, sealed_epoch,
                                        fresh_region_id, fresh_region_version,
                                        fresh_state_digest, epoch_root);
}

static int retire_dead_node_common(uint64_t id, uint64_t birth,
                                   uint64_t latest_snap, int has_snapshot,
                                   struct vos_storage_block_auth *staged_auth_entry,
                                   uint32_t *staged_dead_count,
                                   struct vos_storage_dead_entry staged_deadlist[VOS_STORAGE_MAX_DEADLIST])
{
    if (vos_tree_can_reclaim_node(birth, latest_snap, has_snapshot)) {
        zero_bytes((uint8_t *)staged_auth_entry, sizeof(*staged_auth_entry));
        return 1;
    }
    int already_dead = 0;
    for (uint32_t i = 0u; i < *staged_dead_count; ++i) {
        already_dead |= staged_deadlist[i].node_id == id;
    }
    if (!already_dead) {
        if (*staged_dead_count >= VOS_STORAGE_MAX_DEADLIST) {
            return 0;
        }
        staged_deadlist[*staged_dead_count].node_id = id;
        staged_deadlist[*staged_dead_count].birth_generation = birth;
        ++(*staged_dead_count);
    }
    return 1;
}

static uint64_t latest_snapshot_gen(const uint64_t *snapshots, uint32_t snapshot_count)
{
    uint64_t latest = 0u;
    for (uint32_t i = 0u; i < snapshot_count; ++i) {
        if (snapshots[i] > latest) {
            latest = snapshots[i];
        }
    }
    return latest;
}

static int checkpoint_retains_snapshot_common(const uint64_t *snapshots,
                                              uint32_t snapshot_count,
                                              uint64_t generation)
{
    for (uint32_t i = 0u; i < snapshot_count; ++i) {
        if (snapshots[i] == generation) {
            return 1;
        }
    }
    return 0;
}

static int verify_root_digest_common(const struct vos_crypto_core *crypto,
                                     uint32_t crypto_slot,
                                     const uint8_t *plain_root_block,
                                     size_t block_bytes,
                                     const uint8_t expected_root_digest[VOS_CRYPTO_DIGEST_BYTES])
{
    uint8_t actual_root_digest[VOS_CRYPTO_DIGEST_BYTES];
    return vos_crypto_core_keyed_digest(crypto, crypto_slot, plain_root_block,
                                        block_bytes, actual_root_digest) &&
           equal_bytes_ct(actual_root_digest, expected_root_digest,
                          VOS_CRYPTO_DIGEST_BYTES);
}

static int verify_frame_digest_match(const struct vos_crypto_core *crypto,
                                     uint32_t crypto_slot,
                                     const uint8_t *opened,
                                     size_t block_bytes,
                                     const uint8_t expected_digest[VOS_CRYPTO_DIGEST_BYTES])
{
    uint8_t digest[VOS_CRYPTO_DIGEST_BYTES];
    return vos_crypto_core_keyed_digest(crypto, crypto_slot, opened,
                                        block_bytes, digest) &&
           equal_bytes_ct(digest, expected_digest, VOS_CRYPTO_DIGEST_BYTES);
}

static int object_digest_common(uint32_t open, const struct vos_crypto_core *crypto,
                                uint32_t crypto_slot, const uint8_t *bytes,
                                size_t length, uint8_t digest_out[VOS_CRYPTO_DIGEST_BYTES])
{
    if (!open || crypto == NULL || digest_out == NULL || (length != 0u && bytes == NULL)) {
        return 0;
    }
    return vos_crypto_core_keyed_digest(crypto, crypto_slot, bytes, length, digest_out);
}

enum {
    MANIFEST_ITEM_BYTES = 4u + 4u + 8u + 8u + VOS_CRYPTO_TAG_BYTES + VOS_CRYPTO_DIGEST_BYTES,
    CHECKPOINT_HEADER_BYTES = 8u + 4u + 4u + 8u + 8u + 8u + 8u + 4u + 4u + 8u +
                              8u + 8u + 8u + 4u * VOS_CRYPTO_DIGEST_BYTES + 4u + 4u + 4u,
    CHECKPOINT_AUTH_BYTES = 4u + 4u + 8u + VOS_CRYPTO_TAG_BYTES
};

#define DEFINE_STORAGE_FRAME_OPS(PREFIX, FRAME_TYPE, MAX_FRAMES, MAX_BLOCK, FRAME_TAG, MANIFEST_TAG) \
enum { \
    PREFIX##FRAME_SERIAL_BYTES = 48u + VOS_CRYPTO_TAG_BYTES + VOS_CRYPTO_DIGEST_BYTES + (MAX_BLOCK), \
    PREFIX##MANIFEST_SERIAL_BYTES = 32u + (MAX_FRAMES) * MANIFEST_ITEM_BYTES \
}; \
static size_t serialize_##PREFIX##journal_frame( \
    uint64_t domain_id, uint64_t key_epoch, size_t block_bytes, \
    const struct FRAME_TYPE *frame, uint8_t buf[PREFIX##FRAME_SERIAL_BYTES]) \
{ \
    write_tag8(buf, FRAME_TAG); \
    put_le64(buf + 8u, domain_id); \
    put_le64(buf + 16u, key_epoch); \
    put_le64(buf + 24u, frame->tx_generation); \
    put_le32(buf + 32u, frame->frame_index); \
    put_le32(buf + 36u, frame->kind); \
    put_le64(buf + 40u, frame->target_node_id); \
    copy_bytes(buf + 48u, frame->tag, VOS_CRYPTO_TAG_BYTES); \
    copy_bytes(buf + 48u + VOS_CRYPTO_TAG_BYTES, \
               frame->content_digest, VOS_CRYPTO_DIGEST_BYTES); \
    copy_bytes(buf + 48u + VOS_CRYPTO_TAG_BYTES + VOS_CRYPTO_DIGEST_BYTES, \
               frame->ciphertext, block_bytes); \
    return 48u + VOS_CRYPTO_TAG_BYTES + VOS_CRYPTO_DIGEST_BYTES + block_bytes; \
} \
static int sign_##PREFIX##journal_frame( \
    const struct vos_crypto_core *crypto, uint32_t slot, uint64_t domain_id, \
    uint64_t key_epoch, size_t block_bytes, struct FRAME_TYPE *frame) \
{ \
    uint8_t buf[PREFIX##FRAME_SERIAL_BYTES]; \
    const size_t len = serialize_##PREFIX##journal_frame( \
        domain_id, key_epoch, block_bytes, frame, buf); \
    return vos_crypto_core_commit_mac(crypto, slot, buf, len, frame->frame_mac); \
} \
static int verify_##PREFIX##journal_frame( \
    const struct vos_crypto_core *crypto, uint32_t slot, uint64_t domain_id, \
    uint64_t key_epoch, size_t block_bytes, const struct FRAME_TYPE *frame) \
{ \
    uint8_t buf[PREFIX##FRAME_SERIAL_BYTES]; \
    if (frame == NULL || !frame->occupied) { \
        return 0; \
    } \
    const size_t len = serialize_##PREFIX##journal_frame( \
        domain_id, key_epoch, block_bytes, frame, buf); \
    return vos_crypto_core_verify_commit_mac(crypto, slot, buf, len, frame->frame_mac); \
} \
static int compute_##PREFIX##payload_manifest( \
    const struct vos_crypto_core *crypto, uint32_t slot, uint64_t domain_id, \
    uint64_t tx_generation, const struct FRAME_TYPE *frames, \
    uint32_t frame_count, uint8_t out[VOS_CRYPTO_DIGEST_BYTES]) \
{ \
    uint8_t buf[PREFIX##MANIFEST_SERIAL_BYTES]; \
    if (frame_count > (MAX_FRAMES)) { \
        return 0; \
    } \
    write_tag8(buf, MANIFEST_TAG); \
    put_le64(buf + 8u, domain_id); \
    put_le64(buf + 16u, tx_generation); \
    put_le32(buf + 24u, frame_count); \
    put_le32(buf + 28u, 0u); \
    size_t at = 32u; \
    for (uint32_t i = 0u; i < frame_count; ++i) { \
        put_le32(buf + at, frames[i].frame_index); \
        put_le32(buf + at + 4u, frames[i].kind); \
        put_le64(buf + at + 8u, frames[i].target_node_id); \
        put_le64(buf + at + 16u, frames[i].tx_generation); \
        copy_bytes(buf + at + 24u, frames[i].tag, VOS_CRYPTO_TAG_BYTES); \
        copy_bytes(buf + at + 24u + VOS_CRYPTO_TAG_BYTES, \
                   frames[i].content_digest, VOS_CRYPTO_DIGEST_BYTES); \
        at += MANIFEST_ITEM_BYTES; \
    } \
    return vos_crypto_core_commit_mac(crypto, slot, buf, at, out); \
}

#define DEFINE_STORAGE_CHECKPOINT_OPS(SERIAL_CONST, SERIAL_BYTES_EXPR, SERIALIZE_FN, SIGN_FN, VERIFY_FN, CP_TYPE, OPS_DECL, OPS_CALL, MAX_ARENA, MAX_FRAMES, CP_TAG, VALID_FRESH, KEY_SERIAL_STMT) \
enum { SERIAL_CONST = SERIAL_BYTES_EXPR }; \
static size_t SERIALIZE_FN(OPS_DECL const struct CP_TYPE *cp, uint8_t buf[SERIAL_CONST]) \
{ \
    write_tag8(buf, CP_TAG); \
    put_le32(buf + 8u, cp->committed); \
    put_le32(buf + 12u, cp->commit_mode); \
    put_le64(buf + 16u, cp->domain_id); \
    put_le64(buf + 24u, cp->key_epoch); \
    put_le64(buf + 32u, cp->generation); \
    put_le64(buf + 40u, cp->root); \
    put_le32(buf + 48u, cp->height); \
    put_le32(buf + 52u, cp->frame_count); \
    put_le64(buf + 56u, cp->used); \
    put_le64(buf + 64u, cp->fresh_region_id); \
    put_le64(buf + 72u, cp->fresh_region_version); \
    put_le64(buf + 80u, 0u); \
    size_t at = 88u; \
    zero_bytes(buf + at, VOS_CRYPTO_DIGEST_BYTES); \
    at += VOS_CRYPTO_DIGEST_BYTES; \
    copy_bytes(buf + at, cp->root_digest, VOS_CRYPTO_DIGEST_BYTES); \
    at += VOS_CRYPTO_DIGEST_BYTES; \
    copy_bytes(buf + at, cp->fresh_state_digest, VOS_CRYPTO_DIGEST_BYTES); \
    at += VOS_CRYPTO_DIGEST_BYTES; \
    copy_bytes(buf + at, cp->payload_manifest_digest, VOS_CRYPTO_DIGEST_BYTES); \
    at += VOS_CRYPTO_DIGEST_BYTES; \
    put_le32(buf + at, cp->snapshot_count); \
    put_le32(buf + at + 4u, cp->dead_count); \
    put_le32(buf + at + 8u, cp->fresh_key_count); \
    at += 12u; \
    for (uint32_t i = 0u; i < cp->fresh_key_count; ++i) { \
        KEY_SERIAL_STMT; \
    } \
    for (uint32_t i = 0u; i < cp->snapshot_count && i < VOS_STORAGE_MAX_SNAPSHOTS; ++i) { \
        put_le64(buf + at, cp->snapshots[i]); \
        at += 8u; \
    } \
    for (uint32_t i = 0u; i < cp->dead_count && i < VOS_STORAGE_MAX_DEADLIST; ++i) { \
        put_le64(buf + at, cp->deadlist[i].node_id); \
        put_le64(buf + at + 8u, cp->deadlist[i].birth_generation); \
        at += 16u; \
    } \
    for (uint64_t i = 0u; i < cp->used && i < (MAX_ARENA); ++i) { \
        put_le32(buf + at, cp->auth[(size_t)i].valid); \
        put_le32(buf + at + 4u, cp->auth[(size_t)i].kind); \
        put_le64(buf + at + 8u, cp->auth[(size_t)i].generation); \
        copy_bytes(buf + at + 16u, cp->auth[(size_t)i].tag, VOS_CRYPTO_TAG_BYTES); \
        at += CHECKPOINT_AUTH_BYTES; \
    } \
    return at; \
} \
static int SIGN_FN(OPS_DECL const struct vos_crypto_core *crypto, uint32_t slot, struct CP_TYPE *cp) \
{ \
    uint8_t buf[SERIAL_CONST]; \
    if (cp->used == 0u || cp->used > (MAX_ARENA) || !VALID_FRESH(cp) || \
        cp->snapshot_count > VOS_STORAGE_MAX_SNAPSHOTS || \
        cp->dead_count > VOS_STORAGE_MAX_DEADLIST || \
        cp->frame_count > (MAX_FRAMES)) { \
        return 0; \
    } \
    const size_t len = SERIALIZE_FN(OPS_CALL cp, buf); \
    if (len == 0u) { \
        return 0; \
    } \
    return vos_crypto_core_commit_mac(crypto, slot, buf, len, cp->checkpoint_mac); \
} \
static int VERIFY_FN(OPS_DECL const struct vos_crypto_core *crypto, uint32_t slot, \
                     uint64_t expected_domain, uint64_t expected_epoch, \
                     uint64_t max_arena_nodes, const struct CP_TYPE *cp) \
{ \
    uint8_t buf[SERIAL_CONST]; \
    if (cp == NULL || !cp->committed || cp->domain_id != expected_domain || \
        cp->key_epoch != expected_epoch || cp->generation == 0u || \
        cp->used == 0u || cp->used > max_arena_nodes || cp->used > (MAX_ARENA) || \
        cp->root >= cp->used || cp->frame_count > (MAX_FRAMES) || \
        !VALID_FRESH(cp) || cp->snapshot_count > VOS_STORAGE_MAX_SNAPSHOTS || \
        cp->dead_count > VOS_STORAGE_MAX_DEADLIST || \
        (cp->commit_mode != VOS_STORAGE_COMMIT_ROLLBACKABLE && \
         cp->commit_mode != VOS_STORAGE_COMMIT_FRESH)) { \
        return 0; \
    } \
    const size_t len = SERIALIZE_FN(OPS_CALL cp, buf); \
    if (len == 0u) { \
        return 0; \
    } \
    return vos_crypto_core_verify_commit_mac(crypto, slot, buf, len, cp->checkpoint_mac); \
}

#define DEFINE_STORAGE_ACTIVE_OPS(STORE_TYPE, CP_TYPE, RETAIN_FN, MATCHES_FN, PERSIST_FN, OPS_GUARD, VERIFY_CP_EXPR) \
static void RETAIN_FN(struct STORE_TYPE *store) \
{ \
    store->active_checkpoint_valid = 0u; \
    store->active_medium = store->medium; \
    store->active_crypto = store->crypto; \
    store->active_crypto_slot = store->crypto_slot; \
    copy_bytes(store->active_checkpoint_bytes, \
               (const uint8_t *)&store->medium->checkpoint, \
               sizeof(store->medium->checkpoint)); \
    store->active_key_context = store->crypto->domain_context[store->crypto_slot]; \
    copy_bytes(store->active_geometry_bytes, \
               (const uint8_t *)&store->medium->geometry, \
               sizeof(store->medium->geometry)); \
    copy_bytes(store->active_limits_bytes, \
               (const uint8_t *)&store->medium->limits, \
               sizeof(store->medium->limits)); \
    store->active_checkpoint_valid = 1u; \
} \
static int MATCHES_FN(const struct STORE_TYPE *store) \
{ \
    if (!store->active_checkpoint_valid || !(OPS_GUARD) || \
        store->active_medium != store->medium || \
        store->active_crypto != store->crypto || \
        store->active_crypto_slot != store->crypto_slot || \
        store->crypto_slot >= VOS_CRYPTO_MAX_DOMAINS) { \
        return 0; \
    } \
    const struct vos_crypto_domain_slot *slot = &store->crypto->domains[store->crypto_slot]; \
    const struct CP_TYPE *cp = &store->medium->checkpoint; \
    return slot->provisioned && slot->domain_id == store->domain_id && \
           slot->key_epoch == store->key_epoch && \
           cp->domain_id == store->domain_id && cp->key_epoch == store->key_epoch && \
           cp->generation == store->committed_generation && \
           cp->root == store->committed_root && cp->height == store->committed_height && \
           cp->used == store->committed_used && \
           equal_bytes_ct(store->active_checkpoint_bytes, (const uint8_t *)cp, sizeof(*cp)) && \
           equal_bytes_ct(store->active_geometry_bytes, \
                          (const uint8_t *)&store->medium->geometry, \
                          sizeof(store->medium->geometry)) && \
           equal_bytes_ct(store->active_limits_bytes, \
                          (const uint8_t *)&store->medium->limits, \
                          sizeof(store->medium->limits)) && \
           (store->active_key_context == store->crypto->domain_context[store->crypto_slot] || \
            (VERIFY_CP_EXPR)); \
} \
static int PERSIST_FN(struct STORE_TYPE *store) \
{ \
    if (store->persist != NULL && !store->persist(store->persistence, store->medium)) { \
        store->open = 0u; \
        return 0; \
    } \
    return 1; \
}

#define DEFINE_STORAGE_FORMAT_FN(FN_NAME, MEDIUM_TYPE, STORE_TYPE, CP_TYPE, NODE_TYPE, OPS_PARAM_DECL, EXTRA_CHECK, POST_ZERO_STMT, VALID_GEOM, ENCODE_ROOT, SEAL_BLOCK, MANIFEST_FN, SIGN_CP, RETAIN_ACTIVE) \
int FN_NAME(struct MEDIUM_TYPE *medium, struct STORE_TYPE *store, \
            struct vos_crypto_core *crypto, uint32_t crypto_slot, \
            uint64_t domain_id, uint64_t key_epoch, \
            const struct vos_node_geometry *geometry, \
            const struct vos_tree_limits *limits, \
            uint64_t initial_generation, uint64_t max_generation \
            OPS_PARAM_DECL) \
{ \
    struct NODE_TYPE root_node = {0}; \
    uint32_t root_kind = 0u; \
    if (!valid_domain_init_args(medium, store, crypto, crypto_slot, domain_id, \
                                key_epoch, initial_generation, max_generation) || \
        (EXTRA_CHECK) || !VALID_GEOM(geometry, limits)) { \
        return 0; \
    } \
    zero_bytes((uint8_t *)medium, sizeof(*medium)); \
    zero_bytes((uint8_t *)store, sizeof(*store)); \
    POST_ZERO_STMT; \
    medium->geometry = *geometry; \
    medium->limits = *limits; \
    medium->limits.height = 0u; \
    medium->nonce_record.domain_id = domain_id; \
    medium->nonce_record.key_epoch = key_epoch; \
    medium->nonce_record.reserved_generation = initial_generation; \
    medium->nonce_record.max_generation = max_generation; \
    if (!sign_nonce_record(crypto, crypto_slot, &medium->nonce_record)) { \
        return 0; \
    } \
    root_node.kind = VOS_NODE_LEAF; \
    root_node.count = 0u; \
    root_node.node_id = 0u; \
    root_node.generation = initial_generation; \
    if (!ENCODE_ROOT) { \
        return 0; \
    } \
    store->plain_generations[0] = initial_generation; \
    uint8_t root_tag[VOS_CRYPTO_TAG_BYTES]; \
    uint8_t root_digest[VOS_CRYPTO_DIGEST_BYTES]; \
    if (!SEAL_BLOCK) { \
        return 0; \
    } \
    struct CP_TYPE *cp = &medium->checkpoint; \
    cp->committed = 1u; \
    cp->commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE; \
    cp->domain_id = domain_id; \
    cp->key_epoch = key_epoch; \
    cp->generation = initial_generation; \
    cp->root = 0u; \
    cp->height = 0u; \
    cp->used = 1u; \
    cp->frame_count = 0u; \
    copy_bytes(cp->root_digest, root_digest, VOS_CRYPTO_DIGEST_BYTES); \
    if (!MANIFEST_FN(crypto, crypto_slot, domain_id, initial_generation, \
                     NULL, 0u, cp->payload_manifest_digest)) { \
        return 0; \
    } \
    cp->auth[0].valid = 1u; \
    cp->auth[0].kind = root_kind; \
    cp->auth[0].generation = initial_generation; \
    copy_bytes(cp->auth[0].tag, root_tag, VOS_CRYPTO_TAG_BYTES); \
    if (!SIGN_CP) { \
        return 0; \
    } \
    medium->journal_reusable = 1u; \
    medium->fallback_checkpoint = *cp; \
    medium->has_fallback = 1u; \
    store->open = 1u; \
    store->crypto_slot = crypto_slot; \
    store->domain_id = domain_id; \
    store->key_epoch = key_epoch; \
    store->committed_generation = initial_generation; \
    store->committed_root = 0u; \
    store->committed_height = 0u; \
    store->committed_used = 1u; \
    store->medium = medium; \
    store->crypto = crypto; \
    RETAIN_ACTIVE(store); \
    return 1; \
}

#define DEFINE_STORAGE_RESERVE_FN(FN_NAME, STORE_TYPE, MEDIUM_TYPE, SPEC_TYPE, VALID_SPEC, MATCHES_ACTIVE, FRESH_ALLOWED, ALLOW_REUSE, PERSIST_FN) \
int FN_NAME(struct STORE_TYPE *store, uint64_t caller_domain, \
            const struct SPEC_TYPE *spec) \
{ \
    if (store == NULL || !store->open || store->medium == NULL || \
        store->crypto == NULL || caller_domain != store->domain_id || \
        store->attempt.reserved || !VALID_SPEC) { \
        return 0; \
    } \
    struct MEDIUM_TYPE *medium = store->medium; \
    if (!MATCHES_ACTIVE(store) || !FRESH_ALLOWED(&medium->checkpoint, spec)) { \
        return 0; \
    } \
    if (!verify_nonce_record(store->crypto, store->crypto_slot, \
                             store->domain_id, store->key_epoch, \
                             &medium->nonce_record) || \
        medium->nonce_record.reserved_generation < store->committed_generation || \
        medium->nonce_record.reserved_generation >= medium->nonce_record.max_generation) { \
        return 0; \
    } \
    if (spec->op_kind != VOS_STORAGE_OP_COMPACT && \
        store->committed_used >= medium->geometry.arena_nodes) { \
        int reusable = 0; \
        if (ALLOW_REUSE) { \
            for (uint64_t id = 0u; id < store->committed_used; ++id) { \
                reusable |= !medium->checkpoint.auth[(size_t)id].valid; \
            } \
        } \
        if (!reusable) { \
            return 0; \
        } \
    } \
    if (spec->commit_mode == VOS_STORAGE_COMMIT_FRESH && \
        store->crypto->rot_epoch_counter >= store->crypto->rot_epoch_ceiling) { \
        return 0; \
    } \
    /* Persist key-wide nonce reservation advance before sealing any candidate. */ \
    const uint64_t next_gen = medium->nonce_record.reserved_generation + 1u; \
    struct vos_storage_nonce_record next_nonce = medium->nonce_record; \
    next_nonce.reserved_generation = next_gen; \
    if (!sign_nonce_record(store->crypto, store->crypto_slot, &next_nonce)) { \
        return 0; \
    } \
    medium->nonce_record = next_nonce; \
    if (!PERSIST_FN(store)) { \
        return 0; \
    } \
    zero_bytes((uint8_t *)&store->attempt, sizeof(store->attempt)); \
    store->attempt.reserved = 1u; \
    store->attempt.staged = 0u; \
    store->attempt.caller_domain = caller_domain; \
    store->attempt.generation = next_gen; \
    store->attempt.base_used = store->committed_used; \
    store->attempt.spec = *spec; \
    return 1; \
}

#define DEFINE_STORAGE_STAGE_HELPERS(TAG, STORE_TYPE, MEDIUM_TYPE, ATT_TYPE, FRAME_TYPE, NODE_TYPE, MAX_FRAMES, MAX_BLOCK, OPS_GUARD, VERIFY_CP_EXPR, SEAL_BLOCK_EXPR, SIGN_FRAME_FN, VERIFY_FRAME_FN, OPEN_BLOCK_EXPR) \
static int stage_##TAG##_prepare(struct STORE_TYPE *store, uint64_t caller_domain, \
                                 struct vos_tree_arena *arena_out, \
                                 struct vos_tree_limits *limits_out) \
{ \
    if (store == NULL || !store->open || store->medium == NULL || \
        store->crypto == NULL || !(OPS_GUARD) || \
        caller_domain != store->domain_id || \
        !store->attempt.reserved || store->attempt.staged || \
        store->attempt.caller_domain != caller_domain || \
        store->attempt.generation != store->medium->nonce_record.reserved_generation) { \
        return 0; \
    } \
    struct MEDIUM_TYPE *medium = store->medium; \
    struct ATT_TYPE *att = &store->attempt; \
    if (!(VERIFY_CP_EXPR) || \
        medium->checkpoint.generation != store->committed_generation || \
        medium->checkpoint.root != store->committed_root) { \
        return 0; \
    } \
    const size_t block_bytes = medium->geometry.block_bytes; \
    const size_t arena_bytes = (size_t)medium->geometry.arena_nodes * block_bytes; \
    copy_bytes(att->staged_plaintext, store->plain_arena, arena_bytes); \
    for (uint32_t i = 0u; i < medium->geometry.arena_nodes; ++i) { \
        att->staged_generations[i] = store->plain_generations[i]; \
        att->staged_auth[i] = medium->checkpoint.auth[i]; \
    } \
    att->staged_dead_count = medium->checkpoint.dead_count; \
    for (uint32_t i = 0u; i < medium->checkpoint.dead_count; ++i) { \
        att->staged_deadlist[i] = medium->checkpoint.deadlist[i]; \
    } \
    *limits_out = medium->limits; \
    limits_out->height = store->committed_height; \
    zero_bytes((uint8_t *)arena_out, sizeof(*arena_out)); \
    arena_out->geometry = medium->geometry; \
    arena_out->used = store->committed_used; \
    arena_out->bytes = att->staged_plaintext; \
    arena_out->length = arena_bytes; \
    arena_out->generations = att->staged_generations; \
    arena_out->generation_count = medium->geometry.arena_nodes; \
    return 1; \
} \
static int seal_##TAG##_staged_frames(struct STORE_TYPE *store) \
{ \
    const struct MEDIUM_TYPE *medium = store->medium; \
    struct ATT_TYPE *att = &store->attempt; \
    const size_t block_bytes = medium->geometry.block_bytes; \
    uint32_t f_idx = 0u; \
    for (uint64_t id = 0u; id < att->result.used; ++id) { \
        if (att->staged_generations[(size_t)id] != att->generation) { \
            continue; \
        } \
        if (f_idx >= (MAX_FRAMES)) { \
            return 0; \
        } \
        struct FRAME_TYPE *frame = &att->frames[f_idx]; \
        uint32_t kind = 0u; \
        zero_bytes((uint8_t *)frame, sizeof(*frame)); \
        if (!(SEAL_BLOCK_EXPR)) { \
            return 0; \
        } \
        frame->occupied = 1u; \
        frame->frame_index = f_idx; \
        frame->kind = kind; \
        frame->tx_generation = att->generation; \
        frame->target_node_id = id; \
        if (!SIGN_FRAME_FN(store->crypto, store->crypto_slot, store->domain_id, \
                           store->key_epoch, block_bytes, frame)) { \
            return 0; \
        } \
        att->staged_auth[(size_t)id].valid = 1u; \
        att->staged_auth[(size_t)id].kind = kind; \
        att->staged_auth[(size_t)id].generation = att->generation; \
        copy_bytes(att->staged_auth[(size_t)id].tag, frame->tag, VOS_CRYPTO_TAG_BYTES); \
        ++f_idx; \
    } \
    att->frame_count = f_idx; \
    att->staged = 1u; \
    return 1; \
} \
static int verify_##TAG##_staged_frames(const struct STORE_TYPE *store, \
                                        struct vos_tree_image *candidate_out, \
                                        struct vos_tree_limits *limits_out) \
{ \
    const struct MEDIUM_TYPE *medium = store->medium; \
    const struct ATT_TYPE *att = &store->attempt; \
    const size_t block_bytes = medium->geometry.block_bytes; \
    if (!(OPS_GUARD) || !att->reserved || !att->staged || \
        att->frame_count == 0u || att->frame_count > (MAX_FRAMES) || \
        att->result.used == 0u || att->result.used > medium->geometry.arena_nodes || \
        att->result.root >= att->result.used) { \
        return 0; \
    } \
    for (uint32_t i = 0u; i < att->frame_count; ++i) { \
        const struct FRAME_TYPE *frame = &att->frames[i]; \
        uint8_t opened[MAX_BLOCK]; \
        struct NODE_TYPE decoded = {0}; \
        if (frame->frame_index != i || \
            frame->tx_generation != att->generation || \
            frame->target_node_id >= att->result.used || \
            !VERIFY_FRAME_FN(store->crypto, store->crypto_slot, store->domain_id, \
                             store->key_epoch, block_bytes, frame) || \
            !(OPEN_BLOCK_EXPR) || \
            !equal_bytes_ct(opened, att->staged_plaintext + \
                            (size_t)frame->target_node_id * block_bytes, block_bytes) || \
            !verify_frame_digest_match(store->crypto, store->crypto_slot, \
                                       opened, block_bytes, frame->content_digest)) { \
            return 0; \
        } \
    } \
    zero_bytes((uint8_t *)candidate_out, sizeof(*candidate_out)); \
    candidate_out->geometry = medium->geometry; \
    candidate_out->geometry.arena_nodes = att->result.used; \
    candidate_out->bytes = att->staged_plaintext; \
    candidate_out->length = (size_t)att->result.used * block_bytes; \
    candidate_out->generations = att->staged_generations; \
    candidate_out->generation_count = (size_t)att->result.used; \
    *limits_out = medium->limits; \
    limits_out->height = att->result.height; \
    return 1; \
}

#define DEFINE_STORAGE_PUBLISH_FN(FN_NAME, STORE_TYPE, MEDIUM_TYPE, ATT_TYPE, CP_TYPE, VERIFY_CANDIDATE, INHERIT_FRESH, MANIFEST_FN, SIGN_CP, PERSIST_FN, RETAIN_ACTIVE) \
int FN_NAME(struct STORE_TYPE *store, uint64_t caller_domain, \
            uint32_t cut_point, uint64_t *acknowledged_generation) \
{ \
    if (store == NULL || !store->open || store->medium == NULL || \
        store->crypto == NULL || acknowledged_generation == NULL || \
        caller_domain != store->domain_id || !store->attempt.reserved || \
        store->attempt.caller_domain != caller_domain || \
        store->attempt.generation != store->medium->nonce_record.reserved_generation) { \
        return 0; \
    } \
    if (cut_point == VOS_STORAGE_CUT_AFTER_RESERVE || !VERIFY_CANDIDATE(store)) { \
        return 0; \
    } \
    struct MEDIUM_TYPE *medium = store->medium; \
    struct ATT_TYPE *att = &store->attempt; \
    const size_t block_bytes = medium->geometry.block_bytes; \
    /* Stage journal frames onto the medium before checkpoint publication. */ \
    medium->journal_reusable = 0u; \
    if (cut_point == VOS_STORAGE_CUT_MID_PAYLOAD) { \
        const uint32_t partial = (att->frame_count > 1u) ? (att->frame_count / 2u) : 1u; \
        for (uint32_t i = 0u; i < partial; ++i) { \
            medium->journal[i] = att->frames[i]; \
        } \
        if (att->frame_count == 1u) { \
            medium->journal[0].frame_mac[0] ^= 0xffu; \
        } \
        medium->journal_count = partial; \
        (void)PERSIST_FN(store); \
        return 0; \
    } \
    for (uint32_t i = 0u; i < att->frame_count; ++i) { \
        medium->journal[i] = att->frames[i]; \
    } \
    medium->journal_count = att->frame_count; \
    if (!PERSIST_FN(store) || cut_point == VOS_STORAGE_CUT_BEFORE_CHECKPOINT) { \
        return 0; \
    } \
    struct CP_TYPE next_cp = {0}; \
    next_cp.committed = 1u; \
    next_cp.commit_mode = att->spec.commit_mode; \
    next_cp.domain_id = store->domain_id; \
    next_cp.key_epoch = store->key_epoch; \
    next_cp.generation = att->generation; \
    next_cp.root = att->result.root; \
    next_cp.height = att->result.height; \
    next_cp.used = att->result.used; \
    next_cp.frame_count = att->frame_count; \
    next_cp.snapshot_count = medium->checkpoint.snapshot_count; \
    for (uint32_t i = 0u; i < next_cp.snapshot_count; ++i) { \
        next_cp.snapshots[i] = medium->checkpoint.snapshots[i]; \
    } \
    if (!INHERIT_FRESH(&next_cp, &medium->checkpoint, &att->spec)) { \
        return 0; \
    } \
    next_cp.dead_count = att->staged_dead_count; \
    for (uint32_t i = 0u; i < next_cp.dead_count; ++i) { \
        next_cp.deadlist[i] = att->staged_deadlist[i]; \
    } \
    for (uint64_t i = 0u; i < next_cp.used; ++i) { \
        next_cp.auth[(size_t)i] = att->staged_auth[(size_t)i]; \
    } \
    if (!vos_crypto_core_keyed_digest( \
            store->crypto, store->crypto_slot, \
            att->staged_plaintext + (size_t)next_cp.root * block_bytes, \
            block_bytes, next_cp.root_digest) || \
        !MANIFEST_FN(store->crypto, store->crypto_slot, store->domain_id, \
                     att->generation, att->frames, att->frame_count, \
                     next_cp.payload_manifest_digest)) { \
        return 0; \
    } \
    if (next_cp.commit_mode == VOS_STORAGE_COMMIT_FRESH) { \
        copy_bytes(next_cp.fresh_state_digest, next_cp.root_digest, VOS_CRYPTO_DIGEST_BYTES); \
        next_cp.fresh_region_id = att->spec.fresh_region_id; \
        next_cp.fresh_region_version = att->spec.fresh_region_version; \
        next_cp.sealed_epoch = 0u; \
        zero_bytes(next_cp.epoch_root, VOS_CRYPTO_DIGEST_BYTES); \
        if (!SIGN_CP) { \
            return 0; \
        } \
        medium->fallback_checkpoint = medium->checkpoint; \
        medium->has_fallback = 1u; \
        medium->checkpoint = next_cp; \
        if (!PERSIST_FN(store)) return 0; \
        if (cut_point == VOS_STORAGE_CUT_BEFORE_EPOCH_SEAL) { \
            return 0; \
        } \
        if (!vos_crypto_core_seal_epoch(store->crypto, store->crypto_slot, \
                                        next_cp.fresh_region_id, \
                                        next_cp.fresh_region_version, \
                                        next_cp.fresh_state_digest, \
                                        &next_cp.sealed_epoch, \
                                        next_cp.epoch_root) || \
            !SIGN_CP) { \
            return 0; \
        } \
        medium->checkpoint = next_cp; \
    } else { \
        copy_bytes(next_cp.fresh_state_digest, medium->checkpoint.fresh_state_digest, \
                   VOS_CRYPTO_DIGEST_BYTES); \
        next_cp.fresh_region_id = medium->checkpoint.fresh_region_id; \
        next_cp.fresh_region_version = medium->checkpoint.fresh_region_version; \
        next_cp.sealed_epoch = medium->checkpoint.sealed_epoch; \
        copy_bytes(next_cp.epoch_root, medium->checkpoint.epoch_root, \
                   VOS_CRYPTO_DIGEST_BYTES); \
        if (!SIGN_CP) { \
            return 0; \
        } \
        medium->fallback_checkpoint = medium->checkpoint; \
        medium->has_fallback = 1u; \
        medium->checkpoint = next_cp; \
    } \
    if (!PERSIST_FN(store) || cut_point == VOS_STORAGE_CUT_BEFORE_ACK) { \
        return 0; \
    } \
    for (uint32_t i = 0u; i < att->frame_count; ++i) { \
        const uint64_t id = att->frames[i].target_node_id; \
        copy_bytes(medium->arena_ciphertext + (size_t)id * block_bytes, \
                   att->frames[i].ciphertext, block_bytes); \
    } \
    medium->journal_reusable = 1u; \
    medium->fallback_checkpoint = next_cp; \
    medium->has_fallback = 1u; \
    if (!PERSIST_FN(store)) { \
        return 0; \
    } \
    copy_bytes(store->plain_arena, att->staged_plaintext, \
               (size_t)medium->geometry.arena_nodes * block_bytes); \
    for (uint32_t i = 0u; i < medium->geometry.arena_nodes; ++i) { \
        store->plain_generations[i] = att->staged_generations[i]; \
    } \
    store->committed_generation = next_cp.generation; \
    store->committed_root = next_cp.root; \
    store->committed_height = next_cp.height; \
    store->committed_used = next_cp.used; \
    RETAIN_ACTIVE(store); \
    zero_bytes((uint8_t *)&store->attempt, sizeof(store->attempt)); \
    *acknowledged_generation = next_cp.generation; \
    return 1; \
}

#define DEFINE_STORAGE_REOPEN_FN(FN_NAME, MEDIUM_TYPE, STORE_TYPE, CP_TYPE, FRAME_TYPE, NODE_TYPE, MAX_FRAMES, MAX_BLOCK, OPS_PARAM_DECL, EXTRA_CHECK, VALID_GEOM, POST_ZERO_STMT, VERIFY_CP_FN, OPS_PFX, MANIFEST_FN, VERIFY_FRAME_FN, OPEN_BLOCK_FN, TREE_SANITY_EXPR, RETAIN_ACTIVE) \
int FN_NAME(struct MEDIUM_TYPE *medium, struct STORE_TYPE *store, \
            struct vos_crypto_core *crypto, uint32_t crypto_slot, \
            uint64_t expected_domain_id OPS_PARAM_DECL) \
{ \
    if (!valid_domain_reopen_args(medium, store, crypto, crypto_slot, \
                                  expected_domain_id) || \
        (EXTRA_CHECK) || !VALID_GEOM(&medium->geometry, &medium->limits)) { \
        return 0; \
    } \
    /* Discard all volatile state before reading the persistent medium. */ \
    zero_bytes((uint8_t *)store, sizeof(*store)); \
    POST_ZERO_STMT; \
    const uint64_t key_epoch = crypto->domains[crypto_slot].key_epoch; \
    if (!verify_nonce_record(crypto, crypto_slot, expected_domain_id, \
                             key_epoch, &medium->nonce_record)) { \
        return 0; \
    } \
    const int primary_valid = VERIFY_CP_FN( \
        OPS_PFX crypto, crypto_slot, expected_domain_id, key_epoch, \
        medium->geometry.arena_nodes, &medium->checkpoint); \
    const int fallback_valid = medium->has_fallback && VERIFY_CP_FN( \
        OPS_PFX crypto, crypto_slot, expected_domain_id, key_epoch, \
        medium->geometry.arena_nodes, &medium->fallback_checkpoint); \
    if (!primary_valid && !fallback_valid) { \
        return 0; \
    } \
    if (!primary_valid || (fallback_valid && \
        medium->fallback_checkpoint.generation > medium->checkpoint.generation)) { \
        medium->checkpoint = medium->fallback_checkpoint; \
    } \
    /* The checkpoint authenticates state; epoch evidence is derived from RoT. */ \
    struct CP_TYPE *selected = &medium->checkpoint; \
    if (selected->commit_mode == VOS_STORAGE_COMMIT_FRESH || \
        selected->fresh_region_version != 0u || \
        (crypto->epoch_sealed_mask & (1u << crypto_slot)) != 0u) { \
        const struct vos_crypto_epoch_seal *seal = &crypto->sealed_epochs[crypto_slot]; \
        if (!vos_crypto_core_verify_epoch(crypto, crypto_slot, seal->epoch, \
                                          selected->fresh_region_id, \
                                          selected->fresh_region_version, \
                                          selected->fresh_state_digest, seal->root)) { \
            if (selected->commit_mode != VOS_STORAGE_COMMIT_FRESH || !fallback_valid || \
                medium->fallback_checkpoint.generation >= selected->generation) { \
                return 0; \
            } \
            medium->checkpoint = medium->fallback_checkpoint; \
            selected = &medium->checkpoint; \
            medium->journal_count = 0u; \
            medium->journal_reusable = 1u; \
            zero_bytes((uint8_t *)medium->journal, sizeof(medium->journal)); \
        } \
        if (selected->fresh_region_version != 0u) { \
            if (!vos_crypto_core_verify_epoch(crypto, crypto_slot, seal->epoch, \
                                              selected->fresh_region_id, \
                                              selected->fresh_region_version, \
                                              selected->fresh_state_digest, seal->root)) { \
                return 0; \
            } \
            selected->sealed_epoch = seal->epoch; \
            copy_bytes(selected->epoch_root, seal->root, VOS_CRYPTO_DIGEST_BYTES); \
        } \
    } \
    const struct CP_TYPE *cp = &medium->checkpoint; \
    if (medium->nonce_record.reserved_generation < cp->generation) { \
        return 0; \
    } \
    if (!verify_epoch_if_needed(crypto, crypto_slot, cp->commit_mode, \
                                cp->sealed_epoch, cp->fresh_region_id, \
                                cp->fresh_region_version, \
                                cp->fresh_state_digest, cp->epoch_root)) { \
        return 0; \
    } \
    const size_t block_bytes = medium->geometry.block_bytes; \
    /* R-10-002a bounded prefix redo recovery. */ \
    if (medium->journal_count > 0u && !medium->journal_reusable) { \
        if (medium->journal_count > (MAX_FRAMES)) { \
            return 0; \
        } \
        const uint64_t j_gen = medium->journal[0].tx_generation; \
        if (j_gen == cp->generation) { \
            if (medium->journal_count != cp->frame_count) { \
                return 0; \
            } \
            uint8_t manifest_digest[VOS_CRYPTO_DIGEST_BYTES]; \
            if (!MANIFEST_FN(crypto, crypto_slot, expected_domain_id, cp->generation, \
                             medium->journal, medium->journal_count, manifest_digest) || \
                !equal_bytes_ct(manifest_digest, cp->payload_manifest_digest, \
                                VOS_CRYPTO_DIGEST_BYTES)) { \
                return 0; \
            } \
            for (uint32_t i = 0u; i < medium->journal_count; ++i) { \
                const struct FRAME_TYPE *frame = &medium->journal[i]; \
                uint8_t opened[MAX_BLOCK]; \
                struct NODE_TYPE decoded = {0}; \
                if (frame->frame_index != i || \
                    frame->tx_generation != cp->generation || \
                    frame->target_node_id >= cp->used || \
                    !VERIFY_FRAME_FN(crypto, crypto_slot, expected_domain_id, \
                                     key_epoch, block_bytes, frame) || \
                    !equal_bytes_ct(frame->tag, \
                                    cp->auth[(size_t)frame->target_node_id].tag, \
                                    VOS_CRYPTO_TAG_BYTES) || \
                    !OPEN_BLOCK_FN(OPS_PFX crypto, crypto_slot, &medium->geometry, \
                                   expected_domain_id, key_epoch, \
                                   frame->target_node_id, \
                                   &cp->auth[(size_t)frame->target_node_id], \
                                   frame->ciphertext, opened, &decoded) || \
                    !verify_frame_digest_match(crypto, crypto_slot, opened, \
                                               block_bytes, frame->content_digest)) { \
                    return 0; \
                } \
            } \
            for (uint32_t i = 0u; i < medium->journal_count; ++i) { \
                const uint64_t id = medium->journal[i].target_node_id; \
                copy_bytes(medium->arena_ciphertext + (size_t)id * block_bytes, \
                           medium->journal[i].ciphertext, block_bytes); \
            } \
            medium->journal_reusable = 1u; \
        } else if (j_gen > cp->generation && \
                   j_gen <= medium->nonce_record.reserved_generation) { \
            medium->journal_count = 0u; \
            medium->journal_reusable = 1u; \
            zero_bytes((uint8_t *)medium->journal, sizeof(medium->journal)); \
        } else { \
            return 0; \
        } \
    } \
    /* Authenticate and reconstruct all arena blocks 0 .. cp->used - 1. */ \
    for (uint64_t id = 0u; id < cp->used; ++id) { \
        if (!cp->auth[(size_t)id].valid) { \
            continue; \
        } \
        struct NODE_TYPE decoded = {0}; \
        if (!OPEN_BLOCK_FN(OPS_PFX crypto, crypto_slot, &medium->geometry, \
                           expected_domain_id, key_epoch, id, \
                           &cp->auth[(size_t)id], \
                           medium->arena_ciphertext + (size_t)id * block_bytes, \
                           store->plain_arena + (size_t)id * block_bytes, &decoded)) { \
            zero_bytes((uint8_t *)store, sizeof(*store)); \
            return 0; \
        } \
        store->plain_generations[(size_t)id] = cp->auth[(size_t)id].generation; \
    } \
    if (!verify_root_digest_common(crypto, crypto_slot, \
                                   store->plain_arena + (size_t)cp->root * block_bytes, \
                                   block_bytes, cp->root_digest)) { \
        zero_bytes((uint8_t *)store, sizeof(*store)); \
        return 0; \
    } \
    struct vos_tree_image image = {0}; \
    struct vos_tree_limits check_limits = medium->limits; \
    image.geometry = medium->geometry; \
    image.geometry.arena_nodes = cp->used; \
    image.bytes = store->plain_arena; \
    image.length = (size_t)cp->used * block_bytes; \
    image.generations = store->plain_generations; \
    image.generation_count = (size_t)cp->used; \
    check_limits.height = cp->height; \
    if ((TREE_SANITY_EXPR) == VOS_TREE_REFUSED) { \
        zero_bytes((uint8_t *)store, sizeof(*store)); \
        return 0; \
    } \
    medium->fallback_checkpoint = medium->checkpoint; \
    medium->has_fallback = 1u; \
    store->open = 1u; \
    store->crypto_slot = crypto_slot; \
    store->domain_id = expected_domain_id; \
    store->key_epoch = key_epoch; \
    store->committed_generation = cp->generation; \
    store->committed_root = cp->root; \
    store->committed_height = cp->height; \
    store->committed_used = cp->used; \
    store->medium = medium; \
    store->crypto = crypto; \
    RETAIN_ACTIVE(store); \
    return 1; \
}

#define DEFINE_STORAGE_LOOKUP_FN(FN_NAME, STORE_TYPE, MEDIUM_TYPE, CP_TYPE, KEY_PARAM_DECL, VAL_PARAM_DECL, VAL_OUT_PTR, MAX_BLOCK, NODE_TYPE, BOUND_TYPE, BOUND_INIT, VAL_TYPE, VAL_INIT, MATCHES_ACTIVE, OPEN_BLOCK_FN, OPS_PFX, KEY_CMP_FN, KEY_PTR, LEAF_VAL_FIELD, CHILD_FIELD) \
int FN_NAME(const struct STORE_TYPE *store, uint64_t caller_domain, \
            KEY_PARAM_DECL, VAL_PARAM_DECL) \
{ \
    if (store == NULL || !store->open || store->medium == NULL || \
        store->crypto == NULL || (VAL_OUT_PTR) == NULL || \
        caller_domain != store->domain_id) { \
        return VOS_TREE_REFUSED; \
    } \
    const struct MEDIUM_TYPE *medium = store->medium; \
    const struct CP_TYPE *cp = &medium->checkpoint; \
    const size_t block_bytes = medium->geometry.block_bytes; \
    if (!MATCHES_ACTIVE(store) || \
        !verify_epoch_if_needed(store->crypto, store->crypto_slot, \
                                cp->commit_mode, cp->sealed_epoch, \
                                cp->fresh_region_id, cp->fresh_region_version, \
                                cp->fresh_state_digest, cp->epoch_root)) { \
        return VOS_TREE_REFUSED; \
    } \
    uint64_t cur_id = cp->root; \
    uint32_t rem_height = cp->height; \
    uint32_t rem_visits = medium->limits.visit_limit; \
    BOUND_TYPE lower = BOUND_INIT; \
    BOUND_TYPE upper = BOUND_INIT; \
    int has_lower = 0; \
    int has_upper = 0; \
    while (rem_visits > 0u) { \
        --rem_visits; \
        if (cur_id >= cp->used) { \
            return VOS_TREE_REFUSED; \
        } \
        uint8_t plain_block[MAX_BLOCK]; \
        struct NODE_TYPE node = {0}; \
        if (!OPEN_BLOCK_FN(OPS_PFX store->crypto, store->crypto_slot, \
                           &medium->geometry, store->domain_id, \
                           store->key_epoch, cur_id, &cp->auth[(size_t)cur_id], \
                           medium->arena_ciphertext + (size_t)cur_id * block_bytes, \
                           plain_block, &node)) { \
            return VOS_TREE_REFUSED; \
        } \
        if (cur_id == cp->root && \
            !verify_root_digest_common(store->crypto, store->crypto_slot, \
                                       plain_block, block_bytes, cp->root_digest)) { \
            return VOS_TREE_REFUSED; \
        } \
        if (node.kind == VOS_NODE_LEAF) { \
            if (rem_height != 0u) { \
                return VOS_TREE_REFUSED; \
            } \
            int found = 0; \
            VAL_TYPE found_val = VAL_INIT; \
            for (uint32_t i = 0u; i < node.count; ++i) { \
                if ((i != 0u && KEY_CMP_FN(&node.keys[i - 1u], &node.keys[i]) >= 0) || \
                    (has_lower && KEY_CMP_FN(&node.keys[i], &lower) < 0) || \
                    (has_upper && KEY_CMP_FN(&node.keys[i], &upper) >= 0)) { \
                    return VOS_TREE_REFUSED; \
                } \
                if (KEY_CMP_FN(&node.keys[i], KEY_PTR) == 0) { \
                    found = 1; \
                    found_val = node.LEAF_VAL_FIELD[i]; \
                } \
            } \
            if (!found) { \
                return VOS_TREE_MISSING; \
            } \
            *(VAL_OUT_PTR) = found_val; \
            return VOS_TREE_FOUND; \
        } \
        if (rem_height == 0u || node.count == 0u) { \
            return VOS_TREE_REFUSED; \
        } \
        BOUND_TYPE sep_lower = lower; \
        int sep_has_lower = has_lower; \
        for (uint32_t i = 0u; i + 1u < node.count; ++i) { \
            if ((sep_has_lower && KEY_CMP_FN(&node.keys[i], &sep_lower) <= 0) || \
                (has_upper && KEY_CMP_FN(&node.keys[i], &upper) >= 0)) { \
                return VOS_TREE_REFUSED; \
            } \
            sep_lower = node.keys[i]; \
            sep_has_lower = 1; \
        } \
        uint32_t route = 0u; \
        while (route + 1u < node.count && KEY_CMP_FN(&node.keys[route], KEY_PTR) <= 0) { \
            ++route; \
        } \
        if (route != 0u) { \
            lower = node.keys[route - 1u]; \
            has_lower = 1; \
        } \
        if (route + 1u < node.count) { \
            upper = node.keys[route]; \
            has_upper = 1; \
        } \
        cur_id = node.CHILD_FIELD[route]; \
        --rem_height; \
    } \
    return VOS_TREE_REFUSED; \
}

#define DEFINE_STORAGE_RETAIN_SNAPSHOT_FN(FN_NAME, STORE_TYPE, MEDIUM_TYPE, CP_TYPE, MATCHES_ACTIVE, VERIFY_CP_FN, OPS_PFX, SIGN_CP, PERSIST_FN, RETAIN_ACTIVE) \
int FN_NAME(struct STORE_TYPE *store, uint64_t caller_domain, uint64_t generation) \
{ \
    if (store == NULL || !store->open || store->medium == NULL || \
        store->crypto == NULL || caller_domain != store->domain_id || \
        generation == 0u || generation > store->committed_generation || \
        !MATCHES_ACTIVE(store)) { \
        return 0; \
    } \
    struct MEDIUM_TYPE *medium = store->medium; \
    struct CP_TYPE next = medium->checkpoint; \
    if (!VERIFY_CP_FN(OPS_PFX store->crypto, store->crypto_slot, store->domain_id, \
                      store->key_epoch, medium->geometry.arena_nodes, &next)) { \
        return 0; \
    } \
    const int retained = checkpoint_retains_snapshot_common( \
        next.snapshots, next.snapshot_count, generation); \
    if (retained && medium->has_fallback && \
        equal_bytes_ct(next.checkpoint_mac, medium->fallback_checkpoint.checkpoint_mac, \
                       VOS_CRYPTO_DIGEST_BYTES) && \
        VERIFY_CP_FN(OPS_PFX store->crypto, store->crypto_slot, store->domain_id, \
                     store->key_epoch, medium->geometry.arena_nodes, \
                     &medium->fallback_checkpoint)) { \
        return 1; \
    } \
    if (store->attempt.reserved) { \
        return 0; \
    } \
    if (!retained) { \
        if (generation != store->committed_generation || \
            next.snapshot_count >= VOS_STORAGE_MAX_SNAPSHOTS) { \
            return 0; \
        } \
        next.snapshots[next.snapshot_count] = generation; \
        ++next.snapshot_count; \
        if (!SIGN_CP) { \
            return 0; \
        } \
    } \
    medium->checkpoint = next; \
    medium->fallback_checkpoint = next; \
    medium->has_fallback = 1u; \
    if (!PERSIST_FN(store)) { \
        return 0; \
    } \
    RETAIN_ACTIVE(store); \
    return 1; \
}

static void serialize_nonce_record(const struct vos_storage_nonce_record *rec,
                                   uint8_t buf[40])
{
    write_tag8(buf, "VOSNONC1");
    put_le64(buf + 8u, rec->domain_id);
    put_le64(buf + 16u, rec->key_epoch);
    put_le64(buf + 24u, rec->reserved_generation);
    put_le64(buf + 32u, rec->max_generation);
}

static int sign_nonce_record(const struct vos_crypto_core *crypto,
                             uint32_t slot,
                             struct vos_storage_nonce_record *rec)
{
    uint8_t buf[40];
    serialize_nonce_record(rec, buf);
    return vos_crypto_core_commit_mac(crypto, slot, buf, sizeof(buf), rec->mac);
}

static int verify_nonce_record(const struct vos_crypto_core *crypto,
                               uint32_t slot,
                               uint64_t expected_domain,
                               uint64_t expected_epoch,
                               const struct vos_storage_nonce_record *rec)
{
    uint8_t buf[40];
    if (rec == NULL || rec->domain_id != expected_domain ||
        rec->key_epoch != expected_epoch ||
        rec->reserved_generation == 0u ||
        rec->reserved_generation > rec->max_generation) {
        return 0;
    }
    serialize_nonce_record(rec, buf);
    return vos_crypto_core_verify_commit_mac(crypto, slot, buf, sizeof(buf), rec->mac);
}

DEFINE_STORAGE_FRAME_OPS(, vos_storage_journal_frame, VOS_STORAGE_MAX_JOURNAL_FRAMES,
                         VOS_STORAGE_MAX_BLOCK_BYTES, "VOSJFRM1", "VOSPMAN1")

static int valid_fresh_keys(const struct vos_storage_checkpoint *cp)
{
    if (cp->fresh_key_count > VOS_STORAGE_MAX_FRESH_KEYS) {
        return 0;
    }
    for (uint32_t i = 1u; i < cp->fresh_key_count; ++i) {
        if (cp->fresh_keys[i - 1u] >= cp->fresh_keys[i]) {
            return 0;
        }
    }
    return 1;
}

static int fresh_key_member(const struct vos_storage_checkpoint *cp, uint64_t key)
{
    for (uint32_t i = 0u; i < cp->fresh_key_count; ++i) {
        if (cp->fresh_keys[i] == key) {
            return 1;
        }
        if (cp->fresh_keys[i] > key) {
            break;
        }
    }
    return 0;
}

static int fresh_transaction_allowed(const struct vos_storage_checkpoint *cp,
                                     const struct vos_storage_tx_spec *spec)
{
    if (!valid_fresh_keys(cp) ||
        !fresh_region_allows(spec->commit_mode, cp->fresh_region_id,
                             cp->fresh_region_version, spec->fresh_region_id,
                             spec->fresh_region_version)) {
        return 0;
    }
    const size_t count = spec->op_kind == VOS_STORAGE_OP_COMPACT ? 0u :
        spec->op_kind == VOS_STORAGE_OP_INSERT_BATCH ? spec->entry_count : 1u;
    uint32_t new_keys = 0u;
    for (size_t i = 0u; i < count; ++i) {
        const uint64_t key = spec->op_kind == VOS_STORAGE_OP_INSERT_BATCH
            ? spec->entries[i].key : spec->key;
        const int protected = fresh_key_member(cp, key);
        if (spec->commit_mode == VOS_STORAGE_COMMIT_ROLLBACKABLE && protected) {
            return 0;
        }
        if (!protected) {
            ++new_keys;
        }
    }
    return spec->commit_mode != VOS_STORAGE_COMMIT_FRESH ||
           new_keys <= VOS_STORAGE_MAX_FRESH_KEYS - cp->fresh_key_count;
}

static int inherit_fresh_keys(struct vos_storage_checkpoint *next,
                              const struct vos_storage_checkpoint *prior,
                              const struct vos_storage_tx_spec *spec)
{
    if (!fresh_transaction_allowed(prior, spec)) {
        return 0;
    }
    next->fresh_key_count = prior->fresh_key_count;
    for (uint32_t i = 0u; i < prior->fresh_key_count; ++i) {
        next->fresh_keys[i] = prior->fresh_keys[i];
    }
    if (spec->commit_mode != VOS_STORAGE_COMMIT_FRESH ||
        spec->op_kind == VOS_STORAGE_OP_COMPACT) {
        return 1;
    }
    const size_t count = spec->op_kind == VOS_STORAGE_OP_INSERT_BATCH
        ? spec->entry_count : 1u;
    for (size_t i = 0u; i < count; ++i) {
        const uint64_t key = spec->op_kind == VOS_STORAGE_OP_INSERT_BATCH
            ? spec->entries[i].key : spec->key;
        if (fresh_key_member(next, key)) {
            continue;
        }
        uint32_t at = next->fresh_key_count;
        while (at > 0u && next->fresh_keys[at - 1u] > key) {
            next->fresh_keys[at] = next->fresh_keys[at - 1u];
            --at;
        }
        next->fresh_keys[at] = key;
        ++next->fresh_key_count;
    }
    return 1;
}

DEFINE_STORAGE_CHECKPOINT_OPS(
    CHECKPOINT_SERIAL_BYTES,
    CHECKPOINT_HEADER_BYTES + VOS_STORAGE_MAX_FRESH_KEYS * 8u +
        VOS_STORAGE_MAX_SNAPSHOTS * 8u + VOS_STORAGE_MAX_DEADLIST * 16u +
        VOS_STORAGE_MAX_ARENA_NODES * CHECKPOINT_AUTH_BYTES,
    serialize_checkpoint, sign_checkpoint, verify_checkpoint_mac,
    vos_storage_checkpoint, , ,
    VOS_STORAGE_MAX_ARENA_NODES, VOS_STORAGE_MAX_JOURNAL_FRAMES,
    "VOSCHKP3", valid_fresh_keys,
    put_le64(buf + at, cp->fresh_keys[i]); at += 8u)

static int seal_node_block(const struct vos_crypto_core *crypto,
                           uint32_t slot,
                           uint64_t domain_id,
                           uint64_t key_epoch,
                           const struct vos_node_geometry *geometry,
                           uint64_t node_id,
                           uint64_t generation,
                           const uint8_t *plain_block,
                           uint32_t *kind_out,
                           uint8_t *cipher_out,
                           uint8_t tag_out[VOS_CRYPTO_TAG_BYTES],
                           uint8_t digest_out[VOS_CRYPTO_DIGEST_BYTES])
{
    struct vos_node decoded = {0};
    if (!vos_node_decode(geometry, node_id, generation, plain_block,
                         geometry->block_bytes, &decoded) ||
        !seal_node_block_crypto("VOSNAAD1", crypto, slot, domain_id, key_epoch,
                                geometry, node_id, generation, decoded.kind,
                                plain_block, cipher_out, tag_out, digest_out)) {
        return 0;
    }
    *kind_out = decoded.kind;
    return 1;
}

static int open_node_block(const struct vos_crypto_core *crypto,
                           uint32_t slot,
                           const struct vos_node_geometry *geometry,
                           uint64_t domain_id,
                           uint64_t key_epoch,
                           uint64_t node_id,
                           const struct vos_storage_block_auth *auth,
                           const uint8_t *cipher_block,
                           uint8_t *plain_out,
                           struct vos_node *node_out)
{
    if (!open_node_block_crypto("VOSNAAD1", crypto, slot, geometry, domain_id,
                                key_epoch, node_id, auth, cipher_block, plain_out)) {
        return 0;
    }
    if (!vos_node_decode(geometry, node_id, auth->generation, plain_out,
                         geometry->block_bytes, node_out) ||
        node_out->kind != auth->kind) {
        zero_bytes(plain_out, geometry->block_bytes);
        return 0;
    }
    return 1;
}

DEFINE_STORAGE_ACTIVE_OPS(
    vos_storage_store, vos_storage_checkpoint,
    retain_active_checkpoint, matches_active_checkpoint, persist_store, 1,
    verify_checkpoint_mac(store->crypto, store->crypto_slot, store->domain_id,
                          store->key_epoch, store->medium->geometry.arena_nodes, cp))

DEFINE_STORAGE_FORMAT_FN(
    vos_storage_format, vos_storage_medium, vos_storage_store,
    vos_storage_checkpoint, vos_node, , 0, (void)0, valid_geometry_and_limits,
    vos_node_encode(geometry, &root_node, store->plain_arena, geometry->block_bytes),
    seal_node_block(crypto, crypto_slot, domain_id, key_epoch, geometry, 0u,
                    initial_generation, store->plain_arena, &root_kind,
                    medium->arena_ciphertext, root_tag, root_digest),
    compute_payload_manifest, sign_checkpoint(crypto, crypto_slot, cp),
    retain_active_checkpoint)

static int valid_tx_spec(const struct vos_storage_store *store,
                         const struct vos_storage_tx_spec *spec)
{
    if (spec == NULL ||
        (spec->commit_mode != VOS_STORAGE_COMMIT_ROLLBACKABLE &&
         spec->commit_mode != VOS_STORAGE_COMMIT_FRESH)) {
        return 0;
    }
    if (spec->commit_mode == VOS_STORAGE_COMMIT_FRESH &&
        spec->fresh_region_version == 0u) {
        return 0;
    }
    if (spec->op_kind == VOS_STORAGE_OP_INSERT ||
        spec->op_kind == VOS_STORAGE_OP_DELETE ||
        spec->op_kind == VOS_STORAGE_OP_COMPACT) {
        return 1;
    }
    if (spec->op_kind == VOS_STORAGE_OP_INSERT_BATCH) {
        if (spec->entry_count == 0u || spec->entry_count > VOS_STORAGE_MAX_BATCH) {
            return 0;
        }
        for (size_t i = 1u; i < spec->entry_count; ++i) {
            if (spec->entries[i - 1u].key >= spec->entries[i].key) {
                return 0;
            }
        }
        return 1;
    }
    (void)store;
    return 0;
}

int vos_storage_attach_persistence(struct vos_storage_store *store,
                                    vos_storage_persistor persist, void *opaque)
{
    if (store == NULL || !store->open || store->attempt.reserved) return 0;
    store->persist = persist;
    store->persistence = opaque;
    return 1;
}

DEFINE_STORAGE_RESERVE_FN(
    vos_storage_reserve, vos_storage_store, vos_storage_medium,
    vos_storage_tx_spec, valid_tx_spec(store, spec),
    matches_active_checkpoint, fresh_transaction_allowed, 1, persist_store)

DEFINE_STORAGE_STAGE_HELPERS(
    untyped, vos_storage_store, vos_storage_medium, vos_storage_attempt,
    vos_storage_journal_frame, vos_node, VOS_STORAGE_MAX_JOURNAL_FRAMES,
    VOS_STORAGE_MAX_BLOCK_BYTES, 1,
    verify_checkpoint_mac(store->crypto, store->crypto_slot, store->domain_id,
                          store->key_epoch, medium->geometry.arena_nodes,
                          &medium->checkpoint),
    seal_node_block(store->crypto, store->crypto_slot, store->domain_id,
                    store->key_epoch, &medium->geometry, id, att->generation,
                    att->staged_plaintext + (size_t)id * block_bytes,
                    &kind, frame->ciphertext, frame->tag, frame->content_digest),
    sign_journal_frame, verify_journal_frame,
    open_node_block(store->crypto, store->crypto_slot, &medium->geometry,
                    store->domain_id, store->key_epoch, frame->target_node_id,
                    &att->staged_auth[(size_t)frame->target_node_id],
                    frame->ciphertext, opened, &decoded))

int vos_storage_stage(struct vos_storage_store *store,
                      uint64_t caller_domain)
{
    struct vos_tree_arena arena = {0};
    struct vos_tree_limits cur_limits = {0};
    if (!stage_untyped_prepare(store, caller_domain, &arena, &cur_limits)) {
        return 0;
    }
    struct vos_storage_medium *medium = store->medium;
    struct vos_storage_attempt *att = &store->attempt;

    uint64_t free_ids[VOS_STORAGE_MAX_ARENA_NODES];
    uint8_t retired[VOS_STORAGE_MAX_ARENA_NODES] = {0};
    size_t free_count = 0u;
    const uint64_t latest_snap = latest_snapshot_gen(
        medium->checkpoint.snapshots, medium->checkpoint.snapshot_count);
    const int has_snapshot = medium->checkpoint.snapshot_count != 0u;
    const int compact = att->spec.op_kind == VOS_STORAGE_OP_COMPACT;
    for (uint64_t id = 0u; id < store->committed_used; ++id) {
        const struct vos_storage_block_auth *auth = &medium->checkpoint.auth[(size_t)id];
        if (!auth->valid || (compact &&
            vos_tree_can_reclaim_node(auth->generation, latest_snap, has_snapshot))) {
            free_ids[free_count++] = id;
        }
    }
    const struct vos_tree_reuse reuse = {
        .ids = free_ids, .count = free_count,
        .retired = retired, .retired_count = VOS_STORAGE_MAX_ARENA_NODES
    };
    int update_ok = 0;
    if (att->spec.op_kind == VOS_STORAGE_OP_INSERT) {
        update_ok = vos_tree_insert_reuse(&arena, &cur_limits, store->committed_root,
                                          att->generation, att->spec.key,
                                          att->spec.value, &reuse, &att->result);
    } else if (att->spec.op_kind == VOS_STORAGE_OP_INSERT_BATCH) {
        update_ok = vos_tree_insert_batch_reuse(&arena, &cur_limits, store->committed_root,
                                                att->generation, att->spec.entries,
                                                att->spec.entry_count, &reuse, &att->result);
    } else if (att->spec.op_kind == VOS_STORAGE_OP_DELETE) {
        update_ok = vos_tree_delete_reuse(&arena, &cur_limits, store->committed_root,
                                          att->generation, att->spec.key, &reuse, &att->result);
    } else if (compact) {
        struct vos_tree_arena source = arena;
        source.bytes = store->plain_arena;
        source.generations = store->plain_generations;
        update_ok = vos_tree_compact_into(&source, &arena, &cur_limits,
                                          store->committed_root, att->generation,
                                          &reuse, &att->result);
    }
    if (!update_ok || att->result.used == 0u ||
        att->result.used > medium->geometry.arena_nodes) {
        return 0;
    }

    /* Retire only the rewritten paths; snapshot-owned blocks remain pinned. */
    for (uint64_t id = 0u; id < store->committed_used; ++id) {
        if (!retired[(size_t)id] ||
            att->staged_generations[(size_t)id] == att->generation) {
            continue;
        }
        const uint64_t birth = store->plain_generations[(size_t)id];
        if (!retire_dead_node_common(id, birth, latest_snap, has_snapshot,
                                     &att->staged_auth[(size_t)id],
                                     &att->staged_dead_count,
                                     att->staged_deadlist)) {
            return 0;
        }
    }
    return seal_untyped_staged_frames(store);
}

static int verify_staged_candidate(const struct vos_storage_store *store)
{
    const struct vos_storage_attempt *att = &store->attempt;
    struct vos_tree_image candidate = {0};
    struct vos_tree_limits candidate_limits = {0};
    uint64_t checked = 0u;

    if (!verify_untyped_staged_frames(store, &candidate, &candidate_limits)) {
        return 0;
    }
    if (att->spec.op_kind == VOS_STORAGE_OP_COMPACT) {
        return vos_tree_lookup(&candidate, &candidate_limits,
                               att->result.root, 0u, &checked) != VOS_TREE_REFUSED;
    }
    const size_t queries = att->spec.op_kind == VOS_STORAGE_OP_INSERT_BATCH
        ? att->spec.entry_count : 1u;
    for (size_t i = 0u; i < queries; ++i) {
        const uint64_t key = att->spec.op_kind == VOS_STORAGE_OP_INSERT_BATCH
            ? att->spec.entries[i].key : att->spec.key;
        const int status = vos_tree_lookup_path(&candidate, &candidate_limits,
                                                att->result.root, key, &checked);
        if (att->spec.op_kind == VOS_STORAGE_OP_DELETE) {
            if (status != VOS_TREE_MISSING) {
                return 0;
            }
        } else {
            const uint64_t value = att->spec.op_kind == VOS_STORAGE_OP_INSERT_BATCH
                ? att->spec.entries[i].value : att->spec.value;
            if (status != VOS_TREE_FOUND || checked != value) {
                return 0;
            }
        }
    }
    return 1;
}

DEFINE_STORAGE_PUBLISH_FN(
    vos_storage_publish, vos_storage_store, vos_storage_medium,
    vos_storage_attempt, vos_storage_checkpoint, verify_staged_candidate,
    inherit_fresh_keys, compute_payload_manifest,
    sign_checkpoint(store->crypto, store->crypto_slot, &next_cp),
    persist_store, retain_active_checkpoint)

DEFINE_STORAGE_REOPEN_FN(
    vos_storage_reopen, vos_storage_medium, vos_storage_store,
    vos_storage_checkpoint, vos_storage_journal_frame, vos_node,
    VOS_STORAGE_MAX_JOURNAL_FRAMES, VOS_STORAGE_MAX_BLOCK_BYTES, ,
    0, valid_geometry_and_limits, (void)0, verify_checkpoint_mac, ,
    compute_payload_manifest, verify_journal_frame, open_node_block,
    (vos_tree_lookup(&image, &check_limits, cp->root, 0u, &(uint64_t){0u})),
    retain_active_checkpoint)

DEFINE_STORAGE_LOOKUP_FN(
    vos_storage_lookup, vos_storage_store, vos_storage_medium,
    vos_storage_checkpoint, uint64_t key, uint64_t *value_out, value_out,
    VOS_STORAGE_MAX_BLOCK_BYTES, vos_node, uint64_t, 0u, uint64_t, 0u,
    matches_active_checkpoint, open_node_block, , compare_untyped_keys, &key,
    values, values)

static int checkpoint_retains_snapshot(const struct vos_storage_checkpoint *cp,
                                       uint64_t generation)
{
    return checkpoint_retains_snapshot_common(cp->snapshots, cp->snapshot_count,
                                              generation);
}

DEFINE_STORAGE_RETAIN_SNAPSHOT_FN(
    vos_storage_retain_snapshot, vos_storage_store, vos_storage_medium,
    vos_storage_checkpoint, matches_active_checkpoint, verify_checkpoint_mac, ,
    sign_checkpoint(store->crypto, store->crypto_slot, &next),
    persist_store, retain_active_checkpoint)

int vos_storage_object_digest(const struct vos_storage_store *store,
                              const uint8_t *bytes,
                              size_t length,
                              uint8_t digest_out[VOS_CRYPTO_DIGEST_BYTES])
{
    return store != NULL &&
           object_digest_common(store->open, store->crypto, store->crypto_slot,
                                bytes, length, digest_out);
}

static int compute_resident_digest(const struct vos_storage_store *store,
                                   uint64_t owner_id,
                                   uint64_t domain_id,
                                   uint64_t object_key,
                                   uint64_t version,
                                   uint32_t resident_kind,
                                   uint64_t generation,
                                   const uint8_t *bytes,
                                   size_t length,
                                   uint8_t root_out[VOS_CRYPTO_DIGEST_BYTES])
{
    uint8_t buf[56u + VOS_RESIDENT_BYTES];
    if (length > VOS_RESIDENT_BYTES || (length != 0u && bytes == NULL)) {
        return 0;
    }
    buf[0] = 'V';
    buf[1] = 'O';
    buf[2] = 'S';
    buf[3] = 'R';
    buf[4] = 'O';
    buf[5] = 'B';
    buf[6] = 'J';
    buf[7] = '1';
    put_le64(buf + 8u, owner_id);
    put_le64(buf + 16u, domain_id);
    put_le64(buf + 24u, object_key);
    put_le64(buf + 32u, version);
    put_le32(buf + 40u, resident_kind);
    put_le32(buf + 44u, (uint32_t)length);
    put_le64(buf + 48u, generation);
    if (length != 0u) {
        copy_bytes(buf + 56u, bytes, length);
    }
    return vos_crypto_core_keyed_digest(store->crypto, store->crypto_slot,
                                        buf, 56u + length, root_out);
}

static uint64_t resident_tree_value(const uint8_t root[VOS_CRYPTO_DIGEST_BYTES],
                                    uint64_t version)
{
    return get_le64(root) ^ (version * 0x9e3779b97f4a7c15ULL);
}

int vos_storage_bind_resident_identity(const struct vos_storage_store *store,
                                       uint64_t owner_id,
                                       uint64_t object_key,
                                       uint64_t version,
                                       uint32_t resident_kind,
                                       const uint8_t *bytes,
                                       size_t length,
                                       uint64_t *tree_value_out,
                                       struct vos_resident_identity *identity_out)
{
    struct vos_resident_identity id = {0};
    if (store == NULL || !store->open || store->crypto == NULL ||
        tree_value_out == NULL || identity_out == NULL || version == 0u ||
        length > VOS_RESIDENT_BYTES ||
        (resident_kind != VOS_RESIDENT_SYSTEM &&
         resident_kind != VOS_RESIDENT_USER)) {
        return 0;
    }
    if ((resident_kind == VOS_RESIDENT_SYSTEM &&
         store->crypto_slot != VOS_CRYPTO_DOMAIN_SYSTEM) ||
        (resident_kind == VOS_RESIDENT_USER &&
         store->crypto_slot != VOS_CRYPTO_DOMAIN_USER)) {
        return 0;
    }
    id.owner = owner_id;
    id.domain = store->domain_id;
    id.object = object_key;
    id.version = version;
    id.kind = resident_kind;
    id.generation = store->committed_generation;
    if (!compute_resident_digest(store, id.owner, id.domain, id.object,
                                 id.version, id.kind, id.generation,
                                 bytes, length, id.root)) {
        return 0;
    }
    *tree_value_out = resident_tree_value(id.root, id.version);
    *identity_out = id;
    return 1;
}

int vos_storage_verify_resident(void *verification,
                                const struct vos_resident_identity *identity,
                                const uint8_t *bytes,
                                size_t length)
{
    const struct vos_storage_store *store =
        (const struct vos_storage_store *)verification;
    uint8_t expected_root[VOS_CRYPTO_DIGEST_BYTES];
    uint64_t committed_value = 0u;
    if (store == NULL || !store->open || store->medium == NULL ||
        store->crypto == NULL ||
        identity == NULL || identity->version == 0u ||
        length > VOS_RESIDENT_BYTES ||
        identity->domain != store->domain_id) {
        return 0;
    }
    if (identity->kind == VOS_RESIDENT_SYSTEM) {
        if (store->crypto_slot != VOS_CRYPTO_DOMAIN_SYSTEM ||
            identity->generation != store->committed_generation) {
            return 0;
        }
    } else if (identity->kind == VOS_RESIDENT_USER) {
        if (store->crypto_slot != VOS_CRYPTO_DOMAIN_USER ||
            identity->generation == 0u ||
            identity->generation > store->committed_generation) {
            return 0;
        }
    } else {
        return 0;
    }
    if (!compute_resident_digest(store, identity->owner, identity->domain,
                                 identity->object, identity->version,
                                 identity->kind, identity->generation,
                                 bytes, length, expected_root) ||
        !equal_bytes_ct(expected_root, identity->root, VOS_CRYPTO_DIGEST_BYTES)) {
        return 0;
    }
    if (vos_storage_lookup(store, identity->domain, identity->object,
                           &committed_value) != VOS_TREE_FOUND) {
        return 0;
    }
    return committed_value == resident_tree_value(identity->root, identity->version);
}

int vos_storage_admit_resident(const struct vos_storage_store *store,
                               const struct vos_resident_identity *identity,
                               const uint8_t *bytes, size_t length,
                               struct vos_storage_resident_receipt *receipt)
{
    if (receipt == NULL ||
        !vos_storage_verify_resident((void *)store, identity, bytes, length)) {
        return 0;
    }
    const struct vos_storage_resident_receipt admitted = {
        .store = store,
        .medium = store->medium,
        .crypto = store->crypto,
        .crypto_slot = store->crypto_slot,
        .key_context = store->crypto->domain_context[store->crypto_slot],
        .checkpoint = store->medium->checkpoint,
        .identity = *identity,
        .length = length,
        .valid = 1u
    };
    *receipt = admitted;
    copy_bytes((uint8_t *)&receipt->checkpoint,
                (const uint8_t *)&store->medium->checkpoint,
                sizeof(receipt->checkpoint));
    return 1;
}

static int verify_resident_predecessor(const struct vos_storage_store *store,
                                       const struct vos_storage_resident_receipt *receipt)
{
    const struct vos_storage_checkpoint *old = &receipt->checkpoint;
    const struct vos_storage_checkpoint *current = &store->medium->checkpoint;
    if (receipt->identity.kind != VOS_RESIDENT_USER ||
        receipt->identity.generation != old->generation ||
        current->generation <= old->generation ||
        current->generation - old->generation != 1u ||
        old->commit_mode != VOS_STORAGE_COMMIT_ROLLBACKABLE ||
        current->commit_mode != VOS_STORAGE_COMMIT_ROLLBACKABLE ||
        old->sealed_epoch != 0u || current->sealed_epoch != 0u ||
        (store->crypto->epoch_sealed_mask & (1u << store->crypto_slot)) != 0u ||
        !verify_checkpoint_mac(store->crypto, store->crypto_slot, store->domain_id,
                               store->key_epoch, store->medium->geometry.arena_nodes, old) ||
        !checkpoint_retains_snapshot(old, old->generation) ||
        !checkpoint_retains_snapshot(current, old->generation)) return 0;

    uint64_t current_value = 0u;
    return vos_storage_lookup(store, receipt->identity.domain, receipt->identity.object,
                              &current_value) == VOS_TREE_FOUND;
}

static int verify_resident_receipt(const struct vos_storage_resident_receipt *receipt,
                                    const struct vos_resident_identity *identity,
                                    const uint8_t *bytes, size_t length,
                                    int allow_predecessor)
{
    if (receipt == NULL || receipt->valid != 1u || identity == NULL ||
        length != receipt->length || length > VOS_RESIDENT_BYTES ||
        (length != 0u && bytes == NULL)) return 0;
    const struct vos_storage_store *store = receipt->store;
    if (store == NULL || !store->open || store->medium == NULL ||
        store->crypto == NULL || store->crypto_slot >= VOS_CRYPTO_MAX_DOMAINS ||
        store->medium != receipt->medium || store->crypto != receipt->crypto ||
        store->crypto_slot != receipt->crypto_slot ||
        identity->owner != receipt->identity.owner ||
        identity->domain != receipt->identity.domain ||
        identity->object != receipt->identity.object ||
        identity->version != receipt->identity.version ||
        identity->generation != receipt->identity.generation ||
        identity->kind != receipt->identity.kind ||
        !equal_bytes_ct(identity->root, receipt->identity.root, VOS_CRYPTO_DIGEST_BYTES) ||
        store->domain_id != receipt->checkpoint.domain_id ||
        store->key_epoch != receipt->checkpoint.key_epoch ||
        store->crypto->domain_context[store->crypto_slot] != receipt->key_context ||
        !matches_active_checkpoint(store)) return 0;

    const struct vos_storage_checkpoint *cp = &store->medium->checkpoint;
    const int unchanged = equal_bytes_ct((const uint8_t *)cp,
                                          (const uint8_t *)&receipt->checkpoint,
                                          sizeof(*cp));
    if (!unchanged && (!allow_predecessor || !verify_resident_predecessor(store, receipt)))
        return 0;
    if (!verify_epoch_if_needed(store->crypto, store->crypto_slot,
                                cp->commit_mode, cp->sealed_epoch,
                                cp->fresh_region_id, cp->fresh_region_version,
                                cp->fresh_state_digest, cp->epoch_root)) {
        return 0;
    }
    uint8_t expected[VOS_CRYPTO_DIGEST_BYTES];
    return compute_resident_digest(store, identity->owner, identity->domain,
                                    identity->object, identity->version,
                                    identity->kind, identity->generation,
                                    bytes, length, expected) &&
           equal_bytes_ct(expected, identity->root, VOS_CRYPTO_DIGEST_BYTES);
}

int vos_storage_verify_admitted_resident(void *verification,
                                         const struct vos_resident_identity *identity,
                                         const uint8_t *bytes, size_t length)
{
    return verify_resident_receipt(verification, identity, bytes, length, 0);
}

int vos_storage_verify_retained_resident(void *verification,
                                         const struct vos_resident_identity *identity,
                                         const uint8_t *bytes, size_t length)
{
    return verify_resident_receipt(verification, identity, bytes, length, 1);
}

static uint32_t get_le32(const uint8_t *src)
{
    uint32_t result = 0u;
    for (uint32_t i = 0u; i < 4u; ++i) {
        result |= (uint32_t)src[i] << (8u * i);
    }
    return result;
}

static int all_zero(const uint8_t *buf, size_t length)
{
    uint8_t acc = 0u;
    for (size_t i = 0u; i < length; ++i) {
        acc |= buf[i];
    }
    return acc == 0u;
}

enum {
    BLKDEV_CP_BYTES = 16u * VOS_STORAGE_BLKDEV_BLOCK_BYTES
};

static int encode_blkdev_checkpoint(const struct vos_storage_checkpoint *cp,
                                    uint64_t arena_nodes,
                                    uint8_t out[BLKDEV_CP_BYTES])
{
    if (cp == NULL || out == NULL ||
        arena_nodes > VOS_STORAGE_BLKDEV_MAX_ARENA_NODES ||
        !valid_fresh_keys(cp) ||
        cp->snapshot_count > VOS_STORAGE_MAX_SNAPSHOTS ||
        cp->dead_count > VOS_STORAGE_BLKDEV_MAX_DEADLIST ||
        cp->frame_count > VOS_STORAGE_BLKDEV_MAX_JOURNAL_FRAMES) {
        return 0;
    }
    zero_bytes(out, BLKDEV_CP_BYTES);
    out[0] = 'V';
    out[1] = 'O';
    out[2] = 'S';
    out[3] = 'C';
    out[4] = 'H';
    out[5] = 'K';
    out[6] = '0';
    out[7] = '3';
    put_le32(out + 8u, cp->committed ? 1u : 0u);
    put_le32(out + 12u, cp->commit_mode);
    put_le64(out + 16u, cp->domain_id);
    put_le64(out + 24u, cp->key_epoch);
    put_le64(out + 32u, cp->generation);
    put_le64(out + 40u, cp->root);
    put_le32(out + 48u, cp->height);
    put_le32(out + 52u, cp->frame_count);
    put_le64(out + 56u, cp->used);
    put_le64(out + 64u, cp->fresh_region_id);
    put_le64(out + 72u, cp->fresh_region_version);
    put_le64(out + 80u, 0u);
    put_le32(out + 88u, cp->snapshot_count);
    put_le32(out + 92u, cp->dead_count);
    zero_bytes(out + 96u, VOS_CRYPTO_DIGEST_BYTES);
    copy_bytes(out + 128u, cp->root_digest, VOS_CRYPTO_DIGEST_BYTES);
    copy_bytes(out + 160u, cp->payload_manifest_digest, VOS_CRYPTO_DIGEST_BYTES);
    copy_bytes(out + 192u, cp->checkpoint_mac, VOS_CRYPTO_DIGEST_BYTES);
    copy_bytes(out + 1056u, cp->fresh_state_digest, VOS_CRYPTO_DIGEST_BYTES);
    put_le32(out + 1088u, cp->fresh_key_count);
    for (uint32_t i = 0u; i < cp->fresh_key_count; ++i) {
        put_le64(out + 1092u + (size_t)i * 8u, cp->fresh_keys[i]);
    }
    for (uint32_t i = 0u; i < VOS_STORAGE_MAX_SNAPSHOTS; ++i) {
        put_le64(out + 224u + (size_t)i * 8u,
                 (i < cp->snapshot_count) ? cp->snapshots[i] : 0u);
    }
    for (uint32_t i = 0u; i < VOS_STORAGE_BLKDEV_MAX_DEADLIST; ++i) {
        const size_t at = 288u + (size_t)i * 16u;
        if (i < cp->dead_count) {
            put_le64(out + at, cp->deadlist[i].node_id);
            put_le64(out + at + 8u, cp->deadlist[i].birth_generation);
        }
    }
    for (uint32_t i = 0u; i < VOS_STORAGE_BLKDEV_MAX_ARENA_NODES; ++i) {
        const size_t at = 544u + (size_t)i * 32u;
        if ((uint64_t)i < arena_nodes) {
            put_le32(out + at, cp->auth[i].valid ? 1u : 0u);
            put_le32(out + at + 4u, cp->auth[i].kind);
            put_le64(out + at + 8u, cp->auth[i].generation);
            copy_bytes(out + at + 16u, cp->auth[i].tag, VOS_CRYPTO_TAG_BYTES);
        }
    }
    return 1;
}

static int decode_blkdev_checkpoint(const uint8_t in[BLKDEV_CP_BYTES],
                                    uint64_t arena_nodes,
                                    struct vos_storage_checkpoint *cp_out)
{
    static const uint8_t magic[8] = {'V', 'O', 'S', 'C', 'H', 'K', '0', '3'};
    if (in == NULL || cp_out == NULL ||
        arena_nodes > VOS_STORAGE_BLKDEV_MAX_ARENA_NODES ||
        !equal_bytes_ct(in, magic, sizeof(magic)) ||
        !all_zero(in + 80u, 8u) || !all_zero(in + 96u, VOS_CRYPTO_DIGEST_BYTES) ||
        !all_zero(in + 1604u, BLKDEV_CP_BYTES - 1604u)) {
        return 0;
    }
    zero_bytes((uint8_t *)cp_out, sizeof(*cp_out));
    cp_out->committed = get_le32(in + 8u);
    cp_out->commit_mode = get_le32(in + 12u);
    cp_out->domain_id = get_le64(in + 16u);
    cp_out->key_epoch = get_le64(in + 24u);
    cp_out->generation = get_le64(in + 32u);
    cp_out->root = get_le64(in + 40u);
    cp_out->height = get_le32(in + 48u);
    cp_out->frame_count = get_le32(in + 52u);
    cp_out->used = get_le64(in + 56u);
    cp_out->fresh_region_id = get_le64(in + 64u);
    cp_out->fresh_region_version = get_le64(in + 72u);
    cp_out->sealed_epoch = get_le64(in + 80u);
    cp_out->snapshot_count = get_le32(in + 88u);
    cp_out->dead_count = get_le32(in + 92u);
    cp_out->fresh_key_count = get_le32(in + 1088u);
    if (cp_out->committed > 1u ||
        cp_out->fresh_key_count > VOS_STORAGE_MAX_FRESH_KEYS ||
        cp_out->snapshot_count > VOS_STORAGE_MAX_SNAPSHOTS ||
        cp_out->dead_count > VOS_STORAGE_BLKDEV_MAX_DEADLIST ||
        cp_out->frame_count > VOS_STORAGE_BLKDEV_MAX_JOURNAL_FRAMES) {
        zero_bytes((uint8_t *)cp_out, sizeof(*cp_out));
        return 0;
    }
    for (uint32_t i = 0u; i < VOS_STORAGE_MAX_FRESH_KEYS; ++i) {
        const uint64_t key = get_le64(in + 1092u + (size_t)i * 8u);
        if (i < cp_out->fresh_key_count) {
            cp_out->fresh_keys[i] = key;
        } else if (key != 0u) {
            zero_bytes((uint8_t *)cp_out, sizeof(*cp_out));
            return 0;
        }
    }
    if (!valid_fresh_keys(cp_out)) {
        zero_bytes((uint8_t *)cp_out, sizeof(*cp_out));
        return 0;
    }
    copy_bytes(cp_out->epoch_root, in + 96u, VOS_CRYPTO_DIGEST_BYTES);
    copy_bytes(cp_out->root_digest, in + 128u, VOS_CRYPTO_DIGEST_BYTES);
    copy_bytes(cp_out->payload_manifest_digest, in + 160u, VOS_CRYPTO_DIGEST_BYTES);
    copy_bytes(cp_out->checkpoint_mac, in + 192u, VOS_CRYPTO_DIGEST_BYTES);
    copy_bytes(cp_out->fresh_state_digest, in + 1056u, VOS_CRYPTO_DIGEST_BYTES);
    for (uint32_t i = 0u; i < VOS_STORAGE_MAX_SNAPSHOTS; ++i) {
        const uint64_t snap = get_le64(in + 224u + (size_t)i * 8u);
        if (i < cp_out->snapshot_count) {
            cp_out->snapshots[i] = snap;
        } else if (snap != 0u) {
            zero_bytes((uint8_t *)cp_out, sizeof(*cp_out));
            return 0;
        }
    }
    for (uint32_t i = 0u; i < VOS_STORAGE_BLKDEV_MAX_DEADLIST; ++i) {
        const size_t at = 288u + (size_t)i * 16u;
        const uint64_t nid = get_le64(in + at);
        const uint64_t bgen = get_le64(in + at + 8u);
        if (i < cp_out->dead_count) {
            cp_out->deadlist[i].node_id = nid;
            cp_out->deadlist[i].birth_generation = bgen;
        } else if (nid != 0u || bgen != 0u) {
            zero_bytes((uint8_t *)cp_out, sizeof(*cp_out));
            return 0;
        }
    }
    for (uint32_t i = 0u; i < VOS_STORAGE_BLKDEV_MAX_ARENA_NODES; ++i) {
        const size_t at = 544u + (size_t)i * 32u;
        if ((uint64_t)i < arena_nodes) {
            cp_out->auth[i].valid = get_le32(in + at);
            cp_out->auth[i].kind = get_le32(in + at + 4u);
            cp_out->auth[i].generation = get_le64(in + at + 8u);
            copy_bytes(cp_out->auth[i].tag, in + at + 16u, VOS_CRYPTO_TAG_BYTES);
        } else if (!all_zero(in + at, 32u)) {
            zero_bytes((uint8_t *)cp_out, sizeof(*cp_out));
            return 0;
        }
    }
    return 1;
}

int vos_storage_encode_blkdev_medium(
    const struct vos_storage_medium *medium,
    uint8_t medium_bytes[VOS_STORAGE_BLKDEV_MEDIUM_BYTES])
{
    if (medium == NULL || medium_bytes == NULL ||
        !valid_geometry_and_limits(&medium->geometry, &medium->limits) ||
        medium->geometry.block_bytes != VOS_STORAGE_BLKDEV_BLOCK_BYTES ||
        medium->geometry.arena_nodes > VOS_STORAGE_BLKDEV_MAX_ARENA_NODES ||
        medium->journal_count > VOS_STORAGE_BLKDEV_MAX_JOURNAL_FRAMES ||
        medium->journal_reusable > 1u ||
        medium->has_fallback > 1u) {
        return 0;
    }
    zero_bytes(medium_bytes, VOS_STORAGE_BLKDEV_MEDIUM_BYTES);

    /* Block 0: superblock + durable key-wide nonce reservation record. */
    medium_bytes[0] = 'V';
    medium_bytes[1] = 'O';
    medium_bytes[2] = 'S';
    medium_bytes[3] = 'S';
    medium_bytes[4] = 'U';
    medium_bytes[5] = 'P';
    medium_bytes[6] = '0';
    medium_bytes[7] = '1';
    put_le32(medium_bytes + 8u, medium->geometry.fan);
    put_le32(medium_bytes + 12u, medium->limits.height);
    put_le64(medium_bytes + 16u, medium->geometry.arena_nodes);
    put_le64(medium_bytes + 24u, (uint64_t)medium->geometry.block_bytes);
    put_le32(medium_bytes + 32u, medium->limits.depth_limit);
    put_le32(medium_bytes + 36u, medium->limits.visit_limit);
    put_le32(medium_bytes + 40u, medium->journal_count);
    put_le32(medium_bytes + 44u, medium->journal_reusable);
    put_le32(medium_bytes + 48u, medium->has_fallback);
    put_le64(medium_bytes + 64u, medium->nonce_record.domain_id);
    put_le64(medium_bytes + 72u, medium->nonce_record.key_epoch);
    put_le64(medium_bytes + 80u, medium->nonce_record.reserved_generation);
    put_le64(medium_bytes + 88u, medium->nonce_record.max_generation);
    copy_bytes(medium_bytes + 96u, medium->nonce_record.mac,
               VOS_CRYPTO_DIGEST_BYTES);

    /* Blocks 1..16: encrypted arena blocks. */
    copy_bytes(medium_bytes + VOS_STORAGE_BLKDEV_BLOCK_BYTES,
               medium->arena_ciphertext,
               (size_t)medium->geometry.arena_nodes * VOS_STORAGE_BLKDEV_BLOCK_BYTES);

    /* Blocks 17..30: journal frames 0..6 (2 blocks = 256 bytes per frame). */
    for (uint32_t j = 0u; j < medium->journal_count; ++j) {
        const struct vos_storage_journal_frame *fr = &medium->journal[j];
        uint8_t *hdr = medium_bytes +
                       (size_t)(17u + 2u * j) * VOS_STORAGE_BLKDEV_BLOCK_BYTES;
        uint8_t *ct = hdr + VOS_STORAGE_BLKDEV_BLOCK_BYTES;
        put_le32(hdr + 0u, fr->occupied ? 1u : 0u);
        put_le32(hdr + 4u, fr->frame_index);
        put_le32(hdr + 8u, fr->kind);
        put_le64(hdr + 16u, fr->tx_generation);
        put_le64(hdr + 24u, fr->target_node_id);
        copy_bytes(hdr + 32u, fr->tag, VOS_CRYPTO_TAG_BYTES);
        copy_bytes(hdr + 48u, fr->content_digest, VOS_CRYPTO_DIGEST_BYTES);
        copy_bytes(hdr + 80u, fr->frame_mac, VOS_CRYPTO_DIGEST_BYTES);
        copy_bytes(ct, fr->ciphertext, VOS_STORAGE_BLKDEV_BLOCK_BYTES);
    }

    /* Blocks 32..47: primary checkpoint. */
    if (!encode_blkdev_checkpoint(
            &medium->checkpoint, medium->geometry.arena_nodes,
            medium_bytes + 32u * VOS_STORAGE_BLKDEV_BLOCK_BYTES)) {
        zero_bytes(medium_bytes, VOS_STORAGE_BLKDEV_MEDIUM_BYTES);
        return 0;
    }

    /* Blocks 48..63: fallback checkpoint when present. */
    if (medium->has_fallback &&
        !encode_blkdev_checkpoint(
            &medium->fallback_checkpoint, medium->geometry.arena_nodes,
            medium_bytes + 48u * VOS_STORAGE_BLKDEV_BLOCK_BYTES)) {
        zero_bytes(medium_bytes, VOS_STORAGE_BLKDEV_MEDIUM_BYTES);
        return 0;
    }
    return 1;
}

int vos_storage_decode_blkdev_medium(
    const uint8_t medium_bytes[VOS_STORAGE_BLKDEV_MEDIUM_BYTES],
    struct vos_storage_medium *medium_out)
{
    static const uint8_t sup_magic[8] = {'V', 'O', 'S', 'S', 'U', 'P', '0', '1'};
    if (medium_bytes == NULL || medium_out == NULL ||
        !equal_bytes_ct(medium_bytes, sup_magic, sizeof(sup_magic)) ||
        !all_zero(medium_bytes + 52u, 12u)) {
        return 0;
    }
    zero_bytes((uint8_t *)medium_out, sizeof(*medium_out));
    medium_out->geometry.fan = get_le32(medium_bytes + 8u);
    medium_out->limits.height = get_le32(medium_bytes + 12u);
    medium_out->geometry.arena_nodes = get_le64(medium_bytes + 16u);
    const uint64_t bbytes = get_le64(medium_bytes + 24u);
    medium_out->geometry.block_bytes = (size_t)bbytes;
    medium_out->limits.depth_limit = get_le32(medium_bytes + 32u);
    medium_out->limits.visit_limit = get_le32(medium_bytes + 36u);
    medium_out->journal_count = get_le32(medium_bytes + 40u);
    medium_out->journal_reusable = get_le32(medium_bytes + 44u);
    medium_out->has_fallback = get_le32(medium_bytes + 48u);

    if (bbytes != VOS_STORAGE_BLKDEV_BLOCK_BYTES ||
        !valid_geometry_and_limits(&medium_out->geometry, &medium_out->limits) ||
        medium_out->geometry.arena_nodes > VOS_STORAGE_BLKDEV_MAX_ARENA_NODES ||
        medium_out->journal_count > VOS_STORAGE_BLKDEV_MAX_JOURNAL_FRAMES ||
        medium_out->journal_reusable > 1u ||
        medium_out->has_fallback > 1u) {
        zero_bytes((uint8_t *)medium_out, sizeof(*medium_out));
        return 0;
    }
    medium_out->nonce_record.domain_id = get_le64(medium_bytes + 64u);
    medium_out->nonce_record.key_epoch = get_le64(medium_bytes + 72u);
    medium_out->nonce_record.reserved_generation = get_le64(medium_bytes + 80u);
    medium_out->nonce_record.max_generation = get_le64(medium_bytes + 88u);
    copy_bytes(medium_out->nonce_record.mac, medium_bytes + 96u,
               VOS_CRYPTO_DIGEST_BYTES);

    /* Blocks 1..16: encrypted arena blocks. */
    copy_bytes(medium_out->arena_ciphertext,
               medium_bytes + VOS_STORAGE_BLKDEV_BLOCK_BYTES,
               (size_t)medium_out->geometry.arena_nodes * VOS_STORAGE_BLKDEV_BLOCK_BYTES);

    /* Blocks 17..30: journal frames. Frame blocks may carry bit tears from an
     * interrupted in-flight write; decode raw fields so vos_storage_reopen can
     * apply the R-10-002a prefix-redo / MAC verification decision. */
    for (uint32_t j = 0u; j < medium_out->journal_count; ++j) {
        const uint8_t *hdr = medium_bytes +
                             (size_t)(17u + 2u * j) * VOS_STORAGE_BLKDEV_BLOCK_BYTES;
        const uint8_t *ct = hdr + VOS_STORAGE_BLKDEV_BLOCK_BYTES;
        struct vos_storage_journal_frame *fr = &medium_out->journal[j];
        fr->occupied = (get_le32(hdr + 0u) != 0u) ? 1u : 0u;
        fr->frame_index = get_le32(hdr + 4u);
        fr->kind = get_le32(hdr + 8u);
        fr->tx_generation = get_le64(hdr + 16u);
        fr->target_node_id = get_le64(hdr + 24u);
        copy_bytes(fr->tag, hdr + 32u, VOS_CRYPTO_TAG_BYTES);
        copy_bytes(fr->content_digest, hdr + 48u, VOS_CRYPTO_DIGEST_BYTES);
        copy_bytes(fr->frame_mac, hdr + 80u, VOS_CRYPTO_DIGEST_BYTES);
        copy_bytes(fr->ciphertext, ct, VOS_STORAGE_BLKDEV_BLOCK_BYTES);
    }

    /* Decode slots independently: a torn slot is not a malformed device image.
     * Reopen authenticates/selects complete slots before returning any bytes. */
    if (!decode_blkdev_checkpoint(
            medium_bytes + 32u * VOS_STORAGE_BLKDEV_BLOCK_BYTES,
            medium_out->geometry.arena_nodes, &medium_out->checkpoint)) {
        zero_bytes((uint8_t *)&medium_out->checkpoint, sizeof(medium_out->checkpoint));
    }
    if (medium_out->has_fallback) {
        if (!decode_blkdev_checkpoint(
                medium_bytes + 48u * VOS_STORAGE_BLKDEV_BLOCK_BYTES,
                medium_out->geometry.arena_nodes, &medium_out->fallback_checkpoint)) {
            zero_bytes((uint8_t *)&medium_out->fallback_checkpoint,
                       sizeof(medium_out->fallback_checkpoint));
        }
    } else if (!all_zero(medium_bytes + 48u * VOS_STORAGE_BLKDEV_BLOCK_BYTES,
                         BLKDEV_CP_BYTES)) {
        zero_bytes((uint8_t *)medium_out, sizeof(*medium_out));
        return 0;
    }
    return 1;
}

int vos_storage_encode_blkdev_image(
    const struct vos_storage_medium *medium,
    uint8_t image_bytes[VOS_STORAGE_BLKDEV_IMAGE_BYTES])
{
    if (medium == NULL || image_bytes == NULL) {
        return 0;
    }
    zero_bytes(image_bytes, VOS_STORAGE_BLKDEV_HEADER_BYTES);
    image_bytes[0] = 'V';
    image_bytes[1] = 'O';
    image_bytes[2] = 'S';
    image_bytes[3] = 'B';
    image_bytes[4] = 'L';
    image_bytes[5] = 'K';
    image_bytes[6] = '0';
    image_bytes[7] = '1';
    put_le64(image_bytes + 8u, VOS_STORAGE_BLKDEV_BLOCK_BYTES);
    put_le64(image_bytes + 16u, VOS_STORAGE_BLKDEV_BLOCK_COUNT);
    put_le64(image_bytes + 24u, 0u);
    if (!vos_storage_encode_blkdev_medium(
            medium, image_bytes + VOS_STORAGE_BLKDEV_HEADER_BYTES)) {
        zero_bytes(image_bytes, VOS_STORAGE_BLKDEV_IMAGE_BYTES);
        return 0;
    }
    return 1;
}

int vos_storage_decode_blkdev_image(
    const uint8_t image_bytes[VOS_STORAGE_BLKDEV_IMAGE_BYTES],
    struct vos_storage_medium *medium_out)
{
    static const uint8_t blk_magic[8] = {'V', 'O', 'S', 'B', 'L', 'K', '0', '1'};
    if (image_bytes == NULL || medium_out == NULL ||
        !equal_bytes_ct(image_bytes, blk_magic, sizeof(blk_magic)) ||
        get_le64(image_bytes + 8u) != VOS_STORAGE_BLKDEV_BLOCK_BYTES ||
        get_le64(image_bytes + 16u) != VOS_STORAGE_BLKDEV_BLOCK_COUNT ||
        get_le64(image_bytes + 24u) != 0u) {
        return 0;
    }
    return vos_storage_decode_blkdev_medium(
        image_bytes + VOS_STORAGE_BLKDEV_HEADER_BYTES, medium_out);
}

int vos_storage_reopen_blkdev_image(
    const uint8_t image_bytes[VOS_STORAGE_BLKDEV_IMAGE_BYTES],
    struct vos_storage_medium *medium,
    struct vos_storage_store *store,
    struct vos_crypto_core *crypto,
    uint32_t crypto_slot,
    uint64_t expected_domain_id)
{
    if (image_bytes == NULL || medium == NULL || store == NULL) {
        return 0;
    }
    zero_bytes((uint8_t *)store, sizeof(*store));
    if (!vos_storage_decode_blkdev_image(image_bytes, medium)) {
        return 0;
    }
    return vos_storage_reopen(medium, store, crypto, crypto_slot,
                              expected_domain_id);
}

void vos_storage_apply_block_tear(
    uint8_t medium_bytes[VOS_STORAGE_BLKDEV_MEDIUM_BYTES],
    uint32_t block_index,
    const uint8_t old_block[VOS_STORAGE_BLKDEV_BLOCK_BYTES],
    const uint8_t new_block[VOS_STORAGE_BLKDEV_BLOCK_BYTES],
    const uint8_t tear_mask[VOS_STORAGE_BLKDEV_BLOCK_BYTES])
{
    if (medium_bytes == NULL || old_block == NULL || new_block == NULL ||
        tear_mask == NULL || block_index >= VOS_STORAGE_BLKDEV_BLOCK_COUNT) {
        return;
    }
    uint8_t *dst = medium_bytes +
                   (size_t)block_index * VOS_STORAGE_BLKDEV_BLOCK_BYTES;
    for (size_t i = 0u; i < VOS_STORAGE_BLKDEV_BLOCK_BYTES; ++i) {
        dst[i] = (uint8_t)((old_block[i] & (uint8_t)~tear_mask[i]) |
                           (new_block[i] & tear_mask[i]));
    }
}

/* =========================================================================
 * Additive typed VOSTYP01 / VOSEXT01 authenticated publication, reopen,
 * lookup, snapshot retention, and compaction.
 * ========================================================================= */

static int valid_typed_ops(const struct vos_storage_typed_ops *ops)
{
    return ops != NULL &&
           ops->node_encode != NULL &&
           ops->node_decode != NULL &&
           ops->lookup != NULL &&
           ops->lookup_path != NULL &&
           ops->insert != NULL &&
           ops->insert_batch != NULL &&
           ops->del != NULL &&
           ops->compact != NULL &&
           ops->key_encode != NULL &&
           ops->extent_encode != NULL;
}

static int valid_typed_geometry_and_limits(const struct vos_node_geometry *geometry,
                                           const struct vos_tree_limits *limits)
{
    return valid_geometry_and_limits_common(
        geometry, limits, VOS_STORAGE_TYPED_MAX_ARENA_NODES,
        VOS_STORAGE_TYPED_ENTRY_BYTES, VOS_STORAGE_TYPED_MAX_BLOCK_BYTES);
}

static int compare_typed_keys(const struct vos_storage_typed_key *a,
                              const struct vos_storage_typed_key *b)
{
    const uint64_t left[6] = {
        a->domain, a->space, a->kind, a->object, a->attribute, a->version
    };
    const uint64_t right[6] = {
        b->domain, b->space, b->kind, b->object, b->attribute, b->version
    };
    for (size_t i = 0u; i < 6u; ++i) {
        if (left[i] < right[i]) {
            return -1;
        }
        if (left[i] > right[i]) {
            return 1;
        }
    }
    return 0;
}

static int derive_extent_nonce_and_aad(uint64_t domain_id, uint64_t key_epoch,
                                       uint64_t block_address, uint64_t node_id,
                                       uint64_t generation, uint32_t kind,
                                       uint8_t nonce[VOS_CRYPTO_NONCE_BYTES],
                                       uint8_t aad[56])
{
    const struct vos_node_geometry nonce_geom = {
        .fan = 2u,
        .arena_nodes = (uint64_t)VOS_NODE_NONCE_MAX_ID + 1u,
        .block_bytes = VOS_NODE_HEADER_BYTES + 32u
    };
    const struct vos_node_nonce coords = {
        .domain_epoch = (uint32_t)key_epoch,
        .kind = kind,
        .node_id = node_id,
        .generation = generation
    };
    if (!vos_node_derive_nonce(&nonce_geom, &coords, nonce)) {
        return 0;
    }
    write_tag8(aad, "VOSEXTA1");
    put_le64(aad + 8u, domain_id);
    put_le64(aad + 16u, key_epoch);
    put_le64(aad + 24u, block_address);
    put_le64(aad + 32u, node_id);
    put_le64(aad + 40u, generation);
    put_le32(aad + 48u, kind);
    put_le32(aad + 52u, 0u);
    return 1;
}

DEFINE_STORAGE_FRAME_OPS(typed_, vos_storage_typed_journal_frame,
                         VOS_STORAGE_TYPED_MAX_JOURNAL_FRAMES,
                         VOS_STORAGE_TYPED_MAX_BLOCK_BYTES,
                         "VOSTJFR1", "VOSTPMN1")

static int valid_typed_fresh_keys(const struct vos_storage_typed_checkpoint *cp)
{
    if (cp->fresh_key_count > VOS_STORAGE_TYPED_MAX_FRESH_KEYS) {
        return 0;
    }
    for (uint32_t i = 1u; i < cp->fresh_key_count; ++i) {
        if (compare_typed_keys(&cp->fresh_keys[i - 1u], &cp->fresh_keys[i]) >= 0) {
            return 0;
        }
    }
    return 1;
}

static int typed_fresh_key_member(const struct vos_storage_typed_checkpoint *cp,
                                  const struct vos_storage_typed_key *key)
{
    for (uint32_t i = 0u; i < cp->fresh_key_count; ++i) {
        const int cmp = compare_typed_keys(&cp->fresh_keys[i], key);
        if (cmp == 0) {
            return 1;
        }
        if (cmp > 0) {
            break;
        }
    }
    return 0;
}

static int fresh_typed_transaction_allowed(
    const struct vos_storage_typed_checkpoint *cp,
    const struct vos_storage_typed_tx_spec *spec)
{
    if (!valid_typed_fresh_keys(cp) ||
        !fresh_region_allows(spec->commit_mode, cp->fresh_region_id,
                             cp->fresh_region_version, spec->fresh_region_id,
                             spec->fresh_region_version)) {
        return 0;
    }
    const size_t count = spec->op_kind == VOS_STORAGE_OP_COMPACT ? 0u :
        spec->op_kind == VOS_STORAGE_OP_INSERT_BATCH ? spec->entry_count : 1u;
    uint32_t new_keys = 0u;
    for (size_t i = 0u; i < count; ++i) {
        const struct vos_storage_typed_key *key =
            spec->op_kind == VOS_STORAGE_OP_INSERT_BATCH
                ? &spec->entries[i].key : &spec->key;
        const int is_protected = typed_fresh_key_member(cp, key);
        if (spec->commit_mode == VOS_STORAGE_COMMIT_ROLLBACKABLE && is_protected) {
            return 0;
        }
        if (!is_protected) {
            ++new_keys;
        }
    }
    return spec->commit_mode != VOS_STORAGE_COMMIT_FRESH ||
           new_keys <= VOS_STORAGE_TYPED_MAX_FRESH_KEYS - cp->fresh_key_count;
}

static int inherit_typed_fresh_keys(
    struct vos_storage_typed_checkpoint *next,
    const struct vos_storage_typed_checkpoint *prior,
    const struct vos_storage_typed_tx_spec *spec)
{
    if (!fresh_typed_transaction_allowed(prior, spec)) {
        return 0;
    }
    next->fresh_key_count = prior->fresh_key_count;
    for (uint32_t i = 0u; i < prior->fresh_key_count; ++i) {
        next->fresh_keys[i] = prior->fresh_keys[i];
    }
    if (spec->commit_mode != VOS_STORAGE_COMMIT_FRESH ||
        spec->op_kind == VOS_STORAGE_OP_COMPACT) {
        return 1;
    }
    const size_t count = spec->op_kind == VOS_STORAGE_OP_INSERT_BATCH
        ? spec->entry_count : 1u;
    for (size_t i = 0u; i < count; ++i) {
        const struct vos_storage_typed_key *key =
            spec->op_kind == VOS_STORAGE_OP_INSERT_BATCH
                ? &spec->entries[i].key : &spec->key;
        if (typed_fresh_key_member(next, key)) {
            continue;
        }
        uint32_t at = next->fresh_key_count;
        while (at > 0u && compare_typed_keys(&next->fresh_keys[at - 1u], key) > 0) {
            next->fresh_keys[at] = next->fresh_keys[at - 1u];
            --at;
        }
        next->fresh_keys[at] = *key;
        ++next->fresh_key_count;
    }
    return 1;
}

DEFINE_STORAGE_CHECKPOINT_OPS(
    TYPED_CP_SERIAL_BYTES,
    CHECKPOINT_HEADER_BYTES +
        VOS_STORAGE_TYPED_MAX_FRESH_KEYS * VOS_STORAGE_TYPED_KEY_BYTES +
        VOS_STORAGE_MAX_SNAPSHOTS * 8u + VOS_STORAGE_MAX_DEADLIST * 16u +
        VOS_STORAGE_TYPED_MAX_ARENA_NODES * CHECKPOINT_AUTH_BYTES,
    serialize_typed_checkpoint, sign_typed_checkpoint, verify_typed_checkpoint_mac,
    vos_storage_typed_checkpoint,
    const struct vos_storage_typed_ops *ops VOS_SP_COMMA,
    ops VOS_SP_COMMA,
    VOS_STORAGE_TYPED_MAX_ARENA_NODES, VOS_STORAGE_TYPED_MAX_JOURNAL_FRAMES,
    "VOSTCHK1", valid_typed_fresh_keys,
    if (!ops->key_encode(&cp->fresh_keys[i], buf + at, VOS_STORAGE_TYPED_KEY_BYTES)) {
        return 0u;
    }
    at += VOS_STORAGE_TYPED_KEY_BYTES)

static int seal_typed_node_block(
    const struct vos_storage_typed_ops *ops,
    const struct vos_crypto_core *crypto,
    uint32_t slot,
    uint64_t domain_id,
    uint64_t key_epoch,
    const struct vos_node_geometry *geometry,
    uint64_t node_id,
    uint64_t generation,
    const uint8_t *plain_block,
    uint32_t *kind_out,
    uint8_t *cipher_out,
    uint8_t tag_out[VOS_CRYPTO_TAG_BYTES],
    uint8_t digest_out[VOS_CRYPTO_DIGEST_BYTES])
{
    struct vos_typed_node decoded = {0};
    if (!ops->node_decode(geometry, node_id, generation, plain_block,
                          geometry->block_bytes, &decoded) ||
        !seal_node_block_crypto("VOSTNAD1", crypto, slot, domain_id, key_epoch,
                                geometry, node_id, generation, decoded.kind,
                                plain_block, cipher_out, tag_out, digest_out)) {
        return 0;
    }
    *kind_out = decoded.kind;
    return 1;
}

static int open_typed_node_block(
    const struct vos_storage_typed_ops *ops,
    const struct vos_crypto_core *crypto,
    uint32_t slot,
    const struct vos_node_geometry *geometry,
    uint64_t domain_id,
    uint64_t key_epoch,
    uint64_t node_id,
    const struct vos_storage_block_auth *auth,
    const uint8_t *cipher_block,
    uint8_t *plain_out,
    struct vos_typed_node *node_out)
{
    if (!open_node_block_crypto("VOSTNAD1", crypto, slot, geometry, domain_id,
                                key_epoch, node_id, auth, cipher_block, plain_out)) {
        return 0;
    }
    if (!ops->node_decode(geometry, node_id, auth->generation, plain_out,
                          geometry->block_bytes, node_out) ||
        node_out->kind != auth->kind) {
        zero_bytes(plain_out, geometry->block_bytes);
        return 0;
    }
    return 1;
}

DEFINE_STORAGE_ACTIVE_OPS(
    vos_storage_typed_store, vos_storage_typed_checkpoint,
    retain_active_typed_checkpoint, matches_active_typed_checkpoint, persist_typed_store,
    valid_typed_ops(&store->ops),
    verify_typed_checkpoint_mac(&store->ops, store->crypto, store->crypto_slot,
                                store->domain_id, store->key_epoch,
                                store->medium->geometry.arena_nodes, cp))

static int valid_typed_tx_spec(const struct vos_storage_typed_ops *ops,
                               const struct vos_storage_typed_tx_spec *spec)
{
    uint8_t extent_buf[VOS_STORAGE_EXTENT_BYTES];
    if (spec == NULL || !valid_typed_ops(ops) ||
        (spec->commit_mode != VOS_STORAGE_COMMIT_ROLLBACKABLE &&
         spec->commit_mode != VOS_STORAGE_COMMIT_FRESH)) {
        return 0;
    }
    if (spec->commit_mode == VOS_STORAGE_COMMIT_FRESH &&
        spec->fresh_region_version == 0u) {
        return 0;
    }
    if (spec->op_kind == VOS_STORAGE_OP_INSERT) {
        return ops->extent_encode(&spec->extent, extent_buf, sizeof(extent_buf));
    }
    if (spec->op_kind == VOS_STORAGE_OP_DELETE ||
        spec->op_kind == VOS_STORAGE_OP_COMPACT) {
        return 1;
    }
    if (spec->op_kind == VOS_STORAGE_OP_INSERT_BATCH) {
        if (spec->entry_count == 0u || spec->entry_count > VOS_STORAGE_MAX_BATCH) {
            return 0;
        }
        for (size_t i = 0u; i < spec->entry_count; ++i) {
            if (!ops->extent_encode(&spec->entries[i].extent, extent_buf, sizeof(extent_buf))) {
                return 0;
            }
            if (i != 0u && compare_typed_keys(&spec->entries[i - 1u].key,
                                              &spec->entries[i].key) >= 0) {
                return 0;
            }
        }
        return 1;
    }
    return 0;
}

static int mark_reachable_typed_nodes(
    const struct vos_storage_typed_ops *ops,
    const struct vos_node_geometry *geometry,
    const uint8_t *plain_arena,
    const uint64_t *generations,
    uint64_t used,
    uint64_t node_id,
    uint32_t height,
    uint32_t *remaining,
    uint8_t reachable[VOS_STORAGE_TYPED_MAX_ARENA_NODES])
{
    if (*remaining == 0u || node_id >= used || node_id >= VOS_STORAGE_TYPED_MAX_ARENA_NODES) {
        return 0;
    }
    --(*remaining);
    reachable[(size_t)node_id] = 1u;
    struct vos_typed_node node = {0};
    if (!ops->node_decode(geometry, node_id, generations[(size_t)node_id],
                          plain_arena + (size_t)node_id * geometry->block_bytes,
                          geometry->block_bytes, &node)) {
        return 0;
    }
    if (node.kind == VOS_NODE_LEAF) {
        return height == 0u;
    }
    if (height == 0u) {
        return 0;
    }
    for (uint32_t i = 0u; i < node.count; ++i) {
        if (!mark_reachable_typed_nodes(ops, geometry, plain_arena, generations,
                                        used, node.children[i], height - 1u,
                                        remaining, reachable)) {
            return 0;
        }
    }
    return 1;
}

DEFINE_STORAGE_FORMAT_FN(
    vos_storage_typed_format_ops, vos_storage_typed_medium, vos_storage_typed_store,
    vos_storage_typed_checkpoint, vos_typed_node,
    VOS_SP_COMMA const struct vos_storage_typed_ops *ops,
    !valid_typed_ops(ops), store->ops = *ops, valid_typed_geometry_and_limits,
    store->ops.node_encode(geometry, &root_node, store->plain_arena, geometry->block_bytes),
    seal_typed_node_block(&store->ops, crypto, crypto_slot, domain_id, key_epoch,
                          geometry, 0u, initial_generation, store->plain_arena,
                          &root_kind, medium->arena_ciphertext, root_tag, root_digest),
    compute_typed_payload_manifest,
    sign_typed_checkpoint(&store->ops, crypto, crypto_slot, cp),
    retain_active_typed_checkpoint)

int vos_storage_typed_attach_persistence(struct vos_storage_typed_store *store,
                                           vos_storage_typed_persistor persist,
                                           void *opaque)
{
    if (store == NULL || !store->open || store->attempt.reserved) {
        return 0;
    }
    store->persist = persist;
    store->persistence = opaque;
    return 1;
}

DEFINE_STORAGE_RESERVE_FN(
    vos_storage_typed_reserve, vos_storage_typed_store, vos_storage_typed_medium,
    vos_storage_typed_tx_spec, valid_typed_tx_spec(&store->ops, spec),
    matches_active_typed_checkpoint, fresh_typed_transaction_allowed, 0,
    persist_typed_store)

static int relocate_compacted_typed_nodes(
    struct vos_storage_typed_store *store,
    uint64_t old_used,
    const struct vos_tree_update_result *raw_result)
{
    struct vos_storage_typed_medium *medium = store->medium;
    struct vos_storage_typed_attempt *att = &store->attempt;
    const size_t block_bytes = medium->geometry.block_bytes;
    if (raw_result->used <= old_used) {
        return 0;
    }
    const uint64_t new_used = raw_result->used - old_used;
    if (new_used == 0u || new_used > medium->geometry.arena_nodes ||
        raw_result->root < old_used || raw_result->root >= raw_result->used) {
        return 0;
    }
    zero_bytes(att->staged_plaintext,
               (size_t)medium->geometry.arena_nodes * block_bytes);
    for (uint32_t i = 0u; i < VOS_STORAGE_TYPED_MAX_ARENA_NODES; ++i) {
        att->staged_generations[i] = 0u;
        zero_bytes((uint8_t *)&att->staged_auth[i], sizeof(att->staged_auth[i]));
    }
    att->staged_dead_count = 0u;

    for (uint64_t idx = 0u; idx < new_used; ++idx) {
        const uint64_t src_id = old_used + idx;
        struct vos_typed_node node = {0};
        if (!store->ops.node_decode(&medium->geometry, src_id, att->generation,
                                    store->compact_scratch + (size_t)src_id * block_bytes,
                                    block_bytes, &node)) {
            return 0;
        }
        node.node_id = idx;
        if (node.kind == VOS_NODE_BRANCH) {
            for (uint32_t c = 0u; c < node.count; ++c) {
                if (node.children[c] < old_used || node.children[c] >= raw_result->used) {
                    return 0;
                }
                node.children[c] -= old_used;
            }
        }
        if (!store->ops.node_encode(&medium->geometry, &node,
                                    att->staged_plaintext + (size_t)idx * block_bytes,
                                    block_bytes)) {
            return 0;
        }
        att->staged_generations[(size_t)idx] = att->generation;
    }
    att->result.root = raw_result->root - old_used;
    att->result.used = new_used;
    att->result.height = raw_result->height;
    return 1;
}

DEFINE_STORAGE_STAGE_HELPERS(
    typed, vos_storage_typed_store, vos_storage_typed_medium,
    vos_storage_typed_attempt, vos_storage_typed_journal_frame, vos_typed_node,
    VOS_STORAGE_TYPED_MAX_JOURNAL_FRAMES, VOS_STORAGE_TYPED_MAX_BLOCK_BYTES,
    valid_typed_ops(&store->ops),
    verify_typed_checkpoint_mac(&store->ops, store->crypto, store->crypto_slot,
                                store->domain_id, store->key_epoch,
                                medium->geometry.arena_nodes, &medium->checkpoint),
    seal_typed_node_block(&store->ops, store->crypto, store->crypto_slot,
                          store->domain_id, store->key_epoch, &medium->geometry,
                          id, att->generation,
                          att->staged_plaintext + (size_t)id * block_bytes,
                          &kind, frame->ciphertext, frame->tag, frame->content_digest),
    sign_typed_journal_frame, verify_typed_journal_frame,
    open_typed_node_block(&store->ops, store->crypto, store->crypto_slot,
                          &medium->geometry, store->domain_id, store->key_epoch,
                          frame->target_node_id,
                          &att->staged_auth[(size_t)frame->target_node_id],
                          frame->ciphertext, opened, &decoded))

int vos_storage_typed_stage(struct vos_storage_typed_store *store,
                              uint64_t caller_domain)
{
    struct vos_tree_arena arena = {0};
    struct vos_tree_limits cur_limits = {0};
    if (!stage_typed_prepare(store, caller_domain, &arena, &cur_limits)) {
        return 0;
    }
    struct vos_storage_typed_medium *medium = store->medium;
    struct vos_storage_typed_attempt *att = &store->attempt;
    const size_t block_bytes = medium->geometry.block_bytes;
    const uint64_t latest_snap = latest_snapshot_gen(
        medium->checkpoint.snapshots, medium->checkpoint.snapshot_count);
    const int has_snapshot = medium->checkpoint.snapshot_count != 0u;
    const int compact = att->spec.op_kind == VOS_STORAGE_OP_COMPACT;

    int update_ok = 0;
    if (att->spec.op_kind == VOS_STORAGE_OP_INSERT) {
        update_ok = store->ops.insert(&arena, &cur_limits, store->committed_root,
                                      att->generation, &att->spec.key,
                                      &att->spec.extent, &att->result);
    } else if (att->spec.op_kind == VOS_STORAGE_OP_INSERT_BATCH) {
        update_ok = store->ops.insert_batch(&arena, &cur_limits, store->committed_root,
                                            att->generation, att->spec.entries,
                                            att->spec.entry_count, &att->result);
    } else if (att->spec.op_kind == VOS_STORAGE_OP_DELETE) {
        update_ok = store->ops.del(&arena, &cur_limits, store->committed_root,
                                   att->generation, &att->spec.key, &att->result);
    } else if (compact && !has_snapshot) {
        const uint64_t scratch_nodes = store->committed_used + medium->geometry.arena_nodes;
        if (scratch_nodes > 2u * VOS_STORAGE_TYPED_MAX_ARENA_NODES) {
            return 0;
        }
        zero_bytes(store->compact_scratch, (size_t)scratch_nodes * block_bytes);
        copy_bytes(store->compact_scratch, store->plain_arena,
                   (size_t)store->committed_used * block_bytes);
        for (uint64_t i = 0u; i < scratch_nodes; ++i) {
            store->compact_generations[(size_t)i] =
                i < store->committed_used ? store->plain_generations[(size_t)i] : 0u;
        }
        struct vos_tree_arena scratch = {0};
        scratch.geometry = medium->geometry;
        scratch.geometry.arena_nodes = scratch_nodes;
        scratch.used = store->committed_used;
        scratch.bytes = store->compact_scratch;
        scratch.length = (size_t)scratch_nodes * block_bytes;
        scratch.generations = store->compact_generations;
        scratch.generation_count = (size_t)scratch_nodes;
        struct vos_tree_update_result raw_result = {0};
        update_ok = store->ops.compact(&scratch, &cur_limits, store->committed_root,
                                       att->generation, &raw_result) &&
                    relocate_compacted_typed_nodes(store, store->committed_used, &raw_result);
    } else if (compact) {
        update_ok = store->ops.compact(&arena, &cur_limits, store->committed_root,
                                       att->generation, &att->result);
    }
    if (!update_ok || att->result.used == 0u ||
        att->result.used > medium->geometry.arena_nodes) {
        return 0;
    }

    if (!(compact && !has_snapshot)) {
        uint8_t reachable[VOS_STORAGE_TYPED_MAX_ARENA_NODES] = {0};
        uint32_t rem = VOS_TREE_MAX_VISITS;
        if (!mark_reachable_typed_nodes(&store->ops, &medium->geometry,
                                        att->staged_plaintext, att->staged_generations,
                                        att->result.used, att->result.root,
                                        att->result.height, &rem, reachable)) {
            return 0;
        }
        for (uint64_t id = 0u; id < store->committed_used; ++id) {
            if (!medium->checkpoint.auth[(size_t)id].valid ||
                reachable[(size_t)id] ||
                att->staged_generations[(size_t)id] == att->generation) {
                continue;
            }
            const uint64_t birth = store->plain_generations[(size_t)id];
            if (!retire_dead_node_common(id, birth, latest_snap, has_snapshot,
                                         &att->staged_auth[(size_t)id],
                                         &att->staged_dead_count,
                                         att->staged_deadlist)) {
                return 0;
            }
        }
    }
    return seal_typed_staged_frames(store);
}

static int verify_staged_typed_candidate(const struct vos_storage_typed_store *store)
{
    const struct vos_storage_typed_attempt *att = &store->attempt;
    struct vos_tree_image candidate = {0};
    struct vos_tree_limits candidate_limits = {0};
    struct vos_storage_extent checked = {0};

    if (!verify_typed_staged_frames(store, &candidate, &candidate_limits)) {
        return 0;
    }
    if (att->spec.op_kind == VOS_STORAGE_OP_COMPACT) {
        const struct vos_storage_typed_key zero_key = {0};
        return store->ops.lookup(&candidate, &candidate_limits,
                                 att->result.root, &zero_key, &checked) != VOS_TREE_REFUSED;
    }
    const size_t queries = att->spec.op_kind == VOS_STORAGE_OP_INSERT_BATCH
        ? att->spec.entry_count : 1u;
    for (size_t i = 0u; i < queries; ++i) {
        const struct vos_storage_typed_key *key =
            att->spec.op_kind == VOS_STORAGE_OP_INSERT_BATCH
                ? &att->spec.entries[i].key : &att->spec.key;
        const int status = (i == 0u)
            ? store->ops.lookup(&candidate, &candidate_limits, att->result.root, key, &checked)
            : store->ops.lookup_path(&candidate, &candidate_limits, att->result.root, key, &checked);
        if (att->spec.op_kind == VOS_STORAGE_OP_DELETE) {
            if (status != VOS_TREE_MISSING) {
                return 0;
            }
        } else {
            uint8_t expected_ext[VOS_STORAGE_EXTENT_BYTES];
            uint8_t actual_ext[VOS_STORAGE_EXTENT_BYTES];
            const struct vos_storage_extent *want =
                att->spec.op_kind == VOS_STORAGE_OP_INSERT_BATCH
                    ? &att->spec.entries[i].extent : &att->spec.extent;
            if (status != VOS_TREE_FOUND ||
                !store->ops.extent_encode(want, expected_ext, sizeof(expected_ext)) ||
                !store->ops.extent_encode(&checked, actual_ext, sizeof(actual_ext)) ||
                !equal_bytes_ct(expected_ext, actual_ext, sizeof(expected_ext))) {
                return 0;
            }
        }
    }
    return 1;
}

DEFINE_STORAGE_PUBLISH_FN(
    vos_storage_typed_publish, vos_storage_typed_store, vos_storage_typed_medium,
    vos_storage_typed_attempt, vos_storage_typed_checkpoint,
    verify_staged_typed_candidate, inherit_typed_fresh_keys,
    compute_typed_payload_manifest,
    sign_typed_checkpoint(&store->ops, store->crypto, store->crypto_slot, &next_cp),
    persist_typed_store, retain_active_typed_checkpoint)

DEFINE_STORAGE_REOPEN_FN(
    vos_storage_typed_reopen_ops, vos_storage_typed_medium, vos_storage_typed_store,
    vos_storage_typed_checkpoint, vos_storage_typed_journal_frame, vos_typed_node,
    VOS_STORAGE_TYPED_MAX_JOURNAL_FRAMES, VOS_STORAGE_TYPED_MAX_BLOCK_BYTES,
    VOS_SP_COMMA const struct vos_storage_typed_ops *ops,
    !valid_typed_ops(ops), valid_typed_geometry_and_limits, store->ops = *ops,
    verify_typed_checkpoint_mac, &store->ops VOS_SP_COMMA,
    compute_typed_payload_manifest, verify_typed_journal_frame,
    open_typed_node_block,
    (store->ops.lookup(&image, &check_limits, cp->root,
                       &(const struct vos_storage_typed_key){0},
                       &(struct vos_storage_extent){0})),
    retain_active_typed_checkpoint)

DEFINE_STORAGE_LOOKUP_FN(
    vos_storage_typed_lookup, vos_storage_typed_store, vos_storage_typed_medium,
    vos_storage_typed_checkpoint, const struct vos_storage_typed_key *key,
    struct vos_storage_extent *extent_out, extent_out,
    VOS_STORAGE_TYPED_MAX_BLOCK_BYTES, vos_typed_node,
    struct vos_storage_typed_key, {0}, struct vos_storage_extent, {0},
    matches_active_typed_checkpoint, open_typed_node_block,
    &store->ops VOS_SP_COMMA, compare_typed_keys, key, extents, children)

DEFINE_STORAGE_RETAIN_SNAPSHOT_FN(
    vos_storage_typed_retain_snapshot, vos_storage_typed_store,
    vos_storage_typed_medium, vos_storage_typed_checkpoint,
    matches_active_typed_checkpoint, verify_typed_checkpoint_mac,
    &store->ops VOS_SP_COMMA,
    sign_typed_checkpoint(&store->ops, store->crypto, store->crypto_slot, &next),
    persist_typed_store, retain_active_typed_checkpoint)

int vos_storage_typed_object_digest(const struct vos_storage_typed_store *store,
                                      const uint8_t *bytes,
                                      size_t length,
                                      uint8_t digest_out[VOS_CRYPTO_DIGEST_BYTES])
{
    return store != NULL &&
           object_digest_common(store->open, store->crypto, store->crypto_slot,
                                bytes, length, digest_out);
}

int vos_storage_typed_seal_extent(const struct vos_storage_typed_store *store,
                                    uint64_t block_address,
                                    uint64_t node_id,
                                    uint64_t generation,
                                    uint32_t kind,
                                    const uint8_t *plaintext,
                                    size_t length,
                                    uint8_t *ciphertext_out,
                                    struct vos_storage_extent *extent_out)
{
    if (store == NULL || !store->open || store->medium == NULL ||
        store->crypto == NULL || extent_out == NULL ||
        length > VOS_STORAGE_TYPED_MAX_EXTENT_BYTES ||
        (length != 0u && (plaintext == NULL || ciphertext_out == NULL)) ||
        node_id > VOS_NODE_NONCE_MAX_ID ||
        store->key_epoch > VOS_NODE_NONCE_MAX_DOMAIN ||
        (kind != VOS_NODE_LEAF && kind != VOS_NODE_BRANCH)) {
        return 0;
    }
    uint8_t nonce[VOS_CRYPTO_NONCE_BYTES];
    uint8_t aad[56];
    struct vos_storage_extent ext = {
        .block_address = block_address,
        .byte_length = (uint64_t)length,
        .node_id = node_id,
        .generation = generation,
        .domain_epoch = (uint32_t)store->key_epoch,
        .kind = kind
    };
    if (!derive_extent_nonce_and_aad(store->domain_id, store->key_epoch,
                                     block_address, node_id, generation,
                                     kind, nonce, aad)) {
        return 0;
    }
    if (!vos_crypto_core_seal(store->crypto, store->crypto_slot, nonce,
                              aad, sizeof(aad), plaintext, length,
                              ciphertext_out, ext.tag) ||
        !vos_crypto_core_keyed_digest(store->crypto, store->crypto_slot,
                                      plaintext, length, ext.content_digest)) {
        return 0;
    }
    *extent_out = ext;
    return 1;
}

int vos_storage_typed_read_extent(const struct vos_storage_typed_store *store,
                                    uint64_t caller_domain,
                                    const struct vos_storage_typed_key *key,
                                    const uint8_t *ciphertext,
                                    size_t ciphertext_length,
                                    uint8_t *plaintext_out,
                                    size_t plaintext_capacity,
                                    size_t *length_out)
{
    struct vos_storage_extent ext = {0};
    if (store == NULL || !store->open || store->medium == NULL ||
        store->crypto == NULL || key == NULL || length_out == NULL ||
        caller_domain != store->domain_id ||
        vos_storage_typed_lookup(store, caller_domain, key, &ext) != VOS_TREE_FOUND) {
        return 0;
    }
    if (ext.byte_length > VOS_STORAGE_TYPED_MAX_EXTENT_BYTES ||
        ciphertext_length != (size_t)ext.byte_length ||
        plaintext_capacity < ciphertext_length ||
        ext.domain_epoch != (uint32_t)store->key_epoch ||
        (ciphertext_length != 0u && (ciphertext == NULL || plaintext_out == NULL))) {
        return 0;
    }
    uint8_t nonce[VOS_CRYPTO_NONCE_BYTES];
    uint8_t aad[56];
    uint8_t plain_buf[VOS_STORAGE_TYPED_MAX_EXTENT_BYTES];
    uint8_t actual_digest[VOS_CRYPTO_DIGEST_BYTES];
    if (!derive_extent_nonce_and_aad(store->domain_id, store->key_epoch,
                                     ext.block_address, ext.node_id,
                                     ext.generation, ext.kind, nonce, aad)) {
        return 0;
    }
    if (!vos_crypto_core_open(store->crypto, store->crypto_slot, nonce,
                              aad, sizeof(aad), ciphertext, ciphertext_length,
                              ext.tag, plain_buf) ||
        !vos_crypto_core_keyed_digest(store->crypto, store->crypto_slot,
                                      plain_buf, ciphertext_length, actual_digest) ||
        !equal_bytes_ct(actual_digest, ext.content_digest, VOS_CRYPTO_DIGEST_BYTES)) {
        zero_bytes(plain_buf, sizeof(plain_buf));
        return 0;
    }
    if (ciphertext_length != 0u) {
        copy_bytes(plaintext_out, plain_buf, ciphertext_length);
    }
    zero_bytes(plain_buf, sizeof(plain_buf));
    *length_out = ciphertext_length;
    return 1;
}
