# SPDX-License-Identifier: Apache-2.0
"""Native comparison adapters compile and bind transitive proof dependencies."""

import json
import subprocess
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import composer, proof_staging
from vos.cli import admission as admission_cli


def _fixture(temporary: str, entry: str) -> tuple[Path, Path]:
    directory = Path(temporary)
    root, native = directory / "checkout", directory / "native"
    (root / "proofs").mkdir(parents=True)
    (root / "proofs" / "Shared.v").write_text("Definition value := 1.\n", encoding="utf-8")
    (root / "proofs" / entry).write_text("Require Shared.\n", encoding="utf-8")
    for name in (*proof_staging.IMPLEMENTATION_SOURCES, "tools/vos/composer.py"):
        source = root / name
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("fixture implementation\n", encoding="utf-8")
    return root, native


def _composer_dependencies() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root, native = _fixture(temporary, "HandlerGraph.v")
        commands: list[list[str]] = []

        def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        with ExitStack() as patches:
            patches.enter_context(patch.object(composer.sys, "platform", "linux"))
            patches.enter_context(patch.object(composer.env, "lane_of", return_value="fixture"))
            patches.enter_context(patch.object(composer.env, "lane_root", return_value=native))
            patches.enter_context(patch.object(composer.env, "log_root", return_value=native / "logs"))
            patches.enter_context(patch.object(composer.env, "filesystem", return_value="ext4"))
            patches.enter_context(patch.object(composer.env, "rocq_command", return_value=["rocq"]))
            patches.enter_context(patch.object(composer.env, "rocqchk_command", return_value=["rocqchk"]))
            patches.enter_context(patch.object(composer, "reference_program", return_value="fixture comparison\n"))
            patches.enter_context(patch.object(composer.subprocess, "run", side_effect=run))
            result = composer.prove_reference(root)
        ensure([Path(command[-1]).name for command in commands] ==
               ["Shared.v", "HandlerGraph.v", "ComposerComparison.v", "ComposerComparison"],
               "composer did not compile the dependency before its reference")
        ensure(result["proof_inputs_sha256"] == proof_staging.inputs(root, ("HandlerGraph.v",)),
               "composer receipt omitted a staged dependency")


def _admission_dependencies() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root, native = _fixture(temporary, "AdmissionPath.v")
        commands: list[list[str]] = []

        def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        with ExitStack() as patches:
            patches.enter_context(patch.object(admission_cli.sys, "platform", "linux"))
            patches.enter_context(patch.object(admission_cli.env, "load",
                                              return_value=type("Environment", (), {"lane_root": native})()))
            patches.enter_context(patch.object(admission_cli.env, "log_root", return_value=native / "logs"))
            patches.enter_context(patch.object(admission_cli.env, "lane_of", return_value="fixture"))
            patches.enter_context(patch.object(admission_cli.env, "rocq_command", return_value=["rocq"]))
            patches.enter_context(patch.object(admission_cli.source_bindings, "sources", return_value=()))
            patches.enter_context(patch.object(admission_cli.admission, "read_reference", return_value={}))
            patches.enter_context(patch.object(admission_cli.admission, "comparison_source",
                                              return_value="fixture comparison\n"))
            patches.enter_context(patch.object(admission_cli.admission, "generated_cases", return_value=[{}]))
            patches.enter_context(patch.object(admission_cli.admission, "CHECKER", "tools/vos/composer.py"))
            patches.enter_context(patch.object(admission_cli.subprocess, "run", side_effect=run))
            ensure(admission_cli._compare(root) == 0, "mock admission comparison failed")
        ensure([Path(command[-1]).name for command in commands] ==
               ["Shared.v", "AdmissionPath.v", "AdmissionComparison.v"],
               "admission did not compile the dependency before its reference")
        report = json.loads((native / "admission-reference" / "comparison.json").read_text(encoding="utf-8"))
        ensure("proofs/Shared.v" in report["inputs_before"], "admission receipt omitted the dependency")


def cases() -> list[Case]:
    return [Case("composer-dependencies", _composer_dependencies),
            Case("admission-dependencies", _admission_dependencies)]
