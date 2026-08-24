# SPDX-License-Identifier: Apache-2.0
"""The pin parse, over a record it can read and over every way one can move.

`pins.read_record` and `pins.scan` are the whole of the checker's reading of the
upstream pins, and the live tree exercises the happy path on every `check.py` run.
What only a fixture can pin is the refusal shape: a heading that is gone, a column
retitled, a table with no rows, and a record that is not there at all are four
different repairs and each must answer as itself rather than as an exception. The
same goes for the scan's hard cases, an id on a line naming no upstream, a name
stated after the id it would have claimed, and a name that nests inside a longer one.

**Every upstream and every commit below is invented, and that is load-bearing.**
K-81 reads this directory, so a fixture spelling a real submodule beside a wrong id
would be a restatement of a real pin sitting in a test file, reported by the live run
exactly as it should be. The names here nest the way the real ones do, `core` inside
`nested-core`, so the case they exist for is made without impersonating the record.

Nothing here restates what a disagreement *means*, which is `vos/checks/pins.py`'s
and is stated once, in its own module beside the code that decides it.
"""

import tempfile
from pathlib import Path

from tests.harness import Case, ensure
from vos import pins

# A record shaped exactly as THIRD-PARTY.md shapes one: the pin table under its own
# heading, a column order this parse must not depend on, and a second table above it
# carrying a commit no gitlink owns, which is the shape the parse must not read as a
# pin.
_RECORD = """# Third-Party Components

## Vendored, and redistributed here

| Component | Version or pin | Upstream |
| --- | --- | --- |
| The vendored tree, `vendor/` | `aaa11122` | `example/core` |

## Pinned as submodules

These are gitlink entries.

| Submodule | Upstream | Pin | License | Standing |
| --- | --- | --- | --- | --- |
| `upstream/core` | `example/core` | `1a2b3c4d` | `BSD-2-Clause` | The base. |
| `upstream/nested-core` | `other/nested-core` | `5e6f7a8b` | `Apache-2.0` | A second. |
| `upstream/wide` | `third/wide_name` | `9c0d1e2f` | `Apache-2.0` | A third. |

**Prose after the rows, which ends the table.**

## Used by the build, not conveyed

| Tool | License |
| --- | --- |
| Verilator | `LGPL-3.0` |
"""


def _rows() -> list[pins.Pin]:
    read = pins.read_record(_RECORD)
    ensure(read.fault is None, f"the fixture record must read: {read.fault}")
    return read.rows


def _reads_its_own_table() -> None:
    rows = _rows()
    ensure([(p.path, p.upstream, p.short) for p in rows] == [
        ("upstream/core", "example/core", "1a2b3c4d"),
        ("upstream/nested-core", "other/nested-core", "5e6f7a8b"),
        ("upstream/wide", "third/wide_name", "9c0d1e2f"),
    ], f"the pin table's three rows read as {[(p.path, p.short) for p in rows]}")
    # the line numbers are the file's, so a finding is a place somebody can visit
    ensure([p.line for p in rows] == [15, 16, 17],
           f"the rows must carry their own line numbers, got {[p.line for p in rows]}")


def _stops_at_the_table() -> None:
    # The vendored table above states a commit and the tool table below states none,
    # and neither is a pin: the parse takes the rows of one table and no other.
    rows = _rows()
    ensure(all(p.path.startswith("upstream/") for p in rows),
           f"a row from another table was read as a pin: {[p.path for p in rows]}")


def _columns_are_found_by_name() -> None:
    # The same row with its columns permuted and a fourth inserted answers exactly as
    # it did, which is the whole of what reading the header buys over counting cells.
    permuted = """# Third-Party Components

## Pinned as submodules

| Standing | License | Pin | Read | Upstream | Submodule |
| --- | --- | --- | --- | --- | --- |
| The base. | `BSD-2-Clause` | `1a2b3c4d` | 2026-08-23 | `example/core` | `upstream/core` |
"""
    read = pins.read_record(permuted)
    ensure(read.fault is None, f"a permuted header must still read: {read.fault}")
    ensure([(p.path, p.upstream, p.short) for p in read.rows]
           == [("upstream/core", "example/core", "1a2b3c4d")],
           f"a permuted header read {[(p.path, p.upstream, p.short) for p in read.rows]}")


def _readings_that_have_moved() -> None:
    # Four ways the record can move, four faults, and no exception among them.
    rows = ("| `upstream/core` | `example/core` | `1a2b3c4d` | `BSD-2-Clause` | The base. |\n"
            "| `upstream/nested-core` | `other/nested-core` | `5e6f7a8b` | `Apache-2.0` | A second. |\n"
            "| `upstream/wide` | `third/wide_name` | `9c0d1e2f` | `Apache-2.0` | A third. |\n")
    moved = {
        "an absent record": "",
        "a retitled heading": _RECORD.replace("## Pinned as submodules",
                                              "## Pinned as gitlinks"),
        "a retitled column": _RECORD.replace("| Submodule | Upstream | Pin |",
                                             "| Gitlink | Upstream | Pin |"),
        "a table with no rows": _RECORD.replace(rows, ""),
    }
    for what, text in moved.items():
        read = pins.read_record(text)
        ensure(read.fault is not None,
               f"{what} must be a fault this parse words, and it read "
               f"{len(read.rows)} row(s) instead")
        ensure(not read.rows, f"{what} must yield no rows, and it yielded {read.rows}")


def _a_row_stating_no_id() -> None:
    # A row is still a row: the pin cell being empty is the caller's finding to word,
    # so the parse answers with the row and an empty id rather than dropping it.
    read = pins.read_record(_RECORD.replace("| `1a2b3c4d` |", "| pending |"))
    ensure(read.fault is None, f"a row with no id must not be a fault: {read.fault}")
    ensure([p.short for p in read.rows] == ["", "5e6f7a8b", "9c0d1e2f"],
           f"the row must survive with an empty id, got {[p.short for p in read.rows]}")


def _scan_pairs_by_the_nearest_name() -> None:
    named = pins.spellings(_rows())
    lines = [
        "the base (`example/core` at `1a2b3c4d`) and (`other/nested-core` "
        "at `5e6f7a8b`)",
        "| Implementation | `upstream/core`, `src/` | `1a2b3c4d` | 2026-08-23 |",
        'ORACLE_TREE = "core-1a2b3c4d"',
        "Read at `1a2b3c4d` on 2026-08-23, with no upstream named on this line",
        "`upstream/wide` is pinned and this line states 9c0d1e2f0011 as well",
        "the underscore spelling `third/wide_name` is at `9c0d1e2f` too",
    ]
    found = [(s.line, s.ident, s.pin.path) for s in pins.scan("f", lines, named)]
    ensure(found == [
        (1, "1a2b3c4d", "upstream/core"),
        (1, "5e6f7a8b", "upstream/nested-core"),
        (2, "1a2b3c4d", "upstream/core"),
        (3, "1a2b3c4d", "upstream/core"),
        (5, "9c0d1e2f0011", "upstream/wide"),
        (6, "9c0d1e2f", "upstream/wide"),
    ], f"the scan paired {found}")


def _scan_refuses_what_it_cannot_decide() -> None:
    named = pins.spellings(_rows())
    for line, why in (
        ("nothing here names an upstream, and `1a2b3c4d` stands alone",
         "an id on a line naming no upstream is not a restatement"),
        ("`1a2b3c4d` comes before `upstream/core` names anything",
         "a name stated after the id decides nothing about it"),
        ("the vendor-CORE fork is a project of its own, at 1a2b3c4d",
         "a name that is the tail of a compound is a different project"),
        ("| Component | `vendor/` | aaa11122ffff | `example/core` |",
         "a table cell naming its upstream last states no pin this parse reads"),
    ):
        ensure(not list(pins.scan("f", [line], named)), f"{why}: {line!r}")


def _scan_takes_the_longest_name() -> None:
    # `core` nests inside `nested-core`, so a line spelling the longer one names one
    # upstream and not two, and the id belongs to the longer.
    named = pins.spellings(_rows())
    found = [(s.ident, s.pin.path) for s in
             pins.scan("f", ["`upstream/nested-core` is at `5e6f7a8b`"], named)]
    ensure(found == [("5e6f7a8b", "upstream/nested-core")],
           f"a nested name must claim its own id once, and the scan read {found}")


def _record_skips_a_fence() -> None:
    # A fenced pipe table under the heading is a picture of a table, so the parse
    # must read past it to the one the section actually carries.
    fenced = """# Third-Party Components

## Pinned as submodules

```console
$ head -3 THIRD-PARTY.md
| Submodule | Upstream | Pin |
| --- | --- | --- |
| `upstream/decoy` | `nobody/decoy` | `dddddddd` |
```

| Submodule | Upstream | Pin |
| --- | --- | --- |
| `upstream/core` | `example/core` | `1a2b3c4d` |
"""
    read = pins.read_record(fenced)
    ensure(read.fault is None, f"the real table must still be read: {read.fault}")
    ensure([(p.path, p.short) for p in read.rows]
           == [("upstream/core", "1a2b3c4d")],
           f"a fenced table must be displayed and not read, and the parse read "
           f"{[(p.path, p.short) for p in read.rows]}")


def _scan_leaves_the_fence_to_its_caller() -> None:
    # Whether a line is displayed rather than read is the caller's, because only the
    # caller knows whether the file is Markdown and, where it is, the corpus already
    # holds the mask. The scan therefore reads every line it is handed.
    named = pins.spellings(_rows())
    lines = ["```console",
             "$ cat lane",
             "upstream/core is at 1a2b3c4d",
             "```",
             "`upstream/nested-core` is at `5e6f7a8b`."]
    found = [(s.line, s.ident) for s in pins.scan("f", lines, named)]
    ensure(found == [(3, "1a2b3c4d"), (5, "5e6f7a8b")],
           f"the scan must read every line handed to it, and it read {found}")
    ensure([s.index for s in pins.scan("f", lines, named)] == [2, 4],
           "each site must carry the 0-based index its caller masks by")


def _spellings_are_longest_first() -> None:
    rows = _rows()
    lengths = [len(needle) for needle, _, _ in pins.spellings(rows)]
    ensure(lengths == sorted(lengths, reverse=True),
           f"the spellings must be tried longest first, got {lengths}")
    every = {spelling for _, spelling, _ in pins.spellings(rows)}
    ensure({"upstream/core", "example/core", "core", "nested-core", "wide",
            "wide_name"} <= every,
           f"each row must offer its path, its upstream and both bare names: {every}")


def _a_file_that_is_not_there() -> None:
    # The parse takes text, so the caller's absent file is the empty string, and the
    # rule reading a record the repository does not carry gets a fault rather than an
    # exception. The tree here is real and empty, which is the shape a checkout with
    # nothing tracked in it has.
    with tempfile.TemporaryDirectory(prefix="vos-test-") as td:
        missing = Path(td) / pins.RECORD
        text = missing.read_text(encoding="utf-8") if missing.is_file() else ""
    read = pins.read_record(text)
    ensure(read.fault is not None and not read.rows,
           "an absent record must be a fault with no rows, not an exception")
    ensure(list(pins.scan("f", [], [])) == [],
           "a file with no lines must yield no sites rather than raising")


def cases() -> list[Case]:
    return [
        Case("reads-its-own-table", _reads_its_own_table),
        Case("stops-at-the-table", _stops_at_the_table),
        Case("columns-are-found-by-name", _columns_are_found_by_name),
        Case("readings-that-have-moved", _readings_that_have_moved),
        Case("a-row-stating-no-id", _a_row_stating_no_id),
        Case("scan-pairs-by-the-nearest-name", _scan_pairs_by_the_nearest_name),
        Case("scan-refuses-what-it-cannot-decide", _scan_refuses_what_it_cannot_decide),
        Case("scan-takes-the-longest-name", _scan_takes_the_longest_name),
        Case("record-skips-a-fence", _record_skips_a_fence),
        Case("scan-leaves-the-fence-to-its-caller", _scan_leaves_the_fence_to_its_caller),
        Case("spellings-are-longest-first", _spellings_are_longest_first),
        Case("a-file-that-is-not-there", _a_file_that_is_not_there),
    ]
