# SPDX-License-Identifier: Apache-2.0
"""Cheap target readiness and shared setup preserve the campaign's trust boundary."""

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch

from ci import boot_crypto_plan as plan
from tests import test_boot_crypto as crypto
from tests import test_fanout_ci as workflows
from tests import test_guest_report as guest
from tests.harness import TOOLS, Case, ensure, sandbox_tree
from tests.test_instrument_route import _commit, _git
from vos import boot_crypto_target as target

WORKFLOW = TOOLS.parent / ".github/workflows/boot-crypto-target.yml"
SETUP = "./.target-ci/.github/actions/setup-target-sail"


def _readiness() -> None:
    for value in ("0", "9601", "1.5", "-1", "", "999999999999999999999", " 1", "\u0661"):
        try:
            plan.case_timeout(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid case timeout {value!r} was accepted")
    ensure(plan.case_timeout("9600") == 9600 and plan.case_timeout("1") == 1
           and plan.case_timeout("0008") == 8, "bounded decimal timeouts normalize")
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        template = base / "template"
        crypto._staged_root(template)
        ensure(plan.readiness(template, "9600") == len(target.MODES), "strict staging is ready")
        output = base / "github-output"
        with patch.object(plan, "TOOLS", template / "tools"):
            ensure(plan.main(["--timeout", "0008", "--github-output", str(output)]) == 0
                   and output.read_text(encoding="utf-8") == "case_timeout=8\n",
                   "dependent jobs receive normalized decimal seconds")
        for label in ("absent", "stale", "incomplete", "historical"):
            root = base / label
            shutil.copytree(template, root)
            if label == "absent":
                shutil.rmtree(root / target.STAGED)
            elif label == "stale":
                (root / target.SOURCE).write_bytes(b"int changed;\n")
            elif label == "incomplete":
                (root / target.STAGED / "slh.s").unlink()
            else:
                manifest = root / target.MANIFEST
                data = json.loads(manifest.read_text(encoding="utf-8"))
                data["compiler_provenance"].pop("toolchain")
                manifest.write_text(json.dumps(data), encoding="utf-8")
            try:
                plan.readiness(root, "9000")
            except (OSError, ValueError):
                pass
            else:
                raise AssertionError(f"{label} staging allocated campaign runners")
        normalized = base / "timeout-only"
        with patch.object(plan, "readiness", side_effect=AssertionError("requested staging read")):
            ensure(plan.main(["--timeout", "0008", "--timeout-only", "--github-output",
                              str(normalized)]) == 0
                   and normalized.read_text(encoding="utf-8") == "case_timeout=8\n",
                   "trusted timeout validation does not read another revision's staging")
            ensure(plan.main(["--timeout", "0", "--timeout-only", "--github-output",
                              str(base / "refused")]) == 1 and not (base / "refused").exists(),
                   "zero cannot publish an accepted timeout")


def _plan_steps() -> dict[str, str]:
    job = workflows._workflow_jobs(WORKFLOW.read_text(encoding="utf-8"))["plan"]
    return {step.split("\n", 1)[0]: step for step in workflows._step_texts(job)}


def _trusted_plan() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    jobs = workflows._workflow_jobs(text)
    trusted = jobs["plan"]
    ensure("ref: ${{ github.sha }}" in trusted
           and trusted.index("Verify dispatched revision belongs to main")
           < trusted.index("boot_crypto_plan.py") < trusted.index("Check out the planned revision")
           < trusted.index("run: python tools/run.py boot-crypto verify"),
           "the trusted checkout owns validation before requested code executes")
    ensure("    needs: plan\n" in jobs["interface"]
           and "CASE_TIMEOUT: ${{ needs.plan.outputs.case_timeout }}" in jobs["interface"]
           and "needs: [plan, interface]" in jobs["campaign"]
           and "needs.plan.result == 'success'" in jobs["campaign"],
           "a refused plan allocates neither interface runners nor a diagnostic join")
    ensure("format('{0}', inputs.case_timeout)" in text and "inputs.case_timeout ||" not in text,
           "zero is preserved for validation")
    steps = _plan_steps()
    guard = textwrap.dedent(steps["      - name: Verify dispatched revision belongs to main"].split(
        "        run: |\n", 1)[1])
    switch = textwrap.dedent(steps["      - name: Check out the planned revision"].split(
        "        run: |\n", 1)[1])
    readiness = shlex.split(steps["      - name: Verify campaign readiness"].split(
        "        run: ", 1)[1].strip())
    with sandbox_tree({"README.md": "fixture\n"}) as root:
        _git(root, "config", "user.name", "fixture")
        _git(root, "config", "user.email", "fixture@example.invalid")
        old = _commit(root, {"tools/run.py":
                            "import sys\nfrom pathlib import Path\n"
                            "if sys.argv[1:] != ['boot-crypto', 'verify']:\n"
                            "    raise SystemExit('wrong handler')\n"
                            "Path('verified').write_text('strict old verifier')\n"}, "old")
        tip = _commit(root, {"README.md": "main\n"}, "main")
        _git(root, "checkout", "--detach", old)
        foreign = _commit(root, {"README.md": "other\n"}, "other")
        for requested, ref, accepted in ((old, "refs/heads/main", True),
                                          (tip, "refs/heads/main", True),
                                          (tip[:8], "refs/heads/main", False),
                                          ("--help", "refs/heads/main", False),
                                          ("f" * 40, "refs/heads/main", False),
                                          (foreign, "refs/heads/main", False),
                                          (tip, "refs/heads/other", False)):
            _git(root, "checkout", "--detach", tip)
            environment = dict(os.environ, REQUESTED_REVISION=requested, DISPATCH_REF=ref,
                               DISPATCH_MAIN_SHA=tip)
            result = subprocess.run([sys.executable, "-c", guard], cwd=root, env=environment,
                                    capture_output=True, text=True, check=False, timeout=15)
            ensure((result.returncode == 0) is accepted,
                   f"plan revision guard changed verdict: {requested}/{ref}: {result.stderr}")
            ensure(_git(root, "rev-parse", "HEAD") == tip, "validation checks out no requested code")
        environment = dict(os.environ, REQUESTED_REVISION=old, DISPATCH_REF="refs/heads/main",
                           DISPATCH_MAIN_SHA=tip)
        subprocess.run([sys.executable, "-c", switch], cwd=root, env=environment,
                       check=True, capture_output=True, timeout=15)
        ensure(not (root / "tools/ci/boot_crypto_plan.py").exists(), "the old fixture has no helper")
        subprocess.run([sys.executable, *readiness[1:]], cwd=root, env=environment,
                       check=True, capture_output=True, timeout=15)
        ensure((root / "verified").read_text() == "strict old verifier",
               "an older pinned revision runs its existing strict verifier")


def _caller_faults(text: str, job: str, verifier: str) -> list[str]:
    block = workflows._workflow_jobs(text)[job]
    steps = workflows._step_texts(block)
    local = [index for index, step in enumerate(steps)
             if workflows._step_values(step, "uses") == [SETUP]]
    faults = workflows._refused_dispatch_faults(text, job)
    if len(local) != 1:
        return [*faults, "caller must run the shared setup exactly once"]
    index = local[0]
    prior = steps[:index]
    verified = [n for n, step in enumerate(prior) if verifier in step]
    trusted = [n for n, step in enumerate(prior)
               if "name: Check out the trusted target setup action\n" in step]
    if (len(verified) != 1 or len(trusted) != 1 or verified[0] >= trusted[0]
            or workflows._step_values(prior[verified[0]], "continue-on-error")):
        faults.append("revision and strict staging must precede the trusted action checkout")
    elif any(value not in prior[trusted[0]] for value in (
            "ref: ${{ github.sha }}", "path: .target-ci",
            "sparse-checkout: .github/actions/setup-target-sail",
            "persist-credentials: false", "submodules: false")):
        faults.append("the action must come only from the trusted dispatching commit")
    if "timeout-minutes: 125" not in steps[index]:
        faults.append("the setup caller needs its timeout backstop")
    return faults


def _shared_setup() -> None:
    action = guest.TARGET_SETUP.read_text(encoding="utf-8")
    gates = guest.WORKFLOW.read_text(encoding="utf-8")
    ensure(not guest._campaign_restore_faults(gates, action), "shared setup keeps model cache identities")
    ensure("using: composite" in action and "actions/cache/save@" not in action
           and "timeout --kill-after=60s 120m python3 tools/ci/bootstrap_guest.py" in action
           and 'tee "$RUNNER_TEMP/guest-bootstrap-console.log"' in action
           and "python3 tools/run.py model build" not in action,
           "setup is bounded, retains bootstrap logs, builds no model and saves no cache")
    for step in workflows._step_texts(action):
        if workflows._step_values(step, "run"):
            ensure(workflows._step_values(step, "shell") == ["bash"], "setup shell preserves pipefail")
        else:
            ensure(workflows._step_values(step, "uses") == [
                "actions/cache/restore@55cc8345863c7cc4c66a329aec7e433d2d1c52a9"],
                "the action runs only its pinned cache restores")
    for path, jobs, verifier in (
            (WORKFLOW, ("interface",), "python3 tools/run.py boot-crypto verify"),
            (WORKFLOW.with_name("boot-chain-target.yml"),
             ("cold-boot", "boot", "main-die", "watchdog"),
             "python3 tools/run.py boot-handoff chain-verify")):
        text = path.read_text(encoding="utf-8")
        ensure(text.count(f"uses: {SETUP}\n") == len(jobs), "every target runner shares its setup")
        for job in jobs:
            ensure(not _caller_faults(text, job, verifier), f"{path.name}/{job} lost its setup guard")
            block = workflows._workflow_jobs(text)[job]
            changed = block.replace("ref: ${{ github.sha }}", "ref: ${{ inputs.revision }}", 1)
            ensure(changed != block and bool(_caller_faults(text.replace(block, changed, 1), job, verifier)),
                   "a setup action from the requested revision is refused")
            changed = block.replace(verifier, "echo skipped verifier", 1)
            ensure(changed != block and bool(_caller_faults(text.replace(block, changed, 1), job, verifier)),
                   "a setup action before strict staging is refused")


def cases() -> list[Case]:
    return [Case("strict-signature-readiness-and-timeouts", _readiness),
            Case("trusted-plan-and-older-pinned-revision", _trusted_plan),
            Case("shared-target-setup-guards-and-cache-ownership", _shared_setup)]
