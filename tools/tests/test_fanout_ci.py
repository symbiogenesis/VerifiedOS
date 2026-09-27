# SPDX-License-Identifier: Apache-2.0
"""Hosted fan-out handoffs bind exact revisions and never poll guest verdicts."""

import copy
import json
import os
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import fanout_ci as ci

REVISION = "a" * 40
REPO = "example/verifiedos"
ROOT = Path(__file__).resolve().parents[2]


def _state() -> ci.CIState:
    return ci.new_state(REPO, f"fanout/batch/{REVISION}", REVISION, True)


def _run(number: int = 10, **changes: object) -> dict[str, object]:
    return {"id": number, "head_sha": REVISION, "event": "push", "status": "completed",
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
        self.dispatch_error: ci.APIError | None = None
        self.saved: list[ci.CIState] = []

    def save(self) -> None:
        self.saved.append(copy.deepcopy(self.state))

    def request(self, method: str, path: str,
                payload: dict[str, object] | None = None) -> dict[str, object]:
        self.calls.append((method, path, payload))
        if path.startswith("git/ref/tags/"):
            return {"object": {"type": "commit", "sha": self.ref_sha}}
        if method == "POST":
            lane = "guest" if ci.GUEST in path else "host"
            ensure(bool(self.saved), "dispatch must first publish a journal")
            saved_run = self.saved[-1][lane]
            ensure(saved_run is not None and saved_run["phase"] == "intent",
                   "dispatch intent must be durable before the network call")
            if self.dispatch_error:
                raise self.dispatch_error
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
              patch.object(ci.GitHub, "request", side_effect=self.request)):
            return ci.advance(ROOT, self.state, self.save)

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
        "fanout_token": guest["token"] if guest else "", "cold": True}},
        "guest dispatch must use the immutable tag, explicit cold policy and recovery token")
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
    for key, value in (("head_sha", "b" * 40), ("path", ".github/workflows/another.yml")):
        fake = FakeGitHub(_state())
        fake.host[key] = value
        _refuses(fake.advance, "host must test the exact revision with the intended workflow")
        ensure(not fake.posts(), "wrong revision or workflow cannot dispatch guest")


def _host_dispatch() -> None:
    fake = FakeGitHub(_state())
    fake.host_runs = [_run(head_sha="b" * 40), _run(event="pull_request")]
    ensure(not fake.advance(), "manual host dispatch is initially pending")
    posts = fake.posts()
    ensure(len(posts) == 1 and ci.HOST in posts[0][1],
           "start Host CI when no exact suitable run exists")
    ensure(fake.state["guest"] is None, "host dispatch supplies no verdict")
    ensure(fake.advance(), "the next advance can accept the completed host run")


def _moved_tag() -> None:
    fake = FakeGitHub(_state())
    fake.ref_sha = "b" * 40
    _refuses(fake.advance, "changed remote tags must stop the handoff")
    ensure(not fake.posts(), "changed tag must stop all dispatch")


def _guest_interrupt_recovery() -> None:
    fake = FakeGitHub(_state())
    fake.dispatch_error = ci.APIError(None)
    _refuses(fake.advance, "transport failure must report ambiguity")
    guest = fake.state["guest"]
    ensure(guest is not None and guest["phase"] == "intent", "preserve ambiguous intent")
    ensure(fake.saved[-1]["guest"] == guest, "intent is recoverable from the saved journal")
    token = guest["token"] if guest else "missing"
    fake.dispatch_error = None
    fake.guest_runs = [_run(20, event="workflow_dispatch", display_title="fanout:" + token,
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
        guest = fake.state["guest"]
        token = guest["token"] if guest else "missing"
        fake.guest_runs = [_run(number, event="workflow_dispatch", display_title="fanout:" + token)
                           for number in range(20, 20 + count)]
        fake.dispatch_error = None
        _refuses(fake.advance, "ambiguous identity must not authorize a second dispatch")
        ensure(len(fake.posts()) == 1, "only the original request may have started guest")


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
    host = fake.state["host"]
    token = host["token"] if host else "missing"
    fake.host_runs = [_run(event="workflow_dispatch", display_title="fanout:" + token)]
    fake.dispatch_error = None
    ensure(fake.advance(), "recovered host may establish evidence and dispatch guest")
    ensure(sum(ci.HOST in path for _, path, _ in fake.posts()) == 1,
           "interrupted host dispatch must not duplicate")


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
                       ("ref", "main"), ("repository", "github.com/example/repo")):
        state: dict[str, object] = dict(_state())
        state[key] = value
        _refuses(lambda state=state: ci.validate_state(state), f"invalid {key} must be refused")
    fake = FakeGitHub(_state())
    ensure(fake.advance(), "fixture must complete its hosted handoff")
    fake.state["host"] = None
    _refuses(fake.advance, "guest state without passing host evidence must be refused")


def _transport_contract() -> None:
    with (patch.dict(os.environ, {"GH_TOKEN": "fixture-credential"}, clear=True),
          patch.object(urllib.request, "build_opener") as build):
        response = build.return_value.open.return_value.__enter__.return_value
        response.read.return_value = json.dumps({"workflow_run_id": 42}).encode()
        response.headers.get.return_value = "request-receipt"
        client = ci.GitHub(ROOT, REPO)
        result = client.request("POST", "actions/workflows/guest-gates.yml/dispatches", {"ref": "tag"})
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


def cases() -> list[Case]:
    return [Case("successful-handoff", _successful_handoff),
            Case("host-pending", _host_pending), Case("host-failure", _host_failure),
            Case("host-aggregate-evidence", _host_aggregate_evidence),
            Case("host-revision-binding", _host_revision_binding),
            Case("host-dispatch", _host_dispatch), Case("moved-tag", _moved_tag),
            Case("guest-interrupt-recovery", _guest_interrupt_recovery),
            Case("ambiguous-recovery-never-reposts", _ambiguous_recovery_never_reposts),
            Case("rejected-dispatch-retry", _rejected_dispatch_can_retry),
            Case("host-interrupt-recovery", _host_interrupt_recovery),
            Case("remote-validation", _remote_validation), Case("state-validation", _state_validation),
            Case("transport-contract", _transport_contract)]
