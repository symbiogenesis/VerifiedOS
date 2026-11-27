// SPDX-License-Identifier: Apache-2.0
#include "vos_backup.h"

#include <string.h>

static const uint8_t VOS_BK_MAGIC[VOS_BK_MAGIC_BYTES] = {
    'V', 'O', 'S', 'B', 'K', '0', '0', '1'
};

static void zero_mem(void *ptr, size_t len)
{
    if (ptr == NULL || len == 0u) {
        return;
    }
    volatile uint8_t *p = (volatile uint8_t *)ptr;
    for (size_t i = 0u; i < len; ++i) {
        p[i] = 0u;
    }
}

static void put_be32(uint8_t *dst, uint32_t v)
{
    dst[0] = (uint8_t)(v >> 24u);
    dst[1] = (uint8_t)(v >> 16u);
    dst[2] = (uint8_t)(v >> 8u);
    dst[3] = (uint8_t)v;
}

static uint32_t get_be32(const uint8_t *src)
{
    return ((uint32_t)src[0] << 24u) |
           ((uint32_t)src[1] << 16u) |
           ((uint32_t)src[2] << 8u) |
           (uint32_t)src[3];
}

static void put_be64(uint8_t *dst, uint64_t v)
{
    for (uint32_t i = 0u; i < 8u; ++i) {
        dst[i] = (uint8_t)(v >> (56u - 8u * i));
    }
}

static uint64_t get_be64(const uint8_t *src)
{
    uint64_t v = 0u;
    for (uint32_t i = 0u; i < 8u; ++i) {
        v = (v << 8u) | (uint64_t)src[i];
    }
    return v;
}

static int ct_equal(const uint8_t *a, const uint8_t *b, size_t len)
{
    uint8_t diff = 0u;
    for (size_t i = 0u; i < len; ++i) {
        diff |= (uint8_t)(a[i] ^ b[i]);
    }
    return diff == 0u;
}

static char encode_nibble_upper(uint8_t v)
{
    return (v < 10u) ? (char)('0' + v) : (char)('A' + (v - 10u));
}

static int decode_nibble_upper(char c, uint8_t *out)
{
    if (c >= '0' && c <= '9') {
        *out = (uint8_t)(c - '0');
        return 1;
    }
    if (c >= 'A' && c <= 'F') {
        *out = (uint8_t)(10 + (c - 'A'));
        return 1;
    }
    return 0;
}

void vos_bk_device_store_init(struct vos_bk_device_store *store,
                              uint32_t profile_id,
                              uint64_t generation,
                              uint64_t rot_floor,
                              uint64_t platform_counter)
{
    if (store == NULL) {
        return;
    }
    memset(store, 0, sizeof(*store));
    store->active_idx = 0u;
    store->staging_idx = 1u;
    store->staging_valid = 0u;
    store->slots[0].profile_id = profile_id;
    store->slots[0].generation = generation;
    store->rot_anti_rollback_floor = rot_floor;
    store->continuing_platform_counter = platform_counter;
    store->next_epoch = 1u;
}

const struct vos_bk_namespace *vos_bk_active_namespace(
    const struct vos_bk_device_store *store)
{
    if (store == NULL || store->active_idx >= 2u) {
        return NULL;
    }
    return &store->slots[store->active_idx];
}

enum vos_bk_status vos_bk_add_region(struct vos_bk_device_store *store,
                                     uint32_t region_id,
                                     enum vos_bk_region_kind kind,
                                     enum vos_bk_schema_class schema_class,
                                     uint32_t schema_id,
                                     uint32_t schema_gen,
                                     const uint8_t *payload,
                                     uint32_t payload_len)
{
    if (store == NULL || store->active_idx >= 2u ||
        payload_len > VOS_BK_MAX_REGION_PAYLOAD ||
        (payload_len > 0u && payload == NULL)) {
        return VOS_BK_ERR_INVALID;
    }
    struct vos_bk_namespace *ns = &store->slots[store->active_idx];
    if (ns->region_count >= VOS_BK_MAX_REGIONS) {
        return VOS_BK_ERR_CAPACITY;
    }
    for (uint32_t i = 0u; i < ns->region_count; ++i) {
        if (ns->regions[i].region_id == region_id) {
            return VOS_BK_ERR_INVALID;
        }
    }
    struct vos_bk_region_slot *slot = &ns->regions[ns->region_count];
    memset(slot, 0, sizeof(*slot));
    slot->region_id = region_id;
    slot->kind = kind;
    slot->schema_class = schema_class;
    slot->schema_id = schema_id;
    slot->schema_gen = schema_gen;
    slot->payload_len = payload_len;
    if (payload_len > 0u) {
        memcpy(slot->payload, payload, payload_len);
    }
    ++ns->region_count;
    return VOS_BK_OK;
}

enum vos_bk_status vos_bk_add_fresh_slot(struct vos_bk_device_store *store,
                                         uint32_t region_id,
                                         enum vos_bk_fresh_class fresh_class,
                                         uint32_t has_initializer,
                                         uint32_t enrolled,
                                         uint32_t reconciled,
                                         uint64_t scope_epoch,
                                         uint32_t attempts_remaining,
                                         uint64_t spent_token)
{
    if (store == NULL || store->active_idx >= 2u) {
        return VOS_BK_ERR_INVALID;
    }
    struct vos_bk_namespace *ns = &store->slots[store->active_idx];
    if (ns->fresh_count >= VOS_BK_MAX_FRESH) {
        return VOS_BK_ERR_CAPACITY;
    }
    struct vos_bk_fresh_slot *fs = &ns->fresh[ns->fresh_count];
    memset(fs, 0, sizeof(*fs));
    fs->region_id = region_id;
    fs->fresh_class = fresh_class;
    fs->has_initializer = has_initializer;
    fs->enrolled = enrolled;
    fs->reconciled = reconciled;
    fs->scope_epoch = scope_epoch;
    fs->attempts_remaining = attempts_remaining;
    if (spent_token != 0u) {
        fs->spent_count = 1u;
        fs->spent_tokens[0] = spent_token;
    }
    ++ns->fresh_count;
    return VOS_BK_OK;
}

enum vos_bk_status vos_bk_encode_recovery_secret(const uint8_t key[VOS_BK_KEY_BYTES],
                                                 char out_hex[VOS_BK_RECOVERY_HEX_CHARS + 1u])
{
    if (key == NULL || out_hex == NULL) {
        return VOS_BK_ERR_INVALID;
    }
    for (size_t i = 0u; i < VOS_BK_KEY_BYTES; ++i) {
        const uint8_t b = key[i];
        out_hex[2u * i] = encode_nibble_upper((uint8_t)(b >> 4u));
        out_hex[2u * i + 1u] = encode_nibble_upper((uint8_t)(b & 0x0fu));
    }
    out_hex[VOS_BK_RECOVERY_HEX_CHARS] = '\0';
    return VOS_BK_OK;
}

enum vos_bk_status vos_bk_decode_recovery_secret(const char *hex,
                                                 size_t hex_len,
                                                 uint8_t out_key[VOS_BK_KEY_BYTES])
{
    if (hex == NULL || out_key == NULL) {
        return VOS_BK_ERR_INVALID;
    }
    if (hex_len != VOS_BK_RECOVERY_HEX_CHARS) {
        zero_mem(out_key, VOS_BK_KEY_BYTES);
        return VOS_BK_ERR_HEX_FORMAT;
    }
    for (size_t i = 0u; i < VOS_BK_KEY_BYTES; ++i) {
        uint8_t hi = 0u;
        uint8_t lo = 0u;
        if (!decode_nibble_upper(hex[2u * i], &hi) ||
            !decode_nibble_upper(hex[2u * i + 1u], &lo)) {
            zero_mem(out_key, VOS_BK_KEY_BYTES);
            return VOS_BK_ERR_HEX_FORMAT;
        }
        out_key[i] = (uint8_t)((hi << 4u) | lo);
    }
    return VOS_BK_OK;
}

void vos_bk_derive_subkeys(const uint8_t object_key[VOS_BK_KEY_BYTES],
                           uint8_t manifest_key_out[VOS_BK_KEY_BYTES],
                           uint8_t chunk_key_out[VOS_BK_KEY_BYTES])
{
    static const uint8_t label_manifest[14] = {
        'V', 'O', 'S', 'B', 'K', '-', 'M', 'A', 'N', 'I', 'F', 'E', 'S', 'T'
    };
    static const uint8_t label_chunk[11] = {
        'V', 'O', 'S', 'B', 'K', '-', 'C', 'H', 'U', 'N', 'K'
    };
    uint8_t buf_m[14u + VOS_BK_KEY_BYTES];
    uint8_t buf_c[11u + VOS_BK_KEY_BYTES];

    memcpy(buf_m, label_manifest, sizeof(label_manifest));
    memcpy(buf_m + sizeof(label_manifest), object_key, VOS_BK_KEY_BYTES);
    (void)vos_sha256(buf_m, sizeof(buf_m), manifest_key_out);

    memcpy(buf_c, label_chunk, sizeof(label_chunk));
    memcpy(buf_c + sizeof(label_chunk), object_key, VOS_BK_KEY_BYTES);
    (void)vos_sha256(buf_c, sizeof(buf_c), chunk_key_out);

    zero_mem(buf_m, sizeof(buf_m));
    zero_mem(buf_c, sizeof(buf_c));
}

void vos_bk_chunk_nonce(uint32_t chunk_index,
                        uint8_t nonce_out[VOS_BK_NONCE_BYTES])
{
    static const uint8_t prefix[8] = {
        'V', 'O', 'S', 'C', 'H', 'K', '0', '1'
    };
    memcpy(nonce_out, prefix, 8u);
    put_be32(nonce_out + 8u, chunk_index);
}

uint32_t vos_bk_merkle_depth(uint32_t chunk_count)
{
    if (chunk_count <= 1u) {
        return 0u;
    }
    uint32_t d = 0u;
    uint32_t cap = 1u;
    while (cap < chunk_count && d < VOS_BK_MAX_MERKLE_DEPTH) {
        cap <<= 1u;
        ++d;
    }
    return d;
}

static void merkle_leaf_hash(uint32_t chunk_index,
                             const uint8_t *ciphertext,
                             uint32_t ct_len,
                             const uint8_t tag[VOS_BK_TAG_BYTES],
                             uint8_t out[VOS_BK_DIGEST_BYTES])
{
    static const uint8_t domain[11] = {
        'V', 'O', 'S', 'B', 'K', '-', 'L', 'E', 'A', 'F', '\0'
    };
    uint8_t buf[11u + 4u + VOS_BK_MAX_CHUNK_SIZE + VOS_BK_TAG_BYTES];
    memcpy(buf, domain, sizeof(domain));
    put_be32(buf + 11u, chunk_index);
    if (ct_len > 0u) {
        memcpy(buf + 15u, ciphertext, ct_len);
    }
    memcpy(buf + 15u + ct_len, tag, VOS_BK_TAG_BYTES);
    (void)vos_sha256(buf, 15u + ct_len + VOS_BK_TAG_BYTES, out);
    zero_mem(buf, sizeof(buf));
}

static void merkle_pad_hash(uint32_t pad_index, uint8_t out[VOS_BK_DIGEST_BYTES])
{
    static const uint8_t domain[10] = {
        'V', 'O', 'S', 'B', 'K', '-', 'P', 'A', 'D', '\0'
    };
    uint8_t buf[14];
    memcpy(buf, domain, sizeof(domain));
    put_be32(buf + 10u, pad_index);
    (void)vos_sha256(buf, sizeof(buf), out);
}

static void merkle_node_hash(const uint8_t left[VOS_BK_DIGEST_BYTES],
                             const uint8_t right[VOS_BK_DIGEST_BYTES],
                             uint8_t out[VOS_BK_DIGEST_BYTES])
{
    static const uint8_t domain[11] = {
        'V', 'O', 'S', 'B', 'K', '-', 'N', 'O', 'D', 'E', '\0'
    };
    uint8_t buf[11u + 2u * VOS_BK_DIGEST_BYTES];
    memcpy(buf, domain, sizeof(domain));
    memcpy(buf + 11u, left, VOS_BK_DIGEST_BYTES);
    memcpy(buf + 11u + VOS_BK_DIGEST_BYTES, right, VOS_BK_DIGEST_BYTES);
    (void)vos_sha256(buf, sizeof(buf), out);
}

static void merkle_empty_root(uint8_t out[VOS_BK_DIGEST_BYTES])
{
    static const uint8_t domain[12] = {
        'V', 'O', 'S', 'B', 'K', '-', 'E', 'M', 'P', 'T', 'Y', '\0'
    };
    (void)vos_sha256(domain, sizeof(domain), out);
}

static void merkle_compute_root_and_proof(
    const uint8_t leaves[VOS_BK_MAX_CHUNKS][VOS_BK_DIGEST_BYTES],
    uint32_t chunk_count,
    int32_t target_idx,
    uint8_t root_out[VOS_BK_DIGEST_BYTES],
    uint8_t proof_out[VOS_BK_MAX_MERKLE_DEPTH][VOS_BK_DIGEST_BYTES])
{
    if (chunk_count == 0u) {
        merkle_empty_root(root_out);
        return;
    }
    const uint32_t depth = vos_bk_merkle_depth(chunk_count);
    const uint32_t width = 1u << depth;
    uint8_t cur[VOS_BK_MAX_CHUNKS][VOS_BK_DIGEST_BYTES];
    uint8_t nxt[VOS_BK_MAX_CHUNKS][VOS_BK_DIGEST_BYTES];

    for (uint32_t i = 0u; i < chunk_count; ++i) {
        memcpy(cur[i], leaves[i], VOS_BK_DIGEST_BYTES);
    }
    for (uint32_t i = chunk_count; i < width; ++i) {
        merkle_pad_hash(i, cur[i]);
    }

    uint32_t w = width;
    for (uint32_t lvl = 0u; lvl < depth; ++lvl) {
        if (target_idx >= 0) {
            const uint32_t idx_at_lvl = ((uint32_t)target_idx) >> lvl;
            const uint32_t sib = idx_at_lvl ^ 1u;
            memcpy(proof_out[lvl], cur[sib], VOS_BK_DIGEST_BYTES);
        }
        const uint32_t half = w >> 1u;
        for (uint32_t j = 0u; j < half; ++j) {
            merkle_node_hash(cur[2u * j], cur[2u * j + 1u], nxt[j]);
        }
        for (uint32_t j = 0u; j < half; ++j) {
            memcpy(cur[j], nxt[j], VOS_BK_DIGEST_BYTES);
        }
        w = half;
    }
    memcpy(root_out, cur[0], VOS_BK_DIGEST_BYTES);
}

static int merkle_verify_proof(uint32_t chunk_index,
                               uint32_t chunk_count,
                               const uint8_t *ciphertext,
                               uint32_t ct_len,
                               const uint8_t tag[VOS_BK_TAG_BYTES],
                               const uint8_t *proof_bytes,
                               uint32_t depth,
                               const uint8_t expected_root[VOS_BK_DIGEST_BYTES])
{
    if (chunk_index >= chunk_count || depth != vos_bk_merkle_depth(chunk_count)) {
        return 0;
    }
    uint8_t acc[VOS_BK_DIGEST_BYTES];
    merkle_leaf_hash(chunk_index, ciphertext, ct_len, tag, acc);
    for (uint32_t lvl = 0u; lvl < depth; ++lvl) {
        const uint8_t *sib = proof_bytes + (size_t)lvl * VOS_BK_DIGEST_BYTES;
        uint8_t next[VOS_BK_DIGEST_BYTES];
        if (((chunk_index >> lvl) & 1u) == 0u) {
            merkle_node_hash(acc, sib, next);
        } else {
            merkle_node_hash(sib, acc, next);
        }
        memcpy(acc, next, VOS_BK_DIGEST_BYTES);
    }
    return ct_equal(acc, expected_root, VOS_BK_DIGEST_BYTES);
}

static void serialize_manifest_bytes(const struct vos_bk_manifest *m,
                                     uint8_t *out,
                                     size_t *out_len)
{
    put_be64(out, m->export_gen);
    put_be32(out + 8u, m->source_profile);
    put_be32(out + 12u, m->region_count);
    size_t pos = 16u;
    for (uint32_t i = 0u; i < m->region_count; ++i) {
        const struct vos_bk_region_desc *r = &m->regions[i];
        put_be32(out + pos, r->region_id);
        put_be32(out + pos + 4u, r->schema_id);
        put_be32(out + pos + 8u, r->schema_gen);
        put_be64(out + pos + 12u, r->payload_len);
        put_be32(out + pos + 20u, r->first_chunk);
        put_be32(out + pos + 24u, r->chunk_count);
        pos += VOS_BK_REGION_WIRE_BYTES;
    }
    put_be32(out + pos, m->chunk_size);
    put_be32(out + pos + 4u, m->chunk_count);
    memcpy(out + pos + 8u, m->merkle_root, VOS_BK_DIGEST_BYTES);
    *out_len = pos + 8u + VOS_BK_DIGEST_BYTES;
}

static void compute_catalog_ctx_digest(uint32_t profile_id,
                                       uint64_t total_extent,
                                       const struct vos_bk_manifest *m,
                                       uint8_t digest_out[VOS_BK_DIGEST_BYTES])
{
    static const uint8_t domain[9] = {
        'V', 'O', 'S', 'B', 'K', '-', 'C', 'T', 'X'
    };
    uint8_t buf[9u + 24u + 16u + VOS_BK_MAX_REGIONS * VOS_BK_REGION_WIRE_BYTES + 8u];
    memcpy(buf, domain, sizeof(domain));
    size_t pos = sizeof(domain);
    memcpy(buf + pos, VOS_BK_MAGIC, VOS_BK_MAGIC_BYTES);
    put_be32(buf + pos + 8u, VOS_BK_VERSION);
    put_be32(buf + pos + 12u, profile_id);
    put_be64(buf + pos + 16u, total_extent);
    pos += 24u;

    uint8_t manifest_tmp[VOS_BK_MANIFEST_FIXED_BYTES +
                         VOS_BK_MAX_REGIONS * VOS_BK_REGION_WIRE_BYTES];
    size_t mlen = 0u;
    serialize_manifest_bytes(m, manifest_tmp, &mlen);
    /* Exclude trailing 32-byte merkle_root to avoid circular commitment. */
    const size_t body_len = mlen - VOS_BK_DIGEST_BYTES;
    memcpy(buf + pos, manifest_tmp, body_len);
    pos += body_len;

    (void)vos_sha256(buf, pos, digest_out);
    zero_mem(buf, sizeof(buf));
    zero_mem(manifest_tmp, sizeof(manifest_tmp));
}

static void build_chunk_aad(const uint8_t ctx_digest[VOS_BK_DIGEST_BYTES],
                            uint32_t chunk_index,
                            uint32_t region_id,
                            uint64_t region_offset,
                            uint32_t plaintext_len,
                            uint8_t aad_out[52])
{
    memcpy(aad_out, ctx_digest, VOS_BK_DIGEST_BYTES);
    put_be32(aad_out + 32u, chunk_index);
    put_be32(aad_out + 36u, region_id);
    put_be64(aad_out + 40u, region_offset);
    put_be32(aad_out + 48u, plaintext_len);
}

enum vos_bk_status vos_bk_drbg_draw_key(struct vos_bk_drbg *drbg,
                                        uint8_t key_out[VOS_BK_KEY_BYTES],
                                        uint8_t manifest_nonce_out[VOS_BK_NONCE_BYTES])
{
    if (drbg == NULL || key_out == NULL || manifest_nonce_out == NULL) {
        return VOS_BK_ERR_INVALID;
    }
    if (drbg->healthy == 0u) {
        zero_mem(key_out, VOS_BK_KEY_BYTES);
        zero_mem(manifest_nonce_out, VOS_BK_NONCE_BYTES);
        return VOS_BK_ERR_ENTROPY;
    }
    uint8_t in_buf[VOS_BK_KEY_BYTES + 16u];
    memcpy(in_buf, drbg->seed, VOS_BK_KEY_BYTES);
    put_be64(in_buf + VOS_BK_KEY_BYTES, drbg->counter);
    memcpy(in_buf + VOS_BK_KEY_BYTES + 8u, "KEY-DRAW", 8u);
    (void)vos_sha256(in_buf, sizeof(in_buf), key_out);

    uint8_t nonce_digest[VOS_BK_DIGEST_BYTES];
    memcpy(in_buf + VOS_BK_KEY_BYTES + 8u, "MNF-NONC", 8u);
    (void)vos_sha256(in_buf, sizeof(in_buf), nonce_digest);
    memcpy(manifest_nonce_out, nonce_digest, VOS_BK_NONCE_BYTES);

    ++drbg->counter;
    zero_mem(in_buf, sizeof(in_buf));
    zero_mem(nonce_digest, sizeof(nonce_digest));
    return VOS_BK_OK;
}

static int region_is_exportable(const struct vos_bk_region_slot *reg)
{
    if (reg->kind != VOS_BK_KIND_ROLLBACKABLE ||
        reg->schema_class != VOS_BK_SCHEMA_DATA_ONLY) {
        return 0;
    }
    return 1;
}

static enum vos_bk_status build_export_catalog(
    const struct vos_bk_namespace *ns,
    uint32_t chunk_size,
    struct vos_bk_manifest *manifest_out,
    uint32_t slot_map_out[VOS_BK_MAX_REGIONS])
{
    memset(manifest_out, 0, sizeof(*manifest_out));
    manifest_out->export_gen = ns->generation;
    manifest_out->source_profile = ns->profile_id;
    manifest_out->chunk_size = chunk_size;

    uint32_t selected[VOS_BK_MAX_REGIONS];
    uint32_t sel_count = 0u;
    for (uint32_t i = 0u; i < ns->region_count; ++i) {
        if (!region_is_exportable(&ns->regions[i])) {
            continue;
        }
        selected[sel_count++] = i;
    }

    /* Sort selected regions in strict ascending region_id order. */
    for (uint32_t i = 0u; i < sel_count; ++i) {
        for (uint32_t j = i + 1u; j < sel_count; ++j) {
            if (ns->regions[selected[j]].region_id < ns->regions[selected[i]].region_id) {
                const uint32_t tmp = selected[i];
                selected[i] = selected[j];
                selected[j] = tmp;
            }
        }
    }

    uint32_t next_chunk = 0u;
    for (uint32_t i = 0u; i < sel_count; ++i) {
        const struct vos_bk_region_slot *src = &ns->regions[selected[i]];
        uint32_t r_chunks = 0u;
        if (src->payload_len > 0u) {
            r_chunks = (src->payload_len + chunk_size - 1u) / chunk_size;
        }
        if (next_chunk + r_chunks > VOS_BK_MAX_CHUNKS) {
            return VOS_BK_ERR_CAPACITY;
        }
        struct vos_bk_region_desc *desc = &manifest_out->regions[i];
        desc->region_id = src->region_id;
        desc->schema_id = src->schema_id;
        desc->schema_gen = src->schema_gen;
        desc->payload_len = src->payload_len;
        desc->first_chunk = next_chunk;
        desc->chunk_count = r_chunks;
        slot_map_out[i] = selected[i];
        next_chunk += r_chunks;
    }
    manifest_out->region_count = sel_count;
    manifest_out->chunk_count = next_chunk;
    return VOS_BK_OK;
}

static int find_region_for_chunk(const struct vos_bk_manifest *m,
                                 uint32_t chunk_index,
                                 uint32_t *reg_idx_out,
                                 uint64_t *offset_out,
                                 uint32_t *plen_out)
{
    for (uint32_t i = 0u; i < m->region_count; ++i) {
        const struct vos_bk_region_desc *r = &m->regions[i];
        if (chunk_index >= r->first_chunk &&
            chunk_index < r->first_chunk + r->chunk_count) {
            const uint32_t local_idx = chunk_index - r->first_chunk;
            const uint64_t off = (uint64_t)local_idx * (uint64_t)m->chunk_size;
            const uint64_t rem = r->payload_len - off;
            const uint32_t plen = (rem > (uint64_t)m->chunk_size)
                                    ? m->chunk_size
                                    : (uint32_t)rem;
            *reg_idx_out = i;
            *offset_out = off;
            *plen_out = plen;
            return 1;
        }
    }
    return 0;
}

enum vos_bk_status vos_bk_export(const struct vos_bk_device_store *store,
                                 struct vos_bk_consent *consent,
                                 struct vos_bk_drbg *drbg,
                                 uint32_t profile_id,
                                 uint32_t chunk_size,
                                 struct vos_bk_byte_sink *sink,
                                 uint8_t object_key_out[VOS_BK_KEY_BYTES])
{
    if (store == NULL || consent == NULL || drbg == NULL || sink == NULL ||
        sink->buf == NULL || object_key_out == NULL ||
        chunk_size == 0u || chunk_size > VOS_BK_MAX_CHUNK_SIZE) {
        return VOS_BK_ERR_INVALID;
    }
    const struct vos_bk_namespace *ns = vos_bk_active_namespace(store);
    if (ns == NULL || ns->profile_id != profile_id) {
        return VOS_BK_ERR_PROFILE_MISMATCH;
    }
    if (consent->valid == 0u || consent->consumed != 0u ||
        consent->unlocked == 0u || consent->credential_verified == 0u ||
        consent->op != VOS_BK_OP_EXPORT ||
        consent->source_profile != profile_id) {
        return VOS_BK_ERR_AUTH;
    }

    uint8_t object_key[VOS_BK_KEY_BYTES];
    uint8_t manifest_nonce[VOS_BK_NONCE_BYTES];
    enum vos_bk_status st = vos_bk_drbg_draw_key(drbg, object_key, manifest_nonce);
    if (st != VOS_BK_OK) {
        return st;
    }

    struct vos_bk_manifest manifest;
    uint32_t slot_map[VOS_BK_MAX_REGIONS];
    st = build_export_catalog(ns, chunk_size, &manifest, slot_map);
    if (st != VOS_BK_OK) {
        zero_mem(object_key, sizeof(object_key));
        return st;
    }

    const uint32_t depth = vos_bk_merkle_depth(manifest.chunk_count);
    const size_t manifest_len =
        VOS_BK_MANIFEST_FIXED_BYTES + (size_t)manifest.region_count * VOS_BK_REGION_WIRE_BYTES;
    size_t total_extent = VOS_BK_ENVELOPE_PREFIX_BYTES + manifest_len + VOS_BK_TAG_BYTES;
    for (uint32_t c = 0u; c < manifest.chunk_count; ++c) {
        uint32_t ridx = 0u;
        uint64_t roff = 0u;
        uint32_t plen = 0u;
        if (!find_region_for_chunk(&manifest, c, &ridx, &roff, &plen)) {
            zero_mem(object_key, sizeof(object_key));
            return VOS_BK_ERR_INVALID;
        }
        total_extent += VOS_BK_CHUNK_HEADER_BYTES + (size_t)plen +
                        VOS_BK_TAG_BYTES + (size_t)depth * VOS_BK_DIGEST_BYTES;
    }
    if (total_extent > sink->capacity || total_extent > VOS_BK_MAX_OBJECT_BYTES) {
        zero_mem(object_key, sizeof(object_key));
        sink->length = 0u;
        return VOS_BK_ERR_CAPACITY;
    }

    uint8_t manifest_key[VOS_BK_KEY_BYTES];
    uint8_t chunk_key[VOS_BK_KEY_BYTES];
    vos_bk_derive_subkeys(object_key, manifest_key, chunk_key);

    uint8_t ctx_digest[VOS_BK_DIGEST_BYTES];
    compute_catalog_ctx_digest(profile_id, (uint64_t)total_extent, &manifest, ctx_digest);

    /* Pass 1: encrypt each chunk sequentially in bounded single-chunk scratch to build leaf digests. */
    uint8_t leaves[VOS_BK_MAX_CHUNKS][VOS_BK_DIGEST_BYTES];
    memset(leaves, 0, sizeof(leaves));
    for (uint32_t c = 0u; c < manifest.chunk_count; ++c) {
        uint32_t ridx = 0u;
        uint64_t roff = 0u;
        uint32_t plen = 0u;
        (void)find_region_for_chunk(&manifest, c, &ridx, &roff, &plen);
        const struct vos_bk_region_slot *src = &ns->regions[slot_map[ridx]];
        uint8_t nonce[VOS_BK_NONCE_BYTES];
        uint8_t aad[52];
        uint8_t ct[VOS_BK_MAX_CHUNK_SIZE];
        uint8_t tag[VOS_BK_TAG_BYTES];
        vos_bk_chunk_nonce(c, nonce);
        build_chunk_aad(ctx_digest, c, src->region_id, roff, plen, aad);
        if (!vos_aes_gcm_encrypt(chunk_key, VOS_BK_KEY_BYTES, nonce, sizeof(nonce),
                                 aad, sizeof(aad), src->payload + roff, plen, ct, tag)) {
            zero_mem(object_key, sizeof(object_key));
            zero_mem(manifest_key, sizeof(manifest_key));
            zero_mem(chunk_key, sizeof(chunk_key));
            return VOS_BK_ERR_INVALID;
        }
        merkle_leaf_hash(c, ct, plen, tag, leaves[c]);
        zero_mem(ct, sizeof(ct));
    }
    merkle_compute_root_and_proof(leaves, manifest.chunk_count, -1,
                                  manifest.merkle_root, NULL);

    /* Write 40-byte envelope prefix. */
    uint8_t prefix[VOS_BK_ENVELOPE_PREFIX_BYTES];
    memcpy(prefix, VOS_BK_MAGIC, VOS_BK_MAGIC_BYTES);
    put_be32(prefix + 8u, VOS_BK_VERSION);
    put_be32(prefix + 12u, profile_id);
    put_be64(prefix + 16u, (uint64_t)total_extent);
    memcpy(prefix + 24u, manifest_nonce, VOS_BK_NONCE_BYTES);
    put_be32(prefix + 36u, (uint32_t)manifest_len);
    memcpy(sink->buf, prefix, VOS_BK_ENVELOPE_PREFIX_BYTES);

    /* Seal manifest plaintext with prefix as AAD. */
    uint8_t manifest_pt[VOS_BK_MANIFEST_FIXED_BYTES +
                        VOS_BK_MAX_REGIONS * VOS_BK_REGION_WIRE_BYTES];
    size_t actual_mlen = 0u;
    serialize_manifest_bytes(&manifest, manifest_pt, &actual_mlen);
    uint8_t *enc_manifest_dst = sink->buf + VOS_BK_ENVELOPE_PREFIX_BYTES;
    uint8_t *mtag_dst = enc_manifest_dst + actual_mlen;
    if (!vos_aes_gcm_encrypt(manifest_key, VOS_BK_KEY_BYTES,
                             manifest_nonce, VOS_BK_NONCE_BYTES,
                             prefix, sizeof(prefix),
                             manifest_pt, actual_mlen,
                             enc_manifest_dst, mtag_dst)) {
        zero_mem(object_key, sizeof(object_key));
        zero_mem(manifest_key, sizeof(manifest_key));
        zero_mem(chunk_key, sizeof(chunk_key));
        zero_mem(manifest_pt, sizeof(manifest_pt));
        return VOS_BK_ERR_INVALID;
    }
    zero_mem(manifest_pt, sizeof(manifest_pt));

    /* Pass 2: stream ordered chunk records into sink. */
    size_t cursor = VOS_BK_ENVELOPE_PREFIX_BYTES + actual_mlen + VOS_BK_TAG_BYTES;
    for (uint32_t c = 0u; c < manifest.chunk_count; ++c) {
        uint32_t ridx = 0u;
        uint64_t roff = 0u;
        uint32_t plen = 0u;
        (void)find_region_for_chunk(&manifest, c, &ridx, &roff, &plen);
        const struct vos_bk_region_slot *src = &ns->regions[slot_map[ridx]];

        uint8_t nonce[VOS_BK_NONCE_BYTES];
        uint8_t aad[52];
        uint8_t ct[VOS_BK_MAX_CHUNK_SIZE];
        uint8_t tag[VOS_BK_TAG_BYTES];
        uint8_t proof[VOS_BK_MAX_MERKLE_DEPTH][VOS_BK_DIGEST_BYTES];
        uint8_t root_chk[VOS_BK_DIGEST_BYTES];

        vos_bk_chunk_nonce(c, nonce);
        build_chunk_aad(ctx_digest, c, src->region_id, roff, plen, aad);
        if (!vos_aes_gcm_encrypt(chunk_key, VOS_BK_KEY_BYTES, nonce, sizeof(nonce),
                                 aad, sizeof(aad), src->payload + roff, plen, ct, tag)) {
            zero_mem(object_key, sizeof(object_key));
            zero_mem(manifest_key, sizeof(manifest_key));
            zero_mem(chunk_key, sizeof(chunk_key));
            return VOS_BK_ERR_INVALID;
        }
        merkle_compute_root_and_proof(leaves, manifest.chunk_count, (int32_t)c,
                                      root_chk, proof);

        put_be32(sink->buf + cursor, c);
        put_be32(sink->buf + cursor + 4u, src->region_id);
        put_be64(sink->buf + cursor + 8u, roff);
        put_be32(sink->buf + cursor + 16u, plen);
        cursor += VOS_BK_CHUNK_HEADER_BYTES;
        memcpy(sink->buf + cursor, ct, plen);
        cursor += plen;
        memcpy(sink->buf + cursor, tag, VOS_BK_TAG_BYTES);
        cursor += VOS_BK_TAG_BYTES;
        for (uint32_t lvl = 0u; lvl < depth; ++lvl) {
            memcpy(sink->buf + cursor, proof[lvl], VOS_BK_DIGEST_BYTES);
            cursor += VOS_BK_DIGEST_BYTES;
        }
        zero_mem(ct, sizeof(ct));
    }

    sink->length = cursor;
    consent->consumed = 1u;
    memcpy(object_key_out, object_key, VOS_BK_KEY_BYTES);

    zero_mem(object_key, sizeof(object_key));
    zero_mem(manifest_key, sizeof(manifest_key));
    zero_mem(chunk_key, sizeof(chunk_key));
    zero_mem(leaves, sizeof(leaves));
    return VOS_BK_OK;
}

static int parse_and_validate_manifest(const uint8_t *pt,
                                       size_t pt_len,
                                       uint32_t expected_chunk_size,
                                       struct vos_bk_manifest *m_out)
{
    if (pt_len < VOS_BK_MANIFEST_FIXED_BYTES) {
        return 0;
    }
    memset(m_out, 0, sizeof(*m_out));
    m_out->export_gen = get_be64(pt);
    m_out->source_profile = get_be32(pt + 8u);
    m_out->region_count = get_be32(pt + 12u);
    if (m_out->region_count > VOS_BK_MAX_REGIONS) {
        return 0;
    }
    const size_t expected_len =
        VOS_BK_MANIFEST_FIXED_BYTES + (size_t)m_out->region_count * VOS_BK_REGION_WIRE_BYTES;
    if (pt_len != expected_len) {
        return 0;
    }
    size_t pos = 16u;
    for (uint32_t i = 0u; i < m_out->region_count; ++i) {
        struct vos_bk_region_desc *r = &m_out->regions[i];
        r->region_id = get_be32(pt + pos);
        r->schema_id = get_be32(pt + pos + 4u);
        r->schema_gen = get_be32(pt + pos + 8u);
        r->payload_len = get_be64(pt + pos + 12u);
        r->first_chunk = get_be32(pt + pos + 20u);
        r->chunk_count = get_be32(pt + pos + 24u);
        pos += VOS_BK_REGION_WIRE_BYTES;
    }
    m_out->chunk_size = get_be32(pt + pos);
    m_out->chunk_count = get_be32(pt + pos + 4u);
    memcpy(m_out->merkle_root, pt + pos + 8u, VOS_BK_DIGEST_BYTES);

    if (m_out->chunk_size == 0u || m_out->chunk_size != expected_chunk_size ||
        m_out->chunk_count > VOS_BK_MAX_CHUNKS) {
        return 0;
    }

    uint32_t next_chunk = 0u;
    for (uint32_t i = 0u; i < m_out->region_count; ++i) {
        const struct vos_bk_region_desc *r = &m_out->regions[i];
        if (i > 0u && r->region_id <= m_out->regions[i - 1u].region_id) {
            return 0;
        }
        if (r->first_chunk != next_chunk || r->payload_len > VOS_BK_MAX_REGION_PAYLOAD) {
            return 0;
        }
        if (r->payload_len == 0u) {
            if (r->chunk_count != 0u) {
                return 0;
            }
        } else {
            if (r->chunk_count == 0u || r->chunk_count > VOS_BK_MAX_CHUNKS) {
                return 0;
            }
            const uint64_t min_len = (uint64_t)(r->chunk_count - 1u) * (uint64_t)m_out->chunk_size;
            const uint64_t max_len = (uint64_t)r->chunk_count * (uint64_t)m_out->chunk_size;
            if (r->payload_len <= min_len || r->payload_len > max_len) {
                return 0;
            }
        }
        next_chunk += r->chunk_count;
    }
    if (next_chunk != m_out->chunk_count) {
        return 0;
    }
    return 1;
}

void vos_bk_restore_init(struct vos_bk_restore_ctx *ctx)
{
    if (ctx == NULL) {
        return;
    }
    memset(ctx, 0, sizeof(*ctx));
    ctx->phase = VOS_BK_PHASE_IDLE;
}

void vos_bk_restore_discard(struct vos_bk_restore_ctx *ctx,
                            struct vos_bk_device_store *store)
{
    if (ctx != NULL) {
        zero_mem(ctx->manifest_key, sizeof(ctx->manifest_key));
        zero_mem(ctx->chunk_key, sizeof(ctx->chunk_key));
        ctx->phase = VOS_BK_PHASE_DISCARDED;
    }
    if (store != NULL && store->staging_idx < 2u) {
        store->staging_valid = 0u;
        zero_mem(&store->slots[store->staging_idx], sizeof(store->slots[store->staging_idx]));
    }
}

enum vos_bk_status vos_bk_restore_authorize(struct vos_bk_restore_ctx *ctx,
                                            struct vos_bk_consent *consent,
                                            uint32_t expected_source_profile,
                                            uint32_t local_profile_id,
                                            const uint8_t object_key[VOS_BK_KEY_BYTES])
{
    if (ctx == NULL || consent == NULL || object_key == NULL) {
        return VOS_BK_ERR_INVALID;
    }
    if (ctx->phase != VOS_BK_PHASE_IDLE) {
        return VOS_BK_ERR_STATE;
    }
    if (consent->valid == 0u || consent->consumed != 0u ||
        consent->unlocked == 0u || consent->credential_verified == 0u ||
        consent->op != VOS_BK_OP_RESTORE ||
        consent->source_profile != expected_source_profile ||
        consent->target_profile != local_profile_id) {
        ctx->phase = VOS_BK_PHASE_DISCARDED;
        return VOS_BK_ERR_AUTH;
    }
    if (expected_source_profile != local_profile_id &&
        consent->allow_profile_mapping == 0u) {
        ctx->phase = VOS_BK_PHASE_DISCARDED;
        return VOS_BK_ERR_PROFILE_MISMATCH;
    }
    vos_bk_derive_subkeys(object_key, ctx->manifest_key, ctx->chunk_key);
    ctx->phase = VOS_BK_PHASE_AUTHORIZED;
    return VOS_BK_OK;
}

enum vos_bk_status vos_bk_restore_auth_manifest(struct vos_bk_restore_ctx *ctx,
                                                const struct vos_bk_byte_source *src,
                                                uint32_t expected_profile_id,
                                                uint32_t expected_chunk_size,
                                                size_t *chunks_offset_out)
{
    if (ctx == NULL || src == NULL || src->buf == NULL || chunks_offset_out == NULL) {
        return VOS_BK_ERR_INVALID;
    }
    if (ctx->phase != VOS_BK_PHASE_AUTHORIZED) {
        return VOS_BK_ERR_STATE;
    }
    if (src->length < VOS_BK_ENVELOPE_PREFIX_BYTES + VOS_BK_MANIFEST_FIXED_BYTES + VOS_BK_TAG_BYTES) {
        vos_bk_restore_discard(ctx, NULL);
        return VOS_BK_ERR_ENVELOPE;
    }
    if (memcmp(src->buf, VOS_BK_MAGIC, VOS_BK_MAGIC_BYTES) != 0) {
        vos_bk_restore_discard(ctx, NULL);
        return VOS_BK_ERR_ENVELOPE;
    }
    const uint32_t ver = get_be32(src->buf + 8u);
    const uint32_t prof = get_be32(src->buf + 12u);
    const uint64_t total_extent = get_be64(src->buf + 16u);
    const uint8_t *manifest_nonce = src->buf + 24u;
    const uint32_t enc_mlen = get_be32(src->buf + 36u);

    if (ver != VOS_BK_VERSION || prof != expected_profile_id ||
        total_extent != (uint64_t)src->length ||
        enc_mlen < VOS_BK_MANIFEST_FIXED_BYTES ||
        enc_mlen > VOS_BK_MANIFEST_FIXED_BYTES + VOS_BK_MAX_REGIONS * VOS_BK_REGION_WIRE_BYTES ||
        ((enc_mlen - VOS_BK_MANIFEST_FIXED_BYTES) % VOS_BK_REGION_WIRE_BYTES) != 0u) {
        vos_bk_restore_discard(ctx, NULL);
        return VOS_BK_ERR_ENVELOPE;
    }
    const size_t min_after = VOS_BK_ENVELOPE_PREFIX_BYTES + (size_t)enc_mlen + VOS_BK_TAG_BYTES;
    if (min_after > src->length) {
        vos_bk_restore_discard(ctx, NULL);
        return VOS_BK_ERR_ENVELOPE;
    }

    uint8_t pt[VOS_BK_MANIFEST_FIXED_BYTES + VOS_BK_MAX_REGIONS * VOS_BK_REGION_WIRE_BYTES];
    const uint8_t *enc_m = src->buf + VOS_BK_ENVELOPE_PREFIX_BYTES;
    const uint8_t *mtag = enc_m + enc_mlen;
    if (!vos_aes_gcm_open(ctx->manifest_key, VOS_BK_KEY_BYTES,
                          manifest_nonce, VOS_BK_NONCE_BYTES,
                          src->buf, VOS_BK_ENVELOPE_PREFIX_BYTES,
                          enc_m, enc_mlen, mtag, pt)) {
        zero_mem(pt, sizeof(pt));
        vos_bk_restore_discard(ctx, NULL);
        return VOS_BK_ERR_MANIFEST_TAG;
    }

    if (!parse_and_validate_manifest(pt, enc_mlen, expected_chunk_size, &ctx->manifest)) {
        zero_mem(pt, sizeof(pt));
        vos_bk_restore_discard(ctx, NULL);
        return VOS_BK_ERR_MANIFEST_FORMAT;
    }
    zero_mem(pt, sizeof(pt));

    if (ctx->manifest.source_profile != expected_profile_id) {
        vos_bk_restore_discard(ctx, NULL);
        return VOS_BK_ERR_PROFILE_MISMATCH;
    }

    ctx->total_extent = total_extent;
    ctx->merkle_depth = vos_bk_merkle_depth(ctx->manifest.chunk_count);
    compute_catalog_ctx_digest(prof, total_extent, &ctx->manifest, ctx->catalog_ctx_digest);
    *chunks_offset_out = min_after;
    ctx->phase = VOS_BK_PHASE_MANIFEST_AUTH;
    return VOS_BK_OK;
}

static const struct vos_bk_schema_rule *find_schema_rule(
    const struct vos_bk_restore_policy *policy,
    const struct vos_bk_region_desc *desc)
{
    for (uint32_t i = 0u; i < policy->rule_count; ++i) {
        const struct vos_bk_schema_rule *r = &policy->rules[i];
        if (r->region_id == desc->region_id &&
            r->source_schema_id == desc->schema_id &&
            r->source_schema_gen == desc->schema_gen) {
            return r;
        }
    }
    return NULL;
}

enum vos_bk_status vos_bk_restore_plan(struct vos_bk_restore_ctx *ctx,
                                       struct vos_bk_device_store *store,
                                       const struct vos_bk_restore_policy *policy,
                                       const struct vos_bk_consent *consent)
{
    if (ctx == NULL || store == NULL || policy == NULL || consent == NULL) {
        return VOS_BK_ERR_INVALID;
    }
    if (ctx->phase != VOS_BK_PHASE_MANIFEST_AUTH) {
        return VOS_BK_ERR_STATE;
    }
    const struct vos_bk_namespace *active = vos_bk_active_namespace(store);
    if (active == NULL ||
        policy->expected_source_profile != ctx->manifest.source_profile ||
        policy->local_profile_id != active->profile_id) {
        vos_bk_restore_discard(ctx, NULL);
        return VOS_BK_ERR_PROFILE_MISMATCH;
    }
    if (policy->expected_source_profile != policy->local_profile_id &&
        (policy->allow_profile_mapping == 0u || consent->allow_profile_mapping == 0u)) {
        vos_bk_restore_discard(ctx, NULL);
        return VOS_BK_ERR_PROFILE_MISMATCH;
    }
    for (uint32_t i = 0u; i < active->fresh_count; ++i) {
        if (active->fresh[i].has_initializer == 0u) {
            vos_bk_restore_discard(ctx, NULL);
            return VOS_BK_ERR_FRESH_DENIED;
        }
    }

    for (uint32_t i = 0u; i < ctx->manifest.region_count; ++i) {
        const struct vos_bk_region_desc *desc = &ctx->manifest.regions[i];
        const struct vos_bk_schema_rule *rule = find_schema_rule(policy, desc);
        enum vos_bk_plan_arm arm = (rule != NULL) ? rule->arm : VOS_BK_PLAN_UNSUPPORTED;
        if (arm == VOS_BK_PLAN_UNSUPPORTED) {
            vos_bk_restore_discard(ctx, NULL);
            return VOS_BK_ERR_UNSUPPORTED_SCHEMA;
        }
        if (arm == VOS_BK_PLAN_DISCARD && consent->allow_discard == 0u) {
            vos_bk_restore_discard(ctx, NULL);
            return VOS_BK_ERR_UNSUPPORTED_SCHEMA;
        }
        ctx->region_arms[i] = arm;
        ctx->region_target_schema_id[i] =
            (arm == VOS_BK_PLAN_MIGRATE) ? rule->target_schema_id : desc->schema_id;
        ctx->region_target_schema_gen[i] =
            (arm == VOS_BK_PLAN_MIGRATE) ? rule->target_schema_gen : desc->schema_gen;
        ctx->region_migrate_xor[i] = (arm == VOS_BK_PLAN_MIGRATE) ? rule->migrate_xor_mask : 0u;
    }

    ctx->phase = VOS_BK_PHASE_PLANNED;
    return VOS_BK_OK;
}

static void prepare_staging_namespace(struct vos_bk_restore_ctx *ctx,
                                      struct vos_bk_device_store *store)
{
    const uint32_t act = store->active_idx;
    const uint32_t stg = 1u - act;
    store->staging_idx = stg;
    store->staging_valid = 1u;

    const struct vos_bk_namespace *src_ns = &store->slots[act];
    struct vos_bk_namespace *dst_ns = &store->slots[stg];
    memset(dst_ns, 0, sizeof(*dst_ns));
    dst_ns->profile_id = src_ns->profile_id;
    dst_ns->generation = ctx->manifest.export_gen;
    dst_ns->consent_grant_count = 0u;

    /* Preserve Fresh slot declarations for post-commit fresh initialization. */
    dst_ns->fresh_count = src_ns->fresh_count;
    for (uint32_t i = 0u; i < src_ns->fresh_count; ++i) {
        dst_ns->fresh[i].region_id = src_ns->fresh[i].region_id;
        dst_ns->fresh[i].fresh_class = src_ns->fresh[i].fresh_class;
        dst_ns->fresh[i].has_initializer = src_ns->fresh[i].has_initializer;
    }

    /* Pre-create non-discarded rollbackable region slots in staging namespace. */
    uint32_t dst_rcount = 0u;
    for (uint32_t i = 0u; i < ctx->manifest.region_count; ++i) {
        if (ctx->region_arms[i] == VOS_BK_PLAN_DISCARD) {
            ctx->staged_region_idx[i] = UINT32_MAX;
            continue;
        }
        const struct vos_bk_region_desc *desc = &ctx->manifest.regions[i];
        struct vos_bk_region_slot *slot = &dst_ns->regions[dst_rcount];
        slot->region_id = desc->region_id;
        slot->kind = VOS_BK_KIND_ROLLBACKABLE;
        slot->schema_class = VOS_BK_SCHEMA_DATA_ONLY;
        slot->schema_id = ctx->region_target_schema_id[i];
        slot->schema_gen = ctx->region_target_schema_gen[i];
        slot->payload_len = (uint32_t)desc->payload_len;
        ctx->staged_region_idx[i] = dst_rcount;
        ++dst_rcount;
    }
    dst_ns->region_count = dst_rcount;
}

enum vos_bk_status vos_bk_restore_stage_next_chunk(struct vos_bk_restore_ctx *ctx,
                                                   struct vos_bk_device_store *store,
                                                   const struct vos_bk_byte_source *src,
                                                   size_t *cursor_io)
{
    if (ctx == NULL || store == NULL || src == NULL || src->buf == NULL || cursor_io == NULL) {
        return VOS_BK_ERR_INVALID;
    }
    if (ctx->phase != VOS_BK_PHASE_PLANNED && ctx->phase != VOS_BK_PHASE_STAGING) {
        return VOS_BK_ERR_STATE;
    }
    if (ctx->staged_chunks >= ctx->manifest.chunk_count) {
        vos_bk_restore_discard(ctx, store);
        return VOS_BK_ERR_CHUNK_GEOMETRY;
    }

    if (ctx->phase == VOS_BK_PHASE_PLANNED) {
        prepare_staging_namespace(ctx, store);
    }

    const size_t pos = *cursor_io;
    if (pos + VOS_BK_CHUNK_HEADER_BYTES > src->length) {
        vos_bk_restore_discard(ctx, store);
        return VOS_BK_ERR_ENVELOPE;
    }

    const uint32_t cidx = get_be32(src->buf + pos);
    const uint32_t rid = get_be32(src->buf + pos + 4u);
    const uint64_t roff = get_be64(src->buf + pos + 8u);
    const uint32_t plen = get_be32(src->buf + pos + 16u);

    uint32_t exp_ridx = 0u;
    uint64_t exp_roff = 0u;
    uint32_t exp_plen = 0u;
    if (!find_region_for_chunk(&ctx->manifest, ctx->staged_chunks,
                               &exp_ridx, &exp_roff, &exp_plen) ||
        cidx != ctx->staged_chunks ||
        rid != ctx->manifest.regions[exp_ridx].region_id ||
        roff != exp_roff || plen != exp_plen || plen == 0u ||
        plen > VOS_BK_MAX_CHUNK_SIZE) {
        vos_bk_restore_discard(ctx, store);
        return VOS_BK_ERR_CHUNK_GEOMETRY;
    }

    const size_t proof_bytes_len = (size_t)ctx->merkle_depth * VOS_BK_DIGEST_BYTES;
    const size_t total_chunk_bytes =
        VOS_BK_CHUNK_HEADER_BYTES + (size_t)plen + VOS_BK_TAG_BYTES + proof_bytes_len;
    if (pos + total_chunk_bytes > src->length) {
        vos_bk_restore_discard(ctx, store);
        return VOS_BK_ERR_ENVELOPE;
    }

    const uint8_t *ct = src->buf + pos + VOS_BK_CHUNK_HEADER_BYTES;
    const uint8_t *tag = ct + plen;
    const uint8_t *proof = tag + VOS_BK_TAG_BYTES;

    if (!merkle_verify_proof(cidx, ctx->manifest.chunk_count, ct, plen, tag,
                             proof, ctx->merkle_depth, ctx->manifest.merkle_root)) {
        vos_bk_restore_discard(ctx, store);
        return VOS_BK_ERR_MERKLE_PROOF;
    }

    uint8_t nonce[VOS_BK_NONCE_BYTES];
    uint8_t aad[52];
    uint8_t pt_buf[VOS_BK_MAX_CHUNK_SIZE];
    vos_bk_chunk_nonce(cidx, nonce);
    build_chunk_aad(ctx->catalog_ctx_digest, cidx, rid, roff, plen, aad);
    if (!vos_aes_gcm_open(ctx->chunk_key, VOS_BK_KEY_BYTES, nonce, sizeof(nonce),
                          aad, sizeof(aad), ct, plen, tag, pt_buf)) {
        zero_mem(pt_buf, sizeof(pt_buf));
        vos_bk_restore_discard(ctx, store);
        return VOS_BK_ERR_CHUNK_AUTH;
    }

    if (ctx->region_arms[exp_ridx] != VOS_BK_PLAN_DISCARD) {
        const uint32_t dst_idx = ctx->staged_region_idx[exp_ridx];
        struct vos_bk_namespace *staging_ns = &store->slots[store->staging_idx];
        struct vos_bk_region_slot *dst_slot = &staging_ns->regions[dst_idx];
        if (ctx->region_arms[exp_ridx] == VOS_BK_PLAN_MIGRATE) {
            const uint8_t mask = ctx->region_migrate_xor[exp_ridx];
            for (uint32_t k = 0u; k < plen; ++k) {
                dst_slot->payload[roff + k] = (uint8_t)(pt_buf[k] ^ mask);
            }
        } else {
            memcpy(dst_slot->payload + roff, pt_buf, plen);
        }
        ctx->region_bytes_written[exp_ridx] += plen;
        ++store->write_counter;
    }

    zero_mem(pt_buf, sizeof(pt_buf));
    *cursor_io = pos + total_chunk_bytes;
    ++ctx->staged_chunks;
    ctx->phase = VOS_BK_PHASE_STAGING;
    return VOS_BK_OK;
}

enum vos_bk_status vos_bk_restore_complete(struct vos_bk_restore_ctx *ctx,
                                           const struct vos_bk_byte_source *src,
                                           size_t cursor)
{
    if (ctx == NULL || src == NULL) {
        return VOS_BK_ERR_INVALID;
    }
    if (ctx->phase != VOS_BK_PHASE_STAGING &&
        !(ctx->phase == VOS_BK_PHASE_PLANNED && ctx->manifest.chunk_count == 0u)) {
        return VOS_BK_ERR_STATE;
    }
    if (ctx->staged_chunks != ctx->manifest.chunk_count ||
        cursor != src->length ||
        (uint64_t)cursor != ctx->total_extent) {
        vos_bk_restore_discard(ctx, NULL);
        return VOS_BK_ERR_ENVELOPE;
    }
    for (uint32_t i = 0u; i < ctx->manifest.region_count; ++i) {
        if (ctx->region_arms[i] != VOS_BK_PLAN_DISCARD &&
            (uint64_t)ctx->region_bytes_written[i] != ctx->manifest.regions[i].payload_len) {
            vos_bk_restore_discard(ctx, NULL);
            return VOS_BK_ERR_CHUNK_GEOMETRY;
        }
    }
    ctx->phase = VOS_BK_PHASE_COMPLETE;
    return VOS_BK_OK;
}

static void init_fresh_slot_post_restore(struct vos_bk_fresh_slot *fs,
                                         uint64_t new_epoch)
{
    const uint32_t rid = fs->region_id;
    const enum vos_bk_fresh_class cls = fs->fresh_class;
    const uint32_t has_init = fs->has_initializer;
    memset(fs, 0, sizeof(*fs));
    fs->region_id = rid;
    fs->fresh_class = cls;
    fs->has_initializer = has_init;
    fs->enrolled = 0u;
    fs->reconciled = 0u;
    fs->scope_epoch = new_epoch;
    fs->attempts_remaining = 0u;
    fs->spent_count = 0u;
}

enum vos_bk_status vos_bk_restore_commit(struct vos_bk_restore_ctx *ctx,
                                         struct vos_bk_device_store *store,
                                         struct vos_bk_consent *consent)
{
    if (ctx == NULL || store == NULL || consent == NULL) {
        return VOS_BK_ERR_INVALID;
    }
    if (ctx->phase != VOS_BK_PHASE_COMPLETE) {
        return VOS_BK_ERR_STATE;
    }
    if (consent->valid == 0u || consent->consumed != 0u) {
        vos_bk_restore_discard(ctx, store);
        return VOS_BK_ERR_AUTH;
    }
    if (ctx->manifest.chunk_count == 0u && store->staging_valid == 0u) {
        prepare_staging_namespace(ctx, store);
    }

    struct vos_bk_namespace *staging_ns = &store->slots[store->staging_idx];
    staging_ns->consent_grant_count = 0u;
    for (uint32_t i = 0u; i < staging_ns->fresh_count; ++i) {
        init_fresh_slot_post_restore(&staging_ns->fresh[i], store->next_epoch);
        ++store->next_epoch;
    }

    consent->consumed = 1u;
    store->active_idx = store->staging_idx;
    store->staging_idx = 1u - store->active_idx;
    store->staging_valid = 0u;

    zero_mem(ctx->manifest_key, sizeof(ctx->manifest_key));
    zero_mem(ctx->chunk_key, sizeof(ctx->chunk_key));
    ctx->phase = VOS_BK_PHASE_COMMITTED;
    return VOS_BK_OK;
}

enum vos_bk_status vos_bk_restore_stream(struct vos_bk_device_store *store,
                                         struct vos_bk_consent *consent,
                                         const struct vos_bk_restore_policy *policy,
                                         const uint8_t object_key[VOS_BK_KEY_BYTES],
                                         const struct vos_bk_byte_source *src)
{
    if (store == NULL || consent == NULL || policy == NULL ||
        object_key == NULL || src == NULL) {
        return VOS_BK_ERR_INVALID;
    }
    struct vos_bk_restore_ctx ctx;
    vos_bk_restore_init(&ctx);

    enum vos_bk_status st = vos_bk_restore_authorize(
        &ctx, consent, policy->expected_source_profile,
        policy->local_profile_id, object_key);
    if (st != VOS_BK_OK) {
        return st;
    }

    size_t cursor = 0u;
    st = vos_bk_restore_auth_manifest(
        &ctx, src, policy->expected_source_profile, policy->chunk_size, &cursor);
    if (st != VOS_BK_OK) {
        return st;
    }

    st = vos_bk_restore_plan(&ctx, store, policy, consent);
    if (st != VOS_BK_OK) {
        return st;
    }

    for (uint32_t c = 0u; c < ctx.manifest.chunk_count; ++c) {
        st = vos_bk_restore_stage_next_chunk(&ctx, store, src, &cursor);
        if (st != VOS_BK_OK) {
            return st;
        }
    }

    st = vos_bk_restore_complete(&ctx, src, cursor);
    if (st != VOS_BK_OK) {
        vos_bk_restore_discard(&ctx, store);
        return st;
    }

    return vos_bk_restore_commit(&ctx, store, consent);
}

enum vos_bk_status vos_bk_fresh_check_token(const struct vos_bk_device_store *store,
                                            uint32_t region_id,
                                            uint64_t token)
{
    const struct vos_bk_namespace *ns = vos_bk_active_namespace(store);
    if (ns == NULL) {
        return VOS_BK_ERR_INVALID;
    }
    for (uint32_t i = 0u; i < ns->fresh_count; ++i) {
        const struct vos_bk_fresh_slot *fs = &ns->fresh[i];
        if (fs->region_id != region_id) {
            continue;
        }
        if (fs->enrolled == 0u || fs->reconciled == 0u) {
            return VOS_BK_ERR_FRESH_DENIED;
        }
        for (uint32_t t = 0u; t < fs->spent_count; ++t) {
            if (fs->spent_tokens[t] == token) {
                return VOS_BK_ERR_FRESH_DENIED;
            }
        }
        return VOS_BK_OK;
    }
    return VOS_BK_ERR_FRESH_DENIED;
}

enum vos_bk_status vos_bk_fresh_check_attempt(const struct vos_bk_device_store *store,
                                              uint32_t region_id)
{
    const struct vos_bk_namespace *ns = vos_bk_active_namespace(store);
    if (ns == NULL) {
        return VOS_BK_ERR_INVALID;
    }
    for (uint32_t i = 0u; i < ns->fresh_count; ++i) {
        const struct vos_bk_fresh_slot *fs = &ns->fresh[i];
        if (fs->region_id != region_id) {
            continue;
        }
        if (fs->enrolled == 0u || fs->attempts_remaining == 0u) {
            return VOS_BK_ERR_FRESH_DENIED;
        }
        return VOS_BK_OK;
    }
    return VOS_BK_ERR_FRESH_DENIED;
}
