# SPDX-License-Identifier: Apache-2.0
"""Real copy publication to interrupt-file store and ordinary pending load."""

import json
from pathlib import Path

from vos import (
    asm,
    copy_service,
    copy_target,
    device_registers,
    image,
    jsonc,
    kernel_restore,
    receipts,
)
from vos.boot_target import compiler_inputs
from vos.cli import compiler_diff as cd

INPUTS = ("copy-service", "interfaces/ring-reference.json", "interfaces/device-registers.json",
          "tools/vos/copy_notification.py", "tools/vos/copy_service.py", "tools/vos/copy_target.py",
          "tools/vos/cli/copy_service.py", "tools/vos/device_registers.py", "tools/generated",
          "tools/vos/cli/compiler_diff.py", "tools/vos/asm.py", "tools/vos/image.py")


def layout(root: Path) -> tuple[int, int, int]:
    devices = device_registers.read(root).devices
    device = next(d for d in devices if d.name == "imsic")
    send = next(r for r in device.registers if r.name == "seteipnum")
    pending = next(r for r in device.registers if r.name == "eip")
    identity = next(v for v in send.views if v.name == "identity")
    widths = [f.width for r in (send, pending) for f in r.fields if f.name == "value"]
    config = jsonc.load(root / "model/config/verifiedos.json")
    platform = config.get("platform") if isinstance(config, dict) else None
    imsic = platform.get("imsic") if isinstance(platform, dict) else None
    if not isinstance(imsic, dict):
        raise TypeError("missing interrupt-file composition")
    base, size = imsic.get("base"), imsic.get("size")
    if type(base) is not int or type(size) is not int:
        raise TypeError("interrupt-file bounds must be integer extents")
    if (widths != [64, 64] or send.access != "wo" or pending.access != "rw"
            or identity.lsb != 0 or identity.width > 6 or imsic.get("supported") is not True
            or max(send.offset, pending.offset) + 8 > size):
        raise ValueError("unsupported interrupt-file composition")
    return base + send.offset, base + pending.offset, 1 << identity.width


def adapter(root: Path) -> str:
    _, _, identities = layout(root)
    return (f".equ COPY_NOTIFICATION_IDENTITIES, {identities}\n"
            + (root / "copy-service/src/notification_target.s").read_text(encoding="utf-8"))


def controls(root: Path) -> str:
    send, pending, identities = layout(root)
    config = copy_service.configuration(root)
    lines = [".text", "main:", "    cmove c5, c2", "    cincoffsetimm c2, c2, -16",
             "    sc c1, 0(c2)", "    sc c5, 8(c2)"]

    def pointer(register: int, location: str, extent: int, permissions: int = 7) -> None:
        lines.extend([f"    li x31, {location}", f"    csetaddr c{register}, c4, x31",
                      f"    li x31, {extent}", f"    csetbounds c{register}, c{register}, x31",
                      f"    li x31, {permissions}", f"    candperm c{register}, c{register}, x31"])

    def expect(value: int) -> None:
        lines.extend([f"    li x5, {value}", "    bne x10, x5, notification_fail"])

    def poll(identity: int, value: int) -> None:
        pointer(10, str(pending), 8, 3)
        lines.extend([f"    li x11, {identity}", "    call vos_copy_poll"])
        expect(value)

    def notify(identity: int, requested: int, value: int) -> None:
        pointer(10, str(send), 8)
        lines.extend([f"    li x11, {identity}", f"    li x12, {requested}", "    call vos_copy_notify"])
        expect(value)

    # Explicit composition reset, outside the receiver's read-only interface.
    pointer(5, str(pending), 8)
    lines.append("    sd x0, 0(c5)")
    for identity in (0, identities):
        notify(identity, 1, 0)
        poll(identity, -1)
    notify(1, 2, 0)
    notify(1, 0, 1)
    poll(1, 0)
    # Actual ring publication requests the actual device store; no Boolean
    # stand-in is used for a notification's pending bit.
    pointer(10, "notification_ring", copy_target.RING_BYTES)
    lines.append("    call vos_copy_init")
    pointer(10, "notification_ring", copy_target.RING_BYTES)
    lines.append("    call vos_copy_prepare_sleep")
    expect(1)
    pointer(5, "notification_source", 8)
    lines.extend(["    li x6, 123", "    sb x6, 0(c5)"])
    pointer(10, "notification_ring", copy_target.RING_BYTES)
    lines.extend([f"    li x11, {config.generation}", "    li x12, 7", "    li x13, 0"])
    pointer(14, "notification_source", 8, 3)
    lines.extend(["    li x15, 1", "    li x16, 1"])
    pointer(17, "notification_signal", 8)
    lines.append("    call vos_copy_submit")
    expect(1)
    pointer(5, "notification_signal", 8, 3)
    lines.append("    lwu x12, 0(c5)")
    pointer(10, str(send), 8)
    lines.extend(["    li x11, 1", "    call vos_copy_notify"])
    expect(1)
    poll(1, 1)
    # Coalescing and repeated ordinary polls preserve a pending event across
    # the consumer's recheck-to-yield interval; polling does not clear peers.
    notify(1, 1, 1)
    notify(identities - 1, 1, 1)
    poll(1, 1)
    poll(identities - 1, 1)
    pointer(10, "notification_ring", copy_target.RING_BYTES)
    pointer(11, "notification_destination", 8)
    lines.append("    li x12, 1")
    pointer(13, "notification_length", 8)
    pointer(14, "notification_request", 8)
    lines.append("    call vos_copy_take")
    expect(1)
    pointer(5, "notification_destination", 8, 3)
    lines.extend(["    lbu x6, 0(c5)", "    li x7, 123", "    bne x6, x7, notification_fail"])
    poll(1, 1)
    lines.extend(["    li x10, 0", "    j notification_return", "notification_fail:",
                  "    li x10, 1", "notification_return:", "    lc c1, 0(c2)",
                  "    lc c2, 8(c2)", "    ret", ".data",
                  f"    .balign {copy_target.RING_BYTES}", "notification_ring:",
                  f"    .space {copy_target.RING_BYTES}"])
    for name in ("source", "destination", "signal", "length", "request"):
        lines.extend(["    .balign 8", f"notification_{name}:", "    .space 8"])
    return "\n".join(lines) + "\n"


def run(root: Path, out: Path, ccomp: Path, arguments: list[str], simulator: Path,
        build_receipt: Path, timeout: int = 120) -> dict[str, object]:
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text('{"verdict":"incomplete"}\n', encoding="utf-8")
    sources = receipts.inputs(root, *INPUTS)
    model_sources = receipts.inputs(root, "model")
    simulator_sha, compiler_sha = receipts.digest(simulator), receipts.digest(ccomp)
    private = compiler_inputs(arguments)
    build_sha = receipts.digest(build_receipt)
    kernel_restore.require_build(json.loads(build_receipt.read_text(encoding="utf-8")),
                                 simulator_sha, model_sources)
    (out / "copy_service_config.h").write_text(
        copy_service.configuration_header(copy_service.configuration(root)), encoding="utf-8")
    compiled = cd.compile_c([str(ccomp), *arguments, "-fverifiedos-typed", f"-I{out}",
                             f"-I{root / 'copy-service/include'}"],
                            root / "copy-service/test/target_unit.c", out / "compiler", timeout)
    if compiled.exit_code or compiled.stream is None:
        raise ValueError(f"copy target compilation failed: {compiled.said}")
    notification = adapter(root)
    stream = cd.normalize(compiled.stream) + copy_target.adapter(root) + notification + controls(root)
    (out / "notification.s").write_text(stream, encoding="utf-8")
    variants = {"notification": stream,
                "lost-notify": stream.replace("    sd x11, 0(c10)\n", "    sd x0, 0(c10)\n", 1),
                "lost-pending": stream.replace("    ld x5, 0(c10)\n", "    li x5, 0\n", 1),
                "no-send-authority": stream.replace("    sd x11, 0(c10)\n",
                    "    li x5, 3\n    candperm c10, c10, x5\n    sd x11, 0(c10)\n", 1)}
    if variants["lost-notify"] == stream or variants["lost-pending"] == stream:
        raise ValueError("notification mutant no longer applies")
    results = {}
    for name, variant in variants.items():
        assembler = asm.Assembler(cd.compose(variant), name, data_base=0x80200000)
        sections, symbols, entry = assembler.assemble()
        elf = out / f"{name}.elf"
        image.write_elf(elf, sections, symbols, entry)
        result = copy_target.execute(simulator, root / "model/config/verifiedos.json", elf, timeout)
        expected = "pass" if name == "notification" else "trap" if name == "no-send-authority" else "fail"
        expected_code = 0 if expected == "pass" else 1
        if (result["verdict"] != expected
                or (expected != "trap" and result["code"] != expected_code)):
            raise ValueError(f"{name}: expected actual {expected}, got {result['detail']}")
        results[name] = {"run": result, "image_sha256": receipts.digest(elf)}
    if (sources != receipts.inputs(root, *INPUTS) or model_sources != receipts.inputs(root, "model")
            or compiler_sha != receipts.digest(ccomp) or simulator_sha != receipts.digest(simulator)
            or private != compiler_inputs(arguments) or build_sha != receipts.digest(build_receipt)):
        raise ValueError("notification inputs changed during execution")
    report: dict[str, object] = {"schema": 1, "verdict": "pass", "sources": sources,
        "model_sources": model_sources, "simulator_sha256": simulator_sha,
        "model_build_sha256": build_sha, "compiler_sha256": compiler_sha, "compiler_inputs": private,
        "preprocessed_sha256": compiled.preprocessed.sha256, "results": results,
        "limits": "Real MMIO notification/poll; no new syscall, wait, completion-ring or boot acceptance."}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
