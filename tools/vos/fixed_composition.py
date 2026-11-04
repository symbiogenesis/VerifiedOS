# SPDX-License-Identifier: Apache-2.0
"""Compose stored native package bytes without invoking a package producer.

[The fixed-package contract](../../docs/implementation/contracts/fixed-packages.md)
keeps this host image constructor separate from trusted admission. Actual proof
reuse is coordinated by [package_admission.py](package_admission.py); this command
cannot supply a trusted prior checked-state root or a checker-success flag.
"""

import json
import tempfile
from pathlib import Path
from typing import Any, cast

from vos import image, package_artifacts, schema
from vos.atomic import atomic_path
from vos.jsonutil import unique_object

SCHEMA = Path(__file__).resolve().parents[1] / "composer/fixed-composition.schema.json"


def _path(root: Path, relative: str) -> Path:
    base = root.resolve()
    candidate = base / relative
    if (not relative or Path(relative).is_absolute() or "\\" in relative
            or ".." in Path(relative).parts or not candidate.is_relative_to(base)
            or candidate.resolve() != candidate):
        raise package_artifacts.PackageError("fixed composition path must be checkout-relative and not redirect")
    return candidate


def store_path(root: Path, relative: str) -> Path:
    """Keep host CAS outputs under the checkout's declared output directory."""
    path = _path(root, relative)
    if not path.is_relative_to(root.resolve() / "out") or path == root.resolve() / "out":
        raise package_artifacts.PackageError("fixed package host store belongs under out/")
    return path


def publish_package(root: Path, source: str, store: str) -> dict[str, object]:
    artifact = package_artifacts.read_request(root, source)
    directory = store_path(root, store)
    package_artifacts.store(directory, artifact)
    return {"artifact": artifact.identity, "package_id": artifact.package_id,
            "store": store, "production_admission": False}


def _recipe(path: Path) -> tuple[dict[str, Any], bytes]:
    if not path.is_file():
        raise package_artifacts.PackageError("fixed composition recipe must be an ordinary file")
    with path.open("rb") as stream:
        contents = stream.read(package_artifacts.MANIFEST_LIMIT + 1)
    if len(contents) > package_artifacts.MANIFEST_LIMIT:
        raise package_artifacts.PackageError("fixed composition recipe exceeds its byte limit")
    try:
        raw = json.loads(contents, object_pairs_hook=unique_object)
        schema.validate(SCHEMA, raw)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise package_artifacts.PackageError(f"fixed composition recipe: {error}") from error
    result = cast("dict[str, Any]", raw)
    if type(result["schema_version"]) is not int:
        raise package_artifacts.PackageError("fixed composition schema version must be an integer")
    return result, contents


def compose(root: Path, source: str, store: str, output: str) -> dict[str, object]:
    """Place exact CAS snapshots; validate the whole image before atomic publication."""
    recipe_path = _path(root, source)
    raw, original = _recipe(recipe_path)
    directory = store_path(root, store)
    destination = _path(root, output)
    if (not destination.is_relative_to(root.resolve() / "out")
            or destination == root.resolve() / "out"
            or destination.is_dir()
            or destination.is_relative_to(directory)
            or destination == recipe_path
            or (destination.exists() and destination.samefile(recipe_path))):
        raise package_artifacts.PackageError("fixed composition output must be under out/ and protect its inputs/store")
    placements: list[package_artifacts.Placement] = []
    identities: set[str] = set()
    for member in raw["packages"]:
        identity = member["artifact"]
        if identity in identities:
            raise package_artifacts.PackageError("fixed composition repeats an artifact")
        identities.add(identity)
        artifact = package_artifacts.load(directory, identity)
        if artifact.document()["context"] != raw["context"]:
            raise package_artifacts.PackageError("fixed composition artifact context differs from the selected context")
        placements.append(package_artifacts.place(artifact, member["base"]))
    if raw["entry"] not in identities:
        raise package_artifacts.PackageError("fixed composition entry must name one placed artifact")
    memory = [package_artifacts.MemoryRegion(**region) for region in raw["memory"]]
    package_artifacts.validate_memory(placements, memory)
    entry = next(item.entry for item in placements if item.artifact.identity == raw["entry"])
    sections = [section for item in placements for section in item.sections]
    with tempfile.TemporaryDirectory(prefix="vos-fixed-image-") as temporary:
        interchange = Path(temporary) / "image.elf"
        image.write_elf(interchange, sections, {}, entry)
        blob = interchange.read_bytes()
    package_artifacts.verify_image(blob, placements)
    for item in placements:
        if package_artifacts.load(directory, item.artifact.identity) != item.artifact:
            raise package_artifacts.PackageError("fixed composition stored artifact changed during construction")
    if _recipe(recipe_path)[1] != original:
        raise package_artifacts.PackageError("fixed composition recipe changed during construction")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with atomic_path(destination) as pending:
        pending.write_bytes(blob)
    return {"scope": "fixed-package-host-composition", "production_admission": False,
            "recipe_sha256": package_artifacts.digest(original),
            "image": {"path": output, "sha256": package_artifacts.digest(blob)},
            "packages": [item.binding() for item in placements],
            "open": ["actual TAL/CIC and modular linkage consumers",
                     "authenticated generation commit and native resident qualification"]}
