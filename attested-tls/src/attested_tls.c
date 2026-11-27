// SPDX-License-Identifier: Apache-2.0
#include "vos_attested_tls.h"

_Static_assert((unsigned)VOS_ATLS_DIGEST_BYTES == (unsigned)VOS_CRYPTO_DIGEST_BYTES,
               "digest width must match vos_crypto_core");
_Static_assert((unsigned)VOS_ATLS_MAX_CHALLENGE_WIRE_BYTES ==
                   15u + VOS_ATLS_MAX_NONCE_BYTES + VOS_ATLS_MAX_ORIGIN_BYTES +
                       VOS_ATLS_MAX_DOMAIN_BYTES,
               "challenge wire capacity must match exact field sum");
_Static_assert((unsigned)VOS_ATLS_MAX_EVIDENCE_WIRE_BYTES >=
                   8u + 8u + VOS_ATLS_EXPORTER_BYTES +
                       VOS_ATLS_MAX_CHALLENGE_WIRE_BYTES + 2u +
                       VOS_ATLS_MAX_PRINCIPAL_BYTES + 2u + VOS_ATLS_MAX_ROLE_BYTES +
                       1u + 2u + VOS_ATLS_MAX_ALIAS_BYTES + VOS_ATLS_DIGEST_BYTES,
               "evidence wire capacity must hold maximal canonical frame");

enum {
    VOS_ATLS_CHAL_HDR_BYTES = 15u,
    VOS_ATLS_EVID_HDR_BYTES = 8u + 8u + VOS_ATLS_EXPORTER_BYTES,
    VOS_ATLS_FETCH_REQ_HDR_BYTES = 8u + 2u + 2u + VOS_ATLS_DIGEST_BYTES,
    VOS_ATLS_FETCH_REP_HDR_BYTES = 8u + 1u + 2u + 4u + VOS_ATLS_DIGEST_BYTES
};

static void zero_bytes(uint8_t *dst, size_t len)
{
    if (dst == NULL) {
        return;
    }
    for (size_t i = 0u; i < len; ++i) {
        dst[i] = 0u;
    }
}

static void copy_bytes(uint8_t *dst, const uint8_t *src, size_t len)
{
    if (len == 0u || dst == NULL || src == NULL) {
        return;
    }
    for (size_t i = 0u; i < len; ++i) {
        dst[i] = src[i];
    }
}

static int equal_bytes_ct(const uint8_t *a, const uint8_t *b, size_t len)
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

static int bytes_equal_exact(const uint8_t *a,
                             uint32_t a_len,
                             const uint8_t *b,
                             uint32_t b_len,
                             uint32_t max_len)
{
    if (a_len != b_len || a_len > max_len) {
        return 0;
    }
    return equal_bytes_ct(a, b, (size_t)a_len);
}

static int is_all_zero(const uint8_t *buf, size_t len)
{
    uint8_t acc = 0u;
    for (size_t i = 0u; i < len; ++i) {
        acc |= buf[i];
    }
    return acc == 0u;
}

static void put_le16(uint8_t *dst, uint16_t val)
{
    dst[0] = (uint8_t)(val & 0xffu);
    dst[1] = (uint8_t)((val >> 8u) & 0xffu);
}

static uint16_t get_le16(const uint8_t *src)
{
    return (uint16_t)((uint32_t)src[0] | ((uint32_t)src[1] << 8u));
}

static void put_le32(uint8_t *dst, uint32_t val)
{
    for (uint32_t i = 0u; i < 4u; ++i) {
        dst[i] = (uint8_t)((val >> (8u * i)) & 0xffu);
    }
}

static uint32_t get_le32(const uint8_t *src)
{
    return (uint32_t)src[0] | ((uint32_t)src[1] << 8u) |
           ((uint32_t)src[2] << 16u) | ((uint32_t)src[3] << 24u);
}

static void put_le64(uint8_t *dst, uint64_t val)
{
    for (uint32_t i = 0u; i < 8u; ++i) {
        dst[i] = (uint8_t)((val >> (8u * i)) & 0xffu);
    }
}

static uint64_t get_le64(const uint8_t *src)
{
    uint64_t v = 0u;
    for (uint32_t i = 0u; i < 8u; ++i) {
        v |= ((uint64_t)src[i]) << (8u * i);
    }
    return v;
}

static void write_magic(uint8_t *dst, const char tag[8])
{
    for (size_t i = 0u; i < 8u; ++i) {
        dst[i] = (uint8_t)tag[i];
    }
}

static int check_magic(const uint8_t *src, const char tag[8])
{
    uint8_t diff = 0u;
    for (size_t i = 0u; i < 8u; ++i) {
        diff |= (uint8_t)(src[i] ^ (uint8_t)tag[i]);
    }
    return diff == 0u;
}

static int challenge_fields_valid(const struct vos_atls_challenge *chal)
{
    if (chal == NULL) {
        return 0;
    }
    if (chal->unit_scope > VOS_ATLS_SCOPE_UNIT) {
        return 0;
    }
    if (chal->nonce_len == 0u || chal->nonce_len > VOS_ATLS_MAX_NONCE_BYTES) {
        return 0;
    }
    if (chal->origin_len == 0u || chal->origin_len > VOS_ATLS_MAX_ORIGIN_BYTES) {
        return 0;
    }
    if (chal->domain_len == 0u || chal->domain_len > VOS_ATLS_MAX_DOMAIN_BYTES) {
        return 0;
    }
    return 1;
}

static int challenges_equal(const struct vos_atls_challenge *a,
                            const struct vos_atls_challenge *b)
{
    return a->unit_scope == b->unit_scope &&
           bytes_equal_exact(a->nonce, a->nonce_len, b->nonce, b->nonce_len,
                             VOS_ATLS_MAX_NONCE_BYTES) &&
           bytes_equal_exact(a->origin, a->origin_len, b->origin, b->origin_len,
                             VOS_ATLS_MAX_ORIGIN_BYTES) &&
           bytes_equal_exact(a->domain, a->domain_len, b->domain, b->domain_len,
                             VOS_ATLS_MAX_DOMAIN_BYTES);
}

static enum vos_atls_status encode_challenge_into(const struct vos_atls_profile *profile,
                                                  const struct vos_atls_challenge *chal,
                                                  uint8_t *out,
                                                  size_t cap,
                                                  size_t *out_len)
{
    if (!vos_atls_profile_bounded(profile)) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    if (!challenge_fields_valid(chal) || out == NULL || out_len == NULL) {
        return VOS_ATLS_ERR_INVALID;
    }
    const size_t needed = VOS_ATLS_CHAL_HDR_BYTES + (size_t)chal->nonce_len +
                          (size_t)chal->origin_len + (size_t)chal->domain_len;
    if (needed > (size_t)profile->challenge_bound ||
        needed > VOS_ATLS_MAX_CHALLENGE_WIRE_BYTES) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    if (needed > cap) {
        return VOS_ATLS_ERR_BUFFER;
    }

    write_magic(out, "VOSATLC1");
    out[8] = chal->unit_scope;
    put_le16(out + 9u, (uint16_t)chal->nonce_len);
    put_le16(out + 11u, (uint16_t)chal->origin_len);
    put_le16(out + 13u, (uint16_t)chal->domain_len);
    size_t off = VOS_ATLS_CHAL_HDR_BYTES;
    copy_bytes(out + off, chal->nonce, chal->nonce_len);
    off += chal->nonce_len;
    copy_bytes(out + off, chal->origin, chal->origin_len);
    off += chal->origin_len;
    copy_bytes(out + off, chal->domain, chal->domain_len);
    off += chal->domain_len;
    *out_len = off;
    return VOS_ATLS_OK;
}

static enum vos_atls_status decode_challenge_slice(const struct vos_atls_profile *profile,
                                                   const uint8_t *wire,
                                                   size_t wire_len,
                                                   int allow_prefix,
                                                   struct vos_atls_challenge *out,
                                                   size_t *consumed_len)
{
    if (!vos_atls_profile_bounded(profile)) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    if (wire == NULL || out == NULL) {
        return VOS_ATLS_ERR_INVALID;
    }
    if (wire_len < VOS_ATLS_CHAL_HDR_BYTES ||
        (!allow_prefix && wire_len > (size_t)profile->challenge_bound) ||
        (!allow_prefix && wire_len > VOS_ATLS_MAX_CHALLENGE_WIRE_BYTES)) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }
    if (!check_magic(wire, "VOSATLC1")) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }

    const uint8_t unit_scope = wire[8];
    const uint32_t nonce_len = get_le16(wire + 9u);
    const uint32_t origin_len = get_le16(wire + 11u);
    const uint32_t domain_len = get_le16(wire + 13u);

    if (unit_scope > VOS_ATLS_SCOPE_UNIT ||
        nonce_len == 0u || nonce_len > VOS_ATLS_MAX_NONCE_BYTES ||
        origin_len == 0u || origin_len > VOS_ATLS_MAX_ORIGIN_BYTES ||
        domain_len == 0u || domain_len > VOS_ATLS_MAX_DOMAIN_BYTES) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }

    const size_t expected_len =
        VOS_ATLS_CHAL_HDR_BYTES + (size_t)nonce_len + (size_t)origin_len + (size_t)domain_len;
    if (expected_len > (size_t)profile->challenge_bound ||
        expected_len > VOS_ATLS_MAX_CHALLENGE_WIRE_BYTES) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    if (allow_prefix ? (wire_len < expected_len) : (wire_len != expected_len)) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }

    zero_bytes((uint8_t *)out, sizeof(*out));
    out->unit_scope = unit_scope;
    out->nonce_len = nonce_len;
    out->origin_len = origin_len;
    out->domain_len = domain_len;

    size_t off = VOS_ATLS_CHAL_HDR_BYTES;
    copy_bytes(out->nonce, wire + off, nonce_len);
    off += nonce_len;
    copy_bytes(out->origin, wire + off, origin_len);
    off += origin_len;
    copy_bytes(out->domain, wire + off, domain_len);
    off += domain_len;

    if (consumed_len != NULL) {
        *consumed_len = off;
    }
    return VOS_ATLS_OK;
}

static enum vos_atls_status encode_evidence_body(const struct vos_atls_profile *profile,
                                                 const struct vos_atls_evidence *ev,
                                                 uint8_t *out,
                                                 size_t cap,
                                                 size_t *out_body_len)
{
    if (!vos_atls_profile_bounded(profile)) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    if (ev == NULL || out == NULL || out_body_len == NULL) {
        return VOS_ATLS_ERR_INVALID;
    }
    if (!challenge_fields_valid(&ev->challenge) ||
        ev->principal_len == 0u || ev->principal_len > VOS_ATLS_MAX_PRINCIPAL_BYTES ||
        ev->role_len == 0u || ev->role_len > VOS_ATLS_MAX_ROLE_BYTES ||
        ev->has_alias > 1u ||
        (ev->has_alias == 0u && ev->alias_len != 0u) ||
        (ev->has_alias == 1u &&
         (ev->alias_len == 0u || ev->alias_len > VOS_ATLS_MAX_ALIAS_BYTES))) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }

    uint8_t chal_buf[VOS_ATLS_MAX_CHALLENGE_WIRE_BYTES];
    size_t chal_len = 0u;
    const enum vos_atls_status cst =
        encode_challenge_into(profile, &ev->challenge, chal_buf, sizeof(chal_buf), &chal_len);
    if (cst != VOS_ATLS_OK) {
        return cst;
    }

    const size_t body_len = VOS_ATLS_EVID_HDR_BYTES + chal_len +
                            2u + (size_t)ev->principal_len +
                            2u + (size_t)ev->role_len +
                            1u + 2u + (size_t)ev->alias_len;
    const size_t total_len = body_len + VOS_ATLS_DIGEST_BYTES;
    if (total_len > (size_t)profile->evidence_bound ||
        total_len > VOS_ATLS_MAX_EVIDENCE_WIRE_BYTES) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    if (body_len > cap) {
        return VOS_ATLS_ERR_BUFFER;
    }

    write_magic(out, "VOSATLE1");
    put_le64(out + 8u, ev->generation);
    copy_bytes(out + 16u, ev->exporter, VOS_ATLS_EXPORTER_BYTES);
    size_t off = VOS_ATLS_EVID_HDR_BYTES;

    copy_bytes(out + off, chal_buf, chal_len);
    off += chal_len;

    put_le16(out + off, (uint16_t)ev->principal_len);
    off += 2u;
    copy_bytes(out + off, ev->principal, ev->principal_len);
    off += ev->principal_len;

    put_le16(out + off, (uint16_t)ev->role_len);
    off += 2u;
    copy_bytes(out + off, ev->role, ev->role_len);
    off += ev->role_len;

    out[off] = ev->has_alias;
    off += 1u;
    put_le16(out + off, (uint16_t)ev->alias_len);
    off += 2u;
    if (ev->alias_len > 0u) {
        copy_bytes(out + off, ev->alias, ev->alias_len);
        off += ev->alias_len;
    }
    *out_body_len = off;
    return VOS_ATLS_OK;
}

static enum vos_atls_status compute_evidence_mac(const uint8_t hmac_key[VOS_CRYPTO_KEY_BYTES_256],
                                                 const uint8_t *body,
                                                 size_t body_len,
                                                 uint8_t out_mac[VOS_ATLS_DIGEST_BYTES])
{
    uint8_t claims_digest[VOS_ATLS_DIGEST_BYTES];
    if (hmac_key == NULL || body == NULL || out_mac == NULL) {
        return VOS_ATLS_ERR_INVALID;
    }
    if (vos_sha256(body, body_len, claims_digest) != 1) {
        return VOS_ATLS_ERR_INVALID;
    }
    if (vos_hmac_sha256(hmac_key, VOS_CRYPTO_KEY_BYTES_256,
                        claims_digest, sizeof(claims_digest), out_mac) != 1) {
        return VOS_ATLS_ERR_INVALID;
    }
    return VOS_ATLS_OK;
}

static int nonce_in_history(const struct vos_atls_connection *conn,
                            const uint8_t *nonce,
                            uint32_t nonce_len)
{
    for (uint32_t i = 0u; i < conn->used_nonce_count; ++i) {
        if (bytes_equal_exact(conn->used_nonces[i].bytes, conn->used_nonces[i].len,
                              nonce, nonce_len, VOS_ATLS_MAX_NONCE_BYTES)) {
            return 1;
        }
    }
    return 0;
}

static int context_in_history(const struct vos_atls_connection *conn, uint64_t context_id)
{
    for (uint32_t i = 0u; i < conn->used_context_count; ++i) {
        if (conn->used_contexts[i] == context_id) {
            return 1;
        }
    }
    return 0;
}

static int generation_approved(const struct vos_atls_appraisal_policy *policy,
                               uint64_t generation)
{
    for (uint32_t i = 0u; i < policy->approved_gen_count; ++i) {
        if (policy->approved_generations[i] == generation) {
            return 1;
        }
    }
    return 0;
}

static const struct vos_atls_measurement_entry *find_measurement(
    const struct vos_atls_broker *broker,
    uint64_t unit_id)
{
    for (uint32_t i = 0u; i < VOS_ATLS_MAX_MEASUREMENTS; ++i) {
        if (broker->measurements[i].present != 0u &&
            broker->measurements[i].unit_id == unit_id) {
            return &broker->measurements[i];
        }
    }
    return NULL;
}

static const struct vos_atls_alias_entry *find_alias(const struct vos_atls_broker *broker,
                                                     const uint8_t *origin,
                                                     uint32_t origin_len,
                                                     uint64_t unit_id)
{
    for (uint32_t i = 0u; i < VOS_ATLS_MAX_ALIASES; ++i) {
        if (broker->aliases[i].present != 0u &&
            broker->aliases[i].unit_id == unit_id &&
            bytes_equal_exact(broker->aliases[i].origin, broker->aliases[i].origin_len,
                              origin, origin_len, VOS_ATLS_MAX_ORIGIN_BYTES)) {
            return &broker->aliases[i];
        }
    }
    return NULL;
}

static int local_request_matches(const struct vos_atls_profile *profile,
                                 const struct vos_atls_protected_context *ctx,
                                 const struct vos_atls_challenge *chal,
                                 const struct vos_atls_client_request *req)
{
    if (req->scope > VOS_ATLS_SCOPE_UNIT || chal->unit_scope > VOS_ATLS_SCOPE_UNIT) {
        return 0;
    }
    if (!bytes_equal_exact(req->role, req->role_len,
                           profile->attester_role, profile->attester_role_len,
                           VOS_ATLS_MAX_ROLE_BYTES)) {
        return 0;
    }
    if (!bytes_equal_exact(req->principal, req->principal_len,
                           ctx->principal, ctx->principal_len,
                           VOS_ATLS_MAX_PRINCIPAL_BYTES)) {
        return 0;
    }
    if (req->scope != chal->unit_scope) {
        return 0;
    }
    if (req->operation != profile->attest_operation || req->operation >= 32u) {
        return 0;
    }
    if (!bytes_equal_exact(req->domain, req->domain_len,
                           profile->domain, profile->domain_len,
                           VOS_ATLS_MAX_DOMAIN_BYTES)) {
        return 0;
    }
    if (req->request_len > profile->request_bound ||
        req->request_len > VOS_ATLS_MAX_REQUEST_BYTES) {
        return 0;
    }
    if (!bytes_equal_exact(chal->origin, chal->origin_len,
                           ctx->origin, ctx->origin_len,
                           VOS_ATLS_MAX_ORIGIN_BYTES)) {
        return 0;
    }
    if (!bytes_equal_exact(chal->domain, chal->domain_len,
                           profile->domain, profile->domain_len,
                           VOS_ATLS_MAX_DOMAIN_BYTES)) {
        return 0;
    }
    if (chal->nonce_len == 0u || chal->nonce_len > VOS_ATLS_MAX_NONCE_BYTES) {
        return 0;
    }
    return 1;
}

void vos_atls_profile_default_init(struct vos_atls_profile *profile)
{
    if (profile == NULL) {
        return;
    }
    zero_bytes((uint8_t *)profile, sizeof(*profile));
    profile->domain_len = VOS_ATLS_DOMAIN_BYTES;
    copy_bytes(profile->domain, (const uint8_t *)VOS_ATLS_DOMAIN_STR, VOS_ATLS_DOMAIN_BYTES);
    profile->attester_role_len = VOS_ATLS_ROLE_BYTES;
    copy_bytes(profile->attester_role, (const uint8_t *)VOS_ATLS_ROLE_STR, VOS_ATLS_ROLE_BYTES);
    profile->attest_operation = VOS_ATLS_OP_ATTEST_LOCAL_SESSION;
    profile->challenge_bound = VOS_ATLS_MAX_CHALLENGE_WIRE_BYTES;
    profile->request_bound = VOS_ATLS_MAX_REQUEST_BYTES;
    profile->evidence_bound = VOS_ATLS_MAX_EVIDENCE_WIRE_BYTES;
    profile->manifest_bound = VOS_ATLS_MAX_MANIFEST_BYTES;
    profile->object_bound = VOS_ATLS_MAX_OBJECT_BYTES;
}

int vos_atls_profile_bounded(const struct vos_atls_profile *profile)
{
    if (profile == NULL) {
        return 0;
    }
    if (profile->domain_len == 0u || profile->domain_len > VOS_ATLS_MAX_DOMAIN_BYTES ||
        profile->attester_role_len == 0u || profile->attester_role_len > VOS_ATLS_MAX_ROLE_BYTES) {
        return 0;
    }
    if (profile->challenge_bound == 0u ||
        profile->challenge_bound > VOS_ATLS_MAX_CHALLENGE_WIRE_BYTES ||
        profile->request_bound == 0u ||
        profile->request_bound > VOS_ATLS_MAX_REQUEST_BYTES ||
        profile->evidence_bound == 0u ||
        profile->evidence_bound > VOS_ATLS_MAX_EVIDENCE_WIRE_BYTES ||
        profile->manifest_bound == 0u ||
        profile->manifest_bound > VOS_ATLS_MAX_MANIFEST_BYTES ||
        profile->object_bound == 0u ||
        profile->object_bound > VOS_ATLS_MAX_OBJECT_BYTES) {
        return 0;
    }
    return 1;
}

int vos_atls_context_usable(const struct vos_atls_protected_context *ctx)
{
    if (ctx == NULL) {
        return 0;
    }
    if (ctx->context_id == 0u || ctx->unit_id == 0u) {
        return 0;
    }
    if (ctx->principal_len == 0u || ctx->principal_len > VOS_ATLS_MAX_PRINCIPAL_BYTES ||
        ctx->origin_len == 0u || ctx->origin_len > VOS_ATLS_MAX_ORIGIN_BYTES) {
        return 0;
    }
    if (ctx->handshake_complete != 1u || ctx->server_authenticated != 1u) {
        return 0;
    }
    if (ctx->early_data != 0u) {
        return 0;
    }
    if (ctx->resumed != 0u) {
        return 0;
    }
    return 1;
}

int vos_atls_policy_valid(const struct vos_atls_appraisal_policy *policy)
{
    if (policy == NULL) {
        return 0;
    }
    if (policy->approved_gen_count == 0u ||
        policy->approved_gen_count > VOS_ATLS_MAX_APPROVED_GENS) {
        return 0;
    }
    if (policy->required_principal_len == 0u ||
        policy->required_principal_len > VOS_ATLS_MAX_PRINCIPAL_BYTES) {
        return 0;
    }
    if (policy->unit_policy > 1u) {
        return 0;
    }
    if (policy->unit_policy == 0u && policy->expected_alias_len != 0u) {
        return 0;
    }
    if (policy->unit_policy == 1u &&
        (policy->expected_alias_len == 0u ||
         policy->expected_alias_len > VOS_ATLS_MAX_ALIAS_BYTES)) {
        return 0;
    }
    return 1;
}

enum vos_atls_status vos_atls_encode_challenge(const struct vos_atls_profile *profile,
                                               const struct vos_atls_challenge *chal,
                                               uint8_t *out,
                                               size_t cap,
                                               size_t *out_len)
{
    return encode_challenge_into(profile, chal, out, cap, out_len);
}

enum vos_atls_status vos_atls_decode_challenge(const struct vos_atls_profile *profile,
                                               const uint8_t *wire,
                                               size_t wire_len,
                                               struct vos_atls_challenge *out)
{
    return decode_challenge_slice(profile, wire, wire_len, 0, out, NULL);
}

enum vos_atls_status vos_atls_encode_evidence(const struct vos_atls_profile *profile,
                                              const struct vos_atls_evidence *ev,
                                              uint8_t *out,
                                              size_t cap,
                                              size_t *out_len)
{
    size_t body_len = 0u;
    if (out == NULL || out_len == NULL) {
        return VOS_ATLS_ERR_INVALID;
    }
    const enum vos_atls_status st =
        encode_evidence_body(profile, ev, out, cap, &body_len);
    if (st != VOS_ATLS_OK) {
        return st;
    }
    if (body_len + VOS_ATLS_DIGEST_BYTES > cap) {
        return VOS_ATLS_ERR_BUFFER;
    }
    copy_bytes(out + body_len, ev->seal_mac, VOS_ATLS_DIGEST_BYTES);
    *out_len = body_len + VOS_ATLS_DIGEST_BYTES;
    return VOS_ATLS_OK;
}

enum vos_atls_status vos_atls_decode_evidence(const struct vos_atls_profile *profile,
                                              const uint8_t *wire,
                                              size_t wire_len,
                                              struct vos_atls_evidence *out)
{
    if (!vos_atls_profile_bounded(profile)) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    if (wire == NULL || out == NULL) {
        return VOS_ATLS_ERR_INVALID;
    }
    if (wire_len > (size_t)profile->evidence_bound ||
        wire_len > VOS_ATLS_MAX_EVIDENCE_WIRE_BYTES) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    const size_t min_len = VOS_ATLS_EVID_HDR_BYTES + VOS_ATLS_CHAL_HDR_BYTES +
                           3u + 2u + 2u + 1u + 2u + VOS_ATLS_DIGEST_BYTES;
    if (wire_len < min_len || !check_magic(wire, "VOSATLE1")) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }

    struct vos_atls_evidence parsed;
    zero_bytes((uint8_t *)&parsed, sizeof(parsed));
    parsed.generation = get_le64(wire + 8u);
    copy_bytes(parsed.exporter, wire + 16u, VOS_ATLS_EXPORTER_BYTES);

    size_t off = VOS_ATLS_EVID_HDR_BYTES;
    size_t chal_len = 0u;
    const enum vos_atls_status cst = decode_challenge_slice(
        profile, wire + off, wire_len - off, 1, &parsed.challenge, &chal_len);
    if (cst != VOS_ATLS_OK) {
        return cst;
    }
    off += chal_len;

    if (off + 2u > wire_len) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }
    parsed.principal_len = get_le16(wire + off);
    off += 2u;
    if (parsed.principal_len == 0u ||
        parsed.principal_len > VOS_ATLS_MAX_PRINCIPAL_BYTES ||
        off + parsed.principal_len > wire_len) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }
    copy_bytes(parsed.principal, wire + off, parsed.principal_len);
    off += parsed.principal_len;

    if (off + 2u > wire_len) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }
    parsed.role_len = get_le16(wire + off);
    off += 2u;
    if (parsed.role_len == 0u ||
        parsed.role_len > VOS_ATLS_MAX_ROLE_BYTES ||
        off + parsed.role_len > wire_len) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }
    copy_bytes(parsed.role, wire + off, parsed.role_len);
    off += parsed.role_len;

    if (off + 3u > wire_len) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }
    parsed.has_alias = wire[off];
    off += 1u;
    parsed.alias_len = get_le16(wire + off);
    off += 2u;
    if (parsed.has_alias > 1u ||
        (parsed.has_alias == 0u && parsed.alias_len != 0u) ||
        (parsed.has_alias == 1u &&
         (parsed.alias_len == 0u || parsed.alias_len > VOS_ATLS_MAX_ALIAS_BYTES))) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }
    if (off + parsed.alias_len + VOS_ATLS_DIGEST_BYTES != wire_len) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }
    if (parsed.alias_len > 0u) {
        copy_bytes(parsed.alias, wire + off, parsed.alias_len);
        off += parsed.alias_len;
    }
    copy_bytes(parsed.seal_mac, wire + off, VOS_ATLS_DIGEST_BYTES);
    *out = parsed;
    return VOS_ATLS_OK;
}

enum vos_atls_status vos_atls_encode_fetch_request(const struct vos_atls_profile *profile,
                                                   const struct vos_atls_fetch_request *req,
                                                   uint8_t *out,
                                                   size_t cap,
                                                   size_t *out_len)
{
    if (!vos_atls_profile_bounded(profile)) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    if (req == NULL || out == NULL || out_len == NULL) {
        return VOS_ATLS_ERR_INVALID;
    }
    if (req->object_id_len == 0u ||
        req->object_id_len > VOS_ATLS_MAX_OBJECT_ID_BYTES ||
        req->manifest_ref_len == 0u ||
        req->manifest_ref_len > VOS_ATLS_MAX_MANIFEST_BYTES) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }
    if (req->object_id_len > profile->request_bound ||
        req->manifest_ref_len > profile->manifest_bound) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    const size_t total_len = VOS_ATLS_FETCH_REQ_HDR_BYTES +
                             (size_t)req->object_id_len + (size_t)req->manifest_ref_len;
    if (total_len > cap) {
        return VOS_ATLS_ERR_BUFFER;
    }

    write_magic(out, "VOSATLR1");
    put_le16(out + 8u, (uint16_t)req->object_id_len);
    put_le16(out + 10u, (uint16_t)req->manifest_ref_len);
    copy_bytes(out + 12u, req->expected_digest, VOS_ATLS_DIGEST_BYTES);
    size_t off = VOS_ATLS_FETCH_REQ_HDR_BYTES;
    copy_bytes(out + off, req->object_id, req->object_id_len);
    off += req->object_id_len;
    copy_bytes(out + off, req->manifest_ref, req->manifest_ref_len);
    off += req->manifest_ref_len;
    *out_len = off;
    return VOS_ATLS_OK;
}

enum vos_atls_status vos_atls_decode_fetch_request(const struct vos_atls_profile *profile,
                                                   const uint8_t *wire,
                                                   size_t wire_len,
                                                   struct vos_atls_fetch_request *out)
{
    if (!vos_atls_profile_bounded(profile)) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    if (wire == NULL || out == NULL) {
        return VOS_ATLS_ERR_INVALID;
    }
    if (wire_len < VOS_ATLS_FETCH_REQ_HDR_BYTES ||
        wire_len > VOS_ATLS_MAX_FETCH_REQ_WIRE_BYTES ||
        !check_magic(wire, "VOSATLR1")) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }
    const uint32_t obj_id_len = get_le16(wire + 8u);
    const uint32_t manifest_len = get_le16(wire + 10u);
    if (obj_id_len == 0u || obj_id_len > VOS_ATLS_MAX_OBJECT_ID_BYTES ||
        manifest_len == 0u || manifest_len > VOS_ATLS_MAX_MANIFEST_BYTES) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }
    if (obj_id_len > profile->request_bound ||
        manifest_len > profile->manifest_bound) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    const size_t expected_len =
        VOS_ATLS_FETCH_REQ_HDR_BYTES + (size_t)obj_id_len + (size_t)manifest_len;
    if (wire_len != expected_len) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }

    zero_bytes((uint8_t *)out, sizeof(*out));
    out->object_id_len = obj_id_len;
    out->manifest_ref_len = manifest_len;
    copy_bytes(out->expected_digest, wire + 12u, VOS_ATLS_DIGEST_BYTES);
    copy_bytes(out->object_id, wire + VOS_ATLS_FETCH_REQ_HDR_BYTES, obj_id_len);
    copy_bytes(out->manifest_ref, wire + VOS_ATLS_FETCH_REQ_HDR_BYTES + obj_id_len, manifest_len);
    return VOS_ATLS_OK;
}

enum vos_atls_status vos_atls_encode_fetch_reply(const struct vos_atls_profile *profile,
                                                 const struct vos_atls_fetch_reply *rep,
                                                 uint8_t *out,
                                                 size_t cap,
                                                 size_t *out_len)
{
    if (!vos_atls_profile_bounded(profile)) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    if (rep == NULL || out == NULL || out_len == NULL) {
        return VOS_ATLS_ERR_INVALID;
    }
    if (rep->status > VOS_ATLS_REPLY_REFUSED ||
        rep->object_id_len == 0u ||
        rep->object_id_len > VOS_ATLS_MAX_OBJECT_ID_BYTES ||
        rep->object_len > VOS_ATLS_MAX_OBJECT_BYTES) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }
    if (rep->status == VOS_ATLS_REPLY_REFUSED &&
        (rep->object_len != 0u || !is_all_zero(rep->object_sha256, VOS_ATLS_DIGEST_BYTES))) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }
    if (rep->object_id_len > profile->request_bound ||
        rep->object_len > profile->object_bound) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    const size_t total_len =
        VOS_ATLS_FETCH_REP_HDR_BYTES + (size_t)rep->object_id_len + (size_t)rep->object_len;
    if (total_len > cap) {
        return VOS_ATLS_ERR_BUFFER;
    }

    write_magic(out, "VOSATLP1");
    out[8] = rep->status;
    put_le16(out + 9u, (uint16_t)rep->object_id_len);
    put_le32(out + 11u, rep->object_len);
    copy_bytes(out + 15u, rep->object_sha256, VOS_ATLS_DIGEST_BYTES);
    size_t off = VOS_ATLS_FETCH_REP_HDR_BYTES;
    copy_bytes(out + off, rep->object_id, rep->object_id_len);
    off += rep->object_id_len;
    if (rep->object_len > 0u) {
        copy_bytes(out + off, rep->object_bytes, rep->object_len);
        off += rep->object_len;
    }
    *out_len = off;
    return VOS_ATLS_OK;
}

enum vos_atls_status vos_atls_decode_fetch_reply(const struct vos_atls_profile *profile,
                                                 const uint8_t *wire,
                                                 size_t wire_len,
                                                 struct vos_atls_fetch_reply *out)
{
    if (!vos_atls_profile_bounded(profile)) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    if (wire == NULL || out == NULL) {
        return VOS_ATLS_ERR_INVALID;
    }
    if (wire_len < VOS_ATLS_FETCH_REP_HDR_BYTES ||
        wire_len > VOS_ATLS_MAX_FETCH_REP_WIRE_BYTES ||
        !check_magic(wire, "VOSATLP1")) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }

    const uint8_t status = wire[8];
    const uint32_t obj_id_len = get_le16(wire + 9u);
    const uint32_t obj_len = get_le32(wire + 11u);

    if (status > VOS_ATLS_REPLY_REFUSED ||
        obj_id_len == 0u || obj_id_len > VOS_ATLS_MAX_OBJECT_ID_BYTES ||
        obj_len > VOS_ATLS_MAX_OBJECT_BYTES) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }
    if (status == VOS_ATLS_REPLY_REFUSED &&
        (obj_len != 0u || !is_all_zero(wire + 15u, VOS_ATLS_DIGEST_BYTES))) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }
    if (obj_id_len > profile->request_bound || obj_len > profile->object_bound) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    const size_t expected_len =
        VOS_ATLS_FETCH_REP_HDR_BYTES + (size_t)obj_id_len + (size_t)obj_len;
    if (wire_len != expected_len) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }

    zero_bytes((uint8_t *)out, sizeof(*out));
    out->status = status;
    out->object_id_len = obj_id_len;
    out->object_len = obj_len;
    copy_bytes(out->object_sha256, wire + 15u, VOS_ATLS_DIGEST_BYTES);
    copy_bytes(out->object_id, wire + VOS_ATLS_FETCH_REP_HDR_BYTES, obj_id_len);
    if (obj_len > 0u) {
        copy_bytes(out->object_bytes, wire + VOS_ATLS_FETCH_REP_HDR_BYTES + obj_id_len, obj_len);
    }

    if (status == VOS_ATLS_REPLY_OK) {
        uint8_t computed[VOS_ATLS_DIGEST_BYTES];
        if (vos_sha256(out->object_bytes, out->object_len, computed) != 1 ||
            !equal_bytes_ct(computed, out->object_sha256, VOS_ATLS_DIGEST_BYTES)) {
            zero_bytes((uint8_t *)out, sizeof(*out));
            return VOS_ATLS_ERR_AUTHENTICITY;
        }
    }
    return VOS_ATLS_OK;
}

void vos_atls_broker_init(struct vos_atls_broker *broker,
                          const uint8_t hmac_key[VOS_CRYPTO_KEY_BYTES_256],
                          uint64_t server_now)
{
    if (broker == NULL) {
        return;
    }
    zero_bytes((uint8_t *)broker, sizeof(*broker));
    if (hmac_key != NULL) {
        copy_bytes(broker->hmac_key, hmac_key, VOS_CRYPTO_KEY_BYTES_256);
    }
    broker->server_now = server_now;
}

enum vos_atls_status vos_atls_broker_set_measurement(struct vos_atls_broker *broker,
                                                     uint64_t unit_id,
                                                     uint64_t generation)
{
    if (broker == NULL || unit_id == 0u) {
        return VOS_ATLS_ERR_INVALID;
    }
    for (uint32_t i = 0u; i < VOS_ATLS_MAX_MEASUREMENTS; ++i) {
        if (broker->measurements[i].present != 0u &&
            broker->measurements[i].unit_id == unit_id) {
            broker->measurements[i].generation = generation;
            return VOS_ATLS_OK;
        }
    }
    for (uint32_t i = 0u; i < VOS_ATLS_MAX_MEASUREMENTS; ++i) {
        if (broker->measurements[i].present == 0u) {
            broker->measurements[i].present = 1u;
            broker->measurements[i].unit_id = unit_id;
            broker->measurements[i].generation = generation;
            return VOS_ATLS_OK;
        }
    }
    return VOS_ATLS_ERR_BOUNDS;
}

enum vos_atls_status vos_atls_broker_set_alias(struct vos_atls_broker *broker,
                                               const uint8_t *origin,
                                               uint32_t origin_len,
                                               uint64_t unit_id,
                                               const uint8_t *alias,
                                               uint32_t alias_len)
{
    if (broker == NULL || unit_id == 0u || origin == NULL || alias == NULL ||
        origin_len == 0u || origin_len > VOS_ATLS_MAX_ORIGIN_BYTES ||
        alias_len == 0u || alias_len > VOS_ATLS_MAX_ALIAS_BYTES) {
        return VOS_ATLS_ERR_INVALID;
    }
    for (uint32_t i = 0u; i < VOS_ATLS_MAX_ALIASES; ++i) {
        if (broker->aliases[i].present != 0u &&
            broker->aliases[i].unit_id == unit_id &&
            bytes_equal_exact(broker->aliases[i].origin, broker->aliases[i].origin_len,
                              origin, origin_len, VOS_ATLS_MAX_ORIGIN_BYTES)) {
            zero_bytes(broker->aliases[i].alias, sizeof(broker->aliases[i].alias));
            broker->aliases[i].alias_len = alias_len;
            copy_bytes(broker->aliases[i].alias, alias, alias_len);
            return VOS_ATLS_OK;
        }
    }
    for (uint32_t i = 0u; i < VOS_ATLS_MAX_ALIASES; ++i) {
        if (broker->aliases[i].present == 0u) {
            broker->aliases[i].present = 1u;
            broker->aliases[i].unit_id = unit_id;
            broker->aliases[i].origin_len = origin_len;
            copy_bytes(broker->aliases[i].origin, origin, origin_len);
            broker->aliases[i].alias_len = alias_len;
            copy_bytes(broker->aliases[i].alias, alias, alias_len);
            return VOS_ATLS_OK;
        }
    }
    return VOS_ATLS_ERR_BOUNDS;
}

enum vos_atls_status vos_atls_delegate_credential(const struct vos_atls_credential *parent,
                                                  struct vos_atls_credential *child)
{
    if (parent == NULL || child == NULL || parent->sealed != 1u || child->sealed != 1u) {
        return VOS_ATLS_ERR_CREDENTIAL_AUTH;
    }
    if (child->unit_id != parent->unit_id ||
        !bytes_equal_exact(child->role, child->role_len,
                           parent->role, parent->role_len, VOS_ATLS_MAX_ROLE_BYTES) ||
        !bytes_equal_exact(child->principal, child->principal_len,
                           parent->principal, parent->principal_len, VOS_ATLS_MAX_PRINCIPAL_BYTES) ||
        !bytes_equal_exact(child->origin, child->origin_len,
                           parent->origin, parent->origin_len, VOS_ATLS_MAX_ORIGIN_BYTES) ||
        !bytes_equal_exact(child->domain, child->domain_len,
                           parent->domain, parent->domain_len, VOS_ATLS_MAX_DOMAIN_BYTES)) {
        return VOS_ATLS_ERR_CREDENTIAL_AUTH;
    }
    if ((child->scope_mask & parent->scope_mask) != child->scope_mask ||
        (child->operation_mask & parent->operation_mask) != child->operation_mask ||
        child->use_ceiling > parent->use_ceiling ||
        child->expiry > parent->expiry ||
        child->account_id != parent->account_id) {
        return VOS_ATLS_ERR_CREDENTIAL_AUTH;
    }
    return VOS_ATLS_OK;
}

enum vos_atls_status vos_atls_issue_local(const struct vos_atls_profile *profile,
                                          const struct vos_atls_cred_policy *cred_policy,
                                          const struct vos_atls_credential *credential,
                                          struct vos_atls_broker *broker,
                                          const struct vos_atls_client_request *request,
                                          const struct vos_atls_protected_context *ctx,
                                          const struct vos_atls_challenge *challenge,
                                          struct vos_atls_evidence *out_evidence,
                                          uint8_t *out_wire,
                                          size_t out_wire_cap,
                                          size_t *out_wire_len)
{
    if (!vos_atls_profile_bounded(profile)) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    if (cred_policy == NULL || credential == NULL || broker == NULL ||
        request == NULL || ctx == NULL || challenge == NULL) {
        return VOS_ATLS_ERR_INVALID;
    }
    if (!vos_atls_context_usable(ctx)) {
        return VOS_ATLS_ERR_INELIGIBLE_CONTEXT;
    }
    if (credential->sealed != 1u) {
        return VOS_ATLS_ERR_CREDENTIAL_AUTH;
    }
    if (!local_request_matches(profile, ctx, challenge, request)) {
        return VOS_ATLS_ERR_CREDENTIAL_AUTH;
    }

    const uint32_t req_scope_bit =
        (request->scope == VOS_ATLS_SCOPE_UNIT) ? VOS_ATLS_SCOPE_MASK_UNIT
                                                : VOS_ATLS_SCOPE_MASK_SOFTWARE;
    const uint32_t req_op_bit = 1u << request->operation;

    if (credential->unit_id != ctx->unit_id ||
        !bytes_equal_exact(credential->origin, credential->origin_len,
                           ctx->origin, ctx->origin_len, VOS_ATLS_MAX_ORIGIN_BYTES) ||
        !bytes_equal_exact(credential->role, credential->role_len,
                           request->role, request->role_len, VOS_ATLS_MAX_ROLE_BYTES) ||
        !bytes_equal_exact(credential->principal, credential->principal_len,
                           request->principal, request->principal_len,
                           VOS_ATLS_MAX_PRINCIPAL_BYTES) ||
        !bytes_equal_exact(credential->domain, credential->domain_len,
                           request->domain, request->domain_len, VOS_ATLS_MAX_DOMAIN_BYTES) ||
        (credential->scope_mask & req_scope_bit) == 0u ||
        (credential->operation_mask & req_op_bit) == 0u ||
        (cred_policy->allowed_operation_mask & req_op_bit) == 0u ||
        request->request_len > cred_policy->request_limit ||
        credential->account_id >= VOS_ATLS_MAX_ACCOUNTS ||
        broker->account_used[credential->account_id] >= credential->use_ceiling ||
        broker->server_now >= credential->expiry) {
        return VOS_ATLS_ERR_CREDENTIAL_AUTH;
    }

    if (cred_policy->needs_approval != 0u) {
        if (broker->consent_allows == NULL ||
            broker->consent_allows(credential, request,
                                   broker->account_used[credential->account_id],
                                   broker->consent_ctx) == 0) {
            return VOS_ATLS_ERR_CREDENTIAL_AUTH;
        }
    }

    const struct vos_atls_measurement_entry *meas = find_measurement(broker, ctx->unit_id);
    if (meas == NULL) {
        return VOS_ATLS_ERR_MEASUREMENT;
    }

    struct vos_atls_evidence ev;
    zero_bytes((uint8_t *)&ev, sizeof(ev));
    ev.generation = meas->generation;
    copy_bytes(ev.exporter, ctx->exporter, VOS_ATLS_EXPORTER_BYTES);
    ev.challenge = *challenge;
    ev.principal_len = ctx->principal_len;
    copy_bytes(ev.principal, ctx->principal, ctx->principal_len);
    ev.role_len = profile->attester_role_len;
    copy_bytes(ev.role, profile->attester_role, profile->attester_role_len);

    if (challenge->unit_scope == VOS_ATLS_SCOPE_UNIT) {
        const struct vos_atls_alias_entry *alias =
            find_alias(broker, ctx->origin, ctx->origin_len, ctx->unit_id);
        if (alias == NULL) {
            return VOS_ATLS_ERR_ALIAS;
        }
        ev.has_alias = 1u;
        ev.alias_len = alias->alias_len;
        copy_bytes(ev.alias, alias->alias, alias->alias_len);
    }

    uint8_t body_buf[VOS_ATLS_MAX_EVIDENCE_WIRE_BYTES];
    size_t body_len = 0u;
    const enum vos_atls_status bst =
        encode_evidence_body(profile, &ev, body_buf, sizeof(body_buf), &body_len);
    if (bst != VOS_ATLS_OK) {
        return bst;
    }

    const enum vos_atls_status mst =
        compute_evidence_mac(broker->hmac_key, body_buf, body_len, ev.seal_mac);
    if (mst != VOS_ATLS_OK) {
        return mst;
    }

    if (out_wire != NULL) {
        if (out_wire_len == NULL) {
            return VOS_ATLS_ERR_INVALID;
        }
        const enum vos_atls_status est =
            vos_atls_encode_evidence(profile, &ev, out_wire, out_wire_cap, out_wire_len);
        if (est != VOS_ATLS_OK) {
            return est;
        }
    }

    broker->account_used[credential->account_id] += 1u;
    if (out_evidence != NULL) {
        *out_evidence = ev;
    }
    return VOS_ATLS_OK;
}

void vos_atls_connection_init(struct vos_atls_connection *conn,
                              const struct vos_atls_protected_context *initial_ctx)
{
    if (conn == NULL) {
        return;
    }
    zero_bytes((uint8_t *)conn, sizeof(*conn));
    conn->phase = VOS_ATLS_PHASE_FRESH;
    if (initial_ctx != NULL) {
        conn->ctx = *initial_ctx;
    }
}

enum vos_atls_status vos_atls_begin_appraisal(const struct vos_atls_profile *profile,
                                              const struct vos_atls_appraisal_policy *policy,
                                              struct vos_atls_connection *conn,
                                              const uint8_t *nonce,
                                              uint32_t nonce_len,
                                              uint64_t now,
                                              uint64_t deadline,
                                              uint8_t *out_challenge_wire,
                                              size_t cap,
                                              size_t *out_len)
{
    if (conn == NULL) {
        return VOS_ATLS_ERR_INVALID;
    }
    if (conn->phase != VOS_ATLS_PHASE_FRESH) {
        return VOS_ATLS_ERR_PHASE;
    }
    if (!vos_atls_profile_bounded(profile)) {
        conn->phase = VOS_ATLS_PHASE_CLOSED;
        return VOS_ATLS_ERR_BOUNDS;
    }
    if (!vos_atls_policy_valid(policy)) {
        conn->phase = VOS_ATLS_PHASE_CLOSED;
        return VOS_ATLS_ERR_POLICY;
    }
    if (!vos_atls_context_usable(&conn->ctx)) {
        conn->phase = VOS_ATLS_PHASE_CLOSED;
        return VOS_ATLS_ERR_INELIGIBLE_CONTEXT;
    }
    if (nonce == NULL || nonce_len == 0u || nonce_len > VOS_ATLS_MAX_NONCE_BYTES) {
        conn->phase = VOS_ATLS_PHASE_CLOSED;
        return VOS_ATLS_ERR_INVALID;
    }
    if (now >= deadline) {
        conn->phase = VOS_ATLS_PHASE_CLOSED;
        return VOS_ATLS_ERR_DEADLINE;
    }
    if (nonce_in_history(conn, nonce, nonce_len)) {
        conn->phase = VOS_ATLS_PHASE_CLOSED;
        return VOS_ATLS_ERR_NONCE_REPLAY;
    }
    if (context_in_history(conn, conn->ctx.context_id)) {
        conn->phase = VOS_ATLS_PHASE_CLOSED;
        return VOS_ATLS_ERR_SPENT_CONTEXT;
    }
    if (conn->used_nonce_count >= VOS_ATLS_MAX_USED_NONCES ||
        conn->used_context_count >= VOS_ATLS_MAX_USED_CONTEXTS) {
        conn->phase = VOS_ATLS_PHASE_CLOSED;
        return VOS_ATLS_ERR_HISTORY_FULL;
    }

    struct vos_atls_challenge pending;
    zero_bytes((uint8_t *)&pending, sizeof(pending));
    pending.unit_scope = policy->unit_policy;
    pending.nonce_len = nonce_len;
    copy_bytes(pending.nonce, nonce, nonce_len);
    pending.origin_len = conn->ctx.origin_len;
    copy_bytes(pending.origin, conn->ctx.origin, conn->ctx.origin_len);
    pending.domain_len = profile->domain_len;
    copy_bytes(pending.domain, profile->domain, profile->domain_len);

    if (out_challenge_wire != NULL) {
        if (out_len == NULL) {
            conn->phase = VOS_ATLS_PHASE_CLOSED;
            return VOS_ATLS_ERR_INVALID;
        }
        const enum vos_atls_status cst =
            encode_challenge_into(profile, &pending, out_challenge_wire, cap, out_len);
        if (cst != VOS_ATLS_OK) {
            conn->phase = VOS_ATLS_PHASE_CLOSED;
            return cst;
        }
    } else {
        const size_t needed = VOS_ATLS_CHAL_HDR_BYTES + (size_t)pending.nonce_len +
                              (size_t)pending.origin_len + (size_t)pending.domain_len;
        if (needed > (size_t)profile->challenge_bound) {
            conn->phase = VOS_ATLS_PHASE_CLOSED;
            return VOS_ATLS_ERR_BOUNDS;
        }
    }

    conn->used_nonces[conn->used_nonce_count].len = nonce_len;
    copy_bytes(conn->used_nonces[conn->used_nonce_count].bytes, nonce, nonce_len);
    conn->used_nonce_count += 1u;

    conn->used_contexts[conn->used_context_count] = conn->ctx.context_id;
    conn->used_context_count += 1u;

    conn->pending_challenge = pending;
    conn->pending_deadline = deadline;
    conn->phase = VOS_ATLS_PHASE_WAITING;
    return VOS_ATLS_OK;
}

enum vos_atls_status vos_atls_decide(const struct vos_atls_profile *profile,
                                     const struct vos_atls_appraisal_policy *policy,
                                     const uint8_t hmac_key[VOS_CRYPTO_KEY_BYTES_256],
                                     struct vos_atls_connection *conn,
                                     uint64_t now,
                                     const uint8_t *evidence_wire,
                                     size_t evidence_wire_len)
{
    if (conn == NULL) {
        return VOS_ATLS_ERR_INVALID;
    }
    if (conn->phase != VOS_ATLS_PHASE_WAITING) {
        conn->phase = VOS_ATLS_PHASE_CLOSED;
        return VOS_ATLS_ERR_PHASE;
    }

    /* Consume the single attempt before validating evidence; there is no retry. */
    conn->phase = VOS_ATLS_PHASE_CLOSED;

    if (!vos_atls_profile_bounded(profile)) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    if (!vos_atls_policy_valid(policy) || hmac_key == NULL) {
        return VOS_ATLS_ERR_POLICY;
    }
    if (!vos_atls_context_usable(&conn->ctx)) {
        return VOS_ATLS_ERR_INELIGIBLE_CONTEXT;
    }
    if (now >= conn->pending_deadline) {
        return VOS_ATLS_ERR_DEADLINE;
    }
    if (evidence_wire == NULL || evidence_wire_len == 0u) {
        return VOS_ATLS_ERR_WIRE_FORMAT;
    }
    if (evidence_wire_len > (size_t)profile->evidence_bound) {
        return VOS_ATLS_ERR_BOUNDS;
    }

    struct vos_atls_evidence ev;
    const enum vos_atls_status dst =
        vos_atls_decode_evidence(profile, evidence_wire, evidence_wire_len, &ev);
    if (dst != VOS_ATLS_OK) {
        return dst;
    }

    uint8_t body_buf[VOS_ATLS_MAX_EVIDENCE_WIRE_BYTES];
    size_t body_len = 0u;
    const enum vos_atls_status bst =
        encode_evidence_body(profile, &ev, body_buf, sizeof(body_buf), &body_len);
    if (bst != VOS_ATLS_OK) {
        return bst;
    }

    uint8_t expected_mac[VOS_ATLS_DIGEST_BYTES];
    if (compute_evidence_mac(hmac_key, body_buf, body_len, expected_mac) != VOS_ATLS_OK) {
        return VOS_ATLS_ERR_AUTHENTICITY;
    }
    if (!equal_bytes_ct(expected_mac, ev.seal_mac, VOS_ATLS_DIGEST_BYTES)) {
        return VOS_ATLS_ERR_AUTHENTICITY;
    }

    if (!challenges_equal(&ev.challenge, &conn->pending_challenge)) {
        return VOS_ATLS_ERR_CHALLENGE_MISMATCH;
    }
    if (!equal_bytes_ct(ev.exporter, conn->ctx.exporter, VOS_ATLS_EXPORTER_BYTES)) {
        return VOS_ATLS_ERR_EXPORTER_MISMATCH;
    }
    if (!bytes_equal_exact(ev.role, ev.role_len,
                           profile->attester_role, profile->attester_role_len,
                           VOS_ATLS_MAX_ROLE_BYTES) ||
        !bytes_equal_exact(ev.principal, ev.principal_len,
                           policy->required_principal, policy->required_principal_len,
                           VOS_ATLS_MAX_PRINCIPAL_BYTES) ||
        !generation_approved(policy, ev.generation)) {
        return VOS_ATLS_ERR_POLICY;
    }

    if (policy->unit_policy == 0u) {
        if (ev.has_alias != 0u) {
            return VOS_ATLS_ERR_IDENTITY_SCOPE;
        }
    } else {
        if (ev.has_alias != 1u ||
            !bytes_equal_exact(ev.alias, ev.alias_len,
                               policy->expected_alias, policy->expected_alias_len,
                               VOS_ATLS_MAX_ALIAS_BYTES)) {
            return VOS_ATLS_ERR_IDENTITY_SCOPE;
        }
    }

    conn->phase = VOS_ATLS_PHASE_OPEN;
    return VOS_ATLS_OK;
}

enum vos_atls_status vos_atls_fetch_one(const struct vos_atls_profile *profile,
                                        struct vos_atls_connection *conn,
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
    if (conn == NULL) {
        return VOS_ATLS_ERR_INVALID;
    }
    const enum vos_atls_phase prev_phase = conn->phase;
    conn->phase = VOS_ATLS_PHASE_CLOSED;

    if (prev_phase != VOS_ATLS_PHASE_OPEN) {
        return VOS_ATLS_ERR_PHASE;
    }
    if (!vos_atls_profile_bounded(profile)) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    if (!vos_atls_context_usable(&conn->ctx)) {
        return VOS_ATLS_ERR_INELIGIBLE_CONTEXT;
    }
    if (now >= conn->pending_deadline) {
        return VOS_ATLS_ERR_DEADLINE;
    }
    if (req_wire == NULL || out_reply_wire == NULL || out_reply_len == NULL) {
        return VOS_ATLS_ERR_INVALID;
    }

    struct vos_atls_fetch_request req;
    const enum vos_atls_status rst =
        vos_atls_decode_fetch_request(profile, req_wire, req_wire_len, &req);
    if (rst != VOS_ATLS_OK) {
        return rst;
    }
    if (object_len > profile->object_bound || object_len > VOS_ATLS_MAX_OBJECT_BYTES ||
        (object_len > 0u && object_bytes == NULL)) {
        return VOS_ATLS_ERR_BOUNDS;
    }
    if (manifest_authenticated == 0u || object_matches == 0u) {
        return VOS_ATLS_ERR_FETCH;
    }

    uint8_t obj_digest[VOS_ATLS_DIGEST_BYTES];
    if (vos_sha256(object_bytes, object_len, obj_digest) != 1 ||
        !equal_bytes_ct(obj_digest, req.expected_digest, VOS_ATLS_DIGEST_BYTES)) {
        return VOS_ATLS_ERR_FETCH;
    }

    struct vos_atls_fetch_reply rep;
    zero_bytes((uint8_t *)&rep, sizeof(rep));
    rep.status = VOS_ATLS_REPLY_OK;
    rep.object_id_len = req.object_id_len;
    copy_bytes(rep.object_id, req.object_id, req.object_id_len);
    rep.object_len = object_len;
    if (object_len > 0u) {
        copy_bytes(rep.object_bytes, object_bytes, object_len);
    }
    copy_bytes(rep.object_sha256, obj_digest, VOS_ATLS_DIGEST_BYTES);

    return vos_atls_encode_fetch_reply(profile, &rep, out_reply_wire, cap, out_reply_len);
}

enum vos_atls_status vos_atls_reconnect(struct vos_atls_connection *conn,
                                        const struct vos_atls_protected_context *new_ctx)
{
    if (conn == NULL || new_ctx == NULL) {
        return VOS_ATLS_ERR_INVALID;
    }
    if (new_ctx->context_id == conn->ctx.context_id ||
        context_in_history(conn, new_ctx->context_id)) {
        conn->phase = VOS_ATLS_PHASE_CLOSED;
        return VOS_ATLS_ERR_SPENT_CONTEXT;
    }

    conn->ctx = *new_ctx;
    conn->phase = VOS_ATLS_PHASE_FRESH;
    conn->pending_deadline = 0u;
    zero_bytes((uint8_t *)&conn->pending_challenge, sizeof(conn->pending_challenge));
    return VOS_ATLS_OK;
}

void vos_atls_close(struct vos_atls_connection *conn)
{
    if (conn == NULL) {
        return;
    }
    conn->phase = VOS_ATLS_PHASE_CLOSED;
}
