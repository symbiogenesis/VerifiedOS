# SPDX-License-Identifier: Apache-2.0
"""Retirement checks ownership, ancestry, retention and interrupted removal in real Git."""

import ast
import errno
import io
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from contextlib import redirect_stdout
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from tests.test_worktree import _commit, _git
from vos import fanout_retire as retire
from vos import memory_planner_candidates as candidates
from vos.cli import model as model_cli
from vos.cli import proofs as proofs_cli
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
    import fcntl
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


def _native_linked_proof_workspace() -> None:
    """`proofs.workspace` resolves the lane's `proof-gate`, so through a relative link
    the gate flocks a directory whose name retirement does not hold: the link itself
    is selected and refused, idle or held."""
    with sandbox_tree(FILES) as root, patch.object(retire.env, "filesystem", return_value="ext4"):
        lane = root / "build" / "lane-worker"
        target = lane / "proof-gate-real"
        target.mkdir(parents=True)
        (lane / "proof-gate").symlink_to("proof-gate-real", target_is_directory=True)
        held = (lane / "proof-gate").resolve()
        ensure(held == target, "precondition: the gate's resolved workspace is the link's target")
        fd = os.open(held, os.O_RDONLY)
        try:
            _hold(fd)
            _refused(lambda: retire.retain_native("worker", str(lane), str(root / "logs"), "5" * 20),
                     "redirects")
        finally:
            os.close(fd)
        _refused(lambda: retire.retain_native("worker", str(lane), str(root / "logs"), "5" * 20),
                 "redirects")
        ensure(target.is_dir() and (lane / "proof-gate").is_symlink(), "a linked workspace stays in place")


def _lock_taken_late(name: str) -> None:
    """Create and take the lane's `name` just after the selection first walks the lane."""
    with sandbox_tree(FILES) as root, patch.object(retire.env, "filesystem", return_value="ext4"):
        lane = root / "build" / "lane-worker"
        lane.mkdir(parents=True)
        (lane / "result.bin").write_bytes(b"proof")
        late, walk = lane / name, retire._tree_safe
        held: list[int] = []

        def racing(path: Path, *, checkout: bool = False) -> list[Path]:
            found = walk(path, checkout=checkout)
            if path == lane and not held:
                if late.suffix == ".lock":
                    late.write_text("", encoding="utf-8")
                else:
                    late.mkdir()
                held.append(os.open(late, os.O_RDONLY))
                _hold(held[-1])
            return found

        try:
            with patch.object(retire, "_tree_safe", side_effect=racing):
                _refused(lambda: retire.retain_native("worker", str(lane), str(root / "logs"), "6" * 20),
                         f"native output locks changed while retirement took them: {late}")
        finally:
            for fd in held:
                os.close(fd)
        ensure((lane / "result.bin").exists(), f"a lane whose {name} was taken late stays in place")


def _native_locks_taken_late() -> None:
    """A producer that creates and takes a lock once the selection has walked the lane,
    a `*.lock` file or the proof workspace, is seen by the selection repeated under the
    held locks, and the lane stays in place."""
    for name in ("late.lock", "proof-gate"):
        _lock_taken_late(name)


def _native_hard_linked_locks() -> None:
    """A lane-local uv cache hard-links the files it installs, `*.lock` files among
    them, so two selected paths can name one file: retirement locks it once and the
    idle lane retires, while a producer holding it through either link refuses it. The
    oracle family's locks, selected outside the lane, are held once the same way."""
    with sandbox_tree(FILES) as root, patch.object(retire.env, "filesystem", return_value="ext4"):
        lane = root / "build" / "lane-worker"
        cached = lane / "uv-cache" / "archive-v0" / "entry" / "empty_template_renv.lock"
        installed = lane / "venv-model" / "lib" / "pre_commit" / "empty_template_renv.lock"
        for folder in (cached.parent, installed.parent):
            folder.mkdir(parents=True)
        cached.write_text("", encoding="utf-8")
        os.link(cached, installed)
        ensure(cached.stat().st_ino == installed.stat().st_ino, "precondition: the two links name one file")
        # Positive control: flock belongs to the open file description, so a lock
        # taken through one link excludes a second description through the other,
        # even within one process.
        with cached.open() as first, installed.open() as second:
            _hold(first.fileno())
            try:
                _hold(second.fileno())
            except BlockingIOError:
                pass
            else:
                raise AssertionError("precondition: two descriptions of one file exclude each other")
        for link in (cached, installed):
            with link.open() as handle:
                _hold(handle.fileno())
                _refused(lambda: retire.retain_native("worker", str(lane), str(root / "logs"), "7" * 20),
                         "native output lock is active")
            ensure(cached.exists() and installed.exists(), f"a lock held through {link} keeps the lane in place")
        result = retire.retain_native("worker", str(lane), str(root / "logs"), "7" * 20)
        saved = Path(str(result["archive"])) / "lane"
        ensure(not lane.exists() and (saved / cached.relative_to(lane)).stat().st_ino
               == (saved / installed.relative_to(lane)).stat().st_ino,
               "the idle lane retires with both links to its lock")
    with sandbox_tree(FILES) as root, patch.object(retire.env, "filesystem", return_value="ext4"):
        build, logs = root / "build", root / "logs"
        lane = build / "lane-worker"
        lane.mkdir(parents=True)
        logs.mkdir()
        log = logs / "oracle-build-worker.log"
        log.write_text("oracle", encoding="utf-8")
        unkeyed = retire.env._lock_path(build / retire.env.ORACLE_TREE)
        edition = retire.env._lock_path(build / f"sail-{retire.env.SAIL_VERSION}" / retire.env.ORACLE_TREE)
        edition.parent.mkdir()
        unkeyed.write_text("", encoding="utf-8")
        os.link(unkeyed, edition)
        ensure({unkeyed, edition} <= retire._native_locks([], lane, oracle=True),
               "precondition: the oracle family's selection names both links")
        result = retire.retain_native("worker", str(lane), str(logs), "7b" * 10)
        ensure((Path(str(result["archive"])) / "logs" / log.name).exists() and not log.exists()
               and unkeyed.exists() and edition.exists(),
               "an oracle lock reached through two links does not refuse its own retirement")


def _native_lock_replaced_late() -> None:
    """A producer that replaces a lock retirement holds and takes the new file is not
    excluded by retirement's descriptor on the old one: the repeated selection compares
    the file each lock names, not only its path, and the lane stays in place."""
    with sandbox_tree(FILES) as root, patch.object(retire.env, "filesystem", return_value="ext4"):
        lane = root / "build" / "lane-worker"
        lane.mkdir(parents=True)
        (lane / "result.bin").write_bytes(b"proof")
        lock, walk = lane / "model.lock", retire._tree_safe
        lock.write_text("", encoding="utf-8")
        walks: list[Path] = []
        held: list[int] = []

        def racing(path: Path, *, checkout: bool = False) -> list[Path]:
            walks.append(path)
            if walks.count(lane) == 2:
                lock.unlink()
                lock.write_text("", encoding="utf-8")
                held.append(os.open(lock, os.O_RDONLY))
                _hold(held[-1])
            return walk(path, checkout=checkout)

        try:
            with patch.object(retire, "_tree_safe", side_effect=racing):
                _refused(lambda: retire.retain_native("worker", str(lane), str(root / "logs"), "9" * 20),
                         f"native output locks changed while retirement took them: {lock}")
        finally:
            for fd in held:
                os.close(fd)
        ensure(len(held) == 1, "precondition: the lock was replaced as the selection was repeated")
        ensure((lane / "result.bin").exists(), "a lane whose lock was replaced late stays in place")


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
    """A lane's oracle log is moved only while no oracle build holds its tree: the log's
    name says neither which Sail edition's checkout wrote it nor which oracle pin."""
    with sandbox_tree(FILES) as root, patch.object(retire.env, "filesystem", return_value="ext4"):
        build, logs = root / "build", root / "logs"
        lane = build / "lane-worker"
        lane.mkdir(parents=True)
        logs.mkdir()
        log = logs / "oracle-build-worker.log"
        log.write_text("oracle", encoding="utf-8")
        family = retire.env.ORACLE_TREE.rsplit("-", 1)[0]
        for edition, tree in (("sail-0.0.1", retire.env.ORACLE_TREE),
                              (f"sail-{retire.env.SAIL_VERSION}", retire.env.ORACLE_TREE),
                              ("sail-0.0.1", f"{family}-00000000"),
                              (".", f"{family}-00000000")):
            lock = retire.env._lock_path(build / edition / tree)
            lock.parent.mkdir(exist_ok=True)
            lock.write_text("", encoding="utf-8")
            with lock.open() as handle:
                _hold(handle.fileno())
                _refused(lambda: retire.retain_native("worker", str(lane), str(logs), "0a" * 10),
                         "native output lock is active")
            ensure(log.exists() and lane.exists(),
                   f"an oracle build of {tree} under {edition} keeps the lane's log and "
                   "outputs in place")
        result = retire.retain_native("worker", str(lane), str(logs), "0a" * 10)
        saved = Path(str(result["archive"])) / "logs" / log.name
        ensure(saved.read_text(encoding="utf-8") == "oracle" and not log.exists(),
               "with no oracle build running, the lane's oracle log travels with it")


def _persistence_campaign_lock() -> None:
    """The emulator flocks its block images inside the campaign's output, which the
    retirement does not open; a live campaign is seen through the `<output>.lock` the
    campaign holds beside it, and a finished one retires with its images."""
    with sandbox_tree(FILES) as root, patch.object(retire.env, "filesystem", return_value="ext4"):
        e = retire.env.Environment(root, root / "model", root / "build", root / "logs",
                                   "worker", 4, 4096, 2, 2)
        seen: list[str] = []

        def campaign(*args: object) -> dict[str, object]:
            output = Path(str(args[3]))
            output.mkdir(parents=True)
            (output / "durable.img").write_bytes(b"image")
            try:
                retire.retain_native("worker", str(e.lane_root), str(root / "logs"), "3" * 20)
            except retire.RetirementError as exc:
                seen.append(str(exc))
            return {"passed": True}

        with (patch.object(model_cli.block_persistence, "run", side_effect=campaign),
              redirect_stdout(io.StringIO())):
            ensure(model_cli._corpus_persistence(e, e.lane_root / "corpus", 30) == 0,
                   "the stand-in campaign passes")
        ensure(len(seen) == 1 and seen[0].startswith("native output lock is active: ")
               and re.search(r"/corpus/persistence-[0-9a-f]{32}\.lock$", seen[0]) is not None,
               f"a retirement during the campaign refuses on its output lock, got {seen}")
        result = retire.retain_native("worker", str(e.lane_root), str(root / "logs"), "3" * 20)
        images = list((Path(str(result["archive"])) / "lane" / "corpus").glob("persistence-*/durable.img"))
        ensure(len(images) == 1 and not e.lane_root.exists(),
               "after the campaign the lane retires with its images")


def _idealloc_build_lock() -> None:
    """Cargo flocks `.cargo-lock` and `.package-cache` inside the idealloc build's
    output, names the retirement does not select; a live build is seen through the
    `<output>.lock` the build holds beside it, and a finished one retires."""
    with sandbox_tree(FILES) as root, patch.object(retire.env, "filesystem", return_value="ext4"):
        lane = root / "build" / "lane-worker"
        output = lane / "memory-planner-idealloc"
        checkout = root / "checkout"
        (checkout / candidates.BRIDGE_PATH).parent.mkdir(parents=True)
        (checkout / candidates.PIN_PATH).write_text(json.dumps(
            {"schema": candidates.PIN_SCHEMA, "files": [], "commit": "0" * 40, "license": "fixture"}),
            encoding="utf-8")
        (checkout / candidates.BRIDGE_PATH).write_text("// bridge\n", encoding="utf-8")
        (output / "upstream" / "coreba" / "src" / "bin").mkdir(parents=True)
        seen: list[str] = []

        def cargo(*_: object) -> tuple[str, dict[str, str], dict[str, str]]:
            lock = output / "target" / "release" / ".cargo-lock"
            lock.parent.mkdir(parents=True)
            lock.write_text("", encoding="utf-8")
            with lock.open() as handle:
                _hold(handle.fileno())
                try:
                    retire.retain_native("worker", str(lane), str(root / "logs"), "4" * 20)
                except retire.RetirementError as exc:
                    seen.append(str(exc))
            raise ValueError("the stand-in toolchain stops the build")

        with (patch.object(candidates, "native_output", side_effect=lambda _, path: path),
              patch.object(candidates, "rust_environment", side_effect=cargo)):
            stopped = False
            try:
                candidates.build_idealloc(checkout, output)
            except ValueError as exc:
                stopped = "stand-in" in str(exc)
            ensure(stopped, "the stand-in toolchain ends the build")
        ensure(seen == [f"native output lock is active: {lane / 'memory-planner-idealloc.lock'}"],
               f"a retirement during the build refuses on its output lock, got {seen}")
        result = retire.retain_native("worker", str(lane), str(root / "logs"), "4" * 20)
        saved = Path(str(result["archive"])) / "lane" / "memory-planner-idealloc"
        ensure((saved / "target" / "release" / ".cargo-lock").exists() and not lane.exists(),
               "after the build the lane retires with its outputs")


# The descriptor limit is process-wide, so it is lowered in a child: lowered here, it
# would bind every module the runner's worker process takes next. The child builds a
# lane with four directories per descriptor and a second lane with two lock files per
# descriptor, then reports each outcome as a string, an OSError by its errno.
_DESCRIPTOR_PROBE = """
import fcntl
import json
import os
import resource
import sys
from pathlib import Path
from unittest.mock import patch

from vos import env
from vos import fanout_retire as retire

root, limit = Path(sys.argv[1]).resolve(), int(sys.argv[2])
build, logs = root / "build", root / "logs"
logs.mkdir(parents=True)
lane = build / "lane-worker"
for index in range(4 * limit):
    (lane / "opam" / f"package-{index:04}" / "lib").mkdir(parents=True)
(lane / "proof-gate").mkdir()
crowded = build / "lane-crowded"
crowded.mkdir()
for index in range(2 * limit):
    (crowded / f"run-{index:04}.lock").write_text("", encoding="utf-8")
resource.setrlimit(resource.RLIMIT_NOFILE, (limit, resource.getrlimit(resource.RLIMIT_NOFILE)[1]))
found = {"limit": resource.getrlimit(resource.RLIMIT_NOFILE)[0]}


def outcome(name, batch):
    try:
        retire.retain_native(name, str(build / f"lane-{name}"), str(logs), batch)
    except retire.RetirementError as exc:
        return f"refused: {exc}"
    except OSError as exc:
        return f"OSError {exc.errno}"
    return "retired"


# Positive control: a descriptor held on every directory of this lane exceeds the lowered limit.
held = []
try:
    for path in [lane, *(path for path in retire._tree_safe(lane)
                         if path.is_dir() or path.name.endswith(".lock"))]:
        held.append(os.open(path, os.O_RDONLY))
    found["control"] = "opened"
except OSError as exc:
    found["control"] = f"OSError {exc.errno}"
finally:
    for fd in held:
        os.close(fd)
with patch.object(retire.env, "filesystem", return_value="ext4"):
    handle = env.hold_lock(lane / "opam" / "package-0001" / "lib" / "cache", "a nested producer")
    found["nested"] = outcome("worker", "1" * 20)
    handle.close()
    fd = os.open(lane / "proof-gate", os.O_RDONLY)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    found["directory"] = outcome("worker", "1" * 20)
    os.close(fd)
    found["held-in-place"] = lane.is_dir()
    found["retired"] = outcome("worker", "1" * 20)
    found["crowded"] = outcome("crowded", "2" * 20)
    found["crowded-in-place"] = len(list(crowded.glob("*.lock")))
archive = build / "fanout-retained" / ("1" * 20) / "worker" / "lane" / "opam"
found["archived"] = len(list(archive.iterdir())) if archive.is_dir() else 0
print(json.dumps(found))
"""


def _native_locks_fit_descriptor_limit() -> None:
    """Retirement opens only the locks it selects, never every directory, so a lane
    with more directories than descriptors retires, a held nested lock still refuses
    it, and more lock files than descriptors refuse as a verdict naming the path,
    never as an uncaught OSError."""
    limit = 64
    with tempfile.TemporaryDirectory(prefix="vos-test-") as work:
        done = subprocess.run([sys.executable, "-c", _DESCRIPTOR_PROBE, work, str(limit)],
                              capture_output=True, encoding="utf-8", errors="replace",
                              check=False, timeout=300, env={**os.environ, "PYTHONPATH": str(TOOLS)})
    ensure(done.returncode == 0, f"the descriptor probe must answer: {done.stderr[-800:]!r}")
    found = json.loads(done.stdout)
    ensure(found["limit"] == limit and found["control"] == f"OSError {errno.EMFILE}",
           f"precondition: holding every directory exhausts the lowered limit, got {found}")
    ensure(str(found["nested"]).startswith("refused: native output lock is active")
           and str(found["nested"]).endswith("/opam/package-0001/lib/cache.lock"),
           f"a producer's nested lock file still refuses retirement, got {found['nested']}")
    ensure(str(found["directory"]).startswith("refused: native output lock is active")
           and str(found["directory"]).endswith("/lane-worker/proof-gate") and found["held-in-place"],
           f"the proof workspace's directory lock still refuses retirement, got {found['directory']}")
    ensure(found["retired"] == "retired" and found["archived"] == 4 * limit,
           f"a lane with more directories than descriptors retires whole, got {found}")
    ensure(str(found["crowded"]).startswith("refused: native output lock cannot be taken: ")
           and "run-" in str(found["crowded"]) and f"{2 * limit + 1} locks needed" in str(found["crowded"])
           and found["crowded-in-place"] == 2 * limit,
           f"more lock files than descriptors refuse naming the path and move nothing, got {found}")


def _tool_sources(pattern: str) -> list[Path]:
    """The tools' own sources: the tests and any installed environment are not producers."""
    return [path for path in TOOLS.rglob(pattern)
            if not {"tests", "site-packages", "node_modules"} & set(path.relative_to(TOOLS).parts)
            and not any(part.startswith(".") for part in path.relative_to(TOOLS).parts)]


def _checkout_sources(suffixes: tuple[str, ...]) -> list[Path]:
    """This checkout's own sources by suffix: pinned upstreams, peer worktrees, outputs
    and dot-directories hold none of its producers."""
    found: list[Path] = []
    for directory, dirs, files in os.walk(TOOLS.parent):
        dirs[:] = [name for name in dirs if not name.startswith(".")
                   and name not in {"upstream", "out", "node_modules", "site-packages", "__pycache__"}]
        found.extend(Path(directory) / name for name in files if name.endswith(suffixes))
    return found


_FLOCK = re.compile(r"\bflock\b")


def _python_flock_sites(name: str, text: str) -> set[tuple[str, str]]:
    """Each (module, innermost function) that reaches `flock` in one Python source: an
    attribute named `flock`, a name `from fcntl import flock [as x]` or `*` binds, or a
    call passing a string that names the `flock` command."""
    tree = ast.parse(text)
    imported = {alias.asname or alias.name for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module == "fcntl"
                for alias in node.names if alias.name in {"flock", "*"}}
    bound = (imported - {"*"}) | ({"flock"} if "*" in imported else set())
    sites: set[tuple[str, str]] = set()

    def reaches(node: ast.AST) -> bool:
        if isinstance(node, ast.Attribute):
            return node.attr == "flock"
        if isinstance(node, ast.Name):
            return node.id in bound
        return isinstance(node, ast.Call) and any(
            isinstance(inner, ast.Constant) and isinstance(inner.value, str)
            and _FLOCK.search(inner.value) is not None
            for argument in (*node.args, *(keyword.value for keyword in node.keywords))
            for inner in ast.walk(argument))

    def visit(node: ast.AST, owner: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = child.name if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef) else owner
            if reaches(child):
                sites.add((name, owner))
            visit(child, inner)

    visit(tree, "<module>")
    return sites


# The one recognized shell form: `flock` with option flags and a numeric descriptor,
# ending its command.
_SHELL_FLOCK = re.compile(r"flock(?:[ \t]+(?:-[A-Za-z]+|--[a-z][a-z-]*))+[ \t]+(\d+)[ \t]*(?:$|[;&|)])",
                          re.MULTILINE)


def _shell_code(text: str) -> str:
    """A script with each comment blanked: a `#` opening a word outside quotes runs to
    the end of its line."""
    kept: list[str] = []
    quote, comment, escaped = "", False, False
    for index, char in enumerate(text):
        if comment:
            comment = char != "\n"
            kept.append(char if char == "\n" else " ")
            continue
        if escaped:
            escaped = False
        elif char == "\\" and quote != "'":
            escaped = True
        elif quote:
            quote = "" if char == quote else quote
        elif char in "'\"":
            quote = char
        elif char == "#" and (index == 0 or text[index - 1] in " \t\n;&|()"):
            comment = True
            kept.append(" ")
            continue
        kept.append(char)
    return "".join(kept)


def _shell_flock_sites(text: str) -> tuple[set[str], list[str]]:
    """The descriptors a script flocks in the recognized form, each redirected only to
    a quoted `*.lock` path, and every other `flock` outside comments, unclassified."""
    code = _shell_code(text)
    descriptors: set[str] = set()
    unclassified: list[str] = []
    for token in _FLOCK.finditer(code):
        line = code.count("\n", 0, token.start()) + 1
        form = _SHELL_FLOCK.match(code, token.start())
        if form is None:
            unclassified.append(f"line {line}: flock outside the recognized form")
            continue
        fd = form.group(1)
        targets = re.findall(rf"(?<![\w&$]){fd}(?:>>|<>|>|<)[ \t]*(\"[^\"]*\"|'[^']*'|[^\s;&|)]+)", code)
        if not targets or not all(target.startswith('"') and target.endswith('.lock"') for target in targets):
            unclassified.append(f"line {line}: descriptor {fd} is not redirected only to a quoted *.lock path")
            continue
        descriptors.add(fd)
    return descriptors, unclassified


def _c_code(text: str) -> str:
    """A C or C++ source with its comments blanked and its literals kept."""
    kept: list[str] = []
    state, index = "", 0
    while index < len(text):
        char, pair = text[index], text[index:index + 2]
        if state == "line":
            state = "" if char == "\n" else state
            kept.append(char if char == "\n" else " ")
            index += 1
        elif state == "block":
            state, step = ("", 2) if pair == "*/" else (state, 1)
            kept.append("\n" if char == "\n" else " ")
            index += step
        elif state:
            step = 2 if char == "\\" else 1
            kept.append(text[index:index + step])
            state = "" if char == state else state
            index += step
        elif pair in {"//", "/*"}:
            state = "line" if pair == "//" else "block"
            kept.append("  ")
            index += 2
        else:
            state = char if char in "'\"" else ""
            kept.append(char)
            index += 1
    return "".join(kept)


def _c_flock_calls(text: str) -> int | None:
    """How many `flock(` calls one C or C++ source makes, or `None` when `flock` also
    occurs outside comments as anything but a call."""
    code = _c_code(text)
    calls = len(re.findall(r"\bflock\s*\(", code))
    return calls if calls == len(_FLOCK.findall(code)) else None


def _campaign_calls(name: str, text: str) -> list[tuple[str, bool]]:
    """Each `block_persistence.run` call in one source, and whether it sits inside a
    `with ... hold_lock(<its output>, ...)`."""
    calls: list[tuple[str, bool]] = []

    def visit(node: ast.AST, held: tuple[str, ...]) -> None:
        if isinstance(node, ast.With | ast.AsyncWith):
            held += tuple(ast.dump(item.context_expr.args[0]) for item in node.items
                          if isinstance(item.context_expr, ast.Call) and item.context_expr.args
                          and isinstance(item.context_expr.func, ast.Attribute)
                          and item.context_expr.func.attr == "hold_lock")
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "run"
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "block_persistence"):
            calls.append((f"{name}:{node.lineno}", len(node.args) > 3 and ast.dump(node.args[3]) in held))
        for child in ast.iter_child_nodes(node):
            visit(child, held)

    visit(ast.parse(text), ())
    return calls


def _producer_lock_scanners_fail_closed() -> None:
    """A Python `flock` bound by import or named as a command is a site, and a shell or
    C `flock` outside the one recognized form is reported rather than passed over."""
    for text, owner in (("from fcntl import flock as grab\ndef take(fd):\n    grab(fd, 2)\n", "take"),
                        ("from fcntl import *\ndef take(fd):\n    flock(fd, 2)\n", "take"),
                        ("import subprocess\ndef run(path):\n"
                         "    subprocess.run(['flock', '-x', path, 'true'])\n", "run"),
                        ("import subprocess\ndef run():\n"
                         "    subprocess.run('flock -x 9 true', shell=True)\n", "run"),
                        ("import fcntl\ntake = fcntl.flock\n", "<module>")):
        found = _python_flock_sites("probe.py", text)
        ensure(found == {("probe.py", owner)}, f"the Python scan must find {text!r}, got {found}")
    ensure(_python_flock_sites("probe.py", '"""flock is described, not called."""\n') == set(),
           "a docstring naming flock is not a site")
    for text in ('flock -x "$dir/work.lock" true\n',
                 '(\n    flock --exclusive 9\n) 9>"$dir/state.json"\n',
                 '(\n    flock 9\n) 9>"$dir/work.lock"\n',
                 '(\n    flock -w 10 9\n) 9>"$dir/work.lock"\n',
                 'command -v flock >/dev/null\n'):
        descriptors, unclassified = _shell_flock_sites(text)
        ensure(len(unclassified) == 1 and not descriptors,
               f"the shell scan must report {text!r}, got {descriptors}, {unclassified}")
    ensure(_shell_flock_sites('# flock -x 9 is how\n(\n    flock -x 9\n) 9>"$d/.x.lock"\n') == ({"9"}, []),
           "the recognized form classifies, and a comment is not an occurrence")
    ensure(_c_flock_calls("/* flock(fd) */ int f(int fd) { return flock(fd, 2); } // flock(fd)\n") == 1,
           "the C scan counts a call and skips comments")
    ensure(_c_flock_calls('auto take = flock; const char *s = "flock";\n') is None,
           "the C scan reports a flock it cannot read as a call")
    campaign = ("def go(out, other):\n"
                "    block_persistence.run(1, 2, 3, out, 4)\n"
                "    with env.hold_lock(other, 'x'):\n        block_persistence.run(1, 2, 3, out, 4)\n"
                "    with env.hold_lock(out, 'x'):\n        block_persistence.run(1, 2, 3, out, 4)\n")
    ensure([locked for _, locked in _campaign_calls("probe.py", campaign)] == [False, False, True],
           "only a campaign inside a lock on its own output counts as held")


def _producer_lock_inventory() -> None:
    """Retirement's lock selection covers a producer only while its lock is a `*.lock`
    file, a directory in `_DIRECTORY_LOCKS`, or a lock of its own inside an output
    beside which its launcher holds a `*.lock`: each `flock` site in the tools' Python
    and in the checkout's shell and C and C++ sources is classified here, and an
    occurrence the scans cannot classify fails."""
    lock_files = {("vos/env.py", "_flock"), ("vos/env.py", "_unlock"),  # env._lock_path
                  ("vos/cli/fanout.py", "_exclusive"),  # out/fanout/.lock, host side
                  ("vos/fanout_retire.py", "retain_native")}  # the retirement itself
    directories = {("vos/cli/proofs.py", "_hold")}
    sources = _tool_sources("*.py")
    sites = set().union(*(_python_flock_sites(path.relative_to(TOOLS).as_posix(),
                                              path.read_text(encoding="utf-8")) for path in sources))
    ensure(directories | {("vos/env.py", "_flock")} <= sites,
           f"precondition: the scan finds the known flock sites, got {sites}")
    ensure(sites <= lock_files | directories, f"unclassified flock sites: {sites - lock_files - directories}")
    # Native producers' own locks, by file. The emulator flocks a `--blkdev-image`,
    # which the tools pass only from `block_persistence.run`, under the campaign's
    # `<output>.lock`; the unit test and the emulator it launches lock images in its
    # scratch in the build tree, under the lock ctest's caller holds beside that tree.
    native = {"model/c_emulator/blkdev_image.cpp": 1, "model/test/unit_tests/block_image.cpp": 1}
    counts: dict[str, int | None] = {}
    for path in _checkout_sources((".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if _FLOCK.search(text) is not None:
            counts[path.relative_to(TOOLS.parent).as_posix()] = _c_flock_calls(text)
    ensure({name: count for name, count in counts.items() if count != 0} == native,
           f"unclassified native flock sites (file: calls, None where one is not a call): {counts}")
    launchers = {path.relative_to(TOOLS).as_posix() for path in sources
                 if any(isinstance(node, ast.Constant) and isinstance(node.value, str)
                        and node.value.startswith("--blkdev-image")
                        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))))}
    ensure(launchers == {"vos/block_persistence.py"},
           f"only the persistence campaign passes the emulator a block image, got {launchers}")
    campaigns = [call for path in sources
                 for call in _campaign_calls(path.name, path.read_text(encoding="utf-8"))]
    ensure(bool(campaigns), "precondition: the persistence campaign's callers are found")
    ensure(all(locked for _, locked in campaigns),
           f"the campaign runs outside a lock beside its output: {[at for at, locked in campaigns if not locked]}")
    callers = 0
    for path in sources:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for call in ast.walk(tree):
            if not isinstance(call, ast.Call) or not (
                    (isinstance(call.func, ast.Attribute) and call.func.attr == "_hold")
                    or (path.name == "proofs.py" and isinstance(call.func, ast.Name)
                        and call.func.id == "_hold")):
                continue
            callers += 1
            argument = call.args[0] if call.args else None
            ensure(isinstance(argument, ast.Call) and (
                (isinstance(argument.func, ast.Name) and argument.func.id == "workspace")
                or (isinstance(argument.func, ast.Attribute) and argument.func.attr == "workspace")),
                f"{path.name}:{call.lineno} flocks a directory other than the proof workspace")
    ensure(callers > 0, "precondition: the proof workspace's lock callers are found")
    lane = Path("/nonexistent/build/lane-worker").resolve()
    with patch.object(proofs_cli.env, "lane_of", return_value="worker"), \
            patch.object(proofs_cli.env, "lane_root", return_value=lane), \
            patch.object(proofs_cli.env, "filesystem", return_value="ext4"):
        held = proofs_cli.workspace(Path("/nonexistent/checkout").resolve())
    ensure(held.parent == lane and held.name in retire._DIRECTORY_LOCKS,
           f"the proof workspace {held} must be a directory lock retirement holds")
    installers = 0
    for script in _checkout_sources((".sh",)):
        descriptors, unclassified = _shell_flock_sites(script.read_text(encoding="utf-8"))
        installers += bool(descriptors)
        ensure(not unclassified, f"{script.name}: {unclassified}")
    ensure(installers > 0, "precondition: the toolchain installer scripts' locks are found")


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
            Case("producer-lock-inventory", _producer_lock_inventory),
            Case("producer-lock-scanners-fail-closed", _producer_lock_scanners_fail_closed),
            Case("symlink-escape", _symlink_escape, lane="guest"),
            Case("native-outputs-and-lock", _native_outputs_and_lock, lane="guest"),
            Case("native-directory-lock", _native_directory_lock, lane="guest"),
            Case("native-linked-proof-workspace", _native_linked_proof_workspace, lane="guest"),
            Case("native-locks-taken-late", _native_locks_taken_late, lane="guest"),
            Case("native-hard-linked-locks", _native_hard_linked_locks, lane="guest"),
            Case("native-lock-replaced-late", _native_lock_replaced_late, lane="guest"),
            Case("venv-links-and-target-locks", _venv_links_and_target_locks, lane="guest"),
            Case("native-exact-log-ownership", _native_exact_log_ownership, lane="guest"),
            Case("native-log-directories-and-companions", _native_log_directories_and_companions, lane="guest"),
            Case("native-log-locks-and-peer-directories", _native_log_locks_and_peer_directories, lane="guest"),
            Case("native-oracle-locks-of-every-edition", _native_oracle_locks_of_every_edition, lane="guest"),
            Case("persistence-campaign-lock", _persistence_campaign_lock, lane="guest"),
            Case("idealloc-build-lock", _idealloc_build_lock, lane="guest"),
            Case("native-locks-fit-descriptor-limit", _native_locks_fit_descriptor_limit, lane="guest")]
