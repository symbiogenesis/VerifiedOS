# SPDX-License-Identifier: Apache-2.0
"""The sweep publishes measurements only for a current, wholly successful execution.

Patches replace this module's dependencies rather than shared module attributes:
the host test runner executes other modules concurrently in the same process.
"""

import io
import json
import os
import subprocess
import sys
import tempfile
import threading
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from tests.harness import Case, ensure
from vos import env, receipts
from vos.cli import evidence
from vos.report import Reporter

_OUTPUT = {
    "build": "build completed\n",
    "reference": "model revision abc\nproperties 4\ncorpus v1, 2 members, 3 checks, 4 records\n",
    "sweep": "TOTAL pass=1 refuse=1 hang=0 of 2\n",
    "corpus": "TOTAL pass=2 fail=0 of 2\n",
    "devicetree": "ok at 123 bytes\n",
    "proofs": "ok: 7 constant(s) checked\n",
}


def _scenario(*, build: bool = False, failed: str = "", absent: str = "",
              receipt_error: Exception | None = None, changed_inputs: bool = False,
              changed_build: bool = False,
              proof_error: Exception | None = None,
              lock_failed: str = "", changed_tools: bool = False
              ) -> tuple[Reporter, str, list[str]]:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as temporary:
        root = Path(temporary)
        e = env.Environment(root, root / "model", root / "build", root / "logs",
                            "", 4, 4096, 2, 2)
        e.log_dir.mkdir()
        e.log("model-build").write_text(
            "100% tests passed, 0 tests failed out of 3\nALL_DONE\n", encoding="utf-8")
        held, locked = io.StringIO(), io.StringIO()
        lock_error = SystemExit("another process holds the workspace")
        fake_env = SimpleNamespace(
            load=lambda: e,
            hold_lock=(Mock(side_effect=lock_error) if lock_failed == "evidence"
                       else lambda *args: held),
            build_lock=(Mock(side_effect=lock_error) if lock_failed == "build"
                        else lambda *args: locked))
        before = {"source": "before"}
        after = {"source": "after"} if changed_inputs else before
        fake_receipts = SimpleNamespace(inputs=Mock(side_effect=[before, after]),
                                        write=receipts.write,
                                        executables=Mock(side_effect=[
                                            {"dtc": "before"},
                                            {"dtc": "after" if changed_tools else "before"}]))
        verify = Mock(side_effect=receipt_error) if receipt_error else Mock(
            side_effect=[{"identity": "before"},
                         {"identity": "after" if changed_build else "before"}])
        fake_model = SimpleNamespace(BUILD_INPUTS=("model",), verified_build=verify)
        verify_proofs = (Mock(side_effect=proof_error) if proof_error else
                         Mock(return_value={"sha256": "proof receipt",
                                            "receipt": {"outputs": {"proof.vo": "bytes"}}}))
        launched: list[str] = []
        proof_started = threading.Event()
        reference_finished = threading.Event()

        def launch(member: evidence.Member) -> evidence.Result:
            launched.append(member.name)
            ensure(not held.closed, "every member must run under the evidence lock")
            if member.name != "build":
                ensure(not locked.closed, "every model consumer must hold the build stable")
            if member.name == "proofs":
                proof_started.set()
                ensure(reference_finished.wait(5), "proofs and model consumers must overlap")
            elif member.name == "reference":
                ensure(proof_started.wait(5), "the proof subprocess should already be running")
                reference_finished.set()
            return evidence.Result(member.name, member.command,
                                   1 if member.name == failed else 0,
                                   "" if member.name == absent else _OUTPUT[member.name],
                                   "diagnostic\n" if member.name == failed else "", 0.01)

        out = root / "record.json"
        with (patch.object(evidence, "env", fake_env),
              patch.object(evidence, "receipts", fake_receipts),
              patch.object(evidence, "model_cli", fake_model),
              patch.object(evidence, "_proof_record", verify_proofs),
              patch.object(evidence, "_launch", launch)):
            result = evidence.run(build=build, out=out)
        if lock_failed != "evidence":
            ensure(held.closed, "the evidence lock must close on every outcome")
        if not lock_failed and not (build and failed == "build"):
            ensure(locked.closed, "the build lock must close on every outcome")
        return result, out.read_text(encoding="utf-8"), launched


def _successful_sweep_records_each_process() -> None:
    report, text, launched = _scenario(build=True)
    record = json.loads(text)
    ensure(report.findings == 0 and record["exit_code"] == 0, "a current full sweep succeeds")
    ensure(set(launched) == set(_OUTPUT) and len(launched) == len(_OUTPUT),
           "each member must run exactly once")
    ensure(record["measurements"]["ctest"] == "3 of 3"
           and record["measurements"]["proof gate"] == "7", "measurements retain their producer")
    ensure(len(record["members"]) == len(_OUTPUT)
           and all(member["exit_code"] == 0 for member in record["members"]),
           "execution records must preserve every member verdict")
    ensure("=== exit evidence ===" in report.out, "successful measurements should be displayed")
    ensure(record["proofs"]["receipt"]["outputs"] == {"proof.vo": "bytes"},
           "the final proof receipt must bind its compiled outputs into the sweep")


def _member_failure_suppresses_measurements() -> None:
    for failed in ("reference", "sweep", "corpus", "devicetree", "proofs"):
        report, text, launched = _scenario(failed=failed)
        record = json.loads(text)
        ensure(report.findings > 0 and record["exit_code"] != 0, f"{failed} must fail the sweep")
        ensure(record["measurements"] == {} and "=== exit evidence ===" not in report.out,
               f"{failed}'s plausible output must not produce successful measurements")
        ensure(set(launched) == set(_OUTPUT) - {"build"},
               "independent members still report their outcomes after a member fails")
        ensure(any(member["name"] == failed and member["stderr"] == "diagnostic\n"
                   for member in record["members"]), "the failed process diagnostic must survive")


def _build_failure_stops_consumers() -> None:
    report, text, launched = _scenario(build=True, failed="build")
    record = json.loads(text)
    ensure(launched == ["build"], "failed build must stop all dependent evidence collection")
    ensure(report.findings > 0 and record["measurements"] == {},
           "failed build must publish an unsuccessful record without measurements")


def _missing_or_stale_receipt_stops_consumers() -> None:
    for error in (FileNotFoundError("missing receipt"), ValueError("stale receipt")):
        report, text, launched = _scenario(receipt_error=error)
        record = json.loads(text)
        ensure(not launched, "--no-build must validate the receipt before launching any consumer")
        ensure(report.findings > 0 and record["measurements"] == {}
               and str(error) in record["failures"], "the rejected receipt must remain a finding")


def _changed_inputs_and_artifacts_invalidate_measurements() -> None:
    for key in ("changed_inputs", "changed_build", "changed_tools"):
        report, text, _ = _scenario(changed_inputs=key == "changed_inputs",
                                    changed_build=key == "changed_build",
                                    changed_tools=key == "changed_tools")
        record = json.loads(text)
        ensure(report.findings > 0 and record["measurements"] == {}
               and "=== exit evidence ===" not in report.out,
               "source or artifact changes after successful members invalidate the sweep")


def _missing_measurement_is_a_failure() -> None:
    report, text, _ = _scenario(absent="reference")
    record = json.loads(text)
    ensure(report.findings > 0 and record["measurements"] == {},
           "a zero exit without the promised measurements must fail")


def _changed_proof_outputs_invalidate_measurements() -> None:
    for error in (FileNotFoundError("missing proof receipt"),
                  ValueError("compiled proof artifacts have changed")):
        report, text, _ = _scenario(proof_error=error)
        record = json.loads(text)
        ensure(report.findings > 0 and record["measurements"] == {}
               and str(error) in record["failures"],
               "successful proof stdout cannot substitute for current compiled evidence")


def _lock_refusal_records_failure() -> None:
    for lock in ("evidence", "build"):
        report, text, launched = _scenario(lock_failed=lock)
        record = json.loads(text)
        ensure(not launched and report.findings > 0 and record["exit_code"] == 1
               and record["measurements"] == {},
               "a busy workspace must produce a failed execution record without consumers")


def _ctest_requires_nonempty_complete_success() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as temporary:
        path = Path(temporary) / "build.log"
        for text in ("100% tests passed, 0 tests failed out of 0\nALL_DONE\n",
                     "100% tests passed, 0 tests failed out of 3\n",
                     "67% tests passed, 1 tests failed out of 3\nALL_DONE\n",
                     "ALL_DONE\n"):
            path.write_text(text, encoding="utf-8")
            try:
                evidence._ctest(path)
            except ValueError:
                continue
            raise AssertionError(f"invalid ctest evidence was accepted: {text!r}")


def _launch_uses_an_isolated_subprocess() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as temporary:
        before_directory = Path.cwd()
        before_marker = os.environ.get("VOS_EVIDENCE_TEST_CHILD")
        program = ("import os, sys; os.chdir(sys.argv[1]); "
                   "os.environ['VOS_EVIDENCE_TEST_CHILD'] = 'child'; "
                   "print(os.getpid()); print(os.getcwd()); "
                   "print('child diagnostic', file=sys.stderr); sys.exit(3)")
        fake_cli = SimpleNamespace(entry=lambda *args: [sys.executable, "-c", program, temporary])
        with patch.object(evidence, "cli", fake_cli), redirect_stdout(io.StringIO()):
            found = evidence._launch(evidence.Member("isolation", ("unused",)))
        ensure(found.exit_code == 3 and found.stderr == "child diagnostic\n",
               "subprocess exit and stderr must be captured independently")
        ensure(int(found.stdout.splitlines()[0]) != os.getpid(), "a member must use another process")
        ensure(Path.cwd() == before_directory
               and os.environ.get("VOS_EVIDENCE_TEST_CHILD") == before_marker,
               "child process changes must not alter the orchestration process")


def _launch_failure_is_a_result() -> None:
    fake = SimpleNamespace(Popen=Mock(side_effect=OSError("cannot launch")), PIPE=subprocess.PIPE)
    with patch.object(evidence, "subprocess", fake), redirect_stdout(io.StringIO()):
        found = evidence._launch(evidence.Member("missing", ("unused",)))
    ensure(found.exit_code != 0 and "cannot launch" in found.stderr,
           "failure to start a member must be recorded as a failed execution")


def _timeout_kills_the_process_group() -> None:
    kill_group = Mock()
    child = MagicMock()
    child.pid = 12345
    child.__enter__.return_value = child
    calls = 0

    def communicate(*, timeout: int | None = None) -> tuple[str, str]:
        nonlocal calls
        calls += 1
        if calls == 1:
            ensure(timeout == 17, "the member's configured timeout must reach communicate")
            raise subprocess.TimeoutExpired("child", 17)
        ensure(kill_group.called, "the process group must be killed before draining its pipes")
        return "partial output\n", "partial error\n"

    child.communicate.side_effect = communicate
    popen = Mock(return_value=child)
    fake_process = SimpleNamespace(Popen=popen, PIPE=subprocess.PIPE,
                                   TimeoutExpired=subprocess.TimeoutExpired)
    with (patch.object(evidence, "subprocess", fake_process),
          patch.object(evidence, "os", SimpleNamespace(killpg=kill_group)),
          patch.object(evidence, "signal", SimpleNamespace(SIGKILL=9)),
          patch.object(evidence, "TIMEOUTS", {"hang": 17}),
          redirect_stdout(io.StringIO())):
        found = evidence._launch(evidence.Member("hang", ("unused",)))
    ensure(found.exit_code != 0 and found.stdout == "partial output\n"
           and "partial error" in found.stderr and "timed out" in found.stderr,
           "timeout must retain captured diagnostics and a failed result")
    ensure(popen.call_args.kwargs["start_new_session"] is True,
           "the member must own the process group the timeout kills")
    kill_group.assert_called_once_with(12345, 9)


def cases() -> list[Case]:
    return [
        Case("successful-sweep-records-processes", _successful_sweep_records_each_process),
        Case("member-failure-suppresses-measurements", _member_failure_suppresses_measurements),
        Case("build-failure-stops-consumers", _build_failure_stops_consumers),
        Case("missing-stale-receipts-stop-consumers", _missing_or_stale_receipt_stops_consumers),
        Case("changed-inputs-artifacts-invalidate", _changed_inputs_and_artifacts_invalidate_measurements),
        Case("missing-measurement-fails", _missing_measurement_is_a_failure),
        Case("changed-proof-outputs-invalidate", _changed_proof_outputs_invalidate_measurements),
        Case("lock-refusal-recorded", _lock_refusal_records_failure),
        Case("ctest-complete-nonempty-success", _ctest_requires_nonempty_complete_success),
        Case("launch-subprocess-isolation", _launch_uses_an_isolated_subprocess),
        Case("launch-failure-recorded", _launch_failure_is_a_result),
        Case("timeout-kills-process-group", _timeout_kills_the_process_group),
    ]
