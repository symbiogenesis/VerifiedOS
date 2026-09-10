# SPDX-License-Identifier: Apache-2.0
"""One shared instruction source, explicit safe migration, and a portable import."""

import os
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos.checks import instructions as check_instructions
from vos.cli import sync_instructions as instructions

BASE = b"# Rules\n\nShared instructions.\n"


@contextmanager
def _tree(files: dict[str, bytes]) -> Iterator[Path]:
    """The instruction contract itself works without a Git repository."""
    with tempfile.TemporaryDirectory(prefix="vos-test-instructions-") as td:
        root = Path(td).resolve()
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        yield root


def _both(root: Path) -> tuple[bytes, bytes]:
    return (root / "AGENTS.md").read_bytes(), (root / "CLAUDE.md").read_bytes()


def _refused(root: Path, *, check: bool = False, source: str | None = None,
             migrate: bool = False) -> None:
    before = {name: path.read_bytes() for name in instructions.NAMES
              if (path := root / name).is_file()}
    try:
        instructions.sync(root, check=check, source=source, migrate=migrate)
    except instructions.SyncError:
        after = {name: path.read_bytes() for name in instructions.NAMES
                 if (path := root / name).is_file()}
        ensure(before == after, "a refused operation must preserve both instruction files")
        return
    raise AssertionError("instruction validation should have refused")


def _source_edits() -> None:
    with _tree({"AGENTS.md": BASE, "CLAUDE.md": instructions.IMPORT}) as root:
        for text in (BASE, b"# Updated rules\n", b"# Windows\r\nNo final newline"):
            (root / "AGENTS.md").write_bytes(text)
            instructions.sync(root)
            instructions.sync(root, check=True)
            ensure(_both(root) == (text, instructions.IMPORT),
                   "source edits must require no copying or import rewrite")
        ensure(not (root / "out").exists(), "validation must create no checkpoint or output tree")


def _exact_bytes_and_noop() -> None:
    for imported in instructions.IMPORTS:
        with _tree({"AGENTS.md": BASE, "CLAUDE.md": imported}) as root:
            paths = [root / name for name in instructions.NAMES]
            for path in paths:
                os.utime(path, ns=(1_000_000_000, 1_000_000_000))
            times = [path.stat().st_mtime_ns for path in paths]
            with patch.object(instructions, "_publish_import",
                              side_effect=AssertionError("unneeded write")):
                instructions.sync(root)
                instructions.sync(root, check=True)
                instructions.sync(root, migrate=True)
            ensure(_both(root) == (BASE, imported), "LF and CRLF imports retain exact bytes")
            ensure([path.stat().st_mtime_ns for path in paths] == times,
                   "no-op validation preserves both file mtimes")


def _bootstrap() -> None:
    with _tree({"AGENTS.md": BASE}) as root:
        _refused(root, check=True)
        instructions.sync(root)
        ensure(_both(root) == (BASE, instructions.IMPORT), "a missing import is created")
        (root / "AGENTS.md").unlink()
        _refused(root)
        _refused(root, migrate=True)
        ensure(not (root / "AGENTS.md").exists(), "an import never becomes the shared source")
        (root / "CLAUDE.md").unlink()
        _refused(root)
    for content in (b"", b" \t\r\n", b"\xef\xbb\xbf\n", b"\xffinvalid"):
        with _tree({"AGENTS.md": content}) as root:
            _refused(root)
            ensure(not (root / "CLAUDE.md").exists(), "invalid source cannot bootstrap an import")


def _migration() -> None:
    for source in (BASE, b"# Windows\r\nSame bytes without final newline"):
        with _tree(dict.fromkeys(instructions.NAMES, source)) as root:
            _refused(root)
            _refused(root, check=True)
            instructions.sync(root, migrate=True)
            ensure(_both(root) == (source, instructions.IMPORT),
                   "explicit migration replaces only an exactly equal legacy copy")
            instructions.sync(root, check=True)
    with _tree({"AGENTS.md": b"rules\n", "CLAUDE.md": b"rules\r\n"}) as root:
        _refused(root, migrate=True)


def _unexpected_imports() -> None:
    invalid = (b"", b"@AGENTS.md", b"@AGENTS.md\n\n", b" @AGENTS.md\n",
               b"@../AGENTS.md\n", b"@AGENTS.md\nExtra rules.\n", b"@CLAUDE.md\n",
               b"divergent legacy instructions\n", b"\xffinvalid")
    for content in invalid:
        with _tree({"AGENTS.md": BASE, "CLAUDE.md": content}) as root:
            _refused(root)
            _refused(root, check=True)
            _refused(root, migrate=True)


def _retired_source_choice() -> None:
    with _tree({"AGENTS.md": BASE, "CLAUDE.md": b"independent edit\n"}) as root:
        for source in (*instructions.NAMES, "../elsewhere"):
            _refused(root, source=source)
        _refused(root, check=True, migrate=True)


def _unsafe_paths() -> None:
    for directory in instructions.NAMES:
        with _tree({name: BASE if name == "AGENTS.md" else instructions.IMPORT
                    for name in instructions.NAMES if name != directory}) as root:
            (root / directory).mkdir()
            _refused(root)
            _refused(root, migrate=True)


def _symlink() -> None:
    for linked in instructions.NAMES:
        with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
            base = Path(td)
            root = base / "repo"
            root.mkdir()
            outside = base / "outside.md"
            outside.write_bytes(BASE if linked == "AGENTS.md" else instructions.IMPORT)
            for name in instructions.NAMES:
                if name == linked:
                    (root / name).symlink_to(outside)
                else:
                    (root / name).write_bytes(BASE if name == "AGENTS.md" else instructions.IMPORT)
            before = outside.read_bytes()
            _refused(root)
            _refused(root, migrate=True)
            ensure(outside.read_bytes() == before, "validation cannot write through a symlink")
            (root / linked).unlink()
            (root / linked).symlink_to(base / "missing.md")
            _refused(root)


def _obsolete_checkpoint() -> None:
    with _tree({"AGENTS.md": BASE, "CLAUDE.md": instructions.IMPORT,
                "out/instructions-sync.json": b"invalid obsolete state"}) as root:
        instructions.sync(root)
        ensure((root / "out/instructions-sync.json").read_bytes() == b"invalid obsolete state",
               "old checkpoints have no role and are not rewritten")


def _concurrent_edit_to(changed: str) -> None:
    with _tree(dict.fromkeys(instructions.NAMES, BASE)) as root:
        read = instructions._read
        calls = 0

        def raced(where: Path) -> dict[str, bytes | None]:
            nonlocal calls
            calls += 1
            if calls == 2:
                (root / changed).write_bytes(b"concurrent\n")
            return read(where)

        with patch.object(instructions, "_read", side_effect=raced):
            try:
                instructions.sync(root, migrate=True)
            except instructions.SyncError:
                pass
            else:
                raise AssertionError("concurrent edit must refuse")
        ensure((root / changed).read_bytes() == b"concurrent\n",
               "concurrent source or import bytes must survive")
        ensure(not list(root.glob(".instruction-sync-*")), "temporary output is cleaned")


def _concurrent_edit() -> None:
    for changed in instructions.NAMES:
        _concurrent_edit_to(changed)


def _concurrent_creation() -> None:
    with _tree({"AGENTS.md": BASE}) as root:
        link = os.link

        def raced(temporary: Path, target: Path) -> None:
            target.write_bytes(b"concurrent\n")
            link(temporary, target)

        with patch.object(instructions, "_create", side_effect=raced):
            try:
                instructions.sync(root)
            except FileExistsError:
                pass
            else:
                raise AssertionError("concurrent import creation must refuse")
        ensure(_both(root) == (BASE, b"concurrent\n"), "newly created instructions survive")
        ensure(not list(root.glob(".instruction-sync-*")), "temporary output is cleaned")


def _publication_failure() -> None:
    with _tree(dict.fromkeys(instructions.NAMES, BASE)) as root:
        before = _both(root)
        with patch.object(instructions, "_replace", side_effect=OSError("cannot replace")):
            try:
                instructions.sync(root, migrate=True)
            except OSError:
                pass
            else:
                raise AssertionError("failed publication must fail")
        ensure(_both(root) == before, "failed replacement preserves originals")
        ensure(not list(root.glob(".instruction-sync-*")), "failed output is cleaned")


def _git(root: Path, *args: str, content: bytes | None = None) -> bytes:
    done = subprocess.run(["git", "-C", str(root), *args], input=content,
                          capture_output=True, check=False, timeout=30)
    ensure(done.returncode == 0, f"fixture git command failed: {done.stderr!r}")
    return done.stdout


def _index_modes() -> None:
    with sandbox_tree({"AGENTS.md": BASE.decode(), "CLAUDE.md": instructions.IMPORT.decode()}) as root:
        ensure(not check_instructions._index_faults(root), "tracked regular files pass")
        _git(root, "rm", "--cached", "--", "CLAUDE.md")
        ensure(len(check_instructions._index_faults(root)) == 1, "untracked import fails")
        _git(root, "add", "--", "CLAUDE.md")
        blob = _git(root, "hash-object", "-w", "--stdin", content=b"elsewhere.md").decode().strip()
        _git(root, "update-index", "--cacheinfo", f"120000,{blob},CLAUDE.md")
        ensure(len(check_instructions._index_faults(root)) == 1,
               "a staged symlink fails even with a regular working file")
        _git(root, "update-index", "--cacheinfo", f"160000,{blob},CLAUDE.md")
        ensure(len(check_instructions._index_faults(root)) == 1, "a gitlink fails")
        _git(root, "update-index", "--force-remove", "--", "CLAUDE.md")
        stages = f"100644 {blob} 1\tCLAUDE.md\n100644 {blob} 2\tCLAUDE.md\n"
        _git(root, "update-index", "--index-info", content=stages.encode())
        ensure(len(check_instructions._index_faults(root)) == 1, "unresolved index stages fail")


def _cli() -> None:
    with (_tree({"AGENTS.md": BASE}) as root,
          patch.object(instructions, "find_root", return_value=root)):
        ensure(instructions.main(["--check"]) == 1, "missing import fails CLI check")
        ensure(instructions.main([]) == 0, "default CLI creates missing import")
        ensure(instructions.main(["--check"]) == 0, "canonical CLI check passes")
        ensure(instructions.main(["--from", "CLAUDE.md"]) == 1, "retired CLI choice fails")
        (root / "CLAUDE.md").write_bytes(BASE)
        ensure(instructions.main([]) == 1, "default CLI requires explicit legacy migration")
        ensure(instructions.main(["--migrate"]) == 0, "explicit CLI migration succeeds")


def cases() -> list[Case]:
    return [Case("source-edits", _source_edits), Case("exact-bytes-and-noop", _exact_bytes_and_noop),
            Case("bootstrap", _bootstrap), Case("migration", _migration),
            Case("unexpected-imports", _unexpected_imports),
            Case("retired-source-choice", _retired_source_choice),
            Case("unsafe-paths", _unsafe_paths), Case("symlink", _symlink, lane="guest"),
            Case("obsolete-checkpoint", _obsolete_checkpoint),
            Case("concurrent-edit", _concurrent_edit), Case("concurrent-creation", _concurrent_creation),
            Case("publication-failure", _publication_failure),
            Case("index-modes", _index_modes), Case("cli", _cli)]
