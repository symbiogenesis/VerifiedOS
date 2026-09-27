// SPDX-License-Identifier: Apache-2.0
#include "vos_copy_service.h"
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static vos_copy_ring ring;
static uint8_t source[VOS_COPY_MAX_PAYLOAD + 1], destination[VOS_COPY_MAX_PAYLOAD + 2];
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "control failed at %d\n", __LINE__); return 1; } } while (0)

#include "fixed_controls.h"

static int controls(void)
{
    int result = vos_copy_controls(&ring, source, destination);
    if (!result) fprintf(stderr, "ok fixed consumer controls: bytes, copy-once, refusals, lifecycle, batch, wrap\n");
    return result;
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
        printf("%u %u %u %u %u %u %u %u\n", vos_copy_occupancy(&view), view.produced,
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
