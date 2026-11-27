// SPDX-License-Identifier: Apache-2.0
#include "vos_witness_validator.h"

#include <stdio.h>
#include <string.h>

#define CHECK(cond, msg)                                                      \
    do {                                                                      \
        if (!(cond)) {                                                        \
            fprintf(stderr, "FAIL (%s:%d): %s\n", __FILE__, __LINE__, (msg)); \
            return 1;                                                         \
        }                                                                     \
    } while (0)

static struct vos_wv_hash make_hash(uint8_t tag)
{
    struct vos_wv_hash h;
    for (size_t i = 0u; i < VOS_WV_DIGEST_BYTES; ++i) {
        h.bytes[i] = (uint8_t)(tag ^ (uint8_t)i);
    }
    return h;
}

static void fill_key(uint64_t witness_id, uint8_t out[VOS_WV_KEY_BYTES])
{
    for (size_t i = 0u; i < VOS_WV_KEY_BYTES; ++i) {
        const uint8_t v = (uint8_t)((witness_id * 17u + i) & 0xFFu);
        out[i] = (v == 0u) ? 1u : v;
    }
}

static void fill_bootstrap_key(uint8_t out[VOS_WV_KEY_BYTES])
{
    for (size_t i = 0u; i < VOS_WV_KEY_BYTES; ++i) {
        out[i] = (uint8_t)(0xB0u + i);
    }
}

static struct vos_wv_policy make_policy(uint64_t trust_scope,
                                        uint64_t epoch,
                                        uint32_t n,
                                        uint32_t k,
                                        uint32_t f,
                                        uint64_t id_base)
{
    struct vos_wv_policy p;
    memset(&p, 0, sizeof(p));
    p.trust_scope = trust_scope;
    p.epoch = epoch;
    p.n = n;
    p.k = k;
    p.f = f;
    for (uint32_t i = 0u; i < n; ++i) {
        p.witnesses[i].witness_id = id_base + i;
        fill_key(id_base + i, p.witnesses[i].verify_key);
    }
    return p;
}

static struct vos_wv_checkpoint make_checkpoint(const struct vos_wv_hash *entries,
                                                uint32_t count)
{
    struct vos_wv_checkpoint cp;
    memset(&cp, 0, sizeof(cp));
    cp.entry_count = count;
    for (uint32_t i = 0u; i < count; ++i) {
        cp.entries[i] = entries[i];
    }
    return cp;
}

static void put_le32_t(uint8_t *dst, uint32_t value)
{
    for (uint32_t i = 0u; i < 4u; ++i) {
        dst[i] = (uint8_t)(value >> (8u * i));
    }
}

static void put_le64_t(uint8_t *dst, uint64_t value)
{
    for (uint32_t i = 0u; i < 8u; ++i) {
        dst[i] = (uint8_t)(value >> (8u * i));
    }
}

static size_t encode_policy_wire(const struct vos_wv_policy *p,
                                 uint8_t *out,
                                 size_t cap)
{
    const size_t need = 36u + (size_t)p->n * 40u;
    if (need > cap) {
        return 0u;
    }
    memcpy(out, "VOSWTP01", 8u);
    put_le64_t(out + 8u, p->trust_scope);
    put_le64_t(out + 16u, p->epoch);
    put_le32_t(out + 24u, p->n);
    put_le32_t(out + 28u, p->k);
    put_le32_t(out + 32u, p->f);
    size_t off = 36u;
    for (uint32_t i = 0u; i < p->n; ++i) {
        put_le64_t(out + off, p->witnesses[i].witness_id);
        memcpy(out + off + 8u, p->witnesses[i].verify_key, VOS_WV_KEY_BYTES);
        off += 40u;
    }
    return off;
}

static size_t encode_checkpoint_wire(const struct vos_wv_checkpoint *cp,
                                     uint8_t *out,
                                     size_t cap)
{
    const size_t need = 12u + (size_t)cp->entry_count * VOS_WV_DIGEST_BYTES;
    if (need > cap) {
        return 0u;
    }
    memcpy(out, "VOSWTC01", 8u);
    put_le32_t(out + 8u, cp->entry_count);
    size_t off = 12u;
    for (uint32_t i = 0u; i < cp->entry_count; ++i) {
        memcpy(out + off, cp->entries[i].bytes, VOS_WV_DIGEST_BYTES);
        off += VOS_WV_DIGEST_BYTES;
    }
    return off;
}

static size_t encode_signature_wire(const struct vos_wv_signature *sig,
                                    uint8_t out[VOS_WV_SIGNATURE_WIRE_BYTES])
{
    memcpy(out, "VOSWIT01", 8u);
    put_le32_t(out + 8u, sig->stmt_kind);
    put_le64_t(out + 12u, sig->trust_scope);
    put_le64_t(out + 20u, sig->epoch);
    memcpy(out + 28u, sig->policy_digest.bytes, VOS_WV_DIGEST_BYTES);
    memcpy(out + 60u, sig->checkpoint_digest.bytes, VOS_WV_DIGEST_BYTES);
    memcpy(out + 92u, sig->transition_digest.bytes, VOS_WV_DIGEST_BYTES);
    put_le64_t(out + 124u, sig->signer_id);
    memcpy(out + 132u, sig->signer_key, VOS_WV_KEY_BYTES);
    memcpy(out + 164u, sig->mac, VOS_WV_DIGEST_BYTES);
    return VOS_WV_SIGNATURE_WIRE_BYTES;
}

static size_t encode_certificate_wire(const struct vos_wv_signature *sigs,
                                      uint32_t count,
                                      uint8_t *out,
                                      size_t cap)
{
    const size_t need = 12u + (size_t)count * VOS_WV_SIGNATURE_WIRE_BYTES;
    if (need > cap) {
        return 0u;
    }
    memcpy(out, "VOSWTS01", 8u);
    put_le32_t(out + 8u, count);
    size_t off = 12u;
    for (uint32_t i = 0u; i < count; ++i) {
        encode_signature_wire(&sigs[i], out + off);
        off += VOS_WV_SIGNATURE_WIRE_BYTES;
    }
    return off;
}

static size_t encode_transition_wire(const struct vos_wv_transition *tr,
                                     uint8_t *out,
                                     size_t cap)
{
    uint8_t old_buf[700];
    uint8_t new_buf[700];
    uint8_t cp_buf[600];
    const size_t old_len = encode_policy_wire(&tr->old_policy, old_buf, sizeof(old_buf));
    const size_t new_len = encode_policy_wire(&tr->new_policy, new_buf, sizeof(new_buf));
    const size_t cp_len = encode_checkpoint_wire(&tr->anchor, cp_buf, sizeof(cp_buf));
    const size_t need = 8u + 12u + old_len + new_len + cp_len;
    if (old_len == 0u || new_len == 0u || cp_len == 0u || need > cap) {
        return 0u;
    }
    memcpy(out, "VOSWTT01", 8u);
    size_t off = 8u;
    put_le32_t(out + off, (uint32_t)old_len);
    off += 4u;
    memcpy(out + off, old_buf, old_len);
    off += old_len;
    put_le32_t(out + off, (uint32_t)new_len);
    off += 4u;
    memcpy(out + off, new_buf, new_len);
    off += new_len;
    put_le32_t(out + off, (uint32_t)cp_len);
    off += 4u;
    memcpy(out + off, cp_buf, cp_len);
    off += cp_len;
    return off;
}

static struct vos_wv_signature sign_stmt(const struct vos_wv_policy *policy,
                                         uint32_t idx,
                                         enum vos_wv_stmt_kind kind,
                                         const struct vos_wv_checkpoint *cp,
                                         const struct vos_wv_transition *tr)
{
    struct vos_wv_signature sig;
    uint8_t wire[VOS_WV_SIGNATURE_WIRE_BYTES];

    memset(&sig, 0, sizeof(sig));
    sig.stmt_kind = (uint32_t)kind;
    sig.trust_scope = policy->trust_scope;
    sig.epoch = policy->epoch;
    (void)vos_wv_policy_digest(policy, &sig.policy_digest);
    (void)vos_wv_checkpoint_digest(cp, &sig.checkpoint_digest);
    if (kind == VOS_WV_STMT_TERMINAL && tr != NULL) {
        (void)vos_wv_transition_digest(tr, &sig.transition_digest);
    }
    sig.signer_id = policy->witnesses[idx].witness_id;
    memcpy(sig.signer_key, policy->witnesses[idx].verify_key, VOS_WV_KEY_BYTES);

    encode_signature_wire(&sig, wire);
    (void)vos_hmac_sha256(sig.signer_key,
                          VOS_WV_KEY_BYTES,
                          wire,
                          VOS_WV_SIGNATURE_WIRE_BYTES - VOS_WV_DIGEST_BYTES,
                          sig.mac);
    return sig;
}

static struct vos_wv_rebootstrap make_signed_rebootstrap(
    const struct vos_wv_policy *old_pol,
    const struct vos_wv_policy *new_pol,
    const struct vos_wv_checkpoint *anchor,
    const char *assumptions_text,
    const uint8_t bootstrap_key[VOS_WV_KEY_BYTES])
{
    struct vos_wv_rebootstrap rb;
    uint8_t mac_msg[8u + (3u * VOS_WV_DIGEST_BYTES) + 4u + VOS_WV_MAX_ASSUMPTIONS_BYTES];
    struct vos_wv_hash old_dig;
    struct vos_wv_hash new_dig;
    struct vos_wv_hash anchor_dig;
    const size_t alen = strlen(assumptions_text);

    memset(&rb, 0, sizeof(rb));
    rb.old_policy = *old_pol;
    rb.new_policy = *new_pol;
    rb.anchor = *anchor;
    rb.assumptions_len = (uint32_t)alen;
    memcpy(rb.assumptions, assumptions_text, alen);

    (void)vos_wv_policy_digest(old_pol, &old_dig);
    (void)vos_wv_policy_digest(new_pol, &new_dig);
    (void)vos_wv_checkpoint_digest(anchor, &anchor_dig);

    memcpy(mac_msg, "VOSWTR01", 8u);
    memcpy(mac_msg + 8u, old_dig.bytes, VOS_WV_DIGEST_BYTES);
    memcpy(mac_msg + 8u + VOS_WV_DIGEST_BYTES, new_dig.bytes, VOS_WV_DIGEST_BYTES);
    memcpy(mac_msg + 8u + (2u * VOS_WV_DIGEST_BYTES),
           anchor_dig.bytes,
           VOS_WV_DIGEST_BYTES);
    put_le32_t(mac_msg + 8u + (3u * VOS_WV_DIGEST_BYTES), rb.assumptions_len);
    memcpy(mac_msg + 12u + (3u * VOS_WV_DIGEST_BYTES), rb.assumptions, alen);

    (void)vos_hmac_sha256(bootstrap_key,
                          VOS_WV_KEY_BYTES,
                          mac_msg,
                          12u + (3u * VOS_WV_DIGEST_BYTES) + alen,
                          rb.auth_mac);
    return rb;
}

static size_t encode_rebootstrap_wire(const struct vos_wv_rebootstrap *rb,
                                      uint8_t *out,
                                      size_t cap)
{
    uint8_t old_buf[700];
    uint8_t new_buf[700];
    uint8_t cp_buf[600];
    const size_t old_len = encode_policy_wire(&rb->old_policy, old_buf, sizeof(old_buf));
    const size_t new_len = encode_policy_wire(&rb->new_policy, new_buf, sizeof(new_buf));
    const size_t cp_len = encode_checkpoint_wire(&rb->anchor, cp_buf, sizeof(cp_buf));
    const size_t need = 8u + 16u + old_len + new_len + cp_len +
                        rb->assumptions_len + VOS_WV_DIGEST_BYTES;
    if (old_len == 0u || new_len == 0u || cp_len == 0u || need > cap) {
        return 0u;
    }
    memcpy(out, "VOSWTR01", 8u);
    size_t off = 8u;
    put_le32_t(out + off, (uint32_t)old_len);
    off += 4u;
    memcpy(out + off, old_buf, old_len);
    off += old_len;
    put_le32_t(out + off, (uint32_t)new_len);
    off += 4u;
    memcpy(out + off, new_buf, new_len);
    off += new_len;
    put_le32_t(out + off, (uint32_t)cp_len);
    off += 4u;
    memcpy(out + off, cp_buf, cp_len);
    off += cp_len;
    put_le32_t(out + off, rb->assumptions_len);
    off += 4u;
    memcpy(out + off, rb->assumptions, rb->assumptions_len);
    off += rb->assumptions_len;
    memcpy(out + off, rb->auth_mac, VOS_WV_DIGEST_BYTES);
    off += VOS_WV_DIGEST_BYTES;
    return off;
}

static int test_pinned_python_vectors_and_wire_parsers(void)
{
    static const uint8_t expected_pol_dig[VOS_WV_DIGEST_BYTES] = {
        0xcdu, 0x22u, 0x42u, 0x80u, 0xc8u, 0xa9u, 0x3fu, 0xf9u,
        0x3du, 0xd9u, 0xa0u, 0x5eu, 0xa5u, 0x7au, 0x60u, 0x8au,
        0xc4u, 0x76u, 0x35u, 0xc9u, 0xd5u, 0x17u, 0x80u, 0x25u,
        0x06u, 0xc2u, 0xfdu, 0xceu, 0xf3u, 0xcfu, 0xeau, 0x47u
    };
    static const uint8_t expected_cp_dig[VOS_WV_DIGEST_BYTES] = {
        0xc8u, 0x90u, 0xf1u, 0xebu, 0x4au, 0x08u, 0xd7u, 0x55u,
        0xf4u, 0xa4u, 0x3eu, 0xdbu, 0x37u, 0xb0u, 0xd0u, 0xecu,
        0x73u, 0x62u, 0xe0u, 0x48u, 0x6cu, 0x31u, 0x55u, 0xe6u,
        0x3du, 0x5eu, 0xd9u, 0x95u, 0x18u, 0xa0u, 0x94u, 0xcau
    };
    static const uint8_t expected_sig_mac[VOS_WV_DIGEST_BYTES] = {
        0xd6u, 0x84u, 0x91u, 0x9fu, 0x8du, 0xf6u, 0xe6u, 0x1bu,
        0xc6u, 0x63u, 0x7fu, 0x37u, 0xfau, 0xb4u, 0x19u, 0x1bu,
        0x2cu, 0xe1u, 0xc3u, 0x77u, 0x52u, 0x2au, 0x7cu, 0x67u,
        0x48u, 0xe9u, 0x82u, 0xb7u, 0xdau, 0xaeu, 0xa8u, 0x9fu
    };

    const struct vos_wv_policy pol = make_policy(1u, 0u, 4u, 3u, 1u, 10u);
    const struct vos_wv_hash entries[2] = { make_hash(0x11u), make_hash(0x22u) };
    const struct vos_wv_checkpoint cp = make_checkpoint(entries, 2u);
    const struct vos_wv_signature sig0 = sign_stmt(&pol, 0u, VOS_WV_STMT_PLAIN, &cp, NULL);

    struct vos_wv_hash pd;
    struct vos_wv_hash cd;
    CHECK(vos_wv_policy_digest(&pol, &pd) == VOS_WV_OK, "policy digest");
    CHECK(memcmp(pd.bytes, expected_pol_dig, VOS_WV_DIGEST_BYTES) == 0,
          "policy digest matches Python vector");
    CHECK(vos_wv_checkpoint_digest(&cp, &cd) == VOS_WV_OK, "checkpoint digest");
    CHECK(memcmp(cd.bytes, expected_cp_dig, VOS_WV_DIGEST_BYTES) == 0,
          "checkpoint digest matches Python vector");
    CHECK(memcmp(sig0.mac, expected_sig_mac, VOS_WV_DIGEST_BYTES) == 0,
          "VOSWIT01 MAC matches Python vector");

    /* Roundtrip wire parsing + truncated + trailing bytes + over-limit */
    uint8_t pol_wire[700];
    const size_t pol_len = encode_policy_wire(&pol, pol_wire, sizeof(pol_wire));
    struct vos_wv_policy parsed_pol;
    CHECK(vos_wv_parse_policy(pol_wire, pol_len, &parsed_pol) == VOS_WV_OK,
          "parse valid policy");
    CHECK(vos_wv_parse_policy(pol_wire, pol_len - 1u, &parsed_pol) == VOS_WV_ERR_MALFORMED_WIRE,
          "reject truncated policy");
    pol_wire[pol_len] = 0xAAu;
    CHECK(vos_wv_parse_policy(pol_wire, pol_len + 1u, &parsed_pol) == VOS_WV_ERR_TRAILING_BYTES,
          "reject trailing wire bytes in policy");
    pol_wire[0] = 'X';
    CHECK(vos_wv_parse_policy(pol_wire, pol_len, &parsed_pol) == VOS_WV_ERR_MALFORMED_WIRE,
          "reject bad policy magic");
    pol_wire[0] = 'V';
    put_le32_t(pol_wire + 24u, VOS_WV_MAX_WITNESSES + 1u);
    CHECK(vos_wv_parse_policy(pol_wire, pol_len, &parsed_pol) == VOS_WV_ERR_OVER_LIMIT,
          "reject over-limit policy witnesses");

    uint8_t cp_wire[600];
    const size_t cp_len = encode_checkpoint_wire(&cp, cp_wire, sizeof(cp_wire));
    struct vos_wv_checkpoint parsed_cp;
    CHECK(vos_wv_parse_checkpoint(cp_wire, cp_len, &parsed_cp) == VOS_WV_OK,
          "parse valid checkpoint");
    CHECK(vos_wv_parse_checkpoint(cp_wire, cp_len - 1u, &parsed_cp) == VOS_WV_ERR_MALFORMED_WIRE,
          "reject truncated checkpoint");
    cp_wire[cp_len] = 0x55u;
    CHECK(vos_wv_parse_checkpoint(cp_wire, cp_len + 1u, &parsed_cp) == VOS_WV_ERR_TRAILING_BYTES,
          "reject trailing wire bytes in checkpoint");
    put_le32_t(cp_wire + 8u, VOS_WV_MAX_CHECKPOINT_ENTRIES + 1u);
    CHECK(vos_wv_parse_checkpoint(cp_wire, cp_len, &parsed_cp) == VOS_WV_ERR_OVER_LIMIT,
          "reject over-limit checkpoint entries");

    uint8_t sig_wire[VOS_WV_SIGNATURE_WIRE_BYTES + 4u];
    encode_signature_wire(&sig0, sig_wire);
    struct vos_wv_signature parsed_sig;
    CHECK(vos_wv_parse_signature(sig_wire, VOS_WV_SIGNATURE_WIRE_BYTES, &parsed_sig) == VOS_WV_OK,
          "parse valid signature");
    CHECK(vos_wv_parse_signature(sig_wire, VOS_WV_SIGNATURE_WIRE_BYTES - 1u, &parsed_sig)
          == VOS_WV_ERR_MALFORMED_WIRE, "reject truncated signature");
    sig_wire[VOS_WV_SIGNATURE_WIRE_BYTES] = 0x77u;
    CHECK(vos_wv_parse_signature(sig_wire, VOS_WV_SIGNATURE_WIRE_BYTES + 1u, &parsed_sig)
          == VOS_WV_ERR_TRAILING_BYTES, "reject trailing wire bytes in signature");
    sig_wire[92u] ^= 1u; /* non-zero transition_digest in PLAIN signature */
    CHECK(vos_wv_parse_signature(sig_wire, VOS_WV_SIGNATURE_WIRE_BYTES, &parsed_sig)
          == VOS_WV_ERR_BAD_BINDING, "reject plain signature with transition digest");

    const struct vos_wv_signature sigs[3] = {
        sig0,
        sign_stmt(&pol, 1u, VOS_WV_STMT_PLAIN, &cp, NULL),
        sign_stmt(&pol, 2u, VOS_WV_STMT_PLAIN, &cp, NULL)
    };
    uint8_t cert_wire[12u + 3u * VOS_WV_SIGNATURE_WIRE_BYTES + 4u];
    const size_t cert_len = encode_certificate_wire(sigs, 3u, cert_wire, sizeof(cert_wire));
    struct vos_wv_signature parsed_sigs[VOS_WV_MAX_SIGNATURES];
    size_t parsed_count = 0u;
    CHECK(vos_wv_parse_certificate(cert_wire, cert_len, parsed_sigs,
                                   VOS_WV_MAX_SIGNATURES, &parsed_count) == VOS_WV_OK &&
          parsed_count == 3u, "parse valid certificate bundle");
    cert_wire[cert_len] = 0x99u;
    CHECK(vos_wv_parse_certificate(cert_wire, cert_len + 1u, parsed_sigs,
                                   VOS_WV_MAX_SIGNATURES, &parsed_count)
          == VOS_WV_ERR_TRAILING_BYTES, "reject trailing wire bytes in certificate");

    /* Transition & Rebootstrap wire roundtrip + trailing bytes */
    const struct vos_wv_policy next_pol = make_policy(1u, 1u, 4u, 3u, 1u, 40u);
    const struct vos_wv_transition tr = { pol, next_pol, cp };
    uint8_t tr_wire[2200];
    const size_t tr_len = encode_transition_wire(&tr, tr_wire, sizeof(tr_wire));
    struct vos_wv_transition parsed_tr;
    CHECK(vos_wv_parse_transition(tr_wire, tr_len, &parsed_tr) == VOS_WV_OK,
          "parse valid transition");
    tr_wire[tr_len] = 0x11u;
    CHECK(vos_wv_parse_transition(tr_wire, tr_len + 1u, &parsed_tr) == VOS_WV_ERR_TRAILING_BYTES,
          "reject trailing wire bytes in transition");

    uint8_t boot_key[VOS_WV_KEY_BYTES];
    fill_bootstrap_key(boot_key);
    const struct vos_wv_policy rb_pol = make_policy(8u, 0u, 3u, 3u, 1u, 60u);
    const struct vos_wv_rebootstrap rb = make_signed_rebootstrap(
        &pol, &rb_pol, &cp, "fresh identities and anchors", boot_key);
    uint8_t rb_wire[2600];
    const size_t rb_len = encode_rebootstrap_wire(&rb, rb_wire, sizeof(rb_wire));
    struct vos_wv_rebootstrap parsed_rb;
    CHECK(vos_wv_parse_rebootstrap(rb_wire, rb_len, &parsed_rb) == VOS_WV_OK,
          "parse valid rebootstrap");
    rb_wire[rb_len] = 0x22u;
    CHECK(vos_wv_parse_rebootstrap(rb_wire, rb_len + 1u, &parsed_rb) == VOS_WV_ERR_TRAILING_BYTES,
          "reject trailing wire bytes in rebootstrap");

    return 0;
}

static int test_policy_safety_and_one_of_two_refusal(void)
{
    /* Duplicate witness ID or key or zero key refused */
    struct vos_wv_policy dup_id = make_policy(1u, 0u, 3u, 3u, 1u, 10u);
    dup_id.witnesses[1].witness_id = dup_id.witnesses[0].witness_id;
    CHECK(!vos_wv_policy_is_wellformed(&dup_id), "refuse duplicate witness_id");

    struct vos_wv_policy dup_key = make_policy(1u, 0u, 3u, 3u, 1u, 10u);
    memcpy(dup_key.witnesses[2].verify_key, dup_key.witnesses[0].verify_key, VOS_WV_KEY_BYTES);
    CHECK(!vos_wv_policy_is_wellformed(&dup_key), "refuse duplicate verify_key");

    struct vos_wv_policy zero_key = make_policy(1u, 0u, 3u, 3u, 1u, 10u);
    memset(zero_key.witnesses[0].verify_key, 0, VOS_WV_KEY_BYTES);
    CHECK(!vos_wv_policy_is_wellformed(&zero_key), "refuse all-zero verify_key");

    /* 1-of-2 is wellformed but unsafe (2*1 == 2+0, NOT >) and refused even with valid MACs */
    const struct vos_wv_policy one_of_two = make_policy(2u, 0u, 2u, 1u, 0u, 20u);
    uint8_t wire_1of2[200];
    const size_t wire_1of2_len = encode_policy_wire(&one_of_two, wire_1of2, sizeof(wire_1of2));
    struct vos_wv_policy parsed_1of2;
    CHECK(vos_wv_parse_policy(wire_1of2, wire_1of2_len, &parsed_1of2) == VOS_WV_OK,
          "1-of-2 parses as wellformed");
    CHECK(vos_wv_policy_is_wellformed(&parsed_1of2) && !vos_wv_policy_is_safe(&parsed_1of2),
          "1-of-2 fails safety inequality 2*K > N+f");

    const struct vos_wv_hash base_h = make_hash(0x10u);
    const struct vos_wv_hash left_entries[2] = { base_h, make_hash(0x21u) };
    const struct vos_wv_hash right_entries[2] = { base_h, make_hash(0x22u) };
    const struct vos_wv_checkpoint left_cp = make_checkpoint(left_entries, 2u);
    const struct vos_wv_checkpoint right_cp = make_checkpoint(right_entries, 2u);

    const struct vos_wv_signature left_sig = sign_stmt(&parsed_1of2, 0u, VOS_WV_STMT_PLAIN, &left_cp, NULL);
    const struct vos_wv_signature right_sig = sign_stmt(&parsed_1of2, 1u, VOS_WV_STMT_PLAIN, &right_cp, NULL);

    CHECK(vos_wv_verify_certificate(&parsed_1of2, VOS_WV_STMT_PLAIN, &left_cp, NULL, &left_sig, 1u)
          == VOS_WV_ERR_UNSAFE_POLICY, "refuse 1-of-2 left split-view despite valid HMAC");
    CHECK(vos_wv_verify_certificate(&parsed_1of2, VOS_WV_STMT_PLAIN, &right_cp, NULL, &right_sig, 1u)
          == VOS_WV_ERR_UNSAFE_POLICY, "refuse 1-of-2 right split-view despite valid HMAC");

    uint8_t boot_key[VOS_WV_KEY_BYTES];
    fill_bootstrap_key(boot_key);
    struct vos_wv_client client;
    const struct vos_wv_checkpoint empty_cp = make_checkpoint(NULL, 0u);
    const struct vos_wv_hash init_gen = make_hash(0x01u);
    CHECK(vos_wv_client_init(&client, &parsed_1of2, &empty_cp, &init_gen, boot_key)
          == VOS_WV_ERR_UNSAFE_POLICY, "refuse 1-of-2 client init");

    /* 2-of-3 with f=1: 2*2 == 3+1 -> unsafe; 3-of-3 with f=1: 2*3 > 3+1 -> safe */
    const struct vos_wv_policy two_of_three = make_policy(3u, 0u, 3u, 2u, 1u, 50u);
    const struct vos_wv_policy three_of_three = make_policy(3u, 0u, 3u, 3u, 1u, 50u);
    CHECK(!vos_wv_policy_is_safe(&two_of_three), "2-of-3 f=1 unsafe");
    CHECK(vos_wv_policy_is_safe(&three_of_three), "3-of-3 f=1 safe");

    return 0;
}

static int test_certificate_binding_and_admission_pin_immutability(void)
{
    const struct vos_wv_policy pol = make_policy(1u, 0u, 4u, 3u, 1u, 10u);
    const struct vos_wv_hash base_h = make_hash(0x10u);
    const struct vos_wv_hash pkg_a = make_hash(0x21u);
    const struct vos_wv_hash pkg_b = make_hash(0x22u);
    const struct vos_wv_hash pkg_missing = make_hash(0x99u);
    const struct vos_wv_hash left_entries[2] = { base_h, pkg_a };
    const struct vos_wv_hash right_entries[2] = { base_h, pkg_b };
    const struct vos_wv_hash both_entries[3] = { base_h, pkg_a, pkg_b };
    const struct vos_wv_checkpoint base_cp = make_checkpoint(&base_h, 1u);
    const struct vos_wv_checkpoint left_cp = make_checkpoint(left_entries, 2u);
    const struct vos_wv_checkpoint right_cp = make_checkpoint(right_entries, 2u);
    const struct vos_wv_checkpoint both_cp = make_checkpoint(both_entries, 3u);

    const struct vos_wv_signature g0 = sign_stmt(&pol, 0u, VOS_WV_STMT_PLAIN, &left_cp, NULL);
    const struct vos_wv_signature g1 = sign_stmt(&pol, 1u, VOS_WV_STMT_PLAIN, &left_cp, NULL);
    const struct vos_wv_signature g2 = sign_stmt(&pol, 2u, VOS_WV_STMT_PLAIN, &left_cp, NULL);

    /* Certificate binding refusals */
    const struct vos_wv_signature under_quorum[2] = { g0, g1 };
    CHECK(vos_wv_verify_certificate(&pol, VOS_WV_STMT_PLAIN, &left_cp, NULL, under_quorum, 2u)
          == VOS_WV_ERR_QUORUM_UNMET, "refuse 2-of-4 under-quorum");

    const struct vos_wv_signature dup_signer[3] = { g0, g1, g0 };
    CHECK(vos_wv_verify_certificate(&pol, VOS_WV_STMT_PLAIN, &left_cp, NULL, dup_signer, 3u)
          == VOS_WV_ERR_DUPLICATE_SIGNER, "refuse duplicate signer");

    const struct vos_wv_signature padded_dup[4] = { g0, g1, g2, g0 };
    CHECK(vos_wv_verify_certificate(&pol, VOS_WV_STMT_PLAIN, &left_cp, NULL, padded_dup, 4u)
          == VOS_WV_ERR_DUPLICATE_SIGNER, "refuse padded duplicate signer");

    struct vos_wv_signature foreign = g2;
    foreign.signer_id = 999u;
    const struct vos_wv_signature with_foreign[3] = { g0, g1, foreign };
    CHECK(vos_wv_verify_certificate(&pol, VOS_WV_STMT_PLAIN, &left_cp, NULL, with_foreign, 3u)
          == VOS_WV_ERR_FOREIGN_SIGNER, "refuse foreign signer");

    /* Wrong key even with valid HMAC under that wrong key */
    struct vos_wv_signature wrong_key = g2;
    wrong_key.signer_key[0] ^= 0xFFu;
    uint8_t wrong_wire[VOS_WV_SIGNATURE_WIRE_BYTES];
    encode_signature_wire(&wrong_key, wrong_wire);
    (void)vos_hmac_sha256(wrong_key.signer_key,
                          VOS_WV_KEY_BYTES,
                          wrong_wire,
                          VOS_WV_SIGNATURE_WIRE_BYTES - VOS_WV_DIGEST_BYTES,
                          wrong_key.mac);
    const struct vos_wv_signature with_wrong_key[3] = { g0, g1, wrong_key };
    CHECK(vos_wv_verify_certificate(&pol, VOS_WV_STMT_PLAIN, &left_cp, NULL, with_wrong_key, 3u)
          == VOS_WV_ERR_KEY_MISMATCH, "refuse wrong signer key");

    struct vos_wv_signature forged = g2;
    forged.mac[0] ^= 0x01u;
    const struct vos_wv_signature with_forged[3] = { g0, g1, forged };
    CHECK(vos_wv_verify_certificate(&pol, VOS_WV_STMT_PLAIN, &left_cp, NULL, with_forged, 3u)
          == VOS_WV_ERR_FORGED_MAC, "refuse forged HMAC");

    struct vos_wv_signature forged3 = sign_stmt(&pol, 3u, VOS_WV_STMT_PLAIN, &left_cp, NULL);
    forged3.mac[0] ^= 0x01u;
    const struct vos_wv_signature padded_forged[4] = { g0, g1, g2, forged3 };
    CHECK(vos_wv_verify_certificate(&pol, VOS_WV_STMT_PLAIN, &left_cp, NULL, padded_forged, 4u)
          == VOS_WV_ERR_FORGED_MAC, "refuse padded forged signature");

    const struct vos_wv_signature other_cp_sig = sign_stmt(&pol, 2u, VOS_WV_STMT_PLAIN, &right_cp, NULL);
    const struct vos_wv_signature with_other_cp[3] = { g0, g1, other_cp_sig };
    CHECK(vos_wv_verify_certificate(&pol, VOS_WV_STMT_PLAIN, &left_cp, NULL, with_other_cp, 3u)
          == VOS_WV_ERR_BAD_BINDING, "refuse signature on different checkpoint");

    const struct vos_wv_policy other_pol = make_policy(1u, 1u, 4u, 3u, 1u, 10u);
    const struct vos_wv_signature other_pol_sig = sign_stmt(&other_pol, 2u, VOS_WV_STMT_PLAIN, &left_cp, NULL);
    const struct vos_wv_signature with_other_pol[3] = { g0, g1, other_pol_sig };
    CHECK(vos_wv_verify_certificate(&pol, VOS_WV_STMT_PLAIN, &left_cp, NULL, with_other_pol, 3u)
          == VOS_WV_ERR_BAD_BINDING, "refuse signature on different policy epoch");

    /* Same scope/epoch/keys, different threshold K: only full policy_digest catches it */
    const struct vos_wv_policy diff_k_pol = make_policy(1u, 0u, 4u, 4u, 1u, 10u);
    const struct vos_wv_signature diff_k_sig = sign_stmt(&diff_k_pol, 2u, VOS_WV_STMT_PLAIN, &left_cp, NULL);
    const struct vos_wv_signature with_diff_k[3] = { g0, g1, diff_k_sig };
    CHECK(vos_wv_verify_certificate(&pol, VOS_WV_STMT_PLAIN, &left_cp, NULL, with_diff_k, 3u)
          == VOS_WV_ERR_BAD_BINDING, "refuse signature on different policy parameters");

    /* Client initialization & admission */
    uint8_t boot_key[VOS_WV_KEY_BYTES];
    fill_bootstrap_key(boot_key);
    struct vos_wv_client client;
    const struct vos_wv_checkpoint empty_cp = make_checkpoint(NULL, 0u);
    const struct vos_wv_hash gen0 = make_hash(0xA0u);
    const struct vos_wv_hash gen1 = make_hash(0xA1u);
    const struct vos_wv_hash gen_bad = make_hash(0xEEu);
    CHECK(vos_wv_client_init(&client, &pol, &empty_cp, &gen0, boot_key) == VOS_WV_OK,
          "init client");

    const struct vos_wv_signature good_left[3] = { g0, g1, g2 };
    CHECK(vos_wv_admit(&client, &left_cp, good_left, 3u, &base_h, &pkg_a, 1u, &gen1) == VOS_WV_OK,
          "admit valid left generation");
    CHECK(memcmp(&client.running_generation, &gen1, sizeof(gen1)) == 0 &&
          client.pinned.entry_count == 2u, "client pinned left checkpoint and gen1");

    /* Every refusal leaves client byte-identical */
    struct vos_wv_client snap = client;

    const struct vos_wv_signature right_sigs[3] = {
        sign_stmt(&pol, 0u, VOS_WV_STMT_PLAIN, &right_cp, NULL),
        sign_stmt(&pol, 1u, VOS_WV_STMT_PLAIN, &right_cp, NULL),
        sign_stmt(&pol, 2u, VOS_WV_STMT_PLAIN, &right_cp, NULL)
    };
    CHECK(vos_wv_admit(&client, &right_cp, right_sigs, 3u, &base_h, &pkg_b, 1u, &gen_bad)
          == VOS_WV_ERR_CHECKPOINT_STALE, "refuse forked checkpoint");
    CHECK(memcmp(&snap, &client, sizeof(client)) == 0, "fork refusal preserved client");

    const struct vos_wv_signature base_sigs[3] = {
        sign_stmt(&pol, 0u, VOS_WV_STMT_PLAIN, &base_cp, NULL),
        sign_stmt(&pol, 1u, VOS_WV_STMT_PLAIN, &base_cp, NULL),
        sign_stmt(&pol, 2u, VOS_WV_STMT_PLAIN, &base_cp, NULL)
    };
    CHECK(vos_wv_admit(&client, &base_cp, base_sigs, 3u, &base_h, NULL, 0u, &gen_bad)
          == VOS_WV_ERR_CHECKPOINT_STALE, "refuse stale prefix checkpoint");
    CHECK(memcmp(&snap, &client, sizeof(client)) == 0, "stale refusal preserved client");

    const struct vos_wv_signature both_sigs[3] = {
        sign_stmt(&pol, 0u, VOS_WV_STMT_PLAIN, &both_cp, NULL),
        sign_stmt(&pol, 1u, VOS_WV_STMT_PLAIN, &both_cp, NULL),
        sign_stmt(&pol, 2u, VOS_WV_STMT_PLAIN, &both_cp, NULL)
    };
    CHECK(vos_wv_admit(&client, &both_cp, both_sigs, 3u, &pkg_missing, &pkg_a, 1u, &gen_bad)
          == VOS_WV_ERR_MISSING_BASE, "refuse missing base_image_root");
    CHECK(memcmp(&snap, &client, sizeof(client)) == 0, "missing base refusal preserved client");

    const struct vos_wv_hash req_pkgs[2] = { pkg_a, pkg_missing };
    CHECK(vos_wv_admit(&client, &both_cp, both_sigs, 3u, &base_h, req_pkgs, 2u, &gen_bad)
          == VOS_WV_ERR_MISSING_PACKAGE, "refuse missing package identity");
    CHECK(memcmp(&snap, &client, sizeof(client)) == 0, "missing package refusal preserved client");

    CHECK(vos_wv_admit(&client, &both_cp, both_sigs, 2u, &base_h, &pkg_a, 1u, &gen_bad)
          == VOS_WV_ERR_QUORUM_UNMET, "refuse under-quorum admit");
    CHECK(memcmp(&snap, &client, sizeof(client)) == 0, "quorum refusal preserved client");

    /* Selective delivery residual: same extending checkpoint admits pkg_a or pkg_b */
    struct vos_wv_client client_b;
    CHECK(vos_wv_client_init(&client_b, &pol, &empty_cp, &gen0, boot_key) == VOS_WV_OK,
          "init client_b");
    const struct vos_wv_hash gen2 = make_hash(0xA2u);
    CHECK(vos_wv_admit(&client, &both_cp, both_sigs, 3u, &base_h, &pkg_a, 1u, &gen1) == VOS_WV_OK,
          "admit variant A on both_cp");
    CHECK(vos_wv_admit(&client_b, &both_cp, both_sigs, 3u, &base_h, &pkg_b, 1u, &gen2) == VOS_WV_OK,
          "admit variant B on both_cp");
    CHECK(memcmp(&client.pinned, &client_b.pinned, sizeof(client.pinned)) == 0 &&
          memcmp(&client.running_generation, &client_b.running_generation, sizeof(gen1)) != 0,
          "selective delivery variants share pin");

    return 0;
}

static int test_transitions_and_rebootstraps(void)
{
    const struct vos_wv_policy old_pol = make_policy(7u, 0u, 4u, 3u, 1u, 30u);
    const struct vos_wv_policy new_pol = make_policy(7u, 1u, 4u, 3u, 1u, 40u);
    const struct vos_wv_policy alt_pol = make_policy(7u, 1u, 4u, 3u, 1u, 70u);
    const struct vos_wv_policy skipped_epoch = make_policy(7u, 2u, 4u, 3u, 1u, 40u);
    const struct vos_wv_policy cross_scope = make_policy(8u, 1u, 4u, 3u, 1u, 40u);
    const struct vos_wv_policy unsafe_new = make_policy(7u, 1u, 2u, 1u, 0u, 40u);

    const struct vos_wv_hash h_anchor = make_hash(0x10u);
    const struct vos_wv_hash h_fork = make_hash(0x41u);
    const struct vos_wv_hash fork_entries[2] = { h_anchor, h_fork };
    const struct vos_wv_checkpoint anchor_cp = make_checkpoint(&h_anchor, 1u);
    const struct vos_wv_checkpoint fork_cp = make_checkpoint(fork_entries, 2u);
    const struct vos_wv_checkpoint empty_cp = make_checkpoint(NULL, 0u);

    const struct vos_wv_transition tr = { old_pol, new_pol, anchor_cp };
    const struct vos_wv_transition alt_tr = { old_pol, alt_pol, anchor_cp };
    const struct vos_wv_transition skip_tr = { old_pol, skipped_epoch, anchor_cp };
    const struct vos_wv_transition scope_tr = { old_pol, cross_scope, anchor_cp };
    const struct vos_wv_transition unsafe_tr = { old_pol, unsafe_new, anchor_cp };

    const struct vos_wv_signature old_plain[3] = {
        sign_stmt(&old_pol, 0u, VOS_WV_STMT_PLAIN, &anchor_cp, NULL),
        sign_stmt(&old_pol, 1u, VOS_WV_STMT_PLAIN, &anchor_cp, NULL),
        sign_stmt(&old_pol, 2u, VOS_WV_STMT_PLAIN, &anchor_cp, NULL)
    };
    const struct vos_wv_signature old_seals[3] = {
        sign_stmt(&old_pol, 0u, VOS_WV_STMT_TERMINAL, &anchor_cp, &tr),
        sign_stmt(&old_pol, 1u, VOS_WV_STMT_TERMINAL, &anchor_cp, &tr),
        sign_stmt(&old_pol, 2u, VOS_WV_STMT_TERMINAL, &anchor_cp, &tr)
    };
    const struct vos_wv_signature alt_seals[3] = {
        sign_stmt(&old_pol, 0u, VOS_WV_STMT_TERMINAL, &anchor_cp, &alt_tr),
        sign_stmt(&old_pol, 1u, VOS_WV_STMT_TERMINAL, &anchor_cp, &alt_tr),
        sign_stmt(&old_pol, 2u, VOS_WV_STMT_TERMINAL, &anchor_cp, &alt_tr)
    };
    const struct vos_wv_signature new_anchor_sigs[3] = {
        sign_stmt(&new_pol, 0u, VOS_WV_STMT_PLAIN, &anchor_cp, NULL),
        sign_stmt(&new_pol, 1u, VOS_WV_STMT_PLAIN, &anchor_cp, NULL),
        sign_stmt(&new_pol, 2u, VOS_WV_STMT_PLAIN, &anchor_cp, NULL)
    };

    uint8_t boot_key[VOS_WV_KEY_BYTES];
    fill_bootstrap_key(boot_key);
    const struct vos_wv_hash gen0 = make_hash(0xA0u);

    struct vos_wv_client client;
    CHECK(vos_wv_client_init(&client, &old_pol, &empty_cp, &gen0, boot_key) == VOS_WV_OK,
          "init transition client");
    struct vos_wv_client snap = client;

    /* Prefix-only transition MUST fail */
    CHECK(vos_wv_transition(&client, &tr, old_plain, 3u, new_anchor_sigs, 3u)
          == VOS_WV_ERR_BAD_BINDING, "refuse prefix-only transition without terminal seals");
    CHECK(memcmp(&snap, &client, sizeof(client)) == 0, "prefix-only refusal preserved client");

    /* Wrong destination seals MUST fail */
    CHECK(vos_wv_transition(&client, &tr, alt_seals, 3u, new_anchor_sigs, 3u)
          == VOS_WV_ERR_BAD_BINDING, "refuse mismatched terminal destination");
    CHECK(memcmp(&snap, &client, sizeof(client)) == 0, "alt-seal refusal preserved client");

    /* Missing new anchor quorum MUST fail */
    CHECK(vos_wv_transition(&client, &tr, old_seals, 3u, new_anchor_sigs, 2u)
          == VOS_WV_ERR_QUORUM_UNMET, "refuse transition without new anchor quorum");
    CHECK(memcmp(&snap, &client, sizeof(client)) == 0, "new-quorum refusal preserved client");

    /* Discontinuous transitions: skipped epoch, cross scope, unsafe new */
    const struct vos_wv_signature skip_seals[3] = {
        sign_stmt(&old_pol, 0u, VOS_WV_STMT_TERMINAL, &anchor_cp, &skip_tr),
        sign_stmt(&old_pol, 1u, VOS_WV_STMT_TERMINAL, &anchor_cp, &skip_tr),
        sign_stmt(&old_pol, 2u, VOS_WV_STMT_TERMINAL, &anchor_cp, &skip_tr)
    };
    const struct vos_wv_signature skip_new[3] = {
        sign_stmt(&skipped_epoch, 0u, VOS_WV_STMT_PLAIN, &anchor_cp, NULL),
        sign_stmt(&skipped_epoch, 1u, VOS_WV_STMT_PLAIN, &anchor_cp, NULL),
        sign_stmt(&skipped_epoch, 2u, VOS_WV_STMT_PLAIN, &anchor_cp, NULL)
    };
    CHECK(vos_wv_transition(&client, &skip_tr, skip_seals, 3u, skip_new, 3u)
          == VOS_WV_ERR_DISCONTINUOUS, "refuse nonconsecutive epoch transition");
    CHECK(vos_wv_transition(&client, &scope_tr, old_seals, 3u, new_anchor_sigs, 3u)
          == VOS_WV_ERR_DISCONTINUOUS, "refuse cross-scope continuous transition");
    CHECK(vos_wv_transition(&client, &unsafe_tr, old_seals, 3u, new_anchor_sigs, 3u)
          == VOS_WV_ERR_DISCONTINUOUS, "refuse unsafe destination transition");
    CHECK(memcmp(&snap, &client, sizeof(client)) == 0, "discontinuous refusals preserved client");

    /* Transition below pin MUST fail */
    struct vos_wv_client pinned_client;
    CHECK(vos_wv_client_init(&pinned_client, &old_pol, &fork_cp, &gen0, boot_key) == VOS_WV_OK,
          "init pinned client");
    struct vos_wv_client pinned_snap = pinned_client;
    CHECK(vos_wv_transition(&pinned_client, &tr, old_seals, 3u, new_anchor_sigs, 3u)
          == VOS_WV_ERR_CHECKPOINT_STALE, "refuse transition below pin");
    CHECK(memcmp(&pinned_snap, &pinned_client, sizeof(pinned_client)) == 0,
          "below-pin transition preserved client");

    /* Valid continuous transition */
    CHECK(vos_wv_transition(&client, &tr, old_seals, 3u, new_anchor_sigs, 3u) == VOS_WV_OK,
          "accept valid continuous terminal transition");
    CHECK(client.policy.epoch == 1u &&
          client.policy.trust_scope == 7u &&
          client.pinned.entry_count == 1u &&
          client.continuity_preserved == 1u &&
          memcmp(&client.running_generation, &gen0, sizeof(gen0)) == 0,
          "transition updated policy and pin together without installing image");

    /* Rebootstrap tests starting from pinned_client (policy = old_pol, scope = 7, pinned = fork_cp) */
    const struct vos_wv_policy rb_pol = make_policy(9u, 0u, 3u, 3u, 1u, 60u);
    const struct vos_wv_hash right_entries[2] = { h_anchor, make_hash(0x42u) };
    const struct vos_wv_checkpoint right_cp = make_checkpoint(right_entries, 2u);
    const struct vos_wv_signature rb_sigs[3] = {
        sign_stmt(&rb_pol, 0u, VOS_WV_STMT_PLAIN, &right_cp, NULL),
        sign_stmt(&rb_pol, 1u, VOS_WV_STMT_PLAIN, &right_cp, NULL),
        sign_stmt(&rb_pol, 2u, VOS_WV_STMT_PLAIN, &right_cp, NULL)
    };

    const struct vos_wv_rebootstrap rb_good = make_signed_rebootstrap(
        &old_pol, &rb_pol, &right_cp, "new witness operators and fresh anchors", boot_key);
    pinned_snap = pinned_client;

    struct vos_wv_rebootstrap rb_bad_mac = rb_good;
    rb_bad_mac.auth_mac[0] ^= 0x01u;
    CHECK(vos_wv_rebootstrap(&pinned_client, &rb_bad_mac, rb_sigs, 3u)
          == VOS_WV_ERR_UNAUTHENTICATED, "refuse unauthenticated rebootstrap");
    CHECK(memcmp(&pinned_snap, &pinned_client, sizeof(pinned_client)) == 0,
          "unauthenticated rebootstrap preserved client");

    const struct vos_wv_rebootstrap rb_blank = make_signed_rebootstrap(
        &old_pol, &rb_pol, &right_cp, "   \t\n ", boot_key);
    CHECK(vos_wv_rebootstrap(&pinned_client, &rb_blank, rb_sigs, 3u)
          == VOS_WV_ERR_EMPTY_ASSUMPTIONS, "refuse whitespace-only assumptions");
    CHECK(memcmp(&pinned_snap, &pinned_client, sizeof(pinned_client)) == 0,
          "blank-assumptions rebootstrap preserved client");

    const struct vos_wv_policy reused_scope_pol = make_policy(7u, 0u, 3u, 3u, 1u, 60u);
    const struct vos_wv_rebootstrap rb_same_scope = make_signed_rebootstrap(
        &old_pol, &reused_scope_pol, &right_cp, "attempt reuse", boot_key);
    const struct vos_wv_signature reused_sigs[3] = {
        sign_stmt(&reused_scope_pol, 0u, VOS_WV_STMT_PLAIN, &right_cp, NULL),
        sign_stmt(&reused_scope_pol, 1u, VOS_WV_STMT_PLAIN, &right_cp, NULL),
        sign_stmt(&reused_scope_pol, 2u, VOS_WV_STMT_PLAIN, &right_cp, NULL)
    };
    CHECK(vos_wv_rebootstrap(&pinned_client, &rb_same_scope, reused_sigs, 3u)
          == VOS_WV_ERR_SCOPE_REUSED, "refuse reusing initial scope");
    CHECK(memcmp(&pinned_snap, &pinned_client, sizeof(pinned_client)) == 0,
          "reused-scope rebootstrap preserved client");

    /* Valid rebootstrap with fresh scope 9 surrenders continuity even on conflicting anchor */
    CHECK(vos_wv_rebootstrap(&pinned_client, &rb_good, rb_sigs, 3u) == VOS_WV_OK,
          "accept explicit authenticated rebootstrap");
    CHECK(pinned_client.policy.trust_scope == 9u &&
          pinned_client.continuity_preserved == 0u &&
          pinned_client.seen_scope_count == 2u &&
          pinned_client.pinned.entry_count == 2u &&
          memcmp(&pinned_client.pinned.entries[1], &right_entries[1], VOS_WV_DIGEST_BYTES) == 0 &&
          memcmp(&pinned_client.running_generation, &gen0, sizeof(gen0)) == 0,
          "rebootstrap updated scope/pin and surrendered continuity");

    /* A -> B -> A laundered rebootstrap MUST fail */
    pinned_snap = pinned_client;
    const struct vos_wv_rebootstrap rb_back_to_7 = make_signed_rebootstrap(
        &rb_pol, &old_pol, &fork_cp, "launder scope 7 back", boot_key);
    const struct vos_wv_signature back_sigs[3] = {
        sign_stmt(&old_pol, 0u, VOS_WV_STMT_PLAIN, &fork_cp, NULL),
        sign_stmt(&old_pol, 1u, VOS_WV_STMT_PLAIN, &fork_cp, NULL),
        sign_stmt(&old_pol, 2u, VOS_WV_STMT_PLAIN, &fork_cp, NULL)
    };
    CHECK(vos_wv_rebootstrap(&pinned_client, &rb_back_to_7, back_sigs, 3u)
          == VOS_WV_ERR_SCOPE_REUSED, "refuse A-to-B-to-A reused trust scope");
    CHECK(memcmp(&pinned_snap, &pinned_client, sizeof(pinned_client)) == 0,
          "A-to-B-to-A refusal preserved client");

    return 0;
}

int main(void)
{
    if (test_pinned_python_vectors_and_wire_parsers() != 0) {
        return 1;
    }
    if (test_policy_safety_and_one_of_two_refusal() != 0) {
        return 1;
    }
    if (test_certificate_binding_and_admission_pin_immutability() != 0) {
        return 1;
    }
    if (test_transitions_and_rebootstraps() != 0) {
        return 1;
    }
    printf("witness_validator_test: ok\n");
    return 0;
}
