/* SPDX-License-Identifier: Apache-2.0 */
#include "vos_supervisor.h"

static uint32_t members(uint32_t count)
{
    return (1U << count) - 1U;
}

int vos_supervisor_order_ok(const struct vos_supervisor_manifest *m,
                            const uint32_t *order, uint32_t length)
{
    uint32_t i, unit, seen = 0;
    if (m == 0 || order == 0 || m->units > VOS_SUPERVISOR_UNITS ||
        length != m->units)
        return 0;
    for (i = 0; i < length; ++i) {
        unit = order[i];
        if (unit >= m->units || (seen & (1U << unit)) != 0 ||
            (m->edges[unit] & ~seen) != 0)
            return 0;
        seen |= 1U << unit;
    }
    return seen == members(m->units);
}

int vos_supervisor_manifest_ok(const struct vos_supervisor_manifest *m)
{
    uint32_t i;
    if (m == 0 || m->units == 0 || m->units > VOS_SUPERVISOR_UNITS ||
        m->backoff_count > VOS_SUPERVISOR_BACKOFF ||
        m->escalation >= VOS_SUPERVISOR_ACTIONS ||
        m->restart_members == 0 ||
        (m->restart_members & ~members(m->units)) != 0 ||
        !vos_supervisor_order_ok(m, m->order, m->units))
        return 0;
    for (i = 0; i < VOS_SUPERVISOR_DETECTORS; ++i)
        if (m->respond[i] >= VOS_SUPERVISOR_ACTIONS ||
            m->clear_threshold[i] > m->threshold[i])
            return 0;
    for (i = 0; i < m->backoff_count; ++i)
        if (m->backoff[i] > m->ceiling)
            return 0;
    return 1;
}

static uint32_t delay(const struct vos_supervisor_manifest *m, uint32_t attempts)
{
    return attempts < m->backoff_count ? m->backoff[attempts] : m->ceiling;
}

int vos_supervisor_decide(const struct vos_supervisor_manifest *m,
                          const struct vos_supervisor_declared *state,
                          uint32_t detector, uint32_t signal,
                          struct vos_supervisor_decision *out)
{
    /* Admission belongs at composition/load time. Detection reads one signal;
       it neither scans the roster nor updates a hidden history. */
    if (m == 0 || state == 0 || out == 0 ||
        detector >= VOS_SUPERVISOR_DETECTORS ||
        m->backoff_count > VOS_SUPERVISOR_BACKOFF ||
        m->respond[detector] >= VOS_SUPERVISOR_ACTIONS ||
        m->escalation >= VOS_SUPERVISOR_ACTIONS)
        return 0;
    out->detected = signal >= m->threshold[detector];
    out->admitted = state->dwell >= m->min_dwell &&
                    state->interventions < m->max_interventions;
    out->action = state->interventions < m->max_interventions ?
                  m->respond[detector] : m->escalation;
    out->delay = delay(m, state->attempts);
    out->boot_admitted = state->boots < m->boot_bound;
    return 1;
}

int vos_supervisor_plan(const struct vos_supervisor_manifest *m,
                        const struct vos_supervisor_epoch *epoch,
                        uint32_t current_epoch, uint32_t restart,
                        uint32_t attempts, struct vos_supervisor_plan *out)
{
    uint32_t i, unit, selected;
    struct vos_supervisor_plan plan = {0};
    if (out == 0 || epoch == 0 || restart > 1 ||
        !vos_supervisor_manifest_ok(m) || epoch->number != current_epoch)
        return 0;
    selected = restart ? m->restart_members : members(m->units);
    plan.stop_members = restart ? selected : 0;
    plan.delay = restart ? delay(m, attempts) : 0;
    for (i = 0; i < m->units; ++i) {
        unit = m->order[i];
        if ((selected & (1U << unit)) != 0) {
            plan.starts[plan.count].unit = unit;
            plan.starts[plan.count].grants = m->edges[unit] & ~epoch->retired[unit];
            plan.starts[plan.count].epoch = current_epoch;
            ++plan.count;
        }
    }
    *out = plan;
    return 1;
}

int vos_supervisor_request_current(const struct vos_supervisor_manifest *m,
                                   const struct vos_supervisor_epoch *epoch,
                                   uint32_t current_epoch,
                                   const struct vos_supervisor_start *request)
{
    if (m == 0 || epoch == 0 || request == 0 ||
        m->units > VOS_SUPERVISOR_UNITS || request->unit >= m->units ||
        request->epoch != current_epoch || epoch->number != current_epoch)
        return 0;
    return request->grants ==
           (m->edges[request->unit] & ~epoch->retired[request->unit]);
}
