// SPDX-License-Identifier: Apache-2.0
#include "vos_typed_tree.h"

#include <errno.h>
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

int main(int argc, char **argv)
{
    const int path_only = argc > 1 && strcmp(argv[1], "--path") == 0;
    const int offset = 1 + path_only;
    uint64_t words[13] = {0};
    if (argc < offset + 13) return 3;
    for (size_t i = 0u; i < 13u; ++i)
        if (!number(argv[offset + (int)i], &words[i])) return 3;
    const uint64_t count = words[1], size = words[2];
    if (words[0] > UINT32_MAX || words[4] > UINT32_MAX || words[5] > UINT32_MAX ||
        words[6] > UINT32_MAX || count == 0u || count > 4096u || size > 4096u ||
        size == 0u || argc != offset + 13 + (int)count) return 3;
    uint64_t *generations = calloc((size_t)count, sizeof(*generations));
    uint8_t *bytes = calloc((size_t)count, (size_t)size);
    uint8_t *encoded = calloc(1u, (size_t)size);
    if (generations == NULL || bytes == NULL || encoded == NULL) return 3;
    for (size_t i = 0u; i < (size_t)count; ++i)
        if (!number(argv[offset + 13 + (int)i], &generations[i])) return 3;
    const size_t length = (size_t)count * (size_t)size;
    if (fread(bytes, 1u, length, stdin) != length || fgetc(stdin) != EOF) return 3;
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
