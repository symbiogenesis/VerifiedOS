# SPDX-License-Identifier: Apache-2.0
"""Fanout completes locally without publication, hosted actions or CI waits."""

import io
import subprocess
import time
import urllib.request
from collections.abc import Generator
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.fanout_fixture import commit, finish_args, fixture, git, init, refuses
from tests.harness import Case, ensure
from vos import ci_scope, fanout_ci, fanout_retire
from vos.cli import fanout, worktree

# Fixtures, patches and captured streams are private to each case.
INDEPENDENT_CASES = True


@contextmanager
def _local_only() -> Generator[None]:
    """Refuse remote Git, credentials, API construction and any polling delay."""
    original = worktree._git

    def local_git(root: Path, *args: str, allowed: tuple[int, ...] = (0,),
                  stdin: bytes | None = None) -> bytes:
        forbidden = {"push", "fetch", "pull", "ls-remote", "send-pack", "receive-pack", "credential"}
        ensure(not forbidden.intersection(args), f"completion must keep Git local: {args!r}")
        return original(root, *args, allowed=allowed, stdin=stdin)

    with (patch.object(worktree, "_git", side_effect=local_git),
          patch.object(fanout_ci, "repository", side_effect=AssertionError("CI repository lookup")),
          patch.object(fanout_ci.GitHub, "__init__", side_effect=AssertionError("GitHub client")),
          patch.object(urllib.request, "urlopen", side_effect=AssertionError("network request")),
          patch.object(time, "sleep", side_effect=AssertionError("CI wait"))):
        yield


def _legacy_ci(revision: str, *, passed: bool = False) -> fanout_ci.CIState:
    host: fanout_ci.RunState = {
        "workflow": fanout_ci.HOST, "revision": revision,
        "requested": "2026-11-02T00:00:00Z",
        "phase": "observed" if passed else "intent",
        "run_id": 123 if passed else None,
        "url": "https://github.com/example/repo/actions/runs/123" if passed else "",
        "status": "completed" if passed else "pending",
        "conclusion": "success" if passed else None, "request_id": None,
        "jobs": dict.fromkeys(fanout_ci.HOST_JOBS, "success") if passed else {},
    }
    return {"repository": "example/repo", "ref": "main", "revision": revision,
            "cold": True, "host": host, "guest": None}


def _local_completion_and_repeat() -> None:
    with fixture() as (root, lane, remote):
        (lane / "worker.txt").write_text("integrated locally\n", encoding="utf-8")
        git(lane, "add", "--", "worker.txt")
        worker_head = commit(lane, "worker contribution")
        state, path = init(root, lane)
        git(root, "config", "push.followTags", "true")
        git(root, "-c", "tag.gpgSign=false", "tag", "-a", "private", "-m", "local tag")
        output = lane / "out" / "evidence.txt"
        output.parent.mkdir()
        output.write_text("keep this evidence\n", encoding="utf-8")
        with (_local_only(), patch.object(fanout_retire, "_guest", return_value={}),
              patch.object(fanout, "_precompletion", wraps=fanout._precompletion) as preparation):
            ensure(fanout.finish(root, state, path, finish_args()), "local completion succeeds")
            ensure(state["status"] == "complete" and state["ci"] is None,
                   "local success creates no hosted evidence")
            revision = git(root, "rev-parse", "HEAD")
            ensure(state.get("revision") == revision, "journal binds the settled local revision")
            git(root, "merge-base", "--is-ancestor", worker_head, revision)
            ensure((root / "worker.txt").read_text(encoding="utf-8") == "integrated locally\n",
                   "worker deliverable reaches local main")
            ensure(not lane.exists() and not git(root, "branch", "--list", "work/worker"),
                   "eligible lane and its local branch retire")
            archived = list((path.parent / "retained").rglob("evidence.txt"))
            ensure(len(archived) == 1 and archived[0].read_text(encoding="utf-8") == "keep this evidence\n",
                   "ignored worker evidence survives retirement")
            saved = path.read_bytes()
            state = fanout._load(path, root)
            ensure(fanout.finish(root, state, path, finish_args()), "completed batch resumes locally")
            ensure(path.read_bytes() == saved and preparation.call_count == 1,
                   "completed resume repeats neither preparation nor journal writes")
            commit(root, "new inputs")
            refuses(lambda: fanout.finish(root, state, path, finish_args()), "inputs changed")
        ensure(git(remote, "for-each-ref", "--format=%(refname)") == "",
               "main, worker branches and tags were never published")


def _offline_completion() -> None:
    with fixture() as (root, lane, remote):
        git(root, "remote", "remove", "origin")
        with (_local_only(), patch.object(fanout_retire, "_guest", return_value={})):
            state, path = init(root, lane)
            ensure(fanout.finish(root, state, path, finish_args()),
                   "initialization and completion require no configured or reachable remote")
        selected = state.get("selection")
        ensure(selected is not None and selected["base"] is None and selected["host_full"]
               and selected["guest_lanes"] == ["model", "rtl", "proofs"],
               "missing local comparison history recommends full hosted validation")
        ensure(git(remote, "for-each-ref", "--format=%(refname)") == "",
               "offline completion leaves remote refs untouched")


def _legacy_pending_resume() -> None:
    for status in ("published", "host-pending", "retiring"):
        with fixture() as (root, lane, remote):
            state, path = init(root, lane)
            revision = git(root, "rev-parse", "HEAD")
            historical = _legacy_ci(revision)
            state["ci"] = historical
            state["status"] = status
            fanout._save(path, state)
            with (_local_only(), patch.object(fanout_retire, "_guest", return_value={})):
                resumed = fanout._load(path, root)
                ensure(fanout.finish(root, resumed, path, finish_args()),
                       f"legacy {status} resumes without finishing its dispatch intent")
            ensure(resumed["ci"] == historical and resumed.get("revision") == revision,
                   "legacy CI evidence remains historical beside local completion")
            ensure(resumed["status"] == "complete" and not lane.exists(),
                   "a pending hosted verdict never blocks eligible retirement")
            ensure(git(remote, "for-each-ref", "--format=%(refname)") == "",
                   "legacy resume never publishes")


def _legacy_completed_resume() -> None:
    with fixture() as (root, lane, remote):
        state, path = init(root, lane)
        revision = git(root, "rev-parse", "HEAD")
        state["ci"] = _legacy_ci(revision, passed=True)
        state["status"] = "complete"
        fanout._save(path, state)
        saved = path.read_bytes()
        with (_local_only(), patch.object(fanout, "_prepare") as prepare,
              patch.object(fanout_retire, "retire") as retire):
            resumed = fanout._load(path, root)
            ensure(fanout.finish(root, resumed, path, finish_args()),
                   "a legacy completed journal needs no remote evidence lookup")
            prepare.assert_not_called()
            retire.assert_not_called()
            ensure(path.read_bytes() == saved and lane.exists(), "completed resume is read-only")
            commit(root, "new local inputs")
            refuses(lambda: fanout.finish(root, resumed, path, finish_args()), "inputs changed")
        ensure(git(remote, "for-each-ref", "--format=%(refname)") == "",
               "completed legacy resume leaves every remote ref untouched")


def _historical_evidence_keeps_its_revision() -> None:
    with fixture() as (root, lane, _):
        state, path = init(root, lane)
        old_revision = git(root, "rev-parse", "HEAD")
        historical = _legacy_ci(old_revision)
        old_selection = ci_scope.select_changes(root, None, old_revision, force_guest=True)
        historical["selection"] = old_selection
        state["ci"] = historical
        state["selection"] = old_selection
        state["status"] = "host-pending"
        (root / "README.md").write_text("new local revision\n", encoding="utf-8")
        git(root, "add", "--", "README.md")
        revision = commit(root, "changed settled input")
        with (_local_only(), patch.object(fanout_retire, "_guest", return_value={})):
            ensure(fanout.finish(root, state, path, finish_args()), "changed pending inputs finish locally")
        ensure(state.get("revision") == revision and state["ci"] == historical
               and historical["revision"] == old_revision,
               "new local completion never relabels old hosted evidence")
        ensure(fanout._load(path, root) == state, "independent historical evidence round-trips")


def _retirement_resume() -> None:
    with fixture() as (root, lane, _):
        state, path = init(root, lane)
        original = fanout_retire._git

        def interrupted(checkout: Path, *args: str,
                        allowed: tuple[int, ...] = (0,)) -> bytes:
            if args[:2] == ("branch", "-d"):
                raise fanout_retire.RetirementError("interrupted after checkout removal")
            return original(checkout, *args, allowed=allowed)

        with (_local_only(), patch.object(fanout_retire, "_guest", return_value={}),
              patch.object(fanout, "_precompletion", wraps=fanout._precompletion) as preparation):
            with patch.object(fanout_retire, "_git", side_effect=interrupted):
                refuses(lambda: fanout.finish(root, state, path, finish_args()), "interrupted")
            ensure(state["status"] == "retiring" and not lane.exists()
                   and bool(git(root, "branch", "--list", "work/worker")),
                   "durable retirement interrupted between checkout and branch removal")
            resumed = fanout._load(path, root)
            ensure(fanout.finish(root, resumed, path, finish_args()), "missing checkout resumes from receipt")
            ensure(resumed["status"] == "complete"
                   and not git(root, "branch", "--list", "work/worker"), "resumed retirement finishes")
            ensure(preparation.call_count == 1, "unchanged partial retirement reuses local preparation")


def _main_only() -> None:
    with fixture() as (root, lane, _):
        refuses(lambda: init(lane, root), "on main")
        state, path = init(root, lane)
        git(root, "switch", "-c", "work/old-integration")
        state["branch"] = "work/old-integration"
        state["status"] = "complete"
        with _local_only(), patch.object(fanout_retire, "retire") as retire:
            refuses(lambda: fanout.finish(root, state, path, finish_args()), "requires main")
            retire.assert_not_called()


def _preparation_findings() -> None:
    for selector in ("typecheck", "test_lanes", "test_retained_evidence"):
        with fixture() as (root, lane, remote):
            script = root / "tools/run.py"
            script.write_text("import sys\n"
                              f"raise SystemExit(1 if sys.argv[-1] == {selector!r} else 0)\n",
                              encoding="utf-8", newline="")
            git(root, "add", "--", "tools/run.py")
            commit(root, "preparation finding")
            state, path = init(root, lane)
            with _local_only(), patch.object(fanout_retire, "retire") as retire:
                refuses(lambda state=state, path=path: fanout.finish(root, state, path, finish_args()),
                        "exited 1")
                retire.assert_not_called()
            ensure(lane.exists() and state["status"] != "complete" and state["ci"] is None,
                   f"{selector} finding prevents retirement without hosted evidence")
            ensure(git(remote, "for-each-ref", "--format=%(refname)") == "",
                   "preparation failure cannot publish")


def _preparation_timeouts() -> None:
    for selector in ("typecheck", "test_lanes", "test_retained_evidence"):
        with fixture() as (root, lane, _):
            state, path = init(root, lane)

            def launch(argv: list[str], *, cwd: Path, check: bool,
                       timeout: int, selector: str = selector) -> subprocess.CompletedProcess[bytes]:
                if argv[-1] == selector:
                    ensure(cwd == root and timeout == 300,
                           "preparation uses the settled checkout and bounded local timeout")
                    raise subprocess.TimeoutExpired(argv, timeout)
                return subprocess.run(argv, cwd=cwd, check=check, timeout=timeout)

            with (_local_only(), patch.object(fanout, "subprocess", SimpleNamespace(
                    run=launch, SubprocessError=subprocess.SubprocessError)),
                  patch.object(fanout_retire, "retire") as retire):
                try:
                    fanout.finish(root, state, path, finish_args())
                except subprocess.TimeoutExpired:
                    pass
                else:
                    raise AssertionError("preparation timeout must stop local completion")
                retire.assert_not_called()
            ensure(lane.exists() and state["status"] != "complete" and state["ci"] is None,
                   "preparation timeout preserves the lane and creates no hosted evidence")


def _preparation_changes_inputs() -> None:
    for committed in (False, True):
        with fixture() as (root, lane, _):
            state, path = init(root, lane)

            def changed(checkout: Path, committed: bool = committed) -> None:
                (checkout / "README.md").write_text("concurrent edit\n", encoding="utf-8")
                if committed:
                    git(checkout, "add", "--", "README.md")
                    commit(checkout, "concurrent commit")

            with (_local_only(), patch.object(fanout, "_precompletion", side_effect=changed),
                  patch.object(fanout_retire, "retire") as retire):
                refuses(lambda state=state, path=path: fanout.finish(root, state, path, finish_args()),
                        "revision changed" if committed else "uncommitted inputs")
                retire.assert_not_called()
            ensure(lane.exists() and state["status"] != "complete", "changed inputs prevent retirement")


def _local_tracking_selection() -> None:
    with fixture() as (root, lane, remote):
        base = git(root, "rev-parse", "HEAD")
        # A local tracking ref can exist even when the named remote is unreachable.
        git(root, "update-ref", "refs/remotes/origin/main", base)
        git(root, "remote", "set-url", "origin", "https://unreachable.invalid/repository")
        (root / "README.md").write_text("prose changed before init\n", encoding="utf-8")
        git(root, "add", "--", "README.md")
        revision = commit(root, "document change")
        state, path = init(root, lane)
        state["cold"] = False
        with (_local_only(), patch.object(fanout_retire, "_guest", return_value={}),
              patch.object(fanout, "_precompletion") as preparation):
            ensure(fanout.finish(root, state, path, finish_args()), "local tracking comparison finishes")
            preparation.assert_not_called()
            selected = state.get("selection")
            ensure(selected is not None and selected["base"] == base
                   and selected["revision"] == revision and selected["paths"] == ["README.md"]
                   and selected["guest_lanes"] == [] and not selected["host_full"],
                   "scope includes work before init and recommends no unaffected guest lanes")
            git(root, "update-ref", "refs/remotes/origin/main", revision)
            ensure(fanout._freeze_selection(root, state, revision, path) == selected,
                   "unchanged resume retains its recorded comparison after tracking refs advance")
        ensure(git(remote, "for-each-ref", "--format=%(refname)") == "",
               "tracking recommendation never contacts the remote")


def _scope_overrides_and_legacy() -> None:
    for policy in ("cold", "reading_base", "full_ci", "legacy"):
        with fixture() as (root, lane, _):
            base = git(root, "rev-parse", "HEAD")
            git(root, "update-ref", "refs/remotes/origin/main", base)
            (root / "README.md").write_text("prose for acceptance\n", encoding="utf-8")
            git(root, "add", "--", "README.md")
            revision = commit(root, "settled documentation")
            state, path = init(root, lane, base if policy == "reading_base" else None)
            state["cold"] = policy == "cold"
            state["full_ci"] = policy == "full_ci"
            if policy == "legacy":
                del state["full_ci"]
            with _local_only():
                selected = fanout._freeze_selection(root, state, revision, path)
            full = policy in {"full_ci", "legacy"}
            ensure(selected["base"] == base and selected["paths"] == ["README.md"]
                   and selected["host_full"] is full and selected["model_hooks"] is full
                   and selected["guest_lanes"] == ["model", "rtl", "proofs"],
                   "acceptance expansions remain recommendations with conservative legacy defaults")
            ensure(fanout._load(path, root) == state, "advisory scope policy round-trips")


def _reading_base_handoff() -> None:
    with fixture() as (root, lane, _):
        base = git(root, "rev-parse", "HEAD")
        commit(lane, "worker commit")
        state, path = init(root, lane, base)
        with _local_only(), patch.object(fanout_retire, "_guest", return_value={}):
            ensure(fanout.finish(root, state, path, finish_args()), "proof reading recommendation finishes")
        ensure(state.get("reading_base") == base and state["ci"] is None,
               "user receives reading base without a dispatch or fabricated CI record")
        ensure(fanout._load(path, root) == state, "reading recommendation survives resume")
    with fixture() as (root, lane, _):
        state, path = init(root, lane, git(root, "rev-parse", "HEAD"))
        with _local_only(), patch.object(fanout_retire, "retire") as retire:
            refuses(lambda: fanout.finish(root, state, path, finish_args()),
                    "the settled revision is the reading base itself")
            retire.assert_not_called()
        ensure(state["ci"] is None and lane.exists(), "invalid reading recommendation never retires")


def _old_wait_option_refused() -> None:
    stream = io.StringIO()
    with redirect_stderr(stream):
        try:
            fanout.main(["finish", "example", "--wait-host", "1"])
        except SystemExit as err:
            ensure(err.code == 2, "removed wait flag is a CLI usage error")
        else:
            raise AssertionError("fanout must not retain a Host CI wait option")
    ensure("--wait-host" in stream.getvalue(), "usage error identifies the removed flag")


def _status_and_cli_handoff() -> None:
    with fixture() as (root, lane, _):
        state, path = init(root, lane)
        stream = io.StringIO()
        with (_local_only(), patch.object(fanout, "find_root", return_value=root),
              patch.object(fanout_retire, "_guest", return_value={}), redirect_stdout(stream)):
            ensure(fanout.main(["finish", state["batch"]]) == 0, "CLI returns local success")
            saved = path.read_bytes()
            ensure(fanout.main(["status", state["batch"]]) == 0, "status reads only its local journal")
        ensure(path.read_bytes() == saved and not lane.exists(), "status performs no mutation")
        output = stream.getvalue().lower()
        ensure("user" in output and "host ci" in output and "guest ci" in output,
               "completion output assigns publication and both CI workflows to the user")


def cases() -> list[Case]:
    return [Case("local integration, retention, retirement and read-only repeat", _local_completion_and_repeat),
            Case("offline initialization and completion", _offline_completion),
            Case("legacy pending hosted states finish locally", _legacy_pending_resume),
            Case("legacy completed journal is read-only", _legacy_completed_resume),
            Case("historical CI evidence keeps its own revision", _historical_evidence_keeps_its_revision),
            Case("partial retirement resumes from durable receipt", _retirement_resume),
            Case("local completion requires main", _main_only),
            Case("each local preparation finding prevents retirement", _preparation_findings),
            Case("each local preparation timeout prevents retirement", _preparation_timeouts),
            Case("concurrent input changes prevent retirement", _preparation_changes_inputs),
            Case("local tracking comparison freezes advisory scope", _local_tracking_selection),
            Case("advisory full cold reading and legacy policies", _scope_overrides_and_legacy),
            Case("proof reading is a valid local handoff", _reading_base_handoff),
            Case("old host wait flag is refused", _old_wait_option_refused),
            Case("CLI handoff and status stay local", _status_and_cli_handoff)]
