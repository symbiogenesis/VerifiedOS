# SPDX-License-Identifier: Apache-2.0
"""Bounded length-framed UTF-8 JSON; message semantics belong to each protocol."""

import json
from typing import BinaryIO, cast

from vos.jsonutil import finite_float, unique_object

MAX_HEADER_BYTES = 8192
MAX_BODY_BYTES = 1_048_576
MAX_JSON_DEPTH = 64


class FrameError(ValueError):
    """The stream cannot safely continue at another frame boundary."""


class MessageError(ValueError):
    """Valid JSON that cannot represent one message object."""


def read_frame(stream: BinaryIO) -> bytes | None:
    headers: dict[str, str] = {}
    total = 0
    while True:
        line = stream.readline(MAX_HEADER_BYTES + 1 - total)
        if not line and total == 0:
            return None
        total += len(line)
        if total > MAX_HEADER_BYTES or not line.endswith(b"\r\n"):
            raise FrameError("truncated or oversized frame header")
        if line == b"\r\n":
            break
        try:
            name, separator, value = line[:-2].decode("ascii").partition(":")
        except UnicodeError as error:
            raise FrameError("non-ASCII frame header") from error
        name, value = name.lower(), value.strip()
        if not separator or not name or name in headers:
            raise FrameError("malformed or duplicate frame header")
        headers[name] = value
    length = headers.get("content-length", "")
    if not length.isascii() or not length.isdecimal() or len(length) > 8:
        raise FrameError("one decimal Content-Length is required")
    remaining = int(length)
    if remaining > MAX_BODY_BYTES:
        raise FrameError("frame body exceeds limit")
    content_type = headers.get("content-type", "").lower().replace(" ", "")
    if "charset=" in content_type and content_type.split("charset=", 1)[1] not in {"utf-8", "utf8"}:
        raise FrameError("only UTF-8 content is supported")
    chunks: list[bytes] = []
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise FrameError("truncated frame body")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _reject_constant(value: str) -> object:
    raise ValueError(f"non-finite JSON value: {value}")


def decode_message(raw: bytes) -> dict[str, object]:
    if len(raw) > MAX_BODY_BYTES:
        raise FrameError("frame body exceeds limit")
    quoted, escaped, depth = False, False, 0
    for byte in raw:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise FrameError("JSON nesting exceeds limit")
        elif byte in (93, 125):
            depth -= 1
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object,
                       parse_float=finite_float, parse_constant=_reject_constant)
    if not isinstance(value, dict):
        raise MessageError("one JSON object is required")
    return cast("dict[str, object]", value)


def encode_message(message: dict[str, object]) -> bytes:
    raw = json.dumps(message, ensure_ascii=False, allow_nan=False,
                     separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_BODY_BYTES:
        raise FrameError("reply exceeds limit")
    return f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii") + raw
