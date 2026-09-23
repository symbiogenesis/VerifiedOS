// SPDX-License-Identifier: Apache-2.0
/*
 * A single translation unit for the program-level compiler loop: the kernel
 * sources in their target build (no VOS_HOST_MODEL, so a saved register is a
 * pointer-typed capability slot), driven by a `main` whose return names the
 * first check that failed, on the corpus convention.
 *
 * It is a smoke of the kernel C under the contained compiler, not a kernel
 * instance: there is no firmware handoff, no trap entry, no dispatch and no
 * partition. `run.py compiler-diff program` supplies a test harness around it
 * (a bounded stack and `tohost`), and a green run says only that this program
 * and this machine agree under that harness.
 *
 * Every object is a local of `main` and every field is written before it is
 * read: the scalar source profile admits no aggregate global and no read of an
 * uninitialized value, and there is no libc to zero a record with.
 *
 * Build: pass the kernel's include and source directories to the compiler,
 * for example `--ccomp-arg=-I<checkout>/kernel/include`
 * `--ccomp-arg=-I<checkout>/kernel/src`.
 */
#define VOS_TARGET_SLOT long *

#include "vos_kernel.h"

#include "context.c"
#include "executive.c"
#include "partition.c"

static void clear_extent(struct vos_extent *e)
{
  e->base = 0;
  e->top = 0;
}

static void clear_context(struct vos_context *c)
{
  uint32_t i;
  for (i = 0; i < VOS_REGISTER_COUNT; i++) {
    c->reg[i] = 0;
  }
  for (i = 0; i < VOS_MAX_CSRS; i++) {
    c->csr[i] = 0;
  }
  c->pending = 0;
}

static void clear_descriptor(struct vos_init_desc *d)
{
  uint32_t i;
  d->composition_id = 0;
  d->hart_id = 0;
  clear_extent(&d->root);
  clear_extent(&d->switch_text);
  d->partition_count = 0;
  for (i = 0; i < VOS_MAX_PARTITIONS; i++) {
    d->partitions[i].tenant = 0;
    d->partitions[i].has_context = 0;
    clear_extent(&d->partitions[i].text);
    clear_extent(&d->partitions[i].data);
  }
  d->window_count = 0;
  for (i = 0; i < VOS_MAX_WINDOWS; i++) {
    clear_extent(&d->windows[i]);
  }
  d->frame.major_frame = 0;
  d->frame.phase_offset = 0;
  d->frame.reserved_count = 0;
  d->frame.slot_count = 0;
  for (i = 0; i < VOS_MAX_SLOTS; i++) {
    d->frame.slots[i].width = 0;
    d->frame.slots[i].offset = 0;
    d->frame.slots[i].bound = 0;
    d->frame.slots[i].period = 0;
    d->frame.slots[i].tenant = 0;
  }
  d->machine.csr_count = 0;
  for (i = 0; i < VOS_MAX_CSRS; i++) {
    d->machine.roster[i].csr = i;
    d->machine.roster[i].nameable = 0;
    d->machine.roster[i].zeroized = 0;
  }
  d->machine.pending_swapped = 0;
  d->machine.rotation_swaps_pending = 0;
  d->machine.pending_static_mask = 0;
}

static void set_extent(struct vos_extent *e, uint64_t base, uint64_t top)
{
  e->base = base;
  e->top = top;
}

static void set_slot(struct vos_slot *s, uint64_t width, uint64_t offset, uint32_t tenant)
{
  s->width = width;
  s->offset = offset;
  s->tenant = tenant;
}

static void describe(struct vos_init_desc *d)
{
  clear_descriptor(d);
  d->composition_id = 7;
  set_extent(&d->root, 1000, 2000);
  set_extent(&d->switch_text, 10, 20);
  d->partition_count = 2;
  d->partitions[0].tenant = 0;
  d->partitions[0].has_context = 1;
  set_extent(&d->partitions[0].text, 1000, 1100);
  set_extent(&d->partitions[0].data, 1100, 1200);
  d->partitions[1].tenant = 1;
  d->partitions[1].has_context = 1;
  set_extent(&d->partitions[1].text, 1200, 1300);
  set_extent(&d->partitions[1].data, 1300, 1400);
  d->frame.major_frame = 200;
  d->frame.reserved_count = 1;
  d->frame.slot_count = 3;
  set_slot(&d->frame.slots[0], 60, 0, 0);
  set_slot(&d->frame.slots[1], 90, 60, 1);
  set_slot(&d->frame.slots[2], 50, 150, 0);
  d->machine.csr_count = 3;
  d->machine.roster[0].nameable = 1;
  d->machine.roster[1].nameable = 1;
  d->machine.roster[1].zeroized = 1;
  d->machine.pending_swapped = 1;
  d->machine.rotation_swaps_pending = 1;
}

int main(void)
{
  struct vos_init_desc desc;
  struct vos_context succ;
  struct vos_context pre;
  struct vos_context post;
  struct vos_exec e;
  long cells[VOS_REGISTER_COUNT];
  uint32_t r;
  describe(&desc);
  if (vos_init_validate(&desc, 7, 0) != VOS_OK) {
    return 1;
  }
  if (vos_init_validate(&desc, 7, 1) != VOS_INIT_WRONG_HART) {
    return 2;
  }
  if (vos_slot_index_at(&desc.frame, 155) != 2 || vos_slot_index_at(&desc.frame, 200) != VOS_NO_SLOT) {
    return 3;
  }
  vos_exec_start(&e);
  vos_exec_advance(&desc.frame, &e);
  vos_exec_advance(&desc.frame, &e);
  vos_exec_advance(&desc.frame, &e);
  if (e.frame_index != 1u || vos_exec_release(&desc.frame, &e) != 200u) {
    return 4;
  }
  /* Register 0 stays the null slot; every other slot holds a capability to its
   * own cell. The copies must keep each one's authority: a dropped tag makes the
   * store below fault rather than return a wrong answer. */
  clear_context(&succ);
  clear_context(&pre);
  clear_context(&post);
  cells[0] = 0;
  for (r = 1u; r < VOS_REGISTER_COUNT; r++) {
    cells[r] = (long)r;
    succ.reg[r] = &cells[r];
  }
  succ.csr[0] = 5;
  succ.csr[1] = 6;
  succ.csr[2] = 7;
  pre.csr[2] = 9;
  succ.pending = 3;
  vos_switch_image(&desc.machine, &succ, &pre, &post);
  /* Each restored slot is used as the authority it was saved as. The profile's
   * typed check admits no comparison of a pointer reloaded from a slot with a
   * fresh address (kernel/README.md), so identity is observed through the
   * cells each store reaches rather than by comparing pointers. */
  for (r = 1u; r < VOS_REGISTER_COUNT; r++) {
    long *cell = post.reg[r];
    *cell = *cell + 100;
  }
  for (r = 1u; r < VOS_REGISTER_COUNT; r++) {
    if (cells[r] != (long)r + 100) {
      return 5;
    }
  }
  if (post.csr[0] != 5u || post.csr[1] != 0u || post.csr[2] != 9u || post.pending != 3u) {
    return 6;
  }
  return 0;
}
