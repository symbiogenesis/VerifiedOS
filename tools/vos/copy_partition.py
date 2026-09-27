# SPDX-License-Identifier: Apache-2.0
"""Confined copy activation reset in one persistent, exclusively owned allocation.

The ring is never freed, reallocated or claimed covered by a revocation bitmap.
Only the copy compartment and trusted kernel minting authority hold it. Its
tail contains its actual stack. This component has no exported client endpoint,
borrowed continuation, protected call frame or capability-bearing output.
The source and disclosed destination belong to the kernel/client and are outside
the copy-private reset span; their grants carry no capability-store permission.
"""

import json
from collections.abc import Iterable
from pathlib import Path

from vos import (
    asm,
    copy_notification,
    copy_service,
    copy_target,
    image,
    kernel_effects,
    kernel_restore,
    kernelrun,
    receipts,
    trace,
)
from vos.boot_target import compiler_inputs
from vos.cli import compiler_diff as cd

PREFIX = "vos_copy_partition"
OWNED_BYTES = copy_target.RING_BYTES
STACK_BYTES = OWNED_BYTES // 4
STACK_OFFSET = OWNED_BYTES - STACK_BYTES
CODE_BYTES = 65536
PRIVATE_BYTES = 4096
FRESH = 512
PHASE = 1024
OWNED = 1032
STACK = 1040
SOURCE = 1048
DESTINATION = 1056
SEND = 1064
PENDING = 1072
CODE = 1080
TOHOST = 1088
INPUTS = (*copy_notification.INPUTS, "tools/vos/copy_partition.py",
          "tools/vos/kernel_effects.py", "tools/vos/kernel_restore.py",
          "tools/vos/kernelrun.py", "tools/vos/trace.py")
LIMITS = ("Persistent exclusively owned copy allocation and private activation reset; "
          "no public client endpoint, ring bitmap coverage, address reuse, protected-call "
          "composition, scheduler fixed-release bound or complete boot acceptance.")


def layout() -> dict[str, int]:
    return {"owned_bytes": OWNED_BYTES, "stack_offset": STACK_OFFSET,
            "stack_bytes": STACK_BYTES, "code_bytes": CODE_BYTES,
            "private_bytes": PRIVATE_BYTES, "saved_slots": 33, "fresh_slots": 33}


def clear_span(prefix: str = PREFIX, base: int = 20) -> str:
    """Clear the exact persistent span through caller-owned cbase.

    The caller supplies a capability with the declared bounds and cap-store
    permission. Clobbers c5/c6/x7, preserves every other register and owns no
    trap state. The embedding boundary owns its bounded scheduling cost.
    """
    if not prefix.isidentifier() or base < 8 or base > 30:
        raise ValueError("copy clearing needs a unique label and non-scratch capability")
    return (f"{prefix}_clear_begin:\n    cmove c6, c{base}\n"
            f"    li x7, {OWNED_BYTES // 8}\n{prefix}_clear_word:\n"
            "    sc cnull, 0(c6)\n    cincoffsetimm c6, c6, 8\n"
            f"    addi x7, x7, -1\n    bnez x7, {prefix}_clear_word\n"
            f"{prefix}_clear_end:\n")


def entry(root: Path) -> str:
    """Actual non-ASR payload/notification entry; no kernel trap ownership.

    Inputs: c2 exact tail stack at top; c10 exact private span (data RW), x11
    nonzero 32-bit generation; c12 source RO, c13 destination data RW, c14
    SETEIPNUM data RW, c15 pending RO. c1/c4 are null. It never returns: the
    completed reaction faults at a named point for this bounded experiment.
    The source/destination extents are eight bytes, with no capability-store
    permission. Every cached input capability is on the owned tail stack.
    """
    copy_notification.layout(root)
    p = PREFIX
    lines = [f"{p}_entry:", "    cgettag x5, c1", f"    bnez x5, {p}_failed_fault",
             "    cgettag x5, c4", f"    bnez x5, {p}_failed_fault",
             "    cspecialrw c5, pcc, cnull", f"{p}_permission_check:",
             "    cgetperm x6, c5", "    li x7, 0x800", "    and x6, x6, x7",
             f"    bnez x6, {p}_failed_fault", "    cgetlen x6, c5",
             f"    li x7, {CODE_BYTES}", f"    bne x6, x7, {p}_failed_fault",
             "    cgetlen x5, c10", f"    li x6, {OWNED_BYTES}",
             f"    bne x5, x6, {p}_failed_fault", "    cgetlen x5, c2",
             f"    li x6, {STACK_BYTES}", f"    bne x5, x6, {p}_failed_fault",
             "    cgetbase x5, c10", f"    li x6, {STACK_OFFSET}", "    add x5, x5, x6",
             "    cgetbase x6, c2", f"    bne x5, x6, {p}_failed_fault",
             "    cgetbase x5, c10", "    cgetaddr x6, c10",
             f"    bne x5, x6, {p}_failed_fault", f"    li x6, {OWNED_BYTES}",
             "    add x5, x5, x6", "    cgetaddr x6, c2",
             f"    bne x5, x6, {p}_failed_fault", "    cgettag x5, c2",
             f"    beqz x5, {p}_failed_fault", "    cgettag x5, c10",
             f"    beqz x5, {p}_failed_fault"]
    for register, permission in ((2, 0xfe), (10, 6), (12, 3), (13, 7), (14, 7), (15, 3)):
        lines += [f"    cgetperm x5, c{register}", f"    li x6, {permission}",
                  f"    bne x5, x6, {p}_failed_fault"]
        if register >= 12:
            lines += [f"    cgetlen x5, c{register}", "    li x6, 8",
                      f"    bne x5, x6, {p}_failed_fault"]
    lines += [f"{p}_bounds_checked:",
             "    li x5, 0xffffffff", f"    bgtu x11, x5, {p}_failed_fault",
             f"    beqz x11, {p}_failed_fault", "    cincoffsetimm c2, c2, -128",
             "    sc c10, 0(c2)", "    sd x11, 8(c2)", "    sc c12, 16(c2)",
             "    sc c13, 24(c2)", "    sc c14, 32(c2)", "    sc c15, 40(c2)",
             "    call vos_copy_target_layout", f"    beqz x10, {p}_failed_fault",
             "    call vos_copy_target_ring_bytes", f"    li x5, {STACK_OFFSET}",
             f"    bgtu x10, x5, {p}_failed_fault", "    lc c10, 0(c2)",
             "    ld x11, 8(c2)", "    call vos_copy_init_generation",
             f"    beqz x10, {p}_failed_fault", "    lc c10, 0(c2)",
             "    call vos_copy_prepare_sleep", "    li x5, 1",
             f"    bne x10, x5, {p}_failed_fault"]

    def submit(stale: bool) -> None:
        lines.extend(["    lc c10, 0(c2)", "    ld x11, 8(c2)"])
        if stale:
            lines.append("    addi x11, x11, -1")
        lines.extend(["    li x12, 7", "    li x13, 0", "    lc c14, 16(c2)",
                      "    li x15, 1", "    li x16, 1", "    sw x0, 48(c2)",
                      "    cincoffsetimm c17, c2, 48", "    call vos_copy_submit"])
        lines.append(f"    {'bnez' if stale else 'beqz'} x10, {p}_failed_fault")

    submit(True)
    submit(False)
    lines += ["    lc c10, 32(c2)", "    li x11, 1", "    lwu x12, 48(c2)",
              f"{p}_notify:", "    call vos_copy_notify", f"    beqz x10, {p}_failed_fault",
              "    lc c10, 40(c2)", "    li x11, 1", "    call vos_copy_poll",
              "    li x5, 1", f"    bne x10, x5, {p}_failed_fault",
              "    lc c10, 0(c2)", "    lc c11, 24(c2)", "    li x12, 1",
              "    cincoffsetimm c13, c2, 56", "    cincoffsetimm c14, c2, 64",
              "    call vos_copy_take", f"    beqz x10, {p}_failed_fault",
              "    ld x5, 56(c2)", "    li x6, 1", f"    bne x5, x6, {p}_failed_fault",
              "    lwu x5, 64(c2)", "    li x6, 7", f"    bne x5, x6, {p}_failed_fault",
              "    lc c5, 24(c2)", "    lbu x6, 0(c5)", "    li x7, 123",
              f"    bne x6, x7, {p}_failed_fault", "    lc c12, 0(c2)",
              f"    li x5, {OWNED_BYTES - 8}", "    cincoffset c6, c12, x5",
              "    li x5, 0x456789ab", "    sd x5, 0(c6)",
              f"{p}_fault:", "    ld x5, 0(cnull)", f"    j {p}_fault",
              f"{p}_failed_fault:", "    ld x5, 0(cnull)", f"    j {p}_failed_fault"]
    return "\n".join(lines) + "\n"


def source(root: Path, compiled_stream: str, defect: str = "none") -> str:
    """Independent reset wrapper around reusable entry and clear fragments."""
    if defect not in ("none", "tail-not-cleared", "saved-not-cleared", "resident-not-cleared",
                      "asr-entry", "stale-generation"):
        raise ValueError("unknown copy partition control")
    p = PREFIX
    send, pending, _ = copy_notification.layout(root)
    lines = [".text", ".globl _start", "_start:", "    cmove c4, c1",
             f"    li x5, {p}_private", "    csetaddr c31, c4, x5",
             f"    li x5, {PRIVATE_BYTES}", "    csetbounds c31, c31, x5",
             "    li x5, 0xfe", "    candperm c31, c31, x5",
             "    cspecialrw cnull, mtdc, c31", f"    la c9, {p}_trap",
             "    cspecialrw cnull, mtcc, c9"]

    def bound(reg: int, address: str, size: int, permission: int) -> None:
        lines.extend([f"    li x5, {address}", f"    csetaddr c{reg}, c4, x5",
                      f"    li x5, {size}", f"    csetbounds c{reg}, c{reg}, x5",
                      f"    li x5, {permission}", f"    candperm c{reg}, c{reg}, x5"])

    for slot, address, extent, permission in (
        (OWNED, f"{p}_owned", OWNED_BYTES, 0xfe),
        (STACK, f"{p}_owned + {STACK_OFFSET}", STACK_BYTES, 0xfe),
        (SOURCE, f"{p}_source", 8, 3), (DESTINATION, f"{p}_destination", 8, 7),
        (SEND, str(send), 8, 7), (PENDING, str(pending), 8, 7)):
        bound(7, address, extent, permission)
        if slot == STACK:
            lines += [f"    li x5, {STACK_BYTES}", "    cincoffset c7, c7, x5"]
        lines.append(f"    sc c7, {slot}(c31)")
    lines += [f"    la c7, {p}_code", f"    li x5, {CODE_BYTES}",
              "    csetbounds c7, c7, x5", f"    li x5, {0xfff if defect == 'asr-entry' else 0x7ff}",
              "    candperm c7, c7, x5", f"    li x5, {p}_entry", "    csetaddr c7, c7, x5",
              f"    sc c7, {CODE}(c31)", "    li x5, 1", f"    sd x5, {PHASE}(c31)",
              f"    j {p}_install", f"{p}_trap:", kernel_effects.emit_save(p)]
    scrub = kernel_effects.emit_scrub(p)
    if defect == "resident-not-cleared":
        scrub = scrub.replace("cclear 0, 0xffff", "cclear 0, 0xefff")
    lines += [scrub, "    li x3, 3", "    cgettag x5, c12", f"    bnez x5, {p}_finish",
              "    cgetaddr x5, c12", f"    bnez x5, {p}_finish", "    li x3, 1",
              "    csrr x5, mcause", "    li x6, 28", f"    bne x5, x6, {p}_finish",
              "    lc c5, 256(c31)", "    cgetaddr x5, c5", f"    li x6, {p}_fault",
              f"    bne x5, x6, {p}_finish", f"    lc c20, {OWNED}(c31)"]
    clear = clear_span()
    if defect == "tail-not-cleared":
        clear = clear.replace(f"li x7, {OWNED_BYTES // 8}", f"li x7, {OWNED_BYTES // 8 - 1}")
    lines += [clear, "    li x3, 2", "    cmove c6, c20", f"    li x7, {OWNED_BYTES // 8}",
              f"{p}_verify_owned:", "    ld x5, 0(c6)", f"    bnez x5, {p}_finish",
              "    lc c5, 0(c6)", "    cgettag x5, c5", f"    bnez x5, {p}_finish",
              "    cincoffsetimm c6, c6, 8", "    addi x7, x7, -1",
              f"    bnez x7, {p}_verify_owned", f"{p}_saved_clear_begin:"]
    saved = [*range(0, 264, 8), *range(FRESH, FRESH + 264, 8)]
    lines += [f"    sc cnull, {offset}(c31)" for offset in saved
              if not (defect == "saved-not-cleared" and offset == 96)]
    lines += [f"{p}_saved_clear_end:", "    li x3, 4"]
    for offset in saved:
        lines += [f"    ld x5, {offset}(c31)", f"    bnez x5, {p}_finish",
                  f"    lc c5, {offset}(c31)", "    cgettag x5, c5",
                  f"    bnez x5, {p}_finish"]
    lines += [f"    ld x5, {PHASE}(c31)", "    li x6, 2", f"    beq x5, x6, {p}_success",
              "    li x5, 2", f"    sd x5, {PHASE}(c31)", f"{p}_install:"]
    for offset in range(FRESH, FRESH + 264, 8):
        lines.append(f"    sc cnull, {offset}(c31)")
    for register, slot in ((2, STACK), (10, OWNED), (12, SOURCE), (13, DESTINATION),
                            (14, SEND), (15, PENDING)):
        lines.append(f"    lc c7, {slot}(c31)")
        if register == 10:
            lines += ["    li x5, 6", "    candperm c7, c7, x5"]
        if register == 15:
            lines += ["    sd x0, 0(c7)", "    li x5, 3", "    candperm c7, c7, x5"]
        if register == 13:
            lines.append("    sd x0, 0(c7)")
        lines.append(f"    sc c7, {FRESH + register * 8}(c31)")
    lines += [f"    ld x7, {PHASE}(c31)", f"    sd x7, {FRESH + 88}(c31)",
              f"    lc c7, {CODE}(c31)", f"    sc c7, {FRESH + 256}(c31)",
              f"    cincoffsetimm c31, c31, {FRESH}", "    cclear 0, 0xffff", "    cclear 1, 0x7fff",
              kernel_restore.emit().replace("vos_restore", p + "_restore"),
              f"{p}_success:", "    li x3, 0", f"{p}_finish:", "    slli x5, x3, 1",
              "    ori x5, x5, 1", f"    sd x5, {TOHOST}(c31)", f"{p}_halt:", f"    j {p}_halt",
              f"    .balign {CODE_BYTES}", f"{p}_code:", cd.normalize(compiled_stream)]
    atomic = copy_target.adapter(root)
    if defect == "stale-generation":
        atomic = atomic.replace("vos_copy_init_generation:\n", "vos_copy_init_generation:\n    li x11, 1\n")
    lines += [atomic, copy_notification.adapter(root), entry(root), f"{p}_code_end:",
              ".data", f"    .balign {PRIVATE_BYTES}", f"{p}_private:", f"    .space {TOHOST}",
              "tohost:", "    .dword 0", f"    .space {PRIVATE_BYTES - TOHOST - 8}",
              f"    .balign {OWNED_BYTES}", f"{p}_owned:", f"    .space {OWNED_BYTES}",
              f"{p}_source:", "    .dword 123", f"{p}_destination:", "    .dword 0"]
    return "\n".join(lines) + "\n"


def observations(lines: Iterable[str], symbols: dict[str, int], send: int) -> dict[str, bool]:
    """Read actual publication, register, fault and whole-span clear events."""
    p = PREFIX
    pc = 0
    registers = dict.fromkeys(range(32), (0, 0))
    entries = []
    faults = []
    scrubs = []
    permissions = []
    notifications = payloads = checked_bounds = 0
    clear: set[int] | None = None
    saved: set[int] | None = None
    clears, saves = [], []
    for line in lines:
        for normalized in trace.normalize_commit([line]):
            kind, fields = kernelrun.parse_record(normalized)
            if kind == "I":
                pc = fields[0]
                if pc == symbols[p + "_entry"]:
                    entries.append((registers[11], registers[1], registers[4]))
                if pc == symbols[p + "_bounds_checked"]:
                    checked_bounds += 1
                if pc == symbols[p + "_scrub_end"]:
                    scrubs.append(all(registers[i] == (0, 0) for i in range(1, 31)))
                if pc == symbols[p + "_clear_begin"]:
                    clear = set()
                if pc == symbols[p + "_clear_end"] and clear is not None:
                    clears.append(clear)
                    clear = None
                if pc == symbols[p + "_saved_clear_begin"]:
                    saved = set()
                if pc == symbols[p + "_saved_clear_end"] and saved is not None:
                    saves.append(saved)
                    saved = None
            elif kind == "X":
                registers[fields[0]] = (fields[1], fields[2])
                if pc == symbols[p + "_permission_check"] and fields[0] == 6:
                    permissions.append(fields[2] & 0x800 == 0)
            elif kind == "T":
                faults.append((pc, fields))
            elif kind == "W":
                address, width, tag, value = fields
                if address == send and width == 8 and value == 1:
                    notifications += 1
                if address == symbols[p + "_destination"] and width == 1 and value == 123:
                    payloads += 1
                if width == 8 and tag == 0 and value == 0:
                    if clear is not None:
                        clear.add(address)
                    if saved is not None:
                        saved.add(address)
    expected_clear = set(range(symbols[p + "_owned"], symbols[p + "_owned"] + OWNED_BYTES, 8))
    expected_save = {symbols[p + "_private"] + offset for offset in
                     (*range(0, 264, 8), *range(FRESH, FRESH + 264, 8))}
    return {"two_fresh_entries": entries == [((0, 1), (0, 0), (0, 0)), ((0, 2), (0, 0), (0, 0))],
            "non_asr_pcc": permissions == [True, True],
            "actual_bounds_and_rights_checked": checked_bounds == 2,
            "actual_faults_at_completed_reaction": faults == [(symbols[p + "_fault"], (0, 28))] * 2,
            "resident_words_and_tags_cleared": scrubs == [True, True],
            "whole_owned_span_cleared_twice": clears == [expected_clear, expected_clear],
            "saved_words_and_tags_cleared_twice": saves == [expected_save, expected_save],
            "actual_payload_and_notification_twice": notifications == 2 and payloads == 2}


def run(root: Path, out: Path, ccomp: Path, arguments: list[str], simulator: Path,
        build_receipt: Path, timeout: int = 180) -> dict[str, object]:
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text('{"ok":false,"verdict":"incomplete"}\n', encoding="utf-8")
    sources = receipts.inputs(root, *INPUTS)
    model = receipts.inputs(root, "model")
    compiler_sha, simulator_sha = receipts.digest(ccomp), receipts.digest(simulator)
    private = compiler_inputs(arguments)
    build_sha = receipts.digest(build_receipt)
    kernel_restore.require_build(json.loads(build_receipt.read_text(encoding="utf-8")), simulator_sha, model)
    (out / "copy_service_config.h").write_text(
        copy_service.configuration_header(copy_service.configuration(root)), encoding="utf-8")
    compiled = cd.compile_c([str(ccomp), *arguments, "-fverifiedos-typed", f"-I{out}",
                            f"-I{root / 'copy-service/include'}"],
                           root / "copy-service/test/target_unit.c", out / "compiler", timeout)
    if compiled.exit_code or compiled.stream is None:
        raise ValueError(f"copy partition typed compilation failed: {compiled.said}")
    results = {}
    expected = {"none": 0, "tail-not-cleared": 2, "saved-not-cleared": 4,
                "resident-not-cleared": 3, "asr-entry": 1, "stale-generation": 1}
    send, _, _ = copy_notification.layout(root)
    for defect, code in expected.items():
        emitted = source(root, compiled.stream, defect)
        (out / f"{defect}.s").write_text(emitted, encoding="utf-8")
        assembler = asm.Assembler(emitted, defect, data_base=0x80200000)
        sections, symbols, start = assembler.assemble()
        if assembler.symbols[PREFIX + "_code_end"] - assembler.symbols[PREFIX + "_code"] > CODE_BYTES:
            raise ValueError("copy compartment exceeds its declared PCC extent")
        elf = out / f"{defect}.elf"
        image.write_elf(elf, sections, symbols, start)
        ran = copy_target.execute(simulator, root / "model/config/verifiedos.json", elf, timeout)
        verdict = "pass" if defect == "none" else "fail"
        if ran["verdict"] != verdict or ran["code"] != code:
            raise ValueError(f"{defect}: expected HTIF {code}, got {ran['detail']}")
        with elf.with_suffix(".log").open(encoding="utf-8") as log:
            facts = observations(log, assembler.symbols, send)
        if defect == "none" and not all(facts.values()):
            raise ValueError(f"copy partition trace obligations failed: {facts}")
        results[defect] = {"run": ran, "observations": facts, "image_sha256": receipts.digest(elf),
                           "classification": "positive" if defect == "none" else "killed"}
    if (sources != receipts.inputs(root, *INPUTS) or model != receipts.inputs(root, "model")
            or compiler_sha != receipts.digest(ccomp) or simulator_sha != receipts.digest(simulator)
            or private != compiler_inputs(arguments) or build_sha != receipts.digest(build_receipt)):
        raise ValueError("copy partition inputs changed during execution")
    report: dict[str, object] = {"schema": 1, "ok": True, "verdict": "pass", "limits": LIMITS,
        "layout": layout(), "sources": sources, "model_sources": model,
        "compiler_sha256": compiler_sha, "compiler_inputs": private,
        "simulator_sha256": simulator_sha, "model_build_sha256": build_sha,
        "preprocessed_sha256": compiled.preprocessed.sha256, "results": results}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
