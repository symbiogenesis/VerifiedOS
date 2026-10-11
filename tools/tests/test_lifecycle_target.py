# SPDX-License-Identifier: Apache-2.0
"""Lifecycle target reports retain the contained compiler's locked native tools."""

import json
import subprocess
import tempfile
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests import compiler_fixture
from tests.harness import Case, ensure
from vos import lifecycle_target as target


def report_retains_locked_tools() -> None:
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        ccomp = compiler_fixture.create(root)
        simulator, config, receipt = (root / name for name in ("simulator", "config", "model.json"))
        simulator.write_bytes(b"simulator")
        config.write_bytes(b"configuration")
        receipt.write_text("{}", encoding="utf-8")
        out = root / "out"
        compiled = SimpleNamespace(stream="stream", said="")
        assembler = SimpleNamespace(symbols={"grant_slots": 512}, assemble=lambda: ([], {}, 0))
        def execute(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess([], 0)
        with ExitStack() as stack:
            replacements = [
                (target.compiler_provenance, "find_root", lambda: root),
                (target.receipts, "inputs", lambda *args: {}),
                (target.kernel_restore, "require_build", lambda *args: None),
                (target.compiler_diff, "compile_c", lambda *args: compiled),
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
            report = target.run(root, ccomp, config, simulator, receipt, out)
        recorded = json.loads((out / "report.json").read_text(encoding="utf-8"))
        expected = target.compiler_provenance.read(ccomp, root / target.compiler_provenance.LOCK)[0]
        ensure(report["compiler_provenance"] == recorded["compiler_provenance"] == expected,
               "lifecycle report dropped or substituted the locked native tool identities")


def cases() -> list[Case]:
    return [Case("lifecycle reports retain the complete locked compiler identity", report_retains_locked_tools)]
