// SPDX-License-Identifier: Apache-2.0
#include "vos_copy_service.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static vos_copy_ring ring;
static uint8_t source[VOS_COPY_MAX_PAYLOAD + 1], destination[VOS_COPY_MAX_PAYLOAD + 2];
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "control failed at %d\n", __LINE__); return 1; } } while (0)

static int controls(void)
{
    uint32_t i, j, request = 91, signal = 92, results[VOS_COPY_MAX_BATCH + 1];
    size_t length = 93;
    vos_copy_view view = {0, 0};
    vos_copy_slot slot = {VOS_COPY_TERMINAL, 1, 1, 7};
    vos_copy_request batch[VOS_COPY_MAX_BATCH];
    uint32_t signals[VOS_COPY_MAX_BATCH];
    vos_copy_init(&ring);
    CHECK(!vos_copy_take(&ring, destination, sizeof destination, &length, &request));
    CHECK(length == 93 && request == 91);
    for (i = 0; i < VOS_COPY_MAX_PAYLOAD + 1; ++i) source[i] = (uint8_t)(i * 17 + 3);
    memset(destination, 0xa5, sizeof destination);
    CHECK(!vos_copy_stage(destination + 1, VOS_COPY_MAX_PAYLOAD, source, 0, 1));
    CHECK(destination[1] == 0xa5);
    CHECK(!vos_copy_submit(&ring, VOS_COPY_GENERATION, 1, 0, NULL,
                            VOS_COPY_MAX_PAYLOAD + 1, VOS_COPY_MAX_PAYLOAD + 1, &signal));
    CHECK(signal == 92 && atomic_load(&ring.produced) == 0);
    CHECK(!vos_copy_submit(&ring, VOS_COPY_GENERATION + 1, 1, 0, source, 1, 1, &signal));
    CHECK(!vos_copy_submit(&ring, VOS_COPY_GENERATION, 1, VOS_COPY_OPERATION_COUNT,
                            source, 1, 1, &signal));
    CHECK(vos_copy_prepare_sleep(&ring));
    CHECK(vos_copy_submit(&ring, VOS_COPY_GENERATION, 1, 0, source,
                           VOS_COPY_MAX_PAYLOAD, VOS_COPY_MAX_PAYLOAD, &signal));
    CHECK(signal == 1 && atomic_load(&ring.armed) == 0);
    CHECK(!vos_copy_prepare_sleep(&ring));
    CHECK(!vos_copy_submit(&ring, VOS_COPY_GENERATION, 1, 0, source, 1, 1, &signal));
    CHECK(!vos_copy_take(&ring, destination, 0, &length, &request));
    CHECK(length == 93 && request == 91 && destination[1] == 0xa5);
    /* Change the external source after publication: only staged bytes survive. */
    memset(source, 0xff, sizeof source);
    CHECK(vos_copy_take(&ring, destination + 1, VOS_COPY_MAX_PAYLOAD, &length, &request));
    CHECK(length == VOS_COPY_MAX_PAYLOAD && request == 1);
    CHECK(destination[0] == 0xa5 && destination[VOS_COPY_MAX_PAYLOAD + 1] == 0xa5);
    for (i = 0; i < VOS_COPY_MAX_PAYLOAD; ++i)
        CHECK(destination[i + 1] == (uint8_t)(i * 17 + 3));
    /* Every slot, full refusal, exact payload order, and repeated index wrap. */
    for (j = 0; j < 2 * VOS_COPY_INDEX_SPAN / VOS_COPY_CAPACITY + 1; ++j) {
        for (i = 0; i < VOS_COPY_CAPACITY; ++i) {
            source[0] = (uint8_t)i;
            CHECK(vos_copy_submit(&ring, VOS_COPY_GENERATION, i, 0, source, 1, 1, &signal));
        }
        signal = 92;
        CHECK(!vos_copy_submit(&ring, VOS_COPY_GENERATION, VOS_COPY_CAPACITY, 0,
                                NULL, 1, 1, &signal));
        CHECK(signal == 92);
        for (i = 0; i < VOS_COPY_CAPACITY; ++i) {
            CHECK(vos_copy_take(&ring, destination, sizeof destination, &length, &request));
            CHECK(length == 1 && request == i && destination[0] == (uint8_t)i);
        }
    }
    CHECK(!vos_copy_advance(&slot, VOS_COPY_RECLAIM));
    CHECK(slot.state == VOS_COPY_TERMINAL && slot.readers == 1);
    slot.readers = 0;
    CHECK(vos_copy_advance(&slot, VOS_COPY_RECLAIM));
    view.produced = VOS_COPY_CAPACITY - 1;
    CHECK(vos_copy_batch(&view, VOS_COPY_MAX_BATCH, results));
    CHECK(results[0] == 1 && view.produced == VOS_COPY_CAPACITY);
    for (i = 1; i < VOS_COPY_MAX_BATCH; ++i) CHECK(results[i] == 0);
    results[0] = 99;
    CHECK(!vos_copy_batch(&view, VOS_COPY_MAX_BATCH + 1, results));
    CHECK(results[0] == 99 && view.produced == VOS_COPY_CAPACITY);
    view.produced = UINT32_MAX;
    CHECK(!vos_copy_publish(&view) && view.produced == UINT32_MAX);
    view.produced = 0; view.consumed = VOS_COPY_INDEX_SPAN;
    CHECK(!vos_copy_take_index(&view) && view.consumed == VOS_COPY_INDEX_SPAN);
    vos_copy_init(&ring);
    for (i = 0; i < VOS_COPY_CAPACITY - 1; ++i)
        CHECK(vos_copy_submit(&ring, VOS_COPY_GENERATION, i, 0, source, 1, 1, &signal));
    for (i = 0; i < VOS_COPY_MAX_BATCH; ++i) {
        batch[i].generation = VOS_COPY_GENERATION;
        batch[i].request = VOS_COPY_CAPACITY + i;
        batch[i].operation = 0; batch[i].source = source;
        batch[i].extent = 1; batch[i].length = 1;
    }
    results[0] = 99; signals[0] = 99;
    CHECK(!vos_copy_submit_batch(&ring, NULL, VOS_COPY_MAX_BATCH + 1, results, signals));
    CHECK(results[0] == 99 && signals[0] == 99);
    CHECK(vos_copy_submit_batch(&ring, batch, VOS_COPY_MAX_BATCH, results, signals));
    CHECK(results[0] == 1);
    for (i = 1; i < VOS_COPY_MAX_BATCH; ++i) CHECK(results[i] == 0 && signals[i] == 0);
    for (i = 0; i < VOS_COPY_CAPACITY; ++i)
        CHECK(vos_copy_take(&ring, destination, sizeof destination, &length, &request));
    CHECK(request == VOS_COPY_CAPACITY);
    /* A malformed member cannot roll back a prior enqueue or stop later ones. */
    if (VOS_COPY_MAX_BATCH >= 3) {
        batch[1].length = 2;
        CHECK(vos_copy_submit_batch(&ring, batch, 3, results, signals));
        CHECK(results[0] == 1 && results[1] == 0 && results[2] == 1);
        CHECK(vos_copy_take(&ring, destination, sizeof destination, &length, &request));
        CHECK(request == batch[0].request);
        CHECK(vos_copy_take(&ring, destination, sizeof destination, &length, &request));
        CHECK(request == batch[2].request);
    }
    for (i = 0; i < VOS_COPY_OPERATION_COUNT; ++i) {
        uint32_t limit = vos_copy_payload_limits[i];
        CHECK(vos_copy_submit(&ring, VOS_COPY_GENERATION, i, i,
                               limit == 0 ? NULL : source, limit, limit, &signal));
        CHECK(vos_copy_take(&ring, limit == 0 ? NULL : destination, limit, &length, &request));
        CHECK(length == limit && request == i);
        signal = 92;
        CHECK(!vos_copy_submit(&ring, VOS_COPY_GENERATION, i, i, NULL, limit + 1, limit + 1, &signal));
        CHECK(signal == 92);
    }
    /* Force a live request window through the wire origin before checking IDs. */
    vos_copy_init(&ring);
    atomic_store(&ring.produced, VOS_COPY_INDEX_SPAN - 1);
    atomic_store(&ring.consumed, VOS_COPY_INDEX_SPAN - 1);
    CHECK(vos_copy_submit(&ring, VOS_COPY_GENERATION, 7, 0, source, 1, 1, &signal));
    CHECK(!vos_copy_submit(&ring, VOS_COPY_GENERATION, 7, 0, source, 1, 1, &signal));
    CHECK(vos_copy_submit(&ring, VOS_COPY_GENERATION, 8, 0, source, 1, 1, &signal));
    CHECK(!vos_copy_submit(&ring, VOS_COPY_GENERATION, 7, 0, source, 1, 1, &signal));
    CHECK(vos_copy_take(&ring, destination, sizeof destination, &length, &request));
    CHECK(request == 7);
    CHECK(vos_copy_take(&ring, destination, sizeof destination, &length, &request));
    CHECK(request == 8);
    fprintf(stderr, "ok fixed consumer controls: bytes, copy-once, refusals, lifecycle, batch, wrap\n");
    return 0;
}

static int row(uint32_t *a, size_t n)
{
    vos_copy_view view, published, taken;
    uint32_t results[VOS_COPY_MAX_BATCH], i, took;
    if (n == 0) return 1;
    switch (a[0]) {
    case 0:
        if (n != 3 || a[2] > a[1] || a[1] - a[2] > VOS_COPY_CAPACITY) return 1;
        view.produced = a[1] % VOS_COPY_INDEX_SPAN; view.consumed = a[2] % VOS_COPY_INDEX_SPAN;
        published = view; taken = view;
        i = (uint32_t)vos_copy_publish(&published);
        took = (uint32_t)vos_copy_take_index(&taken);
        printf("%u %u %u %u %u %u %u %u\n", vos_copy_occupancy(view), view.produced,
               view.consumed, a[1] % VOS_COPY_CAPACITY, published.produced,
               took, i, taken.consumed);
        return 0;
    case 1:
        if (n != 4 || a[2] > a[1] || a[1] - a[2] > VOS_COPY_CAPACITY
            || a[3] > VOS_COPY_MAX_BATCH) return 1;
        view.produced = a[1] % VOS_COPY_INDEX_SPAN; view.consumed = a[2] % VOS_COPY_INDEX_SPAN;
        if (!vos_copy_batch(&view, a[3], results)) return 1;
        printf("%u", view.produced);
        for (i = 0; i < a[3]; ++i) printf(" %u", results[i]);
        puts(""); return 0;
    case 2: {
        vos_copy_slot slot;
        if (n != 5 || a[1] >= 6 || a[2] >= 6 || a[3] > 2 || a[4] > 1) return 1;
        slot.state = (vos_copy_state)a[2]; slot.readers = a[3]; slot.validated = a[4]; slot.request = 7;
        i = (uint32_t)vos_copy_advance(&slot, (vos_copy_event)a[1]);
        printf("%u\n", i ? (uint32_t)slot.state + 1 : 0); return 0;
    }
    case 3:
        if (n != 3 || a[1] > VOS_COPY_MAX_PAYLOAD || a[2] > VOS_COPY_MAX_PAYLOAD + 1) return 1;
        i = (uint32_t)vos_copy_stage(destination, a[1], source, a[1], a[2]);
        printf("%u\n", i ? a[2] + 1 : 0); return 0;
    case 4: {
        vos_copy_world world;
        if (n != 10 || a[1] > 1 || a[2] > VOS_COPY_MAX_BATCH || a[4] > a[3]
            || a[3] - a[4] > VOS_COPY_CAPACITY || a[5] > 1 || a[7] > 1 || a[8] > 4
            || a[9] > 2) return 1;
        world.view.produced = a[3] % VOS_COPY_INDEX_SPAN;
        world.view.consumed = a[4] % VOS_COPY_INDEX_SPAN;
        world.armed = a[5]; world.seen = a[6] % VOS_COPY_INDEX_SPAN;
        world.asleep = a[7]; world.signals = a[9]; world.drained = 0;
        vos_copy_activation(&world, (vos_copy_reset)a[1], a[2], a[8]);
        printf("%u %u %u %u %u %u %u\n", world.view.produced, world.view.consumed,
               world.armed, world.signals, world.seen, world.drained, world.asleep);
        return 0;
    }
    default: return 1;
    }
}

int main(int argc, char **argv)
{
    char line[256];
    if (argc == 2 && strcmp(argv[1], "controls") == 0) return controls();
    if (argc != 1) return 1;
    while (fgets(line, sizeof line, stdin)) {
        char *p = line, *end;
        uint32_t values[12];
        size_t n = 0;
        if (strchr(line, '\n') == NULL) return 1;
        while (*p) {
            unsigned long value;
            if (*p == ' ' || *p == '\n' || *p == '\r') { ++p; continue; }
            if (*p < '0' || *p > '9' || n == 12) return 1;
            errno = 0; value = strtoul(p, &end, 10);
            if (errno || value > UINT32_MAX || p == end) return 1;
            values[n++] = (uint32_t)value; p = end;
        }
        if (row(values, n)) return 1;
    }
    return ferror(stdin) ? 1 : 0;
}
