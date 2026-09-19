# SPDX-License-Identifier: Apache-2.0
"""Regeneration, owner drift and real-emulator negative controls for M5.3c."""

import json
import sys
import tempfile
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import asm, block_authority, differential, env, jsonc
from vos.cli.model import _run_member

ROOT = TOOLS.parent


def _regeneration() -> None:
    ensure(not block_authority.check(ROOT), "generated authority member drifted from owners")
    source = block_authority.emit(ROOT)
    ensure(differential.count_checks(source) == 10, "the finite campaign lost a case")
    manifest = differential.load(ROOT)
    members = [m for m in manifest.members if m.name == "block-authority"]
    ensure(len(members) == 1 and members[0].records > 0 and bool(members[0].digest),
           "the authority member must retain measured trace evidence")


def _owner_drift() -> None:
    scratch = ((ROOT / "out") if sys.platform == "win32" else
               env.load(toolchain=False).lane_root) / "block-authority-tests"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        root = Path(temporary)
        for name in block_authority.OWNERS:
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text((ROOT / name).read_text(encoding="utf-8"),
                              encoding="utf-8", newline="\n")
        artifact = root / block_authority.ARTIFACT
        artifact.parent.mkdir(parents=True)
        artifact.write_text(block_authority.emit(root), encoding="utf-8", newline="\n")
        path = root / block_authority.CONFIG
        original = path.read_text(encoding="utf-8")
        # A changed fixture changes expected readback, not just an input receipt.
        raw = json.loads(jsonc.strip_comments(original))
        raw["platform"]["blkdev"]["backing"][64] ^= 1
        path.write_text(json.dumps(raw), encoding="utf-8", newline="\n")
        ensure(bool(block_authority.check(root)), "changed backing was not detected")
        raw["platform"]["blkdev"]["supported"] = False
        path.write_text(json.dumps(raw), encoding="utf-8", newline="\n")
        try:
            block_authority.emit(root)
        except ValueError as exc:
            ensure("enabled device" in str(exc), f"wrong disabled-device refusal: {exc}")
        else:
            raise AssertionError("disabled device admitted as authority evidence")
        path.write_text(original, encoding="utf-8", newline="\n")
        owner = root / block_authority.PERMISSIONS
        owner.write_text(owner.read_text(encoding="utf-8").replace(
            "function cap_permit_load(", "function removed_permit_load("),
            encoding="utf-8", newline="\n")
        try:
            block_authority.emit(root)
        except ValueError as exc:
            ensure("permit-load" in str(exc), f"wrong missing-owner refusal: {exc}")
        else:
            raise AssertionError("missing permission owner silently admitted")


def _executor_controls() -> None:
    environment = env.load()
    source = block_authority.emit(ROOT)
    payload = bytes((0xA3 + i * 17) % 256 for i in range(8))
    expected = int.from_bytes(payload, "little")
    controls = (
        ("positive", source, "PASS", ""),
        ("wrong-byte", source.replace(f"li t2, {expected}", f"li t2, {expected ^ 1}", 1),
         "FAIL", "check 1 failed"),
        ("missing-refusal", source.replace("sd t2, 0(c10)", "sd t2, 40(c9)", 1),
         "FAIL", "check 2 failed"),
        ("wrong-cause", source.replace("li t5, 28", "li t5, 27", 1),
         "FAIL", "check 2 failed"),
    )
    directory = environment.lane_root / "block-authority-controls"
    directory.mkdir(parents=True, exist_ok=True)
    for name, text, expected_verdict, expected_detail in controls:
        if name != "positive":
            ensure(text != source, f"{name} mutation did not apply")
        assembly = directory / f"{name}.s"
        elf = directory / f"{name}.elf"
        assembly.write_text(text, encoding="utf-8", newline="\n")
        asm.assemble_file(assembly, elf)
        verdict, detail, records = _run_member(environment, environment.profile, elf, 30)
        ensure(verdict == expected_verdict and expected_detail in detail and bool(records),
               f"{name}: expected {expected_verdict} {expected_detail}, got {verdict} {detail}")


def cases() -> list[Case]:
    return [Case("generated member and measured membership", _regeneration),
            Case("fixture drift and unreadable owners fail closed", _owner_drift),
            Case("real emulator and HTIF negative controls", _executor_controls,
                 slow=True, lane="toolchain")]
