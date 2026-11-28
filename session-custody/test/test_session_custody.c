// SPDX-License-Identifier: Apache-2.0
#include "vos_session_custody.h"

#include <stdio.h>
#include <string.h>

#define CHECK(cond, msg)                                                      \
    do {                                                                      \
        if (!(cond)) {                                                        \
            fprintf(stderr, "FAIL (%s:%d): %s\n", __FILE__, __LINE__, (msg)); \
            return 1;                                                         \
        }                                                                     \
    } while (0)

static void fill_bytes(uint8_t *dst, size_t len, uint8_t seed)
{
    for (size_t i = 0u; i < len; ++i) {
        dst[i] = (uint8_t)(seed + (uint8_t)i);
    }
}

static struct vos_sc_tls_registration make_reg(uint64_t unit_id,
                                               const char *principal,
                                               const char *origin,
                                               const uint8_t cfg_digest[VOS_SC_DIGEST_BYTES],
                                               uint8_t traffic_seed)
{
    struct vos_sc_tls_registration reg;
    memset(&reg, 0, sizeof(reg));
    reg.unit_id = unit_id;
    reg.principal_len = (uint32_t)strlen(principal);
    memcpy(reg.principal, principal, reg.principal_len);
    reg.origin_len = (uint32_t)strlen(origin);
    memcpy(reg.origin, origin, reg.origin_len);
    memcpy(reg.config_digest, cfg_digest, VOS_SC_DIGEST_BYTES);
    fill_bytes(reg.traffic_key, VOS_SC_KEY_BYTES, traffic_seed);
    reg.handshake_complete = 1u;
    reg.server_authenticated = 1u;
    reg.early_data = 0u;
    reg.resumed = 0u;
    return reg;
}

static struct vos_atls_credential make_cred(uint64_t unit_id,
                                            const char *principal,
                                            const char *origin,
                                            uint32_t scope_mask,
                                            uint32_t use_ceiling,
                                            uint64_t expiry,
                                            uint32_t account_id)
{
    struct vos_atls_credential cred;
    memset(&cred, 0, sizeof(cred));
    cred.sealed = 1u;
    cred.unit_id = unit_id;
    cred.role_len = VOS_ATLS_ROLE_BYTES;
    memcpy(cred.role, VOS_ATLS_ROLE_STR, cred.role_len);
    cred.principal_len = (uint32_t)strlen(principal);
    memcpy(cred.principal, principal, cred.principal_len);
    cred.origin_len = (uint32_t)strlen(origin);
    memcpy(cred.origin, origin, cred.origin_len);
    cred.scope_mask = scope_mask;
    cred.operation_mask = (1u << VOS_ATLS_OP_ATTEST_LOCAL_SESSION);
    cred.domain_len = VOS_ATLS_DOMAIN_BYTES;
    memcpy(cred.domain, VOS_ATLS_DOMAIN_STR, cred.domain_len);
    cred.use_ceiling = use_ceiling;
    cred.expiry = expiry;
    cred.account_id = account_id;
    return cred;
}

static struct vos_atls_client_request make_req(const char *principal,
                                               uint8_t scope,
                                               const uint8_t *payload,
                                               uint32_t payload_len)
{
    struct vos_atls_client_request req;
    memset(&req, 0, sizeof(req));
    req.role_len = VOS_ATLS_ROLE_BYTES;
    memcpy(req.role, VOS_ATLS_ROLE_STR, req.role_len);
    req.principal_len = (uint32_t)strlen(principal);
    memcpy(req.principal, principal, req.principal_len);
    req.scope = scope;
    req.operation = VOS_ATLS_OP_ATTEST_LOCAL_SESSION;
    req.domain_len = VOS_ATLS_DOMAIN_BYTES;
    memcpy(req.domain, VOS_ATLS_DOMAIN_STR, req.domain_len);
    req.request_len = payload_len;
    if (payload_len > 0u && payload != NULL) {
        memcpy(req.request_bytes, payload, payload_len);
    }
    return req;
}

static struct vos_atls_cred_policy make_cred_policy(void)
{
    struct vos_atls_cred_policy cp;
    memset(&cp, 0, sizeof(cp));
    cp.request_limit = 64u;
    cp.allowed_operation_mask = (1u << VOS_ATLS_OP_ATTEST_LOCAL_SESSION);
    cp.needs_approval = 0u;
    return cp;
}

static struct vos_atls_appraisal_policy make_policy(const char *principal,
                                                    uint64_t approved_gen,
                                                    uint8_t unit_policy,
                                                    const char *expected_alias)
{
    struct vos_atls_appraisal_policy pol;
    memset(&pol, 0, sizeof(pol));
    pol.approved_gen_count = 1u;
    pol.approved_generations[0] = approved_gen;
    pol.required_principal_len = (uint32_t)strlen(principal);
    memcpy(pol.required_principal, principal, pol.required_principal_len);
    pol.unit_policy = unit_policy;
    if (unit_policy != 0u && expected_alias != NULL) {
        pol.expected_alias_len = (uint32_t)strlen(expected_alias);
        memcpy(pol.expected_alias, expected_alias, pol.expected_alias_len);
    }
    return pol;
}

static int test_end_to_end_software_and_unit_flows(void)
{
    uint8_t hmac_key[VOS_SC_KEY_BYTES];
    uint8_t custody_key[VOS_SC_KEY_BYTES];
    uint8_t cfg_digest[VOS_SC_DIGEST_BYTES];
    fill_bytes(hmac_key, sizeof(hmac_key), 0x10u);
    fill_bytes(custody_key, sizeof(custody_key), 0x40u);
    fill_bytes(cfg_digest, sizeof(cfg_digest), 0x80u);

    struct vos_sc_vault vault;
    CHECK(vos_sc_vault_init(&vault, hmac_key, custody_key, cfg_digest, 1u) == VOS_SC_OK,
          "vault init");
    CHECK(vos_sc_set_measurement(&vault, 1u, 7u) == VOS_SC_OK, "meas unit 1");
    CHECK(vos_sc_set_measurement(&vault, 2u, 7u) == VOS_SC_OK, "meas unit 2");
    CHECK(vos_sc_set_alias(&vault, (const uint8_t *)"service.example", 15u,
                           1u, (const uint8_t *)"enroll-A", 8u) == VOS_SC_OK,
          "alias A");
    CHECK(vos_sc_set_alias(&vault, (const uint8_t *)"service.example", 15u,
                           2u, (const uint8_t *)"enroll-B", 8u) == VOS_SC_OK,
          "alias B");

    /* Cross-unit alias collision on same origin MUST be rejected. */
    CHECK(vos_sc_set_alias(&vault, (const uint8_t *)"service.example", 15u,
                           2u, (const uint8_t *)"enroll-A", 8u) == VOS_SC_ERR_HANDLE_AUTH,
          "cross-unit alias collision rejected");

    const struct vos_sc_tls_registration reg_a =
        make_reg(1u, "service-client", "service.example", cfg_digest, 0x21u);
    const struct vos_sc_tls_registration reg_b =
        make_reg(2u, "service-client", "service.example", cfg_digest, 0x61u);

    struct vos_sc_context_handle h_a;
    struct vos_sc_context_handle h_b;
    CHECK(vos_sc_register_tls_context(&vault, &reg_a, &h_a) == VOS_SC_OK, "reg ctx A");
    CHECK(vos_sc_register_tls_context(&vault, &reg_b, &h_b) == VOS_SC_OK, "reg ctx B");

    /* Verify internal EXPORTER-Channel-Binding derivation matches RFC/Q22c HMAC-SHA256. */
    uint8_t exp_a[VOS_ATLS_EXPORTER_BYTES];
    uint8_t exp_b[VOS_ATLS_EXPORTER_BYTES];
    CHECK(vos_sc_derive_exporter_for_test(&vault, &h_a, exp_a) == VOS_SC_OK, "exp A");
    CHECK(vos_sc_derive_exporter_for_test(&vault, &h_b, exp_b) == VOS_SC_OK, "exp B");
    CHECK(memcmp(exp_a, exp_b, VOS_ATLS_EXPORTER_BYTES) != 0,
          "distinct traffic keys derive distinct exporters");

    uint8_t expected_input[VOS_SC_EXPORTER_LABEL_BYTES + 2u];
    memcpy(expected_input, VOS_SC_EXPORTER_LABEL, VOS_SC_EXPORTER_LABEL_BYTES);
    expected_input[VOS_SC_EXPORTER_LABEL_BYTES] = 0u;
    expected_input[VOS_SC_EXPORTER_LABEL_BYTES + 1u] = 0u;
    uint8_t direct_hmac[VOS_ATLS_EXPORTER_BYTES];
    CHECK(vos_hmac_sha256(reg_a.traffic_key, VOS_SC_KEY_BYTES,
                          expected_input, sizeof(expected_input), direct_hmac) == 1,
          "direct hmac");
    CHECK(memcmp(exp_a, direct_hmac, VOS_ATLS_EXPORTER_BYTES) == 0,
          "derived exporter matches HMAC-SHA256(traffic_key, EXPORTER-Channel-Binding)");

    const struct vos_atls_credential cred_a_spec =
        make_cred(1u, "service-client", "service.example",
                  VOS_ATLS_SCOPE_MASK_SOFTWARE | VOS_ATLS_SCOPE_MASK_UNIT, 3u, 100u, 0u);
    const struct vos_atls_credential cred_b_spec =
        make_cred(2u, "service-client", "service.example",
                  VOS_ATLS_SCOPE_MASK_SOFTWARE | VOS_ATLS_SCOPE_MASK_UNIT, 3u, 100u, 1u);
    struct vos_sc_cred_handle kh_a;
    struct vos_sc_cred_handle kh_b;
    CHECK(vos_sc_register_credential(&vault, &cred_a_spec, &kh_a) == VOS_SC_OK, "reg cred A");
    CHECK(vos_sc_register_credential(&vault, &cred_b_spec, &kh_b) == VOS_SC_OK, "reg cred B");

    /* Delegated credential shares account 0 and tightens ceiling to 2. */
    const struct vos_atls_credential child_a_spec =
        make_cred(1u, "service-client", "service.example",
                  VOS_ATLS_SCOPE_MASK_SOFTWARE | VOS_ATLS_SCOPE_MASK_UNIT, 2u, 100u, 0u);
    struct vos_sc_cred_handle kh_a_child;
    CHECK(vos_sc_delegate_credential(&vault, &kh_a, &child_a_spec, &kh_a_child) == VOS_SC_OK,
          "delegate cred A");

    struct vos_atls_profile profile;
    vos_atls_profile_default_init(&profile);
    const struct vos_atls_cred_policy cp = make_cred_policy();
    const uint8_t req_tag[4] = { 1u, 2u, 3u, 4u };
    const struct vos_atls_client_request req_sw =
        make_req("service-client", VOS_ATLS_SCOPE_SOFTWARE, req_tag, 4u);
    const struct vos_atls_client_request req_unit =
        make_req("service-client", VOS_ATLS_SCOPE_UNIT, req_tag, 4u);
    const struct vos_atls_appraisal_policy pol_sw =
        make_policy("service-client", 7u, 0u, NULL);
    const struct vos_atls_appraisal_policy pol_unit_a =
        make_policy("service-client", 7u, 1u, "enroll-A");

    /* 1. End-to-end software-policy flow on ctx A. */
    struct vos_sc_session sess_a;
    CHECK(vos_sc_session_open(&sess_a, &vault, &h_a, cfg_digest) == VOS_SC_OK, "open sess A");
    uint8_t chal_wire[VOS_ATLS_MAX_CHALLENGE_WIRE_BYTES];
    size_t chal_len = 0u;
    CHECK(vos_sc_session_begin(&sess_a, &vault, &profile, &pol_sw,
                               (const uint8_t *)"nonce-sw-a", 10u, 1u, 10u,
                               chal_wire, sizeof(chal_wire), &chal_len) == VOS_SC_OK,
          "begin sess A sw");

    /* Unauthenticated fetch fallback before decide MUST fail. */
    const uint8_t obj_bytes[8] = { 'v', 'o', 's', '-', 'd', 'a', 't', 'a' };
    struct vos_atls_fetch_request freq;
    memset(&freq, 0, sizeof(freq));
    freq.object_id_len = 4u;
    memcpy(freq.object_id, "objA", 4u);
    freq.manifest_ref_len = 4u;
    memcpy(freq.manifest_ref, "manA", 4u);
    CHECK(vos_sha256(obj_bytes, sizeof(obj_bytes), freq.expected_digest) == 1, "sha256 obj");
    uint8_t freq_wire[VOS_ATLS_MAX_FETCH_REQ_WIRE_BYTES];
    size_t freq_len = 0u;
    CHECK(vos_atls_encode_fetch_request(&profile, &freq, freq_wire, sizeof(freq_wire), &freq_len) ==
              VOS_ATLS_OK,
          "encode fetch req");
    uint8_t frep_wire[VOS_ATLS_MAX_FETCH_REP_WIRE_BYTES];
    size_t frep_len = 0u;
    CHECK(vos_sc_session_fetch_one(&sess_a, &vault, &profile, 2u, freq_wire, freq_len,
                                   1u, 1u, obj_bytes, (uint32_t)sizeof(obj_bytes),
                                   frep_wire, sizeof(frep_wire), &frep_len) ==
              VOS_SC_ERR_CREDENTIAL_AUTH,
          "unauthenticated fetch before decide refused");
    /* Re-open fresh session on new ctx A2 for clean software flow. */
    const struct vos_sc_tls_registration reg_a2 =
        make_reg(1u, "service-client", "service.example", cfg_digest, 0x22u);
    struct vos_sc_context_handle h_a2;
    CHECK(vos_sc_register_tls_context(&vault, &reg_a2, &h_a2) == VOS_SC_OK, "reg ctx A2");
    CHECK(vos_sc_session_open(&sess_a, &vault, &h_a2, cfg_digest) == VOS_SC_OK, "open A2");
    CHECK(vos_sc_session_begin(&sess_a, &vault, &profile, &pol_sw,
                               (const uint8_t *)"nonce-sw-a2", 11u, 1u, 10u,
                               chal_wire, sizeof(chal_wire), &chal_len) == VOS_SC_OK,
          "begin A2 sw");

    uint8_t ev_wire[VOS_ATLS_MAX_EVIDENCE_WIRE_BYTES];
    size_t ev_len = 0u;
    CHECK(vos_sc_quote_session(&vault, &profile, &cp, &kh_a_child, &h_a2, &req_sw,
                               chal_wire, chal_len,
                               ev_wire, sizeof(ev_wire), &ev_len) == VOS_SC_OK,
          "quote A2 sw");
    CHECK(vault.account_charges[0] == 1u && vault.broker.account_used[0] == 1u,
          "quote charged account 0 once");

    CHECK(vos_sc_session_decide(&sess_a, &vault, &profile, &pol_sw, hmac_key,
                                2u, ev_wire, ev_len) == VOS_SC_OK,
          "decide A2 sw");
    CHECK(sess_a.attested_open == 1u && sess_a.conn.phase == VOS_ATLS_PHASE_OPEN,
          "session A2 open");

    CHECK(vos_sc_session_fetch_one(&sess_a, &vault, &profile, 3u, freq_wire, freq_len,
                                   1u, 1u, obj_bytes, (uint32_t)sizeof(obj_bytes),
                                   frep_wire, sizeof(frep_wire), &frep_len) == VOS_SC_OK,
          "bounded fetch A2 succeeds");
    CHECK(sess_a.conn.phase == VOS_ATLS_PHASE_CLOSED, "fetch closes A2");
    CHECK(vos_sc_session_fetch_one(&sess_a, &vault, &profile, 3u, freq_wire, freq_len,
                                   1u, 1u, obj_bytes, (uint32_t)sizeof(obj_bytes),
                                   frep_wire, sizeof(frep_wire), &frep_len) != VOS_SC_OK,
          "second fetch on A2 refused");

    /* 2. A2 -> B -> A2 cycle refused even with fresh nonce, and fresh open on spent A2 refused. */
    CHECK(vos_sc_session_reconnect(&sess_a, &vault, &h_b, cfg_digest) == VOS_SC_OK,
          "reconnect A2 -> B");
    CHECK(vos_sc_session_reconnect(&sess_a, &vault, &h_a2, cfg_digest) ==
              VOS_SC_ERR_SPENT_CONTEXT,
          "A2 -> B -> A2 cycle refused");
    struct vos_sc_session fresh_spent;
    CHECK(vos_sc_session_open(&fresh_spent, &vault, &h_a2, cfg_digest) ==
              VOS_SC_ERR_SPENT_CONTEXT,
          "fresh session open on spent A2 refused");

    /* 3. End-to-end origin-scoped unit policy flow on A3, while unit B is refused. */
    const struct vos_sc_tls_registration reg_a3 =
        make_reg(1u, "service-client", "service.example", cfg_digest, 0x23u);
    struct vos_sc_context_handle h_a3;
    CHECK(vos_sc_register_tls_context(&vault, &reg_a3, &h_a3) == VOS_SC_OK, "reg ctx A3");
    struct vos_sc_session sess_a_unit;
    CHECK(vos_sc_session_open(&sess_a_unit, &vault, &h_a3, cfg_digest) == VOS_SC_OK,
          "open A3 unit");
    CHECK(vos_sc_session_begin(&sess_a_unit, &vault, &profile, &pol_unit_a,
                               (const uint8_t *)"nonce-u-a3", 10u, 1u, 10u,
                               chal_wire, sizeof(chal_wire), &chal_len) == VOS_SC_OK,
          "begin A3 unit");
    CHECK(vos_sc_quote_session(&vault, &profile, &cp, &kh_a_child, &h_a3, &req_unit,
                               chal_wire, chal_len,
                               ev_wire, sizeof(ev_wire), &ev_len) == VOS_SC_OK,
          "quote A3 unit");
    CHECK(vos_sc_session_decide(&sess_a_unit, &vault, &profile, &pol_unit_a, hmac_key,
                                2u, ev_wire, ev_len) == VOS_SC_OK,
          "decide A3 unit accepts");
    vos_sc_session_close(&sess_a_unit, &vault);

    /* Child ceiling (2) is now exhausted! Third quote with child MUST fail. */
    const struct vos_sc_tls_registration reg_a4 =
        make_reg(1u, "service-client", "service.example", cfg_digest, 0x24u);
    struct vos_sc_context_handle h_a4;
    CHECK(vos_sc_register_tls_context(&vault, &reg_a4, &h_a4) == VOS_SC_OK, "reg ctx A4");
    CHECK(vos_sc_quote_session(&vault, &profile, &cp, &kh_a_child, &h_a4, &req_sw,
                               chal_wire, chal_len,
                               ev_wire, sizeof(ev_wire), &ev_len) == VOS_SC_ERR_CREDENTIAL_AUTH,
          "child credential ceiling enforced");

    /* Unit B on its own session is accepted under software policy, refused under unit_A policy. */
    struct vos_sc_session sess_b_sw;
    CHECK(vos_sc_session_open(&sess_b_sw, &vault, &h_b, cfg_digest) == VOS_SC_OK, "open B sw");
    CHECK(vos_sc_session_begin(&sess_b_sw, &vault, &profile, &pol_sw,
                               (const uint8_t *)"nonce-sw-b", 10u, 1u, 10u,
                               chal_wire, sizeof(chal_wire), &chal_len) == VOS_SC_OK,
          "begin B sw");
    CHECK(vos_sc_quote_session(&vault, &profile, &cp, &kh_b, &h_b, &req_sw,
                               chal_wire, chal_len,
                               ev_wire, sizeof(ev_wire), &ev_len) == VOS_SC_OK,
          "quote B sw");
    CHECK(vos_sc_session_decide(&sess_b_sw, &vault, &profile, &pol_sw, hmac_key,
                                2u, ev_wire, ev_len) == VOS_SC_OK,
          "software policy accepts unit B on B session");

    const struct vos_sc_tls_registration reg_b2 =
        make_reg(2u, "service-client", "service.example", cfg_digest, 0x62u);
    struct vos_sc_context_handle h_b2;
    CHECK(vos_sc_register_tls_context(&vault, &reg_b2, &h_b2) == VOS_SC_OK, "reg ctx B2");
    struct vos_sc_session sess_b_unit;
    CHECK(vos_sc_session_open(&sess_b_unit, &vault, &h_b2, cfg_digest) == VOS_SC_OK, "open B2 unit");
    CHECK(vos_sc_session_begin(&sess_b_unit, &vault, &profile, &pol_unit_a,
                               (const uint8_t *)"nonce-u-b2", 10u, 1u, 10u,
                               chal_wire, sizeof(chal_wire), &chal_len) == VOS_SC_OK,
          "begin B2 unit");
    CHECK(vos_sc_quote_session(&vault, &profile, &cp, &kh_b, &h_b2, &req_unit,
                               chal_wire, chal_len,
                               ev_wire, sizeof(ev_wire), &ev_len) == VOS_SC_OK,
          "quote B2 unit");
    CHECK(vos_sc_session_decide(&sess_b_unit, &vault, &profile, &pol_unit_a, hmac_key,
                                2u, ev_wire, ev_len) != VOS_SC_OK,
          "unit policy for A refuses foreign unit B");

    return 0;
}

static int test_custody_refusals_teardown_and_exposure(void)
{
    uint8_t hmac_key[VOS_SC_KEY_BYTES];
    uint8_t custody_key[VOS_SC_KEY_BYTES];
    uint8_t cfg_digest[VOS_SC_DIGEST_BYTES];
    uint8_t wrong_cfg[VOS_SC_DIGEST_BYTES];
    fill_bytes(hmac_key, sizeof(hmac_key), 0x31u);
    fill_bytes(custody_key, sizeof(custody_key), 0x51u);
    fill_bytes(cfg_digest, sizeof(cfg_digest), 0x91u);
    fill_bytes(wrong_cfg, sizeof(wrong_cfg), 0xA1u);

    struct vos_sc_vault vault;
    CHECK(vos_sc_vault_init(&vault, hmac_key, custody_key, cfg_digest, 1u) == VOS_SC_OK,
          "vault init 2");
    CHECK(vos_sc_set_measurement(&vault, 1u, 7u) == VOS_SC_OK, "meas 1");
    CHECK(vos_sc_set_measurement(&vault, 2u, 7u) == VOS_SC_OK, "meas 2");

    /* Ineligible TLS registrations: resumed, early_data, incomplete, unauthenticated, bad cfg. */
    struct vos_sc_context_handle bad_h;
    struct vos_sc_tls_registration bad_resumed =
        make_reg(1u, "service-client", "service.example", cfg_digest, 0x11u);
    bad_resumed.resumed = 1u;
    CHECK(vos_sc_register_tls_context(&vault, &bad_resumed, &bad_h) == VOS_SC_ERR_INELIGIBLE_TLS,
          "resumed TLS refused");

    struct vos_sc_tls_registration bad_early =
        make_reg(1u, "service-client", "service.example", cfg_digest, 0x12u);
    bad_early.early_data = 1u;
    CHECK(vos_sc_register_tls_context(&vault, &bad_early, &bad_h) == VOS_SC_ERR_INELIGIBLE_TLS,
          "early_data TLS refused");

    struct vos_sc_tls_registration bad_inc =
        make_reg(1u, "service-client", "service.example", cfg_digest, 0x13u);
    bad_inc.handshake_complete = 0u;
    CHECK(vos_sc_register_tls_context(&vault, &bad_inc, &bad_h) == VOS_SC_ERR_INELIGIBLE_TLS,
          "incomplete handshake refused");

    struct vos_sc_tls_registration bad_unauth =
        make_reg(1u, "service-client", "service.example", cfg_digest, 0x14u);
    bad_unauth.server_authenticated = 0u;
    CHECK(vos_sc_register_tls_context(&vault, &bad_unauth, &bad_h) == VOS_SC_ERR_INELIGIBLE_TLS,
          "unauthenticated server refused");

    struct vos_sc_tls_registration bad_cfg_reg =
        make_reg(1u, "service-client", "service.example", wrong_cfg, 0x15u);
    CHECK(vos_sc_register_tls_context(&vault, &bad_cfg_reg, &bad_h) == VOS_SC_ERR_CONFIG_DIGEST,
          "config digest mismatch on registration refused");

    /* Register valid contexts A, A_conc, and B. */
    const struct vos_sc_tls_registration reg_a =
        make_reg(1u, "service-client", "service.example", cfg_digest, 0x71u);
    const struct vos_sc_tls_registration reg_a_conc =
        make_reg(1u, "service-client", "service.example", cfg_digest, 0x72u);
    const struct vos_sc_tls_registration reg_b =
        make_reg(2u, "service-client", "service.example", cfg_digest, 0x73u);
    struct vos_sc_context_handle h_a;
    struct vos_sc_context_handle h_a_conc;
    struct vos_sc_context_handle h_b;
    CHECK(vos_sc_register_tls_context(&vault, &reg_a, &h_a) == VOS_SC_OK, "reg A");
    CHECK(vos_sc_register_tls_context(&vault, &reg_a_conc, &h_a_conc) == VOS_SC_OK, "reg A_conc");
    CHECK(vos_sc_register_tls_context(&vault, &reg_b, &h_b) == VOS_SC_OK, "reg B");

    const struct vos_atls_credential cred_a_spec =
        make_cred(1u, "service-client", "service.example",
                  VOS_ATLS_SCOPE_MASK_SOFTWARE, 10u, 100u, 0u);
    const struct vos_atls_credential cred_b_spec =
        make_cred(2u, "service-client", "service.example",
                  VOS_ATLS_SCOPE_MASK_SOFTWARE, 10u, 100u, 1u);
    struct vos_sc_cred_handle kh_a;
    struct vos_sc_cred_handle kh_b;
    CHECK(vos_sc_register_credential(&vault, &cred_a_spec, &kh_a) == VOS_SC_OK, "reg cred A");
    CHECK(vos_sc_register_credential(&vault, &cred_b_spec, &kh_b) == VOS_SC_OK, "reg cred B");

    struct vos_atls_profile profile;
    vos_atls_profile_default_init(&profile);
    const struct vos_atls_cred_policy cp = make_cred_policy();
    const struct vos_atls_appraisal_policy pol_sw =
        make_policy("service-client", 7u, 0u, NULL);

    /* Config digest mismatch on session open refused. */
    struct vos_sc_session sess_bad_cfg;
    CHECK(vos_sc_session_open(&sess_bad_cfg, &vault, &h_a, wrong_cfg) == VOS_SC_ERR_CONFIG_DIGEST,
          "session open refuses wrong config digest");

    /* Foreign/forged handle lookup refused. */
    struct vos_sc_context_handle forged_h = h_a;
    forged_h.handle_mac[0] ^= 0x55u;
    struct vos_sc_session sess_forged;
    CHECK(vos_sc_session_open(&sess_forged, &vault, &forged_h, cfg_digest) ==
              VOS_SC_ERR_HANDLE_AUTH,
          "forged handle MAC refused");

    /* Foreign unit credential handle refused on ctx A. */
    struct vos_sc_session sess_a;
    CHECK(vos_sc_session_open(&sess_a, &vault, &h_a, cfg_digest) == VOS_SC_OK, "open A");
    uint8_t chal_wire[VOS_ATLS_MAX_CHALLENGE_WIRE_BYTES];
    size_t chal_len = 0u;
    CHECK(vos_sc_session_begin(&sess_a, &vault, &profile, &pol_sw,
                               (const uint8_t *)"nonce-1", 7u, 1u, 10u,
                               chal_wire, sizeof(chal_wire), &chal_len) == VOS_SC_OK,
          "begin A");
    uint8_t ev_wire[VOS_ATLS_MAX_EVIDENCE_WIRE_BYTES];
    size_t ev_len = 0u;
    const uint8_t dummy_req[4] = { 1u, 2u, 3u, 4u };
    const struct vos_atls_client_request req_sw =
        make_req("service-client", VOS_ATLS_SCOPE_SOFTWARE, dummy_req, 4u);
    CHECK(vos_sc_quote_session(&vault, &profile, &cp, &kh_b, &h_a, &req_sw,
                               chal_wire, chal_len,
                               ev_wire, sizeof(ev_wire), &ev_len) == VOS_SC_ERR_CREDENTIAL_AUTH,
          "foreign unit credential handle refused for A");

    /* Caller-supplied exporter attempt via 32-byte request payload MUST NOT override derived exporter. */
    uint8_t exp_a[VOS_ATLS_EXPORTER_BYTES];
    CHECK(vos_sc_derive_exporter_for_test(&vault, &h_a, exp_a) == VOS_SC_OK, "exp A");
    const struct vos_atls_client_request spoof_req =
        make_req("service-client", VOS_ATLS_SCOPE_SOFTWARE, exp_a, VOS_ATLS_EXPORTER_BYTES);
    CHECK(vos_sc_quote_session(&vault, &profile, &cp, &kh_a, &h_a_conc, &spoof_req,
                               chal_wire, chal_len,
                               ev_wire, sizeof(ev_wire), &ev_len) == VOS_SC_OK,
          "quote on concurrent A_conc succeeds with A_conc exporter");
    struct vos_atls_evidence decoded_ev;
    CHECK(vos_atls_decode_evidence(&profile, ev_wire, ev_len, &decoded_ev) == VOS_ATLS_OK,
          "decode conc evidence");
    CHECK(memcmp(decoded_ev.exporter, exp_a, VOS_ATLS_EXPORTER_BYTES) != 0,
          "caller-supplied 32-byte payload never replaces protected exporter");
    CHECK(vos_sc_session_decide(&sess_a, &vault, &profile, &pol_sw, hmac_key,
                                2u, ev_wire, ev_len) != VOS_SC_OK,
          "parallel-session exporter swap refused");

    /* Post-teardown handle use refused (quote, open, decide). */
    CHECK(vos_sc_teardown_context(&vault, &h_a_conc) == VOS_SC_OK, "teardown A_conc");
    CHECK(vos_sc_quote_session(&vault, &profile, &cp, &kh_a, &h_a_conc, &req_sw,
                               chal_wire, chal_len,
                               ev_wire, sizeof(ev_wire), &ev_len) == VOS_SC_ERR_TEARDOWN,
          "post-teardown handle quote refused");
    CHECK(vos_sc_session_open(&sess_forged, &vault, &h_a_conc, cfg_digest) == VOS_SC_ERR_TEARDOWN,
          "post-teardown handle open refused");

    /* Key-exposure flag refuses custody operations. */
    CHECK(vos_sc_mark_key_exposed(&vault, &h_b) == VOS_SC_OK, "mark B key exposed");
    CHECK(vos_sc_quote_session(&vault, &profile, &cp, &kh_b, &h_b, &req_sw,
                               chal_wire, chal_len,
                               ev_wire, sizeof(ev_wire), &ev_len) == VOS_SC_ERR_KEY_CUSTODY,
          "key-exposed context refused for quote");

    /* Lifecycle / generation retirement invalidates remaining live handles. */
    const struct vos_sc_tls_registration reg_a5 =
        make_reg(1u, "service-client", "service.example", cfg_digest, 0x75u);
    struct vos_sc_context_handle h_a5;
    CHECK(vos_sc_register_tls_context(&vault, &reg_a5, &h_a5) == VOS_SC_OK, "reg A5");
    CHECK(vos_sc_retire_unit_generation(&vault, 1u, 8u) == VOS_SC_OK, "retire unit 1 gen 8");
    CHECK(vos_sc_session_open(&sess_forged, &vault, &h_a5, cfg_digest) == VOS_SC_ERR_TEARDOWN,
          "generation change retires active handles for unit");

    /* Global lifecycle advance invalidates all handles from previous epoch. */
    const struct vos_sc_tls_registration reg_a6 =
        make_reg(1u, "service-client", "service.example", cfg_digest, 0x76u);
    struct vos_sc_context_handle h_a6;
    CHECK(vos_sc_register_tls_context(&vault, &reg_a6, &h_a6) == VOS_SC_OK, "reg A6");
    CHECK(vos_sc_advance_lifecycle(&vault) == VOS_SC_OK, "advance lifecycle");
    CHECK(vos_sc_session_open(&sess_forged, &vault, &h_a6, cfg_digest) == VOS_SC_ERR_TEARDOWN,
          "lifecycle advance invalidates old-epoch handles");

    return 0;
}

int main(void)
{
    if (test_end_to_end_software_and_unit_flows() != 0) {
        return 1;
    }
    if (test_custody_refusals_teardown_and_exposure() != 0) {
        return 1;
    }
    printf("session_custody_test: ok\n");
    return 0;
}
