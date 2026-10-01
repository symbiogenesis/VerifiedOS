# SPDX-License-Identifier: Apache-2.0
"""The instrument switch route's plan, limits, wrapper, sampler, staging, comparison
and join, each held to its refusals on fixtures, and the workflow to the module."""

import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import cast
from unittest.mock import patch

from ci import instrument_route as route
from tests.harness import Case, ensure, sandbox_tree
from vos import mutate, seeded

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / route.WORKFLOW
RUN_ID = "4242"
DISPATCH = "d" * 40
REVISION = "a" * 40
BASE = "b" * 40

_INSTALL = 'INSTALL = (("opam", "switch", "create", "s"),)\n'
_RECIPE = 'RECIPE = (("opam", "switch", "create", "r"),)\n'
_SEED = 'COQ_SUBJECT = "proofs/CyclicExecutive.v"\n'


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                          check=False, timeout=60)
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout.strip()


def _commit(root: Path, files: dict[str, str], message: str) -> str:
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="")
        _git(root, "add", rel)
    _git(root, "commit", "--allow-empty", "-qm", message)
    return _git(root, "rev-parse", "HEAD")


@contextmanager
def _history() -> Iterator[tuple[Path, dict[str, str]]]:
    """main at base then tip, the tip declaring RECIPE, and a sibling never on main."""
    with sandbox_tree({"README.md": "fixture\n"}) as root:
        for key, value in (("user.name", "Fixture"), ("user.email", "fixture@example.invalid"),
                           ("commit.gpgsign", "false")):
            _git(root, "config", key, value)
        base = _commit(root, {route.QUICKCHICK: _INSTALL, route.SEED: _SEED}, "base")
        tip = _commit(root, {route.QUICKCHICK: _INSTALL + _RECIPE}, "tip")
        _git(root, "checkout", "-q", "--detach", base)
        sibling = _commit(root, {"README.md": "sibling\n"}, "sibling")
        nested = _commit(root, {route.QUICKCHICK: _INSTALL + "if True:\n    " + _RECIPE},
                         "recipe nested")
        _git(root, "checkout", "-q", "--detach", tip)
        yield root, {"base": base, "tip": tip, "sibling": sibling, "nested": nested}


def _request(commits: dict[str, str], **changes: str) -> route.Request:
    fields = {"ref": route.MAIN, "dispatching_commit": commits["tip"],
              "revision": commits["tip"], "base_revision": "", "build": "install",
              "sample": "20", "title": ""}
    return route.Request(**(fields | changes))


def _verdicts(checks: list[route.Check]) -> dict[str, str]:
    return {check.check: check.verdict for check in checks}


def _plan_accepts_main_revisions() -> None:
    with _history() as (root, commits):
        for asked in (_request(commits),
                      _request(commits, build="recipe"),
                      _request(commits, base_revision=commits["base"], sample="1")):
            checks = route.plan(root, asked)
            ensure(route.accepted(checks), f"a main revision is accepted: {checks!r}")
        record = route.plan_record(root, _request(commits, base_revision=commits["base"]),
                                   route.plan(root, _request(commits,
                                                             base_revision=commits["base"])))
        ensure(record["seed"] is True and record["subjects"] == {
            "candidate": "proofs/CyclicExecutive.v", "base": "proofs/CyclicExecutive.v"},
               f"the plan reads each side's subject from source: {record!r}")


def _plan_refuses_each_bad_request() -> None:
    with _history() as (root, commits):
        tip, base = commits["tip"], commits["base"]
        cases: list[tuple[route.Request, str, str]] = [
            (_request(commits, ref="refs/heads/work/lane"), "ref", "only from"),
            (_request(commits, revision=""), "revision", "no revision"),
            (_request(commits, revision=tip[:12]), "revision", "not a full lowercase"),
            (_request(commits, revision=tip.upper()), "revision", "not a full lowercase"),
            (_request(commits, revision="e" * 40), "revision", "no commit the dispatching"),
            (_request(commits, revision=commits["sibling"]), "revision", "not on main"),
            (_request(commits, base_revision=tip), "base_revision", "the revision itself"),
            (_request(commits, revision=base, base_revision=tip), "base_revision",
             "not an ancestor"),
            (_request(commits, base_revision=commits["sibling"]), "base_revision",
             "not an ancestor"),
            (_request(commits, base_revision=base[:7]), "base_revision", "not a full"),
            (_request(commits, build="certirocq"), "build", "neither install nor recipe"),
            (_request(commits, revision=base, build="recipe"), "recipe", "declares no `RECIPE`"),
            (_request(commits, dispatching_commit=base), "route", "not the dispatching commit"),
        ]
        cases += [(_request(commits, sample=sample), "sample", "not a whole number")
                  for sample in ("21", "0", "020", "-1", "+5", "1.0", "", "twenty")]
        # An annotated tag's object names a commit on main once peeled, and is not one.
        _git(root, "-c", "tag.gpgSign=false", "tag", "-a", "-m", "tip", "tagged-tip", tip)
        _git(root, "-c", "tag.gpgSign=false", "tag", "-a", "-m", "base", "tagged-base", base)
        tag_tip = _git(root, "rev-parse", "tagged-tip")
        tag_base = _git(root, "rev-parse", "tagged-base")
        ensure(tag_tip != tip and tag_base != base, "each tag is an object of its own")
        cases += [(_request(commits, revision=tag_tip), "revision", "no commit the dispatching"),
                  (_request(commits, base_revision=tag_base), "base_revision",
                   "not an ancestor")]
        for asked, check, fragment in cases:
            checks = route.plan(root, asked)
            found = [c for c in checks if c.check == check]
            ensure(not route.accepted(checks) and bool(found) and found[0].verdict == route.REFUSED
                   and fragment in found[0].reason,
                   f"{asked!r} must be refused at {check} ({fragment!r}): {checks!r}")
        # A RECIPE bound only inside a block is not declared at the module's top level.
        _git(root, "update-ref", "refs/heads/main", commits["nested"])
        nested = route.plan(root, _request(commits, dispatching_commit=commits["nested"],
                                           revision=commits["nested"], build="recipe"))
        ensure(_verdicts(nested).get("route") == route.REFUSED
               and _verdicts(nested).get("recipe") == route.REFUSED,
               f"a nested RECIPE is no declaration: {nested!r}")
    for source, expected in (
            ('RECIPE = (("opam", "switch"),)\n', True),
            ('RECIPE: tuple[tuple[str, ...], ...] = (("opam",), *((s,) for s in X))\n', True),
            ('RECIPE = [("opam",)]\n', True),
            ("RECIPE = None\n", False), ("RECIPE = ()\n", False), ("RECIPE = []\n", False),
            ("RECIPE = make()\n", False), ("RECIPE: tuple[str, ...]\n", False),
            ("if True:\n    RECIPE = (('opam',),)\n", False), ("print(RECIPE)\n", False)):
        ensure(route.declares(source, "RECIPE") is expected,
               f"a recipe is declared only as a non-empty tuple or list literal: {source!r}")


def _plan_ref_reads_fetched_main() -> None:
    # A dispatch from another ref is refused, and its revision is still held to main as
    # the checkout fetched it rather than to the other ref's tip.
    with _history() as (root, commits):
        _git(root, "update-ref", route.REMOTE_MAIN, commits["tip"])
        checks = route.plan(root, _request(commits, ref="refs/heads/other"))
        verdicts = _verdicts(checks)
        ensure(verdicts["ref"] == route.REFUSED and verdicts["revision"] == route.HOLDS,
               f"the ref is refused and the revision read against main: {checks!r}")
        checks = route.plan(root, _request(commits, ref="refs/heads/other",
                                           revision=commits["sibling"]))
        ensure(_verdicts(checks)["revision"] == route.REFUSED,
               f"a sibling is not on main from another ref either: {checks!r}")


def _plan_outputs_only_validated_values() -> None:
    with _history() as (root, commits):
        refused = _request(commits, revision="x; rm -rf /", sample="21")
        outputs = route.plan_outputs(refused, route.accepted(route.plan(root, refused)))
        ensure(outputs == {"accepted": "false", "label": "unnamed"},
               f"a refused plan hands later jobs nothing it read: {outputs!r}")
        asked = _request(commits, base_revision=commits["base"])
        record = route.plan_record(root, asked, route.plan(root, asked))
        outputs = route.plan_outputs(asked, True,
                                     cast("dict[str, str | None]", record["subjects"]))
        ensure(outputs["seed"] == "true" and outputs["sample"] == "20"
               and outputs["revision"] == commits["tip"]
               and outputs["subject"] == outputs["base_subject"] == "proofs/CyclicExecutive.v",
               f"accepted outputs, each side's subject read from its source: {outputs!r}")
        environment = {"INSTRUMENT_SIDE": "base", "INSTRUMENT_SUBJECT": "proofs/C.v",
                       "INSTRUMENT_BASE_SUBJECT": "proofs/B.v"}
        with patch.dict(os.environ, environment), tempfile.TemporaryDirectory() as scratch:
            base = route.as_object(route.base_receipt(Path(scratch))["inputs"])
            with patch.dict(os.environ, {"INSTRUMENT_SIDE": "candidate"}):
                candidate = route.as_object(route.base_receipt(Path(scratch))["inputs"])
        ensure(base["subject"] == "proofs/B.v" and candidate["subject"] == "proofs/C.v",
               f"a receipt records its side's subject from its start: {base!r}, {candidate!r}")
        with tempfile.TemporaryDirectory() as scratch:
            target = Path(scratch) / "out"
            try:
                route.github_output({"label": "a\nb"}, target)
            except ValueError:
                pass
            else:
                raise AssertionError("a two-line output must be refused")


def _plan_command_records_and_exits() -> None:
    with _history() as (root, commits), tempfile.TemporaryDirectory() as scratch:
        for revision, code in ((commits["tip"], 0), (commits["sibling"], 1)):
            output = Path(scratch) / f"output-{code}"
            environment = {"GITHUB_REF": route.MAIN, "GITHUB_SHA": commits["tip"],
                           "PLAN_REVISION": revision, "PLAN_BASE_REVISION": "",
                           "PLAN_BUILD": "install", "PLAN_SAMPLE": "20", "PLAN_TITLE": "t",
                           "GITHUB_OUTPUT": str(output), "GITHUB_RUN_ID": RUN_ID}
            job_root = Path(scratch) / f"root-{code}"
            with patch.dict(os.environ, environment), redirect_stdout(StringIO()):
                found = route.main(["--root", str(job_root), "plan", "--checkout", str(root)])
            record = route.load_json(job_root / route.LOGS / route.PLAN)
            ensure(found == code and record is not None and record["accepted"] is (code == 0)
                   and record["run_id"] == RUN_ID,
                   f"the plan writes plan.json and exits {code}: {found}, {record!r}")
            written = output.read_text(encoding="utf-8")
            ensure(f"accepted={'true' if code == 0 else 'false'}" in written
                   and ("subject=proofs/CyclicExecutive.v\n" in written) is (code == 0),
                   f"the plan's outputs reach GITHUB_OUTPUT: {written!r}")


def _limits_and_minutes() -> None:
    for name, limit in route.LIMITS.items():
        ensure(limit.seconds > 0 and bool(limit.basis), f"{name} states a limit and its basis")
    ensure(not route.LIMITS["seed"].measured and route.LIMITS["provision"].measured
           and "4,402" in route.LIMITS["provision"].basis
           and "378" in route.LIMITS["properties"].basis
           and "unmeasured" in route.LIMITS["seed"].basis,
           "the build's limit stands on Q38f's import, properties' on Q38e's run, and the "
           "seed step's is marked unmeasured")
    for job in route.JOB_STEPS:
        ensure(route.job_minutes(job) <= route.HOSTED_MAXIMUM - route.HOSTED_MARGIN,
               f"{job} fits GitHub's hosted maximum less the margin")
        steps = sum(route.LIMITS[step].seconds for step in route.JOB_STEPS[job])
        ensure(route.job_minutes(job) * 60 >= steps + route.STAGING_MARGIN * 60,
               f"{job}'s minutes hold its step limits and the staging margin")
    ensure(route.job_minutes("seed") == route.HOSTED_MAXIMUM - route.HOSTED_MARGIN,
           "the seed job is its own limit")
    for step, limit in route.LIMITS.items():
        ensure(route.backstop_minutes(step) * 60 > limit.seconds + route.KILL_AFTER,
               f"{step}'s backstop stands above its limit and timeout's grace")


def _workflow_jobs() -> dict[str, str]:
    text = WORKFLOW.read_text(encoding="utf-8")
    body = text.split("\njobs:\n", 1)[1]
    names = re.findall(r"(?m)^  ([a-z][\w-]*):\n", body)
    blocks = re.split(r"(?m)^  [a-z][\w-]*:\n", body)[1:]
    return dict(zip(names, blocks, strict=True))


def _workflow_holds_the_module_limits() -> None:
    jobs = _workflow_jobs()
    ensure(set(jobs) == set(route.JOB_STEPS), f"the workflow's jobs are the module's: {set(jobs)}")
    step_ids = {"import": {"import": "import", "check": "check", "compare": "compare"}}
    for job, block in jobs.items():
        minutes = re.search(r"(?m)^    timeout-minutes: (\d+)$", block)
        ensure(minutes is not None and int(minutes[1]) == route.job_minutes(job),
               f"{job}'s timeout-minutes is the module's {route.job_minutes(job)}")
        found = dict(re.findall(r"(?m)^        id: ([\w-]+)\n(?:        (?!timeout)[^\n]*\n)*?"
                                r"        timeout-minutes: (\d+)$", block))
        for step in route.JOB_STEPS[job]:
            name = step_ids.get(job, {}).get(step, step)
            ensure(name in found and int(found[name]) == route.backstop_minutes(step),
                   f"{job}'s {step} step backstops at {route.backstop_minutes(step)} "
                   f"minutes: {found!r}")
        ensure(re.search(r"(?m)^    runs-on: ubuntu-26\.04$", block) is not None,
               f"{job} runs on ubuntu-26.04")


def _readme_holds_the_module_constants() -> None:
    # The contract restates the module's figures in prose; each is held to its constant.
    text = (ROOT / "tools" / "ci" / "README.md").read_text(encoding="utf-8")
    section = text.split("\n## Instrument switch route\n", 1)[1].split("\n## ", 1)[0]
    flat = " ".join(section.split())
    first, last = route.SAMPLES.start, route.SAMPLES.stop - 1
    suffixes = (", ".join(f"`{suffix}`" for suffix in route.ALLOWED_SUFFIXES[:-1])
                + f" and `{route.ALLOWED_SUFFIXES[-1]}`")
    ensure(route.ARCHIVE_LIMIT % (1 << 20) == 0 and route.FILE_LIMIT % (1 << 20) == 0,
           "the archive and file bounds are whole MiB")
    for phrase in (f"Q38f's {route.IMPORT_MEASURED:,} s import",
                   f"Q38e's {route.PROPERTIES_MEASURED} s",
                   f"GitHub's {route.HOSTED_MAXIMUM}-minute hosted maximum less a "
                   f"{route.HOSTED_MARGIN}-minute margin",
                   f"a {route.STAGING_MARGIN}-minute staging-and-upload margin",
                   f"more than {route.ARCHIVE_LIMIT >> 20} MiB",
                   f"holds more than {route.FILE_LIMIT >> 20} MiB",
                   f"the artifact past {route.ARCHIVE_LIMIT >> 20} MiB",
                   f"a whole number from {first} to {last}, default {route.FULL_SAMPLE}",
                   f"a `sample` outside {first} to {last}",
                   f"the sample stays {route.FULL_SAMPLE}",
                   f"whose sample is not {route.FULL_SAMPLE}",
                   f"allowlist of {suffixes} files"):
        ensure(phrase in flat, f"the route's contract states the module's figure: {phrase!r}")


def _workflow_contract_shape() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    body = "\n".join(lines)
    triggers = text.split("\non:\n", 1)[1].split("\npermissions:", 1)[0]
    ensure(re.findall(r"(?m)^  ([a-z_]+):", triggers) == ["workflow_dispatch"],
           "dispatch is the only trigger: no push or schedule")
    ensure("\npermissions:\n  contents: read\n" in text and not re.search(r":\s*write\b", body),
           "the workflow reads contents and writes nothing")
    ensure("group: ${{ github.workflow }}-${{ github.run_id }}\n  cancel-in-progress: false"
           in text, "one concurrency group per run, cancelling nothing")
    ensure("certirocq" not in body.lower(), "no CertiRocq input, job or step")
    for line in lines:
        if "inputs." in line:
            ensure(re.match(r"\s+PLAN_[A-Z_]+: \$\{\{ inputs\.\w+ \}\}$", line) is not None
                   or line.startswith("run-name:"),
                   f"an input reaches a step only through its environment: {line!r}")
    inputs = re.findall(r"(?m)^      ([a-z_]+):\n        description:", text)
    ensure(inputs == ["revision", "base_revision", "build", "sample", "title"],
           f"the inputs are the contract's: {inputs!r}")
    ensure(f'default: "{route.FULL_SAMPLE}"' in text
           and "".join(f"          - {build}\n" for build in route.BUILDS) in text,
           "sample defaults to the full sample and build is a choice of install or recipe")
    uploads = re.findall(r"(?m)uses: actions/upload-artifact@[0-9a-f]{40} # v[\d.]+\n"
                         r"        with:\n          name: (instrument-[^\n]+)$", text)
    ensure(len(uploads) == 5 and not any("attempt" in name for name in uploads),
           f"each job's artifact is named for its job and revision alone: {uploads!r}")
    ensure(body.count("retention-days: 30") == 5 and body.count("overwrite: true") == 5,
           "each artifact is replaced on a rerun and kept 30 days")
    for job, block in _workflow_jobs().items():
        staged = re.search(r"- name: Stage[^\n]*\n        if: \$\{\{ always\(\) \}\}", block)
        kept = re.search(r"- name: Preserve[^\n]*\n(?:        #[^\n]*\n)*"
                         r"        if: \$\{\{ always\(\) \}\}", block)
        ensure(staged is not None and kept is not None,
               f"{job} stages and uploads under always()")
        ensure(f"stage --job {job}" in block, f"{job} stages under its own name")
    ensure("actions/cache" not in body and "save-cache: false" in body,
           "no cache but the read-only uv cache")
    # What starts each later job: a refused plan starts none, the import only a build
    # that exported, the seed jobs only a base revision, and the join any run the plan
    # accepted and nobody cancelled.
    gates = {job: re.findall(r"(?m)^    if: (.+)$", block)
             for job, block in _workflow_jobs().items()}
    ensure(gates == {
        "plan": [],
        "build": ["${{ needs.plan.outputs.accepted == 'true' }}"],
        "import": ["${{ needs.build.result == 'success' "
                   "&& needs.build.outputs.export_sha256 != '' }}"],
        "seed": ["${{ needs.plan.outputs.seed == 'true' }}"],
        "join": ["${{ !cancelled() && needs.plan.result == 'success' }}"]},
           f"each later job starts only where the plan lets it: {gates!r}")


def _classify_records_undecided() -> None:
    limit = 60
    cases = [
        (route.classify(124, limit, oom=[], lowest_free_disk=None), route.UNDECIDED, "limit"),
        (route.classify(137, limit, oom=[], lowest_free_disk=None), route.UNDECIDED,
         "recorded no OOM"),
        (route.classify(137, limit, oom=None, lowest_free_disk=None), route.UNDECIDED,
         "could not be read"),
        (route.classify(1, limit, oom=["Out of memory: Killed process 7"],
                        lowest_free_disk=None), route.UNDECIDED, "OOM killer"),
        (route.classify(2, limit, oom=[], lowest_free_disk=1024), route.UNDECIDED,
         "short of disk"),
        (route.classify(2, limit, oom=[], lowest_free_disk=None, no_space=True),
         route.UNDECIDED, "no space left"),
        (route.classify(1, limit, oom=[], lowest_free_disk=None, prover_timeout=True),
         route.UNDECIDED, "per-file timeout"),
        (route.classify(1, limit, oom=[], lowest_free_disk=None, journal_complete=True),
         route.COMPLETED, "journal closes"),
        (route.classify(124, limit, oom=[], lowest_free_disk=None, journal_complete=True),
         route.UNDECIDED, "limit"),
        (route.classify(124, limit, oom=[], lowest_free_disk=None, seconds=60.2),
         route.UNDECIDED, "timeout ended it"),
        (route.classify(137, limit, oom=[], lowest_free_disk=None, seconds=121.0),
         route.UNDECIDED, "timeout killed it"),
        (route.classify(137, limit, oom=None, lowest_free_disk=None, seconds=1.0),
         route.UNDECIDED, "after 1.0 s, short of its limit of 60 s"),
        (route.classify(124, limit, oom=[], lowest_free_disk=None, seconds=3.5,
                        journal_complete=True), route.UNDECIDED, "what did is unread"),
        (route.classify(0, limit, oom=[], lowest_free_disk=None, journal_complete=False),
         route.FAILED, "no closing line"),
        (route.classify(1, limit, oom=[], lowest_free_disk=None, journal_complete=False,
                        journal_reason="its journal closes on 0 of the 20 mutant(s) it picked"),
         route.FAILED, "exit 1, and its journal closes on 0 of the 20"),
        (route.classify(3, limit, oom=[], lowest_free_disk=None), route.FAILED, "exit 3"),
        (route.classify(None, limit, oom=[], lowest_free_disk=None), route.FAILED,
         "did not start"),
        (route.classify(0, limit, oom=["Killed process"], lowest_free_disk=1), route.PASSED,
         "exit 0"),
    ]
    for outcome, verdict, fragment in cases:
        ensure(outcome.verdict == verdict and fragment in outcome.reason,
               f"{outcome!r} should be {verdict} ({fragment!r})")
    for seconds, said in ((61.0, True), (2.0, False)):
        outcome = route.classify(124, limit, oom=[], lowest_free_disk=None, seconds=seconds)
        report: dict[str, object] = {"verdict": route.UNDECIDED, "request": {}, "jobs": {
            "seed-base": {"verdict": route.UNDECIDED, "steps": {"seed": {
                "verdict": outcome.verdict, "reason": outcome.reason, "exit": 124}}}}}
        text = route.summary(report)
        ensure(("A seed step reached its limit (seed-base)" in text) is said,
               f"the summary names a seed step's limit only where it was reached: {text!r}")


def _sampler_keeps_peaks() -> None:
    readings = iter([route.Sample(100, 300, 5 << 30, (1.0, 2.0, 3.0)),
                     route.Sample(900, 950, 2 << 30, None),
                     route.Sample(50, 60, None, (0.5, 0.5, 0.5))])
    with tempfile.TemporaryDirectory() as scratch:
        progress = Path(scratch) / "logs" / route.PROGRESS
        sampler = route.Sampler(progress, "seed", lambda: next(readings), interval=3600)
        for _ in range(3):
            sampler.sample()
        lines = progress.read_text(encoding="utf-8").splitlines()
        ensure(len(lines) == 3 and all(" seed rss_max_kb=" in line for line in lines)
               and "load=1.00,2.00,3.00" in lines[0] and "free_disk_bytes=unread" in lines[2],
               f"one progress line per reading: {lines!r}")
        ensure(sampler.peak_rss_kb == 900 and sampler.peak_tree_kb == 950
               and sampler.lowest_free_disk == 2 << 30 and sampler.samples == 3,
               "the sampler keeps each peak and the lowest free disk")
    ensure(route.new_oom(["a"], ["a", "b"]) == ["b"] and route.new_oom(["a"], None) is None
           and route.new_oom(None, ["a"]) == ["a"],
           "a step's OOM records are the ones it added; unread before errs toward undecided")
    ensure(route.time_figures("real 1.5\nuser 1\nsys 0.2\nmaxrss_kb 2048\n")
           == {"real": 1.5, "user": 1.0, "sys": 0.2, "maxrss_kb": 2048.0}
           and route.time_figures("") is None, "GNU time's figures are read")
    command = route.step_command(route.LIMITS["check"], ["echo", "x"], Path("t.txt"))
    ensure(command[:5] == [route.GNU_TIME, "-f", route.TIME_FORMAT, "-o", "t.txt"]
           and command[5:9] == ["timeout", f"--kill-after={route.KILL_AFTER}s", "600s", "echo"],
           f"a step runs under GNU time and timeout at its limit: {command!r}")


def _hooks() -> route.Hooks:
    return route.Hooks(oom=list, sample=lambda pid, root: route.Sample(1, 1, 1 << 40, None),
                       gnu_time=None, interval=0.05)


def _run_step_records_how_it_ended() -> None:
    # Linux alone: the wrapper runs coreutils timeout, which Windows does not carry.
    python = sys.executable
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        quiet = redirect_stdout(StringIO())
        with quiet:
            passed = route.run_step("check", [python, "-c", "print('ok')"], root=root,
                                    hooks=_hooks())
            limited = route.run_step("check", [python, "-c", "import time; time.sleep(30)"],
                                     root=root, hooks=_hooks(),
                                     limit=route.Limit(1, "a test", measured=False))
        receipt = route.load_receipt(root)
        steps = route.as_object(receipt["steps"])
        check = route.as_object(steps["check"])
        ensure(passed == 0 and limited == 1 and check["verdict"] == route.UNDECIDED
               and check["exit"] == 124 and check["limit_s"] == 1,
               f"a step cut at its limit is undecided, never failed: {check!r}")
        with quiet:
            failed = route.run_step("properties", [python, "-c", "raise SystemExit(3)"],
                                    root=root, hooks=_hooks())
        steps = route.as_object(route.load_receipt(root)["steps"])
        ensure(failed == 1 and route.as_object(steps["properties"])["verdict"] == route.FAILED,
               "a step that exits nonzero within its limit fails")
        journal = root / route.JOURNAL
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text(_journal(_SURVIVED, whole=1), encoding="utf-8")
        with quiet:
            done = route.run_step("seed", [python, "-c", "raise SystemExit(1)"], root=root,
                                  hooks=_hooks(), journal=journal)
        steps = route.as_object(route.load_receipt(root)["steps"])
        ensure(done == 0 and route.as_object(steps["seed"])["verdict"] == route.COMPLETED,
               "a seed run whose journal closes on every mutant it picked is completed "
               "whatever it exited")
        journal.write_text(_journal(_KILLED, _UNDECIDED), encoding="utf-8")
        with quiet:
            done = route.run_step("seed", [python, "-c", "raise SystemExit(1)"], root=root,
                                  hooks=_hooks(), journal=journal)
        steps = route.as_object(route.load_receipt(root)["steps"])
        ensure(done == 0 and route.as_object(steps["seed"])["verdict"] == route.COMPLETED,
               "a seed run whose journal counts an undecided mutant among those it picked "
               "is completed")
        journal.write_text(_journal(picked=20, whole=90, baseline="the unmutated tree did "
                                    "not compile, so there is no baseline"), encoding="utf-8")
        with quiet:
            done = route.run_step("seed", [python, "-c", "raise SystemExit(1)"], root=root,
                                  hooks=_hooks(), journal=journal)
        seed = route.as_object(route.as_object(route.load_receipt(root)["steps"])["seed"])
        ensure(done == 1 and seed["verdict"] == route.FAILED
               and "closes on 0 of the 20" in str(seed["reason"]),
               f"a seed run whose baseline did not stand measured nothing: {seed!r}")
        oom = route.Hooks(oom=iter([[], ["Out of memory: Killed process 9"]]).__next__,
                          sample=_hooks().sample, gnu_time=None, interval=0.05)
        with quiet:
            route.run_step("export", [python, "-c", "raise SystemExit(137)"], root=root,
                           hooks=oom)
        export = route.as_object(route.as_object(route.load_receipt(root)["steps"])["export"])
        ensure(export["verdict"] == route.UNDECIDED and bool(export["oom_records"])
               and "OOM killer" in str(export["reason"]),
               f"an OOM kill the kernel recorded is undecided: {export!r}")


def _side_commands() -> None:
    receipt: dict[str, object] = {"flag": "--recipe", "inputs": {
        "sample": "20", "subject": "proofs/CyclicExecutive.v"}}
    side = Path("side")
    run = [sys.executable, str(side / "tools" / "run.py")]
    ensure(route.side_command("check", side, receipt) == [*run, "quickchick", "check",
                                                          "--recipe"]
           and route.side_command("seed", side, receipt) == [
               *run, "seed", "coq", "--quickchick", "--sample", "20", "--jobs", "1", "--recipe"]
           and route.side_command("population", side, receipt) == [
               *run, "seed", "list", "--file", "proofs/CyclicExecutive.v", "--sample", "20"],
           "a recipe build's checks and seed run take --recipe; the seed run names no file")
    receipt["flag"] = ""
    ensure(route.side_command("properties", side, receipt) == [*run, "quickchick",
                                                               "properties"],
           "an install build's checks take no flag")
    bads: list[dict[str, object]] = [{"flag": "--other", "inputs": {"sample": "20"}},
                                     {"flag": "", "inputs": {"sample": "020"}},
                                     {"inputs": {}}]
    for bad in bads:
        try:
            route.side_command("seed", side, bad)
        except ValueError:
            continue
        raise AssertionError(f"a receipt without a flag or sample is refused: {bad!r}")


def _staging_refuses_and_records() -> None:
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        logs = root / route.LOGS
        (logs / "side").mkdir(parents=True)
        files = {"check.log": b"ok\n", "progress.log": b"t\n", "side/proofs.txt": b"x\n",
                 "Module.vo": b"Coq", "rocq.log": b"\x7fELF\x02", "demo.wasm.log": b"\0asm\x01",
                 "nul.txt": b"a\0b", "big.json": b"{}"}
        for name, data in files.items():
            (logs / name).write_bytes(data)
        journal = root / route.JOURNAL
        journal.parent.mkdir(parents=True)
        journal.write_text("== j\n", encoding="utf-8")
        (root / route.EXPORT).parent.mkdir(parents=True)
        (root / route.EXPORT).write_text("opam-version: \"2.0\"\n", encoding="utf-8")
        route.save_receipt(root, {"steps": {"provision": {"verdict": route.PASSED},
                                            "check": {"verdict": route.PASSED},
                                            "properties": {"verdict": route.FAILED}}})
        with redirect_stdout(StringIO()):
            excluded = route.stage(root, "build")
        left = {item["path"]: item["reason"] for item in excluded}
        ensure(set(left) >= {"Module.vo", "rocq.log", "demo.wasm.log", "nul.txt", route.EXPORT},
               f"staging leaves out each refused file: {left!r}")
        ensure("ELF magic" in left["rocq.log"] and "Wasm magic" in left["demo.wasm.log"]
               and "NUL" in left["nul.txt"] and "allowlist" in left["Module.vo"]
               and "not every check" in left[route.EXPORT],
               f"each with its reason: {left!r}")
        uploaded = {path.relative_to(root / route.UPLOAD).as_posix()
                    for path in (root / route.UPLOAD).rglob("*") if path.is_file()}
        ensure(uploaded == {"check.log", "progress.log", "side/proofs.txt", "big.json",
                            "seed/quickchick.journal", route.RECEIPT},
               f"only allowlisted text is uploaded: {sorted(uploaded)}")
        receipt = route.load_json(root / route.UPLOAD / route.RECEIPT) or {}
        steps = route.as_object(receipt["steps"])
        ensure(route.as_object(steps["export"])["verdict"] == route.NOT_RUN
               and bool(route.as_object(receipt["staging"])["excluded"]),
               "a step that never ran is recorded not run, and the exclusions are receipted")
        route.save_receipt(root, {"steps": {name: {"verdict": route.PASSED}
                                            for name in route.JOB_STEPS["build"]}})
        with redirect_stdout(StringIO()):
            route.stage(root, "build")
        ensure((root / route.UPLOAD / route.EXPORT).is_file(),
               "the export is uploaded where every check on its switch passed")
        with redirect_stdout(StringIO()):
            excluded = route.stage(root, "import")
        ensure(any(item["path"] == route.EXPORT for item in excluded),
               "no job but the build uploads an export")
        with patch.object(route, "FILE_LIMIT", 1):
            staged, left_out = route.select([(logs / "check.log", "check.log")])
        ensure(not staged and "limit for one file" in left_out[0]["reason"],
               "a file over its limit is left out")
        with patch.object(route, "ARCHIVE_LIMIT", 4):
            staged, left_out = route.select([(logs / "check.log", "a.log"),
                                             (logs / "progress.log", "b.log")])
        ensure(len(staged) == 1 and "past its" in left_out[0]["reason"],
               "the artifact stays within its bound")


def _staging_refuses_a_symlink() -> None:
    # Linux alone: a Windows host needs a privilege to create a symbolic link.
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        logs = root / route.LOGS
        logs.mkdir(parents=True)
        outside = root / "outside.log"
        outside.write_bytes(b"not the job's\n")
        (logs / "link.log").symlink_to(outside)
        (logs / "check.log").write_bytes(b"ok\n")
        with redirect_stdout(StringIO()):
            excluded = route.stage(root, "build")
        left = {item["path"]: item["reason"] for item in excluded}
        uploaded = {path.relative_to(root / route.UPLOAD).as_posix()
                    for path in (root / route.UPLOAD).rglob("*") if path.is_file()}
        ensure("not a regular file" in left.get("link.log", "")
               and uploaded == {"check.log", route.RECEIPT},
               f"a symbolic link is left out, never followed: {left!r}, {sorted(uploaded)}")


# ---------------------------------------------------------------------------- the join


def _receipt(key: str, revision: str, *, candidate: str = REVISION, base: str = BASE,
             dispatch: str = DISPATCH, run_id: str = RUN_ID,
             **changes: object) -> dict[str, object]:
    job = "seed" if key.startswith("seed-") else key
    side = "base" if key == "seed-base" else "candidate"
    steps = {step: {"verdict": route.COMPLETED if step == "seed" else route.PASSED,
                    "seconds": 1.0, "limit_s": 9, "exit": 0, "peak_rss_kb": 10}
             for step in route.JOB_STEPS[job]}
    receipt: dict[str, object] = {
        "job": job, "run": key.removeprefix("seed-") if job == "seed" else "candidate",
        "run_id": run_id, "dispatching_commit": dispatch, "source_revision": revision,
        "inputs": {"side": side, "revision": candidate, "base_revision": base,
                   "build": "recipe", "sample": "20",
                   "subject": "proofs/CyclicExecutive.v"},
        "runner_image": "ubuntu26-1", "uname_m": "x86_64", "opam_client": "2.6.0",
        "switch": "s", "flag": "--recipe", "recipe": "RECIPE", "steps": steps}
    receipt.update(changes)
    return receipt


def _mutant(ident: str, line: int, before: str, after: str) -> mutate.Mutant:
    return mutate.Mutant(ident, ident.rsplit("/", 1)[0], "proofs/C.v", line, 0, 0, before,
                         after)


_RELATIONAL = _mutant("relational/1", 3, "<=", "<")
_SUCCESSOR = _mutant("successor/4", 9, "S n", "n")
_SWAP = _mutant("swap/2", 4, "a", "b")
_TIMED_OUT = ("the compile of proofs/C.v reached gallina's per-file limit of 900 s and was "
              "stopped, so nothing was decided about it")
_KILLED = (_RELATIONAL, seeded.KILLED, "refuted 1 of 33")
_SURVIVED = (_SUCCESSOR, seeded.SURVIVED, "33 held")
_UNDECIDED = (_SUCCESSOR, seeded.UNDECIDED, _TIMED_OUT)
_LISTING = ("== proofs/C.v: 9 mutant(s) over 2 operator(s)\n"
            "     relational/1       proofs/C.v:3 `<=` -> `<`\n"
            "     successor/4        proofs/C.v:9 `S n` -> `n`\n")


def _journal(*verdicts: tuple[mutate.Mutant, str, str], whole: int = 9,
             picked: int | None = None, close: int | None = 1,
             baseline: str | None = None) -> str:
    """A journal written by seed's own `Journal`, driven as `seed coq --quickchick`
    drives it, so a change to the producer's format moves these fixtures with it: the
    head over `picked` of `whole` mutants, the baseline's notes, and for each verdict the
    note naming the mutant the tree is on, a compile's note and the verdict, which
    `record` writes after a note naming its number; then, where `baseline` is given, the
    note saying why there is none in place of every verdict; and the closing line at
    exit `close` unless it is None, as a run that never finished writes none."""
    tree = "quickchick"
    with tempfile.TemporaryDirectory() as scratch:
        book = seeded.Journal(Path(scratch) / "seed" / "quickchick.journal")
        ran = len(verdicts) if picked is None else picked
        book.start("proofs/CyclicExecutive.v", "prover-then-QuickChick",
                   seeded.Scope(whole=whole, ran=ran))
        book.note(f"{tree}: baseline")
        book.note(f"{tree}: Properties.v draws from seed 42")
        book.note(f"{tree}: compiled proofs/C.v in 1.25 s, exit 0")
        if baseline is not None:
            book.note(f"no baseline: {baseline}")
        for mutant, outcome, detail in verdicts:
            book.note(f"{tree}: mutant {mutant.ident} ({mutant.operator}) {mutant.what}")
            book.note(f"{tree}: compiled proofs/C.v in 2.50 s, exit 0")
            book.record(seeded.Verdict(mutant, outcome, detail), f"{tree}: mutant {mutant.ident}")
        if close is not None:
            book.close(close)
        return book.path.read_text(encoding="utf-8")


def _noteless(journal: route.Journal) -> bool:
    """Whether no note entered any verdict's reason or identity."""
    return all("--" not in entry.detail and "compiled" not in entry.detail
               and "is verdict" not in entry.detail and "--" not in entry.identity
               for entry in journal.entries)


def _artifacts(root: Path, *, seed: bool = True,
               edits: dict[str, dict[str, object]] | None = None,
               journals: dict[str, str] | None = None, candidate: str = REVISION,
               base: str = BASE, dispatch: str = DISPATCH, run_id: str = RUN_ID) -> None:
    plan = {"run_id": run_id, "dispatching_commit": dispatch, "accepted": True, "seed": seed,
            "request": {"ref": route.MAIN, "revision": candidate,
                        "base_revision": base if seed else "", "build": "recipe",
                        "sample": "20", "title": ""},
            "subjects": {"candidate": "proofs/CyclicExecutive.v",
                         "base": "proofs/CyclicExecutive.v"}}
    keys = ["build", "import", *([f"seed-{run}" for run in route.SEED_RUNS] if seed else [])]
    (root / f"instrument-plan-{candidate}").mkdir(parents=True)
    (root / f"instrument-plan-{candidate}" / route.PLAN).write_text(json.dumps(plan),
                                                                      encoding="utf-8")
    for key in keys:
        revision = base if key == "seed-base" else candidate
        directory = root / route.artifact_name(key, revision)
        directory.mkdir()
        receipt = _receipt(key, revision, candidate=candidate, base=base, dispatch=dispatch,
                           run_id=run_id)
        if not seed:
            route.as_object(receipt["inputs"])["base_revision"] = ""
        receipt.update((edits or {}).get(key, {}))
        (directory / route.RECEIPT).write_text(json.dumps(receipt), encoding="utf-8")
        if key.startswith("seed-"):
            (directory / "seed").mkdir()
            text = (journals or {}).get(key, _journal(_KILLED, _SURVIVED))
            (directory / "seed" / "quickchick.journal").write_text(text, encoding="utf-8")
            (directory / "population.log").write_text(_LISTING, encoding="utf-8")


_SUCCESS: dict[str, object] = {name: {"result": "success"} for name in ("plan", "build",
                                                                         "import", "seed")}


def _joined(setup: Callable[[Path], object], needs: dict[str, object] | None = None
            ) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        setup(root)
        return route.join(root, needs if needs is not None else _SUCCESS, RUN_ID)


def _join_passes_and_lists_mutants() -> None:
    report = _joined(_artifacts)
    ensure(report["verdict"] == route.PASSED and not report["refusals"],
           f"every job passed: {report['refusals']!r}")
    seed = route.as_object(report["seed"])
    mutants = [route.as_object(item) for item in route.as_list(seed["mutants"])]
    ensure([m["operator"] for m in mutants] == [["relational"], ["successor"]]
           and mutants[0]["site"] == "proofs/C.v:3" and mutants[0]["rewrite"] == "`<=` -> `<`"
           and mutants[0]["base"] == ["killed"] and mutants[1]["candidate-2"] == ["survived"],
           f"each mutant by identity, operator, site and rewrite in every run: {mutants!r}")
    ensure(not seed["candidate_differences"] and not seed["base_differences"]
           and not seed["other_verdicts"], "agreeing runs list no difference")
    text = route.summary(report)
    ensure("| relational |" in text and "Instrument switch route: passed" in text,
           f"the summary names each mutant's operator: {text!r}")


def _join_lists_differences() -> None:
    journals = {"seed-candidate-2": _journal((_RELATIONAL, seeded.SURVIVED, "33 held"),
                                             _SURVIVED),
                "seed-base": _journal(_KILLED, _UNDECIDED)}
    edits: dict[str, dict[str, object]] = {"seed-base": {"opam_client": "2.5.0",
                                                         "runner_image": "ubuntu26-2"}}
    report = _joined(lambda root: _artifacts(root, journals=journals, edits=edits))
    seed = route.as_object(report["seed"])
    ensure(len(route.as_list(seed["candidate_differences"])) == 1
           and len(route.as_list(seed["base_differences"])) == 3,
           f"each mutant whose verdict moves is listed with both runs': {seed!r}")
    base = route.as_object(route.as_object(seed["runs"])["base"])
    ensure(base["complete"] is True and base["decided"] == 1 and base["undecided"] == 1
           and base["shortfall"] is None,
           f"a run with an undecided mutant closes on every mutant it picked: {base!r}")
    other = [route.as_object(item) for item in route.as_list(seed["other_verdicts"])]
    ensure(len(other) == 1 and other[0]["verdict"] == seeded.UNDECIDED
           and other[0]["reason"] == _TIMED_OUT and other[0]["run"] == "base",
           f"an undecided verdict is listed with its journalled reason alone: {other!r}")
    reasons = [str(side["reason"]) for name in ("candidate_differences", "base_differences")
               for item in route.as_list(seed[name])
               for key, sides in route.as_object(item).items() if key != "mutant"
               for side in map(route.as_object, route.as_list(sides))]
    ensure(len(reasons) == 8 and set(reasons) == {"refuted 1 of 33", "33 held", _TIMED_OUT},
           f"each difference carries the verdicts' journalled reasons and no note: {reasons!r}")
    pairs = route.as_list(report["differing_sides"])
    ensure({route.as_object(item)["field"] for item in pairs} == {"opam_client",
                                                                   "runner_image"},
           f"each pair of sides whose client or image differs: {pairs!r}")


def _join_records_not_run_and_refusals() -> None:
    skipped = dict(_SUCCESS, build={"result": "failure"}, **{"import": {"result": "skipped"}})

    def without_import(root: Path) -> None:
        _artifacts(root, seed=False)
        for path in root.glob("instrument-import-*"):
            for item in path.iterdir():
                item.unlink()
            path.rmdir()

    failed = dict(_receipt("build", REVISION))
    route.as_object(failed["steps"])["properties"] = {"verdict": route.FAILED}
    report = _joined(lambda root: (without_import(root),
                                   (root / f"instrument-build-{REVISION}" / route.RECEIPT)
                                   .write_text(json.dumps(dict(
                                       failed, inputs=dict(route.as_object(failed["inputs"]),
                                                           base_revision=""))),
                                       encoding="utf-8")),
                     skipped)
    jobs = route.as_object(report["jobs"])
    ensure(route.as_object(jobs["import"])["verdict"] == route.NOT_RUN
           and "exported no switch" in str(route.as_object(jobs["import"])["reason"])
           and report["verdict"] == route.FAILED and not report["refusals"],
           f"a job its prerequisite's failure skipped is recorded not run: {report!r}")
    cases: list[tuple[Callable[[Path], object], dict[str, object], str]] = [
        (without_import, _SUCCESS, "the import job ran (success) and left no artifact"),
        (lambda root: (_artifacts(root),
                       (root / f"instrument-build-{'c' * 40}").mkdir()),
         _SUCCESS, "duplicate artifacts for the build job"),
        (lambda root: (_artifacts(root), (root / "someone-else").mkdir()), _SUCCESS,
         "an artifact this route does not name"),
        (_artifacts, dict(_SUCCESS, **{"import": {"result": "skipped"}}),
         "an artifact from the import job, which did not run"),
        (lambda root: _artifacts(root, edits={"build": {"run_id": "1"}}), _SUCCESS,
         "names run '1'"),
        (lambda root: _artifacts(root, edits={"build": {"source_revision": BASE}}), _SUCCESS,
         "tested"),
        (lambda root: _artifacts(root, edits={"seed-candidate-1": {"inputs": {
            "side": "candidate", "revision": REVISION, "base_revision": BASE,
            "build": "recipe", "sample": "19", "subject": "proofs/CyclicExecutive.v"}}}),
         _SUCCESS, "records sample '19'"),
        (lambda root: _artifacts(root, edits={"seed-base": {"inputs": {
            "side": "base", "revision": REVISION, "base_revision": BASE, "build": "recipe",
            "sample": "20", "subject": "proofs/Other.v"}}}), _SUCCESS, "records subject"),
        (lambda root: _artifacts(root, edits={"import": {"dispatching_commit": "e" * 40}}),
         _SUCCESS, "another dispatching commit"),
        (lambda root: None, _SUCCESS, "no plan artifact"),
    ]
    for setup, needs, fragment in cases:
        report = _joined(setup, needs)
        ensure(report["verdict"] == route.REFUSED
               and any(fragment in item for item in cast_list(report["refusals"])),
               f"the join refuses ({fragment!r}): {report['refusals']!r}")
    # The join's own artifact, from an earlier attempt, is not one it reads.
    report = _joined(lambda root: (_artifacts(root),
                                   (root / f"instrument-join-{REVISION}").mkdir()))
    ensure(report["verdict"] == route.PASSED, f"an earlier join's artifact is passed over: "
           f"{report['refusals']!r}")
    # A rerun in which the build now fails leaves the earlier attempt's import artifact
    # for a job this attempt skipped: passed over and recorded, so the failure shows.
    failed_build: dict[str, object] = {
        "steps": dict(route.as_object(_receipt("build", REVISION)["steps"]),
                      properties={"verdict": route.FAILED}), "run_attempt": "2"}
    rerun = dict(_SUCCESS, build={"result": "failure"}, **{"import": {"result": "skipped"}})
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        _artifacts(root, seed=False, edits={"build": failed_build,
                                             "import": {"run_attempt": "1"}})
        report = route.join(root, rerun, RUN_ID, "2")
        stale = route.join(root, rerun, RUN_ID, "1")
    passed = [route.as_object(item) for item in route.as_list(report["passed_over"])]
    ensure(report["verdict"] == route.FAILED and not report["refusals"]
           and [item["artifact"] for item in passed] == [f"instrument-import-{REVISION}"]
           and "Passed over:" in route.summary(report),
           f"an earlier attempt's artifact for a skipped job is passed over: {report!r}")
    ensure(stale["verdict"] == route.REFUSED and any(
        "which did not run" in item for item in cast_list(stale["refusals"])),
           f"an artifact from this attempt for a job that did not run is refused: {stale!r}")


def _join_reads_failures_outside_wrapped_steps() -> None:
    not_run = {"verdict": route.NOT_RUN, "reason": "the job ended before this step"}
    early: dict[str, object] = {"steps": dict.fromkeys(route.JOB_STEPS["seed"], not_run)}
    failed_seed = dict(_SUCCESS, seed={"result": "failure"})
    report = _joined(lambda root: _artifacts(root, edits={"seed-candidate-1": early}),
                     failed_seed)
    jobs = route.as_object(report["jobs"])
    ensure(report["verdict"] == route.FAILED and not report["refusals"]
           and route.as_object(jobs["seed-candidate-1"])["verdict"] == route.FAILED
           and "outside its wrapped steps" in str(
               route.as_object(jobs["seed-candidate-1"])["reason"])
           and route.as_object(jobs["seed-base"])["verdict"] == route.PASSED,
           f"a seed run that failed before any step is failed, and the matrix's result "
           f"fails no run whose own steps all ran: {report!r}")
    imported: dict[str, object] = {"steps": dict.fromkeys(route.JOB_STEPS["import"], not_run)}
    report = _joined(lambda root: _artifacts(root, seed=False, edits={"import": imported}),
                     dict(_SUCCESS, **{"import": {"result": "failure"}}))
    ensure(report["verdict"] == route.FAILED
           and route.as_object(route.as_object(report["jobs"])["import"])["verdict"]
           == route.FAILED, f"an import that failed at its download is failed: {report!r}")
    report = _joined(lambda root: _artifacts(root, seed=False, edits={"import": imported}),
                     dict(_SUCCESS, **{"import": {"result": "cancelled"}}))
    ensure(report["verdict"] == route.INCOMPLETE,
           f"a cancelled job that ran no step is incomplete, not failed: {report!r}")
    text = route.summary(_joined(lambda root: _artifacts(root, seed=False,
                                                         edits={"import": imported}),
                                 dict(_SUCCESS, **{"import": {"result": "failure"}})))
    ensure("outside its wrapped steps" in text, f"the summary names why: {text!r}")


def cast_list(value: object) -> list[str]:
    return [str(item) for item in route.as_list(value)]


def _journal_and_population_readers() -> None:
    text = _journal(_KILLED, (_SWAP, seeded.STILLBORN,
                              "did not compile\n  with a second line"))
    journal = route.parse_journal(text)
    ensure(journal.complete and journal.exit == 1
           and journal.scope == "over 2 of 9 mutant(s), which is a sample and not the "
                                "population"
           and [e.outcome for e in journal.entries] == ["killed", "stillborn"]
           and journal.entries[1].detail == "did not compile\n  with a second line"
           and journal.entries[0].detail == "refuted 1 of 33"
           and journal.entries[0].identity == "proofs/C.v:3 `<=` -> `<`",
           f"the journal reads verdicts, a reason over several lines, scope and close: "
           f"{journal!r}")
    ensure(journal.picked == 2 and journal.decided == 2 and journal.undecided == 0
           and "undecided" not in text.splitlines()[-1]
           and route.journal_shortfall(journal) is None,
           f"a journal closing with nothing undecided on every mutant it picked records a "
           f"finished run: {journal!r}")
    mixed_text = _journal(_KILLED, (_SWAP, seeded.SURVIVED, "33 held"), _UNDECIDED)
    mixed = route.parse_journal(mixed_text)
    notes = [line for line in mixed_text.splitlines() if line.startswith("-- ")]
    ensure(len(notes) == 12 and mixed_text.splitlines()[-1]
           == "== complete: 2 verdict(s) decided, 1 undecided, exit 1",
           f"seed's journal interleaves notes with its verdicts and counts the undecided "
           f"apart: {mixed_text!r}")
    ensure([e.outcome for e in mixed.entries] == ["killed", "survived", "undecided"]
           and [e.detail for e in mixed.entries] == ["refuted 1 of 33", "33 held", _TIMED_OUT]
           and _noteless(mixed) and mixed.decided == 2 and mixed.undecided == 1
           and mixed.complete and mixed.exit == 1 and mixed.picked == 3
           and route.journal_shortfall(mixed) is None,
           f"notes are no verdict and no verdict's reason, and an undecided verdict counts "
           f"toward the mutants the run picked: {mixed!r}")
    step = route.classify(1, 60, oom=[], lowest_free_disk=None, seconds=5.0,
                          journal_complete=route.journal_shortfall(mixed) is None)
    ensure(step.verdict == route.COMPLETED,
           f"a seed step whose journal closes with an undecided mutant is completed: {step!r}")
    truncated = route.parse_journal(_journal(_KILLED, _UNDECIDED, close=None))
    ensure(not truncated.complete and len(truncated.entries) == 2 and _noteless(truncated)
           and truncated.decided is None and truncated.undecided is None
           and route.journal_shortfall(truncated) == "its journal has no closing line",
           f"a journal with no closing line is incomplete: {truncated!r}")
    short = route.parse_journal(_journal(_KILLED, _UNDECIDED, picked=4))
    ensure(route.journal_shortfall(short) == "its journal closes on 2 of the 4 mutant(s) it "
                                             "picked, 1 of them undecided",
           f"a closing count short of the mutants picked says how: {short!r}")
    unstood = route.parse_journal(_journal(picked=20, whole=90, baseline="the unmutated "
                                           "tree did not compile, so there is no baseline"))
    ensure(not unstood.entries and unstood.decided == 0 and unstood.undecided == 0
           and route.journal_shortfall(unstood) == "its journal closes on 0 of the 20 "
                                                   "mutant(s) it picked",
           f"a run whose baseline did not stand closes on none it picked: {unstood!r}")
    head = "== proofs/C.v against the prover-then-QuickChick oracle\n"
    for body, fragment in (
            ("   scope: over 20 of 90 mutant(s), which is a sample and not the population\n"
             "== complete: 0 verdict(s) decided, exit 1\n", "closes on 0 of the 20"),
            ("   scope: over the whole population of 3 mutant(s)\n"
             "    1  killed    p:1 `a` -> `b`: x\n"
             "== complete: 1 verdict(s) decided, exit 1\n", "closes on 1 of the 3"),
            ("   scope: over the whole population of 0 mutant(s)\n"
             "== complete: 0 verdict(s) decided, exit 1\n", "picks no mutant"),
            ("== complete: 0 verdict(s) decided, exit 1\n", "states no scope"),
            ("   scope: over the whole population of 1 mutant(s)\n"
             "    1  killed    p:1 `a` -> `b`: x\n"
             "== complete: 1 verdict(s) decided, exit 2\n", "closes at exit 2")):
        found = route.journal_shortfall(route.parse_journal(head + body))
        ensure(found is not None and fragment in found,
               f"a journal falling short says how ({fragment!r}): {found!r}")
    whole = route.parse_journal(head + "   scope: over the whole population of 1 mutant(s)\n"
                                "    1  killed    p:1 `a` -> `b`: x\n"
                                "== complete: 1 verdict(s) decided, exit 0\n")
    ensure(whole.picked == 1 and route.journal_shortfall(whole) is None,
           f"a whole-population scope states its count: {whole!r}")
    listed = route.parse_population(_LISTING + "     successor/5        proofs/C.v:9 "
                                               "`S n` -> `n`\nok proofs/C.v yields 9\n")
    ensure(listed == {"proofs/C.v:3 `<=` -> `<`": ["relational"],
                      "proofs/C.v:9 `S n` -> `n`": ["successor", "successor"]},
           f"the listing maps each site and rewrite to its operators: {listed!r}")


# ----------------------------------------------------------------- the import comparison


def _closure(pin: str = "git+https://github.com/QuickChick/QuickChick.git#3d4d6c0e9f") -> list[
        dict[str, str]]:
    return [{"name": "coq-quickchick", "version": "dev", "pin": pin},
            {"name": "rocq-core", "version": "9.3.0", "pin": ""}]


def _import_comparison() -> None:
    build: dict[str, object] = {"job": "build", "run_id": RUN_ID, "switch": "s",
                                "closure": _closure(), "export": {"sha256": "f" * 64}}
    imported: dict[str, object] = {
        "job": "import", "switch": "s", "closure": list(reversed(_closure())),
        "import_source": {"sha256": "f" * 64},
        "steps": {"check": {"verdict": route.PASSED}},
        "reexport": {"identical": False, "difference": ["-a", "+b"]}}
    found = route.compare_import(build, imported, RUN_ID)
    ensure(found["verdict"] == route.PASSED and found["closure_equal"] is True
           and found["pins_equal"] is True
           and route.as_object(found["pins"])["coq-quickchick"] == {
               "url": "git+https://github.com/QuickChick/QuickChick.git",
               "commit": "3d4d6c0e9f"},
           f"an equal closure, pins and a passing check decide; a re-export that differs "
           f"is an observation: {found!r}")
    cases: list[tuple[dict[str, object], dict[str, object], str]] = [
        ({}, {"steps": {"check": {"verdict": route.FAILED}}}, "not exit 0"),
        ({}, {"closure": [*_closure(), {"name": "extra", "version": "1", "pin": ""}]},
         "closures differ"),
        ({}, {"closure": _closure("git+https://github.com/QuickChick/QuickChick.git#0123456")},
         "pins differ"),
        ({}, {"import_source": {"sha256": "e" * 64}}, "export SHA-256"),
        ({"run_id": "1"}, {}, "names run '1'"),
        ({}, {"switch": "other"}, "the import's 'other'"),
        ({"closure": []}, {}, "records no installed closure"),
    ]
    for build_edit, import_edit, fragment in cases:
        found = route.compare_import(build | build_edit, imported | import_edit, RUN_ID)
        ensure(found["verdict"] == route.FAILED
               and any(fragment in item for item in cast_list(found["reasons"])),
               f"the comparison refuses ({fragment!r}): {found['reasons']!r}")


def cases() -> list[Case]:
    return [Case("plan-accepts-main-revisions", _plan_accepts_main_revisions),
            Case("plan-refuses-each-bad-request", _plan_refuses_each_bad_request),
            Case("plan-ref-reads-fetched-main", _plan_ref_reads_fetched_main),
            Case("plan-outputs-only-validated-values", _plan_outputs_only_validated_values),
            Case("plan-command-records-and-exits", _plan_command_records_and_exits),
            Case("limits-and-minutes", _limits_and_minutes),
            Case("workflow-holds-the-module-limits", _workflow_holds_the_module_limits),
            Case("workflow-contract-shape", _workflow_contract_shape),
            Case("readme-holds-the-module-constants", _readme_holds_the_module_constants),
            Case("classify-records-undecided", _classify_records_undecided),
            Case("sampler-keeps-peaks", _sampler_keeps_peaks),
            Case("run-step-records-how-it-ended", _run_step_records_how_it_ended,
                 lane="guest"),
            Case("side-commands", _side_commands),
            Case("staging-refuses-and-records", _staging_refuses_and_records),
            Case("staging-refuses-a-symlink", _staging_refuses_a_symlink, lane="guest"),
            Case("join-passes-and-lists-mutants", _join_passes_and_lists_mutants),
            Case("join-lists-differences", _join_lists_differences),
            Case("join-records-not-run-and-refusals", _join_records_not_run_and_refusals),
            Case("join-reads-failures-outside-wrapped-steps",
                 _join_reads_failures_outside_wrapped_steps),
            Case("journal-and-population-readers", _journal_and_population_readers),
            Case("import-comparison", _import_comparison)]
