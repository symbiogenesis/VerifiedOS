// SPDX-License-Identifier: Apache-2.0
#include "vos_node_image.h"

static const uint8_t magic[8] = {'V', 'O', 'S', 'N', 'O', 'D', 'E', '1'};

static int geometry_ok(const struct vos_node_geometry *geometry, size_t length)
{
    return geometry != NULL && geometry->fan >= 2u &&
           geometry->fan <= VOS_NODE_MAX_FAN && geometry->arena_nodes != 0u &&
           geometry->block_bytes == length &&
           length >= VOS_NODE_HEADER_BYTES + 16u * geometry->fan;
}

static int shape_ok(const struct vos_node_geometry *geometry,
                    const struct vos_node *node)
{
    uint32_t i;
    if (node->node_id >= geometry->arena_nodes || node->count > geometry->fan) {
        return 0;
    }
    if (node->kind == VOS_NODE_LEAF) {
        return 1;
    }
    if (node->kind != VOS_NODE_BRANCH || node->count == 0u) {
        return 0;
    }
    for (i = 0u; i < node->count; ++i) {
        if (node->values[i] >= geometry->arena_nodes) {
            return 0;
        }
    }
    return 1;
}

static void put_integer(uint8_t *output, uint64_t value, uint32_t width)
{
    uint32_t i;
    for (i = 0u; i < width; ++i) {
        output[i] = (uint8_t)(value >> (8u * i));
    }
}

static uint64_t get_integer(const uint8_t *bytes, uint32_t width)
{
    uint32_t i;
    uint64_t result = 0u;
    for (i = 0u; i < width; ++i) {
        result |= (uint64_t)bytes[i] << (8u * i);
    }
    return result;
}

int vos_node_encode(const struct vos_node_geometry *geometry,
                    const struct vos_node *node, uint8_t *output, size_t length)
{
    size_t at = VOS_NODE_HEADER_BYTES;
    size_t padding;
    uint32_t i;
    if (!geometry_ok(geometry, length) || node == NULL || output == NULL ||
        !shape_ok(geometry, node)) {
        return 0;
    }
    for (i = 0u; i < 8u; ++i) {
        output[i] = magic[i];
    }
    put_integer(output + 8u, node->kind, 4u);
    put_integer(output + 12u, node->count, 4u);
    put_integer(output + 16u, node->node_id, 8u);
    put_integer(output + 24u, node->generation, 8u);
    if (node->kind == VOS_NODE_LEAF) {
        for (i = 0u; i < node->count; ++i) {
            put_integer(output + at, node->keys[i], 8u);
            put_integer(output + at + 8u, node->values[i], 8u);
            at += 16u;
        }
    } else {
        for (i = 0u; i + 1u < node->count; ++i) {
            put_integer(output + at, node->keys[i], 8u);
            at += 8u;
        }
        for (i = 0u; i < node->count; ++i) {
            put_integer(output + at, node->values[i], 8u);
            at += 8u;
        }
    }
    for (padding = at; padding < length; ++padding) {
        output[padding] = 0u;
    }
    return 1;
}

int vos_node_decode(const struct vos_node_geometry *geometry,
                    uint64_t expected_id, uint64_t expected_generation,
                    const uint8_t *bytes, size_t length, struct vos_node *output)
{
    struct vos_node decoded = {0};
    size_t at = VOS_NODE_HEADER_BYTES;
    size_t padding;
    uint32_t i;
    if (!geometry_ok(geometry, length) || bytes == NULL || output == NULL) {
        return 0;
    }
    for (i = 0u; i < 8u; ++i) {
        if (bytes[i] != magic[i]) {
            return 0;
        }
    }
    decoded.kind = (uint32_t)get_integer(bytes + 8u, 4u);
    decoded.count = (uint32_t)get_integer(bytes + 12u, 4u);
    decoded.node_id = get_integer(bytes + 16u, 8u);
    decoded.generation = get_integer(bytes + 24u, 8u);
    /* Check counts before indexing arrays or calculating a payload offset. */
    if (decoded.node_id != expected_id || decoded.generation != expected_generation ||
        decoded.node_id >= geometry->arena_nodes || decoded.count > geometry->fan ||
        (decoded.kind != VOS_NODE_LEAF && decoded.kind != VOS_NODE_BRANCH) ||
        (decoded.kind == VOS_NODE_BRANCH && decoded.count == 0u)) {
        return 0;
    }
    if (decoded.kind == VOS_NODE_LEAF) {
        for (i = 0u; i < decoded.count; ++i) {
            decoded.keys[i] = get_integer(bytes + at, 8u);
            decoded.values[i] = get_integer(bytes + at + 8u, 8u);
            at += 16u;
        }
    } else {
        for (i = 0u; i + 1u < decoded.count; ++i) {
            decoded.keys[i] = get_integer(bytes + at, 8u);
            at += 8u;
        }
        for (i = 0u; i < decoded.count; ++i) {
            decoded.values[i] = get_integer(bytes + at, 8u);
            at += 8u;
        }
    }
    if (!shape_ok(geometry, &decoded)) {
        return 0;
    }
    for (padding = at; padding < length; ++padding) {
        if (bytes[padding] != 0u) {
            return 0;
        }
    }
    *output = decoded;
    return 1;
}
