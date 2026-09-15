#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independent OpenSSL ML-KEM-1024 execution versus the extracted reference.

The seed and ikme controls are used solely for reproducible public test inputs.
No OpenSSL algorithm source is copied. Generated DER wrappers, keys and outputs
remain in the assigned native lane. Requires the preceding vector campaign's
matching extracted executable and receipt in --reference.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import selectors
import shutil
import subprocess
import time


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def der(tag: int, body: bytes) -> bytes:
    length = len(body)
    size = length.to_bytes(max(1, (length.bit_length() + 7) // 8), "big")
    return bytes([tag]) + (bytes([length]) if length < 128 else bytes([128 + len(size)]) + size) + body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["repo", "build", "reference"]:
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--cases", type=int, default=25)
    args = parser.parse_args()
    if not str(args.build.resolve()).startswith("/root/build/lane-") or args.cases < 1:
        raise ValueError("positive case count and assigned native lane required")
    args.build.mkdir(parents=True, exist_ok=True)
    previous = json.loads((args.reference / "mlkem-vector-receipt.json").read_text())
    for name, identity in previous["inputs"].items():
        if sha(args.repo / "proofs" / (name + ".v")) != identity["source_sha256"]:
            raise ValueError("source differs from extracted campaign: " + name)
    executable = args.reference / "mlkem_vectors"
    if sha(executable) != previous["executable_sha256"]:
        raise ValueError("executable differs from vector receipt")
    openssl = Path(shutil.which("openssl") or "").resolve()
    version = subprocess.check_output([str(openssl), "version", "-a"], text=True)
    if "OpenSSL 3.5.5 " not in version:
        raise ValueError("qualify this OpenSSL version before changing the campaign")
    notice = Path("/usr/share/doc/openssl/copyright")
    shutil.copyfile(notice, args.build / "openssl-package-copyright.txt")
    rows, commands = [], []
    algorithm = der(0x30, der(0x06, bytes.fromhex("608648016503040403")))

    def public_key(ek: bytes) -> bytes:
        return der(0x30, algorithm + der(0x03, b"\0" + ek))

    def private_key(value: bytes, seed: bool = False) -> bytes:
        return der(0x30, der(0x02, b"\0") + algorithm + der(0x04, der(0x80 if seed else 0x04, value)))

    def openssl_run(directory: Path, options: list[str], refusal: bool = False) -> None:
        command = [str(openssl)] + options
        done = subprocess.run(command, cwd=directory, capture_output=True, timeout=30, check=False)
        commands.append({"cwd": str(directory), "command": command, "exit": done.returncode})
        with (directory / "openssl.stderr").open("ab") as stream:
            stream.write(done.stderr)
        if (done.returncode != 0) != refusal:
            raise RuntimeError(f"unexpected OpenSSL exit {done.returncode}: {options[0]}")

    def record(label: str, a: bytes, b: bytes) -> None:
        row = {"label": label, "pass": a == b,
               "reference_sha256": hashlib.sha256(a).hexdigest(),
               "oracle_sha256": hashlib.sha256(b).hexdigest()}
        rows.append(row)
        if not row["pass"]:
            raise AssertionError(label)

    start = time.monotonic()
    process = subprocess.Popen([str(executable)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=(args.build / "reference.stderr").open("w"), text=True, bufsize=1)
    assert process.stdin is not None and process.stdout is not None
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)

    def reference(operation: str, a: bytes, b: bytes) -> str:
        assert process.stdin is not None and process.stdout is not None
        process.stdin.write(f"{operation} {a.hex() or '-'} {b.hex() or '-'}\n")
        process.stdin.flush()
        if not selector.select(timeout=120):
            raise TimeoutError(operation)
        answer = process.stdout.readline().strip()
        if not answer:
            raise RuntimeError("reference driver closed")
        return answer

    failure = ""
    try:
        for index in range(args.cases):
            directory = args.build / f"case-{index:03d}"
            directory.mkdir(exist_ok=True)
            def seed(label: str) -> bytes:
                return hashlib.sha256(f"VerifiedOS independent ML-KEM test {index} {label}".encode()).digest()
            d, z, m = seed("d"), seed("z"), seed("m")
            ek, dk = [bytes.fromhex(s) for s in reference("keygen", d, z).split(":")]
            (directory / "public.der").write_bytes(public_key(ek))
            (directory / "private.der").write_bytes(private_key(dk))
            (directory / "seed.der").write_bytes(private_key(d + z, True))
            openssl_run(directory, ["pkey", "-in", "seed.der", "-inform", "DER", "-pubout", "-outform", "DER", "-out", "oracle-public.der"])
            record(f"{index}-keygen-public", public_key(ek), (directory / "oracle-public.der").read_bytes())
            openssl_run(directory, ["pkey", "-provparam", "ml-kem.retain_seed=no", "-in", "seed.der", "-inform", "DER", "-outform", "DER", "-out", "oracle-private.der"])
            record(f"{index}-keygen-private", private_key(dk), (directory / "oracle-private.der").read_bytes())
            key, ciphertext = [bytes.fromhex(s) for s in reference("encaps", ek, m).split(":")]
            (directory / "ciphertext.bin").write_bytes(ciphertext)
            openssl_run(directory, ["pkeyutl", "-encap", "-pubin", "-inkey", "public.der", "-keyform", "DER", "-pkeyopt", "hexikme:" + m.hex(), "-out", "oracle-ciphertext.bin", "-secret", "oracle-secret.bin"])
            record(f"{index}-encaps-ciphertext", ciphertext, (directory / "oracle-ciphertext.bin").read_bytes())
            record(f"{index}-encaps-key", key, (directory / "oracle-secret.bin").read_bytes())
            openssl_run(directory, ["pkeyutl", "-decap", "-inkey", "private.der", "-keyform", "DER", "-in", "ciphertext.bin", "-secret", "decaps-secret.bin"])
            record(f"{index}-decaps", bytes.fromhex(reference("decaps", dk, ciphertext)), (directory / "decaps-secret.bin").read_bytes())
            openssl_run(directory, ["pkeyutl", "-encap", "-pubin", "-inkey", "public.der", "-keyform", "DER", "-out", "random-ciphertext.bin", "-secret", "random-secret.bin"])
            random_ct = (directory / "random-ciphertext.bin").read_bytes()
            record(f"{index}-openssl-random-encaps", bytes.fromhex(reference("decaps", dk, random_ct)), (directory / "random-secret.bin").read_bytes())
            tampered = ciphertext[:index] + bytes([ciphertext[index] ^ 1]) + ciphertext[index + 1:]
            (directory / "tampered.bin").write_bytes(tampered)
            openssl_run(directory, ["pkeyutl", "-decap", "-inkey", "private.der", "-keyform", "DER", "-in", "tampered.bin", "-secret", "tampered-secret.bin"])
            record(f"{index}-implicit-rejection", bytes.fromhex(reference("decaps", dk, tampered)), (directory / "tampered-secret.bin").read_bytes())
            for label, bad in [("short", ciphertext[:-1]), ("long", ciphertext + b"\0")]:
                (directory / "malformed.bin").write_bytes(bad)
                openssl_run(directory, ["pkeyutl", "-decap", "-inkey", "private.der", "-keyform", "DER", "-in", "malformed.bin", "-secret", "malformed-secret.bin"], True)
                record(f"{index}-{label}-ciphertext-refused", reference("decaps", dk, bad).encode(), b"REJECT")
            print("independent case", index, "PASS", flush=True)
    except Exception as error:
        failure = str(error)
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=10)
        selector.close()
    receipt = {"pass": not failure and process.returncode == 0, "failure": failure, "checks": rows,
               "commands": commands, "reference_exit": process.returncode, "inputs": previous["inputs"],
               "reference_executable_sha256": sha(executable), "openssl_version": version,
               "openssl_binary_sha256": sha(openssl), "openssl_package_notice_sha256": sha(notice),
               "libcrypto_sha256": sha(Path("/usr/lib/aarch64-linux-gnu/libcrypto.so.3")),
               "upstream_revision": "67b5686b4419b4cb8caa502711c41815f5279751", "upstream_license": "Apache-2.0",
               "cases": args.cases, "elapsed_seconds": time.monotonic() - start,
               "scope": "Independent installed OpenSSL execution, default provider, generated test seeds; no proof of native oracle, extraction or compiler"}
    (args.build / "mlkem-openssl-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print("independent campaign", "PASS" if receipt["pass"] else "FAIL", len(rows), "checks", failure, flush=True)
    return 0 if receipt["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
