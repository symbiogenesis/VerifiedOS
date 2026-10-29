// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_TREE_IMAGE_H
#define VOS_TREE_IMAGE_H

#include "vos_node_image.h"

#define VOS_TREE_MAX_DEPTH 16u
#define VOS_TREE_MAX_VISITS 4096u
#define VOS_TREE_REFUSED 0
#define VOS_TREE_MISSING 1
#define VOS_TREE_FOUND 2

/* A stable, caller-authenticated arena snapshot. Each block's expected
 * generation is independently bound by the caller's retained root evidence.
 * Pointers and the output must be disjoint and valid for their stated lengths;
 * no input may change during the call. This API performs no authentication. */
struct vos_tree_image {
    struct vos_node_geometry geometry;
    const uint8_t *bytes;
    size_t length;
    const uint64_t *generations;
    size_t generation_count;
};

struct vos_tree_limits {
    /* Leaf height is zero, as in ExecutableIndex.v's at_depth. */
    uint32_t height;
    uint32_t depth_limit;
    /* Counts references visited, including repeated references. */
    uint32_t visit_limit;
};

/* Validate all reachable nodes before returning a found value or a true miss.
 * Output changes only on FOUND; REFUSED and MISSING preserve it. The numeric
 * key order, bounds and exact leaf depth follow well_formed and published in
 * ExecutableIndex.v, with this implementation's explicit work/stack ceilings.
 * Unreachable arena blocks do not enter tree admission. */
int vos_tree_lookup(const struct vos_tree_image *image,
                    const struct vos_tree_limits *limits,
                    uint64_t root, uint64_t key, uint64_t *output);

#endif
