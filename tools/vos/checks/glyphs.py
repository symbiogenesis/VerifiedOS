# SPDX-License-Identifier: Apache-2.0
"""Check all tracked UTF-8 files (including gzip-compressed evidence) for mojibake and `U+FFFD` (`K-41`).

Scans every UTF-8 file in the Git index for replacement characters (`U+FFFD`) and
multi-byte UTF-8 sequences misdecoded as Latin-1 or CP1252. Non-UTF-8 binary files are
skipped; `.gz` files under `docs/implementation/retained-evidence/` are decompressed
before scanning. `K-41` is never auto-repaired.
"""

import re
import zlib
from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, cast

from vos import corpus, pins, retained
from vos.report import sites

from .interims import archive_needles

if TYPE_CHECKING:
    from . import Context

HEADING = "=== glyphs: encoding damage ==="

REPLACEMENT = chr(0xFFFD)

# Lead bytes of multi-byte UTF-8 sequences when misdecoded as Latin-1 or CP1252.
LEAD_BYTES = (0xC2, 0xC3, 0xE2, 0xF0)

# Continuation code points in Latin-1 (C1 block) and CP1252.
CONTINUATION_RANGES = (
    (0x0080, 0x00BF),
    (0x0152, 0x0153), (0x0160, 0x0161),
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

# Fast-path prefix characters shared by all `MOJIBAKE_RE` alternatives.
MOJIBAKE_MARKS = (*(chr(b) for b in LEAD_BYTES), REPLACEMENT)


def _lines_carrying(raw: str, offsets: Iterable[int]) -> list[int]:
    """Return deduplicated 1-based line numbers for `offsets` in `raw`."""
    found: list[int] = []
    last = -1
    at = line = 0
    for offset in offsets:
        if offset < at or offset < 0 or at < 0:
            line = raw.count("\n", 0, offset)
        else:
            line += raw.count("\n", at, offset)
        at = offset
        if line != last:
            found.append(line + 1)
            last = line
    return found


def _texts(ctx: Context) -> Iterator[tuple[str, str]]:
    """Every tracked file, as text, in the index's own order.

    A document is read from the corpus rather than from disk a second time, because it
    is already in memory and its bytes are the same bytes. Everything else is read
    here, and a file that will not decode as UTF-8 is skipped: it is not text, so
    the fault below is not a thing that could be said about it.
    """
    names: tuple[str, ...] | None = None
    sensitive, folded = archive_needles()
    glyph_needles = tuple(mark.encode("utf-8") for mark in MOJIBAKE_MARKS)
    for rel in ctx.corpus.tracked:
        doc = ctx.corpus.get(rel)
        if doc is not None:
            yield rel, doc.raw
            continue
        try:
            if rel.startswith(corpus.COMPRESSED_EVIDENCE) and rel.endswith(".gz"):
                blob = (ctx.root / rel).read_bytes()
                if names is None:
                    names = tuple(needle for needle, _, _ in
                                  pins.spellings(pins.read_record(ctx.text(pins.RECORD)).rows))
                cache = cast(retained.Cache, ctx.shared.setdefault("retained_scan", retained.Cache()))
                try:
                    facts = cache.scan(rel, blob, names, sensitive, folded, glyphs=glyph_needles)
                except OSError, EOFError, ValueError, zlib.error:
                    pass
                else:
                    if facts.glyph is False:
                        continue
                blob = corpus.gzip_contents(blob)
            else:
                blob = corpus.scan_bytes(ctx.corpus.root, rel)
            # Every damage marker is non-ASCII. This also avoids allocating a
            # decoded copy of a large, undamaged ASCII proof reading.
            if blob.isascii():
                continue
            yield rel, blob.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        except UnicodeDecodeError, OSError, EOFError, ValueError, zlib.error:
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
