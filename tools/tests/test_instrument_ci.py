# SPDX-License-Identifier: Apache-2.0
"""`run.py instrument-ci`: one journalled dispatch recovered by its nonce, and a reader
that trusts no artifact, re-joins the run and holds closing evidence to the route."""

import argparse
import hashlib
import io
import json
import tempfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from ci import instrument_route as route
from tests.harness import Case, ensure, sandbox_tree
from tests.test_instrument_route import _artifacts, _commit, _git
from vos import fanout_ci
from vos.cli import instrument_ci as reader

REPO = "example/verifiedos"
NONCE = "0123456789abcdef"


class FakeGitHub:
    """GitHub as the reader and the dispatcher see it: canned answers by path."""

    def __init__(self, answers: dict[str, dict[str, object]] | None = None,
                 journal: Path | None = None) -> None:
        self.answers = answers or {}
        self.calls: list[tuple[str, str, dict[str, object] | None]] = []
        self.error: fanout_ci.APIError | None = None
        self.journal = journal
        self.seen_at_post: dict[str, object] | None = None

    def request(self, method: str, path: str,
                payload: dict[str, object] | None = None) -> dict[str, object]:
        self.calls.append((method, path, payload))
        if method == "POST":
            if self.journal is not None:
                found = sorted(self.journal.glob("*.json"))
                self.seen_at_post = route.load_json(found[0]) if found else None
            if self.error is not None:
                raise self.error
        for prefix, answer in self.answers.items():
            if path.startswith(prefix):
                return answer
        raise fanout_ci.APIError(404)

    def location(self, path: str) -> str:
        self.calls.append(("REDIRECT", path, None))
        return f"https://blob.example.invalid/{path.split('/')[-2]}"


def _args(**changes: object) -> argparse.Namespace:
    fields: dict[str, object] = {"revision": None, "base_revision": None, "build": None,
                                 "sample": None, "title": None, "ref": "main"}
    fields.update(changes)
    return argparse.Namespace(**fields)


def _record(inputs: dict[str, str]) -> dict[str, object]:
    return {"schema": 1, "nonce": NONCE, "workflow": reader.WORKFLOW_FILE,
            "repository": REPO, "ref": "main", "inputs": inputs, "run_id": None, "url": "",
            "status": "pending"}


def _dispatch_sends_inputs_unrefused() -> None:
    inputs = reader.dispatch_inputs(_args(revision="abc1234", sample="21", build="other"),
                                    NONCE)
    ensure(inputs == {"revision": "abc1234", "build": "other", "sample": "21",
                      "title": f"ic-{NONCE} abc1234"},
           f"dispatch refuses nothing the plan refuses and titles the run with its nonce: "
           f"{inputs!r}")
    ensure(reader.dispatch_inputs(_args(title="control"), NONCE)["title"] == f"ic-{NONCE} control"
           and reader.display_title(f"ic-{NONCE} x") == f"instrument-switches:ic-{NONCE} x",
           "the caller's title follows the nonce, and the run title is the workflow's")


def _dispatch_journals_before_posting() -> None:
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        client = FakeGitHub({"actions/workflows/instrument-switches.yml/dispatches": {
            "workflow_run_id": 77}}, journal=reader.journal_dir(root))
        record = reader.post(client, root, REPO, _record({"revision": "r", "title": "t"}))
        ensure(client.seen_at_post is not None and client.seen_at_post["phase"] == "intent"
               and bool(client.seen_at_post["requested"]),
               f"the intent reaches disk before the POST: {client.seen_at_post!r}")
        posts = [call for call in client.calls if call[0] == "POST"]
        ensure(len(posts) == 1 and posts[0][2] == {"ref": "main", "inputs": {
            "revision": "r", "title": "t"}} and record["phase"] == "accepted"
               and record["url"] == f"https://github.com/{REPO}/actions/runs/77",
               f"one POST, its run recorded: {record!r}")
        ensure(not reader.pending(root), "an accepted dispatch is no pending intent")


def _dispatch_rejections_and_interruptions() -> None:
    for error, phase in ((fanout_ci.APIError(422), "rejected"), (fanout_ci.APIError(None),
                                                                  "intent")):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            client = FakeGitHub()
            client.error = error
            try:
                reader.post(client, root, REPO, _record({"title": "t"}))
            except fanout_ci.APIError:
                pass
            else:
                raise AssertionError("a failed POST raises")
            saved = route.load_json(reader.journal_dir(root) / f"{NONCE}.json") or {}
            ensure(saved.get("phase") == phase,
                   f"GitHub's refusal is recorded {phase}: {saved!r}")
            ensure(bool(reader.pending(root)) is (phase == "intent"),
                   "an interrupted POST leaves its intent pending")


def _recovery_matches_the_nonce_never_posts() -> None:
    requested = "2026-10-01T10:00:00Z"
    later, earlier = "2026-10-01T10:00:05Z", "2026-10-01T09:50:00Z"
    path = f".github/workflows/{reader.WORKFLOW_FILE}"

    def run(number: int, title: str, created: str) -> dict[str, object]:
        return {"id": number, "display_title": title, "created_at": created, "path": path}

    mine = f"instrument-switches:ic-{NONCE} control"
    cases = [
        ([run(5, mine, later)], 5),
        ([run(5, mine, earlier)], None),
        ([run(5, "instrument-switches:ic-ffffffffffffffff control", later)], None),
        ([run(5, mine, later), run(6, mine, later)], None),
        ([run(5, f"instrument-switches:ic-{NONCE}", later)], 5),
    ]
    for runs, expected in cases:
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            record = _record({"title": f"ic-{NONCE} control"}) | {
                "phase": "intent", "requested": requested}
            client = FakeGitHub({f"actions/workflows/{reader.WORKFLOW_FILE}/runs": {
                "workflow_runs": runs}})
            try:
                found = reader.recover(client, root, REPO, record)
            except fanout_ci.CIError as error:
                ensure(expected is None and "no dispatch was repeated" in str(error),
                       f"an ambiguous or absent run is no recovery: {error}")
            else:
                ensure(found["run_id"] == expected and found["phase"] == "accepted",
                       f"the one run carrying the nonce is recovered: {found!r}")
            ensure(not any(call[0] == "POST" for call in client.calls),
                   "recovery never posts again")


def _job(name: str, conclusion: str) -> dict[str, object]:
    return {"name": name, "conclusion": conclusion}


def _member(name: str, data: bytes) -> tuple[str, bytes]:
    return name, data


def _zip(*members: tuple[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data in members:
            archive.writestr(name, data)
    return stream.getvalue()


def _extraction_refuses_and_bounds() -> None:
    with tempfile.TemporaryDirectory() as scratch:
        target = Path(scratch) / "artifact"
        good = _zip(_member("receipt.json", b"{}"), _member("logs/check.log", b"ok\n"))
        ensure(not reader.extract(good, target) and (target / "logs" / "check.log").is_file(),
               "an allowlisted archive is extracted under its directory alone")
        for members, fragment in (
                ((_member("/etc/passwd.log", b"x"),), "absolute path"),
                ((_member("C:/x.log", b"x"),), "absolute path"),
                ((_member("../escape.log", b"x"),), "climbs out"),
                ((_member("a/../../escape.log", b"x"),), "climbs out"),
                ((_member("Mod.vo", b"x"),), "outside the allowlist"),
                ((_member("tool.log", b"\x7fELF"),), "ELF magic"),
                ((_member("nul.txt", b"a\0b"),), "NUL byte")):
            fresh = Path(scratch) / f"refused-{fragment.replace(' ', '-')}"
            found = reader.extract(_zip(*members), fresh)
            ensure(any(fragment in item for item in found) and not fresh.exists(),
                   f"an archive is refused whole ({fragment!r}): {found!r}")
        for members, fragment in (
                ((_member("a.log", b"x"), _member("a.log/b.log", b"y")), "is the directory of"),
                ((_member("A.log", b"x"), _member("a.log", b"y")), "name one file")):
            fresh = Path(scratch) / f"collide-{fragment.replace(' ', '-')}"
            found = reader.extract(_zip(*members), fresh)
            ensure(any(fragment in item for item in found) and not fresh.exists(),
                   f"members landing on one another refuse the archive ({fragment!r}): "
                   f"{found!r}")
        corrupt = _zip(_member("ok.log", b"a body to corrupt\n"))
        corrupt = corrupt.replace(b"a body to corrupt", b"a body to c0rrupt", 1)
        fresh = Path(scratch) / "corrupt"
        found = reader.extract(corrupt, fresh)
        ensure(any("cannot be read" in item for item in found) and not fresh.exists()
               and not fresh.with_name("corrupt.partial").exists(),
               f"a member failing its CRC refuses the archive: {found!r}")
        found = reader.extract(good, Path(scratch) / "bounded", limit=3)
        ensure(any("over the 3-byte bound" in item for item in found),
               f"members past the bound refuse the archive: {found!r}")
        ensure(not reader.extract(good, target) and not target.with_name(
            "artifact.partial").exists() and (target / "receipt.json").is_file(),
               "an extraction moved into place leaves no partial tree")
        ensure(reader.extract(b"not a zip", Path(scratch) / "z") == [
            "the artifact is not a zip archive"], "a non-archive is refused")
    ensure(reader.member_refusal("a/b.log") is None
           and reader.member_refusal("..\\x.log") is not None,
           "a backslash path is read as the separator it names")


def _needs_from_jobs() -> None:
    jobs: list[dict[str, object]] = [{"name": "plan", "conclusion": "success"},
                                     {"name": "build", "conclusion": "failure"},
            {"name": "import", "conclusion": "skipped"},
            {"name": "seed (base)", "conclusion": "success"},
            {"name": "seed (candidate-1)", "conclusion": "failure"},
            {"name": "seed (candidate-2)", "conclusion": "success"},
            {"name": "join", "conclusion": None, "status": "in_progress"}]
    found = reader.needs_from_jobs(jobs)
    ensure(found == {"plan": {"result": "success"}, "build": {"result": "failure"},
                     "import": {"result": "skipped"}, "seed": {"result": "failure"},
                     "join": {"result": "skipped"}},
           f"a matrix job fails where any run failed: {found!r}")


@contextmanager
def _repository() -> Iterator[tuple[Path, dict[str, str]]]:
    with sandbox_tree({"README.md": "fixture\n"}) as root:
        for key, value in (("user.name", "Fixture"), ("user.email", "fixture@example.invalid"),
                           ("commit.gpgsign", "false")):
            _git(root, "config", key, value)
        files = {
            "tools/run.py": "from vos import corpus\nfrom vos.commands import BY_NAME\n",
            "tools/vos/__init__.py": "",
            "tools/vos/cli/__init__.py": "import argparse\n",
            "tools/vos/corpus.py": "from vos import env\n",
            "tools/vos/commands.py": "",
            "tools/vos/env.py": "import os\n",
            "tools/vos/gallina.py": "from vos import env, proofs\n",
            "tools/vos/proofs.py": "",
            "tools/vos/seeded.py": "",
            "tools/vos/mutate.py": "",
            "tools/vos/sailrig.py": "def f() -> None:\n    from vos import oracle\n",
            "tools/vos/oracle.py": "",
            "tools/vos/unused.py": "",
            "tools/vos/receipts.py": "from vos import env\n",
            "tools/vos/opam_client.py": "from vos import receipts\n",
            "tools/vos/cli/quickchick.py": "from vos import gallina\nfrom . import seed\n",
            "tools/vos/cli/seed.py": ('from vos import gallina, sailrig\n'
                                      'COQ_SUBJECT = "proofs/CyclicExecutive.v"\n'),
            "tools/vos/cli/provision.py": "from vos.cli import quickchick\n",
            "tools/ci/instrument_route.py": "from vos import receipts\n",
            "tools/ci/bootstrap_instrument.py": ("from ci import instrument_route\n"
                                                 "from vos import opam_client\n"),
            "tools/opam/quickchick.lock": "opam-version: \"2.0\"\n",
            "proofs/CyclicExecutive.v": "Definition x := 0.\n",
            route.WORKFLOW: "name: instrument-switches\n",
        }
        tip = _commit(root, files, "route")
        yield root, {"tip": tip}


def _import_closure_reads_sources() -> None:
    with _repository() as (root, commits):
        found = reader.import_closure(root, commits["tip"], route.SIDE_ROOTS)
        ensure({"tools/vos/corpus.py", "tools/vos/env.py", "tools/vos/commands.py",
                "tools/vos/__init__.py", "tools/vos/cli/__init__.py", "tools/vos/sailrig.py",
                "tools/vos/oracle.py", "tools/vos/proofs.py"} <= found
               and "tools/vos/unused.py" not in found and "tools/vos/receipts.py" not in found,
               f"the closure follows top-level, relative and deferred imports: {sorted(found)}")
        own = reader.route_files(root, commits["tip"])
        ensure({"tools/vos/receipts.py", "tools/vos/env.py", route.WORKFLOW,
                "tools/ci/instrument_route.py"} <= set(own)
               and "tools/vos/gallina.py" not in own,
               f"the route's own files and their closure: {own}")
        inputs = reader.side_inputs(root, commits["tip"])
        ensure(set(route.ROUTE_INPUTS) <= set(inputs) and "tools/vos/sailrig.py" in inputs,
               "the route inputs are the contract's and the closure")


def _closing_commit_refusals() -> None:
    with _repository() as (root, commits):
        lock = b"opam-version: \"2.0\"\npinned: [\"x\"]\n"
        digest = hashlib.sha256(lock).hexdigest()
        inputs = reader.side_inputs(root, commits["tip"])
        allowed = ["tools/vos/gallina.py", "tools/vos/cli/quickchick.py",
                   "tools/vos/cli/provision.py"]
        good = _commit(root, {route.LOCK: lock.decode(), "tools/vos/gallina.py":
                              "from vos import env, proofs\nX = 1\n", "docs/note.md": "n\n"},
                       "close")
        ensure(not reader.closing_refusals(root, good, inputs, allowed, digest),
               "the lock at the export's SHA-256, a named path and a non-input pass")
        found = reader.closing_refusals(root, good, inputs, allowed, "0" * 64)
        ensure(any("not the run's export" in item for item in found),
               f"a lock at another SHA-256 is refused: {found!r}")
        stray = _commit(root, {"tools/vos/env.py": "import os\nY = 2\n"}, "stray")
        found = reader.closing_refusals(root, stray, inputs, allowed, digest)
        ensure(any("tools/vos/env.py" in item for item in found),
               f"a route input the closing landing does not name is refused: {found!r}")
        moved = reader.differing(root, commits["tip"], stray, inputs)
        ensure(set(moved) == {route.LOCK, "tools/vos/gallina.py", "tools/vos/env.py"},
               f"the comparison names each moved input: {moved!r}")
        # A named path that newly imports a module the same commit adds brings that
        # module into the route inputs, though the tested revision has none.
        fresh = _commit(root, {"tools/vos/cli/quickchick.py": ("from vos import gallina, fresh\n"
                                                               "from . import seed\n"),
                               "tools/vos/fresh.py": "X = 1\n"}, "fresh import")
        found = reader.closing_refusals(root, fresh, inputs, allowed, digest)
        ensure("tools/vos/fresh.py" not in inputs
               and any("touches the route input tools/vos/fresh.py" in item for item in found),
               f"a module the closing commit newly imports is a route input: {found!r}")


def _input_refusals() -> None:
    plan: dict[str, object] = {"run_id": "9", "dispatching_commit": "d" * 40,
                               "request": {"title": f"ic-{NONCE} x", "revision": "a" * 40}}
    run: dict[str, object] = {"path": f".github/workflows/{reader.WORKFLOW_FILE}",
                              "event": "workflow_dispatch", "head_sha": "d" * 40,
                              "status": "completed",
                              "display_title": f"instrument-switches:ic-{NONCE} x"}
    ensure(not reader.input_refusals(run, 9, plan), "a run agreeing with its plan holds")
    for change, fragment in (({"path": ".github/workflows/guest-gates.yml"}, "not a run of"),
                             ({"event": "push"}, "not dispatched"),
                             ({"status": "in_progress"}, "not completed"),
                             ({"head_sha": "e" * 40}, "dispatching commit"),
                             ({"display_title": "instrument-switches:other"}, "title")):
        found = reader.input_refusals(run | change, 9, plan)
        ensure(any(fragment in item for item in found), f"{fragment!r}: {found!r}")
    found = reader.input_refusals(run, 10, plan)
    ensure(any("names run '9'" in item for item in found), f"{found!r}")
    ensure(reader.input_refusals(run, 9, None) == ["no plan.json was read"],
           "a run with no plan is refused")


def _serve(directory: Path) -> tuple[list[dict[str, object]], dict[str, bytes]]:
    """Each artifact directory under `directory` as GitHub would list and serve it."""
    listing: list[dict[str, object]] = []
    blobs: dict[str, bytes] = {}
    for number, path in enumerate(sorted(p for p in directory.iterdir() if p.is_dir()), 1):
        members = [(item.relative_to(path).as_posix(), item.read_bytes())
                   for item in sorted(path.rglob("*")) if item.is_file()]
        data = _zip(*members)
        listing.append({"id": number, "name": path.name, "expired": False,
                        "size_in_bytes": len(data)})
        blobs[f"https://blob.example.invalid/{number}"] = data
    return listing, blobs


def _read(root: Path, run: dict[str, object], jobs: list[dict[str, object]], artifacts: Path,
          *, parent: str | None = None, closing: str | None = None,
          paths: tuple[str, ...] = ()) -> tuple[list[str], bool, list[tuple[str, str, object]]]:
    listing, blobs = _serve(artifacts)
    client = FakeGitHub({"actions/runs/9/jobs": {"jobs": jobs},
                         "actions/runs/9/artifacts": {"artifacts": listing},
                         "actions/runs/9": run})
    with patch.object(reader, "fetch", side_effect=lambda url, limit: blobs[url]):
        lines, held = reader.read_run(client, root, 9, parent=parent, closing=closing,
                                      closing_paths=paths)
    return lines, held, [(method, path, payload) for method, path, payload in client.calls]


def _reader_decides_a_refused_plan() -> None:
    with _repository() as (root, commits), tempfile.TemporaryDirectory() as scratch:
        artifacts = Path(scratch)
        plan = {"run_id": "9", "dispatching_commit": commits["tip"], "accepted": False,
                "request": {"revision": "abc1234", "title": f"ic-{NONCE} abc1234"},
                "checks": [{"check": "revision", "verdict": "refused",
                            "reason": "'abc1234' is not a full lowercase commit SHA"}]}
        (artifacts / "instrument-plan-unnamed").mkdir()
        (artifacts / "instrument-plan-unnamed" / route.PLAN).write_text(json.dumps(plan),
                                                                          encoding="utf-8")
        run: dict[str, object] = {
            "id": 9, "path": f".github/workflows/{reader.WORKFLOW_FILE}",
            "event": "workflow_dispatch", "head_sha": commits["tip"], "status": "completed",
               "display_title": f"instrument-switches:ic-{NONCE} abc1234",
               "html_url": "https://github.com/example/verifiedos/actions/runs/9"}
        jobs = [_job("plan", "failure"), *(_job(name, "skipped") for name in ("build", "import", "join"))]
        lines, held, calls = _read(root, run, jobs, artifacts)
        ensure(held and "== verdict: refused by the plan; no later job started" in lines
               and any("not a full lowercase" in line for line in lines),
               f"a refused plan is read from plan.json and the job conclusions: {lines!r}")
        ensure(not any(method == "POST" for method, _, _ in calls), "reading posts nothing")
        jobs[1] = _job("build", "success")
        lines, held, _ = _read(root, run, jobs, artifacts)
        ensure(not held and any("build started" in line for line in lines),
               f"a later job that started is a refusal: {lines!r}")
        saved = root / reader.OUT / "9"
        ensure((saved / "instrument-plan-unnamed.zip").is_file()
               and (saved / "artifacts" / "instrument-plan-unnamed" / route.PLAN).is_file(),
               "each artifact is saved and extracted under out/instrument-ci/<run id>/")


def _reader_reproduces_and_compares() -> None:
    with _repository() as (root, commits), tempfile.TemporaryDirectory() as scratch:
        tip = commits["tip"]
        artifacts = Path(scratch)
        _artifacts(artifacts, seed=False, candidate=tip, dispatch=tip, run_id="9")
        export = b"opam-version: \"2.0\"\n"
        build = artifacts / f"instrument-build-{tip}"
        (build / "export").mkdir()
        (build / route.EXPORT).write_bytes(export)
        receipt = route.load_json(build / route.RECEIPT) or {}
        receipt["export"] = {"sha256": hashlib.sha256(export).hexdigest()}
        (build / route.RECEIPT).write_text(json.dumps(receipt), encoding="utf-8")
        jobs = [_job(name, "success") for name in ("plan", "build", "import", "join")]
        report = route.join(artifacts, reader.needs_from_jobs(jobs), "9")
        (artifacts / f"instrument-join-{tip}").mkdir()
        (artifacts / f"instrument-join-{tip}" / route.REPORT).write_text(
            json.dumps(report), encoding="utf-8")
        run: dict[str, object] = {
            "id": 9, "path": f".github/workflows/{reader.WORKFLOW_FILE}",
            "event": "workflow_dispatch", "head_sha": tip, "status": "completed",
               "display_title": f"instrument-switches:{tip}",
               "html_url": "https://github.com/example/verifiedos/actions/runs/9"}
        lines, held, _ = _read(root, run, jobs, artifacts, parent=tip)
        ensure(held and "== verdict: passed" in lines and "== closing evidence: holds" in lines
               and any(line.startswith(f"== git diff --quiet {tip} {tip} -- <")
                       and line.endswith("holds") for line in lines),
               f"a passing run re-joins to its report and holds as closing evidence: {lines!r}")
        moved = _commit(root, {"tools/vos/env.py": "import os\nZ = 3\n"}, "move env")
        lines, held, _ = _read(root, run, jobs, artifacts, parent=moved)
        ensure(held and "== closing evidence: refused" in lines
               and any("tools/vos/env.py" in line and "does not hold" in line for line in lines),
               f"a moved route input refuses the run as closing evidence: {lines!r}")
        lines, held, _ = _read(root, run, jobs, artifacts, closing=moved,
                               paths=("tools/vos/gallina.py",))
        ensure(not held and any("touches the route input tools/vos/env.py" in line
                                for line in lines),
               f"given the closing commit, a touched input it does not name refuses: {lines!r}")
        lines, held, _ = _read(root, run, jobs, artifacts, parent=moved, closing=moved,
                               paths=("tools/vos/env.py",))
        ensure(not held and any("is not the closing commit's first parent" in line
                                for line in lines),
               f"a closing parent other than the closing commit's first is refused: {lines!r}")
        lines, held, _ = _read(root, run, jobs, artifacts, parent=tip, closing=moved,
                               paths=("tools/vos/env.py",))
        ensure(held and "== closing evidence: holds" in lines,
               f"the closing commit's first parent named as the parent holds: {lines!r}")
        (build / route.EXPORT).unlink()
        lines, held, _ = _read(root, run, jobs, artifacts, parent=tip)
        ensure("== closing evidence: refused" in lines
               and any(f"holds no {route.EXPORT}" in line for line in lines),
               f"a build artifact without its export is no closing evidence: {lines!r}")
        (build / route.EXPORT).write_bytes(export)
        tampered = dict(report, verdict="failed")
        (artifacts / f"instrument-join-{tip}" / route.REPORT).write_text(
            json.dumps(tampered), encoding="utf-8")
        lines, held, _ = _read(root, run, jobs, artifacts, parent=tip)
        ensure(not held and any("re-joining the artifacts gives" in line for line in lines),
               f"a report the artifacts do not give is refused: {lines!r}")
        # A member outside the allowlist refuses its artifact, and the earlier reading's
        # extraction of it does not stand in for it.
        (artifacts / f"instrument-join-{tip}" / route.REPORT).write_text(
            json.dumps(report), encoding="utf-8")
        (build / "Switch.vo").write_bytes(b"compiled")
        lines, held, _ = _read(root, run, jobs, artifacts, parent=tip)
        ensure(not held and any("Switch.vo is outside the allowlist" in line for line in lines)
               and any("the build job ran (success) and left no artifact" in line
                       for line in lines),
               f"a refused artifact is missing from the re-join: {lines!r}")


def _fanout_never_runs_the_route() -> None:
    source = Path(fanout_ci.__file__).read_text(encoding="utf-8")
    ensure("instrument" not in source and fanout_ci.HOST == "host-gates.yml"
           and fanout_ci.GUEST == "guest-gates.yml",
           "fanout dispatches Host and Guest CI alone and never this route")


def cases() -> list[Case]:
    return [Case("dispatch-sends-inputs-unrefused", _dispatch_sends_inputs_unrefused),
            Case("dispatch-journals-before-posting", _dispatch_journals_before_posting),
            Case("dispatch-rejections-and-interruptions",
                 _dispatch_rejections_and_interruptions),
            Case("recovery-matches-the-nonce-never-posts",
                 _recovery_matches_the_nonce_never_posts),
            Case("extraction-refuses-and-bounds", _extraction_refuses_and_bounds),
            Case("needs-from-jobs", _needs_from_jobs),
            Case("import-closure-reads-sources", _import_closure_reads_sources),
            Case("closing-commit-refusals", _closing_commit_refusals),
            Case("input-refusals", _input_refusals),
            Case("reader-decides-a-refused-plan", _reader_decides_a_refused_plan),
            Case("reader-reproduces-and-compares", _reader_reproduces_and_compares),
            Case("fanout-never-runs-the-route", _fanout_never_runs_the_route)]
