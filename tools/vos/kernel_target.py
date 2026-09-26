# SPDX-License-Identifier: Apache-2.0
"""Composed C-class kernel consumer, linked to the actual firmware handoff.

The generated source keeps compiler output in the caller's contained native
directory. Constants here describe one finite composition, not architecture.
"""

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from vos import asm, boot_handoff, jsonc, kernel_restore, kernelrun, receipts, trace
from vos.boot_signing import SlhSigner
from vos.boot_target import compiler_inputs
from vos.cli import compiler_diff

COMPOSITION = 7
PARTITIONS = 2
WINDOWS = 3
SLOTS = 2
CSRS = 1
STATE_BYTES = 4096
CONTEXT_BYTES = 320
STACK_BYTES = 8192
SLOT_WIDTH = 4096
DATA_OFFSET = 0xa000
RETIRED_BYTES = 8
INPUTS = ("kernel", "firmware", "tools/vos", "tools/generated",
          "docs/implementation/contracts/boot-handoff.md",
          "docs/implementation/contracts/purecap-abi.md", "docs/hardware/isa-profile.md")


def _address(register: int, label: str, root: int = 18) -> list[str]:
    return [f"    li x5, {label}", f"    csetaddr c{register}, c{root}, x5"]


def _cap_check(register: int, base: str, length: str, permissions: int,
               failure: int, *, cursor: str | None = None) -> list[str]:
    return [f"    li x3, {failure}", f"    cgettag x5, c{register}",
            "    beqz x5, kernel_fail", f"    cgetsealed x5, c{register}",
            "    bnez x5, kernel_fail", f"    cgetbase x5, c{register}",
            f"    li x6, {base}", "    bne x5, x6, kernel_fail",
            f"    cgetaddr x5, c{register}", f"    li x6, {cursor or base}",
            "    bne x5, x6, kernel_fail",
            f"    cgetlen x5, c{register}", f"    li x6, {length}",
            "    bne x5, x6, kernel_fail", f"    cgetperm x5, c{register}",
            f"    li x6, {permissions}", "    bne x5, x6, kernel_fail"]


def revocation_window(root: Path, object_base: int) -> tuple[int, int]:
    """Select exactly one bitmap word using the model's granule and profile."""
    config = jsonc.load(root / boot_handoff.MAIN_CONFIG)
    platform = config.get("platform") if isinstance(config, dict) else None
    plane = platform.get("revocation") if isinstance(platform, dict) else None
    if not isinstance(plane, dict) or plane.get("supported") is not True:
        raise ValueError("the composed retirement requires a revocation plane")
    base, interval, size = plane.get("base"), plane.get("interval_base"), plane.get("interval_size")
    if type(base) is not int or type(interval) is not int or type(size) is not int:
        raise ValueError("the revocation plane requires integer extents")
    source = (root / "model/model/core/cap_format.sail").read_text(encoding="utf-8")
    widths = re.findall(r"^type log2_cap_size : Int = (\d+)$", source, re.MULTILINE)
    if len(widths) != 1:
        raise ValueError("the capability granule must have one literal owner")
    granule = 1 << int(widths[0])
    offset = object_base - interval
    if granule != RETIRED_BYTES or object_base % 64 or not 0 <= offset <= size - RETIRED_BYTES:
        raise ValueError("the retired object must be aligned inside the declared interval")
    index = offset // granule
    return base + 8 * (index // 64), 1 << (index % 64)


def consumer_source(compiled: str, init_magic: int,
                    timer_windows: tuple[tuple[int, int], tuple[int, int]],
                    revocation_word: tuple[int, int]) -> str:
    """Bind C preparation/context/executive to protected assembly final restore.

    Firmware supplies root-table entries: kernel data, timer comparison,
    timer clock and two partition text roots. Only the kernel can name the timer or a CSR. Two successor
    PCCs lack access-system-registers; their register images contain no timer
    authority. A timer trap enters the next C-selected slot. The final trap
    terminates this finite two-slot observation after one complete frame.
    """
    lines = [".text", ".align 11", "kernel_text_base:", "kernel_entry:",
             "    cmove c5, cnull"]
    lines += _cap_check(10, "root_table", "root_table_end - root_table", 0xcb, 1)
    lines += _cap_check(11, "BOOT_DESCRIPTOR", "BOOT_DESCRIPTOR_BYTES", 3, 2)
    lines += _cap_check(12, "init_desc", "init_desc_end - init_desc", 0xcb, 3)
    lines += ["    lc c18, 0(c10)"]
    lines += _cap_check(18, "kdata_base", "kdata_end - kdata_base", 0xdf, 4)
    lines += ["    cspecialrw c20, mtdc, cnull"]
    lines += _cap_check(20, "kdata_base", "kdata_end - kdata_base", 0xdf, 20)
    lines += _cap_check(2, "kstack_base", "kstack_end - kstack_base", 0xfe, 19,
                        cursor="kstack_end")
    lines += ["    cspecialrw c20, mtcc, cnull"]
    lines += _cap_check(20, "kernel_text_base", "kernel_text_end - kernel_text_base",
                        0x9cb, 21, cursor="kernel_trap")
    lines += ["    cspecialrw c20, pcc, cnull", "entry_pcc_read:"]
    lines += _cap_check(20, "kernel_text_base", "kernel_text_end - kernel_text_base",
                        0x9cb, 22, cursor="entry_pcc_read - 4")
    for index, ((base, size), permissions) in enumerate(zip(timer_windows, (7, 3), strict=True), 1):
        lines += [f"    lc c20, {index * 8}(c10)"]
        lines += _cap_check(20, str(base), str(size), permissions, 11 + index)
    for index, name in enumerate(("partition_one", "partition_two"), 3):
        lines += [f"    lc c20, {index * 8}(c10)"]
        lines += _cap_check(20, name, "64", 0x1cb, 11 + index)
    bitmap_address, bitmap_mask = revocation_word
    lines += ["    lc c20, 40(c10)"]
    lines += _cap_check(20, str(bitmap_address), "8", 7, 17)
    # This adapter is one exact composition. Refuse another structurally valid
    # table rather than interpreting its bounds or widths as our own constants.
    lines += [*_address(19, "expected_init"), "    cmove c20, c12",
              "    li x7, init_desc_end - init_desc", "    li x3, 18",
              "descriptor_compare:", "    ld x5, 0(c19)", "    ld x6, 0(c20)",
              "    bne x5, x6, kernel_fail", "    cincoffsetimm c19, c19, 8",
              "    cincoffsetimm c20, c20, 8", "    addi x7, x7, -8",
              "    bnez x7, descriptor_compare"]
    lines += [*_address(19, "root_handle"), "    sc c10, 0(c19)"]
    lines += ["    cincoffsetimm c2, c2, -16", "    sc c2, 0(c2)"]
    # Each attempt names one actual capability, and checks its result on target.
    for index, (name, register, slot) in enumerate((("root", 18, 0), ("window0", 20, 8),
                                                   ("window1", 21, 16), ("window2", 22, 40))):
        if index:
            lines += [f"    lc c{register}, {slot}(c10)"]
        lines += [f"    li x3, {5 + index}", f"    cgetbase x5, c{register}",
                  f"    cgetlen x6, c{register}", "    add x5, x5, x6",
                  f"    csetaddr c19, c{register}, x5", "    li x7, 8",
                  f"attempt_{name}:", "    csetbounds c19, c19, x7",
                  "    cgettag x5, c19", "    bnez x5, kernel_fail"]
    lines += ["    cmove c10, c11", "    cmove c11, c12",
              "    cgetlen x12, c10", "    cgetlen x13, c11"]
    lines += _address(14, "target_state")
    lines += [f"    li x15, {STATE_BYTES}", f"    li x16, {COMPOSITION}",
              "    csrr x17, mhartid", "    call vos_target_prepare",
              "    li x3, 8", "    bnez x10, kernel_fail",
              "    cspecialrw c18, mtdc, cnull"]
    # The timer epoch is sampled after preparation; no elapsed-time claim is
    # derived from it. The C release cursor supplies every subsequent offset.
    lines += [*_address(19, "root_handle"), "    lc c19, 0(c19)",
              "    lc c20, 16(c19)", "    ld x6, 0(c20)"]
    lines += [*_address(19, "timer_epoch"), "    sd x6, 0(c19)"]
    lines += [*_address(19, "dispatch_count"), "    sd x0, 0(c19)",
              "    j kernel_select", "kernel_trap:",
              "    cspecialrw c18, mtdc, cnull", "    csrr x5, mcause",
              "    li x6, 0x8000000000000007", "    li x3, 9",
              "    bne x5, x6, kernel_fail"]
    # The kernel's stack authority is kept in protected storage and restored
    # before calling C; no outgoing register supplies kernel authority.
    lines += [*_address(19, "kernel_stack"), "    lc c2, 0(c19)"]
    lines += [*_address(19, "dispatch_count"), "    ld x5, 0(c19)",
              f"    li x6, {SLOTS}", "    beq x5, x6, kernel_complete"]
    lines += [*_address(10, "target_state"), "    call vos_target_advance",
              "    cspecialrw c18, mtdc, cnull", "kernel_select:"]
    lines += [*_address(10, "target_state"), "    call vos_target_tenant",
              "    cspecialrw c18, mtdc, cnull", "    li x3, 10",
              "    li x5, 1", "    beq x10, x5, select_one",
              "    li x5, 2", "    bne x10, x5, kernel_fail",
              "    li x6, 32", "    li x7, partition_two_data",
              "    li x8, partition_two_context", "    j selected",
              "select_one:", "    li x6, 24", "    li x7, partition_one_data",
              "    li x8, partition_one_context", "selected:"]
    lines += [*_address(19, "root_handle"), "    lc c19, 0(c19)",
              "    cincoffset c19, c19, x6", "    lc c20, 0(c19)"]
    lines += [*_address(19, "saved_entry"), "    sc c20, 0(c19)"]
    lines += ["    csetaddr c20, c18, x7", "    li x5, 64",
              "    csetbounds c20, c20, x5"]
    lines += [*_address(19, "saved_data"), "    sc c20, 0(c19)"]
    lines += ["    csetaddr c20, c18, x8", f"    li x5, {CONTEXT_BYTES}",
              "    csetbounds c20, c20, x5"]
    lines += [*_address(19, "selected_context"), "    sc c20, 0(c19)",
              "    cmove c19, c20"]
    lines += [f"    sc cnull, {r * 8}(c19)" for r in range(32)]
    # A tagged partition data capability makes loss of tags observable. It is
    # bounded independently of kernel state and carries no timer authority.
    lines += [*_address(20, "saved_data"), "    lc c20, 0(c20)", "    sc c20, 24(c19)"]
    lines += ["    li x20, 1193046", "    sc c20, 56(c19)"]
    lines += [*_address(20, "saved_entry"), "    lc c20, 0(c20)", "    sc c20, 256(c19)"]
    # The bounded holder inventory is one temporary and saved register c4 of
    # the first context. Seed it once; a completed retirement never mints it
    # again. No borrower, proxy, DMA request or grant invocation exists here.
    lines += [*_address(20, "dispatch_count"), "    ld x5, 0(c20)",
              "    bnez x5, revocation_seeded"]
    lines += ["revocation_mint:", *_address(20, "retired_object"), f"    li x5, {RETIRED_BYTES}",
              "    csetbounds c20, c20, x5", "    sc c20, 32(c19)",
              "revocation_seeded:"]
    lines += [*_address(21, "root_handle"), "    lc c21, 0(c21)",
              "    lc c21, 40(c21)", f"    li x6, {bitmap_mask}",
              "    ld x7, 0(c21)", "    or x6, x6, x7",
              "revocation_publish:", "    sd x6, 0(c21)", "    ld x10, 0(c21)",
              "    xor x10, x10, x6", "    sltiu x10, x10, 1",
              "revocation_clear_resident:", "    cmove c20, cnull",
              "    cgettag x11, c20", "    sltiu x11, x11, 1",
              "revocation_filter_saved:", "    lc c20, 32(c19)", "    sc c20, 32(c19)",
              "    cloadtags x12, (c19)", "    andi x12, x12, 16",
              "    sltiu x12, x12, 1",
              "    li x13, 1", "    li x14, 1", "    li x15, 1",
              "revocation_gate:", "    call vos_target_complete",
              "revocation_return:",
              "    li x3, 16", "    beqz x10, kernel_fail",
              "    cspecialrw c18, mtdc, cnull"]
    lines += [*_address(10, "target_state"), *_address(11, "selected_context")]
    lines += ["    lc c11, 0(c11)"]
    lines += [*_address(12, "previous_context"), *_address(13, "restore_context")]
    lines += ["target_switch_call:", "    call vos_target_switch",
              "target_switch_return:", "    cspecialrw c18, mtdc, cnull"]
    lines += [*_address(19, "saved_entry"), "    lc c20, 0(c19)"]
    lines += [*_address(19, "restore_context"), "    sc c20, 256(c19)"]
    lines += [*_address(10, "target_state"), "    call vos_target_release",
              "    cspecialrw c18, mtdc, cnull"]
    lines += [*_address(19, "timer_epoch"), "    ld x5, 0(c19)",
              "    add x6, x5, x10", f"    li x5, {SLOT_WIDTH}",
              "    add x6, x6, x5"]
    lines += [*_address(19, "root_handle"), "    lc c19, 0(c19)",
              "    lc c20, 8(c19)", "    sd x6, 0(c20)"]
    lines += [*_address(19, "dispatch_count"), "    ld x5, 0(c19)",
              "    addi x5, x5, 1", "    sd x5, 0(c19)"]
    lines += _address(31, "restore_context")
    lines += [kernel_restore.emit(), "kernel_complete:", "    li x3, 0",
              "kernel_fail:", "    cspecialrw c18, mtdc, cnull",
              "    slli x6, x3, 1", "    ori x6, x6, 1"]
    lines += [*_address(19, "tohost"), "    sd x6, 0(c19)",
              "kernel_halt:", "    j kernel_halt", compiled,
              ".align 11", "kernel_text_end:"]
    for name in ("partition_one", "partition_two"):
        lines += [f"{name}:", "    li x5, 42", "    sd x5, 0(c3)",
                  f"{name}_wait:", "    wfi", f"    j {name}_wait", ".align 6",
                  f"{name}_end:"]
    lines += [".data", ".align 13", "kdata_base:", "tohost:", "    .dword 0",
              "root_handle:", "    .dword 0",
              "timer_epoch:", "    .dword 0", "dispatch_count:", "    .dword 0",
              "saved_entry:", "    .dword 0", "saved_data:", "    .dword 0",
              "selected_context:", "    .dword 0", ".align 6", "retired_object:",
              f"    .space {RETIRED_BYTES}", "retired_object_end:",
              f"    .space {64 - RETIRED_BYTES}", "partition_one_data:",
              "    .space 64", "partition_two_data:", "    .space 64",
              "target_state:", f"    .space {STATE_BYTES}"]
    for name in ("partition_one_context", "partition_two_context", "previous_context", "restore_context"):
        lines += [".align 6", f"{name}:", f"    .space {CONTEXT_BYTES}"]
    lines += ["expected_init:", "EXPECTED_INIT_WORDS"]
    lines += [".align 13", "kstack_base:", f"    .space {STACK_BYTES - 16}",
              "kernel_stack:", "    .space 16", "kstack_end:",
              "kdata_end:", "root_table:", "    .space 48",
              "root_table_end:", ".align 6", "init_desc:"]
    words: list[int | str] = [init_magic, 1, COMPOSITION, 0,
        "0x80000000", "0x80010000", "kernel_text_base", "kernel_text_end",
        PARTITIONS, WINDOWS, SLOTS, 0, SLOT_WIDTH * SLOTS, 0, 1, 0, 0, 0]
    for tenant, name in ((1, "partition_one"), (2, "partition_two")):
        words += [tenant, f"{name}_context", f"{name}_context + {CONTEXT_BYTES}",
                  name, f"{name} + 64", f"{name}_data", f"{name}_data + 64"]
    for base, size in timer_windows:
        words += [base, base + size]
    words += [bitmap_address, bitmap_address + 8]
    for index in range(SLOTS):
        words += [SLOT_WIDTH, index * SLOT_WIDTH, 0, SLOT_WIDTH * SLOTS, index + 1]
    lines += [f"    .dword {value}" for value in words]
    lines += ["init_desc_end:"]
    result = "\n".join(lines) + "\n"
    result = result.replace("EXPECTED_INIT_WORDS", "\n".join(f"    .dword {v}" for v in words))
    # gp is the corpus's owned check-index spelling; this affects only authored
    # check loads above, never the independently compiled client body.
    authored, suffix = result.split(compiled, 1)
    return authored.replace("li x3,", "li gp,") + compiled + suffix


def observations(records: list[kernelrun.Record], symbols: dict[str, int],
                 bitmap: tuple[int, int]) -> dict[str, object]:
    """Bind each input image, C output, chronological restore and retirement."""
    attempts = tuple(kernelrun.Attempt(symbols[f"attempt_{name}"], 19, target)
                     for name, target in (("root", "R"), ("window0", "W0"),
                                           ("window1", "W1"), ("window2", "W2")))
    restore = kernelrun.Extent(symbols["vos_restore_begin"], symbols["vos_restore_end"])
    bursts = kernelrun.restore_bursts(records, restore)
    snapshots: list[kernelrun.Image] = []
    inputs: list[kernelrun.Image] = []
    input_writes: list[list[kernelrun.Record]] = []
    memory: dict[int, tuple[int, bool]] = {}
    writes: dict[int, list[kernelrun.Record]] = {}
    saved: dict[int, tuple[int, bool]] = {}
    frame_records: list[kernelrun.Record] = []
    frame_started = False
    timer_entries = 0
    registers: dict[int, tuple[int, int]] = {}
    completion_arguments: list[tuple[int, ...]] = []
    completion_returns: list[int] = []
    stale_writes: list[tuple[int, ...]] = []
    bitmap_stores: list[tuple[int, ...]] = []
    current_pc = 0
    publication_seen = False
    no_recreation = True
    minted = 0
    for kind, fields in records:
        if kind == "I":
            current_pc = fields[0]
            if current_pc == symbols["revocation_mint"]:
                minted += 1
                no_recreation = no_recreation and not publication_seen
        if publication_seen and kind in ("R", "W"):
            no_recreation = no_recreation and not (
                symbols["retired_object"] <= fields[0] < symbols["retired_object_end"])
        if publication_seen and stale_writes and kind == "X":
            no_recreation = no_recreation and (fields[1], fields[2]) != (1, stale_writes[0][3])
        if kind == "X":
            registers[fields[0]] = (fields[1], fields[2])
        if kind == "W" and fields[1] == 8:
            memory[fields[0]] = (fields[3], bool(fields[2]))
            for name in ("partition_one_context", "partition_two_context"):
                base = symbols[name]
                if base <= fields[0] < base + 264:
                    writes.setdefault(base, []).append((kind, fields))
            if fields[0] == symbols["partition_one_context"] + 32 and fields[2] == 1:
                stale_writes.append(fields)
            if current_pc == symbols["revocation_publish"]:
                bitmap_stores.append(fields)
                publication_seen = True
            offset = fields[0] - symbols["restore_context"]
            if 0 <= offset < 256 and offset % 8 == 0:
                saved[offset // 8] = (fields[3], bool(fields[2]))
        if kind == "I" and fields[0] == symbols["revocation_gate"]:
            completion_arguments.append(tuple(registers.get(r, (-1, -1))[1] for r in range(10, 16)))
        if kind == "I" and fields[0] == symbols["revocation_return"]:
            completion_returns.append(registers.get(10, (-1, -1))[1])
        if kind == "I" and fields[0] == symbols["target_switch_call"]:
            base = symbols["partition_one_context" if not inputs else "partition_two_context"]
            inputs.append(kernelrun.Image(tuple(memory.get(base + r * 8, (-1, False))
                                                  for r in range(32)), {}))
            input_writes.append(list(writes.get(base, [])))
        if kind == "I" and fields[0] == symbols["vos_restore_setup"]:
            snapshots.append(kernelrun.Image(tuple(saved.get(r, (-1, False)) for r in range(32)), {}))
            saved = {}
            frame_started = True
        if kind == "I" and fields[0] == symbols["kernel_trap"]:
            timer_entries += 1
            if timer_entries == SLOTS:
                break
        if frame_started:
            frame_records.append((kind, fields))
    frame = kernelrun.Frame(tuple(kernelrun.Extent(symbols[name], symbols[f"{name}_end"])
                                  for name in ("partition_one", "partition_two")), 1)
    total = (len(bursts) == SLOTS and len(snapshots) == SLOTS and len(inputs) == SLOTS
             and snapshots == inputs
             and all(kernelrun.switch_is_total((), saved_image, burst)
                     and kernelrun.burst_writes_exactly_once((), burst)
                     for saved_image, burst in zip(inputs, bursts, strict=True)))
    groups = kernel_restore.instruction_groups(records)
    starts = [i for i, (instruction, _) in enumerate(groups)
              if instruction[0] == symbols["vos_restore_setup"]]
    protocols: list[dict[str, bool]] = []
    for index, start in enumerate(starts[:SLOTS]):
        name = ("partition_one", "partition_two")[index]
        end = next((i for i in range(start + 1, len(groups))
                    if groups[i][0][0] == symbols[name]), len(groups))
        phase: list[kernelrun.Record] = list(input_writes[index]) if index < len(input_writes) else []
        for instruction, effects in groups[start:end + 1]:
            phase += [("I", instruction), *effects]
        # Only the actual input writes and contiguous final transfer are in
        # this cut. The scalar primitive checker retains its own chronology,
        # MEPCC, fence, exact-instruction and aligned-effect requirements.
        protocols.append(kernel_restore.observations(phase, {
            **symbols, "context": symbols[f"{name}_context"], "successor": symbols[name]}))
    interrupts = [fields for kind, fields in records if kind == "T"]
    retirement = (len(stale_writes) == 1
        and bitmap_stores == [(bitmap[0], 8, 0, bitmap[1])] * SLOTS
        and completion_arguments == [(1, 1, 1, 1, 1, 1)] * SLOTS
        and completion_returns == [1] * SLOTS and len(inputs) == SLOTS
        and inputs[0].registers[4] == (stale_writes[0][3], False)
        and inputs[1].registers[4] == (0, False))
    return {
        "root_and_window_attempts": kernelrun.well_formed_attempts(attempts)
            and kernelrun.root_is_the_partitions(WINDOWS, attempts, records),
        "complete_restores": total,
        "restore_protocol": len(protocols) == SLOTS and all(all(p.values()) for p in protocols),
        "semantic_completion": retirement,
        "finite_no_recreation": minted == 1 and no_recreation,
        "successor_marker": len(inputs) == SLOTS
            and all(image.registers[7] == (1193046, False) for image in inputs),
        "restore_count": len(bursts),
        "frame_order": kernelrun.frame_is_the_tables(
            kernelrun.Extent(symbols["kernel_text_base"], symbols["kernel_text_end"]), frame, frame_records),
        "timer_boundaries": interrupts == [(1, 7)] * SLOTS and timer_entries == SLOTS,
        "scalar_csrs": all(kind != "C" for burst in bursts for kind, _ in burst),
    }


def snapshot_source(source: str, built: boot_handoff.Assembled, window: bytes,
                    record: bytes, lay: boot_handoff.Layout) -> str:
    """Emit a standard-assembler replay of exactly the released memory bytes.

    The real release ELF is already a flat image. This source preserves all
    compiler/authored instruction mnemonics and places the data and record in
    that same flat load image. Data alignment is zero padding, never text NOPs.
    """
    if source.count("\n.data\n") != 1:
        raise ValueError("snapshot source needs the one composed data section")
    code, data = source.split("\n.data\n")
    data_lines: list[str] = []
    for line in data.splitlines():
        aligned = re.fullmatch(r"\s*\.align\s+(\d+)\s*", line)
        if aligned:
            data_lines.append(f"    .space (-.) & ((1 << {aligned.group(1)}) - 1)")
        else:
            data_lines.append(line)
    header = ("# SPDX-License-Identifier: Apache-2.0\n"
              "# Generated by run.py kernel target from authored kernel C and firmware.\n"
              "# Replay of the actual signed-release memory snapshot; no private keys.\n"
              f"# Released payload SHA256: {hashlib.sha256(built.payload).hexdigest()}\n"
              f"# Handoff record SHA256: {hashlib.sha256(record).hexdigest()}\n")
    emitted = (header + code + f"\n    .space {lay['BRINGUP_MMODE_LOAD_BASE'] + DATA_OFFSET} - .\n"
               + "\n".join(data_lines) + f"\n    .space {lay['BRINGUP_HANDOFF_BASE']} - .\n"
               + "kernel_boot_record:\n"
               + "\n".join("    .byte " + ", ".join(str(b) for b in record[i:i + 16])
                           for i in range(0, len(record), 16)) + "\n")
    assembled = asm.Assembler(emitted, "kernel-snapshot")
    sections, _, entry = assembled.assemble()
    text = next(section for section in sections if section.name == ".text")
    if (text.addr != lay["BRINGUP_MMODE_LOAD_BASE"] or entry != text.addr
            or bytes(text.data) != window + record
            or any(assembled.symbols.get(name) != value for name, value in built.symbols.items())):
        raise ValueError("snapshot replay differs from actual released bytes or symbols")
    return emitted


def replace_once(source: str, old: str, new: str) -> str:
    if source.count(old) != 1:
        raise ValueError(f"control anchor must occur once: {old!r}")
    return source.replace(old, new, 1)


def control_sources(stage: str, consumer: str) -> list[tuple[str, str, str, int | str]]:
    """Executable authority, composition, completion and final-transfer defects."""
    rows: list[tuple[str, str, str, int | str]] = []
    for name, old, new, refusal in (
        ("missing-timer", "        sc      c13, 8(c10)", "        sc      cnull, 8(c10)", 12),
        ("wrong-timer-permission", "        li      t0, 0x7\n        candperm c13, c13, t0\n        sc      c13, 8(c10)",
         "        li      t0, 0x3\n        candperm c13, c13, t0\n        sc      c13, 8(c10)", 12),
        ("sealed-execute-root", "        sc      c13, 24(c10)",
         "        csealentry c13, c13\n        sc      c13, 24(c10)", 14),
        ("overbroad-stack", "        li      t0, kstack_end - kstack_base\n        csetbounds c2, c2, t0",
         "        li      t0, kstack_end - kstack_base + 64\n        csetbounds c2, c2, t0", 19),
        ("overbroad-mtdc", "        cspecialrw cnull, mtdc, c7", "        cspecialrw cnull, mtdc, c8", 20),
    ):
        rows.append((name, replace_once(stage, old, new), consumer, refusal))
    swapped = stage.replace("sc      c13, 8(c10)", "sc      c13, SWAP(c10)")
    swapped = swapped.replace("sc      c13, 16(c10)", "sc      c13, 8(c10)")
    swapped = swapped.replace("sc      c13, SWAP(c10)", "sc      c13, 16(c10)")
    rows.append(("swapped-timers", swapped, consumer, 12))
    timer_anchor = "        csetbounds c13, c13, t0\n        li      t0, 0x7\n        candperm c13, c13, t0\n        sc      c13, 8(c10)"
    rows.append(("overbroad-timer", replace_once(stage, timer_anchor,
        "        li t0, 16\n" + timer_anchor), consumer, 12))
    for name, old, new, refusal in (
        ("resident-copy", "revocation_clear_resident:\n    cmove c20, cnull",
         "revocation_clear_resident:\n    addi x0, x0, 0", 16),
        ("stale-saved-copy", "revocation_filter_saved:\n    lc c20, 32(c19)\n    sc c20, 32(c19)",
         "revocation_filter_saved:\n    addi x0, x0, 0", 16),
        ("epoch-only", "revocation_publish:\n    sd x6, 0(c21)",
         "revocation_publish:\n    addi x0, x0, 0", 16),
        ("missing-fence", "    fence.t\nvos_restore_end:", "vos_restore_end:", "restore_protocol"),
    ):
        rows.append((name, stage, replace_once(consumer, old, new), refusal))
    before, descriptor = consumer.split("init_desc:\n", 1)
    rows.append(("descriptor-data", stage, before + "init_desc:\n" + replace_once(
        descriptor, "    .dword partition_one_data\n", "    .dword partition_one_data + 8\n"), 18))
    words = descriptor.splitlines()
    slot = 18 + PARTITIONS * 7 + WINDOWS * 2
    words[slot] = f"    .dword {SLOT_WIDTH + 64}"
    words[slot + 5] = f"    .dword {SLOT_WIDTH - 64}"
    words[slot + 6] = f"    .dword {SLOT_WIDTH + 64}"
    rows.append(("descriptor-unequal-width", stage, before + "init_desc:\n" + "\n".join(words) + "\n", 18))
    return rows


def execute_controls(root: Path, out: Path, stage: str, consumer: str,
                     lay: boot_handoff.Layout, signer: SlhSigner, binary: Path,
                     inputs: boot_handoff.RotInputs, simulator: Path, timeout: int,
                     compiler_argv: list[str], windows: tuple[tuple[int, int], tuple[int, int]],
                     bitmap: tuple[int, int]) -> list[dict[str, object]]:
    """Compile, sign, release and execute every control; no stillborn counts."""
    rows = control_sources(stage, consumer)
    mutant_dir = out / "controls" / "wrong-c-switch"
    mutant_dir.mkdir(parents=True, exist_ok=True)
    parts = [(root / f"kernel/src/{name}.c").read_text(encoding="utf-8")
             for name in ("context", "executive", "partition", "handoff", "target")]
    parts[0] = replace_once(parts[0], "    post->reg[r] = succ->reg[r];",
                           "    if (r != 7u) { post->reg[r] = succ->reg[r]; }")
    mutant_unit = mutant_dir / "target_unit.c"
    mutant_unit.write_text("\n".join(parts), encoding="utf-8", newline="\n")
    mutant_compile = compiler_diff.compile_c(compiler_argv, mutant_unit, mutant_dir / "compiler", timeout)
    if mutant_compile.exit_code != 0 or mutant_compile.stream is None:
        raise ValueError("the C switch mutant is stillborn: " + mutant_compile.said)
    rows.append(("wrong-c-switch", stage, consumer_source(
        compiler_diff.normalize(mutant_compile.stream), lay["INIT_MAGIC"], windows, bitmap), "complete_restores"))
    results: list[dict[str, object]] = []
    for name, bad_stage, bad_consumer, expected in rows:
        destination = out / "controls" / name
        destination.mkdir(parents=True, exist_ok=True)
        built = boot_handoff.assemble_mmode(root, stage_text=bad_stage, kernel_text=bad_consumer,
            data_base=lay["BRINGUP_MMODE_LOAD_BASE"] + DATA_OFFSET)
        source = bad_stage + "\n" + bad_consumer
        (destination / "kernel.s").write_text(source, encoding="utf-8", newline="\n")
        signed = boot_handoff.build_image(lay, built.payload, security_version=inputs.floor,
            signer=signer.roots[boot_handoff.LIFECYCLES[inputs.lifecycle]], sign=signer.sign)
        image_path = destination / "image.bin"
        image_path.write_bytes(signed)
        release = boot_handoff.rot_stage(binary, image_path, inputs, "slh256s", destination,
                                         roots=signer.roots)
        if release.get("verdict") != "release" or release.get("released") != "1":
            raise ValueError(f"control {name} was not released: {release}")
        window = (destination / "sram.bin").read_bytes()
        record = (destination / "handoff.bin").read_bytes()
        if (window[:len(built.payload)] != built.payload or any(window[len(built.payload):])
                or boot_handoff._record_findings(lay, record, release, built.payload, inputs)):
            raise ValueError(f"control {name} release bytes disagree")
        elf = destination / "kernel.elf"
        boot_handoff.placed_elf(lay, window, record, built.symbols["tohost"], elf)
        argv = [str(simulator), "--config", str(root / boot_handoff.MAIN_CONFIG),
                "--trace-commit", "--inst-limit", "200000", str(elf)]
        done = subprocess.run(argv, cwd=destination, capture_output=True, text=True,
                              timeout=timeout, check=False)
        raw = done.stdout + done.stderr
        (destination / "kernel.trace").write_text(raw, encoding="utf-8", newline="\n")
        normalized = trace.normalize_commit(raw.splitlines())
        records = kernelrun.parse_records(normalized)
        observed = observations(records, built.symbols, bitmap)
        htif, code, _ = compiler_diff.htif_verdict(raw, done.returncode)
        entered = any(kind == "I" and fields[0] == built.symbols["kernel_entry"]
                      for kind, fields in records)
        matched = (htif == "fail" and code == expected) if isinstance(expected, int) else (
            htif == "pass" and observed[expected] is False)
        results.append({"name": name, "matched": entered and matched, "htif": htif,
            "htif_code": code, "decisive": expected, "observations": observed,
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "elf_sha256": receipts.digest(elf), "trace_sha256": trace.digest(normalized),
            "release": release, "argv": argv})
        if name == "wrong-c-switch":
            results[-1]["compilation"] = {"argv": mutant_compile.argv,
                "stream_sha256": mutant_compile.stream_sha256,
                "preprocessed_sha256": mutant_compile.preprocessed.sha256,
                "source_sha256": receipts.digest(mutant_unit)}
    return results


def run(root: Path, ccomp: Path, ccomp_args: list[str], simulator: Path,
        build_receipt: Path, out: Path, timeout: int) -> dict[str, object]:
    """Compile authored C, sign/release its actual payload, and run the consumer.

    The RoT release currently remains host-executed. The report retains that
    explicit chain limitation independently of successful kernel observations.
    """
    root, ccomp, simulator, build_receipt, out = (
        path.resolve() for path in (root, ccomp, simulator, build_receipt, out))
    out.mkdir(parents=True, exist_ok=True)
    sources = receipts.inputs(root, *INPUTS)
    private_inputs = compiler_inputs(ccomp_args)
    host_cc = shutil.which("cc")
    if host_cc is None:
        raise ValueError("the actual RoT source requires a host C compiler")
    host_cc_sha = receipts.digest(Path(host_cc))
    model_sources = receipts.inputs(root, "model")
    simulator_sha = receipts.digest(simulator)
    compiler_sha = receipts.digest(ccomp)
    build_sha = receipts.digest(build_receipt)
    kernel_restore.require_build(json.loads(build_receipt.read_text(encoding="utf-8")),
                                 simulator_sha, model_sources)
    flags = [*ccomp_args, "-fverifiedos-typed", f"-DVOS_MAX_PARTITIONS={PARTITIONS}",
             f"-DVOS_MAX_WINDOWS={WINDOWS}", f"-DVOS_MAX_SLOTS={SLOTS}", f"-DVOS_MAX_CSRS={CSRS}",
             f"-I{root / 'kernel/include'}", f"-I{root / 'firmware/include'}"]
    compiled = compiler_diff.compile_c([str(ccomp), *flags], root / "kernel/test/target_unit.c",
                                       out / "compiler", timeout)
    if compiled.exit_code != 0 or compiled.stream is None:
        raise ValueError(f"kernel C compilation failed: {compiled.said}")
    lay = boot_handoff.layout(root)
    compare, clock = boot_handoff.timer_windows(root)
    windows = ((compare, 8), (clock, 8))
    retired_object = lay["BRINGUP_MMODE_LOAD_BASE"] + DATA_OFFSET + 64
    bitmap = revocation_window(root, retired_object)
    consumer = consumer_source(compiler_diff.normalize(compiled.stream), lay["INIT_MAGIC"], windows, bitmap)
    stage = boot_handoff.scheduled_mmode(root, partition_text=(
        ("partition_one", "partition_one_end"), ("partition_two", "partition_two_end")),
        revocation_word="REVOCATION_WORD")
    stage = f".equ REVOCATION_WORD, {bitmap[0]}\n" + stage
    source = stage + "\n" + consumer
    (out / "kernel.s").write_text(source, encoding="utf-8", newline="\n")
    built = boot_handoff.assemble_mmode(root, stage_text=stage, kernel_text=consumer,
                                       data_base=lay["BRINGUP_MMODE_LOAD_BASE"] + DATA_OFFSET)
    if built.symbols["retired_object"] != retired_object:
        raise ValueError("the retired object disagrees with the declared bitmap word")
    if len(built.payload) > lay["BRINGUP_MMODE_REGION_BYTES"]:
        raise ValueError("kernel payload exceeds the declared M-mode image region")
    signer = SlhSigner(out / "signing", boot_handoff.ROOT_STATES,
                       public_bytes=lay["BOOT_PUBLIC_KEY_BYTES"],
                       signature_bytes=lay["BOOT_SIGNATURE_BYTES"])
    probe_elf = out / "rot-inputs.elf"
    asm.assemble_file(root / boot_handoff.PROBE, probe_elf)
    probe = boot_handoff.emulate(simulator, root / boot_handoff.ROT_CONFIG, probe_elf,
                                 timeout, signature=out / "rot-inputs.sig")
    if probe.verdict != "success" or len(probe.signature) != 3:
        raise ValueError("the actual RoT probe did not supply lifecycle, entropy and floor")
    lifecycle, health, floor = probe.signature
    if not 0 <= lifecycle < len(boot_handoff.LIFECYCLES):
        raise ValueError("the RoT probe supplied an unknown lifecycle")
    entropy = int(bool((health >> 32) & 1) and not bool((health >> 33) & 1))
    inputs = boot_handoff.RotInputs(lifecycle, entropy, 0, floor)
    signed = boot_handoff.build_image(lay, built.payload, security_version=floor,
        signer=signer.roots[boot_handoff.LIFECYCLES[lifecycle]], sign=signer.sign)
    image_path = out / "image.bin"
    image_path.write_bytes(signed)
    binary, host_compiler = boot_handoff.compile_rot_stage(root, out)
    host_stage_sha = receipts.digest(binary)
    release = boot_handoff.rot_stage(binary, image_path, inputs, "slh256s", out, roots=signer.roots)
    if release.get("verdict") != "release" or release.get("released") != "1":
        raise ValueError(f"real signature release refused kernel: {release}")
    window, record = (out / "sram.bin").read_bytes(), (out / "handoff.bin").read_bytes()
    if window[:len(built.payload)] != built.payload or any(window[len(built.payload):]):
        raise ValueError("released kernel bytes differ from the compiled payload")
    if findings := boot_handoff._record_findings(lay, record, release, built.payload, inputs):
        raise ValueError("released kernel record disagrees: " + "; ".join(findings))
    expected = boot_handoff.expected_registers(root, lay, inputs,
        hashlib.shake_256(built.payload).digest(lay["BOOT_DIGEST_BYTES"]))
    if tuple(release.get(key) for key in ("generation", "device", "chain")) != expected:
        raise ValueError("kernel release measurement registers disagree with their owner")
    snapshot = snapshot_source(source, built, window, record, lay)
    (out / "corpus.s").write_text(snapshot, encoding="utf-8", newline="\n")
    elf = out / "kernel.elf"
    boot_handoff.placed_elf(lay, window, record, built.symbols["tohost"], elf)
    argv = [str(simulator), "--config", str(root / boot_handoff.MAIN_CONFIG),
            "--trace-commit", "--inst-limit", "200000", str(elf)]
    done = subprocess.run(argv, cwd=out, capture_output=True, text=True, timeout=timeout, check=False)
    raw = done.stdout + done.stderr
    (out / "kernel.trace").write_text(raw, encoding="utf-8", newline="\n")
    normalized = trace.normalize_commit(raw.splitlines())
    observed = observations(kernelrun.parse_records(normalized), built.symbols, bitmap)
    htif, code, _ = compiler_diff.htif_verdict(raw, done.returncode)
    controls = execute_controls(root, out, stage, consumer, lay, signer, binary,
        inputs, simulator, timeout, [str(ccomp), *flags], windows, bitmap)
    unchanged = (sources == receipts.inputs(root, *INPUTS)
        and model_sources == receipts.inputs(root, "model")
        and compiler_sha == receipts.digest(ccomp) and simulator_sha == receipts.digest(simulator)
        and build_sha == receipts.digest(build_receipt)
        and private_inputs == compiler_inputs(ccomp_args)
        and host_cc_sha == receipts.digest(Path(host_cc)) and host_stage_sha == receipts.digest(binary))
    report: dict[str, object] = {
        "scope": "two-slot C-class kernel under actual signed M-mode release; RoT C runs on host",
        "milestone_acceptance": "open", "sources": sources, "model_sources": model_sources,
        "compiler_sha256": compiler_sha, "simulator_sha256": simulator_sha,
        "build_receipt_sha256": build_sha, "host_compiler": host_compiler,
        "host_compiler_sha256": host_cc_sha, "host_stage_sha256": host_stage_sha,
        "private_compiler_inputs": private_inputs,
        "compilation": {"argv": compiled.argv, "stream_sha256": compiled.stream_sha256,
                        "preprocessed_sha256": compiled.preprocessed.sha256},
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "snapshot_sha256": hashlib.sha256(snapshot.encode()).hexdigest(),
        "revocation": {"object_base": retired_object, "bitmap_address": bitmap[0],
                       "object_bytes": RETIRED_BYTES,
                       "mask": bitmap[1], "root_slot": 3 + PARTITIONS,
                       "borrowed_holders": [], "device_holders": [],
                       "retired_holders": ["c20 before clearing", "partition_one_context.c4"],
                       "sanitized_copies": ["restore_context.c4", "partition_one.c4"],
                       "trusted_minting_roots": ["MTDC", "c10[0]", "root_handle -> c10[0]",
                           "kernel data derivatives in resident registers and protected C frames"],
                       "premise": "fixed trusted kernel never recreates or regrants retired authority; "
                           "finite run only, not general semantic completion or TAL admission"},
        "elf_sha256": receipts.digest(elf), "trace_sha256": trace.digest(normalized),
        "release": release, "signer": signer.identity(), "symbols": built.symbols,
        "htif": htif, "htif_code": code, "observations": observed,
        "controls": controls,
        "inputs_unchanged": unchanged,
        "ok": unchanged and htif == "pass" and all(observed.values())
            and all(case["matched"] for case in controls),
    }
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
