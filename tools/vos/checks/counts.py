# SPDX-License-Identifier: Apache-2.0
"""counts: every figure any document asserts, against the artifact it derives from.

"N requirements", "N crown-jewel specifications", "N enumerated absences" are all
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

import json
import re
from typing import TYPE_CHECKING

from vos import corpus as corpus_mod
from vos import differential, figures
from vos.checks.counts_capformat import cap_format
from vos.checks.counts_configs import shipped_configurations, vectorless_configurations
from vos.checks.counts_coreclass import core_classes
from vos.checks.counts_delta import freeze_delta
from vos.checks.counts_fields import GRANULE_RE, PAYLOAD_RE
from vos.checks.counts_geometry import block_geometry
from vos.checks.counts_model import citation_window, excluded_forms, model_citations
from vos.checks.counts_owned import owned_figures
from vos.checks.counts_tagplane import TAG_PLANE, tag_plane
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
TAL = "docs/typed-assembly-language.md"
TOOLS_README = "tools/README.md"

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

    # the type-obligation menu: owned by R-05-029's enumeration, its count restated
    # across both documents and the assembly language's own account
    (REGISTER, "type-obligations", "words", r"(?<=partitions the canonical )[\w-]+(?= rather)"),
    (REGISTER, "type-obligations", "words", r"(?<=a flat list of )[\w-]+(?= obligations)"),
    (REGISTER, "type-obligations", "words", r"(?<=R-05-029's )[\w-]+(?= type-level obligations)"),
    (REGISTER, "type-obligations", "words", r"(?<=\*\*the )[\w-]+(?= type-level obligations of R-05-029)"),
    (SPEC, "type-obligations", "words", r"(?<=These )[\w-]+(?= type-level obligations)"),
    (SPEC, "type-obligations", "words", r"(?<=The )[\w-]+(?= obligations above)"),
    (SPEC, "type-obligations", "words", r"(?<=a flat list of )[\w-]+(?= obligations)"),
    (SPEC, "type-obligations", "words", r"(?<=subset of the )[\w-]+(?= type-level obligations)"),
    (SPEC, "type-obligations", "words", r"(?<=\*\*The )[\w-]+(?= type-level obligations of §5)"),
    (SPEC, "type-obligations", "words", r"(?<=§5's )[\w-]+(?= type-level obligations)"),
    (REGISTER, "type-obligations", "words", r"(?<=admission check that is not one of the )[\w-]+"),
    (SPEC, "type-obligations", "words", r"(?<=admission check and not one of the )[\w-]+"),
    (SPEC, "type-obligations", "words", r"(?<=WCET\) are not )[\w-]+(?= mechanisms)"),
    (TAL, "type-obligations", "words", r"(?<=exactly these )[\w-]+(?= obligations)"),
    (TAL, "type-obligations", "words", r"(?<=all )[\w-]+(?=, canonically enumerated)"),
    (TAL, "type-obligations", "words", r"(?<=partition the )[\w-]+(?= menu rows)"),

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
    (SPEC, "admission-tests", "words", r"(?<=satisfies all )[\w-]+(?=: \(1\))"),
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

    # the required-but-untrusted build artifacts, owned by the spec line's own markers
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

    # the tools' own value window, owned by the tuple that declares it. The artifact is
    # a constant rather than a table, which changes nothing about the discipline: the
    # size of that window was hand-copied into three sentences and drifted from the
    # tuple the day a file joined it, so the one sentence left states it derived.
    (TOOLS_README, "model-facts", "words",
     r"(?<=`MODEL_FACTS` names )[\w-]+(?= files by path)"),

    # the differential corpus's own size, owned by the manifest. K-50 holds the
    # membership in both directions and says nothing about how many members there
    # are, so a program added to the manifest and described in the document left
    # this sentence behind with every rule green; and the counted-noun sweep does
    # not reach it either, `programs` not being one of the nouns it proposes.
    ("docs/differential-corpus.md", "corpus-members", "words",
     r"[\w-]+(?= purecap programs)"),
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
    r"CSR|letter-suffixed|such entries|obligation|menu row", re.IGNORECASE)

# The trailing lookahead keeps CRLF out of the match: an anchored `\|$` never matches a
# CRLF file, and every row would read as missing.
COVERAGE_ROW_RE = r"(?m)^\| \*\*§(\d+) [^|]*\| \*\*extracted\*\* \| \*\*(\d+)\*\* \|(?=\r?$)"

# The enumerations the co-statement survey found restated as counts across K-61
# pairs, each read from the one entry that owns it rather than declared here: the
# count moves with the list, and every count-word restating it is a claim above.
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


# Every quantity below is a reading of one owner's phrasing, and a reading that
# returns zero means the phrasing moved, never that the list emptied: none of these
# enumerations can be empty while its entry exists. `run` therefore refuses to
# resolve a zero-valued owned count's claims, because resolving them would hold, and
# under `--fix` rewrite, every restatement to "zero", a confident corruption in
# place of the loud stop the K-54 and K-69 owner guards give.
OWNED_COUNTS = frozenset({
    "type-obligations", "unary-invariants", "seam-lemmas", "frozen-absences",
    "admission-tests", "tcb-items", "assurance-tiers", "build-prereqs",
    "radio-protocols", "iris-theories",
    # The one member here whose owner is a file rather than an entry, and it is a
    # member for exactly the same reason: a manifest that will not parse yields no
    # members, which is a reading that has moved and never a corpus that has
    # emptied, and resolving its claim would rewrite the document's own sentence to
    # "zero" under one routine `--fix`.
    "corpus-members",
})

_PARENTHETICAL_RE = re.compile(r"\([^)]*\)")


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


def _anchor_line_marks(ctx: Context, ident: str) -> int:
    """The enumeration markers on the one spec line declaring a bookmark."""
    doc = ctx.corpus.get(SPEC)
    if doc is None:
        return 0
    needle = f'<a id="{ident}">'
    for i, line in enumerate(doc.lines):
        if needle in line and not doc.fenced[i]:
            return len(ENUM_MARK_RE.findall(line))
    return 0


def _corpus_members(ctx: Context) -> int:
    """How many programs the differential corpus's manifest lists, zero where it
    will not parse.

    Guarded rather than allowed to raise, because this group runs well before the
    differential group that owns the manifest: an unreadable one there is that
    group's finding, worded once, and here it must not take the whole run down
    before any rule has decided anything. Zero is the moved-reading answer
    `OWNED_COUNTS` refuses to resolve a claim against.
    """
    try:
        return len(differential.load(ctx.root).members)
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return 0


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
        "absences": len(art.absence_ids),
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
        "build-prereqs": _anchor_line_marks(ctx, "r-06-024"),
        "radio-protocols": _radio_protocols(reg.accept_text.get("R-12-043e", "")),
        "iris-theories": _enumeration(IRIS_THEORIES_RE, reg.body.get("R-13-017", "")),
        "corpus-members": _corpus_members(ctx),
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
    dead = {q for q in OWNED_COUNTS if not ctx.q.get(q)}
    missed: list[str] = [
        f"{q}'s owner no longer states its enumeration in a form this rule reads, "
        f"so its claims stand unresolved rather than repaired to zero"
        for q in sorted(dead)]

    claim_spans: dict[str, list[re.Match[str]]] = {}
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

    # The families, in the order stated at the top of this module: a rule reads what an
    # earlier one left on the `Context`, never the other way round.
    tag_plane(ctx)
    owned_figures(ctx)
    cap_format(ctx)
    block_geometry(ctx)
    freeze_delta(ctx)
    core_classes(ctx)
    window, faults = citation_window(ctx)
    # A third consumer, in a later group: the pin rule reads the ported headers'
    # provenance lines out of the same files. Handed on rather than re-read, for the
    # reason `citation_window` states about the second one.
    ctx.shared["citation_window"] = window
    model_citations(ctx, window, faults)
    excluded_forms(ctx, window)
    shipped_configurations(ctx)
    vectorless_configurations(ctx)
    rep.line()
