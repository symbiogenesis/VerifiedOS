// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_TYPED_ENTRY_H
#define VOS_TYPED_ENTRY_H

#include <stddef.h>
#include <stdint.h>

enum {
    VOS_STORAGE_TYPED_KEY_BYTES = 48u,
    VOS_STORAGE_EXTENT_BYTES = 96u,
    VOS_STORAGE_TYPED_ENTRY_BYTES = VOS_STORAGE_TYPED_KEY_BYTES + VOS_STORAGE_EXTENT_BYTES
};

/* [Bounded format and acceptance](../typed-entry.md). */
struct vos_storage_typed_key {
    uint64_t domain, space, kind, object, attribute, version;
};

struct vos_storage_extent {
    uint64_t block_address, byte_length, node_id, generation;
    uint32_t domain_epoch, kind;
    uint8_t tag[16];
    uint8_t content_digest[32];
};

/* Exact lengths and disjoint input/output objects are required. Refusal
 * preserves output. Key bytes compare in the same order as the tuple. */
int vos_storage_typed_key_encode(const struct vos_storage_typed_key *key,
                                 uint8_t *bytes, size_t length);
int vos_storage_typed_key_decode(const uint8_t *bytes, size_t length,
                                 struct vos_storage_typed_key *key);
int vos_storage_extent_encode(const struct vos_storage_extent *extent,
                              uint8_t *bytes, size_t length);
int vos_storage_extent_decode(const uint8_t *bytes, size_t length,
                              struct vos_storage_extent *extent);
int vos_storage_typed_leaf_capacity(size_t block_bytes, size_t header_bytes,
                                    uint32_t *capacity);

#endif
