"""The apex statement's Vocabulary record, read once and shared.

proofs/ApexTheorem.v is the coverage checklist R-18-031(a) requires: every
side-property some seam consumes or concludes is a Prop field of the record, and a
field nothing instantiates is an uncovered obligation with exactly one name. Two
tools ask the same question of it. The checker holds docs/field-bindings.md against
the fields and their consumers; blast-radius.py answers what an edit re-opens.
Parsed twice they would be one fact restated by hand, which is the defect both tools
exist to catch, so the parse is here and neither carries a copy of it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

APEX = "proofs/ApexTheorem.v"

_COMMENT_RE = re.compile(r"(?s)\(\*(?:(?!\(\*|\*\)).)*\*\)")
_RECORD_RE = re.compile(r"(?s)Record Vocabulary : Type := \{(.*?)\}\.")
_PROP_FIELD_RE = re.compile(r"(?m)^\s*(\w+) : Prop\s*;?\s*$")
_ANY_FIELD_RE = re.compile(r"(?m)^\s*(\w+) : ([\w>< -]+?);?\s*$")
_DEFINITION_RE = re.compile(
    r"(?sm)^Definition (\w+)(.*?)(?=^(?:Definition|Lemma|Print|Record)\b|\Z)"
)
_FIELD_READ_RE = re.compile(r"v\.\((\w+)\)")


@dataclass
class ApexRecord:
    fields: list[str] = field(default_factory=list)          # Prop fields, in declaration order
    field_set: set[str] = field(default_factory=set)
    consumers: dict[str, list[str]] = field(default_factory=dict)   # field -> what touches it
    def_fields: dict[str, list[str]] = field(default_factory=dict)  # definition -> fields read


def read(path: Path) -> ApexRecord:
    raw = path.read_text(encoding="utf-8")

    # comments strip innermost-first, so nesting unwinds; each pass removes at least
    # one balanced comment until none is left to match
    while True:
        stripped = _COMMENT_RE.sub("", raw)
        if stripped == raw:
            break
        raw = stripped

    record = _RECORD_RE.search(raw)
    inner = record.group(1) if record else ""

    rec = ApexRecord()
    rec.fields = _PROP_FIELD_RE.findall(inner)
    rec.field_set = set(rec.fields)
    rec.consumers = {f: [] for f in rec.fields}

    # a coercion field whose type cites Prop fields consumes them
    for name, kind in _ANY_FIELD_RE.findall(inner):
        for word in re.findall(r"\w+", kind):
            if word in rec.field_set and word != name:
                rec.consumers[word].append(name)

    # every Definition consuming a field through the record value: v.(field), in body order
    for name, body in _DEFINITION_RE.findall(raw):
        reads: list[str] = []
        for f in _FIELD_READ_RE.findall(body):
            if f in rec.field_set and f not in reads:
                reads.append(f)
        if reads:
            rec.def_fields[name] = reads
            for f in reads:
                rec.consumers[f].append(name)

    return rec
