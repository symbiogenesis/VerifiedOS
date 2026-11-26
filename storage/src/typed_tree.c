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

static int emit_arena_node(const struct vos_tree_arena *arena, uint64_t *cursor,
                           const struct vos_typed_node *node, uint64_t *id)
{
    const size_t size = arena->geometry.block_bytes;
    if (*cursor >= arena->geometry.arena_nodes ||
        !vos_typed_node_encode(&arena->geometry, node,
                               arena->bytes + (size_t)(*cursor) * size, size))
        return 0;
    arena->generations[(size_t)(*cursor)] = node->generation;
    *id = *cursor;
    ++(*cursor);
    return 1;
}

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
    return emit_arena_node(arena, &update->next, &node, id);
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

static int valid_arena(const struct vos_tree_arena *arena)
{
    return arena != NULL && arena->bytes != NULL && arena->generations != NULL &&
           valid_geometry(&arena->geometry) && arena->used != 0u &&
           arena->used <= arena->geometry.arena_nodes &&
           arena->length % arena->geometry.block_bytes == 0u &&
           arena->length / arena->geometry.block_bytes == arena->geometry.arena_nodes &&
           arena->generation_count == arena->geometry.arena_nodes;
}

int vos_typed_tree_insert(const struct vos_tree_arena *arena,
                           const struct vos_tree_limits *limits,
                           uint64_t root, uint64_t generation,
                           const struct vos_storage_typed_key *key,
                           const struct vos_storage_extent *extent,
                           struct vos_tree_update_result *output)
{
    uint8_t expected[VOS_STORAGE_EXTENT_BYTES];
    if (!valid_arena(arena) || limits == NULL || key == NULL || output == NULL ||
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

struct typed_delete {
    const struct vos_tree_arena *arena;
    struct vos_tree_image prior;
    const struct vos_storage_typed_key *key;
    uint64_t generation;
    uint64_t cursor;
};

static int append_deleted(struct typed_delete *del, struct vos_typed_node *node, uint64_t *id)
{
    node->node_id = del->cursor;
    node->generation = del->generation;
    return emit_arena_node(del->arena, &del->cursor, node, id);
}

static int delete_leaf(struct typed_delete *del, const struct vos_typed_node *node,
                       uint64_t *new_id, int *empty)
{
    struct vos_typed_node out = {.kind = VOS_NODE_LEAF};
    for (uint32_t i = 0u; i < node->count; ++i) {
        if (compare(&node->keys[i], del->key) == 0) continue;
        out.keys[out.count] = node->keys[i];
        out.extents[out.count] = node->extents[i];
        ++out.count;
    }
    if (out.count == 0u) {
        *empty = 1;
        return 1;
    }
    *empty = 0;
    return append_deleted(del, &out, new_id);
}

static int delete_branch(struct typed_delete *del, const struct vos_typed_node *node,
                         uint32_t route, uint64_t child_id, int child_empty,
                         int can_collapse, uint64_t *new_id, uint32_t *out_height, int *empty)
{
    if (!child_empty) {
        struct vos_typed_node out = {.kind = VOS_NODE_BRANCH, .count = node->count};
        for (uint32_t i = 0u; i < node->count; ++i) {
            out.children[i] = (i == route) ? child_id : node->children[i];
            if (i + 1u < node->count) out.keys[i] = node->keys[i];
        }
        *empty = 0;
        return append_deleted(del, &out, new_id);
    }
    if (node->count <= 1u) {
        *empty = 1;
        return 1;
    }
    if (can_collapse && node->count == 2u) {
        *new_id = node->children[1u - route];
        --(*out_height);
        *empty = 0;
        return 1;
    }
    struct vos_typed_node out = {.kind = VOS_NODE_BRANCH, .count = node->count - 1u};
    for (uint32_t i = 0u; i < route; ++i)
        out.children[i] = node->children[i];
    for (uint32_t i = route + 1u; i < node->count; ++i)
        out.children[i - 1u] = node->children[i];
    if (route == 0u) {
        for (uint32_t i = 0u; i + 2u < node->count; ++i)
            out.keys[i] = node->keys[i + 1u];
    } else {
        for (uint32_t i = 0u; i + 1u < route; ++i)
            out.keys[i] = node->keys[i];
        for (uint32_t i = route; i + 1u < node->count; ++i)
            out.keys[i - 1u] = node->keys[i];
    }
    *empty = 0;
    return append_deleted(del, &out, new_id);
}

static int delete_node(struct typed_delete *del, uint64_t id, uint32_t height,
                       int can_collapse, uint64_t *new_id, uint32_t *out_height, int *empty)
{
    struct vos_typed_node node = {0};
    if (!decode_block(&del->prior, id, &node)) return 0;
    if (node.kind == VOS_NODE_LEAF) {
        if (height != 0u) return 0;
        *out_height = 0u;
        return delete_leaf(del, &node, new_id, empty);
    }
    if (height == 0u) return 0;
    const uint32_t route = branch_route(&node, del->key);
    const int collapse_child = can_collapse && node.count == 1u;
    uint64_t child_id = 0u;
    uint32_t child_height = height - 1u;
    int child_empty = 0;
    if (!delete_node(del, node.children[route], height - 1u, collapse_child,
                     &child_id, &child_height, &child_empty))
        return 0;
    if (collapse_child) {
        *new_id = child_id;
        *out_height = child_height;
        *empty = child_empty;
        return 1;
    }
    *out_height = height;
    return delete_branch(del, &node, route, child_id, child_empty,
                         can_collapse, new_id, out_height, empty);
}

int vos_typed_tree_delete(const struct vos_tree_arena *arena,
                           const struct vos_tree_limits *limits,
                           uint64_t root, uint64_t generation,
                           const struct vos_storage_typed_key *key,
                           struct vos_tree_update_result *output)
{
    if (!valid_arena(arena) || limits == NULL || key == NULL || output == NULL) return 0;

    struct typed_delete del = {
        .arena = arena, .prior = prefix_image(arena, arena->used),
        .key = key, .generation = generation, .cursor = arena->used
    };
    struct vos_storage_extent checked = {0};
    if (vos_typed_tree_lookup(&del.prior, limits, root, key, &checked) != VOS_TREE_FOUND)
        return 0;

    struct vos_tree_update_result candidate = {.root = 0u, .height = limits->height};
    int empty = 0;
    if (!delete_node(&del, root, limits->height, 1, &candidate.root, &candidate.height, &empty))
        return 0;
    if (empty) {
        struct vos_typed_node empty_leaf = {.kind = VOS_NODE_LEAF, .count = 0u};
        if (!append_deleted(&del, &empty_leaf, &candidate.root)) return 0;
        candidate.height = 0u;
    } else {
        while (candidate.height > 0u && candidate.root < arena->used) {
            struct vos_typed_node root_node = {0};
            if (!decode_block(&del.prior, candidate.root, &root_node)) return 0;
            if (root_node.kind != VOS_NODE_BRANCH || root_node.count != 1u) break;
            candidate.root = root_node.children[0];
            --candidate.height;
        }
        if (candidate.root < arena->used) {
            struct vos_typed_node promoted = {0};
            if (!decode_block(&del.prior, candidate.root, &promoted) ||
                !append_deleted(&del, &promoted, &candidate.root))
                return 0;
        }
    }
    candidate.used = del.cursor;
    const struct vos_tree_image after = prefix_image(arena, candidate.used);
    struct vos_tree_limits after_limits = *limits;
    after_limits.height = candidate.height;
    if (vos_typed_tree_lookup(&after, &after_limits, candidate.root, key, &checked) != VOS_TREE_MISSING)
        return 0;
    *output = candidate;
    return 1;
}

#define VOS_TYPED_BATCH_MAX_ITEMS (VOS_NODE_MAX_FAN + VOS_TREE_MAX_BATCH + 2u)

struct typed_batch_update {
    const struct vos_tree_arena *arena;
    struct vos_tree_image input;
    uint64_t generation;
    uint64_t append_at;
};

struct typed_batch_nodes {
    uint32_t count;
    uint64_t ids[VOS_TYPED_BATCH_MAX_ITEMS];
    struct vos_storage_typed_key separators[VOS_TYPED_BATCH_MAX_ITEMS];
};

static int publish_typed_batch(struct typed_batch_update *batch, uint32_t kind, uint32_t total,
                               const struct vos_storage_typed_key *keys,
                               const struct vos_storage_extent *extents,
                               const uint64_t *children,
                               struct typed_batch_nodes *out)
{
    const uint32_t fan = batch->arena->geometry.fan;
    if (total == 0u || total > VOS_TYPED_BATCH_MAX_ITEMS) return 0;
    out->count = 0u;
    uint32_t offset = 0u;
    while (offset < total) {
        const uint32_t rem = total - offset;
        uint32_t chunk = fan;
        if (rem <= fan) {
            chunk = rem;
        } else if (rem <= 2u * fan) {
            chunk = rem / 2u;
        }
        struct vos_typed_node node = {
            .kind = kind, .count = chunk, .node_id = batch->append_at,
            .generation = batch->generation
        };
        for (uint32_t i = 0u; i < chunk; ++i) {
            if (kind == VOS_NODE_LEAF) {
                node.keys[i] = keys[offset + i];
                node.extents[i] = extents[offset + i];
            } else {
                node.children[i] = children[offset + i];
                if (i + 1u < chunk) node.keys[i] = keys[offset + i];
            }
        }
        if (out->count > 0u) {
            out->separators[out->count - 1u] =
                keys[kind == VOS_NODE_LEAF ? offset : offset - 1u];
        }
        if (out->count >= VOS_TYPED_BATCH_MAX_ITEMS ||
            !emit_arena_node(batch->arena, &batch->append_at, &node, &out->ids[out->count]))
            return 0;
        ++out->count;
        offset += chunk;
    }
    return 1;
}

static int merge_batch_leaf(struct typed_batch_update *batch, const struct vos_typed_node *node,
                            const struct vos_typed_tree_entry *entries, size_t entry_count,
                            struct typed_batch_nodes *out)
{
    struct vos_storage_typed_key keys[VOS_TYPED_BATCH_MAX_ITEMS];
    struct vos_storage_extent extents[VOS_TYPED_BATCH_MAX_ITEMS];
    uint32_t i = 0u;
    size_t j = 0u;
    uint32_t total = 0u;
    while (i < node->count || j < entry_count) {
        if (total >= VOS_TYPED_BATCH_MAX_ITEMS) return 0;
        const int cmp = (i < node->count && j < entry_count)
            ? compare(&node->keys[i], &entries[j].key)
            : 0;
        if (j >= entry_count || (i < node->count && cmp < 0)) {
            keys[total] = node->keys[i];
            extents[total] = node->extents[i];
            ++i;
        } else if (i >= node->count || cmp > 0) {
            keys[total] = entries[j].key;
            extents[total] = entries[j].extent;
            ++j;
        } else {
            keys[total] = entries[j].key;
            extents[total] = entries[j].extent;
            ++i;
            ++j;
        }
        ++total;
    }
    return publish_typed_batch(batch, VOS_NODE_LEAF, total, keys, extents, NULL, out);
}

static int insert_batch_node(struct typed_batch_update *batch, uint64_t id, uint32_t height,
                             const struct vos_typed_tree_entry *entries, size_t entry_count,
                             struct typed_batch_nodes *out)
{
    struct vos_typed_node node = {0};
    if (!decode_block(&batch->input, id, &node)) return 0;
    if (node.kind == VOS_NODE_LEAF) {
        return height == 0u && merge_batch_leaf(batch, &node, entries, entry_count, out);
    }
    if (height == 0u) return 0;
    struct vos_storage_typed_key keys[VOS_TYPED_BATCH_MAX_ITEMS];
    uint64_t children[VOS_TYPED_BATCH_MAX_ITEMS];
    struct typed_batch_nodes child = {0};
    uint32_t total = 0u;
    size_t at = 0u;
    for (uint32_t i = 0u; i < node.count; ++i) {
        size_t end = at;
        while (end < entry_count &&
               (i + 1u == node.count || compare(&entries[end].key, &node.keys[i]) < 0)) {
            ++end;
        }
        if (end == at) {
            if (total >= VOS_TYPED_BATCH_MAX_ITEMS) return 0;
            children[total] = node.children[i];
            if (i + 1u < node.count) keys[total] = node.keys[i];
            ++total;
        } else {
            if (!insert_batch_node(batch, node.children[i], height - 1u,
                                   entries + at, end - at, &child) ||
                total + child.count > VOS_TYPED_BATCH_MAX_ITEMS)
                return 0;
            for (uint32_t c = 0u; c < child.count; ++c) {
                children[total + c] = child.ids[c];
                if (c + 1u < child.count) keys[total + c] = child.separators[c];
            }
            if (i + 1u < node.count) keys[total + child.count - 1u] = node.keys[i];
            total += child.count;
        }
        at = end;
    }
    return publish_typed_batch(batch, VOS_NODE_BRANCH, total, keys, NULL, children, out);
}

int vos_typed_tree_insert_batch(const struct vos_tree_arena *arena,
                                 const struct vos_tree_limits *limits,
                                 uint64_t root, uint64_t generation,
                                 const struct vos_typed_tree_entry *entries,
                                 size_t entry_count,
                                 struct vos_tree_update_result *output)
{
    uint8_t expected[VOS_STORAGE_EXTENT_BYTES];
    if (!valid_arena(arena) || limits == NULL || output == NULL || entries == NULL ||
        entry_count == 0u || entry_count > VOS_TREE_MAX_BATCH)
        return 0;
    for (size_t i = 0u; i < entry_count; ++i) {
        if (!vos_storage_extent_encode(&entries[i].extent, expected, sizeof(expected))) return 0;
        if (i != 0u && compare(&entries[i - 1u].key, &entries[i].key) >= 0) return 0;
    }

    struct typed_batch_update batch = {
        .arena = arena, .input = prefix_image(arena, arena->used),
        .generation = generation, .append_at = arena->used
    };
    struct vos_storage_extent checked = {0};
    if (vos_typed_tree_lookup(&batch.input, limits, root, &entries[0].key, &checked) ==
        VOS_TREE_REFUSED)
        return 0;

    struct typed_batch_nodes current = {0};
    if (!insert_batch_node(&batch, root, limits->height, entries, entry_count, &current))
        return 0;
    struct vos_tree_update_result candidate = {.root = 0u, .height = limits->height};
    while (current.count > 1u) {
        struct typed_batch_nodes next_level = {0};
        if (candidate.height >= limits->depth_limit ||
            !publish_typed_batch(&batch, VOS_NODE_BRANCH, current.count,
                                 current.separators, NULL, current.ids, &next_level))
            return 0;
        current = next_level;
        ++candidate.height;
    }
    candidate.root = current.ids[0];
    candidate.used = batch.append_at;

    const struct vos_tree_image batch_image = prefix_image(arena, candidate.used);
    struct vos_tree_limits batch_limits = *limits;
    batch_limits.height = candidate.height;
    for (size_t i = 0u; i < entry_count; ++i) {
        const int status = (i == 0u)
            ? vos_typed_tree_lookup(&batch_image, &batch_limits, candidate.root, &entries[i].key, &checked)
            : vos_typed_tree_lookup_path(&batch_image, &batch_limits, candidate.root, &entries[i].key, &checked);
        uint8_t actual[VOS_STORAGE_EXTENT_BYTES];
        if (status != VOS_TREE_FOUND ||
            !vos_storage_extent_encode(&entries[i].extent, expected, sizeof(expected)) ||
            !vos_storage_extent_encode(&checked, actual, sizeof(actual)) ||
            memcmp(actual, expected, sizeof(actual)) != 0)
            return 0;
    }
    *output = candidate;
    return 1;
}

struct typed_compact_builder {
    const struct vos_tree_arena *arena;
    uint64_t generation;
    uint64_t next_id;
    uint32_t max_depth;
    uint32_t top_level;
    struct vos_typed_node levels[VOS_TREE_MAX_DEPTH + 1u];
    struct vos_storage_typed_key min_keys[VOS_TREE_MAX_DEPTH + 1u];
};

static int count_tree_entries(const struct vos_tree_image *image, uint64_t id,
                              uint32_t height, uint32_t *remaining, uint64_t *total)
{
    if (*remaining == 0u) return 0;
    --(*remaining);
    struct vos_typed_node node = {0};
    if (!decode_block(image, id, &node)) return 0;
    if (node.kind == VOS_NODE_LEAF) {
        if (height != 0u) return 0;
        *total += node.count;
        return 1;
    }
    if (height == 0u) return 0;
    for (uint32_t i = 0u; i < node.count; ++i) {
        if (!count_tree_entries(image, node.children[i], height - 1u, remaining, total))
            return 0;
    }
    return 1;
}

static int compact_append(struct typed_compact_builder *builder, struct vos_typed_node *node,
                          uint64_t *id)
{
    node->node_id = builder->next_id;
    node->generation = builder->generation;
    return emit_arena_node(builder->arena, &builder->next_id, node, id);
}

static int compact_push_branch(struct typed_compact_builder *builder, uint32_t level,
                               uint64_t child_id, const struct vos_storage_typed_key *child_min)
{
    if (level > builder->max_depth) return 0;
    if (level > builder->top_level) builder->top_level = level;
    struct vos_typed_node *branch = &builder->levels[level];
    branch->kind = VOS_NODE_BRANCH;
    if (branch->count == builder->arena->geometry.fan) {
        uint64_t branch_id = 0u;
        const struct vos_storage_typed_key branch_min = builder->min_keys[level];
        if (!compact_append(builder, branch, &branch_id)) return 0;
        branch->count = 0u;
        if (!compact_push_branch(builder, level + 1u, branch_id, &branch_min)) return 0;
    }
    if (branch->count == 0u) {
        builder->min_keys[level] = *child_min;
    } else {
        branch->keys[branch->count - 1u] = *child_min;
    }
    branch->children[branch->count] = child_id;
    ++branch->count;
    return 1;
}

static int compact_emit_entry(struct typed_compact_builder *builder,
                              const struct vos_storage_typed_key *key,
                              const struct vos_storage_extent *extent)
{
    struct vos_typed_node *leaf = &builder->levels[0];
    leaf->kind = VOS_NODE_LEAF;
    if (leaf->count == builder->arena->geometry.fan) {
        uint64_t leaf_id = 0u;
        const struct vos_storage_typed_key leaf_min = builder->min_keys[0];
        if (!compact_append(builder, leaf, &leaf_id)) return 0;
        leaf->count = 0u;
        if (!compact_push_branch(builder, 1u, leaf_id, &leaf_min)) return 0;
    }
    if (leaf->count == 0u) builder->min_keys[0] = *key;
    leaf->keys[leaf->count] = *key;
    leaf->extents[leaf->count] = *extent;
    ++leaf->count;
    return 1;
}

static int compact_walk(const struct vos_tree_image *input, uint64_t id, uint32_t height,
                        struct typed_compact_builder *builder)
{
    struct vos_typed_node node = {0};
    if (!decode_block(input, id, &node)) return 0;
    if (node.kind == VOS_NODE_LEAF) {
        if (height != 0u) return 0;
        for (uint32_t i = 0u; i < node.count; ++i) {
            if (!compact_emit_entry(builder, &node.keys[i], &node.extents[i])) return 0;
        }
        return 1;
    }
    if (height == 0u) return 0;
    for (uint32_t i = 0u; i < node.count; ++i) {
        if (!compact_walk(input, node.children[i], height - 1u, builder)) return 0;
    }
    return 1;
}

int vos_typed_tree_compact(const struct vos_tree_arena *arena,
                            const struct vos_tree_limits *limits,
                            uint64_t root, uint64_t generation,
                            struct vos_tree_update_result *output)
{
    if (!valid_arena(arena) || limits == NULL || output == NULL) return 0;

    const struct vos_tree_image prior = prefix_image(arena, arena->used);
    const struct vos_storage_typed_key zero_key = {0};
    struct vos_storage_extent checked = {0};
    if (vos_typed_tree_lookup(&prior, limits, root, &zero_key, &checked) == VOS_TREE_REFUSED)
        return 0;
    uint64_t expected_count = 0u;
    uint32_t prior_remaining = limits->visit_limit;
    if (!count_tree_entries(&prior, root, limits->height, &prior_remaining, &expected_count))
        return 0;

    struct typed_compact_builder builder = {
        .arena = arena,
        .generation = generation,
        .next_id = arena->used,
        .max_depth = limits->depth_limit
    };
    if (!compact_walk(&prior, root, limits->height, &builder)) return 0;

    struct vos_tree_update_result candidate = {0};
    if (builder.top_level == 0u && builder.levels[0].count == 0u) {
        struct vos_typed_node empty_leaf = {.kind = VOS_NODE_LEAF, .count = 0u};
        if (!compact_append(&builder, &empty_leaf, &candidate.root)) return 0;
        candidate.height = 0u;
    } else if (builder.top_level == 0u) {
        builder.levels[0].kind = VOS_NODE_LEAF;
        if (!compact_append(&builder, &builder.levels[0], &candidate.root)) return 0;
        candidate.height = 0u;
    } else {
        if (builder.levels[0].count > 0u) {
            uint64_t leaf_id = 0u;
            const struct vos_storage_typed_key leaf_min = builder.min_keys[0];
            if (!compact_append(&builder, &builder.levels[0], &leaf_id)) return 0;
            builder.levels[0].count = 0u;
            if (!compact_push_branch(&builder, 1u, leaf_id, &leaf_min)) return 0;
        }
        uint32_t level = 1u;
        while (level <= builder.top_level) {
            struct vos_typed_node *branch = &builder.levels[level];
            if (level == builder.top_level) {
                if (branch->count == 1u) {
                    candidate.root = branch->children[0];
                    candidate.height = level - 1u;
                } else {
                    if (!compact_append(&builder, branch, &candidate.root)) return 0;
                    candidate.height = level;
                }
                break;
            }
            if (branch->count > 0u) {
                uint64_t branch_id = 0u;
                const struct vos_storage_typed_key branch_min = builder.min_keys[level];
                if (!compact_append(&builder, branch, &branch_id)) return 0;
                branch->count = 0u;
                if (!compact_push_branch(&builder, level + 1u, branch_id, &branch_min))
                    return 0;
            }
            ++level;
        }
    }
    candidate.used = builder.next_id;

    const struct vos_tree_image compacted = prefix_image(arena, candidate.used);
    struct vos_tree_limits compacted_limits = *limits;
    compacted_limits.height = candidate.height;
    if (vos_typed_tree_lookup(&compacted, &compacted_limits, candidate.root, &zero_key, &checked) ==
        VOS_TREE_REFUSED)
        return 0;
    uint64_t actual_count = 0u;
    uint32_t after_remaining = limits->visit_limit;
    if (!count_tree_entries(&compacted, candidate.root, candidate.height, &after_remaining, &actual_count) ||
        actual_count != expected_count)
        return 0;
    *output = candidate;
    return 1;
}
