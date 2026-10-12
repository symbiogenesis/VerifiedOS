# SPDX-License-Identifier: Apache-2.0
"""Prepare explicitly selected files with the locked formatters, without builds."""

import argparse
import os
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path

from vos import corpus, env, toolenv
from vos.cli import Table, dispatch


def selected(root: Path, names: list[str], scope: str) -> list[str]:
    """Resolve ordinary files inside the selected owner; refuse aliasing and escapes."""
    if not names or scope not in {"python", "model"}:
        raise ValueError("preparation requires explicit files and a known owner")
    base = root.resolve()
    result: list[str] = []
    for name in names:
        path = Path(name)
        if not path.is_absolute():
            path = base / path
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(base) or not path.is_file() or path.is_symlink():
            raise ValueError(f"not an ordinary contained file: {name}")
        relative = resolved.relative_to(base)
        if path.absolute() != resolved:
            raise ValueError(f"symlink or ambiguous path: {name}")
        if scope == "python":
            if relative.parts[0] != "tools" or relative.suffix != ".py":
                raise ValueError(f"Python preparation requires tools/*.py: {name}")
        elif (relative.parts[0] != "model" or relative.parts[:2] == ("model", "dependencies")):
            raise ValueError(f"model preparation requires authored model files: {name}")
        spelling = relative.as_posix()
        if spelling in result:
            raise ValueError(f"duplicate selected file: {name}")
        result.append(spelling)
    return result


def python_prepare(root: Path, names: list[str], *, check: bool) -> int:
    """Only import ordering is automatically rewritten; type acceptance remains separate."""
    paths = selected(root, names, "python")
    executable = Path(sysconfig.get_path("scripts")) / ("ruff.exe" if sys.platform == "win32" else "ruff")
    pin = toolenv.checker_pins(root)["ruff"]
    tools = root / "tools"
    version = subprocess.run([str(executable), "--version"], cwd=tools,
                             capture_output=True, text=True, check=True, timeout=30)
    if version.stdout.strip() != f"ruff {pin}":
        raise ValueError("preparation requires the locked environment's exact Ruff edition")
    argv = [str(executable), "check", "--config", str(root / "tools" / "ruff.toml"),
            "--select", "I", "--no-cache", "--no-respect-gitignore"]
    if not check:
        argv.append("--fix")
    return subprocess.run([*argv, "--", *(str(root / path) for path in paths)],
                          cwd=tools, check=False, timeout=120).returncode


def model_prepare(root: Path, names: list[str]) -> int:
    """The pinned CI hooks on selected files, with native private hook storage."""
    paths = selected(root, names, "model")
    if sys.platform != "linux":
        raise ValueError("model hooks require the guest; use python tools/run.py prepare model")
    lane = env.load(toolchain=False).lane_root / "model-hooks"
    uv = shutil.which("uv")
    if uv is None:
        raise ValueError("the locked uv client is required")
    child = os.environ.copy()
    child.update({
        "UV_PROJECT_ENVIRONMENT": str(lane / "venv-model"),
        "PRE_COMMIT_HOME": str(lane / "pre-commit"),
        "VIRTUALENV_OVERRIDE_APP_DATA": str(lane / "virtualenv"),
        "PIP_CONSTRAINT": str(root / "tools/ci/model-hooks-constraints.txt"),
        "PIP_BUILD_CONSTRAINT": str(root / "tools/ci/model-hooks-build-constraints.txt"),
        "PIP_UPLOADED_PRIOR_TO": "P3D", "SKIP": "markdown-link-check",
    })
    argv = [uv, "run", "--project", "tools", "--locked", "--exact", "--only-group", "model",
            "--no-python-downloads", "pre-commit", "run", "--config", "model/.pre-commit-config.yaml",
            "--show-diff-on-failure", "--files", *paths]
    return subprocess.run(argv, cwd=root, env=child, check=False, timeout=1800).returncode


def run(args: argparse.Namespace) -> int:
    try:
        root = corpus.find_root()
        code = (python_prepare(root, args.path, check=args.check) if args.command == "python"
                else model_prepare(root, args.path))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"FAIL prepare: {error}")
        return 1
    print("Review selected-file diffs; full acceptance remains with hosted CI.")
    return code


TABLE: Table = {"python": (run, "locked Ruff import ordering on selected Python files"),
                "model": (run, "locked model hooks on selected authored files")}


def flags(name: str, parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--path", action="append", required=True, help="selected file; repeatable")
    if name == "python":
        parser.add_argument("--check", action="store_true", help="report import ordering without rewriting")


def main(argv: list[str] | None = None) -> int:
    return dispatch(__doc__, TABLE, argv, flags, prog="run.py prepare")
