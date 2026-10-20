# SPDX-License-Identifier: Apache-2.0
"""Private-pipe, call-level capture and replay over generated Sail definitions.

Development commitments/authentication supply no RoT sealing or export authority.
The pipe controller never retains original words for replay or formats raw frames
in diagnostics. See contracts/development-entropy-replay.md for the exact scope.
"""

import hashlib
import hmac
import os
import re
import secrets
import selectors
import subprocess
import sys
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Never

from vos.replay_envelope import EnvelopeLimits, create, verify
from vos.replay_record import (
    Binding,
    FixtureCursor,
    FixtureRecorder,
    Interface,
    Limits,
    Point,
)

_PUBLIC = (
    "before-startup", "startup", "direct", "mmio", "arm", "accepted-pet",
    "rejected-pet", "bitten", "latched-refusal",
)
_COORDINATE = re.compile(rb"(B|E|V) ([0-9]+) ([0-9]+) ([0-9]+) ([0-9]+)(?: ([01])(?: ([0-9a-f]{16}))?)?")
_DOMAIN = b"VerifiedOS development entropy commitment\x00"


class ReplayRuntimeError(ValueError):
    """Safe controller verdict: never includes a native frame or original word."""

    def __init__(self, reason: str, *, source_unchanged: bool | None = None) -> None:
        super().__init__(reason)
        self.source_unchanged = source_unchanged


def _fail(reason: str) -> Never:
    raise ReplayRuntimeError(reason)


@dataclass(frozen=True)
class Inputs:
    binding: Binding
    origin: bytes
    input_trace: bytes | None
    events: int
    interface: str
    limits: EnvelopeLimits

    def profiles(self) -> dict[str, Interface]:
        return {self.interface: Interface("entropy", 32)}


@dataclass(frozen=True)
class Capture:
    envelope: bytes
    observations: tuple[tuple[str, bool], ...]


def commitment(key: bytes, point: Point, interface: str, value: bytes) -> bytes:
    """An opaque keyed development commitment, not a production seal."""
    if type(key) is not bytes or len(key) < 32 or type(value) is not bytes or len(value) != 8:
        _fail("development commitment parameters refuse")
    coordinates = b"".join(v.to_bytes(8, "big") for v in
                           (point.slot, point.core, point.retire, point.ordinal))
    return hmac.digest(key, _DOMAIN + coordinates + bytes.fromhex(interface) + value, "sha256")


def _point(fields: tuple[bytes | None, ...]) -> Point:
    values = tuple(int(v) for v in fields[1:5] if v is not None)
    if len(values) != 4 or any(v >= 2**64 for v in values):
        _fail("native coordinate refuses")
    return Point(*values)


class _Pipe:
    """Fixed-bound frames on private anonymous pipes, with one bounded deadline."""

    _process: subprocess.Popen[bytes]
    _out: IO[bytes]
    _in: IO[bytes]
    _select: selectors.BaseSelector
    _pending: bytearray
    _deadline: float

    def __init__(self, executable: Path, configuration: Path, work: Path, mode: str) -> None:
        if (sys.platform == "win32" or not work.is_absolute() or not work.is_dir()
                or not work.is_relative_to(Path("/root/build"))):
            _fail("native work directory must be an existing assigned build lane")
        self._process = subprocess.Popen([str(executable), mode, str(configuration)], cwd=work,
                                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                         stderr=subprocess.DEVNULL)
        if self._process.stdout is None or self._process.stdin is None:
            self.close()
            _fail("private native pipes are unavailable")
        self._out = self._process.stdout
        self._in = self._process.stdin
        os.set_blocking(self._out.fileno(), False)
        self._select = selectors.DefaultSelector()
        self._select.register(self._out, selectors.EVENT_READ)
        self._pending = bytearray()
        self._deadline = time.monotonic() + 20

    def read(self) -> bytes:
        while b"\n" not in self._pending:
            remaining = self._deadline - time.monotonic()
            if remaining <= 0 or not self._select.select(remaining):
                _fail("private native protocol timed out")
            chunk = os.read(self._out.fileno(), 256)
            if not chunk:
                _fail("private native protocol interrupted")
            self._pending.extend(chunk)
            boundary = self._pending.find(b"\n")
            if (boundary < 0 and len(self._pending) > 128) or boundary > 128:
                _fail("private native frame exceeds its bound")
        if self._pending.find(b"\n") > 128:
            _fail("private native frame exceeds its bound")
        frame, _, rest = self._pending.partition(b"\n")
        self._pending[:] = rest
        return bytes(frame)

    def answer(self, value: bytes = b"go") -> None:
        try:
            self._in.write(value + b"\n")
            self._in.flush()
        except (BrokenPipeError, OSError):
            raise ReplayRuntimeError("private native protocol interrupted") from None

    def reject(self) -> bool | None:
        try:
            self.answer(b"deny")
            frame = self.read()
        except ReplayRuntimeError:
            return None
        else:
            return frame == b"A 1" if frame in {b"A 0", b"A 1"} else None

    def done(self) -> None:
        try:
            code = self._process.wait(timeout=max(0.01, self._deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            raise ReplayRuntimeError("native completion timed out") from None
        if code:
            _fail("native execution refused")
        if self._pending or self._out.read():
            _fail("native protocol has trailing bytes")

    def close(self) -> None:
        if self._process.poll() is None:
            self._process.kill()
        self._process.wait()
        if hasattr(self, "_pending"):
            self._pending.clear()
        if hasattr(self, "_select"):
            self._select.close()
        for pipe in (self._process.stdin, self._process.stdout):
            if pipe is not None:
                pipe.close()


def _frame(pipe: _Pipe) -> tuple[str, Point, bool | None, bytes | None] | tuple[str, bool] | None:
    raw = pipe.read()
    if raw == b"Z":
        return None
    if raw.startswith(b"O "):
        parts = raw.split(b" ")
        if len(parts) != 3 or parts[1].decode("ascii", errors="replace") not in _PUBLIC or parts[2] not in {b"0", b"1"}:
            _fail("native public observation refuses")
        return (parts[1].decode("ascii"), parts[2] == b"1")
    matched = _COORDINATE.fullmatch(raw)
    if matched is None:
        _fail("native protocol frame refuses")
    fields = matched.groups()
    available: bool | None = None if fields[5] is None else bool(fields[5] == b"1")
    word = None if fields[6] is None else bytes.fromhex(fields[6].decode("ascii"))
    return (raw[:1].decode("ascii"), _point(fields), available, word)


def _public(observations: list[tuple[str, bool]], frame: tuple[str, bool]) -> None:
    if len(observations) >= len(_PUBLIC) or frame[0] != _PUBLIC[len(observations)]:
        _fail("native public observation order refuses")
    observations.append(frame)


def _complete(observations: list[tuple[str, bool]]) -> None:
    if len(observations) != len(_PUBLIC):
        _fail("native public observations are incomplete")


def _artifacts(expected: Binding, executable: Path, configuration: Path) -> None:
    """Check the development files in a trusted exclusive lane, not signed images.

    Completion rechecks detect persisting drift; they do not pin an executable
    against an adversarial concurrent writer. Absolute paths name the same files
    for hashing and for the child whose working directory is the native lane.
    """
    if not executable.is_absolute() or not configuration.is_absolute():
        _fail("native artifact paths must be absolute")
    try:
        if not executable.is_file() or not configuration.is_file():
            _fail("native artifacts are unavailable")
        with executable.open("rb") as stream:
            root = hashlib.file_digest(stream, "sha256").hexdigest()
        with configuration.open("rb") as stream:
            composition = hashlib.file_digest(stream, "sha256").hexdigest()
    except (OSError, ValueError):
        raise ReplayRuntimeError("native artifacts are unavailable") from None
    if (root, composition) != (expected.base_image_root, expected.composition):
        _fail("native artifacts differ from independently expected development binding")


class CaptureSession:
    """One capture; failures also abort direct access to the underlying recorder."""

    def __init__(self, inputs: Inputs, *, authentication_key: bytes, seal_key: bytes,
                 seal: Callable[[Point, bytes], bytes | None] | None = None,
                 mode: str = "development") -> None:
        if mode != "development" or inputs.input_trace is None:
            _fail("production, declassification or absent-input request refuses")
        if (type(seal_key) is not bytes or len(seal_key) < 32
                or seal_key == authentication_key):
            _fail("independent development commitment key is required")
        if (type(authentication_key) is not bytes or len(authentication_key) < 32
                or type(inputs.input_trace) is not bytes
                or hashlib.sha256(inputs.input_trace).hexdigest() != inputs.binding.input_trace
                or type(inputs.origin) is not bytes or not inputs.origin
                or len(inputs.origin) > inputs.limits.max_origin_bytes
                or len(inputs.input_trace) > inputs.limits.max_input_trace_bytes
                or type(inputs.events) is not int or not 0 <= inputs.events <= inputs.limits.max_events):
            _fail("independent capture parameters refuse")
        self.inputs = inputs
        self._input_trace = inputs.input_trace
        self._key = authentication_key
        self._seal = seal or (lambda point, value: commitment(seal_key, point, inputs.interface, value))
        self.recorder = FixtureRecorder(inputs.binding,
                                       limits=Limits(inputs.limits.max_body_bytes, inputs.limits.max_events),
                                       interfaces=inputs.profiles(), validators={})
        self._closed = False

    def run(self, executable: Path, configuration: Path, work: Path) -> Capture:
        if self._closed:
            _fail("capture is already closed")
        self._closed = True
        pipe: _Pipe | None = None
        public: list[tuple[str, bool]] = []
        try:
            _artifacts(self.inputs.binding, executable, configuration)
            pipe = _Pipe(executable, configuration, work, "capture")
            while (frame := _frame(pipe)) is not None:
                if len(frame) == 2:
                    _public(public, frame)
                    continue
                kind, point, available, word = frame
                if kind == "E" and available is False and word is None:
                    pipe.answer()
                    continue
                if kind != "B" or available is not None or word is not None:
                    _fail("capture request ordering refuses")

                def produce(admitted: Point = point) -> bytes | None:
                    pipe.answer()  # FixtureRecorder has already reserved capacity.
                    outcome = _frame(pipe)
                    if outcome is None or len(outcome) != 4:
                        _fail("capture outcome interrupted")
                    event, at, success, value = outcome
                    if event != "E" or at != admitted or success is None:
                        _fail("capture outcome differs from admitted request")
                    if not success:
                        if value is not None:
                            _fail("refused root disclosed a value")
                        pipe.answer()
                        return None
                    if value is None:
                        _fail("successful root omitted its private word")
                    sealed = self._seal(admitted, value)
                    if type(sealed) is not bytes or len(sealed) != 32:
                        _fail("development commitment declined")
                    pipe.answer()
                    return sealed

                try:
                    self.recorder.record(point=point, interface=self.inputs.interface, produce=produce)
                except BaseException:
                    unchanged = pipe.reject()
                    raise ReplayRuntimeError("capture admission or commitment refused",
                                         source_unchanged=unchanged) from None
            pipe.done()
            _complete(public)
            _artifacts(self.inputs.binding, executable, configuration)
            body = self.recorder.finish(expected=self.inputs.binding, expected_events=self.inputs.events)
            envelope = create(key=self._key, origin=self.inputs.origin, input_trace=self._input_trace,
                              body=body, expected=self.inputs.binding, expected_origin=self.inputs.origin,
                              expected_events=self.inputs.events, limits=self.inputs.limits,
                              interfaces=self.inputs.profiles())
            return Capture(envelope, tuple(public))
        except BaseException:
            self.recorder.abort()
            raise
        finally:
            if pipe is not None:
                pipe.close()


def replay(capture: Capture, inputs: Inputs, *, key: bytes, executable: Path,
           configuration: Path, work: Path, entropy: Callable[[], bytes] | None = None,
           request_interfaces: Mapping[int, str] | None = None,
           mode: str = "development") -> tuple[tuple[str, bool], ...]:
    """Verify before starting; release each own-entropy word only after demand matching."""
    if mode != "development" or inputs.input_trace is None:
        _fail("production, declassification or absent-input request refuses")
    authenticated = verify(capture.envelope, key=key, expected=inputs.binding,
                           expected_origin=inputs.origin, expected_events=inputs.events,
                           limits=inputs.limits, interfaces=inputs.profiles())
    if authenticated.input_trace != inputs.input_trace:
        _fail("independent input bytes differ")
    cursor = FixtureCursor(authenticated.record)
    fresh = entropy or (lambda: secrets.token_bytes(8))
    pipe: _Pipe | None = None
    public: list[tuple[str, bool]] = []
    pending: Point | None = None
    successful: Point | None = None
    try:
        _artifacts(inputs.binding, executable, configuration)
        pipe = _Pipe(executable, configuration, work, "replay")
        while (frame := _frame(pipe)) is not None:
            if len(frame) == 2:
                _public(public, frame)
                continue
            kind, point, available, word = frame
            if word is not None:
                _fail("replay observer disclosed an original word")
            if kind == "B" and pending is None and successful is None and available is None:
                pending = point
                pipe.answer()
            elif kind == "E" and available is not None and successful is None:
                if available and pending != point:
                    _fail("unrecorded root request refuses")
                if not available and pending is not None and pending != point:
                    _fail("refused root request differs")
                successful = point if available else None
                pending = None
                pipe.answer()
            elif kind == "V" and point == successful and available is None:
                interface = inputs.interface if request_interfaces is None else request_interfaces.get(point.slot, inputs.interface)
                cursor.consume(point=point, source="entropy", interface=interface)
                try:
                    value = fresh()
                except BaseException:
                    raise ReplayRuntimeError("substitute entropy callback refused") from None
                if type(value) is not bytes or len(value) != 8:
                    _fail("substitute entropy must be one fresh 64-bit word")
                pipe.answer(value.hex().encode("ascii"))
                successful = None
            else:
                _fail("replay request ordering refuses")
        if pending is not None or successful is not None:
            _fail("unfinished root request refuses")
        pipe.done()
        _complete(public)
        _artifacts(inputs.binding, executable, configuration)
        cursor.finish()
        if tuple(public) != capture.observations:
            _fail("finite public observations differ; draw-dependent reproduction unsupported")
        return tuple(public)
    except BaseException:
        cursor.abort()
        raise
    finally:
        if pipe is not None:
            pipe.close()
