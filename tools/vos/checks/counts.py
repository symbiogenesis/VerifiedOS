# SPDX-License-Identifier: Apache-2.0
"""counts: every figure any document asserts, against the artifact it derives from.

"1290 requirements", "twenty-two crown-jewel specifications", "sixteen enumerated
absences" are all restatements of something a table already holds. Each quantity is
computed here; each claim says where it is asserted and in which style, and captures
the number alone, so a repair is the substitution of a single token.
"""

import re
from typing import TYPE_CHECKING

from .. import figures
from ..register import REGISTER, cj_class, cj_status

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== counts: every asserted figure against its artifact ==="

# file, quantity, style, and the pattern that captures the stated figure alone
CLAIMS = [
    # the register states its own coverage
    (REGISTER, "sections", "words", r"[\w-]+(?= normative sections are extracted)"),
    (REGISTER, "requirements", "digits", r"(?<=extracted, at )[\d,]+(?= requirements)"),
    (REGISTER, "lettered", "digits", r"(?<=Counts include the )[\w,-]+(?= letter-suffixed entries)"),

    # the crown-jewel inventory states its own status ratio
    ("docs/crown-jewels.md", "cj-targets", "digits", r"[\d]+(?= entries, all used)"),
    ("docs/crown-jewels.md", "cj-theorems", "words", r"(?<=The remaining )[\w-]+(?= `CJ-` targets name)"),
    ("docs/crown-jewels.md", "cj-unauthored", "words", r"[\w-]+(?= of those [\w-]+ are not authored)"),
    ("docs/crown-jewels.md", "cj-specs", "words", r"(?<=of those )[\w-]+(?= are not authored)"),
    ("docs/crown-jewels.md", "cj-targets", "digits", r"[\d]+(?= targets, every one used)"),
    ("docs/crown-jewels.md", "cj-targets", "digits", r"[\d]+(?= coarse targets)"),
    ("docs/crown-jewels.md", "cj-specs", "digits", r"[\d]+(?= specifications, per-member)"),
    ("docs/crown-jewels.md", "cj-authored", "words", r"[\w-]+(?= of [\w-]+ are authored outright)"),
    ("docs/crown-jewels.md", "cj-specs", "words", r"(?<=of )[\w-]+(?= are authored outright)"),
    ("docs/crown-jewels.md", "cj-partial", "words", r"(?<=and )[\w-]+(?= more are partial)"),
    ("docs/crown-jewels.md", "cj-specs", "words", r"(?<=because these )[\w-]+(?= are \*named)"),
    ("docs/crown-jewels.md", "cj-unauthored", "words", r"[\w-]+(?= of them are not yet written)"),
    ("docs/crown-jewels.md", "cj-theorems", "words", r"(?<=the )[\w-]+(?= theorem targets above cannot start)"),
    ("docs/crown-jewels.md", "cj-conferring", "words", r"(?<=There are )[\w-]+(?= such entries)"),

    # the prose states the size of each seam register it carries
    ("docs/spec.md", "fc-seams", "words", r"[\w-]+(?= fail-closed seams are named with owners)"),

    # and the register states the shape of each enumeration it closes by conferral
    (REGISTER, "fc-conferrals", "words", r"[\w-]+(?= requirements confer a refusal)"),
    (REGISTER, "fc-seams", "words", r"(?<=and )[\w-]+(?= seams collect them)"),
    (REGISTER, "rot-fresh", "words", r"[\w-]+(?= requirements confer freshness)"),

    # the coverage matrix states the shape of its own product
    ("docs/coverage-matrix.md", "boundaries", "words", r"(?<=below are )[\w-]+(?= boundaries)"),
    ("docs/coverage-matrix.md", "properties", "words", r"(?<=boundaries and )[\w-]+(?= properties)"),
    ("docs/coverage-matrix.md", "cells", "words", r"(?<=carries all )[\w-]+(?= of their pairs)"),

    # the README summarizes them
    ("README.md", "views", "words", r"[\w-]+(?= \*\*derived views\*\* collect)"),
    ("README.md", "sections", "words", r"(?<=covers all )[\w-]+(?= normative sections)"),
    ("README.md", "requirements", "digits", r"(?<=sections as )[\d,]+(?= numbered requirements)"),
    ("README.md", "absences", "words", r"[\w-]+(?= enumerated absences)"),
    ("README.md", "cj-specs", "words", r"(?<=the )[\w-]+(?= specifications the review gate audits)"),
    ("README.md", "cj-theorems", "words", r"(?<=plus the )[\w-]+(?= theorem targets)"),

    # the gap catalogue argues from them
    ("docs/critique.md", "views", "words", r"(?<=register and the )[\w-]+(?= derived views)"),
    ("docs/critique.md", "fc-conferrals", "words", r"[\w-]+(?= conferrals against)"),
    ("docs/critique.md", "fc-seams", "words", r"(?<=conferrals against )[\w-]+(?= seams)"),
    ("docs/critique.md", "dispositions", "words", r"[\w-]+(?= candidates stand dispositioned)"),
    ("docs/critique.md", "rot-cases", "words", r"(?<=[Tt]he )[\w-]+(?= on the RoT-fresh side)"),
    ("docs/critique.md", "cj-specs", "words", r"[\w-]+(?= crown-jewel specifications are named)"),
    ("docs/critique.md", "cj-theorems", "words", r"[\w-]+(?= theorem targets are named)"),
    ("docs/critique.md", "cj-specs", "words", r"(?<=of )[\w-]+(?= crown-jewel specifications, \*\*)"),
    ("docs/critique.md", "cj-authored", "words", r"(?<=are named; \*\*)[\w-]+(?=\*\* are authored)"),
    ("docs/critique.md", "cj-authored", "words", r"[\w-]+(?= are authored\*\* \(the frozen)"),
    ("docs/critique.md", "cj-partial", "words", r"(?<=machine-checked statement\), )[\w-]+(?= are partial)"),
    ("docs/critique.md", "cj-unauthored", "words", r"(?<=\*\*)[\w-]+(?= are not authored\*\*)"),
    ("docs/critique.md", "cj-theorems", "words", r"(?<=The )[\w-]+(?= theorem targets each depend)"),
    ("docs/critique.md", "cj-unauthored", "words", r"[\w-]+(?= of those premises do not exist)"),
    ("docs/critique.md", "cj-specs", "words", r"[\w-]+(?= crown jewels, each a small oracle)"),
    ("docs/critique.md", "requirements", "digits", r"(?<=of )[\d,]+(?= acceptance criteria)"),
    ("docs/critique.md", "requirements", "digits", r"(?<=of the )[\d,]+(?= requirements has yet been booked)"),
]

# The claims are the whole mechanism, so a restatement nobody registered is not checked
# at all: right on the day it is written, drifting from then on, and under a repair left
# alone while its neighbours are rewritten around it, which is worse than being
# unchecked, because the document then disagrees with itself. Nothing announces a new
# figure, so the trap is the value: a distinctive form standing on the same line as a
# noun one of these quantities is counted in, and outside the span of every claim, is a
# figure that escaped the register.
COUNTED_NOUN = re.compile(
    r"requirement|acceptance criteri|normative section|crown.jewel|specification|"
    r"theorem target|`CJ-`|absence|boundar|propert|pair|cell|derived view|seam|"
    r"CSR|letter-suffixed|such entries", re.IGNORECASE)

# The trailing lookahead keeps CRLF out of the match: an anchored `\|$` never matches a
# CRLF file, and every row would read as missing.
COVERAGE_ROW_RE = r"(?m)^\| \*\*§(\d+) [^|]*\| \*\*extracted\*\* \| \*\*(\d+)\*\* \|(?=\r?$)"


def _form_sites(form_re: re.Pattern[str], forms: list[str], raw: str) -> list[re.Match[str]]:
    """Every site the form pattern decides, reached through the literals it is built of.

    The pattern is an alternation of the forms the counted quantities take, spelled words
    and digit strings alike, each under a boundary on both sides and the whole under a
    case-insensitive flag. An alternation gives the engine no literal to pre-scan
    for, so it tries every branch at every one of three million positions to return the
    few dozen sites the corpus actually states, and it is the most expensive scan a run
    performs. `str.find` proposes those sites instead, over the case-folded text so that
    a capitalised form is proposed too, and the pattern decides each one: this is the
    pattern's own answer and only the order of the search differs, which is the same
    bargain `figures.find_all` strikes for the claims.

    A fold that is not length-preserving would move every offset under the proposal, so
    the document is read whole rather than searched through a text that no longer lines
    up with it.
    """
    folded = raw.lower()
    if len(folded) != len(raw):
        return list(form_re.finditer(raw))

    sites: set[int] = set()
    for form in forms:
        at = folded.find(form)
        while at >= 0:
            sites.add(at)
            at = folded.find(form, at + 1)

    return [m for at in sorted(sites) if (m := form_re.match(raw, at))]


def _quantities(ctx: Context) -> dict[str, int]:
    reg, art, sh = ctx.reg, ctx.art, ctx.shared
    classes = [cj_class(row) for row in art.cj_rows]
    return {
        "requirements": len(reg.ids),
        "lettered": sum(1 for i in reg.ids if i[-1].isalpha()),
        "sections": len(reg.per_section),
        "cj-targets": len(reg.cj_targets),
        "cj-specs": len(art.cj_rows),
        "cj-authored": classes.count("authored"),
        "cj-partial": classes.count("partial"),
        "cj-unauthored": classes.count("unauthored"),
        "cj-theorems": sum(1 for ln in art.cj_lines
                           if re.match(r"^\| `CJ-[A-Z-]+` \|", ln)),
        "cj-conferring": len(sh["cj_confer"]),
        "fc-seams": len(sh["fc_seams"]),
        "fc-conferrals": len(sh["fc_confer"]),
        "rot-fresh": len(sh["rf_confer"]),
        "dispositions": sh["dispositions"],
        "rot-cases": sh["rot_cases"],
        "views": len(ctx.views),
        "boundaries": len(art.cm_bounds),
        "properties": len(art.cm_props),
        "cells": len(art.cm_cells),
        "absences": len(art.absence_ids),
    }


def run(ctx: Context) -> None:
    rep, reg, art = ctx.rep, ctx.reg, ctx.art
    ctx.q = _quantities(ctx)
    ctx.claims = CLAIMS
    rep.line(HEADING)

    def expected(quantity: str, style: str) -> str:
        n = ctx.q[quantity]
        return figures.words(n) if style == "words" else str(n)

    claim_spans: dict[str, list[re.Match[str]]] = {}
    missed: list[str] = []
    for file, quantity, style, pattern in CLAIMS:
        r = figures.resolve_claim(ctx, file, pattern, expected(quantity, style), quantity)
        if r.fixed:
            rep.line(r.fixed)
        if r.finding:
            missed.append(r.finding)
        claim_spans.setdefault(file, []).extend(r.spans)
    rep.report("K-24", "asserted count(s) disagreeing with their artifact:", missed,
               f"all {len(CLAIMS)} asserted counts agree")

    # --- the status column is three classes, and every row is in one ----------------
    rep.report("K-25", "crown-jewel row(s) whose status is in no class:",
               [f"row {row.split('|')[1].strip()}: {cj_status(row)}"
                for row in art.cj_rows if not cj_class(row)],
               f"{ctx.q['cj-specs']} rows partition into {ctx.q['cj-authored']} authored, "
               f"{ctx.q['cj-partial']} partial, {ctx.q['cj-unauthored']} not authored")

    # --- a figure stated where no claim holds it ------------------------------------
    forms: dict[str, list[str]] = {}
    for quantity, value in ctx.q.items():
        form = figures.distinctive(value)
        if form:
            forms.setdefault(form, []).append(quantity)

    loose: list[str] = []
    if forms:
        # one alternation over all the distinctive forms, longest first so a compound
        # word form is never eaten by its own prefix; the hits are grouped back by form
        # so the findings keep the per-form order the quantity table gives them
        ordered = sorted(forms, key=len, reverse=True)
        form_re = re.compile(
            r"(?i)(?<![\w-])(?:" + "|".join(re.escape(f) for f in ordered) + r")(?![\w-])")

        for doc in ctx.corpus.docs:
            was_fixed = doc.name in ctx.fixed
            raw = ctx.text(doc.name)
            if not raw:
                continue

            # a repaired file's offsets moved, so its held spans are found again on the
            # new text; everywhere else the spans the claims loop found are reused
            if was_fixed:
                held = [m for f, _, _, p in CLAIMS if f == doc.name
                        for m in re.finditer(p, raw)]
            else:
                held = claim_spans.get(doc.name, [])

            by_form: dict[str, list[re.Match[str]]] = {}
            for m in _form_sites(form_re, ordered, raw):
                by_form.setdefault(m.group().lower(), []).append(m)

            for form, quantities in forms.items():
                for m in by_form.get(form, []):
                    rest = raw[m.start():m.start() + 80].split("\n", 1)[0]
                    if not COUNTED_NOUN.search(rest):
                        continue
                    if any(s.start() <= m.start() < s.end() for s in held):
                        continue
                    line = (raw.count("\n", 0, m.start()) + 1 if was_fixed
                            else doc.at(m.start()))
                    loose.append(f"{doc.name}:{line} states '{m.group()}' where no claim "
                                 f"holds it, for {' or '.join(quantities)}")
    rep.report("K-26", "unheld restatement(s) of a counted figure:", loose,
               "every stated figure is held by a claim")

    # --- the Coverage table is one row per section, with the right count -------------
    register_raw = ctx.text(REGISTER)
    rows = list(re.finditer(COVERAGE_ROW_RE, register_raw))
    listed = [m.group(1) for m in rows]

    mismatched = [f"§{s} has no Coverage row" for s in reg.per_section if s not in listed]
    mismatched += [f"Coverage row §{s} names no section" for s in listed
                   if s not in reg.per_section]
    rep.report("K-27", "Coverage row(s) not matching the section list:", mismatched,
               f"{len(rows)} Coverage rows, one per section")

    # A row naming a section the register does not carry is K-27's finding, and it is
    # this rule's only unrepairable one: there is no count to write into it. It is
    # reported here too rather than skipped, because a row whose count agrees with
    # nothing is exactly as wrong as one whose count disagrees.
    def held(m: re.Match[str]) -> int | None:
        return reg.per_section.get(m.group(1))

    wrong = [m for m in rows if int(m.group(2)) != held(m)]
    repairable = [m for m in wrong if held(m) is not None]

    repairing = ctx.fix and bool(repairable)
    if repairing:
        def repair(m: re.Match[str]) -> str:
            count = held(m)
            return (m.group() if count is None
                    else re.sub(r"\*\*\d+\*\* \|$", f"**{count}** |", m.group()))
        ctx.fixed[REGISTER] = re.sub(COVERAGE_ROW_RE, repair, register_raw)
        for m in repairable:
            rep.line(f"fixed: Coverage §{m.group(1)}: {m.group(2)} -> {held(m)}")
        wrong = [m for m in wrong if held(m) is None]

    # a repair that reached everything says so by rewriting, not by also reporting green
    if wrong or not repairing:
        rep.report("K-28", "Coverage row(s) disagreeing with the register:",
                   [f"§{m.group(1)} says {m.group(2)}, register holds "
                    f"{held(m) if held(m) is not None else 'no such section'}"
                    for m in wrong],
                   "every Coverage row matches the register")
    rep.line()
