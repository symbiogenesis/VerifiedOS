# SPDX-License-Identifier: Apache-2.0
"""Native checked-manifest/reactor/trusted-decoder join, without target acceptance."""

import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any, Final

from vos import supervisor

INPUTS: Final = (
    "supervisor/include/vos_supervisor.h", "supervisor/include/vos_supervisor_context.h",
    "supervisor/include/vos_supervisor_effects.h", "supervisor/include/vos_context_layout.h",
    "supervisor/src/supervisor.c", "supervisor/src/context.c",
    "supervisor/test/manifest_context.c", "kernel/include/vos_kernel.h",
    "kernel/include/vos_platform.h", "kernel/include/vos_effects.h",
    "kernel/include/vos_lifecycle.h", "kernel/src/context.c", "kernel/src/effects.c",
    "kernel/src/lifecycle.c", "tools/vos/supervisor_manifest_join.py",
    "tools/vos/supervisor.py",
)
SOURCES: Final = (
    "supervisor/src/supervisor.c", "supervisor/src/context.c",
    "supervisor/test/manifest_context.c", "kernel/src/context.c",
    "kernel/src/effects.c", "kernel/src/lifecycle.c",
)
MUTATIONS: Final = (
    ("start order", "supervisor/src/supervisor.c",
     "plan.starts[plan.count].unit = unit;",
     "plan.starts[plan.count].unit = m->units - 1U - unit;"),
    ("retired grant", "supervisor/src/supervisor.c",
     "plan.starts[plan.count].grants = m->edges[unit] & ~epoch->retired[unit];",
     "plan.starts[plan.count].grants = m->edges[unit];"),
    ("acknowledgment watermark", "supervisor/src/context.c",
     "s->acknowledged_sequence = ack[VOS_CTX_ACK_SEQUENCE];",
     "s->acknowledged_sequence = ack[VOS_CTX_ACK_SEQUENCE] + 1U;"),
    ("early backoff", "supervisor/src/context.c",
     "restart && ack[VOS_CTX_ACK_NOW] < ack[VOS_CTX_ACK_DEADLINE]", "0"),
)


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unchanged(lane: Path, snapshots: dict[str, bytes]) -> None:
    if any((lane / name).read_bytes() != data for name, data in snapshots.items()):
        raise ValueError("native join compiled snapshot changed during execution")


def run(root: Path, work: Path, compiler: str | None = None) -> dict[str, Any]:
    """Retain the exact compiled snapshots and finite controls in a temp lane.

    Mutants must compile and execute before a nonzero control verdict counts as
    detected. Compiler/source drift refuses publication of a successful receipt.
    """
    started = time.monotonic()
    root = root.resolve()
    if not work.is_absolute() or work.resolve().is_relative_to(root):
        raise ValueError("native join work directory must be absolute and outside the checkout")
    work = work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    report = work / "report.json"
    report.write_text('{"schema":1,"comparison":"incomplete","production_admission":false}\n',
                      encoding="utf-8", newline="")
    found = compiler or supervisor.c_compiler()
    if found is None:
        raise ValueError("native supervisor join requires a C compiler")
    compiler_path = Path(found).resolve()
    compiler_before = compiler_path.read_bytes()
    version = subprocess.run([str(compiler_path), "--version"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", timeout=30,
                             check=False, cwd=work)
    (work / "compiler-version.log").write_text(version.stdout + version.stderr,
                                              encoding="utf-8", newline="")
    if version.returncode != 0 or not version.stdout.strip():
        raise ValueError("native supervisor compiler did not report its version")
    manifest = supervisor.checked_manifest(root)
    inputs = {name: (root / name).read_bytes() for name in INPUTS}
    cases: list[dict[str, Any]] = []
    for index, mutation in enumerate((None, *MUTATIONS)):
        lane = work / f"case-{index}"
        lane.mkdir()
        staged: dict[str, bytes] = {}
        for name, data in inputs.items():
            destination = lane / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            compiled_data = data
            if mutation is not None and name == mutation[1]:
                old, new = mutation[2].encode(), mutation[3].encode()
                if data.count(old) != 1:
                    raise ValueError(f"{mutation[0]} mutation site drifted")
                compiled_data = data.replace(old, new, 1)
            destination.write_bytes(compiled_data)
            staged[name] = compiled_data
        for name, data in manifest.items():
            (lane / name).write_bytes(data)
            staged[name] = data
        executable = lane / "manifest-context"
        arguments = [str(compiler_path), *supervisor.CFLAGS, "-DVOS_HOST_MODEL",
                     "-DVOS_EFFECTS_TYPED", "-DVOS_KERNEL_EFFECT_UNITS=3",
                     "-I" + str(lane / "supervisor/include"),
                     "-I" + str(lane / "kernel/include"),
                     str(lane / "manifest.c"), *(str(lane / name) for name in SOURCES),
                     "-o", str(executable)]
        compiled = subprocess.run(arguments, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=60,
                                  check=False, cwd=lane)
        (lane / "compile.log").write_text(compiled.stdout + compiled.stderr,
                                          encoding="utf-8", newline="")
        if compiled.returncode != 0:
            raise ValueError(f"native join case {index} did not compile: {compiled.stderr}")
        _unchanged(lane, staged)
        executable_before = executable.read_bytes()
        executed = subprocess.run([str(executable)], capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", timeout=60,
                                  check=False, cwd=lane)
        (lane / "execute.log").write_text(executed.stdout + executed.stderr,
                                          encoding="utf-8", newline="")
        _unchanged(lane, staged)
        if executable.read_bytes() != executable_before:
            raise ValueError("native join binary changed during execution")
        name = "unchanged producer/consumer control" if mutation is None else mutation[0]
        if ((mutation is None and (executed.returncode != 0 or executed.stdout !=
                                   "ok generated manifest nonblocking lifecycle join\n")) or
                (mutation is not None and (executed.returncode != 1 or
                                           "FAIL generated context join line " not in executed.stderr))):
            raise ValueError(f"native join {name} returned an unexpected control verdict: "
                             f"{executed.returncode}: {executed.stdout}{executed.stderr}")
        cases.append({"name": name, "compiled": True, "executed": True,
                      "verdict": "passed" if mutation is None else "killed",
                      "returncode": executed.returncode,
                      "directory": str(lane), "compile_arguments": arguments,
                      "compile_returncode": compiled.returncode,
                      "compile_log": str(lane / "compile.log"),
                      "execution_arguments": [str(executable)],
                      "execution_cwd": str(lane),
                      "execution_log": str(lane / "execute.log"),
                      "binary_sha256": _digest(executable_before),
                      "compiled_sources": {name: _digest((lane / name).read_bytes())
                                           for name in SOURCES},
                      "manifest_sha256": _digest((lane / "manifest.c").read_bytes())})
    if supervisor.checked_manifest(root) != manifest:
        raise ValueError("native join manifest changed during execution")
    if any((root / name).read_bytes() != data for name, data in inputs.items()):
        raise ValueError("native join source changed during execution")
    if compiler_path.read_bytes() != compiler_before:
        raise ValueError("native join compiler changed during execution")
    result: dict[str, Any] = {
        "schema": 1, "comparison": "passed", "production_admission": False,
        "seconds": time.monotonic() - started,
        "inputs": {name: _digest(data) for name, data in inputs.items()},
        "projections": {name: _digest(data) for name, data in manifest.items()},
        "compiler": {"path": str(compiler_path), "sha256": _digest(compiler_before),
                     "version": version.stdout.strip(), "version_returncode": version.returncode},
        "cases": cases,
        "limits": ["native host roots, admitted clock and resident scrub are test premises",
                   "no authenticated measured-image handoff, target compiler qualification or target execution",
                   "full-roster boot/fault observations and production admission remain open"],
    }
    report.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n",
                      encoding="utf-8", newline="")
    return result
