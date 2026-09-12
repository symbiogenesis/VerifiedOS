# SPDX-License-Identifier: Apache-2.0
"""Bounded host callback capture, with no production ABI or sealing fixture."""

import json
from collections.abc import Callable
from dataclasses import replace
from functools import partial
from typing import cast

from tests.harness import Case, ensure
from vos.replay_record import (
    Binding,
    Event,
    FixtureCursor,
    FixtureRecorder,
    Interface,
    Limits,
    Point,
    RecordError,
    decode,
)

_BINDING = Binding("0123", "a" * 64, "b" * 64)
_INTERFACES = {f"{i + 1:064x}": Interface(source, 4) for i, source in enumerate(
    ("entropy", "link_address", "time_read", "physical_event"))}
_ENTROPY, _ADDRESS, _TIME, _PHYSICAL = _INTERFACES
_LIMITS = Limits(4096, 4)
_POINT = Point(0, 0, 0, 0)


def _valid(payload: bytes) -> bool:
    # A deliberately small synthetic language, not a link, time or sentinel ABI.
    return len(payload) == 2 and payload[0] == 0


def _value(payload: bytes | None) -> bytes | None:
    return payload


def _recorder(*, limits: Limits = _LIMITS) -> FixtureRecorder:
    return FixtureRecorder(_BINDING, limits=limits, interfaces=_INTERFACES,
                           validators={identity: _valid for identity, profile in
                                       _INTERFACES.items() if profile.source != "entropy"})


def _refused(fn: Callable[[], object]) -> None:
    try:
        fn()
    except RecordError:
        return
    raise AssertionError("capture refusal was not raised")


def _finish(recorder: FixtureRecorder, count: int) -> bytes:
    return recorder.finish(expected=_BINDING, expected_events=count)


def _dead(recorder: FixtureRecorder) -> None:
    calls: list[int] = []

    def source() -> bytes:
        calls.append(1)
        return b"\x00\xff"

    _refused(partial(recorder.record, point=_POINT, interface=_ENTROPY, produce=source))
    _refused(partial(_finish, recorder, 0))
    ensure(not calls, "a closed or poisoned capture must not call another source")


def _roundtrip_and_close() -> None:
    recorder = _recorder()
    wanted: list[Event] = []
    for ordinal, (identity, profile) in enumerate(_INTERFACES.items()):
        point = replace(_POINT, ordinal=ordinal)
        payload = b"\xfe\x00" if profile.source == "entropy" else b"\x00\xff"
        expected = Event(ordinal, point, profile.source, identity, payload)
        event = recorder.record(point=point, interface=identity, produce=partial(_value, payload))
        ensure(event == expected, "source-fixed classification and bytes must stay exact")
        wanted.append(expected)
    blob = _finish(recorder, 4)
    record = decode(blob, expected=_BINDING, expected_events=4, limits=_LIMITS,
                    interfaces=_INTERFACES)
    ensure(record.events == tuple(wanted), "independent reader must accept the entire capture")
    ensure(b'"sealed_commitment":"fe00"' in blob and b'"value":"00ff"' in blob,
           "public bytes and opaque commitment fields must use their fixed classes")
    cursor = FixtureCursor(record)
    for event in wanted:
        ensure(cursor.consume(point=event.point, source=event.source,
                              interface=event.interface) == event, "cursor demand must match")
    cursor.finish()
    _dead(recorder)


def _event_capacity_precedes_source() -> None:
    for capacity in (0, 1):
        recorder = _recorder(limits=Limits(4096, capacity))
        if capacity:
            recorder.record(point=_POINT, interface=_ENTROPY, produce=lambda: b"\x00")
        calls: list[int] = []

        def source(calls: list[int] = calls) -> bytes:
            calls.append(1)
            return b"\x00"

        _refused(partial(recorder.record, point=replace(_POINT, ordinal=1),
                         interface=_ENTROPY, produce=source))
        ensure(not calls, "event exhaustion must refuse before a side effect")
        _refused(partial(_finish, recorder, capacity))


def _body_capacity_reserves_maximum() -> None:
    reference = _recorder()
    reference.record(point=_POINT, interface=_ENTROPY, produce=lambda: b"\x00" * 4)
    maximum_size = len(_finish(reference, 1))
    exact = _recorder(limits=Limits(maximum_size, 4))
    exact.record(point=_POINT, interface=_ENTROPY, produce=lambda: b"\x00" * 4)
    ensure(len(_finish(exact, 1)) == maximum_size, "exact maximum-sized event must fit")
    recorder = _recorder(limits=Limits(maximum_size - 1, 4))
    calls: list[int] = []

    def smaller_source() -> bytes:
        calls.append(1)
        return b"\x00"  # This actual value would fit, but discovering it consumes it.

    _refused(partial(recorder.record, point=_POINT, interface=_ENTROPY, produce=smaller_source))
    ensure(not calls, "reserve maximum payload bytes before discovering actual bytes")
    _dead(recorder)


def _actual_size_releases_unused_reservation() -> None:
    reference = _recorder()
    reference.record(point=_POINT, interface=_ENTROPY, produce=lambda: b"\x00")
    reference.record(point=replace(_POINT, ordinal=1), interface=_ENTROPY,
                     produce=lambda: b"\x00" * 4)
    bound = len(_finish(reference, 2))
    recorder = _recorder(limits=Limits(bound, 4))
    recorder.record(point=_POINT, interface=_ENTROPY, produce=lambda: b"\x00")
    recorder.record(point=replace(_POINT, ordinal=1), interface=_ENTROPY,
                    produce=lambda: b"\x00" * 4)
    ensure(len(_finish(recorder, 2)) == bound,
           "reservation is temporary; actual bytes and array comma decide subsequent room")


def _no_value_does_not_advance() -> None:
    recorder = _recorder(limits=Limits(4096, 1))
    ensure(recorder.record(point=_POINT, interface=_ENTROPY, produce=lambda: None) is None,
           "a source declining without consumption has no nondeterminism event")
    event = recorder.record(point=_POINT, interface=_ENTROPY, produce=lambda: b"\x00")
    ensure(event is not None and event.seq == 0, "no-value outcome must release its reservation")
    _finish(recorder, 1)
    empty = _recorder()
    empty.record(point=_POINT, interface=_ENTROPY, produce=lambda: None)
    ensure(json.loads(_finish(empty, 0))["events"] == [], "independent empty window can finish")


def _exceptions_and_payload_refusals_poison() -> None:
    for payload in (b"", b"\x00" * 5, bytearray(b"\x00"), "00", False):
        recorder = _recorder()
        recorder.record(point=_POINT, interface=_ENTROPY, produce=lambda: b"\x00")
        _refused(partial(recorder.record, point=replace(_POINT, ordinal=1),
                         interface=_ENTROPY, produce=partial(_value, cast(bytes, payload))))
        _refused(partial(_finish, recorder, 1))
    recorder = _recorder()
    effects: list[int] = []

    def broken_source() -> bytes:
        effects.append(1)
        raise RuntimeError("synthetic source fails after a side effect")

    try:
        recorder.record(point=_POINT, interface=_ENTROPY, produce=broken_source)
    except RuntimeError:
        pass
    else:
        raise AssertionError("source exception must propagate")
    ensure(effects == [1], "exception control must exercise an actual callback side effect")
    _dead(recorder)


def _public_semantics_and_validator_errors() -> None:
    for identity in (_ADDRESS, _TIME, _PHYSICAL):
        recorder = _recorder()
        released: list[object] = []

        def bad_payload(recorder: FixtureRecorder = recorder, identity: str = identity,
                        released: list[object] = released) -> None:
            released.append(recorder.record(point=_POINT, interface=identity,
                                            produce=lambda: b"\xff\x00"))

        _refused(bad_payload)
        ensure(not released, "failed public semantics must never return a usable event")
        _dead(recorder)

    def broken_validator(_payload: bytes) -> bool:
        raise RuntimeError("synthetic validator failure")

    recorder = FixtureRecorder(_BINDING, limits=_LIMITS, interfaces=_INTERFACES,
                               validators=dict.fromkeys((_ADDRESS, _TIME, _PHYSICAL),
                                                        broken_validator))
    try:
        recorder.record(point=_POINT, interface=_TIME, produce=lambda: b"\x00\xff")
    except RuntimeError:
        pass
    else:
        raise AssertionError("validator exception must propagate")
    _dead(recorder)


def _admission_rejects_bad_endpoint_or_point() -> None:
    for point, identity in (
        (replace(_POINT, slot=True), _ENTROPY),
        (replace(_POINT, core=-1), _ENTROPY),
        (replace(_POINT, retire=1 << 64), _ENTROPY),
        (replace(_POINT, ordinal=0.0), _ENTROPY),
        (_POINT, "f" * 64), (_POINT, "ABC"),
    ):
        recorder = _recorder()
        calls: list[int] = []

        def source(calls: list[int] = calls) -> bytes:
            calls.append(1)
            return b"\x00"

        _refused(partial(recorder.record, point=point, interface=identity, produce=source))
        ensure(not calls, "invalid admission metadata must never call source")
        _dead(recorder)
    for later in (Point(0, 0, 3, 0), Point(1, 0, 2, 0)):
        recorder = _recorder()
        recorder.record(point=Point(0, 0, 3, 0), interface=_ENTROPY, produce=lambda: b"\x00")
        _refused(partial(recorder.record, point=later, interface=_ENTROPY,
                         produce=lambda: b"\x00"))
        _refused(partial(_finish, recorder, 1))


def _reentrant_refusals_cannot_be_swallowed() -> None:
    for nested_finish in (False, True):
        recorder = _recorder()

        def reentrant_source(nested_finish: bool = nested_finish,
                             recorder: FixtureRecorder = recorder) -> bytes | None:
            if nested_finish:
                _refused(partial(_finish, recorder, 0))
                return None
            _refused(partial(recorder.record, point=_POINT, interface=_ENTROPY,
                             produce=lambda: b"\x00"))
            return b"\x00"

        _refused(partial(recorder.record, point=_POINT, interface=_ENTROPY,
                         produce=reentrant_source))
        _dead(recorder)

    def reentrant_validator(_payload: bytes) -> bool:
        _refused(partial(_finish, recorder, 0))
        return True

    recorder = FixtureRecorder(_BINDING, limits=_LIMITS, interfaces=_INTERFACES,
                               validators=dict.fromkeys((_ADDRESS, _TIME, _PHYSICAL),
                                                        reentrant_validator))
    _refused(partial(recorder.record, point=_POINT, interface=_TIME,
                     produce=lambda: b"\x00\xff"))
    _dead(recorder)


def _independent_finish_refuses_missing_or_wrong_binding() -> None:
    for expected, count in (
        (_BINDING, 0), (_BINDING, 2), (_BINDING, True),
        (replace(_BINDING, base_image_root="ab"), 1),
        (replace(_BINDING, composition="c" * 64), 1),
        (replace(_BINDING, input_trace="c" * 64), 1),
    ):
        recorder = _recorder()
        recorder.record(point=_POINT, interface=_ENTROPY, produce=lambda: b"\x00")
        _refused(partial(recorder.finish, expected=expected, expected_events=count))
        _refused(partial(_finish, recorder, 1))
        _dead(recorder)


def _external_profiles_are_snapshotted_and_checked() -> None:
    interfaces = dict(_INTERFACES)
    validators: dict[str, Callable[[bytes], bool]] = dict.fromkeys((_ADDRESS, _TIME, _PHYSICAL), _valid)
    recorder = FixtureRecorder(_BINDING, limits=_LIMITS, interfaces=interfaces,
                               validators=validators)
    interfaces[_TIME] = Interface("entropy", 1)
    validators[_TIME] = lambda _payload: False
    event = recorder.record(point=_POINT, interface=_TIME, produce=lambda: b"\x00\xff")
    ensure(event is not None and event.source == "time_read", "caller cannot change composed profiles")
    _finish(recorder, 1)
    for supplied in ({}, {_ENTROPY: _valid}, {_TIME: _valid}):
        _refused(partial(FixtureRecorder, _BINDING, limits=_LIMITS, interfaces=_INTERFACES,
                         validators=supplied))
    _refused(partial(_recorder, limits=Limits(1, 4)))


def cases() -> list[Case]:
    return [Case(fn.__name__.lstrip("_"), fn) for fn in (
        _roundtrip_and_close,
        _event_capacity_precedes_source,
        _body_capacity_reserves_maximum,
        _actual_size_releases_unused_reservation,
        _no_value_does_not_advance,
        _exceptions_and_payload_refusals_poison,
        _public_semantics_and_validator_errors,
        _admission_rejects_bad_endpoint_or_point,
        _reentrant_refusals_cannot_be_swallowed,
        _independent_finish_refuses_missing_or_wrong_binding,
        _external_profiles_are_snapshotted_and_checked,
    )]
