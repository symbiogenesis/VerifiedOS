# SPDX-License-Identifier: Apache-2.0
"""The host entry points, run twice each over the live tree: identical or lying.

Goal 1's read-only half. Every tool here claims to only read the checkout, and a
claim like that is proven by running the tool twice and comparing everything it
answered: a byte of difference means a timestamp, an unordered set, or a write that
fed back. The module brackets all of it with `git status --porcelain` taken before
its first case and after its last, held identical rather than empty, because the
suite may run on a tree with untracked work in flight and the proof owed is that
these runs added none of it. `__pycache__` never appears in either capture: the
repository ignores it, which is why an interpreter warming its caches does not
break the bracket.

The doubled runs read the live documents, so nothing here asserts on their
content, only on agreement between the two runs and on the exit code's meaning.
"""

import subprocess
import sys
from dataclasses import dataclass

from tests.harness import TOOLS, Case, ensure

_ROOT = TOOLS.parent


def _run(*argv: str) -> tuple[int, str, str]:
    done = subprocess.run(list(argv), capture_output=True, encoding="utf-8",
                          errors="replace", check=False, timeout=300, cwd=_ROOT)
    return done.returncode, done.stdout, done.stderr


def _twice_identical(tool: str, *args: str) -> tuple[int, str, str]:
    """Run one tool twice and hold every observable equal, handing back the verdict."""
    first = _run(sys.executable, str(TOOLS / tool), *args)
    second = _run(sys.executable, str(TOOLS / tool), *args)
    ensure(first == second,
           f"{tool} answered differently on its second run:\n"
           f"first:  {first!r}\nsecond: {second!r}")
    return first


@dataclass
class _Flow:
    porcelain: str | None = None


_FLOW = _Flow()


def _status() -> str:
    code, out, err = _run("git", "-C", str(_ROOT), "status", "--porcelain")
    ensure(code == 0, f"git status failed: {err!r}")
    return out


def _tree_status_before() -> None:
    _FLOW.porcelain = _status()


def _coread_list_twice() -> None:
    code, out, _ = _twice_identical("co-read.py")
    ensure(code == 0, f"list mode is a worklist and exits 0 either way, got {code}")
    ensure("pair" in out, f"the worklist names its pairs, got {out!r}")


def _blast_radius_twice() -> None:
    code, out, _ = _twice_identical("blast-radius.py")
    ensure(code == 0, f"bare mode on the live record exits 0, got {code}: {out!r}")
    ensure(out.startswith("the Vocabulary record's Prop fields and their consumers:"),
           f"bare mode prints the consumers map, got {out!r}")


def _bank_dse_twice() -> None:
    code, out, _ = _twice_identical("bank-dse.py")
    ensure(code == 0, f"the live composition scores clean, got {code}: {out!r}")


def _typecheck_twice() -> None:
    code, out, _ = _twice_identical("typecheck.py")
    ensure(code == 0, f"the tools hold to their own discipline, got {code}: {out!r}")


def _check_twice() -> None:
    code, out, _ = _twice_identical("check.py")
    ensure(code == 0, f"the live tree checks clean, got {code}: {out!r}")
    ensure("every derived fact agrees with its artifact." in out,
           f"a clean run closes on its one sentence, got {out[-400:]!r}")


def _tree_status_after() -> None:
    ensure(_FLOW.porcelain is not None,
           "the before-case did not run, so there is nothing to hold the tree against")
    after = _status()
    ensure(after == _FLOW.porcelain,
           f"the doubled runs changed the tree:\nbefore: {_FLOW.porcelain!r}\n"
           f"after:  {after!r}")


def cases() -> list[Case]:
    # the first case captures the tree's state and the last holds the tree to it, so
    # everything between must leave no trace; `check.py` doubles past the ~2s mark
    # and rides in the slow set, which leaves the bracket and four doubled tools in
    # the fast one
    return [
        Case("tree-status-before", _tree_status_before, lane="host"),
        Case("coread-list-twice", _coread_list_twice, lane="host"),
        Case("blast-radius-twice", _blast_radius_twice, lane="host"),
        Case("bank-dse-twice", _bank_dse_twice, lane="host"),
        Case("typecheck-twice", _typecheck_twice, lane="host"),
        Case("check-twice", _check_twice, slow=True, lane="host"),
        Case("tree-status-after", _tree_status_after, lane="host"),
    ]
