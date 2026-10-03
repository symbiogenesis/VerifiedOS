// SPDX-License-Identifier: Apache-2.0
// The target chain composition of docs/implementation/contracts/boot-handoff.md
// section 9: the constants, verdicts, records and C entry points the four chain
// lanes (model doors; RoT ROM and runtime; M-mode chain stage and kernel stage;
// hosted campaign) share. This header owns the chain's constants as vos_boot.h
// owns the bring-up composition's; `run.py boot-handoff layout` holds section 9's
// tables against it. It reuses vos_boot.h's names and changes none of them.
//
// Nothing under firmware/include/ or firmware/crypto/ may change for the chain:
// M7.1f's staged manifest (firmware/crypto/target/manifest.json) binds those
// trees byte for byte, and the chain's verifier identity freeze (section 9.13)
// is an equality with that manifest. Chain C lives beside this header and
// includes the bound sources unchanged.
#ifndef VOS_CHAIN_H
#define VOS_CHAIN_H

#include <stddef.h>
#include <stdint.h>

#include "vos_boot.h"

// ---------------------------------------------------------------------------
// The RoT side of the composition. Every window is in the one address map both
// compositions share (model/config/verifiedos-rot.json, verifiedos.json); the
// store windows stand for the raw-NAND boot region (R-09-004) and the capture
// window for the RoT's view of main SRAM and its retained state, as the
// contract's section 9.2 says. Composition constants, not architecture.

// The RoT state record: what the ROM leaves for the runtime and what persists
// between RoT runs (the measurement registers and log, the boot inputs).
#define VOS_CHAIN_ROT_STATE_BASE 0x80380000u
#define VOS_CHAIN_ROT_STATE_WINDOW_BYTES 0x1000u
// The RoT runtime execute region: where the ROM places stage 0 and enters it.
// The image's data half starts at DATA_AT; text and data are measured as one
// flat payload from the base to the end of the data.
#define VOS_CHAIN_ROT_RUNTIME_BASE 0x80400000u
#define VOS_CHAIN_ROT_RUNTIME_REGION_BYTES 0x40000u
#define VOS_CHAIN_ROT_RUNTIME_DATA_AT 0x20000u
// The capture window: the RoT run's exported bytes (section 9.11).
#define VOS_CHAIN_ROT_CAPTURE_BASE 0x80500000u
#define VOS_CHAIN_ROT_CAPTURE_WINDOW_BYTES 0x80000u
// The boot-store windows: the stage-0 image, and the A, B and recovery stage-1
// images (R-09-006, R-09-028, R-09-029).
#define VOS_CHAIN_STORE_RUNTIME_BASE 0x80600000u
#define VOS_CHAIN_STORE_RUNTIME_BYTES 0x80000u
#define VOS_CHAIN_STORE_A_BASE 0x80700000u
#define VOS_CHAIN_STORE_B_BASE 0x80780000u
#define VOS_CHAIN_STORE_RECOVERY_BASE 0x80800000u
#define VOS_CHAIN_STORE_MMODE_BYTES 0x80000u

// ---------------------------------------------------------------------------
// The main-die side. The released core starts at the M-mode load base, which is
// the composition's reset vector and a constant, never a header field.

#define VOS_CHAIN_MMODE_LOAD_BASE 0x80000000u
#define VOS_CHAIN_MMODE_REGION_BYTES 0x40000u
#define VOS_CHAIN_MMODE_DATA_AT 0x20000u
#define VOS_CHAIN_HANDOFF_BASE 0x80040000u
// The item-6 mailbox: the M-mode stage's request, then the RoT's response.
#define VOS_CHAIN_MAILBOX_BASE 0x80041000u
#define VOS_CHAIN_MAILBOX_REQUEST_AT 0u
#define VOS_CHAIN_MAILBOX_RESPONSE_AT 256u
#define VOS_CHAIN_MAILBOX_BYTES 512u
// The M-mode chain stage's own exported record (section 9.11).
#define VOS_CHAIN_MMODE_CAPTURE_BASE 0x80042000u
// The main-die run's signature region: the mailbox window and the M-mode
// capture window, 0x1000 bytes each.
#define VOS_CHAIN_MAIN_SIGNATURE_BYTES 0x2000u
// The kernel stage's input window (the separately signed stage-2 image) and the
// region the M-mode stage places it in.
#define VOS_CHAIN_KERNEL_STORE_BASE 0x80080000u
#define VOS_CHAIN_KERNEL_STORE_BYTES 0x20000u
#define VOS_CHAIN_KERNEL_LOAD_BASE 0x80100000u
#define VOS_CHAIN_KERNEL_REGION_BYTES 0x10000u
// The kernel stage's fixed layout inside its region (section 9.3): the M-mode
// stage derives the kernel-entry state from these constants and reads no entry
// point or extent from the image.
#define VOS_CHAIN_KERNEL_TEXT_AT 0u
#define VOS_CHAIN_KERNEL_TEXT_BYTES 0x1000u
#define VOS_CHAIN_KERNEL_ENTRY_AT 0u
#define VOS_CHAIN_KERNEL_TRAP_AT 0x800u
#define VOS_CHAIN_KERNEL_DATA_AT 0x1000u
#define VOS_CHAIN_KERNEL_DATA_BYTES 0x400u
#define VOS_CHAIN_KERNEL_STACK_AT 0x1400u
#define VOS_CHAIN_KERNEL_STACK_BYTES 0x400u
#define VOS_CHAIN_KERNEL_ROOT_TABLE_AT 0x1800u
#define VOS_CHAIN_KERNEL_ROOT_TABLE_BYTES 8u
#define VOS_CHAIN_KERNEL_INIT_AT 0x1840u
#define VOS_CHAIN_KERNEL_INIT_BYTES VOS_INIT_HEADER_BYTES
// The main-die run's HTIF word: the kernel data extent's first word, which both
// the M-mode stage's refusals and the kernel stage's report write.
#define VOS_CHAIN_TOHOST_BASE (VOS_CHAIN_KERNEL_LOAD_BASE + VOS_CHAIN_KERNEL_DATA_AT)

// ---------------------------------------------------------------------------
// The stage-2 header (section 9.3): section 4's field order with ML-DSA-87's
// sizes (FIPS 204), verified above the ROM (R-05-058c, R-09-002). The reader
// accepting it is the M-mode stage, whose constants these are; it refuses every
// other stage before reading further, so no field locates another.

#define VOS_CHAIN_KSTAGE_MAGIC 0x314E52454B534F56u  // the bytes "VOSKERN1"
#define VOS_CHAIN_KSTAGE_SIGNATURE_BYTES 4627u
#define VOS_CHAIN_KSTAGE_PUBLIC_KEY_BYTES 2592u
#define VOS_CHAIN_KSTAGE_SIGNED_BYTES VOS_BOOT_HDR_SIGNATURE
#define VOS_CHAIN_KSTAGE_HEADER_BYTES (VOS_BOOT_HDR_SIGNATURE + VOS_CHAIN_KSTAGE_SIGNATURE_BYTES)

// The three stage-1 payloads end in one of these eight-byte tags, read by
// nothing on the target: they make the slots' measurements distinct.
#define VOS_CHAIN_SLOT_TAG_BYTES 8u
#define VOS_CHAIN_SLOT_TAG_A "VOSSLOTA"
#define VOS_CHAIN_SLOT_TAG_B "VOSSLOTB"
#define VOS_CHAIN_SLOT_TAG_RECOVERY "VOSRCVRY"

// ---------------------------------------------------------------------------
// Boot counting and selection (R-09-028, R-09-029; proofs/RotFirmware.v).

#define VOS_CHAIN_SLOT_A 0u
#define VOS_CHAIN_SLOT_B 1u
#define VOS_CHAIN_SLOT_RECOVERY 2u
#define VOS_CHAIN_BOOT_ATTEMPT_BOUND 3u

// The boot-control window the model adds to the RoT device set (section 9.4).
// model/model/sys/rot.sail owns the offsets as `ROT_BOOT_*`; the base is the
// composition's `platform.boot_control.base`. Every door is a doubleword.
#define VOS_CHAIN_BOOT_CONTROL_BASE 0x2A00000u
#define VOS_CHAIN_BOOT_CONTROL_BYTES 0x1000u
#define VOS_CHAIN_DOOR_BOOT_TARGET 0u  // read: the latched boot-time signal's one bit
#define VOS_CHAIN_DOOR_SLOT 8u         // read/write: the active slot, 0 or 1
#define VOS_CHAIN_DOOR_ATTEMPTS 16u    // read/write: the active slot's attempt count
#define VOS_CHAIN_DOOR_RELEASE 24u     // write 1: release the boot core; the run ends
#define VOS_CHAIN_DOOR_BYTES 32u
#define VOS_CHAIN_RELEASE_WORD 1u

// ---------------------------------------------------------------------------
// The bring-up reset table (section 9.6). Not Q33's production table: three
// steps, each an action, a ready indication over an existing RoT device and the
// watchdog window as its timeout, with a pet point at each completion.

#define VOS_CHAIN_RESET_STEPS 3u
#define VOS_CHAIN_STEP_ARM 0u      // action: arm the watchdog; ready: a nonzero challenge
#define VOS_CHAIN_STEP_ENTROPY 1u  // ready: health word bit 32 set and bit 33 clear
#define VOS_CHAIN_STEP_FLOOR 2u    // ready: counter 0 nonzero

// The external slow clock's host period for each run kind (section 9.10), in
// nanoseconds per tick: an emulation fact handed to `--rot-slow-clock-ns`.
#define VOS_CHAIN_SLOW_CLOCK_BOOT_NS 160000000u
#define VOS_CHAIN_SLOW_CLOCK_WATCHDOG_NS 1000000u
// The instruction limit of the detached-clock control run.
#define VOS_CHAIN_CONTROL_INST_LIMIT 50000000u

// ---------------------------------------------------------------------------
// Measurement in the chain: items 1 to 6 of vos_boot.h's codes, in order.

#define VOS_CHAIN_MEASURE_EXTENSIONS 6u
_Static_assert(VOS_MEASURE_LOG_CAPACITY >= VOS_CHAIN_MEASURE_EXTENSIONS,
               "the measurement log cannot hold the chain's six extensions");

// ---------------------------------------------------------------------------
// Verdicts. Codes 0 to 13 are vos_boot_verdict's, with the same names and
// meanings; the chain adds four. A code is reported as a bounded integer; the
// M-mode stage reports a refusal as HTIF exit MMODE_EXIT_BASE plus its code.

#define VOS_CHAIN_REFUSE_STATE 14u     // the RoT state record's magic, version or run kind
#define VOS_CHAIN_REFUSE_RECORD 15u    // the handoff record's magic or version at the M-mode stage
#define VOS_CHAIN_REFUSE_REQUEST 16u   // an item-6 request not for stage 2, or a log that cannot record it
#define VOS_CHAIN_REFUSE_RESPONSE 17u  // an item-6 response that does not bind this request
#define VOS_CHAIN_MMODE_EXIT_BASE 64u

typedef enum {
  VOS_CHAIN_RELEASE = VOS_BOOT_RELEASE,
  VOS_CHAIN_REFUSE_ENTROPY_V = VOS_BOOT_REFUSE_ENTROPY,
  VOS_CHAIN_REFUSE_NO_ROOT_V = VOS_BOOT_REFUSE_NO_ROOT,
  VOS_CHAIN_REFUSE_TRUNCATED_V = VOS_BOOT_REFUSE_TRUNCATED,
  VOS_CHAIN_REFUSE_MAGIC_V = VOS_BOOT_REFUSE_MAGIC,
  VOS_CHAIN_REFUSE_STAGE_V = VOS_BOOT_REFUSE_STAGE,
  VOS_CHAIN_REFUSE_OFFSET_V = VOS_BOOT_REFUSE_OFFSET,
  VOS_CHAIN_REFUSE_LENGTH_V = VOS_BOOT_REFUSE_LENGTH,
  VOS_CHAIN_REFUSE_FLOOR_V = VOS_BOOT_REFUSE_FLOOR,
  VOS_CHAIN_REFUSE_NO_VERIFIER_V = VOS_BOOT_REFUSE_NO_VERIFIER,
  VOS_CHAIN_REFUSE_SIGNATURE_V = VOS_BOOT_REFUSE_SIGNATURE,
  VOS_CHAIN_REFUSE_PLACEMENT_V = VOS_BOOT_REFUSE_PLACEMENT,
  VOS_CHAIN_REFUSE_DIGEST_V = VOS_BOOT_REFUSE_DIGEST,
  VOS_CHAIN_REFUSE_MEASUREMENT_V = VOS_BOOT_REFUSE_MEASUREMENT,
  VOS_CHAIN_REFUSE_STATE_V = VOS_CHAIN_REFUSE_STATE,
  VOS_CHAIN_REFUSE_RECORD_V = VOS_CHAIN_REFUSE_RECORD,
  VOS_CHAIN_REFUSE_REQUEST_V = VOS_CHAIN_REFUSE_REQUEST,
  VOS_CHAIN_REFUSE_RESPONSE_V = VOS_CHAIN_REFUSE_RESPONSE,
} vos_chain_verdict;

// The phase a RoT run reached, and a RoT run's kind.
#define VOS_CHAIN_PHASE_ROM 0u
#define VOS_CHAIN_PHASE_RUNTIME 1u
#define VOS_CHAIN_PHASE_RELEASED 2u
#define VOS_CHAIN_PHASE_SERVICE 3u
#define VOS_CHAIN_RUN_BOOT 1u
#define VOS_CHAIN_RUN_SERVICE 2u

// ---------------------------------------------------------------------------
// The RoT state record (section 9.5), at ROT_STATE_BASE. Integers are one
// little-endian doubleword. The ROM writes it; the runtime and the item-6
// service read and extend it; the capture exports it, and the harness carries
// it into the next RoT run, standing for the RoT's retained SRAM.

#define VOS_CHAIN_STATE_MAGIC 0x3154415453534F56u  // the bytes "VOSSTAT1"
#define VOS_CHAIN_STATE_VERSION 1u
#define VOS_CHAIN_STATE_MAGIC_AT 0u
#define VOS_CHAIN_STATE_VERSION_AT 8u
#define VOS_CHAIN_STATE_RUN_KIND_AT 16u
#define VOS_CHAIN_STATE_LIFECYCLE_AT 24u
#define VOS_CHAIN_STATE_ENTROPY_AT 32u
#define VOS_CHAIN_STATE_BOOT_TARGET_AT 40u
#define VOS_CHAIN_STATE_FLOOR_AT 48u
#define VOS_CHAIN_STATE_MEASURE_COUNT_AT 56u
#define VOS_CHAIN_STATE_LOG_AT 64u
#define VOS_CHAIN_STATE_LOG_BYTES 16u
#define VOS_CHAIN_STATE_GENERATION_AT 80u
#define VOS_CHAIN_STATE_DEVICE_AT 112u
#define VOS_CHAIN_STATE_BYTES 256u
// In a service run the harness places the item-6 request here, inside the
// state window and after the record.
#define VOS_CHAIN_STATE_REQUEST_AT 256u

// ---------------------------------------------------------------------------
// The item-6 exchange (section 9.7).

#define VOS_CHAIN_REQUEST_MAGIC 0x51364D5449534F56u  // the bytes "VOSITM6Q"
#define VOS_CHAIN_REQUEST_MAGIC_AT 0u
#define VOS_CHAIN_REQUEST_STAGE_AT 8u
#define VOS_CHAIN_REQUEST_DIGEST_AT 16u
#define VOS_CHAIN_REQUEST_BYTES 64u

#define VOS_CHAIN_RESPONSE_MAGIC 0x52364D5449534F56u  // the bytes "VOSITM6R"
#define VOS_CHAIN_RESPONSE_MAGIC_AT 0u
#define VOS_CHAIN_RESPONSE_STAGE_AT 8u
#define VOS_CHAIN_RESPONSE_DIGEST_AT 16u
#define VOS_CHAIN_RESPONSE_GENERATION_AT 48u
#define VOS_CHAIN_RESPONSE_DEVICE_AT 80u
#define VOS_CHAIN_RESPONSE_CHAIN_AT 112u
#define VOS_CHAIN_RESPONSE_MEASURE_COUNT_AT 144u
#define VOS_CHAIN_RESPONSE_LOG_AT 152u
#define VOS_CHAIN_RESPONSE_BYTES 256u

// ---------------------------------------------------------------------------
// The RoT capture (section 9.11): the head, then the handoff record, the item-6
// response and request, the state record as the run left it, and the placed
// M-mode window. Fields the run does not reach are zero.

#define VOS_CHAIN_CAPTURE_VERDICT_AT 0u
#define VOS_CHAIN_CAPTURE_PHASE_AT 8u
#define VOS_CHAIN_CAPTURE_RELEASED_AT 16u
#define VOS_CHAIN_CAPTURE_LIFECYCLE_AT 24u
#define VOS_CHAIN_CAPTURE_HEALTH_AT 32u
#define VOS_CHAIN_CAPTURE_BOOT_TARGET_AT 40u
#define VOS_CHAIN_CAPTURE_FLOOR_AT 48u
#define VOS_CHAIN_CAPTURE_SLOT_INITIAL_AT 56u
#define VOS_CHAIN_CAPTURE_ATTEMPTS_INITIAL_AT 64u
#define VOS_CHAIN_CAPTURE_SLOT_SELECTED_AT 72u
#define VOS_CHAIN_CAPTURE_SLOT_FINAL_AT 80u
#define VOS_CHAIN_CAPTURE_ATTEMPTS_FINAL_AT 88u
#define VOS_CHAIN_CAPTURE_PETS_ACCEPTED_AT 96u
#define VOS_CHAIN_CAPTURE_PETS_SKIPPED_AT 104u
#define VOS_CHAIN_CAPTURE_NONCE_AT_ARM_AT 112u
#define VOS_CHAIN_CAPTURE_BITTEN_AT 120u
#define VOS_CHAIN_CAPTURE_TICKS_AT_END_AT 128u
#define VOS_CHAIN_CAPTURE_STEPS_COMPLETED_AT 136u
#define VOS_CHAIN_CAPTURE_MEASURE_COUNT_AT 144u
#define VOS_CHAIN_CAPTURE_LOG_AT 152u
#define VOS_CHAIN_CAPTURE_GENERATION_AT 168u
#define VOS_CHAIN_CAPTURE_DEVICE_AT 200u
#define VOS_CHAIN_CAPTURE_CHAIN_AT 232u
#define VOS_CHAIN_CAPTURE_RUNTIME_DIGEST_AT 264u
#define VOS_CHAIN_CAPTURE_MMODE_DIGEST_AT 296u
#define VOS_CHAIN_CAPTURE_MMODE_SECURITY_VERSION_AT 328u
#define VOS_CHAIN_CAPTURE_MMODE_PAYLOAD_LENGTH_AT 336u
#define VOS_CHAIN_CAPTURE_HEAD_BYTES 0x200u
#define VOS_CHAIN_CAPTURE_RECORD_AT 0x200u
#define VOS_CHAIN_CAPTURE_RESPONSE_AT 0x300u
#define VOS_CHAIN_CAPTURE_REQUEST_AT 0x400u
#define VOS_CHAIN_CAPTURE_STATE_AT 0x500u
#define VOS_CHAIN_CAPTURE_WINDOW_AT 0x1000u
#define VOS_CHAIN_CAPTURE_BYTES (VOS_CHAIN_CAPTURE_WINDOW_AT + VOS_CHAIN_MMODE_REGION_BYTES)

// The M-mode chain stage's capture, at MMODE_CAPTURE_BASE.
#define VOS_CHAIN_MCAPTURE_VERDICT_AT 0u
#define VOS_CHAIN_MCAPTURE_KERNEL_DIGEST_AT 8u
#define VOS_CHAIN_MCAPTURE_SECURITY_VERSION_AT 40u
#define VOS_CHAIN_MCAPTURE_PAYLOAD_LENGTH_AT 48u
#define VOS_CHAIN_MCAPTURE_REQUEST_WRITTEN_AT 56u
#define VOS_CHAIN_MCAPTURE_RESPONSE_BOUND_AT 64u
#define VOS_CHAIN_MCAPTURE_BYTES 128u

_Static_assert(VOS_CHAIN_KSTAGE_HEADER_BYTES == 4699u, "the stage-2 header is 72 + 4627 bytes");
_Static_assert(VOS_CHAIN_CAPTURE_MMODE_PAYLOAD_LENGTH_AT + 8u <= VOS_CHAIN_CAPTURE_HEAD_BYTES,
               "the capture head overruns its extent");
_Static_assert(VOS_CHAIN_CAPTURE_BYTES <= VOS_CHAIN_ROT_CAPTURE_WINDOW_BYTES,
               "the capture overruns its window");
_Static_assert(VOS_CHAIN_STATE_REQUEST_AT + VOS_CHAIN_REQUEST_BYTES <= VOS_CHAIN_ROT_STATE_WINDOW_BYTES,
               "the state window cannot hold the record and the request");
_Static_assert(VOS_CHAIN_KERNEL_INIT_AT + VOS_CHAIN_KERNEL_INIT_BYTES <= VOS_CHAIN_KERNEL_REGION_BYTES,
               "the kernel layout overruns its region");
_Static_assert(VOS_BOOT_HEADER_BYTES + VOS_CHAIN_MMODE_REGION_BYTES <= VOS_CHAIN_STORE_MMODE_BYTES,
               "a stage-1 store window cannot hold a region-filling image");
_Static_assert(VOS_BOOT_HEADER_BYTES + VOS_CHAIN_ROT_RUNTIME_REGION_BYTES <= VOS_CHAIN_STORE_RUNTIME_BYTES,
               "the stage-0 store window cannot hold a region-filling image");
_Static_assert(VOS_CHAIN_KSTAGE_HEADER_BYTES + VOS_CHAIN_KERNEL_REGION_BYTES <= VOS_CHAIN_KERNEL_STORE_BYTES,
               "the kernel store window cannot hold a region-filling image");

// ---------------------------------------------------------------------------
// The C entry points (section 9.11's work packages). Every body is pure over
// the windows it is handed: the assembly beside it reads and writes the RoT
// doors and the watchdog, because the contained compiler lowers no volatile
// access, and records what it read in the capture. Pointers are bounded
// capabilities on the target; lengths are the windows' extents.

// What the assembly read from the RoT's doors before the ROM or runtime body
// runs. `health_word` is the TRNG health door after the start-up tests.
typedef struct {
  uint64_t lifecycle;
  uint64_t health_word;
  uint64_t boot_target;
  uint64_t floor;
  uint64_t slot;
  uint64_t attempts;
} vos_chain_rot_inputs;

// The ROM root per lifecycle state (R-09-036), NULL where the state accepts
// none. The same roots verify the RoT runtime and the M-mode image (R-09-036a).
typedef struct {
  const uint8_t *root[VOS_LIFECYCLE_COUNT];
} vos_chain_rom_policy;

// The ROM body (section 9.5): items 1 to 3, the entropy and root refusals, the
// stage-0 verification, placement and item 4, the state record. Returns the
// verdict it also writes at `capture` offset CAPTURE_VERDICT_AT; on release the
// caller enters the runtime at ROT_RUNTIME_BASE and on a refusal ends the run.
uint64_t vos_chain_rom(const vos_chain_rot_inputs *inputs, const vos_chain_rom_policy *policy,
                       const uint8_t *store, uint64_t store_len, uint8_t *runtime_region,
                       uint64_t runtime_region_bytes, uint8_t *state, uint8_t *capture);

// Selection and counting (section 9.6), pure: from the latch and the
// boot-control values, the slot to verify and the values to write to the slot
// and attempt doors before that verification. Returns the selected slot code.
typedef struct {
  uint64_t slot;      // the value to write to DOOR_SLOT
  uint64_t attempts;  // the value to write to DOOR_ATTEMPTS
  uint64_t reverted;  // 1 where the bound was reached and the other slot taken
  uint64_t charged;   // 1 where an attempt was charged
} vos_chain_selection;

uint64_t vos_chain_select(uint64_t boot_target, uint64_t slot, uint64_t attempts,
                          vos_chain_selection *out);

// Whether a pet is due at a pet point: 1 inside [early, late], 0 before the
// early bound. A pet after the late bound is unreachable, the bite having ended
// the run.
uint64_t vos_chain_pet_due(uint64_t ticks, uint64_t early, uint64_t late);

// The runtime's verification body (section 9.6): the selected stage-1 image's
// header, floor, SLH-DSA signature under the state's lifecycle root, placement
// into `mmode_window`, measurement, item 5, the handoff record into `record`.
uint64_t vos_chain_runtime_verify(uint8_t *state, const vos_chain_rom_policy *policy,
                                  uint64_t selected, const uint8_t *store, uint64_t store_len,
                                  uint8_t *mmode_window, uint64_t mmode_window_bytes,
                                  uint8_t *record, uint8_t *capture);

// The item-6 service (section 9.7): extend the state's generation register with
// item 6 over the request's digest and write the response.
uint64_t vos_chain_service_item6(uint8_t *state, const uint8_t *request, uint8_t *response,
                                 uint8_t *capture);

// The M-mode chain stage's body (section 9.8): the record's magic and version,
// the stage-2 header, floor, ML-DSA-87 signature under `root_key`, placement
// into `kernel_region`, measurement, the request, the response's binding. On
// VOS_CHAIN_RELEASE the assembly installs section 6's state and enters the kernel.
uint64_t vos_chain_mmode(const uint8_t *record, const uint8_t *root_key, const uint8_t *store,
                         uint64_t store_len, uint8_t *kernel_region, uint64_t kernel_region_bytes,
                         uint8_t *request, const uint8_t *response, uint8_t *capture);

#endif
