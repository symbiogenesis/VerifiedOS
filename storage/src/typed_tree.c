// SPDX-License-Identifier: Apache-2.0
#include "vos_typed_tree.h"

#include <string.h>

static void put_le(uint8_t *out, uint64_t value, size_t width)
{
    for (size_t i = 0u; i < width; ++i)
        out[i] = (uint8_t)(value >> (8u * i));
}

static uint64_t get_le(const uint8_t *bytes, size_t width)
{
    uint64_t value = 0u;
    for (size_t i = 0u; i < width; ++i)
        value |= (uint64_t)bytes[i] << (8u * i);
    return value;
}

static int valid_geometry(const struct vos_node_geometry *geometry)
{
    return geometry != NULL && geometry->fan >= 2u &&
           geometry->fan <= VOS_NODE_MAX_FAN && geometry->arena_nodes != 0u &&
           geometry->block_bytes >= VOS_NODE_HEADER_BYTES +
               (size_t)geometry->fan * VOS_STORAGE_TYPED_ENTRY_BYTES;
}

static int valid_node(const struct vos_node_geometry *geometry,
                       const struct vos_typed_node *node)
{
    if (!valid_geometry(geometry) || node == NULL ||
        node->node_id >= geometry->arena_nodes || node->count > geometry->fan ||
        (node->kind != VOS_NODE_LEAF && node->kind != VOS_NODE_BRANCH) ||
        (node->kind == VOS_NODE_BRANCH && node->count == 0u)) return 0;
    uint8_t extent[VOS_STORAGE_EXTENT_BYTES];
    for (uint32_t i = 0u; i < node->count; ++i) {
        if (node->kind == VOS_NODE_LEAF) {
            if (!vos_storage_extent_encode(&node->extents[i], extent, sizeof(extent))) return 0;
        } else if (node->children[i] >= geometry->arena_nodes) return 0;
    }
    return 1;
}

int vos_typed_node_encode(const struct vos_node_geometry *geometry,
                           const struct vos_typed_node *node,
                           uint8_t *output, size_t length)
{
    if (output == NULL || !valid_node(geometry, node) || length != geometry->block_bytes)
        return 0;
    memset(output, 0, length);
    memcpy(output, "VOSTYP01", 8u);
    put_le(output + 8u, node->kind, 4u);
    put_le(output + 12u, node->count, 4u);
    put_le(output + 16u, node->node_id, 8u);
    put_le(output + 24u, node->generation, 8u);
    size_t at = VOS_NODE_HEADER_BYTES;
    if (node->kind == VOS_NODE_LEAF) {
        for (uint32_t i = 0u; i < node->count; ++i) {
            (void)vos_storage_typed_key_encode(&node->keys[i], output + at,
                                               VOS_STORAGE_TYPED_KEY_BYTES);
            at += VOS_STORAGE_TYPED_KEY_BYTES;
            (void)vos_storage_extent_encode(&node->extents[i], output + at,
                                            VOS_STORAGE_EXTENT_BYTES);
            at += VOS_STORAGE_EXTENT_BYTES;
        }
    } else {
        for (uint32_t i = 0u; i + 1u < node->count; ++i) {
            (void)vos_storage_typed_key_encode(&node->keys[i], output + at,
                                               VOS_STORAGE_TYPED_KEY_BYTES);
            at += VOS_STORAGE_TYPED_KEY_BYTES;
        }
        for (uint32_t i = 0u; i < node->count; ++i) {
            put_le(output + at, node->children[i], 8u);
            at += 8u;
        }
    }
    return 1;
}

int vos_typed_node_decode(const struct vos_node_geometry *geometry,
                           uint64_t expected_id, uint64_t expected_generation,
                           const uint8_t *bytes, size_t length,
                           struct vos_typed_node *output)
{
    if (!valid_geometry(geometry) || bytes == NULL || output == NULL ||
        length != geometry->block_bytes || memcmp(bytes, "VOSTYP01", 8u) != 0)
        return 0;
    struct vos_typed_node node = {
        .kind = (uint32_t)get_le(bytes + 8u, 4u),
        .count = (uint32_t)get_le(bytes + 12u, 4u),
        .node_id = get_le(bytes + 16u, 8u),
        .generation = get_le(bytes + 24u, 8u)
    };
    if (node.node_id != expected_id || node.generation != expected_generation ||
        node.node_id >= geometry->arena_nodes || node.count > geometry->fan ||
        (node.kind != VOS_NODE_LEAF && node.kind != VOS_NODE_BRANCH) ||
        (node.kind == VOS_NODE_BRANCH && node.count == 0u)) return 0;
    size_t at = VOS_NODE_HEADER_BYTES;
    if (node.kind == VOS_NODE_LEAF) {
        for (uint32_t i = 0u; i < node.count; ++i) {
            if (!vos_storage_typed_key_decode(bytes + at, VOS_STORAGE_TYPED_KEY_BYTES,
                                               &node.keys[i])) return 0;
            at += VOS_STORAGE_TYPED_KEY_BYTES;
            if (!vos_storage_extent_decode(bytes + at, VOS_STORAGE_EXTENT_BYTES,
                                            &node.extents[i])) return 0;
            at += VOS_STORAGE_EXTENT_BYTES;
        }
    } else {
        for (uint32_t i = 0u; i + 1u < node.count; ++i) {
            if (!vos_storage_typed_key_decode(bytes + at, VOS_STORAGE_TYPED_KEY_BYTES,
                                               &node.keys[i])) return 0;
            at += VOS_STORAGE_TYPED_KEY_BYTES;
        }
        for (uint32_t i = 0u; i < node.count; ++i) {
            node.children[i] = get_le(bytes + at, 8u);
            if (node.children[i] >= geometry->arena_nodes) return 0;
            at += 8u;
        }
    }
    for (; at < length; ++at) if (bytes[at] != 0u) return 0;
    *output = node;
    return 1;
}

static int compare(const struct vos_storage_typed_key *a,
                     const struct vos_storage_typed_key *b)
{
    const uint64_t left[] = {a->domain, a->space, a->kind, a->object, a->attribute, a->version};
    const uint64_t right[] = {b->domain, b->space, b->kind, b->object, b->attribute, b->version};
    for (size_t i = 0u; i < 6u; ++i) {
        if (left[i] < right[i]) return -1;
        if (left[i] > right[i]) return 1;
    }
    return 0;
}

struct typed_range {
    struct vos_storage_typed_key lower, upper;
    int has_lower, has_upper;
};

struct typed_walk {
    const struct vos_tree_image *image;
    const struct vos_storage_typed_key *key;
    struct vos_storage_extent extent;
    uint32_t remaining;
    int path_only, found;
};

static int within(struct typed_range range, const struct vos_storage_typed_key *key,
                    int strict_lower)
{
    return (!range.has_lower || compare(key, &range.lower) >= strict_lower) &&
           (!range.has_upper || compare(key, &range.upper) < 0);
}

static int walk_node(struct typed_walk *walk, uint64_t id, uint32_t height,
                       struct typed_range range, int selected)
{
    const struct vos_tree_image *image = walk->image;
    if (walk->remaining == 0u || id >= image->geometry.arena_nodes) return 0;
    --walk->remaining;
    struct vos_typed_node node = {0};
    if (!vos_typed_node_decode(&image->geometry, id, image->generations[(size_t)id],
                                image->bytes + (size_t)id * image->geometry.block_bytes,
                                image->geometry.block_bytes, &node)) return 0;
    if (node.kind == VOS_NODE_LEAF) {
        if (height != 0u) return 0;
        for (uint32_t i = 0u; i < node.count; ++i) {
            if ((i != 0u && compare(&node.keys[i - 1u], &node.keys[i]) >= 0) ||
                !within(range, &node.keys[i], 0)) return 0;
            if (selected && compare(&node.keys[i], walk->key) == 0) {
                walk->found = 1;
                walk->extent = node.extents[i];
            }
        }
        return 1;
    }
    if (height == 0u) return 0;
    struct typed_range separators = range;
    for (uint32_t i = 0u; i + 1u < node.count; ++i) {
        if (!within(separators, &node.keys[i], 1)) return 0;
        separators.lower = node.keys[i];
        separators.has_lower = 1;
    }
    uint32_t route = 0u;
    while (route + 1u < node.count && compare(&node.keys[route], walk->key) <= 0) ++route;
    for (uint32_t i = 0u; i < node.count; ++i) {
        if (walk->path_only && i != route) continue;
        struct typed_range child = range;
        if (i != 0u) { child.lower = node.keys[i - 1u]; child.has_lower = 1; }
        if (i + 1u < node.count) { child.upper = node.keys[i]; child.has_upper = 1; }
        if (!walk_node(walk, node.children[i], height - 1u, child, selected && i == route))
            return 0;
    }
    return 1;
}

static int lookup(const struct vos_tree_image *image, const struct vos_tree_limits *limits,
                    uint64_t root, const struct vos_storage_typed_key *key, int path_only,
                    struct vos_storage_extent *output)
{
    if (image == NULL || limits == NULL || key == NULL || output == NULL ||
        image->bytes == NULL || image->generations == NULL ||
        !valid_geometry(&image->geometry) || root >= image->geometry.arena_nodes ||
        image->length % image->geometry.block_bytes != 0u ||
        image->length / image->geometry.block_bytes != image->geometry.arena_nodes ||
        image->generation_count != image->geometry.arena_nodes ||
        limits->height > limits->depth_limit || limits->depth_limit > VOS_TREE_MAX_DEPTH ||
        limits->visit_limit == 0u || limits->visit_limit > VOS_TREE_MAX_VISITS)
        return VOS_TREE_REFUSED;
    struct typed_walk walk = {
        .image = image, .key = key, .remaining = limits->visit_limit, .path_only = path_only
    };
    const struct typed_range range = {0};
    if (!walk_node(&walk, root, limits->height, range, 1)) return VOS_TREE_REFUSED;
    if (!walk.found) return VOS_TREE_MISSING;
    *output = walk.extent;
    return VOS_TREE_FOUND;
}

int vos_typed_tree_lookup(const struct vos_tree_image *image,
                           const struct vos_tree_limits *limits,
                           uint64_t root, const struct vos_storage_typed_key *key,
                           struct vos_storage_extent *output)
{
    return lookup(image, limits, root, key, 0, output);
}

int vos_typed_tree_lookup_path(const struct vos_tree_image *image,
                                const struct vos_tree_limits *limits,
                                uint64_t root, const struct vos_storage_typed_key *key,
                                struct vos_storage_extent *output)
{
    return lookup(image, limits, root, key, 1, output);
}
