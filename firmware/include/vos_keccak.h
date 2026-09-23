// SPDX-License-Identifier: Apache-2.0
// Keccak-f[1600] and SHAKE256 as the RoT boot verifier calls them (FIPS 202).
//
// This is the functional layer only. It makes no constant-time, masking or
// reduction claim (R-05-062, R-05-067, R-05-004a, R-05-077a); those remain the
// crypto owner's obligations over a target binary. The functional reference is
// proofs/Keccak.v; the harness compares this implementation with an
// independent SHAKE256 (docs/implementation/contracts/boot-handoff.md, section 5).
#ifndef VOS_KECCAK_H
#define VOS_KECCAK_H

#include <stddef.h>
#include <stdint.h>

// The SHAKE256 rate in bytes: (1600 - 2 * 256) / 8.
#define VOS_SHAKE256_RATE 136u

// One Keccak-f[1600] permutation over 25 64-bit lanes, lane index x + 5y,
// 24 rounds. A lane holds its eight state bytes least significant first.
void vos_keccak_f1600(uint64_t state[25]);

// An incremental SHAKE256 computation: absorb any number of byte strings,
// then squeeze. Absorbing after the first squeeze is refused by
// vos_shake256_absorb returning 0 and leaving the state unchanged.
typedef struct {
  uint64_t state[25];
  size_t offset;  // bytes absorbed into, or squeezed from, the current block
  int squeezing;  // 0 while absorbing, 1 once padded
} vos_shake256_ctx;

void vos_shake256_init(vos_shake256_ctx *ctx);
int vos_shake256_absorb(vos_shake256_ctx *ctx, const uint8_t *in, size_t len);
void vos_shake256_squeeze(vos_shake256_ctx *ctx, uint8_t *out, size_t len);

// SHAKE256(in, 8 * out_len): absorb `in_len` bytes, pad with the SHAKE domain
// suffix and pad10*1, then squeeze `out_len` bytes.
void vos_shake256(uint8_t *out, size_t out_len, const uint8_t *in, size_t in_len);

#endif
