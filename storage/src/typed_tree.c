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

static uint32_t branch_route(const struct vos_typed_node *node,
                             const struct vos_storage_typed_key *key)
{
    uint32_t route = 0u;
    while (route + 1u < node->count && compare(&node->keys[route], key) <= 0) ++route;
    return route;
}

static int decode_block(const struct vos_tree_image *image, uint64_t id,
                        struct vos_typed_node *node)
{
    const size_t size = image->geometry.block_bytes;
    return id < image->geometry.arena_nodes &&
           vos_typed_node_decode(&image->geometry, id, image->generations[(size_t)id],
                                 image->bytes + (size_t)id * size, size, node);
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
    if (walk->remaining == 0u) return 0;
    --walk->remaining;
    struct vos_typed_node node = {0};
    if (!decode_block(image, id, &node)) return 0;
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
    const uint32_t route = branch_route(&node, walk->key);
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

struct typed_update {
    const struct vos_tree_arena *arena;
    struct vos_tree_image input;
    const struct vos_storage_typed_key *key;
    const struct vos_storage_extent *extent;
    uint64_t generation;
    uint64_t next;
};

struct typed_growth {
    uint64_t left, right;
    struct vos_storage_typed_key separator;
    int split;
};

struct typed_draft {
    uint32_t kind, count;
    struct vos_storage_typed_key keys[VOS_NODE_MAX_FAN + 1u];
    union {
        struct vos_storage_extent extents[VOS_NODE_MAX_FAN + 1u];
        uint64_t children[VOS_NODE_MAX_FAN + 1u];
    } values;
};

static int append_node(struct typed_update *update, const struct typed_draft *draft,
                       uint32_t start, uint32_t count, uint64_t *id)
{
    const struct vos_tree_arena *arena = update->arena;
    if (update->next >= arena->geometry.arena_nodes) return 0;
    struct vos_typed_node node = {
        .kind = draft->kind, .count = count, .node_id = update->next,
        .generation = update->generation
    };
    const int leaf = node.kind == VOS_NODE_LEAF;
    const uint32_t keys = leaf ? count : count - 1u;
    memcpy(node.keys, draft->keys + start, keys * sizeof(node.keys[0]));
    if (leaf) {
        memcpy(node.extents, draft->values.extents + start, count * sizeof(node.extents[0]));
    } else {
        memcpy(node.children, draft->values.children + start, count * sizeof(node.children[0]));
    }
    const size_t size = arena->geometry.block_bytes;
    if (!vos_typed_node_encode(&arena->geometry, &node,
                               arena->bytes + (size_t)update->next * size, size)) return 0;
    arena->generations[(size_t)update->next] = update->generation;
    *id = update->next;
    ++update->next;
    return 1;
}

static int append_draft(struct typed_update *update, const struct typed_draft *draft,
                        struct typed_growth *growth)
{
    growth->split = draft->count > update->arena->geometry.fan;
    if (!growth->split) return append_node(update, draft, 0u, draft->count, &growth->left);
    const uint32_t cut = draft->count / 2u;
    growth->separator = draft->keys[draft->kind == VOS_NODE_LEAF ? cut : cut - 1u];
    return append_node(update, draft, 0u, cut, &growth->left) &&
           append_node(update, draft, cut, draft->count - cut, &growth->right);
}

static int update_leaf(struct typed_update *update, const struct vos_typed_node *node,
                       struct typed_growth *growth)
{
    struct typed_draft draft = {.kind = VOS_NODE_LEAF};
    uint32_t at = 0u;
    while (at < node->count && compare(&node->keys[at], update->key) < 0) {
        draft.keys[at] = node->keys[at];
        draft.values.extents[at] = node->extents[at];
        ++at;
    }
    draft.keys[at] = *update->key;
    draft.values.extents[at] = *update->extent;
    const uint32_t replaced = at < node->count && compare(&node->keys[at], update->key) == 0;
    for (uint32_t i = at + replaced, j = at + 1u; i < node->count; ++i, ++j) {
        draft.keys[j] = node->keys[i];
        draft.values.extents[j] = node->extents[i];
    }
    draft.count = node->count + 1u - replaced;
    return append_draft(update, &draft, growth);
}

static int update_branch(struct typed_update *update, const struct vos_typed_node *node,
                         uint32_t route, const struct typed_growth *child,
                         struct typed_growth *growth)
{
    const uint32_t added = child->split ? 1u : 0u;
    struct typed_draft draft = {.kind = VOS_NODE_BRANCH, .count = node->count + added};
    for (uint32_t i = 0u; i + 1u < node->count; ++i)
        draft.keys[i + (i < route ? 0u : added)] = node->keys[i];
    for (uint32_t i = 0u; i < node->count; ++i)
        draft.values.children[i + (i <= route ? 0u : added)] = node->children[i];
    draft.values.children[route] = child->left;
    if (child->split) {
        draft.keys[route] = child->separator;
        draft.values.children[route + 1u] = child->right;
    }
    return append_draft(update, &draft, growth);
}

static int update_node(struct typed_update *update, uint64_t id, uint32_t height,
                       struct typed_growth *growth)
{
    struct vos_typed_node node = {0};
    if (!decode_block(&update->input, id, &node)) return 0;
    if (node.kind == VOS_NODE_LEAF)
        return height == 0u && update_leaf(update, &node, growth);
    if (height == 0u) return 0;
    const uint32_t route = branch_route(&node, update->key);
    struct typed_growth child = {0};
    return update_node(update, node.children[route], height - 1u, &child) &&
           update_branch(update, &node, route, &child, growth);
}

static struct vos_tree_image prefix_image(const struct vos_tree_arena *arena, uint64_t used)
{
    struct vos_tree_image image = {
        .geometry = arena->geometry, .bytes = arena->bytes, .generations = arena->generations,
        .length = (size_t)used * arena->geometry.block_bytes, .generation_count = (size_t)used
    };
    image.geometry.arena_nodes = used;
    return image;
}

int vos_typed_tree_insert(const struct vos_tree_arena *arena,
                           const struct vos_tree_limits *limits,
                           uint64_t root, uint64_t generation,
                           const struct vos_storage_typed_key *key,
                           const struct vos_storage_extent *extent,
                           struct vos_tree_update_result *output)
{
    uint8_t expected[VOS_STORAGE_EXTENT_BYTES];
    if (arena == NULL || limits == NULL || key == NULL || output == NULL ||
        arena->bytes == NULL || arena->generations == NULL ||
        !valid_geometry(&arena->geometry) || arena->used == 0u ||
        arena->used > arena->geometry.arena_nodes ||
        arena->length % arena->geometry.block_bytes != 0u ||
        arena->length / arena->geometry.block_bytes != arena->geometry.arena_nodes ||
        arena->generation_count != arena->geometry.arena_nodes ||
        !vos_storage_extent_encode(extent, expected, sizeof(expected))) return 0;

    struct typed_update update = {
        .arena = arena, .input = prefix_image(arena, arena->used),
        .key = key, .extent = extent, .generation = generation, .next = arena->used
    };
    struct vos_storage_extent checked = {0};
    if (vos_typed_tree_lookup(&update.input, limits, root, key, &checked) == VOS_TREE_REFUSED)
        return 0;
    struct typed_growth growth = {0};
    if (!update_node(&update, root, limits->height, &growth)) return 0;

    struct vos_tree_update_result candidate = {.root = growth.left, .height = limits->height};
    if (growth.split) {
        if (candidate.height >= limits->depth_limit) return 0;
        const struct typed_draft new_root = {
            .kind = VOS_NODE_BRANCH, .count = 2u, .keys = {growth.separator},
            .values.children = {growth.left, growth.right}
        };
        if (!append_node(&update, &new_root, 0u, 2u, &candidate.root)) return 0;
        ++candidate.height;
    }
    candidate.used = update.next;
    const struct vos_tree_image image = prefix_image(arena, candidate.used);
    struct vos_tree_limits candidate_limits = *limits;
    candidate_limits.height = candidate.height;
    uint8_t actual[VOS_STORAGE_EXTENT_BYTES];
    if (vos_typed_tree_lookup(&image, &candidate_limits, candidate.root, key, &checked) != VOS_TREE_FOUND ||
        !vos_storage_extent_encode(&checked, actual, sizeof(actual)) ||
        memcmp(actual, expected, sizeof(actual)) != 0) return 0;
    *output = candidate;
    return 1;
}
