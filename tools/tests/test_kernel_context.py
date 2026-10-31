# SPDX-License-Identifier: Apache-2.0
"""Native context images preserve their inputs when the output aliases either one."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import toolenv


def context_alias_controls() -> None:
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    ensure(compiler is not None, "native context controls require a C compiler")
    if compiler is None:
        return
    root = TOOLS.parent
    work = toolenv.environment(root, sys.platform).parent / "kernel-context-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="context-", dir=work) as directory:
        executable = Path(directory) / "context"
        built = subprocess.run(
            [compiler, "-std=c17", "-O1", "-Wall", "-Wextra",
             "-Wstrict-prototypes", "-Werror", "-pedantic",
             "-DVOS_HOST_MODEL", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
             "-I", str(root / "kernel/include"), str(root / "kernel/src/context.c"),
             str(root / "kernel/test/context.c"), "-o", str(executable)],
            cwd=directory, capture_output=True, text=True, check=False, timeout=60)
        ensure(built.returncode == 0, f"context compile failed: {built.stdout}{built.stderr}")
        ran = subprocess.run([str(executable)], capture_output=True, text=True,
                             cwd=directory, check=False, timeout=30)
        ensure(ran.returncode == 0, f"context controls failed: {ran.stdout}{ran.stderr}")
        ensure("ok context image alias controls" in ran.stdout,
               f"missing context verdict: {ran.stdout}")
        ensure(not ran.stderr, f"context sanitizer diagnostics: {ran.stderr}")


def cases() -> list[Case]:
    return [Case("context output aliases successor or predecessor",
                 context_alias_controls, lane="guest")]
