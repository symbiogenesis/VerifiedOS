// SPDX-License-Identifier: Apache-2.0
#include "vos_attested_tls.h"

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

static struct vos_atls_protected_context make_ctx(uint64_t ctx_id,
                                                  uint64_t unit_id,
                                                  const char *principal,
                                                  const char *origin,
                                                  uint8_t exporter_seed)
{
    struct vos_atls_protected_context ctx;
    memset(&ctx, 0, sizeof(ctx));
    ctx.context_id = ctx_id;
    ctx.unit_id = unit_id;
    ctx.principal_len = (uint32_t)strlen(principal);
    memcpy(ctx.principal, principal, ctx.principal_len);
    ctx.origin_len = (uint32_t)strlen(origin);
    memcpy(ctx.origin, origin, ctx.origin_len);
    fill_bytes(ctx.exporter, VOS_ATLS_EXPORTER_BYTES, exporter_seed);
    ctx.handshake_complete = 1u;
    ctx.server_authenticated = 1u;
    ctx.early_data = 0u;
    ctx.resumed = 0u;
    return ctx;
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

static struct vos_atls_client_request make_req(const char *principal, uint8_t scope)
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
    req.request_len = 4u;
    req.request_bytes[0] = 1u;
    req.request_bytes[1] = 2u;
    req.request_bytes[2] = 3u;
    req.request_bytes[3] = 4u;
    return req;
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

static struct vos_atls_cred_policy make_cred_policy(void)
{
    struct vos_atls_cred_policy cp;
    memset(&cp, 0, sizeof(cp));
    cp.request_limit = 16u;
    cp.allowed_operation_mask = (1u << VOS_ATLS_OP_ATTEST_LOCAL_SESSION);
    cp.needs_approval = 0u;
    return cp;
}

static int test_wire_codecs_and_canonical_refusals(void)
{
    struct vos_atls_profile profile;
    vos_atls_profile_default_init(&profile);
    CHECK(vos_atls_profile_bounded(&profile) == 1, "default profile bounded");

    /* Zero composition bounds must refuse before parsing. */
    struct vos_atls_profile zero_chal = profile;
    zero_chal.challenge_bound = 0u;
    CHECK(vos_atls_profile_bounded(&zero_chal) == 0, "zero challenge_bound rejected");

    struct vos_atls_challenge chal;
    memset(&chal, 0, sizeof(chal));
    chal.unit_scope = VOS_ATLS_SCOPE_SOFTWARE;
    chal.nonce_len = 5u;
    memcpy(chal.nonce, "n-001", 5u);
    chal.origin_len = 15u;
    memcpy(chal.origin, "service.example", 15u);
    chal.domain_len = VOS_ATLS_DOMAIN_BYTES;
    memcpy(chal.domain, VOS_ATLS_DOMAIN_STR, VOS_ATLS_DOMAIN_BYTES);

    uint8_t chal_wire[VOS_ATLS_MAX_CHALLENGE_WIRE_BYTES + 8u];
    size_t chal_len = 0u;
    CHECK(vos_atls_encode_challenge(&zero_chal, &chal, chal_wire, sizeof(chal_wire), &chal_len) ==
              VOS_ATLS_ERR_BOUNDS,
          "encode challenge refuses zero bound");
    CHECK(vos_atls_encode_challenge(&profile, &chal, chal_wire, sizeof(chal_wire), &chal_len) ==
              VOS_ATLS_OK,
          "encode challenge ok");

    struct vos_atls_challenge chal_dec;
    CHECK(vos_atls_decode_challenge(&zero_chal, chal_wire, chal_len, &chal_dec) ==
              VOS_ATLS_ERR_BOUNDS,
          "decode challenge refuses zero bound");
    CHECK(vos_atls_decode_challenge(&profile, chal_wire, chal_len, &chal_dec) == VOS_ATLS_OK,
          "decode challenge ok");
    CHECK(chal_dec.nonce_len == 5u && memcmp(chal_dec.nonce, "n-001", 5u) == 0,
          "challenge nonce preserved");

    /* Trailing bytes rejected. */
    chal_wire[chal_len] = 0xAAu;
    CHECK(vos_atls_decode_challenge(&profile, chal_wire, chal_len + 1u, &chal_dec) ==
              VOS_ATLS_ERR_WIRE_FORMAT,
          "challenge trailing byte rejected");
    CHECK(vos_atls_decode_challenge(&profile, chal_wire, chal_len - 1u, &chal_dec) ==
              VOS_ATLS_ERR_WIRE_FORMAT,
          "challenge truncated rejected");

    /* Non-canonical unit_scope > 1 rejected. */
    chal_wire[8] = 2u;
    CHECK(vos_atls_decode_challenge(&profile, chal_wire, chal_len, &chal_dec) ==
              VOS_ATLS_ERR_WIRE_FORMAT,
          "challenge invalid unit_scope rejected");

    /* Evidence trailing bytes & non-canonical alias length rejected. */
    uint8_t key[VOS_CRYPTO_KEY_BYTES_256];
    fill_bytes(key, sizeof(key), 0x20u);
    struct vos_atls_broker broker;
    vos_atls_broker_init(&broker, key, 1u);
    CHECK(vos_atls_broker_set_measurement(&broker, 1u, 7u) == VOS_ATLS_OK, "set meas");
    const struct vos_atls_protected_context ctx_a =
        make_ctx(101u, 1u, "service-client", "service.example", 0x41u);
    const struct vos_atls_credential cred_a =
        make_cred(1u, "service-client", "service.example",
                  VOS_ATLS_SCOPE_MASK_SOFTWARE | VOS_ATLS_SCOPE_MASK_UNIT, 2u, 10u, 0u);
    const struct vos_atls_cred_policy cp = make_cred_policy();
    const struct vos_atls_client_request req_sw = make_req("service-client", VOS_ATLS_SCOPE_SOFTWARE);

    uint8_t ev_wire[VOS_ATLS_MAX_EVIDENCE_WIRE_BYTES + 8u];
    size_t ev_len = 0u;
    struct vos_atls_evidence ev;
    CHECK(vos_atls_issue_local(&profile, &cp, &cred_a, &broker, &req_sw, &ctx_a, &chal,
                               &ev, ev_wire, sizeof(ev_wire), &ev_len) == VOS_ATLS_OK,
          "issue evidence for codec check");
    struct vos_atls_evidence ev_dec;
    CHECK(vos_atls_decode_evidence(&profile, ev_wire, ev_len, &ev_dec) == VOS_ATLS_OK,
          "decode evidence ok");

    struct vos_atls_profile zero_ev = profile;
    zero_ev.evidence_bound = 0u;
    CHECK(vos_atls_decode_evidence(&zero_ev, ev_wire, ev_len, &ev_dec) == VOS_ATLS_ERR_BOUNDS,
          "decode evidence refuses zero bound");

    ev_wire[ev_len] = 0x55u;
    CHECK(vos_atls_decode_evidence(&profile, ev_wire, ev_len + 1u, &ev_dec) ==
              VOS_ATLS_ERR_WIRE_FORMAT,
          "evidence trailing byte rejected");

    /* Non-canonical has_alias=0 with non-zero alias_len=1 */
    struct vos_atls_evidence bad_ev = ev;
    bad_ev.has_alias = 0u;
    bad_ev.alias_len = 1u;
    bad_ev.alias[0] = 'x';
    size_t bad_len = 0u;
    CHECK(vos_atls_encode_evidence(&profile, &bad_ev, ev_wire, sizeof(ev_wire), &bad_len) ==
              VOS_ATLS_ERR_WIRE_FORMAT,
          "non-canonical has_alias=0 alias_len=1 rejected");

    /* ObjectFetchRequest & ObjectFetchReply round-trip and canonical checks */
    const uint8_t obj_payload[11] = {
        'h', 'e', 'l', 'l', 'o', '-', 'w', 'o', 'r', 'l', 'd'
    };
    struct vos_atls_fetch_request freq;
    memset(&freq, 0, sizeof(freq));
    freq.object_id_len = 5u;
    memcpy(freq.object_id, "obj-1", 5u);
    freq.manifest_ref_len = 8u;
    memcpy(freq.manifest_ref, "man-v1.0", 8u);
    CHECK(vos_sha256(obj_payload, sizeof(obj_payload), freq.expected_digest) == 1, "hash obj");

    uint8_t freq_wire[VOS_ATLS_MAX_FETCH_REQ_WIRE_BYTES + 4u];
    size_t freq_len = 0u;
    CHECK(vos_atls_encode_fetch_request(&profile, &freq, freq_wire, sizeof(freq_wire), &freq_len) ==
              VOS_ATLS_OK,
          "encode fetch request ok");
    struct vos_atls_fetch_request freq_dec;
    CHECK(vos_atls_decode_fetch_request(&profile, freq_wire, freq_len, &freq_dec) == VOS_ATLS_OK,
          "decode fetch request ok");
    freq_wire[freq_len] = 1u;
    CHECK(vos_atls_decode_fetch_request(&profile, freq_wire, freq_len + 1u, &freq_dec) ==
              VOS_ATLS_ERR_WIRE_FORMAT,
          "fetch request trailing byte rejected");

    struct vos_atls_fetch_reply frep;
    memset(&frep, 0, sizeof(frep));
    frep.status = VOS_ATLS_REPLY_OK;
    frep.object_id_len = 5u;
    memcpy(frep.object_id, "obj-1", 5u);
    frep.object_len = (uint32_t)sizeof(obj_payload);
    memcpy(frep.object_bytes, obj_payload, sizeof(obj_payload));
    memcpy(frep.object_sha256, freq.expected_digest, VOS_ATLS_DIGEST_BYTES);

    uint8_t frep_wire[VOS_ATLS_MAX_FETCH_REP_WIRE_BYTES + 4u];
    size_t frep_len = 0u;
    CHECK(vos_atls_encode_fetch_reply(&profile, &frep, frep_wire, sizeof(frep_wire), &frep_len) ==
              VOS_ATLS_OK,
          "encode fetch reply ok");
    struct vos_atls_fetch_reply frep_dec;
    CHECK(vos_atls_decode_fetch_reply(&profile, frep_wire, frep_len, &frep_dec) == VOS_ATLS_OK,
          "decode fetch reply ok");
    frep_wire[frep_len] = 9u;
    CHECK(vos_atls_decode_fetch_reply(&profile, frep_wire, frep_len + 1u, &frep_dec) ==
              VOS_ATLS_ERR_WIRE_FORMAT,
          "fetch reply trailing byte rejected");

    /* Tampered reply payload fails SHA-256 verification on decode */
    frep_wire[frep_len - 1u] ^= 0x01u;
    CHECK(vos_atls_decode_fetch_reply(&profile, frep_wire, frep_len, &frep_dec) ==
              VOS_ATLS_ERR_AUTHENTICITY,
          "fetch reply tampered object rejected");

    return 0;
}

static int test_broker_custody_and_delegation(void)
{
    struct vos_atls_profile profile;
    vos_atls_profile_default_init(&profile);
    uint8_t key[VOS_CRYPTO_KEY_BYTES_256];
    fill_bytes(key, sizeof(key), 0x30u);

    struct vos_atls_broker broker;
    vos_atls_broker_init(&broker, key, 1u);
    CHECK(vos_atls_broker_set_measurement(&broker, 1u, 7u) == VOS_ATLS_OK, "meas A");
    CHECK(vos_atls_broker_set_alias(&broker, (const uint8_t *)"service.example", 15u,
                                    1u, (const uint8_t *)"alias-a-01", 10u) == VOS_ATLS_OK,
          "alias A");

    const struct vos_atls_protected_context ctx_a =
        make_ctx(10u, 1u, "service-client", "service.example", 0x51u);
    struct vos_atls_challenge chal;
    memset(&chal, 0, sizeof(chal));
    chal.unit_scope = VOS_ATLS_SCOPE_SOFTWARE;
    chal.nonce_len = 4u;
    memcpy(chal.nonce, "n-10", 4u);
    chal.origin_len = 15u;
    memcpy(chal.origin, "service.example", 15u);
    chal.domain_len = VOS_ATLS_DOMAIN_BYTES;
    memcpy(chal.domain, VOS_ATLS_DOMAIN_STR, VOS_ATLS_DOMAIN_BYTES);

    const struct vos_atls_cred_policy cp = make_cred_policy();
    const struct vos_atls_client_request req_sw = make_req("service-client", VOS_ATLS_SCOPE_SOFTWARE);

    /* Unsealed (raw) credential refused without charging */
    struct vos_atls_credential raw_cred =
        make_cred(1u, "service-client", "service.example",
                  VOS_ATLS_SCOPE_MASK_SOFTWARE | VOS_ATLS_SCOPE_MASK_UNIT, 2u, 10u, 0u);
    raw_cred.sealed = 0u;
    CHECK(vos_atls_issue_local(&profile, &cp, &raw_cred, &broker, &req_sw, &ctx_a, &chal,
                               NULL, NULL, 0u, NULL) == VOS_ATLS_ERR_CREDENTIAL_AUTH,
          "raw credential refused");
    CHECK(broker.account_used[0] == 0u, "refused raw credential charges zero uses");

    /* Wrong unit credential refused (borrow-context) */
    const struct vos_atls_credential cred_b =
        make_cred(2u, "service-client", "service.example",
                  VOS_ATLS_SCOPE_MASK_SOFTWARE, 2u, 10u, 1u);
    CHECK(vos_atls_issue_local(&profile, &cp, &cred_b, &broker, &req_sw, &ctx_a, &chal,
                               NULL, NULL, 0u, NULL) == VOS_ATLS_ERR_CREDENTIAL_AUTH,
          "foreign unit credential refused for local context");

    /* Parent + delegated child share account 0 and ceiling */
    const struct vos_atls_credential parent =
        make_cred(1u, "service-client", "service.example",
                  VOS_ATLS_SCOPE_MASK_SOFTWARE | VOS_ATLS_SCOPE_MASK_UNIT, 2u, 10u, 0u);
    struct vos_atls_credential child =
        make_cred(1u, "service-client", "service.example",
                  VOS_ATLS_SCOPE_MASK_SOFTWARE, 1u, 10u, 0u);
    CHECK(vos_atls_delegate_credential(&parent, &child) == VOS_ATLS_OK, "valid delegation");

    struct vos_atls_evidence ev;
    uint8_t wire[VOS_ATLS_MAX_EVIDENCE_WIRE_BYTES];
    size_t wire_len = 0u;
    CHECK(vos_atls_issue_local(&profile, &cp, &child, &broker, &req_sw, &ctx_a, &chal,
                               &ev, wire, sizeof(wire), &wire_len) == VOS_ATLS_OK,
          "child issues once");
    CHECK(broker.account_used[0] == 1u, "shared account incremented");
    CHECK(memcmp(ev.exporter, ctx_a.exporter, VOS_ATLS_EXPORTER_BYTES) == 0,
          "exporter taken strictly from protected context");

    /* Child ceiling (1) exhausted; parent ceiling (2) still has 1 left */
    CHECK(vos_atls_issue_local(&profile, &cp, &child, &broker, &req_sw, &ctx_a, &chal,
                               &ev, wire, sizeof(wire), &wire_len) == VOS_ATLS_ERR_CREDENTIAL_AUTH,
          "child exhausted at 1");
    CHECK(vos_atls_issue_local(&profile, &cp, &parent, &broker, &req_sw, &ctx_a, &chal,
                               &ev, wire, sizeof(wire), &wire_len) == VOS_ATLS_OK,
          "parent spends second use");
    CHECK(broker.account_used[0] == 2u, "shared account at 2");
    CHECK(vos_atls_issue_local(&profile, &cp, &parent, &broker, &req_sw, &ctx_a, &chal,
                               &ev, wire, sizeof(wire), &wire_len) == VOS_ATLS_ERR_CREDENTIAL_AUTH,
          "parent exhausted at 2");

    /* Expired credential refused */
    broker.server_now = 10u;
    const struct vos_atls_credential cred_exp =
        make_cred(1u, "service-client", "service.example",
                  VOS_ATLS_SCOPE_MASK_SOFTWARE, 5u, 10u, 2u);
    CHECK(vos_atls_issue_local(&profile, &cp, &cred_exp, &broker, &req_sw, &ctx_a, &chal,
                               &ev, wire, sizeof(wire), &wire_len) == VOS_ATLS_ERR_CREDENTIAL_AUTH,
          "expired credential refused");

    return 0;
}

static int test_software_unit_substitution_and_lifecycle(void)
{
    struct vos_atls_profile profile;
    vos_atls_profile_default_init(&profile);
    uint8_t key[VOS_CRYPTO_KEY_BYTES_256];
    fill_bytes(key, sizeof(key), 0x70u);

    struct vos_atls_broker broker;
    vos_atls_broker_init(&broker, key, 1u);
    CHECK(vos_atls_broker_set_measurement(&broker, 1u, 7u) == VOS_ATLS_OK, "meas A");
    CHECK(vos_atls_broker_set_measurement(&broker, 2u, 7u) == VOS_ATLS_OK, "meas B");
    CHECK(vos_atls_broker_set_alias(&broker, (const uint8_t *)"service.example", 15u,
                                    1u, (const uint8_t *)"enroll-A", 8u) == VOS_ATLS_OK,
          "alias A");
    CHECK(vos_atls_broker_set_alias(&broker, (const uint8_t *)"service.example", 15u,
                                    2u, (const uint8_t *)"enroll-B", 8u) == VOS_ATLS_OK,
          "alias B");

    const struct vos_atls_protected_context ctx_a =
        make_ctx(1u, 1u, "service-client", "service.example", 0x11u);
    const struct vos_atls_protected_context ctx_b =
        make_ctx(2u, 2u, "service-client", "service.example", 0x22u);
    const struct vos_atls_protected_context ctx_a2 =
        make_ctx(3u, 1u, "service-client", "service.example", 0x33u);

    const struct vos_atls_credential cred_a =
        make_cred(1u, "service-client", "service.example",
                  VOS_ATLS_SCOPE_MASK_SOFTWARE | VOS_ATLS_SCOPE_MASK_UNIT, 16u, 100u, 0u);
    const struct vos_atls_credential cred_b =
        make_cred(2u, "service-client", "service.example",
                  VOS_ATLS_SCOPE_MASK_SOFTWARE | VOS_ATLS_SCOPE_MASK_UNIT, 16u, 100u, 1u);

    const struct vos_atls_cred_policy cp = make_cred_policy();
    const struct vos_atls_client_request req_sw = make_req("service-client", VOS_ATLS_SCOPE_SOFTWARE);
    const struct vos_atls_client_request req_unit = make_req("service-client", VOS_ATLS_SCOPE_UNIT);
    const struct vos_atls_appraisal_policy pol_sw =
        make_policy("service-client", 7u, 0u, NULL);
    const struct vos_atls_appraisal_policy pol_unit_a =
        make_policy("service-client", 7u, 1u, "enroll-A");

    uint8_t chal_wire[VOS_ATLS_MAX_CHALLENGE_WIRE_BYTES];
    size_t chal_len = 0u;
    uint8_t ev_wire[VOS_ATLS_MAX_EVIDENCE_WIRE_BYTES];
    size_t ev_len = 0u;
    struct vos_atls_challenge chal;

    /* 1. Software policy accepts unit A, then fetches exactly one object and closes. */
    struct vos_atls_connection conn_a;
    vos_atls_connection_init(&conn_a, &ctx_a);
    CHECK(vos_atls_begin_appraisal(&profile, &pol_sw, &conn_a,
                                   (const uint8_t *)"nonce-1", 7u, 1u, 10u,
                                   chal_wire, sizeof(chal_wire), &chal_len) == VOS_ATLS_OK,
          "begin sw A");
    CHECK(conn_a.phase == VOS_ATLS_PHASE_WAITING, "phase waiting");
    CHECK(vos_atls_decode_challenge(&profile, chal_wire, chal_len, &chal) == VOS_ATLS_OK,
          "decode chal A");
    CHECK(vos_atls_issue_local(&profile, &cp, &cred_a, &broker, &req_sw, &ctx_a, &chal,
                               NULL, ev_wire, sizeof(ev_wire), &ev_len) == VOS_ATLS_OK,
          "issue sw A");
    CHECK(vos_atls_decide(&profile, &pol_sw, key, &conn_a, 2u, ev_wire, ev_len) == VOS_ATLS_OK,
          "decide sw A accepts");
    CHECK(conn_a.phase == VOS_ATLS_PHASE_OPEN, "phase open");

    /* One bounded fetch succeeds then closes; second fetch refuses. */
    const uint8_t payload[6] = { 'o', 'b', 'j', 'e', 'c', 't' };
    struct vos_atls_fetch_request freq;
    memset(&freq, 0, sizeof(freq));
    freq.object_id_len = 3u;
    memcpy(freq.object_id, "o-1", 3u);
    freq.manifest_ref_len = 3u;
    memcpy(freq.manifest_ref, "m-1", 3u);
    CHECK(vos_sha256(payload, sizeof(payload), freq.expected_digest) == 1, "sha256 obj");
    uint8_t freq_wire[VOS_ATLS_MAX_FETCH_REQ_WIRE_BYTES];
    size_t freq_len = 0u;
    CHECK(vos_atls_encode_fetch_request(&profile, &freq, freq_wire, sizeof(freq_wire), &freq_len) ==
              VOS_ATLS_OK,
          "encode req");
    uint8_t rep_wire[VOS_ATLS_MAX_FETCH_REP_WIRE_BYTES];
    size_t rep_len = 0u;
    CHECK(vos_atls_fetch_one(&profile, &conn_a, 3u, freq_wire, freq_len, 1u, 1u,
                             payload, (uint32_t)sizeof(payload),
                             rep_wire, sizeof(rep_wire), &rep_len) == VOS_ATLS_OK,
          "first fetch succeeds");
    CHECK(conn_a.phase == VOS_ATLS_PHASE_CLOSED, "fetch closes connection");
    CHECK(vos_atls_fetch_one(&profile, &conn_a, 3u, freq_wire, freq_len, 1u, 1u,
                             payload, (uint32_t)sizeof(payload),
                             rep_wire, sizeof(rep_wire), &rep_len) == VOS_ATLS_ERR_PHASE,
          "second fetch refused");

    /* 2. A -> B -> A context cycle refused even with a fresh nonce! */
    CHECK(vos_atls_reconnect(&conn_a, &ctx_b) == VOS_ATLS_OK, "reconnect A -> B");
    CHECK(conn_a.phase == VOS_ATLS_PHASE_FRESH, "reconnected B is Fresh");
    /* Reusing nonce-1 on B must fail and close */
    struct vos_atls_connection conn_b_replay = conn_a;
    CHECK(vos_atls_begin_appraisal(&profile, &pol_sw, &conn_b_replay,
                                   (const uint8_t *)"nonce-1", 7u, 1u, 10u,
                                   chal_wire, sizeof(chal_wire), &chal_len) ==
              VOS_ATLS_ERR_NONCE_REPLAY,
          "reused nonce refused on reconnected context");
    CHECK(conn_b_replay.phase == VOS_ATLS_PHASE_CLOSED, "nonce replay closes");

    /* Returning to context A from B (A -> B -> A) must be refused as spent context! */
    CHECK(vos_atls_reconnect(&conn_a, &ctx_a) == VOS_ATLS_ERR_SPENT_CONTEXT,
          "A -> B -> A cycle refused");
    CHECK(conn_a.phase == VOS_ATLS_PHASE_CLOSED, "cycle closes connection");
    CHECK(vos_atls_begin_appraisal(&profile, &pol_sw, &conn_a,
                                   (const uint8_t *)"nonce-fresh", 11u, 1u, 10u,
                                   chal_wire, sizeof(chal_wire), &chal_len) ==
              VOS_ATLS_ERR_PHASE,
          "closed cycle cannot begin appraisal");

    /* 3. Software policy accepts foreign unit B on B's own session, while unit policy rejects B. */
    struct vos_atls_connection conn_b;
    vos_atls_connection_init(&conn_b, &ctx_b);
    CHECK(vos_atls_begin_appraisal(&profile, &pol_sw, &conn_b,
                                   (const uint8_t *)"nonce-b-sw", 10u, 1u, 10u,
                                   chal_wire, sizeof(chal_wire), &chal_len) == VOS_ATLS_OK,
          "begin sw B");
    CHECK(vos_atls_decode_challenge(&profile, chal_wire, chal_len, &chal) == VOS_ATLS_OK,
          "decode chal B");
    CHECK(vos_atls_issue_local(&profile, &cp, &cred_b, &broker, &req_sw, &ctx_b, &chal,
                               NULL, ev_wire, sizeof(ev_wire), &ev_len) == VOS_ATLS_OK,
          "issue sw B");
    CHECK(vos_atls_decide(&profile, &pol_sw, key, &conn_b, 2u, ev_wire, ev_len) == VOS_ATLS_OK,
          "sw policy accepts B on B's own session");

    /* Unit policy enrolled for A accepts A, refuses B on B's own session. */
    struct vos_atls_connection conn_a_unit;
    vos_atls_connection_init(&conn_a_unit, &ctx_a);
    CHECK(vos_atls_begin_appraisal(&profile, &pol_unit_a, &conn_a_unit,
                                   (const uint8_t *)"nonce-a-u", 9u, 1u, 10u,
                                   chal_wire, sizeof(chal_wire), &chal_len) == VOS_ATLS_OK,
          "begin unit A");
    CHECK(vos_atls_decode_challenge(&profile, chal_wire, chal_len, &chal) == VOS_ATLS_OK,
          "decode chal unit A");
    CHECK(vos_atls_issue_local(&profile, &cp, &cred_a, &broker, &req_unit, &ctx_a, &chal,
                               NULL, ev_wire, sizeof(ev_wire), &ev_len) == VOS_ATLS_OK,
          "issue unit A");
    CHECK(vos_atls_decide(&profile, &pol_unit_a, key, &conn_a_unit, 2u, ev_wire, ev_len) ==
              VOS_ATLS_OK,
          "unit policy accepts A");

    struct vos_atls_connection conn_b_unit;
    vos_atls_connection_init(&conn_b_unit, &ctx_b);
    CHECK(vos_atls_begin_appraisal(&profile, &pol_unit_a, &conn_b_unit,
                                   (const uint8_t *)"nonce-b-u", 9u, 1u, 10u,
                                   chal_wire, sizeof(chal_wire), &chal_len) == VOS_ATLS_OK,
          "begin unit B");
    CHECK(vos_atls_decode_challenge(&profile, chal_wire, chal_len, &chal) == VOS_ATLS_OK,
          "decode chal unit B");
    CHECK(vos_atls_issue_local(&profile, &cp, &cred_b, &broker, &req_unit, &ctx_b, &chal,
                               NULL, ev_wire, sizeof(ev_wire), &ev_len) == VOS_ATLS_OK,
          "issue unit B");
    CHECK(vos_atls_decide(&profile, &pol_unit_a, key, &conn_b_unit, 2u, ev_wire, ev_len) ==
              VOS_ATLS_ERR_IDENTITY_SCOPE,
          "unit policy refuses B");
    CHECK(conn_b_unit.phase == VOS_ATLS_PHASE_CLOSED, "unit mismatch closes");

    /* 4. Parallel-session substitution: A's concurrent context ctx_a2 cannot satisfy ctx_a. */
    struct vos_atls_connection conn_par;
    vos_atls_connection_init(&conn_par, &ctx_a);
    CHECK(vos_atls_begin_appraisal(&profile, &pol_sw, &conn_par,
                                   (const uint8_t *)"nonce-par", 9u, 1u, 10u,
                                   chal_wire, sizeof(chal_wire), &chal_len) == VOS_ATLS_OK,
          "begin parallel A");
    CHECK(vos_atls_decode_challenge(&profile, chal_wire, chal_len, &chal) == VOS_ATLS_OK,
          "decode chal par");
    CHECK(vos_atls_issue_local(&profile, &cp, &cred_a, &broker, &req_sw, &ctx_a2, &chal,
                               NULL, ev_wire, sizeof(ev_wire), &ev_len) == VOS_ATLS_OK,
          "issue on ctx_a2");
    CHECK(vos_atls_decide(&profile, &pol_sw, key, &conn_par, 2u, ev_wire, ev_len) ==
              VOS_ATLS_ERR_EXPORTER_MISMATCH,
          "parallel exporter substitution refused");
    CHECK(conn_par.phase == VOS_ATLS_PHASE_CLOSED, "exporter mismatch closes");
    /* Retry with genuine ctx_a evidence after failure MUST still fail (single attempt!) */
    CHECK(vos_atls_issue_local(&profile, &cp, &cred_a, &broker, &req_sw, &ctx_a, &chal,
                               NULL, ev_wire, sizeof(ev_wire), &ev_len) == VOS_ATLS_OK,
          "issue genuine A");
    CHECK(vos_atls_decide(&profile, &pol_sw, key, &conn_par, 2u, ev_wire, ev_len) ==
              VOS_ATLS_ERR_PHASE,
          "retry after failure refused");

    /* 5. Forged HMAC tag / wrong key refused. */
    struct vos_atls_connection conn_mac;
    vos_atls_connection_init(&conn_mac, &ctx_a);
    CHECK(vos_atls_begin_appraisal(&profile, &pol_sw, &conn_mac,
                                   (const uint8_t *)"nonce-mac", 9u, 1u, 10u,
                                   chal_wire, sizeof(chal_wire), &chal_len) == VOS_ATLS_OK,
          "begin mac");
    CHECK(vos_atls_decode_challenge(&profile, chal_wire, chal_len, &chal) == VOS_ATLS_OK,
          "decode chal mac");
    CHECK(vos_atls_issue_local(&profile, &cp, &cred_a, &broker, &req_sw, &ctx_a, &chal,
                               NULL, ev_wire, sizeof(ev_wire), &ev_len) == VOS_ATLS_OK,
          "issue mac");
    ev_wire[ev_len - 1u] ^= 0x01u;
    CHECK(vos_atls_decide(&profile, &pol_sw, key, &conn_mac, 2u, ev_wire, ev_len) ==
              VOS_ATLS_ERR_AUTHENTICITY,
          "tampered seal MAC refused");

    /* 6. Deadline equality (now == deadline) refused at begin and decide. */
    struct vos_atls_connection conn_dl;
    vos_atls_connection_init(&conn_dl, &ctx_a);
    CHECK(vos_atls_begin_appraisal(&profile, &pol_sw, &conn_dl,
                                   (const uint8_t *)"nonce-dl0", 9u, 10u, 10u,
                                   chal_wire, sizeof(chal_wire), &chal_len) ==
              VOS_ATLS_ERR_DEADLINE,
          "begin refuses now == deadline");
    vos_atls_connection_init(&conn_dl, &ctx_a);
    CHECK(vos_atls_begin_appraisal(&profile, &pol_sw, &conn_dl,
                                   (const uint8_t *)"nonce-dl1", 9u, 1u, 10u,
                                   chal_wire, sizeof(chal_wire), &chal_len) == VOS_ATLS_OK,
          "begin dl1");
    CHECK(vos_atls_decode_challenge(&profile, chal_wire, chal_len, &chal) == VOS_ATLS_OK,
          "decode chal dl1");
    CHECK(vos_atls_issue_local(&profile, &cp, &cred_a, &broker, &req_sw, &ctx_a, &chal,
                               NULL, ev_wire, sizeof(ev_wire), &ev_len) == VOS_ATLS_OK,
          "issue dl1");
    CHECK(vos_atls_decide(&profile, &pol_sw, key, &conn_dl, 10u, ev_wire, ev_len) ==
              VOS_ATLS_ERR_DEADLINE,
          "decide refuses now == deadline");
    CHECK(conn_dl.phase == VOS_ATLS_PHASE_CLOSED, "deadline closes");

    /* 7. Early data / resumed / incomplete / unauthenticated contexts refused. */
    struct vos_atls_protected_context bad_early = ctx_a;
    bad_early.early_data = 1u;
    struct vos_atls_connection conn_bad;
    vos_atls_connection_init(&conn_bad, &bad_early);
    CHECK(vos_atls_begin_appraisal(&profile, &pol_sw, &conn_bad,
                                   (const uint8_t *)"nonce-e", 7u, 1u, 10u,
                                   chal_wire, sizeof(chal_wire), &chal_len) ==
              VOS_ATLS_ERR_INELIGIBLE_CONTEXT,
          "early_data context refused");

    struct vos_atls_protected_context bad_resumed = ctx_a;
    bad_resumed.resumed = 1u;
    vos_atls_connection_init(&conn_bad, &bad_resumed);
    CHECK(vos_atls_begin_appraisal(&profile, &pol_sw, &conn_bad,
                                   (const uint8_t *)"nonce-r", 7u, 1u, 10u,
                                   chal_wire, sizeof(chal_wire), &chal_len) ==
              VOS_ATLS_ERR_INELIGIBLE_CONTEXT,
          "resumed context refused");

    struct vos_atls_protected_context bad_unauth = ctx_a;
    bad_unauth.server_authenticated = 0u;
    vos_atls_connection_init(&conn_bad, &bad_unauth);
    CHECK(vos_atls_begin_appraisal(&profile, &pol_sw, &conn_bad,
                                   (const uint8_t *)"nonce-u", 7u, 1u, 10u,
                                   chal_wire, sizeof(chal_wire), &chal_len) ==
              VOS_ATLS_ERR_INELIGIBLE_CONTEXT,
          "unauthenticated context refused");

    return 0;
}

int main(void)
{
    if (test_wire_codecs_and_canonical_refusals() != 0) {
        return 1;
    }
    if (test_broker_custody_and_delegation() != 0) {
        return 1;
    }
    if (test_software_unit_substitution_and_lifecycle() != 0) {
        return 1;
    }
    printf("attested_tls_test: ok\n");
    return 0;
}
