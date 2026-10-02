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

# Each case writes only under directories it creates, answers requests from a FakeGitHub
# of its own where it makes any, and patches only inside a `with`, so the cases share no
# state, and a sharded run spreads them over every shard (vos/cli/test.py).
INDEPENDENT_CASES = True

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


def _reading_base_forwarded() -> None:
    base = "b" * 40
    fake = FakeGitHub(ci.new_state(REPO, "main", REVISION, True, base))
    fake.host_runs = []
    ensure(not fake.advance(), "the fixture's host dispatch starts pending")
    ensure(fake.advance(), "the passing host run dispatches guest")
    ensure([payload for _, _, payload in fake.posts()] == [
        {"ref": "main", "inputs": {"revision": REVISION, "title": SUBJECT}},
        {"ref": "main", "inputs": {"revision": REVISION, "title": SUBJECT, "cold": True,
                                   "reading_base": base}}],
        "Guest CI's dispatch, and only it, carries the batch's reading base")
    # A rejected guest dispatch, retried, carries the same reading base.
    fake = FakeGitHub(ci.new_state(REPO, "main", REVISION, False, base))
    fake.dispatch_error = ci.APIError(422)
    _refuses(fake.advance, "a rejected dispatch must fail the handoff")
    fake.dispatch_error = None
    ensure(fake.advance(), "a rejected dispatch can retry")
    guest = {"ref": "main", "inputs": {"revision": REVISION, "title": SUBJECT, "cold": False,
                                       "reading_base": base}}
    ensure([payload for _, _, payload in fake.posts()] == [guest, guest],
           "a retried guest dispatch forwards the reading base it first sent")
    # A record without the field sends none.
    fake = FakeGitHub(_state())
    ensure(fake.advance() and "reading_base" not in fake.state, "no reading base is recorded")
    ensure([payload for _, _, payload in fake.posts()] == [
        {"ref": "main", "inputs": {"revision": REVISION, "title": SUBJECT, "cold": True}}],
        "a batch without a reading base sends no reading_base input")


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
                       ("repository", "github.com/example/repo"),
                       # Guest CI's dispatch check refuses each of these reading bases.
                       ("reading_base", "b" * 7), ("reading_base", "B" * 40),
                       ("reading_base", REVISION), ("reading_base", None),
                       ("reading_base", "")):
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


def _job_text(contents: str, job: str) -> str:
    """A workflow job's block after its key's line, ended by the next line at the jobs'
    own indentation, a comment there included."""
    block = contents.split(f"\n  {job}:\n", 1)[1]
    end = re.search(r"\n  (?=\S)", block)
    return block if end is None else block[:end.start()]


def _workflow_host_job_names() -> None:
    # The aggregate jobs' names are the evidence _host_status accepts: a renamed job
    # or platform leaves fanout refusing every Host CI run, however green.
    contents = (ROOT / ".github/workflows" / ci.HOST).read_text(encoding="utf-8")
    shards, aggregate = _job_text(contents, "host-gates-shard"), _job_text(contents, "host-gates")
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
    faults = _runner_faults(contents)
    ensure(not faults, f"{ci.HOST} names an explicit runner image per platform: {faults!r}")
    faults = _gate_faults(contents)
    ensure(not faults, f"{ci.HOST} runs the gate once on every runner: {faults!r}")
    # The model's hooks run on the image the Ubuntu shards name, so an image move that
    # leaves the hooks behind is refused.
    uncommented = {job: [line for line in _job_text(contents, job).split("\n")
                         if not line.lstrip().startswith("#")]
                   for job in ("host-gates-shard", "model-hooks")}
    entries = _include_entries(uncommented["host-gates-shard"])
    ubuntu = [_key_values(entry, "runner") for entry in entries
              if _key_values(entry, "platform") == ["Ubuntu"]]
    hooks = _key_values("\n".join(uncommented["model-hooks"]), "runs-on")
    ensure(len(hooks) == 1 and bool(ubuntu) and all(labels == hooks for labels in ubuntu),
           f"{ci.HOST}'s model-hooks job runs on the Ubuntu shards' image: {hooks!r}, {ubuntu!r}")
    # Each platform runs one unpartitioned job beside its shards, an include entry of its
    # own that names its runner, so the shards and it together run the whole gate.
    unpartitioned = sorted(name for entry in entries
                           if _key_values(entry, "shard") == ["unpartitioned"]
                           and len(_key_values(entry, "runner")) == 1
                           for name in _key_values(entry, "platform"))
    ensure(unpartitioned == sorted(platforms),
           f"{ci.HOST} runs one unpartitioned job on each platform: {unpartitioned!r}")


# Each aggregate check's command: one `test "$NAME" = success` for each job it needs,
# joined by `&&`, so it passes only where every one of them succeeded.
_RESULT_TEST_RE = re.compile(r'test "\$([A-Z][A-Z_]*)" = success')


def _aggregate_faults(contents: str) -> list[str]:
    """Why the host workflow's aggregate job could pass beside a job that did not succeed.

    The aggregate needs every other job of the workflow, listed in a flow sequence, and
    runs whatever they concluded. No uncommented line of any job, the aggregate's
    included, spells continue-on-error in any spelling `_spellings` gives it, so a
    failed step fails its job and a failed job its result. The aggregate's one step
    states only its name, env and run, so no condition skips it and no shell of its own
    runs the line. It binds one environment variable to each needed job's result, and
    its single-line run is a `test "$NAME" = success` of each of them, once, joined by
    `&&` with nothing else. A shell set by `defaults` is not read."""
    jobs = _workflow_jobs(contents)
    aggregate = jobs.get("host-gates", "")
    others = sorted(job for job in jobs if job != "host-gates")
    faults: list[str] = []
    listed = re.search(r"(?m)^    needs: \[([^\]\n]*)\]$", aggregate)
    needed = sorted(name.strip() for name in listed[1].split(",")) if listed else []
    if needed != others:
        faults.append(f"the aggregate needs {needed!r}, not every other job {others!r}")
    if not re.search(r"(?m)^    if: \$\{\{ always\(\) \}\}$", aggregate):
        faults.append("the aggregate does not run whatever the jobs it needs concluded")
    for job, block in sorted(jobs.items()):
        uncommented = "\n".join(line for line in block.split("\n")
                                if not line.lstrip().startswith("#"))
        if any("continue-on-error" in spelling for spelling in _spellings(uncommented)):
            faults.append(f"{job} states continue-on-error, so a failure in it can leave a "
                          "result the aggregate reads green")
    steps = _step_texts(aggregate)
    if len(steps) != 1:
        return [*faults, f"the aggregate runs {len(steps)} step(s), not one"]
    stated = re.findall(r"(?m)^(?:      - |        )([^\s:][^:\n]*?)[ \t]*:", steps[0])
    if extra := sorted(set(stated) - {"name", "env", "run"}):
        faults.append(f"the aggregate's step states {extra!r} beside its name, env and run, "
                      "so it can be skipped or run its line otherwise")
    bound: dict[str, str] = {}
    for line in _step_block(steps[0], "env")[1:]:
        result = re.fullmatch(r"          ([A-Z][A-Z_]*): \$\{\{ needs\.([\w-]+)\.result \}\}",
                              line)
        if result is None:
            faults.append(f"the aggregate's environment line {line!r} binds no job's result")
        else:
            bound[result[1]] = result[2]
    runs = _step_values(steps[0], "run")
    tested = [m[1] for m in _RESULT_TEST_RE.finditer(runs[0])] if len(runs) == 1 else []
    if (len(runs) != 1 or _continued(steps[0])
            or runs[0] != " && ".join(f'test "${name}" = success' for name in tested)):
        faults.append(f"the aggregate runs {runs!r}, not only a success test of each result")
    results = sorted(bound.get(name, "") for name in tested)
    if len(set(tested)) != len(tested) or results != others:
        faults.append(f"the aggregate tests {tested!r}, bound to {bound!r}, not each result of "
                      f"{others!r} once")
    return faults


def _workflow_host_aggregate_needs() -> None:
    # The aggregates are the platforms' verdicts: one that passed beside a failed shard or
    # a failed model-hooks job would report a run green that one of its jobs refused.
    contents = (ROOT / ".github/workflows" / ci.HOST).read_text(encoding="utf-8")
    found = _aggregate_faults(contents)
    ensure(not found, f"{ci.HOST}'s aggregates require every other job: {found!r}")
    hooks = ' && test "$HOOKS_RESULT" = success'
    bindings = "        env:\n          SHARDS_RESULT:"
    for mutant, fragment in (
            (contents.replace("    name: model-hooks\n",
                              "    name: model-hooks\n    continue-on-error: true\n"),
             "model-hooks states continue-on-error"),
            (contents.replace("      - name: Model hooks\n",
                              "      - name: Model hooks\n        continue-on-error: true\n"),
             "model-hooks states continue-on-error"),
            (contents.replace("    if: ${{ always() }}\n",
                              "    if: ${{ always() }}\n    continue-on-error: true\n"),
             "host-gates states continue-on-error"),
            (contents.replace(bindings, "        if: ${{ false }}\n" + bindings),
             "beside its name, env and run"),
            (contents.replace("    needs: [host-gates-shard, model-hooks]\n",
                              "    needs: host-gates-shard\n"), "not every other job"),
            (contents.replace("    if: ${{ always() }}\n", ""), "does not run whatever"),
            (contents.replace(hooks, ""), "not each result"),
            (contents.replace(hooks, hooks + " || true"), "not only a success test"),
            (contents.replace("${{ needs.model-hooks.result }}",
                              "${{ needs.host-gates-shard.result }}"), "not each result"),
            (contents.replace("${{ needs.model-hooks.result }}", "success"),
             "binds no job's result")):
        ensure(mutant != contents, f"the fixture for {fragment!r} changed nothing")
        found = _aggregate_faults(mutant)
        ensure(any(fragment in fault for fault in found),
               f"an aggregate that can pass beside a failed job must be refused "
               f"({fragment!r}): {found!r}")


# The shard job's gate command, and its two platform branches as the workflow spells
# them: PowerShell on Windows and bash on every other runner, so each runner takes one,
# each with the exact line its shell runs. A run that merely starts with the command
# could append `|| true` and finish green without the gate's verdict.
_GATE = "python tools/run.py --check --tests"
_GATE_COMMANDS = {
    ("${{ runner.os == 'Windows' }}", "pwsh"):
        f'{_GATE} "$env:PART" --summary "$env:RUNNER_TEMP/$env:VERDICT_FILE"',
    ("${{ runner.os != 'Windows' }}", "bash"):
        f'{_GATE} "$PART" --summary "$RUNNER_TEMP/$VERDICT_FILE"',
}
_GATE_BRANCHES = sorted(_GATE_COMMANDS)
# A job-level key of the shard job, whose keys sit at four spaces, bare or quoted.
_JOB_CONTINUE_RE = re.compile(r"""(?m)^    (["']?)continue-on-error\1[ \t]*:""")
# Each gate step's environment block, exactly as the workflow spells it for its branch:
# the job's part of the gate, its shard or the unpartitioned members, and on Windows the
# temporary directories on the checkout's drive, and nothing a shell or an interpreter
# would read first.
_GATE_PART = ("          PART: ${{ matrix.shard == 'unpartitioned' && '--unpartitioned' || "
              "format('--shard={0}/{1}', matrix.shard, matrix.shards) }}")
_GATE_ENVS = {
    ("${{ runner.os == 'Windows' }}", "pwsh"):
        ["        env:", _GATE_PART, "          TMP: ${{ runner.temp }}",
         "          TEMP: ${{ runner.temp }}"],
    ("${{ runner.os != 'Windows' }}", "bash"): ["        env:", _GATE_PART],
}
# A variable a shell reads before the command it runs: GitHub runs a bash step as
# non-interactive bash, which sources the file BASH_ENV names and defines a function
# for each BASH_FUNC_<name>%% variable holding a function body, and sh reads ENV where
# it is interactive. Each can install `trap 'exit 0' EXIT` or replace `python`, and
# turn a failing gate green. The reading is textual: such a name standing as a word on
# an uncommented line of the workflow, in any of the spellings `_spellings` gives that
# text. A name a step builds at run time is not read.
_SHELL_STARTUP_RE = re.compile(
    r"(?<![A-Za-z0-9_])(BASH_ENV|ENV|BASH_FUNC_[A-Za-z0-9_]+)(?![A-Za-z0-9_])")
# The numeric escapes YAML's double-quoted scalars and bash's ANSI-C quoting decode, at
# bash's widths, PowerShell 7's `u{...}, and an escaped line break with the indentation
# after it, which YAML and bash both join. A single-character escape such as `\n` or
# PowerShell's `` `n `` is not decoded here; `_spellings` reads it as a separator.
_ESCAPE_RE = re.compile(
    r"\\(?:x([0-9A-Fa-f]{1,2})|u([0-9A-Fa-f]{1,4})|U([0-9A-Fa-f]{1,8})|([0-7]{1,3})"
    r"|\r?\n[ \t]*)|`u\{([0-9A-Fa-f]{1,6})\}")
# How many passes `_decoded` takes at most: a pass can write a new escape, as YAML's
# `\x5c` turns the text after it into a bash escape, and decoding stops sooner where a
# pass changes nothing.
_DECODINGS = 4


def _unescaped(match: re.Match[str]) -> str:
    """One escape `_ESCAPE_RE` matched, decoded, and an escaped line break joined."""
    hexadecimal = match[1] or match[2] or match[3] or match[5]
    if hexadecimal is None and match[4] is None:
        return ""
    point = int(hexadecimal, 16) if hexadecimal is not None else int(match[4], 8)
    return chr(point) if point <= 0x10FFFF else match[0]


def _decoded(text: str) -> str:
    """`text` with `_ESCAPE_RE`'s escapes decoded until a pass changes nothing, or for
    `_DECODINGS` passes, so an escape an earlier decoding wrote is decoded too."""
    for _ in range(_DECODINGS):
        decoded = _ESCAPE_RE.sub(_unescaped, text)
        if decoded == text:
            break
        text = decoded
    return text


def _spellings(text: str) -> list[str]:
    """A workflow's text as written; with its numeric escapes decoded and escaped line
    breaks joined; that again with every quote, backtick and backslash dropped, as bash's
    quote removal and PowerShell's backtick escapes leave a word; that decoded text with
    each backslash or backtick and the character after it read as a separator, as a
    single-character escape such as YAML's or bash's `\\n` or PowerShell's `` `n `` ends
    the word before the name it writes; and that decoded text with each run of
    backslashes and backticks and the character after the run read as one separator, as
    a doubled backslash that bash's or YAML's double quotes reduce to one, before an
    escape `printf` or `echo -e` then decodes, ends that word too."""
    decoded = _decoded(text)
    return [text, decoded, re.sub(r"[\"'`\\]", "", decoded), re.sub(r"[\\`].", " ", decoded),
            re.sub(r"[\\`]+.", " ", decoded)]


def _startup_names(contents: str) -> list[str]:
    """Each `_SHELL_STARTUP_RE` name an uncommented line of a workflow spells."""
    uncommented = "\n".join(line for line in contents.split("\n")
                            if not line.lstrip().startswith("#"))
    return sorted({m[1] for spelling in _spellings(uncommented)
                   for m in _SHELL_STARTUP_RE.finditer(spelling)})


def _step_texts(job: str) -> list[str]:
    """The text of each step of a job's block-sequence `steps:`, comment lines dropped."""
    lines = [line for line in job.split("\n") if not line.lstrip().startswith("#")]
    start = next((n for n, line in enumerate(lines) if line.rstrip() == "    steps:"), None)
    steps: list[list[str]] = []
    for line in lines[start + 1:] if start is not None else []:
        if line.strip() and not line.startswith("      "):
            break
        if line.startswith("      - "):
            steps.append([])
        if steps:
            steps[-1].append(line)
    return ["\n".join(step) for step in steps]


def _step_values(step: str, key: str) -> list[str]:
    """Every value a step states for one of its own keys, on its dash line or beneath."""
    pattern = r"(?m)^(?:      - |        )" + re.escape(key) + r":[ \t]*(.*?)[ \t]*$"
    return [m[1] for m in re.finditer(pattern, step)]


def _step_block(step: str, key: str) -> list[str]:
    """A step's own `key:` line and every nonblank line indented beneath it, before the
    step's next key, as the workflow spells them; empty where the step states none."""
    lines = step.split("\n")
    start = next((n for n, line in enumerate(lines)
                  if re.match(r"(?:      - |        )" + re.escape(key) + ":", line)), None)
    if start is None:
        return []
    block = [lines[start].rstrip()]
    for line in lines[start + 1:]:
        if not line.strip():
            continue
        if len(line) - len(line.lstrip()) <= 8:
            break
        block.append(line.rstrip())
    return block


def _continued(step: str) -> bool:
    """Whether a line follows a step's `run:` line more deeply indented than the step's
    own keys, before the next of them, which YAML folds into a plain scalar's value."""
    lines = step.split("\n")
    start = next((n for n, line in enumerate(lines)
                  if re.match(r"(?:      - |        )run:", line)), None)
    for line in lines[start + 1:] if start is not None else []:
        if not line.strip():
            continue
        return len(line) - len(line.lstrip()) > 8
    return False


def _gate_faults(contents: str) -> list[str]:
    """Why the host workflow's shard job does not run its gate exactly once per runner,
    with the gate's exit as the step's verdict.

    The gate is two steps, and a step whose `if:` is false is skipped with its job still
    green, so a shard on which neither condition held would pass having run nothing.
    Each gate step is a block step whose own single-line `run:` starts with the gate
    command, the command standing anywhere else in the job is refused rather than read,
    and the two steps' `if:` and `shell:` must be exactly the complementary pair. A gate
    that runs can still finish green without its verdict, so each step's `run:` must be
    exactly its branch's command with no continuation line folded into it, and neither a
    gate step nor the shard job may state `continue-on-error`. A shell can run code of
    its own before the command, so each gate step's `env:` block must be exactly its
    branch's PART line and, on Windows, its TMP and TEMP lines, and no uncommented line
    of the workflow may spell BASH_ENV,
    ENV or a BASH_FUNC_ variable as a word in any spelling `_spellings` gives it: as
    written, with its numeric escapes decoded, with its quotes, backticks and
    backslashes then dropped, with each backslash or backtick escape read as a
    separator, or with each run of backslashes and backticks and the character after
    the run read as one separator. Steps other than the gate's are read for those names
    alone, and a name a step builds at run time is not read.
    """
    shards = _job_text(contents, "host-gates-shard")
    gates = [step for step in _step_texts(shards)
             if any(value.startswith(_GATE) for value in _step_values(step, "run"))]
    text = "\n".join(line for line in shards.split("\n") if not line.lstrip().startswith("#"))
    faults: list[str] = []
    if startup := _startup_names(contents):
        faults.append(f"the workflow names {' and '.join(startup)}, which a shell reads "
                      "before the gate's command and which can turn a failing gate green")
    if text.count(_GATE) != len(gates):
        faults.append("the gate command stands outside a step's own single-line run")
    if len(gates) != 2:
        faults.append(f"the shard job runs the gate in {len(gates)} step(s), not two")
    if _JOB_CONTINUE_RE.search(text):
        faults.append("the shard job states continue-on-error, so a failed gate can leave "
                      "it green")
    branches: list[tuple[str, str]] = []
    for step in gates:
        if "continue-on-error" in step:
            faults.append("a gate step states continue-on-error, so its failure can leave "
                          "the job green")
        if _continued(step):
            faults.append("a gate step's run continues past its line, so the command it "
                          "runs is not the line read")
        conditions, shells = _step_values(step, "if"), _step_values(step, "shell")
        runs = _step_values(step, "run")
        # A step whose branch is not one of the pair states no block that is its own.
        environments = _step_values(step, "env")
        stated = (_GATE_ENVS.get((conditions[0], shells[0]))
                  if len(conditions) == 1 and len(shells) == 1 else None)
        if len(environments) != 1 or _step_block(step, "env") != stated:
            faults.append(f"a gate step states {len(environments)} env key(s) and the "
                          f"block {_step_block(step, 'env')!r}, not exactly the lines its "
                          "branch states, so its shell can read more than its part of the gate")
        if len(conditions) != 1 or len(shells) != 1 or len(runs) != 1:
            faults.append(f"a gate step states {len(conditions)} if, {len(shells)} shell "
                          f"and {len(runs)} run keys, not one of each")
            continue
        branches.append((conditions[0], shells[0]))
        wanted = _GATE_COMMANDS.get(branches[-1])
        if wanted is not None and runs[0] != wanted:
            faults.append(f"the {shells[0]} gate step runs {runs[0]!r}, not exactly "
                          f"{wanted!r}, so its exit need not be the gate's")
    if len(gates) == 2 and sorted(branches) != _GATE_BRANCHES:
        faults.append(f"the gate steps' conditions and shells are {sorted(branches)!r}, "
                      f"not the complementary {_GATE_BRANCHES!r}")
    return faults


_GATE_JOB = """jobs:
  host-gates-shard:
    runs-on: ${{ matrix.runner }}
    steps:
      - name: Export a setting
        if: ${{ runner.os == 'Windows' }}
        shell: pwsh
        run: |
          "TMP=$env:RUNNER_TEMP" >> $env:GITHUB_ENV

      # The gate, once per platform.
      - name: Host gates and behavioral tests (Windows)
        if: ${{ runner.os == 'Windows' }}
        shell: pwsh
        env:
          PART: ${{ matrix.shard == 'unpartitioned' && '--unpartitioned' || format('--shard={0}/{1}', matrix.shard, matrix.shards) }}
          TMP: ${{ runner.temp }}
          TEMP: ${{ runner.temp }}
        run: python tools/run.py --check --tests "$env:PART" --summary "$env:RUNNER_TEMP/$env:VERDICT_FILE"

      - name: Host gates and behavioral tests (Ubuntu)
        if: ${{ runner.os != 'Windows' }}
        shell: bash
        env:
          PART: ${{ matrix.shard == 'unpartitioned' && '--unpartitioned' || format('--shard={0}/{1}', matrix.shard, matrix.shards) }}
        run: python tools/run.py --check --tests "$PART" --summary "$RUNNER_TEMP/$VERDICT_FILE"

      - name: Report gate results
        if: ${{ !cancelled() }}
        shell: python
        run: print("report")
  host-gates:
    runs-on: ubuntu-26.04
"""


def _workflow_gate_on_every_runner() -> None:
    # The reading is held to fixtures of its own: the complementary pair passes, and a
    # pair that leaves some runner without a gate, a gate it cannot read, or a gate
    # that can finish green without its verdict, is refused.
    found = _gate_faults(_GATE_JOB)
    ensure(not found, f"the complementary pair passes: {found!r}")
    ubuntu = _GATE_JOB.split("      - name: Host gates and behavioral tests (Ubuntu)\n", 1)
    missing = ubuntu[0] + "      - name: Report" + ubuntu[1].split("      - name: Report", 1)[1]
    verdict = '--summary "$RUNNER_TEMP/$VERDICT_FILE"'
    report = "\n      - name: Report gate results\n"
    part = _GATE_PART + "\n"
    environment = "        env:\n" + part
    temporary = "          TMP: ${{ runner.temp }}\n          TEMP: ${{ runner.temp }}\n"
    job = "    runs-on: ${{ matrix.runner }}\n"
    trap = "${{ runner.temp }}/trap.sh\n"
    export = ("\n      - name: Export\n        if: ${{ runner.os != 'Windows' }}\n"
              "        shell: bash\n        run: ")
    for workflow, fragment in (
            (_GATE_JOB.replace("runner.os != 'Windows'", "runner.os == 'Linux'"),
             "not the complementary"),
            (_GATE_JOB.replace("runner.os != 'Windows'", "runner.os == 'Windows'"),
             "not the complementary"),
            (_GATE_JOB.replace("shell: bash", "shell: pwsh"), "not the complementary"),
            (missing, "in 1 step(s), not two"),
            (_GATE_JOB.replace('run: python tools/run.py --check --tests "$PART"',
                               'run: |\n          python tools/run.py --check --tests '
                               '"$PART"'), "outside a step's own single-line run"),
            (_GATE_JOB.replace("        shell: bash\n",
                               "        shell: bash\n        if: ${{ false }}\n"),
             "states 2 if, 1 shell and 1 run keys"),
            # A gate that runs and finishes green without its verdict: continuing on its
            # error, at the step or the job, or a run that swallows the exit.
            (_GATE_JOB.replace("        shell: bash\n",
                               "        shell: bash\n        continue-on-error: true\n"),
             "a gate step states continue-on-error"),
            (_GATE_JOB.replace("    runs-on: ${{ matrix.runner }}\n",
                               "    runs-on: ${{ matrix.runner }}\n"
                               "    continue-on-error: true\n"),
             "the shard job states continue-on-error"),
            (_GATE_JOB.replace("    runs-on: ${{ matrix.runner }}\n",
                               "    runs-on: ${{ matrix.runner }}\n"
                               "    'continue-on-error': ${{ matrix.shard > 1 }}\n"),
             "the shard job states continue-on-error"),
            (_GATE_JOB.replace(verdict, f"{verdict} || true"),
             "the bash gate step runs"),
            (_GATE_JOB.replace(f"{verdict}\n", f"{verdict}\n          || exit 0\n"),
             "continues past its line"),
            (_GATE_JOB.replace(f"{verdict}\n", f"{verdict}\n\n          || exit 0\n"),
             "continues past its line"),
            (_GATE_JOB.replace(f"{verdict}\n{report}",
                               f"{verdict}\n        continue-on-error: true\n{report}"),
             "a gate step states continue-on-error"),
            # A gate whose shell runs code of its own first: a step environment beyond
            # its part of the gate, or a startup file a shell sources, named at the step,
            # the job or the workflow, bare, quoted or in a flow mapping, or written by a
            # run.
            (_GATE_JOB.replace(part, part + "          BASH_ENV: " + trap, 1),
             "not exactly the lines its branch states"),
            (_GATE_JOB.replace(part, part + "          BASH_ENV: " + trap, 1),
             "the workflow names BASH_ENV"),
            (_GATE_JOB.replace(part, part + "          PYTHONPATH: .\n"),
             "not exactly the lines its branch states"),
            (_GATE_JOB.replace("        shell: pwsh\n" + environment + temporary,
                               "        shell: pwsh\n"), "states 0 env key(s)"),
            (_GATE_JOB.replace("        shell: bash\n" + environment,
                               "        shell: bash\n        env: {PART: --shard=1/4}\n"),
             "not exactly the lines its branch states"),
            # Each branch's own lines: Windows without its temporary directories on the
            # checkout's drive, or bash with Windows's.
            (_GATE_JOB.replace("          TEMP: ${{ runner.temp }}\n", ""),
             "not exactly the lines its branch states"),
            (_GATE_JOB.replace("        shell: bash\n" + environment,
                               "        shell: bash\n" + environment + temporary),
             "not exactly the lines its branch states"),
            (_GATE_JOB.replace(job, job + "    env:\n      BASH_ENV: " + trap),
             "the workflow names BASH_ENV"),
            (_GATE_JOB.replace(job, job + '    env:\n      "BASH_ENV": ' + trap),
             "the workflow names BASH_ENV"),
            (_GATE_JOB.replace(job, job + "    env: {BASH_ENV: " + trap.rstrip() + "}\n"),
             "the workflow names BASH_ENV"),
            ("env:\n  'ENV': " + trap + _GATE_JOB, "the workflow names ENV"),
            (_GATE_JOB.replace('"TMP=$env:RUNNER_TEMP"', '"BASH_ENV=$env:RUNNER_TEMP/trap.sh"'),
             "the workflow names BASH_ENV"),
            # The same names spelled through YAML's double-quoted escapes and escaped
            # line break, bash's ANSI-C quoting and quote removal, or PowerShell's
            # backtick, and a function bash defines in place of python.
            (_GATE_JOB.replace(job, job + '    env:\n      "BASH\\x5fENV": ' + trap),
             "the workflow names BASH_ENV"),
            (_GATE_JOB.replace(job, job + '    env:\n      "BASH\\u005fENV": ' + trap),
             "the workflow names BASH_ENV"),
            (_GATE_JOB.replace(job, job + '    env:\n      "BASH\\\n        _ENV": ' + trap),
             "the workflow names BASH_ENV"),
            ('env:\n  "\\x45NV": ' + trap + _GATE_JOB, "the workflow names ENV"),
            (_GATE_JOB.replace(report, export + "echo $'BASH\\x5fENV=/tmp/t' >> \"$GITHUB_ENV\"\n"
                                       + report), "the workflow names BASH_ENV"),
            (_GATE_JOB.replace(report, export + "echo $'BASH\\137ENV=/tmp/t' >> \"$GITHUB_ENV\"\n"
                                       + report), "the workflow names BASH_ENV"),
            (_GATE_JOB.replace(report, export + "echo \"BASH\"'_ENV=/tmp/t' >> \"$GITHUB_ENV\"\n"
                                       + report), "the workflow names BASH_ENV"),
            (_GATE_JOB.replace('"TMP=$env:RUNNER_TEMP"', '"BASH`_ENV=$env:RUNNER_TEMP/trap.sh"'),
             "the workflow names BASH_ENV"),
            (_GATE_JOB.replace(job, job + '    env:\n      "BASH_FUNC_python%%": "() { exit 0; }"\n'),
             "the workflow names BASH_FUNC_python"),
            # A single-character escape ending the word before the name, in YAML's
            # double quotes, bash's ANSI-C quoting and PowerShell's backtick;
            # PowerShell 7's code-point escape; and a YAML escape writing a bash one.
            (_GATE_JOB.replace(report, export + "\"printf 'x\\nBASH_ENV=/tmp/t' >> "
                                       "$GITHUB_ENV\"\n" + report),
             "the workflow names BASH_ENV"),
            (_GATE_JOB.replace(report, export + "echo $'x\\nBASH_ENV=/tmp/t' >> \"$GITHUB_ENV\"\n"
                                       + report), "the workflow names BASH_ENV"),
            (_GATE_JOB.replace('"TMP=$env:RUNNER_TEMP"',
                               '"TMP=$env:RUNNER_TEMP`nBASH_ENV=$env:RUNNER_TEMP/trap.sh"'),
             "the workflow names BASH_ENV"),
            (_GATE_JOB.replace('"TMP=$env:RUNNER_TEMP"',
                               '"BASH`u{5f}ENV=$env:RUNNER_TEMP/trap.sh"'),
             "the workflow names BASH_ENV"),
            (_GATE_JOB.replace(report, export + "\"echo $'BASH\\x5cx5fENV=/tmp/t' >> "
                                       "$GITHUB_ENV\"\n" + report),
             "the workflow names BASH_ENV"),
            # A doubled backslash, which bash's or YAML's double quotes reduce to one,
            # before an escape printf then decodes into the break ending the word.
            (_GATE_JOB.replace(report, export + "printf \"x\\\\nBASH_ENV=/tmp/t\" >> "
                                       "\"$GITHUB_ENV\"\n" + report),
             "the workflow names BASH_ENV"),
            (_GATE_JOB.replace(report, export + "\"printf 'x\\\\nBASH_ENV=/tmp/t' >> "
                                       "$GITHUB_ENV\"\n" + report),
             "the workflow names BASH_ENV")):
        ensure(workflow != _GATE_JOB, f"the fixture for {fragment!r} changed nothing")
        found = _gate_faults(workflow)
        ensure(any(fragment in fault for fault in found),
               f"a gate some runner would skip, or one that can pass without its verdict, "
               f"must be refused ({fragment!r}): {found!r}")
    # A step other than the gate's is read for a startup file alone: one more step
    # anywhere passes, and so does a comment line naming one.
    extra = _GATE_JOB.replace(report, "\n      - name: Another step\n        if: ${{ "
                                      "runner.os != 'Windows' }}\n        continue-on-error: "
                                      f"true\n        run: echo other\n{report}")
    ensure(extra != _GATE_JOB and not _gate_faults(extra),
           f"a step outside the gate's is not read: {_gate_faults(extra)!r}")
    noted = _GATE_JOB.replace("      # The gate, once per platform.\n",
                              "      # The gate, once per platform; no BASH_ENV or ENV.\n")
    ensure(noted != _GATE_JOB and not _gate_faults(noted),
           f"a comment line naming a startup file is not a setting: {_gate_faults(noted)!r}")
    # The positive control: every tracked workflow's escapes, quotes and backticks read
    # clean in each spelling, so a refusal above is the name and not the decoding.
    workflows = sorted((ROOT / ".github/workflows").glob("*.yml"))
    ensure(bool(workflows), "the workflows directory holds the workflows")
    for workflow in workflows:
        named = _startup_names(workflow.read_text(encoding="utf-8"))
        ensure(not named, f"{workflow.name} spells {named}")


def _key_values(text: str, key: str) -> list[str]:
    """A key's values in any mapping style, block or flow, with the key bare or quoted."""
    pattern = (r"""(?:^|(?<=[\s{,]))(["']?)""" + re.escape(key)
               + r"""\1[ \t]*:[ \t]*["']?([^\s,{}\[\]"'#]*)""")
    return [m[2] for m in re.finditer(pattern, text, re.MULTILINE)]


def _include_entries(lines: list[str]) -> list[str]:
    """The text of each entry of the first `include:` list, as a flow or block sequence."""
    start = next((n for n, line in enumerate(lines)
                  if re.match(r"[ \t]*include:", line)), None)
    if start is None:
        return []
    indent = len(lines[start]) - len(lines[start].lstrip())
    body = [lines[start].split(":", 1)[1]]
    for line in lines[start + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        body.append(line)
    if "\n".join(body).strip().startswith("["):
        return [m[0] for m in re.finditer(r"\{[^{}]*\}", "\n".join(body))]
    dashes = [len(line) - len(line.lstrip()) for line in body if line.lstrip().startswith("- ")]
    entries: list[list[str]] = []
    for line in body:
        if dashes and line.startswith(" " * min(dashes) + "- "):
            entries.append([])
        if entries:
            entries[-1].append(line)
    return ["\n".join(entry) for entry in entries]


def _runner_faults(contents: str) -> list[str]:
    """Why the host workflow's shard runners are not explicit images per platform.

    Every `runner` key the shard job states, in any mapping style, must belong to an
    include entry naming one platform, every platform of the matrix must have one, and
    no label may be a moving `-latest` alias. Every `runs-on` is a block line whose
    value is either the shard job's `${{ matrix.runner }}`, stated once and there alone,
    or one unquoted label fully matching `[A-Za-z0-9][A-Za-z0-9._-]*` without `latest`,
    so a YAML alias, a flow sequence, another expression or a trailing comment is refused.
    """
    faults: list[str] = []
    shards = _job_text(contents, "host-gates-shard")
    lines = [line for line in shards.split("\n") if not line.lstrip().startswith("#")]
    text = "\n".join(lines)
    listed = re.search(r"(?m)^        platform: \[([^\]\n]*)\]$", text)
    platforms = {name.strip() for name in listed[1].split(",")} if listed else set()
    if not platforms:
        faults.append("the shard matrix lists no platform")
    runners: dict[str, list[str]] = {}
    for entry in _include_entries(lines):
        named, labels = _key_values(entry, "platform"), _key_values(entry, "runner")
        if len(named) == 1 and labels:
            runners.setdefault(named[0], []).extend(labels)
    stated = _key_values(text, "runner")
    if len(stated) != sum(len(labels) for labels in runners.values()):
        faults.append(f"a runner key stands outside a one-platform include entry: {stated!r}")
    faults += [f"{name} names no runner image" for name in sorted(platforms - set(runners))]
    faults += [f"{label!r} is not an explicit image label" for label in stated
               if "latest" in label or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", label)]
    workflow = "\n".join(line for line in contents.split("\n")
                         if not line.lstrip().startswith("#"))
    runs_on = re.findall(r"(?m)^[ \t]*runs-on:[ \t]*(.+?)[ \t]*$", workflow)
    if len(runs_on) != len(_key_values(workflow, "runs-on")):
        faults.append("a runs-on key is not a block line this reading takes")
    matrix_runner = "${{ matrix.runner }}"
    for label in runs_on:
        if label == matrix_runner:
            continue
        if "latest" in label:
            faults.append(f"runs-on {label!r} names a moving alias")
        elif not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", label):
            faults.append(f"runs-on {label!r} is not an explicit image label")
    if not re.search(r"(?m)^    runs-on: \$\{\{ matrix\.runner \}\}$", shards):
        faults.append("the shard job does not run on its matrix's runner")
    if runs_on.count(matrix_runner) > 1:
        faults.append(f"runs-on {matrix_runner} is stated {runs_on.count(matrix_runner)} "
                      "times, not once in the shard job")
    return faults


_SHARD_JOB = """jobs:
  host-gates-shard:
    runs-on: ${{ matrix.runner }}
    strategy:
      matrix:
        platform: [Ubuntu, Windows]
        include:
INCLUDE
  host-gates:
    runs-on: ubuntu-26.04
"""


def _workflow_runner_labels_any_style() -> None:
    # The reading is held to fixtures of its own, so a block-style include or a quoted
    # key cannot pass the host workflow's check by escaping it.
    flow = ("          - {platform: Ubuntu, runner: ubuntu-26.04, shards: 4}\n"
            "          - {platform: Windows, runner: windows-2025, shards: 8}")
    block = ("          - platform: Ubuntu\n            runner: ubuntu-26.04\n"
             "          - platform: Windows\n            runner: windows-2025")
    for include in (flow, block):
        found = _runner_faults(_SHARD_JOB.replace("INCLUDE", include))
        ensure(not found, f"explicit labels pass in either style: {found!r}")
    for include, fragment in (
            (block.replace("ubuntu-26.04", "ubuntu-latest"), "'ubuntu-latest' is not"),
            (flow.replace("runner: windows", '"runner": windows-latest-'), "not an explicit"),
            (block.rsplit("\n", 1)[0], "Windows names no runner image"),
            (flow + "\n        runner: [ubuntu-26.04]", "outside a one-platform include")):
        found = _runner_faults(_SHARD_JOB.replace("INCLUDE", include))
        ensure(any(fragment in fault for fault in found),
               f"a moving or missing runner must be refused ({fragment!r}): {found!r}")
    inline = _SHARD_JOB.replace("include:\nINCLUDE", (
        "include: [{platform: Ubuntu, runner: ubuntu-26.04},\n"
        "                  {platform: Windows, runner: windows-2025}]"))
    found = _runner_faults(inline)
    ensure(not found, f"a flow-sequence include is read: {found!r}")
    found = _runner_faults(inline.replace("windows-2025", "windows-latest"))
    ensure(any("'windows-latest' is not" in fault for fault in found),
           f"a flow-sequence alias must be refused: {found!r}")
    found = _runner_faults(_SHARD_JOB.replace("INCLUDE", flow).replace(
        "runs-on: ubuntu-26.04", "runs-on: ubuntu-latest"))
    ensure(any("moving alias" in fault for fault in found),
           f"a runs-on alias must be refused: {found!r}")
    # A runs-on value that names no label outright: a YAML alias, a flow sequence,
    # another expression, a quoted label or a trailing comment.
    for value in ("*image", "[ubuntu-26.04]", "${{ inputs.runner }}", "'ubuntu-26.04'",
                  "ubuntu-26.04 # image"):
        found = _runner_faults(_SHARD_JOB.replace("INCLUDE", flow).replace(
            "runs-on: ubuntu-26.04", f"runs-on: {value}"))
        ensure(any(f"runs-on {value!r} is not an explicit image label" in fault
                   for fault in found),
               f"runs-on {value!r} must be refused: {found!r}")
    found = _runner_faults(_SHARD_JOB.replace("INCLUDE", flow).replace(
        "runs-on: ubuntu-26.04", "runs-on: ${{ matrix.runner }}"))
    ensure(any("stated 2 times, not once in the shard job" in fault for fault in found),
           f"the matrix's runner belongs to the shard job alone: {found!r}")


# The instrument switch route's workflow, whose every job but the plan checks each
# checkout it takes against main before any of that checkout's code runs.
INSTRUMENT = "instrument-switches.yml"
_GUARD = "Verify dispatched revision belongs to main"


def _workflow_jobs(contents: str) -> dict[str, str]:
    """Each job's block of a workflow, by its key."""
    body = contents.split("\njobs:\n", 1)[1]
    names = re.findall(r"(?m)^  ([a-z][\w-]*):\n", body)
    blocks = re.split(r"(?m)^  [a-z][\w-]*:\n", body)[1:]
    return dict(zip(names, blocks, strict=True))


def _instrument_guard_faults(contents: str) -> tuple[list[str], list[str]]:
    """The instrument route's guard scripts, and why its jobs do not guard each checkout.

    The plan job checks out the dispatching commit alone and refuses its own ref and
    commit, so it carries no guard. Every other job's first step checks out that commit
    as `route`, and each checkout a job takes is followed at once by a guard step, run
    by Python in the checkout's directory, holding the checked-out revision, given as
    that checkout's own ref, to main's commit under main's ref, so no code of either
    checkout runs before its guard."""
    scripts: list[str] = []
    faults: list[str] = []
    for job, block in _workflow_jobs(contents).items():
        steps = _step_texts(block)
        checkouts = [n for n, step in enumerate(steps)
                     if re.search(r"(?m)^      - uses: actions/checkout@", step)]
        if job == "plan":
            refs = [_step_block(steps[n], "with") for n in checkouts]
            if len(checkouts) != 1 or "          ref: ${{ github.sha }}" not in refs[0]:
                faults.append("the plan job checks out more than the dispatching commit")
            continue
        if not checkouts or checkouts[0] != 0:
            faults.append(f"{job} does not open with its route checkout")
        for n in checkouts:
            given = "\n".join(_step_block(steps[n], "with"))
            ref = re.search(r"(?m)^          ref: (.+)$", given)
            path = re.search(r"(?m)^          path: (\S+)$", given)
            guard = steps[n + 1] if n + 1 < len(steps) else ""
            if (ref is None or path is None
                    or "          persist-credentials: false" not in given):
                faults.append(f"{job} takes a checkout without a ref, a path or "
                              "persist-credentials: false")
                continue
            if not guard.startswith(f"      - name: {_GUARD} ({path[1]})\n"):
                faults.append(f"{job}'s {path[1]} checkout is not followed by its guard")
                continue
            wanted = ["        env:", f"          REQUESTED_REVISION: {ref[1]}",
                      "          DISPATCH_REF: ${{ github.ref }}",
                      "          DISPATCH_MAIN_SHA: ${{ github.sha }}"]
            if (_step_values(guard, "shell") != ["python"]
                    or _step_values(guard, "working-directory") != [path[1]]
                    or _step_block(guard, "env") != wanted):
                faults.append(f"{job}'s {path[1]} guard does not hold that checkout to main")
            scripts.append(textwrap.dedent(guard.split("        run: |\n", 1)[1]))
    return scripts, faults


def _workflow_instrument_guards() -> None:
    contents = (ROOT / ".github/workflows" / INSTRUMENT).read_text(encoding="utf-8")
    scripts, faults = _instrument_guard_faults(contents)
    ensure(not faults and len(scripts) == 7,
           f"every instrument job guards each checkout it takes: {faults!r}, {len(scripts)}")
    ensure(not _startup_names(contents),
           f"{INSTRUMENT} sets no BASH_ENV, ENV or BASH_FUNC_*: {_startup_names(contents)}")
    side = "      - name: Verify dispatched revision belongs to main (side)\n"
    for workflow, fragment in (
            (contents.replace(side, "      - name: Install something first\n", 1),
             "side checkout is not followed by its guard"),
            (contents.replace("          DISPATCH_MAIN_SHA: ${{ github.sha }}\n",
                              "          DISPATCH_MAIN_SHA: ${{ needs.plan.outputs.revision }}\n",
                              1), "guard does not hold that checkout to main"),
            (contents.replace("        working-directory: side\n",
                              "        working-directory: route\n", 1),
             "guard does not hold that checkout to main"),
            (contents.replace("          path: route\n          fetch-depth: 0\n",
                              "          path: route\n          fetch-depth: 0\n"
                              "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
                              " # v7.0.1\n        with:\n          ref: ${{ inputs.revision }}\n",
                              1), "plan job checks out more")):
        ensure(workflow != contents, f"the fixture for {fragment!r} changed nothing")
        _, found = _instrument_guard_faults(workflow)
        ensure(any(fragment in fault for fault in found),
               f"an unguarded checkout must be refused ({fragment!r}): {found!r}")


def _workflow_checkout_validation() -> None:
    scripts: dict[str, str] = {}
    for workflow in (ci.HOST, ci.GUEST):
        contents = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
        step = contents.split("      - name: Verify dispatched revision belongs to main\n", 1)[1]
        script = step.split("        run: |\n", 1)[1].split("\n      - ", 1)[0]
        scripts[workflow] = textwrap.dedent(script)
    # Host CI checks a dispatch in each job taking a checkout, every copy the step whose
    # script runs below, its condition, identifier and environment included.
    host = (ROOT / ".github/workflows" / ci.HOST).read_text(encoding="utf-8")
    copies = [step for block in _workflow_jobs(host).values() for step in _step_texts(block)
              if _step_values(step, "name") == [_GUARD]]
    ensure(len(copies) == sum(workflow == ci.HOST for workflow, _ in _DISPATCH_JOBS)
           and len(set(copies)) == 1, f"{ci.HOST}'s jobs check a dispatch with one step")
    instrument, _ = _instrument_guard_faults(
        (ROOT / ".github/workflows" / INSTRUMENT).read_text(encoding="utf-8"))
    ensure(bool(instrument), f"{INSTRUMENT}'s guard steps are read")
    scripts.update((f"{INSTRUMENT} guard {n}", script) for n, script in enumerate(instrument))
    with sandbox_tree({"README.md": "workflow fixture\n"}) as root:
        _fixture_identity(root)
        _git(root, "commit", "--allow-empty", "-qm", "base")
        base = _git(root, "rev-parse", "HEAD")
        _git(root, "commit", "--allow-empty", "-qm", "advance main")
        advanced = _git(root, "rev-parse", "HEAD")
        _git(root, "checkout", "--detach", base)
        _git(root, "commit", "--allow-empty", "-qm", "unpublished sibling")
        sibling = _git(root, "rev-parse", "HEAD")
        tree = _git(root, "rev-parse", f"{base}^{{tree}}")
        # Git peels an annotated tag to its commit wherever a commit is expected, so only
        # comparing the named commit with the input refuses the tag object's SHA.
        _git(root, "-c", "tag.gpgSign=false", "tag", "-a", "-m", "reading base", "named", base)
        tag = _git(root, "rev-parse", "named")

        def guard(script: str, checkout: str, requested: str, main: str, ref: str,
                  reading_base: str = "") -> subprocess.CompletedProcess[str]:
            _git(root, "checkout", "--detach", checkout)
            environment = dict(os.environ, REQUESTED_REVISION=requested, DISPATCH_REF=ref,
                               DISPATCH_MAIN_SHA=main, READING_BASE=reading_base)
            return subprocess.run([sys.executable, "-c", script], cwd=root, env=environment,
                                  capture_output=True, text=True, check=False, timeout=30)

        cases = ((base, base, base, "refs/heads/main", True),
                 (base, base, advanced, "refs/heads/main", True),
                 (advanced, base, advanced, "refs/heads/main", False),
                 (base, base[:7], advanced, "refs/heads/main", False),
                 (sibling, sibling, advanced, "refs/heads/main", False),
                 (base, base, advanced, "refs/heads/work/stranded", False))
        for checkout, requested, main, ref, passes in cases:
            for script in scripts.values():
                done = guard(script, checkout, requested, main, ref)
                ensure((done.returncode == 0) == passes,
                       f"workflow checkout guard gave wrong verdict: {done.stderr}")
        # Guest CI's reading base, when nonempty, is refused before checked-out code runs
        # unless it is a full lowercase commit that is a proper ancestor of the revision.
        guest = scripts[ci.GUEST]
        for checkout, reading_base, refusal in (
                (advanced, base, None),
                (advanced, advanced, "other than the revision"),
                (advanced, base[:7], "full lowercase commit SHA"),
                (advanced, "A" * 40, "full lowercase commit SHA"),
                (advanced, f" {base}", "full lowercase commit SHA"),
                (advanced, "f" * 40, "names no commit"),
                (advanced, tree, "names no commit"),
                (advanced, tag, "names no commit"),
                (advanced, sibling, "not an ancestor"),
                (base, advanced, "not an ancestor")):
            done = guard(guest, checkout, checkout, advanced, "refs/heads/main", reading_base)
            if refusal is None:
                ensure(done.returncode == 0, f"a proper ancestor was refused: {done.stderr}")
            else:
                ensure(done.returncode != 0 and refusal in done.stderr,
                       f"reading base {reading_base!r} must be refused with {refusal!r}: "
                       f"{done.stderr}")


# A Host CI checkout's depth where it is not full history: one commit for push and pull
# request runs and full history for a dispatch, whose check runs `git merge-base
# --is-ancestor` against main. The dispatch arm is the string '0', because a bare 0 is
# falsy in an Actions expression and `&& 0 || 1` would give a dispatch depth 1 too.
_DISPATCH_DEPTH = re.compile(
    r"\$\{\{ github\.event_name == 'workflow_dispatch' && '0' \|\| '[1-9][0-9]*' \}\}")


def _checkout_depth_faults(contents: str, job: str) -> list[str]:
    """Why a dispatched Host CI job could check out without the history its ancestry
    check reads: the job takes one checkout, stating one `fetch-depth`, which is either
    0 or `_DISPATCH_DEPTH`'s conditional; an absent key is the action's depth 1."""
    checkouts = [step for step in _step_texts(_job_text(contents, job))
                 if any(value.startswith("actions/checkout@")
                        for value in _step_values(step, "uses"))]
    if len(checkouts) != 1:
        return [f"{job} takes {len(checkouts)} checkout(s), not one"]
    depths = [line.split(":", 1)[1].strip() for line in _step_block(checkouts[0], "with")
              if line.lstrip().startswith("fetch-depth:")]
    if len(depths) != 1:
        return [f"{job}'s checkout states {len(depths)} fetch-depth key(s), not one"]
    if depths[0] != "0" and _DISPATCH_DEPTH.fullmatch(depths[0]) is None:
        return [f"{job}'s fetch-depth {depths[0]!r} can check out a dispatch without the "
                "history its ancestry check reads"]
    return []


def _workflow_dispatch_checkout_keeps_history() -> None:
    # Every Host CI job that checks a dispatch, which is every one taking a checkout.
    contents = (ROOT / ".github/workflows" / ci.HOST).read_text(encoding="utf-8")
    jobs = [job for workflow, job in _DISPATCH_JOBS if workflow == ci.HOST]
    ensure(bool(jobs), f"{ci.HOST}'s checking jobs are read: {jobs!r}")
    for job in jobs:
        found = _checkout_depth_faults(contents, job)
        ensure(not found, f"{ci.HOST}'s {job} checks out a dispatch with main's history: "
                          f"{found!r}")
    depth = re.search(r"(?m)^          fetch-depth: .*\n", contents)
    ensure(depth is not None, f"{ci.HOST}'s shard checkout states its depth")
    line = depth[0] if depth else ""
    for workflow, fragment in (
            (contents.replace(line, "          fetch-depth: ${{ github.event_name == "
                                    "'workflow_dispatch' && 0 || 1 }}\n"), "can check out"),
            (contents.replace(line, "          fetch-depth: 1\n"), "can check out"),
            (contents.replace(line, ""), "states 0 fetch-depth key(s)"),
            (contents.replace(line, line + line), "states 2 fetch-depth key(s)")):
        ensure(workflow != contents, f"the fixture for {fragment!r} changed nothing")
        for job in jobs:
            found = _checkout_depth_faults(workflow, job)
            ensure(any(fragment in fault for fault in found),
                   f"a dispatch {job} checks out without main's history must be refused "
                   f"({fragment!r}): {found!r}")
    found = [fault for job in jobs for fault in _checkout_depth_faults(
        contents.replace(line, "          fetch-depth: 0\n"), job)]
    ensure(not found, f"full history on every run is accepted: {found!r}")


# The step that checks a dispatched revision, and the conjunct each later step that runs
# checked-out code after a failure states, in every job of each workflow that checks one:
# the two fanout dispatches and the boot signature target campaign's.
_DISPATCH_CHECK = "Verify dispatched revision belongs to main"
_DISPATCH_GUARD = "steps.dispatch.outcome != 'failure'"
_CAMPAIGN = "boot-crypto-target.yml"
_DISPATCH_JOBS = ((ci.HOST, "host-gates-shard"), (ci.HOST, "model-hooks"),
                  (ci.GUEST, "guest-gates"), (_CAMPAIGN, "interface"), (_CAMPAIGN, "campaign"))


def _conjuncts(condition: str) -> list[str] | None:
    """A step condition's top-level `&&` operands, or None where it is a disjunction."""
    expression = condition.strip()
    if expression.startswith("${{") and expression.endswith("}}"):
        expression = expression[3:-2]
    operands: list[str] = []
    depth, quoted, start, index = 0, False, 0, 0
    while index < len(expression):
        if expression[index] == "'":
            quoted = not quoted
        elif not quoted and expression[index] in "()":
            depth += 1 if expression[index] == "(" else -1
        elif not quoted and depth == 0 and expression.startswith("||", index):
            return None
        elif not quoted and depth == 0 and expression.startswith("&&", index):
            operands.append(expression[start:index].strip())
            start = index + 2
        index += 1
    return [*operands, expression[start:].strip()]


def _refused_dispatch_faults(contents: str, job: str, check_name: str = _DISPATCH_CHECK,
                             ident: str = "dispatch", exempt: str | None = None) -> list[str]:
    """Why a step of `job` could run checked-out code after its dispatch check refused.

    A step whose condition calls no status function runs only once every earlier step
    has succeeded, so a refused check skips it. One calling `always()`, `failure()` or
    `cancelled()`, `!cancelled()` included, runs after a failure too, so each such step
    after the check that runs a command, whose shell starts in the checkout, or a local
    `./` action must state the guard as a top-level conjunct of a one-line condition. A
    condition stated as a block scalar, or not on its `if:` line, is read as one that
    runs after a failure. The check, the step named `check_name`, is identified as
    `ident`, `dispatch` by default, and does not continue on error, so a refusal is a
    failure every later step sees. A pinned action's step runs that action's code. A
    step whose one command is `exempt`, run by no action, is left to its caller's reading.
    """
    guard = f"steps.{ident}.outcome != 'failure'"
    after = contents.split(f"\n  {job}:\n", 1)[1]
    steps = _step_texts(re.split(r"\n  (?=\S)", after, maxsplit=1)[0])
    checks = [n for n, step in enumerate(steps) if _step_values(step, "name") == [check_name]]
    if len(checks) != 1:
        return [f"{job} states the check {check_name!r} {len(checks)} time(s), not once"]
    check = steps[checks[0]]
    faults: list[str] = []
    if _step_values(check, "id") != [ident]:
        faults.append(f"{job}'s check {check_name!r} is not identified as {ident}, so no "
                      "later step can read its outcome")
    if _step_values(check, "continue-on-error"):
        faults.append(f"{job}'s check {check_name!r} continues on error, so a refusal runs "
                      "every later step")
    for step in steps[checks[0] + 1:]:
        local = any(value.startswith("./") for value in _step_values(step, "uses"))
        conditions = _step_values(step, "if")
        if not (_step_values(step, "run") or local) or not any(
                re.search(r"\b(?:always|failure|cancelled)\(\)", condition)
                or not condition or condition[0] in "|>" for condition in conditions):
            continue
        if exempt is not None and _step_values(step, "run") == [exempt] and not local:
            continue
        name = next(iter(_step_values(step, "name")), "an unnamed step")
        operands = _conjuncts(conditions[0]) if len(conditions) == 1 else None
        if operands is None or guard not in operands:
            faults.append(f"{job}'s step {name!r} runs checked-out code after a failure "
                          f"without requiring {guard}")
    return faults


def _instrument_refused_faults(contents: str) -> list[str]:
    """Why a step of the instrument route could run the requested revision's code after a
    refusal: the reading above over each job's check, the plan job's plan step and each
    later job's side guard, in every job that takes a side checkout, its staging alone
    excepted. Staging's one command runs the route checkout's instrument_route.py, which
    imports only the standard library and that checkout's `vos.receipts` and `vos.env`,
    over the job's private root, read as data, and reads no file of the side's checkout,
    where no step has run that revision's code before a refused guard. A failed route
    guard skips the side checkout, and the join takes none."""
    faults: list[str] = []
    side = f"{_GUARD} (side)"
    for job, block in _workflow_jobs(contents).items():
        names = [_step_values(step, "name") for step in _step_texts(block)]
        if job == "plan":
            check, ident = "Plan the dispatch", "plan"
        elif [side] in names:
            check, ident = side, "side"
        else:
            continue
        stage = f"python3 route/tools/ci/instrument_route.py stage --job {job}"
        faults += _refused_dispatch_faults(contents, job, check, ident, stage)
    return faults


def _in_job(contents: str, job: str, old: str, new: str) -> str:
    """`contents` with the first `old` after `job`'s own header made `new`."""
    start = contents.index(f"\n  {job}:\n")
    return contents[:start] + contents[start:].replace(old, new, 1)


def _workflow_refused_dispatch() -> None:
    # A refused dispatch runs no checked-out code: each step that runs a command after a
    # failure also requires its job's check not to have failed, in every checking job.
    guard = f" && {_DISPATCH_GUARD}"
    check = "        id: dispatch\n"
    named = {"host-gates-shard": ("Analyze workflows", "Report gate results"),
             "model-hooks": ("Model hooks",),
             "guest-gates": ("Model evidence", "Proof gate",
                             "Read the proofs against the reading base", "Report guest results"),
             "interface": (), "campaign": ("Report the campaign",)}
    # Every job of those workflows with a step using actions/checkout, its `uses:` on
    # the step's dash line or beneath it, is read, so a job added with one cannot run
    # its code after a refusal unread.
    for workflow in sorted({workflow for workflow, _ in _DISPATCH_JOBS}):
        contents = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
        taking = sorted(job for job, block in _workflow_jobs(contents).items()
                        if any(value.startswith("actions/checkout@")
                               for step in _step_texts(block)
                               for value in _step_values(step, "uses")))
        listed = sorted(job for read, job in _DISPATCH_JOBS if read == workflow)
        ensure(taking == listed, f"{workflow}'s jobs taking a checkout are read: {taking!r}")
    for workflow, job in _DISPATCH_JOBS:
        contents = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
        found = _refused_dispatch_faults(contents, job)
        ensure(not found, f"{workflow} runs checked-out code after a refusal: {found!r}")
        # The workflow without its guards, as it stood before they were stated, is
        # refused for every step that runs after a failure.
        found = _refused_dispatch_faults(contents.replace(guard, ""), job)
        for step in named[job]:
            ensure(any(f"step {step!r} runs checked-out code" in fault for fault in found),
                   f"{workflow}'s {step!r} without its guard must be refused: {found!r}")
        for mutant, fragment in (
                (_in_job(contents, job, check, ""), "not identified as dispatch"),
                (_in_job(contents, job, check, check + "        continue-on-error: true\n"),
                 "continues on error")):
            ensure(mutant != contents and any(
                fragment in fault for fault in _refused_dispatch_faults(mutant, job)),
                f"{workflow}'s {job} check must be refused ({fragment!r})")
    # A guard that does not bind the step: under a disjunction, at either level, or in a
    # condition the reading does not take; and a local action that runs after a failure.
    contents = (ROOT / ".github/workflows" / ci.GUEST).read_text(encoding="utf-8")
    report = "        if: ${{ !cancelled() && steps.dispatch.outcome != 'failure' }}\n"
    ensure(contents.count(report) == 1, "Guest CI's reporter states the guarded condition")
    upload = "      - name: Preserve guest logs and receipts\n"
    for mutant in (
            contents.replace(report, report.replace(" && ", " || ")),
            contents.replace(report, report.replace(
                f"&& {_DISPATCH_GUARD}", f"&& ({_DISPATCH_GUARD} || always())")),
            contents.replace(report, f"        if: >-\n          {report.split(': ', 1)[1]}"),
            contents.replace(upload, "      - name: Report locally\n        if: ${{ always() }}\n"
                                     "        uses: ./.github/actions/report\n\n" + upload)):
        ensure(mutant != contents and bool(_refused_dispatch_faults(mutant, "guest-gates")),
               "a guard that need not hold, or a local action after a failure, is refused")
    # A pinned action after a failure, such as the artifact upload, runs no checked-out code.
    ensure("        if: ${{ !cancelled() }}\n        uses: actions/upload-artifact@"
           in contents, "Guest CI's upload runs after a failure without the guard")
    # The instrument route: no step runs a requested revision's code after its plan or
    # side guard refused, staging alone running after either.
    contents = (ROOT / ".github/workflows" / INSTRUMENT).read_text(encoding="utf-8")
    found = _instrument_refused_faults(contents)
    ensure(not found, f"{INSTRUMENT} runs checked-out code after a refusal: {found!r}")
    side = "      - name: Verify dispatched revision belongs to main (side)\n        id: side\n"
    ensure(contents.count(side) == 3, f"{INSTRUMENT}'s three side guards are identified")
    stage = "      - name: Stage the build's records\n"
    stage_plan = "      - name: Stage the plan\n"
    for mutant, fragment in (
            (contents.replace(" && steps.side.outcome != 'failure'", ""),
             "step \"Compare the imported switch with the build's\" runs checked-out code"),
            (contents.replace(side, side.replace("        id: side\n", ""), 1),
             "is not identified as side"),
            (contents.replace(side, side + "        continue-on-error: true\n", 1),
             "continues on error"),
            (contents.replace(stage, "      - name: Report the side\n        if: ${{ always() }}\n"
                                     "        run: python3 side/tools/run.py quickchick check\n\n"
                              + stage, 1), "step 'Report the side' runs checked-out code"),
            (contents.replace("stage --job build\n", "stage --job build --side side\n", 1),
             "step \"Stage the build's records\" runs checked-out code"),
            (contents.replace(stage_plan, "      - name: Read the plan\n"
                                          "        if: ${{ failure() }}\n"
                                          "        run: python3 route/tools/ci/instrument_route.py"
                                          " plan\n\n" + stage_plan, 1),
             "step 'Read the plan' runs checked-out code")):
        ensure(mutant != contents, f"the instrument fixture for {fragment!r} changed nothing")
        found = _instrument_refused_faults(mutant)
        ensure(any(fragment in fault for fault in found),
               f"the instrument route must refuse this mutant ({fragment!r}): {found!r}")


def _workflow_reading_base_through_environment() -> None:
    # Every expression reading the input stands in an `if:` condition or as the value of
    # an uppercase environment key, so no script text ever holds its value.
    contents = (ROOT / ".github/workflows" / ci.GUEST).read_text(encoding="utf-8")
    lines = [line for line in contents.split("\n") if not line.lstrip().startswith("#")]
    reads = [line for line in lines if "reading_base" in "".join(
        expression for expression in re.findall(r"\$\{\{(.*?)\}\}", line))]
    ensure(len(reads) == 4, f"the input is read where the step guards expect: {reads!r}")
    for line in reads:
        ensure(re.fullmatch(r"          [A-Z][A-Z_]*: \$\{\{ [^{}]* \}\}", line) is not None
               or re.fullmatch(r"        if: \$\{\{ [^{}]* \}\}", line) is not None,
               f"the reading base reaches a step only through its environment: {line!r}")
    ensure(sum(line == "          READING_BASE: ${{ inputs.reading_base }}" for line in reads) == 2,
           "the dispatch check and the reading step each read the input from their environment")
    # Every other lane's reporter refuses a base, so only the proofs lane's receives one.
    ensure(sum(line == "          GUEST_READING_BASE: ${{ matrix.lane == 'proofs' && "
               "inputs.reading_base || '' }}" for line in reads) == 1,
           "only the proofs lane's reporter receives the base")
    host = (ROOT / ".github/workflows" / ci.HOST).read_text(encoding="utf-8")
    ensure("reading_base" not in host, "Host CI declares no reading base, and fanout sends it none")


def cases() -> list[Case]:
    return [Case("successful-handoff", _successful_handoff),
            Case("reading-base-forwarded", _reading_base_forwarded),
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
            Case("workflow-host-aggregate-needs", _workflow_host_aggregate_needs),
            Case("workflow-gate-on-every-runner", _workflow_gate_on_every_runner),
            Case("workflow-runner-labels-any-style", _workflow_runner_labels_any_style),
            Case("workflow-checkout-validation", _workflow_checkout_validation),
            Case("workflow-dispatch-checkout-keeps-history",
                 _workflow_dispatch_checkout_keeps_history),
            Case("workflow-instrument-guards", _workflow_instrument_guards),
            Case("workflow-refused-dispatch", _workflow_refused_dispatch),
            Case("workflow-reading-base-through-environment",
                 _workflow_reading_base_through_environment)]
