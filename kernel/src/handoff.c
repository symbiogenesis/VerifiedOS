// SPDX-License-Identifier: Apache-2.0
/* M3.5 owns every layout constant in vos_boot.h. Read integers byte by byte:
 * the wire contains 64-bit little-endian integers, not C structs or pointers.
 * No target capability instruction or C-to-ISA correspondence is claimed. */
#include "vos_handoff.h"

static uint64_t read_word(const uint8_t *bytes, size_t at)
{
  uint64_t result = 0;
  unsigned i;
  for (i = 0; i < 8u; i++) {
    result |= (uint64_t)bytes[at + i] << (8u * i);
  }
  return result;
}

static void read_extent(const uint8_t *bytes, size_t at, struct vos_extent *output)
{
  output->base = read_word(bytes, at);
  output->top = read_word(bytes, at + 8u);
}

/* Check before multiplying, on size_t as well as on the wire's uint64_t. */
static int take_array(size_t length, size_t *used, uint64_t count, size_t stride)
{
  if (count > (length - *used) / stride) {
    return 0;
  }
  *used += (size_t)count * stride;
  return 1;
}

enum vos_decode_status vos_init_decode(const uint8_t *bytes, size_t length,
                                      uint64_t composition, uint64_t hart,
                                      struct vos_init_handoff *output,
                                      enum vos_status *init_status)
{
  struct vos_init_handoff candidate = {0};
  struct vos_init_desc *d = &candidate.init;
  uint64_t partitions, windows, slots, csrs, reserved, pending, rotation;
  size_t used = VOS_INIT_HEADER_BYTES;
  size_t at;
  uint32_t i;
  enum vos_status status;
  if (init_status == 0) {
    return VOS_DECODE_MISSING;
  }
  *init_status = VOS_OK;
  if (bytes == 0 || output == 0) {
    return VOS_DECODE_MISSING;
  }
  if (length < VOS_INIT_HEADER_BYTES) {
    return VOS_DECODE_LENGTH;
  }
  if (read_word(bytes, VOS_INIT_MAGIC_AT) != VOS_INIT_MAGIC) {
    return VOS_DECODE_MAGIC;
  }
  if (read_word(bytes, VOS_INIT_VERSION_AT) != VOS_INIT_VERSION) {
    return VOS_DECODE_VERSION;
  }
  partitions = read_word(bytes, VOS_INIT_PARTITION_COUNT_AT);
  windows = read_word(bytes, VOS_INIT_WINDOW_COUNT_AT);
  slots = read_word(bytes, VOS_INIT_SLOT_COUNT_AT);
  csrs = read_word(bytes, VOS_INIT_CSR_COUNT_AT);
  if (partitions > VOS_MAX_PARTITIONS || partitions > UINT32_MAX ||
      windows > VOS_MAX_WINDOWS || windows > UINT32_MAX ||
      slots > VOS_MAX_SLOTS || slots > UINT32_MAX ||
      csrs > VOS_MAX_CSRS || csrs > UINT32_MAX) {
    return VOS_DECODE_CAPACITY;
  }
  if (!take_array(length, &used, partitions, VOS_INIT_PARTITION_BYTES) ||
      !take_array(length, &used, windows, VOS_INIT_WINDOW_BYTES) ||
      !take_array(length, &used, slots, VOS_INIT_SLOT_BYTES) ||
      !take_array(length, &used, csrs, VOS_INIT_CSR_BYTES) || used != length) {
    return VOS_DECODE_LENGTH;
  }
  /* All header and row reads below are inside the exact checked span. */
  reserved = read_word(bytes, VOS_INIT_RESERVED_COUNT_AT);
  pending = read_word(bytes, VOS_INIT_PENDING_ARM_AT);
  rotation = read_word(bytes, VOS_INIT_ROTATION_SWAPS_AT);
  if (reserved > UINT32_MAX) {
    return VOS_DECODE_WIDTH;
  }
  if (pending > 1u || rotation > 1u) {
    return VOS_DECODE_BOOLEAN;
  }
  d->composition_id = read_word(bytes, VOS_INIT_COMPOSITION_AT);
  d->hart_id = read_word(bytes, VOS_INIT_HART_AT);
  read_extent(bytes, VOS_INIT_ROOT_AT, &d->root);
  read_extent(bytes, VOS_INIT_SWITCH_TEXT_AT, &d->switch_text);
  d->partition_count = (uint32_t)partitions;
  d->window_count = (uint32_t)windows;
  d->frame.slot_count = (uint32_t)slots;
  d->machine.csr_count = (uint32_t)csrs;
  d->frame.major_frame = read_word(bytes, VOS_INIT_MAJOR_FRAME_AT);
  d->frame.phase_offset = read_word(bytes, VOS_INIT_PHASE_OFFSET_AT);
  d->frame.reserved_count = (uint32_t)reserved;
  d->machine.pending_swapped = (uint8_t)pending;
  d->machine.rotation_swaps_pending = (uint8_t)rotation;
  d->machine.pending_static_mask = read_word(bytes, VOS_INIT_PENDING_STATIC_MASK_AT);
  at = VOS_INIT_HEADER_BYTES;
  for (i = 0; i < d->partition_count; i++) {
    uint64_t tenant = read_word(bytes, at);
    struct vos_extent save;
    read_extent(bytes, at + 8u, &save);
    if (tenant > UINT32_MAX) {
      return VOS_DECODE_WIDTH;
    }
    if (save.base > save.top) {
      return VOS_DECODE_SAVE_AREA;
    }
    candidate.save_areas[i] = save;
    d->partitions[i].tenant = (uint32_t)tenant;
    d->partitions[i].has_context = save.base < save.top;
    read_extent(bytes, at + 24u, &d->partitions[i].text);
    read_extent(bytes, at + 40u, &d->partitions[i].data);
    at += VOS_INIT_PARTITION_BYTES;
  }
  for (i = 0; i < d->window_count; i++) {
    read_extent(bytes, at, &d->windows[i]);
    at += VOS_INIT_WINDOW_BYTES;
  }
  for (i = 0; i < d->frame.slot_count; i++) {
    uint64_t tenant = read_word(bytes, at + 32u);
    if (tenant > UINT32_MAX) {
      return VOS_DECODE_WIDTH;
    }
    d->frame.slots[i].width = read_word(bytes, at);
    d->frame.slots[i].offset = read_word(bytes, at + 8u);
    d->frame.slots[i].bound = read_word(bytes, at + 16u);
    d->frame.slots[i].period = read_word(bytes, at + 24u);
    d->frame.slots[i].tenant = (uint32_t)tenant;
    at += VOS_INIT_SLOT_BYTES;
  }
  for (i = 0; i < d->machine.csr_count; i++) {
    uint64_t csr = read_word(bytes, at);
    uint64_t nameable = read_word(bytes, at + 8u);
    uint64_t zeroized = read_word(bytes, at + 16u);
    if (csr > UINT32_MAX) {
      return VOS_DECODE_WIDTH;
    }
    if (nameable > 1u || zeroized > 1u) {
      return VOS_DECODE_BOOLEAN;
    }
    d->machine.roster[i].csr = (uint32_t)csr;
    d->machine.roster[i].nameable = (uint8_t)nameable;
    d->machine.roster[i].zeroized = (uint8_t)zeroized;
    at += VOS_INIT_CSR_BYTES;
  }
  status = vos_init_validate(d, composition, hart);
  if (status != VOS_OK) {
    *init_status = status;
    return VOS_DECODE_INIT;
  }
  *output = candidate;
  return VOS_DECODE_OK;
}

static void read_digest(const uint8_t *bytes, size_t at, uint8_t *output, unsigned size)
{
  unsigned i;
  for (i = 0; i < size; i++) {
    output[i] = bytes[at + i];
  }
}

enum vos_decode_status vos_boot_record_decode(const uint8_t *bytes, size_t length,
                                             struct vos_boot_record *output)
{
  struct vos_boot_record candidate = {0};
  size_t i;
  if (bytes == 0 || output == 0) {
    return VOS_DECODE_MISSING;
  }
  if (length != VOS_HANDOFF_BYTES) {
    return VOS_DECODE_LENGTH;
  }
  if (read_word(bytes, VOS_HANDOFF_MAGIC_AT) != VOS_HANDOFF_MAGIC) {
    return VOS_DECODE_MAGIC;
  }
  if (read_word(bytes, VOS_HANDOFF_VERSION_AT) != VOS_HANDOFF_VERSION) {
    return VOS_DECODE_VERSION;
  }
  for (i = VOS_HANDOFF_USED_BYTES; i < VOS_HANDOFF_BYTES; i++) {
    if (bytes[i] != 0u) {
      return VOS_DECODE_RESERVED;
    }
  }
  candidate.lifecycle = read_word(bytes, VOS_HANDOFF_LIFECYCLE_AT);
  candidate.entropy_ok = read_word(bytes, VOS_HANDOFF_ENTROPY_AT);
  candidate.boot_target = read_word(bytes, VOS_HANDOFF_BOOT_TARGET_AT);
  candidate.security_version = read_word(bytes, VOS_HANDOFF_SECURITY_VERSION_AT);
  candidate.floor = read_word(bytes, VOS_HANDOFF_FLOOR_AT);
  candidate.load_base = read_word(bytes, VOS_HANDOFF_LOAD_BASE_AT);
  candidate.payload_length = read_word(bytes, VOS_HANDOFF_PAYLOAD_LENGTH_AT);
  read_digest(bytes, VOS_HANDOFF_IMAGE_DIGEST_AT, candidate.image_digest, VOS_BOOT_DIGEST_BYTES);
  read_digest(bytes, VOS_HANDOFF_GENERATION_AT, candidate.generation, VOS_MEASURE_BYTES);
  read_digest(bytes, VOS_HANDOFF_DEVICE_AT, candidate.device, VOS_MEASURE_BYTES);
  read_digest(bytes, VOS_HANDOFF_CHAIN_AT, candidate.chain, VOS_MEASURE_BYTES);
  *output = candidate;
  return VOS_DECODE_OK;
}
