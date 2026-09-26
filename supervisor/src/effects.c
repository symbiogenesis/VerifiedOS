// SPDX-License-Identifier: Apache-2.0
#include "vos_supervisor_effects.h"

enum vos_supervisor_execution_status vos_supervisor_execute(
    const struct vos_supervisor_manifest *manifest, uint32_t restart,
    uint32_t attempts, const struct vos_supervisor_effects *effects,
    void *context, struct vos_supervisor_execution *out)
{
    struct vos_supervisor_manifest admitted;
    struct vos_supervisor_effects operations;
    struct vos_supervisor_execution result = {
        VOS_SUPERVISOR_INVALID, 0, 0, 0, 0, VOS_SUPERVISOR_UNITS
    };
    struct vos_supervisor_epoch epoch = {0, {0}};
    struct vos_completion completion = {0};
    struct vos_supervisor_plan plan;
    uint32_t i;
    uint64_t current = 0;

    if (out == 0)
        return VOS_SUPERVISOR_INVALID;
    if (restart > 1 || !vos_supervisor_manifest_ok(manifest) ||
        effects == 0 || effects->acquire == 0 || effects->start == 0 ||
        effects->release == 0 ||
        (restart && (effects->retire == 0 || effects->wait == 0))) {
        *out = result;
        return result.status;
    }
    admitted = *manifest;
    operations = *effects;
    if (restart) {
        result.stop_members = admitted.restart_members;
        result.delay = vos_supervisor_backoff(&admitted, attempts);
        result.status = VOS_SUPERVISOR_RETIRE_REFUSED;
        if (!operations.retire(context, result.stop_members, &completion))
            goto finished;
        result.status = VOS_SUPERVISOR_REVOCATION_INCOMPLETE;
        if (!vos_semantic_completion(&completion))
            goto finished;
        result.status = VOS_SUPERVISOR_WAIT_REFUSED;
        if (!operations.wait(context, result.delay))
            goto finished;
    }
    result.status = VOS_SUPERVISOR_ACQUIRE_REFUSED;
    if (!operations.acquire(context, &epoch, &current))
        goto finished;
    result.status = VOS_SUPERVISOR_SNAPSHOT_REFUSED;
    if (!vos_supervisor_plan(&admitted, &epoch, current, restart, attempts, &plan))
        goto release;
    for (i = 0; i < plan.count; ++i) {
        const struct vos_supervisor_start *request = &plan.starts[i];
        if (!vos_supervisor_request_current(&admitted, &epoch, current, request))
            goto release;
        result.status = VOS_SUPERVISOR_START_REFUSED;
        result.refused_unit = request->unit;
        if (!operations.start(context, request))
            goto release;
        result.refused_unit = VOS_SUPERVISOR_UNITS;
        result.started_members |= 1U << request->unit;
        ++result.started_count;
        result.status = VOS_SUPERVISOR_SNAPSHOT_REFUSED;
    }
    result.status = VOS_SUPERVISOR_EXECUTED;
release:
    operations.release(context);
finished:
    *out = result;
    return result.status;
}
