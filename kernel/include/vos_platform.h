// SPDX-License-Identifier: Apache-2.0
/*
 * The one place the kernel sources differ between their two builds.
 *
 * A saved register is a capability slot. On the target it is a pointer-typed
 * slot, which the contained compiler moves with capability loads and stores,
 * so assignment preserves the value and its validity tag together (R-15-007i;
 * compiler-source-values.md section 4). The kernel only ever moves a slot
 * whole, so the same assignment compiles on both sides.
 *
 * In the host model a slot is its 64 data bits and its tag as two fields,
 * which is what the commit trace records (differential-corpus.md section 4)
 * and what the Gallina vectors carry. The host model also supplies the one
 * decode the revocation join reads, a capability's base, as the identity on
 * the data bits: the decode is the model's (KernelInstance.v `base_of`) and a
 * second implementation of it here would be a second place for it to be
 * wrong, so the host model states the function the probe states and no more.
 */
#ifndef VOS_PLATFORM_H
#define VOS_PLATFORM_H 1

#include <stdint.h>

#if defined(VOS_HOST_MODEL)

struct vos_cap {
  uint64_t value;
  uint8_t tag;
};
typedef struct vos_cap vos_cap_t;

/* A published revocation bitmap over the first 64 bases: bit b set marks
 * base b. A base at or past 64 is never marked in the host model. */
struct vos_bitmap {
  uint64_t marked;
};

int vos_cap_tag(vos_cap_t c);
uint64_t vos_cap_base(vos_cap_t c);
int vos_bitmap_marks(const struct vos_bitmap *bm, uint64_t base);

#elif defined(VOS_TARGET_SLOT)

/* A typed slot for a program that stores one kind of object's capability.
 * `void *` is the one C type that holds any capability, and the contained
 * compiler's typed source check currently refuses a `void *` slot that holds
 * a stack object's capability (kernel/README.md); the target smoke names a
 * typed slot for that reason and for no other. */
typedef VOS_TARGET_SLOT vos_cap_t;

#else

typedef void *vos_cap_t;

#endif

#endif
