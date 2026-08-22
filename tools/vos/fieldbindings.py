# SPDX-License-Identifier: Apache-2.0
"""The field-bindings table, parsed once for the two tools that read it.

docs/field-bindings.md is one table, one row per Prop field of the apex statement's
Vocabulary record, and two tools read its cells: the checker's bindings group holds
the mechanical cells against the `.v`, and `blast-radius.py` reads the
Instantiated-by column to find which fields an artifact discharges. The row shape is
therefore a fact two consumers depend on, and it is decided here rather than spelled
at each call site, which is the two-copies-of-one-fact defect the checker exists to
catch.

The cells come back as a `Row` per readable row, in document order. A line the row
pattern claims and the cell reads cannot use, a truncated row, is no `Row` at all:
it is skipped here so neither consumer indexes past it, and `malformed` names it so
the checker can report it rather than crash on it.
"""

import re
from dataclasses import dataclass

BINDINGS = "docs/field-bindings.md"

# the field cell is code-formatted, so the leading backtick is required and is what
# tells a row from the header above it; the closing one is optional only because the
# pattern reads the name and not the formatting
ROW_RE = re.compile(r"^\| ``?(\w+)``? \|")

# The reads below reach `cells[4]`, the Instantiated-by cell of a row split on `|`;
# a full row splits into six segments, two edges around four cells. Five segments is
# the floor a row must clear for that index to name a cell at all: the exact width is
# K-38's, which runs later in the run than these reads happen, so the floor is held
# here where it is relied on.
_WIDTH = 5


@dataclass(frozen=True)
class Row:
    """One binding row, as the cells its two consumers read."""

    field: str            # the Prop field the row binds, backticks stripped
    consumers: str        # the Consumed-by cell, as written
    instantiated_by: str  # the Instantiated-by cell, as written


def _scan(text: str) -> tuple[list[Row], list[str]]:
    rows: list[Row] = []
    broken: list[str] = []
    for line in text.splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        cells = line.split("|")
        if len(cells) < _WIDTH:
            broken.append(line.strip())
            continue
        rows.append(Row(field=m.group(1),
                        consumers=cells[2].strip(),
                        instantiated_by=cells[4].strip()))
    return rows, broken


def rows(text: str) -> list[Row]:
    """Every readable row of the bindings table, in document order."""
    return _scan(text)[0]


def malformed(text: str) -> list[str]:
    """Every line the row pattern claims and the cells cannot be read out of, for the
    checker to report where a bare index would have crashed the run."""
    return _scan(text)[1]
