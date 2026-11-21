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
    REQUIRE(renewed_length == 999u && !owner.pending[1].active && owner.common.backing[0].occupied);
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
    owner.common.backing[0].bytes[0] ^= 1u;
    REQUIRE(!vos_storage_verify_admitted_resident(&receipt, &identity,
                                                  owner.common.backing[0].bytes, sizeof(payload)));
    owner.common.backing[0].bytes[0] ^= 1u;
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

static int publish_version(struct vos_storage_store *store, uint32_t kind, uint64_t version,
                            uint32_t commit_mode,
                            const uint8_t *payload, size_t length,
                            struct vos_resident_identity *identity)
{
    struct vos_storage_store planning = *store;
    ++planning.committed_generation;
    uint64_t value = 0u;
    REQUIRE(vos_storage_bind_resident_identity(&planning, 9u, 40u, version, kind,
                                               payload, length, &value, identity));
    const struct vos_storage_tx_spec tx = {
        .op_kind = VOS_STORAGE_OP_INSERT,
        .commit_mode = commit_mode,
        .key = 40u, .value = value,
        .fresh_region_id = 1u, .fresh_region_version = version
    };
    uint64_t ack = 0u;
    REQUIRE(vos_storage_reserve(store, store->domain_id, &tx));
    REQUIRE(vos_storage_stage(store, store->domain_id));
    REQUIRE(vos_storage_publish(store, store->domain_id, VOS_STORAGE_CUT_NONE, &ack));
    REQUIRE(ack == identity->generation);
    return 1;
}

static int run_predecessor(uint32_t slot, int remove_object, uint32_t successor_mode)
{
    struct vos_crypto_core crypto;
    struct vos_storage_medium medium;
    struct vos_storage_store store;
    const struct vos_node_geometry geometry = {4u, 16u, 128u};
    const struct vos_tree_limits limits = {0u, 4u, 64u};
    const uint64_t domain = 100u + slot;
    const uint32_t kind = slot == VOS_CRYPTO_DOMAIN_SYSTEM ?
                          VOS_RESIDENT_SYSTEM : VOS_RESIDENT_USER;
    const uint8_t key[32] = {19u, 29u, 61u};
    uint8_t predecessor[64];
    uint8_t successor[64];
    for (size_t i = 0u; i < sizeof(predecessor); ++i) {
        predecessor[i] = (uint8_t)(i + 1u);
        successor[i] = (uint8_t)(200u - i);
    }
    vos_crypto_core_init(&crypto, 100u);
    REQUIRE(vos_crypto_core_unlock_domain(&crypto, slot, domain, 1u, key, sizeof(key)));
    REQUIRE(vos_storage_format(&medium, &store, &crypto, slot, domain, 1u,
                                &geometry, &limits, 1u, 100u));
    struct vos_resident_identity old;
    REQUIRE(publish_version(&store, kind, 1u, VOS_STORAGE_COMMIT_ROLLBACKABLE,
                            predecessor, sizeof(predecessor), &old));
    struct vos_storage_resident_receipt unpinned = {0};
    REQUIRE(vos_storage_admit_resident(&store, &old, predecessor, sizeof(predecessor),
                                      &unpinned));
    REQUIRE(vos_storage_retain_snapshot(&store, domain, old.generation));
    struct vos_storage_resident_receipt retained = {0};
    REQUIRE(vos_storage_admit_resident(&store, &old, predecessor, sizeof(predecessor),
                                      &retained));
    struct vos_resident_owner owner;
    struct vos_resident_handle first;
    uint64_t pending = 0u;
    REQUIRE(vos_resident_init(&owner, 1u, old.generation, 100u, NULL, NULL));
    REQUIRE(vos_resident_publish(&owner, &old, predecessor, sizeof(predecessor)));
    REQUIRE(vos_resident_admit(&owner, 0u, domain, &old, 4u, 16u, 2u, 90u, &first));
    REQUIRE(vos_resident_begin(&owner, &first, domain, 2u, 8u, 3u, &pending));

    if (remove_object) {
        const struct vos_storage_tx_spec tx = {
            .op_kind = VOS_STORAGE_OP_DELETE,
            .commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE,
            .key = old.object
        };
        uint64_t ack = 0u;
        REQUIRE(vos_storage_reserve(&store, domain, &tx));
        REQUIRE(vos_storage_stage(&store, domain));
        REQUIRE(vos_storage_publish(&store, domain, VOS_STORAGE_CUT_NONE, &ack));
        REQUIRE(ack == old.generation + 1u);
        uint8_t absent[8] = {91u};
        size_t length = 99u;
        const int released_deleted_object = vos_resident_complete(
            &owner, &first, domain, pending, 4u, vos_storage_verify_retained_resident,
            &retained, absent, sizeof(absent), &length);
        REQUIRE(!released_deleted_object);
        REQUIRE(length == 99u && absent[0] == 91u && owner.pending[0].active);
        return 1;
    }

    struct vos_resident_identity new;
    REQUIRE(publish_version(&store, kind, 2u, successor_mode, successor, sizeof(successor), &new));
    vos_resident_generation(&owner, new.generation);
    REQUIRE(vos_resident_replace(&owner, &new, successor, sizeof(successor)));
    struct vos_storage_resident_receipt current = {0};
    REQUIRE(vos_storage_admit_resident(&store, &new, successor, sizeof(successor), &current));
    struct vos_resident_handle second;
    uint64_t second_pending = 0u;
    REQUIRE(vos_resident_admit(&owner, 1u, domain, &new, 12u, 16u, 4u, 90u, &second));
    REQUIRE(vos_resident_begin(&owner, &second, domain, 2u, 8u, 4u, &second_pending));

    REQUIRE(!vos_storage_verify_admitted_resident(&retained, &old, predecessor,
                                                   sizeof(predecessor)));
    REQUIRE(!vos_storage_verify_retained_resident(&unpinned, &old, predecessor,
                                                   sizeof(predecessor)));
    REQUIRE(!vos_storage_verify_retained_resident(&retained, &old, successor,
                                                   sizeof(successor)));
    retained.checkpoint.checkpoint_mac[0] ^= 1u;
    const int old_mac_valid = vos_storage_verify_retained_resident(
        &retained, &old, predecessor, sizeof(predecessor));
    REQUIRE(!old_mac_valid);
    retained.checkpoint.checkpoint_mac[0] ^= 1u;
    medium.checkpoint.checkpoint_mac[0] ^= 1u;
    REQUIRE(!vos_storage_verify_retained_resident(&retained, &old, predecessor,
                                                   sizeof(predecessor)));
    medium.checkpoint.checkpoint_mac[0] ^= 1u;

    uint8_t output[8] = {91u};
    size_t length = 99u;
    if (kind == VOS_RESIDENT_USER && successor_mode == VOS_STORAGE_COMMIT_ROLLBACKABLE) {
        owner.common.backing[0].bytes[0] ^= 1u;
        REQUIRE(!vos_resident_complete(&owner, &first, domain, pending, 5u,
                                        vos_storage_verify_retained_resident, &retained,
                                        output, sizeof(output), &length));
        REQUIRE(length == 99u && output[0] == 91u && owner.pending[0].active);
        owner.common.backing[0].bytes[0] ^= 1u;
        const struct vos_resident_common common = owner.common;
        for (size_t n = 0u; n < 8u; ++n) {
            REQUIRE(vos_resident_complete(&owner, &first, domain, pending, 5u + 2u * n,
                                           vos_storage_verify_retained_resident, &retained,
                                           output, sizeof(output), &length));
            REQUIRE(length == sizeof(output) &&
                     memcmp(output, predecessor + 6u, length) == 0);
            REQUIRE(vos_resident_begin(&owner, &first, domain, 2u, 8u, 6u + 2u * n, &pending));
        }
        REQUIRE(memcmp(&owner.common, &common, sizeof(common)) == 0);
    } else {
        const int invalid_predecessor = vos_storage_verify_retained_resident(
            &retained, &old, predecessor, sizeof(predecessor));
        REQUIRE(!invalid_predecessor);
        REQUIRE(!vos_resident_complete(&owner, &first, domain, pending, 5u,
                                        vos_storage_verify_retained_resident, &retained,
                                        output, sizeof(output), &length));
        REQUIRE(length == 99u && output[0] == 91u && owner.pending[0].active);
    }
    REQUIRE(!vos_resident_retire_predecessor(&owner, &old, 0));
    REQUIRE(!owner.pending[0].active && owner.common.backing[0].occupied &&
             !owner.common.backing[0].accepting && owner.pending[1].active);
    REQUIRE(vos_resident_complete(&owner, &second, domain, second_pending, 22u,
                                   vos_storage_verify_retained_resident, &current,
                                   output, sizeof(output), &length));
    REQUIRE(length == sizeof(output) && memcmp(output, successor + 14u, length) == 0);
    REQUIRE(vos_resident_retire_predecessor(&owner, &old, 1));
    REQUIRE(!owner.common.backing[0].occupied && owner.common.backing[1].occupied);
    REQUIRE(vos_resident_begin(&owner, &second, domain, 2u, 8u, 23u, &second_pending));
    REQUIRE(vos_resident_crash(&owner, 2u));
    REQUIRE(vos_storage_reopen(&medium, &store, &crypto, slot, domain));
    length = 99u;
    REQUIRE(!vos_resident_complete(&owner, &second, domain, second_pending, 24u,
                                    vos_storage_verify_retained_resident, &current,
                                    output, sizeof(output), &length));
    REQUIRE(length == 99u && !owner.pending[1].active && owner.common.backing[1].occupied);
    return 1;
}

int main(void)
{
    if (!run_domain(VOS_CRYPTO_DOMAIN_SYSTEM) || !run_domain(VOS_CRYPTO_DOMAIN_USER)) return 1;
    if (!run_predecessor(VOS_CRYPTO_DOMAIN_SYSTEM, 0, VOS_STORAGE_COMMIT_ROLLBACKABLE) ||
        !run_predecessor(VOS_CRYPTO_DOMAIN_USER, 0, VOS_STORAGE_COMMIT_ROLLBACKABLE) ||
        !run_predecessor(VOS_CRYPTO_DOMAIN_USER, 0, VOS_STORAGE_COMMIT_FRESH) ||
        !run_predecessor(VOS_CRYPTO_DOMAIN_USER, 1, VOS_STORAGE_COMMIT_ROLLBACKABLE)) return 1;
    puts("resident receipt: ok");
    return 0;
}
