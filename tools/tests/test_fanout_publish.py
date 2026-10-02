# SPDX-License-Identifier: Apache-2.0
"""Batch completion publishes only main, then orders hosted CI and retirement."""

from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

from tests.fanout_fixture import commit, finish_args, fixture, git, init, refuses
from tests.harness import Case, ensure
from vos import fanout_ci, fanout_retire
from vos.cli import fanout

# Each case builds its own repository, remote and lane through fanout_fixture, and
# patches only inside a `with`, so the cases share no state, and a sharded run spreads
# them over every shard (vos/cli/test.py).
INDEPENDENT_CASES = True


def _publish_wait_resume() -> None:
    with fixture() as (root, lane, remote):
        commit(lane, "worker commit")
        state, path = init(root, lane)
        observed: list[str] = []

        def advance(checkout: Path, ci: fanout_ci.CIState, save: Callable[[], None]) -> bool:
            ensure(checkout == root, "CI uses integration checkout")
            published = git(remote, "rev-parse", "refs/heads/main")
            ensure(published == ci["revision"], "publication precedes CI")
            ensure(ci["ref"] == "main", "dispatch always uses main")
            ensure(git(remote, "for-each-ref", "--format=%(refname)") == "refs/heads/main",
                   "publication creates no work branch or tag")
            ensure(ci["cold"], "fresh-proof policy propagates")
            observed.append("ci")
            save()
            return len(observed) > 1

        def retire(checkout: Path, record: fanout_retire.LaneRecord,
                   revision: str, archive_root: Path) -> dict[str, object]:
            ensure(observed == ["ci", "ci"], "retirement follows successful hosted handoff")
            ensure(checkout == root and record.path == str(lane), "only selected lane retires")
            ensure(revision == git(root, "rev-parse", "HEAD"), "retirement bound to tested commit")
            ensure(archive_root.is_relative_to(root / "out/fanout"), "outputs retained per batch")
            observed.append("retire")
            return {"status": "retired"}

        with (patch.object(fanout_ci, "repository", return_value="example/repo"),
              patch.object(fanout_ci, "advance", side_effect=advance),
              patch.object(fanout_retire, "retire", side_effect=retire)):
            ensure(not fanout.finish(root, state, path, finish_args()), "pending host stops completion")
            ensure(state["status"] == "host-pending" and not state["retired"], "pending is not success")
            state = fanout._load(path, root)
            ensure(fanout.finish(root, state, path, finish_args()), "resume finishes")
            ensure(state["status"] == "complete", "completion persisted")
            ensure(fanout.finish(root, state, path, finish_args()), "completed resume is read-only")
            ensure(observed == ["ci", "ci", "retire"], "no repeated dispatch or retirement")
            commit(root, "new inputs")
            refuses(lambda: fanout.finish(root, state, path, finish_args()), "inputs changed")


def _reading_base_reaches_ci() -> None:
    with fixture() as (root, lane, _):
        base = git(root, "rev-parse", "HEAD")
        commit(lane, "worker commit")
        state, path = init(root, lane, base)
        forwarded: list[str | None] = []

        def advance(checkout: Path, ci: fanout_ci.CIState, save: Callable[[], None]) -> bool:
            forwarded.append(ci.get("reading_base"))
            return True

        with (patch.object(fanout_ci, "repository", return_value="example/repo"),
              patch.object(fanout_ci, "advance", side_effect=advance),
              patch.object(fanout_retire, "retire", return_value={"status": "retired"})):
            ensure(fanout.finish(root, state, path, finish_args()), "the batch completes")
        ensure(forwarded == [base],
               "the batch's reading base reaches the CI record Guest CI's dispatch reads")
        ci = fanout._load(path, root)["ci"]
        ensure(ci is not None and ci.get("reading_base") == base,
               "the CI record keeps the reading base for resume")
    with fixture() as (root, lane, remote):
        # Nothing lands after the reading base, so Guest CI would refuse it as no proper
        # ancestor: finish refuses before publishing anything.
        state, path = init(root, lane, git(root, "rev-parse", "HEAD"))
        with (patch.object(fanout_ci, "repository", return_value="example/repo"),
              patch.object(fanout_ci, "advance") as handoff):
            refuses(lambda: fanout.finish(root, state, path, finish_args()),
                    "the settled revision is the reading base itself")
            handoff.assert_not_called()
        ensure(git(remote, "for-each-ref", "--format=%(refname)") == "",
               "a revision Guest CI would refuse is never published")
        ensure(state["ci"] is None, "no CI record exists for a refused revision")


def _retirement_resume() -> None:
    with fixture() as (root, lane, _):
        state, path = init(root, lane)
        state["status"] = "retiring"
        revision = git(root, "rev-parse", "HEAD")
        fanout._publish(root, state, revision)
        state["ci"] = fanout_ci.new_state("example/repo", "main",
                                           revision, True)
        # A prior retirement may already have removed the checkout before failing
        # branch deletion. The retirement module owns recovery from its receipt.
        git(root, "worktree", "remove", str(lane))
        with (patch.object(fanout_ci, "advance", return_value=True),
              patch.object(fanout_retire, "retire", return_value={"status": "retired"}) as retire):
            ensure(fanout.finish(root, state, path, finish_args()), "partial removal can resume")
            ensure(retire.call_count == 1, "retirement receipt handles missing checkout")


def _inputs_change_during_ci() -> None:
    with fixture() as (root, lane, _):
        state, path = init(root, lane)

        def changed(checkout: Path, ci: fanout_ci.CIState, save: Callable[[], None]) -> bool:
            (checkout / "README.md").write_text("concurrent edit\n", encoding="utf-8")
            return True

        with (patch.object(fanout_ci, "repository", return_value="example/repo"),
              patch.object(fanout_ci, "advance", side_effect=changed),
              patch.object(fanout_retire, "retire") as retire):
            refuses(lambda: fanout.finish(root, state, path, finish_args()), "uncommitted inputs")
            retire.assert_not_called()
            ensure(state["status"] != "complete", "changed inputs do not complete")


def _main_only() -> None:
    with fixture() as (root, lane, remote):
        refuses(lambda: init(lane, root), "on main")
        state, path = init(root, lane)
        revision = git(root, "rev-parse", "HEAD")
        git(root, "config", "push.followTags", "true")
        git(root, "tag", "-a", "private", "-m", "must remain local")
        ensure(fanout._publish(root, state, revision) == "main", "only main is a dispatch ref")
        ensure(git(remote, "for-each-ref", "--format=%(refname)") == "refs/heads/main",
               "user followTags configuration cannot publish tags")
        # A legacy completed journal must not bypass the main-only invariant.
        git(root, "switch", "-c", "work/old-integration")
        state["branch"] = "work/old-integration"
        state["status"] = "complete"
        with patch.object(fanout_ci, "advance") as advance:
            refuses(lambda: fanout.finish(root, state, path, finish_args()), "requires main")
            refuses(lambda: fanout._publish(root, state, revision), "requires main")
            advance.assert_not_called()


def _remote_changes_during_ci() -> None:
    with fixture() as (root, lane, remote):
        state, path = init(root, lane)

        def changed(checkout: Path, ci: fanout_ci.CIState, save: Callable[[], None]) -> bool:
            git(remote, "update-ref", "refs/heads/main", ci["revision"] + "^")
            return True

        # Give main a parent so the remote can move independently of local HEAD.
        commit(root, "settled input")
        with (patch.object(fanout_ci, "repository", return_value="example/repo"),
              patch.object(fanout_ci, "advance", side_effect=changed),
              patch.object(fanout_retire, "retire") as retire):
            refuses(lambda: fanout.finish(root, state, path, finish_args()), "remote main changed")
            retire.assert_not_called()
            ensure(state["status"] != "complete", "remote change does not complete")


def cases() -> list[Case]:
    return [Case("publish, pending host, resume and retirement order", _publish_wait_resume),
            Case("reading base reaches CI and needs a proper descendant",
                 _reading_base_reaches_ci),
            Case("partial retirement resumes without checkout", _retirement_resume),
            Case("concurrent inputs prevent retirement", _inputs_change_during_ci),
            Case("main-only completion and publication without tags", _main_only),
            Case("remote changes prevent retirement", _remote_changes_during_ci)]
