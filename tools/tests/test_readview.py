# SPDX-License-Identifier: Apache-2.0
"""read-view.py end to end, in a sandbox checkout small enough to derive by hand.

What is held: the view opens by declaring itself generated, every entry renders as
a quoted block directly beneath the bookmark that cites it, a `-n` repeat bookmark
gets a pointer rather than a second copy, an entry with no bookmark of its own
renders beneath the bookmark its written-out trace names, the run is deterministic
to the byte across a doubled invocation, and the writer touches nothing but its
output path (the git status bracket the entrypoint tests apply to read-only tools,
applied here around a declared write).
"""

import subprocess
import sys
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path

from tests.harness import TOOLS, Case, ensure, sandbox_tree

_SOURCES = ("tools/read-view.py", "tools/vos/__init__.py", "tools/vos/coread.py",
            "tools/vos/corpus.py", "tools/vos/register.py")

# Three entries: one plain, one whose bookmark the prose repeats under a -2 suffix,
# and one with no bookmark of its own that pairs through its neighbour's.
_REGISTER = """\
# Requirements register (fixture)

## §1 Fixture obligations

**R-01-001** MUST hold the first fixture obligation.
· Accept: the first criterion is measured.
· Trace: [spec 1](spec.md#r-01-001)

**R-01-002** MUST hold the second fixture obligation.
· Accept: the second criterion is measured.
· Trace: [spec 1](spec.md#r-01-002), [spec 1](spec.md#r-01-002-2)

**R-01-003** MUST NOT drop the third fixture obligation.
· Accept: the third criterion is measured.
· Trace: [spec 1](spec.md#r-01-002)
"""

_SPEC = """\
# Design (fixture)

## 1. The fixture claims

The first claim's prose stands here. <a id="r-01-001"></a>

The second claim's prose stands here. <a id="r-01-002"></a>

The second claim recurs here. <a id="r-01-002-2"></a>
"""


def _fixture() -> dict[str, str]:
    root = TOOLS.parent
    files = {rel: (root / rel).read_text(encoding="utf-8") for rel in _SOURCES}
    files["docs/requirements-register.md"] = _REGISTER
    files["docs/spec.md"] = _SPEC
    return files


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(root / "tools" / "read-view.py")],
        capture_output=True, encoding="utf-8", errors="replace", check=False,
        timeout=120)


@dataclass
class _Flow:
    stack: ExitStack | None = None
    root: Path | None = None


_FLOW = _Flow()


def _root() -> Path:
    if _FLOW.root is None:
        raise AssertionError("the sandbox setup case did not run or did not survive")
    return _FLOW.root


def _weave_places_every_entry() -> None:
    stack = ExitStack()
    _FLOW.stack = stack
    _FLOW.root = stack.enter_context(sandbox_tree(_fixture()))

    done = _run(_root())
    ensure(done.returncode == 0 and "wove 3 entries into the prose" in done.stdout,
           f"the weave places all three entries, got {done.returncode}: "
           f"{done.stdout!r} {done.stderr!r}")

    text = (_root() / "out" / "spec-woven.md").read_text(encoding="utf-8")
    ensure(text.startswith("*A generated reading view, never a source"),
           f"the view opens by declaring itself generated, got {text[:80]!r}")

    lines = text.split("\n")
    first = lines.index('The first claim\'s prose stands here. <a id="r-01-001"></a>')
    ensure(lines[first + 2] == "> **R-01-001** MUST hold the first fixture obligation."
           and lines[first + 3] == "> · Accept: the first criterion is measured.",
           f"the entry renders quoted beneath its bookmark, got {lines[first:first + 4]!r}")

    second = lines.index('The second claim\'s prose stands here. <a id="r-01-002"></a>')
    beneath = "\n".join(lines[second:second + 9])
    ensure("> **R-01-002** MUST hold the second fixture obligation." in beneath
           and "> **R-01-003** MUST NOT drop the third fixture obligation." in beneath,
           f"the trace-departing entry renders beneath the bookmark it cites, got "
           f"{beneath!r}")

    recur = lines.index('The second claim recurs here. <a id="r-01-002-2"></a>')
    ensure("cited here again: R-01-002, stated in full at their own bookmarks."
           in lines[recur + 2]
           and "**R-01-002**" not in "\n".join(lines[recur:]),
           f"a repeat bookmark gets a direction-neutral pointer and never a second "
           f"copy, got {lines[recur:recur + 3]!r}")


def _doubled_run_is_byte_identical() -> None:
    view = _root() / "out" / "spec-woven.md"
    before = view.read_bytes()
    porcelain = subprocess.run(["git", "status", "--porcelain"], cwd=_root(),
                               capture_output=True, encoding="utf-8", check=False)
    done = _run(_root())
    ensure(done.returncode == 0, f"the second run exits 0, got {done.returncode}")
    ensure(view.read_bytes() == before,
           "a doubled run must land byte-identical output")
    after = subprocess.run(["git", "status", "--porcelain"], cwd=_root(),
                           capture_output=True, encoding="utf-8", check=False)
    ensure(porcelain.stdout == after.stdout,
           "the writer touches nothing but its ignored output path")


def _teardown() -> None:
    if _FLOW.stack is not None:
        _FLOW.stack.close()
        _FLOW.stack = None
        _FLOW.root = None


def cases() -> list[Case]:
    return [
        Case("weave-places-every-entry", _weave_places_every_entry, lane="host"),
        Case("doubled-run-is-byte-identical", _doubled_run_is_byte_identical,
             lane="host"),
        Case("teardown", _teardown, lane="host"),
    ]
