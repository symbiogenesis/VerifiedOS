// SPDX-License-Identifier: Apache-2.0
#include "vos_device_gen.h"

#include <string.h>

static void zero_bytes(uint8_t *dst, size_t len)
{
    if (dst == NULL) {
        return;
    }
    volatile uint8_t *wipe = dst;
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

static int equal_hashes(const struct vos_dgen_hash *a, const struct vos_dgen_hash *b)
{
    return equal_bytes_ct(a->bytes, b->bytes, VOS_DGEN_DIGEST_BYTES);
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

static void put_context(uint8_t *dst, const struct vos_dgen_context *ctx)
{
    put_le64(dst + 0u, ctx->spec_version);
    put_le64(dst + 8u, ctx->model_version);
    put_le64(dst + 16u, ctx->checker_id);
    put_le64(dst + 24u, ctx->tier);
    put_le64(dst + 32u, ctx->policy_epoch);
    put_le64(dst + 40u, ctx->resource_epoch);
}

static int context_equal(const struct vos_dgen_context *a,
                         const struct vos_dgen_context *b)
{
    return a->spec_version == b->spec_version &&
           a->model_version == b->model_version &&
           a->checker_id == b->checker_id &&
           a->tier == b->tier &&
           a->policy_epoch == b->policy_epoch &&
           a->resource_epoch == b->resource_epoch;
}

static int nonce_already_used(const struct vos_dgen_crypto_core *core, uint64_t nonce)
{
    for (uint32_t i = 0u; i < core->used_nonce_count; ++i) {
        if (core->used_nonces[i] == nonce) {
            return 1;
        }
    }
    return 0;
}

static enum vos_dgen_status compute_mint_mac(const struct vos_dgen_crypto_core *core,
                                             const struct vos_dgen_hash *roster_hash,
                                             const struct vos_dgen_hash *gen_root,
                                             uint64_t nonce,
                                             uint8_t out_mac[VOS_DGEN_DIGEST_BYTES])
{
    uint8_t msg[88];
    memcpy(msg, "VOSDGENM", 8u);
    put_le64(msg + 8u, core->key_id);
    memcpy(msg + 16u, roster_hash->bytes, VOS_DGEN_DIGEST_BYTES);
    memcpy(msg + 48u, gen_root->bytes, VOS_DGEN_DIGEST_BYTES);
    put_le64(msg + 80u, nonce);
    const int ok = vos_hmac_sha256(core->signing_key, VOS_DGEN_KEY_BYTES,
                                   msg, sizeof(msg), out_mac);
    zero_bytes(msg, sizeof(msg));
    return ok ? VOS_DGEN_OK : VOS_DGEN_ERR_CRYPTO;
}

static enum vos_dgen_status compute_checked_set_mac(const struct vos_dgen_crypto_core *core,
                                                    const struct vos_dgen_checked_set *set,
                                                    uint8_t out_mac[VOS_DGEN_DIGEST_BYTES])
{
    if (core == NULL || set == NULL || out_mac == NULL ||
        set->entry_count > VOS_DGEN_MAX_CHECKED) {
        return VOS_DGEN_ERR_INVALID_ARG;
    }
    uint8_t buf[12u + VOS_DGEN_MAX_CHECKED * 184u];
    memcpy(buf, "VOSDGENC", 8u);
    put_le32(buf + 8u, set->entry_count);
    size_t off = 12u;
    for (uint32_t i = 0u; i < set->entry_count; ++i) {
        const struct vos_dgen_checked_entry *e = &set->entries[i];
        put_le64(buf + off, e->pkg_id);
        off += 8u;
        memcpy(buf + off, e->artifact_digest.bytes, VOS_DGEN_DIGEST_BYTES);
        off += VOS_DGEN_DIGEST_BYTES;
        memcpy(buf + off, e->source_digest.bytes, VOS_DGEN_DIGEST_BYTES);
        off += VOS_DGEN_DIGEST_BYTES;
        memcpy(buf + off, e->contract_digest.bytes, VOS_DGEN_DIGEST_BYTES);
        off += VOS_DGEN_DIGEST_BYTES;
        memcpy(buf + off, e->proof_digest.bytes, VOS_DGEN_DIGEST_BYTES);
        off += VOS_DGEN_DIGEST_BYTES;
        put_context(buf + off, &e->context);
        off += 48u;
    }
    const int ok = vos_hmac_sha256(core->checked_set_key, VOS_DGEN_KEY_BYTES,
                                   buf, off, out_mac);
    zero_bytes(buf, off);
    return ok ? VOS_DGEN_OK : VOS_DGEN_ERR_CRYPTO;
}

static int find_reusable_entry(const struct vos_dgen_checked_set *set,
                               const struct vos_dgen_package *pkg,
                               const struct vos_dgen_hash *artifact_digest,
                               const struct vos_dgen_context *ctx)
{
    for (uint32_t i = 0u; i < set->entry_count; ++i) {
        const struct vos_dgen_checked_entry *e = &set->entries[i];
        if (e->pkg_id == pkg->pkg_id &&
            equal_hashes(&e->artifact_digest, artifact_digest) &&
            equal_hashes(&e->source_digest, &pkg->source_digest) &&
            equal_hashes(&e->contract_digest, &pkg->contract_digest) &&
            equal_hashes(&e->proof_digest, &pkg->proof_digest) &&
            context_equal(&e->context, ctx)) {
            return 1;
        }
    }
    return 0;
}

enum vos_dgen_status vos_dgen_device_init(struct vos_dgen_device *dev,
                                          uint64_t key_id,
                                          const uint8_t signing_key[VOS_DGEN_KEY_BYTES],
                                          const uint8_t checked_set_key[VOS_DGEN_KEY_BYTES],
                                          const struct vos_dgen_context *ctx,
                                          const struct vos_dgen_hash *initial_root,
                                          uint64_t initial_version,
                                          uint64_t floor,
                                          uint32_t step_budget,
                                          uint32_t workset_budget)
{
    if (dev == NULL || signing_key == NULL || checked_set_key == NULL ||
        ctx == NULL || initial_root == NULL || key_id == 0u ||
        initial_version < floor || step_budget == 0u || workset_budget == 0u) {
        return VOS_DGEN_ERR_INVALID_ARG;
    }
    memset(dev, 0, sizeof(*dev));
    dev->core.key_id = key_id;
    dev->core.enrolled = 1u;
    dev->core.exportable = 0u;
    memcpy(dev->core.signing_key, signing_key, VOS_DGEN_KEY_BYTES);
    memcpy(dev->core.checked_set_key, checked_set_key, VOS_DGEN_KEY_BYTES);

    dev->composer.composer_id = 1u;
    dev->composer.holds_signing_key = 0u;
    dev->composer.holds_mint_cap = 0u;

    dev->mode_guard.mode = VOS_DGEN_MODE_NORMAL;
    dev->mode_guard.priv_active = 0u;
    dev->mode_guard.switches = 0u;

    dev->context = *ctx;
    dev->pinned_checkpoint_id = 1u;
    dev->step_budget = step_budget;
    dev->workset_budget = workset_budget;

    dev->ab.live_is_b = 0u;
    dev->ab.floor = floor;
    dev->ab.slot_a.valid = 1u;
    dev->ab.slot_a.root = *initial_root;
    dev->ab.slot_a.version = initial_version;
    dev->ab.slot_a.declared_floor = floor;

    return vos_dgen_checked_set_seal(&dev->core, &dev->checked_set);
}

enum vos_dgen_status vos_dgen_compute_artifact_digest(const struct vos_dgen_package *pkg,
                                                      const struct vos_dgen_context *ctx,
                                                      struct vos_dgen_hash *out_digest)
{
    if (pkg == NULL || ctx == NULL || out_digest == NULL) {
        return VOS_DGEN_ERR_INVALID_ARG;
    }
    uint8_t buf[228];
    memcpy(buf, "VOSDGENP", 8u);
    put_le64(buf + 8u, pkg->pkg_id);
    put_le32(buf + 16u, pkg->is_base_image);
    memcpy(buf + 20u, pkg->source_digest.bytes, VOS_DGEN_DIGEST_BYTES);
    memcpy(buf + 52u, pkg->contract_digest.bytes, VOS_DGEN_DIGEST_BYTES);
    memcpy(buf + 84u, pkg->code_digest.bytes, VOS_DGEN_DIGEST_BYTES);
    memcpy(buf + 116u, pkg->init_digest.bytes, VOS_DGEN_DIGEST_BYTES);
    memcpy(buf + 148u, pkg->proof_digest.bytes, VOS_DGEN_DIGEST_BYTES);
    put_context(buf + 180u, ctx);
    const int ok = vos_sha256(buf, sizeof(buf), out_digest->bytes);
    zero_bytes(buf, sizeof(buf));
    return ok ? VOS_DGEN_OK : VOS_DGEN_ERR_CRYPTO;
}

enum vos_dgen_status vos_dgen_compute_roster_hash(const struct vos_dgen_package *pkgs,
                                                  uint32_t package_count,
                                                  const struct vos_dgen_context *ctx,
                                                  struct vos_dgen_hash *out_hash)
{
    if (pkgs == NULL || ctx == NULL || out_hash == NULL ||
        package_count == 0u || package_count > VOS_DGEN_MAX_PACKAGES) {
        return VOS_DGEN_ERR_INVALID_ARG;
    }
    uint8_t buf[12u + VOS_DGEN_MAX_PACKAGES * 40u];
    memcpy(buf, "VOSDGENR", 8u);
    put_le32(buf + 8u, package_count);
    size_t off = 12u;
    for (uint32_t i = 0u; i < package_count; ++i) {
        struct vos_dgen_hash art;
        const enum vos_dgen_status st = vos_dgen_compute_artifact_digest(&pkgs[i], ctx, &art);
        if (st != VOS_DGEN_OK) {
            return st;
        }
        put_le64(buf + off, pkgs[i].pkg_id);
        off += 8u;
        memcpy(buf + off, art.bytes, VOS_DGEN_DIGEST_BYTES);
        off += VOS_DGEN_DIGEST_BYTES;
    }
    const int ok = vos_sha256(buf, off, out_hash->bytes);
    zero_bytes(buf, off);
    return ok ? VOS_DGEN_OK : VOS_DGEN_ERR_CRYPTO;
}

enum vos_dgen_status vos_dgen_compute_gen_root(uint64_t version,
                                               uint64_t declared_floor,
                                               const struct vos_dgen_hash *roster_hash,
                                               const struct vos_dgen_context *ctx,
                                               struct vos_dgen_hash *out_root)
{
    if (roster_hash == NULL || ctx == NULL || out_root == NULL) {
        return VOS_DGEN_ERR_INVALID_ARG;
    }
    uint8_t buf[104];
    memcpy(buf, "VOSDGEN1", 8u);
    put_le64(buf + 8u, version);
    put_le64(buf + 16u, declared_floor);
    memcpy(buf + 24u, roster_hash->bytes, VOS_DGEN_DIGEST_BYTES);
    put_context(buf + 56u, ctx);
    const int ok = vos_sha256(buf, sizeof(buf), out_root->bytes);
    zero_bytes(buf, sizeof(buf));
    return ok ? VOS_DGEN_OK : VOS_DGEN_ERR_CRYPTO;
}

enum vos_dgen_status vos_dgen_checked_set_seal(const struct vos_dgen_crypto_core *core,
                                               struct vos_dgen_checked_set *set)
{
    if (core == NULL || set == NULL) {
        return VOS_DGEN_ERR_INVALID_ARG;
    }
    return compute_checked_set_mac(core, set, set->root_hmac);
}

enum vos_dgen_status vos_dgen_checked_set_verify(const struct vos_dgen_crypto_core *core,
                                                 const struct vos_dgen_checked_set *set)
{
    uint8_t expected[VOS_DGEN_DIGEST_BYTES];
    const enum vos_dgen_status st = compute_checked_set_mac(core, set, expected);
    if (st != VOS_DGEN_OK) {
        return st;
    }
    const int match = equal_bytes_ct(expected, set->root_hmac, VOS_DGEN_DIGEST_BYTES);
    zero_bytes(expected, sizeof(expected));
    return match ? VOS_DGEN_OK : VOS_DGEN_ERR_TAMPERED_CHECKED_SET;
}

enum vos_dgen_status vos_dgen_mode_enter(struct vos_dgen_mode_guard *guard,
                                         uint32_t cert_valid,
                                         uint32_t guard_ok,
                                         uint32_t dwell_ok,
                                         uint32_t recovery_reserved)
{
    if (guard == NULL) {
        return VOS_DGEN_ERR_INVALID_ARG;
    }
    if (guard->mode != VOS_DGEN_MODE_NORMAL || guard->priv_active != 0u) {
        guard->mode = VOS_DGEN_MODE_NORMAL;
        guard->priv_active = 0u;
        return VOS_DGEN_ERR_MODE_LOCKED;
    }
    if (cert_valid == 0u || guard_ok == 0u || dwell_ok == 0u || recovery_reserved == 0u) {
        return VOS_DGEN_ERR_MODE_CERT;
    }
    guard->mode = VOS_DGEN_MODE_COMPOSITION;
    guard->priv_active = 1u;
    guard->switches += 1u;
    return VOS_DGEN_OK;
}

void vos_dgen_mode_exit(struct vos_dgen_mode_guard *guard)
{
    if (guard == NULL) {
        return;
    }
    if (guard->mode == VOS_DGEN_MODE_COMPOSITION) {
        guard->switches += 1u;
    }
    guard->mode = VOS_DGEN_MODE_NORMAL;
    guard->priv_active = 0u;
}

enum vos_dgen_status vos_dgen_audit_offline_package(uint32_t network_reachable,
                                                    const struct vos_dgen_package *pkg)
{
    (void)network_reachable;
    if (pkg == NULL || pkg->closure_count > VOS_DGEN_MAX_CLOSURE) {
        return VOS_DGEN_ERR_INVALID_ARG;
    }
    if (pkg->locally_composed != 0u) {
        if (pkg->has_publisher != 0u) {
            return VOS_DGEN_ERR_PUBLISHER_PRESENT;
        }
    } else if (pkg->package_logged == 0u) {
        return VOS_DGEN_ERR_UNLOGGED_FETCH;
    }

    for (uint32_t i = 0u; i < pkg->closure_count; ++i) {
        const struct vos_dgen_closure_member *m = &pkg->closure[i];
        if (m->origin == VOS_DGEN_ORIGIN_LOCAL_AUTHORED) {
            if (m->has_publisher != 0u) {
                return VOS_DGEN_ERR_PUBLISHER_PRESENT;
            }
        } else if (m->origin == VOS_DGEN_ORIGIN_FETCHED_LOGGED) {
            if (m->logged_in_checkpoint == 0u) {
                return VOS_DGEN_ERR_UNLOGGED_FETCH;
            }
            if (m->consistent_with_pin == 0u || m->inclusion_ok == 0u) {
                return VOS_DGEN_ERR_CONSISTENCY;
            }
        } else {
            return VOS_DGEN_ERR_INVALID_ARG;
        }
    }
    return VOS_DGEN_OK;
}

enum vos_dgen_status vos_dgen_core_export_key(const struct vos_dgen_crypto_core *core,
                                              uint8_t out_key[VOS_DGEN_KEY_BYTES])
{
    (void)core;
    if (out_key != NULL) {
        zero_bytes(out_key, VOS_DGEN_KEY_BYTES);
    }
    return VOS_DGEN_ERR_EXPORT_FORBIDDEN;
}

enum vos_dgen_status vos_dgen_trusted_path_mint(struct vos_dgen_crypto_core *core,
                                                const struct vos_dgen_composer_cap *composer,
                                                const struct vos_dgen_hash *roster_hash,
                                                const struct vos_dgen_hash *gen_root,
                                                struct vos_dgen_consent *consent,
                                                struct vos_dgen_mint_signature *out_sig)
{
    if (core == NULL || composer == NULL || roster_hash == NULL ||
        gen_root == NULL || out_sig == NULL) {
        return VOS_DGEN_ERR_INVALID_ARG;
    }
    if (core->exportable != 0u) {
        return VOS_DGEN_ERR_EXPORT_FORBIDDEN;
    }
    if (core->enrolled == 0u) {
        return VOS_DGEN_ERR_INVALID_ARG;
    }
    if (composer->holds_signing_key != 0u || composer->holds_mint_cap != 0u) {
        return VOS_DGEN_ERR_COMPOSER_PRIVILEGED;
    }
    if (consent == NULL || consent->user_consented == 0u) {
        return VOS_DGEN_ERR_NO_CONSENT;
    }
    if (consent->credential_present == 0u) {
        return VOS_DGEN_ERR_CREDENTIAL_ABSENT;
    }
    if (consent->consumed != 0u) {
        return VOS_DGEN_ERR_NONCE_REPLAY;
    }
    if (consent->prompt.roster_name_len == 0u ||
        consent->prompt.roster_name_len > VOS_DGEN_MAX_NAME_BYTES) {
        return VOS_DGEN_ERR_CONSENT_MISMATCH;
    }
    if (!equal_hashes(&consent->prompt.roster_hash, roster_hash) ||
        !equal_hashes(&consent->prompt.gen_root, gen_root)) {
        return VOS_DGEN_ERR_CONSENT_MISMATCH;
    }
    if (nonce_already_used(core, consent->prompt.nonce)) {
        return VOS_DGEN_ERR_NONCE_REPLAY;
    }
    if (core->used_nonce_count >= VOS_DGEN_MAX_NONCES) {
        return VOS_DGEN_ERR_BUDGET_EXCEEDED;
    }

    uint8_t mac[VOS_DGEN_DIGEST_BYTES];
    const enum vos_dgen_status st = compute_mint_mac(
        core, roster_hash, gen_root, consent->prompt.nonce, mac);
    if (st != VOS_DGEN_OK) {
        return st;
    }

    consent->consumed = 1u;
    core->used_nonces[core->used_nonce_count] = consent->prompt.nonce;
    core->used_nonce_count += 1u;

    out_sig->key_id = core->key_id;
    out_sig->roster_hash = *roster_hash;
    out_sig->gen_root = *gen_root;
    out_sig->nonce = consent->prompt.nonce;
    memcpy(out_sig->mac, mac, VOS_DGEN_DIGEST_BYTES);
    zero_bytes(mac, sizeof(mac));
    return VOS_DGEN_OK;
}

enum vos_dgen_status vos_dgen_compose_and_admit(struct vos_dgen_device *dev,
                                                const struct vos_dgen_request *req,
                                                struct vos_dgen_consent *consent)
{
    if (dev == NULL || req == NULL || req->package_count == 0u ||
        req->package_count > VOS_DGEN_MAX_PACKAGES) {
        return VOS_DGEN_ERR_INVALID_ARG;
    }

    enum vos_dgen_status st = vos_dgen_mode_enter(
        &dev->mode_guard,
        req->mode_cert_valid,
        req->mode_guard_ok,
        req->mode_dwell_ok,
        req->mode_recovery_reserved);
    if (st != VOS_DGEN_OK) {
        return st;
    }

    if (req->version < dev->ab.floor || req->version < req->declared_floor) {
        vos_dgen_mode_exit(&dev->mode_guard);
        return VOS_DGEN_ERR_ROLLBACK_FLOOR;
    }

    st = vos_dgen_checked_set_verify(&dev->core, &dev->checked_set);
    if (st != VOS_DGEN_OK) {
        vos_dgen_mode_exit(&dev->mode_guard);
        return st;
    }

    struct vos_dgen_checked_set next_set;
    memset(&next_set, 0, sizeof(next_set));
    struct vos_dgen_occupancy occ;
    memset(&occ, 0, sizeof(occ));
    occ.staged_slots_used = 1u;

    uint32_t total_steps = 0u;
    uint32_t max_workset = 0u;

    for (uint32_t i = 0u; i < req->package_count; ++i) {
        const struct vos_dgen_package *pkg = &req->packages[i];
        st = vos_dgen_audit_offline_package(req->network_reachable, pkg);
        if (st != VOS_DGEN_OK) {
            vos_dgen_mode_exit(&dev->mode_guard);
            return st;
        }
        if (pkg->code_len > VOS_DGEN_MAX_CODE_BYTES) {
            vos_dgen_mode_exit(&dev->mode_guard);
            return VOS_DGEN_ERR_INVALID_ARG;
        }
        if (pkg->code_len > 0u) {
            struct vos_dgen_hash actual_code;
            if (!vos_sha256(pkg->code_bytes, pkg->code_len, actual_code.bytes) ||
                !equal_hashes(&actual_code, &pkg->code_digest)) {
                vos_dgen_mode_exit(&dev->mode_guard);
                return VOS_DGEN_ERR_CORRUPT_OBJECT;
            }
        }
        struct vos_dgen_hash art;
        st = vos_dgen_compute_artifact_digest(pkg, &dev->context, &art);
        if (st != VOS_DGEN_OK) {
            vos_dgen_mode_exit(&dev->mode_guard);
            return st;
        }
        if (!equal_hashes(&art, &pkg->expected_artifact_digest)) {
            vos_dgen_mode_exit(&dev->mode_guard);
            return VOS_DGEN_ERR_CORRUPT_OBJECT;
        }
        if (pkg->is_base_image != 0u &&
            !equal_hashes(&pkg->expected_base_digest, &pkg->code_digest)) {
            vos_dgen_mode_exit(&dev->mode_guard);
            return VOS_DGEN_ERR_BASE_NOT_REPRODUCIBLE;
        }

        occ.total_package_bytes += pkg->code_len + pkg->init_len;

        const int reused = find_reusable_entry(&dev->checked_set, pkg, &art, &dev->context);
        if (reused) {
            occ.reused_packages += 1u;
        } else {
            if (req->cic_checker_available == 0u || pkg->proof_ok == 0u) {
                vos_dgen_mode_exit(&dev->mode_guard);
                return VOS_DGEN_ERR_PROOF_FAILED;
            }
            if (pkg->proof_steps > dev->step_budget ||
                total_steps > dev->step_budget - pkg->proof_steps ||
                pkg->proof_workset_bytes > dev->workset_budget) {
                vos_dgen_mode_exit(&dev->mode_guard);
                return VOS_DGEN_ERR_BUDGET_EXCEEDED;
            }
            total_steps += pkg->proof_steps;
            if (pkg->proof_workset_bytes > max_workset) {
                max_workset = pkg->proof_workset_bytes;
            }
            occ.fresh_checked_packages += 1u;
        }

        if (next_set.entry_count >= VOS_DGEN_MAX_CHECKED) {
            vos_dgen_mode_exit(&dev->mode_guard);
            return VOS_DGEN_ERR_BUDGET_EXCEEDED;
        }
        struct vos_dgen_checked_entry *dst = &next_set.entries[next_set.entry_count];
        dst->pkg_id = pkg->pkg_id;
        dst->artifact_digest = art;
        dst->source_digest = pkg->source_digest;
        dst->contract_digest = pkg->contract_digest;
        dst->proof_digest = pkg->proof_digest;
        dst->context = dev->context;
        next_set.entry_count += 1u;
    }

    if (req->tal_layout_fresh_ok == 0u) {
        vos_dgen_mode_exit(&dev->mode_guard);
        return VOS_DGEN_ERR_TAL_STALE;
    }
    if (req->wiring_fresh_ok == 0u || req->global_resource_ok == 0u) {
        vos_dgen_mode_exit(&dev->mode_guard);
        return VOS_DGEN_ERR_GLOBAL_CHECK_FAILED;
    }

    struct vos_dgen_hash roster_hash;
    st = vos_dgen_compute_roster_hash(
        req->packages, req->package_count, &dev->context, &roster_hash);
    if (st != VOS_DGEN_OK) {
        vos_dgen_mode_exit(&dev->mode_guard);
        return st;
    }
    struct vos_dgen_hash gen_root;
    st = vos_dgen_compute_gen_root(
        req->version, req->declared_floor, &roster_hash, &dev->context, &gen_root);
    if (st != VOS_DGEN_OK) {
        vos_dgen_mode_exit(&dev->mode_guard);
        return st;
    }

    struct vos_dgen_mint_signature sig;
    st = vos_dgen_trusted_path_mint(
        &dev->core, &dev->composer, &roster_hash, &gen_root, consent, &sig);
    if (st != VOS_DGEN_OK) {
        vos_dgen_mode_exit(&dev->mode_guard);
        return st;
    }

    st = vos_dgen_checked_set_seal(&dev->core, &next_set);
    if (st != VOS_DGEN_OK) {
        vos_dgen_mode_exit(&dev->mode_guard);
        return st;
    }

    /* Stage only into the inactive A/B slot; running slot stays untouched until verify passes. */
    struct vos_dgen_ab_slot *spare =
        (dev->ab.live_is_b != 0u) ? &dev->ab.slot_a : &dev->ab.slot_b;
    spare->valid = 1u;
    spare->root = gen_root;
    spare->roster_hash = roster_hash;
    spare->version = req->version;
    spare->declared_floor = req->declared_floor;
    spare->signature = sig;

    dev->ab.staged = 1u;
    dev->ab.admitted = 1u;
    dev->ab.has_retained = 1u;
    dev->ab.live_is_b = (dev->ab.live_is_b != 0u) ? 0u : 1u;
    dev->ab.staged = 0u;
    dev->ab.admitted = 0u;
    dev->checked_set = next_set;

    occ.total_proof_steps = total_steps;
    occ.total_proof_workset_bytes = max_workset;
    vos_dgen_mode_exit(&dev->mode_guard);
    occ.mode_switches = dev->mode_guard.switches;
    dev->last_occupancy = occ;
    return VOS_DGEN_OK;
}

enum vos_dgen_status vos_dgen_health_check(struct vos_dgen_device *dev,
                                            uint32_t healthy)
{
    if (dev == NULL) {
        return VOS_DGEN_ERR_INVALID_ARG;
    }
    if (healthy != 0u) {
        dev->ab.staged = 0u;
        dev->ab.admitted = 0u;
        return VOS_DGEN_OK;
    }
    if (dev->ab.has_retained == 0u) {
        return VOS_DGEN_ERR_NO_RETAINED;
    }
    const struct vos_dgen_ab_slot *ret =
        (dev->ab.live_is_b != 0u) ? &dev->ab.slot_a : &dev->ab.slot_b;
    if (ret->valid == 0u || ret->version < dev->ab.floor ||
        ret->version < ret->declared_floor) {
        return VOS_DGEN_ERR_ROLLBACK_FLOOR;
    }
    dev->ab.live_is_b = (dev->ab.live_is_b != 0u) ? 0u : 1u;
    dev->ab.has_retained = 0u;
    dev->ab.staged = 0u;
    dev->ab.admitted = 0u;
    return VOS_DGEN_ERR_UNHEALTHY_ROLLBACK;
}

const struct vos_dgen_ab_slot *vos_dgen_live_slot(const struct vos_dgen_device *dev)
{
    if (dev == NULL) {
        return NULL;
    }
    return (dev->ab.live_is_b != 0u) ? &dev->ab.slot_b : &dev->ab.slot_a;
}

const struct vos_dgen_ab_slot *vos_dgen_spare_slot(const struct vos_dgen_device *dev)
{
    if (dev == NULL) {
        return NULL;
    }
    return (dev->ab.live_is_b != 0u) ? &dev->ab.slot_a : &dev->ab.slot_b;
}
