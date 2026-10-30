// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_RESIDENT_SCALAR_H
#define VOS_RESIDENT_SCALAR_H

#include "vos_resident_reads.h"
#include "vos_effects.h"

#define VOS_RESIDENT_SCALAR_IDLE 0U
#define VOS_RESIDENT_SCALAR_PREPARED 1U
#define VOS_RESIDENT_SCALAR_COMPLETE 2U
#define VOS_RESIDENT_SCALAR_REFUSED 3U

/* Authenticated composition input: every possible holder slot, including an
 * inactive slot, maps to one scalar unit in the exact closed victim set.
 * Completeness of this finite inventory against the machine, authentic roots
 * and disjoint private storage remain the composition/target obligations. */
struct vos_resident_scalar_binding {
    uint64_t epoch;
    uint32_t members;
    uint32_t holder_units[VOS_RESIDENT_HOLDERS];
};

/* Kernel-private one-attempt record. Ordinary compartments may not retain or
 * mutate it. Calls run with service dispatch excluded, as the scalar producer
 * requires. No read operation touches this record. */
struct vos_resident_scalar_retirement {
    struct vos_resident_owner *owner;
    struct vos_kernel_effect_state *kernel;
    struct vos_resident_common closed;
    struct vos_resident_request pending[VOS_RESIDENT_HOLDERS];
    uint64_t sequence[VOS_RESIDENT_HOLDERS];
    uint64_t epoch, mask;
    uint32_t members, phase;
};

void vos_resident_scalar_init(struct vos_resident_scalar_retirement *attempt);
/* Close admission and cancel all finite reservations and pending requests,
 * then prepare the actual kernel's one-use publication ticket. A producer
 * refusal leaves the original bytes occupied in closed quarantine. Invalid
 * binding refuses before touching the owner or kernel. */
uint64_t vos_resident_scalar_prepare(struct vos_resident_scalar_retirement *attempt,
                                    struct vos_resident_owner *owner,
                                    struct vos_kernel_effect_state *kernel,
                                    const struct vos_resident_scalar_binding *binding);
/* Trusted assembly publishes the returned mask to the actual bitmap, reads it
 * back and scrubs resident roots before this call, as for vos_kernel_retire.
 * Consume publication and actual semantic completion for the same epoch once.
 * Failure is sticky, including after partial kernel teardown. Even success
 * leaves backing occupied and quarantined: this receipt establishes neither a
 * post-barrier sweep nor safe reuse, and this API never releases backing. */
int vos_resident_scalar_finish(struct vos_resident_scalar_retirement *attempt,
                               uint64_t observed);

#endif
