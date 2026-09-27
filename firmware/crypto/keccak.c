// SPDX-License-Identifier: Apache-2.0
// Keccak-f[1600] and SHAKE256 (FIPS 202 sections 3.2, 3.3, 4, 5.1 and 6.2).
//
// The step mappings keep the standard's names and order: theta, rho, pi, chi
// and iota. The rho offsets and round constants are FIPS 202's published
// tables; proofs/Keccak.v derives both from the standard's recurrences and
// computes them equal to these tables. No loop bound or branch depends on a
// byte of input, but no constant-time claim is made for any binary.
#include "vos_keccak.h"

static uint64_t rotl(uint64_t v, unsigned n) {
  return (v << n) | (v >> ((64u - n) & 63u));
}

void vos_keccak_f1600(uint64_t a[25]) {
// Fixed local storage keeps the immutable tables within the selected purecap
// source profile, whose global authority currently admits scalar words only.
// Algorithm 5's round constants for rounds 0 through 23.
const uint64_t round_constant[24] = {
  0x0000000000000001u, 0x0000000000008082u, 0x800000000000808Au, 0x8000000080008000u,
  0x000000000000808Bu, 0x0000000080000001u, 0x8000000080008081u, 0x8000000000008009u,
  0x000000000000008Au, 0x0000000000000088u, 0x0000000080008009u, 0x000000008000000Au,
  0x000000008000808Bu, 0x800000000000008Bu, 0x8000000000008089u, 0x8000000000008003u,
  0x8000000000008002u, 0x8000000000000080u, 0x000000000000800Au, 0x800000008000000Au,
  0x8000000080008081u, 0x8000000000008080u, 0x0000000080000001u, 0x8000000080008008u,
};

  for (unsigned round = 0; round < 24; round++) {
    // theta: each lane takes the parity of the column below it unrotated and
    // the column above it rotated by one.
    uint64_t c[5];
    for (unsigned x = 0; x < 5; x++) {
      c[x] = a[x] ^ a[x + 5] ^ a[x + 10] ^ a[x + 15] ^ a[x + 20];
    }
    // The topology is fixed. Expanding these columns avoids division and
    // variable-index traffic in the scalar RoT binary; the round count stays 24.
#define VOS_THETA(x, before, after) do { \
    uint64_t d = c[before] ^ rotl(c[after], 1); \
    a[x] ^= d; a[x+5] ^= d; a[x+10] ^= d; a[x+15] ^= d; a[x+20] ^= d; \
  } while (0)
    VOS_THETA(0, 4, 1); VOS_THETA(1, 0, 2); VOS_THETA(2, 1, 3);
    VOS_THETA(3, 2, 4); VOS_THETA(4, 3, 0);
#undef VOS_THETA
    // rho and pi: lane (x, y) moves to (y, 2x + 3y) after its rotation.
    uint64_t b[25];
    // Table 2's rho offsets in x + 5y order; the macro states pi directly.
#define VOS_RHO_PI(x, y, offset) \
    b[y + 5 * ((2*x + 3*y) % 5)] = rotl(a[x + 5*y], offset)
    VOS_RHO_PI(0, 0, 0); VOS_RHO_PI(1, 0, 1); VOS_RHO_PI(2, 0, 62);
    VOS_RHO_PI(3, 0, 28); VOS_RHO_PI(4, 0, 27);
    VOS_RHO_PI(0, 1, 36); VOS_RHO_PI(1, 1, 44); VOS_RHO_PI(2, 1, 6);
    VOS_RHO_PI(3, 1, 55); VOS_RHO_PI(4, 1, 20);
    VOS_RHO_PI(0, 2, 3); VOS_RHO_PI(1, 2, 10); VOS_RHO_PI(2, 2, 43);
    VOS_RHO_PI(3, 2, 25); VOS_RHO_PI(4, 2, 39);
    VOS_RHO_PI(0, 3, 41); VOS_RHO_PI(1, 3, 45); VOS_RHO_PI(2, 3, 15);
    VOS_RHO_PI(3, 3, 21); VOS_RHO_PI(4, 3, 8);
    VOS_RHO_PI(0, 4, 18); VOS_RHO_PI(1, 4, 2); VOS_RHO_PI(2, 4, 61);
    VOS_RHO_PI(3, 4, 56); VOS_RHO_PI(4, 4, 14);
#undef VOS_RHO_PI
    // chi, row by row.
    for (unsigned y = 0; y < 5; y++) {
      unsigned p = 5 * y;
      a[p] = b[p] ^ (~b[p+1] & b[p+2]);
      a[p+1] = b[p+1] ^ (~b[p+2] & b[p+3]);
      a[p+2] = b[p+2] ^ (~b[p+3] & b[p+4]);
      a[p+3] = b[p+3] ^ (~b[p+4] & b[p]);
      a[p+4] = b[p+4] ^ (~b[p] & b[p+1]);
    }
    // iota.
    a[0] ^= round_constant[round];
  }
}

static void xor_byte(uint64_t state[25], size_t at, uint8_t byte) {
  state[at / 8] ^= (uint64_t)byte << (8u * (unsigned)(at % 8));
}

static uint8_t state_byte(const uint64_t state[25], size_t at) {
  return (uint8_t)(state[at / 8] >> (8u * (unsigned)(at % 8)));
}

void vos_shake256_init(vos_shake256_ctx *ctx) {
  for (unsigned i = 0; i < 25; i++) {
    ctx->state[i] = 0;
  }
  ctx->offset = 0;
  ctx->squeezing = 0;
}

int vos_shake256_absorb(vos_shake256_ctx *ctx, const uint8_t *in, size_t len) {
  if (ctx->squeezing) {
    return 0;
  }
  for (size_t i = 0; i < len; i++) {
    xor_byte(ctx->state, ctx->offset, in[i]);
    ctx->offset++;
    if (ctx->offset == VOS_SHAKE256_RATE) {
      vos_keccak_f1600(ctx->state);
      ctx->offset = 0;
    }
  }
  return 1;
}

void vos_shake256_squeeze(vos_shake256_ctx *ctx, uint8_t *out, size_t len) {
  if (!ctx->squeezing) {
    // SHAKE's domain suffix 1111 and pad10*1's first bit share one byte; the
    // closing bit lands on the rate's last byte, which may be the same byte.
    xor_byte(ctx->state, ctx->offset, 0x1Fu);
    xor_byte(ctx->state, VOS_SHAKE256_RATE - 1u, 0x80u);
    vos_keccak_f1600(ctx->state);
    ctx->offset = 0;
    ctx->squeezing = 1;
  }
  for (size_t i = 0; i < len; i++) {
    if (ctx->offset == VOS_SHAKE256_RATE) {
      vos_keccak_f1600(ctx->state);
      ctx->offset = 0;
    }
    out[i] = state_byte(ctx->state, ctx->offset);
    ctx->offset++;
  }
}

void vos_shake256(uint8_t *out, size_t out_len, const uint8_t *in, size_t in_len) {
  vos_shake256_ctx ctx;
  vos_shake256_init(&ctx);
  (void)vos_shake256_absorb(&ctx, in, in_len);
  vos_shake256_squeeze(&ctx, out, out_len);
}
