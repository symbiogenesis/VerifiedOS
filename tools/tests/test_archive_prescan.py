# SPDX-License-Identifier: Apache-2.0
"""Small archive fixtures prove absence optimization preserves audit boundaries."""

import gzip
import re
from dataclasses import replace
from itertools import product
from unittest.mock import patch

from tests.harness import Case, ensure, sandbox_tree
from vos import corpus, literalsearch, pins, retained
from vos.checks import Context, glyphs, interims
from vos.checks import pins as pin_checks
from vos.register import REGISTER, read_artifacts, read_register
from vos.report import Reporter


def _names() -> list[tuple[str, str, pins.Pin]]:
    return pins.spellings([pins.Pin("upstream/core", "example/core", "123abcd", 1),
                           pins.Pin("upstream/nested-core", "other/nested-core", "456abcd", 2)])


def _compiled_boundaries_match_the_literal_oracle() -> None:
    names = ("core", "core/core", "with.dot", "a+b")
    patterns = pins.name_patterns(names)
    matcher = literalsearch.compile_names(names)

    def reference(text: str, first: bool, final: bool) -> bool:
        low = text.lower()
        for name in names:
            at = low.find(name)
            while at >= 0:
                end = at + len(name)
                before = low[at - 1] if at else " "
                after = low[end] if end < len(low) else " "
                if ((at or first) and (end < len(low) or final)
                        and not (before.isalnum() or before in "_-")
                        and not (after.isalnum() or after == "_")):
                    return True
                at = low.find(name, at + 1)
        return False

    boundaries = ["", " ", "_", "-", "/", ".", "a", "7", "é", "中", "\u0661", "Ⅳ", "²", "\u0301", "\n"]
    for before, after, name, first, final in product(boundaries, boundaries, names, (False, True), (False, True)):
        text = before + name + after
        for prepared in (None, matcher):
            ensure(retained._bounded_name(text, patterns, first=first, final=final, matcher=prepared)
                   == reference(text, first, final), "compiled name boundaries differ from the literal oracle")
    for text in ("core/core/core ", "core_helper " * 200 + "core ", "a+b a+b", "with.dot_ with.dot "):
        for first, final in product((False, True), repeat=2):
            for prepared in (None, matcher):
                ensure(retained._bounded_name(text, patterns, first=first, final=final, matcher=prepared)
                       == reference(text, first, final), "overlapping names or dense false prefixes lost a candidate")
    lines = [before + name + after for before, after, name in product(boundaries, boundaries, names)
             if "\n" not in before + after]
    lines.extend(("core_helper " * 200, "core/core/core ", "with.dot_ with.dot ", "a+b a+b"))
    text = "\n".join(lines)
    expected = [index for index, line in enumerate(lines) if reference(line, True, True)]
    for prepared in (None, matcher):
        actual = list(pins.candidate_lines(text, names, patterns=patterns, matcher=prepared))
        ensure([index for index, _, _ in actual] == expected,
               "candidate-line boundaries differ from the literal oracle")
        ensure(all(text[start:end] == lines[index] for index, start, end in actual),
               "candidate-line offsets changed at Unicode or overlapping names")
    # A longer literal at an unknown right edge must not hide a valid shorter
    # literal at the same start. The terminal constraint belongs inside the trie.
    ensure(matcher.present("core/core", first=True, final=False),
           "unknown window edge hid the shorter same-start name")
    stale = literalsearch.compile_names(("unrelated",))
    ensure(retained._bounded_name("core", patterns, first=True, final=True, matcher=stale),
           "a compiled matcher for different names hid a current spelling")
    ensure(list(pins.candidate_lines("core 123abcd", names, matcher=stale)) == [(0, 0, 12)],
           "a stale candidate program hid a current source line")
    named = _names()
    ensure(list(pins.scan_text("fixture", "core 123abcd", named, matcher=stale))
           == list(pins._scan_ids("fixture", "core 123abcd", named)),
           "an attribution call reused a program for different names")

    class OnlyMatch:
        def __init__(self, program: re.Pattern[str]) -> None:
            self.program = program
            self.calls = 0

        def match(self, source: str, pos: int = 0) -> re.Match[str] | None:
            self.calls += 1
            return self.program.match(source, pos)

        def search(self, source: str, pos: int = 0) -> None:
            raise AssertionError("word skipping must not retry complete suffix scans")

    complete, partial = OnlyMatch(matcher.complete), OnlyMatch(matcher.known_right)
    controlled = replace(matcher, complete=complete, known_right=partial,
                         ascii_complete=complete, ascii_known_right=partial)
    ensure(not controlled.present("ordinary words " * 100, first=True, final=True)
           and complete.calls == 1, "an absent name must take one anchored scan")
    ensure(controlled.present("core/core", first=True, final=False) and partial.calls == 1,
           "nonfinal matching must take one anchored scan")
    complete.calls = 0
    ensure([index for index, _, _ in controlled.lines("ordinary\ncore 123abcd\nmore\na+b 123abcd\ntrailing")]
           == [1, 3] and complete.calls == 3,
           "complete lines must use one forward match per candidate and final absence")
    for first_names in (("0core", "9core"), ("_core", "-core"), ("a+b", "z.core", "-core"),
                        ("foo", "foo-bar", "foo/bar", "foo+"), ("k", "core", "-core")):
        guarded = literalsearch.compile_names(first_names)
        ensure(guarded.complete.groups == guarded.known_right.groups == 1,
               "first-character filtering changed the candidate capture")
        for name, before, after in product(first_names, boundaries, boundaries):
            text = before + name + after
            for final in (False, True):
                terminal = r"(?!\w)" if final else r"(?=\W)"
                root = literalsearch.expression(
                    literalsearch.build(tuple(n.encode("ascii") for n in first_names)), terminal.encode()).decode()
                for pos in range(len(text) + 1):
                    expected_span = re.compile(root).search(text, pos)
                    ensure(guarded._span(text, pos=pos, final=final)
                           == (expected_span.span() if expected_span is not None else None),
                           "first-character filtering changed an arbitrary-position candidate")


def _ascii_and_unicode_programs_keep_all_offset_boundaries() -> None:
    names = ("core", "core/core", "-core", "foo", "foo-bar", "foo/bar", "foo+", "k")
    matcher = literalsearch.compile_names(names)
    programs = {final: re.compile(literalsearch.expression(
        literalsearch.build(tuple(name.encode("ascii") for name in names)),
        b"(?!\\w)" if final else b"(?=\\W)").decode("ascii")) for final in (False, True)}
    # Exercise every offset, including interiors of words and names containing
    # separators. A shorter same-start spelling must survive unknown EOF edges.
    samples = ["", "ordinary", "core/core", "foo/bar foo-bar foo+", "-core core-", "core_core",
               "xxcore core", "écore core中", "²core coreⅣ", "中-core/core é k", "K core",
               "foo+core/core", "foo-bar/core foo/bar-core", "\x00core\nfoo\r\ncore/core"]
    samples.extend("".join(chars) for chars in product(("a", "-", "/", " ", "é"), repeat=3))
    for sample in samples:
        low = sample.lower()
        for final in (False, True):
            for pos in range(len(low) + 1):
                expected = programs[final].search(low, pos)
                span = expected.span() if expected is not None else None
                ensure(matcher._span(low, pos=pos, final=final) == span,
                       "word-boundary hoisting or ASCII specialization changed a candidate")
                if low.isascii():
                    unicode_program = matcher.complete if final else matcher.known_right
                    unicode_match = unicode_program.match(low, pos)
                    ensure((unicode_match.span(1) if unicode_match is not None else None) == span,
                           "Unicode and ASCII programs disagree on an ASCII source")
        for first, final in product((False, True), repeat=2):
            expected = programs[final].search(low, 0 if first else 1)
            ensure(matcher.present(sample, first=first, final=final) == (expected is not None),
                   "lowercase or streaming window edges changed a presence decision")
    # Program selection is decided from the complete lowered window. Kelvin's
    # length-preserving lower is ASCII; expanding lowercase retains the refusal.
    ensure(matcher.present("K", first=True, final=True), "length-preserving lowercase lost an ASCII name")
    for sample in ("İcore", "coreİ", "core İ"):
        try:
            matcher.present(sample, first=True, final=True)
        except literalsearch.LegacyRequiredError:
            pass
        else:
            raise AssertionError("expanding lowercase entered an offset-based matcher")
    short_names = ("a", "ab", "a+b", "a-b", "a/b", "-a")
    short = literalsearch.compile_names(short_names)
    for final in (False, True):
        oracle = re.compile(literalsearch.expression(
            literalsearch.build(tuple(name.encode("ascii") for name in short_names)),
            b"(?!\\w)" if final else b"(?=\\W)").decode("ascii"))
        for size in range(5):
            for characters in product(("a", "b", "-", "+", "/", " ", "é"), repeat=size):
                source = "".join(characters)
                for pos in range(len(source) + 1):
                    expected = oracle.search(source, pos)
                    ensure(short._span(source, pos=pos, final=final)
                           == (expected.span() if expected is not None else None),
                           "exhaustive word and punctuation offsets disagree with the frozen oracle")


def _literal_searches_and_unsupported_shapes_keep_the_oracle() -> None:
    datasets: list[tuple[tuple[bytes, ...], tuple[bytes, ...]]] = [
        ((), ()), ((b"Raw", b"R+", b"\x00\xff"), (b"fold", b"FOLD", b"with.dot")),
        (tuple(bytes((value,)) for value in (0, 10, 127, 128, 255)), (b"long/word",))]
    samples = [b"", b"ordinary ASCII", b"Raw FOLD", b"rAw fold", b"R+ with.dot", b"\x00\xff",
               bytes(range(256)), b"long/word", b"before Ra", b"w FOLD after"]
    for raw, folded in datasets:
        sensitive = tuple(raw)
        for sample in samples:
            expected = any(needle in sample for needle in sensitive) or any(needle in sample.lower() for needle in folded)
            for size in (1, 3, 17):
                facts = retained.prescan(gzip.compress(sample), (), sensitive, folded, chunk_size=size)
                ensure(facts.lineage == expected, "byte searches lost a cross-chunk or non-ASCII literal")
    for names in ((), ("",), ("CORE",), ("é",), ("core\nother",), ("x" * 65,),
                  ("x",) * 257, ("x" * 32,) * 129, ("/core",), (".core",), ("+core",)):
        try:
            literalsearch.compile_names(names)
        except literalsearch.LegacyRequiredError:
            pass
        else:
            raise AssertionError("unsupported name set silently entered the optimized matcher")
    for literals in ((b"",), (b"x" * 65,), (b"x",) * 257, (b"x" * 32,) * 129):
        ensure(retained.prescan(gzip.compress(b"x"), (), literals, ()).lineage
               == any(needle in b"x" for needle in literals), "byte search changed an unusual literal population")
    with patch.object(literalsearch.re, "compile", side_effect=RecursionError("fixture")):
        try:
            literalsearch.compile_names(("core",))
        except literalsearch.LegacyRequiredError:
            pass
        else:
            raise AssertionError("compilation failure became an absence verdict")
    broken = gzip.compress(b"core 123abcd\nRaw\n") + gzip.compress(b"tail")[:-3]
    with patch.object(literalsearch, "compile_names", side_effect=literalsearch.LegacyRequiredError("fixture")):
        try:
            retained.prescan(broken, ("core",), (b"Raw",), (), chunk_size=3)
        except (OSError, EOFError, ValueError):
            pass
        else:
            raise AssertionError("matcher fallback hid corruption in a later gzip member")


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
    for needles, raw, expected in ((markers, b"ASCII source", False),
                                   ((b"damage",), b"ASCII damage", True),
                                   ((b"",), b"ASCII source", True)):
        for size in (1, 3, 256):
            facts = retained.prescan(gzip.compress(raw), (), (), (), glyphs=needles, chunk_size=size)
            ensure(facts.glyph is expected, "ASCII glyph shortcut changed a generic needle's result")
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
    return [Case("compiled-boundaries-match-literal-oracle", _compiled_boundaries_match_the_literal_oracle),
            Case("ascii-and-unicode-programs-keep-all-offset-boundaries", _ascii_and_unicode_programs_keep_all_offset_boundaries),
            Case("literal-searches-and-unsupported-shapes-keep-oracle", _literal_searches_and_unsupported_shapes_keep_the_oracle),
            Case("pin-boundaries-and-chunks", _pin_boundaries_and_chunks),
            Case("lineage-candidates-across-chunks", _lineage_candidates_across_chunks),
            Case("members-headers-and-corruption", _members_headers_and_corruption),
            Case("unicode-fallback-is-not-absence", _unicode_fallback_is_not_absence),
            Case("cache-requires-actual-bytes-and-matchers", _cache_requires_actual_bytes_and_matchers),
            Case("sparse-pin-candidates-preserve-all-sites", _sparse_pin_candidates_preserve_all_sites),
            Case("glyph-candidates-cover-chunks-and-share-facts", _glyph_candidates_cover_chunks_and_share_facts),
            Case("checks-preserve-results-and-refresh-bytes", _checks_preserve_results_and_refresh_bytes)]
