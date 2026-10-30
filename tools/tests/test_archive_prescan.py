# SPDX-License-Identifier: Apache-2.0
"""Small archive fixtures prove absence optimization preserves audit boundaries."""

import gzip
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import corpus, pins, retained
from vos.checks import Context, glyphs, interims
from vos.checks import pins as pin_checks
from vos.register import REGISTER, read_artifacts, read_register
from vos.report import Reporter


def _names() -> list[tuple[str, str, pins.Pin]]:
    return pins.spellings([pins.Pin("upstream/core", "example/core", "123abcd", 1),
                           pins.Pin("upstream/nested-core", "other/nested-core", "456abcd", 2)])


def _pin_boundaries_and_chunks() -> None:
    named = _names()
    names = tuple(needle for needle, _, _ in named)
    samples = ["", "elem", "score", "-core", "core_", "core7", "CORE", "core-",
               "écore", "core中", "é core 中", "\u212a core", "nested-core",
               "other/nested-core", "core\r\n", "core\r", "prefix core suffix"]
    for text in samples:
        expected = bool(pins._named(text, named))
        blob = gzip.compress(text.encode("utf-8"))
        for size in range(1, len(text.encode("utf-8")) + 3):
            result = retained.prescan(blob, names, (), (), chunk_size=size)
            ensure(result.pin_name == expected,
                   f"bounded-name presence differs for {text!r}, chunk {size}: {result}")


def _lineage_candidates_across_chunks() -> None:
    sensitive, folded = interims.archive_needles()
    for token in interims.TOKENS:
        raw = b"prefix " + token.name.encode("utf-8") + b" suffix"
        ensure(bool(interims.hits(raw)), f"the fixture must cite {token.name}")
        for size in range(1, len(raw) + 2):
            result = retained.prescan(gzip.compress(raw), (), sensitive, folded,
                                      chunk_size=size)
            ensure(result.lineage, f"lost lineage candidate {token.name} at chunk {size}")
    result = retained.prescan(gzip.compress(b"only ordinary arithmetic\n"), (),
                              sensitive, folded, chunk_size=3)
    ensure(not result.lineage, "ordinary text must prove lineage-needle absence")


def _members_headers_and_corruption() -> None:
    names = ("core",)
    first = gzip.compress(b"only prefix ")
    second = gzip.compress(b"core")
    ensure(retained.prescan(first + second + b"\x00\x00", names, (), (), chunk_size=2).pin_name,
           "concatenated members and permitted zero padding must retain their contents")
    for blob in (b"", b"plain", first[:-4], first + b"garbage", first[:-1] + b"\xff"):
        try:
            retained.prescan(blob, names, (), (), chunk_size=2)
        except (OSError, EOFError, ValueError):
            pass
        else:
            raise AssertionError("malformed gzip was accepted as an absence")
    early_candidates = gzip.compress(b"core HACL*\n")
    bad_tail = gzip.compress(b"second member")[:-4]
    try:
        retained.prescan(early_candidates + bad_tail, names, (b"HACL",), (), chunk_size=2)
    except (OSError, EOFError, ValueError):
        pass
    else:
        raise AssertionError("early positive facts must not bypass later member integrity")


def _unicode_fallback_is_not_absence() -> None:
    for raw, names in (("İ no matching name".encode(), ("core",)),
                       (b"invalid \xff text", ("core",))):
        facts = retained.prescan(gzip.compress(raw), names, (), (), chunk_size=2)
        ensure(facts.pin_name and facts.pin_text is None,
               "unsupported Unicode must require the complete pin parser, never absence")
    for raw, names in (("Σ text".encode(), ("\u03c3",)),):
        try:
            retained.prescan(gzip.compress(raw), names, (), (), chunk_size=2)
        except retained.UnsupportedScanError:
            pass
        else:
            raise AssertionError("unsupported Unicode must retain the complete parser")


def _cache_requires_actual_bytes_and_matchers() -> None:
    cache = retained.Cache()
    first = gzip.compress(b"ordinary text", mtime=0)
    second = gzip.compress(b"CORE", mtime=0)
    with patch.object(retained, "prescan", wraps=retained.prescan) as scan:
        ensure(not cache.scan("evidence", first, ("core",), (), (b"hacl",)).pin_name,
               "first immutable input contains no pin")
        ensure(not cache.scan("evidence", bytes(first), (), (), (b"hacl",)).lineage,
               "later lineage consumer may reuse the same archive's facts")
        ensure(scan.call_count == 1, "unchanged explicit bytes must share one pass")
        ensure(cache.scan("evidence", second, ("core",), (), (b"hacl",)).pin_name,
               "changed bytes must invalidate the same path")
        ensure(not cache.scan("evidence", second, ("other",), (), (b"hacl",)).pin_name,
               "changed pin matcher input must invalidate the prior answer")
        ensure(scan.call_count == 3, "each new immutable input needs its own scan")
        cache.scan("evidence", second, (), (), (b"core",))
        ensure(scan.call_count == 4, "changed lineage matcher input must invalidate")
    bad = gzip.compress(b"broken")[:-3]
    for _ in range(2):
        try:
            cache.scan("broken", bad, (), (), ())
        except (OSError, EOFError, ValueError):
            pass
        else:
            raise AssertionError("failed archive became a successful cache entry")
    ensure("broken" not in cache._entries, "failures must not enter the facts cache")


def _sparse_pin_candidates_preserve_all_sites() -> None:
    named = _names()
    names = tuple(needle for needle, _, _ in named)
    samples = ["core\n123abcd\n", "header core\n" + "ordinary abcdef0\n" * 25,
               "ordinary\ncore 123abcd nested-core 456abcd\n\nCORE-123abcd\n",
               "core_ 123abcd\n-core 123abcd\nécore 123abcd\ncore中 123abcd\n",
               "é core 123abcd\ncore 123abcd 456abcd\ntrailing core 123abcd"]
    for sample in samples:
        for newline in ("\n", "\r\n", "\r"):
            text = sample.replace("\n", newline)
            normalized = text.replace("\r\n", "\n").replace("\r", "\n")
            expected = list(pins._scan_ids("fixture", normalized, named))
            blob = gzip.compress(text.encode())
            for size in (1, 2, 7, 31, 256 * 1024):
                facts = retained.prescan(blob, names, (), (), chunk_size=size)
                if facts.pin_text is None:
                    raise AssertionError("requested candidates must be explicit")
                actual = list(pins.scan_text("fixture", facts.pin_text, named))
                ensure(actual == expected,
                       f"sparse source lost sites at chunk {size}, newline {newline!r}")
    for text in ("core 123abcd\ninvalid \xff".encode("latin-1"),
                 "core 123abcd\nİ text".encode()):
        facts = retained.prescan(gzip.compress(text), names, (), (), chunk_size=3)
        ensure(facts.pin_name and facts.pin_text is None,
               "late unsupported text must retain the complete pin reader")
    facts = retained.prescan(gzip.compress(b"core " + b"a" * (1024 * 1024 + 1)), names,
                             (b"HACL",), (), glyphs=(b"damage",))
    ensure(facts.pin_name and facts.pin_text is None and not facts.lineage
           and facts.glyph is False,
           "huge pin lines must preserve independently complete glyph and lineage facts")
    ordinary = b"core_helper " * 100000
    facts = retained.prescan(gzip.compress(ordinary), names, (), (), glyphs=(b"damage",))
    ensure(not facts.pin_name and facts.pin_text is None and facts.glyph is False,
           "huge lines without a bounded spelling must retain complete streaming absence")
    late_name = ordinary + b" core 123abcd"
    facts = retained.prescan(gzip.compress(late_name), names, (), ())
    ensure(facts.pin_name and facts.pin_text is None,
           "a name after sparse fallback must still require the complete pin parser")
    broken = gzip.compress(b"a" * (1024 * 1024 + 1)) + gzip.compress(b"tail")[:-3]
    try:
        retained.prescan(broken, names, (), ())
    except (OSError, EOFError, ValueError):
        pass
    else:
        raise AssertionError("pin fallback must still refuse a corrupt later gzip member")


def _glyph_candidates_cover_chunks_and_share_facts() -> None:
    markers = tuple(mark.encode() for mark in glyphs.MOJIBAKE_MARKS)
    for mark in glyphs.MOJIBAKE_MARKS:
        raw = ("prefix " + mark + " suffix").encode()
        for size in (1, 2, 3, 7):
            facts = retained.prescan(gzip.compress(raw), (), (), (), glyphs=markers,
                                     chunk_size=size)
            ensure(facts.glyph is True, "a glyph marker may cross any chunk boundary")
    evidence = corpus.COMPRESSED_EVIDENCE + "fixture.txt.gz"
    record = ("# Third party\n\n## Pinned as submodules\n\n"
              "| Submodule | Upstream | Pin |\n| --- | --- | --- |\n"
              "| `upstream/core` | `example/core` | `123abcd` |\n"
              "| `upstream/nested-core` | `other/nested-core` | `456abcd` |\n")
    tree = {"README.md": "# Fixture\n", REGISTER: "# Register\n", pins.RECORD: record,
            evidence: "placeholder"}
    with sandbox_tree(tree) as root:
        found = corpus.load(root)
        ctx = Context(root, found, read_register(found), read_artifacts(found), Reporter())
        named = pins.spellings(pins.read_record(record).rows)
        for text in ("ordinary text\n", "core 123abcd\nHACL*\n",
                     "core 123abcd\n" + chr(0xFFFD) + "\n"):
            (root / evidence).write_bytes(gzip.compress(text.encode()))
            with patch.object(retained.Cache, "scan", side_effect=retained.UnsupportedScanError):
                expected = list(glyphs._texts(ctx))
            with patch.object(retained, "prescan", wraps=retained.prescan) as scan:
                actual = list(glyphs._texts(ctx))
                list(pin_checks._sources(ctx, named))
                interims.scan(ctx, {})
                ensure(scan.call_count == 1, "three consumers must share one immutable scan")
            expected_damage = [(rel, glyphs._lines_carrying(raw, (m.start() for m in
                                glyphs.MOJIBAKE_RE.finditer(raw)))) for rel, raw in expected]
            actual_damage = [(rel, glyphs._lines_carrying(raw, (m.start() for m in
                              glyphs.MOJIBAKE_RE.finditer(raw)))) for rel, raw in actual]
            ensure([(rel, lines) for rel, lines in actual_damage if lines]
                   == [(rel, lines) for rel, lines in expected_damage if lines],
                   "shared glyph candidate facts must preserve all exact damage locations")


def _checks_preserve_results_and_refresh_bytes() -> None:
    evidence = corpus.COMPRESSED_EVIDENCE + "fixture.txt.gz"
    named = _names()
    tree = {"README.md": "# Fixture\n", REGISTER: "# Register\n", evidence: "placeholder"}
    with sandbox_tree(tree) as root:
        found = corpus.load(root)
        ctx = Context(root=root, corpus=found, reg=read_register(found),
                      art=read_artifacts(found), rep=Reporter())
        values = [gzip.compress(b"ordinary text\n"),
                  gzip.compress(b"core 123abcd\r\nresting on HACL*\r\n"),
                  gzip.compress("İ core 123abcd\nF⋆\n".encode()),
                  gzip.compress(b"bad \xff text\nHACL*\n"),
                  gzip.compress(b"truncated")[:-4], b"not gzip"]
        for blob in values:
            (root / evidence).write_bytes(blob)
            # The existing full readers supply the independent decision and exact
            # diagnostic oracle. Reuse this context across byte changes so the
            # optimization must invalidate earlier absence and positive facts.
            with patch.object(retained.Cache, "scan", side_effect=retained.UnsupportedScanError):
                expected_pins = list(pin_checks._sources(ctx, named))
                expected_interims = interims.scan(ctx, {})
            actual_pins = list(pin_checks._sources(ctx, named))
            actual_interims = interims.scan(ctx, {})
            # Absence sources may be omitted only when their full pin parse has
            # no restatement; sparse positive sources preserve every complete site.
            def sites(sources: list[tuple[str, str, list[bool]]]) -> list[pins.Site]:
                return [site for file, text, _ in sources
                        for site in pins.scan_text(file, text, named)]
            ensure(sites(actual_pins) == sites(expected_pins), "archive pin decisions changed")
            ensure(actual_interims == expected_interims,
                   "archive lineage decisions or complete diagnostics changed")


def cases() -> list[Case]:
    return [Case("pin-boundaries-and-chunks", _pin_boundaries_and_chunks),
            Case("lineage-candidates-across-chunks", _lineage_candidates_across_chunks),
            Case("members-headers-and-corruption", _members_headers_and_corruption),
            Case("unicode-fallback-is-not-absence", _unicode_fallback_is_not_absence),
            Case("cache-requires-actual-bytes-and-matchers", _cache_requires_actual_bytes_and_matchers),
            Case("sparse-pin-candidates-preserve-all-sites", _sparse_pin_candidates_preserve_all_sites),
            Case("glyph-candidates-cover-chunks-and-share-facts", _glyph_candidates_cover_chunks_and_share_facts),
            Case("checks-preserve-results-and-refresh-bytes", _checks_preserve_results_and_refresh_bytes)]
