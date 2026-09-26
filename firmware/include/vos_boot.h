// SPDX-License-Identifier: Apache-2.0
// The RoT's measured release of the boot core, as
// docs/implementation/contracts/boot-handoff.md states it.
//
// This header is the implementation owner of the boot image layout and the
// bring-up composition constants. The contract's tables and the harness in
// tools/vos/boot_handoff.py are checked against the macros below rather than
// restating them.
#ifndef VOS_BOOT_H
#define VOS_BOOT_H

#include <stddef.h>
#include <stdint.h>

// ---------------------------------------------------------------------------
// The fixed-layout, length-bounded boot header (R-09-005). Every field is at a
// constant offset, integers are little-endian, and no field's value locates
// another field. The signed region is every byte before the signature.

#define VOS_BOOT_MAGIC 0x31544F4F42534F56u  // the bytes "VOSBOOT1"
#define VOS_BOOT_HDR_MAGIC 0u
#define VOS_BOOT_HDR_STAGE 8u
#define VOS_BOOT_HDR_SECURITY_VERSION 16u
#define VOS_BOOT_HDR_PAYLOAD_OFFSET 24u
#define VOS_BOOT_HDR_PAYLOAD_LENGTH 32u
#define VOS_BOOT_HDR_PAYLOAD_DIGEST 40u
#define VOS_BOOT_HDR_SIGNATURE 72u
#define VOS_BOOT_DIGEST_BYTES 32u
// SLH-DSA-SHAKE-256s (R-05-058a): FIPS 205 Table 2's signature size, which
// proofs/RomVerifier.v computes from the parameter set.
#define VOS_BOOT_SIGNATURE_BYTES 29792u
#define VOS_BOOT_PUBLIC_KEY_BYTES 64u
#define VOS_BOOT_SIGNED_BYTES VOS_BOOT_HDR_SIGNATURE
#define VOS_BOOT_HEADER_BYTES (VOS_BOOT_HDR_SIGNATURE + VOS_BOOT_SIGNATURE_BYTES)

// Stage identifiers, in R-09-002's chain order (proofs/RotFirmware.v `Stage`).
#define VOS_BOOT_STAGE_ROT_RUNTIME 0u
#define VOS_BOOT_STAGE_MMODE_IMAGE 1u
#define VOS_BOOT_STAGE_CORE_KERNELS 2u
#define VOS_BOOT_STAGE_STATIC_IMAGE 3u

// Lifecycle indices, in model/model/sys/rot.sail's lifecycle_to_index order.
#define VOS_LIFECYCLE_RAW 0u
#define VOS_LIFECYCLE_TEST 1u
#define VOS_LIFECYCLE_DEVELOPMENT 2u
#define VOS_LIFECYCLE_PRODUCTION 3u
#define VOS_LIFECYCLE_RMA 4u
#define VOS_LIFECYCLE_COUNT 5u

// ---------------------------------------------------------------------------
// Measurement (R-09-025a). Two registers, each 32 bytes and zero at reset.
// extend(R, code, data) = SHAKE256(EXTEND_DOMAIN || R || code || len32 || data, 256);
// chain = SHAKE256(CHAIN_DOMAIN || generation || device, 256).

#define VOS_MEASURE_BYTES 32u
#define VOS_MEASURE_EXTEND_DOMAIN "VOS-EXT1"
#define VOS_MEASURE_CHAIN_DOMAIN "VOS-CHN1"
// Item codes, in proofs/RotFirmware.v `all_items` order.
#define VOS_ITEM_LIFECYCLE 1u
#define VOS_ITEM_ENTROPY_VERDICT 2u
#define VOS_ITEM_BOOT_TARGET 3u
#define VOS_ITEM_STAGE_ROT_RUNTIME 4u
#define VOS_ITEM_STAGE_MMODE_IMAGE 5u
#define VOS_ITEM_STAGE_CORE_KERNELS 6u
#define VOS_ITEM_STAGE_STATIC_IMAGE 7u
#define VOS_MEASURE_LOG_CAPACITY 8u
// The extensions one call of vos_rot_boot_mmode makes: items 1, 2, 3 and 5.
#define VOS_MEASURE_RELEASE_EXTENSIONS 4u

// ---------------------------------------------------------------------------
// The handoff record the RoT writes before release: the boot descriptor the
// M-mode stage hands the kernel in c11 (purecap-abi.md section 7).

#define VOS_HANDOFF_MAGIC 0x31444E4148534F56u  // the bytes "VOSHAND1"
#define VOS_HANDOFF_VERSION 1u
#define VOS_HANDOFF_MAGIC_AT 0u
#define VOS_HANDOFF_VERSION_AT 8u
#define VOS_HANDOFF_LIFECYCLE_AT 16u
#define VOS_HANDOFF_ENTROPY_AT 24u
#define VOS_HANDOFF_BOOT_TARGET_AT 32u
#define VOS_HANDOFF_SECURITY_VERSION_AT 40u
#define VOS_HANDOFF_FLOOR_AT 48u
#define VOS_HANDOFF_LOAD_BASE_AT 56u
#define VOS_HANDOFF_PAYLOAD_LENGTH_AT 64u
#define VOS_HANDOFF_IMAGE_DIGEST_AT 72u
#define VOS_HANDOFF_GENERATION_AT 104u
#define VOS_HANDOFF_DEVICE_AT 136u
#define VOS_HANDOFF_CHAIN_AT 168u
#define VOS_HANDOFF_USED_BYTES 200u
#define VOS_HANDOFF_BYTES 256u

// ---------------------------------------------------------------------------
// The kernel initialization descriptor the M-mode stage hands the kernel in
// c12 (purecap-abi.md section 7). It is composed at build time and is part of
// the measured image; nothing in this directory writes it. Every integer is
// one little-endian doubleword and every extent is two, its base and its top.
// A fixed header is followed by the partition records, the shared windows, the
// schedule table's slots and the CSR roster's rows, each array as long as the
// header's count says, so the descriptor's length is
// INIT_HEADER_BYTES + P * INIT_PARTITION_BYTES + W * INIT_WINDOW_BYTES
//   + S * INIT_SLOT_BYTES + C * INIT_CSR_BYTES.

#define VOS_INIT_MAGIC 0x3154494E49534F56u  // the bytes "VOSINIT1"
#define VOS_INIT_VERSION 1u
#define VOS_INIT_MAGIC_AT 0u
#define VOS_INIT_VERSION_AT 8u
#define VOS_INIT_COMPOSITION_AT 16u
#define VOS_INIT_HART_AT 24u
#define VOS_INIT_ROOT_AT 32u
#define VOS_INIT_SWITCH_TEXT_AT 48u
#define VOS_INIT_PARTITION_COUNT_AT 64u
#define VOS_INIT_WINDOW_COUNT_AT 72u
#define VOS_INIT_SLOT_COUNT_AT 80u
#define VOS_INIT_CSR_COUNT_AT 88u
#define VOS_INIT_MAJOR_FRAME_AT 96u
#define VOS_INIT_PHASE_OFFSET_AT 104u
#define VOS_INIT_RESERVED_COUNT_AT 112u
#define VOS_INIT_PENDING_ARM_AT 120u
#define VOS_INIT_ROTATION_SWAPS_AT 128u
#define VOS_INIT_PENDING_STATIC_MASK_AT 136u
#define VOS_INIT_HEADER_BYTES 144u
#define VOS_INIT_EXTENT_BYTES 16u
// A partition: its tenant, then the planned save area's, the text's and the
// data's extents. An empty save-area extent plans no context for it.
#define VOS_INIT_PARTITION_BYTES 56u
#define VOS_INIT_WINDOW_BYTES 16u
// A slot: width, offset, bound, period and tenant.
#define VOS_INIT_SLOT_BYTES 40u
// A CSR roster row: the CSR's address, nameable and zeroized.
#define VOS_INIT_CSR_BYTES 24u

// ---------------------------------------------------------------------------
// The bring-up composition this harness runs. Composition constants rather
// than architecture: the attested devicetree owes their production values.

#define VOS_BRINGUP_MMODE_LOAD_BASE 0x80000000u
#define VOS_BRINGUP_MMODE_REGION_BYTES 0x10000u
#define VOS_BRINGUP_HANDOFF_BASE 0x80010000u

// ---------------------------------------------------------------------------
// Verdicts. Zero is the only release; every other value is a refusal whose
// name is the first check the image failed, in the contract's order.

typedef enum {
  VOS_BOOT_RELEASE = 0,
  VOS_BOOT_REFUSE_ENTROPY = 1,
  VOS_BOOT_REFUSE_NO_ROOT = 2,
  VOS_BOOT_REFUSE_TRUNCATED = 3,
  VOS_BOOT_REFUSE_MAGIC = 4,
  VOS_BOOT_REFUSE_STAGE = 5,
  VOS_BOOT_REFUSE_OFFSET = 6,
  VOS_BOOT_REFUSE_LENGTH = 7,
  VOS_BOOT_REFUSE_FLOOR = 8,
  VOS_BOOT_REFUSE_NO_VERIFIER = 9,
  VOS_BOOT_REFUSE_SIGNATURE = 10,
  VOS_BOOT_REFUSE_PLACEMENT = 11,
  VOS_BOOT_REFUSE_DIGEST = 12,
  VOS_BOOT_REFUSE_MEASUREMENT = 13,
} vos_boot_verdict;

const char *vos_boot_verdict_name(vos_boot_verdict verdict);

// The inputs the RoT reads from its own devices (model/model/sys/rot.sail):
// the lifecycle fuse state, the start-up entropy verdict, the boot-target
// latch and the image-security-version counter that is the anti-rollback floor.
typedef struct {
  uint8_t lifecycle;
  uint8_t entropy_ok;
  uint8_t boot_target;
  uint64_t floor;
} vos_rot_inputs;

// A signature verifier's answer. The production binding is SLH-DSA-SHAKE-256s
// verification (FIPS 205 Algorithm 20 over the signed header bytes), supplied
// by crypto/slh256s.c. Its host comparisons leave target qualification open.
typedef enum { VOS_SIG_ACCEPT = 1, VOS_SIG_REJECT = 2 } vos_sig_result;

typedef vos_sig_result (*vos_sig_verify_fn)(void *context, const uint8_t *message,
                                            size_t message_len, const uint8_t *signature,
                                            const uint8_t *public_key);

// What the composition fixes for this verifier: one accepted root per
// lifecycle state (R-09-036), NULL where the state accepts none, the bound
// signature verifier, and where the stage is placed.
typedef struct {
  const uint8_t *root[VOS_LIFECYCLE_COUNT];
  vos_sig_verify_fn verify;
  void *verify_context;
  uint64_t load_base;
  uint64_t region_bytes;
} vos_rot_policy;

typedef struct {
  uint8_t generation[VOS_MEASURE_BYTES];
  uint8_t device[VOS_MEASURE_BYTES];
  uint8_t log[VOS_MEASURE_LOG_CAPACITY];
  unsigned count;
} vos_measurements;

typedef struct {
  vos_boot_verdict verdict;
  uint64_t security_version;
  uint64_t payload_length;
  int digest_computed;
  uint8_t image_digest[VOS_BOOT_DIGEST_BYTES];
  uint8_t chain[VOS_MEASURE_BYTES];
  vos_measurements measured;
} vos_boot_result;

// Called once, after the handoff record is written, and never on a refusal.
typedef void (*vos_release_fn)(void *context);

// The main SRAM window the stage is placed in and the handoff record window,
// as the RoT's authority over main memory reaches them. The release refuses
// windows too small for the payload or the record rather than writing past
// them.
typedef struct {
  uint8_t *image;
  uint64_t image_bytes;
  uint8_t *handoff;
  uint64_t handoff_bytes;
} vos_sram_windows;

void vos_measure_reset(vos_measurements *m);
int vos_measure_extend(vos_measurements *m, int generation_register, uint8_t code,
                       const uint8_t *data, uint32_t len);
void vos_measure_chain(const vos_measurements *m, uint8_t out[VOS_MEASURE_BYTES]);

// R-09-006's sequence for the M-mode stage: extend the device register with
// the lifecycle state, the entropy verdict and the boot-target latch; refuse on
// a failed entropy verdict or a state with no accepted root; read the header;
// check the floor; verify the signature; place the payload; measure the placed
// bytes; compare; extend the generation register; write the handoff record;
// release. On any refusal the image window is zeroed, the handoff window is
// untouched and `release` is not called.
//
// The signed prefix is copied once into the function's own storage, and every
// header field it decides on and the message it verifies are read from that
// copy, so a field cannot change between its check and the signature check.
// The signature and the payload are read from `image` in place; `image` and
// both windows must be memory no requester other than the RoT can write for the
// duration of the call.
vos_boot_verdict vos_rot_boot_mmode(const uint8_t *image, uint64_t image_len,
                                    const vos_rot_inputs *inputs,
                                    const vos_rot_policy *policy,
                                    const vos_sram_windows *sram,
                                    vos_release_fn release, void *release_context,
                                    vos_boot_result *result);

#endif
