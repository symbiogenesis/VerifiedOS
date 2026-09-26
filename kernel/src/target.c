// SPDX-License-Identifier: Apache-2.0
/* C-side preparation and table cursor for the C-class entry adapter.
 * This boundary does not authenticate a measured descriptor or inspect a
 * capability. Firmware and the entry adapter own those prerequisites. */
#include "vos_target.h"

int vos_target_prepare(const uint8_t *boot, const uint8_t *init,
                       size_t boot_bytes, size_t init_bytes,
                       struct vos_target_state *state, size_t state_bytes,
                       uint64_t composition, uint64_t hart)
{
  struct vos_target_state candidate;
  enum vos_status init_status;
  if (state == 0 || state_bytes < sizeof(*state)) {
    return VOS_TARGET_STORAGE_SMALL;
  }
  /* The final restore transfer prefix is exactly the merged file, not a
   * guessed host struct layout. Verify this build's target ABI before the
   * assembly adapter supplies these C records. */
  if (sizeof(vos_cap_t) != 8u || offsetof(struct vos_context, reg) != 0u ||
      offsetof(struct vos_context, csr) != 256u || sizeof(struct vos_context) > 320u) {
    return VOS_TARGET_NONSCALAR;
  }
  if (vos_boot_record_decode(boot, boot_bytes, &candidate.boot) != VOS_DECODE_OK) {
    return VOS_TARGET_BOOT_REFUSED;
  }
  if (vos_init_decode(init, init_bytes, composition, hart,
                      &candidate.handoff, &init_status) != VOS_DECODE_OK) {
    return VOS_TARGET_INIT_REFUSED;
  }
  /* The final restore emitter supports a scalar class with no reachable CSR.
   * Nonempty pending state has no target binding in this adapter. Refuse it
   * explicitly instead of silently discarding composition inputs. */
  if (candidate.handoff.init.machine.csr_count != 0u ||
      candidate.handoff.init.machine.pending_swapped != 0u ||
      candidate.handoff.init.machine.rotation_swaps_pending != 0u ||
      candidate.handoff.init.machine.pending_static_mask != 0u) {
    return VOS_TARGET_NONSCALAR;
  }
  vos_exec_start(&candidate.executive);
  *state = candidate;
  return VOS_TARGET_OK;
}

uint32_t vos_target_tenant(const struct vos_target_state *state)
{
  return vos_exec_tenant(&state->handoff.init.frame, &state->executive);
}

uint64_t vos_target_release(const struct vos_target_state *state)
{
  return vos_exec_release(&state->handoff.init.frame, &state->executive);
}

void vos_target_advance(struct vos_target_state *state)
{
  vos_exec_advance(&state->handoff.init.frame, &state->executive);
}

void vos_target_switch(const struct vos_target_state *state,
                       const struct vos_context *successor,
                       const struct vos_context *previous,
                       struct vos_context *output)
{
  vos_switch_image(&state->handoff.init.machine, successor, previous, output);
}
