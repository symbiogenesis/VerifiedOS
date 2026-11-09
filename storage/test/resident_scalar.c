// SPDX-License-Identifier: Apache-2.0
#include "vos_resident_scalar.h"
#include "vos_storage_publish.h"

#include <stdio.h>
#include <string.h>

#define REQUIRE(condition, name) do { if (!(condition)) { \
    fprintf(stderr, "resident scalar refusal: %s at %d\n", name, __LINE__); return 1; \
} } while (0)

struct fixture {
    struct vos_crypto_core crypto;
    struct vos_storage_medium medium;
    struct vos_storage_store store;
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

static int setup(struct fixture *f, uint32_t kind)
{
    static const struct vos_node_geometry geometry = {4U, 16U, 128U};
    static const struct vos_tree_limits limits = {0U, 4U, 32U};
    struct vos_supervisor_execution execution;
    struct vos_storage_tx_spec tx;
    uint8_t master_key[VOS_CRYPTO_KEY_BYTES_256];
    uint64_t tree_value = 0, ack_gen = 0;
    const uint32_t slot = (kind == VOS_RESIDENT_SYSTEM)
                          ? VOS_CRYPTO_DOMAIN_SYSTEM
                          : VOS_CRYPTO_DOMAIN_USER;
    memset(f, 0, sizeof(*f));
    for (uint32_t i = 0; i < sizeof(master_key); ++i)
        master_key[i] = (uint8_t)(0x40U + i);
    for (uint32_t i = 0; i < sizeof(f->bytes); ++i)
        f->bytes[i] = (uint8_t)(3U * i + 1U + kind);
    vos_crypto_core_init(&f->crypto, 16U);
    if (!vos_crypto_core_unlock_domain(&f->crypto, slot, 11U, 1U,
                                       master_key, sizeof(master_key)) ||
        !vos_storage_format(&f->medium, &f->store, &f->crypto, slot, 11U, 1U,
                            &geometry, &limits, 1U, 64U))
        return 0;
    f->store.committed_generation = 2U;
    if (!vos_storage_bind_resident_identity(&f->store, 7U, 19U, 1U, kind,
                                            f->bytes, sizeof(f->bytes),
                                            &tree_value, &f->identity))
        return 0;
    f->store.committed_generation = 1U;
    memset(&tx, 0, sizeof(tx));
    tx.op_kind = VOS_STORAGE_OP_INSERT;
    tx.commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE;
    tx.key = 19U;
    tx.value = tree_value;
    if (!vos_storage_reserve(&f->store, 11U, &tx) ||
        !vos_storage_stage(&f->store, 11U) ||
        !vos_storage_publish(&f->store, 11U, VOS_STORAGE_CUT_NONE, &ack_gen) ||
        ack_gen != 2U)
        return 0;
    if (!vos_resident_init(&f->owner, 1, f->identity.generation, 15, 0, 0) ||
        !vos_resident_publish(&f->owner, &f->identity, f->bytes, sizeof(f->bytes)))
        return 0;
    for (uint32_t i = 0; i < VOS_RESIDENT_HOLDERS; ++i)
        if (!vos_resident_admit(&f->owner, i, 11, &f->identity, i * 8, 16, 0, 12,
                                &f->handles[i]) ||
            !vos_resident_begin(&f->owner, &f->handles[i], 11, 0, 16, 1,
                                &f->sequences[i]))
            return 0;
    if (!vos_kernel_effect_init(&f->kernel, &vos_m8a_supervisor_manifest, 7)) return 0;
    for (uint32_t i = 0; i < f->kernel.manifest.units; ++i) {
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
    for (uint32_t i = 0; i < f->kernel.manifest.units; ++i) {
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
    if (!f->owner.common.occupied || f->owner.common.accepting ||
        memcmp(f->owner.common.bytes, f->bytes, sizeof(f->bytes)) != 0)
        return 0;
    for (uint32_t i = 0; i < VOS_RESIDENT_HOLDERS; ++i)
        if (f->owner.common.reservation[i].live || f->owner.pending[i].active)
            return 0;
    return 1;
}

static int successful(uint32_t kind)
{
    struct fixture f;
    uint8_t output[64];
    size_t length = 999;
    REQUIRE(setup(&f, kind), "setup success");
    REQUIRE(vos_resident_complete(&f.owner, &f.handles[0], 11, f.sequences[0], 1,
                                  vos_storage_verify_resident, &f.store,
                                  output, sizeof(output), &length) &&
            length == 16 && memcmp(output, f.bytes, 16) == 0,
            "authenticated storage verifier accepts resident read before retirement");
    REQUIRE(vos_resident_begin(&f.owner, &f.handles[0], 11, 0, 16, 1,
                               &f.sequences[0]),
            "holder 0 begins second read before retirement");
    length = 999;
    f.medium.checkpoint.checkpoint_mac[0] ^= 0x01U;
    REQUIRE(!vos_resident_complete(&f.owner, &f.handles[0], 11, f.sequences[0], 1,
                                   vos_storage_verify_resident, &f.store,
                                   output, sizeof(output), &length) &&
            length == 999 && f.owner.pending[0].active,
            "corrupted checkpoint MAC refuses resident read without consuming pending transfer");
    f.medium.checkpoint.checkpoint_mac[0] ^= 0x01U;
    /* A failed holder supplies no acknowledgment; the fixed kernel-owned
     * holder inventory still contains its saved and ordinary capabilities. */
    f.kernel.unit[1].running = 0;
    memset(&f.handles[0], 0, sizeof(f.handles[0]));
    const uint64_t mask = vos_resident_scalar_prepare(&f.attempt, &f.owner, &f.kernel, &f.binding);
    REQUIRE(mask == 7 && quarantined(&f), "complete holder cancellation before publication");
    REQUIRE(!vos_resident_complete(&f.owner, &f.handles[1], 11, f.sequences[1], 1,
                                   vos_storage_verify_resident, &f.store,
                                   output, sizeof(output), &length) &&
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
    for (uint32_t i = 0; i < f.kernel.manifest.units; ++i) {
        for (uint32_t n = 0; n < sizeof(f.owned[i]); ++n)
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
    for (uint32_t kind = VOS_RESIDENT_SYSTEM; kind <= VOS_RESIDENT_USER; ++kind)
        if (successful(kind) || controls(kind)) return 1;
    fprintf(stderr, "ok resident scalar actual producer, quarantine and one-attempt controls\n");
    return 0;
}
