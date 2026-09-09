# SPDX-License-Identifier: Apache-2.0
"""Instruction syncing preserves edits in either direction and refuses ambiguity."""

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos.cli import sync_instructions as instructions

BASE = "# Rules\n\nfirst\n\nsecond\n\nthird\n"


def _commit(root: Path) -> None:
    done = subprocess.run(["git", "-C", str(root), "-c", "user.name=Sync test", "-c",
                           "user.email=sync@example.invalid", "-c", "commit.gpgsign=false",
                           "commit", "-qm", "baseline"], capture_output=True, check=False,
                          timeout=30)
    ensure(done.returncode == 0, f"fixture commit failed: {done.stderr!r}")


def _both(root: Path) -> tuple[bytes, bytes]:
    return (root / "AGENTS.md").read_bytes(), (root / "CLAUDE.md").read_bytes()


def _refused(root: Path, *, check: bool = False, source: str | None = None) -> None:
    before = {name: path.read_bytes() for name in instructions.NAMES
              if (path := root / name).is_file()}
    try:
        instructions.sync(root, check=check, source=source)
    except instructions.SyncError:
        after = {name: path.read_bytes() for name in instructions.NAMES
                 if (path := root / name).is_file()}
        ensure(before == after, "a refused sync must preserve both sources")
        return
    raise AssertionError("sync should have refused")


def _directions() -> None:
    for changed in instructions.NAMES:
        with sandbox_tree(dict.fromkeys(instructions.NAMES, BASE)) as root:
            _commit(root)
            content = BASE.replace("first", "new first").encode()
            (root / changed).write_bytes(content)
            _refused(root, check=True)
            instructions.sync(root)
            ensure(_both(root) == (content, content), f"edits from {changed} must win")
            instructions.sync(root, check=True)


def _repeated_edits() -> None:
    with sandbox_tree(dict.fromkeys(instructions.NAMES, BASE)) as root:
        _commit(root)
        for name, replacement in (("AGENTS.md", "one"), ("CLAUDE.md", "two"),
                                  ("AGENTS.md", "three"), ("CLAUDE.md", "four")):
            changed = BASE.replace("first", replacement)
            (root / name).write_bytes(changed.encode())
            instructions.sync(root)
            ensure(_both(root) == (changed.encode(), changed.encode()),
                   "successive same-line edits must use the latest synchronized baseline")


def _new_head() -> None:
    with sandbox_tree(dict.fromkeys(instructions.NAMES, BASE)) as root:
        _commit(root)
        (root / "AGENTS.md").write_bytes(BASE.replace("first", "local baseline").encode())
        instructions.sync(root)
        newer = BASE.replace("first", "committed baseline")
        for name in instructions.NAMES:
            (root / name).write_bytes(newer.encode())
        done = subprocess.run(["git", "-C", str(root), "add", "--", *instructions.NAMES],
                              capture_output=True, check=False, timeout=30)
        ensure(done.returncode == 0, "new baseline fixture must stage")
        _commit(root)
        changed = newer.replace("committed baseline", "after commit").encode()
        (root / "CLAUDE.md").write_bytes(changed)
        instructions.sync(root)
        ensure(_both(root) == (changed, changed), "a new HEAD must invalidate the local checkpoint")


def _damaged_checkpoint() -> None:
    with sandbox_tree(dict.fromkeys(instructions.NAMES, BASE)) as root:
        _commit(root)
        (root / "AGENTS.md").write_bytes(BASE.replace("first", "local baseline").encode())
        instructions.sync(root)
        state = root / instructions.CHECKPOINT
        state.write_bytes(state.read_bytes().replace(b'"sha256": "', b'"sha256": "damaged'))
        changed = BASE.replace("first", "further edit").encode()
        (root / "CLAUDE.md").write_bytes(changed)
        _refused(root)
        instructions.sync(root, source="CLAUDE.md")
        ensure(_both(root) == (changed, changed), "an explicit source repairs a corrupt checkpoint")
        state.write_bytes(b"invalid json")
        instructions.sync(root)
        ensure(instructions._checkpoint(root, instructions._head(root)) == changed,
               "identical files repair an invalid checkpoint without guessing")


def _merge_and_conflict() -> None:
    with sandbox_tree(dict.fromkeys(instructions.NAMES, BASE)) as root:
        _commit(root)
        (root / "AGENTS.md").write_bytes(BASE.replace("first", "changed first").encode())
        (root / "CLAUDE.md").write_bytes(BASE.replace("third", "changed third").encode())
        instructions.sync(root)
        expected = BASE.replace("first", "changed first").replace("third", "changed third").encode()
        ensure(_both(root) == (expected, expected), "disjoint edits must both survive")
        (root / "AGENTS.md").write_bytes(BASE.replace("first", "one choice").encode())
        (root / "CLAUDE.md").write_bytes(BASE.replace("first", "other choice").encode())
        _refused(root)
        instructions.sync(root, source="CLAUDE.md")
        expected = BASE.replace("first", "other choice").encode()
        ensure(_both(root) == (expected, expected), "explicit resolution chooses the named source")


def _bootstrap() -> None:
    with sandbox_tree({"AGENTS.md": BASE}) as root:
        _refused(root, check=True)
        _refused(root, source="CLAUDE.md")
        instructions.sync(root)
        ensure(_both(root) == (BASE.encode(), BASE.encode()), "missing peer is created")
        (root / "AGENTS.md").unlink()
        instructions.sync(root)
        ensure(_both(root) == (BASE.encode(), BASE.encode()), "either missing peer is restored")
        (root / "AGENTS.md").unlink()
        (root / "CLAUDE.md").unlink()
        _refused(root)
    with sandbox_tree({"AGENTS.md": "one\n", "CLAUDE.md": "two\n"}) as root:
        _refused(root)
        _commit(root)
        _refused(root)
        instructions.sync(root, source="AGENTS.md")
        ensure(_both(root) == (b"one\n", b"one\n"), "explicit source bootstraps unequal history")


def _exact_bytes_and_noop() -> None:
    with sandbox_tree(dict.fromkeys(instructions.NAMES, BASE)) as root:
        _commit(root)
        content = b"# Rules\r\n\r\nWindows bytes, without final newline"
        (root / "AGENTS.md").write_bytes(content)
        instructions.sync(root)
        ensure(_both(root) == (content, content), "sync must preserve CRLF and final newline exactly")
        with patch.object(instructions, "_replace", side_effect=AssertionError("unneeded write")):
            instructions.sync(root)
            instructions.sync(root, check=True)
        with patch.object(instructions, "_git", side_effect=AssertionError("read-only check used Git")):
            instructions.sync(root, check=True)


def _unsafe_paths() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        root = Path(td)
        (root / "AGENTS.md").mkdir()
        (root / "CLAUDE.md").write_bytes(b"valid\n")
        _refused(root)
    with sandbox_tree(dict.fromkeys(instructions.NAMES, BASE)) as root:
        _refused(root, source="../elsewhere")
        _refused(root, check=True, source="AGENTS.md")


def _symlink() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        base = Path(td)
        root = base / "repo"
        root.mkdir()
        outside = base / "outside.md"
        outside.write_bytes(b"outside\n")
        (root / "AGENTS.md").symlink_to(outside)
        (root / "CLAUDE.md").write_bytes(b"inside\n")
        _refused(root)
        ensure(outside.read_bytes() == b"outside\n", "a symlink cannot cause an outside write")
        (root / "AGENTS.md").unlink()
        (root / "AGENTS.md").write_bytes(b"source\n")
        store = base / "outside-store"
        store.mkdir()
        (root / "out").symlink_to(store, target_is_directory=True)
        _refused(root, source="AGENTS.md")
        ensure(not list(store.iterdir()), "checkpoint publication cannot escape the root")


def _concurrent_edit() -> None:
    with sandbox_tree(dict.fromkeys(instructions.NAMES, BASE)) as root:
        _commit(root)
        (root / "AGENTS.md").write_bytes(b"planned\n")
        read = instructions._read
        calls = 0

        def raced(where: Path) -> dict[str, bytes | None]:
            nonlocal calls
            calls += 1
            if calls == 2:
                (root / "CLAUDE.md").write_bytes(b"concurrent\n")
            return read(where)

        with patch.object(instructions, "_read", side_effect=raced):
            try:
                instructions.sync(root)
            except instructions.SyncError:
                pass
            else:
                raise AssertionError("concurrent edit must refuse")
        ensure(_both(root) == (b"planned\n", b"concurrent\n"), "concurrent bytes must survive")
        ensure(not list(root.glob(".instruction-sync-*")), "temporary output is cleaned")


def _publication_failure() -> None:
    with sandbox_tree(dict.fromkeys(instructions.NAMES, BASE)) as root:
        _commit(root)
        (root / "AGENTS.md").write_bytes(b"complete\n")
        before = _both(root)
        with patch.object(instructions, "_replace", side_effect=OSError("cannot replace")):
            try:
                instructions.sync(root)
            except OSError:
                pass
            else:
                raise AssertionError("failed publication must fail")
        ensure(_both(root) == before, "failed replacement preserves originals")
        ensure(not list(root.glob(".instruction-sync-*")), "failed output is cleaned")


def _cli() -> None:
    with (sandbox_tree({"AGENTS.md": BASE}) as root,
          patch.object(instructions, "find_root", return_value=root)):
        ensure(instructions.main(["--check"]) == 1, "missing peer fails CLI check")
        ensure(instructions.main([]) == 0, "default CLI sync creates missing peer")
        ensure(instructions.main(["--check"]) == 0, "matching CLI check passes")


def cases() -> list[Case]:
    return [Case("directions", _directions), Case("repeated-edits", _repeated_edits),
            Case("new-head", _new_head), Case("damaged-checkpoint", _damaged_checkpoint),
            Case("merge-and-conflict", _merge_and_conflict),
            Case("bootstrap", _bootstrap), Case("exact-bytes-and-noop", _exact_bytes_and_noop),
            Case("unsafe-paths", _unsafe_paths), Case("symlink", _symlink, lane="guest"),
            Case("concurrent-edit", _concurrent_edit),
            Case("publication-failure", _publication_failure), Case("cli", _cli)]
