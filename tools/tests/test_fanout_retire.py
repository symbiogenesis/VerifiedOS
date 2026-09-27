# SPDX-License-Identifier: Apache-2.0
"""Retirement checks ownership, ancestry, retention and interrupted removal in real Git."""

import os
from collections.abc import Callable
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from tests.test_worktree import _commit, _git
from vos import fanout_retire as retire
from vos.cli import worktree

FILES = {".gitignore": "/.worktrees/\n/out/\n", "README.md": "fixture\n"}


def _worker(root: Path) -> tuple[Path, retire.LaneRecord, str, Path]:
    base = _commit(root)
    worktree.create(root, "worker", base)
    path = root / ".worktrees" / "worker"
    return path, retire.snapshot(root, path), base, root / "out" / "fanout" / "batch" / "retained"


def _refused(action: Callable[[], object], fragment: str = "") -> None:
    try:
        action()
    except retire.RetirementError as exc:
        ensure(fragment in str(exc), f"expected {fragment!r} in {exc!r}")
    else:
        raise AssertionError(f"must refuse {fragment}")


def _retains_outputs_and_repeats() -> None:
    with sandbox_tree(FILES) as root, patch.object(retire, "_guest", return_value={"retained": []}):
        path, record, revision, archive = _worker(root)
        (path / "README.md").write_text("integrated worker contribution\n", encoding="utf-8")
        _git(path, "add", "README.md")
        _commit(path, "worker contribution")
        record = retire.snapshot(root, path)
        _git(root, "merge", "--no-ff", "-m", "integrate worker", "work/worker")
        revision = _git(root, "rev-parse", "HEAD")
        output = path / "out" / "evidence.json"
        output.parent.mkdir()
        output.write_text("important evidence\n", encoding="utf-8")
        result = retire.retire(root, record, revision, archive)
        ensure(result["status"] == "retired" and not path.exists(), "clean lane is removed")
        retained = Path(str(result["archive"])) / "checkout" / "out" / "evidence.json"
        ensure(retained.read_text(encoding="utf-8") == "important evidence\n", "ignored evidence survives")
        ensure(not _git(root, "branch", "--list", "work/worker"), "merged unchanged branch is removed")
        ensure(retire.retire(root, record, revision, archive) == result, "completed receipt resumes safely")


def _dirty_and_unintegrated() -> None:
    with sandbox_tree(FILES) as root, patch.object(retire, "_guest") as native:
        path, record, revision, archive = _worker(root)
        (path / "untracked.txt").write_text("unfinished", encoding="utf-8")
        _refused(lambda: retire.retire(root, record, revision, archive), "dirty")
        (path / "untracked.txt").unlink()
        (path / "README.md").write_text("modified", encoding="utf-8")
        _refused(lambda: retire.retire(root, record, revision, archive), "dirty")
        _git(path, "add", "README.md")
        _commit(path)
        new_record = retire.snapshot(root, path)
        _refused(lambda: retire.retire(root, new_record, revision, archive))
        ensure(path.exists(), "unmerged work remains")
        native.assert_not_called()


def _changed_identity_and_locked() -> None:
    with sandbox_tree(FILES) as root, patch.object(retire, "_guest") as native:
        path, record, revision, archive = _worker(root)
        _git(root, "worktree", "lock", str(path))
        _refused(lambda: retire.retire(root, record, revision, archive), "locked")
        _git(root, "worktree", "unlock", str(path))
        _git(path, "branch", "-m", "changed-worker")
        _refused(lambda: retire.retire(root, record, revision, archive), "changed")
        native.assert_not_called()


def _host_owned_and_outside() -> None:
    with sandbox_tree(FILES) as root, patch.object(retire, "_guest") as native:
        path, record, revision, archive = _worker(root)
        result = retire.retire(root, replace(record, owned=False), revision, archive)
        ensure(result["status"] == "retained-host-managed" and path.exists(), "host lifecycle is retained")
        _refused(lambda: retire.retire(root, record, revision, root / "unowned"), "retention destination")
        outside = root / "native-managed"
        _git(root, "worktree", "add", "--detach", str(outside), revision)
        (root / ".gitignore").write_text(FILES[".gitignore"] + "/native-managed/\n", encoding="utf-8")
        _refused(lambda: retire.snapshot(root, outside), "direct child")
        saved = retire.snapshot(root, outside, owned=False)
        ensure(not saved.owned, "host-owned handoff is accepted outside default root")
        native.assert_not_called()


def _nested_repository() -> None:
    with sandbox_tree(FILES) as root, patch.object(retire, "_guest") as native:
        path, record, revision, archive = _worker(root)
        nested = path / "out" / "other-repo"
        nested.mkdir(parents=True)
        _git(nested, "init", "-q")
        _refused(lambda: retire.retire(root, record, revision, archive), "nested repository")
        ensure(nested.exists(), "ignored nested repository remains")
        native.assert_not_called()


def _interrupted_after_git_remove() -> None:
    with sandbox_tree(FILES) as root, patch.object(retire, "_guest", return_value={}):
        path, record, revision, archive = _worker(root)
        original = retire._write

        def interrupted(destination: Path, receipt: dict[str, object]) -> None:
            if receipt["phase"] == "removed":
                raise OSError("simulated process death after worktree removal")
            original(destination, receipt)

        with patch.object(retire, "_write", side_effect=interrupted):
            try:
                retire.retire(root, record, revision, archive)
            except OSError:
                pass
            else:
                raise AssertionError("interruption must occur")
        ensure(not path.exists() and bool(_git(root, "branch", "--list", "work/worker")), "removal receipt precedes Git")
        result = retire.retire(root, record, revision, archive)
        ensure(result["status"] == "retired", "resume can finish only the recorded branch")


def _branch_moved_after_removal() -> None:
    with sandbox_tree(FILES) as root, patch.object(retire, "_guest", return_value={}):
        path, record, revision, archive = _worker(root)
        original = retire._git

        def refused_branch(where: Path, *args: str, allowed: tuple[int, ...] = (0,)) -> bytes:
            if args[:2] == ("branch", "-d"):
                raise retire.RetirementError("simulated branch deletion refusal")
            return original(where, *args, allowed=allowed)

        with patch.object(retire, "_git", side_effect=refused_branch):
            _refused(lambda: retire.retire(root, record, revision, archive), "deletion refusal")
        ensure(not path.exists(), "non-forced branch refusal keeps the branch and receipt")
        changed = _commit(root)
        _git(root, "branch", "-f", "work/worker", changed)
        _refused(lambda: retire.retire(root, record, changed, archive), "branch changed")
        ensure(bool(_git(root, "branch", "--list", "work/worker")), "changed branch is retained")


def _missing_without_receipt() -> None:
    with sandbox_tree(FILES) as root, patch.object(retire, "_guest") as native:
        path, record, revision, archive = _worker(root)
        _git(root, "worktree", "remove", str(path))
        _refused(lambda: retire.retire(root, record, revision, archive), "no durable removal receipt")
        ensure(bool(_git(root, "branch", "--list", "work/worker")), "unrecorded disappearance cannot prune")
        native.assert_not_called()


def _symlink_escape() -> None:
    with sandbox_tree(FILES) as root, patch.object(retire, "_guest") as native:
        path, record, revision, archive = _worker(root)
        outside = root / "external"
        outside.mkdir()
        (outside / "valuable.txt").write_text("preserve", encoding="utf-8")
        (path / "out").symlink_to(outside, target_is_directory=True)
        _refused(lambda: retire.retire(root, record, revision, archive))
        ensure((outside / "valuable.txt").exists(), "escaping link target is never touched")
        native.assert_not_called()


def _records() -> None:
    with sandbox_tree(FILES) as root:
        _, record, _, _ = _worker(root)
        ensure(retire.validate_record(asdict(record)) == record, "saved record validates")
        _refused(lambda: retire.validate_record({**asdict(record), "owned": "yes"}), "ownership")
        _refused(lambda: retire.validate_record({**asdict(record), "lane": "../escape"}), "lane name")
        _refused(lambda: retire.validate_record({**asdict(record), "head": "HEAD"}), "commit")


def _native_outputs_and_lock() -> None:
    import fcntl  # noqa: PLC0415

    with sandbox_tree(FILES) as root, patch.object(retire.env, "filesystem", return_value="ext4"):
        lane = root / "build" / "lane-worker"
        logs = root / "logs"
        lane.mkdir(parents=True)
        logs.mkdir()
        (lane / "result.bin").write_bytes(b"proof")
        (logs / "build-worker.log").write_text("log", encoding="utf-8")
        other = logs / "build-other.log"
        other.write_text("unrelated", encoding="utf-8")
        lock = lane / "model.lock"
        lock.write_text("", encoding="utf-8")
        with lock.open() as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            _refused(lambda: retire.retain_native("worker", str(lane), str(logs), "a" * 20), "lock is active")
        ensure((lane / "result.bin").exists(), "locked native lane is unchanged")
        result = retire.retain_native("worker", str(lane), str(logs), "a" * 20)
        archive = Path(str(result["archive"]))
        ensure(not lane.exists() and (archive / "lane" / "result.bin").read_bytes() == b"proof", "native build retained")
        ensure((archive / "logs" / "build-worker.log").exists() and other.exists(), "only lane logs moved")
        ensure(retire.retain_native("worker", str(lane), str(logs), "a" * 20)["retained"] == [], "native retry is idempotent")


def _native_directory_lock() -> None:
    import fcntl  # noqa: PLC0415

    with sandbox_tree(FILES) as root, patch.object(retire.env, "filesystem", return_value="ext4"):
        lane = root / "build" / "lane-worker"
        proofs = lane / "proof-gate"
        proofs.mkdir(parents=True)
        fd = os.open(proofs, os.O_RDONLY)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            _refused(lambda: retire.retain_native("worker", str(lane), str(root / "logs"), "b" * 20), "lock is active")
        finally:
            os.close(fd)
        ensure(proofs.exists(), "proof directory lock protects native outputs")


def cases() -> list[Case]:
    return [Case("retains-outputs-and-repeats", _retains_outputs_and_repeats),
            Case("dirty-and-unintegrated", _dirty_and_unintegrated),
            Case("changed-identity-and-locked", _changed_identity_and_locked),
            Case("host-owned-and-outside", _host_owned_and_outside),
            Case("nested-repository", _nested_repository),
            Case("interrupted-after-git-remove", _interrupted_after_git_remove),
            Case("branch-moved-after-removal", _branch_moved_after_removal),
            Case("missing-without-receipt", _missing_without_receipt),
            Case("records", _records), Case("symlink-escape", _symlink_escape, lane="guest"),
            Case("native-outputs-and-lock", _native_outputs_and_lock, lane="guest"),
            Case("native-directory-lock", _native_directory_lock, lane="guest")]
