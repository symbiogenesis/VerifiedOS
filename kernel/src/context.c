// SPDX-License-Identifier: Apache-2.0
/*
 * The partition context and the image a switch installs, authored against
 * proofs/PartitionContext.v, and the revocation join of proofs/KernelInstance.v.
 *
 * `vos_switch_image` is the post-state R-07-015's total restore writes:
 * every one of the 32 merged registers, value and tag together; every CSR
 * the partition can name, restored or written to zero by the profile's own
 * disposition; and R-07-044's pending component on either arm. It is the
 * restore plan the switch text executes, not the instruction sequence: C
 * cannot place values into x1 to x31 or order a total restore, and no
 * emitter yet owns the sequence of `lc` loads, CSR writes, `vmclear`,
 * `fence.t` and the dispatching `mret` (kernel/README.md), so nothing here
 * claims one.
 *
 * `vos_rotation_image` is R-07-037b's intra-slot step between members of one
 * same-label group: the same register swap and restorable-CSR restore, the
 * zeroized class left where the omitted pass leaves it (R-07-037d), and the
 * pending component swapped only on R-07-037c's arm. R-07-037g's elastic
 * step, which runs `vmclear` whenever the two members belong to different
 * applications, is not this function and is not implemented; nor does
 * PartitionContext.v's `Rotation` state that cross-application clear.
 */
#include "vos_kernel.h"

enum vos_status vos_machine_validate(const struct vos_machine *m)
{
  if (m->csr_count > VOS_MAX_CSRS) {
    return VOS_ROSTER_TOO_LARGE;
  }
  return VOS_OK;
}

/* PartitionContext.v `pending_written`: a function of the successor alone
 * on either arm. */
uint64_t vos_pending_written(const struct vos_machine *m, const struct vos_context *succ)
{
  if (m->pending_swapped) {
    return succ->pending;
  }
  return succ->pending & m->pending_static_mask;
}

/* The whole register file, index zero included: PartitionContext.v's
 * `RestoresRegisters` quantifies over all 32, and the save area carries the
 * zero register's null slot like any other. Each slot moves whole. */
static void vos_copy_registers(const struct vos_context *succ, struct vos_context *post)
{
  uint32_t r;
  for (r = 0; r < VOS_REGISTER_COUNT; r++) {
    post->reg[r] = succ->reg[r];
  }
}

void vos_switch_image(const struct vos_machine *m, const struct vos_context *succ,
                      const struct vos_context *pre, struct vos_context *post)
{
  uint32_t i;
  vos_copy_registers(succ, post);
  for (i = 0; i < VOS_MAX_CSRS; i++) {
    post->csr[i] = pre->csr[i];
  }
  for (i = 0; i < m->csr_count && i < VOS_MAX_CSRS; i++) {
    const struct vos_csr_row *row = &m->roster[i];
    if (row->nameable) {
      if (row->zeroized) {
        post->csr[i] = 0;
      } else {
        post->csr[i] = succ->csr[i];
      }
    }
  }
  post->pending = vos_pending_written(m, succ);
}

void vos_rotation_image(const struct vos_machine *m, const struct vos_context *succ,
                        const struct vos_context *pre, struct vos_context *post)
{
  uint32_t i;
  vos_copy_registers(succ, post);
  for (i = 0; i < VOS_MAX_CSRS; i++) {
    post->csr[i] = pre->csr[i];
  }
  for (i = 0; i < m->csr_count && i < VOS_MAX_CSRS; i++) {
    const struct vos_csr_row *row = &m->roster[i];
    if (row->nameable && !row->zeroized) {
      post->csr[i] = succ->csr[i];
    }
  }
  if (m->rotation_swaps_pending) {
    post->pending = vos_pending_written(m, succ);
  } else {
    post->pending = pre->pending;
  }
}

/* KernelInstance.v `SemanticCompletion`: R-08-006's five conditions. The
 * epoch is carried and read by nothing, that entry's own sentence being that
 * advancing it does not establish containment. */
int vos_semantic_completion(const struct vos_completion *c)
{
  return c->bits_published && c->resident_roots_cleared && c->saved_contexts_filtered
         && c->loans_cancelled && c->device_boundary_reached;
}

#if defined(VOS_HOST_MODEL)

int vos_cap_tag(vos_cap_t c)
{
  return c.tag != 0u;
}

uint64_t vos_cap_base(vos_cap_t c)
{
  return c.value;
}

int vos_bitmap_marks(const struct vos_bitmap *bm, uint64_t base)
{
  if (base >= 64u) {
    return 0;
  }
  return ((bm->marked >> base) & 1u) != 0u;
}

/* KernelInstance.v `filtered`: R-08-005b's load result, the tag cleared where
 * the loaded capability's base is marked. On the target this is what the
 * capability load does to every restored slot. */
int vos_filtered_tag(const struct vos_bitmap *bm, vos_cap_t c)
{
  return vos_cap_tag(c) && !vos_bitmap_marks(bm, vos_cap_base(c));
}

/* KernelInstance.v `ImageIsSanitized` over the witnessed registers, 1 to 31. */
int vos_image_sanitized(const struct vos_bitmap *bm, const struct vos_context *succ)
{
  uint32_t r;
  for (r = 1u; r < VOS_REGISTER_COUNT; r++) {
    if (vos_cap_tag(succ->reg[r]) && vos_bitmap_marks(bm, vos_cap_base(succ->reg[r]))) {
      return 0;
    }
  }
  return 1;
}

/*
 * The dispatch-side reading of the revocation join. A saved image the
 * barrier did not sanitize is refused rather than dispatched: restored
 * through the filtered load it stops satisfying R-07-015's total restore,
 * and restored faithfully it is stale authority (KernelInstance.v R4, R5).
 * Only on a sanitized image are the two arms one restore (R6).
 *
 * This takes KernelInstance.v gap a's barrier-sanitizes arm, which the
 * register leaves open (owed at R-08-006 or R-07-015). What follows a
 * refusal, whether the slot idles, the partition restarts or the kernel
 * fails, is not specified, and the check exists in the host model only.
 */
enum vos_status vos_dispatch_check(const struct vos_bitmap *bm,
                                   const struct vos_context *succ)
{
  if (!vos_image_sanitized(bm, succ)) {
    return VOS_DISPATCH_STALE_IMAGE;
  }
  return VOS_OK;
}

#endif
