// SPDX-License-Identifier: Apache-2.0
// The RoT runtime of the target chain, stage 0 (docs/implementation/contracts/
// boot-handoff.md sections 9.6 and 9.7): the state check, the selection and
// counting of R-09-028 and R-09-029, the pet decision, the stage-1
// verification with item 5 and the handoff record, and the item-6 service.
//
// One translation unit with the bound sources included unchanged, as the ROM
// composes them. The assembly beside it (runtime_entry.s) is the program's
// entry and its only door user: it arms the watchdog, walks the bring-up reset
// table, reads the tick, challenge and boot-control doors, pets, writes the
// slot, attempt and release doors and records what it read in the capture,
// calling these pure bodies between those acts.
#include "../crypto/keccak.c"
#include "../crypto/slh256s.c"
#define VOS_BOOT_TARGET 1
#define VOS_BOOT_TARGET_VERIFY vos_boot_slh256s_verify
#include "../rot/boot_verify.c"
#include "chain_common.c"

// Selection and counting (section 9.6, RotFirmware.v). With the latch set the
// recovery generation is selected and the A/B state is left as read, charging
// nothing (F-738). Otherwise a count at or above the bound reverts to the other
// slot with a count of zero (`spec_revert`, RevertsPastTheBound), and the
// attempt is then charged (`spec_charge`'s ordinary-failure arm,
// AdmitsBelowTheBound) before the verification it gates.
uint64_t vos_chain_select(uint64_t boot_target, uint64_t slot, uint64_t attempts,
                          vos_chain_selection *out) {
  if ((boot_target & 1u) != 0u) {
    out->slot = slot;
    out->attempts = attempts;
    out->reverted = 0;
    out->charged = 0;
    return VOS_CHAIN_SLOT_RECOVERY;
  }
  uint64_t active = slot;
  uint64_t count = attempts;
  out->reverted = 0;
  if (count >= VOS_CHAIN_BOOT_ATTEMPT_BOUND) {
    active = active == VOS_CHAIN_SLOT_A ? VOS_CHAIN_SLOT_B : VOS_CHAIN_SLOT_A;
    count = 0;
    out->reverted = 1;
  }
  out->slot = active;
  out->attempts = count + 1u;
  out->charged = 1;
  return active;
}

// The bring-up reset table's ready indications (section 9.6), over the door
// value the assembly polled for `step`: step.arm's challenge door, step.entropy's
// health word and step.floor's counter 0. The assembly polls until this answers
// 1 and never pets while it waits. Section 9.10's stall mutant rewrites the
// completion bit read below to one the health word never sets.
uint64_t vos_chain_step_ready(uint64_t step, uint64_t value) {
  if (step == VOS_CHAIN_STEP_ENTROPY) {
    uint64_t completed = (value >> 32) & 1u;  // the start-up tests completed for every source
    uint64_t stopped = (value >> 33) & 1u;    // the fail-stop latched
    return (completed == 1u && stopped == 0u) ? 1u : 0u;
  }
  return value != 0u ? 1u : 0u;
}

// A pet is due inside the window and never before it: an early pet is a bite
// (R-15-240). After the late bound nothing runs, the bite having ended the run.
// Section 9.10's early-pet mutant answers 1 without consulting the tick count,
// so the first pet point, step.arm's completion, pets early.
uint64_t vos_chain_pet_due(uint64_t ticks, uint64_t early, uint64_t late) {
  return (ticks >= early && ticks <= late) ? 1u : 0u;
}

// Every runtime refusal zeroes the M-mode window, leaves the record slot zero
// and writes the capture head with the verdict and `phase.runtime`.
static uint64_t runtime_refuse(uint64_t verdict, uint8_t *mmode_window,
                               uint64_t mmode_window_bytes, uint8_t *record, uint8_t *capture) {
  zero_bytes(mmode_window, mmode_window_bytes);
  zero_bytes(record, VOS_HANDOFF_BYTES);
  write_u64(capture + VOS_CHAIN_CAPTURE_VERDICT_AT, verdict);
  write_u64(capture + VOS_CHAIN_CAPTURE_PHASE_AT, VOS_CHAIN_PHASE_RUNTIME);
  write_u64(capture + VOS_CHAIN_CAPTURE_RELEASED_AT, 0);
  return verdict;
}

// The runtime's first act (section 9.6): a state record whose magic, version or
// run kind is not a boot run's refuses before the watchdog is armed.
uint64_t vos_chain_runtime_admit(const uint8_t *state, uint8_t *mmode_window,
                                 uint64_t mmode_window_bytes, uint8_t *record,
                                 uint8_t *capture) {
  if (chain_state_admits(state, VOS_CHAIN_RUN_BOOT)) {
    return VOS_CHAIN_RELEASE;
  }
  chain_capture_state(capture, state);
  return runtime_refuse(VOS_CHAIN_REFUSE_STATE_V, mmode_window, mmode_window_bytes, record,
                        capture);
}

uint64_t vos_chain_runtime_verify(uint8_t *state, const vos_chain_rom_policy *policy,
                                  uint64_t selected, const uint8_t *store, uint64_t store_len,
                                  uint8_t *mmode_window, uint64_t mmode_window_bytes,
                                  uint8_t *record, uint8_t *capture) {
  vos_measurements m;
  vos_chain_stage stage;
  chain_get_measurements(state, &m);
  stage.header_read = 0;
  stage.digest_computed = 0;
  write_u64(capture + VOS_CHAIN_CAPTURE_SLOT_SELECTED_AT, selected);

  // Section 3's steps 3 to 7 over the selected store window with the stage 1,
  // the M-mode region, the root the state's lifecycle accepts and the state's
  // floor.
  uint64_t lifecycle = read_u64(state + VOS_CHAIN_STATE_LIFECYCLE_AT);
  uint64_t floor = read_u64(state + VOS_CHAIN_STATE_FLOOR_AT);
  const uint8_t *root = chain_root(policy, lifecycle);
  uint64_t verdict = VOS_CHAIN_REFUSE_NO_ROOT_V;
  if (root != NULL) {
    verdict = chain_verify_stage(VOS_BOOT_STAGE_MMODE_IMAGE, VOS_CHAIN_MMODE_REGION_BYTES, floor,
                                 root, store, store_len, mmode_window, mmode_window_bytes, &stage);
  }
  if (verdict == VOS_CHAIN_RELEASE
      && !vos_measure_extend(&m, 1, VOS_ITEM_STAGE_MMODE_IMAGE, stage.digest,
                             VOS_BOOT_DIGEST_BYTES)) {
    verdict = VOS_CHAIN_REFUSE_MEASUREMENT_V;
  }
  if (stage.header_read) {
    write_u64(capture + VOS_CHAIN_CAPTURE_MMODE_SECURITY_VERSION_AT, stage.security_version);
    write_u64(capture + VOS_CHAIN_CAPTURE_MMODE_PAYLOAD_LENGTH_AT, stage.payload_length);
  }
  if (stage.digest_computed) {
    copy_bytes(capture + VOS_CHAIN_CAPTURE_MMODE_DIGEST_AT, stage.digest, VOS_BOOT_DIGEST_BYTES);
  }
  if (verdict != VOS_CHAIN_RELEASE) {
    // The registers as the ROM left them: no item 5 is extended.
    chain_capture_measurements(capture, &m);
    chain_capture_state(capture, state);
    return runtime_refuse(verdict, mmode_window, mmode_window_bytes, record, capture);
  }

  // The handoff record (sections 6 and 9.9) through the bring-up release's own
  // writer: the load base is the chain's, the generation register holds items
  // 4 and 5 and the device register items 1 to 3.
  vos_rot_inputs inputs;
  inputs.lifecycle = (uint8_t)lifecycle;
  inputs.entropy_ok = (uint8_t)read_u64(state + VOS_CHAIN_STATE_ENTROPY_AT);
  inputs.boot_target = (uint8_t)read_u64(state + VOS_CHAIN_STATE_BOOT_TARGET_AT);
  inputs.floor = floor;
  vos_rot_policy placement;
  for (unsigned i = 0; i < VOS_LIFECYCLE_COUNT; i++) {
    placement.root[i] = NULL;
  }
  placement.verify = NULL;
  placement.verify_context = NULL;
  placement.load_base = VOS_CHAIN_MMODE_LOAD_BASE;
  placement.region_bytes = VOS_CHAIN_MMODE_REGION_BYTES;
  vos_boot_result result;
  result.verdict = VOS_BOOT_RELEASE;
  result.security_version = stage.security_version;
  result.payload_length = stage.payload_length;
  result.digest_computed = 1;
  copy_bytes(result.image_digest, stage.digest, VOS_BOOT_DIGEST_BYTES);
  copy_bytes(result.measured.generation, m.generation, VOS_MEASURE_BYTES);
  copy_bytes(result.measured.device, m.device, VOS_MEASURE_BYTES);
  copy_bytes(result.measured.log, m.log, VOS_MEASURE_LOG_CAPACITY);
  result.measured.count = m.count;
  vos_measure_chain(&m, result.chain);
  write_handoff(record, &inputs, &placement, &result, inputs.entropy_ok, inputs.boot_target);

  // The state carries the registers after item 5 into the item-6 service run.
  chain_state_measurements(state, &m);
  write_u64(capture + VOS_CHAIN_CAPTURE_VERDICT_AT, VOS_CHAIN_RELEASE);
  write_u64(capture + VOS_CHAIN_CAPTURE_PHASE_AT, VOS_CHAIN_PHASE_RELEASED);
  chain_capture_measurements(capture, &m);
  chain_capture_state(capture, state);
  return VOS_CHAIN_RELEASE;
}

// The item-6 service (section 9.7): a `run.service` state record, a request
// for stage 2 and a log that can record item 6, then the generation register
// extended over the request's digest and the response that binds it.
uint64_t vos_chain_service_item6(uint8_t *state, const uint8_t *request, uint8_t *response,
                                 uint8_t *capture) {
  zero_bytes(response, VOS_CHAIN_RESPONSE_BYTES);
  write_u64(capture + VOS_CHAIN_CAPTURE_PHASE_AT, VOS_CHAIN_PHASE_SERVICE);
  copy_bytes(capture + VOS_CHAIN_CAPTURE_REQUEST_AT, request, VOS_CHAIN_REQUEST_BYTES);
  uint64_t verdict = VOS_CHAIN_RELEASE;
  vos_measurements m;
  vos_measure_reset(&m);
  if (!chain_state_admits(state, VOS_CHAIN_RUN_SERVICE)) {
    verdict = VOS_CHAIN_REFUSE_STATE_V;
  } else if (read_u64(request + VOS_CHAIN_REQUEST_MAGIC_AT) != VOS_CHAIN_REQUEST_MAGIC
             || read_u64(request + VOS_CHAIN_REQUEST_STAGE_AT) != VOS_BOOT_STAGE_CORE_KERNELS) {
    verdict = VOS_CHAIN_REFUSE_REQUEST_V;
  } else {
    chain_get_measurements(state, &m);
    if (!vos_measure_extend(&m, 1, VOS_ITEM_STAGE_CORE_KERNELS,
                            request + VOS_CHAIN_REQUEST_DIGEST_AT, VOS_BOOT_DIGEST_BYTES)) {
      verdict = VOS_CHAIN_REFUSE_REQUEST_V;
    }
  }
  write_u64(capture + VOS_CHAIN_CAPTURE_VERDICT_AT, verdict);
  if (verdict == VOS_CHAIN_RELEASE) {
    uint8_t chain[VOS_MEASURE_BYTES];
    vos_measure_chain(&m, chain);
    write_u64(response + VOS_CHAIN_RESPONSE_MAGIC_AT, VOS_CHAIN_RESPONSE_MAGIC);
    write_u64(response + VOS_CHAIN_RESPONSE_STAGE_AT,
              read_u64(request + VOS_CHAIN_REQUEST_STAGE_AT));
    copy_bytes(response + VOS_CHAIN_RESPONSE_DIGEST_AT, request + VOS_CHAIN_REQUEST_DIGEST_AT,
               VOS_BOOT_DIGEST_BYTES);
    chain_put_measurements(response, VOS_CHAIN_RESPONSE_MEASURE_COUNT_AT,
                           VOS_CHAIN_RESPONSE_LOG_AT, VOS_CHAIN_RESPONSE_GENERATION_AT,
                           VOS_CHAIN_RESPONSE_DEVICE_AT, &m);
    copy_bytes(response + VOS_CHAIN_RESPONSE_CHAIN_AT, chain, VOS_MEASURE_BYTES);
    chain_state_measurements(state, &m);
    chain_capture_measurements(capture, &m);
  }
  chain_capture_state(capture, state);
  return verdict;
}
