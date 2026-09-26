// SPDX-License-Identifier: Apache-2.0
/* Target compiler control for the actual byte-reader translation unit.
 * This deliberately uses no host model and no replacement decoder. */
#define VOS_MAX_PARTITIONS 2u
#define VOS_MAX_SLOTS 2u
#define VOS_MAX_WINDOWS 1u
#define VOS_MAX_CSRS 1u
#include "vos_handoff.h"
#include "context.c"
#include "executive.c"
#include "partition.c"
#include "../src/handoff.c"

static void put_word(uint8_t *bytes, size_t at, uint64_t word)
{
  unsigned i;
  for (i = 0; i < 8u; i++) {
    bytes[at + i] = (uint8_t)(word >> (8u * i));
  }
}

int main(void)
{
  uint8_t bytes[VOS_INIT_HEADER_BYTES + VOS_INIT_PARTITION_BYTES + VOS_INIT_SLOT_BYTES];
  struct vos_init_handoff output;
  enum vos_status status;
  size_t i;
  size_t at;
  for (i = 0; i < sizeof(bytes); i++) {
    bytes[i] = 0;
  }
  put_word(bytes, VOS_INIT_MAGIC_AT, VOS_INIT_MAGIC);
  put_word(bytes, VOS_INIT_VERSION_AT, VOS_INIT_VERSION);
  put_word(bytes, VOS_INIT_COMPOSITION_AT, 7);
  put_word(bytes, VOS_INIT_ROOT_AT, 0x80000000);
  put_word(bytes, VOS_INIT_ROOT_AT + 8u, 0x80010000);
  put_word(bytes, VOS_INIT_SWITCH_TEXT_AT, 0x80000000);
  put_word(bytes, VOS_INIT_SWITCH_TEXT_AT + 8u, 0x80001000);
  put_word(bytes, VOS_INIT_PARTITION_COUNT_AT, 1);
  put_word(bytes, VOS_INIT_SLOT_COUNT_AT, 1);
  put_word(bytes, VOS_INIT_MAJOR_FRAME_AT, 100);
  at = VOS_INIT_HEADER_BYTES;
  put_word(bytes, at, 1);
  put_word(bytes, at + 8u, 0x80008000);
  put_word(bytes, at + 16u, 0x80008200);
  put_word(bytes, at + 24u, 0x80002000);
  put_word(bytes, at + 32u, 0x80003000);
  put_word(bytes, at + 40u, 0x80003000);
  put_word(bytes, at + 48u, 0x80004000);
  at += VOS_INIT_PARTITION_BYTES;
  put_word(bytes, at, 100);
  put_word(bytes, at + 32u, 1);
  if (vos_init_decode(bytes, sizeof(bytes), 7, 0, &output, &status) != VOS_DECODE_OK) {
    return 1;
  }
  if (output.init.partition_count != 1u || output.init.frame.slots[0].tenant != 1u ||
      output.save_areas[0].base != 0x80008000) {
    return 2;
  }
  if (vos_init_decode(bytes, sizeof(bytes) - 1u, 7, 0, &output, &status) != VOS_DECODE_LENGTH) {
    return 3;
  }
  if (vos_init_decode(bytes, sizeof(bytes), 8, 0, &output, &status) != VOS_DECODE_INIT ||
      status != VOS_INIT_WRONG_COMPOSITION) {
    return 4;
  }
  return 0;
}
