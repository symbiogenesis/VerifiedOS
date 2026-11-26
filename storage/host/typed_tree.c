// SPDX-License-Identifier: Apache-2.0
#include "vos_typed_tree.h"

#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int number(const char *text, uint64_t *value)
{
    char *end = NULL;
    errno = 0;
    const unsigned long long parsed = strtoull(text, &end, 10);
    if (errno != 0 || end == text || *end != '\0' || *text == '-') return 0;
    *value = (uint64_t)parsed;
    return 1;
}

enum host_update_mode {
    HOST_MODE_INSERT = 0,
    HOST_MODE_DELETE = 1,
    HOST_MODE_INSERT_BATCH = 2,
    HOST_MODE_COMPACT = 3
};

static int run_update(const struct vos_tree_arena *arena, const struct vos_tree_limits *limits,
                      uint64_t root, uint64_t generation, const struct vos_storage_typed_key *key,
                      enum host_update_mode mode, int invalid_extent)
{
    struct vos_storage_extent extent = {0};
    struct vos_typed_tree_entry entries[VOS_TREE_MAX_BATCH + 2u] = {0};
    size_t batch_count = 0u;
    if (arena->used > arena->geometry.arena_nodes) return 3;
    if (mode == HOST_MODE_INSERT) {
        uint8_t serialized[VOS_STORAGE_EXTENT_BYTES];
        if (fread(serialized, 1u, sizeof(serialized), stdin) != sizeof(serialized) ||
            fgetc(stdin) != EOF ||
            !vos_storage_extent_decode(serialized, sizeof(serialized), &extent)) return 3;
        if (invalid_extent) extent.domain_epoch = VOS_NODE_NONCE_MAX_DOMAIN + 1u;
    } else if (mode == HOST_MODE_INSERT_BATCH) {
        uint8_t hdr[4];
        if (fread(hdr, 1u, sizeof(hdr), stdin) != sizeof(hdr)) return 3;
        batch_count = (size_t)hdr[0] | ((size_t)hdr[1] << 8u) |
            ((size_t)hdr[2] << 16u) | ((size_t)hdr[3] << 24u);
        if (batch_count > VOS_TREE_MAX_BATCH + 2u) return 3;
        for (size_t i = 0u; i < batch_count; ++i) {
            uint8_t record[VOS_STORAGE_TYPED_ENTRY_BYTES];
            if (fread(record, 1u, sizeof(record), stdin) != sizeof(record) ||
                !vos_storage_typed_key_decode(record, VOS_STORAGE_TYPED_KEY_BYTES,
                                              &entries[i].key) ||
                !vos_storage_extent_decode(record + VOS_STORAGE_TYPED_KEY_BYTES,
                                           VOS_STORAGE_EXTENT_BYTES, &entries[i].extent))
                return 3;
        }
        if (fgetc(stdin) != EOF) return 3;
        if (invalid_extent && batch_count > 0u)
            entries[batch_count - 1u].extent.domain_epoch = VOS_NODE_NONCE_MAX_DOMAIN + 1u;
    }
    const size_t generation_bytes = arena->generation_count * sizeof(arena->generations[0]);
    uint8_t *bytes_before = malloc(arena->length);
    uint64_t *generations_before = malloc(generation_bytes);
    if (bytes_before == NULL || generations_before == NULL) {
        free(bytes_before);
        free(generations_before);
        return 3;
    }
    memcpy(bytes_before, arena->bytes, arena->length);
    memcpy(generations_before, arena->generations, generation_bytes);
    struct vos_tree_update_result result;
    memset(&result, 0xa5, sizeof(result));
    uint8_t result_before[sizeof(result)];
    memcpy(result_before, &result, sizeof(result));
    int admitted = 0;
    if (mode == HOST_MODE_INSERT) {
        admitted = vos_typed_tree_insert(arena, limits, root, generation, key, &extent, &result);
    } else if (mode == HOST_MODE_DELETE) {
        admitted = vos_typed_tree_delete(arena, limits, root, generation, key, &result);
    } else if (mode == HOST_MODE_INSERT_BATCH) {
        admitted = vos_typed_tree_insert_batch(arena, limits, root, generation,
                                               entries, batch_count, &result);
    } else {
        admitted = vos_typed_tree_compact(arena, limits, root, generation, &result);
    }
    const size_t prefix = (size_t)arena->used * arena->geometry.block_bytes;
    const int preserved = memcmp(bytes_before, arena->bytes, prefix) == 0 &&
        memcmp(generations_before, arena->generations,
               (size_t)arena->used * sizeof(arena->generations[0])) == 0;
    const int staged = memcmp(bytes_before, arena->bytes, arena->length) != 0 ||
        memcmp(generations_before, arena->generations, generation_bytes) != 0;
    free(bytes_before);
    free(generations_before);
    if (!preserved) return 4;
    if (!admitted) {
        if (memcmp(result_before, &result, sizeof(result)) != 0) return 4;
        printf("%d\n", staged);
        return 2;
    }
    if (result.used <= arena->used || result.used > arena->geometry.arena_nodes) return 4;
    printf("%" PRIu64 " %" PRIu64 " %" PRIu32 "\n", result.root, result.used, result.height);
    for (size_t i = (size_t)arena->used; i < (size_t)result.used; ++i)
        printf("%" PRIu64 " ", arena->generations[i]);
    printf("\n");
    const size_t appended = ((size_t)result.used - (size_t)arena->used) * arena->geometry.block_bytes;
    return fwrite(arena->bytes + prefix, 1u, appended, stdout) == appended ? 0 : 4;
}

int main(int argc, char **argv)
{
    const int path_only = argc > 1 && strcmp(argv[1], "--path") == 0;
    const int invalid_single = argc > 1 && strcmp(argv[1], "--insert-invalid-extent") == 0;
    const int insert = invalid_single || (argc > 1 && strcmp(argv[1], "--insert") == 0);
    const int del = argc > 1 && strcmp(argv[1], "--delete") == 0;
    const int invalid_batch = argc > 1 && strcmp(argv[1], "--insert-batch-invalid-extent") == 0;
    const int insert_batch = invalid_batch || (argc > 1 && strcmp(argv[1], "--insert-batch") == 0);
    const int compact = argc > 1 && strcmp(argv[1], "--compact") == 0;
    const int invalid_extent = invalid_single || invalid_batch;
    const int update = insert || del || insert_batch || compact;
    const int offset = 1 + (path_only || update);
    const int parameters = update ? 15 : 13;
    uint64_t words[15] = {0};
    if (argc < offset + parameters) return 3;
    for (int i = 0; i < parameters; ++i)
        if (!number(argv[offset + i], &words[i])) return 3;
    const uint64_t count = words[1], size = words[2];
    if (words[0] > UINT32_MAX || words[4] > UINT32_MAX || words[5] > UINT32_MAX ||
        words[6] > UINT32_MAX || count == 0u || count > 4096u || size > 4096u ||
        size == 0u || argc != offset + parameters + (int)count) return 3;
    uint64_t *generations = calloc((size_t)count, sizeof(*generations));
    uint8_t *bytes = calloc((size_t)count, (size_t)size);
    uint8_t *encoded = calloc(1u, (size_t)size);
    if (generations == NULL || bytes == NULL || encoded == NULL) return 3;
    for (size_t i = 0u; i < (size_t)count; ++i)
        if (!number(argv[offset + parameters + (int)i], &generations[i])) return 3;
    const size_t length = (size_t)count * (size_t)size;
    if (fread(bytes, 1u, length, stdin) != length ||
        (!(insert || insert_batch) && fgetc(stdin) != EOF)) return 3;
    const struct vos_tree_image image = {
        .geometry = {.fan = (uint32_t)words[0], .arena_nodes = count, .block_bytes = (size_t)size},
        .bytes = bytes, .length = length, .generations = generations, .generation_count = (size_t)count
    };
    const struct vos_tree_limits limits = {
        .height = (uint32_t)words[4], .depth_limit = (uint32_t)words[5], .visit_limit = (uint32_t)words[6]
    };
    const struct vos_storage_typed_key key = {
        .domain = words[7], .space = words[8], .kind = words[9],
        .object = words[10], .attribute = words[11], .version = words[12]
    };
    if (update) {
        const struct vos_tree_arena arena = {
            .geometry = image.geometry, .bytes = bytes, .length = length, .generations = generations,
            .generation_count = (size_t)count, .used = words[13]
        };
        enum host_update_mode mode = HOST_MODE_INSERT;
        if (del) mode = HOST_MODE_DELETE;
        else if (insert_batch) mode = HOST_MODE_INSERT_BATCH;
        else if (compact) mode = HOST_MODE_COMPACT;
        const int result = run_update(&arena, &limits, words[3], words[14], &key, mode, invalid_extent);
        free(generations);
        free(bytes);
        free(encoded);
        return result;
    }
    struct vos_storage_extent output;
    memset(&output, 0xa5, sizeof(output));
    uint8_t before[sizeof(output)];
    memcpy(before, &output, sizeof(before));
    const int result = path_only ?
        vos_typed_tree_lookup_path(&image, &limits, words[3], &key, &output) :
        vos_typed_tree_lookup(&image, &limits, words[3], &key, &output);
    if (result != VOS_TREE_FOUND && memcmp(before, &output, sizeof(before)) != 0) return 4;
    /* Every successfully decoded arena block must re-encode to its independent
     * input bytes, and failed local decodes preserve their output. Unreachable
     * malformed blocks are allowed by the tree predicate. */
    for (size_t i = 0u; i < (size_t)count; ++i) {
        struct vos_typed_node node;
        memset(&node, 0xa5, sizeof(node));
        uint8_t node_before[sizeof(node)];
        memcpy(node_before, &node, sizeof(node));
        const int decoded = vos_typed_node_decode(&image.geometry, i, generations[i],
                                                    bytes + i * (size_t)size, (size_t)size, &node);
        if (decoded) {
            if (!vos_typed_node_encode(&image.geometry, &node, encoded, (size_t)size) ||
                memcmp(encoded, bytes + i * (size_t)size, (size_t)size) != 0) return 4;
            node.kind = 2u;
            memset(encoded, 0xa5, (size_t)size);
            if (vos_typed_node_encode(&image.geometry, &node, encoded, (size_t)size)) return 4;
            for (size_t j = 0u; j < (size_t)size; ++j) if (encoded[j] != 0xa5u) return 4;
        } else if (memcmp(node_before, &node, sizeof(node_before)) != 0) return 4;
    }
    if (result == VOS_TREE_REFUSED) {
        free(generations); free(bytes); free(encoded);
        return 2;
    }
    printf("%d\n", result);
    if (result == VOS_TREE_FOUND) {
        uint8_t extent[VOS_STORAGE_EXTENT_BYTES];
        if (!vos_storage_extent_encode(&output, extent, sizeof(extent)) ||
            fwrite(extent, 1u, sizeof(extent), stdout) != sizeof(extent)) return 4;
    }
    free(generations); free(bytes); free(encoded);
    return 0;
}
