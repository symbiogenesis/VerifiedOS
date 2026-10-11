# SPDX-License-Identifier: Apache-2.0
"""The kernel target's report retains contained native tools apart from host C."""

import json
import subprocess
import tempfile
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests import compiler_fixture
from tests.harness import Case, ensure
from vos import kernel_target as target


def report_retains_locked_tools() -> None:
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        ccomp = compiler_fixture.create(root)
        simulator, receipt, binary = (root / name for name in ("simulator", "model.json", "host"))
        simulator.write_bytes(b"simulator")
        receipt.write_text("{}", encoding="utf-8")
        binary.write_bytes(b"host C")
        out = root / "out"
        out.mkdir()
        (out / "sram.bin").write_bytes(b"payload")
        (out / "handoff.bin").write_bytes(b"handoff")
        lay = {"BRINGUP_MMODE_LOAD_BASE": 0, "BRINGUP_MMODE_REGION_BYTES": 1024,
               "INIT_MAGIC": 1, "BOOT_PUBLIC_KEY_BYTES": 1,
               "BOOT_SIGNATURE_BYTES": 1, "BOOT_DIGEST_BYTES": 1}
        symbols = {"retired_object": target.DATA_OFFSET + 64, "tohost": 100}
        built = SimpleNamespace(payload=b"payload", symbols=symbols)
        compiled = SimpleNamespace(exit_code=0, stream="stream", said="", argv=["ccomp"],
                                   stream_sha256="s", preprocessed=SimpleNamespace(sha256="p"))
        release = {"verdict": "release", "released": "1", "generation": "g",
                   "device": "d", "chain": "c"}
        signer = SimpleNamespace(roots={target.boot_handoff.LIFECYCLES[0]: b"root"},
                                 sign=lambda *args: b"signature", identity=dict)
        bh = target.boot_handoff
        with ExitStack() as stack:
            replacements = [
                (target.compiler_provenance, "find_root", lambda: root),
                (target.receipts, "inputs", lambda *args: {}),
                (target.shutil, "which", lambda *args: str(binary)),
                (target.kernel_restore, "require_build", lambda *args: None),
                (target.compiler_diff, "compile_c", lambda *args: compiled),
                (bh, "layout", lambda *args: lay), (bh, "timer_windows", lambda *args: (1, 2)),
                (target, "revocation_window", lambda *args: (3, 1)),
                (target, "consumer_source", lambda *args: "consumer"),
                (bh, "scheduled_mmode", lambda *args, **kwargs: "stage"),
                (bh, "assemble_mmode", lambda *args, **kwargs: built),
                (target, "SlhSigner", lambda *args, **kwargs: signer),
                (target.asm, "assemble_file", lambda *args: None),
                (bh, "emulate", lambda *args, **kwargs: SimpleNamespace(
                    verdict="success", signature=(0, 1 << 32, 1))),
                (bh, "build_image", lambda *args, **kwargs: b"image"),
                (bh, "compile_rot_stage", lambda *args: (binary, {"cc": "host identity"})),
                (bh, "rot_stage", lambda *args, **kwargs: release),
                (bh, "_record_findings", lambda *args: []),
                (bh, "expected_registers", lambda *args: ("g", "d", "c")),
                (target, "snapshot_source", lambda *args: "snapshot"),
                (bh, "placed_elf", lambda *args: args[-1].write_bytes(b"elf")),
                (target.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(
                    [], 0, stdout="", stderr="")),
                (target, "observations", lambda *args: {"fixture": True}),
                (target.compiler_diff, "htif_verdict", lambda *args: ("pass", 0, "")),
                (target, "execute_controls", lambda *args: [{"matched": True}]),
            ]
            for module, member, replacement in replacements:
                stack.enter_context(patch.object(module, member, replacement))
            report = target.run(root, ccomp, [], simulator, receipt, out, 1)
        recorded = json.loads((out / "report.json").read_text(encoding="utf-8"))
        expected = target.compiler_provenance.read(ccomp, root / target.compiler_provenance.LOCK)[0]
        ensure(report["compiler_provenance"] == recorded["compiler_provenance"] == expected,
               "kernel report dropped or substituted contained native tool identities")
        ensure(recorded["host_compiler"] == {"cc": "host identity"},
               "contained native tools replaced the independent host C identity")


def cases() -> list[Case]:
    return [Case("kernel reports retain the complete locked compiler identity", report_retains_locked_tools)]
