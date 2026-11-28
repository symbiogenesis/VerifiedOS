// SPDX-License-Identifier: Apache-2.0
#include "vos_trusted_screen.h"

#include <string.h>

_Static_assert((unsigned)VOS_TS_DISPLAY_SECRET_CHARS == (16u * 4u + 15u),
               "16x4 formatted recovery secret display must be 79 chars");
_Static_assert((unsigned)VOS_TS_HMAC_BYTES == (unsigned)VOS_CRYPTO_DIGEST_BYTES,
               "consent witness MAC must match SHA-256 digest width");

static void put_be32(uint8_t *dst, uint32_t v)
{
    dst[0] = (uint8_t)(v >> 24u);
    dst[1] = (uint8_t)(v >> 16u);
    dst[2] = (uint8_t)(v >> 8u);
    dst[3] = (uint8_t)v;
}

static void put_be64(uint8_t *dst, uint64_t v)
{
    for (uint32_t i = 0u; i < 8u; ++i) {
        dst[i] = (uint8_t)(v >> (56u - 8u * i));
    }
}

static int ct_equal(const uint8_t *a, const uint8_t *b, size_t len)
{
    uint8_t diff = 0u;
    for (size_t i = 0u; i < len; ++i) {
        diff |= (uint8_t)(a[i] ^ b[i]);
    }
    return diff == 0u;
}

static int append_text(char *dst, size_t cap, size_t *pos, const char *src)
{
    if (dst == NULL || pos == NULL || src == NULL) {
        return 0;
    }
    const size_t slen = strlen(src);
    if (*pos + slen + 1u > cap) {
        return 0;
    }
    memcpy(dst + *pos, src, slen);
    *pos += slen;
    dst[*pos] = '\0';
    return 1;
}

static int append_hex_bytes(char *dst, size_t cap, size_t *pos,
                            const uint8_t *bytes, size_t nbytes)
{
    static const char hex_upper[16] = {
        '0', '1', '2', '3', '4', '5', '6', '7',
        '8', '9', 'A', 'B', 'C', 'D', 'E', 'F'
    };
    if (dst == NULL || pos == NULL || bytes == NULL) {
        return 0;
    }
    if (*pos + 2u * nbytes + 1u > cap) {
        return 0;
    }
    for (size_t i = 0u; i < nbytes; ++i) {
        dst[*pos] = hex_upper[bytes[i] >> 4u];
        dst[*pos + 1u] = hex_upper[bytes[i] & 0x0fu];
        *pos += 2u;
    }
    dst[*pos] = '\0';
    return 1;
}

static size_t bounded_cstr_len(const char *s, size_t max_len)
{
    size_t len = 0u;
    while (len < max_len && s[len] != '\0') {
        ++len;
    }
    return len;
}

static enum vos_ts_status check_trusted_gate(const struct vos_ts_trusted_path *tp)
{
    if (tp == NULL) {
        return VOS_TS_ERR_INVALID;
    }
    if (tp->app_originated != 0u) {
        return VOS_TS_ERR_APP_SPOOF;
    }
    if (tp->unlocked == 0u) {
        return VOS_TS_ERR_LOCKED;
    }
    if (tp->hw_latch_active == 0u) {
        return VOS_TS_ERR_LATCH;
    }
    if (tp->primary_cred_verified == 0u) {
        return VOS_TS_ERR_AUTH;
    }
    return VOS_TS_OK;
}

static int flow_is_valid(enum vos_ts_flow flow)
{
    return flow == VOS_TS_FLOW_BACKUP_EXPORT ||
           flow == VOS_TS_FLOW_USER_RESTORE ||
           flow == VOS_TS_FLOW_DEVICE_MIGRATION;
}

static int caveats_ok_for_flow(enum vos_ts_flow flow,
                               const struct vos_ts_caveats *cav,
                               uint32_t needs_discard)
{
    if (cav == NULL || cav->ack_not_rollback == 0u) {
        return 0;
    }
    switch (flow) {
    case VOS_TS_FLOW_BACKUP_EXPORT:
        return cav->ack_off_device_trade != 0u;
    case VOS_TS_FLOW_USER_RESTORE:
        if (cav->ack_surrendered_freshness == 0u) {
            return 0;
        }
        if (needs_discard != 0u && cav->ack_discard_loss == 0u) {
            return 0;
        }
        return 1;
    case VOS_TS_FLOW_DEVICE_MIGRATION:
        return cav->ack_migration_roots != 0u;
    default:
        return 0;
    }
}

static void compute_witness_mac(const struct vos_ts_trusted_path *tp,
                                const struct vos_ts_consent_witness *w,
                                uint8_t out_mac[VOS_TS_HMAC_BYTES])
{
    static const uint8_t tag[8] = { 'V', 'O', 'S', 'T', 'S', 'C', 'W', '1' };
    uint8_t msg[76u + VOS_CRYPTO_DIGEST_BYTES];
    memcpy(msg, tag, 8u);
    put_be32(msg + 8u, w->trusted_issued);
    put_be64(msg + 12u, w->seq);
    put_be64(msg + 20u, w->epoch);
    put_be32(msg + 28u, (uint32_t)w->flow);
    put_be32(msg + 32u, w->unlocked_profile);
    put_be64(msg + 36u, w->generation);
    put_be64(msg + 44u, w->object_or_snapshot_id);
    put_be64(msg + 52u, w->destination_id);
    put_be64(msg + 60u, w->plan_id);
    put_be32(msg + 68u, w->allow_discard);
    put_be32(msg + 72u, w->allow_profile_mapping);
    memcpy(msg + 76u, w->root_digest, VOS_CRYPTO_DIGEST_BYTES);
    (void)vos_hmac_sha256(tp->hmac_key, sizeof(tp->hmac_key),
                          msg, sizeof(msg), out_mac);
    vos_ts_wipe(msg, sizeof(msg));
}

static int is_seq_spent(const struct vos_ts_trusted_path *tp, uint64_t seq)
{
    if (seq == 0u || seq <= tp->min_valid_seq || seq > tp->next_witness_seq) {
        return 1;
    }
    for (uint32_t i = 0u; i < tp->spent_count; ++i) {
        if (tp->spent_seqs[i] == seq) {
            return 1;
        }
    }
    return 0;
}

static void record_seq_spent(struct vos_ts_trusted_path *tp, uint64_t seq)
{
    if (tp->spent_count < VOS_TS_MAX_SPENT_WITNESSES) {
        tp->spent_seqs[tp->spent_count] = seq;
        ++tp->spent_count;
    } else {
        /* Advance floor so bounded ledger never loses replay protection. */
        tp->min_valid_seq = seq;
    }
}

void vos_ts_wipe(void *ptr, size_t len)
{
    if (ptr == NULL || len == 0u) {
        return;
    }
    volatile uint8_t *p = (volatile uint8_t *)ptr;
    for (size_t i = 0u; i < len; ++i) {
        p[i] = 0u;
    }
}

enum vos_ts_status vos_ts_format_recovery_display(
    const uint8_t key[VOS_BK_KEY_BYTES],
    char out_display[VOS_TS_DISPLAY_SECRET_CHARS + 1u])
{
    if (key == NULL || out_display == NULL) {
        return VOS_TS_ERR_INVALID;
    }
    char raw_hex[VOS_BK_RECOVERY_HEX_CHARS + 1u];
    const enum vos_bk_status st = vos_bk_encode_recovery_secret(key, raw_hex);
    if (st != VOS_BK_OK) {
        vos_ts_wipe(raw_hex, sizeof(raw_hex));
        vos_ts_wipe(out_display, VOS_TS_DISPLAY_SECRET_CHARS + 1u);
        return VOS_TS_ERR_HEX_FORMAT;
    }
    size_t out_pos = 0u;
    for (size_t g = 0u; g < 16u; ++g) {
        if (g > 0u) {
            out_display[out_pos++] = ' ';
        }
        for (size_t k = 0u; k < 4u; ++k) {
            out_display[out_pos++] = raw_hex[g * 4u + k];
        }
    }
    out_display[out_pos] = '\0';
    vos_ts_wipe(raw_hex, sizeof(raw_hex));
    return VOS_TS_OK;
}

void vos_ts_trusted_path_init(struct vos_ts_trusted_path *tp,
                              uint32_t unlocked_profile,
                              uint64_t device_generation,
                              const uint8_t hmac_key[VOS_CRYPTO_KEY_BYTES_256])
{
    if (tp == NULL) {
        return;
    }
    memset(tp, 0, sizeof(*tp));
    tp->epoch = 1u;
    tp->unlocked_profile = unlocked_profile;
    tp->device_generation = device_generation;
    if (hmac_key != NULL) {
        memcpy(tp->hmac_key, hmac_key, VOS_CRYPTO_KEY_BYTES_256);
    }
}

void vos_ts_trusted_path_set_gate(struct vos_ts_trusted_path *tp,
                                  uint32_t unlocked,
                                  uint32_t hw_latch_active,
                                  uint32_t primary_cred_verified,
                                  uint32_t receiver_cred_verified,
                                  uint32_t app_originated)
{
    if (tp == NULL) {
        return;
    }
    tp->unlocked = unlocked;
    tp->hw_latch_active = hw_latch_active;
    tp->primary_cred_verified = primary_cred_verified;
    tp->receiver_cred_verified = receiver_cred_verified;
    tp->app_originated = app_originated;
}

void vos_ts_trusted_path_lock(struct vos_ts_trusted_path *tp)
{
    if (tp == NULL) {
        return;
    }
    tp->unlocked = 0u;
    tp->hw_latch_active = 0u;
    tp->primary_cred_verified = 0u;
    tp->receiver_cred_verified = 0u;
    ++tp->epoch;
    tp->min_valid_seq = tp->next_witness_seq;
}

void vos_ts_trusted_path_restart(struct vos_ts_trusted_path *tp,
                                 uint32_t unlocked_profile,
                                 uint64_t device_generation)
{
    if (tp == NULL) {
        return;
    }
    vos_ts_trusted_path_lock(tp);
    tp->unlocked_profile = unlocked_profile;
    tp->device_generation = device_generation;
}

void vos_ts_trusted_path_set_profile(struct vos_ts_trusted_path *tp,
                                     uint32_t new_profile)
{
    if (tp == NULL) {
        return;
    }
    tp->unlocked_profile = new_profile;
}

void vos_ts_trusted_path_set_generation(struct vos_ts_trusted_path *tp,
                                        uint64_t new_generation)
{
    if (tp == NULL) {
        return;
    }
    tp->device_generation = new_generation;
}

enum vos_ts_status vos_ts_compute_root_digest(
    const struct vos_ts_quoted_root *roots,
    uint32_t root_count,
    uint8_t digest_out[VOS_CRYPTO_DIGEST_BYTES])
{
    static const uint8_t domain[12] = {
        'V', 'O', 'S', 'T', 'S', '-', 'R', 'O', 'O', 'T', 'S', '\0'
    };
    if (digest_out == NULL) {
        return VOS_TS_ERR_INVALID;
    }
    if (root_count == 0u) {
        memset(digest_out, 0, VOS_CRYPTO_DIGEST_BYTES);
        return VOS_TS_OK;
    }
    if (roots == NULL || root_count > VOS_TS_MAX_ROOTS) {
        return VOS_TS_ERR_ROOT_TRUNCATED;
    }
    uint8_t buf[12u + 4u + VOS_TS_MAX_ROOTS * (VOS_TS_ROOT_FP_BYTES + VOS_TS_ROOT_LABEL_MAX)];
    size_t pos = 0u;
    memcpy(buf + pos, domain, sizeof(domain));
    pos += sizeof(domain);
    put_be32(buf + pos, root_count);
    pos += 4u;
    for (uint32_t i = 0u; i < root_count; ++i) {
        memcpy(buf + pos, roots[i].fingerprint, VOS_TS_ROOT_FP_BYTES);
        pos += VOS_TS_ROOT_FP_BYTES;
        const size_t llen = bounded_cstr_len(roots[i].label, VOS_TS_ROOT_LABEL_MAX);
        memset(buf + pos, 0, VOS_TS_ROOT_LABEL_MAX);
        memcpy(buf + pos, roots[i].label, llen);
        pos += VOS_TS_ROOT_LABEL_MAX;
    }
    (void)vos_sha256(buf, pos, digest_out);
    vos_ts_wipe(buf, sizeof(buf));
    return VOS_TS_OK;
}

enum vos_ts_status vos_ts_issue_witness(
    struct vos_ts_trusted_path *tp,
    enum vos_ts_flow flow,
    const struct vos_ts_caveats *cav,
    uint64_t obj_or_snap_id,
    uint64_t destination_id,
    uint64_t plan_id,
    uint32_t needs_discard,
    uint32_t allow_profile_mapping,
    const uint8_t root_digest[VOS_CRYPTO_DIGEST_BYTES],
    struct vos_ts_consent_witness *out_witness)
{
    if (tp == NULL || cav == NULL || out_witness == NULL) {
        return VOS_TS_ERR_INVALID;
    }
    const enum vos_ts_status gate = check_trusted_gate(tp);
    if (gate != VOS_TS_OK) {
        return gate;
    }
    if (!flow_is_valid(flow)) {
        return VOS_TS_ERR_BINDING;
    }
    if (flow == VOS_TS_FLOW_DEVICE_MIGRATION && tp->receiver_cred_verified == 0u) {
        return VOS_TS_ERR_AUTH;
    }
    if (!caveats_ok_for_flow(flow, cav, needs_discard)) {
        return VOS_TS_ERR_CAVEAT;
    }

    memset(out_witness, 0, sizeof(*out_witness));
    ++tp->next_witness_seq;
    out_witness->trusted_issued = 1u;
    out_witness->consumed = 0u;
    out_witness->seq = tp->next_witness_seq;
    out_witness->epoch = tp->epoch;
    out_witness->flow = flow;
    out_witness->unlocked_profile = tp->unlocked_profile;
    out_witness->generation = tp->device_generation;
    out_witness->object_or_snapshot_id = obj_or_snap_id;
    out_witness->destination_id = destination_id;
    out_witness->plan_id = plan_id;
    out_witness->allow_discard = (needs_discard != 0u) ? 1u : 0u;
    out_witness->allow_profile_mapping = (allow_profile_mapping != 0u) ? 1u : 0u;
    if (root_digest != NULL) {
        memcpy(out_witness->root_digest, root_digest, VOS_CRYPTO_DIGEST_BYTES);
    }
    compute_witness_mac(tp, out_witness, out_witness->mac);
    return VOS_TS_OK;
}

enum vos_ts_status vos_ts_verify_and_consume_witness(
    struct vos_ts_trusted_path *tp,
    struct vos_ts_consent_witness *witness,
    enum vos_ts_flow expected_flow,
    uint64_t expected_obj_id,
    uint64_t expected_dst_id,
    uint64_t expected_plan_id,
    uint32_t expected_needs_discard,
    const uint8_t expected_root_digest[VOS_CRYPTO_DIGEST_BYTES])
{
    if (tp == NULL || witness == NULL) {
        return VOS_TS_ERR_INVALID;
    }
    const enum vos_ts_status gate = check_trusted_gate(tp);
    if (gate != VOS_TS_OK) {
        return gate;
    }
    if (witness->trusted_issued != 1u) {
        return VOS_TS_ERR_APP_SPOOF;
    }
    if (witness->consumed != 0u || is_seq_spent(tp, witness->seq)) {
        return VOS_TS_ERR_REPLAY;
    }
    if (witness->epoch != tp->epoch) {
        return VOS_TS_ERR_EXPIRED;
    }
    if (!flow_is_valid(expected_flow) || witness->flow != expected_flow) {
        return VOS_TS_ERR_BINDING;
    }
    if (expected_flow == VOS_TS_FLOW_DEVICE_MIGRATION &&
        tp->receiver_cred_verified == 0u) {
        return VOS_TS_ERR_AUTH;
    }
    if (witness->unlocked_profile != tp->unlocked_profile ||
        witness->generation != tp->device_generation ||
        witness->object_or_snapshot_id != expected_obj_id ||
        witness->destination_id != expected_dst_id ||
        witness->plan_id != expected_plan_id ||
        witness->allow_discard != ((expected_needs_discard != 0u) ? 1u : 0u)) {
        return VOS_TS_ERR_BINDING;
    }

    uint8_t zero_digest[VOS_CRYPTO_DIGEST_BYTES];
    memset(zero_digest, 0, sizeof(zero_digest));
    const uint8_t *exp_roots =
        (expected_root_digest != NULL) ? expected_root_digest : zero_digest;
    if (!ct_equal(witness->root_digest, exp_roots, VOS_CRYPTO_DIGEST_BYTES)) {
        return VOS_TS_ERR_ROOT_MISMATCH;
    }

    uint8_t expected_mac[VOS_TS_HMAC_BYTES];
    compute_witness_mac(tp, witness, expected_mac);
    const int mac_ok = ct_equal(witness->mac, expected_mac, VOS_TS_HMAC_BYTES);
    vos_ts_wipe(expected_mac, sizeof(expected_mac));
    if (!mac_ok) {
        return VOS_TS_ERR_HMAC;
    }

    witness->consumed = 1u;
    record_seq_spent(tp, witness->seq);
    return VOS_TS_OK;
}

void vos_ts_witness_to_bk_consent(const struct vos_ts_trusted_path *tp,
                                  const struct vos_ts_consent_witness *witness,
                                  uint32_t target_profile,
                                  struct vos_bk_consent *out_consent)
{
    if (out_consent == NULL) {
        return;
    }
    memset(out_consent, 0, sizeof(*out_consent));
    if (tp == NULL || witness == NULL || witness->trusted_issued != 1u ||
        witness->consumed != 0u || check_trusted_gate(tp) != VOS_TS_OK ||
        witness->epoch != tp->epoch ||
        witness->unlocked_profile != tp->unlocked_profile ||
        witness->generation != tp->device_generation) {
        return;
    }
    if (witness->flow == VOS_TS_FLOW_BACKUP_EXPORT) {
        out_consent->op = VOS_BK_OP_EXPORT;
    } else if (witness->flow == VOS_TS_FLOW_USER_RESTORE ||
               witness->flow == VOS_TS_FLOW_DEVICE_MIGRATION) {
        out_consent->op = VOS_BK_OP_RESTORE;
    } else {
        return;
    }
    out_consent->valid = 1u;
    out_consent->consumed = 0u;
    out_consent->unlocked = tp->unlocked;
    out_consent->credential_verified = tp->primary_cred_verified;
    out_consent->source_profile = witness->unlocked_profile;
    out_consent->target_profile = target_profile;
    out_consent->allow_profile_mapping = witness->allow_profile_mapping;
    out_consent->allow_discard = witness->allow_discard;
}

void vos_ts_export_init(struct vos_ts_export_screen *scr)
{
    if (scr == NULL) {
        return;
    }
    vos_ts_wipe(scr, sizeof(*scr));
    scr->phase = VOS_TS_EXP_IDLE;
}

enum vos_ts_status vos_ts_export_authorize(
    struct vos_ts_export_screen *scr,
    struct vos_ts_trusted_path *tp,
    const struct vos_ts_caveats *cav,
    uint64_t snapshot_id,
    uint64_t destination_id,
    uint64_t plan_id)
{
    if (scr == NULL || tp == NULL || cav == NULL) {
        return VOS_TS_ERR_INVALID;
    }
    if (scr->phase != VOS_TS_EXP_IDLE) {
        return VOS_TS_ERR_STATE;
    }
    if (scr->displayed_once != 0u) {
        return VOS_TS_ERR_REDISPLAY;
    }
    const enum vos_ts_status st = vos_ts_issue_witness(
        tp, VOS_TS_FLOW_BACKUP_EXPORT, cav,
        snapshot_id, destination_id, plan_id, 0u, 0u, NULL, &scr->witness);
    if (st != VOS_TS_OK) {
        return st;
    }
    size_t pos = 0u;
    scr->warning_banner[0] = '\0';
    (void)append_text(
        scr->warning_banner, sizeof(scr->warning_banner), &pos,
        "Backup Export (not system rollback): R-17-054a off-device trade - "
        "duress erase, lock, and rate limiter do not guard off-device copies.");
    scr->snapshot_id = snapshot_id;
    scr->destination_id = destination_id;
    scr->plan_id = plan_id;
    scr->phase = VOS_TS_EXP_AUTHORIZED;
    return VOS_TS_OK;
}

enum vos_ts_status vos_ts_export_show_secret_once(
    struct vos_ts_export_screen *scr,
    const struct vos_ts_trusted_path *tp,
    const uint8_t key[VOS_BK_KEY_BYTES])
{
    if (scr == NULL || tp == NULL || key == NULL) {
        return VOS_TS_ERR_INVALID;
    }
    if (scr->displayed_once != 0u) {
        return VOS_TS_ERR_REDISPLAY;
    }
    if (scr->phase != VOS_TS_EXP_AUTHORIZED) {
        return VOS_TS_ERR_STATE;
    }
    const enum vos_ts_status gate = check_trusted_gate(tp);
    if (gate != VOS_TS_OK) {
        return gate;
    }
    const enum vos_ts_status fmt = vos_ts_format_recovery_display(key, scr->display_buf);
    if (fmt != VOS_TS_OK) {
        vos_ts_wipe(scr->display_buf, sizeof(scr->display_buf));
        return fmt;
    }
    memcpy(scr->secret_buf, key, VOS_BK_KEY_BYTES);
    scr->displayed_once = 1u;
    scr->phase = VOS_TS_EXP_DISPLAYING;
    return VOS_TS_OK;
}

enum vos_ts_status vos_ts_export_confirm_recorded(
    struct vos_ts_export_screen *scr,
    struct vos_ts_trusted_path *tp,
    uint64_t snapshot_id,
    uint64_t destination_id,
    uint64_t plan_id)
{
    if (scr == NULL || tp == NULL) {
        return VOS_TS_ERR_INVALID;
    }
    if (scr->phase != VOS_TS_EXP_DISPLAYING) {
        return VOS_TS_ERR_STATE;
    }
    const enum vos_ts_status st = vos_ts_verify_and_consume_witness(
        tp, &scr->witness, VOS_TS_FLOW_BACKUP_EXPORT,
        snapshot_id, destination_id, plan_id, 0u, NULL);
    vos_ts_wipe(scr->secret_buf, sizeof(scr->secret_buf));
    vos_ts_wipe(scr->display_buf, sizeof(scr->display_buf));
    if (st != VOS_TS_OK) {
        vos_ts_wipe(&scr->witness, sizeof(scr->witness));
        scr->phase = VOS_TS_EXP_CLEARED;
        return st;
    }
    scr->confirmed = 1u;
    vos_ts_wipe(&scr->witness, sizeof(scr->witness));
    scr->phase = VOS_TS_EXP_CONFIRMED;
    return VOS_TS_OK;
}

void vos_ts_export_abort(struct vos_ts_export_screen *scr,
                         enum vos_ts_exit_reason reason)
{
    (void)reason;
    if (scr == NULL) {
        return;
    }
    vos_ts_wipe(scr->secret_buf, sizeof(scr->secret_buf));
    vos_ts_wipe(scr->display_buf, sizeof(scr->display_buf));
    vos_ts_wipe(&scr->witness, sizeof(scr->witness));
    scr->confirmed = 0u;
    scr->phase = VOS_TS_EXP_CLEARED;
}

void vos_ts_restore_init(struct vos_ts_restore_screen *scr)
{
    if (scr == NULL) {
        return;
    }
    vos_ts_wipe(scr, sizeof(*scr));
    scr->phase = VOS_TS_RST_IDLE;
}

enum vos_ts_status vos_ts_restore_authorize(
    struct vos_ts_restore_screen *scr,
    struct vos_ts_trusted_path *tp,
    const struct vos_ts_caveats *cav,
    uint64_t object_id,
    uint64_t target_profile_id,
    uint64_t plan_id,
    uint32_t needs_discard,
    uint32_t allow_profile_mapping)
{
    if (scr == NULL || tp == NULL || cav == NULL) {
        return VOS_TS_ERR_INVALID;
    }
    if (scr->phase != VOS_TS_RST_IDLE) {
        return VOS_TS_ERR_STATE;
    }
    const enum vos_ts_status st = vos_ts_issue_witness(
        tp, VOS_TS_FLOW_USER_RESTORE, cav,
        object_id, target_profile_id, plan_id,
        needs_discard, allow_profile_mapping, NULL, &scr->witness);
    if (st != VOS_TS_OK) {
        return st;
    }
    size_t pos = 0u;
    scr->warning_banner[0] = '\0';
    (void)append_text(
        scr->warning_banner, sizeof(scr->warning_banner), &pos,
        "User-Data Restore (not system-generation rollback): "
        "rollbackable edits return to checkpoint and surrender freshness.");
    if (needs_discard != 0u) {
        (void)append_text(
            scr->warning_banner, sizeof(scr->warning_banner), &pos,
            " Explicit discard: listed obsolete-schema data will be lost.");
    }
    scr->object_id = object_id;
    scr->target_profile_id = target_profile_id;
    scr->plan_id = plan_id;
    scr->needs_discard = (needs_discard != 0u) ? 1u : 0u;
    scr->allow_profile_mapping = (allow_profile_mapping != 0u) ? 1u : 0u;
    scr->phase = VOS_TS_RST_AUTHORIZED;
    return VOS_TS_OK;
}

static int entry_is_canonical_hex_chars(const char *entry, size_t entry_len)
{
    if (entry == NULL || entry_len != VOS_BK_RECOVERY_HEX_CHARS) {
        return 0;
    }
    for (size_t i = 0u; i < entry_len; ++i) {
        const char c = entry[i];
        const int is_digit = (c >= '0' && c <= '9');
        const int is_upper = (c >= 'A' && c <= 'F');
        if (!is_digit && !is_upper) {
            return 0;
        }
    }
    return 1;
}

enum vos_ts_status vos_ts_restore_enter_recovery_secret(
    struct vos_ts_restore_screen *scr,
    const struct vos_ts_trusted_path *tp,
    const char *entry,
    size_t entry_len)
{
    if (scr == NULL || tp == NULL || entry == NULL) {
        return VOS_TS_ERR_INVALID;
    }
    if (scr->phase != VOS_TS_RST_AUTHORIZED) {
        return VOS_TS_ERR_STATE;
    }
    const enum vos_ts_status gate = check_trusted_gate(tp);
    if (gate != VOS_TS_OK) {
        return gate;
    }
    if (!entry_is_canonical_hex_chars(entry, entry_len)) {
        vos_ts_wipe(scr->recovered_key, sizeof(scr->recovered_key));
        return VOS_TS_ERR_HEX_FORMAT;
    }
    if (vos_bk_decode_recovery_secret(entry, entry_len, scr->recovered_key) != VOS_BK_OK) {
        vos_ts_wipe(scr->recovered_key, sizeof(scr->recovered_key));
        return VOS_TS_ERR_HEX_FORMAT;
    }
    scr->phase = VOS_TS_RST_KEY_ENTERED;
    return VOS_TS_OK;
}

enum vos_ts_status vos_ts_restore_consume_and_commit(
    struct vos_ts_restore_screen *scr,
    struct vos_ts_trusted_path *tp,
    uint64_t object_id,
    uint64_t target_profile_id,
    uint64_t plan_id,
    uint8_t key_out[VOS_BK_KEY_BYTES])
{
    if (scr == NULL || tp == NULL || key_out == NULL) {
        return VOS_TS_ERR_INVALID;
    }
    if (scr->phase != VOS_TS_RST_KEY_ENTERED) {
        return VOS_TS_ERR_STATE;
    }
    const enum vos_ts_status st = vos_ts_verify_and_consume_witness(
        tp, &scr->witness, VOS_TS_FLOW_USER_RESTORE,
        object_id, target_profile_id, plan_id, scr->needs_discard, NULL);
    if (st != VOS_TS_OK) {
        vos_ts_wipe(scr->recovered_key, sizeof(scr->recovered_key));
        vos_ts_wipe(&scr->witness, sizeof(scr->witness));
        vos_ts_wipe(key_out, VOS_BK_KEY_BYTES);
        scr->phase = VOS_TS_RST_CLEARED;
        return st;
    }
    memcpy(key_out, scr->recovered_key, VOS_BK_KEY_BYTES);
    vos_ts_wipe(scr->recovered_key, sizeof(scr->recovered_key));
    vos_ts_wipe(&scr->witness, sizeof(scr->witness));
    scr->phase = VOS_TS_RST_COMMITTED;
    return VOS_TS_OK;
}

void vos_ts_restore_abort(struct vos_ts_restore_screen *scr,
                          enum vos_ts_exit_reason reason)
{
    (void)reason;
    if (scr == NULL) {
        return;
    }
    vos_ts_wipe(scr->recovered_key, sizeof(scr->recovered_key));
    vos_ts_wipe(&scr->witness, sizeof(scr->witness));
    scr->phase = VOS_TS_RST_CLEARED;
}

void vos_ts_migration_init(struct vos_ts_migration_screen *scr)
{
    if (scr == NULL) {
        return;
    }
    vos_ts_wipe(scr, sizeof(*scr));
    scr->phase = VOS_TS_MIG_IDLE;
}

enum vos_ts_status vos_ts_migration_present_roots(
    struct vos_ts_migration_screen *scr,
    const struct vos_ts_trusted_path *tp,
    uint32_t mutually_appraised,
    uint64_t receiver_gen,
    uint32_t receiving_profile,
    uint64_t channel_id,
    uint64_t plan_id,
    const struct vos_ts_quoted_root *roots,
    uint32_t root_count)
{
    if (scr == NULL || tp == NULL) {
        return VOS_TS_ERR_INVALID;
    }
    if (scr->phase != VOS_TS_MIG_IDLE) {
        return VOS_TS_ERR_STATE;
    }
    const enum vos_ts_status gate = check_trusted_gate(tp);
    if (gate != VOS_TS_OK) {
        return gate;
    }
    if (tp->receiver_cred_verified == 0u) {
        return VOS_TS_ERR_AUTH;
    }
    if (mutually_appraised == 0u) {
        return VOS_TS_ERR_NOT_APPRAISED;
    }
    if (roots == NULL || root_count == 0u || root_count > VOS_TS_MAX_ROOTS) {
        return VOS_TS_ERR_ROOT_TRUNCATED;
    }

    size_t pos = 0u;
    scr->rendered_roots[0] = '\0';
    for (uint32_t i = 0u; i < root_count; ++i) {
        if (i > 0u) {
            if (!append_text(scr->rendered_roots, sizeof(scr->rendered_roots), &pos, "; ")) {
                vos_ts_migration_abort(scr, VOS_TS_EXIT_FAULT);
                return VOS_TS_ERR_ROOT_TRUNCATED;
            }
        }
        const size_t llen = bounded_cstr_len(roots[i].label, VOS_TS_ROOT_LABEL_MAX);
        if (llen == 0u || llen == VOS_TS_ROOT_LABEL_MAX) {
            vos_ts_migration_abort(scr, VOS_TS_EXIT_FAULT);
            return VOS_TS_ERR_INVALID;
        }
        if (!append_text(scr->rendered_roots, sizeof(scr->rendered_roots), &pos, roots[i].label) ||
            !append_text(scr->rendered_roots, sizeof(scr->rendered_roots), &pos, ":") ||
            !append_hex_bytes(scr->rendered_roots, sizeof(scr->rendered_roots), &pos,
                              roots[i].fingerprint, VOS_TS_ROOT_FP_BYTES)) {
            vos_ts_migration_abort(scr, VOS_TS_EXIT_FAULT);
            return VOS_TS_ERR_ROOT_TRUNCATED;
        }
    }

    const enum vos_ts_status dst = vos_ts_compute_root_digest(
        roots, root_count, scr->root_digest);
    if (dst != VOS_TS_OK) {
        vos_ts_migration_abort(scr, VOS_TS_EXIT_FAULT);
        return dst;
    }

    scr->mutually_appraised = 1u;
    scr->receiver_gen = receiver_gen;
    scr->receiving_profile = receiving_profile;
    scr->channel_id = channel_id;
    scr->plan_id = plan_id;
    scr->root_count = root_count;
    for (uint32_t i = 0u; i < root_count; ++i) {
        scr->roots[i] = roots[i];
    }

    size_t bpos = 0u;
    scr->warning_banner[0] = '\0';
    (void)append_text(
        scr->warning_banner, sizeof(scr->warning_banner), &bpos,
        "Device Migration (not system rollback): confirm complete quoted receiver roots.");
    scr->phase = VOS_TS_MIG_ROOTS_SHOWN;
    return VOS_TS_OK;
}

enum vos_ts_status vos_ts_migration_confirm(
    struct vos_ts_migration_screen *scr,
    struct vos_ts_trusted_path *tp,
    const struct vos_ts_caveats *cav,
    const struct vos_ts_quoted_root *confirmed_roots,
    uint32_t confirmed_count,
    uint64_t channel_id,
    uint64_t plan_id,
    struct vos_ts_consent_witness *out_witness)
{
    if (scr == NULL || tp == NULL || cav == NULL ||
        confirmed_roots == NULL || out_witness == NULL) {
        return VOS_TS_ERR_INVALID;
    }
    if (scr->phase != VOS_TS_MIG_ROOTS_SHOWN || scr->mutually_appraised == 0u) {
        return VOS_TS_ERR_NOT_APPRAISED;
    }
    if (channel_id != scr->channel_id || plan_id != scr->plan_id) {
        return VOS_TS_ERR_BINDING;
    }
    if (confirmed_count != scr->root_count) {
        return VOS_TS_ERR_ROOT_MISMATCH;
    }
    for (uint32_t i = 0u; i < confirmed_count; ++i) {
        if (!ct_equal(confirmed_roots[i].fingerprint,
                      scr->roots[i].fingerprint, VOS_TS_ROOT_FP_BYTES)) {
            return VOS_TS_ERR_ROOT_MISMATCH;
        }
        const size_t l1 = bounded_cstr_len(confirmed_roots[i].label, VOS_TS_ROOT_LABEL_MAX);
        const size_t l2 = bounded_cstr_len(scr->roots[i].label, VOS_TS_ROOT_LABEL_MAX);
        if (l1 != l2 || memcmp(confirmed_roots[i].label, scr->roots[i].label, l1) != 0) {
            return VOS_TS_ERR_ROOT_MISMATCH;
        }
    }
    return vos_ts_issue_witness(
        tp, VOS_TS_FLOW_DEVICE_MIGRATION, cav,
        scr->receiver_gen, scr->channel_id, scr->plan_id,
        0u, 0u, scr->root_digest, out_witness);
}

enum vos_ts_status vos_ts_migration_consume_transfer(
    struct vos_ts_migration_screen *scr,
    struct vos_ts_trusted_path *tp,
    struct vos_ts_consent_witness *witness,
    uint64_t receiver_gen,
    uint64_t channel_id,
    uint64_t plan_id)
{
    if (scr == NULL || tp == NULL || witness == NULL) {
        return VOS_TS_ERR_INVALID;
    }
    if (scr->phase != VOS_TS_MIG_ROOTS_SHOWN || scr->mutually_appraised == 0u) {
        return VOS_TS_ERR_NOT_APPRAISED;
    }
    const enum vos_ts_status st = vos_ts_verify_and_consume_witness(
        tp, witness, VOS_TS_FLOW_DEVICE_MIGRATION,
        receiver_gen, channel_id, plan_id, 0u, scr->root_digest);
    if (st != VOS_TS_OK) {
        vos_ts_migration_abort(scr, VOS_TS_EXIT_FAULT);
        return st;
    }
    scr->phase = VOS_TS_MIG_CONFIRMED;
    return VOS_TS_OK;
}

void vos_ts_migration_abort(struct vos_ts_migration_screen *scr,
                            enum vos_ts_exit_reason reason)
{
    (void)reason;
    if (scr == NULL) {
        return;
    }
    vos_ts_wipe(scr->roots, sizeof(scr->roots));
    vos_ts_wipe(scr->root_digest, sizeof(scr->root_digest));
    vos_ts_wipe(scr->rendered_roots, sizeof(scr->rendered_roots));
    scr->mutually_appraised = 0u;
    scr->root_count = 0u;
    scr->phase = VOS_TS_MIG_CLEARED;
}
