# SPDX-License-Identifier: Apache-2.0
"""Bind finite resident retirement to the actual scalar kernel producer."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import toolenv
from vos.corpus import find_root

SOURCE = "storage/src/resident_scalar.c"


def _variants(source: str) -> list[tuple[str, str, str]]:
    def changed(before: str, after: str) -> str:
        ensure(source.count(before) == 1, "scalar resident mutation anchor must be unique")
        return source.replace(before, after, 1)

    return [
        ("pristine", source, ""),
        ("uncovered-holder", changed(
            "for (i = 0; i < VOS_RESIDENT_HOLDERS; ++i) {",
            "for (i = 0; i + 1 < VOS_RESIDENT_HOLDERS; ++i) {"),
            "uncovered second holder refuses before effects"),
        ("stale-epoch", changed("b->epoch != k->epoch || b->epoch == UINT64_MAX ||",
            "b->epoch == UINT64_MAX ||"), "stale attempt epoch refuses before effects"),
        ("no-cancellation", changed("(void)vos_resident_retire(o, 0);", "(void)o;"),
            "complete holder cancellation before publication"),
        ("incomplete-receipt", changed(
            "!completion.epoch_advanced || !vos_semantic_completion(&completion) ||",
            "!completion.epoch_advanced ||"),
            "partial kernel teardown is not semantic completion"),
        ("premature-reuse", changed(
            "/* CONTAINED_ONLY: semantic completion never authorizes backing release. */",
            "(void)vos_resident_retire(o, 1);"),
            "semantic completion retains backing quarantine"),
        ("binding-drift", changed(
            "memcmp(&o->common, &a->closed, sizeof(a->closed)) != 0 ||", ""),
            "changed resident binding cannot complete"),
    ]


def scalar_resident_controls() -> None:
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    ensure(compiler is not None, "scalar resident controls require a native C compiler")
    if compiler is None:
        raise RuntimeError("no native C compiler")
    root = find_root()
    work = toolenv.environment(root, sys.platform).parent / "resident-scalar-tests"
    work.mkdir(parents=True, exist_ok=True)
    source = (root / SOURCE).read_text(encoding="utf-8")
    dependencies = ("storage/src/resident_reads.c", "kernel/src/effects.c",
                    "kernel/src/context.c", "supervisor/src/supervisor.c",
                    "supervisor/src/effects.c", "supervisor/src/manifest.c",
                    "storage/test/resident_scalar.c")
    with tempfile.TemporaryDirectory(prefix="resident-scalar-", dir=work) as directory:
        scratch = Path(directory)
        for name, candidate, expected in _variants(source):
            path = scratch / f"{name}.c"
            path.write_text(candidate, encoding="utf-8", newline="\n")
            executable = scratch / name
            compiled = subprocess.run([compiler, "-std=c17", "-O1", "-Wall", "-Wextra",
                "-Wstrict-prototypes",
                "-Werror", "-pedantic", "-DVOS_HOST_MODEL",
                *("-I" + str(root / include) for include in
                  ("storage/include", "kernel/include", "supervisor/include")),
                str(path), *(str(root / dep) for dep in dependencies), "-o", str(executable)],
                capture_output=True, text=True, timeout=30, check=False)
            ensure(compiled.returncode == 0,
                   f"{name}: stillborn compilation supplies no rejection: {compiled.stderr}")
            if compiled.returncode != 0:
                raise RuntimeError(f"{name} did not compile")
            result = subprocess.run([str(executable)], capture_output=True, text=True,
                                    timeout=30, check=False)
            if name == "pristine":
                ensure(result.returncode == 0, result.stderr)
                ensure("ok resident scalar actual producer" in result.stderr,
                       "scalar resident positive campaign did not reach its verdict")
            else:
                ensure(result.returncode != 0 and expected in result.stderr,
                       f"{name}: executed defect survived or missed its oracle: {result.stderr}")


def cases() -> list[Case]:
    return [Case("resident scalar actual producer and executed defect controls",
                 scalar_resident_controls, lane="guest")]
