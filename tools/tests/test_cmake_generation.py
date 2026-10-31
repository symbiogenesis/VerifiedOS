# SPDX-License-Identifier: Apache-2.0
"""Real small Ninja graphs exercise the model's content-based generation rules.

These fixtures use fake Sail/solver programs and no model or proof compilation.
They run on Linux, where the supported native model toolchain is installed by
Guest CI. Missing CMake or Ninja is a refusal, never a passing skipped control.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from tests.harness import TOOLS, Case, ensure

INDEPENDENT_CASES = True
HELPER = TOOLS.parent / "model/cmake/sail_toolchain.cmake"


class Fixture:
    """A source tree with the real rule helper and a deliberately tiny emitter."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.build = root / "build"
        self.stamp = self.build / "complete.stamp"
        self.identity = self.build / "sail_toolchain.sha256"
        self.artifact = self.build / "emitted.txt"
        self.counter = self.build / "counter.txt"
        self.bin = root / "bin"
        self.bin.mkdir()
        self.share = root / "share/sail"
        (self.share / "lib").mkdir(parents=True)
        plugins = root / "share/libsail/plugins"
        plugins.mkdir(parents=True)
        self.sail = self.bin / "sail"
        self.sail.write_text(f"#!/bin/sh\nprintf '%s\\n' '{self.share.as_posix()}'\n",
                             encoding="utf-8", newline="")
        self.sail.chmod(0o755)
        self.z3 = self.bin / "z3"
        self.z3.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="")
        self.z3.chmod(0o755)
        self.library = self.share / "lib/core.sail"
        self.runtime = self.share / "lib/runtime.h"
        self.plugin = plugins / "backend.cmxs"
        for path in (self.library, self.runtime, self.plugin):
            path.write_bytes(b"original\n")
        self.failure = root / "failure.txt"
        self.failure.write_text("pass", encoding="utf-8")
        emitter = '''file(READ "${IDENTITY}" identity)
set(count 0)
if(EXISTS "${COUNTER}")
    file(READ "${COUNTER}" count)
endif()
math(EXPR count "${count} + 1")
file(WRITE "${COUNTER}" "${count}")
# Write a partial primary output before failing, just as a generator can.
file(WRITE "${ARTIFACT}" "${identity}")
file(READ "${FAILURE}" failure)
if(failure STREQUAL "fail")
    message(FATAL_ERROR "intentional emitter failure")
endif()
'''
        (root / "emit.cmake").write_text(emitter, encoding="utf-8", newline="")
        source = f'''cmake_minimum_required(VERSION 3.26)
project(generator_fixture NONE)
set(SAIL_BIN "{self.sail.as_posix()}")
set(sail_dir "{self.share.as_posix()}")
include("{HELPER.as_posix()}")
sail_add_toolchain_identity()
sail_generated_command(
    STAMP "${{CMAKE_BINARY_DIR}}/complete.stamp"
    OUTPUTS "${{CMAKE_BINARY_DIR}}/emitted.txt"
    DEPENDS "${{CMAKE_SOURCE_DIR}}/failure.txt"
    WORKING_DIRECTORY "${{CMAKE_SOURCE_DIR}}"
    COMMENT "Running fixture emitter"
    COMMAND "${{CMAKE_COMMAND}}"
        "-DIDENTITY=${{SAIL_TOOLCHAIN_STAMP}}"
        "-DCOUNTER=${{CMAKE_BINARY_DIR}}/counter.txt"
        "-DARTIFACT=${{CMAKE_BINARY_DIR}}/emitted.txt"
        "-DFAILURE=${{CMAKE_SOURCE_DIR}}/failure.txt"
        -P "${{CMAKE_SOURCE_DIR}}/emit.cmake")
add_custom_target(emitted ALL DEPENDS "${{CMAKE_BINARY_DIR}}/emitted.txt")
'''
        (root / "CMakeLists.txt").write_text(source, encoding="utf-8", newline="")
        cmake = shutil.which("cmake")
        ninja = shutil.which("ninja")
        if cmake is None or ninja is None:
            raise RuntimeError("native CMake generation fixtures require cmake and ninja")
        self.cmake = cmake
        self.environment = {key: value for key, value in os.environ.items()
                            if key not in {"SAIL_DIR", "SAIL_NO_PLUGINS", "SAIL_PLUGIN_DIR",
                                           "DUNE_DIR_LOCATIONS"}}
        self.environment["PATH"] = str(self.bin) + os.pathsep + self.environment.get("PATH", "")
        self.run([self.cmake, "-S", str(root), "-B", str(self.build), "-GNinja",
                  f"-DCMAKE_MAKE_PROGRAM={ninja}"])

    def run(self, argv: list[str], *, passed: bool = True) -> str:
        """Run an isolated fixture command and require its exact success polarity."""
        done = subprocess.run(argv, cwd=self.root, env=self.environment, capture_output=True,
                              text=True, check=False, timeout=60)
        output = done.stdout + done.stderr
        ensure((done.returncode == 0) == passed, output)
        return output

    def emit(self, *, passed: bool = True) -> str:
        """Build the fixture's one generated artifact, using the actual Ninja graph."""
        return self.run([self.cmake, "--build", str(self.build)], passed=passed)

    def count(self) -> int:
        """Read the emitter's observed invocation count."""
        return int(self.counter.read_text(encoding="utf-8"))


def _changed_bytes(path: Path) -> None:
    """Change bytes while deliberately retaining the input's recorded timestamps."""
    before = path.stat()
    path.write_bytes(path.read_bytes() + b"\n# changed bytes\n")
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))


def _content_changes() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-cmake-content-") as name:
        fixture = Fixture(Path(name))
        fixture.emit()
        ensure(fixture.count() == 1, "initial generation did not run once")
        unchanged = fixture.identity.stat().st_mtime_ns, fixture.stamp.stat().st_mtime_ns
        fixture.emit()
        ensure(fixture.count() == 1, "unchanged identity regenerated output")
        ensure(unchanged == (fixture.identity.stat().st_mtime_ns,
                             fixture.stamp.stat().st_mtime_ns), "unchanged stamps were rewritten")
        for expected, path in enumerate((fixture.sail, fixture.library, fixture.runtime,
                                         fixture.plugin, fixture.z3), start=2):
            _changed_bytes(path)
            fixture.emit()
            ensure(fixture.count() == expected,
                   f"preserved-mtime change to {path.name} reused stale output")


def _population_changes() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-cmake-population-") as name:
        fixture = Fixture(Path(name))
        fixture.emit()
        (fixture.share / "lib/added.sail").write_bytes(b"new member")
        fixture.emit()
        ensure(fixture.count() == 2, "added library member did not invalidate generation")
        fixture.plugin.unlink()
        fixture.emit()
        ensure(fixture.count() == 3, "removed plugin did not invalidate generation")
        fixture.emit()
        ensure(fixture.count() == 3, "stable changed population regenerated again")
        fixture.run([fixture.cmake, "-S", str(fixture.root), "-B", str(fixture.build),
                     "-DVOS_SAIL_LOADER_IDENTITY=changed-order"])
        fixture.emit()
        ensure(fixture.count() == 4, "changed loader identity did not invalidate generation")
        fixture.emit()
        ensure(fixture.count() == 4, "stable loader identity regenerated again")


def _failed_emission() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-cmake-failure-") as name:
        fixture = Fixture(Path(name))
        fixture.emit()
        fixture.failure.write_text("fail", encoding="utf-8")
        _changed_bytes(fixture.library)
        output = fixture.emit(passed=False)
        ensure("intentional emitter failure" in output, "refusal came from an unrelated failure")
        ensure(fixture.artifact.is_file(), "control did not retain a partial primary output")
        ensure(not fixture.stamp.exists(), "failed generation retained a completion stamp")
        # Restore the flag's timestamp too: the missing completion stamp must
        # force a retry, even though the partial artifact is newer than inputs.
        before = fixture.failure.stat()
        fixture.failure.write_text("pass", encoding="utf-8")
        os.utime(fixture.failure, ns=(before.st_atime_ns, before.st_mtime_ns))
        fixture.emit()
        ensure(fixture.count() == 3 and fixture.stamp.is_file(),
               "partial failed output was reused instead of retrying generation")


def _invalid_identity() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-cmake-identity-") as name:
        fixture = Fixture(Path(name))
        fixture.emit()
        fixture.environment["SAIL_PLUGIN_DIR"] = "relative/plugins"
        output = fixture.emit(passed=False)
        ensure("plugin directory" in output and not fixture.identity.exists(),
               "invalid plugin selection retained current input identity")
        fixture.environment.pop("SAIL_PLUGIN_DIR")
        fixture.emit()
        fixture.library.unlink()
        output = fixture.emit(passed=False)
        ensure("no .sail source files" in output and not fixture.identity.exists(),
               "empty Sail library retained current input identity")


def cases() -> list[Case]:
    """Every native fixture is mandatory on the Linux lane that selects it."""
    return [Case("generator bytes invalidate preserved timestamps", _content_changes, lane="guest"),
            Case("generator population changes invalidate outputs", _population_changes, lane="guest"),
            Case("failed generators cannot reuse partial output", _failed_emission, lane="guest"),
            Case("invalid generator identity refuses before emission", _invalid_identity, lane="guest")]
