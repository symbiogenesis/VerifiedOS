// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_WASM_HOST_H
#define VOS_WASM_HOST_H

#include <stddef.h>
#include <stdint.h>

#include "vos_crypto_core.h"

/*
 * Bounded, GC-free C17 same-session Wasm application host lifecycle engine
 * for Q34f-i. Mirrors [WasmAppHost.v](../../proofs/WasmAppHost.v) and
 * [application-host.md](../../docs/implementation/contracts/application-host.md).
 */

enum {
    VOS_WHOST_DIGEST_BYTES = VOS_CRYPTO_DIGEST_BYTES,
    VOS_WHOST_KEY_BYTES = VOS_CRYPTO_KEY_BYTES_256,
    VOS_WHOST_MAX_HOSTS = 4u,
    VOS_WHOST_MAX_LABEL_BYTES = 64u,
    VOS_WHOST_MAX_MODULE_BYTES = 256u,
    VOS_WHOST_MAX_ASSETS_BYTES = 128u,
    VOS_WHOST_MAX_PENDING = 8u
};

enum vos_whost_phase {
    VOS_WHOST_PHASE_FREE = 0u,
    VOS_WHOST_PHASE_PREPARED = 1u,
    VOS_WHOST_PHASE_ACTIVE = 2u,
    VOS_WHOST_PHASE_CANCELLING = 3u,
    VOS_WHOST_PHASE_SWEEPING = 4u,
    VOS_WHOST_PHASE_SANITIZED = 5u,
    VOS_WHOST_PHASE_REUSABLE = 6u
};

enum vos_whost_status {
    VOS_WHOST_OK = 0,
    VOS_WHOST_ERR_INVALID_ARG = -1,
    VOS_WHOST_ERR_BAD_PHASE = -2,
    VOS_WHOST_ERR_FS_PATH_AUTHORITY = -3,
    VOS_WHOST_ERR_FORGED_CLOSURE = -4,
    VOS_WHOST_ERR_FORGED_DESCRIPTOR = -5,
    VOS_WHOST_ERR_INCOMPATIBLE_ABI = -6,
    VOS_WHOST_ERR_OVERSIZED_RESERVATION = -7,
    VOS_WHOST_ERR_OVER_SCOPED_GRANT = -8,
    VOS_WHOST_ERR_NO_STAGING = -9,
    VOS_WHOST_ERR_NO_CAPACITY = -10,
    VOS_WHOST_ERR_NO_CONSENT = -11,
    VOS_WHOST_ERR_CONSENT_DIGEST_MISMATCH = -12,
    VOS_WHOST_ERR_EPOCH_EXHAUSTED = -13,
    VOS_WHOST_ERR_GROUP_COLLISION = -14,
    VOS_WHOST_ERR_HANDLE_SCOPE = -15,
    VOS_WHOST_ERR_EPOCH_MISMATCH = -16,
    VOS_WHOST_ERR_POOL_CAP_EXPORT = -17,
    VOS_WHOST_ERR_TAGGED_TRANSPORT = -18,
    VOS_WHOST_ERR_YIELD_BOUND = -19,
    VOS_WHOST_ERR_PENDING_IMPORTS = -20,
    VOS_WHOST_ERR_NOT_SANITIZED = -21,
    VOS_WHOST_ERR_UNAUTH_CHECKPOINT = -22,
    VOS_WHOST_ERR_STALE_SCHEMA = -23,
    VOS_WHOST_ERR_INCOMPATIBLE_GEN = -24,
    VOS_WHOST_ERR_COMMIT_UNAUTHORIZED = -25,
    VOS_WHOST_ERR_POST_COMMIT_CLOSED = -26,
    VOS_WHOST_ERR_CRYPTO = -27
};

struct vos_whost_hash {
    uint8_t bytes[VOS_WHOST_DIGEST_BYTES];
};

struct vos_whost_policy {
    uint32_t abi_version;
    uint32_t profile_id;
    uint32_t generation;
    uint32_t mem_page_ceiling;
    uint32_t table_ceiling;
    uint32_t stack_ceiling;
    uint32_t import_ceiling_mask;
    uint32_t max_epoch;
};

struct vos_whost_bundle {
    struct vos_whost_hash bundle_digest;
    struct vos_whost_hash closure_digest;
    uint32_t module_len;
    uint8_t module_bytes[VOS_WHOST_MAX_MODULE_BYTES];
    uint32_t assets_len;
    uint8_t assets_bytes[VOS_WHOST_MAX_ASSETS_BYTES];
    uint32_t ui_label_len;
    uint8_t ui_label[VOS_WHOST_MAX_LABEL_BYTES];
    uint32_t abi_version;
    uint32_t core30_valid;
    uint32_t closure_valid;
    uint32_t descriptor_valid;
    uint32_t init_mem_pages;
    uint32_t max_mem_pages;
    uint32_t table_limit;
    uint32_t stack_limit;
    uint32_t schema_id;
    uint32_t requested_imports_mask;
    uint32_t has_start_fn;
    uint32_t uses_fs_path_authority;
};

struct vos_whost_consent {
    uint32_t user_consented;
    uint32_t credential_ok;
    struct vos_whost_hash trusted_digest;
    uint32_t ui_label_len;
    uint8_t ui_label_shown[VOS_WHOST_MAX_LABEL_BYTES];
    uint64_t nonce;
};

struct vos_whost_handle {
    uint64_t act_id;
    uint32_t epoch;
    uint32_t group_id;
    uint32_t import_bit;
    uint32_t scope_ok;
};

struct vos_whost_import_call {
    struct vos_whost_handle handle;
    uint32_t op_id;
    uint32_t exports_pool_cap;
    uint32_t tagged_transport;
    uint32_t reply_epoch;
    uint32_t yield_bounded;
};

struct vos_whost_durable {
    uint32_t valid;
    uint32_t acked;
    struct vos_whost_hash bundle_digest;
    uint32_t schema_id;
    struct vos_whost_hash state_digest;
};

struct vos_whost_checkpoint {
    struct vos_whost_hash bundle_digest;
    uint32_t abi_version;
    uint32_t profile_id;
    uint32_t schema_id;
    uint32_t generation;
    struct vos_whost_hash durable_digest;
    uint32_t embedded_old_grants_mask;
    uint32_t embedded_tagged_mem;
    uint64_t embedded_session_key;
    uint8_t hmac[VOS_WHOST_DIGEST_BYTES];
};

struct vos_whost_slot {
    uint32_t slot_id;
    uint32_t group_id;
    uint32_t phase;
    uint64_t act_id;
    uint32_t epoch;
    uint32_t epoch_retired;
    uint32_t has_prepared;
    struct vos_whost_bundle prepared;
    uint32_t has_active_bundle;
    struct vos_whost_bundle active_bundle;
    uint32_t active_grants_mask;
    uint64_t session_key;
    uint32_t tagged_mem;
    uint32_t start_executed;
    uint32_t new_grants_spent;
    uint32_t exec_stopped;
    uint32_t ingress_stopped;
    uint32_t pending_imports;
    uint32_t sweep_done;
    uint32_t zeroized;
    struct vos_whost_durable durable;
    uint8_t arena_canary[64];
};

struct vos_whost_pool {
    struct vos_whost_policy policy;
    uint8_t ckpt_auth_key[VOS_WHOST_KEY_BYTES];
    uint32_t avail_pages;
    uint32_t total_pages;
    uint32_t staging_avail;
    uint32_t quarantine_pages;
    uint64_t next_act_id;
    struct vos_whost_slot slots[VOS_WHOST_MAX_HOSTS];
};

struct vos_whost_replace_req {
    struct vos_whost_bundle candidate;
    const struct vos_whost_consent *consent;
    uint32_t new_grants_mask;
    uint32_t transition_reserved;
    uint32_t commit_authorized;
    uint32_t durable_policy_ok;
    uint32_t post_commit_ok;
    struct vos_whost_hash acked_durable_digest;
    uint32_t uses_fs_path_authority;
};

enum vos_whost_status vos_whost_pool_init(struct vos_whost_pool *pool,
                                          const struct vos_whost_policy *policy,
                                          const uint8_t ckpt_auth_key[VOS_WHOST_KEY_BYTES],
                                          uint32_t total_pages);

enum vos_whost_status vos_whost_compute_closure_digest(const struct vos_whost_bundle *bundle,
                                                       struct vos_whost_hash *out_digest);

enum vos_whost_status vos_whost_compute_bundle_digest(const struct vos_whost_bundle *bundle,
                                                      struct vos_whost_hash *out_digest);

enum vos_whost_status vos_whost_seal_checkpoint(const struct vos_whost_pool *pool,
                                                struct vos_whost_checkpoint *ckpt);

enum vos_whost_status vos_whost_prepare(struct vos_whost_pool *pool,
                                        uint32_t slot_id,
                                        const struct vos_whost_bundle *bundle);

enum vos_whost_status vos_whost_launch(struct vos_whost_pool *pool,
                                       uint32_t slot_id,
                                       const struct vos_whost_consent *consent,
                                       uint32_t initial_grants_mask,
                                       uint32_t uses_fs_path_authority,
                                       uint64_t new_session_key);

enum vos_whost_status vos_whost_invoke_import(const struct vos_whost_pool *pool,
                                              uint32_t slot_id,
                                              const struct vos_whost_import_call *call,
                                              uint32_t *out_reply_epoch);

enum vos_whost_status vos_whost_replace(struct vos_whost_pool *pool,
                                        uint32_t slot_id,
                                        const struct vos_whost_replace_req *req,
                                        uint64_t new_session_key);

enum vos_whost_status vos_whost_cancel_begin(struct vos_whost_pool *pool,
                                             uint32_t slot_id);

enum vos_whost_status vos_whost_drain_imports(struct vos_whost_pool *pool,
                                              uint32_t slot_id);

enum vos_whost_status vos_whost_enter_sweeping(struct vos_whost_pool *pool,
                                               uint32_t slot_id);

enum vos_whost_status vos_whost_sweep_and_zeroize(struct vos_whost_pool *pool,
                                                  uint32_t slot_id);

enum vos_whost_status vos_whost_complete_reuse(struct vos_whost_pool *pool,
                                               uint32_t slot_id);

enum vos_whost_status vos_whost_restore(struct vos_whost_pool *pool,
                                        uint32_t slot_id,
                                        const struct vos_whost_bundle *bundle,
                                        const struct vos_whost_checkpoint *ckpt,
                                        uint32_t current_grants_mask,
                                        uint64_t new_session_key);

#endif
