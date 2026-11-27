// SPDX-License-Identifier: Apache-2.0
/*
 * Original GC-free C17 group & elastic executive + general CSR restoration
 * (M4.4b-ii-a), authored against [ElasticDispatch.v](../../proofs/ElasticDispatch.v)
 * and [PartitionContext.v](../../proofs/PartitionContext.v).
 */
#include "vos_elastic_exec.h"

static uint64_t u64_abs(int64_t x)
{
  if (x >= 0) {
    return (uint64_t)x;
  }
  return UINT64_C(0) - (uint64_t)x;
}

static uint64_t gcd_u64(uint64_t a, uint64_t b)
{
  for (uint32_t step = 0u; step < 128u && b != 0u; ++step) {
    const uint64_t t = a % b;
    a = b;
    b = t;
  }
  return a == 0u ? 1u : a;
}

static void mul_u64_u64(uint64_t a, uint64_t b, uint64_t *hi, uint64_t *lo)
{
  const uint64_t a0 = a & UINT64_C(0xffffffff);
  const uint64_t a1 = a >> 32u;
  const uint64_t b0 = b & UINT64_C(0xffffffff);
  const uint64_t b1 = b >> 32u;
  const uint64_t p00 = a0 * b0;
  const uint64_t p01 = a0 * b1;
  const uint64_t p10 = a1 * b0;
  const uint64_t p11 = a1 * b1;
  const uint64_t mid =
      (p00 >> 32u) + (p01 & UINT64_C(0xffffffff)) + (p10 & UINT64_C(0xffffffff));
  *lo = (p00 & UINT64_C(0xffffffff)) | (mid << 32u);
  *hi = p11 + (p01 >> 32u) + (p10 >> 32u) + (mid >> 32u);
}

static int cmp_u128(uint64_t hi1, uint64_t lo1, uint64_t hi2, uint64_t lo2)
{
  if (hi1 != hi2) {
    return hi1 < hi2 ? -1 : 1;
  }
  if (lo1 != lo2) {
    return lo1 < lo2 ? -1 : 1;
  }
  return 0;
}

struct vos_rat vos_rat_make(int64_t num, int64_t den)
{
  if (den == 0) {
    return (struct vos_rat){0, 1};
  }
  uint64_t anum = u64_abs(num);
  uint64_t aden = u64_abs(den);
  const int neg = (num < 0) != (den < 0);
  if (anum == 0u) {
    return (struct vos_rat){0, 1};
  }
  const uint64_t g = gcd_u64(anum, aden);
  anum /= g;
  aden /= g;
  const int64_t rden = (int64_t)aden;
  const int64_t rnum = neg ? -(int64_t)anum : (int64_t)anum;
  return (struct vos_rat){rnum, rden};
}

struct vos_rat vos_rat_add(struct vos_rat a, struct vos_rat b)
{
  const uint64_t da = (uint64_t)a.den;
  const uint64_t db = (uint64_t)b.den;
  const uint64_t g = gcd_u64(da, db);
  const int64_t fa = (int64_t)(db / g);
  const int64_t fb = (int64_t)(da / g);
  const int64_t num = a.num * fa + b.num * fb;
  const int64_t den = a.den * fa;
  return vos_rat_make(num, den);
}

struct vos_rat vos_rat_sub(struct vos_rat a, struct vos_rat b)
{
  return vos_rat_add(a, (struct vos_rat){-b.num, b.den});
}

struct vos_rat vos_rat_mul(struct vos_rat a, struct vos_rat b)
{
  const uint64_t g1 = gcd_u64(u64_abs(a.num), (uint64_t)b.den);
  const uint64_t g2 = gcd_u64(u64_abs(b.num), (uint64_t)a.den);
  const int64_t an = a.num / (int64_t)g1;
  const int64_t bd = b.den / (int64_t)g1;
  const int64_t bn = b.num / (int64_t)g2;
  const int64_t ad = a.den / (int64_t)g2;
  return vos_rat_make(an * bn, ad * bd);
}

struct vos_rat vos_rat_div(struct vos_rat a, struct vos_rat b)
{
  if (b.num == 0) {
    return (struct vos_rat){0, 1};
  }
  return vos_rat_mul(a, vos_rat_make(b.den, b.num));
}

struct vos_rat vos_rat_abs(struct vos_rat a)
{
  return a.num < 0 ? (struct vos_rat){-a.num, a.den} : a;
}

int vos_rat_cmp(struct vos_rat a, struct vos_rat b)
{
  if (a.num == b.num && a.den == b.den) {
    return 0;
  }
  if (a.num <= 0 && b.num > 0) {
    return -1;
  }
  if (a.num >= 0 && b.num < 0) {
    return 1;
  }
  if (a.num == 0 && b.num == 0) {
    return 0;
  }
  uint64_t hi1 = 0u, lo1 = 0u, hi2 = 0u, lo2 = 0u;
  mul_u64_u64(u64_abs(a.num), (uint64_t)b.den, &hi1, &lo1);
  mul_u64_u64(u64_abs(b.num), (uint64_t)a.den, &hi2, &lo2);
  const int mag = cmp_u128(hi1, lo1, hi2, lo2);
  return a.num < 0 ? -mag : mag;
}

int vos_rat_eq(struct vos_rat a, struct vos_rat b)
{
  return vos_rat_cmp(a, b) == 0;
}

/* ------------------------------------------------------------------------
 * General CSR restoration & StaticSlotManifest
 * ------------------------------------------------------------------------ */

enum vos_elastic_status vos_elastic_machine_validate(const struct vos_machine *m)
{
  if (m == 0 || vos_machine_validate(m) != VOS_OK) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  if (m->pending_swapped > 1u || m->rotation_swaps_pending > 1u) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  for (uint32_t i = 0u; i < m->csr_count; ++i) {
    if (m->roster[i].nameable > 1u || m->roster[i].zeroized > 1u) {
      return VOS_ELASTIC_ERR_INVALID;
    }
    for (uint32_t j = i + 1u; j < m->csr_count; ++j) {
      if (m->roster[i].csr == m->roster[j].csr) {
        return VOS_ELASTIC_ERR_INVALID;
      }
    }
  }
  return VOS_ELASTIC_OK;
}

static void record_full_restore(const struct vos_machine *m, const struct vos_context *succ,
                                const struct vos_context *pre, struct vos_context *post,
                                int perform_vmclear, int perform_pending_swap,
                                struct vos_restore_receipt *receipt)
{
  const struct vos_context succ_copy = *succ;
  const struct vos_context pre_copy = *pre;
  if (perform_vmclear) {
    vos_switch_image(m, &succ_copy, &pre_copy, post);
  } else {
    vos_rotation_image(m, &succ_copy, &pre_copy, post);
  }
  if (receipt != 0) {
    receipt->reg_written_mask = UINT32_MAX;
    receipt->vmclear_executed = perform_vmclear ? 1u : 0u;
    receipt->pending_written = (perform_vmclear || perform_pending_swap) ? 1u : 0u;
    for (uint32_t i = 0u; i < VOS_MAX_CSRS; ++i) {
      receipt->csr_written[i] = 0u;
    }
    for (uint32_t i = 0u; i < m->csr_count && i < VOS_MAX_CSRS; ++i) {
      if (m->roster[i].nameable && (!m->roster[i].zeroized || perform_vmclear)) {
        receipt->csr_written[i] = 1u;
      }
    }
  }
}

enum vos_elastic_status vos_elastic_verify_restore(const struct vos_machine *m,
                                                   const struct vos_context *succ,
                                                   const struct vos_context *pre,
                                                   const struct vos_context *post,
                                                   int expect_vmclear,
                                                   int expect_pending_swap,
                                                   const struct vos_restore_receipt *receipt)
{
  if (vos_elastic_machine_validate(m) != VOS_ELASTIC_OK ||
      succ == 0 || pre == 0 || post == 0 || receipt == 0) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  if (receipt->reg_written_mask != UINT32_MAX) {
    return VOS_ELASTIC_ERR_INCOMPLETE_RESTORE;
  }
  for (uint32_t r = 0u; r < VOS_REGISTER_COUNT; ++r) {
    if (post->reg[r].value != succ->reg[r].value || post->reg[r].tag != succ->reg[r].tag) {
      return VOS_ELASTIC_ERR_INCOMPLETE_RESTORE;
    }
  }
  if (expect_vmclear && !receipt->vmclear_executed) {
    return VOS_ELASTIC_ERR_MISSING_VMCLEAR;
  }
  for (uint32_t i = 0u; i < m->csr_count; ++i) {
    const struct vos_csr_row *row = &m->roster[i];
    if (row->nameable) {
      if (row->zeroized) {
        if (expect_vmclear) {
          if (!receipt->csr_written[i]) {
            return VOS_ELASTIC_ERR_INCOMPLETE_RESTORE;
          }
          if (post->csr[i] != 0u) {
            return VOS_ELASTIC_ERR_WRONG_CSR_DISPOSITION;
          }
        } else {
          if (post->csr[i] != pre->csr[i]) {
            return VOS_ELASTIC_ERR_WRONG_CSR_DISPOSITION;
          }
        }
      } else {
        if (!receipt->csr_written[i]) {
          return VOS_ELASTIC_ERR_INCOMPLETE_RESTORE;
        }
        if (post->csr[i] != succ->csr[i]) {
          return VOS_ELASTIC_ERR_WRONG_CSR_DISPOSITION;
        }
      }
    } else {
      if (post->csr[i] != pre->csr[i]) {
        return VOS_ELASTIC_ERR_WRONG_CSR_DISPOSITION;
      }
    }
  }
  if (expect_vmclear || expect_pending_swap) {
    if (!receipt->pending_written) {
      return VOS_ELASTIC_ERR_INCOMPLETE_RESTORE;
    }
    if (post->pending != vos_pending_written(m, succ)) {
      return VOS_ELASTIC_ERR_WRONG_CSR_DISPOSITION;
    }
  } else {
    if (post->pending != pre->pending) {
      return VOS_ELASTIC_ERR_WRONG_CSR_DISPOSITION;
    }
  }
  return VOS_ELASTIC_OK;
}

enum vos_elastic_status vos_elastic_static_slot_switch(const struct vos_machine *m,
                                                       const struct vos_static_slot_manifest *ssm,
                                                       const struct vos_context *succ,
                                                       const struct vos_context *pre,
                                                       struct vos_context *post,
                                                       struct vos_restore_receipt *out_receipt)
{
  if (vos_elastic_machine_validate(m) != VOS_ELASTIC_OK ||
      ssm == 0 || succ == 0 || pre == 0 || post == 0 || out_receipt == 0) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  const int perform_vmclear = !(ssm->vs_off && ssm->xs_off);
  record_full_restore(m, succ, pre, post, perform_vmclear, 1, out_receipt);
  return vos_elastic_verify_restore(m, succ, pre, post, perform_vmclear, 1, out_receipt);
}

/* ------------------------------------------------------------------------
 * R-11-023 permutation & R-11-024 atomic table swap at frame boundary
 * ------------------------------------------------------------------------ */

enum vos_elastic_status vos_frame_check_tenant_permutation(const struct vos_frame *base_frame,
                                                           const struct vos_frame *perm_frame)
{
  if (base_frame == 0 || perm_frame == 0) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  if (vos_frame_validate(base_frame) != VOS_OK || vos_frame_validate(perm_frame) != VOS_OK) {
    return VOS_ELASTIC_ERR_NOT_PERMUTATION;
  }
  if (base_frame->major_frame != perm_frame->major_frame ||
      base_frame->phase_offset != perm_frame->phase_offset ||
      base_frame->reserved_count != perm_frame->reserved_count ||
      base_frame->slot_count != perm_frame->slot_count) {
    return VOS_ELASTIC_ERR_NOT_PERMUTATION;
  }
  for (uint32_t i = 0u; i < base_frame->slot_count; ++i) {
    const struct vos_slot *a = &base_frame->slots[i];
    const struct vos_slot *b = &perm_frame->slots[i];
    if (a->width != b->width || a->offset != b->offset ||
        a->bound != b->bound || a->period != b->period) {
      return VOS_ELASTIC_ERR_NOT_PERMUTATION;
    }
    if (i < base_frame->reserved_count && a->tenant != b->tenant) {
      return VOS_ELASTIC_ERR_NOT_PERMUTATION;
    }
  }
  uint8_t matched[VOS_MAX_SLOTS] = {0};
  for (uint32_t i = base_frame->reserved_count; i < base_frame->slot_count; ++i) {
    const uint32_t t = base_frame->slots[i].tenant;
    int found = 0;
    for (uint32_t j = perm_frame->reserved_count; j < perm_frame->slot_count; ++j) {
      if (!matched[j] && perm_frame->slots[j].tenant == t) {
        matched[j] = 1u;
        found = 1;
        break;
      }
    }
    if (!found) {
      return VOS_ELASTIC_ERR_NOT_PERMUTATION;
    }
  }
  return VOS_ELASTIC_OK;
}

enum vos_elastic_status vos_elastic_table_init(struct vos_elastic_table_exec *te,
                                               const struct vos_frame *initial_frame,
                                               uint32_t initial_rung)
{
  if (te == 0 || initial_frame == 0 || vos_frame_validate(initial_frame) != VOS_OK) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  te->active_frame = *initial_frame;
  te->pending_frame = (struct vos_frame){0};
  vos_exec_start(&te->exec);
  te->rung_index = initial_rung;
  te->pending_rung_index = initial_rung;
  te->has_pending_swap = 0u;
  te->initialized = 1u;
  return VOS_ELASTIC_OK;
}

enum vos_elastic_status vos_elastic_table_stage_swap(struct vos_elastic_table_exec *te,
                                                     const struct vos_frame *next_frame,
                                                     uint32_t next_rung,
                                                     int require_permutation)
{
  if (te == 0 || !te->initialized || next_frame == 0) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  if (vos_frame_validate(next_frame) != VOS_OK) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  if (require_permutation &&
      vos_frame_check_tenant_permutation(&te->active_frame, next_frame) != VOS_ELASTIC_OK) {
    return VOS_ELASTIC_ERR_NOT_PERMUTATION;
  }
  te->pending_frame = *next_frame;
  te->pending_rung_index = next_rung;
  te->has_pending_swap = 1u;
  return VOS_ELASTIC_OK;
}

enum vos_elastic_status vos_elastic_table_advance(struct vos_elastic_table_exec *te,
                                                  uint8_t *out_swapped)
{
  if (te == 0 || !te->initialized || out_swapped == 0) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  *out_swapped = 0u;
  if (!vos_exec_advance(&te->active_frame, &te->exec)) {
    return VOS_ELASTIC_ERR_CLOCK_HORIZON;
  }
  if (te->exec.cursor == 0u && te->has_pending_swap) {
    te->active_frame = te->pending_frame;
    te->rung_index = te->pending_rung_index;
    te->has_pending_swap = 0u;
    *out_swapped = 1u;
  }
  return VOS_ELASTIC_OK;
}

/* ------------------------------------------------------------------------
 * R-07-037b same-label group rotation without cross-label zeroization
 * ------------------------------------------------------------------------ */

enum vos_elastic_status vos_group_validate(const struct vos_same_label_group *g)
{
  if (g == 0 || g->count == 0u || g->count > VOS_ELASTIC_MAX_GROUP ||
      g->cursor >= g->count) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  for (uint32_t i = 0u; i < g->count; ++i) {
    if (g->members[i].label != g->label) {
      return VOS_ELASTIC_ERR_CROSS_LABEL;
    }
  }
  return VOS_ELASTIC_OK;
}

enum vos_elastic_status vos_group_rotate_next(struct vos_same_label_group *g,
                                              const struct vos_machine *m,
                                              struct vos_context *post,
                                              struct vos_restore_receipt *out_receipt)
{
  if (vos_group_validate(g) != VOS_ELASTIC_OK ||
      vos_elastic_machine_validate(m) != VOS_ELASTIC_OK ||
      post == 0 || out_receipt == 0) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  const uint32_t prev_idx = g->cursor;
  const uint32_t next_idx = (g->cursor + 1u) % g->count;
  const struct vos_context *pre = &g->members[prev_idx].ctx;
  const struct vos_context *succ = &g->members[next_idx].ctx;
  record_full_restore(m, succ, pre, post, 0, m->rotation_swaps_pending, out_receipt);
  const enum vos_elastic_status vst = vos_elastic_verify_restore(
      m, succ, pre, post, 0, m->rotation_swaps_pending, out_receipt);
  if (vst != VOS_ELASTIC_OK) {
    return vst;
  }
  g->cursor = next_idx;
  return VOS_ELASTIC_OK;
}

/* ------------------------------------------------------------------------
 * R-07-037g cooperative EEVDF elastic dispatch (ElasticDispatch.v)
 * ------------------------------------------------------------------------ */

static uint32_t is_focus(const struct vos_elastic_domain_state *st, uint32_t i)
{
  const struct vos_session_mgr_fields *sm = &st->contexts[st->sm_idx].sm;
  return (sm->has_focus && sm->focus == i) ? 1u : 0u;
}

static uint32_t eff_weight(const struct vos_elastic_decl *d,
                           const struct vos_elastic_domain_state *st, uint32_t i)
{
  return is_focus(st, i) ? d->focus_weight : d->weights[i];
}

static uint32_t eff_request(const struct vos_elastic_decl *d,
                            const struct vos_elastic_domain_state *st, uint32_t i)
{
  return is_focus(st, i) ? d->focus_request : d->requests[i];
}

static uint32_t eff_coop_request(const struct vos_elastic_decl *d,
                                 const struct vos_elastic_domain_state *st, uint32_t i)
{
  return eff_request(d, st, i) + vos_elastic_call_bound(d);
}

static struct vos_rat coop_deadline_at(const struct vos_elastic_decl *d,
                                       const struct vos_elastic_domain_state *st,
                                       uint32_t i, struct vos_rat ve)
{
  const uint32_t req = eff_coop_request(d, st, i);
  const uint32_t w = eff_weight(d, st, i);
  return vos_rat_add(ve, vos_rat_make((int64_t)req, (int64_t)w));
}

static int competing(const struct vos_elastic_decl *d,
                     const struct vos_elastic_domain_state *st, uint32_t i)
{
  return i < d->count && st->contexts[i].dispatch.active && st->contexts[i].dispatch.pending;
}

static uint32_t total_weight(const struct vos_elastic_decl *d,
                             const struct vos_elastic_domain_state *st)
{
  uint32_t total = 0u;
  for (uint32_t j = 0u; j < d->count; ++j) {
    if (competing(d, st, j)) {
      total += eff_weight(d, st, j);
    }
  }
  return total;
}

static int eligible_at(const struct vos_elastic_decl *d,
                       const struct vos_elastic_domain_state *st,
                       uint32_t i, struct vos_rat vtime)
{
  return competing(d, st, i) && vos_rat_cmp(st->contexts[i].dispatch.eligible, vtime) <= 0;
}

static int preferred(const struct vos_elastic_domain_state *st, uint32_t i, uint32_t j)
{
  const int c = vos_rat_cmp(st->contexts[i].dispatch.deadline, st->contexts[j].dispatch.deadline);
  if (c < 0) {
    return 1;
  }
  if (c == 0 && i <= j) {
    return 1;
  }
  return 0;
}

static int launch_placed(const struct vos_elastic_decl *d, uint32_t member, uint32_t core)
{
  if (member >= d->count) {
    return 0;
  }
  for (uint32_t c = 0u; c < d->core_count; ++c) {
    if (d->cores[c] == core && d->dormant[member][c]) {
      return 1;
    }
  }
  return 0;
}

uint32_t vos_elastic_call_bound(const struct vos_elastic_decl *d)
{
  return d->call_interval + d->yield_bound;
}

uint32_t vos_elastic_boundary_need(const struct vos_elastic_decl *d)
{
  return vos_elastic_call_bound(d) + d->yield_bound + d->step_cost;
}

int vos_elastic_boundary_ok(const struct vos_elastic_decl *d, uint32_t rem)
{
  return vos_elastic_boundary_need(d) <= rem;
}

enum vos_elastic_status vos_elastic_decl_admits(const struct vos_elastic_decl *d)
{
  if (d == 0 || d->count == 0u || d->count > VOS_ELASTIC_MAX_MEMBERS ||
      d->focus_weight == 0u || d->focus_request == 0u ||
      d->width_count == 0u || d->width_count > VOS_MAX_SLOTS ||
      d->core_count == 0u || d->core_count > VOS_ELASTIC_MAX_CORES) {
    return VOS_ELASTIC_ERR_BAD_DECL;
  }
  if (vos_elastic_machine_validate(&d->machine) != VOS_ELASTIC_OK) {
    return VOS_ELASTIC_ERR_BAD_DECL;
  }
  if (d->call_interval > UINT32_MAX - d->yield_bound) {
    return VOS_ELASTIC_ERR_BAD_DECL;
  }
  const uint32_t cb = vos_elastic_call_bound(d);
  if (cb > UINT32_MAX - d->yield_bound || (cb + d->yield_bound) > UINT32_MAX - d->step_cost) {
    return VOS_ELASTIC_ERR_BAD_DECL;
  }
  const uint32_t need = vos_elastic_boundary_need(d);
  if (d->step_cost < d->vmclear_cost) {
    return VOS_ELASTIC_ERR_BAD_DECL;
  }
  for (uint32_t i = 0u; i < d->count; ++i) {
    if (d->weights[i] == 0u || d->requests[i] == 0u) {
      return VOS_ELASTIC_ERR_BAD_DECL;
    }
  }
  for (uint32_t i = 0u; i < d->width_count; ++i) {
    if (d->widths[i] < need) {
      return VOS_ELASTIC_ERR_BAD_DECL;
    }
  }
  return VOS_ELASTIC_OK;
}

enum vos_elastic_status vos_elastic_init_state(const struct vos_elastic_decl *d,
                                               struct vos_elastic_domain_state *st,
                                               uint32_t sm_idx,
                                               uint32_t initial_active_mask)
{
  if (vos_elastic_decl_admits(d) != VOS_ELASTIC_OK || st == 0 || sm_idx >= d->count) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  *st = (struct vos_elastic_domain_state){0};
  st->sm_idx = sm_idx;
  st->current = -1;
  st->contexts[sm_idx].is_session_mgr = 1u;
  st->contexts[sm_idx].sm.vtime = vos_rat_make(0, 1);
  st->contexts[sm_idx].sm.has_focus = 0u;
  st->contexts[sm_idx].sm.focus = 0u;
  st->contexts[sm_idx].sm.request_cell.kind = VOS_SREQ_NONE;
  for (uint32_t i = 0u; i < d->count; ++i) {
    const uint8_t act = ((initial_active_mask & (UINT32_C(1) << i)) != 0u) ? 1u : 0u;
    st->contexts[i].dispatch.active = act;
    st->contexts[i].dispatch.pending = act;
    st->contexts[i].dispatch.weight = d->weights[i];
    st->contexts[i].dispatch.request = d->requests[i];
    st->contexts[i].dispatch.eligible = vos_rat_make(0, 1);
    st->contexts[i].dispatch.deadline = coop_deadline_at(d, st, i, vos_rat_make(0, 1));
    st->contexts[i].dispatch.switch_requested_pending = 0u;
  }
  return VOS_ELASTIC_OK;
}

enum vos_elastic_status vos_elastic_enact_session_request(const struct vos_elastic_decl *d,
                                                          struct vos_elastic_domain_state *st)
{
  if (d == 0 || st == 0 || st->sm_idx >= d->count) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  struct vos_session_mgr_fields *sm = &st->contexts[st->sm_idx].sm;
  const struct vos_session_request req = sm->request_cell;
  sm->request_cell.kind = VOS_SREQ_NONE;
  if (req.kind == VOS_SREQ_NONE) {
    return VOS_ELASTIC_OK;
  }
  if (req.kind == VOS_SREQ_LAUNCH) {
    if (!launch_placed(d, req.member, req.core)) {
      return VOS_ELASTIC_ERR_NOT_PLACED;
    }
    struct vos_member_dispatch_fields *df = &st->contexts[req.member].dispatch;
    df->active = 1u;
    df->pending = 1u;
    df->weight = d->weights[req.member];
    df->request = d->requests[req.member];
    df->eligible = sm->vtime;
    df->deadline = coop_deadline_at(d, st, req.member, sm->vtime);
    df->switch_requested_pending = 0u;
    return VOS_ELASTIC_OK;
  }
  if (req.kind == VOS_SREQ_CLOSE) {
    if (req.member >= d->count) {
      return VOS_ELASTIC_ERR_INVALID;
    }
    struct vos_member_dispatch_fields *df = &st->contexts[req.member].dispatch;
    df->active = 0u;
    df->pending = 0u;
    df->switch_requested_pending = 0u;
    return VOS_ELASTIC_OK;
  }
  if (req.kind == VOS_SREQ_FOCUS) {
    if (req.has_focus && req.member >= d->count) {
      return VOS_ELASTIC_ERR_INVALID;
    }
    sm->has_focus = req.has_focus ? 1u : 0u;
    sm->focus = req.has_focus ? req.member : 0u;
    return VOS_ELASTIC_OK;
  }
  return VOS_ELASTIC_ERR_INVALID;
}

int32_t vos_elastic_select(const struct vos_elastic_decl *d,
                           const struct vos_elastic_domain_state *st)
{
  if (d == 0 || st == 0 || st->sm_idx >= d->count) {
    return -1;
  }
  const struct vos_rat vtime = st->contexts[st->sm_idx].sm.vtime;
  int32_t best = -1;
  for (uint32_t j = 0u; j < d->count; ++j) {
    if (eligible_at(d, st, j, vtime)) {
      if (best < 0 || !preferred(st, (uint32_t)best, j)) {
        best = (int32_t)j;
      }
    }
  }
  return best;
}

enum vos_yield_outcome vos_elastic_reply(const struct vos_elastic_decl *d,
                                         const struct vos_elastic_domain_state *st,
                                         uint32_t member, uint32_t used, uint32_t rem)
{
  if (d == 0 || st == 0 || member >= d->count || !vos_elastic_boundary_ok(d, rem)) {
    return VOS_YIELD_SWITCH_REQUESTED;
  }
  if (used >= eff_request(d, st, member)) {
    return VOS_YIELD_SWITCH_REQUESTED;
  }
  const uint32_t tw = total_weight(d, st);
  struct vos_rat adv_vtime = st->contexts[st->sm_idx].sm.vtime;
  if (tw > 0u) {
    adv_vtime = vos_rat_add(adv_vtime, vos_rat_make((int64_t)used, (int64_t)tw));
  }
  const struct vos_rat my_dl = st->contexts[member].dispatch.deadline;
  for (uint32_t j = 0u; j < d->count; ++j) {
    if (j != member && eligible_at(d, st, j, adv_vtime) &&
        vos_rat_cmp(st->contexts[j].dispatch.deadline, my_dl) < 0) {
      return VOS_YIELD_SWITCH_REQUESTED;
    }
  }
  return VOS_YIELD_CONTINUE;
}

enum vos_elastic_status vos_elastic_context_step(const struct vos_elastic_decl *d,
                                                 const struct vos_elastic_domain_state *st,
                                                 uint32_t out_member, uint32_t in_member,
                                                 struct vos_context *out_post,
                                                 struct vos_restore_receipt *out_receipt)
{
  if (d == 0 || st == 0 || out_member >= d->count || in_member >= d->count ||
      out_post == 0 || out_receipt == 0) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  const int cross_app = d->app_ids[out_member] != d->app_ids[in_member];
  const struct vos_context *pre = &st->contexts[out_member].arch;
  const struct vos_context *succ = &st->contexts[in_member].arch;
  const int swap_pending = d->machine.rotation_swaps_pending != 0u;
  record_full_restore(&d->machine, succ, pre, out_post, cross_app, swap_pending, out_receipt);
  return vos_elastic_verify_restore(&d->machine, succ, pre, out_post, cross_app,
                                    swap_pending, out_receipt);
}

enum vos_elastic_status vos_elastic_invoke_pc_yield(const struct vos_elastic_decl *d,
                                                    struct vos_elastic_domain_state *st,
                                                    int tentative, uint32_t used, uint32_t rem,
                                                    enum vos_yield_outcome *out_outcome,
                                                    int32_t *out_next,
                                                    struct vos_context *out_post,
                                                    struct vos_restore_receipt *out_receipt)
{
  if (d == 0 || st == 0 || st->sm_idx >= d->count ||
      out_outcome == 0 || out_next == 0) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  if (st->current < 0) {
    const int32_t next = vos_elastic_select(d, st);
    st->current = next;
    *out_outcome = VOS_YIELD_SWITCHED;
    *out_next = next;
    return VOS_ELASTIC_OK;
  }
  const uint32_t cur = (uint32_t)st->current;
  if (cur >= d->count) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  struct vos_member_dispatch_fields *df = &st->contexts[cur].dispatch;
  if (!tentative || df->switch_requested_pending) {
    if (!vos_elastic_boundary_ok(d, rem)) {
      return VOS_ELASTIC_ERR_BOUNDARY;
    }
    const uint32_t tw = total_weight(d, st);
    struct vos_session_mgr_fields *sm = &st->contexts[st->sm_idx].sm;
    if (tw > 0u) {
      sm->vtime = vos_rat_add(sm->vtime, vos_rat_make((int64_t)used, (int64_t)tw));
    }
    const uint32_t w_cur = eff_weight(d, st, cur);
    df->eligible = vos_rat_add(df->eligible, vos_rat_make((int64_t)used, (int64_t)w_cur));
    df->deadline = coop_deadline_at(d, st, cur, df->eligible);
    df->switch_requested_pending = 0u;
    const int32_t next = vos_elastic_select(d, st);
    st->current = next;
    *out_outcome = VOS_YIELD_SWITCHED;
    *out_next = next;
    if (next >= 0 && (uint32_t)next != cur && out_post != 0 && out_receipt != 0) {
      return vos_elastic_context_step(d, st, cur, (uint32_t)next, out_post, out_receipt);
    }
    return VOS_ELASTIC_OK;
  }
  const enum vos_yield_outcome rep = vos_elastic_reply(d, st, cur, used, rem);
  if (rep == VOS_YIELD_CONTINUE) {
    *out_outcome = VOS_YIELD_CONTINUE;
    *out_next = (int32_t)cur;
    return VOS_ELASTIC_OK;
  }
  df->switch_requested_pending = 1u;
  *out_outcome = VOS_YIELD_SWITCH_REQUESTED;
  *out_next = (int32_t)cur;
  return VOS_ELASTIC_OK;
}

enum vos_elastic_status vos_elastic_join(const struct vos_elastic_decl *d,
                                         struct vos_elastic_domain_state *st, uint32_t member)
{
  if (d == 0 || st == 0 || member >= d->count || competing(d, st, member)) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  const struct vos_rat vtime = st->contexts[st->sm_idx].sm.vtime;
  struct vos_member_dispatch_fields *df = &st->contexts[member].dispatch;
  df->active = 1u;
  df->pending = 1u;
  df->eligible = vtime;
  df->deadline = coop_deadline_at(d, st, member, vtime);
  df->switch_requested_pending = 0u;
  return VOS_ELASTIC_OK;
}

enum vos_elastic_status vos_elastic_published_leave(const struct vos_elastic_decl *d,
                                                    struct vos_elastic_domain_state *st,
                                                    uint32_t member)
{
  if (d == 0 || st == 0 || member >= d->count || !competing(d, st, member)) {
    return VOS_ELASTIC_ERR_NOT_COMPETING;
  }
  const struct vos_rat lag_j = vos_elastic_accounting_lag(d, st, member);
  st->contexts[member].dispatch.pending = 0u;
  st->contexts[member].dispatch.switch_requested_pending = 0u;
  const uint32_t w_rem = total_weight(d, st);
  if (w_rem > 0u) {
    struct vos_session_mgr_fields *sm = &st->contexts[st->sm_idx].sm;
    sm->vtime = vos_rat_add(sm->vtime, vos_rat_div(lag_j, vos_rat_make((int64_t)w_rem, 1)));
  }
  return VOS_ELASTIC_OK;
}

enum vos_elastic_status vos_elastic_reweight(const struct vos_elastic_decl *old_d,
                                             const struct vos_elastic_decl *new_d,
                                             struct vos_elastic_domain_state *st,
                                             uint8_t has_focus, uint32_t focus_member)
{
  if (old_d == 0 || new_d == 0 || st == 0 || old_d->count != new_d->count ||
      vos_elastic_decl_admits(new_d) != VOS_ELASTIC_OK) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  if (has_focus && focus_member >= new_d->count) {
    return VOS_ELASTIC_ERR_INVALID;
  }
  struct vos_rat lags[VOS_ELASTIC_MAX_MEMBERS];
  for (uint32_t j = 0u; j < old_d->count; ++j) {
    lags[j] = vos_elastic_accounting_lag(old_d, st, j);
  }
  struct vos_session_mgr_fields *sm = &st->contexts[st->sm_idx].sm;
  sm->has_focus = has_focus ? 1u : 0u;
  sm->focus = has_focus ? focus_member : 0u;
  for (uint32_t j = 0u; j < new_d->count; ++j) {
    const uint32_t w_new = eff_weight(new_d, st, j);
    const struct vos_rat ve_new =
        vos_rat_sub(sm->vtime, vos_rat_div(lags[j], vos_rat_make((int64_t)w_new, 1)));
    st->contexts[j].dispatch.weight = new_d->weights[j];
    st->contexts[j].dispatch.request = new_d->requests[j];
    st->contexts[j].dispatch.eligible = ve_new;
    st->contexts[j].dispatch.deadline = coop_deadline_at(new_d, st, j, ve_new);
  }
  return VOS_ELASTIC_OK;
}

struct vos_rat vos_elastic_accounting_lag(const struct vos_elastic_decl *d,
                                          const struct vos_elastic_domain_state *st,
                                          uint32_t member)
{
  if (d == 0 || st == 0 || member >= d->count) {
    return vos_rat_make(0, 1);
  }
  const struct vos_rat w = vos_rat_make((int64_t)eff_weight(d, st, member), 1);
  const struct vos_rat diff =
      vos_rat_sub(st->contexts[st->sm_idx].sm.vtime, st->contexts[member].dispatch.eligible);
  return vos_rat_mul(w, diff);
}

struct vos_rat vos_elastic_sum_competing_lag(const struct vos_elastic_decl *d,
                                             const struct vos_elastic_domain_state *st)
{
  struct vos_rat sum = vos_rat_make(0, 1);
  if (d == 0 || st == 0) {
    return sum;
  }
  for (uint32_t j = 0u; j < d->count; ++j) {
    if (competing(d, st, j)) {
      sum = vos_rat_add(sum, vos_elastic_accounting_lag(d, st, j));
    }
  }
  return sum;
}

struct vos_rat vos_elastic_lag_bound(const struct vos_elastic_decl *d)
{
  if (d == 0) {
    return vos_rat_make(0, 1);
  }
  uint32_t max_req = 0u;
  for (uint32_t j = 0u; j < d->count; ++j) {
    if (d->requests[j] > max_req) {
      max_req = d->requests[j];
    }
  }
  return vos_rat_make((int64_t)(max_req + vos_elastic_call_bound(d)), 1);
}
