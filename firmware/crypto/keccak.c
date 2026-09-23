// SPDX-License-Identifier: Apache-2.0
// Keccak-f[1600] and SHAKE256 (FIPS 202 sections 3.2, 3.3, 4, 5.1 and 6.2).
//
// The step mappings keep the standard's names and order: theta, rho, pi, chi
// and iota. The rho offsets and round constants are FIPS 202's published
// tables; proofs/Keccak.v derives both from the standard's recurrences and
// computes them equal to these tables. No loop bound or branch depends on a
// byte of input, but no constant-time claim is made for any binary.
#include "vos_keccak.h"

// Algorithm 5's round constants for rounds 0 through 23.
static const uint64_t round_constant[24] = {
  0x0000000000000001u, 0x0000000000008082u, 0x800000000000808Au, 0x8000000080008000u,
  0x000000000000808Bu, 0x0000000080000001u, 0x8000000080008081u, 0x8000000000008009u,
  0x000000000000008Au, 0x0000000000000088u, 0x0000000080008009u, 0x000000008000000Au,
  0x000000008000808Bu, 0x800000000000008Bu, 0x8000000000008089u, 0x8000000000008003u,
  0x8000000000008002u, 0x8000000000000080u, 0x000000000000800Au, 0x800000008000000Au,
  0x8000000080008081u, 0x8000000000008080u, 0x0000000080000001u, 0x8000000080008008u,
};

// Table 2's rho offsets, indexed x + 5y.
static const unsigned rho_offset[25] = {
   0,  1, 62, 28, 27,
  36, 44,  6, 55, 20,
   3, 10, 43, 25, 39,
  41, 45, 15, 21,  8,
  18,  2, 61, 56, 14,
};

static uint64_t rotl(uint64_t v, unsigned n) {
  return (v << n) | (v >> ((64u - n) & 63u));
}

void vos_keccak_f1600(uint64_t a[25]) {
  for (unsigned round = 0; round < 24; round++) {
    // theta: each lane takes the parity of the column below it unrotated and
    // the column above it rotated by one.
    uint64_t c[5];
    for (unsigned x = 0; x < 5; x++) {
      c[x] = a[x] ^ a[x + 5] ^ a[x + 10] ^ a[x + 15] ^ a[x + 20];
    }
    for (unsigned x = 0; x < 5; x++) {
      uint64_t d = c[(x + 4) % 5] ^ rotl(c[(x + 1) % 5], 1);
      for (unsigned y = 0; y < 5; y++) {
        a[x + 5 * y] ^= d;
      }
    }
    // rho and pi: lane (x, y) moves to (y, 2x + 3y) after its rotation.
    uint64_t b[25];
    for (unsigned x = 0; x < 5; x++) {
      for (unsigned y = 0; y < 5; y++) {
        b[y + 5 * ((2 * x + 3 * y) % 5)] = rotl(a[x + 5 * y], rho_offset[x + 5 * y]);
      }
    }
    // chi, row by row.
    for (unsigned y = 0; y < 5; y++) {
      for (unsigned x = 0; x < 5; x++) {
        a[x + 5 * y] = b[x + 5 * y] ^ (~b[(x + 1) % 5 + 5 * y] & b[(x + 2) % 5 + 5 * y]);
      }
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
