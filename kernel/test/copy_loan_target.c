// SPDX-License-Identifier: Apache-2.0
#define VOS_EFFECTS_TYPED
#define VOS_KERNEL_EFFECT_UNITS 3
#include "../src/copy_loan.c"

int vos_copy_loan_target_prepare(struct vos_kernel_effect_state *effects,
                                 struct vos_copy_loan *loan)
{
    effects->bound = 1;
    effects->locked = 0;
    effects->retirement_pending = 0;
    effects->needs_replenish = 0;
    effects->loans = 0;
    effects->manifest.units = 1;
    effects->epoch = 7;
    effects->unit[0].running = 1;
    effects->unit[0].generation = 7;
    effects->masks[0] = 1;
    vos_copy_loan_init(loan, 0);
    return sizeof(*effects) <= 16384 && sizeof(*loan) == 24;
}

int vos_copy_loan_target_closed(const struct vos_kernel_effect_state *effects,
                                const struct vos_copy_loan *loan)
{
    return effects->loans == 0 && loan->active == 0;
}
