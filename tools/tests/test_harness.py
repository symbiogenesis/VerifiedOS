# SPDX-License-Identifier: Apache-2.0
"""The harness held to its own promises.

The fixture builder is what every mutating-path test stands on, so a broken
promise here is a mystery in every other module; this one makes it the first
thing the runner reports instead. It also keeps the suite non-empty from birth,
which is what lets the runner treat an empty discovery as the failure it is.
"""

import stat
import subprocess
import tempfile
from pathlib import Path

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


def _listing(admin: Path) -> dict[str, tuple[bytes, int] | None]:
    """Every entry under an administrative directory: a file's bytes and permission
    bits, or None for a directory."""
    found: dict[str, tuple[bytes, int] | None] = {}
    for dirpath, _dirnames, filenames in admin.walk():
        if dirpath != admin:
            found[dirpath.relative_to(admin).as_posix()] = None
        for name in filenames:
            path = dirpath / name
            found[path.relative_to(admin).as_posix()] = (
                path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
    return found


def _administrative_directory_is_what_init_writes() -> None:
    # The fixture writes its cached copy of what `git init` writes rather than starting
    # one per tree. A fresh init beside it must write the same entries and bytes, with
    # `git add` contributing the index and the objects alone.
    with tempfile.TemporaryDirectory(prefix="vos-test-init-") as td:
        fresh = Path(td).resolve()
        done = subprocess.run(["git", "-C", str(fresh), "init", "-q"], capture_output=True,
                              encoding="utf-8", errors="replace", check=False, timeout=60)
        ensure(done.returncode == 0, f"git init failed: {done.stderr.strip()}")
        expected = _listing(fresh / ".git")
    with sandbox_tree({"x.md": "one\n"}) as root:
        written = _listing(root / ".git")
    added = sorted(rel for rel in written.keys() - expected.keys()
                   if rel != "index" and not rel.startswith("objects/"))
    ensure(not added, f"the tree's .git carries entries init and add do not write: {added}")
    kept = {rel: entry for rel, entry in written.items() if rel in expected}
    ensure(kept == expected,
           "the tree's .git differs from a fresh init at "
           f"{sorted(rel for rel in expected if rel not in kept or kept[rel] != expected[rel])}")
    ensure("index" in written and any(rel.startswith("objects/") for rel in written
                                      if rel not in expected),
           "git add wrote no index or object into the tree's .git")


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
        Case("administrative-directory-is-what-init-writes",
             _administrative_directory_is_what_init_writes),
        Case("ensure-raises", _ensure_raises),
    ]
