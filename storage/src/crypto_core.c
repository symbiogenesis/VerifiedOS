// SPDX-License-Identifier: Apache-2.0
#include "vos_crypto_core.h"

static void zero_bytes(uint8_t *dst, size_t length)
{
    if (dst == NULL) {
        return;
    }
    for (size_t i = 0u; i < length; ++i) {
        dst[i] = 0u;
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

static const uint8_t aes_sbox[256] = {
    0x63u, 0x7cu, 0x77u, 0x7bu, 0xf2u, 0x6bu, 0x6fu, 0xc5u,
    0x30u, 0x01u, 0x67u, 0x2bu, 0xfeu, 0xd7u, 0xabu, 0x76u,
    0xcau, 0x82u, 0xc9u, 0x7du, 0xfau, 0x59u, 0x47u, 0xf0u,
    0xadu, 0xd4u, 0xa2u, 0xafu, 0x9cu, 0xa4u, 0x72u, 0xc0u,
    0xb7u, 0xfdu, 0x93u, 0x26u, 0x36u, 0x3fu, 0xf7u, 0xccu,
    0x34u, 0xa5u, 0xe5u, 0xf1u, 0x71u, 0xd8u, 0x31u, 0x15u,
    0x04u, 0xc7u, 0x23u, 0xc3u, 0x18u, 0x96u, 0x05u, 0x9au,
    0x07u, 0x12u, 0x80u, 0xe2u, 0xebu, 0x27u, 0xb2u, 0x75u,
    0x09u, 0x83u, 0x2cu, 0x1au, 0x1bu, 0x6eu, 0x5au, 0xa0u,
    0x52u, 0x3bu, 0xd6u, 0xb3u, 0x29u, 0xe3u, 0x2fu, 0x84u,
    0x53u, 0xd1u, 0x00u, 0xedu, 0x20u, 0xfcu, 0xb1u, 0x5bu,
    0x6au, 0xcbu, 0xbeu, 0x39u, 0x4au, 0x4cu, 0x58u, 0xcfu,
    0xd0u, 0xefu, 0xaau, 0xfbu, 0x43u, 0x4du, 0x33u, 0x85u,
    0x45u, 0xf9u, 0x02u, 0x7fu, 0x50u, 0x3cu, 0x9fu, 0xa8u,
    0x51u, 0xa3u, 0x40u, 0x8fu, 0x92u, 0x9du, 0x38u, 0xf5u,
    0xbcu, 0xb6u, 0xdau, 0x21u, 0x10u, 0xffu, 0xf3u, 0xd2u,
    0xcdu, 0x0cu, 0x13u, 0xecu, 0x5fu, 0x97u, 0x44u, 0x17u,
    0xc4u, 0xa7u, 0x7eu, 0x3du, 0x64u, 0x5du, 0x19u, 0x73u,
    0x60u, 0x81u, 0x4fu, 0xdcu, 0x22u, 0x2au, 0x90u, 0x88u,
    0x46u, 0xeeu, 0xb8u, 0x14u, 0xdeu, 0x5eu, 0x0bu, 0xdbu,
    0xe0u, 0x32u, 0x3au, 0x0au, 0x49u, 0x06u, 0x24u, 0x5cu,
    0xc2u, 0xd3u, 0xacu, 0x62u, 0x91u, 0x95u, 0xe4u, 0x79u,
    0xe7u, 0xc8u, 0x37u, 0x6du, 0x8du, 0xd5u, 0x4eu, 0xa9u,
    0x6cu, 0x56u, 0xf4u, 0xeau, 0x65u, 0x7au, 0xaeu, 0x08u,
    0xbau, 0x78u, 0x25u, 0x2eu, 0x1cu, 0xa6u, 0xb4u, 0xc6u,
    0xe8u, 0xddu, 0x74u, 0x1fu, 0x4bu, 0xbdu, 0x8bu, 0x8au,
    0x70u, 0x3eu, 0xb5u, 0x66u, 0x48u, 0x03u, 0xf6u, 0x0eu,
    0x61u, 0x35u, 0x57u, 0xb9u, 0x86u, 0xc1u, 0x1du, 0x9eu,
    0xe1u, 0xf8u, 0x98u, 0x11u, 0x69u, 0xd9u, 0x8eu, 0x94u,
    0x9bu, 0x1eu, 0x87u, 0xe9u, 0xceu, 0x55u, 0x28u, 0xdfu,
    0x8cu, 0xa1u, 0x89u, 0x0du, 0xbfu, 0xe6u, 0x42u, 0x68u,
    0x41u, 0x99u, 0x2du, 0x0fu, 0xb0u, 0x54u, 0xbbu, 0x16u
};

static const uint8_t aes_inv_sbox[256] = {
    0x52u, 0x09u, 0x6au, 0xd5u, 0x30u, 0x36u, 0xa5u, 0x38u,
    0xbfu, 0x40u, 0xa3u, 0x9eu, 0x81u, 0xf3u, 0xd7u, 0xfbu,
    0x7cu, 0xe3u, 0x39u, 0x82u, 0x9bu, 0x2fu, 0xffu, 0x87u,
    0x34u, 0x8eu, 0x43u, 0x44u, 0xc4u, 0xdeu, 0xe9u, 0xcbu,
    0x54u, 0x7bu, 0x94u, 0x32u, 0xa6u, 0xc2u, 0x23u, 0x3du,
    0xeeu, 0x4cu, 0x95u, 0x0bu, 0x42u, 0xfau, 0xc3u, 0x4eu,
    0x08u, 0x2eu, 0xa1u, 0x66u, 0x28u, 0xd9u, 0x24u, 0xb2u,
    0x76u, 0x5bu, 0xa2u, 0x49u, 0x6du, 0x8bu, 0xd1u, 0x25u,
    0x72u, 0xf8u, 0xf6u, 0x64u, 0x86u, 0x68u, 0x98u, 0x16u,
    0xd4u, 0xa4u, 0x5cu, 0xccu, 0x5du, 0x65u, 0xb6u, 0x92u,
    0x6cu, 0x70u, 0x48u, 0x50u, 0xfdu, 0xedu, 0xb9u, 0xdau,
    0x5eu, 0x15u, 0x46u, 0x57u, 0xa7u, 0x8du, 0x9du, 0x84u,
    0x90u, 0xd8u, 0xabu, 0x00u, 0x8cu, 0xbcu, 0xd3u, 0x0au,
    0xf7u, 0xe4u, 0x58u, 0x05u, 0xb8u, 0xb3u, 0x45u, 0x06u,
    0xd0u, 0x2cu, 0x1eu, 0x8fu, 0xcau, 0x3fu, 0x0fu, 0x02u,
    0xc1u, 0xafu, 0xbdu, 0x03u, 0x01u, 0x13u, 0x8au, 0x6bu,
    0x3au, 0x91u, 0x11u, 0x41u, 0x4fu, 0x67u, 0xdcu, 0xeau,
    0x97u, 0xf2u, 0xcfu, 0xceu, 0xf0u, 0xb4u, 0xe6u, 0x73u,
    0x96u, 0xacu, 0x74u, 0x22u, 0xe7u, 0xadu, 0x35u, 0x85u,
    0xe2u, 0xf9u, 0x37u, 0xe8u, 0x1cu, 0x75u, 0xdfu, 0x6eu,
    0x47u, 0xf1u, 0x1au, 0x71u, 0x1du, 0x29u, 0xc5u, 0x89u,
    0x6fu, 0xb7u, 0x62u, 0x0eu, 0xaau, 0x18u, 0xbeu, 0x1bu,
    0xfcu, 0x56u, 0x3eu, 0x4bu, 0xc6u, 0xd2u, 0x79u, 0x20u,
    0x9au, 0xdbu, 0xc0u, 0xfeu, 0x78u, 0xcdu, 0x5au, 0xf4u,
    0x1fu, 0xddu, 0xa8u, 0x33u, 0x88u, 0x07u, 0xc7u, 0x31u,
    0xb1u, 0x12u, 0x10u, 0x59u, 0x27u, 0x80u, 0xecu, 0x5fu,
    0x60u, 0x51u, 0x7fu, 0xa9u, 0x19u, 0xb5u, 0x4au, 0x0du,
    0x2du, 0xe5u, 0x7au, 0x9fu, 0x93u, 0xc9u, 0x9cu, 0xefu,
    0xa0u, 0xe0u, 0x3bu, 0x4du, 0xaeu, 0x2au, 0xf5u, 0xb0u,
    0xc8u, 0xebu, 0xbbu, 0x3cu, 0x83u, 0x53u, 0x99u, 0x61u,
    0x17u, 0x2bu, 0x04u, 0x7eu, 0xbau, 0x77u, 0xd6u, 0x26u,
    0xe1u, 0x69u, 0x14u, 0x63u, 0x55u, 0x21u, 0x0cu, 0x7du
};

static uint8_t gf256_xtime(uint8_t x)
{
    return (uint8_t)((x << 1u) ^ ((x & 0x80u) != 0u ? 0x1bu : 0x00u));
}

static uint8_t gf256_mul(uint8_t a, uint8_t b)
{
    uint8_t p = 0u;
    uint8_t cur = a;
    for (uint32_t i = 0u; i < 8u; ++i) {
        if ((b & (1u << i)) != 0u) {
            p ^= cur;
        }
        cur = gf256_xtime(cur);
    }
    return p;
}

struct aes_schedule {
    uint32_t nr;
    uint8_t round_keys[15u * VOS_CRYPTO_BLOCK_BYTES];
};

static int aes_expand_key(const uint8_t *key, size_t key_bytes,
                          struct aes_schedule *sched)
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
            temp[0] = (uint8_t)(aes_sbox[temp[1]] ^ rcon);
            temp[1] = aes_sbox[temp[2]];
            temp[2] = aes_sbox[temp[3]];
            temp[3] = aes_sbox[t0];
            rcon = gf256_xtime(rcon);
        } else if (nk > 6u && (i % nk) == 4u) {
            temp[0] = aes_sbox[temp[0]];
            temp[1] = aes_sbox[temp[1]];
            temp[2] = aes_sbox[temp[2]];
            temp[3] = aes_sbox[temp[3]];
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

static void aes_encrypt_with_schedule(const struct aes_schedule *sched,
                                      const uint8_t input[16],
                                      uint8_t output[16])
{
    uint8_t s[16];
    uint8_t tmp[16];
    copy_bytes(s, input, 16u);
    aes_add_round_key(s, sched->round_keys);
    for (uint32_t r = 1u; r < sched->nr; ++r) {
        for (uint32_t i = 0u; i < 16u; ++i) {
            s[i] = aes_sbox[s[i]];
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
            s[4u * col + 0u] = (uint8_t)(gf256_mul(2u, a0) ^ gf256_mul(3u, a1) ^ a2 ^ a3);
            s[4u * col + 1u] = (uint8_t)(a0 ^ gf256_mul(2u, a1) ^ gf256_mul(3u, a2) ^ a3);
            s[4u * col + 2u] = (uint8_t)(a0 ^ a1 ^ gf256_mul(2u, a2) ^ gf256_mul(3u, a3));
            s[4u * col + 3u] = (uint8_t)(gf256_mul(3u, a0) ^ a1 ^ a2 ^ gf256_mul(2u, a3));
        }
        aes_add_round_key(s, sched->round_keys + 16u * r);
    }
    for (uint32_t i = 0u; i < 16u; ++i) {
        s[i] = aes_sbox[s[i]];
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
    struct aes_schedule sched;
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
    struct aes_schedule sched;
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
            tmp[i] = aes_inv_sbox[tmp[i]];
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
        tmp[i] = aes_inv_sbox[tmp[i]];
    }
    aes_add_round_key(tmp, sched.round_keys);
    copy_bytes(output, tmp, 16u);
    zero_bytes((uint8_t *)&sched, sizeof(sched));
    return 1;
}

static void gf128_mul_block(const uint8_t x[16], const uint8_t y[16],
                            uint8_t z[16])
{
    uint8_t v[16];
    uint8_t acc[16];
    copy_bytes(v, y, 16u);
    zero_bytes(acc, 16u);
    for (uint32_t i = 0u; i < 128u; ++i) {
        const uint8_t bit = (uint8_t)((x[i / 8u] >> (7u - (i % 8u))) & 1u);
        const uint8_t mask = (uint8_t)(0u - bit);
        for (uint32_t b = 0u; b < 16u; ++b) {
            acc[b] ^= (uint8_t)(v[b] & mask);
        }
        const uint8_t lsb = (uint8_t)(v[15] & 1u);
        for (uint32_t b = 15u; b > 0u; --b) {
            v[b] = (uint8_t)((v[b] >> 1u) | ((v[b - 1u] & 1u) << 7u));
        }
        v[0] = (uint8_t)((v[0] >> 1u) ^ (lsb != 0u ? 0xe1u : 0x00u));
    }
    copy_bytes(z, acc, 16u);
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

static void gcm_gctr(const struct aes_schedule *sched, const uint8_t icb[16],
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

static void gcm_compute_tag(const struct aes_schedule *sched,
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

int vos_aes_gcm_encrypt(const uint8_t *key, size_t key_bytes,
                        const uint8_t *iv, size_t iv_length,
                        const uint8_t *aad, size_t aad_length,
                        const uint8_t *plaintext, size_t length,
                        uint8_t *ciphertext,
                        uint8_t tag[VOS_CRYPTO_TAG_BYTES])
{
    struct aes_schedule sched;
    uint8_t zero_blk[16] = {0};
    uint8_t h[16];
    uint8_t j0[16];
    uint8_t cb[16];
    if (tag == NULL || iv_length == 0u || iv == NULL ||
        (aad_length != 0u && aad == NULL) ||
        (length != 0u && (plaintext == NULL || ciphertext == NULL)) ||
        !aes_expand_key(key, key_bytes, &sched)) {
        return 0;
    }
    aes_encrypt_with_schedule(&sched, zero_blk, h);
    gcm_compute_j0(h, iv, iv_length, j0);
    copy_bytes(cb, j0, 16u);
    gcm_inc32(cb);
    if (length != 0u) {
        gcm_gctr(&sched, cb, plaintext, length, ciphertext);
    }
    gcm_compute_tag(&sched, h, j0, aad, aad_length, ciphertext, length, tag);
    zero_bytes((uint8_t *)&sched, sizeof(sched));
    zero_bytes(h, sizeof(h));
    zero_bytes(j0, sizeof(j0));
    zero_bytes(cb, sizeof(cb));
    return 1;
}

int vos_aes_gcm_open(const uint8_t *key, size_t key_bytes,
                     const uint8_t *iv, size_t iv_length,
                     const uint8_t *aad, size_t aad_length,
                     const uint8_t *ciphertext, size_t length,
                     const uint8_t tag[VOS_CRYPTO_TAG_BYTES],
                     uint8_t *plaintext)
{
    struct aes_schedule sched;
    uint8_t zero_blk[16] = {0};
    uint8_t h[16];
    uint8_t j0[16];
    uint8_t cb[16];
    uint8_t expected[VOS_CRYPTO_TAG_BYTES];
    if (tag == NULL || iv_length == 0u || iv == NULL ||
        (aad_length != 0u && aad == NULL) ||
        (length != 0u && (ciphertext == NULL || plaintext == NULL)) ||
        !aes_expand_key(key, key_bytes, &sched)) {
        if (plaintext != NULL && length != 0u) {
            zero_bytes(plaintext, length);
        }
        return 0;
    }
    aes_encrypt_with_schedule(&sched, zero_blk, h);
    gcm_compute_j0(h, iv, iv_length, j0);
    gcm_compute_tag(&sched, h, j0, aad, aad_length, ciphertext, length, expected);
    if (!equal_bytes_ct(expected, tag, VOS_CRYPTO_TAG_BYTES)) {
        if (plaintext != NULL && length != 0u) {
            zero_bytes(plaintext, length);
        }
        zero_bytes((uint8_t *)&sched, sizeof(sched));
        zero_bytes(h, sizeof(h));
        zero_bytes(j0, sizeof(j0));
        zero_bytes(expected, sizeof(expected));
        return 0;
    }
    copy_bytes(cb, j0, 16u);
    gcm_inc32(cb);
    if (length != 0u) {
        gcm_gctr(&sched, cb, ciphertext, length, plaintext);
    }
    zero_bytes((uint8_t *)&sched, sizeof(sched));
    zero_bytes(h, sizeof(h));
    zero_bytes(j0, sizeof(j0));
    zero_bytes(cb, sizeof(cb));
    zero_bytes(expected, sizeof(expected));
    return 1;
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
    const uint64_t counter = core->rot_epoch_counter;
    const uint64_t ceiling = core->rot_epoch_ceiling;
    zero_bytes((uint8_t *)core, sizeof(*core));
    core->rot_epoch_counter = counter;
    core->rot_epoch_ceiling = ceiling;
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
    return vos_aes_gcm_encrypt(dom->aead_key, dom->key_bytes,
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
    return vos_aes_gcm_open(dom->aead_key, dom->key_bytes,
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
    uint8_t payload[8u + 8u + 8u + 8u + 8u];
    (void)state_digest;
    payload[0] = 'V';
    payload[1] = 'O';
    payload[2] = 'S';
    payload[3] = 'E';
    payload[4] = 'P';
    payload[5] = 'C';
    payload[6] = 'H';
    payload[7] = '1';
    put_le64(payload + 8u, dom->domain_id);
    put_le64(payload + 16u, epoch);
    put_le64(payload + 24u, region_id);
    put_le64(payload + 32u, region_version);
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
    compute_epoch_root(dom, next_epoch, region_id, region_version,
                       state_digest, core->sealed_epoch_root);
    core->rot_epoch_counter = next_epoch;
    core->epoch_sealed = 1u;
    core->epoch_sealed_mask |= (1u << slot);
    *sealed_epoch_out = next_epoch;
    copy_bytes(epoch_root_out, core->sealed_epoch_root, VOS_CRYPTO_DIGEST_BYTES);
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
        !core->epoch_sealed || expected_epoch == 0u ||
        expected_epoch != core->rot_epoch_counter) {
        return 0;
    }
    compute_epoch_root(dom, expected_epoch, region_id, region_version,
                       state_digest, expected_root);
    const int ok = equal_bytes_ct(expected_root, epoch_root, VOS_CRYPTO_DIGEST_BYTES) &&
                   equal_bytes_ct(core->sealed_epoch_root, epoch_root, VOS_CRYPTO_DIGEST_BYTES);
    zero_bytes(expected_root, sizeof(expected_root));
    return ok;
}
