# SPDX-License-Identifier: Apache-2.0
"""Pinned RISC-V test-suite manifest verification and descriptor-verified copying.

Reads the pinned release and tarball SHA-256 digests from
[model/test/CMakeLists.txt](../../model/test/CMakeLists.txt), verifies extracted suites
against their `.manifest` listings, and copies verified regular files while preserving
descriptor identity `(st_dev, st_ino, st_size)`.
"""

import errno
import fnmatch
import hashlib
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path, PurePosixPath
from typing import NamedTuple, cast


def test_corpus_version(model_root: Path) -> str:
    """Return the `TEST_DOWNLOAD_VERSION` declared in `model_root/test/CMakeLists.txt`."""
    source = model_root / "test/CMakeLists.txt"
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as err:
        raise ValueError(f"cannot read the test corpus pin from {source}: {err}") from err
    versions = list(re.finditer(
        r'^set\(TEST_DOWNLOAD_VERSION "([0-9]{4}-[0-9]{2}-[0-9]{2})" '
        r'CACHE STRING "[^"\r\n]*"\)$', text, re.MULTILINE))
    if len(versions) != 1 or len(re.findall(r"^set\(TEST_DOWNLOAD_VERSION\b", text,
                                           re.MULTILINE)) != 1:
        raise ValueError(f"{source} must declare exactly one dated TEST_DOWNLOAD_VERSION")
    return cast("str", versions[0].group(1))


def test_corpus_digests(model_root: Path, version: str) -> dict[str, str]:
    """Return `{tarball_name: sha256}` declared for `version` in `model_root/test/CMakeLists.txt`."""
    source = model_root / "test/CMakeLists.txt"
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as err:
        raise ValueError(f"cannot read the test corpus digests from {source}: {err}") from err
    prefix = f"set(TEST_DOWNLOAD_SHA256_{version}_"
    declared = [line for line in text.splitlines() if line.startswith(prefix)]
    digests: dict[str, str] = {}
    for line in declared:
        found = re.fullmatch(rf'set\(TEST_DOWNLOAD_SHA256_{re.escape(version)}_'
                             r'([A-Za-z0-9-]+) "([0-9a-f]{64})"\)', line)
        if found is None or found.group(1) in digests:
            raise ValueError(f"{source} declares a malformed or repeated digest: {line}")
        digests[found.group(1)] = found.group(2)
    return digests


# Manifest suffix written beside each extracted suite by `download_riscv_tests` in
# [model/test/CMakeLists.txt](../../model/test/CMakeLists.txt).
CORPUS_MANIFEST_SUFFIX = ".manifest"


def corpus_manifest(suite: Path) -> Path:
    """Return the `.manifest` sibling path for `suite`."""
    return suite.with_name(suite.name + CORPUS_MANIFEST_SUFFIX)


def _unreadable(err: OSError) -> None:
    """Raise `os.walk` directory read errors rather than silently skipping subtrees."""
    raise err


class _CorpusEntry(NamedTuple):
    """Single suite entry discovered during directory traversal."""

    relative: str
    path: Path
    regular: bool


class _Hashed(NamedTuple):
    """Digest and descriptor identity `(device, inode, size)` of a regular file."""

    digest: str
    device: int
    inode: int
    size: int


class VerifiedSuite(NamedTuple):
    """Suite directory verified against its `.manifest` listing."""

    suite: Path
    manifest: bytes
    files: dict[str, _Hashed]


def _corpus_entries(suite: Path) -> list[_CorpusEntry]:
    """Return all entries under `suite` sorted by relative path bytes without opening files."""
    entries: list[tuple[bytes, _CorpusEntry]] = []
    for directory, dirs, files in os.walk(suite, onerror=_unreadable):
        for name in (*dirs, *files):
            path = Path(directory, name)
            if name in dirs and not path.is_symlink():
                continue
            relative = path.relative_to(suite).as_posix()
            if "\n" in relative or "\r" in relative:
                raise ValueError(f"{path}: a path a manifest line cannot hold")
            entries.append((_listed(relative), _CorpusEntry(
                relative, path, not path.is_symlink() and path.is_file())))
    return [entry for _, entry in sorted(entries, key=lambda pair: pair[0])]


def _listed(text: str) -> bytes:
    """Encode `text` as UTF-8 with `surrogateescape` so non-UTF-8 filenames round-trip."""
    return text.encode("utf-8", "surrogateescape")


def _listing_head(suite: Path, tarball_sha256: str) -> str:
    """Return the header line of `suite`'s manifest listing."""
    return f"tarball {suite.name}.tar.gz sha256 {tarball_sha256}\n"


def _hashed_listing(suite: Path, tarball_sha256: str,
                    entries: list[_CorpusEntry]) -> tuple[bytes, dict[str, _Hashed]]:
    """Render the manifest bytes for `entries` and collect `_Hashed` records by relative path."""
    lines = [_listing_head(suite, tarball_sha256)]
    files: dict[str, _Hashed] = {}
    for entry in entries:
        hashed = _regular_digest(entry.path) if entry.regular else None
        if hashed is None:
            lines.append(f"unhashed {entry.relative}\n")
        else:
            files[entry.relative] = hashed
            lines.append(f"{hashed.digest}  {entry.relative}\n")
    return _listed("".join(lines)), files


def corpus_listing(suite: Path, tarball_sha256: str) -> bytes:
    """Render the `download_riscv_tests` manifest bytes for `suite`."""
    return _hashed_listing(suite, tarball_sha256, _corpus_entries(suite))[0]


# Descriptor open flags that avoid FIFO blocking, symlink following, and terminal acquisition.
_REGULAR_ONLY = (os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_NOCTTY", 0) | getattr(os, "O_BINARY", 0))


def _open_regular(path: Path | str) -> int | None:
    """Open `path` as a read-only regular file, verifying `lstat`/`fstat` type and `(st_dev, st_ino)` agreement."""
    named = os.lstat(path)
    if not stat.S_ISREG(named.st_mode):
        return None
    try:
        fd = os.open(path, _REGULAR_ONLY)
    except OSError as err:
        if err.errno == errno.ELOOP and Path(path).is_symlink():
            return None
        raise
    try:
        held = os.fstat(fd)
    except BaseException:
        os.close(fd)
        raise
    if (not stat.S_ISREG(held.st_mode)
            or (held.st_dev, held.st_ino) != (named.st_dev, named.st_ino)):
        os.close(fd)
        return None
    return fd


def _regular_digest(path: Path) -> _Hashed | None:
    """Hash `path` through `_open_regular`, returning its `_Hashed` record or `None` if non-regular."""
    fd = _open_regular(path)
    if fd is None:
        return None
    with os.fdopen(fd, "rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        held = os.fstat(stream.fileno())
        return _Hashed(digest, held.st_dev, held.st_ino, stream.tell())


_HASHED_LINE = re.compile(rb"[0-9a-f]{64}  (.*)", re.DOTALL)


def _recorded_path(line: bytes) -> bytes:
    """Extract the relative path bytes from a `<sha256>  <path>` manifest line, or return `line` unchanged."""
    found = _HASHED_LINE.fullmatch(line)
    return line if found is None else cast("bytes", found.group(1))


def _non_regular(suite: Path) -> ValueError:
    """Build the `ValueError` for a suite containing a symlink or non-regular entry."""
    return ValueError(f"{suite} holds a symbolic link or other non-regular entry, which "
                      "no manifest configure writes holds; configure downloads it again")


def _disagreement(suite: Path, manifest: Path, held: list[bytes], kept: list[bytes],
                  found: list[bytes], *, cut: bool = False) -> ValueError:
    """Build the `ValueError` reporting the first line where `kept` and `found` diverge."""
    where = next((i for i, (a, b) in enumerate(zip(kept, found, strict=False)) if a != b),
                 min(len(kept), len(found)))
    manifest_line, tree_line = (
        lines[where].decode("utf-8", "replace") if where < len(lines) else "<end>"
        for lines in (held, found))
    unread = ", read no further," if cut and where == len(held) - 1 else ""
    return ValueError(f"{suite} disagrees with {manifest.name} at line {where + 1}: the "
                      f"manifest has {manifest_line!r}{unread} and the tree {tree_line!r}; "
                      "configure downloads it again")


def verify_test_corpus(suite: Path, tarball_sha256: str) -> VerifiedSuite:
    """Verify `suite` against its sibling `.manifest` and `tarball_sha256`, returning a `VerifiedSuite`.

    Rejects non-regular manifest or tree entries before hashing, bounds the manifest
    read to the expected byte length of the walked path listing, and verifies every
    listed file's SHA-256 through `_open_regular`.
    """
    manifest = corpus_manifest(suite)
    if suite.is_symlink() or not suite.is_dir():
        raise ValueError(f"{suite} is not an extracted suite directory")
    try:
        fd = _open_regular(manifest)
    except FileNotFoundError:
        raise ValueError(f"{suite} has no {manifest.name}, so no configure that verified "
                         "its tarball extracted it; configure downloads it again") from None
    except OSError as err:
        raise ValueError(f"cannot read {manifest}: {err}") from err
    if fd is None:
        raise ValueError(f"{manifest} is not a regular file, which no configure writes; "
                         f"configure downloads {suite.name} again")
    with os.fdopen(fd, "rb") as handle:
        try:
            entries = _corpus_entries(suite)
        except OSError as err:
            raise ValueError(f"cannot list {suite}: {err}") from err
        if not all(entry.regular for entry in entries):
            raise _non_regular(suite)
        head = _listed(_listing_head(suite, tarball_sha256))
        paths = [_listed(entry.relative) for entry in entries]
        length = len(head) + sum(64 + 2 + len(path) + 1 for path in paths)
        try:
            recorded = handle.read(length + 1)
        except OSError as err:
            raise ValueError(f"cannot read {manifest}: {err}") from err
    held = recorded.splitlines()
    kept = [*held[:1], *(_recorded_path(line) for line in held[1:])]
    walked = [head.rstrip(b"\n"), *paths]
    if kept != walked:
        raise _disagreement(suite, manifest, held, kept, walked, cut=len(recorded) > length)
    try:
        rendered, files = _hashed_listing(suite, tarball_sha256, entries)
    except OSError as err:
        raise ValueError(f"cannot list {suite}: {err}") from err
    if b"\nunhashed " in rendered:
        raise _non_regular(suite)
    if recorded != rendered:
        raise _disagreement(suite, manifest, held, held, rendered.splitlines())
    return VerifiedSuite(suite, recorded, files)


def pinned_suite(directory: Path, model_root: Path) -> VerifiedSuite:
    """Verify and return the `riscv-tests` suite at the release pinned in `model_root`."""
    version = test_corpus_version(model_root)
    suite = directory / "test" / version / "riscv-tests"
    if not suite.is_dir():
        raise ValueError(f"no downloaded riscv-tests at the pinned release: {suite}")
    digest = test_corpus_digests(model_root, version).get("riscv-tests")
    if digest is None:
        raise ValueError(f"the model records no riscv-tests digest at release {version}")
    return verify_test_corpus(suite, digest)


def verified_inputs(verified: VerifiedSuite, pattern: str) -> dict[Path, str]:
    """Return `{path: sha256}` for top-level non-`.dump` files in `verified` matching `pattern`."""
    chosen = {verified.suite / relative: hashed.digest
              for relative, hashed in verified.files.items()
              if "/" not in relative and fnmatch.fnmatchcase(relative, pattern)
              and PurePosixPath(relative).suffix != ".dump"}
    return dict(sorted(chosen.items()))


def sweep_corpus(directory: Path, model_root: Path, xlen: str = "64") -> dict[Path, str]:
    """Return `{path: sha256}` for the verified `rv{xlen}*-p-*` ELF suite under `directory`."""
    verified = pinned_suite(directory, model_root)
    elves = verified_inputs(verified, f"rv{xlen}*-p-*")
    if not elves:
        raise ValueError(f"no rv{xlen} physical-variant ELF inputs under {verified.suite}")
    return elves


def sweep_inputs(directory: Path, model_root: Path, xlen: str = "64") -> list[Path]:
    """Return the sorted paths of the verified `rv{xlen}*-p-*` ELF suite under `directory`."""
    return list(sweep_corpus(directory, model_root, xlen))


def copy_verified_suite(suite: Path, into: Path, digest: str) -> None:
    """Verify `suite` against `digest`, copy its verified files and manifest into a staging directory, re-verify, and rename to `into`."""
    verified = verify_test_corpus(suite, digest)
    into.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{into.name}-seed-", dir=into.parent))
    try:
        copy = staging / into.name
        copy.mkdir()
        for relative, held in verified.files.items():
            (copy / relative).parent.mkdir(parents=True, exist_ok=True)
            _copy_regular_file(suite / relative, copy / relative, held)
        corpus_manifest(copy).write_bytes(verified.manifest)
        verify_test_corpus(copy, digest)
        copy.rename(into)
        corpus_manifest(copy).replace(corpus_manifest(into))
    finally:
        shutil.rmtree(staging, ignore_errors=True)


_COPY_CHUNK = 1 << 20


def _copy_regular_file(source: Path, destination: Path, verified: _Hashed) -> None:
    """Copy `source` to `destination` through `_open_regular`, enforcing `verified`'s `(device, inode, size)`."""
    fd = _open_regular(source)
    if fd is None:
        raise ValueError(f"{source} is not a regular file; the donor changed after it "
                         "verified")
    with os.fdopen(fd, "rb", buffering=0) as reader:
        held = os.fstat(reader.fileno())
        if (held.st_dev, held.st_ino, held.st_size) != (verified.device, verified.inode,
                                                         verified.size):
            raise ValueError(f"{source} is not the file that verified; the donor changed "
                             "after it verified")
        copied = 0
        with destination.open("xb") as writer:
            while copied <= verified.size and (
                    chunk := reader.read(min(verified.size + 1 - copied, _COPY_CHUNK))):
                writer.write(chunk)
                copied += len(chunk)
    if copied != verified.size:
        destination.unlink()
        raise ValueError(f"{source} is {'longer' if copied > verified.size else 'shorter'} "
                         f"than the {verified.size} bytes that verified; the donor changed "
                         "after it verified")
    destination.chmod(stat.S_IMODE(held.st_mode))
    os.utime(destination, ns=(held.st_atime_ns, held.st_mtime_ns))
