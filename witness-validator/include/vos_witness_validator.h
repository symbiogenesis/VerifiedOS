// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_WITNESS_VALIDATOR_H
#define VOS_WITNESS_VALIDATOR_H

#include <stddef.h>
#include <stdint.h>

#include "vos_crypto_core.h"

/*
 * Bounded, GC-free C17 local witness-evidence validator for M6.2c.
 * Reference specification: [WitnessContinuity.v](../../proofs/WitnessContinuity.v),
 * [witness-policy-qualification.md](../../docs/assurance/witness-policy-qualification.md),
 * and [witness.py](../../tools/vos/witness.py).
 */

enum {
    VOS_WV_DIGEST_BYTES = VOS_CRYPTO_DIGEST_BYTES,
    VOS_WV_KEY_BYTES = VOS_CRYPTO_KEY_BYTES_256,
    VOS_WV_MAX_WITNESSES = 16u,
    VOS_WV_MAX_CHECKPOINT_ENTRIES = 16u,
    VOS_WV_MAX_PACKAGES = 16u,
    VOS_WV_MAX_SIGNATURES = 16u,
    VOS_WV_MAX_SEEN_SCOPES = 16u,
    VOS_WV_MAX_ASSUMPTIONS_BYTES = 256u,
    VOS_WV_SIGNATURE_WIRE_BYTES = 196u
};

enum vos_wv_status {
    VOS_WV_OK = 0,
    VOS_WV_ERR_INVALID_ARG = -1,
    VOS_WV_ERR_MALFORMED_WIRE = -2,
    VOS_WV_ERR_TRAILING_BYTES = -3,
    VOS_WV_ERR_OVER_LIMIT = -4,
    VOS_WV_ERR_INVALID_POLICY = -5,
    VOS_WV_ERR_UNSAFE_POLICY = -6,
    VOS_WV_ERR_POLICY_MISMATCH = -7,
    VOS_WV_ERR_DUPLICATE_SIGNER = -8,
    VOS_WV_ERR_FOREIGN_SIGNER = -9,
    VOS_WV_ERR_KEY_MISMATCH = -10,
    VOS_WV_ERR_BAD_BINDING = -11,
    VOS_WV_ERR_FORGED_MAC = -12,
    VOS_WV_ERR_QUORUM_UNMET = -13,
    VOS_WV_ERR_CHECKPOINT_STALE = -14,
    VOS_WV_ERR_MISSING_BASE = -15,
    VOS_WV_ERR_MISSING_PACKAGE = -16,
    VOS_WV_ERR_DISCONTINUOUS = -17,
    VOS_WV_ERR_EMPTY_ASSUMPTIONS = -18,
    VOS_WV_ERR_UNAUTHENTICATED = -19,
    VOS_WV_ERR_SCOPE_REUSED = -20,
    VOS_WV_ERR_CRYPTO = -21
};

enum vos_wv_stmt_kind {
    VOS_WV_STMT_PLAIN = 1u,
    VOS_WV_STMT_TERMINAL = 2u
};

struct vos_wv_hash {
    uint8_t bytes[VOS_WV_DIGEST_BYTES];
};

struct vos_wv_witness_entry {
    uint64_t witness_id;
    uint8_t verify_key[VOS_WV_KEY_BYTES];
};

struct vos_wv_policy {
    uint64_t trust_scope;
    uint64_t epoch;
    uint32_t n;
    uint32_t k;
    uint32_t f;
    struct vos_wv_witness_entry witnesses[VOS_WV_MAX_WITNESSES];
};

struct vos_wv_checkpoint {
    uint32_t entry_count;
    struct vos_wv_hash entries[VOS_WV_MAX_CHECKPOINT_ENTRIES];
};

struct vos_wv_transition {
    struct vos_wv_policy old_policy;
    struct vos_wv_policy new_policy;
    struct vos_wv_checkpoint anchor;
};

struct vos_wv_signature {
    uint32_t stmt_kind;
    uint64_t trust_scope;
    uint64_t epoch;
    struct vos_wv_hash policy_digest;
    struct vos_wv_hash checkpoint_digest;
    struct vos_wv_hash transition_digest;
    uint64_t signer_id;
    uint8_t signer_key[VOS_WV_KEY_BYTES];
    uint8_t mac[VOS_WV_DIGEST_BYTES];
};

struct vos_wv_rebootstrap {
    struct vos_wv_policy old_policy;
    struct vos_wv_policy new_policy;
    struct vos_wv_checkpoint anchor;
    uint32_t assumptions_len;
    uint8_t assumptions[VOS_WV_MAX_ASSUMPTIONS_BYTES];
    uint8_t auth_mac[VOS_WV_DIGEST_BYTES];
};

struct vos_wv_client {
    struct vos_wv_policy policy;
    struct vos_wv_checkpoint pinned;
    struct vos_wv_hash running_generation;
    uint8_t bootstrap_key[VOS_WV_KEY_BYTES];
    uint32_t continuity_preserved;
    uint32_t seen_scope_count;
    uint64_t seen_scopes[VOS_WV_MAX_SEEN_SCOPES];
};

int vos_wv_policy_is_wellformed(const struct vos_wv_policy *policy);

int vos_wv_policy_is_safe(const struct vos_wv_policy *policy);

int vos_wv_checkpoint_is_wellformed(const struct vos_wv_checkpoint *cp);

int vos_wv_checkpoint_extends(const struct vos_wv_checkpoint *new_cp,
                              const struct vos_wv_checkpoint *old_cp);

int vos_wv_checkpoint_contains(const struct vos_wv_checkpoint *cp,
                               const struct vos_wv_hash *entry);

int vos_wv_transition_is_continuous(const struct vos_wv_transition *tr);

enum vos_wv_status vos_wv_policy_digest(const struct vos_wv_policy *policy,
                                        struct vos_wv_hash *out_digest);

enum vos_wv_status vos_wv_checkpoint_digest(const struct vos_wv_checkpoint *cp,
                                            struct vos_wv_hash *out_digest);

enum vos_wv_status vos_wv_transition_digest(const struct vos_wv_transition *tr,
                                            struct vos_wv_hash *out_digest);

enum vos_wv_status vos_wv_parse_policy(const uint8_t *buf,
                                       size_t len,
                                       struct vos_wv_policy *out);

enum vos_wv_status vos_wv_parse_checkpoint(const uint8_t *buf,
                                           size_t len,
                                           struct vos_wv_checkpoint *out);

enum vos_wv_status vos_wv_parse_signature(const uint8_t *buf,
                                          size_t len,
                                          struct vos_wv_signature *out);

enum vos_wv_status vos_wv_parse_certificate(const uint8_t *buf,
                                            size_t len,
                                            struct vos_wv_signature *out_sigs,
                                            size_t max_sigs,
                                            size_t *out_count);

enum vos_wv_status vos_wv_parse_transition(const uint8_t *buf,
                                           size_t len,
                                           struct vos_wv_transition *out);

enum vos_wv_status vos_wv_parse_rebootstrap(const uint8_t *buf,
                                            size_t len,
                                            struct vos_wv_rebootstrap *out);

enum vos_wv_status vos_wv_client_init(struct vos_wv_client *client,
                                      const struct vos_wv_policy *initial_policy,
                                      const struct vos_wv_checkpoint *initial_pin,
                                      const struct vos_wv_hash *initial_generation,
                                      const uint8_t bootstrap_key[VOS_WV_KEY_BYTES]);

enum vos_wv_status vos_wv_verify_certificate(const struct vos_wv_policy *policy,
                                             enum vos_wv_stmt_kind stmt_kind,
                                             const struct vos_wv_checkpoint *checkpoint,
                                             const struct vos_wv_transition *terminal,
                                             const struct vos_wv_signature *sigs,
                                             size_t sig_count);

enum vos_wv_status vos_wv_admit(struct vos_wv_client *client,
                                const struct vos_wv_checkpoint *checkpoint,
                                const struct vos_wv_signature *sigs,
                                size_t sig_count,
                                const struct vos_wv_hash *base_image_root,
                                const struct vos_wv_hash *package_ids,
                                size_t package_count,
                                const struct vos_wv_hash *candidate_generation);

enum vos_wv_status vos_wv_transition(struct vos_wv_client *client,
                                     const struct vos_wv_transition *tr,
                                     const struct vos_wv_signature *old_seals,
                                     size_t old_seal_count,
                                     const struct vos_wv_signature *new_sigs,
                                     size_t new_sig_count);

enum vos_wv_status vos_wv_rebootstrap(struct vos_wv_client *client,
                                      const struct vos_wv_rebootstrap *rb,
                                      const struct vos_wv_signature *new_sigs,
                                      size_t new_sig_count);

#endif
