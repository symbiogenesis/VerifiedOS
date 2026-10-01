#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Reproduce M1.7's client image using the contained accepted purecap compiler.

Only the client assembly is exportable. All C, prover products, traces and native
receipts stay in the explicitly selected native build lane. No runtime is linked.
"""

import argparse
import dataclasses
import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from vos import asm, differential, image, receipts, trace  # noqa: E402
from vos.cli import compiler_diff  # noqa: E402

regenerate = importlib.import_module("bedrock2-lowering.regenerate")
COMPILER_SHA256 = "ecaa5ce0cd29d1099016dc1b62a93d16ecab1fe1bcb3a0e363c2697f6294ddca"
MESSAGE = b"Hello, world!\n"
MEMBER = "gallina-hello"
INPUTS = ("tools/bedrock2-lowering", "tools/opam/rupicola.lock", "tools/vos",
          "tools/generated/dialect-table.json", "model/config/verifiedos.json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8", newline="\n")


def lowering_identity() -> dict[str, str]:
    """Bind the installed prover and its complete installed Rocq library trees."""
    found = regenerate._run(["opam", "var", f"--switch={regenerate.SWITCH}", "prefix"],
                            timeout=30)
    found.check_returncode()
    prefix = Path(found.stdout.strip())
    files = [prefix / "bin" / name for name in ("coqc", "coqchk", "rocq")]
    for name in ("coq", "coq-core"):
        directory = prefix / "lib" / name
        if not directory.is_dir():
            raise ValueError(f"missing installed prover library tree: {directory}")
        for path in directory.rglob("*"):
            if path.is_symlink() and path.is_dir():
                raise ValueError(f"unsupported library directory symlink: {path}")
            if path.is_file():
                files.append(path)
    return {str(path.relative_to(prefix)): sha(path) for path in sorted(files)}


def client_c(raw: str, harness: str) -> str:
    """Retain the printed value function verbatim, excluding the unused preamble."""
    boundary = "uintptr_t hello_char(uintptr_t index) {"
    if raw.count(boundary) != 1:
        raise ValueError("ambiguous printed hello_char boundary")
    function = raw[raw.index(boundary):]
    if "_br2_" in function or "#include" in function or "memcpy" in function:
        raise ValueError("the scalar client depends on the external runtime preamble")
    return ("/* SPDX-License-Identifier: Apache-2.0 */\n"
            "typedef unsigned long uintptr_t;\n" + function + "\n" + harness)


def wrapper(stream: str) -> str:
    """Use the accepted driver setup, then check and print actual client output."""
    setup, ending = compiler_diff.PROLOGUE.split("        call    main\n", 1)
    setup += """        li      t0, hello_values
        csetaddr c10, c4, t0
        csetboundsimm c10, c10, 112
        li      t0, hello_slots
        csetaddr c11, c4, t0
        csetboundsimm c11, c11, 112
        call    main
        li      gp, 1
        bnez    a0, __vos_fail
        li      t0, hello_values
        csetaddr c12, c4, t0
        li      t0, tohost
        csetaddr c31, c4, t0
"""
    for i, byte in enumerate(MESSAGE):
        setup += (f"        li      gp, {i + 2}\n"
                  f"        ld      t2, {i * 8}(c12)\n"
                  f"        li      t1, {byte}\n"
                  "        bne     t2, t1, __vos_fail\n"
                  f"        li      t1, {compiler_diff.HTIF_PUTCHAR:#x}\n"
                  "        or      t0, t1, t2\n"
                  "        sd      t0, 0(c31)\n")
    setup += "        li      gp, 0\n        li      a0, 0\n"
    return ("# SPDX-License-Identifier: Apache-2.0\n"
            "# Generated client program: tools/bedrock2-lowering/hello.py.\n"
            "# Inputs: HelloWorld.v (Rupicola derivation), hello_harness.c.\n"
            "# No compiler source, runtime or library code is included.\n" + setup + ending
            + compiler_diff.normalize(stream) + compiler_diff.EPILOGUE
            + "        .align 3\nhello_values:\n        .space 112\n"
              "hello_slots:\n        .space 112\n")


def slot_roundtrips(records: list[str], base: int, count: int) -> list[int]:
    """Require an intact tagged reload from every declared client pointer slot.

    Writes from the whole trace invalidate overlapping candidates. Frame saves
    cannot count because only the image's hello_slots interval is accepted.
    """
    written: dict[int, str] = {}
    matched: set[int] = set()
    slots = set(range(base, base + 8 * count, 8))
    for record in records:
        parts = record.split()
        if not parts or parts[0] not in ("W", "R"):
            continue
        if trace.COMMIT_RE.fullmatch(record) is None:
            raise ValueError("malformed memory trace record")
        address, width = int(parts[1], 16), int(parts[2])
        if width <= 0 or len(parts[4]) != 2 * width:
            raise ValueError("malformed memory access width/value")
        capability = width == 8 and address in slots and parts[3] == "1"
        if parts[0] == "W":
            for slot in slots:
                if address < slot + 8 and slot < address + width:
                    written.pop(slot, None)
            if capability:
                written[address] = parts[4]
        elif capability and written.get(address) == parts[4]:
            matched.add(address)
    return sorted(matched)


def controls(text: str, stage: Path, simulator: Path) -> dict[str, object]:
    """Execute compiling defects in client values and client capability storage."""
    mutants = (
        ("wrong-gallina-character", " addi x6, x0, 72\n", " addi x6, x0, 73\n", 2),
        ("untagged-client-slot", " sc c13, 0(c14)\n", " sd x13, 0(c14)\n", 284),
        ("missing-client-store", " sc c13, 0(c14)\n", " nop\n", 284),
    )
    results: dict[str, object] = {}
    for name, old, new, expected in mutants:
        if text.count(old) != 1:
            raise ValueError(f"control site missing or ambiguous: {name}")
        source = stage / f"{name}.s"
        source.write_text(text.replace(old, new), encoding="utf-8", newline="\n")
        elf = stage / f"{name}.elf"
        asm.assemble_file(source, elf)
        ran = compiler_diff.run_image([str(simulator)], ROOT / "model/config/verifiedos.json",
                                      elf, stage)
        if ran.code != expected or ran.verdict not in ("fail", "trap") or not ran.records:
            raise ValueError(f"live target control survived or did not run: {name}: {ran}")
        results[name] = {"image_sha256": sha(elf), "assembled": True,
                         "verdict": ran.verdict, "code": ran.code,
                         "records": ran.records, "digest": ran.digest}
    return results


def native(args: argparse.Namespace) -> int:
    stage = Path(args.stage)
    if not stage.is_absolute():
        raise ValueError("stage must be absolute")
    stage = stage.resolve()
    if not stage.is_relative_to(Path("/root/build")):
        raise ValueError("stage must be an absolute directory under /root/build")
    if stage.is_relative_to(ROOT) or ROOT.is_relative_to(stage):
        raise ValueError("stage overlaps a source checkout")
    stage.mkdir(parents=True, exist_ok=True)
    (stage / "result.json").unlink(missing_ok=True)
    ccomp, simulator = Path(args.ccomp).resolve(), Path(args.simulator).resolve()
    if sha(ccomp) != COMPILER_SHA256:
        raise ValueError("compiler differs from M1.2f's accepted executable")
    inputs = receipts.inputs(ROOT, *INPUTS)
    external_paths = (ccomp, simulator, Path(args.config), Path(args.model_receipt))
    external = {str(path): sha(path) for path in external_paths}
    lowering_environment = regenerate.environment()
    lowering_files = lowering_identity()
    model = json.loads(Path(args.model_receipt).read_text(encoding="utf-8"))
    json_write(stage / "model-receipt.json", model)
    # The build receipt binds the curated model population. Other build inputs
    # include historical documentation and corpus members, which are not model bytes.
    if model["exit_code"] or model["artifacts"]["c_emulator/sail_riscv_sim"] != sha(simulator):
        raise ValueError("simulator is not the successful model receipt's executable")
    model_inputs = model["identity"]["inputs"]
    selected = {name: digest for name, digest in model_inputs.items()
                if name.startswith("model/")}
    if not selected:
        raise ValueError("model receipt carries no curated model inputs")
    current_model = receipts.inputs(ROOT, "model")
    if selected != current_model:
        raise ValueError("complete current model source population differs from built source")

    derivation = stage / "derivation"
    regenerate.stage_sources(derivation, [HERE / "HelloWorld.v"])
    (derivation / "hello_char.out").unlink(missing_ok=True)
    derived = regenerate.coqc(derivation, "HelloWorld.v")
    if derived.code or derived.assumptions != "Closed under the global context":
        raise ValueError(f"derivation refused: {derived}")
    kernel = regenerate._run(regenerate._in_switch(["coqchk", "-silent", "HelloWorld"]),
                             cwd=derivation, timeout=900)
    (stage / "kernel.log").write_text(kernel.stdout + kernel.stderr, encoding="utf-8")
    if kernel.returncode:
        raise ValueError("Rupicola client kernel check failed")
    raw_c = regenerate.extract_c(derivation, "hello_char")
    source = stage / "hello.c"
    source.write_text(client_c(raw_c.path.read_text(encoding="utf-8"),
                               (HERE / "hello_harness.c").read_text(encoding="utf-8")),
                      encoding="utf-8", newline="\n")
    config = stage / "compcert.ini"
    config.write_bytes(Path(args.config).read_bytes())
    compiled = compiler_diff.compile_c(
        [str(ccomp), "-conf", str(config), "-fverifiedos-typed"], source, stage / "compiled")
    json_write(stage / "compile.json", compiler_diff._compiled_json(compiled))
    if compiled.exit_code or compiled.stream is None:
        raise ValueError(f"compiler refused client: {compiled.said}")
    # This client must contain only its two functions. Undefined calls cannot
    # silently pull in a runtime because the in-tree assembler has no linker.
    functions = re.findall(r"(?m)^\s*\.globl\s+(\w+)\s*$", compiled.stream)
    if sorted(functions) != ["hello_char", "main"]:
        raise ValueError(f"unexpected compiler-emitted function population: {functions}")
    text = wrapper(compiled.stream)
    assembly = stage / f"{MEMBER}.s"
    assembly.write_text(text, encoding="utf-8", newline="\n")
    assembler = asm.Assembler(text, f"{MEMBER}.s")
    sections, symbols, entry = assembler.assemble()
    elf = stage / f"{MEMBER}.elf"
    image.write_elf(elf, sections, symbols, entry)
    terminal = stage / "terminal.txt"
    terminal.unlink(missing_ok=True)
    argv = [str(simulator), "--config", str(ROOT / "model/config/verifiedos.json"),
            "--trace-commit", "--inst-limit", "100000", "--terminal-log", str(terminal), str(elf)]
    ran = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=30)
    said = ran.stdout + ran.stderr
    (stage / "trace.log").write_text(said, encoding="utf-8")
    records = trace.normalize_commit(said.splitlines())
    verdict, code, detail = compiler_diff.htif_verdict(said, ran.returncode)
    slots = slot_roundtrips(records, symbols["hello_slots"][1], len(MESSAGE))
    if (verdict != "pass" or code != 0 or not records
            or len(slots) != len(MESSAGE) or terminal.read_bytes() != MESSAGE):
        raise ValueError(f"target refused: {verdict} {code} {detail}; {len(slots)} slot roundtrips")
    negative = controls(text, stage, simulator) if args.controls else {}
    if inputs != receipts.inputs(ROOT, *INPUTS):
        raise ValueError("source inputs changed during reproduction")
    if external != {str(path): sha(path) for path in external_paths}:
        raise ValueError("external producer inputs changed during reproduction")
    if lowering_environment != regenerate.environment():
        raise ValueError("lowering environment changed during reproduction")
    if lowering_files != lowering_identity():
        raise ValueError("installed lowering libraries or prover changed during reproduction")
    if selected != receipts.inputs(ROOT, "model"):
        raise ValueError("model inputs changed during reproduction")
    report = {"schema": "verifiedos-gallina-hello/1", "inputs": inputs,
              "external_inputs": external, "lowering_environment": lowering_environment,
              "lowering_files": lowering_files,
              "compiler_sha256": sha(ccomp), "simulator_sha256": sha(simulator),
              "config_sha256": sha(config), "model_receipt_sha256": sha(Path(args.model_receipt)),
              "model_inputs": selected, "derivation": dataclasses.asdict(derived),
              "kernel_exit": kernel.returncode, "c_sha256": sha(raw_c.path),
              "client_c_sha256": sha(source), "assembly_sha256": sha(assembly),
              "image_sha256": sha(elf), "image_bytes": elf.stat().st_size,
              "slot_addresses": slots, "trace_sha256": sha(stage / "trace.log"),
              "controls": negative,
              "member": {"name": MEMBER, "source": assembly.name,
                         "checks": differential.count_checks(text), "records": len(records),
                         "digest": trace.digest(records)},
              "verdict": verdict, "code": code, "output_hex": terminal.read_bytes().hex()}
    if args.check:
        tracked = ROOT / "corpus" / assembly.name
        if tracked.read_bytes() != assembly.read_bytes():
            raise ValueError("tracked client assembly differs from reproduction")
    if args.export:
        (ROOT / "corpus" / assembly.name).write_bytes(assembly.read_bytes())
    json_write(stage / "result.json", report)
    print(json.dumps({key: report[key] for key in ("member", "image_sha256", "assembly_sha256",
                                                 "verdict", "code")}, indent=2))
    return 0


def main() -> int:
    if os.name == "nt":
        argv = [regenerate._guest_path(arg) if regenerate.WINDOWS_PATH.match(arg) else arg
                for arg in sys.argv[1:]]
        return subprocess.run(["wsl", "-u", "root", "-e", "python3",
                               regenerate._guest_path(str(Path(__file__).resolve())), *argv],
                              check=False).returncode
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True)
    parser.add_argument("--ccomp", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--simulator", required=True)
    parser.add_argument("--model-receipt", required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--controls", action="store_true")
    args = parser.parse_args()
    try:
        return native(args)
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"hello-world: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
