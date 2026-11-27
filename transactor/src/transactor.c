// SPDX-License-Identifier: Apache-2.0
#include "vos_transactor.h"

_Static_assert((unsigned)VOS_TX_DIGEST_BYTES == (unsigned)VOS_CRYPTO_DIGEST_BYTES,
               "digest width must match vos_crypto_core");
_Static_assert((unsigned)VOS_TX_COPIES_PER_SLOT >= 2u,
               "R-10-001a requires at least two root copies per slot");
_Static_assert((unsigned)VOS_TX_MAX_COPIES >= (unsigned)VOS_TX_COPIES_PER_SLOT,
               "max root copies must admit minimum copy floor");

enum {
    VOS_TX_OBJ_HEADER_BYTES = 16u,
    VOS_TX_OBJ_BUF_BYTES =
        VOS_TX_OBJ_HEADER_BYTES + VOS_TX_MAX_PAYLOAD +
        (VOS_TX_MAX_KIDS * VOS_TX_DIGEST_BYTES),
    VOS_TX_ROOT_ENC_BYTES = 8u + VOS_TX_DIGEST_BYTES + 24u
};

static void copy_bytes(uint8_t *dst, const uint8_t *src, size_t len)
{
    for (size_t i = 0u; i < len; ++i) {
        dst[i] = src[i];
    }
}

static void zero_bytes(uint8_t *dst, size_t len)
{
    for (size_t i = 0u; i < len; ++i) {
        dst[i] = 0u;
    }
}

static int equal_bytes_ct(const uint8_t *a, const uint8_t *b, size_t len)
{
    uint8_t diff = 0u;
    for (size_t i = 0u; i < len; ++i) {
        diff |= (uint8_t)(a[i] ^ b[i]);
    }
    return diff == 0u;
}

static int equal_hashes(const struct vos_tx_hash *a, const struct vos_tx_hash *b)
{
    return equal_bytes_ct(a->bytes, b->bytes, VOS_TX_DIGEST_BYTES);
}

static int signed_roots_equal(const struct vos_tx_signed_root *a,
                              const struct vos_tx_signed_root *b)
{
    return equal_hashes(&a->root, &b->root) &&
           a->version == b->version &&
           a->declared_floor == b->declared_floor &&
           a->key_id == b->key_id &&
           equal_bytes_ct(a->sig, b->sig, VOS_TX_DIGEST_BYTES) &&
           equal_bytes_ct(a->checksum, b->checksum, VOS_TX_DIGEST_BYTES);
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

static const struct vos_tx_store_entry *store_find(const struct vos_tx_store *store,
                                                   const struct vos_tx_hash *addr)
{
    if (store == NULL || addr == NULL || store->count > VOS_TX_MAX_OBJECTS) {
        return NULL;
    }
    for (uint32_t i = 0u; i < VOS_TX_MAX_OBJECTS; ++i) {
        if (store->entries[i].occupied != 0u &&
            equal_hashes(&store->entries[i].addr, addr)) {
            return &store->entries[i];
        }
    }
    return NULL;
}

static void encode_signed_root(const struct vos_tx_signed_root *sr,
                               uint8_t out[VOS_TX_ROOT_ENC_BYTES])
{
    out[0] = 'V';
    out[1] = 'O';
    out[2] = 'S';
    out[3] = 'T';
    out[4] = 'X';
    out[5] = 'R';
    out[6] = 'T';
    out[7] = '1';
    copy_bytes(out + 8u, sr->root.bytes, VOS_TX_DIGEST_BYTES);
    put_le64(out + 8u + VOS_TX_DIGEST_BYTES, sr->version);
    put_le64(out + 16u + VOS_TX_DIGEST_BYTES, sr->declared_floor);
    put_le64(out + 24u + VOS_TX_DIGEST_BYTES, sr->key_id);
}

static const struct vos_tx_enrolled_key *find_enrolled_key(const struct vos_tx_policy *policy,
                                                           uint64_t key_id)
{
    if (policy == NULL || policy->key_count > VOS_TX_MAX_ENROLLED_KEYS) {
        return NULL;
    }
    for (uint32_t i = 0u; i < policy->key_count; ++i) {
        if (policy->keys[i].enrolled != 0u && policy->keys[i].key_id == key_id) {
            return &policy->keys[i];
        }
    }
    return NULL;
}

static int hash_in_list(const struct vos_tx_hash *list,
                        uint32_t count,
                        const struct vos_tx_hash *needle)
{
    for (uint32_t i = 0u; i < count; ++i) {
        if (equal_hashes(&list[i], needle)) {
            return 1;
        }
    }
    return 0;
}

void vos_tx_store_init(struct vos_tx_store *store)
{
    if (store == NULL) {
        return;
    }
    store->count = 0u;
    for (uint32_t i = 0u; i < VOS_TX_MAX_OBJECTS; ++i) {
        store->entries[i].occupied = 0u;
        zero_bytes(store->entries[i].addr.bytes, VOS_TX_DIGEST_BYTES);
        store->entries[i].obj.kid_count = 0u;
        store->entries[i].obj.payload_len = 0u;
        zero_bytes(store->entries[i].obj.payload, VOS_TX_MAX_PAYLOAD);
        for (uint32_t k = 0u; k < VOS_TX_MAX_KIDS; ++k) {
            zero_bytes(store->entries[i].obj.kids[k].bytes, VOS_TX_DIGEST_BYTES);
        }
    }
}

enum vos_tx_status vos_tx_hash_object(const struct vos_tx_object *obj,
                                      struct vos_tx_hash *out_addr)
{
    uint8_t buf[VOS_TX_OBJ_BUF_BYTES];
    size_t offset = 0u;

    if (obj == NULL || out_addr == NULL) {
        return VOS_TX_ERR_INVALID;
    }
    if (obj->payload_len > VOS_TX_MAX_PAYLOAD || obj->kid_count > VOS_TX_MAX_KIDS) {
        return VOS_TX_ERR_INVALID;
    }

    buf[0] = 'V';
    buf[1] = 'O';
    buf[2] = 'S';
    buf[3] = 'T';
    buf[4] = 'X';
    buf[5] = 'O';
    buf[6] = 'B';
    buf[7] = '1';
    put_le32(buf + 8u, obj->payload_len);
    put_le32(buf + 12u, obj->kid_count);
    offset = VOS_TX_OBJ_HEADER_BYTES;

    if (obj->payload_len > 0u) {
        copy_bytes(buf + offset, obj->payload, obj->payload_len);
        offset += obj->payload_len;
    }
    for (uint32_t i = 0u; i < obj->kid_count; ++i) {
        copy_bytes(buf + offset, obj->kids[i].bytes, VOS_TX_DIGEST_BYTES);
        offset += VOS_TX_DIGEST_BYTES;
    }

    if (vos_sha256(buf, offset, out_addr->bytes) != 1) {
        return VOS_TX_ERR_INVALID;
    }
    return VOS_TX_OK;
}

enum vos_tx_status vos_tx_store_put_at(struct vos_tx_store *store,
                                       const struct vos_tx_hash *addr,
                                       const struct vos_tx_object *obj)
{
    if (store == NULL || addr == NULL || obj == NULL) {
        return VOS_TX_ERR_INVALID;
    }
    if (obj->payload_len > VOS_TX_MAX_PAYLOAD || obj->kid_count > VOS_TX_MAX_KIDS) {
        return VOS_TX_ERR_INVALID;
    }

    for (uint32_t i = 0u; i < VOS_TX_MAX_OBJECTS; ++i) {
        if (store->entries[i].occupied != 0u &&
            equal_hashes(&store->entries[i].addr, addr)) {
            store->entries[i].obj = *obj;
            return VOS_TX_OK;
        }
    }
    for (uint32_t i = 0u; i < VOS_TX_MAX_OBJECTS; ++i) {
        if (store->entries[i].occupied == 0u) {
            store->entries[i].occupied = 1u;
            store->entries[i].addr = *addr;
            store->entries[i].obj = *obj;
            store->count += 1u;
            return VOS_TX_OK;
        }
    }
    return VOS_TX_ERR_STORE_FULL;
}

enum vos_tx_status vos_tx_store_put(struct vos_tx_store *store,
                                    const struct vos_tx_object *obj,
                                    struct vos_tx_hash *out_addr)
{
    struct vos_tx_hash addr;
    const enum vos_tx_status st = vos_tx_hash_object(obj, &addr);
    if (st != VOS_TX_OK) {
        return st;
    }
    const enum vos_tx_status put_st = vos_tx_store_put_at(store, &addr, obj);
    if (put_st == VOS_TX_OK && out_addr != NULL) {
        *out_addr = addr;
    }
    return put_st;
}

enum vos_tx_status vos_tx_store_remove(struct vos_tx_store *store,
                                       const struct vos_tx_hash *addr)
{
    if (store == NULL || addr == NULL) {
        return VOS_TX_ERR_INVALID;
    }
    for (uint32_t i = 0u; i < VOS_TX_MAX_OBJECTS; ++i) {
        if (store->entries[i].occupied != 0u &&
            equal_hashes(&store->entries[i].addr, addr)) {
            store->entries[i].occupied = 0u;
            zero_bytes(store->entries[i].addr.bytes, VOS_TX_DIGEST_BYTES);
            if (store->count > 0u) {
                store->count -= 1u;
            }
            return VOS_TX_OK;
        }
    }
    return VOS_TX_ERR_MISSING;
}

enum vos_tx_status vos_tx_sign_root(const struct vos_tx_policy *policy,
                                    struct vos_tx_signed_root *sr)
{
    uint8_t enc[VOS_TX_ROOT_ENC_BYTES];
    const struct vos_tx_enrolled_key *k = NULL;

    if (policy == NULL || sr == NULL) {
        return VOS_TX_ERR_INVALID;
    }
    k = find_enrolled_key(policy, sr->key_id);
    if (k == NULL) {
        return VOS_TX_ERR_UNVERIFIED;
    }
    encode_signed_root(sr, enc);
    if (vos_sha256(enc, sizeof(enc), sr->checksum) != 1) {
        return VOS_TX_ERR_INVALID;
    }
    if (vos_hmac_sha256(k->hmac_key, VOS_CRYPTO_KEY_BYTES_256,
                        enc, sizeof(enc), sr->sig) != 1) {
        return VOS_TX_ERR_INVALID;
    }
    return VOS_TX_OK;
}

int vos_tx_verify_root(const struct vos_tx_policy *policy,
                       const struct vos_tx_signed_root *sr)
{
    uint8_t enc[VOS_TX_ROOT_ENC_BYTES];
    uint8_t expected_sum[VOS_TX_DIGEST_BYTES];
    uint8_t expected_sig[VOS_TX_DIGEST_BYTES];
    const struct vos_tx_enrolled_key *k = NULL;

    if (policy == NULL || sr == NULL) {
        return 0;
    }
    k = find_enrolled_key(policy, sr->key_id);
    if (k == NULL) {
        return 0;
    }
    encode_signed_root(sr, enc);
    if (vos_sha256(enc, sizeof(enc), expected_sum) != 1) {
        return 0;
    }
    if (!equal_bytes_ct(expected_sum, sr->checksum, VOS_TX_DIGEST_BYTES)) {
        return 0;
    }
    if (vos_hmac_sha256(k->hmac_key, VOS_CRYPTO_KEY_BYTES_256,
                        enc, sizeof(enc), expected_sig) != 1) {
        return 0;
    }
    if (!equal_bytes_ct(expected_sig, sr->sig, VOS_TX_DIGEST_BYTES)) {
        return 0;
    }
    return 1;
}

enum vos_tx_status vos_tx_dag_intact(const struct vos_tx_store *store,
                                     const struct vos_tx_hash *root,
                                     uint32_t walk_depth)
{
    struct vos_tx_hash frontier[VOS_TX_MAX_OBJECTS];
    struct vos_tx_hash next_frontier[VOS_TX_MAX_OBJECTS];
    uint32_t frontier_count = 1u;

    if (store == NULL || root == NULL || walk_depth > VOS_TX_MAX_WALK_DEPTH) {
        return VOS_TX_ERR_INVALID;
    }

    frontier[0] = *root;
    for (uint32_t depth = 0u; depth <= walk_depth; ++depth) {
        uint32_t next_count = 0u;
        for (uint32_t i = 0u; i < frontier_count; ++i) {
            struct vos_tx_hash computed;
            const struct vos_tx_store_entry *entry = store_find(store, &frontier[i]);
            if (entry == NULL) {
                return VOS_TX_ERR_INCOMPLETE_DAG;
            }
            if (vos_tx_hash_object(&entry->obj, &computed) != VOS_TX_OK ||
                !equal_hashes(&computed, &frontier[i])) {
                return VOS_TX_ERR_INCOMPLETE_DAG;
            }
            if (depth == walk_depth) {
                if (entry->obj.kid_count != 0u) {
                    return VOS_TX_ERR_INCOMPLETE_DAG;
                }
            } else {
                for (uint32_t k = 0u; k < entry->obj.kid_count; ++k) {
                    if (!hash_in_list(next_frontier, next_count, &entry->obj.kids[k])) {
                        if (next_count >= VOS_TX_MAX_OBJECTS) {
                            return VOS_TX_ERR_INCOMPLETE_DAG;
                        }
                        next_frontier[next_count] = entry->obj.kids[k];
                        next_count += 1u;
                    }
                }
            }
        }
        if (next_count == 0u) {
            return VOS_TX_OK;
        }
        for (uint32_t i = 0u; i < next_count; ++i) {
            frontier[i] = next_frontier[i];
        }
        frontier_count = next_count;
    }
    return VOS_TX_OK;
}

void vos_tx_ab_init(struct vos_tx_ab *ab,
                    const struct vos_tx_signed_root *initial_live,
                    const struct vos_tx_signed_root *initial_spare,
                    uint64_t floor_version,
                    const struct vos_tx_hash *initial_checkpoint)
{
    if (ab == NULL || initial_live == NULL || initial_spare == NULL) {
        return;
    }
    ab->b_live = 0u;
    ab->slot_a = *initial_live;
    ab->slot_b = *initial_spare;
    ab->floor_version = floor_version;
    ab->staged = 0u;
    ab->admitted = 0u;
    ab->has_retained = 0u;
    zero_bytes((uint8_t *)&ab->retained_predecessor, sizeof(ab->retained_predecessor));
    if (initial_checkpoint != NULL) {
        ab->pinned_checkpoint = *initial_checkpoint;
    } else {
        zero_bytes(ab->pinned_checkpoint.bytes, VOS_TX_DIGEST_BYTES);
    }
}

const struct vos_tx_signed_root *vos_tx_ab_live(const struct vos_tx_ab *ab)
{
    if (ab == NULL) {
        return NULL;
    }
    return (ab->b_live != 0u) ? &ab->slot_b : &ab->slot_a;
}

const struct vos_tx_signed_root *vos_tx_ab_spare(const struct vos_tx_ab *ab)
{
    if (ab == NULL) {
        return NULL;
    }
    return (ab->b_live != 0u) ? &ab->slot_a : &ab->slot_b;
}

enum vos_tx_status vos_tx_path_read(const struct vos_tx_store *store,
                                    const struct vos_tx_hash *attested_root,
                                    const struct vos_tx_hash *target_addr,
                                    const struct vos_tx_path_witness *witness,
                                    uint32_t walk_depth,
                                    uint8_t *out_payload,
                                    size_t out_capacity,
                                    size_t *out_len)
{
    struct vos_tx_hash visited[VOS_TX_MAX_WALK_DEPTH + 1u];
    struct vos_tx_hash curr;

    if (store == NULL || attested_root == NULL || target_addr == NULL ||
        witness == NULL || out_len == NULL) {
        return VOS_TX_ERR_INVALID;
    }
    if (out_capacity > 0u && out_payload == NULL) {
        return VOS_TX_ERR_INVALID;
    }
    if (walk_depth > VOS_TX_MAX_WALK_DEPTH) {
        return VOS_TX_ERR_INVALID;
    }
    if (witness->step_count > walk_depth) {
        return VOS_TX_ERR_DEPTH;
    }

    curr = *attested_root;
    for (uint32_t step = 0u; step <= witness->step_count; ++step) {
        struct vos_tx_hash computed;
        const struct vos_tx_store_entry *entry = NULL;

        if (hash_in_list(visited, step, &curr)) {
            return VOS_TX_ERR_CYCLE;
        }
        visited[step] = curr;

        entry = store_find(store, &curr);
        if (entry == NULL) {
            return VOS_TX_ERR_MISSING;
        }
        if (vos_tx_hash_object(&entry->obj, &computed) != VOS_TX_OK) {
            return VOS_TX_ERR_INVALID;
        }
        if (!equal_hashes(&computed, &curr)) {
            return VOS_TX_ERR_HASH_MISMATCH;
        }

        if (step == witness->step_count) {
            if (!equal_hashes(&curr, target_addr)) {
                return VOS_TX_ERR_TARGET_MISMATCH;
            }
            if (entry->obj.payload_len > out_capacity) {
                return VOS_TX_ERR_BUFFER;
            }
            if (entry->obj.payload_len > 0u) {
                copy_bytes(out_payload, entry->obj.payload, entry->obj.payload_len);
            }
            *out_len = entry->obj.payload_len;
            return VOS_TX_OK;
        }

        if (!hash_in_list(entry->obj.kids, entry->obj.kid_count, &witness->steps[step])) {
            return VOS_TX_ERR_BAD_LINK;
        }
        curr = witness->steps[step];
    }
    return VOS_TX_ERR_DEPTH;
}

enum vos_tx_status vos_tx_select_root(const struct vos_tx_policy *policy,
                                      const struct vos_tx_signed_root *copies,
                                      size_t copy_count,
                                      uint32_t untrusted_slot_ptr,
                                      struct vos_tx_signed_root *out_selected)
{
    int have_best = 0;
    struct vos_tx_signed_root best;

    (void)untrusted_slot_ptr;

    if (policy == NULL || copies == NULL || out_selected == NULL) {
        return VOS_TX_ERR_INVALID;
    }
    if (copy_count < VOS_TX_COPIES_PER_SLOT || copy_count > VOS_TX_MAX_COPIES) {
        return VOS_TX_ERR_INVALID;
    }

    zero_bytes((uint8_t *)&best, sizeof(best));
    for (size_t i = 0u; i < copy_count; ++i) {
        if (vos_tx_verify_root(policy, &copies[i])) {
            if (!have_best || copies[i].version > best.version) {
                best = copies[i];
                have_best = 1;
            }
        }
    }
    if (!have_best) {
        return VOS_TX_ERR_UNVERIFIED;
    }
    *out_selected = best;
    return VOS_TX_OK;
}

enum vos_tx_status vos_tx_stage(struct vos_tx_ab *ab,
                                const struct vos_tx_signed_root *candidate)
{
    if (ab == NULL || candidate == NULL) {
        return VOS_TX_ERR_INVALID;
    }
    if (ab->b_live != 0u) {
        ab->slot_a = *candidate;
    } else {
        ab->slot_b = *candidate;
    }
    ab->staged = 1u;
    ab->admitted = 0u;
    ab->has_retained = 0u;
    zero_bytes((uint8_t *)&ab->retained_predecessor, sizeof(ab->retained_predecessor));
    return VOS_TX_OK;
}

enum vos_tx_status vos_tx_verify_and_flip(const struct vos_tx_policy *policy,
                                          const struct vos_tx_store *store,
                                          struct vos_tx_ab *ab,
                                          uint64_t rot_floor,
                                          const struct vos_tx_witness_evidence *evidence)
{
    const struct vos_tx_signed_root *spare = NULL;
    const struct vos_tx_signed_root *live = NULL;

    if (policy == NULL || store == NULL || ab == NULL || evidence == NULL) {
        return VOS_TX_ERR_INVALID;
    }
    if (ab->staged == 0u) {
        ab->admitted = 0u;
        return VOS_TX_ERR_NOT_STAGED;
    }

    spare = vos_tx_ab_spare(ab);
    live = vos_tx_ab_live(ab);

    if (!vos_tx_verify_root(policy, spare)) {
        ab->admitted = 0u;
        return VOS_TX_ERR_UNVERIFIED;
    }
    if (spare->version < rot_floor ||
        spare->version < ab->floor_version ||
        spare->version < spare->declared_floor) {
        ab->admitted = 0u;
        return VOS_TX_ERR_ROLLBACK_FLOOR;
    }
    if (evidence->proof_admitted != 1u ||
        !equal_hashes(&evidence->verdict_root, &spare->root)) {
        ab->admitted = 0u;
        return VOS_TX_ERR_NOT_ADMITTED;
    }
    if (evidence->checkpoint_accepted != 1u ||
        evidence->checkpoint_consistent != 1u ||
        evidence->base_included != 1u) {
        ab->admitted = 0u;
        return VOS_TX_ERR_WITNESS_PIN;
    }
    if (vos_tx_dag_intact(store, &spare->root, policy->walk_depth) != VOS_TX_OK) {
        ab->admitted = 0u;
        return VOS_TX_ERR_INCOMPLETE_DAG;
    }

    ab->admitted = 1u;
    ab->retained_predecessor = *live;
    ab->has_retained = 1u;
    ab->b_live = (ab->b_live != 0u) ? 0u : 1u;
    ab->staged = 0u;
    ab->admitted = 0u;
    ab->pinned_checkpoint = evidence->offered_checkpoint;
    return VOS_TX_OK;
}

enum vos_tx_status vos_tx_health_check(const struct vos_tx_policy *policy,
                                       const struct vos_tx_store *store,
                                       struct vos_tx_ab *ab,
                                       uint64_t rot_floor,
                                       uint32_t healthy,
                                       uint32_t predecessor_proof_admitted)
{
    const struct vos_tx_signed_root *spare = NULL;
    const struct vos_tx_signed_root *live = NULL;

    if (policy == NULL || store == NULL || ab == NULL) {
        return VOS_TX_ERR_INVALID;
    }
    if (healthy != 0u) {
        ab->staged = 0u;
        ab->admitted = 0u;
        return VOS_TX_OK;
    }

    if (ab->staged != 0u) {
        return VOS_TX_ERR_RESTAGED;
    }
    if (ab->has_retained == 0u) {
        return VOS_TX_ERR_NO_PREDECESSOR;
    }

    spare = vos_tx_ab_spare(ab);
    live = vos_tx_ab_live(ab);

    if (!signed_roots_equal(&ab->retained_predecessor, spare)) {
        return VOS_TX_ERR_PREDECESSOR_MISMATCH;
    }
    if (!vos_tx_verify_root(policy, spare)) {
        return VOS_TX_ERR_UNVERIFIED;
    }
    if (spare->version < rot_floor ||
        spare->version < ab->floor_version ||
        spare->version < spare->declared_floor) {
        return VOS_TX_ERR_ROLLBACK_FLOOR;
    }
    if (predecessor_proof_admitted != 1u) {
        return VOS_TX_ERR_NOT_ADMITTED;
    }
    if (vos_tx_dag_intact(store, &spare->root, policy->walk_depth) != VOS_TX_OK) {
        return VOS_TX_ERR_INCOMPLETE_DAG;
    }

    ab->retained_predecessor = *live;
    ab->has_retained = 1u;
    ab->b_live = (ab->b_live != 0u) ? 0u : 1u;
    ab->staged = 0u;
    ab->admitted = 0u;
    return VOS_TX_OK;
}
