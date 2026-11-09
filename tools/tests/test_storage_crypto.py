# SPDX-License-Identifier: Apache-2.0
"""Independent byte oracles and native controls for the storage crypto repair."""

import ctypes
import hashlib
import hmac
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

from tests.harness import Case, ensure

INDEPENDENT_CASES = True
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "storage" / "src" / "crypto_core.c"
INCLUDE = ROOT / "storage" / "include"
HARNESS = ROOT / "storage" / "host" / "crypto_regressions.c"


def _multiply_byte(a: int, b: int) -> int:
    product = 0
    while b:
        if b & 1:
            product ^= a
        a <<= 1
        if a & 256:
            a ^= 0x11B
        b >>= 1
    return product


def _sbox() -> list[int]:
    values = []
    for x in range(256):
        inverse = next((y for y in range(256) if _multiply_byte(x, y) == 1), 0)
        value = inverse ^ 0x63
        for shift in range(1, 5):
            value ^= ((inverse << shift) | (inverse >> (8 - shift))) & 255
        values.append(value)
    return values


SBOX = _sbox()


def _aes(key: bytes, block: bytes) -> bytes:
    rounds = len(key) // 4 + 6
    expanded = list(key)
    rcon = 1
    while len(expanded) < 16 * (rounds + 1):
        temp = expanded[-4:]
        if len(expanded) % len(key) == 0:
            temp = [SBOX[x] for x in temp[1:] + temp[:1]]
            temp[0] ^= rcon
            rcon = _multiply_byte(rcon, 2)
        elif len(key) == 32 and len(expanded) % len(key) == 16:
            temp = [SBOX[x] for x in temp]
        for x in temp:
            expanded.append(expanded[-len(key)] ^ x)
    state = [x ^ expanded[i] for i, x in enumerate(block)]
    for r in range(1, rounds + 1):
        state = [SBOX[state[(i % 4) + 4 * ((i // 4 + i % 4) % 4)]] for i in range(16)]
        if r < rounds:
            mixed = []
            for col in range(4):
                a = state[4 * col:4 * col + 4]
                mixed.extend(
                    _multiply_byte(2, a[i]) ^ _multiply_byte(3, a[(i + 1) % 4])
                    ^ a[(i + 2) % 4] ^ a[(i + 3) % 4]
                    for i in range(4)
                )
            state = mixed
        state = [x ^ expanded[16 * r + i] for i, x in enumerate(state)]
    return bytes(state)


def _ghash(h: bytes, data: bytes) -> bytes:
    y = 0
    for offset in range(0, len(data), 16):
        x = y ^ int.from_bytes(data[offset:offset + 16].ljust(16, b"\0"), "big")
        value = int.from_bytes(h, "big")
        y = 0
        for bit in range(127, -1, -1):
            if x & (1 << bit):
                y ^= value
            value = (value >> 1) ^ (0xE1 << 120 if value & 1 else 0)
    return y.to_bytes(16, "big")


def _gcm(key: bytes, iv: bytes, aad: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    h = _aes(key, bytes(16))
    if len(iv) == 12:
        j0 = iv + b"\0\0\0\1"
    else:
        j0 = _ghash(h, iv + bytes(-len(iv) % 16) + bytes(8) + (8 * len(iv)).to_bytes(8, "big"))
    ciphertext = bytearray()
    ctr = int.from_bytes(j0[-4:], "big")
    for offset in range(0, len(plaintext), 16):
        ctr = (ctr + 1) % (1 << 32)
        stream = _aes(key, j0[:12] + ctr.to_bytes(4, "big"))
        ciphertext.extend(x ^ y for x, y in zip(plaintext[offset:offset + 16], stream))
    auth = aad + bytes(-len(aad) % 16) + ciphertext + bytes(-len(ciphertext) % 16)
    auth += (len(aad) * 8).to_bytes(8, "big") + (len(ciphertext) * 8).to_bytes(8, "big")
    tag = bytes(x ^ y for x, y in zip(_ghash(h, auth), _aes(key, j0)))
    return bytes(ciphertext), tag


def _build(output: Path, *sources: Path, shared: bool = False) -> None:
    cc = next((path for name in ("cc", "gcc", "clang") if (path := shutil.which(name))), None)
    ensure(cc is not None, "native C compiler unavailable")
    command = [str(cc), "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wstrict-prototypes"]
    if shared:
        command.extend(["-shared", "-fPIC"])
    command.extend([f"-I{INCLUDE}", *(str(path) for path in sources), "-o", str(output)])
    built = subprocess.run(command, capture_output=True, text=True, check=False, timeout=60)
    ensure(built.returncode == 0, f"native crypto build failed: {built.stderr}")


def _reference_vectors() -> None:
    plain = bytes.fromhex("00112233445566778899aabbccddeeff")
    for length, expected in (
        (16, "69c4e0d86a7b0430d8cdb78070b4c55a"),
        (24, "dda97ca4864cdfe06eaf70a0ec0d7191"),
        (32, "8ea2b7ca516745bfeafc49904b496089"),
    ):
        ensure(_aes(bytes(range(length)), plain).hex() == expected, "AES reference FIPS 197 vector")
    cipher, tag = _gcm(bytes(16), bytes(12), b"", bytes(16))
    ensure(cipher.hex() == "0388dace60b6a392f328c2b971b2fe78", "GCM reference ciphertext")
    ensure(tag.hex() == "ab6e47d42cec13bdf53a67b21257bddf", "GCM reference tag")


def _native_vectors() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        library_path = Path(tmp) / "crypto.so"
        _build(library_path, SOURCE, shared=True)
        library = ctypes.CDLL(str(library_path))
        aes_args = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_void_p]
        library.vos_aes_encrypt_block.argtypes = aes_args
        library.vos_aes_decrypt_block.argtypes = aes_args
        gcm_args = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t,
                    ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t,
                    ctypes.c_void_p, ctypes.c_void_p]
        library.vos_aes_gcm_encrypt.argtypes = gcm_args
        library.vos_aes_gcm_open.argtypes = gcm_args
        rng = random.Random(0x564F534352595054)
        for key_bytes in (16, 24, 32):
            for case in range(16):
                key = rng.randbytes(key_bytes)
                plain = rng.randbytes(16)
                expected = _aes(key, plain)
                output = ctypes.create_string_buffer(16)
                ensure(library.vos_aes_encrypt_block(key, key_bytes, plain, output) == 1, "AES encrypt refused")
                ensure(output.raw == expected, "AES differs from independent byte oracle")
                ensure(library.vos_aes_decrypt_block(key, key_bytes, expected, output) == 1, "AES decrypt refused")
                ensure(output.raw == plain, "AES inverse differs from independent byte oracle")
                iv = rng.randbytes((7, 12, 20)[case % 3])
                aad = rng.randbytes((0, 1, 15, 16, 17, 31, 32, 65)[case % 8])
                plaintext = rng.randbytes((0, 1, 15, 16, 17, 31, 32, 127)[case % 8])
                cipher, tag = _gcm(key, iv, aad, plaintext)
                encoded = ctypes.create_string_buffer(max(1, len(plaintext)))
                tag_out = ctypes.create_string_buffer(16)
                ensure(library.vos_aes_gcm_encrypt(key, key_bytes, iv, len(iv), aad, len(aad),
                                                  plaintext, len(plaintext), encoded, tag_out) == 1,
                       "GCM encrypt refused")
                ensure(encoded.raw[:len(cipher)] == cipher and tag_out.raw == tag,
                       "GCM differs from independent polynomial/byte oracle")
                ensure(library.vos_aes_gcm_open(key, key_bytes, iv, len(iv), aad, len(aad),
                                               cipher, len(cipher), tag_out, encoded) == 1,
                       "GCM open refused")
                ensure(encoded.raw[:len(plaintext)] == plaintext, "GCM open bytes differ")


def _epoch_and_cache_controls() -> None:
    commit_key = hmac.digest(bytes(range(32)), b"VOSCMIT1" + (0x1000).to_bytes(8, "little")
                             + (7).to_bytes(8, "little"), "sha256")
    payload = b"VOSEPCH2" + b"".join(value.to_bytes(8, "little") for value in (0x1000, 1, 99, 1, 7))
    expected = hmac.new(commit_key, payload + bytes(range(1, 33)), hashlib.sha256).hexdigest()
    with tempfile.TemporaryDirectory() as tmp:
        binary = Path(tmp) / "crypto-regressions"
        _build(binary, SOURCE, HARNESS)
        result = subprocess.run([str(binary)], capture_output=True, text=True, check=False, timeout=60)
        ensure(result.returncode == 0, result.stderr)
        ensure(result.stdout.strip() == expected, "sealed state differs from independent epoch HMAC oracle")
        source = SOURCE.read_text(encoding="utf-8")
        for name, needle, replacement in (
            ("state-binding", "copy_bytes(payload + 48u, state_digest, VOS_CRYPTO_DIGEST_BYTES);",
             "zero_bytes(payload + 48u, VOS_CRYPTO_DIGEST_BYTES); (void)state_digest;"),
            ("domain-isolation", "expected_epoch != core->sealed_epochs[slot].epoch ||",
             "expected_epoch != core->rot_epoch_counter ||"),
            ("key-cache", "aes_gcm_encrypt_with_schedule(&dom->aead_schedule, dom->ghash_subkey,",
             "vos_aes_gcm_encrypt(dom->aead_key, dom->key_bytes,"),
        ):
            ensure(source.count(needle) == 1, f"missing crypto control target: {name}")
            mutant = Path(tmp) / f"{name}.c"
            mutant.write_text(source.replace(needle, replacement, 1), encoding="utf-8")
            _build(binary, mutant, HARNESS)
            result = subprocess.run([str(binary)], capture_output=True, text=True, check=False, timeout=60)
            ensure(result.returncode != 0, f"compiled crypto defect survived: {name}")


def cases() -> list[Case]:
    return [
        Case("crypto_reference_vectors", _reference_vectors, lane="any"),
        Case("crypto_native_byte_polynomial_oracles", _native_vectors, lane="guest"),
        Case("crypto_epoch_and_cache_controls", _epoch_and_cache_controls, lane="guest"),
    ]
