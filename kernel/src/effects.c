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
    uint8_t *bytes = unit->bytes;
    for (i = 0; i < VOS_KERNEL_PRIVATE_BYTES; ++i)
        bytes[i] = 0;
    for (i = 0; i < unit->owned_length; ++i)
        unit->owned_bytes[i] = 0;
    effect_clear_caps(unit->owned_caps, unit->owned_count);
    effect_clear_caps(unit->saved, 33);
    for (depth = 0; depth < VOS_KERNEL_FRAME_DEPTH; ++depth)
        effect_clear_caps(unit->frames[depth], VOS_KERNEL_FRAME_SLOTS);
    effect_clear_caps(unit->grants, VOS_SUPERVISOR_UNITS);
    unit->running = 0;
    unit->pending = 0;
    unit->poll_hint = 0;
    unit->inflight = 0;
    unit->depth = 0;
}

int vos_kernel_effect_init(struct vos_kernel_effect_state *state,
                           const struct vos_supervisor_manifest *manifest,
                           uint64_t epoch)
{
    uint32_t i;
    if (state == 0 || !vos_supervisor_manifest_ok(manifest) ||
        manifest->units > VOS_KERNEL_EFFECT_UNITS)
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
    state->prepared_mask = 0;
    state->publication_epoch = epoch;
    state->published_mask = 0;
    state->wait_epoch = epoch;
    state->wait_start = 0;
    state->wait_now = 0;
    state->wait_delay = 0;
    state->wait_ready = 0;
    state->wait_seen = 0;
    state->bitmap = 0;
    state->clock = 0;
    effect_clear_caps(state->roots, VOS_KERNEL_EFFECT_UNITS);
    for (i = 0; i < VOS_SUPERVISOR_UNITS; ++i)
        state->snapshot.retired[i] = 0;
    for (i = 0; i < VOS_KERNEL_EFFECT_UNITS; ++i) {
        state->unit[i].owned_bytes = 0;
        state->unit[i].owned_length = 0;
        state->unit[i].owned_caps = 0;
        state->unit[i].owned_count = 0;
        effect_clear_unit(&state->unit[i]);
        state->unit[i].generation = epoch;
        state->masks[i] = 0;
    }
    return 1;
}

int vos_kernel_effect_bind(struct vos_kernel_effect_state *state,
                           const vos_cap_t *roots, const uint64_t *masks,
                           uint64_t *bitmap, uint64_t *clock,
                           uint32_t polls)
{
    uint32_t i;
    uint64_t seen = 0;
    if (state == 0 || roots == 0 || masks == 0 || bitmap == 0 || clock == 0 ||
        polls == 0 || polls > 1048576U || state->bound || state->locked ||
        state->started || state->manifest.units > VOS_KERNEL_EFFECT_UNITS)
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

int vos_kernel_own(struct vos_kernel_effect_state *state, uint32_t unit,
                    uint8_t *bytes, uint32_t length,
                    vos_cap_t *caps, uint32_t count)
{
    if (state == 0 || state->bound || state->locked ||
        unit >= state->manifest.units || length > 524288U || count > 128U ||
        (length != 0 && bytes == 0) || (count != 0 && caps == 0))
        return 0;
    state->unit[unit].owned_bytes = bytes;
    state->unit[unit].owned_length = length;
    state->unit[unit].owned_caps = caps;
    state->unit[unit].owned_count = count;
    return 1;
}

static uint64_t effect_mask(const struct vos_kernel_effect_state *state,
                             uint32_t members)
{
    uint32_t i;
    uint64_t mask = 0;
    if (state == 0 || !state->bound || state->locked || members == 0 ||
        members != state->manifest.restart_members ||
        state->epoch == UINT64_MAX || state->loans || state->devices)
        return 0;
    for (i = 0; i < state->manifest.units; ++i) {
        if (((members & (1U << i)) == 0 &&
             (state->manifest.edges[i] & members) != 0) ||
            ((members & (1U << i)) != 0 && state->unit[i].inflight))
            return 0;
        if ((members & (1U << i)) != 0)
            mask |= state->masks[i];
    }
    return mask;
}

uint64_t vos_kernel_retirement_mask(struct vos_kernel_effect_state *state,
                                    uint32_t members)
{
    uint64_t mask = effect_mask(state, members);
    if (mask == 0 || state->retirement_pending)
        return 0;
    state->retirement_pending = 1;
    state->prepared_mask = mask;
    state->publication_epoch = state->epoch;
    state->published_mask = 0;
    return mask;
}

int vos_kernel_publication(struct vos_kernel_effect_state *state, uint64_t epoch,
                            uint64_t mask, uint64_t observed)
{
    if (state == 0 || !state->retirement_pending || state->published_mask != 0 ||
        epoch != state->epoch || epoch != state->publication_epoch ||
        mask == 0 || mask != state->prepared_mask || (observed & mask) != mask)
        return 0;
    state->published_mask = mask;
    return 1;
}

int vos_kernel_retire(struct vos_kernel_effect_state *state, uint32_t members,
                       struct vos_completion *completion)
{
    uint32_t i;
    uint64_t mask = effect_mask(state, members);
    struct vos_completion done = {0};
    if (mask == 0 || completion == 0 || !state->retirement_pending ||
        mask != state->prepared_mask || state->publication_epoch != state->epoch)
        return 0;
    done.bits_published = state->published_mask == mask;
    state->prepared_mask = 0;
    state->published_mask = 0;
    for (i = 0; i < state->manifest.units; ++i) {
        if ((members & (1U << i)) != 0) {
            effect_clear_unit(&state->unit[i]);
            state->started &= ~(1U << i);
        }
        state->snapshot.retired[i] |= members;
    }
    ++state->epoch;
    state->snapshot.number = state->epoch;
    state->wait_ready = 0;
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

int vos_kernel_wait_sample(struct vos_kernel_effect_state *state, uint64_t epoch,
                            uint32_t delay,
                            uint64_t start, uint64_t now)
{
    if (state == 0 || !state->bound || state->locked || state->wait_ready ||
        state->retirement_pending || epoch != state->epoch ||
        (state->wait_seen && start <= state->wait_now) ||
        delay > state->manifest.ceiling ||
        now < start || now - start < delay)
        return 0;
    state->wait_epoch = state->epoch;
    state->wait_delay = delay;
    state->wait_start = start;
    state->wait_now = now;
    state->wait_ready = 1;
    state->wait_seen = 1;
    return 1;
}

int vos_kernel_wait(struct vos_kernel_effect_state *state, uint32_t delay)
{
    if (state == 0 || !state->bound || state->locked || !state->wait_ready ||
        state->wait_epoch != state->epoch || state->wait_delay != delay ||
        state->wait_now < state->wait_start ||
        state->wait_now - state->wait_start < delay)
        return 0;
    state->wait_ready = 0;
    return 1;
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
    return state != 0 && state->bound && !state->locked && !state->retirement_pending &&
           unit < state->manifest.units && state->unit[unit].running &&
           state->unit[unit].generation == generation;
}

int vos_kernel_notify(struct vos_kernel_effect_state *state, uint32_t unit,
                       uint64_t generation)
{
    if (!effect_current(state, unit, generation))
        return 0;
    state->unit[unit].pending = 1;
    state->unit[unit].poll_hint = 0;
    return 1;
}

int vos_kernel_copy_wait(struct vos_kernel_effect_state *state, uint32_t unit,
                          uint64_t generation)
{
    if (!effect_current(state, unit, generation) || state->unit[unit].inflight)
        return -1;
    if (state->unit[unit].pending) {
        state->unit[unit].pending = 0;
        state->unit[unit].poll_hint = 0;
        return 0;
    }
    state->unit[unit].poll_hint = 1;
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

#if !defined(VOS_EFFECTS_TYPED)
static int effect_retire(void *state, uint32_t members, struct vos_completion *done)
{
    struct vos_kernel_effect_state *kernel = state;
    uint64_t mask = vos_kernel_retirement_mask(kernel, members);
    volatile uint64_t *bitmap;
    if (mask == 0)
        return 0;
    bitmap = kernel->bitmap;
    *bitmap |= mask;
    (void)vos_kernel_publication(kernel, kernel->epoch, mask, *bitmap);
    return vos_kernel_retire(kernel, members, done);
}
static int effect_wait(void *state, uint32_t delay)
{
    struct vos_kernel_effect_state *kernel = state;
    volatile uint64_t *clock;
    uint64_t start, now;
    uint32_t poll;
    if (kernel == 0 || !kernel->bound || kernel->locked)
        return 0;
    clock = kernel->clock;
    start = *clock;
    for (poll = 0; poll < kernel->polls; ++poll) {
        now = *clock;
        if (vos_kernel_wait_sample(kernel, kernel->epoch, delay, start, now))
            return vos_kernel_wait(kernel, delay);
    }
    return 0;
}
static int effect_acquire(void *state, struct vos_supervisor_epoch *snapshot, uint64_t *epoch)
{ return vos_kernel_acquire(state, snapshot, epoch); }
static int effect_start(void *state, const struct vos_supervisor_start *request)
{ return vos_kernel_start(state, request); }
static void effect_release(void *state)
{ vos_kernel_release(state); }

const struct vos_supervisor_effects vos_kernel_supervisor_effects = {
    effect_retire, effect_wait, effect_acquire, effect_start, effect_release
};

#endif
