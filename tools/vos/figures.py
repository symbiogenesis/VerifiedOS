# SPDX-License-Identifier: Apache-2.0
"""Number-word formatting, rounding, literal-anchored regex search, and claim resolution/repair for derived figures.

Provides:
- Count-word and numeric formatting helpers ([`words`](#words), [`format_hours`](#format_hours),
  [`share`](#share), [`percent`](#percent), [`quantize`](#quantize)).
- Literal-substring anchored regex search ([`anchor`](#anchor), [`find_all`](#find_all))
  so lookaround-heavy claim patterns scan only windows around their longest literal phrase.
- Single-figure ([`resolve_claim`](#resolve_claim)) and multi-figure sentence
  ([`resolve_line`](#resolve_line)) checking and `--fix` rewriting.
"""

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .checks import Context

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty",
         6: "sixty", 7: "seventy", 8: "eighty", 9: "ninety"}


def words(n: int) -> str:
    """Return the English word form for `0 <= n < 100`, raising `ValueError` for `n >= 100`."""
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens = _TENS[n // 10]
        return tens if n % 10 == 0 else f"{tens}-{_ONES[n % 10]}"
    raise ValueError(f"no word form for {n}; state it in digits")


def distinctive(n: int) -> str | None:
    """Return the word form (`11 <= n < 100`) or digit string (`n >= 100`), or `None` for `n < 11`."""
    if n >= 100:
        return str(n)
    if n >= 11:
        return words(n)
    return None


def restore_case(found: str, expected: str) -> str:
    """Capitalize `expected` if `found` begins with an uppercase letter."""
    if found[:1].isupper() and found[:1].isalpha():
        return expected[:1].upper() + expected[1:]
    return expected


def same_figure(a: str, b: str) -> bool:
    return a.lower().replace(",", "") == b.lower().replace(",", "")


def format_hours(v: float) -> str:
    """Format hours to one decimal place, dropping a trailing `.0`."""
    r = round(v, 1)
    return f"{r:,.0f}" if r == int(r) else f"{r:,.1f}"


def share(v: float, total: float, digits: int) -> float:
    """Return `v / total * 100` rounded `ROUND_HALF_UP` to `digits` decimal places."""
    if total == 0:
        return 0.0
    quantum = Decimal(1).scaleb(-digits)
    return float(Decimal(v / total * 100).quantize(quantum, rounding=ROUND_HALF_UP))


def percent(v: float, total: float, digits: int) -> str:
    return f"{share(v, total, digits):,.{digits}f}"


def quantize(v: float, digits: int) -> str:
    """Format `v` rounded `ROUND_HALF_UP` to `digits` decimal places with thousands separators."""
    quantum = Decimal(1).scaleb(-digits)
    return f"{Decimal(v).quantize(quantum, rounding=ROUND_HALF_UP):,.{digits}f}"


# Search window radius around each occurrence of `anchor(pattern)`.
WINDOW = 4096

# Regex constructs that prevent extracting a guaranteed literal substring (`|`, non-positive-lookaround groups, group quantifiers, `{m,n}`).
_UNREAD_RE = re.compile(r"(?<!\\)\|" r"|(?<!\\)\((?!\?=|\?<=)" r"|\)[?*{]" r"|(?<!\\)\{")
_FLAGS_RE = re.compile(r"\(\?[aiLmsux]+\)")
_METACHARACTERS = set(r".^$*+?()[]{}|\\")
_DELETES_WHAT_PRECEDES = frozenset("?*{")


def _class_end(pattern: str, i: int) -> int:
    """Return the index one past the `]` closing the character class starting at `i`."""
    j = i + 1 + (pattern[i + 1:i + 2] == "^")
    j += pattern[j:j + 1] == "]"
    while j < len(pattern) and pattern[j] != "]":
        j += 2 if pattern[j] == "\\" else 1
    return j + 1


def anchor(pattern: str) -> str:
    """Return the longest literal substring that every match of `pattern` (or its positive lookarounds) must contain, or `""`."""
    body = _FLAGS_RE.sub("", pattern)
    if _UNREAD_RE.search(body):
        return ""

    best = run = ""
    i = 0
    while i < len(body):
        char, width, literal = body[i], 1, False
        if char == "\\":
            char, width = body[i + 1:i + 2], 2
            literal = not char.isalnum()
            if char in "xuU":
                width += {"x": 2, "u": 4, "U": 8}[char]
        elif char == "[":
            width = _class_end(body, i) - i
        elif char == "(":
            width = 4 if body.startswith("(?<=", i) else 3
        else:
            literal = char not in _METACHARACTERS

        follows = body[i + width:i + width + 1]
        if literal and follows not in _DELETES_WHAT_PRECEDES:
            run += char
            literal = follows != "+"
        if not literal:
            best, run = max(best, run, key=len), ""
        i += width

    return max(best, run, key=len)


def find_all(pattern: str, raw: str) -> list[re.Match[str]]:
    """Return all matches of `pattern` in `raw`, pre-filtering to `WINDOW`-byte windows around `anchor(pattern)` when non-empty."""
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
