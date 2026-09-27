// SPDX-License-Identifier: Apache-2.0
#include "vos_copy_service.h"

uint32_t vos_copy_occupancy(const vos_copy_view *view)
{
    return (view->produced + VOS_COPY_INDEX_SPAN - view->consumed) % VOS_COPY_INDEX_SPAN;
}

int vos_copy_view_valid(const vos_copy_view *view)
{
    return view->produced < VOS_COPY_INDEX_SPAN && view->consumed < VOS_COPY_INDEX_SPAN
        && vos_copy_occupancy(view) <= VOS_COPY_CAPACITY;
}

int vos_copy_publish(vos_copy_view *view)
{
    if (!vos_copy_view_valid(view) || vos_copy_occupancy(view) >= VOS_COPY_CAPACITY)
        return 0;
    view->produced = (view->produced + 1) % VOS_COPY_INDEX_SPAN;
    return 1;
}

int vos_copy_take_index(vos_copy_view *view)
{
    if (!vos_copy_view_valid(view) || vos_copy_occupancy(view) == 0)
        return 0;
    view->consumed = (view->consumed + 1) % VOS_COPY_INDEX_SPAN;
    return 1;
}

int vos_copy_batch(vos_copy_view *view, size_t count, uint32_t *results)
{
    size_t i;
    if (!vos_copy_view_valid(view) || count > VOS_COPY_MAX_BATCH)
        return 0;
    for (i = 0; i < count; ++i)
        results[i] = (uint32_t)vos_copy_publish(view);
    return 1;
}

int vos_copy_advance(vos_copy_slot *slot, vos_copy_event event)
{
    vos_copy_state next;
    if (event == VOS_COPY_RESERVE) {
        if (slot->state != VOS_COPY_FREE) return 0;
        next = VOS_COPY_WRITING;
    } else if (event == VOS_COPY_PUBLISH) {
        if (slot->state != VOS_COPY_WRITING) return 0;
        next = VOS_COPY_SUBMITTED;
    } else if (event == VOS_COPY_ACCEPT) {
        if (slot->state != VOS_COPY_SUBMITTED || !slot->validated) return 0;
        next = VOS_COPY_ACCEPTED;
    } else if (event == VOS_COPY_COMPLETE) {
        if (slot->state != VOS_COPY_ACCEPTED) return 0;
        next = VOS_COPY_TERMINAL;
    } else if (event == VOS_COPY_RECLAIM) {
        if (slot->state != VOS_COPY_TERMINAL || slot->readers != 0) return 0;
        next = VOS_COPY_RECLAIMED;
    } else if (event == VOS_COPY_MALFORMED) {
        if (slot->state != VOS_COPY_SUBMITTED) return 0;
        next = VOS_COPY_TERMINAL;
    } else return 0;
    slot->state = next;
    return 1;
}

int vos_copy_stage(uint8_t *destination, size_t capacity, const uint8_t *source,
                   size_t extent, size_t length)
{
    size_t i;
    /* Metadata is passed by value. Once staged, consumers never reread source.
     * The caller supplies disjoint, accessible extents and excludes concurrent
     * source writes until this function returns, as required by C11. */
    if (length > extent || length > capacity) return 0;
    for (i = 0; i < length; ++i) destination[i] = source[i];
    return 1;
}

void vos_copy_producer(vos_copy_world *world, vos_copy_reset reset)
{
    if (!vos_copy_publish(&world->view)) return;
    if (world->armed) ++world->signals;
    if (reset == VOS_COPY_RESET_SIGNAL) world->armed = 0;
}

void vos_copy_consumer(vos_copy_world *world, vos_copy_reset reset,
                       uint32_t budget, vos_copy_act act)
{
    uint32_t count;
    if (act == VOS_COPY_DRAIN) {
        count = vos_copy_occupancy(&world->view);
        if (count > budget) count = budget;
        world->view.consumed = (world->view.consumed + count) % VOS_COPY_INDEX_SPAN;
        if (reset == VOS_COPY_RESET_DRAIN) world->armed = 0;
        world->seen = world->view.produced;
        world->drained += count;
    } else if (act == VOS_COPY_ARM) {
        world->armed = 1;
    } else if (act == VOS_COPY_RECHECK) {
        world->seen = world->view.produced;
    } else if (act == VOS_COPY_SLEEP) {
        world->asleep = world->armed && world->seen == world->view.consumed;
    }
}

void vos_copy_activation(vos_copy_world *world, vos_copy_reset reset,
                         uint32_t budget, uint32_t publication_step)
{
    uint32_t step;
    if (publication_step > 4) publication_step = 4;
    for (step = 0; step <= 4; ++step) {
        if (step == publication_step) vos_copy_producer(world, reset);
        if (step < 4) vos_copy_consumer(world, reset, budget, (vos_copy_act)step);
    }
}

void vos_copy_init_generation_slots(vos_copy_ring *ring, uint32_t generation)
{
    uint32_t i;
    ring->generation = generation;
    for (i = 0; i < VOS_COPY_CAPACITY; ++i) {
        ring->slots[i].life.state = VOS_COPY_FREE;
        ring->slots[i].life.readers = 0;
        ring->slots[i].life.validated = 0;
        ring->slots[i].life.request = 0;
        ring->slots[i].length = 0;
    }
}

void vos_copy_init_slots(vos_copy_ring *ring)
{
    vos_copy_init_generation_slots(ring, VOS_COPY_GENERATION);
}

int vos_copy_submit_snapshot(vos_copy_ring *ring, const vos_copy_request *input,
                              vos_copy_view *view)
{
    uint32_t i;
    vos_copy_payload *slot;
    uint32_t generation = input->generation, request = input->request;
    uint32_t operation = input->operation;
    const uint8_t *source = input->source;
    size_t extent = input->extent, length = input->length;
    if (!vos_copy_view_valid(view) || generation != ring->generation
        || vos_copy_occupancy(view) >= VOS_COPY_CAPACITY
        || operation >= VOS_COPY_OPERATION_COUNT || length > extent
        || length > vos_copy_payload_limit(operation)) return 0;
    /* Request identifiers are producer-written; consumer-owned lifecycle fields
     * are never scanned. An acquired tail conservatively delimits live IDs. */
    for (i = 0; i < vos_copy_occupancy(view); ++i)
        if (ring->slots[(view->consumed + i) % VOS_COPY_CAPACITY].life.request == request)
            return 0;
    slot = &ring->slots[view->produced % VOS_COPY_CAPACITY];
    if ((slot->life.state != VOS_COPY_FREE && slot->life.state != VOS_COPY_RECLAIMED)
        || slot->life.readers != 0) return 0;
    /* Re-entry to Free is producer-owned only after the previous consumption. */
    slot->life.state = VOS_COPY_FREE;
    slot->life.request = request;
    slot->life.validated = 0;
    (void)vos_copy_advance(&slot->life, VOS_COPY_RESERVE);
    (void)vos_copy_stage(slot->bytes, VOS_COPY_MAX_PAYLOAD, source, extent, length);
    slot->length = length;
    slot->life.validated = 1;
    (void)vos_copy_advance(&slot->life, VOS_COPY_PUBLISH);
    (void)vos_copy_publish(view);
    return 1;
}

int vos_copy_take_snapshot(vos_copy_ring *ring, uint8_t *destination, size_t capacity,
                            size_t *length, uint32_t *request, vos_copy_view *view)
{
    vos_copy_payload *slot;
    if (!vos_copy_view_valid(view) || vos_copy_occupancy(view) == 0)
        return 0;
    slot = &ring->slots[view->consumed % VOS_COPY_CAPACITY];
    if (slot->life.state != VOS_COPY_SUBMITTED || !slot->life.validated
        || slot->life.readers != 0 || slot->length > capacity) return 0;
    (void)vos_copy_advance(&slot->life, VOS_COPY_ACCEPT);
    slot->life.readers = 1;
    (void)vos_copy_stage(destination, capacity, slot->bytes, slot->length, slot->length);
    *length = slot->length;
    *request = slot->life.request;
    slot->life.readers = 0;
    (void)vos_copy_advance(&slot->life, VOS_COPY_COMPLETE);
    (void)vos_copy_advance(&slot->life, VOS_COPY_RECLAIM);
    (void)vos_copy_take_index(view);
    return 1;
}

#ifndef VOS_COPY_TARGET
void vos_copy_init(vos_copy_ring *ring)
{
    (void)vos_copy_init_generation(ring, VOS_COPY_GENERATION);
}

int vos_copy_init_generation(vos_copy_ring *ring, uint32_t generation)
{
    if (generation == 0) return 0;
    vos_copy_index_store(&ring->produced, 0);
    vos_copy_index_store(&ring->consumed, 0);
    vos_copy_word_store(&ring->armed, 0);
    vos_copy_init_generation_slots(ring, generation);
    return 1;
}

int vos_copy_submit(vos_copy_ring *ring, uint32_t generation, uint32_t request,
                    uint32_t operation, const uint8_t *source,
                    size_t extent, size_t length, uint32_t *signal)
{
    vos_copy_view view;
    vos_copy_request input;
    view.produced = vos_copy_index_load(&ring->produced);
    view.consumed = vos_copy_index_load(&ring->consumed);
    input.generation = generation; input.request = request;
    input.operation = operation; input.source = source;
    input.extent = extent; input.length = length;
    if (!vos_copy_submit_snapshot(ring, &input, &view)) return 0;
    vos_copy_index_store(&ring->produced, view.produced);
    *signal = vos_copy_word_exchange(&ring->armed, 0);
    return 1;
}

int vos_copy_take(vos_copy_ring *ring, uint8_t *destination, size_t capacity,
                  size_t *length, uint32_t *request)
{
    vos_copy_view view;
    view.produced = vos_copy_index_load(&ring->produced);
    view.consumed = vos_copy_index_load(&ring->consumed);
    if (!vos_copy_take_snapshot(ring, destination, capacity, length, request, &view)) return 0;
    vos_copy_index_store(&ring->consumed, view.consumed);
    return 1;
}

int vos_copy_prepare_sleep(vos_copy_ring *ring)
{
    uint32_t produced, consumed;
    /* Invoke after draining the admitted batch. A false answer yields to the
     * next activation with backlog. A true answer permits the kernel's wait. */
    vos_copy_word_store(&ring->armed, 1);
    produced = vos_copy_index_load(&ring->produced);
    consumed = vos_copy_index_load(&ring->consumed);
    return produced == consumed;
}

int vos_copy_submit_batch(vos_copy_ring *ring, const vos_copy_request *requests,
                          size_t count, uint32_t *results, uint32_t *signals)
{
    size_t i;
    if (count > VOS_COPY_MAX_BATCH) return 0;
    for (i = 0; i < count; ++i) {
        vos_copy_request request = requests[i];
        uint32_t signal = 0;
        results[i] = (uint32_t)vos_copy_submit(ring, request.generation, request.request,
                         request.operation, request.source, request.extent, request.length, &signal);
        signals[i] = signal;
    }
    return 1;
}

#endif
