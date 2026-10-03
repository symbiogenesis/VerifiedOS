// SPDX-License-Identifier: Apache-2.0
// What the RoT ROM and the RoT runtime of the target chain share
// (docs/implementation/contracts/boot-handoff.md sections 9.5 to 9.7): one
// stage verification over a store window, and the moves of the measurement
// registers between the state record, the capture and the item-6 response.
//
// It is included by rom.c and runtime.c after the bound sources and the
// bring-up release (firmware/rot/boot_verify.c), whose measurement encoding,
// byte helpers and handoff-record writer it reuses unchanged, so the chain
// measures and records exactly as the bring-up release does. Every function is
// pure over the windows it is handed: the assembly beside each unit reads and
// writes the RoT's doors, because the contained compiler lowers no volatile
// access (vos_chain.h).
#include "vos_chain.h"

_Static_assert(VOS_MEASURE_LOG_CAPACITY <= VOS_CHAIN_STATE_LOG_BYTES,
               "the state record's log cannot hold the measurement log");

// One stage's facts as far as its verification reached them. The capture
// reports the version and length once ReadHeader has accepted them and the
// digest once the placed bytes were hashed; a refusal before either leaves it
// zero.
typedef struct {
  uint64_t header_read;
  uint64_t security_version;
  uint64_t payload_length;
  uint64_t digest_computed;
  uint8_t digest[VOS_BOOT_DIGEST_BYTES];
} vos_chain_stage;

// Section 3's steps 3 to 6 for one stage, as sections 9.5 and 9.6 use them:
// ReadHeader over one copy of the signed prefix, CheckFloor, VerifySignature
// under `root`, placement into `region` with the tail zeroed, and the digest of
// the placed bytes against the copied header's. `region_limit` is the
// composition's region for this stage, which bounds the declared length;
// `region_bytes` is the window handed in, which bounds the placement.
static uint64_t chain_check_stage(uint64_t stage, uint64_t region_limit, uint64_t floor,
                                  const uint8_t *root, const uint8_t *store,
                                  uint64_t store_len, uint8_t *region, uint64_t region_bytes,
                                  vos_chain_stage *out) {
  if (store_len < VOS_BOOT_HEADER_BYTES) {
    return VOS_CHAIN_REFUSE_TRUNCATED_V;
  }
  // The signed prefix is copied once; every field below and the verified
  // message are read from the copy, so no field differs between its check and
  // the signature check.
  uint8_t header[VOS_BOOT_SIGNED_BYTES];
  copy_bytes(header, store, VOS_BOOT_SIGNED_BYTES);
  if (read_u64(header + VOS_BOOT_HDR_MAGIC) != VOS_BOOT_MAGIC) {
    return VOS_CHAIN_REFUSE_MAGIC_V;
  }
  if (read_u64(header + VOS_BOOT_HDR_STAGE) != stage) {
    return VOS_CHAIN_REFUSE_STAGE_V;
  }
  if (read_u64(header + VOS_BOOT_HDR_PAYLOAD_OFFSET) != VOS_BOOT_HEADER_BYTES) {
    return VOS_CHAIN_REFUSE_OFFSET_V;
  }
  uint64_t length = read_u64(header + VOS_BOOT_HDR_PAYLOAD_LENGTH);
  if (length == 0 || length > region_limit) {
    return VOS_CHAIN_REFUSE_LENGTH_V;
  }
  if (store_len - VOS_BOOT_HEADER_BYTES < length) {
    return VOS_CHAIN_REFUSE_TRUNCATED_V;
  }
  uint64_t version = read_u64(header + VOS_BOOT_HDR_SECURITY_VERSION);
  out->header_read = 1;
  out->security_version = version;
  out->payload_length = length;

  // CheckFloor (R-09-005, R-09-030).
  if (version < floor) {
    return VOS_CHAIN_REFUSE_FLOOR_V;
  }

  // VerifySignature over the copied prefix under the one root the lifecycle
  // state accepts (R-09-036, R-09-036a). The target binds its verifier
  // statically, as the bring-up release target does.
  if (VOS_BOOT_TARGET_VERIFY(NULL, header, VOS_BOOT_SIGNED_BYTES,
                             store + VOS_BOOT_HDR_SIGNATURE, root) != VOS_SIG_ACCEPT) {
    return VOS_CHAIN_REFUSE_SIGNATURE_V;
  }

  // Place, then Measure the placed bytes: what is hashed is what will run.
  if (region_bytes < length) {
    return VOS_CHAIN_REFUSE_PLACEMENT_V;
  }
  copy_bytes(region, store + VOS_BOOT_HEADER_BYTES, length);
  zero_bytes(region + length, region_bytes - length);
  vos_shake256(out->digest, VOS_BOOT_DIGEST_BYTES, region, (size_t)length);
  out->digest_computed = 1;
  if (!equal_bytes(out->digest, header + VOS_BOOT_HDR_PAYLOAD_DIGEST, VOS_BOOT_DIGEST_BYTES)) {
    return VOS_CHAIN_REFUSE_DIGEST_V;
  }
  return VOS_CHAIN_RELEASE;
}

// The same, with section 9's refusal duty: nothing a refused image supplied
// stays in the region it would have run from.
static uint64_t chain_verify_stage(uint64_t stage, uint64_t region_limit, uint64_t floor,
                                   const uint8_t *root, const uint8_t *store,
                                   uint64_t store_len, uint8_t *region, uint64_t region_bytes,
                                   vos_chain_stage *out) {
  out->header_read = 0;
  out->security_version = 0;
  out->payload_length = 0;
  out->digest_computed = 0;
  zero_bytes(out->digest, VOS_BOOT_DIGEST_BYTES);
  uint64_t verdict = chain_check_stage(stage, region_limit, floor, root, store, store_len,
                                       region, region_bytes, out);
  if (verdict != VOS_CHAIN_RELEASE) {
    zero_bytes(region, region_bytes);
  }
  return verdict;
}

// The root the lifecycle state accepts, or NULL where it accepts none
// (R-09-036): an index outside the enumeration accepts none.
static const uint8_t *chain_root(const vos_chain_rom_policy *policy, uint64_t lifecycle) {
  if (lifecycle >= VOS_LIFECYCLE_COUNT) {
    return NULL;
  }
  return policy->root[lifecycle];
}

// The registers, the count and the log at four offsets of one record: the
// state record, the capture head and the item-6 response lay them out alike.
static void chain_put_measurements(uint8_t *base, uint64_t count_at, uint64_t log_at,
                                   uint64_t generation_at, uint64_t device_at,
                                   const vos_measurements *m) {
  write_u64(base + count_at, m->count);
  zero_bytes(base + log_at, VOS_CHAIN_STATE_LOG_BYTES);
  copy_bytes(base + log_at, m->log, m->count);
  copy_bytes(base + generation_at, m->generation, VOS_MEASURE_BYTES);
  copy_bytes(base + device_at, m->device, VOS_MEASURE_BYTES);
}

// The registers a state record carries. A count beyond the log's capacity
// reads as a full log, so the next extension refuses rather than overruns.
static void chain_get_measurements(const uint8_t *state, vos_measurements *m) {
  vos_measure_reset(m);
  uint64_t count = read_u64(state + VOS_CHAIN_STATE_MEASURE_COUNT_AT);
  if (count > VOS_MEASURE_LOG_CAPACITY) {
    count = VOS_MEASURE_LOG_CAPACITY;
  }
  copy_bytes(m->log, state + VOS_CHAIN_STATE_LOG_AT, count);
  copy_bytes(m->generation, state + VOS_CHAIN_STATE_GENERATION_AT, VOS_MEASURE_BYTES);
  copy_bytes(m->device, state + VOS_CHAIN_STATE_DEVICE_AT, VOS_MEASURE_BYTES);
  m->count = (unsigned)count;
}

static void chain_state_measurements(uint8_t *state, const vos_measurements *m) {
  chain_put_measurements(state, VOS_CHAIN_STATE_MEASURE_COUNT_AT, VOS_CHAIN_STATE_LOG_AT,
                         VOS_CHAIN_STATE_GENERATION_AT, VOS_CHAIN_STATE_DEVICE_AT, m);
}

// The capture head's measurement fields and the chain digest over them.
static void chain_capture_measurements(uint8_t *capture, const vos_measurements *m) {
  uint8_t chain[VOS_MEASURE_BYTES];
  chain_put_measurements(capture, VOS_CHAIN_CAPTURE_MEASURE_COUNT_AT, VOS_CHAIN_CAPTURE_LOG_AT,
                         VOS_CHAIN_CAPTURE_GENERATION_AT, VOS_CHAIN_CAPTURE_DEVICE_AT, m);
  vos_measure_chain(m, chain);
  copy_bytes(capture + VOS_CHAIN_CAPTURE_CHAIN_AT, chain, VOS_MEASURE_BYTES);
}

// Whether `state` is a version-1 state record of `run_kind`.
static int chain_state_admits(const uint8_t *state, uint64_t run_kind) {
  return read_u64(state + VOS_CHAIN_STATE_MAGIC_AT) == VOS_CHAIN_STATE_MAGIC
      && read_u64(state + VOS_CHAIN_STATE_VERSION_AT) == VOS_CHAIN_STATE_VERSION
      && read_u64(state + VOS_CHAIN_STATE_RUN_KIND_AT) == run_kind;
}

// The capture's copy of the state record as the run left it.
static void chain_capture_state(uint8_t *capture, const uint8_t *state) {
  copy_bytes(capture + VOS_CHAIN_CAPTURE_STATE_AT, state, VOS_CHAIN_STATE_BYTES);
}
