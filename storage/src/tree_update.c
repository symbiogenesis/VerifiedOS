// SPDX-License-Identifier: Apache-2.0
#include "vos_tree_update.h"

struct grown {
    uint64_t left;
    uint64_t right;
    uint64_t separator;
    int split;
};

struct update {
    const struct vos_tree_arena *arena;
    struct vos_tree_image input;
    uint64_t next;
    uint64_t generation;
    uint64_t key;
    uint64_t value;
};

static int allocate(struct update *update, struct vos_node *node, uint64_t *id)
{
    const struct vos_tree_arena *arena = update->arena;
    if (update->next >= arena->geometry.arena_nodes) {
        return 0;
    }
    node->node_id = update->next;
    node->generation = update->generation;
    if (!vos_node_encode(&arena->geometry, node,
                         arena->bytes + (size_t)update->next * arena->geometry.block_bytes,
                         arena->geometry.block_bytes)) {
        return 0;
    }
    arena->generations[(size_t)update->next] = update->generation;
    *id = update->next;
    ++update->next;
    return 1;
}

static int publish(struct update *update, uint32_t kind, uint32_t count,
                   const uint64_t *keys, const uint64_t *values, struct grown *result)
{
    struct vos_node left = {0};
    struct vos_node right = {0};
    uint32_t i;
    uint32_t cut;
    left.kind = kind;
    left.count = count;
    result->split = 0;
    if (count <= update->arena->geometry.fan) {
        for (i = 0u; i < count; ++i) {
            left.values[i] = values[i];
            if (kind == VOS_NODE_LEAF || i + 1u < count) {
                left.keys[i] = keys[i];
            }
        }
        return allocate(update, &left, &result->left);
    }
    cut = count / 2u;
    left.count = cut;
    right.kind = kind;
    right.count = count - cut;
    for (i = 0u; i < cut; ++i) {
        left.values[i] = values[i];
        if (kind == VOS_NODE_LEAF || i + 1u < cut) {
            left.keys[i] = keys[i];
        }
    }
    for (i = 0u; i < right.count; ++i) {
        right.values[i] = values[cut + i];
        if (kind == VOS_NODE_LEAF || i + 1u < right.count) {
            right.keys[i] = keys[cut + i];
        }
    }
    result->separator = keys[kind == VOS_NODE_LEAF ? cut : cut - 1u];
    result->split = 1;
    return allocate(update, &left, &result->left) &&
           allocate(update, &right, &result->right);
}

static int insert_node(struct update *update, uint64_t id, uint32_t height,
                       struct grown *result)
{
    struct vos_node node;
    struct grown child;
    uint64_t keys[VOS_NODE_MAX_FAN + 1u];
    uint64_t values[VOS_NODE_MAX_FAN + 1u];
    uint32_t i;
    uint32_t route = 0u;
    uint32_t count;
    const struct vos_tree_image *input = &update->input;
    if (id >= input->geometry.arena_nodes ||
        !vos_node_decode(&input->geometry, id, input->generations[(size_t)id],
                         input->bytes + (size_t)id * input->geometry.block_bytes,
                         input->geometry.block_bytes, &node)) {
        return 0;
    }
    count = node.count;
    if (node.kind == VOS_NODE_LEAF) {
        if (height != 0u) {
            return 0;
        }
        while (route < count && node.keys[route] < update->key) {
            ++route;
        }
        for (i = 0u; i < route; ++i) {
            keys[i] = node.keys[i];
            values[i] = node.values[i];
        }
        keys[route] = update->key;
        values[route] = update->value;
        if (route < count && node.keys[route] == update->key) {
            for (i = route + 1u; i < count; ++i) {
                keys[i] = node.keys[i];
                values[i] = node.values[i];
            }
        } else {
            for (i = route; i < count; ++i) {
                keys[i + 1u] = node.keys[i];
                values[i + 1u] = node.values[i];
            }
            ++count;
        }
        return publish(update, VOS_NODE_LEAF, count, keys, values, result);
    }
    if (height == 0u) {
        return 0;
    }
    while (route + 1u < count && node.keys[route] <= update->key) {
        ++route;
    }
    if (!insert_node(update, node.values[route], height - 1u, &child)) {
        return 0;
    }
    for (i = 0u; i < route; ++i) {
        values[i] = node.values[i];
        keys[i] = node.keys[i];
    }
    values[route] = child.left;
    if (child.split) {
        keys[route] = child.separator;
        values[route + 1u] = child.right;
        for (i = route; i + 1u < count; ++i) {
            keys[i + 1u] = node.keys[i];
            values[i + 2u] = node.values[i + 1u];
        }
        ++count;
    } else {
        for (i = route; i + 1u < count; ++i) {
            keys[i] = node.keys[i];
            values[i + 1u] = node.values[i + 1u];
        }
    }
    return publish(update, VOS_NODE_BRANCH, count, keys, values, result);
}

int vos_tree_insert(const struct vos_tree_arena *arena,
                    const struct vos_tree_limits *limits,
                    uint64_t root, uint64_t generation,
                    uint64_t key, uint64_t value,
                    struct vos_tree_update_result *output)
{
    struct update update;
    struct grown grown;
    struct vos_node new_root = {0};
    struct vos_tree_limits candidate_limits;
    struct vos_tree_image candidate;
    struct vos_tree_update_result accepted;
    uint64_t checked;
    if (arena == NULL || limits == NULL || output == NULL ||
        arena->bytes == NULL || arena->generations == NULL ||
        arena->geometry.fan < 2u || arena->geometry.fan > VOS_NODE_MAX_FAN ||
        arena->geometry.block_bytes < VOS_NODE_HEADER_BYTES + 16u * arena->geometry.fan ||
        arena->used == 0u || arena->used > arena->geometry.arena_nodes ||
        arena->length % arena->geometry.block_bytes != 0u ||
        arena->length / arena->geometry.block_bytes != arena->geometry.arena_nodes ||
        arena->generation_count != arena->geometry.arena_nodes) {
        return 0;
    }
    update.arena = arena;
    update.input.geometry = arena->geometry;
    update.input.geometry.arena_nodes = arena->used;
    update.input.bytes = arena->bytes;
    update.input.length = (size_t)arena->used * arena->geometry.block_bytes;
    update.input.generations = arena->generations;
    update.input.generation_count = (size_t)arena->used;
    /* Full admission precedes any append, including off-route references. */
    if (vos_tree_lookup(&update.input, limits, root, key, &checked) == VOS_TREE_REFUSED) {
        return 0;
    }
    update.next = arena->used;
    update.generation = generation;
    update.key = key;
    update.value = value;
    if (!insert_node(&update, root, limits->height, &grown)) {
        return 0;
    }
    accepted.root = grown.left;
    accepted.height = limits->height;
    if (grown.split) {
        if (accepted.height >= limits->depth_limit) {
            return 0;
        }
        new_root.kind = VOS_NODE_BRANCH;
        new_root.count = 2u;
        new_root.keys[0] = grown.separator;
        new_root.values[0] = grown.left;
        new_root.values[1] = grown.right;
        if (!allocate(&update, &new_root, &accepted.root)) {
            return 0;
        }
        ++accepted.height;
    }
    accepted.used = update.next;
    candidate = update.input;
    candidate.geometry.arena_nodes = accepted.used;
    candidate.length = (size_t)accepted.used * arena->geometry.block_bytes;
    candidate.generation_count = (size_t)accepted.used;
    candidate_limits = *limits;
    candidate_limits.height = accepted.height;
    if (vos_tree_lookup(&candidate, &candidate_limits, accepted.root, key, &checked) !=
        VOS_TREE_FOUND || checked != value) {
        return 0;
    }
    *output = accepted;
    return 1;
}
