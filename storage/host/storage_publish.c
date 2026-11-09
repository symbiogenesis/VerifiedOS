// SPDX-License-Identifier: Apache-2.0
#include "vos_storage_publish.h"

#include <stdio.h>
#include <string.h>

#if defined(VOS_STORAGE_COUNT_CHECKPOINT_MACS)
static uint64_t checkpoint_mac_checks;

int __real_vos_crypto_core_verify_commit_mac(
    const struct vos_crypto_core *core, uint32_t slot,
    const uint8_t *record, size_t length,
    const uint8_t expected[VOS_CRYPTO_DIGEST_BYTES]);

int __wrap_vos_crypto_core_verify_commit_mac(
    const struct vos_crypto_core *core, uint32_t slot,
    const uint8_t *record, size_t length,
    const uint8_t expected[VOS_CRYPTO_DIGEST_BYTES])
{
    ++checkpoint_mac_checks;
    return __real_vos_crypto_core_verify_commit_mac(core, slot, record, length, expected);
}
#endif

static int check_crypto_primitives(void)
{
    /* FIPS 180-4 single-block ("abc") and two-block SHA-256 vectors. */
    static const uint8_t abc[3] = {0x61u, 0x62u, 0x63u};
    static const uint8_t abc_sha256[32] = {
        0xbau, 0x78u, 0x16u, 0xbfu, 0x8fu, 0x01u, 0xcfu, 0xeau,
        0x41u, 0x41u, 0x40u, 0xdeu, 0x5du, 0xaeu, 0x22u, 0x23u,
        0xb0u, 0x03u, 0x61u, 0xa3u, 0x96u, 0x17u, 0x7au, 0x9cu,
        0xb4u, 0x10u, 0xffu, 0x61u, 0xf2u, 0x00u, 0x15u, 0xadu
    };
    static const char two_block_msg[] =
        "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq";
    static const uint8_t two_block_sha256[32] = {
        0x24u, 0x8du, 0x6au, 0x61u, 0xd2u, 0x06u, 0x38u, 0xb8u,
        0xe5u, 0xc0u, 0x26u, 0x93u, 0x0cu, 0x3eu, 0x60u, 0x39u,
        0xa3u, 0x3cu, 0xe4u, 0x59u, 0x64u, 0xffu, 0x21u, 0x67u,
        0xf6u, 0xecu, 0xedu, 0xd4u, 0x19u, 0xdbu, 0x06u, 0xc1u
    };
    uint8_t digest[32] = {0};
    if (!vos_sha256(abc, sizeof(abc), digest) ||
        memcmp(digest, abc_sha256, 32u) != 0) {
        return 0;
    }
    if (!vos_sha256((const uint8_t *)two_block_msg, 56u, digest) ||
        memcmp(digest, two_block_sha256, 32u) != 0) {
        return 0;
    }

    /* RFC 4231 Test Case 1 HMAC-SHA-256 vector. */
    uint8_t hmac_key[20];
    memset(hmac_key, 0x0bu, sizeof(hmac_key));
    static const uint8_t hmac_msg[8] = {'H', 'i', ' ', 'T', 'h', 'e', 'r', 'e'};
    static const uint8_t hmac_expected[32] = {
        0xb0u, 0x34u, 0x4cu, 0x61u, 0xd8u, 0xdbu, 0x38u, 0x53u,
        0x5cu, 0xa8u, 0xafu, 0xceu, 0xafu, 0x0bu, 0xf1u, 0x2bu,
        0x88u, 0x1du, 0xc2u, 0x00u, 0xc9u, 0x83u, 0x3du, 0xa7u,
        0x26u, 0xe9u, 0x37u, 0x6cu, 0x2eu, 0x32u, 0xcfu, 0xf7u
    };
    if (!vos_hmac_sha256(hmac_key, sizeof(hmac_key), hmac_msg, sizeof(hmac_msg), digest) ||
        memcmp(digest, hmac_expected, 32u) != 0) {
        return 0;
    }

    /* FIPS 197 Appendix C.1 (AES-128), C.2 (AES-192), C.3 (AES-256) vectors. */
    uint8_t seq_key[32];
    for (uint32_t i = 0u; i < 32u; ++i) {
        seq_key[i] = (uint8_t)i;
    }
    static const uint8_t c_plain[16] = {
        0x00u, 0x11u, 0x22u, 0x33u, 0x44u, 0x55u, 0x66u, 0x77u,
        0x88u, 0x99u, 0xaau, 0xbbu, 0xccu, 0xddu, 0xeeu, 0xffu
    };
    static const uint8_t c1_cipher[16] = {
        0x69u, 0xc4u, 0xe0u, 0xd8u, 0x6au, 0x7bu, 0x04u, 0x30u,
        0xd8u, 0xcdu, 0xb7u, 0x80u, 0x70u, 0xb4u, 0xc5u, 0x5au
    };
    static const uint8_t c2_cipher[16] = {
        0xddu, 0xa9u, 0x7cu, 0xa4u, 0x86u, 0x4cu, 0xdfu, 0xe0u,
        0x6eu, 0xafu, 0x70u, 0xa0u, 0xecu, 0x0du, 0x71u, 0x91u
    };
    static const uint8_t c3_cipher[16] = {
        0x8eu, 0xa2u, 0xb7u, 0xcau, 0x51u, 0x67u, 0x45u, 0xbfu,
        0xeau, 0xfcu, 0x49u, 0x90u, 0x4bu, 0x49u, 0x60u, 0x89u
    };
    uint8_t blk_out[16] = {0};
    uint8_t blk_dec[16] = {0};
    if (!vos_aes_encrypt_block(seq_key, 16u, c_plain, blk_out) ||
        memcmp(blk_out, c1_cipher, 16u) != 0 ||
        !vos_aes_decrypt_block(seq_key, 16u, blk_out, blk_dec) ||
        memcmp(blk_dec, c_plain, 16u) != 0) {
        return 0;
    }
    if (!vos_aes_encrypt_block(seq_key, 24u, c_plain, blk_out) ||
        memcmp(blk_out, c2_cipher, 16u) != 0 ||
        !vos_aes_decrypt_block(seq_key, 24u, blk_out, blk_dec) ||
        memcmp(blk_dec, c_plain, 16u) != 0) {
        return 0;
    }
    if (!vos_aes_encrypt_block(seq_key, 32u, c_plain, blk_out) ||
        memcmp(blk_out, c3_cipher, 16u) != 0 ||
        !vos_aes_decrypt_block(seq_key, 32u, blk_out, blk_dec) ||
        memcmp(blk_dec, c_plain, 16u) != 0) {
        return 0;
    }

    /* NIST SP 800-38D GCM cases 1, 2, 4, and 5 (matching proofs/AesGcm.v). */
    uint8_t zero_key[16] = {0};
    uint8_t zero_iv[12] = {0};
    uint8_t zero_plain[16] = {0};
    uint8_t tag[16] = {0};
    static const uint8_t gcm_case1_tag[16] = {
        0x58u, 0xe2u, 0xfcu, 0xceu, 0xfau, 0x7eu, 0x30u, 0x61u,
        0x36u, 0x7fu, 0x1du, 0x57u, 0xa4u, 0xe7u, 0x45u, 0x5au
    };
    static const uint8_t gcm_case2_cipher[16] = {
        0x03u, 0x88u, 0xdau, 0xceu, 0x60u, 0xb6u, 0xa3u, 0x92u,
        0xf3u, 0x28u, 0xc2u, 0xb9u, 0x71u, 0xb2u, 0xfeu, 0x78u
    };
    static const uint8_t gcm_case2_tag[16] = {
        0xabu, 0x6eu, 0x47u, 0xd4u, 0x2cu, 0xecu, 0x13u, 0xbdu,
        0xf5u, 0x3au, 0x67u, 0xb2u, 0x12u, 0x57u, 0xbdu, 0xdfu
    };
    if (!vos_aes_gcm_encrypt(zero_key, 16u, zero_iv, 12u, NULL, 0u,
                             NULL, 0u, NULL, tag) ||
        memcmp(tag, gcm_case1_tag, 16u) != 0) {
        return 0;
    }
    if (!vos_aes_gcm_encrypt(zero_key, 16u, zero_iv, 12u, NULL, 0u,
                             zero_plain, 16u, blk_out, tag) ||
        memcmp(blk_out, gcm_case2_cipher, 16u) != 0 ||
        memcmp(tag, gcm_case2_tag, 16u) != 0 ||
        !vos_aes_gcm_open(zero_key, 16u, zero_iv, 12u, NULL, 0u,
                          blk_out, 16u, tag, blk_dec) ||
        memcmp(blk_dec, zero_plain, 16u) != 0) {
        return 0;
    }

    static const uint8_t gcm_key4[16] = {
        0xfeu, 0xffu, 0xe9u, 0x92u, 0x86u, 0x65u, 0x73u, 0x1cu,
        0x6du, 0x6au, 0x8fu, 0x94u, 0x67u, 0x30u, 0x83u, 0x08u
    };
    static const uint8_t gcm_iv4[12] = {
        0xcau, 0xfeu, 0xbau, 0xbeu, 0xfau, 0xceu, 0xdbu, 0xadu,
        0xdeu, 0xcau, 0xf8u, 0x88u
    };
    static const uint8_t gcm_aad4[20] = {
        0xfeu, 0xedu, 0xfau, 0xceu, 0xdeu, 0xadu, 0xbeu, 0xefu,
        0xfeu, 0xedu, 0xfau, 0xceu, 0xdeu, 0xadu, 0xbeu, 0xefu,
        0xabu, 0xadu, 0xdau, 0xd2u
    };
    static const uint8_t gcm_plain4[60] = {
        0xd9u, 0x31u, 0x32u, 0x25u, 0xf8u, 0x84u, 0x06u, 0xe5u,
        0xa5u, 0x59u, 0x09u, 0xc5u, 0xafu, 0xf5u, 0x26u, 0x9au,
        0x86u, 0xa7u, 0xa9u, 0x53u, 0x15u, 0x34u, 0xf7u, 0xdau,
        0x2eu, 0x4cu, 0x30u, 0x3du, 0x8au, 0x31u, 0x8au, 0x72u,
        0x1cu, 0x3cu, 0x0cu, 0x95u, 0x95u, 0x68u, 0x09u, 0x53u,
        0x2fu, 0xcfu, 0x0eu, 0x24u, 0x49u, 0xa6u, 0xb5u, 0x25u,
        0xb1u, 0x6au, 0xedu, 0xf5u, 0xaau, 0x0du, 0xe6u, 0x57u,
        0xbau, 0x63u, 0x7bu, 0x39u
    };
    static const uint8_t gcm_cipher4[60] = {
        0x42u, 0x83u, 0x1eu, 0xc2u, 0x21u, 0x77u, 0x74u, 0x24u,
        0x4bu, 0x72u, 0x21u, 0xb7u, 0x84u, 0xd0u, 0xd4u, 0x9cu,
        0xe3u, 0xaau, 0x21u, 0x2fu, 0x2cu, 0x02u, 0xa4u, 0xe0u,
        0x35u, 0xc1u, 0x7eu, 0x23u, 0x29u, 0xacu, 0xa1u, 0x2eu,
        0x21u, 0xd5u, 0x14u, 0xb2u, 0x54u, 0x66u, 0x93u, 0x1cu,
        0x7du, 0x8fu, 0x6au, 0x5au, 0xacu, 0x84u, 0xaau, 0x05u,
        0x1bu, 0xa3u, 0x0bu, 0x39u, 0x6au, 0x0au, 0xacu, 0x97u,
        0x3du, 0x58u, 0xe0u, 0x91u
    };
    static const uint8_t gcm_tag4[16] = {
        0x5bu, 0xc9u, 0x4fu, 0xbcu, 0x32u, 0x21u, 0xa5u, 0xdbu,
        0x94u, 0xfau, 0xe9u, 0x5au, 0xe7u, 0x12u, 0x1au, 0x47u
    };
    static const uint8_t gcm_tag5[16] = {
        0x36u, 0x12u, 0xd2u, 0xe7u, 0x9eu, 0x3bu, 0x07u, 0x85u,
        0x56u, 0x1bu, 0xe1u, 0x4au, 0xacu, 0xa2u, 0xfcu, 0xcbu
    };
    uint8_t cipher60[60] = {0};
    uint8_t plain60[60] = {0};
    if (!vos_aes_gcm_encrypt(gcm_key4, 16u, gcm_iv4, 12u, gcm_aad4, 20u,
                             gcm_plain4, 60u, cipher60, tag) ||
        memcmp(cipher60, gcm_cipher4, 60u) != 0 ||
        memcmp(tag, gcm_tag4, 16u) != 0 ||
        !vos_aes_gcm_open(gcm_key4, 16u, gcm_iv4, 12u, gcm_aad4, 20u,
                          cipher60, 60u, tag, plain60) ||
        memcmp(plain60, gcm_plain4, 60u) != 0) {
        return 0;
    }
    /* Flip one tag bit: open must refuse and zero plaintext. */
    tag[0] ^= 1u;
    memset(plain60, 0xa5u, sizeof(plain60));
    if (vos_aes_gcm_open(gcm_key4, 16u, gcm_iv4, 12u, gcm_aad4, 20u,
                         cipher60, 60u, tag, plain60)) {
        return 0;
    }
    for (size_t i = 0u; i < sizeof(plain60); ++i) {
        if (plain60[i] != 0u) {
            return 0;
        }
    }
    /* Case 5: 64-bit IV exercises the GHASH J0 arm. */
    if (!vos_aes_gcm_encrypt(gcm_key4, 16u, gcm_iv4, 8u, gcm_aad4, 20u,
                             gcm_plain4, 60u, cipher60, tag) ||
        memcmp(tag, gcm_tag5, 16u) != 0) {
        return 0;
    }
    return 1;
}

static int check_compartment_domains_and_bfu(void)
{
    struct vos_crypto_core core;
    uint8_t master_key[32];
    uint8_t nonce[12] = {1u, 2u, 3u, 4u, 5u, 6u, 7u, 8u, 9u, 10u, 11u, 12u};
    uint8_t plain[32] = "shared-payload-across-instances";
    uint8_t cipher[32] = {0};
    uint8_t opened[32] = {0};
    uint8_t tag[16] = {0};
    uint8_t sys_digest1[32] = {0};
    uint8_t sys_digest2[32] = {0};
    uint8_t usr_digest[32] = {0};

    for (uint32_t i = 0u; i < 32u; ++i) {
        master_key[i] = (uint8_t)(0x40u + i);
    }
    vos_crypto_core_init(&core, 16u);

    /* R-10-032: Before First Unlock holds no key; seal/open/digest must refuse. */
    if (vos_crypto_core_seal(&core, VOS_CRYPTO_DOMAIN_USER, nonce, NULL, 0u,
                             plain, sizeof(plain), cipher, tag) ||
        vos_crypto_core_keyed_digest(&core, VOS_CRYPTO_DOMAIN_USER,
                                     plain, sizeof(plain), usr_digest)) {
        return 0;
    }

    if (!vos_crypto_core_unlock_domain(&core, VOS_CRYPTO_DOMAIN_SYSTEM,
                                       0x1001ULL, 1u, master_key, 32u) ||
        !vos_crypto_core_unlock_domain(&core, VOS_CRYPTO_DOMAIN_USER,
                                       0x2002ULL, 1u, master_key, 32u)) {
        return 0;
    }

    /* R-10-016: deterministic within a domain, incomparable across domains. */
    if (!vos_crypto_core_keyed_digest(&core, VOS_CRYPTO_DOMAIN_SYSTEM,
                                      plain, sizeof(plain), sys_digest1) ||
        !vos_crypto_core_keyed_digest(&core, VOS_CRYPTO_DOMAIN_SYSTEM,
                                      plain, sizeof(plain), sys_digest2) ||
        !vos_crypto_core_keyed_digest(&core, VOS_CRYPTO_DOMAIN_USER,
                                      plain, sizeof(plain), usr_digest) ||
        memcmp(sys_digest1, sys_digest2, 32u) != 0 ||
        memcmp(sys_digest1, usr_digest, 32u) == 0) {
        return 0;
    }

    /* Cross-domain open of ciphertext sealed in another domain must refuse. */
    if (!vos_crypto_core_seal(&core, VOS_CRYPTO_DOMAIN_USER, nonce,
                              plain, 8u, plain, sizeof(plain), cipher, tag) ||
        vos_crypto_core_open(&core, VOS_CRYPTO_DOMAIN_SYSTEM, nonce,
                             plain, 8u, cipher, sizeof(plain), tag, opened) ||
        !vos_crypto_core_open(&core, VOS_CRYPTO_DOMAIN_USER, nonce,
                              plain, 8u, cipher, sizeof(plain), tag, opened) ||
        memcmp(opened, plain, sizeof(plain)) != 0) {
        return 0;
    }

    /* R-10-014 / R-10-032: lock/crypto-erase zeroizes domain keys and refuses open. */
    if (!vos_crypto_core_lock_domain(&core, VOS_CRYPTO_DOMAIN_USER) ||
        vos_crypto_core_open(&core, VOS_CRYPTO_DOMAIN_USER, nonce,
                             plain, 8u, cipher, sizeof(plain), tag, opened) ||
        vos_crypto_core_keyed_digest(&core, VOS_CRYPTO_DOMAIN_USER,
                                     plain, sizeof(plain), usr_digest)) {
        return 0;
    }
    return 1;
}

static int apply_commit(struct vos_storage_store *store,
                        uint64_t domain_id,
                        const struct vos_storage_tx_spec *spec,
                        uint64_t *ack_out)
{
    return vos_storage_reserve(store, domain_id, spec) &&
           vos_storage_stage(store, domain_id) &&
           vos_storage_publish(store, domain_id, VOS_STORAGE_CUT_NONE, ack_out);
}

static int check_publish_lifecycle_and_cuts(void)
{
    const struct vos_node_geometry geometry = {
        .fan = 4u,
        .block_bytes = 96u,
        .arena_nodes = 32u
    };
    const struct vos_tree_limits limits = {
        .height = 0u,
        .depth_limit = 6u,
        .visit_limit = 32u
    };
    const uint64_t sys_domain = 0x53595331ULL;
    uint8_t master_key[32];
    for (uint32_t i = 0u; i < 32u; ++i) {
        master_key[i] = (uint8_t)(0x10u + i);
    }

    struct vos_crypto_core crypto;
    struct vos_storage_medium medium;
    struct vos_storage_store store;
    vos_crypto_core_init(&crypto, 8u);
    if (!vos_crypto_core_unlock_domain(&crypto, VOS_CRYPTO_DOMAIN_SYSTEM,
                                       sys_domain, 3u, master_key, 32u)) {
        return 0;
    }
    if (!vos_storage_format(&medium, &store, &crypto, VOS_CRYPTO_DOMAIN_SYSTEM,
                            sys_domain, 3u, &geometry, &limits, 1u, 12u)) {
        return 0;
    }

    /* Commit a sorted batch of 6 entries (splits root leaf into branch + leaves). */
    struct vos_storage_tx_spec batch_tx = {0};
    batch_tx.op_kind = VOS_STORAGE_OP_INSERT_BATCH;
    batch_tx.commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE;
    batch_tx.entry_count = 6u;
    for (size_t i = 0u; i < 6u; ++i) {
        batch_tx.entries[i].key = (uint64_t)(i + 1u) * 10u;
        batch_tx.entries[i].value = (uint64_t)(i + 1u) * 100u;
    }
    uint64_t ack_gen = 0u;
    if (!apply_commit(&store, sys_domain, &batch_tx, &ack_gen) ||
        ack_gen != 2u || store.committed_height == 0u) {
        return 0;
    }
    const struct vos_storage_nonce_record saved_nonce_gen2 = medium.nonce_record;
    const struct vos_storage_checkpoint checkpoint_gen2 = medium.checkpoint;
    for (size_t i = 0u; i < 6u; ++i) {
        uint64_t val = 0u;
        if (vos_storage_lookup(&store, sys_domain, (uint64_t)(i + 1u) * 10u, &val) !=
                VOS_TREE_FOUND ||
            val != (uint64_t)(i + 1u) * 100u) {
            return 0;
        }
    }

    /* Cut 1: VOS_STORAGE_CUT_AFTER_RESERVE preserves nonce advance across Reopen. */
    struct vos_storage_tx_spec ins_tx = {
        .op_kind = VOS_STORAGE_OP_INSERT,
        .commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE,
        .key = 70u,
        .value = 700u
    };
    if (!vos_storage_reserve(&store, sys_domain, &ins_tx) ||
        medium.nonce_record.reserved_generation != 3u ||
        vos_storage_publish(&store, sys_domain, VOS_STORAGE_CUT_AFTER_RESERVE, &ack_gen)) {
        return 0;
    }
    if (!vos_storage_reopen(&medium, &store, &crypto, VOS_CRYPTO_DOMAIN_SYSTEM, sys_domain) ||
        store.committed_generation != 2u ||
        medium.nonce_record.reserved_generation != 3u) {
        return 0;
    }
    uint64_t probe = 0u;
    if (vos_storage_lookup(&store, sys_domain, 70u, &probe) != VOS_TREE_MISSING) {
        return 0;
    }

    /* Cut 2: VOS_STORAGE_CUT_MID_PAYLOAD discards partial uncommitted journal suffix. */
    if (!vos_storage_reserve(&store, sys_domain, &ins_tx) ||
        store.attempt.generation != 4u ||
        !vos_storage_stage(&store, sys_domain) ||
        vos_storage_publish(&store, sys_domain, VOS_STORAGE_CUT_MID_PAYLOAD, &ack_gen)) {
        return 0;
    }
    if (!vos_storage_reopen(&medium, &store, &crypto, VOS_CRYPTO_DOMAIN_SYSTEM, sys_domain) ||
        store.committed_generation != 2u ||
        medium.nonce_record.reserved_generation != 4u ||
        vos_storage_lookup(&store, sys_domain, 70u, &probe) != VOS_TREE_MISSING) {
        return 0;
    }

    /* Cut 3: VOS_STORAGE_CUT_BEFORE_CHECKPOINT discards uncheckpointed journal frames. */
    if (!vos_storage_reserve(&store, sys_domain, &ins_tx) ||
        store.attempt.generation != 5u ||
        !vos_storage_stage(&store, sys_domain) ||
        vos_storage_publish(&store, sys_domain, VOS_STORAGE_CUT_BEFORE_CHECKPOINT, &ack_gen)) {
        return 0;
    }
    if (!vos_storage_reopen(&medium, &store, &crypto, VOS_CRYPTO_DOMAIN_SYSTEM, sys_domain) ||
        store.committed_generation != 2u ||
        medium.nonce_record.reserved_generation != 5u ||
        vos_storage_lookup(&store, sys_domain, 70u, &probe) != VOS_TREE_MISSING) {
        return 0;
    }

    /* Cut 4: VOS_STORAGE_CUT_BEFORE_EPOCH_SEAL loses unsealed Fresh write (R-10-013c). */
    struct vos_storage_tx_spec fresh_tx = {
        .op_kind = VOS_STORAGE_OP_INSERT,
        .commit_mode = VOS_STORAGE_COMMIT_FRESH,
        .key = 70u,
        .value = 700u,
        .fresh_region_id = 9u,
        .fresh_region_version = 1u
    };
    if (!vos_storage_reserve(&store, sys_domain, &fresh_tx) ||
        store.attempt.generation != 6u ||
        !vos_storage_stage(&store, sys_domain) ||
        vos_storage_publish(&store, sys_domain, VOS_STORAGE_CUT_BEFORE_EPOCH_SEAL, &ack_gen)) {
        return 0;
    }
    if (crypto.rot_epoch_counter != 0u ||
        !vos_storage_reopen(&medium, &store, &crypto, VOS_CRYPTO_DOMAIN_SYSTEM, sys_domain) ||
        store.committed_generation != 2u ||
        vos_storage_lookup(&store, sys_domain, 70u, &probe) != VOS_TREE_MISSING) {
        return 0;
    }

    /* Cut 5: VOS_STORAGE_CUT_BEFORE_ACK replays committed prefix on Reopen (F-460). */
    if (!vos_storage_reserve(&store, sys_domain, &fresh_tx) ||
        store.attempt.generation != 7u ||
        !vos_storage_stage(&store, sys_domain) ||
        vos_storage_publish(&store, sys_domain, VOS_STORAGE_CUT_BEFORE_ACK, &ack_gen)) {
        return 0;
    }
    if (crypto.rot_epoch_counter != 1u || medium.journal_count == 0u) {
        return 0;
    }
    /* Non-prefix tear control on committed journal: missing or modified frame refuses. */
    struct vos_storage_medium torn_medium = medium;
    --torn_medium.journal_count;
    struct vos_storage_store torn_store;
    if (vos_storage_reopen(&torn_medium, &torn_store, &crypto,
                           VOS_CRYPTO_DOMAIN_SYSTEM, sys_domain)) {
        return 0;
    }
    torn_medium = medium;
    torn_medium.journal[0].ciphertext[0] ^= 0x01u;
    if (vos_storage_reopen(&torn_medium, &torn_store, &crypto,
                           VOS_CRYPTO_DOMAIN_SYSTEM, sys_domain)) {
        return 0;
    }
    if (medium.journal_count >= 2u) {
        torn_medium = medium;
        const struct vos_storage_journal_frame tmp = torn_medium.journal[0];
        torn_medium.journal[0] = torn_medium.journal[1];
        torn_medium.journal[1] = tmp;
        if (vos_storage_reopen(&torn_medium, &torn_store, &crypto,
                               VOS_CRYPTO_DOMAIN_SYSTEM, sys_domain)) {
            return 0;
        }
    }

    /* Intact committed prefix replays idempotently on Reopen and recovers key 70. */
    if (!vos_storage_reopen(&medium, &store, &crypto, VOS_CRYPTO_DOMAIN_SYSTEM, sys_domain) ||
        store.committed_generation != 7u ||
        medium.journal_count == 0u ||
        !medium.journal_reusable ||
        vos_storage_lookup(&store, sys_domain, 70u, &probe) != VOS_TREE_FOUND ||
        probe != 700u) {
        return 0;
    }

    /* R-10-013e: rolling back a Fresh checkpoint to the stale fallback refuses. */
    struct vos_storage_medium stale_fresh = medium;
    stale_fresh.checkpoint = checkpoint_gen2;
    stale_fresh.fallback_checkpoint = checkpoint_gen2;
    if (vos_storage_reopen(&stale_fresh, &torn_store, &crypto,
                           VOS_CRYPTO_DOMAIN_SYSTEM, sys_domain)) {
        return 0;
    }

    /* R-10-022a: swapping two valid encrypted blocks in arena_ciphertext refuses. */
    struct vos_storage_medium swapped_blocks = medium;
    uint8_t swap_buf[96];
    memcpy(swap_buf, swapped_blocks.arena_ciphertext, 96u);
    memcpy(swapped_blocks.arena_ciphertext,
           swapped_blocks.arena_ciphertext + 96u, 96u);
    memcpy(swapped_blocks.arena_ciphertext + 96u, swap_buf, 96u);
    if (vos_storage_reopen(&swapped_blocks, &torn_store, &crypto,
                           VOS_CRYPTO_DOMAIN_SYSTEM, sys_domain)) {
        return 0;
    }

    /* Nonce-state rollback (replaying a MAC-valid older nonce record) refuses. */
    struct vos_storage_medium rolled_nonce = medium;
    rolled_nonce.nonce_record = saved_nonce_gen2;
    if (vos_storage_reopen(&rolled_nonce, &torn_store, &crypto,
                           VOS_CRYPTO_DOMAIN_SYSTEM, sys_domain)) {
        return 0;
    }

    /* Snapshot retention + delete + compaction over the committed store. */
    if (!vos_storage_retain_snapshot(&store, sys_domain, 7u)) {
        return 0;
    }
    struct vos_storage_tx_spec del_tx = {
        .op_kind = VOS_STORAGE_OP_DELETE,
        .commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE,
        .key = 30u
    };
    if (!apply_commit(&store, sys_domain, &del_tx, &ack_gen) ||
        ack_gen != 8u ||
        medium.checkpoint.dead_count == 0u ||
        vos_storage_lookup(&store, sys_domain, 30u, &probe) != VOS_TREE_MISSING) {
        return 0;
    }
    const uint64_t used_before_compact = store.committed_used;
    (void)used_before_compact;
    struct vos_storage_tx_spec compact_tx = {
        .op_kind = VOS_STORAGE_OP_COMPACT,
        .commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE
    };
    if (!apply_commit(&store, sys_domain, &compact_tx, &ack_gen) ||
        ack_gen != 9u ||

        vos_storage_lookup(&store, sys_domain, 70u, &probe) != VOS_TREE_FOUND ||
        probe != 700u) {
        return 0;
    }

    /* Exhaustion refusal at max_generation (12) without wrapping. */
    for (uint64_t g = 10u; g <= 12u; ++g) {
        ins_tx.key = 100u + g;
        ins_tx.value = 1000u + g;
        if (!apply_commit(&store, sys_domain, &ins_tx, &ack_gen) || ack_gen != g) {
            return 0;
        }
    }
    ins_tx.key = 999u;
    if (vos_storage_reserve(&store, sys_domain, &ins_tx) ||
        medium.nonce_record.reserved_generation != 12u) {
        return 0;
    }
    return 1;
}

struct write_counter {
    uint32_t common_writes;
    uint32_t private_writes;
    uint32_t response_writes;
};

static void count_resident_store(void *opaque, uint32_t kind,
                                 const void *address, size_t length)
{
    struct write_counter *counter = (struct write_counter *)opaque;
    (void)address;
    if (counter == NULL || length == 0u) {
        return;
    }
    if (kind == VOS_RESIDENT_COMMON) {
        ++counter->common_writes;
    } else if (kind == VOS_RESIDENT_PRIVATE) {
        ++counter->private_writes;
    } else if (kind == VOS_RESIDENT_RESPONSE) {
        ++counter->response_writes;
    }
}

static int check_two_instances_and_resident_reads(void)
{
    const struct vos_node_geometry geometry = {
        .fan = 4u,
        .block_bytes = 96u,
        .arena_nodes = 32u
    };
    const struct vos_tree_limits limits = {
        .height = 0u,
        .depth_limit = 6u,
        .visit_limit = 32u
    };
    const uint64_t sys_domain = 0x53595331ULL;
    const uint64_t usr_domain = 0x55535231ULL;
    uint8_t master_key[32];
    for (uint32_t i = 0u; i < 32u; ++i) {
        master_key[i] = (uint8_t)(0x80u + i);
    }

    struct vos_crypto_core crypto;
    struct vos_storage_medium sys_medium;
    struct vos_storage_medium usr_medium;
    struct vos_storage_store sys_store;
    struct vos_storage_store usr_store;

    vos_crypto_core_init(&crypto, 16u);
    if (!vos_crypto_core_unlock_domain(&crypto, VOS_CRYPTO_DOMAIN_SYSTEM,
                                       sys_domain, 1u, master_key, 32u) ||
        !vos_crypto_core_unlock_domain(&crypto, VOS_CRYPTO_DOMAIN_USER,
                                       usr_domain, 1u, master_key, 32u)) {
        return 0;
    }
    if (!vos_storage_format(&sys_medium, &sys_store, &crypto,
                            VOS_CRYPTO_DOMAIN_SYSTEM, sys_domain, 1u,
                            &geometry, &limits, 1u, 32u) ||
        !vos_storage_format(&usr_medium, &usr_store, &crypto,
                            VOS_CRYPTO_DOMAIN_USER, usr_domain, 1u,
                            &geometry, &limits, 1u, 32u)) {
        return 0;
    }

    /* R-10-016: byte-identical object payload across both instances yields
     * distinct domain-separated digests. */
    static const uint8_t payload[32] = {
        0xdeu, 0xadu, 0xbeu, 0xefu, 0x01u, 0x02u, 0x03u, 0x04u,
        0x11u, 0x22u, 0x33u, 0x44u, 0x55u, 0x66u, 0x77u, 0x88u,
        0x99u, 0xaau, 0xbbu, 0xccu, 0xddu, 0xeeu, 0xffu, 0x00u,
        0x56u, 0x4fu, 0x53u, 0x2du, 0x51u, 0x34u, 0x34u, 0x21u
    };
    uint8_t sys_obj_digest[32] = {0};
    uint8_t usr_obj_digest[32] = {0};
    if (!vos_storage_object_digest(&sys_store, payload, sizeof(payload), sys_obj_digest) ||
        !vos_storage_object_digest(&usr_store, payload, sizeof(payload), usr_obj_digest) ||
        memcmp(sys_obj_digest, usr_obj_digest, 32u) == 0) {
        return 0;
    }

    /* Bind resident identities and commit their object authenticator entries. */
    struct vos_resident_identity sys_id = {0};
    struct vos_resident_identity usr_id = {0};
    uint64_t sys_tree_val = 0u;
    uint64_t usr_tree_val = 0u;

    /* Pre-calculate at generation 2 (the generation the insert commit will land at). */
    sys_store.committed_generation = 2u;
    usr_store.committed_generation = 2u;
    if (!vos_storage_bind_resident_identity(&sys_store, 11u, 500u, 1u,
                                            VOS_RESIDENT_SYSTEM, payload,
                                            sizeof(payload), &sys_tree_val, &sys_id) ||
        !vos_storage_bind_resident_identity(&usr_store, 22u, 500u, 1u,
                                            VOS_RESIDENT_USER, payload,
                                            sizeof(payload), &usr_tree_val, &usr_id)) {
        return 0;
    }
    sys_store.committed_generation = 1u;
    usr_store.committed_generation = 1u;

    struct vos_storage_tx_spec sys_tx = {
        .op_kind = VOS_STORAGE_OP_INSERT,
        .commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE,
        .key = 500u,
        .value = sys_tree_val
    };
    struct vos_storage_tx_spec usr_tx = {
        .op_kind = VOS_STORAGE_OP_INSERT,
        .commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE,
        .key = 500u,
        .value = usr_tree_val
    };
    uint64_t ack = 0u;
    if (!apply_commit(&sys_store, sys_domain, &sys_tx, &ack) || ack != 2u ||
        !apply_commit(&usr_store, usr_domain, &usr_tx, &ack) || ack != 2u) {
        return 0;
    }

    /* Q44: Admit two independent reader handles and serve repeated window reads
     * verified through vos_storage_verify_resident with zero common writes. */
    struct write_counter counter = {0};
    struct vos_resident_owner owner;
    if (!vos_resident_init(&owner, 1u, 2u, 64u, count_resident_store, &counter) ||
        !vos_resident_publish(&owner, &sys_id, payload, sizeof(payload))) {
        return 0;
    }
    struct vos_resident_handle h0 = {0};
    struct vos_resident_handle h1 = {0};
    if (!vos_resident_admit(&owner, 0u, sys_domain, &sys_id, 0u, 16u, 5u, 20u, &h0) ||
        !vos_resident_admit(&owner, 1u, sys_domain, &sys_id, 16u, 16u, 5u, 20u, &h1)) {
        return 0;
    }

    counter.common_writes = 0u;
    counter.private_writes = 0u;
    counter.response_writes = 0u;
    for (uint32_t round = 0u; round < 3u; ++round) {
        uint64_t seq0 = 0u;
        uint64_t seq1 = 0u;
        uint8_t out0[16] = {0};
        uint8_t out1[16] = {0};
        size_t len0 = 0u;
        size_t len1 = 0u;
        if (!vos_resident_begin(&owner, &h0, sys_domain, 0u, 16u, 6u, &seq0) ||
            !vos_resident_begin(&owner, &h1, sys_domain, 0u, 16u, 6u, &seq1) ||
            !vos_resident_complete(&owner, &h0, sys_domain, seq0, 6u,
                                   vos_storage_verify_resident, &sys_store,
                                   out0, sizeof(out0), &len0) ||
            !vos_resident_complete(&owner, &h1, sys_domain, seq1, 6u,
                                   vos_storage_verify_resident, &sys_store,
                                   out1, sizeof(out1), &len1) ||
            len0 != 16u || len1 != 16u ||
            memcmp(out0, payload, 16u) != 0 ||
            memcmp(out1, payload + 16u, 16u) != 0) {
            return 0;
        }
    }
    if (counter.common_writes != 0u || counter.private_writes == 0u ||
        counter.response_writes == 0u) {
        return 0;
    }

    /* Cross-store verification refusal: user-data store refuses system-integrity handle. */
    uint64_t seq_bad = 0u;
    uint8_t out_bad[16] = {0};
    size_t len_bad = 0u;
    if (!vos_resident_begin(&owner, &h0, sys_domain, 0u, 16u, 7u, &seq_bad) ||
        vos_resident_complete(&owner, &h0, sys_domain, seq_bad, 7u,
                              vos_storage_verify_resident, &usr_store,
                              out_bad, sizeof(out_bad), &len_bad)) {
        return 0;
    }

    /* R-10-001: corrupting the underlying B+ tree block in sys_medium causes
     * vos_storage_verify_resident to refuse the resident read! */
    sys_medium.arena_ciphertext[(size_t)sys_store.committed_root * 96u] ^= 0x80u;
    if (vos_resident_complete(&owner, &h0, sys_domain, seq_bad, 7u,
                              vos_storage_verify_resident, &sys_store,
                              out_bad, sizeof(out_bad), &len_bad)) {
        return 0;
    }
    sys_medium.arena_ciphertext[(size_t)sys_store.committed_root * 96u] ^= 0x80u;
    if (!vos_resident_complete(&owner, &h0, sys_domain, seq_bad, 7u,
                               vos_storage_verify_resident, &sys_store,
                               out_bad, sizeof(out_bad), &len_bad) ||
        len_bad != 16u || memcmp(out_bad, payload, 16u) != 0) {
        return 0;
    }
    return 1;
}

static int check_blkdev_image_serialization_and_tears(void)
{
    static const struct vos_node_geometry geom = {
        .fan = 4u,
        .arena_nodes = 16u,
        .block_bytes = 128u
    };
    static const struct vos_tree_limits limits = {
        .height = 0u,
        .depth_limit = 4u,
        .visit_limit = 64u
    };
    static const uint8_t master[32] = {
        0x11u, 0x22u, 0x33u, 0x44u, 0x55u, 0x66u, 0x77u, 0x88u,
        0x99u, 0xaau, 0xbbu, 0xccu, 0xddu, 0xeeu, 0xffu, 0x00u,
        0x01u, 0x23u, 0x45u, 0x67u, 0x89u, 0xabu, 0xcdu, 0xefu,
        0xfeu, 0xdcu, 0xbau, 0x98u, 0x76u, 0x54u, 0x32u, 0x10u
    };
    const uint64_t dom = 0x5050u;
    struct vos_crypto_core crypto;
    struct vos_storage_medium medium;
    struct vos_storage_store store;
    vos_crypto_core_init(&crypto, 16u);
    if (!vos_crypto_core_unlock_domain(&crypto, VOS_CRYPTO_DOMAIN_SYSTEM,
                                       dom, 1u, master, sizeof(master)) ||
        !vos_storage_format(&medium, &store, &crypto, VOS_CRYPTO_DOMAIN_SYSTEM,
                            dom, 1u, &geom, &limits, 1u, 64u)) {
        return 0;
    }

    struct vos_storage_tx_spec tx = {
        .op_kind = VOS_STORAGE_OP_INSERT,
        .commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE,
        .key = 100u,
        .value = 1000u
    };
    uint64_t ack = 0u;
    if (!apply_commit(&store, dom, &tx, &ack) || ack != 2u) {
        return 0;
    }

    uint8_t img_gen2[VOS_STORAGE_BLKDEV_IMAGE_BYTES] = {0};
    if (!vos_storage_encode_blkdev_image(&medium, img_gen2) ||
        memcmp(img_gen2, "VOSBLK01", 8u) != 0) {
        return 0;
    }

    /* Reopen into fresh zeroed medium and store from the VOSBLK01 image bytes. */
    struct vos_storage_medium reopened_med;
    struct vos_storage_store reopened_store;
    uint64_t val = 0u;
    if (!vos_storage_reopen_blkdev_image(img_gen2, &reopened_med,
                                         &reopened_store, &crypto,
                                         VOS_CRYPTO_DOMAIN_SYSTEM, dom) ||
        reopened_store.committed_generation != 2u ||
        vos_storage_lookup(&reopened_store, dom, 100u, &val) != VOS_TREE_FOUND ||
        val != 1000u) {
        return 0;
    }

    /* Header corruption and wrong-geometry refusals. */
    uint8_t bad_img[VOS_STORAGE_BLKDEV_IMAGE_BYTES];
    memcpy(bad_img, img_gen2, sizeof(bad_img));
    bad_img[7] = '2';
    if (vos_storage_reopen_blkdev_image(bad_img, &reopened_med, &reopened_store,
                                        &crypto, VOS_CRYPTO_DOMAIN_SYSTEM, dom)) {
        return 0;
    }
    memcpy(bad_img, img_gen2, sizeof(bad_img));
    bad_img[8] = 64u; /* wrong block_bytes = 64 */
    if (vos_storage_reopen_blkdev_image(bad_img, &reopened_med, &reopened_store,
                                        &crypto, VOS_CRYPTO_DOMAIN_SYSTEM, dom)) {
        return 0;
    }
    memcpy(bad_img, img_gen2, sizeof(bad_img));
    bad_img[24] = 1u; /* non-zero reserved header byte */
    if (vos_storage_reopen_blkdev_image(bad_img, &reopened_med, &reopened_store,
                                        &crypto, VOS_CRYPTO_DOMAIN_SYSTEM, dom)) {
        return 0;
    }

    /* Non-prefix bit tear ((old & ~m) | (new & m)) on an uncommitted journal
     * frame block during VOS_STORAGE_CUT_BEFORE_CHECKPOINT: reopen discards the
     * uncommitted journal and preserves generation 2. */
    tx.key = 200u;
    tx.value = 2000u;
    if (!vos_storage_reserve(&store, dom, &tx) ||
        !vos_storage_stage(&store, dom) ||
        vos_storage_publish(&store, dom, VOS_STORAGE_CUT_BEFORE_CHECKPOINT, &ack)) {
        return 0;
    }
    uint8_t img_cut3[VOS_STORAGE_BLKDEV_IMAGE_BYTES] = {0};
    if (!vos_storage_encode_blkdev_image(&medium, img_cut3)) {
        return 0;
    }
    uint8_t mask[VOS_STORAGE_BLKDEV_BLOCK_BYTES];
    for (size_t i = 0u; i < sizeof(mask); ++i) {
        mask[i] = (uint8_t)((i & 1u) ? 0x5au : 0xa5u);
    }
    const uint8_t *old_blk18 =
        img_gen2 + VOS_STORAGE_BLKDEV_HEADER_BYTES + 18u * VOS_STORAGE_BLKDEV_BLOCK_BYTES;
    const uint8_t *new_blk18 =
        img_cut3 + VOS_STORAGE_BLKDEV_HEADER_BYTES + 18u * VOS_STORAGE_BLKDEV_BLOCK_BYTES;
    uint8_t new_blk18_copy[VOS_STORAGE_BLKDEV_BLOCK_BYTES];
    memcpy(new_blk18_copy, new_blk18, sizeof(new_blk18_copy));
    vos_storage_apply_block_tear(
        img_cut3 + VOS_STORAGE_BLKDEV_HEADER_BYTES, 18u,
        old_blk18, new_blk18_copy, mask);
    if (!vos_storage_reopen_blkdev_image(img_cut3, &reopened_med,
                                         &reopened_store, &crypto,
                                         VOS_CRYPTO_DOMAIN_SYSTEM, dom) ||
        reopened_store.committed_generation != 2u ||
        reopened_med.nonce_record.reserved_generation != 3u ||
        vos_storage_lookup(&reopened_store, dom, 200u, &val) != VOS_TREE_MISSING ||
        vos_storage_lookup(&reopened_store, dom, 100u, &val) != VOS_TREE_FOUND ||
        val != 1000u) {
        return 0;
    }

    /* VOS_STORAGE_CUT_BEFORE_ACK serialized to VOSBLK01 image: intact image
     * replays committed redo prefix to generation 4; non-prefix bit tear on
     * the committed journal block 18 is refused by Reopen! */
    if (!vos_storage_reopen(&medium, &store, &crypto,
                            VOS_CRYPTO_DOMAIN_SYSTEM, dom) ||
        !vos_storage_reserve(&store, dom, &tx) ||
        !vos_storage_stage(&store, dom) ||
        vos_storage_publish(&store, dom, VOS_STORAGE_CUT_BEFORE_ACK, &ack)) {
        return 0;
    }
    uint8_t img_cut5[VOS_STORAGE_BLKDEV_IMAGE_BYTES] = {0};
    if (!vos_storage_encode_blkdev_image(&medium, img_cut5)) {
        return 0;
    }
    if (!vos_storage_reopen_blkdev_image(img_cut5, &reopened_med,
                                         &reopened_store, &crypto,
                                         VOS_CRYPTO_DOMAIN_SYSTEM, dom) ||
        reopened_store.committed_generation != 4u ||
        vos_storage_lookup(&reopened_store, dom, 200u, &val) != VOS_TREE_FOUND ||
        val != 2000u) {
        return 0;
    }
    memcpy(new_blk18_copy,
           img_cut5 + VOS_STORAGE_BLKDEV_HEADER_BYTES +
               18u * VOS_STORAGE_BLKDEV_BLOCK_BYTES,
           sizeof(new_blk18_copy));
    vos_storage_apply_block_tear(
        img_cut5 + VOS_STORAGE_BLKDEV_HEADER_BYTES, 18u,
        old_blk18, new_blk18_copy, mask);
    if (vos_storage_reopen_blkdev_image(img_cut5, &reopened_med,
                                        &reopened_store, &crypto,
                                        VOS_CRYPTO_DOMAIN_SYSTEM, dom)) {
        return 0;
    }
    return 1;
}

static int check_reuse_compaction_and_checkpoint_slots(void)
{
    static const uint8_t master[32] = {0x42u};
    const uint64_t domain = 0x4242u;
    const struct vos_tree_limits limits = {
        .height = 0u, .depth_limit = 4u, .visit_limit = 64u
    };
    for (uint64_t capacity = 2u; capacity <= 16u; ++capacity) {
        const struct vos_node_geometry geometry = {
            .fan = 4u, .arena_nodes = capacity, .block_bytes = 128u
        };
        struct vos_crypto_core crypto;
        struct vos_storage_medium medium;
        struct vos_storage_store store;
        vos_crypto_core_init(&crypto, 32u);
        if (!vos_crypto_core_unlock_domain(&crypto, VOS_CRYPTO_DOMAIN_SYSTEM,
                                           domain, 1u, master, sizeof(master)) ||
            !vos_storage_format(&medium, &store, &crypto, VOS_CRYPTO_DOMAIN_SYSTEM,
                                 domain, 1u, &geometry, &limits, 1u, 128u)) {
            return 0;
        }
        struct vos_storage_tx_spec tx = {
            .op_kind = VOS_STORAGE_OP_INSERT,
            .commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE,
            .key = 7u, .value = 1u
        };
        uint64_t ack = 0u;
        for (uint64_t value = 1u; value <= 40u; ++value) {
            tx.value = value;
            if (!apply_commit(&store, domain, &tx, &ack)) {
                return 0;
            }
        }
        if (capacity == 2u && store.committed_used != capacity) {
            return 0;
        }
        struct vos_storage_tx_spec compact = {
            .op_kind = VOS_STORAGE_OP_COMPACT,
            .commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE
        };
        uint64_t value = 0u;
        if (!apply_commit(&store, domain, &compact, &ack) ||
            !vos_storage_reopen(&medium, &store, &crypto,
                                VOS_CRYPTO_DOMAIN_SYSTEM, domain) ||
            vos_storage_lookup(&store, domain, 7u, &value) != VOS_TREE_FOUND ||
            value != 40u) {
            return 0;
        }
        tx.value = 41u;
        if (!apply_commit(&store, domain, &tx, &ack)) {
            return 0;
        }

        /* Every primary checkpoint block can tear without losing acknowledged
         * data; corruption of both authenticated slots still refuses. */
        uint8_t image[VOS_STORAGE_BLKDEV_IMAGE_BYTES];
        if (!vos_storage_encode_blkdev_image(&medium, image)) {
            return 0;
        }
        for (uint32_t block = 32u; block < 48u; ++block) {
            uint8_t torn[VOS_STORAGE_BLKDEV_IMAGE_BYTES];
            memcpy(torn, image, sizeof(torn));
            const size_t at = VOS_STORAGE_BLKDEV_HEADER_BYTES +
                              (size_t)block * VOS_STORAGE_BLKDEV_BLOCK_BYTES;
            for (size_t i = 0u; i < VOS_STORAGE_BLKDEV_BLOCK_BYTES; ++i) {
                torn[at + i] ^= (uint8_t)((i & 1u) ? 0x5au : 0xa5u);
            }
            struct vos_storage_medium recovered;
            struct vos_storage_store recovered_store;
            if (!vos_storage_reopen_blkdev_image(torn, &recovered, &recovered_store,
                                                  &crypto, VOS_CRYPTO_DOMAIN_SYSTEM,
                                                  domain) ||
                recovered_store.committed_generation != ack ||
                vos_storage_lookup(&recovered_store, domain, 7u, &value) !=
                    VOS_TREE_FOUND || value != 41u) {
                return 0;
            }
        }
        struct vos_storage_medium corrupt = medium;
        corrupt.checkpoint.checkpoint_mac[0] ^= 1u;
        corrupt.fallback_checkpoint.checkpoint_mac[0] ^= 1u;
        struct vos_storage_store rejected;
        if (vos_storage_reopen(&corrupt, &rejected, &crypto,
                               VOS_CRYPTO_DOMAIN_SYSTEM, domain)) {
            return 0;
        }

        /* Retaining the current root pins its bytes across relocation. A
         * previously freed historical generation cannot become a snapshot. */
        if (vos_storage_retain_snapshot(&store, domain, 2u) ||
            !vos_storage_retain_snapshot(&store, domain, ack)) {
            return 0;
        }
        const uint64_t retained_root = store.committed_root;
        uint8_t retained_bytes[VOS_STORAGE_BLKDEV_BLOCK_BYTES];
        memcpy(retained_bytes, medium.arena_ciphertext +
               (size_t)retained_root * geometry.block_bytes, geometry.block_bytes);
        tx.value = 42u;
        if (!apply_commit(&store, domain, &tx, &ack) ||
            !apply_commit(&store, domain, &compact, &ack) ||
            memcmp(retained_bytes, medium.arena_ciphertext +
                   (size_t)retained_root * geometry.block_bytes,
                   geometry.block_bytes) != 0) {
            return 0;
        }
    }
    return 1;
}

static int check_reused_multilevel_maps(void)
{
    static const uint8_t master[32] = {0x39u};
    const uint64_t domain = 0x3939u;
    for (uint32_t fan = 2u; fan <= 4u; ++fan) {
        const struct vos_node_geometry geometry = {
            .fan = fan, .arena_nodes = 32u, .block_bytes = 128u
        };
        const struct vos_tree_limits limits = {
            .height = 0u, .depth_limit = 6u, .visit_limit = 64u
        };
        struct vos_crypto_core crypto;
        struct vos_storage_medium medium;
        struct vos_storage_store store;
        vos_crypto_core_init(&crypto, 16u);
        if (!vos_crypto_core_unlock_domain(&crypto, VOS_CRYPTO_DOMAIN_SYSTEM,
                                           domain, 1u, master, sizeof(master)) ||
            !vos_storage_format(&medium, &store, &crypto, VOS_CRYPTO_DOMAIN_SYSTEM,
                                 domain, 1u, &geometry, &limits, 1u, 128u)) {
            return 0;
        }
        uint64_t expected[8] = {0};
        uint8_t present[8] = {0};
        for (uint64_t step = 0u; step < 48u; ++step) {
            const uint64_t key = (step * 5u + step / 8u) % 8u;
            struct vos_storage_tx_spec tx = {
                .op_kind = step % 11u == 10u ? VOS_STORAGE_OP_COMPACT :
                           step % 5u == 4u ? VOS_STORAGE_OP_DELETE :
                                             VOS_STORAGE_OP_INSERT,
                .commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE,
                .key = key, .value = step + 100u
            };
            uint64_t ack = 0u;
            if (!apply_commit(&store, domain, &tx, &ack) ||
                !vos_storage_reopen(&medium, &store, &crypto,
                                    VOS_CRYPTO_DOMAIN_SYSTEM, domain)) {
                return 0;
            }
            if (tx.op_kind == VOS_STORAGE_OP_INSERT) {
                present[key] = 1u;
                expected[key] = tx.value;
            } else if (tx.op_kind == VOS_STORAGE_OP_DELETE) {
                present[key] = 0u;
            }
            for (uint64_t query = 0u; query < 8u; ++query) {
                uint64_t value = 0u;
                const int status = vos_storage_lookup(&store, domain, query, &value);
                if ((present[query] && (status != VOS_TREE_FOUND || value != expected[query])) ||
                    (!present[query] && status != VOS_TREE_MISSING)) {
                    return 0;
                }
            }
        }
    }
    return 1;
}

static int check_active_checkpoint_cache(void)
{
    const uint64_t domain = 0x6161u;
    static const uint8_t master[32] = {0x61u};
    const struct vos_node_geometry geometry = {
        .fan = 4u, .arena_nodes = 8u, .block_bytes = 128u
    };
    const struct vos_tree_limits limits = {
        .height = 0u, .depth_limit = 4u, .visit_limit = 64u
    };
    struct vos_crypto_core crypto;
    struct vos_storage_medium medium;
    struct vos_storage_store store;
    vos_crypto_core_init(&crypto, 16u);
    if (!vos_crypto_core_unlock_domain(&crypto, VOS_CRYPTO_DOMAIN_SYSTEM,
                                       domain, 1u, master, sizeof(master)) ||
        !vos_storage_format(&medium, &store, &crypto, VOS_CRYPTO_DOMAIN_SYSTEM,
                             domain, 1u, &geometry, &limits, 1u, 64u)) {
        return 0;
    }
    struct vos_storage_tx_spec tx = {
        .op_kind = VOS_STORAGE_OP_INSERT,
        .commit_mode = VOS_STORAGE_COMMIT_ROLLBACKABLE,
        .key = 8u, .value = 80u
    };
    uint64_t ack = 0u;
    if (!apply_commit(&store, domain, &tx, &ack)) {
        return 0;
    }
    uint8_t store_before[sizeof(store)];
    uint8_t crypto_before[sizeof(crypto)];
    memcpy(store_before, &store, sizeof(store));
    memcpy(crypto_before, &crypto, sizeof(crypto));
#if defined(VOS_STORAGE_COUNT_CHECKPOINT_MACS)
    const uint64_t checks_before = checkpoint_mac_checks;
#endif
    for (uint32_t read = 0u; read < 16u; ++read) {
        uint64_t value = 0u;
        if (vos_storage_lookup(&store, domain, 8u, &value) != VOS_TREE_FOUND ||
            value != 80u || memcmp(store_before, &store, sizeof(store)) != 0 ||
            memcmp(crypto_before, &crypto, sizeof(crypto)) != 0) {
            return 0;
        }
    }
#if defined(VOS_STORAGE_COUNT_CHECKPOINT_MACS)
    if (checkpoint_mac_checks != checks_before) {
        return 0;
    }
#endif
    /* Changing any byte of the external checkpoint invalidates the private
     * admission, including its padding and currently unused authentication slots. */
    uint8_t *checkpoint_bytes = (uint8_t *)&medium.checkpoint;
    for (size_t i = 0u; i < sizeof(medium.checkpoint); ++i) {
        checkpoint_bytes[i] ^= 1u;
        uint64_t value = UINT64_MAX;
        const int status = vos_storage_lookup(&store, domain, 8u, &value);
        checkpoint_bytes[i] ^= 1u;
        if (status != VOS_TREE_REFUSED || value != UINT64_MAX) {
            return 0;
        }
    }
    struct vos_storage_medium foreign_medium = medium;
    store.medium = &foreign_medium;
    uint64_t value = 0u;
    if (vos_storage_lookup(&store, domain, 8u, &value) != VOS_TREE_REFUSED) {
        return 0;
    }
    store.medium = &medium;
    static const uint8_t foreign_key[32] = {0x62u};
    vos_crypto_core_lock_domain(&crypto, VOS_CRYPTO_DOMAIN_SYSTEM);
    if (!vos_crypto_core_unlock_domain(&crypto, VOS_CRYPTO_DOMAIN_SYSTEM,
                                       domain, 1u, foreign_key, sizeof(foreign_key)) ||
        vos_storage_lookup(&store, domain, 8u, &value) != VOS_TREE_REFUSED) {
        return 0;
    }
    vos_crypto_core_lock_domain(&crypto, VOS_CRYPTO_DOMAIN_SYSTEM);
    if (vos_storage_lookup(&store, domain, 8u, &value) != VOS_TREE_REFUSED ||
        !vos_crypto_core_unlock_domain(&crypto, VOS_CRYPTO_DOMAIN_SYSTEM,
                                       domain, 1u, master, sizeof(master)) ||
        vos_storage_lookup(&store, domain, 8u, &value) != VOS_TREE_FOUND || value != 80u ||
        !vos_storage_retain_snapshot(&store, domain, ack) ||
        vos_storage_lookup(&store, domain, 8u, &value) != VOS_TREE_FOUND ||
        !vos_storage_reopen(&medium, &store, &crypto, VOS_CRYPTO_DOMAIN_SYSTEM, domain) ||
        vos_storage_lookup(&store, domain, 8u, &value) != VOS_TREE_FOUND || value != 80u) {
        return 0;
    }
    return 1;
}

int main(void)
{
    if (!check_crypto_primitives()) {
        fprintf(stderr, "storage_publish: crypto primitives check failed\n");
        return 1;
    }
    if (!check_compartment_domains_and_bfu()) {
        fprintf(stderr, "storage_publish: compartment domain/BFU check failed\n");
        return 1;
    }
    if (!check_publish_lifecycle_and_cuts()) {
        fprintf(stderr, "storage_publish: publish lifecycle and cuts check failed\n");
        return 1;
    }
    if (!check_two_instances_and_resident_reads()) {
        fprintf(stderr, "storage_publish: two-instance and resident-read check failed\n");
        return 1;
    }
    if (!check_blkdev_image_serialization_and_tears()) {
        fprintf(stderr, "storage_publish: blkdev_image serialization and tears check failed\n");
        return 1;
    }
    if (!check_reuse_compaction_and_checkpoint_slots()) {
        fprintf(stderr, "storage_publish: reuse/compaction/checkpoint slots failed\n");
        return 1;
    }
    if (!check_reused_multilevel_maps()) {
        fprintf(stderr, "storage_publish: reused multilevel map check failed\n");
        return 1;
    }
    if (!check_active_checkpoint_cache()) {
        fprintf(stderr, "storage_publish: active checkpoint cache check failed\n");
        return 1;
    }
    printf("storage_publish: ok\n");
    return 0;
}
