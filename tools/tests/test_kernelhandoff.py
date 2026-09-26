# SPDX-License-Identifier: Apache-2.0
"""Native C byte readers against M3.5's layout and assembled producer fixture.

These fixed controls are separate from Gallina differentials and target evidence.
Ubuntu Host CI compiles with ASan/UBSan; the Windows shard does not compile C.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import TOOLS, Case, ensure
from vos import boot_handoff, toolenv
from vos.cli import kernel


def native_handoff_controls() -> None:
    root = TOOLS.parent
    compiler = kernel.c_compiler()
    ensure(compiler is not None, "native handoff controls require cc, gcc or clang")
    if compiler is None:
        return
    work = toolenv.environment(root, sys.platform).parent / "kernel-handoff-tests"
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="handoff-", dir=work) as temporary:
        scratch = Path(temporary)
        binary = scratch / "handoff"
        assembled = boot_handoff.assemble_mmode(root)
        layout = boot_handoff.layout(root)
        begin = assembled.symbols["init_desc"] - layout["BRINGUP_MMODE_LOAD_BASE"]
        end = assembled.symbols["init_desc_end"] - layout["BRINGUP_MMODE_LOAD_BASE"]
        descriptor = scratch / "producer-init.bin"
        descriptor.write_bytes(assembled.payload[begin:end])
        sources = [root / "kernel" / name for name in (*kernel.SOURCES, "src/handoff.c",
                                                       "test/handoff.c")]
        built = subprocess.run(
            [compiler, *kernel.CFLAGS, "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
             "-I", str(root / "kernel/include"), "-I", str(root / "firmware/include"),
             *(str(source) for source in sources), "-o", str(binary)],
            capture_output=True, text=True, check=False, timeout=60)
        ensure(built.returncode == 0, f"handoff compile failed: {built.stdout}{built.stderr}")
        ran = subprocess.run([str(binary), str(descriptor)], capture_output=True,
                             text=True, check=False, timeout=60)
        ensure(ran.returncode == 0, f"handoff controls failed: {ran.stdout}{ran.stderr}")
        ensure("handoff fixed controls" in ran.stdout, f"missing native verdict: {ran.stdout}")
        ensure(not ran.stderr, f"handoff sanitizer diagnostics: {ran.stderr}")
        print(ran.stdout.strip())


def cases() -> list[Case]:
    return [Case("native_handoff_controls", native_handoff_controls, lane="guest")]
