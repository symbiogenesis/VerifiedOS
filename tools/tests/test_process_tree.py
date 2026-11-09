# SPDX-License-Identifier: Apache-2.0
"""Real owned children and grandchildren cannot outlive a bounded host command."""

import ctypes
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from tests.harness import Case, ensure
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
                process_tree.run(argv, cwd=root, env=os.environ, timeout=3)
            except subprocess.TimeoutExpired as error:
                ensure("leader diagnostic" in str(error.stdout)
                       and "grandchild diagnostic" in str(error.stdout)
                       and "grandchild error" in str(error.stderr),
                       f"timeout lost descendant diagnostics: {error}")
            else:
                raise AssertionError("live descendants holding output must reach the deadline")
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


def cases() -> list[Case]:
    return [Case("timeouts-stop-owned-children-after-live-or-exited-leader", _timeout_stops_tree),
            Case("normal-exit-cleans-descendants-without-inherited-output", _normal_exit_stops_lingering_tree),
            Case("ordinary-exits-streams-and-missing-commands", _ordinary_exit_and_launch_failure)]
