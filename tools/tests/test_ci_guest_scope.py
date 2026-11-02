# SPDX-License-Identifier: Apache-2.0
"""Guest planning rejects malformed selections before allocating toolchain runners."""

import json
import os
import re
import subprocess
import tempfile
import textwrap
from pathlib import Path

from tests import test_fanout_ci as workflows
from tests.harness import TOOLS, Case, ensure

WORKFLOW = TOOLS.parent / ".github/workflows/guest-gates.yml"
LANES = ("model", "rtl", "proofs")


def _plan() -> str:
    contents = WORKFLOW.read_text(encoding="utf-8")
    changes = workflows._workflow_jobs(contents)["changes"]
    steps = [step for step in workflows._step_texts(changes)
             if workflows._step_values(step, "id") == ["plan"]]
    ensure(len(steps) == 1, "Guest CI has one planning step")
    return steps[0]


def _wiring() -> None:
    contents = WORKFLOW.read_text(encoding="utf-8")
    jobs = workflows._workflow_jobs(contents)
    changes, gates = jobs["changes"], jobs["guest-gates"]
    ensure(not re.search(r"(?m)^    if:", changes), "the plan runs for every trigger")
    ensure("actions/checkout@" not in changes and "tools/" not in changes,
           "planning runs no checked-out code or installation command")
    plan = _plan()
    env = workflows._step_block(plan, "env")
    ensure("          REQUESTED_LANES: ${{ inputs.lanes }}" in env
           and "          GUEST_EVENT: ${{ github.event_name }}" in env,
           "raw selection data reaches Bash only through its environment")
    ensure("          FORCE_ALL: ${{ github.event_name == 'schedule' || inputs.cold == true || "
           "inputs.reading_base != '' || github.run_attempt > 1 }}" in env,
           "scheduled, cold, proof-reading and repeated plans require all lanes")
    ensure("      matrix: ${{ steps.plan.outputs.matrix }}" in changes
           and "      matrix: ${{ fromJSON(needs.changes.outputs.matrix) }}" in gates,
           "the matrix comes from the validated plan")
    ensure("    needs: changes\n" in gates
           and "    if: ${{ !cancelled() && needs.changes.result == 'success' && "
           "needs.changes.outputs.unchanged != 'true' }}\n" in gates,
           "a failed or canceled plan cannot allocate guest runners")
    previous = [step for step in workflows._step_texts(changes)
                if workflows._step_values(step, "id") == ["previous"]]
    ensure(len(previous) == 1 and workflows._step_values(previous[0], "if") == [
        "${{ github.event.schedule == '23 4 * * 1' && github.run_attempt == 1 }}"],
        "only the ordinary weekly schedule can use previous full-suite evidence")
    for lane in LANES:
        ensure(f'grep -q "^guest-{lane}-$GITHUB_SHA-"' in previous[0],
               f"a partial manual run cannot supply the {lane} lane's scheduled evidence")


def _run(lanes: str, *, event: str = "workflow_dispatch", force_all: bool = False
         ) -> tuple[subprocess.CompletedProcess[str], str, str]:
    script = textwrap.dedent(_plan().split("        run: |\n", 1)[1])
    with tempfile.TemporaryDirectory(prefix="vos-guest-plan-") as directory:
        root = Path(directory)
        output, summary = root / "output", root / "summary"
        environment = {"PATH": os.defpath, "REQUESTED_LANES": lanes, "GUEST_EVENT": event,
                       "FORCE_ALL": str(force_all).lower(), "GITHUB_OUTPUT": str(output),
                       "GITHUB_STEP_SUMMARY": str(summary)}
        result = subprocess.run(["bash", "--noprofile", "--norc", "-euo", "pipefail", "-c", script],
                                cwd=root, env=environment, capture_output=True, text=True,
                                check=False, timeout=10)
        return (result, output.read_text(encoding="utf-8") if output.exists() else "",
                summary.read_text(encoding="utf-8") if summary.exists() else "")


def _selection() -> None:
    for requested, expected in (("all", LANES), ("model", ("model",)), ("rtl", ("rtl",)),
                                ("proofs", ("proofs",)), ("rtl,model", ("model", "rtl")),
                                ("proofs,model", ("model", "proofs"))):
        result, output, summary = _run(requested)
        ensure(result.returncode == 0, f"valid lanes {requested!r} failed: {result.stderr}")
        rows = json.loads(output.removeprefix("matrix="))["include"]
        ensure([row["lane"] for row in rows] == list(expected),
               f"requested {requested!r} allocated the wrong lanes: {rows!r}")
        for row in rows:
            lane = row["lane"]
            ensure(row["cache_lane"] == ("proofs" if lane == "proofs" else "model")
                   and row["toolchains"] == ("--toolchain rocq" if lane == "proofs" else
                                              "--toolchain sail --toolchain rtl --toolchain rocq"),
                   f"selection changed {lane}'s toolchain or cache ownership")
        ensure(summary == f"Guest CI lanes: `{','.join(expected)}`.\n",
               "the summary records exactly the selected lane set")


def _refusals() -> None:
    for requested in ("", "unknown", "all,rtl", "model,model", "proofs,rtl,proofs", "Model",
                      " model", "model ", "model,", ",rtl", "rtl,,proofs", "rtl\nproofs",
                      "$(echo model)", "model;exit 0"):
        result, output, summary = _run(requested)
        ensure(result.returncode != 0 and not output and not summary,
               f"invalid selection {requested!r} allocated a matrix or claimed a selection")


def _full_overrides() -> None:
    for requested, event, force_all in (("proofs", "workflow_dispatch", True),
                                        ("", "schedule", True), ("", "schedule", False)):
        result, output, _ = _run(requested, event=event, force_all=force_all)
        ensure(result.returncode == 0
               and [row["lane"] for row in json.loads(output.removeprefix("matrix="))["include"]]
               == list(LANES), "full acceptance must not inherit a narrower handoff selection")
    result, output, _ = _run("proofs,proofs", force_all=True)
    ensure(result.returncode != 0 and not output,
           "a full override cannot make a malformed dispatch input valid")


def cases() -> list[Case]:
    return [Case("guest selection precedes toolchain runner allocation", _wiring),
            Case("guest selections preserve lane and cache ownership", _selection, lane="guest"),
            Case("invalid guest selections allocate no matrix", _refusals, lane="guest"),
            Case("full acceptance overrides selective handoffs", _full_overrides, lane="guest")]
