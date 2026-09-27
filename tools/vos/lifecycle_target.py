# SPDX-License-Identifier: Apache-2.0
"""Finite contained supervisor and trusted timer-consumer component experiment.

Reset roots explicitly initialize this composition. It is not firmware, a boot
roster, or execution of the three service bodies. Timing uses a declared one-step
logical clock, source-level loop bounds and a fixed padded release. Physical
WCET and the copy service's separately owned allocation remain separate inputs.
"""

import hashlib
import json
import re
import subprocess
from pathlib import Path

from vos import asm, boot_handoff, dialect, image, jsonc, kernel_effects, kernel_restore
from vos import kernel_target, kernelrun, receipts, trace
from vos.cli import compiler_diff

TEXT_BASE = 0x80200000
DATA_BASE = 0x80008000
SLOT = 200000
STACK = 16384
INPUTS = ("supervisor/include", "supervisor/src", "supervisor/test/context_join.c",
          "kernel/include", "kernel/src", "tools/vos/lifecycle_target.py",
          "tools/vos/asm.py", "tools/vos/dialect.py", "tools/vos/image.py",
          "tools/vos/kernel_effects.py", "tools/vos/kernel_restore.py",
          "tools/vos/kernel_target.py", "tools/vos/kernelrun.py", "tools/vos/trace.py",
          "tools/vos/boot_handoff.py", "tools/vos/jsonc.py", "tools/vos/receipts.py",
          "tools/vos/cli/compiler_diff.py")


def namespace(stream: str, prefix: str) -> str:
    """Composition-local symbol names; instruction and directive bytes unchanged."""
    text = compiler_diff.normalize(stream)
    labels = re.findall(r"^([A-Za-z_.$][A-Za-z_.$0-9]*):", text, re.MULTILINE)
    names = {name: prefix + name.replace(".", "_").replace("$", "_") for name in labels}
    return re.sub(r"[A-Za-z_.$][A-Za-z_.$0-9]*",
                  lambda found: names.get(found.group(), found.group()), text)


def _address(register: int, label: str) -> list[str]:
    return [f"    li x5, {label}", f"    csetaddr c{register}, c18, x5"]


def _root() -> list[str]:
    return ["    cspecialrw c31, mtdc, cnull", "    lc c18, 0(c31)"]


def _cap(register: int, label: str, size: int, permissions: int) -> list[str]:
    return [*_address(register, label), f"    li x5, {size}",
            f"    csetbounds c{register}, c{register}, x5", f"    li x5, {permissions}",
            f"    candperm c{register}, c{register}, x5"]


def _call(name: str, arguments: tuple[str, ...]) -> list[str]:
    lines = _root()
    for register, label in enumerate(arguments, 10):
        lines += _address(register, label)
    return [*lines, f"    call k_{name}", *_root()]


def source(kernel_stream: str, supervisor_stream: str,
           timer_windows: tuple[int, int], bitmap: tuple[int, int],
           boundary_bound: int, *, defect: str = "none", owned_bytes: int = 64,
           service_text: str = "", service_data: str = "", init_extra: str = "",
           after_ack: str = "", retire_extra: str = "", fault_handler: str = "",
           dispatch_handler: str = "", supervisor_publish_extra: str = "") -> str:
    """Compose original compiled units with explicit authority and timer adapters.

    Offline service fragments own their labels and declared extents. The default
    dispatch hook runs no service body. The owned span's size must also be passed
    to the C compiler as VOS_JOIN_OWNED_BYTES and included in the timing account.
    The component account covers empty hooks only. A composition must add every
    injected hook's finite work before supplying its admitted boundary_bound.
    """
    if defect not in {"none", "stale", "incomplete", "ack-write", "asr",
                      "partial", "fault-before", "fault-after", "fault-backoff"}:
        raise ValueError("unknown lifecycle target control")
    if owned_bytes <= 0 or owned_bytes > 524288 or owned_bytes & (owned_bytes - 1):
        raise ValueError("owned span must be a bounded power of two")
    compare, clock = timer_windows
    bitmap_address, first_mask = bitmap
    lines = [".text", ".globl _start", "kernel_text_base:", "_start:",
             "    cmove c18, c1", *_cap(31, "kernel_private", 65536, 0xfe),
             "    sc c18, 0(c31)", "    cspecialrw cnull, mtdc, c31",
             *_cap(2, "kernel_stack", STACK, 0xfe), f"    li x5, {STACK}",
             "    cincoffset c2, c2, x5", "    sc c2, 8(c31)"]
    for register, address, permissions, offset in ((20, compare, 7, 16),
            (20, clock, 3, 24), (20, bitmap_address, 7, 32)):
        lines += [*_cap(register, str(address), 8, permissions), f"    sc c20, {offset}(c31)"]
    lines += ["    la c20, kernel_text_base", "    li x5, kernel_text_end - kernel_text_base",
              "    csetbounds c20, c20, x5", "    li x5, 0x9cb", "    candperm c20, c20, x5",
              "    li x5, lifecycle_timer_entry", "    csetaddr c20, c20, x5",
              "    cspecialrw cnull, mtcc, c20", "    la c20, supervisor_text_base",
              "    li x5, supervisor_text_end - supervisor_text_base",
              "    csetbounds c20, c20, x5", "    li x5, 0x1cb", "    candperm c20, c20, x5",
              "    csealentry c20, c20", "    sc c20, 88(c31)"]
    for i in range(6):
        lines += _cap(20, f"grant_slots + {8 * i}", 8, 7)
        lines += _address(21, "old_roots" if i < 3 else "fresh_roots")
        lines += [f"    sc c20, {8 * (i % 3)}(c21)"]
    for label, shift in (("old_masks", 0), ("fresh_masks", 3)):
        lines += _address(21, label)
        for i in range(3):
            lines += [f"    li x5, {first_mask << (i + shift)}", f"    sd x5, {8 * i}(c21)"]
    lines += _call("vos_join_manifest", ("supervisor_manifest",))
    lines += _root()
    for reg, label in ((10, "effects"), (11, "lifecycle"), (12, "acknowledgment"),
                       (13, "old_roots"), (14, "old_masks")):
        lines += _address(reg, label)
    lines += _cap(17, "lifecycle_owned_span", owned_bytes, 7)
    lines += ["    lc c15, 32(c31)", "    lc c16, 24(c31)", "    call k_vos_join_init",
              *_root(), "    li x3, 1", "    beqz x10, lifecycle_fail", init_extra]
    lines += _address(20, "lifecycle_owned_span")
    lines += [f"    li x6, {owned_bytes // 8}", "    li x7, 0x777", "seed_owned:",
              "    sd x7, 0(c20)", "    cincoffsetimm c20, c20, 8", "    addi x6, x6, -1",
              "    bnez x6, seed_owned", "    lc c20, 24(c31)", "    ld x6, 0(c20)",
              f"    li x7, {SLOT}", "    add x6, x6, x7", "    sd x6, 48(c31)",
              "    li x5, 1", "    sd x5, 40(c31)", "    sd x0, 64(c31)",
              "    li x7, 0", "    j lifecycle_dispatch_setup", "lifecycle_timer_entry:",
              kernel_effects.emit_save("lifecycle_trap", 128),
              kernel_effects.emit_scrub("lifecycle_trap"), *_root(), "    lc c2, 8(c31)",
              "    csrr x5, mcause", "    li x6, 0x8000000000000007",
              "    bne x5, x6, lifecycle_fault_entry", "    ld x5, 64(c31)",
              "    bnez x5, lifecycle_finish_check"]
    lines += _root()
    for reg, label in ((10, "lifecycle"), (11, "effects"), (12, "request")):
        lines += _address(reg, label)
    lines += ["    lc c20, 24(c31)", "    ld x13, 0(c20)",
              "    call k_vos_kernel_lifecycle_prepare", *_root(), "    li x5, 2",
              "    beq x10, x5, lifecycle_retire_clear", "    li x5, 3",
              "    beq x10, x5, lifecycle_start", "    j lifecycle_acknowledge",
              "lifecycle_start:"]
    lines += _call("vos_kernel_lifecycle_start_finish", ("lifecycle", "effects"))
    lines += ["    li x3, 2", "    beqz x10, lifecycle_fail", "    j lifecycle_acknowledge",
              "lifecycle_retire_clear:"]
    lines += _call("vos_kernel_lifecycle_mask", ("lifecycle",))
    lines += ["    lc c20, 32(c31)", "    ld x6, 0(c20)", "    or x6, x6, x10"]
    lines += _address(21, "old_roots")
    lines += ["    lc c17, 0(c21)", "lifecycle_bitmap_publish:", "    sd x6, 0(c20)",
              "    fence rw, rw", "    ld x6, 0(c20)", "    sd x6, 80(c31)"]
    lines += ["lifecycle_old_root_reload:", "    lc c16, 0(c21)",
              "lifecycle_old_root_tag:", "    cgettag x5, c16", "    li x3, 12",
              "    bnez x5, lifecycle_fail"]
    lines += _address(21, "fresh_roots")
    lines += ["    lc c16, 0(c21)", "lifecycle_fresh_root_tag:", "    cgettag x5, c16",
              "    li x3, 13", "    beqz x5, lifecycle_fail"]
    # An abandoned trap/fresh-entry image and MEPCC cannot retain the old PCC.
    for label in ("saved_clear", "restore_context"):
        lines += _address(20, label)
        lines += ["    li x6, 33", f"lifecycle_retire_{label}:", "    sc cnull, 0(c20)",
                  "    cincoffsetimm c20, c20, 8", "    addi x6, x6, -1",
                  f"    bnez x6, lifecycle_retire_{label}"]
    lines += ["lifecycle_retire_mepcc:", "    cmove c5, cnull",
              "    cspecialrw cnull, mepcc, c5", retire_extra]
    if defect != "incomplete":
        lines += ["    cmove c17, cnull"]
    lines += ["lifecycle_resident_observation:", "    cgettag x11, c17", "    seqz x11, x11"]
    lines += _address(10, "effects")
    lines += ["    call k_vos_join_resident", *_root()]
    for reg, label in ((10, "lifecycle"), (11, "effects"), (13, "fresh_roots"), (14, "fresh_masks")):
        lines += _address(reg, label)
    lines += ["    ld x12, 80(c31)", "    lc c20, 24(c31)", "    ld x15, 0(c20)",
              "    call k_vos_kernel_lifecycle_retire_finish", *_root(),
              "    li x3, 3", ("    bnez x10, lifecycle_fail" if defect == "incomplete" else
                                "    beqz x10, lifecycle_fail"), "lifecycle_acknowledge:"]
    lines += _address(20, "acknowledgment")
    lines += ["    sd x0, 0(c20)"]
    for reg, label in ((10, "lifecycle"), (11, "effects"), (12, "acknowledgment")):
        lines += _address(reg, label)
    lines += ["    lc c20, 24(c31)", "    ld x13, 0(c20)",
              "    call k_vos_kernel_lifecycle_acknowledge", *_root()]
    lines += _address(20, "acknowledgment")
    lines += ["lifecycle_ack_publish:", "    fence rw, rw", "    sd x10, 0(c20)", "    mv x12, x10"]
    lines += _address(10, "lifecycle") + _address(11, "effects")
    lines += ["    call k_vos_kernel_lifecycle_published", *_root(),
              "    li x3, 4", "    beqz x10, lifecycle_fail"]
    lines += _address(20, "request")
    lines += ["    sd x0, 0(c20)", after_ack]
    if defect in {"stale", "incomplete"}:
        lines += _address(20, "acknowledgment")
        lines += ["    ld x5, 8(c20)", f"    li x6, {2 if defect == 'stale' else 3}",
                  "    bne x5, x6, lifecycle_control_continue"]
        if defect == "incomplete":
            lines += _call("vos_join_incomplete", ("effects", "lifecycle"))
            lines += ["    li x3, 11", "    beqz x10, lifecycle_fail"]
        lines += ["    j lifecycle_control_pass", "lifecycle_control_continue:"]
    lines += _address(20, "acknowledgment")
    lines += ["    ld x5, 0(c20)", "    li x6, 3", "    bne x5, x6, lifecycle_not_done",
              "    li x5, 1", "    sd x5, 64(c31)", "lifecycle_not_done:",
              "    ld x5, 40(c31)", "    addi x5, x5, 1", "    sd x5, 40(c31)",
              "    li x6, 12", "    li x3, 5", "    bgtu x5, x6, lifecycle_fail",
              "    ld x7, 48(c31)", f"    li x6, {boundary_bound}", "    add x7, x7, x6",
              "    sd x7, 56(c31)", f"    li x6, {SLOT}", "    add x6, x7, x6",
              "    sd x6, 48(c31)", "lifecycle_dispatch_setup:",
              "    lc c20, 16(c31)", "    ld x6, 48(c31)", "    sd x6, 0(c20)"]
    # No abandoned supervisor stack or saved register image survives fresh entry.
    for label, size in (("supervisor_stack", STACK), ("saved_clear", 264)):
        lines += _address(20, label)
        lines += [f"    li x6, {size // 8}", f"{label}_loop:", "    sc cnull, 0(c20)",
                  "    cincoffsetimm c20, c20, 8", "    addi x6, x6, -1", f"    bnez x6, {label}_loop"]
    lines += _address(19, "restore_context")
    for reg in range(33):
        lines += [f"    sc cnull, {reg * 8}(c19)"]
    for reg, label, size, perm in ((2, "supervisor_stack", STACK, 0xfe),
            (10, "supervisor_manifest", 512, 3), (11, "acknowledgment", 256, 3),
            (12, "request", 512, 7)):
        lines += _cap(20, label, size, perm)
        if reg == 2:
            lines += [f"    li x5, {STACK}", "    cincoffset c20, c20, x5"]
        lines += [f"    sc c20, {reg * 8}(c19)"]
    lines += ["    lc c20, 88(c31)", "    sc c20, 256(c19)", "    li x6, 2"]
    lines += _address(20, "acknowledgment")
    lines += ["    ld x5, 32(c20)", "    bnez x5, lifecycle_policy_set",
              "    li x6, 1", "lifecycle_policy_set:", "    sc c6, 104(c19)",
              "    ld x5, 64(c31)", "    beqz x5, lifecycle_policy_done", "    sc cnull, 104(c19)",
              "lifecycle_policy_done:", "    lc c20, 24(c31)", "    cmove c31, c19",
              "    beqz x7, lifecycle_restore", "lifecycle_padding_sample:", "    ld x5, 0(c20)",
              "    sub x6, x7, x5", "    addi x6, x6, -44", "    li x3, 6",
              "    bltz x6, lifecycle_fail", "    srli x8, x6, 1", "    andi x6, x6, 1",
              "    beqz x6, lifecycle_padding_even", "    nop", "lifecycle_padding_even:",
              "    beqz x8, lifecycle_restore", "lifecycle_padding_loop:", "    addi x8, x8, -1",
              "    bnez x8, lifecycle_padding_loop", "lifecycle_restore:", kernel_restore.emit(),
              "lifecycle_finish_check:"]
    lines += _call("vos_join_outcome", ("effects", "lifecycle"))
    lines += ["    li x3, 7", "    beqz x10, lifecycle_fail"]
    lines += _call("vos_join_dispatchable", ("effects",))
    lines += ["    li x3, 8", "    beqz x10, lifecycle_fail", "lifecycle_service_dispatch:",
              dispatch_handler, "    j lifecycle_control_pass", "lifecycle_fault_entry:"]
    lines += _address(10, "request")
    lines += ["    call k_vos_kernel_lifecycle_fault", *_root(), fault_handler]
    if defect in {"ack-write", "asr"}:
        lines += ["    cspecialrw c20, mepcc, cnull", "    cgetaddr x5, c20",
                  "    li x6, supervisor_permission_control", "    li x3, 9",
                  "    bne x5, x6, lifecycle_fail", "    j lifecycle_control_pass"]
    elif defect in {"fault-before", "fault-after", "fault-backoff"}:
        # Fault processing only invalidates the publication. Resume a trusted
        # idle PCC until the original timer fires; only that timer consumes.
        lines += ["    la c20, lifecycle_fault_idle", "    csealentry c20, c20",
                  "    cspecialrw cnull, mepcc, c20", "    mret",
                  "lifecycle_fault_idle:", "    wfi", "    j lifecycle_fault_idle"]
    else:
        lines += ["    li x3, 10", "    j lifecycle_fail"]
    lines += ["lifecycle_control_pass:", "    li x3, 0", "lifecycle_fail:", *_root(),
              "    slli x6, x3, 1", "    ori x6, x6, 1"]
    lines += _address(20, "tohost")
    lines += ["    sd x6, 0(c20)", "lifecycle_halt:", "    j lifecycle_halt",
              namespace(kernel_stream, "k_"), ".align 17", "kernel_text_end:",
              "supervisor_text_base:", "supervisor_entry:"]
    for reg in (1, 4):
        lines += [f"    cgettag x5, c{reg}", "    bnez x5, supervisor_failed",
                  f"    cgetaddr x5, c{reg}", "    bnez x5, supervisor_failed"]
    lines += ["    cspecialrw c20, pcc, cnull"]
    for reg, label, size, perm, cursor in ((20, "supervisor_text_base",
            "supervisor_text_end - supervisor_text_base", 0x1cb, None),
            (2, "supervisor_stack", str(STACK), 0xfe, f"supervisor_stack + {STACK}"),
            (10, "supervisor_manifest", "512", 3, "supervisor_manifest"),
            (11, "acknowledgment", "256", 3, "acknowledgment"),
            (12, "request", "512", 7, "request")):
        lines += [f"supervisor_cap_{reg}_tag:", f"    cgettag x5, c{reg}",
                  "    beqz x5, supervisor_failed", f"    cgetsealed x5, c{reg}",
                  "    bnez x5, supervisor_failed", f"supervisor_cap_{reg}_base:",
                  f"    cgetbase x5, c{reg}", f"    li x6, {label}",
                  "    bne x5, x6, supervisor_failed", f"supervisor_cap_{reg}_length:",
                  f"    cgetlen x5, c{reg}", f"    li x6, {size}",
                  "    bne x5, x6, supervisor_failed", f"supervisor_cap_{reg}_permissions:",
                  f"    cgetperm x5, c{reg}", f"    li x6, {perm}",
                  "    bne x5, x6, supervisor_failed"]
        if cursor is not None:
            lines += [f"    cgetaddr x5, c{reg}", f"    li x6, {cursor}",
                      "    bne x5, x6, supervisor_failed"]
    if defect in {"ack-write", "asr"}:
        lines += ["supervisor_permission_control:", "    sd x0, 0(c11)" if defect == "ack-write" else
                  "    csrr x5, mcause"]
    if defect == "fault-backoff":
        lines += ["    ld x5, 32(c11)", "    li x6, 1", "    bne x5, x6, supervisor_react",
                  "    ld x5, 80(c11)", "    ld x6, 88(c11)", "    bgeu x5, x6, supervisor_react",
                  "supervisor_phase_fault:", "    ld x5, 0(cnull)", "supervisor_react:"]
    lines += ["    cincoffsetimm c2, c2, -16", "    sc c12, 0(c2)", "    sc c11, 8(c2)",
              "    sd x0, 0(c12)", "    call s_vos_join_react", "    lc c12, 0(c2)",
              "    lc c11, 8(c2)", "    cincoffsetimm c2, c2, 16",
              "    li x5, -1", "    beq x10, x5, supervisor_failed",
              "    beqz x10, supervisor_poll_return", supervisor_publish_extra]
    if defect == "partial":
        lines += ["    ld x5, 80(c11)", "    beqz x5, supervisor_poll_return"]
    if defect == "fault-before":
        lines += ["    ld x5, 80(c11)", "    bnez x5, supervisor_publish",
                  "supervisor_phase_fault:", "    ld x5, 0(cnull)"]
    if defect == "stale":
        lines += ["    ld x5, 16(c12)", "    addi x5, x5, -1", "    sd x5, 16(c12)"]
    lines += ["supervisor_publish:", "    fence rw, rw", "    sd x10, 0(c12)"]
    if defect == "fault-after":
        lines += ["    ld x5, 80(c11)", "    bnez x5, supervisor_poll_return",
                  "supervisor_phase_fault:", "    ld x5, 0(cnull)"]
    lines += ["supervisor_poll_return:", "    wfi", "    j supervisor_poll_return",
              "supervisor_failed:", "    ld x5, 0(cnull)", "    j supervisor_failed",
              namespace(supervisor_stream, "s_"), ".align 16", "supervisor_text_end:",
              service_text, ".data", ".align 9", "grant_slots:", "    .space 512",
              ".align 16", "kernel_private:", "    .space 128",
              "saved_clear:", "    .space 264", "    .space 120", "restore_context:", "    .space 264",
              "service_state:", "    .space 256",
              ".align 6", "old_roots:", "    .space 24", "fresh_roots:", "    .space 24",
              "old_masks:", "    .space 24", "fresh_masks:", "    .space 24", "tohost:", "    .dword 0",
              ".align 12", "effects:", "    .space 8192", "lifecycle:", "    .space 512",
              ".align 14", "kernel_stack:", f"    .space {STACK}", ".align 16", "kernel_private_end:",
              ".align 9", "request:", "    .space 512", ".align 8", "acknowledgment:", "    .space 256",
              ".align 9", "supervisor_manifest:", "    .space 512", ".align 14", "supervisor_stack:",
              f"    .space {STACK}",
              f".align {owned_bytes.bit_length() - 1}", "lifecycle_owned_span:", f"    .space {owned_bytes}",
              service_data]
    return "\n".join(lines) + "\n"


def instruction_counts(stream: str) -> dict[str, int]:
    """Count expanded instructions in each emitted C function, including branches."""
    assembled = asm.Assembler(compiler_diff.normalize(stream), "bound", data_base=0x81000000)
    assembled.assemble()
    names = re.findall(r"^\.globl\s+(\S+)", stream, re.MULTILINE)
    starts = sorted((assembled.symbols[name], name) for name in names)
    counts = dict.fromkeys(names, 0)
    for site in assembled.sites:
        preceding = [name for address, name in starts if address <= site.address]
        if preceding:
            counts[preceding[-1]] += 1
    if "effect_clear_unit" not in counts:
        return counts
    # Recognize the owned-byte loop, whose runtime count is supplied only for
    # unit 2. Refuse compiler shape drift instead of silently reusing its cost.
    body = compiler_diff.normalize(stream).split("effect_clear_unit:", 1)[1].split(".globl", 1)[0]
    body_lines = [line.strip() for line in body.splitlines() if line.strip()]
    labels = {line[:-1]: i for i, line in enumerate(body_lines) if line.endswith(":")}
    owned_loops = []
    for i, line in enumerate(body_lines):
        parts = line.split()
        if len(parts) == 2 and parts[0] == "j" and parts[1] in labels and labels[parts[1]] < i:
            loop = body_lines[labels[parts[1]] + 1:i + 1]
            opcodes = [item.split()[0] for item in loop]
            if "sb" in opcodes and "lw" in opcodes:
                expected = ["mv", "lc", "cmove", "addi", "cincoffset", "lw", "bgeu",
                            "lc", "cmove", "addi", "cincoffset", "lc", "mv", "slli",
                            "srli", "cincoffset", "addiw", "sb", "mv", "addiw", "j"]
                if opcodes != expected or i + 1 >= len(body_lines) or not body_lines[i + 1].endswith(":"):
                    raise ValueError("owned-byte clear loop changed; a fresh finite account is required")
                exit_label = body_lines[i + 1][:-1]
                if loop[6].split(",")[-1].strip() != exit_label:
                    raise ValueError("owned-byte loop no longer exits after its counted body")
                start, end = assembled.symbols[parts[1]], assembled.symbols[exit_label]
                owned_loops.append(sum(start <= site.address < end for site in assembled.sites))
    if len(owned_loops) != 1:
        raise ValueError("expected exactly one bounded owned-byte clear loop")
    counts["effect_clear_unit.owned_byte_loop"] = owned_loops[0]
    return counts


def longest_path(counts: dict[str, int], owned_bytes: int = 64,
                 max_boundary_steps: int = 2097152) -> dict[str, object]:
    """Conservative source-bound whole-function charges for this finite instance.

    Sequential loops charge their sum plus one; each whole emitted body is paid
    that many times. Callees are charged separately at maximum call counts. The
    three service units own one bounded span, no extra owned cap slots, and two32
    slot protected frames each. This deliberately overcounts branches and loop
    bodies, and bounds refused paths by the complete accepted path's work.
    """
    def cost(name: str, multiplier: int = 1) -> int:
        if name not in counts:
            raise ValueError(f"unaccounted compiled function {name}")
        return counts[name] * multiplier
    word = cost("lifecycle_word", 9)
    put = cost("lifecycle_put", 9)
    clear_caps = cost("effect_clear_caps", 34)
    clear_unit = cost("effect_clear_unit", 1 + 64 + 2) + 5 * clear_caps
    owned_clear = cost("effect_clear_unit.owned_byte_loop", owned_bytes)
    request = cost("join_kernel_request_current")
    prepare = cost("vos_kernel_lifecycle_prepare", 1 + 26 + 16 + 3 + 3) + 65 * word
    prepare += 6 * request + cost("vos_kernel_acquire") + cost("vos_kernel_retirement_mask")
    prepare += cost("effect_mask", 4) + cost("join_kernel_backoff")
    retirement = cost("vos_kernel_lifecycle_retire_finish") + cost("vos_kernel_publication")
    retirement += cost("vos_kernel_retire", 4) + cost("effect_mask", 4) + 3 * clear_unit + owned_clear
    retirement += 2 * cost("vos_semantic_completion") + cost("vos_kernel_replenish", 10)
    retirement += cost("join_kernel_backoff") + cost("vos_join_resident") + cost("vos_kernel_lifecycle_mask")
    start = cost("vos_kernel_lifecycle_start_finish", 4)
    start += 3 * (cost("vos_kernel_start", 4) + request + clear_caps)
    ack = cost("vos_kernel_lifecycle_acknowledge") + cost("lifecycle_fields", 1 + 31 + 16)
    ack += 59 * put + cost("join_kernel_backoff") + cost("vos_kernel_lifecycle_published")
    ack += cost("vos_kernel_release")
    # At most 2048 stack words, 33 save words, 33 restore-image slots, plus
    # fixed setup, publication, root derivations, checks and35 restore steps.
    assembly = 4 * (STACK // 8 + 99) + 33 + 1024
    total = prepare + max(retirement, start) + ack + assembly
    padded = 1 << total.bit_length()
    if padded > max_boundary_steps:
        raise ValueError("finite handler account exceeds the composition's declared step limit")
    return {"function_instruction_counts": counts, "prepare": prepare,
            "retirement": retirement, "owned_byte_loop_steps": owned_clear,
            "start": start, "acknowledge": ack,
            "assembly_and_cleanup": assembly, "longest_path_steps": total,
            "padded_boundary_steps": padded, "owned_bytes": owned_bytes,
            "clock": "one executor step per tick; not physical WCET"}


def reaction_path(counts: dict[str, int]) -> dict[str, object]:
    """Whole-function overcount for the immutable three-unit, one-delay policy."""
    charges = {
        "vos_join_react": 1, "vos_supervisor_context_recover": 1,
        "vos_supervisor_context_step": 1 + 64 + 16 + 3,
        "context_ack_ok": 2 * (1 + 16 + 4 + 3), "context_ack_read": 2,
        "vos_supervisor_manifest_ok": 3 * (1 + 8 + 1),
        "vos_supervisor_order_ok": 3 * (1 + 3), "members": 7,
        "vos_supervisor_plan": 1 + 3, "vos_supervisor_backoff": 1,
    }
    total = 256 + sum(counts[name] * count for name, count in charges.items())
    if total >= SLOT:
        raise ValueError("supervisor reaction account does not fit its admitted fixed slot")
    return {"function_instruction_counts": counts, "whole_body_multipliers": charges,
            "entry_publication_steps": 256, "longest_path_steps": total, "slot_steps": SLOT}


def observations(log: Path, symbols: dict[str, int], windows: tuple[int, int],
                 bitmap: tuple[int, int], bound: dict[str, object],
                 defect: str = "none") -> dict[str, object]:
    """Stream actual retire/effect records; do not infer success from HTIF alone."""
    pc = previous_pc = order = 0
    count = 0
    digest = hashlib.sha256()
    buffers = {name: bytearray(size) for name, size in
               (("request", 512), ("acknowledgment", 256), ("lifecycle_owned_span", 64))}
    slots = {name: {} for name in ("saved_clear", "restore_context")}
    requests, acknowledgments, entries, releases, traps = [], [], [], [], []
    caps: dict[str, list[int]] = {}
    checks = {}
    for reg, base, length, permissions in (
            (20, "supervisor_text_base", symbols["supervisor_text_end"] - symbols["supervisor_text_base"], 0x1cb),
            (2, "supervisor_stack", STACK, 0xfe), (10, "supervisor_manifest", 512, 3),
            (11, "acknowledgment", 256, 3), (12, "request", 512, 7)):
        for suffix, expected in (("tag", 1), ("base", symbols[base]),
                                 ("length", length), ("permissions", permissions)):
            name = f"supervisor_cap_{reg}_{suffix}"
            checks[symbols[name]] = (name, expected)
            caps[name] = []
    special_zero = []
    cleared_before_retire = []
    restore = {}
    restore_good = []
    retire_order = None
    timer_order = None
    sample = None
    release = None
    bitmap_writes, bitmap_reads, old_tags, fresh_tags, resident_tags = [], [], [], [], []
    supervisor_writes_ok = True
    extra_syscall = False
    publication_fences = []
    work_steps = []
    owned_seeded = False
    mepcc = None
    last_ack = []
    last_trap = None
    timer_consumption = []
    reaction_steps = []
    reaction_entry = None
    with log.open(encoding="utf-8") as lines:
        for raw in lines:
            text = raw.strip()
            if not trace.COMMIT_RE.fullmatch(text):
                continue
            normalized = trace.ORDER_RE.sub("I ", text)
            if count:
                digest.update(b"\n")
            digest.update(normalized.encode())
            count += 1
            kind, fields = kernelrun.parse_record(normalized)
            if kind == "I":
                previous_pc, pc = pc, fields[0]
                order = int(text.split()[1])
                extra_syscall |= fields[1] == 0x73
                if pc == symbols["vos_restore_begin"]:
                    restore = {}
                if pc == symbols["lifecycle_timer_entry"]:
                    timer_order = order
                if pc == symbols["supervisor_entry"]:
                    entries.append(order)
                    reaction_entry = order
                    restore_good.append(
                        set(restore) == set(range(1, 32)) and
                        all(tag == int(reg in (2, 10, 11, 12)) and
                            (reg in (2, 10, 11, 12, 13) or value == 0)
                            for reg, (tag, value) in restore.items()) and
                        previous_pc == symbols["vos_restore_dispatch"])
                    if sample is not None and release is not None:
                        releases.append({"expected": release,
                                         "observed": sample[1] + order - sample[0]})
                        sample = None
                if pc == symbols["k_vos_kernel_lifecycle_retire_finish"]:
                    retire_order = order
                    cleared_before_retire.append(
                        mepcc == (0, 0) and all(len(values) == 33 and
                            all(value == (0, 0) for value in values.values())
                            for values in slots.values()))
                if pc == symbols["k_vos_kernel_lifecycle_prepare"]:
                    timer_consumption.append(last_trap == (1, 7))
                if pc == symbols["k_vos_kernel_lifecycle_fault"] and requests and any(buffers["request"][:8]):
                    requests[-1]["invalidated"] = True
                if pc == symbols["supervisor_poll_return"] and reaction_entry is not None:
                    reaction_steps.append(order - reaction_entry)
                    reaction_entry = None
                continue
            if kind == "T":
                traps.append({"order": order, "pc": pc, "interrupt": fields[0], "cause": fields[1]})
                last_trap = fields
            if kind == "S" and fields[0] == dialect.SCRS["mepcc"]:
                mepcc = fields[1:]
                if symbols["lifecycle_retire_mepcc"] <= pc < symbols["lifecycle_resident_observation"]:
                    special_zero.append(fields[1:] == (0, 0))
            if kind == "X":
                if symbols["vos_restore_begin"] <= pc < symbols["vos_restore_end"]:
                    restore[fields[0]] = fields[1:]
                if pc in checks and fields[0] == 5:
                    caps[checks[pc][0]].append(fields[2])
                for label, result, reg in (("lifecycle_old_root_tag", old_tags, 5),
                        ("lifecycle_fresh_root_tag", fresh_tags, 5),
                        ("lifecycle_resident_observation", resident_tags, 11)):
                    if pc == symbols[label] and fields[0] == reg:
                        result.append(fields[2])
            if kind == "R":
                if fields[0] == bitmap[0]:
                    bitmap_reads.append(fields[3])
                if pc == symbols["lifecycle_padding_sample"] and fields[0] == windows[1]:
                    sample = (order, fields[3])
                    if timer_order is not None:
                        work_steps.append(order - timer_order + 44)
            if kind != "W":
                continue
            address, width, tag, value = fields
            if address == symbols["kernel_private"] + 56:
                release = value
            if address == bitmap[0]:
                bitmap_writes.append(value)
            if symbols["supervisor_text_base"] <= pc < symbols["supervisor_text_end"]:
                supervisor_writes_ok &= any(symbols[name] <= address and address + width <= symbols[name] + size
                                            for name, size in (("request", 512), ("supervisor_stack", STACK)))
            for name, values in slots.items():
                offset = address - symbols[name]
                if 0 <= offset < 264 and width == 8 and offset % 8 == 0:
                    values[offset // 8] = (tag, value)
            for name, data in buffers.items():
                offset = address - symbols[name]
                if 0 <= offset and offset + width <= len(data):
                    data[offset:offset + width] = value.to_bytes(width, "little")
            if pc == symbols["seed_owned"]:
                owned_seeded |= value == 0x777
            if address == symbols["request"] and width == 8 and value != 0:
                words = [int.from_bytes(buffers["request"][i:i + 8], "little") for i in range(0, 512, 8)]
                requests.append({"order": order, "words": words, "prior_ack": last_ack, "invalidated": False})
                publication_fences.append(previous_pc == symbols["supervisor_publish"])
            if address == symbols["acknowledgment"] and width == 8 and pc == symbols["lifecycle_ack_publish"] + 4:
                words = [int.from_bytes(buffers["acknowledgment"][i:i + 8], "little") for i in range(0, 256, 8)]
                last_ack = words
                acknowledgments.append({"order": order, "words": words,
                                       "owned_zero": not any(buffers["lifecycle_owned_span"])})
                publication_fences.append(previous_pc == symbols["lifecycle_ack_publish"])
    facts = {
        "actual_fresh_bounded_entry": bool(entries) and all(restore_good),
        "all_capability_checks_observed": all(len(caps[name]) == len(entries) and
            all(value == expected for value in caps[name]) for name, expected in checks.values()),
        "supervisor_stores_confined": supervisor_writes_ok,
        "no_ecall": not extra_syscall,
        "sequence_last_fences": all(publication_fences),
    }
    if defect in {"none", "partial", "fault-before", "fault-after", "fault-backoff"}:
        acks = [item["words"] for item in acknowledgments]
        accepted_requests = [item for item in requests if not item["invalidated"]]
        reqs = [item["words"] for item in accepted_requests]
        facts.update({
            "fixed_release_empty_and_occupied": len(releases) >= 4 and
                all(item["expected"] == item["observed"] for item in releases) and
                any(a[0] == b[0] == 2 for a, b in zip(acks, acks[1:])),
            "work_within_account": bool(work_steps) and max(work_steps) <= bound["longest_path_steps"],
            "timer_only_consumption": bool(timer_consumption) and all(timer_consumption),
            "exact_start_retire_start": [req[0:2] for req in reqs] == [[1, 2], [2, 1], [3, 2]] and
                all(req[3] == 7 for req in reqs) and all(req[4] == 3 and req[6:12] == [0, 0, 1, 1, 2, 0]
                                                        for req in (reqs[0], reqs[-1])) if len(reqs) == 3 else False,
            "backoff_uses_ack_clock": len(accepted_requests) == 3 and accepted_requests[-1]["prior_ack"][10] >= accepted_requests[-1]["prior_ack"][11],
            "post_replenish_epoch": bool(acks) and acks[-1][0] == 3 and acks[-1][3:5] == [0x100000002, 2] and
                acks[-1][6] == 7 and acks[-1][9] == 1 and all(word == 0 for word in acks[-1][12:28]),
            "bitmap_and_fresh_roots": bitmap_writes == [7] and 7 in bitmap_reads and old_tags == [0] and fresh_tags == [1],
            "saved_context_and_mepcc_cleared": cleared_before_retire == [True] and special_zero == [True],
            "resident_old_root_cleared": resident_tags == [0],
            "real_owned_bytes_cleared": owned_seeded and any(item["words"][0] == 2 and item["owned_zero"] for item in acknowledgments),
            "reaction_within_slot": bool(reaction_steps) and max(reaction_steps) < SLOT,
        })
        if defect == "partial":
            facts["unpublished_fields_do_not_advance"] = bool(acks) and acks[0][0] == 0 and acks[0][4] == 0 and acks[0][6] == 0
        if defect.startswith("fault-"):
            faults = [item for item in traps if item["interrupt"] == 0]
            facts["phase_fault_actual_and_recovered"] = bool(faults) and all(item["pc"] == symbols["supervisor_phase_fault"] for item in faults)
            if defect == "fault-after":
                facts["fault_after_sequence_invalidated"] = sum(item["invalidated"] for item in requests) == 1 and acks[0][0] == 0
    elif defect == "stale":
        facts["stale_definitive_refusal"] = bool(acknowledgments) and acknowledgments[-1]["words"][0:2] == [1, 2]
    elif defect == "incomplete":
        facts["incomplete_prevents_dispatch"] = bool(acknowledgments) and acknowledgments[-1]["words"][0:2] == [2, 3] and resident_tags == [1]
    else:
        facts["permission_fault_at_named_instruction"] = len(traps) == 1 and traps[0]["interrupt"] == 0 and traps[0]["pc"] == symbols["supervisor_permission_control"]
        facts["fault_invalidates_request"] = not any(buffers["request"][:8]) and not acknowledgments
    return {"facts": facts, "ok": all(facts.values()), "records": count,
            "trace_digest": digest.hexdigest()[:16], "entries": entries,
            "release_instants": releases, "handler_steps_before_padding": work_steps,
            "reaction_steps": reaction_steps,
            "requests": requests, "acknowledgments": acknowledgments, "traps": traps,
            "retire_order": retire_order}


def run(root: Path, ccomp: Path, config: Path, simulator: Path,
        build_receipt: Path, out: Path, timeout: int = 180) -> dict[str, object]:
    root, ccomp, config, simulator, build_receipt, out = (
        p.resolve() for p in (root, ccomp, config, simulator, build_receipt, out))
    out.mkdir(parents=True, exist_ok=True)
    receipts.write(out / "report.json", {"status": "incomplete", "ok": False})
    inputs = receipts.inputs(root, *INPUTS)
    model = receipts.inputs(root, "model")
    external = {"ccomp": receipts.digest(ccomp), "config": receipts.digest(config),
                "simulator": receipts.digest(simulator), "model_receipt": receipts.digest(build_receipt)}
    kernel_restore.require_build(json.loads(build_receipt.read_text(encoding="utf-8")), external["simulator"], model)
    args = [str(ccomp), "-conf", str(config), "-fverifiedos-typed",
            "-I" + str(root / "supervisor/include"), "-I" + str(root / "kernel/include")]
    source_path = root / "supervisor/test/context_join.c"
    kernel = compiler_diff.compile_c([*args, "-DVOS_JOIN_KERNEL"], source_path, out / "kernel")
    supervisor = compiler_diff.compile_c(args, source_path, out / "supervisor")
    if kernel.stream is None or supervisor.stream is None:
        raise ValueError(f"component compilation refused: {kernel.said}; {supervisor.said}")
    bound = longest_path(instruction_counts(kernel.stream))
    reaction = reaction_path(instruction_counts(supervisor.stream))
    windows = boot_handoff.timer_windows(root)
    assembly = source(kernel.stream, supervisor.stream, windows, (0, 1), int(bound["padded_boundary_steps"]))
    probe = asm.Assembler(assembly, "layout", text_base=TEXT_BASE, data_base=DATA_BASE)
    probe.assemble()
    bitmap = kernel_target.revocation_window(root, probe.symbols["grant_slots"])
    if bitmap[1] != 1:
        raise ValueError("six grant roots must begin in one aligned512-byte bitmap block")
    profile = jsonc.load(root / boot_handoff.MAIN_CONFIG)
    profile["platform"]["instructions_per_tick"] = 1
    profile_path = out / "profile.json"
    receipts.write(profile_path, profile)
    cases = []
    for defect in ("none", "stale", "incomplete", "ack-write", "asr",
                   "partial", "fault-before", "fault-after", "fault-backoff"):
        text = source(kernel.stream, supervisor.stream, windows, bitmap,
                      int(bound["padded_boundary_steps"]), defect=defect)
        emitted = out / f"{defect}.s"
        emitted.write_text(text, encoding="utf-8", newline="\n")
        assembler = asm.Assembler(text, defect, text_base=TEXT_BASE, data_base=DATA_BASE)
        sections, symbols, entry = assembler.assemble()
        elf = out / f"{defect}.elf"
        image.write_elf(elf, sections, symbols, entry)
        log_path = out / f"{defect}.trace"
        with log_path.open("w", encoding="utf-8") as log:
            done = subprocess.run([str(simulator), "--config", str(profile_path), "--trace-commit",
                                   "--inst-limit", "20000000", str(elf)], cwd=out,
                                  stdout=log, stderr=subprocess.STDOUT, timeout=timeout, check=False)
        with log_path.open("rb") as log:
            log.seek(max(0, log_path.stat().st_size - 8192))
            tail = log.read().decode("utf-8", errors="replace")
        verdict, code, detail = compiler_diff.htif_verdict(tail, done.returncode)
        observed = observations(log_path, assembler.symbols, windows, bitmap, bound, defect)
        cases.append({"name": defect, "htif": verdict, "code": code, "detail": detail,
                      "elf_sha256": receipts.digest(elf), "source_sha256": receipts.digest(emitted),
                      "trace_sha256": receipts.digest(log_path), "observations": observed})
        if verdict != "pass":
            break
    unchanged = (inputs == receipts.inputs(root, *INPUTS) and model == receipts.inputs(root, "model") and
                 external == {"ccomp": receipts.digest(ccomp), "config": receipts.digest(config),
                              "simulator": receipts.digest(simulator), "model_receipt": receipts.digest(build_receipt)})
    report = {"status": "complete", "milestone_acceptance": "open", "sources": inputs,
              "external": external, "model_sources": model, "bound": bound,
              "reaction_bound": reaction, "cases": cases,
              "kernel": compiler_diff._compiled_json(kernel), "supervisor": compiler_diff._compiled_json(supervisor),
              "inputs_unchanged": unchanged, "ok": unchanged and len(cases) == 9 and
              all(case["htif"] == "pass" and case["observations"]["ok"] for case in cases),
              "limits": ["explicit reset initialization, not firmware or boot",
                         "three service lifecycle states; service bodies not executed",
                         "one64-byte owned span; no copy ring teardown claim",
                         "logical instruction clock; no physical WCET claim",
                         "remaining finite decision controls are separately bound target receipts"]}
    receipts.write(out / "report.json", report)
    return report
