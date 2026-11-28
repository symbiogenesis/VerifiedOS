// SPDX-License-Identifier: Apache-2.0
#include "vos_replay_record.h"

#include <string.h>

static const uint8_t VOS_RR_WIRE_MAGIC[VOS_RR_WIRE_MAGIC_BYTES] = {
    'V', 'O', 'S', 'R', 'R', '0', '1', '\0'
};

static const char VOS_RR_SCHEMA_V1[] = "replay-record-v1";

static void secure_zero(uint8_t *dst, size_t len)
{
    if (dst == NULL) {
        return;
    }
    volatile uint8_t *p = dst;
    for (size_t i = 0u; i < len; ++i) {
        p[i] = 0u;
    }
}

static void put_le32(uint8_t *dst, uint32_t v)
{
    for (uint32_t i = 0u; i < 4u; ++i) {
        dst[i] = (uint8_t)(v >> (8u * i));
    }
}

static void put_le64(uint8_t *dst, uint64_t v)
{
    for (uint32_t i = 0u; i < 8u; ++i) {
        dst[i] = (uint8_t)(v >> (8u * i));
    }
}

static uint32_t get_le32(const uint8_t *src)
{
    uint32_t v = 0u;
    for (uint32_t i = 0u; i < 4u; ++i) {
        v |= ((uint32_t)src[i]) << (8u * i);
    }
    return v;
}

static uint64_t get_le64(const uint8_t *src)
{
    uint64_t v = 0u;
    for (uint32_t i = 0u; i < 8u; ++i) {
        v |= ((uint64_t)src[i]) << (8u * i);
    }
    return v;
}

static int bytes_equal(const uint8_t *a, const uint8_t *b, size_t len)
{
    uint8_t diff = 0u;
    for (size_t i = 0u; i < len; ++i) {
        diff |= (uint8_t)(a[i] ^ b[i]);
    }
    return diff == 0u;
}

static size_t wire_header_bytes(const struct vos_rr_binding *binding)
{
    return (size_t)VOS_RR_WIRE_MAGIC_BYTES + 4u +
           (size_t)binding->base_image_root_len +
           (size_t)VOS_RR_DIGEST_BYTES + (size_t)VOS_RR_DIGEST_BYTES + 4u;
}

static int binding_is_valid(const struct vos_rr_binding *binding)
{
    return binding != NULL &&
           binding->base_image_root_len >= 1u &&
           binding->base_image_root_len <= VOS_RR_MAX_BASE_ROOT_BYTES;
}

static int bindings_equal(const struct vos_rr_binding *a,
                          const struct vos_rr_binding *b)
{
    if (!binding_is_valid(a) || !binding_is_valid(b)) {
        return 0;
    }
    if (a->base_image_root_len != b->base_image_root_len) {
        return 0;
    }
    return bytes_equal(a->base_image_root, b->base_image_root, a->base_image_root_len) &&
           bytes_equal(a->composition, b->composition, VOS_RR_DIGEST_BYTES) &&
           bytes_equal(a->input_trace, b->input_trace, VOS_RR_DIGEST_BYTES);
}

static int points_equal(const struct vos_rr_point *a,
                        const struct vos_rr_point *b)
{
    return a->slot == b->slot &&
           a->core == b->core &&
           a->retire == b->retire &&
           a->ordinal == b->ordinal;
}

int vos_rr_source_is_valid(uint32_t source)
{
    return source == (uint32_t)VOS_RR_SRC_ENTROPY ||
           source == (uint32_t)VOS_RR_SRC_LINK_ADDRESS ||
           source == (uint32_t)VOS_RR_SRC_TIME_READ ||
           source == (uint32_t)VOS_RR_SRC_PHYSICAL_EVENT;
}

enum vos_rr_status vos_rr_classify_source(uint32_t source,
                                          enum vos_rr_payload_class *out_class)
{
    if (out_class == NULL) {
        return VOS_RR_ERR_INVALID_ARG;
    }
    if (!vos_rr_source_is_valid(source)) {
        return VOS_RR_ERR_BAD_SOURCE;
    }
    if (source == (uint32_t)VOS_RR_SRC_ENTROPY) {
        *out_class = VOS_RR_CLASS_SECRET_COMMITMENT;
    } else {
        *out_class = VOS_RR_CLASS_PUBLIC_VERBATIM;
    }
    return VOS_RR_OK;
}

int vos_rr_point_lt(const struct vos_rr_point *a,
                    const struct vos_rr_point *b)
{
    if (a == NULL || b == NULL) {
        return 0;
    }
    if (a->slot != b->slot) {
        return a->slot < b->slot;
    }
    if (a->core != b->core) {
        return a->core < b->core;
    }
    if (a->retire != b->retire) {
        return a->retire < b->retire;
    }
    return a->ordinal < b->ordinal;
}

enum vos_rr_status vos_rr_seal_entropy_draw(
    const uint8_t seal_key[VOS_RR_KEY_BYTES],
    const struct vos_rr_binding *binding,
    const struct vos_rr_point *point,
    const uint8_t interface_id[VOS_RR_DIGEST_BYTES],
    const uint8_t *raw_draw,
    size_t raw_draw_len,
    uint8_t out_commitment[VOS_RR_DIGEST_BYTES])
{
    if (seal_key == NULL || !binding_is_valid(binding) || point == NULL ||
        interface_id == NULL || raw_draw == NULL || out_commitment == NULL ||
        raw_draw_len == 0u || raw_draw_len > VOS_RR_MAX_PAYLOAD_BYTES) {
        return VOS_RR_ERR_INVALID_ARG;
    }
    static const uint8_t domain_tag[8] = {'V', 'O', 'S', 'R', 'R', 'C', 'M', '1'};
    uint8_t msg[8u + 32u + 32u + 32u + 32u + 4u + VOS_RR_MAX_PAYLOAD_BYTES];
    size_t off = 0u;
    memcpy(msg + off, domain_tag, 8u);
    off += 8u;
    memcpy(msg + off, binding->composition, VOS_RR_DIGEST_BYTES);
    off += VOS_RR_DIGEST_BYTES;
    memcpy(msg + off, binding->input_trace, VOS_RR_DIGEST_BYTES);
    off += VOS_RR_DIGEST_BYTES;
    put_le64(msg + off, point->slot);
    put_le64(msg + off + 8u, point->core);
    put_le64(msg + off + 16u, point->retire);
    put_le64(msg + off + 24u, point->ordinal);
    off += 32u;
    memcpy(msg + off, interface_id, VOS_RR_DIGEST_BYTES);
    off += VOS_RR_DIGEST_BYTES;
    put_le32(msg + off, (uint32_t)raw_draw_len);
    off += 4u;
    memcpy(msg + off, raw_draw, raw_draw_len);
    off += raw_draw_len;

    const int ok = vos_hmac_sha256(seal_key, VOS_RR_KEY_BYTES,
                                   msg, off, out_commitment);
    secure_zero(msg, sizeof(msg));
    if (!ok) {
        secure_zero(out_commitment, VOS_RR_DIGEST_BYTES);
        return VOS_RR_ERR_CRYPTO;
    }
    return VOS_RR_OK;
}

static const struct vos_rr_interface *find_interface_profile(
    const struct vos_rr_interface *interfaces,
    size_t interface_count,
    const uint8_t id[VOS_RR_DIGEST_BYTES])
{
    for (size_t i = 0u; i < interface_count; ++i) {
        if (bytes_equal(interfaces[i].id, id, VOS_RR_DIGEST_BYTES)) {
            return &interfaces[i];
        }
    }
    return NULL;
}

static const struct vos_rr_interface_entry *find_recorder_interface(
    const struct vos_rr_recorder *recorder,
    const uint8_t id[VOS_RR_DIGEST_BYTES])
{
    for (uint32_t i = 0u; i < recorder->interface_count; ++i) {
        if (bytes_equal(recorder->interfaces[i].profile.id, id, VOS_RR_DIGEST_BYTES)) {
            return &recorder->interfaces[i];
        }
    }
    return NULL;
}

static int check_limits_and_interfaces(
    const struct vos_rr_limits *limits,
    const struct vos_rr_interface *interfaces,
    size_t interface_count)
{
    if (limits == NULL || limits->max_body_bytes == 0u ||
        limits->max_body_bytes > VOS_RR_MAX_WIRE_BYTES ||
        limits->max_events > VOS_RR_MAX_EVENTS) {
        return 0;
    }
    if (interfaces == NULL || interface_count == 0u ||
        interface_count > VOS_RR_MAX_INTERFACES) {
        return 0;
    }
    for (size_t i = 0u; i < interface_count; ++i) {
        if (!vos_rr_source_is_valid(interfaces[i].source) ||
            interfaces[i].max_payload_bytes == 0u ||
            interfaces[i].max_payload_bytes > VOS_RR_MAX_PAYLOAD_BYTES) {
            return 0;
        }
        if (interfaces[i].source == (uint32_t)VOS_RR_SRC_ENTROPY &&
            interfaces[i].max_payload_bytes < VOS_RR_DIGEST_BYTES) {
            return 0;
        }
        for (size_t j = i + 1u; j < interface_count; ++j) {
            if (bytes_equal(interfaces[i].id, interfaces[j].id, VOS_RR_DIGEST_BYTES)) {
                return 0;
            }
        }
    }
    return 1;
}

static int check_core_retire_monotonic(const struct vos_rr_event *events,
                                       uint32_t count,
                                       const struct vos_rr_point *next_pt)
{
    for (uint32_t i = 0u; i < count; ++i) {
        if (events[i].point.core == next_pt->core &&
            next_pt->retire < events[i].point.retire) {
            return 0;
        }
    }
    return 1;
}

static enum vos_rr_status validate_record_against(
    const struct vos_rr_record *record,
    const struct vos_rr_binding *expected_binding,
    uint32_t expected_events,
    const struct vos_rr_limits *limits,
    const struct vos_rr_interface *interfaces,
    size_t interface_count)
{
    if (record == NULL || !binding_is_valid(expected_binding) ||
        !check_limits_and_interfaces(limits, interfaces, interface_count)) {
        return VOS_RR_ERR_INVALID_ARG;
    }
    if (expected_events > limits->max_events) {
        return VOS_RR_ERR_OVER_CAPACITY;
    }
    if (!bindings_equal(&record->binding, expected_binding)) {
        return VOS_RR_ERR_BINDING_MISMATCH;
    }
    if (record->event_count != expected_events) {
        return VOS_RR_ERR_COUNT_MISMATCH;
    }
    size_t total_wire = wire_header_bytes(&record->binding);
    if (total_wire > limits->max_body_bytes) {
        return VOS_RR_ERR_OVER_CAPACITY;
    }

    for (uint32_t i = 0u; i < record->event_count; ++i) {
        const struct vos_rr_event *ev = &record->events[i];
        if (ev->seq != (uint64_t)i) {
            return VOS_RR_ERR_SEQ_GAP;
        }
        if (i > 0u && !vos_rr_point_lt(&record->events[i - 1u].point, &ev->point)) {
            return VOS_RR_ERR_COORD_REGRESSION;
        }
        if (!check_core_retire_monotonic(record->events, i, &ev->point)) {
            return VOS_RR_ERR_RETIRE_REGRESSION;
        }
        if (!vos_rr_source_is_valid(ev->source)) {
            return VOS_RR_ERR_BAD_SOURCE;
        }
        const struct vos_rr_interface *prof =
            find_interface_profile(interfaces, interface_count, ev->interface_id);
        if (prof == NULL) {
            return VOS_RR_ERR_UNKNOWN_INTERFACE;
        }
        if (prof->source != ev->source) {
            return VOS_RR_ERR_SOURCE_MISMATCH;
        }
        enum vos_rr_payload_class expected_cls = VOS_RR_CLASS_PUBLIC_VERBATIM;
        (void)vos_rr_classify_source(ev->source, &expected_cls);
        if (ev->payload_class != (uint32_t)expected_cls) {
            return VOS_RR_ERR_CLASS_MISMATCH;
        }
        if (ev->payload_len == 0u) {
            return VOS_RR_ERR_PAYLOAD_EMPTY;
        }
        if (ev->payload_len > prof->max_payload_bytes) {
            return VOS_RR_ERR_PAYLOAD_OVER_LIMIT;
        }
        const size_t ev_bytes =
            (size_t)VOS_RR_WIRE_EVENT_FIXED_BYTES + (size_t)ev->payload_len;
        if (ev_bytes > (size_t)limits->max_body_bytes - total_wire) {
            return VOS_RR_ERR_OVER_CAPACITY;
        }
        total_wire += ev_bytes;
    }
    return VOS_RR_OK;
}

enum vos_rr_status vos_rr_recorder_init(
    struct vos_rr_recorder *recorder,
    const struct vos_rr_binding *binding,
    const struct vos_rr_limits *limits,
    const struct vos_rr_interface_entry *interfaces,
    size_t interface_count,
    const uint8_t seal_key[VOS_RR_KEY_BYTES])
{
    if (recorder == NULL) {
        return VOS_RR_ERR_INVALID_ARG;
    }
    memset(recorder, 0, sizeof(*recorder));
    if (!binding_is_valid(binding) || limits == NULL ||
        interfaces == NULL || seal_key == NULL ||
        interface_count == 0u || interface_count > VOS_RR_MAX_INTERFACES) {
        recorder->failed = 1u;
        recorder->fault_routed = 1u;
        return VOS_RR_ERR_INVALID_ARG;
    }

    struct vos_rr_interface profiles[VOS_RR_MAX_INTERFACES];
    for (size_t i = 0u; i < interface_count; ++i) {
        profiles[i] = interfaces[i].profile;
        if (interfaces[i].profile.source == (uint32_t)VOS_RR_SRC_ENTROPY) {
            if (interfaces[i].validator != NULL) {
                recorder->failed = 1u;
                recorder->fault_routed = 1u;
                return VOS_RR_ERR_INVALID_ARG;
            }
        } else if (interfaces[i].validator == NULL) {
            recorder->failed = 1u;
            recorder->fault_routed = 1u;
            return VOS_RR_ERR_PUBLIC_VALIDATION;
        }
    }
    if (!check_limits_and_interfaces(limits, profiles, interface_count)) {
        recorder->failed = 1u;
        recorder->fault_routed = 1u;
        return VOS_RR_ERR_INVALID_ARG;
    }
    const size_t base_bytes = wire_header_bytes(binding);
    if (base_bytes > limits->max_body_bytes) {
        recorder->failed = 1u;
        recorder->fault_routed = 1u;
        return VOS_RR_ERR_OVER_CAPACITY;
    }

    recorder->binding = *binding;
    recorder->limits = *limits;
    recorder->interface_count = (uint32_t)interface_count;
    for (size_t i = 0u; i < interface_count; ++i) {
        recorder->interfaces[i] = interfaces[i];
    }
    memcpy(recorder->seal_key, seal_key, VOS_RR_KEY_BYTES);
    recorder->wire_bytes_used = base_bytes;
    return VOS_RR_OK;
}

enum vos_rr_status vos_rr_recorder_source_of(
    const struct vos_rr_recorder *recorder,
    const uint8_t interface_id[VOS_RR_DIGEST_BYTES],
    enum vos_rr_source *out_source)
{
    if (recorder == NULL || interface_id == NULL || out_source == NULL) {
        return VOS_RR_ERR_INVALID_ARG;
    }
    const struct vos_rr_interface_entry *entry =
        find_recorder_interface(recorder, interface_id);
    if (entry == NULL) {
        return VOS_RR_ERR_UNKNOWN_INTERFACE;
    }
    *out_source = (enum vos_rr_source)entry->profile.source;
    return VOS_RR_OK;
}

void vos_rr_recorder_abort(struct vos_rr_recorder *recorder)
{
    if (recorder == NULL) {
        return;
    }
    recorder->failed = 1u;
    recorder->fault_routed = 1u;
}

static enum vos_rr_status recorder_check_ready(struct vos_rr_recorder *recorder)
{
    if (recorder->busy != 0u) {
        recorder->failed = 1u;
        recorder->fault_routed = 1u;
        return VOS_RR_ERR_REENTRANT;
    }
    if (recorder->failed != 0u) {
        recorder->fault_routed = 1u;
        return VOS_RR_ERR_LATCHED_FAILURE;
    }
    if (recorder->finished != 0u) {
        return VOS_RR_ERR_ALREADY_FINISHED;
    }
    return VOS_RR_OK;
}

static enum vos_rr_status recorder_fail(struct vos_rr_recorder *recorder,
                                        enum vos_rr_status status)
{
    recorder->failed = 1u;
    recorder->fault_routed = 1u;
    return status;
}

enum vos_rr_status vos_rr_recorder_record(
    struct vos_rr_recorder *recorder,
    const struct vos_rr_point *point,
    const uint8_t interface_id[VOS_RR_DIGEST_BYTES],
    vos_rr_produce_fn produce,
    void *produce_ctx,
    int *out_accepted,
    struct vos_rr_event *out_event)
{
    if (out_accepted != NULL) {
        *out_accepted = 0;
    }
    if (out_event != NULL) {
        memset(out_event, 0, sizeof(*out_event));
    }
    if (recorder == NULL) {
        return VOS_RR_ERR_INVALID_ARG;
    }
    const enum vos_rr_status ready = recorder_check_ready(recorder);
    if (ready != VOS_RR_OK) {
        return ready;
    }
    if (point == NULL || interface_id == NULL || produce == NULL) {
        return recorder_fail(recorder, VOS_RR_ERR_INVALID_ARG);
    }

    const struct vos_rr_interface_entry *entry =
        find_recorder_interface(recorder, interface_id);
    if (entry == NULL) {
        return recorder_fail(recorder, VOS_RR_ERR_UNKNOWN_INTERFACE);
    }
    if (recorder->event_count > 0u &&
        !vos_rr_point_lt(&recorder->events[recorder->event_count - 1u].point, point)) {
        return recorder_fail(recorder, VOS_RR_ERR_COORD_REGRESSION);
    }
    if (!check_core_retire_monotonic(recorder->events, recorder->event_count, point)) {
        return recorder_fail(recorder, VOS_RR_ERR_RETIRE_REGRESSION);
    }
    if (recorder->event_count >= recorder->limits.max_events) {
        return recorder_fail(recorder, VOS_RR_ERR_OVER_CAPACITY);
    }

    const size_t worst_event_bytes =
        (size_t)VOS_RR_WIRE_EVENT_FIXED_BYTES +
        (size_t)entry->profile.max_payload_bytes;
    if (worst_event_bytes > (size_t)recorder->limits.max_body_bytes - recorder->wire_bytes_used) {
        return recorder_fail(recorder, VOS_RR_ERR_OVER_CAPACITY);
    }

    uint8_t scratch[VOS_RR_MAX_PAYLOAD_BYTES];
    secure_zero(scratch, sizeof(scratch));
    size_t produced_len = 0u;
    int declined = 0;
    const size_t produce_limit =
        (entry->profile.source == (uint32_t)VOS_RR_SRC_ENTROPY)
            ? (size_t)VOS_RR_MAX_PAYLOAD_BYTES
            : (size_t)entry->profile.max_payload_bytes;

    recorder->busy = 1u;
    const enum vos_rr_status prod_status =
        produce(produce_ctx, scratch, produce_limit, &produced_len, &declined);
    recorder->busy = 0u;

    if (recorder->failed != 0u) {
        secure_zero(scratch, sizeof(scratch));
        recorder->fault_routed = 1u;
        return VOS_RR_ERR_REENTRANT;
    }
    if (prod_status != VOS_RR_OK) {
        secure_zero(scratch, sizeof(scratch));
        return recorder_fail(recorder, VOS_RR_ERR_PRODUCER_FAILED);
    }
    if (declined != 0) {
        secure_zero(scratch, sizeof(scratch));
        return VOS_RR_OK;
    }
    if (produced_len == 0u) {
        secure_zero(scratch, sizeof(scratch));
        return recorder_fail(recorder, VOS_RR_ERR_PAYLOAD_EMPTY);
    }
    if (produced_len > produce_limit) {
        secure_zero(scratch, sizeof(scratch));
        return recorder_fail(recorder, VOS_RR_ERR_PAYLOAD_OVER_LIMIT);
    }

    struct vos_rr_event ev;
    memset(&ev, 0, sizeof(ev));
    ev.seq = (uint64_t)recorder->event_count;
    ev.point = *point;
    ev.source = entry->profile.source;
    enum vos_rr_payload_class pclass = VOS_RR_CLASS_PUBLIC_VERBATIM;
    (void)vos_rr_classify_source(ev.source, &pclass);
    ev.payload_class = (uint32_t)pclass;
    memcpy(ev.interface_id, entry->profile.id, VOS_RR_DIGEST_BYTES);

    if (entry->profile.source == (uint32_t)VOS_RR_SRC_ENTROPY) {
        const enum vos_rr_status seal_st = vos_rr_seal_entropy_draw(
            recorder->seal_key, &recorder->binding, point,
            entry->profile.id, scratch, produced_len, ev.payload);
        secure_zero(scratch, sizeof(scratch));
        if (seal_st != VOS_RR_OK) {
            secure_zero((uint8_t *)&ev, sizeof(ev));
            return recorder_fail(recorder, seal_st);
        }
        ev.payload_len = VOS_RR_DIGEST_BYTES;
        if (ev.payload_len > entry->profile.max_payload_bytes) {
            secure_zero((uint8_t *)&ev, sizeof(ev));
            return recorder_fail(recorder, VOS_RR_ERR_PAYLOAD_OVER_LIMIT);
        }
    } else {
        recorder->busy = 1u;
        const int valid_pub =
            entry->validator(scratch, produced_len, entry->validator_ctx);
        recorder->busy = 0u;
        if (recorder->failed != 0u) {
            secure_zero(scratch, sizeof(scratch));
            recorder->fault_routed = 1u;
            return VOS_RR_ERR_REENTRANT;
        }
        if (valid_pub == 0) {
            secure_zero(scratch, sizeof(scratch));
            return recorder_fail(recorder, VOS_RR_ERR_PUBLIC_VALIDATION);
        }
        memcpy(ev.payload, scratch, produced_len);
        ev.payload_len = (uint32_t)produced_len;
        secure_zero(scratch, sizeof(scratch));
    }

    const size_t actual_event_bytes =
        (size_t)VOS_RR_WIRE_EVENT_FIXED_BYTES + (size_t)ev.payload_len;
    if (actual_event_bytes > (size_t)recorder->limits.max_body_bytes - recorder->wire_bytes_used) {
        secure_zero((uint8_t *)&ev, sizeof(ev));
        return recorder_fail(recorder, VOS_RR_ERR_OVER_CAPACITY);
    }

    recorder->events[recorder->event_count] = ev;
    recorder->event_count += 1u;
    recorder->wire_bytes_used += actual_event_bytes;
    if (out_accepted != NULL) {
        *out_accepted = 1;
    }
    if (out_event != NULL) {
        *out_event = ev;
    }
    return VOS_RR_OK;
}

enum vos_rr_status vos_rr_recorder_finish(
    struct vos_rr_recorder *recorder,
    const struct vos_rr_binding *expected_binding,
    uint32_t expected_events,
    uint8_t *out_wire,
    size_t out_cap,
    size_t *out_wire_len)
{
    if (out_wire_len != NULL) {
        *out_wire_len = 0u;
    }
    if (recorder == NULL) {
        return VOS_RR_ERR_INVALID_ARG;
    }
    const enum vos_rr_status ready = recorder_check_ready(recorder);
    if (ready != VOS_RR_OK) {
        return ready;
    }
    if (expected_binding == NULL || out_wire == NULL || out_wire_len == NULL) {
        return recorder_fail(recorder, VOS_RR_ERR_INVALID_ARG);
    }

    struct vos_rr_record tmp;
    memset(&tmp, 0, sizeof(tmp));
    tmp.binding = recorder->binding;
    tmp.event_count = recorder->event_count;
    for (uint32_t i = 0u; i < recorder->event_count; ++i) {
        tmp.events[i] = recorder->events[i];
    }

    size_t wire_len = 0u;
    const enum vos_rr_status enc_st =
        vos_rr_encode_wire(&tmp, out_wire, out_cap, &wire_len);
    if (enc_st != VOS_RR_OK) {
        return recorder_fail(recorder, enc_st);
    }

    struct vos_rr_interface profiles[VOS_RR_MAX_INTERFACES];
    for (uint32_t i = 0u; i < recorder->interface_count; ++i) {
        profiles[i] = recorder->interfaces[i].profile;
    }
    struct vos_rr_record verified;
    const enum vos_rr_status dec_st = vos_rr_decode_wire(
        out_wire, wire_len, expected_binding, expected_events,
        &recorder->limits, profiles, recorder->interface_count, &verified);
    if (dec_st != VOS_RR_OK) {
        secure_zero(out_wire, wire_len);
        return recorder_fail(recorder, dec_st);
    }

    recorder->finished = 1u;
    *out_wire_len = wire_len;
    return VOS_RR_OK;
}

enum vos_rr_status vos_rr_encode_wire(
    const struct vos_rr_record *record,
    uint8_t *out_wire,
    size_t out_cap,
    size_t *out_wire_len)
{
    if (out_wire_len != NULL) {
        *out_wire_len = 0u;
    }
    if (record == NULL || out_wire == NULL || out_wire_len == NULL ||
        !binding_is_valid(&record->binding) ||
        record->event_count > VOS_RR_MAX_EVENTS) {
        return VOS_RR_ERR_INVALID_ARG;
    }

    size_t need = wire_header_bytes(&record->binding);
    for (uint32_t i = 0u; i < record->event_count; ++i) {
        if (record->events[i].payload_len == 0u ||
            record->events[i].payload_len > VOS_RR_MAX_PAYLOAD_BYTES) {
            return VOS_RR_ERR_INVALID_ARG;
        }
        need += (size_t)VOS_RR_WIRE_EVENT_FIXED_BYTES +
                (size_t)record->events[i].payload_len;
    }
    if (need > out_cap) {
        return VOS_RR_ERR_OVER_CAPACITY;
    }

    size_t off = 0u;
    memcpy(out_wire + off, VOS_RR_WIRE_MAGIC, VOS_RR_WIRE_MAGIC_BYTES);
    off += VOS_RR_WIRE_MAGIC_BYTES;
    put_le32(out_wire + off, record->binding.base_image_root_len);
    off += 4u;
    memcpy(out_wire + off, record->binding.base_image_root,
           record->binding.base_image_root_len);
    off += record->binding.base_image_root_len;
    memcpy(out_wire + off, record->binding.composition, VOS_RR_DIGEST_BYTES);
    off += VOS_RR_DIGEST_BYTES;
    memcpy(out_wire + off, record->binding.input_trace, VOS_RR_DIGEST_BYTES);
    off += VOS_RR_DIGEST_BYTES;
    put_le32(out_wire + off, record->event_count);
    off += 4u;

    for (uint32_t i = 0u; i < record->event_count; ++i) {
        const struct vos_rr_event *ev = &record->events[i];
        put_le64(out_wire + off, ev->seq);
        put_le64(out_wire + off + 8u, ev->point.slot);
        put_le64(out_wire + off + 16u, ev->point.core);
        put_le64(out_wire + off + 24u, ev->point.retire);
        put_le64(out_wire + off + 32u, ev->point.ordinal);
        put_le32(out_wire + off + 40u, ev->source);
        put_le32(out_wire + off + 44u, ev->payload_class);
        memcpy(out_wire + off + 48u, ev->interface_id, VOS_RR_DIGEST_BYTES);
        put_le32(out_wire + off + 80u, ev->payload_len);
        off += VOS_RR_WIRE_EVENT_FIXED_BYTES;
        memcpy(out_wire + off, ev->payload, ev->payload_len);
        off += ev->payload_len;
    }

    *out_wire_len = off;
    return VOS_RR_OK;
}

enum vos_rr_status vos_rr_decode_wire(
    const uint8_t *wire,
    size_t wire_len,
    const struct vos_rr_binding *expected_binding,
    uint32_t expected_events,
    const struct vos_rr_limits *limits,
    const struct vos_rr_interface *interfaces,
    size_t interface_count,
    struct vos_rr_record *out_record)
{
    if (out_record == NULL) {
        return VOS_RR_ERR_INVALID_ARG;
    }
    memset(out_record, 0, sizeof(*out_record));
    if (wire == NULL || !binding_is_valid(expected_binding) ||
        !check_limits_and_interfaces(limits, interfaces, interface_count)) {
        return VOS_RR_ERR_INVALID_ARG;
    }
    if (expected_events > limits->max_events) {
        return VOS_RR_ERR_OVER_CAPACITY;
    }
    if (wire_len > limits->max_body_bytes) {
        return VOS_RR_ERR_OVER_CAPACITY;
    }
    if (wire_len < (size_t)VOS_RR_WIRE_MAGIC_BYTES + 4u) {
        return VOS_RR_ERR_MALFORMED;
    }
    if (!bytes_equal(wire, VOS_RR_WIRE_MAGIC, VOS_RR_WIRE_MAGIC_BYTES)) {
        return VOS_RR_ERR_UNKNOWN_SCHEMA;
    }

    size_t off = VOS_RR_WIRE_MAGIC_BYTES;
    const uint32_t root_len = get_le32(wire + off);
    off += 4u;
    if (root_len == 0u || root_len > VOS_RR_MAX_BASE_ROOT_BYTES) {
        return VOS_RR_ERR_MALFORMED;
    }
    if (wire_len - off < (size_t)root_len + 2u * VOS_RR_DIGEST_BYTES + 4u) {
        return VOS_RR_ERR_MALFORMED;
    }

    struct vos_rr_record parsed;
    memset(&parsed, 0, sizeof(parsed));
    parsed.binding.base_image_root_len = root_len;
    memcpy(parsed.binding.base_image_root, wire + off, root_len);
    off += root_len;
    memcpy(parsed.binding.composition, wire + off, VOS_RR_DIGEST_BYTES);
    off += VOS_RR_DIGEST_BYTES;
    memcpy(parsed.binding.input_trace, wire + off, VOS_RR_DIGEST_BYTES);
    off += VOS_RR_DIGEST_BYTES;
    parsed.event_count = get_le32(wire + off);
    off += 4u;

    if (parsed.event_count > VOS_RR_MAX_EVENTS ||
        parsed.event_count > limits->max_events) {
        return VOS_RR_ERR_OVER_CAPACITY;
    }

    for (uint32_t i = 0u; i < parsed.event_count; ++i) {
        if (wire_len - off < VOS_RR_WIRE_EVENT_FIXED_BYTES) {
            return VOS_RR_ERR_MALFORMED;
        }
        struct vos_rr_event *ev = &parsed.events[i];
        ev->seq = get_le64(wire + off);
        ev->point.slot = get_le64(wire + off + 8u);
        ev->point.core = get_le64(wire + off + 16u);
        ev->point.retire = get_le64(wire + off + 24u);
        ev->point.ordinal = get_le64(wire + off + 32u);
        ev->source = get_le32(wire + off + 40u);
        ev->payload_class = get_le32(wire + off + 44u);
        memcpy(ev->interface_id, wire + off + 48u, VOS_RR_DIGEST_BYTES);
        ev->payload_len = get_le32(wire + off + 80u);
        off += VOS_RR_WIRE_EVENT_FIXED_BYTES;

        if (ev->payload_len == 0u) {
            return VOS_RR_ERR_PAYLOAD_EMPTY;
        }
        if (ev->payload_len > VOS_RR_MAX_PAYLOAD_BYTES) {
            return VOS_RR_ERR_PAYLOAD_OVER_LIMIT;
        }
        if (wire_len - off < ev->payload_len) {
            return VOS_RR_ERR_MALFORMED;
        }
        memcpy(ev->payload, wire + off, ev->payload_len);
        off += ev->payload_len;
    }

    if (off != wire_len) {
        return VOS_RR_ERR_TRAILING_BYTES;
    }

    const enum vos_rr_status val_st = validate_record_against(
        &parsed, expected_binding, expected_events,
        limits, interfaces, interface_count);
    if (val_st != VOS_RR_OK) {
        return val_st;
    }

    *out_record = parsed;
    return VOS_RR_OK;
}

/* =========================================================================
 * Bounded compact replay-record-v1 JSON emitter and structural validator.
 * ========================================================================= */

struct json_writer {
    char *buf;
    size_t cap;
    size_t len;
};

static int jw_put_bytes(struct json_writer *jw, const char *s, size_t n)
{
    if (n > jw->cap - jw->len) {
        return 0;
    }
    memcpy(jw->buf + jw->len, s, n);
    jw->len += n;
    return 1;
}

static int jw_put_str(struct json_writer *jw, const char *s)
{
    return jw_put_bytes(jw, s, strlen(s));
}

static int jw_put_hex(struct json_writer *jw, const uint8_t *data, size_t n)
{
    static const char hex_digits[] = "0123456789abcdef";
    if (n > (jw->cap - jw->len) / 2u) {
        return 0;
    }
    for (size_t i = 0u; i < n; ++i) {
        jw->buf[jw->len++] = hex_digits[(data[i] >> 4u) & 0x0Fu];
        jw->buf[jw->len++] = hex_digits[data[i] & 0x0Fu];
    }
    return 1;
}

static int jw_put_u64(struct json_writer *jw, uint64_t val)
{
    char tmp[24];
    size_t idx = 0u;
    if (val == 0u) {
        return jw_put_bytes(jw, "0", 1u);
    }
    while (val > 0u) {
        tmp[idx++] = (char)('0' + (char)(val % 10u));
        val /= 10u;
    }
    if (idx > jw->cap - jw->len) {
        return 0;
    }
    while (idx > 0u) {
        jw->buf[jw->len++] = tmp[--idx];
    }
    return 1;
}

static const char *source_name(uint32_t source)
{
    switch (source) {
    case VOS_RR_SRC_ENTROPY:
        return "entropy";
    case VOS_RR_SRC_LINK_ADDRESS:
        return "link_address";
    case VOS_RR_SRC_TIME_READ:
        return "time_read";
    case VOS_RR_SRC_PHYSICAL_EVENT:
        return "physical_event";
    default:
        return NULL;
    }
}

enum vos_rr_status vos_rr_encode_json(
    const struct vos_rr_record *record,
    char *out_json,
    size_t out_cap,
    size_t *out_json_len)
{
    if (out_json_len != NULL) {
        *out_json_len = 0u;
    }
    if (record == NULL || out_json == NULL || out_json_len == NULL ||
        !binding_is_valid(&record->binding) ||
        record->event_count > VOS_RR_MAX_EVENTS) {
        return VOS_RR_ERR_INVALID_ARG;
    }

    struct json_writer jw = {out_json, out_cap, 0u};
    if (!jw_put_str(&jw, "{\"schema\":\"replay-record-v1\",\"binding\":{\"base_image_root\":\"") ||
        !jw_put_hex(&jw, record->binding.base_image_root, record->binding.base_image_root_len) ||
        !jw_put_str(&jw, "\",\"composition\":\"") ||
        !jw_put_hex(&jw, record->binding.composition, VOS_RR_DIGEST_BYTES) ||
        !jw_put_str(&jw, "\",\"input_trace\":\"") ||
        !jw_put_hex(&jw, record->binding.input_trace, VOS_RR_DIGEST_BYTES) ||
        !jw_put_str(&jw, "\"},\"events\":[")) {
        return VOS_RR_ERR_OVER_CAPACITY;
    }

    for (uint32_t i = 0u; i < record->event_count; ++i) {
        const struct vos_rr_event *ev = &record->events[i];
        const char *sname = source_name(ev->source);
        if (sname == NULL || ev->payload_len == 0u ||
            ev->payload_len > VOS_RR_MAX_PAYLOAD_BYTES) {
            return VOS_RR_ERR_INVALID_ARG;
        }
        const char *pfield =
            (ev->source == (uint32_t)VOS_RR_SRC_ENTROPY) ? "sealed_commitment" : "value";
        if (i > 0u && !jw_put_str(&jw, ",")) {
            return VOS_RR_ERR_OVER_CAPACITY;
        }
        if (!jw_put_str(&jw, "{\"seq\":") ||
            !jw_put_u64(&jw, ev->seq) ||
            !jw_put_str(&jw, ",\"point\":{\"slot\":") ||
            !jw_put_u64(&jw, ev->point.slot) ||
            !jw_put_str(&jw, ",\"core\":") ||
            !jw_put_u64(&jw, ev->point.core) ||
            !jw_put_str(&jw, ",\"retire\":") ||
            !jw_put_u64(&jw, ev->point.retire) ||
            !jw_put_str(&jw, ",\"ordinal\":") ||
            !jw_put_u64(&jw, ev->point.ordinal) ||
            !jw_put_str(&jw, "},\"source\":\"") ||
            !jw_put_str(&jw, sname) ||
            !jw_put_str(&jw, "\",\"interface\":\"") ||
            !jw_put_hex(&jw, ev->interface_id, VOS_RR_DIGEST_BYTES) ||
            !jw_put_str(&jw, "\",\"payload\":{\"") ||
            !jw_put_str(&jw, pfield) ||
            !jw_put_str(&jw, "\":\"") ||
            !jw_put_hex(&jw, ev->payload, ev->payload_len) ||
            !jw_put_str(&jw, "\"}}")) {
            return VOS_RR_ERR_OVER_CAPACITY;
        }
    }

    if (!jw_put_str(&jw, "]}")) {
        return VOS_RR_ERR_OVER_CAPACITY;
    }
    if (jw.len < jw.cap) {
        out_json[jw.len] = '\0';
    }
    *out_json_len = jw.len;
    return VOS_RR_OK;
}

struct json_reader {
    const char *buf;
    size_t len;
    size_t pos;
};

static void jr_skip_ws(struct json_reader *jr)
{
    while (jr->pos < jr->len) {
        const char ch = jr->buf[jr->pos];
        if (ch == ' ' || ch == '\t' || ch == '\r' || ch == '\n') {
            jr->pos += 1u;
        } else {
            break;
        }
    }
}

static int jr_consume(struct json_reader *jr, char expected)
{
    jr_skip_ws(jr);
    if (jr->pos >= jr->len || jr->buf[jr->pos] != expected) {
        return 0;
    }
    jr->pos += 1u;
    return 1;
}

static int jr_read_raw_string(struct json_reader *jr,
                              const char **out_ptr,
                              size_t *out_len)
{
    jr_skip_ws(jr);
    if (jr->pos >= jr->len || jr->buf[jr->pos] != '"') {
        return 0;
    }
    jr->pos += 1u;
    const size_t start = jr->pos;
    while (jr->pos < jr->len) {
        const unsigned char ch = (unsigned char)jr->buf[jr->pos];
        if (ch == '"') {
            *out_ptr = jr->buf + start;
            *out_len = jr->pos - start;
            jr->pos += 1u;
            return 1;
        }
        if (ch < 0x20u || ch == '\\') {
            return 0;
        }
        jr->pos += 1u;
    }
    return 0;
}

static int jr_str_eq(const char *ptr, size_t len, const char *lit)
{
    const size_t lit_len = strlen(lit);
    return len == lit_len && memcmp(ptr, lit, lit_len) == 0;
}

static int hex_nibble(char ch, uint8_t *out)
{
    if (ch >= '0' && ch <= '9') {
        *out = (uint8_t)(ch - '0');
        return 1;
    }
    if (ch >= 'a' && ch <= 'f') {
        *out = (uint8_t)(10 + (ch - 'a'));
        return 1;
    }
    return 0;
}

static int decode_hex_bytes(const char *hex,
                            size_t hex_len,
                            uint8_t *out,
                            size_t max_bytes,
                            size_t *out_bytes)
{
    if (hex_len == 0u || (hex_len % 2u) != 0u) {
        return 0;
    }
    const size_t byte_len = hex_len / 2u;
    if (byte_len > max_bytes) {
        return 0;
    }
    for (size_t i = 0u; i < byte_len; ++i) {
        uint8_t hi = 0u;
        uint8_t lo = 0u;
        if (!hex_nibble(hex[2u * i], &hi) || !hex_nibble(hex[2u * i + 1u], &lo)) {
            return 0;
        }
        out[i] = (uint8_t)((hi << 4u) | lo);
    }
    *out_bytes = byte_len;
    return 1;
}

static int jr_read_u64(struct json_reader *jr, uint64_t *out)
{
    jr_skip_ws(jr);
    if (jr->pos >= jr->len) {
        return 0;
    }
    const size_t start = jr->pos;
    if (jr->buf[start] < '0' || jr->buf[start] > '9') {
        return 0;
    }
    if (jr->buf[start] == '0') {
        jr->pos += 1u;
        if (jr->pos < jr->len &&
            ((jr->buf[jr->pos] >= '0' && jr->buf[jr->pos] <= '9') ||
             jr->buf[jr->pos] == '.' || jr->buf[jr->pos] == 'e' ||
             jr->buf[jr->pos] == 'E')) {
            return 0;
        }
        *out = 0u;
        return 1;
    }
    uint64_t acc = 0u;
    size_t digits = 0u;
    while (jr->pos < jr->len) {
        const char ch = jr->buf[jr->pos];
        if (ch >= '0' && ch <= '9') {
            if (digits >= 20u) {
                return 0;
            }
            const uint64_t d = (uint64_t)(ch - '0');
            if (acc > (UINT64_MAX - d) / 10u) {
                return 0;
            }
            acc = acc * 10u + d;
            digits += 1u;
            jr->pos += 1u;
        } else if (ch == '.' || ch == 'e' || ch == 'E') {
            return 0;
        } else {
            break;
        }
    }
    *out = acc;
    return 1;
}

static enum vos_rr_status parse_json_binding(struct json_reader *jr,
                                             struct vos_rr_binding *out_binding)
{
    if (!jr_consume(jr, '{')) {
        return VOS_RR_ERR_MALFORMED;
    }
    uint32_t seen_mask = 0u;
    while (1) {
        const char *k = NULL;
        size_t klen = 0u;
        if (!jr_read_raw_string(jr, &k, &klen) || !jr_consume(jr, ':')) {
            return VOS_RR_ERR_MALFORMED;
        }
        const char *v = NULL;
        size_t vlen = 0u;
        if (!jr_read_raw_string(jr, &v, &vlen)) {
            return VOS_RR_ERR_MALFORMED;
        }
        if (jr_str_eq(k, klen, "base_image_root")) {
            if ((seen_mask & 1u) != 0u) {
                return VOS_RR_ERR_MALFORMED;
            }
            seen_mask |= 1u;
            size_t blen = 0u;
            if (!decode_hex_bytes(v, vlen, out_binding->base_image_root,
                                  VOS_RR_MAX_BASE_ROOT_BYTES, &blen)) {
                return VOS_RR_ERR_MALFORMED;
            }
            out_binding->base_image_root_len = (uint32_t)blen;
        } else if (jr_str_eq(k, klen, "composition")) {
            if ((seen_mask & 2u) != 0u) {
                return VOS_RR_ERR_MALFORMED;
            }
            seen_mask |= 2u;
            size_t blen = 0u;
            if (vlen != 2u * VOS_RR_DIGEST_BYTES ||
                !decode_hex_bytes(v, vlen, out_binding->composition,
                                  VOS_RR_DIGEST_BYTES, &blen) ||
                blen != VOS_RR_DIGEST_BYTES) {
                return VOS_RR_ERR_MALFORMED;
            }
        } else if (jr_str_eq(k, klen, "input_trace")) {
            if ((seen_mask & 4u) != 0u) {
                return VOS_RR_ERR_MALFORMED;
            }
            seen_mask |= 4u;
            size_t blen = 0u;
            if (vlen != 2u * VOS_RR_DIGEST_BYTES ||
                !decode_hex_bytes(v, vlen, out_binding->input_trace,
                                  VOS_RR_DIGEST_BYTES, &blen) ||
                blen != VOS_RR_DIGEST_BYTES) {
                return VOS_RR_ERR_MALFORMED;
            }
        } else {
            return VOS_RR_ERR_MALFORMED;
        }
        jr_skip_ws(jr);
        if (jr->pos < jr->len && jr->buf[jr->pos] == ',') {
            jr->pos += 1u;
            continue;
        }
        if (jr_consume(jr, '}')) {
            break;
        }
        return VOS_RR_ERR_MALFORMED;
    }
    return (seen_mask == 7u) ? VOS_RR_OK : VOS_RR_ERR_MALFORMED;
}

static enum vos_rr_status parse_json_point(struct json_reader *jr,
                                           struct vos_rr_point *out_pt)
{
    if (!jr_consume(jr, '{')) {
        return VOS_RR_ERR_MALFORMED;
    }
    uint32_t seen_mask = 0u;
    while (1) {
        const char *k = NULL;
        size_t klen = 0u;
        if (!jr_read_raw_string(jr, &k, &klen) || !jr_consume(jr, ':')) {
            return VOS_RR_ERR_MALFORMED;
        }
        uint64_t val = 0u;
        if (!jr_read_u64(jr, &val)) {
            return VOS_RR_ERR_MALFORMED;
        }
        if (jr_str_eq(k, klen, "slot")) {
            if ((seen_mask & 1u) != 0u) {
                return VOS_RR_ERR_MALFORMED;
            }
            seen_mask |= 1u;
            out_pt->slot = val;
        } else if (jr_str_eq(k, klen, "core")) {
            if ((seen_mask & 2u) != 0u) {
                return VOS_RR_ERR_MALFORMED;
            }
            seen_mask |= 2u;
            out_pt->core = val;
        } else if (jr_str_eq(k, klen, "retire")) {
            if ((seen_mask & 4u) != 0u) {
                return VOS_RR_ERR_MALFORMED;
            }
            seen_mask |= 4u;
            out_pt->retire = val;
        } else if (jr_str_eq(k, klen, "ordinal")) {
            if ((seen_mask & 8u) != 0u) {
                return VOS_RR_ERR_MALFORMED;
            }
            seen_mask |= 8u;
            out_pt->ordinal = val;
        } else {
            return VOS_RR_ERR_MALFORMED;
        }
        jr_skip_ws(jr);
        if (jr->pos < jr->len && jr->buf[jr->pos] == ',') {
            jr->pos += 1u;
            continue;
        }
        if (jr_consume(jr, '}')) {
            break;
        }
        return VOS_RR_ERR_MALFORMED;
    }
    return (seen_mask == 15u) ? VOS_RR_OK : VOS_RR_ERR_MALFORMED;
}

static enum vos_rr_status parse_json_payload(struct json_reader *jr,
                                             uint32_t *out_payload_class,
                                             uint8_t out_payload[VOS_RR_MAX_PAYLOAD_BYTES],
                                             uint32_t *out_len)
{
    if (!jr_consume(jr, '{')) {
        return VOS_RR_ERR_MALFORMED;
    }
    const char *k = NULL;
    size_t klen = 0u;
    const char *v = NULL;
    size_t vlen = 0u;
    if (!jr_read_raw_string(jr, &k, &klen) || !jr_consume(jr, ':') ||
        !jr_read_raw_string(jr, &v, &vlen) || !jr_consume(jr, '}')) {
        return VOS_RR_ERR_MALFORMED;
    }
    if (jr_str_eq(k, klen, "sealed_commitment")) {
        *out_payload_class = (uint32_t)VOS_RR_CLASS_SECRET_COMMITMENT;
    } else if (jr_str_eq(k, klen, "value")) {
        *out_payload_class = (uint32_t)VOS_RR_CLASS_PUBLIC_VERBATIM;
    } else {
        return VOS_RR_ERR_MALFORMED;
    }
    if (vlen == 0u) {
        return VOS_RR_ERR_PAYLOAD_EMPTY;
    }
    size_t plen = 0u;
    if (!decode_hex_bytes(v, vlen, out_payload, VOS_RR_MAX_PAYLOAD_BYTES, &plen)) {
        return (vlen / 2u > VOS_RR_MAX_PAYLOAD_BYTES)
                   ? VOS_RR_ERR_PAYLOAD_OVER_LIMIT
                   : VOS_RR_ERR_MALFORMED;
    }
    *out_len = (uint32_t)plen;
    return VOS_RR_OK;
}

static enum vos_rr_status parse_json_event(struct json_reader *jr,
                                           struct vos_rr_event *out_ev)
{
    if (!jr_consume(jr, '{')) {
        return VOS_RR_ERR_MALFORMED;
    }
    uint32_t seen_mask = 0u;
    while (1) {
        const char *k = NULL;
        size_t klen = 0u;
        if (!jr_read_raw_string(jr, &k, &klen) || !jr_consume(jr, ':')) {
            return VOS_RR_ERR_MALFORMED;
        }
        if (jr_str_eq(k, klen, "seq")) {
            if ((seen_mask & 1u) != 0u || !jr_read_u64(jr, &out_ev->seq)) {
                return VOS_RR_ERR_MALFORMED;
            }
            seen_mask |= 1u;
        } else if (jr_str_eq(k, klen, "point")) {
            if ((seen_mask & 2u) != 0u) {
                return VOS_RR_ERR_MALFORMED;
            }
            seen_mask |= 2u;
            const enum vos_rr_status st = parse_json_point(jr, &out_ev->point);
            if (st != VOS_RR_OK) {
                return st;
            }
        } else if (jr_str_eq(k, klen, "source")) {
            if ((seen_mask & 4u) != 0u) {
                return VOS_RR_ERR_MALFORMED;
            }
            seen_mask |= 4u;
            const char *v = NULL;
            size_t vlen = 0u;
            if (!jr_read_raw_string(jr, &v, &vlen)) {
                return VOS_RR_ERR_MALFORMED;
            }
            if (jr_str_eq(v, vlen, "entropy")) {
                out_ev->source = (uint32_t)VOS_RR_SRC_ENTROPY;
            } else if (jr_str_eq(v, vlen, "link_address")) {
                out_ev->source = (uint32_t)VOS_RR_SRC_LINK_ADDRESS;
            } else if (jr_str_eq(v, vlen, "time_read")) {
                out_ev->source = (uint32_t)VOS_RR_SRC_TIME_READ;
            } else if (jr_str_eq(v, vlen, "physical_event")) {
                out_ev->source = (uint32_t)VOS_RR_SRC_PHYSICAL_EVENT;
            } else {
                return VOS_RR_ERR_BAD_SOURCE;
            }
        } else if (jr_str_eq(k, klen, "interface")) {
            if ((seen_mask & 8u) != 0u) {
                return VOS_RR_ERR_MALFORMED;
            }
            seen_mask |= 8u;
            const char *v = NULL;
            size_t vlen = 0u;
            size_t ilen = 0u;
            if (!jr_read_raw_string(jr, &v, &vlen) ||
                vlen != 2u * VOS_RR_DIGEST_BYTES ||
                !decode_hex_bytes(v, vlen, out_ev->interface_id,
                                  VOS_RR_DIGEST_BYTES, &ilen) ||
                ilen != VOS_RR_DIGEST_BYTES) {
                return VOS_RR_ERR_MALFORMED;
            }
        } else if (jr_str_eq(k, klen, "payload")) {
            if ((seen_mask & 16u) != 0u) {
                return VOS_RR_ERR_MALFORMED;
            }
            seen_mask |= 16u;
            const enum vos_rr_status st = parse_json_payload(
                jr, &out_ev->payload_class, out_ev->payload, &out_ev->payload_len);
            if (st != VOS_RR_OK) {
                return st;
            }
        } else {
            return VOS_RR_ERR_MALFORMED;
        }
        jr_skip_ws(jr);
        if (jr->pos < jr->len && jr->buf[jr->pos] == ',') {
            jr->pos += 1u;
            continue;
        }
        if (jr_consume(jr, '}')) {
            break;
        }
        return VOS_RR_ERR_MALFORMED;
    }
    return (seen_mask == 31u) ? VOS_RR_OK : VOS_RR_ERR_MALFORMED;
}

static enum vos_rr_status parse_json_events_array(struct json_reader *jr,
                                                  uint32_t max_events,
                                                  struct vos_rr_record *out_rec)
{
    if (!jr_consume(jr, '[')) {
        return VOS_RR_ERR_MALFORMED;
    }
    jr_skip_ws(jr);
    if (jr->pos < jr->len && jr->buf[jr->pos] == ']') {
        jr->pos += 1u;
        out_rec->event_count = 0u;
        return VOS_RR_OK;
    }
    while (1) {
        if (out_rec->event_count >= VOS_RR_MAX_EVENTS ||
            out_rec->event_count >= max_events) {
            return VOS_RR_ERR_OVER_CAPACITY;
        }
        const enum vos_rr_status st =
            parse_json_event(jr, &out_rec->events[out_rec->event_count]);
        if (st != VOS_RR_OK) {
            return st;
        }
        out_rec->event_count += 1u;
        jr_skip_ws(jr);
        if (jr->pos < jr->len && jr->buf[jr->pos] == ',') {
            jr->pos += 1u;
            continue;
        }
        if (jr_consume(jr, ']')) {
            break;
        }
        return VOS_RR_ERR_MALFORMED;
    }
    return VOS_RR_OK;
}

enum vos_rr_status vos_rr_decode_json(
    const char *json,
    size_t json_len,
    const struct vos_rr_binding *expected_binding,
    uint32_t expected_events,
    const struct vos_rr_limits *limits,
    const struct vos_rr_interface *interfaces,
    size_t interface_count,
    struct vos_rr_record *out_record)
{
    if (out_record == NULL) {
        return VOS_RR_ERR_INVALID_ARG;
    }
    memset(out_record, 0, sizeof(*out_record));
    if (json == NULL || json_len == 0u || !binding_is_valid(expected_binding) ||
        !check_limits_and_interfaces(limits, interfaces, interface_count)) {
        return VOS_RR_ERR_INVALID_ARG;
    }
    if (expected_events > limits->max_events) {
        return VOS_RR_ERR_OVER_CAPACITY;
    }
    if (json_len > VOS_RR_MAX_JSON_BYTES) {
        return VOS_RR_ERR_OVER_CAPACITY;
    }

    struct json_reader jr = {json, json_len, 0u};
    if (!jr_consume(&jr, '{')) {
        return VOS_RR_ERR_MALFORMED;
    }

    struct vos_rr_record parsed;
    memset(&parsed, 0, sizeof(parsed));
    uint32_t seen_mask = 0u;

    while (1) {
        const char *k = NULL;
        size_t klen = 0u;
        if (!jr_read_raw_string(&jr, &k, &klen) || !jr_consume(&jr, ':')) {
            return VOS_RR_ERR_MALFORMED;
        }
        if (jr_str_eq(k, klen, "schema")) {
            if ((seen_mask & 1u) != 0u) {
                return VOS_RR_ERR_MALFORMED;
            }
            seen_mask |= 1u;
            const char *v = NULL;
            size_t vlen = 0u;
            if (!jr_read_raw_string(&jr, &v, &vlen)) {
                return VOS_RR_ERR_MALFORMED;
            }
            if (!jr_str_eq(v, vlen, VOS_RR_SCHEMA_V1)) {
                return VOS_RR_ERR_UNKNOWN_SCHEMA;
            }
        } else if (jr_str_eq(k, klen, "binding")) {
            if ((seen_mask & 2u) != 0u) {
                return VOS_RR_ERR_MALFORMED;
            }
            seen_mask |= 2u;
            const enum vos_rr_status st = parse_json_binding(&jr, &parsed.binding);
            if (st != VOS_RR_OK) {
                return st;
            }
        } else if (jr_str_eq(k, klen, "events")) {
            if ((seen_mask & 4u) != 0u) {
                return VOS_RR_ERR_MALFORMED;
            }
            seen_mask |= 4u;
            const enum vos_rr_status st =
                parse_json_events_array(&jr, limits->max_events, &parsed);
            if (st != VOS_RR_OK) {
                return st;
            }
        } else {
            return VOS_RR_ERR_MALFORMED;
        }
        jr_skip_ws(&jr);
        if (jr.pos < jr.len && jr.buf[jr.pos] == ',') {
            jr.pos += 1u;
            continue;
        }
        if (jr_consume(&jr, '}')) {
            break;
        }
        return VOS_RR_ERR_MALFORMED;
    }

    if (seen_mask != 7u) {
        return VOS_RR_ERR_MALFORMED;
    }
    jr_skip_ws(&jr);
    if (jr.pos != jr.len) {
        return VOS_RR_ERR_TRAILING_BYTES;
    }

    const enum vos_rr_status val_st = validate_record_against(
        &parsed, expected_binding, expected_events,
        limits, interfaces, interface_count);
    if (val_st != VOS_RR_OK) {
        return val_st;
    }

    *out_record = parsed;
    return VOS_RR_OK;
}

/* =========================================================================
 * Strict demand-cursor replay verifier.
 * ========================================================================= */

enum vos_rr_status vos_rr_cursor_init(
    struct vos_rr_cursor *cursor,
    const struct vos_rr_record *record,
    const struct vos_rr_binding *expected_binding,
    uint32_t expected_events,
    const struct vos_rr_limits *limits,
    const struct vos_rr_interface *interfaces,
    size_t interface_count)
{
    if (cursor == NULL) {
        return VOS_RR_ERR_INVALID_ARG;
    }
    memset(cursor, 0, sizeof(*cursor));
    const enum vos_rr_status st = validate_record_against(
        record, expected_binding, expected_events,
        limits, interfaces, interface_count);
    if (st != VOS_RR_OK) {
        cursor->failed = 1u;
        return st;
    }
    cursor->record = *record;
    return VOS_RR_OK;
}

void vos_rr_cursor_abort(struct vos_rr_cursor *cursor)
{
    if (cursor == NULL) {
        return;
    }
    cursor->failed = 1u;
}

enum vos_rr_status vos_rr_cursor_consume(
    struct vos_rr_cursor *cursor,
    const struct vos_rr_point *point,
    enum vos_rr_source source,
    const uint8_t interface_id[VOS_RR_DIGEST_BYTES],
    struct vos_rr_event *out_event)
{
    if (out_event != NULL) {
        memset(out_event, 0, sizeof(*out_event));
    }
    if (cursor == NULL) {
        return VOS_RR_ERR_INVALID_ARG;
    }
    if (cursor->failed != 0u) {
        return VOS_RR_ERR_LATCHED_FAILURE;
    }
    if (cursor->finished != 0u) {
        cursor->failed = 1u;
        return VOS_RR_ERR_ALREADY_FINISHED;
    }
    if (point == NULL || interface_id == NULL ||
        !vos_rr_source_is_valid((uint32_t)source)) {
        cursor->failed = 1u;
        return VOS_RR_ERR_INVALID_ARG;
    }
    if (cursor->next >= cursor->record.event_count) {
        cursor->failed = 1u;
        return VOS_RR_ERR_EXHAUSTED;
    }

    const struct vos_rr_event *ev = &cursor->record.events[cursor->next];
    if (!points_equal(&ev->point, point) ||
        ev->source != (uint32_t)source ||
        !bytes_equal(ev->interface_id, interface_id, VOS_RR_DIGEST_BYTES)) {
        cursor->failed = 1u;
        return VOS_RR_ERR_DEMAND_MISMATCH;
    }

    cursor->next += 1u;
    if (out_event != NULL) {
        *out_event = *ev;
    }
    return VOS_RR_OK;
}

enum vos_rr_status vos_rr_cursor_finish(struct vos_rr_cursor *cursor)
{
    if (cursor == NULL) {
        return VOS_RR_ERR_INVALID_ARG;
    }
    if (cursor->failed != 0u) {
        return VOS_RR_ERR_LATCHED_FAILURE;
    }
    if (cursor->finished != 0u) {
        cursor->failed = 1u;
        return VOS_RR_ERR_ALREADY_FINISHED;
    }
    if (cursor->next != cursor->record.event_count) {
        cursor->failed = 1u;
        return VOS_RR_ERR_TRAILING_EVENTS;
    }
    cursor->finished = 1u;
    return VOS_RR_OK;
}
