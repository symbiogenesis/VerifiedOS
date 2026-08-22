# SPDX-License-Identifier: Apache-2.0
"""The model's configuration dialect: JSON with comments and trailing commas.

The Sail model's configuration files are read by jsoncons, which accepts `//` and
`/* */` comments and a comma before a closing brace or bracket; Python's `json` accepts
none of the three. The tools that read the configuration read the same files the model
reads, so what they accept is what jsoncons accepts: a tool that refuses a file the
model loads is a tool that gets switched off.

The dialect is defined once here rather than approximated wherever it is needed. The
scanner is string-aware, because a `//` inside a quoted value is data rather than the
start of a comment and a line-oriented pattern cannot tell the difference. Comments and
dropped commas are replaced by whitespace, so an offset in a parse error still points
at the same place in the original text.
"""

import json
from pathlib import Path
from typing import cast

# Anything a parse of this dialect can yield. Recursive, because the configuration is,
# and stated here rather than in each reader so that a walk over a config and a walk
# over a schema are the same walk over the same type.
type Json = dict[str, Json] | list[Json] | str | int | float | bool | None


def strip_comments(text: str) -> str:
    out: list[str] = []
    i, n = 0, len(text)
    in_string = False
    while i < n:
        c = text[i]
        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
        elif c == '"':
            in_string = True
            out.append(c)
            i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "/":
            while i < n and text[i] != "\n":
                out.append(" ")
                i += 1
        elif c == "/" and i + 1 < n and text[i + 1] == "*":
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
            if i + 1 < n:
                out.append("  ")
                i += 2
            else:
                # an unterminated comment runs to the end of the text, so its last
                # character is blanked like the rest rather than paired with a `*/`
                # that is not there: `len(out) == len(text)` holds for every input,
                # and the parse error json.loads still raises points where it should
                out.append("\n" if text[i] == "\n" else " ")
                i += 1
        else:
            # a comma left dangling by a deleted entry: the closing brace is the only
            # place it can be seen, and only whitespace and comments can sit between
            if c in "}]":
                j = len(out) - 1
                while j >= 0 and out[j].isspace():
                    j -= 1
                if j >= 0 and out[j] == ",":
                    out[j] = " "
            out.append(c)
            i += 1
    return "".join(out)


def load(path: str | Path) -> Json:
    # `json.loads` is typed `Any`, and `Json` is by construction everything it can
    # return, so this narrows an untyped boundary rather than asserting past one.
    return cast("Json", json.loads(strip_comments(Path(path).read_text(encoding="utf-8"))))
