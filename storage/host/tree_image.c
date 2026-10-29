// SPDX-License-Identifier: Apache-2.0
/* Native tree comparison seam; supplied bytes are unauthenticated fixtures. */
#include "vos_tree_image.h"

#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

#define HOST_NODE_LIMIT 64u
#define HOST_BLOCK_LIMIT 4096u

static uint8_t bytes[HOST_NODE_LIMIT * HOST_BLOCK_LIMIT];

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
    struct vos_tree_image image;
    struct vos_tree_limits limits;
    uint64_t arguments[8];
    uint64_t generations[HOST_NODE_LIMIT];
    uint64_t value = UINT64_MAX - 17u;
    uint32_t i;
    int result;
#ifdef _WIN32
    if (_setmode(_fileno(stdin), _O_BINARY) == -1) {
        return 3;
    }
#endif
    if (argc < 9) {
        return 3;
    }
    for (i = 0u; i < 8u; ++i) {
        if (!number(argv[i + 1u], &arguments[i])) {
            return 3;
        }
    }
    if (arguments[0] > UINT32_MAX || arguments[1] > HOST_NODE_LIMIT ||
        arguments[2] > HOST_BLOCK_LIMIT || arguments[4] > UINT32_MAX ||
        arguments[5] > UINT32_MAX || arguments[6] > UINT32_MAX ||
        argc != 9 + (int)arguments[1]) {
        return 3;
    }
    for (i = 0u; i < arguments[1]; ++i) {
        if (!number(argv[i + 9u], &generations[i])) {
            return 3;
        }
    }
    image.geometry.fan = (uint32_t)arguments[0];
    image.geometry.arena_nodes = arguments[1];
    image.geometry.block_bytes = (size_t)arguments[2];
    image.bytes = bytes;
    image.length = fread(bytes, 1u, sizeof bytes, stdin);
    image.generations = generations;
    image.generation_count = (size_t)arguments[1];
    if (ferror(stdin) || (image.length == sizeof bytes && fgetc(stdin) != EOF)) {
        return 3;
    }
    limits.height = (uint32_t)arguments[4];
    limits.depth_limit = (uint32_t)arguments[5];
    limits.visit_limit = (uint32_t)arguments[6];
    result = vos_tree_lookup(&image, &limits, arguments[3], arguments[7], &value);
    if (result == VOS_TREE_REFUSED) {
        return value == UINT64_MAX - 17u ? 2 : 4;
    }
    if (result == VOS_TREE_MISSING && value != UINT64_MAX - 17u) {
        return 4;
    }
    printf("{\"found\":%s,\"value\":%" PRIu64 "}\n",
           result == VOS_TREE_FOUND ? "true" : "false", value);
    return result == VOS_TREE_FOUND || result == VOS_TREE_MISSING ? 0 : 3;
}
