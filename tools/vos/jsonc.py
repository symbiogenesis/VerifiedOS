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
import re
from pathlib import Path
from typing import cast

# Anything a parse of this dialect can yield. Recursive, because the configuration is,
# and stated here rather than in each reader so that a walk over a config and a walk
# over a schema are the same walk over the same type.
type Json = dict[str, Json] | list[Json] | str | int | float | bool | None


# Strings include an unterminated final token, so comment syntax inside one stays
# untouched and json.loads reports the original malformed string. Escapes consume
# exactly one following character, including a newline in invalid input.
_STRING = r'"[^"\\]*(?:\\[\s\S][^"\\]*)*(?:"|\\?$)'
_COMMENTS = re.compile(_STRING + r'|//[^\n]*|/\*(?:/|[\s\S]*?(?:\*/|$))')
_TRAILING_COMMAS = re.compile(_STRING + r'|,(?=\s*[}\]])')


def _blank_comment(match: re.Match[str]) -> str:
    token = match.group()
    return token if token.startswith('"') else "\n".join(" " * len(line) for line in token.split("\n"))


def strip_comments(text: str) -> str:
    """Blank comments and trailing commas while retaining every source offset."""
    uncommented = _COMMENTS.sub(_blank_comment, text)
    return _TRAILING_COMMAS.sub(lambda match: " " if match.group() == "," else match.group(),
                                uncommented)


def load(path: str | Path) -> Json:
    # `json.loads` is typed `Any`, and `Json` is by construction everything it can
    # return, so this narrows an untyped boundary rather than asserting past one.
    return cast("Json", json.loads(strip_comments(Path(path).read_text(encoding="utf-8"))))
