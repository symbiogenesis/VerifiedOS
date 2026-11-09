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

static int valid_geometry_and_limits(const struct vos_node_geometry *geometry,
                                     const struct vos_tree_limits *limits)
{
    return geometry != NULL && limits != NULL &&
           geometry->fan >= 2u && geometry->fan <= VOS_NODE_MAX_FAN &&
           geometry->arena_nodes >= 2u &&
           geometry->arena_nodes <= VOS_STORAGE_MAX_ARENA_NODES &&
           geometry->block_bytes >= VOS_NODE_HEADER_BYTES + 16u * geometry->fan &&
           geometry->block_bytes <= VOS_STORAGE_MAX_BLOCK_BYTES &&
           limits->height <= limits->depth_limit &&
           limits->depth_limit <= VOS_TREE_MAX_DEPTH &&
           limits->visit_limit > 0u &&
           limits->visit_limit <= VOS_TREE_MAX_VISITS;
}

static void build_node_aad(uint64_t domain_id, uint64_t key_epoch,
                           uint64_t node_id, uint64_t generation,
                           uint32_t kind, uint8_t aad[48])
{
    aad[0] = 'V';
    aad[1] = 'O';
    aad[2] = 'S';
    aad[3] = 'N';
    aad[4] = 'A';
    aad[5] = 'A';
    aad[6] = 'D';
    aad[7] = '1';
    put_le64(aad + 8u, domain_id);
    put_le64(aad + 16u, key_epoch);
    put_le64(aad + 24u, node_id);
    put_le64(aad + 32u, generation);
    put_le32(aad + 40u, kind);
    put_le32(aad + 44u, 0u);
}

static void serialize_nonce_record(const struct vos_storage_nonce_record *rec,
                                   uint8_t buf[40])
{
    buf[0] = 'V';
    buf[1] = 'O';
    buf[2] = 'S';
    buf[3] = 'N';
    buf[4] = 'O';
    buf[5] = 'N';
    buf[6] = 'C';
    buf[7] = '1';
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

enum {
    FRAME_SERIAL_BYTES = 8u + 8u + 8u + 8u + 4u + 4u + 8u +
                         VOS_CRYPTO_TAG_BYTES + VOS_CRYPTO_DIGEST_BYTES +
                         VOS_STORAGE_MAX_BLOCK_BYTES
};

static size_t serialize_journal_frame(uint64_t domain_id, uint64_t key_epoch,
                                      size_t block_bytes,
                                      const struct vos_storage_journal_frame *frame,
                                      uint8_t buf[FRAME_SERIAL_BYTES])
{
    buf[0] = 'V';
    buf[1] = 'O';
    buf[2] = 'S';
    buf[3] = 'J';
    buf[4] = 'F';
    buf[5] = 'R';
    buf[6] = 'M';
    buf[7] = '1';
    put_le64(buf + 8u, domain_id);
    put_le64(buf + 16u, key_epoch);
    put_le64(buf + 24u, frame->tx_generation);
    put_le32(buf + 32u, frame->frame_index);
    put_le32(buf + 36u, frame->kind);
    put_le64(buf + 40u, frame->target_node_id);
    copy_bytes(buf + 48u, frame->tag, VOS_CRYPTO_TAG_BYTES);
    copy_bytes(buf + 48u + VOS_CRYPTO_TAG_BYTES,
               frame->content_digest, VOS_CRYPTO_DIGEST_BYTES);
    copy_bytes(buf + 48u + VOS_CRYPTO_TAG_BYTES + VOS_CRYPTO_DIGEST_BYTES,
               frame->ciphertext, block_bytes);
    return 48u + VOS_CRYPTO_TAG_BYTES + VOS_CRYPTO_DIGEST_BYTES + block_bytes;
}

static int sign_journal_frame(const struct vos_crypto_core *crypto,
                              uint32_t slot, uint64_t domain_id,
                              uint64_t key_epoch, size_t block_bytes,
                              struct vos_storage_journal_frame *frame)
{
    uint8_t buf[FRAME_SERIAL_BYTES];
    const size_t len = serialize_journal_frame(domain_id, key_epoch,
                                               block_bytes, frame, buf);
    return vos_crypto_core_commit_mac(crypto, slot, buf, len, frame->frame_mac);
}

static int verify_journal_frame(const struct vos_crypto_core *crypto,
                                uint32_t slot, uint64_t domain_id,
                                uint64_t key_epoch, size_t block_bytes,
                                const struct vos_storage_journal_frame *frame)
{
    uint8_t buf[FRAME_SERIAL_BYTES];
    if (frame == NULL || !frame->occupied) {
        return 0;
    }
    const size_t len = serialize_journal_frame(domain_id, key_epoch,
                                               block_bytes, frame, buf);
    return vos_crypto_core_verify_commit_mac(crypto, slot, buf, len, frame->frame_mac);
}

enum {
    MANIFEST_ITEM_BYTES = 4u + 4u + 8u + 8u + VOS_CRYPTO_TAG_BYTES + VOS_CRYPTO_DIGEST_BYTES,
    MANIFEST_SERIAL_BYTES = 32u + VOS_STORAGE_MAX_JOURNAL_FRAMES * MANIFEST_ITEM_BYTES
};

static int compute_payload_manifest(const struct vos_crypto_core *crypto,
                                    uint32_t slot, uint64_t domain_id,
                                    uint64_t tx_generation,
                                    const struct vos_storage_journal_frame *frames,
                                    uint32_t frame_count,
                                    uint8_t out[VOS_CRYPTO_DIGEST_BYTES])
{
    uint8_t buf[MANIFEST_SERIAL_BYTES];
    if (frame_count > VOS_STORAGE_MAX_JOURNAL_FRAMES) {
        return 0;
    }
    buf[0] = 'V';
    buf[1] = 'O';
    buf[2] = 'S';
    buf[3] = 'P';
    buf[4] = 'M';
    buf[5] = 'A';
    buf[6] = 'N';
    buf[7] = '1';
    put_le64(buf + 8u, domain_id);
    put_le64(buf + 16u, tx_generation);
    put_le32(buf + 24u, frame_count);
    put_le32(buf + 28u, 0u);
    size_t at = 32u;
    for (uint32_t i = 0u; i < frame_count; ++i) {
        put_le32(buf + at, frames[i].frame_index);
        put_le32(buf + at + 4u, frames[i].kind);
        put_le64(buf + at + 8u, frames[i].target_node_id);
        put_le64(buf + at + 16u, frames[i].tx_generation);
        copy_bytes(buf + at + 24u, frames[i].tag, VOS_CRYPTO_TAG_BYTES);
        copy_bytes(buf + at + 24u + VOS_CRYPTO_TAG_BYTES,
                   frames[i].content_digest, VOS_CRYPTO_DIGEST_BYTES);
        at += MANIFEST_ITEM_BYTES;
    }
    return vos_crypto_core_commit_mac(crypto, slot, buf, at, out);
}

enum {
    CHECKPOINT_HEADER_BYTES = 8u + 4u + 4u + 8u + 8u + 8u + 8u + 4u + 4u + 8u +
                              8u + 8u + 8u + 3u * VOS_CRYPTO_DIGEST_BYTES + 4u + 4u,
    CHECKPOINT_AUTH_BYTES = 4u + 4u + 8u + VOS_CRYPTO_TAG_BYTES,
    CHECKPOINT_SERIAL_BYTES = CHECKPOINT_HEADER_BYTES +
                              VOS_STORAGE_MAX_SNAPSHOTS * 8u +
                              VOS_STORAGE_MAX_DEADLIST * 16u +
                              VOS_STORAGE_MAX_ARENA_NODES * CHECKPOINT_AUTH_BYTES
};

static size_t serialize_checkpoint(const struct vos_storage_checkpoint *cp,
                                   uint8_t buf[CHECKPOINT_SERIAL_BYTES])
{
    buf[0] = 'V';
    buf[1] = 'O';
    buf[2] = 'S';
    buf[3] = 'C';
    buf[4] = 'H';
    buf[5] = 'K';
    buf[6] = 'P';
    buf[7] = '1';
    put_le32(buf + 8u, cp->committed);
    put_le32(buf + 12u, cp->commit_mode);
    put_le64(buf + 16u, cp->domain_id);
    put_le64(buf + 24u, cp->key_epoch);
    put_le64(buf + 32u, cp->generation);
    put_le64(buf + 40u, cp->root);
    put_le32(buf + 48u, cp->height);
    put_le32(buf + 52u, cp->frame_count);
    put_le64(buf + 56u, cp->used);
    put_le64(buf + 64u, cp->fresh_region_id);
    put_le64(buf + 72u, cp->fresh_region_version);
    put_le64(buf + 80u, cp->sealed_epoch);
    size_t at = 88u;
    copy_bytes(buf + at, cp->epoch_root, VOS_CRYPTO_DIGEST_BYTES);
    at += VOS_CRYPTO_DIGEST_BYTES;
    copy_bytes(buf + at, cp->root_digest, VOS_CRYPTO_DIGEST_BYTES);
    at += VOS_CRYPTO_DIGEST_BYTES;
    copy_bytes(buf + at, cp->payload_manifest_digest, VOS_CRYPTO_DIGEST_BYTES);
    at += VOS_CRYPTO_DIGEST_BYTES;
    put_le32(buf + at, cp->snapshot_count);
    put_le32(buf + at + 4u, cp->dead_count);
    at += 8u;
    for (uint32_t i = 0u; i < cp->snapshot_count && i < VOS_STORAGE_MAX_SNAPSHOTS; ++i) {
        put_le64(buf + at, cp->snapshots[i]);
        at += 8u;
    }
    for (uint32_t i = 0u; i < cp->dead_count && i < VOS_STORAGE_MAX_DEADLIST; ++i) {
        put_le64(buf + at, cp->deadlist[i].node_id);
        put_le64(buf + at + 8u, cp->deadlist[i].birth_generation);
        at += 16u;
    }
    for (uint64_t i = 0u; i < cp->used && i < VOS_STORAGE_MAX_ARENA_NODES; ++i) {
        put_le32(buf + at, cp->auth[(size_t)i].valid);
        put_le32(buf + at + 4u, cp->auth[(size_t)i].kind);
        put_le64(buf + at + 8u, cp->auth[(size_t)i].generation);
        copy_bytes(buf + at + 16u, cp->auth[(size_t)i].tag, VOS_CRYPTO_TAG_BYTES);
        at += CHECKPOINT_AUTH_BYTES;
    }
    return at;
}

static int sign_checkpoint(const struct vos_crypto_core *crypto,
                           uint32_t slot,
                           struct vos_storage_checkpoint *cp)
{
    uint8_t buf[CHECKPOINT_SERIAL_BYTES];
    if (cp->used == 0u || cp->used > VOS_STORAGE_MAX_ARENA_NODES ||
        cp->snapshot_count > VOS_STORAGE_MAX_SNAPSHOTS ||
        cp->dead_count > VOS_STORAGE_MAX_DEADLIST ||
        cp->frame_count > VOS_STORAGE_MAX_JOURNAL_FRAMES) {
        return 0;
    }
    const size_t len = serialize_checkpoint(cp, buf);
    return vos_crypto_core_commit_mac(crypto, slot, buf, len, cp->checkpoint_mac);
}

static int verify_checkpoint_mac(const struct vos_crypto_core *crypto,
                                 uint32_t slot,
                                 uint64_t expected_domain,
                                 uint64_t expected_epoch,
                                 uint64_t max_arena_nodes,
                                 const struct vos_storage_checkpoint *cp)
{
    uint8_t buf[CHECKPOINT_SERIAL_BYTES];
    if (cp == NULL || !cp->committed ||
        cp->domain_id != expected_domain ||
        cp->key_epoch != expected_epoch ||
        cp->generation == 0u ||
        cp->used == 0u || cp->used > max_arena_nodes ||
        cp->used > VOS_STORAGE_MAX_ARENA_NODES ||
        cp->root >= cp->used ||
        cp->frame_count > VOS_STORAGE_MAX_JOURNAL_FRAMES ||
        cp->snapshot_count > VOS_STORAGE_MAX_SNAPSHOTS ||
        cp->dead_count > VOS_STORAGE_MAX_DEADLIST ||
        (cp->commit_mode != VOS_STORAGE_COMMIT_ROLLBACKABLE &&
         cp->commit_mode != VOS_STORAGE_COMMIT_FRESH)) {
        return 0;
    }
    const size_t len = serialize_checkpoint(cp, buf);
    return vos_crypto_core_verify_commit_mac(crypto, slot, buf, len, cp->checkpoint_mac);
}

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
    struct vos_node_nonce coords = {0};
    uint8_t nonce[VOS_CRYPTO_NONCE_BYTES];
    uint8_t aad[48];
    if (!vos_node_decode(geometry, node_id, generation, plain_block,
                         geometry->block_bytes, &decoded)) {
        return 0;
    }
    coords.generation = generation;
    coords.node_id = node_id;
    coords.kind = decoded.kind;
    coords.domain_epoch = (uint32_t)key_epoch;
    if (!vos_node_derive_nonce(geometry, &coords, nonce)) {
        return 0;
    }
    build_node_aad(domain_id, key_epoch, node_id, generation, decoded.kind, aad);
    if (!vos_crypto_core_seal(crypto, slot, nonce, aad, sizeof(aad),
                              plain_block, geometry->block_bytes,
                              cipher_out, tag_out) ||
        !vos_crypto_core_keyed_digest(crypto, slot, plain_block,
                                      geometry->block_bytes, digest_out)) {
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
    struct vos_node_nonce coords = {0};
    uint8_t nonce[VOS_CRYPTO_NONCE_BYTES];
    uint8_t aad[48];
    if (auth == NULL || !auth->valid) {
        return 0;
    }
    coords.generation = auth->generation;
    coords.node_id = node_id;
    coords.kind = auth->kind;
    coords.domain_epoch = (uint32_t)key_epoch;
    if (!vos_node_derive_nonce(geometry, &coords, nonce)) {
        return 0;
    }
    build_node_aad(domain_id, key_epoch, node_id, auth->generation, auth->kind, aad);
    if (!vos_crypto_core_open(crypto, slot, nonce, aad, sizeof(aad),
                              cipher_block, geometry->block_bytes,
                              auth->tag, plain_out)) {
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

int vos_storage_format(struct vos_storage_medium *medium,
                       struct vos_storage_store *store,
                       struct vos_crypto_core *crypto,
                       uint32_t crypto_slot,
                       uint64_t domain_id,
                       uint64_t key_epoch,
                       const struct vos_node_geometry *geometry,
                       const struct vos_tree_limits *limits,
                       uint64_t initial_generation,
                       uint64_t max_generation)
{
    struct vos_node root_node = {0};
    uint32_t root_kind = 0u;
    if (medium == NULL || store == NULL || crypto == NULL ||
        crypto_slot >= VOS_CRYPTO_MAX_DOMAINS ||
        !crypto->domains[crypto_slot].provisioned ||
        crypto->domains[crypto_slot].domain_id != domain_id ||
        crypto->domains[crypto_slot].key_epoch != key_epoch ||
        domain_id == 0u || key_epoch > VOS_NODE_NONCE_MAX_DOMAIN ||
        initial_generation == 0u || initial_generation > max_generation ||
        !valid_geometry_and_limits(geometry, limits)) {
        return 0;
    }
    zero_bytes((uint8_t *)medium, sizeof(*medium));
    zero_bytes((uint8_t *)store, sizeof(*store));
    medium->geometry = *geometry;
    medium->limits = *limits;
    medium->limits.height = 0u;

    medium->nonce_record.domain_id = domain_id;
    medium->nonce_record.key_epoch = key_epoch;
    medium->nonce_record.reserved_generation = initial_generation;
    medium->nonce_record.max_generation = max_generation;
    if (!sign_nonce_record(crypto, crypto_slot, &medium->nonce_record)) {
        return 0;
    }

    root_node.kind = VOS_NODE_LEAF;
    root_node.count = 0u;
    root_node.node_id = 0u;
    root_node.generation = initial_generation;
    if (!vos_node_encode(geometry, &root_node, store->plain_arena,
                         geometry->block_bytes)) {
        return 0;
    }
    store->plain_generations[0] = initial_generation;

    uint8_t root_tag[VOS_CRYPTO_TAG_BYTES];
    uint8_t root_digest[VOS_CRYPTO_DIGEST_BYTES];
    if (!seal_node_block(crypto, crypto_slot, domain_id, key_epoch,
                         geometry, 0u, initial_generation,
                         store->plain_arena, &root_kind,
                         medium->arena_ciphertext, root_tag, root_digest)) {
        return 0;
    }

    struct vos_storage_checkpoint *cp = &medium->checkpoint;
    cp->committed = 1u;
    cp->commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE;
    cp->domain_id = domain_id;
    cp->key_epoch = key_epoch;
    cp->generation = initial_generation;
    cp->root = 0u;
    cp->height = 0u;
    cp->used = 1u;
    cp->frame_count = 0u;
    copy_bytes(cp->root_digest, root_digest, VOS_CRYPTO_DIGEST_BYTES);
    if (!compute_payload_manifest(crypto, crypto_slot, domain_id,
                                  initial_generation, NULL, 0u,
                                  cp->payload_manifest_digest)) {
        return 0;
    }
    cp->auth[0].valid = 1u;
    cp->auth[0].kind = root_kind;
    cp->auth[0].generation = initial_generation;
    copy_bytes(cp->auth[0].tag, root_tag, VOS_CRYPTO_TAG_BYTES);
    if (!sign_checkpoint(crypto, crypto_slot, cp)) {
        return 0;
    }
    medium->journal_reusable = 1u;

    store->open = 1u;
    store->crypto_slot = crypto_slot;
    store->domain_id = domain_id;
    store->key_epoch = key_epoch;
    store->committed_generation = initial_generation;
    store->committed_root = 0u;
    store->committed_height = 0u;
    store->committed_used = 1u;
    store->medium = medium;
    store->crypto = crypto;
    return 1;
}

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

int vos_storage_reserve(struct vos_storage_store *store,
                        uint64_t caller_domain,
                        const struct vos_storage_tx_spec *spec)
{
    if (store == NULL || !store->open || store->medium == NULL ||
        store->crypto == NULL || caller_domain != store->domain_id ||
        store->attempt.reserved || !valid_tx_spec(store, spec)) {
        return 0;
    }
    struct vos_storage_medium *medium = store->medium;
    if (!verify_nonce_record(store->crypto, store->crypto_slot,
                             store->domain_id, store->key_epoch,
                             &medium->nonce_record) ||
        medium->nonce_record.reserved_generation < store->committed_generation ||
        medium->nonce_record.reserved_generation >= medium->nonce_record.max_generation) {
        return 0;
    }
    if (spec->op_kind != VOS_STORAGE_OP_COMPACT &&
        store->committed_used >= medium->geometry.arena_nodes) {
        return 0;
    }
    if (spec->commit_mode == VOS_STORAGE_COMMIT_FRESH &&
        store->crypto->rot_epoch_counter >= store->crypto->rot_epoch_ceiling) {
        return 0;
    }

    /* Persist key-wide nonce reservation advance before sealing any candidate. */
    const uint64_t next_gen = medium->nonce_record.reserved_generation + 1u;
    struct vos_storage_nonce_record next_nonce = medium->nonce_record;
    next_nonce.reserved_generation = next_gen;
    if (!sign_nonce_record(store->crypto, store->crypto_slot, &next_nonce)) {
        return 0;
    }
    medium->nonce_record = next_nonce;

    zero_bytes((uint8_t *)&store->attempt, sizeof(store->attempt));
    store->attempt.reserved = 1u;
    store->attempt.staged = 0u;
    store->attempt.caller_domain = caller_domain;
    store->attempt.generation = next_gen;
    store->attempt.base_used = store->committed_used;
    store->attempt.spec = *spec;
    return 1;
}

int vos_storage_stage(struct vos_storage_store *store,
                      uint64_t caller_domain)
{
    if (store == NULL || !store->open || store->medium == NULL ||
        store->crypto == NULL || caller_domain != store->domain_id ||
        !store->attempt.reserved || store->attempt.staged ||
        store->attempt.caller_domain != caller_domain ||
        store->attempt.generation != store->medium->nonce_record.reserved_generation) {
        return 0;
    }
    struct vos_storage_medium *medium = store->medium;
    struct vos_storage_attempt *att = &store->attempt;
    const size_t block_bytes = medium->geometry.block_bytes;
    const size_t arena_bytes = (size_t)medium->geometry.arena_nodes * block_bytes;

    copy_bytes(att->staged_plaintext, store->plain_arena, arena_bytes);
    for (uint32_t i = 0u; i < medium->geometry.arena_nodes; ++i) {
        att->staged_generations[i] = store->plain_generations[i];
        att->staged_auth[i] = medium->checkpoint.auth[i];
    }
    att->staged_dead_count = medium->checkpoint.dead_count;
    for (uint32_t i = 0u; i < medium->checkpoint.dead_count; ++i) {
        att->staged_deadlist[i] = medium->checkpoint.deadlist[i];
    }

    struct vos_tree_limits cur_limits = medium->limits;
    cur_limits.height = store->committed_height;

    struct vos_tree_arena arena = {0};
    arena.geometry = medium->geometry;
    arena.used = store->committed_used;
    arena.bytes = att->staged_plaintext;
    arena.length = arena_bytes;
    arena.generations = att->staged_generations;
    arena.generation_count = medium->geometry.arena_nodes;

    const uint64_t start_allocated = store->committed_used;
    int update_ok = 0;

    if (att->spec.op_kind == VOS_STORAGE_OP_INSERT) {
        update_ok = vos_tree_insert(&arena, &cur_limits, store->committed_root,
                                    att->generation, att->spec.key,
                                    att->spec.value, &att->result);
    } else if (att->spec.op_kind == VOS_STORAGE_OP_INSERT_BATCH) {
        update_ok = vos_tree_insert_batch(&arena, &cur_limits, store->committed_root,
                                          att->generation, att->spec.entries,
                                          att->spec.entry_count, &att->result);
    } else if (att->spec.op_kind == VOS_STORAGE_OP_DELETE) {
        update_ok = vos_tree_delete(&arena, &cur_limits, store->committed_root,
                                    att->generation, att->spec.key, &att->result);
    } else if (att->spec.op_kind == VOS_STORAGE_OP_COMPACT) {
        update_ok = vos_tree_compact(&arena, &cur_limits, store->committed_root,
                                     att->generation, &att->result);
    }

    if (!update_ok || att->result.used <= start_allocated ||
        att->result.used > medium->geometry.arena_nodes ||
        att->result.used - start_allocated > VOS_STORAGE_MAX_JOURNAL_FRAMES) {
        return 0;
    }

    /* Record O(1) birth-generation snapshot reclamation for replaced nodes (R-10-010). */
    if (medium->checkpoint.snapshot_count > 0u) {
        struct vos_tree_arena reclaim_arena = arena;
        reclaim_arena.used = att->result.used;
        struct vos_tree_limits new_limits = medium->limits;
        new_limits.height = att->result.height;
        struct vos_tree_reclaim_plan plan = {0};
        uint64_t latest_snap = 0u;
        for (uint32_t i = 0u; i < medium->checkpoint.snapshot_count; ++i) {
            if (medium->checkpoint.snapshots[i] > latest_snap) {
                latest_snap = medium->checkpoint.snapshots[i];
            }
        }
        if (!vos_tree_classify_reclaim(&reclaim_arena, &cur_limits,
                                       store->committed_root, &new_limits,
                                       att->result.root, latest_snap, 1, &plan)) {
            return 0;
        }
        for (uint32_t i = 0u; i < plan.deadlist_count; ++i) {
            if (att->staged_dead_count >= VOS_STORAGE_MAX_DEADLIST) {
                return 0;
            }
            const uint64_t dead_id = plan.deadlist_ids[i];
            att->staged_deadlist[att->staged_dead_count].node_id = dead_id;
            att->staged_deadlist[att->staged_dead_count].birth_generation =
                att->staged_generations[(size_t)dead_id];
            ++att->staged_dead_count;
        }
    }

    uint32_t f_idx = 0u;
    for (uint64_t id = start_allocated; id < att->result.used; ++id) {
        struct vos_storage_journal_frame *frame = &att->frames[f_idx];
        uint32_t kind = 0u;
        zero_bytes((uint8_t *)frame, sizeof(*frame));
        if (!seal_node_block(store->crypto, store->crypto_slot,
                             store->domain_id, store->key_epoch,
                             &medium->geometry, id, att->generation,
                             att->staged_plaintext + (size_t)id * block_bytes,
                             &kind, frame->ciphertext, frame->tag,
                             frame->content_digest)) {
            return 0;
        }
        frame->occupied = 1u;
        frame->frame_index = f_idx;
        frame->kind = kind;
        frame->tx_generation = att->generation;
        frame->target_node_id = id;
        if (!sign_journal_frame(store->crypto, store->crypto_slot,
                                store->domain_id, store->key_epoch,
                                block_bytes, frame)) {
            return 0;
        }
        att->staged_auth[(size_t)id].valid = 1u;
        att->staged_auth[(size_t)id].kind = kind;
        att->staged_auth[(size_t)id].generation = att->generation;
        copy_bytes(att->staged_auth[(size_t)id].tag, frame->tag, VOS_CRYPTO_TAG_BYTES);
        ++f_idx;
    }
    att->frame_count = f_idx;
    att->staged = 1u;
    return 1;
}

static int verify_staged_candidate(const struct vos_storage_store *store)
{
    const struct vos_storage_medium *medium = store->medium;
    const struct vos_storage_attempt *att = &store->attempt;
    const size_t block_bytes = medium->geometry.block_bytes;
    struct vos_tree_image candidate = {0};
    struct vos_tree_limits candidate_limits = medium->limits;
    uint64_t checked = 0u;

    if (!att->reserved || !att->staged || att->frame_count == 0u ||
        att->frame_count > VOS_STORAGE_MAX_JOURNAL_FRAMES ||
        att->result.used == 0u || att->result.used > medium->geometry.arena_nodes ||
        att->result.root >= att->result.used) {
        return 0;
    }
    for (uint32_t i = 0u; i < att->frame_count; ++i) {
        const struct vos_storage_journal_frame *frame = &att->frames[i];
        uint8_t opened[VOS_STORAGE_MAX_BLOCK_BYTES];
        uint8_t digest[VOS_CRYPTO_DIGEST_BYTES];
        struct vos_node decoded = {0};
        if (frame->frame_index != i ||
            frame->tx_generation != att->generation ||
            frame->target_node_id >= att->result.used ||
            !verify_journal_frame(store->crypto, store->crypto_slot,
                                  store->domain_id, store->key_epoch,
                                  block_bytes, frame) ||
            !open_node_block(store->crypto, store->crypto_slot,
                             &medium->geometry, store->domain_id,
                             store->key_epoch, frame->target_node_id,
                             &att->staged_auth[(size_t)frame->target_node_id],
                             frame->ciphertext, opened, &decoded) ||
            !vos_crypto_core_keyed_digest(store->crypto, store->crypto_slot,
                                          opened, block_bytes, digest) ||
            !equal_bytes_ct(digest, frame->content_digest, VOS_CRYPTO_DIGEST_BYTES)) {
            return 0;
        }
    }
    candidate.geometry = medium->geometry;
    candidate.geometry.arena_nodes = att->result.used;
    candidate.bytes = att->staged_plaintext;
    candidate.length = (size_t)att->result.used * block_bytes;
    candidate.generations = att->staged_generations;
    candidate.generation_count = (size_t)att->result.used;
    candidate_limits.height = att->result.height;
    return vos_tree_lookup(&candidate, &candidate_limits,
                           att->result.root, 0u, &checked) != VOS_TREE_REFUSED;
}

int vos_storage_publish(struct vos_storage_store *store,
                        uint64_t caller_domain,
                        uint32_t cut_point,
                        uint64_t *acknowledged_generation)
{
    if (store == NULL || !store->open || store->medium == NULL ||
        store->crypto == NULL || acknowledged_generation == NULL ||
        caller_domain != store->domain_id ||
        !store->attempt.reserved ||
        store->attempt.caller_domain != caller_domain ||
        store->attempt.generation != store->medium->nonce_record.reserved_generation) {
        return 0;
    }
    if (cut_point == VOS_STORAGE_CUT_AFTER_RESERVE) {
        return 0;
    }
    if (!verify_staged_candidate(store)) {
        return 0;
    }
    struct vos_storage_medium *medium = store->medium;
    struct vos_storage_attempt *att = &store->attempt;
    const size_t block_bytes = medium->geometry.block_bytes;

    /* Stage journal frames onto the medium before checkpoint publication. */
    medium->journal_reusable = 0u;
    if (cut_point == VOS_STORAGE_CUT_MID_PAYLOAD) {
        const uint32_t partial = (att->frame_count > 1u) ? (att->frame_count / 2u) : 1u;
        for (uint32_t i = 0u; i < partial; ++i) {
            medium->journal[i] = att->frames[i];
        }
        if (att->frame_count == 1u) {
            medium->journal[0].frame_mac[0] ^= 0xffu;
        }
        medium->journal_count = partial;
        return 0;
    }

    for (uint32_t i = 0u; i < att->frame_count; ++i) {
        medium->journal[i] = att->frames[i];
    }
    medium->journal_count = att->frame_count;

    if (cut_point == VOS_STORAGE_CUT_BEFORE_CHECKPOINT) {
        return 0;
    }

    struct vos_storage_checkpoint next_cp = {0};
    next_cp.committed = 1u;
    next_cp.commit_mode = att->spec.commit_mode;
    next_cp.domain_id = store->domain_id;
    next_cp.key_epoch = store->key_epoch;
    next_cp.generation = att->generation;
    next_cp.root = att->result.root;
    next_cp.height = att->result.height;
    next_cp.used = att->result.used;
    next_cp.frame_count = att->frame_count;
    next_cp.snapshot_count = medium->checkpoint.snapshot_count;
    for (uint32_t i = 0u; i < next_cp.snapshot_count; ++i) {
        next_cp.snapshots[i] = medium->checkpoint.snapshots[i];
    }
    next_cp.dead_count = att->staged_dead_count;
    for (uint32_t i = 0u; i < next_cp.dead_count; ++i) {
        next_cp.deadlist[i] = att->staged_deadlist[i];
    }
    for (uint64_t i = 0u; i < next_cp.used; ++i) {
        next_cp.auth[(size_t)i] = att->staged_auth[(size_t)i];
    }
    if (!vos_crypto_core_keyed_digest(
            store->crypto, store->crypto_slot,
            att->staged_plaintext + (size_t)next_cp.root * block_bytes,
            block_bytes, next_cp.root_digest) ||
        !compute_payload_manifest(store->crypto, store->crypto_slot,
                                  store->domain_id, att->generation,
                                  att->frames, att->frame_count,
                                  next_cp.payload_manifest_digest)) {
        return 0;
    }

    if (next_cp.commit_mode == VOS_STORAGE_COMMIT_FRESH) {
        next_cp.fresh_region_id = att->spec.fresh_region_id;
        next_cp.fresh_region_version = att->spec.fresh_region_version;
        next_cp.sealed_epoch = 0u;
        zero_bytes(next_cp.epoch_root, VOS_CRYPTO_DIGEST_BYTES);
        if (!sign_checkpoint(store->crypto, store->crypto_slot, &next_cp)) {
            return 0;
        }
        medium->fallback_checkpoint = medium->checkpoint;
        medium->has_fallback = 1u;
        medium->checkpoint = next_cp;
        if (cut_point == VOS_STORAGE_CUT_BEFORE_EPOCH_SEAL) {
            return 0;
        }
        if (!vos_crypto_core_seal_epoch(store->crypto, store->crypto_slot,
                                        next_cp.fresh_region_id,
                                        next_cp.fresh_region_version,
                                        next_cp.root_digest,
                                        &next_cp.sealed_epoch,
                                        next_cp.epoch_root) ||
            !sign_checkpoint(store->crypto, store->crypto_slot, &next_cp)) {
            return 0;
        }
        medium->checkpoint = next_cp;
    } else {
        next_cp.fresh_region_id = medium->checkpoint.fresh_region_id;
        next_cp.fresh_region_version = medium->checkpoint.fresh_region_version;
        next_cp.sealed_epoch = medium->checkpoint.sealed_epoch;
        copy_bytes(next_cp.epoch_root, medium->checkpoint.epoch_root,
                   VOS_CRYPTO_DIGEST_BYTES);
        if (!sign_checkpoint(store->crypto, store->crypto_slot, &next_cp)) {
            return 0;
        }
        medium->fallback_checkpoint = medium->checkpoint;
        medium->has_fallback = 1u;
        medium->checkpoint = next_cp;
    }

    /* Cut before acknowledgment / journal reuse: checkpoint is durable on medium,
     * and arena shadow application + journal retirement will complete on Reopen. */
    if (cut_point == VOS_STORAGE_CUT_BEFORE_ACK) {
        return 0;
    }

    for (uint32_t i = 0u; i < att->frame_count; ++i) {
        const uint64_t id = att->frames[i].target_node_id;
        copy_bytes(medium->arena_ciphertext + (size_t)id * block_bytes,
                   att->frames[i].ciphertext, block_bytes);
    }
    medium->journal_count = 0u;
    medium->journal_reusable = 1u;
    zero_bytes((uint8_t *)medium->journal, sizeof(medium->journal));

    copy_bytes(store->plain_arena, att->staged_plaintext,
               (size_t)medium->geometry.arena_nodes * block_bytes);
    for (uint32_t i = 0u; i < medium->geometry.arena_nodes; ++i) {
        store->plain_generations[i] = att->staged_generations[i];
    }
    store->committed_generation = next_cp.generation;
    store->committed_root = next_cp.root;
    store->committed_height = next_cp.height;
    store->committed_used = next_cp.used;
    zero_bytes((uint8_t *)&store->attempt, sizeof(store->attempt));
    *acknowledged_generation = next_cp.generation;
    return 1;
}

int vos_storage_reopen(struct vos_storage_medium *medium,
                       struct vos_storage_store *store,
                       struct vos_crypto_core *crypto,
                       uint32_t crypto_slot,
                       uint64_t expected_domain_id)
{
    if (medium == NULL || store == NULL || crypto == NULL ||
        crypto_slot >= VOS_CRYPTO_MAX_DOMAINS ||
        !crypto->domains[crypto_slot].provisioned ||
        crypto->domains[crypto_slot].domain_id != expected_domain_id ||
        !valid_geometry_and_limits(&medium->geometry, &medium->limits)) {
        return 0;
    }
    /* Discard all volatile state before reading the persistent medium. */
    zero_bytes((uint8_t *)store, sizeof(*store));

    const uint64_t key_epoch = crypto->domains[crypto_slot].key_epoch;
    if (!verify_nonce_record(crypto, crypto_slot, expected_domain_id,
                             key_epoch, &medium->nonce_record) ||
        !verify_checkpoint_mac(crypto, crypto_slot, expected_domain_id,
                               key_epoch, medium->geometry.arena_nodes,
                               &medium->checkpoint)) {
        return 0;
    }

    /* R-10-013c: an epoch that does not seal loses its writes rather than
     * presenting them as fresh. Roll back unsealed Fresh checkpoints to the
     * retained fallback checkpoint. */
    if (medium->checkpoint.commit_mode == VOS_STORAGE_COMMIT_FRESH &&
        medium->checkpoint.sealed_epoch == 0u) {
        if (!medium->has_fallback ||
            !verify_checkpoint_mac(crypto, crypto_slot, expected_domain_id,
                                   key_epoch, medium->geometry.arena_nodes,
                                   &medium->fallback_checkpoint)) {
            return 0;
        }
        medium->checkpoint = medium->fallback_checkpoint;
        medium->journal_count = 0u;
        medium->journal_reusable = 1u;
        zero_bytes((uint8_t *)medium->journal, sizeof(medium->journal));
    }

    const struct vos_storage_checkpoint *cp = &medium->checkpoint;
    if (medium->nonce_record.reserved_generation < cp->generation) {
        return 0;
    }

    /* R-10-013e: verify sealed Fresh epoch root against the RoT counter. */
    if (((crypto->epoch_sealed_mask & (1u << crypto_slot)) != 0u) ||
        cp->commit_mode == VOS_STORAGE_COMMIT_FRESH ||
        cp->sealed_epoch != 0u) {
        if (!vos_crypto_core_verify_epoch(crypto, crypto_slot, cp->sealed_epoch,
                                          cp->fresh_region_id,
                                          cp->fresh_region_version,
                                          cp->root_digest, cp->epoch_root)) {
            return 0;
        }
    }

    const size_t block_bytes = medium->geometry.block_bytes;

    /* R-10-002a bounded prefix redo recovery. */
    if (medium->journal_count > 0u) {
        if (medium->journal_count > VOS_STORAGE_MAX_JOURNAL_FRAMES) {
            return 0;
        }
        const uint64_t j_gen = medium->journal[0].tx_generation;
        if (j_gen == cp->generation) {
            /* Committed transaction: every bound payload frame must verify. */
            if (medium->journal_count != cp->frame_count) {
                return 0;
            }
            uint8_t manifest_digest[VOS_CRYPTO_DIGEST_BYTES];
            if (!compute_payload_manifest(crypto, crypto_slot, expected_domain_id,
                                          cp->generation, medium->journal,
                                          medium->journal_count, manifest_digest) ||
                !equal_bytes_ct(manifest_digest, cp->payload_manifest_digest,
                                VOS_CRYPTO_DIGEST_BYTES)) {
                return 0;
            }
            for (uint32_t i = 0u; i < medium->journal_count; ++i) {
                const struct vos_storage_journal_frame *frame = &medium->journal[i];
                uint8_t opened[VOS_STORAGE_MAX_BLOCK_BYTES];
                uint8_t digest[VOS_CRYPTO_DIGEST_BYTES];
                struct vos_node decoded = {0};
                if (frame->frame_index != i ||
                    frame->tx_generation != cp->generation ||
                    frame->target_node_id >= cp->used ||
                    !verify_journal_frame(crypto, crypto_slot, expected_domain_id,
                                          key_epoch, block_bytes, frame) ||
                    !equal_bytes_ct(frame->tag,
                                    cp->auth[(size_t)frame->target_node_id].tag,
                                    VOS_CRYPTO_TAG_BYTES) ||
                    !open_node_block(crypto, crypto_slot, &medium->geometry,
                                     expected_domain_id, key_epoch,
                                     frame->target_node_id,
                                     &cp->auth[(size_t)frame->target_node_id],
                                     frame->ciphertext, opened, &decoded) ||
                    !vos_crypto_core_keyed_digest(crypto, crypto_slot,
                                                  opened, block_bytes, digest) ||
                    !equal_bytes_ct(digest, frame->content_digest,
                                    VOS_CRYPTO_DIGEST_BYTES)) {
                    return 0;
                }
            }
            for (uint32_t i = 0u; i < medium->journal_count; ++i) {
                const uint64_t id = medium->journal[i].target_node_id;
                copy_bytes(medium->arena_ciphertext + (size_t)id * block_bytes,
                           medium->journal[i].ciphertext, block_bytes);
            }
            medium->journal_count = 0u;
            medium->journal_reusable = 1u;
            zero_bytes((uint8_t *)medium->journal, sizeof(medium->journal));
        } else if (j_gen > cp->generation &&
                   j_gen <= medium->nonce_record.reserved_generation) {
            /* Uncommitted suffix: discard without rolling back nonce reservation. */
            medium->journal_count = 0u;
            medium->journal_reusable = 1u;
            zero_bytes((uint8_t *)medium->journal, sizeof(medium->journal));
        } else {
            return 0;
        }
    }

    /* Authenticate and reconstruct all arena blocks 0 .. cp->used - 1. */
    for (uint64_t id = 0u; id < cp->used; ++id) {
        struct vos_node decoded = {0};
        if (!open_node_block(crypto, crypto_slot, &medium->geometry,
                             expected_domain_id, key_epoch, id,
                             &cp->auth[(size_t)id],
                             medium->arena_ciphertext + (size_t)id * block_bytes,
                             store->plain_arena + (size_t)id * block_bytes,
                             &decoded)) {
            zero_bytes((uint8_t *)store, sizeof(*store));
            return 0;
        }
        store->plain_generations[(size_t)id] = cp->auth[(size_t)id].generation;
    }

    uint8_t actual_root_digest[VOS_CRYPTO_DIGEST_BYTES];
    if (!vos_crypto_core_keyed_digest(
            crypto, crypto_slot,
            store->plain_arena + (size_t)cp->root * block_bytes,
            block_bytes, actual_root_digest) ||
        !equal_bytes_ct(actual_root_digest, cp->root_digest,
                        VOS_CRYPTO_DIGEST_BYTES)) {
        zero_bytes((uint8_t *)store, sizeof(*store));
        return 0;
    }

    struct vos_tree_image image = {0};
    struct vos_tree_limits check_limits = medium->limits;
    uint64_t dummy = 0u;
    image.geometry = medium->geometry;
    image.geometry.arena_nodes = cp->used;
    image.bytes = store->plain_arena;
    image.length = (size_t)cp->used * block_bytes;
    image.generations = store->plain_generations;
    image.generation_count = (size_t)cp->used;
    check_limits.height = cp->height;
    if (vos_tree_lookup(&image, &check_limits, cp->root, 0u, &dummy) == VOS_TREE_REFUSED) {
        zero_bytes((uint8_t *)store, sizeof(*store));
        return 0;
    }

    store->open = 1u;
    store->crypto_slot = crypto_slot;
    store->domain_id = expected_domain_id;
    store->key_epoch = key_epoch;
    store->committed_generation = cp->generation;
    store->committed_root = cp->root;
    store->committed_height = cp->height;
    store->committed_used = cp->used;
    store->medium = medium;
    store->crypto = crypto;
    return 1;
}

int vos_storage_lookup(const struct vos_storage_store *store,
                       uint64_t caller_domain,
                       uint64_t key,
                       uint64_t *value_out)
{
    if (store == NULL || !store->open || store->medium == NULL ||
        store->crypto == NULL || value_out == NULL ||
        caller_domain != store->domain_id) {
        return VOS_TREE_REFUSED;
    }
    const struct vos_storage_medium *medium = store->medium;
    const struct vos_storage_checkpoint *cp = &medium->checkpoint;
    const size_t block_bytes = medium->geometry.block_bytes;
    if (!verify_checkpoint_mac(store->crypto, store->crypto_slot,
                               store->domain_id, store->key_epoch,
                               medium->geometry.arena_nodes, cp)) {
        return VOS_TREE_REFUSED;
    }
    if (store->crypto->epoch_sealed ||
        cp->commit_mode == VOS_STORAGE_COMMIT_FRESH ||
        cp->sealed_epoch != 0u) {
        if (!vos_crypto_core_verify_epoch(store->crypto, store->crypto_slot,
                                          cp->sealed_epoch,
                                          cp->fresh_region_id,
                                          cp->fresh_region_version,
                                          cp->root_digest, cp->epoch_root)) {
            return VOS_TREE_REFUSED;
        }
    }

    uint64_t cur_id = cp->root;
    uint32_t rem_height = cp->height;
    uint32_t rem_visits = medium->limits.visit_limit;
    uint64_t lower = 0u;
    uint64_t upper = 0u;
    int has_lower = 0;
    int has_upper = 0;

    while (rem_visits > 0u) {
        --rem_visits;
        if (cur_id >= cp->used) {
            return VOS_TREE_REFUSED;
        }
        uint8_t plain_block[VOS_STORAGE_MAX_BLOCK_BYTES];
        struct vos_node node = {0};
        if (!open_node_block(store->crypto, store->crypto_slot,
                             &medium->geometry, store->domain_id,
                             store->key_epoch, cur_id,
                             &cp->auth[(size_t)cur_id],
                             medium->arena_ciphertext + (size_t)cur_id * block_bytes,
                             plain_block, &node)) {
            return VOS_TREE_REFUSED;
        }
        if (cur_id == cp->root) {
            uint8_t root_digest[VOS_CRYPTO_DIGEST_BYTES];
            if (!vos_crypto_core_keyed_digest(store->crypto, store->crypto_slot,
                                              plain_block, block_bytes,
                                              root_digest) ||
                !equal_bytes_ct(root_digest, cp->root_digest,
                                VOS_CRYPTO_DIGEST_BYTES)) {
                return VOS_TREE_REFUSED;
            }
        }
        if (node.kind == VOS_NODE_LEAF) {
            if (rem_height != 0u) {
                return VOS_TREE_REFUSED;
            }
            int found = 0;
            uint64_t found_val = 0u;
            for (uint32_t i = 0u; i < node.count; ++i) {
                if ((i != 0u && node.keys[i - 1u] >= node.keys[i]) ||
                    (has_lower && node.keys[i] < lower) ||
                    (has_upper && node.keys[i] >= upper)) {
                    return VOS_TREE_REFUSED;
                }
                if (node.keys[i] == key) {
                    found = 1;
                    found_val = node.values[i];
                }
            }
            if (!found) {
                return VOS_TREE_MISSING;
            }
            *value_out = found_val;
            return VOS_TREE_FOUND;
        }
        if (rem_height == 0u || node.count == 0u) {
            return VOS_TREE_REFUSED;
        }
        uint64_t sep_lower = lower;
        int sep_has_lower = has_lower;
        for (uint32_t i = 0u; i + 1u < node.count; ++i) {
            if ((sep_has_lower && node.keys[i] <= sep_lower) ||
                (has_upper && node.keys[i] >= upper)) {
                return VOS_TREE_REFUSED;
            }
            sep_lower = node.keys[i];
            sep_has_lower = 1;
        }
        uint32_t route = 0u;
        while (route + 1u < node.count && node.keys[route] <= key) {
            ++route;
        }
        if (route != 0u) {
            lower = node.keys[route - 1u];
            has_lower = 1;
        }
        if (route + 1u < node.count) {
            upper = node.keys[route];
            has_upper = 1;
        }
        cur_id = node.values[route];
        --rem_height;
    }
    return VOS_TREE_REFUSED;
}

int vos_storage_retain_snapshot(struct vos_storage_store *store,
                                uint64_t caller_domain,
                                uint64_t generation)
{
    if (store == NULL || !store->open || store->medium == NULL ||
        store->crypto == NULL || caller_domain != store->domain_id ||
        generation == 0u || generation > store->committed_generation) {
        return 0;
    }
    struct vos_storage_checkpoint *cp = &store->medium->checkpoint;
    for (uint32_t i = 0u; i < cp->snapshot_count; ++i) {
        if (cp->snapshots[i] == generation) {
            return 1;
        }
    }
    if (cp->snapshot_count >= VOS_STORAGE_MAX_SNAPSHOTS) {
        return 0;
    }
    cp->snapshots[cp->snapshot_count] = generation;
    ++cp->snapshot_count;
    return sign_checkpoint(store->crypto, store->crypto_slot, cp);
}

int vos_storage_object_digest(const struct vos_storage_store *store,
                              const uint8_t *bytes,
                              size_t length,
                              uint8_t digest_out[VOS_CRYPTO_DIGEST_BYTES])
{
    if (store == NULL || !store->open || store->crypto == NULL ||
        digest_out == NULL || (length != 0u && bytes == NULL)) {
        return 0;
    }
    return vos_crypto_core_keyed_digest(store->crypto, store->crypto_slot,
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

int vos_storage_verify_admitted_resident(void *verification,
                                         const struct vos_resident_identity *identity,
                                         const uint8_t *bytes, size_t length)
{
    const struct vos_storage_resident_receipt *receipt = verification;
    if (receipt == NULL || receipt->valid != 1u || identity == NULL ||
        length != receipt->length || length > VOS_RESIDENT_BYTES ||
        (length != 0u && bytes == NULL)) return 0;
    const struct vos_storage_store *store = receipt->store;
    if (store == NULL || !store->open || store->medium == NULL ||
        store->crypto == NULL || store->crypto_slot >= VOS_CRYPTO_MAX_DOMAINS ||
        identity->owner != receipt->identity.owner ||
        identity->domain != receipt->identity.domain ||
        identity->object != receipt->identity.object ||
        identity->version != receipt->identity.version ||
        identity->generation != receipt->identity.generation ||
        identity->kind != receipt->identity.kind ||
        !equal_bytes_ct(identity->root, receipt->identity.root, VOS_CRYPTO_DIGEST_BYTES) ||
        store->committed_generation != receipt->checkpoint.generation ||
        store->committed_root != receipt->checkpoint.root ||
        store->domain_id != receipt->checkpoint.domain_id ||
        store->key_epoch != receipt->checkpoint.key_epoch ||
        !equal_bytes_ct((const uint8_t *)&store->medium->checkpoint,
                         (const uint8_t *)&receipt->checkpoint,
                         sizeof(receipt->checkpoint))) return 0;
    const struct vos_crypto_domain_slot *slot = &store->crypto->domains[store->crypto_slot];
    if (!slot->provisioned || slot->domain_id != store->domain_id ||
        slot->key_epoch != store->key_epoch) return 0;
    const struct vos_storage_checkpoint *cp = &receipt->checkpoint;
    if ((((store->crypto->epoch_sealed_mask & (1u << store->crypto_slot)) != 0u) ||
         cp->commit_mode == VOS_STORAGE_COMMIT_FRESH || cp->sealed_epoch != 0u) &&
        !vos_crypto_core_verify_epoch(store->crypto, store->crypto_slot,
                                      cp->sealed_epoch, cp->fresh_region_id,
                                      cp->fresh_region_version, cp->root_digest,
                                      cp->epoch_root)) return 0;
    uint8_t expected[VOS_CRYPTO_DIGEST_BYTES];
    return compute_resident_digest(store, identity->owner, identity->domain,
                                    identity->object, identity->version,
                                    identity->kind, identity->generation,
                                    bytes, length, expected) &&
           equal_bytes_ct(expected, identity->root, VOS_CRYPTO_DIGEST_BYTES);
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
    out[7] = '1';
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
    put_le64(out + 80u, cp->sealed_epoch);
    put_le32(out + 88u, cp->snapshot_count);
    put_le32(out + 92u, cp->dead_count);
    copy_bytes(out + 96u, cp->epoch_root, VOS_CRYPTO_DIGEST_BYTES);
    copy_bytes(out + 128u, cp->root_digest, VOS_CRYPTO_DIGEST_BYTES);
    copy_bytes(out + 160u, cp->payload_manifest_digest, VOS_CRYPTO_DIGEST_BYTES);
    copy_bytes(out + 192u, cp->checkpoint_mac, VOS_CRYPTO_DIGEST_BYTES);
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
    static const uint8_t magic[8] = {'V', 'O', 'S', 'C', 'H', 'K', '0', '1'};
    if (in == NULL || cp_out == NULL ||
        arena_nodes > VOS_STORAGE_BLKDEV_MAX_ARENA_NODES ||
        !equal_bytes_ct(in, magic, sizeof(magic)) ||
        !all_zero(in + 1056u, BLKDEV_CP_BYTES - 1056u)) {
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
    if (cp_out->committed > 1u ||
        cp_out->snapshot_count > VOS_STORAGE_MAX_SNAPSHOTS ||
        cp_out->dead_count > VOS_STORAGE_BLKDEV_MAX_DEADLIST ||
        cp_out->frame_count > VOS_STORAGE_BLKDEV_MAX_JOURNAL_FRAMES) {
        zero_bytes((uint8_t *)cp_out, sizeof(*cp_out));
        return 0;
    }
    copy_bytes(cp_out->epoch_root, in + 96u, VOS_CRYPTO_DIGEST_BYTES);
    copy_bytes(cp_out->root_digest, in + 128u, VOS_CRYPTO_DIGEST_BYTES);
    copy_bytes(cp_out->payload_manifest_digest, in + 160u, VOS_CRYPTO_DIGEST_BYTES);
    copy_bytes(cp_out->checkpoint_mac, in + 192u, VOS_CRYPTO_DIGEST_BYTES);
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

    /* Blocks 32..47: primary checkpoint. */
    if (!decode_blkdev_checkpoint(
            medium_bytes + 32u * VOS_STORAGE_BLKDEV_BLOCK_BYTES,
            medium_out->geometry.arena_nodes, &medium_out->checkpoint)) {
        zero_bytes((uint8_t *)medium_out, sizeof(*medium_out));
        return 0;
    }

    /* Blocks 48..63: fallback checkpoint when present. */
    if (medium_out->has_fallback) {
        if (!decode_blkdev_checkpoint(
                medium_bytes + 48u * VOS_STORAGE_BLKDEV_BLOCK_BYTES,
                medium_out->geometry.arena_nodes,
                &medium_out->fallback_checkpoint)) {
            zero_bytes((uint8_t *)medium_out, sizeof(*medium_out));
            return 0;
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
