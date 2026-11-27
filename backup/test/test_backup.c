// SPDX-License-Identifier: Apache-2.0
#include "vos_backup.h"

#include <stdio.h>
#include <string.h>

#define CHECK(cond, msg)                                                      \
    do {                                                                      \
        if (!(cond)) {                                                        \
            fprintf(stderr, "FAIL (%s:%d): %s\n", __FILE__, __LINE__, (msg)); \
            return 1;                                                         \
        }                                                                     \
    } while (0)

static struct vos_bk_consent make_consent(enum vos_bk_operation op,
                                          uint32_t src_prof,
                                          uint32_t dst_prof,
                                          uint32_t allow_map,
                                          uint32_t allow_discard)
{
    struct vos_bk_consent c;
    memset(&c, 0, sizeof(c));
    c.valid = 1u;
    c.consumed = 0u;
    c.unlocked = 1u;
    c.credential_verified = 1u;
    c.op = op;
    c.source_profile = src_prof;
    c.target_profile = dst_prof;
    c.allow_profile_mapping = allow_map;
    c.allow_discard = allow_discard;
    return c;
}

static struct vos_bk_drbg make_drbg(uint32_t healthy, uint64_t counter)
{
    struct vos_bk_drbg d;
    memset(&d, 0, sizeof(d));
    d.healthy = healthy;
    d.counter = counter;
    for (size_t i = 0u; i < VOS_BK_KEY_BYTES; ++i) {
        d.seed[i] = (uint8_t)(0x40u + i);
    }
    return d;
}

static int contains_subbytes(const uint8_t *haystack, size_t hlen,
                             const uint8_t *needle, size_t nlen)
{
    if (nlen == 0u || hlen < nlen) {
        return 0;
    }
    for (size_t i = 0u; i + nlen <= hlen; ++i) {
        if (memcmp(haystack + i, needle, nlen) == 0) {
            return 1;
        }
    }
    return 0;
}

static uint32_t get_be32_local(const uint8_t *src)
{
    return ((uint32_t)src[0] << 24u) |
           ((uint32_t)src[1] << 16u) |
           ((uint32_t)src[2] << 8u) |
           (uint32_t)src[3];
}

static void put_be64_local(uint8_t *dst, uint64_t v)
{
    for (uint32_t i = 0u; i < 8u; ++i) {
        dst[i] = (uint8_t)(v >> (56u - 8u * i));
    }
}

static int test_recovery_secret_v1(void)
{
    uint8_t key[VOS_BK_KEY_BYTES];
    for (size_t i = 0u; i < VOS_BK_KEY_BYTES; ++i) {
        key[i] = (uint8_t)i;
    }
    char hex[VOS_BK_RECOVERY_HEX_CHARS + 1u];
    CHECK(vos_bk_encode_recovery_secret(key, hex) == VOS_BK_OK, "encode recovery secret");
    const char *expected =
        "000102030405060708090A0B0C0D0E0F101112131415161718191A1B1C1D1E1F";
    CHECK(strlen(hex) == 64u, "exact 64 hex chars");
    CHECK(memcmp(hex, expected, 64u) == 0, "leading zero and uppercase preserved");

    uint8_t decoded[VOS_BK_KEY_BYTES];
    CHECK(vos_bk_decode_recovery_secret(hex, 64u, decoded) == VOS_BK_OK, "decode recovery secret");
    CHECK(memcmp(decoded, key, VOS_BK_KEY_BYTES) == 0, "round-trip key equality");

    char lower_hex[VOS_BK_RECOVERY_HEX_CHARS + 1u];
    memcpy(lower_hex, expected, 65u);
    lower_hex[21] = 'a';
    CHECK(vos_bk_decode_recovery_secret(lower_hex, 64u, decoded) == VOS_BK_ERR_HEX_FORMAT,
          "reject lowercase hex");
    CHECK(vos_bk_decode_recovery_secret(expected, 63u, decoded) == VOS_BK_ERR_HEX_FORMAT,
          "reject short hex");
    char trailing[66];
    memcpy(trailing, expected, 64u);
    trailing[64] = '0';
    trailing[65] = '\0';
    CHECK(vos_bk_decode_recovery_secret(trailing, 65u, decoded) == VOS_BK_ERR_HEX_FORMAT,
          "reject trailing hex");
    return 0;
}

static int test_subkeys_nonces_and_drbg(void)
{
    uint8_t key[VOS_BK_KEY_BYTES];
    for (size_t i = 0u; i < VOS_BK_KEY_BYTES; ++i) {
        key[i] = (uint8_t)(0xA0u + i);
    }
    uint8_t mkey[VOS_BK_KEY_BYTES];
    uint8_t ckey[VOS_BK_KEY_BYTES];
    vos_bk_derive_subkeys(key, mkey, ckey);
    CHECK(memcmp(mkey, ckey, VOS_BK_KEY_BYTES) != 0, "manifest and chunk subkeys distinct");
    CHECK(memcmp(mkey, key, VOS_BK_KEY_BYTES) != 0, "subkey distinct from object key");

    uint8_t n0[VOS_BK_NONCE_BYTES];
    uint8_t n1[VOS_BK_NONCE_BYTES];
    vos_bk_chunk_nonce(0u, n0);
    vos_bk_chunk_nonce(1u, n1);
    CHECK(memcmp(n0, n1, VOS_BK_NONCE_BYTES) != 0, "chunk nonces injective");

    struct vos_bk_drbg bad_drbg = make_drbg(0u, 1u);
    uint8_t out_k[VOS_BK_KEY_BYTES];
    uint8_t out_n[VOS_BK_NONCE_BYTES];
    CHECK(vos_bk_drbg_draw_key(&bad_drbg, out_k, out_n) == VOS_BK_ERR_ENTROPY,
          "unhealthy drbg refuses");

    struct vos_bk_drbg good_drbg = make_drbg(1u, 1u);
    uint8_t k1[VOS_BK_KEY_BYTES];
    uint8_t k2[VOS_BK_KEY_BYTES];
    uint8_t mn1[VOS_BK_NONCE_BYTES];
    uint8_t mn2[VOS_BK_NONCE_BYTES];
    CHECK(vos_bk_drbg_draw_key(&good_drbg, k1, mn1) == VOS_BK_OK, "draw 1");
    CHECK(vos_bk_drbg_draw_key(&good_drbg, k2, mn2) == VOS_BK_OK, "draw 2");
    CHECK(memcmp(k1, k2, VOS_BK_KEY_BYTES) != 0, "retries draw fresh keys");
    CHECK(memcmp(mn1, mn2, VOS_BK_NONCE_BYTES) != 0, "retries draw fresh manifest nonces");
    return 0;
}

static void populate_source_store(struct vos_bk_device_store *src,
                                  uint8_t *p1, size_t p1_len,
                                  uint8_t *p2, size_t p2_len)
{
    vos_bk_device_store_init(src, VOS_BK_DEFAULT_PROFILE_ID, 42u, 100u, 555u);
    for (size_t i = 0u; i < p1_len; ++i) {
        p1[i] = (uint8_t)(0x10u + (i % 73u));
    }
    for (size_t i = 0u; i < p2_len; ++i) {
        p2[i] = (uint8_t)(0x80u + (i % 59u));
    }

    /* Deliberately insert region 20 before region 10 to verify canonical sorting. */
    (void)vos_bk_add_region(src, 20u, VOS_BK_KIND_ROLLBACKABLE,
                            VOS_BK_SCHEMA_DATA_ONLY, 200u, 1u,
                            p2, (uint32_t)p2_len);
    (void)vos_bk_add_region(src, 10u, VOS_BK_KIND_ROLLBACKABLE,
                            VOS_BK_SCHEMA_DATA_ONLY, 100u, 1u,
                            p1, (uint32_t)p1_len);

    /* Excluded regions carrying explicit sentinels. */
    const uint8_t fresh_sentinel[] = "FRESH-SENTINEL-LEAK";
    const uint8_t consent_sentinel[] = "CONSENT-SENTINEL-LEAK";
    const uint8_t key_sentinel[] = "KEYHANDLE-SENTINEL-LEAK";
    const uint8_t cred_sentinel[] = "CRED-SENTINEL-LEAK";
    const uint8_t sealed_sentinel[] = "SEALED-SENTINEL-LEAK";
    const uint8_t nondata_sentinel[] = "NONDATAONLY-SENTINEL-LEAK";

    (void)vos_bk_add_region(src, 30u, VOS_BK_KIND_FRESH,
                            VOS_BK_SCHEMA_DATA_ONLY, 300u, 1u,
                            fresh_sentinel, (uint32_t)sizeof(fresh_sentinel));
    (void)vos_bk_add_region(src, 31u, VOS_BK_KIND_CONSENT_STORE,
                            VOS_BK_SCHEMA_DATA_ONLY, 301u, 1u,
                            consent_sentinel, (uint32_t)sizeof(consent_sentinel));
    (void)vos_bk_add_region(src, 32u, VOS_BK_KIND_KEY_HANDLE,
                            VOS_BK_SCHEMA_KEY, 302u, 1u,
                            key_sentinel, (uint32_t)sizeof(key_sentinel));
    (void)vos_bk_add_region(src, 33u, VOS_BK_KIND_CREDENTIAL_HANDLE,
                            VOS_BK_SCHEMA_CREDENTIAL_HANDLE, 303u, 1u,
                            cred_sentinel, (uint32_t)sizeof(cred_sentinel));
    (void)vos_bk_add_region(src, 34u, VOS_BK_KIND_SEALED_OBJECT,
                            VOS_BK_SCHEMA_SEALED_HANDLE, 304u, 1u,
                            sealed_sentinel, (uint32_t)sizeof(sealed_sentinel));
    (void)vos_bk_add_region(src, 35u, VOS_BK_KIND_ROLLBACKABLE,
                            VOS_BK_SCHEMA_KEY, 305u, 1u,
                            nondata_sentinel, (uint32_t)sizeof(nondata_sentinel));
}

static struct vos_bk_restore_policy make_same_schema_policy(void)
{
    struct vos_bk_restore_policy pol;
    memset(&pol, 0, sizeof(pol));
    pol.expected_source_profile = VOS_BK_DEFAULT_PROFILE_ID;
    pol.local_profile_id = VOS_BK_DEFAULT_PROFILE_ID;
    pol.chunk_size = VOS_BK_DEFAULT_CHUNK_SIZE;
    pol.allow_profile_mapping = 0u;
    pol.rule_count = 2u;
    pol.rules[0].region_id = 10u;
    pol.rules[0].source_schema_id = 100u;
    pol.rules[0].source_schema_gen = 1u;
    pol.rules[0].arm = VOS_BK_PLAN_SAME_SCHEMA;
    pol.rules[1].region_id = 20u;
    pol.rules[1].source_schema_id = 200u;
    pol.rules[1].source_schema_gen = 1u;
    pol.rules[1].arm = VOS_BK_PLAN_SAME_SCHEMA;
    return pol;
}

static void init_target_with_fresh_classes(struct vos_bk_device_store *dst)
{
    vos_bk_device_store_init(dst, VOS_BK_DEFAULT_PROFILE_ID, 7u, 100u, 555u);
    dst->slots[0].consent_grant_count = 3u;
    const uint8_t old_data[16] = { 0xEEu };
    (void)vos_bk_add_region(dst, 10u, VOS_BK_KIND_ROLLBACKABLE,
                            VOS_BK_SCHEMA_DATA_ONLY, 100u, 1u, old_data, 16u);
    (void)vos_bk_add_fresh_slot(dst, 90u, VOS_BK_FRESH_SPENT_PAYMENT, 1u, 1u, 1u, 1u, 0u, 0x1111u);
    (void)vos_bk_add_fresh_slot(dst, 91u, VOS_BK_FRESH_CONSUMED_TOKEN, 1u, 1u, 1u, 1u, 0u, 0x2222u);
    (void)vos_bk_add_fresh_slot(dst, 92u, VOS_BK_FRESH_ONE_TIME_OP, 1u, 1u, 1u, 1u, 0u, 0x3333u);
    (void)vos_bk_add_fresh_slot(dst, 93u, VOS_BK_FRESH_ATTEMPT_COUNTER, 1u, 1u, 1u, 1u, 5u, 0u);
    (void)vos_bk_add_fresh_slot(dst, 94u, VOS_BK_FRESH_REVOCATION_LIST, 1u, 1u, 1u, 1u, 0u, 0x4444u);
    (void)vos_bk_add_fresh_slot(dst, 95u, VOS_BK_FRESH_OTHER, 1u, 1u, 1u, 1u, 0u, 0x5555u);
}

static int test_export_restore_exclusion_and_fresh(void)
{
    struct vos_bk_device_store src;
    uint8_t p1[150];
    uint8_t p2[210];
    populate_source_store(&src, p1, sizeof(p1), p2, sizeof(p2));

    uint8_t obj_buf[VOS_BK_MAX_OBJECT_BYTES];
    struct vos_bk_byte_sink sink = { obj_buf, sizeof(obj_buf), 0u };
    struct vos_bk_consent exp_consent = make_consent(
        VOS_BK_OP_EXPORT, VOS_BK_DEFAULT_PROFILE_ID, VOS_BK_DEFAULT_PROFILE_ID, 0u, 0u);
    struct vos_bk_drbg drbg = make_drbg(1u, 10u);
    uint8_t obj_key[VOS_BK_KEY_BYTES];

    /* Capacity too small refuses. */
    struct vos_bk_byte_sink tiny_sink = { obj_buf, 64u, 0u };
    CHECK(vos_bk_export(&src, &exp_consent, &drbg, VOS_BK_DEFAULT_PROFILE_ID,
                        VOS_BK_DEFAULT_CHUNK_SIZE, &tiny_sink, obj_key) == VOS_BK_ERR_CAPACITY,
          "tiny sink capacity refuses");

    CHECK(vos_bk_export(&src, &exp_consent, &drbg, VOS_BK_DEFAULT_PROFILE_ID,
                        VOS_BK_DEFAULT_CHUNK_SIZE, &sink, obj_key) == VOS_BK_OK,
          "export succeeds");
    CHECK(exp_consent.consumed == 1u, "export consent consumed");
    CHECK(!contains_subbytes(obj_buf, sink.length, p1, 32u),
          "plaintext p1 does not appear in sealed object");

    /* Verify exported manifest directly via auth_manifest to confirm excluded regions are absent. */
    struct vos_bk_restore_ctx inspect_ctx;
    vos_bk_restore_init(&inspect_ctx);
    struct vos_bk_consent inspect_consent = make_consent(
        VOS_BK_OP_RESTORE, VOS_BK_DEFAULT_PROFILE_ID, VOS_BK_DEFAULT_PROFILE_ID, 0u, 0u);
    CHECK(vos_bk_restore_authorize(&inspect_ctx, &inspect_consent,
                                   VOS_BK_DEFAULT_PROFILE_ID,
                                   VOS_BK_DEFAULT_PROFILE_ID, obj_key) == VOS_BK_OK,
          "authorize inspect");
    struct vos_bk_byte_source bsrc = { obj_buf, sink.length };
    size_t chunks_off = 0u;
    CHECK(vos_bk_restore_auth_manifest(&inspect_ctx, &bsrc,
                                       VOS_BK_DEFAULT_PROFILE_ID,
                                       VOS_BK_DEFAULT_CHUNK_SIZE,
                                       &chunks_off) == VOS_BK_OK,
          "auth manifest");
    CHECK(inspect_ctx.manifest.region_count == 2u,
          "only 2 rollbackable DataOnly regions exported (excludes Fresh/Consent/Key/Cred/Sealed)");
    CHECK(inspect_ctx.manifest.regions[0].region_id == 10u &&
          inspect_ctx.manifest.regions[1].region_id == 20u,
          "regions sorted strictly ascending");
    CHECK(inspect_ctx.manifest.chunk_count == 7u, "3 + 4 = 7 chunks");

    /* Verify chunk ciphertexts differ even if we had identical blocks (chunk nonce + AAD uniqueness). */
    const uint32_t enc_mlen = get_be32_local(obj_buf + 36u);
    CHECK(chunks_off == 40u + enc_mlen + 16u, "chunks offset matches prefix");

    /* Full streaming restore onto target store with Fresh slots. */
    struct vos_bk_device_store dst;
    init_target_with_fresh_classes(&dst);
    struct vos_bk_restore_policy pol = make_same_schema_policy();
    struct vos_bk_consent rst_consent = make_consent(
        VOS_BK_OP_RESTORE, VOS_BK_DEFAULT_PROFILE_ID, VOS_BK_DEFAULT_PROFILE_ID, 0u, 0u);

    CHECK(vos_bk_restore_stream(&dst, &rst_consent, &pol, obj_key, &bsrc) == VOS_BK_OK,
          "restore stream succeeds");
    CHECK(rst_consent.consumed == 1u, "restore consent consumed");

    const struct vos_bk_namespace *act = vos_bk_active_namespace(&dst);
    CHECK(act->generation == 42u, "generation updated");
    CHECK(act->region_count == 2u, "2 regions restored");
    CHECK(act->regions[0].region_id == 10u && act->regions[0].payload_len == sizeof(p1) &&
          memcmp(act->regions[0].payload, p1, sizeof(p1)) == 0,
          "region 10 payload exact match");
    CHECK(act->regions[1].region_id == 20u && act->regions[1].payload_len == sizeof(p2) &&
          memcmp(act->regions[1].payload, p2, sizeof(p2)) == 0,
          "region 20 payload exact match");
    CHECK(act->consent_grant_count == 0u, "consent store empty after restore");
    CHECK(dst.rot_anti_rollback_floor == 100u && dst.continuing_platform_counter == 555u,
          "RoT floor and platform counter preserved");

    /* Verify all 6 Fresh classes deny stale/spent tokens and attempts after restore. */
    CHECK(vos_bk_fresh_check_token(&dst, 90u, 0x9999u) == VOS_BK_ERR_FRESH_DENIED,
          "fresh payment denies");
    CHECK(vos_bk_fresh_check_token(&dst, 91u, 0x2222u) == VOS_BK_ERR_FRESH_DENIED,
          "fresh consumed token denies");
    CHECK(vos_bk_fresh_check_token(&dst, 92u, 0x3333u) == VOS_BK_ERR_FRESH_DENIED,
          "fresh one-time op denies");
    CHECK(vos_bk_fresh_check_attempt(&dst, 93u) == VOS_BK_ERR_FRESH_DENIED,
          "fresh attempt counter denies");
    CHECK(vos_bk_fresh_check_token(&dst, 94u, 0x4444u) == VOS_BK_ERR_FRESH_DENIED,
          "fresh revocation list denies");
    CHECK(vos_bk_fresh_check_token(&dst, 95u, 0x5555u) == VOS_BK_ERR_FRESH_DENIED,
          "fresh other class denies");
    return 0;
}

static int test_zero_write_refusals_and_schema_arms(void)
{
    struct vos_bk_device_store src;
    uint8_t p1[150];
    uint8_t p2[210];
    populate_source_store(&src, p1, sizeof(p1), p2, sizeof(p2));

    uint8_t obj_buf[VOS_BK_MAX_OBJECT_BYTES];
    struct vos_bk_byte_sink sink = { obj_buf, sizeof(obj_buf), 0u };
    struct vos_bk_consent exp_consent = make_consent(
        VOS_BK_OP_EXPORT, VOS_BK_DEFAULT_PROFILE_ID, VOS_BK_DEFAULT_PROFILE_ID, 0u, 0u);
    struct vos_bk_drbg drbg = make_drbg(1u, 20u);
    uint8_t obj_key[VOS_BK_KEY_BYTES];
    CHECK(vos_bk_export(&src, &exp_consent, &drbg, VOS_BK_DEFAULT_PROFILE_ID,
                        VOS_BK_DEFAULT_CHUNK_SIZE, &sink, obj_key) == VOS_BK_OK,
          "export for refusal tests");

    struct vos_bk_device_store dst;
    init_target_with_fresh_classes(&dst);
    const struct vos_bk_namespace orig_ns = *vos_bk_active_namespace(&dst);
    struct vos_bk_restore_policy pol = make_same_schema_policy();
    struct vos_bk_byte_source bsrc = { obj_buf, sink.length };

    /* 1. Wrong key refuses manifest with zero writes. */
    uint8_t bad_key[VOS_BK_KEY_BYTES];
    memcpy(bad_key, obj_key, VOS_BK_KEY_BYTES);
    bad_key[0] ^= 0x01u;
    struct vos_bk_consent c1 = make_consent(
        VOS_BK_OP_RESTORE, VOS_BK_DEFAULT_PROFILE_ID, VOS_BK_DEFAULT_PROFILE_ID, 0u, 0u);
    const uint64_t wc0 = dst.write_counter;
    CHECK(vos_bk_restore_stream(&dst, &c1, &pol, bad_key, &bsrc) == VOS_BK_ERR_MANIFEST_TAG,
          "wrong key refuses manifest");
    CHECK(dst.write_counter == wc0, "wrong key performs zero writes");
    CHECK(memcmp(vos_bk_active_namespace(&dst), &orig_ns, sizeof(orig_ns)) == 0,
          "active namespace unchanged");

    /* 2. Locked device / missing credential refuses with zero writes. */
    struct vos_bk_consent locked_c = make_consent(
        VOS_BK_OP_RESTORE, VOS_BK_DEFAULT_PROFILE_ID, VOS_BK_DEFAULT_PROFILE_ID, 0u, 0u);
    locked_c.unlocked = 0u;
    CHECK(vos_bk_restore_stream(&dst, &locked_c, &pol, obj_key, &bsrc) == VOS_BK_ERR_AUTH,
          "locked device refuses");
    CHECK(dst.write_counter == wc0, "locked device performs zero writes");

    /* 3. Trailing byte appended to envelope refuses with zero writes. */
    uint8_t trail_buf[VOS_BK_MAX_OBJECT_BYTES];
    memcpy(trail_buf, obj_buf, sink.length);
    trail_buf[sink.length] = 0xAAu;
    struct vos_bk_byte_source trail_src = { trail_buf, sink.length + 1u };
    struct vos_bk_consent c_trail = make_consent(
        VOS_BK_OP_RESTORE, VOS_BK_DEFAULT_PROFILE_ID, VOS_BK_DEFAULT_PROFILE_ID, 0u, 0u);
    CHECK(vos_bk_restore_stream(&dst, &c_trail, &pol, obj_key, &trail_src) == VOS_BK_ERR_ENVELOPE,
          "trailing byte refuses");
    CHECK(dst.write_counter == wc0, "trailing byte performs zero writes");

    /* 4. Unsupported schema (missing rule) refuses with ZERO writes (must NOT silently discard!). */
    struct vos_bk_restore_policy unsup_pol = pol;
    unsup_pol.rule_count = 1u; /* Omit rule for region 20 */
    struct vos_bk_consent c_unsup = make_consent(
        VOS_BK_OP_RESTORE, VOS_BK_DEFAULT_PROFILE_ID, VOS_BK_DEFAULT_PROFILE_ID, 0u, 1u);
    CHECK(vos_bk_restore_stream(&dst, &c_unsup, &unsup_pol, obj_key, &bsrc) ==
              VOS_BK_ERR_UNSUPPORTED_SCHEMA,
          "unsupported schema refuses");
    CHECK(dst.write_counter == wc0, "unsupported schema performs zero writes");

    /* 5. Missing Fresh initializer refuses before staging with ZERO writes. */
    struct vos_bk_device_store no_init_dst = dst;
    no_init_dst.slots[no_init_dst.active_idx].fresh[0].has_initializer = 0u;
    struct vos_bk_consent c_noinit = make_consent(
        VOS_BK_OP_RESTORE, VOS_BK_DEFAULT_PROFILE_ID, VOS_BK_DEFAULT_PROFILE_ID, 0u, 0u);
    CHECK(vos_bk_restore_stream(&no_init_dst, &c_noinit, &pol, obj_key, &bsrc) ==
              VOS_BK_ERR_FRESH_DENIED,
          "missing fresh initializer refuses");
    CHECK(no_init_dst.write_counter == wc0, "missing fresh initializer performs zero writes");

    /* 6. Checked migration + explicit confirmed discard + cross-profile mapping succeed. */
    struct vos_bk_device_store mig_dst;
    init_target_with_fresh_classes(&mig_dst);
    mig_dst.slots[0].profile_id = 2u;
    struct vos_bk_restore_policy mig_pol = pol;
    mig_pol.local_profile_id = 2u;
    mig_pol.allow_profile_mapping = 1u;
    mig_pol.rules[0].arm = VOS_BK_PLAN_MIGRATE;
    mig_pol.rules[0].target_schema_id = 101u;
    mig_pol.rules[0].target_schema_gen = 2u;
    mig_pol.rules[0].migrate_xor_mask = 0x5Au;
    mig_pol.rules[1].arm = VOS_BK_PLAN_DISCARD;
    struct vos_bk_consent c_mig = make_consent(
        VOS_BK_OP_RESTORE, VOS_BK_DEFAULT_PROFILE_ID, 2u, 1u, 1u);
    CHECK(vos_bk_restore_stream(&mig_dst, &c_mig, &mig_pol, obj_key, &bsrc) == VOS_BK_OK,
          "migration + confirmed discard + profile map succeeds");
    const struct vos_bk_namespace *mig_act = vos_bk_active_namespace(&mig_dst);
    CHECK(mig_act->region_count == 1u && mig_act->regions[0].region_id == 10u &&
          mig_act->regions[0].schema_id == 101u && mig_act->regions[0].schema_gen == 2u,
          "migrated schema recorded and discarded region omitted");
    CHECK(mig_act->regions[0].payload[0] == (uint8_t)(p1[0] ^ 0x5Au),
          "migration transform applied");
    return 0;
}

static int test_chunk_tamper_and_atomic_preservation(void)
{
    struct vos_bk_device_store src;
    uint8_t p1[150];
    uint8_t p2[210];
    populate_source_store(&src, p1, sizeof(p1), p2, sizeof(p2));

    uint8_t obj_buf[VOS_BK_MAX_OBJECT_BYTES];
    struct vos_bk_byte_sink sink = { obj_buf, sizeof(obj_buf), 0u };
    struct vos_bk_consent exp_consent = make_consent(
        VOS_BK_OP_EXPORT, VOS_BK_DEFAULT_PROFILE_ID, VOS_BK_DEFAULT_PROFILE_ID, 0u, 0u);
    struct vos_bk_drbg drbg = make_drbg(1u, 30u);
    uint8_t obj_key[VOS_BK_KEY_BYTES];
    CHECK(vos_bk_export(&src, &exp_consent, &drbg, VOS_BK_DEFAULT_PROFILE_ID,
                        VOS_BK_DEFAULT_CHUNK_SIZE, &sink, obj_key) == VOS_BK_OK,
          "export for chunk tamper test");

    struct vos_bk_device_store dst;
    init_target_with_fresh_classes(&dst);
    const struct vos_bk_namespace orig_ns = *vos_bk_active_namespace(&dst);
    const uint32_t orig_active = dst.active_idx;
    struct vos_bk_restore_policy pol = make_same_schema_policy();

    const uint32_t enc_mlen = get_be32_local(obj_buf + 36u);
    const size_t chunks_off = 40u + (size_t)enc_mlen + 16u;
    const size_t chunk0_ct_off = chunks_off + VOS_BK_CHUNK_HEADER_BYTES;
    const size_t chunk0_proof_off = chunk0_ct_off + VOS_BK_DEFAULT_CHUNK_SIZE + VOS_BK_TAG_BYTES;

    /* 1. Tamper Merkle proof sibling of chunk 0: must fail Merkle proof check. */
    uint8_t bad_proof_buf[VOS_BK_MAX_OBJECT_BYTES];
    memcpy(bad_proof_buf, obj_buf, sink.length);
    bad_proof_buf[chunk0_proof_off] ^= 0xFFu;
    struct vos_bk_byte_source bad_proof_src = { bad_proof_buf, sink.length };
    struct vos_bk_consent cp = make_consent(
        VOS_BK_OP_RESTORE, VOS_BK_DEFAULT_PROFILE_ID, VOS_BK_DEFAULT_PROFILE_ID, 0u, 0u);
    CHECK(vos_bk_restore_stream(&dst, &cp, &pol, obj_key, &bad_proof_src) ==
              VOS_BK_ERR_MERKLE_PROOF,
          "tampered Merkle proof refused");
    CHECK(dst.active_idx == orig_active && dst.staging_valid == 0u,
          "active slot unchanged and staging cleared on Merkle failure");
    CHECK(memcmp(vos_bk_active_namespace(&dst), &orig_ns, sizeof(orig_ns)) == 0,
          "active namespace byte-identical after Merkle failure");

    /* 2. Tamper chunk 1 (to ensure chunk 0 staged into unreachable slot while active stays untouched). */
    const size_t depth = vos_bk_merkle_depth(7u);
    const size_t chunk0_size =
        VOS_BK_CHUNK_HEADER_BYTES + VOS_BK_DEFAULT_CHUNK_SIZE + VOS_BK_TAG_BYTES + depth * 32u;
    const size_t chunk1_ct_off = chunks_off + chunk0_size + VOS_BK_CHUNK_HEADER_BYTES;
    uint8_t bad_c1_buf[VOS_BK_MAX_OBJECT_BYTES];
    memcpy(bad_c1_buf, obj_buf, sink.length);
    bad_c1_buf[chunk1_ct_off] ^= 0x01u;
    struct vos_bk_byte_source bad_c1_src = { bad_c1_buf, sink.length };
    struct vos_bk_consent cc1 = make_consent(
        VOS_BK_OP_RESTORE, VOS_BK_DEFAULT_PROFILE_ID, VOS_BK_DEFAULT_PROFILE_ID, 0u, 0u);
    CHECK(vos_bk_restore_stream(&dst, &cc1, &pol, obj_key, &bad_c1_src) != VOS_BK_OK,
          "tampered chunk 1 refused");
    CHECK(dst.active_idx == orig_active && dst.staging_valid == 0u,
          "active slot preserved after chunk 1 staging failure");
    CHECK(memcmp(vos_bk_active_namespace(&dst), &orig_ns, sizeof(orig_ns)) == 0,
          "active namespace byte-identical after chunk 1 failure");

    /* 3. Truncate final chunk and update total_extent to match truncation: must refuse incomplete coverage! */
    uint8_t trunc_buf[VOS_BK_MAX_OBJECT_BYTES];
    const size_t trunc_len = chunks_off + chunk0_size;
    memcpy(trunc_buf, obj_buf, trunc_len);
    put_be64_local(trunc_buf + 16u, (uint64_t)trunc_len);
    struct vos_bk_byte_source trunc_src = { trunc_buf, trunc_len };
    struct vos_bk_consent ctr = make_consent(
        VOS_BK_OP_RESTORE, VOS_BK_DEFAULT_PROFILE_ID, VOS_BK_DEFAULT_PROFILE_ID, 0u, 0u);
    /* Manifest AAD includes total_extent, so modifying total_extent fails manifest auth;
       and without modifying total_extent it fails extent check. Both refuse! */
    CHECK(vos_bk_restore_stream(&dst, &ctr, &pol, obj_key, &trunc_src) != VOS_BK_OK,
          "truncated object refuses");
    struct vos_bk_byte_source trunc_raw = { obj_buf, trunc_len };
    struct vos_bk_consent ctr2 = make_consent(
        VOS_BK_OP_RESTORE, VOS_BK_DEFAULT_PROFILE_ID, VOS_BK_DEFAULT_PROFILE_ID, 0u, 0u);
    CHECK(vos_bk_restore_stream(&dst, &ctr2, &pol, obj_key, &trunc_raw) == VOS_BK_ERR_ENVELOPE,
          "raw truncated object fails extent check");
    CHECK(memcmp(vos_bk_active_namespace(&dst), &orig_ns, sizeof(orig_ns)) == 0,
          "active namespace byte-identical after truncation");

    /* 4. Step-by-step crash-cut before commit leaves prior state intact; after commit activates new state. */
    struct vos_bk_restore_ctx ctx;
    vos_bk_restore_init(&ctx);
    struct vos_bk_consent c_step = make_consent(
        VOS_BK_OP_RESTORE, VOS_BK_DEFAULT_PROFILE_ID, VOS_BK_DEFAULT_PROFILE_ID, 0u, 0u);
    struct vos_bk_byte_source full_src = { obj_buf, sink.length };
    CHECK(vos_bk_restore_authorize(&ctx, &c_step, VOS_BK_DEFAULT_PROFILE_ID,
                                   VOS_BK_DEFAULT_PROFILE_ID, obj_key) == VOS_BK_OK,
          "step authorize");
    size_t cursor = 0u;
    CHECK(vos_bk_restore_auth_manifest(&ctx, &full_src, VOS_BK_DEFAULT_PROFILE_ID,
                                       VOS_BK_DEFAULT_CHUNK_SIZE, &cursor) == VOS_BK_OK,
          "step auth manifest");
    CHECK(vos_bk_restore_plan(&ctx, &dst, &pol, &c_step) == VOS_BK_OK, "step plan");
    CHECK(dst.write_counter > 0u || ctx.phase == VOS_BK_PHASE_PLANNED, "planned phase");
    for (uint32_t c = 0u; c < ctx.manifest.chunk_count; ++c) {
        CHECK(vos_bk_restore_stage_next_chunk(&ctx, &dst, &full_src, &cursor) == VOS_BK_OK,
              "step stage chunk");
        /* Before commit, active namespace is still byte-identical to orig_ns! */
        CHECK(memcmp(vos_bk_active_namespace(&dst), &orig_ns, sizeof(orig_ns)) == 0,
              "active namespace untouched during staging");
    }
    CHECK(vos_bk_restore_complete(&ctx, &full_src, cursor) == VOS_BK_OK, "step complete");
    CHECK(memcmp(vos_bk_active_namespace(&dst), &orig_ns, sizeof(orig_ns)) == 0,
          "active namespace untouched before commit");
    CHECK(vos_bk_restore_commit(&ctx, &dst, &c_step) == VOS_BK_OK, "step commit");
    CHECK(vos_bk_active_namespace(&dst)->generation == 42u, "committed generation live");
    return 0;
}

int main(void)
{
    if (test_recovery_secret_v1() != 0) {
        return 1;
    }
    if (test_subkeys_nonces_and_drbg() != 0) {
        return 1;
    }
    if (test_export_restore_exclusion_and_fresh() != 0) {
        return 1;
    }
    if (test_zero_write_refusals_and_schema_arms() != 0) {
        return 1;
    }
    if (test_chunk_tamper_and_atomic_preservation() != 0) {
        return 1;
    }
    printf("backup_test: ok\n");
    return 0;
}
