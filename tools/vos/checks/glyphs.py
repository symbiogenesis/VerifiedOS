# SPDX-License-Identifier: Apache-2.0
"""glyphs: the encoding damage a rendered read does not catch.

The other groups check what a document says. This one checks what it is made of:
mojibake is UTF-8 read as some single-byte encoding, and a replacement character is
what a decoder leaves where it gave up. Both render without complaint, so the fault
survives a rendered read and is worth catching the moment it lands.

Damage is reported per file with the lines to visit, and never repaired: a mangled
character can only be restored by whoever knows what it was.

The window is the **whole git index** rather than the `.md` corpus every other group
reads, and that follows from the rule being absolute. The fault is a property of a
file's bytes and not of its prose, so a comment in Sail, in assembly, or in JavaScript
carries it exactly as a paragraph does, and a rule stated with no carve-out that
silently stopped at one suffix would be a carve-out nobody had to audit. A file the
index carries that is not UTF-8 is skipped rather than reported, because the fault
cannot be stated over bytes that are not text. Submodule contents never arrive here at
all: a gitlink carries no file of its own, so an upstream's bytes are out of reach by
construction rather than by an exemption.

Every character this module hunts is built from its code point rather than typed. Half
of them are C1 control characters no editor renders, and typing the rest would put the
very damage this module reports into the file that reports it.
"""

import re
from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING

from vos.report import sites

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== glyphs: encoding damage ==="

REPLACEMENT = chr(0xFFFD)

# A lead byte of a multi-byte UTF-8 sequence, read as Latin-1 or CP1252.
LEAD_BYTES = (0xC2, 0xC3, 0xE2, 0xF0)

# The continuation byte that follows it, read the same way: the whole high half of both
# encodings, so the mangling of any character is caught and not just the common ones.
CONTINUATION_RANGES = (
    (0x0080, 0x00BF),                        # Latin-1's C1 block, read as itself
    (0x0152, 0x0153), (0x0160, 0x0161),      # CP1252's own additions, in code order
    (0x0178, 0x0178), (0x017D, 0x017E),
    (0x0192, 0x0192), (0x02C6, 0x02C6), (0x02DC, 0x02DC),
    (0x2013, 0x2014), (0x2018, 0x201A), (0x201C, 0x201E),
    (0x2020, 0x2022), (0x2026, 0x2026), (0x2030, 0x2030),
    (0x2039, 0x203A), (0x20AC, 0x20AC), (0x2122, 0x2122),
)


def _character_class(ranges: Iterable[tuple[int, int]]) -> str:
    return "".join(chr(lo) if lo == hi else f"{chr(lo)}-{chr(hi)}" for lo, hi in ranges)


MOJIBAKE_RE = re.compile(
    "[" + _character_class((c, c) for c in LEAD_BYTES) + "]"
    "[" + _character_class(CONTINUATION_RANGES) + "]"
    "|" + REPLACEMENT)

# Every alternative the pattern has begins with one of these, so a document carrying
# none of them carries no damage and need not be scanned at all. Both branches are read
# off the pattern's own constants rather than restated, so the shortcut cannot come to
# admit a character the pattern would have caught. Nearly every document takes it, and
# the scan is a twentieth of what it was.
MOJIBAKE_MARKS = (*(chr(b) for b in LEAD_BYTES), REPLACEMENT)


def _lines_carrying(raw: str, offsets: Iterable[int]) -> list[int]:
    """One entry per line, however many hits it carries: the repair is one visit."""
    found: list[int] = []
    last = -1
    for offset in offsets:
        i = raw.count("\n", 0, offset)
        if i != last:
            found.append(i + 1)
            last = i
    return found


def _texts(ctx: Context) -> Iterator[tuple[str, str]]:
    """Every tracked file, as text, in the index's own order.

    A document is read from the corpus rather than from disk a second time, because it
    is already in memory and its bytes are the same bytes. Everything else is read
    here, and a file that will not decode as UTF-8 is skipped: it is not text, so
    the fault below is not a thing that could be said about it.
    """
    for rel in ctx.corpus.tracked:
        doc = ctx.corpus.get(rel)
        if doc is not None:
            yield rel, doc.raw
            continue
        try:
            yield rel, (ctx.corpus.root / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)

    mojibake_hits: list[str] = []
    for name, raw in _texts(ctx):
        if not any(mark in raw for mark in MOJIBAKE_MARKS):
            continue
        damage = _lines_carrying(raw, (m.start() for m in MOJIBAKE_RE.finditer(raw)))
        if damage:
            mojibake_hits.append(sites(name, damage))

    rep.report("K-41", "file(s) carrying mojibake or a replacement character", mojibake_hits,
               "no encoding damage in any tracked file")
    rep.line()
