// SPDX-License-Identifier: Apache-2.0
#include <stdio.h>
#include <string.h>

#include "vos_elastic_pool.h"
#include "vos_supervisor.h"

static uint32_t g_checks = 0u;

#define CHECK_MSG(cond, msg)                                                           \
  do {                                                                                 \
    ++g_checks;                                                                        \
    if (!(cond)) {                                                                     \
      fprintf(stderr, "FAIL elastic_pool check %u line %d: %s\n", g_checks, __LINE__,  \
              (msg));                                                                  \
      return 1;                                                                        \
    }                                                                                  \
  } while (0)

static struct vos_pool_plan make_fixture_plan(void)
{
  struct vos_pool_plan plan = {0};
  plan.island = 0u;
  plan.memory_class = 0u;
  plan.base = 64u;
  plan.span = 64u;
  plan.class_count = 2u;
  plan.classes[0] = (struct vos_pool_size_class){16u, 16u, 1u};
  plan.classes[1] = (struct vos_pool_size_class){32u, 32u, 1u};
  plan.slot_count = 3u;
  plan.slots[0] = (struct vos_pool_slot_layout){64u, 0u};
  plan.slots[1] = (struct vos_pool_slot_layout){80u, 0u};
  plan.slots[2] = (struct vos_pool_slot_layout){96u, 1u};
  plan.quarantine_allowance = 64u;
  return plan;
}

static int test_std_size_classes_and_narrowing(void)
{
  for (uint32_t i = 0u; i < VOS_POOL_STD_CLASS_COUNT; ++i) {
    const struct vos_pool_size_class *sc = &vos_pool_std_classes[i];
    CHECK_MSG(vos_pool_size_class_exact(sc), "std size class must be exact");
    CHECK_MSG(sc->granule == vos_pool_representable_granule(sc->length),
              "std size class granule mismatch");
    CHECK_MSG(vos_pool_narrow_length(sc, 1u) == sc->granule,
              "narrowing 1 byte must yield class granule");
    CHECK_MSG(vos_pool_narrow_length(sc, sc->length) == sc->length,
              "narrowing exact class length must preserve length");
  }
  CHECK_MSG(vos_pool_representable_granule(127u) == 1u, "granule at 127");
  CHECK_MSG(vos_pool_representable_granule(128u) == 2u, "granule at 128");
  CHECK_MSG(vos_pool_representable_granule(192u) == 2u, "granule at 192");
  CHECK_MSG(vos_pool_representable_granule(384u) == 4u, "granule at 384");
  CHECK_MSG(vos_pool_representable_granule(512u) == 8u, "granule at 512");
  CHECK_MSG(vos_pool_representable_granule(65536u) == 1024u, "granule at 65536");

  struct vos_pool_size_class bad = {129u, 2u, 0u};
  CHECK_MSG(!vos_pool_size_class_exact(&bad), "129/2 must be inexact");
  struct vos_pool_size_class c512 = vos_pool_std_classes[5];
  CHECK_MSG(vos_pool_narrow_length(&c512, 0u) == 0u, "zero request refused");
  CHECK_MSG(vos_pool_narrow_length(&c512, 513u) == 0u, "overlong request refused");
  CHECK_MSG(vos_pool_narrow_length(&c512, 9u) == 16u, "9 bytes narrows to 16");
  CHECK_MSG(vos_pool_narrow_length(&c512, 16u) == 16u, "16 bytes narrows to 16");

  static uint8_t backing[512];
  memset(backing, 0x13, sizeof(backing));
  struct vos_pool_plan plan = {0};
  plan.island = 0u;
  plan.memory_class = 0u;
  plan.base = 512u;
  plan.span = 512u;
  plan.class_count = 1u;
  plan.classes[0] = c512;
  plan.slot_count = 1u;
  plan.slots[0] = (struct vos_pool_slot_layout){512u, 0u};
  plan.quarantine_allowance = 512u;
  struct vos_pool pool;
  CHECK_MSG(vos_pool_init(&pool, &plan, backing, sizeof(backing), 10u) == VOS_POOL_OK,
            "512-byte pool init");
  struct vos_pool_grant g;
  CHECK_MSG(vos_pool_alloc_narrowed(&pool, 1u, 0u, 0u, 9u, &g) == VOS_POOL_OK,
            "narrowed allocation must succeed");
  CHECK_MSG(g.length == 16u, "narrowed grant length must be 16");
  uint8_t byte_val = 0x55u;
  CHECK_MSG(vos_pool_read(&pool, &g, 15u, &byte_val) == VOS_POOL_OK && byte_val == 0u,
            "eager zeroing missing on narrowed allocation");
  CHECK_MSG(vos_pool_write(&pool, &g, 16u, 1u) == VOS_POOL_ERR_OUT_OF_RANGE,
            "write past narrowed length must refuse");
  return 0;
}

static int test_eager_zeroing_and_exhaustion(void)
{
  const struct vos_pool_plan plan = make_fixture_plan();
  uint8_t backing[64];
  memset(backing, 0x13, sizeof(backing));
  struct vos_pool pool;
  CHECK_MSG(vos_pool_init(&pool, &plan, backing, sizeof(backing), 1u) == VOS_POOL_OK,
            "pool init");

  struct vos_pool_grant g0, g1, g2;
  CHECK_MSG(vos_pool_alloc(&pool, 1u, 0u, 0u, &g0) == VOS_POOL_OK, "alloc slot 0");
  for (uint64_t i = 0u; i < g0.length; ++i) {
    uint8_t v = 99u;
    CHECK_MSG(vos_pool_read(&pool, &g0, i, &v) == VOS_POOL_OK && v == 0u,
              "eager zeroing missing on initial grant");
  }
  CHECK_MSG(vos_pool_alloc(&pool, 2u, 0u, 0u, &g1) == VOS_POOL_OK, "alloc slot 1");
  struct vos_pool_grant refused = {0};
  const uint64_t serial_before = pool.serial;
  const uint32_t events_before = pool.event_count;
  CHECK_MSG(vos_pool_alloc(&pool, 3u, 0u, 0u, &refused) == VOS_POOL_ERR_EXHAUSTED,
            "exhausted class must refuse without borrowing larger class");
  CHECK_MSG(pool.slots[2].phase == VOS_SLOT_FREE && pool.serial == serial_before &&
                pool.event_count == events_before,
            "exhausted refusal mutated pool state or borrowed larger class");

  CHECK_MSG(vos_pool_alloc(&pool, 3u, 1u, 0u, &g2) == VOS_POOL_OK && g2.length == 32u,
            "class 1 remains independently allocatable");
  CHECK_MSG(vos_pool_write(&pool, &g0, 0u, 0xa7u) == VOS_POOL_OK, "write dirty byte");
  CHECK_MSG(vos_pool_write(&pool, &g0, 15u, 0x5au) == VOS_POOL_OK, "write tail dirty byte");

  CHECK_MSG(vos_pool_release(&pool, &g0) == VOS_POOL_OK, "release slot 0");
  CHECK_MSG(vos_pool_write(&pool, &g0, 0u, 1u) == VOS_POOL_ERR_STALE_OR_FOREIGN,
            "stale write after release refused");
  CHECK_MSG(vos_pool_clear_registers(&pool, g0.slot) == VOS_POOL_OK, "clear reg");
  CHECK_MSG(vos_pool_barrier(&pool) == VOS_POOL_OK, "barrier");
  CHECK_MSG(vos_pool_sweep_begin(&pool) == VOS_POOL_OK, "sweep begin");
  CHECK_MSG(vos_pool_alloc(&pool, 4u, 0u, 0u, &refused) == VOS_POOL_ERR_EXHAUSTED,
            "early reuse during active sweep must refuse");
  CHECK_MSG(vos_pool_sweep_end(&pool) == VOS_POOL_OK, "sweep end");

  struct vos_pool_grant reused;
  CHECK_MSG(vos_pool_alloc(&pool, 4u, 0u, 0u, &reused) == VOS_POOL_OK, "reuse slot 0");
  CHECK_MSG(reused.base == g0.base && reused.serial > g0.serial &&
                reused.generation == g0.generation + 1u,
            "reused slot must advance generation and serial");
  for (uint64_t i = 0u; i < reused.length; ++i) {
    uint8_t v = 99u;
    CHECK_MSG(vos_pool_read(&pool, &reused, i, &v) == VOS_POOL_OK && v == 0u,
              "eager zeroing missing on reused grant");
  }
  CHECK_MSG(vos_pool_write(&pool, &g0, 0u, 1u) == VOS_POOL_ERR_STALE_OR_FOREIGN,
            "old generation grant must stay stale after reuse");
  (void)g1;
  return 0;
}

static int test_two_generation_quarantine(void)
{
  const struct vos_pool_plan plan = make_fixture_plan();
  uint8_t backing[64];
  memset(backing, 0x13, sizeof(backing));
  struct vos_pool pool;
  CHECK_MSG(vos_pool_init(&pool, &plan, backing, sizeof(backing), 2u) == VOS_POOL_OK,
            "pool init");

  struct vos_pool_grant g0, g1;
  CHECK_MSG(vos_pool_alloc(&pool, 1u, 0u, 0u, &g0) == VOS_POOL_OK, "alloc 0");
  CHECK_MSG(vos_pool_alloc(&pool, 2u, 0u, 0u, &g1) == VOS_POOL_OK, "alloc 1");

  CHECK_MSG(vos_pool_release(&pool, &g0) == VOS_POOL_OK, "release 0");
  CHECK_MSG(vos_pool_clear_registers(&pool, g0.slot) == VOS_POOL_OK, "clear 0");
  CHECK_MSG(vos_pool_barrier(&pool) == VOS_POOL_OK, "barrier 0");
  CHECK_MSG(vos_pool_sweep_begin(&pool) == VOS_POOL_OK, "sweep begin 1");

  /* Release & barrier slot 1 WHILE sweep 1 is active: must wait for sweep 2. */
  CHECK_MSG(vos_pool_release(&pool, &g1) == VOS_POOL_OK, "release 1 during sweep");
  CHECK_MSG(vos_pool_clear_registers(&pool, g1.slot) == VOS_POOL_OK, "clear 1 during sweep");
  CHECK_MSG(vos_pool_barrier(&pool) == VOS_POOL_OK, "barrier 1 during sweep");
  CHECK_MSG(vos_pool_sweep_end(&pool) == VOS_POOL_OK, "sweep end 1");

  CHECK_MSG(pool.slots[0].phase == VOS_SLOT_FREE, "slot 0 freed");
  CHECK_MSG(pool.slots[1].phase == VOS_SLOT_BARRIER,
            "early reuse during active sweep: slot 1 must remain BARRIER after sweep 1");

  struct vos_pool_grant g2, g3;
  CHECK_MSG(vos_pool_alloc(&pool, 3u, 0u, 0u, &g2) == VOS_POOL_OK && g2.slot == 0u,
            "realloc slot 0");
  CHECK_MSG(vos_pool_alloc(&pool, 4u, 0u, 0u, &g3) == VOS_POOL_ERR_EXHAUSTED,
            "early reuse during active sweep: slot 1 must not be allocatable before sweep 2");

  CHECK_MSG(vos_pool_sweep_begin(&pool) == VOS_POOL_OK, "sweep begin 2");
  CHECK_MSG(vos_pool_sweep_end(&pool) == VOS_POOL_OK, "sweep end 2");
  CHECK_MSG(vos_pool_alloc(&pool, 4u, 0u, 0u, &g3) == VOS_POOL_OK && g3.slot == 1u,
            "slot 1 freed after second sweep");
  return 0;
}

static int test_holder_barrier_and_kernel_effects(void)
{
  const struct vos_pool_plan plan = make_fixture_plan();
  uint8_t backing[64];
  memset(backing, 0x13, sizeof(backing));
  struct vos_pool pool;
  CHECK_MSG(vos_pool_init(&pool, &plan, backing, sizeof(backing), 3u) == VOS_POOL_OK,
            "pool init");

  /* Wire kernel/include/vos_effects.h single-hart primitives. */
  struct vos_kernel_effect_state effects;
  vos_cap_t roots[VOS_SUPERVISOR_UNITS] = {0};
  uint64_t masks[VOS_SUPERVISOR_UNITS] = {0};
  uint64_t bitmap = 0u;
  uint64_t ticks = 0u;
  for (uint32_t i = 0u; i < 3u; ++i) {
    roots[i].value = 100u + i;
    roots[i].tag = 1u;
    masks[i] = UINT64_C(1) << i;
  }
  CHECK_MSG(vos_kernel_effect_init(&effects, &vos_m8a_supervisor_manifest, 10u),
            "kernel effect init");
  CHECK_MSG(vos_kernel_effect_bind(&effects, roots, masks, &bitmap, &ticks, 4u),
            "kernel effect bind");
  CHECK_MSG(vos_pool_bind_effects(&pool, &effects, 7u) == VOS_POOL_OK,
            "pool bind effects");

  struct vos_pool_grant g0;
  CHECK_MSG(vos_pool_alloc(&pool, 1u, 0u, 0u, &g0) == VOS_POOL_OK, "alloc 0");
  CHECK_MSG(vos_pool_release(&pool, &g0) == VOS_POOL_OK, "release 0");

  /* 1. Stale HReg (automatic from release) blocks barrier even if resident_clean=1. */
  effects.resident_clean = 1u;
  CHECK_MSG(vos_pool_barrier(&pool) == VOS_POOL_ERR_HOLDER_ACTIVE,
            "stale register holder must block barrier");
  CHECK_MSG(pool.slots[0].phase == VOS_SLOT_PENDING,
            "failed barrier must leave slot pending");

  /* Clear registers, then test stale HSavedCtx alone. */
  CHECK_MSG(vos_pool_clear_registers(&pool, g0.slot) == VOS_POOL_OK, "clear reg");
  CHECK_MSG(vos_pool_add_holder(&pool, 100u, VOS_HOLDER_SAVED_CTX, g0.base, g0.length) ==
                VOS_POOL_OK,
            "add saved-ctx holder");
  CHECK_MSG(vos_pool_barrier(&pool) == VOS_POOL_ERR_HOLDER_ACTIVE,
            "stale saved-ctx holder must block barrier");
  CHECK_MSG(vos_pool_clear_holder(&pool, 100u) == VOS_POOL_OK, "clear saved-ctx");

  /* Test stale HStoredCell alone. */
  CHECK_MSG(vos_pool_add_holder(&pool, 101u, VOS_HOLDER_STORED_CELL, g0.base + 8u, 8u) ==
                VOS_POOL_OK,
            "add stored-cell holder");
  CHECK_MSG(vos_pool_barrier(&pool) == VOS_POOL_ERR_HOLDER_ACTIVE,
            "stale stored-cell holder must block barrier");
  CHECK_MSG(vos_pool_clear_holder(&pool, 101u) == VOS_POOL_OK, "clear stored-cell");
  effects.resident_clean = 0u;
  CHECK_MSG(vos_pool_barrier(&pool) == VOS_POOL_ERR_BARRIER_INCOMPLETE,
            "missing resident_clean must block kernel effect semantic completion");
  CHECK_MSG(pool.slots[0].phase == VOS_SLOT_PENDING,
            "incomplete semantic completion must leave slot pending");

  /* Re-initialize fresh kernel effect state at epoch 10 with resident_clean=1. */
  bitmap = 0u;
  CHECK_MSG(vos_kernel_effect_init(&effects, &vos_m8a_supervisor_manifest, 10u),
            "kernel effect re-init");
  CHECK_MSG(vos_kernel_effect_bind(&effects, roots, masks, &bitmap, &ticks, 4u),
            "kernel effect re-bind");
  CHECK_MSG(vos_pool_bind_effects(&pool, &effects, 7u) == VOS_POOL_OK,
            "pool re-bind effects");
  effects.resident_clean = 1u;
  CHECK_MSG(vos_pool_barrier(&pool) == VOS_POOL_OK,
            "barrier must succeed once all holders cleared and semantic completion met");
  CHECK_MSG(effects.epoch == 11u && pool.epoch == 11u && (bitmap & 7u) == 7u,
            "barrier must advance effect epoch and publish bitmap bits");
  CHECK_MSG(vos_pool_sweep_begin(&pool) == VOS_POOL_OK, "sweep begin");
  CHECK_MSG(vos_pool_sweep_end(&pool) == VOS_POOL_OK, "sweep end");
  CHECK_MSG(vos_pool_alloc(&pool, 2u, 0u, 0u, &g0) == VOS_POOL_OK, "reuse after barrier");
  return 0;
}

static int test_descendant_invalidation(void)
{
  const struct vos_pool_plan plan = make_fixture_plan();
  uint8_t backing[64];
  memset(backing, 0x13, sizeof(backing));
  struct vos_pool parent;
  CHECK_MSG(vos_pool_init(&parent, &plan, backing, sizeof(backing), 10u) == VOS_POOL_OK,
            "parent init");

  struct vos_pool_grant root;
  CHECK_MSG(vos_pool_alloc(&parent, 1u, 1u, 0u, &root) == VOS_POOL_OK, "alloc 32B root");

  struct vos_pool child;
  const struct vos_pool_size_class c_classes[1] = {{8u, 8u, 1u}};
  const struct vos_pool_slot_layout c_slots[2] = {{root.base, 0u}, {root.base + 8u, 0u}};
  CHECK_MSG(vos_pool_heap_init(&parent, &root, &child, c_classes, 1u, c_slots, 2u, 11u) ==
                VOS_POOL_OK,
            "child heap init");
  CHECK_MSG(vos_pool_heap_init(&parent, &root, &child, c_classes, 1u, c_slots, 2u, 12u) ==
                VOS_POOL_ERR_CHILD_EXISTS,
            "duplicate child heap refused");
  CHECK_MSG(vos_pool_write(&parent, &root, 0u, 5u) == VOS_POOL_ERR_HEAP_OWNED,
            "direct parent write to heap-owned chunk refused");

  struct vos_pool_grant cg;
  CHECK_MSG(vos_pool_alloc(&child, 1u, 0u, 0u, &cg) == VOS_POOL_OK, "child alloc");
  CHECK_MSG(vos_pool_write(&child, &cg, 0u, 83u) == VOS_POOL_OK, "child write");
  CHECK_MSG(backing[cg.base - parent.plan.base] == 83u,
            "child must share parent backing bytes");

  /* Release parent, reclaim, and reallocate SAME slot at next generation. */
  CHECK_MSG(vos_pool_release(&parent, &root) == VOS_POOL_OK, "parent release");
  CHECK_MSG(vos_pool_alloc(&child, 1u, 0u, 0u, &cg) == VOS_POOL_ERR_PARENT_DEAD,
            "child alloc after parent release must fail");
  CHECK_MSG(vos_pool_clear_registers(&parent, root.slot) == VOS_POOL_OK, "parent clear");
  CHECK_MSG(vos_pool_barrier(&parent) == VOS_POOL_OK, "parent barrier");
  CHECK_MSG(vos_pool_sweep_begin(&parent) == VOS_POOL_OK, "parent sweep begin");
  CHECK_MSG(vos_pool_sweep_end(&parent) == VOS_POOL_OK, "parent sweep end");

  struct vos_pool_grant root_next_gen;
  CHECK_MSG(vos_pool_alloc(&parent, 2u, 1u, 0u, &root_next_gen) == VOS_POOL_OK,
            "parent realloc next gen");
  CHECK_MSG(root_next_gen.slot == root.slot && root_next_gen.generation == root.generation + 1u,
            "parent next gen slot check");

  /* Old child must stay permanently dead even when parent slot is LIVE again! */
  struct vos_pool_grant cg2;
  CHECK_MSG(vos_pool_alloc(&child, 1u, 0u, 0u, &cg2) == VOS_POOL_ERR_PARENT_DEAD,
            "old descendant must remain dead after parent realloc at next generation");
  CHECK_MSG(vos_pool_write(&child, &cg, 0u, 99u) == VOS_POOL_ERR_PARENT_DEAD,
            "old descendant write must remain dead");
  CHECK_MSG(vos_pool_release(&child, &cg) == VOS_POOL_ERR_PARENT_DEAD,
            "old descendant release must remain dead");
  return 0;
}

static int test_island_and_granule_separation(void)
{
  /* Shared 8-byte revocation granule within one pool must fail validation. */
  struct vos_pool_plan bad_slots = {0};
  bad_slots.island = 0u;
  bad_slots.memory_class = 0u;
  bad_slots.base = 64u;
  bad_slots.span = 8u;
  bad_slots.class_count = 1u;
  bad_slots.classes[0] = (struct vos_pool_size_class){4u, 4u, 1u};
  bad_slots.slot_count = 2u;
  bad_slots.slots[0] = (struct vos_pool_slot_layout){64u, 0u};
  bad_slots.slots[1] = (struct vos_pool_slot_layout){68u, 0u};
  bad_slots.quarantine_allowance = 8u;
  CHECK_MSG(vos_pool_plan_validate(&bad_slots) == VOS_POOL_ERR_SHARED_GRANULE,
            "byte-disjoint slots sharing an 8-byte revocation granule must be refused");

  /* Separated by 8-byte granule (64 and 72) is admitted. */
  uint8_t b_isl0[16];
  uint8_t b_isl1[16];
  memset(b_isl0, 0x13, sizeof(b_isl0));
  memset(b_isl1, 0x13, sizeof(b_isl1));
  struct vos_pool_plan p0_plan = {0};
  p0_plan.island = 0u;
  p0_plan.memory_class = 0u;
  p0_plan.base = 64u;
  p0_plan.span = 16u;
  p0_plan.class_count = 1u;
  p0_plan.classes[0] = (struct vos_pool_size_class){4u, 4u, 1u};
  p0_plan.slot_count = 2u;
  p0_plan.slots[0] = (struct vos_pool_slot_layout){64u, 0u};
  p0_plan.slots[1] = (struct vos_pool_slot_layout){72u, 0u};
  p0_plan.quarantine_allowance = 16u;
  p0_plan.revocable_count = 1u;
  p0_plan.revocable[0] = (struct vos_pool_interval){64u, 64u};

  struct vos_pool_plan p1_bad_plan = p0_plan;
  p1_bad_plan.island = 1u;
  p1_bad_plan.base = 68u;
  p1_bad_plan.span = 4u;
  p1_bad_plan.slot_count = 1u;
  p1_bad_plan.slots[0] = (struct vos_pool_slot_layout){68u, 0u};
  p1_bad_plan.quarantine_allowance = 4u;

  struct vos_pool_plan p0_small = p0_plan;
  p0_small.span = 4u;
  p0_small.slot_count = 1u;
  p0_small.quarantine_allowance = 4u;

  struct vos_pool pool0, pool1_bad;
  CHECK_MSG(vos_pool_init(&pool0, &p0_small, b_isl0, 4u, 20u) == VOS_POOL_OK, "small pool0");
  CHECK_MSG(vos_pool_init(&pool1_bad, &p1_bad_plan, b_isl1, 4u, 21u) == VOS_POOL_OK,
            "small pool1_bad");
  const struct vos_domain_pool_binding bad_bindings[2] = {
    {0u, 0u, &pool0},
    {1u, 0u, &pool1_bad}
  };
  const struct vos_domain_launch launches[2] = {{1u, 0u}, {2u, 1u}};
  struct vos_domain_pools dom;
  CHECK_MSG(vos_domain_pools_init(&dom, bad_bindings, 2u, launches, 2u) ==
                VOS_POOL_ERR_SHARED_GRANULE,
            "two arenas sharing an 8-byte revocation granule must be refused");

  /* Disjoint arenas across two islands bind launch islands properly. */
  struct vos_pool_plan p1_good = p0_plan;
  p1_good.island = 1u;
  p1_good.base = 128u;
  p1_good.slots[0].base = 128u;
  p1_good.slots[1].base = 136u;
  p1_good.revocable[0] = (struct vos_pool_interval){128u, 64u};
  struct vos_pool pool0_full, pool1_good;
  CHECK_MSG(vos_pool_init(&pool0_full, &p0_plan, b_isl0, 16u, 22u) == VOS_POOL_OK, "pool0 full");
  CHECK_MSG(vos_pool_init(&pool1_good, &p1_good, b_isl1, 16u, 23u) == VOS_POOL_OK, "pool1 good");
  const struct vos_domain_pool_binding good_bindings[2] = {
    {0u, 0u, &pool0_full},
    {1u, 0u, &pool1_good}
  };
  CHECK_MSG(vos_domain_pools_init(&dom, good_bindings, 2u, launches, 2u) == VOS_POOL_OK,
            "disjoint domain pools init");
  struct vos_pool_grant g_isl0, g_isl1;
  CHECK_MSG(vos_domain_pools_allocate(&dom, 1u, 0u, 0u, &g_isl0) == VOS_POOL_OK &&
                g_isl0.base == 64u,
            "member 1 must allocate on island 0");
  CHECK_MSG(vos_domain_pools_allocate(&dom, 2u, 0u, 0u, &g_isl1) == VOS_POOL_OK &&
                g_isl1.base == 128u,
            "member 2 must allocate on island 1");
  CHECK_MSG(vos_domain_pools_allocate(&dom, 99u, 0u, 0u, &g_isl0) ==
                VOS_POOL_ERR_FOREIGN_ISLAND,
            "unbound member must refuse");
  CHECK_MSG(vos_pool_alloc(&pool0_full, 1u, 0u, 1u, &g_isl0) == VOS_POOL_ERR_FOREIGN_ISLAND,
            "foreign launch island must refuse");
  return 0;
}

static int run_trace_mode(const char *digits)
{
  const struct vos_pool_plan plan = make_fixture_plan();
  uint8_t backing[64];
  memset(backing, 0x13, sizeof(backing));
  struct vos_pool pool;
  if (vos_pool_init(&pool, &plan, backing, sizeof(backing), 1u) != VOS_POOL_OK) {
    return 2;
  }
  for (size_t idx = 0u; digits[idx] != '\0'; ++idx) {
    const int cmd = digits[idx] - '0';
    if (cmd < 0 || cmd > 6) {
      return 2;
    }
    if (cmd < 2) {
      struct vos_pool_grant g;
      (void)vos_pool_alloc(&pool, (uint32_t)(1 + cmd), (uint32_t)cmd, 0u, &g);
    } else if (cmd == 2) {
      for (uint32_t s = 0u; s < pool.plan.slot_count; ++s) {
        if (pool.slots[s].phase == VOS_SLOT_LIVE) {
          const struct vos_pool_grant g = pool.slots[s].grant;
          if (vos_pool_write(&pool, &g, 0u, 7u) == VOS_POOL_OK) {
            (void)vos_pool_release(&pool, &g);
          }
          break;
        }
      }
    } else if (cmd == 3) {
      for (uint32_t s = 0u; s < pool.plan.slot_count; ++s) {
        if (pool.slots[s].phase == VOS_SLOT_PENDING) {
          (void)vos_pool_clear_registers(&pool, s);
        }
      }
    } else if (cmd == 4) {
      (void)vos_pool_barrier(&pool);
    } else if (cmd == 5) {
      (void)vos_pool_sweep_begin(&pool);
    } else {
      (void)vos_pool_sweep_end(&pool);
    }
  }
  for (uint32_t i = 0u; i < pool.event_count; ++i) {
    const struct vos_pool_event *ev = &pool.events[i];
    if (ev->kind == VOS_PEV_ZERO) {
      printf("Zero %llu %llu\n", (unsigned long long)ev->a0, (unsigned long long)ev->a1);
    } else if (ev->kind == VOS_PEV_GRANT) {
      printf("Grant %llu %llu %llu %llu %llu\n", (unsigned long long)ev->a0,
             (unsigned long long)ev->a1, (unsigned long long)ev->a2,
             (unsigned long long)ev->a3, (unsigned long long)ev->a4);
    } else if (ev->kind == VOS_PEV_WRITE) {
      printf("Write %llu %llu\n", (unsigned long long)ev->a0, (unsigned long long)ev->a1);
    } else if (ev->kind == VOS_PEV_RELEASE) {
      printf("Release %llu %llu\n", (unsigned long long)ev->a0, (unsigned long long)ev->a1);
    } else if (ev->kind == VOS_PEV_BARRIER_DONE) {
      printf("BarrierDone\n");
    } else if (ev->kind == VOS_PEV_SWEEP_BEGIN) {
      printf("SweepBegin\n");
    } else if (ev->kind == VOS_PEV_SWEEP_END) {
      printf("SweepEnd\n");
    }
  }
  return 0;
}

int main(int argc, char **argv)
{
  if (argc == 3 && strcmp(argv[1], "--trace") == 0) {
    return run_trace_mode(argv[2]);
  }
  if (test_std_size_classes_and_narrowing() != 0 ||
      test_eager_zeroing_and_exhaustion() != 0 ||
      test_two_generation_quarantine() != 0 ||
      test_holder_barrier_and_kernel_effects() != 0 ||
      test_descendant_invalidation() != 0 ||
      test_island_and_granule_separation() != 0) {
    return 1;
  }
  printf("ok elastic_pool %u checks\n", g_checks);
  return 0;
}
