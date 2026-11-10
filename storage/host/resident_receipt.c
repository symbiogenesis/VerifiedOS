// SPDX-License-Identifier: Apache-2.0
#include "vos_storage_publish.h"

#include <stdio.h>
#include <string.h>

#define REQUIRE(p) do { if (!(p)) { \
    fprintf(stderr, "resident receipt failed at %d: %s\n", __LINE__, #p); return 0; \
} } while (0)

static int run_domain(uint32_t slot)
{
    struct vos_crypto_core crypto;
    struct vos_storage_medium medium;
    struct vos_storage_store store;
    const struct vos_node_geometry geometry = {4u, 16u, 128u};
    const struct vos_tree_limits limits = {0u, 4u, 64u};
    const uint64_t domain = 100u + slot;
    const uint32_t kind = slot == VOS_CRYPTO_DOMAIN_SYSTEM ?
                          VOS_RESIDENT_SYSTEM : VOS_RESIDENT_USER;
    uint8_t key[32];
    uint8_t payload[64];
    for (size_t i = 0; i < sizeof(key); ++i) key[i] = (uint8_t)(i + slot);
    for (size_t i = 0; i < sizeof(payload); ++i) payload[i] = (uint8_t)(3u * i);
    vos_crypto_core_init(&crypto, 100u);
    REQUIRE(vos_crypto_core_unlock_domain(&crypto, slot, domain, 1u, key, sizeof(key)));
    REQUIRE(vos_storage_format(&medium, &store, &crypto, slot, domain, 1u,
                                &geometry, &limits, 1u, 100u));
    struct vos_storage_store planning = store;
    planning.committed_generation = 2u;
    struct vos_resident_identity identity;
    uint64_t value = 0u;
    REQUIRE(vos_storage_bind_resident_identity(&planning, 9u, 40u, 1u, kind,
                                               payload, sizeof(payload), &value, &identity));
    struct vos_storage_tx_spec tx = {
        .op_kind = VOS_STORAGE_OP_INSERT,
        .commit_mode = VOS_STORAGE_COMMIT_FRESH,
        .key = 40u, .value = value,
        .fresh_region_id = 1u, .fresh_region_version = 1u
    };
    uint64_t ack = 0u;
    REQUIRE(vos_storage_reserve(&store, domain, &tx));
    REQUIRE(vos_storage_stage(&store, domain));
    REQUIRE(vos_storage_publish(&store, domain, VOS_STORAGE_CUT_NONE, &ack));
    struct vos_storage_resident_receipt receipt = {0};
    payload[0] ^= 1u;
    REQUIRE(!vos_storage_admit_resident(&store, &identity, payload, sizeof(payload), &receipt));
    REQUIRE(receipt.valid == 0u);
    payload[0] ^= 1u;
    REQUIRE(vos_storage_admit_resident(&store, &identity, payload, sizeof(payload), &receipt));
    const struct vos_storage_resident_receipt before = receipt;
    struct vos_resident_owner owner;
    REQUIRE(vos_resident_init(&owner, 1u, 2u, 100u, NULL, NULL));
    REQUIRE(vos_resident_publish(&owner, &identity, payload, sizeof(payload)));
    struct vos_resident_handle handles[VOS_RESIDENT_HOLDERS];
    for (uint32_t h = 0; h < VOS_RESIDENT_HOLDERS; ++h)
        REQUIRE(vos_resident_admit(&owner, h, domain, &identity, 8u * h, 32u,
                                   1u, h == 0 ? 4u : 90u, &handles[h]));
    uint64_t pending[VOS_RESIDENT_HOLDERS] = {0};
    for (uint32_t h = 0; h < VOS_RESIDENT_HOLDERS; ++h)
        REQUIRE(vos_resident_begin(&owner, &handles[h], domain, 3u, 16u,
                                   2u, &pending[h]));
    REQUIRE(vos_resident_renew(&owner, &handles[0], domain, 2u, 95u));
    uint8_t renewed_output[16] = {0};
    size_t renewed_length = 0;
    REQUIRE(vos_resident_complete(&owner, &handles[0], domain, pending[0], 5u,
                                  vos_storage_verify_admitted_resident, &receipt,
                                  renewed_output, sizeof(renewed_output), &renewed_length));
    REQUIRE(renewed_length == sizeof(renewed_output) &&
            memcmp(renewed_output, payload + 3u, renewed_length) == 0);
    const struct vos_resident_handle closed = handles[1];
    REQUIRE(vos_resident_close(&owner, &closed, domain));
    renewed_length = 999u;
    REQUIRE(!vos_resident_complete(&owner, &closed, domain, pending[1], 5u,
                                   vos_storage_verify_admitted_resident, &receipt,
                                   renewed_output, sizeof(renewed_output), &renewed_length));
    REQUIRE(renewed_length == 999u && !owner.pending[1].active && owner.common.occupied);
    REQUIRE(vos_resident_admit(&owner, 1u, domain, &identity, 8u, 32u,
                               5u, 90u, &handles[1]));
    REQUIRE(handles[1].token > closed.token &&
            !vos_resident_close(&owner, &closed, domain) &&
            !vos_resident_renew(&owner, &closed, domain, 5u, 95u));
    const struct vos_resident_common common = owner.common;
    for (uint32_t n = 0; n < 24u; ++n) {
        const uint32_t h = n % VOS_RESIDENT_HOLDERS;
        uint64_t sequence = 0u;
        uint8_t output[16] = {0};
        size_t length = 0u;
        REQUIRE(vos_resident_begin(&owner, &handles[h], domain, 3u, sizeof(output),
                                   6u, &sequence));
        REQUIRE(vos_resident_complete(&owner, &handles[h], domain, sequence, 7u,
                                      vos_storage_verify_admitted_resident, &receipt,
                                      output, sizeof(output), &length));
        REQUIRE(length == sizeof(output) &&
                 memcmp(output, payload + 8u * h + 3u, length) == 0);
    }
    REQUIRE(memcmp(&owner.common, &common, sizeof(common)) == 0);
    REQUIRE(memcmp(&receipt, &before, sizeof(receipt)) == 0);
    owner.common.bytes[0] ^= 1u;
    REQUIRE(!vos_storage_verify_admitted_resident(&receipt, &identity,
                                                  owner.common.bytes, sizeof(payload)));
    owner.common.bytes[0] ^= 1u;
    medium.arena_ciphertext[medium.checkpoint.root * geometry.block_bytes] ^= 1u;
    REQUIRE(!vos_storage_verify_resident(&store, &identity, payload, sizeof(payload)));
    REQUIRE(vos_storage_verify_admitted_resident(&receipt, &identity, payload, sizeof(payload)));
    medium.arena_ciphertext[medium.checkpoint.root * geometry.block_bytes] ^= 1u;
    medium.checkpoint.checkpoint_mac[0] ^= 1u;
    REQUIRE(!vos_storage_verify_admitted_resident(&receipt, &identity, payload, sizeof(payload)));
    medium.checkpoint.checkpoint_mac[0] ^= 1u;
    identity.object ^= 1u;
    REQUIRE(!vos_storage_verify_admitted_resident(&receipt, &identity, payload, sizeof(payload)));
    identity.object ^= 1u;
    REQUIRE(vos_crypto_core_lock_domain(&crypto, slot));
    REQUIRE(!vos_storage_verify_admitted_resident(&receipt, &identity, payload, sizeof(payload)));
    REQUIRE(vos_crypto_core_unlock_domain(&crypto, slot, domain, 1u, key, sizeof(key)));
    REQUIRE(!vos_storage_verify_admitted_resident(&receipt, &identity, payload, sizeof(payload)));
    REQUIRE(vos_storage_admit_resident(&store, &identity, payload, sizeof(payload), &receipt));
    REQUIRE(vos_storage_verify_admitted_resident(&receipt, &identity, payload, sizeof(payload)));
    uint64_t epoch = 0u;
    uint8_t epoch_root[VOS_CRYPTO_DIGEST_BYTES];
    REQUIRE(vos_crypto_core_seal_epoch(&crypto, slot, 1u, 2u,
                                       medium.checkpoint.root_digest, &epoch, epoch_root));
    REQUIRE(!vos_storage_verify_admitted_resident(&receipt, &identity, payload, sizeof(payload)));
    return 1;
}

int main(void)
{
    if (!run_domain(VOS_CRYPTO_DOMAIN_SYSTEM) || !run_domain(VOS_CRYPTO_DOMAIN_USER)) return 1;
    puts("resident receipt: ok");
    return 0;
}
