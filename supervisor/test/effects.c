// SPDX-License-Identifier: Apache-2.0
#include <stdio.h>
#include <string.h>
#include "vos_supervisor_effects.h"

enum event { RETIRE = 1, WAIT, ACQUIRE, START, RELEASE };

struct binding {
    struct vos_supervisor_manifest manifest;
    struct vos_supervisor_manifest *external;
    uint32_t selected, delay, count, units[VOS_SUPERVISOR_UNITS];
    uint32_t completion_bits, locked, acquired, released;
    uint64_t epoch, stale;
    uint32_t calls, fail_at, started, started_members, error;
    uint32_t events[VOS_SUPERVISOR_UNITS + 4];
    uint32_t event_count, mutate;
};

static int effect(struct binding *b, uint32_t event)
{
    if (b->event_count >= VOS_SUPERVISOR_UNITS + 4) {
        b->error = 1;
        return 0;
    }
    b->events[b->event_count++] = event;
    if (event == RELEASE)
        return 1;
    ++b->calls;
    return b->calls != b->fail_at;
}

static int retire(void *context, uint32_t members, struct vos_completion *out)
{
    struct binding *b = context;
    if (b->locked || members != b->selected || b->event_count != 0)
        b->error = 1;
    if (!effect(b, RETIRE))
        return 0;
    out->bits_published = (b->completion_bits >> 0) & 1U;
    out->epoch_advanced = (b->completion_bits >> 1) & 1U;
    out->resident_roots_cleared = (b->completion_bits >> 2) & 1U;
    out->saved_contexts_filtered = (b->completion_bits >> 3) & 1U;
    out->loans_cancelled = (b->completion_bits >> 4) & 1U;
    out->device_boundary_reached = (b->completion_bits >> 5) & 1U;
    if (b->mutate)
        b->external->order[0] = VOS_SUPERVISOR_UNITS;
    return 1;
}

static int wait_delay(void *context, uint32_t delay)
{
    struct binding *b = context;
    if (b->locked || delay != b->delay || b->event_count != 1)
        b->error = 1;
    if (!effect(b, WAIT))
        return 0;
    /* A revocation during backoff forces the subsequent read to be fresh. */
    ++b->epoch;
    return 1;
}

static int acquire(void *context, struct vos_supervisor_epoch *out,
                   uint64_t *current)
{
    struct binding *b = context;
    uint32_t i;
    if (b->locked)
        b->error = 1;
    if (!effect(b, ACQUIRE))
        return 0;
    b->locked = 1;
    ++b->acquired;
    out->number = b->epoch;
    *current = b->epoch + b->stale;
    for (i = 0; i < b->manifest.units; ++i)
        out->retired[i] = (i + b->epoch) & 1U ? b->manifest.edges[i] : 0;
    return 1;
}

static int start(void *context, const struct vos_supervisor_start *request)
{
    struct binding *b = context;
    uint32_t grants;
    if (request->unit >= b->manifest.units) {
        b->error = 1;
        return 0;
    }
    grants = (request->unit + b->epoch) & 1U ? 0 : b->manifest.edges[request->unit];
    if (!b->locked || request->epoch != b->epoch || b->started >= b->count ||
        request->unit != b->units[b->started] || request->grants != grants)
        b->error = 1;
    if (!effect(b, START))
        return 0;
    ++b->started;
    b->started_members |= 1U << request->unit;
    return 1;
}

static void release(void *context)
{
    struct binding *b = context;
    if (!b->locked)
        b->error = 1;
    (void)effect(b, RELEASE);
    b->locked = 0;
    ++b->released;
}

static const struct vos_supervisor_effects operations = {
    retire, wait_delay, acquire, start, release
};

static struct binding fixture(uint32_t units, uint32_t restart, uint32_t attempts,
                              uint32_t cut)
{
    struct binding b = {0};
    uint32_t i, unit, predecessor = 0;
    b.manifest = vos_m8a_supervisor_manifest;
    b.manifest.units = units;
    b.manifest.restart_members = 0;
    b.completion_bits = 61; /* Epoch advancement is deliberately absent. */
    b.epoch = 7;
    b.delay = restart ? (attempts == 0 ? 1 : attempts == 1 ? 2 :
                        attempts == 2 ? 3 : 5) : 0;
    for (i = 0; i < units; ++i) {
        /* Descending IDs distinguish manifest order from numeric order. */
        unit = units - 1 - i;
        b.manifest.order[i] = unit;
        b.manifest.edges[unit] = predecessor;
        predecessor = 1U << unit;
        if (i >= cut)
            b.manifest.restart_members |= 1U << unit;
        if (!restart || i >= cut) {
            b.units[b.count++] = unit;
            b.selected |= 1U << unit;
        }
    }
    return b;
}

static int trace_ok(const struct binding *b, uint32_t restart, uint32_t starts,
                    uint32_t prefix)
{
    uint32_t i, at = 0;
    if (restart && prefix >= 1 && b->events[at++] != RETIRE)
        return 0;
    if (restart && prefix >= 2 && b->events[at++] != WAIT)
        return 0;
    if (prefix >= (restart ? 3U : 1U) && b->events[at++] != ACQUIRE)
        return 0;
    for (i = 0; i < starts; ++i)
        if (b->events[at++] != START)
            return 0;
    if (b->acquired && b->events[at++] != RELEASE)
        return 0;
    return at == b->event_count;
}

int vos_supervisor_effect_controls(void)
{
    struct binding b;
    struct vos_supervisor_execution result;
    struct vos_supervisor_effects missing;
    enum vos_supervisor_execution_status status, expected;
    uint32_t n, mode, attempt, cut, failure, pre, starts, i, mask;
    uint32_t checks = 0, runs = 0;
#define CHECK(c) do { ++checks; if (!(c)) { \
    fprintf(stderr, "FAIL effect control %u run %u line %d\n", \
            checks, runs, __LINE__); return 1; } } while (0)
    /* Generate every capacity, every nonempty ownership-closed chain suffix,
     * backoff boundary, and failing effect position beside the successful run. */
    for (n = 1; n <= VOS_SUPERVISOR_UNITS; ++n)
        for (mode = 0; mode <= 1; ++mode)
            for (attempt = 0; attempt <= 5; ++attempt)
                for (cut = 0; cut < (mode ? n : 1); ++cut) {
                    pre = mode ? 3 : 1;
                    for (failure = 0; failure <= pre + n - cut; ++failure) {
                        b = fixture(n, mode, attempt, cut);
                        b.fail_at = failure;
                        ++runs;
                        status = vos_supervisor_execute(&b.manifest, mode, attempt,
                                                       &operations, &b, &result);
                        if (failure == 0)
                            expected = VOS_SUPERVISOR_EXECUTED;
                        else if (mode && failure == 1)
                            expected = VOS_SUPERVISOR_RETIRE_REFUSED;
                        else if (mode && failure == 2)
                            expected = VOS_SUPERVISOR_WAIT_REFUSED;
                        else if (failure == pre)
                            expected = VOS_SUPERVISOR_ACQUIRE_REFUSED;
                        else
                            expected = VOS_SUPERVISOR_START_REFUSED;
                        starts = failure == 0 ? b.count : failure > pre ? failure - pre - 1 : 0;
                        CHECK(status == expected && result.status == expected);
                        CHECK(!b.error && !b.locked && b.acquired == b.released);
                        CHECK(b.started == starts && result.started_count == starts &&
                              result.started_members == b.started_members);
                        CHECK(result.stop_members == (mode ? b.selected : 0) &&
                              result.delay == b.delay);
                        CHECK(result.refused_unit == (expected == VOS_SUPERVISOR_START_REFUSED ?
                              b.units[starts] : VOS_SUPERVISOR_UNITS));
                        CHECK(b.calls == (failure ? failure : pre + b.count));
                        CHECK(trace_ok(&b, mode, starts + (failure > pre),
                                       failure && failure < pre ? failure : pre));
                    }
                }
    /* Every semantic-completion bit pattern, including epoch-only success. */
    for (mask = 0; mask < 64; ++mask) {
        b = fixture(3, 1, 0, 0);
        b.completion_bits = mask;
        ++runs;
        status = vos_supervisor_execute(&b.manifest, 1, 0, &operations, &b, &result);
        if ((mask & 61U) == 61U) {
            CHECK(status == VOS_SUPERVISOR_EXECUTED && b.started == 3);
        } else {
            CHECK(status == VOS_SUPERVISOR_REVOCATION_INCOMPLETE && b.calls == 1 &&
                  b.started == 0 && b.acquired == 0);
        }
        CHECK(!b.error && !b.locked);
    }
    for (mode = 0; mode <= 1; ++mode) {
        b = fixture(3, mode, UINT32_MAX, 0);
        b.stale = 1;
        ++runs;
        CHECK(vos_supervisor_execute(&b.manifest, mode, UINT32_MAX, &operations,
                                     &b, &result) == VOS_SUPERVISOR_SNAPSHOT_REFUSED);
        CHECK(!b.error && !b.locked && b.released == 1 && b.started == 0);
        CHECK(result.started_count == 0 && result.started_members == 0);
    }
    /* Epoch equality keeps all 64 bits; this adapter never increments it. */
    for (i = 0; i < 3; ++i) {
        b = fixture(3, 0, 0, 0);
        b.epoch = i == 2 ? UINT64_MAX : (UINT64_C(1) << 32) + 7;
        b.stale = i == 1 ? UINT64_C(1) << 32 : 0;
        ++runs;
        status = vos_supervisor_execute(&b.manifest, 0, 0, &operations, &b, &result);
        CHECK(status == (i == 1 ? VOS_SUPERVISOR_SNAPSHOT_REFUSED :
                         VOS_SUPERVISOR_EXECUTED));
        CHECK(!b.error && !b.locked && b.released == 1 && b.started == (i == 1 ? 0U : 3U));
    }
    /* A callback cannot rewrite the manifest already admitted for this run. */
    b = fixture(3, 1, 0, 0);
    b.external = &b.manifest;
    b.mutate = 1;
    ++runs;
    CHECK(vos_supervisor_execute(&b.manifest, 1, 0, &operations, &b, &result) ==
          VOS_SUPERVISOR_EXECUTED);
    CHECK(!b.error && b.started == 3);
    /* Preflight checks must run before any destructive effect. */
    for (i = 0; i < 10; ++i) {
        b = fixture(3, 1, 0, 0);
        missing = operations;
        if (i == 0) missing.retire = 0;
        if (i == 1) missing.wait = 0;
        if (i == 2) missing.acquire = 0;
        if (i == 3) missing.start = 0;
        if (i == 4) missing.release = 0;
        if (i == 5) b.manifest.order[0] = VOS_SUPERVISOR_UNITS;
        ++runs;
        CHECK(vos_supervisor_execute(i == 6 ? 0 : &b.manifest, i == 7 ? 2 : 1, 0,
              i == 8 ? 0 : &missing, &b, i == 9 ? 0 : &result) == VOS_SUPERVISOR_INVALID);
        CHECK(b.calls == 0 && b.event_count == 0);
    }
    b = fixture(3, 0, 0, 0);
    missing = operations;
    missing.retire = 0;
    missing.wait = 0;
    ++runs;
    CHECK(vos_supervisor_execute(&b.manifest, 0, 0, &missing, &b, &result) ==
          VOS_SUPERVISOR_EXECUTED);
    CHECK(!b.error && b.started == 3 && b.released == 1);
    fprintf(stderr, "ok %u generated effect executions (%u checks; host bindings only)\n",
            runs, checks);
    return 0;
#undef CHECK
}
