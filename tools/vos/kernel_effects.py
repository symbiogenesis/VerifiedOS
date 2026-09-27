# SPDX-License-Identifier: Apache-2.0
"""Bounded scalar trap save, abandonment and fresh-entry restart on Sail.

This primitive saves all merged words and tags, including the bootstrap scratch
register. It is for a live architectural trap only: the model's trap-live guard
prevents a nested synchronous fault from consuming the temporary MTDC exchange.
The finite harness includes real retired capability holders and two dirty private
frames. It does not stand for the separately composed sentry switcher ABI.
"""

import json
import subprocess
from pathlib import Path

from vos import (
    asm,
    boot_handoff,
    dialect,
    kernel_restore,
    kernel_target,
    kernelrun,
    receipts,
    trace,
)
from vos.cli import compiler_diff


def emit_save(prefix: str = "vos_trap", offset: int = 0) -> str:
    """MTDC's cursor plus offset names a private writable 264-byte save area.

    MTDC has store-local and load transitivity. No outgoing register is trusted
    as authority. The exchanged c31 is recovered before MTDC is reinstalled;
    c30 is overwritten only after its old value has been saved.
    """
    if not prefix.isidentifier() or offset < 0 or offset % 8 or offset + 256 > 2040:
        raise ValueError("trap save requires a label and an aligned in-range save area")
    lines = [f"{prefix}_save_begin:", "    cspecialrw c31, mtdc, c31",
             f"    sc cnull, {offset}(c31)"]
    lines += [f"    sc c{r}, {offset + r * 8}(c31)" for r in range(1, 31)]
    lines += ["    cspecialrw c30, mtdc, cnull",
              f"    sc c30, {offset + 248}(c31)",
              "    cspecialrw cnull, mtdc, c31",
              "    cspecialrw c30, mepcc, cnull",
              f"    sc c30, {offset + 256}(c31)", f"{prefix}_save_end:"]
    return "\n".join(lines) + "\n"


def emit_scrub(prefix: str = "vos_trap") -> str:
    """Retain only c31, the newly acquired private trap root."""
    if not prefix.isidentifier():
        raise ValueError("invalid trap label")
    return (f"{prefix}_scrub_begin:\n    cclear 0, 0xffff\n"
            f"    cclear 1, 0x7fff\n{prefix}_scrub_end:\n")


def emit_retire_adapter(name: str = "vos_kernel_retire_target") -> str:
    """Ordinary trusted scalar call: state, members, receipt, bitmap, epoch.

    Caller supplies the authenticated bitmap capability and a private stack.
    The direct C preflight freezes service entry before the first MMIO write.
    Every C call may clobber all allocatable registers, so inputs and the local
    backward continuation live only in the bounded private 64-byte frame.
    """
    if not name.isidentifier():
        raise ValueError("invalid adapter label")
    lines = [f"{name}:", "    cmove c31, c2", "    cincoffsetimm c2, c2, -64",
             "    sc c31, 0(c2)", "    sc c1, 8(c2)", "    sc c10, 16(c2)",
             "    sd x11, 24(c2)", "    sc c12, 32(c2)", "    sc c13, 40(c2)",
             "    sd x14, 48(c2)", "    call vos_kernel_retirement_mask",
             f"    beqz x10, {name}_return", "    sd x10, 56(c2)",
             "    lc c20, 40(c2)", "    ld x21, 0(c20)", "    or x21, x21, x10",
             f"{name}_publish:", "    sd x21, 0(c20)", "    fence rw, rw",
             "    ld x13, 0(c20)", "    lc c10, 16(c2)", "    ld x11, 48(c2)",
             "    ld x12, 56(c2)", "    call vos_kernel_publication",
             f"    beqz x10, {name}_return", "    lc c10, 16(c2)",
             "    ld x11, 24(c2)", "    lc c12, 32(c2)", "    call vos_kernel_retire",
             f"{name}_return:", "    lc c1, 8(c2)", "    lc c2, 0(c2)", "    ret"]
    return "\n".join(lines) + "\n"


def emit_wait_adapter(name: str = "vos_kernel_wait_target") -> str:
    """Trusted scalar call: state, delay, hardware clock, epoch, poll bound.

    Samples the actual clock after entry, refuses backwards/wrapped time and
    consumes the C acknowledgment once. No failure path fabricates elapsed time.
    """
    if not name.isidentifier():
        raise ValueError("invalid adapter label")
    lines = [f"{name}:", "    cmove c31, c2", "    cincoffsetimm c2, c2, -64",
             "    sc c31, 0(c2)", "    sc c1, 8(c2)", "    sc c10, 16(c2)",
             "    sd x11, 24(c2)", "    sd x13, 32(c2)",
             f"    beqz x14, {name}_fail", "    li x15, 1048576",
             f"    bltu x15, x14, {name}_fail", "    ld x15, 0(c12)",
             f"{name}_poll:", "    ld x16, 0(c12)", f"    bltu x16, x15, {name}_fail",
             "    sub x17, x16, x15", f"    bgeu x17, x11, {name}_observed",
             "    addi x14, x14, -1", f"    bnez x14, {name}_poll",
             f"{name}_fail:", "    li x10, 0", f"    j {name}_return",
             f"{name}_observed:", "    cmove c14, c16", "    cmove c13, c15",
             "    ld x12, 24(c2)", "    ld x11, 32(c2)",
             "    call vos_kernel_wait_sample", f"    beqz x10, {name}_return",
             "    lc c10, 16(c2)", "    ld x11, 24(c2)", "    call vos_kernel_wait",
             f"{name}_return:", "    lc c1, 8(c2)", "    lc c2, 0(c2)", "    ret"]
    return "\n".join(lines) + "\n"


def source(defect: str = "none", bitmap: tuple[int, int] = (0, 0)) -> str:
    """Reset-root experiment, with an actual unprivileged fault and fresh entry."""
    address, mask = bitmap
    lines = [".text", ".globl _start", "_start:", "    cmove c4, c1",
             "    li x5, private", "    csetaddr c31, c4, x5", "    li x5, 2048",
             "    csetbounds c31, c31, x5", "    li x5, 0xfe", "    candperm c31, c31, x5",
             "    cspecialrw cnull, mtdc, c31", "    la c9, trap_entry",
             "    cspecialrw cnull, mtcc, c9", f"    li x5, {address}",
             "    csetaddr c6, c4, x5", "    li x5, 8", "    csetbounds c6, c6, x5",
             "    li x5, 7", "    candperm c6, c6, x5", "    sc c6, 832(c31)",
             "    sd x0, 840(c31)", "    li x5, retired_object", "    csetaddr c7, c4, x5",
             "    li x5, 8", "    csetbounds c7, c7, x5", "    li x5, 0x777",
             "    sd x5, 0(c7)"]
    # Both private frames carry real tagged slots, not metadata-only occupancy.
    lines += [f"    sc c7, {offset}(c31)" for offset in range(320, 832, 8)]
    lines += ["    cincoffsetimm c19, c31, 896"]
    for r in range(33):
        lines.append(f"    sc cnull, {r * 8}(c19)")
    lines += ["    sc c7, 24(c19)", "    sc c7, 248(c19)", "    li x7, 1193046",
              "    sc c7, 136(c19)", "    la c7, service_entry", "    li x5, 0x7ff",
              "    candperm c7, c7, x5", "    csealentry c7, c7", "    sc c7, 256(c19)",
              "    cmove c31, c19", "    cclear 0, 0xffff", "    cclear 1, 0x7fff",
              kernel_restore.emit(), "service_entry:", "    ld x5, 0(cnull)", "service_unreachable:",
              "    j service_unreachable", "trap_entry:"]
    save = emit_save()
    if defect == "missing-save":
        save = save.replace("    sc c17, 136(c31)\n", "")
    if defect == "tagless-save":
        save = save.replace("    sc c3, 24(c31)", "    sd x3, 24(c31)")
    if defect == "lost-bootstrap":
        save = save.replace("    sc c30, 248(c31)", "    sc cnull, 248(c31)")
    lines.append(save)
    scrub = emit_scrub()
    if defect == "missing-scrub":
        scrub = scrub.replace("    cclear 0, 0xffff", "    cclear 0, 0xfff7")
    lines += [scrub, "    ld x5, 840(c31)", "    bnez x5, finish",
              "    lc c6, 832(c31)", f"    li x5, {mask}", "    ld x7, 0(c6)",
              "    or x5, x5, x7", "retirement_publish:", "    sd x5, 0(c6)",
              "    ld x7, 0(c6)", "    li x3, 1", "    bne x5, x7, fail",
              "cleanup_begin:"]
    for offset in (*range(0, 264, 8), *range(320, 832, 8), *range(896, 1160, 8)):
        if (defect == "stale-save" and offset == 24) or (defect == "stale-frame" and offset == 400):
            continue
        lines.append(f"    sc cnull, {offset}(c31)")
    lines += ["cleanup_end:", "    li x3, 2"]
    for offset in (*range(0, 264, 8), *range(320, 832, 8), *range(896, 1160, 8)):
        lines += [f"    ld x5, {offset}(c31)", "    bnez x5, fail"]
    lines += ["    li x5, 1", "    sd x5, 840(c31)", "    cincoffsetimm c19, c31, 896",
              "    la c7, restart_entry", "    li x5, 0x7ff", "    candperm c7, c7, x5",
              "    csealentry c7, c7", "    sc c7, 256(c19)", "    li x7, 2",
              "    sc c7, 136(c19)", "    cmove c31, c19", "    cclear 0, 0xffff",
              "    cclear 1, 0x7fff"]
    lines.append(kernel_restore.emit().replace("vos_restore", "restart_restore"))
    lines += ["restart_entry:", "    ld x5, 0(cnull)", "restart_unreachable:", "    j restart_unreachable",
              "finish:", "    li x3, 0", "fail:", "    slli x5, x3, 1", "    ori x5, x5, 1",
              "    sd x5, 848(c31)", "halt:", "    j halt", ".data", ".align 11",
              "private:", "trap_image:", "    .space 264", "    .space 56",
              "protected_frames:", "    .space 512", "bitmap_root:", "    .dword 0",
              "phase:", "    .dword 0", "tohost:", "    .dword 0", "    .space 40",
              "initial_image:", "    .space 264", "    .space 888", ".align 6",
              "retired_object:", "    .space 64"]
    return "\n".join(lines) + "\n"


def observations(records: list[kernelrun.Record], symbols: dict[str, int]) -> dict[str, bool]:
    """Compare actual pretrap register values with the actual stored save image."""
    registers = dict.fromkeys(range(32), (0, 0))
    expected: list[dict[int, tuple[int, int]]] = []
    specials: dict[int, tuple[int, int]] = {}
    saved_entries: list[tuple[int, int] | None] = []
    trap_roots: list[tuple[int, int] | None] = []
    root_restored: list[bool] = []
    fresh_registers: list[bool] = []
    captured: list[dict[int, list[tuple[int, int]]]] = []
    scrubbed: list[bool] = []
    clears: dict[int, list[tuple[int, int]]] = {}
    pc = -1
    frame_seeded: set[int] = set()
    for kind, fields in records:
        if kind == "I":
            pc = fields[0]
            if pc == symbols["vos_trap_save_begin"]:
                expected.append(dict(registers))
                captured.append({})
                saved_entries.append(specials.get(dialect.SCRS["mepcc"]))
                trap_roots.append(specials.get(dialect.SCRS["mtdc"]))
            if pc == symbols["vos_trap_save_end"]:
                root_restored.append(specials.get(dialect.SCRS["mtdc"]) == trap_roots[-1])
            if pc == symbols["restart_entry"]:
                fresh_registers.append(all(registers[r] == (0, 2 if r == 17 else 0)
                                           for r in range(32)))
            if pc == symbols["vos_trap_scrub_end"]:
                scrubbed.append(all(registers[r] == (0, 0) for r in range(1, 31)))
        elif kind == "S":
            specials[fields[0]] = (fields[1], fields[2])
        elif kind == "X":
            registers[fields[0]] = (fields[1], fields[2])
        elif kind == "W" and fields[1] == 8:
            offset = fields[0] - symbols["private"]
            value = (fields[2], fields[3])
            if symbols["vos_trap_save_begin"] <= pc < symbols["vos_trap_save_end"]:
                captured[-1].setdefault(offset, []).append(value)
            if symbols["cleanup_begin"] <= pc < symbols["cleanup_end"]:
                clears.setdefault(offset, []).append(value)
            if not expected and 320 <= offset < 832 and value[0]:
                frame_seeded.add(offset)
    offsets = {*range(0, 264, 8), *range(320, 832, 8), *range(896, 1160, 8)}
    pcs = [fields[0] for kind, fields in records if kind == "I"]
    return {
        "two_real_traps": len(expected) == 2,
        "exact_save_values_tags": len(expected) == 2 and all(
            got.get(r * 8) == [wanted[r]] for wanted, got in zip(expected, captured, strict=True)
            for r in range(32)),
        "saved_interrupted_pcc": len(saved_entries) == 2 and all(
            wanted is not None and got.get(256) == [wanted]
            for wanted, got in zip(saved_entries, captured, strict=True)),
        "trap_data_restored": root_restored == [True, True],
        "fresh_register_image": fresh_registers == [True],
        "resident_scrub": scrubbed == [True, True],
        "dirty_frames_observed": frame_seeded == set(range(320, 832, 8)),
        "complete_memory_and_tag_zeroization": set(clears) == offsets and
            all(values == [(0, 0)] for values in clears.values()),
        "fresh_entry_once": pcs.count(symbols["service_entry"]) == 1 and
            pcs.count(symbols["restart_entry"]) == 1,
    }


def run(root: Path, simulator: Path, build_receipt: Path, out: Path,
        timeout: int = 60) -> dict[str, object]:
    root, simulator, build_receipt, out = (
        path.resolve() for path in (root, simulator, build_receipt, out))
    out.mkdir(parents=True, exist_ok=True)
    receipts.write(out / "report.json", {"ok": False, "status": "incomplete"})
    inputs = receipts.inputs(root, "kernel", "tools/vos/kernel_effects.py", "tools/vos/kernel_restore.py")
    model = receipts.inputs(root, "model")
    simulator_sha = receipts.digest(simulator)
    receipt_sha = receipts.digest(build_receipt)
    kernel_restore.require_build(json.loads(build_receipt.read_text(encoding="utf-8")), simulator_sha, model)
    probe = asm.Assembler(source(), "layout")
    probe.assemble()
    bitmap = kernel_target.revocation_window(root, probe.symbols["retired_object"])
    cases: list[dict[str, object]] = []
    defects = {"none": None, "missing-save": "exact_save_values_tags",
               "tagless-save": "exact_save_values_tags", "lost-bootstrap": "exact_save_values_tags",
               "missing-scrub": "resident_scrub", "stale-save": 2, "stale-frame": 2}
    for defect, decisive in defects.items():
        assembly = source(defect, bitmap)
        source_path = out / f"{defect}.s"
        source_path.write_text(assembly, encoding="utf-8", newline="\n")
        elf = out / f"{defect}.elf"
        assembler = asm.Assembler(assembly, defect)
        assembler.assemble()
        # Use the established assembler writer and model profile.
        asm.assemble_file(source_path, elf)
        result = subprocess.run([str(simulator), "--config", str(root / boot_handoff.MAIN_CONFIG),
            "--trace-commit", "--inst-limit", "20000", str(elf)], cwd=out,
            capture_output=True, text=True, timeout=timeout, check=False)
        raw = result.stdout + result.stderr
        (out / f"{defect}.trace").write_text(raw, encoding="utf-8", newline="\n")
        normalized = trace.normalize_commit(raw.splitlines())
        observed = observations(kernelrun.parse_records(normalized), assembler.symbols)
        htif, code, _ = compiler_diff.htif_verdict(raw, result.returncode)
        matched = (htif == "pass" and all(observed.values()) if decisive is None else
                   htif == "fail" and code == decisive if isinstance(decisive, int) else
                   htif == "pass" and not observed[decisive])
        cases.append({"name": defect, "htif": htif, "code": code, "observations": observed,
                      "decisive": decisive, "matched": matched, "elf_sha256": receipts.digest(elf),
                      "trace_sha256": trace.digest(normalized), "source_sha256": receipts.digest(source_path)})
    unchanged = inputs == receipts.inputs(root, "kernel", "tools/vos/kernel_effects.py", "tools/vos/kernel_restore.py") and model == receipts.inputs(root, "model") and simulator_sha == receipts.digest(simulator) and receipt_sha == receipts.digest(build_receipt)
    report = {"scope": "C-class architectural fault, complete save and bounded crash-only restart; reset roots",
              "milestone_acceptance": "open", "status": "complete", "sources": inputs, "model_sources": model,
              "simulator_sha256": simulator_sha, "build_receipt_sha256": receipt_sha,
              "cases": cases, "inputs_unchanged": unchanged,
              "ok": unchanged and all(row["matched"] for row in cases)}
    receipts.write(out / "report.json", report)
    return report
