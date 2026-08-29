# SPDX-License-Identifier: Apache-2.0
"""counts, the freeze delta: a closed enumeration, and the instrument over it.

R-15-014a closes the freeze's second act by enumerating its delta, and the freeze
measurement contract is what quantifies over that enumeration: a §1 row instruments
an item, a §10 bullet declares one out of the instrument's reach. Every item is owed
exactly one of the two, and the contract's own restatements of the enumeration's size
and its split are read against the register's count rather than against each other.
"""

import re
from typing import TYPE_CHECKING

from vos import figures
from vos.register import REQ_TOKEN_RE

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

# K-70: the freeze's closed delta and the instrument that quantifies over it.
CONTRACT = "docs/freeze-measurement-contract.md"
DELTA_OWNER = "R-15-014a"

# The markers the entry enumerates its delta with, in the order it writes them. The
# run is read rather than a count, so an item inserted, renumbered, or dropped moves
# the sequence and is a finding rather than a quietly shorter list.
DELTA_MARKS = ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii")

DELTA_MARK_RE = re.compile(r"\(([ivx]+)\)")
# a §1 row opens its first cell with the marker of the item it instruments, and
# "(iv, continued)" is the one row carrying a second half of a single item
INSTRUMENT_ROW_RE = re.compile(r"(?m)^\| \(([ivx]+)[,)]")
# What separates a boundary declaration from everything else §10 owes elsewhere. Every
# bullet in that section cites requirements; only the ones saying an item is not this
# instrument's are declaring a delta item out of the report's reach, and reading the
# section by citation alone would let a bullet that merely mentions a governing
# requirement stand in for the declaration that never happened.
BOUNDARY_MARK = "not this instrument's"

# The contract's own restatements of the delta's shape, each read against the
# enumeration and none of them rewritten. Every one stands inside a sentence that
# states the split in words beside the figure, so a token substitution would leave the
# prose describing a partition it no longer carries: this is the judgment side of the
# arithmetic-and-judgment split, and the repair is a person's sentence.
DELTA_TOTAL_RE = re.compile(r"delta is closed at ([\w-]+) enumerated items")
DELTA_SPLIT_RE = re.compile(
    r"\*\*([\w-]+) of the ([\w-]+) are measured against generated output\*\*")
DELTA_REST_RE = re.compile(r"The remaining ([\w-]+) are re-derived at that same act")
DELTA_BOUND_RE = re.compile(r"Two of R-15-014a's ([\w-]+) delta items")

# pattern, the group carrying the figure, which figure it is, and what it states
DELTA_FIGURES: list[tuple[re.Pattern[str], int, str, str]] = [
    (DELTA_TOTAL_RE, 1, "total", "the delta's size where the measured act is introduced"),
    (DELTA_SPLIT_RE, 1, "instrumented", "the share §1 instruments"),
    (DELTA_SPLIT_RE, 2, "total", "the delta's size beside the instrumented share"),
    (DELTA_REST_RE, 1, "bounded", "the share taken elsewhere"),
    (DELTA_BOUND_RE, 1, "total", "the delta's size where §10 states its boundary"),
]


def _delta_items(body: str) -> list[tuple[str, frozenset[str]]]:
    """R-15-014a's enumerated delta: each marker, with the requirements it names.

    An item runs from its own marker to the next, and the last runs to the end of its
    own sentence, because the enumeration is followed by the amendment clause whose
    citation belongs to no item.
    """
    marks = list(DELTA_MARK_RE.finditer(body))
    items: list[tuple[str, frozenset[str]]] = []
    for i, m in enumerate(marks):
        if i + 1 < len(marks):
            end = marks[i + 1].start()
        else:
            tail = re.search(r"\.\s", body[m.end():])
            end = m.end() + tail.start() if tail else len(body)
        items.append((m.group(1), frozenset(REQ_TOKEN_RE.findall(body[m.start():end]))))
    return items


def _section(raw: str, heading: str) -> str:
    """One `## ` section of a document, from its heading to the next one."""
    at = raw.find(heading)
    if at < 0:
        return ""
    end = raw.find("\n## ", at + len(heading))
    return raw[at:end if end >= 0 else len(raw)]


def freeze_delta(ctx: Context) -> None:
    """K-70: every item of R-15-014a's closed delta, accounted for exactly once.

    The freeze's second act has a delta the register closes by enumeration, and the
    freeze measurement contract is the instrument that quantifies over it: its §1 table
    attaches a decision to each item it measures, and its §10 bullets declare the items
    it does not reach and say where they are decided instead. Between the two the
    enumeration must be covered, because the contract's own gate rejects a report in
    which a delta item has no decision row. Nothing held that: the register grew a ninth
    item and the contract went on saying eight, with every citation still resolving, the
    view still carrying every bearing requirement, and the run green.

    **Membership is by marker on one side and by governing requirement on the other**,
    which is not a preference. A §1 row opens with the item's own `(i)`-style marker, so
    it names the item exactly; a §10 bullet is prose about a boundary and carries no
    marker, so what identifies the item there is the set of requirements the register's
    item names, held by containment. That is why the boundary bullets are selected by
    the sentence that declares them rather than by citation alone: §10 also owes things
    elsewhere, and those bullets cite governing requirements too, so a bullet mentioning
    R-15-031a would otherwise stand in for a boundary declaration nobody wrote.

    **Both directions, and both are real.** An item the contract accounts for nowhere is
    the defect above. An item it accounts for twice is the opposite one: a report that
    both owes a decision row and refuses to carry one.

    **Fail-closed in the reading.** An enumeration that is not a run of the markers this
    rule reads, a contract that is absent, and a §1 or §10 that cannot be found are each
    a finding and stop the comparison, so a reworded entry or a renumbered section
    cannot take the check down with it and leave the rule passing over nothing.

    **Reported and never repaired.** The five restated figures each stand inside a
    sentence that also states the split in words, so rewriting a token would leave the
    prose describing a partition it no longer carries; which sentence is right is the
    same judgment K-61 asks for, and it is a person's.
    """
    rep, reg = ctx.rep, ctx.reg
    label = "delta item(s) the freeze contract does not account for exactly once:"

    items = _delta_items(reg.body.get(DELTA_OWNER, ""))
    marks = [mark for mark, _ in items]
    if not items or marks != list(DELTA_MARKS[:len(items)]):
        ctx.shared["delta_items"] = 0
        rep.report("K-70", label, [
            f"{DELTA_OWNER} enumerates "
            + (", ".join(f"({mark})" for mark in marks) or "nothing this rule reads")
            + ", which is not the run of markers its closed delta is written in, so "
            "there is no enumeration to hold the contract against"])
        return

    raw = ctx.text(CONTRACT)
    instrument = _section(raw, "\n## 1. ")
    boundary = _section(raw, "\n## 10. ")
    unreadable = [
        f"{CONTRACT} is not in the repository, so {DELTA_OWNER}'s delta has no "
        "instrument to be read against" if not raw else None,
        f"{CONTRACT} carries no §1 section, where the instrument table stands"
        if raw and not instrument else None,
        f"{CONTRACT} carries no §10 section, where its boundaries are stated"
        if raw and not boundary else None,
    ]
    if any(unreadable):
        ctx.shared["delta_items"] = 0
        rep.report("K-70", label, unreadable)
        return

    instrumented = {m.group(1) for m in INSTRUMENT_ROW_RE.finditer(instrument)}
    declared = [frozenset(REQ_TOKEN_RE.findall(line))
                for line in re.findall(r"(?m)^- .+", boundary)
                if BOUNDARY_MARK in line]

    findings: list[str] = []
    covered: dict[str, list[str]] = {"instrumented": [], "bounded": []}
    for mark, ids in items:
        in_table = mark in instrumented
        in_bound = bool(ids) and any(ids <= names for names in declared)
        if in_table and in_bound:
            findings.append(
                f"{DELTA_OWNER}'s item ({mark}) is instrumented by a §1 row and declared "
                "outside this instrument by a §10 bullet, so the report is owed a "
                "decision row for it and refused one")
        elif in_table or in_bound:
            covered["instrumented" if in_table else "bounded"].append(mark)
        else:
            findings.append(
                f"{DELTA_OWNER}'s item ({mark}) is accounted for by no §1 instrument row "
                "and no §10 boundary bullet, so a freeze report carries no decision row "
                "for it and the gate of §9 rejects the report")
    findings += [f"{CONTRACT} §1 instruments an item ({mark}) {DELTA_OWNER} does not "
                 "enumerate" for mark in sorted(instrumented - set(marks))]

    stated = {"total": figures.words(len(items)),
              "instrumented": figures.words(len(covered["instrumented"])),
              "bounded": figures.words(len(covered["bounded"]))}
    for pattern, group, which, what in DELTA_FIGURES:
        m = pattern.search(raw)
        if m is None:
            findings.append(f"{CONTRACT} no longer states {what} in a form this rule "
                            "reads, so the delta's shape is restated where nothing "
                            "holds it")
        elif m.group(group).lower() != stated[which]:
            findings.append(f"{CONTRACT} states {what} as '{m.group(group)}', "
                            f"{DELTA_OWNER}'s enumeration gives '{stated[which]}'")

    ctx.shared["delta_items"] = len(items)
    rep.report("K-70", label, findings,
               f"all {len(items)} items of {DELTA_OWNER}'s closed delta are accounted "
               f"for once, {len(covered['instrumented'])} by the §1 instrument table and "
               f"{len(covered['bounded'])} by §10's boundary bullets, and the "
               f"{len(DELTA_FIGURES)} restatements of that shape agree")
