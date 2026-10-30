# SPDX-License-Identifier: Apache-2.0
"""Version consumers have one explicit owner and no guessed interpreter default."""

import os
import subprocess
import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import pyversion
from vos.cli import typecheck
from vos.report import Reporter


def _supported_minor() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-pyversion-") as name:
        root = Path(name)
        path = root / pyversion.PROJECT
        path.parent.mkdir()
        for minor in ("3.12", "3.14", "3.99"):
            major, lower = map(int, minor.split("."))
            path.write_text(f'[project]\nrequires-python = ">={minor},<{major}.{lower + 1}"\n',
                            encoding="utf-8", newline="")
            ensure(pyversion.supported_minor(root) == minor,
                   "the target must come from the manifest instead of the running interpreter")


def _invalid_owner_refuses() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-pyversion-") as name:
        root = Path(name)
        path = root / pyversion.PROJECT
        path.parent.mkdir()
        for text in (None, "[broken\n", "", '[project]\nname = "tools"\n',
                     '[project]\nrequires-python = false\n',
                     *('[project]\nrequires-python = "' + value + '"\n' for value in
                       (">=3.12", ">=3.12,<3.15", ">=3.14,<3.14", ">=3.14,<4.15",
                        ">=3.14.0,<3.15", ">=03.14,<3.15", ">=3.014,<3.15",
                        ">=3.14, <3.15", "==3.14", ">=3.14,<3.15,!=3.14.1"))):
            if text is not None:
                path.write_text(text, encoding="utf-8", newline="")
            try:
                pyversion.supported_minor(root)
            except (OSError, ValueError):
                pass
            else:
                raise AssertionError(f"invalid or missing interpreter owner accepted: {text!r}")


def _editor_targets_follow_metadata() -> None:
    report = Reporter()
    editions = (("ty", typecheck.TY_VERSION, "3.11", "3.12", "type Scalar = int\n",
                 ["check", "--output-format", "concise"]),
                ("ruff", typecheck.RUFF_VERSION, "3.9", "3.10",
                 "from typing import Optional\nvalue: Optional[int] = None\n",
                 ["check", "--output-format", "concise"]))
    environment = {key: value for key, value in os.environ.items()
                   if key not in {"PYTHONPATH", "TY_LOG", "TY_LOG_PROFILE"}}
    for tool, pin, older, newer, source, arguments in editions:
        executable = typecheck._pinned(report, tool, pin)
        if executable is None:
            raise AssertionError(f"the pinned checkers must be installed: {report.out!r}")
        with tempfile.TemporaryDirectory(prefix="vos-editor-python-") as name:
            root = Path(name)
            project = root / pyversion.PROJECT
            project.parent.mkdir()
            (project.parent / "probe.py").write_text(source, encoding="utf-8", newline="")
            (project.parent / "ty.toml").write_text('[rules]\nall = "error"\n',
                                                   encoding="utf-8", newline="")
            (project.parent / "ruff.toml").write_text('[lint]\nselect = ["UP045"]\n',
                                                     encoding="utf-8", newline="")
            for minor, expected in ((older, 1 if tool == "ty" else 0),
                                    (newer, 0 if tool == "ty" else 1)):
                major, lower = map(int, minor.split("."))
                project.write_text(f'[project]\nname = "probe"\nversion = "0"\n'
                                   f'requires-python = ">={minor},<{major}.{lower + 1}"\n',
                                   encoding="utf-8", newline="")
                result = subprocess.run([executable, *arguments, "probe.py"],
                                        cwd=project.parent, capture_output=True, encoding="utf-8",
                                        env=environment, check=False, timeout=typecheck.TIMEOUT)
                ensure(result.returncode == expected,
                       f"{tool}'s editor discovery ignored requires-python {minor}: "
                       f"{result.returncode}, {result.stdout!r} {result.stderr!r}")


def cases() -> list[Case]:
    return [Case("supported minor follows the manifest", _supported_minor),
            Case("missing and malformed version owners refuse", _invalid_owner_refuses),
            Case("editor targets follow the project metadata", _editor_targets_follow_metadata)]
