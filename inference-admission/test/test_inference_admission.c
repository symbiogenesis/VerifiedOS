// SPDX-License-Identifier: Apache-2.0
#include "vos_inference_admission.h"

#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(cond, msg)                                                       \
    do {                                                                       \
        if (!(cond)) {                                                         \
            fprintf(stderr, "FAIL (%s:%d): %s\n", __FILE__, __LINE__, (msg));  \
            return 1;                                                          \
        }                                                                      \
    } while (0)

static int server_equal(const vos_inf_server *a, const vos_inf_server *b) {
    if (a->slot != b->slot || a->workers_len != b->workers_len ||
        a->pool_bytes != b->pool_bytes ||
        a->session_capacity != b->session_capacity) {
        return 0;
    }
    for (size_t i = 0u; i < a->workers_len; ++i) {
        if (a->workers[i] != b->workers[i]) {
            return 0;
        }
    }
    return 1;
}

static int shape_equal(const vos_inf_shape *a, const vos_inf_shape *b) {
    return a->resident_bytes == b->resident_bytes &&
           a->context_length == b->context_length &&
           a->format == b->format &&
           a->expert_count == b->expert_count &&
           a->top_k == b->top_k &&
           a->kv_bytes_per_token == b->kv_bytes_per_token;
}

static int test_codec_controls(void) {
    const vos_inf_widths widths = {
        .w_resident_bytes = 2u,
        .w_context_length = 2u,
        .w_format = 2u,
        .w_expert_count = 2u,
        .w_top_k = 2u,
        .w_kv_bytes_per_token = 2u
    };
    const vos_inf_shape shape = {
        .resident_bytes = 40u,
        .context_length = 64u,
        .format = 4u,
        .expert_count = 8u,
        .top_k = 2u,
        .kv_bytes_per_token = 10u
    };
    int ok = 0;
    CHECK(vos_inf_schema_bytes(&widths, &ok) == 12u && ok == 1,
          "demo schema must be 12 bytes");
    CHECK(vos_inf_shape_fits(&widths, &shape) == 1, "demo shape must fit");

    uint8_t buf[VOS_INF_MAX_DESCRIPTOR_BYTES + 1u] = {0};
    size_t out_len = 0u;
    CHECK(vos_inf_encode_shape(&widths, &shape, buf, sizeof(buf), &out_len) == 1,
          "encode demo shape");
    CHECK(out_len == 12u, "encoded length must equal schema_bytes");

    vos_inf_shape decoded = {0};
    CHECK(vos_inf_decode_shape(&widths, buf, out_len, &decoded) == 1,
          "decode demo shape");
    CHECK(shape_equal(&decoded, &shape), "round-trip shape equality");

    uint8_t reencoded[VOS_INF_MAX_DESCRIPTOR_BYTES] = {0};
    size_t re_len = 0u;
    CHECK(vos_inf_encode_shape(&widths, &decoded, reencoded, sizeof(reencoded),
                               &re_len) == 1,
          "re-encode decoded shape");
    CHECK(re_len == out_len && memcmp(reencoded, buf, out_len) == 0,
          "re-encoding must reproduce identical bytes");

    /* Trailing byte (even zero) and truncated input must be refused. */
    buf[12] = 0u;
    CHECK(vos_inf_decode_shape(&widths, buf, 13u, &decoded) == 0,
          "trailing byte must be refused");
    CHECK(vos_inf_decode_shape(&widths, buf, 11u, &decoded) == 0,
          "truncated descriptor must be refused");

    /* Width bounds: 0 allows only 0, 1 allows <= 255, 8 allows full uint64_t. */
    const vos_inf_widths mixed_widths = {8u, 1u, 0u, 2u, 1u, 4u};
    const vos_inf_shape fit_mixed = {UINT64_MAX, 255u, 0u, 65535u, 2u, 100000u};
    CHECK(vos_inf_shape_fits(&mixed_widths, &fit_mixed) == 1,
          "boundary values fit mixed widths");
    CHECK(vos_inf_encode_shape(&mixed_widths, &fit_mixed, buf, sizeof(buf),
                               &out_len) == 1 && out_len == 16u,
          "encode mixed widths");
    CHECK(vos_inf_decode_shape(&mixed_widths, buf, out_len, &decoded) == 1 &&
          shape_equal(&decoded, &fit_mixed),
          "decode mixed widths");

    const vos_inf_shape bad_zero = {0u, 0u, 1u, 0u, 0u, 0u};
    CHECK(vos_inf_shape_fits(&mixed_widths, &bad_zero) == 0,
          "nonzero value in zero-width field must fail fit");
    const vos_inf_shape bad_u8 = {0u, 256u, 0u, 0u, 0u, 0u};
    CHECK(vos_inf_shape_fits(&mixed_widths, &bad_u8) == 0,
          "256 in 1-byte field must fail fit");
    const vos_inf_widths bad_w = {9u, 1u, 1u, 1u, 1u, 1u};
    CHECK(vos_inf_widths_valid(&bad_w) == 0, "width > 8 must fail");
    return 0;
}

static int test_admission_and_ceiling_controls(void) {
    const vos_inf_widths widths = {2u, 2u, 2u, 2u, 2u, 2u};
    const vos_inf_ceiling ceiling = {
        .max_resident_bytes = 50u,
        .max_context_length = 64u,
        .admitted_formats = {4u, 5u},
        .admitted_formats_len = 2u,
        .max_expert_count = 8u,
        .fixed_top_k = 2u,
        .max_kv_bytes_per_token = 16u,
        .ceiling_grant = 200u
    };
    const vos_inf_costs costs = {
        .dense_work_per_token = 10u,
        .expert_work_per_token = 3u,
        .fetch_penalty = 5u
    };
    const uint8_t all_res[8] = {1u, 1u, 1u, 1u, 1u, 1u, 1u, 1u};
    const vos_inf_composition comp = {
        .widths = widths,
        .ceiling = ceiling,
        .costs = costs,
        .residency = {.resident = all_res, .len = 8u},
        .kv_placement = VOS_KV_WEIGHTS_AND_CACHE
    };
    const vos_inf_server srv = {
        .slot = 40u,
        .workers = {0u, 1u},
        .workers_len = 2u,
        .pool_bytes = 60u,
        .session_capacity = 1u
    };
    const vos_inf_sessions idle = {.sessions_open = 0u};
    const vos_inf_sessions full = {.sessions_open = 1u};

    const vos_inf_shape boundary = {50u, 64u, 5u, 8u, 2u, 16u};
    CHECK(vos_inf_why_refused(&ceiling, &boundary) == VOS_INF_REFUSAL_NONE,
          "exact boundary shape must pass ceiling");

    /* Every ceiling field one past its boundary must return its exact refusal. */
    const struct {
        vos_inf_shape shape;
        vos_inf_refusal expected;
    } cases[] = {
        {{51u, 64u, 5u, 8u, 2u, 16u}, VOS_INF_RESIDENT_BYTES_ABOVE_CEILING},
        {{50u, 65u, 5u, 8u, 2u, 16u}, VOS_INF_CONTEXT_ABOVE_CEILING},
        {{50u, 64u, 6u, 8u, 2u, 16u}, VOS_INF_FORMAT_NOT_ADMITTED},
        {{50u, 64u, 5u, 9u, 2u, 16u}, VOS_INF_EXPERT_COUNT_ABOVE_CEILING},
        {{50u, 64u, 5u, 8u, 3u, 16u}, VOS_INF_TOP_K_NOT_THE_FIXED_VALUE},
        {{50u, 64u, 5u, 8u, 2u, 17u}, VOS_INF_KV_PER_TOKEN_ABOVE_CEILING}
    };
    for (size_t i = 0u; i < sizeof(cases) / sizeof(cases[0]); ++i) {
        CHECK(vos_inf_why_refused(&ceiling, &cases[i].shape) == cases[i].expected,
              "ceiling field above bound must return named refusal");
        uint8_t desc[12] = {0};
        size_t dlen = 0u;
        CHECK(vos_inf_encode_shape(&widths, &cases[i].shape, desc, sizeof(desc),
                                   &dlen) == 1,
              "encode over-ceiling shape");
        const vos_inf_request req = {desc, dlen, 1u};
        const vos_inf_step step =
            vos_inf_opening(&comp, &srv, idle, &req);
        CHECK(step.verdict == VOS_INF_REFUSED && step.refusal == cases[i].expected,
              "opening refuses above-ceiling shape");
        CHECK(server_equal(&step.server, &srv) && step.sessions.sessions_open == 0u,
              "refusal preserves server and session occupancy");
    }

    /* Demo shape: 40 + 10 = 50 bytes/token, grant 200 -> admitted rate 4. */
    const vos_inf_shape demo = {40u, 64u, 4u, 8u, 2u, 10u};
    uint8_t demo_desc[13] = {0};
    size_t demo_len = 0u;
    CHECK(vos_inf_encode_shape(&widths, &demo, demo_desc, sizeof(demo_desc),
                               &demo_len) == 1,
          "encode demo");
    const vos_inf_request ok_req = {demo_desc, demo_len, 4u};
    const vos_inf_step admitted =
        vos_inf_composition_opening(&comp, &srv, idle, &ok_req);
    CHECK(admitted.verdict == VOS_INF_ADMITTED &&
          admitted.refusal == VOS_INF_REFUSAL_NONE &&
          admitted.admitted_rate == 4u &&
          admitted.sessions.sessions_open == 1u &&
          server_equal(&admitted.server, &srv),
          "demo admission succeeds at exact derived rate 4");

    /* Above-grant request (5 > 4) must be refused without degradation. */
    const vos_inf_request greedy_req = {demo_desc, demo_len, 5u};
    const vos_inf_step greedy =
        vos_inf_composition_opening(&comp, &srv, idle, &greedy_req);
    CHECK(greedy.verdict == VOS_INF_REFUSED &&
          greedy.refusal == VOS_INF_TOKEN_RATE_ABOVE_GRANT &&
          greedy.admitted_rate == 0u &&
          greedy.sessions.sessions_open == 0u &&
          server_equal(&greedy.server, &srv),
          "above-grant request refused without degradation");

    /* Full session pool must refuse without overcommit. */
    const vos_inf_step exhausted =
        vos_inf_composition_opening(&comp, &srv, full, &ok_req);
    CHECK(exhausted.verdict == VOS_INF_REFUSED &&
          exhausted.refusal == VOS_INF_SESSION_POOL_EXHAUSTED &&
          exhausted.sessions.sessions_open == 1u &&
          server_equal(&exhausted.server, &srv),
          "full pool refuses without overcommit");

    /* Trailing byte must refuse DescriptorNotCanonical. */
    demo_desc[12] = 0u;
    const vos_inf_request trailing_req = {demo_desc, 13u, 1u};
    const vos_inf_step trailing =
        vos_inf_composition_opening(&comp, &srv, idle, &trailing_req);
    CHECK(trailing.verdict == VOS_INF_REFUSED &&
          trailing.refusal == VOS_INF_DESCRIPTOR_NOT_CANONICAL &&
          trailing.sessions.sessions_open == 0u,
          "trailing byte refused as non-canonical");

    /* Nonresident expert must refuse before ceiling checks. */
    const uint8_t missing_res[8] = {0u, 1u, 1u, 1u, 1u, 1u, 1u, 1u};
    vos_inf_composition missing_comp = comp;
    missing_comp.residency = (vos_inf_residency){.resident = missing_res, .len = 8u};
    const vos_inf_step missing =
        vos_inf_composition_opening(&missing_comp, &srv, idle, &ok_req);
    CHECK(missing.verdict == VOS_INF_REFUSED &&
          missing.refusal == VOS_INF_EXPERT_NOT_RESIDENT &&
          missing.sessions.sessions_open == 0u,
          "nonresident expert refused at composition opening");

    /* Zero per-token bytes must refuse PerTokenBytesNotDeclared. */
    const vos_inf_shape zero_demand = {0u, 64u, 4u, 8u, 2u, 0u};
    uint8_t zero_desc[12] = {0};
    size_t zero_len = 0u;
    CHECK(vos_inf_encode_shape(&widths, &zero_demand, zero_desc, sizeof(zero_desc),
                               &zero_len) == 1,
          "encode zero demand");
    const vos_inf_request zero_req = {zero_desc, zero_len, 0u};
    const vos_inf_step zero_step =
        vos_inf_composition_opening(&comp, &srv, idle, &zero_req);
    CHECK(zero_step.verdict == VOS_INF_REFUSED &&
          zero_step.refusal == VOS_INF_PER_TOKEN_BYTES_NOT_DECLARED,
          "zero per-token byte demand refused");

    return 0;
}

static int test_residency_grant_and_ensemble_controls(void) {
    const vos_inf_shape shape = {40u, 64u, 4u, 8u, 2u, 10u};
    const vos_inf_costs costs = {10u, 3u, 5u};
    const uint8_t all_res[8] = {1u, 1u, 1u, 1u, 1u, 1u, 1u, 1u};
    const vos_inf_residency full = {all_res, 8u};
    const uint8_t missing_zero[8] = {0u, 1u, 1u, 1u, 1u, 1u, 1u, 1u};
    const vos_inf_residency missing = {missing_zero, 8u};

    const uint64_t route_a[2] = {0u, 1u};
    const uint64_t route_b[2] = {3u, 7u};
    const uint64_t route_repeat[2] = {2u, 2u};
    const uint64_t route_oob[2] = {0u, 8u};
    uint64_t work_a = 0u, work_b = 0u, work_r = 0u;
    CHECK(vos_inf_checked_routed_work(&shape, &costs, &full, route_a, 2u, &work_a) == 1 &&
          vos_inf_checked_routed_work(&shape, &costs, &full, route_b, 2u, &work_b) == 1 &&
          vos_inf_checked_routed_work(&shape, &costs, &full, route_repeat, 2u, &work_r) == 1,
          "valid routes compute work");
    CHECK(work_a == 16u && work_b == 16u && work_r == 16u,
          "uniform expert cost makes work routing-blind");

    uint64_t bad_work = 999u;
    CHECK(vos_inf_checked_routed_work(&shape, &costs, &full, route_oob, 2u, &bad_work) == 0 &&
          bad_work == 999u,
          "out-of-range route fails and preserves output");
    CHECK(vos_inf_checked_routed_work(&shape, &costs, &missing, route_b, 2u, &bad_work) == 0,
          "missing unrouted expert still fails residency check");

    const vos_inf_fetch f_ok = vos_inf_serve(&full, 3u);
    CHECK(f_ok.kind == VOS_INF_FROM_RESIDENT_BANK && f_ok.expert == 3u &&
          f_ok.refusal == VOS_INF_REFUSAL_NONE,
          "resident expert served from bank");
    const vos_inf_fetch f_bad = vos_inf_serve(&missing, 0u);
    CHECK(f_bad.kind == VOS_INF_FETCH_REFUSED &&
          f_bad.refusal == VOS_INF_ROUTED_FETCH_ACROSS_STORAGE,
          "nonresident expert refuses storage fetch");

    /* KV placement arms: weights_and_cache = 50 -> rate 4; weights_only = 40 -> rate 5. */
    uint64_t bpt_bank = 0u, bpt_weights = 0u, r_bank = 0u, r_weights = 0u;
    CHECK(vos_inf_per_token_bytes(&shape, VOS_KV_WEIGHTS_AND_CACHE, &bpt_bank) == 1 &&
          bpt_bank == 50u, "weights_and_cache = 50");
    CHECK(vos_inf_per_token_bytes(&shape, VOS_KV_WEIGHTS_ONLY, &bpt_weights) == 1 &&
          bpt_weights == 40u, "weights_only = 40");
    CHECK(vos_inf_admitted_rate(200u, bpt_bank, &r_bank) == 1 && r_bank == 4u,
          "weights_and_cache rate = 4");
    CHECK(vos_inf_admitted_rate(200u, bpt_weights, &r_weights) == 1 && r_weights == 5u,
          "weights_only rate = 5");

    /* Ensemble rate = min of members (200/50 = 4, 180/60 = 3 -> 3). */
    const vos_inf_member members[2] = {{200u, 50u}, {180u, 60u}};
    uint64_t ens_rate = 0u;
    CHECK(vos_inf_ensemble_rate(members, 2u, &ens_rate) == 1 && ens_rate == 3u,
          "ensemble rate is slowest member rate");
    const vos_inf_member zero_mem[1] = {{200u, 0u}};
    CHECK(vos_inf_ensemble_rate(zero_mem, 1u, &ens_rate) == 0,
          "ensemble member with zero bytes/token refused");

    /* Route dispatch has no implicit fallback. */
    const uint8_t qual[3] = {1u, 0u, 0u};
    vos_inf_route_dest served = VOS_INF_ROUTE_REMOTE_ENDPOINT;
    CHECK(vos_inf_dispatch(qual, VOS_INF_ROUTE_SOFTWARE_SERVER, &served) == 1 &&
          served == VOS_INF_ROUTE_SOFTWARE_SERVER,
          "qualified route accepted");
    CHECK(vos_inf_dispatch(qual, VOS_INF_ROUTE_MODULE_BROKER, &served) == 0 &&
          served == VOS_INF_ROUTE_SOFTWARE_SERVER,
          "unqualified route refused without fallback");

    return 0;
}

static int parse_hex(const char *hex, size_t expected_bytes, uint8_t *out) {
    if (expected_bytes == 0u) {
        return strcmp(hex, "-") == 0;
    }
    if (strlen(hex) != expected_bytes * 2u) {
        return 0;
    }
    for (size_t i = 0u; i < expected_bytes; ++i) {
        unsigned int byte_val = 0u;
        char pair[3] = {hex[2u * i], hex[2u * i + 1u], '\0'};
        char *end = NULL;
        unsigned long parsed = strtoul(pair, &end, 16);
        if (end == NULL || *end != '\0' || parsed > 255ul) {
            return 0;
        }
        byte_val = (unsigned int)parsed;
        out[i] = (uint8_t)byte_val;
    }
    return 1;
}

static int run_eval(void) {
    char cmd[32];
    while (scanf("%31s", cmd) == 1) {
        if (strcmp(cmd, "ENCODE") == 0) {
            unsigned int ws[6] = {0};
            uint64_t vs[6] = {0};
            for (size_t i = 0u; i < 6u; ++i) {
                if (scanf("%u", &ws[i]) != 1) {
                    return 2;
                }
            }
            for (size_t i = 0u; i < 6u; ++i) {
                if (scanf("%" SCNu64, &vs[i]) != 1) {
                    return 2;
                }
            }
            const vos_inf_widths widths = {
                (uint8_t)ws[0], (uint8_t)ws[1], (uint8_t)ws[2],
                (uint8_t)ws[3], (uint8_t)ws[4], (uint8_t)ws[5]
            };
            const vos_inf_shape shape = {vs[0], vs[1], vs[2], vs[3], vs[4], vs[5]};
            uint8_t buf[VOS_INF_MAX_DESCRIPTOR_BYTES] = {0};
            size_t len = 0u;
            if (!vos_inf_encode_shape(&widths, &shape, buf, sizeof(buf), &len)) {
                printf("ERR\n");
            } else {
                printf("OK %zu ", len);
                if (len == 0u) {
                    printf("-");
                } else {
                    for (size_t i = 0u; i < len; ++i) {
                        printf("%02x", buf[i]);
                    }
                }
                printf("\n");
            }
        } else if (strcmp(cmd, "DECODE") == 0) {
            unsigned int ws[6] = {0};
            size_t len = 0u;
            char hex[256] = {0};
            for (size_t i = 0u; i < 6u; ++i) {
                if (scanf("%u", &ws[i]) != 1) {
                    return 2;
                }
            }
            if (scanf("%zu %255s", &len, hex) != 2) {
                return 2;
            }
            if (len > 120u) {
                return 2;
            }
            uint8_t buf[120] = {0};
            if (!parse_hex(hex, len, buf)) {
                return 2;
            }
            const vos_inf_widths widths = {
                (uint8_t)ws[0], (uint8_t)ws[1], (uint8_t)ws[2],
                (uint8_t)ws[3], (uint8_t)ws[4], (uint8_t)ws[5]
            };
            vos_inf_shape shape = {0};
            if (!vos_inf_decode_shape(&widths, buf, len, &shape)) {
                printf("ERR\n");
            } else {
                printf("OK %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 "\n",
                       shape.resident_bytes, shape.context_length, shape.format,
                       shape.expert_count, shape.top_k, shape.kv_bytes_per_token);
            }
        } else if (strcmp(cmd, "OPEN") == 0) {
            unsigned int mode = 0u;
            unsigned int ws[6] = {0};
            vos_inf_composition comp;
            memset(&comp, 0, sizeof(comp));
            if (scanf("%u", &mode) != 1) {
                return 2;
            }
            for (size_t i = 0u; i < 6u; ++i) {
                if (scanf("%u", &ws[i]) != 1) {
                    return 2;
                }
            }
            comp.widths = (vos_inf_widths){
                (uint8_t)ws[0], (uint8_t)ws[1], (uint8_t)ws[2],
                (uint8_t)ws[3], (uint8_t)ws[4], (uint8_t)ws[5]
            };
            size_t fmt_cnt = 0u;
            if (scanf("%" SCNu64 " %" SCNu64 " %zu",
                      &comp.ceiling.max_resident_bytes,
                      &comp.ceiling.max_context_length, &fmt_cnt) != 3) {
                return 2;
            }
            if (fmt_cnt > VOS_INF_MAX_ADMITTED_FORMATS) {
                return 2;
            }
            comp.ceiling.admitted_formats_len = fmt_cnt;
            for (size_t i = 0u; i < fmt_cnt; ++i) {
                if (scanf("%" SCNu64, &comp.ceiling.admitted_formats[i]) != 1) {
                    return 2;
                }
            }
            if (scanf("%" SCNu64 " %" SCNu64 " %" SCNu64 " %" SCNu64,
                      &comp.ceiling.max_expert_count,
                      &comp.ceiling.fixed_top_k,
                      &comp.ceiling.max_kv_bytes_per_token,
                      &comp.ceiling.ceiling_grant) != 4) {
                return 2;
            }
            if (scanf("%" SCNu64 " %" SCNu64 " %" SCNu64,
                      &comp.costs.dense_work_per_token,
                      &comp.costs.expert_work_per_token,
                      &comp.costs.fetch_penalty) != 3) {
                return 2;
            }
            size_t res_cnt = 0u;
            if (scanf("%zu", &res_cnt) != 1 || res_cnt > VOS_INF_MAX_EXPERTS) {
                return 2;
            }
            uint8_t res_buf[VOS_INF_MAX_EXPERTS] = {0};
            for (size_t i = 0u; i < res_cnt; ++i) {
                unsigned int flag = 0u;
                if (scanf("%u", &flag) != 1) {
                    return 2;
                }
                res_buf[i] = (uint8_t)flag;
            }
            comp.residency = (vos_inf_residency){res_buf, res_cnt};
            unsigned int placement = 0u;
            vos_inf_server srv;
            memset(&srv, 0, sizeof(srv));
            vos_inf_sessions st = {0u};
            uint64_t req_rate = 0u;
            size_t desc_len = 0u;
            char hex[256] = {0};
            if (scanf("%u %" SCNu64 " %" SCNu64 " %" SCNu64 " %" SCNu64 " %" SCNu64 " %zu %255s",
                      &placement, &srv.slot, &srv.pool_bytes,
                      &srv.session_capacity, &st.sessions_open, &req_rate,
                      &desc_len, hex) != 8) {
                return 2;
            }
            if (desc_len > 120u) {
                return 2;
            }
            uint8_t desc[120] = {0};
            if (!parse_hex(hex, desc_len, desc)) {
                return 2;
            }
            comp.kv_placement = (vos_kv_placement)placement;
            const vos_inf_request req = {desc, desc_len, req_rate};
            const vos_inf_step step =
                mode ? vos_inf_composition_opening(&comp, &srv, st, &req)
                     : vos_inf_opening(&comp, &srv, st, &req);
            if (step.verdict == VOS_INF_ADMITTED) {
                printf("ADMIT %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 "\n",
                       step.admitted_rate, step.sessions.sessions_open,
                       step.server.slot, step.server.pool_bytes,
                       step.server.session_capacity);
            } else {
                printf("REFUSE %d %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 "\n",
                       (int)step.refusal, step.sessions.sessions_open,
                       step.server.slot, step.server.pool_bytes,
                       step.server.session_capacity);
            }
        } else if (strcmp(cmd, "WORK") == 0) {
            vos_inf_shape shape = {0};
            vos_inf_costs costs = {0};
            size_t res_cnt = 0u;
            size_t route_len = 0u;
            if (scanf("%" SCNu64 " %" SCNu64 " %" SCNu64 " %" SCNu64 " %" SCNu64 " %" SCNu64
                      " %" SCNu64 " %" SCNu64 " %" SCNu64 " %zu",
                      &shape.resident_bytes, &shape.context_length,
                      &shape.format, &shape.expert_count, &shape.top_k,
                      &shape.kv_bytes_per_token, &costs.dense_work_per_token,
                      &costs.expert_work_per_token, &costs.fetch_penalty,
                      &res_cnt) != 10 || res_cnt > VOS_INF_MAX_EXPERTS) {
                return 2;
            }
            uint8_t res_buf[VOS_INF_MAX_EXPERTS] = {0};
            for (size_t i = 0u; i < res_cnt; ++i) {
                unsigned int flag = 0u;
                if (scanf("%u", &flag) != 1) {
                    return 2;
                }
                res_buf[i] = (uint8_t)flag;
            }
            if (scanf("%zu", &route_len) != 1 || route_len > VOS_INF_MAX_EXPERTS) {
                return 2;
            }
            uint64_t route[VOS_INF_MAX_EXPERTS] = {0};
            for (size_t i = 0u; i < route_len; ++i) {
                if (scanf("%" SCNu64, &route[i]) != 1) {
                    return 2;
                }
            }
            const vos_inf_residency res = {res_buf, res_cnt};
            uint64_t work = 0u;
            if (!vos_inf_checked_routed_work(&shape, &costs, &res, route,
                                             route_len, &work)) {
                printf("ERR\n");
            } else {
                printf("OK %" PRIu64 "\n", work);
            }
        } else if (strcmp(cmd, "SERVE") == 0) {
            size_t res_cnt = 0u;
            uint64_t expert = 0u;
            if (scanf("%zu", &res_cnt) != 1 || res_cnt > VOS_INF_MAX_EXPERTS) {
                return 2;
            }
            uint8_t res_buf[VOS_INF_MAX_EXPERTS] = {0};
            for (size_t i = 0u; i < res_cnt; ++i) {
                unsigned int flag = 0u;
                if (scanf("%u", &flag) != 1) {
                    return 2;
                }
                res_buf[i] = (uint8_t)flag;
            }
            if (scanf("%" SCNu64, &expert) != 1) {
                return 2;
            }
            const vos_inf_residency res = {res_buf, res_cnt};
            const vos_inf_fetch f = vos_inf_serve(&res, expert);
            if (f.kind == VOS_INF_FROM_RESIDENT_BANK) {
                printf("BANK %" PRIu64 "\n", f.expert);
            } else {
                printf("REFUSE %d\n", (int)f.refusal);
            }
        } else if (strcmp(cmd, "ENSEMBLE") == 0) {
            size_t count = 0u;
            if (scanf("%zu", &count) != 1 || count > VOS_INF_MAX_ENSEMBLE_MEMBERS) {
                return 2;
            }
            vos_inf_member members[VOS_INF_MAX_ENSEMBLE_MEMBERS] = {0};
            for (size_t i = 0u; i < count; ++i) {
                if (scanf("%" SCNu64 " %" SCNu64,
                          &members[i].grant_bytes_per_second,
                          &members[i].bytes_per_token) != 2) {
                    return 2;
                }
            }
            uint64_t rate = 0u;
            if (!vos_inf_ensemble_rate(members, count, &rate)) {
                printf("ERR\n");
            } else {
                printf("OK %" PRIu64 "\n", rate);
            }
        } else {
            return 2;
        }
    }
    return 0;
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--eval") == 0) {
        return run_eval();
    }
    if (argc == 1 || (argc == 2 && strcmp(argv[1], "controls") == 0)) {
        if (test_codec_controls() != 0) {
            return 1;
        }
        if (test_admission_and_ceiling_controls() != 0) {
            return 1;
        }
        if (test_residency_grant_and_ensemble_controls() != 0) {
            return 1;
        }
        fprintf(stderr, "inference-admission C controls passed\n");
        return 0;
    }
    fprintf(stderr, "usage: %s [controls|--eval]\n", argv[0]);
    return 2;
}
