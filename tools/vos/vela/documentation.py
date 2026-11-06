# SPDX-License-Identifier: Apache-2.0
"""Source-bound triple-slash documentation for compiler-owned declaration sites."""

import re
from bisect import bisect_right
from dataclasses import dataclass
from typing import cast

from vos.vela.ast import Name, Site, source_text, trivia_end

MAX_DOCUMENTATION_BYTES = 8192


@dataclass(frozen=True)
class Documentation:
    text: str
    start: int
    end: int
    declaration: int

    def record(self) -> dict[str, object]:
        return {"text": self.text, "span": [self.start, self.end],
                "declaration": self.declaration}


class DocumentationSource:
    """Read comment trivia once, without finding declarations or resolving names."""

    def __init__(self, source: bytes) -> None:
        source_text(source)
        self.source = source
        self.starts = [0]
        self.ends: list[int] = []
        for match in re.finditer(rb"\r\n|\r|\n", source):
            self.ends.append(match.start())
            self.starts.append(match.end())
        self.ends.append(len(source))

    def offset(self, site: Site) -> int:
        if not 1 <= site.line <= len(self.starts) or site.column < 1:
            raise ValueError("documentation declaration site is outside source")
        start, end = self.starts[site.line - 1], self.ends[site.line - 1]
        line = self.source[start:end].decode("utf-8")
        if site.column > len(line) + 1:
            raise ValueError("documentation declaration column is outside source")
        return start + len(line[:site.column - 1].encode("utf-8"))

    def at(self, site: Site) -> Documentation | None:
        return self.at_offset(self.offset(site))

    def at_offset(self, declaration: int) -> Documentation | None:
        if type(declaration) is not int or not 0 <= declaration < len(self.source):
            raise ValueError("documentation declaration offset is outside source")
        index = bisect_right(self.starts, declaration) - 1
        if self.source[self.starts[index]:declaration].strip(b" \t"):
            return None
        if index == 0:
            return None
        last = index - 1
        first = last
        pieces: list[bytes] = []
        start = 0
        while first >= 0:
            line = self.source[self.starts[first]:self.ends[first]]
            trimmed = line.lstrip(b" \t")
            if not trimmed.startswith(b"///"):
                break
            start = self.starts[first] + len(line) - len(trimmed)
            content = trimmed[3:]
            pieces.append(content[1:] if content.startswith(b" ") else content)
            first -= 1
        if not pieces:
            return None
        text = b"\n".join(reversed(pieces))
        if len(text) > MAX_DOCUMENTATION_BYTES:
            raise ValueError(f"documentation exceeds {MAX_DOCUMENTATION_BYTES} UTF-8 bytes")
        return Documentation(text.decode("utf-8"), start, self.ends[last], declaration)

    def validate(self, value: object, name: Name, kind: str) -> str:
        """Check a comment witness against bytes and its compiler-selected name site.

        The bounded identifier prefix check binds the declaration anchor to that
        symbol. It supplies no parsing, type checking or name-resolution verdict.
        """
        if not isinstance(value, dict) or set(value) != {"text", "span", "declaration"}:
            raise ValueError("invalid documentation fact fields")
        record = cast("dict[str, object]", value)
        span, text, declaration = record["span"], record["text"], record["declaration"]
        if (not isinstance(span, list) or len(span) != 2
                or any(type(item) is not int for item in span)
                or not isinstance(text, str) or len(text.encode("utf-8")) > MAX_DOCUMENTATION_BYTES
                or type(declaration) is not int or kind not in {"function", "constant"}):
            raise ValueError("invalid documentation fact values")
        offset = declaration
        expected = self.at_offset(offset)
        if expected is None or expected.record() != record:
            raise ValueError("documentation differs from its source comment")
        target = self.offset(name.site)
        if not offset < target:
            raise ValueError("documentation declaration does not precede its name")
        # Comments may occur inside an already selected pure declaration prefix.
        # Only line-comment trivia exists in this executable subset.
        prefix = re.sub(rb"//[^\r\n]*", b"", self.source[offset:target])
        qualifier = rb"const\s+" if kind == "constant" else rb"(?:const\s+)?"
        if re.fullmatch(rb"public\s+" + qualifier + rb"(?:Nat|bool)\s+", prefix) is None:
            raise ValueError("documentation anchor does not belong to this declaration")
        suffix = trivia_end(self.source, target + len(name.text.encode("utf-8")))
        marker = b"=" if kind == "constant" else b"("
        if suffix < 0 or self.source[suffix:suffix + 1] != marker:
            raise ValueError("documentation declaration kind differs from source")
        return text
