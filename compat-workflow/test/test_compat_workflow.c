// SPDX-License-Identifier: Apache-2.0
#include "vos_compat_workflow.h"

#include <stdio.h>
#include <string.h>

#define CHECK(cond, msg)                                                      \
    do {                                                                      \
        if (!(cond)) {                                                        \
            fprintf(stderr, "FAIL (%s:%d): %s\n", __FILE__, __LINE__, (msg)); \
            return 1;                                                         \
        }                                                                     \
    } while (0)

static struct vos_compat_hash make_hash(uint8_t tag)
{
    struct vos_compat_hash h;
    for (size_t i = 0u; i < VOS_COMPAT_DIGEST_BYTES; ++i) {
        h.bytes[i] = (uint8_t)(tag ^ (uint8_t)(i * 5u + 3u));
    }
    return h;
}

static struct vos_compat_editor_auth default_editor_auth(void)
{
    struct vos_compat_editor_auth ea;
    memset(&ea, 0, sizeof(ea));
    ea.private_source_ep = 1u;
    ea.private_result_ep = 1u;
    return ea;
}

static struct vos_compat_builder_auth default_builder_auth(void)
{
    struct vos_compat_builder_auth ba;
    memset(&ba, 0, sizeof(ba));
    ba.immutable_closure_ok = 1u;
    ba.output_reservation_ok = 1u;
    ba.diagnostics_ep_ok = 1u;
    return ba;
}

static struct vos_compat_pool_decl make_pool_decl(uint32_t kind, uint32_t cap)
{
    struct vos_compat_pool_decl pd;
    memset(&pd, 0, sizeof(pd));
    pd.kind = kind;
    pd.max_capacity = cap;
    pd.low_threshold = cap > 1u ? cap / 2u : 1u;
    pd.exhausted_threshold = cap;
    pd.release_bound_ticks = 100u;
    pd.recovery_reserve = 1u;
    pd.has_owning_compartment = 1u;
    pd.has_derivation_source = 1u;
    pd.has_bind_release_caps = 1u;
    pd.has_thresholds = 1u;
    pd.has_release_bound = 1u;
    pd.has_lifecycle = 1u;
    pd.has_recovery_reserve = 1u;
    pd.has_confidentiality = 1u;
    pd.has_telemetry = 1u;
    pd.has_restart_semantics = 1u;
    return pd;
}

static struct vos_compat_profile default_profile(void)
{
    struct vos_compat_profile p;
    memset(&p, 0, sizeof(p));
    p.profile_id = 1u;
    p.predeclared = 1u;
    p.toolchain_id = 10u;
    p.config_id = 20u;
    p.step_budget = 1000u;
    p.pools[VOS_COMPAT_POOL_SOURCE_INDEX] = make_pool_decl(VOS_COMPAT_POOL_SOURCE_INDEX, 16u);
    p.pools[VOS_COMPAT_POOL_EDITED_STAGING] = make_pool_decl(VOS_COMPAT_POOL_EDITED_STAGING, 1024u);
    p.pools[VOS_COMPAT_POOL_BUILD_JOBS] = make_pool_decl(VOS_COMPAT_POOL_BUILD_JOBS, 4u);
    p.pools[VOS_COMPAT_POOL_PASS_ARENAS] = make_pool_decl(VOS_COMPAT_POOL_PASS_ARENAS, 8192u);
    p.pools[VOS_COMPAT_POOL_DIAGNOSTICS_BUFFER] = make_pool_decl(VOS_COMPAT_POOL_DIAGNOSTICS_BUFFER, 4u);
    p.pools[VOS_COMPAT_POOL_PROOF_CACHE] = make_pool_decl(VOS_COMPAT_POOL_PROOF_CACHE, 8u);
    p.pools[VOS_COMPAT_POOL_CANDIDATE_CLOSURE] = make_pool_decl(VOS_COMPAT_POOL_CANDIDATE_CLOSURE, 16u);
    p.pools[VOS_COMPAT_POOL_CONSENT_TRANSFER] = make_pool_decl(VOS_COMPAT_POOL_CONSENT_TRANSFER, 4u);
    p.max_source_edges = 32u;
    p.max_source_depth = 8u;
    p.max_chunk_bytes = 128u;
    p.max_partial_objects = 2u;
    p.epoch_limit = 5u;
    p.max_diag_record_bytes = 64u;
    p.max_diag_bytes = 128u;
    p.max_checking_steps = 2000u;
    p.max_result_bytes = 256u;
    p.ordinary_borrows_comp = 0u;
    return p;
}

static struct vos_compat_cache_identity default_cache_id(void)
{
    struct vos_compat_cache_identity id;
    id.source_digest = make_hash(0x11u);
    id.dep_closure_digest = make_hash(0x22u);
    id.imported_lemma_digest = make_hash(0x33u);
    id.semantics_digest = make_hash(0x44u);
    id.config_digest = make_hash(0x55u);
    id.assumption_digest = make_hash(0x66u);
    id.profile_id = 1u;
    return id;
}

int main(void)
{
    struct vos_compat_editor_auth ea = default_editor_auth();
    struct vos_compat_builder_auth ba = default_builder_auth();
    struct vos_compat_profile prof = default_profile();
    const struct vos_compat_hash init_root = make_hash(0xA0u);
    const struct vos_compat_hash init_roster = make_hash(0xB0u);

    /* 0. Authority separation & R-08-046 profile completeness controls. */
    struct vos_compat_service bad_svc;
    struct vos_compat_editor_auth bad_ea = ea;
    bad_ea.holds_signing_key = 1u;
    CHECK(vos_compat_service_init(&bad_svc, &bad_ea, &ba, &prof, &init_root, &init_roster) ==
              VOS_COMPAT_ERR_AUTHORITY,
          "editor holding signing key accepted");

    struct vos_compat_builder_auth bad_ba = ba;
    bad_ba.holds_exec_staged = 1u;
    CHECK(vos_compat_service_init(&bad_svc, &ea, &bad_ba, &prof, &init_root, &init_roster) ==
              VOS_COMPAT_ERR_AUTHORITY,
          "builder holding execute authority accepted");

    struct vos_compat_profile bad_prof = prof;
    bad_prof.pools[VOS_COMPAT_POOL_PROOF_CACHE].has_recovery_reserve = 0u;
    CHECK(vos_compat_profile_validate(&bad_prof) == VOS_COMPAT_ERR_INVALID_PROFILE,
          "profile missing R-08-046 recovery reserve accepted");

    bad_prof = prof;
    bad_prof.ordinary_borrows_comp = 1u;
    CHECK(vos_compat_profile_validate(&bad_prof) == VOS_COMPAT_ERR_INVALID_PROFILE,
          "ordinary mode borrowing composition slots accepted");

    struct vos_compat_service svc;
    CHECK(vos_compat_service_init(&svc, &ea, &ba, &prof, &init_root, &init_roster) ==
              VOS_COMPAT_OK,
          "service init failed");

    /* 1. Positive end-to-end flow: Read -> Stage -> Submit -> Advance -> Diags -> Admit -> Consent -> Boot -> TestResult. */
    struct vos_compat_source_obj src;
    memset(&src, 0, sizeof(src));
    src.obj_id = 101u;
    src.version = 3u;
    src.grant_ok = 1u;
    src.total_bytes = 200u;
    for (uint32_t i = 0u; i < src.total_bytes; ++i) {
        src.bytes[i] = (uint8_t)(i + 7u);
    }

    uint8_t slice[64];
    uint32_t slice_len = 0u;
    CHECK(vos_compat_read_source_slice(&svc, &src, 101u, 3u, 10u, 64u, 4u, 6u, 3u,
                                       slice, &slice_len) == VOS_COMPAT_OK &&
              slice_len == 64u && slice[0] == 17u,
          "positive read_source_slice failed");

    uint8_t edited[160];
    for (uint32_t i = 0u; i < 160u; ++i) {
        edited[i] = (uint8_t)(i * 3u + 1u);
    }
    struct vos_compat_hash staged_digest;
    CHECK(vos_sha256(edited, 160u, staged_digest.bytes) == 1, "sha256 failed");

    struct vos_compat_staged_obj staged_out;
    CHECK(vos_compat_stage_edited_source(&svc, 1u, 7u, 0u, 160u, edited, 100u,
                                         &staged_digest, 0u, &staged_out) == VOS_COMPAT_OK,
          "staging chunk 0 failed");
    CHECK(vos_compat_stage_edited_source(&svc, 1u, 7u, 1u, 160u, edited + 100u, 60u,
                                         &staged_digest, 1u, &staged_out) == VOS_COMPAT_OK,
          "staging chunk 1 failed");
    CHECK(staged_out.valid == 1u && staged_out.executable == 0u &&
              staged_out.total_bytes == 160u &&
              memcmp(staged_out.content_digest.bytes, staged_digest.bytes, VOS_COMPAT_DIGEST_BYTES) == 0,
          "staged object executable or digest mismatch");

    uint32_t slot = 0u;
    uint32_t epoch = 0u;
    CHECK(vos_compat_submit_build(&svc, 1u, 1u, &staged_digest, 4u, 6u, 3u,
                                  10u, 20u, &prof, &slot, &epoch) == VOS_COMPAT_OK,
          "submit_build failed");

    const struct vos_compat_hash build_out_dig = make_hash(0xC1u);
    const uint8_t diag1[] = "compile: ok";
    CHECK(vos_compat_advance_build(&svc, slot, epoch, 400u, 4096u, &build_out_dig,
                                   diag1, (uint32_t)(sizeof(diag1) - 1u), 1u) == VOS_COMPAT_OK,
          "advance_build failed");
    CHECK(svc.jobs[slot].output_executable == 0u, "build output marked executable");

    struct vos_compat_diag_view dview;
    CHECK(vos_compat_read_diagnostics(&svc, slot, epoch, 1u, 0u, 4u, 128u, &dview) == VOS_COMPAT_OK &&
              dview.record_count == 1u && dview.truncated == 0u,
          "read_diagnostics failed");

    const struct vos_compat_hash cand_root = make_hash(0xD1u);
    const struct vos_compat_hash cand_roster = make_hash(0xE1u);
    const struct vos_compat_cache_identity cid = default_cache_id();

    struct vos_compat_admission_pkg pkg;
    memset(&pkg, 0, sizeof(pkg));
    pkg.job_slot = slot;
    pkg.job_epoch = epoch;
    pkg.proof_complete = 1u;
    pkg.checking_arena_ok = 1u;
    pkg.checking_steps = 500u;
    pkg.roster_entries = 4u;
    pkg.roster_valid = 1u;
    pkg.tal_ok = 1u;
    pkg.source_corr_ok = 1u;
    pkg.cache_hit_used = 0u;
    pkg.cache_id = cid;
    pkg.candidate_root = cand_root;
    pkg.candidate_roster_hash = cand_roster;

    CHECK(vos_compat_submit_successor_admission(&svc, &pkg) == VOS_COMPAT_OK,
          "submit_successor_admission failed");
    CHECK(memcmp(svc.running_gen_root.bytes, init_root.bytes, VOS_COMPAT_DIGEST_BYTES) == 0,
          "admission mutated running generation before consent/boot");

    struct vos_compat_consent_req creq;
    memset(&creq, 0, sizeof(creq));
    creq.candidate_root = cand_root;
    creq.roster_hash = cand_roster;
    creq.user_consented = 1u;
    creq.on_die_cred_ok = 1u;
    creq.external_roaming_key = 0u;
    CHECK(vos_compat_request_generation_consent(&svc, &creq) == VOS_COMPAT_OK,
          "request_generation_consent failed");
    CHECK(vos_compat_boot_successor(&svc) == VOS_COMPAT_OK,
          "boot_successor failed");
    CHECK(svc.boot_epoch == 2u &&
              memcmp(svc.running_gen_root.bytes, cand_root.bytes, VOS_COMPAT_DIGEST_BYTES) == 0,
          "successor boot did not advance generation");

    struct vos_compat_test_result tres;
    memset(&tres, 0, sizeof(tres));
    tres.grant_ok = 1u;
    tres.candidate_root = cand_root;
    tres.test_id = 42u;
    tres.boot_epoch = 2u;
    tres.result_bytes = 32u;
    tres.passed = 1u;
    struct vos_compat_test_result out_tres;
    CHECK(vos_compat_read_successor_test_result(&svc, &tres, &cand_root, 42u, &out_tres) ==
              VOS_COMPAT_OK && out_tres.passed == 1u,
          "read_successor_test_result failed");

    /* 2. Negative controls: R-02-008 same-gen native execution & forbidden operations. */
    CHECK(vos_compat_attempt_forbidden_op(&svc, VOS_COMPAT_FORBID_EXEC_STAGED_NATIVE) ==
              VOS_COMPAT_ERR_SAME_GEN_NATIVE_EXEC,
          "same-gen native execution allowed");
    CHECK(vos_compat_attempt_forbidden_op(&svc, VOS_COMPAT_FORBID_REWRITE_RUNNING_ROSTER) ==
              VOS_COMPAT_ERR_REWRITE_ROSTER,
          "running roster rewrite allowed");
    CHECK(vos_compat_attempt_forbidden_op(&svc, VOS_COMPAT_FORBID_INSTALL_RUNTIME_PLUGIN) ==
              VOS_COMPAT_ERR_RUNTIME_PLUGIN,
          "runtime native plugin allowed");
    CHECK(vos_compat_attempt_forbidden_op(&svc, VOS_COMPAT_FORBID_LOAD_EXTERNAL_PATH) ==
              VOS_COMPAT_ERR_EXTERNAL_PATH,
          "external path load allowed");
    CHECK(vos_compat_attempt_forbidden_op(&svc, VOS_COMPAT_FORBID_BYPASS_CHECKING) ==
              VOS_COMPAT_ERR_BYPASS_CHECKING,
          "checking bypass allowed");
    CHECK(vos_compat_attempt_forbidden_op(&svc, VOS_COMPAT_FORBID_WASM_NATIVE_ESCAPE) ==
              VOS_COMPAT_ERR_SAME_GEN_NATIVE_EXEC,
          "wasm native escape allowed");

    /* 3. Negative controls: ReadSourceSlice grants, version, bounds, index limits. */
    struct vos_compat_source_obj ungranted = src;
    ungranted.grant_ok = 0u;
    CHECK(vos_compat_read_source_slice(&svc, &ungranted, 101u, 3u, 0u, 16u, 1u, 1u, 1u,
                                       slice, &slice_len) == VOS_COMPAT_ERR_MISSING_GRANT,
          "ungranted source read accepted");
    CHECK(vos_compat_read_source_slice(&svc, &src, 101u, 99u, 0u, 16u, 1u, 1u, 1u,
                                       slice, &slice_len) == VOS_COMPAT_ERR_WRONG_OBJECT_OR_VERSION,
          "wrong source version accepted");
    CHECK(vos_compat_read_source_slice(&svc, &src, 101u, 3u, 180u, 64u, 1u, 1u, 1u,
                                       slice, &slice_len) == VOS_COMPAT_ERR_OUT_OF_RANGE,
          "out-of-range read accepted");
    CHECK(vos_compat_read_source_slice(&svc, &src, 101u, 3u, 0u, 16u, 1u, 99u, 1u,
                                       slice, &slice_len) == VOS_COMPAT_ERR_INDEX_EXHAUSTED,
          "index edge overflow accepted");

    /* 4. Negative controls: Staging incomplete/repeated/over-budget/mismatched digest discards partial. */
    const uint32_t staged_before = svc.staged_count;
    CHECK(vos_compat_stage_edited_source(&svc, 1u, 8u, 0u, 100u, edited, 50u,
                                         &staged_digest, 0u, &staged_out) == VOS_COMPAT_OK,
          "partial chunk 0 failed");
    CHECK(vos_compat_stage_edited_source(&svc, 1u, 8u, 0u, 100u, edited, 50u,
                                         &staged_digest, 0u, &staged_out) == VOS_COMPAT_ERR_STAGING_SEQUENCE,
          "repeated chunk seq accepted");
    CHECK(svc.staged_count == staged_before && svc.partials[0].active == 0u,
          "aborted partial leaked");

    CHECK(vos_compat_stage_edited_source(&svc, 1u, 9u, 0u, 100u, edited, 50u,
                                         &staged_digest, 1u, &staged_out) == VOS_COMPAT_ERR_STAGING_INCOMPLETE,
          "incomplete final staging accepted");
    CHECK(vos_compat_stage_edited_source(&svc, 1u, 10u, 0u, 2000u, edited, 50u,
                                         &staged_digest, 0u, &staged_out) == VOS_COMPAT_ERR_STAGING_OVER_BUDGET,
          "over-budget staging accepted");
    struct vos_compat_hash wrong_dig = staged_digest;
    wrong_dig.bytes[0] ^= 0xFFu;
    CHECK(vos_compat_stage_edited_source(&svc, 1u, 11u, 0u, 100u, edited, 100u,
                                         &wrong_dig, 1u, &staged_out) == VOS_COMPAT_ERR_STAGING_DIGEST,
          "mismatched digest staging accepted");
    CHECK(svc.staged_count == staged_before, "failed staging published object");

    /* 5. Negative controls: ProofCache invalidation & no admission bypass. */
    struct vos_compat_cache_identity cid_bad = cid;
    cid_bad.imported_lemma_digest.bytes[0] ^= 1u;
    CHECK(vos_compat_cache_lookup(&svc, &cid_bad, NULL) == 0,
          "cache hit after lemma change");
    cid_bad = cid;
    cid_bad.semantics_digest.bytes[0] ^= 1u;
    CHECK(vos_compat_cache_lookup(&svc, &cid_bad, NULL) == 0,
          "cache hit after semantics change");
    cid_bad = cid;
    cid_bad.assumption_digest.bytes[0] ^= 1u;
    CHECK(vos_compat_cache_lookup(&svc, &cid_bad, NULL) == 0,
          "cache hit after assumption change");

    struct vos_compat_admission_pkg cache_bypass_pkg = pkg;
    cache_bypass_pkg.cache_hit_used = 1u;
    cache_bypass_pkg.tal_ok = 0u;
    CHECK(vos_compat_submit_successor_admission(&svc, &cache_bypass_pkg) ==
              VOS_COMPAT_ERR_TAL_OR_CORR,
          "cache hit bypassed TAL check");

    /* 6. Negative controls: Diagnostics overflow truncation marker, cancel stale/interrupt, budget/arena. */
    uint32_t s2 = 0u;
    uint32_t e2 = 0u;
    CHECK(vos_compat_submit_build(&svc, 1u, 1u, &staged_digest, 4u, 6u, 3u,
                                  10u, 20u, &prof, &s2, &e2) == VOS_COMPAT_OK,
          "submit_build 2 failed");
    CHECK(vos_compat_advance_build(&svc, s2, e2, 1001u, 1024u, &build_out_dig,
                                   NULL, 0u, 0u) == VOS_COMPAT_ERR_BUDGET_EXPANSION,
          "budget expansion accepted");

    const uint8_t long_diag[40] = "diagnostic-overflow-payload-record-0001";
    for (uint32_t i = 0u; i < 5u; ++i) {
        CHECK(vos_compat_advance_build(&svc, s2, e2, 50u, 1024u, &build_out_dig,
                                       long_diag, 40u, 0u) == VOS_COMPAT_OK,
              "advance_build diag fill failed");
    }
    struct vos_compat_diag_view ov_view;
    CHECK(vos_compat_read_diagnostics(&svc, s2, e2, 1u, 0u, 4u, 128u, &ov_view) == VOS_COMPAT_OK &&
              ov_view.truncated == 1u &&
              ov_view.marker_code == VOS_COMPAT_DIAG_TRUNCATED_MARKER,
          "diagnostics overflow missing truncation marker");

    /* Interrupted cancel must NOT become REUSABLE; stale handle preserves job. */
    CHECK(vos_compat_cancel_build(&svc, s2, 999u, 1u, 0u) == VOS_COMPAT_ERR_STALE_HANDLE,
          "stale handle cancel accepted");
    CHECK(svc.jobs[s2].lifecycle == VOS_COMPAT_LC_BOUND, "stale cancel altered job");
    CHECK(vos_compat_cancel_build(&svc, s2, e2, 1u, 1u) == VOS_COMPAT_ERR_LIFECYCLE_INTERRUPTED,
          "interrupted cancel succeeded");
    CHECK(svc.jobs[s2].lifecycle != VOS_COMPAT_LC_REUSABLE,
          "interrupted cancel became reusable early");

    /* Pass arena exhaustion ends job unadmitted & preserves running generation. */
    uint32_t s3 = 0u;
    uint32_t e3 = 0u;
    CHECK(vos_compat_submit_build(&svc, 1u, 1u, &staged_digest, 4u, 6u, 3u,
                                  10u, 20u, &prof, &s3, &e3) == VOS_COMPAT_OK,
          "submit_build 3 failed");
    CHECK(vos_compat_advance_build(&svc, s3, e3, 50u, 9000u, &build_out_dig,
                                   NULL, 0u, 1u) == VOS_COMPAT_ERR_PASS_ARENA_EXHAUSTED,
          "pass arena exhaustion accepted");
    CHECK(svc.jobs[s3].stage == VOS_COMPAT_JOB_FAILED, "arena exhaustion did not fail job");
    CHECK(vos_compat_cancel_build(&svc, s3, e3, 1u, 0u) == VOS_COMPAT_OK &&
              svc.jobs[s3].lifecycle == VOS_COMPAT_LC_REUSABLE,
          "clean cancel did not reach reusable");

    /* 7. Negative controls: R-12-020 external authenticator declined & old-epoch test result refused. */
    struct vos_compat_consent_req ext_creq = creq;
    ext_creq.external_roaming_key = 1u;
    CHECK(vos_compat_request_generation_consent(&svc, &ext_creq) ==
              VOS_COMPAT_ERR_EXTERNAL_AUTH_DECLINED,
          "external roaming authenticator accepted");

    struct vos_compat_test_result old_tres = tres;
    old_tres.boot_epoch = 1u;
    CHECK(vos_compat_read_successor_test_result(&svc, &old_tres, &cand_root, 42u, &out_tres) ==
              VOS_COMPAT_ERR_RESULT_UNBOUND,
          "old boot epoch test result accepted");

    /* 8. Negative controls: Epoch exhaustion retires handle namespace without wrapping. */
    uint32_t s4 = 0u;
    uint32_t e4 = 0u;
    CHECK(vos_compat_submit_build(&svc, 1u, 1u, &staged_digest, 4u, 6u, 3u,
                                  10u, 20u, &prof, &s4, &e4) == VOS_COMPAT_OK,
          "submit_build 4 failed");
    uint32_t s5 = 0u;
    uint32_t e5 = 0u;
    CHECK(vos_compat_submit_build(&svc, 1u, 1u, &staged_digest, 4u, 6u, 3u,
                                  10u, 20u, &prof, &s5, &e5) == VOS_COMPAT_ERR_EPOCH_EXHAUSTED &&
              svc.epoch_retired == 1u && svc.next_job_epoch == prof.epoch_limit,
          "epoch exhaustion wrapped or failed to retire");

    printf("compat_workflow_test: ok\n");
    return 0;
}
