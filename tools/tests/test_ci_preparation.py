# SPDX-License-Identifier: Apache-2.0
"""Campaign readiness and verified archive reuse, without a compiler or network."""

import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import textwrap
from pathlib import Path
from unittest.mock import patch

from ci import boot_chain_plan as plan
from tests import test_boot_chain as chain
from tests import test_fanout_ci as workflows
from tests.harness import TOOLS, Case, ensure, sandbox_tree
from tests.test_instrument_route import _commit, _git
from vos import boot_chain as bc
from vos import boot_chain_target as target


def _readiness() -> None:
    for value in ("0", "12001", "1.5", "-1", "", "999999999999999999999", " 1"):
        try:
            plan.case_timeout(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid case timeout {value!r} was accepted")
    ensure(plan.case_timeout("12000") == 12000 and plan.case_timeout("00001") == 1,
           "the timeout is bounded decimal seconds")
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        template, native = base / "template", base / "native"
        chain._checkout(template)
        with chain._staging(template, native):
            target.stage(template, native, Path("ccomp"), [])
            staged = plan.readiness(template, "12000")
            ensure(bool(staged.streams) and bool(staged.images), "valid staging is ready")
            output = base / "github-output"
            with patch.object(plan, "TOOLS", template / "tools"):
                ensure(plan.main(["--timeout", "00008", "--github-output", str(output)]) == 0
                       and output.read_text(encoding="utf-8") == "case_timeout=8\n",
                       "dependent jobs receive normalized decimal seconds, never an octal literal")
        for label in ("absent", "stale", "incomplete", "historical"):
            root = base / label
            shutil.copytree(template, root)
            if label == "absent":
                shutil.rmtree(root / bc.STAGED)
            elif label == "incomplete":
                (root / bc.IMAGES).unlink()
            elif label == "stale":
                source = root / next(iter(staged.manifest["sources_sha256"]))
                source.write_bytes(source.read_bytes() + b"\n")
            else:
                manifest = root / bc.MANIFEST
                data = json.loads(manifest.read_text(encoding="utf-8"))
                data["compiler_provenance"].pop("toolchain")
                manifest.write_text(json.dumps(data), encoding="utf-8")
            with chain._staging(root, base / f"native-{label}"):
                try:
                    plan.readiness(root, "12000")
                except ValueError:
                    pass
                else:
                    raise AssertionError(f"{label} staging allocated campaign runners")


def _workflow_dependencies() -> None:
    text = (TOOLS.parent / ".github/workflows/boot-chain-target.yml").read_text(encoding="utf-8")
    jobs = workflows._workflow_jobs(text)
    ensure("ref: ${{ github.sha }}" in jobs["plan"]
           and jobs["plan"].index("Verify requested revision belongs to main")
           < jobs["plan"].index("git\", \"checkout")
           < jobs["plan"].index("boot_chain_plan.py"),
           "the plan validates with the dispatching checkout before running requested code")
    ensure("--is-ancestor" in jobs["plan"] and "--end-of-options" in jobs["plan"]
           and "refs/heads/main" in jobs["plan"] and "[0-9a-f]{40}" in jobs["plan"],
           "the plan holds ref, exact commit and main ancestry")
    for name in ("cold-boot", "boot", "watchdog"):
        ensure("    needs: plan\n" in jobs[name], f"{name} can allocate before readiness")
    for name in ("cold-boot", "boot", "main-die", "watchdog"):
        ensure("CASE_TIMEOUT: ${{ needs.plan.outputs.case_timeout }}" in jobs[name],
               f"{name} does not consume the timeout the plan validated")
    ensure("needs: [plan, cold-boot]" in jobs["main-die"]
           and "needs: [plan, cold-boot, boot, main-die, watchdog]" in jobs["campaign"]
           and "needs.plan.result == 'success'" in jobs["campaign"],
           "no campaign job runs after a refused plan, including the diagnostic join")
    ensure("format('{0}', inputs.case_timeout)" in text,
           "a zero timeout is sent to readiness, never replaced by the default")
    host = (TOOLS.parent / ".github/workflows/host-gates.yml").read_text(encoding="utf-8")
    block = workflows._workflow_jobs(host)["host-gates-shard"]
    steps = {step.split("\n", 1)[0]: step for step in workflows._step_texts(block)}
    restore = steps["      - name: Restore the actionlint archive"]
    save = steps["      - name: Save the verified actionlint archive"]
    analysis = steps["      - name: Analyze workflows"]
    for step in (restore, save):
        ensure("matrix.platform == 'Ubuntu'" in step and "matrix.shard == 'unpartitioned'" in step
               and "path: ${{ runner.temp }}/toolchains/archives" in step
               and "key: actionlint-archive-${{ steps.actionlint.outputs.identity }}" in step,
               "only Ubuntu's unpartitioned job caches the identified archive, never its binary")
    ensure("github.ref == 'refs/heads/main'" in save and "github.event_name == 'push'" in save
           and "zizmor --offline" in analysis and "sh tools/ci/actionlint.sh" in analysis
           and "continue-on-error" not in analysis, "only main saves, both analyzers still decide")


def _plan_revision_guard() -> None:
    text = (TOOLS.parent / ".github/workflows/boot-chain-target.yml").read_text(encoding="utf-8")
    step = next(step for step in workflows._step_texts(workflows._workflow_jobs(text)["plan"])
                if "- name: Verify requested revision belongs to main\n" in step)
    script = textwrap.dedent(step.split("        run: |\n", 1)[1])
    with sandbox_tree({"README.md": "fixture\n"}) as root:
        _git(root, "config", "user.name", "fixture")
        _git(root, "config", "user.email", "fixture@example.invalid")
        base = _commit(root, {"README.md": "base\n"}, "base")
        tip = _commit(root, {"README.md": "main\n"}, "main")
        _git(root, "checkout", "--detach", base)
        foreign = _commit(root, {"README.md": "other\n"}, "other")
        for requested, ref, accepted in ((base, "refs/heads/main", True),
                                          (tip, "refs/heads/main", True),
                                          (tip[:8], "refs/heads/main", False),
                                          ("--help", "refs/heads/main", False),
                                          ("f" * 40, "refs/heads/main", False),
                                          (foreign, "refs/heads/main", False),
                                          (tip, "refs/heads/other", False)):
            _git(root, "checkout", "--detach", tip)
            environment = dict(os.environ, REQUESTED_REVISION=requested, DISPATCH_REF=ref,
                               DISPATCH_MAIN_SHA=tip)
            result = subprocess.run([sys.executable, "-c", script], cwd=root, env=environment,
                                    capture_output=True, text=True, check=False, timeout=15)
            ensure((result.returncode == 0) is accepted,
                   f"plan revision guard gave another verdict for {requested}/{ref}: {result.stderr}")
            actual = _git(root, "rev-parse", "HEAD")
            ensure(actual == (requested if accepted else tip),
                   "a refused plan changed checkout before validating its request")


def _archive_fixture(root: Path) -> tuple[Path, str, dict[str, str]]:
    archive = root / "fixture.tar.gz"
    executable = b'#!/bin/sh\nif [ "${1:-}" = -version ]; then echo 1.7.12; fi\n'
    with tarfile.open(archive, "w:gz") as output:
        member = tarfile.TarInfo("actionlint")
        member.size, member.mode = len(executable), 0o755
        output.addfile(member, io.BytesIO(executable))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    script = root / "actionlint.sh"
    script.write_text(re.sub(r"actionlint_sha=[0-9a-f]{64}", f"actionlint_sha={digest}",
                            (TOOLS / "ci/actionlint.sh").read_text(encoding="utf-8")),
                      encoding="utf-8", newline="\n")
    commands = root / "commands"
    commands.mkdir()
    curl = commands / "curl"
    curl.write_text('#!/bin/sh\nprintf "request\\n" >> "$REQUESTS"\n'
                    'while [ "$1" != --output ]; do shift; done\nshift\n'
                    'if [ "$CURL_MODE" = failed ]; then echo partial > "$1"; exit 22; fi\n'
                    'if [ "$CURL_MODE" = corrupt ]; then echo corrupt > "$1"; exit 0; fi\n'
                    'cp -- "$FIXTURE_ARCHIVE" "$1"\n', encoding="utf-8", newline="\n")
    curl.chmod(0o755)
    environment = dict(os.environ, PATH=f"{commands}{os.pathsep}{os.environ['PATH']}",
                       ACTIONLINT_ROOT=str(root / "toolchains"), FIXTURE_ARCHIVE=str(archive),
                       REQUESTS=str(root / "requests.log"), CURL_MODE="good")
    return script, digest, environment


def _invoke(script: Path, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["sh", str(script), "-version"], cwd=script.parent, env=environment,
                          capture_output=True, text=True, check=False, timeout=15)


def _archive_reuse() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        script, digest, environment = _archive_fixture(root)
        first = _invoke(script, environment)
        ensure(first.returncode == 0 and first.stdout.strip() == "1.7.12", first.stderr)
        directory = root / "toolchains"
        for prefix in directory.glob("actionlint_*"):
            shutil.rmtree(prefix)
        reused = _invoke(script, environment | {"CURL_MODE": "failed"})
        ensure(reused.returncode == 0 and (root / "requests.log").read_text().count("request") == 1
               and hashlib.sha256((directory / "archives" / f"{digest}.tar.gz").read_bytes()).hexdigest()
               == digest, f"verified archive reuse reached the network: {reused.stderr}")


def _archive_corruption_and_interruption() -> None:
    for mode in ("good", "failed", "corrupt"):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script, digest, environment = _archive_fixture(root)
            directory = root / "toolchains"
            cached = directory / "archives" / f"{digest}.tar.gz"
            cached.parent.mkdir(parents=True)
            cached.write_bytes(b"untrusted restored bytes")
            result = _invoke(script, environment | {"CURL_MODE": mode})
            ensure((result.returncode == 0) is (mode == "good"),
                   f"corruption was not independently decided: {mode}: {result.stderr}")
            ensure(not list(directory.glob(".actionlint_*.??????")),
                   "failed or successful publication left a temporary stage")
            if mode == "good":
                ensure(hashlib.sha256(cached.read_bytes()).hexdigest() == digest,
                       "corrupt cache was replaced only by verified bytes")
            else:
                ensure(not cached.exists() and not list(directory.glob("actionlint_*")),
                       "failed download or hash verification published an archive or executable")


def cases() -> list[Case]:
    return [Case("strict-staging-readiness", _readiness),
            Case("plan-checks-revision-before-checkout", _plan_revision_guard),
            Case("workflow-readiness-and-cache-wiring", _workflow_dependencies),
            Case("verified-archive-reuses-without-network", _archive_reuse, lane="guest"),
            Case("archive-corruption-and-interruption", _archive_corruption_and_interruption,
                 lane="guest")]
