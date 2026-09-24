# SPDX-License-Identifier: Apache-2.0
"""compounds: a statement synthesized over rows, against the rows it rests on.

Two statements have that shape here, and the failure is the same in both: the parts
are each an artifact somebody maintains, the whole is a synthesis over them restated
by hand, and nothing renders wrong when they part. The first is the archetype band
over the estimate rows. The second is the two-class placement, which is a list of
region classes divided between the two latency classes and restated in three places,
where the same drift puts one region class on both sides of a boundary that has to be
a partition.

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

The placement half has no repair at all, and for a stronger reason. Which class a
region belongs on is a design decision, so a term found on the wrong side is not a
transcription this tool may quietly correct; and a term found on *both* sides or on
neither is the set-stated-twice failure, where the answer is to decide which list owns
it rather than to pick one. What is machine-held is the partition, the class each
declared region carries, that the two by-name placements hold at the entries that
state them rather than only in the summary that collects them, and that the prose
restating the pair does not move a region across. The class boundary carries no trust
gradient (R-15-247s), which is exactly what makes this a bookkeeping property and not
a security one: nothing is weakened by a region sitting on the second class, so the
only thing wrong with a misplaced one is that it is wrong.

The placement is held total over the charge rather than over itself, which is the
difference between a rule that decides something and a rule that agrees with the words
it was written from. R-08-045 enumerates every physical byte a composition pays for; a
check reading only the placement's own terms is total over a vocabulary the placement
chose, so a charged term neither list mentions is invisible to it in exactly the case
that matters. The charge is therefore the enumeration here, read from the entry that
states it, and each of its terms is either placed on one class by name or answered by
the criterion's own clause for what a latency boundary sorts rather than names: an
application payload is an owner and not a latency, so its cycle-critical part is
first-class and its bulk is second-class and neither list names it. Both readings are
the register's; what is here is the totality over them.
"""

import math
import re
from typing import TYPE_CHECKING

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== compounds: the archetype band against the product of the rows it rests on ==="

PERF = "docs/performance/performance-estimates.md"

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

SPEC = "docs/spec.md"

# The one sentence shape both the register's criterion and the spec's restatement take.
# Reading it is what makes the two lists two objects rather than one paragraph, and a
# sentence that has moved out of the shape is this rule's unrepairable finding. Neither
# list carries a full stop, so one bounds them at both ends; the case is free because
# the spec opens a sentence where the criterion opens a clause.
LISTS_RE = re.compile(
    r"(?i)the first class carries ([^.\r\n]*?); the second carries ([^.\r\n]*)")

# Each region class the memory plan places, the pattern that finds it in a list, the
# latency class it must land in, and the entry that governs the placement. The governing
# entry is the point: a term whose class is stated only in the summary that collects
# every term is a term one edit away from being stated nowhere.
PLACEMENT: list[tuple[str, str, str, str]] = [
    ("the scalar working set", r"scalar working set", "first", "R-15-247"),
    ("cycle-critical arrays", r"cycle-critical array", "first", "R-15-247"),
    ("kernel objects", r"kernel objects", "first", "R-15-247s"),
    ("stacks", r"\bstacks\b", "first", "R-15-247s"),
    ("register-save areas", r"register-save areas", "first", "R-15-247s"),
    ("DMA windows", r"DMA windows", "first", "R-15-247s"),
    ("rings", r"\brings\b", "first", "R-15-247s"),
    ("grant slots", r"grant slots", "first", "R-15-247s"),
    ("quarantine entries", r"quarantine entries", "first", "R-15-247s"),
    ("recovery workspaces", r"recovery workspaces", "first", "R-15-247s"),
    ("the servers' scalar working sets", r"servers' scalar working sets", "first", "R-15-247s"),
    ("hard-task and hot code", r"hard-task", "first", "R-15-247j"),
    ("bulk by volume", r"bulk by volume", "second", "R-15-247"),
    ("framebuffers", r"framebuffers", "second", "R-15-247s"),
    ("images", r"\bimages\b", "second", "R-15-247s"),
    ("vector and matrix extents", r"vector and matrix extents", "second", "R-15-247s"),
    ("bulk interpreter object arenas", r"bulk interpreter object arenas", "second", "R-14-015"),
    ("bounded hot guest data", r"bounded hot guest data", "first", "R-14-015"),
    ("media buffers", r"media buffers", "second", "R-15-247s"),
    ("cold statically-placed code", r"cold statically-placed code", "second", "R-15-247s"),
    ("model weights", r"model weights", "second", "R-15-247s"),
]

# The other vocabulary the boundary answers to, read from the entry that states it. A
# term added to the charge is a physical byte somebody now pays for, and it has to be
# placed before this rule goes green over it again, which is the whole of what taking
# the charge as the enumeration buys.
CHARGE_RE = re.compile(r"every physical byte \(([^)]*)\)")

# The criterion's own clause for the charged terms it answers without naming. Read
# rather than assumed: a term dropped out of the clause stops being accounted for
# anywhere, and that is a finding rather than a silence. Several terms join on ' and ',
# so a charged term that itself carries an ' and ' cannot be answered here; it reads as
# unplaced, which is the direction that fails loudly rather than the one that passes.
BY_CRITERION_RE = re.compile(
    r"the boundary places ([^,;:.]+?) by criterion and not by name")

# What each governing entry must still say in its own words, so that a placement holds
# where it is decided and not only where it is summarized. R-15-247s is the summary
# itself and so is not in this table: it is the thing being held.
GOVERNS: list[tuple[str, str]] = [
    ("R-15-247", "the scalar working set and every cycle-critical array"),
    ("R-15-247j", "all §11 hard-task code and all hot code on the first class"),
    ("R-14-015", "Bulk arena backing uses the **second class** by default and the "
                 "interpreter body is **first-class**"),
    ("R-14-015", "every extent and pool draw keeps its composition-fixed memory "
                 "class, bank grants and timing charge, with no runtime relocation "
                 "or automatic tiering"),
]


def _lists(text: str) -> tuple[str, str] | None:
    """The two class lists of one sentence, or None where the sentence has moved."""
    m = LISTS_RE.search(text)
    if not m:
        return None
    # Both groups are required by the pattern, so neither can be absent; a group reads
    # as optional to the typechecker because in general one may be.
    return str(m.group(1)), str(m.group(2))


def _placement(ctx: Context) -> None:
    """K-56: every region class carries exactly one latency class, in three readings,
    and every physical byte the charge names is placed exactly once."""
    rep, reg = ctx.rep, ctx.reg
    ctx.shared["placement_terms"] = 0
    ctx.shared["charged_terms"] = 0

    accept = reg.accept_text.get("R-15-247s", "")
    register = _lists(accept)
    spec = _lists(ctx.text(SPEC))
    if register is None or spec is None:
        rep.report("K-56", "two-class placement reading(s) that have moved:", [
            None if register else
            "R-15-247s's criterion no longer states two class lists this rule can split",
            None if spec else
            f"{SPEC} no longer restates the two class lists in the register's own shape",
        ])
        return

    findings: list[str] = []
    for what, pattern, want, governing in PLACEMENT:
        rx = re.compile(pattern)
        where = [name for name, lst in (("first", register[0]), ("second", register[1]))
                 if rx.search(lst)]
        if len(where) != 1:
            findings.append(
                f"R-15-247s places {what} on {len(where)} of the two classes; a region "
                "on both or on neither is a boundary that has stopped being a partition")
            continue
        if where[0] != want:
            findings.append(f"R-15-247s places {what} on the {where[0]} class, "
                            f"{governing} puts it on the {want}")
            continue

        # the spec restates the pair, and need not carry every term: what it may not do
        # is carry one on the other side
        said = [name for name, lst in (("first", spec[0]), ("second", spec[1]))
                if rx.search(lst)]
        if said and said != [want]:
            findings.append(f"{SPEC} places {what} on {' and '.join(said)}, the register "
                            f"places it on the {want}")

    for ident, literal in GOVERNS:
        entry = reg.body.get(ident, "") + reg.accept_text.get(ident, "")
        if literal not in entry:
            findings.append(f"{ident} no longer states the placement R-15-247s "
                            f"attributes to it, which this rule reads as '{literal}'")

    # the charge, and the terms the criterion answers without naming
    charge = CHARGE_RE.search(reg.body.get("R-08-045", ""))
    unnamed = BY_CRITERION_RE.search(accept)
    charged = [term.strip() for term in charge.group(1).split(",")] if charge else []
    by_criterion = {part.strip().lower()
                    for part in unnamed.group(1).split(" and ")} if unnamed else set()

    if charge is None:
        findings.append("R-08-045 no longer enumerates the physical bytes it charges in "
                        "a form this rule reads, so the placement has nothing to be "
                        "total over but its own words")

    for term in charged:
        rx = re.compile(rf"\b{re.escape(term)}\b")
        placed = [name for name, lst in (("the first class", register[0]),
                                         ("the second class", register[1]))
                  if rx.search(lst)]
        if term.lower() in by_criterion:
            placed.append("the criterion's clause for what it places by criterion")
        if len(placed) == 1:
            continue
        findings.append(
            f"R-08-045 charges {term} and R-15-247s places it nowhere; a byte the "
            "composition pays for lies on one of the two classes or is answered by "
            "the clause that says why it lies on neither"
            if not placed else
            f"R-08-045 charges {term} and R-15-247s places it on "
            f"{' and '.join(placed)}, which is one charge placed twice")

    ctx.shared["placement_terms"] = len(PLACEMENT)
    ctx.shared["charged_terms"] = len(charged)
    rep.report("K-56", "term(s) the two-class placement does not place exactly once:",
               findings,
               f"all {len(PLACEMENT)} region classes carry exactly one latency class, "
               f"{len(GOVERNS)} of them held at the entries that decide them, and all "
               f"{len(charged)} physical bytes R-08-045 charges are placed, "
               f"{len(by_criterion)} of them by criterion rather than by name")


def _band(ctx: Context) -> None:
    """K-30 through K-33: the archetype band against the product of its rows."""
    rep = ctx.rep

    doc = ctx.corpus.get(PERF)
    if doc is None:
        rep.report("K-30", "missing artifact:", [f"{PERF} is not in the repository"])
        ctx.shared["ends"] = []
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
    credit_rows = list(CREDIT_RE.finditer(raw))

    if unread:
        # reported above; without every term there is no product to compare against
        return
    if not band_m or len(credit_rows) != 2:
        rep.report("K-32", "unreadable compound(s):",
                   ["the general-scalar band or its credit table is not in the form "
                    "this check reads"])
        return

    # the better end takes every term's smaller figure and the worse end every term's
    # larger, gains included: the pairing rule, not a choice of which end to be kind at
    product: dict[str, int] = {}
    for end in ("Better", "Worse"):
        p = 1.0
        for gain, lo, hi in ends:
            v = lo if end == "Better" else hi
            p *= (1 + v / 100) if gain else (1 - v / 100)
        product[end] = round((1 - p) * 100)
    band = {"Better": int(band_m.group(1)), "Worse": int(band_m.group(2))}

    stale = [c for c in credit_rows if int(c.group(2)) != product[c.group(1)]]
    if stale and ctx.fix:
        def repair(m: re.Match[str]) -> str:
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
    miscredited: list[str] = []
    for c in credit_rows:
        end = c.group(1)
        gap = abs(band[end] - product[end])
        want = "optimistic" if band[end] < product[end] else "conservative"
        if int(c.group(3)) != gap or c.group(4) != want:
            miscredited.append(
                f"{end}: the table credits {c.group(3)} points {c.group(4)}, "
                f"the band stands {gap} points {want} of the product")
    rep.report("K-33", "credit(s) the band and the product do not support:", miscredited,
               "every credit is the gap between the band and its product")


WASM_CASES = ("Broad coverage", "Very high coverage")
WASM_INPUT_HEADER = (
    "| Case | f | w better / worse | h better / worse |\n"
    "| --- | --- | --- | --- |")
WASM_RESULT_HEADER = (
    "| Case | Unaccelerated interpreter vs same-machine native | "
    "Selected path vs same-machine native | Selected path vs conventional scalar native |\n"
    "| --- | --- | --- | --- |")
WASM_ARCHETYPE_RE = re.compile(
    r"(?m)^(\| Wasm applications covered by whole-loop handlers or native-service batches \| )"
    r"\*\*[^|\n]+\*\*( \| [^\n]+)$")


def _wasm(ctx: Context) -> None:
    """K-111: authored assumptions, generated arithmetic; fixed sites fail closed.

    Both case names, both marked blocks and the two archetype sites are required.
    Missing/duplicate/malformed inputs refuse repair, so this enumeration needs
    no separate floor. This checks a model, never its empirical plausibility.
    """
    raw = ctx.text(PERF)
    problems: list[str] = []
    blocks: dict[str, re.Match[str]] = {}
    for kind in ("inputs", "results"):
        start, end = f"<!-- wasm-model-{kind} -->", f"<!-- /wasm-model-{kind} -->"
        matches = list(re.finditer(re.escape(start) + r"\n(.*?)\n" + re.escape(end),
                                   raw, re.DOTALL))
        if raw.count(start) != 1 or raw.count(end) != 1 or len(matches) != 1:
            problems.append(f"Wasm model requires one complete {kind} block")
        else:
            blocks[kind] = matches[0]
    bands = list(BAND_RE.finditer(raw))
    archetypes = list(WASM_ARCHETYPE_RE.finditer(raw))
    if len(bands) != 1 or len(archetypes) != 1:
        problems.append("Wasm model requires one native scalar band and one Wasm archetype")
    cases: dict[str, tuple[float, float, float, float, float]] = {}
    if "inputs" in blocks:
        lines = blocks["inputs"].group(1).splitlines()
        if "\n".join(lines[:2]) != WASM_INPUT_HEADER:
            problems.append("Wasm model input header is missing or malformed")
        for line in lines[2:]:
            cells = [cell.strip() for cell in line.split("|")]
            if len(cells) != 6 or cells[0] or cells[-1]:
                problems.append("Wasm model input row must have four cells")
                continue
            name = cells[1]
            if name not in WASM_CASES or name in cases:
                problems.append(f"unknown or duplicate Wasm model case: {name}")
                continue
            try:
                f = float(cells[2])
                wb, ww = (float(cell) for cell in cells[3].split(" / "))
                hb, hw = (float(cell) for cell in cells[4].split(" / "))
            except ValueError:
                problems.append(f"{name}: nonnumeric Wasm model assumption")
                continue
            if (not all(math.isfinite(v) for v in (f, wb, ww, hb, hw))
                    or not 0 <= f <= 1 or not 1 <= wb <= ww or not 0 <= hb <= hw
                    or not math.isfinite(f + (1 - f) * ww + hw)):
                problems.append(f"{name}: invalid Wasm model domain or endpoint ordering")
                continue
            cases[name] = (f, wb, ww, hb, hw)
        if set(cases) != set(WASM_CASES):
            problems.append("Wasm model must contain each declared coverage case exactly once")
    if len(bands) == 1:
        native_better, native_worse = (int(v) for v in bands[0].groups())
        if not 0 <= native_better <= native_worse < 100:
            problems.append("Wasm model native scalar penalties must be ordered in [0, 100)")
    if problems:
        ctx.rep.report("K-111", "unreadable Wasm performance model:", problems)
        return

    native = tuple(1 - int(v) / 100 for v in bands[0].groups())
    rows = [WASM_RESULT_HEADER]
    conventional: list[int] = []

    def penalty(ratio: float) -> int:
        return round(100 * (1 - ratio))

    def band(values: tuple[int, int]) -> str:
        return f"−{values[0]}% to −{values[1]}%"

    for name in WASM_CASES:
        f, wb, ww, hb, hw = cases[name]
        fb, fw = f + (1 - f) * wb + hb, f + (1 - f) * ww + hw
        base = (penalty(1 / wb), penalty(1 / ww))
        selected = (penalty(1 / fb), penalty(1 / fw))
        cross = (penalty(native[0] / fb), penalty(native[1] / fw))
        conventional.extend(cross)
        rows.append(f"| {name} | {band(base)} | {band(selected)} | {band(cross)} |")
    wanted = "\n".join(rows)
    summary = (archetypes[0].group(1)
               + f"**{band((min(conventional), max(conventional)))}**"
               + archetypes[0].group(2))
    stale: list[str] = []
    repaired = raw
    if blocks["results"].group(1) != wanted:
        stale.append("Wasm result table disagrees with authored assumptions/native band")
        m = blocks["results"]
        repaired = repaired[:m.start(1)] + wanted + repaired[m.end(1):]
    if archetypes[0].group() != summary:
        stale.append("Wasm archetype band disagrees with modeled coverage cases")
        repaired = WASM_ARCHETYPE_RE.sub(lambda _: summary, repaired)
    if stale and ctx.fix:
        ctx.fixed[PERF] = repaired
        ctx.rep.line("fixed: Wasm modeled penalties from authored assumptions and native band")
        stale = []
    ctx.rep.report("K-111", "stale Wasm modeled penalties:", stale,
                   "Wasm modeled penalties follow their assumptions and comparator")


WASM_SCALAR_HEADER = (
    "| Reference penalty better / worse (%) | Incremental gain better / worse |\n"
    "| --- | --- |")
WASM_SCALAR_SITES = (
    re.compile(r"(?m)^(\| Core µarch \| Prepared Wasm scalar execution \(§14\) \| "
               r"Substituted \| )\*\*[^|\n]+\*\*( \| [^\n]+)$"),
    re.compile(r"(?m)^(\| Wasm scalar execution, unchanged Core 3\.0 modules "
               r"\(conditional target\) \| )\*\*[^|\n]+\*\*( \| [^\n]+)$"),
)


def _wasm_scalar(ctx: Context) -> None:
    """K-112: incremental scalar target, with no second hardware multiplication.

    The input block, native comparator and both output sites are mandatory and
    unique. Missing/malformed sites refuse repair; no enumeration floor is needed.
    Arithmetic does not qualify the authored performance assumptions.
    """
    raw = ctx.text(PERF)
    start, end = "<!-- wasm-scalar-inputs -->", "<!-- /wasm-scalar-inputs -->"
    blocks = list(re.finditer(re.escape(start) + r"\n(.*?)\n" + re.escape(end),
                              raw, re.DOTALL))
    native = list(BAND_RE.finditer(raw))
    sites = [list(pattern.finditer(raw)) for pattern in WASM_SCALAR_SITES]
    problems: list[str] = []
    if raw.count(start) != 1 or raw.count(end) != 1 or len(blocks) != 1:
        problems.append("scalar Wasm target requires one complete input block")
    if len(native) != 1 or any(len(matches) != 1 for matches in sites):
        problems.append("scalar Wasm target requires one native band and both headline sites")
    if problems:
        ctx.rep.report("K-112", "unreadable scalar Wasm target:", problems)
        return
    lines = blocks[0].group(1).splitlines()
    if len(lines) != 3 or "\n".join(lines[:2]) != WASM_SCALAR_HEADER:
        ctx.rep.report("K-112", "unreadable scalar Wasm target:",
                       ["scalar Wasm input header or single assumption row is malformed"])
        return
    cells = [cell.strip() for cell in lines[2].split("|")]
    if len(cells) != 4 or cells[0] or cells[-1]:
        ctx.rep.report("K-112", "unreadable scalar Wasm target:", ["expected two cells"])
        return
    try:
        pb, pw = (float(cell) for cell in cells[1].split(" / "))
        gb, gw = (float(cell) for cell in cells[2].split(" / "))
        nb, nw = (int(value) for value in native[0].groups())
    except ValueError as exc:
        ctx.rep.report("K-112", "unreadable scalar Wasm target:", [str(exc)])
        return
    if (not all(math.isfinite(value) for value in (pb, pw, gb, gw))
            or not 0 <= nb <= nw < 100 or not 0 <= pb <= pw < 100
            or not 1 <= gw <= gb or pb < nb or pw < nw):
        ctx.rep.report("K-112", "unreadable scalar Wasm target:",
                       ["invalid domain, endpoint order or reference/native relation"])
        return
    penalties = [round(100 * (1 - min(1 - n / 100, (1 - p / 100) * g)))
                 for n, p, g in ((nb, pb, gb), (nw, pw, gw))]
    wanted = f"**−{penalties[0]}% to −{penalties[1]}%**"
    repaired = raw
    stale: list[str] = []
    for pattern, matches in zip(WASM_SCALAR_SITES, sites, strict=True):
        match = matches[0]
        replacement = match.group(1) + wanted + match.group(2)
        if match.group() != replacement:
            stale.append("scalar Wasm headline disagrees with incremental target/native ceiling")
            repaired = pattern.sub(lambda _, value=replacement: value, repaired)
    if stale and ctx.fix:
        ctx.fixed[PERF] = repaired
        ctx.rep.line("fixed: scalar Wasm headline targets from authored inputs and native ceiling")
        stale = []
    ctx.rep.report("K-112", "stale scalar Wasm targets:", stale,
                   "scalar Wasm headlines follow their inputs without double-counting hardware")


def run(ctx: Context) -> None:
    ctx.rep.line(HEADING)
    _band(ctx)
    _placement(ctx)
    _wasm(ctx)
    _wasm_scalar(ctx)
    ctx.rep.line()
