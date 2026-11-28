// SPDX-License-Identifier: Apache-2.0
#include "vos_wasm_host.h"

#include <string.h>

static void zero_bytes(void *dst, size_t len)
{
    if (dst == NULL) {
        return;
    }
    volatile uint8_t *wipe = (volatile uint8_t *)dst;
    for (size_t i = 0u; i < len; ++i) {
        wipe[i] = 0u;
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

static int equal_hashes(const struct vos_whost_hash *a, const struct vos_whost_hash *b)
{
    return equal_bytes_ct(a->bytes, b->bytes, VOS_WHOST_DIGEST_BYTES);
}

static void put_le32(uint8_t *dst, uint32_t value)
{
    for (uint32_t i = 0u; i < 4u; ++i) {
        dst[i] = (uint8_t)(value >> (8u * i));
    }
}

static int is_power_of_two_u32(uint32_t v)
{
    return v != 0u && (v & (v - 1u)) == 0u;
}

static int grants_within(uint32_t requested, uint32_t allowed)
{
    return (requested & ~allowed) == 0u;
}

static int slot_accepts_prepare(uint32_t phase)
{
    return phase == VOS_WHOST_PHASE_FREE || phase == VOS_WHOST_PHASE_REUSABLE;
}

static int group_collision(const struct vos_whost_pool *pool, uint32_t slot_id)
{
    const uint32_t gid = pool->slots[slot_id].group_id;
    for (uint32_t i = 0u; i < VOS_WHOST_MAX_HOSTS; ++i) {
        if (i == slot_id) {
            continue;
        }
        const struct vos_whost_slot *other = &pool->slots[i];
        if (other->phase != VOS_WHOST_PHASE_FREE &&
            other->phase != VOS_WHOST_PHASE_REUSABLE &&
            other->group_id == gid) {
            return 1;
        }
    }
    return 0;
}

static enum vos_whost_status validate_bundle(const struct vos_whost_pool *pool,
                                             const struct vos_whost_bundle *bundle)
{
    if (bundle == NULL) {
        return VOS_WHOST_ERR_INVALID_ARG;
    }
    if (bundle->uses_fs_path_authority != 0u) {
        return VOS_WHOST_ERR_FS_PATH_AUTHORITY;
    }
    if (bundle->closure_valid == 0u ||
        bundle->module_len > VOS_WHOST_MAX_MODULE_BYTES ||
        bundle->assets_len > VOS_WHOST_MAX_ASSETS_BYTES) {
        return VOS_WHOST_ERR_FORGED_CLOSURE;
    }
    struct vos_whost_hash expected_cl;
    enum vos_whost_status st = vos_whost_compute_closure_digest(bundle, &expected_cl);
    if (st != VOS_WHOST_OK) {
        return st;
    }
    if (!equal_hashes(&expected_cl, &bundle->closure_digest)) {
        return VOS_WHOST_ERR_FORGED_CLOSURE;
    }
    if (bundle->descriptor_valid == 0u || bundle->core30_valid == 0u ||
        bundle->ui_label_len == 0u || bundle->ui_label_len > VOS_WHOST_MAX_LABEL_BYTES) {
        return VOS_WHOST_ERR_FORGED_DESCRIPTOR;
    }
    struct vos_whost_hash expected_bd;
    st = vos_whost_compute_bundle_digest(bundle, &expected_bd);
    if (st != VOS_WHOST_OK) {
        return st;
    }
    if (!equal_hashes(&expected_bd, &bundle->bundle_digest)) {
        return VOS_WHOST_ERR_FORGED_DESCRIPTOR;
    }
    if (bundle->abi_version != pool->policy.abi_version) {
        return VOS_WHOST_ERR_INCOMPATIBLE_ABI;
    }
    if (bundle->init_mem_pages > bundle->max_mem_pages ||
        bundle->max_mem_pages > pool->policy.mem_page_ceiling ||
        bundle->init_mem_pages > pool->avail_pages ||
        bundle->table_limit > pool->policy.table_ceiling ||
        bundle->stack_limit > pool->policy.stack_ceiling) {
        return VOS_WHOST_ERR_OVERSIZED_RESERVATION;
    }
    if (!grants_within(bundle->requested_imports_mask, pool->policy.import_ceiling_mask)) {
        return VOS_WHOST_ERR_OVER_SCOPED_GRANT;
    }
    return VOS_WHOST_OK;
}

static enum vos_whost_status check_consent(const struct vos_whost_bundle *bundle,
                                           const struct vos_whost_consent *consent)
{
    if (consent == NULL || consent->user_consented == 0u || consent->credential_ok == 0u) {
        return VOS_WHOST_ERR_NO_CONSENT;
    }
    if (!equal_hashes(&consent->trusted_digest, &bundle->bundle_digest)) {
        return VOS_WHOST_ERR_CONSENT_DIGEST_MISMATCH;
    }
    return VOS_WHOST_OK;
}

static enum vos_whost_status compute_ckpt_hmac(const struct vos_whost_pool *pool,
                                               const struct vos_whost_checkpoint *ckpt,
                                               uint8_t out_mac[VOS_WHOST_DIGEST_BYTES])
{
    uint8_t buf[88];
    memcpy(buf, "VOSWHCK1", 8u);
    memcpy(buf + 8u, ckpt->bundle_digest.bytes, VOS_WHOST_DIGEST_BYTES);
    put_le32(buf + 40u, ckpt->abi_version);
    put_le32(buf + 44u, ckpt->profile_id);
    put_le32(buf + 48u, ckpt->schema_id);
    put_le32(buf + 52u, ckpt->generation);
    memcpy(buf + 56u, ckpt->durable_digest.bytes, VOS_WHOST_DIGEST_BYTES);
    const int ok = vos_hmac_sha256(pool->ckpt_auth_key, VOS_WHOST_KEY_BYTES,
                                   buf, sizeof(buf), out_mac);
    zero_bytes(buf, sizeof(buf));
    return ok ? VOS_WHOST_OK : VOS_WHOST_ERR_CRYPTO;
}

enum vos_whost_status vos_whost_pool_init(struct vos_whost_pool *pool,
                                          const struct vos_whost_policy *policy,
                                          const uint8_t ckpt_auth_key[VOS_WHOST_KEY_BYTES],
                                          uint32_t total_pages)
{
    if (pool == NULL || policy == NULL || ckpt_auth_key == NULL ||
        total_pages == 0u || policy->max_epoch == 0u) {
        return VOS_WHOST_ERR_INVALID_ARG;
    }
    memset(pool, 0, sizeof(*pool));
    pool->policy = *policy;
    memcpy(pool->ckpt_auth_key, ckpt_auth_key, VOS_WHOST_KEY_BYTES);
    pool->avail_pages = total_pages;
    pool->total_pages = total_pages;
    pool->staging_avail = 1u;
    pool->next_act_id = 100u;

    for (uint32_t i = 0u; i < VOS_WHOST_MAX_HOSTS; ++i) {
        pool->slots[i].slot_id = i;
        pool->slots[i].group_id = 7000u + i;
        pool->slots[i].phase = VOS_WHOST_PHASE_FREE;
        pool->slots[i].exec_stopped = 1u;
        pool->slots[i].ingress_stopped = 1u;
        pool->slots[i].sweep_done = 1u;
        pool->slots[i].zeroized = 1u;
    }
    return VOS_WHOST_OK;
}

enum vos_whost_status vos_whost_compute_closure_digest(const struct vos_whost_bundle *bundle,
                                                       struct vos_whost_hash *out_digest)
{
    if (bundle == NULL || out_digest == NULL ||
        bundle->module_len > VOS_WHOST_MAX_MODULE_BYTES ||
        bundle->assets_len > VOS_WHOST_MAX_ASSETS_BYTES) {
        return VOS_WHOST_ERR_INVALID_ARG;
    }
    uint8_t buf[16u + VOS_WHOST_MAX_MODULE_BYTES + VOS_WHOST_MAX_ASSETS_BYTES];
    memcpy(buf, "VOSWHCL1", 8u);
    put_le32(buf + 8u, bundle->module_len);
    size_t off = 12u;
    if (bundle->module_len > 0u) {
        memcpy(buf + off, bundle->module_bytes, bundle->module_len);
        off += bundle->module_len;
    }
    put_le32(buf + off, bundle->assets_len);
    off += 4u;
    if (bundle->assets_len > 0u) {
        memcpy(buf + off, bundle->assets_bytes, bundle->assets_len);
        off += bundle->assets_len;
    }
    const int ok = vos_sha256(buf, off, out_digest->bytes);
    zero_bytes(buf, off);
    return ok ? VOS_WHOST_OK : VOS_WHOST_ERR_CRYPTO;
}

enum vos_whost_status vos_whost_compute_bundle_digest(const struct vos_whost_bundle *bundle,
                                                      struct vos_whost_hash *out_digest)
{
    if (bundle == NULL || out_digest == NULL) {
        return VOS_WHOST_ERR_INVALID_ARG;
    }
    uint8_t buf[68];
    memcpy(buf, "VOSWHBD1", 8u);
    memcpy(buf + 8u, bundle->closure_digest.bytes, VOS_WHOST_DIGEST_BYTES);
    put_le32(buf + 40u, bundle->abi_version);
    put_le32(buf + 44u, bundle->init_mem_pages);
    put_le32(buf + 48u, bundle->max_mem_pages);
    put_le32(buf + 52u, bundle->table_limit);
    put_le32(buf + 56u, bundle->stack_limit);
    put_le32(buf + 60u, bundle->schema_id);
    put_le32(buf + 64u, bundle->requested_imports_mask);
    const int ok = vos_sha256(buf, sizeof(buf), out_digest->bytes);
    zero_bytes(buf, sizeof(buf));
    return ok ? VOS_WHOST_OK : VOS_WHOST_ERR_CRYPTO;
}

enum vos_whost_status vos_whost_seal_checkpoint(const struct vos_whost_pool *pool,
                                                struct vos_whost_checkpoint *ckpt)
{
    if (pool == NULL || ckpt == NULL) {
        return VOS_WHOST_ERR_INVALID_ARG;
    }
    return compute_ckpt_hmac(pool, ckpt, ckpt->hmac);
}

enum vos_whost_status vos_whost_prepare(struct vos_whost_pool *pool,
                                        uint32_t slot_id,
                                        const struct vos_whost_bundle *bundle)
{
    if (pool == NULL || slot_id >= VOS_WHOST_MAX_HOSTS || bundle == NULL) {
        return VOS_WHOST_ERR_INVALID_ARG;
    }
    struct vos_whost_slot *slot = &pool->slots[slot_id];
    if (!slot_accepts_prepare(slot->phase)) {
        return VOS_WHOST_ERR_BAD_PHASE;
    }
    if (pool->staging_avail == 0u) {
        return VOS_WHOST_ERR_NO_STAGING;
    }
    const enum vos_whost_status st = validate_bundle(pool, bundle);
    if (st != VOS_WHOST_OK) {
        return st;
    }

    slot->phase = VOS_WHOST_PHASE_PREPARED;
    slot->has_prepared = 1u;
    slot->prepared = *bundle;
    slot->has_active_bundle = 0u;
    zero_bytes(&slot->active_bundle, sizeof(slot->active_bundle));
    slot->active_grants_mask = 0u;
    slot->session_key = 0u;
    slot->tagged_mem = 0u;
    slot->start_executed = 0u;
    slot->new_grants_spent = 0u;
    slot->exec_stopped = 1u;
    slot->ingress_stopped = 1u;
    slot->pending_imports = 0u;
    return VOS_WHOST_OK;
}

enum vos_whost_status vos_whost_launch(struct vos_whost_pool *pool,
                                       uint32_t slot_id,
                                       const struct vos_whost_consent *consent,
                                       uint32_t initial_grants_mask,
                                       uint32_t uses_fs_path_authority,
                                       uint64_t new_session_key)
{
    if (pool == NULL || slot_id >= VOS_WHOST_MAX_HOSTS) {
        return VOS_WHOST_ERR_INVALID_ARG;
    }
    if (uses_fs_path_authority != 0u) {
        return VOS_WHOST_ERR_FS_PATH_AUTHORITY;
    }
    struct vos_whost_slot *slot = &pool->slots[slot_id];
    if (slot->phase != VOS_WHOST_PHASE_PREPARED || slot->has_prepared == 0u) {
        return VOS_WHOST_ERR_BAD_PHASE;
    }
    if (slot->epoch_retired != 0u || slot->epoch >= pool->policy.max_epoch) {
        slot->epoch_retired = 1u;
        return VOS_WHOST_ERR_EPOCH_EXHAUSTED;
    }
    if (group_collision(pool, slot_id)) {
        return VOS_WHOST_ERR_GROUP_COLLISION;
    }

    const struct vos_whost_bundle *bd = &slot->prepared;
    const enum vos_whost_status cst = check_consent(bd, consent);
    if (cst != VOS_WHOST_OK) {
        return cst;
    }
    if (!grants_within(initial_grants_mask, bd->requested_imports_mask) ||
        !grants_within(initial_grants_mask, pool->policy.import_ceiling_mask)) {
        return VOS_WHOST_ERR_OVER_SCOPED_GRANT;
    }
    if (bd->init_mem_pages > pool->avail_pages) {
        return VOS_WHOST_ERR_NO_CAPACITY;
    }

    pool->avail_pages -= bd->init_mem_pages;
    slot->phase = VOS_WHOST_PHASE_ACTIVE;
    slot->act_id = pool->next_act_id;
    pool->next_act_id += 1u;
    slot->epoch += 1u;
    slot->has_active_bundle = 1u;
    slot->active_bundle = *bd;
    slot->has_prepared = 0u;
    zero_bytes(&slot->prepared, sizeof(slot->prepared));
    slot->active_grants_mask = initial_grants_mask;
    slot->session_key = new_session_key;
    slot->tagged_mem = 0u;
    slot->start_executed = slot->active_bundle.has_start_fn;
    slot->new_grants_spent = 1u;
    slot->exec_stopped = 0u;
    slot->ingress_stopped = 0u;
    slot->pending_imports = 0u;
    slot->sweep_done = 0u;
    slot->zeroized = 0u;
    memset(slot->arena_canary, (int)(0xA0u + (slot->epoch & 0x1Fu)), sizeof(slot->arena_canary));
    return VOS_WHOST_OK;
}

enum vos_whost_status vos_whost_invoke_import(const struct vos_whost_pool *pool,
                                              uint32_t slot_id,
                                              const struct vos_whost_import_call *call,
                                              uint32_t *out_reply_epoch)
{
    if (pool == NULL || slot_id >= VOS_WHOST_MAX_HOSTS || call == NULL || out_reply_epoch == NULL) {
        return VOS_WHOST_ERR_INVALID_ARG;
    }
    const struct vos_whost_slot *slot = &pool->slots[slot_id];
    if (slot->phase != VOS_WHOST_PHASE_ACTIVE ||
        slot->exec_stopped != 0u ||
        slot->ingress_stopped != 0u) {
        return VOS_WHOST_ERR_BAD_PHASE;
    }
    if (call->handle.act_id != slot->act_id ||
        call->handle.epoch != slot->epoch ||
        call->handle.group_id != slot->group_id ||
        call->handle.scope_ok == 0u) {
        return VOS_WHOST_ERR_HANDLE_SCOPE;
    }
    if (!is_power_of_two_u32(call->handle.import_bit) ||
        !grants_within(call->handle.import_bit, slot->active_grants_mask)) {
        return VOS_WHOST_ERR_OVER_SCOPED_GRANT;
    }
    if (call->exports_pool_cap != 0u) {
        return VOS_WHOST_ERR_POOL_CAP_EXPORT;
    }
    if (call->tagged_transport != 0u) {
        return VOS_WHOST_ERR_TAGGED_TRANSPORT;
    }
    if (call->reply_epoch != slot->epoch) {
        return VOS_WHOST_ERR_EPOCH_MISMATCH;
    }
    if (call->yield_bounded == 0u) {
        return VOS_WHOST_ERR_YIELD_BOUND;
    }
    *out_reply_epoch = slot->epoch;
    return VOS_WHOST_OK;
}

enum vos_whost_status vos_whost_replace(struct vos_whost_pool *pool,
                                        uint32_t slot_id,
                                        const struct vos_whost_replace_req *req,
                                        uint64_t new_session_key)
{
    if (pool == NULL || slot_id >= VOS_WHOST_MAX_HOSTS || req == NULL) {
        return VOS_WHOST_ERR_INVALID_ARG;
    }
    struct vos_whost_slot *slot = &pool->slots[slot_id];
    if (slot->phase != VOS_WHOST_PHASE_ACTIVE || slot->has_active_bundle == 0u) {
        return VOS_WHOST_ERR_BAD_PHASE;
    }
    if (req->uses_fs_path_authority != 0u) {
        return VOS_WHOST_ERR_FS_PATH_AUTHORITY;
    }
    if (req->transition_reserved == 0u) {
        return VOS_WHOST_ERR_NO_CAPACITY;
    }
    if (req->durable_policy_ok == 0u) {
        return VOS_WHOST_ERR_COMMIT_UNAUTHORIZED;
    }
    const enum vos_whost_status vst = validate_bundle(pool, &req->candidate);
    if (vst != VOS_WHOST_OK) {
        return vst;
    }
    if (slot->epoch_retired != 0u || slot->epoch >= pool->policy.max_epoch) {
        return VOS_WHOST_ERR_EPOCH_EXHAUSTED;
    }
    const enum vos_whost_status cst = check_consent(&req->candidate, req->consent);
    if (cst != VOS_WHOST_OK) {
        return cst;
    }
    if (!grants_within(req->new_grants_mask, req->candidate.requested_imports_mask) ||
        !grants_within(req->new_grants_mask, pool->policy.import_ceiling_mask)) {
        return VOS_WHOST_ERR_OVER_SCOPED_GRANT;
    }
    if (req->commit_authorized == 0u) {
        return VOS_WHOST_ERR_COMMIT_UNAUTHORIZED;
    }

    const uint32_t old_pages = slot->active_bundle.init_mem_pages;
    if (pool->avail_pages + old_pages < req->candidate.init_mem_pages) {
        return VOS_WHOST_ERR_NO_CAPACITY;
    }

    /* Commit point: retire old binding and record acknowledged durable state for candidate. */
    struct vos_whost_durable acked;
    acked.valid = 1u;
    acked.acked = 1u;
    acked.bundle_digest = req->candidate.bundle_digest;
    acked.schema_id = req->candidate.schema_id;
    acked.state_digest = req->acked_durable_digest;

    zero_bytes(slot->arena_canary, sizeof(slot->arena_canary));
    slot->session_key = 0u;
    slot->active_grants_mask = 0u;
    slot->tagged_mem = 0u;
    slot->pending_imports = 0u;
    pool->avail_pages += old_pages;

    slot->act_id = pool->next_act_id;
    pool->next_act_id += 1u;
    slot->epoch += 1u;
    slot->durable = acked;

    if (req->post_commit_ok != 0u) {
        pool->avail_pages -= req->candidate.init_mem_pages;
        slot->phase = VOS_WHOST_PHASE_ACTIVE;
        slot->has_active_bundle = 1u;
        slot->active_bundle = req->candidate;
        slot->active_grants_mask = req->new_grants_mask;
        slot->session_key = new_session_key;
        slot->start_executed = req->candidate.has_start_fn;
        slot->new_grants_spent = 1u;
        slot->exec_stopped = 0u;
        slot->ingress_stopped = 0u;
        slot->sweep_done = 0u;
        slot->zeroized = 0u;
        memset(slot->arena_canary, (int)(0xB0u + (slot->epoch & 0x1Fu)), sizeof(slot->arena_canary));
        return VOS_WHOST_OK;
    }

    /* Post-commit failure: close cleanly with acknowledged durable work, no rollback. */
    slot->phase = VOS_WHOST_PHASE_SANITIZED;
    slot->has_active_bundle = 0u;
    zero_bytes(&slot->active_bundle, sizeof(slot->active_bundle));
    slot->active_grants_mask = 0u;
    slot->session_key = 0u;
    slot->tagged_mem = 0u;
    slot->start_executed = 0u;
    slot->new_grants_spent = 0u;
    slot->exec_stopped = 1u;
    slot->ingress_stopped = 1u;
    slot->sweep_done = 1u;
    slot->zeroized = 1u;
    return VOS_WHOST_ERR_POST_COMMIT_CLOSED;
}

enum vos_whost_status vos_whost_cancel_begin(struct vos_whost_pool *pool,
                                             uint32_t slot_id)
{
    if (pool == NULL || slot_id >= VOS_WHOST_MAX_HOSTS) {
        return VOS_WHOST_ERR_INVALID_ARG;
    }
    struct vos_whost_slot *slot = &pool->slots[slot_id];
    if (slot->phase != VOS_WHOST_PHASE_ACTIVE) {
        return VOS_WHOST_ERR_BAD_PHASE;
    }
    slot->phase = VOS_WHOST_PHASE_CANCELLING;
    slot->exec_stopped = 1u;
    slot->ingress_stopped = 1u;
    slot->sweep_done = 0u;
    slot->zeroized = 0u;
    return VOS_WHOST_OK;
}

enum vos_whost_status vos_whost_drain_imports(struct vos_whost_pool *pool,
                                              uint32_t slot_id)
{
    if (pool == NULL || slot_id >= VOS_WHOST_MAX_HOSTS) {
        return VOS_WHOST_ERR_INVALID_ARG;
    }
    struct vos_whost_slot *slot = &pool->slots[slot_id];
    if (slot->phase != VOS_WHOST_PHASE_CANCELLING) {
        return VOS_WHOST_ERR_BAD_PHASE;
    }
    slot->pending_imports = 0u;
    return VOS_WHOST_OK;
}

enum vos_whost_status vos_whost_enter_sweeping(struct vos_whost_pool *pool,
                                               uint32_t slot_id)
{
    if (pool == NULL || slot_id >= VOS_WHOST_MAX_HOSTS) {
        return VOS_WHOST_ERR_INVALID_ARG;
    }
    struct vos_whost_slot *slot = &pool->slots[slot_id];
    if (slot->phase != VOS_WHOST_PHASE_CANCELLING ||
        slot->exec_stopped == 0u ||
        slot->ingress_stopped == 0u) {
        return VOS_WHOST_ERR_BAD_PHASE;
    }
    if (slot->pending_imports != 0u) {
        return VOS_WHOST_ERR_PENDING_IMPORTS;
    }
    slot->phase = VOS_WHOST_PHASE_SWEEPING;
    return VOS_WHOST_OK;
}

enum vos_whost_status vos_whost_sweep_and_zeroize(struct vos_whost_pool *pool,
                                                  uint32_t slot_id)
{
    if (pool == NULL || slot_id >= VOS_WHOST_MAX_HOSTS) {
        return VOS_WHOST_ERR_INVALID_ARG;
    }
    struct vos_whost_slot *slot = &pool->slots[slot_id];
    if (slot->phase != VOS_WHOST_PHASE_SWEEPING) {
        return VOS_WHOST_ERR_BAD_PHASE;
    }
    if (slot->has_active_bundle != 0u) {
        pool->avail_pages += slot->active_bundle.init_mem_pages;
    }
    zero_bytes(&slot->prepared, sizeof(slot->prepared));
    zero_bytes(&slot->active_bundle, sizeof(slot->active_bundle));
    zero_bytes(slot->arena_canary, sizeof(slot->arena_canary));
    slot->has_prepared = 0u;
    slot->has_active_bundle = 0u;
    slot->active_grants_mask = 0u;
    slot->session_key = 0u;
    slot->tagged_mem = 0u;
    slot->start_executed = 0u;
    slot->new_grants_spent = 0u;
    slot->exec_stopped = 1u;
    slot->ingress_stopped = 1u;
    slot->pending_imports = 0u;
    slot->sweep_done = 1u;
    slot->zeroized = 1u;
    slot->phase = VOS_WHOST_PHASE_SANITIZED;
    return VOS_WHOST_OK;
}

enum vos_whost_status vos_whost_complete_reuse(struct vos_whost_pool *pool,
                                               uint32_t slot_id)
{
    if (pool == NULL || slot_id >= VOS_WHOST_MAX_HOSTS) {
        return VOS_WHOST_ERR_INVALID_ARG;
    }
    struct vos_whost_slot *slot = &pool->slots[slot_id];
    if (slot->phase != VOS_WHOST_PHASE_SANITIZED ||
        slot->sweep_done == 0u ||
        slot->zeroized == 0u) {
        return VOS_WHOST_ERR_NOT_SANITIZED;
    }
    if (slot->pending_imports != 0u) {
        return VOS_WHOST_ERR_PENDING_IMPORTS;
    }
    slot->phase = VOS_WHOST_PHASE_REUSABLE;
    return VOS_WHOST_OK;
}

enum vos_whost_status vos_whost_restore(struct vos_whost_pool *pool,
                                        uint32_t slot_id,
                                        const struct vos_whost_bundle *bundle,
                                        const struct vos_whost_checkpoint *ckpt,
                                        uint32_t current_grants_mask,
                                        uint64_t new_session_key)
{
    if (pool == NULL || slot_id >= VOS_WHOST_MAX_HOSTS ||
        bundle == NULL || ckpt == NULL) {
        return VOS_WHOST_ERR_INVALID_ARG;
    }
    struct vos_whost_slot *slot = &pool->slots[slot_id];
    if (!slot_accepts_prepare(slot->phase)) {
        return VOS_WHOST_ERR_BAD_PHASE;
    }

    uint8_t expected_hmac[VOS_WHOST_DIGEST_BYTES];
    enum vos_whost_status st = compute_ckpt_hmac(pool, ckpt, expected_hmac);
    if (st != VOS_WHOST_OK) {
        return st;
    }
    const int auth_ok = equal_bytes_ct(expected_hmac, ckpt->hmac, VOS_WHOST_DIGEST_BYTES);
    zero_bytes(expected_hmac, sizeof(expected_hmac));
    if (!auth_ok) {
        return VOS_WHOST_ERR_UNAUTH_CHECKPOINT;
    }

    st = validate_bundle(pool, bundle);
    if (st != VOS_WHOST_OK) {
        return st;
    }
    if (!equal_hashes(&ckpt->bundle_digest, &bundle->bundle_digest)) {
        return VOS_WHOST_ERR_FORGED_DESCRIPTOR;
    }
    if (ckpt->abi_version != pool->policy.abi_version) {
        return VOS_WHOST_ERR_INCOMPATIBLE_ABI;
    }
    if (ckpt->profile_id != pool->policy.profile_id ||
        ckpt->generation != pool->policy.generation) {
        return VOS_WHOST_ERR_INCOMPATIBLE_GEN;
    }
    if (ckpt->schema_id != bundle->schema_id) {
        return VOS_WHOST_ERR_STALE_SCHEMA;
    }
    if (slot->epoch_retired != 0u || slot->epoch >= pool->policy.max_epoch) {
        slot->epoch_retired = 1u;
        return VOS_WHOST_ERR_EPOCH_EXHAUSTED;
    }
    if (group_collision(pool, slot_id)) {
        return VOS_WHOST_ERR_GROUP_COLLISION;
    }
    if (!grants_within(current_grants_mask, bundle->requested_imports_mask) ||
        !grants_within(current_grants_mask, pool->policy.import_ceiling_mask)) {
        return VOS_WHOST_ERR_OVER_SCOPED_GRANT;
    }
    if (bundle->init_mem_pages > pool->avail_pages) {
        return VOS_WHOST_ERR_NO_CAPACITY;
    }

    pool->avail_pages -= bundle->init_mem_pages;
    slot->phase = VOS_WHOST_PHASE_ACTIVE;
    slot->act_id = pool->next_act_id;
    pool->next_act_id += 1u;
    slot->epoch += 1u;
    slot->has_prepared = 0u;
    zero_bytes(&slot->prepared, sizeof(slot->prepared));
    slot->has_active_bundle = 1u;
    slot->active_bundle = *bundle;
    /* Current grants and fresh session key only; never resurrect embedded old grants/keys/tags. */
    slot->active_grants_mask = current_grants_mask;
    slot->session_key = new_session_key;
    slot->tagged_mem = 0u;
    slot->start_executed = bundle->has_start_fn;
    slot->new_grants_spent = 1u;
    slot->exec_stopped = 0u;
    slot->ingress_stopped = 0u;
    slot->pending_imports = 0u;
    slot->sweep_done = 0u;
    slot->zeroized = 0u;
    slot->durable.valid = 1u;
    slot->durable.acked = 1u;
    slot->durable.bundle_digest = bundle->bundle_digest;
    slot->durable.schema_id = ckpt->schema_id;
    slot->durable.state_digest = ckpt->durable_digest;
    memset(slot->arena_canary, (int)(0xC0u + (slot->epoch & 0x1Fu)), sizeof(slot->arena_canary));
    return VOS_WHOST_OK;
}
