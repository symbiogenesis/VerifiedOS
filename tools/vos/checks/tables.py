"""tables: every row against the width its header declares.

Nearly every counted artifact here is a table, and the counts group reads one by
column position: the crown-jewel status is the last cell, the Coverage total the
third. A row short a cell does not fail, it renders short, and every field after the
gap shifts one place left, so a column read at the end returns the neighbouring field
and the count taken from it is wrong while still being computed. The header row
decides the width; a row that disagrees is the finding, and only its author knows
which cell is missing.

A run of rows carrying no header rule is the second finding, and the coarser one. It
is either a table whose `| --- |` was lost, which renders as a paragraph of pipes and
is read by nothing, or a row pasted somewhere on its own, which renders as its own
one-row table and is read by nothing either. Both are invisible in the source and
obvious the moment anything looks for the rule.
"""

from __future__ import annotations

import re

from .links import sites

HEADING = "=== tables: every row against the width its header declares ==="

# only the rows are visited: the matcher hands back every pipe-led line with its
# offset, an offset is its line by exact search (the match is ^-anchored), and a run is
# rows on consecutive lines; a fenced row is display text, and the line it holds breaks
# the adjacency exactly as any prose line does
ROW_RE = re.compile(r"(?m)^[^\S\r\n]*\|[^\r\n]*")
RULE_RE = re.compile(r"^\s*\|[\s:|-]+\|\s*$")
ESCAPED_PIPE_RE = re.compile(r"\\\|")


def run(ctx) -> None:
    rep = ctx.rep
    rep.line(HEADING)

    ragged: list[str] = []
    ruleless: list[str] = []
    for doc in ctx.corpus.docs:
        bad: list[int] = []
        width = rows = 0
        start_line = 0
        has_rule = False
        prev_line = -2

        for m in ROW_RE.finditer(doc.raw):
            line_index = doc.line_of(m.start())
            if doc.fenced[line_index]:
                continue
            if rows and line_index != prev_line + 1:
                if not has_rule:
                    ruleless.append(f"{doc.name}:{start_line + 1}, {rows} row(s) with no header rule")
                rows, has_rule = 0, False
            line = m.group()
            # an escaped pipe is a character inside a cell, not a wall between two
            cells = len(ESCAPED_PIPE_RE.sub("", line.rstrip()).split("|")) - 2
            if rows == 0:
                start_line, width = line_index, cells
            elif cells != width:
                bad.append(line_index + 1)
            if RULE_RE.match(line):
                has_rule = True
            rows += 1
            prev_line = line_index

        if rows and not has_rule:
            ruleless.append(f"{doc.name}:{start_line + 1}, {rows} row(s) with no header rule")
        if bad:
            ragged.append(sites(doc.name, bad))

    rep.report("K-38", "file(s) with a table row of the wrong width", ragged,
               "every table row is the width its header declares")
    rep.report("K-39", "run(s) of table rows carrying no header rule:", ruleless,
               "every table row belongs to a table with a header rule")
    rep.line()
