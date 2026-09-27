# SPDX-License-Identifier: Apache-2.0
"""Source-bound purecap target comparisons for the real signature interfaces."""

import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from vos import asm, boot_crypto, boot_handoff, boot_target, image, kernel_restore, receipts
from vos.cli import compiler_diff as cd

SOURCE = "firmware/crypto/signature_target.c"
MODES = ("slh", "slh-internal", "mldsa", "mldsa-internal", "mldsa-mu")
STACK_BYTES = 32768
SOURCES = ("firmware", "tools/vos", "tools/generated/dialect-table.json")


def compiler_provenance(ccomp: Path) -> tuple[dict[str, object], dict[str, str]]:
    """Bind the selected executable to its successful contained source build."""
    ccomp = ccomp.resolve()
    result_path, inputs_path = ccomp.parent / "build-result.json", ccomp.parent / "build-inputs.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    inputs = json.loads(inputs_path.read_text(encoding="utf-8"))
    if (not isinstance(result, dict) or result.get("passed") is not True
            or result.get("inputs_unchanged") is not True
            or result.get("compiler_sha256") != receipts.digest(ccomp)
            or not isinstance(result.get("revision"), str)):
        raise ValueError("signature target requires a successful source-bound compiler build")
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError("signature target compiler source manifest is absent")
    for name, identity in inputs.items():
        path = (ccomp.parent / name.removeprefix("native:")).resolve()
        if not path.is_relative_to(ccomp.parent) or not isinstance(identity, dict):
            raise ValueError("invalid compiler source manifest entry")
        expected = identity.get("sha256" if name.startswith("native:") else "canonical_sha256")
        if receipts.digest(path) != expected:
            raise ValueError(f"compiler build source changed: {name}")
    return ({"revision": result["revision"], "kind": result.get("kind"),
             "compiler_sha256": result["compiler_sha256"], "source_count": len(inputs)},
            {str(path): receipts.digest(path) for path in (result_path, inputs_path)})


def population(work: Path) -> list[boot_crypto.Case]:
    """Pinned ACVP positives with every applicable authored refusal family."""
    result: list[boot_crypto.Case] = []
    boot_crypto.fetch(boot_crypto.BASE + "README.md", work / "NIST-NOTICE.md", boot_crypto.NOTICE_SHA)
    for scheme, (directory, digest) in boot_crypto.SOURCES.items():
        data = boot_crypto.fetch(boot_crypto.BASE +
            f"gen-val/json-files/{directory}/internalProjection.json", work / (scheme + ".json"), digest)
        selected, _ = boot_crypto.cases(json.loads(data), scheme)
        for mode in MODES:
            if not mode.startswith(scheme):
                continue
            positive = next(case for case in selected if case.mode == mode and case.expected)
            result.extend([positive, *boot_crypto.refusals(positive)])
    return result


def compose(stream: str, case: boot_crypto.Case) -> str:
    """Supply all eight real arguments, with no generated expected result in C."""
    setup = ""
    objects: list[tuple[str, bytes, int]] = []
    for register, label, data in ((10, "pk", case.pk), (12, "message", case.message),
                                  (14, "context", case.context), (16, "signature", case.signature)):
        extent = 1 << max(0, (len(data) - 1).bit_length())
        objects.append((label, data, extent))
        setup += (f"        li t0, vos_crypto_{label}\n"
                  f"        csetaddr c{register}, c4, t0\n"
                  f"        li t0, {extent}\n"
                  f"        csetbounds c{register}, c{register}, t0\n"
                  "        li t0, 3\n"
                  f"        candperm c{register}, c{register}, t0\n"
                  f"        li x{register + 1}, {len(data)}\n")
    anchor = "        call    main\n"
    if cd.PROLOGUE.count(anchor) != 1:
        raise ValueError("compiler harness must have exactly one main call")
    stack_size = f"        li      t1, {cd.STACK_BYTES}\n"
    stack_space = f"        .space  {cd.STACK_BYTES}\n"
    stack_alignment = "        .align  8\n__vos_stack:\n"
    if (cd.PROLOGUE.count(stack_size) != 1 or cd.EPILOGUE.count(stack_space) != 1
            or cd.EPILOGUE.count(stack_alignment) != 1):
        raise ValueError("compiler harness stack anchors changed")
    prologue = cd.PROLOGUE.replace(stack_size, f"        li      t1, {STACK_BYTES}\n")
    epilogue = cd.EPILOGUE.replace(stack_space, f"        .space  {STACK_BYTES}\n").replace(
        stack_alignment, f"        .balign {STACK_BYTES}\n__vos_stack:\n")
    composite = prologue.replace(anchor, setup + anchor, 1) + cd.normalize(stream) + "\n" + epilogue
    for label, data, extent in objects:
        composite += f"\n        .balign {extent}\nvos_crypto_{label}:\n"
        composite += "\n".join("        .byte " + ",".join(map(str, data[i:i+32]))
                                for i in range(0, len(data), 32)) + "\n"
        if extent > len(data):
            composite += f"        .space {extent - len(data)}\n"
    return composite


def target_verdict(log: str, process_exit: int | None, expected: bool) -> tuple[bool, str, int | None, str]:
    if process_exit is None:
        return False, "no-verdict", None, "target timed out"
    markers = [line.strip() for line in log.splitlines() if "SUCCESS" in line or "FAILURE" in line]
    if len(markers) != 1:
        return False, "no-verdict", None, "target must report exactly one HTIF decision"
    match = re.fullmatch(r"FAILURE: (\d+) \(0x([0-9a-fA-F]+)\)", markers[0])
    if markers[0] != "SUCCESS" and (match is None or int(match[1]) != int(match[2], 16)):
        return False, "no-verdict", None, "malformed HTIF decision"
    verdict, code, diagnostic = cd.htif_verdict(log, process_exit)
    wanted = 0 if expected else 1
    return (verdict == ("pass" if expected else "fail") and code == wanted and process_exit == wanted,
            verdict, code, diagnostic)


def run(root: Path, out: Path, ccomp: Path, compiler_args: list[str], simulator: Path,
        build_receipt: Path, timeout: int, inst_limit: int, first: bool = False,
        jobs: int = 1) -> dict[str, Any]:
    started = time.monotonic()
    root, out, ccomp, simulator, build_receipt = (
        path.resolve() for path in (root, out, ccomp, simulator, build_receipt))
    out.mkdir(parents=True, exist_ok=True)
    if not 1 <= jobs <= 6 or timeout < 1 or inst_limit < 1:
        raise ValueError("target requires 1..6 jobs and positive timeout/instruction limits")
    sources = receipts.inputs(root, *SOURCES)
    model = receipts.inputs(root, "model")
    identities = {str(path): receipts.digest(path) for path in (ccomp, simulator, build_receipt)}
    provenance, provenance_files = compiler_provenance(ccomp)
    identities.update(provenance_files)
    compiler_files = boot_target.compiler_inputs(compiler_args)
    kernel_restore.require_build(json.loads(build_receipt.read_text(encoding="utf-8")),
                                  identities[str(simulator)], model)
    cases = population(out)
    if first:
        cases = [next(case for case in cases if case.mode == mode and case.expected) for mode in MODES]
    host = boot_crypto.build(root, out / "host")
    host_identity = receipts.digest(host)
    host_compiler = receipts.executables("gcc")
    compiled: dict[str, cd.Compiled] = {}
    compiled_records: dict[str, object] = {}
    rows: list[dict[str, object]] = []
    for mode in dict.fromkeys(case.mode for case in cases):
        scheme = 1 if mode.startswith("slh") else 2
        interface = 3 if mode.endswith("-mu") else 2 if mode.endswith("-internal") else 1
        unit = cd.compile_c([str(ccomp), *compiler_args, "-fverifiedos-typed",
            "-I" + str(root / "firmware/include"), f"-DVOS_TARGET_SCHEME={scheme}",
            f"-DVOS_TARGET_INTERFACE={interface}"], root / SOURCE, out / mode / "compiled")
        if unit.stream is None or unit.exit_code:
            raise ValueError(f"{mode} target compilation refused: {unit.said}")
        if cd.refusals(unit.stream):
            raise ValueError(f"{mode} target stream is outside the accepted dialect")
        frames = boot_target.stack_ceiling(unit.stream)
        if frames > STACK_BYTES:
            raise ValueError(f"{mode} frame sum {frames} exceeds stack {STACK_BYTES}")
        compiled[mode] = unit
        compiled_records[mode] = {"assembly_sha256": unit.stream_sha256,
            "preprocessed_sha256": unit.preprocessed.sha256, "argv": list(unit.argv),
            "sum_of_function_frames": frames}

    def execute(case: boot_crypto.Case) -> dict[str, object]:
        unit = compiled[case.mode]
        if unit.stream is None:
            raise ValueError("compiled signature stream disappeared")
        work = out / case.name
        work.mkdir(parents=True, exist_ok=True)
        host_answer = boot_crypto.invoke(host, work, case)
        if host_answer != case.expected:
            raise ValueError(f"host C disagrees with expected input: {case.name}")
        composite = compose(unit.stream, case)
        (work / "target.s").write_text(composite, encoding="utf-8", newline="\n")
        assembler = asm.Assembler(composite, case.name)
        sections, symbols, entry = assembler.assemble()
        addresses = assembler.symbols
        if (addresses["__vos_stack_top"] - addresses["__vos_stack"] != STACK_BYTES
                or addresses["__vos_stack"] % STACK_BYTES):
            raise ValueError("signature target stack allocation is not exactly aligned and bounded")
        text = next(section for section in sections if section.name == ".text")
        if text.addr + len(text.data) > asm.DATA_BASE:
            raise ValueError("target signature text reaches the data section")
        elf, log = work / "target.elf", work / "target.log"
        image.write_elf(elf, sections, symbols, entry)
        argv = [str(simulator), "--config", str(root / boot_handoff.ROT_CONFIG),
                "--inst-limit", str(inst_limit), str(elf)]
        began = time.monotonic()
        exit_code: int | None = None
        try:
            with log.open("w", encoding="utf-8") as output:
                completed = subprocess.run(argv, cwd=out, stdout=output, stderr=subprocess.STDOUT,
                                           timeout=timeout, check=False)
                exit_code = completed.returncode
        except subprocess.TimeoutExpired:
            pass
        passed, verdict, code, diagnostic = target_verdict(log.read_text(encoding="utf-8"),
                                                         exit_code, case.expected)
        return {"case": case.name, "mode": case.mode, "expected": case.expected,
            "host": host_answer, "passed": passed, "verdict": verdict, "code": code,
            "process_exit": exit_code, "diagnostic": diagnostic, "argv": argv,
            "seconds": round(time.monotonic() - began, 3), "elf_sha256": receipts.digest(elf),
            "log_sha256": receipts.digest(log), "inputs_sha256": {
                field: boot_crypto.sha(getattr(case, field)) for field in ("pk", "message", "context", "signature")}}

    order = {case.name: index for index, case in enumerate(cases)}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        positives = [case for case in cases if case.expected]
        for phase in (positives, [case for case in cases if not case.expected]):
            accepted_modes = {row["mode"] for row in rows if row["expected"] and row["passed"]}
            runnable = [case for case in phase if case.expected or case.mode in accepted_modes]
            pending = [pool.submit(execute, case) for case in runnable]
            for completed in as_completed(pending):
                rows.append(completed.result())
                rows.sort(key=lambda row: order[str(row["case"])])
                receipts.write(out / "progress.json", {"status": "incomplete", "cases": rows})
    if sources != receipts.inputs(root, *SOURCES) or model != receipts.inputs(root, "model"):
        raise ValueError("target crypto sources changed during campaign")
    if any(receipts.digest(Path(path)) != value for path, value in identities.items()):
        raise ValueError("target crypto tool or model receipt changed")
    if compiler_files != boot_target.compiler_inputs(compiler_args):
        raise ValueError("target crypto compiler configuration or headers changed")
    if compiler_provenance(ccomp) != (provenance, provenance_files):
        raise ValueError("target crypto retained compiler sources changed")
    if host_identity != receipts.digest(host) or host_compiler != receipts.executables("gcc"):
        raise ValueError("target crypto host reference changed")
    return {"passed": len(rows) == len(cases) and all(row["passed"] for row in rows), "cases": rows,
        "complete_selected_population": not first,
        "population_scope": "one ACVP positive per interface and every applicable authored refusal family",
        "all_acvp_vectors_executed": False,
        "unexecuted_cases": [case.name for case in cases if case.name not in {row["case"] for row in rows}],
        "source_sha256": sources, "model_source_sha256": model, "inputs_sha256": identities,
        "compiler_inputs_sha256": compiler_files, "compiled": compiled_records,
        "compiler_provenance": provenance,
        "host_binary_sha256": host_identity, "host_compiler": host_compiler,
        "acvp_revision": boot_crypto.REVISION, "acvp_sources": boot_crypto.SOURCES,
        "acvp_notice_sha256": boot_crypto.NOTICE_SHA,
        "stack_bytes": STACK_BYTES, "jobs": jobs, "seconds": round(time.monotonic() - started, 3),
        "scope": "real signature interfaces on the scalar RoT profile",
        "milestone_acceptance": "open", "limits": ["firmware release join separate",
            "no binary refinement, constant-time or masking claim"]}
