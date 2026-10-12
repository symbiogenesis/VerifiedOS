# SPDX-License-Identifier: Apache-2.0
"""Reviewed per-member corpus image identities; additions cannot rebaseline old bytes."""

import hashlib
import json
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

from vos import asm, differential, jsonutil, receipts

BASELINE = "tools/corpus-image-baseline.json"
SCHEMA = "verifiedos-corpus-image-baseline/1"
# The existing reviewed aggregate, reproduced before the per-member migration.
LEGACY_REVISION = "e47221691096395742d4e55f2069e6a859de08ac"
LEGACY_SHA256 = "80e754f5cc08dfbdf27c76f44a2319c0b5f4b31a11a472f8af16e9a777232318"
LEGACY_BYTES = 276_016
LEGACY_MEMBERS = 30
_SHA256 = re.compile(r"[0-9a-f]{64}")
_NAME = re.compile(r"[a-z][a-z0-9-]*")
_SOURCE = re.compile(r"[a-z][a-z0-9-]*\.s")


@dataclass(frozen=True)
class MemberImage:
    name: str
    source: str
    source_sha256: str
    image_sha256: str
    image_bytes: int


def capture(root: Path) -> tuple[tuple[MemberImage, ...], str, int]:
    """Assemble host-only images and bind the actual source bytes each read."""
    corpus = differential.load(root)
    if corpus.directory.is_symlink() or corpus.directory.is_junction():
        raise ValueError("corpus directory must not redirect outside the checkout")
    digest = hashlib.sha256()
    total = 0
    rows = []
    names: set[str] = set()
    sources: set[str] = set()
    with tempfile.TemporaryDirectory(prefix="vos-corpus-images-") as temporary:
        for member in corpus.members:
            if not _NAME.fullmatch(member.name) or not _SOURCE.fullmatch(member.source):
                raise ValueError(f"unsafe corpus member: {member.name!r} {member.source!r}")
            if member.name in names or member.source in sources:
                raise ValueError(f"duplicate corpus member: {member.name} {member.source}")
            names.add(member.name)
            sources.add(member.source)
            source = corpus.source(member)
            if source.is_symlink() or source.resolve().parent != corpus.directory.resolve():
                raise ValueError(f"corpus source escapes its directory: {member.source}")
            before = source.read_bytes()
            elf = Path(temporary) / f"{member.name}.elf"
            asm.assemble_file(source, elf)
            if source.read_bytes() != before:
                raise ValueError(f"source changed while assembling: {member.source}")
            image = elf.read_bytes()
            rows.append(MemberImage(member.name, member.source, hashlib.sha256(before).hexdigest(),
                                    hashlib.sha256(image).hexdigest(), len(image)))
            digest.update(image)
            total += len(image)
    if not rows:
        raise ValueError("empty corpus cannot establish an image baseline")
    return tuple(rows), digest.hexdigest(), total


def read(path: Path) -> tuple[MemberImage, ...]:
    if path.is_symlink() or path.is_junction():
        raise ValueError("corpus image baseline must be a regular file")
    raw = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=jsonutil.unique_object)
    if (not isinstance(raw, dict) or set(raw) != {"schema", "migration", "members"}
            or raw["schema"] != SCHEMA or raw["migration"] != migration_record()
            or not isinstance(raw["members"], list) or not raw["members"]):
        raise ValueError("unsupported or empty corpus image baseline")
    result = []
    names: set[str] = set()
    sources: set[str] = set()
    for row in raw["members"]:
        if (not isinstance(row, dict)
                or set(row) != {"name", "source", "source_sha256", "image_sha256", "image_bytes"}
                or not isinstance(row["name"], str) or not _NAME.fullmatch(row["name"])
                or not isinstance(row["source"], str) or not _SOURCE.fullmatch(row["source"])
                or not isinstance(row["source_sha256"], str) or not _SHA256.fullmatch(row["source_sha256"])
                or not isinstance(row["image_sha256"], str) or not _SHA256.fullmatch(row["image_sha256"])
                or type(row["image_bytes"]) is not int or row["image_bytes"] <= 0):
            raise ValueError("malformed corpus image baseline member")
        if row["name"] in names or row["source"] in sources:
            raise ValueError("duplicate corpus image baseline member")
        names.add(row["name"])
        sources.add(row["source"])
        result.append(MemberImage(**row))
    return tuple(result)


def migration_record() -> dict[str, str | int]:
    return {"revision": LEGACY_REVISION, "aggregate_sha256": LEGACY_SHA256,
            "aggregate_bytes": LEGACY_BYTES, "members": LEGACY_MEMBERS}


def compare(reviewed: tuple[MemberImage, ...], current: tuple[MemberImage, ...], *,
            allow_additions: bool = False) -> list[str]:
    """Old member identity is indivisible; ordering or additions cannot hide a change."""
    previous = {row.name: row for row in reviewed}
    now = {row.name: row for row in current}
    faults = []
    for name, row in previous.items():
        actual = now.get(name)
        if actual is None:
            faults.append(f"{name}: reviewed member removed")
        elif actual != row:
            changed = [field for field in ("source", "source_sha256", "image_sha256", "image_bytes")
                       if getattr(actual, field) != getattr(row, field)]
            faults.append(f"{name}: changed {', '.join(changed)}; requires a reviewed baseline update")
    if not allow_additions:
        faults += [f"{name}: new member requires corpus-images extend" for name in sorted(now.keys() - previous.keys())]
    return faults


def check(root: Path) -> list[str]:
    current, _, _ = capture(root)
    return compare(read(root / BASELINE), current)


def publish(path: Path, rows: tuple[MemberImage, ...], previous: bytes | None) -> None:
    if (path.read_bytes() if path.exists() else None) != previous:
        raise ValueError("corpus image baseline changed during preparation")
    raw = {"schema": SCHEMA, "migration": migration_record(), "members": [asdict(row) for row in rows]}
    with receipts.atomic_path(path) as pending:
        pending.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8", newline="\n")


def migrate(root: Path) -> None:
    path = root / BASELINE
    if path.exists():
        raise ValueError("corpus image baseline already exists; migration cannot overwrite it")
    rows, digest, size = capture(root)
    if (len(rows), digest, size) != (LEGACY_MEMBERS, LEGACY_SHA256, LEGACY_BYTES):
        raise ValueError(f"legacy aggregate mismatch: {len(rows)} members, {size} bytes, {digest}")
    publish(path, rows, None)


def extend(root: Path) -> int:
    path = root / BASELINE
    before = path.read_bytes()
    reviewed = read(path)
    current, _, _ = capture(root)
    faults = compare(reviewed, current, allow_additions=True)
    if faults:
        raise ValueError("; ".join(faults))
    names = {row.name for row in reviewed}
    additions = tuple(row for row in current if row.name not in names)
    if additions:
        publish(path, reviewed + additions, before)
    return len(additions)
