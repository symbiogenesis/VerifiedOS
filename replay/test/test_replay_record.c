// SPDX-License-Identifier: Apache-2.0
#include "vos_replay_record.h"

#include <stdio.h>
#include <string.h>

#define CHECK(cond, msg)                                                      \
    do {                                                                      \
        if (!(cond)) {                                                        \
            fprintf(stderr, "FAIL (%s:%d): %s\n", __FILE__, __LINE__, (msg)); \
            return 1;                                                         \
        }                                                                     \
    } while (0)

static void fill_digest(uint8_t out[VOS_RR_DIGEST_BYTES], uint8_t tag)
{
    for (size_t i = 0u; i < VOS_RR_DIGEST_BYTES; ++i) {
        out[i] = (uint8_t)(tag + (uint8_t)i);
    }
}

static void fill_key(uint8_t out[VOS_RR_KEY_BYTES])
{
    for (size_t i = 0u; i < VOS_RR_KEY_BYTES; ++i) {
        out[i] = (uint8_t)(0xA5u ^ (uint8_t)(i * 7u));
    }
}

static struct vos_rr_binding make_binding(uint8_t tag)
{
    struct vos_rr_binding b;
    memset(&b, 0, sizeof(b));
    b.base_image_root_len = 4u;
    b.base_image_root[0] = 0x00u;
    b.base_image_root[1] = tag;
    b.base_image_root[2] = 0x22u;
    b.base_image_root[3] = 0x33u;
    fill_digest(b.composition, (uint8_t)(tag + 0x10u));
    fill_digest(b.input_trace, (uint8_t)(tag + 0x20u));
    return b;
}

static int pub_valid_even_prefix(const uint8_t *payload, size_t len, void *ctx)
{
    (void)ctx;
    return len >= 2u && payload[0] == 0x10u;
}

struct fixed_prod_ctx {
    const uint8_t *data;
    size_t len;
    int decline;
    int fail;
    int calls;
    struct vos_rr_recorder *reentrant_rec;
    int reentrant_finish;
};

static enum vos_rr_status fixed_producer(void *ctx,
                                         uint8_t *out_buf,
                                         size_t max_len,
                                         size_t *out_len,
                                         int *out_declined)
{
    struct fixed_prod_ctx *p = (struct fixed_prod_ctx *)ctx;
    p->calls += 1;
    if (p->reentrant_rec != NULL) {
        if (p->reentrant_finish) {
            uint8_t wire[VOS_RR_MAX_WIRE_BYTES];
            size_t wlen = 0u;
            const struct vos_rr_binding b = make_binding(1u);
            (void)vos_rr_recorder_finish(p->reentrant_rec, &b, 0u, wire, sizeof(wire), &wlen);
        } else {
            struct vos_rr_point pt = {0u, 0u, 0u, 99u};
            uint8_t iface_id[VOS_RR_DIGEST_BYTES];
            fill_digest(iface_id, 0x01u);
            struct fixed_prod_ctx nested = {p->data, p->len, 0, 0, 0, NULL, 0};
            (void)vos_rr_recorder_record(p->reentrant_rec, &pt, iface_id,
                                         fixed_producer, &nested, NULL, NULL);
        }
    }
    if (p->fail) {
        return VOS_RR_ERR_PRODUCER_FAILED;
    }
    if (p->decline) {
        *out_declined = 1;
        *out_len = 0u;
        return VOS_RR_OK;
    }
    if (p->len > max_len) {
        return VOS_RR_ERR_PAYLOAD_OVER_LIMIT;
    }
    memcpy(out_buf, p->data, p->len);
    *out_len = p->len;
    *out_declined = 0;
    return VOS_RR_OK;
}

static void build_default_interfaces(struct vos_rr_interface_entry entries[4],
                                     struct vos_rr_interface profiles[4])
{
    const uint32_t srcs[4] = {
        VOS_RR_SRC_ENTROPY,
        VOS_RR_SRC_LINK_ADDRESS,
        VOS_RR_SRC_TIME_READ,
        VOS_RR_SRC_PHYSICAL_EVENT
    };
    for (uint32_t i = 0u; i < 4u; ++i) {
        memset(&entries[i], 0, sizeof(entries[i]));
        fill_digest(entries[i].profile.id, (uint8_t)(0x01u + i * 0x10u));
        entries[i].profile.source = srcs[i];
        entries[i].profile.max_payload_bytes = (i == 0u) ? 32u : 16u;
        if (i != 0u) {
            entries[i].validator = pub_valid_even_prefix;
        }
        profiles[i] = entries[i].profile;
    }
}

static int contains_subseq(const uint8_t *haystack,
                           size_t hlen,
                           const uint8_t *needle,
                           size_t nlen)
{
    if (nlen == 0u || hlen < nlen) {
        return 0;
    }
    for (size_t i = 0u; i <= hlen - nlen; ++i) {
        if (memcmp(haystack + i, needle, nlen) == 0) {
            return 1;
        }
    }
    return 0;
}

static void put_le64_t(uint8_t *dst, uint64_t v)
{
    for (uint32_t i = 0u; i < 8u; ++i) {
        dst[i] = (uint8_t)(v >> (8u * i));
    }
}

static void put_le32_t(uint8_t *dst, uint32_t v)
{
    for (uint32_t i = 0u; i < 4u; ++i) {
        dst[i] = (uint8_t)(v >> (8u * i));
    }
}

static int test_four_sources_and_secret_non_exposure(void)
{
    struct vos_rr_interface_entry entries[4];
    struct vos_rr_interface profiles[4];
    build_default_interfaces(entries, profiles);

    const struct vos_rr_binding binding = make_binding(1u);
    const struct vos_rr_limits limits = {VOS_RR_MAX_WIRE_BYTES, 8u};
    uint8_t seal_key[VOS_RR_KEY_BYTES];
    fill_key(seal_key);

    struct vos_rr_recorder rec;
    CHECK(vos_rr_recorder_init(&rec, &binding, &limits, entries, 4u, seal_key) == VOS_RR_OK,
          "recorder init failed");

    /* Snapshot isolation: mutate caller arrays after init. */
    entries[1].profile.source = VOS_RR_SRC_ENTROPY;
    entries[1].validator = NULL;
    enum vos_rr_source queried = VOS_RR_SRC_ENTROPY;
    CHECK(vos_rr_recorder_source_of(&rec, profiles[1].id, &queried) == VOS_RR_OK &&
              queried == VOS_RR_SRC_LINK_ADDRESS,
          "recorder snapshot failed");

    /* Record all 4 sources with monotonically increasing coordinates. */
    const uint8_t secret_draw[VOS_RR_DIGEST_BYTES] = {
        0xDEu, 0xADu, 0xBEu, 0xEFu, 0xCAu, 0xFEu, 0xBAu, 0xBEu,
        0x13u, 0x37u, 0x42u, 0x99u, 0xAAu, 0x55u, 0x77u, 0x88u,
        0x01u, 0x23u, 0x45u, 0x67u, 0x89u, 0xABu, 0xCDu, 0xEFu,
        0xFEu, 0xDCu, 0xBAu, 0x98u, 0x76u, 0x54u, 0x32u, 0x10u
    };
    const uint8_t link_addr[6] = {0x10u, 0x02u, 0x03u, 0x04u, 0x05u, 0x06u};
    const uint8_t time_read[8] = {0x10u, 0x00u, 0x00u, 0x01u, 0x02u, 0x03u, 0x04u, 0x05u};
    const uint8_t phys_evt[4] = {0x10u, 0xAAu, 0xBBu, 0xCCu};

    const struct vos_rr_point pts[4] = {
        {0u, 0u, 0u, 0u},
        {0u, 0u, 1u, 0u},
        {0u, 1u, 0u, 0u},
        {1u, 0u, 1u, 0u}
    };

    struct vos_rr_event evs[4];
    int accepted = 0;

    /* Declined draw releases reservation and advances nothing. */
    struct fixed_prod_ctx decl_ctx = {secret_draw, sizeof(secret_draw), 1, 0, 0, NULL, 0};
    CHECK(vos_rr_recorder_record(&rec, &pts[0], profiles[0].id,
                                 fixed_producer, &decl_ctx, &accepted, &evs[0]) == VOS_RR_OK &&
              accepted == 0 && rec.event_count == 0u,
          "declined draw mutated event count");

    struct fixed_prod_ctx p0 = {secret_draw, sizeof(secret_draw), 0, 0, 0, NULL, 0};
    CHECK(vos_rr_recorder_record(&rec, &pts[0], profiles[0].id,
                                 fixed_producer, &p0, &accepted, &evs[0]) == VOS_RR_OK &&
              accepted == 1 && evs[0].seq == 0u &&
              evs[0].payload_class == VOS_RR_CLASS_SECRET_COMMITMENT &&
              evs[0].payload_len == VOS_RR_DIGEST_BYTES,
          "entropy draw recording failed");

    uint8_t expected_commit[VOS_RR_DIGEST_BYTES];
    CHECK(vos_rr_seal_entropy_draw(seal_key, &binding, &pts[0], profiles[0].id,
                                   secret_draw, sizeof(secret_draw),
                                   expected_commit) == VOS_RR_OK,
          "seal helper failed");
    CHECK(memcmp(evs[0].payload, secret_draw, sizeof(secret_draw)) != 0,
          "raw entropy draw leaked into commitment");
    CHECK(memcmp(evs[0].payload, expected_commit, VOS_RR_DIGEST_BYTES) == 0,
          "entropy event payload did not match HMAC commitment");

    struct fixed_prod_ctx p1 = {link_addr, sizeof(link_addr), 0, 0, 0, NULL, 0};
    CHECK(vos_rr_recorder_record(&rec, &pts[1], profiles[1].id,
                                 fixed_producer, &p1, &accepted, &evs[1]) == VOS_RR_OK &&
              accepted == 1 && evs[1].seq == 1u &&
              evs[1].payload_class == VOS_RR_CLASS_PUBLIC_VERBATIM &&
              evs[1].payload_len == sizeof(link_addr) &&
              memcmp(evs[1].payload, link_addr, sizeof(link_addr)) == 0,
          "link_address verbatim recording failed");

    struct fixed_prod_ctx p2 = {time_read, sizeof(time_read), 0, 0, 0, NULL, 0};
    CHECK(vos_rr_recorder_record(&rec, &pts[2], profiles[2].id,
                                 fixed_producer, &p2, &accepted, &evs[2]) == VOS_RR_OK &&
              accepted == 1 && evs[2].seq == 2u &&
              evs[2].payload_class == VOS_RR_CLASS_PUBLIC_VERBATIM,
          "time_read recording failed");

    struct fixed_prod_ctx p3 = {phys_evt, sizeof(phys_evt), 0, 0, 0, NULL, 0};
    CHECK(vos_rr_recorder_record(&rec, &pts[3], profiles[3].id,
                                 fixed_producer, &p3, &accepted, &evs[3]) == VOS_RR_OK &&
              accepted == 1 && evs[3].seq == 3u &&
              evs[3].payload_class == VOS_RR_CLASS_PUBLIC_VERBATIM,
          "physical_event recording failed");

    uint8_t wire[VOS_RR_MAX_WIRE_BYTES];
    size_t wire_len = 0u;
    CHECK(vos_rr_recorder_finish(&rec, &binding, 4u, wire, sizeof(wire), &wire_len) == VOS_RR_OK,
          "recorder finish failed");
    CHECK(!contains_subseq(wire, wire_len, secret_draw, sizeof(secret_draw)),
          "raw entropy leak in finished wire payload");

    /* Decode wire and JSON roundtrip + strict demand cursor replay. */
    struct vos_rr_record decoded;
    CHECK(vos_rr_decode_wire(wire, wire_len, &binding, 4u, &limits,
                             profiles, 4u, &decoded) == VOS_RR_OK,
          "wire decode failed");

    char json[VOS_RR_MAX_JSON_BYTES];
    size_t json_len = 0u;
    CHECK(vos_rr_encode_json(&decoded, json, sizeof(json), &json_len) == VOS_RR_OK,
          "json encode failed");
    CHECK(strstr(json, "\"sealed_commitment\":\"") != NULL &&
              strstr(json, "\"value\":\"100203040506\"") != NULL,
          "json class field mismatch");

    struct vos_rr_record json_decoded;
    CHECK(vos_rr_decode_json(json, json_len, &binding, 4u, &limits,
                             profiles, 4u, &json_decoded) == VOS_RR_OK,
          "json decode failed");
    CHECK(json_decoded.event_count == 4u &&
              memcmp(json_decoded.events[0].payload, expected_commit, VOS_RR_DIGEST_BYTES) == 0,
          "json roundtrip mismatch");

    struct vos_rr_cursor cur;
    CHECK(vos_rr_cursor_init(&cur, &decoded, &binding, 4u, &limits,
                             profiles, 4u) == VOS_RR_OK,
          "cursor init failed");
    const uint32_t srcs[4] = {
        VOS_RR_SRC_ENTROPY, VOS_RR_SRC_LINK_ADDRESS,
        VOS_RR_SRC_TIME_READ, VOS_RR_SRC_PHYSICAL_EVENT
    };
    for (uint32_t i = 0u; i < 4u; ++i) {
        struct vos_rr_event ce;
        CHECK(vos_rr_cursor_consume(&cur, &pts[i], (enum vos_rr_source)srcs[i],
                                    profiles[i].id, &ce) == VOS_RR_OK,
              "cursor consume failed");
        CHECK(ce.seq == i, "cursor event seq mismatch");
    }
    /* Premature exhaustion after 4 events must refuse. */
    CHECK(vos_rr_cursor_consume(&cur, &pts[0], VOS_RR_SRC_ENTROPY,
                                profiles[0].id, NULL) == VOS_RR_ERR_EXHAUSTED,
          "premature cursor exhaustion ignored");
    CHECK(cur.failed == 1u, "cursor exhaustion did not latch failure");

    /* Re-run cursor cleanly to test cursor_finish. */
    CHECK(vos_rr_cursor_init(&cur, &decoded, &binding, 4u, &limits,
                             profiles, 4u) == VOS_RR_OK,
          "cursor re-init failed");
    for (uint32_t i = 0u; i < 4u; ++i) {
        CHECK(vos_rr_cursor_consume(&cur, &pts[i], (enum vos_rr_source)srcs[i],
                                    profiles[i].id, NULL) == VOS_RR_OK,
              "cursor consume 2 failed");
    }
    CHECK(vos_rr_cursor_finish(&cur) == VOS_RR_OK, "cursor finish failed");
    return 0;
}

static int test_pre_invocation_capacity_and_margin_release(void)
{
    struct vos_rr_interface_entry entries[4];
    struct vos_rr_interface profiles[4];
    build_default_interfaces(entries, profiles);

    const struct vos_rr_binding binding = make_binding(2u);
    uint8_t seal_key[VOS_RR_KEY_BYTES];
    fill_key(seal_key);

    /* Header = 80 + 4 = 84 bytes.
       Public interface 1 has max_payload_bytes = 16 -> worst event = 84 + 16 = 100 bytes.
       With max_body_bytes = 84 + 99 = 183, even a 2-byte public event must be refused
       BEFORE invoking producer. */
    const struct vos_rr_limits tight = {183u, 4u};
    struct vos_rr_recorder rec;
    CHECK(vos_rr_recorder_init(&rec, &binding, &tight, entries, 4u, seal_key) == VOS_RR_OK,
          "tight recorder init failed");

    const uint8_t small_val[2] = {0x10u, 0x01u};
    struct fixed_prod_ctx p_small = {small_val, sizeof(small_val), 0, 0, 0, NULL, 0};
    const struct vos_rr_point pt0 = {0u, 0u, 0u, 0u};
    int accepted = 0;
    CHECK(vos_rr_recorder_record(&rec, &pt0, profiles[1].id,
                                 fixed_producer, &p_small, &accepted, NULL) == VOS_RR_ERR_OVER_CAPACITY,
          "post-invocation capacity check allowed or wrong error");
    CHECK(p_small.calls == 0,
          "post-invocation capacity check invoked producer before reservation");
    CHECK(rec.failed == 1u && rec.fault_routed == 1u && rec.event_count == 0u,
          "capacity refusal failed to latch fault");

    /* Unused margin release: two events of 2 bytes and 16 bytes with exact budget.
       Header (84) + (84+2) + (84+16) = 84 + 86 + 100 = 270 bytes.
       Before second event, 84 + 86 + worst(100) = 270 <= 270!
       If unused margin (14 bytes) had remained charged, 84 + 100 + 100 = 284 > 270 would fail. */
    const struct vos_rr_limits exact_two = {270u, 4u};
    CHECK(vos_rr_recorder_init(&rec, &binding, &exact_two, entries, 4u, seal_key) == VOS_RR_OK,
          "exact_two init failed");
    CHECK(vos_rr_recorder_record(&rec, &pt0, profiles[1].id,
                                 fixed_producer, &p_small, &accepted, NULL) == VOS_RR_OK,
          "first small event failed");
    uint8_t full_val[16];
    memset(full_val, 0x10, sizeof(full_val));
    struct fixed_prod_ctx p_full = {full_val, sizeof(full_val), 0, 0, 0, NULL, 0};
    const struct vos_rr_point pt1 = {0u, 0u, 0u, 1u};
    CHECK(vos_rr_recorder_record(&rec, &pt1, profiles[1].id,
                                 fixed_producer, &p_full, &accepted, NULL) == VOS_RR_OK,
          "unused margin was not released after first event");
    uint8_t wire[VOS_RR_MAX_WIRE_BYTES];
    size_t wire_len = 0u;
    CHECK(vos_rr_recorder_finish(&rec, &binding, 2u, wire, sizeof(wire), &wire_len) == VOS_RR_OK &&
              wire_len == 270u,
          "exact_two finish failed");
    return 0;
}

static int test_refusals_and_latches(void)
{
    struct vos_rr_interface_entry entries[4];
    struct vos_rr_interface profiles[4];
    build_default_interfaces(entries, profiles);

    const struct vos_rr_binding binding = make_binding(3u);
    const struct vos_rr_limits limits = {VOS_RR_MAX_WIRE_BYTES, 8u};
    uint8_t seal_key[VOS_RR_KEY_BYTES];
    fill_key(seal_key);

    const uint8_t good_pub[4] = {0x10u, 0x01u, 0x02u, 0x03u};
    const uint8_t bad_pub[4] = {0xFFu, 0x01u, 0x02u, 0x03u};
    const struct vos_rr_point pt0 = {0u, 0u, 2u, 0u};
    const struct vos_rr_point pt1 = {0u, 0u, 2u, 1u};
    const struct vos_rr_point pt_reg_coord = {0u, 0u, 1u, 9u};
    const struct vos_rr_point pt_reg_retire = {1u, 0u, 1u, 0u};
    int accepted = 0;

    /* 1. Sticky failure latch prevents finish of uncertain prefix, and public validator works. */
    struct vos_rr_recorder rec;
    CHECK(vos_rr_recorder_init(&rec, &binding, &limits, entries, 4u, seal_key) == VOS_RR_OK,
          "latch test init failed");
    struct fixed_prod_ctx p_good = {good_pub, sizeof(good_pub), 0, 0, 0, NULL, 0};
    CHECK(vos_rr_recorder_record(&rec, &pt0, profiles[1].id,
                                 fixed_producer, &p_good, &accepted, NULL) == VOS_RR_OK,
          "prefix event failed");
    struct fixed_prod_ctx p_bad = {bad_pub, sizeof(bad_pub), 0, 0, 0, NULL, 0};
    CHECK(vos_rr_recorder_record(&rec, &pt1, profiles[1].id,
                                 fixed_producer, &p_bad, &accepted, NULL) == VOS_RR_ERR_PUBLIC_VALIDATION,
          "public validator bypassed");
    uint8_t wire[VOS_RR_MAX_WIRE_BYTES];
    size_t wire_len = 0u;
    CHECK(vos_rr_recorder_finish(&rec, &binding, 1u, wire, sizeof(wire), &wire_len) == VOS_RR_ERR_LATCHED_FAILURE,
          "missing sticky failure latch allowed finish");

    /* 2. Reentrancy inside callback latches failure even if inner return code is ignored. */
    CHECK(vos_rr_recorder_init(&rec, &binding, &limits, entries, 4u, seal_key) == VOS_RR_OK,
          "reentrant init failed");
    struct fixed_prod_ctx p_re = {good_pub, sizeof(good_pub), 0, 0, 0, &rec, 0};
    CHECK(vos_rr_recorder_record(&rec, &pt0, profiles[1].id,
                                 fixed_producer, &p_re, &accepted, NULL) == VOS_RR_ERR_REENTRANT,
          "reentrancy allowed inside record");
    CHECK(vos_rr_recorder_finish(&rec, &binding, 0u, wire, sizeof(wire), &wire_len) == VOS_RR_ERR_LATCHED_FAILURE,
          "reentrant failure did not latch finish");

    /* 3. Coordinate regression & local retire regression refused. */
    CHECK(vos_rr_recorder_init(&rec, &binding, &limits, entries, 4u, seal_key) == VOS_RR_OK,
          "coord init failed");
    CHECK(vos_rr_recorder_record(&rec, &pt0, profiles[1].id,
                                 fixed_producer, &p_good, &accepted, NULL) == VOS_RR_OK,
          "coord event 0 failed");
    CHECK(vos_rr_recorder_record(&rec, &pt_reg_coord, profiles[1].id,
                                 fixed_producer, &p_good, &accepted, NULL) == VOS_RR_ERR_COORD_REGRESSION,
          "coordinate regression accepted in recorder");

    CHECK(vos_rr_recorder_init(&rec, &binding, &limits, entries, 4u, seal_key) == VOS_RR_OK,
          "retire init failed");
    CHECK(vos_rr_recorder_record(&rec, &pt0, profiles[1].id,
                                 fixed_producer, &p_good, &accepted, NULL) == VOS_RR_OK,
          "retire event 0 failed");
    CHECK(vos_rr_recorder_record(&rec, &pt_reg_retire, profiles[1].id,
                                 fixed_producer, &p_good, &accepted, NULL) == VOS_RR_ERR_RETIRE_REGRESSION,
          "local retire regression accepted in recorder");

    /* 4. Build valid 2-event wire record and mutate wire to test decode/cursor refusals. */
    CHECK(vos_rr_recorder_init(&rec, &binding, &limits, entries, 4u, seal_key) == VOS_RR_OK,
          "wire test init failed");
    CHECK(vos_rr_recorder_record(&rec, &pt0, profiles[1].id,
                                 fixed_producer, &p_good, &accepted, NULL) == VOS_RR_OK,
          "wire event 0 failed");
    CHECK(vos_rr_recorder_record(&rec, &pt1, profiles[2].id,
                                 fixed_producer, &p_good, &accepted, NULL) == VOS_RR_OK,
          "wire event 1 failed");
    CHECK(vos_rr_recorder_finish(&rec, &binding, 2u, wire, sizeof(wire), &wire_len) == VOS_RR_OK,
          "wire finish failed");

    struct vos_rr_record out_rec;
    struct vos_rr_record bad_rec;
    /* Self-declared / mismatched binding must be refused. */
    struct vos_rr_binding wrong_binding = make_binding(9u);
    CHECK(vos_rr_decode_wire(wire, wire_len, &wrong_binding, 2u, &limits,
                             profiles, 4u, &bad_rec) == VOS_RR_ERR_BINDING_MISMATCH,
          "self-declared binding accepted");

    /* Expected count mismatch must be refused. */
    CHECK(vos_rr_decode_wire(wire, wire_len, &binding, 1u, &limits,
                             profiles, 4u, &bad_rec) == VOS_RR_ERR_COUNT_MISMATCH,
          "wrong expected count accepted");

    /* Caller-selected classification: flip payload_class of event 0 on wire. */
    uint8_t bad_wire[VOS_RR_MAX_WIRE_BYTES];
    memcpy(bad_wire, wire, wire_len);
    const size_t ev0_off = 8u + 4u + binding.base_image_root_len + 64u + 4u;
    put_le32_t(bad_wire + ev0_off + 44u, VOS_RR_CLASS_SECRET_COMMITMENT);
    CHECK(vos_rr_decode_wire(bad_wire, wire_len, &binding, 2u, &limits,
                             profiles, 4u, &bad_rec) == VOS_RR_ERR_CLASS_MISMATCH,
          "caller-selected classification accepted on wire");

    /* seq gap on wire. */
    memcpy(bad_wire, wire, wire_len);
    put_le64_t(bad_wire + ev0_off, 5u);
    CHECK(vos_rr_decode_wire(bad_wire, wire_len, &binding, 2u, &limits,
                             profiles, 4u, &bad_rec) == VOS_RR_ERR_SEQ_GAP,
          "seq gap accepted on wire");

    /* Coordinate regression on wire (set event 1 point = event 0 point). */
    memcpy(bad_wire, wire, wire_len);
    const size_t ev1_off = ev0_off + VOS_RR_WIRE_EVENT_FIXED_BYTES + sizeof(good_pub);
    put_le64_t(bad_wire + ev1_off + 32u, 0u);
    CHECK(vos_rr_decode_wire(bad_wire, wire_len, &binding, 2u, &limits,
                             profiles, 4u, &bad_rec) == VOS_RR_ERR_COORD_REGRESSION,
          "coordinate regression accepted on wire");

    /* JSON structural check: caller-selected payload key on public source refused. */
    CHECK(vos_rr_decode_wire(wire, wire_len, &binding, 2u, &limits,
                             profiles, 4u, &out_rec) == VOS_RR_OK,
          "valid decode failed");
    char json[VOS_RR_MAX_JSON_BYTES];
    size_t json_len = 0u;
    CHECK(vos_rr_encode_json(&out_rec, json, sizeof(json), &json_len) == VOS_RR_OK,
          "json encode 2 failed");
    char *val_pos = strstr(json, "\"value\"");
    CHECK(val_pos != NULL, "missing value key in json");
    char bad_json[VOS_RR_MAX_JSON_BYTES];
    const size_t prefix_len = (size_t)(val_pos - json);
    memcpy(bad_json, json, prefix_len);
    const char *inj = "\"sealed_commitment\"";
    memcpy(bad_json + prefix_len, inj, strlen(inj));
    memcpy(bad_json + prefix_len + strlen(inj), val_pos + 7u, json_len - prefix_len - 7u);
    const size_t bad_json_len = json_len - 7u + strlen(inj);
    CHECK(vos_rr_decode_json(bad_json, bad_json_len, &binding, 2u, &limits,
                             profiles, 4u, &bad_rec) == VOS_RR_ERR_CLASS_MISMATCH,
          "caller-selected classification accepted in json");

    /* Trailing event ignored by cursor finish must be refused. */
    struct vos_rr_cursor cur;
    CHECK(vos_rr_cursor_init(&cur, &out_rec, &binding, 2u, &limits,
                             profiles, 4u) == VOS_RR_OK,
          "cursor init 2 failed");
    CHECK(vos_rr_cursor_consume(&cur, &pt0, VOS_RR_SRC_LINK_ADDRESS,
                                profiles[1].id, NULL) == VOS_RR_OK,
          "cursor first consume failed");
    CHECK(vos_rr_cursor_finish(&cur) == VOS_RR_ERR_TRAILING_EVENTS,
          "trailing event ignored by cursor");
    CHECK(cur.failed == 1u, "cursor trailing event did not latch failure");

    return 0;
}

int main(void)
{
    if (test_four_sources_and_secret_non_exposure() != 0) {
        return 1;
    }
    if (test_pre_invocation_capacity_and_margin_release() != 0) {
        return 1;
    }
    if (test_refusals_and_latches() != 0) {
        return 1;
    }
    printf("replay_record_test: ok\n");
    return 0;
}
