# SPDX-License-Identifier: Apache-2.0
"""glyphs: punctuation the house style forbids, and the encoding damage that mimics it.

The other groups check what a document says. This one checks what it is made of, where
two unrelated faults share one symptom, a wrong character, and neither survives a
rendered read: the em-dash is against house style (the punctuation here is explicit,
so a clause takes a comma, a colon, parentheses, or its own sentence), and mojibake is
UTF-8 read as some single-byte encoding, which leaves a signature worth catching the
moment it lands.

Both are reported per file with the lines to visit, and neither is repaired. An
em-dash is removed by deciding what the sentence meant; a mangled character can only
be restored by whoever knows what it was.

The rule is absolute, and that is a decision rather than an oversight. It stood
failing across nine files for as long as it did because it conflated prose punctuation
with two structural uses that no rewrite can reach: the register's entry header
(`**R-nn-nnn** MUST <U+2014> obligation`) and its section headings (`## Sn <U+2014>
Title`), a delimiter and a title separator, one per requirement and one per section.
Neither has a sentence whose meaning could be decided. Both were changed to ASCII
rather than exempted here, because an exemption is a proviso that must itself be
audited, and a rule with no carve-out is closed by construction: any U+2014 anywhere
is a finding, and a table cell meaning *not applicable* is spelled `n/a` rather than
left as a bare dash.

Every character this module hunts is built from its code point rather than typed. Half
of them are C1 control characters no editor renders, and typing the other half would
put the very glyph this module forbids into the file that forbids it.
"""

import re

from .links import sites

HEADING = "=== glyphs: forbidden punctuation and encoding damage ==="

EM_DASH = chr(0x2014)
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


def _character_class(ranges) -> str:
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
MOJIBAKE_MARKS = tuple(chr(b) for b in LEAD_BYTES) + (REPLACEMENT,)


def _offsets(raw: str, needle: str):
    start = raw.find(needle)
    while start >= 0:
        yield start
        start = raw.find(needle, start + 1)


def _lines_carrying(doc, offsets) -> list[int]:
    """One entry per line, however many hits it carries: the repair is one visit."""
    found: list[int] = []
    last = -1
    for offset in offsets:
        i = doc.line_of(offset)
        if i != last:
            found.append(i + 1)
            last = i
    return found


def run(ctx) -> None:
    rep = ctx.rep
    rep.line(HEADING)

    em_hits: list[str] = []
    mojibake_hits: list[str] = []
    for doc in ctx.corpus.docs:
        dashes = _lines_carrying(doc, _offsets(doc.raw, EM_DASH))
        damage: list[int] = []
        if any(mark in doc.raw for mark in MOJIBAKE_MARKS):
            damage = _lines_carrying(doc, (m.start() for m in MOJIBAKE_RE.finditer(doc.raw)))
        if dashes:
            em_hits.append(sites(doc.name, dashes))
        if damage:
            mojibake_hits.append(sites(doc.name, damage))

    rep.report("K-40", "file(s) carrying an em-dash (U+2014)", em_hits,
               "no em-dash in any document")
    rep.report("K-41", "file(s) carrying mojibake or a replacement character", mojibake_hits,
               "no encoding damage in any document")
    rep.line()
