/* SPDX-License-Identifier: Apache-2.0 */
#include "vos_compat_workflow.h"

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

static int equal_hashes(const struct vos_compat_hash *a,
                        const struct vos_compat_hash *b)
{
    return equal_bytes_ct(a->bytes, b->bytes, VOS_COMPAT_DIGEST_BYTES);
}

static void put_le64(uint8_t *dst, uint64_t val)
{
    for (uint32_t i = 0u; i < 8u; ++i) {
        dst[i] = (uint8_t)(val >> (8u * i));
    }
}

static int check_authorities(const struct vos_compat_service *svc)
{
    if (svc == NULL) {
        return 0;
    }
    const struct vos_compat_editor_auth *ea = &svc->editor_auth;
    const struct vos_compat_builder_auth *ba = &svc->builder_auth;

    if (ea->private_source_ep == 0u || ea->private_result_ep == 0u ||
        ea->holds_exec_staged != 0u || ea->holds_signing_key != 0u ||
        ea->holds_mint_cap != 0u || ea->holds_sealing_cap != 0u ||
        ea->holds_wiring_cap != 0u || ea->holds_boot_select_cap != 0u) {
        return 0;
    }
    if (ba->immutable_closure_ok == 0u || ba->output_reservation_ok == 0u ||
        ba->diagnostics_ep_ok == 0u || ba->holds_exec_staged != 0u ||
        ba->holds_sealing_cap != 0u || ba->holds_wiring_cap != 0u ||
        ba->holds_signing_key != 0u) {
        return 0;
    }
    return 1;
}

static int pool_decl_valid(uint32_t expected_kind,
                           const struct vos_compat_pool_decl *pd)
{
    if (pd == NULL || pd->kind != expected_kind || pd->max_capacity == 0u) {
        return 0;
    }
    if (pd->has_owning_compartment == 0u || pd->has_derivation_source == 0u ||
        pd->has_bind_release_caps == 0u || pd->has_thresholds == 0u ||
        pd->has_release_bound == 0u || pd->has_lifecycle == 0u ||
        pd->has_recovery_reserve == 0u || pd->has_confidentiality == 0u ||
        pd->has_telemetry == 0u || pd->has_restart_semantics == 0u) {
        return 0;
    }
    if (pd->low_threshold > pd->max_capacity ||
        pd->exhausted_threshold > pd->max_capacity) {
        return 0;
    }
    return 1;
}

enum vos_compat_status vos_compat_profile_validate(const struct vos_compat_profile *profile)
{
    if (profile == NULL || profile->predeclared == 0u ||
        profile->step_budget == 0u || profile->ordinary_borrows_comp != 0u) {
        return VOS_COMPAT_ERR_INVALID_PROFILE;
    }
    for (uint32_t i = 0u; i < VOS_COMPAT_POOL_COUNT; ++i) {
        if (!pool_decl_valid(i, &profile->pools[i])) {
            return VOS_COMPAT_ERR_INVALID_PROFILE;
        }
    }
    if (profile->pools[VOS_COMPAT_POOL_EDITED_STAGING].max_capacity > VOS_COMPAT_MAX_STAGED_BYTES ||
        profile->pools[VOS_COMPAT_POOL_BUILD_JOBS].max_capacity > VOS_COMPAT_MAX_JOBS ||
        profile->pools[VOS_COMPAT_POOL_DIAGNOSTICS_BUFFER].max_capacity > VOS_COMPAT_MAX_DIAG_RECORDS ||
        profile->pools[VOS_COMPAT_POOL_PROOF_CACHE].max_capacity > VOS_COMPAT_MAX_CACHE_ENTRIES ||
        profile->pools[VOS_COMPAT_POOL_CANDIDATE_CLOSURE].max_capacity > VOS_COMPAT_MAX_ROSTER_ENTRIES) {
        return VOS_COMPAT_ERR_INVALID_PROFILE;
    }
    if (profile->max_source_edges == 0u || profile->max_source_depth == 0u ||
        profile->max_chunk_bytes == 0u || profile->max_chunk_bytes > VOS_COMPAT_MAX_CHUNK_BYTES ||
        profile->max_partial_objects == 0u ||
        profile->max_partial_objects > VOS_COMPAT_MAX_PARTIAL_OBJS ||
        profile->epoch_limit == 0u ||
        profile->max_diag_record_bytes == 0u ||
        profile->max_diag_record_bytes > VOS_COMPAT_MAX_DIAG_RECORD_BYTES ||
        profile->max_diag_bytes == 0u || profile->max_diag_bytes > VOS_COMPAT_MAX_DIAG_BYTES ||
        profile->max_checking_steps == 0u ||
        profile->max_result_bytes == 0u ||
        profile->max_result_bytes > VOS_COMPAT_MAX_RESULT_BYTES) {
        return VOS_COMPAT_ERR_INVALID_PROFILE;
    }
    return VOS_COMPAT_OK;
}

enum vos_compat_status vos_compat_lifecycle_step(uint32_t current_state,
                                                 uint32_t action,
                                                 uint32_t *next_state_out)
{
    if (next_state_out == NULL) {
        return VOS_COMPAT_ERR_INVALID_ARG;
    }
    if (action == VOS_COMPAT_ACT_BIND &&
        (current_state == VOS_COMPAT_LC_FREE || current_state == VOS_COMPAT_LC_REUSABLE)) {
        *next_state_out = VOS_COMPAT_LC_BOUND;
        return VOS_COMPAT_OK;
    }
    if (action == VOS_COMPAT_ACT_QUIESCE && current_state == VOS_COMPAT_LC_BOUND) {
        *next_state_out = VOS_COMPAT_LC_QUIESCING;
        return VOS_COMPAT_OK;
    }
    if (action == VOS_COMPAT_ACT_REVOKE &&
        (current_state == VOS_COMPAT_LC_BOUND || current_state == VOS_COMPAT_LC_QUIESCING)) {
        *next_state_out = VOS_COMPAT_LC_REVOKED;
        return VOS_COMPAT_OK;
    }
    if (action == VOS_COMPAT_ACT_SWEEP && current_state == VOS_COMPAT_LC_REVOKED) {
        *next_state_out = VOS_COMPAT_LC_SWEEPING;
        return VOS_COMPAT_OK;
    }
    if (action == VOS_COMPAT_ACT_RELEASE && current_state == VOS_COMPAT_LC_SWEEPING) {
        *next_state_out = VOS_COMPAT_LC_REUSABLE;
        return VOS_COMPAT_OK;
    }
    if (action == VOS_COMPAT_ACT_INTERRUPT &&
        (current_state == VOS_COMPAT_LC_QUIESCING ||
         current_state == VOS_COMPAT_LC_REVOKED ||
         current_state == VOS_COMPAT_LC_SWEEPING)) {
        *next_state_out = current_state;
        return VOS_COMPAT_OK;
    }
    return VOS_COMPAT_ERR_JOB_NOT_ACTIVE;
}

enum vos_compat_status vos_compat_compute_cache_key(const struct vos_compat_cache_identity *id,
                                                    struct vos_compat_hash *out_key)
{
    if (id == NULL || out_key == NULL) {
        return VOS_COMPAT_ERR_INVALID_ARG;
    }
    uint8_t buf[8u + 6u * VOS_COMPAT_DIGEST_BYTES + 8u];
    memcpy(buf, "VOSCPKEY", 8u);
    size_t off = 8u;
    memcpy(buf + off, id->source_digest.bytes, VOS_COMPAT_DIGEST_BYTES);
    off += VOS_COMPAT_DIGEST_BYTES;
    memcpy(buf + off, id->dep_closure_digest.bytes, VOS_COMPAT_DIGEST_BYTES);
    off += VOS_COMPAT_DIGEST_BYTES;
    memcpy(buf + off, id->imported_lemma_digest.bytes, VOS_COMPAT_DIGEST_BYTES);
    off += VOS_COMPAT_DIGEST_BYTES;
    memcpy(buf + off, id->semantics_digest.bytes, VOS_COMPAT_DIGEST_BYTES);
    off += VOS_COMPAT_DIGEST_BYTES;
    memcpy(buf + off, id->config_digest.bytes, VOS_COMPAT_DIGEST_BYTES);
    off += VOS_COMPAT_DIGEST_BYTES;
    memcpy(buf + off, id->assumption_digest.bytes, VOS_COMPAT_DIGEST_BYTES);
    off += VOS_COMPAT_DIGEST_BYTES;
    put_le64(buf + off, id->profile_id);
    off += 8u;
    const int ok = vos_sha256(buf, off, out_key->bytes);
    zero_bytes(buf, sizeof(buf));
    return ok ? VOS_COMPAT_OK : VOS_COMPAT_ERR_CRYPTO;
}

static int cache_identity_equal(const struct vos_compat_cache_identity *a,
                                const struct vos_compat_cache_identity *b)
{
    return equal_hashes(&a->source_digest, &b->source_digest) &&
           equal_hashes(&a->dep_closure_digest, &b->dep_closure_digest) &&
           equal_hashes(&a->imported_lemma_digest, &b->imported_lemma_digest) &&
           equal_hashes(&a->semantics_digest, &b->semantics_digest) &&
           equal_hashes(&a->config_digest, &b->config_digest) &&
           equal_hashes(&a->assumption_digest, &b->assumption_digest) &&
           a->profile_id == b->profile_id;
}

int vos_compat_cache_lookup(const struct vos_compat_service *svc,
                            const struct vos_compat_cache_identity *id,
                            struct vos_compat_cache_entry *out_entry)
{
    if (svc == NULL || id == NULL) {
        return 0;
    }
    struct vos_compat_hash key;
    if (vos_compat_compute_cache_key(id, &key) != VOS_COMPAT_OK) {
        return 0;
    }
    const uint32_t cap = svc->profile.pools[VOS_COMPAT_POOL_PROOF_CACHE].max_capacity;
    const uint32_t limit = cap < VOS_COMPAT_MAX_CACHE_ENTRIES ? cap : VOS_COMPAT_MAX_CACHE_ENTRIES;
    for (uint32_t i = 0u; i < limit; ++i) {
        const struct vos_compat_cache_entry *e = &svc->proof_cache[i];
        if (e->valid != 0u && e->verified != 0u &&
            equal_hashes(&e->key_digest, &key) &&
            cache_identity_equal(&e->identity, id)) {
            if (out_entry != NULL) {
                *out_entry = *e;
            }
            return 1;
        }
    }
    return 0;
}

enum vos_compat_status vos_compat_service_init(struct vos_compat_service *svc,
                                             const struct vos_compat_editor_auth *editor_auth,
                                             const struct vos_compat_builder_auth *builder_auth,
                                             const struct vos_compat_profile *profile,
                                             const struct vos_compat_hash *initial_root,
                                             const struct vos_compat_hash *initial_roster)
{
    if (svc == NULL || editor_auth == NULL || builder_auth == NULL ||
        profile == NULL || initial_root == NULL || initial_roster == NULL) {
        return VOS_COMPAT_ERR_INVALID_ARG;
    }
    memset(svc, 0, sizeof(*svc));
    svc->editor_auth = *editor_auth;
    svc->builder_auth = *builder_auth;
    if (!check_authorities(svc)) {
        memset(svc, 0, sizeof(*svc));
        return VOS_COMPAT_ERR_AUTHORITY;
    }
    const enum vos_compat_status pst = vos_compat_profile_validate(profile);
    if (pst != VOS_COMPAT_OK) {
        memset(svc, 0, sizeof(*svc));
        return pst;
    }
    svc->profile = *profile;
    svc->running_gen_root = *initial_root;
    svc->running_roster_hash = *initial_roster;
    svc->boot_epoch = 1u;
    svc->next_job_epoch = 1u;
    return VOS_COMPAT_OK;
}

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
                                                uint32_t *out_len)
{
    if (svc == NULL || src == NULL || out_bytes == NULL || out_len == NULL) {
        return VOS_COMPAT_ERR_INVALID_ARG;
    }
    if (!check_authorities(svc)) {
        return VOS_COMPAT_ERR_AUTHORITY;
    }
    if (vos_compat_profile_validate(&svc->profile) != VOS_COMPAT_OK) {
        return VOS_COMPAT_ERR_INVALID_PROFILE;
    }
    if (src->grant_ok == 0u) {
        return VOS_COMPAT_ERR_MISSING_GRANT;
    }
    if (req_obj_id != src->obj_id || req_version != src->version) {
        return VOS_COMPAT_ERR_WRONG_OBJECT_OR_VERSION;
    }
    if (src->total_bytes > VOS_COMPAT_MAX_STAGED_BYTES ||
        len > VOS_COMPAT_MAX_SOURCE_SLICE ||
        offset > src->total_bytes ||
        len > src->total_bytes - offset) {
        return VOS_COMPAT_ERR_OUT_OF_RANGE;
    }
    if (index_objs > svc->profile.pools[VOS_COMPAT_POOL_SOURCE_INDEX].max_capacity ||
        index_edges > svc->profile.max_source_edges ||
        index_depth > svc->profile.max_source_depth) {
        return VOS_COMPAT_ERR_INDEX_EXHAUSTED;
    }
    if (len > 0u) {
        memcpy(out_bytes, src->bytes + offset, len);
    }
    *out_len = len;
    return VOS_COMPAT_OK;
}

static void abort_partial(struct vos_compat_partial_stage *ps)
{
    zero_bytes(ps->bytes, sizeof(ps->bytes));
    memset(ps, 0, sizeof(*ps));
}

static struct vos_compat_partial_stage *find_partial_by_slot(struct vos_compat_service *svc,
                                                             uint64_t slot_id,
                                                             uint32_t *active_count_out)
{
    struct vos_compat_partial_stage *found = NULL;
    uint32_t active = 0u;
    for (uint32_t i = 0u; i < VOS_COMPAT_MAX_PARTIAL_OBJS; ++i) {
        if (svc->partials[i].active != 0u) {
            active += 1u;
            if (svc->partials[i].slot_id == slot_id) {
                found = &svc->partials[i];
            }
        }
    }
    if (active_count_out != NULL) {
        *active_count_out = active;
    }
    return found;
}

enum vos_compat_status vos_compat_stage_edited_source(struct vos_compat_service *svc,
                                                  uint32_t reservation_ok,
                                                  uint64_t slot_id,
                                                  uint32_t seq,
                                                  uint32_t declared_total,
                                                  const uint8_t *chunk_bytes,
                                                  uint32_t chunk_len,
                                                  const struct vos_compat_hash *expected_digest,
                                                  uint32_t is_final,
                                                  struct vos_compat_staged_obj *out_staged)
{
    if (svc == NULL || (chunk_len > 0u && chunk_bytes == NULL)) {
        return VOS_COMPAT_ERR_INVALID_ARG;
    }
    if (!check_authorities(svc)) {
        return VOS_COMPAT_ERR_AUTHORITY;
    }
    if (vos_compat_profile_validate(&svc->profile) != VOS_COMPAT_OK) {
        return VOS_COMPAT_ERR_INVALID_PROFILE;
    }
    if (reservation_ok == 0u) {
        return VOS_COMPAT_ERR_MISSING_GRANT;
    }

    const uint32_t max_bytes = svc->profile.pools[VOS_COMPAT_POOL_EDITED_STAGING].max_capacity;
    const uint32_t max_chunk = svc->profile.max_chunk_bytes;
    const uint32_t max_partials = svc->profile.max_partial_objects;

    uint32_t active_count = 0u;
    struct vos_compat_partial_stage *ps = find_partial_by_slot(svc, slot_id, &active_count);

    if (declared_total == 0u || declared_total > max_bytes || chunk_len > max_chunk) {
        if (ps != NULL) {
            abort_partial(ps);
        }
        return VOS_COMPAT_ERR_STAGING_OVER_BUDGET;
    }

    if (ps == NULL) {
        if (active_count >= max_partials) {
            return VOS_COMPAT_ERR_STAGING_OVER_BUDGET;
        }
        if (seq != 0u || chunk_len > declared_total) {
            return VOS_COMPAT_ERR_STAGING_SEQUENCE;
        }
        for (uint32_t i = 0u; i < VOS_COMPAT_MAX_PARTIAL_OBJS; ++i) {
            if (svc->partials[i].active == 0u) {
                ps = &svc->partials[i];
                break;
            }
        }
        if (ps == NULL) {
            return VOS_COMPAT_ERR_STAGING_OVER_BUDGET;
        }
        memset(ps, 0, sizeof(*ps));
        ps->active = 1u;
        ps->slot_id = slot_id;
        ps->declared_total = declared_total;
        ps->next_seq = 0u;
        ps->accum_bytes = 0u;
    } else {
        if (seq != ps->next_seq || declared_total != ps->declared_total ||
            chunk_len > ps->declared_total - ps->accum_bytes) {
            abort_partial(ps);
            return VOS_COMPAT_ERR_STAGING_SEQUENCE;
        }
    }

    if (chunk_len > 0u) {
        memcpy(ps->bytes + ps->accum_bytes, chunk_bytes, chunk_len);
        ps->accum_bytes += chunk_len;
    }
    ps->next_seq += 1u;

    if (is_final == 0u) {
        return VOS_COMPAT_OK;
    }

    if (ps->accum_bytes != ps->declared_total) {
        abort_partial(ps);
        return VOS_COMPAT_ERR_STAGING_INCOMPLETE;
    }
    if (expected_digest == NULL) {
        abort_partial(ps);
        return VOS_COMPAT_ERR_STAGING_DIGEST;
    }

    struct vos_compat_hash actual;
    if (!vos_sha256(ps->bytes, ps->accum_bytes, actual.bytes)) {
        abort_partial(ps);
        return VOS_COMPAT_ERR_CRYPTO;
    }
    if (!equal_hashes(&actual, expected_digest)) {
        abort_partial(ps);
        return VOS_COMPAT_ERR_STAGING_DIGEST;
    }

    if (svc->staged_count >= VOS_COMPAT_MAX_STAGED_OBJS) {
        abort_partial(ps);
        return VOS_COMPAT_ERR_STAGING_OVER_BUDGET;
    }

    struct vos_compat_staged_obj *dst = &svc->staged[svc->staged_count];
    memset(dst, 0, sizeof(*dst));
    dst->valid = 1u;
    dst->obj_id = slot_id;
    dst->total_bytes = ps->accum_bytes;
    dst->executable = 0u;
    dst->content_digest = actual;
    memcpy(dst->bytes, ps->bytes, ps->accum_bytes);
    svc->staged_count += 1u;

    if (out_staged != NULL) {
        *out_staged = *dst;
    }
    abort_partial(ps);
    return VOS_COMPAT_OK;
}

static int profiles_match(const struct vos_compat_profile *a,
                          const struct vos_compat_profile *b)
{
    return a->profile_id == b->profile_id &&
           a->toolchain_id == b->toolchain_id &&
           a->config_id == b->config_id &&
           a->step_budget == b->step_budget;
}

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
                                             uint32_t *out_epoch)
{
    if (svc == NULL || closure_digest == NULL || req_profile == NULL ||
        out_slot == NULL || out_epoch == NULL) {
        return VOS_COMPAT_ERR_INVALID_ARG;
    }
    if (!check_authorities(svc)) {
        return VOS_COMPAT_ERR_AUTHORITY;
    }
    if (closure_ok == 0u) {
        return VOS_COMPAT_ERR_MISSING_CLOSURE;
    }
    if (comp_service_ep_ok == 0u) {
        return VOS_COMPAT_ERR_COMP_SERVICE;
    }
    if (vos_compat_profile_validate(req_profile) != VOS_COMPAT_OK ||
        !profiles_match(&svc->profile, req_profile) ||
        toolchain_id != req_profile->toolchain_id ||
        config_id != req_profile->config_id) {
        return VOS_COMPAT_ERR_INVALID_PROFILE;
    }
    if (closure_objs > req_profile->pools[VOS_COMPAT_POOL_SOURCE_INDEX].max_capacity ||
        closure_edges > req_profile->max_source_edges ||
        closure_depth > req_profile->max_source_depth) {
        return VOS_COMPAT_ERR_INDEX_EXHAUSTED;
    }
    if (svc->epoch_retired != 0u || svc->next_job_epoch >= req_profile->epoch_limit) {
        svc->epoch_retired = 1u;
        return VOS_COMPAT_ERR_EPOCH_EXHAUSTED;
    }

    const uint32_t max_jobs = req_profile->pools[VOS_COMPAT_POOL_BUILD_JOBS].max_capacity;
    uint32_t active_jobs = 0u;
    uint32_t free_idx = VOS_COMPAT_MAX_JOBS;
    for (uint32_t i = 0u; i < VOS_COMPAT_MAX_JOBS; ++i) {
        const uint32_t lc = svc->jobs[i].lifecycle;
        if (lc != VOS_COMPAT_LC_FREE && lc != VOS_COMPAT_LC_REUSABLE) {
            active_jobs += 1u;
        } else if (free_idx == VOS_COMPAT_MAX_JOBS) {
            free_idx = i;
        }
    }
    if (active_jobs >= max_jobs || free_idx >= VOS_COMPAT_MAX_JOBS) {
        return VOS_COMPAT_ERR_JOB_POOL_EXHAUSTED;
    }

    uint32_t next_lc = 0u;
    const enum vos_compat_status lc_st = vos_compat_lifecycle_step(
        svc->jobs[free_idx].lifecycle, VOS_COMPAT_ACT_BIND, &next_lc);
    if (lc_st != VOS_COMPAT_OK) {
        return lc_st;
    }

    struct vos_compat_build_job *jb = &svc->jobs[free_idx];
    memset(jb, 0, sizeof(*jb));
    jb->handle_slot = free_idx;
    jb->epoch = svc->next_job_epoch;
    svc->next_job_epoch += 1u;
    jb->lifecycle = next_lc;
    jb->stage = VOS_COMPAT_JOB_RUNNING;
    jb->closure_digest = *closure_digest;
    jb->profile_id = req_profile->profile_id;
    jb->step_budget = req_profile->step_budget;
    jb->output_executable = 0u;

    *out_slot = jb->handle_slot;
    *out_epoch = jb->epoch;
    return VOS_COMPAT_OK;
}

static struct vos_compat_build_job *find_job(struct vos_compat_service *svc,
                                             uint32_t slot,
                                             uint32_t epoch,
                                             enum vos_compat_status *err_out)
{
    if (slot >= VOS_COMPAT_MAX_JOBS) {
        *err_out = VOS_COMPAT_ERR_STALE_HANDLE;
        return NULL;
    }
    struct vos_compat_build_job *jb = &svc->jobs[slot];
    if (jb->lifecycle == VOS_COMPAT_LC_FREE || jb->epoch != epoch) {
        *err_out = VOS_COMPAT_ERR_STALE_HANDLE;
        return NULL;
    }
    return jb;
}

enum vos_compat_status vos_compat_advance_build(struct vos_compat_service *svc,
                                              uint32_t slot,
                                              uint32_t epoch,
                                              uint32_t steps_req,
                                              uint32_t workset_bytes,
                                              const struct vos_compat_hash *output_digest,
                                              const uint8_t *diag_msg,
                                              uint32_t diag_msg_len,
                                              uint32_t finish_build)
{
    if (svc == NULL || (finish_build != 0u && output_digest == NULL) ||
        (diag_msg_len > 0u && diag_msg == NULL)) {
        return VOS_COMPAT_ERR_INVALID_ARG;
    }
    if (!check_authorities(svc)) {
        return VOS_COMPAT_ERR_AUTHORITY;
    }
    enum vos_compat_status st = VOS_COMPAT_OK;
    struct vos_compat_build_job *jb = find_job(svc, slot, epoch, &st);
    if (jb == NULL) {
        return st;
    }
    if (jb->lifecycle != VOS_COMPAT_LC_BOUND || jb->stage != VOS_COMPAT_JOB_RUNNING) {
        return VOS_COMPAT_ERR_JOB_NOT_ACTIVE;
    }
    if (steps_req > jb->step_budget || jb->steps_used > jb->step_budget - steps_req) {
        return VOS_COMPAT_ERR_BUDGET_EXPANSION;
    }
    const uint32_t arena_cap = svc->profile.pools[VOS_COMPAT_POOL_PASS_ARENAS].max_capacity;
    if (workset_bytes > arena_cap) {
        jb->stage = VOS_COMPAT_JOB_FAILED;
        memset(&jb->output_digest, 0, sizeof(jb->output_digest));
        jb->output_executable = 0u;
        return VOS_COMPAT_ERR_PASS_ARENA_EXHAUSTED;
    }

    jb->steps_used += steps_req;
    if (diag_msg_len > 0u) {
        const uint32_t max_recs =
            svc->profile.pools[VOS_COMPAT_POOL_DIAGNOSTICS_BUFFER].max_capacity;
        const uint32_t max_rec_bytes = svc->profile.max_diag_record_bytes;
        const uint32_t max_diag_bytes = svc->profile.max_diag_bytes;
        const uint32_t rec_len = diag_msg_len > max_rec_bytes ? max_rec_bytes : diag_msg_len;
        if (diag_msg_len > max_rec_bytes) {
            jb->diag_truncated = 1u;
        }
        if (jb->diag_count >= max_recs || rec_len > max_diag_bytes - jb->diag_bytes) {
            jb->diag_truncated = 1u;
        } else {
            struct vos_compat_diag_record *dr = &jb->diags[jb->diag_count];
            memset(dr, 0, sizeof(*dr));
            dr->seq = jb->diag_count;
            dr->len = rec_len;
            dr->is_truncation_marker = 0u;
            memcpy(dr->text, diag_msg, rec_len);
            jb->diag_count += 1u;
            jb->diag_bytes += rec_len;
        }
    }

    if (finish_build != 0u) {
        jb->stage = VOS_COMPAT_JOB_COMPLETED;
        jb->output_digest = *output_digest;
        jb->output_executable = 0u;
    }
    return VOS_COMPAT_OK;
}

enum vos_compat_status vos_compat_read_diagnostics(const struct vos_compat_service *svc,
                                                 uint32_t slot,
                                                 uint32_t epoch,
                                                 uint32_t result_ep_ok,
                                                 uint32_t seq_start,
                                                 uint32_t max_records,
                                                 uint32_t max_bytes,
                                                 struct vos_compat_diag_view *out_view)
{
    if (svc == NULL || out_view == NULL) {
        return VOS_COMPAT_ERR_INVALID_ARG;
    }
    if (!check_authorities(svc)) {
        return VOS_COMPAT_ERR_AUTHORITY;
    }
    if (result_ep_ok == 0u) {
        return VOS_COMPAT_ERR_MISSING_GRANT;
    }
    if (slot >= VOS_COMPAT_MAX_JOBS ||
        svc->jobs[slot].lifecycle == VOS_COMPAT_LC_FREE ||
        svc->jobs[slot].epoch != epoch) {
        return VOS_COMPAT_ERR_STALE_HANDLE;
    }
    const struct vos_compat_build_job *jb = &svc->jobs[slot];
    memset(out_view, 0, sizeof(*out_view));

    const uint32_t cap_recs =
        svc->profile.pools[VOS_COMPAT_POOL_DIAGNOSTICS_BUFFER].max_capacity;
    const uint32_t cap_bytes = svc->profile.max_diag_bytes;
    const uint32_t eff_recs = max_records < cap_recs ? max_records : cap_recs;
    const uint32_t eff_bytes = max_bytes < cap_bytes ? max_bytes : cap_bytes;

    uint32_t trunc = jb->diag_truncated;
    if (max_records > cap_recs || max_bytes > cap_bytes) {
        trunc = 1u;
    }

    for (uint32_t i = seq_start; i < jb->diag_count; ++i) {
        const struct vos_compat_diag_record *src = &jb->diags[i];
        if (out_view->record_count >= eff_recs ||
            src->len > eff_bytes - out_view->total_bytes) {
            trunc = 1u;
            break;
        }
        out_view->records[out_view->record_count] = *src;
        out_view->record_count += 1u;
        out_view->total_bytes += src->len;
    }

    if (trunc != 0u) {
        out_view->truncated = 1u;
        out_view->marker_code = VOS_COMPAT_DIAG_TRUNCATED_MARKER;
        if (out_view->record_count < VOS_COMPAT_MAX_DIAG_RECORDS) {
            struct vos_compat_diag_record *m = &out_view->records[out_view->record_count];
            memset(m, 0, sizeof(*m));
            m->seq = out_view->record_count;
            m->is_truncation_marker = 1u;
            out_view->record_count += 1u;
        }
    }
    return VOS_COMPAT_OK;
}

enum vos_compat_status vos_compat_cancel_build(struct vos_compat_service *svc,
                                             uint32_t slot,
                                             uint32_t epoch,
                                             uint32_t cancel_cap_ok,
                                             uint32_t interrupt_mid_sweep)
{
    if (svc == NULL) {
        return VOS_COMPAT_ERR_INVALID_ARG;
    }
    if (!check_authorities(svc)) {
        return VOS_COMPAT_ERR_AUTHORITY;
    }
    if (cancel_cap_ok == 0u) {
        return VOS_COMPAT_ERR_MISSING_GRANT;
    }
    enum vos_compat_status st = VOS_COMPAT_OK;
    struct vos_compat_build_job *jb = find_job(svc, slot, epoch, &st);
    if (jb == NULL) {
        return st;
    }

    uint32_t lc = jb->lifecycle;
    if (vos_compat_lifecycle_step(lc, VOS_COMPAT_ACT_QUIESCE, &lc) != VOS_COMPAT_OK ||
        vos_compat_lifecycle_step(lc, VOS_COMPAT_ACT_REVOKE, &lc) != VOS_COMPAT_OK ||
        vos_compat_lifecycle_step(lc, VOS_COMPAT_ACT_SWEEP, &lc) != VOS_COMPAT_OK) {
        return VOS_COMPAT_ERR_JOB_NOT_ACTIVE;
    }

    jb->stage = VOS_COMPAT_JOB_CANCELLED;
    memset(&jb->output_digest, 0, sizeof(jb->output_digest));
    jb->output_executable = 0u;

    if (interrupt_mid_sweep != 0u) {
        (void)vos_compat_lifecycle_step(lc, VOS_COMPAT_ACT_INTERRUPT, &lc);
        jb->lifecycle = lc;
        return VOS_COMPAT_ERR_LIFECYCLE_INTERRUPTED;
    }

    if (vos_compat_lifecycle_step(lc, VOS_COMPAT_ACT_RELEASE, &lc) != VOS_COMPAT_OK) {
        jb->lifecycle = lc;
        return VOS_COMPAT_ERR_LIFECYCLE_INTERRUPTED;
    }
    jb->lifecycle = lc;
    return VOS_COMPAT_OK;
}

enum vos_compat_status vos_compat_submit_successor_admission(struct vos_compat_service *svc,
                                                           const struct vos_compat_admission_pkg *pkg)
{
    if (svc == NULL || pkg == NULL) {
        return VOS_COMPAT_ERR_INVALID_ARG;
    }
    if (!check_authorities(svc)) {
        return VOS_COMPAT_ERR_AUTHORITY;
    }
    enum vos_compat_status st = VOS_COMPAT_OK;
    const struct vos_compat_build_job *jb = find_job(svc, pkg->job_slot, pkg->job_epoch, &st);
    if (jb == NULL) {
        return st;
    }
    if (jb->stage != VOS_COMPAT_JOB_COMPLETED) {
        return VOS_COMPAT_ERR_JOB_NOT_ACTIVE;
    }
    if (pkg->proof_complete == 0u) {
        return VOS_COMPAT_ERR_PROOF_INCOMPLETE;
    }
    if (pkg->checking_arena_ok == 0u) {
        return VOS_COMPAT_ERR_CHECKING_ARENA;
    }
    if (pkg->roster_entries >
            svc->profile.pools[VOS_COMPAT_POOL_CANDIDATE_CLOSURE].max_capacity ||
        pkg->checking_steps > svc->profile.max_checking_steps) {
        return VOS_COMPAT_ERR_CHECKING_STEPS;
    }
    if (pkg->roster_valid == 0u) {
        return VOS_COMPAT_ERR_INADMISSIBLE_ROSTER;
    }
    if (pkg->tal_ok == 0u || pkg->source_corr_ok == 0u) {
        return VOS_COMPAT_ERR_TAL_OR_CORR;
    }
    if (pkg->cache_hit_used != 0u) {
        if (!vos_compat_cache_lookup(svc, &pkg->cache_id, NULL)) {
            return VOS_COMPAT_ERR_CACHE_MISS;
        }
    }

    struct vos_compat_hash key;
    if (vos_compat_compute_cache_key(&pkg->cache_id, &key) != VOS_COMPAT_OK) {
        return VOS_COMPAT_ERR_CRYPTO;
    }
    const uint32_t cache_cap =
        svc->profile.pools[VOS_COMPAT_POOL_PROOF_CACHE].max_capacity;
    if (cache_cap > 0u) {
        const uint32_t idx = svc->cache_write_cursor % cache_cap;
        svc->proof_cache[idx].valid = 1u;
        svc->proof_cache[idx].identity = pkg->cache_id;
        svc->proof_cache[idx].key_digest = key;
        svc->proof_cache[idx].proof_digest = pkg->candidate_root;
        svc->proof_cache[idx].verified = 1u;
        svc->cache_write_cursor = (svc->cache_write_cursor + 1u) % cache_cap;
    }

    svc->has_admitted = 1u;
    svc->admitted_root = pkg->candidate_root;
    svc->admitted_roster_hash = pkg->candidate_roster_hash;
    svc->consent_granted = 0u;
    svc->successor_booted = 0u;
    return VOS_COMPAT_OK;
}

enum vos_compat_status vos_compat_request_generation_consent(struct vos_compat_service *svc,
                                                           const struct vos_compat_consent_req *req)
{
    if (svc == NULL || req == NULL) {
        return VOS_COMPAT_ERR_INVALID_ARG;
    }
    if (req->external_roaming_key != 0u) {
        return VOS_COMPAT_ERR_EXTERNAL_AUTH_DECLINED;
    }
    if (!check_authorities(svc)) {
        return VOS_COMPAT_ERR_AUTHORITY;
    }
    const uint32_t max_consent =
        svc->profile.pools[VOS_COMPAT_POOL_CONSENT_TRANSFER].max_capacity;
    if (svc->consent_outstanding >= max_consent) {
        return VOS_COMPAT_ERR_CONSENT_POOL_EXHAUSTED;
    }
    if (svc->has_admitted == 0u) {
        return VOS_COMPAT_ERR_NO_ADMITTED;
    }
    if (!equal_hashes(&req->candidate_root, &svc->admitted_root) ||
        !equal_hashes(&req->roster_hash, &svc->admitted_roster_hash)) {
        return VOS_COMPAT_ERR_CONSENT_MISMATCH;
    }
    if (req->on_die_cred_ok == 0u) {
        return VOS_COMPAT_ERR_ON_DIE_CRED_ABSENT;
    }
    if (req->user_consented == 0u) {
        return VOS_COMPAT_ERR_CONSENT_MISMATCH;
    }
    svc->consent_granted = 1u;
    svc->consent_outstanding += 1u;
    return VOS_COMPAT_OK;
}

enum vos_compat_status vos_compat_boot_successor(struct vos_compat_service *svc)
{
    if (svc == NULL) {
        return VOS_COMPAT_ERR_INVALID_ARG;
    }
    if (!check_authorities(svc)) {
        return VOS_COMPAT_ERR_AUTHORITY;
    }
    if (svc->has_admitted == 0u || svc->consent_granted == 0u) {
        return VOS_COMPAT_ERR_NO_ADMITTED;
    }
    svc->running_gen_root = svc->admitted_root;
    svc->running_roster_hash = svc->admitted_roster_hash;
    svc->boot_epoch += 1u;
    svc->consent_granted = 0u;
    svc->consent_outstanding = 0u;
    svc->successor_booted = 1u;
    return VOS_COMPAT_OK;
}

enum vos_compat_status vos_compat_read_successor_test_result(struct vos_compat_service *svc,
                                                           const struct vos_compat_test_result *res,
                                                           const struct vos_compat_hash *expected_root,
                                                           uint64_t expected_test_id,
                                                           struct vos_compat_test_result *out_res)
{
    if (svc == NULL || res == NULL || expected_root == NULL || out_res == NULL) {
        return VOS_COMPAT_ERR_INVALID_ARG;
    }
    if (!check_authorities(svc)) {
        return VOS_COMPAT_ERR_AUTHORITY;
    }
    if (svc->successor_booted == 0u) {
        return VOS_COMPAT_ERR_NOT_BOOTED;
    }
    if (res->grant_ok == 0u) {
        return VOS_COMPAT_ERR_MISSING_GRANT;
    }
    if (res->result_bytes > svc->profile.max_result_bytes) {
        return VOS_COMPAT_ERR_RESULT_OVER_BUDGET;
    }
    if (!equal_hashes(&res->candidate_root, expected_root) ||
        !equal_hashes(&res->candidate_root, &svc->running_gen_root) ||
        res->test_id != expected_test_id ||
        res->boot_epoch != svc->boot_epoch) {
        return VOS_COMPAT_ERR_RESULT_UNBOUND;
    }
    *out_res = *res;
    svc->has_last_test_result = 1u;
    svc->last_test_result = *res;
    return VOS_COMPAT_OK;
}

enum vos_compat_status vos_compat_attempt_forbidden_op(const struct vos_compat_service *svc,
                                                       uint32_t forbidden_op)
{
    (void)svc;
    switch (forbidden_op) {
    case VOS_COMPAT_FORBID_EXEC_STAGED_NATIVE:
    case VOS_COMPAT_FORBID_WASM_NATIVE_ESCAPE:
        return VOS_COMPAT_ERR_SAME_GEN_NATIVE_EXEC;
    case VOS_COMPAT_FORBID_REWRITE_RUNNING_ROSTER:
        return VOS_COMPAT_ERR_REWRITE_ROSTER;
    case VOS_COMPAT_FORBID_INSTALL_RUNTIME_PLUGIN:
        return VOS_COMPAT_ERR_RUNTIME_PLUGIN;
    case VOS_COMPAT_FORBID_LOAD_EXTERNAL_PATH:
        return VOS_COMPAT_ERR_EXTERNAL_PATH;
    case VOS_COMPAT_FORBID_BYPASS_CHECKING:
        return VOS_COMPAT_ERR_BYPASS_CHECKING;
    default:
        return VOS_COMPAT_ERR_SAME_GEN_NATIVE_EXEC;
    }
}
