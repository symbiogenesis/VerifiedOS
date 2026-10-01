# SPDX-License-Identifier: Apache-2.0
"""Real Git fixtures the fanout test modules share: a main checkout, a bare remote and
one registered worker lane."""

import argparse
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from tests.harness import ensure, sandbox_tree
from vos.cli import fanout, worktree

FILES = {".gitignore": "/.worktrees/\n/out/\n", "README.md": "base\n",
         "tools/run.py": "raise SystemExit(0)\n"}


def git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), *args], check=False, capture_output=True,
                          encoding="utf-8", timeout=60)
    ensure(done.returncode == 0, f"fixture Git failed: {done.stderr}")
    return done.stdout.strip()


def commit(root: Path, name: str) -> str:
    git(root, "commit", "--allow-empty", "-qm", name)
    return git(root, "rev-parse", "HEAD")


@contextmanager
def fixture() -> Iterator[tuple[Path, Path, Path]]:
    with sandbox_tree(FILES) as root, tempfile.TemporaryDirectory(prefix="vos-remote-") as remote:
        git(root, "config", "user.name", "Fanout test")
        git(root, "config", "user.email", "fanout@example.invalid")
        git(root, "config", "commit.gpgsign", "false")
        base = commit(root, "base")
        git(root, "branch", "-M", "main")
        git(Path(remote), "init", "--bare", "-q")
        git(root, "remote", "add", "origin", remote)
        record = worktree.create(root, "worker", base)
        lane = Path(str(record["path"]))
        yield root, lane, Path(remote)


def init(root: Path, lane: Path,
         reading_base: str | None = None) -> tuple[fanout.Batch, Path]:
    args = argparse.Namespace(batch="example", worktree=[lane], host_worktree=[],
                              remote="origin", cold=True, reading_base=reading_base,
                              defer=["separate experiment"])
    return fanout.initialize(root, args), root / "out/fanout/example/state.json"


def finish_args() -> argparse.Namespace:
    return argparse.Namespace(path=[], message=None, wait_host=0)


def refuses(action: Callable[[], object], fragment: str) -> None:
    try:
        action()
    except ValueError as err:
        ensure(fragment in str(err), f"expected {fragment}: {err}")
    else:
        raise AssertionError(f"expected refusal: {fragment}")
