# SPDX-License-Identifier: Apache-2.0
"""Locked Python dependencies and a separate environment for each checkout and OS."""

import hashlib
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

READY = "_VOS_TOOL_ENV"
PROJECT = "tools/pyproject.toml"
LOCK = "tools/uv.lock"


def checker_pins(root: Path) -> dict[str, str]:
    project = tomllib.loads((root / PROJECT).read_text(encoding="utf-8"))
    dependencies = project["dependency-groups"]["dev"]
    if not isinstance(dependencies, list):
        raise TypeError("dependency-groups.dev must be a list of exact checker pins")
    pins: dict[str, str] = {}
    for dependency in dependencies:
        if not isinstance(dependency, str):
            raise TypeError("every checker dependency must be an exact pin")
        name, separator, version = dependency.partition("==")
        if not separator or not version or name in pins:
            raise ValueError(f"invalid or duplicate checker pin: {dependency}")
        pins[name] = version
    if set(pins) != {"ty", "ruff"}:
        raise ValueError("dependency-groups.dev must pin ty and ruff")
    return pins


def environment(root: Path, platform: str) -> Path:
    return root / "out" / f"venv-{platform}"


def identity(root: Path, platform: str) -> str:
    digest = hashlib.sha256(str(environment(root, platform)).encode("utf-8"))
    for name in (PROJECT, LOCK):
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


def bootstrap(root: Path, argv: list[str]) -> int | None:
    """Synchronize before dispatch; children inherit the settled environment."""
    target = environment(root, sys.platform)
    try:
        token = identity(root, sys.platform)
    except OSError as err:
        print(f"the tools require {PROJECT} and {LOCK}: {err}", file=sys.stderr)
        return 1
    if Path(sys.prefix) == target and os.environ.get(READY) == token:
        return None
    uv = shutil.which("uv")
    if uv is None:
        print(f"uv is required; install the version in {PROJECT}'s "
              "tool.uv.required-version, then rerun this command", file=sys.stderr)
        return 1
    child_env = os.environ.copy()
    child_env.pop("VIRTUAL_ENV", None)
    child_env["UV_PROJECT_ENVIRONMENT"] = str(target)
    child_env["PYTHONUTF8"] = "1"
    child_env[READY] = token
    try:
        return subprocess.run(
            [uv, "run", "--project", str((root / PROJECT).parent), "--locked", "--exact",
             "--no-python-downloads", "python",
             str(root / "tools" / "run.py"), *argv],
            env=child_env, check=False).returncode
    except OSError as err:
        print(f"the tools environment could not be started: {err}", file=sys.stderr)
        return 1
