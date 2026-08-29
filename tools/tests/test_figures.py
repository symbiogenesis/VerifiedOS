# SPDX-License-Identifier: Apache-2.0
"""The figure engine, and the closure that makes one `--fix` a fixpoint.

A repair rewrites a site to `restore_case(site, expected)` with the same pattern
that found it, so `--fix` converges in one application only if every registered
pattern re-matches its own expected spelling: a pattern whose capture cannot
spell the value it would write repairs a document into unfindability, and the
next run reports the figure as stated nowhere. That closure is proven here over
every registered claim at the live tree's current values, beside the cheapest
direct proof of the anchor-window machinery: `find_all` must be `re.finditer`'s
own answer, differing only in the order of the search.

The live-tree cases read the real corpus and never write; the values they check
against are recomputed from the artifacts each run, so nothing here needs
rerecording when a count moves.
"""

import functools
import re

from tests.harness import Case, ensure
from vos import corpus as corpus_mod
from vos import figures
from vos.checks import Context, confers, counts, views
from vos.register import Register, read_artifacts, read_register
from vos.report import Reporter


@functools.cache
def _live() -> Context:
    """The live tree's Context with the quantity table computed, once per run.

    Read-only: the three groups run without fix, so nothing reaches ctx.fixed and
    nothing touches disk. views and confers run first because counts reads their
    shared keys, the same dependency order check.py declares.
    """
    root = corpus_mod.find_root()
    corpus = corpus_mod.load(root)
    reg = read_register(corpus)
    art = read_artifacts(corpus)
    ctx = Context(root=root, corpus=corpus, reg=reg, art=art, rep=Reporter())
    views.run(ctx)
    confers.run(ctx)
    counts.run(ctx)
    return ctx


def _tag_expected(reg: Register) -> dict[str, str]:
    """The tag-plane values, from the two register fields that fix them.

    Deliberately the same arithmetic counts_tagplane.tag_plane performs: the test must
    compute the expected spellings independently of the code under test, and a
    drift between the two is this test failing loudly, which is the point.
    """
    granule = counts.GRANULE_RE.search(reg.body.get("R-15-203", ""))
    payload = counts.PAYLOAD_RE.search(reg.body.get("R-15-181a", ""))
    if granule is None or payload is None:
        raise AssertionError("the register no longer fixes the granule and payload "
                             "the tag-plane claims derive from")
    g, p = int(granule.group(1)), int(payload.group(1))
    return {
        "plane-exact": figures.quantize(100 / g, 4),
        "plane-short": figures.quantize(100 / g, 2),
        "half-short": figures.quantize(100 / (2 * g), 2),
        "mb-per-gb": figures.quantize(1000 / g, 1),
        "payload": str(p),
        "tags-per-codeword": figures.words(p // g),
    }


def _closure(file: str, pattern: str, expected: str, raw: str, what: str) -> None:
    """One claim's fixpoint: the canonical rewrite is re-found by its own pattern."""
    hits = figures.find_all(pattern, raw)
    ensure(len(hits) > 0, f"{what}: /{pattern}/ finds no site in {file}")
    # the exact rewrite resolve_claim performs under --fix
    repaired = re.sub(pattern, lambda m: figures.restore_case(m.group(), expected), raw)
    again = figures.find_all(pattern, repaired)
    ensure(len(again) == len(hits),
           f"{what}: the repair changed the site count in {file} from "
           f"{len(hits)} to {len(again)}, so a second --fix would not converge")
    ensure(all(h.group() == figures.restore_case(h.group(), expected) for h in again),
           f"{what}: /{pattern}/ cannot re-match its own expected spelling "
           f"'{expected}' in {file}")


def _words_forms() -> None:
    ensure(figures.words(0) == "zero" and figures.words(13) == "thirteen",
           "the under-twenty forms are the ones table")
    ensure(figures.words(20) == "twenty" and figures.words(23) == "twenty-three"
           and figures.words(99) == "ninety-nine",
           "a non-round form above twenty is hyphenated")
    try:
        figures.words(100)
    except ValueError:
        return
    raise AssertionError("words(100) must raise: the counts group's overflow "
                         "finding stands on that refusal")


def _distinctive_forms() -> None:
    ensure(figures.distinctive(5) is None, "a small count collides with prose")
    ensure(figures.distinctive(11) == "eleven" and figures.distinctive(100) == "100",
           "eleven and up in words, one hundred and up in digits")


def _rounding() -> None:
    # golden arithmetic, not recorded behavior: each value is the documented rule
    # (ROUND_HALF_UP, away from zero) applied by hand
    ensure(figures.quantize(2.5, 0) == "3", "a tie rounds away from zero")
    ensure(figures.quantize(0.125, 2) == "0.13", "a tie rounds away at any scale")
    ensure(figures.quantize(100 / 64, 4) == "1.5625", "an exact ratio is untouched")
    ensure(figures.share(12.5, 100, 0) == 13.0, "share rounds the same way")
    ensure(figures.share(1, 0, 1) == 0.0, "an empty total is a zero share, not a crash")
    ensure(figures.percent(1, 3, 1) == "33.3", "percent renders share at its digits")
    ensure(figures.format_hours(1070.3) == "1,070.3", "hours keep their comma grouping")
    ensure(figures.format_hours(12.0) == "12", "a whole number of hours drops the .0")


def _restore_case() -> None:
    ensure(figures.restore_case("Twelve", "eleven") == "Eleven",
           "a sentence's own capital survives the repair")
    ensure(figures.restore_case("twelve", "eleven") == "eleven",
           "a lowercase site takes the expected spelling verbatim")
    ensure(figures.restore_case("12", "eleven") == "eleven",
           "a digit opening confers no capital")
    once = figures.restore_case("Twelve", "eleven")
    ensure(figures.restore_case(once, "eleven") == once,
           "restore_case is idempotent, so re-repair rewrites nothing")


def _anchor_refusals() -> None:
    # what the phrase reading refuses rather than guesses at
    ensure(figures.anchor(r"a|b") == "", "an alternation has no required phrase")
    ensure(figures.anchor(r"(x) y") == "", "a group a quantifier could delete is refused")
    ensure(figures.anchor(r"ab{2}c") == "", "a counted repetition is not text")
    ensure(figures.anchor(r"(?i:seven) cells") == "",
           "a scoped flag group is refused, so no phrase is searched case-blind")


def _anchor_extraction() -> None:
    ensure(figures.anchor(r"plain phrase") == "plain phrase",
           "a literal pattern is its own phrase")
    ensure(figures.anchor(r"a\.b") == "a.b", "an escape stands for its character")
    got = figures.anchor(r"(?<=granule is )[\d.]+(?= MB per GB of data)")
    ensure(got == " MB per GB of data",
           f"a positive lookaround's text counts, and the longest run wins: {got!r}")
    got = figures.anchor(r"(?<=below the ≤\u2009)\d+k(?=-line target)")
    ensure(got == "-line target",
           f"a hex escape's digits are its spelling, never document text: {got!r}")


def _no_registered_flags() -> None:
    # anchor() strips a bare flag group before reading the phrase, so a flagged
    # pattern would be proposed by a case-sensitive substring scan its own flag
    # contradicts; what keeps that sound is that no registered claim carries one
    flagged = [p for _f, _q, _s, p in counts.CLAIMS if figures._FLAGS_RE.search(p)]
    flagged += [p for _f, _k, p in counts.TAG_PLANE if figures._FLAGS_RE.search(p)]
    ensure(flagged == [],
           f"registered claim patterns must carry no flag group: {flagged!r}")


def _find_all_equals_finditer() -> None:
    # the anchor-window bargain, proven the direct way: over every registered
    # pattern and its own live document, the windowed search is the plain scan's
    # answer, span for span
    ctx = _live()
    seen = 0
    for file, pattern in ([(f, p) for f, _q, _s, p in counts.CLAIMS]
                          + [(f, p) for f, _k, p in counts.TAG_PLANE]):
        raw = ctx.corpus.by_name[file].raw
        windowed = [(m.start(), m.end(), m.group())
                    for m in figures.find_all(pattern, raw)]
        plain = [(m.start(), m.end(), m.group())
                 for m in re.finditer(pattern, raw)]
        ensure(windowed == plain,
               f"find_all diverges from finditer for /{pattern}/ in {file}: "
               f"{windowed!r} != {plain!r}")
        seen += len(plain)
    ensure(seen > 0, "the registered patterns must match somewhere, or this proved "
                     "nothing")


def _claims_closure() -> None:
    ctx = _live()
    for file, quantity, style, pattern in counts.CLAIMS:
        expected = (figures.words(ctx.q[quantity]) if style == "words"
                    else str(ctx.q[quantity]))
        _closure(file, pattern, expected, ctx.corpus.by_name[file].raw,
                 f"claim '{quantity}'")


def _tag_plane_closure() -> None:
    ctx = _live()
    expected = _tag_expected(ctx.reg)
    for file, key, pattern in counts.TAG_PLANE:
        _closure(file, pattern, expected[key], ctx.corpus.by_name[file].raw,
                 f"tag-plane '{key}'")


def _hyphenated_capture() -> None:
    # the tags-per-codeword capture is [\w-]+ rather than \w+, because its value
    # is figures.words of a ratio and every non-round word form from twenty-one up
    # is hyphenated: a bare \w+ would repair a grown quantity to a spelling its
    # own pattern could no longer find
    pattern = next(p for _f, k, p in counts.TAG_PLANE if k == "tags-per-codeword")
    raw = "the codeword is unchanged at 92 data bits carrying twenty-three tag bits"
    hits = figures.find_all(pattern, raw)
    ensure(len(hits) == 1 and hits[0].group() == "twenty-three",
           f"the capture must span a hyphenated word form whole: {hits!r}")
    _closure("synthetic", pattern, figures.words(46), raw, "hyphenated tags-per-codeword")


def cases() -> list[Case]:
    return [
        Case("words-forms", _words_forms),
        Case("distinctive-forms", _distinctive_forms),
        Case("rounding", _rounding),
        Case("restore-case", _restore_case),
        Case("anchor-refusals", _anchor_refusals),
        Case("anchor-extraction", _anchor_extraction),
        Case("no-registered-flags", _no_registered_flags),
        Case("find-all-equals-finditer", _find_all_equals_finditer),
        Case("claims-closure", _claims_closure),
        Case("tag-plane-closure", _tag_plane_closure),
        Case("hyphenated-capture", _hyphenated_capture),
    ]
