// SPDX-License-Identifier: Apache-2.0
/* Host fixture producer for the bounded Lustre route trial. The current C
 * manifest and planner own the answers; this harness only supplies inputs.
 * Refused output records are normalized to zero after checking nonmutation.
 */
#include <inttypes.h>
#include <stdio.h>
#include "vos_supervisor.h"

int main(void)
{
    const uint64_t epochs[] = {0, 1, UINT64_C(0x100000001), UINT64_MAX};
    const uint32_t tries[] = {0, 1, 2, 3, 4, 5, 6, UINT32_MAX};
    uint32_t restart, attempt_index, retired, stale, i, j;
    for (restart = 0; restart < 3; ++restart)
        for (attempt_index = 0; attempt_index < 8; ++attempt_index)
            for (retired = 0; retired < 2; ++retired)
                for (stale = 0; stale < 3; ++stale)
                    for (i = 0; i < 4; ++i) {
                        struct vos_supervisor_epoch snapshot = {0, {0}};
                        struct vos_supervisor_plan plan = {0};
                        uint64_t current = epochs[i];
                        uint32_t attempts = tries[attempt_index];
                        int accepted;
                        snapshot.number = current ^ (stale == 1 ? 1 :
                            stale == 2 ? UINT64_C(0x100000000) : 0);
                        snapshot.retired[1] = retired;
                        plan.count = 99;
                        plan.stop_members = 98;
                        plan.delay = 97;
                        accepted = vos_supervisor_plan(&vos_m8a_supervisor_manifest,
                            &snapshot, current, restart, attempts, &plan);
                        if (accepted) {
                            if (plan.count != 3)
                                return 1;
                            for (j = 0; j < plan.count; ++j)
                                if (plan.starts[j].unit != j ||
                                    plan.starts[j].epoch != current ||
                                    !vos_supervisor_request_current(
                                        &vos_m8a_supervisor_manifest, &snapshot,
                                        current, &plan.starts[j]))
                                    return 2;
                        } else if (plan.count != 99 || plan.stop_members != 98 ||
                                   plan.delay != 97) {
                            return 3;
                        }
                        printf("%" PRIu32 " %" PRIu32 " %" PRIu64 " %" PRIu64
                               " %" PRIu32
                               " %d %" PRIu32 " %" PRIu32 " %" PRIu32
                               " %" PRIu32 " %" PRIu32 " %" PRIu32 " %" PRIu32
                               "\n", restart, attempts,
                               snapshot.number, current, retired,
                               accepted, accepted ? plan.count : 0,
                               accepted ? plan.stop_members : 0,
                               accepted ? plan.delay : 0,
                               accepted ? plan.starts[1].grants : 0,
                               accepted ? plan.starts[0].unit : 0,
                               accepted ? plan.starts[1].unit : 0,
                               accepted ? plan.starts[2].unit : 0);
                    }
    return 0;
}
