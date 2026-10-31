# SPDX-License-Identifier: Apache-2.0
"""Authenticate and materialize the model's declared inputs before CMake starts.

The CMake declarations own every URL and archive digest. A retained archive is
authenticated again and supplies the expected file population on each reuse;
an editable extracted-tree manifest cannot authorize substituted source bytes.
Offline preparation never downloads, repairs or deletes an existing population.
"""

import hashlib
import os
import re
import shutil
import stat
import tarfile
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import IO

from filelock import FileLock

from vos import model_corpus, receipts


@dataclass(frozen=True, slots=True)
class Dependency:
    """One archive selected by its authored CMake declaration."""

    name: str
    url: str
    algorithm: str
    digest: str
    source_root: bool


@dataclass(frozen=True, slots=True)
class Population:
    """The authenticated tar members and their complete normalized population."""

    members: list[tarfile.TarInfo]
    prefix: str
    directories: frozenset[str]
    files: dict[str, str]
    aliases: dict[str, str]


_DEPENDENCIES = ("CLI11", "jsoncons", "asio")
_UNSAFE_NAME = re.compile(r"[\\;:\r\n]")
_MAX_MEMBERS = 200_000
_MAX_BYTES = 2 * 1024 * 1024 * 1024


def _one(pattern: str, text: str, owner: Path, label: str) -> re.Match[str]:
    found = list(re.finditer(pattern, text, re.MULTILINE))
    if len(found) != 1:
        raise ValueError(f"{owner}: expected exactly one supported {label}")
    return found[0]


def dependencies(model_root: Path) -> tuple[Dependency, ...]:
    """Read the actual FetchContent declarations and canonical test-suite pin."""
    selected = []
    for directory in _DEPENDENCIES:
        owner = model_root / "dependencies" / directory / "CMakeLists.txt"
        text = owner.read_text(encoding="utf-8")
        declaration = _one(r"FetchContent_Declare\(\s*([A-Za-z0-9_]+)\s+([\s\S]*?)\n\)",
                           text, owner, "FetchContent declaration")
        name = declaration[1]
        if name != directory.lower():
            raise ValueError(f"{owner}: unexpected dependency {name}")
        body = declaration[2]
        if (len(re.findall(r"^\s*URL\s", body, re.MULTILINE)) != 1
                or len(re.findall(r"^\s*URL_HASH\s", body, re.MULTILINE)) != 1
                or len(re.findall(r"\bFetchContent_Declare\s*\(", text)) != 1):
            raise ValueError(f"{owner}: ambiguous FetchContent input declaration")
        url = _one(r'^\s*URL\s+"?(https://[^\s";]+)"?\s*$', body, owner, "HTTPS URL")[1]
        pinned = _one(r"^\s*URL_HASH\s+(SHA256|SHA3_256)=([0-9a-f]{64})\s*$",
                      body, owner, "archive hash")
        selected.append(Dependency(name, url, pinned[1].lower(), pinned[2], True))
    owner = model_root / "test/CMakeLists.txt"
    text = owner.read_text(encoding="utf-8")
    base = _one(r'^set\(TEST_DOWNLOAD_URL "(https://[^";\s]+)" CACHE STRING "[^"\r\n]*"\)$',
                text, owner, "test download URL")[1]
    version = model_corpus.test_corpus_version(model_root)
    digests = model_corpus.test_corpus_digests(model_root, version)
    if "riscv-tests" not in digests:
        raise ValueError(f"{owner}: canonical riscv-tests digest is missing")
    selected.append(Dependency("riscv-tests", f"{base}/{version}/riscv-tests.tar.gz",
                               "sha256", digests["riscv-tests"], False))
    return tuple(selected)


def _open_regular(path: Path) -> IO[bytes]:
    named = path.lstat()
    if not stat.S_ISREG(named.st_mode):
        raise ValueError(f"{path}: dependency input must be a regular file")
    flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
             | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOCTTY", 0))
    descriptor = os.open(path, flags)
    try:
        _held_identity(path, named, descriptor)
        return os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise


def _held_identity(path: Path, named: os.stat_result, descriptor: int) -> None:
    held = os.fstat(descriptor)
    if (not stat.S_ISREG(held.st_mode)
            or (named.st_dev, named.st_ino) != (held.st_dev, held.st_ino)):
        raise ValueError(f"{path}: dependency input changed during opening")


def _stream_digest(stream: IO[bytes], algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    while block := stream.read(1024 * 1024):
        digest.update(block)
    return digest.hexdigest()


def _digest(path: Path, algorithm: str) -> str:
    with _open_regular(path) as stream:
        return _stream_digest(stream, algorithm)


def _download(dependency: Dependency, archive: Path) -> None:
    import urllib.request  # noqa: PLC0415 (offline acquisition needs no HTTP stack)

    with receipts.atomic_path(archive) as pending:
        with (urllib.request.urlopen(dependency.url, timeout=120) as response,  # noqa: S310
              pending.open("wb") as output):
            shutil.copyfileobj(response, output)
        if _digest(pending, dependency.algorithm) != dependency.digest:
            raise ValueError(f"{dependency.url}: dependency archive hash mismatch")


def _population(bundle: tarfile.TarFile, dependency: Dependency) -> Population:
    members = []
    roots: set[str] = set()
    total = 0
    for member in bundle:
        parts = PurePosixPath(member.name).parts
        if not parts and member.isdir() and not dependency.source_root:
            continue
        if (not parts or PurePosixPath(member.name).is_absolute() or ".." in parts
                or _UNSAFE_NAME.search(member.name)
                or not (member.isdir() or member.isfile()
                        or (dependency.source_root and member.issym()))):
            raise ValueError(f"{dependency.name}: unsafe archive member {member.name!r}")
        total += member.size
        if len(members) >= _MAX_MEMBERS or total > _MAX_BYTES or member.size < 0:
            raise ValueError(f"{dependency.name}: archive exceeds materialization limits")
        roots.add(parts[0])
        members.append(member)
    if not members or (dependency.source_root and len(roots) != 1):
        raise ValueError(f"{dependency.name}: archive has no unique source root")
    prefix = next(iter(roots)) if dependency.source_root else ""
    directories: set[str] = set()
    files: dict[str, str] = {}
    sizes: dict[str, int] = {}
    aliases: dict[str, str] = {}
    kinds: dict[str, bool] = {}
    for member in members:
        parts = PurePosixPath(member.name).parts[1:] if prefix else PurePosixPath(member.name).parts
        relative = PurePosixPath(*parts).as_posix() if parts else ""
        if not relative:
            if not member.isdir():
                raise ValueError(f"{dependency.name}: source root is not a directory")
            continue
        if relative in kinds:
            raise ValueError(f"{dependency.name}: repeated archive member {relative}")
        kinds[relative] = member.isdir()
        if member.issym():
            aliases[relative] = _alias_target(relative, member.linkname, dependency.name)
        elif member.isdir():
            directories.add(relative)
        else:
            contents = bundle.extractfile(member)
            if contents is None:
                raise ValueError(f"{dependency.name}: unreadable archive member {relative}")
            with contents:
                files[relative] = _stream_digest(contents, "sha256")
                sizes[relative] = member.size
        directories.update(parent.as_posix() for parent in PurePosixPath(relative).parents
                           if parent.as_posix() != ".")
    if not files or any(path in files for path in directories):
        raise ValueError(f"{dependency.name}: empty or conflicting archive population")
    original_files = dict(files)
    original_directories = frozenset(directories)
    for alias, target in aliases.items():
        if (target not in original_directories or alias in original_directories
                or any(path == target or path.startswith(target + "/") for path in aliases)
                or any(path != alias and (path.startswith(alias + "/") or alias.startswith(path + "/"))
                       for path in aliases)):
            raise ValueError(f"{dependency.name}: alias is not an independent internal directory: {alias}")
        directories.add(alias)
        directories.update(alias + path[len(target):] for path in original_directories
                           if path.startswith(target + "/"))
        for path, digest in original_files.items():
            if path.startswith(target + "/"):
                copied = alias + path[len(target):]
                files[copied] = digest
                sizes[copied] = sizes[path]
        if len(files) + len(directories) > _MAX_MEMBERS or sum(sizes.values()) > _MAX_BYTES:
            raise ValueError(f"{dependency.name}: aliases exceed materialization limits")
    return Population([member for member in members if not member.issym()], prefix,
                      frozenset(directories), files, aliases)


def _alias_target(relative: str, target: str, name: str) -> str:
    if not target or PurePosixPath(target).is_absolute() or _UNSAFE_NAME.search(target):
        raise ValueError(f"{name}: unsafe archive alias target {target!r}")
    parts = list(PurePosixPath(relative).parent.parts)
    for part in PurePosixPath(target).parts:
        if part == "..":
            if not parts:
                raise ValueError(f"{name}: archive alias escapes its source root")
            parts.pop()
        else:
            parts.append(part)
    return PurePosixPath(*parts).as_posix()


@contextmanager
def _authenticated_archive(archive: Path, dependency: Dependency) -> Generator[tuple[tarfile.TarFile, str]]:
    # Parse and extract the very bytes that authenticated. A retained file can
    # change in place while it is open, so read it into a private disposable
    # snapshot before hashing rather than reopening a path after verification.
    with _open_regular(archive) as original, tempfile.TemporaryFile(dir=archive.parent) as snapshot:
        shutil.copyfileobj(original, snapshot)
        snapshot.seek(0)
        if _stream_digest(snapshot, dependency.algorithm) != dependency.digest:
            raise ValueError(f"{archive}: cached dependency archive hash mismatch")
        snapshot.seek(0)
        archive_sha256 = _stream_digest(snapshot, "sha256")
        snapshot.seek(0)
        with tarfile.open(fileobj=snapshot, mode="r:gz") as bundle:
            yield bundle, archive_sha256


def _manifest(target: Path, population: Population, archive_sha256: str) -> bytes:
    lines = [f"tarball {target.name}.tar.gz sha256 {archive_sha256}\n"]
    lines.extend(f"{population.files[name]}  {name}\n"
                 for name in sorted(population.files, key=lambda item: item.encode("utf-8")))
    return "".join(lines).encode("utf-8")


def _verify(target: Path, population: Population, archive_sha256: str) -> None:
    if target.is_symlink() or not target.is_dir():
        raise ValueError(f"{target}: dependency source is not an ordinary directory")
    verified = model_corpus.verify_test_corpus(target, archive_sha256)
    if verified.manifest != _manifest(target, population, archive_sha256):
        raise ValueError(f"{target}: extracted population differs from authenticated archive")
    directories = set()
    for directory, children, _ in os.walk(target, onerror=_unreadable):
        for child in children:
            path = Path(directory, child)
            if path.is_symlink() or not path.is_dir():
                raise ValueError(f"{path}: dependency directory is not ordinary")
            directories.add(path.relative_to(target).as_posix())
    if directories != population.directories:
        raise ValueError(f"{target}: dependency directory population differs from archive")


def _unreadable(error: OSError) -> None:
    raise error


def _ordinary_directory(path: Path, *, create: bool) -> None:
    # Retained native cache/build ancestors must not redirect publication through
    # a symbolic link or Windows junction into an unrelated directory.
    for directory in reversed((path, *path.parents)):
        try:
            found = directory.lstat()
        except FileNotFoundError:
            if not create:
                return
            directory.mkdir()
            found = directory.lstat()
        if not stat.S_ISDIR(found.st_mode) or directory.is_symlink() or directory.is_junction():
            raise ValueError(f"{directory}: dependency directory must not redirect through a link")


def _materialize(archive: Path, dependency: Dependency, target: Path) -> None:
    _ordinary_directory(target.parent, create=False)
    with _authenticated_archive(archive, dependency) as (bundle, archive_sha256):
        population = _population(bundle, dependency)
        if target.exists() or target.is_symlink():
            _verify(target, population, archive_sha256)
            return
        _ordinary_directory(target.parent, create=True)
        with tempfile.TemporaryDirectory(prefix=".model-dependency-", dir=target.parent) as name:
            staging = Path(name)
            unpacked = staging / "unpacked"
            unpacked.mkdir()
            bundle.extractall(unpacked, members=population.members, filter="data")
            staged = unpacked / population.prefix if population.prefix else unpacked
            for alias, target_name in population.aliases.items():
                destination = staged / alias
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(staged / target_name, destination)
            manifest = model_corpus.corpus_manifest(staged)
            # A temporary name must not change the tarball-name line.
            manifest.write_bytes(_manifest(target, population, archive_sha256))
            staged.rename(target)
            manifest.replace(model_corpus.corpus_manifest(target))
            _verify(target, population, archive_sha256)


def prepare(model_root: Path, build_dir: Path, *, offline: bool = False,
            cache_root: Path | None = None) -> list[str]:
    """Return offline CMake arguments after authenticating every selected input.

    Callers hold their build-lane lock. The acquisition cache has its own lock so
    independently selected build profiles can safely share an explicitly named cache.
    """
    selected = dependencies(model_root)
    home = cache_root if cache_root is not None else build_dir.parent / "model-dependencies"
    home = home.absolute()
    build_dir = build_dir.absolute()
    if (re.search(r"[;\r\n]", str(home) + str(build_dir))
            or (os.name != "nt" and _UNSAFE_NAME.search(str(home) + str(build_dir)))):
        raise ValueError(f"{home}: unsupported dependency cache path")
    if ".." in home.parts or ".." in build_dir.parts:
        raise ValueError("dependency cache and build paths must not contain parent traversal")
    _ordinary_directory(home, create=True)
    arguments = ["-DFETCHCONTENT_FULLY_DISCONNECTED=ON", "-DVOS_MODEL_OFFLINE=ON"]
    with FileLock(home / ".prepare.lock", timeout=180, fallback_to_soft=False,
                  preserve_lock_file=True):
        for dependency in selected:
            archive = home / f"{dependency.name}-{dependency.algorithm}-{dependency.digest}.tar.gz"
            if not archive.exists() and not archive.is_symlink():
                if offline:
                    raise ValueError(f"{archive}: dependency archive is missing in offline mode")
                _download(dependency, archive)
            target = (home / "sources" / f"{dependency.name}-{dependency.digest}"
                      if dependency.source_root else build_dir / "test" /
                      model_corpus.test_corpus_version(model_root) / dependency.name)
            try:
                _materialize(archive, dependency, target)
            except tarfile.TarError as err:
                raise ValueError(f"{archive}: malformed authenticated archive: {err}") from err
            if dependency.source_root:
                arguments.append(f"-DFETCHCONTENT_SOURCE_DIR_{dependency.name.upper()}={target}")
    return arguments
