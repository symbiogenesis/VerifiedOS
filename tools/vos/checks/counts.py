# SPDX-License-Identifier: Apache-2.0
"""counts: every figure any document asserts, against the artifact it derives from.

"N requirements" and "N crown-jewel specifications" are
restatements of something a table already holds, and the figure each stands in for is
the table's rather than this docstring's. Each quantity is
computed here; each claim says where it is asserted and in which style, and captures
the number alone, so a repair is the substitution of a single token.

A cardinality is not the only figure a document can restate, and the second kind is
here for the same reason the first is. The tag plane's cost is not a count of anything:
it is one register field, the granule width, read as a ratio, and four documents state
that ratio in four spellings between them. Nothing about it is anybody's measurement,
so a granule that moves has to move every one of them in the same edit, which is
exactly what a claim is. The band beside it is the other half and is not arithmetic at
all, the DECTED code over the plane being fixed at no width; that half is held by
inequality against the bare figure and never rewritten.

**The group is one heading and several files.** This module is the group's entry
point and holds the claim table, the quantity table every claim is held against, and
the run; each of the other figures it is responsible for lives in a `counts_*.py`
module beside it, one per family, named for the artifact its rules read: the tag
plane, the owned figures, the capability format, the welded block, the freeze delta,
the core classes, the model window, and the shipped configurations. The group name,
the heading, and every rule id are unchanged by that split, and `check-rules.md`
registers a rule by its id and its group rather than by the file carrying it.

**The order `run` calls them in is load-bearing and not alphabetical.** A rule may
read what an earlier one left on the `Context` and never the other way round, which is
the same dependency order the package's own `GROUPS` list is in: the claims resolve
against the quantity table before anything else reads it, the model window is opened
once and handed to both rules that scan it, and the floors group prices, after this
group has run, every enumeration each of them recorded.
"""

import re
from typing import TYPE_CHECKING

from vos import coread, figures
from vos import corpus as corpus_mod
from vos.checks.counts_capcauses import cap_causes
from vos.checks.counts_capformat import cap_format
from vos.checks.counts_configs import (
    aperture_placements,
    device_region_executability,
    excluded_by_name_keys,
    shipped_configurations,
    vectorless_configurations,
)
from vos.checks.counts_coreclass import core_classes
from vos.checks.counts_delta import freeze_delta
from vos.checks.counts_fields import GRANULE_RE, PAYLOAD_RE
from vos.checks.counts_geometry import block_geometry
from vos.checks.counts_model import citation_window, excluded_forms, model_citations
from vos.checks.counts_owned import owned_figures
from vos.checks.counts_tagplane import TAG_PLANE, tag_plane
from vos.cli import provision
from vos.register import REGISTER, cj_class, cj_status

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

# The group's public surface, declared rather than incidental: what this module
# defines, and the three names it re-exports from the families for the readers that
# ask the group for them rather than the family.
__all__ = ["CLAIMS", "GRANULE_RE", "HEADING", "PAYLOAD_RE", "TAG_PLANE", "run"]

HEADING = "=== counts: every asserted figure against its artifact ==="

SPEC = "docs/spec.md"
TAL = "docs/languages/typed-assembly-language.md"
TOOLS_README = "tools/README.md"
PLAN = "docs/implementation/implementation-checklist.md"
# Historical landing measurements are deliberately not live repair targets.
LOG = "docs/implementation/completion-log.md"

# file, quantity, style, and the pattern that captures the stated figure alone
CLAIMS = [
    # the register states its own coverage
    (REGISTER, "sections", "words", r"[\w-]+(?= normative sections are extracted)"),
    (REGISTER, "requirements", "digits", r"(?<=extracted, at )[\d,]+(?= requirements)"),
    (REGISTER, "lettered", "digits", r"(?<=Counts include the )[\w,-]+(?= letter-suffixed entries)"),

    # the prose states the size of each seam register it carries
    ("docs/spec.md", "fc-seams", "words", r"[\w-]+(?= fail-closed seams are named with owners)"),

    # and the register states the shape of each enumeration it closes by conferral
    (REGISTER, "fc-conferrals", "words", r"[\w-]+(?= requirements confer a refusal)"),
    (REGISTER, "fc-seams", "words", r"(?<=and )[\w-]+(?= seams collect them)"),
    (REGISTER, "rot-fresh", "words", r"[\w-]+(?= requirements confer freshness)"),

    # the four unary invariants, owned by R-05-159's enumeration
    (REGISTER, "unary-invariants", "words", r"[\w-]+(?= unary invariants form the substrate)"),
    (REGISTER, "unary-invariants", "words", r"(?<=against the )[\w-]+(?= unary invariants)"),
    (SPEC, "unary-invariants", "words", r"(?<=the )[\w-]+(?= unary invariants that make)"),
    (SPEC, "unary-invariants", "words", r"(?<=against the )[\w-]+(?= unary invariants)"),
    (SPEC, "unary-invariants", "words", r"(?<=the )[\w-]+(?= invariants and the seam lemmas)"),

    # the nine seam lemmas, owned by R-05-160's semicolon list; the prose states the
    # list without its count, so the register's is the one count-word to hold
    (REGISTER, "seam-lemmas", "words", r"(?<=seam lemmas are exactly )[\w-]+(?=: NI)"),

    # the frozen theory's absences, owned by the entries themselves
    (SPEC, "frozen-absences", "words", r"(?<=the )[\w-]+(?= absences that produce)"),
    (TAL, "frozen-absences", "words", r"(?<=### 7\.1 The )[\w-]+(?= absences)"),
    (TAL, "frozen-absences", "words", r"(?<=The )[\w-]+(?= absences hold)"),

    # the five-part admission test, owned by R-15-010's own markers
    (REGISTER, "admission-tests", "words", r"(?<=satisfies all )[\w-]+(?= tests)"),
    (REGISTER, "admission-tests", "words", r"(?<=### 15\.2 The )[\w-]+(?=-part admission test)"),
    (REGISTER, "admission-tests", "words", r"(?<=carries )[\w-]+(?= recorded dispositions)"),
    (REGISTER, "admission-tests", "words", r"(?<=the )[\w-]+(?=-part admission test)"),
    (REGISTER, "admission-tests", "words", r"(?<=the )[\w-]+(?=-part test)"),
    (SPEC, "admission-tests", "words", r"(?<=satisfies all )[\w-]+(?= parts)"),
    (SPEC, "admission-tests", "words", r"(?<=The )[\w-]+(?=-part test governs)"),
    (SPEC, "admission-tests", "words", r"(?<=passes all )[\w-]+(?= admission tests)"),
    (SPEC, "admission-tests", "words", r"(?<=the )[\w-]+(?=-part mechanism test)"),
    (SPEC, "admission-tests", "words", r"(?<=the )[\w-]+(?=-part admission test)"),
    (SPEC, "admission-tests", "words", r"(?<=The \*\*)[\w-]+(?=-part admission test)"),

    # the TCB's item count, owned by the specification's own §6 list
    (REGISTER, "tcb-items", "words", r"(?<=exhaustively enumerated as )[\w-]+(?= items)"),
    (REGISTER, "tcb-items", "words", r"(?<=R-06-001's )[\w-]+(?=-item enumeration)"),

    # the assurance tiers, owned by the specification's own tier table
    (REGISTER, "assurance-tiers", "words", r"(?<=There are exactly )[\w-]+(?= assurance tiers)"),

    # the required-but-untrusted build artifacts, owned by their prose span's markers
    (REGISTER, "build-prereqs", "words", r"[\w-]+(?= artifacts are hard prerequisites)"),
    (REGISTER, "build-prereqs", "words", r"(?<=list has )[\w-]+(?= entries rather than five)"),
    (SPEC, "build-prereqs", "words", r"(?<=All )[\w-]+(?= are untrusted evidence-producing)"),

    # the one program logic's theories, owned by R-13-017's roster
    (REGISTER, "iris-theories", "words", r"(?<=program logic with its )[\w-]+(?= theories)"),
    (REGISTER, "iris-theories", "words", r"(?<=program logic with )[\w-]+(?= theories, not five frameworks)"),
    (SPEC, "iris-theories", "words", r"(?<=logic\*\* with its )[\w-]+(?= theories)"),
    (SPEC, "iris-theories", "words", r"(?<=Iris-over-Sail logic with )[\w-]+(?= theories)"),

    # the machine-checked radio protocols, owned by the inventory-row span R-12-043e pins
    (REGISTER, "radio-protocols", "words", r"(?<=and for the )[\w-]+(?= radio protocols)"),
    (REGISTER, "radio-protocols", "words", r"(?<=narrowed for the )[\w-]+(?= radio protocols)"),
    (REGISTER, "radio-protocols", "words", r"(?<=analyzed models for the )[\w-]+(?= radio protocols)"),
    (SPEC, "radio-protocols", "words", r"(?<=for the )[\w-]+(?= radio protocols that layer)"),
]

# The trailing lookahead keeps CRLF out of the match: an anchored `\|$` never matches a
# CRLF file, and every row would read as missing.
COVERAGE_ROW_RE = r"(?m)^\| \*\*§(\d+) [^|]*\| \*\*extracted\*\* \| \*\*(\d+)\*\* \|(?=\r?$)"

# The enumerations the co-statement survey found restated as counts across K-61
# pairs, each read from the one entry that owns it rather than declared here: the
# count moves with the list. Incidental type-obligation count words are omitted;
# its owner still has a nonempty guard independent of the remaining prose claims.
TYPE_OBLIGATIONS_RE = re.compile(r"obligations are exactly: ([^.]+)\.")
UNARY_INVARIANTS_RE = re.compile(
    r"unary invariants form the substrate every seam assumes: (.+)")
SEAM_LEMMAS_RE = re.compile(r"seam lemmas are exactly [\w-]+: ([^.]+)\.")
# the roster ends where the entry turns to what the theories instantiate, so the
# capture is bounded by that turn rather than by a period the names never carry
IRIS_THEORIES_RE = re.compile(r"theories, not five frameworks: (.+?), all instantiating")
# a parenthesized single digit is an enumeration's own marker; a requirement id or a
# section reference never takes that shape
ENUM_MARK_RE = re.compile(r"\(\d\)")
RADIO_ROWS_RE = re.compile(r"inventory rows (\d+)–(\d+)")
TCB_ITEM_RE = re.compile(r"^\d+\. ")
TIER_ROW_RE = re.compile(r"^\s*\| \*\*Tier \d")


_PARENTHETICAL_RE = re.compile(r"\([^)]*\)")

# Every quantity declares its source guard independently of whether prose repeats it.
# Required sources may not read empty. Optional buckets are bounded by a required
# parent, so a legitimate zero never disguises a missing inventory.
REQUIRED_COUNTS = {
    "requirements": "the requirements register",
    "lettered": "the register's permanent letter-suffixed entries",
    "sections": "the register's normative sections",
    "cj-targets": "the register's crown-jewel trace legend",
    "cj-specs": "the crown-jewel inventory",
    "cj-theorems": "the inventory's theorem-target table",
    "cj-conferring": "the requirements conferring crown-jewel membership",
    "fc-seams": "the fail-closed seam register",
    "fc-conferrals": "the requirements conferring refusals",
    "rot-fresh": "the requirements conferring freshness",
    "dispositions": "the reviewed candidate dispositions",
    "rot-cases": "the freshness candidate dispositions",
    "views": "the declared derived views",
    "boundaries": "the coverage matrix's boundary enumeration",
    "properties": "the coverage matrix's property enumeration",
    "cells": "the coverage matrix's cells",
    "model-facts": "the MODEL_FACTS value-window declaration",
    "type-obligations": "R-05-029's type-level obligation enumeration",
    "unary-invariants": "R-05-159's unary invariant enumeration",
    "seam-lemmas": "R-05-160's seam lemma enumeration",
    "frozen-absences": "the register's frozen-theory absence entries",
    "admission-tests": "R-15-010's admission test enumeration",
    "tcb-items": "the specification's TCB enumeration",
    "assurance-tiers": "the specification's assurance tier table",
    "build-prereqs": "the specification's R-06-024 prerequisite enumeration",
    "radio-protocols": "R-12-043e's inventory-row range",
    "iris-theories": "R-13-017's theory enumeration",
    "provision-facts": "the provisioner's FACTS declaration",
    "provision-switches": "the provisioner's switch rows",
}
OPTIONAL_COUNTS = {
    "cj-authored": "cj-specs",
    "cj-partial": "cj-specs",
    "cj-unauthored": "cj-specs",
    "cells-authored": "cells",
    "cells-partial": "cells",
    "cells-unauthored": "cells",
    "provision-uncommanded": "provision-facts",
}


def count_owner_findings(quantities: dict[str, int]) -> list[str]:
    """Reject missing owner readings and undeclared policies; allow bounded zeros."""
    findings = [f"{name} is computed without a declared owner guard"
                for name in sorted(quantities.keys() - REQUIRED_COUNTS.keys()
                                   - OPTIONAL_COUNTS.keys())]
    findings += [f"{name} has both required and optional owner policies"
                 for name in sorted(REQUIRED_COUNTS.keys() & OPTIONAL_COUNTS.keys())]
    for name, owner in REQUIRED_COUNTS.items():
        if quantities.get(name, 0) <= 0:
            findings.append(f"{name} reads no members from {owner}")
    for name, parent in OPTIONAL_COUNTS.items():
        if parent not in REQUIRED_COUNTS or parent not in quantities:
            findings.append(f"{name} names {parent}, which is not a recorded required owner")
        value = quantities.get(name)
        if value is None or not 0 <= value <= quantities.get(parent, 0):
            findings.append(f"{name} must be a recorded bucket within {parent}")
    return findings


# K-26 declares both the subject and the document in which it denotes a live
# inventory. Completion evidence is deliberately absent. Bare numbers or generic
# nouns in unrelated documents never become candidates when an inventory grows.
# A final field bounds the register introduction before normative entries begin.
# New subjects and document scopes need explicit registration and a regression.
_CROWN_SUBJECT = r"(?:crown[- ]jewel specifications|coarse targets|theorem targets|`CJ-` targets)"
COUNT_SCOPES = [
    (file, "crown-jewel inventory", _CROWN_SUBJECT, "")
    for file in ("README.md", REGISTER, SPEC, TAL, TOOLS_README, PLAN,
                 "docs/assurance/crown-jewels.md", "docs/background/critique.md",
                 "docs/assurance/coverage-matrix.md")
] + [
    (REGISTER, "register summary",
     r"(?:requirements|normative sections|letter-suffixed entries)", "## §1."),
    ("docs/assurance/coverage-matrix.md", "coverage product",
     r"(?:boundaries|properties|(?:boundary-property|coverage) (?:pairs|cells)|of their pairs)", ""),
    ("docs/assurance/differential-corpus.md", "differential corpus", r"purecap programs", ""),
    (TOOLS_README, "tool declarations", r"(?:files by path|opam switches)", ""),
] + [
    (file, "canonical type obligations", r"type-level obligations", "")
    for file in (REGISTER, SPEC, TAL)
]

# Word spellings are a fixed lexical grammar, not the current values of inventories.
# Digits have no upper bound; boundaries prevent reading a decimal, a version or one
# group of a comma-separated integer as an independent count.
_COUNT_WORDS = "|".join(sorted((figures.words(n) for n in range(100)),
                             key=len, reverse=True))
_COUNT_FORM = (r"(?<![\w,.-])(?P<count>(?:\d{1,3}(?:,\d{3})+|\d+|"
               + _COUNT_WORDS + r"))(?![\w-]|[,.]\d)")


def unheld_counts(ctx: Context) -> list[str]:
    """Find unregistered live counts in explicit subject/document scopes.

    Claims are found again on the current text so a preceding repair cannot leave
    stale offsets. Fenced examples are not assertions. Findings are deduplicated
    when a subject participates in more than one declared scope.
    """
    findings: dict[tuple[str, int], str] = {}
    for file, subject, noun, until in COUNT_SCOPES:
        raw = ctx.text(file)
        if not raw:
            continue
        # The introduction is deliberately a bounded scope, not a keyword search
        # over the register's normative contract quantities.
        end = raw.find(until) if until else -1
        scoped = raw[:end] if end >= 0 else raw
        held = [m.span() for f, _, _, pattern in CLAIMS if f == file
                for m in re.finditer(pattern, raw)]
        fenced = corpus_mod.fence_lines(raw.splitlines())
        pattern = re.compile(_COUNT_FORM + r"[*`]*[ \t]+(?:" + noun + r")\b",
                             re.IGNORECASE)
        for match in pattern.finditer(scoped):
            start, finish = match.span("count")
            line = raw.count("\n", 0, start)
            if fenced[line] or any(a <= start and finish <= b for a, b in held):
                continue
            findings[file, start] = (
                f"{file}:{line + 1} states '{match['count']}' where no claim holds it, "
                f"for {subject}")
    return list(findings.values())


def _enumeration(pattern: re.Pattern[str], text: str, sep: str = ",") -> int:
    """The member count of an owned enumeration, zero where the owner has moved.

    Parentheticals are stripped before the split, so a comma inside a member's
    gloss is never a member; what this cannot survive is a separator gaining a
    second meaning inside a member's bare text, which is the register's own
    single-line entry grammar to refuse.
    """
    m = pattern.search(text)
    if not m:
        return 0
    bare = _PARENTHETICAL_RE.sub("", m.group(1))
    return len([s for s in bare.split(sep) if s.strip()])


def _spec_lines(ctx: Context, lead: str, pattern: re.Pattern[str],
                until: str | None = None) -> int:
    """Lines of the specification a pattern decides, optionally scoped to run from
    one heading to the next `## `. The fence mask is honored as everywhere."""
    doc = ctx.corpus.get(SPEC)
    if doc is None:
        return 0
    inside = until is None
    n = 0
    for i, line in enumerate(doc.lines):
        if until is not None:
            if line.startswith(until):
                inside = True
                continue
            if inside and line.startswith("## "):
                break
        if inside and lead in line and not doc.fenced[i] and pattern.match(line):
            n += 1
    return n


def _anchor_span_marks(ctx: Context, ident: str) -> int:
    """Count a bookmark's enumeration, including continuation lines it owns.

    Use the co-read ownership rule so a wrapped or bulleted list has the same
    extent for its count and its review. A missing bookmark still returns zero,
    which the owned-count guard refuses to treat as an empty enumeration.
    """
    if SPEC not in ctx.corpus:
        return 0
    return len(ENUM_MARK_RE.findall(coread.spans(ctx.corpus).get(ident, "")))


def _radio_protocols(reg_accept: str) -> int:
    """The curated-analysis set's size, read as the register itself states it: the
    span of crown-jewel inventory rows R-12-043e pins its lineages to."""
    m = RADIO_ROWS_RE.search(reg_accept)
    return int(m.group(2)) - int(m.group(1)) + 1 if m else 0


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
        # the cells by the standing the views group computed for each, the inventory's
        # three classes lifted over the rows a cell's requirements constrain
        "cells-authored": sh.get("cm_standing", {}).get("authored", 0),
        "cells-partial": sh.get("cm_standing", {}).get("partial", 0),
        "cells-unauthored": sh.get("cm_standing", {}).get("unauthored", 0),
        "model-facts": len(corpus_mod.MODEL_FACTS),
        # the counts the co-statement survey found restated across K-61 pairs, each
        # computed from the artifact that owns it: an entry's own enumeration, the
        # specification's own list or table, or the row range the register pins
        "type-obligations": _enumeration(TYPE_OBLIGATIONS_RE,
                                         reg.body.get("R-05-029", "")),
        "unary-invariants": _enumeration(UNARY_INVARIANTS_RE,
                                         reg.body.get("R-05-159", "")),
        "seam-lemmas": _enumeration(SEAM_LEMMAS_RE, reg.body.get("R-05-160", ""), ";"),
        "frozen-absences": sum(1 for b in reg.body.values() if ": Absence (" in b),
        "admission-tests": len(ENUM_MARK_RE.findall(reg.body.get("R-15-010", ""))),
        "tcb-items": _spec_lines(ctx, ". ", TCB_ITEM_RE, until="## 6. "),
        "assurance-tiers": _spec_lines(ctx, "| **Tier", TIER_ROW_RE),
        "build-prereqs": _anchor_span_marks(ctx, "r-06-024"),
        "radio-protocols": _radio_protocols(reg.accept_text.get("R-12-043e", "")),
        "iris-theories": _enumeration(IRIS_THEORIES_RE, reg.body.get("R-13-017", "")),
        # the lane's shape, read off the provisioner's own table rather than parsed
        # out of the file a second time: a second parse of one table is exactly the
        # two-copies defect this group exists to catch, and the table is a tuple of
        # frozen rows an import already resolves
        "provision-facts": len(provision.FACTS),
        "provision-uncommanded": sum(1 for f in provision.FACTS if not f.install),
        "provision-switches": sum(1 for f in provision.FACTS
                                  if f.name.endswith("switch")),
    }


def run(ctx: Context) -> None:
    rep, reg, art = ctx.rep, ctx.reg, ctx.art
    ctx.q = _quantities(ctx)
    ctx.claims = CLAIMS
    rep.line(HEADING)

    def expected(quantity: str, style: str) -> str:
        n = ctx.q[quantity]
        return figures.words(n) if style == "words" else str(n)

    # An owned count of zero is a moved owner, never an empty list, and its claims
    # are skipped rather than resolved: resolved, they would hold every restating
    # count-word to "zero", and one routine `--fix` would write that corruption
    # into three documents and leave the next run green.
    dead = {q for q in REQUIRED_COUNTS if not ctx.q.get(q)}
    claimed = {quantity for _, quantity, _, _ in CLAIMS}
    missed: list[str] = [
        f"{q}'s owner no longer states its enumeration in a form this rule reads, "
        f"so its claims stand unresolved rather than repaired to zero"
        for q in sorted(dead & claimed)]

    for file, quantity, style, pattern in CLAIMS:
        if quantity in dead:
            continue
        # `figures.words` refuses a count past ninety-nine, and the count is the
        # documents' to grow: a quantity that outgrows its word form is this rule's
        # finding, naming the claim owed a digits spelling, never a stopped run
        try:
            want = expected(quantity, style)
        except ValueError:
            missed.append(f"{quantity} is {ctx.q[quantity]}, which has no word form; "
                          f"the claim in {file} must state it in digits")
            continue
        r = figures.resolve_claim(ctx, file, pattern, want, quantity)
        if r.fixed:
            rep.line(r.fixed)
        if r.finding:
            missed.append(r.finding)
    rep.report("K-24", "asserted count(s) disagreeing with their artifact:", missed,
               f"all {len(CLAIMS)} asserted counts agree")

    # --- the status column is three classes, and every row is in one ----------------
    rep.report("K-25", "crown-jewel row(s) whose status is in no class:",
               [f"row {row.split('|')[1].strip()}: {cj_status(row)}"
                for row in art.cj_rows if not cj_class(row)],
               f"{ctx.q['cj-specs']} rows partition into {ctx.q['cj-authored']} authored, "
               f"{ctx.q['cj-partial']} partial, {ctx.q['cj-unauthored']} not authored")

    # Subject and document scope decide a duplicate, never a coincident current value.
    rep.report("K-26", "unheld restatement(s) of a counted figure:",
               unheld_counts(ctx), "every count in a declared scope is held by a claim")

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

    # The families, in the order stated at the top of this module: a rule reads what an
    # earlier one left on the `Context`, never the other way round.
    tag_plane(ctx)
    owned_figures(ctx)
    cap_format(ctx)
    cap_causes(ctx)
    block_geometry(ctx)
    freeze_delta(ctx)
    core_classes(ctx)
    window, faults = citation_window(ctx)
    # The second consumer, in a later group: the pin rule reads the ported headers'
    # provenance lines out of the same files. Handed on rather than re-read, for the
    # reason `citation_window` states.
    ctx.shared["citation_window"] = window
    model_citations(ctx, window, faults)
    excluded_forms(ctx)
    shipped_configurations(ctx)
    vectorless_configurations(ctx)
    aperture_placements(ctx)
    excluded_by_name_keys(ctx)
    device_region_executability(ctx)
    rep.line()
