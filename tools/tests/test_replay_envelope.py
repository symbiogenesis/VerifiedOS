# SPDX-License-Identifier: Apache-2.0
"""Host authentication evidence, with synthetic bodies and no device claims."""

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import fields, replace
from functools import partial
from typing import cast
from unittest.mock import patch

from tests.harness import Case, ensure
from vos import replay_envelope as envelope
from vos.jsonc import Json
from vos.replay_record import Binding, Interface, RecordError

_KEY = bytes(range(32))  # Published development fixture, never a device secret.
_ORIGIN = b"development reset epoch\x00\x01"
_TRACE = b"public fixture input\x00\xff\n"
_INTERFACE = "a" * 64
_PROFILES = {_INTERFACE: Interface("time_read", 8)}
_BINDING = Binding("001122", "b" * 64, hashlib.sha256(_TRACE).hexdigest())
_LIMITS = envelope.EnvelopeLimits(16_384, 128, 256, 8_192, 4)


def _body(binding: Binding = _BINDING, *, count: int = 1) -> bytes:
    # This endpoint and its bytes are synthetic; the envelope has no authority
    # to certify a real time service's precision or an entropy commitment seal.
    value: Json = {
        "schema": "replay-record-v1",
        "binding": {"base_image_root": binding.base_image_root,
                    "composition": binding.composition, "input_trace": binding.input_trace},
        "events": [{"seq": i, "source": "time_read", "interface": _INTERFACE,
                    "point": {"slot": 0, "core": 0, "retire": 0, "ordinal": i},
                    "payload": {"value": "0001ff"}} for i in range(count)],
    }
    # Whitespace and the final newline must survive authentication unchanged.
    return (json.dumps(value, indent=1) + "\n").encode()


_BODY = _body()
_create = partial(envelope.create, key=_KEY, origin=_ORIGIN, input_trace=_TRACE,
                  body=_BODY, expected=_BINDING, expected_origin=_ORIGIN,
                  expected_events=1, limits=_LIMITS, interfaces=_PROFILES)
_verify = partial(envelope.verify, key=_KEY, expected=_BINDING, expected_origin=_ORIGIN,
                  expected_events=1, limits=_LIMITS, interfaces=_PROFILES)


def _oracle_mac(key: bytes, message: bytes) -> bytes:
    """RFC 2104 construction independent of the implementation's hmac API.

    Only the SHA-256 primitive is shared. RFC 4231 validates this test oracle;
    the complete-message framing below does not import implementation constants.
    """
    if len(key) > 64:
        key = hashlib.sha256(key).digest()
    block = key.ljust(64, b"\x00")
    inner = bytes(value ^ 0x36 for value in block)
    outer = bytes(value ^ 0x5c for value in block)
    return hashlib.sha256(outer + hashlib.sha256(inner + message).digest()).digest()


def _wire(*, key: bytes = _KEY, origin: bytes = _ORIGIN, trace: bytes = _TRACE,
          body: bytes = _BODY, version: int = 1) -> bytes:
    message = b"VerifiedOS host replay envelope\x00" + bytes([version])
    for item in (origin, trace, body):
        message += len(item).to_bytes(8, "big")
    message += origin + trace + body
    return message + _oracle_mac(key, message)


def _refused(fn: Callable[[], object]) -> None:
    try:
        fn()
    except envelope.EnvelopeError:
        return
    raise AssertionError("invalid host envelope or parameters were accepted")


def _published_vectors() -> None:
    # RFC 4231 section 4.7, https://www.rfc-editor.org/rfc/rfc4231.html.
    # The provenance and distinct IETF terms are recorded in THIRD-PARTY.md.
    key = b"\xaa" * 131
    vectors = (
        (b"Test Using Larger Than Block-Size Key - Hash Key First",
         "60e431591ee0b67f0d8a26aacbf5b77f8e0bc6213728c5140546040f0ee37f54"),
    )
    for message, wanted in vectors:
        ensure(envelope._tag(key, message).hex() == wanted, "HMAC known answer differs")
        ensure(_oracle_mac(key, message).hex() == wanted, "independent HMAC oracle differs")


def _round_trip_and_independent_wire() -> None:
    encoded = _create()
    ensure(encoded == _wire(), "complete wire differs from independent framing and MAC")
    for value in (encoded, _wire()):
        result = _verify(value)
        ensure((result.origin, result.input_trace, result.body) == (_ORIGIN, _TRACE, _BODY),
               "authenticated bytes were changed")
        ensure(result.record.binding == _BINDING, "decoded binding differs")
        ensure(result.record.events[0].payload == b"\x00\x01\xff", "decoded bytes differ")
        ensure(tuple(field.name for field in fields(result)) ==
               ("origin", "input_trace", "body", "record"), "result carries unexpected evidence")
        ensure(_KEY not in encoded, "serializer included the external fixture key")
    long_key = b"\xaa" * 131
    ensure(_create(key=long_key) == _wire(key=long_key), "long-key encoding differs")
    _verify(_wire(key=long_key), key=long_key)


def _every_byte_is_protected() -> None:
    value = _wire()
    for index in range(len(value)):
        damaged = value[:index] + bytes([value[index] ^ 1]) + value[index + 1:]
        _refused(partial(_verify, damaged))


def _authentication_precedes_decode() -> None:
    value = _wire()
    # The fixed framing is valid. Authentication must reject both payload and
    # tag corruption without parsing even an apparently well-formed JSON body.
    for damaged in (value[:-1] + bytes([value[-1] ^ 1]), _wire(key=b"x" * 32),
                    value[:-33] + bytes([value[-33] ^ 1]) + value[-32:]):
        with patch.object(envelope, "decode", side_effect=AssertionError("decoded before MAC")):
            _refused(partial(_verify, damaged))
    with patch.object(envelope, "decode", side_effect=RecordError("body reached")) as decoder:
        _refused(partial(_verify, value))
        ensure(decoder.call_count == 1, "authenticated body never reached structural validation")


def _keys_and_immutable_inputs() -> None:
    value = _wire()
    for key in (None, b"", b"k" * 31, bytearray(_KEY), memoryview(_KEY), "k" * 32):
        _refused(partial(_verify, value, key=cast(bytes, key)))
        _refused(partial(_create, key=cast(bytes, key)))
    _refused(partial(_verify, value, key=b"x" * 32))
    for field in ("origin", "input_trace", "body"):
        for invalid in (None, bytearray(b"data"), memoryview(b"data"), "data"):
            _refused(partial(_create, **{field: invalid}))
    for invalid in (None, bytearray(value), memoryview(value), "data"):
        _refused(partial(_verify, cast(bytes, cast(object, invalid))))
    for operation in (partial(_verify, value), _create):
        for origin in (None, b"", bytearray(_ORIGIN), memoryview(_ORIGIN), "origin"):
            _refused(partial(operation, expected_origin=cast(bytes, origin)))
    _refused(partial(_create, origin=b""))
    _refused(partial(_verify, _wire(origin=b"")))


def _independent_bindings() -> None:
    value = _wire()
    for binding in (replace(_BINDING, base_image_root="ff"),
                    replace(_BINDING, composition="c" * 64),
                    replace(_BINDING, input_trace="d" * 64)):
        _refused(partial(_verify, value, expected=binding))
        _refused(partial(_create, expected=binding))
        _refused(partial(_verify, _wire(body=_body(binding))))
        _refused(partial(_create, body=_body(binding)))
    for operation in (partial(_verify, value), _create):
        _refused(partial(operation, expected_origin=b"another epoch"))
        _refused(partial(operation, expected_events=0))
        _refused(partial(operation, expected_events=2))
    _refused(partial(_verify, _wire(origin=b"another epoch")))
    _refused(partial(_create, origin=b"another epoch"))
    _refused(partial(_verify, _wire(trace=b"other input")))
    _refused(partial(_create, input_trace=b"other input"))


def _framing_refusals() -> None:
    value = _wire()
    for length in range(len(value)):
        _refused(partial(_verify, value[:length]))
    for extra in (b"\x00", value, b"trailing"):
        _refused(partial(_verify, value + extra))
    for version in (0, 2, 255):
        _refused(partial(_verify, _wire(version=version)))
    # Independently reauthenticate malformed lengths, so MAC failure cannot
    # disguise a parser that trusts a length or accepts a trailing artifact.
    for offset in (33, 41, 49):
        for declared in (0, 1, (1 << 64) - 1):
            message = value[:-32]
            message = message[:offset] + declared.to_bytes(8, "big") + message[offset + 8:]
            _refused(partial(_verify, message + _oracle_mac(_KEY, message)))


def _external_parameters() -> None:
    value = _wire()
    for field in fields(_LIMITS):
        for invalid in (-1, True, 1.0, 1 << 64, "1024", None):
            changed = replace(_LIMITS, **{field.name: invalid})
            for operation in (partial(_verify, value), _create):
                _refused(partial(operation, limits=changed))
    for operation in (partial(_verify, value), _create):
        for count in (-1, True, 1.0, 1 << 64, None):
            _refused(partial(operation, expected_events=cast(int, count)))
        for binding in (None, "binding", replace(_BINDING, base_image_root=""),
                        replace(_BINDING, composition="B" * 64),
                        replace(_BINDING, input_trace="01")):
            _refused(partial(operation, expected=cast(Binding, binding)))
        _refused(partial(operation, limits=cast(envelope.EnvelopeLimits, cast(object, None))))
        for profiles in (None, [], {_INTERFACE: None},
                         {"short": Interface("time_read", 8)},
                         {_INTERFACE: Interface("unknown", 8)},
                         {_INTERFACE: Interface("time_read", True)},
                         {_INTERFACE: Interface("time_read", 0)}):
            _refused(partial(operation, interfaces=cast(Mapping[str, Interface], profiles)))


def _capacity_boundaries() -> None:
    value = _wire()
    exact = envelope.EnvelopeLimits(len(value), len(_ORIGIN), len(_TRACE), len(_BODY), 1)
    ensure(_create(limits=exact) == value, "exactly bounded creation refused")
    _verify(value, limits=exact)
    for field in fields(exact):
        capacity = cast(int, getattr(exact, field.name))
        smaller = replace(exact, **{field.name: capacity - 1})
        for operation in (partial(_verify, value), _create):
            with patch.object(envelope, "decode", side_effect=AssertionError("decoded over capacity")):
                _refused(partial(operation, limits=smaller))
        larger = replace(exact, **{field.name: capacity + 1})
        _verify(value, limits=larger)
        _create(limits=larger)
    for operation in (partial(_verify, value), _create):
        _refused(partial(operation, interfaces={_INTERFACE: Interface("time_read", 2)}))
        operation(interfaces={_INTERFACE: Interface("time_read", 3)})


def _authenticated_invalid_body() -> None:
    for body in (b"", b"not JSON", b"\xff", b"{}", _BODY + b"{}",
                 b"[" * 1_100 + b"0" + b"]" * 1_100,
                 _BODY.replace(b'"replay-record-v1"', b'"unknown"'),
                 _BODY.replace(b'"schema":', b'"schema":"replay-record-v1","schema":'),
                 _BODY.replace(b'"time_read"', b'"entropy"'),
                 _BODY.replace(b'"seq": 0', b'"seq": 1')):
        _refused(partial(_verify, _wire(body=body)))
        _refused(partial(_create, body=body))
    _refused(partial(_verify, _wire(), interfaces={}))
    _refused(partial(_create, interfaces={}))


def _explicit_empty_trace_and_window() -> None:
    binding = replace(_BINDING, input_trace=hashlib.sha256(b"").hexdigest())
    body = _body(binding, count=0)
    value = _wire(trace=b"", body=body)
    limits = envelope.EnvelopeLimits(len(value), len(_ORIGIN), 0, len(body), 0)
    ensure(_create(input_trace=b"", body=body, expected=binding,
                   expected_events=0, limits=limits) == value,
           "explicit empty data or zero-event window was lost")
    result = _verify(value, expected=binding, expected_events=0, limits=limits)
    ensure(result.input_trace == b"" and result.record.events == (), "empty window differs")
    _refused(partial(_create, input_trace=cast(bytes, cast(object, None)), body=body,
                     expected=binding, expected_events=0))


def cases() -> list[Case]:
    return [
        Case("published-vectors", _published_vectors),
        Case("round-trip-and-independent-wire", _round_trip_and_independent_wire),
        Case("every-byte-is-protected", _every_byte_is_protected),
        Case("authentication-precedes-decode", _authentication_precedes_decode),
        Case("keys-and-immutable-inputs", _keys_and_immutable_inputs),
        Case("independent-bindings", _independent_bindings),
        Case("framing-refusals", _framing_refusals),
        Case("external-parameters", _external_parameters),
        Case("capacity-boundaries", _capacity_boundaries),
        Case("authenticated-invalid-body", _authenticated_invalid_body),
        Case("explicit-empty-trace-and-window", _explicit_empty_trace_and_window),
    ]
