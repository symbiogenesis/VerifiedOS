# SPDX-License-Identifier: Apache-2.0
"""Executable tests for `crypto-core` (`storage/src/crypto_core.c`) and the
`M5.3d` early executable publication checkpoint (`storage/src/storage_publish.c`),
including the `Q44` authenticated resident-read verifier join.
"""

from __future__ import annotations

import hashlib
import hmac
import shutil
import subprocess
import tempfile
from pathlib import Path

from tests.harness import Case, ensure

INDEPENDENT_CASES = True

ROOT = Path(__file__).resolve().parents[2]
CRYPTO_HEADER = ROOT / "storage" / "include" / "vos_crypto_core.h"
PUBLISH_HEADER = ROOT / "storage" / "include" / "vos_storage_publish.h"
CRYPTO_SOURCE = ROOT / "storage" / "src" / "crypto_core.c"
PUBLISH_SOURCE = ROOT / "storage" / "src" / "storage_publish.c"
NODE_SOURCE = ROOT / "storage" / "src" / "node_image.c"
TREE_IMAGE_SOURCE = ROOT / "storage" / "src" / "tree_image.c"
TREE_UPDATE_SOURCE = ROOT / "storage" / "src" / "tree_update.c"
RESIDENT_SOURCE = ROOT / "storage" / "src" / "resident_reads.c"
HARNESS = ROOT / "storage" / "host" / "storage_publish.c"


def _compiler() -> str:
    for candidate in ("cc", "gcc", "clang"):
        found = shutil.which(candidate)
        if found is not None:
            return found
    raise AssertionError("no C compiler available in guest test lane")


def _derive_purpose_key(master_key: bytes, domain_id: int,
                        key_epoch: int, label: bytes) -> bytes:
    info = label + domain_id.to_bytes(8, "little") + key_epoch.to_bytes(8, "little")
    return hmac.new(master_key, info, hashlib.sha256).digest()


def _keyed_digest(master_key: bytes, domain_id: int,
                  key_epoch: int, plaintext: bytes) -> bytes:
    dedup_key = _derive_purpose_key(master_key, domain_id, key_epoch, b"VOSDDUP1")
    header = (
        b"VOSKDIG1"
        + domain_id.to_bytes(8, "little")
        + len(plaintext).to_bytes(8, "little")
    )
    return hmac.new(dedup_key, header + plaintext, hashlib.sha256).digest()


def _check_python_crypto_and_kdf_oracle() -> None:
    """Verify the Python reference vectors embedded in `storage/host/storage_publish.c`."""
    ensure(
        hashlib.sha256(b"abc").digest()
        == bytes.fromhex(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        ),
        "FIPS 180-4 'abc' SHA-256 vector",
    )
    ensure(
        hashlib.sha256(
            b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"
        ).digest()
        == bytes.fromhex(
            "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"
        ),
        "FIPS 180-4 two-block SHA-256 vector",
    )
    ensure(
        hmac.new(bytes([0x0B] * 20), b"Hi There", hashlib.sha256).digest()
        == bytes.fromhex(
            "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7"
        ),
        "RFC 4231 Case 1 HMAC-SHA-256 vector",
    )
    master = bytes(range(0x40, 0x60))
    payload = b"shared-payload-across-instances\x00"
    sys_d1 = _keyed_digest(master, 0x1001, 1, payload)
    sys_d2 = _keyed_digest(master, 0x1001, 1, payload)
    usr_d = _keyed_digest(master, 0x2002, 1, payload)
    ensure(sys_d1 == sys_d2, "domain-separated keyed digest is deterministic within a domain")
    ensure(sys_d1 != usr_d, "domain-separated keyed digest differs across domains")

    for path in (
        CRYPTO_HEADER,
        PUBLISH_HEADER,
        CRYPTO_SOURCE,
        PUBLISH_SOURCE,
        HARNESS,
    ):
        ensure(path.is_file(), f"missing storage publish artifact: {path}")


def _compile_and_run_c_harness() -> None:
    cc = _compiler()
    sources = [
        NODE_SOURCE,
        TREE_IMAGE_SOURCE,
        TREE_UPDATE_SOURCE,
        RESIDENT_SOURCE,
        CRYPTO_SOURCE,
        PUBLISH_SOURCE,
        HARNESS,
    ]
    with tempfile.TemporaryDirectory() as tmp:
        binary = Path(tmp) / "storage_publish_test"
        cmd = [
            cc,
            "-std=c11",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            f"-I{CRYPTO_HEADER.parent}",
            *[str(src) for src in sources],
            "-o",
            str(binary),
        ]
        built = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=60)
        ensure(built.returncode == 0, f"failed to compile storage_publish C harness: {built.stderr}")
        ran = subprocess.run([str(binary)], check=False, capture_output=True, text=True, timeout=60)
        ensure(
            ran.returncode == 0,
            f"storage_publish C harness failed: {ran.stderr or ran.stdout}",
        )
        ensure("storage_publish: ok" in ran.stdout, f"unexpected output: {ran.stdout!r}")

        crypto_src = CRYPTO_SOURCE.read_text(encoding="utf-8")
        publish_src = PUBLISH_SOURCE.read_text(encoding="utf-8")

        mutants: list[tuple[str, str, str, str]] = [
            (
                "crypto",
                "bypass AES-GCM tag check",
                "if (!equal_bytes_ct(expected, tag, VOS_CRYPTO_TAG_BYTES)) {",
                "if (0 && !equal_bytes_ct(expected, tag, VOS_CRYPTO_TAG_BYTES)) {",
            ),
            (
                "crypto",
                "collapse domain separation in purpose KDF and keyed digest",
                "put_le64(info + 8u, domain_id);",
                "put_le64(info + 8u, 0u); (void)domain_id;",
            ),
            (
                "publish",
                "omit durable nonce reservation persistence in Reserve",
                "medium->nonce_record = next_nonce;",
                "(void)next_nonce;",
            ),
            (
                "publish",
                "accept replayed nonce record below committed generation in Reopen",
                "if (medium->nonce_record.reserved_generation < cp->generation) {",
                "if (0 && medium->nonce_record.reserved_generation < cp->generation) {",
            ),
            (
                "publish",
                "skip committed redo journal prefix replay in Reopen",
                "if (j_gen == cp->generation) {",
                "if (0 && j_gen == cp->generation) {",
            ),
            (
                "publish",
                "present unsealed Fresh epoch write as committed on Reopen",
                "if (medium->checkpoint.commit_mode == VOS_STORAGE_COMMIT_FRESH &&\n"
                "        medium->checkpoint.sealed_epoch == 0u) {",
                "if (0 && medium->checkpoint.commit_mode == VOS_STORAGE_COMMIT_FRESH) {",
            ),
            (
                "publish",
                "skip authenticated B+ tree lookup in vos_storage_verify_resident",
                "if (vos_storage_lookup(store, identity->domain, identity->object,\n"
                "                           &committed_value) != VOS_TREE_FOUND) {",
                "committed_value = resident_tree_value(identity->root, identity->version);\n"
                "    if (0) {",
            ),
        ]

        for idx, (kind, label, target, replacement) in enumerate(mutants):
            base_text = crypto_src if kind == "crypto" else publish_src
            ensure(target in base_text, f"mutant target missing for {label}")
            mutated_text = base_text.replace(target, replacement, 1)
            mut_file = Path(tmp) / f"mutant_{idx}_{kind}.c"
            mut_file.write_text(mutated_text, encoding="utf-8")
            mut_bin = Path(tmp) / f"mutant_{idx}"
            mut_sources = [
                NODE_SOURCE,
                TREE_IMAGE_SOURCE,
                TREE_UPDATE_SOURCE,
                RESIDENT_SOURCE,
                mut_file if kind == "crypto" else CRYPTO_SOURCE,
                mut_file if kind == "publish" else PUBLISH_SOURCE,
                HARNESS,
            ]
            m_built = subprocess.run(
                [
                    cc,
                    "-std=c11",
                    "-O2",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    f"-I{CRYPTO_HEADER.parent}",
                    *[str(src) for src in mut_sources],
                    "-o",
                    str(mut_bin),
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )
            ensure(m_built.returncode == 0, f"mutant {label} did not compile: {m_built.stderr}")
            m_ran = subprocess.run([str(mut_bin)], check=False, capture_output=True, text=True, timeout=60)
            ensure(m_ran.returncode != 0, f"mutant survived: {label}")


def cases() -> list[Case]:
    return [
        Case("storage_publish_python_oracle", _check_python_crypto_and_kdf_oracle, lane="any"),
        Case("storage_publish_c_harness_and_mutants", _compile_and_run_c_harness, lane="guest"),
    ]
