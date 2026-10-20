# SPDX-License-Identifier: Apache-2.0
"""Generated-manifest consumption, independent runtime expectations and refusals."""

import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos import boot, composer, composition, supervisor, supervisor_manifest_join, toolenv

ROOT = TOOLS.parent


@contextmanager
def _sandbox() -> Generator[tuple[Path, dict[str, Any]]]:
    raw = json.loads((ROOT / composition.EXAMPLE).read_bytes())
    paths = {composition.EXAMPLE, boot.CONTRACT, raw["configuration"]["path"],
             *composition.PRODUCERS}
    for member in raw["members"]:
        paths.update(ref["path"] for ref in member["sources"])
        if member["descriptor"] is not None:
            paths.add(member["descriptor"]["path"])
            package = composition._package(ROOT, member)
            if package is not None:
                paths.update(ref["path"] for ref in composition._package_sources(package))
    for producer in raw["producers"]:
        paths.update(ref["path"] for ref in producer["sources"])
    paths.update(f"supervisor/{name}" for name in supervisor.SOURCES)
    paths.update(f"kernel/{name}" for name in
                 (*supervisor.KERNEL_SOURCES, *supervisor.KERNEL_HEADERS))
    paths.update(("supervisor/include/vos_supervisor.h",
                  "supervisor/include/vos_supervisor_effects.h"))
    paths.update(supervisor_manifest_join.INPUTS)
    with tempfile.TemporaryDirectory(prefix="vos-supervisor-manifest-") as temporary:
        root = Path(temporary)
        for relative in paths:
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        composition.emit(root, composition.EXAMPLE, composition.GENERATED)
        yield root, raw


def _refused(call: Callable[[], object], phrase: str) -> None:
    try:
        call()
    except composition.CompositionError as error:
        ensure(phrase in str(error), f"wrong refusal: {error}")
        return
    raise AssertionError(f"expected refusal: {phrase}")


def _published_manifest() -> None:
    with _sandbox() as (root, _raw):
        snapshots = supervisor.checked_manifest(root)
        document = json.loads(snapshots["manifest.json"])
        payload = document["payload"]
        ensure(payload["units"] == ["crypto-core", "storage", "copy-service"],
               "independently expected service roster")
        ensure(payload["order"] == [0, 1, 2] and payload["edges"] == [0, 1, 0],
               "storage starts after, and holds only, crypto-core")
        ensure(document["production_admission"] is False,
               "host consumption supplies no production admission")


def _projection_refusals() -> None:
    for name in supervisor.MANIFESTS:
        with _sandbox() as (root, _raw):
            path = root / composition.GENERATED / name
            original = path.read_bytes()
            if name == "manifest.c":
                changed = original.replace(b"3, {0, 1, 2}", b"3, {0, 2, 1}")
                ensure(changed != original, "C start-order substitution site drifted")
            else:
                raw = json.loads(original)
                raw["payload"]["edges"] = [0, 0, 0]
                changed = composer.canonical_bytes(raw)
            path.write_bytes(changed)
            _refused(lambda: supervisor.checked_manifest(root),
                     f"stale supervisor projection: {name}")
            path.unlink()
            _refused(lambda: supervisor.checked_manifest(root),
                     f"unreadable supervisor projection: {name}")
    with _sandbox() as (root, _raw):
        path = root / "supervisor/src/manifest.c"
        path.write_bytes(path.read_bytes() + b"// changed declared source\n")
        _refused(lambda: supervisor.checked_manifest(root), "stale source binding")


def _compilation_snapshot() -> None:
    with _sandbox() as (root, _raw):
        work = root / "native"
        binary = work / "consumer"
        before = supervisor.checked_manifest(root)

        def compile_snapshot(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            compiled = work / "consumer-manifest.c"
            ensure(str(compiled) in argv, "compiler did not consume the checked snapshot")
            ensure(str(root / "supervisor/src/manifest.c") not in argv,
                   "compiler retained the handwritten manifest")
            ensure(compiled.read_bytes() == before["manifest.c"], "compiler snapshot differs")
            ensure(kwargs["cwd"] == work.resolve(), "compiler inherited a checkout directory")
            return subprocess.CompletedProcess(argv, 0, "", "")

        with patch.object(supervisor.subprocess, "run", side_effect=compile_snapshot) as compiler:
            result = supervisor.build_host(root / "supervisor", binary, "native-cc")
        ensure(result.returncode == 0 and compiler.call_count == 1, "valid snapshot was refused")


def _compilation_drift() -> None:
    for name in (*supervisor.MANIFESTS, "compiled-snapshot"):
        with _sandbox() as (root, _raw):
            work = root / "native"
            binary = work / "consumer"
            changed = (work / "consumer-manifest.c" if name == "compiled-snapshot" else
                       root / composition.GENERATED / name)

            def drift(argv: list[str], *, path: Path = changed,
                      **_kwargs: object) -> subprocess.CompletedProcess[str]:
                path.write_bytes(path.read_bytes() + b" ")
                return subprocess.CompletedProcess(argv, 0, "", "")

            phrase = ("manifest changed during compilation" if name == "compiled-snapshot" else
                      f"stale supervisor projection: {name}")
            with patch.object(supervisor.subprocess, "run", side_effect=drift):
                _refused(lambda root=root, binary=binary:
                         supervisor.build_host(root / "supervisor", binary, "native-cc"),
                         phrase)


def _native_consumer() -> None:
    compiler = supervisor.c_compiler()
    ensure(compiler is not None, "native C compiler is missing")
    if compiler is None:
        return
    work = toolenv.environment(ROOT, sys.platform).parent / "supervisor-manifest-tests"
    work.mkdir(parents=True, exist_ok=True)
    with _sandbox() as (root, raw):
        # The bound legacy comparison source is deliberately not compilable.
        # Only consumption of the generated immutable C can build this control.
        legacy = root / "supervisor/src/manifest.c"
        legacy.write_bytes(b"#error handwritten manifest must not compile\n")
        for member in raw["members"]:
            for index, ref in enumerate(member["sources"]):
                if ref["path"] == "supervisor/src/manifest.c":
                    member["sources"][index] = composition.reference(root, ref["path"])
        (root / composition.EXAMPLE).write_bytes(composer.canonical_bytes(raw))
        composition.emit(root, composition.EXAMPLE, composition.GENERATED)
        with tempfile.TemporaryDirectory(prefix="native-", dir=work) as temporary:
            binary = Path(temporary) / "consumer"
            built = supervisor.build_host(root / "supervisor", binary, compiler)
            ensure(built.returncode == 0, built.stderr)
            ran = subprocess.run([str(binary), "controls"], capture_output=True, text=True,
                                 timeout=60, check=False, cwd=binary.parent.resolve())
            ensure(ran.returncode == 0, ran.stderr)
            ensure("fixed consumer controls" in ran.stderr, "runtime controls did not execute")
            ensure("generated effect executions" in ran.stderr, "kernel-effect controls did not execute")


def _native_manifest_context() -> None:
    with (_sandbox() as (root, _raw),
          tempfile.TemporaryDirectory(prefix="vos-supervisor-manifest-context-") as temporary):
        result = supervisor_manifest_join.run(root, Path(temporary).resolve())
        ensure(result["comparison"] == "passed" and result["production_admission"] is False,
               "native context join changed its evidence scope")
        ensure(set(result["projections"]) == set(supervisor.MANIFESTS),
               "context join did not bind both checked manifest projections")
        ensure(len(result["cases"]) == 5 and
               [case["verdict"] for case in result["cases"]] == ["passed", *["killed"] * 4],
               "compiled context defects lack execution evidence")
        ensure(all(case["compiled"] and case["executed"] for case in result["cases"]),
               "a stillborn mutant was reported detected")
        ensure(set(result["inputs"]) == set(supervisor_manifest_join.INPUTS),
               "context join source identity is incomplete")


def cases() -> list[Case]:
    return [
        Case("published production manifest and independent roster", _published_manifest),
        Case("substituted, missing and stale manifest sources refuse", _projection_refusals),
        Case("compiler consumes checked generated bytes", _compilation_snapshot),
        Case("projection and compiler snapshot drift refuse", _compilation_drift),
        Case("generated manifest runtime order and current epochs", _native_consumer, lane="guest"),
        Case("generated manifest nonblocking trusted lifecycle join",
             _native_manifest_context, lane="guest"),
    ]
