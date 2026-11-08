# SPDX-License-Identifier: Apache-2.0
"""Check that [freeze-measurement.md](../../../docs/implementation/contracts/freeze-measurement.md) accounts for every item in `R-15-014a`'s closed freeze delta (`K-70`)."""

import re
from typing import TYPE_CHECKING

from vos import figures
from vos.register import REQ_TOKEN_RE

if TYPE_CHECKING:
    from . import Context

CONTRACT = "docs/implementation/contracts/freeze-measurement.md"
DELTA_OWNER = "R-15-014a"

DELTA_MARKS = ("i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii")

DELTA_MARK_RE = re.compile(r"\(([ivx]+)\)")
# §1 rows open with the marker of the item they instrument (including "(iv, continued)").
INSTRUMENT_ROW_RE = re.compile(r"(?m)^\| \(([ivx]+)[,)]")
# Phrase distinguishing §10 delta-boundary bullets from other §10 bullets that cite requirements.
BOUNDARY_MARK = "not this instrument's"

DELTA_TOTAL_RE = re.compile(r"delta is closed at ([\w-]+) enumerated items")
DELTA_SPLIT_RE = re.compile(
    r"\*\*([\w-]+) of the ([\w-]+) are measured against generated output\*\*")
DELTA_REST_RE = re.compile(r"The remaining ([\w-]+) are re-derived at that same act")
DELTA_BOUND_RE = re.compile(r"Two of R-15-014a's ([\w-]+) delta items")

# (pattern, capture_group, count_key, description)
DELTA_FIGURES: list[tuple[re.Pattern[str], int, str, str]] = [
    (DELTA_TOTAL_RE, 1, "total", "the delta's size where the measured act is introduced"),
    (DELTA_SPLIT_RE, 1, "instrumented", "the share §1 instruments"),
    (DELTA_SPLIT_RE, 2, "total", "the delta's size beside the instrumented share"),
    (DELTA_REST_RE, 1, "bounded", "the share taken elsewhere"),
    (DELTA_BOUND_RE, 1, "total", "the delta's size where §10 states its boundary"),
]


def _delta_items(body: str) -> list[tuple[str, frozenset[str]]]:
    """Return `(marker, requirement_ids)` for each `(i)`-style item in `R-15-014a`.

    Each item spans from its marker to the next marker (or to the end of its sentence
    for the final item, excluding the trailing amendment clause).
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
    """Return the slice of `raw` from `heading` to the next `## ` heading."""
    at = raw.find(heading)
    if at < 0:
        return ""
    end = raw.find("\n## ", at + len(heading))
    return raw[at:end if end >= 0 else len(raw)]


def freeze_delta(ctx: Context) -> None:
    """K-70: every item of `R-15-014a`'s closed freeze delta is accounted for once in [freeze-measurement.md](../../../docs/implementation/contracts/freeze-measurement.md).

    Checks that:
    1. Every enumerated `(i)`..`(n)` item in `R-15-014a` is either instrumented by a §1
       table row (matched by marker) or declared out of reach by a §10 boundary bullet
       containing `BOUNDARY_MARK` (matched by requirement-set containment), and never
       both.
    2. Every count-word restatement of the total, instrumented, and bounded counts in
       `DELTA_FIGURES` matches the partition.
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
