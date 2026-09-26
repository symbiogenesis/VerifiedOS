# SPDX-License-Identifier: Apache-2.0
"""Composed C-class kernel consumer, linked to the actual firmware handoff.

The generated source keeps compiler output in the caller's contained native
directory. Constants here describe one finite composition, not architecture.
"""

import hashlib
import json
import subprocess
from pathlib import Path

from vos import asm, boot_handoff, kernel_restore, kernelrun, receipts, trace
from vos.boot_signing import SlhSigner
from vos.cli import compiler_diff

COMPOSITION = 7
PARTITIONS = 2
WINDOWS = 2
SLOTS = 2
CSRS = 1
STATE_BYTES = 4096
CONTEXT_BYTES = 320
STACK_BYTES = 8192
SLOT_WIDTH = 4096


def _address(register: int, label: str, root: int = 18) -> list[str]:
    return [f"    li x5, {label}", f"    csetaddr c{register}, c{root}, x5"]


def _cap_check(register: int, base: str, length: str, permissions: int,
               failure: int) -> list[str]:
    return [f"    li x3, {failure}", f"    cgettag x5, c{register}",
            "    beqz x5, kernel_fail", f"    cgetsealed x5, c{register}",
            "    bnez x5, kernel_fail", f"    cgetbase x5, c{register}",
            f"    li x6, {base}", "    bne x5, x6, kernel_fail",
            f"    cgetaddr x5, c{register}", "    bne x5, x6, kernel_fail",
            f"    cgetlen x5, c{register}", f"    li x6, {length}",
            "    bne x5, x6, kernel_fail", f"    cgetperm x5, c{register}",
            f"    li x6, {permissions}", "    bne x5, x6, kernel_fail"]


def consumer_source(compiled: str, init_magic: int,
                    timer_windows: tuple[tuple[int, int], tuple[int, int]]) -> str:
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
    for index, ((base, size), permissions) in enumerate(zip(timer_windows, (7, 3), strict=True), 1):
        lines += [f"    lc c20, {index * 8}(c10)"]
        lines += _cap_check(20, str(base), str(size), permissions, 11 + index)
    for index, name in enumerate(("partition_one", "partition_two"), 3):
        lines += [f"    lc c20, {index * 8}(c10)"]
        lines += _cap_check(20, name, "64", 0x1cb, 11 + index)
    lines += [*_address(19, "root_handle"), "    sc c10, 0(c19)"]
    lines += ["    cincoffsetimm c2, c2, -16", "    sc c2, 0(c2)"]
    # Each attempt names one actual capability, and checks its result on target.
    for index, (name, register) in enumerate((("root", 18), ("window0", 20),
                                             ("window1", 21))):
        if index:
            lines += [f"    lc c{register}, {index * 8}(c10)"]
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
    lines += [*_address(10, "target_state"), *_address(11, "selected_context")]
    lines += ["    lc c11, 0(c11)"]
    lines += [*_address(12, "previous_context"), *_address(13, "restore_context")]
    lines += ["    call vos_target_switch", "    cspecialrw c18, mtdc, cnull"]
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
              "selected_context:", "    .dword 0", ".align 6", "partition_one_data:",
              "    .space 64", "partition_two_data:", "    .space 64",
              "target_state:", f"    .space {STATE_BYTES}"]
    for name in ("partition_one_context", "partition_two_context", "previous_context", "restore_context"):
        lines += [".align 6", f"{name}:", f"    .space {CONTEXT_BYTES}"]
    lines += [".align 13", "kstack_base:", f"    .space {STACK_BYTES - 16}",
              "kernel_stack:", "    .space 16", "kstack_end:",
              "kdata_end:", "root_table:", "    .space 40",
              "root_table_end:", ".align 6", "init_desc:"]
    words: list[int | str] = [init_magic, 1, COMPOSITION, 0,
        "0x80000000", "0x80010000", "kernel_text_base", "kernel_text_end",
        PARTITIONS, WINDOWS, SLOTS, 0, SLOT_WIDTH * SLOTS, 0, 1, 0, 0, 0]
    for tenant, name in ((1, "partition_one"), (2, "partition_two")):
        words += [tenant, f"{name}_context", f"{name}_context + {CONTEXT_BYTES}",
                  name, f"{name} + 64", f"{name}_data", f"{name}_data + 64"]
    for base, size in timer_windows:
        words += [base, base + size]
    for index in range(SLOTS):
        words += [SLOT_WIDTH, index * SLOT_WIDTH, 0, SLOT_WIDTH * SLOTS, index + 1]
    lines += [f"    .dword {value}" for value in words]
    lines += ["init_desc_end:"]
    return "\n".join(lines) + "\n"


def observations(records: list[kernelrun.Record], symbols: dict[str, int]) -> dict[str, object]:
    """Read confinement, each real saved image/restore pair and one complete frame."""
    attempts = tuple(kernelrun.Attempt(symbols[f"attempt_{name}"], 19, target)
                     for name, target in (("root", "R"), ("window0", "W0"), ("window1", "W1")))
    restore = kernelrun.Extent(symbols["vos_restore_begin"], symbols["vos_restore_end"])
    bursts = kernelrun.restore_bursts(records, restore)
    snapshots: list[kernelrun.Image] = []
    saved: dict[int, tuple[int, bool]] = {}
    frame_records: list[kernelrun.Record] = []
    frame_started = False
    timer_entries = 0
    for kind, fields in records:
        if kind == "W" and fields[1] == 8:
            offset = fields[0] - symbols["restore_context"]
            if 0 <= offset < 256 and offset % 8 == 0:
                saved[offset // 8] = (fields[3], bool(fields[2]))
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
    total = (len(bursts) == SLOTS and len(snapshots) == SLOTS
             and all(kernelrun.switch_is_total((), saved_image, burst)
                     and kernelrun.burst_writes_exactly_once((), burst)
                     for saved_image, burst in zip(snapshots, bursts, strict=True)))
    interrupts = [fields for kind, fields in records if kind == "T"]
    return {
        "root_and_window_attempts": kernelrun.well_formed_attempts(attempts)
            and kernelrun.root_is_the_partitions(WINDOWS, attempts, records),
        "complete_restores": total,
        "restore_count": len(bursts),
        "frame_order": kernelrun.frame_is_the_tables(
            kernelrun.Extent(symbols["kernel_text_base"], symbols["kernel_text_end"]), frame, frame_records),
        "timer_boundaries": interrupts == [(1, 7)] * SLOTS and timer_entries == SLOTS,
        "scalar_csrs": all(kind != "C" for burst in bursts for kind, _ in burst),
    }


def run(root: Path, ccomp: Path, ccomp_args: list[str], simulator: Path,
        build_receipt: Path, out: Path, timeout: int) -> dict[str, object]:
    """Compile authored C, sign/release its actual payload, and run the consumer.

    The RoT release currently remains host-executed. The report retains that
    explicit chain limitation independently of successful kernel observations.
    """
    root, ccomp, simulator, build_receipt, out = (
        path.resolve() for path in (root, ccomp, simulator, build_receipt, out))
    out.mkdir(parents=True, exist_ok=True)
    sources = receipts.inputs(root, "kernel", "firmware", "tools/vos/kernel_target.py",
                              "tools/vos/boot_handoff.py", "tools/vos/boot_signing.py",
                              "tools/vos/kernel_restore.py", "tools/vos/kernelrun.py",
                              "tools/vos/cli/compiler_diff.py", "tools/vos/asm.py",
                              "tools/vos/image.py", "tools/vos/trace.py")
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
    consumer = consumer_source(compiler_diff.normalize(compiled.stream), lay["INIT_MAGIC"], windows)
    stage = boot_handoff.scheduled_mmode(root, partition_text=(
        ("partition_one", "partition_one_end"), ("partition_two", "partition_two_end")))
    source = stage + "\n" + consumer
    (out / "kernel.s").write_text(source, encoding="utf-8", newline="\n")
    built = boot_handoff.assemble_mmode(root, stage_text=stage, kernel_text=consumer,
                                       data_base=lay["BRINGUP_MMODE_LOAD_BASE"] + 0xa000)
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
    release = boot_handoff.rot_stage(binary, image_path, inputs, "slh256s", out, roots=signer.roots)
    if release.get("verdict") != "release" or release.get("released") != "1":
        raise ValueError(f"real signature release refused kernel: {release}")
    window, record = (out / "sram.bin").read_bytes(), (out / "handoff.bin").read_bytes()
    if window[:len(built.payload)] != built.payload:
        raise ValueError("released kernel bytes differ from the compiled payload")
    elf = out / "kernel.elf"
    boot_handoff.placed_elf(lay, window, record, built.symbols["tohost"], elf)
    argv = [str(simulator), "--config", str(root / boot_handoff.MAIN_CONFIG),
            "--trace-commit", "--inst-limit", "200000", str(elf)]
    done = subprocess.run(argv, cwd=out, capture_output=True, text=True, timeout=timeout, check=False)
    raw = done.stdout + done.stderr
    (out / "kernel.trace").write_text(raw, encoding="utf-8", newline="\n")
    normalized = trace.normalize_commit(raw.splitlines())
    observed = observations(kernelrun.parse_records(normalized), built.symbols)
    htif, code, _ = compiler_diff.htif_verdict(raw, done.returncode)
    unchanged = (sources == receipts.inputs(root, "kernel", "firmware", "tools/vos/kernel_target.py",
        "tools/vos/boot_handoff.py", "tools/vos/boot_signing.py", "tools/vos/kernel_restore.py",
        "tools/vos/kernelrun.py", "tools/vos/cli/compiler_diff.py", "tools/vos/asm.py",
        "tools/vos/image.py", "tools/vos/trace.py")
        and model_sources == receipts.inputs(root, "model")
        and compiler_sha == receipts.digest(ccomp) and simulator_sha == receipts.digest(simulator)
        and build_sha == receipts.digest(build_receipt))
    report: dict[str, object] = {
        "scope": "two-slot C-class kernel under actual signed M-mode release; RoT C runs on host",
        "milestone_acceptance": "open", "sources": sources, "model_sources": model_sources,
        "compiler_sha256": compiler_sha, "simulator_sha256": simulator_sha,
        "build_receipt_sha256": build_sha, "host_compiler": host_compiler,
        "compilation": {"argv": compiled.argv, "stream_sha256": compiled.stream_sha256,
                        "preprocessed_sha256": compiled.preprocessed.sha256},
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "elf_sha256": receipts.digest(elf), "trace_sha256": trace.digest(normalized),
        "release": release, "signer": signer.identity(), "symbols": built.symbols,
        "htif": htif, "htif_code": code, "observations": observed,
        "inputs_unchanged": unchanged,
        "ok": unchanged and htif == "pass" and all(observed.values()),
    }
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
