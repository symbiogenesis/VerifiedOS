# SPDX-License-Identifier: Apache-2.0
"""estimates: every total and share against the item hours beneath it.

The implementation checklist prices itself twice. Once per item, where an estimate is
somebody's judgment about a piece of work, and once in the subtotals, shares, and
progress figures, which are arithmetic over those judgments and nobody's opinion at
all. The second layer is the one that rots: re-pricing an item, splitting it, or
checking it off moves every figure above it, and a subtotal that no longer sums still
renders as a subtotal, so the drift survives exactly the reading anyone gives it.

So the document declares one shape and this group owns everything derived from it.
Two things are authored: an open item's range and a completed item's actual. The
midpoint is the mean of the range ends, an item's share is that midpoint over the
grand total, and every subtotal, the grand range, and the progress pair are sums over
the items beneath them. All of it is arithmetic, so a repair rewrites all of it;
unlike the compounded product, there is no judgment layer here to leave standing.

Two figures the plan derives over sets it names by judgment land here too, under K-96.
The critical chain is the author's to name and the tool's to sum: its members are a
list held here beside the two gate partitions, and its range, its midpoint, and the
horizon they give at the attended rate the plan states are arithmetic over those
cells. The calibration is the author's to pool and the tool's to fit: the plan's
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
figure fitted across the pair is the one the plan states in order to refuse it, what the
class-X-authored pool would read if the two were pooled, and it is computed here for the
same reason every other figure is: a number stated to be rejected still has to be the
number.

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
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, cast

from vos import figures
from vos.figures import format_hours, percent, quantize, words

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== estimates: every total and share against the item hours beneath it ==="

PLAN = "docs/implementation-checklist.md"

# an item line or a subtotal line, in document order: the subtotal closes the run of
# items above it, which is the whole of how an item finds the total it belongs to
SCAN_RE = re.compile(
    r"(?m)^(?P<ind>[^\S\r\n]*)(?:"
    r"\* \[(?P<box>[ x])\] \*\*(?P<label>[^*]+)\*\*(?P<rest>[^\r\n]*)"
    r"|\*\*(?P<sec>[^*]+) subtotal:\*\*(?P<tail>[^\r\n]*))")

# the estimate cell in its two forms, each capturing the tail after it, which is prose
# (`Parallel`, and what it is parallel with) that no figure here may disturb
DONE_RE = re.compile(r"^ · (?P<h>[\d.,]+) h actual · (?P<pct>[\d.]+)%(?P<tail>.*)$")
OPEN_RE = re.compile(r"^ · (?P<h>[\d.,]+) h, range (?P<lo>[\d.,]+)–(?P<hi>[\d.,]+) "
                     r"· (?P<pct>[\d.]+)%(?P<tail>.*)$")

# the authority class opens the tail, ahead of whatever prose follows it. An open item owes
# one and a completed item does not: the class is a prior on a range, and a completed item
# has an actual instead of a range for the prior to widen
CLASS_RE = re.compile(r"^ · (?P<cls>[IX])(?= ·|$)")

# the gate is two gates over two chains, so the partition is two lists rather than one. A
# label names a position in the order rather than one item, and `Post-M10` carries several,
# so what is held below is that each label is occupied and not that the two counts match.
# `AFTER_M8B` is what falls beyond the co-simulation gate; `AFTER_M8A` is that plus the RTL
# chain, which runs beside the software one rather than inside it, so an item on it falls
# after the software gate without being deferred past anything
AFTER_M8B = ["R4", "R5", "M9", "M9a", "M10", "Post-M10",
             "M0.8c", "M1.3", "M1.3a", "M1.4", "M1.8b",
             "M3.4b", "M3.6b", "M5.4", "M6.1b", "M6.2b", "M6.3b", "M6.5b",
             "M6.6", "M6.7", "M6.8", "S5", "S6",
             # the assessment's decision items, each a decision over measurements Q4 and Q5
             # take ahead of the software gate, and none on either chain
             "Q6", "Q7", "Q8", "Q9", "Q10"]
AFTER_M8A = ["R1b", "R1c-i", "R1c-ii", "R2", "R3", "M8b", *AFTER_M8B]

# the critical chain through the software gate, in the order the summary names it. A
# member is the open item carrying that label, or every open child of one that carries no
# cell of its own, which is how M1.2 enters as its six children. The membership is the
# author's, as the two partitions above are; what is held is that each member is occupied
# and that the range, the midpoint and the horizon the plan states are the arithmetic over
# those cells
CHAIN_M8A = ["M1.2", "M1.7", "M3.5", "M4.4", "M5.3", "M7.1", "M8a"]

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
HOURS_RE = re.compile(r"^[\d.,]+$")

# the attended rate is the plan's to state and the horizon is this group's to derive from
# it, so the sentence is read for its rate before it is held for its quotients
RATE_RE = re.compile(r"(?m)^\* Horizon: at (?P<lo>\d+)–(?P<hi>\d+) attended hours per week")


def _hours(text: str) -> float:
    return float(text.replace(",", ""))


def _head(label: str) -> str:
    return label.partition(" · ")[0].strip()


def _count(n: int) -> str:
    """A count as the plan writes one: in words where a word form exists, else digits."""
    return words(n) if n < 100 else str(n)


def _weeks(hours: float, rate: int) -> str:
    """Attended weeks at a rate, to the whole week, rounded the way a share is."""
    return str(int(Decimal(hours / rate).quantize(Decimal(1), rounding=ROUND_HALF_UP)))


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
    # the cell-less parent whose children are still arriving: it outlives `pending`,
    # which is cleared by the first child, and is closed by the next item at its own
    # depth or shallower, or by the subtotal that closes its section
    parent: tuple[str, int] | None = None

    for m in SCAN_RE.finditer(raw):
        if m.group("sec") is not None:
            if pending:
                malformed.append(f"{pending[0]}: no estimate cell, and no nested item to carry one")
                pending = None
            parent = None
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
        if parent and indent <= parent[1]:
            parent = None

        done = DONE_RE.match(rest)
        opened = OPEN_RE.match(rest)
        # `cell` is whichever of the two matched, and the guard is written as one
        # test on it rather than as `not done and not opened` so that what follows
        # reads a match rather than a value that is a match on the strength of a
        # condition two statements away.
        cell = done or opened
        if cell is None:
            if rest.strip():
                malformed.append(f"{label}: '{rest.strip()}' is not an estimate cell")
            else:
                pending = (label, indent)
                parent = (_head(label), indent)
            continue

        lo = _hours(opened.group("lo")) if opened else 0.0
        hi = _hours(opened.group("hi")) if opened else 0.0
        klass = CLASS_RE.match(cell.group("tail"))
        if opened and klass is None:
            malformed.append(f"{label}: no authority class beside the estimate; an open cell "
                             "reads '· I' or '· X' after its percentage")
        # every sum below reads `hours`, and for an open item that is the range's mean
        # rather than the midpoint as written: the range is the estimate, so a stated
        # midpoint that disagrees with it is a stale token, reported and rewritten
        item = Item(
            label=label, line=m.group(),
            head=m.group()[:len(m.group()) - len(rest)],
            done=bool(done),
            stated=_hours(cell.group("h")),
            hours=round((lo + hi) / 2, 1) if opened else _hours(cell.group("h")),
            lo=lo, hi=hi, tail=cell.group("tail"),
            cls=klass.group("cls") if klass else None,
            parent=parent[0] if parent else None)
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
         subject: str, derived: list[str]) -> dict[str, list[tuple[str, float, float]]]:
    """One record joined to the actuals in the items' own cells, pool by pool.

    Held total in both directions, so a landing that adds no row is loud rather than a
    fit taken silently over fewer items, and a row naming an item of the other series
    is a finding rather than a pair quietly counted in the wrong record.
    """
    seen: set[str] = set()
    fit: dict[str, list[tuple[str, float, float]]] = {pool: [] for pool in POOLS}
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
    open_lo = round(sum(i.lo for i in open_items), 1)
    open_hi = round(sum(i.hi for i in open_items), 1)

    stated: list[str] = []
    carried = {_head(i.label) for i in items}
    for name, partition in (("M8a", AFTER_M8A), ("M8b", AFTER_M8B)):
        if empty := [label for label in partition if label not in carried]:
            stated.append(f"the {name} partition names work the document carries no item "
                          f"under: {', '.join(empty)}")

    def _at_or_before(partition: list[str]) -> list[Item]:
        return [i for i in open_items if _head(i.label) not in partition]

    # the software gate is what open work falls at or before it, where the old single gate
    # was the whole midpoint less the deferred tail; the two differ by the completed hours,
    # and the open reading is the one a schedule is made against
    gate_a = _at_or_before(AFTER_M8A)
    gate_a_h = round(sum(i.hours for i in gate_a), 1)
    gate_a_x = round(sum(i.hours for i in gate_a if i.cls == "X"), 1)
    # the RTL chain is what the two partitions differ by: after the software gate, and not
    # deferred past the co-simulation one, so it runs beside rather than behind
    chain_b = round(sum(i.hours for i in open_items
                        if _head(i.label) in AFTER_M8A
                        and _head(i.label) not in AFTER_M8B), 1)

    # ---- K-96, first half: the critical chain, summed over the cells its list names ----
    derived: list[str] = []
    chain = [i for i in open_items
             if _head(i.label) in CHAIN_M8A or (i.parent in CHAIN_M8A)]
    occupied = {_head(i.label) for i in chain} | {i.parent for i in chain if i.parent}
    derived.extend(f"the critical chain names {label} and the document carries no open "
                   "item under it" for label in CHAIN_M8A if label not in occupied)
    chain_lo = round(sum(i.lo for i in chain), 1)
    chain_hi = round(sum(i.hi for i in chain), 1)
    chain_mid = round(sum(i.hours for i in chain), 1)

    # ---- K-96, second half: the calibration, fitted over the record and the actuals ----
    # Two records and two fits, and the pair is never summed: an attended actual is an
    # elapsed attended interval and an agent-parallel one is summed agent-session
    # wall-clock, no item carries both, and the plan's own ruling is that nothing here
    # converts between them. So each series is joined to its own record and each ratio
    # the basis states is the quotient over the record that carries the pool it names.
    record, unreadable = _record(raw, RECORD_HEADING)
    derived.extend(unreadable)
    ctx.shared["calibration_rows"] = len(record)
    attended = {_head(i.label): i for i in items
                if i.done and AGENT_PARALLEL not in i.tail}
    parallel_items = {_head(i.label): i for i in items
                      if i.done and AGENT_PARALLEL in i.tail}
    parallel = list(parallel_items)
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
    all_pairs = [pair for pairs in fit.values() for pair in pairs]
    fit_est = round(sum(e for _, e, _ in all_pairs), 1)
    fit_act = round(sum(a for _, _, a in all_pairs), 1)
    lowest = sorted((a / e, item) for item, e, a in all_pairs if e)[:2]
    ppairs = [pair for pairs in pfit.values() for pair in pairs]
    pfit_est = round(sum(e for _, e, _ in ppairs), 1)
    pfit_act = round(sum(a for _, _, a in ppairs), 1)

    # the calibrated total re-weights each class's open hours by its pool's ratio: class I
    # by the I pool's, and class X by the authored pool's alone, which the conventions state
    # is the pool every open class-X cell is priced against and not the class
    by_class = {c: round(sum(i.hours for i in open_items if i.cls == c), 1)
                for c in ("I", "X")}
    class_ratio: dict[str, str] | None = None
    if ratios["I"] is not None and ratios["X-authored"] is not None:
        class_ratio = {"I": quantize(ratios["I"], 2), "X": quantize(ratios["X-authored"], 2)}
    else:
        derived.append("the calibrated total cannot be decided, its ratios resting on a "
                       "pool the record leaves empty")

    # every derived token, old against new; nothing here is a judgment, so a repair
    # takes all of it
    edits: list[tuple[str, str, str]] = []
    for item in items:
        pct = percent(item.hours, grand, 1)
        cell = (f" · {format_hours(item.hours)} h actual · {pct}%" if item.done
                else f" · {format_hours(item.hours)} h, range {format_hours(item.lo)}–"
                     f"{format_hours(item.hi)} · {pct}%")
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

    # the figures the summary and the basis restate, the prose that carries them staying
    # the document's. These are claims in exactly the counts group's sense, differing
    # only in that the value is computed from the items above rather than read from the
    # quantity table, and that each is owed exactly one site: a second sentence
    # restating a total is the drift, not a synonym.
    grand_t = format_hours(grand)
    lo_t = format_hours(done_h + open_lo)
    hi_t = format_hours(done_h + open_hi)
    derived_lines = [
        ("the total estimate",
         r"(?m)^\* Total estimate: (?P<mid>[\d.,]+) h midpoint, class I (?P<ci>[\d.,]+) h "
         r"and class X (?P<cx>[\d.,]+) h over the open items",
         {"mid": grand_t, "ci": format_hours(by_class["I"]),
          "cx": format_hours(by_class["X"])}),
        ("the progress pair",
         r"(?m)^\* Progress by estimate: (?P<done>[\d.,]+) of (?P<total>[\d.,]+) h complete "
         r"\((?P<donePct>[\d.]+)%\); (?P<left>[\d.,]+) h remaining \((?P<leftPct>[\d.]+)%\)",
         {"done": format_hours(done_h), "total": grand_t,
          "donePct": percent(done_h, grand, 1),
          "left": format_hours(grand - done_h),
          "leftPct": percent(grand - done_h, grand, 1)}),
        ("the M8a gate figure",
         r"(?m)^\* M8a gate: (?P<gate>[\d.,]+) h of open work falls at or before it, of "
         r"which (?P<x>[\d.,]+) h is class X",
         {"gate": format_hours(gate_a_h), "x": format_hours(gate_a_x)}),
        ("the M8b chain figure",
         r"(?m)^\* M8b gate: a (?P<chain>[\d.,]+) h chain of open work",
         {"chain": format_hours(chain_b)}),
        ("the grand-total basis",
         r"(?m)^\* Grand total: the sum of the item cells, (?P<mid>[\d.,]+) h midpoint over "
         r"a (?P<lo>[\d.,]+)–(?P<hi>[\d.,]+) h range",
         {"mid": grand_t, "lo": lo_t, "hi": hi_t}),
    ]
    if class_ratio is not None:
        calibrated = round(done_h + sum(float(class_ratio[c]) * h
                                        for c, h in by_class.items()), 1)
        derived_lines.insert(1, (
            "the calibrated total",
            r"(?m)^\* Calibrated against completed-item outturn \(class I (?P<ri>[\d.]+), "
            r"class X (?P<rx>[\d.]+)\): approximately (?P<cal>[\d.,]+) h",
            {"ri": class_ratio["I"], "rx": class_ratio["X"],
             "cal": format_hours(calibrated)}))

    restated = 0
    for what, pattern, expected in derived_lines:
        restated += len(expected)
        r = figures.resolve_line(ctx, PLAN, pattern, expected, what)
        for line in r.fixed:
            rep.line(line)
        stated.extend(r.findings)
    rep.report("K-37", "restated total(s) disagreeing with the items beneath them:", stated,
               f"all {restated} restated totals agree with the items, over "
               f"{len(derived_lines)} sentences")

    # ---- K-96: the sentences that state the chain and the calibration ----
    counts = {pool: _count(len(pairs)) for pool, pairs in fit.items()}
    ratio_t = {pool: quantize(ratio, 2) if ratio is not None else "n/a"
               for pool, ratio in ratios.items()}
    pratio_t = {pool: quantize(ratio, 2) if ratio is not None else "n/a"
                for pool, ratio in pratios.items()}
    outside = _count(len(fit["X-read"]) + len(fit["X-authored"]))
    # the one fit taken across both records, and the plan states it as the thing the
    # ruling refuses rather than as a figure anything is priced against
    pooled = fit["X-authored"] + pfit["X-authored"]
    pooled_est = round(sum(e for _, e, _ in pooled), 1)
    pooled_act = round(sum(a for _, _, a in pooled), 1)
    judged_lines = [
        ("the critical chain",
         r"(?m)^\* Critical chain through M8a:.*?Over those items the chain sums to "
         r"(?P<lo>[\d.,]+)–(?P<hi>[\d.,]+) h at a (?P<mid>[\d.,]+) h midpoint",
         {"lo": format_hours(chain_lo), "hi": format_hours(chain_hi),
          "mid": format_hours(chain_mid)}),
        ("the calibration convention",
         r"(?m)^\* \*\*Every open item carries an authority class beside its estimate\*\*"
         r".*?over the (?P<n>[a-z-]+) completed items carrying both an estimate and an "
         r"actual, the (?P<ni>[a-z-]+) whose authority is inside this repository ran at "
         r"(?P<ri>[\d.]+), and the (?P<nx>[a-z-]+) whose authority is outside it split, "
         r"the (?P<nr>[a-z-]+) that read, pin, install or measure an external thing "
         r"running at (?P<rr>[\d.]+) and the (?P<na>[a-z-]+) that authored against an "
         r"external authority at (?P<ra>[\d.]+)\. \*\*The (?P<ra2>[\d.]+) every open "
         r"class-X cell is priced against is that second pool and not the class\*\*, which "
         r"is the whole of what makes n = (?P<na2>\d+) the weakness",
         {"n": _count(len(all_pairs)), "ni": counts["I"], "ri": ratio_t["I"],
          "nx": outside, "nr": counts["X-read"], "rr": ratio_t["X-read"],
          "na": counts["X-authored"], "ra": ratio_t["X-authored"],
          "ra2": ratio_t["X-authored"], "na2": str(len(fit["X-authored"]))}),
        ("the agent-parallel series",
         r"(?m)^\* \*\*A completed item marked `agent-parallel`.*?\*\*The series is "
         r"(?P<n>[a-z-]+) items\*\* \((?P<list>[^)]*)\)",
         {"n": _count(len(parallel)), "list": ", ".join(parallel)}),
        ("the class-X pool size",
         r"the (?P<ra>[\d.]+) the whole convention rests on is fitted over "
         r"(?P<na>[a-z-]+) completed items",
         {"ra": ratio_t["X-authored"], "na": counts["X-authored"]}),
        ("the fan-out count",
         r"the fan-out having already run (?P<n>[a-z-]+) agent-parallel landings",
         {"n": _count(len(parallel))}),
        ("the fan-out ceiling count",
         r"The fan-out has run against that ceiling (?P<n>[a-z-]+) times",
         {"n": _count(len(parallel))}),
        ("the class-I outturn an open item prices against",
         r"Class I has run at (?P<ri>[\d.]+) over (?P<ni>[a-z-]+) completed items",
         {"ri": ratio_t["I"], "ni": counts["I"]}),
        ("the calibration risk",
         r"rests on (?P<na>[a-z-]+) completed items in the class that matters",
         {"na": counts["X-authored"]}),
        ("the calibration basis",
         r"(?m)^\* \*\*The authority class is the calibration, and it is measured rather "
         r"than assumed\.\*\*.*?across the (?P<n>[a-z-]+) items carrying both, gives "
         r"(?P<act>[\d.,]+) h actual against (?P<est>[\d.,]+) h estimated, a ratio of "
         r"(?P<r>[\d.]+)\..*?: (?P<ni>[a-z-]+) items whose authority is in this repository "
         r"ran at \*\*(?P<ri>[\d.]+)\*\*, (?P<nr>[a-z-]+) that read, pin, install or "
         r"measure an external thing ran at \*\*(?P<rr>[\d.]+)\*\*, and the "
         r"(?P<na>[a-z-]+) that authored against an external authority ran at "
         r"\*\*(?P<ra>[\d.]+)\*\*\..*?the two lowest ratios in the record being "
         r"(?P<u1>\S+) at (?P<r1>[\d.]+) and (?P<u2>\S+) at (?P<r2>[\d.]+)\.",
         {"n": _count(len(all_pairs)), "act": format_hours(fit_act),
          "est": format_hours(fit_est),
          "r": quantize(fit_act / fit_est, 2) if fit_est else "n/a",
          "ni": counts["I"], "ri": ratio_t["I"], "nr": counts["X-read"],
          "rr": ratio_t["X-read"], "na": counts["X-authored"], "ra": ratio_t["X-authored"],
          **({"u1": lowest[0][1], "r1": quantize(lowest[0][0], 2),
              "u2": lowest[1][1], "r2": quantize(lowest[1][0], 2)}
             if len(lowest) == 2 else {})}),
        ("the pool weakness",
         r"n = (?P<na>\d+) in the pool that matters",
         {"na": str(len(fit["X-authored"]))}),
        # the second fit, over the second record, in the shape the first is stated in.
        # Its last two figures are the pair the ruling turns on and are the two pools'
        # own ratios again, stated together because what the sentence asserts is that
        # they straddle one and neither figure alone says that
        ("the agent-parallel fit",
         r"(?m)^\* \*\*The agent-parallel series is fitted on its own record and the two "
         r"fits are not pooled\*\*.*?across the (?P<n>[a-z-]+) items carrying both, gives "
         r"(?P<act>[\d.,]+) h actual against (?P<est>[\d.,]+) h estimated, a ratio of "
         r"(?P<r>[\d.]+): (?P<ni>[a-z-]+) items whose authority is in this repository ran "
         r"at \*\*(?P<ri>[\d.]+)\*\*, (?P<nr>[a-z-]+) that read an external thing ran at "
         r"\*\*(?P<rr>[\d.]+)\*\*, and the (?P<na>[a-z-]+) that authored against an "
         r"external authority ran at \*\*(?P<ra>[\d.]+)\*\*\..*?"
         r"(?P<attended>[\d.]+) attended against (?P<parallel>[\d.]+) here",
         {"n": _count(len(ppairs)), "act": format_hours(pfit_act),
          "est": format_hours(pfit_est),
          "r": quantize(pfit_act / pfit_est, 2) if pfit_est else "n/a",
          "ni": _count(len(pfit["I"])), "ri": pratio_t["I"],
          "nr": _count(len(pfit["X-read"])), "rr": pratio_t["X-read"],
          "na": _count(len(pfit["X-authored"])), "ra": pratio_t["X-authored"],
          "attended": ratio_t["X-authored"], "parallel": pratio_t["X-authored"]}),
        # what the ruling refuses, computed rather than asserted: the one pool the
        # calibration rests on, taken over both records at once. It is the only figure
        # here fitted across the two clocks, and it exists to be reported as the thing
        # that would happen and not as the thing that is done
        ("the pooled class-X fit",
         r"the pool is then (?P<n>[a-z-]+) items at (?P<act>[\d.,]+) h actual against "
         r"(?P<est>[\d.,]+) h estimated, a ratio of \*\*(?P<r>[\d.]+)\*\*",
         {"n": _count(len(pooled)), "act": format_hours(pooled_act),
          "est": format_hours(pooled_est),
          "r": quantize(pooled_act / pooled_est, 2) if pooled_est else "n/a"}),
    ]

    # the horizon is the one sentence read before it is held: the rate is the plan's, and
    # the weeks are the remaining hours and the chain's midpoint over it
    rate = RATE_RE.search(raw)
    if rate is None:
        derived.append(f"{PLAN} states no attended rate in a '* Horizon: at N–N attended "
                       "hours per week' sentence, so no horizon can be derived")
    else:
        lo_rate, hi_rate = int(rate.group("lo")), int(rate.group("hi"))
        left = grand - done_h
        judged_lines.append((
            "the horizon",
            r"(?m)^\* Horizon: at \d+–\d+ attended hours per week, the (?P<left>[\d.,]+) h "
            r"remaining is (?P<wlo>\d+)–(?P<whi>\d+) attended weeks and the critical "
            r"chain's (?P<cmid>[\d.,]+) h midpoint (?P<clo>\d+)–(?P<chi>\d+) of them",
            {"left": format_hours(left), "wlo": _weeks(left, hi_rate),
             "whi": _weeks(left, lo_rate), "cmid": format_hours(chain_mid),
             "clo": _weeks(chain_mid, hi_rate), "chi": _weeks(chain_mid, lo_rate)}))

    held = 0
    for what, pattern, expected in judged_lines:
        held += len(expected)
        r = figures.resolve_line(ctx, PLAN, pattern, expected, what)
        for line in r.fixed:
            rep.line(line)
        derived.extend(r.findings)
    rep.report("K-96", "chain or calibration figure(s) the cells beneath them do not give:",
               derived,
               f"the critical chain sums over {len(chain)} open cells, the calibration "
               f"fits over {len(all_pairs)} of the record's {len(record)} rows and the "
               f"agent-parallel series over {len(ppairs)} of its own record's "
               f"{len(precord)}, and all {held} figures stated over them agree, across "
               f"{len(judged_lines)} sentences")
    rep.line()
