# SPDX-License-Identifier: Apache-2.0
"""Bounded host authentication for development replay artifacts.

This format authenticates bytes under an external shared development key. It
does not seal entropy, verify image signatures, authorize export, establish
capture completeness, or replay a machine. The input trace remains plaintext.
See docs/implementation/contracts/host-replay-envelope-contract.md.
"""

import hashlib
import hmac
import re
import struct
from collections.abc import Mapping
from dataclasses import dataclass

from vos.replay_record import (
    SOURCES,
    U64_MAX,
    Binding,
    Interface,
    Limits,
    Record,
    RecordError,
    decode,
)

# Every byte preceding the tag is authenticated, including the domain and
# version. The three unsigned big-endian lengths name origin, trace, then body.
_DOMAIN = b"VerifiedOS host replay envelope\x00"
_VERSION = 1
_HEADER = struct.Struct(">BQQQ")
_TAG_BYTES = 32
_FIXED_BYTES = len(_DOMAIN) + _HEADER.size + _TAG_BYTES


class EnvelopeError(ValueError):
    """The complete artifact or its independently supplied parameters refuse."""


@dataclass(frozen=True)
class EnvelopeLimits:
    max_envelope_bytes: int
    max_origin_bytes: int
    max_input_trace_bytes: int
    max_body_bytes: int
    max_events: int


@dataclass(frozen=True)
class AuthenticatedEnvelope:
    """Exact authenticated bytes and the structurally accepted replay record.

    Authentication is under the supplied host key only. This result contains no
    key, image-signature verdict, confidentiality verdict, or replay permission.
    """

    origin: bytes
    input_trace: bytes
    body: bytes
    record: Record


def _uint(value: object) -> bool:
    return type(value) is int and 0 <= value <= U64_MAX


def _hex(value: object, *, digest: bool = False) -> bool:
    return (type(value) is str and bool(value) and len(value) % 2 == 0
            and (not digest or len(value) == 64)
            and re.fullmatch(r"[0-9a-f]+", value) is not None)


def _parameters(*, key: bytes, expected: Binding, expected_origin: bytes,
                expected_events: int, limits: EnvelopeLimits,
                interfaces: Mapping[str, Interface]) -> dict[str, Interface]:
    if type(key) is not bytes or len(key) < 32:
        raise EnvelopeError("an external immutable development key needs at least 32 bytes")
    if type(limits) is not EnvelopeLimits or not all(_uint(value) for value in (
            limits.max_envelope_bytes, limits.max_origin_bytes,
            limits.max_input_trace_bytes, limits.max_body_bytes, limits.max_events)):
        raise EnvelopeError("capacities must be unsigned 64-bit integers")
    if type(expected) is not Binding or not (
            _hex(expected.base_image_root) and _hex(expected.composition, digest=True)
            and _hex(expected.input_trace, digest=True)):
        raise EnvelopeError("independent binding is malformed")
    if (type(expected_origin) is not bytes or not expected_origin
            or len(expected_origin) > limits.max_origin_bytes):
        raise EnvelopeError("independent origin is missing, mutable, or exceeds its capacity")
    if not _uint(expected_events) or expected_events > limits.max_events:
        raise EnvelopeError("independent event count is invalid or exceeds its capacity")
    if not isinstance(interfaces, Mapping):
        raise EnvelopeError("independent interface profiles require a mapping")
    profiles = dict(interfaces)
    for identity, profile in profiles.items():
        if (not _hex(identity, digest=True) or type(profile) is not Interface
                or type(profile.source) is not str or profile.source not in SOURCES
                or not _uint(profile.max_payload_bytes) or profile.max_payload_bytes == 0):
            raise EnvelopeError("independent interface profile is malformed")
    return profiles


def _sizes(origin: int, trace: int, body: int, total: int, limits: EnvelopeLimits) -> None:
    if (total > limits.max_envelope_bytes or origin > limits.max_origin_bytes
            or trace > limits.max_input_trace_bytes or body > limits.max_body_bytes):
        raise EnvelopeError("envelope or field capacity exceeded")
    if _FIXED_BYTES + origin + trace + body != total:
        raise EnvelopeError("declared lengths do not cover exactly one complete envelope")


def _tag(key: bytes, message: bytes | memoryview) -> bytes:
    return hmac.digest(key, message, "sha256")


def _record(*, origin: bytes, input_trace: bytes, body: bytes, expected: Binding,
            expected_origin: bytes, expected_events: int, limits: EnvelopeLimits,
            interfaces: Mapping[str, Interface]) -> Record:
    if origin != expected_origin:
        raise EnvelopeError("capture origin differs from independent expected bytes")
    if hashlib.sha256(input_trace).hexdigest() != expected.input_trace:
        raise EnvelopeError("input trace differs from independent expected digest")
    try:
        return decode(body, expected=expected, expected_events=expected_events,
                      limits=Limits(limits.max_body_bytes, limits.max_events), interfaces=interfaces)
    except RecordError as exc:
        raise EnvelopeError(str(exc)) from exc


def create(*, key: bytes, origin: bytes, input_trace: bytes, body: bytes,
           expected: Binding, expected_origin: bytes, expected_events: int,
           limits: EnvelopeLimits, interfaces: Mapping[str, Interface]) -> bytes:
    """Validate development inputs, then authenticate their exact bytes.

    An explicit empty input trace is allowed when its expected digest agrees.
    Missing bytes and mutable buffers are refused. The caller supplies the key;
    there is no persisted key or production mode.
    """
    profiles = _parameters(key=key, expected=expected, expected_origin=expected_origin,
                           expected_events=expected_events, limits=limits, interfaces=interfaces)
    if any(type(value) is not bytes for value in (origin, input_trace, body)):
        raise EnvelopeError("origin, input trace and body must be immutable bytes")
    lengths = (len(origin), len(input_trace), len(body))
    _sizes(*lengths, _FIXED_BYTES + sum(lengths), limits)
    _record(origin=origin, input_trace=input_trace, body=body, expected=expected,
            expected_origin=expected_origin, expected_events=expected_events,
            limits=limits, interfaces=profiles)
    message = b"".join((_DOMAIN, _HEADER.pack(_VERSION, *lengths), origin, input_trace, body))
    return message + _tag(key, message)


def verify(envelope: bytes, *, key: bytes, expected: Binding, expected_origin: bytes,
           expected_events: int, limits: EnvelopeLimits,
           interfaces: Mapping[str, Interface]) -> AuthenticatedEnvelope:
    """Authenticate the whole bounded artifact before decoding or releasing it.

    Only fixed-size framing is read before tag verification. Declared lengths
    cannot allocate buffers, body decoding cannot run on an invalid tag, and no
    payload or decoded prefix is returned on any refusal.
    """
    profiles = _parameters(key=key, expected=expected, expected_origin=expected_origin,
                           expected_events=expected_events, limits=limits, interfaces=interfaces)
    if type(envelope) is not bytes:
        raise EnvelopeError("envelope must be immutable bytes")
    total = len(envelope)
    if not _FIXED_BYTES <= total <= limits.max_envelope_bytes:
        raise EnvelopeError("envelope is truncated or exceeds its capacity")
    if not envelope.startswith(_DOMAIN):
        raise EnvelopeError("unsupported envelope domain")
    version, origin_size, trace_size, body_size = _HEADER.unpack_from(envelope, len(_DOMAIN))
    if version != _VERSION:
        raise EnvelopeError("unsupported envelope version")
    _sizes(origin_size, trace_size, body_size, total, limits)
    if not hmac.compare_digest(_tag(key, memoryview(envelope)[:-_TAG_BYTES]),
                               envelope[-_TAG_BYTES:]):
        raise EnvelopeError("envelope authentication failed")
    start = len(_DOMAIN) + _HEADER.size
    origin_end = start + origin_size
    trace_end = origin_end + trace_size
    origin = envelope[start:origin_end]
    input_trace = envelope[origin_end:trace_end]
    body = envelope[trace_end:-_TAG_BYTES]
    record = _record(origin=origin, input_trace=input_trace, body=body, expected=expected,
                     expected_origin=expected_origin, expected_events=expected_events,
                     limits=limits, interfaces=profiles)
    return AuthenticatedEnvelope(origin, input_trace, body, record)
