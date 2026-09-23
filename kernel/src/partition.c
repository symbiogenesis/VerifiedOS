// SPDX-License-Identifier: Apache-2.0
/*
 * Partition root handling over the composed initialization descriptor.
 *
 * purecap-abi.md section 7 hands the kernel, at its first C instruction, a
 * read-only root-set table in `c10`, the boot descriptor in `c11` and this
 * descriptor in `c12`. The consumer obligations it states are the ones below:
 * a missing descriptor, a wrong-composition or wrong-hart descriptor, and an
 * initialization lacking a planned successor are refused before any dispatch,
 * as producer/consumer checks and not as capability faults.
 *
 * What is deliberately not here. R-07-005 makes composition-time disjointness
 * a build-time artifact, so these checks re-read declared extents for the
 * consumer's own consistency and are not that artifact. R-07-006's runtime
 * half is CHERI monotonicity itself: the extents below are declarations and
 * never a decode of a capability's bounds (KernelInstance.v reading 1), so no
 * check here stands in for the in-program derivation attempts a run makes.
 */
#include "vos_kernel.h"

/* KernelInstance.v `within`. */
int vos_extent_within(const struct vos_extent *e, uint64_t address)
{
  return e->base <= address && address < e->top;
}

/* KernelInstance.v `extent_eqb`. */
int vos_extent_equal(const struct vos_extent *a, const struct vos_extent *b)
{
  return a->base == b->base && a->top == b->top;
}

/* KernelInstance.v `separated`. */
int vos_extent_separated(const struct vos_extent *a, const struct vos_extent *b)
{
  return a->top <= b->base || b->top <= a->base;
}

/* KernelInstance.v `compatible`: two slots of one tenant declare one extent. */
int vos_extent_compatible(const struct vos_extent *a, const struct vos_extent *b)
{
  return vos_extent_equal(a, b) || vos_extent_separated(a, b);
}

int vos_extent_contains(const struct vos_extent *outer, const struct vos_extent *inner)
{
  return outer->base <= inner->base && inner->top <= outer->top;
}

static int vos_extent_well_formed(const struct vos_extent *e)
{
  return e->base < e->top;
}

int32_t vos_partition_index(const struct vos_init_desc *d, uint32_t tenant)
{
  uint32_t i;
  for (i = 0; i < d->partition_count && i < VOS_MAX_PARTITIONS; i++) {
    if (d->partitions[i].tenant == tenant) {
      return (int32_t)i;
    }
  }
  return -1;
}

/* The partition declaring a slot's tenant, as an index, or -1. An index
 * rather than an optional pointer: the contained compiler's typed check
 * refuses a pointer result that is null on one path and an address on
 * another (kernel/README.md). */
static int32_t vos_slot_partition(const struct vos_init_desc *d, uint32_t slot)
{
  return vos_partition_index(d, d->frame.slots[slot].tenant);
}

/*
 * KernelInstance.v `ExtentsAreReadable` over the table's declared extents:
 * each pair of slot extents is one extent or does not meet, and the switch
 * text meets none of them, so a retired instruction's `pc` names one site.
 * A slot whose tenant no partition declares has no extent and is unreadable.
 */
int vos_extents_readable(const struct vos_init_desc *d)
{
  uint32_t i;
  uint32_t j;
  for (i = 0; i < d->frame.slot_count && i < VOS_MAX_SLOTS; i++) {
    int32_t a = vos_slot_partition(d, i);
    if (a < 0) {
      return 0;
    }
    if (!vos_extent_separated(&d->switch_text, &d->partitions[a].text)) {
      return 0;
    }
    for (j = i + 1u; j < d->frame.slot_count && j < VOS_MAX_SLOTS; j++) {
      int32_t b = vos_slot_partition(d, j);
      if (b < 0) {
        return 0;
      }
      if (!vos_extent_compatible(&d->partitions[a].text, &d->partitions[b].text)) {
        return 0;
      }
    }
  }
  return 1;
}

enum vos_status vos_init_validate(const struct vos_init_desc *d, uint64_t composition_id,
                                  uint64_t hart_id)
{
  uint32_t i;
  enum vos_status table;
  if (d == 0) {
    return VOS_INIT_MISSING;
  }
  if (d->composition_id != composition_id) {
    return VOS_INIT_WRONG_COMPOSITION;
  }
  if (d->hart_id != hart_id) {
    return VOS_INIT_WRONG_HART;
  }
  if (d->partition_count > VOS_MAX_PARTITIONS) {
    return VOS_INIT_TOO_MANY_PARTITIONS;
  }
  if (d->window_count > VOS_MAX_WINDOWS) {
    return VOS_INIT_TOO_MANY_WINDOWS;
  }
  if (vos_machine_validate(&d->machine) != VOS_OK) {
    return VOS_ROSTER_TOO_LARGE;
  }
  table = vos_frame_validate(&d->frame);
  if (table != VOS_OK) {
    return table;
  }
  if (!vos_extent_well_formed(&d->root) || !vos_extent_well_formed(&d->switch_text)) {
    return VOS_INIT_EXTENT_MALFORMED;
  }
  for (i = 0; i < d->window_count; i++) {
    if (!vos_extent_well_formed(&d->windows[i])) {
      return VOS_INIT_EXTENT_MALFORMED;
    }
  }
  for (i = 0; i < d->partition_count; i++) {
    const struct vos_partition_desc *p = &d->partitions[i];
    if (!vos_extent_well_formed(&p->text) || !vos_extent_well_formed(&p->data)) {
      return VOS_INIT_EXTENT_MALFORMED;
    }
    if (!vos_extent_contains(&d->root, &p->text) || !vos_extent_contains(&d->root, &p->data)) {
      return VOS_INIT_EXTENT_OUTSIDE_ROOT;
    }
  }
  /* Every table entry must name a partition with a planned save area and
   * initial image: the successor of every boundary exists before the first
   * dispatch, which is the ABI's "initialization lacking a planned successor". */
  for (i = 0; i < d->frame.slot_count; i++) {
    int32_t p = vos_partition_index(d, d->frame.slots[i].tenant);
    if (p < 0 || !d->partitions[p].has_context) {
      return VOS_INIT_NO_PLANNED_SUCCESSOR;
    }
  }
  if (!vos_extents_readable(d)) {
    return VOS_INIT_EXTENTS_UNREADABLE;
  }
  return VOS_OK;
}
