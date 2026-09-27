// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_EFFECTS_H
#define VOS_EFFECTS_H

#include "vos_supervisor_effects.h"

/* Composition bounds. All storage is kernel-private and all public entry
 * points run on one hart while ordinary service dispatch is stopped. The
 * serialized region is a kernel dispatch exclusion, not a C atomic lock.
 * Callers may not hand this record or its roots to an ordinary compartment. */
#ifndef VOS_KERNEL_EFFECT_UNITS
#define VOS_KERNEL_EFFECT_UNITS VOS_SUPERVISOR_UNITS
#endif
#define VOS_KERNEL_PRIVATE_BYTES 64U
#define VOS_KERNEL_FRAME_DEPTH 2U
#define VOS_KERNEL_FRAME_SLOTS 32U

struct vos_kernel_unit {
    uint32_t running, pending, poll_hint, inflight, depth;
    uint64_t generation;
    uint8_t *owned_bytes;
    uint32_t owned_length;
    vos_cap_t *owned_caps;
    uint32_t owned_count;
    uint8_t bytes[VOS_KERNEL_PRIVATE_BYTES];
    vos_cap_t saved[33];
    vos_cap_t frames[VOS_KERNEL_FRAME_DEPTH][VOS_KERNEL_FRAME_SLOTS];
    vos_cap_t grants[VOS_SUPERVISOR_UNITS];
};

struct vos_kernel_effect_state {
    struct vos_supervisor_manifest manifest;
    struct vos_supervisor_epoch snapshot;
    struct vos_kernel_unit unit[VOS_KERNEL_EFFECT_UNITS];
    /* Roots and bitmap masks come from the authenticated composition. Roots
     * retained here are trusted minting authority, not service-held grants. */
    vos_cap_t roots[VOS_KERNEL_EFFECT_UNITS];
    uint64_t masks[VOS_KERNEL_EFFECT_UNITS];
    uint64_t *bitmap;
    uint64_t *clock;
    uint64_t epoch;
    uint64_t prepared_mask, publication_epoch, published_mask;
    uint64_t wait_epoch, wait_start, wait_now;
    uint32_t wait_delay, wait_ready, wait_seen;
    uint32_t locked, bound, polls, started, resident_clean;
    uint32_t loans, devices, retirement_pending;
};

int vos_kernel_effect_init(struct vos_kernel_effect_state *state,
                           const struct vos_supervisor_manifest *manifest,
                           uint64_t epoch);
/* The target entry validates actual capability bounds/rights before binding.
 * Every retired object must map to this one bitmap word in this bounded
 * composition. A zero mask, unbounded polling, and overlapping masks refuse. */
int vos_kernel_effect_bind(struct vos_kernel_effect_state *state,
                           const vos_cap_t *roots, const uint64_t *masks,
                           uint64_t *bitmap, uint64_t *clock,
                           uint32_t polls);
/* The trap adapter saves all outgoing registers, destroys the live activation
 * chain and scrubs outgoing resident registers before setting resident_clean.
 * A C callback cannot establish that architectural prerequisite itself. */
/* Assembly prepares a one-use ticket, publishes the mask on the actual
 * bitmap, and returns its readback with the same epoch/mask before retire.
 * The ticket refuses stale acknowledgments and cannot be reused. */
uint64_t vos_kernel_retirement_mask(struct vos_kernel_effect_state *state,
                                    uint32_t members);
int vos_kernel_publication(struct vos_kernel_effect_state *state, uint64_t epoch,
                            uint64_t mask, uint64_t observed);
int vos_kernel_wait_sample(struct vos_kernel_effect_state *state, uint64_t epoch,
                            uint32_t delay,
                            uint64_t start, uint64_t now);
/* External storage belongs exclusively to the unit, is disjoint from this
 * state and every peer's storage, and has checked actual capability bounds.
 * These obligations belong to the authenticated composition/target adapter.
 * The byte bound includes the copy service's complete 524288-byte region. */
int vos_kernel_own(struct vos_kernel_effect_state *state, uint32_t unit,
                    uint8_t *bytes, uint32_t length,
                    vos_cap_t *caps, uint32_t count);
int vos_kernel_retire(struct vos_kernel_effect_state *state, uint32_t members,
                       struct vos_completion *completion);
int vos_kernel_wait(struct vos_kernel_effect_state *state, uint32_t delay);
int vos_kernel_acquire(struct vos_kernel_effect_state *state,
                        struct vos_supervisor_epoch *snapshot, uint64_t *epoch);
int vos_kernel_start(struct vos_kernel_effect_state *state,
                      const struct vos_supervisor_start *request);
void vos_kernel_release(struct vos_kernel_effect_state *state);
extern const struct vos_supervisor_effects vos_kernel_supervisor_effects;

/* A pending signal is sticky until wait consumes it. Thus a publication
 * between recheck and wait is consumed, never lost. poll_hint records only the
 * notification protocol; running stays true and there is no blocked queue or
 * scheduler suspension. A quiet poll returns to the admitted synchronous yield
 * site (R-07-029a). One finite synchronous
 * invocation per unit is supported; active work refuses retirement. */
int vos_kernel_notify(struct vos_kernel_effect_state *state, uint32_t unit,
                       uint64_t generation);
int vos_kernel_copy_wait(struct vos_kernel_effect_state *state, uint32_t unit,
                          uint64_t generation);
int vos_kernel_copy_begin(struct vos_kernel_effect_state *state, uint32_t unit,
                           uint64_t generation);
int vos_kernel_copy_complete(struct vos_kernel_effect_state *state, uint32_t unit,
                              uint64_t generation);
/* Protected frame reserve/pop never writes outside the bounded array.
 * A fault discards the whole chain through retire, never resumes a snapshot. */
int vos_kernel_frame_enter(struct vos_kernel_effect_state *state, uint32_t unit,
                            uint64_t generation);
int vos_kernel_frame_leave(struct vos_kernel_effect_state *state, uint32_t unit,
                            uint64_t generation);

#endif
