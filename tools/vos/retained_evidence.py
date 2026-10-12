# SPDX-License-Identifier: Apache-2.0
"""Retained evidence identities, contained bundles and indexed citation validation.

A retained record preserves observed bytes. It supplies no current build or proof
acceptance; the external indexed citation and its hash own the retention relation.
"""

import ctypes
import gzip
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata
import zlib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import cast
from urllib.parse import quote, unquote

from vos import receipts

EVIDENCE = "docs/implementation/retained-evidence"
# A label describes the record; the resolved indexed target and hash identify it.
_LINK = re.compile(r"\[(?P<label>[^\]\r\n]+)\]\((?P<target><[^>\r\n]+>|[^)\s]+)\)"
                   r"(?:\s*[,(]?\s*(?:has\s+)?SHA-?256\s+`(?P<sha>[0-9a-f]{64})`)?")
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _cited(rel: str) -> str:
    """The path a citation names for the copy at `rel`; guest paths are absolute."""
    return "/" + rel if rel.startswith("root/") else rel


def _tracked(root: Path) -> list[str]:
    done = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True,
                          check=True, timeout=60)
    return [name for name in done.stdout.decode("utf-8").split("\0") if name]


def _bindings(value: object) -> Iterator[tuple[str, str]]:
    """Every JSON object that binds a path to a SHA-256."""
    if isinstance(value, dict):
        path, sha = value.get("path"), value.get("sha256")
        if isinstance(path, str) and isinstance(sha, str):
            yield path, sha
        for item in value.values():
            yield from _bindings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _bindings(item)


def _manifest_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """A retained map may not conceal a member beneath a duplicate JSON key."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate manifest key {key!r}")
        result[key] = value
    return result


def _manifest_files(blob: bytes) -> dict[str, object]:
    document = json.loads(blob.decode("utf-8"), object_pairs_hook=_manifest_object)
    files = document.get("files") if isinstance(document, dict) else None
    if not isinstance(files, dict) or not files:
        raise ValueError("bundle manifest requires a nonempty files map")
    return cast("dict[str, object]", files)


def _member_path(root: Path, owner: str, path: object) -> str:
    """Portable relative names must stay beneath their manifest's own directory."""
    if not isinstance(path, str) or not path:
        raise ValueError("member path must be a nonempty relative name")
    portable = path.replace("\\", "/")
    windows, posix = PureWindowsPath(path), PurePosixPath(portable)
    if windows.drive or windows.root or posix.is_absolute() or ".." in posix.parts:
        raise ValueError(f"absolute or traversing member path {path!r}")
    manifest = (root / EVIDENCE / owner).resolve()
    target = (manifest.parent / portable).resolve()
    if target == manifest or not target.is_relative_to(manifest.parent):
        raise ValueError(f"self or escaping member path {path!r}")
    return target.relative_to((root / EVIDENCE).resolve()).as_posix()


def _identity(data: bytes, sha: object, count: object, role: str) -> None:
    if (not isinstance(sha, str) or _SHA256.fullmatch(sha) is None
            or type(count) is not int or count < 0):
        raise ValueError(f"{role} identity requires SHA-256 and a nonnegative byte count")
    if len(data) != count or hashlib.sha256(data).hexdigest() != sha:
        raise ValueError(f"{role} hash or size does not match the retained bytes")


def _member_bytes(blob: bytes, entry: dict[str, object]) -> int:
    """Check the stored bytes and, for gzip, the decoded content separately."""
    encoding = entry.get("encoding", "identity")
    if encoding not in ("identity", "gzip"):
        raise ValueError(f"unknown member encoding {encoding!r}")
    stored = encoding == "gzip" or "stored_sha256" in entry or "stored_bytes" in entry
    if stored:
        _identity(blob, entry.get("stored_sha256"), entry.get("stored_bytes"), "stored")
    content = blob
    if encoding == "gzip":
        if not blob.startswith(b"\x1f\x8b"):
            raise ValueError("gzip member lacks a gzip header")
        content = gzip.decompress(blob)
    _identity(content, entry.get("sha256"), entry.get("bytes"), "content")
    return 1 + int(stored)


def _distinct_member(root: Path, owner: str, path: object, targets: set[str]) -> str:
    member = _member_path(root, owner, path)
    folded = member.casefold()
    if folded in targets:
        raise ValueError(f"colliding member path {member!r}")
    targets.add(folded)
    return member


def _bundles(root: Path, names: set[str], data: dict[str, bytes],
             roots: set[str]) -> tuple[list[str], set[str], int]:
    """Only independently linked, SHA-bound manifests confer member citation.

    A nested manifest is retained as bytes; it needs its own external root before
    its children count. Internal links or a cycle never create an external root.
    """
    findings: list[str] = []
    seen: set[str] = set()
    compared = 0
    for owner in sorted(name for name in names if PurePosixPath(name).name == "manifest.json"):
        if owner not in roots:
            findings.append(f"{owner}: bundle has no externally linked SHA-bound root")
        if owner not in data:
            continue
        try:
            files = _manifest_files(data[owner])
        except ValueError as error:
            findings.append(f"{owner}: invalid bundle schema ({error})")
            continue
        targets: set[str] = set()
        for key, entry in files.items():
            if not isinstance(entry, dict):
                findings.append(f"{owner}: member {key!r} is not an identity record")
                continue
            try:
                member = _distinct_member(root, owner, entry.get("path", key), targets)
                blob = data.get(member) if member in names else None
                if blob is None:
                    findings.append(f"{owner}: member {key!r} names no indexed readable copy: {member}")
                    continue
                checked = _member_bytes(blob, entry)
            except (OSError, ValueError, EOFError, zlib.error) as error:
                findings.append(f"{owner}: member {key!r} is invalid ({error})")
                continue
            compared += checked
            if owner in roots:
                seen.add(_cited(member))
    return findings, seen, compared


def findings(root: Path) -> tuple[list[str], int]:
    """Each disagreement between the copies and their citations, and the hashes compared."""
    tracked = _tracked(root)
    prefix = EVIDENCE + "/"
    names = {name[len(prefix):] for name in tracked
             if name.startswith(prefix) and name != prefix + "README.md"}
    findings: list[str] = []
    data: dict[str, bytes] = {}
    for rel in sorted(names):
        try:
            _no_links(root / prefix / rel)
            data[rel] = (root / prefix / rel).read_bytes()
        except (OSError, ValueError) as error:
            findings.append(f"{rel}: retained copy cannot be read ({error})")
    copies = {rel: hashlib.sha256(blob).hexdigest() for rel, blob in data.items()}
    by_cited = {_cited(rel): rel for rel in names}
    evidence = (root / EVIDENCE).resolve()
    compared = 0
    for rel in copies:
        if rel.endswith(".json"):
            try:
                json.loads(data[rel].decode("utf-8"))
            except ValueError as err:
                findings.append(f"{rel}: not valid JSON ({err})")
    seen: set[str] = set()
    roots: set[str] = set()
    for name in tracked:
        if name.startswith(prefix) or not name.endswith((".md", ".json")):
            continue
        text = (root / name).read_text(encoding="utf-8", errors="replace")
        present = [cited for cited in by_cited if cited in text]
        if name.endswith(".json"):
            if not present:
                continue
            try:
                document = json.loads(text)
            except ValueError as error:
                findings.append(f"{name}: not valid JSON ({error})")
                continue
            seen.update(present)
            for path, sha in _bindings(document):
                if path in by_cited:
                    compared += 1
                    if sha != copies.get(by_cited[path]):
                        findings.append(f"{name}: binds {path} to {sha}, "
                                        f"not its retained copy's bytes")
                    else:
                        roots.add(by_cited[path])
            continue
        seen.update(present)
        for match in _LINK.finditer(text):
            named = unquote(match["target"].strip("<>").split("#", 1)[0])
            target = ((root / name).parent / named).resolve()
            if not target.is_relative_to(evidence):
                continue
            rel = target.relative_to(evidence).as_posix()
            if rel == "README.md":
                continue  # The directory's guide is documentation, not retained evidence.
            if rel not in copies:
                findings.append(f"{name}: links {match['target']}, which is not a retained copy")
                continue
            seen.add(_cited(rel))
            if match["sha"]:
                compared += 1
                if match["sha"] != copies[rel]:
                    findings.append(f"{name}: records SHA256 {match['sha']} beside "
                                    f"{_cited(rel)}, not its retained copy's bytes")
                else:
                    roots.add(rel)
        findings.extend(f"{name}: cites {cited} without linking its retained copy"
                        for cited in present
                        if re.search(r"(?<!\[)" + re.escape(f"`{cited}`"), text))
    bundled, members, hashes = _bundles(root, names, data, roots)
    findings += bundled
    seen |= members
    compared += hashes
    findings.extend(f"{by_cited[cited]}: no tracked file cites {cited}"
                    for cited in sorted(set(by_cited) - seen))
    return findings, compared


@dataclass(frozen=True)
class Member:
    """One explicitly selected source, its retained name and stored encoding."""

    source: Path
    path: str
    encoding: str = "identity"


@dataclass(frozen=True)
class Bundle:
    """The published manifest and a citation for the caller's owning note."""

    manifest: Path
    sha256: str
    citation: str


def _portable(path: str) -> str:
    """A canonical member name with one spelling on both supported host platforms."""
    if (not path or "\\" in path or re.search(r"%[A-Za-z_][A-Za-z0-9_]*%", path)
            or PureWindowsPath(path).drive
            or PurePosixPath(path).is_absolute()
            or PurePosixPath(path).as_posix() != path
            or any(part in (".", "..") for part in path.split("/"))):
        raise ValueError(f"noncanonical, absolute or traversing retained name {path!r}")
    for part in path.split("/"):
        if (any(ord(char) < 32 or char in '<>:"|?*' for char in part)
                or part.endswith((".", " "))
                or unicodedata.normalize("NFC", part) != part
                or re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part)):
            raise ValueError(f"ambiguous retained name {path!r}")
    return path


def _no_links(path: Path) -> None:
    """Refuse symbolic links and Windows junctions in any path component."""
    for component in (path, *path.parents):
        if component.is_symlink() or component.is_junction():
            raise ValueError(f"symlink or junction in retained path {component}")


def _publish(pending: Path, destination: Path) -> None:
    """Atomically rename a directory without replacing even an empty destination.

    Windows rename already refuses an existing target. Linux rename alone replaces
    empty directories; renameat2's RENAME_NOREPLACE closes that publication race.
    Unsupported filesystems fail rather than falling back to a replacing rename.
    """
    if sys.platform == "win32":
        pending.rename(destination)
    elif sys.platform == "linux":
        try:
            operation = ctypes.CDLL(None, use_errno=True).renameat2
        except AttributeError as error:
            raise ValueError("the system C library provides no atomic nonreplacing rename") from error
        operation.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                              ctypes.c_char_p, ctypes.c_uint]
        operation.restype = ctypes.c_int
        if operation(-100, os.fsencode(pending), -100, os.fsencode(destination), 1):
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error), str(destination))
    else:
        raise ValueError(f"atomic new-bundle publication is unsupported on {sys.platform}")


def produce(root: Path, destination: str, members: list[Member], *,
            note: Path, label: str = "Retained evidence bundle") -> Bundle:
    """Copy a complete new bundle; never edit a note, stage files or replace evidence.

    A private sibling holds all member bytes and the manifest until the final atomic
    publication. An exception or interruption publishes no destination. Existing
    directories, symlinks, ambiguous names and nested manifests are refused.
    """
    _no_links(root.absolute())
    root = root.resolve(strict=True)
    base = root / EVIDENCE
    target = base / _portable(destination)
    _no_links(target)
    directory = base
    for part in target.relative_to(base).parts:
        if directory.is_dir():
            aliases = [child.name for child in directory.iterdir()
                       if child.name.casefold() == part.casefold() and child.name != part]
            if aliases:
                raise ValueError(f"ambiguous retained destination spelling {part!r}: {aliases}")
        directory /= part
    if target.exists():
        raise FileExistsError(f"retained destination already exists: {target}")
    note = note if note.is_absolute() else root / note
    if re.search(r"%[A-Za-z_][A-Za-z0-9_]*%", str(note)):
        raise ValueError(f"unexpanded environment variable in owning note: {note}")
    _no_links(note)
    note = note.resolve()
    if not note.is_relative_to(root) or note.is_relative_to(base):
        raise ValueError("the owning note must be outside retained evidence and inside the checkout")
    if note.suffix != ".md":
        raise ValueError("a generated Markdown citation requires an owning .md note")
    if not label.strip() or any(char in label for char in "[]\r\n"):
        raise ValueError("citation label must be nonempty single-line Markdown link text")
    if not members:
        raise ValueError("a retained bundle requires explicitly selected source files")
    selected: list[tuple[Member, Path]] = []
    names: set[str] = set()
    spellings: dict[str, str] = {}
    for member in members:
        path = _portable(member.path)
        folded = path.casefold()
        if any(part.casefold() == "manifest.json" for part in path.split("/")):
            raise ValueError("a selected member may not be a nested or replacement manifest")
        if (folded in names or any(folded.startswith(name + "/")
                                   or name.startswith(folded + "/") for name in names)):
            raise ValueError(f"colliding retained member names: {path}")
        names.add(folded)
        for count in range(1, len(path.split("/")) + 1):
            prefix = "/".join(path.split("/")[:count])
            prior = spellings.setdefault(prefix.casefold(), prefix)
            if prior != prefix:
                raise ValueError(f"ambiguous retained member spelling: {prior!r}, {prefix!r}")
        if member.encoding not in ("identity", "gzip"):
            raise ValueError(f"unknown member encoding {member.encoding!r}")
        source = member.source if member.source.is_absolute() else root / member.source
        if re.search(r"%[A-Za-z_][A-Za-z0-9_]*%", str(source)):
            raise ValueError(f"unexpanded environment variable in selected source: {source}")
        _no_links(source)
        if not source.is_file():
            raise ValueError(f"selected source is not a regular file: {source}")
        selected.append((member, source))
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".retain-", dir=target.parent) as staging:
        pending = Path(staging) / "bundle"
        pending.mkdir()
        identities: dict[str, object] = {}
        for member, source in selected:
            _no_links(source)
            blob = source.read_bytes()
            entry: dict[str, object] = {"path": member.path, "encoding": member.encoding}
            content = blob
            if member.encoding == "gzip":
                content = gzip.decompress(blob)
                entry.update(stored_sha256=hashlib.sha256(blob).hexdigest(),
                             stored_bytes=len(blob))
            entry.update(sha256=hashlib.sha256(content).hexdigest(), bytes=len(content))
            _member_bytes(blob, entry)
            output = pending / member.path
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(blob)
            identities[member.path] = entry
        manifest = pending / "manifest.json"
        receipts.write(manifest, {"files": identities})
        sha = receipts.digest(manifest)
        _no_links(target)
        _publish(pending, target)
    manifest = target / "manifest.json"
    relative = manifest.relative_to(note.parent, walk_up=True).as_posix()
    citation = f"[{label}]({quote(relative, safe='/.-')}), SHA256 `{sha}`."
    return Bundle(manifest, sha, citation)
