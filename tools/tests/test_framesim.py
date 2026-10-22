# SPDX-License-Identifier: Apache-2.0
"""Frame simulation's assertion policy at the compiler and process boundaries.

Host controls substitute process outcomes, retaining the real command construction
and frame decoder. The native framesim command runs the authored assertion bench
under the locked Verilator and supplies the actual elaboration/runtime evidence.
"""

import io
import subprocess
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure
from vos import rtltrace
from vos.cli import testrig

_ROOT = TOOLS.parent
_DISABLE = "assertion-policy: disable requested\n"
_PASS = _DISABLE + "assertion-policy: assertion passed\nassertion-policy: completed\n"
_FAIL = _DISABLE + "assertion-policy: assertion failed\n"
_SUPPRESSED = _DISABLE + "assertion-policy: completed\n"


def _done(code: int = 0, output: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], code, output, "")


def _frame_build_and_run_are_assertion_enabled() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-framesim-") as td:
        work = Path(td)
        drives = testrig._synthetic_drives()
        want = [drive.retire for drive in drives if drive.retire is not None]
        with patch.object(testrig.subprocess, "run", return_value=_done()) as run:
            testrig._verilate("pinned-verilator", _ROOT, work,
                              _ROOT / testrig.HARNESS_SOURCES[0])
        command = run.call_args.args[0]
        ensure(command[0] == "pinned-verilator" and "--assert" in command,
               f"the frame bench must compile with assertions: {command}")
        ensure(command[-1] == str(_ROOT / testrig.HARNESS_SOURCES[1]),
               "the assertion-enabled command still builds the actual frame bench")
        ensure(run.call_args.kwargs["cwd"] == work,
               "native compilation uses its assigned output directory")
        # The runner removes stale frames before launch. The substitute process
        # writes what a successful bench would write, which the real decoder reads.
        def emit(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            frame = next(arg.removeprefix("+frame=") for arg in command
                         if arg.startswith("+frame="))
            Path(frame).write_text(rtltrace.encode(want), encoding="utf-8", newline="\n")
            return _done()

        with patch.object(testrig.subprocess, "run", side_effect=emit) as run:
            got, why = testrig._framesim_one(work / "framesim", work, "synthetic", drives)
        ensure(got == want and not why,
               f"the locked run retains the actual frame round trip: {why}")
        ensure(testrig.ASSERTION_LOCK in run.call_args.args[0],
               "every frame execution locks assertions at startup")
        ensure(run.call_args.kwargs["cwd"] == work,
               "native simulation uses its assigned output directory")


def _policy_commands_and_verdicts() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-framesim-") as td:
        work = Path(td)
        with patch.object(testrig.subprocess, "run", side_effect=[
                _done(), _done(output=_PASS), _done(-6, _FAIL),
                _done(output=_SUPPRESSED)]) as run, redirect_stdout(io.StringIO()):
            failures = testrig._assertion_controls("pinned-verilator", _ROOT, work)
        ensure(failures == 0, "the passing, caught and disabled controls jointly pass")
        compile_command, passing, failing, unlocked = [call.args[0]
                                                      for call in run.call_args_list]
        ensure("--assert" in compile_command and str(_ROOT / testrig.ASSERTION_BENCH)
               in compile_command, "the actual policy fixture compiles with assertions")
        ensure(testrig.ASSERTION_LOCK in passing and "+fail" not in passing,
               "the positive control locks an assertion that should pass")
        ensure(testrig.ASSERTION_LOCK in failing and "+fail" in failing,
               "the failure control locks the same assertion with a failing input")
        ensure(testrig.ASSERTION_LOCK not in unlocked and "+fail" in unlocked,
               "the negative control changes only the lock on the failing input")
        ensure(all(call.kwargs["cwd"] == work / "assertion-policy"
                   for call in run.call_args_list), "all policy processes use the native lane")
        ensure((work / "assertion-policy" / "locked-fail.log").read_text() == _FAIL,
               "the assertion failure evidence is retained independently")


def _build_failure_is_not_detection() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-framesim-") as td:
        out = io.StringIO()
        with patch.object(testrig.subprocess, "run", return_value=_done(1, "compiler error")) as run, \
                redirect_stdout(out):
            failures = testrig._assertion_controls("pinned-verilator", _ROOT, Path(td))
        ensure(failures == 1 and run.call_count == 1 and "STILLBORN" in out.getvalue(),
               "a compiler refusal fails the policy without claiming any assertion detection")


def _runtime_refusals() -> None:
    # Neither a crash without the assertion marker nor successful execution of the
    # supposedly failing locked case supplies detection. The unlocked arm must
    # actually suppress the assertion, and the passing arm must evaluate it.
    controls = (
        (_done(output=_SUPPRESSED), _done(-6, _FAIL), _done(output=_SUPPRESSED)),
        (_done(output=_PASS), _done(-6, "segmentation fault"), _done(output=_SUPPRESSED)),
        (_done(output=_PASS), _done(output=_SUPPRESSED), _done(output=_SUPPRESSED)),
        (_done(output=_PASS), _done(-6, _FAIL), _done(-6, _FAIL)),
        (_done(output=_PASS), _done(-6, _FAIL), _done(output=_PASS)),
    )
    with tempfile.TemporaryDirectory(prefix="vos-test-framesim-") as td:
        for outcomes in controls:
            with patch.object(testrig.subprocess, "run", side_effect=[_done(), *outcomes]), \
                    redirect_stdout(io.StringIO()):
                failures = testrig._assertion_controls("pinned-verilator", _ROOT, Path(td))
            ensure(failures == 1, f"an invalid process outcome fails exactly its arm: {outcomes}")


def _normal_framesim_requires_policy() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-framesim-") as td:
        location = SimpleNamespace(root=_ROOT, lane_root=Path(td))
        want = [drive.retire for drive in testrig._synthetic_drives()
                if drive.retire is not None]
        for policy_failures in (0, 1):
            with patch.object(testrig.env, "load", return_value=location), \
                    patch.object(testrig.env, "hold_lock", return_value=io.StringIO()), \
                    patch.object(testrig.rtl, "_require_verilator", return_value="pinned-verilator"), \
                    patch.object(testrig, "_assertion_controls", return_value=policy_failures) as policy, \
                    patch.object(testrig, "_verilate", return_value=_done()), \
                    patch.object(testrig, "_framesim_one", return_value=(want, "")), \
                    redirect_stdout(io.StringIO()):
                code = testrig.main(["framesim"])
            ensure(policy.call_count == 1 and code == policy_failures,
                   "ordinary framesim always runs the assertion controls and propagates their refusal")


def cases() -> list[Case]:
    return [
        Case("frame-build-and-run-are-assertion-enabled", _frame_build_and_run_are_assertion_enabled),
        Case("policy-commands-and-verdicts", _policy_commands_and_verdicts),
        Case("build-failure-is-not-detection", _build_failure_is_not_detection),
        Case("runtime-refusals", _runtime_refusals),
        Case("normal-framesim-requires-policy", _normal_framesim_requires_policy),
    ]
