# SPDX-License-Identifier: Apache-2.0
"""Lifecycle target reports retain the contained compiler's locked native tools."""

import json
import struct
import subprocess
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests import compiler_fixture
from tests.harness import TOOLS, Case, ensure
from vos import lifecycle_target as target
from vos import supervisor, toolenv


def report_retains_locked_tools(generated: bool = False, drift: str = "") -> None:
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        ccomp = compiler_fixture.create(root)
        simulator, config, receipt = (root / name for name in ("simulator", "config", "model.json"))
        simulator.write_bytes(b"simulator")
        config.write_bytes(b"configuration")
        receipt.write_text("{}", encoding="utf-8")
        out = root / "out"
        compiled = SimpleNamespace(stream="stream", said="")
        snapshot = supervisor.checked_manifest(TOOLS.parent)
        def compile_checked(args: list[str], source: Path, work: Path) -> SimpleNamespace:
            if generated and "-DVOS_JOIN_KERNEL" in args:
                ensure(source == out / "manifest-target.c", "generated mode compiled its comparison policy")
                ensure((out / "manifest.c").read_bytes() == snapshot["manifest.c"],
                       "target compilation did not consume the checked C bytes")
                ensure('#include "manifest.c"' in source.read_text(encoding="utf-8"),
                       "compiled wrapper omitted the generated object")
                if drift:
                    changed = out / ("manifest-target.c" if drift == "unit" else drift)
                    changed.write_bytes(changed.read_bytes() + b" ")
            return compiled
        assembler = SimpleNamespace(symbols={"grant_slots": 512}, assemble=lambda: ([], {}, 0))
        def execute(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess([], 0)
        with ExitStack() as stack:
            replacements = [
                (target.compiler_provenance, "find_root", lambda: root),
                (target.receipts, "inputs", lambda *args: {}),
                (target.kernel_restore, "require_build", lambda *args: None),
                (target.compiler_diff, "compile_c", compile_checked),
                (target.supervisor, "checked_manifest", lambda *args: snapshot),
                (target.compiler_diff, "_compiled_json", lambda *args: {}),
                (target, "instruction_counts", lambda *args: {}),
                (target, "longest_path", lambda *args: {"padded_boundary_steps": 1}),
                (target, "reaction_path", lambda *args: {}),
                (target.boot_handoff, "timer_windows", lambda *args: (1, 2)),
                (target, "source", lambda *args, **kwargs: "fixture assembly"),
                (target.asm, "Assembler", lambda *args, **kwargs: assembler),
                (target.kernel_target, "revocation_window", lambda *args: (512, 1)),
                (target.jsonc, "load", lambda *args: {"platform": {}}),
                (target.image, "write_elf", lambda path, *args: path.write_bytes(b"elf")),
                (target.subprocess, "run", execute),
                (target.compiler_diff, "htif_verdict", lambda *args: ("pass", 0, "")),
                (target, "observations", lambda *args: {"ok": True}),
            ]
            for module, member, replacement in replacements:
                stack.enter_context(patch.object(module, member, replacement))
            report = target.run(root, ccomp, config, simulator, receipt, out,
                                generated_manifest=generated)
        recorded = json.loads((out / "report.json").read_text(encoding="utf-8"))
        expected = target.compiler_provenance.read(ccomp, root / target.compiler_provenance.LOCK)[0]
        ensure(report["compiler_provenance"] == recorded["compiler_provenance"] == expected,
               "lifecycle report dropped or substituted the locked native tool identities")
        if generated:
            ensure(report["generated_manifest"] is True and report["production_admission"] is False,
                   "component receipt promoted production admission")
            ensure(report["production_manifest"] == {
                name: target.receipts.digest(out / name) for name in snapshot},
                "target receipt lost checked manifest identities")


def generated_snapshot_drift() -> None:
    for name in ("manifest.c", "manifest.json", "unit"):
        try:
            report_retains_locked_tools(True, name)
        except ValueError as error:
            ensure("changed during" in str(error), f"unexpected snapshot refusal: {error}")
        else:
            raise AssertionError(f"target compilation accepted drift: {name}")


def generated_layout() -> None:
    snapshot = supervisor.checked_manifest(TOOLS.parent)
    payload = json.loads(snapshot["manifest.json"])["payload"]
    words = struct.unpack("<80I", target.manifest_bytes(payload))
    ensure(words[0] == 3 and words[1:4] == (0, 1, 2) and words[17:20] == (0, 1, 0),
           "target layout lost independently expected service order/authority")
    ensure(words[33:41] == (3,) * 8 and words[41:49] == (1,) * 8,
           "target layout lost generated detector thresholds")
    ensure(words[57:65] == (2, 3, 8, 4, 1, 2, 3, 5) and words[77:] == (5, 3, 7),
           "target layout replaced the composition's policy with the long-delay comparison")
    payload["order"] = [0, 2, 1]
    try:
        target.manifest_bytes(payload)
    except ValueError as error:
        ensure("three-unit" in str(error), "changed roster received an unrelated refusal")
    else:
        raise AssertionError("different roster was accepted by a fixed component account")


def locked_producer_refusal() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-manifest-producer-refusal-") as name:
        root = Path(name)
        ccomp = compiler_fixture.create(root)
        result_path = ccomp.parent / "build-result.json"
        result = json.loads(result_path.read_bytes())
        result["toolchain"]["lock_sha256"] = "0" * 64
        result_path.write_text(json.dumps(result), encoding="utf-8")
        lock = root / target.compiler_provenance.LOCK
        lock_before = lock.read_bytes()
        out = root / "out"
        with patch.object(target.compiler_provenance, "find_root", lambda: root), \
                patch.object(target.compiler_diff, "compile_c") as compile_control:
            try:
                target.run(root, ccomp, root / "config", root / "simulator",
                           root / "model-receipt", out, generated_manifest=True)
            except ValueError as error:
                ensure(str(error) == "contained compiler toolchain does not bind the recorded lock",
                       "invalid producer received an unrelated refusal")
            else:
                raise AssertionError("generated target bypassed the locked producer preflight")
            ensure(compile_control.call_count == 0, "rejected producer compiled a target")
        record = json.loads((out / "report.json").read_bytes())
        ensure(record["status"] == "refused" and record["stage"] == "compiler-provenance" and
               record["ok"] is False and record["production_admission"] is False and
               record["milestone_acceptance"] == "open" and record["target_execution"] is False,
               "producer refusal supplied acceptance")
        ensure(lock.read_bytes() == lock_before, "target refusal changed the locked toolchain")


def native_generated_unit() -> None:
    compiler = supervisor.c_compiler()
    ensure(compiler is not None, "native C compiler is missing")
    if compiler is None:
        return
    report_dir = toolenv.environment(TOOLS.parent, sys.platform).parent / "supervisor-manifest-native"
    report_dir.mkdir(parents=True, exist_ok=True)
    source_snapshot = target.receipts.inputs(TOOLS.parent, *target.INPUTS, "tools/tests/test_lifecycle_target.py")
    controls = []
    with tempfile.TemporaryDirectory(prefix="vos-manifest-target-native-") as name:
        work = Path(name).resolve()
        version = subprocess.run([compiler, "--version"], capture_output=True, text=True,
                                 timeout=60, check=False, cwd=work)
        ensure(version.returncode == 0, "native compiler did not report its identity")
        unit, snapshot, expected = target.manifest_unit(TOOLS.parent, work)
        unit.write_text(unit.read_text(encoding="utf-8") + '''
#include <stdio.h>
int main(void) {
    struct vos_supervisor_manifest m;
    vos_join_manifest(&m);
    return fwrite(&m, 1, sizeof(m), stdout) == sizeof(m) ? 0 : 1;
}
''', encoding="utf-8", newline="\n")
        for mutated in (False, True):
            if mutated:
                changed = snapshot["manifest.c"].replace(b"4, {1, 2, 3, 5}", b"4, {2, 2, 3, 5}")
                ensure(changed != snapshot["manifest.c"], "generated policy mutation site drifted")
                (work / "manifest.c").write_bytes(changed)
            binary = work / ("mutant" if mutated else "control")
            built = subprocess.run([compiler, *supervisor.CFLAGS, "-DVOS_JOIN_KERNEL",
                                    f"-I{TOOLS.parent / 'supervisor/include'}",
                                    f"-I{TOOLS.parent / 'kernel/include'}", str(unit), "-o", str(binary)],
                                   capture_output=True, text=True, timeout=60, check=False, cwd=work)
            ensure(built.returncode == 0, f"generated target wrapper did not compile: {built.stderr}")
            ran = subprocess.run([str(binary)], capture_output=True, timeout=60, check=False, cwd=work)
            ensure(ran.returncode == 0, "generated wrapper did not run")
            ensure((ran.stdout == expected) is not mutated,
                   "native compiled manifest did not match its independent target layout")
            controls.append({"mutated": mutated, "binary_sha256": target.receipts.digest(binary),
                             "compiled_manifest_sha256": target.receipts.digest(work / "manifest.c"),
                             "emitted_layout_sha256": target.hashlib.sha256(ran.stdout).hexdigest(),
                             "exit_code": ran.returncode, "layout_matches": ran.stdout == expected})
        (work / "manifest.c").write_bytes(snapshot["manifest.c"])
        target.manifest_unchanged(TOOLS.parent, work, snapshot)
        ensure(source_snapshot == target.receipts.inputs(TOOLS.parent, *target.INPUTS,
                                                        "tools/tests/test_lifecycle_target.py"),
               "native wrapper source changed during compilation or execution")
        target.receipts.write(report_dir / "report.json", {
            "ok": True, "evidence": "native C wrapper and independently computed object layout",
            "compiler": {"path": compiler, "sha256": target.receipts.digest(Path(compiler)),
                         "reported_version": version.stdout.splitlines()[0]},
            "manifest": {name: target.hashlib.sha256(data).hexdigest() for name, data in snapshot.items()},
            "sources": source_snapshot,
            "expected_layout_sha256": target.hashlib.sha256(expected).hexdigest(),
            "controls": controls, "target_execution": False, "production_admission": False,
            "milestone_acceptance": "open"})


def cases() -> list[Case]:
    return [
        Case("lifecycle reports retain the complete locked compiler identity", report_retains_locked_tools),
        Case("generated target retains checked projection and locked producer identities",
             lambda: report_retains_locked_tools(True)),
        Case("generated C, JSON and compilation-unit drift refuse", generated_snapshot_drift),
        Case("independent generated target layout and roster refusal", generated_layout),
        Case("locked producer refusal is recorded before target compilation", locked_producer_refusal),
        Case("native generated target wrapper and live policy mutation", native_generated_unit, lane="guest"),
    ]
