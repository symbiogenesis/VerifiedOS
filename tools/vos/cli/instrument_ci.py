# SPDX-License-Identifier: Apache-2.0
"""Dispatch the instrument switch route, and read one of its runs back.

    python tools/run.py instrument-ci dispatch --revision SHA [--base-revision SHA]
                                               [--build install|recipe] [--sample N]
                                               [--title TEXT] [--ref main]
    python tools/run.py instrument-ci dispatch --resume NONCE
    python tools/run.py instrument-ci read --run ID [--parent REV]
                                           [--closing COMMIT --closing-path PATH ...]

[instrument-switches.yml](../../../.github/workflows/instrument-switches.yml) builds and
checks QuickChick's switch on GitHub-hosted runners, and
[its contract](../../ci/README.md#instrument-switch-route) states what a run decides.
`fanout` never runs this command, and nothing here dispatches Host or Guest CI.

**`dispatch` decides nothing about what it sends.** Every refusal is the plan job's,
read from the run's `plan.json`, so a dispatch this command would have refused locally
could not hide a plan that accepts it. It puts a nonce in the run's title, journals
its intent under that nonce before its one POST, and recovers an interrupted dispatch
by finding the run whose title carries the nonce, never by posting again.

**`read` trusts nothing it downloads.** Each artifact's redirect is followed without
credentials, saved under `out/instrument-ci/<run id>/` and extracted only there, a
member whose path is absolute or climbs out of its directory, two members landing on one
another, a member that cannot be read or an archive larger than the route's bound
refusing it; each member is held to the staging allowlist and each
recorded input to the run. It re-joins the artifacts and holds the result to the run's
own report, prints the verdict with the run's URL, tested revisions, runner images and
step durations and peaks, and says whether the run is closing evidence: whether the
route inputs at the candidate's tested revision, and the route's own files at the
dispatching commit, are unchanged at the closing parent, and, given the closing commit,
whether its own diff touches only the tracked lock at the export's SHA-256 and the paths
the owning item's closing landing names.
"""

import argparse
import ast
import hashlib
import io
import json
import re
import secrets
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Protocol, cast, override

from ci import instrument_route as route
from vos import cli, fanout_ci, receipts
from vos.corpus import find_root

WORKFLOW_FILE = "instrument-switches.yml"
WORKFLOW_NAME = WORKFLOW_FILE.removesuffix(".yml")
OUT = "out/instrument-ci"
DISPATCHES = "dispatches"
NONCE_RE = re.compile(r"[0-9a-f]{16}")
# GitHub creates a dispatched run after its intent reaches disk; recovery also accepts
# a run stamped this much earlier, in case the local clock runs ahead.
CLOCK_SKEW = timedelta(seconds=60)
# Statuses with which GitHub refused a dispatch outright, so no run exists for it.
REJECTED = frozenset({400, 401, 403, 404, 409, 410, 422, 429})
# The top-level packages under tools/ whose imports the closure follows.
PACKAGES: tuple[str, ...] = ("vos", "ci")


class Client(Protocol):
    """What this command asks of GitHub: one JSON request, and an artifact's redirect."""

    def request(self, method: str, path: str,
                payload: dict[str, object] | None = None) -> dict[str, object]: ...

    def location(self, path: str) -> str: ...


class _Refused(urllib.request.HTTPRedirectHandler):
    @override
    def redirect_request(self, req: urllib.request.Request, fp: object, code: int,
                         msg: str, headers: object, newurl: str) -> None:
        # The redirect is read, never followed, so the token stays with GitHub's API.
        return None


class GitHub(fanout_ci.GitHub):
    """Fanout's REST client, with the one read it lacks: where an artifact's download
    redirects to, read from the authenticated response and never followed with it."""

    def location(self, path: str) -> str:
        request = urllib.request.Request(
            f"https://api.github.com/repos/{self.repo}/{path}", method="GET",
            headers={"Accept": "application/vnd.github+json",
                     "Authorization": f"Bearer {self._token}",
                     "X-GitHub-Api-Version": fanout_ci.API_VERSION,
                     "User-Agent": "VerifiedOS-instrument-ci"})
        try:
            with urllib.request.build_opener(_Refused).open(request, timeout=30):
                pass
        except urllib.error.HTTPError as error:
            target = error.headers.get("Location") if error.code in (301, 302, 303, 307, 308) else None
            if target:
                return str(target)
            raise fanout_ci.APIError(error.code) from None
        except OSError:
            raise fanout_ci.APIError(None) from None
        raise fanout_ci.CIError("GitHub answered an artifact download without a redirect")


def fetch(url: str, limit: int) -> bytes:
    """An artifact's bytes from the address its redirect named, fetched with no
    credentials and refused past `limit` bytes."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise fanout_ci.CIError("an artifact redirect must name an https address")
    # An https address only, carrying no credential of ours.
    request = urllib.request.Request(url, headers={"User-Agent": "VerifiedOS-instrument-ci"})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
            data = bytes(response.read(limit + 1))
    except (OSError, ValueError):
        raise fanout_ci.CIError("the artifact download failed; no credential was sent") from None
    if len(data) > limit:
        raise fanout_ci.CIError(f"the artifact is larger than its {limit}-byte bound")
    return data


# ------------------------------------------------------------------------- dispatching


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _instant(value: object) -> datetime | None:
    try:
        moment = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None
    return moment if moment is not None and moment.tzinfo is not None else None


def title_for(nonce: str, title: str, revision: str, ref: str) -> str:
    """The title input: the nonce first, so the run's title names it, then the caller's
    title or the revision asked for."""
    return f"ic-{nonce} {title or revision or ref}".strip()


def display_title(title: str) -> str:
    """The run title GitHub shows for a title input, as the workflow's run-name forms it."""
    return f"{WORKFLOW_NAME}:{title}"


def dispatch_inputs(args: argparse.Namespace, nonce: str) -> dict[str, str]:
    """The inputs sent, exactly as given: every one the caller named, and the title."""
    given = (("revision", args.revision), ("base_revision", args.base_revision),
             ("build", args.build), ("sample", args.sample))
    found: dict[str, str] = {key: value for key, value in given if value is not None}
    found["title"] = title_for(nonce, args.title or "", args.revision or "", args.ref)
    return found


def journal_dir(root: Path) -> Path:
    return root / OUT / DISPATCHES


def pending(root: Path) -> list[dict[str, object]]:
    """Every journalled dispatch whose POST was sent and whose run is not yet known."""
    found: list[dict[str, object]] = []
    directory = journal_dir(root)
    for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
        record = route.load_json(path)
        if record is not None and record.get("phase") == "intent":
            found.append(record)
    return found


def _save(root: Path, record: dict[str, object]) -> None:
    receipts.write(journal_dir(root) / f"{record['nonce']}.json", record)


def _run_url(repo: str, run_id: int) -> str:
    return f"https://github.com/{repo}/actions/runs/{run_id}"


def post(client: Client, root: Path, repo: str, record: dict[str, object]) -> dict[str, object]:
    """Journal the intent, then post the one dispatch it names."""
    record["phase"] = "intent"
    record["requested"] = _now()
    _save(root, record)
    try:
        result = client.request("POST", f"actions/workflows/{WORKFLOW_FILE}/dispatches",
                                {"ref": record["ref"], "inputs": record["inputs"]})
    except fanout_ci.APIError as error:
        if error.status in REJECTED:
            record["phase"] = "rejected"
            record["status"] = f"rejected HTTP {error.status}"
            _save(root, record)
        raise
    run_id = result.get("workflow_run_id")
    if type(run_id) is not int or run_id <= 0:
        raise fanout_ci.CIError("the dispatch response named no run; recover it with --resume "
                                f"{record['nonce']}")
    record |= {"phase": "accepted", "run_id": run_id, "url": _run_url(repo, run_id),
               "status": "dispatched"}
    _save(root, record)
    return record


def recover(client: Client, root: Path, repo: str, record: dict[str, object]) -> dict[str, object]:
    """Find the run an interrupted dispatch started by the nonce in its title, among the
    runs created after its intent, and never post again."""
    if record.get("phase") != "intent":
        return record
    earliest = _instant(record.get("requested"))
    if earliest is None:
        raise fanout_ci.CIError("the journalled intent has no zoned timestamp")
    earliest -= CLOCK_SKEW
    query = urllib.parse.urlencode({"event": "workflow_dispatch", "per_page": 100})
    response = client.request("GET", f"actions/workflows/{WORKFLOW_FILE}/runs?{query}")
    runs = response.get("workflow_runs")
    if not isinstance(runs, list):
        raise fanout_ci.CIError("GitHub did not return workflow runs")
    marker = display_title(f"ic-{record['nonce']} ")
    matches: list[dict[str, object]] = []
    for raw in cast("list[object]", runs):
        run = route.as_object(raw)
        created = _instant(run.get("created_at"))
        title = run.get("display_title")
        if (isinstance(title, str) and (title + " ").startswith(marker)
                and run.get("path") == f".github/workflows/{WORKFLOW_FILE}"
                and created is not None and created >= earliest):
            matches.append(run)
    if len(matches) != 1:
        raise fanout_ci.CIError(f"{len(matches)} runs carry nonce {record['nonce']}; no dispatch "
                                "was repeated. Retry --resume once the run is visible")
    run_id = matches[0].get("id")
    if type(run_id) is not int or run_id <= 0:
        raise fanout_ci.CIError("the recovered run has no identifier")
    record |= {"phase": "accepted", "run_id": run_id, "url": _run_url(repo, run_id),
               "status": "recovered"}
    _save(root, record)
    return record


def cmd_dispatch(args: argparse.Namespace) -> int:
    root = find_root()
    repo = fanout_ci.repository(root, args.remote)
    client = GitHub(root, repo)
    if args.resume:
        path = journal_dir(root) / f"{args.resume}.json"
        record = route.load_json(path) if NONCE_RE.fullmatch(args.resume) else None
        if record is None:
            print(f"FAIL no journalled dispatch {args.resume!r} under {journal_dir(root)}")
            return 1
        try:
            record = recover(client, root, repo, record)
        except fanout_ci.CIError as error:
            print(f"FAIL {error}")
            return 1
        print(f"{record['phase']} {record.get('url') or ''} (nonce {record['nonce']})")
        return 0 if record["phase"] == "accepted" else 1
    if unresolved := pending(root):
        print("FAIL an earlier dispatch's run is not yet known, so no dispatch is sent: "
              + ", ".join(f"run.py instrument-ci dispatch --resume {item['nonce']}"
                          for item in unresolved))
        return 1
    nonce = secrets.token_hex(8)
    record: dict[str, object] = {"schema": 1, "nonce": nonce, "workflow": WORKFLOW_FILE,
                                 "repository": repo, "ref": args.ref,
                                 "inputs": dispatch_inputs(args, nonce), "run_id": None,
                                 "url": "", "status": "pending"}
    try:
        record = post(client, root, repo, record)
    except fanout_ci.CIError as error:
        print(f"FAIL {error}; the intent is journalled as nonce {nonce}")
        return 1
    print(f"dispatched {record['url']} (nonce {nonce}, inputs {json.dumps(record['inputs'])})")
    return 0


# ---------------------------------------------------------------------------- reading


def member_refusal(name: str) -> str | None:
    """Why an archive member's path may not be extracted: absolute, or climbing out."""
    posix = name.replace("\\", "/")
    if not posix or posix.startswith("/") or re.match(r"^[A-Za-z]:", posix):
        return f"member {name!r} has an absolute path"
    if ".." in PurePosixPath(posix).parts:
        return f"member {name!r} climbs out of its directory"
    return None


def collisions(names: Sequence[str]) -> list[str]:
    """Members that would land on one another: two names equal but for case, which one
    file holds on a case-insensitive filesystem, and a name that is another's directory."""
    found: list[str] = []
    seen: dict[str, str] = {}
    for name in names:
        folded = name.casefold()
        if folded in seen:
            found.append(f"members {seen[folded]!r} and {name!r} name one file")
        else:
            seen[folded] = name
    for name in names:
        parts = PurePosixPath(name.casefold()).parts
        for depth in range(1, len(parts)):
            prefix = "/".join(parts[:depth])
            if prefix in seen:
                found.append(f"member {seen[prefix]!r} is the directory of member {name!r}")
    return found


# What reading a member raises where its archive is malformed: a bad CRC, an unsupported
# compression, an encrypted member, or a truncated stream.
_UNREADABLE = (zipfile.BadZipFile, NotImplementedError, RuntimeError, ValueError, EOFError,
               OSError)


def extract(data: bytes, target: Path, limit: int = route.ARCHIVE_LIMIT) -> list[str]:
    """Extract one artifact's archive into `target` alone, or refuse it whole: a member
    whose path is absolute or climbs out, two members that would land on one another,
    members totalling more than `limit` bytes, a member that cannot be read, or one
    outside the staging allowlist or carrying a Wasm or ELF header or a NUL byte. The
    members are written beside `target` and moved into place whole, so a refused archive
    leaves nothing extracted."""
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except (zipfile.BadZipFile, zipfile.LargeZipFile, ValueError, EOFError):
        return ["the artifact is not a zip archive"]
    with archive:
        members = [info for info in archive.infolist() if not info.is_dir()]
        refusals = [refusal for info in members
                    if (refusal := member_refusal(info.filename)) is not None]
        refusals += collisions([info.filename.replace("\\", "/") for info in members])
        total = sum(info.file_size for info in members)
        if total > limit:
            refusals.append(f"its members hold {total} bytes, over the {limit}-byte bound")
        if refusals:
            return refusals
        contents: list[tuple[str, bytes]] = []
        for info in members:
            name = info.filename.replace("\\", "/")
            try:
                body = archive.read(info)
            except _UNREADABLE as error:
                refusals.append(f"member {name} cannot be read: {error}")
                continue
            why = route.name_refusal(name) or route.content_refusal(body)
            if why is not None:
                refusals.append(f"member {name} is outside the allowlist: {why}")
            contents.append((name, body))
    if refusals:
        return refusals
    partial = target.with_name(f"{target.name}.partial")
    if partial.exists():
        shutil.rmtree(partial)
    try:
        for name, body in contents:
            path = partial.joinpath(*PurePosixPath(name).parts)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(body)
    except OSError as error:
        shutil.rmtree(partial, ignore_errors=True)
        return [f"the archive could not be extracted: {error}"]
    if target.exists():
        shutil.rmtree(target)
    partial.mkdir(parents=True, exist_ok=True)
    partial.rename(target)
    return []


def _pages(client: Client, path: str, key: str) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for page in range(1, 11):
        separator = "&" if "?" in path else "?"
        response = client.request("GET", f"{path}{separator}per_page=100&page={page}")
        values = response.get(key)
        if not isinstance(values, list):
            raise fanout_ci.CIError(f"GitHub returned no {key}")
        found += [route.as_object(value) for value in cast("list[object]", values)]
        if len(values) < 100:
            return found
    raise fanout_ci.CIError(f"the run's {key} exceed the bounded pagination")


def needs_from_jobs(jobs: Sequence[dict[str, object]]) -> dict[str, object]:
    """The join's `needs` as GitHub would hand it over, from the jobs' conclusions: a
    matrix job fails where one of its runs failed, is cancelled where one was, and
    succeeds only where every run did."""
    grouped: dict[str, list[str]] = {}
    for job in jobs:
        name = str(job.get("name", "")).split(" (", 1)[0]
        conclusion = job.get("conclusion")
        grouped.setdefault(name, []).append(
            conclusion if isinstance(conclusion, str) else str(job.get("status")))
    found: dict[str, object] = {}
    for name, results in grouped.items():
        if "failure" in results or "timed_out" in results:
            result = "failure"
        elif "cancelled" in results:
            result = "cancelled"
        elif all(item == "success" for item in results):
            result = "success"
        else:
            result = "skipped"
        found[name] = {"result": result}
    return found


def _git(checkout: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(("git", "-C", str(checkout), *args), capture_output=True,
                          check=False, timeout=120)


def _git_text(checkout: Path, *args: str) -> str:
    done = _git(checkout, *args)
    if done.returncode != 0:
        raise fanout_ci.CIError(f"git {' '.join(args)} failed: "
                                f"{done.stderr.decode('utf-8', 'replace').strip()}")
    return done.stdout.decode("utf-8", "replace")


def _module_of(path: str) -> tuple[str, bool]:
    """A tools/ path's module name, and whether it is a package's initializer."""
    parts = PurePosixPath(path).relative_to("tools").with_suffix("").parts
    if parts[-1] == "__init__":
        return ".".join(parts[:-1]), True
    return ".".join(parts), False


def _module_files(module: str, tree: set[str]) -> list[str]:
    """The files importing `module` runs: each enclosing package's initializer and the
    module's own file, as far as the tree carries them."""
    parts = module.split(".")
    files = [f"tools/{'/'.join(parts[:depth])}/__init__.py" for depth in range(1, len(parts))]
    own = f"tools/{'/'.join(parts)}"
    files += [f"{own}.py", f"{own}/__init__.py"]
    return [path for path in files if path in tree]


def imports_of(source: str, module: str, package: bool) -> set[str]:
    """Every module under `PACKAGES` a source imports, anywhere in it, a deferred or a
    type-checking import included, which errs toward a larger closure."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = module.split(".") if package else module.split(".")[:-1]
                base = base[:len(base) - (node.level - 1)]
                prefix = ".".join([*base, *([node.module] if node.module else [])])
            else:
                prefix = node.module or ""
            found.add(prefix)
            found.update(f"{prefix}.{alias.name}" for alias in node.names)
    return {name for name in found if name.split(".")[0] in PACKAGES}


def import_closure(checkout: Path, revision: str, roots: Iterable[str]) -> set[str]:
    """The files of the transitive `vos` and `ci` import closure of `roots` at a
    revision, read from that revision's sources without running them."""
    tree = set(_git_text(checkout, "ls-tree", "-r", "--name-only", revision, "--", "tools")
               .splitlines())
    seen: set[str] = set()
    pending_files = [path for path in roots if path in tree]
    while pending_files:
        path = pending_files.pop()
        if path in seen:
            continue
        seen.add(path)
        source = _git_text(checkout, "show", f"{revision}:{path}")
        module, package = _module_of(path)
        try:
            names = imports_of(source, module, package)
        except SyntaxError as error:
            raise fanout_ci.CIError(f"{path} at {revision} does not parse: {error}") from None
        for name in names:
            pending_files += [found for found in _module_files(name, tree) if found not in seen]
    return seen


def side_inputs(checkout: Path, revision: str) -> list[str]:
    """The route inputs at a side's revision: those the contract names and the import
    closure of every module the route runs there."""
    return sorted({*route.ROUTE_INPUTS, *import_closure(checkout, revision, route.SIDE_ROOTS)})


def route_files(checkout: Path, revision: str) -> list[str]:
    """The route's own files at the dispatching commit, with their import closure."""
    return sorted({*route.ROUTE_FILES, *import_closure(checkout, revision, route.ROUTE_ROOTS)})


def differing(checkout: Path, left: str, right: str, paths: Sequence[str]) -> list[str]:
    """The paths among `paths` whose bytes differ between two revisions, which is what
    `git diff --quiet left right -- paths` decides."""
    return [line for line in _git_text(checkout, "diff", "--name-only", left, right, "--",
                                       *paths).splitlines() if line]


def closing_refusals(checkout: Path, closing: str, inputs: Sequence[str],
                     allowed: Sequence[str], export_sha256: str | None) -> list[str]:
    """Why a closing commit's own diff refuses the run as its evidence: a route input it
    touches other than the tracked lock, at the export's SHA-256, and the paths the
    owning item's closing landing names. The inputs are those at the tested revision
    and the closing commit's own, so a module a named path newly imports is one."""
    refusals: list[str] = []
    inputs = sorted({*inputs, *side_inputs(checkout, closing)})
    touched = differing(checkout, f"{closing}^1", closing, inputs)
    for path in touched:
        if path == route.LOCK:
            shown = _git(checkout, "show", f"{closing}:{route.LOCK}")
            digest = hashlib.sha256(shown.stdout).hexdigest() if shown.returncode == 0 else None
            if digest is None or digest != export_sha256:
                refusals.append(f"the closing commit's {route.LOCK} has SHA-256 {digest}, not "
                                f"the run's export {export_sha256}")
        elif path not in allowed:
            refusals.append(f"the closing commit touches the route input {path}, which is "
                            "neither the tracked lock nor a path the closing landing names")
    return refusals


def _commit_of(checkout: Path, revision: str) -> str | None:
    """The commit a revision names in the checkout, None where it names none."""
    done = _git(checkout, "rev-parse", "--verify", "--quiet", f"{revision}^{{commit}}")
    found = done.stdout.decode("utf-8", "replace").strip()
    return found if done.returncode == 0 and found else None


def _receipt(directory: Path | None) -> dict[str, object] | None:
    return route.load_json(directory / route.RECEIPT) if directory is not None else None


def input_refusals(run: dict[str, object], run_id: int,
                   plan: dict[str, object] | None) -> list[str]:
    """What makes a run's plan disagree with the run GitHub reports."""
    refusals: list[str] = []
    if run.get("path") != f".github/workflows/{WORKFLOW_FILE}":
        refusals.append(f"run {run_id} is not a run of {WORKFLOW_FILE}")
    if run.get("event") != "workflow_dispatch":
        refusals.append(f"run {run_id} was not dispatched")
    if run.get("status") != "completed":
        refusals.append(f"run {run_id} is {run.get('status')!r}, not completed, so its "
                        "artifacts are not yet all there")
    if plan is None:
        refusals.append("no plan.json was read")
        return refusals
    if plan.get("run_id") != str(run_id):
        refusals.append(f"plan.json names run {plan.get('run_id')!r}, not {run_id}")
    if plan.get("dispatching_commit") != run.get("head_sha"):
        refusals.append(f"plan.json names dispatching commit {plan.get('dispatching_commit')!r}, "
                        f"the run {run.get('head_sha')!r}")
    request = (route.as_object(plan.get("request", {}))
               if isinstance(plan.get("request"), dict) else {})
    shown = request.get("title") or request.get("revision") or run.get("head_sha")
    if run.get("display_title") != display_title(str(shown)):
        refusals.append(f"the run's title {run.get('display_title')!r} is not the one its "
                        f"recorded inputs give, {display_title(str(shown))!r}")
    return refusals


def _durations(report: dict[str, object]) -> list[str]:
    lines: list[str] = []
    for key, raw in route.as_object(report.get("jobs", {})).items():
        job = route.as_object(raw)
        lines.append(f"   {key}: {job.get('verdict')} ({job.get('result')}), tested "
                     f"{job.get('source_revision')}, image {job.get('runner_image')}, "
                     f"{job.get('uname_m')}, opam {job.get('opam_client')}")
        for step, rows in route.as_object(job.get("steps", {})).items():
            row = route.as_object(rows)
            lines.append(f"     {step:<11} {row.get('verdict')}: {row.get('seconds')} s of "
                         f"{row.get('limit_s')}, peak {route.peak_text(row)}")
    return lines


def download(client: Client, run_id: int, base: Path) -> tuple[dict[str, Path], list[str]]:
    """Every artifact of a run saved and extracted under `base`, by name, and every
    refusal that kept one out."""
    found: dict[str, Path] = {}
    refusals: list[str] = []
    # An earlier reading's extraction never stands in for an artifact this one refuses.
    if (base / "artifacts").exists():
        shutil.rmtree(base / "artifacts")
    for artifact in _pages(client, f"actions/runs/{run_id}/artifacts", "artifacts"):
        name = str(artifact.get("name", ""))
        if not route.ARTIFACT_RE.fullmatch(name):
            refusals.append(f"artifact {name!r} is not one the route names")
            continue
        if artifact.get("expired") is True:
            refusals.append(f"artifact {name} has expired")
            continue
        size = artifact.get("size_in_bytes")
        if type(size) is not int or size < 0 or size > route.ARCHIVE_LIMIT:
            refusals.append(f"artifact {name} states {size!r} bytes, outside the route's bound")
            continue
        data = fetch(client.location(f"actions/artifacts/{artifact.get('id')}/zip"),
                     route.ARCHIVE_LIMIT)
        archive = base / f"{name}.zip"
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(data)
        why = extract(data, base / "artifacts" / name)
        if why:
            refusals += [f"artifact {name}: {item}" for item in why]
            continue
        found[name] = base / "artifacts" / name
    return found, refusals


def read_run(client: Client, checkout: Path, run_id: int, *, parent: str | None,
             closing: str | None, closing_paths: Sequence[str]) -> tuple[list[str], bool]:
    """The reading's lines, and whether every record the run left held."""
    run = client.request("GET", f"actions/runs/{run_id}")
    if run.get("id") != run_id:
        raise fanout_ci.CIError("GitHub returned another run")
    jobs = _pages(client, f"actions/runs/{run_id}/jobs?filter=latest", "jobs")
    base = checkout / OUT / str(run_id)
    found, refusals = download(client, run_id, base)
    by_key: dict[str, Path] = {}
    for name, path in found.items():
        matched = route.ARTIFACT_RE.fullmatch(name)
        if matched is not None:
            by_key[matched.group(1)] = path
    plan = route.load_json(by_key["plan"] / route.PLAN) if "plan" in by_key else None
    refusals += input_refusals(run, run_id, plan)
    lines = [f"== run {run_id}: {run.get('html_url')}",
             f"   {run.get('status')} {run.get('conclusion')}, dispatched from "
             f"{run.get('head_sha')}, titled {run.get('display_title')!r}"]
    conclusions = {str(job.get("name")): job.get("conclusion") for job in jobs}
    lines += [f"   job {name}: {conclusion}" for name, conclusion in sorted(conclusions.items())]
    if plan is not None:
        lines += [f"   plan {route.as_object(item).get('verdict')} "
                  f"{route.as_object(item).get('check')}: {route.as_object(item).get('reason')}"
                  for item in route.as_list(plan.get("checks", []))]
    if plan is not None and plan.get("accepted") is not True:
        started = [name for name, conclusion in conclusions.items()
                   if name != "plan" and conclusion not in ("skipped", None)]
        if conclusions.get("plan") != "failure":
            refusals.append(f"the plan refused the dispatch and its job concluded "
                            f"{conclusions.get('plan')!r}, not failure")
        if started:
            refusals.append(f"the plan refused the dispatch and {', '.join(started)} started")
        lines.append("== verdict: refused by the plan" + (
            "; no later job started" if not started else ""))
        lines += [f"FAIL {item}" for item in refusals]
        return lines, not refusals
    staged = base / "artifacts"
    attempt = run.get("run_attempt")
    report = route.join(staged, needs_from_jobs(jobs), str(run_id),
                        str(attempt) if type(attempt) is int else "")
    joined = route.load_json(by_key["join"] / route.REPORT) if "join" in by_key else None
    if joined is None:
        refusals.append("the run left no report.json from its join job")
    elif (joined.get("verdict"), joined.get("refusals"), joined.get("jobs")) != (
            report.get("verdict"), report.get("refusals"), report.get("jobs")):
        refusals.append(f"re-joining the artifacts gives {report.get('verdict')!r}, the run's "
                        f"report {joined.get('verdict')!r}")
    lines.append(f"== verdict: {report.get('verdict')}")
    lines += [f"   refused: {item}" for item in cast("list[str]", report.get("refusals", []))]
    lines += _durations(report)
    evidence, compared = closing_evidence(checkout, report, plan or {}, by_key,
                                          parent=parent, closing=closing,
                                          closing_paths=closing_paths)
    lines += compared
    lines.append("== closing evidence: holds" if not evidence
                 else "== closing evidence: refused")
    lines += [f"   {item}" for item in evidence]
    lines += [f"FAIL {item}" for item in refusals]
    held = not refusals and (closing is None or not evidence)
    return lines, held


def closing_evidence(checkout: Path, report: dict[str, object], plan: dict[str, object],
                     by_key: dict[str, Path], *, parent: str | None, closing: str | None,
                     closing_paths: Sequence[str]) -> tuple[list[str], list[str]]:
    """Why the run is not closing evidence, empty where it is, and the comparisons."""
    refusals: list[str] = []
    lines: list[str] = []
    request = (route.as_object(plan.get("request", {}))
               if isinstance(plan.get("request"), dict) else {})
    if report.get("verdict") != route.PASSED:
        refusals.append(f"the run's verdict is {report.get('verdict')}, not passed")
    build = _receipt(by_key.get("build"))
    tested = build.get("source_revision") if build is not None else None
    dispatching = str(plan.get("dispatching_commit") or "")
    target = parent or (f"{closing}^1" if closing else "main")
    if parent is not None and closing is not None:
        named, first = _commit_of(checkout, parent), _commit_of(checkout, f"{closing}^1")
        if named is None or named != first:
            refusals.append(f"the closing parent {parent} is not the closing commit's first "
                            f"parent {first}")
    if not isinstance(tested, str) or not route.FULL_COMMIT.fullmatch(tested):
        refusals.append("the build job recorded no tested revision")
        return refusals, lines
    inputs = side_inputs(checkout, tested)
    moved = differing(checkout, tested, target, inputs)
    lines.append(f"== git diff --quiet {tested} {target} -- <{len(inputs)} route inputs>: "
                 + ("holds" if not moved else f"does not hold ({', '.join(moved)})"))
    if moved:
        refusals.append(f"the route inputs moved between {tested} and {target}: "
                        f"{', '.join(moved)}")
    own = route_files(checkout, dispatching) if route.FULL_COMMIT.fullmatch(dispatching) else []
    if not own:
        refusals.append("the plan recorded no dispatching commit")
    else:
        changed = differing(checkout, dispatching, target, own)
        lines.append(f"== git diff --quiet {dispatching} {target} -- <{len(own)} route files>: "
                     + ("holds" if not changed else f"does not hold ({', '.join(changed)})"))
        if changed:
            refusals.append(f"the route's own files moved between {dispatching} and {target}: "
                            f"{', '.join(changed)}")
    exported = build.get("export") if build is not None else None
    recorded = route.as_object(exported).get("sha256") if isinstance(exported, dict) else None
    artifact = by_key.get("build")
    if artifact is None or not (artifact / route.EXPORT).is_file():
        refusals.append(f"the build artifact holds no {route.EXPORT}, so no tracked lock "
                        "can be held to it")
    else:
        digest = receipts.digest(artifact / route.EXPORT)
        if digest != recorded:
            refusals.append(f"the artifact's export has SHA-256 {digest}, the receipt "
                            f"{recorded}")
    if closing is not None:
        refusals += closing_refusals(checkout, closing, inputs, closing_paths,
                                     recorded if isinstance(recorded, str) else None)
        lines.append("== the closing landing restates its switch constant and provisioning "
                     "recipe to the lock at: " + (", ".join(closing_paths) or "no path"))
    if request.get("base_revision"):
        if request.get("sample") != str(route.FULL_SAMPLE):
            refusals.append(f"the run compares a base at sample {request.get('sample')}, not "
                            f"{route.FULL_SAMPLE}")
        source = route.source_at(checkout, tested, route.SEED)
        default = route.string_constant(source, "COQ_SUBJECT") if source else None
        subjects = (route.as_object(plan.get("subjects", {}))
                    if isinstance(plan.get("subjects"), dict) else {})
        if default is None or any(value != default for value in subjects.values()):
            refusals.append(f"the run's subjects {subjects} are not seed's default {default!r}")
    return refusals, lines


def cmd_read(args: argparse.Namespace) -> int:
    root = find_root()
    repo = fanout_ci.repository(root, args.remote)
    client = GitHub(root, repo)
    try:
        lines, held = read_run(client, root, args.run, parent=args.parent,
                               closing=args.closing, closing_paths=args.closing_path)
    except fanout_ci.CIError as error:
        print(f"FAIL {error}")
        return 1
    print("\n".join(lines))
    return 0 if held else 1


COMMANDS: cli.Table = {
    "dispatch": (cmd_dispatch, "dispatch the instrument switch route once, or recover a "
                 "dispatch by its nonce"),
    "read": (cmd_read, "read a run's artifacts back and say whether it is closing evidence"),
}


def _flags(name: str, sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--remote", default="origin",
                     help="the github.com remote naming the repository (default: origin)")
    if name == "dispatch":
        sub.add_argument("--revision", help="the commit whose switch the route builds")
        sub.add_argument("--base-revision", help="a base revision; given, the seed jobs run")
        sub.add_argument("--build", help="install or recipe, as the workflow's input takes it")
        sub.add_argument("--sample", help="the seed runs' sample, as the workflow's input "
                                          "takes it")
        sub.add_argument("--title", help="title text after the nonce")
        sub.add_argument("--ref", default="main",
                         help="the ref the workflow is dispatched at (default: main)")
        sub.add_argument("--resume", metavar="NONCE",
                         help="find the run of an interrupted dispatch; never posts again")
    if name == "read":
        sub.add_argument("--run", type=int, required=True, help="the run's identifier")
        sub.add_argument("--parent", help="the closing parent the route inputs are held "
                                          "against (default: the closing commit's first "
                                          "parent, or main)")
        sub.add_argument("--closing", help="the closing commit whose own diff is read")
        sub.add_argument("--closing-path", action="append", default=[], metavar="PATH",
                         help="a path the owning item's closing landing names; repeatable")


def main(argv: list[str] | None = None) -> int:
    return cli.dispatch(__doc__, COMMANDS, argv, _flags, prog="run.py instrument-ci")
