# SPDX-License-Identifier: Apache-2.0
"""Content identity of the configured model's native compilation inputs.

CMake's configured tools, compiler support files, their shared libraries, the
actual compiled source/header population and the simulator's shared libraries
are evidence inputs. Generated files beneath the build root have their own
owners and are excluded here. This is native input freshness, not a hermetic
execution environment or an independent reproducibility result.

Call ``prepare`` under the build lock before reusing objects, and clean when it
returns true. ``configured`` and ``observe`` give pre-build snapshots; validating
them after the build refuses a known input that changed during it. Publish
``capture`` only after successful compilation, then use ``verify`` on reuse.
"""

import json
import os
import re
import shlex
import shutil
import stat
import subprocess
from pathlib import Path
from typing import TypedDict

from vos import receipts

SCHEMA = "verifiedos-native-inputs/1"
STAMP = "vos-native-inputs.json"
SIMULATOR = "c_emulator/sail_riscv_sim"
_TOOLS = ("CMAKE_C_COMPILER", "CMAKE_CXX_COMPILER", "CMAKE_AR", "CMAKE_RANLIB",
          "CMAKE_LINKER", "CMAKE_MAKE_PROGRAM", "CMAKE_COMMAND")
_OPTIONAL_TOOLS = ("CMAKE_C_COMPILER_AR", "CMAKE_CXX_COMPILER_AR",
                   "CMAKE_C_COMPILER_RANLIB", "CMAKE_CXX_COMPILER_RANLIB",
                   "CMAKE_C_COMPILER_LAUNCHER", "CMAKE_CXX_COMPILER_LAUNCHER")
_ENVIRONMENT = ("PATH", "CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "LIBRARY_PATH",
                "LD_LIBRARY_PATH", "LD_PRELOAD", "LD_AUDIT", "COMPILER_PATH",
                "GCC_EXEC_PREFIX", "SDKROOT", "SOURCE_DATE_EPOCH")
_SUPPORT = ("crt1.o", "Scrt1.o", "crti.o", "crtn.o", "crtbegin.o", "crtbeginS.o",
            "crtend.o", "crtendS.o", "libgcc.a", "libgcc_eh.a", "libgcc_s.so",
            "libc.so", "libm.so", "libstdc++.so")
_SHA = re.compile(r"[0-9a-f]{64}")


class Manifest(TypedDict):
    """Serializable selected names and content identities for one native tree."""

    schema: str
    build_root: str
    source_root: str
    tools: dict[str, str]
    compiler_ids: dict[str, str]
    environment: dict[str, str]
    files: dict[str, str]
    targets: dict[str, str]
    population: list[str]
    complete: bool


def _run(argv: list[str], directory: Path) -> str:
    done = subprocess.run(argv, cwd=directory, capture_output=True, text=True,
                          check=False, timeout=120)
    if done.returncode:
        raise ValueError(f"native input discovery failed: {argv[0]}: {done.stderr.strip()}")
    return done.stdout


def _cache(build: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in (build / "CMakeCache.txt").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith(("//", "#")):
            continue
        match = re.fullmatch(r"([^:=]+):[A-Z]+=(.*)", line)
        if match is None or match[1] in values:
            raise ValueError("native input discovery requires an unambiguous CMake cache")
        values[match[1]] = match[2]
    return values


def _path(value: str, name: str, *, search: bool = False) -> Path:
    path = Path(value)
    if search and not path.is_absolute():
        selected = shutil.which(value)
        if selected is None:
            raise ValueError(f"configured native tool is missing: {name}={value}")
        path = Path(selected)
    if not value or not path.is_absolute() or value.endswith("-NOTFOUND"):
        raise ValueError(f"native input requires an absolute configured path: {name}")
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError(f"native input is not a regular file: {path}")
    return path.absolute()


def _runtime(executable: Path, ldd: Path, build: Path) -> set[Path]:
    """Read the native loader's resolved shared closure without version guessing."""
    with executable.open("rb") as stream:
        prefix = stream.read(4096)
    if prefix.startswith(b"#!"):
        words = shlex.split(prefix.split(b"\n", 1)[0][2:].decode("utf-8"))
        if len(words) != 1:
            raise ValueError(f"unsupported native tool interpreter: {executable}")
        interpreter = _path(words[0], "tool interpreter")
        return {interpreter, *_runtime(interpreter, ldd, build)}
    if not prefix.startswith(b"\x7fELF"):
        raise ValueError(f"unsupported native tool format: {executable}")
    done = subprocess.run([str(ldd), str(executable)], cwd=build, capture_output=True,
                          text=True, check=False, timeout=120)
    output = (done.stdout + "\n" + done.stderr).strip()
    if output in {"statically linked", "not a dynamic executable"}:
        return set()
    if done.returncode:
        raise ValueError(f"cannot identify native shared libraries: {executable}: {output}")
    paths: set[Path] = set()
    for line in output.splitlines():
        row = line.strip()
        # The virtual DSO is supplied by the kernel and names no filesystem input.
        if re.fullmatch(r"linux-vdso(?:32|64)?\.so\.\d+ \(0x[0-9a-f]+\)", row):
            continue
        match = re.fullmatch(r"(?:\S+ => )?((?:/|[A-Za-z]:[\\/]).+) \(0x[0-9a-f]+\)", row)
        if match is None:
            raise ValueError(f"unresolved native shared-library record: {row}")
        paths.add(_path(match[1], "shared library"))
    if not paths:
        raise ValueError(f"empty native shared-library population: {executable}")
    return paths


def _compiler_records(build: Path, cache: dict[str, str]) -> tuple[dict[str, str], set[Path]]:
    identities: dict[str, str] = {}
    paths: set[Path] = set()
    for language in ("C", "CXX"):
        files = list((build / "CMakeFiles").glob(f"*/CMake{language}Compiler.cmake"))
        if len(files) != 1:
            raise ValueError(f"native build lacks unique {language} compiler configuration")
        text = files[0].read_text(encoding="utf-8")
        found = re.findall(rf'set\(CMAKE_{language}_COMPILER_ID "([^"]+)"\)', text)
        if len(found) != 1 or found[0] not in {"GNU", "Clang", "AppleClang"}:
            raise ValueError(f"unsupported configured native {language} compiler")
        configured = re.findall(rf'set\(CMAKE_{language}_COMPILER "([^"]+)"\)', text)
        if configured != [cache[f"CMAKE_{language}_COMPILER"]]:
            raise ValueError(f"native {language} compiler disagrees with its CMake cache")
        identities[language] = found[0]
        paths.add(files[0])
    return identities, paths


def _sources(build: Path) -> tuple[set[Path], set[str]]:
    records: object = json.loads((build / "compile_commands.json").read_text(encoding="utf-8"))
    if not isinstance(records, list) or not records:
        raise ValueError("native compilation source population is empty")
    paths: set[Path] = set()
    outputs: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise TypeError("invalid native compilation record")
        source, directory = record.get("file"), record.get("directory")
        if not isinstance(source, str) or not source or not isinstance(directory, str):
            raise ValueError("native compilation record lacks a source and directory")
        base = Path(directory)
        if not base.is_absolute():
            raise ValueError("native compilation directory must be absolute")
        path = Path(source)
        paths.add(path if path.is_absolute() else base / path)
        command, arguments = record.get("command"), record.get("arguments")
        if isinstance(command, str):
            argv = shlex.split(command)
        elif isinstance(arguments, list) and all(isinstance(arg, str) for arg in arguments):
            argv = list(arguments)
        else:
            raise ValueError("native compilation record lacks its actual command")
        if argv.count("-o") != 1 or argv.index("-o") + 1 >= len(argv):
            raise ValueError("native compilation record lacks unique object output")
        target = Path(argv[argv.index("-o") + 1])
        target = target if target.is_absolute() else base / target
        outputs.add(str(target.absolute()))
    return paths, outputs


def _headers(output: str, build: Path, outputs: set[str], *, complete: bool = False) -> set[Path]:
    paths: set[Path] = set()
    expected = -1
    observed = 0
    seen: set[str] = set()
    for line in [*output.splitlines(), ""]:
        if line.startswith("    "):
            if expected >= 0:
                name = line[4:]
                if not name:
                    raise ValueError("empty native compiler dependency")
                paths.add(Path(name))
                observed += 1
        elif line:
            if expected >= 0 and observed != expected:
                raise ValueError("incomplete native compiler dependency record")
            match = re.fullmatch(r"(.+): #deps (\d+), .+", line)
            if match is None:
                raise ValueError("unrecognized native compiler dependency record")
            target = Path(match[1])
            target = target if target.is_absolute() else build / target
            expected = int(match[2]) if str(target.absolute()) in outputs else -1
            if expected >= 0:
                seen.add(str(target.absolute()))
            observed = 0
            if expected == 0:
                raise ValueError("empty native compiler dependency record")
        elif expected >= 0 and observed != expected:
            raise ValueError("incomplete native compiler dependency record")
    if complete and not {name for name in outputs if Path(name).is_file()}.issubset(seen):
        raise ValueError("native compiler dependency population omits a built object")
    return paths


def _snapshot(paths: set[Path], build: Path) -> tuple[dict[str, str], dict[str, str]]:
    files: dict[str, str] = {}
    targets: dict[str, str] = {}
    for selected in sorted(paths):
        path = selected.absolute()
        # Source and dependency inputs are bound; generated intermediates are not
        # immutable inputs and must not invalidate their own build's evidence.
        configuration = path.name in {"CMakeCache.txt", "CMakeCCompiler.cmake",
                                       "CMakeCXXCompiler.cmake"}
        if path.is_relative_to(build) and not configuration:
            continue
        path = _path(str(path), "native input")
        name = str(path)
        files[name] = receipts.digest(path)
        targets[name] = str(path.resolve(strict=True))
    if not files:
        raise ValueError("native input population is empty")
    return files, targets


def configured(build_dir: Path, source_root: Path, *, known: bool = True) -> Manifest:
    """Snapshot configured tools and known sources before native compilation."""
    build, source = build_dir.resolve(), source_root.resolve()
    cache = _cache(build)
    if cache.get("CMAKE_HOME_DIRECTORY") != str(source):
        raise ValueError("native CMake cache names another source tree")
    tools = {name: str(_path(cache.get(name, ""), name)) for name in _TOOLS}
    for name in _OPTIONAL_TOOLS:
        if bool(cache.get(name)):
            tools[name] = str(_path(cache[name], name, search=True))
    selected_ldd = shutil.which("ldd")
    if selected_ldd is None:
        raise ValueError("native shared-library discovery requires ldd")
    ldd = _path(selected_ldd, "ldd")
    tools["ldd"] = str(ldd)
    identities, paths = _compiler_records(build, cache)
    paths.update(Path(path) for path in tools.values())
    paths.add(build / "CMakeCache.txt")
    sources, outputs = _sources(build)
    paths.update(sources)
    for name in ("GMP_C_LIBRARIES", "GMP_C_INCLUDES"):
        if not bool(cache.get(name)):
            raise ValueError(f"native build lacks configured {name}")
    paths.add(_path(cache["GMP_C_LIBRARIES"], "GMP library"))
    include = Path(cache["GMP_C_INCLUDES"])
    paths.add(_path(str(include / "gmp.h"), "GMP header"))
    for executable in {Path(path) for path in tools.values()}:
        paths.update(_runtime(executable, ldd, build))
    for language in ("C", "CXX"):
        compiler = tools[f"CMAKE_{language}_COMPILER"]
        programs = ["ld", "as"]
        if identities[language] == "GNU":
            programs.extend(("cc1", "cc1plus", "collect2", "lto1"))
        for program in programs:
            selected = _run([compiler, f"-print-prog-name={program}"], build).strip()
            executable = _path(selected, f"compiler-selected {program}", search=True)
            paths.add(executable)
            paths.update(_runtime(executable, ldd, build))
        for name in _SUPPORT:
            selected = _run([compiler, f"-print-file-name={name}"], build).strip()
            paths.add(_path(selected, f"compiler support file {name}"))
    if known and (build / ".ninja_deps").exists():
        headers = _headers(_run([tools["CMAKE_MAKE_PROGRAM"], "-C", str(build),
                                 "-t", "deps"], build), build, outputs)
        # Missing previous dependencies force a clean through prepare; an old
        # Ninja database may retain them after clean, so don't snapshot absent
        # historical paths into the replacement run's pre-build identity.
        paths.update(selected for path in headers
                     if (selected := path if path.is_absolute() else build / path).exists())
    files, targets = _snapshot(paths, build)
    return {"schema": SCHEMA, "build_root": str(build), "source_root": str(source),
            "tools": tools, "compiler_ids": identities,
            "environment": {key: os.environ[key] for key in _ENVIRONMENT if key in os.environ},
            "files": files, "targets": targets, "population": sorted(files), "complete": False}


def capture(build_dir: Path, source_root: Path) -> Manifest:
    """Capture completed native inputs, including actual compiler dependencies."""
    record = configured(build_dir, source_root)
    build = Path(record["build_root"])
    _sources_read, outputs = _sources(build)
    dependencies = _headers(_run([record["tools"]["CMAKE_MAKE_PROGRAM"], "-C", str(build),
                                  "-t", "deps"], build), build, outputs, complete=True)
    if not dependencies:
        raise ValueError("native build has no compiler dependency population")
    simulator = _path(str(build / SIMULATOR), "built simulator")
    runtime = _runtime(simulator, Path(record["tools"]["ldd"]), build)
    paths = {*(Path(name) for name in record["files"]), *runtime}
    paths.update(path if path.is_absolute() else build / path for path in dependencies)
    files, targets = _snapshot(paths, build)
    record.update(files=files, targets=targets, population=sorted(files), complete=True)
    return record


def _strings(raw: object, label: str) -> dict[str, str]:
    if not isinstance(raw, dict) or not all(isinstance(key, str) and isinstance(value, str)
                                            for key, value in raw.items()):
        raise ValueError(f"native input record requires {label}")
    return dict(raw)


def _record(raw: object) -> Manifest:
    if not isinstance(raw, dict) or set(raw) != set(Manifest.__annotations__):
        raise ValueError("malformed native input identity")
    schema, build, source = raw.get("schema"), raw.get("build_root"), raw.get("source_root")
    complete, population = raw.get("complete"), raw.get("population")
    if (schema != SCHEMA or not isinstance(build, str) or not Path(build).is_absolute()
            or not isinstance(source, str) or not Path(source).is_absolute()
            or type(complete) is not bool or not isinstance(population, list)
            or not all(isinstance(item, str) for item in population)):
        raise ValueError("invalid native input identity")
    tools = _strings(raw["tools"], "configured tools")
    ids = _strings(raw["compiler_ids"], "compiler identities")
    files, targets = _strings(raw["files"], "file hashes"), _strings(raw["targets"], "targets")
    environment = _strings(raw["environment"], "environment")
    if (not files or set(files) != set(targets) or sorted(files) != population
            or not set(_TOOLS).issubset(tools) or set(ids) != {"C", "CXX"}
            or any(value not in {"GNU", "Clang", "AppleClang"} for value in ids.values())
            or not set(environment).issubset(_ENVIRONMENT)
            or any(not Path(name).is_absolute() or _SHA.fullmatch(value) is None
                   for name, value in files.items())
            or any(not Path(path).is_absolute() for path in targets.values())
            or any(not Path(path).is_absolute() or path not in files for path in tools.values())):
        raise ValueError("incomplete native input identity")
    return {"schema": schema, "build_root": build, "source_root": source, "tools": tools,
            "compiler_ids": ids, "environment": environment, "files": files,
            "targets": targets, "population": list(population), "complete": complete}


def observe(raw: object) -> Manifest:
    """Rehash the previous known input population before a replacement build."""
    record = _record(raw)
    files, targets = _snapshot({Path(name) for name in record["files"]}, Path(record["build_root"]))
    record.update(files=files, targets=targets, population=sorted(files),
                  environment={key: os.environ[key] for key in _ENVIRONMENT if key in os.environ})
    return record


def validate(raw: object) -> None:
    """Reject changed bytes, symlink selection, environment or malformed identity."""
    record = _record(raw)
    if observe(record) != record:
        raise ValueError("native build inputs changed: tools, sources, headers or libraries")


def verify(raw: object, build_dir: Path, source_root: Path) -> None:
    """Require complete current content and actual dependency population."""
    record = _record(raw)
    validate(record)
    if not record["complete"] or capture(build_dir, source_root) != record:
        raise ValueError("native build input population or configured producers changed")


def prepare(build_dir: Path, source_root: Path, previous: object = None) -> bool:
    """Return whether existing native products require a clean rebuild."""
    build = build_dir.resolve()
    configured(build, source_root, known=False)
    if previous is None and (build / STAMP).exists():
        previous = json.loads((build / STAMP).read_text(encoding="utf-8"))
    if not (build / SIMULATOR).exists() and not (build / ".ninja_deps").exists():
        return False
    try:
        verify(previous, build, source_root)
    except (OSError, ValueError, TypeError):
        return True
    return False
