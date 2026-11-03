# SPDX-License-Identifier: Apache-2.0
"""The apex statement's Vocabulary record, read once and shared.

[ApexTheorem.v's Vocabulary](../../proofs/ApexTheorem.v#Vocabulary)
is the coverage checklist R-18-031(a) requires: every
side-property some seam consumes or concludes is a Prop field of the record, and a
field nothing instantiates is an uncovered obligation with exactly one name. Two
tools ask the same question of it. The checker holds
[field-bindings.md](../../docs/assurance/field-bindings.md) against the fields
and their consumers; [the blast command](cli/blast.py) answers what an edit re-opens.
Parsed twice they would be one fact restated by hand, which is the defect both tools
exist to catch, so the parse is here and neither carries a copy of it.

**What this reads is what the source spells, which is why it is Python and not a
prover.** A record's field list and the field reads inside a definition body are
tokens the author wrote, not terms anything elaborates. `Compute` is conversion, and a
field name is not a term conversion reduces to, so an artifact printing its own field
names would be quoting its own syntax back through a reflection plugin: the same
lexical fact through a heavier machine, and an import into a file whose own prose says
it depends on nothing beyond the prelude. The proof gate independently inventories
compiled constants and audits their assumptions; source-authored print commands
do not decide its verdict. This lexical analysis runs on the host wave with
no toolchain in reach instead, which is what lets K-42, K-43 and K-44 be decided by the
push workflow on a runner with no Rocq and no submodule. What a term *means* is the
guest lane's, and `run.py proofs` is where it is asked.

**The parse is total over what the record declares, and that is the shape rather
than a flourish.** The failure this file must not have is the quiet one: a field
added to the record that the reader does not match is an obligation with no name at
all, and no floor sees it, because a floor counts members and the count is merely one
short. So the body is cut at every top-level `;` and every piece is read, a piece
that will not read is handed back in `unread` for the caller to report, and which
pieces are Prop fields falls out of the types rather than out of a second pattern
that could disagree with the first. The same reasoning fixes the two anchors that
used to decide by spelling: the body is found by matching braces rather than by a
lazy `}.`, which a brace inside the record would have ended early, and a field read
is `<anything>.(field)` rather than `v.(field)`, so a definition that names its
record argument something else is read instead of silently contributing nothing.

**The consumer half is read twice and the two readings are held together.** The same
quiet failure has a second shape on this side: `v.(f)` abbreviates the projection `f`
applied to `v`, so a seam written `f v` consumes the field in Gallina and not in any
scan for the abbreviation, which leaves one consumer cell short and the view agreeing
with it. So each body is also read for the field names it mentions outside an
assignment, and a body whose two readings differ is `unread` rather than answered from
whichever is longer. Both callers refuse on a non-empty `unread`, which is the only
answer available: a parse that cannot say what a body consumes cannot narrow the
answer to what it happened to see.

**Two spellings Rocq admits are read or refused, never skipped.** A definition under a
decoration, `#[local] Definition` or `Time Definition`, is the same body and is read as
one, over the decoration grammar and the comment lexing the shared lexer writes once
for every reader ([proofs.py](proofs.py)); a count taken wider than the reading makes a
definition under `Fail` or `Succeed`, on its line or on one above it, a residue rather
than a definition nobody saw, the flag keeping nothing it states. A record value
completed from a base, `{| v with f := x |}`, consumes by projection every field it does
not assign and names none of them, so a body that may carry one is `unread` rather than
answered from the fields it happens to spell.
"""

import re
from bisect import bisect_left
from dataclasses import dataclass, field
from pathlib import Path

from vos.proofs import CONTROL_PREFIXES, sentence_ends, strip_comments, void_flag

APEX = "proofs/ApexTheorem.v"

# The type that makes a declaration one of the checklist's obligations.
PROP = "Prop"

# Locate the header, then match braces so nested braces cannot truncate the record.
_RECORD_OPEN_RE = re.compile(r"Record\s+Vocabulary\s*:\s*Type\s*:=\s*\{")
_BRACE_RE = re.compile(r"[{}]")

# Split declarations at semicolons outside brackets, scanning only delimiters.
_DELIM_RE = re.compile(r"[;(){}\[\]]")
_OPENERS = "({["
_CLOSERS = ")}]"

# One declaration, as the name it binds and the type it binds it at. Anything the
# record states that is not of that shape is `unread` rather than skipped.
_DECL_RE = re.compile(r"(?s)^\s*(\w+)\s*:\s*(\S.*?)\s*$")

# Every identifier a type mentions, for the coercion whose type cites the Prop fields
# it carries.
_WORD_RE = re.compile(r"\w+")

# Accept the shared lexer's Definition prefixes. proofs.void_flag rejects Fail
# and Succeed, including flags on preceding lines, leaving an unread declaration.
# proofs.sentence_ends finds each body's terminator while respecting strings.
_DEFINITION_RE = re.compile(r"(?m)^" + CONTROL_PREFIXES + r"Definition\s+(\w+)")

# Count Definition keywords independently of the supported header grammar.
# A count mismatch exposes unsupported or rejected declarations as unread.
_DEFINITION_HEAD_RE = re.compile(r"(?<![\w'])Definition(?![\w'])")

# Record updates such as `{| v with f := x |}` implicitly read unnamed fields.
# Reject bodies with more `with` than `match` tokens; neither field scan can
# enumerate those implicit reads.
_WITH_RE = re.compile(r"(?<![\w'])with(?![\w'])")
_MATCH_RE = re.compile(r"(?<![\w'])match(?![\w'])")

# Compare explicit projections (`v.(f)`) with field-name occurrences outside
# assignments. Bare applications (`f v`) can expose reads the first scan misses.
# Treat any disagreement as unread rather than silently omitting a consumer.
# Exclude assignment occurrences, not names: `f := f v` still reads f on the right.
_FIELD_READ_RE = re.compile(r"\w+\.\((\w+)\)")
_ASSIGNED_RE = re.compile(r"\b(\w+)\s*:=")


@dataclass
class ApexRecord:
    fields: list[str] = field(default_factory=list)          # Prop fields, in declaration order
    field_set: set[str] = field(default_factory=set)
    consumers: dict[str, list[str]] = field(default_factory=dict)   # field -> what touches it
    def_fields: dict[str, list[str]] = field(default_factory=dict)  # definition -> fields read
    declarations: int = 0          # every declaration the record makes, read or not
    # Unparsed declarations or bodies, with diagnostics for the caller. A nonempty
    # list requires a finding; a partial parse cannot establish complete coverage.
    unread: list[str] = field(default_factory=list)


def _body(raw: str) -> str | None:
    """The Vocabulary record's body, or None where the record is not there to read.

    Brace-matched rather than lazily terminated, so the answer is the record's whole
    body or nothing at all, and never a prefix of it.
    """
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
    """The record body cut at every `;` that is not inside a bracket.

    The last declaration carries no separator, so the tail is a piece like the rest;
    an empty piece is the trailing `;` some records write and is not one.
    """
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
    """One declaration as a finding names it: whitespace flattened and cut short."""
    flat = " ".join(piece.split())
    return flat if len(flat) <= 60 else flat[:57] + "..."


def read(path: Path) -> ApexRecord:
    # Comments as Rocq's lexer reads them: nested, a string inside one read whole, and
    # each a separator, so `Local(* c *)Definition` is the decorated definition it is.
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

    # a field whose type cites Prop fields consumes them, which is what a coercion is
    for name, kind in declared:
        for word in _WORD_RE.findall(kind):
            if word in rec.field_set and word != name:
                rec.consumers[word].append(name)

    # every Definition consuming a field through the record value, in body order, and
    # none that a control flag on its line or above it keeps nothing of; a head opening
    # inside the body above, on a line of a string there, is no head
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
