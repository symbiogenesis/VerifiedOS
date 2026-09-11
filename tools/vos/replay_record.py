# SPDX-License-Identifier: Apache-2.0
"""Bounded review-body reader for replay-record-contract.md.

This is structural fixture validation. It neither authenticates opaque seals nor
records, exports, or replays a machine. In particular, an Event's secret payload
is opaque commitment bytes, never entropy a consumer may substitute or unseal.
"""

import json
import re
from collections.abc import Mapping
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
