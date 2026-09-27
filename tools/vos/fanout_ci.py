# SPDX-License-Identifier: Apache-2.0
"""Resumable hosted validation for a settled fan-out revision.

The caller publishes a lightweight tag, owns the journal lock and atomically saves
the enclosing batch whenever requested. A dispatch intent reaches disk before the
POST. An interrupted POST is recovered by its unique workflow title, never retried
on the assumption that a missing response means GitHub did not start a run.
"""

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict, cast, override

HOST = "host-gates.yml"
GUEST = "guest-gates.yml"
HOST_JOBS = {"host-gates (ubuntu-latest)", "host-gates (windows-latest)"}
API_VERSION = "2026-03-10"


class RunState(TypedDict):
    workflow: str
    revision: str
    token: str
    phase: str
    run_id: int | None
    url: str
    status: str
    conclusion: str | None
    request_id: str | None
    jobs: dict[str, str]


class CIState(TypedDict):
    repository: str
    ref: str
    revision: str
    cold: bool
    host: RunState | None
    guest: RunState | None


class CIError(RuntimeError):
    """Hosted evidence is missing, failed, malformed or ambiguous."""


class APIError(CIError):
    def __init__(self, status: int | None) -> None:
        self.status = status
        detail = f"HTTP {status}" if status is not None else "transport failure"
        super().__init__(f"GitHub Actions API {detail}; credentials and response bodies are omitted")


def repository(root: Path, remote: str) -> str:
    """Resolve only an explicit github.com remote; never send credentials elsewhere."""
    done: subprocess.CompletedProcess[str] = subprocess.run(
        ["git", "-C", str(root), "remote", "get-url", remote],
        capture_output=True, text=True, check=False, timeout=30)
    if done.returncode:
        raise CIError("cannot resolve publication remote")
    url = done.stdout.strip()
    match = re.fullmatch(r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
                         r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?/?", url)
    if match is None:
        raise CIError("publication remote must be an ordinary github.com HTTPS or SSH URL")
    return str(match.group(1))


def new_state(repository: str, ref: str, revision: str, cold: bool) -> CIState:
    state: CIState = {"repository": repository, "ref": ref, "revision": revision,
                      "cold": cold, "host": None, "guest": None}
    return validate_state(state)


def _object(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise CIError("GitHub evidence must be a JSON object")
    return cast(dict[str, object], value)


def _string(record: dict[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        raise CIError(f"GitHub evidence has no string {key}")
    return value


def _run_id(value: object) -> int:
    if type(value) is not int or value <= 0:
        raise CIError("GitHub evidence has no positive run identifier")
    return value


def validate_state(value: object) -> CIState:
    record = _object(value)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", _string(record, "repository")):
        raise CIError("invalid GitHub repository identity")
    revision = _string(record, "revision")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise CIError("hosted validation needs a full lowercase commit SHA")
    ref = _string(record, "ref")
    if (not ref.startswith("fanout/") or not ref.endswith("/" + revision)
            or not re.fullmatch(r"[A-Za-z0-9_./-]+", ref) or ".." in ref or "//" in ref):
        raise CIError("hosted validation needs its immutable fanout/<batch>/<SHA> tag")
    if type(record.get("cold")) is not bool:
        raise CIError("hosted validation needs an explicit cold boolean")
    for lane, workflow in (("host", HOST), ("guest", GUEST)):
        if lane not in record:
            raise CIError(f"hosted validation is missing {lane} state")
        if record[lane] is None:
            continue
        run = _object(record[lane])
        if run.get("workflow") != workflow or run.get("revision") != revision:
            raise CIError("hosted evidence belongs to another workflow or revision")
        if run.get("phase") not in {"intent", "accepted", "observed", "rejected"}:
            raise CIError("hosted evidence has an unknown dispatch phase")
        for key in ("token", "url", "status"):
            _string(run, key)
        for key in ("conclusion", "request_id"):
            if key not in run or (run[key] is not None and not isinstance(run[key], str)):
                raise CIError(f"invalid hosted evidence {key}")
        if "run_id" not in run:
            raise CIError("hosted evidence is missing its run identifier field")
        if run["run_id"] is not None:
            _run_id(run["run_id"])
            expected = f"https://github.com/{record['repository']}/actions/runs/{run['run_id']}"
            if run["url"] != expected:
                raise CIError("hosted run URL disagrees with its repository and identifier")
        jobs = _object(run.get("jobs"))
        if not all(isinstance(item, str) for item in jobs.values()):
            raise CIError("invalid hosted job conclusions")
    if record["guest"] is not None and _object(record["guest"]).get("phase") == "accepted":
        host = _object(record["host"])
        if (host.get("status") != "completed" or host.get("conclusion") != "success"
                or host.get("jobs") != dict.fromkeys(HOST_JOBS, "success")):
            raise CIError("guest dispatch state requires passing evidence from both host platforms")
    return cast(CIState, value)


def _token(root: Path, repo: str) -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    environment = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    try:
        done = subprocess.run(["git", "-C", str(root), "credential", "fill"],
                              input=f"protocol=https\nhost=github.com\npath={repo}.git\n\n",
                              capture_output=True, text=True, check=False, timeout=30,
                              env=environment)
    except (OSError, subprocess.TimeoutExpired):
        raise CIError("cannot read GitHub credentials; set GH_TOKEN or GITHUB_TOKEN") from None
    if done.returncode == 0:
        for line in done.stdout.splitlines():
            if line.startswith("password=") and line.removeprefix("password="):
                return line.removeprefix("password=")
    raise CIError("GitHub credentials unavailable; set GH_TOKEN or GITHUB_TOKEN")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    @override
    def redirect_request(self, req: urllib.request.Request, fp: object, code: int,
                         msg: str, headers: object, newurl: str) -> None:
        # A redirect must not send the Authorization header to another origin.
        return None


class GitHub:
    def __init__(self, root: Path, repo: str) -> None:
        self.repo = repo
        self._token = _token(root, repo)

    def request(self, method: str, path: str,
                payload: dict[str, object] | None = None) -> dict[str, object]:
        url = f"https://api.github.com/repos/{self.repo}/{path}"
        request = urllib.request.Request(
            url, method=method,
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers={"Accept": "application/vnd.github+json", "Content-Type": "application/json",
                     "Authorization": f"Bearer {self._token}",
                     "X-GitHub-Api-Version": API_VERSION, "User-Agent": "VerifiedOS-fanout"})
        try:
            # All URLs use a fixed HTTPS origin and repository-relative paths.
            with urllib.request.build_opener(_NoRedirect).open(request, timeout=30) as response:
                raw = response.read()
                result = _object(json.loads(raw)) if raw else {}
                result["_request_id"] = response.headers.get("X-GitHub-Request-Id")
                return result
        except urllib.error.HTTPError as error:
            raise APIError(error.code) from None
        except (OSError, ValueError):
            raise APIError(None) from None

    def runs(self, workflow: str, revision: str) -> list[dict[str, object]]:
        query = urllib.parse.urlencode({"head_sha": revision, "per_page": 100})
        response = self.request("GET", f"actions/workflows/{workflow}/runs?{query}")
        runs = response.get("workflow_runs")
        if not isinstance(runs, list):
            raise CIError("GitHub did not return workflow runs")
        return [_object(run) for run in runs]

    def verify_ref(self, state: CIState) -> None:
        response = self.request("GET", "git/ref/tags/" + urllib.parse.quote(state["ref"], safe=""))
        target = _object(response.get("object"))
        if target.get("type") != "commit" or target.get("sha") != state["revision"]:
            raise CIError("published fan-out tag no longer identifies the settled revision")


def _blank(workflow: str, revision: str) -> RunState:
    return {"workflow": workflow, "revision": revision, "token": uuid.uuid4().hex,
            "phase": "intent", "run_id": None, "url": "", "status": "pending",
            "conclusion": None, "request_id": None, "jobs": {}}


def _identity(state: CIState, record: RunState, run: dict[str, object]) -> None:
    if run.get("head_sha") != state["revision"]:
        raise CIError("GitHub workflow run tested a different revision")
    if run.get("event") not in {"push", "workflow_dispatch"}:
        raise CIError("pull-request or scheduled runs cannot establish this publication's host evidence")
    if run.get("path") != ".github/workflows/" + record["workflow"]:
        raise CIError("GitHub workflow run used a different workflow file")
    record["run_id"] = _run_id(run.get("id"))
    record["url"] = f"https://github.com/{state['repository']}/actions/runs/{record['run_id']}"


def _recover(client: GitHub, state: CIState, record: RunState,
             save: Callable[[], None]) -> None:
    # One identity lookup resolves interrupted requests. A guest's verdict is never
    # read or copied, even when it happens to be included in this API response.
    matches = [run for run in client.runs(record["workflow"], state["revision"])
               if run.get("display_title") == "fanout:" + record["token"]
               and run.get("head_sha") == state["revision"]
               and run.get("event") == "workflow_dispatch"]
    if len(matches) != 1:
        raise CIError("dispatch identity remains ambiguous; no dispatch was repeated. "
                      "Inspect GitHub Actions and retry recovery when the original run is visible")
    _identity(state, record, matches[0])
    record["phase"] = "accepted"
    record["status"] = "pending"
    save()


def _dispatch(client: GitHub, state: CIState, record: RunState,
              save: Callable[[], None]) -> None:
    client.verify_ref(state)
    record["phase"] = "intent"
    save()
    inputs: dict[str, object] = {"fanout_token": record["token"]}
    if record["workflow"] == GUEST:
        # guest-gates owns a mandatory model/proofs matrix; there is no lane filter.
        inputs["cold"] = state["cold"]
    try:
        result = client.request("POST", f"actions/workflows/{record['workflow']}/dispatches",
                                {"ref": state["ref"], "inputs": inputs})
    except APIError as error:
        if error.status in {400, 401, 403, 404, 409, 410, 422, 429}:
            record["phase"] = "rejected"
            record["status"] = f"rejected HTTP {error.status}"
            save()
        raise
    # The current API returns the run ID directly. Older empty responses leave a
    # durable intent requiring identity recovery rather than a duplicate POST.
    record["run_id"] = _run_id(result.get("workflow_run_id"))
    record["url"] = f"https://github.com/{state['repository']}/actions/runs/{record['run_id']}"
    if result.get("html_url") != record["url"]:
        raise CIError("dispatch response returned an unexpected run URL; recover its identity")
    request_id = result.get("_request_id")
    record["request_id"] = request_id if isinstance(request_id, str) else None
    record["phase"] = "accepted"
    record["status"] = "pending"
    save()


def _host_status(client: GitHub, state: CIState, record: RunState,
                 save: Callable[[], None]) -> bool:
    run = client.request("GET", f"actions/runs/{record['run_id']}")
    if run.get("id") != record["run_id"]:
        raise CIError("GitHub returned the wrong workflow run identifier")
    _identity(state, record, run)
    record["phase"] = "observed"
    record["status"] = _string(run, "status")
    conclusion = run.get("conclusion")
    if conclusion is not None and not isinstance(conclusion, str):
        raise CIError("GitHub returned a malformed host conclusion")
    record["conclusion"] = conclusion
    record["jobs"] = {}
    save()
    if record["status"] != "completed":
        return False
    if conclusion != "success":
        raise CIError(f"Host CI did not pass: {conclusion}; {record['url']}")
    jobs: dict[str, str] = {}
    # filter=latest excludes failed jobs from previous attempts of a rerun.
    for page in range(1, 11):
        response = client.request("GET", f"actions/runs/{record['run_id']}/jobs"
                                  f"?filter=latest&per_page=100&page={page}")
        values = response.get("jobs")
        if not isinstance(values, list):
            raise CIError("GitHub did not return host jobs")
        for value in values:
            job = _object(value)
            name = _string(job, "name")
            if name in HOST_JOBS:
                if name in jobs:
                    raise CIError("Host CI returned duplicate aggregate jobs")
                jobs[name] = str(job.get("conclusion")) if job.get("status") == "completed" else "pending"
        if len(values) < 100:
            break
    else:
        raise CIError("Host CI job listing exceeded the bounded pagination limit")
    record["jobs"] = jobs
    save()
    if set(jobs) != HOST_JOBS or any(result != "success" for result in jobs.values()):
        raise CIError("Host CI lacks successful Windows and Ubuntu aggregate jobs")
    return True


def advance(root: Path, state: CIState, save: Callable[[], None]) -> bool:
    """Advance once; False means host pending, True means guest dispatch recorded.

    The caller may repeat pending host steps. Never repeat this function to learn
    a guest verdict: after accepted dispatch it returns without contacting GitHub.
    """
    validate_state(state)
    guest = state["guest"]
    if guest is not None and guest["phase"] == "accepted" and guest["run_id"] is not None:
        return True
    client = GitHub(root, state["repository"])
    client.verify_ref(state)
    host = state["host"]
    if host is None:
        runs = [run for run in client.runs(HOST, state["revision"])
                if run.get("head_sha") == state["revision"]
                and run.get("event") in {"push", "workflow_dispatch"}]
        host = _blank(HOST, state["revision"])
        state["host"] = host
        if runs:
            selected = max(runs, key=lambda run: _run_id(run.get("id")))
            _identity(state, host, selected)
            host["phase"] = "accepted"
            save()
        else:
            _dispatch(client, state, host, save)
            return False
    elif host["phase"] == "rejected":
        _dispatch(client, state, host, save)
        return False
    elif host["phase"] == "intent" or host["run_id"] is None:
        _recover(client, state, host, save)
    if not _host_status(client, state, host, save):
        return False
    if guest is None:
        guest = _blank(GUEST, state["revision"])
        state["guest"] = guest
        _dispatch(client, state, guest, save)
    elif guest["phase"] == "rejected":
        _dispatch(client, state, guest, save)
    else:
        _recover(client, state, guest, save)
    return True
