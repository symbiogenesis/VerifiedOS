// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_DEVICE_GEN_H
#define VOS_DEVICE_GEN_H

#include <stddef.h>
#include <stdint.h>

#include "vos_crypto_core.h"

/*
 * Bounded, GC-free C17 on-device generation coordinator for M6.10-i.
 * Reference specification: [DeviceGeneration.v](../../proofs/DeviceGeneration.v)
 * and [fixed-packages.md](../../docs/implementation/contracts/fixed-packages.md).
 */

enum {
    VOS_DGEN_DIGEST_BYTES = VOS_CRYPTO_DIGEST_BYTES,
    VOS_DGEN_KEY_BYTES = VOS_CRYPTO_KEY_BYTES_256,
    VOS_DGEN_MAX_PACKAGES = 16u,
    VOS_DGEN_MAX_CLOSURE = 16u,
    VOS_DGEN_MAX_CHECKED = 32u,
    VOS_DGEN_MAX_NONCES = 16u,
    VOS_DGEN_MAX_NAME_BYTES = 64u,
    VOS_DGEN_MAX_CODE_BYTES = 256u,
    VOS_DGEN_DEFAULT_STEP_BUDGET = 10000u,
    VOS_DGEN_DEFAULT_WORKSET_BYTES = 65536u
};

enum vos_dgen_status {
    VOS_DGEN_OK = 0,
    VOS_DGEN_ERR_INVALID_ARG = -1,
    VOS_DGEN_ERR_MODE_LOCKED = -2,
    VOS_DGEN_ERR_MODE_CERT = -3,
    VOS_DGEN_ERR_UNLOGGED_FETCH = -4,
    VOS_DGEN_ERR_PUBLISHER_PRESENT = -5,
    VOS_DGEN_ERR_CONSISTENCY = -6,
    VOS_DGEN_ERR_CORRUPT_OBJECT = -7,
    VOS_DGEN_ERR_TAMPERED_CHECKED_SET = -8,
    VOS_DGEN_ERR_BUDGET_EXCEEDED = -9,
    VOS_DGEN_ERR_PROOF_FAILED = -10,
    VOS_DGEN_ERR_TAL_STALE = -11,
    VOS_DGEN_ERR_GLOBAL_CHECK_FAILED = -12,
    VOS_DGEN_ERR_BASE_NOT_REPRODUCIBLE = -13,
    VOS_DGEN_ERR_NO_CONSENT = -14,
    VOS_DGEN_ERR_CREDENTIAL_ABSENT = -15,
    VOS_DGEN_ERR_CONSENT_MISMATCH = -16,
    VOS_DGEN_ERR_NONCE_REPLAY = -17,
    VOS_DGEN_ERR_EXPORT_FORBIDDEN = -18,
    VOS_DGEN_ERR_COMPOSER_PRIVILEGED = -19,
    VOS_DGEN_ERR_ROLLBACK_FLOOR = -20,
    VOS_DGEN_ERR_UNHEALTHY_ROLLBACK = -21,
    VOS_DGEN_ERR_NO_RETAINED = -22,
    VOS_DGEN_ERR_CRYPTO = -23
};

enum vos_dgen_origin {
    VOS_DGEN_ORIGIN_LOCAL_AUTHORED = 1u,
    VOS_DGEN_ORIGIN_FETCHED_LOGGED = 2u
};

enum vos_dgen_mode {
    VOS_DGEN_MODE_NORMAL = 0u,
    VOS_DGEN_MODE_COMPOSITION = 1u
};

struct vos_dgen_hash {
    uint8_t bytes[VOS_DGEN_DIGEST_BYTES];
};

struct vos_dgen_context {
    uint64_t spec_version;
    uint64_t model_version;
    uint64_t checker_id;
    uint64_t tier;
    uint64_t policy_epoch;
    uint64_t resource_epoch;
};

struct vos_dgen_closure_member {
    uint64_t member_id;
    uint32_t origin;
    uint32_t has_publisher;
    uint32_t logged_in_checkpoint;
    uint32_t consistent_with_pin;
    uint32_t inclusion_ok;
    struct vos_dgen_hash content_digest;
};

struct vos_dgen_package {
    uint64_t pkg_id;
    uint32_t is_base_image;
    uint32_t locally_composed;
    uint32_t has_publisher;
    uint32_t package_logged;
    struct vos_dgen_hash source_digest;
    struct vos_dgen_hash contract_digest;
    struct vos_dgen_hash code_digest;
    struct vos_dgen_hash init_digest;
    struct vos_dgen_hash proof_digest;
    struct vos_dgen_hash expected_base_digest;
    struct vos_dgen_hash expected_artifact_digest;
    uint32_t code_len;
    uint8_t code_bytes[VOS_DGEN_MAX_CODE_BYTES];
    uint32_t init_len;
    uint32_t proof_steps;
    uint32_t proof_workset_bytes;
    uint32_t proof_ok;
    uint32_t closure_count;
    struct vos_dgen_closure_member closure[VOS_DGEN_MAX_CLOSURE];
};

struct vos_dgen_checked_entry {
    uint64_t pkg_id;
    struct vos_dgen_hash artifact_digest;
    struct vos_dgen_hash source_digest;
    struct vos_dgen_hash contract_digest;
    struct vos_dgen_hash proof_digest;
    struct vos_dgen_context context;
};

struct vos_dgen_checked_set {
    uint32_t entry_count;
    struct vos_dgen_checked_entry entries[VOS_DGEN_MAX_CHECKED];
    uint8_t root_hmac[VOS_DGEN_DIGEST_BYTES];
};

struct vos_dgen_crypto_core {
    uint64_t key_id;
    uint32_t enrolled;
    uint32_t exportable;
    uint8_t signing_key[VOS_DGEN_KEY_BYTES];
    uint8_t checked_set_key[VOS_DGEN_KEY_BYTES];
    uint32_t used_nonce_count;
    uint64_t used_nonces[VOS_DGEN_MAX_NONCES];
};

struct vos_dgen_composer_cap {
    uint64_t composer_id;
    uint32_t holds_signing_key;
    uint32_t holds_mint_cap;
};

struct vos_dgen_prompt {
    struct vos_dgen_hash roster_hash;
    struct vos_dgen_hash gen_root;
    uint64_t nonce;
    uint32_t roster_name_len;
    uint8_t roster_name[VOS_DGEN_MAX_NAME_BYTES];
};

struct vos_dgen_consent {
    uint32_t credential_present;
    uint32_t user_consented;
    uint32_t consumed;
    struct vos_dgen_prompt prompt;
};

struct vos_dgen_mint_signature {
    uint64_t key_id;
    struct vos_dgen_hash roster_hash;
    struct vos_dgen_hash gen_root;
    uint64_t nonce;
    uint8_t mac[VOS_DGEN_DIGEST_BYTES];
};

struct vos_dgen_mode_guard {
    uint32_t mode;
    uint32_t priv_active;
    uint32_t switches;
};

struct vos_dgen_ab_slot {
    uint32_t valid;
    struct vos_dgen_hash root;
    struct vos_dgen_hash roster_hash;
    uint64_t version;
    uint64_t declared_floor;
    struct vos_dgen_mint_signature signature;
};

struct vos_dgen_ab_state {
    uint32_t live_is_b;
    uint64_t floor;
    uint32_t staged;
    uint32_t admitted;
    uint32_t has_retained;
    struct vos_dgen_ab_slot slot_a;
    struct vos_dgen_ab_slot slot_b;
};

struct vos_dgen_occupancy {
    uint32_t total_package_bytes;
    uint32_t total_proof_workset_bytes;
    uint32_t total_proof_steps;
    uint32_t reused_packages;
    uint32_t fresh_checked_packages;
    uint32_t staged_slots_used;
    uint32_t mode_switches;
};

struct vos_dgen_device {
    struct vos_dgen_crypto_core core;
    struct vos_dgen_composer_cap composer;
    struct vos_dgen_mode_guard mode_guard;
    struct vos_dgen_checked_set checked_set;
    struct vos_dgen_context context;
    struct vos_dgen_ab_state ab;
    uint64_t pinned_checkpoint_id;
    uint32_t step_budget;
    uint32_t workset_budget;
    struct vos_dgen_occupancy last_occupancy;
};

struct vos_dgen_request {
    uint32_t network_reachable;
    uint64_t version;
    uint64_t declared_floor;
    uint32_t package_count;
    struct vos_dgen_package packages[VOS_DGEN_MAX_PACKAGES];
    uint32_t tal_layout_fresh_ok;
    uint32_t wiring_fresh_ok;
    uint32_t global_resource_ok;
    uint32_t cic_checker_available;
    uint32_t mode_cert_valid;
    uint32_t mode_guard_ok;
    uint32_t mode_dwell_ok;
    uint32_t mode_recovery_reserved;
};

enum vos_dgen_status vos_dgen_device_init(struct vos_dgen_device *dev,
                                          uint64_t key_id,
                                          const uint8_t signing_key[VOS_DGEN_KEY_BYTES],
                                          const uint8_t checked_set_key[VOS_DGEN_KEY_BYTES],
                                          const struct vos_dgen_context *ctx,
                                          const struct vos_dgen_hash *initial_root,
                                          uint64_t initial_version,
                                          uint64_t floor,
                                          uint32_t step_budget,
                                          uint32_t workset_budget);

enum vos_dgen_status vos_dgen_compute_artifact_digest(const struct vos_dgen_package *pkg,
                                                      const struct vos_dgen_context *ctx,
                                                      struct vos_dgen_hash *out_digest);

enum vos_dgen_status vos_dgen_compute_roster_hash(const struct vos_dgen_package *pkgs,
                                                  uint32_t package_count,
                                                  const struct vos_dgen_context *ctx,
                                                  struct vos_dgen_hash *out_hash);

enum vos_dgen_status vos_dgen_compute_gen_root(uint64_t version,
                                               uint64_t declared_floor,
                                               const struct vos_dgen_hash *roster_hash,
                                               const struct vos_dgen_context *ctx,
                                               struct vos_dgen_hash *out_root);

enum vos_dgen_status vos_dgen_checked_set_seal(const struct vos_dgen_crypto_core *core,
                                               struct vos_dgen_checked_set *set);

enum vos_dgen_status vos_dgen_checked_set_verify(const struct vos_dgen_crypto_core *core,
                                                 const struct vos_dgen_checked_set *set);

enum vos_dgen_status vos_dgen_mode_enter(struct vos_dgen_mode_guard *guard,
                                         uint32_t cert_valid,
                                         uint32_t guard_ok,
                                         uint32_t dwell_ok,
                                         uint32_t recovery_reserved);

void vos_dgen_mode_exit(struct vos_dgen_mode_guard *guard);

enum vos_dgen_status vos_dgen_audit_offline_package(uint32_t network_reachable,
                                                    const struct vos_dgen_package *pkg);

enum vos_dgen_status vos_dgen_core_export_key(const struct vos_dgen_crypto_core *core,
                                              uint8_t out_key[VOS_DGEN_KEY_BYTES]);

enum vos_dgen_status vos_dgen_trusted_path_mint(struct vos_dgen_crypto_core *core,
                                                const struct vos_dgen_composer_cap *composer,
                                                const struct vos_dgen_hash *roster_hash,
                                                const struct vos_dgen_hash *gen_root,
                                                struct vos_dgen_consent *consent,
                                                struct vos_dgen_mint_signature *out_sig);

enum vos_dgen_status vos_dgen_compose_and_admit(struct vos_dgen_device *dev,
                                                const struct vos_dgen_request *req,
                                                struct vos_dgen_consent *consent);

enum vos_dgen_status vos_dgen_health_check(struct vos_dgen_device *dev,
                                            uint32_t healthy);

const struct vos_dgen_ab_slot *vos_dgen_live_slot(const struct vos_dgen_device *dev);

const struct vos_dgen_ab_slot *vos_dgen_spare_slot(const struct vos_dgen_device *dev);

#endif
