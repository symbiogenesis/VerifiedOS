// SPDX-License-Identifier: Apache-2.0
#include <stdio.h>
#include <string.h>
#include "vos_effects.h"

static struct vos_kernel_effect_state state;
static uint8_t owned[524288];
static vos_cap_t owned_caps[128];
static vos_cap_t roots[VOS_SUPERVISOR_UNITS];
static uint64_t masks[VOS_SUPERVISOR_UNITS], bitmap, ticks;

static int prepare(uint64_t epoch)
{
    uint32_t i;
    for (i = 0; i < VOS_SUPERVISOR_UNITS; ++i) {
        roots[i].value = 100 + i;
        roots[i].tag = 1;
        masks[i] = UINT64_C(1) << i;
    }
    bitmap = 0x8000000000000000ULL;
    ticks = 0;
    if (!vos_kernel_effect_init(&state, &vos_m8a_supervisor_manifest, epoch) ||
        !vos_kernel_own(&state, 2, owned, sizeof(owned), owned_caps, 128) ||
        !vos_kernel_effect_bind(&state, roots, masks, &bitmap, &ticks, 4))
        return 0;
    return 1;
}

static int starts(void)
{
    struct vos_supervisor_epoch snapshot;
    struct vos_supervisor_plan plan;
    uint64_t epoch;
    uint32_t i;
    if (!vos_kernel_acquire(&state, &snapshot, &epoch) ||
        !vos_supervisor_plan(&state.manifest, &snapshot, epoch, 0, 0, &plan))
        return 0;
    for (i = 0; i < plan.count; ++i)
        if (!vos_kernel_start(&state, &plan.starts[i]))
            return 0;
    vos_kernel_release(&state);
    return 1;
}

int main(void)
{
    uint32_t i, n, checks = 0;
    uint64_t mask, epoch;
    struct vos_completion done;
    struct vos_supervisor_epoch snapshot;
    struct vos_supervisor_start request;
#define CHECK(p) do { ++checks; if (!(p)) { \
    fprintf(stderr, "FAIL scalar effects control %u line %d\n", checks, __LINE__); return 1; } } while (0)
    CHECK(prepare(7) && starts());
    CHECK(state.started == 7 && state.unit[1].grants[0].tag);
    CHECK(!vos_kernel_notify(&state, 2, 6));
    CHECK(vos_kernel_copy_wait(&state, 2, 7) == 1);
    CHECK(vos_kernel_notify(&state, 2, 7));
    CHECK(!state.unit[2].poll_hint && vos_kernel_copy_wait(&state, 2, 7) == 0);
    CHECK(vos_kernel_notify(&state, 2, 7));
    CHECK(vos_kernel_copy_wait(&state, 2, 7) == 0);
    CHECK(!vos_kernel_copy_complete(&state, 2, 7));
    CHECK(vos_kernel_copy_begin(&state, 2, 7));
    CHECK(!vos_kernel_copy_begin(&state, 2, 7));
    CHECK(vos_kernel_retirement_mask(&state, 7) == 0);
    CHECK(vos_kernel_copy_complete(&state, 2, 7));
    for (i = 0; i < VOS_KERNEL_FRAME_DEPTH; ++i)
        CHECK(vos_kernel_frame_enter(&state, 2, 7));
    CHECK(!vos_kernel_frame_enter(&state, 2, 7));
    for (i = 0; i < VOS_KERNEL_FRAME_DEPTH; ++i)
        CHECK(vos_kernel_frame_leave(&state, 2, 7));
    CHECK(!vos_kernel_frame_leave(&state, 2, 7));
    memset(owned, 0xa5, sizeof(owned));
    for (i = 0; i < 128; ++i) owned_caps[i] = roots[0];
    state.unit[2].saved[31] = roots[1];
    state.unit[2].frames[1][31] = roots[2];
    state.resident_clean = 1;
    mask = vos_kernel_retirement_mask(&state, 7);
    CHECK(mask == 7 && !vos_kernel_notify(&state, 2, 7));
    CHECK(!vos_kernel_publication(&state, 6, mask, mask));
    CHECK(!vos_kernel_publication(&state, 7, mask ^ 1, mask));
    CHECK(!vos_kernel_publication(&state, 7, mask, mask ^ 1));
    bitmap |= mask;
    CHECK(vos_kernel_publication(&state, 7, mask, bitmap));
    CHECK(!vos_kernel_publication(&state, 7, mask, bitmap));
    CHECK(vos_kernel_retire(&state, 7, &done) && vos_semantic_completion(&done));
    CHECK(!vos_kernel_retire(&state, 7, &done));
    CHECK(state.epoch == 8 && state.started == 0 && bitmap == 0x8000000000000007ULL);
    for (i = 0; i < sizeof(owned); ++i) CHECK(owned[i] == 0);
    for (i = 0; i < 128; ++i) CHECK(!owned_caps[i].tag && owned_caps[i].value == 0);
    CHECK(!state.unit[2].saved[31].tag && !state.unit[2].frames[1][31].tag);
    CHECK(!vos_kernel_wait_sample(&state, 7, 2, 10, 12));
    CHECK(!vos_kernel_wait_sample(&state, 8, 2, 10, 11));
    CHECK(vos_kernel_wait_sample(&state, 8, 2, 10, 12));
    CHECK(!vos_kernel_wait(&state, 3) && vos_kernel_wait(&state, 2));
    CHECK(!vos_kernel_wait(&state, 2));
    CHECK(!vos_kernel_wait_sample(&state, 8, 2, 10, 12));
    CHECK(starts() && !state.unit[1].grants[0].tag);
    CHECK(!vos_kernel_notify(&state, 2, 7));
    /* Every completion pattern: independently withhold publication or resident
     * scrub; missing physical conditions never become true through the epoch. */
    for (n = 0; n < 4; ++n) {
        CHECK(prepare(7) && starts());
        state.resident_clean = n & 1;
        mask = vos_kernel_retirement_mask(&state, 7);
        CHECK(mask == 7);
        if (n & 2) CHECK(vos_kernel_publication(&state, 7, mask, mask));
        CHECK(vos_kernel_retire(&state, 7, &done));
        CHECK(vos_semantic_completion(&done) == (n == 3));
        CHECK(vos_kernel_acquire(&state, &snapshot, &epoch));
        request.unit = 0; request.grants = 0; request.epoch = epoch;
        CHECK(vos_kernel_start(&state, &request) == (n == 3));
        vos_kernel_release(&state);
    }
    CHECK(prepare(UINT64_MAX) && starts());
    CHECK(vos_kernel_retirement_mask(&state, 7) == 0);
    CHECK(prepare(7) && starts());
    state.manifest.restart_members = 1;
    CHECK(vos_kernel_retirement_mask(&state, 1) == 0);
    state.manifest.restart_members = 7;
    state.loans = 1;
    CHECK(vos_kernel_retirement_mask(&state, 7) == 0);
    state.loans = 0; state.devices = 1;
    CHECK(vos_kernel_retirement_mask(&state, 7) == 0);
    CHECK(prepare(7));
    CHECK(vos_supervisor_execute(&state.manifest, 0, 0,
              &vos_kernel_supervisor_effects, &state,
              &(struct vos_supervisor_execution){0}) == VOS_SUPERVISOR_EXECUTED);
    state.resident_clean = 1;
    state.manifest.backoff[0] = 0;
    CHECK(vos_supervisor_execute(&state.manifest, 1, 0,
              &vos_kernel_supervisor_effects, &state,
              &(struct vos_supervisor_execution){0}) == VOS_SUPERVISOR_EXECUTED);
    fprintf(stderr, "ok scalar effects %u checks; real host storage, hardware boundary mocked\n", checks);
    return 0;
}
