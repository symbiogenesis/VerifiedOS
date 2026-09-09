# SPDX-License-Identifier: Apache-2.0
"""Synchronize the root instruction documents without guessing which edit wins."""

import argparse
import base64
import hashlib
import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path

from vos import env, receipts
from vos.corpus import find_root

NAMES = ("AGENTS.md", "CLAUDE.md")
CHECKPOINT = "out/instructions-sync.json"
RESOLVE = "review both files, then run `python tools/run.py sync-instructions --from AGENTS.md` " \
          "or `--from CLAUDE.md` to choose the complete result"


class SyncError(ValueError):
    """A sync cannot choose or safely publish the two documents."""


def _read(root: Path) -> dict[str, bytes | None]:
    """Read only the named regular files; never follow a link outside the checkout."""
    found: dict[str, bytes | None] = {}
    for name in NAMES:
        path = root / name
        try:
            before = path.lstat()
        except FileNotFoundError:
            found[name] = None
            continue
        if not stat.S_ISREG(before.st_mode) or path.resolve().parent != root:
            raise SyncError(f"{name} must be a regular file directly inside {root}")
        with path.open("rb") as handle:
            opened = os.fstat(handle.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise SyncError(f"{name} changed while opening it; rerun")
            found[name] = handle.read()
    return found


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          env={**os.environ, **env.git_env(root)}, check=False, timeout=30)


def _head(root: Path) -> str | None:
    tip = _git(root, "rev-parse", "--verify", "HEAD")
    if tip.returncode:
        return None
    return tip.stdout.decode("ascii").strip()


def _baseline(root: Path, revision: str | None) -> bytes | None:
    """Only two equal committed blobs establish which working file changed."""
    if revision is None:
        return None
    versions = [_git(root, "show", f"{revision}:{name}") for name in NAMES]
    if any(part.returncode for part in versions):
        return None
    left, right = (part.stdout for part in versions)
    return left if left == right else None


def _state_path(root: Path) -> Path:
    path = root / CHECKPOINT
    if path.parent.is_symlink() or path.parent.resolve().parent != root:
        raise SyncError(f"{CHECKPOINT} must stay directly beneath this checkout's out directory")
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise SyncError(f"{CHECKPOINT} must be a regular file")
    return path


def _stamp(content: bytes, revision: str | None) -> str:
    return hashlib.sha256((revision or "").encode("ascii") + b"\0" + content).hexdigest()


def _checkpoint(root: Path, revision: str | None) -> bytes | None:
    """A verified local baseline is valid only while its recorded HEAD still stands."""
    path = _state_path(root)
    try:
        record = json.loads(path.read_bytes())
        if not isinstance(record, dict) or record.get("schema") != 1 or record.get("head") != revision:
            return None
        encoded = record.get("content")
        if not isinstance(encoded, str):
            return None
        content = base64.b64decode(encoded, validate=True)
        return content if record.get("sha256") == _stamp(content, revision) else None
    except (FileNotFoundError, ValueError):
        return None


def _remember(root: Path, revision: str | None, content: bytes) -> None:
    if _checkpoint(root, revision) != content:
        receipts.write(_state_path(root), {"schema": 1, "head": revision,
                       "content": base64.b64encode(content).decode("ascii"),
                       "sha256": _stamp(content, revision)})


def _merge(root: Path, before: bytes, left: bytes, right: bytes) -> bytes:
    """Git merges temporary bytes only; conflict markers never reach the documents."""
    with tempfile.TemporaryDirectory(prefix="vos-instructions-") as td:
        paths = [Path(td) / name for name in ("agents", "base", "claude")]
        for path, content in zip(paths, (left, before, right), strict=True):
            path.write_bytes(content)
        done = _git(root, "merge-file", "-p", *map(str, paths))
    if done.returncode:
        detail = done.stderr.decode("utf-8", errors="replace").strip()
        raise SyncError("both instruction files changed and could not be merged; "
                        f"{RESOLVE}" + (f" ({detail})" if detail else ""))
    return done.stdout


def _replace(temporary: Path, target: Path) -> None:
    temporary.replace(target)


def _publish(root: Path, expected: dict[str, bytes | None], content: bytes) -> list[str]:
    """Stage complete bytes, re-read both inputs, then atomically replace each target.

    Each replacement is atomic. A failed second replacement leaves the merged text
    in the first file and the other original intact, so no source edit is discarded.
    Concurrent editors do not share a lock: checking again before each replacement
    catches edits during planning and staging rather than overwriting them silently.
    """
    changed: list[str] = []
    for name in NAMES:
        if expected[name] == content:
            continue
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=root, prefix=".instruction-sync-",
                                             suffix=".tmp", delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            if _read(root) != expected:
                raise SyncError("instruction files changed while syncing; rerun against "
                                "the current files" + (f" (already updated {', '.join(changed)})"
                                                       if changed else ""))
            path = root / name
            if expected[name] is not None:
                temporary.chmod(stat.S_IMODE(path.stat().st_mode))
            _replace(temporary, path)
            expected[name] = content
            changed.append(name)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return changed


def sync(root: Path, *, check: bool = False, source: str | None = None) -> str:
    """Return the successful action; refuse ambiguous edits without changing either file."""
    root = root.resolve(strict=True)
    if source is not None and source not in NAMES:
        raise SyncError(f"--from must name {' or '.join(NAMES)}")
    if check and source is not None:
        raise SyncError("--check is read-only and cannot be combined with --from")
    current = _read(root)
    left, right = (current[name] for name in NAMES)
    if left is None and right is None:
        raise SyncError("AGENTS.md and CLAUDE.md are both missing; create one before syncing")
    if left is not None and left == right:
        if not check:
            _remember(root, _head(root), left)
        return "AGENTS.md and CLAUDE.md are in sync"
    if check:
        raise SyncError("AGENTS.md and CLAUDE.md differ or one is missing; "
                        "run `python tools/run.py sync-instructions`")
    revision = _head(root)
    before = _checkpoint(root, revision)
    if source is not None:
        chosen = current[source]
        if chosen is None:
            raise SyncError(f"cannot sync from missing {source}")
    elif left is None or right is None:
        chosen = right if left is None else left
    else:
        if before is None:
            before = _baseline(root, revision)
        if before is None:
            raise SyncError("the committed instruction files have no equal baseline; " + RESOLVE)
        chosen = right if left == before else left if right == before else _merge(
            root, before, left, right)
    if chosen is None:
        raise SyncError("no instruction text is available to synchronize")
    changed = _publish(root, current, chosen)
    if _read(root) != dict.fromkeys(NAMES, chosen):
        raise SyncError("instruction files changed before sync completed; rerun")
    _remember(root, revision, chosen)
    return f"synchronized {', '.join(changed)}; both instruction files now match"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true", help="fail on drift without writing")
    action.add_argument("--from", choices=NAMES, dest="source",
                        help="explicitly choose the file whose complete text wins")
    args = parser.parse_args(argv)
    try:
        print(sync(find_root(), check=args.check, source=args.source))
    except (OSError, ValueError, subprocess.SubprocessError) as err:
        print(f"instruction sync failed: {err}")
        return 1
    return 0
