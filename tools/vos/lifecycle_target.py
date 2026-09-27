# SPDX-License-Identifier: Apache-2.0
"""Finite contained supervisor and trusted timer-consumer component experiment.

Reset roots explicitly initialize this composition. It is not firmware, a boot
roster, or execution of the three service bodies. Timing uses a declared one-step
logical clock, source-level loop bounds and a fixed padded release. Physical
WCET and the copy service's separately owned allocation remain separate inputs.
"""

import json
import re
import subprocess
from pathlib import Path

from vos import asm, boot_handoff, image, jsonc, kernel_effects, kernel_restore
from vos import kernel_target, kernelrun, receipts, trace
from vos.cli import compiler_diff

TEXT_BASE = 0x80200000
DATA_BASE = 0x80008000
SLOT = 200000
STACK = 16384
INPUTS = ("supervisor", "kernel", "tools/vos/lifecycle_target.py",
          "tools/vos/asm.py", "tools/vos/dialect.py", "tools/vos/image.py",
          "tools/vos/kernel_effects.py", "tools/vos/kernel_restore.py")


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
           dispatch_handler: str = "") -> str:
    """Compose original compiled units with explicit authority and timer adapters.

    Offline service fragments own their labels and declared extents. The default
    dispatch hook runs no service body. The owned span's size must also be passed
    to the C compiler as VOS_JOIN_OWNED_BYTES and included in the timing account.
    """
    if defect not in {"none", "stale", "incomplete", "ack-write", "asr"}:
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
                       (13, "old_roots"), (14, "old_masks"), (17, "lifecycle_owned_span")):
        lines += _address(reg, label)
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
    # An abandoned trap/fresh-entry image and MEPCC cannot retain the old PCC.
    for label in ("saved_clear", "restore_context"):
        lines += _address(20, label)
        lines += ["    li x6, 33", f"lifecycle_retire_{label}:", "    sc cnull, 0(c20)",
                  "    cincoffsetimm c20, c20, 8", "    addi x6, x6, -1",
                  f"    bnez x6, lifecycle_retire_{label}"]
    lines += ["lifecycle_retire_mepcc:", "    cspecialrw cnull, mepcc, cnull", retire_extra]
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
    lines += ["    lc c20, 88(c31)", "    sc c20, 256(c19)", "    li x6, 2",
              "    ld x5, 40(c31)", "    li x8, 1", "    bne x5, x8, lifecycle_policy_set",
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
    lines += ["    cincoffsetimm c2, c2, -16", "    sc c12, 0(c2)", "    sd x0, 0(c12)",
              "    call s_vos_join_react", "    lc c12, 0(c2)", "    cincoffsetimm c2, c2, 16",
              "    li x5, -1", "    beq x10, x5, supervisor_failed",
              "    beqz x10, supervisor_poll_return"]
    if defect == "stale":
        lines += ["    ld x5, 16(c12)", "    addi x5, x5, -1", "    sd x5, 16(c12)"]
    lines += ["supervisor_publish:", "    fence rw, rw", "    sd x10, 0(c12)",
              "supervisor_poll_return:", "    wfi", "    j supervisor_poll_return",
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
    return counts


def longest_path(counts: dict[str, int], owned_bytes: int = 64,
                 max_boundary_steps: int = 2097152) -> dict[str, object]:
    """Conservative source-bound whole-function charges for this finite instance.

    Sequential loops charge their sum plus one; each whole emitted body is paid
    that many times. Callees are charged separately at maximum call counts. The
    three service units own one64-byte span, no extra owned cap slots, and two32
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
    clear_unit = cost("effect_clear_unit", 1 + 64 + owned_bytes + 2) + 5 * clear_caps
    request = cost("join_kernel_request_current")
    prepare = cost("vos_kernel_lifecycle_prepare", 1 + 26 + 16 + 3 + 3) + 65 * word
    prepare += 6 * request + cost("vos_kernel_acquire") + cost("vos_kernel_retirement_mask")
    prepare += cost("effect_mask", 4) + cost("join_kernel_backoff")
    retirement = cost("vos_kernel_lifecycle_retire_finish") + cost("vos_kernel_publication")
    retirement += cost("vos_kernel_retire", 4) + cost("effect_mask", 4) + 3 * clear_unit
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
            "retirement": retirement, "start": start, "acknowledge": ack,
            "assembly_and_cleanup": assembly, "longest_path_steps": total,
            "padded_boundary_steps": padded, "owned_bytes": owned_bytes,
            "clock": "one executor step per tick; not physical WCET"}


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
    for defect in ("none", "stale", "incomplete", "ack-write", "asr"):
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
        raw = log_path.read_text(encoding="utf-8")
        verdict, code, detail = compiler_diff.htif_verdict(raw, done.returncode)
        cases.append({"name": defect, "htif": verdict, "code": code, "detail": detail,
                      "elf_sha256": receipts.digest(elf), "source_sha256": receipts.digest(emitted),
                      "trace_sha256": receipts.digest(log_path)})
        if verdict != "pass":
            break
    unchanged = inputs == receipts.inputs(root, *INPUTS) and model == receipts.inputs(root, "model")
    report = {"status": "complete", "milestone_acceptance": "open", "sources": inputs,
              "external": external, "model_sources": model, "bound": bound, "cases": cases,
              "kernel": compiler_diff._compiled_json(kernel), "supervisor": compiler_diff._compiled_json(supervisor),
              "inputs_unchanged": unchanged, "ok": unchanged and len(cases) == 5 and
              all(case["htif"] == "pass" for case in cases),
              "limits": ["explicit reset initialization, not firmware or boot",
                         "three service lifecycle states; service bodies not executed",
                         "one64-byte owned span; no copy ring teardown claim",
                         "logical instruction clock; no physical WCET claim"]}
    receipts.write(out / "report.json", report)
    return report
