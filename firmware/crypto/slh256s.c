// SPDX-License-Identifier: Apache-2.0
// Authored from NIST FIPS 205 (2024), Algorithms 8, 11, 13, 17, 20 and 24.
// Specialized to SLH-DSA-SHAKE-256s: n=32,h=64,d=8,h'=8,a=14,k=22,lg_w=4.
// Fixed storage, bounded loops, no allocation, recursion or library calls.
#include "vos_signature.h"
#include "vos_keccak.h"

static void copy32(uint8_t *out, const uint8_t *in) {
  for (unsigned i = 0; i < 32; i++) out[i] = in[i];
}

static void word(uint8_t a[32], unsigned index, uint32_t v) {
  for (unsigned j = 0; j < 4; j++) a[4 * index + j] = (uint8_t)(v >> (24 - 8*j));
}

static void address(uint8_t a[32], unsigned layer, uint64_t tree,
                    unsigned type, unsigned keypair) {
  for (unsigned i = 0; i < 32; i++) a[i] = 0;
  word(a, 0, layer);
  word(a, 2, (uint32_t)(tree >> 32));
  word(a, 3, (uint32_t)tree);
  word(a, 4, type);
  word(a, 5, keypair);
}

// F, H and T_l share this SHAKE instantiation (FIPS 205 section 11.1).
static void hash(uint8_t out[32], const uint8_t seed[32],
                 const uint8_t a[32], const uint8_t *in, size_t len) {
  vos_shake256_ctx x;
  vos_shake256_init(&x);
  (void)vos_shake256_absorb(&x, seed, 32);
  (void)vos_shake256_absorb(&x, a, 32);
  (void)vos_shake256_absorb(&x, in, len);
  vos_shake256_squeeze(&x, out, 32);
}

static void parent(uint8_t node[32], const uint8_t sibling[32],
                   unsigned right, const uint8_t seed[32], const uint8_t a[32]) {
  uint8_t pair[64];
  copy32(pair + (right ? 32 : 0), node);
  copy32(pair + (right ? 0 : 32), sibling);
  hash(node, seed, a, pair, sizeof pair);
}

static unsigned digit(const uint8_t *message, unsigned bit, unsigned width) {
  unsigned value = 0;
  for (unsigned j = 0; j < width; j++) {
    unsigned at = bit + j;
    value = 2 * value + ((message[at / 8] >> (7 - at % 8)) & 1u);
  }
  return value;
}

static void fors(uint8_t out[32], const uint8_t *sig, const uint8_t digest[39],
                 const uint8_t seed[32], uint64_t tree, unsigned leaf) {
  uint8_t roots[22 * 32], a[32];
  address(a, 0, tree, 3, leaf); // FORS_TREE
  for (unsigned i = 0; i < 22; i++) {
    unsigned index = (i << 14) + digit(digest, i * 14, 14);
    uint8_t *node = roots + 32 * i;
    word(a, 6, 0);
    word(a, 7, index);
    hash(node, seed, a, sig, 32);
    sig += 32;
    for (unsigned height = 1; height <= 14; height++) {
      unsigned right = index & 1u;
      index >>= 1;
      word(a, 6, height);
      word(a, 7, index);
      parent(node, sig, right, seed, a);
      sig += 32;
    }
  }
  address(a, 0, tree, 4, leaf); // FORS_ROOTS, clearing height/index
  hash(out, seed, a, roots, sizeof roots);
}

static void xmss(uint8_t node[32], const uint8_t *sig, const uint8_t seed[32],
                 unsigned layer, uint64_t tree, unsigned leaf) {
  uint8_t chains[67 * 32], a[32];
  unsigned digits[67], checksum = 0;
  for (unsigned i = 0; i < 64; i++) {
    digits[i] = digit(node, 4 * i, 4);
    checksum += 15 - digits[i];
  }
  // The three big-endian base-16 digits of the checksum. This is exactly
  // the standard's shift by four followed by base_2b over two bytes.
  for (unsigned i = 0; i < 3; i++) digits[64 + i] = (checksum >> (8 - 4*i)) & 15u;
  address(a, layer, tree, 0, leaf); // WOTS_HASH
  for (unsigned i = 0; i < 67; i++) {
    uint8_t *chain = chains + i * 32;
    copy32(chain, sig + i * 32);
    word(a, 6, i);
    for (unsigned step = digits[i]; step < 15; step++) {
      word(a, 7, step);
      hash(chain, seed, a, chain, 32);
    }
  }
  address(a, layer, tree, 1, leaf); // WOTS_PK
  hash(node, seed, a, chains, sizeof chains);
  sig += 67 * 32;
  address(a, layer, tree, 2, 0); // TREE clears the keypair field
  for (unsigned height = 1; height <= 8; height++) {
    unsigned right = leaf & 1u;
    leaf >>= 1;
    word(a, 6, height);
    word(a, 7, leaf);
    parent(node, sig, right, seed, a);
    sig += 32;
  }
}

static int verify(const uint8_t *pk, size_t pk_len, const uint8_t *message,
                  size_t message_len, const uint8_t *context, size_t context_len,
                  const uint8_t *sig, size_t sig_len, int pure) {
  if (pk_len != VOS_SLH256S_PUBLIC_BYTES || sig_len != VOS_SLH256S_SIGNATURE_BYTES ||
      message_len > VOS_SIGNATURE_MESSAGE_MAX || context_len > 255 ||
      !pk || !sig || (message_len && !message) || (context_len && !context)) return 0;
  uint8_t digest[47], node[32];
  vos_shake256_ctx x;
  vos_shake256_init(&x);
  (void)vos_shake256_absorb(&x, sig, 32);
  (void)vos_shake256_absorb(&x, pk, 64);
  if (pure) {
    uint8_t prefix[2] = {0, (uint8_t)context_len};
    (void)vos_shake256_absorb(&x, prefix, 2);
    (void)vos_shake256_absorb(&x, context, context_len);
  }
  (void)vos_shake256_absorb(&x, message, message_len);
  vos_shake256_squeeze(&x, digest, sizeof digest);
  uint64_t tree = 0;
  for (unsigned i = 39; i < 46; i++) tree = (tree << 8) | digest[i];
  unsigned leaf = digest[46];
  sig += 32;
  fors(node, sig, digest, pk, tree, leaf);
  sig += 22 * 15 * 32;
  for (unsigned layer = 0; layer < 8; layer++) {
    xmss(node, sig, pk, layer, tree, leaf);
    sig += 75 * 32;
    leaf = (unsigned)(tree & 255u);
    tree >>= 8;
  }
  unsigned difference = 0;
  for (unsigned i = 0; i < 32; i++) difference |= node[i] ^ pk[32+i];
  return difference == 0;
}

int vos_slh256s_verify_internal(const uint8_t *pk, size_t pk_len,
  const uint8_t *m, size_t m_len, const uint8_t *sig, size_t sig_len) {
  return verify(pk, pk_len, m, m_len, NULL, 0, sig, sig_len, 0);
}
int vos_slh256s_verify(const uint8_t *pk, size_t pk_len,
  const uint8_t *m, size_t m_len, const uint8_t *ctx, size_t ctx_len,
  const uint8_t *sig, size_t sig_len) {
  return verify(pk, pk_len, m, m_len, ctx, ctx_len, sig, sig_len, 1);
}

_Static_assert(VOS_SLH256S_PUBLIC_BYTES == VOS_BOOT_PUBLIC_KEY_BYTES, "boot root size");
_Static_assert(VOS_SLH256S_SIGNATURE_BYTES == VOS_BOOT_SIGNATURE_BYTES, "boot signature size");
vos_sig_result vos_boot_slh256s_verify(void *context, const uint8_t *message,
  size_t message_len, const uint8_t *sig, const uint8_t *pk) {
  (void)context;
  if (message_len != VOS_BOOT_SIGNED_BYTES) return VOS_SIG_REJECT;
  return vos_slh256s_verify_internal(pk, VOS_SLH256S_PUBLIC_BYTES, message,
    message_len, sig, VOS_SLH256S_SIGNATURE_BYTES) ? VOS_SIG_ACCEPT : VOS_SIG_REJECT;
}
