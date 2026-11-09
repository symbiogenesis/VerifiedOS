// SPDX-License-Identifier: Apache-2.0
#include "vos_typed_entry.h"

#include <string.h>

#include "vos_node_image.h"

static void put_word(uint8_t *out, uint64_t value, size_t width, int big_endian)
{
    for (size_t i = 0; i < width; ++i)
        out[big_endian ? width - 1u - i : i] = (uint8_t)(value >> (8u * i));
}

static uint64_t get_word(const uint8_t *in, size_t width, int big_endian)
{
    uint64_t value = 0u;
    for (size_t i = 0; i < width; ++i)
        value |= (uint64_t)in[big_endian ? width - 1u - i : i] << (8u * i);
    return value;
}

int vos_storage_typed_key_encode(const struct vos_storage_typed_key *key,
                                 uint8_t *bytes, size_t length)
{
    if (key == NULL || bytes == NULL || length != VOS_STORAGE_TYPED_KEY_BYTES) return 0;
    const uint64_t fields[] = {
        key->domain, key->space, key->kind, key->object, key->attribute, key->version
    };
    for (size_t i = 0; i < 6u; ++i) put_word(bytes + 8u * i, fields[i], 8u, 1);
    return 1;
}

int vos_storage_typed_key_decode(const uint8_t *bytes, size_t length,
                                 struct vos_storage_typed_key *key)
{
    if (bytes == NULL || key == NULL || length != VOS_STORAGE_TYPED_KEY_BYTES) return 0;
    const struct vos_storage_typed_key decoded = {
        .domain = get_word(bytes, 8u, 1),
        .space = get_word(bytes + 8u, 8u, 1),
        .kind = get_word(bytes + 16u, 8u, 1),
        .object = get_word(bytes + 24u, 8u, 1),
        .attribute = get_word(bytes + 32u, 8u, 1),
        .version = get_word(bytes + 40u, 8u, 1)
    };
    *key = decoded;
    return 1;
}

static int valid_extent(const struct vos_storage_extent *extent)
{
    return extent != NULL &&
           extent->domain_epoch <= VOS_NODE_NONCE_MAX_DOMAIN &&
           extent->node_id <= VOS_NODE_NONCE_MAX_ID &&
           (extent->kind == VOS_NODE_LEAF || extent->kind == VOS_NODE_BRANCH);
}

int vos_storage_extent_encode(const struct vos_storage_extent *extent,
                              uint8_t *bytes, size_t length)
{
    if (bytes == NULL || length != VOS_STORAGE_EXTENT_BYTES || !valid_extent(extent)) return 0;
    memcpy(bytes, "VOSEXT01", 8u);
    put_word(bytes + 8u, extent->block_address, 8u, 0);
    put_word(bytes + 16u, extent->byte_length, 8u, 0);
    put_word(bytes + 24u, extent->node_id, 8u, 0);
    put_word(bytes + 32u, extent->generation, 8u, 0);
    put_word(bytes + 40u, extent->domain_epoch, 4u, 0);
    put_word(bytes + 44u, extent->kind, 4u, 0);
    memcpy(bytes + 48u, extent->tag, sizeof(extent->tag));
    memcpy(bytes + 64u, extent->content_digest, sizeof(extent->content_digest));
    return 1;
}

int vos_storage_extent_decode(const uint8_t *bytes, size_t length,
                              struct vos_storage_extent *extent)
{
    if (bytes == NULL || extent == NULL || length != VOS_STORAGE_EXTENT_BYTES ||
        memcmp(bytes, "VOSEXT01", 8u) != 0) return 0;
    struct vos_storage_extent decoded = {
        .block_address = get_word(bytes + 8u, 8u, 0),
        .byte_length = get_word(bytes + 16u, 8u, 0),
        .node_id = get_word(bytes + 24u, 8u, 0),
        .generation = get_word(bytes + 32u, 8u, 0),
        .domain_epoch = (uint32_t)get_word(bytes + 40u, 4u, 0),
        .kind = (uint32_t)get_word(bytes + 44u, 4u, 0)
    };
    if (!valid_extent(&decoded)) return 0;
    memcpy(decoded.tag, bytes + 48u, sizeof(decoded.tag));
    memcpy(decoded.content_digest, bytes + 64u, sizeof(decoded.content_digest));
    *extent = decoded;
    return 1;
}

int vos_storage_typed_leaf_capacity(size_t block_bytes, size_t header_bytes,
                                    uint32_t *capacity)
{
    if (capacity == NULL || header_bytes > block_bytes) return 0;
    const size_t count = (block_bytes - header_bytes) / VOS_STORAGE_TYPED_ENTRY_BYTES;
    if (count == 0u || count > UINT32_MAX) return 0;
    *capacity = (uint32_t)count;
    return 1;
}
