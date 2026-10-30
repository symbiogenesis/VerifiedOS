# SPDX-License-Identifier: Apache-2.0
"""Pipe-led runs require a table separator even when Markdown reads them as prose.

The maintained host Markdown gate owns table width and pipe style. This small
residue catches a missing separator, which prevents recognition as a table.
"""

import re
from typing import TYPE_CHECKING

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== tables: pipe-led runs retain their table separator ==="

# only the rows are visited: a row is a pipe-led line, and a run is rows on consecutive
# lines; a fenced row is display text, and the line it holds breaks the adjacency
# exactly as any prose line does. The lines are walked rather than scanned for with
# `(?m)^`, so a line carrying no pipe at all is rejected by a substring test before the
# regex engine is entered, and each row's index comes from the walk instead of from a
# binary search back through the offsets.
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
