# SPDX-License-Identifier: Apache-2.0
"""Encoding-damage line accounting, diagnostic equivalence and scan bounds."""

import itertools
import operator
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import SupportsIndex, override

from tests.harness import Case, ensure
from vos import corpus
from vos.checks import Context, glyphs
from vos.register import Artifacts, Register
from vos.report import Reporter


def _prefix_lines(raw: str, offsets: Iterable[int]) -> list[int]:
    """The original prefix-count result, including consecutive-hit deduplication."""
    found: list[int] = []
    last = -1
    for offset in offsets:
        line = raw.count("\n", 0, offset)
        if line != last:
            found.append(line + 1)
            last = line
    return found


def _line_results_equal_prefix_reader() -> None:
    alphabet = ("a", "\n", "\r", glyphs.REPLACEMENT)
    for length in range(6):
        for parts in itertools.product(alphabet, repeat=length):
            raw = "".join(parts)
            offsets = [m.start() for m in glyphs.MOJIBAKE_RE.finditer(raw)]
            got = glyphs._lines_carrying(raw, iter(offsets))
            want = _prefix_lines(raw, offsets)
            ensure(got == want, f"damage lines in {raw!r}: {got!r}, wanted {want!r}")


def _other_offset_orders_retain_results() -> None:
    raw = "first\nsecond\nthird\n"
    for offsets in ([], [0, 0, 5, 6, 6, 12, len(raw)],
                    [12, 0, 12, 6, 0], [-1, 0, -5, 12, -30, 30, 6]):
        got = glyphs._lines_carrying(raw, iter(offsets))
        want = _prefix_lines(raw, offsets)
        ensure(got == want, f"lines for {offsets!r}: {got!r}, wanted {want!r}")


class _CountedText(str):
    __slots__ = ("scanned",)

    def __init__(self, _text: str) -> None:
        self.scanned = 0

    @override
    def count(self, sub: str, start: SupportsIndex | None = 0,
              end: SupportsIndex | None = None, /) -> int:
        first = 0 if start is None else operator.index(start)
        finish = len(self) if end is None else operator.index(end)
        self.scanned += max(0, finish - first)
        return super().count(sub, start) if end is None else super().count(sub, start, end)


def _ordered_hits_scan_each_prefix_character_once() -> None:
    raw = _CountedText(("plain " + glyphs.REPLACEMENT * 2 + "\n") * 1024)
    offsets = (m.start() for m in glyphs.MOJIBAKE_RE.finditer(raw))
    got = glyphs._lines_carrying(raw, offsets)
    ensure(got == list(range(1, 1025)), "dense corruption lost or duplicated a line")
    ensure(raw.scanned <= len(raw),
           f"newline accounting rescanned prefixes: {raw.scanned} characters for {len(raw)}")


def _diagnostics_preserve_order_and_duplicate_suppression() -> None:
    damage = glyphs.REPLACEMENT
    with tempfile.TemporaryDirectory(prefix="vos-glyphs-") as directory:
        root = Path(directory).resolve()
        docs = [corpus.from_text("clean\r\n" + damage * 3 + "\r\n```\r\n" + damage
                                 + "\r\n```\r\n", "docs/a.md"),
                corpus.from_text("healthy\n", "docs/b.md"),
                corpus.from_text((damage + "\n") * 14, "docs/c.md")]
        tree = corpus.Corpus(root, docs, {}, [doc.name for doc in docs])
        rep = Reporter()
        glyphs.run(Context(root, tree, Register(), Artifacts(), rep))
    expected = [glyphs.HEADING,
                "FAIL K-41: 2 file(s) carrying mojibake or a replacement character",
                "       docs/a.md: 2 line(s): 2, 4",
                "       docs/c.md: 14 line(s): 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, and 2 more",
                ""]
    ensure(rep.out == expected, f"encoding diagnostics changed: {rep.out!r}")


def cases() -> list[Case]:
    return [
        Case("line-results-equal-prefix-reader", _line_results_equal_prefix_reader),
        Case("other-offset-orders-retain-results", _other_offset_orders_retain_results),
        Case("ordered-hits-scan-each-prefix-character-once",
             _ordered_hits_scan_each_prefix_character_once),
        Case("diagnostics-preserve-order-and-duplicate-suppression",
             _diagnostics_preserve_order_and_duplicate_suppression),
    ]
