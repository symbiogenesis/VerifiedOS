# SPDX-License-Identifier: Apache-2.0
"""Real owned children and grandchildren cannot outlive a bounded host command."""

import ctypes
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import BinaryIO, cast
from unittest.mock import Mock, patch

from tests.harness import TOOLS, Case, ensure
from vos import process_tree


def _running(pid: int) -> bool:
    if sys.platform == "win32":
        library = ctypes.WinDLL("kernel32", use_last_error=True)
        library.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
        library.OpenProcess.restype = ctypes.c_void_p
        library.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
        library.WaitForSingleObject.restype = ctypes.c_uint32
        library.CloseHandle.argtypes = (ctypes.c_void_p,)
        library.CloseHandle.restype = ctypes.c_int
        handle = library.OpenProcess(0x00100000, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            ensure(error == 87, f"cannot inspect owned test descendant {pid}: {error}")
            return False
        try:
            state = library.WaitForSingleObject(handle, 0)
            ensure(state in (0, 258), f"cannot wait on owned test descendant {pid}: {state}")
            return bool(state == 258)
        finally:
            library.CloseHandle(handle)
    try:
        state = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    return state.rpartition(")")[2].split()[0] != "Z"


def _tree(root: Path, *, early_exit: bool, detached_output: bool = False) -> list[str]:
    grandchild = root / "grandchild.py"
    grandchild.write_text(
        "import os,sys,time\nfrom pathlib import Path\n"
        "Path('grandchild.pid').write_text(str(os.getpid()))\n"
        "print('grandchild diagnostic', flush=True)\n"
        "print('grandchild error', file=sys.stderr, flush=True)\n"
        "time.sleep(30)\n", encoding="utf-8")
    child = root / "child.py"
    child.write_text(
        "import os,subprocess,sys,time\nfrom pathlib import Path\n"
        "Path('child.pid').write_text(str(os.getpid()))\n"
        "subprocess.Popen([sys.executable, 'grandchild.py'])\n"
        "while not Path('grandchild.pid').exists(): time.sleep(0.01)\n"
        "print('child diagnostic', flush=True)\n"
        "time.sleep(30)\n", encoding="utf-8")
    leader = root / "leader.py"
    redirect = ", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL" if detached_output else ""
    leader.write_text(
        "import os,subprocess,sys,time\nfrom pathlib import Path\n"
        f"subprocess.Popen([sys.executable, 'child.py']{redirect})\n"
        "while not Path('grandchild.pid').exists(): time.sleep(0.01)\n"
        "print('leader diagnostic', flush=True)\n"
        + ("" if early_exit else "time.sleep(30)\n"), encoding="utf-8")
    return [sys.executable, str(leader)]


def _descendants_stopped(root: Path) -> None:
    for name in ("child", "grandchild"):
        pid = int((root / f"{name}.pid").read_text(encoding="utf-8"))
        ensure(not _running(pid), f"owned {name} {pid} survived command cleanup")


def _timeout_stops_tree() -> None:
    for early_exit in (False, True):
        with tempfile.TemporaryDirectory(prefix="vos-process-tree-") as temporary:
            root = Path(temporary)
            argv = _tree(root, early_exit=early_exit)
            try:
                result = process_tree.run(argv, cwd=root, env=os.environ, timeout=3)
            except subprocess.TimeoutExpired as error:
                ensure(not early_exit, "a completed leader must not wait for inherited output handles")
                ensure("leader diagnostic" in str(error.stdout)
                       and "grandchild diagnostic" in str(error.stdout)
                       and "grandchild error" in str(error.stderr),
                       f"timeout lost descendant diagnostics: {error}")
            else:
                ensure(early_exit and result.returncode == 0
                       and "leader diagnostic" in result.stdout,
                       "a live leader must time out; an exited leader retains its exit/output")
            _descendants_stopped(root)


def _normal_exit_stops_lingering_tree() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-process-exit-") as temporary:
        root = Path(temporary)
        argv = _tree(root, early_exit=True, detached_output=True)
        result = process_tree.run(argv, cwd=root, env=os.environ, timeout=10)
        ensure(result.returncode == 0 and result.stdout == "leader diagnostic\n",
               f"normal completion must preserve its own exit and output: {result}")
        _descendants_stopped(root)


def _ordinary_exit_and_launch_failure() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-process-ordinary-") as temporary:
        root = Path(temporary)
        result = process_tree.run([sys.executable, "-c",
                                   "import sys; print('stdout'); print('stderr', file=sys.stderr); sys.exit(2)"],
                                  cwd=root, env=os.environ, timeout=10)
        ensure(result.returncode == 2 and result.stdout == "stdout\n" and result.stderr == "stderr\n",
               f"ordinary nonzero exit and streams must remain exact: {result}")
        try:
            process_tree.run([str(root / "missing-executable")], cwd=root, env=os.environ, timeout=1)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError("a missing command must remain a launch failure")


def _linux_nested_scope() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-process-nested-") as temporary:
        root = Path(temporary)
        _tree(root, early_exit=False)
        worker = root / "worker.py"
        worker.write_text(
            "import os,subprocess,sys,time\nfrom pathlib import Path\n"
            f"sys.path.insert(0, {str(TOOLS)!r})\nfrom vos import process_tree\n"
            "sibling=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])\n"
            "Path('sibling.pid').write_text(str(sibling.pid))\n"
            "try:\n process_tree.run([sys.executable,'leader.py'],cwd=Path.cwd(),env=os.environ,timeout=2)\n"
            "except subprocess.TimeoutExpired:\n pass\n"
            "else:\n raise AssertionError('nested command did not time out')\n"
            "if sibling.poll() is not None: raise AssertionError('nested cleanup killed a sibling')\n"
            "print('nested timeout preserved its sibling',flush=True)\n"
            "time.sleep(30)\n", encoding="utf-8")
        try:
            process_tree.run([sys.executable, str(worker)], cwd=root, env=os.environ, timeout=4)
        except subprocess.TimeoutExpired as error:
            ensure("nested timeout preserved its sibling" in str(error.stdout),
                   f"inner cleanup must preserve sibling ownership: {error.stdout}")
        else:
            raise AssertionError("outer command did not reach its deadline")
        _descendants_stopped(root)
        sibling = int((root / "sibling.pid").read_text(encoding="utf-8"))
        ensure(not _running(sibling), "outer cancellation missed an authored nested command")


def _windows_waits_for_quiescence() -> None:
    job = process_tree._WindowsJob.__new__(process_tree._WindowsJob)
    job.handle = 123
    waits: list[str] = []

    def call(name: str, *arguments: object) -> int:
        if name == "WaitForSingleObject":
            waits.append(name)
            return 258 if len(waits) == 1 else 0
        return 1

    with (patch.object(job, "_process_handles", return_value=[456]),
          patch.object(job, "_accounting", return_value=SimpleNamespace(active=0)),
          patch.object(job, "_call", side_effect=call),
          patch.object(process_tree.time, "sleep") as pause):
        job.stop()
    ensure(len(waits) == 2 and pause.call_count == 1,
           "an empty active count must still wait for asynchronously terminating handles")


def _cleanup_preserves_primary_and_closes_capture() -> None:
    owner_type = process_tree._WindowsJob if sys.platform == "win32" else process_tree._LinuxOwner
    start = "start" if sys.platform == "win32" else "bind"
    temporary_file = tempfile.TemporaryFile
    for stage in ("start", "stop", "wait", "cancel", "timeout"):
        captures: list[BinaryIO] = []

        def capture(captures: list[BinaryIO] = captures) -> BinaryIO:
            stream = cast("BinaryIO", temporary_file())
            captures.append(stream)
            return stream

        primary = (KeyboardInterrupt("cancelled") if stage == "cancel" else
                   subprocess.TimeoutExpired("fixture", 0.25) if stage == "timeout" else
                   OSError("primary failure"))
        process = Mock()
        process.pid = 999999
        process.poll.return_value = None
        process.wait.side_effect = [primary, 0] if stage != "start" else [0]

        def spawn(*arguments: object, captures: list[BinaryIO] = captures,
                  process: Mock = process, **keywords: object) -> Mock:
            stream = keywords["stdout"]
            ensure(hasattr(stream, "write"), "capture must be an owned file")
            captures[0].write(b"retained diagnostic\n")
            return process

        with (tempfile.TemporaryDirectory(prefix="vos-process-refusal-") as temporary,
              patch.object(process_tree.tempfile, "TemporaryFile", side_effect=capture),
              patch.object(process_tree.subprocess, "Popen", side_effect=spawn),
              patch.object(owner_type, start, side_effect=primary if stage == "start" else None),
              patch.object(owner_type, "stop", side_effect=OSError("stop failure")
                           if stage in {"stop", "cancel", "timeout"} else None)):
            if stage == "wait":
                process.wait.side_effect = [primary, OSError("cleanup wait failure")]
            try:
                process_tree.run(["fixture"], cwd=Path(temporary), env=os.environ, timeout=0.25)
            except BaseException as error:
                ensure(type(error) is type(primary), f"{stage}: cleanup replaced the primary error")
                if stage in {"stop", "cancel", "timeout", "wait"}:
                    ensure(isinstance(error.__cause__, OSError), f"{stage}: cleanup error was lost")
                if isinstance(error, subprocess.TimeoutExpired):
                    ensure(error.timeout == 0.25 and "retained diagnostic" in str(error.stdout),
                           "cleanup must preserve the execution timeout and captured output")
            else:
                raise AssertionError(f"{stage}: injected failure unexpectedly passed")
        ensure(process.kill.call_count == 1 and process.wait.call_count >= 1,
               f"{stage}: direct-child fallback did not run")
        ensure(len(captures) == 2 and all(stream.closed for stream in captures),
               f"{stage}: a cleanup error leaked capture handles")


def cases() -> list[Case]:
    return [Case("timeouts-stop-owned-children-after-live-or-exited-leader", _timeout_stops_tree),
            Case("normal-exit-cleans-descendants-without-inherited-output", _normal_exit_stops_lingering_tree),
            Case("ordinary-exits-streams-and-missing-commands", _ordinary_exit_and_launch_failure),
            Case("nested-Linux-deadlines-preserve-siblings-and-obey-outer-ownership",
                 _linux_nested_scope, lane="guest"),
            Case("Windows-waits-for-delayed-descendant-quiescence", _windows_waits_for_quiescence,
                 lane="host"),
            Case("cleanup-refusals-preserve-primary-error-and-release-files",
                 _cleanup_preserves_primary_and_closes_capture)]
