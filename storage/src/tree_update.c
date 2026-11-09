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
    const struct vos_tree_reuse *reuse;
    size_t reused;
};

static int allocate(struct update *update, struct vos_node *node, uint64_t *id)
{
    const struct vos_tree_arena *arena = update->arena;
    const int reused = update->reuse != NULL && update->reused < update->reuse->count;
    const uint64_t next_id = reused ? update->reuse->ids[update->reused] : update->next;
    if (next_id >= arena->geometry.arena_nodes) {
        return 0;
    }
    node->node_id = next_id;
    node->generation = update->generation;
    if (!vos_node_encode(&arena->geometry, node,
                         arena->bytes + (size_t)next_id * arena->geometry.block_bytes,
                         arena->geometry.block_bytes)) {
        return 0;
    }
    arena->generations[(size_t)next_id] = update->generation;
    *id = next_id;
    if (reused) {
        ++update->reused;
    } else {
        ++update->next;
    }
    return 1;
}

static int publish(struct update *update, uint32_t kind, uint32_t count,
                   const uint64_t *keys, const uint64_t *values, struct grown *result)
{
    struct vos_node left = {0};
    struct vos_node right = {0};
    left.kind = kind;
    left.count = count;
    result->split = 0;
    if (count <= update->arena->geometry.fan) {
        for (uint32_t i = 0u; i < count; ++i) {
            left.values[i] = values[i];
            if (kind == VOS_NODE_LEAF || i + 1u < count) {
                left.keys[i] = keys[i];
            }
        }
        return allocate(update, &left, &result->left);
    }
    const uint32_t cut = count / 2u;
    left.count = cut;
    right.kind = kind;
    right.count = count - cut;
    for (uint32_t i = 0u; i < cut; ++i) {
        left.values[i] = values[i];
        if (kind == VOS_NODE_LEAF || i + 1u < cut) {
            left.keys[i] = keys[i];
        }
    }
    for (uint32_t i = 0u; i < right.count; ++i) {
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
    uint32_t route = 0u;
    const struct vos_tree_image *input = &update->input;
    if (id >= input->geometry.arena_nodes ||
        !vos_node_decode(&input->geometry, id, input->generations[(size_t)id],
                         input->bytes + (size_t)id * input->geometry.block_bytes,
                         input->geometry.block_bytes, &node)) {
        return 0;
    }
    uint32_t count = node.count;
    if (update->reuse != NULL && update->reuse->retired != NULL) {
        update->reuse->retired[(size_t)id] = 1u;
    }
    if (node.kind == VOS_NODE_LEAF) {
        if (height != 0u) {
            return 0;
        }
        while (route < count && node.keys[route] < update->key) {
            ++route;
        }
        for (uint32_t i = 0u; i < route; ++i) {
            keys[i] = node.keys[i];
            values[i] = node.values[i];
        }
        keys[route] = update->key;
        values[route] = update->value;
        if (route < count && node.keys[route] == update->key) {
            for (uint32_t i = route + 1u; i < count; ++i) {
                keys[i] = node.keys[i];
                values[i] = node.values[i];
            }
        } else {
            for (uint32_t i = route; i < count; ++i) {
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
    for (uint32_t i = 0u; i < route; ++i) {
        values[i] = node.values[i];
        keys[i] = node.keys[i];
    }
    values[route] = child.left;
    if (child.split) {
        keys[route] = child.separator;
        values[route + 1u] = child.right;
        for (uint32_t i = route; i + 1u < count; ++i) {
            keys[i + 1u] = node.keys[i];
            values[i + 2u] = node.values[i + 1u];
        }
        ++count;
    } else {
        for (uint32_t i = route; i + 1u < count; ++i) {
            keys[i] = node.keys[i];
            values[i + 1u] = node.values[i + 1u];
        }
    }
    return publish(update, VOS_NODE_BRANCH, count, keys, values, result);
}

static int valid_arena_header(const struct vos_tree_arena *arena,
                              const struct vos_tree_limits *limits,
                              const struct vos_tree_update_result *output,
                              struct update *update)
{
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
    update->arena = arena;
    update->input.geometry = arena->geometry;
    update->input.geometry.arena_nodes = arena->used;
    update->input.bytes = arena->bytes;
    update->input.length = (size_t)arena->used * arena->geometry.block_bytes;
    update->input.generations = arena->generations;
    update->input.generation_count = (size_t)arena->used;
    update->next = arena->used;
    return 1;
}

static int valid_arena_and_input(const struct vos_tree_arena *arena,
                                 const struct vos_tree_limits *limits,
                                 uint64_t root,
                                 const struct vos_tree_update_result *output,
                                 struct update *update)
{
    uint64_t checked = 0u;
    if (!valid_arena_header(arena, limits, output, update)) {
        return 0;
    }
    if (vos_tree_lookup(&update->input, limits, root, 0u, &checked) == VOS_TREE_REFUSED) {
        return 0;
    }
    return 1;
}

static int set_reuse(struct update *update, const struct vos_tree_reuse *reuse)
{
    if (reuse == NULL) {
        return 1;
    }
    if ((reuse->count != 0u && reuse->ids == NULL) ||
        (reuse->retired != NULL && reuse->retired_count < update->arena->geometry.arena_nodes)) {
        return 0;
    }
    for (size_t i = 0u; i < reuse->count; ++i) {
        if (reuse->ids[i] >= update->arena->used ||
            (i != 0u && reuse->ids[i - 1u] >= reuse->ids[i])) {
            return 0;
        }
    }
    update->reuse = reuse;
    return 1;
}

static int insert_internal(const struct vos_tree_arena *arena,
                           const struct vos_tree_limits *limits,
                           uint64_t root, uint64_t generation,
                           uint64_t key, uint64_t value,
                           int path_only,
                           const struct vos_tree_reuse *reuse,
                           struct vos_tree_update_result *output)
{
    struct update update = {0};
    struct grown grown;
    struct vos_node new_root = {0};
    struct vos_tree_limits candidate_limits;
    struct vos_tree_image candidate;
    struct vos_tree_update_result accepted;
    uint64_t checked = 0u;
    if (!valid_arena_header(arena, limits, output, &update)) {
        return 0;
    }
    const int pre_status = path_only
        ? vos_tree_lookup_path(&update.input, limits, root, key, &checked)
        : vos_tree_lookup(&update.input, limits, root, key, &checked);
    if (pre_status == VOS_TREE_REFUSED) {
        return 0;
    }
    if (!set_reuse(&update, reuse)) {
        return 0;
    }
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
    const int post_status = path_only
        ? vos_tree_lookup_path(&candidate, &candidate_limits, accepted.root, key, &checked)
        : vos_tree_lookup(&candidate, &candidate_limits, accepted.root, key, &checked);
    if (post_status != VOS_TREE_FOUND || checked != value) {
        return 0;
    }
    *output = accepted;
    return 1;
}

int vos_tree_insert(const struct vos_tree_arena *arena,
                    const struct vos_tree_limits *limits,
                    uint64_t root, uint64_t generation,
                    uint64_t key, uint64_t value,
                    struct vos_tree_update_result *output)
{
    return insert_internal(arena, limits, root, generation, key, value, 0, NULL, output);
}

int vos_tree_insert_path(const struct vos_tree_arena *arena,
                         const struct vos_tree_limits *limits,
                         uint64_t root, uint64_t generation,
                         uint64_t key, uint64_t value,
                         struct vos_tree_update_result *output)
{
    return insert_internal(arena, limits, root, generation, key, value, 1, NULL, output);
}

#define VOS_BATCH_MAX_ITEMS (VOS_NODE_MAX_FAN * (VOS_TREE_MAX_BATCH + 2u))

struct batch_nodes {
    uint32_t count;
    uint64_t ids[VOS_BATCH_MAX_ITEMS];
    uint64_t separators[VOS_BATCH_MAX_ITEMS];
};

static int publish_batch(struct update *update, uint32_t kind, uint32_t total,
                         const uint64_t *keys, const uint64_t *values,
                         struct batch_nodes *out)
{
    const uint32_t fan = update->arena->geometry.fan;
    if (total <= fan + 1u) {
        struct grown grown = {0};
        if (!publish(update, kind, total, keys, values, &grown)) {
            return 0;
        }
        out->ids[0] = grown.left;
        if (grown.split) {
            out->count = 2u;
            out->ids[1] = grown.right;
            out->separators[0] = grown.separator;
        } else {
            out->count = 1u;
        }
        return 1;
    }
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
        struct vos_node node = {0};
        node.kind = kind;
        node.count = chunk;
        for (uint32_t i = 0u; i < chunk; ++i) {
            node.values[i] = values[offset + i];
            if (kind == VOS_NODE_LEAF || i + 1u < chunk) {
                node.keys[i] = keys[offset + i];
            }
        }
        if (out->count > 0u) {
            out->separators[out->count - 1u] =
                keys[kind == VOS_NODE_LEAF ? offset : offset - 1u];
        }
        if (!allocate(update, &node, &out->ids[out->count])) {
            return 0;
        }
        ++out->count;
        offset += chunk;
    }
    return 1;
}

static int insert_batch_node(struct update *update, uint64_t id, uint32_t height,
                             const struct vos_tree_entry *entries, size_t entry_count,
                             struct batch_nodes *out)
{
    struct vos_node node;
    uint64_t keys[VOS_BATCH_MAX_ITEMS];
    uint64_t values[VOS_BATCH_MAX_ITEMS];
    const struct vos_tree_image *input = &update->input;
    if (id >= input->geometry.arena_nodes ||
        !vos_node_decode(&input->geometry, id, input->generations[(size_t)id],
                         input->bytes + (size_t)id * input->geometry.block_bytes,
                         input->geometry.block_bytes, &node)) {
        return 0;
    }
    if (update->reuse != NULL && update->reuse->retired != NULL) {
        update->reuse->retired[(size_t)id] = 1u;
    }
    if (node.kind == VOS_NODE_LEAF) {
        if (height != 0u) {
            return 0;
        }
        uint32_t i = 0u;
        size_t j = 0u;
        uint32_t total = 0u;
        while (i < node.count || j < entry_count) {
            if (total >= VOS_BATCH_MAX_ITEMS) {
                return 0;
            }
            if (j >= entry_count || (i < node.count && node.keys[i] < entries[j].key)) {
                keys[total] = node.keys[i];
                values[total] = node.values[i];
                ++i;
            } else if (i >= node.count || entries[j].key < node.keys[i]) {
                keys[total] = entries[j].key;
                values[total] = entries[j].value;
                ++j;
            } else {
                keys[total] = entries[j].key;
                values[total] = entries[j].value;
                ++i;
                ++j;
            }
            ++total;
        }
        return publish_batch(update, VOS_NODE_LEAF, total, keys, values, out);
    }
    if (height == 0u) {
        return 0;
    }
    uint32_t total = 0u;
    size_t at = 0u;
    for (uint32_t i = 0u; i < node.count; ++i) {
        size_t end = at;
        while (end < entry_count &&
               (i + 1u == node.count || entries[end].key < node.keys[i])) {
            ++end;
        }
        if (end == at) {
            if (total >= VOS_BATCH_MAX_ITEMS) {
                return 0;
            }
            values[total] = node.values[i];
            if (i + 1u < node.count) {
                keys[total] = node.keys[i];
            }
            ++total;
        } else {
            struct batch_nodes child = {0};
            if (!insert_batch_node(update, node.values[i], height - 1u,
                                   entries + at, end - at, &child) ||
                total + child.count > VOS_BATCH_MAX_ITEMS) {
                return 0;
            }
            for (uint32_t c = 0u; c < child.count; ++c) {
                values[total + c] = child.ids[c];
                if (c + 1u < child.count) {
                    keys[total + c] = child.separators[c];
                }
            }
            if (i + 1u < node.count) {
                keys[total + child.count - 1u] = node.keys[i];
            }
            total += child.count;
        }
        at = end;
    }
    return publish_batch(update, VOS_NODE_BRANCH, total, keys, values, out);
}

static int insert_batch_internal(const struct vos_tree_arena *arena,
                                 const struct vos_tree_limits *limits,
                                 uint64_t root, uint64_t generation,
                                 const struct vos_tree_entry *entries,
                                 size_t entry_count,
                                 int path_only,
                                 const struct vos_tree_reuse *reuse,
                                 struct vos_tree_update_result *output)
{
    struct update update = {0};
    struct batch_nodes current = {0};
    struct vos_tree_limits candidate_limits;
    struct vos_tree_image candidate;
    struct vos_tree_update_result accepted;
    uint64_t checked = 0u;
    if (entries == NULL || entry_count == 0u || entry_count > VOS_TREE_MAX_BATCH) {
        return 0;
    }
    for (size_t i = 1u; i < entry_count; ++i) {
        if (entries[i - 1u].key >= entries[i].key) {
            return 0;
        }
    }
    if (path_only) {
        if (!valid_arena_header(arena, limits, output, &update)) {
            return 0;
        }
        for (size_t i = 0u; i < entry_count; ++i) {
            if (vos_tree_lookup_path(&update.input, limits, root,
                                     entries[i].key, &checked) == VOS_TREE_REFUSED) {
                return 0;
            }
        }
    } else if (!valid_arena_and_input(arena, limits, root, output, &update)) {
        return 0;
    }
    if (!set_reuse(&update, reuse)) {
        return 0;
    }
    update.generation = generation;
    if (!insert_batch_node(&update, root, limits->height, entries, entry_count, &current)) {
        return 0;
    }
    accepted.height = limits->height;
    while (current.count > 1u) {
        struct batch_nodes next_level = {0};
        if (accepted.height >= limits->depth_limit ||
            !publish_batch(&update, VOS_NODE_BRANCH, current.count,
                           current.separators, current.ids, &next_level)) {
            return 0;
        }
        current = next_level;
        ++accepted.height;
    }
    accepted.root = current.ids[0];
    accepted.used = update.next;
    candidate = update.input;
    candidate.geometry.arena_nodes = accepted.used;
    candidate.length = (size_t)accepted.used * arena->geometry.block_bytes;
    candidate.generation_count = (size_t)accepted.used;
    candidate_limits = *limits;
    candidate_limits.height = accepted.height;
    for (size_t i = 0u; i < entry_count; ++i) {
        const int status = (!path_only && i == 0u)
            ? vos_tree_lookup(&candidate, &candidate_limits, accepted.root,
                              entries[i].key, &checked)
            : vos_tree_lookup_path(&candidate, &candidate_limits, accepted.root,
                                   entries[i].key, &checked);
        if (status != VOS_TREE_FOUND || checked != entries[i].value) {
            return 0;
        }
    }
    *output = accepted;
    return 1;
}

int vos_tree_insert_batch(const struct vos_tree_arena *arena,
                          const struct vos_tree_limits *limits,
                          uint64_t root, uint64_t generation,
                          const struct vos_tree_entry *entries,
                          size_t entry_count,
                          struct vos_tree_update_result *output)
{
    return insert_batch_internal(arena, limits, root, generation,
                                 entries, entry_count, 0, NULL, output);
}

int vos_tree_insert_batch_path(const struct vos_tree_arena *arena,
                               const struct vos_tree_limits *limits,
                               uint64_t root, uint64_t generation,
                               const struct vos_tree_entry *entries,
                               size_t entry_count,
                               struct vos_tree_update_result *output)
{
    return insert_batch_internal(arena, limits, root, generation,
                                 entries, entry_count, 1, NULL, output);
}

static int delete_node(struct update *update, uint64_t id, uint32_t height,
                       uint64_t *new_id, int *empty)
{
    struct vos_node node;
    struct vos_node out = {0};
    uint32_t route = 0u;
    uint64_t child_id = 0u;
    int child_empty = 0;
    const struct vos_tree_image *input = &update->input;
    if (id >= input->geometry.arena_nodes ||
        !vos_node_decode(&input->geometry, id, input->generations[(size_t)id],
                         input->bytes + (size_t)id * input->geometry.block_bytes,
                         input->geometry.block_bytes, &node)) {
        return 0;
    }
    if (update->reuse != NULL && update->reuse->retired != NULL) {
        update->reuse->retired[(size_t)id] = 1u;
    }
    if (node.kind == VOS_NODE_LEAF) {
        if (height != 0u) {
            return 0;
        }
        out.kind = VOS_NODE_LEAF;
        out.count = 0u;
        for (uint32_t i = 0u; i < node.count; ++i) {
            if (node.keys[i] == update->key) {
                continue;
            }
            out.keys[out.count] = node.keys[i];
            out.values[out.count] = node.values[i];
            ++out.count;
        }
        if (out.count == 0u) {
            *empty = 1;
            return 1;
        }
        *empty = 0;
        return allocate(update, &out, new_id);
    }
    if (height == 0u) {
        return 0;
    }
    while (route + 1u < node.count && node.keys[route] <= update->key) {
        ++route;
    }
    if (!delete_node(update, node.values[route], height - 1u, &child_id, &child_empty)) {
        return 0;
    }
    out.kind = VOS_NODE_BRANCH;
    if (!child_empty) {
        out.count = node.count;
        for (uint32_t i = 0u; i < node.count; ++i) {
            out.values[i] = (i == route) ? child_id : node.values[i];
            if (i + 1u < node.count) {
                out.keys[i] = node.keys[i];
            }
        }
        *empty = 0;
        return allocate(update, &out, new_id);
    }
    if (node.count <= 1u) {
        *empty = 1;
        return 1;
    }
    out.count = node.count - 1u;
    for (uint32_t i = 0u; i < route; ++i) {
        out.values[i] = node.values[i];
    }
    for (uint32_t i = route + 1u; i < node.count; ++i) {
        out.values[i - 1u] = node.values[i];
    }
    if (route == 0u) {
        for (uint32_t i = 1u; i + 1u < node.count; ++i) {
            out.keys[i - 1u] = node.keys[i];
        }
    } else {
        for (uint32_t i = 0u; i + 1u < route; ++i) {
            out.keys[i] = node.keys[i];
        }
        for (uint32_t i = route; i + 1u < node.count; ++i) {
            out.keys[i - 1u] = node.keys[i];
        }
    }
    *empty = 0;
    return allocate(update, &out, new_id);
}

static int delete_internal(const struct vos_tree_arena *arena,
                           const struct vos_tree_limits *limits,
                           uint64_t root, uint64_t generation,
                           uint64_t key, int path_only,
                           const struct vos_tree_reuse *reuse,
                           struct vos_tree_update_result *output)
{
    struct update update = {0};
    struct vos_tree_limits candidate_limits;
    struct vos_tree_image candidate;
    struct vos_tree_update_result accepted;
    uint64_t checked = 0u;
    int empty = 0;
    if (path_only) {
        if (!valid_arena_header(arena, limits, output, &update) ||
            vos_tree_lookup_path(&update.input, limits, root, key, &checked) ==
                VOS_TREE_REFUSED) {
            return 0;
        }
    } else if (!valid_arena_and_input(arena, limits, root, output, &update)) {
        return 0;
    }
    if (!set_reuse(&update, reuse)) {
        return 0;
    }
    update.generation = generation;
    update.key = key;
    if (!delete_node(&update, root, limits->height, &accepted.root, &empty)) {
        return 0;
    }
    accepted.height = limits->height;
    if (empty) {
        struct vos_node empty_leaf = {0};
        empty_leaf.kind = VOS_NODE_LEAF;
        empty_leaf.count = 0u;
        if (!allocate(&update, &empty_leaf, &accepted.root)) {
            return 0;
        }
        accepted.height = 0u;
    } else {
        while (accepted.height > 0u) {
            struct vos_node root_node;
            if (!vos_node_decode(&arena->geometry, accepted.root,
                                 arena->generations[(size_t)accepted.root],
                                 arena->bytes + (size_t)accepted.root * arena->geometry.block_bytes,
                                 arena->geometry.block_bytes, &root_node)) {
                return 0;
            }
            if (root_node.kind != VOS_NODE_BRANCH || root_node.count != 1u) {
                break;
            }
            accepted.root = root_node.values[0];
            --accepted.height;
        }
        if (accepted.root < arena->used &&
            (reuse == NULL || arena->generations[(size_t)accepted.root] != generation)) {
            struct vos_node promoted;
            if (!vos_node_decode(&arena->geometry, accepted.root,
                                 arena->generations[(size_t)accepted.root],
                                 arena->bytes + (size_t)accepted.root * arena->geometry.block_bytes,
                                 arena->geometry.block_bytes, &promoted) ||
                !allocate(&update, &promoted, &accepted.root)) {
                return 0;
            }
        }
    }
    accepted.used = update.next;
    candidate = update.input;
    candidate.geometry.arena_nodes = accepted.used;
    candidate.length = (size_t)accepted.used * arena->geometry.block_bytes;
    candidate.generation_count = (size_t)accepted.used;
    candidate_limits = *limits;
    candidate_limits.height = accepted.height;
    const int post_status = path_only
        ? vos_tree_lookup_path(&candidate, &candidate_limits, accepted.root, key, &checked)
        : vos_tree_lookup(&candidate, &candidate_limits, accepted.root, key, &checked);
    if (post_status != VOS_TREE_MISSING) {
        return 0;
    }
    *output = accepted;
    return 1;
}

int vos_tree_delete(const struct vos_tree_arena *arena,
                    const struct vos_tree_limits *limits,
                    uint64_t root, uint64_t generation,
                    uint64_t key,
                    struct vos_tree_update_result *output)
{
    return delete_internal(arena, limits, root, generation, key, 0, NULL, output);
}

int vos_tree_delete_path(const struct vos_tree_arena *arena,
                         const struct vos_tree_limits *limits,
                         uint64_t root, uint64_t generation,
                         uint64_t key,
                         struct vos_tree_update_result *output)
{
    return delete_internal(arena, limits, root, generation, key, 1, NULL, output);
}

struct compact_builder {
    struct update *update;
    uint32_t max_depth;
    uint32_t top_level;
    struct vos_node levels[VOS_TREE_MAX_DEPTH + 1u];
    uint64_t min_keys[VOS_TREE_MAX_DEPTH + 1u];
};

static int compact_push_branch(struct compact_builder *builder, uint32_t level,
                               uint64_t child_id, uint64_t child_min)
{
    if (level > builder->max_depth) {
        return 0;
    }
    if (level > builder->top_level) {
        builder->top_level = level;
    }
    struct vos_node *branch = &builder->levels[level];
    branch->kind = VOS_NODE_BRANCH;
    if (branch->count == 0u) {
        builder->min_keys[level] = child_min;
    } else {
        branch->keys[branch->count - 1u] = child_min;
    }
    branch->values[branch->count] = child_id;
    ++branch->count;
    if (branch->count == builder->update->arena->geometry.fan) {
        uint64_t branch_id = 0u;
        const uint64_t branch_min = builder->min_keys[level];
        if (!allocate(builder->update, branch, &branch_id)) {
            return 0;
        }
        branch->count = 0u;
        return compact_push_branch(builder, level + 1u, branch_id, branch_min);
    }
    return 1;
}

static int compact_emit_entry(struct compact_builder *builder, uint64_t key, uint64_t value)
{
    struct vos_node *leaf = &builder->levels[0];
    leaf->kind = VOS_NODE_LEAF;
    if (leaf->count == 0u) {
        builder->min_keys[0] = key;
    }
    leaf->keys[leaf->count] = key;
    leaf->values[leaf->count] = value;
    ++leaf->count;
    if (leaf->count == builder->update->arena->geometry.fan) {
        uint64_t leaf_id = 0u;
        const uint64_t leaf_min = builder->min_keys[0];
        if (!allocate(builder->update, leaf, &leaf_id)) {
            return 0;
        }
        leaf->count = 0u;
        return compact_push_branch(builder, 1u, leaf_id, leaf_min);
    }
    return 1;
}

static int compact_walk(const struct vos_tree_image *input, uint64_t id, uint32_t height,
                        struct compact_builder *builder)
{
    struct vos_node node;
    if (id >= input->geometry.arena_nodes ||
        !vos_node_decode(&input->geometry, id, input->generations[(size_t)id],
                         input->bytes + (size_t)id * input->geometry.block_bytes,
                         input->geometry.block_bytes, &node)) {
        return 0;
    }
    if (builder->update->reuse != NULL && builder->update->reuse->retired != NULL) {
        builder->update->reuse->retired[(size_t)id] = 1u;
    }
    if (node.kind == VOS_NODE_LEAF) {
        if (height != 0u) {
            return 0;
        }
        for (uint32_t i = 0u; i < node.count; ++i) {
            if (!compact_emit_entry(builder, node.keys[i], node.values[i])) {
                return 0;
            }
        }
        return 1;
    }
    if (height == 0u) {
        return 0;
    }
    for (uint32_t i = 0u; i < node.count; ++i) {
        if (!compact_walk(input, node.values[i], height - 1u, builder)) {
            return 0;
        }
    }
    return 1;
}

static int compact_internal(const struct vos_tree_arena *source,
                             const struct vos_tree_arena *arena,
                             const struct vos_tree_limits *limits,
                             uint64_t root, uint64_t generation,
                             const struct vos_tree_reuse *reuse,
                             struct vos_tree_update_result *output)
{
    struct update update = {0};
    struct compact_builder builder = {0};
    struct vos_tree_limits candidate_limits;
    struct vos_tree_image candidate;
    struct vos_tree_update_result accepted;
    uint64_t checked = 0u;
    if (!valid_arena_and_input(source, limits, root, output, &update)) {
        return 0;
    }
    if (source->geometry.fan != arena->geometry.fan ||
        source->geometry.block_bytes != arena->geometry.block_bytes ||
        arena->length / arena->geometry.block_bytes != arena->geometry.arena_nodes ||
        arena->generation_count != arena->geometry.arena_nodes ||
        arena->bytes == NULL || arena->generations == NULL ||
        arena->used > arena->geometry.arena_nodes ||
        (reuse != NULL && reuse->retired != NULL &&
         reuse->retired_count < source->geometry.arena_nodes)) {
        return 0;
    }
    update.arena = arena;
    update.next = arena->used;
    if (!set_reuse(&update, reuse)) {
        return 0;
    }
    update.generation = generation;
    builder.update = &update;
    builder.max_depth = limits->depth_limit;
    builder.top_level = 0u;
    if (!compact_walk(&update.input, root, limits->height, &builder)) {
        return 0;
    }
    if (builder.top_level == 0u && builder.levels[0].count == 0u) {
        struct vos_node empty_leaf = {0};
        empty_leaf.kind = VOS_NODE_LEAF;
        empty_leaf.count = 0u;
        if (!allocate(&update, &empty_leaf, &accepted.root)) {
            return 0;
        }
        accepted.height = 0u;
    } else {
        if (builder.levels[0].count > 0u) {
            uint64_t leaf_id = 0u;
            const uint64_t leaf_min = builder.min_keys[0];
            if (!allocate(&update, &builder.levels[0], &leaf_id)) {
                return 0;
            }
            builder.levels[0].count = 0u;
            if (!compact_push_branch(&builder, 1u, leaf_id, leaf_min)) {
                return 0;
            }
        }
        uint32_t level = 1u;
        while (level <= builder.top_level) {
            struct vos_node *branch = &builder.levels[level];
            if (level == builder.top_level && branch->count == 1u) {
                accepted.root = branch->values[0];
                accepted.height = level - 1u;
                break;
            }
            if (branch->count > 0u) {
                uint64_t branch_id = 0u;
                const uint64_t branch_min = builder.min_keys[level];
                if (!allocate(&update, branch, &branch_id)) {
                    return 0;
                }
                branch->count = 0u;
                if (!compact_push_branch(&builder, level + 1u, branch_id, branch_min)) {
                    return 0;
                }
            }
            ++level;
        }
    }
    accepted.used = update.next;
    candidate = update.input;
    candidate.bytes = arena->bytes;
    candidate.generations = arena->generations;
    candidate.geometry.arena_nodes = accepted.used;
    candidate.length = (size_t)accepted.used * arena->geometry.block_bytes;
    candidate.generation_count = (size_t)accepted.used;
    candidate_limits = *limits;
    candidate_limits.height = accepted.height;
    if (vos_tree_lookup(&candidate, &candidate_limits, accepted.root, 0u, &checked) ==
        VOS_TREE_REFUSED) {
        return 0;
    }
    *output = accepted;
    return 1;
}

int vos_tree_compact(const struct vos_tree_arena *arena,
                     const struct vos_tree_limits *limits,
                     uint64_t root, uint64_t generation,
                     struct vos_tree_update_result *output)
{
    return compact_internal(arena, arena, limits, root, generation, NULL, output);
}

int vos_tree_compact_into(const struct vos_tree_arena *source,
                          const struct vos_tree_arena *destination,
                          const struct vos_tree_limits *limits,
                          uint64_t root, uint64_t generation,
                          const struct vos_tree_reuse *reuse,
                          struct vos_tree_update_result *output)
{
    if (source == NULL || destination == NULL || source->bytes == destination->bytes ||
        source->generations == destination->generations) {
        return 0;
    }
    return compact_internal(source, destination, limits, root, generation, reuse, output);
}

int vos_tree_insert_reuse(const struct vos_tree_arena *arena,
                          const struct vos_tree_limits *limits,
                          uint64_t root, uint64_t generation,
                          uint64_t key, uint64_t value,
                          const struct vos_tree_reuse *reuse,
                          struct vos_tree_update_result *output)
{
    return insert_internal(arena, limits, root, generation, key, value, 1, reuse, output);
}

int vos_tree_insert_batch_reuse(const struct vos_tree_arena *arena,
                                const struct vos_tree_limits *limits,
                                uint64_t root, uint64_t generation,
                                const struct vos_tree_entry *entries,
                                size_t entry_count,
                                const struct vos_tree_reuse *reuse,
                                struct vos_tree_update_result *output)
{
    return insert_batch_internal(arena, limits, root, generation,
                                 entries, entry_count, 1, reuse, output);
}

int vos_tree_delete_reuse(const struct vos_tree_arena *arena,
                          const struct vos_tree_limits *limits,
                          uint64_t root, uint64_t generation, uint64_t key,
                          const struct vos_tree_reuse *reuse,
                          struct vos_tree_update_result *output)
{
    return delete_internal(arena, limits, root, generation, key, 1, reuse, output);
}

int vos_tree_can_reclaim_node(uint64_t node_generation,
                              uint64_t latest_snapshot_generation,
                              int has_snapshot)
{
    return !has_snapshot || node_generation > latest_snapshot_generation;
}

struct node_set {
    uint32_t visits;
    uint32_t count;
    uint64_t ids[VOS_TREE_MAX_VISITS];
};

static int collect_reachable(const struct vos_tree_image *image,
                             uint32_t visit_limit,
                             uint64_t id, uint32_t height,
                             struct node_set *set)
{
    struct vos_node node;
    if (set->visits >= visit_limit || set->visits >= VOS_TREE_MAX_VISITS ||
        id >= image->geometry.arena_nodes ||
        !vos_node_decode(&image->geometry, id, image->generations[(size_t)id],
                         image->bytes + (size_t)id * image->geometry.block_bytes,
                         image->geometry.block_bytes, &node)) {
        return 0;
    }
    ++set->visits;
    int seen = 0;
    for (uint32_t i = 0u; i < set->count; ++i) {
        if (set->ids[i] == id) {
            seen = 1;
            break;
        }
    }
    if (!seen) {
        set->ids[set->count] = id;
        ++set->count;
    }
    if (node.kind == VOS_NODE_LEAF) {
        return height == 0u;
    }
    if (height == 0u) {
        return 0;
    }
    for (uint32_t i = 0u; i < node.count; ++i) {
        if (!collect_reachable(image, visit_limit, node.values[i], height - 1u, set)) {
            return 0;
        }
    }
    return 1;
}

int vos_tree_classify_reclaim(const struct vos_tree_arena *arena,
                              const struct vos_tree_limits *old_limits,
                              uint64_t old_root,
                              const struct vos_tree_limits *new_limits,
                              uint64_t new_root,
                              uint64_t latest_snapshot_generation,
                              int has_snapshot,
                              struct vos_tree_reclaim_plan *output)
{
    struct update update = {0};
    struct vos_tree_update_result dummy = {0};
    struct node_set old_set = {0};
    struct node_set new_set = {0};
    uint64_t checked = 0u;
    if (output == NULL || new_limits == NULL ||
        !valid_arena_header(arena, old_limits, &dummy, &update)) {
        return 0;
    }
    if (vos_tree_lookup(&update.input, old_limits, old_root, 0u, &checked) == VOS_TREE_REFUSED ||
        vos_tree_lookup(&update.input, new_limits, new_root, 0u, &checked) == VOS_TREE_REFUSED ||
        !collect_reachable(&update.input, old_limits->visit_limit, old_root,
                           old_limits->height, &old_set) ||
        !collect_reachable(&update.input, new_limits->visit_limit, new_root,
                           new_limits->height, &new_set)) {
        return 0;
    }
    output->reclaimed_count = 0u;
    output->deadlist_count = 0u;
    for (uint32_t i = 0u; i < old_set.count; ++i) {
        const uint64_t id = old_set.ids[i];
        int still_live = 0;
        for (uint32_t j = 0u; j < new_set.count; ++j) {
            if (new_set.ids[j] == id) {
                still_live = 1;
                break;
            }
        }
        if (still_live) {
            continue;
        }
        if (vos_tree_can_reclaim_node(arena->generations[(size_t)id],
                                      latest_snapshot_generation, has_snapshot)) {
            output->reclaimed_ids[output->reclaimed_count] = id;
            ++output->reclaimed_count;
        } else {
            output->deadlist_ids[output->deadlist_count] = id;
            ++output->deadlist_count;
        }
    }
    return 1;
}
