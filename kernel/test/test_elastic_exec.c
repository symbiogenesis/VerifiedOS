// SPDX-License-Identifier: Apache-2.0
#include <stdio.h>
#include <string.h>

#include "vos_elastic_exec.h"

static uint32_t g_checks = 0u;

#define CHECK_MSG(cond, msg)                                                           \
  do {                                                                                 \
    ++g_checks;                                                                        \
    if (!(cond)) {                                                                     \
      fprintf(stderr, "FAIL elastic_exec check %u line %d: %s\n", g_checks, __LINE__,  \
              (msg));                                                                  \
      return 1;                                                                        \
    }                                                                                  \
  } while (0)

static struct vos_machine make_test_machine(void)
{
  struct vos_machine m = {0};
  m.csr_count = 4u;
  m.roster[0] = (struct vos_csr_row){.csr = 0x100u, .nameable = 1u, .zeroized = 0u};
  m.roster[1] = (struct vos_csr_row){.csr = 0x101u, .nameable = 1u, .zeroized = 1u};
  m.roster[2] = (struct vos_csr_row){.csr = 0x102u, .nameable = 0u, .zeroized = 0u};
  m.roster[3] = (struct vos_csr_row){.csr = 0x103u, .nameable = 1u, .zeroized = 0u};
  m.pending_swapped = 1u;
  m.rotation_swaps_pending = 1u;
  m.pending_static_mask = 0x0fu;
  return m;
}

static struct vos_context make_test_context(uint64_t seed)
{
  struct vos_context ctx = {0};
  for (uint32_t r = 0u; r < VOS_REGISTER_COUNT; ++r) {
    ctx.reg[r].value = seed * 100u + r;
    ctx.reg[r].tag = (uint8_t)((seed + r) & 1u);
  }
  for (uint32_t c = 0u; c < VOS_MAX_CSRS; ++c) {
    ctx.csr[c] = seed * 1000u + c + 1u;
  }
  ctx.pending = seed * 17u + 3u;
  return ctx;
}

static struct vos_frame make_test_frame(uint32_t t0, uint32_t t1, uint32_t t2)
{
  struct vos_frame f = {0};
  f.major_frame = 300u;
  f.phase_offset = 10u;
  f.reserved_count = 1u;
  f.slot_count = 3u;
  f.slots[0] = (struct vos_slot){.width = 50u, .offset = 0u, .bound = 40u, .period = 300u, .tenant = t0};
  f.slots[1] = (struct vos_slot){.width = 100u, .offset = 50u, .bound = 80u, .period = 300u, .tenant = t1};
  f.slots[2] = (struct vos_slot){.width = 100u, .offset = 150u, .bound = 80u, .period = 300u, .tenant = t2};
  return f;
}

static int test_general_csr_restore_and_static_elision(void)
{
  const struct vos_machine m = make_test_machine();
  const struct vos_context succ = make_test_context(1u);
  const struct vos_context pre = make_test_context(2u);
  struct vos_context post = {0};
  struct vos_restore_receipt receipt = {0};

  /* StaticSlotManifest with VS=Off, XS=Off allows vmclear elision. */
  const struct vos_static_slot_manifest ssm_off = {.vs_off = 1u, .xs_off = 1u};
  CHECK_MSG(vos_elastic_static_slot_switch(&m, &ssm_off, &succ, &pre, &post, &receipt) ==
                VOS_ELASTIC_OK,
            "static switch with VS/XS=Off must succeed");
  CHECK_MSG(receipt.vmclear_executed == 0u && post.csr[1] == pre.csr[1],
            "static switch with VS/XS=Off elides vmclear");

  /* StaticSlotManifest with VS=On or XS=On must execute vmclear and zeroize CSR[1]. */
  const struct vos_static_slot_manifest ssm_vs_on = {.vs_off = 0u, .xs_off = 1u};
  CHECK_MSG(vos_elastic_static_slot_switch(&m, &ssm_vs_on, &succ, &pre, &post, &receipt) ==
                VOS_ELASTIC_OK,
            "static switch with VS!=Off must succeed");
  CHECK_MSG(receipt.vmclear_executed == 1u && post.csr[1] == 0u &&
                post.csr[0] == succ.csr[0] && post.csr[2] == pre.csr[2] &&
                post.csr[3] == succ.csr[3],
            "static switch with VS!=Off must execute vmclear and restore CSRs");

  /* Incomplete CSR restoration must be refused. */
  struct vos_restore_receipt incomplete = receipt;
  incomplete.csr_written[3] = 0u;
  CHECK_MSG(vos_elastic_verify_restore(&m, &succ, &pre, &post, 1, 1, &incomplete) ==
                VOS_ELASTIC_ERR_INCOMPLETE_RESTORE,
            "incomplete CSR restore must be refused");

  struct vos_context bad_post = post;
  bad_post.csr[1] = pre.csr[1];
  CHECK_MSG(vos_elastic_verify_restore(&m, &succ, &pre, &bad_post, 1, 1, &receipt) ==
                VOS_ELASTIC_ERR_WRONG_CSR_DISPOSITION,
            "unzeroed zeroizable CSR must be refused");

  incomplete = receipt;
  incomplete.reg_written_mask = UINT32_MAX ^ 1u;
  CHECK_MSG(vos_elastic_verify_restore(&m, &succ, &pre, &post, 1, 1, &incomplete) ==
                VOS_ELASTIC_ERR_INCOMPLETE_RESTORE,
            "incomplete register restore must be refused");
  return 0;
}

static int test_table_permutation_and_boundary_swap(void)
{
  const struct vos_frame base = make_test_frame(10u, 20u, 30u);
  const struct vos_frame perm = make_test_frame(10u, 30u, 20u);
  const struct vos_frame bad_res = make_test_frame(20u, 10u, 30u);
  const struct vos_frame bad_multiset = make_test_frame(10u, 20u, 20u);
  struct vos_frame bad_order = perm;
  bad_order.slots[1].offset = 150u;
  bad_order.slots[2].offset = 50u;

  CHECK_MSG(vos_frame_check_tenant_permutation(&base, &perm) == VOS_ELASTIC_OK,
            "discretionary permutation accepted");
  CHECK_MSG(vos_frame_check_tenant_permutation(&base, &bad_res) == VOS_ELASTIC_ERR_NOT_PERMUTATION,
            "reserved-band permutation refused");
  CHECK_MSG(vos_frame_check_tenant_permutation(&base, &bad_multiset) ==
                VOS_ELASTIC_ERR_NOT_PERMUTATION,
            "non-bijective tenant map refused");
  CHECK_MSG(vos_frame_check_tenant_permutation(&base, &bad_order) ==
                VOS_ELASTIC_ERR_NOT_PERMUTATION,
            "wrong table order must be refused");

  struct vos_elastic_table_exec te;
  CHECK_MSG(vos_elastic_table_init(&te, &base, 0u) == VOS_ELASTIC_OK, "table init");
  CHECK_MSG(vos_elastic_table_stage_swap(&te, &bad_order, 1u, 1) == VOS_ELASTIC_ERR_INVALID,
            "wrong table order must be refused at swap stage");
  CHECK_MSG(vos_elastic_table_stage_swap(&te, &perm, 1u, 1) == VOS_ELASTIC_OK,
            "stage valid permutation");

  uint8_t swapped = 0u;
  CHECK_MSG(vos_elastic_table_advance(&te, &swapped) == VOS_ELASTIC_OK && swapped == 0u &&
                te.active_frame.slots[1].tenant == 20u && te.rung_index == 0u,
            "swap must not occur mid-frame at slot 1");
  CHECK_MSG(vos_elastic_table_advance(&te, &swapped) == VOS_ELASTIC_OK && swapped == 0u &&
                te.active_frame.slots[2].tenant == 30u,
            "swap must not occur mid-frame at slot 2");
  CHECK_MSG(vos_elastic_table_advance(&te, &swapped) == VOS_ELASTIC_OK && swapped == 1u &&
                te.exec.cursor == 0u && te.exec.frame_index == 1u &&
                te.active_frame.slots[1].tenant == 30u && te.rung_index == 1u,
            "atomic table swap must occur at major-frame boundary");
  return 0;
}

static int test_same_label_group_rotation(void)
{
  const struct vos_machine m = make_test_machine();
  struct vos_same_label_group g = {0};
  g.tenant = 5u;
  g.label = 42u;
  g.count = 3u;
  g.cursor = 0u;
  for (uint32_t i = 0u; i < 3u; ++i) {
    g.members[i].partition_idx = i;
    g.members[i].label = 42u;
    g.members[i].app_id = 1u;
    g.members[i].ctx = make_test_context(i + 1u);
  }
  struct vos_context post = {0};
  struct vos_restore_receipt receipt = {0};
  CHECK_MSG(vos_group_rotate_next(&g, &m, &post, &receipt) == VOS_ELASTIC_OK &&
                g.cursor == 1u && receipt.vmclear_executed == 0u &&
                post.csr[1] == g.members[0].ctx.csr[1] &&
                post.csr[0] == g.members[1].ctx.csr[0] &&
                post.pending == g.members[1].ctx.pending,
            "same-label rotation must omit vmclear and swap pending/restorable CSRs");

  g.members[2].label = 99u;
  CHECK_MSG(vos_group_rotate_next(&g, &m, &post, &receipt) == VOS_ELASTIC_ERR_INVALID,
            "cross-label group member must be refused");
  return 0;
}

static struct vos_elastic_decl make_test_decl(void)
{
  struct vos_elastic_decl d = {0};
  d.count = 3u;
  d.weights[0] = 1u;
  d.weights[1] = 2u;
  d.weights[2] = 3u;
  d.requests[0] = 4u;
  d.requests[1] = 4u;
  d.requests[2] = 4u;
  d.app_ids[0] = 10u;
  d.app_ids[1] = 20u;
  d.app_ids[2] = 10u;
  d.focus_weight = 2u;
  d.focus_request = 4u;
  d.call_interval = 2u;
  d.yield_bound = 2u;
  d.step_cost = 5u;
  d.width_count = 1u;
  d.widths[0] = 100u;
  d.core_count = 1u;
  d.cores[0] = 0u;
  d.dormant[0][0] = 1u;
  d.dormant[1][0] = 1u;
  d.dormant[2][0] = 0u;
  d.vmclear_cost = 3u;
  d.machine = make_test_machine();
  return d;
}

static int test_eevdf_dispatch_vmclear_boundary_and_leave(void)
{
  const struct vos_elastic_decl d = make_test_decl();
  CHECK_MSG(vos_elastic_decl_admits(&d) == VOS_ELASTIC_OK, "decl admits");
  CHECK_MSG(vos_elastic_call_bound(&d) == 4u && vos_elastic_boundary_need(&d) == 11u,
            "call_bound=4 and boundary_need=11");

  struct vos_elastic_domain_state st;
  CHECK_MSG(vos_elastic_init_state(&d, &st, 0u, 0x3u) == VOS_ELASTIC_OK, "init state");
  for (uint32_t i = 0u; i < 3u; ++i) {
    st.contexts[i].arch = make_test_context(i + 1u);
  }
  CHECK_MSG(vos_rat_eq(vos_elastic_sum_competing_lag(&d, &st), vos_rat_make(0, 1)),
            "fresh zero-sum lag");

  /* Launch request: member 2 is not dormant on core 0 -> refused; member 1 -> ok. */
  st.contexts[0].sm.request_cell =
      (struct vos_session_request){.kind = VOS_SREQ_LAUNCH, .member = 2u, .core = 0u};
  CHECK_MSG(vos_elastic_enact_session_request(&d, &st) == VOS_ELASTIC_ERR_NOT_PLACED &&
                !st.contexts[2].dispatch.active,
            "unplaced launch must refuse");

  /* Initial yield selects earliest deadline: member 1 (coop_req=8, w=2 -> dl=4 < 8). */
  enum vos_yield_outcome out = VOS_YIELD_CONTINUE;
  int32_t next = -1;
  struct vos_context post = {0};
  struct vos_restore_receipt receipt = {0};
  CHECK_MSG(vos_elastic_invoke_pc_yield(&d, &st, 1, 0u, 100u, &out, &next, &post, &receipt) ==
                VOS_ELASTIC_OK &&
                out == VOS_YIELD_SWITCHED && next == 1,
            "initial dispatch selects member 1");

  /* Tentative yield with used=2 < req=4 and rem=100 >= 11 -> Continue. */
  CHECK_MSG(vos_elastic_invoke_pc_yield(&d, &st, 1, 2u, 100u, &out, &next, &post, &receipt) ==
                VOS_ELASTIC_OK &&
                out == VOS_YIELD_CONTINUE && st.current == 1,
            "tentative yield continues within request and boundary");

  /* Boundary overrun (rem=10 < 11) must refuse Continue and block real yield! */
  CHECK_MSG(vos_elastic_invoke_pc_yield(&d, &st, 1, 2u, 10u, &out, &next, &post, &receipt) ==
                VOS_ELASTIC_OK &&
                out == VOS_YIELD_SWITCH_REQUESTED && st.current == 1,
            "boundary overrun must request switch");
  CHECK_MSG(vos_elastic_invoke_pc_yield(&d, &st, 0, 2u, 10u, &out, &next, &post, &receipt) ==
                VOS_ELASTIC_ERR_BOUNDARY,
            "boundary overrun must be refused on dispatch step");

  /* Second tentative yield backstop enacts switch from member 1 (app 20) to member 0 (app 10).
   * Cross-application switch MUST execute vmclear! */
  CHECK_MSG(vos_elastic_invoke_pc_yield(&d, &st, 1, 2u, 100u, &out, &next, &post, &receipt) ==
                VOS_ELASTIC_OK &&
                out == VOS_YIELD_SWITCHED && next == 0,
            "repeated tentative backstop switches to member 0");
  CHECK_MSG(receipt.vmclear_executed == 1u && post.csr[1] == 0u,
            "cross-app switch must execute vmclear");
  CHECK_MSG(vos_rat_eq(vos_elastic_sum_competing_lag(&d, &st), vos_rat_make(0, 1)),
            "charge preserves zero-sum lag");

  /* Same-app step between member 0 (app 10) and member 2 (app 10) elides vmclear. */
  CHECK_MSG(vos_elastic_context_step(&d, &st, 0u, 2u, &post, &receipt) == VOS_ELASTIC_OK &&
                receipt.vmclear_executed == 0u && post.csr[1] == st.contexts[0].arch.csr[1],
            "same-app step elides vmclear");

  /* Starvation control for EEVDF published leave adjustment:
   * Member 1 runs with used=6 (ahead of vtime by +1: vtime=2, elig[1]=3, lag[1]=-2;
   * elig[0]=0, lag[0]=+2). Then member 0 leaves!
   *Wait: let's have member 0 leave? No: if member 0 (lag=+2) leaves, vtime increases by +2/2=+1 -> vtime=3==elig[1],
   * so member 1 (the ONLY remaining competing member!) becomes immediately eligible (select == 1) and never starves!
   * Without the EEVDF leave adjustment, vtime stays 2 < elig[1]=3, so select == -1 (starvation)! */
  struct vos_elastic_domain_state leave_st;
  CHECK_MSG(vos_elastic_init_state(&d, &leave_st, 0u, 0x3u) == VOS_ELASTIC_OK, "leave init");
  leave_st.current = 1;
  CHECK_MSG(vos_elastic_invoke_pc_yield(&d, &leave_st, 0, 6u, 100u, &out, &next, &post, &receipt) ==
                VOS_ELASTIC_OK,
            "charge member 1");
  /* After used=6: vtime = 6/3 = 2, elig[1] = 6/2 = 3, lag[1] = 2*(2-3) = -2, lag[0] = 1*(2-0) = +2. */
  CHECK_MSG(vos_elastic_published_leave(&d, &leave_st, 0u) == VOS_ELASTIC_OK,
            "published leave of member 0");
  CHECK_MSG(vos_rat_eq(vos_elastic_sum_competing_lag(&d, &leave_st), vos_rat_make(0, 1)),
            "published leave must preserve zero-sum lag");
  CHECK_MSG(vos_elastic_select(&d, &leave_st) == 1,
            "dropped EEVDF leave adjustment causes starvation of eligible member");

  /* Cooperative lag bound check: |lag| <= max_request + call_bound. */
  const struct vos_rat bound = vos_elastic_lag_bound(&d);
  for (uint32_t i = 0u; i < d.count; ++i) {
    if (st.contexts[i].dispatch.active && st.contexts[i].dispatch.pending) {
      const struct vos_rat lag_i = vos_rat_abs(vos_elastic_accounting_lag(&d, &st, i));
      CHECK_MSG(vos_rat_cmp(lag_i, bound) <= 0, "accounting lag within cooperative bound");
    }
  }
  return 0;
}

static int run_eevdf_trace(void)
{
  /* Replay the exact 3-member cooperative trace and emit rational state lines. */
  struct vos_elastic_decl d = make_test_decl();
  d.weights[0] = 1u;
  d.weights[1] = 9u;
  d.weights[2] = 90u;
  d.requests[0] = 4u;
  d.requests[1] = 1u;
  d.requests[2] = 4u;
  d.app_ids[0] = 0u;
  d.app_ids[1] = 1u;
  d.app_ids[2] = 2u;

  struct vos_elastic_domain_state st;
  if (vos_elastic_init_state(&d, &st, 0u, 0x7u) != VOS_ELASTIC_OK) {
    return 2;
  }
  const uint32_t steps[6] = {9u, 1u, 1u, 6u, 6u, 6u};
  for (uint32_t k = 0u; k < 6u; ++k) {
    enum vos_yield_outcome out = VOS_YIELD_CONTINUE;
    int32_t next = -1;
    struct vos_context post = {0};
    struct vos_restore_receipt receipt = {0};
    if (st.current < 0) {
      if (vos_elastic_invoke_pc_yield(&d, &st, 0, 0u, 100u, &out, &next, &post, &receipt) !=
          VOS_ELASTIC_OK) {
        return 2;
      }
    }
    const uint32_t cur = (uint32_t)st.current;
    if (vos_elastic_invoke_pc_yield(&d, &st, 0, steps[k], 100u, &out, &next, &post, &receipt) !=
        VOS_ELASTIC_OK) {
      return 2;
    }
    const struct vos_rat sum = vos_elastic_sum_competing_lag(&d, &st);
    const struct vos_rat l0 = vos_elastic_accounting_lag(&d, &st, 0u);
    const struct vos_rat l1 = vos_elastic_accounting_lag(&d, &st, 1u);
    const struct vos_rat l2 = vos_elastic_accounting_lag(&d, &st, 2u);
    printf("STEP %u cur=%u next=%d vmclear=%u v=%lld/%lld sum=%lld/%lld l0=%lld/%lld l1=%lld/%lld l2=%lld/%lld\n",
           k, cur, next, (unsigned)receipt.vmclear_executed,
           (long long)st.contexts[0].sm.vtime.num, (long long)st.contexts[0].sm.vtime.den,
           (long long)sum.num, (long long)sum.den,
           (long long)l0.num, (long long)l0.den,
           (long long)l1.num, (long long)l1.den,
           (long long)l2.num, (long long)l2.den);
  }
  return 0;
}

int main(int argc, char **argv)
{
  if (argc == 2 && strcmp(argv[1], "--eevdf-trace") == 0) {
    return run_eevdf_trace();
  }
  if (test_general_csr_restore_and_static_elision() != 0 ||
      test_table_permutation_and_boundary_swap() != 0 ||
      test_same_label_group_rotation() != 0 ||
      test_eevdf_dispatch_vmclear_boundary_and_leave() != 0) {
    return 1;
  }
  printf("ok elastic_exec %u checks\n", g_checks);
  return 0;
}
