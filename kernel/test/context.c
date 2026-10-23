// SPDX-License-Identifier: Apache-2.0
/* Fixed context-image controls, independent of generated Gallina vectors. */
#include <stdio.h>

#include "vos_kernel.h"

static int image_control(unsigned rotation, unsigned swapped,
                         unsigned rotation_swaps, unsigned alias)
{
  struct vos_machine machine = {0};
  struct vos_context successor = {0};
  struct vos_context previous = {0};
  struct vos_context separate = {0};
  struct vos_context original_successor;
  struct vos_context original_previous;
  struct vos_context *output = &separate;
  uint32_t i;

  machine.csr_count = 4;
  machine.roster[0].nameable = 1;
  machine.roster[1].nameable = 1;
  machine.roster[1].zeroized = 1;
  machine.roster[3].zeroized = 1;
  machine.pending_swapped = (uint8_t)swapped;
  machine.rotation_swaps_pending = (uint8_t)rotation_swaps;
  machine.pending_static_mask = 0x0f;
  for (i = 0; i < VOS_REGISTER_COUNT; ++i) {
    successor.reg[i].value = 100 + i;
    successor.reg[i].tag = (uint8_t)(i % 2);
    previous.reg[i].value = 200 + i;
    previous.reg[i].tag = (uint8_t)(1 - i % 2);
  }
  for (i = 0; i < VOS_MAX_CSRS; ++i) {
    successor.csr[i] = 1000 + i;
    previous.csr[i] = 2000 + i;
  }
  successor.pending = 0x35;
  previous.pending = 0x79;
  original_successor = successor;
  original_previous = previous;
  if (alias == 1) output = &successor;
  if (alias == 2) output = &previous;
  if (rotation)
    vos_rotation_image(&machine, &successor, &previous, output);
  else
    vos_switch_image(&machine, &successor, &previous, output);

  for (i = 0; i < VOS_REGISTER_COUNT; ++i) {
    if (output->reg[i].value != original_successor.reg[i].value ||
        output->reg[i].tag != original_successor.reg[i].tag)
      return 0;
  }
  for (i = 0; i < VOS_MAX_CSRS; ++i) {
    uint64_t expected = original_previous.csr[i];
    if (i == 0) expected = original_successor.csr[i];
    if (i == 1 && !rotation) expected = 0;
    if (output->csr[i] != expected) return 0;
  }
  if (rotation && !rotation_swaps)
    return output->pending == original_previous.pending;
  return output->pending == (swapped ? original_successor.pending :
                            original_successor.pending & machine.pending_static_mask);
}

int main(void)
{
  unsigned rotation, swapped, rotation_swaps, alias;
  for (rotation = 0; rotation < 2; ++rotation)
    for (swapped = 0; swapped < 2; ++swapped)
      for (rotation_swaps = 0; rotation_swaps < 2; ++rotation_swaps)
        for (alias = 0; alias < 3; ++alias)
          if (!image_control(rotation, swapped, rotation_swaps, alias)) {
            fprintf(stderr, "context image failed: rotation=%u swapped=%u "
                    "rotation_swaps=%u alias=%u\n",
                    rotation, swapped, rotation_swaps, alias);
            return 1;
          }
  puts("ok context image alias controls");
  return 0;
}
