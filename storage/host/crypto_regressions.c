// SPDX-License-Identifier: Apache-2.0
#include "vos_crypto_core.h"

#include <stdio.h>
#include <string.h>

#define CHECK(condition) do { if (!(condition)) { \
    fprintf(stderr, "crypto regression failed at %d\n", __LINE__); return 0; \
} } while (0)

static int check_cached_keys(void)
{
    const size_t lengths[] = {0u, 1u, 15u, 16u, 17u, 31u, 32u, 33u, 63u, 127u, 128u};
    uint8_t master[32];
    uint8_t input[128];
    uint8_t aad[19];
    uint8_t nonce[12] = {0};
    for (uint32_t i = 0u; i < sizeof(master); ++i) {
        master[i] = (uint8_t)(3u * i + 1u);
    }
    for (uint32_t i = 0u; i < sizeof(input); ++i) {
        input[i] = (uint8_t)(7u * i + 11u);
    }
    for (uint32_t i = 0u; i < sizeof(aad); ++i) {
        aad[i] = (uint8_t)(5u * i + 19u);
    }
    for (size_t key_bytes = 16u; key_bytes <= 32u; key_bytes += 16u) {
        struct vos_crypto_core core;
        vos_crypto_core_init(&core, 1u);
        CHECK(vos_crypto_core_unlock_domain(&core, 0u, 10u, 3u, master, key_bytes));
        uint8_t derived_key[32];
        memcpy(derived_key, core.domains[0].aead_key, sizeof(derived_key));
        memset(core.domains[0].aead_key, 0, sizeof(core.domains[0].aead_key));
        for (size_t n = 0u; n < sizeof(lengths) / sizeof(lengths[0]); ++n) {
            const size_t length = lengths[n];
            nonce[11] = (uint8_t)n;
            uint8_t raw[128];
            uint8_t cached[128];
            uint8_t opened[128];
            uint8_t raw_tag[16];
            uint8_t cached_tag[16];
            CHECK(vos_aes_gcm_encrypt(derived_key, key_bytes, nonce, sizeof(nonce),
                                      aad, sizeof(aad), input, length, raw, raw_tag));
            CHECK(vos_crypto_core_seal(&core, 0u, nonce, aad, sizeof(aad),
                                       input, length, cached, cached_tag));
            CHECK(memcmp(raw, cached, length) == 0 && memcmp(raw_tag, cached_tag, 16u) == 0);
            CHECK(vos_crypto_core_open(&core, 0u, nonce, aad, sizeof(aad),
                                       cached, length, cached_tag, opened));
            CHECK(memcmp(input, opened, length) == 0);
            cached_tag[n % sizeof(cached_tag)] ^= 1u;
            memset(opened, 0xa5, sizeof(opened));
            CHECK(!vos_crypto_core_open(&core, 0u, nonce, aad, sizeof(aad),
                                        cached, length, cached_tag, opened));
            for (size_t i = 0u; i < length; ++i) {
                CHECK(opened[i] == 0u);
            }
        }
        CHECK(vos_crypto_core_lock_domain(&core, 0u));
        const uint8_t empty[sizeof(struct vos_crypto_domain_slot)] = {0};
        CHECK(memcmp(&core.domains[0], empty, sizeof(empty)) == 0);
    }
    return 1;
}

static int check_domain_context(void)
{
    struct vos_crypto_core core;
    const uint8_t key[32] = {1u};
    const uint8_t other_key[32] = {2u};
    vos_crypto_core_init(&core, 1u);
    for (uint32_t slot = 0u; slot < VOS_CRYPTO_MAX_DOMAINS; ++slot) {
        CHECK(core.domain_context[slot] == 0u);
    }
    CHECK(!vos_crypto_core_unlock_domain(&core, 0u, 0u, 1u, key, sizeof(key)));
    CHECK(!vos_crypto_core_unlock_domain(&core, 0u, 10u, 1u, key, 17u));
    CHECK(!vos_crypto_core_unlock_domain(&core, VOS_CRYPTO_MAX_DOMAINS,
                                         10u, 1u, key, sizeof(key)));
    CHECK(core.domain_context[0] == 0u);
    CHECK(vos_crypto_core_unlock_domain(&core, 0u, 10u, 1u, key, sizeof(key)));
    CHECK(core.domain_context[0] == 1u);
    CHECK(!vos_crypto_core_unlock_domain(&core, 1u, 10u, 1u, key, sizeof(key)));
    CHECK(core.domain_context[0] == 1u && core.domain_context[1] == 0u);
    CHECK(vos_crypto_core_unlock_domain(&core, 0u, 10u, 1u, key, sizeof(key)));
    CHECK(core.domain_context[0] == 2u);
    CHECK(vos_crypto_core_lock_domain(&core, 0u));
    CHECK(core.domain_context[0] == 2u);
    CHECK(vos_crypto_core_unlock_domain(&core, 0u, 10u, 1u, other_key, sizeof(other_key)));
    CHECK(core.domain_context[0] == 3u);
    vos_crypto_core_erase_all(&core);
    CHECK(core.domain_context[0] == 3u);
    CHECK(vos_crypto_core_unlock_domain(&core, 0u, 10u, 1u, key, sizeof(key)));
    CHECK(core.domain_context[0] == 4u);
    core.domain_context[0] = UINT64_MAX - 1u;
    CHECK(vos_crypto_core_unlock_domain(&core, 0u, 10u, 1u, key, sizeof(key)));
    CHECK(core.domain_context[0] == UINT64_MAX);
    const struct vos_crypto_core before = core;
    CHECK(!vos_crypto_core_unlock_domain(&core, 0u, 10u, 1u, other_key, sizeof(other_key)));
    CHECK(memcmp(&core, &before, sizeof(core)) == 0);
    CHECK(vos_crypto_core_lock_domain(&core, 0u));
    CHECK(core.domain_context[0] == UINT64_MAX);
    CHECK(!vos_crypto_core_unlock_domain(&core, 0u, 10u, 1u, key, sizeof(key)));
    vos_crypto_core_erase_all(&core);
    CHECK(core.domain_context[0] == UINT64_MAX);
    CHECK(!vos_crypto_core_unlock_domain(&core, 0u, 10u, 1u, key, sizeof(key)));
    for (uint32_t slot = 1u; slot < VOS_CRYPTO_MAX_DOMAINS; ++slot) {
        CHECK(core.domain_context[slot] == 0u);
    }
    return 1;
}

static int check_epoch_seals(void)
{
    struct vos_crypto_core core;
    uint8_t master[32];
    uint8_t states[VOS_CRYPTO_MAX_DOMAINS][32] = {{0}};
    uint8_t roots[VOS_CRYPTO_MAX_DOMAINS][32] = {{0}};
    uint64_t epochs[VOS_CRYPTO_MAX_DOMAINS] = {0};
    for (uint32_t i = 0u; i < sizeof(master); ++i) {
        master[i] = (uint8_t)i;
    }
    vos_crypto_core_init(&core, 32u);
    for (uint32_t slot = 0u; slot < VOS_CRYPTO_MAX_DOMAINS; ++slot) {
        CHECK(vos_crypto_core_unlock_domain(&core, slot, 0x1000u + slot, 7u,
                                            master, sizeof(master)));
    }
    for (uint64_t version = 1u; version <= 8u; ++version) {
        for (uint32_t slot = 0u; slot < VOS_CRYPTO_MAX_DOMAINS; ++slot) {
            for (uint32_t i = 0u; i < sizeof(states[slot]); ++i) {
                states[slot][i] = (uint8_t)(i + slot + version);
            }
            CHECK(vos_crypto_core_seal_epoch(&core, slot, 99u + slot, version,
                                             states[slot], &epochs[slot], roots[slot]));
            if (version == 1u && slot == 0u) {
                for (size_t i = 0u; i < sizeof(roots[slot]); ++i) {
                    printf("%02x", roots[slot][i]);
                }
                putchar('\n');
            }
            for (uint32_t other = 0u; other < VOS_CRYPTO_MAX_DOMAINS; ++other) {
                if (epochs[other] == 0u) {
                    continue;
                }
                const uint64_t other_version = other <= slot ? version : version - 1u;
                CHECK(vos_crypto_core_verify_epoch(&core, other, epochs[other], 99u + other,
                                                   other_version, states[other], roots[other]));
            }
            for (size_t i = 0u; i < sizeof(states[slot]); ++i) {
                states[slot][i] ^= 1u;
                CHECK(!vos_crypto_core_verify_epoch(&core, slot, epochs[slot], 99u + slot,
                                                    version, states[slot], roots[slot]));
                states[slot][i] ^= 1u;
            }
            CHECK(!vos_crypto_core_verify_epoch(&core, slot, epochs[slot], 100u + slot,
                                                version, states[slot], roots[slot]));
            CHECK(!vos_crypto_core_verify_epoch(&core, slot, epochs[slot], 99u + slot,
                                                version + 1u, states[slot], roots[slot]));
        }
    }
    CHECK(core.rot_epoch_counter == core.rot_epoch_ceiling);
    const struct vos_crypto_core before = core;
    uint64_t epoch = UINT64_MAX;
    uint8_t root[32];
    memset(root, 0xa5, sizeof(root));
    CHECK(!vos_crypto_core_seal_epoch(&core, 0u, 99u, 9u, states[0], &epoch, root));
    CHECK(epoch == UINT64_MAX && memcmp(&core, &before, sizeof(core)) == 0);
    for (size_t i = 0u; i < sizeof(root); ++i) {
        CHECK(root[i] == 0xa5u);
    }
    CHECK(vos_crypto_core_lock_domain(&core, 0u));
    CHECK(!vos_crypto_core_unlock_domain(&core, 0u, 0x2000u, 7u, master, sizeof(master)));
    CHECK(!vos_crypto_core_unlock_domain(&core, 0u, 0x1000u, 6u, master, sizeof(master)));
    CHECK(!vos_crypto_core_unlock_domain(&core, 1u, 0x1000u, 7u, master, sizeof(master)));
    CHECK(vos_crypto_core_unlock_domain(&core, 0u, 0x1000u, 7u, master, sizeof(master)));
    CHECK(vos_crypto_core_verify_epoch(&core, 0u, epochs[0], 99u, 8u, states[0], roots[0]));
    CHECK(!vos_crypto_core_verify_epoch(&core, 0u, 1u, 99u, 1u, states[0], roots[0]));
    vos_crypto_core_erase_all(&core);
    CHECK(core.rot_epoch_counter == before.rot_epoch_counter);
    CHECK(core.epoch_sealed_mask == before.epoch_sealed_mask);
    const uint8_t empty[sizeof(struct vos_crypto_domain_slot)] = {0};
    for (uint32_t slot = 0u; slot < VOS_CRYPTO_MAX_DOMAINS; ++slot) {
        CHECK(memcmp(&core.domains[slot], empty, sizeof(empty)) == 0);
        CHECK(vos_crypto_core_unlock_domain(&core, slot, 0x1000u + slot, 7u,
                                            master, sizeof(master)));
        CHECK(vos_crypto_core_verify_epoch(&core, slot, epochs[slot], 99u + slot,
                                           8u, states[slot], roots[slot]));
    }
    return 1;
}

int main(void)
{
    return check_cached_keys() && check_domain_context() && check_epoch_seals() ? 0 : 1;
}
