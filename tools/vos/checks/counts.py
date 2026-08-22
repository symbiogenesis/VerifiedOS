# SPDX-License-Identifier: Apache-2.0
"""counts: every figure any document asserts, against the artifact it derives from.

"1290 requirements", "twenty-two crown-jewel specifications", "sixteen enumerated
absences" are all restatements of something a table already holds. Each quantity is
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
"""

import re
from typing import TYPE_CHECKING

from vos import coreclass, figures, geometry
from vos import corpus as corpus_mod
from vos.register import REGISTER, REQ_TOKEN_RE, cj_class, cj_status

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

SPEC = "docs/spec.md"
ALTERNATIVES = "docs/architectural-alternatives.md"
ESTIMATES = "docs/performance-estimates.md"

# The two register fields every tag-plane figure below is arithmetic over. Read from
# the entries that fix them rather than declared here, so this module states no width
# of its own: a granule is R-15-203's and a codeword payload is R-15-181a's.
GRANULE_RE = re.compile(r"one validity tag per \*\*(\d+)-bit\*\* granule")
PAYLOAD_RE = re.compile(r"data payload is (\d+) bits")

# file, key, and the pattern capturing the stated figure alone. Each pattern holds
# exactly one site in its own file, which a claim owes because a repair rewrites every
# site the pattern matches.
TAG_PLANE: list[tuple[str, str, str]] = [
    (REGISTER, "mb-per-gb", r"(?<=granule is )[\d.]+(?= MB per GB of data)"),
    (REGISTER, "plane-exact", r"(?<=native tags cost )[\d.]+(?=% plus that code)"),
    (REGISTER, "plane-short", r"(?<=tag-plane density doubles to )[\d.]+(?=% of the array)"),
    (SPEC, "mb-per-gb", r"(?<=granule is )[\d.]+(?= MB per GB of data)"),
    (SPEC, "plane-exact", r"(?<=native tags cost )[\d.]+(?=% plus that code)"),
    (SPEC, "plane-short", r"(?<=the tag plane doubles to )[\d.]+(?=% of the array)"),
    (ALTERNATIVES, "mb-per-gb", r"(?<=granule is )[\d.]+(?= MB per GB of data)"),
    (ESTIMATES, "plane-short", r"(?<=and )[\d.]+(?=% in array area)"),
    (ESTIMATES, "plane-short", r"(?<=the plane is )[\d.]+(?=% of the array rather than)"),
    (ESTIMATES, "half-short", r"(?<=% of the array rather than )[\d.]+(?=% and its DECTED)"),
    (ESTIMATES, "payload", r"(?<=codeword is unchanged at )\d+(?= data bits)"),
    (ESTIMATES, "tags-per-codeword", r"(?<=data bits carrying )\w+(?= tag bits)"),
]

# The DECTED-inclusive bands beside the bare figures. These are judgment: the code over
# the plane is "about one check bit per codeword" and the register fixes no width for
# it, so the band is nobody's arithmetic and is never rewritten. What is machine-held is
# that it stands above the plane it includes, which is the one thing a band that had
# drifted off its own figure would stop doing.
BAND_MB_RE = re.compile(r"about (\d+)–(\d+) MB of SRAM per GB")
BAND_PCT_RE = re.compile(r"some ([\d.]+)–([\d.]+)% of the bulk array")
SIDECAR_RE = re.compile(r"consume (\d+)–\d+% of a \d+–(\d+) GB first class")
TIER_RE = re.compile(r"a (\d+) GB bulk tier")


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


def _tag_plane(ctx: Context) -> None:
    """K-54: every stated tag-plane figure, against the two fields it is arithmetic over.

    The granule is one bit of validity per so many bits of data, so the plane is
    `100/granule` percent of the array it covers and `1000/granule` megabytes per
    gigabyte of it, and the ECC codeword carries `payload/granule` tag bits. Three
    quantities, two register fields, and four documents that between them state the
    result eleven times over.

    A reading that has moved is the one finding this rule cannot repair: with no
    granule there is no arithmetic to compare against, so it reports and stops rather
    than passing over an empty claim table, which is the vacuity the floors group
    exists to refuse and would not see here, the table being a literal.
    """
    rep, reg = ctx.rep, ctx.reg

    granule = GRANULE_RE.search(reg.body.get("R-15-203", ""))
    payload = PAYLOAD_RE.search(reg.body.get("R-15-181a", ""))
    if not granule or not payload:
        rep.report("K-54", "tag-plane field(s) the register no longer fixes:", [
            None if granule else
            "R-15-203 no longer states the granule width in a form this rule reads",
            None if payload else
            "R-15-181a no longer states the codeword's data payload in a form this "
            "rule reads",
        ])
        ctx.shared["tag_plane"] = 0
        return

    g, p = int(granule.group(1)), int(payload.group(1))
    expected = {
        "plane-exact": figures.quantize(100 / g, 4),
        "plane-short": figures.quantize(100 / g, 2),
        # the halved comparator: the plane a granule twice this wide would have given,
        # which the estimate row states beside the one this profile took
        "half-short": figures.quantize(100 / (2 * g), 2),
        "mb-per-gb": figures.quantize(1000 / g, 1),
        "payload": str(p),
        "tags-per-codeword": figures.words(p // g),
    }

    missed: list[str] = []
    for file, key, pattern in TAG_PLANE:
        r = figures.resolve_claim(ctx, file, pattern, expected[key],
                                  f"the tag plane's {key} figure")
        if r.fixed:
            rep.line(r.fixed)
        if r.finding:
            missed.append(r.finding)

    # The bands are read from the entry that states them and compared by inequality
    # alone. A band that includes the plane's own code must exceed the bare plane; the
    # sidecar's low end is the one figure in the sentence that is a product of the
    # others and so has an answer.
    accept = reg.accept_text.get("R-15-247a", "")
    band_mb, band_pct = BAND_MB_RE.search(accept), BAND_PCT_RE.search(accept)
    sidecar, tier = SIDECAR_RE.search(accept), TIER_RE.search(accept)
    if not (band_mb and band_pct and sidecar and tier):
        missed.append("R-15-247a no longer states the DECTED-inclusive bands in a form "
                      "this rule reads")
    else:
        if float(band_mb.group(1)) <= 1000 / g:
            missed.append(f"R-15-247a's DECTED band opens at {band_mb.group(1)} MB per "
                          f"GB, at or below the bare plane's {expected['mb-per-gb']}")
        if float(band_pct.group(1)) <= 100 / g:
            missed.append(f"R-15-247a's DECTED band opens at {band_pct.group(1)}% of the "
                          f"array, at or below the bare plane's {expected['plane-exact']}")
        # low band MB per GB over the whole tier, against the largest first class
        want = round(float(band_mb.group(1)) * int(tier.group(1))
                     / (int(sidecar.group(2)) * 1000) * 100)
        if int(sidecar.group(1)) != want:
            missed.append(f"R-15-247a says a sidecar consumes {sidecar.group(1)}% of the "
                          f"largest first class at the band's low end, the figures "
                          f"beside it give {want}%")

    ctx.shared["tag_plane"] = len(TAG_PLANE)
    rep.report("K-54", "tag-plane figure(s) disagreeing with the fields they derive from:",
               missed,
               f"all {len(TAG_PLANE)} tag-plane figures follow the {g}-bit granule "
               f"R-15-203 fixes and the {p}-bit payload R-15-181a fixes")


def _block_geometry(ctx: Context) -> None:
    """K-57: the welded block size, in every artifact that writes it.

    Four instructions share one parameter, and it is written six times: twice in Sail,
    twice in the model's configuration dialect, once as a literal in the model's own
    harness, and once as the candidate set of the document that constrains it. The
    assertions inside the model hold the first pair together at run time; nothing held
    the harness's literal or the document's set against them, and a document stating a
    figure nothing checks is worse than one that states none, because it reads as
    checked.

    The candidate set is recomputed rather than trusted, from the granule the model
    declares and the ceiling an integer destination imposes, so a candidate row edited
    in the document without its arithmetic is a finding. It is reported and never
    repaired: four of the six sites are under a `-text` tree, where a rewrite risks the
    line-ending sweep the tools' `newline=""` convention exists to prevent, and the
    seventh thing this rule could touch, which value inside the set is taken, is
    R-15-014a's second act rather than arithmetic.
    """
    rep, reg = ctx.rep, ctx.reg
    geo = geometry.read(ctx.root)
    payload = PAYLOAD_RE.search(reg.body.get("R-15-181a", ""))

    if geo.granule_exp is None or payload is None:
        rep.report("K-57", "block-geometry reading(s) that have moved:", [
            None if geo.granule_exp is not None else
            "the model no longer declares log2_cap_size in a form this rule reads, so "
            "there is no granule to derive the block against",
            None if payload is not None else
            "R-15-181a no longer states the codeword's data payload, so there is no "
            "floor to derive the block against",
        ])
        ctx.shared["block_candidates"] = 0
        return

    findings: list[str] = []
    written = {site: exp for site, exp in geo.sites.items() if exp is not None}
    findings += [f"{site} no longer writes the block size in a form this rule reads"
                 for site, exp in geo.sites.items() if exp is None]

    if len(set(written.values())) > 1:
        findings += [f"{site} writes a block of {1 << exp} bytes"
                     for site, exp in sorted(written.items())]

    # The two derivable constraints that bind, C5 and C3 of the document. The floor is
    # one ECC codeword, no sub-codeword write existing at the array; the ceiling is the
    # widest tag group an integer destination can carry back. The rest of the derivable
    # rows are implied by these two over a power-of-two space, which is what the
    # document says and what this arithmetic is the other statement of.
    granule = 1 << geo.granule_exp
    codeword = int(payload.group(1)) // 8
    ceiling = granule * 64                       # caps_per_block at most XLEN
    candidates = [b for e in range(13) if codeword <= (b := 1 << e) <= ceiling]

    if geo.ceiling != ceiling:
        findings.append(f"{geometry.DOCUMENT} states a ceiling of {geo.ceiling} bytes, "
                        f"the {granule}-byte granule and an integer destination give "
                        f"{ceiling}")
    if geo.declared and geo.declared != candidates:
        findings.append(f"{geometry.DOCUMENT} declares candidates {geo.declared}, the "
                        f"constraints it states compound to {candidates}")
    elif not geo.declared:
        findings.append(f"{geometry.DOCUMENT} states no candidate set this rule reads")

    for site, exp in written.items():
        if (1 << exp) not in candidates:
            findings.append(f"{site} writes a block of {1 << exp} bytes, which is "
                            "outside the candidate set the constraints admit")

    ctx.shared["block_candidates"] = len(candidates)
    rep.report("K-57", "welded block-size site(s) that disagree:", findings,
               f"the welded block size is {1 << next(iter(written.values()), 0)} bytes "
               f"in all {len(geo.sites)} sites that write it, inside a candidate set of "
               f"{len(candidates)}")


def _core_classes(ctx: Context) -> None:
    """K-60: the core-class table, in every artifact that writes it.

    One Sail model is parameterized by core class (R-15-005), and the table saying what
    each class *is* is written four times: once as the specification's core-class table,
    once as the profile's, once as the register's one-sentence enumeration, and once as
    the class table the model is actually composed from. The first three are prose in
    three different idioms, which is what makes this the shape where an edit to one
    renders correctly in all four; the fourth is the only one the machine reads, so a
    document that has drifted from it describes a machine nobody runs.

    Counts are held on a narrower ground and it is worth stating, because R-15-113 calls
    them composition parameters rather than architecture. A machine may carry any
    roster. This repository composes exactly one, so the reference instantiation the
    specification states is a claim about *that* roster, and a count in prose that no
    roster realizes is a figure nobody renders wrong. Only the specification states
    counts, so only it is held against the roster.

    Reported and never repaired, for K-57's two reasons: the composition is under a
    `-text` tree where a rewrite risks the line-ending sweep the tools' `newline=""`
    convention exists to prevent, and which geometry a class takes is R-15-108's
    exploration rather than arithmetic.
    """
    rep, reg = ctx.rep, ctx.reg
    cc = coreclass.read(ctx.root, reg.body.get("R-15-113", ""))

    findings = [f"{site} no longer writes the core-class table in a form this rule reads"
                for site, table in sorted(cc.stated.items()) if table is None]
    if cc.declared is None:
        findings.append(f"{coreclass.CONFIG} no longer declares a per-class vector "
                        "geometry this rule reads")
    if cc.roster is None:
        findings.append(f"{coreclass.CONFIG} no longer declares a core roster this "
                        "rule reads")

    # Every readable prose site against the one table the machine is built from. The
    # composition is the reference and not merely a fourth opinion: it is what the
    # emulator, the generated devicetree, and the validator all read.
    if cc.declared is not None:
        for site, table in sorted(cc.stated.items()):
            if table is None:
                continue
            findings += [
                f"{site} states {name}-class at "
                + (f"VLEN={table[name]}" if table[name] else "no vector geometry")
                + ", the composition declares "
                + (f"VLEN={cc.declared[name]}" if cc.declared[name] else "none")
                for name in coreclass.CLASSES if table[name] != cc.declared[name]]

    if cc.roster is not None:
        if not cc.counts:
            findings.append("the specification's core-class table states no counts this "
                            "rule reads, so nothing holds the roster to a stated one")
        findings += [f"the specification states {n} {name}-class core(s) and the "
                     f"composed roster carries {cc.roster[name]}"
                     for name, n in sorted(cc.counts.items()) if cc.roster[name] != n]

    ctx.shared["core_class_sites"] = sum(
        1 for table in cc.stated.values() if table is not None) + (
        (cc.declared is not None) + (cc.roster is not None))
    rep.report("K-60", "core-class table site(s) that disagree:", findings,
               f"the {len(coreclass.CLASSES)} core classes carry one vector geometry "
               f"across all {len(cc.stated) + 1} sites that write it, and the "
               f"{len(cc.counts)} stated counts are the composed roster's")


def _model_citations(ctx: Context) -> None:
    """K-63: every requirement the model cites, in the files this tool can see.

    The curated model argues from the register constantly: a Sail file states why a
    field is the width it is, why a class declares nothing where another declares
    something, why an instruction traps where the base ISA would execute. Every one of
    those arguments names a requirement id, and until now not one of them was checked,
    because `model/` is excluded from the checker's corpus wholesale and K-11 reads
    only tracked documents. A mistyped or invented id in a model comment therefore
    rendered as a citation, survived review, and pointed at nothing.

    The reach is the `MODEL_FACTS` carve-out and not the whole tree, which is a real
    limit rather than a chosen scope: those are the files the selftest's sandbox copies
    instead of standing up empty, so they are the only model paths a rule may read at
    all. Widening it means widening that list, which is the decision the list exists to
    make visible.

    Ids are permanent and a retired requirement is struck rather than removed
    (CLAUDE.md), so what this catches is not renumbering. It is the typo, the id
    invented while writing prose about a requirement that turned out to be numbered
    something else, and the citation carried across from an upstream that had its own.
    """
    rep, reg = ctx.rep, ctx.reg
    findings: list[str] = []
    cited = 0
    for rel in corpus_mod.MODEL_FACTS:
        path = ctx.root / rel
        if not path.is_file():
            continue
        for ident in sorted(set(REQ_TOKEN_RE.findall(path.read_text(encoding="utf-8")))):
            cited += 1
            if ident not in reg.id_set:
                findings.append(f"{rel} cites {ident}, which the register does not "
                                "declare")
    ctx.shared["model_citations"] = cited
    rep.report("K-63", "model citation(s) naming no requirement:", findings,
               f"all {cited} requirement citations in the {len(corpus_mod.MODEL_FACTS)} "
               "model files this tool reads resolve")


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

    _tag_plane(ctx)
    _block_geometry(ctx)
    _core_classes(ctx)
    _model_citations(ctx)
    rep.line()
