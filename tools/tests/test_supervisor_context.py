# SPDX-License-Identifier: Apache-2.0
"""Finite nonblocking supervisor protocol controls and compiled regressions."""

import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import supervisor, toolenv


def native_context_controls() -> None:
    compiler = supervisor.c_compiler()
    ensure(compiler is not None, "native C compiler is missing")
    if compiler is None:
        return
    source = TOOLS.parent / "supervisor"
    work = toolenv.environment(TOOLS.parent, sys.platform).parent / "supervisor-context-tests"
    work.mkdir(parents=True, exist_ok=True)
    mutations = (
        ("unmatched acknowledgment", "ack[VOS_CTX_ACK_SEQUENCE] != sequence", "0"),
        ("early backoff", "restart && ack[VOS_CTX_ACK_NOW] < ack[VOS_CTX_ACK_DEADLINE]", "0"),
        ("reserved sequence", "sequence >= UINT64_MAX - 1U", "sequence == UINT64_MAX"),
    )
    original = (source / "src/context.c").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="native-", dir=work) as directory:
        lane = Path(directory)
        for index, mutation in enumerate((None, *mutations)):
            context = lane / f"context-{index}.c"
            body = original
            if mutation is not None:
                name, old, new = mutation
                ensure(body.count(old) == 1, f"{name}: mutation site drifted")
                body = body.replace(old, new, 1)
            context.write_text(body, encoding="utf-8", newline="")
            binary = lane / f"context-{index}"
            built = subprocess.run(
                [compiler, *supervisor.CFLAGS, "-I", str(source / "include"),
                 str(source / "src/supervisor.c"), str(context),
                 str(source / "test/context.c"), "-o", str(binary)],
                capture_output=True, text=True, timeout=60, check=False)
            ensure(built.returncode == 0, f"control did not compile: {built.stderr}")
            ran = subprocess.run([str(binary)], capture_output=True, text=True,
                                 timeout=60, check=False)
            if mutation is None:
                ensure(ran.returncode == 0, f"context control {ran.returncode} failed")
            else:
                ensure(ran.returncode != 0, f"compiled mutant survived: {mutation[0]}")


def cases() -> list[Case]:
    return [Case("nonblocking reactions and three compiled regressions",
                 native_context_controls, lane="guest")]
