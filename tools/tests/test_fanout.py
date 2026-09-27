# SPDX-License-Identifier: Apache-2.0
"""Batch integration preserves worker ancestry, the journal and explicit commit paths."""

import json
from pathlib import Path

from tests.fanout_fixture import commit, fixture, git, init, refuses
from tests.harness import Case, ensure
from vos.cli import fanout


def _roundtrip_and_handoff() -> None:
    with fixture() as (root, lane, _):
        (lane / "worker.txt").write_text("landed\n", encoding="utf-8")
        git(lane, "add", "--", "worker.txt")
        head = commit(lane, "worker")
        state, path = init(root, lane)
        ensure(fanout._load(path, root) == state, "journal round-trips")
        fanout.integrate(root, state, path)
        git(root, "merge-base", "--is-ancestor", head, "HEAD")
        ensure((root / "worker.txt").read_text(encoding="utf-8") == "landed\n",
               "worker changes reach integration")
        revision = git(root, "rev-parse", "HEAD")
        fanout.integrate(root, state, path)
        ensure(git(root, "rev-parse", "HEAD") == revision, "resume does not merge twice")
        commit(lane, "changed handoff")
        refuses(lambda: fanout.integrate(root, state, path), "handoff changed")


def _conflict() -> None:
    with fixture() as (root, lane, _):
        (lane / "README.md").write_text("worker\n", encoding="utf-8")
        git(lane, "add", "--", "README.md")
        commit(lane, "worker edit")
        (root / "README.md").write_text("integrator\n", encoding="utf-8")
        git(root, "add", "--", "README.md")
        commit(root, "integrator edit")
        state, path = init(root, lane)
        refuses(lambda: fanout.integrate(root, state, path), "")
        ensure("UU README.md" in git(root, "status", "--porcelain"),
               "conflict left for integrator, never reset")
        ensure(lane.exists() and state["ci"] is None, "conflict neither dispatches nor retires")


def _paths_and_journal() -> None:
    with fixture() as (root, lane, _):
        refuses(lambda: fanout._location(root, "../escape"), "portable")
        state, path = init(root, lane)
        refuses(lambda: init(root, lane), "already exists")
        value = dict(state)
        value["root"] = str(lane)
        path.write_text(json.dumps(value), encoding="utf-8")
        refuses(lambda: fanout._load(path, root), "different integration")
        fanout._save(path, state)
        refuses(lambda: fanout._prepare(root, ["../outside"], "bad"), "individual file")
        refuses(lambda: fanout._prepare(root, ["tools"], "bad"), "individual file")
        refuses(lambda: fanout._prepare(root, ["README.md"], None), "together")
        with fanout._exclusive(root):
            refuses(lambda: _lock_again(root), "another fanout")


def _lock_again(root: Path) -> None:
    with fanout._exclusive(root):
        raise AssertionError("second lock must be refused")


def _explicit_commit() -> None:
    with fixture() as (root, _, _):
        (root / "deliverable.txt").write_text("new\n", encoding="utf-8")
        (root / "unrelated.txt").write_text("other session\n", encoding="utf-8")
        refuses(lambda: fanout._prepare(root, ["deliverable.txt"], "deliver explicit file"),
                 "uncommitted inputs")
        ensure(git(root, "show", "HEAD:deliverable.txt") == "new", "explicit path committed")
        ensure("?? unrelated.txt" in git(root, "status", "--porcelain"),
               "another session's work is not staged")


def _dirty_handoff() -> None:
    with fixture() as (root, lane, _):
        state, path = init(root, lane)
        (lane / "uncommitted.txt").write_text("work in progress", encoding="utf-8")
        refuses(lambda: fanout.integrate(root, state, path), "uncommitted inputs")
        ensure(state["status"] == "initialized", "dirty worker never enters integration")


def cases() -> list[Case]:
    return [Case("journal, merge ancestry and changed handoff", _roundtrip_and_handoff),
            Case("conflict remains for integrator", _conflict),
            Case("paths, journal identity and exclusive mutation", _paths_and_journal),
            Case("only explicit paths enter commit", _explicit_commit),
            Case("dirty handoff stops before integration", _dirty_handoff)]
