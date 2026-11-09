# SPDX-License-Identifier: Apache-2.0
"""Immutable native package objects, translated placement and physical image joins.

[The fixed-package contract](../../docs/implementation/contracts/fixed-packages.md)
owns this host construction boundary. Object hashes bind bytes, not their source
correspondence or proof validity. Proof objects never become loadable regions.
"""

import hashlib
import json
import re
import stat
import struct
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from filelock import FileLock

from vos import image, schema
from vos.atomic import atomic_path
from vos.jsonutil import unique_object

SCHEMA = Path(__file__).resolve().parents[1] / "composer/fixed-package.schema.json"
ADDRESS_LIMIT = 1 << 36
MANIFEST_LIMIT = 1 << 20
HASH = re.compile(r"[0-9a-f]{64}\Z")
NAME = re.compile(r"[a-z][a-z0-9-]{0,95}\Z")


class PackageError(ValueError):
    """A fixed package cannot be read, reused, placed or joined to an image."""


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                       allow_nan=False) + "\n").encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode(data: bytes) -> dict[str, Any]:
    if len(data) > MANIFEST_LIMIT:
        raise PackageError("fixed package manifest exceeds its byte limit")
    try:
        raw = json.loads(data, object_pairs_hook=unique_object)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise PackageError(f"unreadable fixed package JSON: {error}") from error
    if not isinstance(raw, dict):
        raise PackageError("fixed package JSON must be an object")
    return cast("dict[str, Any]", raw)


def _hash(value: object) -> str:
    if not isinstance(value, str) or HASH.fullmatch(value) is None:
        raise PackageError("fixed package requires a lowercase SHA-256 identity")
    return value


def _reference(raw: object) -> tuple[str, int]:
    if (not isinstance(raw, dict) or set(raw) != {"sha256", "bytes"}
            or type(raw["bytes"]) is not int or not 0 < raw["bytes"] <= ADDRESS_LIMIT):
        raise PackageError("malformed fixed package object reference")
    return _hash(raw["sha256"]), raw["bytes"]


def _references(document: Mapping[str, Any]) -> dict[str, int]:
    values = [document["source_closure"], document["contract"],
              *(region["object"] for region in document["regions"]),
              document["proofs"]["derivation_template"], document["proofs"]["correspondence"],
              *document["proofs"]["hyperproperties"]]
    result: dict[str, int] = {}
    for raw in values:
        identity, size = _reference(raw)
        if identity in result and result[identity] != size:
            raise PackageError("one fixed object identity has inconsistent declared lengths")
        result[identity] = size
    return result


def _power_of_two(value: int) -> bool:
    return value > 0 and value & (value - 1) == 0


def _manifest(document: dict[str, Any]) -> None:
    try:
        schema.validate(SCHEMA, document)
    except ValueError as error:
        raise PackageError(f"fixed package schema: {error}") from error
    if type(document["schema_version"]) is not int:
        raise PackageError("fixed package schema version must be an integer")
    for value in document["context"].values():
        _hash(value)
    if NAME.fullmatch(document["package_id"]) is None:
        raise PackageError("invalid fixed package name")
    if not _power_of_two(document["alignment"]):
        raise PackageError("fixed package alignment must be a power of two")
    names: set[str] = set()
    extents: list[tuple[int, int]] = []
    code: list[tuple[int, int]] = []
    for region in document["regions"]:
        if NAME.fullmatch(region["name"]) is None:
            raise PackageError("invalid fixed package region name")
        if region["name"] in names:
            raise PackageError("duplicate fixed package region name")
        names.add(region["name"])
        _, size = _reference(region["object"])
        offset, alignment = region["offset"], region["alignment"]
        if (not _power_of_two(alignment) or document["alignment"] % alignment
                or offset % alignment or offset + size > document["span"]):
            raise PackageError("fixed package region alignment or extent differs from its span")
        if any(offset < end and start < offset + size for start, end in extents):
            raise PackageError("fixed package regions overlap")
        extents.append((offset, offset + size))
        if region["kind"] == "code":
            if offset % 4 or size % 4 or alignment < 4:
                raise PackageError("canonical fixed package code must contain aligned whole instructions")
            code.append((offset, offset + size))
    if document["entry"] % 4 or not any(start <= document["entry"] < end for start, end in code):
        raise PackageError("fixed package entry is outside aligned code")
    exported: set[str] = set()
    for item in document["exports"]:
        if NAME.fullmatch(item["name"]) is None:
            raise PackageError("invalid fixed package export name")
        if item["name"] in exported:
            raise PackageError("duplicate fixed package export name")
        exported.add(item["name"])
        if not any(start <= item["offset"] < end for start, end in extents):
            raise PackageError("fixed package export is outside its regions")
        if item["offset"] % 4 and any(start <= item["offset"] < end for start, end in code):
            raise PackageError("fixed package code export is not instruction aligned")
    proof_objects = {ref["sha256"] for ref in (
        document["proofs"]["derivation_template"], document["proofs"]["correspondence"],
        *document["proofs"]["hyperproperties"])}
    if any(region["object"]["sha256"] in proof_objects for region in document["regions"]):
        raise PackageError("fixed package proof objects cannot be loadable regions")
    _references(document)


@dataclass(frozen=True)
class Artifact:
    identity: str
    manifest: bytes
    objects: tuple[tuple[str, bytes], ...]

    def document(self) -> dict[str, Any]:
        return _decode(self.manifest)

    @property
    def package_id(self) -> str:
        return str(self.document()["package_id"])

    def validate(self) -> None:
        if not isinstance(self.manifest, bytes) or type(self.objects) is not tuple:
            raise PackageError("fixed artifact storage must be immutable bytes and tuples")
        document = self.document()
        _manifest(document)
        if self.manifest != canonical(document) or digest(self.manifest) != _hash(self.identity):
            raise PackageError("fixed package manifest content identity differs")
        wanted = _references(document)
        found: set[str] = set()
        for item in self.objects:
            if (type(item) is not tuple or len(item) != 2 or not isinstance(item[1], bytes)
                    or not isinstance(item[0], str) or item[0] in found):
                raise PackageError("malformed or duplicate fixed package object population")
            identity, data = item
            found.add(identity)
            if (identity not in wanted or len(data) != wanted[identity] or digest(data) != identity):
                raise PackageError("fixed package object digest or byte length differs")
        if found != wanted.keys():
            raise PackageError("fixed package object population is incomplete")


def _ordinary_file(path: Path, *, size: int | None = None) -> bytes:
    if path.resolve() != path or not stat.S_ISREG(path.stat().st_mode):
        raise PackageError(f"fixed package input must be an ordinary non-redirected file: {path}")
    limit = MANIFEST_LIMIT if size is None else size
    actual_size = path.stat().st_size
    if actual_size > limit or (size is not None and actual_size != size):
        raise PackageError("fixed package object digest or byte length differs")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit or (size is not None and len(data) != size):
        raise PackageError("fixed package object digest or byte length differs")
    return data


def _input(root: Path, relative: object) -> Path:
    if (not isinstance(relative, str) or not relative or "\\" in relative
            or Path(relative).is_absolute() or ".." in Path(relative).parts):
        raise PackageError("fixed package transport path must be checkout-relative")
    base = root.resolve()
    path = base / relative
    if not path.is_relative_to(base) or path.resolve() != path:
        raise PackageError("fixed package transport path escapes or redirects")
    return path


def read_request(root: Path, source: str) -> Artifact:
    """Snapshot a transport request, excluding transport paths from content identity."""
    request = _decode(_ordinary_file(_input(root, source)))
    if set(request) != {"manifest", "objects"} or not isinstance(request["manifest"], dict):
        raise PackageError("fixed package request requires manifest and object transports")
    document = request["manifest"]
    _manifest(document)
    wanted = _references(document)
    transports = request["objects"]
    if not isinstance(transports, list) or len(transports) != len(wanted):
        raise PackageError("fixed package transport population differs from manifest")
    objects: dict[str, bytes] = {}
    for transport in transports:
        if not isinstance(transport, dict) or set(transport) != {"path", "sha256", "bytes"}:
            raise PackageError("malformed fixed package object transport")
        identity, size = _reference({key: value for key, value in transport.items() if key != "path"})
        if identity not in wanted or wanted[identity] != size or identity in objects:
            raise PackageError("fixed package object transport identity differs or repeats")
        path = _input(root, transport["path"])
        if path.stat().st_size != size:
            raise PackageError("fixed package transport byte length differs")
        objects[identity] = _ordinary_file(path, size=size)
    content = canonical(document)
    artifact = Artifact(digest(content), content, tuple(sorted(objects.items())))
    artifact.validate()
    return artifact


def _directory(path: Path, *, create: bool) -> None:
    for ancestor in reversed((path, *path.parents)):
        try:
            mode = ancestor.lstat().st_mode
        except FileNotFoundError:
            if not create:
                raise
            ancestor.mkdir()
            continue
        if not stat.S_ISDIR(mode) or ancestor.resolve() != ancestor:
            raise PackageError("fixed package store directories must not redirect")


def _publish(path: Path, data: bytes) -> None:
    if path.exists() or path.is_symlink():
        if _ordinary_file(path, size=len(data)) != data:
            raise PackageError("corrupt fixed package store object refuses publication")
        return
    with atomic_path(path) as pending:
        pending.write_bytes(data)


def store(directory: Path, artifact: Artifact) -> str:
    """Publish immutable content objects; corrupt retained bytes are never repaired."""
    artifact.validate()
    home = directory.absolute()
    _directory(home, create=True)
    lock = home / ".publish.lock"
    if lock.is_symlink() or lock.resolve() != lock:
        raise PackageError("fixed package store lock must not redirect")
    with FileLock(lock, timeout=30):
        _directory(home / "objects", create=True)
        _directory(home / "manifests", create=True)
        retained = home / "manifests" / f"{artifact.identity}.json"
        if retained.exists() or retained.is_symlink():
            # An existing root must still be complete; publishing the same
            # artifact cannot silently restore a missing retained object.
            load(home, artifact.identity)
            return artifact.identity
        # Preflight every existing destination before publishing any new object.
        outputs = [(home / "objects" / f"{identity}.bin", data) for identity, data in artifact.objects]
        outputs.append((home / "manifests" / f"{artifact.identity}.json", artifact.manifest))
        for path, data in outputs:
            if (path.exists() or path.is_symlink()) and _ordinary_file(path, size=len(data)) != data:
                raise PackageError("corrupt fixed package store object refuses publication")
        for path, data in outputs:
            _publish(path, data)
    return artifact.identity


def load(directory: Path, identity: str) -> Artifact:
    home = directory.absolute()
    _directory(home, create=False)
    _hash(identity)
    content = _ordinary_file(home / "manifests" / f"{identity}.json")
    document = _decode(content)
    _manifest(document)
    objects = tuple((sha, _ordinary_file(home / "objects" / f"{sha}.bin", size=size))
                    for sha, size in sorted(_references(document).items()))
    artifact = Artifact(identity, content, objects)
    artifact.validate()
    return artifact


@dataclass(frozen=True)
class Placement:
    artifact: Artifact
    base: int
    sections: tuple[image.Section, ...]
    entry: int
    exports: tuple[tuple[str, int], ...]

    @property
    def span(self) -> int:
        return int(self.artifact.document()["span"])

    def binding(self) -> dict[str, object]:
        return {"package_id": self.artifact.package_id, "artifact": self.artifact.identity,
                "base": self.base, "span": self.span, "entry": self.entry,
                "exports": dict(self.exports)}


def place(artifact: Artifact, base: int) -> Placement:
    artifact.validate()
    document = artifact.document()
    if (type(base) is not int or base < 0 or base % document["alignment"]
            or base + document["span"] > ADDRESS_LIMIT):
        raise PackageError("fixed package placement alignment or address overflow")
    objects = dict(artifact.objects)
    sections = tuple(image.Section(f".{document['package_id']}.{region['name']}",
        base + region["offset"], bytearray(objects[region["object"]["sha256"]]),
        writable=region["kind"] == "initializer", executable=region["kind"] == "code")
        for region in document["regions"])
    return Placement(artifact, base, sections, base + document["entry"],
                     tuple((item["name"], base + item["offset"]) for item in document["exports"]))


def _placements(placements: Sequence[Placement]) -> tuple[Placement, ...]:
    fresh = tuple(place(item.artifact, item.base) for item in placements)
    if not fresh or len({item.artifact.package_id for item in fresh}) != len(fresh):
        raise PackageError("fixed package roster is empty or repeats a package identity")
    for index, item in enumerate(fresh):
        for other in fresh[:index]:
            if item.base < other.base + other.span and other.base < item.base + item.span:
                raise PackageError("fixed package reserved spans overlap")
    return fresh


@dataclass(frozen=True)
class MemoryRegion:
    base: int
    size: int
    memory_class: int
    writable: bool
    executable: bool


def validate_memory(placements: Sequence[Placement], regions: Sequence[MemoryRegion]) -> None:
    fresh = _placements(placements)
    for index, region in enumerate(regions):
        if (type(region.base) is not int or type(region.size) is not int
                or region.base < 0 or region.size <= 0 or region.base + region.size > ADDRESS_LIMIT
                or type(region.memory_class) is not int or region.memory_class not in (0, 1)
                or type(region.writable) is not bool or type(region.executable) is not bool):
            raise PackageError("invalid physical memory class region")
        if any(region.base < other.base + other.size and other.base < region.base + region.size
               for other in regions[:index]):
            raise PackageError("physical memory class regions overlap")
    for item in fresh:
        for section, declared in zip(item.sections, item.artifact.document()["regions"], strict=True):
            homes = [region for region in regions if region.base <= section.addr
                     and section.addr + len(section.data) <= region.base + region.size]
            if (len(homes) != 1 or homes[0].memory_class != declared["memory_class"]
                    or (section.writable and not homes[0].writable)
                    or (section.executable and not homes[0].executable)):
                raise PackageError("fixed package region has incompatible physical memory class or permissions")


def verify_image(blob: bytes, placements: Sequence[Placement], *, expected_entry: int | None = None) -> None:
    """Check physical PT_LOAD effects and an optional caller-selected package entry."""
    fresh = _placements(placements)
    if len(blob) < image.EHDR_SIZE:
        raise PackageError("fixed package image is not an ELF64 RISC-V executable")
    header = struct.unpack_from("<16sHHIQQQIHHHHHH", blob)
    if (header[0][:7] != b"\x7fELF\x02\x01\x01" or header[1] != image.ET_EXEC
            or header[2] != image.EM_RISCV or header[3] != 1 or header[8] != image.EHDR_SIZE
            or header[9] != image.PHDR_SIZE or not 0 < header[10] < 0xffff):
        raise PackageError("fixed package image is not a supported ELF64 RISC-V executable")
    if header[5] + header[10] * image.PHDR_SIZE > len(blob):
        raise PackageError("fixed package image program table is truncated")
    entries = {item.entry for item in fresh}
    if header[4] not in entries:
        raise PackageError("fixed package image entry differs from declared package entries")
    if expected_entry is not None and (type(expected_entry) is not int or expected_entry not in entries
                                       or header[4] != expected_entry):
        raise PackageError("fixed package image entry differs from the selected package entry")
    expected = [(item, section) for item in fresh for section in item.sections]
    matched: set[int] = set()
    extents: list[tuple[int, int]] = []
    for index in range(header[10]):
        kind, flags, offset, virtual, physical, file_size, memory_size, alignment = struct.unpack_from(
            "<IIQQQQQQ", blob, header[5] + index * image.PHDR_SIZE)
        if kind != image.PT_LOAD:
            continue
        if (file_size > memory_size or offset + file_size > len(blob)
                or physical + memory_size > ADDRESS_LIMIT or virtual != physical
                or not _power_of_two(alignment) or offset % alignment != physical % alignment):
            raise PackageError("fixed package image load extent is invalid or truncated")
        if memory_size and any(physical < end and start < physical + memory_size for start, end in extents):
            raise PackageError("fixed package image load segments overlap")
        extents.append((physical, physical + memory_size))
        hits = [i for i, (_, section) in enumerate(expected)
                if section.addr == physical and len(section.data) == file_size == memory_size]
        if len(hits) != 1 or hits[0] in matched:
            raise PackageError("fixed package image load extent differs from declared regions")
        selected = hits[0]
        section = expected[selected][1]
        if flags != section.p_flags or blob[offset:offset + file_size] != section.data:
            raise PackageError("fixed package image bytes or permissions differ from immutable artifact")
        matched.add(selected)
    if matched != set(range(len(expected))):
        raise PackageError("fixed package image omits a declared loadable region")
