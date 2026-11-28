// SPDX-License-Identifier: Apache-2.0
#include "vos_resident_tc.h"

#include <stdio.h>
#include <string.h>

#define CHECK(cond, msg)                                                      \
    do {                                                                      \
        if (!(cond)) {                                                        \
            fprintf(stderr, "FAIL (%s:%d): %s\n", __FILE__, __LINE__, (msg)); \
            return 1;                                                         \
        }                                                                     \
    } while (0)

static struct vos_rtc_hash make_digest(uint8_t tag)
{
    struct vos_rtc_hash h;
    for (size_t i = 0u; i < VOS_RTC_DIGEST_BYTES; ++i) {
        h.bytes[i] = (uint8_t)(tag ^ (uint8_t)(i * 5u + 3u));
    }
    return h;
}

static struct vos_rtc_component_license make_lic_independent(uint64_t id)
{
    struct vos_rtc_component_license lic;
    memset(&lic, 0, sizeof(lic));
    lic.comp_id = id;
    lic.route = VOS_RTC_ROUTE_INDEPENDENT_IMPL;
    lic.read_at_incorporation = 1u;
    lic.has_noncommercial_pass = 0u;
    lic.has_commercial_grant = 0u;
    lic.dual_subset_only = 0u;
    lic.provides_required_backend = 1u;
    return lic;
}

static struct vos_rtc_closure_unit make_clean_unit(uint64_t id)
{
    struct vos_rtc_closure_unit u;
    memset(&u, 0, sizeof(u));
    u.unit_id = id;
    u.disposition = VOS_RTC_DISP_CLEAN;
    return u;
}

static struct vos_rtc_compartment_caps make_comp(uint64_t id, uint32_t role)
{
    struct vos_rtc_compartment_caps c;
    memset(&c, 0, sizeof(c));
    c.comp_id = id;
    c.role = role;
    c.store_consent_grant = 1u;
    return c;
}

static struct vos_rtc_build_receipt make_receipt(const struct vos_rtc_hash *src,
                                                 const struct vos_rtc_hash *sw,
                                                 const struct vos_rtc_hash *art)
{
    struct vos_rtc_build_receipt r;
    memset(&r, 0, sizeof(r));
    r.source_digest = *src;
    r.switch_digest = *sw;
    r.artifact_digest = *art;
    r.tal_admitted = 1u;
    r.cic_admitted = 1u;
    r.ddc_checked = 1u;
    r.rot_measured = 1u;
    r.root_status = VOS_RTC_ROOT_RELOCATED;
    (void)vos_rtc_compute_receipt_digest(&r, &r.receipt_digest);
    return r;
}

int main(void)
{
    struct vos_rtc_state st;
    CHECK(vos_rtc_state_init(&st, 5u) == VOS_RTC_OK, "state init failed");

    const struct vos_rtc_hash src_digest = make_digest(0x11u);
    const struct vos_rtc_hash sw_digest = make_digest(0x22u);
    uint8_t code[32];
    for (size_t i = 0u; i < sizeof(code); ++i) {
        code[i] = (uint8_t)(0x40u + i);
    }
    struct vos_rtc_hash art_digest;
    CHECK(vos_rtc_compute_artifact_digest(1u, code, (uint32_t)sizeof(code),
                                          &src_digest, &art_digest) == VOS_RTC_OK,
          "artifact digest failed");

    /* 1. Positive resident toolchain cycle + bootstrap reproduction. */
    struct vos_rtc_request req;
    memset(&req, 0, sizeof(req));
    req.license_count = 3u;
    req.licenses[0] = make_lic_independent(1u);

    req.licenses[1].comp_id = 2u;
    req.licenses[1].route = VOS_RTC_ROUTE_COMMERCIAL_GRANT;
    req.licenses[1].read_at_incorporation = 1u;
    req.licenses[1].has_noncommercial_pass = 1u;
    req.licenses[1].has_commercial_grant = 1u;
    req.licenses[1].provides_required_backend = 1u;

    req.licenses[2].comp_id = 3u;
    req.licenses[2].route = VOS_RTC_ROUTE_DUAL_LICENSED_SUBSET;
    req.licenses[2].read_at_incorporation = 1u;
    req.licenses[2].dual_subset_only = 1u;

    req.closure_count = 3u;
    req.closure[0] = make_clean_unit(10u);

    req.closure[1].unit_id = 11u;
    req.closure[1].unsafe_sites = 2u;
    req.closure[1].unsafe_hal_or_proof_ok = 1u;
    req.closure[1].disposition = VOS_RTC_DISP_VERIFIED_HAL_OR_PROOF;

    req.closure[2].unit_id = 12u;
    req.closure[2].has_filesystem = 1u;
    req.closure[2].has_subprocess = 1u;
    req.closure[2].has_host_allocator = 1u;
    req.closure[2].disposition = VOS_RTC_DISP_DELETED;

    req.compartment_count = 3u;
    req.compartments[0] = make_comp(101u, VOS_RTC_ROLE_TYPE_CHECKER);
    req.compartments[1] = make_comp(102u, VOS_RTC_ROLE_PROVER);
    req.compartments[2] = make_comp(103u, VOS_RTC_ROLE_COMPILER);

    req.pool.pool_id = 1u;
    req.pool.owner_id = 103u;
    req.pool.capacity_bytes = 64000u;
    req.pool.low_threshold = 48000u;
    req.pool.exhausted_threshold = 60000u;
    req.pool.used_bytes = 0u;
    req.pool.peak_bytes = 0u;
    req.pool.lifecycle = VOS_RTC_POOL_FREE;

    req.activation_count = 2u;
    req.activations[0].pass_id = 1u;
    req.activations[0].role = VOS_RTC_ROLE_TYPE_CHECKER;
    req.activations[0].pool_id = 1u;
    req.activations[0].step_budget = 500u;
    req.activations[0].steps_used = 120u;
    req.activations[0].alloc_bytes = 4096u;
    req.activations[0].pass_peak_bytes = 8192u;
    req.activations[0].resumable = 1u;
    req.activations[0].checkpoint_saved = 1u;

    req.activations[1].pass_id = 2u;
    req.activations[1].role = VOS_RTC_ROLE_COMPILER;
    req.activations[1].pool_id = 1u;
    req.activations[1].step_budget = 2000u;
    req.activations[1].steps_used = 1500u;
    req.activations[1].alloc_bytes = 12288u;
    req.activations[1].pass_peak_bytes = 24576u;
    req.activations[1].resumable = 1u;
    req.activations[1].checkpoint_saved = 0u;

    req.residency.reading = VOS_RTC_READING_A;
    req.residency.ordinary_bytes = 40000u;
    req.residency.compiler_peak_bytes = 24576u;
    req.residency.prover_peak_bytes = 38000u;
    req.residency.first_class_cap_bytes = 60000u;
    req.residency.sharing.disjoint_live_ranges = 1u;
    req.residency.sharing.frame_or_region_proven = 1u;
    req.residency.sharing.assumed_correlation_only = 0u;
    req.residency.sharing.temporal_barrier_ok = 1u;

    req.host_receipt = make_receipt(&src_digest, &sw_digest, &art_digest);
    req.dev_receipt = make_receipt(&src_digest, &sw_digest, &art_digest);

    struct vos_rtc_bootstrap_verdict verdict;
    CHECK(vos_rtc_run_cycle(&st, &req, &verdict) == VOS_RTC_OK,
          "positive resident toolchain cycle failed");
    CHECK(st.running_generation == 6u && st.last_peak_bytes == 24576u &&
          verdict.reproduced == 1u && verdict.root_status == VOS_RTC_ROOT_RELOCATED,
          "positive resident toolchain state mismatch");

    /* Named sub-port audit succeeds at audit time, but blocks active runnable admission. */
    struct vos_rtc_closure_unit subport_unit = make_clean_unit(13u);
    subport_unit.has_filesystem = 1u;
    subport_unit.has_host_allocator = 1u;
    subport_unit.disposition = VOS_RTC_DISP_NAMED_SUBPORT;
    subport_unit.subport_id = 77u;
    subport_unit.subport_estimated = 1u;
    uint32_t out_sp = 0u;
    CHECK(vos_rtc_audit_closure(&subport_unit, &out_sp) == VOS_RTC_OK && out_sp == 77u,
          "named estimated subport audit failed");

    /* 2. Adverse license screening controls (R-18-004e). */
    struct vos_rtc_request bad_lic = req;
    bad_lic.licenses[0].read_at_incorporation = 0u;
    CHECK(vos_rtc_run_cycle(&st, &bad_lic, &verdict) == VOS_RTC_ERR_LICENSE_UNREAD,
          "unread license accepted");

    bad_lic = req;
    bad_lic.licenses[1].route = VOS_RTC_ROUTE_NONCOMMERCIAL_ONLY;
    bad_lic.licenses[1].has_commercial_grant = 0u;
    CHECK(vos_rtc_run_cycle(&st, &bad_lic, &verdict) == VOS_RTC_ERR_NONCOMMERCIAL_NO_GRANT,
          "noncommercial pass without grant accepted");

    bad_lic = req;
    bad_lic.licenses[2].dual_subset_only = 0u;
    CHECK(vos_rtc_run_cycle(&st, &bad_lic, &verdict) == VOS_RTC_ERR_OUTSIDE_DUAL_SUBSET,
          "outside dual-licensed subset accepted");

    /* 3. Adverse closure audit controls (R-13-027, R-13-027a). */
    struct vos_rtc_request bad_clos = req;
    bad_clos.closure[0].disposition = VOS_RTC_DISP_UNSAFE_EXCEPTION;
    CHECK(vos_rtc_run_cycle(&st, &bad_clos, &verdict) == VOS_RTC_ERR_UNSAFE_EXCEPTION,
          "unsafe exception accepted");

    bad_clos = req;
    bad_clos.closure[0].ambient_authority = 1u;
    CHECK(vos_rtc_run_cycle(&st, &bad_clos, &verdict) == VOS_RTC_ERR_AMBIENT_AUTHORITY,
          "ambient authority accepted");

    bad_clos = req;
    bad_clos.closure[0].has_filesystem = 1u;
    CHECK(vos_rtc_run_cycle(&st, &bad_clos, &verdict) == VOS_RTC_ERR_UNRESOLVED_HOST_ASSUMP,
          "unresolved host assumption accepted");

    /* 4. Adverse authority and smallest-loop-first order controls. */
    struct vos_rtc_request bad_auth = req;
    bad_auth.compartments[2].exec_over_own_output = 1u;
    CHECK(vos_rtc_run_cycle(&st, &bad_auth, &verdict) == VOS_RTC_ERR_EXEC_OWN_OUTPUT,
          "execute over own output accepted");

    struct vos_rtc_request bad_order = req;
    bad_order.compartments[0] = make_comp(103u, VOS_RTC_ROLE_COMPILER);
    bad_order.compartments[1] = make_comp(101u, VOS_RTC_ROLE_TYPE_CHECKER);
    CHECK(vos_rtc_run_cycle(&st, &bad_order, &verdict) == VOS_RTC_ERR_ORDER_VIOLATION,
          "compiler before type-checker accepted");

    /* 5. Adverse pool sharing & ReadingA vs ReadingB controls (R-08-014, R-08-018a). */
    struct vos_rtc_request bad_share = req;
    bad_share.residency.sharing.assumed_correlation_only = 1u;
    CHECK(vos_rtc_pools_can_share(&bad_share.residency.sharing) == 0u,
          "assumed correlation allowed pool sharing");
    CHECK(vos_rtc_run_cycle(&st, &bad_share, &verdict) == VOS_RTC_ERR_RESIDENCY_EXCEEDED,
          "assumed correlation pool sharing fit accepted");

    struct vos_rtc_request bad_reading_b = req;
    bad_reading_b.residency.reading = VOS_RTC_READING_B;
    CHECK(vos_rtc_run_cycle(&st, &bad_reading_b, &verdict) == VOS_RTC_ERR_RESIDENCY_EXCEEDED,
          "ReadingB ignored ordinary bytes");

    /* 6. Adverse pool exhaustion and step budget exhaustion (R-08-046, R-13-027a). */
    const uint64_t saved_gen = st.running_generation;
    struct vos_rtc_request bad_pool = req;
    bad_pool.activations[1].pass_peak_bytes = 60001u;
    bad_pool.residency.compiler_peak_bytes = 60001u;
    bad_pool.residency.first_class_cap_bytes = 100000u;
    CHECK(vos_rtc_run_cycle(&st, &bad_pool, &verdict) == VOS_RTC_ERR_CAPACITY_EXHAUSTED,
          "pool exhaustion accepted");
    CHECK(st.running_generation == saved_gen, "pool exhaustion mutated running generation");

    struct vos_rtc_request bad_steps = req;
    bad_steps.activations[1].steps_used = 2001u;
    CHECK(vos_rtc_run_cycle(&st, &bad_steps, &verdict) == VOS_RTC_ERR_STEP_BUDGET_EXCEEDED,
          "step budget exceeded accepted");
    CHECK(st.running_generation == saved_gen, "step exhaustion mutated running generation");

    /* 7. Adverse bootstrap divergence & Closed De Bruijn claim (R-13-027, R-06-014). */
    struct vos_rtc_request bad_art = req;
    bad_art.dev_receipt.artifact_digest = make_digest(0x99u);
    (void)vos_rtc_compute_receipt_digest(&bad_art.dev_receipt,
                                         &bad_art.dev_receipt.receipt_digest);
    CHECK(vos_rtc_run_cycle(&st, &bad_art, &verdict) == VOS_RTC_ERR_BOOTSTRAP_DIVERGED &&
          verdict.reproduced == 0u && verdict.cause == VOS_RTC_CAUSE_ARTIFACT_MISMATCH,
          "diverged bootstrap artifact accepted");

    struct vos_rtc_request bad_root = req;
    bad_root.dev_receipt.root_status = VOS_RTC_ROOT_CLOSED;
    (void)vos_rtc_compute_receipt_digest(&bad_root.dev_receipt,
                                         &bad_root.dev_receipt.receipt_digest);
    CHECK(vos_rtc_run_cycle(&st, &bad_root, &verdict) == VOS_RTC_ERR_CLOSED_DEBRUIJN_CLAIM &&
          verdict.cause == VOS_RTC_CAUSE_CLOSED_BOOTSTRAP_CLAIMED,
          "closed De Bruijn root claim accepted");

    printf("resident_tc_test: ok\n");
    return 0;
}
