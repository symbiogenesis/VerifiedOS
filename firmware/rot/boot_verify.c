// SPDX-License-Identifier: Apache-2.0
// The RoT's measured release of the boot core into the M-mode stage
// (R-09-002, R-09-005, R-09-006, R-09-006a, R-09-025a, R-09-036, R-09-037), in
// the order docs/implementation/contracts/boot-handoff.md section 3 fixes.
//
// Integer-only C with no allocation, no library call and no loop whose bound is
// read from the image other than the declared payload length, which is checked
// against the composition's region before anything reads that far. The target
// build of this file waits on the purecap backend and M1.7's target path; the
// harness compiles it for the host and says so in every report.
#include "vos_boot.h"
#include "vos_keccak.h"

const char *vos_boot_verdict_name(vos_boot_verdict verdict) {
  switch (verdict) {
  case VOS_BOOT_RELEASE: return "release";
  case VOS_BOOT_REFUSE_ENTROPY: return "refuse-entropy";
  case VOS_BOOT_REFUSE_NO_ROOT: return "refuse-no-root";
  case VOS_BOOT_REFUSE_TRUNCATED: return "refuse-truncated";
  case VOS_BOOT_REFUSE_MAGIC: return "refuse-magic";
  case VOS_BOOT_REFUSE_STAGE: return "refuse-stage";
  case VOS_BOOT_REFUSE_OFFSET: return "refuse-offset";
  case VOS_BOOT_REFUSE_LENGTH: return "refuse-length";
  case VOS_BOOT_REFUSE_FLOOR: return "refuse-floor";
  case VOS_BOOT_REFUSE_NO_VERIFIER: return "refuse-no-verifier";
  case VOS_BOOT_REFUSE_SIGNATURE: return "refuse-signature";
  case VOS_BOOT_REFUSE_PLACEMENT: return "refuse-placement";
  case VOS_BOOT_REFUSE_DIGEST: return "refuse-digest";
  }
  return "refuse-unknown";
}

static uint64_t read_u64(const uint8_t *p) {
  uint64_t v = 0;
  for (unsigned i = 0; i < 8; i++) {
    v |= (uint64_t)p[i] << (8u * i);
  }
  return v;
}

static void write_u64(uint8_t *p, uint64_t v) {
  for (unsigned i = 0; i < 8; i++) {
    p[i] = (uint8_t)(v >> (8u * i));
  }
}

static void copy_bytes(uint8_t *to, const uint8_t *from, uint64_t len) {
  for (uint64_t i = 0; i < len; i++) {
    to[i] = from[i];
  }
}

static void zero_bytes(uint8_t *to, uint64_t len) {
  for (uint64_t i = 0; i < len; i++) {
    to[i] = 0;
  }
}

// Every byte is compared whatever the first difference, so the comparison's
// length does not depend on where two digests part.
static int equal_bytes(const uint8_t *a, const uint8_t *b, unsigned len) {
  uint8_t diff = 0;
  for (unsigned i = 0; i < len; i++) {
    diff = (uint8_t)(diff | (a[i] ^ b[i]));
  }
  return diff == 0;
}

void vos_measure_reset(vos_measurements *m) {
  zero_bytes(m->generation, VOS_MEASURE_BYTES);
  zero_bytes(m->device, VOS_MEASURE_BYTES);
  zero_bytes(m->log, VOS_MEASURE_LOG_CAPACITY);
  m->count = 0;
}

int vos_measure_extend(vos_measurements *m, int generation_register, uint8_t code,
                       const uint8_t *data, uint32_t len) {
  if (m->count >= VOS_MEASURE_LOG_CAPACITY) {
    return 0;
  }
  uint8_t *reg = generation_register ? m->generation : m->device;
  uint8_t len_bytes[4] = {(uint8_t)len, (uint8_t)(len >> 8), (uint8_t)(len >> 16),
                          (uint8_t)(len >> 24)};
  vos_shake256_ctx ctx;
  vos_shake256_init(&ctx);
  (void)vos_shake256_absorb(&ctx, (const uint8_t *)VOS_MEASURE_EXTEND_DOMAIN, 8);
  (void)vos_shake256_absorb(&ctx, reg, VOS_MEASURE_BYTES);
  (void)vos_shake256_absorb(&ctx, &code, 1);
  (void)vos_shake256_absorb(&ctx, len_bytes, 4);
  (void)vos_shake256_absorb(&ctx, data, len);
  vos_shake256_squeeze(&ctx, reg, VOS_MEASURE_BYTES);
  m->log[m->count] = code;
  m->count++;
  return 1;
}

void vos_measure_chain(const vos_measurements *m, uint8_t out[VOS_MEASURE_BYTES]) {
  vos_shake256_ctx ctx;
  vos_shake256_init(&ctx);
  (void)vos_shake256_absorb(&ctx, (const uint8_t *)VOS_MEASURE_CHAIN_DOMAIN, 8);
  (void)vos_shake256_absorb(&ctx, m->generation, VOS_MEASURE_BYTES);
  (void)vos_shake256_absorb(&ctx, m->device, VOS_MEASURE_BYTES);
  vos_shake256_squeeze(&ctx, out, VOS_MEASURE_BYTES);
}

static vos_boot_verdict refuse(const vos_sram_windows *sram, vos_boot_result *result,
                               vos_boot_verdict verdict) {
  // Nothing the refused image supplied stays where the boot core would fetch it.
  zero_bytes(sram->image, sram->image_bytes);
  result->verdict = verdict;
  vos_measure_chain(&result->measured, result->chain);
  return verdict;
}

static void write_handoff(uint8_t *record, const vos_rot_inputs *inputs,
                          const vos_rot_policy *policy, const vos_boot_result *result) {
  zero_bytes(record, VOS_HANDOFF_BYTES);
  write_u64(record + VOS_HANDOFF_MAGIC_AT, VOS_HANDOFF_MAGIC);
  write_u64(record + VOS_HANDOFF_VERSION_AT, VOS_HANDOFF_VERSION);
  write_u64(record + VOS_HANDOFF_LIFECYCLE_AT, inputs->lifecycle);
  write_u64(record + VOS_HANDOFF_ENTROPY_AT, inputs->entropy_ok);
  write_u64(record + VOS_HANDOFF_BOOT_TARGET_AT, inputs->boot_target);
  write_u64(record + VOS_HANDOFF_SECURITY_VERSION_AT, result->security_version);
  write_u64(record + VOS_HANDOFF_FLOOR_AT, inputs->floor);
  write_u64(record + VOS_HANDOFF_LOAD_BASE_AT, policy->load_base);
  write_u64(record + VOS_HANDOFF_PAYLOAD_LENGTH_AT, result->payload_length);
  copy_bytes(record + VOS_HANDOFF_IMAGE_DIGEST_AT, result->image_digest, VOS_BOOT_DIGEST_BYTES);
  copy_bytes(record + VOS_HANDOFF_GENERATION_AT, result->measured.generation, VOS_MEASURE_BYTES);
  copy_bytes(record + VOS_HANDOFF_DEVICE_AT, result->measured.device, VOS_MEASURE_BYTES);
  copy_bytes(record + VOS_HANDOFF_CHAIN_AT, result->chain, VOS_MEASURE_BYTES);
}

vos_boot_verdict vos_rot_boot_mmode(const uint8_t *image, uint64_t image_len,
                                    const vos_rot_inputs *inputs,
                                    const vos_rot_policy *policy,
                                    const vos_sram_windows *sram,
                                    vos_release_fn release, void *release_context,
                                    vos_boot_result *result) {
  result->verdict = VOS_BOOT_REFUSE_TRUNCATED;
  result->security_version = 0;
  result->payload_length = 0;
  result->digest_computed = 0;
  zero_bytes(result->image_digest, VOS_BOOT_DIGEST_BYTES);
  zero_bytes(result->chain, VOS_MEASURE_BYTES);
  vos_measure_reset(&result->measured);

  // The device register's inputs, lifecycle first (R-09-037), before any byte
  // of the image is read. The entropy verdict is measured before it decides
  // anything (R-09-006a), and the boot-target latch like every other input.
  uint8_t lifecycle = inputs->lifecycle;
  uint8_t entropy = inputs->entropy_ok ? 1u : 0u;
  uint8_t target = inputs->boot_target;
  (void)vos_measure_extend(&result->measured, 0, VOS_ITEM_LIFECYCLE, &lifecycle, 1);
  (void)vos_measure_extend(&result->measured, 0, VOS_ITEM_ENTROPY_VERDICT, &entropy, 1);
  (void)vos_measure_extend(&result->measured, 0, VOS_ITEM_BOOT_TARGET, &target, 1);

  if (!entropy) {
    return refuse(sram, result, VOS_BOOT_REFUSE_ENTROPY);
  }
  if (lifecycle >= VOS_LIFECYCLE_COUNT || policy->root[lifecycle] == NULL) {
    return refuse(sram, result, VOS_BOOT_REFUSE_NO_ROOT);
  }

  // ReadHeader: constant offsets, each field checked against a constant or a
  // composition bound and none followed.
  if (image_len < VOS_BOOT_HEADER_BYTES) {
    return refuse(sram, result, VOS_BOOT_REFUSE_TRUNCATED);
  }
  if (read_u64(image + VOS_BOOT_HDR_MAGIC) != VOS_BOOT_MAGIC) {
    return refuse(sram, result, VOS_BOOT_REFUSE_MAGIC);
  }
  if (read_u64(image + VOS_BOOT_HDR_STAGE) != VOS_BOOT_STAGE_MMODE_IMAGE) {
    return refuse(sram, result, VOS_BOOT_REFUSE_STAGE);
  }
  if (read_u64(image + VOS_BOOT_HDR_PAYLOAD_OFFSET) != VOS_BOOT_HEADER_BYTES) {
    return refuse(sram, result, VOS_BOOT_REFUSE_OFFSET);
  }
  uint64_t length = read_u64(image + VOS_BOOT_HDR_PAYLOAD_LENGTH);
  if (length == 0 || length > policy->region_bytes) {
    return refuse(sram, result, VOS_BOOT_REFUSE_LENGTH);
  }
  if (image_len - VOS_BOOT_HEADER_BYTES < length) {
    return refuse(sram, result, VOS_BOOT_REFUSE_TRUNCATED);
  }
  result->payload_length = length;

  // CheckFloor (R-09-005, R-09-030).
  uint64_t version = read_u64(image + VOS_BOOT_HDR_SECURITY_VERSION);
  result->security_version = version;
  if (version < inputs->floor) {
    return refuse(sram, result, VOS_BOOT_REFUSE_FLOOR);
  }

  // VerifySignature over the signed header bytes under the one root this
  // lifecycle state accepts (R-09-036). No bound verifier is a refusal.
  if (policy->verify == NULL) {
    return refuse(sram, result, VOS_BOOT_REFUSE_NO_VERIFIER);
  }
  if (policy->verify(policy->verify_context, image, VOS_BOOT_SIGNED_BYTES,
                     image + VOS_BOOT_HDR_SIGNATURE, policy->root[lifecycle])
      != VOS_SIG_ACCEPT) {
    return refuse(sram, result, VOS_BOOT_REFUSE_SIGNATURE);
  }

  // Place, then Measure the placed bytes: what is hashed is what the boot core
  // will fetch, and the core is held until the comparison below.
  if (sram->image_bytes < length || sram->handoff_bytes < VOS_HANDOFF_BYTES) {
    return refuse(sram, result, VOS_BOOT_REFUSE_PLACEMENT);
  }
  copy_bytes(sram->image, image + VOS_BOOT_HEADER_BYTES, length);
  zero_bytes(sram->image + length, sram->image_bytes - length);
  vos_shake256(result->image_digest, VOS_BOOT_DIGEST_BYTES, sram->image, (size_t)length);
  result->digest_computed = 1;
  if (!equal_bytes(result->image_digest, image + VOS_BOOT_HDR_PAYLOAD_DIGEST,
                   VOS_BOOT_DIGEST_BYTES)) {
    return refuse(sram, result, VOS_BOOT_REFUSE_DIGEST);
  }
  (void)vos_measure_extend(&result->measured, 1, VOS_ITEM_STAGE_MMODE_IMAGE,
                           result->image_digest, VOS_BOOT_DIGEST_BYTES);
  vos_measure_chain(&result->measured, result->chain);

  // Execute: the record first, then the release, and nothing after it.
  result->verdict = VOS_BOOT_RELEASE;
  write_handoff(sram->handoff, inputs, policy, result);
  release(release_context);
  return VOS_BOOT_RELEASE;
}
