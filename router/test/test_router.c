// SPDX-License-Identifier: Apache-2.0
#include "vos_router.h"

#include <stdio.h>
#include <string.h>

#define CHECK(cond, msg)                                                       \
    do {                                                                       \
        if (!(cond)) {                                                         \
            fprintf(stderr, "router control failed (%s): %s\n", #cond, (msg)); \
            return 1;                                                          \
        }                                                                      \
    } while (0)

static uint32_t test_req_limit(uint32_t role, uint32_t op, void *ctx)
{
    (void)role;
    (void)op;
    (void)ctx;
    return 4U;
}

static int test_proto_op(uint32_t role, uint32_t op, void *ctx)
{
    (void)ctx;
    return role == op;
}

static int test_needs_approval(uint32_t role, uint32_t op, void *ctx)
{
    (void)role;
    (void)op;
    (void)ctx;
    return 1;
}

static int consent_allow_all(
    const vos_cred_bindings *cred, const vos_cred_request *req,
    uint32_t current_used, void *ctx)
{
    (void)cred;
    (void)req;
    (void)current_used;
    (void)ctx;
    return 1;
}

static int consent_deny_all(
    const vos_cred_bindings *cred, const vos_cred_request *req,
    uint32_t current_used, void *ctx)
{
    (void)cred;
    (void)req;
    (void)current_used;
    (void)ctx;
    return 0;
}

static int consent_once(
    const vos_cred_bindings *cred, const vos_cred_request *req,
    uint32_t current_used, void *ctx)
{
    (void)cred;
    (void)req;
    (void)ctx;
    return current_used == 0U;
}

static int test_namespaces_and_routing(void)
{
    const vos_router_extent extents[3] = {
        { .base = 10U, .span = 40U, .domain = 0U, .space = 0U },
        { .base = 50U, .span = 40U, .domain = 1U, .space = 0U },
        { .base = 90U, .span = 20U, .domain = 0U, .space = 1U }
    };
    const vos_router_composition comp = {
        .extents = extents,
        .extent_count = 3U,
        .queue_bound = 4U,
        .result_bound = 8U,
        .ring_capacity = 64U,
        .live_epoch = 4U,
        .discipline = VOS_ROUTER_REFUSE_TYPED
    };
    CHECK(vos_router_composition_valid(&comp) == 1, "valid composition rejected");

    const vos_router_extent spanning[2] = {
        { .base = 10U, .span = 40U, .domain = 0U, .space = 0U },
        { .base = 40U, .span = 40U, .domain = 1U, .space = 2U }
    };
    vos_router_composition bad = comp;
    bad.extents = spanning;
    bad.extent_count = 2U;
    CHECK(vos_router_composition_valid(&bad) == 0, "cross-domain overlapping extents accepted");

    const vos_router_extent unplaced[1] = {
        { .base = 10U, .span = 0U, .domain = 0U, .space = 0U }
    };
    bad = comp;
    bad.extents = unplaced;
    bad.extent_count = 1U;
    CHECK(vos_router_composition_valid(&bad) == 0, "zero-span extent accepted");

    bad = comp;
    bad.queue_bound = 0U;
    CHECK(vos_router_composition_valid(&bad) == 0, "zero queue bound accepted");

    bad = comp;
    bad.queue_bound = 65U;
    CHECK(vos_router_composition_valid(&bad) == 0, "oversize queue bound accepted");

    bad = comp;
    bad.result_bound = 0U;
    CHECK(vos_router_composition_valid(&bad) == 0, "zero result bound accepted");

    /* Index writes: plain accepted, tagged refused, cross-domain refused. */
    const vos_router_word plain_words[6] = {
        {0U, 0U}, {0U, 0U}, {2U, 0U}, {11U, 0U}, {5U, 0U}, {3U, 0U}
    };
    vos_router_write_record staged[6];
    CHECK(vos_router_stage_index_key(&comp, 0U, 0U, 6U, plain_words, 6U, staged, 6U) == VOS_ROUTER_OK,
          "plain key staging failed");
    CHECK(staged[0].address == 16U && staged[5].address == 21U, "staged key addresses wrong");
    CHECK(vos_router_validate_write(&comp, 0U, 0U, staged, 6U) == VOS_ROUTER_OK,
          "plain key write validation failed");

    vos_router_word tagged_words[6] = {
        {0U, 0U}, {0U, 0U}, {2U, 0U}, {11U, 0U}, {5U, 0U}, {2U, 1U}
    };
    vos_router_write_record bad_staged[6];
    CHECK(vos_router_stage_index_key(&comp, 0U, 0U, 6U, tagged_words, 6U, bad_staged, 6U)
              == VOS_ROUTER_ERR_TAGGED_WRITE,
          "tagged key staging accepted");
    vos_router_write_record tagged_rec = { .address = 16U, .word = { .bits = 2U, .tag = 1U } };
    CHECK(vos_router_validate_write(&comp, 0U, 0U, &tagged_rec, 1U) == VOS_ROUTER_ERR_TAGGED_WRITE,
          "tagged key write accepted");

    vos_router_write_record cross_rec = { .address = 55U, .word = { .bits = 9U, .tag = 0U } };
    CHECK(vos_router_validate_write(&comp, 0U, 0U, &cross_rec, 1U) == VOS_ROUTER_ERR_CROSS_DOMAIN,
          "cross-domain write accepted");

    vos_router_write_record oob_rec = { .address = 120U, .word = { .bits = 9U, .tag = 0U } };
    CHECK(vos_router_validate_write(&comp, 0U, 0U, &oob_rec, 1U) == VOS_ROUTER_ERR_OUT_OF_EXTENT,
          "out-of-extent write accepted");

    /* Sessions, epoch invalidation, and derivability. */
    const vos_router_session sessions[3] = {
        { .id = 0U, .cap = { .domain = 0U, .space = 0U, .rights = 2U }, .epoch = 4U, .active = 1U },
        { .id = 1U, .cap = { .domain = 1U, .space = 0U, .rights = 3U }, .epoch = 4U, .active = 1U },
        { .id = 2U, .cap = { .domain = 0U, .space = 0U, .rights = 7U }, .epoch = 3U, .active = 1U }
    };
    const vos_router_ask valid_ask = { .domain = 0U, .space = 0U, .object = 11U, .rights = 2U };
    const vos_router_ask wide_ask = { .domain = 0U, .space = 0U, .object = 11U, .rights = 3U };
    const vos_router_ask foreign_dom_ask = { .domain = 1U, .space = 0U, .object = 11U, .rights = 2U };
    const vos_router_ask foreign_sp_ask = { .domain = 0U, .space = 1U, .object = 11U, .rights = 2U };

    vos_router_answer ans = vos_router_route(&comp, sessions, 3U, 0U, &valid_ask);
    CHECK(ans.kind == VOS_ROUTER_ANSWER_GRANTED && ans.obj_cap.rights == 2U, "valid ask refused");
    CHECK(vos_router_cap_derivable(&sessions[0].cap, &ans.obj_cap) == 1, "granted cap not derivable");

    ans = vos_router_route(&comp, sessions, 3U, 0U, &wide_ask);
    CHECK(ans.kind == VOS_ROUTER_ANSWER_REFUSED, "widened ask not refused");

    ans = vos_router_route(&comp, sessions, 3U, 0U, &foreign_dom_ask);
    CHECK(ans.kind == VOS_ROUTER_ANSWER_REFUSED, "cross-domain ask not refused");

    ans = vos_router_route(&comp, sessions, 3U, 0U, &foreign_sp_ask);
    CHECK(ans.kind == VOS_ROUTER_ANSWER_REFUSED, "foreign-space ask not refused");

    ans = vos_router_route(&comp, sessions, 3U, 2U, &valid_ask);
    CHECK(ans.kind == VOS_ROUTER_ANSWER_REFUSED, "stale epoch session granted authority");

    vos_router_composition empty_comp = comp;
    empty_comp.discipline = VOS_ROUTER_ANSWER_EMPTY;
    ans = vos_router_route(&empty_comp, sessions, 3U, 0U, &wide_ask);
    CHECK(ans.kind == VOS_ROUTER_ANSWER_EMPTY_RESULT, "AnswerEmpty discipline wrong");

    vos_router_composition trunc_comp = comp;
    trunc_comp.discipline = VOS_ROUTER_GRANT_TRUNCATED;
    ans = vos_router_route(&trunc_comp, sessions, 3U, 0U, &wide_ask);
    CHECK(ans.kind == VOS_ROUTER_ANSWER_GRANTED && ans.obj_cap.rights == 2U
          && vos_router_cap_derivable(&sessions[0].cap, &ans.obj_cap) == 1,
          "GrantTruncated discipline failed derivability");

    /* Bounded result delivery. */
    vos_router_obj_cap cand[9];
    vos_router_obj_cap out[9];
    size_t out_n = 99U;
    for (size_t i = 0U; i < 9U; ++i) {
        cand[i].domain = 0U;
        cand[i].space = 0U;
        cand[i].object = 100U + i;
        cand[i].rights = 2U;
    }
    CHECK(vos_router_deliver_results(&comp, sessions, 3U, 0U, cand, 8U, out, 9U, &out_n) == VOS_ROUTER_OK
          && out_n == 8U,
          "bounded result delivery at bound failed");
    CHECK(vos_router_deliver_results(&comp, sessions, 3U, 0U, cand, 9U, out, 9U, &out_n)
              == VOS_ROUTER_ERR_CAPACITY && out_n == 0U,
          "result delivery past bound accepted");
    cand[0].rights = 3U;
    CHECK(vos_router_deliver_results(&comp, sessions, 3U, 0U, cand, 1U, out, 9U, &out_n)
              == VOS_ROUTER_ERR_DENIED && out_n == 0U,
          "underivable result cap delivered");
    return 0;
}

static int test_live_query_deltas(void)
{
    const vos_router_extent extents[1] = {
        { .base = 10U, .span = 40U, .domain = 0U, .space = 0U }
    };
    const vos_router_composition comp = {
        .extents = extents,
        .extent_count = 1U,
        .queue_bound = 4U,
        .result_bound = 8U,
        .ring_capacity = 64U,
        .live_epoch = 4U,
        .discipline = VOS_ROUTER_REFUSE_TYPED
    };
    vos_delta qbuf[4];
    vos_router_sub sub;
    CHECK(vos_router_establish_sub(&comp, &sub, 0U, 0U, 0U, qbuf, 4U) == VOS_ROUTER_OK,
          "establish sub failed");
    CHECK(sub.count == 1U && sub.queue[0].kind == VOS_DELTA_RESCAN && sub.phase == VOS_SUB_LIVE,
          "initial establishment must start with rescan marker");

    /* Reset queue to live 2-delta fixture mirroring ObjectRouter.v. */
    sub.count = 2U;
    sub.queue[0] = (vos_delta){ .kind = VOS_DELTA_ADDED, .object_id = 11U };
    sub.queue[1] = (vos_delta){ .kind = VOS_DELTA_REMOVED, .object_id = 12U };
    sub.phase = VOS_SUB_LIVE;

    const vos_delta two[2] = {
        { .kind = VOS_DELTA_ADDED, .object_id = 13U },
        { .kind = VOS_DELTA_ADDED, .object_id = 14U }
    };
    const vos_delta three[3] = {
        { .kind = VOS_DELTA_ADDED, .object_id = 13U },
        { .kind = VOS_DELTA_ADDED, .object_id = 14U },
        { .kind = VOS_DELTA_ADDED, .object_id = 15U }
    };

    /* Pre-commit transaction must publish nothing. */
    const vos_router_txn open_txn = { .id = 8U, .committed = 0U };
    CHECK(vos_router_publish_deltas(&comp, &open_txn, &sub, two, 2U) == VOS_ROUTER_OK,
          "uncommitted publish errored");
    CHECK(sub.count == 2U && sub.phase == VOS_SUB_LIVE, "pre-commit delta published");

    /* Exact bound publication retains all 4 deltas. */
    vos_router_sub sub_fit = sub;
    vos_delta qfit[4];
    memcpy(qfit, qbuf, sizeof(qfit));
    sub_fit.queue = qfit;
    const vos_router_txn committed_txn = vos_router_commit_txn(&sub_fit, 1U, VOS_SUBMIT_WOULD_BLOCK, open_txn);
    CHECK(committed_txn.committed == 1U, "backpressuring commit on full ring");

    CHECK(vos_router_publish_deltas(&comp, &committed_txn, &sub_fit, two, 2U) == VOS_ROUTER_OK,
          "exact-bound publish failed");
    CHECK(sub_fit.count == 4U && sub_fit.phase == VOS_SUB_LIVE
          && qfit[2].object_id == 13U && qfit[3].object_id == 14U,
          "exact-bound publish altered deltas");

    /* One past bound: exact-one VOS_DELTA_RESCAN marker, bounded storage, no further deltas. */
    CHECK(vos_router_publish_deltas(&comp, &committed_txn, &sub, three, 3U) == VOS_ROUTER_OK,
          "overflow publish failed");
    CHECK(sub.count == 4U && sub.phase == VOS_SUB_RESCAN_REQUIRED,
          "overflow did not enter rescan-required within bound");
    size_t rescan_count = 0U;
    for (size_t i = 0U; i < sub.count; ++i) {
        if (sub.queue[i].kind == VOS_DELTA_RESCAN) {
            ++rescan_count;
        }
    }
    CHECK(rescan_count == 1U && sub.queue[3].kind == VOS_DELTA_RESCAN
          && sub.queue[2].kind == VOS_DELTA_ADDED && sub.queue[2].object_id == 13U,
          "twin rescan marker or wrong prefix on overflow");

    /* Subsequent publication adds zero deltas. */
    CHECK(vos_router_publish_deltas(&comp, &committed_txn, &sub, two, 2U) == VOS_ROUTER_OK,
          "post-marker publish errored");
    CHECK(sub.count == 4U && sub.phase == VOS_SUB_RESCAN_REQUIRED,
          "further delta added after rescan marker");

    /* Commit must not backpressure even when a subscription is in VOS_SUB_RESCAN_REQUIRED. */
    const vos_router_txn committed2 = vos_router_commit_txn(&sub, 1U, VOS_SUBMIT_WOULD_BLOCK, open_txn);
    CHECK(committed2.committed == 1U, "backpressuring commit on rescan-required subscription");

    /* Reboot erases subscriptions; recovery re-establishes with rescan. */
    vos_router_reboot_subs(&sub, 1U);
    CHECK(sub.active == 0U && sub.count == 0U && sub.phase == VOS_SUB_RESCAN_REQUIRED,
          "reboot survival of subscription");
    CHECK(vos_router_establish_sub(&comp, &sub, 1U, 0U, 0U, qbuf, 4U) == VOS_ROUTER_OK,
          "post-reboot re-establishment failed");
    CHECK(sub.active == 1U && sub.count == 1U && sub.queue[0].kind == VOS_DELTA_RESCAN,
          "post-reboot recovery did not begin with rescan");
    return 0;
}

static int test_credential_handles(void)
{
    const vos_cred_policy policy = {
        .role_count = 3U,
        .principal_count = 4U,
        .scope_count = 5U,
        .operation_count = 3U,
        .transcript_count = 6U,
        .request_limit = test_req_limit,
        .protocol_operation = test_proto_op,
        .needs_approval = test_needs_approval,
        .policy_ctx = NULL
    };

    const vos_cred_bindings parent_b = {
        .role = 1U,
        .principal = 2U,
        .scope_mask = (1ULL << 1U) | (1ULL << 2U),
        .op_mask = (1ULL << 1U) | (1ULL << 2U),
        .transcript = 3U,
        .use_ceiling = 2U,
        .expiry = 20U,
        .account_id = 7U
    };
    const vos_cred_bindings child_b = {
        .role = 1U,
        .principal = 2U,
        .scope_mask = (1ULL << 1U),
        .op_mask = (1ULL << 1U),
        .transcript = 3U,
        .use_ceiling = 1U,
        .expiry = 15U,
        .account_id = 7U
    };

    vos_cred_vault_slot slots[8];
    vos_cred_vault vault;
    vos_cred_vault_init(&vault, slots, 8U);

    vos_cred_handle parent_h;
    CHECK(vos_cred_issue_handle(&vault, &parent_b, &parent_h) == VOS_ROUTER_OK,
          "issue parent handle failed");
    CHECK(parent_h.kind == VOS_HANDLE_SEALED, "issued handle not sealed");

    vos_cred_bindings resolved;
    CHECK(vos_cred_resolve_sealed(&vault, &parent_h, &resolved) == VOS_ROUTER_OK,
          "resolve sealed failed");
    CHECK(resolved.role == parent_b.role && resolved.principal == parent_b.principal
          && resolved.scope_mask == parent_b.scope_mask && resolved.op_mask == parent_b.op_mask
          && resolved.transcript == parent_b.transcript
          && resolved.use_ceiling == parent_b.use_ceiling && resolved.expiry == parent_b.expiry
          && resolved.account_id == parent_b.account_id,
          "resolved seven bindings differ");

    vos_cred_handle child_h;
    CHECK(vos_cred_delegate_handle(&policy, &vault, &parent_h, &child_b, &child_h) == VOS_ROUTER_OK,
          "monotone child delegation failed");

    /* Raw handle and export requests must be refused. */
    const uint8_t payload[2] = { 17U, 23U };
    const vos_cred_request valid_req = {
        .role = 1U, .principal = 2U, .scope_bit = 1U, .op_bit = 1U,
        .transcript = 3U, .bytes = payload, .byte_len = 2U
    };
    uint32_t accounts[10] = { 0U };
    vos_cred_server server = {
        .account_used = accounts,
        .account_count = 10U,
        .server_now = 10U,
        .consent_allows = consent_allow_all,
        .consent_ctx = NULL
    };

    const vos_cred_handle_request export_req = {
        .kind = VOS_HANDLE_REQ_EXPORT_SECRET,
        .protocol_req = valid_req
    };
    CHECK(vos_cred_use_handle(&policy, &vault, &server, &parent_h, &export_req) == VOS_ROUTER_ERR_DENIED,
          "raw export accepted");

    vos_cred_handle raw_h = parent_h;
    raw_h.kind = VOS_HANDLE_RAW;
    const vos_cred_handle_request proto_req = {
        .kind = VOS_HANDLE_REQ_PROTOCOL_USE,
        .protocol_req = valid_req
    };
    CHECK(vos_cred_use_handle(&policy, &vault, &server, &raw_h, &proto_req) == VOS_ROUTER_ERR_DENIED,
          "raw export / unsealed handle accepted");
    CHECK(vos_cred_resolve_sealed(&vault, &raw_h, &resolved) == VOS_ROUTER_ERR_DENIED,
          "raw export resolved");

    /* Widened delegations across all bindings and cloned account counter must fail. */
    vos_cred_bindings bad_child = child_b;
    vos_cred_handle bad_h;

    bad_child = child_b; bad_child.role = 2U;
    CHECK(vos_cred_delegate_handle(&policy, &vault, &parent_h, &bad_child, &bad_h) == VOS_ROUTER_ERR_DENIED,
          "widened delegation of role accepted");

    bad_child = child_b; bad_child.principal = 3U;
    CHECK(vos_cred_delegate_handle(&policy, &vault, &parent_h, &bad_child, &bad_h) == VOS_ROUTER_ERR_DENIED,
          "widened delegation of principal accepted");

    bad_child = child_b; bad_child.scope_mask = (1ULL << 1U) | (1ULL << 4U);
    CHECK(vos_cred_delegate_handle(&policy, &vault, &parent_h, &bad_child, &bad_h) == VOS_ROUTER_ERR_DENIED,
          "widened delegation of scope accepted");

    bad_child = child_b; bad_child.op_mask = (1ULL << 1U) | (1ULL << 0U);
    CHECK(vos_cred_delegate_handle(&policy, &vault, &parent_h, &bad_child, &bad_h) == VOS_ROUTER_ERR_DENIED,
          "widened delegation of operation accepted");

    bad_child = child_b; bad_child.transcript = 4U;
    CHECK(vos_cred_delegate_handle(&policy, &vault, &parent_h, &bad_child, &bad_h) == VOS_ROUTER_ERR_DENIED,
          "widened delegation of transcript accepted");

    bad_child = child_b; bad_child.use_ceiling = 3U;
    CHECK(vos_cred_delegate_handle(&policy, &vault, &parent_h, &bad_child, &bad_h) == VOS_ROUTER_ERR_DENIED,
          "widened delegation of use ceiling accepted");

    bad_child = child_b; bad_child.expiry = 21U;
    CHECK(vos_cred_delegate_handle(&policy, &vault, &parent_h, &bad_child, &bad_h) == VOS_ROUTER_ERR_DENIED,
          "widened delegation of expiry accepted");

    bad_child = child_b; bad_child.account_id = 8U;
    CHECK(vos_cred_delegate_handle(&policy, &vault, &parent_h, &bad_child, &bad_h) == VOS_ROUTER_ERR_DENIED,
          "cloned account counter accepted in delegation");

    /* Child spends shared account; parent observes charge; exhaustion stops both. */
    CHECK(vos_cred_use_handle(&policy, &vault, &server, &child_h, &proto_req) == VOS_ROUTER_OK,
          "valid child handle use refused");
    CHECK(accounts[7] == 1U, "shared account not charged");
    CHECK(vos_cred_use_handle(&policy, &vault, &server, &child_h, &proto_req) == VOS_ROUTER_ERR_DENIED,
          "child handle exceeded ceiling");
    CHECK(accounts[7] == 1U, "failed use modified account");

    CHECK(vos_cred_use_handle(&policy, &vault, &server, &parent_h, &proto_req) == VOS_ROUTER_OK,
          "parent handle refused with remaining shared budget");
    CHECK(accounts[7] == 2U, "parent use did not charge shared account");
    CHECK(vos_cred_use_handle(&policy, &vault, &server, &parent_h, &proto_req) == VOS_ROUTER_ERR_DENIED,
          "parent handle exceeded shared ceiling");
    CHECK(accounts[7] == 2U && accounts[8] == 0U, "account counter corruption");

    /* Trusted-path consent and expiry enforcement. */
    accounts[7] = 0U;
    server.consent_allows = consent_deny_all;
    CHECK(vos_cred_use_handle(&policy, &vault, &server, &parent_h, &proto_req) == VOS_ROUTER_ERR_DENIED,
          "denied consent accepted");
    CHECK(accounts[7] == 0U, "denied consent charged account");

    server.consent_allows = consent_once;
    CHECK(vos_cred_use_handle(&policy, &vault, &server, &parent_h, &proto_req) == VOS_ROUTER_OK,
          "first consent_once refused");
    CHECK(vos_cred_use_handle(&policy, &vault, &server, &parent_h, &proto_req) == VOS_ROUTER_ERR_DENIED,
          "replayed ordinal consent accepted");

    accounts[7] = 0U;
    server.consent_allows = consent_allow_all;
    server.server_now = 20U;
    CHECK(vos_cred_use_handle(&policy, &vault, &server, &parent_h, &proto_req) == VOS_ROUTER_ERR_DENIED,
          "expired credential accepted");

    /* Schema payload length bound check. */
    server.server_now = 10U;
    const uint8_t overlong[5] = { 0U, 1U, 2U, 3U, 4U };
    vos_cred_handle_request overlong_req = proto_req;
    overlong_req.protocol_req.bytes = overlong;
    overlong_req.protocol_req.byte_len = 5U;
    CHECK(vos_cred_use_handle(&policy, &vault, &server, &parent_h, &overlong_req) == VOS_ROUTER_ERR_DENIED,
          "overlong request payload accepted");

    return 0;
}

int main(void)
{
    if (test_namespaces_and_routing() != 0) {
        return 1;
    }
    if (test_live_query_deltas() != 0) {
        return 1;
    }
    if (test_credential_handles() != 0) {
        return 1;
    }
    fprintf(stderr, "ok router C controls: namespaces, deltas, sealed 7-binding handles\n");
    return 0;
}
