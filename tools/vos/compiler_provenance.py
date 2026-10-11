# SPDX-License-Identifier: Apache-2.0
"""Bind a contained compiler's retained source build to its released toolchain lock."""

import json
import re
from pathlib import Path
from typing import cast

from vos import compiler_component, receipts
from vos.corpus import find_root
from vos.jsonc import Json

LOCK = "tools/opam/contained-compiler.lock"
TOOLS = {"prover": "rocq-core", "ocaml": "ocaml-base-compiler", "menhir": "menhir"}
_SHA256 = re.compile(r"[0-9a-f]{64}")


def toolchain(raw: object, lock: Path) -> dict[str, Json]:
    """Require every native tool identity and its exact package version in the lock.

    The executable hashes identify the binaries the build actually used. They need
    not identify tools installed on the reader's host: portable target receipts
    are read on machines which do not install this contained producer.
    """
    if not isinstance(raw, dict) or raw.get("lock_sha256") != receipts.digest(lock):
        raise ValueError("contained compiler toolchain does not bind the recorded lock")
    installed = compiler_component.installed(lock.read_text(encoding="utf-8"))
    result: dict[str, Json] = {"lock_sha256": receipts.digest(lock)}
    for role, package in TOOLS.items():
        versions = [name.removeprefix(package + ".") for name in installed
                    if name.startswith(package + ".")]
        identity = raw.get(role)
        if len(versions) != 1 or not isinstance(identity, dict):
            raise ValueError(f"contained compiler toolchain is missing {role} identity")
        version, reported, digest = (identity.get(key) for key in (
            "version", "reported_version", "executable_sha256"))
        if (identity.get("package") != package or version != versions[0]
                or not isinstance(reported, str) or not reported.strip()
                or not isinstance(digest, str) or _SHA256.fullmatch(digest) is None):
            raise ValueError(f"contained compiler {role} identity disagrees with the recorded lock")
        if role == "prover":
            agrees = compiler_component.reports_release(reported, versions[0])
        else:
            agrees = re.search(rf"(?<![\w.]){re.escape(versions[0])}(?![\w.+~-])", reported) is not None
        if not agrees:
            raise ValueError(f"contained compiler {role} reported version disagrees with the recorded lock")
        result[role] = cast("dict[str, Json]", identity)
    return result


def portable(raw: object, lock: Path) -> dict[str, Json]:
    """Validate a staged producer receipt without its external native binaries."""
    if (not isinstance(raw, dict) or raw.get("build_receipt") != "present"
            or not isinstance(raw.get("revision"), str) or not raw["revision"].strip()
            or not isinstance(raw.get("compiler_sha256"), str)
            or _SHA256.fullmatch(raw["compiler_sha256"]) is None
            or type(raw.get("source_count")) is not int or raw["source_count"] < 1):
        raise ValueError("staged target requires complete contained compiler provenance")
    toolchain(raw.get("toolchain"), lock)
    return cast("dict[str, Json]", raw)


def read(ccomp: Path, lock: Path | None = None,
         required: bool = True) -> tuple[dict[str, Json], dict[str, str]]:
    """Read exact retained source and native-tool identities; absence is explicit.

    Target acceptance requires the receipt. Compiler-diff also examines unbuilt or
    stock executables, so it may report absence, but never swallow an invalid or
    partially present receipt as though no receipt stood there.
    """
    ccomp = ccomp.resolve()
    result_path, inputs_path = ccomp.parent / "build-result.json", ccomp.parent / "build-inputs.json"
    if not result_path.exists() and not inputs_path.exists() and not required:
        return {"build_receipt": "absent", "toolchain": None}, {}
    result = json.loads(result_path.read_text(encoding="utf-8"))
    inputs = json.loads(inputs_path.read_text(encoding="utf-8"))
    if (not isinstance(result, dict) or result.get("passed") is not True
            or result.get("inputs_unchanged") is not True
            or result.get("compiler_sha256") != receipts.digest(ccomp)
            or not isinstance(result.get("revision"), str) or not result["revision"]):
        raise ValueError("target requires a successful source-bound contained compiler build")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError("contained compiler source manifest is absent")
    for name, identity in inputs.items():
        if not isinstance(name, str) or not isinstance(identity, dict):
            raise TypeError("invalid contained compiler source manifest entry")
        path = (ccomp.parent / name.removeprefix("native:")).resolve()
        expected = identity.get("sha256" if name.startswith("native:") else "canonical_sha256")
        if not path.is_relative_to(ccomp.parent) or not isinstance(expected, str):
            raise ValueError("invalid contained compiler source manifest entry")
        if receipts.digest(path) != expected:
            raise ValueError(f"contained compiler build source changed: {name}")
    lock = lock or find_root() / LOCK
    native = toolchain(result.get("toolchain"), lock)
    return ({"build_receipt": "present", "revision": result["revision"],
             "kind": result.get("kind"), "compiler_sha256": result["compiler_sha256"],
             "source_count": len(inputs), "toolchain": native},
            {str(path): receipts.digest(path) for path in (result_path, inputs_path, lock)})


def unchanged(files: dict[str, str]) -> bool:
    """The retained receipts and lock are immutable throughout a target campaign."""
    return all(receipts.digest(Path(path)) == digest for path, digest in files.items())
