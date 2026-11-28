// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_REPLAY_RECORD_H
#define VOS_REPLAY_RECORD_H

#include <stddef.h>
#include <stdint.h>

#include "vos_crypto_core.h"

/*
 * Bounded, GC-free C17 deterministic-replay nondeterminism recorder,
 * HMAC-SHA256 commitment sealer seam, canonical wire + replay-record-v1 JSON
 * structural validators, and strict demand-cursor verifier for S6.
 */

enum {
    VOS_RR_DIGEST_BYTES = VOS_CRYPTO_DIGEST_BYTES,
    VOS_RR_KEY_BYTES = VOS_CRYPTO_KEY_BYTES_256,
    VOS_RR_MAX_BASE_ROOT_BYTES = 64u,
    VOS_RR_MAX_INTERFACES = 8u,
    VOS_RR_MAX_EVENTS = 16u,
    VOS_RR_MAX_PAYLOAD_BYTES = 64u,
    VOS_RR_WIRE_MAGIC_BYTES = 8u,
    VOS_RR_WIRE_EVENT_FIXED_BYTES = 84u,
    VOS_RR_MAX_WIRE_BYTES = 4096u,
    VOS_RR_MAX_JSON_BYTES = 8192u
};

enum vos_rr_source {
    VOS_RR_SRC_ENTROPY = 0u,
    VOS_RR_SRC_LINK_ADDRESS = 1u,
    VOS_RR_SRC_TIME_READ = 2u,
    VOS_RR_SRC_PHYSICAL_EVENT = 3u
};

enum vos_rr_payload_class {
    VOS_RR_CLASS_SECRET_COMMITMENT = 0u,
    VOS_RR_CLASS_PUBLIC_VERBATIM = 1u
};

enum vos_rr_status {
    VOS_RR_OK = 0,
    VOS_RR_ERR_INVALID_ARG = -1,
    VOS_RR_ERR_MALFORMED = -2,
    VOS_RR_ERR_TRAILING_BYTES = -3,
    VOS_RR_ERR_UNKNOWN_SCHEMA = -4,
    VOS_RR_ERR_BAD_SOURCE = -5,
    VOS_RR_ERR_UNKNOWN_INTERFACE = -6,
    VOS_RR_ERR_SOURCE_MISMATCH = -7,
    VOS_RR_ERR_CLASS_MISMATCH = -8,
    VOS_RR_ERR_BINDING_MISMATCH = -9,
    VOS_RR_ERR_COUNT_MISMATCH = -10,
    VOS_RR_ERR_SEQ_GAP = -11,
    VOS_RR_ERR_COORD_REGRESSION = -12,
    VOS_RR_ERR_RETIRE_REGRESSION = -13,
    VOS_RR_ERR_OVER_CAPACITY = -14,
    VOS_RR_ERR_PAYLOAD_EMPTY = -15,
    VOS_RR_ERR_PAYLOAD_OVER_LIMIT = -16,
    VOS_RR_ERR_PUBLIC_VALIDATION = -17,
    VOS_RR_ERR_REENTRANT = -18,
    VOS_RR_ERR_LATCHED_FAILURE = -19,
    VOS_RR_ERR_ALREADY_FINISHED = -20,
    VOS_RR_ERR_PRODUCER_FAILED = -21,
    VOS_RR_ERR_EXHAUSTED = -22,
    VOS_RR_ERR_TRAILING_EVENTS = -23,
    VOS_RR_ERR_DEMAND_MISMATCH = -24,
    VOS_RR_ERR_CRYPTO = -25
};

struct vos_rr_point {
    uint64_t slot;
    uint64_t core;
    uint64_t retire;
    uint64_t ordinal;
};

struct vos_rr_binding {
    uint32_t base_image_root_len;
    uint8_t base_image_root[VOS_RR_MAX_BASE_ROOT_BYTES];
    uint8_t composition[VOS_RR_DIGEST_BYTES];
    uint8_t input_trace[VOS_RR_DIGEST_BYTES];
};

struct vos_rr_limits {
    uint32_t max_body_bytes;
    uint32_t max_events;
};

struct vos_rr_interface {
    uint8_t id[VOS_RR_DIGEST_BYTES];
    uint32_t source;
    uint32_t max_payload_bytes;
};

typedef int (*vos_rr_public_validator_fn)(const uint8_t *payload,
                                          size_t len,
                                          void *ctx);

struct vos_rr_interface_entry {
    struct vos_rr_interface profile;
    vos_rr_public_validator_fn validator;
    void *validator_ctx;
};

struct vos_rr_event {
    uint64_t seq;
    struct vos_rr_point point;
    uint32_t source;
    uint32_t payload_class;
    uint8_t interface_id[VOS_RR_DIGEST_BYTES];
    uint32_t payload_len;
    uint8_t payload[VOS_RR_MAX_PAYLOAD_BYTES];
};

struct vos_rr_record {
    struct vos_rr_binding binding;
    uint32_t event_count;
    struct vos_rr_event events[VOS_RR_MAX_EVENTS];
};

typedef enum vos_rr_status (*vos_rr_produce_fn)(void *ctx,
                                                uint8_t *out_buf,
                                                size_t max_len,
                                                size_t *out_len,
                                                int *out_declined);

struct vos_rr_recorder {
    struct vos_rr_binding binding;
    struct vos_rr_limits limits;
    uint32_t interface_count;
    struct vos_rr_interface_entry interfaces[VOS_RR_MAX_INTERFACES];
    uint8_t seal_key[VOS_RR_KEY_BYTES];
    uint32_t event_count;
    struct vos_rr_event events[VOS_RR_MAX_EVENTS];
    size_t wire_bytes_used;
    uint32_t busy;
    uint32_t failed;
    uint32_t finished;
    uint32_t fault_routed;
};

struct vos_rr_cursor {
    struct vos_rr_record record;
    uint32_t next;
    uint32_t failed;
    uint32_t finished;
};

int vos_rr_source_is_valid(uint32_t source);

enum vos_rr_status vos_rr_classify_source(uint32_t source,
                                          enum vos_rr_payload_class *out_class);

int vos_rr_point_lt(const struct vos_rr_point *a,
                    const struct vos_rr_point *b);

enum vos_rr_status vos_rr_seal_entropy_draw(
    const uint8_t seal_key[VOS_RR_KEY_BYTES],
    const struct vos_rr_binding *binding,
    const struct vos_rr_point *point,
    const uint8_t interface_id[VOS_RR_DIGEST_BYTES],
    const uint8_t *raw_draw,
    size_t raw_draw_len,
    uint8_t out_commitment[VOS_RR_DIGEST_BYTES]);

enum vos_rr_status vos_rr_recorder_init(
    struct vos_rr_recorder *recorder,
    const struct vos_rr_binding *binding,
    const struct vos_rr_limits *limits,
    const struct vos_rr_interface_entry *interfaces,
    size_t interface_count,
    const uint8_t seal_key[VOS_RR_KEY_BYTES]);

enum vos_rr_status vos_rr_recorder_source_of(
    const struct vos_rr_recorder *recorder,
    const uint8_t interface_id[VOS_RR_DIGEST_BYTES],
    enum vos_rr_source *out_source);

void vos_rr_recorder_abort(struct vos_rr_recorder *recorder);

enum vos_rr_status vos_rr_recorder_record(
    struct vos_rr_recorder *recorder,
    const struct vos_rr_point *point,
    const uint8_t interface_id[VOS_RR_DIGEST_BYTES],
    vos_rr_produce_fn produce,
    void *produce_ctx,
    int *out_accepted,
    struct vos_rr_event *out_event);

enum vos_rr_status vos_rr_recorder_finish(
    struct vos_rr_recorder *recorder,
    const struct vos_rr_binding *expected_binding,
    uint32_t expected_events,
    uint8_t *out_wire,
    size_t out_cap,
    size_t *out_wire_len);

enum vos_rr_status vos_rr_encode_wire(
    const struct vos_rr_record *record,
    uint8_t *out_wire,
    size_t out_cap,
    size_t *out_wire_len);

enum vos_rr_status vos_rr_decode_wire(
    const uint8_t *wire,
    size_t wire_len,
    const struct vos_rr_binding *expected_binding,
    uint32_t expected_events,
    const struct vos_rr_limits *limits,
    const struct vos_rr_interface *interfaces,
    size_t interface_count,
    struct vos_rr_record *out_record);

enum vos_rr_status vos_rr_encode_json(
    const struct vos_rr_record *record,
    char *out_json,
    size_t out_cap,
    size_t *out_json_len);

enum vos_rr_status vos_rr_decode_json(
    const char *json,
    size_t json_len,
    const struct vos_rr_binding *expected_binding,
    uint32_t expected_events,
    const struct vos_rr_limits *limits,
    const struct vos_rr_interface *interfaces,
    size_t interface_count,
    struct vos_rr_record *out_record);

enum vos_rr_status vos_rr_cursor_init(
    struct vos_rr_cursor *cursor,
    const struct vos_rr_record *record,
    const struct vos_rr_binding *expected_binding,
    uint32_t expected_events,
    const struct vos_rr_limits *limits,
    const struct vos_rr_interface *interfaces,
    size_t interface_count);

void vos_rr_cursor_abort(struct vos_rr_cursor *cursor);

enum vos_rr_status vos_rr_cursor_consume(
    struct vos_rr_cursor *cursor,
    const struct vos_rr_point *point,
    enum vos_rr_source source,
    const uint8_t interface_id[VOS_RR_DIGEST_BYTES],
    struct vos_rr_event *out_event);

enum vos_rr_status vos_rr_cursor_finish(struct vos_rr_cursor *cursor);

#endif
