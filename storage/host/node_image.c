// SPDX-License-Identifier: Apache-2.0
/* Native codec comparison seam. Not a target storage service. */
#include "vos_node_image.h"

#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

#define HOST_BLOCK_LIMIT 4096u

static int number(const char *text, uint64_t *out)
{
    char *end;
    unsigned long long value;
    if (*text < '0' || *text > '9') {
        return 0;
    }
    errno = 0;
    value = strtoull(text, &end, 10);
    if (errno != 0 || *end != '\0') {
        return 0;
    }
    *out = (uint64_t)value;
    return 1;
}

int main(int argc, char **argv)
{
    struct vos_node_geometry geometry;
    struct vos_node node;
    struct vos_node prior;
    uint64_t args[7] = {0};
    uint8_t block[HOST_BLOCK_LIMIT];
    uint32_t i;
    int encode;
    size_t length;
#ifdef _WIN32
    if (_setmode(_fileno(stdin), _O_BINARY) == -1 ||
        _setmode(_fileno(stdout), _O_BINARY) == -1) {
        return 3;
    }
#endif
    if (argc < 7 || (strcmp(argv[1], "encode") != 0 && strcmp(argv[1], "decode") != 0)) {
        return 3;
    }
    encode = strcmp(argv[1], "encode") == 0;
    for (i = 0u; i < (encode ? 7u : 5u); ++i) {
        if ((int)(i + 2u) >= argc || !number(argv[i + 2u], &args[i])) {
            return 3;
        }
    }
    if (args[0] > UINT32_MAX || args[2] > HOST_BLOCK_LIMIT) {
        return 3;
    }
    geometry.fan = (uint32_t)args[0];
    geometry.arena_nodes = args[1];
    geometry.block_bytes = (size_t)args[2];
    if (encode) {
        uint32_t keys;
        uint32_t values;
        size_t at;
        uint8_t old[HOST_BLOCK_LIMIT];
        if (args[3] > UINT32_MAX || args[4] > VOS_NODE_MAX_FAN) {
            return 3;
        }
        memset(&node, 0, sizeof node);
        node.kind = (uint32_t)args[3];
        node.count = (uint32_t)args[4];
        node.node_id = args[5];
        node.generation = args[6];
        keys = node.kind == VOS_NODE_BRANCH && node.count != 0u ? node.count - 1u : node.count;
        values = node.count;
        if (argc != 9 + (int)keys + (int)values) {
            return 3;
        }
        for (i = 0u; i < keys + values; ++i) {
            uint64_t value;
            if (!number(argv[9u + i], &value)) {
                return 3;
            }
            if (i < keys) {
                node.keys[i] = value;
            } else {
                node.values[i - keys] = value;
            }
        }
        memset(block, 0xa5, sizeof block);
        memcpy(old, block, sizeof block);
        if (!vos_node_encode(&geometry, &node, block, geometry.block_bytes)) {
            return memcmp(old, block, sizeof block) == 0 ? 2 : 4;
        }
        for (at = geometry.block_bytes; at < sizeof block; ++at) {
            if (block[at] != 0xa5) {
                return 4;
            }
        }
        return fwrite(block, 1u, geometry.block_bytes, stdout) == geometry.block_bytes ? 0 : 3;
    }
    if (argc != 7) {
        return 3;
    }
    length = fread(block, 1u, sizeof block, stdin);
    if (ferror(stdin) || (length == sizeof block && fgetc(stdin) != EOF)) {
        return 3;
    }
    memset(&node, 0xa5, sizeof node);
    memcpy(&prior, &node, sizeof node);
    if (!vos_node_decode(&geometry, args[3], args[4], block, length, &node)) {
        return memcmp(&prior, &node, sizeof node) == 0 ? 2 : 4;
    }
    printf("{\"kind\":%" PRIu32 ",\"count\":%" PRIu32 ",\"id\":%" PRIu64
           ",\"generation\":%" PRIu64 ",\"keys\":[",
           node.kind, node.count, node.node_id, node.generation);
    for (i = 0u; i < VOS_NODE_MAX_FAN; ++i) {
        printf("%s%" PRIu64, i == 0u ? "" : ",", node.keys[i]);
    }
    printf("],\"values\":[");
    for (i = 0u; i < VOS_NODE_MAX_FAN; ++i) {
        printf("%s%" PRIu64, i == 0u ? "" : ",", node.values[i]);
    }
    printf("]}\n");
    return 0;
}
