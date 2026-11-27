// SPDX-License-Identifier: Apache-2.0
#include "vos_dma_service.h"

static int config_valid(const vos_dma_config *config)
{
    if (config == NULL || config->ops == NULL || config->op_count == 0U) {
        return 0;
    }
    if (config->capacity == 0U || config->index_span <= config->capacity) {
        return 0;
    }
    if ((config->index_span % config->capacity) != 0U) {
        return 0;
    }
    if (config->capacity > (config->index_span / 2U)) {
        return 0;
    }
    if (config->max_batch_size == 0U || config->max_batch_size > config->capacity) {
        return 0;
    }
    if (config->initial_generation == 0U
        || config->max_segments == 0U
        || config->segment_max_bytes == 0U) {
        return 0;
    }
    return 1;
}

uint32_t vos_dma_occupancy(const vos_dma_ring *ring)
{
    if (ring == NULL || ring->config == NULL || ring->config->index_span == 0U) {
        return 0U;
    }
    const uint32_t span = ring->config->index_span;
    return (ring->produced + span - ring->consumed) % span;
}

vos_dma_perm vos_dma_direction_permission(vos_dma_direction dir)
{
    if (dir == VOS_DMA_DIR_TO_SERVER) {
        return VOS_DMA_PERM_LOAD;
    }
    return VOS_DMA_PERM_STORE;
}

int vos_dma_direction_authorized(vos_dma_perm granted, vos_dma_direction dir)
{
    return granted == vos_dma_direction_permission(dir);
}

int vos_dma_segment_valid(const vos_dma_ring *ring, const vos_dma_buffer_ref *seg)
{
    if (ring == NULL || ring->config == NULL || seg == NULL
        || ring->session_table == NULL) {
        return 0;
    }
    if (seg->direction != VOS_DMA_DIR_TO_SERVER
        && seg->direction != VOS_DMA_DIR_TO_CLIENT) {
        return 0;
    }
    if (seg->content != VOS_DMA_CONTENT_OPAQUE_BYTES
        && seg->content != VOS_DMA_CONTENT_GRANULE_EXTENT) {
        return 0;
    }
    if ((size_t)seg->session_index >= ring->session_table_len) {
        return 0;
    }
    const vos_dma_session_cap *cap = &ring->session_table[seg->session_index];
    if (cap->valid == 0U) {
        return 0;
    }
    if (!vos_dma_direction_authorized(cap->permission, seg->direction)) {
        return 0;
    }
    if (seg->length > ring->config->segment_max_bytes) {
        return 0;
    }
    if (seg->offset > cap->capability_bytes
        || seg->length > (cap->capability_bytes - seg->offset)) {
        return 0;
    }
    return 1;
}

static void reset_slot_fields(vos_dma_slot *slot)
{
    slot->state = VOS_DMA_FREE;
    slot->request_id = 0U;
    slot->generation = 0U;
    slot->op = 0U;
    slot->window_index = 0U;
    slot->transfer_length = 0U;
    slot->staged_bytes = 0U;
    slot->held_capabilities = 0U;
    slot->position = 0U;
    slot->completion_status = VOS_DMA_STATUS_OK;
    slot->extent_validated = 0U;
    slot->validated_before_start = 0U;
    slot->segment_count = 0U;
}

static void release_all_capabilities(vos_dma_ring *ring)
{
    if (ring == NULL || ring->slots == NULL || ring->config == NULL) {
        return;
    }
    for (size_t i = 0U; i < ring->config->capacity; ++i) {
        ring->slots[i].held_capabilities = 0U;
    }
}

int vos_dma_init(
    vos_dma_ring *ring,
    const vos_dma_config *config,
    vos_dma_slot *slots,
    size_t slot_capacity,
    vos_dma_buffer_ref *slot_seg_bufs,
    size_t seg_stride,
    const vos_dma_session_cap *session_table,
    size_t session_table_len)
{
    if (ring == NULL || !config_valid(config)
        || slots == NULL || slot_seg_bufs == NULL
        || (session_table_len > 0U && session_table == NULL)) {
        return 0;
    }
    if (slot_capacity < (size_t)config->capacity || seg_stride < (size_t)config->max_segments) {
        return 0;
    }
    ring->config = config;
    ring->slots = slots;
    ring->slot_capacity = slot_capacity;
    ring->session_table = session_table;
    ring->session_table_len = session_table_len;
    ring->produced = 0U;
    ring->consumed = 0U;
    ring->armed = 0U;
    ring->generation = config->initial_generation;
    ring->fail_stopped = 0U;
    for (size_t i = 0U; i < (size_t)config->capacity; ++i) {
        slots[i].segments = &slot_seg_bufs[i * seg_stride];
        slots[i].segment_cap = seg_stride;
        reset_slot_fields(&slots[i]);
    }
    return 1;
}

static int duplicate_live_request(const vos_dma_ring *ring, uint32_t request_id)
{
    const uint32_t occ = vos_dma_occupancy(ring);
    const uint32_t cap = ring->config->capacity;
    for (uint32_t i = 0U; i < occ; ++i) {
        const uint32_t idx = (ring->consumed + i) % cap;
        const vos_dma_slot *s = &ring->slots[idx];
        if ((s->state == VOS_DMA_SUBMITTED || s->state == VOS_DMA_ACCEPTED)
            && s->request_id == request_id) {
            return 1;
        }
    }
    return 0;
}

vos_dma_status vos_dma_submit(
    vos_dma_ring *ring,
    const vos_dma_descriptor *desc,
    vos_dma_submit_result *out_submit_result,
    uint32_t *out_slot_idx)
{
    if (out_submit_result != NULL) {
        *out_submit_result = VOS_DMA_SUBMIT_WOULD_BLOCK;
    }
    if (out_slot_idx != NULL) {
        *out_slot_idx = 0U;
    }
    if (ring == NULL || ring->config == NULL || ring->slots == NULL || desc == NULL) {
        return VOS_DMA_STATUS_INVALID;
    }
    if (ring->fail_stopped != 0U) {
        return VOS_DMA_STATUS_DEVICE_FAULT;
    }
    if (desc->generation != ring->generation || ring->generation == 0U) {
        return VOS_DMA_STATUS_REFUSED;
    }
    const vos_dma_config *cfg = ring->config;
    const uint32_t occ = vos_dma_occupancy(ring);
    if (occ >= cfg->capacity) {
        return VOS_DMA_STATUS_RESOURCE_EXHAUSTED;
    }
    if ((size_t)desc->op >= cfg->op_count) {
        return VOS_DMA_STATUS_INVALID;
    }
    if (duplicate_live_request(ring, desc->request_id)) {
        return VOS_DMA_STATUS_REFUSED;
    }
    const vos_dma_op_spec *spec = &cfg->ops[desc->op];
    if (desc->segment_count > (size_t)spec->max_segment_count
        || desc->segment_count > (size_t)cfg->max_segments) {
        return VOS_DMA_STATUS_INVALID;
    }
    if (desc->segment_count > 0U && desc->segments == NULL) {
        return VOS_DMA_STATUS_INVALID;
    }
    if (spec->max_payload_bytes == 0U
        && (desc->transfer_length != 0U || desc->segment_count != 0U)) {
        return VOS_DMA_STATUS_INVALID;
    }
    uint32_t total_seg_bytes = 0U;
    for (size_t i = 0U; i < desc->segment_count; ++i) {
        if (!vos_dma_segment_valid(ring, &desc->segments[i])) {
            return VOS_DMA_STATUS_REFUSED;
        }
        if (desc->segments[i].length > (UINT32_MAX - total_seg_bytes)) {
            return VOS_DMA_STATUS_INVALID;
        }
        total_seg_bytes += desc->segments[i].length;
    }
    if (desc->transfer_length > spec->max_payload_bytes
        || total_seg_bytes > spec->max_payload_bytes) {
        return VOS_DMA_STATUS_INVALID;
    }
    if (desc->segment_count > 0U && desc->transfer_length != total_seg_bytes) {
        return VOS_DMA_STATUS_INVALID;
    }
    const uint32_t slot_idx = ring->produced % cfg->capacity;
    vos_dma_slot *slot = &ring->slots[slot_idx];
    if ((slot->state != VOS_DMA_FREE && slot->state != VOS_DMA_RECLAIMED)
        || slot->held_capabilities != 0U
        || desc->segment_count > slot->segment_cap) {
        return VOS_DMA_STATUS_RESOURCE_EXHAUSTED;
    }
    slot->state = VOS_DMA_WRITING;
    slot->request_id = desc->request_id;
    slot->generation = desc->generation;
    slot->op = desc->op;
    slot->window_index = desc->window_index;
    slot->transfer_length = desc->transfer_length;
    slot->staged_bytes = desc->transfer_length;
    slot->held_capabilities = 0U;
    slot->position = 0U;
    slot->completion_status = VOS_DMA_STATUS_OK;
    slot->segment_count = desc->segment_count;
    for (size_t i = 0U; i < desc->segment_count; ++i) {
        slot->segments[i] = desc->segments[i];
    }
    slot->extent_validated = 1U;
    slot->validated_before_start = 1U;
    slot->state = VOS_DMA_SUBMITTED;
    ring->produced = (ring->produced + 1U) % cfg->index_span;
    if (out_submit_result != NULL) {
        *out_submit_result = VOS_DMA_SUBMIT_ENQUEUED;
    }
    if (out_slot_idx != NULL) {
        *out_slot_idx = slot_idx;
    }
    return VOS_DMA_STATUS_OK;
}

vos_dma_status vos_dma_accept(vos_dma_ring *ring, uint32_t slot_idx)
{
    if (ring == NULL || ring->config == NULL || ring->slots == NULL
        || slot_idx >= ring->config->capacity) {
        return VOS_DMA_STATUS_INVALID;
    }
    if (ring->fail_stopped != 0U) {
        return VOS_DMA_STATUS_DEVICE_FAULT;
    }
    vos_dma_slot *slot = &ring->slots[slot_idx];
    if (slot->state != VOS_DMA_SUBMITTED
        || slot->extent_validated == 0U
        || slot->validated_before_start == 0U) {
        return VOS_DMA_STATUS_INVALID;
    }
    if (slot->generation != ring->generation) {
        /* Generation mismatch after submission triggers fail-stop (R-12-099). */
        ring->fail_stopped = 1U;
        release_all_capabilities(ring);
        return VOS_DMA_STATUS_DEVICE_FAULT;
    }
    if ((size_t)slot->op >= ring->config->op_count) {
        return VOS_DMA_STATUS_INVALID;
    }
    /* Re-verify snapshotted segment bounds against live session table without
     * re-reading external caller descriptors. */
    for (size_t i = 0U; i < slot->segment_count; ++i) {
        if (!vos_dma_segment_valid(ring, &slot->segments[i])) {
            return VOS_DMA_STATUS_REFUSED;
        }
    }
    const vos_dma_op_spec *spec = &ring->config->ops[slot->op];
    slot->state = VOS_DMA_ACCEPTED;
    slot->held_capabilities = spec->held_capabilities;
    slot->position = 0U;
    return VOS_DMA_STATUS_OK;
}

vos_dma_status vos_dma_advance_progress(vos_dma_ring *ring, uint32_t slot_idx, uint32_t position)
{
    if (ring == NULL || ring->config == NULL || ring->slots == NULL
        || slot_idx >= ring->config->capacity) {
        return VOS_DMA_STATUS_INVALID;
    }
    if (ring->fail_stopped != 0U) {
        return VOS_DMA_STATUS_DEVICE_FAULT;
    }
    vos_dma_slot *slot = &ring->slots[slot_idx];
    if (slot->state != VOS_DMA_ACCEPTED) {
        return VOS_DMA_STATUS_INVALID;
    }
    slot->position = position;
    return VOS_DMA_STATUS_OK;
}

vos_dma_status vos_dma_complete(vos_dma_ring *ring, uint32_t slot_idx, vos_dma_status status)
{
    if (ring == NULL || ring->config == NULL || ring->slots == NULL
        || slot_idx >= ring->config->capacity) {
        return VOS_DMA_STATUS_INVALID;
    }
    if (ring->fail_stopped != 0U) {
        return VOS_DMA_STATUS_DEVICE_FAULT;
    }
    vos_dma_slot *slot = &ring->slots[slot_idx];
    if (slot->state != VOS_DMA_ACCEPTED) {
        return VOS_DMA_STATUS_INVALID;
    }
    slot->state = VOS_DMA_TERMINAL;
    slot->completion_status = status;
    slot->held_capabilities = 0U;
    return VOS_DMA_STATUS_OK;
}

vos_dma_status vos_dma_reclaim(vos_dma_ring *ring, uint32_t slot_idx)
{
    if (ring == NULL || ring->config == NULL || ring->slots == NULL
        || slot_idx >= ring->config->capacity) {
        return VOS_DMA_STATUS_INVALID;
    }
    if (vos_dma_occupancy(ring) == 0U
        || slot_idx != (ring->consumed % ring->config->capacity)) {
        return VOS_DMA_STATUS_INVALID;
    }
    vos_dma_slot *slot = &ring->slots[slot_idx];
    if (slot->state != VOS_DMA_TERMINAL || slot->held_capabilities != 0U) {
        return VOS_DMA_STATUS_INVALID;
    }
    slot->state = VOS_DMA_RECLAIMED;
    ring->consumed = (ring->consumed + 1U) % ring->config->index_span;
    return VOS_DMA_STATUS_OK;
}

vos_dma_cancel_answer vos_dma_cancel(vos_dma_ring *ring, uint32_t request_id, uint32_t position)
{
    if (ring == NULL || ring->config == NULL || ring->slots == NULL
        || ring->fail_stopped != 0U) {
        return VOS_DMA_NOT_LIVE;
    }
    const uint32_t occ = vos_dma_occupancy(ring);
    const uint32_t cap = ring->config->capacity;
    vos_dma_slot *slot = NULL;
    for (uint32_t i = 0U; i < occ; ++i) {
        vos_dma_slot *cand = &ring->slots[(ring->consumed + i) % cap];
        if ((cand->state == VOS_DMA_SUBMITTED || cand->state == VOS_DMA_ACCEPTED)
            && cand->request_id == request_id) {
            slot = cand;
            break;
        }
    }
    if (slot == NULL || (size_t)slot->op >= ring->config->op_count) {
        return VOS_DMA_NOT_LIVE;
    }
    const vos_dma_op_spec *spec = &ring->config->ops[slot->op];
    if (spec->cancellable == 0U) {
        return VOS_DMA_NOT_LIVE;
    }
    if (slot->state == VOS_DMA_SUBMITTED) {
        slot->state = VOS_DMA_TERMINAL;
        slot->completion_status = VOS_DMA_STATUS_CANCELLED;
        slot->held_capabilities = 0U;
        return VOS_DMA_CANCELED;
    }
    if (slot->state == VOS_DMA_ACCEPTED) {
        if (position < spec->commit_index) {
            slot->state = VOS_DMA_TERMINAL;
            slot->completion_status = VOS_DMA_STATUS_CANCELLED;
            slot->held_capabilities = 0U;
            return VOS_DMA_CANCELED;
        }
        return VOS_DMA_TOO_LATE;
    }
    return VOS_DMA_NOT_LIVE;
}

int vos_dma_reset_session(
    vos_dma_ring *ring, uint8_t dma_quiesced, uint32_t quiescence_elapsed)
{
    if (ring == NULL || ring->config == NULL || ring->slots == NULL) {
        return 0;
    }
    if (ring->fail_stopped != 0U || ring->generation == UINT32_MAX) {
        return 0;
    }
    uint32_t max_quiesce = 0U;
    uint8_t has_active = 0U;
    for (size_t i = 0U; i < (size_t)ring->config->capacity; ++i) {
        const vos_dma_slot *slot = &ring->slots[i];
        if (slot->state == VOS_DMA_SUBMITTED || slot->state == VOS_DMA_ACCEPTED) {
            if ((size_t)slot->op < ring->config->op_count) {
                const uint32_t b = ring->config->ops[slot->op].quiescence_bound;
                if (has_active == 0U || b > max_quiesce) {
                    max_quiesce = b;
                }
                has_active = 1U;
            }
        }
    }
    if (dma_quiesced == 0U || (has_active != 0U && quiescence_elapsed > max_quiesce)) {
        ring->fail_stopped = 1U;
        release_all_capabilities(ring);
        return 0;
    }
    for (size_t i = 0U; i < (size_t)ring->config->capacity; ++i) {
        reset_slot_fields(&ring->slots[i]);
    }
    ring->produced = 0U;
    ring->consumed = 0U;
    ring->armed = 0U;
    ring->generation += 1U;
    return 1;
}

vos_dma_status vos_dma_enforce_quiescence(
    vos_dma_ring *ring, uint32_t slot_idx, uint8_t dma_quiesced, uint32_t quiescence_elapsed)
{
    if (ring == NULL || ring->config == NULL || ring->slots == NULL
        || slot_idx >= ring->config->capacity) {
        return VOS_DMA_STATUS_INVALID;
    }
    vos_dma_slot *slot = &ring->slots[slot_idx];
    if ((size_t)slot->op >= ring->config->op_count) {
        return VOS_DMA_STATUS_INVALID;
    }
    const uint32_t bound = ring->config->ops[slot->op].quiescence_bound;
    if (dma_quiesced == 0U || quiescence_elapsed > bound) {
        ring->fail_stopped = 1U;
        release_all_capabilities(ring);
        return VOS_DMA_STATUS_DEVICE_FAULT;
    }
    return VOS_DMA_STATUS_OK;
}

uint32_t vos_dma_held_capabilities(const vos_dma_ring *ring, uint32_t slot_idx)
{
    if (ring == NULL || ring->config == NULL || ring->slots == NULL
        || slot_idx >= ring->config->capacity) {
        return 0U;
    }
    return ring->slots[slot_idx].held_capabilities;
}
