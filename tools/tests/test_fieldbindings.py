# SPDX-License-Identifier: Apache-2.0
"""The field-bindings row parse, held to what its two consumers rely on.

`vos/fieldbindings.py` is the one parse of docs/field-bindings.md's table, and its
contract has three load-bearing edges: a data row is told from the header by the
leading backtick on the field cell, a truncated row is skipped from `rows()` and
surfaced by `malformed()` instead of crashing an index, and the five-segment width
floor is exactly where `cells[4]` starts naming a cell at all.
"""

from tests.harness import Case, ensure
from vos import fieldbindings

# A table in the live document's shape: header, separator, one single-backtick row
# and one double-backtick row, all four cells present.
_WELL_FORMED = """\
| Field | Consumed by | Semantics | Instantiated by |
| --- | --- | --- | --- |
| `alpha` | seam_one | prose here | [proofs/Alpha.v](../proofs/Alpha.v) (`AlphaProof`) |
| ``beta`` | seam_one, seam_two | more prose | none yet |
"""


def _well_formed_rows() -> None:
    rows = fieldbindings.rows(_WELL_FORMED)
    ensure(len(rows) == 2, f"expected 2 rows out of the well-formed table, got {len(rows)}")
    ensure(rows[0].field == "alpha" and rows[1].field == "beta",
           f"fields read back as {[r.field for r in rows]}, backticks not stripped")
    ensure(rows[0].consumers == "seam_one",
           f"the Consumed-by cell read back as {rows[0].consumers!r}")
    ensure(rows[0].instantiated_by == "[proofs/Alpha.v](../proofs/Alpha.v) (`AlphaProof`)",
           f"the Instantiated-by cell read back as {rows[0].instantiated_by!r}")
    ensure(rows[1].instantiated_by == "none yet",
           f"the named absence read back as {rows[1].instantiated_by!r}")
    ensure(fieldbindings.malformed(_WELL_FORMED) == [],
           "a well-formed table must surface no malformed line")


def _truncated_row_surfaced() -> None:
    text = _WELL_FORMED + "| `gamma` | one cell only |\n"
    rows = fieldbindings.rows(text)
    ensure([r.field for r in rows] == ["alpha", "beta"],
           "a truncated row must be skipped, not read past its last cell")
    ensure(fieldbindings.malformed(text) == ["| `gamma` | one cell only |"],
           f"the truncated row must be surfaced whole, got {fieldbindings.malformed(text)!r}")


def _header_and_separator_skipped() -> None:
    # Neither the header nor the separator opens its first cell with a backtick, which
    # is the whole of what tells a data row from them; both fall outside rows() and
    # malformed() alike.
    text = "| Field | Consumed by | Semantics | Instantiated by |\n| --- | --- | --- | --- |\n"
    ensure(fieldbindings.rows(text) == [], "the header and separator are not rows")
    ensure(fieldbindings.malformed(text) == [],
           "the header and separator are not malformed rows either")


def _width_floor() -> None:
    # Five segments is the floor: `| `f` | a | b |` splits into exactly five, so
    # cells[4] is the (empty) edge past the last pipe and the row is admitted with an
    # empty Instantiated-by cell; one cell fewer is malformed. The exact width is
    # K-38's to hold, later in a check run than this parse.
    at_floor = "| `f` | a | b |\n"
    rows = fieldbindings.rows(at_floor)
    ensure(len(rows) == 1 and rows[0].instantiated_by == "",
           "a five-segment row sits exactly at the floor and reads an empty cell")
    below = "| `g` | a |\n"
    ensure(fieldbindings.rows(below) == [] and fieldbindings.malformed(below) == ["| `g` | a |"],
           "a four-segment row sits below the floor and must be malformed")


def cases() -> list[Case]:
    return [
        Case("well-formed-rows", _well_formed_rows),
        Case("truncated-row-surfaced", _truncated_row_surfaced),
        Case("header-and-separator-skipped", _header_and_separator_skipped),
        Case("width-floor", _width_floor),
    ]
