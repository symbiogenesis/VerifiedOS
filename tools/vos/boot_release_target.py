# SPDX-License-Identifier: Apache-2.0
"""Execute the release C on the RoT hart and boot its actual output bytes."""

import hashlib
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from vos import asm, boot_crypto_target, boot_target, config, image, kernel_restore, receipts
from vos import boot_handoff as bh
from vos.cli import compiler_diff as cd

SOURCE = "firmware/harness/rot_release_target.c"
METADATA_BYTES = 128
SOURCE_INPUTS = ("firmware", "tools/vos", "tools/generated/dialect-table.json")


def _word(data: bytes, at: int) -> int:
    return int.from_bytes(data[at:at + 8], "little")


def compose(root: Path, stream: str, boot: bytes, public: bytes, floor: int) -> str:
    """Read RoT devices, then bind the four arguments to bounded capabilities."""
    lay = bh.layout(root)
    output_bytes = METADATA_BYTES + lay["HANDOFF_BYTES"] + lay["BRINGUP_MMODE_REGION_BYTES"]
    image_extent = 1 << (len(boot) - 1).bit_length()
    output_extent = 1 << (output_bytes - 1).bit_length()
    # These door addresses are taken from the same composition the RoT runs.
    doors: list[tuple[str, int, int]] = []
    for name, length in (("otp", 8), ("trng", 40), ("monotonic_counters", 48), ("watchdog", 56)):
        address = config.integer(root / bh.ROT_CONFIG, "platform", name, "base")
        size = config.integer(root / bh.ROT_CONFIG, "platform", name, "size")
        if address is None or size is None or address % 8 or size < length:
            raise ValueError(f"RoT composition lacks the {name} register aperture")
        doors.append((name, address, length))
    arguments = [("vos_public_key", len(public), 3), ("vos_boot_image", image_extent, 3),
                 ("begin_signature", output_extent, 7)]
    arguments.append(("vos_parameters", 48, 3))
    setup = ""
    for reg, (_, address, length) in enumerate(doors, 20):
        setup += (f"        li t0, {address}\n        csetaddr c{reg}, c4, t0\n"
                  f"        li t0, {length}\n        csetbounds c{reg}, c{reg}, t0\n")
    setup += ("        li t0, vos_parameters\n        csetaddr c24, c4, t0\n"
              "        ld t0, 0(c20)\n        sd t0, 16(c24)\n"
              "        sd zero, 32(c21)\n        ld t0, 8(c21)\n        sd t0, 24(c24)\n"
              f"        li t1, {floor}\n__vos_floor_advance:\n"
              "        beqz t1, __vos_floor_read\n        sd zero, 32(c22)\n"
              "        addi t1, t1, -1\n        j __vos_floor_advance\n__vos_floor_read:\n"
              "        ld t0, 0(c22)\n        sd t0, 32(c24)\n"
              "        ld t0, 24(c24)\n        srli t0, t0, 32\n        andi t0, t0, 3\n"
              "        li t1, 1\n        bne t0, t1, __vos_entropy_refusal\n"
              "        sd zero, 48(c23)\n__vos_entropy_refusal:\n"
              "        ld t0, 0(c23)\n        sd t0, 40(c24)\n")
    for reg, (address, length, permissions) in enumerate(arguments, 10):
        setup += (f"        li t0, {address}\n        csetaddr c{reg}, c4, t0\n"
                  f"        li t0, {length}\n        csetbounds c{reg}, c{reg}, t0\n"
                  f"        li t0, {permissions}\n        candperm c{reg}, c{reg}, t0\n")
    anchor = "        call    main\n"
    if cd.PROLOGUE.count(anchor) != 1:
        raise ValueError("target prologue no longer has one main call")
    watchdog_base = doors[-1][1]
    after = (f"        li t0, {watchdog_base}\n        csetaddr c23, c4, t0\n"
             "        li t0, begin_signature\n        csetaddr c24, c4, t0\n"
             "        ld t0, 8(c23)\n        sd t0, 80(c24)\n"
             "        ld t1, 24(c23)\n        sd t1, 88(c24)\n"
             "        bnez t1, __vos_watchdog_failed\n"
             "        ld t1, 40(c23)\n        bltu t1, t0, __vos_watchdog_failed\n"
             "        ld t1, 32(c23)\n        bltu t0, t1, __vos_watchdog_done\n"
             "        ld t1, 0(c23)\n        sd t1, 16(c23)\n"
             "        ld t1, 24(c23)\n        beqz t1, __vos_watchdog_done\n"
             "__vos_watchdog_failed:\n        li a0, 30\n__vos_watchdog_done:\n")
    result = cd.compose(stream, cd.PROLOGUE.replace(anchor, setup + anchor + after, 1))
    for label, blob, capacity in (("vos_public_key", public, len(public)),
                                  ("vos_boot_image", boot, image_extent)):
        result += f"\n        .balign {capacity}\n{label}:\n"
        result += "\n".join("        .byte " + ",".join(str(b) for b in blob[i:i + 32])
                            for i in range(0, len(blob), 32)) + "\n"
        result += f"        .space {capacity - len(blob)}\n"
    result += (f"        .balign 8\nvos_parameters:\n"
               f"        .dword {len(boot)}, 0, 0, 0, 0, 0\n"
               f"        .balign {output_extent}\nbegin_signature:\n"
               f"        .space {output_bytes}\nend_signature:\n"
               f"        .space {output_extent - output_bytes}\n")
    return result


def read_output(path: Path, expected_bytes: int) -> bytes:
    """Decode the emulator's eight-byte little-endian signature words strictly."""
    words = path.read_text(encoding="utf-8").split()
    if len(words) * 8 != expected_bytes or any(re.fullmatch(r"[0-9a-fA-F]{16}", word) is None for word in words):
        raise ValueError("target output has an incorrect signature extent")
    try:
        return b"".join(int(word, 16).to_bytes(8, "little") for word in words)
    except ValueError as exc:
        raise ValueError("target output contains an invalid signature word") from exc


def completed_attempt(log: str, process_exit: int | None) -> bool:
    """Only one exact HTIF completion authorizes reading the exported verdict."""
    outcomes = [line.strip() for line in log.splitlines()
                if line.strip().startswith(("SUCCESS", "FAILURE"))]
    return process_exit == 0 and outcomes == ["SUCCESS"]


def capture_findings(captured: bytes, lay: bh.Layout, expected: int, floor: int,
                     oracle: dict[str, str], host_window: bytes | None = None,
                     host_record: bytes | None = None) -> list[str]:
    """Decide the target output independently of HTIF's completion status."""
    problems: list[str] = []
    released = int(expected == 0)
    wanted_log = bytes((1, 2, 3, 5)) if released else bytes((1, 2, 3))
    if oracle.get("code") != str(expected) or oracle.get("released") != str(released):
        problems.append("host oracle verdict or release count disagrees")
    if oracle.get("log") != ",".join(str(item) for item in wanted_log):
        problems.append("host oracle measured-item order disagrees")
    if _word(captured, 0) != expected or _word(captured, 8) != released:
        problems.append("target verdict or release-hook count disagrees")
    if _word(captured, 56) != len(wanted_log) or captured[64:64 + len(wanted_log)] != wanted_log:
        problems.append("target measured-item order disagrees")
    if ((_word(captured, 16), _word(captured, 32), _word(captured, 40)) != (3, floor, 0)
            or (_word(captured, 24) >> 32) & 3 != 1
            or not _word(captured, 48) or _word(captured, 88)):
        problems.append("target device inputs or watchdog startup disagree")
    record = captured[METADATA_BYTES:METADATA_BYTES + lay["HANDOFF_BYTES"]]
    window = captured[METADATA_BYTES + lay["HANDOFF_BYTES"]:]
    if not released:
        if oracle.get("image_window_zero") != "1" or oracle.get("handoff_window_untouched") != "1":
            problems.append("host refusal did not erase its image and preserve its handoff")
        host_window = bytes(lay["BRINGUP_MMODE_REGION_BYTES"])
        host_record = bytes([0x5a]) * lay["HANDOFF_BYTES"]
    if host_window is None or host_record is None or record != host_record or window != host_window:
        problems.append("target-written handoff or placed window differs from required output")
    return problems


def run(root: Path, out: Path, ccomp: Path, ccomp_args: list[str], simulator: Path,
        build_receipt: Path, boot_image: Path, public_key: Path,
        timeout: int = 1200, inst_limit: int = 1_500_000_000) -> dict[str, object]:
    """Compare actual target placement and refusals with the existing host oracle."""
    started = time.monotonic()
    paths = (root, out, ccomp, simulator, build_receipt, boot_image, public_key)
    root, out, ccomp, simulator, build_receipt, boot_image, public_key = (p.resolve() for p in paths)
    out.mkdir(parents=True, exist_ok=True)
    sources = receipts.inputs(root, *SOURCE_INPUTS)
    model_sources = receipts.inputs(root, "model")
    identities = {str(p): receipts.digest(p) for p in (ccomp, simulator, build_receipt, boot_image, public_key)}
    provenance, provenance_files = boot_crypto_target.compiler_provenance(ccomp)
    identities.update(provenance_files)
    compiler_files = boot_target.compiler_inputs(ccomp_args)
    kernel_restore.require_build(json.loads(build_receipt.read_text(encoding="utf-8")),
                                  identities[str(simulator)], model_sources)
    lay = bh.layout(root)
    built = bh.assemble_mmode(root)
    boot, public = boot_image.read_bytes(), public_key.read_bytes()
    if len(public) != lay["BOOT_PUBLIC_KEY_BYTES"]:
        raise ValueError("release target requires an exact raw SLH public key")
    if len(boot) < lay["BOOT_HEADER_BYTES"] or boot[lay["BOOT_HEADER_BYTES"]:] != built.payload:
        raise ValueError("release target input must sign the current handoff fixture payload")
    floor = int.from_bytes(boot[16:24], "little")
    if not 1 <= floor <= 16:
        raise ValueError("release target floor must be between 1 and 16 advance operations")
    host_compiler = receipts.executables("cc")
    host, _ = bh.compile_rot_stage(root, out)
    host_digest = receipts.digest(host)
    compiled = cd.compile_c([str(ccomp), *ccomp_args, "-fverifiedos-typed",
                             "-I" + str(root / "firmware/include")], root / SOURCE, out / "compiled")
    if compiled.stream is None or compiled.exit_code or cd.refusals(compiled.stream):
        raise ValueError(f"RoT release target compilation refused: {compiled.said}")
    stream = compiled.stream
    frames = boot_target.stack_ceiling(stream)
    if frames > cd.STACK_BYTES:
        raise ValueError("release target frame sum exceeds its bounded stack")
    cases = (("valid", boot, public, 0),
             ("bad-magic", bh.flip(boot, 0), public, 4),
             ("below-floor", bh.put_word(boot, 16, floor - 1), public, 8),
             ("corrupt-signature", bh.flip(boot, lay["BOOT_HDR_SIGNATURE"]), public, 10),
             ("wrong-root", boot, bh.flip(public, 0), 10),
             ("corrupt-payload", bh.flip(boot, lay["BOOT_HEADER_BYTES"]), public, 12))
    rows: list[dict[str, object]] = []
    output_bytes = METADATA_BYTES + lay["HANDOFF_BYTES"] + lay["BRINGUP_MMODE_REGION_BYTES"]
    def run_case(case: tuple[str, bytes, bytes, int]) -> dict[str, object]:
        name, candidate, key, expected = case
        directory = out / name
        directory.mkdir(exist_ok=True)
        candidate_path = directory / "image.bin"
        candidate_path.write_bytes(candidate)
        oracle = bh.rot_stage(host, candidate_path, bh.RotInputs(3, 1, 0, floor), "slh256s",
                              directory, roots={"production": key})
        composite = compose(root, stream, candidate, key, floor)
        (directory / "target.s").write_text(composite, encoding="utf-8", newline="\n")
        sections, symbols, entry = asm.Assembler(composite, name).assemble()
        text = next(section for section in sections if section.name == ".text")
        if text.addr + len(text.data) > asm.DATA_BASE:
            raise ValueError("release target text overlaps its data")
        elf = directory / "target.elf"
        image.write_elf(elf, sections, symbols, entry)
        signature = directory / "target.signature"
        signature.unlink(missing_ok=True)
        argv = [str(simulator), "--config", str(root / bh.ROT_CONFIG),
                "--inst-limit", str(inst_limit), "--test-signature", str(signature),
                "--signature-granularity", "8", str(elf)]
        log = directory / "target.log"
        began = time.monotonic()
        process_exit: int | None = None
        try:
            with log.open("w", encoding="utf-8") as output:
                completed = subprocess.run(argv, cwd=out, stdout=output, stderr=subprocess.STDOUT,
                                           timeout=timeout, check=False)
            process_exit = completed.returncode
            verdict, code, diagnostic = cd.htif_verdict(log.read_text(encoding="utf-8"), process_exit)
        except subprocess.TimeoutExpired:
            verdict, code, diagnostic = "no-verdict", None, f"target exceeded {timeout}s"
        problems = []
        if not completed_attempt(log.read_text(encoding="utf-8"), process_exit):
            problems.append(f"target attempt did not complete with one HTIF SUCCESS: {diagnostic}")
        row: dict[str, object] = {"case": name, "expected": expected, "verdict": verdict,
                                 "code": code, "process_exit": process_exit, "argv": argv,
                                 "seconds": round(time.monotonic() - began, 3), "problems": problems,
                                 "elf_sha256": receipts.digest(elf), "log_sha256": receipts.digest(log),
                                 "assembly_sha256": receipts.digest(directory / "target.s")}
        if not problems:
            captured = read_output(signature, output_bytes)
            record = captured[METADATA_BYTES:METADATA_BYTES + lay["HANDOFF_BYTES"]]
            window = captured[METADATA_BYTES + lay["HANDOFF_BYTES"]:]
            host_window = (directory / "sram.bin").read_bytes() if expected == 0 else None
            host_record = (directory / "handoff.bin").read_bytes() if expected == 0 else None
            problems += capture_findings(captured, lay, expected, floor, oracle, host_window, host_record)
            row["target_output_sha256"] = hashlib.sha256(captured).hexdigest()
            row["boot_verdict"] = _word(captured, 0)
            row["host_verdict"] = oracle.get("verdict")
            if expected == 0 and not problems:
                placed = directory / "placed.elf"
                bh.placed_elf(lay, window, record, built.symbols["tohost"], placed)
                main = bh.emulate(simulator, root / bh.MAIN_CONFIG, placed, 60,
                                  watch={"kernel_entry": built.symbols["kernel_entry"]})
                row["main_die"] = {"verdict": main.verdict, "first_pc": main.first_pc,
                                    "kernel_entry": main.reached.get("kernel_entry"), "retired": main.retired}
                if main.verdict != "success" or main.first_pc != lay["BRINGUP_MMODE_LOAD_BASE"] or not main.reached.get("kernel_entry"):
                    problems.append("main die did not execute the released handoff through kernel entry")
        row["passed"] = not problems
        return row

    rows.append(run_case(cases[0]))
    receipts.write(out / "progress.json", {"status": "incomplete", "cases": rows})
    if rows[0]["passed"]:
        # Each case has private outputs and consumes the same frozen compiler
        # stream. The real positive must complete before any negative starts.
        with ThreadPoolExecutor(max_workers=3) as workers:
            for row in workers.map(run_case, cases[1:]):
                rows.append(row)
                receipts.write(out / "progress.json", {"status": "incomplete", "cases": rows})
    if sources != receipts.inputs(root, *SOURCE_INPUTS) or model_sources != receipts.inputs(root, "model"):
        raise ValueError("release target sources changed during execution")
    if any(receipts.digest(Path(path)) != digest for path, digest in identities.items()):
        raise ValueError("release target tool or input bytes changed")
    if boot_crypto_target.compiler_provenance(ccomp) != (provenance, provenance_files):
        raise ValueError("release target retained compiler sources changed")
    if compiler_files != boot_target.compiler_inputs(ccomp_args) or host_compiler != receipts.executables("cc") or host_digest != receipts.digest(host):
        raise ValueError("release target compiler or host oracle changed")
    return {"passed": len(rows) == len(cases) and all(row["passed"] for row in rows),
            "cases": rows, "unexecuted_cases": [name for name, *_ in cases[len(rows):]],
            "milestone_acceptance": "open", "scope": "RoT target release into existing M-mode handoff fixture",
            "open_joins": ["ROM runtime measurement", "A/B boot counting", "separately signed kernel and item 6",
                           "reset-table sequencing", "watchdog asynchronous timeout campaign", "complete roster"],
            "source_sha256": sources, "model_source_sha256": model_sources, "inputs_sha256": identities,
            "compiler_inputs_sha256": compiler_files, "compile_argv": list(compiled.argv),
            "compiler_provenance": provenance,
            "preprocessed_sha256": compiled.preprocessed.sha256, "assembly_sha256": compiled.stream_sha256,
            "sum_of_function_frames": frames, "host_binary_sha256": host_digest,
            "host_compiler": host_compiler,
            "seconds": round(time.monotonic() - started, 3)}
