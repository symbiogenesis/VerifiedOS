// SPDX-License-Identifier: Apache-2.0
#include "vos_transactor.h"

#include <stdio.h>
#include <string.h>

#define CHECK(cond, msg)                                                      \
    do {                                                                      \
        if (!(cond)) {                                                        \
            fprintf(stderr, "FAIL (%s:%d): %s\n", __FILE__, __LINE__, (msg)); \
            return 1;                                                         \
        }                                                                     \
    } while (0)

static struct vos_tx_object make_obj(const char *text,
                                     const struct vos_tx_hash *kids,
                                     uint32_t kid_count)
{
    struct vos_tx_object obj;
    memset(&obj, 0, sizeof(obj));
    if (text != NULL) {
        const size_t len = strlen(text);
        obj.payload_len = (uint32_t)len;
        memcpy(obj.payload, text, len);
    }
    obj.kid_count = kid_count;
    for (uint32_t i = 0u; i < kid_count; ++i) {
        obj.kids[i] = kids[i];
    }
    return obj;
}

static struct vos_tx_policy make_policy(uint32_t walk_depth)
{
    struct vos_tx_policy policy;
    memset(&policy, 0, sizeof(policy));
    policy.walk_depth = walk_depth;
    policy.key_count = 1u;
    policy.keys[0].enrolled = 1u;
    policy.keys[0].key_id = 3u;
    for (uint32_t i = 0u; i < VOS_CRYPTO_KEY_BYTES_256; ++i) {
        policy.keys[0].hmac_key[i] = (uint8_t)(0xA0u + i);
    }
    return policy;
}

static struct vos_tx_signed_root make_signed_root(const struct vos_tx_policy *policy,
                                                  const struct vos_tx_hash *root,
                                                  uint64_t version,
                                                  uint64_t declared_floor,
                                                  uint64_t key_id)
{
    struct vos_tx_signed_root sr;
    memset(&sr, 0, sizeof(sr));
    sr.root = *root;
    sr.version = version;
    sr.declared_floor = declared_floor;
    sr.key_id = key_id;
    (void)vos_tx_sign_root(policy, &sr);
    return sr;
}

static struct vos_tx_hash make_checkpoint(uint8_t tag)
{
    struct vos_tx_hash h;
    for (size_t i = 0u; i < VOS_TX_DIGEST_BYTES; ++i) {
        h.bytes[i] = (uint8_t)(tag ^ (uint8_t)i);
    }
    return h;
}

static int test_path_read(void)
{
    struct vos_tx_store store;
    vos_tx_store_init(&store);

    const struct vos_tx_object leaf_a_obj = make_obj("leaf-alpha", NULL, 0u);
    const struct vos_tx_object leaf_b_obj = make_obj("leaf-beta", NULL, 0u);
    const struct vos_tx_object stray_obj = make_obj("stray-leaf", NULL, 0u);

    struct vos_tx_hash leaf_a;
    struct vos_tx_hash leaf_b;
    struct vos_tx_hash stray;
    CHECK(vos_tx_store_put(&store, &leaf_a_obj, &leaf_a) == VOS_TX_OK, "put leaf_a");
    CHECK(vos_tx_store_put(&store, &leaf_b_obj, &leaf_b) == VOS_TX_OK, "put leaf_b");
    CHECK(vos_tx_store_put(&store, &stray_obj, &stray) == VOS_TX_OK, "put stray");

    const struct vos_tx_hash mid_kids[2] = { leaf_a, leaf_b };
    const struct vos_tx_object mid_obj = make_obj("mid-node", mid_kids, 2u);
    struct vos_tx_hash mid;
    CHECK(vos_tx_store_put(&store, &mid_obj, &mid) == VOS_TX_OK, "put mid");

    const struct vos_tx_hash root_kids[1] = { mid };
    const struct vos_tx_object root_obj = make_obj("root-node", root_kids, 1u);
    struct vos_tx_hash root;
    CHECK(vos_tx_store_put(&store, &root_obj, &root) == VOS_TX_OK, "put root");

    uint8_t buf[VOS_TX_MAX_PAYLOAD];
    size_t out_len = 0u;

    /* Read root directly with 0-step witness */
    struct vos_tx_path_witness w_root;
    memset(&w_root, 0, sizeof(w_root));
    CHECK(vos_tx_path_read(&store, &root, &root, &w_root, 2u, buf, sizeof(buf), &out_len) == VOS_TX_OK,
          "read root");
    CHECK(out_len == 9u && memcmp(buf, "root-node", 9u) == 0, "root payload");

    /* Read 2-hop leaf_a */
    struct vos_tx_path_witness w_leaf_a;
    memset(&w_leaf_a, 0, sizeof(w_leaf_a));
    w_leaf_a.step_count = 2u;
    w_leaf_a.steps[0] = mid;
    w_leaf_a.steps[1] = leaf_a;
    CHECK(vos_tx_path_read(&store, &root, &leaf_a, &w_leaf_a, 2u, buf, sizeof(buf), &out_len) == VOS_TX_OK,
          "read leaf_a");
    CHECK(out_len == 10u && memcmp(buf, "leaf-alpha", 10u) == 0, "leaf_a payload");

    /* Sibling independence: remove leaf_b and verify leaf_a still reads cleanly */
    struct vos_tx_store no_sib = store;
    CHECK(vos_tx_store_remove(&no_sib, &leaf_b) == VOS_TX_OK, "remove sibling leaf_b");
    CHECK(vos_tx_dag_intact(&no_sib, &root, 2u) == VOS_TX_ERR_INCOMPLETE_DAG,
          "whole-DAG audit refuses missing sibling");
    memset(buf, 0x5Au, sizeof(buf));
    out_len = 999u;
    CHECK(vos_tx_path_read(&no_sib, &root, &leaf_a, &w_leaf_a, 2u, buf, sizeof(buf), &out_len) == VOS_TX_OK,
          "path_read succeeds with unavailable sibling");
    CHECK(out_len == 10u && memcmp(buf, "leaf-alpha", 10u) == 0, "leaf_a payload without sibling");

    /* Refusal: unauthenticated parent (tamper mid payload while keeping hash key) */
    struct vos_tx_store bad_parent = store;
    struct vos_tx_object tampered_mid = mid_obj;
    tampered_mid.payload[0] = 'X';
    CHECK(vos_tx_store_put_at(&bad_parent, &mid, &tampered_mid) == VOS_TX_OK, "tamper mid");
    memset(buf, 0xA5u, sizeof(buf));
    out_len = 77u;
    CHECK(vos_tx_path_read(&bad_parent, &root, &leaf_a, &w_leaf_a, 2u, buf, sizeof(buf), &out_len)
          == VOS_TX_ERR_HASH_MISMATCH, "refuse unauthenticated parent");
    CHECK(buf[0] == 0xA5u && out_len == 77u, "caller output preserved on parent hash failure");

    /* Refusal: target hash mismatch */
    struct vos_tx_store bad_leaf = store;
    struct vos_tx_object tampered_leaf = leaf_a_obj;
    tampered_leaf.payload[0] = 'Z';
    CHECK(vos_tx_store_put_at(&bad_leaf, &leaf_a, &tampered_leaf) == VOS_TX_OK, "tamper leaf_a");
    memset(buf, 0x3Cu, sizeof(buf));
    CHECK(vos_tx_path_read(&bad_leaf, &root, &leaf_a, &w_leaf_a, 2u, buf, sizeof(buf), &out_len)
          == VOS_TX_ERR_HASH_MISMATCH, "refuse target hash mismatch");
    CHECK(buf[0] == 0x3Cu, "caller buffer preserved on leaf hash failure");

    /* Refusal: broken child link (stray object exists and hashes validly, but not in kids) */
    struct vos_tx_path_witness w_stray;
    memset(&w_stray, 0, sizeof(w_stray));
    w_stray.step_count = 2u;
    w_stray.steps[0] = mid;
    w_stray.steps[1] = stray;
    CHECK(vos_tx_path_read(&store, &root, &stray, &w_stray, 2u, buf, sizeof(buf), &out_len)
          == VOS_TX_ERR_BAD_LINK, "refuse unlinked stray object");

    /* Refusal: wrong root */
    CHECK(vos_tx_path_read(&store, &stray, &leaf_a, &w_leaf_a, 2u, buf, sizeof(buf), &out_len)
          == VOS_TX_ERR_BAD_LINK, "refuse wrong root");
    struct vos_tx_hash missing_root = make_checkpoint(0xEEu);
    CHECK(vos_tx_path_read(&store, &missing_root, &leaf_a, &w_leaf_a, 2u, buf, sizeof(buf), &out_len)
          == VOS_TX_ERR_MISSING, "refuse missing root");

    /* Refusal: wrong final target */
    CHECK(vos_tx_path_read(&store, &root, &leaf_b, &w_leaf_a, 2u, buf, sizeof(buf), &out_len)
          == VOS_TX_ERR_TARGET_MISMATCH, "refuse wrong target at path end");

    /* Refusal: exhausted walk depth */
    CHECK(vos_tx_path_read(&store, &root, &leaf_a, &w_leaf_a, 1u, buf, sizeof(buf), &out_len)
          == VOS_TX_ERR_DEPTH, "refuse exhausted depth");

    /* Refusal: undersized output buffer */
    CHECK(vos_tx_path_read(&store, &root, &leaf_a, &w_leaf_a, 2u, buf, 4u, &out_len)
          == VOS_TX_ERR_BUFFER, "refuse undersized output buffer");

    return 0;
}

static int test_select_root(void)
{
    const struct vos_tx_policy policy = make_policy(2u);
    const struct vos_tx_hash r_v3 = make_checkpoint(0x11u);
    const struct vos_tx_hash r_v5 = make_checkpoint(0x22u);
    const struct vos_tx_hash r_v9 = make_checkpoint(0x33u);

    const struct vos_tx_signed_root low = make_signed_root(&policy, &r_v3, 3u, 2u, 3u);
    const struct vos_tx_signed_root mid = make_signed_root(&policy, &r_v5, 5u, 4u, 3u);
    struct vos_tx_signed_root torn = make_signed_root(&policy, &r_v9, 9u, 4u, 3u);
    torn.checksum[0] ^= 0xFFu;

    /* Untrusted slot pointer points to index 0 (torn) or index 1 (low), yet selector picks index 2 (mid) */
    const struct vos_tx_signed_root copies[3] = { torn, low, mid };
    struct vos_tx_signed_root selected;
    memset(&selected, 0, sizeof(selected));

    CHECK(vos_tx_select_root(&policy, copies, 3u, 0u, &selected) == VOS_TX_OK, "select ignores torn ptr 0");
    CHECK(selected.version == 5u && memcmp(selected.root.bytes, r_v5.bytes, VOS_TX_DIGEST_BYTES) == 0,
          "select picked highest verifying version 5");

    CHECK(vos_tx_select_root(&policy, copies, 3u, 1u, &selected) == VOS_TX_OK, "select ignores low ptr 1");
    CHECK(selected.version == 5u, "select with ptr=1 still picks version 5");

    CHECK(vos_tx_select_root(&policy, copies, 3u, 99u, &selected) == VOS_TX_OK, "select ignores OOB ptr");
    CHECK(selected.version == 5u, "select with OOB ptr still picks version 5");

    /* Unenrolled key refused */
    const struct vos_tx_signed_root rogue_key = make_signed_root(&policy, &r_v9, 9u, 4u, 99u);
    const struct vos_tx_signed_root bad_copies[2] = { torn, rogue_key };
    CHECK(vos_tx_select_root(&policy, bad_copies, 2u, 0u, &selected) == VOS_TX_ERR_UNVERIFIED,
          "refuse when all copies fail verification or enrolled key");

    /* Fewer than 2 copies refused (R-10-001a) */
    CHECK(vos_tx_select_root(&policy, &mid, 1u, 0u, &selected) == VOS_TX_ERR_INVALID,
          "refuse single-copy slot");

    return 0;
}

static int test_transactor_ab_and_health(void)
{
    const struct vos_tx_policy policy = make_policy(2u);
    struct vos_tx_store store;
    vos_tx_store_init(&store);

    /* Build base image (depth 1) and next image (depth 2) */
    const struct vos_tx_object base_leaf_obj = make_obj("base-leaf", NULL, 0u);
    const struct vos_tx_object next_leaf_obj = make_obj("next-leaf", NULL, 0u);
    struct vos_tx_hash base_leaf;
    struct vos_tx_hash next_leaf;
    CHECK(vos_tx_store_put(&store, &base_leaf_obj, &base_leaf) == VOS_TX_OK, "put base_leaf");
    CHECK(vos_tx_store_put(&store, &next_leaf_obj, &next_leaf) == VOS_TX_OK, "put next_leaf");

    const struct vos_tx_object base_root_obj = make_obj("base-root", &base_leaf, 1u);
    struct vos_tx_hash base_root_hash;
    CHECK(vos_tx_store_put(&store, &base_root_obj, &base_root_hash) == VOS_TX_OK, "put base_root");

    const struct vos_tx_object next_mid_obj = make_obj("next-mid", &next_leaf, 1u);
    struct vos_tx_hash next_mid_hash;
    CHECK(vos_tx_store_put(&store, &next_mid_obj, &next_mid_hash) == VOS_TX_OK, "put next_mid");

    const struct vos_tx_object next_root_obj = make_obj("next-root", &next_mid_hash, 1u);
    struct vos_tx_hash next_root_hash;
    CHECK(vos_tx_store_put(&store, &next_root_obj, &next_root_hash) == VOS_TX_OK, "put next_root");

    /* Deep image of depth 3 (exceeds policy.walk_depth == 2) for truncated-walk control */
    const struct vos_tx_object deep_root_obj = make_obj("deep-root", &next_root_hash, 1u);
    struct vos_tx_hash deep_root_hash;
    CHECK(vos_tx_store_put(&store, &deep_root_obj, &deep_root_hash) == VOS_TX_OK, "put deep_root");

    const struct vos_tx_signed_root base_sr = make_signed_root(&policy, &base_root_hash, 5u, 4u, 3u);
    const struct vos_tx_signed_root stale_sr = make_signed_root(&policy, &base_root_hash, 2u, 1u, 3u);
    const struct vos_tx_signed_root next_sr = make_signed_root(&policy, &next_root_hash, 6u, 5u, 3u);
    const struct vos_tx_signed_root deep_sr = make_signed_root(&policy, &deep_root_hash, 7u, 5u, 3u);
    const struct vos_tx_signed_root low_decl_sr = make_signed_root(&policy, &next_root_hash, 6u, 2u, 3u);
    const struct vos_tx_signed_root over_decl_sr = make_signed_root(&policy, &next_root_hash, 6u, 9u, 3u);
    struct vos_tx_signed_root bad_key_sr = next_sr;
    bad_key_sr.key_id = 77u;

    const struct vos_tx_hash cp0 = make_checkpoint(0x70u);
    const struct vos_tx_hash cp1 = make_checkpoint(0x71u);

    struct vos_tx_ab ab;
    vos_tx_ab_init(&ab, &base_sr, &stale_sr, 4u, &cp0);
    CHECK(vos_tx_ab_live(&ab)->version == 5u, "initial live is base");

    /* Verify-and-flip refuses when nothing is staged */
    struct vos_tx_witness_evidence ev;
    memset(&ev, 0, sizeof(ev));
    ev.offered_checkpoint = cp1;
    ev.checkpoint_accepted = 1u;
    ev.checkpoint_consistent = 1u;
    ev.base_included = 1u;
    ev.proof_admitted = 1u;
    ev.verdict_root = next_root_hash;
    CHECK(vos_tx_verify_and_flip(&policy, &store, &ab, 4u, &ev) == VOS_TX_ERR_NOT_STAGED,
          "flip refuses unstaged state");

    /* Stage next_sr: running generation remains immutable, spare gets candidate */
    CHECK(vos_tx_stage(&ab, &next_sr) == VOS_TX_OK, "stage next_sr");
    CHECK(vos_tx_ab_live(&ab)->version == 5u &&
          memcmp(vos_tx_ab_live(&ab)->root.bytes, base_root_hash.bytes, VOS_TX_DIGEST_BYTES) == 0,
          "stage preserves running generation");
    CHECK(vos_tx_ab_spare(&ab)->version == 6u, "stage writes inactive slot");
    CHECK(ab.floor_version == 4u && ab.has_retained == 0u, "stage clears retained and preserves floor");

    /* Refusal: unenrolled root key (R-09-036a) */
    struct vos_tx_ab ab_bad = ab;
    CHECK(vos_tx_stage(&ab_bad, &bad_key_sr) == VOS_TX_OK, "stage bad_key");
    CHECK(vos_tx_verify_and_flip(&policy, &store, &ab_bad, 4u, &ev) == VOS_TX_ERR_UNVERIFIED,
          "refuse unenrolled root key");
    CHECK(vos_tx_ab_live(&ab_bad)->version == 5u, "live unchanged on key refusal");

    /* Refusal: candidate below RoT floor (4 vs version 2) or declared floor (9 vs version 6) */
    ab_bad = ab;
    CHECK(vos_tx_stage(&ab_bad, &stale_sr) == VOS_TX_OK, "stage stale_sr");
    ev.verdict_root = stale_sr.root;
    CHECK(vos_tx_verify_and_flip(&policy, &store, &ab_bad, 4u, &ev) == VOS_TX_ERR_ROLLBACK_FLOOR,
          "refuse candidate below floor");
    ab_bad = ab;
    CHECK(vos_tx_stage(&ab_bad, &over_decl_sr) == VOS_TX_OK, "stage over_decl_sr");
    ev.verdict_root = over_decl_sr.root;
    CHECK(vos_tx_verify_and_flip(&policy, &store, &ab_bad, 4u, &ev) == VOS_TX_ERR_ROLLBACK_FLOOR,
          "refuse candidate below its own declared floor");

    /* Refusal: proof admission missing or bound to wrong root */
    ev.verdict_root = base_root_hash;
    CHECK(vos_tx_verify_and_flip(&policy, &store, &ab, 4u, &ev) == VOS_TX_ERR_NOT_ADMITTED,
          "refuse mismatched verdict_root");
    ev.verdict_root = next_root_hash;
    ev.proof_admitted = 0u;
    CHECK(vos_tx_verify_and_flip(&policy, &store, &ab, 4u, &ev) == VOS_TX_ERR_NOT_ADMITTED,
          "refuse proof_admitted == 0");
    ev.proof_admitted = 1u;

    /* Refusal: witness pin guards */
    ev.checkpoint_consistent = 0u;
    CHECK(vos_tx_verify_and_flip(&policy, &store, &ab, 4u, &ev) == VOS_TX_ERR_WITNESS_PIN,
          "refuse inconsistent checkpoint");
    CHECK(memcmp(ab.pinned_checkpoint.bytes, cp0.bytes, VOS_TX_DIGEST_BYTES) == 0,
          "pinned checkpoint unchanged on refusal");
    ev.checkpoint_consistent = 1u;
    ev.checkpoint_accepted = 0u;
    CHECK(vos_tx_verify_and_flip(&policy, &store, &ab, 4u, &ev) == VOS_TX_ERR_WITNESS_PIN,
          "refuse unaccepted checkpoint");
    ev.checkpoint_accepted = 1u;
    ev.base_included = 0u;
    CHECK(vos_tx_verify_and_flip(&policy, &store, &ab, 4u, &ev) == VOS_TX_ERR_WITNESS_PIN,
          "refuse unincluded base root");
    ev.base_included = 1u;

    /* Refusal: truncated DAG walk (deep_sr exceeds walk_depth 2) */
    ab_bad = ab;
    CHECK(vos_tx_stage(&ab_bad, &deep_sr) == VOS_TX_OK, "stage deep_sr");
    ev.verdict_root = deep_root_hash;
    CHECK(vos_tx_verify_and_flip(&policy, &store, &ab_bad, 4u, &ev) == VOS_TX_ERR_INCOMPLETE_DAG,
          "refuse truncated walk exceeding walk_depth");

    /* Refusal: incomplete store (missing descendant) */
    struct vos_tx_store incomplete_store = store;
    CHECK(vos_tx_store_remove(&incomplete_store, &next_leaf) == VOS_TX_OK, "remove next_leaf");
    ev.verdict_root = next_root_hash;
    CHECK(vos_tx_verify_and_flip(&policy, &incomplete_store, &ab, 4u, &ev) == VOS_TX_ERR_INCOMPLETE_DAG,
          "refuse incomplete DAG");

    /* Successful verify_and_flip: also test with low_decl_sr (declares floor 2 < 4) to verify floor is NOT lowered or raised */
    ab_bad = ab;
    CHECK(vos_tx_stage(&ab_bad, &low_decl_sr) == VOS_TX_OK, "stage low_decl_sr");
    CHECK(vos_tx_verify_and_flip(&policy, &store, &ab_bad, 4u, &ev) == VOS_TX_OK,
          "flip low_decl_sr succeeds");
    CHECK(ab_bad.floor_version == 4u, "flip must NOT lower floor to declared_floor 2");

    /* Real flip with next_sr (declared_floor 5 > 4): floor MUST stay 4 (transactor never writes/reseals floor) */
    CHECK(vos_tx_verify_and_flip(&policy, &store, &ab, 4u, &ev) == VOS_TX_OK, "flip next_sr");
    CHECK(vos_tx_ab_live(&ab)->version == 6u, "live is now next_sr v6");
    CHECK(ab.floor_version == 4u, "transactor must NOT raise/reseal floor to 5");
    CHECK(ab.has_retained == 1u && ab.retained_predecessor.version == 5u,
          "retained predecessor recorded on flip");
    CHECK(memcmp(ab.pinned_checkpoint.bytes, cp1.bytes, VOS_TX_DIGEST_BYTES) == 0,
          "pinned checkpoint updated on flip");

    /* Health check: healthy settles */
    struct vos_tx_ab ab_healthy = ab;
    CHECK(vos_tx_health_check(&policy, &store, &ab_healthy, 4u, 1u, 1u) == VOS_TX_OK,
          "healthy generation settles");
    CHECK(vos_tx_ab_live(&ab_healthy)->version == 6u, "healthy keeps live generation");

    /* Health check: unhealthy falls back to retained predecessor v5 when rot_floor == 4 */
    struct vos_tx_ab ab_fb = ab;
    CHECK(vos_tx_health_check(&policy, &store, &ab_fb, 4u, 0u, 1u) == VOS_TX_OK,
          "unhealthy falls back to retained predecessor v5");
    CHECK(vos_tx_ab_live(&ab_fb)->version == 5u && ab_fb.floor_version == 4u,
          "fallback restored base v5 without writing floor");

    /* Refusal: fallback refused when RoT floor advanced above retained predecessor (rot_floor == 6 > v5) */
    ab_fb = ab;
    CHECK(vos_tx_health_check(&policy, &store, &ab_fb, 6u, 0u, 1u) == VOS_TX_ERR_ROLLBACK_FLOOR,
          "refuse fallback below RoT floor");
    CHECK(vos_tx_ab_live(&ab_fb)->version == 6u, "live unchanged on floor-refused fallback");

    /* Refusal: restaging invalidates predecessor and refuses health fallback */
    ab_fb = ab;
    CHECK(vos_tx_stage(&ab_fb, &next_sr) == VOS_TX_OK, "restage invalidates predecessor");
    CHECK(vos_tx_health_check(&policy, &store, &ab_fb, 4u, 0u, 1u) == VOS_TX_ERR_RESTAGED,
          "refuse fallback after restaging");
    CHECK(vos_tx_ab_live(&ab_fb)->version == 6u, "restaged fallback keeps live unchanged");

    /* Refusal: tampered spare copy mismatches signature/retained predecessor */
    ab_fb = ab;
    if (ab_fb.b_live != 0u) {
        ab_fb.slot_a.checksum[0] ^= 1u;
    } else {
        ab_fb.slot_b.checksum[0] ^= 1u;
    }
    CHECK(vos_tx_health_check(&policy, &store, &ab_fb, 4u, 0u, 1u) == VOS_TX_ERR_PREDECESSOR_MISMATCH,
          "refuse tampered retained spare");

    /* Refusal: unauthenticated predecessor matching retained record */
    ab_fb = ab;
    if (ab_fb.b_live != 0u) {
        ab_fb.slot_a.checksum[0] ^= 1u;
        ab_fb.retained_predecessor = ab_fb.slot_a;
    } else {
        ab_fb.slot_b.checksum[0] ^= 1u;
        ab_fb.retained_predecessor = ab_fb.slot_b;
    }
    CHECK(vos_tx_health_check(&policy, &store, &ab_fb, 4u, 0u, 1u) == VOS_TX_ERR_UNVERIFIED,
          "refuse unverified predecessor even if retained record matches");

    return 0;
}

int main(void)
{
    if (test_path_read() != 0) {
        return 1;
    }
    if (test_select_root() != 0) {
        return 1;
    }
    if (test_transactor_ab_and_health() != 0) {
        return 1;
    }
    printf("transactor_test: ok\n");
    return 0;
}
