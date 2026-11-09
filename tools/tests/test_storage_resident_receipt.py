# SPDX-License-Identifier: Apache-2.0
"""Check authenticated resident admission and unchanged-checkpoint reuse."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import toolenv

ROOT = Path(__file__).resolve().parents[2]


def resident_receipt() -> None:
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    ensure(compiler is not None, "resident receipt checks require a native C compiler")
    if compiler is None:
        raise RuntimeError("no native C compiler")
    work = toolenv.environment(ROOT, sys.platform).parent / "resident-receipt-tests"
    work.mkdir(parents=True, exist_ok=True)
    sources = [ROOT / "storage/src" / f"{name}.c" for name in (
        "crypto_core", "node_image", "tree_image", "tree_update", "resident_reads", "storage_publish"
    )]
    with tempfile.TemporaryDirectory(prefix="receipt-", dir=work) as directory:
        binary = Path(directory) / "resident-receipt"
        result = subprocess.run([
            compiler, "-std=c17", "-O2", "-Wall", "-Wextra", "-Werror",
            "-Wstrict-prototypes", "-pedantic", "-I" + str(ROOT / "storage/include"),
            *map(str, sources), str(ROOT / "storage/host/resident_receipt.c"), "-o", str(binary)
        ], capture_output=True, text=True, timeout=60, check=False)
        ensure(result.returncode == 0, f"resident receipt compilation failed: {result.stderr}")
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        result = subprocess.run([str(binary)], capture_output=True, text=True,
                                timeout=60, check=False)
        ensure(result.returncode == 0, result.stderr or result.stdout)
        ensure("resident receipt: ok" in result.stdout, "resident receipt verdict missing")


def cases() -> list[Case]:
    return [Case("resident receipt authenticates admission and invalidates stale bindings",
                 resident_receipt, lane="guest")]
