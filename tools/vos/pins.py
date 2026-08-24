# SPDX-License-Identifier: Apache-2.0
"""The upstream pins: the record's own table, and every site that restates one.

Three artifacts state which commit of an upstream this repository stands on, and
only one of them is the truth. The **git index** carries a gitlink entry per
submodule, whose object id is what a clone actually fetches. [THIRD-PARTY.md](../../THIRD-PARTY.md)
carries the licence record, whose pin column is hand-copied from that gitlink and
is where each upstream's terms were read. And the documents, the ported model
headers and the tools restate those short ids wherever they argue from one.

This module is the parse and never the decision. It reads the record's table as a
*structure*, locating its columns by their own headings rather than by position and
its rows by the table they sit in rather than by a count, so a row added or removed
changes what it answers and never whether it can answer. And it finds the restating
sites by the shape a restatement takes: an abbreviated object id standing on a line
that has already named the upstream it belongs to. What those answers mean, which
side owns which, and which disagreement is repairable are `vos/checks/pins.py`'s.

**Why the site is a line and not a paragraph.** A restatement pairs a name with an
id, and the pairing has to be decided by something. Proximity in characters is the
obvious rule and it is wrong here: the delta's provenance table puts one upstream's
row four lines above another's cell, so a character window either reaches across
rows or fails to reach across a table cell. A line is what both the tables and the
prose already use as the unit that states one pin, so the nearest name *on the
line* is the name the id is stated under, and an id on a line naming no upstream is
not a restatement this parse can decide at all.
"""

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from .corpus import FENCE_RE

RECORD = "THIRD-PARTY.md"

# The record's own heading over the pin table, and the three column headings the
# parse locates by. Reading the columns by name is what lets a column be inserted,
# moved or retitled without this parse silently reading the wrong cell: a heading it
# cannot find is a finding at the caller rather than a cell taken by position.
TABLE_HEADING = "## Pinned as submodules"
COLUMNS = ("Submodule", "Upstream", "Pin")

# An abbreviated git object id as this repository writes one: hexadecimal, at least
# the seven digits git's own default abbreviation gives, and at most a full id. The
# boundaries refuse a token that is part of a longer word, which is what keeps the
# `0x`-prefixed literals of the model and the sixty-four-digit digests of the corpus
# manifest and the co-read ledger out of the reading: neither has a boundary where a
# seven-to-forty-digit run would have to start.
#
# The two boundaries are deliberately not the same class. A hyphen may *precede* an
# id, because `env.py`'s `ORACLE_TREE` names a build tree by joining the upstream to
# its pin with one and no space, and a rule that refused it would leave the one site
# where a stale pin silently reuses another edition's tree unread. Nothing writes a
# hyphen *after* an id, so admitting one there would buy nothing and would let the
# hexadecimal head of an ordinary hyphenated word read as a commit.
ID_RE = re.compile(r"(?<![0-9A-Za-z_])([0-9a-f]{7,40})(?![\w-])")

_BACKTICKED_RE = re.compile(r"`([^`]+)`")
_ROW_RE = re.compile(r"^\|(.*)\|\s*$")
_RULE_RE = re.compile(r"^\|[\s:|-]+\|\s*$")


@dataclass(frozen=True)
class Pin:
    """One row of the record's pin table, as the row states it."""

    path: str            # the gitlink's path, as the Submodule cell names it
    upstream: str        # the upstream's own `<owner>/<repo>`
    short: str           # the abbreviated object id the row states, "" where it states none
    line: int            # 1-based, for a finding somebody has to go and visit

    def names(self) -> tuple[str, ...]:
        """Every spelling a site may name this pin by, longest first and once each.

        Four are looked for rather than one, because the tree writes all four: the
        gitlink path, the upstream's `owner/repo`, and the bare repository name at
        the end of each. The two bare names differ where the submodule is checked
        out under a path the upstream does not use, `axi-cheri-tagcontroller`
        against `axi_cheri_tagcontroller` being the one that does, so taking either
        alone would leave that row's sites unread. Longest first is what makes
        `cheriot-ibex` win over `ibex` where a line spells the longer one.
        """
        found = {self.path, self.upstream,
                 self.path.rsplit("/", 1)[-1], self.upstream.rsplit("/", 1)[-1]}
        return tuple(sorted((n for n in found if n), key=len, reverse=True))


@dataclass
class Record:
    """The record's pin table, or the reason there is none to read."""

    rows: list[Pin] = field(default_factory=list)
    fault: str | None = None


@dataclass(frozen=True)
class Site:
    """One restatement: an id, and the pin whose name the line states before it."""

    file: str
    line: int            # 1-based
    index: int           # 0-based, into the caller's own line list
    start: int           # the id's span within its line
    end: int
    ident: str           # the id as the site writes it
    named: str           # the spelling of the pin the line used
    pin: Pin

    def where(self) -> str:
        return f"{self.file}:{self.line}"


def _cells(line: str) -> list[str] | None:
    """A table row's cells, or None where the line is not a row."""
    m = _ROW_RE.match(line)
    return [c.strip() for c in m.group(1).split("|")] if m else None


def read_record(text: str) -> Record:
    """The record's pin table, read by its own headings.

    Fail-closed at every step, because each step's failure is a different repair and
    none of them may pass silently: the heading is where the table is, the column
    headings are which cell holds what, and a table with no rows under a heading
    that exists is a record that has stopped stating any pin at all.

    A Pin cell may carry more than one id-shaped token, the page writing the tag a
    commit is named by beside the commit itself, and what is read is the **first**,
    which is the order the rows are written in. That convention is not enforced here
    and does not need to be: a row that wrote the tag first would state an id no
    gitlink carries, so the caller reports it rather than reading it silently as the
    pin, which is the failure a reader of that row would have made too.
    """
    if not text:
        return Record(fault=f"{RECORD} is not in the repository")

    # matched at a line start rather than searched for after a newline, so the
    # heading is still found in a file that opens with it
    found = re.search(rf"(?m)^{re.escape(TABLE_HEADING)}[^\S\r\n]*$", text)
    if found is None:
        return Record(fault=f"{RECORD} carries no `{TABLE_HEADING}` heading, so there "
                             "is no pin table to read the gitlinks against")

    lines = text[found.start():].split("\n")
    head: list[str] | None = None
    columns: dict[str, int] = {}
    rows: list[Pin] = []
    fenced = False
    # the 1-based line the heading itself sits on, so a row's number is the file's
    base = text.count("\n", 0, found.start()) + 1

    for i, raw in enumerate(lines[1:], start=1):
        line = raw.removesuffix("\r")
        # a fence displays its content as text, so a pipe table inside one is a
        # picture of a table and not this document's pin table. The rule is the
        # corpus's and comes from there; the walk is here because this parse is
        # handed a text rather than a Document, which is what lets a fixture
        # exercise it without standing up a corpus.
        if "```" in line and FENCE_RE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        if line.startswith("## "):
            break                       # the next section: this table is over
        cells = _cells(line)
        if cells is None:
            if head is not None and columns:
                break                   # prose after the rows: this table is over
            continue
        if head is None:
            head = cells
            continue
        if not columns:
            if not _RULE_RE.match(line):
                head = cells            # a second header before any rule: take it
                continue
            columns = {name: head.index(name) for name in COLUMNS if name in head}
            if len(columns) != len(COLUMNS):
                missing = ", ".join(c for c in COLUMNS if c not in columns)
                return Record(fault=f"{RECORD}'s pin table carries no {missing} "
                                    "column, so its rows cannot be read")
            continue
        if max(columns.values()) >= len(cells):
            continue                    # a short row is K-38's finding, not this one
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
    """Every name any pin may be written under, folded, longest first.

    Built once per run rather than once per line: the fold and the sort are the
    whole cost of the scan below over a file that states no pin at all, and there
    are files here with a thousand lines carrying a digest apiece.

    Longest first is what decides an overlap between two upstreams whose names
    nest, `cheriot-ibex` over `ibex` being the pair this repository actually pins.
    """
    return sorted(((spelling.lower(), spelling, pin)
                   for pin in pins for spelling in pin.names()),
                  key=lambda row: len(row[0]), reverse=True)


def scan(file: str, lines: list[str], named: list[tuple[str, str, Pin]]) -> Iterator[Site]:
    """Every restatement the lines carry, in the order they read.

    A line is skipped whole unless it carries an id, which is what keeps this off the
    ninety-nine lines in a hundred that state no commit at all. Whether a line is
    *displayed* rather than read is the caller's, because only the caller knows
    whether the file is Markdown at all and, where it is, the corpus already holds
    the fence mask over it; recomputing one here would be a second answer to a
    question that is already answered.

    The pin is decided by the last of its own spellings to *begin* before the id.
    Beginning and not ending, because `env.py`'s `ORACLE_TREE` joins the upstream to
    its pin with one hyphen and no space, and a rule reading from the name's end
    would take the id as part of the name.
    """
    for index, raw in enumerate(lines):
        line = raw.removesuffix("\r")
        found = list(ID_RE.finditer(line))
        if not found:
            continue
        marks = _named(line, named)
        if not marks:
            continue
        for m in found:
            before = [mark for mark in marks if mark[0] < m.start()]
            if not before:
                continue
            _, spelling, pin = before[-1]
            yield Site(file=file, line=index + 1, index=index,
                       start=m.start(), end=m.end(), ident=m.group(1),
                       named=spelling, pin=pin)


def _named(line: str, named: list[tuple[str, str, Pin]]) -> list[tuple[int, str, Pin]]:
    """Where each pin is named on one line, in the order the line reads.

    A position already claimed by a longer spelling is not claimed again, so a line
    spelling `cheriot-ibex` names one upstream rather than two overlapping ones. The
    match is case-insensitive because prose capitalizes a project's name where a
    path does not.

    **The two boundaries differ, on the same asymmetry `ID_RE` carries.** A hyphen
    *before* a name means the name is the tail of a longer compound and not the
    project: the plan writes `CHERI-QEMU` for the fork and `cheriot-ibex` for a
    different upstream than `ibex`, and reading either as the shorter name would
    attach an id to the wrong pin. A hyphen *after* one is the joint the tools
    attach a pin at, which is how the capability oracle's build tree is named, so
    refusing it there would leave that site unread.
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
