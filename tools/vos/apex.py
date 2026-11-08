# SPDX-License-Identifier: Apache-2.0
"""Lexical parser for [ApexTheorem.v's `Vocabulary`](../../proofs/ApexTheorem.v#Vocabulary) record and its consumers.

Shared by [field-bindings.md](../../docs/assurance/field-bindings.md) checks (K-42..K-44)
and [`run.py blast`](cli/blast.py). Parses every top-level declaration in `Vocabulary`
and cross-checks explicit record projections (`v.(f)`) against bare field-name mentions
in `Definition` bodies, reporting any unparsed declaration or mismatch in `unread`.
"""

import re
from bisect import bisect_left
from dataclasses import dataclass, field
from pathlib import Path

from vos.proofs import CONTROL_PREFIXES, sentence_ends, strip_comments, void_flag

APEX = "proofs/ApexTheorem.v"
PROP = "Prop"

_RECORD_OPEN_RE = re.compile(r"Record\s+Vocabulary\s*:\s*Type\s*:=\s*\{")
_BRACE_RE = re.compile(r"[{}]")

_DELIM_RE = re.compile(r"[;(){}\[\]]")
_OPENERS = "({["
_CLOSERS = ")}]"

_DECL_RE = re.compile(r"(?s)^\s*(\w+)\s*:\s*(\S.*?)\s*$")
_WORD_RE = re.compile(r"\w+")

_DEFINITION_RE = re.compile(r"(?m)^" + CONTROL_PREFIXES + r"Definition\s+(\w+)")
_DEFINITION_HEAD_RE = re.compile(r"(?<![\w'])Definition(?![\w'])")

# Reject record-update syntax (`{| v with f := x |}`), which implicitly reads unnamed fields.
_WITH_RE = re.compile(r"(?<![\w'])with(?![\w'])")
_MATCH_RE = re.compile(r"(?<![\w'])match(?![\w'])")

_FIELD_READ_RE = re.compile(r"\w+\.\((\w+)\)")
_ASSIGNED_RE = re.compile(r"\b(\w+)\s*:=")


@dataclass
class ApexRecord:
    fields: list[str] = field(default_factory=list)          # Prop fields in declaration order
    field_set: set[str] = field(default_factory=set)
    consumers: dict[str, list[str]] = field(default_factory=dict)   # field -> consumer names
    def_fields: dict[str, list[str]] = field(default_factory=dict)  # definition -> fields read
    declarations: int = 0
    unread: list[str] = field(default_factory=list)


def _body(raw: str) -> str | None:
    """Return the brace-matched body of `Record Vocabulary : Type := { ... }`, or `None`."""
    opened = _RECORD_OPEN_RE.search(raw)
    if opened is None:
        return None
    depth = 1
    for brace in _BRACE_RE.finditer(raw, opened.end()):
        depth += 1 if brace.group() == "{" else -1
        if depth == 0:
            return raw[opened.end():brace.start()]
    return None


def _split(inner: str) -> list[str]:
    """Split `inner` at top-level `;` delimiters outside brackets."""
    out: list[str] = []
    depth = start = 0
    for delim in _DELIM_RE.finditer(inner):
        char = delim.group()
        if char in _OPENERS:
            depth += 1
        elif char in _CLOSERS:
            depth -= 1
        elif not depth:
            out.append(inner[start:delim.start()])
            start = delim.end()
    out.append(inner[start:])
    return [piece for piece in out if piece.strip()]


def _quote(piece: str) -> str:
    """Flatten whitespace in `piece` and truncate to 60 characters for diagnostics."""
    flat = " ".join(piece.split())
    return flat if len(flat) <= 60 else flat[:57] + "..."


def read(path: Path) -> ApexRecord:
    """Parse `Vocabulary` fields and their consumers from `path` (`proofs/ApexTheorem.v`)."""
    raw = strip_comments(path.read_text(encoding="utf-8"))
    ends = sentence_ends(raw)

    rec = ApexRecord()
    inner = _body(raw)
    if inner is None:
        rec.unread.append(
            "the file states no `Record Vocabulary : Type := { ... }` this parse can "
            "read, so nothing here names a Prop field of the statement")
        inner = ""

    pieces = _split(inner)
    rec.declarations = len(pieces)
    declared: list[tuple[str, str]] = []
    for piece in pieces:
        m = _DECL_RE.match(piece)
        if m is None:
            rec.unread.append(
                f"the record declaration '{_quote(piece)}' is in no `name : type` "
                "form, so whatever it declares carries no name here")
            continue
        declared.append((m.group(1), " ".join(m.group(2).split())))

    rec.fields = [name for name, kind in declared if kind == PROP]
    rec.field_set = set(rec.fields)
    rec.consumers = {f: [] for f in rec.fields}

    # Record fields whose types reference `Prop` fields act as coercion consumers.
    for name, kind in declared:
        for word in _WORD_RE.findall(kind):
            if word in rec.field_set and word != name:
                rec.consumers[word].append(name)

    definitions: list[tuple[str, str]] = []
    read_to = 0
    for found in _DEFINITION_RE.finditer(raw):
        if found.start() < read_to:
            continue
        stop = bisect_left(ends, found.end())
        read_to = ends[stop] + 1 if stop < len(ends) else len(raw)
        if void_flag(raw, found.start(), ends) is None:
            definitions.append((found.group(1), raw[found.end():read_to]))
    spelled = len(_DEFINITION_HEAD_RE.findall(raw))
    if len(definitions) < spelled:
        rec.unread.append(
            f"the file spells {spelled} `Definition` sentences and this parse reads "
            f"{len(definitions)}, so what the rest consume is counted nowhere")
    for name, body in definitions:
        withs, matches = len(_WITH_RE.findall(body)), len(_MATCH_RE.findall(body))
        if withs > matches:
            rec.unread.append(
                f"the definition '{name}' writes {withs} `with` where its `match` "
                f"account for {matches}, so a record value in it may be completed from "
                "a base, which copies fields it never names, and this parse states no "
                "reading of what it consumes")
            continue
        reads: list[str] = []
        for f in _FIELD_READ_RE.findall(body):
            if f in rec.field_set and f not in reads:
                reads.append(f)
        assigned = {m.span(1) for m in _ASSIGNED_RE.finditer(body)}
        named = {m.group() for m in _WORD_RE.finditer(body)
                 if m.group() in rec.field_set and m.span() not in assigned}
        if named != set(reads):
            rec.unread.append(
                f"the definition '{name}' reads "
                f"{', '.join(reads) or 'no field'} through the record value and names "
                f"{', '.join(sorted(named)) or 'none'}, so what it consumes is two "
                "answers and this parse states neither")
        if reads:
            rec.def_fields[name] = reads
            for f in reads:
                rec.consumers[f].append(name)

    return rec
