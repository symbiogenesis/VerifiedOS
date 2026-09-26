# SPDX-License-Identifier: Apache-2.0
"""Scalar restore emission controls; emulator execution is `kernel restore`."""

import json
import subprocess
import tempfile
from pathlib import Path
from unittest import mock

from tests.harness import Case, ensure
from vos import asm, dialect, kernel_restore, kernelrun, receipts


def unsupported_architecture() -> None:
    for core_class, roster in (("V", ()), ("M", ()), ("C", (0x300,))):
        try:
            kernel_restore.emit(core_class=core_class, csr_roster=roster)
        except ValueError:
            continue
        raise AssertionError(f"unsupported restore accepted: {core_class}, {roster}")


def generated_controls_assemble() -> None:
    for control in kernel_restore.controls():
        assembler = asm.Assembler(kernel_restore.control_source(control), control.name)
        assembler.assemble()
        symbols = assembler.symbols
        ensure(symbols["vos_restore_setup"] < symbols["vos_restore_begin"]
               <= symbols["vos_restore_end"] == symbols["vos_restore_dispatch"]
               < symbols["vos_restore_dispatch_end"] == symbols["successor"],
               f"invalid restore/dispatch cut in {control.name}")
        if control.defect == "none":
            ensure(symbols["vos_restore_end"] - symbols["vos_restore_begin"] == 32 * 4,
                   "restore must include 31 register loads and the fence")


def absent_observations_refused() -> None:
    assembler = asm.Assembler(kernel_restore.control_source(kernel_restore.controls()[0]), "empty")
    assembler.assemble()
    observed = kernel_restore.observations([], assembler.symbols)
    ensure(not any(observed.values()), f"missing trace supplied evidence: {observed}")


def ordered_trace_controls() -> None:
    """Equal final values cannot conceal duplicate or missing register writes."""
    assembler = asm.Assembler(kernel_restore.control_source(kernel_restore.controls()[0]), "trace")
    sections, _, _ = assembler.assemble()
    symbols = assembler.symbols
    text = sections[0]
    def insn(pc: int) -> kernelrun.Record:
        offset = pc - text.addr
        return "I", (pc, int.from_bytes(text.data[offset:offset + 4], "little"))

    records: list[kernelrun.Record] = [
        ("W", (symbols["context"] + r * 8, 8, r % 2, r * 17)) for r in range(32)]
    records += [("W", (symbols["context"] + 256, 8, 1, 1234)),
                insn(symbols["vos_restore_setup"]),
                ("X", (30, 1, 1234)),
                insn(symbols["vos_restore_setup"] + 4),
                ("S", (dialect.SCRS["mepcc"], 1, 1234))]
    for r in range(1, 32):
        records += [insn(symbols["vos_restore_begin"] + (r - 1) * 4),
                    ("X", (r, r % 2, r * 17))]
    records += [insn(symbols["vos_restore_end"] - 4),
                insn(symbols["vos_restore_dispatch"]),
                ("C", (dialect.CSRS["mstatus"], 0)), insn(symbols["successor"])]
    ensure(all(kernel_restore.observations(records, symbols).values()), "valid trace refused")
    at = next(i for i, rec in enumerate(records) if rec == ("X", (17, 1, 289)))
    duplicate = [*records[:at], records[at], *records[at:]]
    observed = kernel_restore.observations(duplicate, symbols)
    ensure(observed["register_values_and_tags"] and not observed["exactly_once"],
           "coincidentally equal duplicate write passed")
    omitted = records[:at] + records[at + 1:]
    observed = kernel_restore.observations(omitted, symbols)
    ensure(not observed["register_values_and_tags"] and not observed["exactly_once"],
           "missing write passed")
    wrong_dispatch = [(kind, (0x301, *fields[1:])) if kind == "C" else (kind, fields)
                      for kind, fields in records]
    ensure(not kernel_restore.observations(wrong_dispatch, symbols)[
        "dispatch_mstatus_outside_restore"], "wrong dispatch CSR passed")
    # These preserve every register's value and global write order. Only
    # instruction/effect association distinguishes the wrong trace.
    shifted = [*records[:at], records[at + 1], records[at], *records[at + 2:]]
    observed = kernel_restore.observations(shifted, symbols)
    ensure(observed["exact_instruction_sequence"] and observed["exactly_once"]
           and observed["register_values_and_tags"] and not observed["register_effects_aligned"],
           "a register effect borrowed its next instruction")
    setup_at = next(i for i, rec in enumerate(records)
                    if rec == insn(symbols["vos_restore_setup"]))
    load_at = next(i for i, rec in enumerate(records)
                   if rec == insn(symbols["vos_restore_begin"]))
    fence_at = next(i for i, rec in enumerate(records)
                    if rec == insn(symbols["vos_restore_end"] - 4))
    dispatch_at = next(i for i, rec in enumerate(records)
                       if rec == insn(symbols["vos_restore_dispatch"]))
    prefix, setup = records[:setup_at], records[setup_at:load_at]
    loads, fence = records[load_at:fence_at], records[fence_at:dispatch_at]
    dispatch, successor = records[dispatch_at:-1], records[-1:]
    corruptions = {
        "fence before loads": prefix + setup + fence + loads + dispatch + successor,
        "MEPCC installed after restore": prefix + loads + fence + setup + dispatch + successor,
        "successor before restore": prefix + successor + setup + loads + fence + dispatch,
        "dispatch before restore": prefix + setup + dispatch + loads + fence + successor,
    }
    for name, corrupted in corruptions.items():
        observed = kernel_restore.observations(corrupted, symbols)
        ensure(not observed["exact_instruction_sequence"], f"accepted {name}")
        ensure(not all(observed.values()), f"phase ordering supplied false acceptance: {name}")


def stale_model_build_refused() -> None:
    inputs = {"model/model/core/ext_regs.sail": "source"}
    record = {"schema": 1, "exit_code": 0,
              "stages": {"configure": 0, "build": 0, "ctest": 0},
              "identity": {"inputs": inputs},
              "artifacts": {"c_emulator/sail_riscv_sim": "binary"}}
    kernel_restore.require_build(record, "binary", inputs)
    for candidate, digest, sources in (
        ({**record, "exit_code": 1}, "binary", inputs),
        (record, "changed-binary", inputs),
        (record, "binary", {**inputs, "model/new.sail": "new"}),
        (record, "binary", {"model/model/core/ext_regs.sail": "changed"}),
    ):
        try:
            kernel_restore.require_build(candidate, digest, sources)
        except ValueError:
            continue
        raise AssertionError("a failed build, changed simulator or stale model was accepted")


def relative_run_paths_reach_the_child_absolutely() -> None:
    fixture_root = Path(__file__).resolve().parents[2] / "out"
    fixture_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kernel-restore-paths-", dir=fixture_root) as directory:
        root = Path(directory).resolve()
        simulator = root / "simulator"
        simulator.write_bytes(b"path fixture; never executed")
        profile = root / "model/config/verifiedos.json"
        profile.parent.mkdir(parents=True)
        profile.write_text("{}", encoding="utf-8")
        sources = {"model/config/verifiedos.json": receipts.digest(profile)}
        build = root / "build.json"
        build.write_text(json.dumps({"schema": 1, "exit_code": 0,
            "stages": {"configure": 0, "build": 0, "ctest": 0},
            "identity": {"inputs": sources},
            "artifacts": {"c_emulator/sail_riscv_sim": receipts.digest(simulator)}}),
            encoding="utf-8")
        output = root / "nested/output"

        def execute(argv: list[str], *, cwd: Path, capture_output: bool,
                    text: bool, timeout: int, check: bool) -> subprocess.CompletedProcess[str]:
            ensure(cwd == output and cwd.is_absolute(), "child cwd was relative")
            ensure(Path(argv[0]) == simulator, "relative simulator was rebased under output")
            ensure(Path(argv[2]) == profile, "relative profile was rebased under output")
            ensure(Path(argv[-1]).is_absolute() and Path(argv[-1]).is_file(),
                   "child ELF argument cannot name its actual input")
            return subprocess.CompletedProcess(argv, 1, "", "")

        control = kernel_restore.controls()[0]
        with (mock.patch.object(receipts, "inputs", return_value=sources),
              mock.patch.object(kernel_restore, "controls", return_value=(control,)),
              mock.patch.object(subprocess, "run", side_effect=execute) as process):
            relative = [p.relative_to(Path.cwd(), walk_up=True)
                        for p in (root, simulator, output, build)]
            result = kernel_restore.run(relative[0], relative[1], relative[2], 60, relative[3])
        ensure(process.call_count == 1 and not result["ok"],
               "path fixture supplied a fabricated emulator verdict")
        ensure((output / "report.json").is_file(), "output path was rebased under itself")


def cases() -> list[Case]:
    return [Case("unsupported_architecture", unsupported_architecture),
            Case("generated_controls_assemble", generated_controls_assemble),
            Case("absent_observations_refused", absent_observations_refused),
            Case("ordered_trace_controls", ordered_trace_controls),
            Case("stale_model_build_refused", stale_model_build_refused),
            Case("relative_run_paths_reach_the_child_absolutely",
                 relative_run_paths_reach_the_child_absolutely)]
