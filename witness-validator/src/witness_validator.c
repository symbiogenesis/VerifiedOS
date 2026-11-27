// SPDX-License-Identifier: Apache-2.0
#include "vos_witness_validator.h"

_Static_assert((unsigned)VOS_WV_DIGEST_BYTES == (unsigned)VOS_CRYPTO_DIGEST_BYTES,
               "digest width must match vos_crypto_core");
_Static_assert((unsigned)VOS_WV_KEY_BYTES == (unsigned)VOS_CRYPTO_KEY_BYTES_256,
               "verification key width must match 256-bit HMAC key");
_Static_assert((unsigned)VOS_WV_MAX_SIGNATURES >= (unsigned)VOS_WV_MAX_WITNESSES,
               "signature capacity must cover maximum witness population");

enum {
    VOS_WV_MAGIC_BYTES = 8u,
    VOS_WV_POLICY_HDR_BYTES = 36u,
    VOS_WV_POLICY_ENTRY_BYTES = 40u,
    VOS_WV_POLICY_BUF_BYTES =
        VOS_WV_POLICY_HDR_BYTES + (VOS_WV_MAX_WITNESSES * VOS_WV_POLICY_ENTRY_BYTES),
    VOS_WV_CHECKPOINT_HDR_BYTES = 12u,
    VOS_WV_CHECKPOINT_BUF_BYTES =
        VOS_WV_CHECKPOINT_HDR_BYTES + (VOS_WV_MAX_CHECKPOINT_ENTRIES * VOS_WV_DIGEST_BYTES),
    VOS_WV_TRANSITION_DIGEST_BUF_BYTES = VOS_WV_MAGIC_BYTES + (3u * VOS_WV_DIGEST_BYTES),
    VOS_WV_SIG_MAC_MSG_BYTES = VOS_WV_SIGNATURE_WIRE_BYTES - VOS_WV_DIGEST_BYTES,
    VOS_WV_REBOOT_MAC_BUF_BYTES =
        VOS_WV_MAGIC_BYTES + (3u * VOS_WV_DIGEST_BYTES) + 4u + VOS_WV_MAX_ASSUMPTIONS_BYTES
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

static int is_zero_bytes(const uint8_t *buf, size_t len)
{
    uint8_t acc = 0u;
    for (size_t i = 0u; i < len; ++i) {
        acc |= buf[i];
    }
    return acc == 0u;
}

static int equal_hashes(const struct vos_wv_hash *a, const struct vos_wv_hash *b)
{
    return equal_bytes_ct(a->bytes, b->bytes, VOS_WV_DIGEST_BYTES);
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

static uint32_t get_le32(const uint8_t *src)
{
    return ((uint32_t)src[0]) |
           ((uint32_t)src[1] << 8u) |
           ((uint32_t)src[2] << 16u) |
           ((uint32_t)src[3] << 24u);
}

static uint64_t get_le64(const uint8_t *src)
{
    uint64_t out = 0u;
    for (uint32_t i = 0u; i < 8u; ++i) {
        out |= ((uint64_t)src[i]) << (8u * i);
    }
    return out;
}

static void write_magic(uint8_t *dst, const char magic[8])
{
    for (size_t i = 0u; i < VOS_WV_MAGIC_BYTES; ++i) {
        dst[i] = (uint8_t)magic[i];
    }
}

static int match_magic(const uint8_t *buf, const char magic[8])
{
    uint8_t diff = 0u;
    for (size_t i = 0u; i < VOS_WV_MAGIC_BYTES; ++i) {
        diff |= (uint8_t)(buf[i] ^ (uint8_t)magic[i]);
    }
    return diff == 0u;
}

static int has_non_whitespace(const uint8_t *buf, size_t len)
{
    for (size_t i = 0u; i < len; ++i) {
        if (buf[i] != (uint8_t)' ' && buf[i] != (uint8_t)'\t' &&
            buf[i] != (uint8_t)'\n' && buf[i] != (uint8_t)'\r') {
            return 1;
        }
    }
    return 0;
}

static int policies_equal(const struct vos_wv_policy *a, const struct vos_wv_policy *b)
{
    if (a == NULL || b == NULL) {
        return 0;
    }
    if (a->trust_scope != b->trust_scope ||
        a->epoch != b->epoch ||
        a->n != b->n ||
        a->k != b->k ||
        a->f != b->f ||
        a->n > VOS_WV_MAX_WITNESSES) {
        return 0;
    }
    for (uint32_t i = 0u; i < a->n; ++i) {
        if (a->witnesses[i].witness_id != b->witnesses[i].witness_id ||
            !equal_bytes_ct(a->witnesses[i].verify_key,
                            b->witnesses[i].verify_key,
                            VOS_WV_KEY_BYTES)) {
            return 0;
        }
    }
    return 1;
}

static int scope_already_seen(const struct vos_wv_client *client, uint64_t trust_scope)
{
    if (client == NULL || client->seen_scope_count > VOS_WV_MAX_SEEN_SCOPES) {
        return 1;
    }
    for (uint32_t i = 0u; i < client->seen_scope_count; ++i) {
        if (client->seen_scopes[i] == trust_scope) {
            return 1;
        }
    }
    return 0;
}

int vos_wv_policy_is_wellformed(const struct vos_wv_policy *policy)
{
    if (policy == NULL) {
        return 0;
    }
    if (policy->trust_scope == 0u) {
        return 0;
    }
    if (policy->n == 0u || policy->n > VOS_WV_MAX_WITNESSES) {
        return 0;
    }
    if (policy->k < 1u || policy->k > policy->n) {
        return 0;
    }
    if (policy->f >= policy->n) {
        return 0;
    }
    for (uint32_t i = 0u; i < policy->n; ++i) {
        if (is_zero_bytes(policy->witnesses[i].verify_key, VOS_WV_KEY_BYTES)) {
            return 0;
        }
        for (uint32_t j = i + 1u; j < policy->n; ++j) {
            if (policy->witnesses[i].witness_id == policy->witnesses[j].witness_id) {
                return 0;
            }
            if (equal_bytes_ct(policy->witnesses[i].verify_key,
                               policy->witnesses[j].verify_key,
                               VOS_WV_KEY_BYTES)) {
                return 0;
            }
        }
    }
    return 1;
}

int vos_wv_policy_is_safe(const struct vos_wv_policy *policy)
{
    if (!vos_wv_policy_is_wellformed(policy)) {
        return 0;
    }
    return ((uint64_t)2u * (uint64_t)policy->k) >
           ((uint64_t)policy->n + (uint64_t)policy->f);
}

int vos_wv_checkpoint_is_wellformed(const struct vos_wv_checkpoint *cp)
{
    if (cp == NULL) {
        return 0;
    }
    return cp->entry_count <= VOS_WV_MAX_CHECKPOINT_ENTRIES;
}

int vos_wv_checkpoint_extends(const struct vos_wv_checkpoint *new_cp,
                              const struct vos_wv_checkpoint *old_cp)
{
    if (!vos_wv_checkpoint_is_wellformed(new_cp) ||
        !vos_wv_checkpoint_is_wellformed(old_cp)) {
        return 0;
    }
    if (old_cp->entry_count > new_cp->entry_count) {
        return 0;
    }
    for (uint32_t i = 0u; i < old_cp->entry_count; ++i) {
        if (!equal_hashes(&new_cp->entries[i], &old_cp->entries[i])) {
            return 0;
        }
    }
    return 1;
}

int vos_wv_checkpoint_contains(const struct vos_wv_checkpoint *cp,
                               const struct vos_wv_hash *entry)
{
    if (!vos_wv_checkpoint_is_wellformed(cp) || entry == NULL) {
        return 0;
    }
    for (uint32_t i = 0u; i < cp->entry_count; ++i) {
        if (equal_hashes(&cp->entries[i], entry)) {
            return 1;
        }
    }
    return 0;
}

int vos_wv_transition_is_continuous(const struct vos_wv_transition *tr)
{
    if (tr == NULL) {
        return 0;
    }
    if (!vos_wv_policy_is_safe(&tr->old_policy) ||
        !vos_wv_policy_is_safe(&tr->new_policy) ||
        !vos_wv_checkpoint_is_wellformed(&tr->anchor)) {
        return 0;
    }
    if (tr->new_policy.trust_scope != tr->old_policy.trust_scope) {
        return 0;
    }
    if (tr->old_policy.epoch == UINT64_MAX ||
        tr->new_policy.epoch != tr->old_policy.epoch + 1u) {
        return 0;
    }
    return 1;
}

enum vos_wv_status vos_wv_policy_digest(const struct vos_wv_policy *policy,
                                        struct vos_wv_hash *out_digest)
{
    uint8_t buf[VOS_WV_POLICY_BUF_BYTES];
    size_t offset = 0u;

    if (policy == NULL || out_digest == NULL) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    if (!vos_wv_policy_is_wellformed(policy)) {
        return VOS_WV_ERR_INVALID_POLICY;
    }

    write_magic(buf, "VOSWTP01");
    put_le64(buf + 8u, policy->trust_scope);
    put_le64(buf + 16u, policy->epoch);
    put_le32(buf + 24u, policy->n);
    put_le32(buf + 28u, policy->k);
    put_le32(buf + 32u, policy->f);
    offset = VOS_WV_POLICY_HDR_BYTES;

    for (uint32_t i = 0u; i < policy->n; ++i) {
        put_le64(buf + offset, policy->witnesses[i].witness_id);
        copy_bytes(buf + offset + 8u,
                   policy->witnesses[i].verify_key,
                   VOS_WV_KEY_BYTES);
        offset += VOS_WV_POLICY_ENTRY_BYTES;
    }

    if (vos_sha256(buf, offset, out_digest->bytes) != 1) {
        return VOS_WV_ERR_CRYPTO;
    }
    return VOS_WV_OK;
}

enum vos_wv_status vos_wv_checkpoint_digest(const struct vos_wv_checkpoint *cp,
                                            struct vos_wv_hash *out_digest)
{
    uint8_t buf[VOS_WV_CHECKPOINT_BUF_BYTES];
    size_t offset = 0u;

    if (cp == NULL || out_digest == NULL) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    if (!vos_wv_checkpoint_is_wellformed(cp)) {
        return VOS_WV_ERR_OVER_LIMIT;
    }

    write_magic(buf, "VOSWTC01");
    put_le32(buf + 8u, cp->entry_count);
    offset = VOS_WV_CHECKPOINT_HDR_BYTES;

    for (uint32_t i = 0u; i < cp->entry_count; ++i) {
        copy_bytes(buf + offset, cp->entries[i].bytes, VOS_WV_DIGEST_BYTES);
        offset += VOS_WV_DIGEST_BYTES;
    }

    if (vos_sha256(buf, offset, out_digest->bytes) != 1) {
        return VOS_WV_ERR_CRYPTO;
    }
    return VOS_WV_OK;
}

enum vos_wv_status vos_wv_transition_digest(const struct vos_wv_transition *tr,
                                            struct vos_wv_hash *out_digest)
{
    uint8_t buf[VOS_WV_TRANSITION_DIGEST_BUF_BYTES];
    struct vos_wv_hash old_dig;
    struct vos_wv_hash new_dig;
    struct vos_wv_hash anchor_dig;
    enum vos_wv_status st;

    if (tr == NULL || out_digest == NULL) {
        return VOS_WV_ERR_INVALID_ARG;
    }

    st = vos_wv_policy_digest(&tr->old_policy, &old_dig);
    if (st != VOS_WV_OK) {
        return st;
    }
    st = vos_wv_policy_digest(&tr->new_policy, &new_dig);
    if (st != VOS_WV_OK) {
        return st;
    }
    st = vos_wv_checkpoint_digest(&tr->anchor, &anchor_dig);
    if (st != VOS_WV_OK) {
        return st;
    }

    write_magic(buf, "VOSWTT01");
    copy_bytes(buf + 8u, old_dig.bytes, VOS_WV_DIGEST_BYTES);
    copy_bytes(buf + 8u + VOS_WV_DIGEST_BYTES, new_dig.bytes, VOS_WV_DIGEST_BYTES);
    copy_bytes(buf + 8u + (2u * VOS_WV_DIGEST_BYTES),
               anchor_dig.bytes,
               VOS_WV_DIGEST_BYTES);

    if (vos_sha256(buf, sizeof(buf), out_digest->bytes) != 1) {
        return VOS_WV_ERR_CRYPTO;
    }
    return VOS_WV_OK;
}

enum vos_wv_status vos_wv_parse_policy(const uint8_t *buf,
                                       size_t len,
                                       struct vos_wv_policy *out)
{
    struct vos_wv_policy parsed;
    size_t offset = 0u;
    size_t entries_bytes = 0u;

    if (buf == NULL || out == NULL) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    if (len < VOS_WV_POLICY_HDR_BYTES) {
        return VOS_WV_ERR_MALFORMED_WIRE;
    }
    if (!match_magic(buf, "VOSWTP01")) {
        return VOS_WV_ERR_MALFORMED_WIRE;
    }

    zero_bytes((uint8_t *)&parsed, sizeof(parsed));
    parsed.trust_scope = get_le64(buf + 8u);
    parsed.epoch = get_le64(buf + 16u);
    parsed.n = get_le32(buf + 24u);
    parsed.k = get_le32(buf + 28u);
    parsed.f = get_le32(buf + 32u);
    offset = VOS_WV_POLICY_HDR_BYTES;

    if (parsed.n > VOS_WV_MAX_WITNESSES) {
        return VOS_WV_ERR_OVER_LIMIT;
    }
    entries_bytes = (size_t)parsed.n * (size_t)VOS_WV_POLICY_ENTRY_BYTES;
    if (entries_bytes > len - offset) {
        return VOS_WV_ERR_MALFORMED_WIRE;
    }

    for (uint32_t i = 0u; i < parsed.n; ++i) {
        parsed.witnesses[i].witness_id = get_le64(buf + offset);
        copy_bytes(parsed.witnesses[i].verify_key,
                   buf + offset + 8u,
                   VOS_WV_KEY_BYTES);
        offset += VOS_WV_POLICY_ENTRY_BYTES;
    }

    if (offset != len) {
        return VOS_WV_ERR_TRAILING_BYTES;
    }
    if (!vos_wv_policy_is_wellformed(&parsed)) {
        return VOS_WV_ERR_INVALID_POLICY;
    }

    *out = parsed;
    return VOS_WV_OK;
}

enum vos_wv_status vos_wv_parse_checkpoint(const uint8_t *buf,
                                           size_t len,
                                           struct vos_wv_checkpoint *out)
{
    struct vos_wv_checkpoint parsed;
    size_t offset = 0u;
    size_t entries_bytes = 0u;

    if (buf == NULL || out == NULL) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    if (len < VOS_WV_CHECKPOINT_HDR_BYTES) {
        return VOS_WV_ERR_MALFORMED_WIRE;
    }
    if (!match_magic(buf, "VOSWTC01")) {
        return VOS_WV_ERR_MALFORMED_WIRE;
    }

    zero_bytes((uint8_t *)&parsed, sizeof(parsed));
    parsed.entry_count = get_le32(buf + 8u);
    offset = VOS_WV_CHECKPOINT_HDR_BYTES;

    if (parsed.entry_count > VOS_WV_MAX_CHECKPOINT_ENTRIES) {
        return VOS_WV_ERR_OVER_LIMIT;
    }
    entries_bytes = (size_t)parsed.entry_count * (size_t)VOS_WV_DIGEST_BYTES;
    if (entries_bytes > len - offset) {
        return VOS_WV_ERR_MALFORMED_WIRE;
    }

    for (uint32_t i = 0u; i < parsed.entry_count; ++i) {
        copy_bytes(parsed.entries[i].bytes, buf + offset, VOS_WV_DIGEST_BYTES);
        offset += VOS_WV_DIGEST_BYTES;
    }

    if (offset != len) {
        return VOS_WV_ERR_TRAILING_BYTES;
    }

    *out = parsed;
    return VOS_WV_OK;
}

enum vos_wv_status vos_wv_parse_signature(const uint8_t *buf,
                                          size_t len,
                                          struct vos_wv_signature *out)
{
    struct vos_wv_signature parsed;

    if (buf == NULL || out == NULL) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    if (len < VOS_WV_SIGNATURE_WIRE_BYTES) {
        return VOS_WV_ERR_MALFORMED_WIRE;
    }
    if (len > VOS_WV_SIGNATURE_WIRE_BYTES) {
        return VOS_WV_ERR_TRAILING_BYTES;
    }
    if (!match_magic(buf, "VOSWIT01")) {
        return VOS_WV_ERR_MALFORMED_WIRE;
    }

    zero_bytes((uint8_t *)&parsed, sizeof(parsed));
    parsed.stmt_kind = get_le32(buf + 8u);
    if (parsed.stmt_kind != (uint32_t)VOS_WV_STMT_PLAIN &&
        parsed.stmt_kind != (uint32_t)VOS_WV_STMT_TERMINAL) {
        return VOS_WV_ERR_MALFORMED_WIRE;
    }

    parsed.trust_scope = get_le64(buf + 12u);
    parsed.epoch = get_le64(buf + 20u);
    copy_bytes(parsed.policy_digest.bytes, buf + 28u, VOS_WV_DIGEST_BYTES);
    copy_bytes(parsed.checkpoint_digest.bytes, buf + 60u, VOS_WV_DIGEST_BYTES);
    copy_bytes(parsed.transition_digest.bytes, buf + 92u, VOS_WV_DIGEST_BYTES);
    parsed.signer_id = get_le64(buf + 124u);
    copy_bytes(parsed.signer_key, buf + 132u, VOS_WV_KEY_BYTES);
    copy_bytes(parsed.mac, buf + 164u, VOS_WV_DIGEST_BYTES);

    if (parsed.stmt_kind == (uint32_t)VOS_WV_STMT_PLAIN &&
        !is_zero_bytes(parsed.transition_digest.bytes, VOS_WV_DIGEST_BYTES)) {
        return VOS_WV_ERR_BAD_BINDING;
    }

    *out = parsed;
    return VOS_WV_OK;
}

enum vos_wv_status vos_wv_parse_certificate(const uint8_t *buf,
                                            size_t len,
                                            struct vos_wv_signature *out_sigs,
                                            size_t max_sigs,
                                            size_t *out_count)
{
    size_t offset = 0u;
    uint32_t count = 0u;
    size_t sigs_bytes = 0u;

    if (buf == NULL || out_sigs == NULL || out_count == NULL) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    if (len < 12u || !match_magic(buf, "VOSWTS01")) {
        return VOS_WV_ERR_MALFORMED_WIRE;
    }

    count = get_le32(buf + 8u);
    offset = 12u;
    if (count > VOS_WV_MAX_SIGNATURES || (size_t)count > max_sigs) {
        return VOS_WV_ERR_OVER_LIMIT;
    }
    sigs_bytes = (size_t)count * (size_t)VOS_WV_SIGNATURE_WIRE_BYTES;
    if (sigs_bytes > len - offset) {
        return VOS_WV_ERR_MALFORMED_WIRE;
    }
    if (offset + sigs_bytes != len) {
        return VOS_WV_ERR_TRAILING_BYTES;
    }

    for (uint32_t i = 0u; i < count; ++i) {
        const enum vos_wv_status st = vos_wv_parse_signature(
            buf + offset,
            VOS_WV_SIGNATURE_WIRE_BYTES,
            &out_sigs[i]);
        if (st != VOS_WV_OK) {
            return st;
        }
        offset += VOS_WV_SIGNATURE_WIRE_BYTES;
    }

    *out_count = (size_t)count;
    return VOS_WV_OK;
}

static enum vos_wv_status read_len_prefixed_slice(const uint8_t *buf,
                                                  size_t len,
                                                  size_t *offset,
                                                  const uint8_t **out_ptr,
                                                  size_t *out_len)
{
    uint32_t item_len = 0u;

    if (4u > len - *offset) {
        return VOS_WV_ERR_MALFORMED_WIRE;
    }
    item_len = get_le32(buf + *offset);
    *offset += 4u;
    if ((size_t)item_len > len - *offset) {
        return VOS_WV_ERR_MALFORMED_WIRE;
    }
    *out_ptr = buf + *offset;
    *out_len = (size_t)item_len;
    *offset += (size_t)item_len;
    return VOS_WV_OK;
}

enum vos_wv_status vos_wv_parse_transition(const uint8_t *buf,
                                           size_t len,
                                           struct vos_wv_transition *out)
{
    struct vos_wv_transition parsed;
    size_t offset = 0u;
    const uint8_t *slice = NULL;
    size_t slice_len = 0u;
    enum vos_wv_status st;

    if (buf == NULL || out == NULL) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    if (len < VOS_WV_MAGIC_BYTES || !match_magic(buf, "VOSWTT01")) {
        return VOS_WV_ERR_MALFORMED_WIRE;
    }

    zero_bytes((uint8_t *)&parsed, sizeof(parsed));
    offset = VOS_WV_MAGIC_BYTES;

    st = read_len_prefixed_slice(buf, len, &offset, &slice, &slice_len);
    if (st != VOS_WV_OK) {
        return st;
    }
    st = vos_wv_parse_policy(slice, slice_len, &parsed.old_policy);
    if (st != VOS_WV_OK) {
        return st;
    }

    st = read_len_prefixed_slice(buf, len, &offset, &slice, &slice_len);
    if (st != VOS_WV_OK) {
        return st;
    }
    st = vos_wv_parse_policy(slice, slice_len, &parsed.new_policy);
    if (st != VOS_WV_OK) {
        return st;
    }

    st = read_len_prefixed_slice(buf, len, &offset, &slice, &slice_len);
    if (st != VOS_WV_OK) {
        return st;
    }
    st = vos_wv_parse_checkpoint(slice, slice_len, &parsed.anchor);
    if (st != VOS_WV_OK) {
        return st;
    }

    if (offset != len) {
        return VOS_WV_ERR_TRAILING_BYTES;
    }

    *out = parsed;
    return VOS_WV_OK;
}

enum vos_wv_status vos_wv_parse_rebootstrap(const uint8_t *buf,
                                            size_t len,
                                            struct vos_wv_rebootstrap *out)
{
    struct vos_wv_rebootstrap parsed;
    size_t offset = 0u;
    const uint8_t *slice = NULL;
    size_t slice_len = 0u;
    enum vos_wv_status st;

    if (buf == NULL || out == NULL) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    if (len < VOS_WV_MAGIC_BYTES || !match_magic(buf, "VOSWTR01")) {
        return VOS_WV_ERR_MALFORMED_WIRE;
    }

    zero_bytes((uint8_t *)&parsed, sizeof(parsed));
    offset = VOS_WV_MAGIC_BYTES;

    st = read_len_prefixed_slice(buf, len, &offset, &slice, &slice_len);
    if (st != VOS_WV_OK) {
        return st;
    }
    st = vos_wv_parse_policy(slice, slice_len, &parsed.old_policy);
    if (st != VOS_WV_OK) {
        return st;
    }

    st = read_len_prefixed_slice(buf, len, &offset, &slice, &slice_len);
    if (st != VOS_WV_OK) {
        return st;
    }
    st = vos_wv_parse_policy(slice, slice_len, &parsed.new_policy);
    if (st != VOS_WV_OK) {
        return st;
    }

    st = read_len_prefixed_slice(buf, len, &offset, &slice, &slice_len);
    if (st != VOS_WV_OK) {
        return st;
    }
    st = vos_wv_parse_checkpoint(slice, slice_len, &parsed.anchor);
    if (st != VOS_WV_OK) {
        return st;
    }

    st = read_len_prefixed_slice(buf, len, &offset, &slice, &slice_len);
    if (st != VOS_WV_OK) {
        return st;
    }
    if (slice_len > VOS_WV_MAX_ASSUMPTIONS_BYTES) {
        return VOS_WV_ERR_OVER_LIMIT;
    }
    parsed.assumptions_len = (uint32_t)slice_len;
    if (slice_len > 0u) {
        copy_bytes(parsed.assumptions, slice, slice_len);
    }

    if ((size_t)VOS_WV_DIGEST_BYTES > len - offset) {
        return VOS_WV_ERR_MALFORMED_WIRE;
    }
    copy_bytes(parsed.auth_mac, buf + offset, VOS_WV_DIGEST_BYTES);
    offset += VOS_WV_DIGEST_BYTES;

    if (offset != len) {
        return VOS_WV_ERR_TRAILING_BYTES;
    }

    *out = parsed;
    return VOS_WV_OK;
}

enum vos_wv_status vos_wv_client_init(struct vos_wv_client *client,
                                      const struct vos_wv_policy *initial_policy,
                                      const struct vos_wv_checkpoint *initial_pin,
                                      const struct vos_wv_hash *initial_generation,
                                      const uint8_t bootstrap_key[VOS_WV_KEY_BYTES])
{
    if (client == NULL || initial_policy == NULL || initial_pin == NULL ||
        initial_generation == NULL || bootstrap_key == NULL) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    if (!vos_wv_policy_is_wellformed(initial_policy)) {
        return VOS_WV_ERR_INVALID_POLICY;
    }
    if (!vos_wv_policy_is_safe(initial_policy)) {
        return VOS_WV_ERR_UNSAFE_POLICY;
    }
    if (!vos_wv_checkpoint_is_wellformed(initial_pin)) {
        return VOS_WV_ERR_OVER_LIMIT;
    }
    if (is_zero_bytes(bootstrap_key, VOS_WV_KEY_BYTES)) {
        return VOS_WV_ERR_INVALID_ARG;
    }

    zero_bytes((uint8_t *)client, sizeof(*client));
    client->policy = *initial_policy;
    client->pinned = *initial_pin;
    client->running_generation = *initial_generation;
    copy_bytes(client->bootstrap_key, bootstrap_key, VOS_WV_KEY_BYTES);
    client->continuity_preserved = 1u;
    client->seen_scope_count = 1u;
    client->seen_scopes[0] = initial_policy->trust_scope;
    return VOS_WV_OK;
}

static void encode_sig_mac_message(const struct vos_wv_signature *sig,
                                   uint8_t msg[VOS_WV_SIG_MAC_MSG_BYTES])
{
    write_magic(msg, "VOSWIT01");
    put_le32(msg + 8u, sig->stmt_kind);
    put_le64(msg + 12u, sig->trust_scope);
    put_le64(msg + 20u, sig->epoch);
    copy_bytes(msg + 28u, sig->policy_digest.bytes, VOS_WV_DIGEST_BYTES);
    copy_bytes(msg + 60u, sig->checkpoint_digest.bytes, VOS_WV_DIGEST_BYTES);
    copy_bytes(msg + 92u, sig->transition_digest.bytes, VOS_WV_DIGEST_BYTES);
    put_le64(msg + 124u, sig->signer_id);
    copy_bytes(msg + 132u, sig->signer_key, VOS_WV_KEY_BYTES);
}

enum vos_wv_status vos_wv_verify_certificate(const struct vos_wv_policy *policy,
                                             enum vos_wv_stmt_kind stmt_kind,
                                             const struct vos_wv_checkpoint *checkpoint,
                                             const struct vos_wv_transition *terminal,
                                             const struct vos_wv_signature *sigs,
                                             size_t sig_count)
{
    struct vos_wv_hash expected_policy_dig;
    struct vos_wv_hash expected_cp_dig;
    struct vos_wv_hash expected_tr_dig;
    uint8_t seen_signers[VOS_WV_MAX_WITNESSES];
    uint32_t valid_count = 0u;
    enum vos_wv_status st;

    if (policy == NULL || checkpoint == NULL) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    if (sig_count > 0u && sigs == NULL) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    if (sig_count > VOS_WV_MAX_SIGNATURES) {
        return VOS_WV_ERR_OVER_LIMIT;
    }
    if (!vos_wv_policy_is_wellformed(policy)) {
        return VOS_WV_ERR_INVALID_POLICY;
    }
    if (!vos_wv_policy_is_safe(policy)) {
        return VOS_WV_ERR_UNSAFE_POLICY;
    }
    if (!vos_wv_checkpoint_is_wellformed(checkpoint)) {
        return VOS_WV_ERR_OVER_LIMIT;
    }

    zero_bytes(expected_tr_dig.bytes, VOS_WV_DIGEST_BYTES);
    if (stmt_kind == VOS_WV_STMT_PLAIN) {
        if (terminal != NULL) {
            return VOS_WV_ERR_INVALID_ARG;
        }
    } else if (stmt_kind == VOS_WV_STMT_TERMINAL) {
        if (terminal == NULL) {
            return VOS_WV_ERR_INVALID_ARG;
        }
        if (!policies_equal(&terminal->old_policy, policy) ||
            !vos_wv_transition_is_continuous(terminal)) {
            return VOS_WV_ERR_DISCONTINUOUS;
        }
        if (terminal->anchor.entry_count != checkpoint->entry_count ||
            !vos_wv_checkpoint_extends(&terminal->anchor, checkpoint)) {
            return VOS_WV_ERR_BAD_BINDING;
        }
        st = vos_wv_transition_digest(terminal, &expected_tr_dig);
        if (st != VOS_WV_OK) {
            return st;
        }
    } else {
        return VOS_WV_ERR_INVALID_ARG;
    }

    st = vos_wv_policy_digest(policy, &expected_policy_dig);
    if (st != VOS_WV_OK) {
        return st;
    }
    st = vos_wv_checkpoint_digest(checkpoint, &expected_cp_dig);
    if (st != VOS_WV_OK) {
        return st;
    }

    zero_bytes(seen_signers, sizeof(seen_signers));

    for (size_t s = 0u; s < sig_count; ++s) {
        const struct vos_wv_signature *sig = &sigs[s];
        uint32_t enrolled_idx = policy->n;
        uint8_t msg[VOS_WV_SIG_MAC_MSG_BYTES];
        uint8_t expected_mac[VOS_WV_DIGEST_BYTES];

        if (sig->stmt_kind != (uint32_t)stmt_kind ||
            sig->trust_scope != policy->trust_scope ||
            sig->epoch != policy->epoch ||
            !equal_hashes(&sig->policy_digest, &expected_policy_dig) ||
            !equal_hashes(&sig->checkpoint_digest, &expected_cp_dig) ||
            !equal_hashes(&sig->transition_digest, &expected_tr_dig)) {
            return VOS_WV_ERR_BAD_BINDING;
        }

        for (uint32_t w = 0u; w < policy->n; ++w) {
            if (policy->witnesses[w].witness_id == sig->signer_id) {
                enrolled_idx = w;
                break;
            }
        }
        if (enrolled_idx >= policy->n) {
            return VOS_WV_ERR_FOREIGN_SIGNER;
        }

        if (!equal_bytes_ct(sig->signer_key,
                            policy->witnesses[enrolled_idx].verify_key,
                            VOS_WV_KEY_BYTES)) {
            return VOS_WV_ERR_KEY_MISMATCH;
        }

        if (seen_signers[enrolled_idx] != 0u) {
            return VOS_WV_ERR_DUPLICATE_SIGNER;
        }

        encode_sig_mac_message(sig, msg);
        if (vos_hmac_sha256(policy->witnesses[enrolled_idx].verify_key,
                            VOS_WV_KEY_BYTES,
                            msg,
                            sizeof(msg),
                            expected_mac) != 1) {
            return VOS_WV_ERR_CRYPTO;
        }
        if (!equal_bytes_ct(sig->mac, expected_mac, VOS_WV_DIGEST_BYTES)) {
            return VOS_WV_ERR_FORGED_MAC;
        }

        seen_signers[enrolled_idx] = 1u;
        valid_count += 1u;
    }

    if (valid_count < policy->k) {
        return VOS_WV_ERR_QUORUM_UNMET;
    }
    return VOS_WV_OK;
}

enum vos_wv_status vos_wv_admit(struct vos_wv_client *client,
                                const struct vos_wv_checkpoint *checkpoint,
                                const struct vos_wv_signature *sigs,
                                size_t sig_count,
                                const struct vos_wv_hash *base_image_root,
                                const struct vos_wv_hash *package_ids,
                                size_t package_count,
                                const struct vos_wv_hash *candidate_generation)
{
    enum vos_wv_status st;

    if (client == NULL || checkpoint == NULL || base_image_root == NULL ||
        candidate_generation == NULL) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    if ((sig_count > 0u && sigs == NULL) ||
        (package_count > 0u && package_ids == NULL)) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    if (package_count > VOS_WV_MAX_PACKAGES) {
        return VOS_WV_ERR_OVER_LIMIT;
    }
    if (is_zero_bytes(base_image_root->bytes, VOS_WV_DIGEST_BYTES)) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    for (size_t i = 0u; i < package_count; ++i) {
        if (is_zero_bytes(package_ids[i].bytes, VOS_WV_DIGEST_BYTES)) {
            return VOS_WV_ERR_INVALID_ARG;
        }
    }

    st = vos_wv_verify_certificate(&client->policy,
                                   VOS_WV_STMT_PLAIN,
                                   checkpoint,
                                   NULL,
                                   sigs,
                                   sig_count);
    if (st != VOS_WV_OK) {
        return st;
    }

    if (!vos_wv_checkpoint_extends(checkpoint, &client->pinned)) {
        return VOS_WV_ERR_CHECKPOINT_STALE;
    }

    if (!vos_wv_checkpoint_contains(checkpoint, base_image_root)) {
        return VOS_WV_ERR_MISSING_BASE;
    }

    for (size_t i = 0u; i < package_count; ++i) {
        if (!vos_wv_checkpoint_contains(checkpoint, &package_ids[i])) {
            return VOS_WV_ERR_MISSING_PACKAGE;
        }
    }

    client->pinned = *checkpoint;
    client->running_generation = *candidate_generation;
    return VOS_WV_OK;
}

enum vos_wv_status vos_wv_transition(struct vos_wv_client *client,
                                     const struct vos_wv_transition *tr,
                                     const struct vos_wv_signature *old_seals,
                                     size_t old_seal_count,
                                     const struct vos_wv_signature *new_sigs,
                                     size_t new_sig_count)
{
    enum vos_wv_status st;

    if (client == NULL || tr == NULL) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    if ((old_seal_count > 0u && old_seals == NULL) ||
        (new_sig_count > 0u && new_sigs == NULL)) {
        return VOS_WV_ERR_INVALID_ARG;
    }

    if (!policies_equal(&tr->old_policy, &client->policy)) {
        return VOS_WV_ERR_POLICY_MISMATCH;
    }
    if (!vos_wv_transition_is_continuous(tr)) {
        return VOS_WV_ERR_DISCONTINUOUS;
    }
    if (!vos_wv_checkpoint_extends(&tr->anchor, &client->pinned)) {
        return VOS_WV_ERR_CHECKPOINT_STALE;
    }

    st = vos_wv_verify_certificate(&tr->old_policy,
                                   VOS_WV_STMT_TERMINAL,
                                   &tr->anchor,
                                   tr,
                                   old_seals,
                                   old_seal_count);
    if (st != VOS_WV_OK) {
        return st;
    }

    st = vos_wv_verify_certificate(&tr->new_policy,
                                   VOS_WV_STMT_PLAIN,
                                   &tr->anchor,
                                   NULL,
                                   new_sigs,
                                   new_sig_count);
    if (st != VOS_WV_OK) {
        return st;
    }

    client->policy = tr->new_policy;
    client->pinned = tr->anchor;
    return VOS_WV_OK;
}

enum vos_wv_status vos_wv_rebootstrap(struct vos_wv_client *client,
                                      const struct vos_wv_rebootstrap *rb,
                                      const struct vos_wv_signature *new_sigs,
                                      size_t new_sig_count)
{
    uint8_t mac_msg[VOS_WV_REBOOT_MAC_BUF_BYTES];
    uint8_t expected_mac[VOS_WV_DIGEST_BYTES];
    struct vos_wv_hash old_dig;
    struct vos_wv_hash new_dig;
    struct vos_wv_hash anchor_dig;
    size_t msg_len = 0u;
    enum vos_wv_status st;

    if (client == NULL || rb == NULL) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    if (new_sig_count > 0u && new_sigs == NULL) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    if (client->seen_scope_count > VOS_WV_MAX_SEEN_SCOPES) {
        return VOS_WV_ERR_INVALID_ARG;
    }
    if (is_zero_bytes(client->bootstrap_key, VOS_WV_KEY_BYTES)) {
        return VOS_WV_ERR_INVALID_ARG;
    }

    if (!policies_equal(&rb->old_policy, &client->policy)) {
        return VOS_WV_ERR_POLICY_MISMATCH;
    }
    if (rb->assumptions_len == 0u ||
        rb->assumptions_len > VOS_WV_MAX_ASSUMPTIONS_BYTES ||
        !has_non_whitespace(rb->assumptions, rb->assumptions_len)) {
        return VOS_WV_ERR_EMPTY_ASSUMPTIONS;
    }
    if (!vos_wv_policy_is_wellformed(&rb->new_policy)) {
        return VOS_WV_ERR_INVALID_POLICY;
    }
    if (!vos_wv_policy_is_safe(&rb->new_policy)) {
        return VOS_WV_ERR_UNSAFE_POLICY;
    }
    if (!vos_wv_checkpoint_is_wellformed(&rb->anchor)) {
        return VOS_WV_ERR_OVER_LIMIT;
    }

    st = vos_wv_policy_digest(&rb->old_policy, &old_dig);
    if (st != VOS_WV_OK) {
        return st;
    }
    st = vos_wv_policy_digest(&rb->new_policy, &new_dig);
    if (st != VOS_WV_OK) {
        return st;
    }
    st = vos_wv_checkpoint_digest(&rb->anchor, &anchor_dig);
    if (st != VOS_WV_OK) {
        return st;
    }

    write_magic(mac_msg, "VOSWTR01");
    copy_bytes(mac_msg + 8u, old_dig.bytes, VOS_WV_DIGEST_BYTES);
    copy_bytes(mac_msg + 8u + VOS_WV_DIGEST_BYTES, new_dig.bytes, VOS_WV_DIGEST_BYTES);
    copy_bytes(mac_msg + 8u + (2u * VOS_WV_DIGEST_BYTES),
               anchor_dig.bytes,
               VOS_WV_DIGEST_BYTES);
    put_le32(mac_msg + 8u + (3u * VOS_WV_DIGEST_BYTES), rb->assumptions_len);
    copy_bytes(mac_msg + 12u + (3u * VOS_WV_DIGEST_BYTES),
               rb->assumptions,
               rb->assumptions_len);
    msg_len = 12u + (3u * VOS_WV_DIGEST_BYTES) + (size_t)rb->assumptions_len;

    if (vos_hmac_sha256(client->bootstrap_key,
                        VOS_WV_KEY_BYTES,
                        mac_msg,
                        msg_len,
                        expected_mac) != 1) {
        return VOS_WV_ERR_CRYPTO;
    }
    if (!equal_bytes_ct(rb->auth_mac, expected_mac, VOS_WV_DIGEST_BYTES)) {
        return VOS_WV_ERR_UNAUTHENTICATED;
    }

    if (scope_already_seen(client, rb->new_policy.trust_scope)) {
        return VOS_WV_ERR_SCOPE_REUSED;
    }
    if (client->seen_scope_count >= VOS_WV_MAX_SEEN_SCOPES) {
        return VOS_WV_ERR_OVER_LIMIT;
    }

    st = vos_wv_verify_certificate(&rb->new_policy,
                                   VOS_WV_STMT_PLAIN,
                                   &rb->anchor,
                                   NULL,
                                   new_sigs,
                                   new_sig_count);
    if (st != VOS_WV_OK) {
        return st;
    }

    client->policy = rb->new_policy;
    client->pinned = rb->anchor;
    client->continuity_preserved = 0u;
    client->seen_scopes[client->seen_scope_count] = rb->new_policy.trust_scope;
    client->seen_scope_count += 1u;
    return VOS_WV_OK;
}
