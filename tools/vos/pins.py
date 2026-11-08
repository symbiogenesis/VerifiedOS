# SPDX-License-Identifier: Apache-2.0
"""Parse the upstream pin table in [THIRD-PARTY.md](../../THIRD-PARTY.md) and scan files for pin restatements.

This module parses the record table by column heading and scans lines that name an
upstream before stating an abbreviated commit ID. Rule decisions and repairs belong
to [checks/pins.py](checks/pins.py).
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from . import literalsearch
from .corpus import fence_lines

RECORD = "THIRD-PARTY.md"

TABLE_HEADING = "## Pinned as submodules"
COLUMNS = ("Submodule", "Upstream", "Pin")

# Match a 7..40-hex-digit abbreviated git object ID.
# A hyphen may precede an ID (`ORACLE_TREE` in `env.py` joins the upstream name and
# pin with `-`), whereas a trailing hyphen is excluded so hyphenated words with hex
# prefixes are not misread as commit IDs.
ID_RE = re.compile(r"([0-9a-f](?<![0-9A-Za-z_][0-9a-f])[0-9a-f]{6,39}+)(?![\w-])")

_BACKTICKED_RE = re.compile(r"`([^`]+)`")
_ROW_RE = re.compile(r"^\|(.*)\|\s*$")
_RULE_RE = re.compile(r"^\|[\s:|-]+\|\s*$")


@dataclass(frozen=True)
class Pin:
    """One row of the upstream pin table."""

    path: str            # gitlink path (`Submodule` column)
    upstream: str        # upstream `<owner>/<repo>`
    short: str           # abbreviated object ID (`""` if absent)
    line: int            # 1-based line number

    def names(self) -> tuple[str, ...]:
        """Spellings that may name this pin (gitlink path, `<owner>/<repo>`, and bare repo names), longest first."""
        found = {self.path, self.upstream,
                 self.path.rsplit("/", 1)[-1], self.upstream.rsplit("/", 1)[-1]}
        return tuple(sorted((n for n in found if n), key=len, reverse=True))


@dataclass
class Record:
    """Parsed pin table rows, or `fault` if the table is absent or malformed."""

    rows: list[Pin] = field(default_factory=list)
    fault: str | None = None


@dataclass(frozen=True)
class Site:
    """An abbreviated commit ID and the upstream pin named earlier on the same line."""

    file: str
    line: int            # 1-based
    index: int           # 0-based index into caller's line list
    start: int           # span within line
    end: int
    ident: str           # commit ID as written
    named: str           # pin spelling matched on the line
    pin: Pin

    def where(self) -> str:
        return f"{self.file}:{self.line}"


def _cells(line: str) -> list[str] | None:
    """Return a pipe-table row's stripped cells, or `None` if `line` is not a row."""
    m = _ROW_RE.match(line)
    return [c.strip() for c in m.group(1).split("|")] if m else None


def read_record(text: str) -> Record:
    """Parse the pin table in `THIRD-PARTY.md` by its section and column headings."""
    if not text:
        return Record(fault=f"{RECORD} is not in the repository")

    found = re.search(rf"(?m)^{re.escape(TABLE_HEADING)}[^\S\r\n]*\r?$", text)
    if found is None:
        return Record(fault=f"{RECORD} carries no `{TABLE_HEADING}` heading, so there "
                             "is no pin table to read the gitlinks against")

    lines = text[found.start():].split("\n")
    head: list[str] | None = None
    columns: dict[str, int] = {}
    rows: list[Pin] = []
    fenced = fence_lines(lines)
    base = text.count("\n", 0, found.start()) + 1

    for i, raw in enumerate(lines[1:], start=1):
        line = raw.removesuffix("\r")
        if fenced[i]:
            continue
        if line.startswith("## "):
            break
        cells = _cells(line)
        if cells is None:
            if head is not None and columns:
                break
            continue
        if head is None:
            head = cells
            continue
        if not columns:
            if not _RULE_RE.match(line):
                head = cells
                continue
            columns = {name: head.index(name) for name in COLUMNS if name in head}
            if len(columns) != len(COLUMNS):
                missing = ", ".join(c for c in COLUMNS if c not in columns)
                return Record(fault=f"{RECORD}'s pin table carries no {missing} "
                                    "column, so its rows cannot be read")
            continue
        if max(columns.values()) >= len(cells):
            continue                    # short rows are reported by K-38
        path = _BACKTICKED_RE.search(cells[columns["Submodule"]])
        upstream = _BACKTICKED_RE.search(cells[columns["Upstream"]])
        ident = ID_RE.search(cells[columns["Pin"]])
        rows.append(Pin(path=path.group(1) if path else "",
                        upstream=upstream.group(1) if upstream else "",
                        short=ident.group(1) if ident else "",
                        line=base + i))

    if head is None or not columns:
        return Record(fault=f"{RECORD}'s `{TABLE_HEADING}` section carries no table "
                            "this parse reads")
    if not rows:
        return Record(fault=f"{RECORD}'s pin table carries no rows, so the gitlinks "
                            "would be held against nothing")
    return Record(rows=rows)


def spellings(pins: list[Pin]) -> list[tuple[str, str, Pin]]:
    """Return `(lowered_spelling, original_spelling, pin)` tuples sorted longest first."""
    return sorted(((spelling.lower(), spelling, pin)
                   for pin in pins for spelling in pin.names()),
                  key=lambda row: len(row[0]), reverse=True)


def scan(file: str, lines: list[str], named: list[tuple[str, str, Pin]]) -> Iterator[Site]:
    """Scan a line list for pin restatements."""
    return scan_text(file, "\n".join(lines), named)


def scan_text(file: str, text: str, named: list[tuple[str, str, Pin]], *,
              matcher: literalsearch.CandidateTrie | None = None) -> Iterator[Site]:
    """Yield every pin restatement in `text` in source order.

    Each commit ID is attributed to the last upstream name spelling that begins
    before it on the same line.
    """
    low = text.lower()
    if len(low) == len(text) and all("\n" not in name for name, _, _ in named):
        names = tuple(n for n, _, _ in named)
        if matcher is None or matcher.names != names:
            try:
                matcher = literalsearch.compile_names(names)
            except literalsearch.LegacyRequiredError:
                matcher = None
        for index, start, end in candidate_lines(text, names, lowered=low, matcher=matcher):
            if ID_RE.search(text, start, end) is None:
                continue
            marks = _named(text[start:end].removesuffix("\r"), named)
            if not marks:
                continue
            cursor = 0
            for match in ID_RE.finditer(text, start, end):
                offset = match.start() - start
                while cursor < len(marks) and marks[cursor][0] < offset:
                    cursor += 1
                if cursor:
                    _, spelling, pin = marks[cursor - 1]
                    yield Site(file, index + 1, index, offset, match.end() - start,
                               match.group(1), spelling, pin)
        return
    yield from _scan_ids(file, text, named)


def name_patterns(names: tuple[str, ...]) -> tuple[tuple[str, re.Pattern[str]], ...]:
    """Compile boundary-checked patterns for each upstream name."""
    return tuple((name, re.compile(re.escape(name) + r"(?<![\w-]" + re.escape(name) + r")(?!\w)"))
                 for name in names)


def candidate_lines(text: str, names: tuple[str, ...], *, lowered: str | None = None,
                    patterns: tuple[tuple[str, re.Pattern[str]], ...] | None = None,
                    matcher: literalsearch.CandidateTrie | None = None
                    ) -> Iterator[tuple[int, int, int]]:
    """Yield `(line_index, start, end)` for lines containing any upstream name."""
    if not names:
        return
    low = text.lower() if lowered is None else lowered
    if len(low) != len(text):
        raise ValueError("Unicode lowercase changes source offsets")
    if matcher is not None and matcher.names == names:
        yield from matcher.lines(text, lowered=low)
        return
    if not any(name in low for name in names):
        return
    spans: set[tuple[int, int]] = set()
    for name, pattern in name_patterns(names) if patterns is None else patterns:
        if name not in low:
            continue
        match = pattern.search(low)
        while match is not None:
            start = text.rfind("\n", 0, match.start()) + 1
            end = text.find("\n", match.end())
            spans.add((start, end if end >= 0 else len(text)))
            if end < 0:
                break
            match = pattern.search(low, end + 1)
    cursor = index = 0
    for start, end in sorted(spans):
        index += text.count("\n", cursor, start)
        yield index, start, end
        cursor = start


def _scan_ids(file: str, text: str, named: list[tuple[str, str, Pin]]) -> Iterator[Site]:
    """Fallback whole-text ID scan when Unicode lowercasing changes string length."""
    index = start = 0
    end = -1
    marks: list[tuple[int, str, Pin]] = []
    cursor = 0
    for m in ID_RE.finditer(text):
        if m.start() >= end:
            next_start = text.rfind("\n", start, m.start()) + 1
            index += text.count("\n", start, next_start)
            start = next_start
            end = text.find("\n", m.end())
            if end < 0:
                end = len(text)
            marks = _named(text[start:end].removesuffix("\r"), named)
            cursor = 0
        offset = m.start() - start
        while cursor < len(marks) and marks[cursor][0] < offset:
            cursor += 1
        if cursor:
            _, spelling, pin = marks[cursor - 1]
            yield Site(file=file, line=index + 1, index=index,
                       start=offset, end=m.end() - start, ident=m.group(1),
                       named=spelling, pin=pin)


def _named(line: str, named: list[tuple[str, str, Pin]]) -> list[tuple[int, str, Pin]]:
    """Find non-overlapping upstream name matches on `line`, longest spelling first.

    A preceding hyphen rejects the match (so `CHERI-QEMU` or `cheriot-ibex` is not
    matched as `qemu` or `ibex`), while a trailing hyphen is allowed (`<name>-<pin>`).
    """
    low = line.lower()
    marks: list[tuple[int, str, Pin]] = []
    claimed: list[tuple[int, int]] = []
    for needle, spelling, pin in named:
        at = low.find(needle)
        while at >= 0:
            end = at + len(needle)
            before = low[at - 1] if at else " "
            after = low[end] if end < len(low) else " "
            if (not (before.isalnum() or before in "_-")
                    and not (after.isalnum() or after == "_")
                    and not any(a <= at < b for a, b in claimed)):
                marks.append((at, spelling, pin))
                claimed.append((at, end))
            at = low.find(needle, at + 1)
    marks.sort(key=lambda mark: mark[0])
    return marks
