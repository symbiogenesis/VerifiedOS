# SPDX-License-Identifier: Apache-2.0
"""Focused fixed-holder checks; target traces supply architectural evidence."""

import shutil
import subprocess
import sys
import tempfile

from tests.harness import Case, ensure
from vos import asm, copy_loan, toolenv
from vos.corpus import find_root


def emitters() -> None:
    holders = (copy_loan.Holder("borrower_stack", 8192),
               copy_loan.Holder("borrower_saved", 512),
               copy_loan.Holder("borrower_frames", 512))
    for defect in ("none", "missing-stack", "missing-saved", "missing-frames"):
        source = (".text\n" + copy_loan.emit_redeem(slot_base="grant_slots", ring_base="ring")
                  + copy_loan.emit_cleanup(holders, defect=defect)
                  + "vos_copy_loan_begin:\n ret\nvos_copy_loan_finish:\n ret\n.data\n"
                  + "grant_slots:\n .space 512\nring:\n .space 524288\n"
                  + "".join(f"{holder.label}:\n .space {holder.size}\n" for holder in holders))
        assembler = asm.Assembler(source, defect)
        assembler.assemble()
        ensure(assembler.symbols["vos_copy_loan_cleanup"] > assembler.symbols["vos_copy_loan_redeem"],
               "missing actual boundary bodies")
    for size in (0, 127, 129, 65537):
        try:
            copy_loan.Holder("holder", size).check()
        except ValueError:
            continue
        raise AssertionError("unbounded or unrepresentable holder accepted")


def native_guards() -> None:
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if cc is None:
        raise RuntimeError("native loan controls require a C compiler")
    root = find_root()
    work = toolenv.environment(root, sys.platform).parent / "copy-loan-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="copy-loan-", dir=work) as directory:
        executable = directory + "/loan"
        result = subprocess.run([cc, "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
            "-pedantic", "-DVOS_HOST_MODEL", "-fsanitize=address,undefined",
            "-I" + str(root / "kernel/include"), "-I" + str(root / "supervisor/include"),
            str(root / "kernel/src/copy_loan.c"), str(root / "kernel/test/copy_loan.c"),
            "-o", executable], capture_output=True, text=True, check=False)
        ensure(result.returncode == 0, result.stderr)
        result = subprocess.run([executable], capture_output=True, text=True, timeout=30, check=False)
        ensure(result.returncode == 0 and "ok copy loan " in result.stderr, result.stderr)


def empty_trace() -> None:
    ensure(not any(copy_loan.observations([], {}).values()), "empty trace manufactured holder evidence")


def cases() -> list[Case]:
    return [Case("actual grant and complete holder cleanup emitters assemble", emitters),
            Case("missing loan trace provides no holder evidence", empty_trace),
            Case("loan remains outstanding on every incomplete observation", native_guards, lane="guest")]
