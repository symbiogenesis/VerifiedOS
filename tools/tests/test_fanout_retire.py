# SPDX-License-Identifier: Apache-2.0
"""Retirement checks ownership, ancestry, retention and interrupted removal in real Git."""

import ast
import os
import sys
from collections.abc import Callable
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure, sandbox_tree
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


def _hold(fd: int) -> None:
    """Take the nonblocking exclusive `flock` a native run holds on `fd`, as the cases
    below do to stand in for an active run. POSIX-only, so these cases are the
    guest's and win32 is refused before the deferred import."""
    if sys.platform == "win32":
        raise AssertionError("flock is POSIX-only; the native lock cases run in the guest")
    import fcntl  # noqa: PLC0415
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def _native_outputs_and_lock() -> None:
    with sandbox_tree(FILES) as root, patch.object(retire.env, "filesystem", return_value="ext4"):
        lane = root / "build" / "lane-worker"
        logs = root / "logs"
        lane.mkdir(parents=True)
        logs.mkdir()
        (lane / "result.bin").write_bytes(b"proof")
        (logs / "model-build-worker.log").write_text("log", encoding="utf-8")
        other = logs / "build-other.log"
        other.write_text("unrelated", encoding="utf-8")
        lock = lane / "model.lock"
        lock.write_text("", encoding="utf-8")
        with lock.open() as handle:
            _hold(handle.fileno())
            _refused(lambda: retire.retain_native("worker", str(lane), str(logs), "a" * 20), "lock is active")
        ensure((lane / "result.bin").exists(), "locked native lane is unchanged")
        result = retire.retain_native("worker", str(lane), str(logs), "a" * 20)
        archive = Path(str(result["archive"]))
        ensure(not lane.exists() and (archive / "lane" / "result.bin").read_bytes() == b"proof", "native build retained")
        ensure((archive / "logs" / "model-build-worker.log").exists() and other.exists(), "only lane logs moved")
        ensure(retire.retain_native("worker", str(lane), str(logs), "a" * 20)["retained"] == [], "native retry is idempotent")


def _native_directory_lock() -> None:
    with sandbox_tree(FILES) as root, patch.object(retire.env, "filesystem", return_value="ext4"):
        lane = root / "build" / "lane-worker"
        proofs = lane / "proof-gate"
        proofs.mkdir(parents=True)
        fd = os.open(proofs, os.O_RDONLY)
        try:
            _hold(fd)
            _refused(lambda: retire.retain_native("worker", str(lane), str(root / "logs"), "b" * 20), "lock is active")
        finally:
            os.close(fd)
        ensure(proofs.exists(), "proof directory lock protects native outputs")


def _venv_links_and_target_locks() -> None:
    with sandbox_tree(FILES) as root, patch.object(retire.env, "filesystem", return_value="ext4"):
        lane = root / "build" / "lane-worker"
        library = lane / "venv-linux" / "lib"
        library.mkdir(parents=True)
        (library.parent / "lib64").symlink_to("lib", target_is_directory=True)
        lock = library / "active.lock"
        lock.write_text("", encoding="utf-8")
        with lock.open() as handle:
            _hold(handle.fileno())
            _refused(lambda: retire.retain_native("worker", str(lane), str(root / "logs"), "c" * 20),
                     "lock is active")
        result = retire.retain_native("worker", str(lane), str(root / "logs"), "c" * 20)
        saved = Path(str(result["archive"])) / "lane" / "venv-linux"
        ensure((saved / "lib64").is_symlink() and (saved / "lib64").resolve() == saved / "lib",
               "relative environment link and target survive together")
    with sandbox_tree(FILES) as root, patch.object(retire, "_guest", return_value={}):
        path, record, revision, archive = _worker(root)
        library = path / "out" / "venv-linux" / "lib"
        library.mkdir(parents=True)
        (library.parent / "lib64").symlink_to("lib", target_is_directory=True)
        result = retire.retire(root, record, revision, archive)
        saved = Path(str(result["archive"])) / "checkout" / "out" / "venv-linux"
        ensure((saved / "lib64").resolve() == saved / "lib", "checkout environment link retained")


def _log_inventory_covers_callers() -> None:
    stems: set[str] = set()
    for path in (TOOLS / "vos").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            if call.func.attr != "log" or not call.args:
                continue
            argument = call.args[0]
            candidates = [argument.body, argument.orelse] if isinstance(argument, ast.IfExp) else [argument]
            stems.update(item.value for item in candidates
                         if isinstance(item, ast.Constant) and isinstance(item.value, str))
    ensure(stems <= retire._LOG_STEMS, f"unclassified Environment.log callers: {stems - retire._LOG_STEMS}")


def _native_exact_log_ownership() -> None:
    with sandbox_tree(FILES) as root, patch.object(retire.env, "filesystem", return_value="ext4"):
        lane, logs = root / "build" / "lane-worker", root / "logs"
        lane.mkdir(parents=True)
        logs.mkdir()
        for name in ("model-build-worker.log", "model-build-worker.json", "model-build-fast-worker.log",
                     "model-build-fast-worker.json", "build-other-worker.log", "model-build-other-worker.log"):
            (logs / name).write_text(name, encoding="utf-8")
        result = retire.retain_native("worker", str(lane), str(logs), "d" * 20,
                                      ["worker", "fast-worker", "other-worker"])
        saved = Path(str(result["archive"])) / "logs"
        ensure((saved / "model-build-worker.log").exists() and (saved / "model-build-worker.json").exists(),
               "the exact model log and SHA-bound receipt travel together")
        ensure(all((logs / name).exists() for name in ("model-build-fast-worker.log", "model-build-fast-worker.json",
                                                      "build-other-worker.log", "model-build-other-worker.log")),
               "ambiguous and unknown suffix matches remain untouched")
        deferred = str(result["deferred"])
        ensure("registered peer" in deferred and "build-other-worker.log" in deferred,
               "ambiguities and unknown historical outputs are explicit evidence")


def _native_log_directories_and_companions() -> None:
    with sandbox_tree(FILES) as root, patch.object(retire.env, "filesystem", return_value="ext4"):
        lane, logs = root / "build" / "lane-worker", root / "logs"
        lane.mkdir(parents=True)
        relative = ["worker/composer-reference", "worker/copy-service", "worker/supervisor",
                    "lane-worker/admission-reference", "sail-assist-worker/session/attempt-0001",
                    "sail-modular-worker-" + "a" * 32]
        for name in relative:
            folder = logs / name
            folder.mkdir(parents=True)
            (folder / "evidence.bin").write_bytes(b"evidence")
        for name in ("model-build-fast-worker.log", "model-build-fast-worker.json",
                     "testrig-worker.log", "testrig-worker.trace", "testrig-worker.log.lock",
                     "sail-isla-provision-00-worker.log", "sail-isla-qualify-100-worker.log"):
            (logs / name).write_text(name, encoding="utf-8")
        result = retire.retain_native("worker", str(lane), str(logs), "e" * 20)
        saved = Path(str(result["archive"])) / "logs"
        ensure(all((saved / name / "evidence.bin").read_bytes() == b"evidence" for name in relative),
               "all current log directory layouts retain their full contents")
        ensure((saved / "testrig-worker.trace").exists() and (saved / "testrig-worker.log.lock").exists(),
               "RVFI trace and native log lock sidecars are retained")
        ensure((saved / "model-build-fast-worker.json").exists()
               and (saved / "sail-isla-qualify-100-worker.log").exists(), "dynamic logs and receipts are retained")
        ensure(not result["deferred"], "complete unambiguous inventory has no deferred outputs")


def _native_log_locks_and_peer_directories() -> None:
    with sandbox_tree(FILES) as root, patch.object(retire.env, "filesystem", return_value="ext4"):
        lane, logs = root / "build" / "lane-worker", root / "logs"
        lane.mkdir(parents=True)
        logs.mkdir()
        lock = logs / "testrig-worker.log.lock"
        lock.write_text("", encoding="utf-8")
        with lock.open() as handle:
            _hold(handle.fileno())
            _refused(lambda: retire.retain_native("worker", str(lane), str(logs), "f" * 20), "lock is active")
        folder = logs / "worker" / "supervisor"
        folder.mkdir(parents=True)
        fd = os.open(folder, os.O_RDONLY)
        try:
            _hold(fd)
            _refused(lambda: retire.retain_native("worker", str(lane), str(logs), "f" * 20), "lock is active")
        finally:
            os.close(fd)
        shared = logs / "sail-assist-worker"
        shared.mkdir()
        (shared / "evidence.bin").write_bytes(b"retain")
        result = retire.retain_native("worker", str(lane), str(logs), "f" * 20,
                                      ["worker", "sail-assist-worker"])
        ensure((shared / "evidence.bin").exists() and "registered peer" in str(result["deferred"]),
               "a peer's nested log namespace protects an overlapping output directory")


def _native_oracle_locks_of_every_edition() -> None:
    """A lane's oracle log is moved only while no edition's oracle build holds its tree:
    the log's name does not say which edition's checkout wrote it."""
    with sandbox_tree(FILES) as root, patch.object(retire.env, "filesystem", return_value="ext4"):
        build, logs = root / "build", root / "logs"
        lane = build / "lane-worker"
        lane.mkdir(parents=True)
        logs.mkdir()
        log = logs / "oracle-build-worker.log"
        log.write_text("oracle", encoding="utf-8")
        for edition in ("sail-0.0.1", f"sail-{retire.env.SAIL_VERSION}"):
            lock = retire.env._lock_path(build / edition / retire.env.ORACLE_TREE)
            lock.parent.mkdir()
            lock.write_text("", encoding="utf-8")
            with lock.open() as handle:
                _hold(handle.fileno())
                _refused(lambda: retire.retain_native("worker", str(lane), str(logs), "0a" * 10),
                         "native output lock is active")
            ensure(log.exists() and lane.exists(),
                   f"an oracle build under {edition} keeps the lane's log and outputs in place")
        result = retire.retain_native("worker", str(lane), str(logs), "0a" * 10)
        saved = Path(str(result["archive"])) / "logs" / log.name
        ensure(saved.read_text(encoding="utf-8") == "oracle" and not log.exists(),
               "with no oracle build running, the lane's oracle log travels with it")


def cases() -> list[Case]:
    return [Case("retains-outputs-and-repeats", _retains_outputs_and_repeats),
            Case("dirty-and-unintegrated", _dirty_and_unintegrated),
            Case("changed-identity-and-locked", _changed_identity_and_locked),
            Case("host-owned-and-outside", _host_owned_and_outside),
            Case("nested-repository", _nested_repository),
            Case("interrupted-after-git-remove", _interrupted_after_git_remove),
            Case("branch-moved-after-removal", _branch_moved_after_removal),
            Case("missing-without-receipt", _missing_without_receipt),
            Case("records", _records), Case("log-inventory-covers-callers", _log_inventory_covers_callers),
            Case("symlink-escape", _symlink_escape, lane="guest"),
            Case("native-outputs-and-lock", _native_outputs_and_lock, lane="guest"),
            Case("native-directory-lock", _native_directory_lock, lane="guest"),
            Case("venv-links-and-target-locks", _venv_links_and_target_locks, lane="guest"),
            Case("native-exact-log-ownership", _native_exact_log_ownership, lane="guest"),
            Case("native-log-directories-and-companions", _native_log_directories_and_companions, lane="guest"),
            Case("native-log-locks-and-peer-directories", _native_log_locks_and_peer_directories, lane="guest"),
            Case("native-oracle-locks-of-every-edition", _native_oracle_locks_of_every_edition, lane="guest")]
