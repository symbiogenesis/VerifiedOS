# SPDX-License-Identifier: Apache-2.0
"""Provision isolated Git worktrees beneath the primary checkout's .worktrees directory."""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PureWindowsPath

from vos import env
from vos.corpus import find_root

DIRECTORY = ".worktrees"
_SLUG = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?")
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
             *(f"lpt{i}" for i in range(1, 10))}
_GIT_LOCATION = {"GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"}


class WorktreeError(ValueError):
    """A worktree cannot be provisioned or verified without guessing."""


@dataclass(frozen=True)
class Worktree:
    """Git's registered checkout, including records whose directory is missing."""

    path: str
    head: str = ""
    branch: str | None = None
    bare: bool = False
    locked: bool = False
    prunable: bool = False


def _git(root: Path, *args: str, allowed: tuple[int, ...] = (0,)) -> bytes:
    if os.environ.get("VOS_GIT_DIR"):
        raise WorktreeError("unset VOS_GIT_DIR before using worktree commands; each checkout "
                            "must resolve its own Git administrative directory")
    child_env = {key: value for key, value in os.environ.items() if key not in _GIT_LOCATION}
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          env={**child_env, **env.git_env(root)}, check=False, timeout=60)
    if done.returncode not in allowed:
        raise WorktreeError(done.stderr.decode("utf-8", errors="replace").strip()
                            or f"git {args[0]} exited {done.returncode}")
    return done.stdout


def _windows_path(value: str) -> Path:
    bridge = shutil.which("wslpath")
    if bridge is None:
        raise WorktreeError(f"cannot resolve this platform's worktree path: {value}")
    done = subprocess.run([bridge, "-u", value], capture_output=True,
                          text=True, check=False, timeout=30)
    if done.returncode:
        raise WorktreeError(f"cannot translate worktree path: {value}")
    return Path(done.stdout.removesuffix("\n"))


def _path(value: str) -> Path:
    """Translate a Windows registration when Git is being read through WSL."""
    path = Path(value)
    if sys.platform != "win32" and not path.exists():
        # Linux Git can prepend the admin directory to a Windows absolute backlink.
        # Only its own gitdir file may establish that this suffix is a Windows path.
        windows = re.search(r"/([A-Za-z]:/.*)$", value)
        if windows:
            admin = Path(value[:windows.start()])
            pointer = admin / "gitdir"
            if admin.parent.name == "worktrees" and pointer.is_file():
                target = PureWindowsPath(pointer.read_text(encoding="utf-8").removesuffix("\n"))
                if target.is_absolute() and target.name == ".git" and target.parent == PureWindowsPath(windows[1]):
                    return _path(windows[1])
    if not path.is_absolute() and PureWindowsPath(value).is_absolute():
        path = _windows_path(value)
    if not path.is_absolute():
        raise WorktreeError(f"Git returned a non-absolute worktree path: {value}")
    return path.resolve()


def registered(root: Path) -> list[Worktree]:
    """Parse NUL-delimited porcelain; spaces, newlines and quotes are path content."""
    result: list[Worktree] = []
    for block in _git(root, "worktree", "list", "--porcelain", "-z").split(b"\0\0"):
        if not block:
            continue
        fields = dict(os.fsdecode(part).partition(" ")[::2]
                      for part in block.split(b"\0") if part)
        if "worktree" not in fields:
            raise WorktreeError("Git returned a worktree record without its path")
        branch = fields.get("branch")
        result.append(Worktree(str(_path(fields["worktree"])), fields.get("HEAD", ""),
                               branch.removeprefix("refs/heads/") if branch else None,
                               "bare" in fields, "locked" in fields, "prunable" in fields))
    if not result:
        raise WorktreeError("Git returned no worktrees")
    return result


def primary(root: Path) -> Path:
    """Git lists the main checkout first, even when invoked in a linked checkout."""
    first = registered(root)[0]
    if first.bare:
        raise WorktreeError("a bare repository has no primary checkout for .worktrees")
    path = Path(first.path)
    if not path.is_dir():
        raise WorktreeError(f"primary checkout is unavailable: {path}")
    return path


def _commit(root: Path, revision: str) -> str:
    if not revision or revision.startswith("-"):
        raise WorktreeError("--base must name a commit revision")
    return _git(root, "rev-parse", "--verify", "--end-of-options",
                f"{revision}^{{commit}}").decode("ascii").strip()


def _branch(root: Path, branch: str) -> None:
    validated = _git(root, "check-ref-format", "--branch", branch).decode("utf-8").strip()
    if validated != branch:
        raise WorktreeError("branch must be a literal fresh branch name")
    for part in branch.split("/"):
        if part.casefold().split(".")[0] in _RESERVED:
            raise WorktreeError(f"branch contains a Windows-reserved component: {part}")


def _isolated(path: Path, records: list[Worktree]) -> None:
    """Every enclosing checkout must exclude this worktree from its own corpus."""
    for record in records:
        ancestor = Path(record.path)
        if ancestor == path or not path.is_relative_to(ancestor):
            continue
        relative = path.relative_to(ancestor).as_posix()
        if _git(ancestor, "--literal-pathspecs", "ls-files", "-z", "--", relative):
            raise WorktreeError(f"ancestor checkout {ancestor} tracks entries at or beneath "
                                f"{relative}; choose a destination outside its tracked corpus")
        if not _git(ancestor, "check-ignore", "--no-index", "--", f"{relative}/", allowed=(0, 1)):
            raise WorktreeError(f"ancestor checkout {ancestor} must ignore /{relative}/ in "
                                "its .gitignore before this worktree can be used")


def verify(root: Path, path: Path, base: str, *, branch: str | None = None,
           exact: bool = False) -> dict[str, str | bool | None]:
    """Accept a registered dedicated checkout, including one supplied by an application."""
    if not path.is_absolute():
        raise WorktreeError("verification requires the assigned absolute checkout path")
    path = path.resolve(strict=True)
    records = registered(root)
    found = next((record for record in records[1:] if Path(record.path) == path), None)
    if found is None or found.bare:
        raise WorktreeError(f"not an available dedicated worktree of this repository: {path}")
    _isolated(path, records)
    actual_root = _path(os.fsdecode(_git(path, "rev-parse", "--show-toplevel")).removesuffix("\n"))
    if actual_root != path:
        raise WorktreeError(f"assigned path is not a checkout root: {path}")
    common = [_path(os.fsdecode(_git(where, "rev-parse", "--path-format=absolute",
                                    "--git-common-dir")).removesuffix("\n"))
              for where in (root, path)]
    if common[0] != common[1]:
        raise WorktreeError(f"registered path now belongs to a different repository: {path}")
    admin = _path(os.fsdecode(_git(path, "rev-parse", "--absolute-git-dir")).removesuffix("\n"))
    backlink = (admin / "gitdir").read_text(encoding="utf-8").removesuffix("\n")
    linked = (_path(backlink) if Path(backlink).is_absolute() or PureWindowsPath(backlink).is_absolute()
              else (admin / backlink).resolve())
    if linked != path / ".git":
        raise WorktreeError(f"Git administrative directory points to a different checkout: {linked}")
    expected = _commit(root, base)
    head = _commit(path, "HEAD")
    actual_branch = _git(path, "symbolic-ref", "--quiet", "--short", "HEAD",
                         allowed=(0, 1)).decode("utf-8").strip() or None
    if branch is not None and actual_branch != branch:
        raise WorktreeError(f"expected branch {branch}, found {actual_branch or 'detached HEAD'}")
    _git(path, "merge-base", "--is-ancestor", expected, head)
    if exact and head != expected:
        raise WorktreeError(f"expected exact base {expected}, found HEAD {head}")
    return {"path": str(path), "base": expected, "head": head, "branch": actual_branch,
            "exact_base": head == expected}


def create(root: Path, lane: str, base: str, *, branch: str | None = None
           ) -> dict[str, str | bool | None]:
    """Create once at an explicit commit; never reuse a path or reset an existing branch."""
    if not _SLUG.fullmatch(lane) or lane in _RESERVED:
        raise WorktreeError("lane must be 1-80 lowercase letters/digits with interior hyphens, "
                            "and cannot be a Windows-reserved name")
    owner = primary(root)
    worktrees = owner / DIRECTORY
    if worktrees.is_symlink() or worktrees.is_junction() or worktrees.resolve() != worktrees:
        raise WorktreeError(f"worktree directory must not redirect outside its primary: {worktrees}")
    if worktrees.exists() and not worktrees.is_dir():
        raise WorktreeError(f"worktree root is not a directory: {worktrees}")
    ignored = _git(owner, "check-ignore", "--no-index", "--", f"{DIRECTORY}/", allowed=(0, 1))
    if not ignored:
        raise WorktreeError(f"add /{DIRECTORY}/ to the primary checkout's .gitignore first")
    target = worktrees / lane
    if target.exists() or target.is_symlink() or target.is_junction():
        raise WorktreeError(f"worktree path already exists, including an empty directory: {target}")
    records = registered(owner)
    if any(Path(record.path) == target for record in records):
        raise WorktreeError(f"worktree path is already registered: {target}")
    _isolated(target, records)
    name = branch if branch is not None else f"work/{lane}"
    _branch(owner, name)
    if _git(owner, "rev-parse", "--verify", "--quiet", f"refs/heads/{name}", allowed=(0, 1)):
        raise WorktreeError(f"branch already exists; choose a fresh branch: {name}")
    expected = _commit(root, base)
    # mkdir is deliberately non-recursive: the resolved primary owns this one root.
    worktrees.mkdir(exist_ok=True)
    if worktrees.is_symlink() or worktrees.is_junction() or worktrees.resolve() != worktrees:
        raise WorktreeError(f"worktree directory changed before provisioning: {worktrees}")
    _git(owner, "worktree", "add", "--relative-paths", "-b", name, "--", str(target), expected)
    return verify(owner, target, expected, branch=name, exact=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    listing = subs.add_parser("list", help="show primary, default directory and registered worktrees")
    creating = subs.add_parser("create", help="provision a fresh lane at an explicit base commit")
    creating.add_argument("lane")
    verifying = subs.add_parser("verify", help="verify an assigned registered checkout")
    verifying.add_argument("path", type=Path)
    verifying.add_argument("--exact", action="store_true", help="require HEAD equal to --base")
    for sub in (creating, verifying):
        sub.add_argument("--base", required=True, help="expected base commit revision")
        sub.add_argument("--branch", help="fresh branch name (create), or expected branch (verify)")
    for sub in (listing, creating, verifying):
        sub.add_argument("--json", action="store_true", help="emit machine-readable absolute paths")
    args = parser.parse_args(argv)
    try:
        root = find_root()
        if args.command == "list":
            owner = primary(root)
            result = {"primary": str(owner), "root": str(owner / DIRECTORY),
                      "worktrees": [asdict(record) for record in registered(root)]}
        elif args.command == "create":
            result = create(root, args.lane, args.base, branch=args.branch)
        else:
            result = verify(root, args.path, args.base, branch=args.branch, exact=args.exact)
        print(json.dumps(result, indent=2) if args.json else "\n".join(
            f"{key}: {value}" for key, value in result.items()))
    except (OSError, ValueError, subprocess.SubprocessError) as err:
        print(f"worktree failed: {err}", file=sys.stderr)
        return 1
    return 0
