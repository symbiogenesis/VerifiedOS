// SPDX-License-Identifier: Apache-2.0
#include "vos_resident_reads.h"
#include "vos_resident_scalar.h"
#include "vos_storage_publish.h"

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#define FAIL(msg) do { \
    fprintf(stderr, "resident correspondence error at %d: %s\n", __LINE__, (msg)); \
    return 0; \
} while (0)

enum {
    CORR_DOMAIN = 7u,
    CORR_OWNER = 1u,
    CORR_OBJECT = 1u,
    CORR_PAYLOAD_LEN = 16u,
    CORR_BYTE_BOUND = 32u,
    CORR_READ_BOUND = 16u,
    CORR_RETENTION_BOUND = 4u,
    CORR_COUNTER_BOUND = 30u,
    CORR_MAX_CELLS = 128u
};

struct write_log {
    const struct vos_resident_owner *owner;
    uint32_t common_writes;
    uint32_t private_writes;
    uint32_t response_writes;
    uint32_t misclassified;
    uint32_t cell_count;
    uint32_t cell_kind[CORR_MAX_CELLS];
    int32_t cell_holder[CORR_MAX_CELLS];
    const char *cell_name[CORR_MAX_CELLS];
};

static int in_range(const void *ptr, size_t len, const void *base, size_t total)
{
    const uintptr_t p = (uintptr_t)ptr;
    const uintptr_t b = (uintptr_t)base;
    return len > 0u && p >= b && p <= b + total && (p - b) + len <= total;
}

static void reset_log(struct write_log *log, const struct vos_resident_owner *owner)
{
    memset(log, 0, sizeof(*log));
    log->owner = owner;
}

static void observe_write(void *opaque, uint32_t classification,
                          const void *address, size_t bytes)
{
    struct write_log *log = (struct write_log *)opaque;
    if (log == NULL || log->owner == NULL || bytes == 0u) {
        return;
    }
    const struct vos_resident_owner *o = log->owner;
    int actual_kind = 0;
    int32_t holder = -1;
    const char *name = "ResponsePublication";

    if (in_range(address, bytes, &o->common, sizeof(o->common))) {
        actual_kind = (int)VOS_RESIDENT_COMMON;
        name = "CommonBacking";
        for (uint32_t h = 0u; h < VOS_RESIDENT_HOLDERS; ++h) {
            if (in_range(address, bytes, &o->common.reservation[h],
                         sizeof(o->common.reservation[h]))) {
                name = "CommonReservation";
                holder = (int32_t)h;
                break;
            }
        }
        if (in_range(address, bytes, &o->common.next_token,
                     sizeof(o->common.next_token))) {
            name = "CommonCounter";
        }
    } else if (in_range(address, bytes, o, sizeof(*o))) {
        actual_kind = (int)VOS_RESIDENT_PRIVATE;
        for (uint32_t h = 0u; h < VOS_RESIDENT_HOLDERS; ++h) {
            if (in_range(address, bytes, &o->sequence[h], sizeof(o->sequence[h]))) {
                name = "PrivateSequence";
                holder = (int32_t)h;
                break;
            }
            if (in_range(address, bytes, &o->pending[h], sizeof(o->pending[h]))) {
                name = "PrivatePending";
                holder = (int32_t)h;
                break;
            }
        }
    } else {
        actual_kind = (int)VOS_RESIDENT_RESPONSE;
    }

    if ((uint32_t)actual_kind != classification) {
        log->misclassified = 1u;
    }
    if (classification == VOS_RESIDENT_COMMON) {
        ++log->common_writes;
    } else if (classification == VOS_RESIDENT_PRIVATE) {
        ++log->private_writes;
    } else if (classification == VOS_RESIDENT_RESPONSE) {
        ++log->response_writes;
    } else {
        log->misclassified = 1u;
    }
    if (log->cell_count < CORR_MAX_CELLS) {
        log->cell_kind[log->cell_count] = classification;
        log->cell_holder[log->cell_count] = holder;
        log->cell_name[log->cell_count] = name;
        ++log->cell_count;
    }
}

static void print_bytes_json(const uint8_t *bytes, size_t len)
{
    putchar('[');
    for (size_t i = 0u; i < len; ++i) {
        if (i != 0u) {
            putchar(',');
        }
        printf("%u", (unsigned)bytes[i]);
    }
    putchar(']');
}

static void print_identity_json(const struct vos_resident_identity *id)
{
    printf("{\"owner\":%" PRIu64 ",\"domain\":%" PRIu64
           ",\"object_id\":%" PRIu64 ",\"version\":%" PRIu64
           ",\"root_kind\":\"%s\",\"generation\":%" PRIu64 ",\"root_digest\":",
           id->owner, id->domain, id->object, id->version,
           id->kind == VOS_RESIDENT_SYSTEM ? "SystemImage" : "UserData",
           id->generation);
    print_bytes_json(id->root, sizeof(id->root));
    putchar('}');
}

static void print_handle_json(const struct vos_resident_handle *h)
{
    printf("{\"token\":%" PRIu64 ",\"boot_epoch\":%" PRIu64
           ",\"holder\":%u,\"handle_identity\":",
           h->token, h->boot, h->holder);
    print_identity_json(&h->identity);
    printf(",\"window_start\":%zu,\"window_length\":%zu}", h->start, h->length);
}

static void print_backing_json(const struct vos_resident_backing *b)
{
    if (!b->occupied) {
        printf("null");
        return;
    }
    printf("{\"resident_identity\":");
    print_identity_json(&b->identity);
    printf(",\"resident_bytes\":");
    print_bytes_json(b->bytes, b->length);
    printf(",\"accepting\":%s}", b->accepting ? "true" : "false");
}

static void print_owner_state_json(const struct vos_resident_owner *o,
                                   uint64_t logical_clock,
                                   int two_slot)
{
    printf("{\"boot\":%" PRIu64 ",\"generation\":%" PRIu64
           ",\"next_token\":%" PRIu64 ",\"clock\":%" PRIu64
           ",\"grants\":%u,\"current\":%u,",
           o->common.boot, o->common.generation, o->common.next_token,
           logical_clock, o->common.grants, o->common.current);
    if (two_slot) {
        const uint32_t cur = o->common.current;
        const uint32_t pred = 1u - cur;
        printf("\"current_backing\":");
        print_backing_json(&o->common.backing[cur]);
        printf(",\"predecessor_backing\":");
        print_backing_json(&o->common.backing[pred]);
    } else {
        printf("\"backing\":");
        print_backing_json(&o->common.backing[o->common.current]);
    }
    printf(",\"reservations\":[");
    for (uint32_t h = 0u; h < VOS_RESIDENT_HOLDERS; ++h) {
        const struct vos_resident_reservation *r = &o->common.reservation[h];
        if (h != 0u) {
            putchar(',');
        }
        if (!r->live) {
            printf("null");
        } else {
            printf("{\"reserved_handle\":");
            print_handle_json(&r->handle);
            printf(",\"expires\":%" PRIu64 ",\"renewed\":%u,\"backing\":%u}",
                   r->expires, r->renewed, r->backing);
        }
    }
    printf("],\"sessions\":[");
    for (uint32_t h = 0u; h < VOS_RESIDENT_HOLDERS; ++h) {
        const struct vos_resident_request *q = &o->pending[h];
        if (h != 0u) {
            putchar(',');
        }
        printf("{\"sequence\":%" PRIu64 ",\"pending\":", o->sequence[h]);
        if (!q->active) {
            printf("null");
        } else {
            printf("{\"sequence\":%" PRIu64 ",\"token\":%" PRIu64
                   ",\"offset\":%zu,\"length\":%zu}",
                   q->sequence, q->token, q->offset, q->length);
        }
        putchar('}');
    }
    printf("]}");
}

static void print_step_json(int first,
                            const char *op,
                            int ok,
                            const struct write_log *log,
                            const uint8_t *payload_out,
                            size_t payload_len,
                            int has_payload,
                            const struct vos_resident_handle *handle_out,
                            const struct vos_resident_owner *owner,
                            uint64_t logical_clock,
                            int two_slot)
{
    if (!first) {
        putchar(',');
    }
    printf("{\"op\":\"%s\",\"ok\":%s,\"common_writes\":%u,\"private_writes\":%u,"
           "\"response_writes\":%u,\"cells\":[",
           op, ok ? "true" : "false",
           log->common_writes, log->private_writes, log->response_writes);
    for (uint32_t i = 0u; i < log->cell_count; ++i) {
        if (i != 0u) {
            putchar(',');
        }
        printf("{\"kind\":%u,\"name\":\"%s\",\"holder\":%d}",
               log->cell_kind[i], log->cell_name[i], log->cell_holder[i]);
    }
    printf("],\"payload_out\":");
    if (has_payload) {
        print_bytes_json(payload_out, payload_len);
    } else {
        printf("null");
    }
    printf(",\"handle_out\":");
    if (handle_out != NULL) {
        print_handle_json(handle_out);
    } else {
        printf("null");
    }
    printf(",\"state\":");
    print_owner_state_json(owner, logical_clock, two_slot);
    putchar('}');
}

struct storage_env {
    struct vos_crypto_core crypto;
    struct vos_storage_medium medium;
    struct vos_storage_store store;
    uint32_t slot;
};

static int init_storage_env(struct storage_env *env, uint32_t kind)
{
    const struct vos_node_geometry geometry = {
        .fan = 4u, .block_bytes = 128u, .arena_nodes = 32u
    };
    const struct vos_tree_limits limits = {
        .height = 0u, .depth_limit = 6u, .visit_limit = 64u
    };
    uint8_t master_key[32];
    for (size_t i = 0u; i < sizeof(master_key); ++i) {
        master_key[i] = (uint8_t)(0x31u + i + kind);
    }
    memset(env, 0, sizeof(*env));
    env->slot = (kind == VOS_RESIDENT_SYSTEM)
                    ? VOS_CRYPTO_DOMAIN_SYSTEM
                    : VOS_CRYPTO_DOMAIN_USER;
    vos_crypto_core_init(&env->crypto, 32u);
    if (!vos_crypto_core_unlock_domain(&env->crypto, env->slot, CORR_DOMAIN, 1u,
                                       master_key, sizeof(master_key)) ||
        !vos_storage_format(&env->medium, &env->store, &env->crypto, env->slot,
                            CORR_DOMAIN, 1u, &geometry, &limits, 1u, 64u)) {
        return 0;
    }
    return 1;
}

static int commit_resident_object(struct storage_env *env,
                                  uint32_t kind,
                                  uint64_t version,
                                  const uint8_t *payload,
                                  size_t len,
                                  struct vos_resident_identity *id_out)
{
    struct vos_storage_store planning = env->store;
    ++planning.committed_generation;
    uint64_t tree_val = 0u;
    if (!vos_storage_bind_resident_identity(&planning, CORR_OWNER, CORR_OBJECT,
                                            version, kind, payload, len,
                                            &tree_val, id_out)) {
        return 0;
    }
    const struct vos_storage_tx_spec tx = {
        .op_kind = VOS_STORAGE_OP_INSERT,
        .commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE,
        .key = CORR_OBJECT,
        .value = tree_val
    };
    uint64_t ack = 0u;
    if (!vos_storage_reserve(&env->store, CORR_DOMAIN, &tx) ||
        !vos_storage_stage(&env->store, CORR_DOMAIN) ||
        !vos_storage_publish(&env->store, CORR_DOMAIN, VOS_STORAGE_CUT_NONE, &ack) ||
        ack != id_out->generation) {
        return 0;
    }
    return 1;
}

static int run_single_slot_campaign(uint32_t kind, int first_campaign)
{
    struct storage_env env;
    if (!init_storage_env(&env, kind)) {
        FAIL("single-slot storage setup");
    }
    uint8_t payload[CORR_PAYLOAD_LEN];
    for (size_t i = 0u; i < sizeof(payload); ++i) {
        payload[i] = (uint8_t)(0x41u + i + (kind == VOS_RESIDENT_SYSTEM ? 16u : 0u));
    }
    struct vos_resident_identity id = {0};
    if (!commit_resident_object(&env, kind, 1u, payload, sizeof(payload), &id)) {
        FAIL("single-slot storage commit");
    }

    struct vos_resident_owner owner = {0};
    struct write_log log = {0};
    reset_log(&log, &owner);
    if (!vos_resident_init(&owner, 0u, id.generation, CORR_COUNTER_BOUND,
                           observe_write, &log)) {
        FAIL("resident init");
    }

    if (!first_campaign) {
        putchar(',');
    }
    printf("{\"kind\":\"%s\",\"domain\":%u,\"owner_id\":%u,\"object_id\":%u,"
           "\"initial_generation\":%" PRIu64 ",\"identity\":",
           kind == VOS_RESIDENT_SYSTEM ? "SystemImage" : "UserData",
           CORR_DOMAIN, CORR_OWNER, CORR_OBJECT, id.generation);
    print_identity_json(&id);
    printf(",\"payload\":");
    print_bytes_json(payload, sizeof(payload));
    printf(",\"steps\":[");

    int first_step = 1;
    uint64_t clock = 0u;

    reset_log(&log, &owner);
    if (!vos_resident_publish(&owner, &id, payload, sizeof(payload)) ||
        log.misclassified) {
        FAIL("observer classification mismatch");
    }
    print_step_json(first_step, "publish", 1, &log, NULL, 0u, 0, NULL, &owner, clock, 0);
    first_step = 0;

    /* Admit two independent holders. */
    struct vos_resident_handle h0 = {0}, h1 = {0};
    reset_log(&log, &owner);
    if (!vos_resident_admit(&owner, 0u, CORR_DOMAIN, &id, 0u, 16u,
                            clock, clock + CORR_RETENTION_BOUND, &h0) ||
        log.misclassified) {
        FAIL("admit holder 0");
    }
    print_step_json(first_step, "admit_h0", 1, &log, NULL, 0u, 0, &h0, &owner, clock, 0);

    reset_log(&log, &owner);
    if (!vos_resident_admit(&owner, 1u, CORR_DOMAIN, &id, 4u, 12u,
                            clock, clock + CORR_RETENTION_BOUND, &h1) ||
        log.misclassified) {
        FAIL("admit holder 1");
    }
    print_step_json(0, "admit_h1", 1, &log, NULL, 0u, 0, &h1, &owner, clock, 0);

    /* Two-holder repeated reads with zero common writes. */
    for (uint32_t round = 0u; round < 3u; ++round) {
        for (uint32_t holder = 0u; holder < 2u; ++holder) {
            const struct vos_resident_handle *hh = (holder == 0u) ? &h0 : &h1;
            const size_t expected_len = (holder == 0u) ? 16u : 12u;
            const size_t expected_off = (holder == 0u) ? 0u : 4u;
            uint64_t seq = 0u;
            uint8_t out[16] = {0};
            size_t out_len = 0u;
            reset_log(&log, &owner);
            const int beg_ok = vos_resident_begin(&owner, hh, CORR_DOMAIN, 0u,
                                                  expected_len, clock, &seq);
            const int cmp_ok = beg_ok && vos_resident_complete(
                &owner, hh, CORR_DOMAIN, seq, clock,
                vos_storage_verify_resident, &env.store,
                out, sizeof(out), &out_len);
            if (log.misclassified) {
                FAIL("observer classification mismatch");
            }
            if (log.common_writes != 0u) {
                FAIL("common write during read traffic");
            }
            if (!cmp_ok || out_len != expected_len ||
                memcmp(out, payload + expected_off, expected_len) != 0 ||
                owner.common.next_token != 2u) {
                FAIL("repeated read payload or token mismatch");
            }
            print_step_json(0, holder == 0u ? "read_h0" : "read_h1",
                            1, &log, out, out_len, 1, NULL, &owner, clock, 0);
        }
    }

    /* Advance clock to 3, begin holder 0 read, renew holder 0 to 3 + 4 = 7. */
    clock = 3u;
    uint64_t seq0 = 0u;
    reset_log(&log, &owner);
    if (!vos_resident_begin(&owner, &h0, CORR_DOMAIN, 2u, 8u, clock, &seq0) ||
        log.misclassified || log.common_writes != 0u) {
        FAIL("common write during read traffic");
    }
    print_step_json(0, "begin_h0_at3", 1, &log, NULL, 0u, 0, NULL, &owner, clock, 0);

    reset_log(&log, &owner);
    const int renew_ok = vos_resident_renew(&owner, &h0, CORR_DOMAIN,
                                            clock, clock + CORR_RETENTION_BOUND);
    if (log.misclassified) {
        FAIL("observer classification mismatch");
    }
    if (!renew_ok) {
        FAIL("renew holder 0 failed");
    }
    print_step_json(0, "renew_h0_at3", 1, &log, NULL, 0u, 0, NULL, &owner, clock, 0);

    /* Second renewal within same reservation must refuse even for a larger expiry. */
    if (vos_resident_renew(&owner, &h0, CORR_DOMAIN, clock,
                           clock + CORR_RETENTION_BOUND + 1u)) {
        FAIL("double renewal succeeded");
    }

    /* Advance clock to 5 (past original expiry 4): renewed h0 completes, unrenewed h1 refuses. */
    clock = 5u;
    uint8_t out_buf[16] = {0};
    size_t out_len = 0u;
    reset_log(&log, &owner);
    const int comp0_ok = vos_resident_complete(
        &owner, &h0, CORR_DOMAIN, seq0, clock,
        vos_storage_verify_resident, &env.store,
        out_buf, sizeof(out_buf), &out_len);
    if (log.misclassified || log.common_writes != 0u) {
        FAIL("common write during read traffic");
    }
    if (!comp0_ok || out_len != 8u || memcmp(out_buf, payload + 2u, 8u) != 0) {
        FAIL("renewed handle failed past original expiry");
    }
    print_step_json(0, "complete_h0_at5", 1, &log, out_buf, out_len, 1, NULL, &owner, clock, 0);

    uint64_t seq1_exp = 0u;
    reset_log(&log, &owner);
    const int h1_exp_ok = vos_resident_begin(&owner, &h1, CORR_DOMAIN, 0u, 4u, clock, &seq1_exp);
    if (h1_exp_ok || log.common_writes != 0u) {
        FAIL("expired unrenewed handle succeeded");
    }
    print_step_json(0, "begin_h1_expired_at5", 0, &log, NULL, 0u, 0, NULL, &owner, clock, 0);

    /* Close holder 0, verify stale refusal, readmit holder 0 with fresh token. */
    const struct vos_resident_handle old_h0 = h0;
    reset_log(&log, &owner);
    if (!vos_resident_close(&owner, &old_h0, CORR_DOMAIN) || log.misclassified) {
        FAIL("close failed to cancel or disturbed peer");
    }
    print_step_json(0, "close_h0", 1, &log, NULL, 0u, 0, NULL, &owner, clock, 0);

    if (vos_resident_close(&owner, &old_h0, CORR_DOMAIN)) {
        FAIL("stale handle accepted after close/readmit");
    }

    reset_log(&log, &owner);
    if (!vos_resident_admit(&owner, 0u, CORR_DOMAIN, &id, 0u, 16u,
                            clock, clock + CORR_RETENTION_BOUND, &h0) ||
        h0.token <= old_h0.token || log.misclassified) {
        FAIL("readmit holder 0 failed");
    }
    print_step_json(0, "readmit_h0", 1, &log, NULL, 0u, 0, &h0, &owner, clock, 0);

    if (vos_resident_close(&owner, &old_h0, CORR_DOMAIN) ||
        vos_resident_renew(&owner, &old_h0, CORR_DOMAIN, clock, clock + CORR_RETENTION_BOUND)) {
        FAIL("stale handle accepted after close/readmit");
    }

    reset_log(&log, &owner);
    uint64_t seq_new = 0u;
    if (!vos_resident_begin(&owner, &h0, CORR_DOMAIN, 0u, 16u, clock, &seq_new) ||
        !vos_resident_complete(&owner, &h0, CORR_DOMAIN, seq_new, clock,
                               vos_storage_verify_resident, &env.store,
                               out_buf, sizeof(out_buf), &out_len) ||
        out_len != 16u || memcmp(out_buf, payload, 16u) != 0 ||
        log.common_writes != 0u) {
        FAIL("readmitted handle read failed");
    }
    print_step_json(0, "read_readmitted_h0", 1, &log, out_buf, out_len, 1, NULL, &owner, clock, 0);

    /* Begin an in-flight read, then crash + reopen storage. */
    uint64_t seq_crash = 0u;
    reset_log(&log, &owner);
    if (!vos_resident_begin(&owner, &h0, CORR_DOMAIN, 0u, 8u, clock, &seq_crash)) {
        FAIL("begin before crash");
    }
    print_step_json(0, "begin_before_crash", 1, &log, NULL, 0u, 0, NULL, &owner, clock, 0);

    const uint64_t seq0_before = owner.sequence[0];
    const uint64_t seq1_before = owner.sequence[1];
    reset_log(&log, &owner);
    if (!vos_resident_crash(&owner, 1u) ||
        !vos_storage_reopen(&env.medium, &env.store, &env.crypto, env.slot, CORR_DOMAIN) ||
        owner.common.boot != 1u ||
        owner.common.backing[0].accepting != 0u ||
        owner.common.reservation[0].live != 0u ||
        owner.common.reservation[1].live != 0u ||
        owner.pending[0].active != 0u ||
        owner.pending[1].active != 0u ||
        owner.sequence[0] != seq0_before ||
        owner.sequence[1] != seq1_before) {
        FAIL("crash failed to close backing or preserve sequences");
    }
    if (vos_resident_complete(&owner, &h0, CORR_DOMAIN, seq_crash, clock,
                              vos_storage_verify_resident, &env.store,
                              out_buf, sizeof(out_buf), &out_len) ||
        vos_resident_admit(&owner, 0u, CORR_DOMAIN, &id, 0u, 16u,
                           clock, clock + CORR_RETENTION_BOUND, &h0)) {
        FAIL("crash failed to close backing or preserve sequences");
    }
    print_step_json(0, "crash", 1, &log, NULL, 0u, 0, NULL, &owner, clock, 0);

    printf("]}");
    return 1;
}

static int run_two_slot_campaign(uint32_t kind, int first_campaign)
{
    struct storage_env env;
    if (!init_storage_env(&env, kind)) {
        FAIL("two-slot storage setup");
    }
    uint8_t p1[CORR_PAYLOAD_LEN], p2[CORR_PAYLOAD_LEN], p3[CORR_PAYLOAD_LEN];
    for (size_t i = 0u; i < CORR_PAYLOAD_LEN; ++i) {
        p1[i] = (uint8_t)(0x60u + i);
        p2[i] = (uint8_t)(0x80u + i);
        p3[i] = (uint8_t)(0xa0u + i);
    }

    struct vos_resident_identity id1 = {0}, id2 = {0}, id3 = {0};
    if (!commit_resident_object(&env, kind, 1u, p1, sizeof(p1), &id1)) {
        FAIL("two-slot v1 commit");
    }
    struct vos_storage_resident_receipt receipt1 = {0};
    if (kind == VOS_RESIDENT_USER) {
        if (!vos_storage_retain_snapshot(&env.store, CORR_DOMAIN, id1.generation) ||
            !vos_storage_admit_resident(&env.store, &id1, p1, sizeof(p1), &receipt1)) {
            FAIL("two-slot v1 snapshot/receipt");
        }
    }

    /* Precompute v2 and v3 storage commits later at their exact steps. */
    struct vos_resident_owner owner = {0};
    struct write_log log = {0};
    reset_log(&log, &owner);
    if (!vos_resident_init(&owner, 0u, id1.generation, CORR_COUNTER_BOUND,
                           observe_write, &log)) {
        FAIL("two-slot resident init");
    }

    if (!first_campaign) {
        putchar(',');
    }
    printf("{\"kind\":\"%s\",\"domain\":%u,\"initial_generation\":%" PRIu64 ","
           "\"p1\":", kind == VOS_RESIDENT_SYSTEM ? "SystemImage" : "UserData",
           CORR_DOMAIN, id1.generation);
    print_bytes_json(p1, sizeof(p1));
    printf(",\"p2\":");
    print_bytes_json(p2, sizeof(p2));
    printf(",\"p3\":");
    print_bytes_json(p3, sizeof(p3));
    printf(",\"id1\":");
    print_identity_json(&id1);

    uint64_t clock = 0u;
    struct vos_resident_handle h0 = {0}, h1 = {0};
    uint64_t seq0 = 0u, seq1 = 0u;
    uint8_t out_buf[16] = {0};
    size_t out_len = 0u;

    /* Step 0: publish_initial */
    reset_log(&log, &owner);
    if (!vos_resident_publish(&owner, &id1, p1, sizeof(p1)) || log.misclassified) {
        FAIL("two-slot publish_initial");
    }

    /* Commit v2 in storage now so id2 is known for JSON header, before replace step. */
    if (!commit_resident_object(&env, kind, 2u, p2, sizeof(p2), &id2)) {
        FAIL("two-slot v2 commit");
    }
    /* Prepare id3 identity/commit preview? Wait: if we commit v3 into env.store now,
     * SystemImage v2 check would see gen 4 instead of gen 3! So commit v3 only when
     * step 10 runs, and print steps array first or pre-bind id3?
     * Even simpler: print id1, id2, and id3 in a separate metadata field or embed
     * id1/id2/id3 inside each step's handle_out / backing state! Yes! Every backing
     * in each step's state already contains its full Identity! */
    printf(",\"id2\":");
    print_identity_json(&id2);
    printf(",\"steps\":[");

    print_step_json(1, "publish_initial", 1, &log, NULL, 0u, 0, NULL, &owner, clock, 1);

    /* Step 1: admit h0 on v1 */
    reset_log(&log, &owner);
    if (!vos_resident_admit(&owner, 0u, CORR_DOMAIN, &id1, 0u, 16u,
                            clock, clock + CORR_RETENTION_BOUND, &h0)) {
        FAIL("two-slot admit h0");
    }
    print_step_json(0, "admit_h0", 1, &log, NULL, 0u, 0, &h0, &owner, clock, 1);

    /* Step 2: begin h0 on v1 */
    clock = 1u;
    reset_log(&log, &owner);
    if (!vos_resident_begin(&owner, &h0, CORR_DOMAIN, 0u, 16u, clock, &seq0) ||
        log.common_writes != 0u) {
        FAIL("common write during read traffic");
    }
    print_step_json(0, "begin_h0", 1, &log, NULL, 0u, 0, NULL, &owner, clock, 1);

    /* Step 3: replace_cow with v2 */
    reset_log(&log, &owner);
    if (kind == VOS_RESIDENT_SYSTEM) {
        vos_resident_generation(&owner, id2.generation);
    }
    if (!vos_resident_replace(&owner, &id2, p2, sizeof(p2)) || log.misclassified) {
        FAIL("two-slot replace_cow v2");
    }
    print_step_json(0, "replace_cow_v2", 1, &log, NULL, 0u, 0, NULL, &owner, clock, 1);

    /* Step 4: complete h0 (predecessor) */
    reset_log(&log, &owner);
    const int pred_ok = vos_resident_complete(
        &owner, &h0, CORR_DOMAIN, seq0, clock,
        kind == VOS_RESIDENT_USER ? vos_storage_verify_retained_resident
                                  : vos_storage_verify_resident,
        kind == VOS_RESIDENT_USER ? (void *)&receipt1 : (void *)&env.store,
        out_buf, sizeof(out_buf), &out_len);
    if (log.misclassified || log.common_writes != 0u) {
        FAIL("common write during read traffic");
    }
    if (kind == VOS_RESIDENT_USER) {
        if (!pred_ok || out_len != 16u || memcmp(out_buf, p1, 16u) != 0) {
            FAIL("userdata predecessor failed after CoW replace");
        }
    } else {
        if (pred_ok) {
            FAIL("system predecessor succeeded after generation advance");
        }
    }
    print_step_json(0, "complete_pred_h0", pred_ok, &log,
                    out_buf, pred_ok ? out_len : 0u, pred_ok,
                    NULL, &owner, clock, 1);

    /* Step 5: admit h1 on successor v2 and begin read */
    reset_log(&log, &owner);
    if (!vos_resident_admit(&owner, 1u, CORR_DOMAIN, &id2, 4u, 8u,
                            clock, clock + CORR_RETENTION_BOUND, &h1)) {
        FAIL("two-slot admit h1");
    }
    print_step_json(0, "admit_h1", 1, &log, NULL, 0u, 0, &h1, &owner, clock, 1);

    reset_log(&log, &owner);
    if (!vos_resident_begin(&owner, &h1, CORR_DOMAIN, 0u, 8u, clock, &seq1) ||
        log.common_writes != 0u) {
        FAIL("common write during read traffic");
    }
    print_step_json(0, "begin_h1", 1, &log, NULL, 0u, 0, NULL, &owner, clock, 1);

    /* Step 6: probe v3 replace while predecessor is occupied -> must refuse. */
    struct vos_resident_identity id3_probe = id2;
    id3_probe.version = 3u;
    if (kind == VOS_RESIDENT_SYSTEM) {
        id3_probe.generation = owner.common.generation;
    }
    reset_log(&log, &owner);
    if (vos_resident_replace(&owner, &id3_probe, p3, sizeof(p3))) {
        FAIL("third version accepted while predecessor occupied");
    }
    print_step_json(0, "replace_occupied_refused", 0, &log, NULL, 0u, 0, NULL, &owner, clock, 1);

    /* Step 7: retire_predecessor without barrier -> quarantine; 3rd version still refuses! */
    reset_log(&log, &owner);
    if (vos_resident_retire_predecessor(&owner, &id1, 0) || log.misclassified) {
        FAIL("retire_predecessor(0) unexpectedly succeeded");
    }
    print_step_json(0, "retire_pred_no_barrier", 1, &log, NULL, 0u, 0, NULL, &owner, clock, 1);

    reset_log(&log, &owner);
    if (vos_resident_replace(&owner, &id3_probe, p3, sizeof(p3))) {
        FAIL("third version accepted while predecessor quarantined");
    }
    print_step_json(0, "replace_quarantined_refused", 0, &log, NULL, 0u, 0, NULL, &owner, clock, 1);

    /* Step 8: retire_predecessor with barrier -> releases slot, preserves h1! */
    reset_log(&log, &owner);
    if (!vos_resident_retire_predecessor(&owner, &id1, 1) || log.misclassified) {
        FAIL("retire_predecessor(1) failed");
    }
    print_step_json(0, "retire_pred_barrier", 1, &log, NULL, 0u, 0, NULL, &owner, clock, 1);

    /* Step 9: complete h1 on current v2 -> succeeds! */
    reset_log(&log, &owner);
    if (!vos_resident_complete(&owner, &h1, CORR_DOMAIN, seq1, clock,
                               vos_storage_verify_resident, &env.store,
                               out_buf, sizeof(out_buf), &out_len) ||
        log.misclassified || log.common_writes != 0u ||
        out_len != 8u || memcmp(out_buf, p2 + 4u, 8u) != 0) {
        FAIL("current peer failed after predecessor retirement");
    }
    print_step_json(0, "complete_cur_h1", 1, &log, out_buf, out_len, 1, NULL, &owner, clock, 1);

    /* Step 10: commit v3 in storage and replace_cow_v3 -> reuses freed slot! */
    if (!commit_resident_object(&env, kind, 3u, p3, sizeof(p3), &id3)) {
        FAIL("two-slot v3 commit");
    }
    reset_log(&log, &owner);
    if (kind == VOS_RESIDENT_SYSTEM) {
        vos_resident_generation(&owner, id3.generation);
    }
    if (!vos_resident_replace(&owner, &id3, p3, sizeof(p3)) || log.misclassified) {
        FAIL("two-slot replace_cow v3 after barrier");
    }
    print_step_json(0, "replace_cow_v3", 1, &log, NULL, 0u, 0, NULL, &owner, clock, 1);

    /* Step 11: crash + reopen closes both slots and preserves sequences. */
    const uint64_t seq0_before = owner.sequence[0];
    const uint64_t seq1_before = owner.sequence[1];
    reset_log(&log, &owner);
    if (!vos_resident_crash(&owner, 1u) ||
        !vos_storage_reopen(&env.medium, &env.store, &env.crypto, env.slot, CORR_DOMAIN) ||
        owner.common.boot != 1u ||
        owner.common.backing[0].accepting != 0u ||
        owner.common.backing[1].accepting != 0u ||
        owner.common.reservation[0].live != 0u ||
        owner.common.reservation[1].live != 0u ||
        owner.pending[0].active != 0u ||
        owner.pending[1].active != 0u ||
        owner.sequence[0] != seq0_before ||
        owner.sequence[1] != seq1_before ||
        vos_resident_admit(&owner, 0u, CORR_DOMAIN, &id3, 0u, 8u,
                           clock, clock + CORR_RETENTION_BOUND, &h0) ||
        vos_resident_replace(&owner, &id3_probe, p3, sizeof(p3))) {
        FAIL("crash failed to close backing or preserve sequences");
    }
    print_step_json(0, "crash", 1, &log, NULL, 0u, 0, NULL, &owner, clock, 1);

    printf("]}");
    return 1;
}

static int run_scalar_campaign(uint32_t kind, int first_campaign)
{
    struct storage_env env;
    if (!init_storage_env(&env, kind)) {
        FAIL("scalar storage setup");
    }
    uint8_t payload[CORR_PAYLOAD_LEN];
    for (size_t i = 0u; i < sizeof(payload); ++i) {
        payload[i] = (uint8_t)(0x20u + i + (kind == VOS_RESIDENT_SYSTEM ? 32u : 0u));
    }
    struct vos_resident_identity id = {0};
    if (!commit_resident_object(&env, kind, 1u, payload, sizeof(payload), &id)) {
        FAIL("scalar storage commit");
    }

    struct vos_resident_owner owner = {0};
    struct write_log log = {0};
    reset_log(&log, &owner);
    if (!vos_resident_init(&owner, 0u, id.generation, CORR_COUNTER_BOUND,
                           observe_write, &log) ||
        !vos_resident_publish(&owner, &id, payload, sizeof(payload))) {
        FAIL("scalar resident publish");
    }
    struct vos_resident_handle h0 = {0}, h1 = {0};
    uint64_t seq0 = 0u, seq1 = 0u;
    if (!vos_resident_admit(&owner, 0u, CORR_DOMAIN, &id, 0u, 16u,
                            0u, CORR_RETENTION_BOUND, &h0) ||
        !vos_resident_admit(&owner, 1u, CORR_DOMAIN, &id, 4u, 12u,
                            0u, CORR_RETENTION_BOUND, &h1) ||
        !vos_resident_begin(&owner, &h0, CORR_DOMAIN, 0u, 16u, 1u, &seq0) ||
        !vos_resident_begin(&owner, &h1, CORR_DOMAIN, 0u, 12u, 1u, &seq1)) {
        FAIL("scalar admit/begin");
    }

    uint8_t out_buf[16] = {0};
    size_t out_len = 0u;
    if (!vos_resident_complete(&owner, &h0, CORR_DOMAIN, seq0, 1u,
                               vos_storage_verify_resident, &env.store,
                               out_buf, sizeof(out_buf), &out_len) ||
        out_len != 16u || memcmp(out_buf, payload, 16u) != 0 ||
        !vos_resident_begin(&owner, &h0, CORR_DOMAIN, 0u, 8u, 1u, &seq0)) {
        FAIL("scalar pre-retire read");
    }

    struct vos_kernel_effect_state kernel;
    struct vos_supervisor_execution execution;
    struct vos_resident_scalar_retirement attempt;
    struct vos_resident_scalar_binding binding;
    uint64_t masks[VOS_SUPERVISOR_UNITS] = {0}, bitmap = 0u, kclock = 0u;
    vos_cap_t roots[VOS_SUPERVISOR_UNITS] = {0}, caps[3][2] = {0};
    uint8_t owned[3][16] = {0};

    if (!vos_kernel_effect_init(&kernel, &vos_m8a_supervisor_manifest, 7u)) {
        FAIL("scalar kernel init");
    }
    for (uint32_t i = 0u; i < kernel.manifest.units; ++i) {
        roots[i].value = 100u + i;
        roots[i].tag = 1u;
        masks[i] = UINT64_C(1) << i;
        if (!vos_kernel_own(&kernel, i, owned[i], sizeof(owned[i]), caps[i], 2u)) {
            FAIL("scalar kernel own");
        }
    }
    if (!vos_kernel_effect_bind(&kernel, roots, masks, &bitmap, &kclock, 4u) ||
        vos_supervisor_execute(&kernel.manifest, 0u, 0u, &vos_kernel_supervisor_effects,
                               &kernel, &execution) != VOS_SUPERVISOR_EXECUTED) {
        FAIL("scalar supervisor execute");
    }
    memset(owned, 0x5au, sizeof(owned));
    for (uint32_t i = 0u; i < kernel.manifest.units; ++i) {
        caps[i][0] = roots[i];
        caps[i][1] = roots[i];
        kernel.unit[i].saved[31] = roots[i];
        kernel.unit[i].frames[1][31] = roots[i];
    }
    binding.epoch = 7u;
    binding.members = 7u;
    binding.holder_units[0] = 1u;
    binding.holder_units[1] = 2u;
    vos_resident_scalar_init(&attempt);

    reset_log(&log, &owner);
    const uint64_t mask = vos_resident_scalar_prepare(&attempt, &owner, &kernel, &binding);
    if (mask != 7u || log.misclassified) {
        FAIL("scalar retirement failed or released backing");
    }
    bitmap |= mask;
    kernel.resident_clean = 1u;
    if (!vos_resident_scalar_finish(&attempt, bitmap) ||
        attempt.phase != VOS_RESIDENT_SCALAR_COMPLETE ||
        kernel.epoch != 8u ||
        !owner.common.backing[0].occupied ||
        owner.common.backing[0].accepting ||
        owner.common.reservation[0].live ||
        owner.common.reservation[1].live ||
        owner.pending[0].active ||
        owner.pending[1].active) {
        FAIL("scalar retirement failed or released backing");
    }
    for (uint32_t i = 0u; i < kernel.manifest.units; ++i) {
        for (size_t n = 0u; n < sizeof(owned[i]); ++n) {
            if (owned[i][n] != 0u) {
                FAIL("scalar retirement failed or released backing");
            }
        }
        if (caps[i][0].tag || caps[i][1].tag ||
            kernel.unit[i].saved[31].tag || kernel.unit[i].frames[1][31].tag) {
            FAIL("scalar retirement failed or released backing");
        }
    }

    if (!first_campaign) {
        putchar(',');
    }
    printf("{\"kind\":\"%s\",\"domain\":%u,\"initial_generation\":%" PRIu64 ","
           "\"mask\":%" PRIu64 ",\"epoch_after\":%" PRIu64 ",\"identity\":",
           kind == VOS_RESIDENT_SYSTEM ? "SystemImage" : "UserData",
           CORR_DOMAIN, id.generation, mask, kernel.epoch);
    print_identity_json(&id);
    printf(",\"payload\":");
    print_bytes_json(payload, sizeof(payload));
    printf(",\"state\":");
    print_owner_state_json(&owner, 1u, 1);
    putchar('}');
    return 1;
}

int main(void)
{
    printf("{\"bounds\":{\"byte_bound\":%u,\"read_bound\":%u,"
           "\"retention_bound\":%u,\"counter_bound\":%u},\"single_slot\":[",
           CORR_BYTE_BOUND, CORR_READ_BOUND, CORR_RETENTION_BOUND, CORR_COUNTER_BOUND);
    if (!run_single_slot_campaign(VOS_RESIDENT_USER, 1) ||
        !run_single_slot_campaign(VOS_RESIDENT_SYSTEM, 0)) {
        return 1;
    }
    printf("],\"two_slot\":[");
    if (!run_two_slot_campaign(VOS_RESIDENT_USER, 1) ||
        !run_two_slot_campaign(VOS_RESIDENT_SYSTEM, 0)) {
        return 1;
    }
    printf("],\"scalar_retire\":[");
    if (!run_scalar_campaign(VOS_RESIDENT_USER, 1) ||
        !run_scalar_campaign(VOS_RESIDENT_SYSTEM, 0)) {
        return 1;
    }
    printf("]}\n");
    return 0;
}
