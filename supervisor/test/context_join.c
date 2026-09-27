// SPDX-License-Identifier: Apache-2.0
/* Finite component composition. This is not the boot roster or copy service. */
#ifdef VOS_JOIN_KERNEL
#define VOS_EFFECTS_TYPED 1
#define VOS_KERNEL_EFFECT_UNITS 3
#define members join_kernel_members
#define vos_supervisor_order_ok join_kernel_order_ok
#define vos_supervisor_manifest_ok join_kernel_manifest_ok
#define vos_supervisor_backoff join_kernel_backoff
#define vos_supervisor_decide join_kernel_decide
#define vos_supervisor_plan join_kernel_plan
#define vos_supervisor_request_current join_kernel_request_current
#include "../../kernel/src/context.c"
#include "../src/supervisor.c"
#include "../../kernel/src/effects.c"
#include "../../kernel/src/lifecycle.c"
#ifndef VOS_JOIN_OWNED_BYTES
#define VOS_JOIN_OWNED_BYTES 64
#endif
#ifndef VOS_JOIN_INITIAL_EPOCH
#define VOS_JOIN_INITIAL_EPOCH UINT64_C(0x100000001)
#endif

void vos_join_manifest(struct vos_supervisor_manifest *out)
{
    struct vos_supervisor_manifest m = {
        3, {0, 1, 2}, {0, 1, 0}, {0}, {0}, {0},
        0, 3, VOS_FAIL_STOP, 1, {500000}, 500000, 3, 7
    };
    *out = m;
}

int vos_join_init(struct vos_kernel_effect_state *e,
                  struct vos_kernel_lifecycle *l, uint8_t *ack,
                  const vos_cap_t *roots, const uint64_t *masks,
                  uint64_t *bitmap, uint64_t *clock, uint8_t *owned)
{
    struct vos_supervisor_manifest m;
    vos_join_manifest(&m);
    if (sizeof(*e) > 8192 || sizeof(*l) > 512 || sizeof(m) > 512)
        return 0;
    return vos_kernel_effect_init(e, &m, VOS_JOIN_INITIAL_EPOCH) &&
        vos_kernel_own(e, 2, owned, VOS_JOIN_OWNED_BYTES, 0, 0) &&
        vos_kernel_effect_bind(e, roots, masks, bitmap, clock, 1) &&
        vos_kernel_lifecycle_init(l, e, ack);
}

void vos_join_resident(struct vos_kernel_effect_state *e, uint32_t clean)
{
    /* The assembly caller supplies the observation after actual register scrub. */
    e->resident_clean = clean;
}

int vos_join_dispatchable(const struct vos_kernel_effect_state *e)
{
    return !e->retirement_pending && !e->needs_replenish && e->started == 7;
}

uint64_t vos_join_epoch(const struct vos_kernel_effect_state *e)
{
    return e->epoch;
}

int vos_join_incomplete(const struct vos_kernel_effect_state *e,
                        const struct vos_kernel_lifecycle *l)
{
    return e->retirement_pending &&
           ((e->needs_replenish == 7 && e->started == 0) ||
            (e->needs_replenish == 0 && e->started == 7)) &&
           l->phase == VOS_CTX_PHASE_FAILED &&
           l->status == VOS_CTX_STATUS_INCOMPLETE && !vos_join_dispatchable(e);
}

int vos_join_outcome(const struct vos_kernel_effect_state *e,
                     const struct vos_kernel_lifecycle *l)
{
    return e->started == 7 && e->epoch == VOS_JOIN_INITIAL_EPOCH + 1 &&
           l->phase == VOS_CTX_PHASE_RUNNING && l->last_sequence == 3 &&
           l->attempts == 1 && !e->retirement_pending && !e->needs_replenish;
}
#else
#include "../src/supervisor.c"
#include "../src/context.c"

uint64_t vos_join_react(const struct vos_supervisor_manifest *m,
                        const uint64_t *ack, uint64_t *request, uint32_t desired)
{
    struct vos_supervisor_context state;
    uint64_t sequence = 0;
    enum vos_supervisor_context_result result;
    if (!vos_supervisor_context_recover(m, ack, &state))
        return UINT64_MAX;
    result = vos_supervisor_context_step(m, &state, ack, desired, request, &sequence);
    return result == VOS_SUPERVISOR_CONTEXT_REJECTED ? UINT64_MAX : sequence;
}
#endif
