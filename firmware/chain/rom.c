// SPDX-License-Identifier: Apache-2.0
// The RoT ROM body of the target chain (docs/implementation/contracts/
// boot-handoff.md section 9.5): items 1 to 3, the entropy and root refusals,
// the stage-0 verification of the RoT runtime, its placement and item 4, and
// the state record the runtime reads.
//
// One translation unit with the bound sources included unchanged, as
// firmware/harness/rot_release_target.c composes them, and the bring-up
// release's measurement and byte helpers. The assembly beside it
// (rom_entry.s, composed by tools/vos/chain_rot.py) reads the OTP, entropy,
// boot-control and counter doors into a vos_chain_rot_inputs record, binds
// every argument below to a bounded capability, and on release enters the
// runtime; this body touches no door.
#include "../crypto/keccak.c"
#include "../crypto/slh256s.c"
#define VOS_BOOT_TARGET 1
#define VOS_BOOT_TARGET_VERIFY vos_boot_slh256s_verify
#include "../rot/boot_verify.c"
#include "chain_common.c"

// Every refusal zeroes the runtime region, leaves the state record's magic
// zero and writes the capture head with the verdict (section 9.5, step 10).
static uint64_t rom_refuse(uint64_t verdict, const vos_measurements *m,
                           const vos_chain_stage *stage, uint8_t *runtime_region,
                           uint64_t runtime_region_bytes, uint8_t *state, uint8_t *capture) {
  zero_bytes(runtime_region, runtime_region_bytes);
  zero_bytes(state, VOS_CHAIN_STATE_BYTES);
  write_u64(capture + VOS_CHAIN_CAPTURE_VERDICT_AT, verdict);
  write_u64(capture + VOS_CHAIN_CAPTURE_PHASE_AT, VOS_CHAIN_PHASE_ROM);
  chain_capture_measurements(capture, m);
  if (stage->digest_computed) {
    copy_bytes(capture + VOS_CHAIN_CAPTURE_RUNTIME_DIGEST_AT, stage->digest, VOS_BOOT_DIGEST_BYTES);
  }
  chain_capture_state(capture, state);
  return verdict;
}

uint64_t vos_chain_rom(const vos_chain_rot_inputs *inputs, const vos_chain_rom_policy *policy,
                       const uint8_t *store, uint64_t store_len, uint8_t *runtime_region,
                       uint64_t runtime_region_bytes, uint8_t *state, uint8_t *capture) {
  vos_measurements m;
  vos_chain_stage stage;
  vos_measure_reset(&m);
  stage.header_read = 0;
  stage.digest_computed = 0;
  zero_bytes(capture, VOS_CHAIN_CAPTURE_HEAD_BYTES);

  // What the assembly read, as read.
  write_u64(capture + VOS_CHAIN_CAPTURE_LIFECYCLE_AT, inputs->lifecycle);
  write_u64(capture + VOS_CHAIN_CAPTURE_HEALTH_AT, inputs->health_word);
  write_u64(capture + VOS_CHAIN_CAPTURE_BOOT_TARGET_AT, inputs->boot_target);
  write_u64(capture + VOS_CHAIN_CAPTURE_FLOOR_AT, inputs->floor);

  // Items 1 to 3 into the device register before any byte of any image is
  // read (R-09-037): the lifecycle index, the start-up verdict as 0 or 1
  // (R-09-006a: bit 32 set and bit 33 clear), the latch's one bit (R-09-029).
  uint8_t lifecycle = (uint8_t)inputs->lifecycle;
  uint8_t entropy = (uint8_t)((((inputs->health_word >> 32) & 1u) == 1u
                               && ((inputs->health_word >> 33) & 1u) == 0u) ? 1u : 0u);
  uint8_t target = (uint8_t)(inputs->boot_target & 1u);
  if (!vos_measure_extend(&m, 0, VOS_ITEM_LIFECYCLE, &lifecycle, 1)
      || !vos_measure_extend(&m, 0, VOS_ITEM_ENTROPY_VERDICT, &entropy, 1)
      || !vos_measure_extend(&m, 0, VOS_ITEM_BOOT_TARGET, &target, 1)) {
    return rom_refuse(VOS_CHAIN_REFUSE_MEASUREMENT_V, &m, &stage, runtime_region,
                      runtime_region_bytes, state, capture);
  }

  // The halt charges no attempt and writes no boot-control door; a lifecycle
  // state with no root admits nothing.
  if (!entropy) {
    return rom_refuse(VOS_CHAIN_REFUSE_ENTROPY_V, &m, &stage, runtime_region,
                      runtime_region_bytes, state, capture);
  }
  const uint8_t *root = chain_root(policy, inputs->lifecycle);
  if (root == NULL) {
    return rom_refuse(VOS_CHAIN_REFUSE_NO_ROOT_V, &m, &stage, runtime_region,
                      runtime_region_bytes, state, capture);
  }

  // Stage 0 under the same root as stage 1 (R-09-036a), against counter 0.
  uint64_t verdict = chain_verify_stage(VOS_BOOT_STAGE_ROT_RUNTIME,
                                        VOS_CHAIN_ROT_RUNTIME_REGION_BYTES, inputs->floor, root,
                                        store, store_len, runtime_region, runtime_region_bytes,
                                        &stage);
  if (verdict != VOS_CHAIN_RELEASE) {
    return rom_refuse(verdict, &m, &stage, runtime_region, runtime_region_bytes, state, capture);
  }
  if (!vos_measure_extend(&m, 1, VOS_ITEM_STAGE_ROT_RUNTIME, stage.digest, VOS_BOOT_DIGEST_BYTES)) {
    return rom_refuse(VOS_CHAIN_REFUSE_MEASUREMENT_V, &m, &stage, runtime_region,
                      runtime_region_bytes, state, capture);
  }

  // The state record the runtime reads, and the capture head's ROM fields.
  zero_bytes(state, VOS_CHAIN_STATE_BYTES);
  write_u64(state + VOS_CHAIN_STATE_MAGIC_AT, VOS_CHAIN_STATE_MAGIC);
  write_u64(state + VOS_CHAIN_STATE_VERSION_AT, VOS_CHAIN_STATE_VERSION);
  write_u64(state + VOS_CHAIN_STATE_RUN_KIND_AT, VOS_CHAIN_RUN_BOOT);
  write_u64(state + VOS_CHAIN_STATE_LIFECYCLE_AT, inputs->lifecycle);
  write_u64(state + VOS_CHAIN_STATE_ENTROPY_AT, entropy);
  write_u64(state + VOS_CHAIN_STATE_BOOT_TARGET_AT, target);
  write_u64(state + VOS_CHAIN_STATE_FLOOR_AT, inputs->floor);
  chain_state_measurements(state, &m);

  write_u64(capture + VOS_CHAIN_CAPTURE_VERDICT_AT, VOS_CHAIN_RELEASE);
  write_u64(capture + VOS_CHAIN_CAPTURE_PHASE_AT, VOS_CHAIN_PHASE_ROM);
  chain_capture_measurements(capture, &m);
  copy_bytes(capture + VOS_CHAIN_CAPTURE_RUNTIME_DIGEST_AT, stage.digest, VOS_BOOT_DIGEST_BYTES);
  chain_capture_state(capture, state);
  return VOS_CHAIN_RELEASE;
}
