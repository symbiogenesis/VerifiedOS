# SPDX-License-Identifier: Apache-2.0
"""Actual Sail delivery, deferral, and fail-stop through assembled instructions."""

import hashlib
import json
import re
import subprocess
from pathlib import Path

from tests.harness import Case, ensure
from vos import asm, env, jsonc, trace
from vos.cli import compiler_diff as cd
from vos.cli.model import verified_build


def _timer_address(root: Path, profile: Path) -> int:
    config = json.loads(jsonc.strip_comments(profile.read_text(encoding="utf-8")))
    platform = (root / "model/model/sys/platform.sail").read_text(encoding="utf-8")
    match = re.search(r"let MTIMECMP_BASE\s*:\s*physaddrbits\s*=\s*zero_extend\(0x([0-9a-fA-F]+)\)",
                      platform)
    if match is None:
        raise AssertionError("the timer door no longer has its checked literal form")
    return int(config["platform"]["clint"]["base"]) + int(match.group(1), 16)


def _programs(timer: int) -> dict[str, str]:
    setup = f"""
        .text
main:
        cmove c18, cra
        li x19, 0
        li x20, 0
        li t0, {timer}
        csetaddr c21, c4, t0
        la c9, timer_handler
        cspecialrw cnull, mtcc, c9
        csrw mie, zero
        csrw mstatus, zero
"""
    done = """
        li a0, 0
        cmove cra, c18
        ret
failed:
        li a0, 1
        cmove cra, c18
        ret
"""
    timer_handler = """
timer_handler:
        csrr t0, mcause
        li t1, 0x8000000000000007
        bne t0, t1, failed
        addi x19, x19, 1
        mret
"""
    unmaskable = setup + """
first_arm:
        sd zero, 0(c21)
after_first_arm:
        addi x20, x20, 1
        addi x20, x20, 1
        addi x20, x20, 1
        li t0, 1
        bne x19, t0, failed
second_arm:
        sd zero, 0(c21)
after_second_arm:
        li t0, 2
        bne x19, t0, failed
        li t0, 3
        bne x20, t0, failed
""" + done + timer_handler
    deferred = setup + """
sync_call:
        ecall
after_sync:
        li t0, 1
        bne x19, t0, failed
        li t0, 7
        bne x20, t0, failed
""" + done + """
timer_handler:
        csrr t0, mcause
        li t1, 11
        bne t0, t1, boundary_handler
arm_inside_sync:
        sd zero, 0(c21)
        addi x20, x20, 7
        cspecialrw c6, mepcc, cnull
        cincoffsetimm c6, c6, 4
        cspecialrw cnull, mepcc, c6
sync_return:
        mret
boundary_handler:
        li t1, 0x8000000000000007
        bne t0, t1, failed
        addi x19, x19, 1
        mret
"""
    double_fault = setup + """
        ecall
must_not_resume:
        li a0, 0
        cmove cra, c18
        ret
timer_handler:
second_fault:
        .word 0xffffffff
must_not_issue:
        addi x20, x20, 1
"""
    return {"unmaskable-and-rearm": unmaskable,
            "pending-until-mret": deferred, "second-trap-fail-stop": double_fault}


def _execution_contract() -> None:
    environment = env.load()
    build_record = verified_build(environment)
    test_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    timer = _timer_address(environment.root, environment.profile)
    directory = environment.lane_root / "trap-boundary-controls"
    logs = environment.log_root / "trap-boundary-controls"
    directory.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for name, source in _programs(timer).items():
        assembly = directory / f"{name}.s"
        elf = directory / f"{name}.elf"
        assembly.write_text(cd.compose(source), encoding="utf-8", newline="\n")
        asm.assemble_file(assembly, elf)
        _, symbols, _ = asm.Assembler(cd.compose(source), name).assemble()
        argv = [str(environment.simulator), "--config", str(environment.profile),
                "--trace-commit", "--inst-limit", "1000", str(elf)]
        ran = subprocess.run(argv, cwd=directory, capture_output=True, text=True,
                             timeout=30, check=False)
        raw = ran.stdout + ran.stderr
        log = logs / f"{name}.log"
        log.write_text(raw, encoding="utf-8", newline="\n")
        records = trace.normalize_commit(raw.splitlines())
        traps = [r for r in records if r.startswith("T ")]
        # Interrupt records carry an I row with a zero word at the saved PC;
        # that row is not a fetched or executed ordinary instruction.
        issued = [r for r in records if r.startswith("I ") and r.split()[2] != "00000000"]
        pcs = [int(r.split()[1], 16) for r in issued]
        verdict, code, detail = cd.htif_verdict(raw, ran.returncode)
        if name == "unmaskable-and-rearm":
            ensure((verdict, code) == ("pass", 0), detail)
            ensure(traps == ["T 1 7", "T 1 7"], "each comparator programming delivers exactly once")
            for label in ("first_arm", "second_arm", "after_first_arm", "after_second_arm"):
                ensure(pcs.count(symbols[label][1]) == 1, f"{label}: instruction omitted or replayed")
        elif name == "pending-until-mret":
            ensure((verdict, code) == ("pass", 0), detail)
            ensure(traps == ["T 0 11", "T 1 7"], "timer must follow the completed synchronous path")
            ensure(pcs.count(symbols["arm_inside_sync"][1]) == 1, "completed timer store replayed")
            timer_record = records.index("T 1 7")
            completed = f'I {symbols["sync_return"][1]:016X} '
            resumed = f'I {symbols["after_sync"][1]:016X} '
            ensure(any(r.startswith(completed) for r in records[:timer_record]),
                   "timer entered before synchronous mret")
            ensure(not any(r.startswith(resumed) and r in issued for r in records[:timer_record]),
                   "predecessor issued an ordinary instruction before the pending timer")
        else:
            ensure("Fail-stop: synchronous fault on a live trap path" in raw,
                   "second synchronous fault must latch fail-stop")
            ensure("RoT watchdog bite asserted the die reset" in raw,
                   "fail-stop must service the RoT bite without an optional slow clock")
            ensure(verdict != "pass" and traps == ["T 0 11"], "second trap was vectored or resumed")
            ensure(sum(r.startswith("S 31 ") for r in records) == 1, "MEPCC overwritten by second trap")
            for csr in ("342", "343"):
                ensure(sum(r.startswith(f"C {csr} ") for r in records) == 1,
                       f"trap CSR {csr} overwritten")
            ensure(symbols["must_not_resume"][1] not in pcs and symbols["must_not_issue"][1] not in pcs,
                   "a stopped core issued a successor instruction")
        results.append({"name": name, "argv": argv, "exit": ran.returncode,
                        "verdict": verdict, "code": code, "traps": traps,
                        "elf_sha256": hashlib.sha256(elf.read_bytes()).hexdigest(),
                        "trace_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
                        "trace_digest": trace.digest(records), "passed": True})
    ensure(verified_build(environment) == build_record, "model inputs changed during the campaign")
    ensure(hashlib.sha256(Path(__file__).read_bytes()).hexdigest() == test_sha256,
           "test inputs changed during the campaign")
    result = {"passed": True, "cases": results, "verified_build": build_record,
              "test_sha256": test_sha256,
              "profile_sha256": hashlib.sha256(environment.profile.read_bytes()).hexdigest()}
    (directory / "result.json").write_text(json.dumps(result, indent=2) + "\n",
                                           encoding="utf-8", newline="\n")


def cases() -> list[Case]:
    return [Case("timer-deferral-and-second-trap-on-sail", _execution_contract,
                 slow=True, lane="toolchain")]
