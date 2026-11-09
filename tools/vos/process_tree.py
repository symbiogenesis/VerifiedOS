# SPDX-License-Identifier: Apache-2.0
"""Bounded host commands with owned descendants and complete captured diagnostics.

Windows assigns a suspended leader to a private Job before resuming its initial
thread; descendants inherit that Job even when the leader exits first. POSIX
commands start a new session and retain their process-group identity for cleanup.
This is lifecycle ownership for authored tools, not a sandbox for hostile code.
"""

import ctypes
import os
import signal
import subprocess
import sys
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol, cast

_CLEANUP_SECONDS = 5
_CREATE_SUSPENDED = 0x00000004
_KILL_ON_JOB_CLOSE = 0x00002000
_EXTENDED_LIMIT_INFORMATION = 9
_SNAP_THREADS = 0x00000004
_THREAD_SUSPEND_RESUME = 0x0002
_THREAD_QUERY_LIMITED_INFORMATION = 0x0800
_INVALID_HANDLE = ctypes.c_void_p(-1).value


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
        self._bind("CloseHandle", ctypes.c_int, handle)
        self._bind("CreateToolhelp32Snapshot", handle, uint, uint)
        self._bind("Thread32First", ctypes.c_int, handle, ctypes.POINTER(_ThreadEntry))
        self._bind("Thread32Next", ctypes.c_int, handle, ctypes.POINTER(_ThreadEntry))
        self._bind("OpenThread", handle, uint, ctypes.c_int, uint)
        self._bind("GetProcessIdOfThread", uint, handle)
        self._bind("ResumeThread", uint, handle)
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

    def stop(self) -> None:
        if self.handle is not None and not self._call("TerminateJobObject", self.handle, 1):
            self._error("terminate the owned process Job")

    def close(self) -> None:
        if self.handle is not None:
            self._call("CloseHandle", self.handle)
            self.handle = None


def run(argv: list[str], *, cwd: Path, env: Mapping[str, str],
        timeout: float) -> subprocess.CompletedProcess[str]:
    """Capture a command and clean its tree on success, timeout or interruption.

    A timeout retains stdout/stderr in `TimeoutExpired`, including bytes emitted
    by descendants before termination. Cleanup is bounded independently of the
    execution deadline; it never waits for pipe EOF from a live owned descendant.
    """
    job = _WindowsJob() if sys.platform == "win32" else None
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, encoding="utf-8", errors="replace",
                                   start_new_session=job is None,
                                   creationflags=_CREATE_SUSPENDED if job else 0)
        if job is not None:
            job.start(process)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _stop(process, job)
            stdout, stderr = process.communicate(timeout=_CLEANUP_SECONDS)
            raise subprocess.TimeoutExpired(argv, timeout, stdout, stderr) from None
        return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)
    finally:
        try:
            if process is not None:
                _stop(process, job)
                process.wait(timeout=_CLEANUP_SECONDS)
                for stream in (process.stdout, process.stderr):
                    if stream is not None:
                        stream.close()
        finally:
            if job is not None:
                job.close()


def _stop(process: subprocess.Popen[str], job: _WindowsJob | None) -> None:
    if job is not None:
        job.stop()
        # Assignment or initial-thread setup may have failed before the Job owns it.
        if process.poll() is None:
            process.kill()
    elif sys.platform != "win32":
        # The leader can already have exited while descendants still own its pipes.
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
    else:
        raise OSError("Windows command has no owned process Job")
