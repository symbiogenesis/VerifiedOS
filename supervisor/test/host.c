// SPDX-License-Identifier: Apache-2.0
#include <stdio.h>
#include <string.h>
#include "vos_supervisor.h"

/* SupervisionTree.v's demo witness. This is not the M8a composition. */
static const struct vos_supervisor_manifest demo = {
    5, {0, 1, 2, 3, 4}, {0, 1, 2, 4, 8},
    {3, 3, 3, 3, 3, 3, 3, 3}, {1, 1, 1, 1, 1, 1, 1, 1},
    {0, 1, 2, 5, 6, 8, 5, 3}, 2, 3, 9, 4, {1, 2, 3, 5}, 5, 3, 31
};

static int controls(void)
{
    struct vos_supervisor_manifest m = vos_m8a_supervisor_manifest;
    struct vos_supervisor_epoch epoch = {7, {0}};
    struct vos_supervisor_plan plan = {0}, before;
    struct vos_supervisor_start request;
    struct vos_supervisor_declared state = {0};
    struct vos_supervisor_decision result = {0};
    unsigned int checks = 0;
#define CHECK(c) do { ++checks; if (!(c)) { \
    fprintf(stderr, "FAIL consumer control %u line %d\n", checks, __LINE__); \
    return 1; } } while (0)
    CHECK(vos_supervisor_manifest_ok(&m));
    CHECK(vos_supervisor_plan(&m, &epoch, 7, 0, 0, &plan));
    CHECK(plan.count == 3 && plan.stop_members == 0 && plan.delay == 0);
    CHECK(plan.starts[0].unit == 0 && plan.starts[1].unit == 1 &&
          plan.starts[2].unit == 2 && plan.starts[1].grants == 1);
    request = plan.starts[1];
    CHECK(vos_supervisor_request_current(&m, &epoch, 7, &request));
    before = plan;
    CHECK(!vos_supervisor_plan(&m, &epoch, 8, 0, 0, &plan));
    CHECK(memcmp(&before, &plan, sizeof(plan)) == 0);
    CHECK(!vos_supervisor_request_current(&m, &epoch, 8, &request));
    epoch.number = 8;
    epoch.retired[1] = 1;
    CHECK(!vos_supervisor_request_current(&m, &epoch, 8, &request));
    CHECK(vos_supervisor_plan(&m, &epoch, 8, 1, 0, &plan));
    CHECK(plan.count == 3 && plan.stop_members == 7 && plan.delay == 1);
    CHECK(plan.starts[1].grants == 0 && plan.starts[1].epoch == 8);
    CHECK(vos_supervisor_request_current(&m, &epoch, 8, &plan.starts[1]));
    request = plan.starts[1];
    request.grants = 1;
    CHECK(!vos_supervisor_request_current(&m, &epoch, 8, &request));
    request = plan.starts[0];
    request.grants = 4;
    CHECK(!vos_supervisor_request_current(&m, &epoch, 8, &request));
    CHECK(vos_supervisor_plan(&m, &epoch, 8, 1, UINT32_MAX, &plan));
    CHECK(plan.delay == m.ceiling);
    m.restart_members = 6;
    CHECK(vos_supervisor_plan(&m, &epoch, 8, 1, 1, &plan));
    CHECK(plan.count == 2 && plan.stop_members == 6 && plan.delay == 2 &&
          plan.starts[0].unit == 1 && plan.starts[1].unit == 2);
    m.restart_members = 8;
    CHECK(!vos_supervisor_manifest_ok(&m));
    m = demo;
    m.units = VOS_SUPERVISOR_UNITS + 1;
    CHECK(!vos_supervisor_manifest_ok(&m));
    m = demo;
    m.order[1] = 0;
    CHECK(!vos_supervisor_manifest_ok(&m));
    m = demo;
    m.edges[0] = 1;
    CHECK(!vos_supervisor_manifest_ok(&m));
    m = demo;
    m.edges[0] = 1U << VOS_SUPERVISOR_UNITS;
    CHECK(!vos_supervisor_manifest_ok(&m));
    m = demo;
    m.backoff_count = VOS_SUPERVISOR_BACKOFF + 1;
    CHECK(!vos_supervisor_manifest_ok(&m));
    m = demo;
    m.backoff[0] = m.ceiling + 1;
    CHECK(!vos_supervisor_manifest_ok(&m));
    m = demo;
    m.clear_threshold[0] = 4;
    CHECK(!vos_supervisor_manifest_ok(&m));
    m = demo;
    m.clear_threshold[0] = 3;
    CHECK(vos_supervisor_manifest_ok(&m));
    m.respond[0] = VOS_SUPERVISOR_ACTIONS;
    CHECK(!vos_supervisor_manifest_ok(&m));
    CHECK(!vos_supervisor_decide(&demo, &state, VOS_SUPERVISOR_DETECTORS, 3, &result));
    CHECK(!vos_supervisor_plan(&demo, &epoch, 8, 2, 0, &plan));
    fprintf(stderr, "ok %u fixed consumer controls (not Gallina comparisons)\n", checks);
    return 0;
#undef CHECK
}

int main(int argc, char **argv)
{
    unsigned int family, n, i, detector, signal, u, v;
    uint32_t order[VOS_SUPERVISOR_UNITS + 1];
    struct vos_supervisor_declared state;
    struct vos_supervisor_decision result;
    struct vos_supervisor_epoch epoch = {0, {0, 0, 0, 0, 8}};
    struct vos_supervisor_plan plan;
    if (argc == 2 && strcmp(argv[1], "controls") == 0)
        return controls();
    if (argc != 1)
        return 2;
    while (scanf("%u", &family) == 1) {
        if (family == 0) {
            if (scanf("%u", &n) != 1 || n > VOS_SUPERVISOR_UNITS + 1)
                return 2;
            for (i = 0; i < n; ++i) {
                unsigned int unit;
                if (scanf("%u", &unit) != 1)
                    return 2;
                order[i] = unit;
            }
            printf("%d\n", vos_supervisor_order_ok(&demo, order, n));
        } else if (family == 1) {
            unsigned int attempts, interventions, dwell, boots;
            if (scanf("%u %u %u %u %u %u", &detector, &signal,
                      &attempts, &interventions, &dwell, &boots) != 6)
                return 2;
            state.attempts = attempts;
            state.interventions = interventions;
            state.dwell = dwell;
            state.boots = boots;
            if (!vos_supervisor_decide(&demo, &state, detector, signal, &result))
                return 2;
            printf("%u %u %u %u %u\n", (unsigned int)result.detected,
                   (unsigned int)result.admitted, (unsigned int)result.action,
                   (unsigned int)result.delay, (unsigned int)result.boot_admitted);
        } else if (family == 2) {
            if (scanf("%u %u", &u, &v) != 2 || u >= demo.units || v >= demo.units ||
                !vos_supervisor_plan(&demo, &epoch, 0, 1, 0, &plan))
                return 2;
            printf("%u\n", (unsigned int)((plan.starts[u].grants >> v) & 1U));
        } else {
            return 2;
        }
    }
    return feof(stdin) ? 0 : 2;
}
