// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_COMPAT_WORKFLOW_H
#define VOS_COMPAT_WORKFLOW_H

#include <stddef.h>
#include <stdint.h>

#include "vos_crypto_core.h"

/*
 * Bounded, GC-free C17 compatibility workflow service for Q9-i.
 * Reference specification: [CompatibilityWorkflow.v](../../proofs/CompatibilityWorkflow.v)
 * and [compatibility.md](../../docs/implementation/contracts/compatibility.md).
 */

enum {
    VOS_COMPAT_DIGEST_BYTES = VOS_CRYPTO_DIGEST_BYTES,
    VOS_COMPAT_MAX_SOURCE_SLICE = 256u,
    VOS_COMPAT_MAX_STAGED_BYTES = 1024u,
    VOS_COMPAT_MAX_CHUNK_BYTES = 256u,
    VOS_COMPAT_MAX_PARTIAL_OBJS = 4u,
    VOS_COMPAT_MAX_STAGED_OBJS = 8u,
    VOS_COMPAT_MAX_JOBS = 4u,
    VOS_COMPAT_MAX_DIAG_RECORDS = 8u,
    VOS_COMPAT_MAX_DIAG_RECORD_BYTES = 64u,
    VOS_COMPAT_MAX_DIAG_BYTES = 256u,
    VOS_COMPAT_MAX_CACHE_ENTRIES = 8u,
    VOS_COMPAT_MAX_ROSTER_ENTRIES = 16u,
    VOS_COMPAT_MAX_RESULT_BYTES = 256u,
    VOS_COMPAT_POOL_COUNT = 8u,
    VOS_COMPAT_DIAG_TRUNCATED_MARKER = 0x5452554Eu
};

enum vos_compat_status {
    VOS_COMPAT_OK = 0,
    VOS_COMPAT_ERR_INVALID_ARG = -1,
    VOS_COMPAT_ERR_AUTHORITY = -2,
    VOS_COMPAT_ERR_INVALID_PROFILE = -3,
    VOS_COMPAT_ERR_MISSING_GRANT = -4,
    VOS_COMPAT_ERR_WRONG_OBJECT_OR_VERSION = -5,
    VOS_COMPAT_ERR_OUT_OF_RANGE = -6,
    VOS_COMPAT_ERR_INDEX_EXHAUSTED = -7,
    VOS_COMPAT_ERR_STAGING_OVER_BUDGET = -8,
    VOS_COMPAT_ERR_STAGING_SEQUENCE = -9,
    VOS_COMPAT_ERR_STAGING_INCOMPLETE = -10,
    VOS_COMPAT_ERR_STAGING_DIGEST = -11,
    VOS_COMPAT_ERR_MISSING_CLOSURE = -12,
    VOS_COMPAT_ERR_COMP_SERVICE = -13,
    VOS_COMPAT_ERR_JOB_POOL_EXHAUSTED = -14,
    VOS_COMPAT_ERR_EPOCH_EXHAUSTED = -15,
    VOS_COMPAT_ERR_STALE_HANDLE = -16,
    VOS_COMPAT_ERR_BUDGET_EXPANSION = -17,
    VOS_COMPAT_ERR_PASS_ARENA_EXHAUSTED = -18,
    VOS_COMPAT_ERR_JOB_NOT_ACTIVE = -19,
    VOS_COMPAT_ERR_LIFECYCLE_INTERRUPTED = -20,
    VOS_COMPAT_ERR_PROOF_INCOMPLETE = -21,
    VOS_COMPAT_ERR_CHECKING_ARENA = -22,
    VOS_COMPAT_ERR_CHECKING_STEPS = -23,
    VOS_COMPAT_ERR_INADMISSIBLE_ROSTER = -24,
    VOS_COMPAT_ERR_TAL_OR_CORR = -25,
    VOS_COMPAT_ERR_CACHE_MISS = -26,
    VOS_COMPAT_ERR_NO_ADMITTED = -27,
    VOS_COMPAT_ERR_CONSENT_MISMATCH = -28,
    VOS_COMPAT_ERR_CONSENT_POOL_EXHAUSTED = -29,
    VOS_COMPAT_ERR_ON_DIE_CRED_ABSENT = -30,
    VOS_COMPAT_ERR_EXTERNAL_AUTH_DECLINED = -31,
    VOS_COMPAT_ERR_NOT_BOOTED = -32,
    VOS_COMPAT_ERR_RESULT_UNBOUND = -33,
    VOS_COMPAT_ERR_RESULT_OVER_BUDGET = -34,
    VOS_COMPAT_ERR_SAME_GEN_NATIVE_EXEC = -35,
    VOS_COMPAT_ERR_REWRITE_ROSTER = -36,
    VOS_COMPAT_ERR_RUNTIME_PLUGIN = -37,
    VOS_COMPAT_ERR_EXTERNAL_PATH = -38,
    VOS_COMPAT_ERR_BYPASS_CHECKING = -39,
    VOS_COMPAT_ERR_CRYPTO = -40
};

enum vos_compat_pool_id {
    VOS_COMPAT_POOL_SOURCE_INDEX = 0u,
    VOS_COMPAT_POOL_EDITED_STAGING = 1u,
    VOS_COMPAT_POOL_BUILD_JOBS = 2u,
    VOS_COMPAT_POOL_PASS_ARENAS = 3u,
    VOS_COMPAT_POOL_DIAGNOSTICS_BUFFER = 4u,
    VOS_COMPAT_POOL_PROOF_CACHE = 5u,
    VOS_COMPAT_POOL_CANDIDATE_CLOSURE = 6u,
    VOS_COMPAT_POOL_CONSENT_TRANSFER = 7u
};

enum vos_compat_lifecycle {
    VOS_COMPAT_LC_FREE = 0u,
    VOS_COMPAT_LC_BOUND = 1u,
    VOS_COMPAT_LC_QUIESCING = 2u,
    VOS_COMPAT_LC_REVOKED = 3u,
    VOS_COMPAT_LC_SWEEPING = 4u,
    VOS_COMPAT_LC_REUSABLE = 5u
};

enum vos_compat_lifecycle_action {
    VOS_COMPAT_ACT_BIND = 0u,
    VOS_COMPAT_ACT_QUIESCE = 1u,
    VOS_COMPAT_ACT_REVOKE = 2u,
    VOS_COMPAT_ACT_SWEEP = 3u,
    VOS_COMPAT_ACT_RELEASE = 4u,
    VOS_COMPAT_ACT_INTERRUPT = 5u
};

enum vos_compat_job_stage {
    VOS_COMPAT_JOB_EMPTY = 0u,
    VOS_COMPAT_JOB_RUNNING = 1u,
    VOS_COMPAT_JOB_COMPLETED = 2u,
    VOS_COMPAT_JOB_FAILED = 3u,
    VOS_COMPAT_JOB_CANCELLED = 4u
};

enum vos_compat_forbidden_op {
    VOS_COMPAT_FORBID_EXEC_STAGED_NATIVE = 0u,
    VOS_COMPAT_FORBID_REWRITE_RUNNING_ROSTER = 1u,
    VOS_COMPAT_FORBID_INSTALL_RUNTIME_PLUGIN = 2u,
    VOS_COMPAT_FORBID_LOAD_EXTERNAL_PATH = 3u,
    VOS_COMPAT_FORBID_BYPASS_CHECKING = 4u,
    VOS_COMPAT_FORBID_WASM_NATIVE_ESCAPE = 5u
};

struct vos_compat_hash {
    uint8_t bytes[VOS_COMPAT_DIGEST_BYTES];
};

struct vos_compat_editor_auth {
    uint32_t private_source_ep;
    uint32_t private_result_ep;
    uint32_t holds_exec_staged;
    uint32_t holds_signing_key;
    uint32_t holds_mint_cap;
    uint32_t holds_sealing_cap;
    uint32_t holds_wiring_cap;
    uint32_t holds_boot_select_cap;
};

struct vos_compat_builder_auth {
    uint32_t immutable_closure_ok;
    uint32_t output_reservation_ok;
    uint32_t diagnostics_ep_ok;
    uint32_t holds_exec_staged;
    uint32_t holds_sealing_cap;
    uint32_t holds_wiring_cap;
    uint32_t holds_signing_key;
};

struct vos_compat_pool_decl {
    uint32_t kind;
    uint32_t max_capacity;
    uint32_t low_threshold;
    uint32_t exhausted_threshold;
    uint32_t release_bound_ticks;
    uint32_t recovery_reserve;
    uint32_t has_owning_compartment;
    uint32_t has_derivation_source;
    uint32_t has_bind_release_caps;
    uint32_t has_thresholds;
    uint32_t has_release_bound;
    uint32_t has_lifecycle;
    uint32_t has_recovery_reserve;
    uint32_t has_confidentiality;
    uint32_t has_telemetry;
    uint32_t has_restart_semantics;
};

struct vos_compat_profile {
    uint64_t profile_id;
    uint32_t predeclared;
    uint64_t toolchain_id;
    uint64_t config_id;
    uint32_t step_budget;
    struct vos_compat_pool_decl pools[VOS_COMPAT_POOL_COUNT];
    uint32_t max_source_edges;
    uint32_t max_source_depth;
    uint32_t max_chunk_bytes;
    uint32_t max_partial_objects;
    uint32_t epoch_limit;
    uint32_t max_diag_record_bytes;
    uint32_t max_diag_bytes;
    uint32_t max_checking_steps;
    uint32_t max_result_bytes;
    uint32_t ordinary_borrows_comp;
};

struct vos_compat_cache_identity {
    struct vos_compat_hash source_digest;
    struct vos_compat_hash dep_closure_digest;
    struct vos_compat_hash imported_lemma_digest;
    struct vos_compat_hash semantics_digest;
    struct vos_compat_hash config_digest;
    struct vos_compat_hash assumption_digest;
    uint64_t profile_id;
};

struct vos_compat_cache_entry {
    uint32_t valid;
    struct vos_compat_cache_identity identity;
    struct vos_compat_hash key_digest;
    struct vos_compat_hash proof_digest;
    uint32_t verified;
};

struct vos_compat_source_obj {
    uint64_t obj_id;
    uint64_t version;
    uint32_t grant_ok;
    uint32_t total_bytes;
    uint8_t bytes[VOS_COMPAT_MAX_STAGED_BYTES];
};

struct vos_compat_partial_stage {
    uint32_t active;
    uint64_t slot_id;
    uint32_t next_seq;
    uint32_t declared_total;
    uint32_t accum_bytes;
    uint8_t bytes[VOS_COMPAT_MAX_STAGED_BYTES];
};

struct vos_compat_staged_obj {
    uint32_t valid;
    uint64_t obj_id;
    uint32_t total_bytes;
    uint32_t executable;
    struct vos_compat_hash content_digest;
    uint8_t bytes[VOS_COMPAT_MAX_STAGED_BYTES];
};

struct vos_compat_diag_record {
    uint32_t seq;
    uint32_t len;
    uint32_t is_truncation_marker;
    uint8_t text[VOS_COMPAT_MAX_DIAG_RECORD_BYTES];
};

struct vos_compat_diag_view {
    uint32_t record_count;
    uint32_t total_bytes;
    uint32_t truncated;
    uint32_t marker_code;
    struct vos_compat_diag_record records[VOS_COMPAT_MAX_DIAG_RECORDS];
};

struct vos_compat_build_job {
    uint32_t handle_slot;
    uint32_t epoch;
    uint32_t lifecycle;
    uint32_t stage;
    struct vos_compat_hash closure_digest;
    uint64_t profile_id;
    uint32_t step_budget;
    uint32_t steps_used;
    struct vos_compat_hash output_digest;
    uint32_t output_executable;
    uint32_t diag_count;
    uint32_t diag_bytes;
    uint32_t diag_truncated;
    struct vos_compat_diag_record diags[VOS_COMPAT_MAX_DIAG_RECORDS];
};

struct vos_compat_admission_pkg {
    uint32_t job_slot;
    uint32_t job_epoch;
    uint32_t proof_complete;
    uint32_t checking_arena_ok;
    uint32_t checking_steps;
    uint32_t roster_entries;
    uint32_t roster_valid;
    uint32_t tal_ok;
    uint32_t source_corr_ok;
    uint32_t cache_hit_used;
    struct vos_compat_cache_identity cache_id;
    struct vos_compat_hash candidate_root;
    struct vos_compat_hash candidate_roster_hash;
};

struct vos_compat_consent_req {
    struct vos_compat_hash candidate_root;
    struct vos_compat_hash roster_hash;
    uint32_t user_consented;
    uint32_t on_die_cred_ok;
    uint32_t external_roaming_key;
};

struct vos_compat_test_result {
    uint32_t grant_ok;
    struct vos_compat_hash candidate_root;
    uint64_t test_id;
    uint64_t boot_epoch;
    uint32_t result_bytes;
    uint32_t passed;
    uint8_t payload[VOS_COMPAT_MAX_RESULT_BYTES];
};

struct vos_compat_service {
    struct vos_compat_editor_auth editor_auth;
    struct vos_compat_builder_auth builder_auth;
    struct vos_compat_profile profile;
    struct vos_compat_hash running_gen_root;
    struct vos_compat_hash running_roster_hash;
    uint64_t boot_epoch;
    uint32_t next_job_epoch;
    uint32_t epoch_retired;
    struct vos_compat_partial_stage partials[VOS_COMPAT_MAX_PARTIAL_OBJS];
    uint32_t staged_count;
    struct vos_compat_staged_obj staged[VOS_COMPAT_MAX_STAGED_OBJS];
    struct vos_compat_build_job jobs[VOS_COMPAT_MAX_JOBS];
    uint32_t cache_write_cursor;
    struct vos_compat_cache_entry proof_cache[VOS_COMPAT_MAX_CACHE_ENTRIES];
    uint32_t has_admitted;
    struct vos_compat_hash admitted_root;
    struct vos_compat_hash admitted_roster_hash;
    uint32_t consent_granted;
    uint32_t consent_outstanding;
    uint32_t successor_booted;
    uint32_t has_last_test_result;
    struct vos_compat_test_result last_test_result;
};

enum vos_compat_status vos_compat_service_init(struct vos_compat_service *svc,
                                             const struct vos_compat_editor_auth *editor_auth,
                                             const struct vos_compat_builder_auth *builder_auth,
                                             const struct vos_compat_profile *profile,
                                             const struct vos_compat_hash *initial_root,
                                             const struct vos_compat_hash *initial_roster);

enum vos_compat_status vos_compat_profile_validate(const struct vos_compat_profile *profile);

enum vos_compat_status vos_compat_lifecycle_step(uint32_t current_state,
                                                 uint32_t action,
                                                 uint32_t *next_state_out);

enum vos_compat_status vos_compat_compute_cache_key(const struct vos_compat_cache_identity *id,
                                                    struct vos_compat_hash *out_key);

int vos_compat_cache_lookup(const struct vos_compat_service *svc,
                            const struct vos_compat_cache_identity *id,
                            struct vos_compat_cache_entry *out_entry);

enum vos_compat_status vos_compat_read_source_slice(const struct vos_compat_service *svc,
                                                const struct vos_compat_source_obj *src,
                                                uint64_t req_obj_id,
                                                uint64_t req_version,
                                                uint32_t offset,
                                                uint32_t len,
                                                uint32_t index_objs,
                                                uint32_t index_edges,
                                                uint32_t index_depth,
                                                uint8_t *out_bytes,
                                                uint32_t *out_len);

enum vos_compat_status vos_compat_stage_edited_source(struct vos_compat_service *svc,
                                                  uint32_t reservation_ok,
                                                  uint64_t slot_id,
                                                  uint32_t seq,
                                                  uint32_t declared_total,
                                                  const uint8_t *chunk_bytes,
                                                  uint32_t chunk_len,
                                                  const struct vos_compat_hash *expected_digest,
                                                  uint32_t is_final,
                                                  struct vos_compat_staged_obj *out_staged);

enum vos_compat_status vos_compat_submit_build(struct vos_compat_service *svc,
                                             uint32_t closure_ok,
                                             uint32_t comp_service_ep_ok,
                                             const struct vos_compat_hash *closure_digest,
                                             uint32_t closure_objs,
                                             uint32_t closure_edges,
                                             uint32_t closure_depth,
                                             uint64_t toolchain_id,
                                             uint64_t config_id,
                                             const struct vos_compat_profile *req_profile,
                                             uint32_t *out_slot,
                                             uint32_t *out_epoch);

enum vos_compat_status vos_compat_advance_build(struct vos_compat_service *svc,
                                              uint32_t slot,
                                              uint32_t epoch,
                                              uint32_t steps_req,
                                              uint32_t workset_bytes,
                                              const struct vos_compat_hash *output_digest,
                                              const uint8_t *diag_msg,
                                              uint32_t diag_msg_len,
                                              uint32_t finish_build);

enum vos_compat_status vos_compat_read_diagnostics(const struct vos_compat_service *svc,
                                                 uint32_t slot,
                                                 uint32_t epoch,
                                                 uint32_t result_ep_ok,
                                                 uint32_t seq_start,
                                                 uint32_t max_records,
                                                 uint32_t max_bytes,
                                                 struct vos_compat_diag_view *out_view);

enum vos_compat_status vos_compat_cancel_build(struct vos_compat_service *svc,
                                             uint32_t slot,
                                             uint32_t epoch,
                                             uint32_t cancel_cap_ok,
                                             uint32_t interrupt_mid_sweep);

enum vos_compat_status vos_compat_submit_successor_admission(struct vos_compat_service *svc,
                                                           const struct vos_compat_admission_pkg *pkg);

enum vos_compat_status vos_compat_request_generation_consent(struct vos_compat_service *svc,
                                                           const struct vos_compat_consent_req *req);

enum vos_compat_status vos_compat_boot_successor(struct vos_compat_service *svc);

enum vos_compat_status vos_compat_read_successor_test_result(struct vos_compat_service *svc,
                                                           const struct vos_compat_test_result *res,
                                                           const struct vos_compat_hash *expected_root,
                                                           uint64_t expected_test_id,
                                                           struct vos_compat_test_result *out_res);

enum vos_compat_status vos_compat_attempt_forbidden_op(const struct vos_compat_service *svc,
                                                       uint32_t forbidden_op);

#endif
