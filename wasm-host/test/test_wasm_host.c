// SPDX-License-Identifier: Apache-2.0
#include "vos_wasm_host.h"

#include <stdio.h>
#include <string.h>

#define CHECK(cond, msg)                                                      \
    do {                                                                      \
        if (!(cond)) {                                                        \
            fprintf(stderr, "FAIL (%s:%d): %s\n", __FILE__, __LINE__, (msg)); \
            return 1;                                                         \
        }                                                                     \
    } while (0)

static struct vos_whost_hash make_digest(uint8_t tag)
{
    struct vos_whost_hash h;
    for (size_t i = 0u; i < VOS_WHOST_DIGEST_BYTES; ++i) {
        h.bytes[i] = (uint8_t)(tag ^ (uint8_t)(i * 5u + 3u));
    }
    return h;
}

static void fill_key(uint8_t seed, uint8_t out[VOS_WHOST_KEY_BYTES])
{
    for (size_t i = 0u; i < VOS_WHOST_KEY_BYTES; ++i) {
        out[i] = (uint8_t)((seed + i * 7u) | 1u);
    }
}

static struct vos_whost_policy default_policy(void)
{
    struct vos_whost_policy pol;
    pol.abi_version = 1u;
    pol.profile_id = 10u;
    pol.generation = 4u;
    pol.mem_page_ceiling = 64u;
    pol.table_ceiling = 256u;
    pol.stack_ceiling = 128u;
    pol.import_ceiling_mask = 0x07u;
    pol.max_epoch = 3u;
    return pol;
}

static struct vos_whost_bundle make_bundle(uint8_t mod_tag,
                                           const char *label,
                                           uint32_t abi_version,
                                           uint32_t init_pages,
                                           uint32_t max_pages,
                                           uint32_t schema_id,
                                           uint32_t req_grants_mask)
{
    struct vos_whost_bundle b;
    memset(&b, 0, sizeof(b));
    b.module_len = 32u;
    for (uint32_t i = 0u; i < b.module_len; ++i) {
        b.module_bytes[i] = (uint8_t)(mod_tag + i);
    }
    b.assets_len = 16u;
    for (uint32_t i = 0u; i < b.assets_len; ++i) {
        b.assets_bytes[i] = (uint8_t)(mod_tag ^ (uint8_t)(i + 0x20u));
    }
    const size_t llen = strlen(label);
    b.ui_label_len = (uint32_t)(llen > VOS_WHOST_MAX_LABEL_BYTES ? VOS_WHOST_MAX_LABEL_BYTES : llen);
    memcpy(b.ui_label, label, b.ui_label_len);
    b.abi_version = abi_version;
    b.core30_valid = 1u;
    b.closure_valid = 1u;
    b.descriptor_valid = 1u;
    b.init_mem_pages = init_pages;
    b.max_mem_pages = max_pages;
    b.table_limit = 64u;
    b.stack_limit = 32u;
    b.schema_id = schema_id;
    b.requested_imports_mask = req_grants_mask;
    b.has_start_fn = 1u;
    b.uses_fs_path_authority = 0u;
    (void)vos_whost_compute_closure_digest(&b, &b.closure_digest);
    (void)vos_whost_compute_bundle_digest(&b, &b.bundle_digest);
    return b;
}

static struct vos_whost_consent make_consent(const struct vos_whost_hash *digest,
                                             const char *label,
                                             uint64_t nonce)
{
    struct vos_whost_consent c;
    memset(&c, 0, sizeof(c));
    c.user_consented = 1u;
    c.credential_ok = 1u;
    c.trusted_digest = *digest;
    const size_t llen = strlen(label);
    c.ui_label_len = (uint32_t)(llen > VOS_WHOST_MAX_LABEL_BYTES ? VOS_WHOST_MAX_LABEL_BYTES : llen);
    memcpy(c.ui_label_shown, label, c.ui_label_len);
    c.nonce = nonce;
    return c;
}

int main(void)
{
    const struct vos_whost_policy pol = default_policy();
    uint8_t ckpt_key[VOS_WHOST_KEY_BYTES];
    fill_key(0x31u, ckpt_key);

    struct vos_whost_pool pool;
    CHECK(vos_whost_pool_init(&pool, &pol, ckpt_key, 64u) == VOS_WHOST_OK,
          "pool init failed");

    const struct vos_whost_bundle app_a = make_bundle(0x10u, "AppAlpha", 1u, 8u, 32u, 1u, 0x03u);
    const struct vos_whost_bundle app_b = make_bundle(0x40u, "AppAlpha", 1u, 12u, 48u, 2u, 0x06u);

    /* 1. Prepare checks closure/descriptor without executing start or spending grants. */
    CHECK(vos_whost_prepare(&pool, 0u, &app_a) == VOS_WHOST_OK, "prepare app_a failed");
    CHECK(pool.slots[0].phase == VOS_WHOST_PHASE_PREPARED &&
          pool.slots[0].start_executed == 0u &&
          pool.slots[0].new_grants_spent == 0u,
          "prepare executed start or spent grants");

    /* 2. Negative prepare controls (forged closure, bad ABI, oversized, fs path) on slot 1. */
    struct vos_whost_bundle bad_closure = app_a;
    bad_closure.closure_digest.bytes[0] ^= 0xFFu;
    CHECK(vos_whost_prepare(&pool, 1u, &bad_closure) == VOS_WHOST_ERR_FORGED_CLOSURE,
          "forged closure accepted");

    struct vos_whost_bundle bad_abi = make_bundle(0x20u, "BadAbi", 99u, 8u, 32u, 1u, 0x01u);
    CHECK(vos_whost_prepare(&pool, 1u, &bad_abi) == VOS_WHOST_ERR_INCOMPATIBLE_ABI,
          "incompatible ABI accepted");

    struct vos_whost_bundle oversized = make_bundle(0x21u, "TooBig", 1u, 8u, 128u, 1u, 0x01u);
    CHECK(vos_whost_prepare(&pool, 1u, &oversized) == VOS_WHOST_ERR_OVERSIZED_RESERVATION,
          "oversized reservation accepted");

    struct vos_whost_bundle fs_bundle = app_a;
    fs_bundle.uses_fs_path_authority = 1u;
    CHECK(vos_whost_prepare(&pool, 1u, &fs_bundle) == VOS_WHOST_ERR_FS_PATH_AUTHORITY,
          "fs path authority accepted in prepare");

    /* Failed prepares leave slot 0 prepared and slot 1 untouched free. */
    CHECK(pool.slots[0].phase == VOS_WHOST_PHASE_PREPARED &&
          pool.slots[1].phase == VOS_WHOST_PHASE_FREE,
          "failed prepare mutated slots");

    /* 3. Launch refuses UI label spoof and fs-path authority; succeeds with exact digest. */
    const struct vos_whost_consent spoof_consent = make_consent(&app_b.bundle_digest, "AppAlpha", 1u);
    CHECK(vos_whost_launch(&pool, 0u, &spoof_consent, 0x01u, 0u, 555u) ==
          VOS_WHOST_ERR_CONSENT_DIGEST_MISMATCH,
          "UI label spoof consent accepted");

    const struct vos_whost_consent consent_a = make_consent(&app_a.bundle_digest, "AppAlpha", 2u);
    CHECK(vos_whost_launch(&pool, 0u, &consent_a, 0x01u, 1u, 555u) ==
          VOS_WHOST_ERR_FS_PATH_AUTHORITY,
          "fs path authority accepted in launch");

    CHECK(vos_whost_launch(&pool, 0u, &consent_a, 0x01u, 0u, 555u) == VOS_WHOST_OK,
          "launch app_a failed");
    CHECK(pool.slots[0].phase == VOS_WHOST_PHASE_ACTIVE &&
          pool.slots[0].epoch == 1u &&
          pool.slots[0].start_executed == 1u &&
          pool.avail_pages == 56u,
          "launch postcondition mismatch");

    /* Clear-group collision refusal when another active slot claims the same group_id. */
    CHECK(vos_whost_prepare(&pool, 1u, &app_b) == VOS_WHOST_OK, "prepare slot 1 failed");
    pool.slots[1].group_id = pool.slots[0].group_id;
    const struct vos_whost_consent consent_b = make_consent(&app_b.bundle_digest, "AppAlpha", 3u);
    CHECK(vos_whost_launch(&pool, 1u, &consent_b, 0x02u, 0u, 777u) ==
          VOS_WHOST_ERR_GROUP_COLLISION,
          "clear-group collision accepted");
    pool.slots[1].group_id = 7001u;
    CHECK(vos_whost_launch(&pool, 1u, &consent_b, 0x02u, 0u, 777u) == VOS_WHOST_OK,
          "distinct group launch failed");

    /* 4. InvokeImport positive + cross-instance, stale epoch, pool-cap export, tagged transport. */
    struct vos_whost_import_call call;
    memset(&call, 0, sizeof(call));
    call.handle.act_id = pool.slots[0].act_id;
    call.handle.epoch = pool.slots[0].epoch;
    call.handle.group_id = pool.slots[0].group_id;
    call.handle.import_bit = 0x01u;
    call.handle.scope_ok = 1u;
    call.op_id = 42u;
    call.exports_pool_cap = 0u;
    call.tagged_transport = 0u;
    call.reply_epoch = pool.slots[0].epoch;
    call.yield_bounded = 1u;

    uint32_t rep_ep = 0u;
    CHECK(vos_whost_invoke_import(&pool, 0u, &call, &rep_ep) == VOS_WHOST_OK &&
          rep_ep == 1u,
          "valid invoke_import failed");

    struct vos_whost_import_call bad_call = call;
    bad_call.handle.group_id = pool.slots[1].group_id;
    CHECK(vos_whost_invoke_import(&pool, 0u, &bad_call, &rep_ep) == VOS_WHOST_ERR_HANDLE_SCOPE,
          "cross-instance handle accepted");

    bad_call = call;
    bad_call.handle.import_bit = 0x02u;
    CHECK(vos_whost_invoke_import(&pool, 0u, &bad_call, &rep_ep) == VOS_WHOST_ERR_OVER_SCOPED_GRANT,
          "ungranted import accepted");

    bad_call = call;
    bad_call.exports_pool_cap = 1u;
    CHECK(vos_whost_invoke_import(&pool, 0u, &bad_call, &rep_ep) == VOS_WHOST_ERR_POOL_CAP_EXPORT,
          "pool-cap export accepted");

    bad_call = call;
    bad_call.tagged_transport = 1u;
    CHECK(vos_whost_invoke_import(&pool, 0u, &bad_call, &rep_ep) == VOS_WHOST_ERR_TAGGED_TRANSPORT,
          "tagged transport accepted");

    bad_call = call;
    bad_call.reply_epoch = 0u;
    CHECK(vos_whost_invoke_import(&pool, 0u, &bad_call, &rep_ep) == VOS_WHOST_ERR_EPOCH_MISMATCH,
          "stale reply epoch accepted");

    /* 5. Transactional Replace: pre-commit failure keeps old binding live; commit switches cleanly. */
    struct vos_whost_replace_req rep_req;
    memset(&rep_req, 0, sizeof(rep_req));
    rep_req.candidate = app_b;
    rep_req.consent = NULL;
    rep_req.new_grants_mask = 0x04u;
    rep_req.transition_reserved = 1u;
    rep_req.commit_authorized = 1u;
    rep_req.durable_policy_ok = 1u;
    rep_req.post_commit_ok = 1u;
    rep_req.acked_durable_digest = make_digest(0x71u);

    CHECK(vos_whost_replace(&pool, 0u, &rep_req, 888u) == VOS_WHOST_ERR_NO_CONSENT,
          "pre-commit replace without consent succeeded");
    CHECK(pool.slots[0].phase == VOS_WHOST_PHASE_ACTIVE &&
          pool.slots[0].epoch == 1u &&
          pool.slots[0].active_grants_mask == 0x01u &&
          vos_whost_invoke_import(&pool, 0u, &call, &rep_ep) == VOS_WHOST_OK,
          "pre-commit replace failure damaged old binding");

    rep_req.consent = &consent_b;
    CHECK(vos_whost_replace(&pool, 0u, &rep_req, 888u) == VOS_WHOST_OK,
          "valid replace failed");
    CHECK(pool.slots[0].epoch == 2u &&
          pool.slots[0].active_grants_mask == 0x04u &&
          memcmp(pool.slots[0].active_bundle.bundle_digest.bytes,
                 app_b.bundle_digest.bytes, VOS_WHOST_DIGEST_BYTES) == 0,
          "replace did not install candidate bundle/grants");

    /* Old handle from epoch 1 must now be rejected. */
    CHECK(vos_whost_invoke_import(&pool, 0u, &call, &rep_ep) == VOS_WHOST_ERR_HANDLE_SCOPE,
          "stale handle survived replace");

    /* Post-commit failure on slot 1: closes cleanly with acknowledged durable work. */
    rep_req.post_commit_ok = 0u;
    rep_req.acked_durable_digest = make_digest(0x72u);
    CHECK(vos_whost_replace(&pool, 1u, &rep_req, 999u) == VOS_WHOST_ERR_POST_COMMIT_CLOSED,
          "post-commit failure did not return closed status");
    CHECK(pool.slots[1].phase == VOS_WHOST_PHASE_SANITIZED &&
          pool.slots[1].active_grants_mask == 0u &&
          pool.slots[1].session_key == 0u &&
          pool.slots[1].zeroized == 1u &&
          pool.slots[1].durable.acked == 1u &&
          memcmp(pool.slots[1].durable.bundle_digest.bytes,
                 app_b.bundle_digest.bytes, VOS_WHOST_DIGEST_BYTES) == 0,
          "post-commit failure leaked grants or lost durable state");

    /* 6. Cancel/Close lifecycle and sweep-before-reuse barrier on slot 0. */
    CHECK(vos_whost_cancel_begin(&pool, 0u) == VOS_WHOST_OK, "cancel_begin failed");
    pool.slots[0].pending_imports = 2u;
    CHECK(vos_whost_invoke_import(&pool, 0u, &call, &rep_ep) == VOS_WHOST_ERR_BAD_PHASE,
          "invoke allowed during cancelling");
    CHECK(vos_whost_enter_sweeping(&pool, 0u) == VOS_WHOST_ERR_PENDING_IMPORTS,
          "sweeping entered with pending imports");
    CHECK(vos_whost_complete_reuse(&pool, 0u) == VOS_WHOST_ERR_NOT_SANITIZED,
          "reuse allowed before sweep/sanitize");

    CHECK(vos_whost_drain_imports(&pool, 0u) == VOS_WHOST_OK, "drain_imports failed");
    CHECK(vos_whost_enter_sweeping(&pool, 0u) == VOS_WHOST_OK, "enter_sweeping failed");
    CHECK(vos_whost_sweep_and_zeroize(&pool, 0u) == VOS_WHOST_OK, "sweep_and_zeroize failed");
    for (size_t i = 0u; i < sizeof(pool.slots[0].arena_canary); ++i) {
        CHECK(pool.slots[0].arena_canary[i] == 0u, "arena canary not zeroized");
    }
    CHECK(vos_whost_complete_reuse(&pool, 0u) == VOS_WHOST_OK, "complete_reuse failed");
    CHECK(pool.slots[0].phase == VOS_WHOST_PHASE_REUSABLE &&
          pool.slots[0].epoch == 2u &&
          pool.avail_pages == 64u,
          "reusable postcondition mismatch");

    /* 7. Restore from authenticated semantic checkpoint using current grants only. */
    struct vos_whost_checkpoint ckpt;
    memset(&ckpt, 0, sizeof(ckpt));
    ckpt.bundle_digest = app_b.bundle_digest;
    ckpt.abi_version = 1u;
    ckpt.profile_id = 10u;
    ckpt.schema_id = 2u;
    ckpt.generation = 4u;
    ckpt.durable_digest = make_digest(0x73u);
    ckpt.embedded_old_grants_mask = 0x07u;
    ckpt.embedded_tagged_mem = 1u;
    ckpt.embedded_session_key = 12345u;
    CHECK(vos_whost_seal_checkpoint(&pool, &ckpt) == VOS_WHOST_OK, "seal ckpt failed");

    struct vos_whost_checkpoint bad_ckpt = ckpt;
    bad_ckpt.hmac[0] ^= 0xFFu;
    CHECK(vos_whost_restore(&pool, 0u, &app_b, &bad_ckpt, 0x04u, 321u) ==
          VOS_WHOST_ERR_UNAUTH_CHECKPOINT,
          "unauthenticated checkpoint accepted");

    bad_ckpt = ckpt;
    bad_ckpt.schema_id = 99u;
    CHECK(vos_whost_seal_checkpoint(&pool, &bad_ckpt) == VOS_WHOST_OK, "seal stale ckpt");
    CHECK(vos_whost_restore(&pool, 0u, &app_b, &bad_ckpt, 0x04u, 321u) ==
          VOS_WHOST_ERR_STALE_SCHEMA,
          "stale schema checkpoint accepted");

    bad_ckpt = ckpt;
    bad_ckpt.generation = 3u;
    CHECK(vos_whost_seal_checkpoint(&pool, &bad_ckpt) == VOS_WHOST_OK, "seal old gen ckpt");
    CHECK(vos_whost_restore(&pool, 0u, &app_b, &bad_ckpt, 0x04u, 321u) ==
          VOS_WHOST_ERR_INCOMPATIBLE_GEN,
          "incompatible generation checkpoint accepted");

    /* Positive restore uses current grants (0x04) and fresh session key (321), not embedded old ones. */
    CHECK(vos_whost_restore(&pool, 0u, &app_b, &ckpt, 0x04u, 321u) == VOS_WHOST_OK,
          "valid checkpoint restore failed");
    CHECK(pool.slots[0].active_grants_mask == 0x04u &&
          pool.slots[0].session_key == 321u &&
          pool.slots[0].tagged_mem == 0u &&
          pool.slots[0].epoch == 3u,
          "restore resurrected old grants/keys/tags");

    /* 8. Epoch exhaustion retires handle namespace without wraparound. */
    CHECK(vos_whost_cancel_begin(&pool, 0u) == VOS_WHOST_OK, "cancel_begin 2");
    CHECK(vos_whost_enter_sweeping(&pool, 0u) == VOS_WHOST_OK, "enter_sweeping 2");
    CHECK(vos_whost_sweep_and_zeroize(&pool, 0u) == VOS_WHOST_OK, "sweep 2");
    CHECK(vos_whost_complete_reuse(&pool, 0u) == VOS_WHOST_OK, "reuse 2");
    CHECK(vos_whost_prepare(&pool, 0u, &app_a) == VOS_WHOST_OK, "prepare after max_epoch");
    CHECK(vos_whost_launch(&pool, 0u, &consent_a, 0x01u, 0u, 111u) ==
          VOS_WHOST_ERR_EPOCH_EXHAUSTED,
          "epoch exhaustion did not refuse launch");
    CHECK(pool.slots[0].epoch == 3u && pool.slots[0].epoch_retired == 1u,
          "exhausted epoch wrapped or failed to retire");

    printf("wasm_host_test: ok\n");
    return 0;
}
