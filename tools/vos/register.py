# SPDX-License-Identifier: Apache-2.0
"""The register, and the artifacts whose rows other documents count.

Everything here is a parse, never a decision. A check reads these structures and
reports; nothing in this module reports anything, so what a rule decides is always
visible beside the rule rather than buried in a reader.
"""

import re
from dataclasses import dataclass, field

from .corpus import Corpus

REGISTER = "docs/requirements-register.md"
CROWN_JEWELS = "docs/crown-jewels.md"
ABSENCE_CONTRACT = "docs/absence-contract.md"
ISA_PROFILE = "docs/isa-profile.md"
COVERAGE_MATRIX = "docs/coverage-matrix.md"

REQ_TOKEN_RE = re.compile(r"R-\d\d-\d+[a-z]?")

_SECTION_RE = re.compile(r"^## §(\d+)")
_SUBSECTION_RE = re.compile(r"^### (\d+\.\d+) ")
_ENTRY_RE = re.compile(r"^\*\*(R-\d\d-\d+[a-z]?)\*\* (?:IS|MUST NOT|MUST)")
_CONFER_RE = re.compile(r"^· (Fail-closed|RoT-fresh):")
_CJ_TARGET_RE = re.compile(r"^\| `(CJ-[A-Z-]+)`")


@dataclass
class Register:
    """Every entry, where it sits, its body, and the lines it carries beneath it."""

    ids: list[str] = field(default_factory=list)
    id_set: set[str] = field(default_factory=set)
    cj_targets: list[str] = field(default_factory=list)
    subsection: dict[str, str | None] = field(default_factory=dict)   # id -> "15.4"
    body: dict[str, str] = field(default_factory=dict)                # id -> its entry line
    trace_of: dict[str, str] = field(default_factory=dict)            # id -> its · Trace: line
    per_section: dict[str, int] = field(default_factory=dict)         # section -> entry count
    confers: dict[str, dict[str, str]] = field(default_factory=dict)  # kind -> (id -> line)
    accepts: dict[str, int] = field(default_factory=dict)             # id -> · Accept: line count
    accept_text: dict[str, str] = field(default_factory=dict)         # id -> those lines, joined
    late_accept: list[str] = field(default_factory=list)              # criteria stated too late


def read_register(corpus: Corpus) -> Register:
    """One pass over the register.

    Every line kind this parse reads announces itself in its first character, so the
    dispatch below spends a pattern only on the few lines whose kind it could be.
    """
    reg = Register()
    section = subsec = current = entry = None
    saw_tail = False

    for line in corpus.by_name[REGISTER].lines:
        if not line:
            continue
        lead = line[0]

        if lead == "#":
            m = _SECTION_RE.match(line)
            if m:
                section, subsec = m.group(1), None
                reg.per_section.setdefault(section, 0)
                continue
            m = _SUBSECTION_RE.match(line)
            if m:
                subsec = m.group(1)

        elif lead == "*":
            m = _ENTRY_RE.match(line)
            if m:
                current = entry = m.group(1)
                saw_tail = False
                reg.ids.append(current)
                reg.subsection[current] = subsec
                reg.body[current] = line
                reg.accepts[current] = 0
                reg.accept_text[current] = ""
                if section:
                    reg.per_section[section] += 1

        elif lead == "·":
            if entry and line.startswith("· Accept:"):
                # criteria are conjunctive, and they come before the lines that follow
                # them: `entry` outlives the trace where `current` does not, so one
                # written below the trace is caught here rather than going uncounted
                reg.accepts[entry] += 1
                reg.accept_text[entry] += " " + line
                if saw_tail:
                    reg.late_accept.append(entry)
            elif current:
                m = _CONFER_RE.match(line)
                if m:
                    # a property line conferring membership in a set another entry collects
                    reg.confers.setdefault(m.group(1), {})[current] = line
                    saw_tail = True
                elif line.startswith("· Trace:"):
                    reg.trace_of[current] = line
                    current = None
                    saw_tail = True

        elif lead == "|":
            m = _CJ_TARGET_RE.match(line)
            if m:
                reg.cj_targets.append(m.group(1))

    reg.id_set = set(reg.ids)
    return reg


def cj_status(row: str) -> str:
    return row.split("|")[-2].strip()


def cj_class(row: str) -> str | None:
    """The status column is a closed vocabulary of three, and the counts are taken by
    reading it. A status spelled a fourth way is counted by none of them, so the ratio
    quietly stops summing to the inventory while each figure remains individually
    true. One classifier, and the rows it classifies as nothing are the finding."""
    s = cj_status(row).lower()
    if s.startswith("not authored"):
        return "unauthored"
    if s.startswith("partial"):
        return "partial"
    if "authored" in s:
        return "authored"
    return None


@dataclass
class Artifacts:
    """The counted tables other documents restate figures from."""

    cj_lines: list[str] = field(default_factory=list)
    cj_rows: list[str] = field(default_factory=list)
    absence_ids: list[str] = field(default_factory=list)
    csr_rows: dict[str, list[str]] = field(default_factory=dict)
    exclusion_rows: list[str] = field(default_factory=list)
    cm_bounds: list[str] = field(default_factory=list)
    cm_props: list[str] = field(default_factory=list)
    cm_cells: dict[str, str] = field(default_factory=dict)
    cm_twice: list[str] = field(default_factory=list)


# An absence row's id, letter suffix and all. The absence contract inserts between two
# rows the way the register inserts between two entries, `A-12a` sitting where its
# structure belongs rather than where its number would put it, so a pattern that stops
# at the digits reads one row fewer than the table has and every figure derived from it
# is short by that row while the rule reporting them stays green.
_ABSENCE_RE = re.compile(r"^\| \*\*(A-\d+[a-z]?)\*\*")
_CSR_SECTION_RE = re.compile(r"^### (5\.\d) ")
_EXCLUSION_SECTION_RE = re.compile(r"^## 6\. ")
# a table's header rule, which is the one `|` line that is not a row
_TABLE_RULE_RE = re.compile(r"^\|[\s\-:|]+\|$")
_CM_CELL_RE = re.compile(r"^\| `(B-\d\d)` \| `(P-\d)` \|")
_CM_BOUND_RE = re.compile(r"^\| `(B-\d\d)` \| [^`|]")
_CM_PROP_RE = re.compile(r"^\| `(P-\d)` \| [^`|]")


def read_artifacts(corpus: Corpus) -> Artifacts:
    art = Artifacts()

    cj = corpus.get(CROWN_JEWELS)
    if cj:
        art.cj_lines = cj.lines
        art.cj_rows = [ln for ln in cj.lines if re.match(r"^\| \d+ \|", ln)]

    absence = corpus.get(ABSENCE_CONTRACT)
    if absence:
        art.absence_ids = [
            m.group(1) for m in (_ABSENCE_RE.match(ln) for ln in absence.lines) if m
        ]

    # The profile's CSR bank, one bucket per §5.n table. The document declares the
    # shape the check reads: "Each row below cites the requirement that admits or
    # excludes it; a row citing none would be a defect in this view, not an
    # implementer's discretion".
    #
    # §6's exclusion table is read in the same pass and kept whole rather than split
    # into cells, because what a rule wants from a row differs by rule: the names it
    # excludes are in its first cell and the requirements it rests on in its last, and
    # a parse that decided which was which here would be deciding the rule's question.
    # Its rows are not filtered to `| \`` as the CSR bank's are: an exclusion's subject
    # is written as prose where it has no single spelling, so a row may open with a
    # bare word, and dropping those would silently shorten the table.
    profile = corpus.get(ISA_PROFILE)
    if profile:
        sec = None
        excluding = False
        for line in profile.lines:
            m = _CSR_SECTION_RE.match(line)
            if m:
                sec = m.group(1)
                art.csr_rows[sec] = []
            elif line.startswith("#"):
                sec = None
                excluding = bool(_EXCLUSION_SECTION_RE.match(line))
            elif sec and line.startswith("| `"):
                art.csr_rows[sec].append(line)
            elif (excluding and line.startswith("|")
                  and not _TABLE_RULE_RE.match(line)
                  and not line.startswith("| Excluded ")):
                art.exclusion_rows.append(line)

    # A definition row names one id and then prose; a matrix row names two ids. That
    # is the whole difference, so one pass reads all three.
    matrix = corpus.get(COVERAGE_MATRIX)
    if matrix:
        for line in matrix.lines:
            cell = _CM_CELL_RE.match(line)
            if cell:
                pair = f"{cell.group(1)} by {cell.group(2)}"
                if pair in art.cm_cells:
                    art.cm_twice.append(f"{pair} has more than one cell")
                art.cm_cells[pair] = line
                continue
            bound = _CM_BOUND_RE.match(line)
            if bound:
                art.cm_bounds.append(bound.group(1))
                continue
            prop = _CM_PROP_RE.match(line)
            if prop:
                art.cm_props.append(prop.group(1))

    return art
