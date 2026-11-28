// SPDX-License-Identifier: Apache-2.0
#include "vos_session_custody.h"

_Static_assert((unsigned)VOS_SC_KEY_BYTES == (unsigned)VOS_CRYPTO_KEY_BYTES_256,
               "custody key width must match vos_crypto_core");
_Static_assert((unsigned)VOS_SC_DIGEST_BYTES == (unsigned)VOS_ATLS_DIGEST_BYTES,
               "digest width must match vos_attested_tls");
_Static_assert((unsigned)VOS_SC_MAX_SPENT_CONTEXTS == (unsigned)VOS_ATLS_MAX_USED_CONTEXTS,
               "spent-context capacity must match vos_attested_tls");

static void sc_zero_bytes(uint8_t *dst, size_t len)
{
    if (dst == NULL) {
        return;
    }
    volatile uint8_t *wipe = dst;
    for (size_t i = 0u; i < len; ++i) {
        wipe[i] = 0u;
    }
}

static void sc_copy_bytes(uint8_t *dst, const uint8_t *src, size_t len)
{
    if (len == 0u || dst == NULL || src == NULL) {
        return;
    }
    for (size_t i = 0u; i < len; ++i) {
        dst[i] = src[i];
    }
}

static int sc_equal_bytes_ct(const uint8_t *a, const uint8_t *b, size_t len)
{
    if (len == 0u) {
        return 1;
    }
    if (a == NULL || b == NULL) {
        return 0;
    }
    uint8_t diff = 0u;
    for (size_t i = 0u; i < len; ++i) {
        diff |= (uint8_t)(a[i] ^ b[i]);
    }
    return diff == 0u;
}

static int sc_bytes_equal_exact(const uint8_t *a,
                                uint32_t a_len,
                                const uint8_t *b,
                                uint32_t b_len,
                                uint32_t max_len)
{
    if (a_len != b_len || a_len > max_len) {
        return 0;
    }
    return sc_equal_bytes_ct(a, b, (size_t)a_len);
}

static int sc_is_all_zero(const uint8_t *buf, size_t len)
{
    if (buf == NULL) {
        return 1;
    }
    uint8_t acc = 0u;
    for (size_t i = 0u; i < len; ++i) {
        acc |= buf[i];
    }
    return acc == 0u;
}

static void sc_put_le32(uint8_t *dst, uint32_t val)
{
    for (uint32_t i = 0u; i < 4u; ++i) {
        dst[i] = (uint8_t)((val >> (8u * i)) & 0xffu);
    }
}

static void sc_put_le64(uint8_t *dst, uint64_t val)
{
    for (uint32_t i = 0u; i < 8u; ++i) {
        dst[i] = (uint8_t)((val >> (8u * i)) & 0xffu);
    }
}

static int sc_id_in_list(const uint64_t *items, uint32_t count, uint64_t id)
{
    for (uint32_t i = 0u; i < count; ++i) {
        if (items[i] == id) {
            return 1;
        }
    }
    return 0;
}

static enum vos_sc_status sc_record_id(uint64_t *items,
                                       uint32_t *count,
                                       uint32_t cap,
                                       uint64_t id)
{
    if (sc_id_in_list(items, *count, id)) {
        return VOS_SC_OK;
    }
    if (*count >= cap) {
        return VOS_SC_ERR_CAPACITY;
    }
    items[*count] = id;
    *count += 1u;
    return VOS_SC_OK;
}

static int sc_tls_registration_eligible(const struct vos_sc_tls_registration *reg)
{
    if (reg == NULL) {
        return 0;
    }
    if (reg->unit_id == 0u ||
        reg->principal_len == 0u || reg->principal_len > VOS_ATLS_MAX_PRINCIPAL_BYTES ||
        reg->origin_len == 0u || reg->origin_len > VOS_ATLS_MAX_ORIGIN_BYTES) {
        return 0;
    }
    if (reg->handshake_complete != 1u || reg->server_authenticated != 1u) {
        return 0;
    }
    if (reg->early_data != 0u) {
        return 0;
    }
    if (reg->resumed != 0u) {
        return 0;
    }
    return 1;
}

static int sc_slot_tls_eligible(const struct vos_sc_context_slot *slot)
{
    if (slot == NULL) {
        return 0;
    }
    if (slot->context_id == 0u || slot->unit_id == 0u ||
        slot->principal_len == 0u || slot->principal_len > VOS_ATLS_MAX_PRINCIPAL_BYTES ||
        slot->origin_len == 0u || slot->origin_len > VOS_ATLS_MAX_ORIGIN_BYTES) {
        return 0;
    }
    if (slot->handshake_complete != 1u || slot->server_authenticated != 1u ||
        slot->early_data != 0u || slot->resumed != 0u) {
        return 0;
    }
    return 1;
}

/* Derives RFC-8446 / Q22c EXPORTER-Channel-Binding (empty context, 32 bytes)
 * solely from traffic-key custody via HMAC-SHA256. */
static enum vos_sc_status sc_derive_channel_binding(
    const uint8_t traffic_key[VOS_SC_KEY_BYTES],
    uint8_t out_exporter[VOS_ATLS_EXPORTER_BYTES])
{
    if (traffic_key == NULL || out_exporter == NULL) {
        return VOS_SC_ERR_INVALID;
    }
    uint8_t input[VOS_SC_EXPORTER_LABEL_BYTES + 2u];
    sc_copy_bytes(input, (const uint8_t *)VOS_SC_EXPORTER_LABEL, VOS_SC_EXPORTER_LABEL_BYTES);
    input[VOS_SC_EXPORTER_LABEL_BYTES] = 0u;
    input[VOS_SC_EXPORTER_LABEL_BYTES + 1u] = 0u;

    const int ok = vos_hmac_sha256(traffic_key, VOS_SC_KEY_BYTES,
                                   input, sizeof(input), out_exporter);
    sc_zero_bytes(input, sizeof(input));
    if (ok != 1) {
        return VOS_SC_ERR_KEY_CUSTODY;
    }
    return VOS_SC_OK;
}

static enum vos_sc_status sc_compute_ctx_handle_mac(
    const struct vos_sc_vault *vault,
    uint32_t slot_idx,
    const struct vos_sc_context_slot *slot,
    uint8_t out_mac[VOS_SC_DIGEST_BYTES])
{
    uint8_t msg[8u + 4u + 8u + 8u + 8u + VOS_SC_DIGEST_BYTES];
    const uint8_t tag[8] = { 'V', 'O', 'S', 'S', 'C', 'C', 'H', '1' };
    sc_copy_bytes(msg, tag, 8u);
    sc_put_le32(msg + 8u, slot_idx);
    sc_put_le64(msg + 12u, slot->context_id);
    sc_put_le64(msg + 20u, slot->lifecycle_epoch);
    sc_put_le64(msg + 28u, slot->unit_id);
    sc_copy_bytes(msg + 36u, slot->config_digest, VOS_SC_DIGEST_BYTES);

    const int ok = vos_hmac_sha256(vault->vault_custody_key, VOS_SC_KEY_BYTES,
                                   msg, sizeof(msg), out_mac);
    sc_zero_bytes(msg, sizeof(msg));
    return (ok == 1) ? VOS_SC_OK : VOS_SC_ERR_KEY_CUSTODY;
}

static enum vos_sc_status sc_compute_cred_handle_mac(
    const struct vos_sc_vault *vault,
    uint32_t slot_idx,
    const struct vos_sc_cred_slot *slot,
    uint8_t out_mac[VOS_SC_DIGEST_BYTES])
{
    uint8_t msg[8u + 4u + 8u + 8u + 8u + 4u];
    const uint8_t tag[8] = { 'V', 'O', 'S', 'S', 'C', 'K', 'H', '1' };
    sc_copy_bytes(msg, tag, 8u);
    sc_put_le32(msg + 8u, slot_idx);
    sc_put_le64(msg + 12u, slot->cred_id);
    sc_put_le64(msg + 20u, slot->lifecycle_epoch);
    sc_put_le64(msg + 28u, slot->cred.unit_id);
    sc_put_le32(msg + 36u, slot->cred.account_id);

    const int ok = vos_hmac_sha256(vault->vault_custody_key, VOS_SC_KEY_BYTES,
                                   msg, sizeof(msg), out_mac);
    sc_zero_bytes(msg, sizeof(msg));
    return (ok == 1) ? VOS_SC_OK : VOS_SC_ERR_KEY_CUSTODY;
}

static enum vos_sc_status sc_resolve_context_handle(
    const struct vos_sc_vault *vault,
    const struct vos_sc_context_handle *handle,
    const struct vos_sc_context_slot **out_slot)
{
    if (vault == NULL || vault->initialized != 1u || handle == NULL || out_slot == NULL) {
        return VOS_SC_ERR_INVALID;
    }
    if (handle->sealed != 1u || handle->slot >= VOS_SC_MAX_CONTEXTS) {
        return VOS_SC_ERR_HANDLE_AUTH;
    }

    const struct vos_sc_context_slot *slot = &vault->contexts[handle->slot];
    if (slot->retired != 0u || slot->active != 1u) {
        return VOS_SC_ERR_TEARDOWN;
    }
    if (slot->context_id != handle->context_id ||
        slot->lifecycle_epoch != vault->lifecycle_epoch ||
        handle->lifecycle_epoch != vault->lifecycle_epoch) {
        return VOS_SC_ERR_TEARDOWN;
    }
    if (slot->key_exposed != 0u) {
        return VOS_SC_ERR_KEY_CUSTODY;
    }
    if (!sc_slot_tls_eligible(slot)) {
        return VOS_SC_ERR_INELIGIBLE_TLS;
    }
    if (!sc_equal_bytes_ct(slot->config_digest, vault->expected_config_digest,
                           VOS_SC_DIGEST_BYTES)) {
        return VOS_SC_ERR_CONFIG_DIGEST;
    }

    uint8_t expected_mac[VOS_SC_DIGEST_BYTES];
    const enum vos_sc_status mst =
        sc_compute_ctx_handle_mac(vault, handle->slot, slot, expected_mac);
    if (mst != VOS_SC_OK) {
        return mst;
    }
    if (!sc_equal_bytes_ct(expected_mac, handle->handle_mac, VOS_SC_DIGEST_BYTES)) {
        sc_zero_bytes(expected_mac, sizeof(expected_mac));
        return VOS_SC_ERR_HANDLE_AUTH;
    }
    sc_zero_bytes(expected_mac, sizeof(expected_mac));
    *out_slot = slot;
    return VOS_SC_OK;
}

static enum vos_sc_status sc_resolve_cred_handle(
    const struct vos_sc_vault *vault,
    const struct vos_sc_cred_handle *handle,
    const struct vos_sc_cred_slot **out_slot)
{
    if (vault == NULL || vault->initialized != 1u || handle == NULL || out_slot == NULL) {
        return VOS_SC_ERR_INVALID;
    }
    if (handle->sealed != 1u || handle->slot >= VOS_SC_MAX_CREDENTIALS) {
        return VOS_SC_ERR_HANDLE_AUTH;
    }

    const struct vos_sc_cred_slot *slot = &vault->creds[handle->slot];
    if (slot->active != 1u || slot->cred_id != handle->cred_id) {
        return VOS_SC_ERR_HANDLE_AUTH;
    }
    if (slot->lifecycle_epoch != vault->lifecycle_epoch ||
        handle->lifecycle_epoch != vault->lifecycle_epoch) {
        return VOS_SC_ERR_TEARDOWN;
    }

    uint8_t expected_mac[VOS_SC_DIGEST_BYTES];
    const enum vos_sc_status mst =
        sc_compute_cred_handle_mac(vault, handle->slot, slot, expected_mac);
    if (mst != VOS_SC_OK) {
        return mst;
    }
    if (!sc_equal_bytes_ct(expected_mac, handle->handle_mac, VOS_SC_DIGEST_BYTES)) {
        sc_zero_bytes(expected_mac, sizeof(expected_mac));
        return VOS_SC_ERR_HANDLE_AUTH;
    }
    sc_zero_bytes(expected_mac, sizeof(expected_mac));
    *out_slot = slot;
    return VOS_SC_OK;
}

static void sc_build_atls_context(const struct vos_sc_context_slot *slot,
                                  struct vos_atls_protected_context *out_ctx)
{
    sc_zero_bytes((uint8_t *)out_ctx, sizeof(*out_ctx));
    out_ctx->context_id = slot->context_id;
    out_ctx->unit_id = slot->unit_id;
    out_ctx->principal_len = slot->principal_len;
    sc_copy_bytes(out_ctx->principal, slot->principal, slot->principal_len);
    out_ctx->origin_len = slot->origin_len;
    sc_copy_bytes(out_ctx->origin, slot->origin, slot->origin_len);
    sc_copy_bytes(out_ctx->exporter, slot->derived_exporter, VOS_ATLS_EXPORTER_BYTES);
    out_ctx->handshake_complete = slot->handshake_complete;
    out_ctx->server_authenticated = slot->server_authenticated;
    out_ctx->early_data = slot->early_data;
    out_ctx->resumed = slot->resumed;
}

static void sc_retire_context_slot(struct vos_sc_vault *vault,
                                   struct vos_sc_context_slot *slot)
{
    if (slot->active != 0u && slot->context_id != 0u) {
        (void)sc_record_id(vault->spent_contexts, &vault->spent_context_count,
                           VOS_SC_MAX_SPENT_CONTEXTS, slot->context_id);
    }
    sc_zero_bytes(slot->traffic_key, sizeof(slot->traffic_key));
    sc_zero_bytes(slot->derived_exporter, sizeof(slot->derived_exporter));
    slot->active = 0u;
    slot->retired = 1u;
}

enum vos_sc_status vos_sc_vault_init(struct vos_sc_vault *vault,
                                     const uint8_t hmac_key[VOS_SC_KEY_BYTES],
                                     const uint8_t custody_key[VOS_SC_KEY_BYTES],
                                     const uint8_t config_digest[VOS_SC_DIGEST_BYTES],
                                     uint64_t server_now)
{
    if (vault == NULL || hmac_key == NULL || custody_key == NULL || config_digest == NULL) {
        return VOS_SC_ERR_INVALID;
    }
    if (sc_is_all_zero(custody_key, VOS_SC_KEY_BYTES) ||
        sc_is_all_zero(config_digest, VOS_SC_DIGEST_BYTES)) {
        return VOS_SC_ERR_INVALID;
    }

    sc_zero_bytes((uint8_t *)vault, sizeof(*vault));
    vos_crypto_core_init(&vault->crypto_core, 1024u);
    if (vos_crypto_core_unlock_domain(&vault->crypto_core, VOS_CRYPTO_DOMAIN_SYSTEM,
                                      1u, 1u, custody_key, VOS_SC_KEY_BYTES) != 1) {
        sc_zero_bytes((uint8_t *)vault, sizeof(*vault));
        return VOS_SC_ERR_KEY_CUSTODY;
    }
    vos_atls_broker_init(&vault->broker, hmac_key, server_now);
    sc_copy_bytes(vault->vault_custody_key, custody_key, VOS_SC_KEY_BYTES);
    sc_copy_bytes(vault->expected_config_digest, config_digest, VOS_SC_DIGEST_BYTES);
    vault->lifecycle_epoch = 1u;
    vault->next_context_id = 1u;
    vault->next_cred_id = 1u;
    vault->initialized = 1u;
    return VOS_SC_OK;
}

enum vos_sc_status vos_sc_set_measurement(struct vos_sc_vault *vault,
                                          uint64_t unit_id,
                                          uint64_t generation)
{
    if (vault == NULL || vault->initialized != 1u || unit_id == 0u) {
        return VOS_SC_ERR_INVALID;
    }
    if (vos_atls_broker_set_measurement(&vault->broker, unit_id, generation) != VOS_ATLS_OK) {
        return VOS_SC_ERR_ATLS;
    }
    return VOS_SC_OK;
}

enum vos_sc_status vos_sc_set_alias(struct vos_sc_vault *vault,
                                    const uint8_t *origin,
                                    uint32_t origin_len,
                                    uint64_t unit_id,
                                    const uint8_t *alias,
                                    uint32_t alias_len)
{
    if (vault == NULL || vault->initialized != 1u || unit_id == 0u ||
        origin == NULL || alias == NULL ||
        origin_len == 0u || origin_len > VOS_ATLS_MAX_ORIGIN_BYTES ||
        alias_len == 0u || alias_len > VOS_ATLS_MAX_ALIAS_BYTES) {
        return VOS_SC_ERR_INVALID;
    }

    /* Enforce AuthenticatedUnitPseudonyms: an origin's alias uniquely identifies one unit. */
    for (uint32_t i = 0u; i < VOS_ATLS_MAX_ALIASES; ++i) {
        const struct vos_atls_alias_entry *entry = &vault->broker.aliases[i];
        if (entry->present != 0u &&
            entry->unit_id != unit_id &&
            sc_bytes_equal_exact(entry->origin, entry->origin_len,
                                 origin, origin_len, VOS_ATLS_MAX_ORIGIN_BYTES) &&
            sc_bytes_equal_exact(entry->alias, entry->alias_len,
                                 alias, alias_len, VOS_ATLS_MAX_ALIAS_BYTES)) {
            return VOS_SC_ERR_HANDLE_AUTH;
        }
    }

    if (vos_atls_broker_set_alias(&vault->broker, origin, origin_len,
                                  unit_id, alias, alias_len) != VOS_ATLS_OK) {
        return VOS_SC_ERR_ATLS;
    }
    return VOS_SC_OK;
}

enum vos_sc_status vos_sc_register_tls_context(struct vos_sc_vault *vault,
                                               const struct vos_sc_tls_registration *reg,
                                               struct vos_sc_context_handle *out_handle)
{
    if (vault == NULL || vault->initialized != 1u || reg == NULL || out_handle == NULL) {
        return VOS_SC_ERR_INVALID;
    }
    if (!sc_tls_registration_eligible(reg)) {
        return VOS_SC_ERR_INELIGIBLE_TLS;
    }
    if (!sc_equal_bytes_ct(reg->config_digest, vault->expected_config_digest,
                           VOS_SC_DIGEST_BYTES)) {
        return VOS_SC_ERR_CONFIG_DIGEST;
    }
    if (sc_is_all_zero(reg->traffic_key, VOS_SC_KEY_BYTES)) {
        return VOS_SC_ERR_KEY_CUSTODY;
    }

    uint32_t free_idx = VOS_SC_MAX_CONTEXTS;
    for (uint32_t i = 0u; i < VOS_SC_MAX_CONTEXTS; ++i) {
        if (vault->contexts[i].active == 0u) {
            free_idx = i;
            break;
        }
    }
    if (free_idx >= VOS_SC_MAX_CONTEXTS) {
        return VOS_SC_ERR_CAPACITY;
    }

    struct vos_sc_context_slot *slot = &vault->contexts[free_idx];
    sc_zero_bytes((uint8_t *)slot, sizeof(*slot));

    slot->context_id = vault->next_context_id;
    vault->next_context_id += 1u;
    slot->lifecycle_epoch = vault->lifecycle_epoch;
    slot->unit_id = reg->unit_id;
    slot->principal_len = reg->principal_len;
    sc_copy_bytes(slot->principal, reg->principal, reg->principal_len);
    slot->origin_len = reg->origin_len;
    sc_copy_bytes(slot->origin, reg->origin, reg->origin_len);
    sc_copy_bytes(slot->config_digest, reg->config_digest, VOS_SC_DIGEST_BYTES);
    sc_copy_bytes(slot->traffic_key, reg->traffic_key, VOS_SC_KEY_BYTES);
    slot->handshake_complete = reg->handshake_complete;
    slot->server_authenticated = reg->server_authenticated;
    slot->early_data = reg->early_data;
    slot->resumed = reg->resumed;

    const enum vos_sc_status dst =
        sc_derive_channel_binding(slot->traffic_key, slot->derived_exporter);
    if (dst != VOS_SC_OK) {
        sc_zero_bytes((uint8_t *)slot, sizeof(*slot));
        return dst;
    }

    struct vos_sc_context_handle h;
    sc_zero_bytes((uint8_t *)&h, sizeof(h));
    h.slot = free_idx;
    h.context_id = slot->context_id;
    h.lifecycle_epoch = slot->lifecycle_epoch;
    h.sealed = 1u;
    const enum vos_sc_status mst =
        sc_compute_ctx_handle_mac(vault, free_idx, slot, h.handle_mac);
    if (mst != VOS_SC_OK) {
        sc_zero_bytes((uint8_t *)slot, sizeof(*slot));
        return mst;
    }

    slot->active = 1u;
    slot->retired = 0u;
    slot->key_exposed = 0u;
    *out_handle = h;
    return VOS_SC_OK;
}

enum vos_sc_status vos_sc_register_credential(struct vos_sc_vault *vault,
                                              const struct vos_atls_credential *cred,
                                              struct vos_sc_cred_handle *out_handle)
{
    if (vault == NULL || vault->initialized != 1u || cred == NULL || out_handle == NULL) {
        return VOS_SC_ERR_INVALID;
    }
    if (cred->sealed != 1u || cred->unit_id == 0u ||
        cred->account_id >= VOS_ATLS_MAX_ACCOUNTS ||
        cred->role_len == 0u || cred->role_len > VOS_ATLS_MAX_ROLE_BYTES ||
        cred->principal_len == 0u || cred->principal_len > VOS_ATLS_MAX_PRINCIPAL_BYTES ||
        cred->origin_len == 0u || cred->origin_len > VOS_ATLS_MAX_ORIGIN_BYTES ||
        cred->domain_len == 0u || cred->domain_len > VOS_ATLS_MAX_DOMAIN_BYTES) {
        return VOS_SC_ERR_CREDENTIAL_AUTH;
    }

    uint32_t free_idx = VOS_SC_MAX_CREDENTIALS;
    for (uint32_t i = 0u; i < VOS_SC_MAX_CREDENTIALS; ++i) {
        if (vault->creds[i].active == 0u) {
            free_idx = i;
            break;
        }
    }
    if (free_idx >= VOS_SC_MAX_CREDENTIALS) {
        return VOS_SC_ERR_CAPACITY;
    }

    struct vos_sc_cred_slot *slot = &vault->creds[free_idx];
    sc_zero_bytes((uint8_t *)slot, sizeof(*slot));
    slot->active = 1u;
    slot->cred_id = vault->next_cred_id;
    vault->next_cred_id += 1u;
    slot->lifecycle_epoch = vault->lifecycle_epoch;
    slot->cred = *cred;

    struct vos_sc_cred_handle h;
    sc_zero_bytes((uint8_t *)&h, sizeof(h));
    h.slot = free_idx;
    h.cred_id = slot->cred_id;
    h.lifecycle_epoch = slot->lifecycle_epoch;
    h.sealed = 1u;
    const enum vos_sc_status mst =
        sc_compute_cred_handle_mac(vault, free_idx, slot, h.handle_mac);
    if (mst != VOS_SC_OK) {
        sc_zero_bytes((uint8_t *)slot, sizeof(*slot));
        return mst;
    }

    *out_handle = h;
    return VOS_SC_OK;
}

enum vos_sc_status vos_sc_delegate_credential(struct vos_sc_vault *vault,
                                              const struct vos_sc_cred_handle *parent_handle,
                                              const struct vos_atls_credential *child_spec,
                                              struct vos_sc_cred_handle *out_child_handle)
{
    const struct vos_sc_cred_slot *parent_slot = NULL;
    const enum vos_sc_status rst = sc_resolve_cred_handle(vault, parent_handle, &parent_slot);
    if (rst != VOS_SC_OK) {
        return rst;
    }
    if (child_spec == NULL || out_child_handle == NULL) {
        return VOS_SC_ERR_INVALID;
    }
    struct vos_atls_credential checked_child = *child_spec;
    if (vos_atls_delegate_credential(&parent_slot->cred, &checked_child) != VOS_ATLS_OK) {
        return VOS_SC_ERR_CREDENTIAL_AUTH;
    }
    return vos_sc_register_credential(vault, &checked_child, out_child_handle);
}

enum vos_sc_status vos_sc_derive_exporter_for_test(const struct vos_sc_vault *vault,
                                                   const struct vos_sc_context_handle *ctx_handle,
                                                   uint8_t out_exporter[VOS_ATLS_EXPORTER_BYTES])
{
    if (out_exporter == NULL) {
        return VOS_SC_ERR_INVALID;
    }
    const struct vos_sc_context_slot *slot = NULL;
    const enum vos_sc_status rst = sc_resolve_context_handle(vault, ctx_handle, &slot);
    if (rst != VOS_SC_OK) {
        return rst;
    }
    sc_copy_bytes(out_exporter, slot->derived_exporter, VOS_ATLS_EXPORTER_BYTES);
    return VOS_SC_OK;
}

enum vos_sc_status vos_sc_quote_session(struct vos_sc_vault *vault,
                                        const struct vos_atls_profile *profile,
                                        const struct vos_atls_cred_policy *cred_policy,
                                        const struct vos_sc_cred_handle *cred_handle,
                                        const struct vos_sc_context_handle *ctx_handle,
                                        const struct vos_atls_client_request *request,
                                        const uint8_t *challenge_wire,
                                        size_t challenge_wire_len,
                                        uint8_t *out_evidence_wire,
                                        size_t out_evidence_cap,
                                        size_t *out_evidence_len)
{
    if (vault == NULL || vault->initialized != 1u || profile == NULL ||
        cred_policy == NULL || request == NULL || challenge_wire == NULL ||
        out_evidence_wire == NULL || out_evidence_len == NULL) {
        return VOS_SC_ERR_INVALID;
    }

    const struct vos_sc_context_slot *ctx_slot = NULL;
    const enum vos_sc_status cst = sc_resolve_context_handle(vault, ctx_handle, &ctx_slot);
    if (cst != VOS_SC_OK) {
        return cst;
    }

    const struct vos_sc_cred_slot *cred_slot = NULL;
    const enum vos_sc_status kst = sc_resolve_cred_handle(vault, cred_handle, &cred_slot);
    if (kst != VOS_SC_OK) {
        return kst;
    }

    if (cred_slot->cred.unit_id != ctx_slot->unit_id) {
        return VOS_SC_ERR_CREDENTIAL_AUTH;
    }
    if (vault->account_charges[cred_slot->cred.account_id] >= cred_slot->cred.use_ceiling) {
        return VOS_SC_ERR_CREDENTIAL_AUTH;
    }

    struct vos_atls_challenge chal;
    if (vos_atls_decode_challenge(profile, challenge_wire, challenge_wire_len, &chal) !=
        VOS_ATLS_OK) {
        return VOS_SC_ERR_ATLS;
    }

    struct vos_atls_protected_context pctx;
    sc_build_atls_context(ctx_slot, &pctx);

    /* Keep derived_exporter strictly from protected traffic-key custody. */
    sc_copy_bytes(pctx.exporter, ctx_slot->derived_exporter, VOS_ATLS_EXPORTER_BYTES);

    const enum vos_atls_status ist = vos_atls_issue_local(
        profile, cred_policy, &cred_slot->cred, &vault->broker, request, &pctx, &chal,
        NULL, out_evidence_wire, out_evidence_cap, out_evidence_len);
    sc_zero_bytes((uint8_t *)&pctx, sizeof(pctx));
    if (ist != VOS_ATLS_OK) {
        return VOS_SC_ERR_ATLS;
    }

    vault->account_charges[cred_slot->cred.account_id] += 1u;
    return VOS_SC_OK;
}

enum vos_sc_status vos_sc_teardown_context(struct vos_sc_vault *vault,
                                           const struct vos_sc_context_handle *ctx_handle)
{
    const struct vos_sc_context_slot *checked_slot = NULL;
    const enum vos_sc_status rst = sc_resolve_context_handle(vault, ctx_handle, &checked_slot);
    if (rst != VOS_SC_OK) {
        return rst;
    }
    (void)checked_slot;
    sc_retire_context_slot(vault, &vault->contexts[ctx_handle->slot]);
    return VOS_SC_OK;
}

enum vos_sc_status vos_sc_advance_lifecycle(struct vos_sc_vault *vault)
{
    if (vault == NULL || vault->initialized != 1u) {
        return VOS_SC_ERR_INVALID;
    }
    for (uint32_t i = 0u; i < VOS_SC_MAX_CONTEXTS; ++i) {
        if (vault->contexts[i].active != 0u) {
            sc_retire_context_slot(vault, &vault->contexts[i]);
        }
    }
    for (uint32_t i = 0u; i < VOS_SC_MAX_CREDENTIALS; ++i) {
        vault->creds[i].active = 0u;
    }
    vault->lifecycle_epoch += 1u;
    return VOS_SC_OK;
}

enum vos_sc_status vos_sc_retire_unit_generation(struct vos_sc_vault *vault,
                                                 uint64_t unit_id,
                                                 uint64_t new_generation)
{
    if (vault == NULL || vault->initialized != 1u || unit_id == 0u) {
        return VOS_SC_ERR_INVALID;
    }
    if (vos_atls_broker_set_measurement(&vault->broker, unit_id, new_generation) != VOS_ATLS_OK) {
        return VOS_SC_ERR_ATLS;
    }
    for (uint32_t i = 0u; i < VOS_SC_MAX_CONTEXTS; ++i) {
        if (vault->contexts[i].active != 0u && vault->contexts[i].unit_id == unit_id) {
            sc_retire_context_slot(vault, &vault->contexts[i]);
        }
    }
    return VOS_SC_OK;
}

enum vos_sc_status vos_sc_mark_key_exposed(struct vos_sc_vault *vault,
                                           const struct vos_sc_context_handle *ctx_handle)
{
    const struct vos_sc_context_slot *checked_slot = NULL;
    const enum vos_sc_status rst = sc_resolve_context_handle(vault, ctx_handle, &checked_slot);
    if (rst != VOS_SC_OK) {
        return rst;
    }
    (void)checked_slot;
    vault->contexts[ctx_handle->slot].key_exposed = 1u;
    return VOS_SC_OK;
}

enum vos_sc_status vos_sc_session_open(struct vos_sc_session *session,
                                       const struct vos_sc_vault *vault,
                                       const struct vos_sc_context_handle *ctx_handle,
                                       const uint8_t expected_config_digest[VOS_SC_DIGEST_BYTES])
{
    if (session == NULL || expected_config_digest == NULL) {
        return VOS_SC_ERR_INVALID;
    }
    sc_zero_bytes((uint8_t *)session, sizeof(*session));

    const struct vos_sc_context_slot *slot = NULL;
    const enum vos_sc_status rst = sc_resolve_context_handle(vault, ctx_handle, &slot);
    if (rst != VOS_SC_OK) {
        return rst;
    }
    if (!sc_equal_bytes_ct(expected_config_digest, vault->expected_config_digest,
                           VOS_SC_DIGEST_BYTES)) {
        return VOS_SC_ERR_CONFIG_DIGEST;
    }
    if (sc_id_in_list(vault->spent_contexts, vault->spent_context_count, slot->context_id)) {
        return VOS_SC_ERR_SPENT_CONTEXT;
    }

    struct vos_atls_protected_context pctx;
    sc_build_atls_context(slot, &pctx);
    vos_atls_connection_init(&session->conn, &pctx);
    sc_zero_bytes((uint8_t *)&pctx, sizeof(pctx));

    session->initialized = 1u;
    session->attested_open = 0u;
    session->bound_lifecycle_epoch = vault->lifecycle_epoch;
    sc_copy_bytes(session->expected_config_digest, expected_config_digest, VOS_SC_DIGEST_BYTES);
    session->bound_handle = *ctx_handle;
    return VOS_SC_OK;
}

enum vos_sc_status vos_sc_session_begin(struct vos_sc_session *session,
                                        struct vos_sc_vault *vault,
                                        const struct vos_atls_profile *profile,
                                        const struct vos_atls_appraisal_policy *policy,
                                        const uint8_t *nonce,
                                        uint32_t nonce_len,
                                        uint64_t now,
                                        uint64_t deadline,
                                        uint8_t *out_challenge_wire,
                                        size_t cap,
                                        size_t *out_len)
{
    if (session == NULL || session->initialized != 1u || vault == NULL ||
        vault->initialized != 1u) {
        return VOS_SC_ERR_INVALID;
    }
    if (session->bound_lifecycle_epoch != vault->lifecycle_epoch) {
        vos_atls_close(&session->conn);
        return VOS_SC_ERR_TEARDOWN;
    }
    if (!sc_equal_bytes_ct(session->expected_config_digest, vault->expected_config_digest,
                           VOS_SC_DIGEST_BYTES)) {
        vos_atls_close(&session->conn);
        return VOS_SC_ERR_CONFIG_DIGEST;
    }

    const struct vos_sc_context_slot *slot = NULL;
    const enum vos_sc_status rst =
        sc_resolve_context_handle(vault, &session->bound_handle, &slot);
    if (rst != VOS_SC_OK) {
        vos_atls_close(&session->conn);
        return rst;
    }
    if (sc_id_in_list(session->spent_ids, session->spent_count, slot->context_id) ||
        sc_id_in_list(vault->spent_contexts, vault->spent_context_count, slot->context_id)) {
        vos_atls_close(&session->conn);
        return VOS_SC_ERR_SPENT_CONTEXT;
    }

    const enum vos_atls_status bst = vos_atls_begin_appraisal(
        profile, policy, &session->conn, nonce, nonce_len, now, deadline,
        out_challenge_wire, cap, out_len);
    if (bst != VOS_ATLS_OK) {
        return VOS_SC_ERR_ATLS;
    }

    if (sc_record_id(session->spent_ids, &session->spent_count,
                     VOS_SC_MAX_SPENT_CONTEXTS, slot->context_id) != VOS_SC_OK ||
        sc_record_id(vault->spent_contexts, &vault->spent_context_count,
                     VOS_SC_MAX_SPENT_CONTEXTS, slot->context_id) != VOS_SC_OK) {
        vos_atls_close(&session->conn);
        return VOS_SC_ERR_CAPACITY;
    }
    return VOS_SC_OK;
}

enum vos_sc_status vos_sc_session_decide(struct vos_sc_session *session,
                                         const struct vos_sc_vault *vault,
                                         const struct vos_atls_profile *profile,
                                         const struct vos_atls_appraisal_policy *policy,
                                         const uint8_t hmac_key[VOS_SC_KEY_BYTES],
                                         uint64_t now,
                                         const uint8_t *evidence_wire,
                                         size_t evidence_wire_len)
{
    if (session == NULL || session->initialized != 1u || vault == NULL ||
        vault->initialized != 1u) {
        return VOS_SC_ERR_INVALID;
    }
    session->attested_open = 0u;

    if (session->bound_lifecycle_epoch != vault->lifecycle_epoch) {
        vos_atls_close(&session->conn);
        return VOS_SC_ERR_TEARDOWN;
    }
    if (!sc_equal_bytes_ct(session->expected_config_digest, vault->expected_config_digest,
                           VOS_SC_DIGEST_BYTES)) {
        vos_atls_close(&session->conn);
        return VOS_SC_ERR_CONFIG_DIGEST;
    }

    const struct vos_sc_context_slot *slot = NULL;
    const enum vos_sc_status rst =
        sc_resolve_context_handle(vault, &session->bound_handle, &slot);
    if (rst != VOS_SC_OK) {
        vos_atls_close(&session->conn);
        return rst;
    }
    if (!sc_equal_bytes_ct(slot->derived_exporter, session->conn.ctx.exporter,
                           VOS_ATLS_EXPORTER_BYTES)) {
        vos_atls_close(&session->conn);
        return VOS_SC_ERR_KEY_CUSTODY;
    }

    const enum vos_atls_status dst = vos_atls_decide(
        profile, policy, hmac_key, &session->conn, now, evidence_wire, evidence_wire_len);
    if (dst != VOS_ATLS_OK) {
        return VOS_SC_ERR_ATLS;
    }

    session->attested_open = 1u;
    return VOS_SC_OK;
}

enum vos_sc_status vos_sc_session_fetch_one(struct vos_sc_session *session,
                                            const struct vos_sc_vault *vault,
                                            const struct vos_atls_profile *profile,
                                            uint64_t now,
                                            const uint8_t *req_wire,
                                            size_t req_wire_len,
                                            uint32_t manifest_authenticated,
                                            uint32_t object_matches,
                                            const uint8_t *object_bytes,
                                            uint32_t object_len,
                                            uint8_t *out_reply_wire,
                                            size_t cap,
                                            size_t *out_reply_len)
{
    if (session == NULL || session->initialized != 1u || vault == NULL ||
        vault->initialized != 1u) {
        return VOS_SC_ERR_INVALID;
    }

    const uint8_t was_attested_open = session->attested_open;
    session->attested_open = 0u;

    if (was_attested_open != 1u) {
        vos_atls_close(&session->conn);
        return VOS_SC_ERR_CREDENTIAL_AUTH;
    }
    if (session->bound_lifecycle_epoch != vault->lifecycle_epoch) {
        vos_atls_close(&session->conn);
        return VOS_SC_ERR_TEARDOWN;
    }
    if (!sc_equal_bytes_ct(session->expected_config_digest, vault->expected_config_digest,
                           VOS_SC_DIGEST_BYTES)) {
        vos_atls_close(&session->conn);
        return VOS_SC_ERR_CONFIG_DIGEST;
    }

    const struct vos_sc_context_slot *slot = NULL;
    const enum vos_sc_status rst =
        sc_resolve_context_handle(vault, &session->bound_handle, &slot);
    if (rst != VOS_SC_OK) {
        vos_atls_close(&session->conn);
        return rst;
    }

    const enum vos_atls_status fst = vos_atls_fetch_one(
        profile, &session->conn, now, req_wire, req_wire_len,
        manifest_authenticated, object_matches, object_bytes, object_len,
        out_reply_wire, cap, out_reply_len);
    if (fst != VOS_ATLS_OK) {
        return VOS_SC_ERR_ATLS;
    }
    return VOS_SC_OK;
}

enum vos_sc_status vos_sc_session_reconnect(struct vos_sc_session *session,
                                            const struct vos_sc_vault *vault,
                                            const struct vos_sc_context_handle *new_ctx_handle,
                                            const uint8_t expected_config_digest[VOS_SC_DIGEST_BYTES])
{
    if (session == NULL || session->initialized != 1u || expected_config_digest == NULL) {
        return VOS_SC_ERR_INVALID;
    }
    session->attested_open = 0u;

    const struct vos_sc_context_slot *slot = NULL;
    const enum vos_sc_status rst = sc_resolve_context_handle(vault, new_ctx_handle, &slot);
    if (rst != VOS_SC_OK) {
        vos_atls_close(&session->conn);
        return rst;
    }
    if (!sc_equal_bytes_ct(expected_config_digest, vault->expected_config_digest,
                           VOS_SC_DIGEST_BYTES)) {
        vos_atls_close(&session->conn);
        return VOS_SC_ERR_CONFIG_DIGEST;
    }
    if (sc_id_in_list(session->spent_ids, session->spent_count, slot->context_id) ||
        sc_id_in_list(vault->spent_contexts, vault->spent_context_count, slot->context_id)) {
        vos_atls_close(&session->conn);
        return VOS_SC_ERR_SPENT_CONTEXT;
    }

    struct vos_atls_protected_context new_pctx;
    sc_build_atls_context(slot, &new_pctx);
    const enum vos_atls_status rct = vos_atls_reconnect(&session->conn, &new_pctx);
    sc_zero_bytes((uint8_t *)&new_pctx, sizeof(new_pctx));
    if (rct != VOS_ATLS_OK) {
        return (rct == VOS_ATLS_ERR_SPENT_CONTEXT) ? VOS_SC_ERR_SPENT_CONTEXT : VOS_SC_ERR_ATLS;
    }

    session->bound_lifecycle_epoch = vault->lifecycle_epoch;
    sc_copy_bytes(session->expected_config_digest, expected_config_digest, VOS_SC_DIGEST_BYTES);
    session->bound_handle = *new_ctx_handle;
    return VOS_SC_OK;
}

void vos_sc_session_close(struct vos_sc_session *session, struct vos_sc_vault *vault)
{
    if (session == NULL) {
        return;
    }
    session->attested_open = 0u;
    vos_atls_close(&session->conn);
    if (vault != NULL && vault->initialized == 1u &&
        session->bound_handle.sealed == 1u &&
        session->bound_handle.slot < VOS_SC_MAX_CONTEXTS) {
        struct vos_sc_context_slot *slot = &vault->contexts[session->bound_handle.slot];
        if (slot->context_id == session->bound_handle.context_id) {
            sc_retire_context_slot(vault, slot);
        }
    }
}
