// SPDX-License-Identifier: Apache-2.0
// The target chain's M-mode stage body (docs/implementation/contracts/boot-handoff.md
// section 9.8): the handoff record's magic and version, the stage-2 header, the
// floor, the ML-DSA-87 signature under the kernel-stage root the measured image
// carries, placement into the kernel region, measurement, the item-6 request and
// the response's binding (section 9.7). The hand-lowered entry beside it
// (mmode_entry.s) derives every capability this body receives, installs section
// 6's kernel-entry state on a release and reports a refusal through HTIF.
//
// Pure over the windows it is handed: no access outside them, no volatile access
// (the contained compiler lowers none), no global storage, no allocation and no loop
// whose bound is read from an input other than the declared payload length, which
// is checked against the kernel region before anything reads that far. The bound
// sources are included unchanged (section 9.13).
#include "../crypto/keccak.c"
#include "../crypto/mldsa87.c"
#include "vos_chain.h"

// The kernel region is reached by aligned doublewords only. In the main-die
// composition the HTIF word, `chain.tohost_base`, is the kernel data extent's first
// word, and the emulator's HTIF device answers that word to aligned four- and
// eight-byte accesses alone, so a byte loop over the region would fault there; the
// typed route admits no cast from a byte pointer, so vos_chain.h hands the region
// as doublewords.
_Static_assert(VOS_CHAIN_KERNEL_REGION_BYTES % 8u == 0, "the kernel region is not whole doublewords");
_Static_assert(VOS_CHAIN_KERNEL_DATA_AT % 8u == 0, "the HTIF word is not an aligned doubleword");

static uint64_t mm_read_u64(const uint8_t *p) {
  uint64_t v = 0;
  for (unsigned i = 0; i < 8; i++) {
    v |= (uint64_t)p[i] << (8u * i);
  }
  return v;
}

static void mm_write_u64(uint8_t *p, uint64_t v) {
  for (unsigned i = 0; i < 8; i++) {
    p[i] = (uint8_t)(v >> (8u * i));
  }
}

static void mm_copy(uint8_t *to, const uint8_t *from, uint64_t len) {
  for (uint64_t i = 0; i < len; i++) {
    to[i] = from[i];
  }
}

static void mm_zero(uint8_t *to, uint64_t len) {
  for (uint64_t i = 0; i < len; i++) {
    to[i] = 0;
  }
}

// Every byte is compared whatever the first difference.
static int mm_equal(const uint8_t *a, const uint8_t *b, unsigned len) {
  uint8_t diff = 0;
  for (unsigned i = 0; i < len; i++) {
    diff = (uint8_t)(diff | (a[i] ^ b[i]));
  }
  return diff == 0;
}

static void mm_region_zero(uint64_t *region, uint64_t region_bytes) {
  for (uint64_t i = 0; i < region_bytes / 8u; i++) {
    region[i] = 0;
  }
}

// Place `length` payload bytes at the region's base and zero the rest of the
// region, one doubleword at a time, the last partial doubleword zero-filled.
static void mm_place(uint64_t *region, uint64_t region_bytes, const uint8_t *payload,
                     uint64_t length) {
  uint64_t whole = length / 8u;
  for (uint64_t i = 0; i < whole; i++) {
    region[i] = mm_read_u64(payload + 8u * i);
  }
  uint64_t next = whole;
  if (length % 8u != 0) {
    uint64_t last = 0;
    for (uint64_t j = 0; 8u * whole + j < length; j++) {
      last |= (uint64_t)payload[8u * whole + j] << (8u * j);
    }
    region[whole] = last;
    next = whole + 1u;
  }
  for (uint64_t i = next; i < region_bytes / 8u; i++) {
    region[i] = 0;
  }
}

// SHAKE256 of the placed bytes, read back from the region: what is hashed is
// what the kernel stage will fetch.
static void mm_digest_placed(uint8_t out[VOS_BOOT_DIGEST_BYTES], const uint64_t *region,
                             uint64_t length) {
  vos_shake256_ctx ctx;
  vos_shake256_init(&ctx);
  for (uint64_t at = 0; at < length; at += 8u) {
    uint8_t bytes[8];
    mm_write_u64(bytes, region[at / 8u]);
    uint64_t take = length - at < 8u ? length - at : 8u;
    (void)vos_shake256_absorb(&ctx, bytes, (size_t)take);
  }
  vos_shake256_squeeze(&ctx, out, VOS_BOOT_DIGEST_BYTES);
}

// Section 5's extension, SHAKE256(EXTEND_DOMAIN || register || code || len32 ||
// data), and its chain digest, SHAKE256(CHAIN_DOMAIN || generation || device).
static void mm_extend(uint8_t out[VOS_MEASURE_BYTES], const uint8_t *reg, uint8_t code,
                      const uint8_t *data, uint32_t len) {
  const uint8_t domain[] = VOS_MEASURE_EXTEND_DOMAIN;
  uint8_t len_bytes[4] = {(uint8_t)len, (uint8_t)(len >> 8), (uint8_t)(len >> 16),
                          (uint8_t)(len >> 24)};
  vos_shake256_ctx ctx;
  vos_shake256_init(&ctx);
  (void)vos_shake256_absorb(&ctx, domain, 8);
  (void)vos_shake256_absorb(&ctx, reg, VOS_MEASURE_BYTES);
  (void)vos_shake256_absorb(&ctx, &code, 1);
  (void)vos_shake256_absorb(&ctx, len_bytes, 4);
  (void)vos_shake256_absorb(&ctx, data, len);
  vos_shake256_squeeze(&ctx, out, VOS_MEASURE_BYTES);
}

static void mm_chain(uint8_t out[VOS_MEASURE_BYTES], const uint8_t *generation,
                     const uint8_t *device) {
  const uint8_t domain[] = VOS_MEASURE_CHAIN_DOMAIN;
  vos_shake256_ctx ctx;
  vos_shake256_init(&ctx);
  (void)vos_shake256_absorb(&ctx, domain, 8);
  (void)vos_shake256_absorb(&ctx, generation, VOS_MEASURE_BYTES);
  (void)vos_shake256_absorb(&ctx, device, VOS_MEASURE_BYTES);
  vos_shake256_squeeze(&ctx, out, VOS_MEASURE_BYTES);
}

// Every refusal zeroes the kernel region and records its code; the entry
// reports it through HTIF as VOS_CHAIN_MMODE_EXIT_BASE plus the code.
static uint64_t mm_refuse(uint64_t *kernel_region, uint64_t kernel_region_bytes,
                          uint8_t *capture, uint64_t verdict) {
  mm_region_zero(kernel_region, kernel_region_bytes);
  mm_write_u64(capture + VOS_CHAIN_MCAPTURE_VERDICT_AT, verdict);
  return verdict;
}

// The M-mode capture's fields are written as the stage reaches them: the payload
// length and security version once ReadHeader has accepted the header, the
// kernel digest once the placed bytes are hashed, the request flag once the
// request is written, the binding flag once the response binds it, and the
// verdict last on every path. Every other byte is zero.
uint64_t vos_chain_mmode(const uint8_t *record, const uint8_t *root_key, const uint8_t *store,
                         uint64_t store_len, uint64_t *kernel_region, uint64_t kernel_region_bytes,
                         uint8_t *request, const uint8_t *response, uint8_t *capture) {
  mm_zero(capture, VOS_CHAIN_MCAPTURE_BYTES);

  // 1. The handoff record is section 6's.
  if (mm_read_u64(record + VOS_HANDOFF_MAGIC_AT) != VOS_HANDOFF_MAGIC
      || mm_read_u64(record + VOS_HANDOFF_VERSION_AT) != VOS_HANDOFF_VERSION) {
    return mm_refuse(kernel_region, kernel_region_bytes, capture, VOS_CHAIN_REFUSE_RECORD);
  }

  // 2. ReadHeader with section 9.3's stage-2 layout: the signed prefix is copied
  // once and every field and the verified message are read from the copy.
  if (store_len < VOS_CHAIN_KSTAGE_HEADER_BYTES) {
    return mm_refuse(kernel_region, kernel_region_bytes, capture, VOS_BOOT_REFUSE_TRUNCATED);
  }
  uint8_t header[VOS_CHAIN_KSTAGE_SIGNED_BYTES];
  mm_copy(header, store, VOS_CHAIN_KSTAGE_SIGNED_BYTES);
  if (mm_read_u64(header + VOS_BOOT_HDR_MAGIC) != VOS_CHAIN_KSTAGE_MAGIC) {
    return mm_refuse(kernel_region, kernel_region_bytes, capture, VOS_BOOT_REFUSE_MAGIC);
  }
  if (mm_read_u64(header + VOS_BOOT_HDR_STAGE) != VOS_BOOT_STAGE_CORE_KERNELS) {
    return mm_refuse(kernel_region, kernel_region_bytes, capture, VOS_BOOT_REFUSE_STAGE);
  }
  if (mm_read_u64(header + VOS_BOOT_HDR_PAYLOAD_OFFSET) != VOS_CHAIN_KSTAGE_HEADER_BYTES) {
    return mm_refuse(kernel_region, kernel_region_bytes, capture, VOS_BOOT_REFUSE_OFFSET);
  }
  uint64_t length = mm_read_u64(header + VOS_BOOT_HDR_PAYLOAD_LENGTH);
  if (length == 0 || length > VOS_CHAIN_KERNEL_REGION_BYTES) {
    return mm_refuse(kernel_region, kernel_region_bytes, capture, VOS_BOOT_REFUSE_LENGTH);
  }
  if (store_len - VOS_CHAIN_KSTAGE_HEADER_BYTES < length) {
    return mm_refuse(kernel_region, kernel_region_bytes, capture, VOS_BOOT_REFUSE_TRUNCATED);
  }
  uint64_t version = mm_read_u64(header + VOS_BOOT_HDR_SECURITY_VERSION);
  mm_write_u64(capture + VOS_CHAIN_MCAPTURE_PAYLOAD_LENGTH_AT, length);
  mm_write_u64(capture + VOS_CHAIN_MCAPTURE_SECURITY_VERSION_AT, version);

  // 3. CheckFloor against the floor the record carries.
  if (version < mm_read_u64(record + VOS_HANDOFF_FLOOR_AT)) {
    return mm_refuse(kernel_region, kernel_region_bytes, capture, VOS_BOOT_REFUSE_FLOOR);
  }

  // 4. VerifySignature: FIPS 204's internal algorithm, no context prefix, over the
  // copied signed prefix, the signature read in place (F-742's chain binding).
  if (vos_mldsa87_verify_internal(root_key, VOS_CHAIN_KSTAGE_PUBLIC_KEY_BYTES, header,
                                  VOS_CHAIN_KSTAGE_SIGNED_BYTES, store + VOS_BOOT_HDR_SIGNATURE,
                                  VOS_CHAIN_KSTAGE_SIGNATURE_BYTES) != 1) {
    return mm_refuse(kernel_region, kernel_region_bytes, capture, VOS_BOOT_REFUSE_SIGNATURE);
  }

  // 5. Place, zero the rest of the region, Measure the placed bytes. The entry
  // hands the region at its constant extent, so the placement refusal is
  // unreachable here; it stays so that a narrower window refuses rather than
  // faults.
  if (kernel_region_bytes < length || kernel_region_bytes % 8u != 0) {
    return mm_refuse(kernel_region, kernel_region_bytes, capture, VOS_BOOT_REFUSE_PLACEMENT);
  }
  mm_place(kernel_region, kernel_region_bytes, store + VOS_CHAIN_KSTAGE_HEADER_BYTES, length);
  uint8_t digest[VOS_BOOT_DIGEST_BYTES];
  mm_digest_placed(digest, kernel_region, length);
  mm_copy(capture + VOS_CHAIN_MCAPTURE_KERNEL_DIGEST_AT, digest, VOS_BOOT_DIGEST_BYTES);
  if (!mm_equal(digest, header + VOS_BOOT_HDR_PAYLOAD_DIGEST, VOS_BOOT_DIGEST_BYTES)) {
    return mm_refuse(kernel_region, kernel_region_bytes, capture, VOS_BOOT_REFUSE_DIGEST);
  }

  // 6. The item-6 request, written before the response is read, then the
  // response's binding: its magic and stage, the echoed digest, the generation
  // register after item 6 over the record's, the record's device register and the
  // chain digest over both.
  mm_zero(request, VOS_CHAIN_REQUEST_BYTES);
  mm_write_u64(request + VOS_CHAIN_REQUEST_MAGIC_AT, VOS_CHAIN_REQUEST_MAGIC);
  mm_write_u64(request + VOS_CHAIN_REQUEST_STAGE_AT, VOS_BOOT_STAGE_CORE_KERNELS);
  mm_copy(request + VOS_CHAIN_REQUEST_DIGEST_AT, digest, VOS_BOOT_DIGEST_BYTES);
  mm_write_u64(capture + VOS_CHAIN_MCAPTURE_REQUEST_WRITTEN_AT, 1);

  uint8_t expected[VOS_MEASURE_BYTES];
  if (mm_read_u64(response + VOS_CHAIN_RESPONSE_MAGIC_AT) != VOS_CHAIN_RESPONSE_MAGIC
      || mm_read_u64(response + VOS_CHAIN_RESPONSE_STAGE_AT) != VOS_BOOT_STAGE_CORE_KERNELS
      || !mm_equal(response + VOS_CHAIN_RESPONSE_DIGEST_AT, digest, VOS_BOOT_DIGEST_BYTES)) {
    return mm_refuse(kernel_region, kernel_region_bytes, capture, VOS_CHAIN_REFUSE_RESPONSE);
  }
  mm_extend(expected, record + VOS_HANDOFF_GENERATION_AT, VOS_ITEM_STAGE_CORE_KERNELS, digest,
            VOS_BOOT_DIGEST_BYTES);
  if (!mm_equal(response + VOS_CHAIN_RESPONSE_GENERATION_AT, expected, VOS_MEASURE_BYTES)
      || !mm_equal(response + VOS_CHAIN_RESPONSE_DEVICE_AT, record + VOS_HANDOFF_DEVICE_AT,
                   VOS_MEASURE_BYTES)) {
    return mm_refuse(kernel_region, kernel_region_bytes, capture, VOS_CHAIN_REFUSE_RESPONSE);
  }
  mm_chain(expected, expected, record + VOS_HANDOFF_DEVICE_AT);
  if (!mm_equal(response + VOS_CHAIN_RESPONSE_CHAIN_AT, expected, VOS_MEASURE_BYTES)) {
    return mm_refuse(kernel_region, kernel_region_bytes, capture, VOS_CHAIN_REFUSE_RESPONSE);
  }
  mm_write_u64(capture + VOS_CHAIN_MCAPTURE_RESPONSE_BOUND_AT, 1);

  // 7. The entry writes nothing to the capture after this; it installs section
  // 6's state and enters the kernel stage.
  mm_write_u64(capture + VOS_CHAIN_MCAPTURE_VERDICT_AT, VOS_CHAIN_RELEASE);
  return VOS_CHAIN_RELEASE;
}

// The entry's call: seven bounded capabilities, which fit the argument registers,
// with the windows' extents supplied here from vos_chain.h. The request and
// response slots are separate capabilities over the mailbox's two slots.
uint64_t vos_chain_mmode_entry(const uint8_t *record, const uint8_t *root_key,
                               const uint8_t *store, uint64_t *kernel_region, uint8_t *request,
                               const uint8_t *response, uint8_t *capture) {
  return vos_chain_mmode(record, root_key, store, VOS_CHAIN_KERNEL_STORE_BYTES, kernel_region,
                         VOS_CHAIN_KERNEL_REGION_BYTES, request, response, capture);
}
