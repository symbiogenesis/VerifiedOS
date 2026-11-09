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

#define VOS_TREE_MAX_BATCH 64u

struct vos_tree_entry {
    uint64_t key;
    uint64_t value;
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

/* Apply a strictly key-sorted batch of 1..VOS_TREE_MAX_BATCH insertions or
 * replacements in a single top-down copy-on-write pass (R-10-004). Each
 * modified subtree is visited once and allocated in generation at most once per
 * batch, while untouched subtrees and the retained prefix remain unchanged. */
int vos_tree_insert_batch(const struct vos_tree_arena *arena,
                          const struct vos_tree_limits *limits,
                          uint64_t root, uint64_t generation,
                          const struct vos_tree_entry *entries,
                          size_t entry_count,
                          struct vos_tree_update_result *output);

/* Remove key using Rodeh-style lazy copy-on-write deletion without sibling
 * underflow borrows or merges (R-10-010). Prunes empty subtrees along the
 * root-to-leaf path and collapses single-child branch roots while preserving
 * the retained prefix. */
int vos_tree_delete(const struct vos_tree_arena *arena,
                    const struct vos_tree_limits *limits,
                    uint64_t root, uint64_t generation,
                    uint64_t key,
                    struct vos_tree_update_result *output);

/* Pack all reachable live key/value entries of root into a canonical,
 * history-independent B+ tree in generation by bottom-up sorted chunking
 * (R-10-021). Any two valid trees with the same key/value map and geometry
 * compact to identical node layouts. */
int vos_tree_compact(const struct vos_tree_arena *arena,
                     const struct vos_tree_limits *limits,
                     uint64_t root, uint64_t generation,
                     struct vos_tree_update_result *output);

/* Decide in O(1) from a node's immutable birth generation whether an
 * overwritten or deleted node can be reclaimed immediately (1) or is still
 * referenced by a retained snapshot and must join its deadlist (0) (R-10-010). */
int vos_tree_can_reclaim_node(uint64_t node_generation,
                              uint64_t latest_snapshot_generation,
                              int has_snapshot);

#endif
