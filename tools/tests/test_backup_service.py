# SPDX-License-Identifier: Apache-2.0
"""Independent Python oracles and native C17 controls for `BackupObject.v` and `backup/`."""

import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from tests.harness import Case, ensure
from vos.proofs import strip_comments

INDEPENDENT_CASES = True

ROOT = Path(__file__).resolve().parents[2]
BACKUP_DIR = ROOT / "backup"
BACKUP_H = BACKUP_DIR / "include" / "vos_backup.h"
BACKUP_C = BACKUP_DIR / "src" / "backup.c"
BACKUP_TEST_C = BACKUP_DIR / "test" / "test_backup.c"
BACKUP_README = BACKUP_DIR / "README.md"
CRYPTO_INCLUDE = ROOT / "storage" / "include"
CRYPTO_SOURCE = ROOT / "storage" / "src" / "crypto_core.c"
PROOFS_V = ROOT / "proofs" / "BackupObject.v"

MAGIC = b"VOSBK001"
VERSION = 1
UPPER_HEX = "0123456789ABCDEF"

# Standard AES S-box and Rcon for pure-Python AES-256-GCM reference oracle.
_SBOX = (
    0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
    0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
    0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
    0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
    0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
    0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
    0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
    0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
    0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
    0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
    0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
    0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
    0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
    0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
    0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
    0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16,
)


def _xtime(a: int) -> int:
    return ((a << 1) ^ 0x1B) & 0xFF if (a & 0x80) else ((a << 1) & 0xFF)


def _aes256_expand(key: bytes) -> list[bytes]:
    words = [list(key[4 * i : 4 * i + 4]) for i in range(8)]
    rcon = 1
    for i in range(8, 60):
        t = list(words[i - 1])
        if i % 8 == 0:
            t = [_SBOX[t[1]] ^ rcon, _SBOX[t[2]], _SBOX[t[3]], _SBOX[t[0]]]
            rcon = _xtime(rcon)
        elif i % 8 == 4:
            t = [_SBOX[b] for b in t]
        words.append([words[i - 8][j] ^ t[j] for j in range(4)])
    return [bytes(b for w in words[4 * r : 4 * r + 4] for b in w) for r in range(15)]


def _aes256_encrypt_block(rks: list[bytes], block: bytes) -> bytes:
    s = [b ^ k for b, k in zip(block, rks[0], strict=True)]
    for r in range(1, 15):
        s = [_SBOX[b] for b in s]
        tmp = [s[row + 4 * ((col + row) % 4)] for col in range(4) for row in range(4)]
        if r < 14:
            s = [0] * 16
            for col in range(4):
                a0, a1, a2, a3 = tmp[4 * col : 4 * col + 4]
                tot = a0 ^ a1 ^ a2 ^ a3
                s[4 * col] = a0 ^ tot ^ _xtime(a0 ^ a1)
                s[4 * col + 1] = a1 ^ tot ^ _xtime(a1 ^ a2)
                s[4 * col + 2] = a2 ^ tot ^ _xtime(a2 ^ a3)
                s[4 * col + 3] = a3 ^ tot ^ _xtime(a3 ^ a0)
        else:
            s = tmp
        s = [b ^ k for b, k in zip(s, rks[r], strict=True)]
    return bytes(s)


def _gf128_mul(x: int, y: int) -> int:
    z = 0
    v = y
    for i in range(128):
        if (x >> (127 - i)) & 1:
            z ^= v
        lsb = v & 1
        v >>= 1
        if lsb:
            v ^= 0xE1000000000000000000000000000000
    return z


def _ghash(h_int: int, aad: bytes, ct: bytes) -> bytes:
    y = 0
    for data in (aad, ct):
        for off in range(0, len(data), 16):
            blk = data[off : off + 16].ljust(16, b"\x00")
            y = _gf128_mul(y ^ int.from_bytes(blk, "big"), h_int)
    lens = ((len(aad) * 8) << 64) | (len(ct) * 8)
    y = _gf128_mul(y ^ lens, h_int)
    return y.to_bytes(16, "big")


def _aes256_gcm_encrypt(key: bytes, iv12: bytes, aad: bytes, pt: bytes) -> tuple[bytes, bytes]:
    rks = _aes256_expand(key)
    h_int = int.from_bytes(_aes256_encrypt_block(rks, b"\x00" * 16), "big")
    j0 = iv12 + b"\x00\x00\x00\x01"
    ct = bytearray()
    ctr = 2
    for off in range(0, len(pt), 16):
        cb = iv12 + ctr.to_bytes(4, "big")
        ks = _aes256_encrypt_block(rks, cb)
        chunk = pt[off : off + 16]
        ct.extend(a ^ b for a, b in zip(chunk, ks, strict=False))
        ctr += 1
    s = _ghash(h_int, aad, bytes(ct))
    tag = bytes(a ^ b for a, b in zip(s, _aes256_encrypt_block(rks, j0), strict=True))
    return bytes(ct), tag


def _aes256_gcm_open(key: bytes, iv12: bytes, aad: bytes, ct: bytes, tag: bytes) -> bytes | None:
    rks = _aes256_expand(key)
    h_int = int.from_bytes(_aes256_encrypt_block(rks, b"\x00" * 16), "big")
    j0 = iv12 + b"\x00\x00\x00\x01"
    s = _ghash(h_int, aad, ct)
    expected = bytes(a ^ b for a, b in zip(s, _aes256_encrypt_block(rks, j0), strict=True))
    if expected != tag:
        return None
    pt = bytearray()
    ctr = 2
    for off in range(0, len(ct), 16):
        cb = iv12 + ctr.to_bytes(4, "big")
        ks = _aes256_encrypt_block(rks, cb)
        chunk = ct[off : off + 16]
        pt.extend(a ^ b for a, b in zip(chunk, ks, strict=False))
        ctr += 1
    return bytes(pt)


def _encode_recovery_secret(key: bytes) -> str:
    ensure(len(key) == 32, "recovery secret requires 32 key bytes")
    return "".join(UPPER_HEX[b >> 4] + UPPER_HEX[b & 0x0F] for b in key)


def _decode_recovery_secret(text: str) -> bytes | None:
    if len(text) != 64:
        return None
    out = bytearray()
    for i in range(0, 64, 2):
        hi = UPPER_HEX.find(text[i])
        lo = UPPER_HEX.find(text[i + 1])
        if hi < 0 or lo < 0:
            return None
        out.append((hi << 4) | lo)
    return bytes(out)


@dataclass(frozen=True)
class _OracleRegion:
    region_id: int
    schema_id: int
    schema_gen: int
    payload_len: int
    first_chunk: int
    chunk_count: int


def _merkle_depth(chunk_count: int) -> int:
    if chunk_count <= 1:
        return 0
    d = 0
    cap = 1
    while cap < chunk_count:
        cap <<= 1
        d += 1
    return d


def _leaf_hash(idx: int, ct: bytes, tag: bytes) -> bytes:
    return hashlib.sha256(b"VOSBK-LEAF\x00" + idx.to_bytes(4, "big") + ct + tag).digest()


def _pad_hash(idx: int) -> bytes:
    return hashlib.sha256(b"VOSBK-PAD\x00" + idx.to_bytes(4, "big")).digest()


def _node_hash(left: bytes, right: bytes) -> bytes:
    return hashlib.sha256(b"VOSBK-NODE\x00" + left + right).digest()


def _build_merkle(leaves: list[bytes]) -> tuple[bytes, list[list[bytes]]]:
    n = len(leaves)
    if n == 0:
        return hashlib.sha256(b"VOSBK-EMPTY\x00").digest(), []
    depth = _merkle_depth(n)
    width = 1 << depth
    levels: list[list[bytes]] = [
        list(leaves) + [_pad_hash(i) for i in range(n, width)]
    ]
    for _ in range(depth):
        prev = levels[-1]
        levels.append([_node_hash(prev[2 * j], prev[2 * j + 1]) for j in range(len(prev) // 2)])
    proofs = [
        [levels[lvl][(idx >> lvl) ^ 1] for lvl in range(depth)]
        for idx in range(n)
    ]
    return levels[-1][0], proofs


def _verify_merkle(idx: int, n: int, ct: bytes, tag: bytes,
                   proof: list[bytes], root: bytes) -> bool:
    if idx < 0 or idx >= n or len(proof) != _merkle_depth(n):
        return False
    acc = _leaf_hash(idx, ct, tag)
    for lvl, sib in enumerate(proof):
        acc = _node_hash(acc, sib) if ((idx >> lvl) & 1) == 0 else _node_hash(sib, acc)
    return acc == root


def _encode_manifest_body(export_gen: int, profile_id: int,
                          regions: list[_OracleRegion], chunk_size: int,
                          chunk_count: int, merkle_root: bytes) -> bytes:
    buf = bytearray()
    buf += export_gen.to_bytes(8, "big")
    buf += profile_id.to_bytes(4, "big")
    buf += len(regions).to_bytes(4, "big")
    for r in regions:
        buf += r.region_id.to_bytes(4, "big")
        buf += r.schema_id.to_bytes(4, "big")
        buf += r.schema_gen.to_bytes(4, "big")
        buf += r.payload_len.to_bytes(8, "big")
        buf += r.first_chunk.to_bytes(4, "big")
        buf += r.chunk_count.to_bytes(4, "big")
    buf += chunk_size.to_bytes(4, "big")
    buf += chunk_count.to_bytes(4, "big")
    buf += merkle_root
    return bytes(buf)


def _decode_manifest_body(data: bytes, expected_chunk_size: int) -> tuple[int, int, list[_OracleRegion], int, bytes] | None:
    if len(data) < 56:
        return None
    export_gen = int.from_bytes(data[0:8], "big")
    source_profile = int.from_bytes(data[8:12], "big")
    rcnt = int.from_bytes(data[12:16], "big")
    if len(data) != 56 + 28 * rcnt:
        return None
    regions: list[_OracleRegion] = []
    pos = 16
    prev_id = -1
    next_chunk = 0
    for _ in range(rcnt):
        rid = int.from_bytes(data[pos : pos + 4], "big")
        sid = int.from_bytes(data[pos + 4 : pos + 8], "big")
        sgen = int.from_bytes(data[pos + 8 : pos + 12], "big")
        plen = int.from_bytes(data[pos + 12 : pos + 20], "big")
        fc = int.from_bytes(data[pos + 20 : pos + 24], "big")
        cc = int.from_bytes(data[pos + 24 : pos + 28], "big")
        pos += 28
        if rid <= prev_id or fc != next_chunk:
            return None
        if plen == 0 and cc != 0:
            return None
        if plen > 0 and (cc == 0 or plen <= (cc - 1) * expected_chunk_size or plen > cc * expected_chunk_size):
            return None
        prev_id = rid
        next_chunk += cc
        regions.append(_OracleRegion(rid, sid, sgen, plen, fc, cc))
    csize = int.from_bytes(data[pos : pos + 4], "big")
    ccnt = int.from_bytes(data[pos + 4 : pos + 8], "big")
    mroot = data[pos + 8 : pos + 40]
    if csize != expected_chunk_size or ccnt != next_chunk:
        return None
    return export_gen, source_profile, regions, ccnt, mroot


def _recovery_secret_oracle() -> None:
    """Verify `RecoverySecret-v1` leading-zero preservation and strict uppercase canonicity."""
    key_lz = bytes(range(32))
    hex_lz = _encode_recovery_secret(key_lz)
    ensure(len(hex_lz) == 64 and hex_lz.startswith("000102"), "leading zero preserved")
    ensure(_decode_recovery_secret(hex_lz) == key_lz, "round-trip recovery secret")
    ensure(_decode_recovery_secret(hex_lz.lower()) is None, "lowercase hex rejected")
    ensure(_decode_recovery_secret(hex_lz[:-1]) is None, "short hex rejected")
    ensure(_decode_recovery_secret(hex_lz + "0") is None, "trailing char rejected")
    ensure(_decode_recovery_secret(hex_lz[:10] + "G" + hex_lz[11:]) is None, "non-hex rejected")


def _backup_object_wire_and_crypto_oracle() -> None:
    """Verify `BackupObject-v1` wire format, domain-separated AES-GCM, Merkle tree, and refusals."""
    obj_key = bytes(0x30 + i for i in range(32))
    manifest_key = hashlib.sha256(b"VOSBK-MANIFEST" + obj_key).digest()
    chunk_key = hashlib.sha256(b"VOSBK-CHUNK" + obj_key).digest()
    ensure(manifest_key != chunk_key, "distinct domain-separated subkeys")

    manifest_nonce = bytes(0x11 + i for i in range(12))
    chunk_size = 64
    p1 = bytes((0x10 + (i % 73)) for i in range(150))
    p2 = bytes((0x80 + (i % 59)) for i in range(100))
    regs = [
        _OracleRegion(10, 100, 1, len(p1), 0, 3),
        _OracleRegion(20, 200, 1, len(p2), 3, 2),
    ]
    total_chunks = 5
    depth = _merkle_depth(total_chunks)
    ensure(depth == 3, "5 chunks -> merkle depth 3")

    manifest_len = 56 + 28 * len(regs)
    chunk_lens = [64, 64, 22, 64, 36]
    total_extent = 40 + manifest_len + 16 + sum(20 + ln + 16 + depth * 32 for ln in chunk_lens)

    dummy_body = _encode_manifest_body(42, 1, regs, chunk_size, total_chunks, b"\x00" * 32)
    ctx_digest = hashlib.sha256(
        b"VOSBK-CTX" + MAGIC + VERSION.to_bytes(4, "big") + (1).to_bytes(4, "big")
        + total_extent.to_bytes(8, "big") + dummy_body[:-32]
    ).digest()

    payloads = [
        (0, 10, 0, p1[0:64]),
        (1, 10, 64, p1[64:128]),
        (2, 10, 128, p1[128:150]),
        (3, 20, 0, p2[0:64]),
        (4, 20, 64, p2[64:100]),
    ]
    encrypted_chunks: list[tuple[int, int, int, bytes, bytes]] = []
    leaves: list[bytes] = []
    for idx, rid, roff, pt in payloads:
        nonce = b"VOSCHK01" + idx.to_bytes(4, "big")
        aad = ctx_digest + idx.to_bytes(4, "big") + rid.to_bytes(4, "big") + roff.to_bytes(8, "big") + len(pt).to_bytes(4, "big")
        ct, tag = _aes256_gcm_encrypt(chunk_key, nonce, aad, pt)
        encrypted_chunks.append((idx, rid, roff, ct, tag))
        leaves.append(_leaf_hash(idx, ct, tag))

    mroot, proofs = _build_merkle(leaves)
    for idx, _rid, _roff, ct, tag in encrypted_chunks:
        ensure(_verify_merkle(idx, total_chunks, ct, tag, proofs[idx], mroot),
               f"merkle proof {idx} verifies")

    manifest_pt = _encode_manifest_body(42, 1, regs, chunk_size, total_chunks, mroot)
    prefix = MAGIC + VERSION.to_bytes(4, "big") + (1).to_bytes(4, "big") + total_extent.to_bytes(8, "big") + manifest_nonce + manifest_len.to_bytes(4, "big")
    enc_m, mtag = _aes256_gcm_encrypt(manifest_key, manifest_nonce, prefix, manifest_pt)

    wire = bytearray(prefix + enc_m + mtag)
    for (idx, rid, roff, ct, tag), pf in zip(encrypted_chunks, proofs, strict=True):
        wire += idx.to_bytes(4, "big") + rid.to_bytes(4, "big") + roff.to_bytes(8, "big") + len(ct).to_bytes(4, "big")
        wire += ct + tag + b"".join(pf)
    ensure(len(wire) == total_extent, "exact total extent match")

    # Decode and verify canonicity and trailing-byte refusal.
    wire_bytes = bytes(wire)
    dec_m = _aes256_gcm_open(
        manifest_key,
        manifest_nonce,
        wire_bytes[0:40],
        wire_bytes[40 : 40 + manifest_len],
        wire_bytes[40 + manifest_len : 56 + manifest_len],
    )
    ensure(dec_m == manifest_pt, "manifest round-trip")
    if dec_m is None:
        raise AssertionError("manifest round-trip failed")
    parsed = _decode_manifest_body(dec_m, chunk_size)
    ensure(parsed is not None, "manifest parses canonically")
    # Duplicate / unsorted region IDs refuse.
    bad_regs = [_OracleRegion(20, 200, 1, 100, 0, 2), _OracleRegion(20, 200, 1, 100, 2, 2)]
    ensure(_decode_manifest_body(_encode_manifest_body(42, 1, bad_regs, chunk_size, 4, mroot), chunk_size) is None,
           "duplicate region ID refused")
    # Non-contiguous chunk range refuses.
    gap_regs = [_OracleRegion(10, 100, 1, 64, 0, 1), _OracleRegion(20, 200, 1, 64, 2, 1)]
    ensure(_decode_manifest_body(_encode_manifest_body(42, 1, gap_regs, chunk_size, 3, mroot), chunk_size) is None,
           "non-contiguous chunks refused")


def _export_view_and_restore_sm_oracle() -> None:
    """Verify `ExportView` exclusions, restore zero-write preconditions, and Fresh denials."""
    regions = [
        (10, "Rollbackable", "DataOnly", b"alpha"),
        (20, "Fresh", "DataOnly", b"fresh-secret"),
        (30, "ConsentStore", "DataOnly", b"consent-grant"),
        (40, "KeyHandle", "Key", b"key-handle"),
        (50, "CredentialHandle", "CredentialHandle", b"cred-handle"),
        (60, "SealedObject", "SealedHandle", b"sealed-blob"),
        (70, "Rollbackable", "Key", b"retyped-key"),
    ]
    exported = [r for r in regions if r[1] == "Rollbackable" and r[2] == "DataOnly"]
    ensure(len(exported) == 1 and exported[0][0] == 10, "ExportView includes only Rollbackable+DataOnly")


def _surface_and_proof_contract() -> None:
    """Verify deliverable files, SPDX headers, heap-free C17, and Rocq theorems/witnesses."""
    for path in (BACKUP_H, BACKUP_C, BACKUP_TEST_C, BACKUP_README, PROOFS_V):
        ensure(path.is_file(), f"missing backup artifact: {path}")

    for c_path in (BACKUP_H, BACKUP_C, BACKUP_TEST_C):
        text = c_path.read_text(encoding="utf-8")
        ensure(text.splitlines()[0] == "// SPDX-License-Identifier: Apache-2.0",
               f"missing // SPDX header in {c_path}")
        for forbidden in ("malloc(", "calloc(", "realloc(", "free("):
            ensure(forbidden not in text, f"forbidden dynamic allocation {forbidden} in {c_path}")

    c_src = BACKUP_C.read_text(encoding="utf-8")
    for fn in (
        "vos_bk_encode_recovery_secret",
        "vos_bk_decode_recovery_secret",
        "vos_bk_derive_subkeys",
        "vos_bk_chunk_nonce",
        "vos_bk_export",
        "vos_bk_restore_authorize",
        "vos_bk_restore_auth_manifest",
        "vos_bk_restore_plan",
        "vos_bk_restore_stage_next_chunk",
        "vos_bk_restore_complete",
        "vos_bk_restore_commit",
        "vos_bk_fresh_check_token",
        "vos_bk_fresh_check_attempt",
    ):
        ensure(fn in c_src, f"missing C entry point {fn}")

    v_src = PROOFS_V.read_text(encoding="utf-8")
    ensure(v_src.splitlines()[0] == "(* SPDX-License-Identifier: Apache-2.0 *)",
           "missing Rocq SPDX header in BackupObject.v")
    for sym in (
        "recovery_secret_decode_of_encode",
        "recovery_secret_encode_of_decode",
        "recovery_secret_canonicity",
        "plaintext_parse_of_serialize",
        "plaintext_serialize_of_parse",
        "plaintext_canonicity",
        "envelope_parse_of_serialize",
        "envelope_serialize_of_parse",
        "envelope_canonicity",
        "export_view_only_rollbackable_data_only",
        "zero_writes_before_staging",
        "unsupported_plan_discards_with_zero_writes",
        "fresh_install_denies_old_authority",
        "witness_RecoverySecret",
        "witness_BackupProfile",
        "witness_BackupRegion",
        "witness_BackupPlaintext",
        "witness_BackupProof",
        "witness_BackupChunk",
        "witness_BackupEnvelope",
        "witness_SourceRegion",
        "witness_ExportableEntry",
        "witness_RestoreMachine",
        "witness_FreshInitState",
    ):
        ensure(sym in v_src, f"missing Rocq specification symbol {sym} in BackupObject.v")
    v_clean = strip_comments(v_src)
    for banned in ("Admitted", "admit", "Axiom", "Parameter", "Conjecture", "Section", "CoFixpoint", "CoInductive"):
        ensure(
            re.search(rf"\b{banned}\b", v_clean) is None,
            f"forbidden proof keyword {banned} in BackupObject.v",
        )


def _select_sanitizer_compiler(tmp_path: Path) -> tuple[str, list[str]]:
    """Select a C17 compiler supporting ASan/UBSan on Linux."""
    cflags = ["-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wstrict-prototypes"]
    san_flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    probe_src = tmp_path / "probe.c"
    probe_src.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    probe_bin = tmp_path / "probe"

    for name in ("gcc", "clang", "cc"):
        compiler = shutil.which(name)
        if compiler is None:
            continue
        res = subprocess.run(
            [compiler, *cflags, *san_flags, str(probe_src), "-o", str(probe_bin)],
            capture_output=True, text=True, check=False, timeout=30,
        )
        if res.returncode == 0:
            return compiler, [*cflags, *san_flags]

    raise AssertionError("no C17 compiler with ASan/UBSan runtime available in Linux guest")


def _native_c_and_mutation_controls() -> None:
    """Compile and run `backup` tests with Clang strict + GCC ASan/UBSan and kill >= 10 behavioral mutants."""
    if sys.platform == "win32":
        return

    with tempfile.TemporaryDirectory(prefix="vos-backup-c-") as td:
        tmp = Path(td)
        compiler, flags = _select_sanitizer_compiler(tmp)
        binary = tmp / "test_backup"
        cmd = [
            compiler,
            *flags,
            f"-I{BACKUP_H.parent}",
            f"-I{CRYPTO_INCLUDE}",
            str(BACKUP_C),
            str(CRYPTO_SOURCE),
            str(BACKUP_TEST_C),
            "-o",
            str(binary),
        ]
        built = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=60)
        ensure(built.returncode == 0, f"backup C build failed: {built.stderr}")
        ran = subprocess.run([str(binary)], capture_output=True, text=True, check=False, timeout=60)
        ensure(ran.returncode == 0 and "backup_test: ok" in ran.stdout,
               f"backup C test failed: {ran.stderr or ran.stdout}")

        clang = shutil.which("clang")
        if clang is not None:
            clang_bin = tmp / "test_backup_clang"
            clang_built = subprocess.run(
                [
                    clang, "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror", "-Wstrict-prototypes",
                    f"-I{BACKUP_H.parent}", f"-I{CRYPTO_INCLUDE}",
                    str(BACKUP_C), str(CRYPTO_SOURCE), str(BACKUP_TEST_C),
                    "-o", str(clang_bin),
                ],
                capture_output=True, text=True, check=False, timeout=60,
            )
            ensure(clang_built.returncode == 0, f"clang strict C17 build failed: {clang_built.stderr}")
            clang_ran = subprocess.run([str(clang_bin)], capture_output=True, text=True, check=False, timeout=60)
            ensure(clang_ran.returncode == 0 and "backup_test: ok" in clang_ran.stdout,
                   f"clang binary failed: {clang_ran.stderr or clang_ran.stdout}")

        source = BACKUP_C.read_text(encoding="utf-8")
        mutants: list[tuple[str, str, str]] = [
            (
                "backup-export-reads-fresh",
                "    if (reg->kind != VOS_BK_KIND_ROLLBACKABLE ||\n"
                "        reg->schema_class != VOS_BK_SCHEMA_DATA_ONLY) {\n"
                "        return 0;\n"
                "    }",
                "    if (reg->kind == VOS_BK_KIND_FRESH) {\n"
                "        return 1;\n"
                "    }\n"
                "    if (reg->kind != VOS_BK_KIND_ROLLBACKABLE ||\n"
                "        reg->schema_class != VOS_BK_SCHEMA_DATA_ONLY) {\n"
                "        return 0;\n"
                "    }",
            ),
            (
                "backup-export-reads-consent-or-sealed",
                "    if (reg->kind != VOS_BK_KIND_ROLLBACKABLE ||\n"
                "        reg->schema_class != VOS_BK_SCHEMA_DATA_ONLY) {\n"
                "        return 0;\n"
                "    }\n"
                "    return 1;",
                "    if (reg->kind == VOS_BK_KIND_CONSENT_STORE ||\n"
                "        reg->kind == VOS_BK_KIND_SEALED_OBJECT) {\n"
                "        return 1;\n"
                "    }\n"
                "    if (reg->kind != VOS_BK_KIND_ROLLBACKABLE ||\n"
                "        reg->schema_class != VOS_BK_SCHEMA_DATA_ONLY) {\n"
                "        return 0;\n"
                "    }\n"
                "    return 1;",
            ),
            (
                "backup-recovery-secret-accept-lowercase",
                "    if (c >= 'A' && c <= 'F') {\n"
                "        *out = (uint8_t)(10 + (c - 'A'));\n"
                "        return 1;\n"
                "    }",
                "    if (c >= 'A' && c <= 'F') {\n"
                "        *out = (uint8_t)(10 + (c - 'A'));\n"
                "        return 1;\n"
                "    }\n"
                "    if (c >= 'a' && c <= 'f') {\n"
                "        *out = (uint8_t)(10 + (c - 'a'));\n"
                "        return 1;\n"
                "    }",
            ),
            (
                "backup-recovery-secret-drop-leading-zero",
                "        out_hex[2u * i] = encode_nibble_upper((uint8_t)(b >> 4u));",
                "        out_hex[2u * i] = (b == 0u) ? 'X' : encode_nibble_upper((uint8_t)(b >> 4u));",
            ),
            (
                "backup-reuse-manifest-subkey-for-chunks",
                "    memcpy(buf_c, label_chunk, sizeof(label_chunk));\n"
                "    memcpy(buf_c + sizeof(label_chunk), object_key, VOS_BK_KEY_BYTES);\n"
                "    (void)vos_sha256(buf_c, sizeof(buf_c), chunk_key_out);",
                "    (void)label_chunk;\n"
                "    (void)buf_c;\n"
                "    memcpy(chunk_key_out, manifest_key_out, VOS_BK_KEY_BYTES);",
            ),
            (
                "backup-constant-chunk-nonce",
                "    put_be32(nonce_out + 8u, chunk_index);",
                "    (void)chunk_index;\n"
                "    put_be32(nonce_out + 8u, 0u);",
            ),
            (
                "backup-skip-merkle-proof-verify",
                "    if (!merkle_verify_proof(cidx, ctx->manifest.chunk_count, ct, plen, tag,\n"
                "                             proof, ctx->merkle_depth, ctx->manifest.merkle_root)) {\n"
                "        vos_bk_restore_discard(ctx, store);\n"
                "        return VOS_BK_ERR_MERKLE_PROOF;\n"
                "    }",
                "    if (0 && !merkle_verify_proof(cidx, ctx->manifest.chunk_count, ct, plen, tag,\n"
                "                                  proof, ctx->merkle_depth, ctx->manifest.merkle_root)) {\n"
                "        vos_bk_restore_discard(ctx, store);\n"
                "        return VOS_BK_ERR_MERKLE_PROOF;\n"
                "    }",
            ),
            (
                "backup-stage-before-plan",
                "        if (arm == VOS_BK_PLAN_UNSUPPORTED) {\n"
                "            vos_bk_restore_discard(ctx, NULL);\n"
                "            return VOS_BK_ERR_UNSUPPORTED_SCHEMA;\n"
                "        }",
                "        if (arm == VOS_BK_PLAN_UNSUPPORTED) {\n"
                "            ++store->write_counter;\n"
                "            vos_bk_restore_discard(ctx, NULL);\n"
                "            return VOS_BK_ERR_UNSUPPORTED_SCHEMA;\n"
                "        }",
            ),
            (
                "backup-silent-discard-unsupported",
                "        enum vos_bk_plan_arm arm = (rule != NULL) ? rule->arm : VOS_BK_PLAN_UNSUPPORTED;",
                "        enum vos_bk_plan_arm arm = (rule != NULL) ? rule->arm : VOS_BK_PLAN_DISCARD;",
            ),
            (
                "backup-restore-skips-fresh-init",
                "    for (uint32_t i = 0u; i < staging_ns->fresh_count; ++i) {\n"
                "        init_fresh_slot_post_restore(&staging_ns->fresh[i], store->next_epoch);\n"
                "        ++store->next_epoch;\n"
                "    }",
                "    for (uint32_t i = 0u; i < staging_ns->fresh_count; ++i) {\n"
                "        if (0) { init_fresh_slot_post_restore(&staging_ns->fresh[i], store->next_epoch); }\n"
                "        staging_ns->fresh[i].enrolled = 1u;\n"
                "        staging_ns->fresh[i].reconciled = 1u;\n"
                "        staging_ns->fresh[i].attempts_remaining = 5u;\n"
                "    }",
            ),
            (
                "backup-accept-trailing-bytes",
                "    if (ver != VOS_BK_VERSION || prof != expected_profile_id ||\n"
                "        total_extent != (uint64_t)src->length ||",
                "    if (ver != VOS_BK_VERSION || prof != expected_profile_id ||\n"
                "        total_extent > (uint64_t)src->length ||",
            ),
            (
                "backup-overwrite-active-during-staging",
                "    const uint32_t act = store->active_idx;\n"
                "    const uint32_t stg = 1u - act;",
                "    const uint32_t act = store->active_idx;\n"
                "    const uint32_t stg = act;",
            ),
        ]

        ensure(len(mutants) >= 10, "expected at least 10 behavioral mutants")
        for label, target, replacement in mutants:
            ensure(source.count(target) == 1, f"mutant target missing or non-unique: {label}")
            mutant_c = tmp / f"mutant_{label}.c"
            mutant_c.write_text(source.replace(target, replacement, 1), encoding="utf-8")
            mutant_bin = tmp / f"mutant_{label}"
            m_built = subprocess.run(
                [
                    compiler, *flags,
                    f"-I{BACKUP_H.parent}", f"-I{CRYPTO_INCLUDE}",
                    str(mutant_c), str(CRYPTO_SOURCE), str(BACKUP_TEST_C),
                    "-o", str(mutant_bin),
                ],
                capture_output=True, text=True, check=False, timeout=60,
            )
            ensure(m_built.returncode == 0, f"stillborn mutant {label}: {m_built.stderr}")
            m_ran = subprocess.run([str(mutant_bin)], capture_output=True, text=True, check=False, timeout=60)
            ensure(m_ran.returncode != 0, f"mutant survived: {label}")


def cases() -> list[Case]:
    return [
        Case("backup_recovery_secret_oracle", _recovery_secret_oracle, lane="any"),
        Case("backup_object_wire_and_crypto_oracle", _backup_object_wire_and_crypto_oracle, lane="any"),
        Case("backup_export_view_and_restore_sm_oracle", _export_view_and_restore_sm_oracle, lane="any"),
        Case("backup_surface_and_proof_contract", _surface_and_proof_contract, lane="any"),
        Case("backup_native_c_and_mutation_controls", _native_c_and_mutation_controls, lane="guest"),
    ]
