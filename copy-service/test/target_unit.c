// SPDX-License-Identifier: Apache-2.0
#define VOS_COPY_TARGET
#include "vos_copy_service.h"
#include "../src/copy_service.c"
#include "target_comparison.c"
uint32_t vos_copy_target_ring_bytes(void)
{
    return (uint32_t)sizeof(vos_copy_ring);
}
int vos_copy_target_layout(void)
{
    return offsetof(vos_copy_ring, produced) == 0u
        && offsetof(vos_copy_ring, consumed) == 1u
        && offsetof(vos_copy_ring, armed) == 4u
        && offsetof(vos_copy_ring, generation) == 8u
        && offsetof(vos_copy_ring, slots) == 16u
        && sizeof(vos_copy_atomic_index) == 1u
        && sizeof(vos_copy_atomic_word) == 4u
        && sizeof(vos_copy_request) == 40u
        && offsetof(vos_copy_request, source) == 16u
        && offsetof(vos_copy_request, extent) == 24u
        && offsetof(vos_copy_request, length) == 32u
        && sizeof(vos_copy_ring) <= 524288u;
}
