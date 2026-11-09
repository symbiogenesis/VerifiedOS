# SPDX-License-Identifier: Apache-2.0
"""Compose stored native package bytes without invoking a package producer.

[The fixed-package contract](../../docs/implementation/contracts/fixed-packages.md)
keeps this host image constructor separate from trusted admission. Actual proof
reuse is coordinated by [package_admission.py](package_admission.py); this command
cannot supply a trusted prior checked-state root or a checker-success flag.
"""

import json
import tempfile
from dataclasses import dataclass
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


@dataclass(frozen=True)
class _Inputs:
    recipe: Path
    original: bytes
    directory: Path
    placements: tuple[package_artifacts.Placement, ...]
    entry: int
    tohost: tuple[str, int] | None


def _inputs(root: Path, source: str, store: str) -> _Inputs:
    recipe_path = _path(root, source)
    raw, original = _recipe(recipe_path)
    directory = store_path(root, store)
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
    tohost = package_artifacts.observation_symbol(placements)
    return _Inputs(recipe_path, original, directory, tuple(placements), entry, tohost)


def _stable(inputs: _Inputs) -> None:
    for item in inputs.placements:
        if package_artifacts.load(inputs.directory, item.artifact.identity) != item.artifact:
            raise package_artifacts.PackageError("fixed composition stored artifact changed during construction")
    if _recipe(inputs.recipe)[1] != inputs.original:
        raise package_artifacts.PackageError("fixed composition recipe changed during construction")


def _report(inputs: _Inputs, path: str, blob: bytes) -> dict[str, object]:
    return {"scope": "fixed-package-host-composition", "production_admission": False,
            "recipe_sha256": package_artifacts.digest(inputs.original),
            "image": {"path": path, "sha256": package_artifacts.digest(blob)},
            "packages": [item.binding() for item in inputs.placements],
            "tohost": None if inputs.tohost is None else inputs.tohost[1],
            "open": ["actual TAL/CIC and modular linkage consumers",
                     "authenticated generation commit and native resident qualification"]}


def validate(root: Path, source: str, store: str, image: str) -> dict[str, object]:
    """Bind an existing image to the full recipe/CAS snapshot without writing."""
    inputs = _inputs(root, source, store)
    path = _path(root, image)
    blob = package_artifacts._ordinary_file(path, size=path.stat().st_size)
    package_artifacts.verify_image(blob, inputs.placements, expected_entry=inputs.entry)
    package_artifacts.verify_observation_symbol(blob, inputs.tohost)
    _stable(inputs)
    if package_artifacts._ordinary_file(path, size=len(blob)) != blob:
        raise package_artifacts.PackageError("fixed composition image changed during validation")
    return _report(inputs, image, blob)


def compose(root: Path, source: str, store: str, output: str) -> dict[str, object]:
    """Place exact CAS snapshots; validate the whole image before atomic publication."""
    inputs = _inputs(root, source, store)
    destination = _path(root, output)
    if (not destination.is_relative_to(root.resolve() / "out")
            or destination == root.resolve() / "out"
            or destination.is_dir()
            or destination.is_relative_to(inputs.directory)
            or destination == inputs.recipe
            or (destination.exists() and destination.samefile(inputs.recipe))):
        raise package_artifacts.PackageError("fixed composition output must be under out/ and protect its inputs/store")
    sections = [section for item in inputs.placements for section in item.sections]
    with tempfile.TemporaryDirectory(prefix="vos-fixed-image-") as temporary:
        interchange = Path(temporary) / "image.elf"
        symbols = {} if inputs.tohost is None else {"tohost": inputs.tohost}
        image.write_elf(interchange, sections, symbols, inputs.entry)
        blob = interchange.read_bytes()
    package_artifacts.verify_image(blob, inputs.placements, expected_entry=inputs.entry)
    package_artifacts.verify_observation_symbol(blob, inputs.tohost)
    _stable(inputs)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with atomic_path(destination) as pending:
        pending.write_bytes(blob)
    return _report(inputs, output, blob)
