// SPDX-License-Identifier: Apache-2.0
#include "vos_router.h"

static int extent_bounds_valid(const vos_router_extent *ext)
{
    if (ext == NULL || ext->span == 0U) {
        return 0;
    }
    return ext->span <= (UINT32_MAX - ext->base);
}

int vos_router_extent_inside(const vos_router_extent *ext, uint32_t addr)
{
    if (!extent_bounds_valid(ext)) {
        return 0;
    }
    return addr >= ext->base && (addr - ext->base) < ext->span;
}

int vos_router_extents_overlap(const vos_router_extent *a, const vos_router_extent *b)
{
    if (!extent_bounds_valid(a) || !extent_bounds_valid(b)) {
        return 0;
    }
    const uint32_t a_end = a->base + a->span;
    const uint32_t b_end = b->base + b->span;
    return a->base < b_end && b->base < a_end;
}

static int extents_separated(const vos_router_extent *extents, size_t count)
{
    for (size_t i = 0U; i < count; ++i) {
        if (!extent_bounds_valid(&extents[i])) {
            return 0;
        }
        for (size_t j = i + 1U; j < count; ++j) {
            if (!extent_bounds_valid(&extents[j])) {
                return 0;
            }
            if (extents[i].domain != extents[j].domain
                && vos_router_extents_overlap(&extents[i], &extents[j])) {
                return 0;
            }
        }
    }
    return 1;
}

int vos_router_composition_valid(const vos_router_composition *comp)
{
    if (comp == NULL) {
        return 0;
    }
    if (comp->extent_count > 0U && comp->extents == NULL) {
        return 0;
    }
    if (!extents_separated(comp->extents, comp->extent_count)) {
        return 0;
    }
    if (comp->queue_bound == 0U || comp->ring_capacity == 0U
        || comp->queue_bound > comp->ring_capacity || comp->result_bound == 0U) {
        return 0;
    }
    return 1;
}

const vos_router_extent *vos_router_find_extent(
    const vos_router_composition *comp, uint32_t domain, uint32_t space)
{
    if (!vos_router_composition_valid(comp)) {
        return NULL;
    }
    for (size_t i = 0U; i < comp->extent_count; ++i) {
        if (comp->extents[i].domain == domain && comp->extents[i].space == space) {
            return &comp->extents[i];
        }
    }
    return NULL;
}

static int address_hits_foreign_domain(
    const vos_router_composition *comp, uint32_t domain, uint32_t addr)
{
    for (size_t i = 0U; i < comp->extent_count; ++i) {
        if (comp->extents[i].domain != domain
            && vos_router_extent_inside(&comp->extents[i], addr)) {
            return 1;
        }
    }
    return 0;
}

static int word_has_tag(const vos_router_word *word)
{
    return word->tag != 0U;
}

vos_router_status vos_router_validate_write(
    const vos_router_composition *comp, uint32_t domain, uint32_t space,
    const vos_router_write_record *records, size_t count)
{
    const vos_router_extent *target = vos_router_find_extent(comp, domain, space);
    if (target == NULL) {
        return VOS_ROUTER_ERR_NO_EXTENT;
    }
    if (count > 0U && records == NULL) {
        return VOS_ROUTER_ERR_INVALID;
    }
    for (size_t i = 0U; i < count; ++i) {
        if (word_has_tag(&records[i].word)) {
            return VOS_ROUTER_ERR_TAGGED_WRITE;
        }
        if (address_hits_foreign_domain(comp, domain, records[i].address)) {
            return VOS_ROUTER_ERR_CROSS_DOMAIN;
        }
        if (!vos_router_extent_inside(target, records[i].address)) {
            return VOS_ROUTER_ERR_OUT_OF_EXTENT;
        }
    }
    return VOS_ROUTER_OK;
}

vos_router_status vos_router_stage_index_key(
    const vos_router_composition *comp, uint32_t domain, uint32_t space,
    uint32_t slot, const vos_router_word *words, size_t word_count,
    vos_router_write_record *out_records, size_t out_cap)
{
    const vos_router_extent *target = vos_router_find_extent(comp, domain, space);
    if (target == NULL) {
        return VOS_ROUTER_ERR_NO_EXTENT;
    }
    if ((word_count > 0U && (words == NULL || out_records == NULL))
        || word_count > out_cap) {
        return VOS_ROUTER_ERR_CAPACITY;
    }
    if (slot > target->span || word_count > (size_t)(target->span - slot)) {
        return VOS_ROUTER_ERR_OUT_OF_EXTENT;
    }
    for (size_t i = 0U; i < word_count; ++i) {
        if (word_has_tag(&words[i])) {
            return VOS_ROUTER_ERR_TAGGED_WRITE;
        }
        const uint32_t addr = target->base + slot + (uint32_t)i;
        if (address_hits_foreign_domain(comp, domain, addr)) {
            return VOS_ROUTER_ERR_CROSS_DOMAIN;
        }
        out_records[i].address = addr;
        out_records[i].word = words[i];
    }
    return VOS_ROUTER_OK;
}

int vos_router_cap_derivable(const vos_router_ns_cap *ns, const vos_router_obj_cap *obj)
{
    if (ns == NULL || obj == NULL) {
        return 0;
    }
    return obj->domain == ns->domain
        && obj->space == ns->space
        && (obj->rights & ns->rights) == obj->rights;
}

static int ask_admitted(const vos_router_ns_cap *ns, const vos_router_ask *ask)
{
    return ask->domain == ns->domain
        && ask->space == ns->space
        && (ask->rights & ns->rights) == ask->rights;
}

const vos_router_session *vos_router_live_session(
    const vos_router_composition *comp, const vos_router_session *sessions,
    size_t session_count, uint32_t sid)
{
    if (!vos_router_composition_valid(comp) || (session_count > 0U && sessions == NULL)) {
        return NULL;
    }
    for (size_t i = 0U; i < session_count; ++i) {
        if (sessions[i].active != 0U
            && sessions[i].id == sid
            && sessions[i].epoch == comp->live_epoch) {
            return &sessions[i];
        }
    }
    return NULL;
}

static vos_router_answer answer_under(
    const vos_router_composition *comp, const vos_router_ns_cap *ns,
    const vos_router_ask *ask)
{
    vos_router_answer ans = {
        .kind = VOS_ROUTER_ANSWER_REFUSED,
        .obj_cap = {0U, 0U, 0U, 0U}
    };
    if (ask_admitted(ns, ask)) {
        ans.kind = VOS_ROUTER_ANSWER_GRANTED;
        ans.obj_cap.domain = ns->domain;
        ans.obj_cap.space = ns->space;
        ans.obj_cap.object = ask->object;
        ans.obj_cap.rights = ask->rights;
        return ans;
    }
    if (comp->discipline == VOS_ROUTER_ANSWER_EMPTY) {
        ans.kind = VOS_ROUTER_ANSWER_EMPTY_RESULT;
        return ans;
    }
    if (comp->discipline == VOS_ROUTER_GRANT_TRUNCATED) {
        ans.kind = VOS_ROUTER_ANSWER_GRANTED;
        ans.obj_cap.domain = ns->domain;
        ans.obj_cap.space = ns->space;
        ans.obj_cap.object = ask->object;
        ans.obj_cap.rights = ask->rights & ns->rights;
        return ans;
    }
    return ans;
}

vos_router_answer vos_router_route(
    const vos_router_composition *comp, const vos_router_session *sessions,
    size_t session_count, uint32_t sid, const vos_router_ask *ask)
{
    const vos_router_answer refused = {
        .kind = VOS_ROUTER_ANSWER_REFUSED,
        .obj_cap = {0U, 0U, 0U, 0U}
    };
    if (!vos_router_composition_valid(comp) || ask == NULL) {
        return refused;
    }
    const vos_router_session *live = vos_router_live_session(comp, sessions, session_count, sid);
    if (live == NULL) {
        return refused;
    }
    return answer_under(comp, &live->cap, ask);
}

vos_router_status vos_router_deliver_results(
    const vos_router_composition *comp, const vos_router_session *sessions,
    size_t session_count, uint32_t sid, const vos_router_obj_cap *candidates,
    size_t candidate_count, vos_router_obj_cap *out_results, size_t out_cap,
    size_t *out_count)
{
    if (out_count != NULL) {
        *out_count = 0U;
    }
    if (!vos_router_composition_valid(comp)) {
        return VOS_ROUTER_ERR_INVALID;
    }
    const vos_router_session *live = vos_router_live_session(comp, sessions, session_count, sid);
    if (live == NULL) {
        return VOS_ROUTER_ERR_STALE_EPOCH;
    }
    if (candidate_count > (size_t)comp->result_bound || candidate_count > out_cap) {
        return VOS_ROUTER_ERR_CAPACITY;
    }
    if (candidate_count > 0U && (candidates == NULL || out_results == NULL)) {
        return VOS_ROUTER_ERR_INVALID;
    }
    for (size_t i = 0U; i < candidate_count; ++i) {
        if (!vos_router_cap_derivable(&live->cap, &candidates[i])) {
            return VOS_ROUTER_ERR_DENIED;
        }
    }
    for (size_t i = 0U; i < candidate_count; ++i) {
        out_results[i] = candidates[i];
    }
    if (out_count != NULL) {
        *out_count = candidate_count;
    }
    return VOS_ROUTER_OK;
}

vos_router_txn vos_router_commit_txn(
    const vos_router_sub *subs, size_t sub_count,
    vos_submit_result ring_status, vos_router_txn txn)
{
    /* Publication and ring fullness never backpressure transaction commit. */
    (void)subs;
    (void)sub_count;
    (void)ring_status;
    txn.committed = 1U;
    return txn;
}

vos_router_status vos_router_publish_deltas(
    const vos_router_composition *comp, const vos_router_txn *txn,
    vos_router_sub *sub, const vos_delta *deltas, size_t delta_count)
{
    if (!vos_router_composition_valid(comp) || txn == NULL || sub == NULL) {
        return VOS_ROUTER_ERR_INVALID;
    }
    if (sub->active == 0U || sub->queue == NULL
        || sub->queue_cap < (size_t)comp->queue_bound
        || sub->count > (size_t)comp->queue_bound) {
        return VOS_ROUTER_ERR_INVALID;
    }
    if (delta_count > 0U && deltas == NULL) {
        return VOS_ROUTER_ERR_INVALID;
    }
    for (size_t i = 0U; i < delta_count; ++i) {
        if (deltas[i].kind != VOS_DELTA_ADDED && deltas[i].kind != VOS_DELTA_REMOVED) {
            return VOS_ROUTER_ERR_INVALID;
        }
    }
    if (txn->committed == 0U) {
        return VOS_ROUTER_OK;
    }
    if (sub->phase == VOS_SUB_RESCAN_REQUIRED) {
        return VOS_ROUTER_OK;
    }
    const size_t qbound = (size_t)comp->queue_bound;
    if (delta_count <= (qbound - sub->count)) {
        for (size_t i = 0U; i < delta_count; ++i) {
            sub->queue[sub->count + i] = deltas[i];
        }
        sub->count += delta_count;
        return VOS_ROUTER_OK;
    }
    /* Overflow: keep at most queue_bound - 1 leading deltas and emit one rescan marker. */
    const size_t prefix = qbound - 1U;
    if (sub->count < prefix) {
        const size_t copy_n = prefix - sub->count;
        for (size_t i = 0U; i < copy_n; ++i) {
            sub->queue[sub->count + i] = deltas[i];
        }
    }
    sub->queue[prefix].kind = VOS_DELTA_RESCAN;
    sub->queue[prefix].object_id = 0U;
    sub->count = qbound;
    sub->phase = VOS_SUB_RESCAN_REQUIRED;
    return VOS_ROUTER_OK;
}

void vos_router_reboot_subs(vos_router_sub *subs, size_t sub_count)
{
    if (subs == NULL) {
        return;
    }
    for (size_t i = 0U; i < sub_count; ++i) {
        subs[i].active = 0U;
        subs[i].phase = VOS_SUB_RESCAN_REQUIRED;
        subs[i].count = 0U;
        subs[i].id = 0U;
        subs[i].domain = 0U;
        subs[i].space = 0U;
        if (subs[i].queue != NULL) {
            for (size_t j = 0U; j < subs[i].queue_cap; ++j) {
                subs[i].queue[j].kind = VOS_DELTA_RESCAN;
                subs[i].queue[j].object_id = 0U;
            }
        }
    }
}

vos_router_status vos_router_establish_sub(
    const vos_router_composition *comp, vos_router_sub *sub,
    uint32_t id, uint32_t domain, uint32_t space,
    vos_delta *queue_buf, size_t queue_cap)
{
    if (!vos_router_composition_valid(comp) || sub == NULL || queue_buf == NULL) {
        return VOS_ROUTER_ERR_INVALID;
    }
    if (queue_cap < (size_t)comp->queue_bound) {
        return VOS_ROUTER_ERR_CAPACITY;
    }
    sub->id = id;
    sub->domain = domain;
    sub->space = space;
    sub->active = 1U;
    sub->phase = VOS_SUB_LIVE;
    sub->queue = queue_buf;
    sub->queue_cap = queue_cap;
    sub->queue[0].kind = VOS_DELTA_RESCAN;
    sub->queue[0].object_id = 0U;
    sub->count = 1U;
    return VOS_ROUTER_OK;
}

/* --- Credential handles (CredentialHandles.v) --- */

static int policy_valid(const vos_cred_policy *policy)
{
    return policy != NULL
        && policy->scope_count <= 64U
        && policy->operation_count <= 64U;
}

static int schema_accepts(const vos_cred_policy *policy, const vos_cred_request *req)
{
    if (!policy_valid(policy) || req == NULL) {
        return 0;
    }
    if (req->role >= policy->role_count
        || req->principal >= policy->principal_count
        || req->scope_bit >= policy->scope_count
        || req->op_bit >= policy->operation_count
        || req->transcript >= policy->transcript_count) {
        return 0;
    }
    if (policy->protocol_operation != NULL
        && !policy->protocol_operation(req->role, req->op_bit, policy->policy_ctx)) {
        return 0;
    }
    if (req->byte_len > 0U && req->bytes == NULL) {
        return 0;
    }
    if (policy->request_limit != NULL) {
        const uint32_t limit = policy->request_limit(req->role, req->op_bit, policy->policy_ctx);
        if (req->byte_len > (size_t)limit) {
            return 0;
        }
    }
    return 1;
}

static int bindings_match(const vos_cred_bindings *cred, const vos_cred_request *req)
{
    if (req->scope_bit >= 64U || req->op_bit >= 64U) {
        return 0;
    }
    const uint64_t scope_flag = ((uint64_t)1U) << req->scope_bit;
    const uint64_t op_flag = ((uint64_t)1U) << req->op_bit;
    return req->role == cred->role
        && req->principal == cred->principal
        && (cred->scope_mask & scope_flag) != 0U
        && (cred->op_mask & op_flag) != 0U
        && req->transcript == cred->transcript;
}

int vos_cred_delegates(
    const vos_cred_policy *policy,
    const vos_cred_bindings *parent,
    const vos_cred_bindings *child)
{
    if (!policy_valid(policy) || parent == NULL || child == NULL) {
        return 0;
    }
    if (child->role != parent->role || child->principal != parent->principal) {
        return 0;
    }
    if ((child->scope_mask & parent->scope_mask) != child->scope_mask) {
        return 0;
    }
    if ((child->op_mask & parent->op_mask) != child->op_mask) {
        return 0;
    }
    if (child->transcript != parent->transcript) {
        return 0;
    }
    if (child->use_ceiling > parent->use_ceiling || child->expiry > parent->expiry) {
        return 0;
    }
    if (child->account_id != parent->account_id) {
        return 0;
    }
    return 1;
}

int vos_cred_authorize_and_charge(
    const vos_cred_policy *policy,
    const vos_cred_bindings *cred,
    vos_cred_server *server,
    const vos_cred_request *req)
{
    if (!policy_valid(policy) || cred == NULL || server == NULL || req == NULL) {
        return 0;
    }
    if (server->account_used == NULL || cred->account_id >= server->account_count) {
        return 0;
    }
    if (!bindings_match(cred, req) || !schema_accepts(policy, req)) {
        return 0;
    }
    const uint32_t used = server->account_used[cred->account_id];
    if (used >= cred->use_ceiling) {
        return 0;
    }
    if (server->server_now >= cred->expiry) {
        return 0;
    }
    if (policy->needs_approval != NULL
        && policy->needs_approval(req->role, req->op_bit, policy->policy_ctx)) {
        if (server->consent_allows == NULL
            || !server->consent_allows(cred, req, used, server->consent_ctx)) {
            return 0;
        }
    }
    server->account_used[cred->account_id] = used + 1U;
    return 1;
}

void vos_cred_vault_init(vos_cred_vault *vault, vos_cred_vault_slot *slots, size_t capacity)
{
    if (vault == NULL) {
        return;
    }
    vault->slots = slots;
    vault->capacity = capacity;
    vault->next_gen = 1U;
    if (slots != NULL) {
        for (size_t i = 0U; i < capacity; ++i) {
            slots[i].occupied = 0U;
            slots[i].generation = 0U;
        }
    }
}

vos_router_status vos_cred_issue_handle(
    vos_cred_vault *vault, const vos_cred_bindings *bindings,
    vos_cred_handle *out_handle)
{
    if (vault == NULL || vault->slots == NULL || bindings == NULL || out_handle == NULL) {
        return VOS_ROUTER_ERR_INVALID;
    }
    if (vault->next_gen == 0U) {
        return VOS_ROUTER_ERR_CAPACITY;
    }
    for (size_t i = 0U; i < vault->capacity; ++i) {
        if (vault->slots[i].occupied == 0U) {
            const uint32_t gen = vault->next_gen;
            vault->next_gen = (gen < UINT32_MAX) ? (gen + 1U) : 0U;
            vault->slots[i].occupied = 1U;
            vault->slots[i].generation = gen;
            vault->slots[i].bindings = *bindings;
            out_handle->kind = VOS_HANDLE_SEALED;
            out_handle->slot_id = (uint32_t)i;
            out_handle->generation = gen;
            return VOS_ROUTER_OK;
        }
    }
    return VOS_ROUTER_ERR_CAPACITY;
}

vos_router_status vos_cred_resolve_sealed(
    const vos_cred_vault *vault, const vos_cred_handle *handle,
    vos_cred_bindings *out_bindings)
{
    if (vault == NULL || vault->slots == NULL || handle == NULL || out_bindings == NULL) {
        return VOS_ROUTER_ERR_INVALID;
    }
    if (handle->kind != VOS_HANDLE_SEALED) {
        return VOS_ROUTER_ERR_DENIED;
    }
    if ((size_t)handle->slot_id >= vault->capacity) {
        return VOS_ROUTER_ERR_DENIED;
    }
    const vos_cred_vault_slot *slot = &vault->slots[handle->slot_id];
    if (slot->occupied == 0U || slot->generation == 0U
        || slot->generation != handle->generation) {
        return VOS_ROUTER_ERR_DENIED;
    }
    *out_bindings = slot->bindings;
    return VOS_ROUTER_OK;
}

vos_router_status vos_cred_delegate_handle(
    const vos_cred_policy *policy, vos_cred_vault *vault,
    const vos_cred_handle *parent_handle, const vos_cred_bindings *child_bindings,
    vos_cred_handle *out_child_handle)
{
    vos_cred_bindings parent_bindings;
    const vos_router_status st = vos_cred_resolve_sealed(vault, parent_handle, &parent_bindings);
    if (st != VOS_ROUTER_OK) {
        return st;
    }
    if (!vos_cred_delegates(policy, &parent_bindings, child_bindings)) {
        return VOS_ROUTER_ERR_DENIED;
    }
    return vos_cred_issue_handle(vault, child_bindings, out_child_handle);
}

vos_router_status vos_cred_use_handle(
    const vos_cred_policy *policy, const vos_cred_vault *vault,
    vos_cred_server *server, const vos_cred_handle *handle,
    const vos_cred_handle_request *req)
{
    if (req == NULL) {
        return VOS_ROUTER_ERR_INVALID;
    }
    if (req->kind == VOS_HANDLE_REQ_EXPORT_SECRET) {
        return VOS_ROUTER_ERR_DENIED;
    }
    if (req->kind != VOS_HANDLE_REQ_PROTOCOL_USE) {
        return VOS_ROUTER_ERR_INVALID;
    }
    vos_cred_bindings bindings;
    const vos_router_status st = vos_cred_resolve_sealed(vault, handle, &bindings);
    if (st != VOS_ROUTER_OK) {
        return st;
    }
    if (!vos_cred_authorize_and_charge(policy, &bindings, server, &req->protocol_req)) {
        return VOS_ROUTER_ERR_DENIED;
    }
    return VOS_ROUTER_OK;
}
