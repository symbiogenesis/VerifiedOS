// SPDX-License-Identifier: Apache-2.0
#include "vos_resident_scalar.h"

#include <stdio.h>
#include <string.h>

#define REQUIRE(condition, name) do { if (!(condition)) { \
    fprintf(stderr, "resident scalar refusal: %s at %d\n", name, __LINE__); return 1; \
} } while (0)

struct fixture {
    struct vos_resident_owner owner;
    struct vos_resident_scalar_retirement attempt;
    struct vos_kernel_effect_state kernel;
    struct vos_resident_scalar_binding binding;
    struct vos_resident_identity identity;
    struct vos_resident_handle handles[VOS_RESIDENT_HOLDERS];
    uint64_t sequences[VOS_RESIDENT_HOLDERS];
    uint64_t masks[VOS_SUPERVISOR_UNITS], bitmap, clock;
    vos_cap_t roots[VOS_SUPERVISOR_UNITS], caps[3][2];
    uint8_t owned[3][16], bytes[64];
};

static int verify(void *opaque, const struct vos_resident_identity *identity,
                  const uint8_t *bytes, size_t length)
{
    struct fixture *f = opaque;
    return identity->kind == f->identity.kind && length == sizeof(f->bytes) &&
           memcmp(bytes, f->bytes, length) == 0;
}

static int setup(struct fixture *f, uint32_t kind)
{
    struct vos_supervisor_execution execution;
    uint32_t i;
    memset(f, 0, sizeof(*f));
    f->identity.owner = 7; f->identity.domain = 11; f->identity.object = 19;
    f->identity.version = 1; f->identity.generation = 1; f->identity.kind = kind;
    for (i = 0; i < sizeof(f->identity.root); ++i)
        f->identity.root[i] = (uint8_t)(31U + i);
    for (i = 0; i < sizeof(f->bytes); ++i) f->bytes[i] = (uint8_t)(3U * i + 1U);
    if (!vos_resident_init(&f->owner, 1, 1, 15, 0, 0) ||
        !vos_resident_publish(&f->owner, &f->identity, f->bytes, sizeof(f->bytes)))
        return 0;
    for (i = 0; i < VOS_RESIDENT_HOLDERS; ++i)
        if (!vos_resident_admit(&f->owner, i, 11, &f->identity, i * 8, 16, 0, 12,
                                &f->handles[i]) ||
            !vos_resident_begin(&f->owner, &f->handles[i], 11, 0, 16, 1,
                                &f->sequences[i]))
            return 0;
    if (!vos_kernel_effect_init(&f->kernel, &vos_m8a_supervisor_manifest, 7)) return 0;
    for (i = 0; i < f->kernel.manifest.units; ++i) {
        f->roots[i].value = 100 + i; f->roots[i].tag = 1;
        f->masks[i] = UINT64_C(1) << i;
        if (!vos_kernel_own(&f->kernel, i, f->owned[i], sizeof(f->owned[i]),
                            f->caps[i], 2)) return 0;
    }
    if (!vos_kernel_effect_bind(&f->kernel, f->roots, f->masks,
                                &f->bitmap, &f->clock, 4) ||
        vos_supervisor_execute(&f->kernel.manifest, 0, 0, &vos_kernel_supervisor_effects,
                                &f->kernel, &execution) != VOS_SUPERVISOR_EXECUTED)
        return 0;
    memset(f->owned, 0x5a, sizeof(f->owned));
    for (i = 0; i < f->kernel.manifest.units; ++i) {
        f->caps[i][0] = f->roots[i]; f->caps[i][1] = f->roots[i];
        f->kernel.unit[i].saved[31] = f->roots[i];
        f->kernel.unit[i].frames[1][31] = f->roots[i];
    }
    f->binding.epoch = 7; f->binding.members = 7;
    f->binding.holder_units[0] = 1; f->binding.holder_units[1] = 2;
    vos_resident_scalar_init(&f->attempt);
    return 1;
}

static int quarantined(const struct fixture *f)
{
    uint32_t i;
    if (!f->owner.common.occupied || f->owner.common.accepting ||
        memcmp(f->owner.common.bytes, f->bytes, sizeof(f->bytes)) != 0)
        return 0;
    for (i = 0; i < VOS_RESIDENT_HOLDERS; ++i)
        if (f->owner.common.reservation[i].live || f->owner.pending[i].active)
            return 0;
    return 1;
}

static int successful(uint32_t kind)
{
    struct fixture f;
    uint8_t output[64];
    size_t length = 999;
    uint32_t i, n;
    uint64_t mask;
    REQUIRE(setup(&f, kind), "setup success");
    /* A failed holder supplies no acknowledgment; the fixed kernel-owned
     * holder inventory still contains its saved and ordinary capabilities. */
    f.kernel.unit[1].running = 0;
    memset(&f.handles[0], 0, sizeof(f.handles[0]));
    mask = vos_resident_scalar_prepare(&f.attempt, &f.owner, &f.kernel, &f.binding);
    REQUIRE(mask == 7 && quarantined(&f), "complete holder cancellation before publication");
    REQUIRE(!vos_resident_complete(&f.owner, &f.handles[1], 11, f.sequences[1], 1,
                                   verify, &f, output, sizeof(output), &length) &&
            length == 999, "late resident completion cannot publish");
    REQUIRE(!vos_resident_scalar_prepare(&f.attempt, &f.owner, &f.kernel, &f.binding),
            "prepare is one use");
    /* Trusted architectural observations are mocked only at their existing
     * seam. The actual producer clears the declared source storage below. */
    f.bitmap |= mask; f.kernel.resident_clean = 1;
    REQUIRE(vos_resident_scalar_finish(&f.attempt, f.bitmap) &&
            f.attempt.phase == VOS_RESIDENT_SCALAR_COMPLETE && f.kernel.epoch == 8,
            "actual scalar completion");
    REQUIRE(quarantined(&f), "semantic completion retains backing quarantine");
    REQUIRE(!f.kernel.started && f.kernel.needs_replenish == 7 &&
            !f.kernel.retirement_pending, "kernel fresh-replacement obligation");
    for (i = 0; i < f.kernel.manifest.units; ++i) {
        for (n = 0; n < sizeof(f.owned[i]); ++n)
            REQUIRE(f.owned[i][n] == 0, "actual kernel-owned bytes cleared");
        REQUIRE(!f.caps[i][0].tag && !f.caps[i][1].tag &&
                !f.kernel.unit[i].saved[31].tag && !f.kernel.unit[i].frames[1][31].tag,
                "actual kernel-owned capabilities cleared");
    }
    REQUIRE(!vos_resident_scalar_finish(&f.attempt, f.bitmap) && f.kernel.epoch == 8,
            "completion is one use");
    f.identity.version = 2;
    REQUIRE(!vos_resident_publish(&f.owner, &f.identity, f.bytes, sizeof(f.bytes)),
            "semantic completion cannot reuse backing");
    return 0;
}

static int controls(uint32_t kind)
{
    struct fixture f;
    struct vos_resident_owner before;
    uint64_t mask;
    REQUIRE(setup(&f, kind), "setup coverage");
    memcpy(&before, &f.owner, sizeof(before));
    f.binding.holder_units[1] = f.kernel.manifest.units;
    REQUIRE(!vos_resident_scalar_prepare(&f.attempt, &f.owner, &f.kernel, &f.binding) &&
            memcmp(&before, &f.owner, sizeof(before)) == 0 && !f.kernel.retirement_pending,
            "uncovered second holder refuses before effects");
    REQUIRE(setup(&f, kind), "setup epoch");
    f.binding.epoch = 6;
    REQUIRE(!vos_resident_scalar_prepare(&f.attempt, &f.owner, &f.kernel, &f.binding) &&
            f.owner.common.accepting && !f.kernel.retirement_pending,
            "stale attempt epoch refuses before effects");
    REQUIRE(setup(&f, kind), "setup storage alias");
    f.kernel.unit[1].owned_bytes = f.owner.common.bytes;
    REQUIRE(!vos_resident_scalar_prepare(&f.attempt, &f.owner, &f.kernel, &f.binding) &&
            f.owner.common.accepting, "kernel clear cannot alias retained bytes");
    REQUIRE(setup(&f, kind), "setup active copy");
    f.kernel.unit[1].inflight = 1;
    REQUIRE(!vos_resident_scalar_prepare(&f.attempt, &f.owner, &f.kernel, &f.binding) &&
            f.attempt.phase == VOS_RESIDENT_SCALAR_REFUSED && quarantined(&f),
            "active copy refusal quarantines without holder wait");
    f.kernel.unit[1].inflight = 0;
    REQUIRE(!vos_resident_scalar_prepare(&f.attempt, &f.owner, &f.kernel, &f.binding),
            "producer refusal is sticky");
    REQUIRE(setup(&f, kind), "setup open victim");
    f.binding.members = 1; f.kernel.manifest.restart_members = 1;
    f.binding.holder_units[0] = 0; f.binding.holder_units[1] = 0;
    REQUIRE(!vos_resident_scalar_prepare(&f.attempt, &f.owner, &f.kernel, &f.binding) &&
            quarantined(&f), "actual kernel rejects ownership-open victim");
    REQUIRE(setup(&f, kind), "setup missing publication");
    mask = vos_resident_scalar_prepare(&f.attempt, &f.owner, &f.kernel, &f.binding);
    f.kernel.resident_clean = 1;
    REQUIRE(mask == 7 && !vos_resident_scalar_finish(&f.attempt, mask ^ 1) &&
            f.attempt.phase == VOS_RESIDENT_SCALAR_REFUSED && f.kernel.epoch == 7 &&
            quarantined(&f), "missing publication refuses");
    REQUIRE(!vos_resident_scalar_finish(&f.attempt, mask) && f.kernel.epoch == 7,
            "failed completion is one use");
    REQUIRE(setup(&f, kind), "setup missing scrub");
    mask = vos_resident_scalar_prepare(&f.attempt, &f.owner, &f.kernel, &f.binding);
    REQUIRE(mask == 7 && !vos_resident_scalar_finish(&f.attempt, mask) &&
            f.attempt.phase == VOS_RESIDENT_SCALAR_REFUSED && f.kernel.epoch == 8 &&
            f.kernel.retirement_pending && quarantined(&f),
            "partial kernel teardown is not semantic completion");
    f.kernel.resident_clean = 1;
    REQUIRE(!vos_resident_scalar_finish(&f.attempt, mask), "partial teardown cannot retry");
    REQUIRE(setup(&f, kind), "setup epoch drift");
    mask = vos_resident_scalar_prepare(&f.attempt, &f.owner, &f.kernel, &f.binding);
    ++f.kernel.epoch; f.kernel.resident_clean = 1;
    REQUIRE(!vos_resident_scalar_finish(&f.attempt, mask) && quarantined(&f),
            "current kernel epoch must match attempt");
    REQUIRE(setup(&f, kind), "setup resident drift");
    mask = vos_resident_scalar_prepare(&f.attempt, &f.owner, &f.kernel, &f.binding);
    ++f.owner.common.identity.version; f.kernel.resident_clean = 1;
    REQUIRE(!vos_resident_scalar_finish(&f.attempt, mask) && f.kernel.epoch == 7,
            "changed resident binding cannot complete");
    REQUIRE(setup(&f, kind), "setup late transfer");
    mask = vos_resident_scalar_prepare(&f.attempt, &f.owner, &f.kernel, &f.binding);
    f.owner.pending[1].active = 1; f.kernel.resident_clean = 1;
    REQUIRE(!vos_resident_scalar_finish(&f.attempt, mask) && f.kernel.epoch == 7,
            "late transfer cannot complete retirement");
    return 0;
}

int main(void)
{
    uint32_t kind;
    for (kind = VOS_RESIDENT_SYSTEM; kind <= VOS_RESIDENT_USER; ++kind)
        if (successful(kind) || controls(kind)) return 1;
    fprintf(stderr, "ok resident scalar actual producer, quarantine and one-attempt controls\n");
    return 0;
}
