// SPDX-License-Identifier: Apache-2.0
#include "vos_typed_entry.h"

#include <stdio.h>
#include <string.h>

struct key_vector {
    struct vos_storage_typed_key key;
    uint8_t bytes[VOS_STORAGE_TYPED_KEY_BYTES];
};
struct extent_vector {
    struct vos_storage_extent extent;
    uint8_t bytes[VOS_STORAGE_EXTENT_BYTES];
};
#include "typed_entry_vectors.h"

#define REQUIRE(p) do { if (!(p)) { \
    fprintf(stderr, "typed entry failed at %d: %s\n", __LINE__, #p); return 1; \
} } while (0)

static int same_key(const struct vos_storage_typed_key *a,
                     const struct vos_storage_typed_key *b)
{
    return a->domain == b->domain && a->space == b->space && a->kind == b->kind &&
           a->object == b->object && a->attribute == b->attribute && a->version == b->version;
}

int main(void)
{
    uint8_t key_bytes[VOS_STORAGE_TYPED_KEY_BYTES];
    for (size_t i = 0; i < sizeof(keys) / sizeof(keys[0]); ++i) {
        struct vos_storage_typed_key decoded;
        REQUIRE(vos_storage_typed_key_encode(&keys[i].key, key_bytes, sizeof(key_bytes)));
        REQUIRE(memcmp(key_bytes, keys[i].bytes, sizeof(key_bytes)) == 0);
        REQUIRE(vos_storage_typed_key_decode(keys[i].bytes, sizeof(key_bytes), &decoded));
        REQUIRE(same_key(&decoded, &keys[i].key));
        if (i > 0) REQUIRE(memcmp(keys[i - 1].bytes, key_bytes, sizeof(key_bytes)) < 0);
        const struct vos_storage_typed_key before = decoded;
        REQUIRE(!vos_storage_typed_key_decode(key_bytes, sizeof(key_bytes) - 1u, &decoded));
        REQUIRE(same_key(&decoded, &before));
    }
    uint8_t encoded[VOS_STORAGE_EXTENT_BYTES];
    for (size_t i = 0; i < sizeof(extents) / sizeof(extents[0]); ++i) {
        struct vos_storage_extent decoded;
        const struct vos_storage_extent *expected = &extents[i].extent;
        REQUIRE(vos_storage_extent_encode(expected, encoded, sizeof(encoded)));
        REQUIRE(memcmp(encoded, extents[i].bytes, sizeof(encoded)) == 0);
        REQUIRE(vos_storage_extent_decode(extents[i].bytes, sizeof(encoded), &decoded));
        REQUIRE(decoded.block_address == expected->block_address &&
                 decoded.byte_length == expected->byte_length && decoded.node_id == expected->node_id &&
                 decoded.generation == expected->generation && decoded.domain_epoch == expected->domain_epoch &&
                 decoded.kind == expected->kind && memcmp(decoded.tag, expected->tag, 16u) == 0 &&
                 memcmp(decoded.content_digest, expected->content_digest, 32u) == 0);
        uint8_t before[sizeof(decoded)];
        memcpy(before, &decoded, sizeof(decoded));
        for (size_t n = 0; n < sizeof(encoded); ++n) {
            REQUIRE(!vos_storage_extent_decode(encoded, n, &decoded));
            REQUIRE(memcmp(before, &decoded, sizeof(decoded)) == 0);
        }
        const size_t malformed[] = {0u, 27u, 40u, 44u};
        for (size_t n = 0; n < sizeof(malformed) / sizeof(malformed[0]); ++n) {
            const size_t offset = malformed[n];
            const uint8_t saved = encoded[offset];
            encoded[offset] = 0xffu;
            REQUIRE(!vos_storage_extent_decode(encoded, sizeof(encoded), &decoded));
            REQUIRE(memcmp(before, &decoded, sizeof(decoded)) == 0);
            encoded[offset] = saved;
        }
        struct vos_storage_extent invalid = *expected;
        invalid.node_id = 0x1000000u;
        REQUIRE(!vos_storage_extent_encode(&invalid, encoded, sizeof(encoded)));
        REQUIRE(memcmp(encoded, extents[i].bytes, sizeof(encoded)) == 0);
    }
    uint32_t capacity = 91u;
    REQUIRE(!vos_storage_typed_leaf_capacity(128u, 32u, &capacity) && capacity == 91u);
    REQUIRE(!vos_storage_typed_leaf_capacity(32u, 33u, &capacity) && capacity == 91u);
    REQUIRE(vos_storage_typed_leaf_capacity(4096u, 32u, &capacity) && capacity == 28u);
    puts("typed entry: ok");
    return 0;
}
