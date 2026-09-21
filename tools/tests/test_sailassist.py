# SPDX-License-Identifier: Apache-2.0
"""Repair budgets, immutable constraints, crash state and exact diagnostic bytes."""

import base64
import hashlib
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stderr, redirect_stdout, suppress
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from tests.harness import TOOLS, Case, ensure, sandbox_tree
from vos import env, sailassist
from vos.cli import BY_NAME
from vos.cli import sail_assist as cli


@contextmanager
def _session(*, limit: int = 12, seconds: int = 1800) -> Iterator[tuple[Path, Path, Path]]:
    files = {"docs/requirements-register.md": "# R-15-001\n",
             "docs/hardware/isa-profile.md": "frozen ISA\n",
             "model/config/verifiedos.json": "{}\n",
             "model/model/a.sail": "function example() = 0\n"}
    selected = {"binaries": {"python": "1" * 64}, "library_root": None, "libraries": {}}
    with (sandbox_tree(files) as root, patch.object(sailassist, "_git", return_value="a" * 40),
          patch.object(sailassist, "toolchain", return_value=selected)):
        directory = root / "out" / "sessions" / "sample"
        plan = {"target": "example", "requirements": ["R-15-001"],
                "frozen_constraints": ["preserve the ISA"], "affected_paths": ["model/model/a.sail"],
                "validation_plan": ["model typecheck", "model build", "model corpus"]}
        sailassist.initialize(root, directory, plan, limit, seconds)
        yield root, directory, root / "out" / "logs"


def _run_script(script: str, cwd: Path, logs: Path, timeout: float) -> dict[str, Any]:
    return sailassist.process([sys.executable, "-c", script], cwd, logs, timeout)


def _raw_process_bytes() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-assist-") as temporary:
        root = Path(temporary)
        script = "import os; os.write(1,b'out\\xff\\r\\n'); os.write(2,b'err\\x00\\n'); raise SystemExit(7)"
        report = _run_script(script, root, root / "logs", 10)
        sailassist.validate(report, "process")
        ensure(report["outcome"] == "completed" and report["exit_code"] == 7, "preserve actual child status")
        for name, expected in (("stdout", b"out\xff\r\n"), ("stderr", b"err\x00\n")):
            stream = report[name]
            ensure(base64.b64decode(stream["base64"]) == expected and
                   Path(stream["path"]).read_bytes() == expected, "raw diagnostics must not be normalized")
            ensure(stream["sha256"] == hashlib.sha256(expected).hexdigest(), "raw hash binds emitted bytes")
        timed = _run_script("import time; time.sleep(10)", root, root / "timeout", 0.03)
        ensure(timed["outcome"] == "timeout" and timed["exit_code"] != 0, "timeout must terminate the child")
        absent = sailassist.process([str(root / "absent-compiler")], root, root / "absent", 1)
        ensure(absent["outcome"] == "launch_error" and absent["exit_code"] is None and absent["launch_error"],
               "launch failure is not a compiler verdict")


def _bounded_inline_output() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-assist-") as temporary:
        root = Path(temporary)
        result = _run_script("import os; os.write(1,b'x'*2097153)", root, root / "logs", 10)
        stream = result["stdout"]
        ensure(stream["base64"] is None and stream["inline_truncated"] and stream["bytes"] == 2097153,
               "oversized diagnostics must stay in the complete log without unbounded inline output")
        ensure(Path(stream["path"]).stat().st_size == 2097153, "the bound must not truncate the original log")


def _wait_stopped(pid: int) -> None:
    deadline = time.monotonic() + 3
    while True:
        try:
            state = Path(f"/proc/{pid}/stat").read_text().rpartition(")")[2].split()[0]
        except FileNotFoundError:
            return
        if state in {"Z", "X"}:
            return
        ensure(time.monotonic() < deadline, f"descendant {pid} still running after cleanup (state {state})")
        time.sleep(0.01)


def _timeout_process_tree() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-tree-") as temporary:
        root = Path(temporary)
        script = ("import subprocess,sys,time; "
                  "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
                  "print(child.pid,flush=True); time.sleep(30)")
        report = _run_script(script, root, root / "tree", 2)
        ensure(report["outcome"] == "timeout", "the parent must reach its finite deadline")
        pid = int(base64.b64decode(report["stdout"]["base64"]))
        if sys.platform == "win32":
            # An inherited child handle prevents this unlink on Windows.
            Path(report["stdout"]["path"]).unlink()
            Path(report["stderr"]["path"]).unlink()
        else:
            try:
                _wait_stopped(pid)
            finally:
                with suppress(ProcessLookupError):
                    os.kill(pid, signal.SIGKILL)


def _resistant_descendant() -> None:
    # The grandchild reports readiness only after installing its SIGTERM handler.
    child_script = ("import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                    "print('ready',flush=True); time.sleep(30)")
    for exited in (False, True):
        with tempfile.TemporaryDirectory(prefix="vos-sail-resistant-") as temporary:
            root = Path(temporary)
            script = ("import subprocess,sys,time; "
                      f"child=subprocess.Popen([sys.executable,'-c',{child_script!r}],stdout=subprocess.PIPE,text=True); "
                      "print(child.pid,flush=True); print(child.stdout.readline().strip(),flush=True); "
                      + ("raise SystemExit(0)" if exited else "time.sleep(30)"))
            with (root.joinpath("stdout").open("wb") as output,
                  subprocess.Popen([sys.executable, "-c", script], cwd=root, stdout=output,
                                   start_new_session=True) as leader):
                descendant = 0
                try:
                    deadline = time.monotonic() + 5
                    while True:
                        lines = (root / "stdout").read_text().splitlines()
                        if lines:
                            descendant = int(lines[0])
                        if lines[1:] == ["ready"]:
                            break
                        ensure(time.monotonic() < deadline, "resistant child never completed its readiness handshake")
                        time.sleep(0.01)
                    if exited:
                        ensure(leader.wait(timeout=5) == 0, "the parent must exit before testing remaining-group cleanup")
                    else:
                        try:
                            leader.wait(timeout=0.03)
                        except subprocess.TimeoutExpired:
                            pass
                        else:
                            raise AssertionError("the ready process tree must reach its timeout")
                    sailassist._stop(leader)
                    if descendant <= 0:
                        raise AssertionError("the readiness handshake must identify the child")
                    _wait_stopped(descendant)
                finally:
                    with suppress(ProcessLookupError):
                        os.killpg(leader.pid, signal.SIGKILL)
                    leader.wait(timeout=5)
                    if descendant > 0:
                        _wait_stopped(descendant)


def _attempt_budget_and_replan() -> None:
    original = sailassist.process

    def failure(argv: list[str], cwd: Path, logs: Path, timeout: float) -> dict[str, Any]:
        return original([sys.executable, "-c", "raise SystemExit(7)"], cwd, logs, timeout)

    with _session(limit=4) as (root, directory, logs), patch.object(sailassist, "process", side_effect=failure):
        for index in range(3):
            result, code = sailassist.typecheck(root, directory, logs, f"candidate {index}", 10)
            ensure(code == 7 and len(result["checkpoint"]["attempts"]) == index + 1,
                   "failed invocations must consume attempts and preserve actual status")
        ensure("replan" in str(result["reason"]), "three failures need a material replan")
        try:
            sailassist.typecheck(root, directory, logs, "fourth without replan", 10)
        except ValueError as exc:
            ensure("replan" in str(exc), "a fourth identical approach must refuse")
        else:
            raise AssertionError("missing replan was accepted")
        sailassist.transition(root, directory, "replan", "inspect the declaration instead of changing callers")
        result, _ = sailassist.typecheck(root, directory, logs, "different approach", 10)
        sailassist.validate(result, "status")
        ensure(result["reason"] == "attempt budget exhausted", "replanning must not reset the finite budget")


def _clock_pause_and_exhaustion() -> None:
    with patch.object(sailassist.time, "time", return_value=100.0), _session(seconds=10) as (root, directory, _):
        with patch.object(sailassist.time, "time", return_value=104.0):
            paused = sailassist.transition(root, directory, "pause", "waiting for a review")
        with patch.object(sailassist.time, "time", return_value=1000.0):
            ensure(sailassist.active_seconds(paused) == 4, "paused wall time must not consume active budget")
            ready = sailassist.transition(root, directory, "resume", "review complete")
        with patch.object(sailassist.time, "time", return_value=1007.0):
            ensure(sailassist.refusal(ready) == "active-time budget exhausted", "active edit time must count")
        with patch.object(sailassist.time, "time", return_value=999.0):
            try:
                sailassist.active_seconds(ready)
            except ValueError:
                pass
            else:
                raise AssertionError("a backward clock must not refund budget")


def _frozen_and_changed_inputs() -> None:
    original = sailassist.process

    def drifting(argv: list[str], cwd: Path, logs: Path, timeout: float) -> dict[str, Any]:
        result = original([sys.executable, "-c", "pass"], cwd, logs, timeout)
        (cwd / "model/model/a.sail").write_bytes(b"function example() = 1\n")
        return result

    with _session() as (root, directory, logs):
        with patch.object(sailassist, "process", side_effect=drifting):
            result, code = sailassist.typecheck(root, directory, logs, "racing edit", 10)
        ensure(code == 1 and result["checkpoint"]["attempts"][-1]["outcome"] == "inputs_changed",
               "exit zero cannot accept a changing input set")
        (root / "docs/hardware/isa-profile.md").write_bytes(b"weakened\n")
        with patch.object(sailassist, "process") as launch:
            try:
                sailassist.typecheck(root, directory, logs, "widened profile", 10)
            except ValueError as exc:
                ensure("frozen" in str(exc), "changed constraints need explicit re-review")
            else:
                raise AssertionError("changed frozen inputs were accepted")
            launch.assert_not_called()


def _interrupted_reservation() -> None:
    with _session() as (root, directory, logs):
        with patch.object(sailassist, "process", side_effect=OSError("simulated parent loss")), suppress(OSError):
            sailassist.typecheck(root, directory, logs, "interrupted candidate", 10)
        journal = sailassist.load(directory)
        ensure(journal["state"] == "running" and len(journal["attempts"]) == 1,
               "a hard interruption must leave the reserved attempt visible")
        recovered = sailassist.transition(root, directory, "recover", "logs inspected; start a separately reviewed session")
        ensure(recovered["state"] == "closed" and recovered["attempts"][0]["outcome"] == "interrupted" and
               recovered["active_seconds"] == recovered["active_seconds_limit"],
               "unobserved duration must not silently refund the interrupted budget")


def _schema_and_path_refusals() -> None:
    with _session() as (root, directory, _):
        for name in ("../outside", "UPPER", "", "x/y", "a" * 65):
            try:
                sailassist.session_dir(root, name)
            except ValueError:
                pass
            else:
                raise AssertionError(f"unsafe session name accepted: {name}")
        checkpoint = directory / "checkpoint.json"
        good = checkpoint.read_bytes()
        checkpoint.write_bytes(b'{"version":1,"version":1}')
        try:
            sailassist.load(directory)
        except ValueError as exc:
            ensure("duplicate" in str(exc), "duplicate JSON keys must be rejected")
        checkpoint.write_bytes(b'{"active_seconds":1e999}')
        try:
            sailassist.read_json(checkpoint)
        except ValueError as exc:
            ensure("finite" in str(exc), "overflowing JSON floats must refuse before schema validation")
        else:
            raise AssertionError("infinite active time was accepted")
        checkpoint.write_bytes(good)
        journal = sailassist.load(directory)
        journal["state"] = "paused"
        sailassist.save(directory, journal)
        try:
            sailassist.load(directory)
        except ValueError as exc:
            ensure("state" in str(exc), "inconsistent checkpoint state must refuse")
        else:
            raise AssertionError("inconsistent state was accepted")


def _wsl_stdout_is_protocol_only() -> None:
    spec = spec_from_file_location("vos_sail_dispatch_test", TOOLS / "run.py")
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load the dispatcher")
    runner = module_from_spec(spec)
    spec.loader.exec_module(runner)
    out, err = io.StringIO(), io.StringIO()

    def child(argv: list[str], **kwargs: object) -> SimpleNamespace:
        print('{"native":"result"}')
        return SimpleNamespace(returncode=7)

    with (patch.object(runner.subprocess, "run", side_effect=child), redirect_stdout(out), redirect_stderr(err)):
        code = runner._in_guest(TOOLS.parent, BY_NAME["sail-assist"], ["status", "sample", "--json"])
    ensure(code == 7 and json.loads(out.getvalue()) == {"native": "result"} and "WSL" in err.getvalue(),
           "Windows dispatch must preserve native status and reserve stdout for the result")


def _exclusive_native_lock() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-sail-lock-") as temporary:
        directory = Path(temporary) / "session"
        with env.hold_lock(directory, "session"):
            try:
                env.hold_lock(directory, "session")
            except SystemExit:
                pass
            else:
                raise AssertionError("a second writer acquired the same checkpoint lock")


def _preparation_budget_and_foreign_model() -> None:
    with _session(seconds=10) as (root, directory, logs):
        journal = sailassist.load(directory)
        started = journal["active_since"]
        def slow_metadata(scratch: Path) -> dict[str, Any]:
            clock.return_value = started + 11
            return {"binaries": {}, "library_root": None, "libraries": {}}
        with (patch.object(sailassist.time, "time", return_value=started) as clock,
              patch.object(sailassist, "toolchain", side_effect=slow_metadata),
              patch.object(sailassist, "process") as launch):
            try:
                sailassist.typecheck(root, directory, logs, "preparation consumes remaining budget")
            except ValueError as exc:
                ensure("budget" in str(exc), "metadata preparation counts toward active time")
            else:
                raise AssertionError("expired preparation launched a compiler")
            launch.assert_not_called()
        ensure(not sailassist.load(directory)["attempts"], "refused preparation must not reserve an attempt")
    fake = SimpleNamespace(root=TOOLS.parent, model=TOOLS.parent / "outside-model")
    with (patch.object(cli.env, "load", return_value=fake),
          patch.object(cli.env, "hold_lock") as lock, redirect_stderr(io.StringIO()) as err):
        code = cli.main(["status", "sample", "--json"])
    ensure(code == 1 and "VOS_ROOT/VOS_MODEL" in err.getvalue(), "a foreign model must not receive this checkout's identity")
    lock.assert_not_called()


def cases() -> list[Case]:
    return [Case("raw-process-status-and-bytes", _raw_process_bytes),
            Case("timeout-stops-descendants", _timeout_process_tree),
            Case("resistant-descendant-after-parent-exit", _resistant_descendant, lane="guest"),
            Case("bounded-inline-diagnostics", _bounded_inline_output),
            Case("attempt-budget-and-replan", _attempt_budget_and_replan),
            Case("active-clock-and-pause", _clock_pause_and_exhaustion),
            Case("frozen-and-changing-inputs", _frozen_and_changed_inputs),
            Case("interrupted-reservation", _interrupted_reservation),
            Case("schema-and-path-refusals", _schema_and_path_refusals),
            Case("windows-dispatch-json", _wsl_stdout_is_protocol_only),
            Case("preparation-budget-and-model-identity", _preparation_budget_and_foreign_model),
            Case("exclusive-native-lock", _exclusive_native_lock, lane="guest")]
