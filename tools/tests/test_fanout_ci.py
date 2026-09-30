# SPDX-License-Identifier: Apache-2.0
"""Hosted fan-out handoffs bind exact revisions and never poll guest verdicts."""

import copy
import json
import os
import re
import subprocess
import sys
import textwrap
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import fanout_ci as ci

REVISION = "a" * 40
SUBJECT = "Settle the fixture batch"
HOST_TITLE = f"host-gates:{SUBJECT}"
GUEST_TITLE = f"guest-gates:{SUBJECT}"
# The fixture's dispatch intent reaches disk at NOW; GitHub creates its run LATER.
NOW = "2026-09-27T16:00:00Z"
LATER = "2026-09-27T16:00:05Z"
# A dispatch identity from when run titles carried one, as `fanout:<id>:`.
OLD_ID = "5c6c433b07cb4212b594b83fffccdc48"
REPO = "example/verifiedos"
ROOT = Path(__file__).resolve().parents[2]


def _state() -> ci.CIState:
    return ci.new_state(REPO, "main", REVISION, True)


def _run(number: int = 10, **changes: object) -> dict[str, object]:
    return {"id": number, "head_sha": REVISION, "head_branch": "main",
            "event": "push", "status": "completed", "created_at": LATER,
            "path": ".github/workflows/host-gates.yml", "conclusion": "success", **changes}


class FakeGitHub:
    def __init__(self, state: ci.CIState) -> None:
        self.state = state
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []
        self.host_runs = [_run()]
        self.host = _run()
        self.jobs: list[dict[str, object]] = [
            {"name": name, "status": "completed", "conclusion": "success"}
            for name in sorted(ci.HOST_JOBS)]
        self.guest_runs: list[dict[str, object]] = []
        self.ref_sha = REVISION
        self.dispatch_sha = REVISION
        self.comparison: dict[str, object] = {"status": "ahead", "merge_base_commit": {"sha": REVISION}}
        self.dispatch_error: ci.APIError | None = None
        self.saved: list[ci.CIState] = []
        self.slept: list[float] = []
        # Host runs GitHub lists only after the first pause, as a push run it has
        # accepted but not yet registered.
        self.late_host_runs: list[dict[str, object]] | None = None

    def save(self) -> None:
        self.saved.append(copy.deepcopy(self.state))

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        if self.late_host_runs is not None:
            self.host_runs, self.late_host_runs = self.late_host_runs, None

    def request(self, method: str, path: str,
                payload: dict[str, object] | None = None) -> dict[str, object]:
        self.calls.append((method, path, payload))
        if path == "git/ref/heads/main":
            return {"object": {"type": "commit", "sha": self.ref_sha}}
        if path.startswith("compare/"):
            return self.comparison
        if method == "POST":
            lane = "guest" if ci.GUEST in path else "host"
            ensure(bool(self.saved), "dispatch must first publish a journal")
            saved_run = self.saved[-1][lane]
            ensure(saved_run is not None and saved_run["phase"] == "intent",
                   "dispatch intent must be durable before the network call")
            if self.dispatch_error:
                raise self.dispatch_error
            if lane == "host" and saved_run is not None:
                self.host = _run(event="workflow_dispatch", head_sha=self.dispatch_sha,
                                 display_title=HOST_TITLE)
            number = 20 if lane == "guest" else 10
            return {"workflow_run_id": number,
                    "html_url": f"https://github.com/{REPO}/actions/runs/{number}",
                    "_request_id": "receipt-123"}
        if f"workflows/{ci.HOST}/runs?" in path:
            return {"workflow_runs": self.host_runs}
        if f"workflows/{ci.GUEST}/runs?" in path:
            return {"workflow_runs": self.guest_runs}
        if path == "actions/runs/10":
            return self.host
        if path.startswith("actions/runs/10/jobs?"):
            return {"jobs": self.jobs}
        raise AssertionError(f"unexpected GitHub request: {method} {path}")

    def advance(self) -> bool:
        with (patch.object(ci, "_token", return_value="fixture-credential"),
              patch.object(ci, "_subject", return_value=SUBJECT),
              patch.object(ci, "_now", return_value=NOW),
              patch.object(ci.GitHub, "request", side_effect=self.request),
              patch.object(ci.time, "sleep", side_effect=self.sleep)):
            return ci.advance(ROOT, self.state, self.save)

    def host_lookups(self) -> int:
        return sum(f"workflows/{ci.HOST}/runs?" in path for _, path, _ in self.calls)

    def posts(self) -> list[tuple[str, str, dict[str, object] | None]]:
        return [call for call in self.calls if call[0] == "POST"]


def _refuses(action: Callable[[], object], message: str) -> None:
    try:
        action()
    except ci.CIError:
        return
    raise AssertionError(message)


def _successful_handoff() -> None:
    state = _state()
    fake = FakeGitHub(state)
    ensure(fake.advance(), "passing host must dispatch guest")
    host, guest = state["host"], state["guest"]
    ensure(host is not None and host["jobs"] == dict.fromkeys(ci.HOST_JOBS, "success"),
           "both successful host aggregates must be retained")
    ensure(guest is not None and guest["status"] == "pending" and guest["run_id"] == 20,
           "guest dispatch is pending evidence with the returned run identifier")
    ensure(guest is not None and guest["request_id"] == "receipt-123", "retain dispatch receipt")
    posts = fake.posts()
    ensure(len(posts) == 1, "dispatch guest exactly once")
    ensure(posts[0][2] == {"ref": state["ref"], "inputs": {
        "revision": REVISION, "title": SUBJECT, "cold": True}},
        "guest dispatch must use main, exact revision, explicit cold policy and subject title")
    ensure(guest is not None and guest.get("requested") == NOW and "token" not in guest,
           "the record keeps when its intent reached disk, for recovery by title")
    ensure(not any(ci.GUEST in path and method == "GET" for method, path, _ in fake.calls),
           "normal guest dispatch must not query guest runs")
    fake.calls.clear()
    ensure(fake.advance(), "completed handoff should be idempotent")
    ensure(not fake.calls, "completed handoff must not request a guest verdict")


def _host_pending() -> None:
    state = _state()
    fake = FakeGitHub(state)
    fake.host.update(status="in_progress", conclusion=None)
    ensure(not fake.advance(), "pending host is not a passing verdict")
    ensure(not fake.posts() and state["guest"] is None, "guest must wait for completed host")


def _host_failure() -> None:
    for result in ("failure", "skipped", "cancelled", None):
        fake = FakeGitHub(_state())
        fake.host["conclusion"] = result
        _refuses(fake.advance, f"host {result} cannot pass")
        ensure(not fake.posts(), "failed host must not dispatch guest")


def _host_aggregate_evidence() -> None:
    for change in ("missing", "skipped", "pending", "duplicate"):
        fake = FakeGitHub(_state())
        if change == "missing":
            fake.jobs.pop()
        elif change == "duplicate":
            fake.jobs.append(fake.jobs[0])
        elif change == "pending":
            fake.jobs[0]["status"] = "in_progress"
        else:
            fake.jobs[0]["conclusion"] = "skipped"
        _refuses(fake.advance, f"{change} host aggregate cannot pass")
        ensure(not fake.posts(), "incomplete aggregate evidence must stop guest")


def _host_revision_binding() -> None:
    for key, value in (("head_sha", "b" * 40), ("path", ".github/workflows/another.yml"),
                       ("head_branch", "work/stranded")):
        fake = FakeGitHub(_state())
        fake.host[key] = value
        _refuses(fake.advance, "host must test the exact revision with the intended workflow")
        ensure(not fake.posts(), "wrong revision or workflow cannot dispatch guest")


def _host_dispatch() -> None:
    fake = FakeGitHub(_state())
    fake.host_runs = [_run(head_sha="b" * 40), _run(event="pull_request"),
                      _run(head_branch="work/stranded"), _run(event="workflow_dispatch")]
    ensure(not fake.advance(), "manual host dispatch is initially pending")
    ensure(fake.slept == list(ci.PUSH_RUN_WAITS)
           and fake.host_lookups() == len(ci.PUSH_RUN_WAITS) + 1,
           "dispatch only after the bounded wait for GitHub to list a push run")
    posts = fake.posts()
    ensure(len(posts) == 1 and ci.HOST in posts[0][1],
           "start Host CI when no exact suitable run exists")
    ensure(posts[0][2] == {"ref": "main", "inputs": {"revision": REVISION, "title": SUBJECT}},
           "Host CI dispatch must pin checkout to the requested main revision")
    ensure(fake.state["guest"] is None, "host dispatch supplies no verdict")
    ensure(fake.advance(), "the next advance can accept the completed host run")


def _late_push_run_adopted() -> None:
    fake = FakeGitHub(_state())
    fake.host_runs = []
    fake.late_host_runs = [_run()]
    ensure(fake.advance(), "a push run listed during the wait establishes host evidence")
    ensure(not any(ci.HOST in path for _, path, _ in fake.posts()),
           "a push run GitHub had not yet listed must not be duplicated by a dispatch")
    ensure(fake.slept == list(ci.PUSH_RUN_WAITS[:1]), "stop waiting once the push run is listed")
    host = fake.state["host"]
    ensure(host is not None and host["run_id"] == 10 and host["jobs"]
           == dict.fromkeys(ci.HOST_JOBS, "success"), "adopt the push run's host evidence")
    fake = FakeGitHub(_state())
    ensure(fake.advance() and not fake.slept, "an already listed push run needs no wait")


def _main_ancestry() -> None:
    fake = FakeGitHub(_state())
    fake.ref_sha = "b" * 40
    ensure(fake.advance(), "an ancestor of advanced main remains a published revision")
    ensure(any(path == f"compare/{REVISION}...{'b' * 40}" for _, path, _ in fake.calls),
           "remote main ancestry must be verified with immutable comparison endpoints")
    for result in ({"status": "diverged", "merge_base_commit": {"sha": REVISION}},
                   {"status": "ahead", "merge_base_commit": {"sha": "c" * 40}},
                   {"status": "behind", "merge_base_commit": {"sha": REVISION}}):
        fake = FakeGitHub(_state())
        fake.ref_sha = "b" * 40
        fake.comparison = dict(result)
        _refuses(fake.advance, "revision outside remote main must stop the handoff")
        ensure(not fake.posts(), "unpublished revision must stop all dispatch")


def _dispatch_revision_survives_main_advance() -> None:
    fake = FakeGitHub(_state())
    fake.host_runs = []
    fake.dispatch_sha = "b" * 40
    ensure(not fake.advance(), "host dispatch starts pending")
    ensure(fake.advance(), "pinned checkout remains evidence when main advances during dispatch")
    ensure(fake.state["host"] is not None and fake.state["host"]["revision"] == REVISION,
           "evidence must name the checked out revision, not the workflow's newer main tip")
    for title in (GUEST_TITLE, "host-gates:Another subject", "host-gates:" + REVISION,
                  HOST_TITLE + " ", f"fanout:{'0' * 32}:{SUBJECT}", None):
        fake = FakeGitHub(_state())
        fake.host_runs = []
        ensure(not fake.advance(), "fixture host dispatch starts pending")
        fake.host["display_title"] = title
        _refuses(fake.advance, "a dispatch needs the title its request set with the revision")
        ensure(len(fake.posts()) == 1, "wrong dispatch cannot start guest")


def _guest_interrupt_recovery() -> None:
    fake = FakeGitHub(_state())
    fake.dispatch_error = ci.APIError(None)
    _refuses(fake.advance, "transport failure must report ambiguity")
    guest = fake.state["guest"]
    ensure(guest is not None and guest["phase"] == "intent", "preserve ambiguous intent")
    ensure(fake.saved[-1]["guest"] == guest, "intent is recoverable from the saved journal")
    fake.dispatch_error = None
    # Stamped a clock allowance before the intent, as by a GitHub clock running behind.
    fake.guest_runs = [_run(20, event="workflow_dispatch", head_sha="b" * 40,
                            display_title=GUEST_TITLE, created_at="2026-09-27T15:59:00Z",
                            status="completed", conclusion="failure",
                            path=".github/workflows/guest-gates.yml")]
    ensure(fake.advance(), "a unique dispatched identity must be adopted")
    ensure(len(fake.posts()) == 1, "recovery must never duplicate an ambiguous dispatch")
    ensure(guest is not None and guest["conclusion"] is None and guest["status"] == "pending",
           "identity recovery must not collect or claim a guest verdict")
    ensure(sum(ci.GUEST in path and method == "GET" for method, path, _ in fake.calls) == 1,
           "ambiguous dispatch permits a single identity lookup")


def _ambiguous_recovery_never_reposts() -> None:
    for count in (0, 2):
        fake = FakeGitHub(_state())
        fake.dispatch_error = ci.APIError(500)
        _refuses(fake.advance, "server error may have accepted the dispatch")
        fake.guest_runs = [_run(number, event="workflow_dispatch", display_title=GUEST_TITLE)
                           for number in range(20, 20 + count)]
        fake.dispatch_error = None
        _refuses(fake.advance, "ambiguous identity must not authorize a second dispatch")
        ensure(len(fake.posts()) == 1, "only the original request may have started guest")


def _recovery_requires_main_and_own_dispatch() -> None:
    for change in ("branch", "title", "earlier", "workflow"):
        fake = FakeGitHub(_state())
        fake.dispatch_error = ci.APIError(None)
        _refuses(fake.advance, "interrupted dispatch must retain its intent")
        ensure(fake.state["guest"] is not None, "interrupted guest intent must exist")
        candidate = _run(20, event="workflow_dispatch", display_title=GUEST_TITLE,
                         path=".github/workflows/guest-gates.yml")
        if change == "branch":
            candidate["head_branch"] = "work/stranded"
        elif change == "title":
            candidate["display_title"] = "guest-gates:Another subject"
        elif change == "earlier":
            # An older dispatch of the same commit, beyond the local clock allowance.
            candidate["created_at"] = "2026-09-27T15:58:59Z"
        else:
            candidate["path"] = ".github/workflows/host-gates.yml"
        fake.guest_runs = [candidate]
        fake.dispatch_error = None
        _refuses(fake.advance, "recovery must identify main and this record's own dispatch")
        ensure(len(fake.posts()) == 1, "identity mismatch must not repeat the guest dispatch")


def _rejected_dispatch_can_retry() -> None:
    fake = FakeGitHub(_state())
    fake.dispatch_error = ci.APIError(403)
    _refuses(fake.advance, "a rejected dispatch must fail the handoff")
    guest = fake.state["guest"]
    ensure(guest is not None and guest["phase"] == "rejected", "record definite rejection")
    fake.dispatch_error = None
    ensure(fake.advance(), "a rejected dispatch can safely retry after authorization repair")
    ensure(len(fake.posts()) == 2, "a rejection, unlike ambiguity, permits retry")


def _host_interrupt_recovery() -> None:
    fake = FakeGitHub(_state())
    fake.host_runs = []
    fake.dispatch_error = ci.APIError(None)
    _refuses(fake.advance, "host transport error must preserve its intent")
    fake.host_runs = [_run(event="workflow_dispatch", head_sha="b" * 40,
                          display_title=HOST_TITLE)]
    fake.host = fake.host_runs[0]
    fake.dispatch_error = None
    ensure(fake.advance(), "recovered host may establish evidence and dispatch guest")
    ensure(sum(ci.HOST in path for _, path, _ in fake.posts()) == 1,
           "interrupted host dispatch must not duplicate")


def _token_journal_recovery() -> None:
    for title, adopted in ((f"fanout:{OLD_ID}:{REVISION}", True),
                           (f"fanout:{OLD_ID}:{SUBJECT}", True), (HOST_TITLE, False)):
        fake = FakeGitHub(_state())
        fake.host_runs = []
        fake.dispatch_error = ci.APIError(None)
        _refuses(fake.advance, "host transport error must preserve its intent")
        host = fake.state["host"]
        if host is None:
            raise AssertionError("interrupted host intent must exist")
        # A journal from when titles carried a token has the token and no request time.
        del host["requested"]
        host["token"] = OLD_ID
        fake.host_runs = [_run(event="workflow_dispatch", display_title=title,
                               created_at="2026-09-20T00:00:00Z")]
        fake.host = fake.host_runs[0]
        fake.dispatch_error = None
        if adopted:
            ensure(fake.advance(), "a token-titled dispatch recovers by its token")
        else:
            _refuses(fake.advance, "without a request time, a title alone cannot identify it")
        ensure(sum(ci.HOST in path for _, path, _ in fake.posts()) == 1,
               "recovering a token journal never repeats its dispatch")


def _remote_validation() -> None:
    for url in ("https://github.com/example/verifiedos.git", "git@github.com:example/verifiedos.git",
                "ssh://git@github.com/example/verifiedos"):
        result = subprocess.CompletedProcess([], 0, url + "\n", "")
        with patch.object(subprocess, "run", return_value=result):
            ensure(ci.repository(ROOT, "origin") == REPO, "parse supported GitHub remote")
    for url in ("https://github.com.evil/example/verifiedos", "https://token@github.com/a/b",
                "https://github.com/a/b/../../bad", "file:///tmp/example"):
        result = subprocess.CompletedProcess([], 0, url + "\n", "")
        with patch.object(subprocess, "run", return_value=result):
            _refuses(lambda: ci.repository(ROOT, "origin"), "untrusted remote must be refused")


def _state_validation() -> None:
    for key, value in (("revision", "a" * 7), ("cold", "true"),
                       ("ref", "work/stranded"), ("ref", f"fanout/batch/{REVISION}"),
                       ("repository", "github.com/example/repo")):
        state: dict[str, object] = dict(_state())
        state[key] = value
        _refuses(lambda state=state: ci.validate_state(state), f"invalid {key} must be refused")
    fake = FakeGitHub(_state())
    ensure(fake.advance(), "fixture must complete its hosted handoff")
    for requested in ("yesterday", "2026-09-27T16:00:00", 1759000000):
        timed = copy.deepcopy(fake.state)
        guest: dict[str, object] = dict(timed["guest"] or {})
        guest["requested"] = requested
        _refuses(lambda guest=guest, timed=timed: ci.validate_state({**timed, "guest": guest}),
                 f"request time {requested!r} must be a zoned timestamp")
    tokened = copy.deepcopy(fake.state)
    guest = dict(tokened["guest"] or {})
    del guest["requested"]
    guest["token"] = OLD_ID
    ci.validate_state({**tokened, "guest": guest})
    legacy = copy.deepcopy(fake.state)
    legacy["ref"] = f"fanout/batch/{REVISION}"
    _refuses(lambda: ci.advance(ROOT, legacy, lambda: None),
             "even completed legacy tag handoffs must be rejected")
    fake.state["host"] = None
    _refuses(fake.advance, "guest state without passing host evidence must be refused")


def _transport_contract() -> None:
    with (patch.dict(os.environ, {"GH_TOKEN": "fixture-credential"}, clear=True),
          patch.object(urllib.request, "build_opener") as build):
        response = build.return_value.open.return_value.__enter__.return_value
        response.read.return_value = json.dumps({"workflow_run_id": 42}).encode()
        response.headers.get.return_value = "request-receipt"
        client = ci.GitHub(ROOT, REPO)
        result = client.request("POST", "actions/workflows/guest-gates.yml/dispatches", {"ref": "main"})
        request = build.return_value.open.call_args.args[0]
        ensure(request.full_url == f"https://api.github.com/repos/{REPO}/actions/workflows/guest-gates.yml/dispatches",
               "authenticated requests must stay on the fixed GitHub HTTPS origin")
        ensure(request.get_header("X-github-api-version") == ci.API_VERSION,
               "dispatch response contract must use its API version")
        ensure(result.get("_request_id") == "request-receipt", "retain the API dispatch receipt")
        build.return_value.open.side_effect = urllib.error.URLError("fixture-credential")
        try:
            client.request("GET", "actions/runs/42")
        except ci.APIError as error:
            ensure("fixture-credential" not in str(error), "transport diagnostics must omit secrets")
        else:
            raise AssertionError("failed transport must not establish a verdict")


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          text=True, check=True, timeout=30)
    return done.stdout.strip()


def _fixture_identity(root: Path) -> None:
    _git(root, "config", "user.name", "Workflow test")
    _git(root, "config", "user.email", "workflow@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")


def _dispatch_subject() -> None:
    long = "Accelerate scoped document count checks with candidate and offset indexes"
    with sandbox_tree({"README.md": "subject fixture\n"}) as root:
        _fixture_identity(root)
        revisions: dict[str, str] = {}
        for subject in ("Short subject", "a" * ci.SUBJECT_LIMIT, long):
            _git(root, "commit", "--allow-empty", "-qm", subject, "-m", "Body text stays out.")
            revisions[subject] = _git(root, "rev-parse", "HEAD")
        ensure(ci._subject(root, revisions["Short subject"]) == "Short subject",
               "a short subject is the whole title text, without the body")
        ensure(ci._subject(root, revisions["a" * ci.SUBJECT_LIMIT]) == "a" * ci.SUBJECT_LIMIT,
               "a subject at the limit is not shortened")
        ensure(ci._subject(root, revisions[long])
               == "Accelerate scoped document count checks with candidate and offset ind…",
               "a long subject is shortened as GitHub shortens a push run's title")
        _refuses(lambda: ci._subject(root, "b" * 40), "a missing revision has no subject")


def _workflow_titles() -> None:
    record = ci._blank(ci.GUEST, REVISION)
    ensure(ci._title(record, "") == f"guest-gates:{REVISION}",
           "an empty subject leaves the revision, as the workflow's title fallback does")
    for workflow in (ci.HOST, ci.GUEST):
        contents = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
        ensure(f"\nname: {workflow.removesuffix('.yml')}\n" in contents,
               f"{workflow} is named for its file, as fanout's expected title assumes")
        ensure("format('{0}:{1}', github.workflow, inputs.title || inputs.revision || github.sha)"
               in contents and "fanout_token" not in contents,
               f"{workflow} titles a dispatch with its name and the title input, and no token")


def _workflow_host_job_names() -> None:
    # The aggregate jobs' names are the evidence _host_status accepts: a renamed job
    # or platform leaves fanout refusing every Host CI run, however green.
    contents = (ROOT / ".github/workflows" / ci.HOST).read_text(encoding="utf-8")
    shards, aggregate = contents.split("\n  host-gates-shard:\n", 1)[1].split("\n  host-gates:\n", 1)
    platform_list = re.compile(r"(?m)^        platform: \[([^\]\n]*)\]$")
    named = platform_list.search(aggregate)
    ensure(aggregate.startswith("    name: host-gates (${{ matrix.platform }})\n")
           and named is not None,
           f"{ci.HOST}'s aggregate job is named for its platform matrix")
    platforms = [platform.strip() for platform in named[1].split(",")] if named else []
    ensure({f"host-gates ({platform})" for platform in platforms} == ci.HOST_JOBS,
           f"{ci.HOST}'s aggregate names are fanout_ci.HOST_JOBS: {platforms!r}")
    sharded = platform_list.search(shards)
    ensure(named is not None and sharded is not None and sharded[1] == named[1],
           "every aggregate platform runs the shards it requires")
    labels = re.findall(r"(?m)^\s*(?:runs-on|- \{platform: \w+, runner): ([^\s,}]+)", contents)
    ensure(bool(labels) and not any("latest" in label for label in labels),
           f"{ci.HOST} names explicit runner images: {labels!r}")


def _workflow_checkout_validation() -> None:
    scripts: list[str] = []
    for workflow in (ci.HOST, ci.GUEST):
        contents = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
        step = contents.split("      - name: Verify dispatched revision belongs to main\n", 1)[1]
        script = step.split("        run: |\n", 1)[1].split("\n      - ", 1)[0]
        scripts.append(textwrap.dedent(script))
    with sandbox_tree({"README.md": "workflow fixture\n"}) as root:
        _fixture_identity(root)
        _git(root, "commit", "--allow-empty", "-qm", "base")
        base = _git(root, "rev-parse", "HEAD")
        _git(root, "commit", "--allow-empty", "-qm", "advance main")
        advanced = _git(root, "rev-parse", "HEAD")
        _git(root, "checkout", "--detach", base)
        _git(root, "commit", "--allow-empty", "-qm", "unpublished sibling")
        sibling = _git(root, "rev-parse", "HEAD")
        cases = ((base, base, base, "refs/heads/main", True),
                 (base, base, advanced, "refs/heads/main", True),
                 (advanced, base, advanced, "refs/heads/main", False),
                 (base, base[:7], advanced, "refs/heads/main", False),
                 (sibling, sibling, advanced, "refs/heads/main", False),
                 (base, base, advanced, "refs/heads/work/stranded", False))
        for checkout, requested, main, ref, passes in cases:
            _git(root, "checkout", "--detach", checkout)
            environment = dict(os.environ, REQUESTED_REVISION=requested,
                               DISPATCH_REF=ref, DISPATCH_MAIN_SHA=main)
            for script in scripts:
                done = subprocess.run([sys.executable, "-c", script], cwd=root,
                                      env=environment, capture_output=True, text=True,
                                      check=False, timeout=30)
                ensure((done.returncode == 0) == passes,
                       f"workflow checkout guard gave wrong verdict: {done.stderr}")


def cases() -> list[Case]:
    return [Case("successful-handoff", _successful_handoff),
            Case("host-pending", _host_pending), Case("host-failure", _host_failure),
            Case("host-aggregate-evidence", _host_aggregate_evidence),
            Case("host-revision-binding", _host_revision_binding),
            Case("host-dispatch", _host_dispatch),
            Case("late-push-run-adopted", _late_push_run_adopted),
            Case("main-ancestry", _main_ancestry),
            Case("dispatch-revision-survives-main-advance", _dispatch_revision_survives_main_advance),
            Case("guest-interrupt-recovery", _guest_interrupt_recovery),
            Case("ambiguous-recovery-never-reposts", _ambiguous_recovery_never_reposts),
            Case("recovery-main-and-own-dispatch", _recovery_requires_main_and_own_dispatch),
            Case("rejected-dispatch-retry", _rejected_dispatch_can_retry),
            Case("host-interrupt-recovery", _host_interrupt_recovery),
            Case("token-journal-recovery", _token_journal_recovery),
            Case("remote-validation", _remote_validation), Case("state-validation", _state_validation),
            Case("transport-contract", _transport_contract),
            Case("dispatch-subject", _dispatch_subject),
            Case("workflow-titles", _workflow_titles),
            Case("workflow-host-job-names", _workflow_host_job_names),
            Case("workflow-checkout-validation", _workflow_checkout_validation)]
