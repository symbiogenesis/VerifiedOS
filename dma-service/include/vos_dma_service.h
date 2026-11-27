// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_DMA_SERVICE_H
#define VOS_DMA_SERVICE_H

#include <stddef.h>
#include <stdint.h>

/* GC-free C17 DMA ring service mirroring `proofs/RingContract.v` (`RingDma`)
 * and `proofs/CopyRingService.v`. All ring and operation bounds are injected via
 * `vos_dma_config` (sourced from `interfaces/ring-reference.json` `ring_dma`). */

typedef enum {
    VOS_DMA_STATUS_OK = 0,
    VOS_DMA_STATUS_REFUSED = 1,
    VOS_DMA_STATUS_INVALID = 2,
    VOS_DMA_STATUS_CANCELLED = 3,
    VOS_DMA_STATUS_DEADLINE_EXPIRED = 4,
    VOS_DMA_STATUS_PEER_RESTARTED = 5,
    VOS_DMA_STATUS_DEVICE_FAULT = 6,
    VOS_DMA_STATUS_RESOURCE_EXHAUSTED = 7
} vos_dma_status;

typedef enum {
    VOS_DMA_FREE = 0,
    VOS_DMA_WRITING = 1,
    VOS_DMA_SUBMITTED = 2,
    VOS_DMA_ACCEPTED = 3,
    VOS_DMA_TERMINAL = 4,
    VOS_DMA_RECLAIMED = 5
} vos_dma_slot_state;

typedef enum {
    VOS_DMA_SUBMIT_ENQUEUED = 0,
    VOS_DMA_SUBMIT_WOULD_BLOCK = 1
} vos_dma_submit_result;

typedef enum {
    VOS_DMA_CANCELED = 0,
    VOS_DMA_TOO_LATE = 1,
    VOS_DMA_NOT_LIVE = 2
} vos_dma_cancel_answer;

typedef enum {
    VOS_DMA_DIR_TO_SERVER = 0,
    VOS_DMA_DIR_TO_CLIENT = 1
} vos_dma_direction;

typedef enum {
    VOS_DMA_PERM_LOAD = 0,
    VOS_DMA_PERM_STORE = 1
} vos_dma_perm;

typedef enum {
    VOS_DMA_CONTENT_OPAQUE_BYTES = 0,
    VOS_DMA_CONTENT_GRANULE_EXTENT = 1
} vos_dma_content_type;

typedef struct {
    uint32_t max_payload_bytes;
    uint32_t max_segment_count;
    uint8_t cancellable;
    uint32_t cancel_points;
    uint32_t commit_index;
    uint32_t quiescence_bound;
    uint32_t held_capabilities;
    uint32_t extent_validated_bytes;
    uint32_t descriptor_validation_cost;
    uint32_t segment_validation_cost;
    uint32_t validation_cost;
    uint32_t max_to_terminal;
} vos_dma_op_spec;

typedef struct {
    uint32_t capacity;
    uint32_t index_span;
    uint32_t max_batch_size;
    uint32_t initial_generation;
    uint32_t max_segments;
    uint32_t segment_max_bytes;
    uint32_t slot_budget;
    const vos_dma_op_spec *ops;
    size_t op_count;
} vos_dma_config;

typedef struct {
    uint16_t session_index;
    vos_dma_perm permission;
    uint32_t capability_bytes;
    uint8_t valid;
} vos_dma_session_cap;

typedef struct {
    uint16_t session_index;
    uint32_t offset;
    uint32_t length;
    vos_dma_direction direction;
    vos_dma_content_type content;
} vos_dma_buffer_ref;

typedef struct {
    uint32_t op;
    uint32_t request_id;
    uint32_t generation;
    uint32_t window_index;
    uint32_t transfer_length;
    const vos_dma_buffer_ref *segments;
    size_t segment_count;
} vos_dma_descriptor;

typedef struct {
    vos_dma_slot_state state;
    uint32_t request_id;
    uint32_t generation;
    uint32_t op;
    uint32_t window_index;
    uint32_t transfer_length;
    uint32_t staged_bytes;
    uint32_t held_capabilities;
    uint32_t position;
    vos_dma_status completion_status;
    uint8_t extent_validated;
    uint8_t validated_before_start;
    vos_dma_buffer_ref *segments;
    size_t segment_cap;
    size_t segment_count;
} vos_dma_slot;

typedef struct {
    const vos_dma_config *config;
    vos_dma_slot *slots;
    size_t slot_capacity;
    const vos_dma_session_cap *session_table;
    size_t session_table_len;
    uint32_t produced;
    uint32_t consumed;
    uint8_t armed;
    uint32_t generation;
    uint8_t fail_stopped;
} vos_dma_ring;

uint32_t vos_dma_occupancy(const vos_dma_ring *ring);
vos_dma_perm vos_dma_direction_permission(vos_dma_direction dir);
int vos_dma_direction_authorized(vos_dma_perm granted, vos_dma_direction dir);
int vos_dma_segment_valid(const vos_dma_ring *ring, const vos_dma_buffer_ref *seg);

int vos_dma_init(
    vos_dma_ring *ring,
    const vos_dma_config *config,
    vos_dma_slot *slots,
    size_t slot_capacity,
    vos_dma_buffer_ref *slot_seg_bufs,
    size_t seg_stride,
    const vos_dma_session_cap *session_table,
    size_t session_table_len);

vos_dma_status vos_dma_submit(
    vos_dma_ring *ring,
    const vos_dma_descriptor *desc,
    vos_dma_submit_result *out_submit_result,
    uint32_t *out_slot_idx);

vos_dma_status vos_dma_accept(vos_dma_ring *ring, uint32_t slot_idx);
vos_dma_status vos_dma_advance_progress(vos_dma_ring *ring, uint32_t slot_idx, uint32_t position);
vos_dma_status vos_dma_complete(vos_dma_ring *ring, uint32_t slot_idx, vos_dma_status status);
vos_dma_status vos_dma_reclaim(vos_dma_ring *ring, uint32_t slot_idx);

vos_dma_cancel_answer vos_dma_cancel(vos_dma_ring *ring, uint32_t request_id, uint32_t position);

int vos_dma_reset_session(
    vos_dma_ring *ring, uint8_t dma_quiesced, uint32_t quiescence_elapsed);

vos_dma_status vos_dma_enforce_quiescence(
    vos_dma_ring *ring, uint32_t slot_idx, uint8_t dma_quiesced, uint32_t quiescence_elapsed);

uint32_t vos_dma_held_capabilities(const vos_dma_ring *ring, uint32_t slot_idx);

#endif
