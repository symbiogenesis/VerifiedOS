# SPDX-License-Identifier: Apache-2.0
"""Immutable diagnostic source identities and explicit source coordinate units."""

import hashlib
import json
from dataclasses import dataclass

from vos.vela_ast import MAX_SOURCE_BYTES

MAX_URI_BYTES = 4096


def _normalized(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


@dataclass(frozen=True)
class SourceSnapshot:
    uri: str
    version: int
    text: str
    generation: int

    def __post_init__(self) -> None:
        if not self.uri or len(self.uri.encode("utf-8")) > MAX_URI_BYTES:
            raise ValueError("document URI is empty or exceeds limit")
        if len(self.text.encode("utf-8")) > MAX_SOURCE_BYTES:
            raise ValueError("document exceeds pure prototype source limit")
        if (type(self.version) is not int or not -(2 ** 31) <= self.version < 2 ** 31
                or type(self.generation) is not int or self.generation < 1):
            raise ValueError("invalid document version or generation")

    @property
    def source(self) -> bytes:
        return self.text.encode("utf-8")

    @property
    def identity(self) -> str:
        fields = [self.uri, self.version, self.generation, self.text]
        return hashlib.sha256(json.dumps(fields, ensure_ascii=False).encode("utf-8")).hexdigest()

    def byte_position(self, offset: int) -> dict[str, int]:
        """Convert a UTF-8 boundary to LSP UTF-16, never an interior byte/CRLF."""
        source = self.source
        if type(offset) is not int or not 0 <= offset <= len(source):
            raise ValueError("source byte offset out of bounds")
        prefix = source[:offset].decode("utf-8")
        if prefix.endswith("\r") and source[offset:offset + 1] == b"\n":
            raise ValueError("source byte offset splits CRLF")
        lines = _normalized(prefix).split("\n")
        return {"line": len(lines) - 1, "character": _utf16_length(lines[-1])}

    def diagnostic_position(self, line: int, column: int) -> dict[str, int]:
        """Adapt the legacy producer's one-based normalized code-point site."""
        lines = _normalized(self.text).split("\n")
        if not 1 <= line <= len(lines) or not 1 <= column <= len(lines[line - 1]) + 1:
            raise ValueError("producer diagnostic outside source")
        return {"line": line - 1, "character": _utf16_length(lines[line - 1][:column - 1])}
