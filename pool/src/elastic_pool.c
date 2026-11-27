// SPDX-License-Identifier: Apache-2.0
/*
 * Original GC-free C17 elastic pool service and default member heap library
 * (Q34c-ii-a), authored against [ElasticPool.v](../../proofs/ElasticPool.v)
 * and [elastic_pool.py](../../tools/vos/elastic_pool.py).
 */
#include "vos_elastic_pool.h"

const struct vos_pool_size_class vos_pool_std_classes[VOS_POOL_STD_CLASS_COUNT] = {
  {16u, 16u, 1u},
  {32u, 32u, 1u},
  {64u, 64u, 1u},
  {128u, 128u, 2u},
  {256u, 256u, 4u},
  {512u, 512u, 8u},
  {1024u, 1024u, 16u},
  {2048u, 2048u, 32u},
  {4096u, 4096u, 64u},
  {8192u, 8192u, 128u},
  {16384u, 16384u, 256u},
  {32768u, 32768u, 512u},
  {65536u, 65536u, 1024u}
};

static int extents_overlap(uint64_t b1, uint64_t l1, uint64_t b2, uint64_t l2)
{
  if (l1 == 0u || l2 == 0u) {
    return 0;
  }
  if (b1 < b2) {
    return (b2 - b1) < l1;
  }
  return (b1 - b2) < l2;
}

static int extents_granules_disjoint(uint64_t b1, uint64_t l1, uint64_t b2, uint64_t l2)
{
  const uint64_t f1 = b1 / VOS_POOL_REV_GRANULE;
  const uint64_t lim1 = ((b1 + l1 - 1u) / VOS_POOL_REV_GRANULE) + 1u;
  const uint64_t f2 = b2 / VOS_POOL_REV_GRANULE;
  const uint64_t lim2 = ((b2 + l2 - 1u) / VOS_POOL_REV_GRANULE) + 1u;
  return lim1 <= f2 || lim2 <= f1;
}

static void zero_bytes(uint8_t *dst, uint64_t len)
{
  for (uint64_t i = 0u; i < len; ++i) {
    dst[i] = 0u;
  }
}

static void record_event(struct vos_pool *pool, enum vos_pool_event_kind kind,
                         uint64_t a0, uint64_t a1, uint64_t a2, uint64_t a3, uint64_t a4)
{
  if (pool->event_count < VOS_POOL_MAX_HISTORY) {
    struct vos_pool_event *ev = &pool->events[pool->event_count++];
    ev->kind = kind;
    ev->a0 = a0;
    ev->a1 = a1;
    ev->a2 = a2;
    ev->a3 = a3;
    ev->a4 = a4;
  } else {
    ++pool->event_dropped;
  }
}

static enum vos_pool_status check_parent(const struct vos_pool *pool)
{
  const struct vos_pool *cur = pool;
  for (uint32_t depth = 0u; depth < VOS_POOL_MAX_SLOTS; ++depth) {
    if (cur->parent == 0) {
      return VOS_POOL_OK;
    }
    if (vos_pool_grant_live(cur->parent, &cur->parent_grant, 0) != VOS_POOL_OK) {
      return VOS_POOL_ERR_PARENT_DEAD;
    }
    cur = cur->parent;
  }
  return VOS_POOL_ERR_PARENT_DEAD;
}

uint64_t vos_pool_representable_granule(uint64_t length)
{
  if (length < 128u) {
    return 1u;
  }
  uint64_t g = 1u;
  for (uint32_t bit = 0u; bit < 57u; ++bit) {
    if (g > (UINT64_MAX / 128u)) {
      break;
    }
    if ((128u * g) <= length) {
      g *= 2u;
    } else {
      break;
    }
  }
  return g;
}

int vos_pool_size_class_exact(const struct vos_pool_size_class *sc)
{
  if (sc == 0 || sc->length == 0u || sc->alignment == 0u) {
    return 0;
  }
  const uint64_t g = vos_pool_representable_granule(sc->length);
  if (sc->granule != 0u && sc->granule != g) {
    return 0;
  }
  return (sc->length % g) == 0u && (sc->alignment % g) == 0u;
}

uint64_t vos_pool_narrow_length(const struct vos_pool_size_class *sc, uint64_t requested)
{
  if (sc == 0 || requested == 0u || requested > sc->length || sc->granule == 0u) {
    return 0u;
  }
  const uint64_t g = sc->granule;
  const uint64_t r = requested % g;
  if (r == 0u) {
    return requested;
  }
  if (requested > UINT64_MAX - (g - r)) {
    return 0u;
  }
  const uint64_t rounded = requested + (g - r);
  if (rounded > sc->length) {
    return 0u;
  }
  return rounded;
}

static int revocable_interval_ok(const struct vos_pool_interval *iv)
{
  if (iv == 0 || iv->span == 0u || iv->base > UINT64_MAX - iv->span) {
    return 0;
  }
  return (iv->base % VOS_POOL_ROT_UNION_ALIGN) == 0u &&
         ((iv->base + iv->span) % VOS_POOL_ROT_UNION_ALIGN) == 0u;
}

enum vos_pool_status vos_pool_plan_validate(const struct vos_pool_plan *plan)
{
  if (plan == 0 || plan->span == 0u || plan->base > UINT64_MAX - plan->span ||
      plan->class_count == 0u || plan->class_count > VOS_POOL_MAX_CLASSES ||
      plan->slot_count == 0u || plan->slot_count > VOS_POOL_MAX_SLOTS ||
      plan->revocable_count > VOS_POOL_MAX_REV_INTERVALS) {
    return VOS_POOL_ERR_SHAPE;
  }
  for (uint32_t i = 0u; i < plan->class_count; ++i) {
    if (!vos_pool_size_class_exact(&plan->classes[i])) {
      return VOS_POOL_ERR_INEXACT_CLASS;
    }
  }
  if (plan->revocable_count > 0u) {
    int contained = 0;
    for (uint32_t i = 0u; i < plan->revocable_count; ++i) {
      const struct vos_pool_interval *iv = &plan->revocable[i];
      if (revocable_interval_ok(iv) && iv->base <= plan->base &&
          (plan->base + plan->span) <= (iv->base + iv->span)) {
        contained = 1;
        break;
      }
    }
    if (!contained) {
      return VOS_POOL_ERR_REVOCABLE_UNION;
    }
  }
  uint64_t total_len = 0u;
  const uint64_t arena_top = plan->base + plan->span;
  for (uint32_t i = 0u; i < plan->slot_count; ++i) {
    const struct vos_pool_slot_layout *sl = &plan->slots[i];
    if (sl->cls >= plan->class_count) {
      return VOS_POOL_ERR_SHAPE;
    }
    const struct vos_pool_size_class *sc = &plan->classes[sl->cls];
    if (sl->base > UINT64_MAX - sc->length) {
      return VOS_POOL_ERR_OUTSIDE_ARENA;
    }
    const uint64_t top = sl->base + sc->length;
    if ((sl->base % sc->alignment) != 0u) {
      return VOS_POOL_ERR_UNALIGNED;
    }
    if (sl->base < plan->base || top > arena_top) {
      return VOS_POOL_ERR_OUTSIDE_ARENA;
    }
    if (total_len > UINT64_MAX - sc->length) {
      return VOS_POOL_ERR_ALLOWANCE;
    }
    total_len += sc->length;
  }
  if (plan->quarantine_allowance < total_len) {
    return VOS_POOL_ERR_ALLOWANCE;
  }
  for (uint32_t i = 0u; i < plan->slot_count; ++i) {
    const uint64_t b1 = plan->slots[i].base;
    const uint64_t l1 = plan->classes[plan->slots[i].cls].length;
    for (uint32_t j = i + 1u; j < plan->slot_count; ++j) {
      const uint64_t b2 = plan->slots[j].base;
      const uint64_t l2 = plan->classes[plan->slots[j].cls].length;
      if (extents_overlap(b1, l1, b2, l2)) {
        return VOS_POOL_ERR_OVERLAP;
      }
      if (!extents_granules_disjoint(b1, l1, b2, l2)) {
        return VOS_POOL_ERR_SHARED_GRANULE;
      }
    }
  }
  return VOS_POOL_OK;
}

enum vos_pool_status vos_pool_init(struct vos_pool *pool, const struct vos_pool_plan *plan,
                                   uint8_t *backing, uint64_t backing_len, uint64_t issuer_id)
{
  if (pool == 0 || plan == 0 || backing == 0 || issuer_id == 0u) {
    return VOS_POOL_ERR_INVALID;
  }
  const enum vos_pool_status st = vos_pool_plan_validate(plan);
  if (st != VOS_POOL_OK) {
    return st;
  }
  if (backing_len < plan->span) {
    return VOS_POOL_ERR_SHAPE;
  }
  pool->plan = *plan;
  for (uint32_t i = 0u; i < pool->plan.class_count; ++i) {
    if (pool->plan.classes[i].granule == 0u) {
      pool->plan.classes[i].granule =
          vos_pool_representable_granule(pool->plan.classes[i].length);
    }
  }
  pool->backing = backing;
  pool->backing_len = backing_len;
  pool->sweep_active = 0u;
  pool->serial = 0u;
  pool->epoch = 0u;
  pool->issuer_id = issuer_id;
  pool->holder_count = 0u;
  pool->event_count = 0u;
  pool->event_dropped = 0u;
  pool->parent = 0;
  pool->parent_grant = (struct vos_pool_grant){0};
  pool->effects = 0;
  pool->effect_members = 0u;
  for (uint32_t i = 0u; i < VOS_POOL_MAX_SLOTS; ++i) {
    pool->slots[i] = (struct vos_pool_slot){0};
  }
  for (uint32_t i = 0u; i < VOS_POOL_MAX_HOLDERS; ++i) {
    pool->holders[i] = (struct vos_pool_holder){0};
  }
  return VOS_POOL_OK;
}

enum vos_pool_status vos_pool_bind_effects(struct vos_pool *pool,
                                           struct vos_kernel_effect_state *effects,
                                           uint32_t members)
{
  if (pool == 0 || effects == 0 || !effects->bound || members == 0u ||
      members != effects->manifest.restart_members) {
    return VOS_POOL_ERR_INVALID;
  }
  pool->effects = effects;
  pool->effect_members = members;
  pool->epoch = effects->epoch;
  return VOS_POOL_OK;
}

enum vos_pool_status vos_pool_grant_live(const struct vos_pool *pool,
                                         const struct vos_pool_grant *grant,
                                         uint32_t *out_slot_index)
{
  if (pool == 0 || grant == 0) {
    return VOS_POOL_ERR_INVALID;
  }
  const enum vos_pool_status pst = check_parent(pool);
  if (pst != VOS_POOL_OK) {
    return pst;
  }
  if (grant->issuer_id != pool->issuer_id || grant->slot >= pool->plan.slot_count) {
    return VOS_POOL_ERR_STALE_OR_FOREIGN;
  }
  const struct vos_pool_slot *sl = &pool->slots[grant->slot];
  if (sl->phase != VOS_SLOT_LIVE || sl->grant.holder != grant->holder ||
      sl->grant.slot != grant->slot || sl->grant.base != grant->base ||
      sl->grant.length != grant->length || sl->grant.serial != grant->serial ||
      sl->grant.generation != grant->generation ||
      sl->grant.issuer_id != grant->issuer_id) {
    return VOS_POOL_ERR_STALE_OR_FOREIGN;
  }
  if (out_slot_index != 0) {
    *out_slot_index = grant->slot;
  }
  return VOS_POOL_OK;
}

static enum vos_pool_status alloc_impl(struct vos_pool *pool, uint32_t holder, uint32_t cls,
                                       uint32_t launch_island, uint64_t requested_len,
                                       int narrow, struct vos_pool_grant *out_grant)
{
  if (pool == 0 || out_grant == 0) {
    return VOS_POOL_ERR_INVALID;
  }
  const enum vos_pool_status pst = check_parent(pool);
  if (pst != VOS_POOL_OK) {
    return pst;
  }
  if (launch_island != pool->plan.island) {
    return VOS_POOL_ERR_FOREIGN_ISLAND;
  }
  if (cls >= pool->plan.class_count) {
    return VOS_POOL_ERR_SHAPE;
  }
  const struct vos_pool_size_class *sc = &pool->plan.classes[cls];
  uint64_t grant_len = sc->length;
  if (narrow) {
    grant_len = vos_pool_narrow_length(sc, requested_len);
    if (grant_len == 0u) {
      return VOS_POOL_ERR_OUT_OF_RANGE;
    }
  }
  for (uint32_t i = 0u; i < pool->plan.slot_count; ++i) {
    if (pool->plan.slots[i].cls == cls && pool->slots[i].phase == VOS_SLOT_FREE) {
      if (pool->serial == UINT64_MAX || pool->slots[i].generation == UINT64_MAX) {
        return VOS_POOL_ERR_SERIAL_EXHAUSTED;
      }
      const uint64_t base = pool->plan.slots[i].base;
      const uint64_t offset = base - pool->plan.base;
      zero_bytes(pool->backing + offset, sc->length);
      ++pool->serial;
      ++pool->slots[i].generation;
      const struct vos_pool_grant g = {
        .holder = holder,
        .slot = i,
        .base = base,
        .length = grant_len,
        .serial = pool->serial,
        .generation = pool->slots[i].generation,
        .issuer_id = pool->issuer_id
      };
      pool->slots[i].phase = VOS_SLOT_LIVE;
      pool->slots[i].grant = g;
      pool->slots[i].in_sweep = 0u;
      pool->slots[i].has_child = 0u;
      pool->slots[i].zeroed = 1u;
      record_event(pool, VOS_PEV_ZERO, base, sc->length, 0u, 0u, 0u);
      record_event(pool, VOS_PEV_GRANT, holder, cls, base, base, grant_len);
      *out_grant = g;
      return VOS_POOL_OK;
    }
  }
  return VOS_POOL_ERR_EXHAUSTED;
}

enum vos_pool_status vos_pool_alloc(struct vos_pool *pool, uint32_t holder, uint32_t cls,
                                    uint32_t launch_island, struct vos_pool_grant *out_grant)
{
  return alloc_impl(pool, holder, cls, launch_island, 0u, 0, out_grant);
}

enum vos_pool_status vos_pool_alloc_narrowed(struct vos_pool *pool, uint32_t holder, uint32_t cls,
                                             uint32_t launch_island, uint64_t requested_len,
                                             struct vos_pool_grant *out_grant)
{
  return alloc_impl(pool, holder, cls, launch_island, requested_len, 1, out_grant);
}

enum vos_pool_status vos_pool_write(struct vos_pool *pool, const struct vos_pool_grant *grant,
                                    uint64_t offset, uint8_t value)
{
  uint32_t slot_idx = 0u;
  const enum vos_pool_status gst = vos_pool_grant_live(pool, grant, &slot_idx);
  if (gst != VOS_POOL_OK) {
    return gst;
  }
  if (pool->slots[slot_idx].has_child) {
    return VOS_POOL_ERR_HEAP_OWNED;
  }
  if (offset >= grant->length) {
    return VOS_POOL_ERR_OUT_OF_RANGE;
  }
  const uint64_t backing_offset = (grant->base - pool->plan.base) + offset;
  pool->backing[backing_offset] = value;
  pool->slots[slot_idx].zeroed = 0u;
  record_event(pool, VOS_PEV_WRITE, grant->base + offset, value, 0u, 0u, 0u);
  return VOS_POOL_OK;
}

enum vos_pool_status vos_pool_read(const struct vos_pool *pool, const struct vos_pool_grant *grant,
                                   uint64_t offset, uint8_t *out_value)
{
  if (out_value == 0) {
    return VOS_POOL_ERR_INVALID;
  }
  uint32_t slot_idx = 0u;
  const enum vos_pool_status gst = vos_pool_grant_live(pool, grant, &slot_idx);
  if (gst != VOS_POOL_OK) {
    return gst;
  }
  if (offset >= grant->length) {
    return VOS_POOL_ERR_OUT_OF_RANGE;
  }
  const uint64_t backing_offset = (grant->base - pool->plan.base) + offset;
  *out_value = pool->backing[backing_offset];
  return VOS_POOL_OK;
}

static enum vos_pool_status insert_holder(struct vos_pool *pool, uint32_t id,
                                          enum vos_holder_kind kind, uint64_t cap_base,
                                          uint64_t cap_length)
{
  for (uint32_t i = 0u; i < pool->holder_count; ++i) {
    if (pool->holders[i].active && pool->holders[i].id == id) {
      pool->holders[i].kind = kind;
      pool->holders[i].cap_base = cap_base;
      pool->holders[i].cap_length = cap_length;
      return VOS_POOL_OK;
    }
  }
  for (uint32_t i = 0u; i < pool->holder_count; ++i) {
    if (!pool->holders[i].active) {
      pool->holders[i] = (struct vos_pool_holder){
        .id = id,
        .kind = kind,
        .active = 1u,
        .cap_base = cap_base,
        .cap_length = cap_length
      };
      return VOS_POOL_OK;
    }
  }
  if (pool->holder_count >= VOS_POOL_MAX_HOLDERS) {
    return VOS_POOL_ERR_CAPACITY;
  }
  pool->holders[pool->holder_count++] = (struct vos_pool_holder){
    .id = id,
    .kind = kind,
    .active = 1u,
    .cap_base = cap_base,
    .cap_length = cap_length
  };
  return VOS_POOL_OK;
}

enum vos_pool_status vos_pool_release(struct vos_pool *pool, const struct vos_pool_grant *grant)
{
  uint32_t slot_idx = 0u;
  const enum vos_pool_status gst = vos_pool_grant_live(pool, grant, &slot_idx);
  if (gst != VOS_POOL_OK) {
    return gst;
  }
  if (pool->epoch == UINT64_MAX) {
    return VOS_POOL_ERR_EPOCH_EXHAUSTED;
  }
  const uint32_t cls = pool->plan.slots[slot_idx].cls;
  const uint64_t slot_len = pool->plan.classes[cls].length;
  const enum vos_pool_status hst =
      insert_holder(pool, slot_idx, VOS_HOLDER_REG, grant->base, slot_len);
  if (hst != VOS_POOL_OK) {
    return hst;
  }
  ++pool->epoch;
  pool->slots[slot_idx].phase = VOS_SLOT_PENDING;
  record_event(pool, VOS_PEV_RELEASE, grant->base, cls, 0u, 0u, 0u);
  return VOS_POOL_OK;
}

enum vos_pool_status vos_pool_add_holder(struct vos_pool *pool, uint32_t id,
                                         enum vos_holder_kind kind, uint64_t cap_base,
                                         uint64_t cap_length)
{
  if (pool == 0 || cap_length == 0u || cap_base > UINT64_MAX - cap_length) {
    return VOS_POOL_ERR_INVALID;
  }
  const enum vos_pool_status pst = check_parent(pool);
  if (pst != VOS_POOL_OK) {
    return pst;
  }
  return insert_holder(pool, id, kind, cap_base, cap_length);
}

enum vos_pool_status vos_pool_clear_holder(struct vos_pool *pool, uint32_t id)
{
  if (pool == 0) {
    return VOS_POOL_ERR_INVALID;
  }
  const enum vos_pool_status pst = check_parent(pool);
  if (pst != VOS_POOL_OK) {
    return pst;
  }
  for (uint32_t i = 0u; i < pool->holder_count; ++i) {
    if (pool->holders[i].active && pool->holders[i].id == id) {
      pool->holders[i].active = 0u;
      pool->holders[i].cap_base = 0u;
      pool->holders[i].cap_length = 0u;
    }
  }
  return VOS_POOL_OK;
}

enum vos_pool_status vos_pool_clear_registers(struct vos_pool *pool, uint32_t slot_index)
{
  if (pool == 0) {
    return VOS_POOL_ERR_INVALID;
  }
  const enum vos_pool_status pst = check_parent(pool);
  if (pst != VOS_POOL_OK) {
    return pst;
  }
  if (slot_index >= pool->plan.slot_count) {
    return VOS_POOL_ERR_OUT_OF_RANGE;
  }
  if (pool->slots[slot_index].phase != VOS_SLOT_PENDING) {
    return VOS_POOL_ERR_NO_PENDING;
  }
  const uint64_t s_base = pool->plan.slots[slot_index].base;
  const uint64_t s_len = pool->plan.classes[pool->plan.slots[slot_index].cls].length;
  for (uint32_t i = 0u; i < pool->holder_count; ++i) {
    struct vos_pool_holder *h = &pool->holders[i];
    if (h->active && h->kind == VOS_HOLDER_REG &&
        extents_overlap(h->cap_base, h->cap_length, s_base, s_len)) {
      h->active = 0u;
      h->cap_base = 0u;
      h->cap_length = 0u;
    }
  }
  return VOS_POOL_OK;
}

int vos_pool_no_holder_for_pending(const struct vos_pool *pool)
{
  if (pool == 0) {
    return 0;
  }
  for (uint32_t s = 0u; s < pool->plan.slot_count; ++s) {
    if (pool->slots[s].phase != VOS_SLOT_PENDING) {
      continue;
    }
    const uint64_t s_base = pool->plan.slots[s].base;
    const uint64_t s_len = pool->plan.classes[pool->plan.slots[s].cls].length;
    for (uint32_t h = 0u; h < pool->holder_count; ++h) {
      const struct vos_pool_holder *he = &pool->holders[h];
      if (!he->active) {
        continue;
      }
      if (he->kind == VOS_HOLDER_REG &&
          extents_overlap(he->cap_base, he->cap_length, s_base, s_len)) {
        return 0;
      }
      if (he->kind == VOS_HOLDER_SAVED_CTX &&
          extents_overlap(he->cap_base, he->cap_length, s_base, s_len)) {
        return 0;
      }
      if (he->kind == VOS_HOLDER_STORED_CELL &&
          extents_overlap(he->cap_base, he->cap_length, s_base, s_len)) {
        return 0;
      }
    }
  }
  return 1;
}

enum vos_pool_status vos_pool_barrier(struct vos_pool *pool)
{
  if (pool == 0) {
    return VOS_POOL_ERR_INVALID;
  }
  const enum vos_pool_status pst = check_parent(pool);
  if (pst != VOS_POOL_OK) {
    return pst;
  }
  uint32_t pending_count = 0u;
  for (uint32_t i = 0u; i < pool->plan.slot_count; ++i) {
    if (pool->slots[i].phase == VOS_SLOT_PENDING) {
      ++pending_count;
    }
  }
  if (pending_count == 0u) {
    return VOS_POOL_ERR_NO_PENDING;
  }
  if (!vos_pool_no_holder_for_pending(pool)) {
    return VOS_POOL_ERR_HOLDER_ACTIVE;
  }
  if (pool->effects != 0) {
    const uint64_t mask = vos_kernel_retirement_mask(pool->effects, pool->effect_members);
    if (mask == 0u) {
      return VOS_POOL_ERR_BARRIER_INCOMPLETE;
    }
    *pool->effects->bitmap |= mask;
    if (!vos_kernel_publication(pool->effects, pool->effects->epoch, mask,
                                *pool->effects->bitmap)) {
      return VOS_POOL_ERR_BARRIER_INCOMPLETE;
    }
    struct vos_completion done = {0};
    if (!vos_kernel_retire(pool->effects, pool->effect_members, &done) ||
        !vos_semantic_completion(&done)) {
      return VOS_POOL_ERR_BARRIER_INCOMPLETE;
    }
    pool->epoch = pool->effects->epoch;
  }
  for (uint32_t i = 0u; i < pool->plan.slot_count; ++i) {
    if (pool->slots[i].phase == VOS_SLOT_PENDING) {
      pool->slots[i].phase = VOS_SLOT_BARRIER;
      pool->slots[i].in_sweep = 0u;
    }
  }
  record_event(pool, VOS_PEV_BARRIER_DONE, 0u, 0u, 0u, 0u, 0u);
  return VOS_POOL_OK;
}

enum vos_pool_status vos_pool_sweep_begin(struct vos_pool *pool)
{
  if (pool == 0) {
    return VOS_POOL_ERR_INVALID;
  }
  const enum vos_pool_status pst = check_parent(pool);
  if (pst != VOS_POOL_OK) {
    return pst;
  }
  if (pool->sweep_active) {
    return VOS_POOL_ERR_SWEEP_ACTIVE;
  }
  uint32_t barrier_count = 0u;
  for (uint32_t i = 0u; i < pool->plan.slot_count; ++i) {
    if (pool->slots[i].phase == VOS_SLOT_BARRIER) {
      ++barrier_count;
    }
  }
  if (barrier_count == 0u) {
    return VOS_POOL_ERR_NO_BARRIER;
  }
  for (uint32_t i = 0u; i < pool->plan.slot_count; ++i) {
    if (pool->slots[i].phase == VOS_SLOT_BARRIER) {
      pool->slots[i].phase = VOS_SLOT_SWEEPING;
      pool->slots[i].in_sweep = 1u;
    }
  }
  pool->sweep_active = 1u;
  record_event(pool, VOS_PEV_SWEEP_BEGIN, 0u, 0u, 0u, 0u, 0u);
  return VOS_POOL_OK;
}

enum vos_pool_status vos_pool_sweep_end(struct vos_pool *pool)
{
  if (pool == 0) {
    return VOS_POOL_ERR_INVALID;
  }
  const enum vos_pool_status pst = check_parent(pool);
  if (pst != VOS_POOL_OK) {
    return pst;
  }
  if (!pool->sweep_active) {
    return VOS_POOL_ERR_NO_SWEEP;
  }
  for (uint32_t i = 0u; i < pool->plan.slot_count; ++i) {
    if (pool->slots[i].phase == VOS_SLOT_SWEEPING && pool->slots[i].in_sweep) {
      pool->slots[i].phase = VOS_SLOT_FREE;
      pool->slots[i].grant = (struct vos_pool_grant){0};
      pool->slots[i].in_sweep = 0u;
      pool->slots[i].has_child = 0u;
      pool->slots[i].zeroed = 0u;
    }
  }
  pool->sweep_active = 0u;
  record_event(pool, VOS_PEV_SWEEP_END, 0u, 0u, 0u, 0u, 0u);
  return VOS_POOL_OK;
}

enum vos_pool_status vos_pool_heap_init(struct vos_pool *parent,
                                        const struct vos_pool_grant *parent_grant,
                                        struct vos_pool *child,
                                        const struct vos_pool_size_class *classes,
                                        uint32_t class_count,
                                        const struct vos_pool_slot_layout *slots,
                                        uint32_t slot_count, uint64_t issuer_id)
{
  if (parent == 0 || parent_grant == 0 || child == 0 || classes == 0 || slots == 0 ||
      class_count == 0u || class_count > VOS_POOL_MAX_CLASSES ||
      slot_count == 0u || slot_count > VOS_POOL_MAX_SLOTS ||
      issuer_id == 0u || issuer_id == parent->issuer_id) {
    return VOS_POOL_ERR_INVALID;
  }
  uint32_t slot_idx = 0u;
  const enum vos_pool_status gst = vos_pool_grant_live(parent, parent_grant, &slot_idx);
  if (gst != VOS_POOL_OK) {
    return gst;
  }
  if (parent->slots[slot_idx].has_child) {
    return VOS_POOL_ERR_CHILD_EXISTS;
  }
  struct vos_pool_plan cplan = {0};
  cplan.island = parent->plan.island;
  cplan.memory_class = parent->plan.memory_class;
  cplan.base = parent_grant->base;
  cplan.span = parent_grant->length;
  cplan.class_count = class_count;
  for (uint32_t i = 0u; i < class_count; ++i) {
    cplan.classes[i] = classes[i];
  }
  cplan.slot_count = slot_count;
  for (uint32_t i = 0u; i < slot_count; ++i) {
    cplan.slots[i] = slots[i];
  }
  cplan.quarantine_allowance = parent_grant->length;
  const uint64_t offset = parent_grant->base - parent->plan.base;
  const enum vos_pool_status ist =
      vos_pool_init(child, &cplan, parent->backing + offset, parent_grant->length, issuer_id);
  if (ist != VOS_POOL_OK) {
    return ist;
  }
  child->parent = parent;
  child->parent_grant = *parent_grant;
  parent->slots[slot_idx].has_child = 1u;
  return VOS_POOL_OK;
}

enum vos_pool_status vos_domain_pools_init(struct vos_domain_pools *domain,
                                           const struct vos_domain_pool_binding *bindings,
                                           uint32_t pool_count,
                                           const struct vos_domain_launch *launches,
                                           uint32_t member_count)
{
  if (domain == 0 || bindings == 0 || launches == 0 ||
      pool_count == 0u || pool_count > VOS_POOL_MAX_POOLS ||
      member_count == 0u || member_count > VOS_POOL_MAX_MEMBERS) {
    return VOS_POOL_ERR_SHAPE;
  }
  for (uint32_t i = 0u; i < pool_count; ++i) {
    const struct vos_pool *p = bindings[i].pool;
    if (p == 0) {
      return VOS_POOL_ERR_INVALID;
    }
    const enum vos_pool_status pst = vos_pool_plan_validate(&p->plan);
    if (pst != VOS_POOL_OK) {
      return pst;
    }
    if (bindings[i].island != p->plan.island ||
        bindings[i].memory_class != p->plan.memory_class) {
      return VOS_POOL_ERR_FOREIGN_ISLAND;
    }
  }
  for (uint32_t i = 0u; i < pool_count; ++i) {
    const struct vos_pool *pi = bindings[i].pool;
    for (uint32_t j = i + 1u; j < pool_count; ++j) {
      const struct vos_pool *pj = bindings[j].pool;
      if (bindings[i].island == bindings[j].island &&
          bindings[i].memory_class == bindings[j].memory_class) {
        return VOS_POOL_ERR_OVERLAP;
      }
      if (extents_overlap(pi->plan.base, pi->plan.span, pj->plan.base, pj->plan.span)) {
        return VOS_POOL_ERR_OVERLAP;
      }
      if (!extents_granules_disjoint(pi->plan.base, pi->plan.span,
                                     pj->plan.base, pj->plan.span)) {
        return VOS_POOL_ERR_SHARED_GRANULE;
      }
    }
  }
  for (uint32_t m = 0u; m < member_count; ++m) {
    for (uint32_t n = m + 1u; n < member_count; ++n) {
      if (launches[m].member == launches[n].member) {
        return VOS_POOL_ERR_SHAPE;
      }
    }
    const uint32_t isl = launches[m].island;
    for (uint32_t c = 0u; c < pool_count; ++c) {
      const uint32_t mc = bindings[c].memory_class;
      int found = 0;
      for (uint32_t k = 0u; k < pool_count; ++k) {
        if (bindings[k].island == isl && bindings[k].memory_class == mc) {
          found = 1;
          break;
        }
      }
      if (!found) {
        return VOS_POOL_ERR_MISSING_POOL;
      }
    }
  }
  domain->pool_count = pool_count;
  for (uint32_t i = 0u; i < pool_count; ++i) {
    domain->pools[i] = bindings[i];
  }
  domain->member_count = member_count;
  for (uint32_t i = 0u; i < member_count; ++i) {
    domain->launches[i] = launches[i];
  }
  return VOS_POOL_OK;
}

enum vos_pool_status vos_domain_pools_allocate(struct vos_domain_pools *domain, uint32_t holder,
                                               uint32_t memory_class, uint32_t cls,
                                               struct vos_pool_grant *out_grant)
{
  if (domain == 0 || out_grant == 0) {
    return VOS_POOL_ERR_INVALID;
  }
  int found_member = 0;
  uint32_t island = 0u;
  for (uint32_t i = 0u; i < domain->member_count; ++i) {
    if (domain->launches[i].member == holder) {
      found_member = 1;
      island = domain->launches[i].island;
      break;
    }
  }
  if (!found_member) {
    return VOS_POOL_ERR_FOREIGN_ISLAND;
  }
  for (uint32_t i = 0u; i < domain->pool_count; ++i) {
    if (domain->pools[i].island == island &&
        domain->pools[i].memory_class == memory_class) {
      return vos_pool_alloc(domain->pools[i].pool, holder, cls, island, out_grant);
    }
  }
  return VOS_POOL_ERR_MISSING_POOL;
}
