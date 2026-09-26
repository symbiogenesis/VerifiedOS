// SPDX-License-Identifier: Apache-2.0
// Authored from FIPS 204 and proofs/MlDsa.v. ML-DSA-87 verification only.
// Canonical modular arithmetic uses int64_t products below q*q < 2^46.
// Fixed sampler budgets match the Gallina reference; exhaustion refuses.
#include "vos_signature.h"
#include "vos_keccak.h"

#define Q 8380417
typedef int32_t poly[256];

static int32_t mod(int64_t x) {
  int32_t r = (int32_t)(x % Q);
  return r < 0 ? r + Q : r;
}
static int32_t power(int32_t a, unsigned e) {
  int32_t r = 1;
  for (; e; e >>= 1, a = mod((int64_t)a * a)) if (e & 1u) r = mod((int64_t)r * a);
  return r;
}
static unsigned reverse8(unsigned k) {
  unsigned r = 0;
  for (unsigned i = 0; i < 8; i++, k >>= 1) r = (r << 1) | (k & 1u);
  return r;
}
// The complete negacyclic NTT. Twiddles are derived, never copied from a table.
static void ntt(poly a) {
  unsigned k = 1;
  for (unsigned length = 128; length; length >>= 1) {
    for (unsigned start = 0; start < 256; start += 2 * length) {
      int32_t zeta = power(1753, reverse8(k++));
      for (unsigned j = start; j < start + length; j++) {
        int32_t t = mod((int64_t)zeta * a[j+length]);
        a[j+length] = mod((int64_t)a[j] - t);
        a[j] = mod((int64_t)a[j] + t);
      }
    }
  }
}
static void intt(poly a) {
  unsigned k = 255;
  for (unsigned length = 1; length < 256; length <<= 1) {
    // Reverse both the stage and the block order of the forward transform.
    for (unsigned end = 256; end; end -= 2 * length) {
      int32_t zeta = power(1753, 512 - reverse8(k--));
      for (unsigned j = end - 2 * length; j < end - length; j++) {
        int32_t x = a[j], y = a[j+length];
        a[j] = mod((int64_t)x + y);
        a[j+length] = mod((int64_t)zeta * mod((int64_t)x-y));
      }
    }
  }
  for (unsigned i = 0; i < 256; i++) a[i] = mod((int64_t)a[i] * 8347681);
}

// SHAKE128 for the fixed 34-byte matrix seed, same Keccak-f as SHAKE256.
static void matrix_stream(uint8_t out[894], const uint8_t rho[32], unsigned col, unsigned row) {
  uint64_t state[25] = {0};
  for (unsigned i = 0; i < 32; i++) state[i/8] ^= (uint64_t)rho[i] << (8*(i%8));
  state[4] = (uint64_t)col | ((uint64_t)row << 8) | (UINT64_C(0x1f) << 16);
  state[20] |= UINT64_C(0x8000000000000000);
  for (unsigned i = 0; i < 894; i++) {
    unsigned at = i % 168;
    if (!at) vos_keccak_f1600(state);
    out[i] = (uint8_t)(state[at/8] >> (8*(at%8)));
  }
}
static int matrix(poly out, const uint8_t rho[32], unsigned col, unsigned row) {
  uint8_t bytes[894];
  matrix_stream(bytes, rho, col, row);
  unsigned count = 0;
  for (unsigned i = 0; i < sizeof bytes && count < 256; i += 3) {
    uint32_t v = bytes[i] | ((uint32_t)bytes[i+1] << 8) | ((uint32_t)(bytes[i+2]&127u) << 16);
    if (v < Q) out[count++] = (int32_t)v;
  }
  return count == 256;
}
static uint32_t unpack(const uint8_t *bytes, unsigned index, unsigned width) {
  uint32_t v = 0;
  for (unsigned i = 0; i < width; i++) {
    unsigned bit = index * width + i;
    v |= (uint32_t)((bytes[bit/8] >> (bit%8)) & 1u) << i;
  }
  return v;
}
static int challenge(poly c, const uint8_t seed[64]) {
  uint8_t stream[221];
  vos_shake256(stream, sizeof stream, seed, 64);
  for (unsigned i = 0; i < 256; i++) c[i] = 0;
  unsigned at = 8;
  for (unsigned i = 196; i < 256; i++) {
    unsigned j;
    do {
      if (at == sizeof stream) return 0;
      j = stream[at++];
    } while (j > i);
    c[i] = c[j];
    unsigned bit = i - 196;
    c[j] = (stream[bit/8] >> (bit%8)) & 1u ? Q - 1 : 1;
  }
  return 1;
}
static int hints(uint8_t out[8][256], const uint8_t bytes[83]) {
  unsigned previous = 0;
  for (unsigned row = 0; row < 8; row++) {
    unsigned end = bytes[75+row];
    if (end < previous || end > 75) return 0;
    for (unsigned j = 0; j < 256; j++) out[row][j] = 0;
    for (unsigned j = previous; j < end; j++) {
      if (j > previous && bytes[j] <= bytes[j-1]) return 0;
      out[row][bytes[j]] = 1;
    }
    previous = end;
  }
  for (unsigned j = previous; j < 75; j++) if (bytes[j]) return 0;
  return 1;
}
static unsigned use_hint(int32_t r, unsigned hint) {
  // Centered reduction is (-gamma2,gamma2], as in MlDsa.dsa_decompose.
  int32_t low = r % 523776;
  if (low > 261888) low -= 523776;
  int32_t hi = (r - low) / 523776;
  if (r - low == Q - 1) { hi = 0; low--; }
  if (hint) hi = (hi + (low > 0 ? 1 : 15)) % 16;
  return (unsigned)hi;
}

int vos_mldsa87_verify_mu(const uint8_t *pk, size_t pk_len,
  const uint8_t *mu, size_t mu_len, const uint8_t *sig, size_t sig_len) {
  if (pk_len != VOS_MLDSA87_PUBLIC_BYTES || sig_len != VOS_MLDSA87_SIGNATURE_BYTES ||
      mu_len != 64 || !pk || !sig || !mu) return 0;
  poly z[7], c, a, sum, t;
  uint8_t hint[8][256], packed[8*128], check[64];
  if (!hints(hint, sig + 4544) || !challenge(c, sig)) return 0;
  ntt(c);
  for (unsigned col = 0; col < 7; col++) {
    for (unsigned i = 0; i < 256; i++) {
      int32_t v = 524288 - (int32_t)unpack(sig + 64 + col*640, i, 20);
      if (v >= 524168 || v <= -524168) return 0;
      z[col][i] = mod(v);
    }
    ntt(z[col]);
  }
  for (unsigned row = 0; row < 8; row++) {
    for (unsigned i = 0; i < 256; i++) sum[i] = 0;
    for (unsigned col = 0; col < 7; col++) {
      if (!matrix(a, pk, col, row)) return 0;
      for (unsigned i = 0; i < 256; i++) sum[i] = mod(sum[i] + (int64_t)a[i]*z[col][i]);
    }
    for (unsigned i = 0; i < 256; i++) t[i] = mod((int64_t)8192 * unpack(pk + 32 + row*320, i, 10));
    ntt(t);
    for (unsigned i = 0; i < 256; i++) sum[i] = mod(sum[i] - (int64_t)c[i]*t[i]);
    intt(sum);
    for (unsigned i = 0; i < 128; i++) packed[row*128+i] = (uint8_t)(
      use_hint(sum[2*i], hint[row][2*i]) | (use_hint(sum[2*i+1], hint[row][2*i+1]) << 4));
  }
  vos_shake256_ctx x;
  vos_shake256_init(&x);
  (void)vos_shake256_absorb(&x, mu, 64);
  (void)vos_shake256_absorb(&x, packed, sizeof packed);
  vos_shake256_squeeze(&x, check, sizeof check);
  unsigned difference = 0;
  for (unsigned i = 0; i < 64; i++) difference |= check[i] ^ sig[i];
  return difference == 0;
}

static int verify(const uint8_t *pk, size_t pk_len, const uint8_t *m, size_t m_len,
  const uint8_t *ctx, size_t ctx_len, const uint8_t *sig, size_t sig_len, int pure) {
  if (pk_len != VOS_MLDSA87_PUBLIC_BYTES || sig_len != VOS_MLDSA87_SIGNATURE_BYTES ||
      m_len > VOS_SIGNATURE_MESSAGE_MAX || ctx_len > 255 || !pk || !sig ||
      (m_len && !m) || (ctx_len && !ctx)) return 0;
  uint8_t tr[64], mu[64];
  vos_shake256(tr, sizeof tr, pk, pk_len);
  vos_shake256_ctx x;
  vos_shake256_init(&x);
  (void)vos_shake256_absorb(&x, tr, sizeof tr);
  if (pure) {
    uint8_t prefix[2] = {0, (uint8_t)ctx_len};
    (void)vos_shake256_absorb(&x, prefix, 2);
    (void)vos_shake256_absorb(&x, ctx, ctx_len);
  }
  (void)vos_shake256_absorb(&x, m, m_len);
  vos_shake256_squeeze(&x, mu, sizeof mu);
  return vos_mldsa87_verify_mu(pk, pk_len, mu, sizeof mu, sig, sig_len);
}
int vos_mldsa87_verify(const uint8_t *pk, size_t pk_len,
  const uint8_t *m, size_t m_len, const uint8_t *ctx, size_t ctx_len,
  const uint8_t *sig, size_t sig_len) {
  return verify(pk, pk_len, m, m_len, ctx, ctx_len, sig, sig_len, 1);
}
int vos_mldsa87_verify_internal(const uint8_t *pk, size_t pk_len,
  const uint8_t *m, size_t m_len, const uint8_t *sig, size_t sig_len) {
  return verify(pk, pk_len, m, m_len, NULL, 0, sig, sig_len, 0);
}
