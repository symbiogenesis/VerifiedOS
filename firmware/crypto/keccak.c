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

static void vos_keccak_round(uint64_t state[25], uint64_t constant) {
  // Keep each lane in a scalar local while computing the round. The selected
  // backend can allocate/spill these values without repeated array addressing.
  uint64_t a0 = state[0];
  uint64_t a1 = state[1];
  uint64_t a2 = state[2];
  uint64_t a3 = state[3];
  uint64_t a4 = state[4];
  uint64_t a5 = state[5];
  uint64_t a6 = state[6];
  uint64_t a7 = state[7];
  uint64_t a8 = state[8];
  uint64_t a9 = state[9];
  uint64_t a10 = state[10];
  uint64_t a11 = state[11];
  uint64_t a12 = state[12];
  uint64_t a13 = state[13];
  uint64_t a14 = state[14];
  uint64_t a15 = state[15];
  uint64_t a16 = state[16];
  uint64_t a17 = state[17];
  uint64_t a18 = state[18];
  uint64_t a19 = state[19];
  uint64_t a20 = state[20];
  uint64_t a21 = state[21];
  uint64_t a22 = state[22];
  uint64_t a23 = state[23];
  uint64_t a24 = state[24];
  // Theta: five column parities, then the two neighboring column contributions.
  uint64_t c0 = a0 ^ a5 ^ a10 ^ a15 ^ a20;
  uint64_t c1 = a1 ^ a6 ^ a11 ^ a16 ^ a21;
  uint64_t c2 = a2 ^ a7 ^ a12 ^ a17 ^ a22;
  uint64_t c3 = a3 ^ a8 ^ a13 ^ a18 ^ a23;
  uint64_t c4 = a4 ^ a9 ^ a14 ^ a19 ^ a24;
  uint64_t d0 = c4 ^ rotl(c1, 1);
  uint64_t d1 = c0 ^ rotl(c2, 1);
  uint64_t d2 = c1 ^ rotl(c3, 1);
  uint64_t d3 = c2 ^ rotl(c4, 1);
  uint64_t d4 = c3 ^ rotl(c0, 1);
  a0 ^= d0;
  a1 ^= d1;
  a2 ^= d2;
  a3 ^= d3;
  a4 ^= d4;
  a5 ^= d0;
  a6 ^= d1;
  a7 ^= d2;
  a8 ^= d3;
  a9 ^= d4;
  a10 ^= d0;
  a11 ^= d1;
  a12 ^= d2;
  a13 ^= d3;
  a14 ^= d4;
  a15 ^= d0;
  a16 ^= d1;
  a17 ^= d2;
  a18 ^= d3;
  a19 ^= d4;
  a20 ^= d0;
  a21 ^= d1;
  a22 ^= d2;
  a23 ^= d3;
  a24 ^= d4;
  // Rho and pi: source x+5y moves to y+5*((2x+3y) mod 5), using Table 2.
  uint64_t b0 = rotl(a0, 0);
  uint64_t b10 = rotl(a1, 1);
  uint64_t b20 = rotl(a2, 62);
  uint64_t b5 = rotl(a3, 28);
  uint64_t b15 = rotl(a4, 27);
  uint64_t b16 = rotl(a5, 36);
  uint64_t b1 = rotl(a6, 44);
  uint64_t b11 = rotl(a7, 6);
  uint64_t b21 = rotl(a8, 55);
  uint64_t b6 = rotl(a9, 20);
  uint64_t b7 = rotl(a10, 3);
  uint64_t b17 = rotl(a11, 10);
  uint64_t b2 = rotl(a12, 43);
  uint64_t b12 = rotl(a13, 25);
  uint64_t b22 = rotl(a14, 39);
  uint64_t b23 = rotl(a15, 41);
  uint64_t b8 = rotl(a16, 45);
  uint64_t b18 = rotl(a17, 15);
  uint64_t b3 = rotl(a18, 21);
  uint64_t b13 = rotl(a19, 8);
  uint64_t b14 = rotl(a20, 18);
  uint64_t b24 = rotl(a21, 2);
  uint64_t b9 = rotl(a22, 61);
  uint64_t b19 = rotl(a23, 56);
  uint64_t b4 = rotl(a24, 14);
  // Chi uses each completed row; iota adds this round's constant to lane zero.
  state[0] = b0 ^ (~b1 & b2) ^ constant;
  state[1] = b1 ^ (~b2 & b3);
  state[2] = b2 ^ (~b3 & b4);
  state[3] = b3 ^ (~b4 & b0);
  state[4] = b4 ^ (~b0 & b1);
  state[5] = b5 ^ (~b6 & b7);
  state[6] = b6 ^ (~b7 & b8);
  state[7] = b7 ^ (~b8 & b9);
  state[8] = b8 ^ (~b9 & b5);
  state[9] = b9 ^ (~b5 & b6);
  state[10] = b10 ^ (~b11 & b12);
  state[11] = b11 ^ (~b12 & b13);
  state[12] = b12 ^ (~b13 & b14);
  state[13] = b13 ^ (~b14 & b10);
  state[14] = b14 ^ (~b10 & b11);
  state[15] = b15 ^ (~b16 & b17);
  state[16] = b16 ^ (~b17 & b18);
  state[17] = b17 ^ (~b18 & b19);
  state[18] = b18 ^ (~b19 & b15);
  state[19] = b19 ^ (~b15 & b16);
  state[20] = b20 ^ (~b21 & b22);
  state[21] = b21 ^ (~b22 & b23);
  state[22] = b22 ^ (~b23 & b24);
  state[23] = b23 ^ (~b24 & b20);
  state[24] = b24 ^ (~b20 & b21);
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

  // A separate nonrecursive round keeps the loop's branch displacement small.
  for (unsigned round = 0; round < 24; round++) vos_keccak_round(a, round_constant[round]);
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
