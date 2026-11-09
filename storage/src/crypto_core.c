// SPDX-License-Identifier: Apache-2.0
#include "vos_crypto_core.h"

static void zero_bytes(uint8_t *dst, size_t length)
{
    if (dst == NULL) {
        return;
    }
    volatile uint8_t *wipe = dst;
    for (size_t i = 0u; i < length; ++i) {
        wipe[i] = 0u;
    }
}

static void copy_bytes(uint8_t *dst, const uint8_t *src, size_t length)
{
    for (size_t i = 0u; i < length; ++i) {
        dst[i] = src[i];
    }
}

static int equal_bytes_ct(const uint8_t *a, const uint8_t *b, size_t length)
{
    uint8_t diff = 0u;
    for (size_t i = 0u; i < length; ++i) {
        diff |= (uint8_t)(a[i] ^ b[i]);
    }
    return diff == 0u;
}

static void put_be32(uint8_t *dst, uint32_t value)
{
    dst[0] = (uint8_t)(value >> 24u);
    dst[1] = (uint8_t)(value >> 16u);
    dst[2] = (uint8_t)(value >> 8u);
    dst[3] = (uint8_t)value;
}

static uint32_t get_be32(const uint8_t *src)
{
    return ((uint32_t)src[0] << 24u) |
           ((uint32_t)src[1] << 16u) |
           ((uint32_t)src[2] << 8u) |
           (uint32_t)src[3];
}

static void put_be64(uint8_t *dst, uint64_t value)
{
    for (uint32_t i = 0u; i < 8u; ++i) {
        dst[i] = (uint8_t)(value >> (56u - 8u * i));
    }
}

static void put_le64(uint8_t *dst, uint64_t value)
{
    for (uint32_t i = 0u; i < 8u; ++i) {
        dst[i] = (uint8_t)(value >> (8u * i));
    }
}

static uint32_t rotr32(uint32_t x, uint32_t n)
{
    return (x >> n) | (x << (32u - n));
}

static const uint32_t sha256_initial[8] = {
    0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
    0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u
};

static const uint32_t sha256_k[64] = {
    0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u,
    0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
    0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
    0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
    0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu,
    0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
    0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u,
    0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
    0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
    0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
    0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u,
    0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
    0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u,
    0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
    0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
    0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u
};

struct sha256_state {
    uint32_t h[8];
    uint8_t block[64];
    size_t block_used;
    uint64_t total_bits;
};

static void sha256_compress(uint32_t h[8], const uint8_t block[64])
{
    uint32_t w[64];
    for (uint32_t t = 0u; t < 16u; ++t) {
        w[t] = get_be32(block + 4u * t);
    }
    for (uint32_t t = 16u; t < 64u; ++t) {
        const uint32_t s0 = rotr32(w[t - 15u], 7u) ^ rotr32(w[t - 15u], 18u) ^ (w[t - 15u] >> 3u);
        const uint32_t s1 = rotr32(w[t - 2u], 17u) ^ rotr32(w[t - 2u], 19u) ^ (w[t - 2u] >> 10u);
        w[t] = w[t - 16u] + s0 + w[t - 7u] + s1;
    }
    uint32_t a = h[0];
    uint32_t b = h[1];
    uint32_t c = h[2];
    uint32_t d = h[3];
    uint32_t e = h[4];
    uint32_t f = h[5];
    uint32_t g = h[6];
    uint32_t v = h[7];
    for (uint32_t t = 0u; t < 64u; ++t) {
        const uint32_t big_s1 = rotr32(e, 6u) ^ rotr32(e, 11u) ^ rotr32(e, 25u);
        const uint32_t ch = (e & f) ^ ((~e) & g);
        const uint32_t t1 = v + big_s1 + ch + sha256_k[t] + w[t];
        const uint32_t big_s0 = rotr32(a, 2u) ^ rotr32(a, 13u) ^ rotr32(a, 22u);
        const uint32_t maj = (a & b) ^ (a & c) ^ (b & c);
        const uint32_t t2 = big_s0 + maj;
        v = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }
    h[0] += a;
    h[1] += b;
    h[2] += c;
    h[3] += d;
    h[4] += e;
    h[5] += f;
    h[6] += g;
    h[7] += v;
}

static void sha256_init(struct sha256_state *st)
{
    for (uint32_t i = 0u; i < 8u; ++i) {
        st->h[i] = sha256_initial[i];
    }
    zero_bytes(st->block, sizeof(st->block));
    st->block_used = 0u;
    st->total_bits = 0u;
}

static void sha256_update(struct sha256_state *st, const uint8_t *data, size_t length)
{
    for (size_t i = 0u; i < length; ++i) {
        st->block[st->block_used] = data[i];
        ++st->block_used;
        st->total_bits += 8u;
        if (st->block_used == 64u) {
            sha256_compress(st->h, st->block);
            st->block_used = 0u;
        }
    }
}

static void sha256_final(struct sha256_state *st, uint8_t digest[VOS_CRYPTO_DIGEST_BYTES])
{
    st->block[st->block_used] = 0x80u;
    ++st->block_used;
    if (st->block_used > 56u) {
        while (st->block_used < 64u) {
            st->block[st->block_used] = 0u;
            ++st->block_used;
        }
        sha256_compress(st->h, st->block);
        st->block_used = 0u;
    }
    while (st->block_used < 56u) {
        st->block[st->block_used] = 0u;
        ++st->block_used;
    }
    put_be64(st->block + 56u, st->total_bits);
    sha256_compress(st->h, st->block);
    for (uint32_t i = 0u; i < 8u; ++i) {
        put_be32(digest + 4u * i, st->h[i]);
    }
    zero_bytes((uint8_t *)st, sizeof(*st));
}

int vos_sha256(const uint8_t *message, size_t length,
               uint8_t digest[VOS_CRYPTO_DIGEST_BYTES])
{
    struct sha256_state st;
    if (digest == NULL || (length != 0u && message == NULL)) {
        return 0;
    }
    sha256_init(&st);
    if (length != 0u) {
        sha256_update(&st, message, length);
    }
    sha256_final(&st, digest);
    return 1;
}

int vos_hmac_sha256(const uint8_t *key, size_t key_length,
                    const uint8_t *message, size_t message_length,
                    uint8_t mac[VOS_CRYPTO_DIGEST_BYTES])
{
    uint8_t k0[64];
    uint8_t pad[64];
    uint8_t inner[VOS_CRYPTO_DIGEST_BYTES];
    struct sha256_state st;
    if (mac == NULL || (key_length != 0u && key == NULL) ||
        (message_length != 0u && message == NULL)) {
        return 0;
    }
    zero_bytes(k0, sizeof(k0));
    if (key_length > 64u) {
        if (!vos_sha256(key, key_length, k0)) {
            return 0;
        }
    } else if (key_length != 0u) {
        copy_bytes(k0, key, key_length);
    }
    for (uint32_t i = 0u; i < 64u; ++i) {
        pad[i] = (uint8_t)(k0[i] ^ 0x36u);
    }
    sha256_init(&st);
    sha256_update(&st, pad, 64u);
    if (message_length != 0u) {
        sha256_update(&st, message, message_length);
    }
    sha256_final(&st, inner);
    for (uint32_t i = 0u; i < 64u; ++i) {
        pad[i] = (uint8_t)(k0[i] ^ 0x5cu);
    }
    sha256_init(&st);
    sha256_update(&st, pad, 64u);
    sha256_update(&st, inner, VOS_CRYPTO_DIGEST_BYTES);
    sha256_final(&st, mac);
    zero_bytes(k0, sizeof(k0));
    zero_bytes(pad, sizeof(pad));
    zero_bytes(inner, sizeof(inner));
    return 1;
}

static uint8_t gf256_xtime(uint8_t x)
{
    const uint8_t mask = (uint8_t)(0u - (uint32_t)(x >> 7u));
    return (uint8_t)((x << 1u) ^ (0x1bu & mask));
}

static uint8_t gf256_mul(uint8_t a, uint8_t b)
{
    uint8_t p = 0u;
    uint8_t cur = a;
    for (uint32_t i = 0u; i < 8u; ++i) {
        const uint8_t mask = (uint8_t)(0u - (uint32_t)((b >> i) & 1u));
        p ^= (uint8_t)(cur & mask);
        cur = gf256_xtime(cur);
    }
    return p;
}

/* [The functional AES reference](../../proofs/AesGcm.v#sub_byte) derives the
 * substitution from field inversion and the affine map. Fixed arithmetic here
 * removes secret-indexed tables; binary constant-time qualification is separate. */
static uint8_t gf256_inverse(uint8_t x)
{
    const uint8_t x2 = gf256_mul(x, x);
    const uint8_t x3 = gf256_mul(x2, x);
    const uint8_t x6 = gf256_mul(x3, x3);
    const uint8_t x12 = gf256_mul(x6, x6);
    const uint8_t x15 = gf256_mul(x12, x3);
    const uint8_t x30 = gf256_mul(x15, x15);
    const uint8_t x60 = gf256_mul(x30, x30);
    const uint8_t x120 = gf256_mul(x60, x60);
    const uint8_t x240 = gf256_mul(x120, x120);
    const uint8_t x252 = gf256_mul(x240, x12);
    return gf256_mul(x252, x2);
}

static uint8_t rotl8(uint8_t x, uint32_t shift)
{
    return (uint8_t)((x << shift) | (x >> (8u - shift)));
}

static uint8_t aes_sub_byte(uint8_t x)
{
    const uint8_t y = gf256_inverse(x);
    return (uint8_t)(y ^ rotl8(y, 1u) ^ rotl8(y, 2u) ^
                     rotl8(y, 3u) ^ rotl8(y, 4u) ^ 0x63u);
}

static uint8_t aes_inv_sub_byte(uint8_t x)
{
    const uint8_t y = (uint8_t)(rotl8(x, 1u) ^ rotl8(x, 3u) ^
                                rotl8(x, 6u) ^ 0x05u);
    return gf256_inverse(y);
}

static int aes_expand_key(const uint8_t *key, size_t key_bytes,
                          struct vos_crypto_aes_schedule *sched)
{
    uint32_t nk = 0u;
    if (key == NULL || sched == NULL) {
        return 0;
    }
    if (key_bytes == VOS_CRYPTO_KEY_BYTES_128) {
        nk = 4u;
        sched->nr = 10u;
    } else if (key_bytes == VOS_CRYPTO_KEY_BYTES_192) {
        nk = 6u;
        sched->nr = 12u;
    } else if (key_bytes == VOS_CRYPTO_KEY_BYTES_256) {
        nk = 8u;
        sched->nr = 14u;
    } else {
        return 0;
    }
    copy_bytes(sched->round_keys, key, key_bytes);
    const uint32_t total_words = 4u * (sched->nr + 1u);
    uint8_t rcon = 0x01u;
    for (uint32_t i = nk; i < total_words; ++i) {
        uint8_t temp[4];
        copy_bytes(temp, sched->round_keys + 4u * (i - 1u), 4u);
        if (i % nk == 0u) {
            const uint8_t t0 = temp[0];
            temp[0] = (uint8_t)(aes_sub_byte(temp[1]) ^ rcon);
            temp[1] = aes_sub_byte(temp[2]);
            temp[2] = aes_sub_byte(temp[3]);
            temp[3] = aes_sub_byte(t0);
            rcon = gf256_xtime(rcon);
        } else if (nk > 6u && (i % nk) == 4u) {
            temp[0] = aes_sub_byte(temp[0]);
            temp[1] = aes_sub_byte(temp[1]);
            temp[2] = aes_sub_byte(temp[2]);
            temp[3] = aes_sub_byte(temp[3]);
        }
        for (uint32_t j = 0u; j < 4u; ++j) {
            sched->round_keys[4u * i + j] =
                (uint8_t)(sched->round_keys[4u * (i - nk) + j] ^ temp[j]);
        }
    }
    return 1;
}

static void aes_add_round_key(uint8_t state[16], const uint8_t rk[16])
{
    for (uint32_t i = 0u; i < 16u; ++i) {
        state[i] ^= rk[i];
    }
}

static void aes_encrypt_with_schedule(const struct vos_crypto_aes_schedule *sched,
                                      const uint8_t input[16],
                                      uint8_t output[16])
{
    uint8_t s[16];
    uint8_t tmp[16];
    copy_bytes(s, input, 16u);
    aes_add_round_key(s, sched->round_keys);
    for (uint32_t r = 1u; r < sched->nr; ++r) {
        for (uint32_t i = 0u; i < 16u; ++i) {
            s[i] = aes_sub_byte(s[i]);
        }
        for (uint32_t row = 0u; row < 4u; ++row) {
            for (uint32_t col = 0u; col < 4u; ++col) {
                tmp[row + 4u * col] = s[row + 4u * ((col + row) % 4u)];
            }
        }
        for (uint32_t col = 0u; col < 4u; ++col) {
            const uint8_t a0 = tmp[4u * col + 0u];
            const uint8_t a1 = tmp[4u * col + 1u];
            const uint8_t a2 = tmp[4u * col + 2u];
            const uint8_t a3 = tmp[4u * col + 3u];
            const uint8_t sum = (uint8_t)(a0 ^ a1 ^ a2 ^ a3);
            s[4u * col + 0u] = (uint8_t)(a0 ^ sum ^ gf256_xtime((uint8_t)(a0 ^ a1)));
            s[4u * col + 1u] = (uint8_t)(a1 ^ sum ^ gf256_xtime((uint8_t)(a1 ^ a2)));
            s[4u * col + 2u] = (uint8_t)(a2 ^ sum ^ gf256_xtime((uint8_t)(a2 ^ a3)));
            s[4u * col + 3u] = (uint8_t)(a3 ^ sum ^ gf256_xtime((uint8_t)(a3 ^ a0)));
        }
        aes_add_round_key(s, sched->round_keys + 16u * r);
    }
    for (uint32_t i = 0u; i < 16u; ++i) {
        s[i] = aes_sub_byte(s[i]);
    }
    for (uint32_t row = 0u; row < 4u; ++row) {
        for (uint32_t col = 0u; col < 4u; ++col) {
            tmp[row + 4u * col] = s[row + 4u * ((col + row) % 4u)];
        }
    }
    aes_add_round_key(tmp, sched->round_keys + 16u * sched->nr);
    copy_bytes(output, tmp, 16u);
}

int vos_aes_encrypt_block(const uint8_t *key, size_t key_bytes,
                          const uint8_t input[VOS_CRYPTO_BLOCK_BYTES],
                          uint8_t output[VOS_CRYPTO_BLOCK_BYTES])
{
    struct vos_crypto_aes_schedule sched;
    if (input == NULL || output == NULL || !aes_expand_key(key, key_bytes, &sched)) {
        return 0;
    }
    aes_encrypt_with_schedule(&sched, input, output);
    zero_bytes((uint8_t *)&sched, sizeof(sched));
    return 1;
}

int vos_aes_decrypt_block(const uint8_t *key, size_t key_bytes,
                          const uint8_t input[VOS_CRYPTO_BLOCK_BYTES],
                          uint8_t output[VOS_CRYPTO_BLOCK_BYTES])
{
    struct vos_crypto_aes_schedule sched;
    uint8_t s[16];
    uint8_t tmp[16];
    if (input == NULL || output == NULL || !aes_expand_key(key, key_bytes, &sched)) {
        return 0;
    }
    copy_bytes(s, input, 16u);
    aes_add_round_key(s, sched.round_keys + 16u * sched.nr);
    for (uint32_t r = sched.nr - 1u; r >= 1u; --r) {
        for (uint32_t row = 0u; row < 4u; ++row) {
            for (uint32_t col = 0u; col < 4u; ++col) {
                tmp[row + 4u * col] = s[row + 4u * ((col + 4u - row) % 4u)];
            }
        }
        for (uint32_t i = 0u; i < 16u; ++i) {
            tmp[i] = aes_inv_sub_byte(tmp[i]);
        }
        aes_add_round_key(tmp, sched.round_keys + 16u * r);
        for (uint32_t col = 0u; col < 4u; ++col) {
            const uint8_t a0 = tmp[4u * col + 0u];
            const uint8_t a1 = tmp[4u * col + 1u];
            const uint8_t a2 = tmp[4u * col + 2u];
            const uint8_t a3 = tmp[4u * col + 3u];
            s[4u * col + 0u] = (uint8_t)(gf256_mul(14u, a0) ^ gf256_mul(11u, a1) ^
                                         gf256_mul(13u, a2) ^ gf256_mul(9u, a3));
            s[4u * col + 1u] = (uint8_t)(gf256_mul(9u, a0) ^ gf256_mul(14u, a1) ^
                                         gf256_mul(11u, a2) ^ gf256_mul(13u, a3));
            s[4u * col + 2u] = (uint8_t)(gf256_mul(13u, a0) ^ gf256_mul(9u, a1) ^
                                         gf256_mul(14u, a2) ^ gf256_mul(11u, a3));
            s[4u * col + 3u] = (uint8_t)(gf256_mul(11u, a0) ^ gf256_mul(13u, a1) ^
                                         gf256_mul(9u, a2) ^ gf256_mul(14u, a3));
        }
    }
    for (uint32_t row = 0u; row < 4u; ++row) {
        for (uint32_t col = 0u; col < 4u; ++col) {
            tmp[row + 4u * col] = s[row + 4u * ((col + 4u - row) % 4u)];
        }
    }
    for (uint32_t i = 0u; i < 16u; ++i) {
        tmp[i] = aes_inv_sub_byte(tmp[i]);
    }
    aes_add_round_key(tmp, sched.round_keys);
    copy_bytes(output, tmp, 16u);
    zero_bytes((uint8_t *)&sched, sizeof(sched));
    return 1;
}

static uint64_t get_be64(const uint8_t src[8])
{
    uint64_t value = 0u;
    for (uint32_t i = 0u; i < 8u; ++i) {
        value = (value << 8u) | src[i];
    }
    return value;
}

static void gf128_mul_block(const uint8_t x[16], const uint8_t y[16],
                            uint8_t z[16])
{
    const uint64_t x_hi = get_be64(x);
    const uint64_t x_lo = get_be64(x + 8u);
    uint64_t v_hi = get_be64(y);
    uint64_t v_lo = get_be64(y + 8u);
    uint64_t acc_hi = 0u;
    uint64_t acc_lo = 0u;
    for (uint32_t i = 0u; i < 128u; ++i) {
        const uint64_t word = i < 64u ? x_hi : x_lo;
        const uint64_t mask = UINT64_C(0) - ((word >> (63u - (i % 64u))) & 1u);
        acc_hi ^= v_hi & mask;
        acc_lo ^= v_lo & mask;
        const uint64_t reduction = UINT64_C(0) - (v_lo & 1u);
        v_lo = (v_lo >> 1u) | (v_hi << 63u);
        v_hi = (v_hi >> 1u) ^ (UINT64_C(0xe100000000000000) & reduction);
    }
    put_be64(z, acc_hi);
    put_be64(z + 8u, acc_lo);
}

static void ghash_absorb(const uint8_t h[16], uint8_t y[16],
                         const uint8_t *data, size_t length)
{
    size_t offset = 0u;
    while (offset < length) {
        uint8_t blk[16];
        zero_bytes(blk, 16u);
        const size_t chunk = (length - offset < 16u) ? (length - offset) : 16u;
        copy_bytes(blk, data + offset, chunk);
        for (uint32_t i = 0u; i < 16u; ++i) {
            y[i] ^= blk[i];
        }
        gf128_mul_block(y, h, y);
        offset += chunk;
    }
}

static void gcm_inc32(uint8_t cb[16])
{
    const uint32_t ctr = get_be32(cb + 12u) + 1u;
    put_be32(cb + 12u, ctr);
}

static void gcm_compute_j0(const uint8_t h[16], const uint8_t *iv,
                           size_t iv_length, uint8_t j0[16])
{
    zero_bytes(j0, 16u);
    if (iv_length == VOS_CRYPTO_NONCE_BYTES) {
        copy_bytes(j0, iv, VOS_CRYPTO_NONCE_BYTES);
        j0[15] = 1u;
        return;
    }
    ghash_absorb(h, j0, iv, iv_length);
    uint8_t len_blk[16];
    zero_bytes(len_blk, 16u);
    put_be64(len_blk + 8u, (uint64_t)iv_length * 8u);
    ghash_absorb(h, j0, len_blk, 16u);
}

static void gcm_gctr(const struct vos_crypto_aes_schedule *sched, const uint8_t icb[16],
                     const uint8_t *input, size_t length, uint8_t *output)
{
    uint8_t cb[16];
    uint8_t ks[16];
    copy_bytes(cb, icb, 16u);
    size_t offset = 0u;
    while (offset < length) {
        aes_encrypt_with_schedule(sched, cb, ks);
        const size_t chunk = (length - offset < 16u) ? (length - offset) : 16u;
        for (size_t i = 0u; i < chunk; ++i) {
            output[offset + i] = (uint8_t)(input[offset + i] ^ ks[i]);
        }
        gcm_inc32(cb);
        offset += chunk;
    }
    zero_bytes(cb, sizeof(cb));
    zero_bytes(ks, sizeof(ks));
}

static void gcm_compute_tag(const struct vos_crypto_aes_schedule *sched,
                            const uint8_t h[16], const uint8_t j0[16],
                            const uint8_t *aad, size_t aad_length,
                            const uint8_t *ciphertext, size_t length,
                            uint8_t tag[VOS_CRYPTO_TAG_BYTES])
{
    uint8_t s[16];
    uint8_t lengths[16];
    zero_bytes(s, 16u);
    if (aad_length != 0u) {
        ghash_absorb(h, s, aad, aad_length);
    }
    if (length != 0u) {
        ghash_absorb(h, s, ciphertext, length);
    }
    put_be64(lengths, (uint64_t)aad_length * 8u);
    put_be64(lengths + 8u, (uint64_t)length * 8u);
    ghash_absorb(h, s, lengths, 16u);
    gcm_gctr(sched, j0, s, 16u, tag);
    zero_bytes(s, sizeof(s));
}

static int gcm_valid_input(const uint8_t *iv, size_t iv_length,
                            const uint8_t *aad, size_t aad_length,
                            const uint8_t *input, size_t length,
                            const uint8_t *output, const uint8_t *tag)
{
    return tag != NULL && iv_length != 0u && iv != NULL &&
           (aad_length == 0u || aad != NULL) &&
           (length == 0u || (input != NULL && output != NULL)) &&
           (uint64_t)length <= UINT64_C(0xfffffffe) * 16u &&
           (uint64_t)aad_length <= UINT64_MAX / 8u &&
           (uint64_t)iv_length <= UINT64_MAX / 8u;
}

static int aes_gcm_encrypt_with_schedule(const struct vos_crypto_aes_schedule *sched,
                                         const uint8_t h[16],
                                         const uint8_t *iv, size_t iv_length,
                                         const uint8_t *aad, size_t aad_length,
                                         const uint8_t *plaintext, size_t length,
                                         uint8_t *ciphertext, uint8_t tag[16])
{
    if (!gcm_valid_input(iv, iv_length, aad, aad_length,
                          plaintext, length, ciphertext, tag)) {
        return 0;
    }
    uint8_t j0[16];
    uint8_t cb[16];
    gcm_compute_j0(h, iv, iv_length, j0);
    copy_bytes(cb, j0, 16u);
    gcm_inc32(cb);
    if (length != 0u) {
        gcm_gctr(sched, cb, plaintext, length, ciphertext);
    }
    gcm_compute_tag(sched, h, j0, aad, aad_length, ciphertext, length, tag);
    zero_bytes(j0, sizeof(j0));
    zero_bytes(cb, sizeof(cb));
    return 1;
}

static int aes_gcm_open_with_schedule(const struct vos_crypto_aes_schedule *sched,
                                      const uint8_t h[16],
                                      const uint8_t *iv, size_t iv_length,
                                      const uint8_t *aad, size_t aad_length,
                                      const uint8_t *ciphertext, size_t length,
                                      const uint8_t tag[16], uint8_t *plaintext)
{
    if (!gcm_valid_input(iv, iv_length, aad, aad_length,
                          ciphertext, length, plaintext, tag)) {
        if (plaintext != NULL && length != 0u) {
            zero_bytes(plaintext, length);
        }
        return 0;
    }
    uint8_t j0[16];
    uint8_t cb[16];
    uint8_t expected[VOS_CRYPTO_TAG_BYTES];
    gcm_compute_j0(h, iv, iv_length, j0);
    gcm_compute_tag(sched, h, j0, aad, aad_length, ciphertext, length, expected);
    if (!equal_bytes_ct(expected, tag, VOS_CRYPTO_TAG_BYTES)) {
        if (plaintext != NULL && length != 0u) {
            zero_bytes(plaintext, length);
        }
        zero_bytes(j0, sizeof(j0));
        zero_bytes(expected, sizeof(expected));
        return 0;
    }
    copy_bytes(cb, j0, 16u);
    gcm_inc32(cb);
    if (length != 0u) {
        gcm_gctr(sched, cb, ciphertext, length, plaintext);
    }
    zero_bytes(j0, sizeof(j0));
    zero_bytes(cb, sizeof(cb));
    zero_bytes(expected, sizeof(expected));
    return 1;
}

int vos_aes_gcm_encrypt(const uint8_t *key, size_t key_bytes,
                        const uint8_t *iv, size_t iv_length,
                        const uint8_t *aad, size_t aad_length,
                        const uint8_t *plaintext, size_t length,
                        uint8_t *ciphertext,
                        uint8_t tag[VOS_CRYPTO_TAG_BYTES])
{
    struct vos_crypto_aes_schedule sched;
    uint8_t zero_blk[16] = {0};
    uint8_t h[16];
    if (!aes_expand_key(key, key_bytes, &sched)) {
        return 0;
    }
    aes_encrypt_with_schedule(&sched, zero_blk, h);
    const int ok = aes_gcm_encrypt_with_schedule(&sched, h, iv, iv_length,
                                                 aad, aad_length, plaintext,
                                                 length, ciphertext, tag);
    zero_bytes((uint8_t *)&sched, sizeof(sched));
    zero_bytes(h, sizeof(h));
    return ok;
}

int vos_aes_gcm_open(const uint8_t *key, size_t key_bytes,
                     const uint8_t *iv, size_t iv_length,
                     const uint8_t *aad, size_t aad_length,
                     const uint8_t *ciphertext, size_t length,
                     const uint8_t tag[VOS_CRYPTO_TAG_BYTES],
                     uint8_t *plaintext)
{
    struct vos_crypto_aes_schedule sched;
    uint8_t zero_blk[16] = {0};
    uint8_t h[16];
    if (!aes_expand_key(key, key_bytes, &sched)) {
        if (plaintext != NULL && length != 0u) {
            zero_bytes(plaintext, length);
        }
        return 0;
    }
    aes_encrypt_with_schedule(&sched, zero_blk, h);
    const int ok = aes_gcm_open_with_schedule(&sched, h, iv, iv_length,
                                              aad, aad_length, ciphertext,
                                              length, tag, plaintext);
    zero_bytes((uint8_t *)&sched, sizeof(sched));
    zero_bytes(h, sizeof(h));
    return ok;
}

static void derive_purpose_key(const uint8_t *master_key, size_t key_bytes,
                               uint64_t domain_id, uint64_t key_epoch,
                               const uint8_t label[8],
                               uint8_t out[VOS_CRYPTO_DIGEST_BYTES])
{
    uint8_t info[24];
    copy_bytes(info, label, 8u);
    put_le64(info + 8u, domain_id);
    put_le64(info + 16u, key_epoch);
    (void)vos_hmac_sha256(master_key, key_bytes, info, sizeof(info), out);
    zero_bytes(info, sizeof(info));
}

void vos_crypto_core_init(struct vos_crypto_core *core,
                          uint64_t rot_epoch_ceiling)
{
    if (core == NULL) {
        return;
    }
    zero_bytes((uint8_t *)core, sizeof(*core));
    core->rot_epoch_ceiling = rot_epoch_ceiling;
}

int vos_crypto_core_unlock_domain(struct vos_crypto_core *core, uint32_t slot,
                                  uint64_t domain_id, uint64_t key_epoch,
                                  const uint8_t *master_key, size_t key_bytes)
{
    static const uint8_t label_aead[8] = {'V', 'O', 'S', 'A', 'E', 'A', 'D', '1'};
    static const uint8_t label_dedup[8] = {'V', 'O', 'S', 'D', 'D', 'U', 'P', '1'};
    static const uint8_t label_commit[8] = {'V', 'O', 'S', 'C', 'M', 'I', 'T', '1'};
    if (core == NULL || slot >= VOS_CRYPTO_MAX_DOMAINS || master_key == NULL ||
        domain_id == 0u ||
        (key_bytes != VOS_CRYPTO_KEY_BYTES_128 &&
         key_bytes != VOS_CRYPTO_KEY_BYTES_256)) {
        return 0;
    }
    if ((core->epoch_sealed_mask & (1u << slot)) != 0u &&
        (core->sealed_epochs[slot].domain_id != domain_id ||
         core->sealed_epochs[slot].key_epoch != key_epoch)) {
        return 0;
    }
    for (uint32_t i = 0u; i < VOS_CRYPTO_MAX_DOMAINS; ++i) {
        if (i != slot &&
            ((core->domains[i].provisioned && core->domains[i].domain_id == domain_id) ||
             ((core->epoch_sealed_mask & (1u << i)) != 0u &&
              core->sealed_epochs[i].domain_id == domain_id))) {
            return 0;
        }
    }
    struct vos_crypto_domain_slot *dst = &core->domains[slot];
    zero_bytes((uint8_t *)dst, sizeof(*dst));
    derive_purpose_key(master_key, key_bytes, domain_id, key_epoch,
                       label_aead, dst->aead_key);
    derive_purpose_key(master_key, key_bytes, domain_id, key_epoch,
                       label_dedup, dst->dedup_key);
    derive_purpose_key(master_key, key_bytes, domain_id, key_epoch,
                       label_commit, dst->commit_key);
    dst->domain_id = domain_id;
    dst->key_epoch = key_epoch;
    dst->key_bytes = (uint32_t)key_bytes;
    if (!aes_expand_key(dst->aead_key, key_bytes, &dst->aead_schedule)) {
        zero_bytes((uint8_t *)dst, sizeof(*dst));
        return 0;
    }
    const uint8_t zero_blk[16] = {0};
    aes_encrypt_with_schedule(&dst->aead_schedule, zero_blk, dst->ghash_subkey);
    dst->provisioned = 1u;
    return 1;
}

int vos_crypto_core_lock_domain(struct vos_crypto_core *core, uint32_t slot)
{
    if (core == NULL || slot >= VOS_CRYPTO_MAX_DOMAINS) {
        return 0;
    }
    zero_bytes((uint8_t *)&core->domains[slot], sizeof(core->domains[slot]));
    return 1;
}

void vos_crypto_core_erase_all(struct vos_crypto_core *core)
{
    if (core == NULL) {
        return;
    }
    zero_bytes((uint8_t *)core->domains, sizeof(core->domains));
}

static const struct vos_crypto_domain_slot *active_slot(
    const struct vos_crypto_core *core, uint32_t slot)
{
    if (core == NULL || slot >= VOS_CRYPTO_MAX_DOMAINS ||
        !core->domains[slot].provisioned) {
        return NULL;
    }
    return &core->domains[slot];
}

int vos_crypto_core_seal(const struct vos_crypto_core *core, uint32_t slot,
                         const uint8_t nonce[VOS_CRYPTO_NONCE_BYTES],
                         const uint8_t *aad, size_t aad_length,
                         const uint8_t *plaintext, size_t length,
                         uint8_t *ciphertext,
                         uint8_t tag[VOS_CRYPTO_TAG_BYTES])
{
    const struct vos_crypto_domain_slot *dom = active_slot(core, slot);
    if (dom == NULL || nonce == NULL) {
        return 0;
    }
    return aes_gcm_encrypt_with_schedule(&dom->aead_schedule, dom->ghash_subkey,
                               nonce, VOS_CRYPTO_NONCE_BYTES,
                               aad, aad_length,
                               plaintext, length, ciphertext, tag);
}

int vos_crypto_core_open(const struct vos_crypto_core *core, uint32_t slot,
                         const uint8_t nonce[VOS_CRYPTO_NONCE_BYTES],
                         const uint8_t *aad, size_t aad_length,
                         const uint8_t *ciphertext, size_t length,
                         const uint8_t tag[VOS_CRYPTO_TAG_BYTES],
                         uint8_t *plaintext)
{
    const struct vos_crypto_domain_slot *dom = active_slot(core, slot);
    if (dom == NULL || nonce == NULL) {
        if (plaintext != NULL && length != 0u) {
            zero_bytes(plaintext, length);
        }
        return 0;
    }
    return aes_gcm_open_with_schedule(&dom->aead_schedule, dom->ghash_subkey,
                            nonce, VOS_CRYPTO_NONCE_BYTES,
                            aad, aad_length,
                            ciphertext, length, tag, plaintext);
}

int vos_crypto_core_keyed_digest(const struct vos_crypto_core *core,
                                 uint32_t slot,
                                 const uint8_t *plaintext, size_t length,
                                 uint8_t digest[VOS_CRYPTO_DIGEST_BYTES])
{
    const struct vos_crypto_domain_slot *dom = active_slot(core, slot);
    uint8_t k0[64];
    uint8_t pad[64];
    uint8_t inner[VOS_CRYPTO_DIGEST_BYTES];
    uint8_t header[24];
    struct sha256_state st;
    if (dom == NULL || digest == NULL || (length != 0u && plaintext == NULL)) {
        return 0;
    }
    header[0] = 'V';
    header[1] = 'O';
    header[2] = 'S';
    header[3] = 'K';
    header[4] = 'D';
    header[5] = 'I';
    header[6] = 'G';
    header[7] = '1';
    put_le64(header + 8u, dom->domain_id);
    put_le64(header + 16u, (uint64_t)length);
    zero_bytes(k0, sizeof(k0));
    copy_bytes(k0, dom->dedup_key, VOS_CRYPTO_DIGEST_BYTES);
    for (uint32_t i = 0u; i < 64u; ++i) {
        pad[i] = (uint8_t)(k0[i] ^ 0x36u);
    }
    sha256_init(&st);
    sha256_update(&st, pad, 64u);
    sha256_update(&st, header, sizeof(header));
    if (length != 0u) {
        sha256_update(&st, plaintext, length);
    }
    sha256_final(&st, inner);
    for (uint32_t i = 0u; i < 64u; ++i) {
        pad[i] = (uint8_t)(k0[i] ^ 0x5cu);
    }
    sha256_init(&st);
    sha256_update(&st, pad, 64u);
    sha256_update(&st, inner, VOS_CRYPTO_DIGEST_BYTES);
    sha256_final(&st, digest);
    zero_bytes(k0, sizeof(k0));
    zero_bytes(pad, sizeof(pad));
    zero_bytes(inner, sizeof(inner));
    zero_bytes(header, sizeof(header));
    return 1;
}

int vos_crypto_core_commit_mac(const struct vos_crypto_core *core,
                               uint32_t slot,
                               const uint8_t *record, size_t length,
                               uint8_t mac[VOS_CRYPTO_DIGEST_BYTES])
{
    const struct vos_crypto_domain_slot *dom = active_slot(core, slot);
    if (dom == NULL || mac == NULL || (length != 0u && record == NULL)) {
        return 0;
    }
    return vos_hmac_sha256(dom->commit_key, VOS_CRYPTO_DIGEST_BYTES,
                           record, length, mac);
}

int vos_crypto_core_verify_commit_mac(const struct vos_crypto_core *core,
                                      uint32_t slot,
                                      const uint8_t *record, size_t length,
                                      const uint8_t expected[VOS_CRYPTO_DIGEST_BYTES])
{
    uint8_t actual[VOS_CRYPTO_DIGEST_BYTES];
    if (expected == NULL ||
        !vos_crypto_core_commit_mac(core, slot, record, length, actual)) {
        return 0;
    }
    const int ok = equal_bytes_ct(actual, expected, VOS_CRYPTO_DIGEST_BYTES);
    zero_bytes(actual, sizeof(actual));
    return ok;
}

static void compute_epoch_root(const struct vos_crypto_domain_slot *dom,
                               uint64_t epoch, uint64_t region_id,
                               uint64_t region_version,
                               const uint8_t state_digest[VOS_CRYPTO_DIGEST_BYTES],
                               uint8_t out[VOS_CRYPTO_DIGEST_BYTES])
{
    uint8_t payload[8u + 8u + 8u + 8u + 8u + 8u + VOS_CRYPTO_DIGEST_BYTES];
    payload[0] = 'V';
    payload[1] = 'O';
    payload[2] = 'S';
    payload[3] = 'E';
    payload[4] = 'P';
    payload[5] = 'C';
    payload[6] = 'H';
    payload[7] = '2';
    put_le64(payload + 8u, dom->domain_id);
    put_le64(payload + 16u, epoch);
    put_le64(payload + 24u, region_id);
    put_le64(payload + 32u, region_version);
    put_le64(payload + 40u, dom->key_epoch);
    copy_bytes(payload + 48u, state_digest, VOS_CRYPTO_DIGEST_BYTES);
    (void)vos_hmac_sha256(dom->commit_key, VOS_CRYPTO_DIGEST_BYTES,
                          payload, sizeof(payload), out);
    zero_bytes(payload, sizeof(payload));
}

int vos_crypto_core_seal_epoch(struct vos_crypto_core *core, uint32_t slot,
                               uint64_t region_id, uint64_t region_version,
                               const uint8_t state_digest[VOS_CRYPTO_DIGEST_BYTES],
                               uint64_t *sealed_epoch_out,
                               uint8_t epoch_root_out[VOS_CRYPTO_DIGEST_BYTES])
{
    const struct vos_crypto_domain_slot *dom = active_slot(core, slot);
    if (dom == NULL || state_digest == NULL || sealed_epoch_out == NULL ||
        epoch_root_out == NULL || region_version == 0u ||
        core->rot_epoch_counter >= core->rot_epoch_ceiling) {
        return 0;
    }
    const uint64_t next_epoch = core->rot_epoch_counter + 1u;
    struct vos_crypto_epoch_seal *seal = &core->sealed_epochs[slot];
    compute_epoch_root(dom, next_epoch, region_id, region_version,
                       state_digest, seal->root);
    seal->domain_id = dom->domain_id;
    seal->key_epoch = dom->key_epoch;
    seal->epoch = next_epoch;
    core->rot_epoch_counter = next_epoch;
    core->epoch_sealed = 1u;
    core->epoch_sealed_mask |= (1u << slot);
    *sealed_epoch_out = next_epoch;
    copy_bytes(epoch_root_out, seal->root, VOS_CRYPTO_DIGEST_BYTES);
    return 1;
}

int vos_crypto_core_verify_epoch(const struct vos_crypto_core *core,
                                 uint32_t slot, uint64_t expected_epoch,
                                 uint64_t region_id, uint64_t region_version,
                                 const uint8_t state_digest[VOS_CRYPTO_DIGEST_BYTES],
                                 const uint8_t epoch_root[VOS_CRYPTO_DIGEST_BYTES])
{
    const struct vos_crypto_domain_slot *dom = active_slot(core, slot);
    uint8_t expected_root[VOS_CRYPTO_DIGEST_BYTES];
    if (dom == NULL || state_digest == NULL || epoch_root == NULL ||
        (core->epoch_sealed_mask & (1u << slot)) == 0u || expected_epoch == 0u ||
        expected_epoch != core->sealed_epochs[slot].epoch ||
        dom->domain_id != core->sealed_epochs[slot].domain_id ||
        dom->key_epoch != core->sealed_epochs[slot].key_epoch) {
        return 0;
    }
    compute_epoch_root(dom, expected_epoch, region_id, region_version,
                       state_digest, expected_root);
    const int ok = equal_bytes_ct(expected_root, epoch_root, VOS_CRYPTO_DIGEST_BYTES) &&
                   equal_bytes_ct(core->sealed_epochs[slot].root, epoch_root, VOS_CRYPTO_DIGEST_BYTES);
    zero_bytes(expected_root, sizeof(expected_root));
    return ok;
}
