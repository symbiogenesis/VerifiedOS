# SPDX-License-Identifier: Apache-2.0
"""Independent executable ML-DSA-87 comparison with installed OpenSSL 3.5.5.

All seeds, messages, contexts and hedging bytes here are public authored tests,
not standard KATs. Only DER framing and CLI glue are authored here; OpenSSL and
the Gallina executable independently compute every cryptographic operation.
No OpenSSL source or binary is incorporated into the tracked tree.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import time
import sys
import urllib.request

sys.dont_write_bytecode = True
import mldsa_vectors as campaign

OPENSSL_COMMIT = "67b5686b4419b4cb8caa502711c41815f5279751"
LICENSE_SHA = "7d5450cb2d142651b8afa315b5f238efc805dad827d91ba367d8516bc9d49e7a"
LICENSE_URL = f"https://raw.githubusercontent.com/openssl/openssl/{OPENSSL_COMMIT}/LICENSE.txt"


def der(tag: int, data: bytes) -> bytes:
    size = len(data)
    length = size.to_bytes((size.bit_length() + 7) // 8, "big")
    return bytes([tag]) + (bytes([size]) if size < 128 else bytes([128 + len(length)]) + length) + data


ALGORITHM = der(0x30, der(6, bytes.fromhex("608648016503040313")))


def public_der(pk: bytes) -> bytes:
    if len(pk) != 2592:
        raise ValueError("ML-DSA-87 public key length")
    return der(0x30, ALGORITHM + der(3, b"\0" + pk))


def private_der(sk: bytes) -> bytes:
    if len(sk) != 4896:
        raise ValueError("ML-DSA-87 secret key length")
    return der(0x30, der(2, b"\0") + ALGORITHM + der(4, der(4, sk)))


def openssl_verify(work: Path, pk: bytes, message: bytes, context: bytes, sig: bytes) -> bool:
    (work / "check-pk.der").write_bytes(public_der(pk))
    (work / "check-message.bin").write_bytes(message)
    (work / "check-signature.bin").write_bytes(sig)
    command = ["openssl", "pkeyutl", "-verify", "-provider", "default", "-pubin",
               "-keyform", "DER", "-inkey", "check-pk.der", "-in", "check-message.bin",
               "-sigfile", "check-signature.bin", "-pkeyopt", "hexcontext-string:" + context.hex()]
    result = campaign.run(command, work)
    if result.returncode == 0 and result.stdout.strip() == "Signature Verified Successfully":
        return True
    if result.returncode == 1 and result.stdout.strip() == "Signature Verification Failure":
        return False
    raise RuntimeError(f"OpenSSL command failure, not a verification refusal: {result}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    baseline, work = args.baseline.resolve(), args.work.resolve()
    if work.parent != baseline.parent or not str(work).startswith("/root/build/lane-"):
        parser.error("use sibling baseline and oracle directories in the assigned native lane")
    work.mkdir(parents=True, exist_ok=True)
    receipt = json.loads((baseline / "receipt.json").read_text())
    if not receipt["passed"]:
        raise ValueError("passing baseline required")
    for module in ("PqArith", "Keccak", "MlDsa"):
        source = campaign.ROOT / "proofs" / (module + ".v")
        if receipt["bindings"][str(source.relative_to(campaign.ROOT))] != campaign.sha(source.read_bytes()):
            raise ValueError("baseline source drift")
    if receipt["bindings"]["dsa.exe"] != campaign.sha((baseline / "dsa.exe").read_bytes()):
        raise ValueError("baseline executable drift")
    version = campaign.checked(["openssl", "version", "-a"], work, "version.log")
    if not version.startswith("OpenSSL 3.5.5 "):
        raise ValueError("this campaign qualified OpenSSL 3.5.5; requalify another version's license/API")
    license_path = work / "LICENSE.txt"
    if not license_path.exists():
        license_path.write_bytes(urllib.request.urlopen(LICENSE_URL, timeout=60).read())
    if campaign.sha(license_path.read_bytes()) != LICENSE_SHA:
        raise ValueError("OpenSSL selected revision license mismatch")
    executable = Path(shutil.which("openssl") or "")
    linkage = campaign.checked(["ldd", str(executable)], work, "linkage.log")
    binaries = {str(executable): campaign.sha(executable.read_bytes())}
    for match in re.finditer(r"(?:libcrypto|libssl)\.so\.3 => (\S+)", linkage):
        library = Path(match.group(1)); binaries[str(library)] = campaign.sha(library.read_bytes())
    if len(binaries) != 3:
        raise ValueError("could not bind OpenSSL and both libraries")
    copyright_path = Path("/usr/share/doc/openssl/copyright")
    copyright_sha = campaign.sha(copyright_path.read_bytes())
    (work / "package-copyright.txt").write_bytes(copyright_path.read_bytes())
    package = campaign.checked(["dpkg-query", "-W", "openssl", "libssl3t64"], work, "package.log")
    results = []
    started = time.time()
    for index in range(3):
        stage = work / f"case-{index}"; stage.mkdir(exist_ok=True)
        seed = bytes((j + 67 * index) % 256 for j in range(32))
        rnd = bytes((255 - j - 19 * index) % 256 for j in range(32))
        context = b"\x00VerifiedOS oracle\xff" + bytes([index])
        message = b"Independent ML-DSA-87 comparison\x00" + bytes(range(256)) + bytes([index])
        pair = campaign.invoke(baseline, "keygen", [seed.hex()])
        if len(pair) != 2:
            raise ValueError("Gallina key generation did not return a pair")
        pk, sk = map(bytes.fromhex, pair)
        campaign.checked(["openssl", "genpkey", "-provider", "default", "-algorithm", "ML-DSA-87",
                          "-pkeyopt", "hexseed:" + seed.hex(), "-out", "key.pem"], stage, "keygen.log")
        campaign.checked(["openssl", "pkey", "-in", "key.pem", "-pubout", "-outform", "DER",
                          "-out", "public.der"], stage, "public-export.log")
        campaign.checked(["openssl", "pkey", "-in", "key.pem", "-outform", "DER", "-out", "private.der",
                          "-provparam", "ml-dsa.output_formats=priv-only"], stage, "private-export.log")
        comparisons = {"public-key-bytes": (stage / "public.der").read_bytes() == public_der(pk),
                       "secret-key-bytes": (stage / "private.der").read_bytes() == private_der(sk)}
        ours = campaign.invoke(baseline, "sign", [sk.hex(), context.hex(), message.hex(), rnd.hex()])
        if len(ours) != 1 or len(ours[0]) != 9254:
            raise ValueError("Gallina signer did not return a signature")
        own_sig = bytes.fromhex(ours[0])
        (stage / "message.bin").write_bytes(message)
        campaign.checked(["openssl", "pkeyutl", "-sign", "-provider", "default", "-inkey", "key.pem",
                          "-in", "message.bin", "-out", "openssl.sig", "-pkeyopt",
                          "hexcontext-string:" + context.hex(), "-pkeyopt", "hextest-entropy:" + rnd.hex()],
                         stage, "sign.log")
        other_sig = (stage / "openssl.sig").read_bytes()
        comparisons["signature-bytes"] = own_sig == other_sig
        comparisons["openssl-verifies-gallina"] = openssl_verify(stage, pk, message, context, own_sig)
        comparisons["gallina-verifies-openssl"] = campaign.invoke(baseline, "verify",
            [pk.hex(), context.hex(), message.hex(), other_sig.hex()]) == ["true"]
        bad_z = bytearray(own_sig)
        packed = int.from_bytes(bad_z[64:67], "little")
        bad_z[64:67] = ((packed & ~((1 << 20) - 1)) | 120).to_bytes(3, "little")
        bad_hint = bytearray(own_sig); bad_hint[-1] = 76
        corruptions = {
            "changed-message": (pk, message + b"\0", context, own_sig),
            "changed-context": (pk, message, context + b"\0", own_sig),
            "changed-challenge": (pk, message, context, bytes([own_sig[0] ^ 1]) + own_sig[1:]),
            "strict-response-boundary": (pk, message, context, bytes(bad_z)),
            "hint-endpoint-overflow": (pk, message, context, bytes(bad_hint)),
            "short-signature": (pk, message, context, own_sig[:-1]),
            "changed-public-key": (bytes([pk[0] ^ 1]) + pk[1:], message, context, own_sig),
        }
        for name, (test_pk, test_message, test_context, test_sig) in corruptions.items():
            other = openssl_verify(stage, test_pk, test_message, test_context, test_sig)
            own = campaign.invoke(baseline, "verify", [test_pk.hex(), test_context.hex(),
                                                       test_message.hex(), test_sig.hex()])
            comparisons[name] = not other and own == ["false"]
        results.append({"case": index, "seed": seed.hex(), "hedging_bytes": rnd.hex(),
                        "message_sha256": campaign.sha(message), "context": context.hex(),
                        "public_key_sha256": campaign.sha(pk), "secret_key_sha256": campaign.sha(sk),
                        "gallina_signature_sha256": campaign.sha(own_sig),
                        "openssl_signature_sha256": campaign.sha(other_sig), "comparisons": comparisons})
        print(index, comparisons, flush=True)
    report = {"oracle": "OpenSSL 3.5.5 default provider", "upstream_commit": OPENSSL_COMMIT,
              "license_url": LICENSE_URL, "license_sha256": LICENSE_SHA,
              "package_copyright_sha256": copyright_sha, "package": package, "version": version,
              "binaries": binaries, "gallina_bindings": receipt["bindings"],
              "harness_sha256": campaign.sha(Path(__file__).read_bytes()), "cases": results,
              "started_unix": started, "finished_unix": time.time(),
              "passed": all(all(case["comparisons"].values()) for case in results),
              "scope": "authored public inputs; exact key/signature bytes, bidirectional verification and paired corruption refusals; no imported crypto implementation, no production signing or standard-KAT label"}
    (work / "receipt.json").write_text(json.dumps(report, indent=2) + "\n")
    print("INDEPENDENT ORACLE", report["passed"], flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())