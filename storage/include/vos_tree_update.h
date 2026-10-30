// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_TREE_UPDATE_H
#define VOS_TREE_UPDATE_H

#include "vos_tree_image.h"

/* Append-only, caller-authenticated arena. used is the retained allocated
 * prefix; geometry.arena_nodes is the full capacity. All reachable input
 * references must lie inside used, including those outside the update route.
 * Inputs, output and the two backing arrays must be disjoint and stable except
 * for the unused suffix this operation owns. Authentication is a caller duty. */
struct vos_tree_arena {
    struct vos_node_geometry geometry;
    uint8_t *bytes;
    size_t length;
    uint64_t *generations;
    size_t generation_count;
    uint64_t used;
};

struct vos_tree_update_result {
    uint64_t root;
    uint64_t used;
    uint32_t height;
};

/* Return 1 only after complete input and candidate tree admission. Insert or
 * replace one numeric entry using copy-on-write path rebuilding and splits.
 * New nodes use generation; retained prefix bytes/generations never change.
 * Output changes only on success. Refusal may change unused suffix bytes, which
 * remain unreachable and reusable; it does not consume used or publish a root.
 * Success is a candidate, not authenticated or durable publication. */
int vos_tree_insert(const struct vos_tree_arena *arena,
                    const struct vos_tree_limits *limits,
                    uint64_t root, uint64_t generation,
                    uint64_t key, uint64_t value,
                    struct vos_tree_update_result *output);

#endif
