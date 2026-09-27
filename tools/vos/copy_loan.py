# SPDX-License-Identifier: Apache-2.0
"""Trusted grant-redeem and complete fixed-holder cleanup for a copy activation.

These helpers are kernel internals. The existing grant-redeem entry must supply
protected state, unseal/bitmap authority and composition-checked descriptors.
They do not create an entry opcode or prove arbitrary borrowers cannot capture.

The fixed holder predicate includes the whole borrower stack, not just declared
spill offsets: copy-service's atomic_target.s keeps the ring at csp+16 in its
96-byte submit/batch and 48-byte take frames, and typed C can add nested spills.
No ring-pointer result or capability store outside the declared holder spans is
admitted. All other borrower write destinations must carry byte-only authority.
Establishing that predicate for a particular borrower binary belongs to its
composition/admission owner; these helpers neither infer it from C nor accept an
integer generation in place of the real sealed slot and current-bit check.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from vos import asm, dialect, image, jsonc, kernel_restore, kernelrun, receipts, trace
from vos.cli import compiler_diff as cd


@dataclass(frozen=True)
class Holder:
    """One complete allocation, addressed through its protected descriptor slot."""

    label: str
    size: int

    def check(self) -> None:
        if not self.label.isidentifier() or not 128 <= self.size <= 65536:
            raise ValueError("holder requires a label and a bounded complete allocation")
        if self.size & (self.size - 1):
            raise ValueError("holder extent must be an exactly representable power of two")


def _check_name(name: str) -> None:
    if not name.isidentifier():
        raise ValueError("invalid assembly label")


def _checked_root(register: int, base: str, size: int, fail: str) -> list[str]:
    return [f"    cgettag x5, c{register}", f"    beqz x5, {fail}",
            f"    cgetsealed x5, c{register}", f"    bnez x5, {fail}",
            f"    cgetbase x5, c{register}", f"    li x6, {base}",
            f"    bne x5, x6, {fail}", f"    cgetaddr x5, c{register}",
            f"    bne x5, x6, {fail}", f"    cgetlen x5, c{register}",
            f"    li x6, {size}", f"    bne x5, x6, {fail}"]


def emit_redeem(*, slot_base: str, ring_base: str, bitmap_address: int = 0x2200000,
                otype: int = 1, ring_bytes: int = 524288,
                name: str = "vos_copy_loan_redeem") -> str:
    """Validate an actual slot and return its local byte-RW loan in c10.

    c10 effects; c11 private loan state; c12 sealed handle; c13 unseal root;
    c14 exact 8-byte bitmap-word authority. slot_base is the covered aligned
    512-byte block belonging to that word. The caller never supplies a bit index.
    Returns x11=1 on success, x11=0/c10=null on refusal. csp/cra are preserved;
    every other non-result register and every helper spill is cleared.
    """
    for label in (slot_base, ring_base, name):
        _check_name(label)
    if not 0 <= otype < 13 or ring_bytes != 524288 or bitmap_address % 8:
        raise ValueError("unsupported grant type, full ring extent, or bitmap word")
    fail, done = name + "_fail", name + "_done"
    lines = [f"{name}:", "    cmove c31, c2", "    cincoffsetimm c2, c2, -64",
             "    sc c31, 0(c2)", "    sc c1, 8(c2)", "    sc c10, 16(c2)",
             "    sc c11, 24(c2)", "    sc cnull, 32(c2)",
             "    cgettag x5, c12", f"    beqz x5, {fail}",
             "    cgettype x5, c12", f"    li x6, {otype}", f"    bne x5, x6, {fail}",
             "    cunseal c12, c12, c13", "    cgettag x5, c12", f"    beqz x5, {fail}",
             "    cgetlen x5, c12", "    li x6, 8", f"    bne x5, x6, {fail}",
             "    cgetbase x7, c12", "    cgetaddr x5, c12", f"    bne x5, x7, {fail}",
             f"    li x6, {slot_base}", f"    bltu x7, x6, {fail}",
             "    sub x7, x7, x6", "    li x6, 512", f"    bgeu x7, x6, {fail}",
             "    andi x5, x7, 7", f"    bnez x5, {fail}",
             "    srli x7, x7, 3", "    li x17, 1", "    sll x17, x17, x7"]
    lines += _checked_root(14, str(bitmap_address), 8, fail)
    lines += ["    ld x5, 0(c14)", "    and x5, x5, x17", f"    bnez x5, {fail}",
              "    lc c16, 0(c12)"]
    lines += _checked_root(16, ring_base, ring_bytes, fail)
    lines += ["    cgetperm x5, c16", "    andi x5, x5, 6", "    li x6, 6",
              f"    bne x5, x6, {fail}", "    candperm c16, c16, x6",
              "    cgetperm x5, c16", f"    bne x5, x6, {fail}",
              "    sc c16, 32(c2)", "    cmove c12, c17", "    call vos_copy_loan_begin",
              f"    beqz x10, {fail}", "    lc c10, 32(c2)", "    li x11, 1", f"    j {done}",
              f"{fail}:", "    cmove c10, cnull", "    li x11, 0", f"{done}:",
              "    lc c1, 8(c2)", "    lc c31, 0(c2)"]
    lines += [f"    sc cnull, {offset}(c2)" for offset in range(0, 64, 8)]
    lines += ["    cmove c2, c31", "    cclear 0, 0xf3f9", "    cclear 1, 0xffff", "    ret"]
    return "\n".join(lines) + "\n"


def emit_cleanup(holders: tuple[Holder, Holder, Holder], *,
                 name: str = "vos_copy_loan_cleanup", defect: str = "none") -> str:
    """Destroy stack, saved image and protected frames, then close exactly once.

    c10 effects; c11 private loan state; c12 protected 32-byte descriptor carrying
    three exact holder capabilities at 0,8,16. No borrowed register is preserved.
    Caller has reached trusted text and switched to its disjoint private csp.
    The complete old activation ends here: MEPCC is cleared. A caller returning
    through mret must install the successor MEPCC after this helper succeeds.
    Untrusted code cannot reach this routine or its internal C finish directly.
    """
    _check_name(name)
    for holder in holders:
        holder.check()
    if len({holder.label for holder in holders}) != 3:
        raise ValueError("holder allocations must have distinct composition labels")
    if defect not in {"none", "missing-stack", "missing-saved", "missing-frames"}:
        raise ValueError("unknown cleanup control")
    fail, done = name + "_fail", name + "_done"
    lines = [f"{name}:", "    cmove c31, c2", "    cincoffsetimm c2, c2, -64",
             "    sc c31, 0(c2)", "    sc c1, 8(c2)", "    sc c10, 16(c2)",
             "    sc c11, 24(c2)", "    sc c12, 32(c2)"]
    # Preflight every span before clearing anything. Exact bounds exclude aliasing
    # with trusted state; the authenticated layout additionally proves disjointness.
    for index, holder in enumerate(holders):
        lines += [f"    lc c13, {index * 8}(c12)"]
        lines += _checked_root(13, holder.label, holder.size, fail)
        lines += ["    cgetperm x5, c13", "    andi x5, x5, 30", "    li x6, 30",
                  f"    bne x5, x6, {fail}"]
    for index, holder in enumerate(holders):
        loop, check = f"{name}_clear_{index}", f"{name}_check_{index}"
        lines += ["    lc c12, 32(c2)", f"    lc c13, {index * 8}(c12)",
                  f"    li x14, {holder.size // 8}", f"{loop}:"]
        if defect != ("missing-stack", "missing-saved", "missing-frames")[index]:
            lines.append("    sc cnull, 0(c13)")
        lines += ["    cincoffsetimm c13, c13, 8", "    addi x14, x14, -1",
                  f"    bnez x14, {loop}", f"    lc c13, {index * 8}(c12)",
                  f"    li x14, {holder.size // 8}", f"{check}:",
                  "    lc c15, 0(c13)", "    cgettag x5, c15", f"    bnez x5, {fail}",
                  "    ld x5, 0(c13)", f"    bnez x5, {fail}",
                  "    cincoffsetimm c13, c13, 8", "    addi x14, x14, -1",
                  f"    bnez x14, {check}"]
    lines += ["    cmove c5, cnull", "    cspecialrw cnull, mepcc, c5",
              "    lc c10, 16(c2)", "    lc c11, 24(c2)",
              "    cclear 0, 0xf3f9", "    cclear 1, 0xffff",
              "    li x12, 31", "    call vos_copy_loan_finish", f"    j {done}",
              f"{fail}:", "    li x10, 0", f"{done}:", "    lc c1, 8(c2)", "    lc c31, 0(c2)"]
    lines += [f"    sc cnull, {offset}(c2)" for offset in range(0, 64, 8)]
    lines += ["    cmove c2, c31", "    cclear 0, 0xfbf9", "    cclear 1, 0xffff", "    ret"]
    return "\n".join(lines) + "\n"


def experiment(compiled: str, defect: str = "none") -> str:
    """Real local loan, interior-base spill and complete cleanup on one hart.

    The tiny borrower is authored assembly; the outstanding-loan decisions are
    the actual accepted C. This fixture does not claim an arbitrary no-capture
    theorem or the separate supervisor/copy composition's accepted entry path.
    """
    if defect not in {"none", "revoked-resident", "wrong-slot", "missing-stack",
                      "missing-saved", "missing-frames"}:
        raise ValueError("unknown loan target control")
    holders = (Holder("borrower_stack", 8192), Holder("borrower_saved", 512),
               Holder("borrower_frames", 512))
    lines = [".text", ".globl _start", "_start:", "    cmove c8, c2", "    cmove c9, c3",
             "    cmove c4, c1"]

    def ptr(reg: int, label: str, size: int, mask: int | None = None) -> None:
        lines.extend([f"    li x31, {label}", f"    csetaddr c{reg}, c4, x31",
                      f"    li x31, {size}", f"    csetbounds c{reg}, c{reg}, x31"])
        if mask is not None:
            lines.extend([f"    li x31, {mask}", f"    candperm c{reg}, c{reg}, x31"])

    ptr(30, "private", 128, 0xfe)
    lines += ["    cspecialrw cnull, mtdc, c30", "    sc c4, 0(c30)",
              "    sc c8, 8(c30)", "    sc c9, 16(c30)"]
    ptr(2, "kernel_stack", 8192, 0xfe)
    lines += ["    li x31, 8192", "    cincoffset c2, c2, x31", "    sc c2, 24(c30)",
              "    la c5, trap_fail", "    cspecialrw cnull, mtcc, c5"]
    for index, holder in enumerate(holders):
        ptr(5, holder.label, holder.size, 0xfe)
        lines.append(f"    sc c5, {32 + index * 8}(c30)")
    ptr(5, "ring", 524288)
    ptr(6, "grant_slots", 8)
    lines.append("    sc c5, 0(c6)")
    # The actual slot is sealed with the reset-provided mint root. Only its
    # independently protected redeem root is passed to the trusted helper.
    lines += ["    li x31, 1", "    csetaddr c8, c8, x31", "    csetaddr c9, c9, x31"]
    if defect == "wrong-slot":
        ptr(6, "grant_slots", 16)
    lines += ["    cseal c6, c6, c8", "    sc c6, 56(c30)", "    sc c9, 64(c30)"]
    ptr(10, "effects", 16384)
    ptr(11, "loan", 32)
    lines += ["    call vos_copy_loan_target_prepare", "    beqz x10, prepare_fail",
              "    cspecialrw c30, mtdc, cnull", "    lc c4, 0(c30)"]
    ptr(10, "effects", 16384)
    ptr(11, "loan", 32)
    lines += ["    lc c12, 56(c30)", "    lc c13, 64(c30)"]
    ptr(14, "35651584", 8, 7)
    if defect == "revoked-resident":
        lines += ["    li x5, 1", "    sd x5, 0(c14)"]
    lines += ["    call vos_copy_loan_redeem", "    beqz x11, redeem_fail",
              "    cspecialrw c30, mtdc, cnull", "    lc c4, 0(c30)",
              "    lc c5, 40(c30)", "    sc c10, 0(c5)",
              "    lc c5, 48(c30)", "    sc c10, 0(c5)",
              "    lc c2, 32(c30)", "    li x5, 8192", "    cincoffset c2, c2, x5",
              "    la c19, borrower", "    li x5, 128", "    csetbounds c19, c19, x5",
              "    li x5, 0x103", "    candperm c19, c19, x5", "    csealentry c19, c19",
              "    cspecialrw cnull, mepcc, c19", "    cclear 0, 0xfbfb",
              "    cclear 1, 0xfff7", "    cjalr c1, c19, 0", "borrower_return:",
              "    cspecialrw c30, mtdc, cnull", "    lc c2, 24(c30)", "    lc c4, 0(c30)"]
    ptr(10, "effects", 16384)
    ptr(11, "loan", 32)
    lines += ["    cincoffsetimm c12, c30, 32", "    li x5, 32", "    csetbounds c12, c12, x5",
              "    call vos_copy_loan_cleanup", "    beqz x10, cleanup_fail",
              "    cspecialrw c30, mtdc, cnull", "    lc c4, 0(c30)"]
    ptr(10, "effects", 16384)
    ptr(11, "loan", 32)
    lines += ["    call vos_copy_loan_target_closed", "    beqz x10, inconsistent_fail",
              "    li x3, 0", "    j exit", "prepare_fail:", "    li x3, 1", "    j exit"]
    for label, expected, code in (("cleanup_fail", 0, 2), ("redeem_fail", 1, 3)):
        lines += [f"{label}:", "    cspecialrw c30, mtdc, cnull", "    lc c4, 0(c30)"]
        ptr(10, "effects", 16384)
        ptr(11, "loan", 32)
        lines += ["    call vos_copy_loan_target_closed", f"    li x5, {expected}",
                  "    bne x10, x5, inconsistent_fail", f"    li x3, {code}", "    j exit"]
    lines += ["inconsistent_fail:", "    li x3, 5", "    j exit", "trap_fail:", "    li x3, 4", "exit:",
              "    cspecialrw c30, mtdc, cnull", "    lc c4, 0(c30)"]
    ptr(5, "tohost", 8)
    lines += ["    slli x3, x3, 1", "    ori x3, x3, 1", "    sd x3, 0(c5)", "halt:", "    j halt",
              "    .balign 128", "borrower:", "    li x5, 42", "    sb x5, 0(c10)",
              "    sc c10, -8(c2)", "    li x5, 40000", "    cincoffset c5, c10, x5",
              "    li x6, 8", "    csetbounds c5, c5, x6", "    sc c5, -16(c2)",
              "    li x6, 43", "    sb x6, 0(c5)", "    ret", "    .balign 128"]
    lines += [emit_redeem(slot_base="grant_slots", ring_base="ring"),
              emit_cleanup(holders, defect=defect if defect.startswith("missing-") else "none"),
              ".data", ".balign 512", "grant_slots:", "    .space 512", ".balign 128",
              "private:", "    .space 128", ".balign 32", "loan:", "    .space 32",
              ".balign 8", "tohost:", "    .dword 0", ".balign 16384", "effects:", "    .space 16384"]
    for holder in (*holders, Holder("kernel_stack", 8192), Holder("ring", 524288)):
        lines += [f".balign {holder.size}", f"{holder.label}:", f"    .space {holder.size}"]
    return "\n".join(lines) + "\n.text\n" + cd.normalize(compiled)


def observations(records: list[kernelrun.Record], symbols: dict[str, int]) -> dict[str, bool]:
    """Observe the real holder population before the C completion guard runs."""
    registers = dict.fromkeys(range(32), (0, 0))
    cells: dict[int, tuple[int, int]] = {}
    specials: dict[int, tuple[int, int]] = {}
    borrowed: tuple[int, int] | None = None
    interior: tuple[int, int] | None = None
    result = {"borrower_entered": False, "actual_stack_loan_spill": False,
              "actual_interior_base_spill": False, "complete_holders_zero": False,
              "borrowed_words_absent_from_registers": False, "obsolete_mepcc_cleared": False}
    for kind, fields in records:
        if kind == "X":
            registers[fields[0]] = fields[1], fields[2]
        elif kind == "S":
            specials[fields[0]] = fields[1], fields[2]
        elif kind == "W" and fields[1] == 8:
            cells[fields[0]] = fields[2], fields[3]
            if fields[0] == symbols["borrower_stack"] + 8192 - 8:
                result["actual_stack_loan_spill"] |= borrowed is not None and cells[fields[0]] == borrowed
            if fields[0] == symbols["borrower_stack"] + 8192 - 16 and fields[2] == 1:
                interior = cells[fields[0]]
                result["actual_interior_base_spill"] = borrowed is not None and interior != borrowed
        elif kind == "I" and fields[0] == symbols["borrower"]:
            borrowed = registers[10]
            result["borrower_entered"] = borrowed[0] == 1
        elif kind == "I" and fields[0] == symbols["vos_copy_loan_finish"]:
            spans = (("borrower_stack", 8192), ("borrower_saved", 512), ("borrower_frames", 512))
            result["complete_holders_zero"] = all(cells.get(symbols[label] + offset) == (0, 0)
                for label, size in spans for offset in range(0, size, 8))
            result["borrowed_words_absent_from_registers"] = borrowed is not None and interior is not None and all(
                value != borrowed and value != interior for value in registers.values())
            result["obsolete_mepcc_cleared"] = specials.get(dialect.SCRS["mepcc"]) == (0, 0)
    return result


def run(root: Path, ccomp: Path, config: Path, simulator: Path, build_receipt: Path,
        out: Path, timeout: int = 60) -> dict[str, object]:
    """Source-bound native component campaign; no hosted gate substitute."""
    root, ccomp, config, simulator, build_receipt, out = (
        p.resolve() for p in (root, ccomp, config, simulator, build_receipt, out))
    out.mkdir(parents=True, exist_ok=True)
    receipts.write(out / "report.json", {"status": "incomplete", "ok": False})
    inputs = ("kernel/include/vos_copy_loan.h", "kernel/src/copy_loan.c", "kernel/test/copy_loan_target.c",
              "kernel/include/vos_effects.h", "kernel/include/vos_platform.h", "kernel/include/vos_kernel.h",
              "supervisor/include", "tools/vos/copy_loan.py", "tools/vos/asm.py", "tools/vos/image.py",
              "tools/vos/cli/compiler_diff.py", "tools/vos/kernel_restore.py", "tools/vos/kernelrun.py",
              "tools/vos/dialect.py", "tools/vos/jsonc.py", "tools/vos/trace.py", "tools/vos/receipts.py",
              "tools/generated/dialect-table.json", "model")
    sources = receipts.inputs(root, *inputs)
    external = {str(p): receipts.digest(p) for p in (ccomp, config, simulator, build_receipt)}
    kernel_restore.require_build(json.loads(build_receipt.read_text(encoding="utf-8")),
                                 receipts.digest(simulator), receipts.inputs(root, "model"))
    compiled = cd.compile_c([str(ccomp), "-conf", str(config), "-fverifiedos-typed",
                            "-I" + str(root / "kernel/include"),
                            "-I" + str(root / "supervisor/include")],
                           root / "kernel/test/copy_loan_target.c", out / "compiled", timeout)
    if compiled.exit_code or compiled.stream is None:
        raise ValueError(f"loan C compilation failed: {compiled.said}")
    cases: list[dict[str, object]] = []
    for defect in ("none", "revoked-resident", "wrong-slot", "missing-stack", "missing-saved", "missing-frames"):
        text = experiment(compiled.stream, defect)
        (out / f"{defect}.s").write_text(text, encoding="utf-8")
        assembler = asm.Assembler(text, defect, data_base=0x80008000)
        sections, image_symbols, entry = assembler.assemble()
        symbols = assembler.symbols
        if symbols["grant_slots"] % 512:
            raise ValueError("grant block is not aligned to a complete bitmap word")
        profile = jsonc.load(root / "model/config/verifiedos.json")
        if not isinstance(profile, dict) or not isinstance(platform := profile.get("platform"), dict):
            raise TypeError("missing model platform configuration")
        if not isinstance(plane := platform.get("revocation"), dict) or plane.get("interval_size") != 32768:
            raise ValueError("requires the reviewed unchanged 32KiB revocation capacity")
        plane["interval_base"] = symbols["grant_slots"]
        profile_path = out / f"{defect}.json"
        receipts.write(profile_path, profile)
        elf = out / f"{defect}.elf"
        image.write_elf(elf, sections, image_symbols, entry)
        done = subprocess.run([str(simulator), "--config", str(profile_path),
                               "--trace-commit", "--inst-limit", "1000000", str(elf)],
                              cwd=out, capture_output=True, text=True, timeout=timeout, check=False)
        said = done.stdout + done.stderr
        (out / f"{defect}.log").write_text(said, encoding="utf-8")
        verdict, code, detail = cd.htif_verdict(said, done.returncode)
        records = trace.normalize_commit(said.splitlines())
        observed = observations(kernelrun.parse_records(records), symbols)
        expected = 0 if defect == "none" else 2 if defect.startswith("missing-") else 3
        cases.append({"name": defect, "expected_code": expected, "verdict": verdict,
                      "code": code, "detail": detail, "records": len(records),
                      "trace_sha256": trace.digest(records), "observations": observed,
                      "matched": code == expected and bool(records) and (all(observed.values()) if defect == "none" else True),
                      "image_sha256": receipts.digest(elf), "profile_sha256": receipts.digest(profile_path)})
    unchanged = sources == receipts.inputs(root, *inputs) and external == {
        str(p): receipts.digest(p) for p in (ccomp, config, simulator, build_receipt)}
    report = {"status": "complete", "sources": sources, "external": external,
              "preprocessed_sha256": compiled.preprocessed.sha256, "cases": cases,
              "limits": "Actual fixed-shape helper controls, not arbitrary no-capture proof or roster join.",
              "inputs_unchanged": unchanged, "ok": unchanged and all(c["matched"] for c in cases)}
    receipts.write(out / "report.json", report)
    return report
