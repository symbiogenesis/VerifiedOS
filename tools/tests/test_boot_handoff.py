# SPDX-License-Identifier: Apache-2.0
"""M3.5's boot-handoff harness: the owner agreement, the image builder, and a real run."""

import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos import asm, boot_release_target, boot_target, env, toolenv
from vos import boot_handoff as bh

ROOT = TOOLS.parent


def _owners_agree() -> None:
    ensure(bh.contract_findings(ROOT) == [], f"contract drift: {bh.contract_findings(ROOT)}")
    lay = bh.layout(ROOT)
    built = bh.assemble_mmode(ROOT)
    ensure(bh.composition_findings(lay, built) == [], "the image and vos_boot.h disagree")
    ensure(bh.entry_table_findings(ROOT, built) == [],
           f"permission drift: {bh.entry_table_findings(ROOT, built)}")
    ensure(lay["BOOT_HEADER_BYTES"] == lay["BOOT_HDR_SIGNATURE"] + lay["BOOT_SIGNATURE_BYTES"],
           "the header length is not the signature's end")
    ensure(lay["BOOT_SIGNATURE_BYTES"] == 29792, "not FIPS 205's SLH-DSA-SHAKE-256s size")


def _sandbox(names: tuple[str, ...]) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    scratch = toolenv.environment(ROOT, sys.platform).parent / "boot-handoff-tests"
    scratch.mkdir(parents=True, exist_ok=True)
    holder = tempfile.TemporaryDirectory(dir=scratch)
    root = Path(holder.name)
    for name in names:
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    return holder, root


def _drift_is_reported() -> None:
    holder, root = _sandbox((bh.HEADER, bh.CONTRACT))
    with holder:
        contract = root / bh.CONTRACT
        original = contract.read_text(encoding="utf-8")
        edits = (
            ("| `header.stage` | 8 | 8 |", "| `header.stage` | 16 | 8 |", "header.stage"),
            ("| `record.chain` | 168 | 32 |", "| `record.chain` | 168 | 31 |", "record.chain"),
            ("| `composition.handoff_base` | 0x80010000 |",
             "| `composition.handoff_base` | 0x80020000 |", "composition.handoff_base"),
            ("| `init.hart` | 24 | 8 |", "| `init.hart` | 16 | 8 |", "init.hart"),
            ("| `below-floor` | version F - 1 | `refuse-floor` |",
             "| `below-floor` | version F - 1 | `refuse-length` |", "below-floor"),
            ("| `mutant-mepcc-kept` | stage clears MEPCC through `cnull` | `release` | "
             "`FAILURE: 10` |", "", "mutant-mepcc-kept"),
        )
        for old, new, name in edits:
            ensure(old in original, f"the drift anchor for {name} is gone from the contract")
            contract.write_text(original.replace(old, new, 1), encoding="utf-8", newline="\n")
            found = bh.contract_findings(root)
            ensure(any(name in finding for finding in found),
                   f"changing {name} was not reported: {found}")
        contract.write_text(original, encoding="utf-8", newline="\n")
        ensure(bh.contract_findings(root) == [], "the restored sandbox still reports drift")
        built = bh.assemble_mmode(ROOT)
        ensure(bh.entry_table_findings(root, built) == [], "the sandbox's permissions drift")
        contract.write_text(original.replace("| `c11` |", "| `c11` (moved) |", 1),
                            encoding="utf-8", newline="\n")
        found = bh.entry_table_findings(root, built)
        ensure(any("no permission row for `c11`" in finding for finding in found),
               f"dropping c11's permission row was not reported: {found}")
        stack = next(line for line in original.splitlines() if line.startswith("| `csp` / `c2` |"))
        contract.write_text(original.replace(stack, stack.replace("`0xfe`", "`0xff`"), 1),
                            encoding="utf-8", newline="\n")
        found = bh.entry_table_findings(root, built)
        ensure(any("PERMS_STACK_LOCAL" in finding for finding in found),
               f"a changed stack permission was not reported: {found}")
        contract.write_text(original, encoding="utf-8", newline="\n")
        header = root / bh.HEADER
        header.write_text(header.read_text(encoding="utf-8").replace(
            "#define VOS_BOOT_DIGEST_BYTES 32u", "#define VOS_BOOT_DIGEST_BYTES VOS_UNDEFINED"),
            encoding="utf-8", newline="\n")
        try:
            bh.header_constants(root)
        except ValueError as exc:
            ensure("VOS_UNDEFINED" in str(exc), f"wrong refusal: {exc}")
        else:
            raise AssertionError("an undefined macro was evaluated")


def _descriptor_counts_are_held() -> None:
    lay = bh.layout(ROOT)
    built = bh.assemble_mmode(ROOT)
    ensure(bh.descriptor_findings(lay, built) == [], "the fixture's descriptor drifts")
    at = built.symbols["init_desc"] - lay["BRINGUP_MMODE_LOAD_BASE"]
    count = at + lay["INIT_PARTITION_COUNT_AT"]
    claimed = bh.Assembled(bh.put_word(built.payload, count, 1), built.symbols, built.constants)
    found = bh.descriptor_findings(lay, claimed)
    ensure(any("counts imply" in finding for finding in found),
           f"a partition count with no record was not reported: {found}")
    magic = at + lay["INIT_MAGIC_AT"]
    renamed = bh.Assembled(bh.put_word(built.payload, magic, 0), built.symbols, built.constants)
    ensure(any("magic" in finding for finding in bh.descriptor_findings(lay, renamed)),
           "a wrong descriptor magic was not reported")


def _image_builder() -> None:
    lay = bh.layout(ROOT)
    payload = bytes(range(256)) * 3
    signer = bh.root_key("production")
    data = bh.build_image(lay, payload, security_version=7, signer=signer)
    header = lay["BOOT_HEADER_BYTES"]

    def word(at: int) -> int:
        return int.from_bytes(data[at:at + 8], "little")

    ensure(len(data) == header + len(payload) and data[header:] == payload, "payload misplaced")
    ensure(data[:8] == b"VOSBOOT1", "the magic is not the bytes VOSBOOT1")
    ensure(word(lay["BOOT_HDR_STAGE"]) == lay["BOOT_STAGE_MMODE_IMAGE"], "stage")
    ensure(word(lay["BOOT_HDR_SECURITY_VERSION"]) == 7, "security version")
    ensure(word(lay["BOOT_HDR_PAYLOAD_OFFSET"]) == header, "payload offset")
    ensure(word(lay["BOOT_HDR_PAYLOAD_LENGTH"]) == len(payload), "payload length")
    at = lay["BOOT_HDR_PAYLOAD_DIGEST"]
    ensure(data[at:at + 32] == hashlib.shake_256(payload).digest(32), "payload digest")
    signature = data[lay["BOOT_HDR_SIGNATURE"]:header]
    ensure(signature == bh.fixture_signature(lay, signer, data[:lay["BOOT_SIGNED_BYTES"]]),
           "the fixture signature is not over the signed prefix")
    ensure(signature != bh.fixture_signature(lay, bh.root_key("development"),
                                             data[:lay["BOOT_SIGNED_BYTES"]]),
           "two roots produce one fixture signature")


def _explicit_signer() -> None:
    lay = bh.layout(ROOT)
    seen: list[tuple[bytes, bytes]] = []

    def sign(public: bytes, message: bytes) -> bytes:
        seen.append((public, message))
        return bytes([17]) * lay["BOOT_SIGNATURE_BYTES"]

    pk, payload = bytes([19]) * lay["BOOT_PUBLIC_KEY_BYTES"], b"placed payload"
    signed = bh.build_image(lay, payload, security_version=2, signer=pk, sign=sign)
    ensure(seen == [(pk, signed[:lay["BOOT_SIGNED_BYTES"]])],
           "the signer did not receive the exact signed prefix and selected root")
    ensure(signed[lay["BOOT_HDR_SIGNATURE"]:lay["BOOT_HEADER_BYTES"]]
           == bytes([17]) * lay["BOOT_SIGNATURE_BYTES"],
           "the supplied signature was overwritten by the fixture")
    try:
        bh.build_image(lay, payload, security_version=2, signer=pk, sign=lambda p, m: b"short")
    except ValueError:
        pass
    else:
        raise AssertionError("a short signer result resized the fixed header")


def _scheduled_producer() -> None:
    compare, clock = bh.timer_windows(ROOT)
    stage = bh.scheduled_mmode(ROOT)
    ensure(compare != clock and compare % 8 == 0 and clock % 8 == 0,
           "timer windows must be distinct and aligned")
    ensure(f"li      t0, {compare:#x}" in stage and f"li      t0, {clock:#x}" in stage,
           "scheduled producer missed its profile-derived windows")
    kernel = (ROOT / bh.FIXTURE).read_text(encoding="utf-8")
    ensure(bh.assemble_mmode(ROOT, kernel_text=kernel).payload == bh.assemble_mmode(ROOT).payload,
           "explicit kernel substitution changed the unchanged fixture")
    holder, root = _sandbox((bh.MAIN_CONFIG, "model/model/sys/platform.sail"))
    with holder:
        model = root / "model/model/sys/platform.sail"
        model.write_text(model.read_text(encoding="utf-8").replace("let MTIME_BASE ", "let REMOVED "),
                         encoding="utf-8", newline="\n")
        try:
            bh.timer_windows(root)
        except ValueError as exc:
            ensure("MTIME_BASE" in str(exc), "an absent timer owner failed for another reason")
        else:
            raise AssertionError("missing timer offset silently defaulted")


def _target_stack_budget() -> None:
    stream = "cincoffsetimm c2, c2, -16\nli x31, -2528\ncincoffset c2, c2, x31\n"
    ensure(boot_target.stack_ceiling(stream) == 2544,
           "large target frame was omitted from the declared stack ceiling")
    for source in ("", stream + "cincoffset c2, c2, x15\n",
                   "cincoffsetimm c2, c2, 16\n"):
        try:
            boot_target.stack_ceiling(source)
        except ValueError:
            pass
        else:
            raise AssertionError("an unknown stack allocation supplied a budget")


def _target_release_composition() -> None:
    lay = bh.layout(ROOT)
    built = bh.assemble_mmode(ROOT)
    boot = bh.build_image(lay, built.payload, security_version=2,
                          signer=bh.root_key("production"))
    source = boot_release_target.compose(ROOT, "main:\n        li a0, 0\n        ret\n",
                                          boot, bh.root_key("production"), 2)
    sections, symbols, _ = asm.Assembler(source, "target-release-test").assemble()
    ensure(symbols["end_signature"][1] - symbols["begin_signature"][1]
           == 128 + lay["HANDOFF_BYTES"] + lay["BRINGUP_MMODE_REGION_BYTES"],
           "release target does not capture the complete handoff and placed window")
    ensure(symbols["begin_signature"][1] % 131072 == 0, "target output capability is not exact")
    ensure("sd zero, 32(c21)" in source and "ld t0, 0(c22)" in source,
           "release inputs did not come from RoT startup and counter doors")
    ensure(any(s.name == ".text" for s in sections), "release target lacks executable text")
    holder, root = _sandbox((bh.ROT_CONFIG, bh.HEADER))
    with holder:
        path = root / "capture"
        path.write_text("0706050403020100\n0f0e0d0c0b0a0908\n", encoding="utf-8")
        ensure(boot_release_target.read_output(path, 16) == bytes(range(16)),
               "target output was decoded with the wrong byte order")
        for malformed in ("0\n", "0000000000000000\n", "xxxxxxxxxxxxxxxx\n" * 2):
            path.write_text(malformed, encoding="utf-8")
            try:
                boot_release_target.read_output(path, 16)
            except ValueError:
                pass
            else:
                raise AssertionError("a malformed or truncated target capture was accepted")


def _emulator_process_verdict() -> None:
    for line, code, expected in (("SUCCESS\n", 0, "success"), ("SUCCESS\n", -11, "no-verdict"),
                                 ("FAILURE: 4\n", 1, "failure"), ("FAILURE: 4\n", -11, "no-verdict"),
                                 ("FAILURE: 4\n", 0, "no-verdict")):
        with patch.object(bh.subprocess, "run", return_value=subprocess.CompletedProcess([], code, line, "")):
            result = bh.emulate(Path("simulator"), Path("profile"), Path("image"), 1)
        ensure(result.verdict == expected, "an abnormal process exit supplied an emulator verdict")


def _receipt_required() -> None:
    holder, root = _sandbox((bh.HEADER,))
    with holder:
        try:
            bh.run_harness(root, root / "missing-simulator", root / "output", 1)
        except ValueError as exc:
            ensure("build receipt" in str(exc), "missing receipt did not fail first")
        else:
            raise AssertionError("a receipt-free run was admitted")


def _compiler_file_bindings() -> None:
    holder, root = _sandbox(())
    with holder:
        config = root / "compcert.ini"
        headers = root / "include"
        headers.mkdir()
        header = headers / "stdint.h"
        config.write_text("model=64\n", encoding="utf-8")
        header.write_text("typedef unsigned long uint64_t;\n", encoding="utf-8")
        flags = ["-conf", str(config), "-stdlib", str(headers)]
        original = boot_target.compiler_inputs(flags)
        ensure(len(original) == 2, "compiler config or header closure was omitted")
        header.write_text("typedef unsigned int uint64_t;\n", encoding="utf-8")
        ensure(boot_target.compiler_inputs(flags) != original, "changed runtime header kept its identity")
        for invalid in (["-conf"], ["-conf", str(root / "missing")]):
            try:
                boot_target.compiler_inputs(invalid)
            except ValueError:
                pass
            else:
                raise AssertionError("missing compiler input was silently omitted")


def _registers_split() -> None:
    lay = bh.layout(ROOT)
    digest = hashlib.shake_256(b"image").digest(32)
    production = bh.expected_registers(ROOT, lay, bh.RotInputs(3, 1, 0, 2), digest)
    development = bh.expected_registers(ROOT, lay, bh.RotInputs(2, 1, 0, 2), digest)
    refused = bh.expected_registers(ROOT, lay, bh.RotInputs(3, 1, 0, 2), None)
    ensure(production[0] == development[0], "the generation register saw a unit input")
    ensure(production[1] != development[1], "the device register missed the lifecycle state")
    ensure(refused[0] == "00" * 32 and refused[1] == production[1],
           "a refusal must extend the device prologue alone")
    ensure(len({production[2], development[2], refused[2]}) == 3, "chain digests collide")


def _harness_run() -> None:
    environment = env.load()
    ensure(environment.simulator.is_file(), f"no golden emulator at {environment.simulator}")
    result = bh.run_harness(environment.root, environment.simulator,
                            environment.lane_root / "boot-handoff-test", 60,
                            build_receipt=environment.log("model-build").with_suffix(".json"))
    failing = [f"{line.case}: {line.problems}" for line in result.lines if line.problems]
    ensure(result.ok, f"boot-handoff harness failed: {failing} {result.findings}")
    ensure(len(result.lines) == len(bh.cases()), "a case produced no line")


def cases() -> list[Case]:
    return [Case("contract, image and vos_boot.h agree", _owners_agree),
            Case("table, case and macro drift is reported", _drift_is_reported),
            Case("the descriptor's counts and magic are held", _descriptor_counts_are_held),
            Case("the image builder places every field", _image_builder),
            Case("an explicit signer receives the exact prefix", _explicit_signer),
            Case("the scheduled producer follows timer owners", _scheduled_producer),
            Case("the target stack budget includes large frames", _target_stack_budget),
            Case("the release target binds devices and exact output capture", _target_release_composition),
            Case("abnormal emulator exits provide no verdict", _emulator_process_verdict),
            Case("the model build receipt is mandatory", _receipt_required),
            Case("compiler configuration and headers are bound", _compiler_file_bindings),
            Case("the two registers split unit and generation inputs", _registers_split),
            Case("every contract case on the golden emulator", _harness_run,
                 slow=True, lane="toolchain")]
