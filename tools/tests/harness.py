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

import subprocess
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

# Where the real tools live, for a test that runs one as a subprocess.
TOOLS = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Case:
    """One check: `fn` returns None on pass and raises, with a message, on failure.

    `slow` cases run only under `--slow`; `lane` is "any", "host", or "guest", and
    the runner filters by platform, so one module can carry both lanes' cases.
    """

    name: str
    fn: Callable[[], None]
    slow: bool = False
    lane: str = "any"


def ensure(cond: bool, msg: str) -> None:
    """The assertion that survives -O: raise, never assert."""
    if not cond:
        raise AssertionError(msg)


@contextmanager
def sandbox_tree(files: dict[str, str]) -> Iterator[Path]:
    """A throwaway git-tracked tree holding exactly `files` (relative path -> text).

    Contents are written byte-for-byte (UTF-8, no newline translation), then
    `git init` + `git add -A` so a tool whose corpus is the index sees every file.
    The tree lives in the system tempdir and vanishes with the context; nothing a
    test does here can reach the real checkout.
    """
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td).resolve()
        for rel, text in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="")
        _git(root, "init", "-q")
        _git(root, "add", "-A")
        yield root


def _git(root: Path, *args: str) -> None:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          encoding="utf-8", errors="replace", check=False, timeout=60)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} exited {done.returncode}: "
                           f"{done.stderr.strip()}")
