# SPDX-License-Identifier: Apache-2.0
"""Complete an explicit fan-out batch, including hosted CI and safe retirement."""

import argparse
import json
import re
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import NotRequired, TypedDict, cast

from vos import fanout_ci, fanout_retire, receipts
from vos.cli import worktree
from vos.corpus import find_root

# A reading base is a full lowercase commit SHA, the only form Guest CI's dispatch
# check accepts.
_COMMIT = re.compile(r"[0-9a-f]{40}")

# Seconds between Host CI polls under --wait-host. A poll is two or three GitHub GETs
# and a status read of the integration checkout, so even the longest bound stays far
# inside the API's hourly request limit, and a completed run is seen within seconds.
_HOST_POLL_SECONDS = 5


class FanoutError(ValueError):
    """Batch completion cannot continue without an explicit correction."""


class Batch(TypedDict):
    """Local journal; CI records are evidence for one settled revision only.

    `reading_base` is fixed at init: the commit Guest CI's proofs lane reads beside
    the settled revision, or None. A journal without the key names none.
    """

    version: int
    batch: str
    root: str
    base: str
    branch: str
    remote: str
    cold: bool
    reading_base: NotRequired[str | None]
    deferred: list[str]
    lanes: list[dict[str, object]]
    retired: dict[str, object]
    ci: fanout_ci.CIState | None
    status: str


def _git(root: Path, *args: str) -> str:
    return worktree._git(root, *args).decode("utf-8").strip()


def _clean(root: Path) -> None:
    status = _git(root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise ValueError(f"checkout has uncommitted inputs: {root}\n{status}")
    admin = Path(_git(root, "rev-parse", "--absolute-git-dir"))
    for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply"):
        if (admin / name).exists():
            raise ValueError(f"finish or abort the existing Git operation first: {name}")


def _location(root: Path, name: str) -> Path:
    if not worktree._SLUG.fullmatch(name) or name in worktree._RESERVED:
        raise ValueError("batch must be a portable lowercase lane-style name")
    target = root / "out" / "fanout" / name
    for part in (root / "out", root / "out" / "fanout", target):
        if part.is_symlink() or part.is_junction() or part.resolve() != part:
            raise ValueError(f"batch directory must not redirect: {part}")
    if not worktree._git(root, "check-ignore", "--no-index", "--", "out/fanout/", allowed=(0, 1)):
        raise ValueError("out/fanout must be ignored before recording a batch")
    return target


@contextmanager
def _exclusive(root: Path) -> Iterator[None]:
    """All batches in one integration checkout share a process-lifetime lock."""
    directory = _location(root, "lock").parent
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / ".lock"
    if lock.is_symlink() or lock.is_junction() or lock.resolve() != lock:
        raise ValueError(f"integration lock must not redirect: {lock}")
    with lock.open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if sys.platform == "win32":
            import msvcrt

            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as err:
                raise ValueError("another fanout command owns this integration checkout") from err
        else:
            import fcntl

            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as err:
                raise ValueError("another fanout command owns this integration checkout") from err
        try:
            yield
        finally:
            if sys.platform == "win32":
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _save(path: Path, state: Batch) -> None:
    receipts.write(path, state)


def _load(path: Path, root: Path) -> Batch:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("version") != 1:
        raise ValueError("unsupported fanout journal")
    if value.get("root") != str(root) or value.get("batch") != path.parent.name:
        raise ValueError("journal belongs to a different integration checkout or batch")
    for key in ("base", "branch", "remote", "status"):
        if not isinstance(value.get(key), str) or not value[key]:
            raise ValueError(f"invalid batch {key}")
    if not isinstance(value.get("cold"), bool):
        raise FanoutError("invalid cold policy")
    reading_base = value.get("reading_base")
    if reading_base is not None and (not isinstance(reading_base, str)
                                     or not _COMMIT.fullmatch(reading_base)):
        raise FanoutError("invalid reading base")
    for key in ("deferred", "lanes"):
        if not isinstance(value.get(key), list):
            raise FanoutError(f"invalid batch {key}")
    if not all(isinstance(item, str) for item in value["deferred"]):
        raise ValueError("invalid deferred checks")
    if not isinstance(value.get("retired"), dict):
        raise FanoutError("invalid retirement journal")
    if "ci" not in value:
        raise ValueError("missing CI journal")
    for lane in value["lanes"]:
        fanout_retire.validate_record(lane)
    if value.get("ci") is not None:
        value["ci"] = fanout_ci.validate_state(value["ci"])
        if value["ci"]["cold"] != value["cold"]:
            raise ValueError("CI cold policy differs from the batch")
        if value["ci"].get("reading_base") != reading_base:
            raise ValueError("CI reading base differs from the batch")
    return cast("Batch", value)


def _reading_base(root: Path, value: str | None) -> str | None:
    """The reading base `init` fixes: a commit main's head descends from, or None.

    Every revision the batch settles descends from main's head at init, so it descends
    from this commit too; `finish` refuses to publish the commit itself.
    """
    if value is None:
        return None
    if not _COMMIT.fullmatch(value):
        raise ValueError("--reading-base must be a full lowercase commit SHA")
    named = worktree._git(root, "rev-parse", "--verify", "--quiet", f"{value}^{{commit}}",
                          allowed=(0, 1)).decode("utf-8").strip()
    if named != value:
        raise ValueError(f"--reading-base names no commit in this checkout: {value}")
    try:
        _git(root, "merge-base", "--is-ancestor", value, "HEAD")
    except worktree.WorktreeError as err:
        raise ValueError(f"--reading-base is not an ancestor of main's head: {value}") from err
    return value


def _reading_settled(root: Path, state: Batch, revision: str) -> None:
    """Refuse a revision Guest CI's dispatch check would refuse beside the reading base."""
    base = state.get("reading_base")
    if base is None:
        return
    if base == revision:
        raise ValueError("the settled revision is the reading base itself; Guest CI reads "
                         "only a proper ancestor, so land a change or initialize a new batch")
    try:
        _git(root, "merge-base", "--is-ancestor", base, revision)
    except worktree.WorktreeError as err:
        raise ValueError(f"the settled revision does not descend from the reading base {base}") from err


def _checkout(root: Path, state: Batch) -> None:
    if state["branch"] != "main":
        raise ValueError("completion requires main; initialize a new batch on main")
    if _git(root, "rev-parse", "--show-toplevel") != root.as_posix() and Path(
            _git(root, "rev-parse", "--show-toplevel")).resolve() != root:
        raise ValueError("integration root is no longer a checkout")
    if _git(root, "symbolic-ref", "--short", "HEAD") != state["branch"]:
        raise ValueError("integration branch changed since batch initialization")
    _git(root, "merge-base", "--is-ancestor", state["base"], "HEAD")


def initialize(root: Path, args: argparse.Namespace) -> Batch:
    if _git(root, "symbolic-ref", "--short", "HEAD") != "main":
        raise ValueError("initialize completion on main; select the worktree as a worker to merge and retire")
    path = _location(root, args.batch) / "state.json"
    if path.exists():
        raise ValueError(f"batch already exists: {path}")
    _clean(root)
    paths = [*args.worktree, *args.host_worktree]
    if len({str(path.resolve()) for path in paths}) != len(paths):
        raise ValueError("a worktree may appear only once in a batch")
    for worker in paths:
        if worker.resolve() == root:
            raise ValueError("integration checkout cannot be its own worker")
        _clean(worker)
    lanes = [asdict(fanout_retire.snapshot(root, path, owned=owned))
             for owned, selected in ((True, args.worktree), (False, args.host_worktree))
             for path in selected]
    worktree._branch(root, args.remote)  # Ref-safe literal, never an option or URL.
    _git(root, "remote", "get-url", args.remote)
    state: Batch = {
        "version": 1, "batch": args.batch, "root": str(root),
        "base": _git(root, "rev-parse", "HEAD"),
        "branch": _git(root, "symbolic-ref", "--short", "HEAD"),
        "remote": args.remote, "cold": args.cold,
        "reading_base": _reading_base(root, args.reading_base), "deferred": args.defer,
        "lanes": lanes, "retired": {}, "ci": None, "status": "initialized",
    }
    _save(path, state)
    return state


def _merge_message(root: Path, lane: fanout_retire.LaneRecord) -> str:
    # A push run is titled with this subject, so it names the lane, not a hash.
    name = lane.branch or lane.lane
    latest = _git(root, "log", "-1", "--no-merges", "--format=%s", f"HEAD..{lane.head}")
    return f"Merge {name}: {latest}" if latest else f"Merge {name}"


def integrate(root: Path, state: Batch, path: Path) -> None:
    _checkout(root, state)
    for raw in state["lanes"]:
        lane = fanout_retire.validate_record(raw)
        if lane.path in state["retired"]:
            continue
        _clean(Path(lane.path))
        current = fanout_retire.snapshot(root, Path(lane.path), owned=lane.owned)
        if current != lane:
            raise ValueError(f"worker handoff changed; create a new batch: {lane.path}")
        # An already integrated lane permits authored integrator edits on resume.
        if _git(root, "merge-base", lane.head, "HEAD") == lane.head:
            continue
        _clean(root)
        _git(root, "merge", "--no-ff", "-m", _merge_message(root, lane), lane.head)
        state["ci"] = None
        state["status"] = "integrating"
        _save(path, state)
    state["status"] = "integrated"
    _save(path, state)


def _prepare(root: Path, paths: list[str], message: str | None) -> None:
    """Repair arithmetic; leave co-read and other judgment failures to the integrator."""
    if bool(paths) != bool(message):
        raise ValueError("--path and --message must be supplied together")
    normalized: list[str] = []
    # New deliverables must enter the index before the checker can see them.
    if paths:
        if _git(root, "diff", "--cached", "--name-only"):
            raise ValueError("index already contains staged changes; commit or unstage them first")
        for relative in paths:
            target = root / relative
            if (Path(relative).is_absolute() or not target.resolve().is_relative_to(root)
                    or target.is_dir() or target.is_symlink() or target.is_junction()):
                raise ValueError(f"--path must name an individual file inside this checkout: {relative}")
            normalized.append(target.relative_to(root).as_posix())
        print(_git(root, "status", "--short", "--untracked-files=all"), flush=True)
        for relative in normalized:
            print(_git(root, "--literal-pathspecs", "diff", "HEAD", "--", relative), flush=True)
            if not _git(root, "--literal-pathspecs", "ls-files", "--", relative):
                print(f"new file: {relative}\n{(root / relative).read_text(encoding='utf-8')}", flush=True)
        _git(root, "--literal-pathspecs", "add", "--", *normalized)
    result = subprocess.run([sys.executable, str(root / "tools" / "run.py"), "check", "--fix"],
                            cwd=root, check=False, timeout=300)
    if result.returncode:
        raise ValueError("repair/check reported findings; resolve them and required co-reads before finish")
    if paths:
        # Repair may have changed named files. Other derived files remain unstaged
        # and prevent publication until the integrator explicitly selects them.
        for relative in normalized:
            print(_git(root, "--literal-pathspecs", "diff", "--", relative), flush=True)
        _git(root, "--literal-pathspecs", "add", "--", *normalized)
        if _git(root, "diff", "--cached", "--name-only"):
            _git(root, "commit", "-m", cast("str", message))
    _clean(root)


def _publish(root: Path, state: Batch, revision: str) -> str:
    _settled(root, state, revision)
    remote = state["remote"]
    # Explicitly disable followTags even if a user's Git configuration enables it.
    _git(root, "-c", "push.followTags=false", "push", remote, f"{revision}:refs/heads/main")
    _published(root, state, revision)
    return "main"


def _published(root: Path, state: Batch, revision: str) -> None:
    answer = _git(root, "ls-remote", "--exit-code", state["remote"], "refs/heads/main")
    if answer.split() != [revision, "refs/heads/main"]:
        raise ValueError("remote main changed; integrate its changes and refresh hosted evidence")


def _settled(root: Path, state: Batch, revision: str) -> None:
    _checkout(root, state)
    _clean(root)
    if _git(root, "rev-parse", "HEAD") != revision:
        raise ValueError("integration revision changed during hosted validation or retirement")


def finish(root: Path, state: Batch, path: Path, args: argparse.Namespace) -> bool:
    _checkout(root, state)
    if state["status"] == "complete":
        _clean(root)
        ci = state["ci"]
        if ci is None or ci["revision"] != _git(root, "rev-parse", "HEAD"):
            raise ValueError("completed batch inputs changed; initialize a new batch")
        _published(root, state, ci["revision"])
        return True
    if state["status"] != "retiring":
        integrate(root, state, path)
        _prepare(root, args.path, args.message)
    else:
        # A fix to the retirement code may itself need a new tested revision.
        # Already removed workers resume via their durable removal receipts.
        _prepare(root, args.path, args.message)
    revision = _git(root, "rev-parse", "HEAD")
    if state["ci"] is None or state["ci"]["revision"] != revision:
        _reading_settled(root, state, revision)
        ref = _publish(root, state, revision)
        state["ci"] = fanout_ci.new_state(fanout_ci.repository(root, state["remote"]),
                                          ref, revision, state["cold"],
                                          state.get("reading_base"))
        state["status"] = "published"
        _save(path, state)
    deadline = time.monotonic() + args.wait_host
    while True:
        _settled(root, state, revision)
        ready = fanout_ci.advance(root, state["ci"], lambda: _save(path, state))
        if ready:
            break
        state["status"] = "host-pending"
        _save(path, state)
        host = state["ci"]["host"]
        print(f"Host CI {host['status'] if host else 'pending'}: "
              f"{host['url'] if host else 'awaiting dispatch'}", flush=True)
        if time.monotonic() >= deadline:
            return False
        time.sleep(min(_HOST_POLL_SECONDS, max(0, deadline - time.monotonic())))
    state["status"] = "retiring"
    _save(path, state)
    for raw in state["lanes"]:
        _settled(root, state, revision)
        _published(root, state, revision)
        lane = fanout_retire.validate_record(raw)
        if lane.path not in state["retired"]:
            state["retired"][lane.path] = fanout_retire.retire(
                root, lane, revision, path.parent / "retained")
            _save(path, state)
    _settled(root, state, revision)
    _published(root, state, revision)
    state["status"] = "complete"
    _save(path, state)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    init = subs.add_parser("init", help="record completed worker handoffs and batch ownership")
    init.add_argument("--worktree", action="append", type=Path, default=[],
                      help="batch-owned worktree to integrate and retire (repeatable)")
    init.add_argument("--host-worktree", action="append", type=Path, default=[],
                      help="host-owned worktree to integrate and retain (repeatable)")
    init.add_argument("--remote", default="origin")
    init.add_argument("--cold", action="store_true", help="require cold Guest CI and fresh proofs")
    init.add_argument("--reading-base", metavar="COMMIT",
                      help="full lowercase SHA of a commit main's head descends from; "
                           "Guest CI's proofs lane reads that commit's proofs and compares "
                           "them with the settled revision's (default: no reading)")
    init.add_argument("--defer", action="append", default=[], help="acceptance check outside CI")
    joining = subs.add_parser("integrate", help="merge recorded worker commits, stopping on conflicts")
    finishing = subs.add_parser("finish", help="repair, publish, require Host CI, dispatch Guest CI, retire")
    finishing.add_argument("--path", action="append", default=[], help="individual file to stage and commit")
    finishing.add_argument("--message", help="commit message for explicitly selected --path files")
    finishing.add_argument("--wait-host", type=int, default=0, metavar="SECONDS",
                           help="bounded Host CI wait; default returns pending for later resume")
    status = subs.add_parser("status", help="read local evidence without querying Guest CI")
    for sub in (init, joining, finishing, status):
        sub.add_argument("batch")
    args = parser.parse_args(argv)
    if args.command == "finish" and not 0 <= args.wait_host <= 7200:
        parser.error("--wait-host must be between 0 and 7200 seconds")
    try:
        root = find_root().resolve()
        path = _location(root, args.batch) / "state.json"
        with _exclusive(root):
            if args.command == "init":
                state = initialize(root, args)
            else:
                state = _load(path, root)
                if args.command == "integrate":
                    integrate(root, state, path)
                elif args.command == "finish" and not finish(root, state, path, args):
                    print(f"Host CI pending; resume: python tools/run.py fanout finish {args.batch}")
                    return 1
            print(json.dumps(state, indent=2))
            print(f"Journal: {path}")
    except (OSError, ValueError, fanout_ci.CIError, subprocess.SubprocessError) as err:
        print(f"fanout failed: {err}", file=sys.stderr)
        return 1
    return 0
