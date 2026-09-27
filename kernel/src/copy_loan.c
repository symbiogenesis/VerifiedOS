// SPDX-License-Identifier: Apache-2.0
#include "vos_copy_loan.h"

void vos_copy_loan_init(struct vos_copy_loan *loan, uint32_t unit)
{
    loan->epoch = 0;
    loan->slot_mask = 0;
    loan->unit = unit;
    loan->active = 0;
}

int vos_copy_loan_begin(struct vos_kernel_effect_state *effects,
                        struct vos_copy_loan *loan, uint64_t slot_mask)
{
    uint32_t unit;
    if (effects == 0 || loan == 0 || !effects->bound || effects->locked ||
        effects->retirement_pending || effects->needs_replenish || effects->loans ||
        loan->active || slot_mask == 0 || (slot_mask & (slot_mask - 1)) != 0)
        return 0;
    unit = loan->unit;
    if (unit >= effects->manifest.units || !effects->unit[unit].running ||
        effects->unit[unit].generation != effects->epoch ||
        (effects->masks[unit] & slot_mask) != slot_mask)
        return 0;
    loan->epoch = effects->epoch;
    loan->slot_mask = slot_mask;
    loan->active = 1;
    effects->loans = 1;
    return 1;
}

int vos_copy_loan_finish(struct vos_kernel_effect_state *effects,
                         struct vos_copy_loan *loan, uint32_t observed)
{
    if (effects == 0 || loan == 0 || !loan->active || effects->loans != 1 ||
        loan->epoch != effects->epoch || loan->unit >= effects->manifest.units ||
        effects->unit[loan->unit].generation != loan->epoch ||
        (effects->masks[loan->unit] & loan->slot_mask) != loan->slot_mask ||
        observed != VOS_COPY_LOAN_ALL)
        return 0;
    loan->active = 0;
    loan->slot_mask = 0;
    effects->loans = 0;
    return 1;
}
