# SPDX-License-Identifier: Apache-2.0
"""Scalar kernel restore emission and its generated target controls.

The input is a kernel-owned, stable, readable 264-byte save image: 32 capability
slots followed by the successor MEPCC. c31 points at its base on entry. This is
the final restore primitive, not an ordinary C call: no continuation is retained.
The caller has established the context's validity, confinement and revocation
conditions and installed the boundary timer and trap data. Neither this emitter
nor its harness establishes those prerequisites.

Only the C class with an empty partition-nameable CSR roster is supported. The
profile gates all scalar CSRs through PCC's ASR permission, which the successor
must lack. V/M zeroization, pending-state installation and a general CSR roster
remain separate joins. Setup's MEPCC write and dispatch's mstatus write sit
outside the declared register-restore extent and are checked separately.
"""

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from vos import asm, dialect, image, kernelrun, receipts, trace
from vos.cli.compiler_diff import htif_verdict

REGISTER_COUNT = kernelrun.REGISTER_COUNT
SLOT_BYTES = 8  # isa-profile.md: merged registers carry 64 data bits plus a tag.
ENTRY_OFFSET = REGISTER_COUNT * SLOT_BYTES
CONTEXT_BYTES = ENTRY_OFFSET + SLOT_BYTES


def emit(*, core_class: str = "C", csr_roster: tuple[int, ...] = ()) -> str:
    """Emit the scalar primitive; refuse unsupported architectural obligations."""
    if core_class != "C" or csr_roster:
        raise ValueError("scalar restore requires C class and an empty nameable CSR roster")
    lines = ["vos_restore_setup:", f"    lc c30, {ENTRY_OFFSET}(c31)",
             "    cspecialrw cnull, mepcc, c30", "vos_restore_begin:"]
    # c31 remains the image pointer until its own final load. No scratch register
    # is touched after its image slot has been installed.
    lines += [f"    lc c{r}, {r * SLOT_BYTES}(c31)" for r in range(1, REGISTER_COUNT)]
    lines += ["    fence.t", "vos_restore_end:", "vos_restore_dispatch:",
              "    mret", "vos_restore_dispatch_end:"]
    return "\n".join(lines) + "\n"


@dataclass(frozen=True)
class Control:
    name: str
    seed: int
    defect: str = "none"


def controls() -> tuple[Control, ...]:
    """Independent saved values/tag patterns, then executable restore defects."""
    return (*(Control(f"pattern-{seed}", seed) for seed in range(4)),
        Control("omitted-register", 0, "omit"),
        Control("lost-tag", 0, "tag"),
        Control("duplicate-register", 0, "duplicate"),
        Control("early-base-restore", 0, "base"),
        Control("missing-fence", 0, "fence"),
        Control("missing-dispatch", 0, "dispatch"),
    )


def control_source(control: Control) -> str:
    """The test builds the saved image and compares a captured image in-program.

    All authority originates at reset in this harness. That is intentionally
    separate from firmware handoff. Every third slot is tagged; c4 retains the
    store root and c31 the capture extent. sc captures all 31 restored registers
    before a scratch write, including c31 itself. The HTIF check compares raw
    words and tags against the saved image, without decoding capability bounds.
    """
    lines = [".text", ".globl _start", "_start:", "    cmove c4, c1",
             "    la c9, control_trap", "    cspecialrw cnull, mtcc, c9",
             "    cspecialrw cnull, mtdc, c4", "    li x5, context",
             "    csetaddr c31, c4, x5", f"    li x5, {CONTEXT_BYTES}",
             "    csetbounds c31, c31, x5", "    sc cnull, 0(c31)"]
    for r in range(1, REGISTER_COUNT):
        if r == 4:
            lines.append("    cmove c6, c4")
        elif r == 31:
            lines += ["    li x5, captured", "    csetaddr c6, c4, x5"]
        elif (r + control.seed) % 3 == 0:
            lines += [f"    li x5, context + {r * SLOT_BYTES}",
                      "    csetaddr c6, c4, x5"]
        else:
            lines += [f"    li x6, {(control.seed + 1) * 0x10000 + r * 17}"]
        lines.append(f"    sc c6, {r * SLOT_BYTES}(c31)")
    lines += ["    la c6, successor", "    li x5, 0x7ff",
              "    candperm c6, c6, x5", f"    sc c6, {ENTRY_OFFSET}(c31)",
              # Clear old values so every omitted register has an in-program
              # counterexample. Only the image pointer survives.
              "    cclear 0, 0xffff", "    cclear 1, 0x7fff"]
    primitive = emit()
    if control.defect == "omit":
        primitive = primitive.replace("    lc c17, 136(c31)\n", "")
    elif control.defect == "tag":
        primitive = primitive.replace("    lc c3, 24(c31)", "    ld x3, 24(c31)")
    elif control.defect == "duplicate":
        primitive = primitive.replace("    lc c17, 136(c31)\n",
                                      "    lc c17, 136(c31)\n    lc c17, 136(c31)\n")
    elif control.defect == "base":
        primitive = primitive.replace("    lc c31, 248(c31)\n", "")
        primitive = primitive.replace("vos_restore_begin:\n",
                                      "vos_restore_begin:\n    lc c31, 248(c31)\n")
    elif control.defect == "fence":
        primitive = primitive.replace("    fence.t\n", "")
    elif control.defect == "dispatch":
        primitive = primitive.replace("    mret\n", "    j successor\n")
    lines += [primitive, "successor:"]
    lines += [f"    sc c{r}, {r * SLOT_BYTES}(c31)" for r in range(1, REGISTER_COUNT)]
    lines += ["    li x3, 32", "    cspecialrw c7, pcc, cnull", "    cgetperm x5, c7",
              "    li x6, 0x800", "    and x5, x5, x6", "    bnez x5, control_fail",
              "    li x5, context", "    csetaddr c8, c4, x5", "    li x3, 1"]
    for r in range(1, REGISTER_COUNT):
        lines += [f"    li x3, {r}", f"    ld x5, {r * SLOT_BYTES}(c8)",
                  f"    ld x6, {r * SLOT_BYTES}(c31)", "    bne x5, x6, control_fail",
                  f"    lc c5, {r * SLOT_BYTES}(c8)",
                  f"    lc c6, {r * SLOT_BYTES}(c31)", "    cgettag x5, c5",
                  "    cgettag x6, c6", "    bne x5, x6, control_fail"]
    lines += ["    li x3, 0", "control_fail:", "    slli x5, x3, 1",
              "    ori x5, x5, 1", "    li x6, tohost", "    csetaddr c31, c4, x6",
              "    sd x5, 0(c31)", "control_halt:", "    j control_halt",
              "control_trap:", "    cspecialrw c4, mtdc, cnull", "    li x3, 63",
              "    j control_fail", ".data", ".align 3", "tohost:", "    .dword 0",
              ".align 6", "context:", f"    .space {CONTEXT_BYTES}",
              ".align 6", "captured:", f"    .space {ENTRY_OFFSET}"]
    return "\n".join(lines) + "\n"


def instruction_groups(records: list[kernelrun.Record]) -> list[
        tuple[tuple[int, int], list[kernelrun.Record]]]:
    """Keep effects attached to the retirement that produced them."""
    groups: list[tuple[tuple[int, int], list[kernelrun.Record]]] = []
    for kind, fields in records:
        if kind == "I":
            groups.append(((fields[0], fields[1]), []))
        elif groups:
            groups[-1][1].append((kind, fields))
    return groups


def observations(records: list[kernelrun.Record], symbols: dict[str, int]) -> dict[str, bool]:
    """Read actual stored input and ordered restore writes, with independent cuts."""
    restore = kernelrun.Extent(symbols["vos_restore_begin"], symbols["vos_restore_end"])
    setup = kernelrun.Extent(symbols["vos_restore_setup"], restore.base)
    dispatch = kernelrun.Extent(symbols["vos_restore_dispatch"],
                                symbols["vos_restore_dispatch_end"])
    saved: dict[int, tuple[int, bool]] = {0: (0, False)}
    saved_entry: tuple[int, int] | None = None
    for kind, fields in records:
        if kind == "I" and fields[0] == setup.base:
            break
        if kind == "W" and fields[1] == SLOT_BYTES:
            offset = fields[0] - symbols["context"]
            if 0 <= offset < ENTRY_OFFSET and offset % SLOT_BYTES == 0:
                saved[offset // SLOT_BYTES] = (fields[3], bool(fields[2]))
            if offset == ENTRY_OFFSET:
                saved_entry = (fields[2], fields[3])
    bursts = kernelrun.restore_bursts(records, restore)
    burst = bursts[0] if len(bursts) == 1 else []
    complete = set(saved) == set(range(REGISTER_COUNT))
    succ = kernelrun.Image(tuple(saved.get(r, (0, False)) for r in range(REGISTER_COUNT)), {})
    order = [fields[0] for kind, fields in burst if kind == "X"]
    setup_bursts = kernelrun.restore_bursts(records, setup)
    dispatch_bursts = kernelrun.restore_bursts(records, dispatch)
    mepcc = [fields for b in setup_bursts for kind, fields in b
             if kind == "S" and fields[0] == dialect.SCRS["mepcc"]]
    dispatch_csrs = [fields[0] for b in dispatch_bursts for kind, fields in b if kind == "C"]
    pcs = [(fields[0], fields[1]) for kind, fields in records if kind == "I"]
    groups = instruction_groups(records)
    starts = [i for i, (instruction, _) in enumerate(groups) if instruction[0] == setup.base]
    start = starts[0] if len(starts) == 1 else len(groups)
    canonical = asm.Assembler(".text\n" + emit(), "restore-contract").assemble()[0][0].data
    expected_path = [(setup.base + offset, int.from_bytes(canonical[offset:offset + 4], "little"))
                     for offset in range(0, len(canonical), 4)]
    window = groups[start:start + len(expected_path) + 1]
    # Membership in a text extent cannot establish chronology. Require the
    # complete contiguous instruction path, once, through the successor entry.
    path = (len(window) == len(expected_path) + 1
            and [instruction for instruction, _ in window[:-1]] == expected_path
            and window[-1][0][0] == symbols["successor"]
            and sum(setup.base <= instruction[0] <= symbols["successor"]
                    for instruction, _ in groups) == len(window))
    setup_window = groups[start:start + 3]
    setup_before = (len(setup_window) == 3
                    and [instruction for instruction, _ in setup_window[:2]] == expected_path[:2]
                    and setup_window[2][0][0] == restore.base
                    and not any(restore.within(instruction[0])
                                for instruction, _ in groups[:start]))
    setup_effects = [[(kind, fields) for kind, fields in effects if kind in ("X", "S", "C", "T")]
                     for _, effects in setup_window[:2]]
    setup_aligned = (saved_entry is not None and setup_effects == [
        [("X", (30, *saved_entry))], [("S", (dialect.SCRS["mepcc"], *saved_entry))]])
    restore_groups = [(instruction, effects) for instruction, effects in groups
                      if restore.within(instruction[0])]
    # Each load must write its own register, under that exact instruction; a
    # shifted X record cannot borrow an adjacent instruction's register value.
    aligned = (complete and len(restore_groups) == REGISTER_COUNT
               and all(instruction == expected_path[r + 1]
                       and [(kind, fields) for kind, fields in effects
                            if kind in ("X", "S", "C", "T")]
                       == [("X", (r, int(saved[r][1]), saved[r][0]))]
                       for r, (instruction, effects) in enumerate(restore_groups[:-1], start=1))
               and not any(kind in ("X", "S", "C", "T")
                           for kind, _ in restore_groups[-1][1]))
    fence = asm.Assembler(".text\n fence.t\n", "fence").assemble()[0][0].data
    fence_word = int.from_bytes(fence, "little")
    return {
        "saved_image_observed": complete,
        "one_restore_burst": len(bursts) == 1,
        "register_values_and_tags": complete and kernelrun.switch_is_total((), succ, burst),
        "exactly_once": kernelrun.burst_writes_exactly_once((), burst),
        "ordered_registers_base_last": order == list(range(1, REGISTER_COUNT)),
        "exact_instruction_sequence": path,
        "register_effects_aligned": aligned,
        "fence_at_restore_end": (bool(restore_groups)
                                  and restore_groups[-1][0] == (restore.top - 4, fence_word)),
        "mepcc_installed_before_restore": (saved_entry is not None and saved_entry[0] == 1
                                            and len(mepcc) == 1 and mepcc[0][1:] == saved_entry
                                            and setup_before and setup_aligned),
        "dispatch_mret": (dispatch.base, 0x30200073) in pcs,
        "dispatch_mstatus_outside_restore": dispatch_csrs == [dialect.CSRS["mstatus"]],
        "successor_reached": any(pc == symbols["successor"] for pc, _ in pcs),
    }


class Report(TypedDict):
    scope: str
    milestone_acceptance: str
    cases: list[dict[str, object]]
    simulator: str
    simulator_sha256: str
    profile_sha256: str
    sources: dict[str, str]
    model_sources: dict[str, str]
    build_receipt: str
    build_receipt_sha256: str
    inputs_unchanged: bool
    ok: bool


def require_build(record: object, simulator_digest: str, model_sources: dict[str, str]) -> None:
    """Require a successful build of these model bytes and this simulator.

    This checks the exported model/build join, not availability of the original
    build tree, installed compiler tools or every other build artifact. The
    complete original receipt remains identified in the target report.
    """
    if (not isinstance(record, dict) or record.get("schema") != 1
            or record.get("exit_code") != 0
            or record.get("stages") != {"configure": 0, "build": 0, "ctest": 0}):
        raise ValueError("restore requires a successful complete model build receipt")
    artifacts = record.get("artifacts")
    identity = record.get("identity")
    if (not isinstance(artifacts, dict)
            or artifacts.get("c_emulator/sail_riscv_sim") != simulator_digest):
        raise ValueError("restore simulator differs from the model build receipt")
    inputs = identity.get("inputs") if isinstance(identity, dict) else None
    if (not isinstance(inputs, dict)
            or {k: v for k, v in inputs.items() if k.startswith("model/")} != model_sources):
        raise ValueError("restore model sources differ from the model build receipt")


def run(root: Path, simulator: Path, out: Path, timeout: int, build_receipt: Path) -> Report:
    """Run every generated control, retaining source, ELF and raw trace identities."""
    root, simulator, out, build_receipt = (
        path.resolve() for path in (root, simulator, out, build_receipt))
    out.mkdir(parents=True, exist_ok=True)
    profile = root / "model/config/verifiedos.json"
    input_paths = (
        "tools/vos/kernel_restore.py", "tools/vos/kernelrun.py", "tools/vos/asm.py",
        "tools/vos/image.py", "tools/vos/trace.py", "tools/vos/cli/compiler_diff.py",
        "tools/vos/cli/kernel.py", "tools/vos/dialect.py", "tools/generated/dialect-table.json",
        "docs/implementation/contracts/purecap-abi.md", "docs/hardware/isa-profile.md")
    sources = receipts.inputs(root, *input_paths)
    model_sources = receipts.inputs(root, "model")
    simulator_digest = receipts.digest(simulator)
    profile_digest = receipts.digest(profile)
    build_digest = receipts.digest(build_receipt)
    require_build(json.loads(build_receipt.read_text(encoding="utf-8")),
                  simulator_digest, model_sources)
    rows: list[dict[str, object]] = []
    for control in controls():
        source = control_source(control)
        source_path = out / f"{control.name}.s"
        source_path.write_text(source, encoding="utf-8", newline="\n")
        assembler = asm.Assembler(source, control.name)
        sections, symbol_sections, entry = assembler.assemble()
        elf = out / f"{control.name}.elf"
        image.write_elf(elf, sections, symbol_sections, entry)
        argv = [str(simulator), "--config", str(profile), "--trace-commit",
                "--inst-limit", "20000", str(elf)]
        run_error = ""
        try:
            done = subprocess.run(argv, cwd=out, capture_output=True, text=True,
                                  timeout=timeout, check=False)
            raw = done.stdout + done.stderr
            returncode = done.returncode
        except (OSError, subprocess.TimeoutExpired) as error:
            run_error = str(error)
            raw, returncode = "", 1
        (out / f"{control.name}.trace").write_text(raw, encoding="utf-8", newline="\n")
        normalized = trace.normalize_commit(raw.splitlines())
        observed = observations(kernelrun.parse_records(normalized), assembler.symbols)
        verdict, code, _ = htif_verdict(raw, returncode)
        accepted = verdict == "pass" and all(observed.values())
        expected = control.defect == "none"
        # Defects have independently specified failing observations, not merely
        # an aggregate false which could be an unrelated environment failure.
        decisive = {"omit": "register_values_and_tags", "tag": "register_values_and_tags",
                    "duplicate": "exactly_once", "base": "ordered_registers_base_last",
                    "fence": "fence_at_restore_end", "dispatch": "dispatch_mret"}
        matched = accepted if expected else not observed[decisive[control.defect]]
        if control.defect in ("omit", "tag"):
            matched = matched and verdict == "fail" and code == (17 if control.defect == "omit" else 3)
        if control.defect == "dispatch":
            matched = matched and verdict == "fail" and code == 32
        if control.defect == "base":
            matched = matched and verdict == "fail" and code == 63
        if control.defect in ("duplicate", "fence"):
            matched = matched and verdict == "pass"
        matched = (matched and not run_error and observed["saved_image_observed"]
                   and observed["mepcc_installed_before_restore"])
        rows.append({"name": control.name, "seed": control.seed, "defect": control.defect,
                     "matched": matched, "htif": verdict, "htif_code": code,
                     "run_error": run_error,
                     "process_returncode": returncode,
                     "observations": observed, "argv": argv,
                     "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
                     "elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
                     "trace_sha256": trace.digest(normalized),
                     "extents": {name: assembler.symbols[name] for name in assembler.symbols
                                 if name.startswith("vos_restore_")}})
    unchanged = (sources == receipts.inputs(root, *input_paths)
                 and model_sources == receipts.inputs(root, "model")
                 and simulator_digest == receipts.digest(simulator)
                 and profile_digest == receipts.digest(profile)
                 and build_digest == receipts.digest(build_receipt))
    report: Report = {
        "scope": "scalar restore primitive under generated harness; no firmware or C lowering",
        "milestone_acceptance": "open", "cases": rows,
        "simulator": str(simulator), "simulator_sha256": simulator_digest,
        "profile_sha256": profile_digest, "sources": sources, "model_sources": model_sources,
        "build_receipt": str(build_receipt), "build_receipt_sha256": build_digest,
        "inputs_unchanged": unchanged,
        "ok": unchanged and all(row["matched"] for row in rows),
    }
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
