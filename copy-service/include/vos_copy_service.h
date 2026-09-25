/* SPDX-License-Identifier: Apache-2.0 */
#ifndef VOS_COPY_SERVICE_H
#define VOS_COPY_SERVICE_H

#include <stddef.h>
#include <stdint.h>
#include <stdatomic.h>
#include "copy_service_config.h"

/* Pure ordered helpers require a valid view and bounded observation counters.
 * They are separate from the atomic payload ring below. API pointers must name
 * disjoint accessible objects; request records and source bytes remain immutable
 * for the duration of each submit. Reset requires both endpoints quiescent. */
typedef struct { uint32_t produced, consumed; } vos_copy_view;
typedef enum { VOS_COPY_FREE, VOS_COPY_WRITING, VOS_COPY_SUBMITTED,
               VOS_COPY_ACCEPTED, VOS_COPY_TERMINAL, VOS_COPY_RECLAIMED } vos_copy_state;
typedef enum { VOS_COPY_RESERVE, VOS_COPY_PUBLISH, VOS_COPY_ACCEPT,
               VOS_COPY_COMPLETE, VOS_COPY_RECLAIM, VOS_COPY_MALFORMED } vos_copy_event;
typedef enum { VOS_COPY_RESET_SIGNAL, VOS_COPY_RESET_DRAIN } vos_copy_reset;
typedef enum { VOS_COPY_DRAIN, VOS_COPY_ARM, VOS_COPY_RECHECK, VOS_COPY_SLEEP } vos_copy_act;
typedef struct {
    vos_copy_state state;
    uint32_t readers, validated, request;
} vos_copy_slot;
typedef struct {
    vos_copy_view view;
    uint32_t armed, signals, seen, drained, asleep;
} vos_copy_world;
typedef struct {
    vos_copy_slot life;
    size_t length;
    uint8_t bytes[VOS_COPY_MAX_PAYLOAD];
} vos_copy_payload;
typedef struct {
    _Atomic uint32_t produced, consumed, armed;
    uint32_t generation;
    vos_copy_payload slots[VOS_COPY_CAPACITY];
} vos_copy_ring;
typedef struct {
    uint32_t generation, request, operation;
    const uint8_t *source;
    size_t extent, length;
} vos_copy_request;

uint32_t vos_copy_occupancy(vos_copy_view view);
int vos_copy_view_valid(vos_copy_view view);
int vos_copy_publish(vos_copy_view *view);
int vos_copy_take_index(vos_copy_view *view);
int vos_copy_batch(vos_copy_view *view, size_t count, uint32_t *results);
int vos_copy_advance(vos_copy_slot *slot, vos_copy_event event);
/* Source/destination extents must be accessible and disjoint; no concurrent
 * writer may modify source bytes until staging returns (ordinary C11 memory). */
int vos_copy_stage(uint8_t *destination, size_t capacity, const uint8_t *source,
                   size_t extent, size_t length);
void vos_copy_producer(vos_copy_world *world, vos_copy_reset reset);
void vos_copy_consumer(vos_copy_world *world, vos_copy_reset reset,
                       uint32_t budget, vos_copy_act act);
void vos_copy_activation(vos_copy_world *world, vos_copy_reset reset,
                         uint32_t budget, uint32_t publication_step);
void vos_copy_init(vos_copy_ring *ring);
int vos_copy_submit(vos_copy_ring *ring, uint32_t generation, uint32_t request,
                    uint32_t operation, const uint8_t *source,
                    size_t extent, size_t length, uint32_t *signal);
int vos_copy_take(vos_copy_ring *ring, uint8_t *destination, size_t capacity,
                  size_t *length, uint32_t *request);
int vos_copy_prepare_sleep(vos_copy_ring *ring);
int vos_copy_submit_batch(vos_copy_ring *ring, const vos_copy_request *requests,
                          size_t count, uint32_t *results, uint32_t *signals);

#endif
