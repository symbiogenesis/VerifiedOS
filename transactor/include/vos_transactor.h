// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_TRANSACTOR_H
#define VOS_TRANSACTOR_H

#include <stddef.h>
#include <stdint.h>

#include "vos_crypto_core.h"

enum {
    VOS_TX_DIGEST_BYTES = VOS_CRYPTO_DIGEST_BYTES,
    VOS_TX_MAX_KIDS = 16u,
    VOS_TX_MAX_PAYLOAD = 256u,
    VOS_TX_MAX_OBJECTS = 64u,
    VOS_TX_MAX_WALK_DEPTH = 16u,
    VOS_TX_COPIES_PER_SLOT = 2u,
    VOS_TX_MAX_COPIES = 4u,
    VOS_TX_MAX_ENROLLED_KEYS = 4u
};

enum vos_tx_status {
    VOS_TX_OK = 0,
    VOS_TX_ERR_INVALID = -1,
    VOS_TX_ERR_MISSING = -2,
    VOS_TX_ERR_HASH_MISMATCH = -3,
    VOS_TX_ERR_BAD_LINK = -4,
    VOS_TX_ERR_TARGET_MISMATCH = -5,
    VOS_TX_ERR_CYCLE = -6,
    VOS_TX_ERR_DEPTH = -7,
    VOS_TX_ERR_BUFFER = -8,
    VOS_TX_ERR_STORE_FULL = -9,
    VOS_TX_ERR_UNVERIFIED = -10,
    VOS_TX_ERR_NOT_STAGED = -11,
    VOS_TX_ERR_ROLLBACK_FLOOR = -12,
    VOS_TX_ERR_NOT_ADMITTED = -13,
    VOS_TX_ERR_WITNESS_PIN = -14,
    VOS_TX_ERR_INCOMPLETE_DAG = -15,
    VOS_TX_ERR_RESTAGED = -16,
    VOS_TX_ERR_NO_PREDECESSOR = -17,
    VOS_TX_ERR_PREDECESSOR_MISMATCH = -18
};

struct vos_tx_hash {
    uint8_t bytes[VOS_TX_DIGEST_BYTES];
};

struct vos_tx_object {
    uint32_t kid_count;
    uint32_t payload_len;
    uint8_t payload[VOS_TX_MAX_PAYLOAD];
    struct vos_tx_hash kids[VOS_TX_MAX_KIDS];
};

struct vos_tx_store_entry {
    uint32_t occupied;
    struct vos_tx_hash addr;
    struct vos_tx_object obj;
};

struct vos_tx_store {
    uint32_t count;
    struct vos_tx_store_entry entries[VOS_TX_MAX_OBJECTS];
};

struct vos_tx_path_witness {
    uint32_t step_count;
    struct vos_tx_hash steps[VOS_TX_MAX_WALK_DEPTH];
};

struct vos_tx_signed_root {
    struct vos_tx_hash root;
    uint64_t version;
    uint64_t declared_floor;
    uint64_t key_id;
    uint8_t sig[VOS_TX_DIGEST_BYTES];
    uint8_t checksum[VOS_TX_DIGEST_BYTES];
};

struct vos_tx_enrolled_key {
    uint32_t enrolled;
    uint64_t key_id;
    uint8_t hmac_key[VOS_CRYPTO_KEY_BYTES_256];
};

struct vos_tx_policy {
    uint32_t walk_depth;
    uint32_t key_count;
    struct vos_tx_enrolled_key keys[VOS_TX_MAX_ENROLLED_KEYS];
};

struct vos_tx_witness_evidence {
    struct vos_tx_hash offered_checkpoint;
    uint32_t checkpoint_accepted;
    uint32_t checkpoint_consistent;
    uint32_t base_included;
    uint32_t proof_admitted;
    struct vos_tx_hash verdict_root;
};

struct vos_tx_ab {
    uint32_t b_live;
    struct vos_tx_signed_root slot_a;
    struct vos_tx_signed_root slot_b;
    uint64_t floor_version;
    uint32_t staged;
    uint32_t admitted;
    uint32_t has_retained;
    struct vos_tx_signed_root retained_predecessor;
    struct vos_tx_hash pinned_checkpoint;
};

void vos_tx_store_init(struct vos_tx_store *store);

enum vos_tx_status vos_tx_hash_object(const struct vos_tx_object *obj,
                                      struct vos_tx_hash *out_addr);

enum vos_tx_status vos_tx_store_put(struct vos_tx_store *store,
                                    const struct vos_tx_object *obj,
                                    struct vos_tx_hash *out_addr);

enum vos_tx_status vos_tx_store_put_at(struct vos_tx_store *store,
                                       const struct vos_tx_hash *addr,
                                       const struct vos_tx_object *obj);

enum vos_tx_status vos_tx_store_remove(struct vos_tx_store *store,
                                       const struct vos_tx_hash *addr);

enum vos_tx_status vos_tx_sign_root(const struct vos_tx_policy *policy,
                                    struct vos_tx_signed_root *sr);

int vos_tx_verify_root(const struct vos_tx_policy *policy,
                       const struct vos_tx_signed_root *sr);

enum vos_tx_status vos_tx_dag_intact(const struct vos_tx_store *store,
                                     const struct vos_tx_hash *root,
                                     uint32_t walk_depth);

void vos_tx_ab_init(struct vos_tx_ab *ab,
                    const struct vos_tx_signed_root *initial_live,
                    const struct vos_tx_signed_root *initial_spare,
                    uint64_t floor_version,
                    const struct vos_tx_hash *initial_checkpoint);

const struct vos_tx_signed_root *vos_tx_ab_live(const struct vos_tx_ab *ab);

const struct vos_tx_signed_root *vos_tx_ab_spare(const struct vos_tx_ab *ab);

enum vos_tx_status vos_tx_path_read(const struct vos_tx_store *store,
                                    const struct vos_tx_hash *attested_root,
                                    const struct vos_tx_hash *target_addr,
                                    const struct vos_tx_path_witness *witness,
                                    uint32_t walk_depth,
                                    uint8_t *out_payload,
                                    size_t out_capacity,
                                    size_t *out_len);

enum vos_tx_status vos_tx_select_root(const struct vos_tx_policy *policy,
                                      const struct vos_tx_signed_root *copies,
                                      size_t copy_count,
                                      uint32_t untrusted_slot_ptr,
                                      struct vos_tx_signed_root *out_selected);

enum vos_tx_status vos_tx_stage(struct vos_tx_ab *ab,
                                const struct vos_tx_signed_root *candidate);

enum vos_tx_status vos_tx_verify_and_flip(const struct vos_tx_policy *policy,
                                          const struct vos_tx_store *store,
                                          struct vos_tx_ab *ab,
                                          uint64_t rot_floor,
                                          const struct vos_tx_witness_evidence *evidence);

enum vos_tx_status vos_tx_health_check(const struct vos_tx_policy *policy,
                                       const struct vos_tx_store *store,
                                       struct vos_tx_ab *ab,
                                       uint64_t rot_floor,
                                       uint32_t healthy,
                                       uint32_t predecessor_proof_admitted);

#endif
