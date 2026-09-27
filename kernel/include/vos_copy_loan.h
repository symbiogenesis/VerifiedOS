// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_COPY_LOAN_H
#define VOS_COPY_LOAN_H

#include "vos_effects.h"

/* Private state for one synchronous copy activation. The ring allocation stays
 * live. Its grant slot, rather than its byte extent, is what gets retired.
 * These functions are trusted boundary internals, not principal invocations. */
enum vos_copy_loan_holders {
    VOS_COPY_LOAN_STACK = 1,
    VOS_COPY_LOAN_SAVED = 2,
    VOS_COPY_LOAN_FRAMES = 4,
    VOS_COPY_LOAN_REGISTERS = 8,
    VOS_COPY_LOAN_RETURN = 16,
    VOS_COPY_LOAN_ALL = 31
};

struct vos_copy_loan {
    uint64_t epoch, slot_mask;
    uint32_t unit, active;
};

/* The descriptor and this state are inaccessible to the borrower. Initialization
 * is a composition act and must not overwrite an outstanding activation. */
void vos_copy_loan_init(struct vos_copy_loan *loan, uint32_t unit);
/* The assembly boundary has checked the actual sealed handle, current slot bit,
 * ring authority and complete fixed holder layout before calling begin. Only
 * then can it expose the local, byte-only ring loan. The mask is derived from
 * the handle's actual base, not from a caller's integer generation. */
int vos_copy_loan_begin(struct vos_kernel_effect_state *effects,
                        struct vos_copy_loan *loan, uint64_t slot_mask);
/* Called only by the trusted cleanup emitter after clearing and reading back
 * the entire declared stack/save/frame population, scrubbing resident registers
 * and cancelling the obsolete return state. A partial or stale observation
 * leaves the loan outstanding. This C guard supplies no hardware observation. */
int vos_copy_loan_finish(struct vos_kernel_effect_state *effects,
                         struct vos_copy_loan *loan, uint32_t observed);

#endif
