# SPDX-License-Identifier: Apache-2.0
"""Retire explicitly handed-off lanes, retaining outputs before non-forced removal."""

import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import cast

from vos import env
from vos.cli import worktree


class RetirementError(ValueError):
    """A retirement cannot establish ownership, integration or safe retention."""


@dataclass(frozen=True)
class LaneRecord:
    """Immutable handoff identity; ownership is declared by the batch integrator."""

    path: str
    head: str
    branch: str | None
    owned: bool
    lane: str
    lane_root: str
    primary: str
    admin: str
    log_root: str


def validate_record(value: object) -> LaneRecord:
    """Reject malformed persisted input before interpreting it as a filesystem path."""
    keys = set(LaneRecord.__dataclass_fields__)
    if not isinstance(value, dict) or set(value) != keys:
        raise RetirementError("invalid lane record fields")
    data = cast(dict[str, object], value)
    strings = keys - {"branch", "owned"}
    if any(not isinstance(data[key], str) or not data[key] for key in strings):
        raise RetirementError("invalid lane record strings")
    if type(data["owned"]) is not bool or not (
            data["branch"] is None or (isinstance(data["branch"], str) and data["branch"])):
        raise RetirementError("invalid lane ownership or branch")
    if not re.fullmatch(r"[0-9a-f]{40,64}", str(data["head"])):
        raise RetirementError("invalid lane commit")
    lane = str(data["lane"])
    if lane in {".", ".."} or any(char in lane for char in "/\\\0"):
        raise RetirementError("invalid lane name")
    return LaneRecord(str(data["path"]), str(data["head"]), cast(str | None, data["branch"]),
                      data["owned"], lane, str(data["lane_root"]),
                      str(data["primary"]), str(data["admin"]), str(data["log_root"]))


def _git(root: Path, *args: str, allowed: tuple[int, ...] = (0,)) -> bytes:
    try:
        return worktree._git(root, *args, allowed=allowed)
    except worktree.WorktreeError as exc:
        raise RetirementError(str(exc)) from exc


def _plain(path: Path) -> None:
    """Check each existing component without traversing a link or a mounted child."""
    if not path.is_absolute() or path.resolve() != path:
        raise RetirementError(f"path redirects or is not absolute: {path}")
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise RetirementError(f"path contains a link or junction: {part}")


def _contained(owner: Path, path: Path) -> None:
    _plain(owner)
    _plain(owner / worktree.DIRECTORY)
    _plain(path)
    if (path.parent != owner / worktree.DIRECTORY or path.is_mount()
            or (owner / worktree.DIRECTORY).is_mount()):
        raise RetirementError(f"retirement requires a direct child of {owner / worktree.DIRECTORY}: {path}")


def _clean(path: Path) -> None:
    if _git(path, "status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none"):
        raise RetirementError(f"worker is dirty, including untracked files: {path}")


def _tree_safe(path: Path, *, checkout: bool = False) -> list[Path]:
    """Never recurse through directory links, mount points, or nested checkouts."""
    found: list[Path] = []
    if not path.exists():
        return found
    _plain(path)
    for directory, dirs, files in os.walk(path, followlinks=False):
        current = Path(directory)
        for name in dirs:
            child = current / name
            if child.is_symlink() or child.is_junction() or child.is_mount():
                raise RetirementError(f"output directory redirects or is mounted: {child}")
            if checkout and name == ".git":
                raise RetirementError(f"nested repository must be retained separately: {child}")
            found.append(child)
        for name in files:
            child = current / name
            if checkout and name == ".git" and current != path:
                raise RetirementError(f"nested checkout must be retired separately: {child}")
            found.append(child)
    return found


def snapshot(root: Path, path: Path, owned: bool = True) -> LaneRecord:
    """Freeze Git's identity for one explicitly selected, available worker checkout."""
    _plain(path)
    try:
        owner = worktree.primary(root)
        records = worktree.registered(root)
        record = next((item for item in records[1:] if Path(item.path) == path), None)
        if record is None or not record.lane or not record.lane_root:
            raise RetirementError(f"not a dedicated registered checkout: {path}")
        worktree.verify(root, path, record.head, branch=record.branch, exact=True)
        if owned:
            _contained(owner, path)
        admin = os.fsdecode(_git(path, "rev-parse", "--absolute-git-dir")).strip()
        return LaneRecord(str(path), record.head, record.branch, owned, record.lane,
                          record.lane_root, str(owner), str(Path(admin).resolve()),
                          env.log_root().as_posix())
    except worktree.WorktreeError as exc:
        raise RetirementError(str(exc)) from exc


def _write(path: Path, value: dict[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    _plain(path)
    _plain(temporary)
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def _archive(root: Path, record: LaneRecord, archive_root: Path) -> tuple[Path, str]:
    _plain(root)
    _plain(archive_root)
    allowed = root / "out" / "fanout"
    if not archive_root.is_relative_to(allowed) or archive_root == allowed:
        raise RetirementError(f"retention destination must be beneath {allowed}")
    path = Path(record.path)
    if archive_root.is_relative_to(path):
        raise RetirementError("retention destination is inside the retiring worktree")
    digest = hashlib.sha256(json.dumps(asdict(record), sort_keys=True).encode()).hexdigest()[:16]
    destination = archive_root / f"{record.lane}-{digest}"
    _plain(destination)
    # Include the integration identity: equal batch labels in separate checkouts do
    # not share a native archive. Only the native helper examines native outputs.
    batch = hashlib.sha256(str(archive_root).encode()).hexdigest()[:20]
    return destination, batch


def _check_identity(root: Path, record: LaneRecord, revision: str) -> bool:
    """Return whether the original checkout remains; never repair changed identity."""
    try:
        records = worktree.registered(root)
        if str(worktree.primary(root)) != record.primary:
            raise RetirementError("record belongs to another primary checkout")
        path = Path(record.path)
        _contained(Path(record.primary), path)
        if root.resolve() == path:
            raise RetirementError("the integration checkout cannot retire itself")
        _git(root, "merge-base", "--is-ancestor", record.head, revision)
        matches = [item for item in records if Path(item.path) == path]
        if not matches:
            if path.exists():
                raise RetirementError("removed worktree path has been recreated")
            return False
        current = matches[0]
        if current.locked or current.prunable:
            raise RetirementError("worktree is locked or unavailable")
        if (current.head, current.branch, current.lane, current.lane_root) != (
                record.head, record.branch, record.lane, record.lane_root):
            raise RetirementError("worker HEAD, branch or output lane changed after handoff")
        verified = snapshot(root, path, owned=True)
        if verified != record:
            raise RetirementError("worker administrative identity changed after handoff")
        for item in records:
            child = Path(item.path)
            if child != path and child.is_relative_to(path):
                raise RetirementError(f"nested registered worktree must remain: {child}")
        _clean(path)
        _tree_safe(path, checkout=True)
    except worktree.WorktreeError as exc:
        raise RetirementError(str(exc)) from exc
    return True


def _branch_safe(root: Path, record: LaneRecord, revision: str, *, removing: bool) -> bool:
    if record.branch is None:
        return False
    ref = f"refs/heads/{record.branch}"
    current = _git(root, "rev-parse", "--verify", "--quiet", ref, allowed=(0, 1)).decode().strip()
    if not current:
        if removing:
            raise RetirementError("worker branch disappeared before removal")
        return False
    if current != record.head:
        raise RetirementError("worker branch changed after handoff")
    _git(root, "merge-base", "--is-ancestor", current, revision)
    for item in worktree.registered(root):
        if item.branch == record.branch and (not removing or item.path != record.path):
            raise RetirementError(f"worker branch is checked out at {item.path}")
    return True


def _retain_host(path: Path, destination: Path) -> list[str]:
    ignored = _git(path, "ls-files", "--others", "--ignored", "--exclude-standard",
                   "--directory", "-z")
    retained: list[str] = []
    for raw in ignored.split(b"\0"):
        if not raw:
            continue
        relative = Path(os.fsdecode(raw).rstrip("/"))
        if relative.is_absolute() or ".." in relative.parts:
            raise RetirementError("Git returned an escaping ignored output")
        source, target = path / relative, destination / "checkout" / relative
        _plain(source.parent)
        _plain(target)
        if source.is_dir():
            _tree_safe(source)
        if target.exists() or target.is_symlink():
            raise RetirementError(f"retained output already exists; review before resuming: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        retained.append(str(target))
    return retained


def _guest(record: LaneRecord, batch: str, root: Path) -> dict[str, object]:
    if sys.platform != "win32":
        return retain_native(record.lane, record.lane_root, record.log_root, batch)
    code = ("import json,sys;sys.path.insert(0,'tools');"
            "from vos.fanout_retire import retain_native;"
            "print(json.dumps(retain_native(**json.load(sys.stdin))))")
    payload = {"lane": record.lane, "lane_root": record.lane_root,
               "log_root": record.log_root, "batch": batch}
    done = subprocess.run(["wsl", "-u", "root", "-e", "python3", "-c", code],
                          cwd=root, input=json.dumps(payload), capture_output=True,
                          text=True, check=False, timeout=120)
    if done.returncode:
        raise RetirementError(f"native output retention refused: {done.stderr.strip()}")
    result = json.loads(done.stdout)
    if not isinstance(result, dict):
        raise RetirementError("native output retention returned invalid evidence")
    return cast(dict[str, object], result)


def retain_native(lane: str, lane_root: str, log_root: str, batch: str) -> dict[str, object]:
    """Run only on the native guest; retain outputs while holding their live locks.

    Symlink files are renamed as links, never followed. Directory links and mounted
    subtrees refuse. All existing directory locks (including the proof workspace)
    and *.lock files are held non-blockingly through the move. No glob ever removes
    another lane, and no source path is recursively deleted.
    """
    if sys.platform == "win32":
        raise RetirementError("native output retention must run through the guest")
    import fcntl  # noqa: PLC0415

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", lane) or lane in {".", ".."}:
        raise RetirementError("invalid native lane")
    if not re.fullmatch(r"[a-f0-9]{20}", batch):
        raise RetirementError("invalid native batch")
    source, logs = Path(lane_root), Path(log_root)
    if not PurePosixPath(lane_root).is_absolute() or source.name != f"lane-{lane}":
        raise RetirementError("native lane root does not match the handoff")
    if not logs.is_absolute() or logs == source or logs.is_relative_to(source):
        raise RetirementError("invalid native log root")
    for path in (source, logs):
        _plain(path)
        kind = env.filesystem(path)
        if not kind or kind in env.CROSS_OS_FILESYSTEMS | env.VOLATILE_FILESYSTEMS:
            raise RetirementError(f"retention requires a persistent native filesystem: {path} ({kind})")
    destination = source.parent / "fanout-retained" / batch / lane
    _plain(destination)
    entries = _tree_safe(source)
    selected_logs = sorted(logs.glob(f"*-{lane}.log")) if logs.exists() else []
    targets = [(source, destination / "lane")] if source.exists() else []
    targets.extend((path, destination / "logs" / path.name) for path in selected_logs)
    for before, after in targets:
        _plain(before)
        if before.is_mount() or after.exists() or after.is_symlink():
            raise RetirementError(f"native output or retained destination needs review: {before}, {after}")
    lock_paths = ([source] if source.exists() else []) + [
        path for path in entries if path.is_dir() or path.name.endswith(".lock")]
    with contextlib.ExitStack() as stack:
        for path in lock_paths:
            if path.is_symlink():
                raise RetirementError(f"lock redirects: {path}")
            fd = os.open(path, os.O_RDONLY)
            stack.callback(os.close, fd)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RetirementError(f"native output lock is active: {path}") from exc
        for before, after in targets:
            _plain(before)
            _plain(after)
            after.parent.mkdir(parents=True, exist_ok=True)
            before.rename(after)
    return {"archive": str(destination), "retained": [str(after) for _, after in targets]}


def retire(root: Path, record: LaneRecord, revision: str, archive_root: Path) -> dict[str, object]:
    """Retain outputs, remove one worktree, then prune only its unchanged merged branch.

    A durable receipt precedes removal. If interrupted after Git removes the checkout,
    a retry recognizes that receipt and still checks branch identity and ancestry.
    Refusals preserve everything that has not already been safely archived.
    """
    validate_record(asdict(record))
    if not record.owned:
        return {"status": "retained-host-managed", "path": record.path, "branch": record.branch}
    revision = worktree._commit(root, revision)
    destination, batch = _archive(root, record, archive_root)
    receipt_path = destination / "retirement.json"
    receipt: dict[str, object] = {"record": asdict(record), "revision": revision, "phase": "prepared"}
    previous = receipt_path.exists()
    if previous:
        loaded = json.loads(receipt_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict) or loaded.get("record") != asdict(record):
            raise RetirementError("retirement receipt belongs to another handoff")
        receipt = cast(dict[str, object], loaded)
    present = _check_identity(root, record, revision)
    branch_exists = _branch_safe(root, record, revision, removing=present)
    if not present and (not previous or receipt.get("phase") not in {"removing", "removed", "complete"}):
        raise RetirementError("missing worker has no durable removal receipt")
    destination.mkdir(parents=True, exist_ok=True)
    if present:
        _write(receipt_path, receipt)
        receipt["native"] = _guest(record, batch, root)
        _write(receipt_path, receipt)
        retained = list(cast(list[str], receipt.get("retained", [])))
        retained.extend(_retain_host(Path(record.path), destination))
        receipt["retained"] = retained
        _check_identity(root, record, revision)
        _branch_safe(root, record, revision, removing=True)
        receipt["phase"] = "removing"
        _write(receipt_path, receipt)
        _git(root, "worktree", "remove", "--", record.path)
        receipt["phase"] = "removed"
        _write(receipt_path, receipt)
    if branch_exists:
        _branch_safe(root, record, revision, removing=False)
        _git(root, "branch", "-d", "--", cast(str, record.branch))
    receipt.update({"phase": "complete", "revision": revision})
    _write(receipt_path, receipt)
    return {"status": "retired", "path": record.path, "branch": record.branch,
            "archive": str(destination), "native": receipt.get("native"),
            "retained": receipt.get("retained", []), "revision": revision}
