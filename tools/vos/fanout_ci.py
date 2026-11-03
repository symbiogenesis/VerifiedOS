# SPDX-License-Identifier: Apache-2.0
"""Historical CI journal validation and shared GitHub request transport.

Local fanout completion reads historical records without advancing them. The
request client remains available to separately invoked hosted tools; no batch
orchestration, polling or waiting lives here.
"""

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import NotRequired, TypedDict, cast, override

from vos import ci_scope

HOST = "host-gates.yml"
GUEST = "guest-gates.yml"
# host-gates.yml names each aggregate job for its platform, never for its runner
# image, so an image move leaves this set and the evidence it accepts unchanged.
HOST_JOBS = {"host-gates (Ubuntu)", "host-gates (Windows)"}
API_VERSION = "2026-03-10"


class RunState(TypedDict):
    workflow: str
    revision: str
    # A record from when run titles carried a recovery token keeps that token;
    # later records keep the time their dispatch intent reached disk.
    token: NotRequired[str]
    requested: NotRequired[str]
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
    # The commit Guest CI's proofs lane reads beside the revision, forwarded as its
    # `reading_base` input; a record without the key names none.
    reading_base: NotRequired[str]
    # Omitted in journals written before changed-path selection.
    selection: NotRequired[ci_scope.Selection]
    full_ci: NotRequired[bool]
    guest_omitted: NotRequired[bool]
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


def new_state(repository: str, ref: str, revision: str, cold: bool,
              reading_base: str | None = None, *,
              selection: ci_scope.Selection | None = None, full_ci: bool = False) -> CIState:
    state: CIState = {"repository": repository, "ref": ref, "revision": revision,
                      "cold": cold, "host": None, "guest": None}
    if reading_base is not None:
        state["reading_base"] = reading_base
    if selection is not None:
        state["selection"] = selection
    if full_ci:
        state["full_ci"] = True
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


def _instant(value: object) -> datetime:
    try:
        moment = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        moment = None
    if moment is None or moment.tzinfo is None:
        raise CIError("hosted evidence has no zoned timestamp")
    return moment


def validate_state(value: object) -> CIState:
    record = _object(value)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", _string(record, "repository")):
        raise CIError("invalid GitHub repository identity")
    revision = _string(record, "revision")
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise CIError("hosted validation needs a full lowercase commit SHA")
    ref = _string(record, "ref")
    if ref != "main":
        raise CIError("hosted validation publishes and dispatches only main; initialize a new main batch")
    if type(record.get("cold")) is not bool:
        raise CIError("hosted validation needs an explicit cold boolean")
    for key in ("full_ci", "guest_omitted"):
        if key in record and type(record[key]) is not bool:
            raise CIError(f"hosted validation needs a boolean {key}")
    if "selection" in record:
        try:
            selection = ci_scope.validate_selection(record["selection"], revision)
        except ValueError as error:
            raise CIError(f"invalid frozen CI selection: {error}") from error
        if ((record["cold"] or record.get("reading_base") is not None or record.get("full_ci"))
                and selection["guest_lanes"] != list(ci_scope.ALL_GUEST_LANES)):
            raise CIError("cold, full CI and proof reading require every guest lane")
        if record.get("full_ci") and not (selection["host_full"] and selection["model_hooks"]):
            raise CIError("full CI requires every host check and model hooks")
    # Guest CI's dispatch check refuses any other reading base before checked-out code runs.
    if "reading_base" in record:
        base = _string(record, "reading_base")
        if not re.fullmatch(r"[0-9a-f]{40}", base) or base == revision:
            raise CIError("a reading base must be a full lowercase commit SHA other than "
                          "the revision")
    for lane, workflow in (("host", HOST), ("guest", GUEST)):
        if lane not in record:
            raise CIError(f"hosted validation is missing {lane} state")
        if record[lane] is None:
            continue
        run = _object(record[lane])
        if run.get("workflow") != workflow or run.get("revision") != revision:
            raise CIError("hosted evidence belongs to another workflow or revision")
        phase = run.get("phase")
        if not isinstance(phase, str) or phase not in {"intent", "accepted", "observed", "rejected"}:
            raise CIError("hosted evidence has an unknown dispatch phase")
        for key in ("url", "status"):
            _string(run, key)
        if "token" in run:
            _string(run, "token")
        if "requested" in run:
            _instant(run["requested"])
        for key in ("conclusion", "request_id"):
            if key not in run or (run[key] is not None and not isinstance(run[key], str)):
                raise CIError(f"invalid hosted evidence {key}")
        if "run_id" not in run:
            raise CIError("hosted evidence is missing its run identifier field")
        if phase in {"accepted", "observed"} and run["run_id"] is None:
            raise CIError("accepted or observed hosted evidence needs a run identifier")
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
        if (host.get("phase") != "observed" or host.get("status") != "completed"
                or host.get("conclusion") != "success"
                or host.get("jobs") != dict.fromkeys(HOST_JOBS, "success")):
            raise CIError("guest dispatch state requires passing evidence from both host platforms")
    if record.get("guest_omitted"):
        selection = record.get("selection")
        host = _object(record["host"])
        if (selection is None or _object(selection).get("guest_lanes") != []
                or record["guest"] is not None or host.get("phase") != "observed"
                or host.get("status") != "completed" or host.get("conclusion") != "success"
                or host.get("jobs") != dict.fromkeys(HOST_JOBS, "success")):
            raise CIError("omitted guest lanes need a frozen empty selection and passing Host CI")
    return cast(CIState, value)


def _token(root: Path, repo: str) -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if bool(token):
        return token
    environment = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never")
    try:
        done = subprocess.run(["git", "-C", str(root), "credential", "fill"],
                              input=f"protocol=https\nhost=github.com\npath={repo}.git\n\n",
                              capture_output=True, text=True, check=False, timeout=30,
                              env=environment)
    except OSError, subprocess.TimeoutExpired:
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
        except OSError, ValueError:
            raise APIError(None) from None
