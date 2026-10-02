# SPDX-License-Identifier: Apache-2.0
"""The vocabulary every test module shares.

A test module under `tools/tests/` is one subject: it exports `cases()` returning
the checks it makes, and each check decides by raising. `ensure` is the one
assertion helper, a raise rather than an `assert`, because `python -O` deletes
asserts and a test that -O empties is a test that lies. `sandbox_tree` is the
fixture builder for anything that needs a corpus-shaped checkout: mutating-path
tests (`--fix`, `--bless`, ledger and manifest writes) run there, never against
the live tree.
"""

import os
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Literal

# Where the real tools live, for a test that runs one as a subprocess.
TOOLS = Path(__file__).resolve().parents[1]

type Lane = Literal["any", "host", "guest", "toolchain"]


@dataclass(frozen=True)
class Case:
    """One check: `fn` returns None on pass and raises, with a message, on failure.

    `slow` cases run only under `--slow`; `lane` is "any", "host", "guest", or
    "toolchain". The runner decides "host" and "guest" by platform, so one module can
    carry both lanes' cases; "toolchain" is the guest with the Sail switch standing,
    which a Linux runner that never provisioned is not, so a case that drives the
    toolchain is skipped there rather than failing on a precondition about the machine.
    """

    name: str
    fn: Callable[[], None]
    slow: bool = False
    lane: Lane = "any"


def ensure(cond: bool, msg: str) -> None:
    """The assertion that survives -O: raise, never assert."""
    if not cond:
        raise AssertionError(msg)


def with_env(name: str, value: str | None, fn: Callable[[], None]) -> None:
    """Run `fn` with one environment override in place, restoring whatever stood.

    The hook the tools' own call-time overrides are written for: `vos.env` reads each
    of its `VOS_*` settings where it uses them rather than at import, so a case can
    name the build root, the lane or the administrative directory a run is to answer
    about. Shared here because three modules want it, and the restore is what keeps a
    case that sets one from deciding the next case's answer.
    """
    was = os.environ.get(name)
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value
    try:
        fn()
    finally:
        if was is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = was


@contextmanager
def sandbox_tree(files: dict[str, str]) -> Iterator[Path]:
    """A throwaway git-tracked tree holding exactly `files` (relative path -> text).

    Contents are written byte-for-byte (UTF-8, no newline translation), then
    `git init` + `git add -A` so a tool whose corpus is the index sees every file.
    The init is `git_skeleton`'s copy of what `git init` writes, unless `files` itself
    reaches into `.git`, where git's own init decides what such a file meets.
    The tree lives in the system tempdir and vanishes with the context; nothing a
    test does here can reach the real checkout.
    """
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td).resolve()
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="")
        if any(Path(rel).parts[:1] == (".git",) for rel in files):
            _git(root, "init", "-q")
        else:
            directories, written = git_skeleton()
            admin = root / ".git"
            admin.mkdir()
            for rel in directories:
                (admin / rel).mkdir(parents=True, exist_ok=True)
            for rel, data, mode in written:
                (admin / rel).write_bytes(data)
                (admin / rel).chmod(mode)
        _git(root, "add", "-A")
        yield root


# A fresh repository's administrative directory: every directory in it, and every file
# with its bytes and permission bits, each by its path relative to `.git`.
type Skeleton = tuple[tuple[str, ...], tuple[tuple[str, bytes, int], ...]]


@cache
def git_skeleton() -> Skeleton:
    """What `git init` writes into an empty directory under the system tempdir, read
    once per process.

    A sandbox writes this rather than starting `git init` itself, because starting the
    process is most of what an init costs, on Windows above all. The copy is what init
    would write there: the template is git's, and the tempdir's filesystem decides the
    probes `config` records. Git for Windows also marks the directory hidden, which no
    reader here consults.
    """
    with tempfile.TemporaryDirectory(prefix="vos-test-init-") as td:
        admin = Path(td).resolve() / ".git"
        _git(admin.parent, "init", "-q")
        directories: list[str] = []
        written: list[tuple[str, bytes, int]] = []
        for dirpath, _dirnames, filenames in admin.walk():
            if dirpath != admin:
                directories.append(dirpath.relative_to(admin).as_posix())
            for name in filenames:
                path = dirpath / name
                written.append((path.relative_to(admin).as_posix(), path.read_bytes(),
                                stat.S_IMODE(path.stat().st_mode)))
    return tuple(sorted(directories)), tuple(sorted(written))


def cli_argv(root: Path, module: str, *args: str) -> list[str]:
    """Run a fixture's CLI in the settled interpreter without provisioning its inputs."""
    return [sys.executable, "-c",
            "import sys; from importlib import import_module; "
            "sys.path.insert(0, sys.argv[1]); "
            "raise SystemExit(import_module(sys.argv[2]).main(sys.argv[3:]))",
            str(root / "tools"), module, *args]


def _git(root: Path, *args: str) -> None:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          encoding="utf-8", errors="replace", check=False, timeout=60)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} exited {done.returncode}: "
                           f"{done.stderr.strip()}")
