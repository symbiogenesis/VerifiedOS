# SPDX-License-Identifier: Apache-2.0
"""Synthetic record acceptance and telling refusals, with no replay claim."""

import json
from collections.abc import Callable
from dataclasses import replace
from functools import partial
from typing import cast

from tests.harness import Case, ensure
from vos.jsonc import Json
from vos.replay_record import (
    SCHEMA,
    Binding,
    FixtureCursor,
    Interface,
    Limits,
    Point,
    Record,
    RecordError,
    decode,
    instruction_point,
)

# Synthetic endpoint identities and payloads, not claimed production ABIs,
# actual entropy, sealed objects, or cryptographic authentication fixtures.
_SOURCES = ("entropy", "link_address", "time_read", "physical_event")
_INTERFACES = {f"{i + 1:064x}": Interface(source, 16)
               for i, source in enumerate(_SOURCES)}
_BINDING = Binding("001122", "a" * 64, "b" * 64)
_LIMITS = Limits(16_384, 4)


def _fixture() -> dict[str, Json]:
    events: list[Json] = []
    for i, (identity, profile) in enumerate(_INTERFACES.items()):
        events.append({
            "seq": i, "source": profile.source, "interface": identity,
            "point": {"slot": 0, "core": 0, "retire": 0, "ordinal": i},
            "payload": {"sealed_commitment" if i == 0 else "value": "00ff0100"},
        })
    return {"schema": SCHEMA, "binding": {
        "base_image_root": _BINDING.base_image_root,
        "composition": _BINDING.composition, "input_trace": _BINDING.input_trace,
    }, "events": events}


def _events(body: dict[str, Json]) -> list[dict[str, Json]]:
    # The synthetic builder fixes this narrower mutable shape. Passing through
    # object avoids claiming invariant list types are generally interchangeable.
    return cast(list[dict[str, Json]], cast(object, body["events"]))


def _blob(body: Json) -> bytes:
    return json.dumps(body, separators=(",", ":")).encode("utf-8")


def _read(body: Json, *, expected: Binding = _BINDING, count: int = 4,
          limits: Limits = _LIMITS) -> Record:
    return decode(_blob(body), expected=expected, expected_events=count,
                  limits=limits, interfaces=_INTERFACES)


def _refused(fn: Callable[[], object]) -> None:
    try:
        fn()
    except RecordError:
        return
    raise AssertionError("defective fixture was accepted")


def _public_and_secret() -> None:
    record = _read(_fixture())
    ensure(tuple(e.source for e in record.events) == _SOURCES, "source set drifted")
    ensure(all(e.payload == b"\x00\xff\x01\x00" for e in record.events),
           "payload bytes including leading zero must remain exact")
    ensure(record.binding == _BINDING, "opaque root width belongs to image owner")
    cursor = FixtureCursor(record)
    for event in record.events:
        ensure(cursor.consume(point=event.point, source=event.source,
                              interface=event.interface) == event, "demand changed bytes")
    cursor.finish()
    _refused(cursor.finish)


def _unknown_fields_and_secrets() -> None:
    for extra in ("seed", "draw", "hash", "dump", "metadata"):
        body = _fixture()
        payload = cast(dict[str, Json], _events(body)[0]["payload"])
        payload[extra] = "01"
        _refused(partial(_read, body))
    for level in ("body", "binding", "event", "point"):
        body = _fixture()
        objects = {"body": body, "binding": cast(dict[str, Json], body["binding"]),
                   "event": _events(body)[0],
                   "point": cast(dict[str, Json], _events(body)[0]["point"])}
        objects[level]["extension"] = "01"
        _refused(partial(_read, body))
    for index, field in ((0, "value"), (1, "sealed_commitment")):
        body = _fixture()
        _events(body)[index]["payload"] = {field: "01"}
        _refused(partial(_read, body))


def _closed_sources_and_interfaces() -> None:
    for field, value in (("source", "jitter"), ("source", []),
                         ("interface", "0" * 64), ("interface", "2".zfill(64))):
        body = _fixture()
        _events(body)[0][field] = value
        _refused(partial(_read, body))
    body = _fixture()
    body["schema"] = "replay-record-v2"
    _refused(partial(_read, body))


def _bindings() -> None:
    for expected in (replace(_BINDING, base_image_root="00"),
                     replace(_BINDING, composition="c" * 64),
                     replace(_BINDING, input_trace="c" * 64)):
        _refused(partial(_read, _fixture(), expected=expected))
    for field, value in (("base_image_root", ""), ("base_image_root", "ab0"),
                         ("composition", "a" * 16), ("input_trace", "B" * 64)):
        body = _fixture()
        cast(dict[str, Json], body["binding"])[field] = value
        _refused(partial(_read, body))


def _sequence_and_truncation() -> None:
    for position in range(4):
        body = _fixture()
        del _events(body)[position]
        _refused(partial(_read, body))
    for seq in (0, 2, -1, True, 1.0, 1 << 64):
        body = _fixture()
        _events(body)[1]["seq"] = seq
        _refused(partial(_read, body))
    body = _fixture()
    _events(body).reverse()
    _refused(partial(_read, body))
    body = _fixture()
    _events(body).append(_events(body)[-1])
    _refused(partial(_read, body))


def _coordinates() -> None:
    for field in ("slot", "core", "retire", "ordinal"):
        for value in (-1, True, 0.0, 1 << 64, "0"):
            body = _fixture()
            cast(dict[str, Json], _events(body)[0]["point"])[field] = value
            _refused(partial(_read, body))
    body = _fixture()
    _events(body)[1]["point"] = _events(body)[0]["point"]
    _refused(partial(_read, body))
    # A larger slot makes tuple order increase, but cannot hide a local reset.
    body = _fixture()
    _events(body)[0]["point"] = {"slot": 0, "core": 0, "retire": 9, "ordinal": 0}
    _events(body)[1]["point"] = {"slot": 1, "core": 0, "retire": 0, "ordinal": 0}
    _refused(partial(_read, body))


def _bounds_and_bytes() -> None:
    body = _fixture()
    exact = len(_blob(body))
    _read(body, limits=Limits(exact, 4))
    _refused(lambda: _read(body, limits=Limits(exact - 1, 4)))
    _refused(lambda: _read(body, limits=Limits(exact, 3)))
    _refused(lambda: _read(body, count=3))
    for encoded in ("", "0", "AA", "0g", "00 ", "00" * 17):
        body = _fixture()
        _events(body)[0]["payload"] = {"sealed_commitment": encoded}
        _refused(partial(_read, body))
    body = _fixture()
    _events(body)[0]["payload"] = {"sealed_commitment": "00" * 16}
    _read(body)


def _json_refusals() -> None:
    valid = _blob(_fixture())
    malformed = (b"[]", b"null", b"{", b"\xff", valid[:-1],
                 valid.replace(b'"seq":0', b'"seq":0,"seq":0', 1),
                 valid.replace(b'"seq":0', b'"seq":NaN', 1),
                 valid.replace(b'"seq":0', b'"seq":Infinity', 1),
                 valid.replace(b'"seq":0', b'"seq":' + b"9" * 5000, 1),
                 b"[" * 1200 + b"]" * 1200)
    for blob in malformed:
        _refused(partial(decode, blob, expected=_BINDING, expected_events=4,
                         limits=_LIMITS, interfaces=_INTERFACES))
    for value in (None, [], "string", 1):
        body = _fixture()
        body["events"] = value
        _refused(partial(_read, body))


def _cursor_refusals_latch() -> None:
    record = _read(_fixture())
    event = record.events[0]
    for point, source, identity in (
        (replace(event.point, ordinal=1), event.source, event.interface),
        (replace(event.point, retire=False), event.source, event.interface),
        (event.point, "time_read", event.interface),
        (event.point, event.source, "0" * 64),
    ):
        cursor = FixtureCursor(record)
        _refused(partial(cursor.consume, point=point, source=source, interface=identity))
        _refused(partial(cursor.consume, point=event.point, source=event.source,
                         interface=event.interface))
        _refused(cursor.finish)
    cursor = FixtureCursor(record)
    _refused(cursor.finish)  # even untouched valid bytes cannot excuse trailing events
    cursor = FixtureCursor(record)
    for event in record.events:
        cursor.consume(point=event.point, source=event.source, interface=event.interface)
    _refused(partial(cursor.consume, point=event.point, source=event.source,
                     interface=event.interface))
    _refused(cursor.finish)


def _trace_anchor_and_async() -> None:
    point = instruction_point("I 17 0000000080000000 00000013", slot=4, core=2, ordinal=0)
    ensure(point == Point(4, 2, 17, 0), "trace normalizer must not erase retire order")
    for line in ("I 0000000080000000 00000013", "X 1 0 0000000000000001",
                 "I 17 0000000080000000 00000013 ignored"):
        _refused(partial(instruction_point, line, slot=4, core=2, ordinal=0))
    ensure(_read(_fixture()).events[-1].point.retire == 0,
           "physical events require no retiring instruction")
    body = _fixture()
    body["events"] = []
    empty = _read(body, count=0)
    FixtureCursor(empty).finish()  # externally declared empty capture only


def cases() -> list[Case]:
    return [
        Case("public-and-secret", _public_and_secret),
        Case("unknown-fields-and-secrets", _unknown_fields_and_secrets),
        Case("closed-sources-and-interfaces", _closed_sources_and_interfaces),
        Case("bindings", _bindings),
        Case("sequence-and-truncation", _sequence_and_truncation),
        Case("coordinates", _coordinates),
        Case("bounds-and-bytes", _bounds_and_bytes),
        Case("json-refusals", _json_refusals),
        Case("cursor-refusals-latch", _cursor_refusals_latch),
        Case("trace-anchor-and-async", _trace_anchor_and_async),
    ]
