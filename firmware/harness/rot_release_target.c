// SPDX-License-Identifier: Apache-2.0
// The existing release implementation and real signature policy on the RoT
// hart. The composition supplies bounded capabilities, including device doors.
// The emulator's one-hart boundary exports the placed bytes only after this
// program has called the release hook. It supplies no physical reset door.
#include "../crypto/keccak.c"
#include "../crypto/slh256s.c"
#define VOS_BOOT_TARGET 1
#define VOS_BOOT_TARGET_VERIFY vos_boot_slh256s_verify
#include "../rot/boot_verify.c"

#define TARGET_METADATA_BYTES 128u
#define TARGET_HANDOFF_AT TARGET_METADATA_BYTES
#define TARGET_IMAGE_AT (TARGET_HANDOFF_AT + VOS_HANDOFF_BYTES)

static void target_release(uint64_t *count) {
  (*count)++;
}

// The assembly entry reads lifecycle, entropy, floor and watchdog doors on
// this RoT hart into the bounded parameter record. C never receives a host
// probe result. The selected compiler does not yet lower volatile accesses.
int main(const uint8_t *public_key, const uint8_t *image, uint8_t *output,
         const uint64_t *parameters) {
  zero_bytes(output, TARGET_IMAGE_AT + VOS_BRINGUP_MMODE_REGION_BYTES);
  uint64_t release_count = 0;
  for (unsigned i = 0; i < VOS_HANDOFF_BYTES; i++) {
    output[TARGET_HANDOFF_AT + i] = 0x5a;
  }
  vos_rot_inputs inputs;
  inputs.lifecycle = (uint8_t)parameters[2];
  inputs.entropy_ok = (uint8_t)(((parameters[3] >> 32) & 1) && !((parameters[3] >> 33) & 1));
  inputs.boot_target = (uint8_t)parameters[1];
  inputs.floor = parameters[4];
  write_u64(output + 16, inputs.lifecycle);
  write_u64(output + 24, parameters[3]);
  write_u64(output + 32, inputs.floor);
  write_u64(output + 40, inputs.boot_target);
  write_u64(output + 48, parameters[5]);
  vos_rot_policy policy;
  for (unsigned i = 0; i < VOS_LIFECYCLE_COUNT; i++) policy.root[i] = NULL;
  policy.root[VOS_LIFECYCLE_PRODUCTION] = public_key;
  policy.verify_context = NULL;
  policy.load_base = VOS_BRINGUP_MMODE_LOAD_BASE;
  policy.region_bytes = VOS_BRINGUP_MMODE_REGION_BYTES;
  vos_sram_windows windows;
  windows.image = output + TARGET_IMAGE_AT;
  windows.image_bytes = VOS_BRINGUP_MMODE_REGION_BYTES;
  windows.handoff = output + TARGET_HANDOFF_AT;
  windows.handoff_bytes = VOS_HANDOFF_BYTES;
  vos_boot_result result;
  vos_boot_verdict verdict = vos_rot_prepare_mmode(image, parameters[0], &inputs,
      &policy, &windows, &result);
  if (verdict == VOS_BOOT_RELEASE) target_release(&release_count);
  write_u64(output, verdict);
  write_u64(output + 8, release_count);
  write_u64(output + 56, result.measured.count);
  for (unsigned i = 0; i < result.measured.count; i++) {
    output[64 + i] = result.measured.log[i];
  }
  return (int)verdict;
}
