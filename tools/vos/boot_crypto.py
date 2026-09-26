# SPDX-License-Identifier: Apache-2.0
"""Byte-oriented boot signature comparisons, separate from target acceptance."""

import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, replace
from pathlib import Path
from types import ModuleType
from typing import Any

from vos import boot_handoff, receipts

REVISION = "975de31eb83d87039ec88934fdc47d8c312b892d"
BASE = f"https://raw.githubusercontent.com/usnistgov/ACVP-Server/{REVISION}/"
SOURCES: dict[str, tuple[str, str]] = {
    "slh": ("SLH-DSA-sigVer-FIPS205", "a013fc2104f4ed4799d96d51141f65b965969b2cf10646626a021b6d456ce792"),
    "mldsa": ("ML-DSA-sigVer-FIPS204", "47cdd6314c7f746d02421ffcba89d4dbc7bb875ac49e07a029fdfc26fba55437"),
}
NOTICE_SHA = "d5a569884ee83bd1c4737042d0a2cc7d68c6950690f75a73ef14f505a9aa3555"
OPENSSL_REVISION = "67b5686b4419b4cb8caa502711c41815f5279751"
OPENSSL_LICENSE_SHA = "7d5450cb2d142651b8afa315b5f238efc805dad827d91ba367d8516bc9d49e7a"
SOURCE_FILES = ("firmware/crypto/keccak.c", "firmware/crypto/slh256s.c",
                "firmware/crypto/mldsa87.c", "firmware/crypto/check_signature.c",
                "firmware/rot/boot_verify.c", "firmware/include/vos_signature.h",
                "firmware/include/vos_keccak.h", "firmware/include/vos_boot.h")
EVIDENCE_FILES = (*SOURCE_FILES, "tools/vos/boot_crypto.py", "tools/vos/cli/boot_crypto.py",
    "tools/vos/boot_handoff.py", "tools/vos/receipts.py", "tools/vos/env.py",
    "proofs/campaigns/mldsa_vectors.py", "proofs/MlDsa.v", "proofs/PqArith.v", "proofs/Keccak.v",
    "firmware/crypto/fixtures.json")


@dataclass(frozen=True)
class Case:
    name: str
    mode: str
    pk: bytes
    message: bytes
    context: bytes
    signature: bytes
    expected: bool


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def run(command: list[str], work: Path, timeout: int = 240) -> str:
    result = subprocess.run(command, cwd=work, text=True, capture_output=True, timeout=timeout, check=False)
    if result.returncode:
        raise ValueError(f"command failed ({result.returncode}): {command[0]}: "
                         f"{result.stdout[-2000:]}{result.stderr[-2000:]}")
    return result.stdout.strip()


def fetch(url: str, dest: Path, expected: str) -> bytes:
    receipts.download(url, dest, expected)
    return dest.read_bytes()


def build(root: Path, work: Path) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    binary = work / "check-signature"
    command = ["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
               "-ffreestanding", "-fno-builtin", "-fsanitize=address,undefined",
               "-fno-sanitize-recover=all", "-I", str(root / "firmware/include")]
    command += [str(root / name) for name in SOURCE_FILES if name.endswith(".c")]
    command += ["-o", str(binary)]
    run(command, work)
    (work / "compile.json").write_text(json.dumps(command) + "\n", encoding="utf-8")
    return binary


def invoke(binary: Path, work: Path, case: Case) -> bool:
    paths: list[str] = []
    for name, data in (("pk", case.pk), ("message", case.message),
                       ("context", case.context), ("signature", case.signature)):
        path = work / (name + ".bin")
        path.write_bytes(data)
        paths.append(str(path))
    answer = run([str(binary), case.mode, *paths], work)
    if answer not in ("0", "1"):
        raise ValueError(f"invalid C verdict {answer!r}")
    return answer == "1"


def cases(document: dict[str, Any], scheme: str) -> tuple[list[Case], list[str]]:
    """Select only byte-aligned pure/internal/mu inputs; name every exclusion."""
    selected: list[Case] = []
    omitted: list[str] = []
    parameter = "SLH-DSA-SHAKE-256s" if scheme == "slh" else "ML-DSA-87"
    for group in document["testGroups"]:
        if group["parameterSet"] != parameter:
            continue
        for case in group["tests"]:
            name = f"{scheme}-tg{group['tgId']}-tc{case['tcId']}"
            if group.get("preHash") == "preHash":
                omitted.append(name + ": prehash outside pure API")
                continue
            mode = scheme + ("-mu" if group.get("externalMu") else "-internal"
                             if group["signatureInterface"] == "internal" else "")
            message = bytes.fromhex(case["mu"] if mode.endswith("-mu") else case["message"])
            if not mode.endswith("-mu") and case.get("messageLength", len(message)*8) != len(message)*8:
                omitted.append(name + ": partial-byte input outside byte API")
                continue
            selected.append(Case(name, mode, bytes.fromhex(case["pk"]), message,
                                 bytes.fromhex(case.get("context", "")),
                                 bytes.fromhex(case["signature"]), case["testPassed"]))
    if not selected or not any(c.expected for c in selected) or not any(not c.expected for c in selected):
        raise ValueError(f"{scheme}: comparison must include both accepted and refused signatures")
    return selected, omitted


def refusals(case: Case) -> list[Case]:
    def flip(data: bytes, at: int = 0) -> bytes:
        return data[:at] + bytes([data[at] ^ 1]) + data[at+1:]
    controls = [replace(case, name=case.name + "-" + name, expected=False, **changes)
                for name, changes in (
                    ("signature-flipped", {"signature": flip(case.signature)}),
                    ("wrong-root", {"pk": flip(case.pk, len(case.pk)-1)}),
                    ("message-flipped", {"message": flip(case.message) if case.message else b"x"}),
                    ("short-signature", {"signature": case.signature[:-1]}),
                    ("long-signature", {"signature": case.signature+b"\0"}),
                    ("short-root", {"pk": case.pk[:-1]}),
                    ("long-root", {"pk": case.pk+b"\0"}),
                )]
    if case.mode in ("slh", "mldsa"):
        controls += [replace(case, name=case.name+"-context-changed", context=case.context+b"x", expected=False),
                     replace(case, name=case.name+"-context-overlong", context=bytes(256), expected=False)]
    if not case.mode.endswith("-mu"):
        controls.append(replace(case, name=case.name+"-message-overlong", message=bytes(65537), expected=False))
    if case.mode.startswith("mldsa"):
        noncanonical = bytearray(case.signature)
        noncanonical[4544+75] = 76
        controls.append(replace(case, name=case.name+"-hint-end-overflow", signature=bytes(noncanonical), expected=False))
        for value, label in ((120, "positive-z-bound"), (1048456, "negative-z-bound")):
            encoded = bytearray(case.signature)
            encoded[64:66] = (value & 65535).to_bytes(2, "little")
            encoded[66] = (encoded[66] & 240) | (value >> 16)
            controls.append(replace(case, name=case.name+"-"+label, signature=bytes(encoded), expected=False))
    return controls


def offline_fixtures(root: Path) -> list[Case]:
    data = json.loads((root / "firmware/crypto/fixtures.json").read_text(encoding="utf-8"))
    rows = [Case("authored-offline-"+row["mode"], row["mode"], bytes.fromhex(row["pk"]),
                 bytes.fromhex(row["message"]), bytes.fromhex(row["context"]),
                 bytes.fromhex(row["signature"]), True) for row in data["cases"]]
    if len(rows) != 2 or {row.mode for row in rows} != {"slh", "mldsa"}:
        raise ValueError("offline fixtures require exactly one positive per scheme")
    return rows


def der(tag: int, data: bytes) -> bytes:
    length = len(data)
    size = length.to_bytes((length.bit_length()+7)//8, "big")
    return bytes([tag]) + (bytes([length]) if length < 128 else bytes([128+len(size)])+size) + data


def public_der(case: Case) -> bytes:
    # CSOR sigAlgs: id-ml-dsa-87 19, id-slh-dsa-shake-256s 30.
    oid = bytes.fromhex("6086480165030403") + bytes([30 if case.mode.startswith("slh") else 19])
    return der(0x30, der(0x30, der(6, oid)) + der(3, b"\0"+case.pk))


def openssl_verify(work: Path, case: Case) -> bool:
    (work / "public.der").write_bytes(public_der(case))
    (work / "message.bin").write_bytes(case.message)
    (work / "signature.bin").write_bytes(case.signature)
    command = ["openssl", "pkeyutl", "-verify", "-provider", "default", "-pubin", "-keyform", "DER",
               "-inkey", "public.der", "-in", "message.bin", "-sigfile", "signature.bin"]
    if case.mode.endswith("-internal"):
        command += ["-pkeyopt", "message-encoding:0"]
    elif case.mode.endswith("-mu"):
        command += ["-pkeyopt", "mu:1"]
    else:
        command += ["-pkeyopt", "hexcontext-string:"+case.context.hex()]
    result = subprocess.run(command, cwd=work, text=True, capture_output=True, timeout=60, check=False)
    if result.returncode == 0 and result.stdout.strip() == "Signature Verified Successfully":
        return True
    if result.returncode == 1 and result.stdout.strip() == "Signature Verification Failure":
        return False
    raise ValueError(f"OpenSSL operational failure, not refusal: {result.stderr[-1000:]}")


def openssl_identity(work: Path) -> dict[str, object]:
    version = run(["openssl", "version", "-a"], work)
    if not version.startswith("OpenSSL 3.5.5 "):
        raise ValueError("requalify another OpenSSL release before this campaign")
    url = f"https://raw.githubusercontent.com/openssl/openssl/{OPENSSL_REVISION}/LICENSE.txt"
    fetch(url, work / "OpenSSL-LICENSE.txt", OPENSSL_LICENSE_SHA)
    executable = Path(shutil.which("openssl") or "")
    linkage = run(["ldd", str(executable)], work)
    binaries = {str(executable): sha(executable.read_bytes())}
    for match in re.finditer(r"(?:libcrypto|libssl)\.so\.3 => (\S+)", linkage):
        path = Path(match.group(1))
        binaries[str(path)] = sha(path.read_bytes())
    if len(binaries) != 3:
        raise ValueError("OpenSSL binary/library identity incomplete")
    notice = Path("/usr/share/doc/openssl/copyright").read_bytes()
    (work / "OpenSSL-package-copyright.txt").write_bytes(notice)
    return {"version": version, "binaries": binaries, "license_sha256": OPENSSL_LICENSE_SHA,
            "package_notice_sha256": sha(notice)}


def gallina_build(root: Path, work: Path) -> tuple[ModuleType, dict[str, str]]:
    path = root / "proofs/campaigns/mldsa_vectors.py"
    spec = importlib.util.spec_from_file_location("boot_crypto_gallina", path)
    if spec is None or spec.loader is None:
        raise ValueError("missing ML-DSA extraction campaign")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    work.mkdir(exist_ok=True)
    raw = module.build(work)
    if not isinstance(raw, dict):
        raise TypeError("invalid extraction bindings")
    bindings: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise TypeError("invalid extraction binding identity")
        bindings[key] = value
    return module, bindings


def boot_cases(root: Path, binary: Path, work: Path) -> list[dict[str, object]]:
    """Sign an authored fixed header with OpenSSL, then bind the real callback."""
    lay = boot_handoff.layout(root)
    run(["openssl", "genpkey", "-algorithm", "SLH-DSA-SHAKE-256s", "-out", "boot-key.pem"], work)
    run(["openssl", "pkey", "-in", "boot-key.pem", "-pubout", "-outform", "DER", "-out", "boot-public.der"], work)
    raw = (work / "boot-public.der").read_bytes()
    pk = raw[-64:]
    probe = Case("boot", "slh-internal", pk, b"", b"", b"", True)
    if raw != public_der(probe):
        raise ValueError("unexpected OpenSSL SLH public-key encoding")
    payload = bytes(range(1, 65))
    prefix = bytearray(lay["BOOT_SIGNED_BYTES"])
    for field, value in (("MAGIC", lay["BOOT_MAGIC"]), ("STAGE", lay["BOOT_STAGE_MMODE_IMAGE"]),
                         ("SECURITY_VERSION", 2), ("PAYLOAD_OFFSET", lay["BOOT_HEADER_BYTES"]),
                         ("PAYLOAD_LENGTH", len(payload))):
        at = lay["BOOT_HDR_"+field]
        prefix[at:at+8] = value.to_bytes(8, "little")
    at = lay["BOOT_HDR_PAYLOAD_DIGEST"]
    prefix[at:at+32] = hashlib.shake_256(payload).digest(32)
    (work / "boot-prefix.bin").write_bytes(prefix)
    run(["openssl", "pkeyutl", "-sign", "-inkey", "boot-key.pem", "-in", "boot-prefix.bin",
         "-out", "boot-signature.bin", "-pkeyopt", "message-encoding:0"], work)
    signature = (work / "boot-signature.bin").read_bytes()
    if len(signature) != lay["BOOT_SIGNATURE_BYTES"]:
        raise ValueError("unexpected OpenSSL signature size")
    (work / "boot-public.bin").write_bytes(pk)
    good = bytes(prefix)+signature+payload
    bad_signature = bytearray(good)
    bad_signature[lay["BOOT_HDR_SIGNATURE"]] ^= 1
    overlength = bytearray(good)
    at = lay["BOOT_HDR_PAYLOAD_LENGTH"]
    overlength[at:at+8] = (lay["BRINGUP_MMODE_REGION_BYTES"]+1).to_bytes(8, "little")
    bad_digest = bytearray(good)
    bad_digest[-1] ^= 1
    records: list[dict[str, object]] = []
    for name, image, public, expected in (
        ("boot-valid", good, pk, "release"),
        ("boot-corrupt-signature", bytes(bad_signature), pk, "refuse-signature"),
        ("boot-wrong-root", good, pk[:-1]+bytes([pk[-1]^1]), "refuse-signature"),
        ("boot-overlength-field", bytes(overlength), pk, "refuse-length"),
        ("boot-corrupt-payload", bytes(bad_digest), pk, "refuse-digest"),
    ):
        (work / "boot-image.bin").write_bytes(image)
        (work / "boot-check-public.bin").write_bytes(public)
        answer = run([str(binary), "boot", str(work / "boot-check-public.bin"), str(work / "boot-image.bin")], work).split()
        if len(answer) != 6:
            raise ValueError("invalid boot driver answer")
        verdict, release, nonzero, changed, placed, measured = answer
        passed = verdict == expected
        if expected == "release":
            passed = passed and release == "1" and placed == "1" and changed != "0" and measured == "4"
        else:
            passed = passed and release == "0" and nonzero == "0" and changed == "0" and measured == "3"
        records.append({"name": name, "family": "real-boot-binding", "passed": passed, "answer": answer})
    # Public reproduction inputs. The ephemeral signing key stays in native output.
    receipts.write(work / "boot-fixture.json", {"mode": "slh-internal", "pk": pk.hex(),
        "message": bytes(prefix).hex(), "context": "", "signature": signature.hex(), "payload": payload.hex()})
    return records


def input_snapshot(root: Path) -> dict[str, str]:
    return receipts.snapshot(root, [root / name for name in EVIDENCE_FILES])


def require_unchanged(root: Path, before: dict[str, str]) -> None:
    if input_snapshot(root) != before:
        raise ValueError("crypto campaign inputs changed while running")


def campaign(root: Path, work: Path, gallina: bool = False, first: bool = False) -> dict[str, object]:
    started = time.monotonic()
    sources = input_snapshot(root)
    work.mkdir(parents=True, exist_ok=True)
    compiler_identity = receipts.executables("gcc")
    compiler_version = run(["gcc", "--version"], work)
    revision = run(["git", "-c", f"safe.directory={root}", "-C", str(root), "rev-parse", "HEAD"], work)
    binary = build(root, work)
    compiler = {"executables": compiler_identity, "version": compiler_version,
                "command": json.loads((work / "compile.json").read_text(encoding="utf-8"))}
    fetch(BASE+"README.md", work / "NIST-README.md", NOTICE_SHA)
    vectors: list[Case] = []
    omitted: list[str] = []
    for scheme, (directory, digest) in SOURCES.items():
        data = fetch(BASE+f"gen-val/json-files/{directory}/internalProjection.json", work / (scheme+".json"), digest)
        selected, excluded = cases(json.loads(data), scheme)
        vectors.extend(selected)
        omitted.extend(excluded)
    if first:
        vectors = [next(c for c in vectors if c.mode == mode and c.expected)
                   for mode in ("slh", "mldsa")]
    records: list[dict[str, object]] = []
    for case in vectors:
        got = invoke(binary, work, case)
        records.append({"name": case.name, "family": "ACVP", "passed": got == case.expected,
                        "expected": case.expected, "actual": got})
        if got != case.expected:
            raise ValueError(f"C disagrees with ACVP: {case.name}")
    records.append({"name": "invalid-lengths-before-read", "family": "bounds",
                    "passed": run([str(binary), "bounds"], work) == "0"})
    if first:
        require_unchanged(root, sources)
        return {"passed": all(r["passed"] for r in records), "first_case_only": True, "records": records,
                "source_sha256": sources, "seconds": round(time.monotonic()-started, 3),
                "milestone_acceptance": "open"}
    identities = openssl_identity(work)
    oracle, bindings = gallina_build(root, work / "gallina") if gallina else (None, None)
    positives = [next(c for c in vectors if c.mode == mode and c.expected)
                 for mode in ("slh", "slh-internal", "mldsa", "mldsa-internal", "mldsa-mu")]
    for positive in positives:
        for case in [positive, *refusals(positive)]:
            c_answer = invoke(binary, work, case)
            # Malformed root/context and our explicit message resource cap are
            # local API checks, outside OpenSSL's verifier result contract.
            local = any(case.name.endswith(s) for s in ("short-root", "long-root", "context-overlong", "message-overlong"))
            answers = {"c": c_answer}
            if not local:
                answers["openssl"] = openssl_verify(work, case)
            if oracle is not None and case.mode.startswith("mldsa") and not case.name.endswith("message-overlong"):
                operation = {"mldsa": "verify", "mldsa-internal": "verify_internal", "mldsa-mu": "verify_mu"}[case.mode]
                args = [case.pk.hex()]
                if case.mode == "mldsa":
                    args.append(case.context.hex())
                args.extend([case.message.hex(), case.signature.hex()])
                answer = oracle.invoke(work / "gallina", operation, args)
                if answer not in (["true"], ["false"]):
                    raise ValueError("invalid Gallina verifier answer")
                answers["gallina"] = answer == ["true"]
            records.append({"name": case.name, "family": "comparison", "expected": case.expected,
                            "answers": answers, "passed": all(v == case.expected for v in answers.values())})
    for positive in offline_fixtures(root):
        for case in [positive, refusals(positive)[0]]:
            answers = {"c": invoke(binary, work, case), "openssl": openssl_verify(work, case)}
            if oracle is not None and case.mode == "mldsa":
                answer = oracle.invoke(work / "gallina", "verify", [case.pk.hex(), case.context.hex(),
                                                                      case.message.hex(), case.signature.hex()])
                if answer not in (["true"], ["false"]):
                    raise ValueError("invalid Gallina fixture answer")
                answers["gallina"] = answer == ["true"]
            records.append({"name": case.name, "family": "offline-fixture", "answers": answers,
                            "expected": case.expected, "passed": all(v == case.expected for v in answers.values())})
    records.extend(boot_cases(root, binary, work))
    require_unchanged(root, sources)
    if receipts.executables("gcc") != compiler_identity:
        raise ValueError("C compiler changed during the campaign")
    return {"passed": all(r["passed"] for r in records), "records": records, "omitted_vectors": omitted,
            "git_revision": revision,
            "source_sha256": sources, "binary_sha256": sha(binary.read_bytes()),
            "acvp_revision": REVISION, "acvp_sources": SOURCES, "openssl": identities,
            "gallina_bindings": bindings, "gallina_comparison": "run" if gallina else "omitted",
            "compiler": compiler,
            "seconds": round(time.monotonic()-started, 3), "milestone_acceptance": "open",
            "limits": ["host executable only", "byte messages only", "target backend and firmware join open",
                       "no binary constant-time, masking or refinement claim"]}
