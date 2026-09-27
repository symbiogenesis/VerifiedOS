// SPDX-License-Identifier: Apache-2.0
#include "vos_effects.h"

static void effect_clear_caps(vos_cap_t *slots, uint32_t count)
{
    uint32_t i;
    vos_cap_t zero = {0};
    for (i = 0; i < count; ++i)
        slots[i] = zero;
}

static void effect_clear_unit(struct vos_kernel_unit *unit)
{
    uint32_t i, depth;
    volatile uint8_t *bytes = unit->bytes;
    for (i = 0; i < VOS_KERNEL_PRIVATE_BYTES; ++i)
        bytes[i] = 0;
    effect_clear_caps(unit->saved, 33);
    for (depth = 0; depth < VOS_KERNEL_FRAME_DEPTH; ++depth)
        effect_clear_caps(unit->frames[depth], VOS_KERNEL_FRAME_SLOTS);
    effect_clear_caps(unit->grants, VOS_SUPERVISOR_UNITS);
    unit->running = 0;
    unit->pending = 0;
    unit->waiting = 0;
    unit->inflight = 0;
    unit->depth = 0;
}

int vos_kernel_effect_init(struct vos_kernel_effect_state *state,
                           const struct vos_supervisor_manifest *manifest,
                           uint64_t epoch)
{
    uint32_t i;
    if (state == 0 || !vos_supervisor_manifest_ok(manifest))
        return 0;
    state->manifest = *manifest;
    state->epoch = epoch;
    state->snapshot.number = epoch;
    state->locked = 0;
    state->bound = 0;
    state->polls = 0;
    state->started = 0;
    state->resident_clean = 0;
    state->loans = 0;
    state->devices = 0;
    state->retirement_pending = 0;
    state->bitmap = 0;
    state->clock = 0;
    effect_clear_caps(state->roots, VOS_SUPERVISOR_UNITS);
    for (i = 0; i < VOS_SUPERVISOR_UNITS; ++i) {
        effect_clear_unit(&state->unit[i]);
        state->unit[i].generation = epoch;
        state->snapshot.retired[i] = 0;
        state->masks[i] = 0;
    }
    return 1;
}

int vos_kernel_effect_bind(struct vos_kernel_effect_state *state,
                           const vos_cap_t *roots, const uint64_t *masks,
                           volatile uint64_t *bitmap, volatile uint64_t *clock,
                           uint32_t polls)
{
    uint32_t i;
    uint64_t seen = 0;
    if (state == 0 || roots == 0 || masks == 0 || bitmap == 0 || clock == 0 ||
        polls == 0 || polls > 1048576U || state->bound || state->locked ||
        state->started || state->manifest.units > VOS_SUPERVISOR_UNITS)
        return 0;
    for (i = 0; i < state->manifest.units; ++i) {
        if (masks[i] == 0 || (seen & masks[i]) != 0)
            return 0;
        seen |= masks[i];
    }
    for (i = 0; i < state->manifest.units; ++i) {
        state->roots[i] = roots[i];
        state->masks[i] = masks[i];
    }
    state->bitmap = bitmap;
    state->clock = clock;
    state->polls = polls;
    state->bound = 1;
    return 1;
}

int vos_kernel_retire(struct vos_kernel_effect_state *state, uint32_t members,
                       struct vos_completion *completion)
{
    uint32_t i;
    uint64_t mask = 0;
    struct vos_completion done = {0};
    if (state == 0 || completion == 0 || !state->bound || state->locked ||
        members == 0 || members != state->manifest.restart_members ||
        state->epoch == UINT64_MAX || state->loans || state->devices)
        return 0;
    /* All possible holders outside the victim refuse its destruction. The
     * immutable manifest, rather than a possibly empty current grant table,
     * closes authority that an interrupted invocation may have copied. */
    for (i = 0; i < state->manifest.units; ++i) {
        if (((members & (1U << i)) == 0 &&
             (state->manifest.edges[i] & members) != 0) ||
            ((members & (1U << i)) != 0 && state->unit[i].inflight))
            return 0;
        if ((members & (1U << i)) != 0)
            mask |= state->masks[i];
    }
    state->retirement_pending = 1;
    *state->bitmap |= mask;
    done.bits_published = (*state->bitmap & mask) == mask;
    for (i = 0; i < state->manifest.units; ++i) {
        if ((members & (1U << i)) != 0) {
            effect_clear_unit(&state->unit[i]);
            state->started &= ~(1U << i);
        }
        state->snapshot.retired[i] |= members;
    }
    ++state->epoch;
    state->snapshot.number = state->epoch;
    done.epoch_advanced = 1;
    done.resident_roots_cleared = state->resident_clean != 0;
    done.saved_contexts_filtered = 1;
    done.loans_cancelled = state->loans == 0;
    done.device_boundary_reached = state->devices == 0;
    state->resident_clean = 0;
    if (vos_semantic_completion(&done))
        state->retirement_pending = 0;
    *completion = done;
    return 1;
}

int vos_kernel_wait(struct vos_kernel_effect_state *state, uint32_t delay)
{
    uint32_t poll;
    uint64_t start, now;
    if (state == 0 || !state->bound || state->locked || delay > state->manifest.ceiling)
        return 0;
    start = *state->clock;
    for (poll = 0; poll < state->polls; ++poll) {
        now = *state->clock;
        if (now >= start && now - start >= delay)
            return 1;
    }
    return 0;
}

int vos_kernel_acquire(struct vos_kernel_effect_state *state,
                        struct vos_supervisor_epoch *snapshot, uint64_t *epoch)
{
    if (state == 0 || snapshot == 0 || epoch == 0 || !state->bound || state->locked)
        return 0;
    state->locked = 1;
    *snapshot = state->snapshot;
    *epoch = state->epoch;
    return 1;
}

int vos_kernel_start(struct vos_kernel_effect_state *state,
                      const struct vos_supervisor_start *request)
{
    uint32_t i, unit;
    if (state == 0 || request == 0 || !state->bound || !state->locked || state->retirement_pending ||
        !vos_supervisor_request_current(&state->manifest, &state->snapshot,
                                        state->epoch, request))
        return 0;
    unit = request->unit;
    if (state->unit[unit].running || (request->grants & ~state->started) != 0)
        return 0;
    effect_clear_caps(state->unit[unit].grants, VOS_SUPERVISOR_UNITS);
    for (i = 0; i < state->manifest.units; ++i)
        if ((request->grants & (1U << i)) != 0)
            state->unit[unit].grants[i] = state->roots[i];
    state->unit[unit].generation = state->epoch;
    state->unit[unit].running = 1;
    state->started |= 1U << unit;
    return 1;
}

void vos_kernel_release(struct vos_kernel_effect_state *state)
{
    state->locked = 0;
}

static int effect_current(const struct vos_kernel_effect_state *state,
                           uint32_t unit, uint64_t generation)
{
    return state != 0 && state->bound && !state->locked &&
           unit < state->manifest.units && state->unit[unit].running &&
           state->unit[unit].generation == generation;
}

int vos_kernel_notify(struct vos_kernel_effect_state *state, uint32_t unit,
                       uint64_t generation)
{
    if (!effect_current(state, unit, generation))
        return 0;
    state->unit[unit].pending = 1;
    state->unit[unit].waiting = 0;
    return 1;
}

int vos_kernel_copy_wait(struct vos_kernel_effect_state *state, uint32_t unit,
                          uint64_t generation)
{
    if (!effect_current(state, unit, generation) || state->unit[unit].inflight)
        return -1;
    if (state->unit[unit].pending) {
        state->unit[unit].pending = 0;
        state->unit[unit].waiting = 0;
        return 0;
    }
    state->unit[unit].waiting = 1;
    return 1;
}

int vos_kernel_copy_begin(struct vos_kernel_effect_state *state, uint32_t unit,
                           uint64_t generation)
{
    if (!effect_current(state, unit, generation) || state->unit[unit].inflight)
        return 0;
    state->unit[unit].inflight = 1;
    return 1;
}

int vos_kernel_copy_complete(struct vos_kernel_effect_state *state, uint32_t unit,
                              uint64_t generation)
{
    if (!effect_current(state, unit, generation) || !state->unit[unit].inflight)
        return 0;
    state->unit[unit].inflight = 0;
    return 1;
}

int vos_kernel_frame_enter(struct vos_kernel_effect_state *state, uint32_t unit,
                            uint64_t generation)
{
    if (!effect_current(state, unit, generation) ||
        state->unit[unit].depth >= VOS_KERNEL_FRAME_DEPTH)
        return 0;
    effect_clear_caps(state->unit[unit].frames[state->unit[unit].depth],
                      VOS_KERNEL_FRAME_SLOTS);
    ++state->unit[unit].depth;
    return 1;
}

int vos_kernel_frame_leave(struct vos_kernel_effect_state *state, uint32_t unit,
                            uint64_t generation)
{
    if (!effect_current(state, unit, generation) || state->unit[unit].depth == 0)
        return 0;
    --state->unit[unit].depth;
    effect_clear_caps(state->unit[unit].frames[state->unit[unit].depth],
                      VOS_KERNEL_FRAME_SLOTS);
    return 1;
}

static int effect_retire(void *state, uint32_t members, struct vos_completion *done)
{ return vos_kernel_retire(state, members, done); }
static int effect_wait(void *state, uint32_t delay)
{ return vos_kernel_wait(state, delay); }
static int effect_acquire(void *state, struct vos_supervisor_epoch *snapshot, uint64_t *epoch)
{ return vos_kernel_acquire(state, snapshot, epoch); }
static int effect_start(void *state, const struct vos_supervisor_start *request)
{ return vos_kernel_start(state, request); }
static void effect_release(void *state)
{ vos_kernel_release(state); }

const struct vos_supervisor_effects vos_kernel_supervisor_effects = {
    effect_retire, effect_wait, effect_acquire, effect_start, effect_release
};
