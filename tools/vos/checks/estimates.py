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

What the group does not compute is what the sums cannot give: the critical chain is the
author's, stated beside the derived gate figures rather than folded into them, so the two
kinds of figure stay separable.

A third authored token joins the range: an open item's **authority class**, `I` where what
the item realizes is fixed inside this repository and `X` where it is not. It is a judgment
and stays one, but everything resting on it is arithmetic and lands here: the two class
sums, and the calibrated total, which re-weights each class's open hours by the ratio that
class of completed item actually ran at. A completed item carries no class, having an actual
where the class would have widened a range.

An item carrying no cell at all is legal in one place, a parent whose children carry
the estimates, which is why the check reads the indent rather than demanding a figure
of every bullet: the parent is a heading with a checkbox, and its children are already
counted. Anything else missing a cell is counted by nothing and is the finding.
"""

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from vos import figures
from vos.figures import format_hours, percent

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
             "M6.6", "M6.7", "M6.8", "S5", "S6"]
AFTER_M8A = ["R1b", "R1c", "R2", "R3", "M8b", *AFTER_M8B]

# the outturn ratios the plan's own §12 measures over the completed items, one per authority
# class. They multiply the open hours of their class and nothing else: a completed item's
# actual is what it cost, so the calibrated figure is the done hours plus the open ones
# re-weighted, and the ratios are stated here rather than in the document because the
# document restates the figure they produce
CLASS_RATIO = {"I": 0.66, "X": 1.68}


def _hours(text: str) -> float:
    return float(text.replace(",", ""))


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

    for m in SCAN_RE.finditer(raw):
        if m.group("sec") is not None:
            if pending:
                malformed.append(f"{pending[0]}: no estimate cell, and no nested item to carry one")
                pending = None
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
            cls=klass.group("cls") if klass else None)
        items.append(item)
        bucket.append(item)

    if pending:
        malformed.append(f"{pending[0]}: no estimate cell, and no nested item to carry one")
    if bucket:
        malformed.append(f"{len(bucket)} item(s) after the last subtotal, counted by no "
                         f"total: {bucket[0].label} onward")
    return items, sections, malformed


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)

    if PLAN not in ctx.corpus:
        rep.report("K-34", "missing artifact:", [f"{PLAN} is not in the repository"])
        ctx.shared.update(items=[], sections=[])
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
    # The threshold the 1.68 ratio actually motivates, that the calibrated value lie inside the
    # range, is arithmetically unavailable beside K-35 and the conventions say so: a midpoint is
    # the mean of the range ends, so `hi >= 1.68 * mid` is `lo <= 0.32 * mid` and forces every
    # class-X span above five. Reported and never repaired, because which end of a range moves
    # is the estimate itself and not arithmetic over one.
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
    carried = {i.label.split(" · ")[0] for i in items}
    for name, partition in (("M8a", AFTER_M8A), ("M8b", AFTER_M8B)):
        if empty := [label for label in partition if label not in carried]:
            stated.append(f"the {name} partition names work the document carries no item "
                          f"under: {', '.join(empty)}")

    def _at_or_before(partition: list[str]) -> list[Item]:
        return [i for i in open_items if i.label.split(" · ")[0] not in partition]

    # the software gate is what open work falls at or before it, where the old single gate
    # was the whole midpoint less the deferred tail; the two differ by the completed hours,
    # and the open reading is the one a schedule is made against
    gate_a = _at_or_before(AFTER_M8A)
    gate_a_h = round(sum(i.hours for i in gate_a), 1)
    gate_a_x = round(sum(i.hours for i in gate_a if i.cls == "X"), 1)
    # the RTL chain is what the two partitions differ by: after the software gate, and not
    # deferred past the co-simulation one, so it runs beside rather than behind
    chain_b = round(sum(i.hours for i in open_items
                        if i.label.split(" · ")[0] in AFTER_M8A
                        and i.label.split(" · ")[0] not in AFTER_M8B), 1)

    by_class = {c: round(sum(i.hours for i in open_items if i.cls == c), 1)
                for c in CLASS_RATIO}
    calibrated = round(done_h + sum(CLASS_RATIO[c] * h for c, h in by_class.items()), 1)

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
        ("the calibrated total",
         r"(?m)^\* Calibrated against completed-item outturn \(class I 0\.66, class X "
         r"1\.68\): approximately (?P<cal>[\d.,]+) h",
         {"cal": format_hours(calibrated)}),
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
    rep.line()
