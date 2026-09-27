# SPDX-License-Identifier: Apache-2.0
"""Batch orchestration preserves inputs and orders publication, CI and retirement."""

import argparse
import json
import subprocess
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import fanout_ci, fanout_retire
from vos.cli import fanout, worktree

FILES = {".gitignore": "/.worktrees/\n/out/\n", "README.md": "base\n",
         "tools/run.py": "raise SystemExit(0)\n"}


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), *args], check=False, capture_output=True,
                          encoding="utf-8", timeout=60)
    ensure(done.returncode == 0, f"fixture Git failed: {done.stderr}")
    return done.stdout.strip()


def _commit(root: Path, name: str) -> str:
    _git(root, "commit", "--allow-empty", "-qm", name)
    return _git(root, "rev-parse", "HEAD")


@contextmanager
def _fixture() -> Iterator[tuple[Path, Path, Path]]:
    with sandbox_tree(FILES) as root, tempfile.TemporaryDirectory(prefix="vos-remote-") as remote:
        _git(root, "config", "user.name", "Fanout test")
        _git(root, "config", "user.email", "fanout@example.invalid")
        _git(root, "config", "commit.gpgsign", "false")
        base = _commit(root, "base")
        _git(root, "branch", "-M", "main")
        _git(Path(remote), "init", "--bare", "-q")
        _git(root, "remote", "add", "origin", remote)
        record = worktree.create(root, "worker", base)
        lane = Path(str(record["path"]))
        yield root, lane, Path(remote)


def _init(root: Path, lane: Path) -> tuple[fanout.Batch, Path]:
    args = argparse.Namespace(batch="example", worktree=[lane], host_worktree=[],
                              remote="origin", cold=True, defer=["separate experiment"])
    return fanout.initialize(root, args), root / "out/fanout/example/state.json"


def _finish_args() -> argparse.Namespace:
    return argparse.Namespace(path=[], message=None, wait_host=0)


def _refuses(action: Callable[[], object], fragment: str) -> None:
    try:
        action()
    except ValueError as err:
        ensure(fragment in str(err), f"expected {fragment}: {err}")
    else:
        raise AssertionError(f"expected refusal: {fragment}")


def _roundtrip_and_handoff() -> None:
    with _fixture() as (root, lane, _):
        (lane / "worker.txt").write_text("landed\n", encoding="utf-8")
        _git(lane, "add", "--", "worker.txt")
        head = _commit(lane, "worker")
        state, path = _init(root, lane)
        ensure(fanout._load(path, root) == state, "journal round-trips")
        fanout.integrate(root, state, path)
        _git(root, "merge-base", "--is-ancestor", head, "HEAD")
        ensure((root / "worker.txt").read_text(encoding="utf-8") == "landed\n",
               "worker changes reach integration")
        revision = _git(root, "rev-parse", "HEAD")
        fanout.integrate(root, state, path)
        ensure(_git(root, "rev-parse", "HEAD") == revision, "resume does not merge twice")
        _commit(lane, "changed handoff")
        _refuses(lambda: fanout.integrate(root, state, path), "handoff changed")


def _conflict() -> None:
    with _fixture() as (root, lane, _):
        (lane / "README.md").write_text("worker\n", encoding="utf-8")
        _git(lane, "add", "--", "README.md")
        _commit(lane, "worker edit")
        (root / "README.md").write_text("integrator\n", encoding="utf-8")
        _git(root, "add", "--", "README.md")
        _commit(root, "integrator edit")
        state, path = _init(root, lane)
        _refuses(lambda: fanout.integrate(root, state, path), "")
        ensure("UU README.md" in _git(root, "status", "--porcelain"),
               "conflict left for integrator, never reset")
        ensure(lane.exists() and state["ci"] is None, "conflict neither dispatches nor retires")


def _publish_wait_resume() -> None:
    with _fixture() as (root, lane, remote):
        _commit(lane, "worker commit")
        state, path = _init(root, lane)
        observed: list[str] = []

        def advance(checkout: Path, ci: fanout_ci.CIState, save: Callable[[], None]) -> bool:
            ensure(checkout == root, "CI uses integration checkout")
            published = _git(remote, "rev-parse", "refs/heads/main")
            ensure(published == ci["revision"], "publication precedes CI")
            ensure(_git(remote, "rev-parse", f"refs/tags/{ci['ref']}") == published,
                   "dispatch tag pins the same revision")
            ensure(ci["cold"], "fresh-proof policy propagates")
            observed.append("ci")
            save()
            return len(observed) > 1

        def retire(checkout: Path, record: fanout_retire.LaneRecord,
                   revision: str, archive_root: Path) -> dict[str, object]:
            ensure(observed == ["ci", "ci"], "retirement follows successful hosted handoff")
            ensure(checkout == root and record.path == str(lane), "only selected lane retires")
            ensure(revision == _git(root, "rev-parse", "HEAD"), "retirement bound to tested commit")
            ensure(archive_root.is_relative_to(root / "out/fanout"), "outputs retained per batch")
            observed.append("retire")
            return {"status": "retired"}

        with (patch.object(fanout_ci, "repository", return_value="example/repo"),
              patch.object(fanout_ci, "advance", side_effect=advance),
              patch.object(fanout_retire, "retire", side_effect=retire)):
            ensure(not fanout.finish(root, state, path, _finish_args()), "pending host stops completion")
            ensure(state["status"] == "host-pending" and not state["retired"], "pending is not success")
            state = fanout._load(path, root)
            ensure(fanout.finish(root, state, path, _finish_args()), "resume finishes")
            ensure(state["status"] == "complete", "completion persisted")
            ensure(fanout.finish(root, state, path, _finish_args()), "completed resume is read-only")
            ensure(observed == ["ci", "ci", "retire"], "no repeated dispatch or retirement")
            _commit(root, "new inputs")
            _refuses(lambda: fanout.finish(root, state, path, _finish_args()), "inputs changed")


def _retirement_resume() -> None:
    with _fixture() as (root, lane, _):
        state, path = _init(root, lane)
        state["status"] = "retiring"
        revision = _git(root, "rev-parse", "HEAD")
        state["ci"] = fanout_ci.new_state("example/repo", f"fanout/example/{revision}",
                                           revision, True)
        # A prior retirement may already have removed the checkout before failing
        # branch deletion. The retirement module owns recovery from its receipt.
        _git(root, "worktree", "remove", str(lane))
        with (patch.object(fanout_ci, "advance", return_value=True),
              patch.object(fanout_retire, "retire", return_value={"status": "retired"}) as retire):
            ensure(fanout.finish(root, state, path, _finish_args()), "partial removal can resume")
            ensure(retire.call_count == 1, "retirement receipt handles missing checkout")


def _paths_and_journal() -> None:
    with _fixture() as (root, lane, _):
        _refuses(lambda: fanout._location(root, "../escape"), "portable")
        state, path = _init(root, lane)
        _refuses(lambda: _init(root, lane), "already exists")
        value = dict(state)
        value["root"] = str(lane)
        path.write_text(json.dumps(value), encoding="utf-8")
        _refuses(lambda: fanout._load(path, root), "different integration")
        fanout._save(path, state)
        _refuses(lambda: fanout._prepare(root, ["../outside"], "bad"), "individual file")
        _refuses(lambda: fanout._prepare(root, ["tools"], "bad"), "individual file")
        _refuses(lambda: fanout._prepare(root, ["README.md"], None), "together")
        with fanout._exclusive(root):
            _refuses(lambda: _lock_again(root), "another fanout")


def _lock_again(root: Path) -> None:
    with fanout._exclusive(root):
        raise AssertionError("second lock must be refused")


def _explicit_commit() -> None:
    with _fixture() as (root, _, _):
        (root / "deliverable.txt").write_text("new\n", encoding="utf-8")
        (root / "unrelated.txt").write_text("other session\n", encoding="utf-8")
        _refuses(lambda: fanout._prepare(root, ["deliverable.txt"], "deliver explicit file"),
                 "uncommitted inputs")
        ensure(_git(root, "show", "HEAD:deliverable.txt") == "new", "explicit path committed")
        ensure("?? unrelated.txt" in _git(root, "status", "--porcelain"),
               "another session's work is not staged")


def _dirty_handoff() -> None:
    with _fixture() as (root, lane, _):
        state, path = _init(root, lane)
        (lane / "uncommitted.txt").write_text("work in progress", encoding="utf-8")
        _refuses(lambda: fanout.integrate(root, state, path), "uncommitted inputs")
        ensure(state["status"] == "initialized", "dirty worker never enters integration")


def cases() -> list[Case]:
    return [Case("journal, merge ancestry and changed handoff", _roundtrip_and_handoff),
            Case("conflict remains for integrator", _conflict),
            Case("publish, pending host, resume and retirement order", _publish_wait_resume),
            Case("partial retirement resumes without checkout", _retirement_resume),
            Case("paths, journal identity and exclusive mutation", _paths_and_journal),
            Case("only explicit paths enter commit", _explicit_commit),
            Case("dirty handoff stops before integration", _dirty_handoff)]
