// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_SUPERVISOR_H
#define VOS_SUPERVISOR_H

#include <stdint.h>

/* Composition capacities, not requirements or runtime allocation limits. */
#define VOS_SUPERVISOR_UNITS 16U
#define VOS_SUPERVISOR_BACKOFF 16U
#define VOS_SUPERVISOR_DETECTORS 8U
#define VOS_SUPERVISOR_ACTIONS 10U

enum vos_detector {
    VOS_POOL_LOW, VOS_POOL_EXHAUSTED, VOS_OLDEST_WAITER,
    VOS_QUARANTINE_BACKLOG, VOS_RELEASE_DEADLINE, VOS_RESTART_RATE,
    VOS_POPULATION_CEILING, VOS_CHECKPOINT_SPACE
};

enum vos_action {
    VOS_REFUSE_REQUEST, VOS_SHED_STATE, VOS_SUSPEND_TENANT,
    VOS_CHECKPOINT_TERMINATE, VOS_TERMINATE_GROUP, VOS_STEP_DOWN,
    VOS_DISABLE_SERVICE, VOS_RESTART_SUBTREE, VOS_FAIL_STOP, VOS_ROT_RESET
};

struct vos_supervisor_manifest {
    uint32_t units;
    uint32_t order[VOS_SUPERVISOR_UNITS];
    /* Bit v of row u means u may hold authority designating v. */
    uint32_t edges[VOS_SUPERVISOR_UNITS];
    uint32_t threshold[VOS_SUPERVISOR_DETECTORS];
    uint32_t clear_threshold[VOS_SUPERVISOR_DETECTORS];
    uint32_t respond[VOS_SUPERVISOR_DETECTORS];
    uint32_t min_dwell;
    uint32_t max_interventions;
    uint32_t escalation;
    uint32_t backoff_count;
    uint32_t backoff[VOS_SUPERVISOR_BACKOFF];
    uint32_t ceiling;
    uint32_t boot_bound;
    /* One composition-declared ownership-closed restart victim. */
    uint32_t restart_members;
};

struct vos_supervisor_declared {
    uint32_t attempts;
    uint32_t interventions;
    uint32_t dwell;
    uint32_t boots;
};

struct vos_supervisor_decision {
    uint32_t detected;
    uint32_t admitted;
    uint32_t action;
    uint32_t delay;
    uint32_t boot_admitted;
};

struct vos_supervisor_epoch {
    uint64_t number;
    uint32_t retired[VOS_SUPERVISOR_UNITS];
};

/* A request to the kernel adapter, not a capability or a completion receipt. */
struct vos_supervisor_start {
    uint32_t unit;
    uint32_t grants;
    uint64_t epoch;
};

struct vos_supervisor_plan {
    uint32_t count;
    uint32_t stop_members;
    uint32_t delay;
    struct vos_supervisor_start starts[VOS_SUPERVISOR_UNITS];
};

int vos_supervisor_order_ok(const struct vos_supervisor_manifest *m,
                            const uint32_t *order, uint32_t length);
int vos_supervisor_manifest_ok(const struct vos_supervisor_manifest *m);
/* The manifest must already have passed admission. */
uint32_t vos_supervisor_backoff(const struct vos_supervisor_manifest *m,
                               uint32_t attempts);
int vos_supervisor_decide(const struct vos_supervisor_manifest *m,
                          const struct vos_supervisor_declared *state,
                          uint32_t detector, uint32_t signal,
                          struct vos_supervisor_decision *out);
/* Refusal leaves out unchanged. current_epoch is the kernel's current value. */
int vos_supervisor_plan(const struct vos_supervisor_manifest *m,
                        const struct vos_supervisor_epoch *epoch,
                        uint64_t current_epoch, uint32_t restart,
                        uint32_t attempts, struct vos_supervisor_plan *out);
/* Call after completed teardown and immediately before consuming any start. */
int vos_supervisor_request_current(const struct vos_supervisor_manifest *m,
                                   const struct vos_supervisor_epoch *epoch,
                                   uint64_t current_epoch,
                                   const struct vos_supervisor_start *request);

extern const struct vos_supervisor_manifest vos_m8a_supervisor_manifest;

#endif
