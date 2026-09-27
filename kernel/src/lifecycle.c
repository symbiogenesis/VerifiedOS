// SPDX-License-Identifier: Apache-2.0
#include "vos_lifecycle.h"

static uint64_t lifecycle_word(const uint8_t *bytes, uint32_t word)
{
    uint32_t i;
    uint64_t result = 0;
    for (i = 0; i < VOS_CTX_WORD_BYTES; ++i)
        result |= (uint64_t)bytes[word * VOS_CTX_WORD_BYTES + i] << (i * 8U);
    return result;
}

static void lifecycle_put(uint8_t *bytes, uint32_t word, uint64_t value)
{
    uint32_t i;
    for (i = 0; i < VOS_CTX_WORD_BYTES; ++i)
        bytes[word * VOS_CTX_WORD_BYTES + i] = (uint8_t)(value >> (i * 8U));
}

static void lifecycle_fields(const struct vos_kernel_lifecycle *c,
                              const struct vos_kernel_effect_state *e,
                              uint8_t *ack)
{
    uint32_t i;
    for (i = 1; i < VOS_CTX_ACK_WORDS; ++i)
        lifecycle_put(ack, i, 0);
    lifecycle_put(ack, VOS_CTX_ACK_STATUS, c->status);
    lifecycle_put(ack, VOS_CTX_ACK_OPERATION, c->operation);
    lifecycle_put(ack, VOS_CTX_ACK_EPOCH, e->epoch);
    lifecycle_put(ack, VOS_CTX_ACK_PHASE, c->phase);
    lifecycle_put(ack, VOS_CTX_ACK_MEMBERS, c->members);
    lifecycle_put(ack, VOS_CTX_ACK_STARTED, e->started);
    lifecycle_put(ack, VOS_CTX_ACK_COUNT, c->prefix);
    lifecycle_put(ack, VOS_CTX_ACK_REFUSED, c->refused);
    lifecycle_put(ack, VOS_CTX_ACK_ATTEMPTS, c->attempts);
    lifecycle_put(ack, VOS_CTX_ACK_NOW, c->now);
    lifecycle_put(ack, VOS_CTX_ACK_DEADLINE, c->deadline);
    for (i = 0; i < VOS_CTX_UNITS; ++i)
        lifecycle_put(ack, VOS_CTX_ACK_RETIRED + i, e->snapshot.retired[i]);
}

int vos_kernel_lifecycle_init(struct vos_kernel_lifecycle *c,
                              struct vos_kernel_effect_state *e, uint8_t *ack)
{
    uint32_t i;
    if (c == 0 || e == 0 || ack == 0 || !e->bound || e->locked || e->started ||
        e->retirement_pending || e->needs_replenish ||
        !vos_supervisor_manifest_ok(&e->manifest) ||
        e->manifest.units > VOS_KERNEL_EFFECT_UNITS || e->snapshot.number != e->epoch)
        return 0;
    c->last_sequence = 0; c->pending_sequence = 0; c->request_epoch = e->epoch;
    c->mask = 0; c->now = 0; c->deadline = 0; c->completion_epoch = e->epoch;
    c->initialized = 1; c->action = VOS_LIFECYCLE_NONE; c->held = 0;
    c->initial_consumed = 0; c->operation = VOS_CTX_OP_NONE;
    c->status = VOS_CTX_STATUS_OK; c->phase = VOS_CTX_PHASE_INITIAL;
    c->members = 0; c->count = 0; c->prefix = 0;
    c->refused = e->manifest.units; c->attempts = 0;
    for (i = 0; i < VOS_CTX_UNITS; ++i) {
        c->starts[i].unit = 0; c->starts[i].grants = 0; c->starts[i].epoch = 0;
    }
    lifecycle_fields(c, e, ack);
    return 1;
}

uint32_t vos_kernel_lifecycle_prepare(struct vos_kernel_lifecycle *c,
                                      struct vos_kernel_effect_state *e,
                                      const uint8_t *request, uint64_t now)
{
    uint64_t sequence, value, epoch;
    uint32_t i, j, unit, selected, count, operation, members, attempts;
    struct vos_supervisor_epoch snapshot;
    if (c == 0 || e == 0 || request == 0 || !c->initialized || !e->bound ||
        c->action != VOS_LIFECYCLE_NONE || e->locked)
        return VOS_LIFECYCLE_NONE;
    sequence = lifecycle_word(request, VOS_CTX_REQ_SEQUENCE);
    if (sequence == 0 || c->last_sequence == UINT64_MAX ||
        sequence != c->last_sequence + 1 || sequence == UINT64_MAX)
        return VOS_LIFECYCLE_NONE;
    c->pending_sequence = sequence;
    c->action = VOS_LIFECYCLE_ACK;
    c->operation = VOS_CTX_OP_NONE; c->members = 0; c->count = 0;
    c->prefix = 0; c->refused = e->manifest.units; c->mask = 0;
    c->status = VOS_CTX_STATUS_INVALID;
    if (now < c->now) return c->action;
    c->now = now;
    value = lifecycle_word(request, VOS_CTX_REQ_OPERATION);
    if (value != VOS_CTX_OP_RETIRE && value != VOS_CTX_OP_START) return c->action;
    operation = (uint32_t)value; c->operation = operation;
    value = lifecycle_word(request, VOS_CTX_REQ_MEMBERS);
    if (value > UINT32_MAX) return c->action;
    members = (uint32_t)value; c->members = members;
    value = lifecycle_word(request, VOS_CTX_REQ_COUNT);
    if (value > VOS_CTX_UNITS) return c->action;
    count = (uint32_t)value; c->count = count;
    value = lifecycle_word(request, VOS_CTX_REQ_ATTEMPTS);
    if (value > UINT32_MAX) return c->action;
    attempts = (uint32_t)value;
    for (i = VOS_CTX_REQ_USED; i < VOS_CTX_REQ_WORDS; ++i)
        if (lifecycle_word(request, i) != 0) return c->action;
    for (i = 0; i < VOS_CTX_UNITS; ++i) {
        j = VOS_CTX_REQ_STARTS + i * VOS_CTX_START_WORDS;
        value = lifecycle_word(request, j + VOS_CTX_START_UNIT);
        if (value > UINT32_MAX || (i >= count && value != 0)) return c->action;
        c->starts[i].unit = (uint32_t)value;
        value = lifecycle_word(request, j + VOS_CTX_START_GRANTS);
        if (value > UINT32_MAX || (i >= count && value != 0)) return c->action;
        c->starts[i].grants = (uint32_t)value;
    }
    epoch = lifecycle_word(request, VOS_CTX_REQ_EPOCH);
    c->request_epoch = epoch;
    if (epoch != e->epoch || e->snapshot.number != epoch) {
        c->status = VOS_CTX_STATUS_STALE; return c->action;
    }
    if (attempts != c->attempts) return c->action;
    if (operation == VOS_CTX_OP_RETIRE) {
        if (!c->initial_consumed || members != e->manifest.restart_members || count != 0 ||
            (c->phase != VOS_CTX_PHASE_RUNNING && c->phase != VOS_CTX_PHASE_FAILED) ||
            c->attempts == UINT32_MAX || epoch == UINT64_MAX ||
            now > UINT64_MAX - vos_supervisor_backoff(&e->manifest, c->attempts))
            return c->action;
        c->mask = vos_kernel_retirement_mask(e, members);
        if (c->mask == 0) {
            c->status = VOS_CTX_STATUS_INCOMPLETE; return c->action;
        }
        c->action = VOS_LIFECYCLE_RETIRE;
        return c->action;
    }
    selected = c->initial_consumed ? e->manifest.restart_members :
               (1U << e->manifest.units) - 1U;
    if (members != selected || e->retirement_pending || e->needs_replenish ||
        (c->initial_consumed && (c->phase != VOS_CTX_PHASE_RETIRED ||
                                c->completion_epoch != epoch)))
        return c->action;
    if (c->initial_consumed && now < c->deadline) {
        c->status = VOS_CTX_STATUS_EARLY; return c->action;
    }
    j = 0;
    for (i = 0; i < e->manifest.units; ++i) {
        unit = e->manifest.order[i];
        if ((selected & (1U << unit)) != 0) {
            if (j >= count || c->starts[j].unit != unit) return c->action;
            c->starts[j].epoch = epoch;
            if (!vos_supervisor_request_current(&e->manifest, &e->snapshot,
                                                epoch, &c->starts[j]))
                return c->action;
            ++j;
        }
    }
    if (j != count) return c->action;
    if (!vos_kernel_acquire(e, &snapshot, &epoch)) return c->action;
    c->held = 1;
    for (i = 0; i < count; ++i)
        if (!vos_supervisor_request_current(&e->manifest, &snapshot, epoch, &c->starts[i])) {
            c->status = VOS_CTX_STATUS_STALE; return c->action;
        }
    c->initial_consumed = 1;
    c->phase = VOS_CTX_PHASE_FAILED;
    c->action = VOS_LIFECYCLE_START;
    return c->action;
}

uint64_t vos_kernel_lifecycle_mask(const struct vos_kernel_lifecycle *c)
{
    return c != 0 && c->action == VOS_LIFECYCLE_RETIRE ? c->mask : 0;
}

int vos_kernel_lifecycle_retire_finish(struct vos_kernel_lifecycle *c,
                                       struct vos_kernel_effect_state *e,
                                       uint64_t observed,
                                       const vos_cap_t *fresh_roots,
                                       const uint64_t *fresh_masks,
                                       uint64_t now)
{
    struct vos_completion completion;
    uint32_t delay;
    if (c == 0 || e == 0 || c->action != VOS_LIFECYCLE_RETIRE)
        return 0;
    c->action = VOS_LIFECYCLE_ACK; c->phase = VOS_CTX_PHASE_FAILED;
    c->status = VOS_CTX_STATUS_INCOMPLETE;
    delay = vos_supervisor_backoff(&e->manifest, c->attempts);
    if (now < c->now || now > UINT64_MAX - delay ||
        !vos_kernel_publication(e, c->request_epoch, c->mask, observed) ||
        !vos_kernel_retire(e, c->members, &completion) ||
        !completion.epoch_advanced || !vos_semantic_completion(&completion) ||
        e->epoch != c->request_epoch + 1 ||
        !vos_kernel_replenish(e, e->epoch, fresh_roots, fresh_masks))
        return 0;
    c->now = now; c->completion_epoch = e->epoch;
    ++c->attempts;
    c->phase = VOS_CTX_PHASE_RETIRED; c->status = VOS_CTX_STATUS_OK;
    return 1;
}

int vos_kernel_lifecycle_start_finish(struct vos_kernel_lifecycle *c,
                                      struct vos_kernel_effect_state *e)
{
    uint32_t i;
    if (c == 0 || e == 0 || c->action != VOS_LIFECYCLE_START || !c->held || !e->locked)
        return 0;
    c->action = VOS_LIFECYCLE_ACK; c->status = VOS_CTX_STATUS_START_REFUSED;
    for (i = 0; i < c->count; ++i) {
        if (!vos_kernel_start(e, &c->starts[i])) {
            c->refused = c->starts[i].unit;
            return 0;
        }
        ++c->prefix;
    }
    c->phase = VOS_CTX_PHASE_RUNNING; c->status = VOS_CTX_STATUS_OK;
    return 1;
}

uint64_t vos_kernel_lifecycle_acknowledge(struct vos_kernel_lifecycle *c,
                                         struct vos_kernel_effect_state *e,
                                         uint8_t *ack, uint64_t now)
{
    uint32_t delay;
    if (c == 0 || e == 0 || ack == 0 || !c->initialized ||
        (c->action != VOS_LIFECYCLE_NONE && c->action != VOS_LIFECYCLE_ACK))
        return 0;
    if (c->pending_sequence != 0 && c->operation == VOS_CTX_OP_RETIRE &&
        c->status == VOS_CTX_STATUS_OK && c->phase == VOS_CTX_PHASE_RETIRED) {
        delay = vos_supervisor_backoff(&e->manifest, c->attempts - 1);
        if (now < c->now || now > UINT64_MAX - delay) {
            c->status = VOS_CTX_STATUS_INCOMPLETE; c->phase = VOS_CTX_PHASE_FAILED;
        } else {
            c->deadline = now + delay;
        }
    }
    if (now >= c->now) c->now = now;
    lifecycle_fields(c, e, ack);
    c->action = VOS_LIFECYCLE_PUBLISH;
    return c->pending_sequence != 0 ? c->pending_sequence : c->last_sequence;
}

int vos_kernel_lifecycle_published(struct vos_kernel_lifecycle *c,
                                   struct vos_kernel_effect_state *e, uint64_t sequence)
{
    uint64_t expected;
    if (c == 0 || e == 0 || c->action != VOS_LIFECYCLE_PUBLISH) return 0;
    expected = c->pending_sequence != 0 ? c->pending_sequence : c->last_sequence;
    if (sequence != expected) return 0;
    c->last_sequence = expected; c->pending_sequence = 0;
    if (c->held) vos_kernel_release(e);
    c->held = 0; c->action = VOS_LIFECYCLE_NONE;
    return 1;
}

void vos_kernel_lifecycle_fault(uint8_t *request)
{
    if (request != 0) lifecycle_put(request, VOS_CTX_REQ_SEQUENCE, 0);
}
