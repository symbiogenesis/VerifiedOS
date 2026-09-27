// SPDX-License-Identifier: Apache-2.0
/* Compiles the real pure C effects and exercises their finite scalar state.
 * Local bitmap/clock objects model the hardware boundary in this component
 * test. The composed assembly campaign supplies actual architectural effects. */
#define VOS_EFFECTS_TYPED 1
#define VOS_KERNEL_EFFECT_UNITS 3
#include "vos_effects.h"
#include "../src/context.c"
#include "../../supervisor/src/supervisor.c"
#include "../src/effects.c"

int main(void)
{
    struct vos_kernel_effect_state state;
    struct vos_supervisor_manifest manifest = {
        3, {0, 1, 2}, {0, 1, 0}, {0}, {0}, {0},
        0, 3, VOS_FAIL_STOP, 1, {0}, 5, 3, 7
    };
    struct vos_supervisor_epoch snapshot;
    struct vos_supervisor_plan plan;
    struct vos_completion done;
    vos_cap_t roots[VOS_SUPERVISOR_UNITS] = {0};
    uint64_t masks[VOS_SUPERVISOR_UNITS] = {1, 2, 4};
    uint64_t bitmap = 0, clock = 0, epoch, mask;
    uint32_t i;
    uint8_t bytes[16];
    if (!vos_kernel_effect_init(&state, &manifest, 7)) return 1;
    if (!vos_kernel_own(&state, 2, bytes, 16, 0, 0)) return 2;
    if (!vos_kernel_effect_bind(&state, roots, masks, &bitmap, &clock, 4)) return 3;
    if (!vos_kernel_acquire(&state, &snapshot, &epoch)) return 4;
    if (!vos_supervisor_plan(&manifest, &snapshot, epoch, 0, 0, &plan)) return 5;
    for (i = 0; i < plan.count; ++i)
        if (!vos_kernel_start(&state, &plan.starts[i])) return 6;
    vos_kernel_release(&state);
    for (i = 0; i < 16; ++i) bytes[i] = 123;
    if (!vos_kernel_copy_begin(&state, 2, 7)) return 7;
    if (vos_kernel_retirement_mask(&state, 7)) return 8;
    if (!vos_kernel_copy_complete(&state, 2, 7)) return 9;
    if (vos_kernel_copy_wait(&state, 2, 7) != 1) return 10;
    if (!vos_kernel_notify(&state, 2, 7)) return 11;
    if (vos_kernel_copy_wait(&state, 2, 7) != 0) return 12;
    if (!vos_kernel_frame_enter(&state, 2, 7)) return 13;
    if (!vos_kernel_frame_enter(&state, 2, 7)) return 14;
    if (vos_kernel_frame_enter(&state, 2, 7)) return 15;
    state.resident_clean = 1;
    mask = vos_kernel_retirement_mask(&state, 7);
    if (mask != 7) return 16;
    bitmap |= mask;
    if (vos_kernel_publication(&state, 6, mask, bitmap)) return 17;
    if (!vos_kernel_publication(&state, 7, mask, bitmap)) return 18;
    if (vos_kernel_publication(&state, 7, mask, bitmap)) return 19;
    if (!vos_kernel_retire(&state, 7, &done)) return 20;
    if (!vos_semantic_completion(&done)) return 21;
    for (i = 0; i < 16; ++i) if (bytes[i] != 0) return 22;
    if (state.epoch != 8 || state.started != 0) return 23;
    if (vos_kernel_wait_sample(&state, 7, 1, 10, 11)) return 24;
    if (!vos_kernel_wait_sample(&state, 8, 1, 10, 11)) return 25;
    if (!vos_kernel_wait(&state, 1) || vos_kernel_wait(&state, 1)) return 26;
    if (vos_kernel_wait_sample(&state, 8, 1, 10, 11)) return 27;
    return 0;
}
