"""Read the model's configuration dialect: JSON with comments and trailing commas.

The Sail model's configuration files are read by jsoncons, which accepts `//` and
`/* */` comments and a comma before a closing brace or bracket; Python's `json`
accepts none of the three. Both tools/config-keys.py and tools/validate-config.py
read the same files the model reads, so what they accept is what jsoncons accepts:
a tool that refuses a file the model loads is a tool that gets switched off.

The dialect is defined once here rather than approximated twice. The scanner is
string-aware, because a `//` inside a quoted value is data rather than the start of
a comment and a line-oriented regex cannot tell the difference. Comments and dropped
commas are replaced by whitespace, so an offset in a parse error still points at the
same place in the original text.
"""

import json


def strip_comments(text):
    out = []
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
            out.append("  ")
            i += 2
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


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.loads(strip_comments(f.read()))
