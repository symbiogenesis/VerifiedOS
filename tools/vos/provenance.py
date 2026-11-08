# SPDX-License-Identifier: Apache-2.0
"""Parse [rtl/synthesis-provenance.md](../../rtl/synthesis-provenance.md) and extract
parameter bindings from [rtl/vos_c_class_config_pkg.sv](../../rtl/vos_c_class_config_pkg.sv)
(R-15-103)."""

import re
from dataclasses import dataclass
from pathlib import Path

RECORD = "rtl/synthesis-provenance.md"
CONFIG = "rtl/vos_c_class_config_pkg.sv"

# Backticked `Name = value` parameter binding inside a table cell.
SETTING_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([A-Za-z0-9_']+)`")

_ABSENCE_HEADING = "## 2. The absences the contract enumerates"
_REMOVAL_HEADING = "## 3. The profile's ISA-visible removals"

_ID_RE = re.compile(r"^A-\d+[a-z]?$")


@dataclass(frozen=True)
class Row:
    """Single synthesis-provenance table row."""

    subject: str
    settings: tuple[tuple[str, str], ...]
    binding_text: str
    line: int

    @property
    def is_na(self) -> bool:
        """Return whether the row declares `n/a` (no synthesis parameter applies)."""
        return not self.settings and self.binding_text.lstrip().startswith("n/a")

    @property
    def is_bound(self) -> bool:
        """Return whether the row has at least one `Name = value` setting or an `n/a` rationale."""
        return bool(self.settings) or self.is_na


@dataclass(frozen=True)
class Record:
    """Parsed synthesis-provenance record separating absence-contract rows and ISA-removal rows."""

    absences: tuple[Row, ...]
    removals: tuple[Row, ...]
    present: bool

    @property
    def rows(self) -> tuple[Row, ...]:
        """Return all rows from both tables."""
        return self.absences + self.removals

    @property
    def settings(self) -> tuple[tuple[str, str, str], ...]:
        """Return `(subject, name, value)` triples across all rows."""
        return tuple((row.subject, name, value)
                     for row in self.rows for name, value in row.settings)


def _cells(line: str) -> list[str]:
    """Split a Markdown table row into stripped cells, or return `[]` if `line` is not a table row."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _table(lines: list[str], heading: str, binding_col: int) -> tuple[Row, ...]:
    """Parse table rows under `heading`, extracting `SETTING_RE` bindings from column `binding_col`."""
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
                rows.pop()
            continue
        binding = cells[binding_col]
        rows.append(Row(subject=cells[0],
                        settings=tuple(SETTING_RE.findall(binding)),
                        binding_text=binding,
                        line=number))
    return tuple(rows)


def read(root: Path) -> Record:
    """Parse `root / RECORD`, or return `Record(present=False)` if missing."""
    path = root / RECORD
    if not path.is_file():
        return Record(absences=(), removals=(), present=False)
    lines = path.read_text(encoding="utf-8").splitlines()
    return Record(absences=_table(lines, _ABSENCE_HEADING, binding_col=2),
                  removals=_table(lines, _REMOVAL_HEADING, binding_col=1),
                  present=True)


def stated_ids(record: Record) -> tuple[str, ...]:
    """Return `A-*` absence identifiers from `record.absences` in table order."""
    return tuple(row.subject for row in record.absences if _ID_RE.match(row.subject))


def config_values(text: str, name: str) -> tuple[int, ...] | None:
    """Return integer literals on the `name:` field line in `text`, or `None` if `name` is absent."""
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*:(.*)$", re.MULTILINE)
    found = pattern.search(text)
    if not found:
        return None
    return tuple(int(token) for token in re.findall(r"\d+", found.group(1)))
