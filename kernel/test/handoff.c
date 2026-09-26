// SPDX-License-Identifier: Apache-2.0
/* Fixed wire-contract controls, not Gallina vectors or target evidence. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "vos_handoff.h"

#define MAX_BYTES (VOS_INIT_HEADER_BYTES + VOS_MAX_PARTITIONS * VOS_INIT_PARTITION_BYTES + \
                   VOS_MAX_WINDOWS * VOS_INIT_WINDOW_BYTES + VOS_MAX_SLOTS * VOS_INIT_SLOT_BYTES + \
                   VOS_MAX_CSRS * VOS_INIT_CSR_BYTES)
static unsigned checks;

static void require(int condition, const char *name)
{
  checks++;
  if (!condition) {
    fprintf(stderr, "FAIL handoff control %u: %s\n", checks, name);
    exit(1);
  }
}

static void word(uint8_t *bytes, size_t at, uint64_t value)
{
  unsigned i;
  for (i = 0; i < 8; i++) {
    bytes[at + i] = (uint8_t)(value >> (8u * i));
  }
}

static size_t fixture(uint8_t *b, unsigned p, unsigned w, unsigned s, unsigned c)
{
  size_t at = VOS_INIT_HEADER_BYTES;
  unsigned i;
  memset(b, 0, MAX_BYTES + 1);
  word(b, VOS_INIT_MAGIC_AT, VOS_INIT_MAGIC);
  word(b, VOS_INIT_VERSION_AT, VOS_INIT_VERSION);
  word(b, VOS_INIT_COMPOSITION_AT, 7);
  word(b, VOS_INIT_HART_AT, 9);
  word(b, VOS_INIT_ROOT_AT, 0);
  word(b, VOS_INIT_ROOT_AT + 8, 65536);
  word(b, VOS_INIT_SWITCH_TEXT_AT, 100);
  word(b, VOS_INIT_SWITCH_TEXT_AT + 8, 200);
  word(b, VOS_INIT_PARTITION_COUNT_AT, p);
  word(b, VOS_INIT_WINDOW_COUNT_AT, w);
  word(b, VOS_INIT_SLOT_COUNT_AT, s);
  word(b, VOS_INIT_CSR_COUNT_AT, c);
  word(b, VOS_INIT_MAJOR_FRAME_AT, 10 * s);
  word(b, VOS_INIT_PHASE_OFFSET_AT, UINT64_C(0x1020304050607080));
  word(b, VOS_INIT_RESERVED_COUNT_AT, s > 1 ? 1 : 0);
  word(b, VOS_INIT_PENDING_ARM_AT, 1);
  word(b, VOS_INIT_ROTATION_SWAPS_AT, 1);
  word(b, VOS_INIT_PENDING_STATIC_MASK_AT, UINT64_C(0xfedcba9876543210));
  for (i = 0; i < p; i++) {
    word(b, at, i);
    word(b, at + 8, 40000 + 64 * i);
    word(b, at + 16, 40032 + 64 * i);
    word(b, at + 24, 1000 + 64 * i);
    word(b, at + 32, 1032 + 64 * i);
    word(b, at + 40, 30000 + 64 * i);
    word(b, at + 48, 30032 + 64 * i);
    at += VOS_INIT_PARTITION_BYTES;
  }
  for (i = 0; i < w; i++) {
    word(b, at, 50000 + 64 * i);
    word(b, at + 8, 50032 + 64 * i);
    at += VOS_INIT_WINDOW_BYTES;
  }
  for (i = 0; i < s; i++) {
    word(b, at, 10);
    word(b, at + 8, 10 * i);
    word(b, at + 16, 8);
    word(b, at + 24, 10 * s);
    word(b, at + 32, i);
    at += VOS_INIT_SLOT_BYTES;
  }
  for (i = 0; i < c; i++) {
    word(b, at, 32 + i);
    word(b, at + 8, i % 2);
    word(b, at + 16, 1 - i % 2);
    at += VOS_INIT_CSR_BYTES;
  }
  return at;
}

static void refusal(const uint8_t *b, size_t length, enum vos_decode_status expected,
                    enum vos_status semantic)
{
  struct vos_init_handoff output;
  unsigned char saved[sizeof output];
  enum vos_status status = VOS_INIT_MISSING;
  memset(&output, 0xa5, sizeof output);
  memcpy(saved, &output, sizeof output);
  require(vos_init_decode(b, length, 7, 9, &output, &status) == expected,
          "initialization refusal status");
  require(status == semantic, "initialization semantic status");
  require(memcmp(saved, &output, sizeof output) == 0, "refusal leaves output unchanged");
}

static void changed(size_t at, uint64_t value, enum vos_decode_status expected,
                    enum vos_status semantic)
{
  uint8_t b[MAX_BYTES + 1];
  size_t length = fixture(b, 2, 1, 2, 2);
  word(b, at, value);
  refusal(b, length, expected, semantic);
}

static void positive(unsigned p, unsigned w, unsigned s, unsigned c)
{
  uint8_t b[MAX_BYTES + 1];
  struct vos_init_handoff output;
  struct vos_init_desc *d = &output.init;
  enum vos_status status;
  unsigned i;
  size_t length = fixture(b, p, w, s, c);
  require(vos_init_decode(b, length, 7, 9, &output, &status) == VOS_DECODE_OK,
          "valid initialization");
  require(status == VOS_OK, "valid semantic status");
  require(d->composition_id == 7 && d->hart_id == 9 && d->root.base == 0 &&
          d->root.top == 65536 && d->switch_text.base == 100 && d->switch_text.top == 200,
          "header identity and extents");
  require(d->partition_count == p && d->window_count == w && d->frame.slot_count == s &&
          d->machine.csr_count == c && d->frame.major_frame == 10 * s &&
          d->frame.reserved_count == (s > 1 ? 1u : 0u), "header counts");
  require(d->frame.phase_offset == UINT64_C(0x1020304050607080) &&
          d->machine.pending_static_mask == UINT64_C(0xfedcba9876543210) &&
          d->machine.pending_swapped == 1 && d->machine.rotation_swaps_pending == 1,
          "full-width header fields");
  for (i = 0; i < p; i++) {
    struct vos_partition_desc *part = &d->partitions[i];
    require(part->tenant == i && part->has_context == 1 &&
            output.save_areas[i].base == 40000 + 64 * i &&
            output.save_areas[i].top == 40032 + 64 * i &&
            part->text.base == 1000 + 64 * i && part->text.top == 1032 + 64 * i &&
            part->data.base == 30000 + 64 * i && part->data.top == 30032 + 64 * i,
            "partition and save-area fields");
  }
  for (i = 0; i < w; i++) {
    require(d->windows[i].base == 50000 + 64 * i && d->windows[i].top == 50032 + 64 * i,
            "window fields");
  }
  for (i = 0; i < s; i++) {
    struct vos_slot *slot = &d->frame.slots[i];
    require(slot->width == 10 && slot->offset == 10 * i && slot->bound == 8 &&
            slot->period == 10 * s && slot->tenant == i, "slot fields");
  }
  for (i = 0; i < c; i++) {
    require(d->machine.roster[i].csr == 32 + i && d->machine.roster[i].nameable == i % 2 &&
            d->machine.roster[i].zeroized == 1 - i % 2, "CSR fields");
  }
}

static void initialization_controls(void)
{
  uint8_t b[MAX_BYTES + 1];
  size_t length = fixture(b, 2, 1, 2, 2);
  size_t n;
  const size_t partition = VOS_INIT_HEADER_BYTES;
  const size_t window = partition + 2 * VOS_INIT_PARTITION_BYTES;
  const size_t slot = window + VOS_INIT_WINDOW_BYTES;
  const size_t csr = slot + 2 * VOS_INIT_SLOT_BYTES;
  const size_t counts[] = {VOS_INIT_PARTITION_COUNT_AT, VOS_INIT_WINDOW_COUNT_AT,
                         VOS_INIT_SLOT_COUNT_AT, VOS_INIT_CSR_COUNT_AT};
  const uint64_t capacities[] = {VOS_MAX_PARTITIONS, VOS_MAX_WINDOWS,
                                VOS_MAX_SLOTS, VOS_MAX_CSRS};
  const size_t booleans[] = {VOS_INIT_PENDING_ARM_AT, VOS_INIT_ROTATION_SWAPS_AT,
                            csr + 8, csr + 16};
  const size_t widths[] = {VOS_INIT_RESERVED_COUNT_AT, partition, slot + 32, csr};
  positive(2, 1, 2, 2);
  positive(1, 0, 1, 0);
  positive(VOS_MAX_PARTITIONS, VOS_MAX_WINDOWS, VOS_MAX_SLOTS, VOS_MAX_CSRS);
  {
    struct vos_init_handoff output;
    enum vos_status status;
    word(b, partition, UINT32_MAX);
    word(b, slot + 32, UINT32_MAX);
    word(b, csr, UINT32_MAX);
    word(b, VOS_INIT_PENDING_ARM_AT, 0);
    word(b, VOS_INIT_ROTATION_SWAPS_AT, 0);
    require(vos_init_decode(b, length, 7, 9, &output, &status) == VOS_DECODE_OK &&
            output.init.partitions[0].tenant == UINT32_MAX &&
            output.init.frame.slots[0].tenant == UINT32_MAX &&
            output.init.machine.roster[0].csr == UINT32_MAX &&
            output.init.machine.pending_swapped == 0 &&
            output.init.machine.rotation_swaps_pending == 0,
            "maximum consumer integer and static-arm fields are preserved");
    require(vos_init_decode(b, length, 7, 9, 0, &status) == VOS_DECODE_MISSING,
            "missing output refused");
    require(vos_init_decode(b, length, 7, 9, &output, 0) == VOS_DECODE_MISSING,
            "missing status refused");
    length = fixture(b, 2, 1, 2, 2);
  }
  /* Exact heap spans let ASan catch a decoder reading past a truncation. */
  for (n = 0; n < length; n++) {
    uint8_t *short_input = malloc(n ? n : 1);
    require(short_input != 0, "allocate truncation fixture");
    memcpy(short_input, b, n);
    refusal(short_input, n, VOS_DECODE_LENGTH, VOS_OK);
    free(short_input);
  }
  refusal(b, length + 1, VOS_DECODE_LENGTH, VOS_OK);
  refusal(0, length, VOS_DECODE_MISSING, VOS_OK);
  changed(VOS_INIT_MAGIC_AT, 0, VOS_DECODE_MAGIC, VOS_OK);
  changed(VOS_INIT_VERSION_AT, 2, VOS_DECODE_VERSION, VOS_OK);
  changed(VOS_INIT_COMPOSITION_AT, 8, VOS_DECODE_INIT, VOS_INIT_WRONG_COMPOSITION);
  changed(VOS_INIT_HART_AT, 10, VOS_DECODE_INIT, VOS_INIT_WRONG_HART);
  for (n = 0; n < sizeof counts / sizeof counts[0]; n++) {
    changed(counts[n], capacities[n] + 1, VOS_DECODE_CAPACITY, VOS_OK);
    changed(counts[n], UINT64_MAX, VOS_DECODE_CAPACITY, VOS_OK);
  }
  for (n = 0; n < sizeof booleans / sizeof booleans[0]; n++) {
    changed(booleans[n], 2, VOS_DECODE_BOOLEAN, VOS_OK);
    changed(booleans[n], 256, VOS_DECODE_BOOLEAN, VOS_OK);
  }
  for (n = 0; n < sizeof widths / sizeof widths[0]; n++) {
    changed(widths[n], UINT64_C(0x100000000), VOS_DECODE_WIDTH, VOS_OK);
  }
  changed(partition + 16, 39999, VOS_DECODE_SAVE_AREA, VOS_OK);
  changed(partition + 16, 40000, VOS_DECODE_INIT, VOS_INIT_NO_PLANNED_SUCCESSOR);
  changed(slot + 32, 99, VOS_DECODE_INIT, VOS_INIT_NO_PLANNED_SUCCESSOR);
  changed(partition + VOS_INIT_PARTITION_BYTES, 0, VOS_DECODE_INIT, VOS_INIT_TENANT_SHARED);
  changed(VOS_INIT_ROOT_AT + 8, 0, VOS_DECODE_INIT, VOS_INIT_EXTENT_MALFORMED);
  changed(VOS_INIT_SWITCH_TEXT_AT + 8, 100, VOS_DECODE_INIT, VOS_INIT_EXTENT_MALFORMED);
  changed(window + 8, 50000, VOS_DECODE_INIT, VOS_INIT_EXTENT_MALFORMED);
  changed(partition + 32, 1000, VOS_DECODE_INIT, VOS_INIT_EXTENT_MALFORMED);
  changed(partition + 48, 30000, VOS_DECODE_INIT, VOS_INIT_EXTENT_MALFORMED);
  changed(partition + 48, 65537, VOS_DECODE_INIT, VOS_INIT_EXTENT_OUTSIDE_ROOT);
  changed(slot + VOS_INIT_SLOT_BYTES + 8, 0, VOS_DECODE_INIT, VOS_TABLE_OVERLAP);
}

static void boot_refusal(const uint8_t *bytes, size_t length, enum vos_decode_status expected)
{
  struct vos_boot_record output;
  unsigned char saved[sizeof output];
  memset(&output, 0x5a, sizeof output);
  memcpy(saved, &output, sizeof output);
  require(vos_boot_record_decode(bytes, length, &output) == expected, "boot refusal status");
  require(memcmp(saved, &output, sizeof output) == 0, "boot refusal leaves output unchanged");
}

static void boot_controls(void)
{
  uint8_t b[VOS_HANDOFF_BYTES + 1] = {0};
  struct vos_boot_record output;
  size_t n;
  word(b, VOS_HANDOFF_MAGIC_AT, VOS_HANDOFF_MAGIC);
  word(b, VOS_HANDOFF_VERSION_AT, VOS_HANDOFF_VERSION);
  for (n = VOS_HANDOFF_LIFECYCLE_AT; n < VOS_HANDOFF_IMAGE_DIGEST_AT; n += 8) {
    word(b, n, UINT64_C(0x1020304050607080) + n);
  }
  for (n = VOS_HANDOFF_IMAGE_DIGEST_AT; n < VOS_HANDOFF_USED_BYTES; n++) {
    b[n] = (uint8_t)n;
  }
  require(vos_boot_record_decode(b, VOS_HANDOFF_BYTES, &output) == VOS_DECODE_OK,
          "boot record accepted without interpreting measurement as authentication");
  require(output.lifecycle == UINT64_C(0x1020304050607090) &&
          output.entropy_ok == UINT64_C(0x1020304050607098) &&
          output.boot_target == UINT64_C(0x10203040506070a0) &&
          output.security_version == UINT64_C(0x10203040506070a8) &&
          output.floor == UINT64_C(0x10203040506070b0) &&
          output.load_base == UINT64_C(0x10203040506070b8) &&
          output.payload_length == UINT64_C(0x10203040506070c0), "boot scalar fields");
  require(memcmp(output.image_digest, b + VOS_HANDOFF_IMAGE_DIGEST_AT, VOS_BOOT_DIGEST_BYTES) == 0 &&
          memcmp(output.generation, b + VOS_HANDOFF_GENERATION_AT, VOS_MEASURE_BYTES) == 0 &&
          memcmp(output.device, b + VOS_HANDOFF_DEVICE_AT, VOS_MEASURE_BYTES) == 0 &&
          memcmp(output.chain, b + VOS_HANDOFF_CHAIN_AT, VOS_MEASURE_BYTES) == 0,
          "boot measurement bytes");
  for (n = 0; n < VOS_HANDOFF_BYTES; n++) {
    uint8_t *short_input = malloc(n ? n : 1);
    require(short_input != 0, "allocate boot truncation");
    memcpy(short_input, b, n);
    boot_refusal(short_input, n, VOS_DECODE_LENGTH);
    free(short_input);
  }
  boot_refusal(b, VOS_HANDOFF_BYTES + 1, VOS_DECODE_LENGTH);
  boot_refusal(0, VOS_HANDOFF_BYTES, VOS_DECODE_MISSING);
  word(b, VOS_HANDOFF_MAGIC_AT, 0);
  boot_refusal(b, VOS_HANDOFF_BYTES, VOS_DECODE_MAGIC);
  word(b, VOS_HANDOFF_MAGIC_AT, VOS_HANDOFF_MAGIC);
  word(b, VOS_HANDOFF_VERSION_AT, 2);
  boot_refusal(b, VOS_HANDOFF_BYTES, VOS_DECODE_VERSION);
  word(b, VOS_HANDOFF_VERSION_AT, VOS_HANDOFF_VERSION);
  for (n = VOS_HANDOFF_USED_BYTES; n < VOS_HANDOFF_BYTES; n++) {
    b[n] = 1;
    boot_refusal(b, VOS_HANDOFF_BYTES, VOS_DECODE_RESERVED);
    b[n] = 0;
  }
}

int main(int argc, char **argv)
{
  FILE *input;
  uint8_t bytes[VOS_INIT_HEADER_BYTES + 1];
  struct vos_init_handoff output;
  enum vos_status status;
  size_t length;
  require(argc == 2, "assembled producer descriptor path supplied");
  input = fopen(argv[1], "rb");
  require(input != 0, "read producer descriptor");
  length = fread(bytes, 1, sizeof bytes, input);
  require(fclose(input) == 0, "close producer descriptor");
  require(length == VOS_INIT_HEADER_BYTES, "producer descriptor header only");
  require(vos_init_decode(bytes, length, 1, 0, &output, &status) == VOS_DECODE_INIT &&
          status == VOS_TABLE_EMPTY, "M3.5 empty fixture cannot dispatch");
  initialization_controls();
  boot_controls();
  printf("ok %u handoff fixed controls; target capability entry remains unbuilt\n", checks);
  return 0;
}
