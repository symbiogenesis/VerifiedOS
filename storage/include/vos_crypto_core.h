// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_CRYPTO_CORE_H
#define VOS_CRYPTO_CORE_H

#include <stddef.h>
#include <stdint.h>

enum {
    VOS_CRYPTO_KEY_BYTES_128 = 16u,
    VOS_CRYPTO_KEY_BYTES_192 = 24u,
    VOS_CRYPTO_KEY_BYTES_256 = 32u,
    VOS_CRYPTO_BLOCK_BYTES = 16u,
    VOS_CRYPTO_NONCE_BYTES = 12u,
    VOS_CRYPTO_TAG_BYTES = 16u,
    VOS_CRYPTO_DIGEST_BYTES = 32u,
    VOS_CRYPTO_MAX_DOMAINS = 4u
};

enum vos_crypto_domain_kind {
    VOS_CRYPTO_DOMAIN_SYSTEM = 0u,
    VOS_CRYPTO_DOMAIN_USER = 1u,
    VOS_CRYPTO_DOMAIN_CHECKPOINT = 2u,
    VOS_CRYPTO_DOMAIN_EPOCH = 3u
};

struct vos_crypto_domain_slot {
    uint32_t provisioned;
    uint32_t key_bytes;
    uint64_t domain_id;
    uint64_t key_epoch;
    uint8_t aead_key[VOS_CRYPTO_KEY_BYTES_256];
    uint8_t dedup_key[VOS_CRYPTO_DIGEST_BYTES];
    uint8_t commit_key[VOS_CRYPTO_DIGEST_BYTES];
};

struct vos_crypto_core {
    struct vos_crypto_domain_slot domains[VOS_CRYPTO_MAX_DOMAINS];
    uint64_t rot_epoch_counter;
    uint64_t rot_epoch_ceiling;
    uint32_t epoch_sealed;
    uint32_t epoch_sealed_mask;
    uint8_t sealed_epoch_root[VOS_CRYPTO_DIGEST_BYTES];
};

int vos_sha256(const uint8_t *message, size_t length,
               uint8_t digest[VOS_CRYPTO_DIGEST_BYTES]);

int vos_hmac_sha256(const uint8_t *key, size_t key_length,
                    const uint8_t *message, size_t message_length,
                    uint8_t mac[VOS_CRYPTO_DIGEST_BYTES]);

int vos_aes_encrypt_block(const uint8_t *key, size_t key_bytes,
                          const uint8_t input[VOS_CRYPTO_BLOCK_BYTES],
                          uint8_t output[VOS_CRYPTO_BLOCK_BYTES]);

int vos_aes_decrypt_block(const uint8_t *key, size_t key_bytes,
                          const uint8_t input[VOS_CRYPTO_BLOCK_BYTES],
                          uint8_t output[VOS_CRYPTO_BLOCK_BYTES]);

int vos_aes_gcm_encrypt(const uint8_t *key, size_t key_bytes,
                        const uint8_t *iv, size_t iv_length,
                        const uint8_t *aad, size_t aad_length,
                        const uint8_t *plaintext, size_t length,
                        uint8_t *ciphertext,
                        uint8_t tag[VOS_CRYPTO_TAG_BYTES]);

int vos_aes_gcm_open(const uint8_t *key, size_t key_bytes,
                     const uint8_t *iv, size_t iv_length,
                     const uint8_t *aad, size_t aad_length,
                     const uint8_t *ciphertext, size_t length,
                     const uint8_t tag[VOS_CRYPTO_TAG_BYTES],
                     uint8_t *plaintext);

void vos_crypto_core_init(struct vos_crypto_core *core,
                          uint64_t rot_epoch_ceiling);

int vos_crypto_core_unlock_domain(struct vos_crypto_core *core, uint32_t slot,
                                  uint64_t domain_id, uint64_t key_epoch,
                                  const uint8_t *master_key, size_t key_bytes);

int vos_crypto_core_lock_domain(struct vos_crypto_core *core, uint32_t slot);

void vos_crypto_core_erase_all(struct vos_crypto_core *core);

int vos_crypto_core_seal(const struct vos_crypto_core *core, uint32_t slot,
                         const uint8_t nonce[VOS_CRYPTO_NONCE_BYTES],
                         const uint8_t *aad, size_t aad_length,
                         const uint8_t *plaintext, size_t length,
                         uint8_t *ciphertext,
                         uint8_t tag[VOS_CRYPTO_TAG_BYTES]);

int vos_crypto_core_open(const struct vos_crypto_core *core, uint32_t slot,
                         const uint8_t nonce[VOS_CRYPTO_NONCE_BYTES],
                         const uint8_t *aad, size_t aad_length,
                         const uint8_t *ciphertext, size_t length,
                         const uint8_t tag[VOS_CRYPTO_TAG_BYTES],
                         uint8_t *plaintext);

int vos_crypto_core_keyed_digest(const struct vos_crypto_core *core,
                                 uint32_t slot,
                                 const uint8_t *plaintext, size_t length,
                                 uint8_t digest[VOS_CRYPTO_DIGEST_BYTES]);

int vos_crypto_core_commit_mac(const struct vos_crypto_core *core,
                               uint32_t slot,
                               const uint8_t *record, size_t length,
                               uint8_t mac[VOS_CRYPTO_DIGEST_BYTES]);

int vos_crypto_core_verify_commit_mac(const struct vos_crypto_core *core,
                                      uint32_t slot,
                                      const uint8_t *record, size_t length,
                                      const uint8_t expected[VOS_CRYPTO_DIGEST_BYTES]);

int vos_crypto_core_seal_epoch(struct vos_crypto_core *core, uint32_t slot,
                               uint64_t region_id, uint64_t region_version,
                               const uint8_t state_digest[VOS_CRYPTO_DIGEST_BYTES],
                               uint64_t *sealed_epoch_out,
                               uint8_t epoch_root_out[VOS_CRYPTO_DIGEST_BYTES]);

int vos_crypto_core_verify_epoch(const struct vos_crypto_core *core,
                                 uint32_t slot, uint64_t expected_epoch,
                                 uint64_t region_id, uint64_t region_version,
                                 const uint8_t state_digest[VOS_CRYPTO_DIGEST_BYTES],
                                 const uint8_t epoch_root[VOS_CRYPTO_DIGEST_BYTES]);

#endif
