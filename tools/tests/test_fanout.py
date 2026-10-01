# SPDX-License-Identifier: Apache-2.0
"""Batch integration preserves worker ancestry, the journal and explicit commit paths."""

import json
from pathlib import Path

from tests.fanout_fixture import commit, fixture, git, init, refuses
from tests.harness import Case, ensure
from vos import fanout_ci
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
        ensure(git(root, "log", "-1", "--format=%s") == "Merge work/worker: worker",
               "the merge subject, a push run's title, names the lane and its work")
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


def _reading_base_fixed_at_init() -> None:
    with fixture() as (root, lane, _):
        base = git(root, "rev-parse", "HEAD")
        head = commit(root, "settled on main")
        unmerged = commit(lane, "worker only")
        tree = git(root, "rev-parse", f"{base}^{{tree}}")
        # Git peels an annotated tag to its commit, so only comparing the named commit
        # with the value refuses the tag object's SHA.
        git(root, "-c", "tag.gpgSign=false", "tag", "-a", "-m", "reading base", "named", base)
        tag = git(root, "rev-parse", "named")
        # Guest CI's dispatch check takes only a full lowercase commit SHA.
        for value, fragment in ((base[:7], "full lowercase"), ("A" * 40, "full lowercase"),
                                ("", "full lowercase"), (f"{base}\n", "full lowercase"),
                                ("f" * 40, "names no commit"), (tree, "names no commit"),
                                (tag, "names no commit"), (unmerged, "not an ancestor")):
            refuses(lambda value=value: init(root, lane, value), fragment)
            ensure(not (root / "out/fanout/example/state.json").exists(),
                   f"a refused reading base {value!r} recorded a batch")
        state, path = init(root, lane, base)
        ensure(state["reading_base"] == base, "init fixes the reading base in the journal")
        ensure(fanout._load(path, root) == state, "the reading base round-trips")
        # A CI record must name the batch's reading base, or none where the batch has none.
        state["ci"] = fanout_ci.new_state("example/repo", "main", head, True)
        fanout._save(path, state)
        refuses(lambda: fanout._load(path, root), "CI reading base differs")
        state["ci"] = fanout_ci.new_state("example/repo", "main", head, True, base)
        fanout._save(path, state)
        ensure(fanout._load(path, root) == state, "an agreeing CI record loads")
    with fixture() as (root, lane, _):
        state, path = init(root, lane)
        ensure(state["reading_base"] is None, "without the option a batch names no reading base")
        # A journal without the field resumes with no reading base.
        legacy = {key: value for key, value in state.items() if key != "reading_base"}
        path.write_text(json.dumps(legacy), encoding="utf-8")
        ensure(fanout._load(path, root).get("reading_base") is None,
               "a journal without the field names no reading base")
        for bad in ("A" * 40, "a" * 7, 5, ""):
            path.write_text(json.dumps({**legacy, "reading_base": bad}), encoding="utf-8")
            refuses(lambda: fanout._load(path, root), "invalid reading base")


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
            Case("reading base fixed at init and resumable without it",
                 _reading_base_fixed_at_init),
            Case("dirty handoff stops before integration", _dirty_handoff)]
