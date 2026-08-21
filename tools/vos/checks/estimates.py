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

What the group does not compute is what the sums cannot give: the optimization and
gating adjustments and the critical chain are the author's, stated beside the derived
M8 figure rather than folded into it, so the two kinds of figure stay separable.

An item carrying no cell at all is legal in one place, a parent whose children carry
the estimates, which is why the check reads the indent rather than demanding a figure
of every bullet: the parent is a heading with a checkbox, and its children are already
counted. Anything else missing a cell is counted by nothing and is the finding.
"""

import re
from dataclasses import dataclass

from .. import figures
from ..figures import format_hours, percent

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

# the M8 gate figure is the total less the work that lands after the gate, and the items
# that do are named here rather than inferred, everything else falling at or before it
AFTER_GATE = ["M9", "M9a", "M10", "Post-M10"]


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


@dataclass
class Section:
    name: str
    line: str
    head: str
    tail: str
    items: list[Item]


def _parse(raw: str):
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

        label = m.group("label").strip()
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
        if not done and not opened:
            if rest.strip():
                malformed.append(f"{label}: '{rest.strip()}' is not an estimate cell")
            else:
                pending = (label, indent)
            continue

        cell = done or opened
        lo = _hours(opened.group("lo")) if opened else 0.0
        hi = _hours(opened.group("hi")) if opened else 0.0
        # every sum below reads `hours`, and for an open item that is the range's mean
        # rather than the midpoint as written: the range is the estimate, so a stated
        # midpoint that disagrees with it is a stale token, reported and rewritten
        item = Item(
            label=label, line=m.group(),
            head=m.group()[:len(m.group()) - len(rest)],
            done=bool(done),
            stated=_hours(cell.group("h")),
            hours=round((lo + hi) / 2, 1) if opened else _hours(cell.group("h")),
            lo=lo, hi=hi, tail=cell.group("tail"))
        items.append(item)
        bucket.append(item)

    if pending:
        malformed.append(f"{pending[0]}: no estimate cell, and no nested item to carry one")
    if bucket:
        malformed.append(f"{len(bucket)} item(s) after the last subtotal, counted by no "
                         f"total: {bucket[0].label} onward")
    return items, sections, malformed


def run(ctx) -> None:
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

    open_items = [i for i in items if not i.done]
    grand = round(sum(i.hours for i in items), 1)
    done_h = round(sum(i.hours for i in items if i.done), 1)
    open_lo = round(sum(i.lo for i in open_items), 1)
    open_hi = round(sum(i.hi for i in open_items), 1)

    after = [i for i in items if i.label.split(" · ")[0] in AFTER_GATE]
    stated: list[str] = []
    if len(after) != len(AFTER_GATE):
        stated.append(f"{len(AFTER_GATE)} items land after the M8 gate; the document "
                      f"carries {len(after)} of those labels")
    gate_h = round(grand - sum(i.hours for i in after), 1)

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
         r"(?m)^\* Total estimate: (?P<mid>[\d.,]+) h midpoint, range "
         r"(?P<lo>[\d.,]+)–(?P<hi>[\d.,]+) h",
         {"mid": grand_t, "lo": lo_t, "hi": hi_t}),
        ("the progress pair",
         r"(?m)^\* Progress by estimate: (?P<done>[\d.,]+) of (?P<total>[\d.,]+) h complete "
         r"\((?P<donePct>[\d.]+)%\); (?P<left>[\d.,]+) h remaining \((?P<leftPct>[\d.]+)%\)",
         {"done": format_hours(done_h), "total": grand_t,
          "donePct": percent(done_h, grand, 1),
          "left": format_hours(grand - done_h),
          "leftPct": percent(grand - done_h, grand, 1)}),
        ("the M8 gate figure",
         r"(?m)^\* M8 gate: (?P<gate>[\d.,]+) h of the (?P<total>[\d.,]+) h midpoint",
         {"gate": format_hours(gate_h), "total": grand_t}),
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
