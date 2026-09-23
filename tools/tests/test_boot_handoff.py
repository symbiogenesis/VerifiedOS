# SPDX-License-Identifier: Apache-2.0
"""M3.5's boot-handoff harness: the owner agreement, the image builder, and a real run."""

import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import boot_handoff as bh
from vos import env, toolenv

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
                            environment.lane_root / "boot-handoff-test", 60)
    failing = [f"{line.case}: {line.problems}" for line in result.lines if line.problems]
    ensure(result.ok, f"boot-handoff harness failed: {failing} {result.findings}")
    ensure(len(result.lines) == len(bh.cases()), "a case produced no line")


def cases() -> list[Case]:
    return [Case("contract, image and vos_boot.h agree", _owners_agree),
            Case("table, case and macro drift is reported", _drift_is_reported),
            Case("the descriptor's counts and magic are held", _descriptor_counts_are_held),
            Case("the image builder places every field", _image_builder),
            Case("the two registers split unit and generation inputs", _registers_split),
            Case("every contract case on the golden emulator", _harness_run,
                 slow=True, lane="toolchain")]
