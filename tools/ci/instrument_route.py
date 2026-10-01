#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The instrument switch route's plan, step limits, staging, comparison and join.

[instrument-switches.yml](../../.github/workflows/instrument-switches.yml) builds and
checks QuickChick's switch on GitHub-hosted runners, and every one of its jobs runs
this file from the dispatching commit's checkout, never from the revision a side
tests. The plan refuses a dispatch before any requested revision is checked out; each
instrument step runs under the limit wrapper and its sampler; each job's staging
decides what leaves its runner; the import job's comparison holds a re-imported switch
to the one the build job exported; and the join reads one artifact per job into
`report.json`. [`run.py instrument-ci read`](../vos/cli/instrument_ci.py) reads the
same records back on the host. [The route's contract](README.md#instrument-switch-route)
states what a run decides and what it leaves to the item that owns the switch.

**A step that reaches its limit decides nothing.** Each step runs under coreutils
`timeout` at the limit stated below, inside the step, so the wrapper outlives it and
records why it ended. An exit of 124, or of 137 where the kernel recorded no OOM kill
during the step, once the step has run for its limit, is the limit reached, and either
exit sooner leaves its cause unread; a step the OOM killer acted on, or that ran short
of disk, is the runner's want rather than the instrument's answer. Each of those is
recorded `undecided`, never as a failure, because a failure moves a pin and a runner's
limit is not evidence about one.
"""

import argparse
import ast
import html
import io
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from vos import receipts  # noqa: E402  (the route's steps run before any locked environment)

# The workflow, and the route's own files: every job runs these from the dispatching
# commit's checkout, so a side's revision supplies none of the code that decides it.
WORKFLOW = ".github/workflows/instrument-switches.yml"
ROUTE_FILES: tuple[str, ...] = (
    WORKFLOW, "tools/ci/bootstrap_instrument.py", "tools/ci/instrument_route.py",
    "tools/vos/opam_client.py",
)
# What a side takes from its own revision: the owner's declarations, the instruments
# and their harnesses, the proofs they compile and the Python environment they run in.
# The reader adds the `vos` import closure of every module here, computed at the
# side's revision, to decide whether a later commit still runs what a run checked.
SIDE_INPUTS: tuple[str, ...] = (
    "tools/vos/gallina.py", "tools/vos/cli/quickchick.py", "tools/vos/cli/seed.py",
    "tools/vos/cli/provision.py", "tools/vos/env.py", "tools/vos/proofs.py",
    "tools/vos/seeded.py", "tools/vos/mutate.py", "tools/run.py", "tools/pyproject.toml",
    "tools/uv.lock", "tools/quickchick/", "tools/opam/quickchick.lock", "proofs/",
)
# Every route input the contract names, before the import closure is added.
ROUTE_INPUTS: tuple[str, ...] = (*ROUTE_FILES, *SIDE_INPUTS)
LOCK = "tools/opam/quickchick.lock"
QUICKCHICK = "tools/vos/cli/quickchick.py"
SEED = "tools/vos/cli/seed.py"
# The modules whose import closure the reader computes at the side's revision: the
# entry point, the two instruments it dispatches to, and every Python route input.
SIDE_ROOTS: tuple[str, ...] = tuple(path for path in SIDE_INPUTS if path.endswith(".py"))
# And at the dispatching commit: the route's own Python.
ROUTE_ROOTS: tuple[str, ...] = tuple(path for path in ROUTE_FILES if path.endswith(".py"))

# Where a job keeps everything it may upload. One root per job on a runner of its own,
# so a side's switch is always built in a root no earlier run touched.
ROOT = Path.home() / "verifiedos-instrument"
LOGS = "logs"
UPLOAD = "upload"
RECEIPT = "receipt.json"
PLAN = "plan.json"
REPORT = "report.json"
PROGRESS = "progress.log"
# The build job's export, staged once every check on its switch passed, and the import
# job's re-export, an observation beside it.
EXPORT = "export/quickchick.lock"
REEXPORT = "export/reexport.lock"
# Where `seed coq --quickchick` journals its verdicts under the root's build tree: the
# lane root's `seed` directory, in the journal seed.py names for the QuickChick oracle.
JOURNAL = "build/seed/quickchick.journal"

# The jobs and the steps each runs under the limit wrapper, in order.
JOB_STEPS: dict[str, tuple[str, ...]] = {
    "plan": ("plan",),
    "build": ("provision", "check", "properties", "export"),
    "import": ("import", "check", "compare"),
    "seed": ("provision", "population", "seed"),
    "join": ("join",),
}
# The three seed runs: the base side and two runs of the candidate's population.
SEED_RUNS: tuple[str, ...] = ("base", "candidate-1", "candidate-2")
# seed's `--jobs`, at one until the build job's recorded `quickchick properties` peak is
# the basis for more; a seed step that reaches its limit raises it in the next dispatch
# on that peak, or leaves the runner decision to the user, and never lowers the sample.
SEED_JOBS = 1
# The sample a comparison dispatch takes, which the reader holds closing evidence to.
FULL_SAMPLE = 20

# The verdicts a step and a job carry. `completed` is a seed run whose journal closes
# on every mutant its head picked, at seed's exit 0 or 1, whatever the step exited:
# seed exits 1 on a survivor, which is the measurement and not a failure of the step.
# A journal that closes on fewer, as one whose baseline did not stand closes on none,
# records a run that measured nothing, and its step fails.
PASSED = "passed"
COMPLETED = "completed"
FAILED = "failed"
UNDECIDED = "undecided"
NOT_RUN = "not run"
# A run in which a job the plan expected never ran although nothing failed.
INCOMPLETE = "incomplete"


@dataclass(frozen=True)
class Limit:
    """One step's limit, the ground it is stated on, and whether a run measured it."""

    seconds: int
    basis: str
    measured: bool


def _ceil_to(seconds: int, unit: int) -> int:
    return math.ceil(seconds / unit) * unit


# GitHub's hosted maximum for a job, in minutes, the margin kept below it, and the
# margin every job keeps for its checkouts, interpreter, staging and upload.
HOSTED_MAXIMUM = 360
HOSTED_MARGIN = 5
STAGING_MARGIN = 15
# How long `timeout` waits after its TERM before it sends KILL.
KILL_AFTER = 60
# A step's `timeout-minutes` is its limit plus that grace plus this, so the backstop
# fires only where the wrapper itself has stopped.
BACKSTOP_MARGIN = 2
# The measurements the limits stand on: Q38f's lane imported its candidate lock into a
# fresh root on the aarch64 guest in this many seconds at OPAMJOBS=2 under opam 2.5.0,
# and Q38e's `quickchick properties` run took this many.
IMPORT_MEASURED = 4_402
PROPERTIES_MEASURED = 378

_PROVISION = Limit(
    _ceil_to(2 * IMPORT_MEASURED + 600, 600),
    f"twice Q38f's {IMPORT_MEASURED:,} s import of its candidate lock into a fresh root on "
    "the aarch64 guest at OPAMJOBS=2, plus ten minutes for the distribution packages, the "
    "client and the root, rounded up to ten whole minutes", measured=True)
_POPULATION = Limit(300, "unmeasured: a text walk of one source, allowed five minutes",
                    measured=False)
LIMITS: dict[str, Limit] = {
    "plan": Limit(300, "unmeasured: reads of the dispatching checkout's history, allowed "
                  "five minutes", measured=False),
    "provision": _PROVISION,
    "import": Limit(_PROVISION.seconds, "the provisioning limit: importing the build's "
                    "export installs the closure the build installed", measured=True),
    "check": Limit(600, "unmeasured: two opam reads and a prover version query, allowed "
                   "ten minutes", measured=False),
    "properties": Limit(
        _ceil_to(5 * PROPERTIES_MEASURED, 300),
        f"five times Q38e's {PROPERTIES_MEASURED} s run of the 33 property sets on the "
        "guest at load 3.3 to 15.5, rounded up to five whole minutes", measured=True),
    "export": Limit(600, "unmeasured: one opam read of the switch, allowed ten minutes",
                    measured=False),
    "compare": Limit(300, "unmeasured: a reading of two receipts, allowed five minutes",
                     measured=False),
    "population": _POPULATION,
    "seed": Limit(
        (HOSTED_MAXIMUM - HOSTED_MARGIN - STAGING_MARGIN) * 60 - _PROVISION.seconds
        - _POPULATION.seconds,
        f"its job's limit: GitHub's {HOSTED_MAXIMUM}-minute hosted maximum less a "
        f"{HOSTED_MARGIN}-minute margin, less the provisioning limit, the population "
        f"listing's and the {STAGING_MARGIN}-minute staging margin; unmeasured, no "
        "`seed coq --quickchick` run having a recorded duration", measured=False),
    "join": Limit(300, "unmeasured: reads of the run's receipts and journals, allowed "
                  "five minutes", measured=False),
}


def job_minutes(job: str) -> int:
    """A job's `timeout-minutes`: the sum of its step limits plus the staging margin."""
    return math.ceil(sum(LIMITS[step].seconds for step in JOB_STEPS[job]) / 60) + STAGING_MARGIN


def backstop_minutes(step: str) -> int:
    """A step's `timeout-minutes`, above its limit and `timeout`'s grace after it."""
    return math.ceil((LIMITS[step].seconds + KILL_AFTER) / 60) + BACKSTOP_MARGIN


# A step that ends with less free disk than this, at any sample or at its end, ran
# short of disk; so does one whose log reports no space left on the device.
DISK_FLOOR = 1 << 30
SAMPLE_INTERVAL = 60.0
GNU_TIME = "/usr/bin/time"
# GNU time's figures, as the other workflows record them: the last is the peak resident
# memory of the command's largest single process.
TIME_FORMAT = "real %e\nuser %U\nsys %S\nmaxrss_kb %M"

# What staging may upload: text in these kinds alone, each file and the whole artifact
# bounded, and no file carrying a Wasm or ELF header or a NUL byte, so that no switch,
# build tree, `.vo`, executable, image or opam cache leaves the runner.
ALLOWED_SUFFIXES: tuple[str, ...] = (".json", ".log", ".txt", ".lock", ".journal")
MAGIC: tuple[tuple[bytes, str], ...] = ((b"\0asm", "Wasm magic"), (b"\x7fELF", "ELF magic"))
FILE_LIMIT = 64 << 20
ARCHIVE_LIMIT = 256 << 20

FULL_COMMIT = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
MAIN = "refs/heads/main"
# Where a dispatch from another ref finds main among the refs its checkout fetched.
REMOTE_MAIN = "refs/remotes/origin/main"
BUILDS: tuple[str, ...] = ("install", "recipe")
SAMPLES = range(1, 21)
HOLDS = "pass"
REFUSED = "refused"
NOT_DECIDED = "not decided"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def as_object(value: object) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise TypeError("expected a JSON object")
    return cast("dict[str, object]", value)


def as_list(value: object) -> list[object]:
    return cast("list[object]", value) if isinstance(value, list) else []


def _read(path: Path) -> str | None:
    """A small text file's contents, None where it cannot be read."""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def load_json(path: Path) -> dict[str, object] | None:
    """A JSON object from a file, None where there is none or it is not an object."""
    text = _read(path)
    if text is None:
        return None
    try:
        return as_object(json.loads(text))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------- the plan


@dataclass(frozen=True)
class Request:
    """What a dispatch asked for, as the workflow hands it over, before any check."""

    ref: str
    dispatching_commit: str
    revision: str
    base_revision: str
    build: str
    sample: str
    title: str


@dataclass(frozen=True)
class Check:
    """One of the plan's checks, its verdict and why."""

    check: str
    verdict: str
    reason: str


def _git(checkout: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(("git", "-C", str(checkout), *args), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", check=False,
                          timeout=120)


def _is_commit(checkout: Path, revision: str) -> bool:
    """Whether the object itself is a commit: an annotated tag's object, which git would
    peel to the commit it tags, is not one."""
    done = _git(checkout, "cat-file", "-t", revision)
    return done.returncode == 0 and done.stdout.strip() == "commit"


def _is_ancestor(checkout: Path, older: str, newer: str) -> bool:
    return _git(checkout, "merge-base", "--is-ancestor", older, newer).returncode == 0


def source_at(checkout: Path, revision: str, path: str) -> str | None:
    """One file's text at a revision, read from history, None where it has none."""
    done = _git(checkout, "show", f"{revision}:{path}")
    return done.stdout if done.returncode == 0 else None


def _top_level(source: str, name: str) -> ast.expr | None:
    """The value a module's source binds `name` to at its top level, read without running
    it: an assignment or an annotated assignment with a value, and no other binding."""
    for node in ast.parse(source).body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return node.value
        if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
                and node.target.id == name and node.value is not None):
            return node.value
    return None


def declares(source: str, name: str) -> bool:
    """Whether a module's source binds `name` at its top level. A name bound inside a
    function, a class or a conditional block, or only mentioned, is not declared."""
    return _top_level(source, name) is not None


def string_constant(source: str, name: str) -> str | None:
    """A top-level string a module's source binds `name` to, None where it binds none."""
    try:
        value = _top_level(source, name)
    except SyntaxError:
        return None
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def _recipe_check(checkout: Path, revision: str, name: str, check: str) -> Check:
    source = source_at(checkout, revision, QUICKCHICK)
    if source is None:
        return Check(check, REFUSED, f"{revision} carries no {QUICKCHICK}")
    try:
        found = declares(source, name)
    except SyntaxError as error:
        return Check(check, REFUSED, f"{QUICKCHICK} at {revision} does not parse: {error}")
    if not found:
        return Check(check, REFUSED, f"{QUICKCHICK} at {revision} declares no `{name}`, read "
                     "from its source without running it")
    return Check(check, HOLDS, f"{QUICKCHICK} at {revision} declares `{name}`")


def _main_tip(checkout: Path, asked: Request) -> str | None:
    """The commit main stands at for this dispatch: the dispatching commit where the
    dispatch is from main, and otherwise main as the checkout fetched it."""
    if asked.ref == MAIN:
        return asked.dispatching_commit
    found = _git(checkout, "rev-parse", "--verify", "--quiet", f"{REMOTE_MAIN}^{{commit}}")
    tip = found.stdout.strip()
    return tip if found.returncode == 0 and FULL_COMMIT.fullmatch(tip) else None


def plan(checkout: Path, asked: Request) -> list[Check]:
    """Every check the plan makes, each decided where its premises are, so a refused
    dispatch names each reason rather than the first."""
    checks: list[Check] = []
    head = _git(checkout, "rev-parse", "HEAD").stdout.strip()
    if head == asked.dispatching_commit and FULL_COMMIT.fullmatch(head):
        checks.append(Check("route", HOLDS, f"the plan runs from the dispatching commit {head}"))
    else:
        checks.append(Check("route", REFUSED, f"the plan runs from {head or 'no commit'}, not "
                            f"the dispatching commit {asked.dispatching_commit!r}"))
    if asked.ref == MAIN:
        checks.append(Check("ref", HOLDS, f"dispatched from {MAIN}"))
    else:
        checks.append(Check("ref", REFUSED, f"dispatched from {asked.ref!r}; the route runs "
                            f"only from {MAIN}"))

    revision = asked.revision
    main = _main_tip(checkout, asked)
    on_main = False
    if not revision:
        checks.append(Check("revision", REFUSED, "no revision was requested; a run names the "
                            "commit it tests rather than taking main's tip"))
    elif not FULL_COMMIT.fullmatch(revision):
        checks.append(Check("revision", REFUSED, f"{revision!r} is not a full lowercase "
                            "commit SHA"))
    elif not _is_commit(checkout, revision):
        checks.append(Check("revision", REFUSED, f"{revision} is no commit the dispatching "
                            "checkout reaches, a tag's object included, so it is not a "
                            "commit on main"))
    elif main is None:
        checks.append(Check("revision", NOT_DECIDED, "the checkout fetched no main to hold "
                            "the revision against"))
    elif not _is_ancestor(checkout, revision, main):
        checks.append(Check("revision", REFUSED, f"{revision} is not on main: it is no "
                            f"ancestor of main's {main}"))
    else:
        on_main = True
        checks.append(Check("revision", HOLDS, f"{revision} is on main"))

    build_ok = asked.build in BUILDS
    checks.append(Check("build", HOLDS, f"build {asked.build}") if build_ok else Check(
        "build", REFUSED, f"build {asked.build!r} is neither {' nor '.join(BUILDS)}"))

    # The canonical spelling alone, so the sample every job records is the request's.
    if re.fullmatch(r"[1-9][0-9]*", asked.sample) and int(asked.sample) in SAMPLES:
        checks.append(Check("sample", HOLDS, f"sample {asked.sample}"))
    else:
        checks.append(Check("sample", REFUSED, f"sample {asked.sample!r} is not a whole "
                            f"number from {SAMPLES.start} to {SAMPLES.stop - 1}, written "
                            "without a sign or leading zero"))

    base = asked.base_revision
    base_ok = False
    if not base:
        checks.append(Check("base_revision", HOLDS, "no base revision was requested, so the "
                            "seed jobs do not run"))
    elif not FULL_COMMIT.fullmatch(base):
        checks.append(Check("base_revision", REFUSED, f"{base!r} is not a full lowercase "
                            "commit SHA"))
    elif base == revision:
        checks.append(Check("base_revision", REFUSED, f"{base} is the revision itself, not a "
                            "proper ancestor of it"))
    elif not on_main:
        checks.append(Check("base_revision", NOT_DECIDED, "the revision it must precede was "
                            "refused"))
    elif not _is_commit(checkout, base):
        checks.append(Check("base_revision", REFUSED, f"{base} is no commit the dispatching "
                            "checkout reaches, a tag's object included, so it is not an "
                            f"ancestor of {revision}"))
    elif not _is_ancestor(checkout, base, revision):
        checks.append(Check("base_revision", REFUSED, f"{base} is not an ancestor of "
                            f"{revision}"))
    else:
        base_ok = True
        checks.append(Check("base_revision", HOLDS, f"{base} is a proper ancestor of "
                            f"{revision}"))

    if not on_main or not build_ok:
        checks.append(Check("recipe", NOT_DECIDED, "the revision or the build it names was "
                            "refused"))
    else:
        checks.append(_recipe_check(checkout, revision,
                                    "RECIPE" if asked.build == "recipe" else "INSTALL", "recipe"))
    if base_ok:
        checks.append(_recipe_check(checkout, base, "INSTALL", "base_recipe"))
    return checks


def accepted(checks: Sequence[Check]) -> bool:
    return all(check.verdict == HOLDS for check in checks)


def plan_record(checkout: Path, asked: Request, checks: Sequence[Check]) -> dict[str, object]:
    """plan.json: the request as it arrived, each check's verdict and reason, and what
    the accepted run runs, with seed's default subject at each side read from source."""
    ok = accepted(checks)
    subjects: dict[str, str | None] = {}
    if ok:
        for side, revision in (("candidate", asked.revision), ("base", asked.base_revision)):
            if revision:
                source = source_at(checkout, revision, SEED)
                found = string_constant(source, "COQ_SUBJECT") if source else None
                # One printable line, as a job output carries it, or none.
                subjects[side] = found if found and found.isprintable() else None
    return {
        "schema": 1, "workflow": WORKFLOW,
        "request": {"ref": asked.ref, "revision": asked.revision,
                    "base_revision": asked.base_revision, "build": asked.build,
                    "sample": asked.sample, "title": asked.title},
        "dispatching_commit": asked.dispatching_commit,
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "checks": [{"check": c.check, "verdict": c.verdict, "reason": c.reason} for c in checks],
        "accepted": ok,
        "seed": ok and bool(asked.base_revision),
        "subjects": subjects,
    }


def plan_outputs(asked: Request, ok: bool,
                 subjects: dict[str, str | None] | None = None) -> dict[str, str]:
    """The job outputs later jobs read, each a value the plan validated or read from a
    side's source, so no input reaches a later job's expression unchecked: with each
    side's subject, which every job's receipt records from its start."""
    label = asked.revision if FULL_COMMIT.fullmatch(asked.revision) else "unnamed"
    found = {"accepted": "true" if ok else "false", "label": label}
    if ok:
        named = subjects or {}
        found |= {"revision": asked.revision, "base_revision": asked.base_revision,
                  "build": asked.build, "sample": asked.sample,
                  "seed": "true" if asked.base_revision else "false",
                  "subject": named.get("candidate") or "",
                  "base_subject": named.get("base") or ""}
    return found


def github_output(values: dict[str, str], target: Path | str | None = None) -> None:
    """Append job outputs, each one line, to the file GitHub reads them from."""
    target = target or os.environ.get("GITHUB_OUTPUT")
    if not target:
        return
    if any(c in value for value in values.values() for c in "\r\n"):
        raise ValueError("a job output must be one line")
    with Path(target).open("a", encoding="utf-8", newline="") as stream:
        stream.writelines(f"{key}={value}\n" for key, value in values.items())


def request_from_environment() -> Request:
    environ = os.environ
    return Request(
        ref=environ.get("GITHUB_REF", ""), dispatching_commit=environ.get("GITHUB_SHA", ""),
        revision=environ.get("PLAN_REVISION", ""),
        base_revision=environ.get("PLAN_BASE_REVISION", ""),
        build=environ.get("PLAN_BUILD", ""), sample=environ.get("PLAN_SAMPLE", ""),
        title=environ.get("PLAN_TITLE", ""))


def cmd_plan(args: argparse.Namespace) -> int:
    asked = request_from_environment()
    checkout = args.checkout
    checks = plan(checkout, asked)
    ok = accepted(checks)
    record = plan_record(checkout, asked, checks)
    receipts.write(args.root / LOGS / PLAN, record)
    github_output(plan_outputs(asked, ok,
                               cast("dict[str, str | None]", record["subjects"])))
    for check in checks:
        print(f"{check.verdict:<11} {check.check}: {check.reason}")
    print("ok the plan accepts the dispatch" if ok else "FAIL the plan refuses the dispatch; "
          "no later job starts")
    return 0 if ok else 1


# ------------------------------------------------------------------- receipts and steps


def receipt_path(root: Path) -> Path:
    return root / LOGS / RECEIPT


def free_disk(path: Path) -> int | None:
    """Free bytes on the filesystem holding `path` or its nearest existing parent."""
    probe = path
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        return shutil.disk_usage(probe).free
    except OSError:
        return None


def base_receipt(root: Path) -> dict[str, object]:
    """What every job's receipt records before its first step: the job, its side and the
    dispatch's effective inputs, as the workflow states them from the plan, the side's
    subject among them, beside the run. The side's source revision, recipe, switch and
    closure are the provisioning's to add."""
    environ = os.environ
    side = environ.get("INSTRUMENT_SIDE", "")
    return {
        "schema": 1, "job": environ.get("INSTRUMENT_JOB", ""),
        "run": environ.get("INSTRUMENT_RUN", ""),
        "inputs": {"side": side,
                   "revision": environ.get("INSTRUMENT_REVISION", ""),
                   "base_revision": environ.get("INSTRUMENT_BASE_REVISION", ""),
                   "build": environ.get("INSTRUMENT_BUILD", ""),
                   "sample": environ.get("INSTRUMENT_SAMPLE", ""),
                   "subject": environ.get("INSTRUMENT_BASE_SUBJECT" if side == "base"
                                          else "INSTRUMENT_SUBJECT", "")},
        "dispatching_commit": environ.get("GITHUB_SHA", ""),
        "run_id": environ.get("GITHUB_RUN_ID", ""),
        "run_attempt": environ.get("GITHUB_RUN_ATTEMPT", ""),
        "runner_image": f"{environ.get('ImageOS', 'unknown')}-"
                        f"{environ.get('ImageVersion', 'unknown')}",
        "uname_m": platform.machine(),
        "free_disk_before": free_disk(root),
        "steps": {},
    }


def load_receipt(root: Path) -> dict[str, object]:
    found = load_json(receipt_path(root))
    return found if found is not None else base_receipt(root)


def save_receipt(root: Path, receipt: dict[str, object]) -> None:
    receipts.write(receipt_path(root), receipt)


def update_receipt(root: Path, **fields: object) -> dict[str, object]:
    """Merge fields into a job's receipt, as each step that knows one adds it."""
    receipt = load_receipt(root)
    receipt.update(fields)
    save_receipt(root, receipt)
    return receipt


def update_inputs(root: Path, **fields: str) -> dict[str, object]:
    """Merge fields into the receipt's effective inputs."""
    receipt = load_receipt(root)
    inputs = as_object(receipt.get("inputs", {}))
    inputs.update(fields)
    receipt["inputs"] = inputs
    save_receipt(root, receipt)
    return receipt


@dataclass(frozen=True)
class Sample:
    """One minute's reading: the step's largest resident set and its tree's total, the
    root's free disk and the load average."""

    rss_max_kb: int
    rss_tree_kb: int
    free_disk: int | None
    load: tuple[float, float, float] | None


def _load_average() -> tuple[float, float, float] | None:
    if sys.platform == "win32":
        return None
    return os.getloadavg()


def _rss_kb(pid: int) -> int:
    text = _read(Path("/proc") / str(pid) / "status") or ""
    found = re.search(r"(?m)^VmRSS:\s+(\d+)\s+kB", text)
    return int(found.group(1)) if found else 0


def _tree(pid: int) -> set[int]:
    """`pid` and every process descended from it, read from /proc."""
    children: dict[int, list[int]] = {}
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        entries = []
    for entry in entries:
        if not entry.name.isdigit():
            continue
        stat = _read(entry / "stat")
        if stat is None or ")" not in stat:
            continue
        fields = stat[stat.rindex(")") + 2:].split()
        if len(fields) > 1 and fields[1].isdigit():
            children.setdefault(int(fields[1]), []).append(int(entry.name))
    found: set[int] = set()
    pending = [pid]
    while pending:
        current = pending.pop()
        if current not in found:
            found.add(current)
            pending.extend(children.get(current, ()))
    return found


def linux_sample(pid: int, root: Path) -> Sample:
    sizes = [_rss_kb(member) for member in _tree(pid)]
    return Sample(max(sizes, default=0), sum(sizes), free_disk(root), _load_average())


class Sampler:
    """Appends one line per interval to the job's progress log while a step runs, and
    keeps the step's peaks, so a step cut at its limit still leaves them."""

    def __init__(self, progress: Path, step: str, read: Callable[[], Sample],
                 interval: float = SAMPLE_INTERVAL) -> None:
        self.progress = progress
        self.step = step
        self.read = read
        self.interval = interval
        self.peak_rss_kb = 0
        self.peak_tree_kb = 0
        self.lowest_free_disk: int | None = None
        self.samples = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def sample(self) -> Sample:
        found = self.read()
        self.samples += 1
        self.peak_rss_kb = max(self.peak_rss_kb, found.rss_max_kb)
        self.peak_tree_kb = max(self.peak_tree_kb, found.rss_tree_kb)
        if found.free_disk is not None:
            self.lowest_free_disk = (found.free_disk if self.lowest_free_disk is None
                                     else min(self.lowest_free_disk, found.free_disk))
        load = ",".join(f"{value:.2f}" for value in found.load) if found.load else "unread"
        disk = found.free_disk if found.free_disk is not None else "unread"
        self.progress.parent.mkdir(parents=True, exist_ok=True)
        with self.progress.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"{_now()} {self.step} rss_max_kb={found.rss_max_kb} "
                         f"rss_tree_kb={found.rss_tree_kb} free_disk_bytes={disk} "
                         f"load={load}\n")
        return found

    def _loop(self) -> None:
        while not self._stop.wait(self.interval):
            try:
                self.sample()
            except OSError:
                continue

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=10)


# The kernel's own records of an OOM kill, as its ring buffer words them.
_OOM_RE = re.compile(r"Out of memory|oom-kill|oom_reaper|Killed process")


def kernel_oom() -> list[str] | None:
    """The OOM records the kernel's ring buffer holds, None where it cannot be read."""
    if sys.platform == "win32":
        return None
    prefix = () if os.geteuid() == 0 else ("sudo", "-n")
    try:
        done = subprocess.run((*prefix, "dmesg"), capture_output=True, text=True,
                              errors="replace", check=False, timeout=60,
                              stdin=subprocess.DEVNULL)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0:
        return None
    return [line for line in done.stdout.splitlines() if _OOM_RE.search(line)]


def new_oom(before: list[str] | None, after: list[str] | None) -> list[str] | None:
    """The OOM records a step added. Unread afterwards is unread; unread before counts
    every record found after as the step's, which errs toward undecided."""
    if after is None:
        return None
    seen = set(before or ())
    return [line for line in after if line not in seen]


@dataclass(frozen=True)
class Outcome:
    verdict: str
    reason: str


def classify(exit_code: int | None, limit: int, *, oom: Sequence[str] | None,
             lowest_free_disk: int | None, no_space: bool = False,
             prover_timeout: bool = False, journal_complete: bool | None = None,
             journal_reason: str = "its journal has no closing line",
             seconds: float | None = None) -> Outcome:
    """A step's verdict from how it ended.

    A limit reached, an OOM kill and a want of disk are each undecided, never a failure.
    An exit of 124 or 137 is the limit reached once the step has run `seconds` up to its
    limit; sooner, `timeout` did not end it, and what did is unread, so it is undecided.
    `journal_complete` is given for a step a journal decides, a seed run, and such a step
    is `completed` once its journal closes on every mutant it picked, whatever the step
    exited, unless the kernel killed one of its processes for memory, which can read as
    a mutant's verdict; `journal_reason` says why a journal that does not falls short.
    """
    if exit_code == 0 and journal_complete is None:
        return Outcome(PASSED, "exit 0")
    if oom:
        return Outcome(UNDECIDED, f"the kernel's OOM killer acted during the step: {oom[0]}")
    if exit_code in (124, 137) and seconds is not None and seconds < limit:
        return Outcome(UNDECIDED, f"the step exited {exit_code} after {seconds:.1f} s, short "
                       f"of its limit of {limit} s, so timeout did not end it, and what "
                       "did is unread")
    if exit_code == 124:
        return Outcome(UNDECIDED, f"the step reached its limit of {limit} s and timeout "
                       "ended it")
    if exit_code == 137:
        why = ("the kernel recorded no OOM kill during it" if oom is not None
               else "the kernel's ring buffer could not be read, so an OOM kill is not excluded")
        return Outcome(UNDECIDED, f"the step reached its limit of {limit} s and outlived "
                       f"timeout's {KILL_AFTER} s grace, so timeout killed it; {why}")
    if no_space or (lowest_free_disk is not None and lowest_free_disk < DISK_FLOOR):
        shown = ("its log reports no space left on the device" if no_space
                 else f"free disk fell to {lowest_free_disk} bytes, below {DISK_FLOOR}")
        return Outcome(UNDECIDED, f"the step ran short of disk: {shown}")
    if prover_timeout:
        return Outcome(UNDECIDED, "a compile reached gallina's per-file timeout, which "
                       "raises out of the run")
    if journal_complete:
        return Outcome(COMPLETED, f"the run finished: its journal closes on every mutant "
                       f"it picked, and it exited {exit_code}")
    if exit_code is None:
        return Outcome(FAILED, "the step's command did not start")
    if journal_complete is not None:
        return Outcome(FAILED, f"exit {exit_code}, and {journal_reason}")
    return Outcome(FAILED, f"exit {exit_code}")


def time_figures(text: str | None) -> dict[str, float] | None:
    """GNU time's figures from its output file, None where it wrote none."""
    if not text:
        return None
    found: dict[str, float] = {str(key): float(value) for key, value in
                               re.findall(r"(?m)^(real|user|sys|maxrss_kb) ([0-9.]+)$", text)}
    return found or None


def step_command(limit: Limit, argv: Sequence[str], time_path: Path,
                 gnu_time: str | None = GNU_TIME) -> list[str]:
    """The argv a step runs: its command under coreutils `timeout` at its limit, with
    KILL after the grace, under GNU time writing its figures to `time_path`."""
    limited = ["timeout", f"--kill-after={KILL_AFTER}s", f"{limit.seconds}s", *argv]
    if gnu_time is None:
        return limited
    return [gnu_time, "-f", TIME_FORMAT, "-o", str(time_path), *limited]


def _echo(line: bytes) -> None:
    stream = sys.stdout.buffer if isinstance(sys.stdout, io.TextIOWrapper) else None
    if stream is not None:
        stream.write(line)
        stream.flush()
    else:
        print(line.decode("utf-8", errors="replace"), end="")


@dataclass
class Hooks:
    """What a step reads of the machine, replaceable so a test can stand in for it."""

    oom: Callable[[], list[str] | None] = kernel_oom
    sample: Callable[[int, Path], Sample] = linux_sample
    gnu_time: str | None = GNU_TIME
    interval: float = SAMPLE_INTERVAL


def run_step(name: str, argv: Sequence[str], *, root: Path = ROOT, limit: Limit | None = None,
             journal: Path | None = None, hooks: Hooks | None = None) -> int:
    """Run one step under `timeout` at its limit and GNU time, sampling it every
    interval, and record how it ended in the job's receipt."""
    chosen = limit or LIMITS[name]
    found = hooks or Hooks()
    logs = root / LOGS
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / f"{name}.log"
    time_path = logs / f"{name}.time.txt"
    time_path.unlink(missing_ok=True)
    if not receipt_path(root).is_file():
        save_receipt(root, base_receipt(root))
    oom_before = found.oom()
    disk_before = free_disk(root)
    began = _now()
    started = time.monotonic()
    command = step_command(chosen, argv, time_path, found.gnu_time)
    no_space = prover_timeout = False
    exit_code: int | None = None
    sampler: Sampler | None = None
    with log_path.open("wb") as log:
        log.write(f"== {name}: limit {chosen.seconds} s ({chosen.basis})\n".encode())
        log.flush()
        try:
            child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL)
        except OSError as error:
            log.write(f"FAIL the step did not start: {error}\n".encode())
        else:
            sampler = Sampler(logs / PROGRESS, name,
                              lambda: found.sample(child.pid, root), found.interval)
            sampler.start()
            stream = child.stdout
            if stream is not None:
                for line in stream:
                    _echo(line)
                    log.write(line)
                    no_space = no_space or b"No space left on device" in line
                    prover_timeout = prover_timeout or b"TimeoutExpired" in line
            exit_code = child.wait()
            sampler.stop()
    elapsed = time.monotonic() - started
    seconds = round(elapsed, 1)
    oom = new_oom(oom_before, found.oom())
    disk_after = free_disk(root)
    lows = [value for value in (disk_before, disk_after,
                                sampler.lowest_free_disk if sampler else None)
            if value is not None]
    complete: bool | None = None
    shortfall = ""
    if journal is not None:
        text = _read(journal) if journal.is_file() else None
        why = journal_shortfall(parse_journal(text)) if text is not None else (
            "it wrote no journal")
        complete, shortfall = why is None, why or ""
    outcome = classify(exit_code, chosen.seconds, oom=oom, lowest_free_disk=min(lows, default=None),
                       no_space=no_space, prover_timeout=prover_timeout,
                       journal_complete=complete, journal_reason=shortfall, seconds=elapsed)
    receipt = load_receipt(root)
    steps = as_object(receipt.get("steps", {}))
    steps[name] = {
        "limit_s": chosen.seconds, "limit_basis": chosen.basis, "measured": chosen.measured,
        "kill_after_s": KILL_AFTER, "started_utc": began, "seconds": seconds,
        "exit": exit_code, "verdict": outcome.verdict, "reason": outcome.reason,
        "time": time_figures(_read(time_path)),
        "peak_rss_kb": sampler.peak_rss_kb if sampler else None,
        "peak_tree_rss_kb": sampler.peak_tree_kb if sampler else None,
        "samples": sampler.samples if sampler else 0,
        "free_disk_before": disk_before, "free_disk_after": disk_after,
        "lowest_free_disk": min(lows, default=None), "oom_records": oom,
        "log": f"{name}.log",
    }
    receipt["steps"] = steps
    save_receipt(root, receipt)
    print(f"{outcome.verdict} {name}: {outcome.reason}")
    return 0 if outcome.verdict in (PASSED, COMPLETED) else 1


def cmd_step(args: argparse.Namespace) -> int:
    argv = list(args.argv)
    if argv[:1] == ["--"]:
        argv = argv[1:]
    if not argv:
        print("FAIL a step names the command it runs after `--`", file=sys.stderr)
        return 2
    journal = args.root / JOURNAL if args.journal else None
    return run_step(args.step, argv, root=args.root, journal=journal)


# The instrument steps, each the side's own command at its revision.
INSTRUMENTS: tuple[str, ...] = ("check", "properties", "population", "seed")


def side_command(step: str, side: Path, receipt: dict[str, object],
                 python: str = sys.executable) -> list[str]:
    """The side's command one instrument step runs, with the flag its build calls for:
    `--recipe` after a `RECIPE` build, read from the receipt the provisioning wrote,
    the sample the plan accepted, and seed's default subject, which the seed run takes
    by naming none."""
    inputs = as_object(receipt.get("inputs", {}))
    flag = receipt.get("flag")
    if flag not in ("", "--recipe"):
        raise ValueError(f"the receipt records no flag the provisioning sets: {flag!r}")
    flags = [flag] if flag else []
    entry = [python, str(side / "tools" / "run.py")]
    sample = str(inputs.get("sample", ""))
    if step in ("population", "seed") and not re.fullmatch(r"[1-9][0-9]*", sample):
        raise ValueError(f"the receipt records no sample: {sample!r}")
    if step == "check":
        return [*entry, "quickchick", "check", *flags]
    if step == "properties":
        return [*entry, "quickchick", "properties", *flags]
    if step == "population":
        subject = str(inputs.get("subject", ""))
        if not subject:
            raise ValueError("the receipt records no subject to list")
        return [*entry, "seed", "list", "--file", subject, "--sample", sample]
    if step == "seed":
        return [*entry, "seed", "coq", "--quickchick", "--sample", sample,
                "--jobs", str(SEED_JOBS), *flags]
    raise ValueError(f"no instrument step {step!r}")


def cmd_instrument(args: argparse.Namespace) -> int:
    receipt = load_receipt(args.root)
    argv = side_command(args.step, args.side, receipt)
    journal = args.root / JOURNAL if args.step == "seed" else None
    return run_step(args.step, argv, root=args.root, journal=journal)


# --------------------------------------------------------------------------- staging


def name_refusal(name: str) -> str | None:
    """Why a staged name is not in the allowlist, None where it is."""
    if not name.endswith(ALLOWED_SUFFIXES):
        return f"its kind is outside the allowlist {', '.join(ALLOWED_SUFFIXES)}"
    return None


def content_refusal(data: bytes) -> str | None:
    """Why bytes may not leave the runner: a Wasm or ELF header or a NUL byte."""
    for magic, what in MAGIC:
        if data.startswith(magic):
            return f"it carries {what}"
    if b"\0" in data:
        return "it carries a NUL byte"
    return None


def select(sources: Iterable[tuple[Path, str]]) -> tuple[list[tuple[Path, str]],
                                                         list[dict[str, str]]]:
    """Which files staging uploads, each under its name in the artifact, and every one
    it leaves out with the reason."""
    staged: list[tuple[Path, str]] = []
    excluded: list[dict[str, str]] = []
    total = 0
    for path, name in sorted(sources, key=lambda item: item[1]):
        reason = name_refusal(name)
        if reason is None and (path.is_symlink() or not path.is_file()):
            reason = "it is not a regular file"
        size = path.stat().st_size if reason is None else 0
        if reason is None and size > FILE_LIMIT:
            reason = f"it holds {size} bytes, over the {FILE_LIMIT}-byte limit for one file"
        if reason is None:
            reason = content_refusal(path.read_bytes())
        if reason is None and total + size > ARCHIVE_LIMIT:
            reason = f"it would take the artifact past its {ARCHIVE_LIMIT}-byte limit"
        if reason is None:
            total += size
            staged.append((path, name))
        else:
            excluded.append({"path": name, "reason": reason})
    return staged, excluded


def _sources(root: Path) -> list[tuple[Path, str]]:
    """Every file a job may upload, under its name in the artifact: its logs, seed's
    journals, and opam's own diagnostic text for a failed package, as `.log` copies.
    The export is not among them: `stage` adds it where every check passed."""
    found: list[tuple[Path, str]] = []
    logs = root / LOGS
    if logs.is_dir():
        found += [(path, path.relative_to(logs).as_posix()) for path in logs.rglob("*")
                  if path.relative_to(logs).as_posix() != RECEIPT and not path.is_dir()]
    seed = (root / JOURNAL).parent
    if seed.is_dir():
        found += [(path, f"seed/{path.name}") for path in seed.glob("*.journal")]
    opam_log = root / "opam" / "log"
    if opam_log.is_dir():
        found += [(path, f"opam-log/{path.name}.log") for path in opam_log.iterdir()
                  if path.suffix in {".out", ".info"}]
    reexport = root / REEXPORT
    if reexport.is_file():
        found.append((reexport, REEXPORT))
    return found


def _passed(steps: dict[str, object], names: Iterable[str]) -> bool:
    return all(as_object(steps.get(name, {})).get("verdict") == PASSED for name in names)


def stage(root: Path, job: str) -> list[dict[str, str]]:
    """Copy what a job may upload into its upload directory, recording in the receipt
    every step that never ran and every file left out with its reason."""
    receipt = load_receipt(root)
    steps = as_object(receipt.get("steps", {}))
    for step in JOB_STEPS.get(job, ()):
        if step not in steps:
            steps[step] = {"verdict": NOT_RUN, "reason": "an earlier step of the job did not "
                           "pass, or the job ended before this step"}
    receipt["steps"] = steps
    receipt["free_disk_after"] = free_disk(root)
    sources = _sources(root)
    export = root / EXPORT
    held_out: list[dict[str, str]] = []
    if export.is_file():
        if job == "build" and _passed(steps, JOB_STEPS["build"]):
            sources.append((export, EXPORT))
        else:
            held_out.append({"path": EXPORT, "reason": "not every check on its switch "
                             "passed, so the switch's export is not uploaded"})
    staged, excluded = select(sources)
    excluded = [*held_out, *excluded]
    receipt["staging"] = {"allowlist": list(ALLOWED_SUFFIXES),
                          "staged": [*(name for _, name in staged), RECEIPT],
                          "excluded": excluded}
    save_receipt(root, receipt)
    upload = root / UPLOAD
    if upload.exists():
        shutil.rmtree(upload)
    for path, name in [*staged, (receipt_path(root), RECEIPT)]:
        target = upload / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    for item in excluded:
        print(f"left out {item['path']}: {item['reason']}")
    print(f"staged {len(staged) + 1} file(s) into {upload}")
    return excluded


def cmd_stage(args: argparse.Namespace) -> int:
    stage(args.root, args.job)
    return 0


# ----------------------------------------------------------------- the import comparison


@dataclass(frozen=True)
class Package:
    """One installed package of a switch's closure, with the source a pin names."""

    name: str
    version: str
    pin: str


_PIN_RE = re.compile(r"(?P<url>[a-z0-9+]+://\S+?)#(?P<commit>[0-9a-f]{7,40})")


def closure_of(receipt: dict[str, object]) -> list[Package] | None:
    """The installed closure a receipt records, None where it records none."""
    raw = receipt.get("closure")
    if not isinstance(raw, list) or not raw:
        return None
    found: list[Package] = []
    for item in cast("list[object]", raw):
        if not isinstance(item, dict):
            return None
        entry = as_object(item)
        name, version, pin = entry.get("name"), entry.get("version"), entry.get("pin", "")
        if not (isinstance(name, str) and isinstance(version, str) and isinstance(pin, str)):
            return None
        found.append(Package(name, version, pin))
    return sorted(found, key=lambda package: package.name)


def pins_of(closure: Sequence[Package]) -> dict[str, tuple[str, str]]:
    """Each pinned package's upstream URL and commit, as its pin names them."""
    found: dict[str, tuple[str, str]] = {}
    for package in closure:
        matched = _PIN_RE.fullmatch(package.pin) if package.pin else None
        if matched is not None:
            found[package.name] = (matched["url"], matched["commit"])
        elif package.pin:
            found[package.name] = (package.pin, "")
    return found


def compare_import(build: dict[str, object], imported: dict[str, object],
                   run_id: str) -> dict[str, object]:
    """Whether the import job's switch is the build's: decided by `quickchick check`'s
    exit 0 on it, the installed closure and each pin's URL and commit, with the byte
    difference of its re-export recorded as an observation and nothing more."""
    reasons: list[str] = []
    if build.get("job") != "build":
        reasons.append(f"the build receipt names job {build.get('job')!r}")
    if build.get("run_id") != run_id:
        reasons.append(f"the build receipt names run {build.get('run_id')!r}, not {run_id}")
    exported = as_object(build.get("export", {})) if isinstance(build.get("export"), dict) else {}
    source = (as_object(imported.get("import_source", {}))
              if isinstance(imported.get("import_source"), dict) else {})
    if not exported.get("sha256") or exported.get("sha256") != source.get("sha256"):
        reasons.append(f"the build recorded export SHA-256 {exported.get('sha256')!r} and the "
                       f"import read {source.get('sha256')!r}")
    steps = as_object(imported.get("steps", {}))
    check = as_object(steps.get("check", {})).get("verdict", NOT_RUN)
    if check != PASSED:
        reasons.append(f"`quickchick check` on the imported switch is {check}, not exit 0")
    for side, receipt in (("build", build), ("import", imported)):
        if receipt.get("switch") in (None, ""):
            reasons.append(f"the {side} receipt names no switch")
    if build.get("switch") != imported.get("switch"):
        reasons.append(f"the build's switch is {build.get('switch')!r} and the import's "
                       f"{imported.get('switch')!r}")
    built, taken = closure_of(build), closure_of(imported)
    closure_equal = built is not None and built == taken
    if built is None or taken is None:
        reasons.append("a receipt records no installed closure")
    elif not closure_equal:
        only_build = sorted(f"{p.name}.{p.version}" for p in set(built) - set(taken))
        only_import = sorted(f"{p.name}.{p.version}" for p in set(taken) - set(built))
        reasons.append(f"the installed closures differ: the build's alone holds "
                       f"{only_build or 'nothing'}, the import's alone {only_import or 'nothing'}")
    pins_equal = built is not None and taken is not None and pins_of(built) == pins_of(taken)
    if built is not None and taken is not None and not pins_equal:
        reasons.append(f"the pins differ: the build's {pins_of(built)}, the import's "
                       f"{pins_of(taken)}")
    observed = imported.get("reexport")
    return {"verdict": PASSED if not reasons else FAILED, "reasons": reasons,
            "check": check, "closure_equal": closure_equal, "pins_equal": pins_equal,
            "pins": {name: {"url": url, "commit": commit}
                     for name, (url, commit) in pins_of(taken or []).items()},
            "reexport": observed if isinstance(observed, dict) else None}


def cmd_compare(args: argparse.Namespace) -> int:
    build = load_json(args.build_receipt)
    if build is None:
        print(f"FAIL {args.build_receipt} holds no build receipt", file=sys.stderr)
        return 1
    imported = load_receipt(args.root)
    found = compare_import(build, imported, os.environ.get("GITHUB_RUN_ID", ""))
    update_receipt(args.root, comparison=found)
    for reason in cast("list[str]", found["reasons"]):
        print(f"   {reason}")
    observed = found.get("reexport")
    if isinstance(observed, dict):
        print(f"   observation: the re-export is "
              f"{'byte-identical to' if observed.get('identical') else 'not byte-identical to'}"
              " the build's export")
    print(f"{found['verdict']} the imported switch "
          f"{'is' if found['verdict'] == PASSED else 'is not'} the build's")
    return 0 if found["verdict"] == PASSED else 1


# ------------------------------------------------------------------------- the journal


@dataclass(frozen=True)
class Entry:
    """One journalled verdict: the mutant's site and rewrite as seed writes them."""

    index: int
    outcome: str
    site: str | None
    before: str | None
    after: str | None
    detail: str
    text: str

    @property
    def identity(self) -> str:
        if self.site is None:
            return self.text
        return f"{self.site} `{self.before}` -> `{self.after}`"


@dataclass(frozen=True)
class Journal:
    """A seed journal: its verdicts, whether it closes and on how many verdicts at what
    exit, and the scope its head states."""

    entries: list[Entry] = field(default_factory=list)
    complete: bool = False
    exit: int | None = None
    scope: str | None = None
    decided: int | None = None

    @property
    def picked(self) -> int | None:
        """How many mutants the head says the run picked, None where it says none."""
        found = _SCOPE_RE.match(self.scope or "")
        if found is None:
            return None
        return int(found["whole"] if found["whole"] is not None else found["ran"])


# The scope a journal's head states, as seed's `Scope.stated` words it: the whole
# population, or a sample of it.
_SCOPE_RE = re.compile(r"over (?:the whole population of (?P<whole>\d+)|(?P<ran>\d+) of \d+)"
                       r" mutant\(s\)")
_ENTRY_RE = re.compile(r"^\s*(\d+)  (\S+)\s+(.*)$")
_MUTANT_RE = re.compile(r"^(?P<site>\S+:\d+) `(?P<before>.*?)` -> `(?P<after>.*?)`: "
                        r"(?P<detail>.*)$", re.DOTALL)
_CLOSE_RE = re.compile(r"^== complete: (\d+) verdict\(s\) decided, exit (-?\d+)$")


def _entry(index: int, outcome: str, text: str) -> Entry:
    found = _MUTANT_RE.match(text)
    if found is None:
        head, _, detail = text.partition(": ")
        return Entry(index, outcome, None, None, None, detail, head)
    return Entry(index, outcome, found["site"], found["before"], found["after"],
                 found["detail"], text)


def parse_journal(text: str) -> Journal:
    """A seed journal: its verdicts in the order written, whether its closing line is
    there, and its scope. A line that opens no verdict continues the one before it."""
    entries: list[Entry] = []
    pending: tuple[int, str, list[str]] | None = None
    complete, code, scope, decided = False, None, None, None
    for line in text.splitlines():
        closing = _CLOSE_RE.match(line)
        opened = _ENTRY_RE.match(line)
        if (closing or opened or line.startswith("==")) and pending is not None:
            entries.append(_entry(pending[0], pending[1], "\n".join(pending[2])))
            pending = None
        if closing:
            complete, decided, code = True, int(closing.group(1)), int(closing.group(2))
        elif opened:
            pending = (int(opened.group(1)), str(opened.group(2)), [str(opened.group(3))])
        elif line.lstrip().startswith("scope:") and not entries and pending is None:
            scope = line.split("scope:", 1)[1].strip()
        elif pending is not None and not line.startswith("=="):
            pending[2].append(line)
    if pending is not None:
        entries.append(_entry(pending[0], pending[1], "\n".join(pending[2])))
    return Journal(entries, complete, code, scope, decided)


def journal_shortfall(journal: Journal) -> str | None:
    """Why a seed journal records no finished run, None where it does: a finished run's
    closing line counts every mutant its head picked, at seed's exit 0 or 1. A run whose
    baseline did not stand closes on none of them, and is no measurement."""
    if not journal.complete:
        return "its journal has no closing line"
    picked = journal.picked
    if picked is None:
        return "its journal's head states no scope"
    if picked < 1:
        return "its journal's head picks no mutant"
    if journal.decided != picked:
        return f"its journal closes on {journal.decided} of the {picked} mutant(s) it picked"
    if journal.exit not in (0, 1):
        return f"its journal closes at exit {journal.exit}"
    return None


# One sampled mutant as `seed list` prints it: its identifier, which leads with its
# operator, then its site and rewrite exactly as the journal writes them.
_LISTED_RE = re.compile(r"^ {5}(?P<ident>[\w.+-]+/\d+)\s+(?P<what>\S+:\d+ `.*` -> `.*`)$")


def parse_population(text: str) -> dict[str, list[str]]:
    """Each listed mutant's operator by its site and rewrite, the journal's identity;
    one site and rewrite two operators share lists both."""
    found: dict[str, list[str]] = {}
    for line in text.splitlines():
        matched = _LISTED_RE.match(line)
        if matched is not None:
            operator = matched["ident"].rsplit("/", 1)[0]
            found.setdefault(matched["what"], []).append(operator)
    return found


# ---------------------------------------------------------------------------- the join

# One artifact per job, named for its job and its side's revision; the plan's carries
# the requested revision where it was a full commit and `unnamed` otherwise. The join's
# own, from an earlier attempt of this run, is not one the join reads.
ARTIFACT_RE = re.compile(r"instrument-(plan|build|import|join|seed-base|seed-candidate-1"
                         r"|seed-candidate-2)-([0-9a-f]{40}|unnamed)")
KNOWN_OUTCOMES: frozenset[str] = frozenset({"killed", "survived", "stillborn", "unseeded"})


def artifact_name(key: str, revision: str) -> str:
    return f"instrument-{key}-{revision}"


def _job_of(key: str) -> str:
    return "seed" if key.startswith("seed-") else key


def _verdict_of(steps: dict[str, object], job: str) -> str:
    verdicts = [str(as_object(steps.get(step, {})).get("verdict", NOT_RUN))
                for step in JOB_STEPS[job]]
    if FAILED in verdicts:
        return FAILED
    if UNDECIDED in verdicts:
        return UNDECIDED
    if NOT_RUN in verdicts:
        return NOT_RUN
    return PASSED


def _failed_outside(key: str, steps: dict[str, object], result: str) -> bool:
    """Whether a job failed outside the steps the wrapper records: its result is failure
    and none of its wrapped steps failed or was undecided, as where a guard, an action or
    a download ended it. A seed run's result is its matrix's, failed where any run
    failed, so one run is held to it only where a step of its own never ran."""
    if result != "failure":
        return False
    verdicts = {str(as_object(steps.get(step, {})).get("verdict", NOT_RUN))
                for step in JOB_STEPS[_job_of(key)]}
    if not verdicts <= {PASSED, COMPLETED, NOT_RUN}:
        return False
    return NOT_RUN in verdicts or _job_of(key) != "seed"


def _expected(plan_json: dict[str, object]) -> list[str]:
    keys = ["build", "import"]
    if plan_json.get("seed") is True:
        keys += [f"seed-{run}" for run in SEED_RUNS]
    return keys


def _side_of(key: str) -> str:
    return "base" if key == "seed-base" else "candidate"


def _side_revision(key: str, request: dict[str, object]) -> str:
    field_name = "base_revision" if key == "seed-base" else "revision"
    return str(request.get(field_name, ""))


def _receipt_refusals(key: str, receipt: dict[str, object], plan_json: dict[str, object],
                      run_id: str, revision: str) -> list[str]:
    """What makes a job's receipt disagree with the plan and the run it claims."""
    request = as_object(plan_json.get("request", {}))
    subjects = (as_object(plan_json.get("subjects", {}))
                if isinstance(plan_json.get("subjects"), dict) else {})
    refusals: list[str] = []
    job = _job_of(key)
    if receipt.get("job") != job:
        refusals.append(f"{key}'s receipt names job {receipt.get('job')!r}")
    if job == "seed" and receipt.get("run") != key.removeprefix("seed-"):
        refusals.append(f"{key}'s receipt names seed run {receipt.get('run')!r}")
    if receipt.get("run_id") != run_id:
        refusals.append(f"{key}'s receipt names run {receipt.get('run_id')!r}, not {run_id}")
    if receipt.get("dispatching_commit") != plan_json.get("dispatching_commit"):
        refusals.append(f"{key}'s receipt names another dispatching commit")
    inputs = as_object(receipt.get("inputs", {})) if isinstance(receipt.get("inputs"), dict) else {}
    side = _side_of(key)
    wanted: dict[str, object] = {
        "side": side, "revision": request.get("revision"),
        "base_revision": request.get("base_revision"), "build": request.get("build"),
        "sample": request.get("sample")}
    if job == "seed":
        wanted["subject"] = subjects.get(side)
    refusals += [f"{key}'s receipt records {name} {inputs.get(name)!r}, the plan {value!r}"
                 for name, value in wanted.items() if inputs.get(name) != value]
    tested = receipt.get("source_revision")
    steps = as_object(receipt.get("steps", {})) if isinstance(receipt.get("steps"), dict) else {}
    provisioned = as_object(steps.get("provision", steps.get("import", {}))).get("verdict")
    if tested is None and provisioned not in (None, NOT_RUN):
        refusals.append(f"{key}'s receipt records no tested revision")
    elif tested is not None and tested != revision:
        refusals.append(f"{key}'s receipt tested {tested!r}, not {revision}")
    return refusals


def _by_identity(journal: Journal) -> dict[str, list[Entry]]:
    grouped: dict[str, list[Entry]] = {}
    for entry in journal.entries:
        grouped.setdefault(entry.identity, []).append(entry)
    return grouped


def _differences(runs: dict[str, Journal], left: str, right: str) -> list[dict[str, object]]:
    """Each mutant whose verdicts differ between two runs, by its identity."""
    if left not in runs or right not in runs:
        return []
    found: list[dict[str, object]] = []
    sides = {name: _by_identity(runs[name]) for name in (left, right)}
    for identity in sorted(set(sides[left]) | set(sides[right])):
        a = sorted(sides[left].get(identity, []), key=lambda entry: entry.outcome)
        b = sorted(sides[right].get(identity, []), key=lambda entry: entry.outcome)
        if [entry.outcome for entry in a] != [entry.outcome for entry in b]:
            found.append({"mutant": identity,
                          left: [{"verdict": e.outcome, "reason": e.detail} for e in a],
                          right: [{"verdict": e.outcome, "reason": e.detail} for e in b]})
    return found


def _artifacts(artifacts: Path, refusals: list[str]) -> dict[str, Path]:
    """One artifact directory per job key, refusing a name the route does not give and a
    second artifact for one job; the join's own is passed over."""
    found: dict[str, Path] = {}
    names = (sorted(path.name for path in artifacts.iterdir() if path.is_dir())
             if artifacts.is_dir() else [])
    for name in names:
        matched = ARTIFACT_RE.fullmatch(name)
        if matched is None:
            refusals.append(f"an artifact this route does not name: {name}")
            continue
        key = matched.group(1)
        if key == "join":
            continue
        if key in found:
            refusals.append(f"duplicate artifacts for the {key} job: {found[key].name} and {name}")
            continue
        found[key] = artifacts / name
    return found


def _seed_report(journals: dict[str, Journal],
                 operators: dict[str, list[str]]) -> dict[str, object]:
    identities = sorted({entry.identity for journal in journals.values()
                         for entry in journal.entries})
    mutants: list[dict[str, object]] = []
    for identity in identities:
        first = next(entry for journal in journals.values() for entry in journal.entries
                     if entry.identity == identity)
        mutants.append({
            "mutant": identity, "site": first.site, "rewrite": (
                None if first.site is None else f"`{first.before}` -> `{first.after}`"),
            "operator": sorted(set(operators.get(identity, []))) or None,
            **{run: [entry.outcome for entry in _by_identity(journal).get(identity, [])]
               for run, journal in journals.items()}})
    return {
        "runs": {run: {"complete": journal.complete, "exit": journal.exit,
                       "scope": journal.scope, "picked": journal.picked,
                       "decided": journal.decided, "verdicts": len(journal.entries),
                       "shortfall": journal_shortfall(journal)}
                 for run, journal in journals.items()},
        "mutants": mutants,
        "candidate_differences": _differences(journals, "candidate-1", "candidate-2"),
        "base_differences": [*_differences(journals, "base", "candidate-1"),
                             *_differences(journals, "base", "candidate-2")],
        "other_verdicts": [{"run": run, "mutant": entry.identity, "verdict": entry.outcome,
                            "reason": entry.detail}
                           for run, journal in journals.items() for entry in journal.entries
                           if entry.outcome not in KNOWN_OUTCOMES],
    }


def join(artifacts: Path, needs: dict[str, object], run_id: str) -> dict[str, object]:
    """The run's report from one artifact per job: each job's verdict or why it did not
    run, each seed run's verdicts, and every disagreement a reader acts on."""
    refusals: list[str] = []
    found = _artifacts(artifacts, refusals)
    plan_json: dict[str, object] = {}
    if "plan" not in found:
        refusals.append("no plan artifact, so the run's inputs are unknown")
    else:
        loaded = load_json(found["plan"] / PLAN)
        if loaded is None:
            refusals.append("the plan artifact holds no readable plan.json")
        else:
            plan_json = loaded
            if plan_json.get("run_id") != run_id:
                refusals.append(f"the plan names run {plan_json.get('run_id')!r}, not {run_id}")
    request = (as_object(plan_json.get("request", {}))
               if isinstance(plan_json.get("request"), dict) else {})
    jobs: dict[str, dict[str, object]] = {}
    receipts_by_key: dict[str, dict[str, object]] = {}
    journals: dict[str, Journal] = {}
    operators: dict[str, list[str]] = {}
    for key in _expected(plan_json) if plan_json else []:
        need = needs.get(_job_of(key), {})
        result = str(as_object(need).get("result", "skipped")) if isinstance(need, dict) else "skipped"
        ran = result in {"success", "failure", "cancelled"}
        revision = _side_revision(key, request)
        if not ran:
            if key in found:
                refusals.append(f"an artifact from the {key} job, which did not run")
            why = ("its prerequisite, the build job, exported no switch whose checks all "
                   "passed" if key == "import" else f"the job's result is {result}")
            jobs[key] = {"verdict": NOT_RUN, "result": result, "reason": why}
            continue
        if key not in found:
            refusals.append(f"the {key} job ran ({result}) and left no artifact")
            continue
        if found[key].name != artifact_name(key, revision):
            refusals.append(f"the {key} job's artifact {found[key].name} is not named for "
                            f"its side's revision {revision}")
        receipt = load_json(found[key] / RECEIPT)
        if receipt is None:
            refusals.append(f"the {key} job's artifact holds no readable receipt")
            continue
        refusals += _receipt_refusals(key, receipt, plan_json, run_id, revision)
        receipts_by_key[key] = receipt
        steps = as_object(receipt.get("steps", {})) if isinstance(receipt.get("steps"), dict) else {}
        outside = _failed_outside(key, steps, result)
        jobs[key] = {
            "verdict": FAILED if outside else _verdict_of(steps, _job_of(key)),
            **({"reason": "the job failed outside its wrapped steps, so no instrument step "
                          "decided it"} if outside else {}),
            "result": result,
            "artifact": found[key].name, "source_revision": receipt.get("source_revision"),
            "runner_image": receipt.get("runner_image"), "uname_m": receipt.get("uname_m"),
            "opam_client": receipt.get("opam_client"), "switch": receipt.get("switch"),
            "flag": receipt.get("flag"), "recipe": receipt.get("recipe"),
            "steps": {step: {name: as_object(steps.get(step, {})).get(name) for name in
                             ("verdict", "reason", "exit", "limit_s", "seconds", "peak_rss_kb")}
                      for step in JOB_STEPS[_job_of(key)]},
        }
        if key == "build":
            exported = receipt.get("export")
            jobs[key]["export"] = exported if isinstance(exported, dict) else None
        if key == "import":
            compared = receipt.get("comparison")
            jobs[key]["comparison"] = compared if isinstance(compared, dict) else None
        if _job_of(key) == "seed":
            text = _read(found[key] / "seed" / Path(JOURNAL).name)
            if text is not None:
                journals[key.removeprefix("seed-")] = parse_journal(text)
            listed = _read(found[key] / "population.log")
            if listed is not None:
                for identity, names in parse_population(listed).items():
                    operators.setdefault(identity, []).extend(names)
    seed = _seed_report(journals, operators) if journals else {}
    pairs: list[dict[str, object]] = []
    keys = sorted(receipts_by_key)
    for index, left in enumerate(keys):
        for right in keys[index + 1:]:
            for name in ("opam_client", "runner_image"):
                a, b = receipts_by_key[left].get(name), receipts_by_key[right].get(name)
                if a != b:
                    pairs.append({"sides": [left, right], "field": name, left: a, right: b})
    verdicts = {str(job.get("verdict")) for job in jobs.values()}
    if refusals:
        verdict = REFUSED
    elif FAILED in verdicts:
        verdict = FAILED
    elif UNDECIDED in verdicts:
        verdict = UNDECIDED
    elif NOT_RUN in verdicts:
        verdict = INCOMPLETE
    else:
        verdict = PASSED
    return {"schema": 1, "run_id": run_id, "verdict": verdict, "refusals": refusals,
            "request": request, "dispatching_commit": plan_json.get("dispatching_commit"),
            "jobs": jobs, "seed": seed, "differing_sides": pairs}


def _cell(value: object) -> str:
    return html.escape(str(value)).replace("|", "&#124;").replace("\r", " ").replace("\n", " ")


def summary(report: dict[str, object]) -> str:
    """The job summary: each step's verdict, each sampled mutant's verdict in every seed
    run, each difference, and each pair of sides whose client or image differs."""
    request = as_object(report.get("request", {}))
    lines = [f"### Instrument switch route: {report.get('verdict')}", "",
             f"Revision `{request.get('revision')}`, base "
             f"`{request.get('base_revision') or 'none'}`, build `{request.get('build')}`, "
             f"sample {request.get('sample')}; dispatched from "
             f"`{report.get('dispatching_commit')}`."]
    refusals = cast("list[str]", report.get("refusals", []))
    if refusals:
        lines += ["", "Refused:", *(f"- {_cell(item)}" for item in refusals)]
    lines += ["", "| Job | Step | Verdict | Limit s | Seconds | Peak RSS kB | Reason |",
              "| --- | --- | --- | --- | --- | --- | --- |"]
    limited: list[str] = []
    for key, raw in as_object(report.get("jobs", {})).items():
        job = as_object(raw)
        steps = as_object(job.get("steps", {}))
        if not steps or job.get("reason"):
            lines.append(f"| {key} | | {job.get('verdict')} | | | | "
                         f"{_cell(job.get('reason', ''))} |")
        for step, rows in steps.items():
            row = as_object(rows)
            lines.append(f"| {key} | {step} | {row.get('verdict')} | {row.get('limit_s')} | "
                         f"{row.get('seconds')} | {row.get('peak_rss_kb')} | "
                         f"{_cell(row.get('reason') or '')} |")
            if step == "seed" and "reached its limit" in str(row.get("reason") or ""):
                limited.append(key)
    if limited:
        lines += ["", f"A seed step reached its limit ({', '.join(limited)}): the next "
                  "dispatch raises `--jobs` on the build job's recorded `quickchick "
                  "properties` peak or records the runner decision as owed to the user, "
                  "the sample staying 20."]
    seed = as_object(report.get("seed", {}))
    if seed:
        runs = list(as_object(seed.get("runs", {})))
        lines += ["", "| Mutant (site and rewrite) | Operator | " + " | ".join(runs) + " |",
                  "| --- | --- | " + " | ".join("---" for _ in runs) + " |"]
        for raw in as_list(seed.get("mutants", [])):
            mutant = as_object(raw)
            cells = [", ".join(cast("list[str]", mutant.get(run, []))) or "absent" for run in runs]
            operator = mutant.get("operator")
            named = ", ".join(cast("list[str]", operator)) if isinstance(operator, list) else (
                "not listed")
            lines.append(f"| {_cell(mutant.get('mutant'))} | {_cell(named)} | "
                         + " | ".join(cells) + " |")
        for title, name in (("Differing between the candidate runs", "candidate_differences"),
                            ("Differing between base and candidate", "base_differences"),
                            ("Journalled with another verdict", "other_verdicts")):
            items = as_list(seed.get(name, []))
            if items:
                lines += ["", f"{title}:", *(f"- {_cell(json.dumps(item, sort_keys=True))}"
                                             for item in items)]
    pairs = as_list(report.get("differing_sides", []))
    if pairs:
        lines += ["", "Sides whose opam client or runner image differ:",
                  *(f"- {_cell(json.dumps(item, sort_keys=True))}" for item in pairs)]
    return "\n".join(lines) + "\n"


def cmd_join(args: argparse.Namespace) -> int:
    needs = as_object(json.loads(os.environ.get("NEEDS", "{}") or "{}"))
    report = join(args.artifacts, needs, os.environ.get("GITHUB_RUN_ID", ""))
    receipts.write(args.root / LOGS / REPORT, report)
    text = summary(report)
    print(text)
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with Path(target).open("a", encoding="utf-8", newline="") as stream:
            stream.write(text)
    return 1 if report["verdict"] == REFUSED else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="the job's private root (default: ~/verifiedos-instrument)")
    subs = parser.add_subparsers(dest="command", required=True)
    planning = subs.add_parser("plan", help="refuse a dispatch before any revision is checked out")
    planning.add_argument("--checkout", type=Path, default=TOOLS.parent,
                          help="the dispatching commit's checkout (default: this one)")
    stepping = subs.add_parser("step", help="run one step under its limit, sampled")
    stepping.add_argument("step", choices=sorted(LIMITS))
    stepping.add_argument("--journal", action="store_true",
                          help="the step is decided by seed's journal under the root")
    stepping.add_argument("argv", nargs=argparse.REMAINDER)
    instrumenting = subs.add_parser("instrument", help="run one of the side's instruments "
                                    "under its limit, with the flag its build calls for")
    instrumenting.add_argument("step", choices=INSTRUMENTS)
    instrumenting.add_argument("--side", type=Path, required=True,
                               help="the side revision's checkout")
    staging = subs.add_parser("stage", help="stage the allowlist for upload")
    staging.add_argument("--job", required=True, choices=sorted(JOB_STEPS))
    comparing = subs.add_parser("compare", help="hold the imported switch to the build's")
    comparing.add_argument("--build-receipt", type=Path, required=True)
    joining = subs.add_parser("join", help="join one artifact per job into report.json")
    joining.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args(argv)
    handlers: dict[str, Callable[[argparse.Namespace], int]] = {
        "plan": cmd_plan, "step": cmd_step, "instrument": cmd_instrument, "stage": cmd_stage,
        "compare": cmd_compare, "join": cmd_join}
    try:
        return handlers[args.command](args)
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
        print(f"FAIL {args.command}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
