// SPDX-License-Identifier: Apache-2.0
#include "vos_supervisor_context.h"

static int context_ack_ok(const struct vos_supervisor_manifest *m,
                          const uint64_t *ack)
{
    uint32_t i, unit, count = 0, prefix = 0, refused = m->units;
    uint32_t all = (1U << m->units) - 1U;
    if (ack[VOS_CTX_ACK_STATUS] > VOS_CTX_STATUS_START_REFUSED ||
        ack[VOS_CTX_ACK_OPERATION] > VOS_CTX_OP_START ||
        ack[VOS_CTX_ACK_PHASE] > VOS_CTX_PHASE_FAILED ||
        ack[VOS_CTX_ACK_MEMBERS] > all || ack[VOS_CTX_ACK_STARTED] > all ||
        ack[VOS_CTX_ACK_COUNT] > m->units ||
        ack[VOS_CTX_ACK_REFUSED] > m->units ||
        ack[VOS_CTX_ACK_ATTEMPTS] > UINT32_MAX)
        return 0;
    for (i = 0; i < VOS_CTX_UNITS; ++i)
        if (ack[VOS_CTX_ACK_RETIRED + i] > (i < m->units ? all : 0U))
            return 0;
    for (i = VOS_CTX_ACK_USED; i < VOS_CTX_ACK_WORDS; ++i)
        if (ack[i] != 0)
            return 0;
    if (ack[VOS_CTX_ACK_SEQUENCE] == 0 &&
        (ack[VOS_CTX_ACK_OPERATION] != VOS_CTX_OP_NONE ||
         ack[VOS_CTX_ACK_STATUS] != VOS_CTX_STATUS_OK ||
         ack[VOS_CTX_ACK_PHASE] != VOS_CTX_PHASE_INITIAL ||
         ack[VOS_CTX_ACK_MEMBERS] != 0 || ack[VOS_CTX_ACK_STARTED] != 0 ||
         ack[VOS_CTX_ACK_COUNT] != 0 || ack[VOS_CTX_ACK_ATTEMPTS] != 0 ||
         ack[VOS_CTX_ACK_DEADLINE] != 0 ||
         ack[VOS_CTX_ACK_REFUSED] != m->units))
        return 0;
    if (ack[VOS_CTX_ACK_SEQUENCE] != 0 &&
        ack[VOS_CTX_ACK_OPERATION] == VOS_CTX_OP_NONE &&
        (ack[VOS_CTX_ACK_STATUS] != VOS_CTX_STATUS_INVALID ||
         ack[VOS_CTX_ACK_COUNT] != 0 ||
         ack[VOS_CTX_ACK_REFUSED] != m->units))
        return 0;
    if (ack[VOS_CTX_ACK_STATUS] == VOS_CTX_STATUS_OK &&
        ack[VOS_CTX_ACK_PHASE] == VOS_CTX_PHASE_RETIRED &&
        (ack[VOS_CTX_ACK_OPERATION] != VOS_CTX_OP_RETIRE ||
         ack[VOS_CTX_ACK_MEMBERS] != m->restart_members ||
         ack[VOS_CTX_ACK_COUNT] != 0 ||
         (ack[VOS_CTX_ACK_STARTED] & m->restart_members) != 0 ||
         ack[VOS_CTX_ACK_ATTEMPTS] == 0 ||
         ack[VOS_CTX_ACK_REFUSED] != m->units))
        return 0;
    if (ack[VOS_CTX_ACK_OPERATION] == VOS_CTX_OP_START &&
        (ack[VOS_CTX_ACK_STATUS] == VOS_CTX_STATUS_OK ||
         ack[VOS_CTX_ACK_STATUS] == VOS_CTX_STATUS_START_REFUSED)) {
        if (ack[VOS_CTX_ACK_MEMBERS] != all &&
            ack[VOS_CTX_ACK_MEMBERS] != m->restart_members)
            return 0;
        for (i = 0; i < m->units; ++i) {
            unit = m->order[i];
            if ((ack[VOS_CTX_ACK_MEMBERS] & (1U << unit)) != 0) {
                if (count < ack[VOS_CTX_ACK_COUNT])
                    prefix |= 1U << unit;
                else if (refused == m->units)
                    refused = unit;
                ++count;
            }
        }
        if (ack[VOS_CTX_ACK_COUNT] > count ||
            (ack[VOS_CTX_ACK_STARTED] & ack[VOS_CTX_ACK_MEMBERS]) != prefix ||
            ack[VOS_CTX_ACK_REFUSED] != refused ||
            (ack[VOS_CTX_ACK_STATUS] == VOS_CTX_STATUS_OK &&
             (ack[VOS_CTX_ACK_COUNT] != count ||
              ack[VOS_CTX_ACK_PHASE] != VOS_CTX_PHASE_RUNNING)) ||
            (ack[VOS_CTX_ACK_STATUS] == VOS_CTX_STATUS_START_REFUSED &&
             (ack[VOS_CTX_ACK_COUNT] == count ||
              ack[VOS_CTX_ACK_PHASE] != VOS_CTX_PHASE_FAILED)))
            return 0;
    }
    return 1;
}

static void context_ack_read(struct vos_supervisor_context *s,
                             const uint64_t *ack)
{
    s->acknowledged_sequence = ack[VOS_CTX_ACK_SEQUENCE];
    s->epoch = ack[VOS_CTX_ACK_EPOCH];
    s->lifecycle_phase = (uint32_t)ack[VOS_CTX_ACK_PHASE];
    s->status = (uint32_t)ack[VOS_CTX_ACK_STATUS];
    s->members = (uint32_t)ack[VOS_CTX_ACK_MEMBERS];
    s->started = (uint32_t)ack[VOS_CTX_ACK_STARTED];
    s->count = (uint32_t)ack[VOS_CTX_ACK_COUNT];
    s->refused = (uint32_t)ack[VOS_CTX_ACK_REFUSED];
    s->attempts = (uint32_t)ack[VOS_CTX_ACK_ATTEMPTS];
}

int vos_supervisor_context_recover(
    const struct vos_supervisor_manifest *m,
    const uint64_t ack[VOS_CTX_ACK_WORDS], struct vos_supervisor_context *s)
{
    struct vos_supervisor_context next = {0};
    if (s == 0 || ack == 0 || !vos_supervisor_manifest_ok(m) ||
        !context_ack_ok(m, ack))
        return 0;
    context_ack_read(&next, ack);
    next.phase = next.lifecycle_phase == VOS_CTX_PHASE_RETIRED ?
                 VOS_SUPERVISOR_CONTEXT_BACKOFF : VOS_SUPERVISOR_CONTEXT_READY;
    *s = next;
    return 1;
}

enum vos_supervisor_context_result vos_supervisor_context_step(
    const struct vos_supervisor_manifest *m, struct vos_supervisor_context *s,
    const uint64_t ack[VOS_CTX_ACK_WORDS], uint32_t desired,
    uint64_t request[VOS_CTX_REQ_WORDS], uint64_t *publish_sequence)
{
    uint32_t i, restart, operation, attempts;
    uint64_t sequence;
    struct vos_supervisor_epoch snapshot = {0};
    struct vos_supervisor_plan plan = {0};
    if (publish_sequence == 0 || request == 0)
        return VOS_SUPERVISOR_CONTEXT_REJECTED;
    *publish_sequence = 0;
    for (i = 0; i < VOS_CTX_REQ_WORDS; ++i)
        request[i] = 0;
    if (s == 0 || ack == 0 || !vos_supervisor_manifest_ok(m))
        return VOS_SUPERVISOR_CONTEXT_REJECTED;
    if (s->phase == VOS_SUPERVISOR_CONTEXT_REFUSED)
        return VOS_SUPERVISOR_CONTEXT_REJECTED;
    sequence = s->phase == VOS_SUPERVISOR_CONTEXT_AWAIT_ACK ?
               s->outstanding_sequence : s->acknowledged_sequence;
    if (ack[VOS_CTX_ACK_SEQUENCE] != sequence)
        return VOS_SUPERVISOR_CONTEXT_WAIT;
    if (s->phase > VOS_SUPERVISOR_CONTEXT_REFUSED ||
        desired > VOS_SUPERVISOR_CONTEXT_RESTART || !context_ack_ok(m, ack)) {
        s->phase = VOS_SUPERVISOR_CONTEXT_REFUSED;
        return VOS_SUPERVISOR_CONTEXT_REJECTED;
    }
    if (s->phase == VOS_SUPERVISOR_CONTEXT_AWAIT_ACK) {
        operation = s->outstanding_operation;
        if (sequence == 0 || ack[VOS_CTX_ACK_OPERATION] != operation) {
            s->phase = VOS_SUPERVISOR_CONTEXT_REFUSED;
            return VOS_SUPERVISOR_CONTEXT_REJECTED;
        }
        context_ack_read(s, ack);
        s->outstanding_sequence = 0;
        s->outstanding_operation = VOS_CTX_OP_NONE;
        if (s->status != VOS_CTX_STATUS_OK ||
            (operation == VOS_CTX_OP_RETIRE &&
             s->lifecycle_phase != VOS_CTX_PHASE_RETIRED) ||
            (operation == VOS_CTX_OP_START &&
             s->lifecycle_phase != VOS_CTX_PHASE_RUNNING)) {
            s->phase = VOS_SUPERVISOR_CONTEXT_REFUSED;
            return VOS_SUPERVISOR_CONTEXT_REJECTED;
        }
        if (operation == VOS_CTX_OP_START) {
            s->phase = VOS_SUPERVISOR_CONTEXT_READY;
            return VOS_SUPERVISOR_CONTEXT_DONE;
        }
        s->phase = VOS_SUPERVISOR_CONTEXT_BACKOFF;
        return VOS_SUPERVISOR_CONTEXT_WAIT;
    }
    context_ack_read(s, ack);
    if (desired == VOS_SUPERVISOR_CONTEXT_HOLD)
        return s->phase == VOS_SUPERVISOR_CONTEXT_BACKOFF ?
               VOS_SUPERVISOR_CONTEXT_WAIT : VOS_SUPERVISOR_CONTEXT_IDLE;
    if (sequence >= UINT64_MAX - 1U ||
        (desired == VOS_SUPERVISOR_CONTEXT_INITIAL &&
         s->lifecycle_phase != VOS_CTX_PHASE_INITIAL) ||
        (desired == VOS_SUPERVISOR_CONTEXT_RESTART &&
         s->lifecycle_phase == VOS_CTX_PHASE_INITIAL)) {
        s->phase = VOS_SUPERVISOR_CONTEXT_REFUSED;
        return VOS_SUPERVISOR_CONTEXT_REJECTED;
    }
    operation = desired == VOS_SUPERVISOR_CONTEXT_RESTART &&
                s->lifecycle_phase != VOS_CTX_PHASE_RETIRED ?
                VOS_CTX_OP_RETIRE : VOS_CTX_OP_START;
    if (operation == VOS_CTX_OP_START) {
        restart = desired == VOS_SUPERVISOR_CONTEXT_RESTART;
        if (restart && ack[VOS_CTX_ACK_NOW] < ack[VOS_CTX_ACK_DEADLINE]) {
            s->phase = VOS_SUPERVISOR_CONTEXT_BACKOFF;
            return VOS_SUPERVISOR_CONTEXT_WAIT;
        }
        snapshot.number = s->epoch;
        for (i = 0; i < VOS_CTX_UNITS; ++i)
            snapshot.retired[i] = (uint32_t)ack[VOS_CTX_ACK_RETIRED + i];
        /* Successful retirement increments attempts after choosing its delay. */
        attempts = restart && s->attempts != 0 ? s->attempts - 1U : s->attempts;
        if (!vos_supervisor_plan(m, &snapshot, s->epoch, restart, attempts, &plan)) {
            s->phase = VOS_SUPERVISOR_CONTEXT_REFUSED;
            return VOS_SUPERVISOR_CONTEXT_REJECTED;
        }
        request[VOS_CTX_REQ_COUNT] = plan.count;
        for (i = 0; i < plan.count; ++i) {
            request[VOS_CTX_REQ_STARTS + VOS_CTX_START_WORDS * i +
                    VOS_CTX_START_UNIT] = plan.starts[i].unit;
            request[VOS_CTX_REQ_STARTS + VOS_CTX_START_WORDS * i +
                    VOS_CTX_START_GRANTS] = plan.starts[i].grants;
        }
    }
    request[VOS_CTX_REQ_OPERATION] = operation;
    request[VOS_CTX_REQ_EPOCH] = s->epoch;
    request[VOS_CTX_REQ_MEMBERS] = desired == VOS_SUPERVISOR_CONTEXT_INITIAL ?
                                 (1U << m->units) - 1U : m->restart_members;
    request[VOS_CTX_REQ_ATTEMPTS] = s->attempts;
    s->outstanding_sequence = sequence + 1U;
    s->outstanding_operation = operation;
    s->phase = VOS_SUPERVISOR_CONTEXT_AWAIT_ACK;
    *publish_sequence = s->outstanding_sequence;
    return VOS_SUPERVISOR_CONTEXT_PUBLISH;
}
