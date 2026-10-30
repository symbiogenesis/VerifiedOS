# SPDX-License-Identifier: Apache-2.0
"""The locked resolver refuses stale input before running a tool command."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import toolenv


def _locked_resolution() -> None:
    uv = shutil.which("uv")
    ensure(uv is not None, "the public tool bootstrap requires uv")
    with tempfile.TemporaryDirectory(prefix="vos-locked-resolution-") as directory:
        root = Path(directory)
        project = root / "pyproject.toml"
        declaration = ('[project]\nname = "vos-lock-fixture"\nversion = "0"\n'
                       'requires-python = ">=3.14,<3.15"\n'
                       '[tool.uv]\npackage = false\npython-downloads = "never"\n')
        project.write_text(declaration, encoding="utf-8")
        environment = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(root / "venv")}
        environment.pop("VIRTUAL_ENV", None)
        command = [str(uv), "run", "--project", str(root), "--offline", "--exact",
                   "--no-python-downloads", "--python", sys.executable, "python", "-c",
                   "from pathlib import Path; Path('dispatched').write_text('yes')"]
        first = subprocess.run(command, cwd=root, env=environment, capture_output=True,
                               text=True, check=False, timeout=30)
        ensure(first.returncode == 0 and (root / "dispatched").is_file(),
               f"a coherent fixture must dispatch: {first.stderr}")
        locked = (root / "uv.lock").read_bytes()
        (root / "dispatched").unlink()
        project.write_text(declaration.replace('version = "0"', 'version = "1"'),
                           encoding="utf-8")
        stale = subprocess.run([*command[:2], "--locked", *command[2:]], cwd=root,
                               env=environment, capture_output=True, text=True,
                               check=False, timeout=30)
        ensure(stale.returncode != 0 and "lockfile" in stale.stderr.lower(),
               f"uv must refuse the stale lock: {stale.stderr}")
        ensure(not (root / "dispatched").exists(), "stale input reached command dispatch")
        ensure((root / "uv.lock").read_bytes() == locked,
               "locked validation must not repair dependency decisions")


def _exact_checker_pins() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-checker-pins-") as directory:
        root = Path(directory)
        (root / "tools").mkdir()
        path = root / toolenv.PROJECT
        for dependencies in ('["ty>=1", "ruff==2"]',
                             '["ty==1", "ty==1", "ruff==2"]',
                             '["ty==1"]', '"invalid"'):
            path.write_text(f"[dependency-groups]\ndev = {dependencies}\n", encoding="utf-8")
            try:
                toolenv.checker_pins(root)
            except (TypeError, ValueError):
                continue
            raise AssertionError(f"invalid exact checker pin policy accepted: {dependencies}")


def cases() -> list[Case]:
    return [Case("locked resolver refuses stale input before dispatch", _locked_resolution),
            Case("checker dependencies remain exact and unique", _exact_checker_pins)]
