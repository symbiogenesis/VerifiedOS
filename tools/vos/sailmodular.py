# SPDX-License-Identifier: Apache-2.0
"""Optional, compiler-described partitioning of Sail's generated C++ model.

Libclang supplies source extents. This module does not parse C++ or Sail. Every
Model method has one byte-identical owner, and helpers and mutable globals have
one shared owner. Qualification is empirical evidence, not a semantic theorem.
"""

import ctypes
import ctypes.util
import hashlib
import json
import os
import shlex
import shutil
import signal
import subprocess
import sysconfig
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vos import differential, env, receipts, trace
from vos.cli import model

LLVM_VERSION = "21.1.8"
METHOD_KINDS = {21, 24, 25}  # CXCursor_CXXMethod, Constructor, Destructor


@dataclass(frozen=True)
class Declaration:
    kind: int
    name: str
    begin: int
    end: int
    body: int | None = None
    internal: bool = False
    initialized: bool = False


class _Cursor(ctypes.Structure):
    _fields_ = [("kind", ctypes.c_int), ("xdata", ctypes.c_int),
                ("data", ctypes.c_void_p * 3)]


class _String(ctypes.Structure):
    _fields_ = [("data", ctypes.c_void_p), ("flags", ctypes.c_uint)]


class _Location(ctypes.Structure):
    _fields_ = [("data", ctypes.c_void_p * 2), ("offset", ctypes.c_uint)]


class _Range(ctypes.Structure):
    _fields_ = [("data", ctypes.c_void_p * 2), ("begin", ctypes.c_uint),
                ("end", ctypes.c_uint)]


class _Type(ctypes.Structure):
    _fields_ = [("kind", ctypes.c_int), ("data", ctypes.c_void_p * 2)]


class Clang:
    """Small authored binding to the stable libclang C API, loaded only on demand."""

    def __init__(self, path: Path) -> None:
        self.library = ctypes.CDLL(str(path))
        self.visit_type = ctypes.CFUNCTYPE(ctypes.c_uint, _Cursor, _Cursor, ctypes.c_void_p)
        self.include_type = ctypes.CFUNCTYPE(None, ctypes.c_void_p,
                                            ctypes.POINTER(_Location), ctypes.c_uint,
                                            ctypes.c_void_p)
        self._bind("createIndex", ctypes.c_void_p, ctypes.c_int, ctypes.c_int)
        self._bind("disposeIndex", None, ctypes.c_void_p)
        self._bind("parseTranslationUnit", ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p), ctypes.c_int,
                   ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint)
        self._bind("disposeTranslationUnit", None, ctypes.c_void_p)
        self._bind("getTranslationUnitCursor", _Cursor, ctypes.c_void_p)
        self._bind("visitChildren", ctypes.c_uint, _Cursor, self.visit_type, ctypes.c_void_p)
        self._bind("getCursorSpelling", _String, _Cursor)
        self._bind("getClangVersion", _String)
        self._bind("getCString", ctypes.c_char_p, _String)
        self._bind("disposeString", None, _String)
        self._bind("getCursorLocation", _Location, _Cursor)
        self._bind("getCursorExtent", _Range, _Cursor)
        self._bind("getRangeStart", _Location, _Range)
        self._bind("getRangeEnd", _Location, _Range)
        self._bind("getFileLocation", None, _Location, ctypes.POINTER(ctypes.c_void_p),
                   ctypes.POINTER(ctypes.c_uint), ctypes.POINTER(ctypes.c_uint),
                   ctypes.POINTER(ctypes.c_uint))
        self._bind("getFileName", _String, ctypes.c_void_p)
        self._bind("getCursorLinkage", ctypes.c_int, _Cursor)
        self._bind("getCursorType", _Type, _Cursor)
        self._bind("getTypeSpelling", _String, _Type)
        self._bind("isCursorDefinition", ctypes.c_uint, _Cursor)
        self._bind("getNumDiagnostics", ctypes.c_uint, ctypes.c_void_p)
        self._bind("getDiagnostic", ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint)
        self._bind("getDiagnosticSeverity", ctypes.c_uint, ctypes.c_void_p)
        self._bind("getDiagnosticSpelling", _String, ctypes.c_void_p)
        self._bind("disposeDiagnostic", None, ctypes.c_void_p)
        self._bind("getInclusions", None, ctypes.c_void_p, self.include_type, ctypes.c_void_p)
        version = self.string(self.call("getClangVersion"))
        if LLVM_VERSION not in version.split():
            raise ValueError(f"libclang {LLVM_VERSION} required, found {version}")

    def _bind(self, name: str, result: Any, *arguments: Any) -> None:  # noqa: ANN401 (ctypes C ABI boundary)
        function = getattr(self.library, "clang_" + name)
        function.restype, function.argtypes = result, list(arguments)

    def call(self, name: str, *arguments: Any) -> Any:  # noqa: ANN401 (ctypes C ABI boundary)
        return getattr(self.library, "clang_" + name)(*arguments)

    def string(self, value: _String) -> str:
        result = self.call("getCString", value)
        try:
            return str(result.decode("utf-8")) if result else ""
        finally:
            self.call("disposeString", value)

    def position(self, location: _Location) -> tuple[str, int]:
        file, offset = ctypes.c_void_p(), ctypes.c_uint()
        self.call("getFileLocation", location, ctypes.byref(file), None, None,
                  ctypes.byref(offset))
        return (self.string(self.call("getFileName", file)) if file else "", offset.value)

    def bounds(self, cursor: _Cursor) -> tuple[int, int]:
        extent = self.call("getCursorExtent", cursor)
        return (self.position(self.call("getRangeStart", extent))[1],
                self.position(self.call("getRangeEnd", extent))[1])

    def inspect(self, source: Path, arguments: list[str]) -> tuple[list[Declaration], dict[str, str]]:
        index = self.call("createIndex", 0, 0)
        args = (ctypes.c_char_p * len(arguments))(*(arg.encode() for arg in arguments))
        unit = self.call("parseTranslationUnit", index, str(source).encode(), args,
                         len(arguments), None, 0, 0)
        if not unit:
            self.call("disposeIndex", index)
            raise ValueError("libclang could not parse the generated model")
        found: list[Declaration] = []
        errors: list[str] = []
        includes: set[str] = set()
        raw_source = source.read_bytes()

        def visit(cursor: _Cursor, parent: _Cursor, _: object) -> int:
            try:
                file, _offset = self.position(self.call("getCursorLocation", cursor))
                name = self.string(self.call("getCursorSpelling", cursor))
                if cursor.kind == 22:  # namespace
                    if file == str(source) and name != "hart":
                        errors.append(f"unsupported namespace {name}")
                    return 2 if name == "hart" else 1
                if file != str(source) or parent.kind != 22:
                    return 1
                begin, end = self.bounds(cursor)
                body: int | None = None

                def child(node: _Cursor, _parent: _Cursor, _data: object) -> int:
                    nonlocal body
                    if node.kind == 202:  # compound statement
                        body = self.bounds(node)[0]
                    return 1

                if cursor.kind in METHOD_KINDS | {8}:
                    self.call("visitChildren", cursor, self.visit_type(child), None)
                    if not self.call("isCursorDefinition", cursor) or body is None:
                        errors.append(f"unsupported nondefinition {name}")
                elif cursor.kind != 9:
                    errors.append(f"unsupported generated declaration kind {cursor.kind}: {name}")
                initialized = False
                if cursor.kind == 9:
                    # libclang reports an implicit constructor for lbits/sail_int.
                    # Accept only the exact compiler-described type/name spelling;
                    # actual initializers or more complex declarators are refused.
                    type_name = self.string(self.call("getTypeSpelling", self.call(
                        "getCursorType", cursor)))
                    initialized = raw_source[begin:end] != f"{type_name} {name}".encode()
                found.append(Declaration(cursor.kind, name, begin, end, body,
                                         self.call("getCursorLinkage", cursor) == 2,
                                         initialized))
            except Exception as exc:  # No Python exception may cross a C callback.
                errors.append(str(exc))
            return 1

        def include(file: object, _stack: object, _length: int, _data: object) -> None:
            try:
                includes.add(self.string(self.call("getFileName", file)))
            except Exception as exc:  # No Python exception may cross a C callback.
                errors.append(str(exc))

        try:
            for number in range(self.call("getNumDiagnostics", unit)):
                diagnostic = self.call("getDiagnostic", unit, number)
                if self.call("getDiagnosticSeverity", diagnostic) >= 3:
                    errors.append(self.string(self.call("getDiagnosticSpelling", diagnostic)))
                self.call("disposeDiagnostic", diagnostic)
            self.call("visitChildren", self.call("getTranslationUnitCursor", unit),
                      self.visit_type(visit), None)
            self.call("getInclusions", unit, self.include_type(include), None)
            if errors:
                raise ValueError("generated model AST refused: " + "; ".join(errors[:10]))
            return sorted(found, key=lambda item: item.begin), {
                path: receipts.digest(Path(path)) for path in sorted(includes)}
        finally:
            self.call("disposeTranslationUnit", unit)
            self.call("disposeIndex", index)


def libclang_path() -> Path:
    name = ctypes.util.find_library("clang-21")
    candidates = [Path("/usr/lib") / str(sysconfig.get_config_var("MULTIARCH")) / str(name),
                  Path("/usr/lib/llvm-21/lib/libclang.so.1")]
    for path in candidates:
        if path.is_file():
            return path.absolute()
    raise ValueError("libclang 21.1.8 is required; provision it explicitly (no automatic install)")


def compile_arguments(directory: Path) -> tuple[Path, list[str], str]:
    rows = json.loads((directory / "compile_commands.json").read_text(encoding="utf-8"))
    picked = [row for row in rows if row["file"] == str(directory / "sail_riscv_model.cpp")]
    if len(picked) != 1:
        raise ValueError("expected exactly one generated model compile command")
    row = picked[0]
    args = list(row.get("arguments") or shlex.split(row["command"]))
    compiler = args.pop(0)
    index = args.index("-o")
    del args[index:index + 2]
    args.remove("-c")
    args.remove(row["file"])
    if any(arg in {"-include", "-imacros", "-Xclang"} for arg in args):
        raise ValueError("forced includes and custom Clang AST flags are unsupported")
    return Path(row["file"]), args, compiler


def partition(raw: bytes, declarations: list[Declaration], count: int) -> tuple[dict[str, bytes], list[dict[str, object]]]:
    """Validate compiler ranges and partition complete method definitions once."""
    if not 2 <= count <= 16:
        raise ValueError("partitions must be between 2 and 16")
    ordered = sorted(declarations, key=lambda item: item.begin)
    previous = 0
    for item in ordered:
        if not previous <= item.begin < item.end <= len(raw):
            raise ValueError("overlapping or invalid compiler declaration ranges")
        previous = item.end
        if item.kind not in METHOD_KINDS | {8, 9}:
            raise ValueError(f"unsupported declaration kind {item.kind}")
        if item.kind != 9 and (item.body is None or not item.begin < item.body < item.end
                               or raw[item.body:item.body + 1] != b"{"):
            raise ValueError(f"missing compiler body range for {item.name}")
        if item.kind == 9 and (item.initialized or item.internal):
            raise ValueError(f"initialized/internal namespace state is unsupported: {item.name}")
    methods = [item for item in ordered if item.kind in METHOD_KINDS]
    if len(methods) < count or not any(item.kind == 8 for item in ordered):
        raise ValueError("insufficient method/helper membership for generated model")
    # Only includes are emitted outside definitions by the supported Sail backend.
    # Refuse conditional compilation rather than moving its selected branch.
    if any(not line.startswith(b"#include ") for line in raw.splitlines()
           if line.lstrip().startswith(b"#")):
        raise ValueError("unsupported preprocessor directive in generated model")
    buckets: list[list[Declaration]] = [[] for _ in range(count)]
    weights = [0] * count
    for item in sorted(methods, key=lambda value: (value.begin - value.end, value.begin)):
        slot = min(range(count), key=lambda number: (weights[number], number))
        buckets[slot].append(item)
        weights[slot] += item.end - item.begin
    declarations_out: list[bytes] = []
    changes: list[tuple[int, int, bytes]] = []
    for item in ordered:
        if item.kind in METHOD_KINDS:
            changes.append((item.begin, item.end, b"\n"))
        elif item.kind == 8:
            signature = raw[item.begin:item.body].rstrip()
            if item.internal:
                if not signature.startswith(b"static "):
                    raise ValueError(f"internal helper does not start with static: {item.name}")
                signature = signature[len(b"static "):]
                changes.append((item.begin, item.begin + len(b"static "), b""))
            declarations_out.append(signature + b";")
        else:
            declarations_out.append(b"extern " + raw[item.begin:item.end] + b";")
    shared = (b'#pragma once\n#include "sail_riscv_model.h"\n#include "riscv_softfloat.h"\n'
              b"namespace hart {\n" + b"\n".join(declarations_out) + b"\n}\n")
    owner = bytearray()
    previous = 0
    for begin, end, replacement in sorted(changes):
        owner.extend(raw[previous:begin])
        owner.extend(replacement)
        previous = end
    owner.extend(raw[previous:])
    outputs = {"shared.hpp": shared, "owner.cpp": b'#include "shared.hpp"\n' + owner}
    membership: list[dict[str, object]] = []
    for number, bucket in enumerate(buckets):
        name = f"part{number}.cpp"
        body = b"\n".join(raw[item.begin:item.end] for item in sorted(bucket, key=lambda value: value.begin))
        outputs[name] = b'#include "shared.hpp"\nnamespace hart {\n' + body + b"\n}\n"
        membership.extend({"name": item.name, "begin": item.begin, "end": item.end,
                           "partition": name,
                           "sha256": hashlib.sha256(raw[item.begin:item.end]).hexdigest()}
                          for item in sorted(bucket, key=lambda value: value.begin))
    if sorted((row["begin"], row["end"]) for row in membership) != [
            (item.begin, item.end) for item in methods]:
        raise ValueError("incomplete or duplicate method membership")
    return outputs, membership


def verify_manifest(manifest: dict[str, str]) -> None:
    for name, expected in manifest.items():
        if receipts.digest(Path(name)) != expected:
            raise ValueError(f"stale input or output: {name}")


def build_dependencies(directory: Path, compiler: str) -> dict[str, str]:
    """Read Ninja's actual header closure and CMake/compiler-selected native tools."""
    done = subprocess.run(["ninja", "-C", str(directory), "-t", "deps"],
                          capture_output=True, text=True, check=False, timeout=120)
    if done.returncode:
        raise ValueError("cannot read the baseline Ninja dependency database")
    paths = {Path(line[4:]) for line in done.stdout.splitlines() if line.startswith("    ")}
    if not paths:
        raise ValueError("baseline Ninja dependency database is empty")
    paths = {path if path.is_absolute() else directory / path for path in paths}
    for line in (directory / "CMakeCache.txt").read_text(encoding="utf-8").splitlines():
        key, _separator, value = line.partition("=")
        if key in {"CMAKE_AR:FILEPATH", "CMAKE_RANLIB:FILEPATH", "CMAKE_LINKER:FILEPATH"}:
            paths.add(Path(value))
    linker = subprocess.run([compiler, "-print-prog-name=ld"], capture_output=True,
                            text=True, check=True, timeout=30).stdout.strip()
    resolved = shutil.which(linker)
    if resolved is None:
        raise ValueError("cannot identify the compiler-selected linker")
    paths.add(Path(resolved))
    # Retain the selected path so retargeting a symlink cannot hide behind the
    # still-present old target at the final freshness check.
    return {str(path.absolute()): receipts.digest(path) for path in sorted(paths)}


def _measure(name: str, argv: list[str], directory: Path, logs: Path,
             extra_env: dict[str, str] | None = None) -> dict[str, object]:
    log = logs / f"{name}.log"
    started = time.monotonic()
    with (log.open("wb") as stream,
          subprocess.Popen(argv, cwd=directory, env={**os.environ, **(extra_env or {})},
                           stdout=stream, stderr=stream, start_new_session=True) as process):
        try:
            while True:
                pid, status, usage = os.wait4(process.pid, os.WNOHANG)
                if pid:
                    process.returncode = os.waitstatus_to_exitcode(status)
                    break
                if time.monotonic() - started >= 3600:
                    raise TimeoutError(f"{name} timed out; see {log}")  # noqa: TRY301 (shared process-group cleanup)
                time.sleep(0.025)
        except BaseException:
            if process.returncode is None:
                os.killpg(process.pid, signal.SIGKILL)
                _pid, status, _usage = os.wait4(process.pid, 0)
                process.returncode = os.waitstatus_to_exitcode(status)
            raise
    code = process.returncode
    record: dict[str, object] = {"name": name, "command": argv, "exit_code": code,
                                "wall_seconds": round(time.monotonic() - started, 3),
                                "log": str(log), "log_sha256": receipts.digest(log),
                                "user_seconds": usage.ru_utime, "system_seconds": usage.ru_stime,
                                "peak_rss_kib": usage.ru_maxrss}
    receipts.write(log.with_suffix(".time.json"), record)
    if code:
        raise ValueError(f"{name} failed ({code}); see {log}")
    return record


def _suite(path: Path, root: Path) -> dict[str, tuple[str, str]]:
    raw = path.read_bytes()
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise ValueError("CTest report must not contain DTD/entity declarations")
    suite = ET.fromstring(raw)  # noqa: S314 (local CTest output; entity declarations refused)
    result = {}
    for case in suite.findall("testcase"):
        name = case.attrib["name"]
        if name in result:
            raise ValueError(f"duplicate CTest name {name}")
        output = case.findtext("system-out", "").replace(str(root), "<BUILD>")
        result[name] = (case.attrib.get("status", ""), output)
    if not result:
        raise ValueError("CTest recorded no cases")
    return result


def qualify(e: env.Environment, count: int = 4) -> dict[str, object]:
    """Build an isolated CMake overlay and compare the full suite and frozen corpus."""
    baseline = model.verified_build(e)
    root = e.lane_root / "sail-modular"
    root.mkdir(parents=True, exist_ok=True)
    with env.hold_lock(root, "Sail modular qualification"), env.hold_lock(e.build_dir, "baseline comparison"):
        try:
            return _qualify_locked(e, count, root, baseline)
        except (ValueError, OSError, RuntimeError) as exc:
            receipts.write(root / "last-failure.json", {"schema": 1, "verdict": "fail", "error": str(exc)})
            raise


def _qualify_locked(e: env.Environment, count: int, root: Path,
                    baseline: dict[str, object]) -> dict[str, object]:
    import uuid  # noqa: PLC0415 (fresh output for each qualification)

    run = root / uuid.uuid4().hex
    run.mkdir()
    generated, build = run / "generated", run / "build"
    generated.mkdir()
    logs = e.log_dir / f"sail-modular-{e.lane or 'primary'}-{run.name}"
    logs.mkdir(parents=True)
    source, arguments, compiler = compile_arguments(e.build_dir)
    library = libclang_path()
    start = model.build_identity(e)
    declarations, headers = Clang(library).inspect(source, arguments)
    outputs, membership = partition(source.read_bytes(), declarations, count)
    for name, content in outputs.items():
        (generated / name).write_bytes(content)
    manifest = {str(source): receipts.digest(source), **headers,
                **build_dependencies(e.build_dir, compiler),
                str(library): receipts.digest(library),
                **receipts.executables("clang++", "cmake", "ninja", "ctest", "ar"),
                str(e.build_dir / "compile_commands.json"):
                    receipts.digest(e.build_dir / "compile_commands.json")}
    recipe = e.root / "tools/sail-modular/overlay.cmake"
    manifest[str(recipe)] = receipts.digest(recipe)
    manifest.update({str(generated / name): receipts.digest(generated / name) for name in outputs})
    receipts.write(run / "partition.json", {"schema": 1, "partitions": count,
                   "compiler": compiler, "arguments": arguments, "files": manifest,
                   "methods": membership, "declarations": len(declarations)})
    model._seed_tree(e, build)
    stages: list[dict[str, object]] = []
    # A receipt does not bind all installed runtime headers. Rebuild the baseline
    # from clean objects after capturing those headers, then refuse any drift.
    stages.append(_measure("clean-baseline-build", ["cmake", "--build", str(e.build_dir),
                           "--clean-first", "-j", str(min(e.jobs, 4))], e.root, logs,
                           {**env.git_env(e.root), "CCACHE_DISABLE": "1"}))
    verify_manifest(manifest)
    stages.append(_measure("configure", ["cmake", "-S", str(e.model), "-B", str(build), "-GNinja",
                  "-DCMAKE_BUILD_TYPE=RelWithDebInfo", "-DDOWNLOAD_GMP=FALSE",
                  "-DENABLE_RISCV_TESTS=TRUE", *e.compilers, *e.ccache,
                  f"-DTEST_DOWNLOAD_VERSION={model.test_corpus_version(e.model)}",
                  f"-DCMAKE_PROJECT_INCLUDE={recipe}", f"-DVOS_MODULAR_DIR={generated}",
                  f"-DVOS_MODULAR_COUNT={count}"], e.root, logs, env.git_env(e.root)))
    stages.append(_measure("build", ["cmake", "--build", str(build), "-j", str(min(e.jobs, 4))],
                           e.root, logs, {**env.git_env(e.root), "CCACHE_DISABLE": "1"}))
    for suffix in (".cpp", ".h"):
        if receipts.digest(build / f"sail_riscv_model{suffix}") != receipts.digest(
                e.build_dir / f"sail_riscv_model{suffix}"):
            raise ValueError(f"fresh partitioned emission differs from baseline {suffix}")
    suites = []
    for label, directory in (("baseline", e.build_dir), ("partitioned", build)):
        junit = logs / f"{label}.xml"
        stages.append(_measure(label + "-suite", ["ctest", "--test-dir", str(directory),
                              "-j", str(e.test_jobs), "--output-on-failure", "--output-junit", str(junit)],
                               e.root, logs))
        suites.append(_suite(junit, directory))
    if suites[0] != suites[1]:
        names = sorted(name for name in suites[0].keys() | suites[1].keys()
                       if suites[0].get(name) != suites[1].get(name))
        raise ValueError(f"CTest output/status differs: {names[:12]}; see {logs}")
    corpus = differential.load(e.root)
    if not corpus.members:
        raise ValueError("differential corpus is empty")
    comparisons = []
    for member in corpus.members:
        elf = differential.assemble(corpus, member, run / "corpus")
        observed = []
        for label, directory in (("baseline", e.build_dir), ("partitioned", build)):
            simulator = directory / "c_emulator/sail_riscv_sim"
            record = _measure(f"{label}-corpus-{member.name}", [str(simulator), "--config", str(e.profile),
                              "--trace-commit", "--inst-limit", "1000000", str(elf)], e.root, logs)
            stages.append(record)
            raw = Path(str(record["log"])).read_bytes()
            records = trace.normalize_commit(raw.decode("utf-8").splitlines())
            if not records or trace.digest(records) != member.digest or len(records) != member.records:
                raise ValueError(f"corpus {member.name} differs from its frozen trace")
            observed.append(raw)
        if observed[0] != observed[1]:
            raise ValueError(f"corpus output differs for {member.name}")
        comparisons.append({"name": member.name, "elf_sha256": receipts.digest(elf),
                            "output_sha256": hashlib.sha256(observed[0]).hexdigest(),
                            "records": member.records, "trace_digest": member.digest})
    verify_manifest(manifest)
    if start != model.build_identity(e):
        raise ValueError("model inputs or tools changed during qualification")
    report: dict[str, object] = {"schema": 1, "verdict": "pass", "run": str(run),
        "limitations": "Empirical finite-corpus equivalence; not a proof or dynamic extension ABI.",
        "partitions": count, "methods": len(membership), "declarations": len(declarations),
        "build_jobs": min(e.jobs, 4), "compiler_cache": "disabled for both measured builds",
        "identity": start, "manifest": manifest, "baseline_receipt": baseline,
        "suite_cases": len(suites[0]), "corpus": comparisons, "stages": stages,
        "artifacts": receipts.snapshot(build, [*build.glob("libsail_modular_*.a"),
                                               build / "c_emulator/sail_riscv_sim"])}
    receipts.write(run / "qualification.json", report)
    receipts.write(root / "latest.json", report)
    return report
