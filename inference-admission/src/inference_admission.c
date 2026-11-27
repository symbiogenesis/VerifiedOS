// SPDX-License-Identifier: Apache-2.0
#include "vos_inference_admission.h"

#include <string.h>

static void extract_widths(const vos_inf_widths *widths,
                           uint8_t out[VOS_INF_SHAPE_FIELD_COUNT]) {
    out[0] = widths->w_resident_bytes;
    out[1] = widths->w_context_length;
    out[2] = widths->w_format;
    out[3] = widths->w_expert_count;
    out[4] = widths->w_top_k;
    out[5] = widths->w_kv_bytes_per_token;
}

static void extract_shape(const vos_inf_shape *shape,
                          uint64_t out[VOS_INF_SHAPE_FIELD_COUNT]) {
    out[0] = shape->resident_bytes;
    out[1] = shape->context_length;
    out[2] = shape->format;
    out[3] = shape->expert_count;
    out[4] = shape->top_k;
    out[5] = shape->kv_bytes_per_token;
}

static void store_shape(const uint64_t vals[VOS_INF_SHAPE_FIELD_COUNT],
                        vos_inf_shape *shape) {
    shape->resident_bytes = vals[0];
    shape->context_length = vals[1];
    shape->format = vals[2];
    shape->expert_count = vals[3];
    shape->top_k = vals[4];
    shape->kv_bytes_per_token = vals[5];
}

int vos_inf_widths_valid(const vos_inf_widths *widths) {
    if (widths == NULL) {
        return 0;
    }
    uint8_t ws[VOS_INF_SHAPE_FIELD_COUNT] = {0};
    extract_widths(widths, ws);
    for (size_t i = 0u; i < VOS_INF_SHAPE_FIELD_COUNT; ++i) {
        if (ws[i] > VOS_INF_MAX_FIELD_WIDTH) {
            return 0;
        }
    }
    return 1;
}

size_t vos_inf_schema_bytes(const vos_inf_widths *widths, int *ok) {
    if (!vos_inf_widths_valid(widths)) {
        if (ok != NULL) {
            *ok = 0;
        }
        return 0u;
    }
    uint8_t ws[VOS_INF_SHAPE_FIELD_COUNT] = {0};
    extract_widths(widths, ws);
    size_t total = 0u;
    for (size_t i = 0u; i < VOS_INF_SHAPE_FIELD_COUNT; ++i) {
        total += (size_t)ws[i];
    }
    if (ok != NULL) {
        *ok = 1;
    }
    return total;
}

int vos_inf_field_fits(uint8_t width, uint64_t value) {
    if (width > VOS_INF_MAX_FIELD_WIDTH) {
        return 0;
    }
    if (width == 0u) {
        return value == 0u;
    }
    if (width == VOS_INF_MAX_FIELD_WIDTH) {
        return 1;
    }
    const uint64_t limit = UINT64_C(1) << (8u * (unsigned)width);
    return value < limit;
}

int vos_inf_shape_fits(const vos_inf_widths *widths, const vos_inf_shape *shape) {
    if (!vos_inf_widths_valid(widths) || shape == NULL) {
        return 0;
    }
    uint8_t ws[VOS_INF_SHAPE_FIELD_COUNT] = {0};
    uint64_t vals[VOS_INF_SHAPE_FIELD_COUNT] = {0};
    extract_widths(widths, ws);
    extract_shape(shape, vals);
    for (size_t i = 0u; i < VOS_INF_SHAPE_FIELD_COUNT; ++i) {
        if (!vos_inf_field_fits(ws[i], vals[i])) {
            return 0;
        }
    }
    return 1;
}

int vos_inf_encode_shape(const vos_inf_widths *widths, const vos_inf_shape *shape,
                         uint8_t *out, size_t out_cap, size_t *out_len) {
    int ok = 0;
    const size_t total = vos_inf_schema_bytes(widths, &ok);
    if (!ok || shape == NULL || !vos_inf_shape_fits(widths, shape)) {
        return 0;
    }
    if (total > out_cap || (total > 0u && out == NULL)) {
        return 0;
    }
    uint8_t ws[VOS_INF_SHAPE_FIELD_COUNT] = {0};
    uint64_t vals[VOS_INF_SHAPE_FIELD_COUNT] = {0};
    extract_widths(widths, ws);
    extract_shape(shape, vals);

    size_t pos = 0u;
    for (size_t i = 0u; i < VOS_INF_SHAPE_FIELD_COUNT; ++i) {
        uint64_t v = vals[i];
        for (uint8_t b = 0u; b < ws[i]; ++b) {
            out[pos++] = (uint8_t)(v & 0xffu);
            v >>= 8u;
        }
    }
    if (out_len != NULL) {
        *out_len = pos;
    }
    return 1;
}

int vos_inf_decode_shape(const vos_inf_widths *widths, const uint8_t *bytes,
                         size_t len, vos_inf_shape *out_shape) {
    int ok = 0;
    const size_t total = vos_inf_schema_bytes(widths, &ok);
    if (!ok || out_shape == NULL) {
        return 0;
    }
    if (len != total || (len > 0u && bytes == NULL)) {
        return 0;
    }
    uint8_t ws[VOS_INF_SHAPE_FIELD_COUNT] = {0};
    uint64_t vals[VOS_INF_SHAPE_FIELD_COUNT] = {0};
    extract_widths(widths, ws);

    size_t pos = 0u;
    for (size_t i = 0u; i < VOS_INF_SHAPE_FIELD_COUNT; ++i) {
        uint64_t v = 0u;
        for (uint8_t b = 0u; b < ws[i]; ++b) {
            v |= ((uint64_t)bytes[pos++]) << (8u * (unsigned)b);
        }
        vals[i] = v;
    }
    store_shape(vals, out_shape);
    return 1;
}

static int format_is_admitted(const vos_inf_ceiling *ceiling, uint64_t fmt) {
    if (ceiling == NULL || ceiling->admitted_formats_len > VOS_INF_MAX_ADMITTED_FORMATS) {
        return 0;
    }
    for (size_t i = 0u; i < ceiling->admitted_formats_len; ++i) {
        if (ceiling->admitted_formats[i] == fmt) {
            return 1;
        }
    }
    return 0;
}

vos_inf_refusal vos_inf_why_refused(const vos_inf_ceiling *ceiling,
                                    const vos_inf_shape *shape) {
    if (ceiling == NULL || shape == NULL ||
        ceiling->admitted_formats_len > VOS_INF_MAX_ADMITTED_FORMATS) {
        return VOS_INF_DESCRIPTOR_NOT_CANONICAL;
    }
    if (shape->resident_bytes > ceiling->max_resident_bytes) {
        return VOS_INF_RESIDENT_BYTES_ABOVE_CEILING;
    }
    if (shape->context_length > ceiling->max_context_length) {
        return VOS_INF_CONTEXT_ABOVE_CEILING;
    }
    if (!format_is_admitted(ceiling, shape->format)) {
        return VOS_INF_FORMAT_NOT_ADMITTED;
    }
    if (shape->expert_count > ceiling->max_expert_count) {
        return VOS_INF_EXPERT_COUNT_ABOVE_CEILING;
    }
    if (shape->top_k != ceiling->fixed_top_k) {
        return VOS_INF_TOP_K_NOT_THE_FIXED_VALUE;
    }
    if (shape->kv_bytes_per_token > ceiling->max_kv_bytes_per_token) {
        return VOS_INF_KV_PER_TOKEN_ABOVE_CEILING;
    }
    return VOS_INF_REFUSAL_NONE;
}

static int residency_array_valid(const vos_inf_residency *res) {
    if (res == NULL || res->len > VOS_INF_MAX_EXPERTS) {
        return 0;
    }
    if (res->len > 0u && res->resident == NULL) {
        return 0;
    }
    for (size_t i = 0u; i < res->len; ++i) {
        if (res->resident[i] > 1u) {
            return 0;
        }
    }
    return 1;
}

int vos_inf_all_experts_resident(const vos_inf_shape *shape,
                                 const vos_inf_residency *res) {
    if (shape == NULL || !residency_array_valid(res)) {
        return 0;
    }
    if (shape->expert_count > (uint64_t)res->len) {
        return 0;
    }
    const size_t count = (size_t)shape->expert_count;
    for (size_t e = 0u; e < count; ++e) {
        if (res->resident[e] != 1u) {
            return 0;
        }
    }
    return 1;
}

int vos_inf_routing_ok(const vos_inf_shape *shape,
                       const uint64_t *route, size_t route_len) {
    if (shape == NULL || (uint64_t)route_len != shape->top_k ||
        route_len > VOS_INF_MAX_EXPERTS) {
        return 0;
    }
    if (route_len > 0u && route == NULL) {
        return 0;
    }
    for (size_t i = 0u; i < route_len; ++i) {
        if (route[i] >= shape->expert_count) {
            return 0;
        }
    }
    return 1;
}

int vos_inf_checked_routed_work(const vos_inf_shape *shape,
                                const vos_inf_costs *costs,
                                const vos_inf_residency *res,
                                const uint64_t *route, size_t route_len,
                                uint64_t *out_work) {
    if (shape == NULL || costs == NULL || out_work == NULL) {
        return 0;
    }
    if (!vos_inf_routing_ok(shape, route, route_len) ||
        !vos_inf_all_experts_resident(shape, res)) {
        return 0;
    }
    uint64_t total = costs->dense_work_per_token;
    for (size_t i = 0u; i < route_len; ++i) {
        if (total > UINT64_MAX - costs->expert_work_per_token) {
            return 0;
        }
        total += costs->expert_work_per_token;
    }
    *out_work = total;
    return 1;
}

vos_inf_fetch vos_inf_serve(const vos_inf_residency *res, uint64_t expert) {
    if (residency_array_valid(res) && expert < (uint64_t)res->len &&
        res->resident[(size_t)expert] == 1u) {
        return (vos_inf_fetch){
            .kind = VOS_INF_FROM_RESIDENT_BANK,
            .expert = expert,
            .refusal = VOS_INF_REFUSAL_NONE
        };
    }
    return (vos_inf_fetch){
        .kind = VOS_INF_FETCH_REFUSED,
        .expert = expert,
        .refusal = VOS_INF_ROUTED_FETCH_ACROSS_STORAGE
    };
}

int vos_inf_dispatch(const uint8_t qualified[3], vos_inf_route_dest requested,
                     vos_inf_route_dest *out_served) {
    if (qualified == NULL || out_served == NULL) {
        return 0;
    }
    const unsigned idx = (unsigned)requested;
    if (idx >= 3u || qualified[idx] != 1u) {
        return 0;
    }
    *out_served = requested;
    return 1;
}

int vos_inf_per_token_bytes(const vos_inf_shape *shape,
                            vos_kv_placement placement,
                            uint64_t *out_bytes) {
    if (shape == NULL || out_bytes == NULL) {
        return 0;
    }
    if (placement == VOS_KV_WEIGHTS_ONLY) {
        *out_bytes = shape->resident_bytes;
        return 1;
    }
    if (placement == VOS_KV_WEIGHTS_AND_CACHE) {
        if (shape->resident_bytes > UINT64_MAX - shape->kv_bytes_per_token) {
            return 0;
        }
        *out_bytes = shape->resident_bytes + shape->kv_bytes_per_token;
        return 1;
    }
    return 0;
}

int vos_inf_admitted_rate(uint64_t grant_bytes_per_sec,
                          uint64_t per_token_bytes,
                          uint64_t *out_rate) {
    if (out_rate == NULL || per_token_bytes == 0u) {
        return 0;
    }
    *out_rate = grant_bytes_per_sec / per_token_bytes;
    return 1;
}

vos_inf_refusal vos_inf_grant_refusal(uint64_t grant_bytes_per_sec,
                                      uint64_t per_token_bytes,
                                      uint64_t requested_rate) {
    uint64_t max_rate = 0u;
    if (!vos_inf_admitted_rate(grant_bytes_per_sec, per_token_bytes, &max_rate)) {
        return VOS_INF_PER_TOKEN_BYTES_NOT_DECLARED;
    }
    if (requested_rate > max_rate) {
        return VOS_INF_TOKEN_RATE_ABOVE_GRANT;
    }
    return VOS_INF_REFUSAL_NONE;
}

int vos_inf_ensemble_rate(const vos_inf_member *members,
                          size_t member_count,
                          uint64_t *out_rate) {
    if (members == NULL || out_rate == NULL ||
        member_count == 0u || member_count > VOS_INF_MAX_ENSEMBLE_MEMBERS) {
        return 0;
    }
    uint64_t min_rate = 0u;
    for (size_t i = 0u; i < member_count; ++i) {
        uint64_t rate = 0u;
        if (!vos_inf_admitted_rate(members[i].grant_bytes_per_second,
                                   members[i].bytes_per_token, &rate)) {
            return 0;
        }
        if (i == 0u || rate < min_rate) {
            min_rate = rate;
        }
    }
    *out_rate = min_rate;
    return 1;
}

static vos_inf_step refused_step(const vos_inf_server *srv,
                                 vos_inf_sessions st,
                                 vos_inf_refusal reason) {
    vos_inf_step step;
    memset(&step, 0, sizeof(step));
    if (srv != NULL) {
        step.server = *srv;
    }
    step.sessions = st;
    step.verdict = VOS_INF_REFUSED;
    step.admitted_rate = 0u;
    step.refusal = reason;
    return step;
}

static vos_inf_step opening_decoded(const vos_inf_composition *comp,
                                    const vos_inf_server *srv,
                                    vos_inf_sessions st,
                                    const vos_inf_request *req,
                                    const vos_inf_shape *shape) {
    const vos_inf_refusal ceiling_reason = vos_inf_why_refused(&comp->ceiling, shape);
    if (ceiling_reason != VOS_INF_REFUSAL_NONE) {
        return refused_step(srv, st, ceiling_reason);
    }

    uint64_t traffic = 0u;
    if (!vos_inf_per_token_bytes(shape, comp->kv_placement, &traffic) || traffic == 0u) {
        return refused_step(srv, st, VOS_INF_PER_TOKEN_BYTES_NOT_DECLARED);
    }

    if (st.sessions_open >= srv->session_capacity) {
        return refused_step(srv, st, VOS_INF_SESSION_POOL_EXHAUSTED);
    }

    uint64_t max_rate = 0u;
    if (!vos_inf_admitted_rate(comp->ceiling.ceiling_grant, traffic, &max_rate)) {
        return refused_step(srv, st, VOS_INF_PER_TOKEN_BYTES_NOT_DECLARED);
    }
    if (req->requested_tokens_per_second > max_rate) {
        return refused_step(srv, st, VOS_INF_TOKEN_RATE_ABOVE_GRANT);
    }

    return (vos_inf_step){
        .server = *srv,
        .sessions = {.sessions_open = st.sessions_open + 1u},
        .verdict = VOS_INF_ADMITTED,
        .admitted_rate = max_rate,
        .refusal = VOS_INF_REFUSAL_NONE
    };
}

static int server_valid(const vos_inf_server *srv) {
    return srv != NULL && srv->workers_len <= VOS_INF_MAX_WORKERS;
}

vos_inf_step vos_inf_opening(const vos_inf_composition *comp,
                             const vos_inf_server *srv,
                             vos_inf_sessions st,
                             const vos_inf_request *req) {
    if (comp == NULL || !server_valid(srv) || req == NULL) {
        return refused_step(srv, st, VOS_INF_DESCRIPTOR_NOT_CANONICAL);
    }
    vos_inf_shape shape;
    if (!vos_inf_decode_shape(&comp->widths, req->descriptor,
                              req->descriptor_len, &shape)) {
        return refused_step(srv, st, VOS_INF_DESCRIPTOR_NOT_CANONICAL);
    }
    return opening_decoded(comp, srv, st, req, &shape);
}

vos_inf_step vos_inf_composition_opening(const vos_inf_composition *comp,
                                         const vos_inf_server *srv,
                                         vos_inf_sessions st,
                                         const vos_inf_request *req) {
    if (comp == NULL || !server_valid(srv) || req == NULL) {
        return refused_step(srv, st, VOS_INF_DESCRIPTOR_NOT_CANONICAL);
    }
    vos_inf_shape shape;
    if (!vos_inf_decode_shape(&comp->widths, req->descriptor,
                              req->descriptor_len, &shape)) {
        return refused_step(srv, st, VOS_INF_DESCRIPTOR_NOT_CANONICAL);
    }
    if (!vos_inf_all_experts_resident(&shape, &comp->residency)) {
        return refused_step(srv, st, VOS_INF_EXPERT_NOT_RESIDENT);
    }
    if (shape.top_k > shape.expert_count) {
        return refused_step(srv, st, VOS_INF_TOP_K_NOT_THE_FIXED_VALUE);
    }
    return opening_decoded(comp, srv, st, req, &shape);
}
