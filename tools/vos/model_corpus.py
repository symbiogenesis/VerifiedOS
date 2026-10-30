# SPDX-License-Identifier: Apache-2.0
"""Pinned RISC-V test suites, verified snapshots and safe copies.

Manifest bytes follow the model's download declaration. Every consumer selects
files from the same verified snapshot; copying retains that snapshot's identity
until the destination itself verifies. Build and donor policy belongs to callers.
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
    """The release declared by the model, shared by configure and corpus consumers."""
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
    """The SHA-256 the model records for each tarball of one release, by tarball name.

    Fail-closed like `test_corpus_version`: a digest line of the release that is not a
    well-formed 64-hex declaration, or a tarball declared twice, is refused rather than
    passed over, since a suite whose digest went unread would go unverified.
    """
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


# The manifest `download_riscv_tests` in model/test/CMakeLists.txt writes beside a
# suite it has just extracted from a tarball whose SHA-256 it verified, and holds that
# suite to on every configure, downloading again a suite that disagrees. The listing is
# the tarball's recorded digest, then each file's SHA-256 and path relative to the
# suite, sorted by the path's bytes; a symbolic link is listed unhashed, every name
# holding `;` or `\` leaves at least one unhashed line, and no written manifest holds
# an unhashed line. `corpus_listing` renders that listing for the readers that do not
# configure: the seeding that copies a suite into a new lane, and the sweep and
# trace-diff that read one. It walks the tree rather than globbing it and lists every
# non-regular entry unhashed without reading it, hashing a file only through a
# descriptor that is a regular file, so the sweep and trace-diff also refuse what
# configure does not tell apart: a FIFO or device node, which the verified tarball
# does not contain.
# A build's receipt reads the corpus through `pinned_suite` too, so a disagreement
# between the two renderings fails the first build that records its evidence rather
# than passing unseen.
CORPUS_MANIFEST_SUFFIX = ".manifest"


def corpus_manifest(suite: Path) -> Path:
    """Where the manifest of an extracted suite lives: beside it, not inside it."""
    return suite.with_name(suite.name + CORPUS_MANIFEST_SUFFIX)


def _unreadable(err: OSError) -> None:
    """`os.walk` passes over a directory it cannot read unless told otherwise, and a
    listing that skipped one would no longer describe the whole tree."""
    raise err


class _CorpusEntry(NamedTuple):
    """One entry of a suite as the walk finds it, before any file is read."""

    relative: str  # the path relative to the suite, as a listing line spells it
    path: Path
    regular: bool  # whether the name, its final link not followed, is a regular file


class _Hashed(NamedTuple):
    """A regular file as one read of it found it."""

    digest: str  # the SHA-256 of the bytes read
    device: int  # the device and inode of the descriptor they were read through
    inode: int
    size: int  # how many bytes were read, to the end of the file


class VerifiedSuite(NamedTuple):
    """A suite as `verify_test_corpus` found it agreeing with its manifest."""

    suite: Path
    manifest: bytes  # the manifest's bytes, as they were read and compared
    files: dict[str, _Hashed]  # each file by its listed path, in the listing's order


def _corpus_entries(suite: Path) -> list[_CorpusEntry]:
    """Every entry of `suite` a listing has a line for, sorted by its relative path's
    bytes, as the walk finds them: a file, a symbolic link, or a node of another kind,
    and no file opened."""
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
    """A listing's text as its bytes: a name that is not UTF-8 keeps the bytes it has."""
    return text.encode("utf-8", "surrogateescape")


def _listing_head(suite: Path, tarball_sha256: str) -> str:
    """The first line of `suite`'s listing, which records its tarball's digest."""
    return f"tarball {suite.name}.tar.gz sha256 {tarball_sha256}\n"


def _hashed_listing(suite: Path, tarball_sha256: str,
                    entries: list[_CorpusEntry]) -> tuple[bytes, dict[str, _Hashed]]:
    """The listing of `entries`, reading each file only through `_regular_digest`, and
    what that read found of each file it hashed, by listed path."""
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
    """The listing `download_riscv_tests` records for `suite`, rendered from the tree."""
    return _hashed_listing(suite, tarball_sha256, _corpus_entries(suite))[0]


# How a corpus file is opened for reading once its name has been found to be a regular
# file: without waiting, without following a final link and without taking a terminal
# as the controlling one, so an entry replaced by another kind since is neither waited
# on nor followed nor made this process's terminal, and its descriptor refuses it.
# Opening a FIFO for reading otherwise waits for a writer that never comes, and a
# character device such as `/dev/zero`, or a link to one, is read without end. What
# opening a device node does to the device the flags do not prevent, so the name is
# asked first, and only a device put in its place between that answer and the open is
# opened at all. win32 has none of these flags, so there the name's and the opened
# descriptor's kinds decide alone; `O_BINARY` keeps its reads byte-exact.
_REGULAR_ONLY = (os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_NOCTTY", 0) | getattr(os, "O_BINARY", 0))


def _open_regular(path: Path | str) -> int | None:
    """A read descriptor on `path` when it is a regular file, and None when it is not.

    The name is asked first, without following a final link, and nothing it reports as
    another kind is opened, since opening a device node can act on the device. The
    opened descriptor must then be a regular file and the very file the name reported,
    by device and inode, so an entry replaced between the two is refused as well. An
    `OSError` from either question, `FileNotFoundError` among them, is the caller's.
    """
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
    """The SHA-256 of `path`, read through a descriptor that is a regular file, with that
    descriptor's device and inode and the length read, and None when `_open_regular`
    finds it is not one: an entry replaced after the listing's check by name is listed
    unhashed rather than waited on or read without end."""
    fd = _open_regular(path)
    if fd is None:
        return None
    with os.fdopen(fd, "rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
        held = os.fstat(stream.fileno())
        return _Hashed(digest, held.st_dev, held.st_ino, stream.tell())


# A hashed listing line, `<sha256>  <path>`, and the path it records.
_HASHED_LINE = re.compile(rb"[0-9a-f]{64}  (.*)", re.DOTALL)


def _recorded_path(line: bytes) -> bytes:
    """The path a manifest's hashed line records, and a line of any other shape whole,
    which then names no entry of the tree."""
    found = _HASHED_LINE.fullmatch(line)
    return line if found is None else cast("bytes", found.group(1))


def _non_regular(suite: Path) -> ValueError:
    """The refusal of a suite holding an entry that is not a regular file."""
    return ValueError(f"{suite} holds a symbolic link or other non-regular entry, which "
                      "no manifest configure writes holds; configure downloads it again")


def _disagreement(suite: Path, manifest: Path, held: list[bytes], kept: list[bytes],
                  found: list[bytes], *, cut: bool = False) -> ValueError:
    """The refusal at the first line where `kept`, the manifest's lines `held` as they
    are compared, differs from `found`, the tree's. `cut` says the read stopped at its
    bound rather than at the manifest's end, so the last line held is only as much of
    that line as was read."""
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
    """Refuse a suite unless it is what its manifest records for this tarball digest,
    and answer what agreed: the manifest's bytes, and each file's SHA-256 with the
    device and inode of the descriptor it was hashed through and the length hashed.

    The manifest is read only when its name and its opened descriptor are one regular
    file, which is what configure writes, so a manifest standing as a FIFO, a device
    node or a symbolic link is refused rather than waited on or read without end,
    whichever reader asks: the donor seeding, the sweep, trace-diff and the build
    receipt.

    The tree is walked before any file of it is read. An entry that is not a regular
    file is refused, and then the walked paths are held to the ones the manifest
    records, so an entry it does not list, or a listed one that is gone, is refused
    before a file is hashed. No more of the manifest is read than the listing of those
    paths is long and one byte, so a regular manifest longer than that, a sparse one
    among them, disagrees rather than being read until memory runs out. Only then is
    each file hashed and the whole listing compared. A file under a listed name is
    hashed whatever its length, since the listing records no sizes: an oversized one,
    a sparse one among them, is read in full before it is found to disagree. That
    residual is the listing format's, which `riscv_tests_listing` in
    model/test/CMakeLists.txt owns.

    The answer is what a reader after the verification goes by, rather than the tree's
    names, which can change once it returns: the seeding copies only the files it
    lists, each while it is still the file that verified, and writes their manifest
    from the bytes that verified; the sweep, trace-diff and the build receipt choose
    their inputs from the files it lists, and the receipt records the digests it read.
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
        # each file's line is its digest in hex, two spaces, its path and a newline
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
    """Select the declared release even when older or newer donor caches coexist, and
    only a suite that is the verified extraction its manifest records, as it verified."""
    version = test_corpus_version(model_root)
    suite = directory / "test" / version / "riscv-tests"
    if not suite.is_dir():
        raise ValueError(f"no downloaded riscv-tests at the pinned release: {suite}")
    digest = test_corpus_digests(model_root, version).get("riscv-tests")
    if digest is None:
        raise ValueError(f"the model records no riscv-tests digest at release {version}")
    return verify_test_corpus(suite, digest)


def verified_inputs(verified: VerifiedSuite, pattern: str) -> dict[Path, str]:
    """The files at the top of `verified`'s suite whose names match the glob `pattern`,
    other than the `.dump` disassemblies beside them, in path order, each with the
    SHA-256 its verification read. They are chosen from what verified rather than from
    the tree as it stands, so an entry added after the verification is not among them,
    and none is read again to choose it."""
    chosen = {verified.suite / relative: hashed.digest
              for relative, hashed in verified.files.items()
              if "/" not in relative and fnmatch.fnmatchcase(relative, pattern)
              and PurePosixPath(relative).suffix != ".dump"}
    return dict(sorted(chosen.items()))


def sweep_corpus(directory: Path, model_root: Path, xlen: str = "64") -> dict[Path, str]:
    """The nonempty physical-variant suite selected by both the runner and its receipt,
    each input with the SHA-256 its suite's verification read."""
    verified = pinned_suite(directory, model_root)
    elves = verified_inputs(verified, f"rv{xlen}*-p-*")
    if not elves:
        raise ValueError(f"no rv{xlen} physical-variant ELF inputs under {verified.suite}")
    return elves


def sweep_inputs(directory: Path, model_root: Path, xlen: str = "64") -> list[Path]:
    """The nonempty physical-variant suite selected by both the runner and its receipt."""
    return list(sweep_corpus(directory, model_root, xlen))


def copy_verified_suite(suite: Path, into: Path, digest: str) -> None:
    """Copy `suite` and its manifest to `into`, publishing only a copy that verifies.

    The donor is verified before it is copied as well as after. A FIFO is waited on and
    a character device such as a `/dev/zero` node is read without end, so a donor
    holding either would stall the command standing the lane up; the listing the
    verification renders reads no non-regular entry and refuses a suite holding one.
    The donor can still change between that verification and the copy, so the copy is
    made from what the verification answered rather than from the donor's names: its
    manifest is written from the bytes that verified, and only the files that verified
    are copied, each by `_copy_regular_file` and only while it is the file that
    verified, so an entry added since is not copied and one replaced or grown since is
    refused before more of it is read than verified. The copy is verified before it is
    published.
    """
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


# How much of a donor's file one read of the seeding's copy asks for.
_COPY_CHUNK = 1 << 20


def _copy_regular_file(source: Path, destination: Path, verified: _Hashed) -> None:
    """Copy `source` to the new file `destination` as `copy2` would, reading it only
    while it is the regular file `verified` records.

    The descriptor read from is the one whose kind `_open_regular` checked, so a FIFO is
    not waited on and a device is not read. It must also be the very file that verified,
    by device, inode and length, so a donor entry replaced or resized since is refused
    before any of it is read, and the read stops one byte past the verified length, so
    a file grown after its length was asked is refused rather than read to its end.
    What is refused raises `ValueError` and leaves no destination. Mode and times are
    kept from the descriptor, as `copy2` keeps them.
    """
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
