// SPDX-License-Identifier: Apache-2.0
/*
 * Original GC-free C17 elastic pool service and default member heap library
 * (Q34c-ii-a), authored against [ElasticPool.v](../../proofs/ElasticPool.v)
 * and [elastic_pool.py](../../tools/vos/elastic_pool.py).
 *
 * Incorporates no CheriBSD or upstream allocator code. Every structure has a
 * composition-fixed capacity, caller-supplied backing storage, bounded loops,
 * and zero dynamic allocation.
 */
#ifndef VOS_ELASTIC_POOL_H
#define VOS_ELASTIC_POOL_H 1

#include <stdint.h>

#include "vos_effects.h"

#define VOS_POOL_STD_CLASS_COUNT 13u
#define VOS_POOL_REV_GRANULE 8u
#define VOS_POOL_ROT_UNION_ALIGN 64u

#ifndef VOS_POOL_MAX_CLASSES
#define VOS_POOL_MAX_CLASSES 16u
#endif

#ifndef VOS_POOL_MAX_SLOTS
#define VOS_POOL_MAX_SLOTS 64u
#endif

#ifndef VOS_POOL_MAX_HOLDERS
#define VOS_POOL_MAX_HOLDERS 64u
#endif

#ifndef VOS_POOL_MAX_HISTORY
#define VOS_POOL_MAX_HISTORY 256u
#endif

#ifndef VOS_POOL_MAX_POOLS
#define VOS_POOL_MAX_POOLS 16u
#endif

#ifndef VOS_POOL_MAX_MEMBERS
#define VOS_POOL_MAX_MEMBERS 32u
#endif

#ifndef VOS_POOL_MAX_REV_INTERVALS
#define VOS_POOL_MAX_REV_INTERVALS 16u
#endif

enum vos_pool_status {
  VOS_POOL_OK = 0,
  VOS_POOL_ERR_INVALID = 1,
  VOS_POOL_ERR_SHAPE = 2,
  VOS_POOL_ERR_INEXACT_CLASS = 3,
  VOS_POOL_ERR_ALLOWANCE = 4,
  VOS_POOL_ERR_UNALIGNED = 5,
  VOS_POOL_ERR_OUTSIDE_ARENA = 6,
  VOS_POOL_ERR_OVERLAP = 7,
  VOS_POOL_ERR_SHARED_GRANULE = 8,
  VOS_POOL_ERR_REVOCABLE_UNION = 9,
  VOS_POOL_ERR_FOREIGN_ISLAND = 10,
  VOS_POOL_ERR_EXHAUSTED = 11,
  VOS_POOL_ERR_EPOCH_EXHAUSTED = 12,
  VOS_POOL_ERR_SERIAL_EXHAUSTED = 13,
  VOS_POOL_ERR_STALE_OR_FOREIGN = 14,
  VOS_POOL_ERR_HEAP_OWNED = 15,
  VOS_POOL_ERR_OUT_OF_RANGE = 16,
  VOS_POOL_ERR_NO_PENDING = 17,
  VOS_POOL_ERR_HOLDER_ACTIVE = 18,
  VOS_POOL_ERR_BARRIER_INCOMPLETE = 19,
  VOS_POOL_ERR_SWEEP_ACTIVE = 20,
  VOS_POOL_ERR_NO_BARRIER = 21,
  VOS_POOL_ERR_NO_SWEEP = 22,
  VOS_POOL_ERR_PARENT_DEAD = 23,
  VOS_POOL_ERR_CHILD_EXISTS = 24,
  VOS_POOL_ERR_MISSING_POOL = 25,
  VOS_POOL_ERR_CAPACITY = 26
};

enum vos_slot_phase {
  VOS_SLOT_FREE = 0,
  VOS_SLOT_LIVE = 1,
  VOS_SLOT_PENDING = 2,
  VOS_SLOT_BARRIER = 3,
  VOS_SLOT_SWEEPING = 4
};

enum vos_holder_kind {
  VOS_HOLDER_REG = 0,
  VOS_HOLDER_SAVED_CTX = 1,
  VOS_HOLDER_STORED_CELL = 2
};

enum vos_pool_event_kind {
  VOS_PEV_ZERO = 0,
  VOS_PEV_GRANT = 1,
  VOS_PEV_WRITE = 2,
  VOS_PEV_RELEASE = 3,
  VOS_PEV_BARRIER_DONE = 4,
  VOS_PEV_SWEEP_BEGIN = 5,
  VOS_PEV_SWEEP_END = 6
};

struct vos_pool_size_class {
  uint64_t length;
  uint64_t alignment;
  uint64_t granule;
};

extern const struct vos_pool_size_class vos_pool_std_classes[VOS_POOL_STD_CLASS_COUNT];

struct vos_pool_slot_layout {
  uint64_t base;
  uint32_t cls;
};

struct vos_pool_interval {
  uint64_t base;
  uint64_t span;
};

struct vos_pool_plan {
  uint32_t island;
  uint32_t memory_class;
  uint64_t base;
  uint64_t span;
  uint32_t class_count;
  struct vos_pool_size_class classes[VOS_POOL_MAX_CLASSES];
  uint32_t slot_count;
  struct vos_pool_slot_layout slots[VOS_POOL_MAX_SLOTS];
  uint64_t quarantine_allowance;
  uint32_t revocable_count;
  struct vos_pool_interval revocable[VOS_POOL_MAX_REV_INTERVALS];
};

struct vos_pool_grant {
  uint32_t holder;
  uint32_t slot;
  uint64_t base;
  uint64_t length;
  uint64_t serial;
  uint64_t generation;
  uint64_t issuer_id;
};

struct vos_pool_holder {
  uint32_t id;
  enum vos_holder_kind kind;
  uint8_t active;
  uint64_t cap_base;
  uint64_t cap_length;
};

struct vos_pool_event {
  enum vos_pool_event_kind kind;
  uint64_t a0;
  uint64_t a1;
  uint64_t a2;
  uint64_t a3;
  uint64_t a4;
};

struct vos_pool_slot {
  enum vos_slot_phase phase;
  struct vos_pool_grant grant;
  uint64_t generation;
  uint8_t in_sweep;
  uint8_t has_child;
  uint8_t zeroed;
};

struct vos_pool {
  struct vos_pool_plan plan;
  uint8_t *backing;
  uint64_t backing_len;
  struct vos_pool_slot slots[VOS_POOL_MAX_SLOTS];
  uint8_t sweep_active;
  uint64_t serial;
  uint64_t epoch;
  uint64_t issuer_id;
  uint32_t holder_count;
  struct vos_pool_holder holders[VOS_POOL_MAX_HOLDERS];
  uint32_t event_count;
  uint32_t event_dropped;
  struct vos_pool_event events[VOS_POOL_MAX_HISTORY];
  struct vos_pool *parent;
  struct vos_pool_grant parent_grant;
  struct vos_kernel_effect_state *effects;
  uint32_t effect_members;
};

struct vos_domain_pool_binding {
  uint32_t island;
  uint32_t memory_class;
  struct vos_pool *pool;
};

struct vos_domain_launch {
  uint32_t member;
  uint32_t island;
};

struct vos_domain_pools {
  uint32_t pool_count;
  struct vos_domain_pool_binding pools[VOS_POOL_MAX_POOLS];
  uint32_t member_count;
  struct vos_domain_launch launches[VOS_POOL_MAX_MEMBERS];
};

/* Admission-time representable granule and class exactness (R-15-007k). */
uint64_t vos_pool_representable_granule(uint64_t length);
int vos_pool_size_class_exact(const struct vos_pool_size_class *sc);
enum vos_pool_status vos_pool_plan_validate(const struct vos_pool_plan *plan);

/* Exact granule narrowing for positive requested lengths without runtime CRRL/CRAM. */
uint64_t vos_pool_narrow_length(const struct vos_pool_size_class *sc, uint64_t requested);

/* Pool lifecycle. Caller owns `backing` of `plan->span` bytes. */
enum vos_pool_status vos_pool_init(struct vos_pool *pool, const struct vos_pool_plan *plan,
                                   uint8_t *backing, uint64_t backing_len, uint64_t issuer_id);

/* Bind M4.4 single-hart kernel effect primitives to barrier completion. */
enum vos_pool_status vos_pool_bind_effects(struct vos_pool *pool,
                                           struct vos_kernel_effect_state *effects,
                                           uint32_t members);

/* Allocation, narrowed sub-allocation, checked read/write, and liveness. */
enum vos_pool_status vos_pool_grant_live(const struct vos_pool *pool,
                                         const struct vos_pool_grant *grant,
                                         uint32_t *out_slot_index);
enum vos_pool_status vos_pool_alloc(struct vos_pool *pool, uint32_t holder, uint32_t cls,
                                    uint32_t launch_island, struct vos_pool_grant *out_grant);
enum vos_pool_status vos_pool_alloc_narrowed(struct vos_pool *pool, uint32_t holder, uint32_t cls,
                                             uint32_t launch_island, uint64_t requested_len,
                                             struct vos_pool_grant *out_grant);
enum vos_pool_status vos_pool_write(struct vos_pool *pool, const struct vos_pool_grant *grant,
                                    uint64_t offset, uint8_t value);
enum vos_pool_status vos_pool_read(const struct vos_pool *pool, const struct vos_pool_grant *grant,
                                   uint64_t offset, uint8_t *out_value);

/* 5-phase two-generation quarantine and holder-map barrier. */
enum vos_pool_status vos_pool_release(struct vos_pool *pool, const struct vos_pool_grant *grant);
enum vos_pool_status vos_pool_add_holder(struct vos_pool *pool, uint32_t id,
                                         enum vos_holder_kind kind, uint64_t cap_base,
                                         uint64_t cap_length);
enum vos_pool_status vos_pool_clear_holder(struct vos_pool *pool, uint32_t id);
enum vos_pool_status vos_pool_clear_registers(struct vos_pool *pool, uint32_t slot_index);
int vos_pool_no_holder_for_pending(const struct vos_pool *pool);
enum vos_pool_status vos_pool_barrier(struct vos_pool *pool);
enum vos_pool_status vos_pool_sweep_begin(struct vos_pool *pool);
enum vos_pool_status vos_pool_sweep_end(struct vos_pool *pool);

/* Nested member heap sharing parent backing bytes and bound to parent grant lifetime. */
enum vos_pool_status vos_pool_heap_init(struct vos_pool *parent,
                                        const struct vos_pool_grant *parent_grant,
                                        struct vos_pool *child,
                                        const struct vos_pool_size_class *classes,
                                        uint32_t class_count,
                                        const struct vos_pool_slot_layout *slots,
                                        uint32_t slot_count, uint64_t issuer_id);

/* Per-domain multi-island pool registry and launch-island binding (R-08-047a). */
enum vos_pool_status vos_domain_pools_init(struct vos_domain_pools *domain,
                                           const struct vos_domain_pool_binding *bindings,
                                           uint32_t pool_count,
                                           const struct vos_domain_launch *launches,
                                           uint32_t member_count);
enum vos_pool_status vos_domain_pools_allocate(struct vos_domain_pools *domain, uint32_t holder,
                                               uint32_t memory_class, uint32_t cls,
                                               struct vos_pool_grant *out_grant);

#endif
