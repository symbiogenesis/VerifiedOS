// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_RESIDENT_TC_H
#define VOS_RESIDENT_TC_H

#include <stddef.h>
#include <stdint.h>

#include "vos_crypto_core.h"

/*
 * Bounded, GC-free C17 resident toolchain admissibility, pass-activation,
 * and bootstrap-reproduction coordinator for M1.10-i.
 * Reference specification: [ResidentToolchain.v](../../proofs/ResidentToolchain.v).
 */

enum {
    VOS_RTC_DIGEST_BYTES = VOS_CRYPTO_DIGEST_BYTES,
    VOS_RTC_MAX_LICENSES = 16u,
    VOS_RTC_MAX_CLOSURE = 16u,
    VOS_RTC_MAX_COMPARTMENTS = 16u,
    VOS_RTC_MAX_ACTIVATIONS = 16u,
    VOS_RTC_MAX_NAME_BYTES = 64u,
    VOS_RTC_MAX_CODE_BYTES = 256u
};

enum vos_rtc_status {
    VOS_RTC_OK = 0,
    VOS_RTC_ERR_INVALID_ARG = -1,
    VOS_RTC_ERR_LICENSE_UNREAD = -2,
    VOS_RTC_ERR_NONCOMMERCIAL_NO_GRANT = -3,
    VOS_RTC_ERR_MISSING_COMMERCIAL_GRANT = -4,
    VOS_RTC_ERR_OUTSIDE_DUAL_SUBSET = -5,
    VOS_RTC_ERR_AMBIENT_AUTHORITY = -6,
    VOS_RTC_ERR_UNCOVERED_UNSAFE = -7,
    VOS_RTC_ERR_UNSAFE_EXCEPTION = -8,
    VOS_RTC_ERR_UNRESOLVED_HOST_ASSUMP = -9,
    VOS_RTC_ERR_UNESTIMATED_SUBPORT = -10,
    VOS_RTC_ERR_EXEC_OWN_OUTPUT = -11,
    VOS_RTC_ERR_FORBIDDEN_AUTH = -12,
    VOS_RTC_ERR_ORDER_VIOLATION = -13,
    VOS_RTC_ERR_WRONG_POOL = -14,
    VOS_RTC_ERR_POOL_LIFECYCLE = -15,
    VOS_RTC_ERR_NOT_RESUMABLE = -16,
    VOS_RTC_ERR_STEP_BUDGET_EXCEEDED = -17,
    VOS_RTC_ERR_CAPACITY_EXHAUSTED = -18,
    VOS_RTC_ERR_RESIDENCY_EXCEEDED = -19,
    VOS_RTC_ERR_BOOTSTRAP_DIVERGED = -20,
    VOS_RTC_ERR_CLOSED_DEBRUIJN_CLAIM = -21,
    VOS_RTC_ERR_CRYPTO = -22
};

enum vos_rtc_license_route {
    VOS_RTC_ROUTE_INDEPENDENT_IMPL = 1u,
    VOS_RTC_ROUTE_COMMERCIAL_GRANT = 2u,
    VOS_RTC_ROUTE_DUAL_LICENSED_SUBSET = 3u,
    VOS_RTC_ROUTE_NONCOMMERCIAL_ONLY = 4u
};

enum vos_rtc_closure_disp {
    VOS_RTC_DISP_CLEAN = 1u,
    VOS_RTC_DISP_DELETED = 2u,
    VOS_RTC_DISP_VERIFIED_HAL_OR_PROOF = 3u,
    VOS_RTC_DISP_NAMED_SUBPORT = 4u,
    VOS_RTC_DISP_UNSAFE_EXCEPTION = 5u,
    VOS_RTC_DISP_UNRESOLVED_AMBIENT = 6u
};

enum vos_rtc_role {
    VOS_RTC_ROLE_TYPE_CHECKER = 0u,
    VOS_RTC_ROLE_PROVER = 1u,
    VOS_RTC_ROLE_COMPILER = 2u,
    VOS_RTC_ROLE_COMPOSER = 3u,
    VOS_RTC_ROLE_PACKAGE_BUILDER = 4u
};

enum vos_rtc_pool_lifecycle {
    VOS_RTC_POOL_FREE = 0u,
    VOS_RTC_POOL_BOUND = 1u,
    VOS_RTC_POOL_QUIESCING = 2u,
    VOS_RTC_POOL_REVOKED = 3u,
    VOS_RTC_POOL_SWEEPING = 4u,
    VOS_RTC_POOL_REUSABLE = 5u
};

enum vos_rtc_reading {
    VOS_RTC_READING_A = 1u,
    VOS_RTC_READING_B = 2u
};

enum vos_rtc_root_status {
    VOS_RTC_ROOT_RELOCATED = 1u,
    VOS_RTC_ROOT_CLOSED = 2u
};

enum vos_rtc_divergence_cause {
    VOS_RTC_CAUSE_NONE = 0u,
    VOS_RTC_CAUSE_SOURCE_MISMATCH = 1u,
    VOS_RTC_CAUSE_SWITCH_MISMATCH = 2u,
    VOS_RTC_CAUSE_ARTIFACT_MISMATCH = 3u,
    VOS_RTC_CAUSE_DEVICE_ADMISSION_REFUSED = 4u,
    VOS_RTC_CAUSE_HOST_ADMISSION_REFUSED = 5u,
    VOS_RTC_CAUSE_DDC_OR_ROT_INCOMPLETE = 6u,
    VOS_RTC_CAUSE_CLOSED_BOOTSTRAP_CLAIMED = 7u
};

struct vos_rtc_hash {
    uint8_t bytes[VOS_RTC_DIGEST_BYTES];
};

struct vos_rtc_component_license {
    uint64_t comp_id;
    uint32_t route;
    uint32_t read_at_incorporation;
    uint32_t has_noncommercial_pass;
    uint32_t has_commercial_grant;
    uint32_t dual_subset_only;
    uint32_t provides_required_backend;
};

struct vos_rtc_closure_unit {
    uint64_t unit_id;
    uint32_t unsafe_sites;
    uint32_t unsafe_hal_or_proof_ok;
    uint32_t ambient_authority;
    uint32_t has_filesystem;
    uint32_t has_subprocess;
    uint32_t has_host_allocator;
    uint32_t disposition;
    uint32_t subport_id;
    uint32_t subport_estimated;
};

struct vos_rtc_compartment_caps {
    uint64_t comp_id;
    uint32_t role;
    uint32_t exec_over_own_output;
    uint32_t sealing_auth;
    uint32_t wiring_auth;
    uint32_t store_consent_grant;
};

struct vos_rtc_bounded_pool {
    uint32_t pool_id;
    uint64_t owner_id;
    uint32_t capacity_bytes;
    uint32_t low_threshold;
    uint32_t exhausted_threshold;
    uint32_t used_bytes;
    uint32_t peak_bytes;
    uint32_t lifecycle;
};

struct vos_rtc_pass_activation {
    uint32_t pass_id;
    uint32_t role;
    uint32_t pool_id;
    uint32_t step_budget;
    uint32_t steps_used;
    uint32_t alloc_bytes;
    uint32_t pass_peak_bytes;
    uint32_t resumable;
    uint32_t checkpoint_saved;
};

struct vos_rtc_pool_sharing_proof {
    uint32_t disjoint_live_ranges;
    uint32_t frame_or_region_proven;
    uint32_t assumed_correlation_only;
    uint32_t temporal_barrier_ok;
};

struct vos_rtc_residency_spec {
    uint32_t reading;
    uint32_t ordinary_bytes;
    uint32_t compiler_peak_bytes;
    uint32_t prover_peak_bytes;
    uint32_t first_class_cap_bytes;
    struct vos_rtc_pool_sharing_proof sharing;
};

struct vos_rtc_build_receipt {
    struct vos_rtc_hash source_digest;
    struct vos_rtc_hash switch_digest;
    struct vos_rtc_hash artifact_digest;
    uint32_t tal_admitted;
    uint32_t cic_admitted;
    uint32_t ddc_checked;
    uint32_t rot_measured;
    uint32_t root_status;
    struct vos_rtc_hash receipt_digest;
};

struct vos_rtc_bootstrap_verdict {
    uint32_t reproduced;
    uint32_t cause;
    uint32_t root_status;
};

struct vos_rtc_state {
    uint64_t running_generation;
    uint32_t last_peak_bytes;
    uint32_t admitted_runs;
    struct vos_rtc_bootstrap_verdict last_verdict;
};

struct vos_rtc_request {
    uint32_t license_count;
    struct vos_rtc_component_license licenses[VOS_RTC_MAX_LICENSES];
    uint32_t closure_count;
    struct vos_rtc_closure_unit closure[VOS_RTC_MAX_CLOSURE];
    uint32_t compartment_count;
    struct vos_rtc_compartment_caps compartments[VOS_RTC_MAX_COMPARTMENTS];
    struct vos_rtc_bounded_pool pool;
    uint32_t activation_count;
    struct vos_rtc_pass_activation activations[VOS_RTC_MAX_ACTIVATIONS];
    struct vos_rtc_residency_spec residency;
    struct vos_rtc_build_receipt host_receipt;
    struct vos_rtc_build_receipt dev_receipt;
};

enum vos_rtc_status vos_rtc_state_init(struct vos_rtc_state *state,
                                       uint64_t running_generation);

enum vos_rtc_status vos_rtc_compute_artifact_digest(uint64_t pkg_id,
                                                    const uint8_t *code_bytes,
                                                    uint32_t code_len,
                                                    const struct vos_rtc_hash *source_digest,
                                                    struct vos_rtc_hash *out_digest);

enum vos_rtc_status vos_rtc_compute_receipt_digest(const struct vos_rtc_build_receipt *rec,
                                                   struct vos_rtc_hash *out_digest);

enum vos_rtc_status vos_rtc_screen_license(const struct vos_rtc_component_license *lic);

enum vos_rtc_status vos_rtc_audit_closure(const struct vos_rtc_closure_unit *unit,
                                          uint32_t *out_subport_id);

enum vos_rtc_status vos_rtc_check_compartment_caps(const struct vos_rtc_compartment_caps *caps);

enum vos_rtc_status vos_rtc_check_smallest_loop_first(
    const struct vos_rtc_compartment_caps *comps,
    uint32_t count);

uint32_t vos_rtc_pools_can_share(const struct vos_rtc_pool_sharing_proof *proof);

uint32_t vos_rtc_toolchain_pool_charge(uint32_t compiler_peak,
                                       uint32_t prover_peak,
                                       const struct vos_rtc_pool_sharing_proof *proof,
                                       uint32_t *out_overflow);

enum vos_rtc_status vos_rtc_check_residency(const struct vos_rtc_residency_spec *spec,
                                            uint32_t *out_charge);

enum vos_rtc_status vos_rtc_run_activation(struct vos_rtc_bounded_pool *pool,
                                           const struct vos_rtc_pass_activation *act,
                                           uint32_t *out_recorded_peak);

enum vos_rtc_status vos_rtc_compare_bootstrap_receipts(
    const struct vos_rtc_build_receipt *host,
    const struct vos_rtc_build_receipt *dev,
    struct vos_rtc_bootstrap_verdict *out_verdict);

enum vos_rtc_status vos_rtc_run_cycle(struct vos_rtc_state *state,
                                      const struct vos_rtc_request *req,
                                      struct vos_rtc_bootstrap_verdict *out_verdict);

#endif
