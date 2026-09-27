// SPDX-License-Identifier: Apache-2.0
/* The real consumer compiles with the accepted typed scalar backend.
 * Hardware bitmap, clock and acknowledgment ordering belong to the composed
 * boundary adapter, not these local scalar fixtures. */
#define VOS_EFFECTS_TYPED 1
#define VOS_KERNEL_EFFECT_UNITS 3
#include "../src/context.c"
#include "../../supervisor/src/supervisor.c"
#include "../src/effects.c"
#include "../src/lifecycle.c"

static int target_publish(struct vos_kernel_lifecycle *c,
                           struct vos_kernel_effect_state *e, uint8_t *ack,
                           uint64_t now)
{
    uint64_t sequence = vos_kernel_lifecycle_acknowledge(c, e, ack, now);
    lifecycle_put(ack, VOS_CTX_ACK_SEQUENCE, sequence);
    return vos_kernel_lifecycle_published(c, e, sequence);
}

static void target_request(struct vos_kernel_lifecycle *c,
                            struct vos_kernel_effect_state *e, uint8_t *request,
                            uint32_t operation, uint64_t sequence)
{
    uint32_t i;
    for (i = 0; i < VOS_CTX_REQ_BYTES; ++i) request[i] = 0;
    lifecycle_put(request, VOS_CTX_REQ_SEQUENCE, sequence);
    lifecycle_put(request, VOS_CTX_REQ_OPERATION, operation);
    lifecycle_put(request, VOS_CTX_REQ_EPOCH, e->epoch);
    lifecycle_put(request, VOS_CTX_REQ_MEMBERS, 7);
    lifecycle_put(request, VOS_CTX_REQ_ATTEMPTS, c->attempts);
    if (operation == VOS_CTX_OP_START) {
        lifecycle_put(request, VOS_CTX_REQ_COUNT, 3);
        for (i = 0; i < 3; ++i) {
            lifecycle_put(request, VOS_CTX_REQ_STARTS + i * VOS_CTX_START_WORDS, i);
            lifecycle_put(request, VOS_CTX_REQ_STARTS + i * VOS_CTX_START_WORDS + 1,
                          e->manifest.edges[i]);
        }
    }
}

int main(void)
{
    struct vos_kernel_effect_state effect;
    struct vos_kernel_lifecycle lifecycle;
    struct vos_supervisor_manifest manifest = {
        3, {0, 1, 2}, {0, 1, 2}, {0}, {0}, {0},
        0, 3, VOS_FAIL_STOP, 2, {3, 5}, 7, 3, 7
    };
    uint8_t request[VOS_CTX_REQ_BYTES], ack[VOS_CTX_ACK_BYTES], owned[32];
    vos_cap_t roots[3] = {0};
    uint64_t masks[3] = {1, 2, 4}, fresh[3] = {8, 16, 32};
    uint64_t bitmap = 0, clock = 0;
    uint32_t i;
    if (!vos_kernel_effect_init(&effect, &manifest, UINT64_C(0x100000007)) ||
        !vos_kernel_own(&effect, 2, owned, 32, 0, 0) ||
        !vos_kernel_effect_bind(&effect, roots, masks, &bitmap, &clock, 1) ||
        !vos_kernel_lifecycle_init(&lifecycle, &effect, ack)) return 1;
    target_request(&lifecycle, &effect, request, VOS_CTX_OP_START, 1);
    lifecycle_put(request, VOS_CTX_REQ_STARTS + 5, 8);
    if (vos_kernel_lifecycle_prepare(&lifecycle, &effect, request, 10) != VOS_LIFECYCLE_ACK ||
        effect.started != 0 || !target_publish(&lifecycle, &effect, ack, 10)) return 2;
    target_request(&lifecycle, &effect, request, VOS_CTX_OP_START, 2);
    if (vos_kernel_lifecycle_prepare(&lifecycle, &effect, request, 11) != VOS_LIFECYCLE_START ||
        !vos_kernel_lifecycle_start_finish(&lifecycle, &effect) || !effect.locked ||
        !target_publish(&lifecycle, &effect, ack, 11) || effect.locked) return 3;
    for (i = 0; i < 32; ++i) owned[i] = 213;
    target_request(&lifecycle, &effect, request, VOS_CTX_OP_RETIRE, 3);
    if (vos_kernel_lifecycle_prepare(&lifecycle, &effect, request, 20) != VOS_LIFECYCLE_RETIRE)
        return 4;
    bitmap |= vos_kernel_lifecycle_mask(&lifecycle);
    effect.resident_clean = 1;
    if (!vos_kernel_lifecycle_retire_finish(&lifecycle, &effect, bitmap, roots, fresh, 21) ||
        !target_publish(&lifecycle, &effect, ack, 21)) return 5;
    for (i = 0; i < 32; ++i) if (owned[i] != 0) return 6;
    if (effect.epoch != UINT64_C(0x100000008) || lifecycle.deadline != 24 ||
        lifecycle.attempts != 1 || effect.started != 0) return 7;
    target_request(&lifecycle, &effect, request, VOS_CTX_OP_START, 4);
    if (vos_kernel_lifecycle_prepare(&lifecycle, &effect, request, 23) != VOS_LIFECYCLE_ACK ||
        lifecycle.status != VOS_CTX_STATUS_EARLY ||
        !target_publish(&lifecycle, &effect, ack, 23)) return 8;
    target_request(&lifecycle, &effect, request, VOS_CTX_OP_START, 5);
    if (vos_kernel_lifecycle_prepare(&lifecycle, &effect, request, 24) != VOS_LIFECYCLE_START ||
        !vos_kernel_lifecycle_start_finish(&lifecycle, &effect) ||
        !target_publish(&lifecycle, &effect, ack, 24) || effect.started != 7) return 9;
    return 0;
}
