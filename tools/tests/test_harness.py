# SPDX-License-Identifier: Apache-2.0
"""The harness held to its own promises.

The fixture builder is what every mutating-path test stands on, so a broken
promise here is a mystery in every other module; this one makes it the first
thing the runner reports instead. It also keeps the suite non-empty from birth,
which is what lets the runner treat an empty discovery as the failure it is.
"""

import subprocess

from tests.harness import Case, ensure, sandbox_tree


def _bytes_verbatim() -> None:
    with sandbox_tree({"docs/a.md": "# a\r\nline\n", "b.txt": "b\n"}) as root:
        ensure((root / "docs" / "a.md").read_bytes() == b"# a\r\nline\n",
               "sandbox_tree must write bytes verbatim, newline translation included")
        ensure((root / "b.txt").read_bytes() == b"b\n",
               "sandbox_tree must write every file it was given")


def _index_populated() -> None:
    with sandbox_tree({"x.md": "one\n", "d/y.txt": "two\n"}) as root:
        done = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True,
                              encoding="utf-8", errors="replace", check=False, timeout=60)
        ensure(sorted(done.stdout.split()) == ["d/y.txt", "x.md"],
               f"the index holds {sorted(done.stdout.split())!r}, "
               f"not the two files the tree was given")


def _tree_vanishes() -> None:
    with sandbox_tree({"x.md": "one\n"}) as root:
        kept = root
    ensure(not kept.exists(), "the sandbox tree must vanish with its context, "
                              "git's read-only object files included")


def _ensure_raises() -> None:
    try:
        ensure(False, "expected")
    except AssertionError as err:
        if str(err) != "expected":
            raise AssertionError(f"ensure carried {err!r}, not its own message") from err
        return
    raise AssertionError("ensure(False, ...) must raise")


def cases() -> list[Case]:
    return [
        Case("bytes-verbatim", _bytes_verbatim),
        Case("index-populated", _index_populated),
        Case("tree-vanishes", _tree_vanishes),
        Case("ensure-raises", _ensure_raises),
    ]
