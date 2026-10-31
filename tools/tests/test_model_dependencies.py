# SPDX-License-Identifier: Apache-2.0
"""Authenticated archive contents govern offline model dependency reuse."""

import hashlib
import io
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos import model_corpus
from vos import model_dependencies as dependencies


def _archive(name: str, *, bad: str = "") -> bytes:
    contents = io.BytesIO()
    with tarfile.open(fileobj=contents, mode="w:gz") as bundle:
        if name == "riscv-tests":
            root = tarfile.TarInfo(".")
            root.type = tarfile.DIRTYPE
            bundle.addfile(root)
        entry = tarfile.TarInfo(f"{name}/include/header.h" if name != "riscv-tests"
                                else "rv64ui-p-add")
        entry.mode = 0o644
        data = b"original dependency bytes\n"
        entry.size = len(data)
        if bad == "escape":
            entry.name = "../outside"
        elif bad == "absolute":
            entry.name = "/outside"
        elif bad == "backslash":
            entry.name = "root\\outside"
        elif bad == "symlink":
            entry.type = tarfile.SYMTYPE
            entry.linkname = "outside"
        elif bad == "hardlink":
            entry.type = tarfile.LNKTYPE
            entry.linkname = "outside"
        elif bad == "fifo":
            entry.type = tarfile.FIFOTYPE
        bundle.addfile(entry, io.BytesIO(data) if entry.isfile() else None)
        if bad == "duplicate":
            bundle.addfile(entry, io.BytesIO(data))
        if bad in {"directory-alias", "alias-escape", "alias-cycle"}:
            alias = tarfile.TarInfo(f"{name}/compat/include")
            alias.type = tarfile.SYMTYPE
            alias.linkname = {"directory-alias": "../include", "alias-escape": "../../outside",
                              "alias-cycle": "include"}[bad]
            bundle.addfile(alias)
    return contents.getvalue()


def _fixture(root: Path, *, alias: bool = False) -> tuple[Path, Path, dict[str, bytes]]:
    model = root / "model"
    assets = {name: _archive(name) for name in ("cli11", "jsoncons", "asio", "riscv-tests")}
    if alias:
        assets["asio"] = _archive("asio", bad="directory-alias")
    for directory, algorithm in (("CLI11", "SHA256"), ("jsoncons", "SHA3_256"),
                                  ("asio", "SHA3_256")):
        name = directory.lower()
        declaration = model / "dependencies" / directory / "CMakeLists.txt"
        declaration.parent.mkdir(parents=True)
        digest = hashlib.new(algorithm.lower(), assets[name]).hexdigest()
        declaration.write_text(f"FetchContent_Declare({name}\n"
            f"  URL https://example.invalid/{name}.tar.gz\n"
            f"  URL_HASH {algorithm}={digest}\n)\n", encoding="utf-8")
    (model / "test").mkdir()
    digest = hashlib.sha256(assets["riscv-tests"]).hexdigest()
    (model / "test/CMakeLists.txt").write_text(
        'set(TEST_DOWNLOAD_URL "https://example.invalid/tests" CACHE STRING "Test base")\n'
        'set(TEST_DOWNLOAD_VERSION "2026-08-20" CACHE STRING "Test version")\n'
        f'set(TEST_DOWNLOAD_SHA256_2026-08-20_riscv-tests "{digest}")\n', encoding="utf-8")
    return model, root / "native/build", assets


def _download(assets: dict[str, bytes], dependency: dependencies.Dependency, archive: Path) -> None:
    archive.write_bytes(assets[dependency.name])


def _prepared(root: Path) -> tuple[Path, Path, dict[str, bytes], list[str]]:
    model, build, assets = _fixture(root)
    with patch.object(dependencies, "_download", side_effect=lambda item, path: _download(assets, item, path)):
        arguments = dependencies.prepare(model, build)
    return model, build, assets, arguments


def _refuses(model: Path, build: Path, message: str) -> None:
    with patch.object(dependencies, "_download", side_effect=AssertionError("offline fetched")):
        try:
            dependencies.prepare(model, build, offline=True)
        except OSError, ValueError, tarfile.TarError:
            return
    raise AssertionError(message)


def _round_trip() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-model-dependencies-") as name:
        model, build, _, arguments = _prepared(Path(name))
        with patch.object(dependencies, "_download", side_effect=AssertionError("warm build fetched")):
            ensure(dependencies.prepare(model, build, offline=True) == arguments,
                   "verified offline inputs changed their configure arguments")
        ensure("-DFETCHCONTENT_FULLY_DISCONNECTED=ON" in arguments
               and "-DVOS_MODEL_OFFLINE=ON" in arguments,
               "configuration was not disconnected from acquisition")
        ensure(sum(argument.startswith("-DFETCHCONTENT_SOURCE_DIR_") for argument in arguments) == 3,
               "not every source dependency has a verified override")
        pinned = model_corpus.pinned_suite(build, model)
        ensure("rv64ui-p-add" in pinned.files, "acquired test suite does not use the corpus owner")


def _offline_refusals() -> None:
    for defect in ("archive-missing", "archive-changed", "source-missing", "source-changed",
                   "coordinated-manifest", "extra-file", "extra-directory", "suite-changed"):
        with tempfile.TemporaryDirectory(prefix="vos-offline-dependency-") as name:
            root = Path(name)
            model, build, _, arguments = _prepared(root)
            home = build.parent / "model-dependencies"
            archive = next(home.glob("cli11-*.tar.gz"))
            source_arg = next(arg for arg in arguments if arg.startswith("-DFETCHCONTENT_SOURCE_DIR_CLI11="))
            source = Path(source_arg.split("=", 1)[1])
            header = source / "include/header.h"
            if defect == "archive-missing":
                archive.unlink()
            elif defect == "archive-changed":
                archive.write_bytes(b"not the pinned archive")
            elif defect == "source-missing":
                shutil.rmtree(source)
            elif defect in {"source-changed", "coordinated-manifest"}:
                before = header.stat()
                header.write_bytes(b"substituted source\n")
                os.utime(header, ns=(before.st_atime_ns, before.st_mtime_ns))
                if defect == "coordinated-manifest":
                    model_corpus.corpus_manifest(source).write_bytes(
                        model_corpus.corpus_listing(source, hashlib.sha256(archive.read_bytes()).hexdigest()))
            elif defect == "extra-file":
                (source / "unexpected").write_bytes(b"extra source")
            elif defect == "extra-directory":
                (source / "unexpected").mkdir()
            else:
                (build / "test/2026-08-20/riscv-tests/rv64ui-p-add").write_bytes(b"changed test")
            kept = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
            _refuses(model, build, f"offline {defect} input was accepted")
            ensure(all(path.is_file() and path.read_bytes() == value for path, value in kept.items()),
                   "offline refusal changed or deleted an existing input")


def _unsafe_archives() -> None:
    for defect in ("escape", "absolute", "backslash", "symlink", "hardlink", "fifo", "duplicate",
                   "alias-escape", "alias-cycle"):
        with tempfile.TemporaryDirectory(prefix="vos-dependency-archive-") as name:
            root = Path(name)
            model, build, assets = _fixture(root)
            assets["cli11"] = _archive("cli11", bad=defect)
            owner = model / "dependencies/CLI11/CMakeLists.txt"
            text = owner.read_text(encoding="utf-8")
            before = hashlib.sha256(_archive("cli11")).hexdigest()
            owner.write_text(text.replace(before, hashlib.sha256(assets["cli11"]).hexdigest()),
                             encoding="utf-8")
            with patch.object(dependencies, "_download", side_effect=lambda item, path, _assets=assets: _download(_assets, item, path)):
                try:
                    dependencies.prepare(model, build)
                except OSError, ValueError, tarfile.TarError:
                    ensure(not (root / "outside").exists(), "unsafe archive escaped materialization")
                    continue
            raise AssertionError(f"unsafe {defect} archive was accepted")


def _directory_aliases() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-dependency-alias-") as name:
        model, build, assets = _fixture(Path(name), alias=True)
        with patch.object(dependencies, "_download", side_effect=lambda item, path: _download(assets, item, path)):
            arguments = dependencies.prepare(model, build)
        source = Path(next(arg.split("=", 1)[1] for arg in arguments
                           if arg.startswith("-DFETCHCONTENT_SOURCE_DIR_ASIO=")))
        alias = source / "compat/include"
        ensure(alias.is_dir() and not alias.is_symlink(), "archive alias retained filesystem link authority")
        ensure((alias / "header.h").read_bytes() == (source / "include/header.h").read_bytes(),
               "archive directory alias lost its authenticated contents")
        dependencies.prepare(model, build, offline=True)
        for limit in (1, 40):
            with patch.object(dependencies, "_MAX_BYTES", limit):
                _refuses(model, build, "alias expansion escaped the materialization byte budget")


def _declaration_ownership() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-dependency-owners-") as name:
        model, _, _ = _fixture(Path(name))
        owner = model / "dependencies/CLI11/CMakeLists.txt"
        original = owner.read_text(encoding="utf-8")
        for changed in ("", original + original, original.replace("SHA256=", "SHA256=invalid"),
                        original.replace("https://", "http://")):
            owner.write_text(changed, encoding="utf-8")
            try:
                dependencies.dependencies(model)
            except ValueError:
                continue
            raise AssertionError("unreadable or ambiguous dependency pin accepted")


def _cmake_offline_refusal() -> None:
    executable = shutil.which("cmake")
    if executable is None:
        ensure(os.environ.get("GITHUB_ACTIONS") != "true", "hosted offline CMake control requires CMake")
        return
    owner = (TOOLS.parent / "model/test/CMakeLists.txt").read_text(encoding="utf-8")
    prefix = owner.split("function(setup_vector_test", 1)[0]
    for populated in (False, True):
        with tempfile.TemporaryDirectory(prefix="vos-offline-cmake-") as name:
            root = Path(name)
            suite = root / "riscv-tests"
            if populated:
                suite.mkdir()
                (suite / "retained").write_bytes(b"preserve me")
            script = root / "control.cmake"
            script.write_text(prefix + '\ndownload_riscv_tests("' + root.as_posix()
                              + '" "riscv-tests" "https://example.invalid/no-download")\n', encoding="utf-8")
            result = subprocess.run([executable, "-DVOS_MODEL_OFFLINE=ON", "-P", str(script)],
                                    cwd=root, capture_output=True, text=True, check=False, timeout=15)
            ensure(result.returncode != 0 and "Offline riscv-tests input" in result.stderr,
                   f"offline CMake did not refuse before download: {result.stderr}")
            ensure(not populated or (suite / "retained").read_bytes() == b"preserve me",
                   "offline CMake deleted an unverified suite")


def cases() -> list[Case]:
    return [Case("verified acquisition supports a fully offline configure", _round_trip),
            Case("offline archive and population substitutions refuse without repair", _offline_refusals),
            Case("dependency extraction rejects unsafe archive members", _unsafe_archives),
            Case("internal directory aliases become bounded ordinary copies", _directory_aliases),
            Case("CMake declarations remain the sole dependency pin owners", _declaration_ownership),
            Case("offline CMake refuses missing and invalid suites without deleting", _cmake_offline_refusal)]
