# SPDX-License-Identifier: Apache-2.0
"""Derived figures: how one is spelled, found, compared, and repaired.

A *claim* is a file, a pattern capturing a stated figure alone, and the value that
figure must read. That is the unit wherever a figure is asserted in a sentence of its
own and may be asserted in several. Where instead one sentence carries four derived
figures at once, the unit is the sentence: the pattern is anchored to the line, each
figure is a named group, and the sentence is owed exactly one site for the same
reason a total is.

Comparison is on the figure, not on its spelling: commas and capitals are formatting,
and the register writes 1275 where the checklist writes 1,070.3. A site that states
the right figure in the other document's format is therefore not a finding, and a
repair still normalizes it, because the rewrite is driven by the literal text.

A claim is *found* by its phrase rather than by its pattern. Nearly all of a claim is
literal prose, the figure beside it being one short token, and a pattern that opens on
that token has no literal prefix for the regex engine to seek: it is tried at every
offset of a document that runs to hundreds of kilobytes, and backtracks at most of
them. The phrase is read back out of the pattern by `anchor` and found by substring
search, which is a word-at-a-time scan in C, and the pattern is then run only in a
window around each occurrence. The answer is the pattern's own; only the order of the
search is different.
"""

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

# `Context` lives in `vos.checks`, which imports this module. Guarded, so the
# annotations below cost no import at run time and no cycle at any time.
if TYPE_CHECKING:
    from .checks import Context

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty",
         6: "sixty", 7: "seventy", 8: "eighty", 9: "ninety"}


def words(n: int) -> str:
    """The word form of a count, so a claim may read as prose without becoming
    unmaintainable. Past ninety-nine there is no word form worth writing and the
    document is required to state the figure in digits."""
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens = _TENS[n // 10]
        return tens if n % 10 == 0 else f"{tens}-{_ONES[n % 10]}"
    raise ValueError(f"no word form for {n}; state it in digits")


def distinctive(n: int) -> str | None:
    """The spelling of a quantity distinctive enough not to collide with ordinary
    prose: a word form of eleven or more, or three digits and up."""
    if n >= 100:
        return str(n)
    if n >= 11:
        return words(n)
    return None


def restore_case(found: str, expected: str) -> str:
    """A sentence's own capital is the sentence's, not the figure's."""
    if found[:1].isupper() and found[:1].isalpha():
        return expected[:1].upper() + expected[1:]
    return expected


def same_figure(a: str, b: str) -> bool:
    return a.lower().replace(",", "") == b.lower().replace(",", "")


def format_hours(v: float) -> str:
    """Hours read as they are written, the trailing .0 dropped."""
    r = round(v, 1)
    return f"{r:,.0f}" if r == int(r) else f"{r:,.1f}"


def share(v: float, total: float, digits: int) -> float:
    """A percentage, rounded away from zero so a share never reads as smaller than it
    is by the accident of a tie."""
    if total == 0:
        return 0.0
    quantum = Decimal(1).scaleb(-digits)
    return float(Decimal(v / total * 100).quantize(quantum, rounding=ROUND_HALF_UP))


def percent(v: float, total: float, digits: int) -> str:
    return f"{share(v, total, digits):,.{digits}f}"


def quantize(v: float, digits: int) -> str:
    """A derived ratio at a fixed number of decimals, rounded the way `share` rounds.

    `share` is that rule over a percentage. A ratio that is not a percentage, megabytes
    of tag plane per gigabyte of data being the one this exists for, wants the same rule
    and not a second one: away from zero, so a tie never reads smaller than it is.
    """
    quantum = Decimal(1).scaleb(-digits)
    return f"{Decimal(v).quantize(quantum, rounding=ROUND_HALF_UP):,.{digits}f}"


# How much room a claim's pattern is given on either side of its phrase. A claim
# captures one figure standing beside that phrase, so the whole construct is a fragment
# of a single sentence and this is two orders of magnitude more than one needs. A match
# reaching an edge is one the window may have cut, and the document is then read whole
# rather than a partial reading reported.
WINDOW = 4096

# What the phrase reading refuses rather than guesses at: a choice, where neither side
# is required; a negative lookaround, whose text must be absent rather than present; any
# other group, which a quantifier outside it may delete entire; and a counted
# repetition, whose bounds are not text at all.
_UNREAD_RE = re.compile(r"(?<!\\)\|" r"|(?<!\\)\((?!\?=|\?<=)" r"|\)[?*{]" r"|(?<!\\)\{")
_FLAGS_RE = re.compile(r"\(\?[aiLmsux]+\)")
_METACHARACTERS = set(r".^$*+?()[]{}|\\")
# sets rather than strings, so that the empty string the end of a pattern hands back is
# a member of neither
_DELETES_WHAT_PRECEDES = frozenset("?*{")


def _class_end(pattern: str, i: int) -> int:
    """One past the `]` closing the character class that opens at `i`. A `^` may lead
    the class and a `]` written first inside it is a literal, so neither closes it."""
    j = i + 1 + (pattern[i + 1:i + 2] == "^")
    j += pattern[j:j + 1] == "]"
    while j < len(pattern) and pattern[j] != "]":
        j += 2 if pattern[j] == "\\" else 1
    return j + 1


def anchor(pattern: str) -> str:
    """The longest phrase the pattern must match verbatim, or "" where it must match
    none.

    Only what is certainly required is read. A run of literal characters ends at every
    metacharacter, at an escape naming a class rather than a character, and around any
    character a quantifier could delete or repeat; a positive lookaround's text counts,
    because it stands in the document beside the match whether the match consumes it or
    not. A pattern built from anything `_UNREAD_RE` names is answered "", which the
    caller reads as a pattern with no phrase to find it by.
    """
    body = _FLAGS_RE.sub("", pattern)       # a flag group carries no text of its own
    if _UNREAD_RE.search(body):
        return ""

    best = run = ""
    i = 0
    while i < len(body):
        char, width, literal = body[i], 1, False
        if char == "\\":
            # an escape stands for the character it names, unless that character is a
            # letter or a digit, which is how a class or an assertion is spelled
            char, width = body[i + 1:i + 2], 2
            literal = not char.isalnum()
        elif char == "[":
            width = _class_end(body, i) - i
        elif char == "(":
            width = 4 if body.startswith("(?<=", i) else 3
        else:
            literal = char not in _METACHARACTERS

        follows = body[i + width:i + width + 1]
        if literal and follows not in _DELETES_WHAT_PRECEDES:
            run += char
            # a `+` keeps the character it repeats and separates it from the next, which
            # the document need not carry immediately after
            literal = follows != "+"
        if not literal:
            best, run = max(best, run, key=len), ""
        i += width

    return max(best, run, key=len)


def find_all(pattern: str, raw: str) -> list[re.Match[str]]:
    """Every match, reached through the pattern's phrase wherever it has one.

    The phrase proposes the sites and the pattern decides them, so this is the pattern's
    own answer and only the order of the search differs. Windows that overlap are merged,
    so a site lying in two of them is decided once and the matches stay in the order the
    document reads; a match reaching the edge of its window is one the window may have
    cut, and the document is read whole instead of trusting the fragment.
    """
    compiled = re.compile(pattern)
    phrase = anchor(pattern)
    if not phrase:
        return list(compiled.finditer(raw))

    windows: list[list[int]] = []
    site = raw.find(phrase)
    while site >= 0:
        lo, hi = max(0, site - WINDOW), min(len(raw), site + len(phrase) + WINDOW)
        if windows and lo <= windows[-1][1]:
            windows[-1][1] = hi
        else:
            windows.append([lo, hi])
        site = raw.find(phrase, site + 1)

    hits = []
    for lo, hi in windows:
        for m in compiled.finditer(raw, lo, hi):
            if (m.start() == lo and lo > 0) or (m.end() == hi and hi < len(raw)):
                return list(compiled.finditer(raw))
            hits.append(m)
    return hits


@dataclass
class ClaimResult:
    spans: list[re.Match[str]] = field(default_factory=list)
    finding: str | None = None
    fixed: str | None = None


def resolve_claim(ctx: Context, file: str, pattern: str, expected: str,
                  what: str) -> ClaimResult:
    """One figure, found and then either repaired or reported."""
    result = ClaimResult()
    if file not in ctx.corpus:
        result.finding = f"{file} is not in the repository"
        return result

    raw = ctx.text(file)
    hits = find_all(pattern, raw)
    result.spans = hits

    if not hits:
        result.finding = (f"{file}: {what} is stated nowhere /{pattern}/ holds it; "
                          "the wording moved, so re-anchor the claim or drop it")
        return result

    # the repair is the test: a site is rewritten where it does not already read what
    # the repair would write, which catches the wrong figure and the figure written in
    # the other document's format, and leaves a sentence's own capital alone
    stale = [h for h in hits if h.group() != restore_case(h.group(), expected)]
    if ctx.fix:
        if stale:
            ctx.fixed[file] = re.sub(pattern, lambda m: restore_case(m.group(), expected), raw)
            result.fixed = (f"fixed: {file}: {what} {stale[0].group()} -> "
                            f"{restore_case(stale[0].group(), expected)}")
            result.spans = []      # the offsets moved; the caller finds them again
        return result

    # without a repair only the figure is reported: a comma the other document's
    # convention would not use is a formatting difference, and no claim is wrong
    wrong = [h for h in hits if not same_figure(h.group(), expected)]
    if wrong:
        result.finding = (f"{file}: {what} asserted as '{wrong[0].group()}', "
                          f"the artifact gives '{expected}'")
    return result


@dataclass
class LineResult:
    findings: list[str] = field(default_factory=list)
    fixed: list[str] = field(default_factory=list)


def resolve_line(ctx: Context, file: str, pattern: str, expected: dict[str, str],
                 what: str) -> LineResult:
    """One sentence, and every derived figure it carries at once.

    Anchored one figure at a time, each pattern would have to re-encode every figure
    before it on its line as a lookbehind, so one reworded sentence is four patterns to
    re-derive and the last of them states the sentence nearly twice over. One pattern
    per line states the shape once and names each figure it carries, which is also what
    the document means: the sentence is the thing that must agree.
    """
    result = LineResult()
    if file not in ctx.corpus:
        result.findings.append(f"{file} is not in the repository")
        return result

    raw = ctx.text(file)
    hits = list(re.finditer(pattern, raw))
    if len(hits) != 1:
        result.findings.append(
            f"{file}: {what} is stated in {len(hits)} places /{pattern}/ holds it; "
            "the wording moved, so re-anchor the sentence or the pattern")
        return result
    m = hits[0]

    work = []
    for name, want in expected.items():
        found = m.group(name)
        if found is None:
            result.findings.append(
                f"{file}: {what} carries no '{name}' figure where the pattern names one")
            continue
        work.append((name, m.start(name), m.end(name), found, str(want)))

    if not ctx.fix:
        for name, _, _, found, want in work:
            if not same_figure(found, want):
                result.findings.append(
                    f"{file}: {what} states {name} as '{found}', the items give '{want}'")
        return result

    # the groups are rewritten last-first, so replacing one never moves the offsets of
    # the ones still to be written
    text = raw
    for name, start, end, found, want in sorted(work, key=lambda w: w[1], reverse=True):
        if found == want:
            continue
        text = text[:start] + want + text[end:]
        result.fixed.append(f"fixed: {file}: {what} {name} {found} -> {want}")
    if text != raw:
        ctx.fixed[file] = text
        result.fixed.reverse()      # reported in the order the sentence reads
    return result
