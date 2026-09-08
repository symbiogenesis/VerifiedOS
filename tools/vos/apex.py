# SPDX-License-Identifier: Apache-2.0
"""The apex statement's Vocabulary record, read once and shared.

proofs/ApexTheorem.v is the coverage checklist R-18-031(a) requires: every
side-property some seam consumes or concludes is a Prop field of the record, and a
field nothing instantiates is an uncovered obligation with exactly one name. Two
tools ask the same question of it. The checker holds docs/field-bindings.md against
the fields and their consumers; blast-radius.py answers what an edit re-opens.
Parsed twice they would be one fact restated by hand, which is the defect both tools
exist to catch, so the parse is here and neither carries a copy of it.

**What this reads is what the source spells, which is why it is Python and not a
prover.** A record's field list and the field reads inside a definition body are
tokens the author wrote, not terms anything elaborates. `Compute` is conversion, and a
field name is not a term conversion reduces to, so an artifact printing its own field
names would be quoting its own syntax back through a reflection plugin: the same
lexical fact through a heavier machine, and an import into a file whose own prose says
it depends on nothing beyond the prelude. The assumption gate settles it in any case,
since `run.py proofs` reads the statement's compile output and holds every line that
is not `Closed under the global context` against the set R-05-164 makes empty, so a
`Compute` here fails R-05-163 rather than serving it. This runs on the host wave with
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
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

APEX = "proofs/ApexTheorem.v"

# The type that makes a declaration one of the checklist's obligations.
PROP = "Prop"

_COMMENT_RE = re.compile(r"(?s)\(\*(?:(?!\(\*|\*\)).)*\*\)")

# The record's opening, and then its body by brace depth. The lazy `\{(.*?)\}\.` this
# replaces ended at the first `}.` after the header, so a record that ever gained a
# brace inside it would have been truncated and every field past the truncation would
# have vanished with only the view's own rows left to notice.
_RECORD_OPEN_RE = re.compile(r"Record\s+Vocabulary\s*:\s*Type\s*:=\s*\{")
_BRACE_RE = re.compile(r"[{}]")

# The body's declarations, cut at every `;` outside a bracket. One C-level scan over
# the delimiters rather than a walk over the characters: the body is a couple of
# thousand characters and the delimiters are a few dozen.
_DELIM_RE = re.compile(r"[;(){}\[\]]")
_OPENERS = "({["
_CLOSERS = ")}]"

# One declaration, as the name it binds and the type it binds it at. Anything the
# record states that is not of that shape is `unread` rather than skipped.
_DECL_RE = re.compile(r"(?s)^\s*(\w+)\s*:\s*(\S.*?)\s*$")

# Every identifier a type mentions, for the coercion whose type cites the Prop fields
# it carries.
_WORD_RE = re.compile(r"\w+")

# A `Definition` sentence and its body. The body ends at a period that a sentence head
# follows, which is what a Gallina sentence boundary is, so no list of vernacular
# keywords stands between this and a file that grows one: the terminator this replaces
# named four of them, and a `Theorem` written between two definitions was swallowed by
# the definition above it and reported as that definition's own field reads.
_DEFINITION_RE = re.compile(r"(?sm)^Definition (\w+)(.*?\.)\s*(?=^[A-Z]\w*\b|\Z)")

# What a `Definition` sentence looks like from outside, for the count that says whether
# the pattern above read all of them. Indentation is admitted here and refused there on
# purpose, and that difference is the whole of what makes this a count rather than a
# restatement: a definition inside a `Module` or a `Section` is indented, the pattern
# above anchors at column 0, and a count anchored at column 0 too would have been the
# audited pattern spelling its own answer, unable to report the one shape it exists to
# catch. Counted wider than it is read, so an indented sentence is a residue and not a
# consumer nobody saw.
_DEFINITION_HEAD_RE = re.compile(r"(?m)^[ \t]*Definition\s")

# A field read through a record value, at whatever the definition calls its argument,
# and the second reading that holds the first honest. `v.(f)` is an abbreviation: `f v`
# applies the same projection and is equally legal Gallina, so a seam written that way
# consumes a field this pattern does not see, and the consumer cell is short with
# nothing to disagree with it. The two readings are held together rather than unioned,
# because the record constructions at the end of the statement name every field in
# assignment position and consume none of them, which a union would report as
# thirty-four consumers apiece; so an assignment is what the second reading discounts,
# and a body the two read differently is handed to the caller instead of answered.
#
# **What is discounted is the occurrence and never the name**, because one body does
# both: a record built from another record writes `f := f v`, assigning the field and
# consuming it in the same line. Subtracting the name would drop that read from the
# second reading, leave it absent from the first as well, and let the two agree on a
# body whose every consumer had just been lost, which is this file's silent failure
# wearing an assignment. Subtracting the position keeps the read and reports it.
_FIELD_READ_RE = re.compile(r"\w+\.\((\w+)\)")
_ASSIGNED_RE = re.compile(r"\b(\w+)\s*:=")


@dataclass
class ApexRecord:
    fields: list[str] = field(default_factory=list)          # Prop fields, in declaration order
    field_set: set[str] = field(default_factory=set)
    consumers: dict[str, list[str]] = field(default_factory=dict)   # field -> what touches it
    def_fields: dict[str, list[str]] = field(default_factory=dict)  # definition -> fields read
    declarations: int = 0          # every declaration the record makes, read or not
    # What the statement says and this parse could not read whole, in the record or in
    # a definition body, each worded for a caller that has to report it. Non-empty is a
    # finding and never a narrower answer: a declaration nobody can name is an
    # obligation nobody can bind, and a body nobody can read is a consumer cell held
    # against a set rather than against the statement.
    unread: list[str] = field(default_factory=list)


def _strip_comments(raw: str) -> str:
    """The source with its comments gone, nesting and all.

    Innermost-first, so nesting unwinds: each pass removes at least one balanced
    comment until none is left to match.
    """
    while True:
        stripped = _COMMENT_RE.sub("", raw)
        if stripped == raw:
            return raw
        raw = stripped


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
    raw = _strip_comments(path.read_text(encoding="utf-8"))

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

    # every Definition consuming a field through the record value, in body order
    definitions = _DEFINITION_RE.findall(raw)
    spelled = len(_DEFINITION_HEAD_RE.findall(raw))
    if len(definitions) < spelled:
        rec.unread.append(
            f"the file spells {spelled} `Definition` sentences and this parse reads "
            f"{len(definitions)}, so what the rest consume is counted nowhere")
    for name, body in definitions:
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
