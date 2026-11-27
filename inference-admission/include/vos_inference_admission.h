// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_INFERENCE_ADMISSION_H
#define VOS_INFERENCE_ADMISSION_H

#include <stddef.h>
#include <stdint.h>

/* GC-free C17 inference descriptor, residency and grant-to-rate admission
 * core matching [InferenceAdmission.v](../../proofs/InferenceAdmission.v) and
 * [the inference contract](../../tools/vos/inference_contract.py).
 *
 * All buffers are caller-owned and loops are statically bounded. Refusals
 * preserve server and session state. */

enum {
    VOS_INF_SHAPE_FIELD_COUNT = 6u,
    VOS_INF_MAX_FIELD_WIDTH = 8u,
    VOS_INF_MAX_DESCRIPTOR_BYTES = VOS_INF_SHAPE_FIELD_COUNT * VOS_INF_MAX_FIELD_WIDTH,
    VOS_INF_MAX_ADMITTED_FORMATS = 32u,
    VOS_INF_MAX_WORKERS = 64u,
    VOS_INF_MAX_EXPERTS = 4096u,
    VOS_INF_MAX_ENSEMBLE_MEMBERS = 64u
};

typedef enum {
    VOS_INF_REFUSAL_NONE = 0,
    VOS_INF_DESCRIPTOR_NOT_CANONICAL = 1,
    VOS_INF_RESIDENT_BYTES_ABOVE_CEILING = 2,
    VOS_INF_CONTEXT_ABOVE_CEILING = 3,
    VOS_INF_FORMAT_NOT_ADMITTED = 4,
    VOS_INF_EXPERT_COUNT_ABOVE_CEILING = 5,
    VOS_INF_TOP_K_NOT_THE_FIXED_VALUE = 6,
    VOS_INF_KV_PER_TOKEN_ABOVE_CEILING = 7,
    VOS_INF_PER_TOKEN_BYTES_NOT_DECLARED = 8,
    VOS_INF_SESSION_POOL_EXHAUSTED = 9,
    VOS_INF_TOKEN_RATE_ABOVE_GRANT = 10,
    VOS_INF_EXPERT_NOT_RESIDENT = 11,
    VOS_INF_ROUTED_FETCH_ACROSS_STORAGE = 12,
    VOS_INF_ROUTE_NOT_QUALIFIED = 13
} vos_inf_refusal;

typedef enum {
    VOS_KV_WEIGHTS_ONLY = 0,
    VOS_KV_WEIGHTS_AND_CACHE = 1
} vos_kv_placement;

typedef enum {
    VOS_INF_ADMITTED = 0,
    VOS_INF_REFUSED = 1
} vos_inf_verdict_kind;

typedef enum {
    VOS_INF_FROM_RESIDENT_BANK = 0,
    VOS_INF_FETCH_REFUSED = 1
} vos_inf_fetch_kind;

typedef enum {
    VOS_INF_ROUTE_SOFTWARE_SERVER = 0,
    VOS_INF_ROUTE_MODULE_BROKER = 1,
    VOS_INF_ROUTE_REMOTE_ENDPOINT = 2
} vos_inf_route_dest;

typedef struct {
    uint64_t resident_bytes;
    uint64_t context_length;
    uint64_t format;
    uint64_t expert_count;
    uint64_t top_k;
    uint64_t kv_bytes_per_token;
} vos_inf_shape;

typedef struct {
    uint8_t w_resident_bytes;
    uint8_t w_context_length;
    uint8_t w_format;
    uint8_t w_expert_count;
    uint8_t w_top_k;
    uint8_t w_kv_bytes_per_token;
} vos_inf_widths;

typedef struct {
    uint64_t max_resident_bytes;
    uint64_t max_context_length;
    uint64_t admitted_formats[VOS_INF_MAX_ADMITTED_FORMATS];
    size_t admitted_formats_len;
    uint64_t max_expert_count;
    uint64_t fixed_top_k;
    uint64_t max_kv_bytes_per_token;
    uint64_t ceiling_grant;
} vos_inf_ceiling;

typedef struct {
    uint64_t dense_work_per_token;
    uint64_t expert_work_per_token;
    uint64_t fetch_penalty;
} vos_inf_costs;

typedef struct {
    const uint8_t *resident;
    size_t len;
} vos_inf_residency;

typedef struct {
    uint64_t slot;
    uint64_t workers[VOS_INF_MAX_WORKERS];
    size_t workers_len;
    uint64_t pool_bytes;
    uint64_t session_capacity;
} vos_inf_server;

typedef struct {
    uint64_t sessions_open;
} vos_inf_sessions;

typedef struct {
    const uint8_t *descriptor;
    size_t descriptor_len;
    uint64_t requested_tokens_per_second;
} vos_inf_request;

typedef struct {
    vos_inf_widths widths;
    vos_inf_ceiling ceiling;
    vos_inf_costs costs;
    vos_inf_residency residency;
    vos_kv_placement kv_placement;
} vos_inf_composition;

typedef struct {
    vos_inf_server server;
    vos_inf_sessions sessions;
    vos_inf_verdict_kind verdict;
    uint64_t admitted_rate;
    vos_inf_refusal refusal;
} vos_inf_step;

typedef struct {
    uint64_t grant_bytes_per_second;
    uint64_t bytes_per_token;
} vos_inf_member;

typedef struct {
    vos_inf_fetch_kind kind;
    uint64_t expert;
    vos_inf_refusal refusal;
} vos_inf_fetch;

/* M6.6-i: canonical fixed-width shape descriptor codec. */
int vos_inf_widths_valid(const vos_inf_widths *widths);
size_t vos_inf_schema_bytes(const vos_inf_widths *widths, int *ok);
int vos_inf_field_fits(uint8_t width, uint64_t value);
int vos_inf_shape_fits(const vos_inf_widths *widths, const vos_inf_shape *shape);
int vos_inf_encode_shape(const vos_inf_widths *widths, const vos_inf_shape *shape,
                         uint8_t *out, size_t out_cap, size_t *out_len);
int vos_inf_decode_shape(const vos_inf_widths *widths, const uint8_t *bytes,
                         size_t len, vos_inf_shape *out_shape);

/* M6.6-i: seven-term ceiling and session opening. */
vos_inf_refusal vos_inf_why_refused(const vos_inf_ceiling *ceiling,
                                    const vos_inf_shape *shape);
vos_inf_step vos_inf_opening(const vos_inf_composition *comp,
                             const vos_inf_server *srv,
                             vos_inf_sessions st,
                             const vos_inf_request *req);
vos_inf_step vos_inf_composition_opening(const vos_inf_composition *comp,
                                         const vos_inf_server *srv,
                                         vos_inf_sessions st,
                                         const vos_inf_request *req);

/* M6.7-i: finite residency prefix, fixed top-k routing, uniform work, storage fence. */
int vos_inf_all_experts_resident(const vos_inf_shape *shape,
                                 const vos_inf_residency *res);
int vos_inf_routing_ok(const vos_inf_shape *shape,
                       const uint64_t *route, size_t route_len);
int vos_inf_checked_routed_work(const vos_inf_shape *shape,
                                const vos_inf_costs *costs,
                                const vos_inf_residency *res,
                                const uint64_t *route, size_t route_len,
                                uint64_t *out_work);
vos_inf_fetch vos_inf_serve(const vos_inf_residency *res, uint64_t expert);
int vos_inf_dispatch(const uint8_t qualified[3], vos_inf_route_dest requested,
                     vos_inf_route_dest *out_served);

/* M6.8-i: bank-grant per-token traffic, integer rate, ensemble minimum. */
int vos_inf_per_token_bytes(const vos_inf_shape *shape,
                            vos_kv_placement placement,
                            uint64_t *out_bytes);
int vos_inf_admitted_rate(uint64_t grant_bytes_per_sec,
                          uint64_t per_token_bytes,
                          uint64_t *out_rate);
vos_inf_refusal vos_inf_grant_refusal(uint64_t grant_bytes_per_sec,
                                      uint64_t per_token_bytes,
                                      uint64_t requested_rate);
int vos_inf_ensemble_rate(const vos_inf_member *members,
                          size_t member_count,
                          uint64_t *out_rate);

#endif
