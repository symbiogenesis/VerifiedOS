# SPDX-License-Identifier: Apache-2.0
"""The configuration dialect's scanner, held to its own two promises.

What `strip_comments` accepts is contractually what jsoncons accepts, and what
it returns is offset-preserving: `len(out) == len(in)` for every input, so a
parse error still points at the same place in the original text. The corner
inputs here are the ones a line-oriented pattern gets wrong: comment openers
inside strings, terminators that never come, and the lone slash at EOF.
"""

import json
import tempfile
from pathlib import Path
from typing import Final

from tests.harness import Case, ensure
from vos import jsonc

# (input, what json.loads makes of the stripped text, or None for no parse).
# Every entry is also held to length preservation, unterminated input included.
_CASES: Final[tuple[tuple[str, jsonc.Json | None], ...]] = (
    ('{"a": 1, // note\n"b": 2}', {"a": 1, "b": 2}),
    ('{"a": /* why */ 1}', {"a": 1}),
    ('/* multi\nline */ {"a": 1}', {"a": 1}),
    ('{"url": "http://x", "c": "/* not */"}', {"url": "http://x", "c": "/* not */"}),
    ('{"s": "a\\"b//c"}', {"s": 'a"b//c'}),
    ('{"a": [1, 2, /* tail */ ], }', {"a": [1, 2]}),
    ("[1, /* c */ ]", [1]),
    ('{"a": 1,\n}', {"a": 1}),
    ("/* /* */ 1", 1),          # not nested: the first */ closes
    ('{"a": 1 /* x', None),     # unterminated comment: blanked to the end
    ("/", None),                # a lone slash before EOF is data, by fallthrough
    ("{} /", None),
    ("", None),
)


def _dialect_corners() -> None:
    for text, want in _CASES:
        out = jsonc.strip_comments(text)
        try:
            got: jsonc.Json | None = json.loads(out)
        except ValueError:
            got = None
        ensure(got == want,
               f"strip_comments({text!r}) parses to {got!r}, expected {want!r}")


def _offset_preservation() -> None:
    # The whole battery, the unterminated-comment branch included: that one used
    # to append a terminator that was never there and come out one char long.
    for text, _ in _CASES:
        out = jsonc.strip_comments(text)
        ensure(len(out) == len(text),
               f"strip_comments({text!r}) returned {len(out)} chars for "
               f"{len(text)}: parse-error offsets no longer point home")


def _newlines_survive_blanking() -> None:
    # A blanked comment keeps its newlines, so line/column in a parse error
    # still count the original text.
    out = jsonc.strip_comments('/* a\nb */ {"x": 1}')
    ensure(out.count("\n") == 1 and out.index("\n") == 4,
           f"the newline inside a blanked block comment moved: {out!r}")
    out = jsonc.strip_comments('// note\n{"x": 1}')
    ensure(out.startswith("       \n"),
           f"a line comment must blank to spaces up to its newline: {out!r}")


def _load_reads_the_dialect() -> None:
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        path = Path(td) / "c.json"
        path.write_text('{\n  "a": 1, // note\n  "b": [2, /* c */ ],\n}\n',
                        encoding="utf-8")
        ensure(jsonc.load(path) == {"a": 1, "b": [2]},
               "load must decode the dialect the model's own reader accepts")


def cases() -> list[Case]:
    return [
        Case("dialect-corners", _dialect_corners),
        Case("offset-preservation", _offset_preservation),
        Case("newlines-survive-blanking", _newlines_survive_blanking),
        Case("load-reads-the-dialect", _load_reads_the_dialect),
    ]
