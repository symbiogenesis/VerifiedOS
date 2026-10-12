# SPDX-License-Identifier: Apache-2.0
"""The owning project source identity detects edits the Sail MD5 map omits."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import rocqterm, sailbundle


def _fixture() -> dict[str, str]:
    source = "function recorded() = 0\n"
    bundle: dict[str, Any] = {
        "version": 1, "embedding": "plain",
        "hashes": {"recorded.sail": {"md5": hashlib.md5(source.encode(), usedforsecurity=False).hexdigest()}},
        **{kind: {} for kind in ("functions", "mappings", "vals", "types", "registers", "lets", "anchors", "spans")},
    }
    return {"model/model/recorded.sail": source,
            "model/model/unhashed.sail": "function unhashed() = 1\n",
            sailbundle.PROJECT_FILE: "fixture project selecting both sources",
            sailbundle.BUNDLE: json.dumps(bundle)}


def _publish(root: Path) -> bytes:
    bundle = (root / sailbundle.BUNDLE).read_bytes()
    identity = sailbundle.source_identity(root, ["recorded.sail", "unhashed.sail"], bundle)
    (root / sailbundle.SOURCE_IDENTITY).write_bytes(identity)
    return bundle


def _refuses(root: Path, bundle: bytes, message: str) -> None:
    captured: dict[str, bytes] = {}
    try:
        sailbundle.read_source_identity(root, bundle, captured=captured)
    except (OSError, sailbundle.BundleError) as exc:
        ensure(message in str(exc), f"source identity refusal should name {message!r}: {exc}")
        ensure(not captured, "a refused identity must publish no partial byte captures")
    else:
        raise RuntimeError(f"source identity accepted invalid input: {message}")


def _complete_source_freshness() -> None:
    with sandbox_tree(_fixture()) as root:
        bundle = _publish(root)
        captured: dict[str, bytes] = {}
        owners = sailbundle.read_source_identity(root, bundle, captured=captured)
        omitted = "model/model/unhashed.sail"
        ensure(omitted in owners and set(owners) == set(captured),
               "project-selected files omitted by Sail's MD5 map must be checked and captured")
        ensure(owners[omitted] == hashlib.sha256(captured[omitted]).hexdigest(),
               "SHA-256 owners must bind the returned exact bytes")
        path = root / omitted
        before = path.stat()
        path.write_bytes(path.read_bytes().replace(b"= 1", b"= 2"))
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        _refuses(root, bundle, "digest differs")
        path.unlink()
        _refuses(root, bundle, "missing regular source")


def _binding_and_md5_consistency() -> None:
    with sandbox_tree(_fixture()) as root:
        bundle = _publish(root)
        _refuses(root, bundle + b"\n", "bundle digest differs")
        project = root / sailbundle.PROJECT_FILE
        original = project.read_bytes()
        project.write_bytes(original + b" altered selection")
        _refuses(root, bundle, "project digest differs")
        project.write_bytes(original)
        changed = json.loads(bundle)
        changed["hashes"]["recorded.sail"]["md5"] = "0" * 32
        stale_bundle = json.dumps(changed).encode()
        (root / sailbundle.SOURCE_IDENTITY).write_bytes(
            sailbundle.source_identity(root, ["recorded.sail", "unhashed.sail"], stale_bundle))
        _refuses(root, stale_bundle, "bundle MD5 differs")


def _schema_and_membership_fail_closed() -> None:
    with sandbox_tree(_fixture()) as root:
        bundle = _publish(root)
        target = root / sailbundle.SOURCE_IDENTITY
        baseline = target.read_bytes()
        variants: list[tuple[dict[str, Any], str]] = []
        for files in (0, True, 2.0, 3):
            raw = json.loads(baseline)
            raw["sources"]["files"] = files
            variants.append((raw, "count or aggregate"))
        raw = json.loads(baseline)
        raw["sources"]["aggregate"] = "0" * 64
        variants.append((raw, "count or aggregate"))
        raw = json.loads(baseline)
        del raw["sources"]["sha256"]["model/model/recorded.sail"]
        raw["sources"] = rocqterm.manifest(raw["sources"]["sha256"])
        variants.append((raw, "omits bundle owners"))
        raw = json.loads(baseline)
        raw["sources"] = rocqterm.manifest({})
        variants.append((raw, "complete source manifest"))
        raw = json.loads(baseline)
        raw["unexpected"] = "field"
        variants.append((raw, "malformed or unsupported"))
        for unsafe in ("model/model/../outside.sail", "model/model/C:/outside.sail",
                       "model/model/NUL.sail", "model/model/a\\b.sail"):
            raw = json.loads(baseline)
            raw["sources"]["sha256"] = {unsafe: "0" * 64}
            variants.append((raw, "unsafe"))
        for raw, message in variants:
            target.write_bytes(json.dumps(raw).encode())
            _refuses(root, bundle, message)
        for malformed in (b'{"format":1,"format":1}', b'{"constant":NaN}', b'not JSON'):
            target.write_bytes(malformed)
            _refuses(root, bundle, "not readable")
        target.write_bytes(baseline)
        ensure(len(sailbundle.read_source_identity(root, bundle)) == 2,
               "a repaired artifact must be read again after schema refusals")


def _generator_and_links_fail_closed() -> None:
    with sandbox_tree(_fixture()) as root:
        bundle = _publish(root)
        for listed in ([], ["recorded.sail", "recorded.sail"], ["../outside.sail"], ["missing.sail"]):
            try:
                sailbundle.source_identity(root, listed, bundle)
            except sailbundle.BundleError:
                pass
            else:
                raise RuntimeError(f"generator accepted an empty, duplicate or unsafe owner list: {listed}")

        def linked(path: Path) -> bool:
            return path.name == "unhashed.sail"

        for method in ("is_symlink", "is_junction"):
            with patch.object(Path, method, autospec=True, side_effect=linked):
                _refuses(root, bundle, "links and junctions")


def cases() -> list[Case]:
    return [Case("complete-source-freshness", _complete_source_freshness),
            Case("bundle-project-and-md5-binding", _binding_and_md5_consistency),
            Case("schema-and-membership-fail-closed", _schema_and_membership_fail_closed),
            Case("generator-and-links-fail-closed", _generator_and_links_fail_closed)]
