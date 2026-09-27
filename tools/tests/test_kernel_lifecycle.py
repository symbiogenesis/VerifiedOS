# SPDX-License-Identifier: Apache-2.0
"""Finite lifecycle wire and trusted transition controls; target join is separate."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import toolenv
from vos.corpus import find_root


def lifecycle_controls() -> None:
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    ensure(cc is not None, "native lifecycle tests require a C compiler")
    if cc is None:
        raise RuntimeError("no native C compiler")
    root = find_root()
    work = toolenv.environment(root, sys.platform).parent / "kernel-lifecycle-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="lifecycle-", dir=work) as directory:
        executable = Path(directory) / "lifecycle"
        sources = ("kernel/src/effects.c", "kernel/src/context.c",
                   "kernel/src/lifecycle.c", "supervisor/src/supervisor.c",
                   "kernel/test/lifecycle.c")
        compiled = subprocess.run([cc, "-std=c11", "-O1", "-Wall", "-Wextra", "-Werror",
            "-pedantic", "-DVOS_HOST_MODEL", "-DVOS_EFFECTS_TYPED", "-DVOS_KERNEL_EFFECT_UNITS=3",
            "-I" + str(root / "kernel/include"), "-I" + str(root / "supervisor/include"),
            *(str(root / name) for name in sources), "-o", str(executable)],
            capture_output=True, text=True, check=False)
        ensure(compiled.returncode == 0, compiled.stderr)
        result = subprocess.run([str(executable)], capture_output=True, text=True,
                                timeout=30, check=False)
        ensure(result.returncode == 0, result.stderr)
        ensure("ok lifecycle scalar request controls" in result.stderr,
               "lifecycle controls did not reach their success verdict")


def cases() -> list[Case]:
    return [Case("bounded lifecycle wire decoding and publication controls",
                 lifecycle_controls, lane="guest")]
