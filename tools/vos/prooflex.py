# SPDX-License-Identifier: Apache-2.0
"""Comment and string regions for proof-source readers with explicit policies.

This scanner only locates regions. Readers decide whether malformed input is a
refusal, and whether comments become separators or blanks at their source offsets.
The gate reads quoted strings inside comments; advisory navigation reads comment
delimiters there regardless of quotes. Neither policy is implicit.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

_DELIMITER = re.compile(r'\(\*|\*\)|"')


@dataclass(frozen=True)
class Region:
    """One outer comment, string or unmatched comment ending, at source offsets."""

    kind: Literal["comment", "string", "unmatched-end"]
    start: int
    end: int
    closed: bool


def _string_end(text: str, start: int) -> tuple[int, bool]:
    """Read a quoted string whole, including doubled quotes and unfinished tails."""
    at = start + 1
    while (quote := text.find('"', at)) >= 0:
        if text.startswith('"', quote + 1):
            at = quote + 2
        else:
            return quote + 1, True
    return len(text), False


def regions(text: str, *, strings_in_comments: bool) -> Iterator[Region]:
    """Locate nested comments and strings without deciding malformed-input policy.

    Unfinished regions extend to EOF. An unmatched `*)` is reported separately,
    allowing a tolerant reader to retain it and a strict reader to name its line.
    Ordinary source text is skipped by the regex engine rather than visited in
    Python; quoted delimiters never open or close a region outside comments.
    """
    depth = start = quoted_until = 0
    for token in _DELIMITER.finditer(text):
        if token.start() < quoted_until:
            continue
        delimiter = token.group()
        if delimiter == '"' and (not depth or strings_in_comments):
            quoted_until, closed = _string_end(text, token.start())
            if not depth:
                yield Region("string", token.start(), quoted_until, closed)
        elif delimiter == "(*":
            if not depth:
                start = token.start()
            depth += 1
        elif delimiter == "*)":
            if not depth:
                yield Region("unmatched-end", token.start(), token.end(), False)
            else:
                depth -= 1
                if not depth:
                    yield Region("comment", start, token.end(), True)
    if depth:
        yield Region("comment", start, len(text), False)
