// SPDX-License-Identifier: Apache-2.0
#include "vos_lifecycle.h"
#ifndef VOS_LIFECYCLE_TARGET
#include <stdio.h>
#endif

static struct vos_kernel_effect_state effect;
static struct vos_kernel_lifecycle lifecycle;
static uint8_t request_storage[VOS_CTX_REQ_BYTES + 2];
static uint8_t ack_storage[VOS_CTX_ACK_BYTES + 2];
static uint8_t owned[32];
static vos_cap_t roots[VOS_KERNEL_EFFECT_UNITS];
static uint64_t masks[VOS_KERNEL_EFFECT_UNITS], fresh[VOS_KERNEL_EFFECT_UNITS];
static uint64_t bitmap, ticks;

static void put(uint8_t *bytes, uint32_t word, uint64_t value)
{
    uint32_t i;
    for (i = 0; i < 8; ++i) bytes[word * 8 + i] = (uint8_t)(value >> (i * 8));
}

static uint64_t get(const uint8_t *bytes, uint32_t word)
{
    uint32_t i;
    uint64_t value = 0;
    for (i = 0; i < 8; ++i) value |= (uint64_t)bytes[word * 8 + i] << (i * 8);
    return value;
}

static int fixture(uint64_t epoch)
{
    struct vos_supervisor_manifest manifest = {
        3, {0, 1, 2}, {0, 1, 2}, {0}, {0}, {0},
        0, 3, VOS_FAIL_STOP, 2, {3, 5}, 7, 3, 7
    };
    uint32_t i;
    for (i = 0; i < VOS_KERNEL_EFFECT_UNITS; ++i) {
        masks[i] = UINT64_C(1) << i;
        fresh[i] = UINT64_C(1) << (i + 16);
    }
    for (i = 0; i < VOS_CTX_REQ_BYTES + 2; ++i) request_storage[i] = 0;
    for (i = 0; i < VOS_CTX_ACK_BYTES + 2; ++i) ack_storage[i] = 0;
    request_storage[0] = 197; request_storage[VOS_CTX_REQ_BYTES + 1] = 199;
    ack_storage[0] = 193; ack_storage[VOS_CTX_ACK_BYTES + 1] = 191;
    bitmap = 0; ticks = 0;
    return vos_kernel_effect_init(&effect, &manifest, epoch) &&
        vos_kernel_own(&effect, 2, owned, 32, 0, 0) &&
        vos_kernel_effect_bind(&effect, roots, masks, &bitmap, &ticks, 1) &&
        vos_kernel_lifecycle_init(&lifecycle, &effect, ack_storage + 1);
}

static void request(uint32_t operation, uint64_t sequence)
{
    uint8_t *bytes = request_storage + 1;
    uint32_t i, j = 0, members;
    for (i = 0; i < VOS_CTX_REQ_BYTES; ++i) bytes[i] = 0;
    members = lifecycle.initial_consumed ? effect.manifest.restart_members : 7;
    put(bytes, VOS_CTX_REQ_SEQUENCE, sequence);
    put(bytes, VOS_CTX_REQ_OPERATION, operation);
    put(bytes, VOS_CTX_REQ_EPOCH, effect.epoch);
    put(bytes, VOS_CTX_REQ_MEMBERS, members);
    put(bytes, VOS_CTX_REQ_ATTEMPTS, lifecycle.attempts);
    if (operation == VOS_CTX_OP_START) {
        for (i = 0; i < effect.manifest.units; ++i) {
            uint32_t unit = effect.manifest.order[i];
            if ((members & (1U << unit)) != 0) {
                put(bytes, VOS_CTX_REQ_STARTS + j * VOS_CTX_START_WORDS, unit);
                put(bytes, VOS_CTX_REQ_STARTS + j * VOS_CTX_START_WORDS + 1,
                    effect.manifest.edges[unit] & ~effect.snapshot.retired[unit]);
                ++j;
            }
        }
        put(bytes, VOS_CTX_REQ_COUNT, j);
    }
}

static uint32_t prepare(uint64_t now)
{
    return vos_kernel_lifecycle_prepare(&lifecycle, &effect, request_storage + 1, now);
}

static int publish(uint64_t now)
{
    uint64_t sequence;
    uint8_t *ack = ack_storage + 1;
    put(ack, VOS_CTX_ACK_SEQUENCE, 0);
    sequence = vos_kernel_lifecycle_acknowledge(&lifecycle, &effect, ack, now);
    put(ack, VOS_CTX_ACK_SEQUENCE, sequence);
    return vos_kernel_lifecycle_published(&lifecycle, &effect, sequence);
}

static int initial(void)
{
    request(VOS_CTX_OP_START, 1);
    return prepare(10) == VOS_LIFECYCLE_START &&
        vos_kernel_lifecycle_start_finish(&lifecycle, &effect) && publish(11);
}

static int retire(uint64_t sequence, uint64_t now)
{
    request(VOS_CTX_OP_RETIRE, sequence);
    if (prepare(now) != VOS_LIFECYCLE_RETIRE) return 0;
    bitmap |= vos_kernel_lifecycle_mask(&lifecycle);
    effect.resident_clean = 1;
    return vos_kernel_lifecycle_retire_finish(&lifecycle, &effect, bitmap,
        roots, fresh, now + 1) && publish(now + 1);
}

int vos_lifecycle_target_controls(void)
{
    uint32_t i, j;
    uint64_t sequence, high_epoch = UINT64_C(0x100000007);
    uint8_t *ack = ack_storage + 1, *req = request_storage + 1;
#define CHECK(p) do { if (!(p)) return __LINE__; } while (0)
    CHECK(fixture(high_epoch));
    CHECK(get(ack, VOS_CTX_ACK_EPOCH) == high_epoch &&
          get(ack, VOS_CTX_ACK_REFUSED) == 3 && lifecycle.last_sequence == 0);
    request(VOS_CTX_OP_START, 0);
    CHECK(prepare(1) == VOS_LIFECYCLE_NONE && publish(1));
    request(VOS_CTX_OP_START, 2);
    CHECK(prepare(2) == VOS_LIFECYCLE_NONE && publish(2));
    CHECK(lifecycle.last_sequence == 0 && effect.started == 0);
    request(VOS_CTX_OP_RETIRE, 1);
    CHECK(prepare(3) == VOS_LIFECYCLE_ACK && publish(3));
    CHECK(lifecycle.status == VOS_CTX_STATUS_INVALID && !lifecycle.initial_consumed);
    CHECK(lifecycle.last_sequence == 1 && effect.epoch == high_epoch);

    /* Every padding and unused pair cell refuses before a unit starts. */
    for (i = VOS_CTX_REQ_STARTS + 3 * VOS_CTX_START_WORDS;
         i < VOS_CTX_REQ_WORDS; ++i) {
        CHECK(fixture(high_epoch)); request(VOS_CTX_OP_START, 1); put(req, i, 1);
        CHECK(prepare(10) == VOS_LIFECYCLE_ACK && effect.started == 0);
        CHECK(publish(10) && lifecycle.status == VOS_CTX_STATUS_INVALID);
    }
    /* Each scalar width, all batch positions and every grant are checked. */
    for (i = VOS_CTX_REQ_OPERATION; i <= VOS_CTX_REQ_ATTEMPTS; ++i) {
        if (i != VOS_CTX_REQ_EPOCH) {
            CHECK(fixture(high_epoch)); request(VOS_CTX_OP_START, 1);
            put(req, i, UINT64_C(0x100000000));
            CHECK(prepare(10) == VOS_LIFECYCLE_ACK && effect.started == 0 && publish(10));
            CHECK(lifecycle.status == VOS_CTX_STATUS_INVALID);
        }
    }
    for (i = 0; i < 3; ++i) {
        for (j = 0; j < VOS_CTX_START_WORDS; ++j) {
            CHECK(fixture(high_epoch)); request(VOS_CTX_OP_START, 1);
            put(req, VOS_CTX_REQ_STARTS + i * VOS_CTX_START_WORDS + j,
                UINT64_C(0x100000000));
            CHECK(prepare(10) == VOS_LIFECYCLE_ACK && publish(10) && effect.started == 0);
        }
        CHECK(fixture(high_epoch)); request(VOS_CTX_OP_START, 1);
        put(req, VOS_CTX_REQ_STARTS + i * VOS_CTX_START_WORDS + 1, 8);
        CHECK(prepare(10) == VOS_LIFECYCLE_ACK && publish(10) && effect.started == 0);
    }
    CHECK(fixture(high_epoch)); request(VOS_CTX_OP_START, 1);
    put(req, VOS_CTX_REQ_EPOCH, 7);
    CHECK(prepare(10) == VOS_LIFECYCLE_ACK && publish(10));
    CHECK(lifecycle.status == VOS_CTX_STATUS_STALE && !lifecycle.initial_consumed);
    request(VOS_CTX_OP_START, 2); put(req, VOS_CTX_REQ_STARTS, 1);
    CHECK(prepare(10) == VOS_LIFECYCLE_ACK && publish(10) && effect.started == 0);
    request(VOS_CTX_OP_START, 3); put(req, VOS_CTX_REQ_MEMBERS, 3);
    CHECK(prepare(10) == VOS_LIFECYCLE_ACK && publish(10) && effect.started == 0);
    request(VOS_CTX_OP_START, 4); put(req, VOS_CTX_REQ_COUNT, 2);
    CHECK(prepare(10) == VOS_LIFECYCLE_ACK && publish(10) && effect.started == 0);
    request(VOS_CTX_OP_START, 5); put(req, VOS_CTX_REQ_ATTEMPTS, 1);
    CHECK(prepare(10) == VOS_LIFECYCLE_ACK && publish(10) && effect.started == 0);

    CHECK(fixture(high_epoch)); request(VOS_CTX_OP_START, 1);
    CHECK(prepare(10) == VOS_LIFECYCLE_START && effect.locked);
    CHECK(!vos_kernel_lifecycle_retire_finish(&lifecycle, &effect, 7, roots, fresh, 10));
    CHECK(vos_kernel_lifecycle_start_finish(&lifecycle, &effect) && effect.locked);
    CHECK(lifecycle.prefix == 3 && lifecycle.phase == VOS_CTX_PHASE_RUNNING);
    sequence = vos_kernel_lifecycle_acknowledge(&lifecycle, &effect, ack, 11);
    CHECK(sequence == 1 && get(ack, VOS_CTX_ACK_SEQUENCE) == 0 && effect.locked);
    CHECK(!vos_kernel_lifecycle_published(&lifecycle, &effect, 2) && effect.locked);
    put(ack, VOS_CTX_ACK_SEQUENCE, sequence);
    CHECK(vos_kernel_lifecycle_published(&lifecycle, &effect, sequence) && !effect.locked);
    CHECK(prepare(12) == VOS_LIFECYCLE_NONE && publish(12));
    CHECK(lifecycle.prefix == 3 && lifecycle.phase == VOS_CTX_PHASE_RUNNING);
    CHECK(get(ack, VOS_CTX_ACK_NOW) == 12 && lifecycle.last_sequence == 1);
    request(VOS_CTX_OP_START, 2);
    CHECK(prepare(13) == VOS_LIFECYCLE_ACK && publish(13));
    CHECK(lifecycle.status == VOS_CTX_STATUS_INVALID && effect.started == 7);
    for (i = 0; i < 32; ++i) owned[i] = 213;
    CHECK(retire(3, 20));
    CHECK(effect.epoch == high_epoch + 1 && bitmap == 7 && effect.started == 0);
    CHECK(lifecycle.phase == VOS_CTX_PHASE_RETIRED && lifecycle.attempts == 1 &&
          lifecycle.deadline == 24 && get(ack, VOS_CTX_ACK_COUNT) == 0);
    for (i = 0; i < 32; ++i) CHECK(owned[i] == 0);
    for (i = 0; i < VOS_CTX_UNITS; ++i) CHECK(get(ack, VOS_CTX_ACK_RETIRED + i) == 0);
    request(VOS_CTX_OP_START, 4);
    CHECK(prepare(23) == VOS_LIFECYCLE_ACK && publish(23));
    CHECK(lifecycle.status == VOS_CTX_STATUS_EARLY && lifecycle.phase == VOS_CTX_PHASE_RETIRED);
    request(VOS_CTX_OP_START, 5);
    CHECK(prepare(24) == VOS_LIFECYCLE_START && vos_kernel_lifecycle_start_finish(&lifecycle, &effect));
    CHECK(publish(24) && effect.started == 7 && lifecycle.attempts == 1);

    /* Backoff begins after clearing/replenishment, at acknowledgment time. */
    CHECK(fixture(7) && initial()); request(VOS_CTX_OP_RETIRE, 2);
    CHECK(prepare(20) == VOS_LIFECYCLE_RETIRE);
    bitmap = 7; effect.resident_clean = 1;
    CHECK(vos_kernel_lifecycle_retire_finish(&lifecycle, &effect, bitmap, roots, fresh, 21));
    CHECK(publish(30) && lifecycle.deadline == 33);
    request(VOS_CTX_OP_START, 3);
    CHECK(prepare(32) == VOS_LIFECYCLE_ACK && publish(32) && lifecycle.status == VOS_CTX_STATUS_EARLY);
    request(VOS_CTX_OP_START, 0);
    CHECK(prepare(33) == VOS_LIFECYCLE_NONE && publish(33) && lifecycle.deadline == 33);
    CHECK(lifecycle.last_sequence == 3 && lifecycle.status == VOS_CTX_STATUS_EARLY);

    /* A failing second effect preserves the successful prefix and consumes
     * initial eligibility. Only a new retirement can authorize retry. */
    CHECK(fixture(7)); request(VOS_CTX_OP_START, 1);
    CHECK(prepare(10) == VOS_LIFECYCLE_START);
    effect.unit[1].running = 1;
    CHECK(!vos_kernel_lifecycle_start_finish(&lifecycle, &effect));
    CHECK(effect.started == 1 && !effect.unit[2].running && lifecycle.prefix == 1);
    CHECK(publish(11) && get(ack, VOS_CTX_ACK_REFUSED) == 1);
    request(VOS_CTX_OP_START, 2);
    CHECK(prepare(12) == VOS_LIFECYCLE_ACK && publish(12) && effect.started == 1);
    CHECK(retire(3, 20));

    /* Each hardware prerequisite can leave a retirement unavailable. */
    for (i = 0; i < 4; ++i) {
        CHECK(fixture(7) && initial()); request(VOS_CTX_OP_RETIRE, 2);
        CHECK(prepare(20) == VOS_LIFECYCLE_RETIRE);
        bitmap = i == 0 ? 6 : 7; effect.resident_clean = i == 1 ? 0 : 1;
        if (i == 2) fresh[0] = 1;
        CHECK(!vos_kernel_lifecycle_retire_finish(&lifecycle, &effect, bitmap,
                                                 roots, fresh, i == 3 ? 19 : 21));
        CHECK(publish(21) && lifecycle.phase == VOS_CTX_PHASE_FAILED && lifecycle.attempts == 0);
        request(VOS_CTX_OP_START, 3);
        CHECK(prepare(22) == VOS_LIFECYCLE_ACK && publish(22));
        CHECK(lifecycle.status == VOS_CTX_STATUS_INVALID);
    }
    CHECK(fixture(7) && initial()); effect.unit[2].inflight = 1;
    request(VOS_CTX_OP_RETIRE, 2);
    CHECK(prepare(20) == VOS_LIFECYCLE_ACK && publish(20));
    CHECK(lifecycle.status == VOS_CTX_STATUS_INCOMPLETE && effect.epoch == 7);

    /* A smaller ownership-closed set retains the unaffected unit. */
    CHECK(fixture(7)); effect.manifest.edges[2] = 0; effect.manifest.restart_members = 3;
    CHECK(initial() && retire(2, 20) && effect.started == 4);
    request(VOS_CTX_OP_START, 3);
    CHECK(prepare(24) == VOS_LIFECYCLE_START && vos_kernel_lifecycle_start_finish(&lifecycle, &effect));
    CHECK(publish(24) && lifecycle.prefix == 2 && effect.started == 7);

    CHECK(fixture(UINT64_MAX) && initial()); request(VOS_CTX_OP_RETIRE, 2);
    CHECK(prepare(20) == VOS_LIFECYCLE_ACK && publish(20) && effect.epoch == UINT64_MAX);
    CHECK(fixture(7)); lifecycle.last_sequence = UINT64_MAX - 2;
    request(VOS_CTX_OP_START, UINT64_MAX - 1);
    CHECK(prepare(10) == VOS_LIFECYCLE_START && vos_kernel_lifecycle_start_finish(&lifecycle, &effect));
    CHECK(publish(11) && lifecycle.last_sequence == UINT64_MAX - 1);
    request(VOS_CTX_OP_RETIRE, UINT64_MAX);
    CHECK(prepare(20) == VOS_LIFECYCLE_NONE && publish(20) && effect.epoch == 7);
    CHECK(lifecycle.prefix == 3 && lifecycle.last_sequence == UINT64_MAX - 1);
    CHECK(fixture(7)); request(VOS_CTX_OP_START, 1);
    vos_kernel_lifecycle_fault(req);
    CHECK(prepare(10) == VOS_LIFECYCLE_NONE && publish(10) && !lifecycle.initial_consumed);
    CHECK(request_storage[0] == 197 && request_storage[VOS_CTX_REQ_BYTES + 1] == 199);
    CHECK(ack_storage[0] == 193 && ack_storage[VOS_CTX_ACK_BYTES + 1] == 191);
    return 0;
#undef CHECK
}

#ifndef VOS_LIFECYCLE_TARGET
int main(void)
{
    int result = vos_lifecycle_target_controls();
    if (result) fprintf(stderr, "FAIL lifecycle control line %d\n", result);
    else fprintf(stderr, "ok lifecycle scalar request controls\n");
    return result != 0;
}
#endif
