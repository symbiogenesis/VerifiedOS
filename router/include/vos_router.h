// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_ROUTER_H
#define VOS_ROUTER_H

#include <stddef.h>
#include <stdint.h>

/* Contained object router and sealed credential handle boundary.
 * Mirrors `proofs/ObjectRouter.v` and `proofs/CredentialHandles.v`:
 * - GC-free ISO C17 with explicit caller-owned bounded buffers.
 * - Logical capability/namespace records only; not a hardware CHERI sentry. */

typedef enum {
    VOS_ROUTER_OK = 0,
    VOS_ROUTER_ERR_INVALID = 1,
    VOS_ROUTER_ERR_TAGGED_WRITE = 2,
    VOS_ROUTER_ERR_CROSS_DOMAIN = 3,
    VOS_ROUTER_ERR_OUT_OF_EXTENT = 4,
    VOS_ROUTER_ERR_NO_EXTENT = 5,
    VOS_ROUTER_ERR_DENIED = 6,
    VOS_ROUTER_ERR_STALE_EPOCH = 7,
    VOS_ROUTER_ERR_CAPACITY = 8
} vos_router_status;

/* --- Private namespaces and live-query delta streams (ObjectRouter.v) --- */

typedef struct {
    uint64_t bits;
    uint8_t tag;
} vos_router_word;

typedef struct {
    uint32_t address;
    vos_router_word word;
} vos_router_write_record;

typedef struct {
    uint32_t base;
    uint32_t span;
    uint32_t domain;
    uint32_t space;
} vos_router_extent;

typedef struct {
    uint32_t domain;
    uint32_t space;
    uint32_t rights;
} vos_router_ns_cap;

typedef struct {
    uint32_t domain;
    uint32_t space;
    uint64_t object;
    uint32_t rights;
} vos_router_obj_cap;

typedef struct {
    uint32_t domain;
    uint32_t space;
    uint64_t object;
    uint32_t rights;
} vos_router_ask;

typedef struct {
    uint32_t id;
    vos_router_ns_cap cap;
    uint32_t epoch;
    uint8_t active;
} vos_router_session;

typedef enum {
    VOS_ROUTER_REFUSE_TYPED = 0,
    VOS_ROUTER_ANSWER_EMPTY = 1,
    VOS_ROUTER_GRANT_TRUNCATED = 2
} vos_router_discipline;

typedef enum {
    VOS_ROUTER_ANSWER_GRANTED = 0,
    VOS_ROUTER_ANSWER_EMPTY_RESULT = 1,
    VOS_ROUTER_ANSWER_REFUSED = 2
} vos_router_answer_kind;

typedef struct {
    vos_router_answer_kind kind;
    vos_router_obj_cap obj_cap;
} vos_router_answer;

typedef struct {
    const vos_router_extent *extents;
    size_t extent_count;
    uint32_t queue_bound;
    uint32_t result_bound;
    uint32_t ring_capacity;
    uint32_t live_epoch;
    vos_router_discipline discipline;
} vos_router_composition;

typedef enum {
    VOS_DELTA_ADDED = 0,
    VOS_DELTA_REMOVED = 1,
    VOS_DELTA_RESCAN = 2
} vos_delta_kind;

typedef struct {
    vos_delta_kind kind;
    uint64_t object_id;
} vos_delta;

typedef enum {
    VOS_SUB_LIVE = 0,
    VOS_SUB_RESCAN_REQUIRED = 1
} vos_sub_phase;

typedef enum {
    VOS_SUBMIT_ENQUEUED = 0,
    VOS_SUBMIT_WOULD_BLOCK = 1
} vos_submit_result;

typedef struct {
    uint32_t id;
    uint8_t committed;
} vos_router_txn;

typedef struct {
    uint32_t id;
    uint32_t domain;
    uint32_t space;
    uint8_t active;
    vos_sub_phase phase;
    vos_delta *queue;
    size_t queue_cap;
    size_t count;
} vos_router_sub;

int vos_router_extent_inside(const vos_router_extent *ext, uint32_t addr);
int vos_router_extents_overlap(const vos_router_extent *a, const vos_router_extent *b);
int vos_router_composition_valid(const vos_router_composition *comp);
const vos_router_extent *vos_router_find_extent(
    const vos_router_composition *comp, uint32_t domain, uint32_t space);

vos_router_status vos_router_validate_write(
    const vos_router_composition *comp, uint32_t domain, uint32_t space,
    const vos_router_write_record *records, size_t count);

vos_router_status vos_router_stage_index_key(
    const vos_router_composition *comp, uint32_t domain, uint32_t space,
    uint32_t slot, const vos_router_word *words, size_t word_count,
    vos_router_write_record *out_records, size_t out_cap);

int vos_router_cap_derivable(const vos_router_ns_cap *ns, const vos_router_obj_cap *obj);
const vos_router_session *vos_router_live_session(
    const vos_router_composition *comp, const vos_router_session *sessions,
    size_t session_count, uint32_t sid);

vos_router_answer vos_router_route(
    const vos_router_composition *comp, const vos_router_session *sessions,
    size_t session_count, uint32_t sid, const vos_router_ask *ask);

vos_router_status vos_router_deliver_results(
    const vos_router_composition *comp, const vos_router_session *sessions,
    size_t session_count, uint32_t sid, const vos_router_obj_cap *candidates,
    size_t candidate_count, vos_router_obj_cap *out_results, size_t out_cap,
    size_t *out_count);

vos_router_txn vos_router_commit_txn(
    const vos_router_sub *subs, size_t sub_count,
    vos_submit_result ring_status, vos_router_txn txn);

vos_router_status vos_router_publish_deltas(
    const vos_router_composition *comp, const vos_router_txn *txn,
    vos_router_sub *sub, const vos_delta *deltas, size_t delta_count);

void vos_router_reboot_subs(vos_router_sub *subs, size_t sub_count);

vos_router_status vos_router_establish_sub(
    const vos_router_composition *comp, vos_router_sub *sub,
    uint32_t id, uint32_t domain, uint32_t space,
    vos_delta *queue_buf, size_t queue_cap);

/* --- Sealed 7-binding credential handles (CredentialHandles.v) --- */

typedef struct {
    uint32_t role;
    uint32_t principal;
    uint64_t scope_mask;
    uint64_t op_mask;
    uint64_t transcript;
    uint32_t use_ceiling;
    uint64_t expiry;
    uint32_t account_id;
} vos_cred_bindings;

typedef struct {
    uint32_t role;
    uint32_t principal;
    uint32_t scope_bit;
    uint32_t op_bit;
    uint64_t transcript;
    const uint8_t *bytes;
    size_t byte_len;
} vos_cred_request;

typedef struct {
    uint32_t role_count;
    uint32_t principal_count;
    uint32_t scope_count;
    uint32_t operation_count;
    uint64_t transcript_count;
    uint32_t (*request_limit)(uint32_t role, uint32_t op, void *ctx);
    int (*protocol_operation)(uint32_t role, uint32_t op, void *ctx);
    int (*needs_approval)(uint32_t role, uint32_t op, void *ctx);
    void *policy_ctx;
} vos_cred_policy;

typedef struct {
    uint32_t *account_used;
    size_t account_count;
    uint64_t server_now;
    int (*consent_allows)(const vos_cred_bindings *cred, const vos_cred_request *req,
                          uint32_t current_used, void *ctx);
    void *consent_ctx;
} vos_cred_server;

typedef enum {
    VOS_HANDLE_RAW = 0,
    VOS_HANDLE_SEALED = 1
} vos_handle_kind;

typedef struct {
    vos_handle_kind kind;
    uint32_t slot_id;
    uint32_t generation;
} vos_cred_handle;

typedef struct {
    uint8_t occupied;
    uint32_t generation;
    vos_cred_bindings bindings;
} vos_cred_vault_slot;

typedef struct {
    vos_cred_vault_slot *slots;
    size_t capacity;
    uint32_t next_gen;
} vos_cred_vault;

typedef enum {
    VOS_HANDLE_REQ_PROTOCOL_USE = 0,
    VOS_HANDLE_REQ_EXPORT_SECRET = 1
} vos_cred_handle_req_kind;

typedef struct {
    vos_cred_handle_req_kind kind;
    vos_cred_request protocol_req;
} vos_cred_handle_request;

int vos_cred_delegates(
    const vos_cred_policy *policy,
    const vos_cred_bindings *parent,
    const vos_cred_bindings *child);

int vos_cred_authorize_and_charge(
    const vos_cred_policy *policy,
    const vos_cred_bindings *cred,
    vos_cred_server *server,
    const vos_cred_request *req);

void vos_cred_vault_init(vos_cred_vault *vault, vos_cred_vault_slot *slots, size_t capacity);

vos_router_status vos_cred_issue_handle(
    vos_cred_vault *vault, const vos_cred_bindings *bindings,
    vos_cred_handle *out_handle);

vos_router_status vos_cred_delegate_handle(
    const vos_cred_policy *policy, vos_cred_vault *vault,
    const vos_cred_handle *parent_handle, const vos_cred_bindings *child_bindings,
    vos_cred_handle *out_child_handle);

vos_router_status vos_cred_resolve_sealed(
    const vos_cred_vault *vault, const vos_cred_handle *handle,
    vos_cred_bindings *out_bindings);

vos_router_status vos_cred_use_handle(
    const vos_cred_policy *policy, const vos_cred_vault *vault,
    vos_cred_server *server, const vos_cred_handle *handle,
    const vos_cred_handle_request *req);

#endif
