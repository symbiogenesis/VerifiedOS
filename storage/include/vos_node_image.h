// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_NODE_IMAGE_H
#define VOS_NODE_IMAGE_H

#include <stddef.h>
#include <stdint.h>

/* A bounded numeric-key/value instance of ExecutableIndex.v's ENode.
 * This codec checks local shape, not tree admission or authentication. */
#define VOS_NODE_MAX_FAN 16u
#define VOS_NODE_HEADER_BYTES 32u
#define VOS_NODE_LEAF 0u
#define VOS_NODE_BRANCH 1u

struct vos_node_geometry {
    uint32_t fan;
    uint64_t arena_nodes;
    size_t block_bytes;
};

struct vos_node {
    uint32_t kind;
    /* Leaf: number of entries. Branch: number of children. */
    uint32_t count;
    uint64_t node_id;
    uint64_t generation;
    /* Leaf entries use count keys and values. Branches use count - 1
     * separators in keys and count child addresses in values. */
    uint64_t keys[VOS_NODE_MAX_FAN];
    uint64_t values[VOS_NODE_MAX_FAN];
};

/* Both return 1 on success, 0 on refusal. Refusal preserves output bytes.
 * Inputs and outputs must be disjoint. Unused in-memory array cells are
 * ignored by encode and zeroed by decode. The on-wire padding is canonical
 * zero. Callers authenticate the entire encoded block before using a decoded
 * node; node_id/generation equality alone authenticates nothing. */
int vos_node_encode(const struct vos_node_geometry *geometry,
                    const struct vos_node *node, uint8_t *output, size_t length);
int vos_node_decode(const struct vos_node_geometry *geometry,
                    uint64_t expected_id, uint64_t expected_generation,
                    const uint8_t *bytes, size_t length, struct vos_node *output);

#endif
