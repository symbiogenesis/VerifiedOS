# SPDX-License-Identifier: Apache-2.0
"""Check that every run of pipe-led lines in Markdown includes a header separator rule (`K-39`).

The host Markdown linter checks table column widths and pipe formatting once a block is
parsed as a table; `K-39` catches consecutive unfenced pipe-led lines that omit the
`| --- |` separator row and would otherwise be parsed as plain paragraph text.
"""

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import Context

HEADING = "=== tables: pipe-led runs retain their table separator ==="

# Consecutive unfenced pipe-led lines form a table run; each run must contain a `RULE_RE` line.
ROW_RE = re.compile(r"[^\S\r\n]*\|")
RULE_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)

    ruleless: list[str] = []
    for doc in ctx.corpus.docs:
        if "|" not in doc.raw:
            continue
        rows = 0
        start_line = 0
        has_rule = False
        prev_line = -2

        for line_index, line in enumerate(doc.lines):
            if "|" not in line or not ROW_RE.match(line):
                continue
            if doc.fenced[line_index]:
                continue
            if rows and line_index != prev_line + 1:
                if not has_rule:
                    ruleless.append(f"{doc.name}:{start_line + 1}, {rows} row(s) with no header rule")
                rows, has_rule = 0, False
            if rows == 0:
                start_line = line_index
            if RULE_RE.match(line):
                has_rule = True
            rows += 1
            prev_line = line_index

        if rows and not has_rule:
            ruleless.append(f"{doc.name}:{start_line + 1}, {rows} row(s) with no header rule")

    rep.report("K-39", "run(s) of table rows carrying no header rule:", ruleless,
               "every table row belongs to a table with a header rule")
    rep.line()
