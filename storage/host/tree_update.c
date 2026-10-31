// SPDX-License-Identifier: Apache-2.0
/* Native comparison seam; all supplied arena bytes are unauthenticated. */
#include "vos_tree_update.h"

#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HOST_NODE_LIMIT 2048u
#define HOST_BLOCK_LIMIT 4096u

static uint8_t bytes[HOST_NODE_LIMIT * HOST_BLOCK_LIMIT];
static uint8_t retained[HOST_NODE_LIMIT * HOST_BLOCK_LIMIT];
static uint64_t generations[HOST_NODE_LIMIT];
static uint64_t retained_generations[HOST_NODE_LIMIT];

static int number(const char *text, uint64_t *out)
{
    char *end;
    if (*text < '0' || *text > '9') {
        return 0;
    }
    errno = 0;
    const unsigned long long value = strtoull(text, &end, 10);
    if (errno != 0 || *end != '\0') {
        return 0;
    }
    *out = (uint64_t)value;
    return 1;
}

int main(int argc, char **argv)
{
    struct vos_tree_arena arena;
    struct vos_tree_limits limits;
    struct vos_tree_update_result result = {
        .root = UINT64_MAX, .used = UINT64_MAX, .height = UINT32_MAX,
    };
    uint64_t arguments[12];
    if (argc < 13) {
        return 3;
    }
    for (uint32_t i = 0u; i < 12u; ++i) {
        if (!number(argv[i + 1u], &arguments[i])) {
            return 3;
        }
    }
    if (arguments[0] > UINT32_MAX || arguments[1] > HOST_NODE_LIMIT ||
        arguments[2] > HOST_BLOCK_LIMIT || arguments[3] > arguments[1] ||
        arguments[5] > UINT32_MAX || arguments[6] > UINT32_MAX || arguments[7] > UINT32_MAX ||
        argc != 13 + (int)arguments[1]) {
        return 3;
    }
    for (uint32_t i = 0u; i < arguments[1]; ++i) {
        if (!number(argv[i + 13u], &generations[i])) {
            return 3;
        }
    }
    arena.geometry.fan = (uint32_t)arguments[0];
    arena.geometry.arena_nodes = arguments[1];
    arena.geometry.block_bytes = (size_t)arguments[2];
    arena.bytes = bytes;
    arena.length = fread(bytes, 1u, sizeof bytes, stdin);
    arena.generations = generations;
    arena.generation_count = (size_t)arguments[1];
    arena.used = arguments[3];
    if (ferror(stdin) || (arena.length == sizeof bytes && fgetc(stdin) != EOF)) {
        return 3;
    }
    const size_t retained_length = (size_t)arena.used * arena.geometry.block_bytes;
    memcpy(retained, bytes, arena.length);
    memcpy(retained_generations, generations, sizeof generations);
    limits.height = (uint32_t)arguments[5];
    limits.depth_limit = (uint32_t)arguments[6];
    limits.visit_limit = (uint32_t)arguments[7];
    const int accepted = vos_tree_insert(&arena, &limits, arguments[4], arguments[8],
                               arguments[9], arguments[10], &result);
    if (memcmp(retained, bytes, retained_length) != 0 ||
        memcmp(retained_generations, generations, (size_t)arena.used * sizeof(uint64_t)) != 0) {
        return 4;
    }
    if (!accepted) {
        if (arguments[11] != 0u &&
            (memcmp(retained, bytes, arena.length) != 0 ||
             memcmp(retained_generations, generations, sizeof generations) != 0)) {
            return 4;
        }
        return result.root == UINT64_MAX && result.used == UINT64_MAX &&
               result.height == UINT32_MAX ? 2 : 4;
    }
    printf("{\"root\":%" PRIu64 ",\"used\":%" PRIu64 ",\"height\":%" PRIu32 ",\"generations\":[",
           result.root, result.used, result.height);
    for (uint32_t i = 0u; i < arena.geometry.arena_nodes; ++i) {
        printf("%s%" PRIu64, i == 0u ? "" : ",", generations[i]);
    }
    printf("]}\n");
    return fwrite(bytes, 1u, arena.length, stdout) == arena.length ? 0 : 3;
}
