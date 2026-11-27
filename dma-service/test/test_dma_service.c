// SPDX-License-Identifier: Apache-2.0
#include "vos_dma_service.h"
#include "dma_service_config.h"

#include <stdio.h>
#include <string.h>

#define CHECK(cond, msg)                                                     \
    do {                                                                     \
        if (!(cond)) {                                                       \
            fprintf(stderr, "dma control failed (%s): %s\n", #cond, (msg));  \
            return 1;                                                        \
        }                                                                    \
    } while (0)

static vos_dma_slot g_slots[VOS_DMA_CAPACITY];
static vos_dma_buffer_ref g_slot_segs[VOS_DMA_CAPACITY * VOS_DMA_MAX_SEGMENTS];

static int init_default_ring(
    vos_dma_ring *ring, const vos_dma_config *cfg,
    const vos_dma_session_cap *table, size_t table_len)
{
    return vos_dma_init(
        ring, cfg, g_slots, VOS_DMA_CAPACITY,
        g_slot_segs, VOS_DMA_MAX_SEGMENTS, table, table_len);
}

static int test_directions_and_segments(const vos_dma_config *cfg)
{
    CHECK(vos_dma_direction_permission(VOS_DMA_DIR_TO_SERVER) == VOS_DMA_PERM_LOAD,
          "to_server perm wrong");
    CHECK(vos_dma_direction_permission(VOS_DMA_DIR_TO_CLIENT) == VOS_DMA_PERM_STORE,
          "to_client perm wrong");
    CHECK(vos_dma_direction_authorized(VOS_DMA_PERM_LOAD, VOS_DMA_DIR_TO_SERVER) == 1,
          "load not authorized for to_server");
    CHECK(vos_dma_direction_authorized(VOS_DMA_PERM_STORE, VOS_DMA_DIR_TO_SERVER) == 0,
          "direction mismatch accepted (store for to_server)");
    CHECK(vos_dma_direction_authorized(VOS_DMA_PERM_STORE, VOS_DMA_DIR_TO_CLIENT) == 1,
          "store not authorized for to_client");
    CHECK(vos_dma_direction_authorized(VOS_DMA_PERM_LOAD, VOS_DMA_DIR_TO_CLIENT) == 0,
          "direction mismatch accepted (load for to_client)");

    const vos_dma_session_cap table[3] = {
        { .session_index = 0U, .permission = VOS_DMA_PERM_LOAD,
          .capability_bytes = VOS_DMA_SEGMENT_MAX_BYTES * 2U, .valid = 1U },
        { .session_index = 1U, .permission = VOS_DMA_PERM_STORE,
          .capability_bytes = VOS_DMA_SEGMENT_MAX_BYTES * 2U, .valid = 1U },
        { .session_index = 2U, .permission = VOS_DMA_PERM_LOAD,
          .capability_bytes = VOS_DMA_SEGMENT_MAX_BYTES, .valid = 0U }
    };
    vos_dma_ring ring;
    CHECK(init_default_ring(&ring, cfg, table, 3U) == 1, "ring init failed");

    /* Max segment list accepted. */
    vos_dma_buffer_ref segs[VOS_DMA_MAX_SEGMENTS + 1U];
    for (size_t i = 0U; i < VOS_DMA_MAX_SEGMENTS; ++i) {
        segs[i].session_index = 0U;
        segs[i].offset = 0U;
        segs[i].length = VOS_DMA_SEGMENT_MAX_BYTES;
        segs[i].direction = VOS_DMA_DIR_TO_SERVER;
        segs[i].content = VOS_DMA_CONTENT_OPAQUE_BYTES;
    }
    vos_dma_descriptor desc = {
        .op = VOS_DMA_OP_STREAM_TO_DEVICE,
        .request_id = 100U,
        .generation = ring.generation,
        .window_index = 0U,
        .transfer_length = VOS_DMA_MAX_SEGMENTS * VOS_DMA_SEGMENT_MAX_BYTES,
        .segments = segs,
        .segment_count = VOS_DMA_MAX_SEGMENTS
    };
    vos_dma_submit_result sres = VOS_DMA_SUBMIT_WOULD_BLOCK;
    uint32_t slot_idx = 0U;
    CHECK(vos_dma_submit(&ring, &desc, &sres, &slot_idx) == VOS_DMA_STATUS_OK
          && sres == VOS_DMA_SUBMIT_ENQUEUED,
          "maximum valid segment list rejected");

    /* Mutate caller descriptor & segments after submit: service must not reinterpret. */
    desc.transfer_length = 999999U;
    segs[0].length = VOS_DMA_SEGMENT_MAX_BYTES + 100U;
    segs[0].direction = VOS_DMA_DIR_TO_CLIENT;
    CHECK(vos_dma_accept(&ring, slot_idx) == VOS_DMA_STATUS_OK,
          "snapshotted transfer rejected after caller mutation");
    CHECK(ring.slots[slot_idx].staged_bytes == VOS_DMA_MAX_SEGMENTS * VOS_DMA_SEGMENT_MAX_BYTES
          && ring.slots[slot_idx].segments[0].length == VOS_DMA_SEGMENT_MAX_BYTES,
          "reinterpreted caller descriptor after submit");

    /* Capability held during ACCEPTED, released immediately at TERMINAL. */
    const uint32_t expected_held = cfg->ops[VOS_DMA_OP_STREAM_TO_DEVICE].held_capabilities;
    CHECK(expected_held > 0U && vos_dma_held_capabilities(&ring, slot_idx) == expected_held,
          "capability not held while accepted");
    CHECK(vos_dma_complete(&ring, slot_idx, VOS_DMA_STATUS_OK) == VOS_DMA_STATUS_OK,
          "complete failed");
    CHECK(ring.slots[slot_idx].state == VOS_DMA_TERMINAL, "not terminal");
    CHECK(vos_dma_held_capabilities(&ring, slot_idx) == 0U,
          "retained capability after completion");
    CHECK(vos_dma_reclaim(&ring, slot_idx) == VOS_DMA_STATUS_OK, "reclaim failed");
    CHECK(vos_dma_held_capabilities(&ring, slot_idx) == 0U, "capability held after reclaim");

    /* One segment past maximum refused. */
    segs[0].length = VOS_DMA_SEGMENT_MAX_BYTES;
    segs[0].direction = VOS_DMA_DIR_TO_SERVER;
    segs[VOS_DMA_MAX_SEGMENTS] = segs[0];
    vos_dma_descriptor over_segs = {
        .op = VOS_DMA_OP_STREAM_TO_DEVICE,
        .request_id = 101U,
        .generation = ring.generation,
        .window_index = 0U,
        .transfer_length = VOS_DMA_MAX_SEGMENTS * VOS_DMA_SEGMENT_MAX_BYTES,
        .segments = segs,
        .segment_count = VOS_DMA_MAX_SEGMENTS + 1U
    };
    CHECK(vos_dma_submit(&ring, &over_segs, &sres, &slot_idx) != VOS_DMA_STATUS_OK,
          "segment count past max accepted");

    /* Segment larger than segment_max_bytes refused. */
    vos_dma_buffer_ref too_big_seg = {
        .session_index = 0U,
        .offset = 0U,
        .length = VOS_DMA_SEGMENT_MAX_BYTES + 1U,
        .direction = VOS_DMA_DIR_TO_SERVER,
        .content = VOS_DMA_CONTENT_OPAQUE_BYTES
    };
    vos_dma_descriptor bad_seg_desc = {
        .op = VOS_DMA_OP_STREAM_TO_DEVICE,
        .request_id = 102U,
        .generation = ring.generation,
        .window_index = 0U,
        .transfer_length = VOS_DMA_SEGMENT_MAX_BYTES + 1U,
        .segments = &too_big_seg,
        .segment_count = 1U
    };
    CHECK(vos_dma_submit(&ring, &bad_seg_desc, &sres, &slot_idx) != VOS_DMA_STATUS_OK,
          "omitted segment check: segment larger than segment_max_bytes accepted");

    /* Segment extending past session capability_bytes refused. */
    vos_dma_buffer_ref past_cap_seg = {
        .session_index = 0U,
        .offset = VOS_DMA_SEGMENT_MAX_BYTES + 1U,
        .length = VOS_DMA_SEGMENT_MAX_BYTES,
        .direction = VOS_DMA_DIR_TO_SERVER,
        .content = VOS_DMA_CONTENT_OPAQUE_BYTES
    };
    bad_seg_desc.request_id = 103U;
    bad_seg_desc.transfer_length = VOS_DMA_SEGMENT_MAX_BYTES;
    bad_seg_desc.segments = &past_cap_seg;
    CHECK(vos_dma_submit(&ring, &bad_seg_desc, &sres, &slot_idx) != VOS_DMA_STATUS_OK,
          "omitted segment check: segment past capability_bytes accepted");

    /* Direction mismatch in segment table refused. */
    vos_dma_buffer_ref wrong_dir_seg = {
        .session_index = 1U,
        .offset = 0U,
        .length = VOS_DMA_SEGMENT_MAX_BYTES,
        .direction = VOS_DMA_DIR_TO_SERVER,
        .content = VOS_DMA_CONTENT_OPAQUE_BYTES
    };
    bad_seg_desc.request_id = 104U;
    bad_seg_desc.segments = &wrong_dir_seg;
    CHECK(vos_dma_submit(&ring, &bad_seg_desc, &sres, &slot_idx) != VOS_DMA_STATUS_OK,
          "direction mismatch accepted in segment validation");

    /* Revoked session entry refused. */
    vos_dma_buffer_ref dead_cap_seg = {
        .session_index = 2U,
        .offset = 0U,
        .length = VOS_DMA_SEGMENT_MAX_BYTES,
        .direction = VOS_DMA_DIR_TO_SERVER,
        .content = VOS_DMA_CONTENT_OPAQUE_BYTES
    };
    bad_seg_desc.request_id = 105U;
    bad_seg_desc.segments = &dead_cap_seg;
    CHECK(vos_dma_submit(&ring, &bad_seg_desc, &sres, &slot_idx) != VOS_DMA_STATUS_OK,
          "invalid session capability accepted");

    /* Bad segment in second position refuses whole list. */
    vos_dma_buffer_ref mixed_segs[2] = {
        { .session_index = 0U, .offset = 0U, .length = 1024U,
          .direction = VOS_DMA_DIR_TO_SERVER, .content = VOS_DMA_CONTENT_OPAQUE_BYTES },
        { .session_index = 0U, .offset = (VOS_DMA_SEGMENT_MAX_BYTES * 2U) - 512U, .length = 1024U,
          .direction = VOS_DMA_DIR_TO_SERVER, .content = VOS_DMA_CONTENT_OPAQUE_BYTES }
    };
    bad_seg_desc.request_id = 106U;
    bad_seg_desc.transfer_length = 2048U;
    bad_seg_desc.segments = mixed_segs;
    bad_seg_desc.segment_count = 2U;
    CHECK(vos_dma_submit(&ring, &bad_seg_desc, &sres, &slot_idx) != VOS_DMA_STATUS_OK,
          "omitted segment check: second bad segment accepted");

    return 0;
}

static int test_cancellation_and_capacity(const vos_dma_config *cfg)
{
    const vos_dma_session_cap table[2] = {
        { .session_index = 0U, .permission = VOS_DMA_PERM_LOAD,
          .capability_bytes = VOS_DMA_SEGMENT_MAX_BYTES, .valid = 1U },
        { .session_index = 1U, .permission = VOS_DMA_PERM_STORE,
          .capability_bytes = VOS_DMA_SEGMENT_MAX_BYTES, .valid = 1U }
    };
    vos_dma_ring ring;
    CHECK(init_default_ring(&ring, cfg, table, 2U) == 1, "init failed");

    const vos_dma_buffer_ref seg_load = {
        .session_index = 0U, .offset = 0U, .length = 512U,
        .direction = VOS_DMA_DIR_TO_SERVER, .content = VOS_DMA_CONTENT_OPAQUE_BYTES
    };
    const vos_dma_buffer_ref seg_store = {
        .session_index = 1U, .offset = 0U, .length = 512U,
        .direction = VOS_DMA_DIR_TO_CLIENT, .content = VOS_DMA_CONTENT_OPAQUE_BYTES
    };

    /* 1. Unstarted SUBMITTED cancellable -> VOS_DMA_CANCELED. */
    const vos_dma_descriptor d1 = {
        .op = VOS_DMA_OP_STREAM_TO_DEVICE, .request_id = 201U,
        .generation = ring.generation, .window_index = 0U,
        .transfer_length = 512U, .segments = &seg_load, .segment_count = 1U
    };
    uint32_t s1 = 0U;
    CHECK(vos_dma_submit(&ring, &d1, NULL, &s1) == VOS_DMA_STATUS_OK, "submit d1 failed");
    CHECK(vos_dma_cancel(&ring, 201U, 0U) == VOS_DMA_CANCELED, "submitted cancel failed");
    CHECK(ring.slots[s1].state == VOS_DMA_TERMINAL && vos_dma_held_capabilities(&ring, s1) == 0U,
          "canceled submitted did not release");
    CHECK(vos_dma_cancel(&ring, 201U, 0U) == VOS_DMA_NOT_LIVE, "terminal op still cancellable");

    /* 2. Duplicate live request_id refused. */
    const vos_dma_descriptor d2 = {
        .op = VOS_DMA_OP_STREAM_FROM_DEVICE, .request_id = 202U,
        .generation = ring.generation, .window_index = 0U,
        .transfer_length = 512U, .segments = &seg_store, .segment_count = 1U
    };
    uint32_t s2 = 0U;
    uint32_t dup_slot = 0U;
    CHECK(vos_dma_submit(&ring, &d2, NULL, &s2) == VOS_DMA_STATUS_OK, "submit d2 failed");
    CHECK(vos_dma_submit(&ring, &d2, NULL, &dup_slot) == VOS_DMA_STATUS_REFUSED,
          "duplicate live request accepted");

    /* 3. ACCEPTED before commit point -> VOS_DMA_CANCELED; at/after commit point -> VOS_DMA_TOO_LATE. */
    const uint32_t commit_pt = cfg->ops[VOS_DMA_OP_STREAM_FROM_DEVICE].commit_index;
    CHECK(commit_pt >= 1U, "expected positive commit_index for stream_from_device");
    CHECK(vos_dma_accept(&ring, s2) == VOS_DMA_STATUS_OK, "accept d2 failed");
    CHECK(vos_dma_cancel(&ring, 202U, commit_pt) == VOS_DMA_TOO_LATE,
          "post-commit cancel accepted at commit_index");
    CHECK(ring.slots[s2].state == VOS_DMA_ACCEPTED, "too-late cancel altered state");
    CHECK(vos_dma_cancel(&ring, 202U, commit_pt - 1U) == VOS_DMA_CANCELED,
          "pre-commit cancel refused");
    CHECK(ring.slots[s2].state == VOS_DMA_TERMINAL && vos_dma_held_capabilities(&ring, s2) == 0U,
          "retained capability after completion by cancel");

    /* 4. Non-cancellable op (quiesce_window) -> VOS_DMA_NOT_LIVE. */
    const vos_dma_descriptor d3 = {
        .op = VOS_DMA_OP_QUIESCE_WINDOW, .request_id = 203U,
        .generation = ring.generation, .window_index = 0U,
        .transfer_length = 0U, .segments = NULL, .segment_count = 0U
    };
    uint32_t s3 = 0U;
    CHECK(vos_dma_submit(&ring, &d3, NULL, &s3) == VOS_DMA_STATUS_OK, "submit quiesce failed");
    CHECK(vos_dma_cancel(&ring, 203U, 0U) == VOS_DMA_NOT_LIVE,
          "non-cancellable op canceled");

    /* 5. Ring capacity bound: fill remaining slots then check one past full. */
    CHECK(init_default_ring(&ring, cfg, table, 2U) == 1, "re-init failed");
    for (uint32_t i = 0U; i < VOS_DMA_CAPACITY; ++i) {
        vos_dma_descriptor di = d1;
        di.request_id = 1000U + i;
        vos_dma_submit_result res = VOS_DMA_SUBMIT_WOULD_BLOCK;
        CHECK(vos_dma_submit(&ring, &di, &res, NULL) == VOS_DMA_STATUS_OK
              && res == VOS_DMA_SUBMIT_ENQUEUED,
              "fill to capacity failed");
    }
    vos_dma_descriptor past = d1;
    past.request_id = 2000U;
    vos_dma_submit_result past_res = VOS_DMA_SUBMIT_ENQUEUED;
    CHECK(vos_dma_submit(&ring, &past, &past_res, NULL) == VOS_DMA_STATUS_RESOURCE_EXHAUSTED
          && past_res == VOS_DMA_SUBMIT_WOULD_BLOCK,
          "submit past capacity did not report would_block");
    return 0;
}

static int test_reset_generation_and_quiescence(const vos_dma_config *cfg)
{
    const vos_dma_session_cap table[1] = {
        { .session_index = 0U, .permission = VOS_DMA_PERM_LOAD,
          .capability_bytes = VOS_DMA_SEGMENT_MAX_BYTES, .valid = 1U }
    };
    const vos_dma_buffer_ref seg = {
        .session_index = 0U, .offset = 0U, .length = 256U,
        .direction = VOS_DMA_DIR_TO_SERVER, .content = VOS_DMA_CONTENT_OPAQUE_BYTES
    };
    const vos_dma_descriptor d = {
        .op = VOS_DMA_OP_STREAM_TO_DEVICE, .request_id = 301U,
        .generation = cfg->initial_generation, .window_index = 0U,
        .transfer_length = 256U, .segments = &seg, .segment_count = 1U
    };

    /* Test reset across every lifecycle state: FREE, WRITING, SUBMITTED, ACCEPTED, TERMINAL, RECLAIMED. */
    for (int target_state = VOS_DMA_FREE; target_state <= VOS_DMA_RECLAIMED; ++target_state) {
        vos_dma_ring ring;
        CHECK(init_default_ring(&ring, cfg, table, 1U) == 1, "init failed");
        const uint32_t old_gen = ring.generation;
        if (target_state == VOS_DMA_WRITING) {
            ring.slots[0].state = VOS_DMA_WRITING;
        } else if (target_state >= VOS_DMA_SUBMITTED) {
            uint32_t idx = 0U;
            CHECK(vos_dma_submit(&ring, &d, NULL, &idx) == VOS_DMA_STATUS_OK, "submit failed");
            if (target_state >= VOS_DMA_ACCEPTED) {
                CHECK(vos_dma_accept(&ring, idx) == VOS_DMA_STATUS_OK, "accept failed");
            }
            if (target_state >= VOS_DMA_TERMINAL) {
                CHECK(vos_dma_complete(&ring, idx, VOS_DMA_STATUS_OK) == VOS_DMA_STATUS_OK,
                      "complete failed");
            }
            if (target_state == VOS_DMA_RECLAIMED) {
                CHECK(vos_dma_reclaim(&ring, idx) == VOS_DMA_STATUS_OK, "reclaim failed");
            }
        }
        const uint32_t qbound = cfg->ops[VOS_DMA_OP_STREAM_TO_DEVICE].quiescence_bound;
        CHECK(vos_dma_reset_session(&ring, 1U, qbound) == 1, "quiesced reset failed");
        CHECK(ring.generation == old_gen + 1U && ring.produced == 0U
              && ring.consumed == 0U && ring.armed == 0U
              && ring.slots[0].state == VOS_DMA_FREE
              && vos_dma_held_capabilities(&ring, 0U) == 0U,
              "reset did not clear indices and state");

        /* Stale generation descriptor must be refused; new generation accepted. */
        CHECK(vos_dma_submit(&ring, &d, NULL, NULL) == VOS_DMA_STATUS_REFUSED,
              "stale generation accepted after reset");
        vos_dma_descriptor fresh = d;
        fresh.generation = ring.generation;
        CHECK(vos_dma_submit(&ring, &fresh, NULL, NULL) == VOS_DMA_STATUS_OK,
              "fresh generation refused after reset");
    }

    /* Missing quiescence (!dma_quiesced) must fail-stop and refuse generation publish. */
    vos_dma_ring ring;
    CHECK(init_default_ring(&ring, cfg, table, 1U) == 1, "init failed");
    const uint32_t initial_gen = ring.generation;
    uint32_t slot_idx = 0U;
    CHECK(vos_dma_submit(&ring, &d, NULL, &slot_idx) == VOS_DMA_STATUS_OK, "submit failed");
    CHECK(vos_dma_accept(&ring, slot_idx) == VOS_DMA_STATUS_OK, "accept failed");
    CHECK(vos_dma_reset_session(&ring, 0U, 0U) == 0,
          "missing quiescence fail-stop: unquiesced reset succeeded");
    CHECK(ring.fail_stopped == 1U && ring.generation == initial_gen
          && vos_dma_held_capabilities(&ring, slot_idx) == 0U,
          "missing quiescence fail-stop: ring did not fail-stop");
    vos_dma_descriptor post_fault = d;
    post_fault.request_id = 302U;
    CHECK(vos_dma_submit(&ring, &post_fault, NULL, NULL) == VOS_DMA_STATUS_DEVICE_FAULT,
          "missing quiescence fail-stop: fail-stopped ring accepted submission");

    /* Exceeding op quiescence_bound must fail-stop. */
    CHECK(init_default_ring(&ring, cfg, table, 1U) == 1, "init failed");
    CHECK(vos_dma_submit(&ring, &d, NULL, &slot_idx) == VOS_DMA_STATUS_OK, "submit failed");
    CHECK(vos_dma_accept(&ring, slot_idx) == VOS_DMA_STATUS_OK, "accept failed");
    const uint32_t qbound = cfg->ops[VOS_DMA_OP_STREAM_TO_DEVICE].quiescence_bound;
    CHECK(vos_dma_enforce_quiescence(&ring, slot_idx, 1U, qbound) == VOS_DMA_STATUS_OK,
          "quiescence at exact bound rejected");
    CHECK(vos_dma_enforce_quiescence(&ring, slot_idx, 1U, qbound + 1U) == VOS_DMA_STATUS_DEVICE_FAULT,
          "missing quiescence fail-stop: exceeded quiescence bound accepted");
    CHECK(ring.fail_stopped == 1U, "missing quiescence fail-stop: fail_stopped not set");

    return 0;
}

int main(void)
{
    const vos_dma_config cfg = vos_dma_reference_config();
    if (test_directions_and_segments(&cfg) != 0) {
        return 1;
    }
    if (test_cancellation_and_capacity(&cfg) != 0) {
        return 1;
    }
    if (test_reset_generation_and_quiescence(&cfg) != 0) {
        return 1;
    }
    fprintf(stderr,
            "ok dma-service C controls: segments, directions, cancel, quiescence fail-stop, terminal release, generation\n");
    return 0;
}
