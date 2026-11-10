// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_TYPED_TREE_H
#define VOS_TYPED_TREE_H

#include "vos_tree_image.h"
#include "vos_typed_entry.h"

/* [Format and routing acceptance](../typed-entry.md#typed-node-and-routing-contract). */
struct vos_typed_node {
    uint32_t kind;
    uint32_t count;
    uint64_t node_id;
    uint64_t generation;
    struct vos_storage_typed_key keys[VOS_NODE_MAX_FAN];
    struct vos_storage_extent extents[VOS_NODE_MAX_FAN];
    uint64_t children[VOS_NODE_MAX_FAN];
};

int vos_typed_node_encode(const struct vos_node_geometry *geometry,
                           const struct vos_typed_node *node,
                           uint8_t *output, size_t length);
int vos_typed_node_decode(const struct vos_node_geometry *geometry,
                           uint64_t expected_id, uint64_t expected_generation,
                           const uint8_t *bytes, size_t length,
                           struct vos_typed_node *output);

/* The arena and generations are stable and independently authenticated by the
 * caller. These readers establish structural admission, not authentication or
 * physical extent validity. Inputs and output must be disjoint. Only FOUND
 * changes output; MISSING and REFUSED preserve it. */
int vos_typed_tree_lookup(const struct vos_tree_image *image,
                           const struct vos_tree_limits *limits,
                           uint64_t root, const struct vos_storage_typed_key *key,
                           struct vos_storage_extent *output);
int vos_typed_tree_lookup_path(const struct vos_tree_image *image,
                                const struct vos_tree_limits *limits,
                                uint64_t root, const struct vos_storage_typed_key *key,
                                struct vos_storage_extent *output);

#endif
