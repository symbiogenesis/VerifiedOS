// SPDX-License-Identifier: Apache-2.0
/* The byte readers for boot-handoff.md section 6. Target entry and capability
 * inspection are separate, unbuilt joins: these functions neither authenticate
 * bytes nor observe c10/c11/c12 tags, bounds, permissions or provenance. */
#ifndef VOS_HANDOFF_H
#define VOS_HANDOFF_H 1

#include <stddef.h>
#include "vos_kernel.h"
#include "vos_boot.h"

enum vos_decode_status {
  VOS_DECODE_OK = 0,
  VOS_DECODE_MISSING = 1,
  VOS_DECODE_LENGTH = 2,
  VOS_DECODE_MAGIC = 3,
  VOS_DECODE_VERSION = 4,
  VOS_DECODE_CAPACITY = 5,
  VOS_DECODE_WIDTH = 6,
  VOS_DECODE_BOOLEAN = 7,
  VOS_DECODE_SAVE_AREA = 8,
  VOS_DECODE_RESERVED = 9,
  VOS_DECODE_INIT = 10
};

/* Preserve the save-area declarations that vos_init_desc represents only by
 * has_context. A nonempty declaration is not a constructed initial context. */
struct vos_init_handoff {
  struct vos_init_desc init;
  struct vos_extent save_areas[VOS_MAX_PARTITIONS];
};

struct vos_boot_record {
  uint64_t lifecycle;
  uint64_t entropy_ok;
  uint64_t boot_target;
  uint64_t security_version;
  uint64_t floor;
  uint64_t load_base;
  uint64_t payload_length;
  uint8_t image_digest[VOS_BOOT_DIGEST_BYTES];
  uint8_t generation[VOS_MEASURE_BYTES];
  uint8_t device[VOS_MEASURE_BYTES];
  uint8_t chain[VOS_MEASURE_BYTES];
};

/* Input is a stable readable byte span of exactly length bytes. The future
 * entry adapter must derive that span from the actual read-only capability,
 * not an untrusted integer length. Output and init_status must be writable,
 * disjoint from input and from each other. Refusal leaves output unchanged.
 * No pointer is retained or followed from the wire. On VOS_DECODE_INIT,
 * init_status names the semantic refusal; otherwise it is VOS_OK. */
enum vos_decode_status vos_init_decode(const uint8_t *bytes, size_t length,
                                      uint64_t composition, uint64_t hart,
                                      struct vos_init_handoff *output,
                                      enum vos_status *init_status);
enum vos_decode_status vos_boot_record_decode(const uint8_t *bytes, size_t length,
                                             struct vos_boot_record *output);

#endif
