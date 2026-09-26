# SPDX-License-Identifier: Apache-2.0
"""Disposable SLH-DSA signing inputs for the measured-boot executable join.

Private keys and generated signatures stay in the caller's native output lane.
OpenSSL produces inputs; firmware/crypto/slh256s.c makes the release decision.
This helper supplies neither a production root nor target qualification.
"""

import hashlib
import shutil
import subprocess
from pathlib import Path


class SlhSigner:
    """One disposable key per lifecycle root and a cache per signed prefix."""

    def __init__(self, work: Path, states: tuple[str, ...], *, public_bytes: int,
                 signature_bytes: int) -> None:
        self.work = work
        self.public_bytes = public_bytes
        self.signature_bytes = signature_bytes
        work.mkdir(parents=True, exist_ok=True)
        executable = shutil.which("openssl")
        if executable is None:
            raise ValueError("SLH boot signing needs OpenSSL with SLH-DSA-SHAKE-256s")
        self.executable = Path(executable)
        self.version = self._run("version", "-a").strip()
        self.executable_sha256 = hashlib.sha256(self.executable.read_bytes()).hexdigest()
        self.roots: dict[str, bytes] = {}
        self.keys: dict[bytes, Path] = {}
        self.signed: dict[tuple[bytes, bytes], bytes] = {}
        for state in states:
            if state not in ("test", "development", "production", "rma"):
                raise ValueError(f"unsupported lifecycle root {state}")
            key = work / f"{state}-key.pem"
            public = work / f"{state}-public.der"
            self._run("genpkey", "-algorithm", "SLH-DSA-SHAKE-256s", "-out", str(key))
            key.chmod(0o600)
            self._run("pkey", "-in", str(key), "-pubout", "-outform", "DER", "-out", str(public))
            encoded = public.read_bytes()
            # AlgorithmIdentifier id-slh-dsa-shake-256s and 64-byte BIT STRING.
            prefix = bytes.fromhex("3050300b060960864801650304031e034100")
            if len(encoded) != len(prefix) + self.public_bytes or not encoded.startswith(prefix):
                raise ValueError("unexpected SLH-DSA-SHAKE-256s public-key encoding")
            pk = encoded[len(prefix):]
            self.roots[state] = pk
            self.keys[pk] = key

    def _run(self, *args: str) -> str:
        result = subprocess.run([str(self.executable), *args], cwd=self.work,
                                capture_output=True, text=True, timeout=120, check=False)
        if result.returncode:
            raise ValueError(f"OpenSSL {args[0]} failed ({result.returncode}): {result.stderr[-1000:]}")
        return result.stdout

    def sign(self, public: bytes, message: bytes) -> bytes:
        pair = (public, message)
        if pair in self.signed:
            return self.signed[pair]
        if public not in self.keys:
            raise ValueError("the signing campaign has no private key for the selected root")
        identity = hashlib.sha256(public + message).hexdigest()
        prefix = self.work / f"{identity}.message"
        signature = self.work / f"{identity}.signature"
        prefix.write_bytes(message)
        self._run("pkeyutl", "-sign", "-inkey", str(self.keys[public]), "-in", str(prefix),
                  "-out", str(signature), "-pkeyopt", "message-encoding:0")
        result = signature.read_bytes()
        if len(result) != self.signature_bytes:
            raise ValueError("unexpected SLH-DSA-SHAKE-256s signature size")
        self.signed[pair] = result
        return result

    def identity(self) -> dict[str, object]:
        if hashlib.sha256(self.executable.read_bytes()).hexdigest() != self.executable_sha256:
            raise ValueError("the OpenSSL executable changed during boot signing")
        return {"scheme": "SLH-DSA-SHAKE-256s", "interface": "internal message",
                "openssl_version": self.version, "openssl_executable": str(self.executable),
                "openssl_sha256": self.executable_sha256,
                "roots": {state: pk.hex() for state, pk in self.roots.items()},
                "signed_prefixes": len(self.signed)}
