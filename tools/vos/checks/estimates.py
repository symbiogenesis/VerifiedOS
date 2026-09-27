# SPDX-License-Identifier: Apache-2.0
"""estimates: every total and share against the item hours beneath it.

The implementation checklist prices itself twice. Once per item, where an estimate is
somebody's judgment about a piece of work, and once in the subtotals, shares, and
progress figures, which are arithmetic over those judgments and nobody's opinion at
all. The second layer is the one that rots: re-pricing an item, splitting it, or
checking it off moves every figure above it, and a subtotal that no longer sums still
renders as a subtotal, so the drift survives exactly the reading anyone gives it.

So the document declares one shape and this group owns everything derived from it.
The authored weights are an open item's range, a completed item's actual, or an
explicitly retained estimate when historical actual time is unavailable. The
midpoint is the mean of the range ends, and every subtotal, the grand range, and the
progress figures are sums over the items beneath them. Item cells carry no share of a
changing grand total. All derived figures are arithmetic, so a repair rewrites them;
unlike the compounded product, there is no judgment layer here to leave standing.

K-96 holds the explicit priced-leaf dispositions and artifact joins in work-order.json,
and the calibration results. Membership is authored; unknown work never enters a
committed gate by default. The generated dispatch view distinguishes authoring inputs
from acceptance joins and supplies no elapsed critical-path prediction. The calibration
is the author's to pool and the tool's to fit: the plan's
calibration record carries each completed attended item's pool and the earliest
estimate its cell recorded, the actual is read from the item's own cell, and every
ratio and count the calibration states is the quotient over that record, which is held
total over the completed attended items in both directions so that a landing which
adds no row is loud rather than a fit taken over fewer items.

There are two such records and never one sum over both. An attended actual is an
elapsed attended interval and an agent-parallel actual is summed agent-session
wall-clock over an item's passes, no item carries both, and the plan's own ruling is
that nothing here converts between them, so each series is joined to its own record and
each stated ratio is the quotient over the record carrying the pool it names. The one
figure ever fitted across the pair, what the class-X-authored pool would read if the two
were pooled, is the one S19 stated in order to refuse it, and it stays in that item's
completion-log note as the measurement its gate took rather than being held live here.

A third authored token joins the range: an open item's **authority class**, `I` where what
the item realizes is fixed inside this repository and `X` where it is not. It is a judgment
and stays one, but everything resting on it is arithmetic and lands here: the two class
sums, and the calibrated total, which re-weights each class's open hours by the ratio the
calibration record gives for it. A completed item carries no class, having an actual
where the class would have widened a range, which is why the record carries its pool.

An item carrying no cell at all is legal in one place, a parent whose children carry
the estimates, which is why the check reads the indent rather than demanding a figure
of every bullet: the parent is a heading with a checkbox, and its children are already
counted. Anything else missing a cell is counted by nothing and is the finding.
"""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from vos import figures, workorder
from vos.figures import format_hours, percent, quantize

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== estimates: every total and share against the item hours beneath it ==="

PLAN = "docs/implementation/implementation-checklist.md"

# an item line or a subtotal line, in document order: the subtotal closes the run of
# items above it, which is the whole of how an item finds the total it belongs to
SCAN_RE = re.compile(
    r"(?m)^(?P<ind>[^\S\r\n]*)(?:"
    r"\* \[(?P<box>[ x])\] \*\*(?P<label>[^*]+)\*\*(?P<rest>[^\r\n]*)"
    r"|\*\*(?P<sec>[^*]+) subtotal:\*\*(?P<tail>[^\r\n]*))")

# The tail is authored prose (`Parallel`, and what it is parallel with). A legacy
# share is read only to remove it under K-36; it never contributes to a value.
# Numeric tokens must be readable before _hours is called, including comma groups.
NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
CELL_END = r"(?: · (?P<pct>\d+(?:\.\d+)?)%)?(?P<tail>(?: · .*)?)$"
DONE_RE = re.compile(rf"^ · (?P<h>{NUMBER}) h actual" + CELL_END)
RETAINED_RE = re.compile(rf"^ · (?P<h>{NUMBER}) h retained estimate, actual n/a" + CELL_END)
OPEN_RE = re.compile(rf"^ · (?P<h>{NUMBER}) h, range (?P<lo>{NUMBER})–(?P<hi>{NUMBER})"
                     + CELL_END)

# the authority class opens the tail, ahead of whatever prose follows it. An open item owes
# one and a completed item does not: the class is a prior on a range, and a completed item
# has an actual instead of a range for the prior to widen
CLASS_RE = re.compile(r"^ · (?P<cls>[IX])(?= ·|$)")

WORK_FIELDS = {
    "m8a": "Committed M8a open h",
    "m8b": "Committed M8b open h",
    "committed": "Other committed open h",
    "conditional": "Conditional open h",
    "option": "Unfunded option open h",
}

# the calibration record: one row per completed attended item, the pool its authority fell
# in and the earliest estimate its cell recorded. The pools are the three the plan's basis
# fits over, and `n/a` in both columns is an item that never carried an estimate, which is
# inside the record's totality and outside the fit
RECORD_HEADING = "### Calibration record"

# the agent-parallel series' own record, and it is a second table rather than a fourth
# column of the first for two reasons neither of which is taste. The two series are
# fitted apart, S19 having ruled that an attended interval and a summed agent-session
# wall-clock are two quantities with no measured conversion between them, so a pooled
# ratio would be arithmetic over two units; and the row pattern below is three cells
# wide, so a widened row matches in no record at all and the reading would empty in
# silence while every figure it feeds went undefined. A heading of any depth is where
# `_record` stops, which is what holds the two tables apart with no second pattern.
PARALLEL_HEADING = "#### The agent-parallel series"

RECORD_ROW_RE = re.compile(
    r"(?m)^\| (?P<item>[^|\r\n]+?) \| (?P<pool>[^|\r\n]+?) \| (?P<est>[^|\r\n]+?) \|[ \t]*\r?$")
POOLS = ("I", "X-read", "X-authored")
NOT_APPLICABLE = "n/a"
AGENT_PARALLEL = "agent-parallel"
HOURS_RE = re.compile(rf"^{NUMBER}$")

SUMMARY_START = "<!-- estimate-summary:start -->"
SUMMARY_END = "<!-- estimate-summary:end -->"
SUMMARY_HEADER = "| Measure | Value |"
SUMMARY_RULE = "| --- | --- |"
SUMMARY_FIELDS: dict[str, re.Pattern[str]] = {
    "Total estimate midpoint h": HOURS_RE,
    "Total estimate range h": re.compile(rf"^{NUMBER}–{NUMBER}$"),
    "Completed scope h": HOURS_RE,
    "Complete by estimate %": HOURS_RE,
    "Remaining h": HOURS_RE,
    "Open class I h": HOURS_RE,
    "Open class X h": HOURS_RE,
    "Retained completion estimate h": HOURS_RE,
    "Unmeasured completed items": re.compile(r"^\d+$"),
    "Calibrated total h": HOURS_RE,
    **dict.fromkeys(WORK_FIELDS.values(), HOURS_RE),
    "Committed M8a open class X h": HOURS_RE,
    "Committed M8a open range h": re.compile(rf"^{NUMBER}–{NUMBER}$"),
}
# A one-way repair migration preserves the historical table until all new owners
# are valid. It cannot populate new commitments from the old exclusion lists.
LEGACY_SUMMARY_FIELDS = {
    **{key: pattern for key, pattern in SUMMARY_FIELDS.items()
       if key not in WORK_FIELDS.values() and not key.startswith("Committed M8a")},
    "M8a open h": HOURS_RE,
    "M8a open class X h": HOURS_RE,
    "M8b parallel chain h": HOURS_RE,
    "M8a critical chain midpoint h": HOURS_RE,
    "M8a critical chain range h": re.compile(rf"^{NUMBER}–{NUMBER}$"),
}

CALIBRATION_START = "<!-- calibration-results:start -->"
CALIBRATION_END = "<!-- calibration-results:end -->"
CALIBRATION_HEADER = "| Mode | Pool | Measured items | Estimate h | Actual h | Actual/estimate |"
CALIBRATION_RULE = "| --- | --- | --- | --- | --- | --- |"
MODES = ("attended", AGENT_PARALLEL)
RESULT_POOLS = (*POOLS, "All")

type Fit = dict[str, list[tuple[str, float, float]]]


def _hours(text: str) -> float:
    return float(text.replace(",", ""))


def _head(label: str) -> str:
    return label.partition(" · ")[0].strip()


@dataclass
class Item:
    label: str
    line: str
    head: str
    done: bool
    stated: float
    hours: float
    lo: float
    hi: float
    tail: str
    cls: str | None
    # the label head of the cell-less parent this item is nested under, where it is; a
    # chain member that carries no cell enters as its children through this
    parent: str | None = None
    # All cell-less ancestors, outermost first, retain membership in a nested chain.
    ancestors: tuple[str, ...] = ()
    # A retained planning weight contributes to completed scope, never to a fit.
    measured_actual: bool = True


@dataclass
class Section:
    name: str
    line: str
    head: str
    tail: str
    items: list[Item]


def _parse(raw: str) -> tuple[list[Item], list[Section], list[str]]:
    items: list[Item] = []
    sections: list[Section] = []
    bucket: list[Item] = []
    malformed: list[str] = []
    pending: tuple[str, int] | None = None
    # A stack restores the enclosing parent after a nested group ends. A single
    # parent loses both grandchildren and later siblings from the outer chain.
    parents: list[tuple[str, int]] = []

    for m in SCAN_RE.finditer(raw):
        if m.group("sec") is not None:
            if pending:
                malformed.append(f"{pending[0]}: no estimate cell, and no nested item to carry one")
                pending = None
            parents.clear()
            tail = m.group("tail")
            sections.append(Section(name=m.group("sec"), line=m.group(),
                                    head=m.group()[:len(m.group()) - len(tail)],
                                    tail=tail, items=bucket))
            bucket = []
            continue

        # `Match.group` answers `str | Any` for a named group the pattern makes
        # mandatory, so the `Any` arm is narrowed here rather than at each of the
        # places `label` is carried into a typed slot.
        label = cast("str", m.group("label")).strip()
        indent = len(m.group("ind"))
        rest = m.group("rest")

        # a parent is an item with no cell whose children are indented under it; the
        # next item at the same depth or shallower means the children never came
        if pending:
            if indent <= pending[1]:
                malformed.append(f"{pending[0]}: no estimate cell, and no nested item to carry one")
            pending = None
        while parents and indent <= parents[-1][1]:
            parents.pop()

        done = DONE_RE.match(rest)
        retained = RETAINED_RE.match(rest)
        opened = OPEN_RE.match(rest)
        # `cell` is whichever of the forms matched, and the guard is written as one
        # test on it rather than as `not done and not opened` so that what follows
        # reads a match rather than a value that is a match on the strength of a
        # condition two statements away.
        cell = done or retained or opened
        if cell is None:
            if rest.strip():
                malformed.append(f"{label}: '{rest.strip()}' is not an estimate cell")
            else:
                pending = (label, indent)
                parents.append((_head(label), indent))
            continue

        if retained and m.group("box") != "x":
            malformed.append(f"{label}: a retained estimate with actual n/a requires "
                             "a completed checkbox")
        if done and m.group("box") != "x":
            malformed.append(f"{label}: a measured actual requires a completed checkbox")
        if opened and m.group("box") == "x":
            malformed.append(f"{label}: a completed checkbox requires an actual or a "
                             "retained estimate with actual n/a")
        if "%" in cell.group("tail"):
            malformed.append(f"{label}: a percentage outside the legacy share position "
                             "is not part of an estimate cell")
        lo = _hours(opened.group("lo")) if opened else 0.0
        hi = _hours(opened.group("hi")) if opened else 0.0
        klass = CLASS_RE.match(cell.group("tail"))
        if opened and klass is None:
            malformed.append(f"{label}: no authority class beside the estimate; an open cell "
                             "reads '· I' or '· X' after its range")
        # every sum below reads `hours`, and for an open item that is the range's mean
        # rather than the midpoint as written: the range is the estimate, so a stated
        # midpoint that disagrees with it is a stale token, reported and rewritten
        item = Item(
            label=label, line=m.group(),
            head=m.group()[:len(m.group()) - len(rest)],
            done=bool(done or retained),
            stated=_hours(cell.group("h")),
            hours=round((lo + hi) / 2, 1) if opened else _hours(cell.group("h")),
            lo=lo, hi=hi, tail=cell.group("tail"),
            cls=klass.group("cls") if klass else None,
            parent=parents[-1][0] if parents else None,
            ancestors=tuple(head for head, _ in parents),
            measured_actual=bool(done))
        items.append(item)
        bucket.append(item)

    if pending:
        malformed.append(f"{pending[0]}: no estimate cell, and no nested item to carry one")
    if bucket:
        malformed.append(f"{len(bucket)} item(s) after the last subtotal, counted by no "
                         f"total: {bucket[0].label} onward")
    return items, sections, malformed


def _record(raw: str, heading: str) -> tuple[list[tuple[str, str, str]], list[str]]:
    """A calibration record's rows, and what stops them being read.

    A record is the run of table rows under its own heading, up to the next heading
    of any depth. The header row and its rule are the table's and not rows of the record,
    and a record with no rows at all is a finding rather than a fit over nothing. Two
    records are read this way, the attended one and the agent-parallel one, and the
    heading each stops at is the other's.
    """
    at = raw.find(f"\n{heading}")
    if at < 0:
        return [], [f"{PLAN} carries no '{heading}' heading, so no pool and no "
                    "estimate is recorded for any completed item under it"]
    body = raw[at + 1 + len(heading):]
    end = re.search(r"(?m)^#{1,6} ", body)
    if end:
        body = body[:end.start()]
    # `Match.group` answers `str | Any` for a group the pattern makes mandatory, so the
    # three cells are narrowed here, once, the way `_parse` narrows a label
    rows: list[tuple[str, str, str]] = []
    for m in RECORD_ROW_RE.finditer(body):
        item = cast("str", m.group("item")).strip()
        if item == "Item" or set(item) <= {"-", ":"}:
            continue
        rows.append((item, cast("str", m.group("pool")).strip(),
                     cast("str", m.group("est")).strip()))
    if not rows:
        return [], [f"the calibration record under '{heading}' carries no row"]
    return rows, []


def _fit(record: list[tuple[str, str, str]], actuals: dict[str, Item], what: str,
         subject: str, derived: list[str]) -> Fit:
    """One record joined to the actuals in the items' own cells, pool by pool.

    Held total in both directions, so a landing that adds no row is loud rather than a
    fit taken silently over fewer items, and a row naming an item of the other series
    is a finding rather than a pair quietly counted in the wrong record.
    """
    seen: set[str] = set()
    fit: Fit = {pool: [] for pool in POOLS}
    for item, pool, est in record:
        if item in seen:
            derived.append(f"the {what} carries {item} twice")
            continue
        seen.add(item)
        if item not in actuals:
            derived.append(f"the {what} carries {item}, which is not a {subject} "
                           "of the plan")
            continue
        if pool == NOT_APPLICABLE and est == NOT_APPLICABLE:
            continue
        if not actuals[item].measured_actual:
            derived.append(f"{item}: actual n/a requires n/a in both calibration "
                           "columns; a retained estimate is not a measured actual")
            continue
        if pool not in POOLS or not HOURS_RE.match(est):
            derived.append(f"{item}: pool '{pool}' and estimate '{est}' are not one of "
                           f"{', '.join(POOLS)} beside an hours figure, or n/a in both")
            continue
        fit[pool].append((item, _hours(est), actuals[item].hours))
    derived.extend(f"{item} is a {subject} the {what} carries no row for"
                   for item in actuals if item not in seen)
    return fit


def _ratio(pairs: list[tuple[str, float, float]]) -> float | None:
    estimated = sum(e for _, e, _ in pairs)
    return sum(a for _, _, a in pairs) / estimated if estimated else None


def _summary_table(values: dict[str, str]) -> str:
    """The summary has one row per measure, independent of narrative wording."""
    return "\n".join([SUMMARY_HEADER, SUMMARY_RULE,
                      *(f"| {key} | {values[key]} |" for key in SUMMARY_FIELDS)])


def _summary_results(ctx: Context, values: dict[str, str]) -> figures.LineResult:
    """Repair only values with valid sources in an intact generated summary.

    Every declared row and its numeric shape must remain readable. Missing markers,
    unknown rows and authored text inside the block are report-only; repair cannot
    silently discard them. A caller omits a value whose owner could not be read.
    """
    result = figures.LineResult()
    raw = ctx.text(PLAN)
    markers = [list(re.finditer(rf"(?m)^{re.escape(marker)}(?=\r?$)", raw))
               for marker in (SUMMARY_START, SUMMARY_END)]
    if any(len(hits) != 1 for hits in markers) or any(
            raw.count(marker) != 1 for marker in (SUMMARY_START, SUMMARY_END)):
        result.findings.append(f"{PLAN}: estimate summary requires one start marker "
                               "and one end marker, each on its own line")
        return result
    start, end = markers[0][0].end(), markers[1][0].start()
    if start >= end:
        result.findings.append(f"{PLAN}: estimate summary markers are out of order")
        return result
    body = raw[start:end]
    lines = body.strip().splitlines()
    if lines[:2] != [SUMMARY_HEADER, SUMMARY_RULE]:
        result.findings.append(f"{PLAN}: estimate summary has a missing or malformed header")
        return result
    current: dict[str, str] = {}
    keys: list[str] = []
    for line in lines[2:]:
        cells = line.split("|")
        if len(cells) != 4 or cells[0].strip() or cells[-1].strip():
            result.findings.append(f"{PLAN}: malformed estimate summary row: {line}")
            continue
        key, value = (cell.strip() for cell in cells[1:-1])
        keys.append(key)
        pattern = SUMMARY_FIELDS.get(key, LEGACY_SUMMARY_FIELDS.get(key))
        if pattern is None or not pattern.fullmatch(value):
            result.findings.append(f"{PLAN}: unreadable estimate summary value: {line}")
        current[key] = value
    legacy = sorted(keys) == sorted(LEGACY_SUMMARY_FIELDS)
    if sorted(keys) != sorted(SUMMARY_FIELDS) and not legacy:
        result.findings.append(f"{PLAN}: estimate summary requires exactly one row "
                               "for each declared measure")
    if legacy and (not ctx.fix or set(values) != set(SUMMARY_FIELDS)):
        result.findings.append(f"{PLAN}: legacy estimate summary needs explicit work owners "
                               "and check --fix before migration")
    if result.findings or not values:
        return result
    newline = "\r\n" if body.startswith("\r\n") else "\n"
    expected = newline + _summary_table(values if legacy else current | values).replace("\n", newline) + newline
    if body == expected:
        return result
    if ctx.fix:
        ctx.fixed[PLAN] = raw[:start] + expected + raw[end:]
        result.fixed.append(f"fixed: {PLAN}: estimate summary from its item and record owners")
    else:
        result.findings.append(f"{PLAN}: estimate summary disagrees with its owners; "
                               "run check --fix to regenerate the table")
    return result


def _calibration_table(fits: dict[str, Fit]) -> str:
    """One summary per measurement mode; no row combines the two clocks."""
    lines = [CALIBRATION_HEADER, CALIBRATION_RULE]
    for mode in MODES:
        fit = fits[mode]
        pools = {**fit, "All": [pair for pairs in fit.values() for pair in pairs]}
        for pool in RESULT_POOLS:
            pairs = pools[pool]
            estimated = format_hours(round(sum(e for _, e, _ in pairs), 1))
            actual = format_hours(round(sum(a for _, _, a in pairs), 1))
            ratio = _ratio(pairs)
            shown_ratio = quantize(ratio, 2) if ratio is not None else NOT_APPLICABLE
            lines.append(f"| {mode} | {pool} | {len(pairs)} | {estimated} | {actual} | "
                         f"{shown_ratio} |")
    return "\n".join(lines)


def _calibration_results(ctx: Context, fits: dict[str, Fit], *,
                         valid_records: bool = True) -> figures.LineResult:
    """Repair numeric results only inside one intact, explicitly owned table.

    Missing markers, duplicate rows and malformed cells are report-only. A repair
    must not hide authored material or a broken table by replacing it wholesale.
    Once its schema and keys are intact, all remaining cells are derived values.
    """
    result = figures.LineResult()
    raw = ctx.text(PLAN)
    markers = [list(re.finditer(rf"(?m)^{re.escape(marker)}(?=\r?$)", raw))
               for marker in (CALIBRATION_START, CALIBRATION_END)]
    if any(len(hits) != 1 for hits in markers) or any(
            raw.count(marker) != 1 for marker in (CALIBRATION_START, CALIBRATION_END)):
        result.findings.append(f"{PLAN}: calibration results require one start marker "
                               "and one end marker, each on its own line")
        return result
    start, end = markers[0][0].end(), markers[1][0].start()
    if start >= end:
        result.findings.append(f"{PLAN}: calibration result markers are out of order")
        return result
    body = raw[start:end]
    lines = body.strip().splitlines()
    if lines[:2] != [CALIBRATION_HEADER, CALIBRATION_RULE]:
        result.findings.append(f"{PLAN}: calibration results have a missing or malformed header")
        return result
    keys: list[tuple[str, str]] = []
    for line in lines[2:]:
        cells = line.split("|")
        if len(cells) != 8 or cells[0].strip() or cells[-1].strip():
            result.findings.append(f"{PLAN}: malformed calibration result row: {line}")
            continue
        mode, pool, count, estimated, actual, ratio = (cell.strip() for cell in cells[1:-1])
        keys.append((mode, pool))
        if (not re.fullmatch(r"\d+", count)
                or not HOURS_RE.fullmatch(estimated) or not HOURS_RE.fullmatch(actual)
                or (ratio != NOT_APPLICABLE and not HOURS_RE.fullmatch(ratio))):
            result.findings.append(f"{PLAN}: unreadable calibration result values: {line}")
    expected_keys = [(mode, pool) for mode in MODES for pool in RESULT_POOLS]
    if sorted(keys) != sorted(expected_keys):
        result.findings.append(f"{PLAN}: calibration results require exactly one row for "
                               "each measurement mode and pool, including its All row")
    if result.findings or not valid_records:
        return result
    newline = "\r\n" if body.startswith("\r\n") else "\n"
    expected = newline + _calibration_table(fits).replace("\n", newline) + newline
    if body == expected:
        return result
    if ctx.fix:
        ctx.fixed[PLAN] = raw[:start] + expected + raw[end:]
        result.fixed.append(f"fixed: {PLAN}: calibration results from each mode's record")
    else:
        result.findings.append(f"{PLAN}: calibration results disagree with the records; "
                               "run check --fix to regenerate the table")
    return result


def _work_order_results(ctx: Context, order: workorder.WorkOrder) -> figures.LineResult:
    """Regenerate only the marked table; reject missing markers and authored text."""
    result = figures.LineResult()
    raw = ctx.text(PLAN)
    markers = [list(re.finditer(rf"(?m)^{re.escape(marker)}(?=\r?$)", raw))
               for marker in (workorder.START, workorder.END)]
    if any(len(hits) != 1 for hits in markers) or any(
            raw.count(marker) != 1 for marker in (workorder.START, workorder.END)):
        result.findings.append(f"{PLAN}: work-order view requires one start and end marker")
        return result
    start, end = markers[0][0].end(), markers[1][0].start()
    if start >= end:
        result.findings.append(f"{PLAN}: work-order view markers are out of order")
        return result
    body = raw[start:end]
    lines = body.strip().splitlines()
    if lines[:2] != [workorder.HEADER, workorder.RULE]:
        result.findings.append(f"{PLAN}: work-order view has a malformed header")
        return result
    keys: list[str] = []
    for line in lines[2:]:
        cells = line.split("|")
        if len(cells) != 5 or cells[0].strip() or cells[-1].strip() or any(
                not cell.strip() for cell in cells[1:-1]):
            result.findings.append(f"{PLAN}: malformed work-order view row: {line}")
        else:
            keys.append(cells[1].strip())
    if len(keys) != len(set(keys)):
        result.findings.append(f"{PLAN}: duplicate work-order view row")
    if result.findings or order.findings:
        return result
    newline = "\r\n" if body.startswith("\r\n") else "\n"
    expected = newline + order.table().replace("\n", newline) + newline
    if body != expected:
        if ctx.fix:
            ctx.fixed[PLAN] = raw[:start] + expected + raw[end:]
            result.fixed.append(f"fixed: {PLAN}: dispatch view from explicit leaf and artifact owners")
        else:
            result.findings.append(f"{PLAN}: work-order view disagrees with its owners")
    return result


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)

    if PLAN not in ctx.corpus:
        rep.report("K-34", "missing artifact:", [f"{PLAN} is not in the repository"])
        ctx.shared.update(items=[], sections=[], calibration_rows=0)
        rep.line()
        return

    raw = ctx.text(PLAN)
    items, sections, malformed = _parse(raw)
    ctx.shared.update(items=items, sections=sections)

    rep.report("K-34", "item(s) whose estimate cell the document cannot read:", malformed,
               f"all {len(items)} items carry a cell in the declared shape, and every one "
               "is under a subtotal")

    # an open item's midpoint is the mean of its range, so the range is the only figure
    # in the cell anybody wrote; a completed item's actual has no range to disagree
    # with. Under a repair the cell rewrite below carries the correction, so the
    # mismatch is reported only where nothing is going to correct it.
    if not ctx.fix:
        rep.report("K-35", "open item(s) whose midpoint is not the mean of its range:",
                   [f"{i.label}: {format_hours(i.stated)} h against a {format_hours(i.lo)}–"
                    f"{format_hours(i.hi)} range, whose mean is {format_hours(i.hours)} h"
                    for i in items if not i.done and i.stated != i.hours],
                   "every open midpoint is the mean of its own range")

    # the width test the authority class has always implied and never stated. The class is a
    # prior on a range, and a prior nothing measures the range against decides nothing, so the
    # floor is a span: a class-X range's upper end is at least twice its lower end, which is
    # the "roughly a factor of two" the conventions claim of every range, made a gate for the
    # one class whose outturn says it is not decoration. Class I carries no floor, having run
    # under estimate; a completed item carries no range for a floor to reach.
    #
    # The threshold the calibrated ratio actually motivates, that the calibrated value lie
    # inside the range, is arithmetically unavailable beside K-35 and the conventions say so:
    # a midpoint is the mean of the range ends, so `hi >= r * mid` is `lo <= (2 - r) * mid`
    # and forces every class-X span above five at the ratio the record gives. Reported and
    # never repaired, because which end of a range moves is the estimate itself and not
    # arithmetic over one.
    narrow = [i for i in items
              if not i.done and i.cls == "X" and i.lo > 0 and i.hi < 2 * i.lo]
    rep.report("K-86", "open class-X item(s) whose range spans under a factor of two:",
               [f"{i.label}: {format_hours(i.lo)}–{format_hours(i.hi)} spans "
                f"{i.hi / i.lo:.2f}, against the 2.00 the class owes"
                for i in narrow],
               "every open class-X range spans at least a factor of two end to end")

    open_items = [i for i in items if not i.done]
    grand = round(sum(i.hours for i in items), 1)
    done_h = round(sum(i.hours for i in items if i.done), 1)
    retained_items = [i for i in items if i.done and not i.measured_actual]
    retained_h = round(sum(i.hours for i in retained_items), 1)
    open_lo = round(sum(i.lo for i in open_items), 1)
    open_hi = round(sum(i.hi for i in open_items), 1)

    stated: list[str] = []
    order = workorder.read(ctx.root, {item.label: item.done for item in items})
    if len({item.label for item in items}) != len(items):
        order.findings.append("duplicate priced leaf labels prevent work-order derivation")
    if malformed:
        order.findings.append("unreadable estimate cells prevent work-order derivation")
    derived = list(order.findings)
    buckets = {name: [item for item in open_items if item.label in labels]
               for name, labels in order.buckets.items()}

    # ---- K-96, second half: the calibration, fitted over the record and the actuals ----
    # Two records and two fits, and the pair is never summed: an attended actual is an
    # elapsed attended interval and an agent-parallel one is summed agent-session
    # wall-clock, no item carries both, and the plan's own ruling is that nothing here
    # converts between them. So each series is joined to its own record and each ratio
    # the basis states is the quotient over the record that carries the pool it names.
    calibration_findings_before = len(derived)
    record, unreadable = _record(raw, RECORD_HEADING)
    derived.extend(unreadable)
    ctx.shared["calibration_rows"] = len(record)
    attended = {_head(i.label): i for i in items
                if i.done and AGENT_PARALLEL not in i.tail}
    parallel_items = {_head(i.label): i for i in items
                      if i.done and AGENT_PARALLEL in i.tail}
    fit = _fit(record, attended, "calibration record", "completed attended item", derived)

    precord, punreadable = _record(raw, PARALLEL_HEADING)
    derived.extend(punreadable)
    ctx.shared["parallel_rows"] = len(precord)
    pfit = _fit(precord, parallel_items, "agent-parallel record",
                "completed agent-parallel item", derived)

    ratios = {pool: _ratio(pairs) for pool, pairs in fit.items()}
    pratios = {pool: _ratio(pairs) for pool, pairs in pfit.items()}
    derived.extend(f"the {pool} pool of the calibration record is empty, so the ratio "
                   "the basis states for it exists over nothing"
                   for pool, ratio in ratios.items() if ratio is None)
    derived.extend(f"the {pool} pool of the agent-parallel record is empty, so the ratio "
                   "the basis states for it exists over nothing"
                   for pool, ratio in pratios.items() if ratio is None)
    valid_records = len(derived) == calibration_findings_before
    all_pairs = [pair for pairs in fit.values() for pair in pairs]
    ppairs = [pair for pairs in pfit.values() for pair in pairs]

    # the calibrated total re-weights each class's open hours by its pool's ratio: class I
    # by the I pool's, and class X by the authored pool's alone, which the conventions state
    # is the pool every open class-X cell is priced against and not the class
    by_class = {c: round(sum(i.hours for i in open_items if i.cls == c), 1)
                for c in ("I", "X")}
    class_ratio: dict[str, str] | None = None
    if valid_records and ratios["I"] is not None and ratios["X-authored"] is not None:
        class_ratio = {"I": quantize(ratios["I"], 2), "X": quantize(ratios["X-authored"], 2)}
    else:
        derived.append("the calibrated total cannot be decided because the calibration "
                       "records are incomplete or invalid")

    # every derived token, old against new; nothing here is a judgment, so a repair
    # takes all of it
    edits: list[tuple[str, str, str]] = []
    for item in items:
        cell = (f" · {format_hours(item.hours)} h retained estimate, actual n/a"
                if item.done and not item.measured_actual else
                f" · {format_hours(item.hours)} h actual" if item.done
                else f" · {format_hours(item.hours)} h, range {format_hours(item.lo)}–"
                     f"{format_hours(item.hi)}")
        new = item.head + cell + item.tail
        if new != item.line:
            edits.append((item.label, item.line, new))

    for section in sections:
        opened = [i for i in section.items if not i.done]
        total = round(sum(i.hours for i in section.items), 1)
        complete = round(sum(i.hours for i in section.items if i.done), 1)
        tail = f" {format_hours(total)} h · {percent(total, grand, 0)}%"
        if complete > 0:
            tail += f" · {format_hours(complete)} h complete"
        if opened:
            tail += (f" · open range {format_hours(round(sum(i.lo for i in opened), 1))}–"
                     f"{format_hours(round(sum(i.hi for i in opened), 1))} h")
        tail += "."
        if tail != section.tail:
            edits.append((f"{section.name} subtotal", section.line, section.head + tail))

    if edits and ctx.fix:
        pristine = raw
        unrewritable = []
        for what, old, new in edits:
            pattern = "(?m)^" + re.escape(old) + r"(?=\r?$)"
            sites = len(re.findall(pattern, raw))
            if sites != 1:
                unrewritable.append(f"'{what}' matches {sites} lines; "
                                    "the line is not unique enough to rewrite")
                continue
            raw = re.sub(pattern, lambda _m, n=new: n, raw)
            rep.line(f"fixed: {what}: {old.strip()} -> {new.strip()}")
        # recorded only where a rewrite landed: an edit refused as unrewritable leaves
        # the text as it was, and recording it anyway would write the file back
        # byte-identical and report a rewrite on every run without ever reaching one
        if raw != pristine:
            ctx.fixed[PLAN] = raw
        rep.report("K-36", "figure(s) the repair could not place:", unrewritable,
                   f"all {len(edits)} rewritten item cells and subtotals were placed")
    else:
        rep.report("K-36", "item or subtotal figure(s) disagreeing with the hours beneath them:",
                   [f"{what}: {new.strip()}" for what, _, new in edits],
                   f"all {len(items)} item cells and {len(sections)} subtotals agree with "
                   "their hours")

    # Each measure has one generated home. Narrative wording carries no numeric
    # obligation, and a broken source must not rewrite the measure it owns.
    values: dict[str, str] = {}
    if items and not malformed:
        values = {
            "Total estimate midpoint h": format_hours(grand),
            "Total estimate range h": (f"{format_hours(done_h + open_lo)}–"
                                       f"{format_hours(done_h + open_hi)}"),
            "Completed scope h": format_hours(done_h),
            "Complete by estimate %": percent(done_h, grand, 1),
            "Remaining h": format_hours(grand - done_h),
            "Open class I h": format_hours(by_class["I"]),
            "Open class X h": format_hours(by_class["X"]),
            "Retained completion estimate h": format_hours(retained_h),
            "Unmeasured completed items": str(len(retained_items)),
        }
        if class_ratio is not None:
            calibrated = round(done_h + sum(float(class_ratio[c]) * h
                                            for c, h in by_class.items()), 1)
            values["Calibrated total h"] = format_hours(calibrated)
        if not order.findings:
            for name, field in WORK_FIELDS.items():
                values[field] = format_hours(round(sum(i.hours for i in buckets[name]), 1))
            gate_a = buckets["m8a"]
            values["Committed M8a open class X h"] = format_hours(
                round(sum(i.hours for i in gate_a if i.cls == "X"), 1))
            values["Committed M8a open range h"] = (
                f"{format_hours(round(sum(i.lo for i in gate_a), 2))}–"
                f"{format_hours(round(sum(i.hi for i in gate_a), 2))}")
    summary = _summary_results(ctx, values)
    for line in summary.fixed:
        rep.line(line)
    stated.extend(summary.findings)
    rep.report("K-37", "estimate summary or partition finding(s):", stated,
               "the generated summary agrees with its item and record owners")

    view = _work_order_results(ctx, order)
    derived.extend(view.findings)
    for line in view.fixed:
        rep.line(line)
    # ---- K-96: explicit work membership and the marked calibration results ----
    calibration = _calibration_results(ctx, {"attended": fit, AGENT_PARALLEL: pfit},
                                       valid_records=valid_records)
    for line in calibration.fixed:
        rep.line(line)
    derived.extend(calibration.findings)
    rep.report("K-96", "work-order or calibration finding(s):", derived,
               f"the work order classifies {len(open_items)} open cells, the calibration "
               f"fits over {len(all_pairs)} of the record's {len(record)} rows and the "
               f"agent-parallel series over {len(ppairs)} of its own record's "
               f"{len(precord)}, and the generated calibration results agree")
    rep.line()
