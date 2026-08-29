# SPDX-License-Identifier: Apache-2.0
"""provenance: the synthesis-configuration record, parsed once.

R-15-103 asks that an imported core's absences be bound to a build rather than to
a reading, and [rtl/synthesis-provenance.md](../../rtl/synthesis-provenance.md) is
the record that binds them. Two tools read it: the checker holds it against the
absence contract and against the configuration package, and `run.py rtl provenance` prints
it and elaborates against it. So the parse lives here and neither carries a copy,
which is the convention every other reading in this directory keeps.

**A binding is a list of settings or it is `n/a`, and there is no third form.** The
grammar is deliberately the smallest thing that can be checked: a cell is scanned
for backticked ``Name = value`` settings, and a cell yielding none must open with
`n/a` and then say why. A cell that yields neither is not a defective row to be
repaired, it is a row that binds an absence to nothing, which is the state the
record exists to make visible.

Nothing here decides whether a binding is *true*. Whether `BHTEntries = 0` in fact
removes the array is the elaborator's to report and this module's to leave alone;
what is decided here is that the row says something a build could be held to.
"""

import re
from dataclasses import dataclass
from pathlib import Path

RECORD = "rtl/synthesis-provenance.md"
CONFIG = "rtl/vos_c_class_config_pkg.sv"

# A setting inside a binding cell: `Name = value`, backticked so that a bare word
# in the prose beside it cannot be read as one.
SETTING_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z0-9_']+)`")

# The heading that opens each of the record's two tables. Located by number and
# by name together, so a renumbering that leaves the name is still found and a
# rename that leaves the number is a finding rather than a silent empty table.
_ABSENCE_HEADING = "## 2. The absences the contract enumerates"
_REMOVAL_HEADING = "## 3. The profile's ISA-visible removals"

_ID_RE = re.compile(r"^A-\d+[a-z]?$")


@dataclass(frozen=True)
class Row:
    """One row of either table: what it names, what binds it, and where it sits."""

    subject: str
    settings: tuple[tuple[str, str], ...]
    binding_text: str
    line: int

    @property
    def is_na(self) -> bool:
        """Whether the row states that no parameter reaches its subject."""
        return not self.settings and self.binding_text.lstrip().startswith("n/a")

    @property
    def is_bound(self) -> bool:
        """Whether the row says anything a build could be held to."""
        return bool(self.settings) or self.is_na


@dataclass(frozen=True)
class Record:
    """The record as a whole, with each table kept apart.

    The two are not one list because they answer to different documents: the
    absence rows are quantified over by the absence contract's own enumeration
    and the removal rows are the profile's, which carries no identifier per row.
    """

    absences: tuple[Row, ...]
    removals: tuple[Row, ...]
    present: bool

    @property
    def rows(self) -> tuple[Row, ...]:
        """Every row of both tables, for the checks that quantify over settings."""
        return self.absences + self.removals

    @property
    def settings(self) -> tuple[tuple[str, str, str], ...]:
        """Every setting any row names, each with the subject that names it."""
        return tuple((row.subject, name, value)
                     for row in self.rows for name, value in row.settings)


def _cells(line: str) -> list[str]:
    """One table row's cells, or an empty list where the line is not a row."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _table(lines: list[str], heading: str, binding_col: int) -> tuple[Row, ...]:
    """The rows of the table under one heading, from its heading to the next.

    A separator row is a row whose every cell is dashes, and a header row is the
    one before it; both are skipped by the same test rather than by counting, so
    a table that grows a column does not silently drop its first data row.
    """
    rows: list[Row] = []
    inside = False
    for number, line in enumerate(lines, start=1):
        if line.startswith(heading):
            inside = True
            continue
        if inside and line.startswith("## "):
            break
        if not inside:
            continue
        cells = _cells(line)
        if len(cells) <= binding_col:
            continue
        if all(set(cell) <= {"-", ":"} and cell for cell in cells):
            if rows:
                rows.pop()  # the header row precedes the separator; drop that one only
            continue
        binding = cells[binding_col]
        rows.append(Row(subject=cells[0],
                        settings=tuple(SETTING_RE.findall(binding)),
                        binding_text=binding,
                        line=number))
    return tuple(rows)


def read(root: Path) -> Record:
    """The record at `root`, or an empty one marked absent.

    Absence is reported rather than raised, because the rule that reads this is
    one finding about a missing record and not a traceback in the middle of a run
    that was checking something else.
    """
    path = root / RECORD
    if not path.is_file():
        return Record(absences=(), removals=(), present=False)
    lines = path.read_text(encoding="utf-8").splitlines()
    return Record(absences=_table(lines, _ABSENCE_HEADING, binding_col=2),
                  removals=_table(lines, _REMOVAL_HEADING, binding_col=1),
                  present=True)


def stated_ids(record: Record) -> tuple[str, ...]:
    """The absence identifiers the record's first table names, in its own order."""
    return tuple(row.subject for row in record.absences if _ID_RE.match(row.subject))


def config_values(text: str, name: str) -> tuple[int, ...] | None:
    """The integer literals the configuration package writes at one field.

    `None` where the package states no such field at all, which is a different
    finding from stating it at another value and is reported as one.

    The reading is the whole line's integer literals rather than a parse of
    SystemVerilog, and it is strict on purpose: every field this record names is
    set to `0` or `1`, so a line yielding any other set is a field written in a
    form this rule does not read and is a finding asking for a person rather than
    a pass over something unrecognised.
    """
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*:(.*)$", re.MULTILINE)
    found = pattern.search(text)
    if not found:
        return None
    return tuple(int(token) for token in re.findall(r"\d+", found.group(1)))
