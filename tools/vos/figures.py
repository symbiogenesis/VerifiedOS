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
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen "
         "fourteen fifteen sixteen seventeen eighteen nineteen").split()
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


@dataclass
class ClaimResult:
    spans: list = field(default_factory=list)
    finding: str | None = None
    fixed: str | None = None


def resolve_claim(ctx, file: str, pattern: str, expected: str, what: str) -> ClaimResult:
    """One figure, found and then either repaired or reported."""
    result = ClaimResult()
    if file not in ctx.corpus:
        result.finding = f"{file} is not in the repository"
        return result

    raw = ctx.text(file)
    hits = list(re.finditer(pattern, raw))
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


def resolve_line(ctx, file: str, pattern: str, expected: dict[str, str], what: str) -> LineResult:
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
