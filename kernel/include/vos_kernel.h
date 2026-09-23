// SPDX-License-Identifier: Apache-2.0
/*
 * One isolated kernel instance: the partition context and its switch, the
 * table-driven cyclic executive, and the consumer checks over the composed
 * initialization descriptor. Authored against proofs/PartitionContext.v,
 * proofs/CyclicExecutive.v and proofs/KernelInstance.v (M4.1b: authored
 * instead; nothing here derives from seL4 or CHERI-seL4).
 *
 * GC-free by construction: every object is a fixed-size record, every table
 * has a composition-fixed capacity, no function allocates, and no loop is
 * unbounded. The scalar source profile of the contained compiler applies:
 * no pointer/integer conversion, no union, no floating point, no varargs.
 *
 * Every magnitude the register leaves to composition is a record field here,
 * as it is in the Gallina statements. The VOS_MAX_* capacities bound the
 * records; they are not composition choices and a descriptor that needs more
 * is refused.
 */
#ifndef VOS_KERNEL_H
#define VOS_KERNEL_H 1

#include <stdint.h>

#include "vos_platform.h"

/* R-15-007i: one merged file of 32 registers of 64+1 bits. */
#define VOS_REGISTER_COUNT 32u

#define VOS_MAX_SLOTS 16u
#define VOS_MAX_CSRS 16u
#define VOS_MAX_PARTITIONS 8u
#define VOS_MAX_WINDOWS 4u

/* slot_index_at's `None`: no slot owns the instant (R-07-036). */
#define VOS_NO_SLOT (-1)

/* Every refusal a consumer check can return. Zero is acceptance. */
enum vos_status {
  VOS_OK = 0,
  VOS_TABLE_EMPTY = 1,
  VOS_TABLE_TOO_LARGE = 2,
  VOS_TABLE_NO_FOCUS = 3,
  VOS_TABLE_ZERO_FRAME = 4,
  VOS_TABLE_ZERO_WIDTH = 5,
  VOS_TABLE_OVERFLOW = 6,
  VOS_TABLE_OUTSIDE_FRAME = 7,
  VOS_TABLE_OVERLAP = 8,
  VOS_TABLE_UNORDERED = 9,
  VOS_INIT_MISSING = 10,
  VOS_INIT_WRONG_COMPOSITION = 11,
  VOS_INIT_WRONG_HART = 12,
  VOS_INIT_TOO_MANY_PARTITIONS = 13,
  VOS_INIT_NO_PLANNED_SUCCESSOR = 14,
  VOS_INIT_EXTENT_MALFORMED = 15,
  VOS_INIT_EXTENT_OUTSIDE_ROOT = 16,
  VOS_INIT_EXTENTS_UNREADABLE = 17,
  VOS_INIT_TOO_MANY_WINDOWS = 18,
  VOS_ROSTER_TOO_LARGE = 19,
  VOS_DISPATCH_STALE_IMAGE = 20
};

/* ------------------------------------------------------------------------
 * The schedule table (CyclicExecutive.v `Slot`, `Band`, `Frame`).
 *
 * `slots` is `frame_slots`: the reserved band first, then the band's focus,
 * then its background slots, in that list order. `reserved_count` slots are
 * the reserved band, so the focus is slots[reserved_count].
 * ------------------------------------------------------------------------ */

struct vos_slot {
  uint64_t width;
  uint64_t offset;
  uint64_t bound;  /* R-11-015's declared in-slot bound; admission's, not read here */
  uint64_t period; /* R-11-006's declared visit period; admission's, not read here */
  uint32_t tenant;
};

struct vos_frame {
  uint64_t major_frame;  /* R-11-014d */
  uint64_t phase_offset; /* R-11-014a */
  uint32_t reserved_count;
  uint32_t slot_count;
  struct vos_slot slots[VOS_MAX_SLOTS];
};

/* The executive's whole state: which major frame and which table entry.
 * There is no priority, budget or ready set to consult (R-07-032). */
struct vos_exec {
  uint64_t frame_index;
  uint32_t cursor;
};

int vos_slot_disjoint(const struct vos_slot *s, const struct vos_slot *t);
int vos_slot_in_frame(const struct vos_slot *s, uint64_t major_frame);
int vos_frame_pairwise_disjoint(const struct vos_frame *f);
uint64_t vos_frame_total_width(const struct vos_frame *f);
int32_t vos_slot_index_at(const struct vos_frame *f, uint64_t instant);
enum vos_status vos_frame_validate(const struct vos_frame *f);

void vos_exec_start(struct vos_exec *e);
uint32_t vos_exec_slot(const struct vos_exec *e);
uint32_t vos_exec_tenant(const struct vos_frame *f, const struct vos_exec *e);
uint64_t vos_exec_release(const struct vos_frame *f, const struct vos_exec *e);
void vos_exec_advance(const struct vos_frame *f, struct vos_exec *e);

/* ------------------------------------------------------------------------
 * The partition context (PartitionContext.v `Machine`, `Context`).
 *
 * The CSR bank enters as a roster, KernelInstance.v reading 4: the switch
 * must write every nameable CSR, and a predicate cannot be walked. The
 * roster is a composition input; no artifact in the tree enumerates it
 * (KernelInstance.v gap b), so this code never names a CSR itself.
 * ------------------------------------------------------------------------ */

struct vos_csr_row {
  uint32_t csr;      /* the CSR address, as the restore stub names it */
  uint8_t nameable;  /* R-07-015's "a partition can name" */
  uint8_t zeroized;  /* isa-profile.md section 5.1's "zeroizes and does not save" */
};

struct vos_machine {
  uint32_t csr_count;
  struct vos_csr_row roster[VOS_MAX_CSRS];
  uint8_t pending_swapped;        /* R-07-044's arm: 1 swapped, 0 static */
  uint8_t rotation_swaps_pending; /* R-07-037c on the swapping arm */
  uint64_t pending_static_mask;   /* the static arm's partition of the file */
};

/* One context. `csr` is indexed by roster position, not by CSR address. */
struct vos_context {
  vos_cap_t reg[VOS_REGISTER_COUNT];
  uint64_t csr[VOS_MAX_CSRS];
  uint64_t pending;
};

enum vos_status vos_machine_validate(const struct vos_machine *m);
uint64_t vos_pending_written(const struct vos_machine *m, const struct vos_context *succ);
void vos_switch_image(const struct vos_machine *m, const struct vos_context *succ,
                      const struct vos_context *pre, struct vos_context *post);
void vos_rotation_image(const struct vos_machine *m, const struct vos_context *succ,
                        const struct vos_context *pre, struct vos_context *post);

/* ------------------------------------------------------------------------
 * The revocation join (KernelInstance.v's R1 to R7; Q22a).
 * ------------------------------------------------------------------------ */

struct vos_completion {
  uint8_t bits_published;
  uint8_t epoch_advanced; /* recorded; deliberately not a conjunct (R-08-006) */
  uint8_t resident_roots_cleared;
  uint8_t saved_contexts_filtered;
  uint8_t loans_cancelled;
  uint8_t device_boundary_reached;
};

int vos_semantic_completion(const struct vos_completion *c);

#if defined(VOS_HOST_MODEL)
/* The observation half needs a register's tag and base, which on the target
 * are the model's decode reached through primitives this profile has not
 * yet bound (kernel/README.md). The host model supplies both. */
int vos_filtered_tag(const struct vos_bitmap *bm, vos_cap_t c);
int vos_image_sanitized(const struct vos_bitmap *bm, const struct vos_context *succ);
enum vos_status vos_dispatch_check(const struct vos_bitmap *bm,
                                   const struct vos_context *succ);
#endif

/* ------------------------------------------------------------------------
 * The composed initialization descriptor (purecap-abi.md section 7, `c12`)
 * and the partition root handling it carries.
 * ------------------------------------------------------------------------ */

struct vos_extent {
  uint64_t base;
  uint64_t top;
};

struct vos_partition_desc {
  uint32_t tenant;
  uint32_t has_context; /* a planned save area and initial image exist */
  struct vos_extent text;
  struct vos_extent data;
};

struct vos_init_desc {
  uint64_t composition_id;
  uint64_t hart_id;
  struct vos_extent root;        /* the partition-bounded root's declared extent */
  struct vos_extent switch_text; /* the kernel's own switch text */
  uint32_t partition_count;
  struct vos_partition_desc partitions[VOS_MAX_PARTITIONS];
  uint32_t window_count;
  struct vos_extent windows[VOS_MAX_WINDOWS];
  struct vos_frame frame;
  struct vos_machine machine;
};

int vos_extent_within(const struct vos_extent *e, uint64_t address);
int vos_extent_equal(const struct vos_extent *a, const struct vos_extent *b);
int vos_extent_separated(const struct vos_extent *a, const struct vos_extent *b);
int vos_extent_compatible(const struct vos_extent *a, const struct vos_extent *b);
int vos_extent_contains(const struct vos_extent *outer, const struct vos_extent *inner);
int32_t vos_partition_index(const struct vos_init_desc *d, uint32_t tenant);
int vos_extents_readable(const struct vos_init_desc *d);
enum vos_status vos_init_validate(const struct vos_init_desc *d, uint64_t composition_id,
                                  uint64_t hart_id);

#endif
