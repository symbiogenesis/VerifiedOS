# SPDX-License-Identifier: Apache-2.0
"""Bounded review-body fixtures for replay-record-contract.md.

This is structural fixture validation. It neither authenticates opaque seals nor
records, exports, or replays a machine. In particular, an Event's secret payload
is opaque commitment bytes, never entropy a consumer may substitute or unseal.
"""

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import cast

from vos.jsonc import Json
from vos.trace import COMMIT_RE

SCHEMA = "replay-record-v1"
SOURCES = frozenset({"entropy", "link_address", "time_read", "physical_event"})
U64_MAX = (1 << 64) - 1


class RecordError(ValueError):
    """A whole body or a fixture consumption request is refused."""


@dataclass(frozen=True)
class Binding:
    base_image_root: str
    composition: str
    input_trace: str


@dataclass(frozen=True)
class Limits:
    max_body_bytes: int
    max_events: int


@dataclass(frozen=True)
class Interface:
    source: str
    max_payload_bytes: int


@dataclass(frozen=True, order=True)
class Point:
    slot: int
    core: int
    retire: int
    ordinal: int


@dataclass(frozen=True)
class Event:
    seq: int
    point: Point
    source: str
    interface: str
    payload: bytes


@dataclass(frozen=True)
class Record:
    binding: Binding
    events: tuple[Event, ...]


def _uint(value: object) -> int:
    if type(value) is not int or not 0 <= value <= U64_MAX:
        raise RecordError("integer must be unsigned 64-bit, never bool or float")
    return value


def _hex(value: object, *, digest: bool = False) -> str:
    if not isinstance(value, str) or not value or len(value) % 2:
        raise RecordError("expected nonempty even-length hex")
    if re.fullmatch(r"[0-9a-f]+", value) is None or (digest and len(value) != 64):
        raise RecordError("invalid lowercase hex or host digest width")
    return value


def _object(value: Json, keys: set[str]) -> dict[str, Json]:
    if not isinstance(value, dict) or value.keys() != keys:
        raise RecordError("object has missing or unknown fields")
    return value


def _pairs(pairs: list[tuple[str, Json]]) -> dict[str, Json]:
    result: dict[str, Json] = {}
    for key, value in pairs:
        if key in result:
            raise RecordError("duplicate JSON key")
        result[key] = value
    return result


def _noninteger(_value: str) -> None:
    raise RecordError("floating-point and non-finite JSON numbers are unsupported")


def _integer(value: str) -> int:
    if len(value) > 20:
        raise RecordError("JSON integer exceeds coordinate width")
    return int(value)


def _point(raw: Json) -> Point:
    obj = _object(raw, {"slot", "core", "retire", "ordinal"})
    return Point(*(_uint(obj[key]) for key in ("slot", "core", "retire", "ordinal")))


def instruction_point(line: str, *, slot: int, core: int, ordinal: int) -> Point:
    """Preserve the existing emitter's order for a local development anchor.

    Physical events may instead name the current count directly with Point;
    they do not require an instruction to retire. No effect value is exported.
    """
    if not line.startswith("I ") or COMMIT_RE.fullmatch(line) is None:
        raise RecordError("anchor requires one existing commit I record")
    return Point(_uint(slot), _uint(core), _uint(_integer(line.split()[1])), _uint(ordinal))


def decode(blob: bytes, *, expected: Binding, expected_events: int,
           limits: Limits, interfaces: Mapping[str, Interface]) -> Record:
    """Read the complete bounded body or raise, without accepting a prefix.

    Expected bindings/count and interface profiles come from an independent
    fixture descriptor. Their production authentication and public payload
    semantics remain the absent envelope reader and adapter's obligations.
    """
    if _uint(limits.max_body_bytes) == 0 or _uint(expected_events) > _uint(limits.max_events):
        raise RecordError("invalid external bounds or expected count")
    if len(blob) > limits.max_body_bytes:
        raise RecordError("body byte capacity exceeded")
    _hex(expected.base_image_root)
    _hex(expected.composition, digest=True)
    _hex(expected.input_trace, digest=True)
    for identity, profile in interfaces.items():
        _hex(identity, digest=True)
        if profile.source not in SOURCES or _uint(profile.max_payload_bytes) == 0:
            raise RecordError("invalid external interface profile")
    try:
        raw = cast(Json, json.loads(blob.decode("utf-8"), object_pairs_hook=_pairs,
                                   parse_constant=_noninteger, parse_float=_noninteger,
                                   parse_int=_integer))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise RecordError("invalid UTF-8 JSON body") from None
    body = _object(raw, {"schema", "binding", "events"})
    if body["schema"] != SCHEMA:
        raise RecordError("unsupported schema")
    binding = _object(body["binding"], {"base_image_root", "composition", "input_trace"})
    found = Binding(_hex(binding["base_image_root"]),
                    _hex(binding["composition"], digest=True),
                    _hex(binding["input_trace"], digest=True))
    if found != expected:
        raise RecordError("binding differs from independent expected identity")
    entries = body["events"]
    if not isinstance(entries, list) or len(entries) != expected_events:
        raise RecordError("event count differs from independent capture descriptor")

    events: list[Event] = []
    retired: dict[int, int] = {}
    for seq, entry in enumerate(entries):
        obj = _object(entry, {"seq", "point", "source", "interface", "payload"})
        if _uint(obj["seq"]) != seq:
            raise RecordError("event sequence is not contiguous")
        point = _point(obj["point"])
        if events and point <= events[-1].point:
            raise RecordError("event coordinates are repeated or regressing")
        if point.retire < retired.get(point.core, 0):
            raise RecordError("local retire count regresses within capture origin")
        source = obj["source"]
        if not isinstance(source, str) or source not in SOURCES:
            raise RecordError("unsupported nondeterminism source")
        identity = _hex(obj["interface"], digest=True)
        profile = interfaces.get(identity)
        if profile is None or profile.source != source:
            raise RecordError("interface is unknown or belongs to another source")
        field = "sealed_commitment" if source == "entropy" else "value"
        payload = _object(obj["payload"], {field})
        encoded = _hex(payload[field])
        if len(encoded) // 2 > profile.max_payload_bytes:
            raise RecordError("interface payload capacity exceeded")
        events.append(Event(seq, point, source, identity, bytes.fromhex(encoded)))
        retired[point.core] = point.retire
    return Record(found, tuple(events))


def _event_body(event: Event) -> dict[str, Json]:
    return {
        "seq": event.seq,
        "point": {"slot": event.point.slot, "core": event.point.core,
                  "retire": event.point.retire, "ordinal": event.point.ordinal},
        "source": event.source,
        "interface": event.interface,
        "payload": {"sealed_commitment" if event.source == "entropy" else "value":
                    event.payload.hex()},
    }


def _encode(value: Json) -> bytes:
    return json.dumps(value, separators=(",", ":")).encode("utf-8")


def _record_body(binding: Binding, events: list[Event]) -> bytes:
    return _encode({
        "schema": SCHEMA,
        "binding": {"base_image_root": binding.base_image_root,
                    "composition": binding.composition, "input_trace": binding.input_trace},
        "events": [_event_body(event) for event in events],
    })


class FixtureRecorder:
    """Single-caller bounded capture with admission before a fixture callback.

    Public endpoint validators decide fixture payload semantics, not production
    service ABIs. Entropy callbacks return opaque commitment bytes, never draws;
    nothing here establishes that those bytes are sealed. A callback returning
    None promises no value was consumed and no nondeterminism event is owed.
    Any exception or refusal poisons the capture, even if a callback catches it.
    Only finish can return body bytes, and only for independent bindings/count.
    """

    def __init__(self, binding: Binding, *, limits: Limits,
                 interfaces: Mapping[str, Interface],
                 validators: Mapping[str, Callable[[bytes], bool]]) -> None:
        self._binding = binding
        self._limits = limits
        self._interfaces = dict(interfaces)
        self._validators = dict(validators)
        self._events: list[Event] = []
        self._retired: dict[int, int] = {}
        self._busy = False
        self._failed = False
        self._finished = False
        empty = _record_body(binding, [])
        decode(empty, expected=binding, expected_events=0, limits=limits,
               interfaces=self._interfaces)
        public = {identity for identity, profile in self._interfaces.items()
                  if profile.source != "entropy"}
        if self._validators.keys() != public or not all(map(callable, self._validators.values())):
            raise RecordError("every public fixture endpoint requires its own validator")
        self._body_bytes = len(empty)

    def _ready(self) -> None:
        if self._failed or self._finished or self._busy:
            raise RecordError("capture is refused, finished, or already consuming")

    def _admit(self, point: Point, interface: str) -> tuple[Event, Interface, int]:
        self._ready()
        for value in (point.slot, point.core, point.retire, point.ordinal):
            _uint(value)
        if self._events and point <= self._events[-1].point:
            raise RecordError("event coordinates are repeated or regressing")
        if point.retire < self._retired.get(point.core, 0):
            raise RecordError("local retire count regresses within capture origin")
        identity = _hex(interface, digest=True)
        profile = self._interfaces.get(identity)
        if profile is None:
            raise RecordError("interface is not a composed fixture endpoint")
        seq = len(self._events)
        if seq >= self._limits.max_events:
            raise RecordError("event capacity exhausted before source consumption")
        template = Event(seq, point, profile.source, identity, b"")
        overhead = len(_encode(_event_body(template))) + (1 if seq else 0)
        if self._body_bytes + overhead + 2 * profile.max_payload_bytes > self._limits.max_body_bytes:
            raise RecordError("body capacity exhausted before source consumption")
        return template, profile, overhead

    def record(self, *, point: Point, interface: str,
               produce: Callable[[], bytes | None]) -> Event | None:
        """Reserve the endpoint maximum before calling produce, then record it.

        A public event is returned only after validation and append. The maximum
        reservation can refuse a smaller actual payload that would fit; it never
        calls a side-effectful source to discover whether there is enough room.
        This refusal is not an implementation of the reserved terminal fault path.
        """
        try:
            template, profile, overhead = self._admit(point, interface)
            self._busy = True
            try:
                payload = produce()
                if self._failed:
                    raise RecordError("callback caught a nested capture refusal")
                if payload is None:
                    return None
                if type(payload) is not bytes or not 0 < len(payload) <= profile.max_payload_bytes:
                    raise RecordError("callback returned an invalid or oversized payload")
                if profile.source != "entropy":
                    if self._validators[template.interface](payload) is not True:
                        raise RecordError("public fixture payload failed endpoint validation")
                    if self._failed:
                        raise RecordError("validator caught a nested capture refusal")
                event = Event(template.seq, point, profile.source, template.interface, payload)
                self._events.append(event)
                self._retired[point.core] = point.retire
                self._body_bytes += overhead + 2 * len(payload)
                return event
            finally:
                self._busy = False
        except BaseException:
            # Source exceptions may follow an irreversible side effect. Preserve
            # cancellation/exception identity, but never finalize an uncertain prefix.
            self._failed = True
            raise

    def finish(self, *, expected: Binding, expected_events: int) -> bytes:
        """Close once, refusing the whole capture on binding/count disagreement."""
        try:
            self._ready()
            blob = _record_body(self._binding, self._events)
            decode(blob, expected=expected, expected_events=expected_events,
                   limits=self._limits, interfaces=self._interfaces)
        except BaseException:
            self._failed = True
            raise
        else:
            self._finished = True
            return blob


class FixtureCursor:
    """Demand matching for tests, with a latched refusal and explicit finish.

    Returning an opaque Event validates fixture sequencing only. It performs
    no entropy substitution, payload-semantic validation, or machine injection.
    """

    def __init__(self, record: Record) -> None:
        self._record = record
        self._next = 0
        self._failed = False
        self._finished = False

    def _refuse(self) -> None:
        self._failed = True
        raise RecordError("fixture demand or completion differs from record")

    def consume(self, *, point: Point, source: str, interface: str) -> Event:
        if self._failed or self._finished or self._next >= len(self._record.events):
            self._refuse()
        # Python's bool and float equality can otherwise impersonate an int
        # when a fixture request is constructed directly instead of decoded.
        if any(type(value) is not int
               for value in (point.slot, point.core, point.retire, point.ordinal)):
            self._refuse()
        event = self._record.events[self._next]
        if (event.point, event.source, event.interface) != (point, source, interface):
            self._refuse()
        self._next += 1
        return event

    def finish(self) -> None:
        if self._failed or self._finished or self._next != len(self._record.events):
            self._refuse()
        self._finished = True
