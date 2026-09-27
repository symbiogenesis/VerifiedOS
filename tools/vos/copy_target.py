# SPDX-License-Identifier: Apache-2.0
"""Accepted scalar C stages joined to the actual fenced ring adapter."""

import hashlib
import itertools
import json
import subprocess
from collections import deque
from pathlib import Path
from typing import cast

from vos import asm, copy_service, image, kernel_restore, receipts, trace
from vos.boot_target import compiler_inputs
from vos.cli import compiler_diff as cd

RING_BYTES = 524288
INPUTS = ("copy-service", "interfaces/ring-reference.json", "tools/vos/copy_service.py",
          "tools/vos/copy_target.py", "tools/vos/cli/copy_service.py",
          "tools/vos/cli/compiler_diff.py", "tools/vos/asm.py", "tools/vos/image.py",
          "tools/generated/dialect-table.json")


def wakeup_litmus(fenced: bool) -> tuple[int, list[tuple[str, ...]]]:
    """Enumerate the projected two-cell Store/Load race, not an ISA proof.

    Producer AMO drains its preceding publication. Consumer's fence drains its
    arm store before recheck. Deleting that edge exposes the lost-wakeup trace.
    Kernel pending-signal preservation is a separate adapter obligation.
    """
    examined = 0
    lost = []
    for order in itertools.permutations(("publish", "exchange", "arm", "flush", "recheck")):
        positions = {event: order.index(event) for event in order}
        if (positions["publish"] > positions["exchange"]
                or positions["arm"] > positions["flush"]
                or positions["arm"] > positions["recheck"]
                or (fenced and positions["flush"] > positions["recheck"])):
            continue
        examined += 1
        head = armed = signal = seen = 0
        for event in order:
            if event == "exchange":
                head = 1
                signal, armed = armed, 0
            elif event == "flush":
                armed = 1
            elif event == "recheck":
                seen = head
        if seen == 0 and signal == 0:
            lost.append(order)
    return examined, lost


def adapter(root: Path) -> str:
    config = copy_service.configuration(root)
    return (f".equ COPY_MAX_BATCH, {config.batch}\n.equ COPY_GENERATION, {config.generation}\n"
            + (root / "copy-service/src/atomic_target.s").read_text(encoding="utf-8"))


def execute(simulator: Path, profile: Path, elf: Path, timeout: int) -> dict[str, object]:
    """Retain the actual trace on native storage without keeping it all in RAM."""
    log = elf.with_suffix(".log")
    terminal = elf.with_suffix(".term")
    terminal.unlink(missing_ok=True)
    argv = [str(simulator), "--config", str(profile), "--trace-commit",
            "--inst-limit", "40000000", "--terminal-log", str(terminal), str(elf)]
    with log.open("w", encoding="utf-8") as output:
        done = subprocess.run(argv, cwd=elf.parent, stdout=output, stderr=subprocess.STDOUT,
                              timeout=timeout, check=False)
    digest = hashlib.sha256()
    count = 0
    messages: deque[str] = deque(maxlen=64)
    with log.open(encoding="utf-8") as output:
        for line in output:
            records = trace.normalize_commit([line])
            if not records:
                messages.append(line)
            for record in records:
                if count:
                    digest.update(b"\n")
                digest.update(record.encode())
                count += 1
    verdict, code, detail = cd.htif_verdict("".join(messages), done.returncode)
    if verdict == "pass" and count == 0:
        raise ValueError("target success has no commit trace")
    return {"verdict": verdict, "code": code, "detail": detail, "records": count,
            "trace_sha256": digest.hexdigest(), "log": str(log), "argv": argv}


def reference_rows(root: Path, reference: Path) -> tuple[list[list[int]], dict[str, object]]:
    report = json.loads((reference / "report.json").read_text(encoding="utf-8"))
    if report.get("comparison") != "passed":
        raise ValueError("requires completed copy-service reference comparison")
    sources = report.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("reference comparison has no bound sources")
    for name, digest in sources.items():
        if receipts.digest(root / name) != digest:
            raise ValueError(f"reference comparison input changed: {name}")
    answers = reference / "answers.txt"
    if receipts.digest(answers) != report.get("answers_sha256"):
        raise ValueError("reference answers changed")
    cases = copy_service.generated(copy_service.configuration(root))
    lines = answers.read_text(encoding="utf-8").splitlines()
    if len(cases) != len(lines):
        raise ValueError("reference population differs")
    # Validate the reference's closed natural output grammar, without an oracle
    # in this driver. Its existing Gallina conversion owns expected answers.
    copy_service.comparison_source(cases, "\n".join(lines))
    rows = []
    for case, line in zip(cases, lines, strict=True):
        values = [int(value) for value in line.split()]
        if len(case.inputs) > 10 or len(values) > 10:
            raise ValueError("target comparison row exceeds its declared width")
        rows.append([len(case.inputs), len(values), *case.inputs,
                     *([0] * (10 - len(case.inputs))), *values, *([0] * (10 - len(values)))])
    return rows, cast(dict[str, object], report)


def controls(config: copy_service.Config, rows: list[list[int]]) -> str:
    """Exercise actual target publication, transfer, wrap and bounded batches."""
    lines = [".text", "main:", "    cmove c5, c2", "    cincoffsetimm c2, c2, -16",
             "    sc c1, 0(c2)", "    sc c5, 8(c2)", "    call vos_copy_target_layout",
             "    li x5, 1", "    bne x10, x5, copy_fail"]
    sizes = {"copy_ring": RING_BYTES, "copy_source": config.maximum + 1,
             "copy_destination": config.maximum + 2, "copy_signal": 8, "copy_length": 8,
             "copy_request": 8, "copy_cycles": 8, "copy_backlog": 8,
             "copy_batch": config.batch * 40, "copy_results": config.batch * 4,
             "copy_signals": config.batch * 4, "copy_rows": len(rows) * 22 * 4}
    extents = {name: 1 << (size - 1).bit_length() for name, size in sizes.items()}

    def ptr(reg: int, label: str) -> None:
        base = label.split(" + ", 1)[0]
        lines.extend([f"    li x31, {base}", f"    csetaddr c{reg}, c4, x31",
                      f"    li x31, {extents[base]}", f"    csetbounds c{reg}, c{reg}, x31"])
        if base != label:
            lines.extend([f"    li x31, {label}", f"    csetaddr c{reg}, c{reg}, x31"])

    def expected(value: int) -> None:
        lines.extend([f"    li x5, {value}", "    bne x10, x5, copy_fail"])

    def read(label: str, value: int, width: str = "lwu", offset: int = 0) -> None:
        if not -2048 <= offset <= 2047:
            label, offset = f"{label} + {offset}", 0
        ptr(5, label)
        lines.extend([f"    {width} x6, {offset}(c5)", f"    li x7, {value}",
                      "    bne x6, x7, copy_fail"])

    def write(label: str, value: int, width: str = "sw", offset: int = 0) -> None:
        if not -2048 <= offset <= 2047:
            label, offset = f"{label} + {offset}", 0
        ptr(5, label)
        lines.extend([f"    li x6, {value}", f"    {width} x6, {offset}(c5)"])

    def init() -> None:
        ptr(10, "copy_ring")
        lines.append("    call vos_copy_init")

    def submit(request: int, length: int = 1, *, generation: int | None = None,
               operation: int = 0, extent: int | None = None, answer: int = 1) -> None:
        ptr(10, "copy_ring")
        lines.extend([f"    li x11, {config.generation if generation is None else generation}",
                      f"    li x12, {request}", f"    li x13, {operation}"])
        ptr(14, "copy_source")
        lines.extend([f"    li x15, {length if extent is None else extent}", f"    li x16, {length}"])
        ptr(17, "copy_signal")
        lines.append("    call vos_copy_submit")
        expected(answer)

    def take(answer: int = 1, capacity: int | None = None) -> None:
        ptr(10, "copy_ring")
        ptr(11, "copy_destination + 1")
        lines.append(f"    li x12, {config.maximum if capacity is None else capacity}")
        ptr(13, "copy_length")
        ptr(14, "copy_request")
        lines.append("    call vos_copy_take")
        expected(answer)

    ptr(10, "copy_rows")
    ptr(12, "copy_source")
    ptr(13, "copy_destination")
    lines.extend([f"    li x11, {len(rows)}", "    call vos_copy_target_rows"])
    expected(0)
    init()
    write("copy_length", 93, "sd")
    write("copy_request", 91)
    write("copy_signal", 92)
    take(0)
    read("copy_length", 93, "ld")
    read("copy_request", 91)
    submit(1, config.maximum + 1, answer=0)
    submit(1, generation=config.generation + 1, answer=0)
    submit(1, operation=len(config.payloads), answer=0)
    read("copy_signal", 92)
    ptr(10, "copy_ring")
    lines.append("    call vos_copy_prepare_sleep")
    expected(1)
    # Fill a patterned external source, then verify that later mutation cannot
    # change bytes copied into private staging before publication.
    ptr(6, "copy_source")
    lines.extend(["    li x7, 0", f"    li x8, {config.maximum}", "copy_fill_bytes:",
                  "    li x9, 17", "    mul x9, x7, x9", "    addi x9, x9, 3",
                  "    sb x9, 0(c6)", "    cincoffsetimm c6, c6, 1",
                  "    addi x7, x7, 1", "    bltu x7, x8, copy_fill_bytes"])
    write("copy_destination", 165, "sb")
    write("copy_destination", 165, "sb", config.maximum + 1)
    submit(1, config.payloads[0])
    read("copy_signal", 1)
    submit(1, answer=0)
    take(0, 0)
    ptr(6, "copy_source")
    lines.extend([f"    li x7, {config.maximum}", "    li x8, 255", "copy_mutate_source:",
                  "    sb x8, 0(c6)", "    cincoffsetimm c6, c6, 1", "    addi x7, x7, -1",
                  "    bnez x7, copy_mutate_source"])
    take()
    read("copy_length", config.payloads[0], "ld")
    read("copy_request", 1)
    read("copy_destination", 165, "lbu")
    read("copy_destination", 165, "lbu", config.maximum + 1)
    ptr(6, "copy_destination + 1")
    lines.extend(["    li x7, 0", f"    li x8, {config.payloads[0]}", "copy_check_bytes:",
                  "    li x9, 17", "    mul x9, x7, x9", "    addi x9, x9, 3",
                  "    andi x9, x9, 255", "    lbu x10, 0(c6)", "    bne x10, x9, copy_fail",
                  "    cincoffsetimm c6, c6, 1", "    addi x7, x7, 1",
                  "    bltu x7, x8, copy_check_bytes"])
    # Repeat one statically emitted full-window control across multiple wire
    # wraps. A persistent counter is data because every call clobbers registers.
    write("copy_cycles", 2 * config.span // config.capacity + 1)
    lines.append("copy_wrap_cycle:")
    for index in range(config.capacity):
        write("copy_source", index, "sb")
        submit(index)
    submit(config.capacity, answer=0)
    for index in range(config.capacity):
        take()
        read("copy_request", index)
        read("copy_destination", index, "lbu", 1)
    ptr(5, "copy_cycles")
    lines.extend(["    lwu x6, 0(c5)", "    addi x6, x6, -1", "    sw x6, 0(c5)",
                  "    beqz x6, copy_wrap_done", "    j copy_wrap_cycle", "copy_wrap_done:"])
    init()
    for index in range(config.capacity - 1):
        submit(index)
    # The batch descriptors carry source capabilities, not their bit patterns.
    for index in range(config.batch):
        ptr(6, f"copy_batch + {index * 40}")
        lines.extend([f"    li x7, {config.generation}", "    sw x7, 0(c6)",
                      f"    li x7, {config.capacity + index}", "    sw x7, 4(c6)", "    sw x0, 8(c6)"])
        ptr(7, "copy_source")
        lines.extend(["    sc c7, 16(c6)", "    li x7, 1", "    sd x7, 24(c6)", "    sd x7, 32(c6)"])
    for count, answer in ((config.batch + 1, 0), (config.batch, 1)):
        ptr(10, "copy_ring")
        ptr(11, "copy_batch")
        lines.append(f"    li x12, {count}")
        ptr(13, "copy_results")
        ptr(14, "copy_signals")
        lines.append("    call vos_copy_submit_batch")
        expected(answer)
    for index in range(config.batch):
        read("copy_results", int(index == 0), offset=index * 4)
    for _ in range(config.capacity):
        take()
    read("copy_request", config.capacity)
    # Publication at each boundary of drain/arm/recheck/sleep. After arming,
    # the actual exchange requests a sticky kernel signal even after recheck.
    for step in range(5):
        init()
        write("copy_signal", 0)
        for boundary in range(5):
            if step == boundary:
                submit(77)
            if boundary == 0:
                take(1 if step == 0 else 0)
            elif boundary == 1:
                write("copy_ring", 1, offset=4)
                lines.append("    fence rw, rw")
            elif boundary == 2:
                ptr(5, "copy_ring")
                lines.extend(["    lbu x6, 0(c5)", "    lbu x7, 1(c5)", "    sub x6, x6, x7"])
                ptr(5, "copy_backlog")
                lines.append("    sw x6, 0(c5)")
        read("copy_signal", int(step >= 2))
        if step == 1 or step == 2:
            read("copy_backlog", 1)
    init()
    ptr(10, "copy_ring")
    lines.extend(["    li x11, 0", "    call vos_copy_init_generation"])
    expected(0)
    read("copy_ring", config.generation, offset=8)
    if config.generation == 2**32 - 1:
        raise ValueError("target restart controls require an available successor generation")
    ptr(10, "copy_ring")
    lines.extend([f"    li x11, {config.generation + 1}", "    call vos_copy_init_generation"])
    expected(1)
    submit(88, generation=config.generation, answer=0)
    submit(88, generation=config.generation + 1)
    take()
    lines.extend(["    li x10, 0", "    j copy_return", "copy_fail:", "    li x10, 1",
                  "copy_return:", "    lc c1, 0(c2)", "    lc c2, 8(c2)", "    ret", ".data"])
    for label, size in extents.items():
        if label != "copy_rows":
            lines.extend([f"    .balign {size}", f"{label}:", f"    .space {size}"])
    lines.extend([f"    .balign {extents['copy_rows']}", "copy_rows:"])
    lines.extend("    .word " + ", ".join(map(str, row)) for row in rows)
    lines.append(f"    .space {extents['copy_rows'] - sizes['copy_rows']}")
    expanded = []
    for index, line in enumerate(lines):
        if line.startswith("    bne ") and line.endswith(", copy_fail"):
            local = f"copy_check_{index}"
            expanded.extend([line.replace("bne ", "beq ").replace("copy_fail", local),
                             "    j copy_fail", f"{local}:"])
        else:
            expanded.append(line)
    return "\n".join(expanded) + "\n"


def run(root: Path, out: Path, reference: Path, ccomp: Path, arguments: list[str],
        simulator: Path, build_receipt: Path, timeout: int = 600) -> dict[str, object]:
    root, out, reference, ccomp, simulator, build_receipt = (
        p.resolve() for p in (root, out, reference, ccomp, simulator, build_receipt))
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text('{"verdict":"incomplete"}\n', encoding="utf-8")
    sources = receipts.inputs(root, *INPUTS)
    model_sources = receipts.inputs(root, "model")
    simulator_sha, compiler_sha = receipts.digest(simulator), receipts.digest(ccomp)
    private = compiler_inputs(arguments)
    build_sha = receipts.digest(build_receipt)
    kernel_restore.require_build(json.loads(build_receipt.read_text(encoding="utf-8")),
                                 simulator_sha, model_sources)
    rows, comparison = reference_rows(root, reference)
    litmus_count, lost = wakeup_litmus(True)
    _, unfenced = wakeup_litmus(False)
    if lost or not unfenced:
        raise ValueError("wakeup ordering projection or missing-fence control failed")
    config = copy_service.configuration(root)
    header = out / "copy_service_config.h"
    header.write_text(copy_service.configuration_header(config), encoding="utf-8")
    compiled = cd.compile_c([str(ccomp), *arguments, "-fverifiedos-typed", f"-I{out}",
                             f"-I{root / 'copy-service/include'}"],
                            root / "copy-service/test/target_unit.c", out / "compiler", timeout)
    if compiled.exit_code or compiled.stream is None:
        raise ValueError(f"copy target compilation failed: {compiled.said}")
    stream = cd.normalize(compiled.stream) + adapter(root) + controls(config, rows)
    (out / "copy-target.s").write_text(stream, encoding="utf-8")
    # This member's full-window controls exceed the generic 32 KiB text slot.
    # Give its test composition a disjoint declared data section.
    source = cd.compose(stream)
    assembler = asm.Assembler(source, "copy-target", data_base=0x80200000)
    sections, symbols, entry = assembler.assemble()
    elf = out / "copy-target.elf"
    image.write_elf(elf, sections, symbols, entry)
    profile = root / "model/config/verifiedos.json"
    ran = execute(simulator, profile, elf, timeout)
    if ran["verdict"] != "pass":
        raise ValueError(f"copy target controls failed: {ran['detail']}")
    negatives = []
    wrong_rows = [row.copy() for row in rows]
    wrong_rows[0][12] += 1
    variants = {
        "wrong-reference": cd.normalize(compiled.stream) + adapter(root) + controls(config, wrong_rows),
        "lost-publication": stream.replace("    sb x6, 0(c5)\n", "    sb x0, 0(c5)\n", 1),
    }
    if variants["lost-publication"] == stream:
        raise ValueError("publication mutant no longer applies")
    for name, variant in variants.items():
        mutant = asm.Assembler(cd.compose(variant), name, data_base=0x80200000)
        sections, symbols, entry = mutant.assemble()
        mutant_elf = out / f"{name}.elf"
        image.write_elf(mutant_elf, sections, symbols, entry)
        result = execute(simulator, profile, mutant_elf, timeout)
        if result["verdict"] != "fail" or result["code"] != 1:
            raise ValueError(f"{name} was not detected by an executed target control")
        negatives.append({"name": name, "classification": "killed", "run": result,
                          "image_sha256": receipts.digest(mutant_elf)})
    unchanged = (sources == receipts.inputs(root, *INPUTS)
                 and model_sources == receipts.inputs(root, "model")
                 and compiler_sha == receipts.digest(ccomp)
                 and simulator_sha == receipts.digest(simulator)
                 and private == compiler_inputs(arguments)
                 and build_sha == receipts.digest(build_receipt))
    if not unchanged:
        raise ValueError("copy target inputs changed during execution")
    report: dict[str, object] = {
        "schema": 1, "verdict": "pass", "milestone_acceptance": "open",
        "sources": sources, "compiler_sha256": compiler_sha, "compiler_inputs": private,
        "simulator_sha256": simulator_sha, "model_build_sha256": build_sha,
        "model_sources": model_sources, "reference": comparison,
        "rows": len(rows), "preprocessed_sha256": compiled.preprocessed.sha256,
        "image_sha256": receipts.digest(elf), "stream_sha256": receipts.digest(out / "copy-target.s"),
        "run": ran, "negative_controls": negatives,
        "wakeup_projection": {"orders": litmus_count, "lost": 0,
                              "unfenced_counterexamples": unfenced},
        "limits": "Single-hart component controls; kernel effect and composed boot joins separate. "
                  "Fenced ordering is explicit; no cross-core refinement or TAL ownership proof."}
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
