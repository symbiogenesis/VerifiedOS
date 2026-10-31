// SPDX-License-Identifier: Apache-2.0
#include "vos_tree_image.h"

struct key_range {
    uint64_t lower;
    uint64_t upper;
    int has_lower;
    int has_upper;
};

struct tree_walk {
    const struct vos_tree_image *image;
    uint64_t key;
    uint64_t value;
    uint32_t remaining;
    int found;
};

static int within(struct key_range range, uint64_t key, int strict_lower)
{
    return (!range.has_lower ||
            (strict_lower ? key > range.lower : key >= range.lower)) &&
           (!range.has_upper || key < range.upper);
}

static int walk_node(struct tree_walk *walk, uint64_t id, uint32_t height,
                     struct key_range range, int selected)
{
    struct vos_node node;
    uint32_t route = 0u;
    struct key_range separators = range;
    const struct vos_tree_image *image = walk->image;
    if (walk->remaining == 0u || id >= image->geometry.arena_nodes) {
        return 0;
    }
    --walk->remaining;
    if (!vos_node_decode(&image->geometry, id, image->generations[(size_t)id],
                         image->bytes + (size_t)id * image->geometry.block_bytes,
                         image->geometry.block_bytes, &node)) {
        return 0;
    }
    if (node.kind == VOS_NODE_LEAF) {
        if (height != 0u) {
            return 0;
        }
        for (uint32_t i = 0u; i < node.count; ++i) {
            if ((i != 0u && node.keys[i - 1u] >= node.keys[i]) ||
                !within(range, node.keys[i], 0)) {
                return 0;
            }
            if (selected && node.keys[i] == walk->key) {
                walk->found = 1;
                walk->value = node.values[i];
            }
        }
        return 1;
    }
    if (height == 0u) {
        return 0;
    }
    for (uint32_t i = 0u; i + 1u < node.count; ++i) {
        if (!within(separators, node.keys[i], 1)) {
            return 0;
        }
        separators.lower = node.keys[i];
        separators.has_lower = 1;
    }
    while (route + 1u < node.count && node.keys[route] <= walk->key) {
        ++route;
    }
    for (uint32_t i = 0u; i < node.count; ++i) {
        struct key_range child = range;
        if (i != 0u) {
            child.lower = node.keys[i - 1u];
            child.has_lower = 1;
        }
        if (i + 1u < node.count) {
            child.upper = node.keys[i];
            child.has_upper = 1;
        }
        if (!walk_node(walk, node.values[i], height - 1u, child,
                       selected && i == route)) {
            return 0;
        }
    }
    return 1;
}

int vos_tree_lookup(const struct vos_tree_image *image,
                    const struct vos_tree_limits *limits,
                    uint64_t root, uint64_t key, uint64_t *output)
{
    struct tree_walk walk;
    struct key_range range = {0};
    if (image == NULL || limits == NULL || output == NULL ||
        image->bytes == NULL || image->generations == NULL ||
        image->geometry.fan < 2u || image->geometry.fan > VOS_NODE_MAX_FAN ||
        image->geometry.block_bytes < VOS_NODE_HEADER_BYTES + 16u * image->geometry.fan ||
        image->geometry.arena_nodes == 0u || root >= image->geometry.arena_nodes ||
        image->length % image->geometry.block_bytes != 0u ||
        image->length / image->geometry.block_bytes != image->geometry.arena_nodes ||
        image->generation_count != image->geometry.arena_nodes ||
        limits->height > limits->depth_limit || limits->depth_limit > VOS_TREE_MAX_DEPTH ||
        limits->visit_limit == 0u || limits->visit_limit > VOS_TREE_MAX_VISITS) {
        return VOS_TREE_REFUSED;
    }
    walk.image = image;
    walk.key = key;
    walk.value = 0u;
    walk.remaining = limits->visit_limit;
    walk.found = 0;
    if (!walk_node(&walk, root, limits->height, range, 1)) {
        return VOS_TREE_REFUSED;
    }
    if (!walk.found) {
        return VOS_TREE_MISSING;
    }
    *output = walk.value;
    return VOS_TREE_FOUND;
}
