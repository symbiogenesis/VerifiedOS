// SPDX-License-Identifier: Apache-2.0
/* Native producer/consumer join; roots, clock and resident scrub are host data. */
#include "vos_supervisor_context.h"
#include "vos_lifecycle.h"
#include <stdio.h>

static struct vos_kernel_effect_state effects;
static struct vos_kernel_lifecycle lifecycle;
static struct vos_supervisor_context supervisor;
static uint8_t request[VOS_CTX_REQ_BYTES], acknowledgment[VOS_CTX_ACK_BYTES];
static uint8_t owned[3][32];
static vos_cap_t roots[3];
static uint64_t masks[3], fresh_masks[3], bitmap, clock_value;
static uint64_t ack[VOS_CTX_ACK_WORDS], planned[VOS_CTX_REQ_WORDS], sequence;

static void put(uint8_t *bytes, uint32_t word, uint64_t value)
{
    uint32_t i;
    for (i = 0; i < VOS_CTX_WORD_BYTES; ++i)
        bytes[word * VOS_CTX_WORD_BYTES + i] = (uint8_t)(value >> (8U * i));
}

static uint64_t get(const uint8_t *bytes, uint32_t word)
{
    uint32_t i;
    uint64_t value = 0;
    for (i = 0; i < VOS_CTX_WORD_BYTES; ++i)
        value |= (uint64_t)bytes[word * VOS_CTX_WORD_BYTES + i] << (8U * i);
    return value;
}

static int fixture(uint64_t epoch, uint32_t retired)
{
    uint32_t i, j;
    const struct vos_supervisor_manifest *m = &vos_m8a_supervisor_manifest;
    if (m->units != 3 || m->restart_members != 7 || m->backoff_count != 4 ||
        m->backoff[0] != 1 || m->order[0] != 0 || m->order[1] != 1 ||
        m->order[2] != 2 || m->edges[0] != 0 || m->edges[1] != 1 || m->edges[2] != 0)
        return 0;
    for (i = 0; i < VOS_CTX_REQ_BYTES; ++i) request[i] = 0;
    for (i = 0; i < VOS_CTX_ACK_BYTES; ++i) acknowledgment[i] = 0;
    bitmap = 0; clock_value = 0;
    if (!vos_kernel_effect_init(&effects, m, epoch)) return 0;
    for (i = 0; i < 3; ++i) {
        masks[i] = UINT64_C(1) << i;
        fresh_masks[i] = UINT64_C(1) << (i + 16);
        for (j = 0; j < 32; ++j) owned[i][j] = 213;
        if (!vos_kernel_own(&effects, i, owned[i], 32, 0, 0)) return 0;
    }
    effects.snapshot.retired[1] = retired;
    return vos_kernel_effect_bind(&effects, roots, masks, &bitmap, &clock_value, 1) &&
           vos_kernel_lifecycle_init(&lifecycle, &effects, acknowledgment);
}

static void read_ack(void)
{
    uint32_t i;
    for (i = 0; i < VOS_CTX_ACK_WORDS; ++i) ack[i] = get(acknowledgment, i);
}

static enum vos_supervisor_context_result react(uint32_t desired)
{
    read_ack();
    if (!vos_supervisor_context_recover(&vos_m8a_supervisor_manifest, ack, &supervisor))
        return VOS_SUPERVISOR_CONTEXT_REJECTED;
    return vos_supervisor_context_step(&vos_m8a_supervisor_manifest, &supervisor,
                                       ack, desired, planned, &sequence);
}

static void publish_request(void)
{
    uint32_t i;
    put(request, VOS_CTX_REQ_SEQUENCE, 0);
    for (i = 1; i < VOS_CTX_REQ_WORDS; ++i) put(request, i, planned[i]);
    /* Native ordering only; the target wrapper owns its required fence. */
    put(request, VOS_CTX_REQ_SEQUENCE, sequence);
}

static int publish_ack(uint64_t now)
{
    uint64_t published;
    put(acknowledgment, VOS_CTX_ACK_SEQUENCE, 0);
    published = vos_kernel_lifecycle_acknowledge(&lifecycle, &effects, acknowledgment, now);
    put(acknowledgment, VOS_CTX_ACK_SEQUENCE, published);
    return vos_kernel_lifecycle_published(&lifecycle, &effects, published);
}

int main(void)
{
    uint32_t i, j;
    uint64_t high = UINT64_C(0x100000007);
#define CHECK(p) do { if (!(p)) { fprintf(stderr, "FAIL generated context join line %d\n", __LINE__); return 1; } } while (0)
    CHECK(fixture(high, 1));
    CHECK(react(VOS_SUPERVISOR_CONTEXT_INITIAL) == VOS_SUPERVISOR_CONTEXT_PUBLISH);
    CHECK(sequence == 1 && planned[VOS_CTX_REQ_SEQUENCE] == 0 &&
          planned[VOS_CTX_REQ_EPOCH] == high && planned[VOS_CTX_REQ_MEMBERS] == 7 &&
          planned[VOS_CTX_REQ_COUNT] == 3 && planned[VOS_CTX_REQ_STARTS] == 0 &&
          planned[VOS_CTX_REQ_STARTS + 2] == 1 && planned[VOS_CTX_REQ_STARTS + 3] == 0 &&
          planned[VOS_CTX_REQ_STARTS + 4] == 2);
    publish_request();
    /* An actual consumer fault clears a publication without advancing its watermark. */
    vos_kernel_lifecycle_fault(request);
    CHECK(get(request, VOS_CTX_REQ_SEQUENCE) == 0);
    CHECK(vos_kernel_lifecycle_prepare(&lifecycle, &effects, request, 10) == VOS_LIFECYCLE_NONE);
    CHECK(publish_ack(10) && lifecycle.last_sequence == 0 && effects.started == 0);
    CHECK(react(VOS_SUPERVISOR_CONTEXT_INITIAL) == VOS_SUPERVISOR_CONTEXT_PUBLISH);
    CHECK(sequence == 1);
    publish_request();
    CHECK(vos_kernel_lifecycle_prepare(&lifecycle, &effects, request, 11) == VOS_LIFECYCLE_START);
    CHECK(vos_kernel_lifecycle_start_finish(&lifecycle, &effects) && effects.locked);
    CHECK(publish_ack(12) && !effects.locked && lifecycle.last_sequence == 1);
    read_ack();
    CHECK(vos_supervisor_context_step(&vos_m8a_supervisor_manifest, &supervisor, ack,
          VOS_SUPERVISOR_CONTEXT_INITIAL, planned, &sequence) == VOS_SUPERVISOR_CONTEXT_DONE);
    CHECK(supervisor.started == 7 && supervisor.count == 3 && supervisor.epoch == high);
    CHECK(react(VOS_SUPERVISOR_CONTEXT_HOLD) == VOS_SUPERVISOR_CONTEXT_IDLE && sequence == 0);
    CHECK(react(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_PUBLISH);
    CHECK(sequence == 2 && planned[VOS_CTX_REQ_OPERATION] == VOS_CTX_OP_RETIRE);
    publish_request();
    CHECK(vos_kernel_lifecycle_prepare(&lifecycle, &effects, request, 20) == VOS_LIFECYCLE_RETIRE);
    bitmap |= vos_kernel_lifecycle_mask(&lifecycle);
    effects.resident_clean = 1; /* A host premise, not an observed architectural scrub. */
    CHECK(vos_kernel_lifecycle_retire_finish(&lifecycle, &effects, bitmap, roots, fresh_masks, 21));
    CHECK(effects.epoch == high + 1 && effects.started == 0 && bitmap == 7);
    for (i = 0; i < 3; ++i) for (j = 0; j < 32; ++j) CHECK(owned[i][j] == 0);
    /* Delayed acknowledgment anchors backoff after completed clearing and replenishment. */
    CHECK(publish_ack(30) && lifecycle.deadline == 31 && lifecycle.attempts == 1);
    CHECK(react(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_WAIT && sequence == 0);
    put(request, VOS_CTX_REQ_SEQUENCE, 0);
    CHECK(vos_kernel_lifecycle_prepare(&lifecycle, &effects, request, 31) == VOS_LIFECYCLE_NONE);
    CHECK(publish_ack(31) && lifecycle.last_sequence == 2 && lifecycle.deadline == 31);
    CHECK(react(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_PUBLISH);
    CHECK(sequence == 3 && planned[VOS_CTX_REQ_EPOCH] == high + 1 &&
          planned[VOS_CTX_REQ_ATTEMPTS] == 1 && planned[VOS_CTX_REQ_STARTS + 3] == 1);
    publish_request();
    /* A malformed request consumes a sequence while retaining completed retirement. */
    put(request, VOS_CTX_REQ_OPERATION, 99);
    CHECK(vos_kernel_lifecycle_prepare(&lifecycle, &effects, request, 31) == VOS_LIFECYCLE_ACK);
    CHECK(publish_ack(31) && lifecycle.last_sequence == 3 &&
          lifecycle.phase == VOS_CTX_PHASE_RETIRED && lifecycle.status == VOS_CTX_STATUS_INVALID);
    CHECK(react(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_PUBLISH);
    CHECK(sequence == 4 && supervisor.acknowledged_sequence == 3);
    publish_request();
    CHECK(vos_kernel_lifecycle_prepare(&lifecycle, &effects, request, 31) == VOS_LIFECYCLE_START);
    CHECK(vos_kernel_lifecycle_start_finish(&lifecycle, &effects) && publish_ack(32));
    read_ack();
    CHECK(vos_supervisor_context_step(&vos_m8a_supervisor_manifest, &supervisor, ack,
          VOS_SUPERVISOR_CONTEXT_RESTART, planned, &sequence) == VOS_SUPERVISOR_CONTEXT_DONE);
    CHECK(effects.started == 7 && !effects.needs_replenish && !effects.retirement_pending &&
          supervisor.acknowledged_sequence == 4 && supervisor.epoch == high + 1);
    /* A real refused second effect keeps its prefix and requires a new retirement. */
    CHECK(fixture(high, 0));
    CHECK(react(VOS_SUPERVISOR_CONTEXT_INITIAL) == VOS_SUPERVISOR_CONTEXT_PUBLISH);
    publish_request();
    CHECK(vos_kernel_lifecycle_prepare(&lifecycle, &effects, request, 10) == VOS_LIFECYCLE_START);
    effects.unit[1].running = 1;
    CHECK(!vos_kernel_lifecycle_start_finish(&lifecycle, &effects) && publish_ack(11));
    read_ack();
    CHECK(vos_supervisor_context_step(&vos_m8a_supervisor_manifest, &supervisor, ack,
          VOS_SUPERVISOR_CONTEXT_INITIAL, planned, &sequence) == VOS_SUPERVISOR_CONTEXT_REJECTED);
    CHECK(supervisor.started == 1 && supervisor.count == 1 && supervisor.refused == 1);
    CHECK(react(VOS_SUPERVISOR_CONTEXT_RESTART) == VOS_SUPERVISOR_CONTEXT_PUBLISH);
    CHECK(sequence == 2 && planned[VOS_CTX_REQ_OPERATION] == VOS_CTX_OP_RETIRE);
    publish_request();
    CHECK(vos_kernel_lifecycle_prepare(&lifecycle, &effects, request, 20) == VOS_LIFECYCLE_RETIRE);
    fprintf(stdout, "ok generated manifest nonblocking lifecycle join\n");
    return 0;
#undef CHECK
}
