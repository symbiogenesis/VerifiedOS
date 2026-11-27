// SPDX-License-Identifier: Apache-2.0
/*
 * Original GC-free C17 group & elastic executive + general CSR restoration
 * (M4.4b-ii-a), authored against [ElasticDispatch.v](../../proofs/ElasticDispatch.v)
 * and [PartitionContext.v](../../proofs/PartitionContext.v).
 *
 * Additive consumer of [vos_kernel.h](vos_kernel.h). Introduces no new kernel
 * table or object class: EEVDF per-member and session-manager fields live inside
 * placed partition context records.
 */
#ifndef VOS_ELASTIC_EXEC_H
#define VOS_ELASTIC_EXEC_H 1

#include <stdint.h>

#include "vos_kernel.h"

#ifndef VOS_ELASTIC_MAX_MEMBERS
#define VOS_ELASTIC_MAX_MEMBERS 32u
#endif

#ifndef VOS_ELASTIC_MAX_CORES
#define VOS_ELASTIC_MAX_CORES 16u
#endif

#ifndef VOS_ELASTIC_MAX_GROUP
#define VOS_ELASTIC_MAX_GROUP 32u
#endif

enum vos_elastic_status {
  VOS_ELASTIC_OK = 0,
  VOS_ELASTIC_ERR_INVALID = 1,
  VOS_ELASTIC_ERR_NOT_PERMUTATION = 2,
  VOS_ELASTIC_ERR_NOT_BOUNDARY = 3,
  VOS_ELASTIC_ERR_INCOMPLETE_RESTORE = 4,
  VOS_ELASTIC_ERR_WRONG_CSR_DISPOSITION = 5,
  VOS_ELASTIC_ERR_MISSING_VMCLEAR = 6,
  VOS_ELASTIC_ERR_CROSS_LABEL = 7,
  VOS_ELASTIC_ERR_BAD_DECL = 8,
  VOS_ELASTIC_ERR_NOT_PLACED = 9,
  VOS_ELASTIC_ERR_BOUNDARY = 10,
  VOS_ELASTIC_ERR_NOT_COMPETING = 11,
  VOS_ELASTIC_ERR_CLOCK_HORIZON = 12
};

/* Exact rational arithmetic without floating point (c-language-profile.md). */
struct vos_rat {
  int64_t num;
  int64_t den; /* strictly positive */
};

struct vos_rat vos_rat_make(int64_t num, int64_t den);
struct vos_rat vos_rat_add(struct vos_rat a, struct vos_rat b);
struct vos_rat vos_rat_sub(struct vos_rat a, struct vos_rat b);
struct vos_rat vos_rat_mul(struct vos_rat a, struct vos_rat b);
struct vos_rat vos_rat_div(struct vos_rat a, struct vos_rat b);
struct vos_rat vos_rat_abs(struct vos_rat a);
int vos_rat_cmp(struct vos_rat a, struct vos_rat b);
int vos_rat_eq(struct vos_rat a, struct vos_rat b);

/* General CSR restoration & StaticSlotManifest (PartitionContext.v, ElasticDispatch.v S5). */
struct vos_static_slot_manifest {
  uint8_t vs_off;
  uint8_t xs_off;
};

struct vos_restore_receipt {
  uint32_t reg_written_mask;
  uint8_t csr_written[VOS_MAX_CSRS];
  uint8_t pending_written;
  uint8_t vmclear_executed;
};

enum vos_elastic_status vos_elastic_machine_validate(const struct vos_machine *m);
enum vos_elastic_status vos_elastic_verify_restore(const struct vos_machine *m,
                                                   const struct vos_context *succ,
                                                   const struct vos_context *pre,
                                                   const struct vos_context *post,
                                                   int expect_vmclear,
                                                   int expect_pending_swap,
                                                   const struct vos_restore_receipt *receipt);
enum vos_elastic_status vos_elastic_static_slot_switch(const struct vos_machine *m,
                                                       const struct vos_static_slot_manifest *ssm,
                                                       const struct vos_context *succ,
                                                       const struct vos_context *pre,
                                                       struct vos_context *post,
                                                       struct vos_restore_receipt *out_receipt);

/* R-11-023 slot-to-tenant permutation & R-11-024 atomic table swap at frame boundary. */
enum vos_elastic_status vos_frame_check_tenant_permutation(const struct vos_frame *base_frame,
                                                           const struct vos_frame *perm_frame);

struct vos_elastic_table_exec {
  struct vos_frame active_frame;
  struct vos_frame pending_frame;
  struct vos_exec exec;
  uint32_t rung_index;
  uint32_t pending_rung_index;
  uint8_t has_pending_swap;
  uint8_t initialized;
};

enum vos_elastic_status vos_elastic_table_init(struct vos_elastic_table_exec *te,
                                               const struct vos_frame *initial_frame,
                                               uint32_t initial_rung);
enum vos_elastic_status vos_elastic_table_stage_swap(struct vos_elastic_table_exec *te,
                                                     const struct vos_frame *next_frame,
                                                     uint32_t next_rung,
                                                     int require_permutation);
enum vos_elastic_status vos_elastic_table_advance(struct vos_elastic_table_exec *te,
                                                  uint8_t *out_swapped);

/* R-07-037b same-label group rotation without cross-label zeroization. */
struct vos_group_member {
  uint32_t partition_idx;
  uint32_t label;
  uint32_t app_id;
  struct vos_context ctx;
};

struct vos_same_label_group {
  uint32_t tenant;
  uint32_t label;
  uint32_t count;
  uint32_t cursor;
  struct vos_group_member members[VOS_ELASTIC_MAX_GROUP];
};

enum vos_elastic_status vos_group_validate(const struct vos_same_label_group *g);
enum vos_elastic_status vos_group_rotate_next(struct vos_same_label_group *g,
                                              const struct vos_machine *m,
                                              struct vos_context *post,
                                              struct vos_restore_receipt *out_receipt);

/* R-07-037g cooperative EEVDF elastic dispatch (ElasticDispatch.v). */
enum vos_session_req_kind {
  VOS_SREQ_NONE = 0,
  VOS_SREQ_LAUNCH = 1,
  VOS_SREQ_CLOSE = 2,
  VOS_SREQ_FOCUS = 3
};

struct vos_session_request {
  enum vos_session_req_kind kind;
  uint32_t member;
  uint32_t core;
  uint8_t has_focus;
};

struct vos_member_dispatch_fields {
  uint8_t active;
  uint8_t pending;
  uint32_t weight;
  uint32_t request;
  struct vos_rat eligible;
  struct vos_rat deadline;
  uint8_t switch_requested_pending;
};

struct vos_session_mgr_fields {
  struct vos_rat vtime;
  uint8_t has_focus;
  uint32_t focus;
  struct vos_session_request request_cell;
};

struct vos_placed_context {
  struct vos_context arch;
  struct vos_member_dispatch_fields dispatch;
  uint8_t is_session_mgr;
  struct vos_session_mgr_fields sm;
};

struct vos_elastic_decl {
  uint32_t count;
  uint32_t weights[VOS_ELASTIC_MAX_MEMBERS];
  uint32_t requests[VOS_ELASTIC_MAX_MEMBERS];
  uint32_t app_ids[VOS_ELASTIC_MAX_MEMBERS];
  uint32_t focus_weight;
  uint32_t focus_request;
  uint32_t call_interval;
  uint32_t yield_bound;
  uint32_t step_cost;
  uint32_t width_count;
  uint32_t widths[VOS_MAX_SLOTS];
  uint32_t core_count;
  uint32_t cores[VOS_ELASTIC_MAX_CORES];
  uint8_t dormant[VOS_ELASTIC_MAX_MEMBERS][VOS_ELASTIC_MAX_CORES];
  uint32_t vmclear_cost;
  struct vos_machine machine;
};

struct vos_elastic_domain_state {
  uint32_t sm_idx;
  int32_t current;
  struct vos_placed_context contexts[VOS_ELASTIC_MAX_MEMBERS];
};

enum vos_yield_outcome {
  VOS_YIELD_CONTINUE = 0,
  VOS_YIELD_SWITCH_REQUESTED = 1,
  VOS_YIELD_SWITCHED = 2
};

uint32_t vos_elastic_call_bound(const struct vos_elastic_decl *d);
uint32_t vos_elastic_boundary_need(const struct vos_elastic_decl *d);
int vos_elastic_boundary_ok(const struct vos_elastic_decl *d, uint32_t rem);
enum vos_elastic_status vos_elastic_decl_admits(const struct vos_elastic_decl *d);
enum vos_elastic_status vos_elastic_init_state(const struct vos_elastic_decl *d,
                                               struct vos_elastic_domain_state *st,
                                               uint32_t sm_idx,
                                               uint32_t initial_active_mask);
enum vos_elastic_status vos_elastic_enact_session_request(const struct vos_elastic_decl *d,
                                                          struct vos_elastic_domain_state *st);
int32_t vos_elastic_select(const struct vos_elastic_decl *d,
                           const struct vos_elastic_domain_state *st);
enum vos_yield_outcome vos_elastic_reply(const struct vos_elastic_decl *d,
                                         const struct vos_elastic_domain_state *st,
                                         uint32_t member, uint32_t used, uint32_t rem);
enum vos_elastic_status vos_elastic_context_step(const struct vos_elastic_decl *d,
                                                 const struct vos_elastic_domain_state *st,
                                                 uint32_t out_member, uint32_t in_member,
                                                 struct vos_context *out_post,
                                                 struct vos_restore_receipt *out_receipt);
enum vos_elastic_status vos_elastic_invoke_pc_yield(const struct vos_elastic_decl *d,
                                                    struct vos_elastic_domain_state *st,
                                                    int tentative, uint32_t used, uint32_t rem,
                                                    enum vos_yield_outcome *out_outcome,
                                                    int32_t *out_next,
                                                    struct vos_context *out_post,
                                                    struct vos_restore_receipt *out_receipt);
enum vos_elastic_status vos_elastic_join(const struct vos_elastic_decl *d,
                                         struct vos_elastic_domain_state *st, uint32_t member);
enum vos_elastic_status vos_elastic_published_leave(const struct vos_elastic_decl *d,
                                                    struct vos_elastic_domain_state *st,
                                                    uint32_t member);
enum vos_elastic_status vos_elastic_reweight(const struct vos_elastic_decl *old_d,
                                             const struct vos_elastic_decl *new_d,
                                             struct vos_elastic_domain_state *st,
                                             uint8_t has_focus, uint32_t focus_member);
struct vos_rat vos_elastic_accounting_lag(const struct vos_elastic_decl *d,
                                          const struct vos_elastic_domain_state *st,
                                          uint32_t member);
struct vos_rat vos_elastic_sum_competing_lag(const struct vos_elastic_decl *d,
                                             const struct vos_elastic_domain_state *st);
struct vos_rat vos_elastic_lag_bound(const struct vos_elastic_decl *d);

#endif
