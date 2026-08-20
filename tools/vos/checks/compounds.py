"""compounds: the archetype band against the product of the rows it rests on.

The estimates carry two layers of figure and only one of them is anybody's artifact.
A big-table row is scored against the baseline and moves when a lever lands in it;
the archetype band beneath is a synthesis over those rows, restated by hand, and it
moves when someone remembers. Nothing renders wrong when they part: the row reads
correctly, the band reads correctly, and only the arithmetic between them is gone.
That is the drift this group closes, and it has already happened once, a commit
re-scoring the in-order row and leaving the static-prediction row it landed in the
same paragraph as, so the two ends of one lever disagreed for a day.

The product is the dominant terms only, and that is the whole of what makes it
meaningful. Multiplying every applicable row runs past -90% and describes no workload
that exists, because separate rows reach their worse ends on disjoint sub-workloads:
the pointer-chase that empties the cache row is not the branchy dependent code that
empties the in-order one. So the terms are declared here, four losses and two gains,
each naming the row it reads and the range inside that row's figure, and each end's
gains are taken at the end the same workload property drives them to.

What the check cannot decide is the credit: the band's worse end stands a few points
optimistic of the product for exactly the non-simultaneity above, and how many points
that is worth is a judgment. So the document states it, the check recomputes the
product from the rows, and the two are required to agree. A lever that tightens a row
then has one of two consequences and no third: the credit absorbs it, or the band
moves. Neither is silent.

The document is regularized so that the two halves separate cleanly. The product is
arithmetic over the rows and nobody's judgment, so a repair rewrites it. The credit is
the author's, and it has no repair: a row that moves changes the product under a
credit that no longer matches it, and whether that spends the credit or moves the band
is exactly the decision this group exists to force. Running a repair therefore leaves
the finding standing rather than absorbing it, which is the point.
"""

from __future__ import annotations

import re

HEADING = "=== compounds: the archetype band against the product of the rows it rests on ==="

PERF = "docs/performance-estimates.md"

# The column is one shape, stated in the document's own how-to-read: clauses joined by
# '; ', each a range over the scope it names, or `n/a` where the row carries no figure
# of its own. Checking it is what lets everything below read a figure by position rather
# than by pattern, and it catches the row that states its cost in prose, which renders
# as an estimate and is read by nothing.
_POINT = r"≈?[−+]?\d+%"
_CLAUSE = rf"{_POINT}( to {_POINT})?( \([^)]*\))?( [^;]+)?"
SHAPE_RE = re.compile(rf"^(n/a|{_CLAUSE}(; {_CLAUSE})*)$")

# each term names the big-table row it reads and, where that row's figure states more
# than one clause, the scope of the clause that enters: the clock row's sustained half
# is the only one, and it is selected the same way any other scoped clause would be
TERMS = [
    ("In-order issue, no speculation/OoO", ""),
    ("Static-only branch prediction", ""),
    ("No hardware caches, flat SRAM", ""),
    ("Fixed modest clocks, no turbo", "sustained"),
    ("No MMU / single address space", ""),
    ("Macro-op fusion", ""),
]

# one range reads every figure in the corpus, the column having one shape: a signed
# pair, its sign carrying whether the term is a loss or a gain, so neither is declared
RANGE_RE = re.compile(r"([−+])(\d+)% to \1(\d+)%")

BAND_RE = re.compile(r"(?m)^\| General scalar[^|]*\| \*\*−(\d+)% to −(\d+)%\*\*")
CREDIT_RE = re.compile(r"(?m)^\| (Better|Worse) \| −(\d+)% \| (\d+) points (optimistic|conservative) \|")


def run(ctx) -> None:
    rep = ctx.rep
    rep.line(HEADING)

    doc = ctx.corpus.get(PERF)
    if doc is None:
        rep.report("K-30", "missing artifact:", [f"{PERF} is not in the repository"])
        ctx.shared["ends"] = []
        rep.line()
        return
    raw = ctx.text(PERF)

    misshapen = []
    for line in doc.lines:
        if not line.startswith("|"):
            continue
        cells = line.split("|")
        if len(cells) < 8:                      # the big table alone is this wide
            continue
        figure = re.sub(r"^\*\*|\*\*$", "", cells[4].strip())
        if figure in ("Est. Δ perf", "---") or not figure:
            continue
        if SHAPE_RE.match(figure):
            continue
        label = re.sub(r"\s*\(§.*$", "", cells[2].strip())
        misshapen.append(f"{label}: '{figure}'")
    rep.report("K-30", "figure cell(s) outside the column's declared shape:", misshapen,
               "every figure is a range over its scope, or n/a")

    unread: list[str] = []
    ends: list[tuple[bool, int, int]] = []
    for row, scope in TERMS:
        hits = [ln for ln in doc.lines if ln.startswith("|") and row in ln]
        if len(hits) != 1:
            unread.append(f"'{row}': {len(hits)} big-table row(s) match")
            continue
        # the figure cell is clauses joined by '; ', each a range over the scope it names
        clauses = [c for c in hits[0].split("|")[4].split("; ") if scope in c]
        if len(clauses) != 1:
            unread.append(f"'{row}': {len(clauses)} figure clause(s) scoped '{scope}'")
            continue
        m = RANGE_RE.search(clauses[0])
        if not m:
            unread.append(f"'{row}': the clause '{clauses[0].strip()}' states no range")
            continue
        ends.append((m.group(1) == "+", int(m.group(2)), int(m.group(3))))
    rep.report("K-31", "dominant term(s) whose row or figure the big table no longer carries:",
               unread, f"all {len(TERMS)} dominant terms read their own row")
    ctx.shared["ends"] = ends

    band_m = BAND_RE.search(raw)
    credits = list(CREDIT_RE.finditer(raw))

    if unread:
        # reported above; without every term there is no product to compare against
        rep.line()
        return
    if not band_m or len(credits) != 2:
        rep.report("K-32", "unreadable compound(s):",
                   ["the general-scalar band or its credit table is not in the form "
                    "this check reads"])
        rep.line()
        return

    # the better end takes every term's smaller figure and the worse end every term's
    # larger, gains included: the pairing rule, not a choice of which end to be kind at
    product = {}
    for end in ("Better", "Worse"):
        p = 1.0
        for gain, lo, hi in ends:
            v = lo if end == "Better" else hi
            p *= (1 + v / 100) if gain else (1 - v / 100)
        product[end] = int(round((1 - p) * 100))
    band = {"Better": int(band_m.group(1)), "Worse": int(band_m.group(2))}

    stale = [c for c in credits if int(c.group(2)) != product[c.group(1)]]
    if stale and ctx.fix:
        def repair(m: re.Match) -> str:
            end = m.group(1)
            return f"| {end} | −{product[end]}% | {m.group(3)} points {m.group(4)} |"
        ctx.fixed[PERF] = CREDIT_RE.sub(repair, raw)
        for c in stale:
            rep.line(f"fixed: {c.group(1)} product: {c.group(2)}% -> {product[c.group(1)]}%")
    else:
        rep.report("K-32", "product cell(s) disagreeing with the rows they compound:",
                   [f"{c.group(1)}: the table says {c.group(2)}%, the rows compound to "
                    f"{product[c.group(1)]}%" for c in stale],
                   f"the general-scalar band stands {product['Better']}% to "
                   f"{product['Worse']}% by its rows")

    # the band is optimistic where it is nearer zero than the product and conservative
    # where it is further, so neither the gap nor its sense is free to state
    miscredited = []
    for c in credits:
        end = c.group(1)
        gap = abs(band[end] - product[end])
        want = "optimistic" if band[end] < product[end] else "conservative"
        if int(c.group(3)) != gap or c.group(4) != want:
            miscredited.append(
                f"{end}: the table credits {c.group(3)} points {c.group(4)}, "
                f"the band stands {gap} points {want} of the product")
    rep.report("K-33", "credit(s) the band and the product do not support:", miscredited,
               "every credit is the gap between the band and its product")
    rep.line()
