# SPDX-License-Identifier: Apache-2.0
"""Worktree provisioning preserves isolation and refuses stale or escaping destinations."""

import io
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path, PureWindowsPath
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from vos.cli import worktree

FILES = {".gitignore": "/.worktrees/\n", "README.md": "fixture\n"}


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), "-c", "user.name=Worktree test", "-c",
                           "user.email=worktree@example.invalid", "-c", "commit.gpgsign=false",
                           *args], capture_output=True, check=False, timeout=60)
    ensure(done.returncode == 0, f"fixture Git failed: {done.stderr!r}")
    return done.stdout.decode("utf-8").strip()


def _commit(root: Path, message: str = "fixture") -> str:
    _git(root, "commit", "--allow-empty", "-qm", message)
    return _git(root, "rev-parse", "HEAD")


def _refused(action: Callable[[], object], fragment: str) -> None:
    try:
        action()
    except worktree.WorktreeError as err:
        ensure(fragment in str(err), f"expected {fragment!r} in {err!r}")
    else:
        raise AssertionError(f"must refuse: {fragment}")


def _create_and_nested() -> None:
    with sandbox_tree(FILES) as root:
        base = _commit(root)
        first = worktree.create(root, "first-lane", base)
        path = root / ".worktrees" / "first-lane"
        ensure(first == {"path": str(path), "base": base, "head": base,
                         "branch": "work/first-lane", "exact_base": True},
               "dispatch receives the exact commit and assigned absolute checkout")
        advanced = _commit(path)
        second = worktree.create(path, "second-lane", "HEAD", branch="review/second-lane")
        ensure(second["path"] == str(root / ".worktrees" / "second-lane"),
               "nested provisioning resolves the primary's root rather than nesting")
        ensure(second["base"] == advanced and second["head"] == advanced,
               "symbolic base resolves in the invoking lane, not the primary checkout")
        ensure(not (path / ".worktrees").exists(), "no worktree is placed inside another lane")
        ensure(not _git(root, "status", "--porcelain"), "ignored lanes do not dirty the primary")


def _freshness() -> None:
    with sandbox_tree(FILES) as root:
        base = _commit(root)
        _git(root, "branch", "work/old-branch")
        _refused(lambda: worktree.create(root, "old-branch", base), "branch already exists")
        destination = root / ".worktrees" / "empty-lane"
        destination.mkdir(parents=True)
        _refused(lambda: worktree.create(root, "empty-lane", base), "path already exists")
        worktree.create(root, "active-lane", base)
        _refused(lambda: worktree.create(root, "active-lane", base), "path already exists")
        ensure(not _git(root, "branch", "--list", "work/empty-lane"),
               "refusing a preexisting path cannot create a branch")


def _stale_registration() -> None:
    with sandbox_tree(FILES) as root:
        base = _commit(root)
        created = root / ".worktrees" / "stale-lane"
        worktree.create(root, "stale-lane", base)
        moved = root / ".worktrees" / "moved-lane"
        created.rename(moved)
        _refused(lambda: worktree.create(root, "stale-lane", base, branch="work/new-branch"),
                 "already registered")
        ensure(not _git(root, "branch", "--list", "work/new-branch"),
               "stale registration cannot allocate another branch")


def _ignore_required() -> None:
    with sandbox_tree({"README.md": "fixture\n"}) as root:
        base = _commit(root)
        _refused(lambda: worktree.create(root, "valid-lane", base), ".gitignore")
        ensure(not (root / ".worktrees").exists(), "missing ignore is rejected before writes")


def _native_ancestor_isolation() -> None:
    with sandbox_tree(FILES) as root:
        base = _commit(root)
        native = root / "native-child"
        _git(root, "worktree", "add", "--detach", str(native), base)
        _refused(lambda: worktree.verify(root, native, base), "must ignore /native-child/")
        (root / ".gitignore").write_text("/.worktrees/\n/native-child/\n", encoding="utf-8")
        worktree.verify(root, native, base, exact=True)
        nested = native / "inner-child"
        _git(root, "worktree", "add", "--detach", str(nested), base)
        _refused(lambda: worktree.verify(root, nested, base), "must ignore /inner-child/")
        (native / ".gitignore").write_text("/.worktrees/\n/inner-child/\n", encoding="utf-8")
        worktree.verify(root, nested, base, exact=True)
        blob = _git(root, "rev-parse", "HEAD:README.md")
        _git(native, "update-index", "--add", "--cacheinfo", f"100644,{blob},inner-child/README.md")
        _refused(lambda: worktree.verify(root, nested, base), "tracks entries")


def _tracked_destination() -> None:
    with sandbox_tree(FILES) as root:
        base = _commit(root)
        blob = _git(root, "rev-parse", "HEAD:README.md")
        _git(root, "update-index", "--add", "--cacheinfo", f"100644,{blob},.worktrees/staged-lane/README.md")
        _refused(lambda: worktree.create(root, "staged-lane", base), "tracks entries")
        ensure(not (root / ".worktrees").exists(), "staged missing contents refuse before creating directories")
        ensure(not _git(root, "branch", "--list", "work/staged-lane"), "staged contents cannot allocate a branch")
        worktree.create(root, "other-lane", base)
        path = root / ".worktrees" / "other-lane"
        _git(root, "update-index", "--add", "--cacheinfo", f"160000,{base},.worktrees/other-lane")
        _refused(lambda: worktree.verify(root, path, base), "tracks entries")


def _git_dir_override() -> None:
    with sandbox_tree(FILES) as root, sandbox_tree(FILES) as foreign:
        base = _commit(root)
        _commit(foreign, "different repository HEAD")
        created = worktree.create(root, "override-lane", base)
        path = Path(str(created["path"]))
        _commit(path, "different worker HEAD")
        before = [_git(where, "show-ref") for where in (root, foreign)]
        script = ("import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
                  "from vos.cli import worktree; worktree.find_root = lambda: Path(sys.argv[2]); "
                  "raise SystemExit(worktree.main(sys.argv[3:]))")
        for args in (["create", "blocked-lane", "--base", "HEAD"],
                     ["verify", str(path), "--base", base, "--exact"]):
            done = subprocess.run([sys.executable, "-c", script, str(TOOLS), str(root), *args],
                                  cwd=root, env={**os.environ, "VOS_GIT_DIR": str(foreign / ".git")},
                                  capture_output=True, text=True, check=False, timeout=60)
            ensure(done.returncode == 1 and "unset VOS_GIT_DIR" in done.stderr,
                   "an administrative override must fail with guidance before interpreting any checkout")
        ensure(before == [_git(where, "show-ref") for where in (root, foreign)],
               "override refusal preserves both repositories' refs")
        ensure(not (root / ".worktrees" / "blocked-lane").exists(), "override cannot allocate a checkout")


def _relative_links() -> None:
    with sandbox_tree(FILES) as root:
        base = _commit(root)
        worktree.create(root, "relative-lane", base)
        path = root / ".worktrees" / "relative-lane"
        forward = (path / ".git").read_text(encoding="utf-8").removeprefix("gitdir: ").strip()
        ensure(not Path(forward).is_absolute() and not PureWindowsPath(forward).is_absolute(),
               "new .git pointer must be relative across Windows and WSL")
        admin = (path / forward).resolve()
        backward = (admin / "gitdir").read_text(encoding="utf-8").strip()
        ensure(not Path(backward).is_absolute() and not PureWindowsPath(backward).is_absolute(),
               "new administrative backlink must also be relative")
        ensure((admin / backward).resolve() == path / ".git", "relative backlink locates its own checkout")
        records = worktree.registered(root)
        records[-1] = worktree.Worktree(str(path), base, "work/relative-lane", prunable=True)
        with patch.object(worktree, "registered", return_value=records):
            worktree.verify(root, path, base, branch="work/relative-lane", exact=True)


def _wrong_backlink() -> None:
    with sandbox_tree(FILES) as root:
        base = _commit(root)
        worktree.create(root, "first-backlink", base)
        worktree.create(root, "second-backlink", base)
        first = root / ".worktrees" / "first-backlink"
        second = root / ".worktrees" / "second-backlink"
        admin = _git(first, "rev-parse", "--absolute-git-dir")
        (Path(admin) / "gitdir").write_text(f"{(second / '.git').as_posix()}\n", encoding="utf-8")
        _refused(lambda: worktree.verify(root, first, base), "not an available dedicated worktree")


def _legacy_windows_paths() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-legacy-path-") as td:
        root = Path(td).resolve()
        admin = root / ".git" / "worktrees" / "legacy-lane"
        admin.mkdir(parents=True)
        pointer = admin / "gitdir"
        pointer.write_text("C:/legacy/lane/.git\n", encoding="utf-8")
        malformed = admin / "C:" / "legacy" / "lane"
        translated = root / "actual-lane"
        with patch.object(worktree, "_windows_path", return_value=translated) as bridge:
            ensure(worktree._path(str(malformed)) == translated, "backlink corroborates Windows suffix")
            bridge.assert_called_once_with("C:/legacy/lane")
        pointer.write_text("C:/different/lane/.git\n", encoding="utf-8")
        with patch.object(worktree, "_windows_path") as bridge:
            ensure(worktree._path(str(malformed)) == malformed, "uncorroborated suffix stays native")
            bridge.assert_not_called()
        malformed.mkdir(parents=True)
        pointer.write_text("C:/legacy/lane/.git\n", encoding="utf-8")
        with patch.object(worktree, "_windows_path") as bridge:
            ensure(worktree._path(str(malformed)) == malformed, "existing colon-containing native path wins")
            bridge.assert_not_called()


def _portable_names() -> None:
    with sandbox_tree(FILES) as root:
        base = _commit(root)
        for name in ("../escape", "nested/lane", "with\\separator", "CON", "con", "aux",
                     "lpt1", "com9", "MixedCase", "-option", "dot.", "white space", "x" * 81):
            _refused(lambda name=name: worktree.create(root, name, base), "lane must")
        _refused(lambda: worktree.create(root, "valid-lane", base, branch="work/con"),
                 "Windows-reserved")
        _refused(lambda: worktree.create(root, "valid-lane", "--all"), "--base")
        ensure(not (root / ".worktrees").exists(), "bad names cannot write a worktree root")


def _native_and_progressed() -> None:
    with sandbox_tree(FILES) as root, tempfile.TemporaryDirectory(prefix="vos-native-") as td:
        base = _commit(root)
        native = Path(td).resolve() / "native checkout"
        _git(root, "worktree", "add", "--detach", str(native), base)
        verified = worktree.verify(root, native, base, exact=True)
        ensure(verified["branch"] is None, "an assigned detached application worktree is valid")
        next_head = _commit(native, "native progress")
        advanced = worktree.verify(root, native, base)
        ensure(advanced["head"] == next_head and advanced["exact_base"] is False,
               "progressed worktrees report HEAD and ancestor-only base evidence")
        _refused(lambda: worktree.verify(root, native, base, exact=True), "expected exact base")
        _refused(lambda: worktree.verify(root, native, base, branch="work/expected"),
                 "expected branch")
        _refused(lambda: worktree.verify(root, root, base), "dedicated worktree")
        _refused(lambda: worktree.verify(root, Path("relative"), base), "absolute")
        unrelated = _commit(root, "unrelated primary progress")
        _refused(lambda: worktree.verify(root, native, unrelated), "merge-base")


def _foreign_repository() -> None:
    with sandbox_tree(FILES) as root, sandbox_tree(FILES) as foreign:
        base = _commit(root)
        _commit(foreign)
        _refused(lambda: worktree.verify(root, foreign, base), "dedicated worktree")


def _replaced_registration() -> None:
    with sandbox_tree(FILES) as root, sandbox_tree(FILES) as foreign:
        base = _commit(root)
        _commit(foreign)
        worktree.create(root, "replaced-lane", base)
        path = root / ".worktrees" / "replaced-lane"
        pointer = path / ".git"
        # Git hides this file on Windows; reopen it without CREATE_ALWAYS.
        with pointer.open("r+b") as handle:
            handle.write(f"gitdir: {(foreign / '.git').as_posix()}\n".encode())
            handle.truncate()
        _refused(lambda: worktree.verify(root, path, base), "different repository")


def _symlink() -> None:
    with sandbox_tree(FILES) as root, tempfile.TemporaryDirectory(prefix="vos-outside-") as td:
        base = _commit(root)
        outside = Path(td).resolve()
        link = root / ".worktrees"
        link.symlink_to(outside, target_is_directory=True)
        _refused(lambda: worktree.create(root, "safe-lane", base), "must not redirect")
        ensure(not list(outside.iterdir()), "a symlink cannot write outside the primary")
        link.unlink()
        link.mkdir()
        target = link / "safe-lane"
        target.symlink_to(outside / "missing", target_is_directory=True)
        _refused(lambda: worktree.create(root, "safe-lane", base), "path already exists")
        target.unlink()


def _junction() -> None:
    with sandbox_tree(FILES) as root, tempfile.TemporaryDirectory(prefix="vos-outside-") as td:
        base = _commit(root)
        outside = Path(td).resolve()
        link = root / ".worktrees"
        done = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                              capture_output=True, check=False, timeout=30)
        ensure(done.returncode == 0, f"junction fixture failed: {done.stderr!r}")
        try:
            _refused(lambda: worktree.create(root, "safe-lane", base), "must not redirect")
            ensure(not list(outside.iterdir()), "a junction cannot write outside the primary")
        finally:
            link.rmdir()


def _cli_json() -> None:
    with sandbox_tree(FILES) as root, patch.object(worktree, "find_root", return_value=root):
        base = _commit(root)
        output = io.StringIO()
        with redirect_stdout(output):
            ensure(worktree.main(["create", "json-lane", "--base", base, "--json"]) == 0,
                   "create CLI succeeds")
        created = json.loads(output.getvalue())
        output = io.StringIO()
        with redirect_stdout(output):
            ensure(worktree.main(["verify", created["path"], "--base", base,
                                  "--exact", "--json"]) == 0, "verify CLI succeeds")
        ensure(json.loads(output.getvalue()) == created, "verify JSON agrees with creation")
        output = io.StringIO()
        with redirect_stdout(output):
            ensure(worktree.main(["list", "--json"]) == 0, "list CLI succeeds")
        listed = json.loads(output.getvalue())
        ensure(listed["primary"] == str(root) and listed["root"] == str(root / ".worktrees"),
               "list exposes absolute primary and default worktree root")
        ensure(len(listed["worktrees"]) == 2, "list includes both primary and worker")
        with redirect_stderr(io.StringIO()):
            ensure(worktree.main(["create", "json-lane", "--base", base]) == 1,
                   "a refused CLI action exits one")


def cases() -> list[Case]:
    return [Case("create-and-nested", _create_and_nested), Case("freshness", _freshness),
            Case("stale-registration", _stale_registration), Case("ignore-required", _ignore_required),
            Case("native-ancestor-isolation", _native_ancestor_isolation),
            Case("tracked-destination", _tracked_destination), Case("git-dir-override", _git_dir_override),
            Case("relative-links", _relative_links), Case("wrong-backlink", _wrong_backlink),
            Case("legacy-windows-paths", _legacy_windows_paths, lane="guest"),
            Case("portable-names", _portable_names), Case("native-and-progressed", _native_and_progressed),
            Case("foreign-repository", _foreign_repository),
            Case("replaced-registration", _replaced_registration),
            Case("symlink", _symlink, lane="guest"),
            Case("junction", _junction, lane="host"), Case("cli-json", _cli_json)]
