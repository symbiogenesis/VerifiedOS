// SPDX-License-Identifier: Apache-2.0
#include <stdio.h>
#include "vos_copy_loan.h"

static struct vos_kernel_effect_state effects;
static struct vos_copy_loan loan;
static unsigned checks;
#define CHECK(c) do { ++checks; if (!(c)) { fprintf(stderr, "loan failure %u\n", checks); return 1; } } while (0)

int main(void)
{
    unsigned observed;
    effects.bound = 1;
    effects.manifest.units = 1;
    effects.epoch = 7;
    effects.unit[0].running = 1;
    effects.unit[0].generation = 7;
    effects.masks[0] = 2;
    vos_copy_loan_init(&loan, 0);
    CHECK(!vos_copy_loan_begin(&effects, &loan, 0));
    CHECK(!vos_copy_loan_begin(&effects, &loan, 1));
    CHECK(!vos_copy_loan_begin(&effects, &loan, 3));
    CHECK(vos_copy_loan_begin(&effects, &loan, 2));
    CHECK(effects.loans == 1 && loan.active && loan.epoch == 7);
    CHECK(!vos_copy_loan_begin(&effects, &loan, 2));
    for (observed = 0; observed < 31; ++observed) {
        CHECK(!vos_copy_loan_finish(&effects, &loan, observed));
        CHECK(effects.loans == 1 && loan.active);
    }
    effects.epoch = 8;
    CHECK(!vos_copy_loan_finish(&effects, &loan, 31));
    CHECK(effects.loans == 1 && loan.active);
    effects.epoch = 7;
    CHECK(vos_copy_loan_finish(&effects, &loan, 31));
    CHECK(!effects.loans && !loan.active);
    CHECK(!vos_copy_loan_finish(&effects, &loan, 31));
    effects.retirement_pending = 1;
    CHECK(!vos_copy_loan_begin(&effects, &loan, 2));
    effects.retirement_pending = 0;
    effects.needs_replenish = 1;
    CHECK(!vos_copy_loan_begin(&effects, &loan, 2));
    effects.needs_replenish = 0;
    effects.unit[0].generation = 6;
    CHECK(!vos_copy_loan_begin(&effects, &loan, 2));
    fprintf(stderr, "ok copy loan %u checks; hardware observations mocked\n", checks);
    return 0;
}
