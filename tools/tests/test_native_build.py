# SPDX-License-Identifier: Apache-2.0
"""Native reuse binds actual configured tools and content, including old mtimes."""

import copy
import json
import os
import subprocess
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import native_build as subject


class Fixture:
    """A tiny configured model whose discovery subprocesses have fixed answers."""

    __slots__ = ("build", "compiler_files", "deps", "header", "loader", "root", "runtime",
                 "source", "support", "tools", "unit")

    def __init__(self, root: Path) -> None:
        self.root, self.build, self.source = root, root / "build", root / "model"
        self.build.mkdir()
        self.source.mkdir()
        self.tools: dict[str, Path] = {}
        for name in (*subject._TOOLS, "ldd"):
            path = root / (name.lower() + ".native")
            path.write_bytes(b"\x7fELF" + name.encode())
            self.tools[name] = path
        self.runtime, self.loader = root / "libnative.so", root / "loader.so"
        self.runtime.write_bytes(b"shared library")
        self.loader.write_bytes(b"native loader")
        self.support = root / "compiler-support"
        self.support.mkdir()
        for name in subject._SUPPORT:
            (self.support / name).write_bytes(name.encode())
        (self.support / "gmp.h").write_bytes(b"GMP header")
        (self.support / "libgmp.so").write_bytes(b"GMP library")
        self.header, self.unit = self.source / "native.h", self.source / "native.cpp"
        self.header.write_bytes(b"original header")
        self.unit.write_bytes(b"original source")
        self.deps = [self.unit, self.header]
        entries = {**{name: str(path) for name, path in self.tools.items() if name != "ldd"},
                   "CMAKE_HOME_DIRECTORY": str(self.source),
                   "GMP_C_LIBRARIES": str(self.support / "libgmp.so"),
                   "GMP_C_INCLUDES": str(self.support)}
        (self.build / "CMakeCache.txt").write_text(
            "\n".join(f"{key}:FILEPATH={value}" for key, value in entries.items()) + "\n",
            encoding="utf-8")
        configuration = self.build / "CMakeFiles/4.0"
        configuration.mkdir(parents=True)
        self.compiler_files: dict[str, Path] = {}
        for language in ("C", "CXX"):
            path = configuration / f"CMake{language}Compiler.cmake"
            path.write_text(f'set(CMAKE_{language}_COMPILER_ID "Clang")\n'
                            f'set(CMAKE_{language}_COMPILER "{self.tools[f"CMAKE_{language}_COMPILER"]}")\n',
                            encoding="utf-8")
            self.compiler_files[language] = path
        (self.build / "compile_commands.json").write_text(json.dumps([
            {"directory": str(self.build), "file": str(self.unit),
             "arguments": [str(self.tools["CMAKE_CXX_COMPILER"]), "-c", str(self.unit),
                           "-o", "native.cpp.o"]}]), encoding="utf-8")
        (self.build / ".ninja_deps").write_bytes(b"fixture database")
        (self.build / "native.cpp.o").write_bytes(b"compiled object")
        simulator = self.build / subject.SIMULATOR
        simulator.parent.mkdir(parents=True)
        simulator.write_bytes(b"\x7fELFsimulator")

    def run(self, argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if argv[0] == str(self.tools["ldd"]):
            output = (f"libnative.so => {self.runtime} (0x123)\n"
                      f"{self.loader} (0x456)\n")
        elif argv[-1].startswith("-print-prog-name="):
            output = str(self.tools["CMAKE_LINKER"]) + "\n"
        elif argv[-1].startswith("-print-file-name="):
            output = str(self.support / argv[-1].split("=", 1)[1]) + "\n"
        elif argv[-2:] == ["-t", "deps"]:
            output = (f"native.cpp.o: #deps {len(self.deps)}, deps mtime 123 (VALID)\n"
                      + "".join(f"    {path}\n" for path in self.deps) + "\n")
        else:
            raise AssertionError(f"unexpected discovery command: {argv}")
        return subprocess.CompletedProcess(argv, 0, output, "")


@contextmanager
def fixture() -> Generator[Fixture]:
    with tempfile.TemporaryDirectory(prefix="vos-native-inputs-") as name:
        at = Fixture(Path(name))
        with (patch.object(subject.subprocess, "run", side_effect=at.run),
              patch.object(subject.shutil, "which", return_value=str(at.tools["ldd"]))):
            yield at


def _refuses(fn: object, *args: object) -> None:
    if not callable(fn):
        raise TypeError("refusal control needs a callable")
    try:
        fn(*args)
    except (OSError, ValueError, TypeError):
        return
    raise AssertionError("invalid native identity was accepted")


def _change(path: Path) -> bytes:
    before = path.read_bytes()
    previous = path.stat()
    path.write_bytes(before[:-1] + bytes([before[-1] ^ 1]))
    os.utime(path, ns=(previous.st_atime_ns, previous.st_mtime_ns))
    ensure(path.stat().st_mtime_ns == previous.st_mtime_ns, "mtime control did not hold")
    return before


def _content_and_reuse() -> None:
    with fixture() as at:
        original = subject.capture(at.build, at.source)
        subject.validate(original)
        subject.verify(original, at.build, at.source)
        ensure(not subject.prepare(at.build, at.source, original), "honest native reuse was refused")
        ensure(subject.prepare(at.build, at.source), "unrecorded existing native products were reused")
        for path in (at.header, at.unit, at.runtime, at.loader,
                     at.tools["CMAKE_CXX_COMPILER"], at.support / "crti.o",
                     at.support / "libgmp.so", at.support / "gmp.h"):
            before = _change(path)
            _refuses(subject.validate, original)
            ensure(subject.prepare(at.build, at.source, original),
                   f"preserved-mtime change failed to force a clean: {path}")
            refreshed = subject.observe(original)
            subject.validate(refreshed)
            path.write_bytes(before)
            _refuses(subject.validate, refreshed)
        subject.verify(original, at.build, at.source)


def _population_and_configuration() -> None:
    with fixture() as at:
        original = subject.capture(at.build, at.source)
        extra = at.source / "new-header.h"
        extra.write_bytes(b"new actual dependency")
        at.deps.append(extra)
        _refuses(subject.verify, original, at.build, at.source)
        ensure(subject.prepare(at.build, at.source, original), "new native header was not discovered")
        at.deps.pop()
        # The actual cached path wins even if another compiler is on PATH.
        with patch.dict(os.environ, {"PATH": str(at.root / "another-toolchain")}):
            current = subject.capture(at.build, at.source)
            ensure(current["tools"]["CMAKE_CXX_COMPILER"] == str(at.tools["CMAKE_CXX_COMPILER"]),
                   "PATH compiler replaced CMake's selected compiler in the receipt")
            _refuses(subject.validate, original)
        compiler = at.compiler_files["CXX"]
        source = compiler.read_text(encoding="utf-8")
        compiler.write_text(source.replace('"Clang"', '"Unknown"'), encoding="utf-8")
        _refuses(subject.capture, at.build, at.source)
        compiler.write_text(source.replace(str(at.tools["CMAKE_CXX_COMPILER"]),
                                           str(at.tools["CMAKE_C_COMPILER"])), encoding="utf-8")
        _refuses(subject.capture, at.build, at.source)
        compiler.write_text(source, encoding="utf-8")
        at.header.unlink()
        _refuses(subject.capture, at.build, at.source)
        ensure(subject.prepare(at.build, at.source, original), "missing prior header allowed reuse")


def _malformed_and_failed_discovery() -> None:
    with fixture() as at:
        original = subject.capture(at.build, at.source)
        for key, value in (("schema", "old"), ("files", {}), ("tools", {}),
                           ("population", []), ("compiler_ids", {}),
                           ("targets", {}), ("complete", 1)):
            broken: dict[str, object] = dict(copy.deepcopy(original))
            broken[key] = value
            _refuses(subject.validate, broken)
        bad_hash = copy.deepcopy(original)
        bad_hash["files"][str(at.header)] = "not-a-hash"
        _refuses(subject.validate, bad_hash)
        at.deps.clear()
        _refuses(subject.capture, at.build, at.source)
        with patch.object(subject.subprocess, "run", return_value=subprocess.CompletedProcess(
                ["tool"], 1, "", "discovery failed")):
            _refuses(subject.capture, at.build, at.source)
        with patch.object(subject.shutil, "which", return_value=None):
            _refuses(subject.configured, at.build, at.source)
        cache = at.build / "CMakeCache.txt"
        cache.write_text(cache.read_text(encoding="utf-8") +
                         f'CMAKE_C_COMPILER:FILEPATH={at.tools["CMAKE_C_COMPILER"]}\n',
                         encoding="utf-8")
        _refuses(subject.capture, at.build, at.source)


def _fresh_and_generated() -> None:
    with fixture() as at:
        (at.build / subject.SIMULATOR).unlink()
        (at.build / ".ninja_deps").unlink()
        ensure(not subject.prepare(at.build, at.source), "fresh native tree requires unnecessary clean")
        generated = at.build / "generated.h"
        generated.write_bytes(b"generated")
        at.deps.append(generated)
        commands = at.build / "compile_commands.json"
        population = json.loads(commands.read_text(encoding="utf-8"))
        population.append({"directory": str(at.build), "file": str(at.build / "not-emitted.cpp"),
                           "arguments": [str(at.tools["CMAKE_CXX_COMPILER"]), "-c",
                                         "not-emitted.cpp", "-o", "not-emitted.o"]})
        commands.write_text(json.dumps(population), encoding="utf-8")
        known = subject.configured(at.build, at.source)
        generated.write_bytes(b"replacement generated result")
        subject.validate(known)


def _symlink_selection() -> None:
    with fixture() as at:
        alias = at.source / "selected.h"
        other = at.source / "equivalent.h"
        other.write_bytes(at.header.read_bytes())
        alias.symlink_to(at.header)
        at.deps.append(alias)
        original = subject.capture(at.build, at.source)
        alias.unlink()
        alias.symlink_to(other)
        _refuses(subject.validate, original)


def _native_fixture() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-native-cmake-") as name:
        root = Path(name)
        source, build = root / "model", root / "build"
        source.mkdir()
        (source / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.26)\nproject(native_fixture C CXX)\n"
            "set(CMAKE_EXPORT_COMPILE_COMMANDS ON)\n"
            "find_library(GMP_C_LIBRARIES NAMES gmp REQUIRED)\n"
            "find_path(GMP_C_INCLUDES NAMES gmp.h REQUIRED)\n"
            "add_executable(sail_riscv_sim main.cpp helper.c)\n"
            "target_include_directories(sail_riscv_sim PRIVATE ${GMP_C_INCLUDES})\n"
            "target_link_libraries(sail_riscv_sim PRIVATE ${GMP_C_LIBRARIES})\n"
            "set_target_properties(sail_riscv_sim PROPERTIES "
            "RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/c_emulator)\n", encoding="utf-8")
        (source / "main.cpp").write_text(
            '#include <gmp.h>\n#include "local.h"\nextern "C" int helper(void);\n'
            "int main() { mpz_t n; mpz_init(n); mpz_clear(n); return helper() + LOCAL; }\n",
            encoding="utf-8")
        (source / "helper.c").write_text("int helper(void) { return 0; }\n", encoding="utf-8")
        header = source / "local.h"
        header.write_text("#define LOCAL 0\n", encoding="utf-8")
        subprocess.run(["cmake", "-S", str(source), "-B", str(build), "-GNinja"],
                       capture_output=True, text=True, check=True, timeout=60)
        before = subject.configured(build, source)
        subprocess.run(["cmake", "--build", str(build)], capture_output=True,
                       text=True, check=True, timeout=60)
        subject.validate(before)
        record = subject.capture(build, source)
        subject.verify(record, build, source)
        ensure(not subject.prepare(build, source, record), "real native no-op reuse refused")
        _change(header)
        ensure(subject.prepare(build, source, record), "real old-mtime header failed to invalidate reuse")


def cases() -> list[Case]:
    return [Case("native tools, sources, headers and libraries bind bytes despite old mtimes", _content_and_reuse),
            Case("native dependency population and configured compiler identity", _population_and_configuration),
            Case("malformed native identity and failed discovery refuse", _malformed_and_failed_discovery),
            Case("fresh native builds and generated intermediate ownership", _fresh_and_generated),
            Case("retargeted native header symlink refuses even for equal bytes", _symlink_selection,
                 lane="guest"),
            Case("actual CMake Ninja compiler and GMP closure on a small native fixture", _native_fixture,
                 lane="toolchain")]
