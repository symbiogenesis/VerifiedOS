# SPDX-License-Identifier: Apache-2.0
"""Development controller controls, including actual generated Sail executions."""

import hashlib
import json
import secrets
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import override
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import env, receipts, replay_runtime
from vos.replay_envelope import EnvelopeError, EnvelopeLimits, create, verify
from vos.replay_record import Binding, FixtureCursor, Point, Record, RecordError
from vos.replay_runtime import (
    Capture,
    CaptureSession,
    Inputs,
    ReplayRuntimeError,
    commitment,
    replay,
)


def _inputs() -> Inputs:
    return Inputs(Binding("ab", "a" * 64, hashlib.sha256(b"").hexdigest()),
                  b"cold development origin", b"", 4, "e" * 64,
                  EnvelopeLimits(4096, 128, 128, 3000, 8))


def _parameters() -> None:
    inputs = _inputs()
    point = Point(1, 15, 0, 0)
    key = b"a" * 32
    word = b"w" * 8
    opaque = commitment(key, point, inputs.interface, word)
    ensure(len(opaque) == 32 and opaque != word, "only an opaque keyed commitment is returned")
    ensure(opaque != commitment(b"b" * 32, point, inputs.interface, word), "wrong sealing key differs")
    ensure(opaque != commitment(key, replace(point, slot=2), inputs.interface, word), "point is committed")
    for mode in ("production", "declassification", "actual-draw"):
        try:
            CaptureSession(inputs, authentication_key=b"b" * 32, seal_key=key, mode=mode)
        except ReplayRuntimeError:
            pass
        else:
            raise AssertionError("a production/declassification mode was admitted")
    for changed in (replace(inputs, input_trace=None),
                    replace(inputs, input_trace=b"missing bytes"), replace(inputs, origin=b"")):
        try:
            CaptureSession(changed, authentication_key=b"b" * 32, seal_key=key)
        except ReplayRuntimeError:
            pass
        else:
            raise AssertionError("independent missing/mismatched input was admitted")


def _buffered_bound() -> None:
    pipe = object.__new__(replay_runtime._Pipe)
    pipe._pending = bytearray(b"Z\n" + b"x" * 129 + b"\n")
    ensure(pipe.read() == b"Z", "a short first buffered frame is valid")
    try:
        pipe.read()
    except ReplayRuntimeError as error:
        ensure(str(error) == "private native frame exceeds its bound", "oversized buffered frame has a safe verdict")
    else:
        raise AssertionError("an oversized second buffered frame was admitted")


def _protocol_failure(fault: str, executable: Path, configuration: Path, work: Path,
                      captured: Capture, inputs: Inputs, auth_key: bytes, seal_key: bytes) -> None:
    """Interrupt the real model at its first preflight, or corrupt that frame."""
    opened: list[replay_runtime._Pipe] = []
    cursors: list[FixtureCursor] = []

    class FaultPipe(replay_runtime._Pipe):
        def __init__(self, executable: Path, configuration: Path, work: Path, mode: str) -> None:
            super().__init__(executable, configuration, work, mode)
            self.faulted = False
            opened.append(self)

        @override
        def read(self) -> bytes:
            frame = super().read()
            if not self.faulted and frame.startswith(b"B "):
                self.faulted = True
                if fault == "EOF":
                    self._process.kill()
                    self._process.wait()
                    return super().read()
                return b"unexpected 0123456789abcdef"
            return frame

    class TrackedCursor(FixtureCursor):
        def __init__(self, record: Record) -> None:
            super().__init__(record)
            cursors.append(self)

    session = CaptureSession(inputs, authentication_key=auth_key, seal_key=seal_key)
    with patch.object(replay_runtime, "_Pipe", FaultPipe), patch.object(replay_runtime, "FixtureCursor", TrackedCursor):
        for action in (lambda: session.run(executable, configuration, work),
                       lambda: replay(captured, inputs, key=auth_key, executable=executable,
                                      configuration=configuration, work=work)):
            try:
                action()
            except ReplayRuntimeError as error:
                ensure("0123456789abcdef" not in str(error), "protocol diagnostics omit transient frame content")
            else:
                raise AssertionError("native protocol failure was accepted")
    try:
        session.recorder.finish(expected=inputs.binding, expected_events=0)
    except RecordError:
        pass
    else:
        raise AssertionError("interrupted native capture finalized directly")
    ensure(len(cursors) == 1, "replay created one authenticated cursor")
    try:
        cursors[0].finish()
    except RecordError:
        pass
    else:
        raise AssertionError("interrupted native replay finalized directly")
    ensure(len(opened) == 2 and all(pipe._process.poll() is not None
           and pipe._in.closed and pipe._out.closed and not pipe._pending for pipe in opened),
           "both interrupted children terminated and their private pipes closed")


def _artifact_preflight(executable: Path, configuration: Path, work: Path,
                        captured: Capture, inputs: Inputs, auth_key: bytes, seal_key: bytes) -> None:
    cursors: list[FixtureCursor] = []
    calls = 0

    class TrackedCursor(FixtureCursor):
        def __init__(self, record: Record) -> None:
            super().__init__(record)
            cursors.append(self)

    def fresh() -> bytes:
        nonlocal calls
        calls += 1
        return secrets.token_bytes(8)

    session = CaptureSession(inputs, authentication_key=auth_key, seal_key=seal_key)
    with patch.object(replay_runtime, "_Pipe", side_effect=AssertionError("wrong native artifacts reached launch")) as launch, \
            patch.object(replay_runtime, "FixtureCursor", TrackedCursor):
        for action in (lambda: session.run(executable, configuration, work),
                       lambda: replay(captured, inputs, key=auth_key, executable=executable,
                                      configuration=configuration, work=work, entropy=fresh)):
            try:
                action()
            except ReplayRuntimeError as error:
                ensure(str(error) == "native artifacts differ from independently expected development binding",
                       "actual artifact mismatch has a fixed safe verdict")
            else:
                raise AssertionError("wrong actual native artifacts were admitted")
        ensure(launch.call_count == 0 and calls == 0, "artifact preflight refusal precedes launch and fresh callbacks")
    try:
        session.recorder.finish(expected=inputs.binding, expected_events=0)
    except RecordError:
        pass
    else:
        raise AssertionError("wrong-artifact capture finalized directly")
    ensure(len(cursors) == 1, "preflight replay created one authenticated cursor")
    try:
        cursors[0].consume(point=Point(1, 15, 0, 0), source="entropy", interface=inputs.interface)
    except RecordError:
        pass
    else:
        raise AssertionError("wrong-artifact replay cursor consumed after refusal")


def _artifact_drift(kind: str, mode: str, executable: Path, configuration: Path,
                    original: Path, work: Path, captured: Capture, inputs: Inputs,
                    auth_key: bytes, seal_key: bytes) -> None:
    pipes: list[replay_runtime._Pipe] = []
    cursors: list[FixtureCursor] = []
    calls = 0

    class TrackedPipe(replay_runtime._Pipe):
        def __init__(self, executable: Path, configuration: Path, work: Path, mode: str) -> None:
            super().__init__(executable, configuration, work, mode)
            pipes.append(self)

    class TrackedCursor(FixtureCursor):
        def __init__(self, record: Record) -> None:
            super().__init__(record)
            cursors.append(self)

    def drift() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            if kind == "executable":
                # Replace this disposable path; never write an active executable.
                replacement = executable.with_name("replacement")
                shutil.copy2(original, replacement)
                with replacement.open("ab") as stream:
                    stream.write(b"\n")
                replacement.replace(executable)
            else:
                with configuration.open("ab") as stream:
                    stream.write(b"\n")

    def seal(point: Point, value: bytes) -> bytes:
        drift()
        return commitment(seal_key, point, inputs.interface, value)

    def fresh() -> bytes:
        drift()
        return secrets.token_bytes(8)

    session = CaptureSession(inputs, authentication_key=auth_key, seal_key=seal_key, seal=seal)
    with patch.object(replay_runtime, "_Pipe", TrackedPipe), patch.object(replay_runtime, "FixtureCursor", TrackedCursor):
        try:
            if mode == "capture":
                session.run(executable, configuration, work)
            else:
                replay(captured, inputs, key=auth_key, executable=executable,
                       configuration=configuration, work=work, entropy=fresh)
        except ReplayRuntimeError as error:
            ensure(str(error) == "native artifacts differ from independently expected development binding",
                   "persisting drift has a fixed safe completion verdict")
        else:
            raise AssertionError("mid-run native artifact drift finalized successfully")
    ensure(calls == 4, "drift was detected at completion after all actual demands")
    if mode == "capture":
        try:
            session.recorder.finish(expected=inputs.binding, expected_events=4)
        except RecordError:
            pass
        else:
            raise AssertionError("drifted capture finalized directly")
    else:
        ensure(len(cursors) == 1, "drifted replay created one authenticated cursor")
        try:
            cursors[0].finish()
        except RecordError:
            pass
        else:
            raise AssertionError("drifted replay finalized directly")
    ensure(len(pipes) == 1 and all(pipe._process.poll() is not None and pipe._in.closed
           and pipe._out.closed and not pipe._pending for pipe in pipes),
           "drift refusal closed the actual child and its private pipes")


def _artifact_controls(executable: Path, configuration: Path, work: Path,
                       captured: Capture, inputs: Inputs, auth_key: bytes, seal_key: bytes) -> list[str]:
    passed: list[str] = []
    with tempfile.TemporaryDirectory(prefix="vos-replay-artifacts-") as directory:
        copies = Path(directory)
        native, config = copies / "entropy_capture", copies / "composition.json"
        for kind in ("executable", "configuration"):
            shutil.copy2(executable, native)
            shutil.copy2(configuration, config)
            changed = native if kind == "executable" else config
            with changed.open("ab") as stream:
                stream.write(b"\n")
            _artifact_preflight(native, config, work, captured, inputs, auth_key, seal_key)
            passed.append("wrong actual " + kind + " refuses capture/replay before launch or fresh callback")
            for mode in ("capture", "replay"):
                shutil.copy2(executable, native)
                shutil.copy2(configuration, config)
                _artifact_drift(kind, mode, native, config, executable, work, captured, inputs, auth_key, seal_key)
                passed.append(mode + " mid-run " + kind + " drift refuses finalization")
    return passed


def _native() -> None:
    """One finite campaign over the real generated definitions; no raw pipe logs."""
    environment = env.load()
    executable = environment.build_dir / "test/unit_tests/entropy_capture"
    configuration = environment.root / "model/config/verifiedos-rot.json"
    work = environment.lane_root / "entropy-runtime"
    work.mkdir(parents=True, exist_ok=True)
    ensure(executable.is_file(), "build this lane's entropy_capture target before the focused native case")
    auth_key, seal_key = secrets.token_bytes(32), secrets.token_bytes(32)
    inputs = replace(_inputs(), binding=Binding(
        hashlib.sha256(executable.read_bytes()).hexdigest(),
        hashlib.sha256(configuration.read_bytes()).hexdigest(),
        hashlib.sha256(b"").hexdigest()))
    passed: list[str] = []
    refused_file = subprocess.run([str(executable), "capture", str(configuration)],
                                  cwd=work, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, check=False, timeout=2)
    ensure(refused_file.returncode == 2, "capture refuses non-pipe stdout before model initialization")
    passed.append("ordinary non-pipe stdout refuses before model initialization")

    def record(request: Inputs = inputs) -> tuple[CaptureSession, Capture]:
        session = CaptureSession(request, authentication_key=auth_key, seal_key=seal_key)
        return session, session.run(executable, configuration, work)

    _, captured = record()
    ensure(dict(captured.observations) == {
        "before-startup": False, "startup": True, "direct": True, "mmio": True,
        "arm": True, "accepted-pet": True, "rejected-pet": True, "bitten": True,
        "latched-refusal": False,
    }, "actual direct/MMIO/watchdog classes agree")
    authenticated = verify(captured.envelope, key=auth_key, expected=inputs.binding,
                           expected_origin=inputs.origin, expected_events=4,
                           limits=inputs.limits, interfaces=inputs.profiles())
    ensure([event.point.slot for event in authenticated.record.events] == [1, 2, 3, 4],
           "actual internal watchdog draws are recorded exactly once; refused draws/pet add none")
    ensure(all(event.point.core == 15 and event.point.retire == 0 for event in authenticated.record.events),
           "coordinates identify the composed core and claim no retirement")
    passed.append("actual direct/MMIO/watchdog capture")

    supplied = 0
    def own_entropy() -> bytes:
        nonlocal supplied
        supplied += 1
        return secrets.token_bytes(8)

    ensure(replay(captured, inputs, key=auth_key, executable=executable,
                  configuration=configuration, work=work, entropy=own_entropy) == captured.observations,
           "fresh independent words reproduce only finite public call-level observations")
    ensure(supplied == 4, "exactly one independent substitute per matching successful demand")
    passed.append("paired own-entropy public call-level comparison")
    ensure(replay(captured, inputs, key=auth_key, executable=executable,
                  configuration=configuration, work=work, entropy=lambda: bytes(8)) == captured.observations,
           "zero-word development control preserves these classes through watchdog zero normalization")
    passed.append("zero-substitute public classes; token values excluded")
    passed.extend(_artifact_controls(executable, configuration, work, captured, inputs, auth_key, seal_key))

    def refuse(candidate: Capture = captured, request: Inputs = inputs,
               key: bytes = auth_key, *, entropy: Callable[[], bytes] | None = None,
               request_interfaces: Mapping[int, str] | None = None,
               mode: str = "development") -> None:
        cursors: list[FixtureCursor] = []
        pipes: list[replay_runtime._Pipe] = []

        class TrackedCursor(FixtureCursor):
            def __init__(self, record: Record) -> None:
                super().__init__(record)
                cursors.append(self)

        class TrackedPipe(replay_runtime._Pipe):
            def __init__(self, executable: Path, configuration: Path, work: Path, mode: str) -> None:
                super().__init__(executable, configuration, work, mode)
                pipes.append(self)

        try:
            with patch.object(replay_runtime, "FixtureCursor", TrackedCursor), patch.object(replay_runtime, "_Pipe", TrackedPipe):
                replay(candidate, request, key=key, executable=executable,
                       configuration=configuration, work=work, entropy=entropy,
                       request_interfaces=request_interfaces, mode=mode)
        except (EnvelopeError, ReplayRuntimeError, RecordError) as error:
            ensure("0123456789abcdef" not in str(error), "fresh callback diagnostics omit transient content")
            for cursor in cursors:
                try:
                    cursor.finish()
                except RecordError:
                    pass
                else:
                    raise AssertionError("refused replay cursor finalized directly")
            ensure(all(pipe._process.poll() is not None and pipe._in.closed
                   and pipe._out.closed and not pipe._pending for pipe in pipes),
                   "refused replay terminated its child and closed private pipes")
            if mode != "development":
                ensure(not pipes and not cursors, "forbidden modes refuse before native launch or model advancement")
            return
        raise AssertionError("native replay refusal control unexpectedly passed")

    refuse(key=secrets.token_bytes(32))
    passed.append("wrong key")
    refuse(replace(captured, envelope=captured.envelope[:-1] + bytes([captured.envelope[-1] ^ 1])))
    passed.append("changed tag")
    refuse(request=replace(inputs, binding=replace(inputs.binding, base_image_root="ff")))
    passed.append("wrong expected root")
    refuse(request=replace(inputs, binding=replace(inputs.binding, composition="b" * 64)))
    passed.append("wrong expected composition")
    refuse(request=replace(inputs, origin=b"wrong origin"))
    passed.append("wrong origin")
    refuse(request=replace(inputs, input_trace=None))
    passed.append("absent input")
    refuse(request=replace(inputs, input_trace=b"wrong"))
    passed.append("wrong input bytes")
    refuse(request_interfaces={3: "f" * 64})
    passed.append("wrong watchdog endpoint")
    refuse(entropy=lambda: b"short")
    passed.append("wrong substitute shape")
    def failing_entropy() -> bytes:
        raise ValueError("0123456789abcdef")

    refuse(entropy=failing_entropy)
    passed.append("substitute callback exception")
    for mode in ("production", "declassification", "actual-draw"):
        refuse(mode=mode)
        passed.append(mode + " request")

    def modified(events: list[dict[str, object]]) -> tuple[Capture, Inputs]:
        body = json.loads(authenticated.body)
        body["events"] = events
        for seq, event in enumerate(events):
            event["seq"] = seq
        changed = replace(inputs, events=len(events))
        blob = json.dumps(body, separators=(",", ":")).encode()
        envelope = create(key=auth_key, origin=inputs.origin, input_trace=b"",
                          body=blob, expected=inputs.binding, expected_origin=inputs.origin,
                          expected_events=len(events), limits=inputs.limits, interfaces=inputs.profiles())
        return replace(captured, envelope=envelope), changed

    events = json.loads(authenticated.body)["events"]
    for index, name in ((0, "removed first draw"), (2, "unrecorded watchdog draw"), (3, "record exhaustion")):
        candidate, request = modified(events[:index] + events[index + 1:])
        refuse(candidate, request)
        passed.append(name)

    for fault in ("EOF", "unexpected frame"):
        _protocol_failure(fault, executable, configuration, work, captured, inputs, auth_key, seal_key)
        passed.append(fault + " latches recorder/cursor and closes actual native pipes")
    wrong = json.loads(authenticated.body)["events"]
    wrong[0]["point"]["ordinal"] = 1
    candidate, request = modified(wrong)
    refuse(candidate, request)
    passed.append("wrong actual draw point")
    trailing = json.loads(authenticated.body)["events"]
    extra = json.loads(json.dumps(trailing[-1]))
    extra["point"]["slot"] = 7
    candidate, request = modified([*trailing, extra])
    refuse(candidate, request)
    passed.append("trailing event")

    for limits, expected_same, name in (
        (replace(inputs.limits, max_events=0), True, "event capacity before source advancement"),
        (replace(inputs.limits, max_body_bytes=400), True, "body capacity before source advancement"),
        (inputs.limits, False, "declined commitment after source advancement"),
    ):
        request = replace(inputs, limits=limits, events=0 if expected_same else 4)
        session = CaptureSession(request, authentication_key=auth_key, seal_key=seal_key,
                                 seal=None if expected_same else (lambda _point, _word: None))
        try:
            session.run(executable, configuration, work)
        except ReplayRuntimeError as error:
            ensure(error.source_unchanged is expected_same, "actual source-state refusal observation agrees")
        else:
            raise AssertionError("native recording refusal control passed")
        try:
            session.recorder.finish(expected=inputs.binding, expected_events=0)
        except RecordError:
            pass
        else:
            raise AssertionError("uncertain prefix finalized through direct recorder access")
        passed.append(name)

    # Evidence contains public verdicts/identities only; no keys, words or envelopes.
    receipt = {"scope": "finite generated-Sail call-level development checkpoint",
               "production": False, "instruction_replay": False, "ct_proof": False,
               "draw_dependent_faults": "unsupported", "successful_events": 4,
               "artifact_binding": {"base_image_root": "exact native executable SHA256",
                                    "composition": "exact passed configuration-byte SHA256",
                                    "preflight_and_completion": True,
                                    "trusted_exclusive_lane": True,
                                    "adversarial_race_free_pinning": False},
               "public_observations": dict(captured.observations), "passed_controls": passed,
               "harness_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
               "configuration_sha256": inputs.binding.composition,
               "controller_sha256": hashlib.sha256((environment.root / "tools/vos/replay_runtime.py").read_bytes()).hexdigest(),
               "test_sha256": hashlib.sha256((environment.root / "tools/tests/test_replay_runtime.py").read_bytes()).hexdigest(),
               "tools": receipts.executables("sail", "clang++", "cmake", "ninja", "ccache"),
               "sail_version": env.SAIL_VERSION,
               "source_sha256": {path: hashlib.sha256((environment.root / path).read_bytes()).hexdigest()
                                 for path in ("model/model/core/callbacks.sail", "model/model/sys/rot.sail",
                                              "model/model/unit_tests/test_rot.sail", "model/model/CMakeLists.txt",
                                              "model/c_emulator/riscv_platform_if.h", "model/c_emulator/riscv_platform_if.cpp",
                                              "model/test/unit_tests/entropy_capture.cpp", "tools/vos/replay_record.py",
                                              "tools/vos/replay_envelope.py", "tools/opam/sail.lock")}}
    (work / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="")


def cases() -> list[Case]:
    return [Case("development-keys-modes-and-inputs", _parameters),
            Case("buffered-second-frame-stays-bounded", _buffered_bound),
            Case("actual-generated-sail-capture-replay-and-refusals", _native, slow=True, lane="toolchain")]
