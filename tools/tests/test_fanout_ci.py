# SPDX-License-Identifier: Apache-2.0
"""Historical CI records, shared transport and independent hosted workflow controls."""

import copy
import json
import os
import re
import runpy
import subprocess
import sys
import tempfile
import textwrap
import urllib.error
import urllib.request
from collections.abc import Callable
from itertools import product
from pathlib import Path
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import ci_scope
from vos import fanout_ci as ci

# Each case owns its fixtures and patches, so sharded cases share no state.
INDEPENDENT_CASES = True

REVISION = "a" * 40
NOW = "2026-09-27T16:00:00Z"
OLD_ID = "5c6c433b07cb4212b594b83fffccdc48"
REPO = "example/verifiedos"
ROOT = Path(__file__).resolve().parents[2]


def _state() -> ci.CIState:
    return ci.new_state(REPO, "main", REVISION, True)


def _record(workflow: str, number: int, phase: str) -> ci.RunState:
    return {"workflow": workflow, "revision": REVISION, "requested": NOW,
            "phase": phase, "run_id": number,
            "url": f"https://github.com/{REPO}/actions/runs/{number}",
            "status": "completed" if phase == "observed" else "pending",
            "conclusion": "success" if phase == "observed" else None,
            "request_id": "historical-receipt",
            "jobs": dict.fromkeys(ci.HOST_JOBS, "success") if phase == "observed" else {}}


def _historical() -> ci.CIState:
    state = _state()
    state["host"] = _record(ci.HOST, 10, "observed")
    state["guest"] = _record(ci.GUEST, 20, "accepted")
    return state


def _refuses(action: Callable[[], object], message: str) -> None:
    try:
        action()
    except ci.CIError:
        return
    raise AssertionError(message)


def _selection(paths: list[str]) -> ci_scope.Selection:
    return {**ci_scope.classify(paths), "base": "b" * 40, "revision": REVISION,
            "paths": sorted(paths), "reason": "changed paths"}


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
                       ("reading_base", "b" * 7), ("reading_base", "B" * 40),
                       ("reading_base", REVISION), ("reading_base", None),
                       ("reading_base", "")):
        state: dict[str, object] = dict(_state())
        state[key] = value
        _refuses(lambda state=state: ci.validate_state(state), f"invalid {key} must be refused")
    historical = _historical()
    for requested in ("yesterday", "2026-09-27T16:00:00", 1759000000):
        timed = copy.deepcopy(historical)
        guest: dict[str, object] = dict(timed["guest"] or {})
        guest["requested"] = requested
        _refuses(lambda guest=guest, timed=timed: ci.validate_state({**timed, "guest": guest}),
                 f"request time {requested!r} must be a zoned timestamp")
    tokened = copy.deepcopy(historical)
    guest = dict(tokened["guest"] or {})
    del guest["requested"]
    guest["token"] = OLD_ID
    ci.validate_state({**tokened, "guest": guest})
    legacy = copy.deepcopy(historical)
    legacy["ref"] = f"fanout/batch/{REVISION}"
    _refuses(lambda: ci.validate_state(legacy), "legacy tag handoffs remain invalid")
    historical["host"] = None
    _refuses(lambda: ci.validate_state(historical),
             "historical guest dispatch without passing host evidence must be refused")


def _phase_validation() -> None:
    for lane, workflow in (("host", ci.HOST), ("guest", ci.GUEST)):
        for phase in ([], {}, ["intent"], {"phase": "intent"}):
            state: dict[str, object] = dict(_state())
            record: dict[str, object] = dict(_record(workflow, 10, "accepted"))
            record["phase"] = phase
            state[lane] = record
            _refuses(lambda state=state: ci.validate_state(state),
                     f"malformed {lane} phase must produce a controlled refusal")


def _completed_handoff_provenance() -> None:
    for lane, change in (("host", "unobserved"), ("host", "missing-run"),
                         ("guest", "missing-run")):
        state: dict[str, object] = dict(_historical())
        run = dict(cast(dict[str, object], state[lane]))
        if change == "unobserved":
            run["phase"] = "intent"
        else:
            run["run_id"], run["url"] = None, ""
        state[lane] = run
        _refuses(lambda state=state: ci.validate_state(state),
                 f"historical handoffs cannot trust {change} {lane} provenance")


def _historical_validation_is_local() -> None:
    with (patch.object(ci, "GitHub", side_effect=AssertionError("unexpected CI client")),
          patch.object(ci, "_token", side_effect=AssertionError("unexpected credential read"))):
        for state in (_state(), _historical()):
            before = copy.deepcopy(state)
            ensure(ci.validate_state(state) == before and state == before,
                   "historical validation only reads existing evidence")


def _scope_validation() -> None:
    narrow = _selection(["README.md"])
    for cold, base, full in ((True, None, False), (False, "b" * 40, False),
                             (False, None, True)):
        _refuses(lambda cold=cold, base=base, full=full: ci.new_state(
            REPO, "main", REVISION, cold, base, selection=narrow, full_ci=full),
                 "historical scope must agree with its frozen overrides")
    legacy = ci.new_state(REPO, "main", REVISION, False)
    ensure("selection" not in legacy, "old records remain valid without invented scope")
    state = ci.new_state(REPO, "main", REVISION, False, selection=narrow)
    state["host"] = _record(ci.HOST, 10, "observed")
    state["guest_omitted"] = True
    ci.validate_state(state)
    for change in ("selection", "host"):
        damaged: dict[str, object] = dict(copy.deepcopy(state))
        del damaged[change]
        _refuses(lambda damaged=damaged: ci.validate_state(damaged),
                 "historical omission needs both its selection and host evidence")


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


def _workflow_titles() -> None:
    for workflow in (ci.HOST, ci.GUEST):
        contents = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
        ensure(f"\nname: {workflow.removesuffix('.yml')}\n" in contents,
               f"{workflow} is named for its file, matching their workflow identities")
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
    # The aggregate names remain stable for retained historical evidence and hosted
    # workflow consumers, including when runner images change.
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
    # A platform's shards and unpartitioned job each state its label, so an image move
    # that reaches only one of them is refused.
    moved = re.sub(r"(\{platform: Windows, shard: unpartitioned, runner: [^\s,{}]+)\}",
                   r"\1-moved}", contents)
    faults = _runner_faults(moved)
    ensure(moved != contents and any("not one runner image" in fault for fault in faults),
           f"Windows's unpartitioned job must share its shards' image: {faults!r}")
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
    # own that names its runner, so the shards and it together run the whole gate; the
    # conditions that pick it out read the literal its entries state.
    faults = _unpartitioned_faults(contents)
    ensure(not faults, f"{ci.HOST} runs one unpartitioned job on each platform: {faults!r}")
    analysis = "matrix.platform == 'Ubuntu' && matrix.shard == 'unpartitioned' }}"
    saving = "save-cache: ${{ github.event_name == 'push' && matrix.shard == 'unpartitioned' }}"
    for mutant, fragment in (
            (contents.replace(analysis, analysis.replace("'unpartitioned'", "1")),
             "the workflow analysis runs on"),
            (contents.replace(saving, saving.replace("'unpartitioned'", "'Unpartitioned '")),
             "setup-uv saves its cache on"),
            (contents.replace("shard: unpartitioned,", "shard: Unpartitioned,"),
             "the gate's PART line does not compare"),
            (contents.replace("{platform: Ubuntu, shard: unpartitioned,",
                              "{platform: Ubuntu, shard: Unpartitioned,"),
             "not one unpartitioned value"),
            (re.sub(r"(?m)^ *- \{platform: Windows, shard: unpartitioned,.*\n", "", contents),
             "not each of")):
        ensure(mutant != contents, f"the fixture for {fragment!r} changed nothing")
        found = _unpartitioned_faults(mutant)
        ensure(any(fragment in fault for fault in found),
               f"a drifted unpartitioned literal must be refused ({fragment!r}): {found!r}")


def _unpartitioned_faults(contents: str) -> list[str]:
    """Why the host workflow's unpartitioned jobs need not run once per platform, or need
    not be the jobs that run the gate's unpartitioned part, save the uv cache and, on
    Ubuntu, analyze the workflows.

    The include entries stating a shard must state one value between them, once for each
    platform of the matrix, each entry naming its runner. The gate's PART line, setup-uv's
    one save-cache line and the Analyze workflows step's one condition must each compare
    `matrix.shard` with that value: a literal no combination holds leaves every job green
    while none of them saves the cache or analyzes the workflows."""
    shards = _job_text(contents, "host-gates-shard")
    lines = [line for line in shards.split("\n") if not line.lstrip().startswith("#")]
    listed = re.search(r"(?m)^        platform: \[([^\]\n]*)\]$", "\n".join(lines))
    platforms = sorted(name.strip() for name in listed[1].split(",")) if listed else []
    entries = [entry for entry in _include_entries(lines) if _key_values(entry, "shard")]
    values = sorted({value for entry in entries for value in _key_values(entry, "shard")})
    if len(values) != 1:
        return [f"the include entries state the shards {values!r}, not one unpartitioned value"]
    compared = f"matrix.shard == '{values[0]}'"
    faults: list[str] = []
    named = sorted(name for entry in entries if len(_key_values(entry, "runner")) == 1
                   for name in _key_values(entry, "platform"))
    if named != platforms:
        faults.append(f"the {values[0]!r} entries name {named!r}, not each of {platforms!r} "
                      "once with its runner")
    if compared not in _GATE_PART:
        faults.append(f"the gate's PART line does not compare {compared}")
    steps = _step_texts(shards)
    saves = [m[1] for step in steps
             if any(uses.startswith("astral-sh/setup-uv@") for uses in _step_values(step, "uses"))
             for m in re.finditer(r"(?m)^          save-cache:[ \t]*(.*?)[ \t]*$", step)]
    saving = f"${{{{ github.event_name == 'push' && {compared} }}}}"
    if saves != [saving]:
        faults.append(f"setup-uv saves its cache on {saves!r}, not exactly {saving!r}")
    analyses = [_step_values(step, "if") for step in steps
                if _step_values(step, "name") == ["Analyze workflows"]]
    analyzing = f"&& matrix.platform == 'Ubuntu' && {compared} }}}}"
    if len(analyses) != 1 or len(analyses[0]) != 1 or not analyses[0][0].endswith(analyzing):
        faults.append(f"the workflow analysis runs on {analyses!r}, not on Ubuntu's "
                      f"{values[0]!r} job alone")
    return faults


def _aggregate_faults(contents: str) -> list[str]:
    """Require all job results and scope flags to reach an unconditional aggregate.

    The separate outcome controls execute its actual Python script for every
    result combination, including selected failures and intentional skips.
    """
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
    if extra := sorted(set(stated) - {"name", "shell", "env", "run"}):
        faults.append(f"the aggregate's step states {extra!r} beside its name, env and run, "
                      "so it can be skipped or run its line otherwise")
    expected = ["        env:",
                "          SCOPE_RESULT: ${{ needs.scope.result }}",
                "          SHARDS_RESULT: ${{ needs.host-gates-shard.result }}",
                "          DOCS_RESULT: ${{ needs.docs-checks.result }}",
                "          HOOKS_RESULT: ${{ needs.model-hooks.result }}",
                "          HOST_FULL: ${{ needs.scope.outputs.host_full }}",
                "          MODEL_HOOKS: ${{ needs.scope.outputs.model_hooks }}"]
    if _step_block(steps[0], "env") != expected:
        faults.append("the aggregate does not bind every job result and both scope flags")
    if _step_values(steps[0], "shell") != ["python"] or _step_values(steps[0], "run") != ["|"]:
        faults.append("the aggregate does not run its Python verdict script")
    return faults


def _aggregate_outcome_faults(contents: str) -> list[str]:
    steps = _step_texts(_workflow_jobs(contents)["host-gates"])
    script = textwrap.dedent(steps[0].split("        run: |\n", 1)[1])
    with tempfile.TemporaryDirectory(prefix="vos-aggregate-") as temporary:
        path = Path(temporary) / "aggregate.py"
        path.write_text(script, encoding="utf-8")
        results = ("SCOPE_RESULT", "SHARDS_RESULT", "DOCS_RESULT", "HOOKS_RESULT")
        for full, hooks in product(("true", "false", ""), repeat=2):
            for outcomes in product(("success", "skipped", "failure", "cancelled"), repeat=4):
                environment = dict(zip(results, outcomes, strict=True), HOST_FULL=full, MODEL_HOOKS=hooks)
                expected = (outcomes[0] == "success" and full in {"true", "false"}
                            and hooks in {"true", "false"}
                            and outcomes[1] == ("success" if full == "true" else "skipped")
                            and outcomes[2] == ("skipped" if full == "true" else "success")
                            and outcomes[3] == ("success" if hooks == "true" else "skipped"))
                accepted = True
                with patch.dict(os.environ, environment):
                    try:
                        runpy.run_path(str(path), run_name="__main__")
                    except SystemExit as error:
                        accepted = error.code in (None, 0)
                if accepted != expected:
                    return [f"aggregate gave {accepted}, expected {expected}: {environment}"]
    return []


def _workflow_host_aggregate_needs() -> None:
    # The aggregates are the platforms' verdicts: one that passed beside a failed shard or
    # a failed model-hooks job would report a run green that one of its jobs refused.
    contents = (ROOT / ".github/workflows" / ci.HOST).read_text(encoding="utf-8")
    found = _aggregate_faults(contents)
    ensure(not found, f"{ci.HOST}'s aggregates require every other job: {found!r}")
    ensure(not _aggregate_outcome_faults(contents),
           "the actual aggregate script accepts only successful scope and every selected gate")
    bindings = "        env:\n          SCOPE_RESULT:"
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
            (contents.replace("    needs: [scope, host-gates-shard, docs-checks, model-hooks]\n",
                              "    needs: host-gates-shard\n"), "not every other job"),
            (contents.replace("    if: ${{ always() }}\n", ""), "does not run whatever"),
            (contents.replace("${{ needs.model-hooks.result }}",
                              "${{ needs.host-gates-shard.result }}"), "does not bind every job"),
            (contents.replace("${{ needs.model-hooks.result }}", "success"),
             "does not bind every job")):
        ensure(mutant != contents, f"the fixture for {fragment!r} changed nothing")
        found = _aggregate_faults(mutant)
        ensure(any(fragment in fault for fault in found),
               f"an aggregate that can pass beside a failed job must be refused "
               f"({fragment!r}): {found!r}")
    for mutant in (contents.replace('if os.environ[name] != result:', 'if False:'),
                   contents.replace('if os.environ["SCOPE_RESULT"] != "success":', 'if False:'),
                   contents.replace('else "skipped",', 'else "success",', 1)):
        ensure(mutant != contents and bool(_aggregate_outcome_faults(mutant)),
               "accepting failed required jobs or unexpectedly skipped jobs must be detected")


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
    include entry naming one platform, every platform of the matrix must have one, the
    entries naming one platform must all name the same label, so its shards and its
    unpartitioned job share an image, and no label may be a moving `-latest` alias.
    Every `runs-on` is a block line whose value is either the shard job's
    `${{ matrix.runner }}`, stated once there and once in documentation checks when
    present, or one unquoted label fully
    matching `[A-Za-z0-9][A-Za-z0-9._-]*` without `latest`, so a YAML alias, a flow
    sequence, another expression or a trailing comment is refused.
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
    faults += [f"{name} names {sorted(set(labels))!r}, not one runner image for all its jobs"
               for name, labels in sorted(runners.items()) if len(set(labels)) > 1]
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
    documents = _job_text(contents, "docs-checks") if "\n  docs-checks:\n" in contents else None
    expected_count = 1 if documents is None else 2
    if documents is not None:
        docs_lines = [line for line in documents.split("\n") if not line.lstrip().startswith("#")]
        docs_runners = {_key_values(entry, "platform")[0]: _key_values(entry, "runner")
                        for entry in _include_entries(docs_lines)
                        if len(_key_values(entry, "platform")) == 1}
        if docs_runners != {name: [labels[0]] for name, labels in runners.items() if labels}:
            faults.append("documentation jobs do not name each platform's shard image")
    if runs_on.count(matrix_runner) > expected_count:
        faults.append(f"runs-on {matrix_runner} is stated {runs_on.count(matrix_runner)} "
                      "times, not once in the shard job" + (" and documentation job" if documents is not None else ""))
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
            (flow + "\n        runner: [ubuntu-26.04]", "outside a one-platform include"),
            (flow + "\n          - {platform: Windows, shard: unpartitioned, runner: windows-2022}",
             "not one runner image for all its jobs")):
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
    scripts: dict[tuple[str, str], str] = {}
    for workflow, job in _DISPATCH_JOBS:
        if workflow not in (ci.HOST, ci.GUEST):
            continue
        contents = (ROOT / ".github/workflows" / workflow).read_text(encoding="utf-8")
        checks = [step for step in _step_texts(_workflow_jobs(contents)[job])
                  if _step_values(step, "name") == [_GUARD]]
        ensure(len(checks) == 1, f"{workflow}'s {job} states one dispatch check")
        step = checks[0]
        wanted = ["          REQUESTED_REVISION: ${{ inputs.revision || github.sha }}",
                  "          DISPATCH_REF: ${{ github.ref }}",
                  "          DISPATCH_MAIN_SHA: ${{ github.sha }}"]
        if workflow == ci.HOST and job == "host-gates-shard":
            wanted.append("          PERFORMANCE_BASE: ${{ inputs.performance_base }}")
        elif workflow == ci.GUEST:
            wanted.append("          READING_BASE: ${{ inputs.reading_base }}")
        ensure(_step_values(step, "id") == ["dispatch"]
               and _step_values(step, "if") == ["${{ github.event_name == 'workflow_dispatch' }}"]
               and _step_values(step, "shell") == ["python"]
               and _step_values(step, "run") == ["|"]
               and not any(_step_values(step, key)
                           for key in ("uses", "working-directory", "continue-on-error"))
               and sorted(_step_block(step, "env")[1:]) == sorted(wanted),
               f"{workflow}'s {job} binds its dispatch check to the requested revision")
        # Each job's actual script is exercised below: optional comparison inputs
        # need not make otherwise equivalent checkout guards textually identical.
        scripts[workflow, job] = textwrap.dedent(step.split("        run: |\n", 1)[1])
    instrument, _ = _instrument_guard_faults(
        (ROOT / ".github/workflows" / INSTRUMENT).read_text(encoding="utf-8"))
    ensure(bool(instrument), f"{INSTRUMENT}'s guard steps are read")
    scripts.update(((INSTRUMENT, f"guard {n}"), script) for n, script in enumerate(instrument))
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
                  reading_base: str = "", performance_base: str = "") -> subprocess.CompletedProcess[str]:
            _git(root, "checkout", "--detach", checkout)
            environment = dict(os.environ, REQUESTED_REVISION=requested, DISPATCH_REF=ref,
                               DISPATCH_MAIN_SHA=main, READING_BASE=reading_base,
                               PERFORMANCE_BASE=performance_base)
            return subprocess.run([sys.executable, "-c", script], cwd=root, env=environment,
                                  capture_output=True, text=True, check=False, timeout=30)

        cases = ((base, base, base, "refs/heads/main", True),
                 (base, base, advanced, "refs/heads/main", True),
                 (advanced, base, advanced, "refs/heads/main", False),
                 (base, base[:7], advanced, "refs/heads/main", False),
                 (sibling, sibling, advanced, "refs/heads/main", False),
                 (base, base, advanced, "refs/heads/work/stranded", False))
        for checkout, requested, main, ref, passes in cases:
            for (workflow, job), script in scripts.items():
                done = guard(script, checkout, requested, main, ref)
                ensure((done.returncode == 0) == passes,
                       f"{workflow}'s {job} checkout guard gave wrong verdict: {done.stderr}")
        # Guest CI's reading base, when nonempty, is refused before checked-out code runs
        # unless it is a full lowercase commit that is a proper ancestor of the revision.
        guest = scripts[ci.GUEST, "guest-gates"]
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

        # Only the shard job takes a performance comparison base. Its actual guard
        # accepts a proper ancestor and refuses malformed or unrelated bases.
        host = scripts[ci.HOST, "host-gates-shard"]
        for checkout, performance_base, passes in (
                (advanced, base, True), (advanced, advanced, False),
                (advanced, base[:7], False), (advanced, "A" * 40, False),
                (advanced, "f" * 40, False), (advanced, tree, False),
                (advanced, sibling, False), (base, advanced, False)):
            done = guard(host, checkout, checkout, advanced, "refs/heads/main",
                         performance_base=performance_base)
            ensure((done.returncode == 0) == passes,
                   f"performance base {performance_base!r} gave wrong verdict: {done.stderr}")


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
    for job in jobs:
        depth = re.search(r"(?m)^          fetch-depth: .*\n", _job_text(contents, job))
        ensure(depth is not None, f"{ci.HOST}'s {job} checkout states its depth")
        line = depth[0] if depth else ""
        for workflow, fragment in (
                (_in_job(contents, job, line, "          fetch-depth: ${{ github.event_name == "
                         "'workflow_dispatch' && 0 || 1 }}\n"), "can check out"),
                (_in_job(contents, job, line, "          fetch-depth: 1\n"), "can check out"),
                (_in_job(contents, job, line, ""), "states 0 fetch-depth key(s)"),
                (_in_job(contents, job, line, line + line), "states 2 fetch-depth key(s)")):
            ensure(workflow != contents, f"the fixture for {fragment!r} changed nothing")
            found = _checkout_depth_faults(workflow, job)
            ensure(any(fragment in fault for fault in found),
                   f"a dispatch {job} checks out without main's history must be refused "
                   f"({fragment!r}): {found!r}")
        found = _checkout_depth_faults(_in_job(contents, job, line, "          fetch-depth: 0\n"), job)
        ensure(not found, f"full history on every run is accepted: {found!r}")


# The step that checks a dispatched revision, and the conjunct each later step that runs
# checked-out code after a failure states, in every job of each workflow that checks one:
# Host CI, Guest CI and the boot signature target campaign.
_DISPATCH_CHECK = "Verify dispatched revision belongs to main"
_DISPATCH_GUARD = "steps.dispatch.outcome != 'failure'"
_CAMPAIGN = "boot-crypto-target.yml"
_DISPATCH_JOBS = ((ci.HOST, "scope"), (ci.HOST, "host-gates-shard"),
                  (ci.HOST, "docs-checks"), (ci.HOST, "model-hooks"),
                  (ci.GUEST, "guest-gates"), (_CAMPAIGN, "plan"),
                  (_CAMPAIGN, "interface"), (_CAMPAIGN, "campaign"))


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
    named = {"scope": (), "docs-checks": (),
             "host-gates-shard": ("Analyze workflows", "Report gate results"),
             "model-hooks": ("Model hooks",),
             "guest-gates": ("Model evidence", "Proof gate",
                             "Read the proofs against the reading base", "Report guest results"),
             "plan": (), "interface": (), "campaign": ("Report the campaign",)}
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
    ensure(len(reads) == 5, f"the input is read where the step guards expect: {reads!r}")
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
    ensure("reading_base" not in host, "Host CI declares no reading base")


def cases() -> list[Case]:
    return [Case("remote-validation", _remote_validation),
            Case("state-validation", _state_validation),
            Case("scope-validation", _scope_validation),
            Case("malformed-phase-refusal", _phase_validation),
            Case("completed-handoff-provenance", _completed_handoff_provenance),
            Case("historical-validation-is-local", _historical_validation_is_local),
            Case("transport-contract", _transport_contract),
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
