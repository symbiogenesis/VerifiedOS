# SPDX-License-Identifier: Apache-2.0
"""Finite executive clock controls against authored native C and target wiring."""

import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import kernel_target, toolenv
from vos.cli import kernel


def native_clock_controls() -> None:
    root = TOOLS.parent
    compiler = kernel.c_compiler()
    ensure(compiler is not None, "clock controls require a native C compiler")
    if compiler is None:
        return
    work = toolenv.environment(root, sys.platform).parent / "kernel-clock-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="clock-", dir=work) as temporary:
        scratch = Path(temporary)
        binary = scratch / "clock"
        built = subprocess.run(
            [compiler, "-std=c17", "-Wall", "-Wextra", "-Werror", "-Wstrict-prototypes",
             "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
             "-I", str(root / "kernel/include"), "-I", str(root / "firmware/include"),
             str(root / "kernel/test/target_unit.c"), str(root / "kernel/test/clock.c"),
             "-o", str(binary)], capture_output=True, text=True, check=False, timeout=60)
        ensure(built.returncode == 0, f"clock compile failed: {built.stdout}{built.stderr}")
        ran = subprocess.run([str(binary)], capture_output=True, text=True,
                             check=False, timeout=60)
        ensure(ran.returncode == 0, f"clock controls failed: {ran.stdout}{ran.stderr}")
        ensure("executive clock controls passed" in ran.stdout, ran.stdout)
        ensure(not ran.stderr, f"clock sanitizer diagnostics: {ran.stderr}")
        # The negative controls must compile and execute: refusal by the C
        # compiler is a stillborn candidate, never a detected clock defect.
        sources = {name: (root / f"kernel/src/{name}.c").read_text(encoding="utf-8")
                   for name in ("context", "executive", "partition", "handoff", "target")}
        offset = next(mutant for mutant in kernel.C_MUTANTS
                      if mutant.name == "release ignoring the slot's offset")
        mutations = (
            ("offset", "executive", offset.old, offset.new),
            ("product", "executive",
             "if (e->frame_index > (UINT64_MAX - origin) / f->major_frame)", "if (0)"),
            ("epoch", "target", "epoch > UINT64_MAX - release", "0"),
            ("duration", "target", "if (duration > UINT64_MAX - absolute)", "if (0)"),
        )
        for name, owner, before, after in mutations:
            ensure(sources[owner].count(before) == 1, f"clock mutant anchor drift: {name}")
            mutant = scratch / f"{name}.c"
            mutant.write_text("\n".join(text.replace(before, after) if unit == owner else text
                                      for unit, text in sources.items()), encoding="utf-8")
            candidate = scratch / name
            built = subprocess.run(
                [compiler, "-std=c17", "-Wall", "-Wextra", "-Werror", "-Wstrict-prototypes",
                 "-I", str(root / "kernel/include"), "-I", str(root / "firmware/include"),
                 str(mutant), str(root / "kernel/test/clock.c"), "-o", str(candidate)],
                capture_output=True, text=True, check=False, timeout=60)
            ensure(built.returncode == 0,
                   f"clock mutant {name} stillborn: {built.stdout}{built.stderr}")
            ran = subprocess.run([str(candidate)], capture_output=True, text=True,
                                 check=False, timeout=60)
            ensure(ran.returncode == 1 and "clock control failed" in ran.stderr,
                   f"clock mutant {name} survived: {ran.stdout}{ran.stderr}")


def target_checks_clock_before_timer_write() -> None:
    source = kernel_target.consumer_source("COMPILED-C", 1, ((4096, 8), (8192, 8)), (12288, 1))
    advance = source.index("    call vos_target_advance")
    select = source.index("kernel_select:", advance)
    ensure("    beqz x10, kernel_fail" in source[advance:select],
           "failed cursor advancement must stop selection")
    release = source.index("    call vos_target_release")
    load = source.index("    ld x6, 0(c19)", release)
    write = source.index("    sd x6, 0(c20)", load)
    ensure("    beqz x10, kernel_fail" in source[release:load],
           "failed deadline calculation must stop before loading the comparator output")
    ensure("timer_deadline" in source[release:load] and write > load,
           "timer comparator must consume only the checked deadline output")
    ensure("    add x6, x5, x10" not in source and "    add x6, x6, x5" not in source,
           "target adapter must not reconstruct an unchecked deadline")


def cases() -> list[Case]:
    return [Case("native executive clock controls", native_clock_controls, lane="guest"),
            Case("target refuses bad clocks before comparator write", target_checks_clock_before_timer_write)]
