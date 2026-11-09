# SPDX-License-Identifier: Apache-2.0
"""Selected-file preparation respects ownership, locked editions and no-build scope."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos.cli import prepare


def _selection() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-prepare-") as name:
        root = Path(name).resolve()
        (root / "tools").mkdir()
        path = root / "tools/selected.py"
        path.write_text("import os\n", encoding="utf-8")
        ensure(prepare.selected(root, [str(path)], "python") == ["tools/selected.py"],
               "ordinary absolute selection was not normalized")
        for paths in ([], [str(path), "tools/selected.py"], ["tools/../tools/selected.py"], [str(TOOLS / "run.py")]):
            try:
                prepare.selected(root, paths, "python")
            except ValueError:
                pass
            else:
                raise AssertionError(f"ambiguous or escaping selection accepted: {paths}")
        (root / "model/dependencies").mkdir(parents=True)
        dependency = root / "model/dependencies/vendor.c"
        dependency.write_text("int x;\n", encoding="utf-8")
        try:
            prepare.selected(root, [str(dependency)], "model")
        except ValueError:
            pass
        else:
            raise AssertionError("dependency formatting accepted")


def _locked_formatter() -> None:
    root = TOOLS.parent
    pin = prepare.toolenv.checker_pins(root)["ruff"]
    version = subprocess.CompletedProcess([], 0, stdout=f"ruff {pin}\n", stderr="")
    result = subprocess.CompletedProcess([], 0)
    with patch.object(prepare.subprocess, "run", side_effect=[version, result]) as invoke:
        ensure(prepare.python_prepare(root, ["tools/run.py"], check=True) == 0, "check failed")
        argv = invoke.call_args.args[0]
        ensure("--fix" not in argv and argv[-1] == str(root / "tools/run.py") and "I" in argv,
               "read-only preparation rewrote files or selected unrelated rules")
        ensure(argv[argv.index("--target-version") + 1]
               == "py" + prepare.pyversion.supported_minor(root).replace(".", ""),
               "explicit-config preparation must use the manifest target")
        ensure(invoke.call_args.kwargs["cwd"] == root / "tools",
               "import classification must use the gate's Python source root")
    with patch.object(prepare.subprocess, "run", side_effect=[version, result]) as invoke:
        ensure(prepare.python_prepare(root, ["tools/run.py"], check=False) == 0, "fix failed")
        ensure("--fix" in invoke.call_args.args[0], "import ordering repair was not requested")
    wrong = subprocess.CompletedProcess([], 0, stdout="ruff 0.0.1\n", stderr="")
    with patch.object(prepare.subprocess, "run", return_value=wrong) as invoke:
        try:
            prepare.python_prepare(root, ["tools/run.py"], check=False)
        except ValueError:
            ensure(invoke.call_count == 1, "wrong edition still performed a rewrite")
        else:
            raise AssertionError("unlocked formatter accepted")


def _locked_model_hooks() -> None:
    root = TOOLS.parent
    result = subprocess.CompletedProcess([], 0)
    with tempfile.TemporaryDirectory(prefix="vos-prepare-lane-") as name:
        base = Path(name).resolve()
        lane_env = prepare.env.Environment(root, root / "model", base / "build", base / "logs",
                                           "", 4, 8192, 4, 4)
        with (patch.object(prepare.sys, "platform", "linux"),
              patch.object(prepare.env, "load", return_value=lane_env),
              patch.object(prepare.shutil, "which", return_value="/usr/bin/uv"),
              patch.object(prepare.subprocess, "run", return_value=result) as invoke):
            ensure(prepare.model_prepare(root, ["model/README.md"]) == 0, "model prepare failed")
            argv = invoke.call_args.args[0]
            child = invoke.call_args.kwargs["env"]
            ensure(argv[:9] == ["/usr/bin/uv", "run", "--project", "tools", "--locked", "--exact",
                                "--only-group", "model", "--no-python-downloads"],
                   "model preparation must use the locked model group")
            ensure(argv[9:] == ["prek", "run", "--config", "model/.pre-commit-config.yaml",
                                "--show-diff-on-failure", "--files", "model/README.md"],
                   "model preparation must run prek on the selected files")
            ensure(child["PREK_HOME"] == str(base / "build" / "model-hooks" / "prek")
                   and child["PREK_UV_SOURCE"] == "none"
                   and child["UV_PYTHON_DOWNLOADS"] == "never"
                   and child["UV_CONSTRAINT"] == str(root / "tools/ci/model-hooks-constraints.txt")
                   and child["UV_BUILD_CONSTRAINT"] == str(root / "tools/ci/model-hooks-build-constraints.txt")
                   and child["UV_EXCLUDE_NEWER"] == "3 days"
                   and child["SKIP"] == "markdown-link-check",
                   "model preparation must pass isolated prek and uv constraint variables")


def cases() -> list[Case]:
    return [Case("contained explicit selection", _selection),
            Case("locked import formatter and check-only mode", _locked_formatter),
            Case("locked model hook runner and uv constraints", _locked_model_hooks)]
