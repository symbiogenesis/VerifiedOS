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
    struct vos_tree_entry batch[VOS_TREE_MAX_BATCH];
    struct vos_tree_reclaim_plan reclaim_plan = {0};
    uint64_t arguments[12];
    int mode = 0; /* 0=insert, 1=delete, 2=compact, 3=batch, 4=insert-path, 5=delete-path, 6=batch-path */
    if (argc > 1) {
        if (strcmp(argv[1], "--delete") == 0) {
            mode = 1;
            --argc;
            ++argv;
        } else if (strcmp(argv[1], "--compact") == 0) {
            mode = 2;
            --argc;
            ++argv;
        } else if (strcmp(argv[1], "--batch") == 0) {
            mode = 3;
            --argc;
            ++argv;
        } else if (strcmp(argv[1], "--insert-path") == 0) {
            mode = 4;
            --argc;
            ++argv;
        } else if (strcmp(argv[1], "--delete-path") == 0) {
            mode = 5;
            --argc;
            ++argv;
        } else if (strcmp(argv[1], "--batch-path") == 0) {
            mode = 6;
            --argc;
            ++argv;
        }
    }
    const int is_batch = (mode == 3 || mode == 6);
    const int is_path = (mode >= 4);
    const uint32_t header_args = is_batch ? 11u : 12u;
    if (argc < (int)(header_args + 1u)) {
        return 3;
    }
    for (uint32_t i = 0u; i < header_args; ++i) {
        if (!number(argv[i + 1u], &arguments[i])) {
            return 3;
        }
    }
    size_t batch_count = 0u;
    uint64_t untouched_flag = 0u;
    int gen_offset = 13;
    if (is_batch) {
        batch_count = (size_t)arguments[9];
        untouched_flag = arguments[10];
        if (batch_count > VOS_TREE_MAX_BATCH ||
            argc != (int)(12u + 2u * batch_count + arguments[1])) {
            return 3;
        }
        for (size_t i = 0u; i < batch_count; ++i) {
            if (!number(argv[12u + 2u * i], &batch[i].key) ||
                !number(argv[13u + 2u * i], &batch[i].value)) {
                return 3;
            }
        }
        gen_offset = (int)(12u + 2u * batch_count);
    } else {
        untouched_flag = arguments[11];
        if (argc != 13 + (int)arguments[1]) {
            return 3;
        }
    }
    if (arguments[0] > UINT32_MAX || arguments[1] > HOST_NODE_LIMIT ||
        arguments[2] > HOST_BLOCK_LIMIT || arguments[3] > arguments[1] ||
        arguments[5] > UINT32_MAX || arguments[6] > UINT32_MAX || arguments[7] > UINT32_MAX) {
        return 3;
    }
    for (uint32_t i = 0u; i < arguments[1]; ++i) {
        if (!number(argv[(int)i + gen_offset], &generations[i])) {
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
    int accepted = 0;
    if (mode == 0) {
        accepted = vos_tree_insert(&arena, &limits, arguments[4], arguments[8],
                                   arguments[9], arguments[10], &result);
    } else if (mode == 1) {
        accepted = vos_tree_delete(&arena, &limits, arguments[4], arguments[8],
                                   arguments[9], &result);
    } else if (mode == 2) {
        accepted = vos_tree_compact(&arena, &limits, arguments[4], arguments[8], &result);
    } else if (mode == 3) {
        accepted = vos_tree_insert_batch(&arena, &limits, arguments[4], arguments[8],
                                         batch, batch_count, &result);
    } else if (mode == 4) {
        accepted = vos_tree_insert_path(&arena, &limits, arguments[4], arguments[8],
                                        arguments[9], arguments[10], &result);
    } else if (mode == 5) {
        accepted = vos_tree_delete_path(&arena, &limits, arguments[4], arguments[8],
                                        arguments[9], &result);
    } else {
        accepted = vos_tree_insert_batch_path(&arena, &limits, arguments[4], arguments[8],
                                              batch, batch_count, &result);
    }
    if (memcmp(retained, bytes, retained_length) != 0 ||
        memcmp(retained_generations, generations, (size_t)arena.used * sizeof(uint64_t)) != 0) {
        return 4;
    }
    if (!accepted) {
        if (untouched_flag != 0u &&
            (memcmp(retained, bytes, arena.length) != 0 ||
             memcmp(retained_generations, generations, sizeof generations) != 0)) {
            return 4;
        }
        return result.root == UINT64_MAX && result.used == UINT64_MAX &&
               result.height == UINT32_MAX ? 2 : 4;
    }
    const uint64_t snap_gen = is_batch ? 0u : arguments[10];
    const int has_snap = mode == 2 ? (arguments[9] != 0u) : 1;
    const int reclaimable = vos_tree_can_reclaim_node(arguments[8], snap_gen, has_snap);
    if (!is_path) {
        struct vos_tree_arena post_arena = arena;
        struct vos_tree_limits new_limits = limits;
        post_arena.used = result.used;
        new_limits.height = result.height;
        if (!vos_tree_classify_reclaim(&post_arena, &limits, arguments[4],
                                       &new_limits, result.root,
                                       snap_gen, has_snap, &reclaim_plan)) {
            return 4;
        }
        for (uint32_t i = 0u; i < reclaim_plan.reclaimed_count; ++i) {
            const uint64_t id = reclaim_plan.reclaimed_ids[i];
            if (id >= arena.used ||
                !vos_tree_can_reclaim_node(generations[id], snap_gen, has_snap)) {
                return 4;
            }
        }
        for (uint32_t i = 0u; i < reclaim_plan.deadlist_count; ++i) {
            const uint64_t id = reclaim_plan.deadlist_ids[i];
            if (id >= arena.used ||
                vos_tree_can_reclaim_node(generations[id], snap_gen, has_snap)) {
                return 4;
            }
        }
    }
    printf("{\"root\":%" PRIu64 ",\"used\":%" PRIu64 ",\"height\":%" PRIu32
           ",\"reclaimable\":%s,\"reclaimed\":[",
           result.root, result.used, result.height,
           reclaimable ? "true" : "false");
    for (uint32_t i = 0u; i < reclaim_plan.reclaimed_count; ++i) {
        printf("%s%" PRIu64, i == 0u ? "" : ",", reclaim_plan.reclaimed_ids[i]);
    }
    printf("],\"deadlist\":[");
    for (uint32_t i = 0u; i < reclaim_plan.deadlist_count; ++i) {
        printf("%s%" PRIu64, i == 0u ? "" : ",", reclaim_plan.deadlist_ids[i]);
    }
    printf("],\"generations\":[");
    for (uint32_t i = 0u; i < arena.geometry.arena_nodes; ++i) {
        printf("%s%" PRIu64, i == 0u ? "" : ",", generations[i]);
    }
    printf("]}\n");
    return fwrite(bytes, 1u, arena.length, stdout) == arena.length ? 0 : 3;
}
