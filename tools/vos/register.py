# SPDX-License-Identifier: Apache-2.0
"""Parse [docs/requirements-register.md](../../docs/requirements-register.md) and counted companion tables."""

import re
from dataclasses import dataclass, field

from .corpus import Corpus

REGISTER = "docs/requirements-register.md"
CROWN_JEWELS = "docs/assurance/crown-jewels.md"
ABSENCE_CONTRACT = "docs/hardware/absence-contract.md"
ISA_PROFILE = "docs/hardware/isa-profile.md"
COVERAGE_MATRIX = "docs/assurance/coverage-matrix.md"

# Alphabetic suffixes can grow without renumbering permanent requirement IDs.
# Numeric -n suffixes belong to repeated prose bookmarks, never to an ID.
REQ_ID_PATTERN = r"R-\d\d-\d+[a-z]*"
REQ_TOKEN_RE = re.compile(REQ_ID_PATTERN)

_SECTION_RE = re.compile(r"^## §(\d+)")
_SUBSECTION_RE = re.compile(r"^### (\d+\.\d+) ")
_ENTRY_RE = re.compile(rf"^\*\*({REQ_ID_PATTERN})\*\* (?:IS|MUST NOT|MUST)")
_CONFER_RE = re.compile(r"^· (Fail-closed|RoT-fresh):")
_CJ_TARGET_RE = re.compile(r"^\| `(CJ-[A-Z-]+)`")


@dataclass
class Register:
    """Parsed requirement entries, section counts, conferrals, and traces."""

    ids: list[str] = field(default_factory=list)
    id_set: set[str] = field(default_factory=set)
    cj_targets: list[str] = field(default_factory=list)
    subsection: dict[str, str | None] = field(default_factory=dict)   # id -> "15.4"
    body: dict[str, str] = field(default_factory=dict)                # id -> entry line
    trace_of: dict[str, str] = field(default_factory=dict)            # id -> · Trace: line
    per_section: dict[str, int] = field(default_factory=dict)         # section -> entry count
    confers: dict[str, dict[str, str]] = field(default_factory=dict)  # kind -> (id -> line)
    accepts: dict[str, int] = field(default_factory=dict)             # id -> · Accept: line count
    accept_text: dict[str, str] = field(default_factory=dict)         # id -> joined accept lines
    late_accept: list[str] = field(default_factory=list)              # criteria after conferral/trace


def read_register(corpus: Corpus) -> Register:
    """Parse `docs/requirements-register.md` in a single pass."""
    reg = Register()
    section = subsec = current = entry = None
    saw_tail = False

    document = corpus.by_name[REGISTER]
    for i, line in enumerate(document.lines):
        if not line or document.fenced[i]:
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
                if bool(section):
                    reg.per_section[section] += 1

        elif lead == "·":
            if bool(entry) and line.startswith("· Accept:"):
                # `entry` remains set after `· Trace:` clears `current`, so acceptance
                # criteria placed after a conferral or trace line are recorded in `late_accept`.
                reg.accepts[entry] += 1
                reg.accept_text[entry] += " " + line
                if saw_tail:
                    reg.late_accept.append(entry)
            elif bool(current):
                m = _CONFER_RE.match(line)
                if m:
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
    """Classify a crown-jewel status cell into `unauthored`, `partial`, `authored`, or `None`."""
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
    """Counted tables from crown jewels, absence contract, ISA profile, and coverage matrix."""

    cj_lines: list[str] = field(default_factory=list)
    cj_rows: list[str] = field(default_factory=list)
    absence_ids: list[str] = field(default_factory=list)
    csr_rows: dict[str, list[str]] = field(default_factory=dict)
    exclusion_rows: list[str] = field(default_factory=list)
    cm_bounds: list[str] = field(default_factory=list)
    cm_props: list[str] = field(default_factory=list)
    cm_cells: dict[str, str] = field(default_factory=dict)
    cm_twice: list[str] = field(default_factory=list)


_ABSENCE_RE = re.compile(r"^\| \*\*(A-\d+[a-z]?)\*\*")
_CSR_SECTION_RE = re.compile(r"^### (5\.\d) ")
_EXCLUSION_SECTION_RE = re.compile(r"^## 6\. ")
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

    # Collect CSR bank rows per §5.n table and §6 exclusion rows from `isa-profile.md`.
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
            elif bool(sec) and line.startswith("| `"):
                art.csr_rows[sec].append(line)
            elif (excluding and line.startswith("|")
                  and not _TABLE_RULE_RE.match(line)
                  and not line.startswith("| Excluded ")):
                art.exclusion_rows.append(line)

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
