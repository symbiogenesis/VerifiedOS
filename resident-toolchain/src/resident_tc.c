// SPDX-License-Identifier: Apache-2.0
#include "vos_resident_tc.h"

#include <string.h>

static void zero_bytes(uint8_t *dst, size_t len)
{
    if (dst == NULL) {
        return;
    }
    volatile uint8_t *wipe = dst;
    for (size_t i = 0u; i < len; ++i) {
        wipe[i] = 0u;
    }
}

static int equal_bytes_ct(const uint8_t *a, const uint8_t *b, size_t len)
{
    uint8_t diff = 0u;
    for (size_t i = 0u; i < len; ++i) {
        diff |= (uint8_t)(a[i] ^ b[i]);
    }
    return diff == 0u;
}

static int equal_hashes(const struct vos_rtc_hash *a, const struct vos_rtc_hash *b)
{
    return equal_bytes_ct(a->bytes, b->bytes, VOS_RTC_DIGEST_BYTES);
}

static void put_le32(uint8_t *dst, uint32_t value)
{
    for (uint32_t i = 0u; i < 4u; ++i) {
        dst[i] = (uint8_t)(value >> (8u * i));
    }
}

static void put_le64(uint8_t *dst, uint64_t value)
{
    for (uint32_t i = 0u; i < 8u; ++i) {
        dst[i] = (uint8_t)(value >> (8u * i));
    }
}

static int unit_has_host_assumption(const struct vos_rtc_closure_unit *u)
{
    return u->has_filesystem != 0u ||
           u->has_subprocess != 0u ||
           u->has_host_allocator != 0u;
}

static int pool_can_bind(uint32_t lifecycle)
{
    return lifecycle == VOS_RTC_POOL_FREE ||
           lifecycle == VOS_RTC_POOL_BOUND ||
           lifecycle == VOS_RTC_POOL_REUSABLE;
}

enum vos_rtc_status vos_rtc_state_init(struct vos_rtc_state *state,
                                       uint64_t running_generation)
{
    if (state == NULL || running_generation == 0u) {
        return VOS_RTC_ERR_INVALID_ARG;
    }
    memset(state, 0, sizeof(*state));
    state->running_generation = running_generation;
    state->last_verdict.reproduced = 0u;
    state->last_verdict.cause = VOS_RTC_CAUSE_NONE;
    state->last_verdict.root_status = VOS_RTC_ROOT_RELOCATED;
    return VOS_RTC_OK;
}

enum vos_rtc_status vos_rtc_compute_artifact_digest(uint64_t pkg_id,
                                                    const uint8_t *code_bytes,
                                                    uint32_t code_len,
                                                    const struct vos_rtc_hash *source_digest,
                                                    struct vos_rtc_hash *out_digest)
{
    if (code_bytes == NULL || source_digest == NULL || out_digest == NULL ||
        code_len == 0u || code_len > VOS_RTC_MAX_CODE_BYTES) {
        return VOS_RTC_ERR_INVALID_ARG;
    }
    uint8_t buf[52u + VOS_RTC_MAX_CODE_BYTES];
    memcpy(buf, "VOSRTCA1", 8u);
    put_le64(buf + 8u, pkg_id);
    put_le32(buf + 16u, code_len);
    memcpy(buf + 20u, source_digest->bytes, VOS_RTC_DIGEST_BYTES);
    memcpy(buf + 52u, code_bytes, code_len);
    const int ok = vos_sha256(buf, 52u + (size_t)code_len, out_digest->bytes);
    zero_bytes(buf, 52u + (size_t)code_len);
    return ok ? VOS_RTC_OK : VOS_RTC_ERR_CRYPTO;
}

enum vos_rtc_status vos_rtc_compute_receipt_digest(const struct vos_rtc_build_receipt *rec,
                                                   struct vos_rtc_hash *out_digest)
{
    if (rec == NULL || out_digest == NULL) {
        return VOS_RTC_ERR_INVALID_ARG;
    }
    uint8_t buf[124];
    memcpy(buf, "VOSRTCR1", 8u);
    memcpy(buf + 8u, rec->source_digest.bytes, VOS_RTC_DIGEST_BYTES);
    memcpy(buf + 40u, rec->switch_digest.bytes, VOS_RTC_DIGEST_BYTES);
    memcpy(buf + 72u, rec->artifact_digest.bytes, VOS_RTC_DIGEST_BYTES);
    put_le32(buf + 104u, rec->tal_admitted ? 1u : 0u);
    put_le32(buf + 108u, rec->cic_admitted ? 1u : 0u);
    put_le32(buf + 112u, rec->ddc_checked ? 1u : 0u);
    put_le32(buf + 116u, rec->rot_measured ? 1u : 0u);
    put_le32(buf + 120u, rec->root_status);
    const int ok = vos_sha256(buf, sizeof(buf), out_digest->bytes);
    zero_bytes(buf, sizeof(buf));
    return ok ? VOS_RTC_OK : VOS_RTC_ERR_CRYPTO;
}

enum vos_rtc_status vos_rtc_screen_license(const struct vos_rtc_component_license *lic)
{
    if (lic == NULL) {
        return VOS_RTC_ERR_INVALID_ARG;
    }
    if (lic->read_at_incorporation == 0u) {
        return VOS_RTC_ERR_LICENSE_UNREAD;
    }
    if (lic->route == VOS_RTC_ROUTE_INDEPENDENT_IMPL) {
        if (lic->has_noncommercial_pass != 0u) {
            return VOS_RTC_ERR_NONCOMMERCIAL_NO_GRANT;
        }
        return VOS_RTC_OK;
    }
    if (lic->route == VOS_RTC_ROUTE_COMMERCIAL_GRANT) {
        if (lic->has_commercial_grant == 0u) {
            return VOS_RTC_ERR_MISSING_COMMERCIAL_GRANT;
        }
        return VOS_RTC_OK;
    }
    if (lic->route == VOS_RTC_ROUTE_DUAL_LICENSED_SUBSET) {
        if (lic->dual_subset_only == 0u ||
            lic->has_noncommercial_pass != 0u ||
            lic->provides_required_backend != 0u) {
            return VOS_RTC_ERR_OUTSIDE_DUAL_SUBSET;
        }
        return VOS_RTC_OK;
    }
    if (lic->route == VOS_RTC_ROUTE_NONCOMMERCIAL_ONLY) {
        return VOS_RTC_ERR_NONCOMMERCIAL_NO_GRANT;
    }
    return VOS_RTC_ERR_INVALID_ARG;
}

enum vos_rtc_status vos_rtc_audit_closure(const struct vos_rtc_closure_unit *unit,
                                          uint32_t *out_subport_id)
{
    if (unit == NULL) {
        return VOS_RTC_ERR_INVALID_ARG;
    }
    if (out_subport_id != NULL) {
        *out_subport_id = 0u;
    }
    if (unit->ambient_authority != 0u) {
        return VOS_RTC_ERR_AMBIENT_AUTHORITY;
    }
    if (unit->disposition == VOS_RTC_DISP_UNSAFE_EXCEPTION) {
        return VOS_RTC_ERR_UNSAFE_EXCEPTION;
    }
    if (unit->disposition == VOS_RTC_DISP_UNRESOLVED_AMBIENT) {
        return VOS_RTC_ERR_AMBIENT_AUTHORITY;
    }
    if (unit->disposition == VOS_RTC_DISP_CLEAN) {
        if (unit->unsafe_sites != 0u) {
            return VOS_RTC_ERR_UNCOVERED_UNSAFE;
        }
        if (unit_has_host_assumption(unit)) {
            return VOS_RTC_ERR_UNRESOLVED_HOST_ASSUMP;
        }
        return VOS_RTC_OK;
    }
    if (unit->disposition == VOS_RTC_DISP_DELETED) {
        if (unit->unsafe_sites != 0u && unit->unsafe_hal_or_proof_ok == 0u) {
            return VOS_RTC_ERR_UNCOVERED_UNSAFE;
        }
        return VOS_RTC_OK;
    }
    if (unit->disposition == VOS_RTC_DISP_VERIFIED_HAL_OR_PROOF) {
        if (unit->unsafe_hal_or_proof_ok == 0u) {
            return VOS_RTC_ERR_UNCOVERED_UNSAFE;
        }
        if (unit_has_host_assumption(unit)) {
            return VOS_RTC_ERR_UNRESOLVED_HOST_ASSUMP;
        }
        return VOS_RTC_OK;
    }
    if (unit->disposition == VOS_RTC_DISP_NAMED_SUBPORT) {
        if (unit->unsafe_sites != 0u && unit->unsafe_hal_or_proof_ok == 0u) {
            return VOS_RTC_ERR_UNCOVERED_UNSAFE;
        }
        if (!unit_has_host_assumption(unit)) {
            return VOS_RTC_ERR_UNRESOLVED_HOST_ASSUMP;
        }
        if (unit->subport_id == 0u || unit->subport_estimated == 0u) {
            return VOS_RTC_ERR_UNESTIMATED_SUBPORT;
        }
        if (out_subport_id != NULL) {
            *out_subport_id = unit->subport_id;
        }
        return VOS_RTC_OK;
    }
    return VOS_RTC_ERR_INVALID_ARG;
}

enum vos_rtc_status vos_rtc_check_compartment_caps(const struct vos_rtc_compartment_caps *caps)
{
    if (caps == NULL) {
        return VOS_RTC_ERR_INVALID_ARG;
    }
    if (caps->exec_over_own_output != 0u) {
        return VOS_RTC_ERR_EXEC_OWN_OUTPUT;
    }
    if (caps->sealing_auth != 0u ||
        caps->wiring_auth != 0u ||
        caps->store_consent_grant == 0u) {
        return VOS_RTC_ERR_FORBIDDEN_AUTH;
    }
    return VOS_RTC_OK;
}

enum vos_rtc_status vos_rtc_check_smallest_loop_first(
    const struct vos_rtc_compartment_caps *comps,
    uint32_t count)
{
    if (comps == NULL || count == 0u || count > VOS_RTC_MAX_COMPARTMENTS) {
        return VOS_RTC_ERR_INVALID_ARG;
    }
    uint32_t has_type_checker = 0u;
    uint32_t min_rank = 0u;
    for (uint32_t i = 0u; i < count; ++i) {
        const uint32_t role = comps[i].role;
        if (role > VOS_RTC_ROLE_PACKAGE_BUILDER) {
            return VOS_RTC_ERR_INVALID_ARG;
        }
        if (role == VOS_RTC_ROLE_TYPE_CHECKER) {
            has_type_checker = 1u;
        }
        if (role < min_rank) {
            return VOS_RTC_ERR_ORDER_VIOLATION;
        }
        min_rank = role;
    }
    if (has_type_checker == 0u) {
        return VOS_RTC_ERR_ORDER_VIOLATION;
    }
    return VOS_RTC_OK;
}

uint32_t vos_rtc_pools_can_share(const struct vos_rtc_pool_sharing_proof *proof)
{
    if (proof == NULL) {
        return 0u;
    }
    if (proof->disjoint_live_ranges == 0u ||
        proof->frame_or_region_proven == 0u ||
        proof->assumed_correlation_only != 0u ||
        proof->temporal_barrier_ok == 0u) {
        return 0u;
    }
    return 1u;
}

uint32_t vos_rtc_toolchain_pool_charge(uint32_t compiler_peak,
                                       uint32_t prover_peak,
                                       const struct vos_rtc_pool_sharing_proof *proof,
                                       uint32_t *out_overflow)
{
    if (out_overflow != NULL) {
        *out_overflow = 0u;
    }
    if (vos_rtc_pools_can_share(proof) != 0u) {
        return (compiler_peak >= prover_peak) ? compiler_peak : prover_peak;
    }
    if (compiler_peak > UINT32_MAX - prover_peak) {
        if (out_overflow != NULL) {
            *out_overflow = 1u;
        }
        return UINT32_MAX;
    }
    return compiler_peak + prover_peak;
}

enum vos_rtc_status vos_rtc_check_residency(const struct vos_rtc_residency_spec *spec,
                                            uint32_t *out_charge)
{
    if (spec == NULL) {
        return VOS_RTC_ERR_INVALID_ARG;
    }
    if (spec->reading != VOS_RTC_READING_A && spec->reading != VOS_RTC_READING_B) {
        return VOS_RTC_ERR_INVALID_ARG;
    }
    uint32_t overflow = 0u;
    const uint32_t pool_charge = vos_rtc_toolchain_pool_charge(
        spec->compiler_peak_bytes, spec->prover_peak_bytes, &spec->sharing, &overflow);
    if (overflow != 0u) {
        return VOS_RTC_ERR_RESIDENCY_EXCEEDED;
    }
    uint32_t total_charge = pool_charge;
    if (spec->reading == VOS_RTC_READING_B) {
        if (spec->ordinary_bytes > UINT32_MAX - pool_charge) {
            return VOS_RTC_ERR_RESIDENCY_EXCEEDED;
        }
        total_charge = spec->ordinary_bytes + pool_charge;
    }
    if (out_charge != NULL) {
        *out_charge = total_charge;
    }
    if (total_charge > spec->first_class_cap_bytes) {
        return VOS_RTC_ERR_RESIDENCY_EXCEEDED;
    }
    return VOS_RTC_OK;
}

enum vos_rtc_status vos_rtc_run_activation(struct vos_rtc_bounded_pool *pool,
                                           const struct vos_rtc_pass_activation *act,
                                           uint32_t *out_recorded_peak)
{
    if (pool == NULL || act == NULL) {
        return VOS_RTC_ERR_INVALID_ARG;
    }
    if (pool->pool_id != act->pool_id) {
        return VOS_RTC_ERR_WRONG_POOL;
    }
    if (!pool_can_bind(pool->lifecycle)) {
        return VOS_RTC_ERR_POOL_LIFECYCLE;
    }
    if (act->resumable == 0u) {
        return VOS_RTC_ERR_NOT_RESUMABLE;
    }
    if (act->steps_used > act->step_budget) {
        return VOS_RTC_ERR_STEP_BUDGET_EXCEEDED;
    }
    if (pool->exhausted_threshold > pool->capacity_bytes) {
        return VOS_RTC_ERR_CAPACITY_EXHAUSTED;
    }
    if (act->alloc_bytes > UINT32_MAX - pool->used_bytes) {
        return VOS_RTC_ERR_CAPACITY_EXHAUSTED;
    }
    const uint32_t next_used = pool->used_bytes + act->alloc_bytes;
    const uint32_t cand_peak =
        (next_used >= act->pass_peak_bytes) ? next_used : act->pass_peak_bytes;
    if (cand_peak > pool->exhausted_threshold) {
        return VOS_RTC_ERR_CAPACITY_EXHAUSTED;
    }
    pool->used_bytes = next_used;
    if (cand_peak > pool->peak_bytes) {
        pool->peak_bytes = cand_peak;
    }
    pool->lifecycle = VOS_RTC_POOL_BOUND;
    if (out_recorded_peak != NULL) {
        *out_recorded_peak = cand_peak;
    }
    return VOS_RTC_OK;
}

enum vos_rtc_status vos_rtc_compare_bootstrap_receipts(
    const struct vos_rtc_build_receipt *host,
    const struct vos_rtc_build_receipt *dev,
    struct vos_rtc_bootstrap_verdict *out_verdict)
{
    if (host == NULL || dev == NULL || out_verdict == NULL) {
        return VOS_RTC_ERR_INVALID_ARG;
    }
    out_verdict->reproduced = 0u;
    out_verdict->cause = VOS_RTC_CAUSE_NONE;
    out_verdict->root_status = VOS_RTC_ROOT_RELOCATED;

    if (host->root_status != VOS_RTC_ROOT_RELOCATED ||
        dev->root_status != VOS_RTC_ROOT_RELOCATED) {
        out_verdict->cause = VOS_RTC_CAUSE_CLOSED_BOOTSTRAP_CLAIMED;
        out_verdict->root_status = VOS_RTC_ROOT_CLOSED;
        return VOS_RTC_ERR_CLOSED_DEBRUIJN_CLAIM;
    }

    struct vos_rtc_hash expected_host_digest;
    struct vos_rtc_hash expected_dev_digest;
    if (vos_rtc_compute_receipt_digest(host, &expected_host_digest) != VOS_RTC_OK ||
        vos_rtc_compute_receipt_digest(dev, &expected_dev_digest) != VOS_RTC_OK) {
        return VOS_RTC_ERR_CRYPTO;
    }
    if (!equal_hashes(&expected_host_digest, &host->receipt_digest) ||
        !equal_hashes(&expected_dev_digest, &dev->receipt_digest)) {
        out_verdict->cause = VOS_RTC_CAUSE_ARTIFACT_MISMATCH;
        return VOS_RTC_ERR_BOOTSTRAP_DIVERGED;
    }

    if (host->tal_admitted == 0u || host->cic_admitted == 0u) {
        out_verdict->cause = VOS_RTC_CAUSE_HOST_ADMISSION_REFUSED;
        return VOS_RTC_ERR_BOOTSTRAP_DIVERGED;
    }
    if (dev->tal_admitted == 0u || dev->cic_admitted == 0u) {
        out_verdict->cause = VOS_RTC_CAUSE_DEVICE_ADMISSION_REFUSED;
        return VOS_RTC_ERR_BOOTSTRAP_DIVERGED;
    }
    if (!equal_hashes(&host->source_digest, &dev->source_digest)) {
        out_verdict->cause = VOS_RTC_CAUSE_SOURCE_MISMATCH;
        return VOS_RTC_ERR_BOOTSTRAP_DIVERGED;
    }
    if (!equal_hashes(&host->switch_digest, &dev->switch_digest)) {
        out_verdict->cause = VOS_RTC_CAUSE_SWITCH_MISMATCH;
        return VOS_RTC_ERR_BOOTSTRAP_DIVERGED;
    }
    if (!equal_hashes(&host->artifact_digest, &dev->artifact_digest)) {
        out_verdict->cause = VOS_RTC_CAUSE_ARTIFACT_MISMATCH;
        return VOS_RTC_ERR_BOOTSTRAP_DIVERGED;
    }
    if (host->ddc_checked == 0u || dev->ddc_checked == 0u ||
        host->rot_measured == 0u || dev->rot_measured == 0u) {
        out_verdict->cause = VOS_RTC_CAUSE_DDC_OR_ROT_INCOMPLETE;
        return VOS_RTC_ERR_BOOTSTRAP_DIVERGED;
    }

    out_verdict->reproduced = 1u;
    out_verdict->cause = VOS_RTC_CAUSE_NONE;
    out_verdict->root_status = VOS_RTC_ROOT_RELOCATED;
    return VOS_RTC_OK;
}

enum vos_rtc_status vos_rtc_run_cycle(struct vos_rtc_state *state,
                                      const struct vos_rtc_request *req,
                                      struct vos_rtc_bootstrap_verdict *out_verdict)
{
    if (state == NULL || req == NULL || out_verdict == NULL ||
        req->license_count == 0u || req->license_count > VOS_RTC_MAX_LICENSES ||
        req->closure_count == 0u || req->closure_count > VOS_RTC_MAX_CLOSURE ||
        req->compartment_count == 0u || req->compartment_count > VOS_RTC_MAX_COMPARTMENTS ||
        req->activation_count == 0u || req->activation_count > VOS_RTC_MAX_ACTIVATIONS) {
        return VOS_RTC_ERR_INVALID_ARG;
    }

    memset(out_verdict, 0, sizeof(*out_verdict));

    for (uint32_t i = 0u; i < req->license_count; ++i) {
        const enum vos_rtc_status st = vos_rtc_screen_license(&req->licenses[i]);
        if (st != VOS_RTC_OK) {
            return st;
        }
    }

    for (uint32_t i = 0u; i < req->closure_count; ++i) {
        uint32_t subport_id = 0u;
        const enum vos_rtc_status st = vos_rtc_audit_closure(&req->closure[i], &subport_id);
        if (st != VOS_RTC_OK) {
            return st;
        }
        /* Active resident execution cannot proceed while a closure unit has unresolved host assumptions. */
        if (subport_id != 0u) {
            return VOS_RTC_ERR_UNRESOLVED_HOST_ASSUMP;
        }
    }

    for (uint32_t i = 0u; i < req->compartment_count; ++i) {
        const enum vos_rtc_status st = vos_rtc_check_compartment_caps(&req->compartments[i]);
        if (st != VOS_RTC_OK) {
            return st;
        }
    }

    enum vos_rtc_status st =
        vos_rtc_check_smallest_loop_first(req->compartments, req->compartment_count);
    if (st != VOS_RTC_OK) {
        return st;
    }

    st = vos_rtc_check_residency(&req->residency, NULL);
    if (st != VOS_RTC_OK) {
        return st;
    }

    /* Operate on a staging copy of the pool so any exhaustion preserves running state. */
    struct vos_rtc_bounded_pool staged_pool = req->pool;
    uint32_t max_recorded_peak = 0u;
    for (uint32_t i = 0u; i < req->activation_count; ++i) {
        uint32_t pass_peak = 0u;
        st = vos_rtc_run_activation(&staged_pool, &req->activations[i], &pass_peak);
        if (st != VOS_RTC_OK) {
            return st;
        }
        if (pass_peak > max_recorded_peak) {
            max_recorded_peak = pass_peak;
        }
    }

    if (max_recorded_peak > req->residency.compiler_peak_bytes) {
        return VOS_RTC_ERR_RESIDENCY_EXCEEDED;
    }

    struct vos_rtc_bootstrap_verdict verdict;
    st = vos_rtc_compare_bootstrap_receipts(&req->host_receipt, &req->dev_receipt, &verdict);
    *out_verdict = verdict;
    if (st != VOS_RTC_OK) {
        return st;
    }

    state->running_generation += 1u;
    state->last_peak_bytes =
        (staged_pool.peak_bytes >= max_recorded_peak) ? staged_pool.peak_bytes : max_recorded_peak;
    state->admitted_runs += 1u;
    state->last_verdict = verdict;
    return VOS_RTC_OK;
}
