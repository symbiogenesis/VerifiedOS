# SPDX-License-Identifier: Apache-2.0
"""Verify explicit historical helper/lock mappings without authorizing reuse."""

import gzip
import hashlib
import io
import json
import re
import zlib
from pathlib import Path
from typing import Any

from vos.atomic import atomic_path
from vos.jsonutil import unique_object

PROTOCOL = "verifiedos-contained-compiler-relocation/1"
CATALOG = "verifiedos-contained-compilation-candidates/1"
MAX_JSON = 8 * 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}")
REVISION = re.compile(r"[0-9a-f]{40}")


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _path(path: Path) -> Path:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("relocation paths must be absolute without parent traversal")
    if any(part.is_symlink() or part.is_junction() for part in (path, *path.parents)):
        raise ValueError("linked relocation paths are unsupported")
    return path.resolve()


def _json(data: bytes, where: str) -> dict[str, Any]:
    if len(data) > MAX_JSON:
        raise ValueError(f"oversized {where}")
    try:
        raw = json.loads(data, object_pairs_hook=unique_object,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite JSON")))
    except (ValueError, RecursionError) as error:
        raise ValueError(f"malformed {where}: {error}") from error
    if not isinstance(raw, dict):
        raise TypeError(f"{where} must be an object")
    return raw


def _hash(value: object) -> str:
    if not isinstance(value, str) or SHA256.fullmatch(value) is None:
        raise ValueError("malformed SHA-256 identity")
    return value


def _read(path: Path, snapshots: dict[Path, bytes]) -> bytes:
    path = _path(path)
    if not path.is_file() or path.stat().st_size > MAX_JSON:
        raise ValueError("missing or oversized relocation input")
    data = path.read_bytes()
    if path in snapshots and snapshots[path] != data:
        raise ValueError("relocation input changed during verification")
    snapshots[path] = data
    return data


def _recheck(snapshots: dict[Path, bytes]) -> None:
    for path, data in snapshots.items():
        if _path(path) != path or path.read_bytes() != data:
            raise ValueError("relocation input changed during verification")


def verify(catalog: Path, catalog_sha256: str, candidate: str, seal: Path,
           mapping: Path, *, output: Path | None = None,
           output_root: Path | None = None) -> dict[str, Any]:
    """Bind a trusted catalog/seal to exact mapped bytes; never import helpers."""
    snapshots: dict[Path, bytes] = {}
    catalog_data = _read(catalog, snapshots)
    if _digest(catalog_data) != _hash(catalog_sha256):
        raise ValueError("catalog differs from its independently supplied identity")
    raw = _json(catalog_data, "catalog")
    if raw.get("schema") != CATALOG or not isinstance(raw.get("candidates"), list):
        raise ValueError("unsupported compilation catalog")
    candidates = raw["candidates"]
    if any(not isinstance(item, dict) or not isinstance(item.get("name"), str)
           for item in candidates):
        raise ValueError("malformed compilation candidate")
    names = [item["name"] for item in candidates]
    if len(set(names)) != len(names) or candidate not in names:
        raise ValueError("missing or duplicate selected candidate")
    selected = candidates[names.index(candidate)]
    revision = selected.get("source_revision")
    if not isinstance(revision, str) or REVISION.fullmatch(revision) is None:
        raise ValueError("candidate lacks its immutable source revision")
    files = selected.get("files")
    reference = files.get("compile-seal.json") if isinstance(files, dict) else None
    if (not isinstance(reference, dict) or set(reference) != {"bytes", "sha256"}
            or type(reference["bytes"]) is not int or not 0 < reference["bytes"] <= MAX_JSON):
        raise ValueError("candidate lacks a supported compilation seal identity")
    stored = _read(seal, snapshots)
    if stored.startswith(b"\x1f\x8b"):
        # Limit the decompressed read before JSON decoding, including concatenated members.
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(stored)) as compressed:
                sealed_data = compressed.read(MAX_JSON + 1)
        except (OSError, EOFError, zlib.error) as error:
            raise ValueError("malformed compressed compilation seal") from error
    else:
        sealed_data = stored
    if len(sealed_data) != reference["bytes"] or _digest(sealed_data) != _hash(reference["sha256"]):
        raise ValueError("compilation seal differs from the selected catalog identity")
    sealed = _json(sealed_data, "compilation seal")
    if (sealed.get("schema") != "verifiedos-clean-compile-seal/2"
            or not isinstance(selected.get("native_root"), str)
            or sealed.get("original") != selected["native_root"]):
        raise ValueError("unsupported or substituted compilation seal origin")
    helpers = sealed.get("helpers")
    lock = sealed.get("lock")
    if (not isinstance(helpers, dict) or not helpers or not isinstance(lock, str)
            or lock in helpers or any(not isinstance(name, str) or not name.startswith("/")
                                      for name in (*helpers, lock))):
        raise ValueError("malformed sealed helper/lock identities")
    expected = {name: _hash(value) for name, value in helpers.items()}
    expected[lock] = _hash(sealed.get("lock_sha256"))
    mapped = _json(_read(mapping, snapshots), "relocation mapping")
    if (set(mapped) != {"schema", "candidate", "files"} or mapped["schema"] != PROTOCOL
            or mapped["candidate"] != candidate or not isinstance(mapped["files"], dict)
            or set(mapped["files"]) != set(expected)):
        raise ValueError("relocation mapping must cover exactly the selected sealed helper/lock paths")
    identities = []
    for historical, digest in sorted(expected.items()):
        current = mapped["files"][historical]
        if not isinstance(current, str) or not current:
            raise ValueError("malformed restored file path")
        path = _path(Path(current))
        data = _read(path, snapshots)
        if _digest(data) != digest:
            raise ValueError("restored helper/lock bytes differ from the compilation seal")
        identities.append({"historical": historical, "restored": str(path),
                           "sha256": digest, "bytes": len(data)})
    verifier = Path(__file__).resolve()
    verifier_data = _read(verifier, snapshots)
    report = {
        "schema": PROTOCOL, "status": "verified", "candidate": candidate,
        "source_revision": revision, "original_native_root": selected["native_root"],
        "catalog": {"path": str(_path(catalog)), "sha256": catalog_sha256},
        "seal": {"path": str(_path(seal)), "stored_sha256": _digest(stored),
                 "sha256": reference["sha256"]},
        "mapping": {"path": str(_path(mapping)), "sha256": _digest(snapshots[_path(mapping)])},
        "verifier": {"path": str(verifier), "sha256": _digest(verifier_data)},
        "files": identities, "compilation_reuse": False, "kernel_qualification": False,
        "target_acceptance": False, "checker_resume": False,
        "scope": "explicit helper/lock byte connection only; private path-bound reuse remains unavailable",
    }
    target = None
    if output is not None:
        if output_root is None:
            raise ValueError("report output needs an explicit output root")
        target, boundary = _path(output), _path(output_root)
        if not target.is_relative_to(boundary) or target == boundary:
            raise ValueError("report output escapes its declared root")
        if target in snapshots or (target.exists() and any(target.samefile(path) for path in snapshots)):
            raise ValueError("report output aliases a consumed input")
    _recheck(snapshots)
    if target is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with atomic_path(target) as pending:
            pending.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n",
                               encoding="utf-8", newline="\n")
    return report
