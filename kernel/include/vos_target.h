// SPDX-License-Identifier: Apache-2.0
#ifndef VOS_TARGET_H
#define VOS_TARGET_H 1

#include "vos_handoff.h"

/* Storage is supplied by the composed kernel data region. No pointer to the
 * firmware's descriptors survives preparation. Assembly supplies the byte
 * lengths only after inspecting the actual read-only input capabilities. */
struct vos_target_state {
  struct vos_boot_record boot;
  struct vos_init_handoff handoff;
  struct vos_exec executive;
};

enum vos_target_status {
  VOS_TARGET_OK = 0,
  VOS_TARGET_BOOT_REFUSED = 1,
  VOS_TARGET_INIT_REFUSED = 2,
  VOS_TARGET_STORAGE_SMALL = 3,
  VOS_TARGET_NONSCALAR = 4
};

int vos_target_prepare(const uint8_t *boot, const uint8_t *init,
                       size_t boot_bytes, size_t init_bytes,
                       struct vos_target_state *state, size_t state_bytes,
                       uint64_t composition, uint64_t hart);
uint32_t vos_target_tenant(const struct vos_target_state *state);
uint64_t vos_target_release(const struct vos_target_state *state);
void vos_target_advance(struct vos_target_state *state);
void vos_target_switch(const struct vos_target_state *state,
                       const struct vos_context *successor,
                       const struct vos_context *previous,
                       struct vos_context *output);
int vos_target_complete(unsigned published, unsigned resident, unsigned saved,
                         unsigned loans, unsigned devices, unsigned epoch);

#endif
