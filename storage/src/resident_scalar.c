// SPDX-License-Identifier: Apache-2.0
#include "vos_resident_scalar.h"

#include <string.h>

static int overlap(const void *a, size_t alen, const void *b, size_t blen)
{
    uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
    return alen != 0 && blen != 0 &&
           (x <= y ? y - x < alen : x - y < blen);
}

static int outside(const struct vos_resident_scalar_retirement *a,
                   const struct vos_resident_owner *o,
                   const void *p, size_t length)
{
    return (length == 0 || p != 0) &&
           !overlap(a, sizeof(*a), p, length) &&
           !overlap(o, sizeof(*o), p, length);
}

static int binding_ok(const struct vos_resident_scalar_retirement *a,
                      const struct vos_resident_owner *o,
                      const struct vos_kernel_effect_state *k,
                      const struct vos_resident_scalar_binding *b)
{
    uint32_t i;
    if (a == 0 || o == 0 || k == 0 || b == 0 ||
        overlap(a, sizeof(*a), o, sizeof(*o)) ||
        overlap(k, sizeof(*k), o, sizeof(*o)) ||
        overlap(k, sizeof(*k), a, sizeof(*a)) ||
        !o->common.occupied || !k->bound || k->locked || k->retirement_pending ||
        !vos_supervisor_manifest_ok(&k->manifest) ||
        k->manifest.units > VOS_KERNEL_EFFECT_UNITS ||
        b->epoch != k->epoch || b->epoch == UINT64_MAX ||
        b->members == 0 || b->members != k->manifest.restart_members)
        return 0;
    for (i = 0; i < VOS_RESIDENT_HOLDERS; ++i) {
        /* COVERAGE: even an inactive slot can contain an old pending transfer. */
        if (b->holder_units[i] >= k->manifest.units ||
            (b->members & (1U << b->holder_units[i])) == 0)
            return 0;
    }
    /* Teardown of declared unit storage must not overwrite retained backing or
     * the one-attempt record before a separate reuse/sweep argument exists. */
    for (i = 0; i < k->manifest.units; ++i) {
        const struct vos_kernel_unit *u = &k->unit[i];
        /* vos_kernel_own already admitted these private bounds. */
        if (!outside(a, o, u->owned_bytes, u->owned_length) ||
            !outside(a, o, u->owned_caps, sizeof(vos_cap_t) * u->owned_count))
            return 0;
    }
    return 1;
}

void vos_resident_scalar_init(struct vos_resident_scalar_retirement *a)
{
    if (a != 0) memset(a, 0, sizeof(*a));
}

uint64_t vos_resident_scalar_prepare(struct vos_resident_scalar_retirement *a,
                                    struct vos_resident_owner *o,
                                    struct vos_kernel_effect_state *k,
                                    const struct vos_resident_scalar_binding *binding)
{
    struct vos_resident_scalar_binding b;
    if (a == 0 || a->phase != VOS_RESIDENT_SCALAR_IDLE ||
        !binding_ok(a, o, k, binding))
        return 0;
    b = *binding;
    a->phase = VOS_RESIDENT_SCALAR_REFUSED;
    a->owner = o; a->kernel = k; a->epoch = b.epoch; a->members = b.members;
    /* Existing owner code closes every holder/request before touching bytes.
     * A false barrier deliberately leaves the backing occupied and unchanged. */
    (void)vos_resident_retire(o, 0);
    memcpy(&a->closed, &o->common, sizeof(a->closed));
    memcpy(a->pending, o->pending, sizeof(a->pending));
    memcpy(a->sequence, o->sequence, sizeof(a->sequence));
    a->mask = vos_kernel_retirement_mask(k, b.members);
    if (a->mask == 0) return 0;
    a->phase = VOS_RESIDENT_SCALAR_PREPARED;
    return a->mask;
}

int vos_resident_scalar_finish(struct vos_resident_scalar_retirement *a,
                               uint64_t observed)
{
    struct vos_completion completion;
    struct vos_resident_owner *o;
    struct vos_kernel_effect_state *k;
    uint32_t i;
    if (a == 0 || a->phase != VOS_RESIDENT_SCALAR_PREPARED) return 0;
    a->phase = VOS_RESIDENT_SCALAR_REFUSED;
    o = a->owner; k = a->kernel;
    if (k->epoch != a->epoch || !o->common.occupied || o->common.accepting ||
        memcmp(&o->common, &a->closed, sizeof(a->closed)) != 0 ||
        memcmp(o->pending, a->pending, sizeof(a->pending)) != 0 ||
        memcmp(o->sequence, a->sequence, sizeof(a->sequence)) != 0)
        return 0;
    for (i = 0; i < VOS_RESIDENT_HOLDERS; ++i)
        if (o->common.reservation[i].live || o->pending[i].active) return 0;
    if (!vos_kernel_publication(k, a->epoch, a->mask, observed) ||
        !vos_kernel_retire(k, a->members, &completion) ||
        !completion.epoch_advanced || !vos_semantic_completion(&completion) ||
        k->epoch != a->epoch + 1)
        return 0;
    /* CONTAINED_ONLY: semantic completion never authorizes backing release. */
    a->phase = VOS_RESIDENT_SCALAR_COMPLETE;
    return 1;
}
