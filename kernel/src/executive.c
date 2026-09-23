// SPDX-License-Identifier: Apache-2.0
/*
 * The table-driven static cyclic executive (R-07-032), authored against
 * proofs/CyclicExecutive.v and the frame clause of proofs/KernelInstance.v.
 *
 * What runs is a pure function of the table and a cursor. There is no
 * priority, no ready set, no budget and no occupancy input anywhere below, so
 * a runtime scheduling decision has nothing to read (R-07-032, R-07-036).
 * Admission itself, the interval arithmetic with the switch duty inside it,
 * is R-11-006's Coq artifact and is decided at composition; the checks here
 * are the consumer's structural checks on the table it is handed before its
 * first dispatch (purecap-abi.md section 7, gap k).
 *
 * One table, one tenant per slot. R-11-023's slot-to-tenant permutation,
 * R-11-024's table swap, R-07-037b's group rotation and R-07-037g's elastic
 * dispatch are executive duties this file does not implement.
 */
#include "vos_kernel.h"

/* CyclicExecutive.v `disjoint`: one slot ends at or before the other begins. */
int vos_slot_disjoint(const struct vos_slot *s, const struct vos_slot *t)
{
  if (s->offset + s->width <= t->offset) {
    return 1;
  }
  if (t->offset + t->width <= s->offset) {
    return 1;
  }
  return 0;
}

/* The first conjunct `slot_fits` reads: the slot ends within the major frame. */
int vos_slot_in_frame(const struct vos_slot *s, uint64_t major_frame)
{
  return s->offset + s->width <= major_frame;
}

/* CyclicExecutive.v `pairwise_disjoint` over `frame_slots`. Each loop here
 * also stops at the record's capacity, so an unvalidated count cannot read
 * past `slots`. */
int vos_frame_pairwise_disjoint(const struct vos_frame *f)
{
  uint32_t i;
  uint32_t j;
  for (i = 0; i < f->slot_count && i < VOS_MAX_SLOTS; i++) {
    for (j = i + 1u; j < f->slot_count && j < VOS_MAX_SLOTS; j++) {
      if (!vos_slot_disjoint(&f->slots[i], &f->slots[j])) {
        return 0;
      }
    }
  }
  return 1;
}

/* CyclicExecutive.v `total_width` over `frame_slots`. */
uint64_t vos_frame_total_width(const struct vos_frame *f)
{
  uint64_t total = 0;
  uint32_t i;
  for (i = 0; i < f->slot_count && i < VOS_MAX_SLOTS; i++) {
    total += f->slots[i].width;
  }
  return total;
}

/*
 * CyclicExecutive.v `slot_index_at (frame_slots f) 0 t`: the first slot, in
 * list order, whose half-open interval holds the instant. An instant no slot
 * holds answers VOS_NO_SLOT, and nothing is lent across it (R-07-036).
 */
int32_t vos_slot_index_at(const struct vos_frame *f, uint64_t instant)
{
  uint32_t i;
  for (i = 0; i < f->slot_count && i < VOS_MAX_SLOTS; i++) {
    const struct vos_slot *s = &f->slots[i];
    if (s->offset <= instant && instant < s->offset + s->width) {
      return (int32_t)i;
    }
  }
  return VOS_NO_SLOT;
}

/*
 * The consumer's structural checks, in the order a reader would diagnose
 * them. Two are this kernel's rather than admission's and are stated as such
 * in kernel/README.md: a zero-width slot, which the time-to-slot map can never
 * select, and a list order that is not the time order, which would make the
 * table's own sequence (KernelInstance.v `SwitchesInTableOrder`, read in list
 * order) disagree with the instants the executive releases slots at.
 */
enum vos_status vos_frame_validate(const struct vos_frame *f)
{
  uint32_t i;
  if (f->slot_count == 0u) {
    return VOS_TABLE_EMPTY;
  }
  if (f->slot_count > VOS_MAX_SLOTS) {
    return VOS_TABLE_TOO_LARGE;
  }
  if (f->reserved_count >= f->slot_count) {
    return VOS_TABLE_NO_FOCUS;
  }
  if (f->major_frame == 0u) {
    return VOS_TABLE_ZERO_FRAME;
  }
  for (i = 0; i < f->slot_count; i++) {
    const struct vos_slot *s = &f->slots[i];
    if (s->width == 0u) {
      return VOS_TABLE_ZERO_WIDTH;
    }
    if (s->offset + s->width < s->offset) {
      return VOS_TABLE_OVERFLOW;
    }
    if (!vos_slot_in_frame(s, f->major_frame)) {
      return VOS_TABLE_OUTSIDE_FRAME;
    }
  }
  if (!vos_frame_pairwise_disjoint(f)) {
    return VOS_TABLE_OVERLAP;
  }
  for (i = 1u; i < f->slot_count; i++) {
    if (f->slots[i].offset <= f->slots[i - 1u].offset) {
      return VOS_TABLE_UNORDERED;
    }
  }
  return VOS_OK;
}

/* The cursor below reads `slots[cursor]` and wraps at `slot_count`: its
 * frame must have passed vos_frame_validate (vos_kernel.h). */
void vos_exec_start(struct vos_exec *e)
{
  e->frame_index = 0;
  e->cursor = 0;
}

uint32_t vos_exec_slot(const struct vos_exec *e)
{
  return e->cursor;
}

uint32_t vos_exec_tenant(const struct vos_frame *f, const struct vos_exec *e)
{
  return f->slots[e->cursor].tenant;
}

/*
 * The table instant the current entry is released at: the core's one phase
 * offset (R-11-014a), whole major frames of the one length (R-11-014d), and
 * the slot's own offset. The successor's first instruction follows at this
 * instant plus R-07-040's padded boundary constant, which the boundary
 * handler waits out on `mtime`; neither term reads the predecessor.
 */
uint64_t vos_exec_release(const struct vos_frame *f, const struct vos_exec *e)
{
  return f->phase_offset + e->frame_index * f->major_frame + f->slots[e->cursor].offset;
}

/* The next entry is the next row of the table, wrapping into the next major
 * frame. The only input is the cursor. */
void vos_exec_advance(const struct vos_frame *f, struct vos_exec *e)
{
  uint32_t next = e->cursor + 1u;
  if (next >= f->slot_count) {
    e->cursor = 0;
    e->frame_index = e->frame_index + 1u;
  } else {
    e->cursor = next;
  }
}
