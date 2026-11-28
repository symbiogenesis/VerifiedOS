// SPDX-License-Identifier: Apache-2.0
#include "vos_device_gen.h"

#include <stdio.h>
#include <string.h>

#define CHECK(cond, msg)                                                      \
    do {                                                                      \
        if (!(cond)) {                                                        \
            fprintf(stderr, "FAIL (%s:%d): %s\n", __FILE__, __LINE__, (msg)); \
            return 1;                                                         \
        }                                                                     \
    } while (0)

static struct vos_dgen_hash make_digest(uint8_t tag)
{
    struct vos_dgen_hash h;
    for (size_t i = 0u; i < VOS_DGEN_DIGEST_BYTES; ++i) {
        h.bytes[i] = (uint8_t)(tag ^ (uint8_t)(i * 3u + 1u));
    }
    return h;
}

static void fill_key(uint8_t seed, uint8_t out[VOS_DGEN_KEY_BYTES])
{
    for (size_t i = 0u; i < VOS_DGEN_KEY_BYTES; ++i) {
        out[i] = (uint8_t)((seed + i * 11u) | 1u);
    }
}

static struct vos_dgen_context default_ctx(void)
{
    struct vos_dgen_context ctx;
    ctx.spec_version = 1u;
    ctx.model_version = 1u;
    ctx.checker_id = 2u;
    ctx.tier = 2u;
    ctx.policy_epoch = 1u;
    ctx.resource_epoch = 1u;
    return ctx;
}

static struct vos_dgen_package make_pkg(uint64_t pkg_id,
                                        uint32_t is_base,
                                        uint8_t code_tag,
                                        uint32_t steps,
                                        uint32_t workset,
                                        const struct vos_dgen_context *ctx)
{
    struct vos_dgen_package p;
    memset(&p, 0, sizeof(p));
    p.pkg_id = pkg_id;
    p.is_base_image = is_base;
    p.locally_composed = 1u;
    p.has_publisher = 0u;
    p.package_logged = 0u;
    p.source_digest = make_digest((uint8_t)(0x10u + code_tag));
    p.contract_digest = make_digest((uint8_t)(0x20u + code_tag));
    p.init_digest = make_digest((uint8_t)(0x30u + code_tag));
    p.proof_digest = make_digest((uint8_t)(0x40u + code_tag));
    p.code_len = 32u;
    for (uint32_t i = 0u; i < p.code_len; ++i) {
        p.code_bytes[i] = (uint8_t)(code_tag + i);
    }
    (void)vos_sha256(p.code_bytes, p.code_len, p.code_digest.bytes);
    p.expected_base_digest = p.code_digest;
    p.init_len = 16u;
    p.proof_steps = steps;
    p.proof_workset_bytes = workset;
    p.proof_ok = 1u;

    p.closure_count = 1u;
    p.closure[0].member_id = 100u + pkg_id;
    p.closure[0].origin = VOS_DGEN_ORIGIN_LOCAL_AUTHORED;
    p.closure[0].has_publisher = 0u;
    p.closure[0].content_digest = make_digest((uint8_t)(0x50u + code_tag));

    (void)vos_dgen_compute_artifact_digest(&p, ctx, &p.expected_artifact_digest);
    return p;
}

static struct vos_dgen_consent make_consent(const struct vos_dgen_hash *roster_hash,
                                            const struct vos_dgen_hash *gen_root,
                                            uint64_t nonce,
                                            const char *name)
{
    struct vos_dgen_consent c;
    memset(&c, 0, sizeof(c));
    c.credential_present = 1u;
    c.user_consented = 1u;
    c.consumed = 0u;
    c.prompt.roster_hash = *roster_hash;
    c.prompt.gen_root = *gen_root;
    c.prompt.nonce = nonce;
    const size_t nlen = strlen(name);
    c.prompt.roster_name_len = (uint32_t)(nlen > VOS_DGEN_MAX_NAME_BYTES ? VOS_DGEN_MAX_NAME_BYTES : nlen);
    memcpy(c.prompt.roster_name, name, c.prompt.roster_name_len);
    return c;
}

static void prepare_hashes(const struct vos_dgen_request *req,
                           const struct vos_dgen_context *ctx,
                           struct vos_dgen_hash *out_roster,
                           struct vos_dgen_hash *out_root)
{
    (void)vos_dgen_compute_roster_hash(req->packages, req->package_count, ctx, out_roster);
    (void)vos_dgen_compute_gen_root(req->version, req->declared_floor, out_roster, ctx, out_root);
}

int main(void)
{
    const struct vos_dgen_context ctx = default_ctx();
    uint8_t sign_key[VOS_DGEN_KEY_BYTES];
    uint8_t cset_key[VOS_DGEN_KEY_BYTES];
    fill_key(0x21u, sign_key);
    fill_key(0x73u, cset_key);

    const struct vos_dgen_hash init_root = make_digest(0xA1u);
    struct vos_dgen_device dev;
    CHECK(vos_dgen_device_init(&dev, 3u, sign_key, cset_key, &ctx,
                               &init_root, 4u, 4u,
                               VOS_DGEN_DEFAULT_STEP_BUDGET,
                               VOS_DGEN_DEFAULT_WORKSET_BYTES) == VOS_DGEN_OK,
          "device init failed");

    /* Seed initial authenticated checked set with base (id=1) and pkg A (id=2). */
    const struct vos_dgen_package base_pkg = make_pkg(1u, 1u, 1u, 300u, 2048u, &ctx);
    const struct vos_dgen_package pkg_a = make_pkg(2u, 0u, 2u, 250u, 1024u, &ctx);

    dev.checked_set.entry_count = 2u;
    dev.checked_set.entries[0].pkg_id = base_pkg.pkg_id;
    dev.checked_set.entries[0].artifact_digest = base_pkg.expected_artifact_digest;
    dev.checked_set.entries[0].source_digest = base_pkg.source_digest;
    dev.checked_set.entries[0].contract_digest = base_pkg.contract_digest;
    dev.checked_set.entries[0].proof_digest = base_pkg.proof_digest;
    dev.checked_set.entries[0].context = ctx;

    dev.checked_set.entries[1].pkg_id = pkg_a.pkg_id;
    dev.checked_set.entries[1].artifact_digest = pkg_a.expected_artifact_digest;
    dev.checked_set.entries[1].source_digest = pkg_a.source_digest;
    dev.checked_set.entries[1].contract_digest = pkg_a.contract_digest;
    dev.checked_set.entries[1].proof_digest = pkg_a.proof_digest;
    dev.checked_set.entries[1].context = ctx;
    CHECK(vos_dgen_checked_set_seal(&dev.core, &dev.checked_set) == VOS_DGEN_OK,
          "initial checked-set seal failed");

    /* 1. Positive offline package-change generation (network_reachable = 0). */
    struct vos_dgen_package pkg_b = make_pkg(3u, 0u, 3u, 120u, 1024u, &ctx);
    pkg_b.closure_count = 2u;
    pkg_b.closure[1].member_id = 202u;
    pkg_b.closure[1].origin = VOS_DGEN_ORIGIN_FETCHED_LOGGED;
    pkg_b.closure[1].has_publisher = 1u;
    pkg_b.closure[1].logged_in_checkpoint = 1u;
    pkg_b.closure[1].consistent_with_pin = 1u;
    pkg_b.closure[1].inclusion_ok = 1u;
    pkg_b.closure[1].content_digest = make_digest(0x66u);

    struct vos_dgen_request req1;
    memset(&req1, 0, sizeof(req1));
    req1.network_reachable = 0u;
    req1.version = 5u;
    req1.declared_floor = 4u;
    req1.package_count = 3u;
    req1.packages[0] = base_pkg;
    req1.packages[1] = pkg_a;
    req1.packages[2] = pkg_b;
    req1.tal_layout_fresh_ok = 1u;
    req1.wiring_fresh_ok = 1u;
    req1.global_resource_ok = 1u;
    req1.cic_checker_available = 1u;
    req1.mode_cert_valid = 1u;
    req1.mode_guard_ok = 1u;
    req1.mode_dwell_ok = 1u;
    req1.mode_recovery_reserved = 1u;

    struct vos_dgen_hash r1_hash;
    struct vos_dgen_hash g1_root;
    prepare_hashes(&req1, &ctx, &r1_hash, &g1_root);
    struct vos_dgen_consent consent1 = make_consent(&r1_hash, &g1_root, 1u, "offline-pkg-change");

    CHECK(vos_dgen_compose_and_admit(&dev, &req1, &consent1) == VOS_DGEN_OK,
          "offline package-change generation failed");
    CHECK(dev.mode_guard.mode == VOS_DGEN_MODE_NORMAL && dev.mode_guard.priv_active == 0u,
          "composition mode lingered after gen1");
    CHECK(dev.last_occupancy.reused_packages == 2u &&
          dev.last_occupancy.fresh_checked_packages == 1u &&
          dev.last_occupancy.total_proof_steps == 120u &&
          dev.last_occupancy.total_package_bytes == 144u,
          "gen1 reuse/occupancy accounting mismatch");
    CHECK(memcmp(vos_dgen_live_slot(&dev)->root.bytes, g1_root.bytes, VOS_DGEN_DIGEST_BYTES) == 0,
          "gen1 live root mismatch");
    CHECK(vos_dgen_checked_set_verify(&dev.core, &dev.checked_set) == VOS_DGEN_OK,
          "gen1 successor checked set invalid");
    CHECK(vos_dgen_health_check(&dev, 1u) == VOS_DGEN_OK,
          "gen1 healthy settle failed");

    /* 2. Positive offline reproducible base-image rebuild + health-gated rollback check. */
    const struct vos_dgen_package base_rebuilt = make_pkg(1u, 1u, 9u, 300u, 2048u, &ctx);
    struct vos_dgen_request req2 = req1;
    req2.version = 6u;
    req2.packages[0] = base_rebuilt;
    struct vos_dgen_hash r2_hash;
    struct vos_dgen_hash g2_root;
    prepare_hashes(&req2, &ctx, &r2_hash, &g2_root);
    struct vos_dgen_consent consent2 = make_consent(&r2_hash, &g2_root, 2u, "offline-base-rebuild");

    CHECK(vos_dgen_compose_and_admit(&dev, &req2, &consent2) == VOS_DGEN_OK,
          "offline base-image rebuild generation failed");
    CHECK(dev.last_occupancy.reused_packages == 2u &&
          dev.last_occupancy.fresh_checked_packages == 1u &&
          dev.last_occupancy.total_proof_steps == 300u,
          "gen2 reuse/occupancy accounting mismatch");
    CHECK(memcmp(vos_dgen_live_slot(&dev)->root.bytes, g2_root.bytes, VOS_DGEN_DIGEST_BYTES) == 0,
          "gen2 live root mismatch");

    /* Health failure must roll back to gen1 root. */
    CHECK(vos_dgen_health_check(&dev, 0u) == VOS_DGEN_ERR_UNHEALTHY_ROLLBACK,
          "health rollback status missing");
    CHECK(memcmp(vos_dgen_live_slot(&dev)->root.bytes, g1_root.bytes, VOS_DGEN_DIGEST_BYTES) == 0,
          "health rollback did not restore gen1 live root");

    /* 3. Adverse mint controls (R-13-027b). */
    struct vos_dgen_request req_adv = req1;
    req_adv.version = 7u;
    struct vos_dgen_hash ra_hash;
    struct vos_dgen_hash ga_root;
    prepare_hashes(&req_adv, &ctx, &ra_hash, &ga_root);

    /* 3a: mint without consent (NULL consent and user_consented == 0) */
    CHECK(vos_dgen_compose_and_admit(&dev, &req_adv, NULL) == VOS_DGEN_ERR_NO_CONSENT,
          "mint without consent accepted");
    struct vos_dgen_consent c_declined = make_consent(&ra_hash, &ga_root, 20u, "declined");
    c_declined.user_consented = 0u;
    CHECK(vos_dgen_compose_and_admit(&dev, &req_adv, &c_declined) == VOS_DGEN_ERR_NO_CONSENT,
          "mint with user_consented == 0 accepted");
    CHECK(dev.mode_guard.mode == VOS_DGEN_MODE_NORMAL && dev.mode_guard.priv_active == 0u,
          "composition mode leaked after no-consent failure");
    CHECK(memcmp(vos_dgen_live_slot(&dev)->root.bytes, g1_root.bytes, VOS_DGEN_DIGEST_BYTES) == 0,
          "no-consent failure mutated live slot");

    /* 3b: consent over altered root */
    struct vos_dgen_hash wrong_root = make_digest(0xEEu);
    struct vos_dgen_consent c_altered = make_consent(&ra_hash, &wrong_root, 3u, "altered");
    CHECK(vos_dgen_compose_and_admit(&dev, &req_adv, &c_altered) == VOS_DGEN_ERR_CONSENT_MISMATCH,
          "mint with altered root accepted");
    CHECK(dev.mode_guard.mode == VOS_DGEN_MODE_NORMAL && dev.mode_guard.priv_active == 0u,
          "composition mode leaked after altered-root failure");

    /* 3c: credential absent */
    struct vos_dgen_consent c_nocred = make_consent(&ra_hash, &ga_root, 4u, "no-cred");
    c_nocred.credential_present = 0u;
    CHECK(vos_dgen_compose_and_admit(&dev, &req_adv, &c_nocred) == VOS_DGEN_ERR_CREDENTIAL_ABSENT,
          "mint with absent credential accepted");
    CHECK(dev.mode_guard.mode == VOS_DGEN_MODE_NORMAL && dev.mode_guard.priv_active == 0u,
          "composition mode leaked after absent-credential failure");

    /* 3d: nonce replay + key export refusal + privileged composer refusal */
    struct vos_dgen_consent c_replay = make_consent(&ra_hash, &ga_root, 1u, "replay");
    CHECK(vos_dgen_compose_and_admit(&dev, &req_adv, &c_replay) == VOS_DGEN_ERR_NONCE_REPLAY,
          "replayed consent nonce accepted");

    uint8_t exported[VOS_DGEN_KEY_BYTES];
    memset(exported, 0xAAu, sizeof(exported));
    CHECK(vos_dgen_core_export_key(&dev.core, exported) == VOS_DGEN_ERR_EXPORT_FORBIDDEN,
          "key export allowed");
    for (size_t i = 0u; i < VOS_DGEN_KEY_BYTES; ++i) {
        CHECK(exported[i] == 0u, "key export buffer not wiped");
    }

    struct vos_dgen_composer_cap priv_comp = dev.composer;
    priv_comp.holds_mint_cap = 1u;
    struct vos_dgen_mint_signature dummy_sig;
    struct vos_dgen_consent c_priv = make_consent(&ra_hash, &ga_root, 5u, "priv");
    CHECK(vos_dgen_trusted_path_mint(&dev.core, &priv_comp, &ra_hash, &ga_root,
                                     &c_priv, &dummy_sig) == VOS_DGEN_ERR_COMPOSER_PRIVILEGED,
          "privileged composer mint accepted");

    /* 4. Adverse offline unlogged fetched object (R-13-023b). */
    struct vos_dgen_request req_unlog = req_adv;
    req_unlog.packages[2].closure[1].logged_in_checkpoint = 0u;
    struct vos_dgen_hash ru_hash;
    struct vos_dgen_hash gu_root;
    prepare_hashes(&req_unlog, &ctx, &ru_hash, &gu_root);
    struct vos_dgen_consent c_unlog = make_consent(&ru_hash, &gu_root, 6u, "unlogged");
    CHECK(vos_dgen_compose_and_admit(&dev, &req_unlog, &c_unlog) == VOS_DGEN_ERR_UNLOGGED_FETCH,
          "unlogged fetched object accepted offline");
    CHECK(dev.mode_guard.mode == VOS_DGEN_MODE_NORMAL && dev.mode_guard.priv_active == 0u,
          "composition mode leaked after unlogged-fetch failure");

    /* 5. Adverse stale TAL / global checks on all-reused generation (R-13-028). */
    struct vos_dgen_request req_stale_tal = req_adv;
    req_stale_tal.tal_layout_fresh_ok = 0u;
    struct vos_dgen_consent c_tal = make_consent(&ra_hash, &ga_root, 7u, "stale-tal");
    CHECK(vos_dgen_compose_and_admit(&dev, &req_stale_tal, &c_tal) == VOS_DGEN_ERR_TAL_STALE,
          "stale TAL layout accepted");
    CHECK(dev.mode_guard.mode == VOS_DGEN_MODE_NORMAL && dev.mode_guard.priv_active == 0u,
          "composition mode leaked after stale-TAL failure");

    struct vos_dgen_request req_bad_global = req_adv;
    req_bad_global.global_resource_ok = 0u;
    struct vos_dgen_consent c_glob = make_consent(&ra_hash, &ga_root, 8u, "bad-global");
    CHECK(vos_dgen_compose_and_admit(&dev, &req_bad_global, &c_glob) == VOS_DGEN_ERR_GLOBAL_CHECK_FAILED,
          "failed global resource check accepted");

    /* 6. Adverse proof budget exhaustion (R-06-015a). */
    struct vos_dgen_request req_overbudget = req_adv;
    req_overbudget.packages[2] = make_pkg(3u, 0u, 0x77u, VOS_DGEN_DEFAULT_STEP_BUDGET + 1u, 1024u, &ctx);
    struct vos_dgen_hash ro_hash;
    struct vos_dgen_hash go_root;
    prepare_hashes(&req_overbudget, &ctx, &ro_hash, &go_root);
    struct vos_dgen_consent c_over = make_consent(&ro_hash, &go_root, 9u, "over-budget");
    CHECK(vos_dgen_compose_and_admit(&dev, &req_overbudget, &c_over) == VOS_DGEN_ERR_BUDGET_EXCEEDED,
          "proof budget exceeded accepted");
    CHECK(dev.mode_guard.mode == VOS_DGEN_MODE_NORMAL && dev.mode_guard.priv_active == 0u,
          "composition mode leaked after budget failure");

    /* 7. Adverse tampered checked-set root HMAC (R-13-028). */
    dev.checked_set.root_hmac[0] ^= 0xFFu;
    struct vos_dgen_consent c_tamper = make_consent(&ra_hash, &ga_root, 10u, "tamper");
    CHECK(vos_dgen_compose_and_admit(&dev, &req_adv, &c_tamper) == VOS_DGEN_ERR_TAMPERED_CHECKED_SET,
          "tampered checked set accepted");
    dev.checked_set.root_hmac[0] ^= 0xFFu;

    /* 8. Adverse non-reproducible base image (R-13-026) & mode cert refusal (R-11-018). */
    struct vos_dgen_request req_nonrepro = req2;
    req_nonrepro.version = 8u;
    req_nonrepro.packages[0].expected_base_digest.bytes[0] ^= 0x01u;
    struct vos_dgen_hash rn_hash;
    struct vos_dgen_hash gn_root;
    prepare_hashes(&req_nonrepro, &ctx, &rn_hash, &gn_root);
    struct vos_dgen_consent c_nonrepro = make_consent(&rn_hash, &gn_root, 11u, "nonrepro");
    CHECK(vos_dgen_compose_and_admit(&dev, &req_nonrepro, &c_nonrepro) == VOS_DGEN_ERR_BASE_NOT_REPRODUCIBLE,
          "non-reproducible base image accepted");

    struct vos_dgen_request req_badmode = req_adv;
    req_badmode.mode_cert_valid = 0u;
    struct vos_dgen_consent c_badmode = make_consent(&ra_hash, &ga_root, 12u, "badmode");
    CHECK(vos_dgen_compose_and_admit(&dev, &req_badmode, &c_badmode) == VOS_DGEN_ERR_MODE_CERT,
          "invalid mode transition certificate accepted");

    printf("device_gen_test: ok\n");
    return 0;
}
