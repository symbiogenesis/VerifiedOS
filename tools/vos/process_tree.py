# SPDX-License-Identifier: Apache-2.0
"""Bounded host commands with owned descendants and complete captured diagnostics.

Windows assigns a suspended leader to a private Job before resuming its initial
thread; descendants inherit that Job even when the leader exits first. Linux
commands export a unique invocation lineage before launch, so authored helpers
remain owned when they start new sessions; native session/group membership also
reaches same-session descendants that do not retain the environment marker.
This is lifecycle ownership for authored tools, not a sandbox for hostile code.
"""

import ctypes
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypedDict, cast

_CLEANUP_SECONDS = 5
_CREATE_SUSPENDED = 0x00000004
_KILL_ON_JOB_CLOSE = 0x00002000
_EXTENDED_LIMIT_INFORMATION = 9
_SNAP_THREADS = 0x00000004
_THREAD_SUSPEND_RESUME = 0x0002
_THREAD_QUERY_LIMITED_INFORMATION = 0x0800
_INVALID_HANDLE = ctypes.c_void_p(-1).value
_CONTEXT = "_VOS_PROCESS_TREE_CONTEXT"


class _Context(TypedDict):
    lineage: list[str]


class _Accounting(ctypes.Structure):
    _fields_ = [("user_time", ctypes.c_int64), ("kernel_time", ctypes.c_int64),
                ("period_user_time", ctypes.c_int64), ("period_kernel_time", ctypes.c_int64),
                ("page_faults", ctypes.c_uint32), ("total", ctypes.c_uint32),
                ("active", ctypes.c_uint32), ("terminated", ctypes.c_uint32)]


class _BasicLimits(ctypes.Structure):
    _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                ("flags", ctypes.c_uint32), ("minimum_working_set", ctypes.c_size_t),
                ("maximum_working_set", ctypes.c_size_t), ("active_processes", ctypes.c_uint32),
                ("affinity", ctypes.c_size_t), ("priority", ctypes.c_uint32),
                ("scheduling", ctypes.c_uint32)]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [("basic", _BasicLimits), ("io_counters", ctypes.c_uint64 * 6),
                ("process_memory", ctypes.c_size_t), ("job_memory", ctypes.c_size_t),
                ("peak_process_memory", ctypes.c_size_t), ("peak_job_memory", ctypes.c_size_t)]


class _ThreadEntry(ctypes.Structure):
    _fields_ = [("size", ctypes.c_uint32), ("usage", ctypes.c_uint32),
                ("thread", ctypes.c_uint32), ("process", ctypes.c_uint32),
                ("priority", ctypes.c_int32), ("priority_delta", ctypes.c_int32),
                ("flags", ctypes.c_uint32)]


class _WindowsPopen(Protocol):
    _handle: int


class _WindowsJob:
    """A private kill-on-close Job owns the command before its code can execute."""

    library: ctypes.CDLL

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise OSError("Windows process ownership is unavailable on this platform")
        self.library = ctypes.WinDLL("kernel32", use_last_error=True)
        handle, uint = ctypes.c_void_p, ctypes.c_uint32
        self._bind("CreateJobObjectW", handle, handle, ctypes.c_wchar_p)
        self._bind("SetInformationJobObject", ctypes.c_int, handle, uint, handle, uint)
        self._bind("AssignProcessToJobObject", ctypes.c_int, handle, handle)
        self._bind("TerminateJobObject", ctypes.c_int, handle, uint)
        self._bind("QueryInformationJobObject", ctypes.c_int, handle, uint, handle, uint, handle)
        self._bind("CloseHandle", ctypes.c_int, handle)
        self._bind("CreateToolhelp32Snapshot", handle, uint, uint)
        self._bind("Thread32First", ctypes.c_int, handle, ctypes.POINTER(_ThreadEntry))
        self._bind("Thread32Next", ctypes.c_int, handle, ctypes.POINTER(_ThreadEntry))
        self._bind("OpenThread", handle, uint, ctypes.c_int, uint)
        self._bind("GetProcessIdOfThread", uint, handle)
        self._bind("ResumeThread", uint, handle)
        self._bind("OpenProcess", handle, uint, ctypes.c_int, uint)
        self._bind("IsProcessInJob", ctypes.c_int, handle, handle, ctypes.POINTER(ctypes.c_int))
        self._bind("WaitForSingleObject", uint, handle, uint)
        self.handle: int | None = self._call("CreateJobObjectW", None, None)
        if self.handle is None or self.handle == 0:
            self._error("create owned process Job")
        limits = _ExtendedLimits()
        limits.basic.flags = _KILL_ON_JOB_CLOSE
        if not self._call("SetInformationJobObject", self.handle, _EXTENDED_LIMIT_INFORMATION,
                          ctypes.byref(limits), ctypes.sizeof(limits)):
            error = ctypes.get_last_error()
            self.close()
            raise OSError(error, "configure owned process Job")

    def _bind(self, name: str, result: Any, *arguments: Any) -> None:  # noqa: ANN401 (Windows C ABI)
        function = getattr(self.library, name)
        function.restype, function.argtypes = result, list(arguments)

    def _call(self, name: str, *arguments: Any) -> Any:  # noqa: ANN401 (Windows C ABI)
        return getattr(self.library, name)(*arguments)

    @staticmethod
    def _error(operation: str) -> None:
        if sys.platform == "win32":
            raise OSError(ctypes.get_last_error(), operation)
        raise OSError(operation)

    @staticmethod
    def _last_error() -> int:
        if sys.platform != "win32":
            raise OSError("Windows process ownership is unavailable on this platform")
        return ctypes.get_last_error()

    def start(self, process: subprocess.Popen[str]) -> None:
        """Assign the suspended process, then resume its single initial thread.

        [Job inheritance](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)
        prevents the venv launcher's real interpreter from escaping ownership.
        """
        if sys.platform != "win32":
            raise OSError("Windows process ownership is unavailable on this platform")
        if not self._call("AssignProcessToJobObject", self.handle,
                          int(cast("_WindowsPopen", process)._handle)):
            self._error("assign suspended command to its owned process Job")
        snapshot = self._call("CreateToolhelp32Snapshot", _SNAP_THREADS, 0)
        if snapshot in (None, _INVALID_HANDLE):
            self._error("enumerate the owned command's suspended thread")
        try:
            entry = _ThreadEntry()
            entry.size = ctypes.sizeof(entry)
            found: list[int] = []
            present = self._call("Thread32First", snapshot, ctypes.byref(entry))
            while present:
                if entry.process == process.pid:
                    found.append(entry.thread)
                present = self._call("Thread32Next", snapshot, ctypes.byref(entry))
            if len(found) != 1:
                raise OSError("suspended command does not have exactly one initial thread")
            thread = self._call("OpenThread",
                                _THREAD_SUSPEND_RESUME | _THREAD_QUERY_LIMITED_INFORMATION,
                                False, found[0])
            if not thread:
                self._error("open the owned command's suspended thread")
            try:
                if self._call("GetProcessIdOfThread", thread) != process.pid:
                    raise OSError("suspended thread no longer belongs to the owned command")
                if self._call("ResumeThread", thread) == 0xFFFFFFFF:
                    self._error("resume the owned command")
            finally:
                self._call("CloseHandle", thread)
        finally:
            self._call("CloseHandle", snapshot)

    def _accounting(self) -> _Accounting:
        accounting = _Accounting()
        if not self._call("QueryInformationJobObject", self.handle, 1,
                          ctypes.byref(accounting), ctypes.sizeof(accounting), None):
            self._error("query the owned process Job's remaining processes")
        return accounting

    def _process_handles(self) -> list[int]:
        capacity = max(1, self._accounting().active) + 16
        # Two DWORD counts precede the variable-length ULONG_PTR process list.
        deadline = time.monotonic() + _CLEANUP_SECONDS
        while True:
            listing = ctypes.create_string_buffer(8 + capacity * ctypes.sizeof(ctypes.c_size_t))
            if self._call("QueryInformationJobObject", self.handle, 3,
                          listing, ctypes.sizeof(listing), None):
                break
            if self._last_error() != 234 or time.monotonic() >= deadline:
                self._error("enumerate owned Windows descendants before termination")
            capacity *= 2
        count = ctypes.c_uint32.from_buffer(listing, 4).value
        handles: list[int] = []
        try:
            for index in range(count):
                pid = ctypes.c_size_t.from_buffer(listing, 8 + index * ctypes.sizeof(ctypes.c_size_t)).value
                handle = self._call("OpenProcess", 0x00101000, False, pid)
                if not handle:
                    if self._last_error() != 87:
                        self._error("open an owned Windows process handle")
                    continue
                member = ctypes.c_int()
                if not self._call("IsProcessInJob", handle, self.handle, ctypes.byref(member)):
                    self._call("CloseHandle", handle)
                    self._error("verify an owned Windows process handle")
                if member.value:
                    handles.append(handle)
                else:
                    self._call("CloseHandle", handle)
        except BaseException:
            for handle in handles:
                self._call("CloseHandle", handle)
            raise
        return handles

    def stop(self) -> None:
        if self.handle is None:
            return
        handles = self._process_handles()
        try:
            if not self._call("TerminateJobObject", self.handle, 1):
                self._error("terminate the owned process Job")
            deadline = time.monotonic() + _CLEANUP_SECONDS
            while (self._accounting().active != 0
                   or any(self._pending(handle) for handle in handles)):
                if time.monotonic() >= deadline:
                    raise OSError("owned Windows descendants did not terminate within the cleanup bound")
                time.sleep(0.01)
        finally:
            for handle in handles:
                self._call("CloseHandle", handle)

    def _pending(self, handle: int) -> bool:
        result = self._call("WaitForSingleObject", handle, 0)
        if result not in (0, 258):
            self._error("wait for an owned Windows process to terminate")
        return bool(result == 258)

    def close(self) -> None:
        if self.handle is not None:
            self._call("CloseHandle", self.handle)
            self.handle = None


def _context(raw: str | bytes | None) -> _Context | None:
    try:
        value = json.loads(raw or "null")
    except (ValueError, UnicodeError):
        return None
    if (not isinstance(value, dict) or set(value) != {"lineage"}
            or not isinstance(value["lineage"], list) or not value["lineage"]
            or any(not isinstance(part, str) or len(part) != 32
                   or any(char not in "0123456789abcdef" for char in part)
                   for part in value["lineage"])):
        return None
    return cast("_Context", value)


@dataclass(frozen=True)
class _LinuxProcess:
    pid: int
    group: int
    session: int
    start: int


def _linux_process(path: Path) -> _LinuxProcess | None:
    try:
        text = (path / "stat").read_text(encoding="utf-8")
    except (FileNotFoundError, ProcessLookupError):
        return None
    fields = text.rpartition(")")[2].split()
    if fields[0] in {"Z", "X"}:
        return None
    return _LinuxProcess(int(path.name), int(fields[2]), int(fields[3]), int(fields[19]))


class _LinuxOwner:
    """Each invocation owns one unique lineage prefix, including detached helpers."""

    uid: int

    def __init__(self) -> None:
        if sys.platform != "linux":
            raise OSError("host process ownership supports Linux and Windows")
        inherited = _context(os.environ.get(_CONTEXT))
        ancestors = inherited["lineage"] if inherited is not None else []
        self.context: _Context = {"lineage": [*ancestors, uuid.uuid4().hex]}
        self.whole_session = inherited is None
        self.session = os.getsid(0)
        self.uid = os.getuid()
        self.pid = 0

    def bind(self, process: subprocess.Popen[str]) -> None:
        self.pid = process.pid
        if self.whole_session:
            self.session = process.pid

    def members(self) -> list[_LinuxProcess]:
        if self.pid == 0:
            return []
        result: list[_LinuxProcess] = []
        for path in Path("/proc").iterdir():
            if not path.name.isdecimal():
                continue
            try:
                if path.stat().st_uid != self.uid:
                    continue
            except (FileNotFoundError, ProcessLookupError):
                continue
            member = _linux_process(path)
            if member is None:
                continue
            if member.session == self.session and (self.whole_session or member.group == self.pid):
                result.append(member)
                continue
            try:
                environment = (path / "environ").read_bytes().split(b"\0")
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                continue
            prefix = (_CONTEXT + "=").encode()
            raw = next((item[len(prefix):] for item in environment if item.startswith(prefix)), None)
            context = _context(raw)
            if (context is not None and context["lineage"][:len(self.context["lineage"])]
                    == self.context["lineage"]):
                result.append(member)
        return result

    def stop(self) -> None:
        if sys.platform != "linux":
            raise OSError("Linux process ownership is unavailable on this platform")
        deadline = time.monotonic() + _CLEANUP_SECONDS
        while members := self.members():
            for member in members:
                try:
                    descriptor = os.pidfd_open(member.pid)
                except ProcessLookupError:
                    continue
                try:
                    # Recheck identity after opening the stable process descriptor.
                    # No reused PID or a sibling command can acquire this signal.
                    if _linux_process(Path("/proc") / str(member.pid)) == member:
                        with suppress(ProcessLookupError):
                            signal.pidfd_send_signal(descriptor, signal.SIGKILL)
                finally:
                    os.close(descriptor)
            if time.monotonic() >= deadline:
                raise OSError("owned Linux descendants did not terminate within the cleanup bound")
            time.sleep(0.01)

    def close(self) -> None:
        pass


def _cleanup(process: subprocess.Popen[str], owner: _WindowsJob | _LinuxOwner) -> BaseException | None:
    errors: list[BaseException] = []
    try:
        owner.stop()
    except BaseException as error:
        errors.append(error)
    try:
        # Job assignment or initial-thread setup may fail before ownership starts.
        if process.poll() is None:
            process.kill()
    except BaseException as error:
        errors.append(error)
    try:
        process.wait(timeout=_CLEANUP_SECONDS)
    except BaseException as error:
        errors.append(error)
    try:
        owner.close()
    except BaseException as error:
        errors.append(error)
    return errors[0] if errors else None


def _text(blob: bytes) -> str:
    return blob.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")


def run(argv: list[str], *, cwd: Path, env: Mapping[str, str],
        timeout: float) -> subprocess.CompletedProcess[str]:
    """Capture a command and await its owned descendants on every exit path.

    Temporary-file capture cannot wait on descendant pipe handles. A timeout
    retains its original deadline and all captured bytes; cleanup failures are
    chained without replacing the command's primary error. Linux ownership
    deliberately requires `/proc` and pidfds on the supported host platform.
    """
    owner = _WindowsJob() if sys.platform == "win32" else _LinuxOwner()
    environment = dict(env)
    if isinstance(owner, _LinuxOwner):
        environment[_CONTEXT] = json.dumps(owner.context)
    try:
        with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
            process = subprocess.Popen(
                argv, cwd=cwd, env=environment, stdout=stdout_file, stderr=stderr_file,
                encoding="utf-8", errors="replace",
                start_new_session=isinstance(owner, _LinuxOwner) and owner.whole_session,
                process_group=0 if isinstance(owner, _LinuxOwner) and not owner.whole_session else None,
                creationflags=_CREATE_SUSPENDED if isinstance(owner, _WindowsJob) else 0)
            primary: BaseException | None = None
            try:
                if isinstance(owner, _WindowsJob):
                    owner.start(process)
                else:
                    owner.bind(process)
                process.wait(timeout=timeout)
            except BaseException as error:
                primary = error
            cleanup = _cleanup(process, owner)
            stdout_file.seek(0)
            stderr_file.seek(0)
            stdout_blob, stderr_blob = stdout_file.read(), stderr_file.read()
            stdout, stderr = _text(stdout_blob), _text(stderr_blob)
            if isinstance(primary, subprocess.TimeoutExpired):
                primary.output, primary.stderr = stdout_blob, stderr_blob
            if primary is not None:
                if cleanup is not None:
                    raise primary from cleanup
                raise primary
            if cleanup is not None:
                raise cleanup
            return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    finally:
        owner.close()
