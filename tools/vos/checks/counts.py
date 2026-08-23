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
"""

import re
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from vos import config, coreclass, decode, figures, geometry
from vos import corpus as corpus_mod
from vos.register import ISA_PROFILE, REGISTER, REQ_TOKEN_RE, cj_class, cj_status

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

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

ALTERNATIVES = "docs/architectural-alternatives.md"
ESTIMATES = "docs/performance-estimates.md"

# The two register fields every tag-plane figure below is arithmetic over. Read from
# the entries that fix them rather than declared here, so this module states no width
# of its own: a granule is R-15-203's and a codeword payload is R-15-181a's.
GRANULE_RE = re.compile(r"one validity tag per \*\*(\d+)-bit\*\* granule")
PAYLOAD_RE = re.compile(r"data payload is (\d+) bits")

# R-15-007q's own statement of the welded block's ceiling. The bound is the width of
# the register the group comes back in, so it is the entry's to state and this rule's
# to recompute: of every site that writes a figure about this parameter, the entry is
# the only normative one, and the only one an edit can move without the model or a
# composition rendering wrong.
BLOCK_CEILING_RE = re.compile(r"the block at most \*\*(\d+) bytes\*\*")

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
    (REGISTER, "plane-short", r"(?<=tag plane's ~)[\d.]+(?=% share of the array)"),
    (SPEC, "plane-short", r"(?<=tag plane's ~)[\d.]+(?=% share of the array)"),
    (ALTERNATIVES, "mb-per-gb", r"(?<=granule is )[\d.]+(?= MB per GB of data)"),
    (ESTIMATES, "plane-short", r"(?<=and )[\d.]+(?=% in array area)"),
    (ESTIMATES, "plane-short", r"(?<=the plane is )[\d.]+(?=% of the array rather than)"),
    (ESTIMATES, "half-short", r"(?<=% of the array rather than )[\d.]+(?=% and its DECTED)"),
    (ESTIMATES, "payload", r"(?<=codeword is unchanged at )\d+(?= data bits)"),
    # [\w-]+ and not \w+: the expected value is figures.words(payload // granule), and
    # every word form from twenty-one up that is not a round ten is hyphenated, so a
    # bare \w+ would repair to a spelling its own pattern can no longer find.
    (ESTIMATES, "tags-per-codeword", r"(?<=data bits carrying )[\w-]+(?= tag bits)"),
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

# The enumerations the co-statement survey found restated as counts across K-61
# pairs, each read from the one entry that owns it rather than declared here: the
# count moves with the list, and every count-word restating it is a claim below.
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

# K-69: a figure one entry fixes and other sites restate verbatim, with no arithmetic
# between them: the K-54 shape without the ratio. Each row is the figure's key, the
# owning entry, the pattern reading it from that entry's own lines, and the sites the
# repair rewrites from the owner. Each site pattern captures the figure alone and
# holds every occurrence its file carries.
OWNED: list[tuple[str, str, str, list[tuple[str, str]]]] = [
    ("kernel-line-budget", "R-07-001", r"targeting ≤(\d+k) lines", [
        # anchored on the microkernel's own sentence, not the stock magnitude
        # idiom: "on the order of Nk LoC" is a spelling any entry may use, and a
        # repair rewrites every match its pattern holds
        (REGISTER, r"(?<=microkernel is on the order of )\d+k(?= LoC of verified C)"),
        (SPEC, r"(?<=\(~)\d+k(?= LoC verified C\))"),
        (SPEC, r"(?<=target ≤)\d+k(?= lines)"),
        # the prose writes a thin space (U+2009) between the sign and the figure
        (SPEC, r"(?<=below the ≤\u2009)\d+k(?=-line target)"),
    ]),
    ("range-decoder-share", "R-15-067g", r"measured at roughly (\d+)% of decode time", [
        (SPEC, r"(?<=measured at roughly )\d+(?=% of decode time)"),
    ]),
    ("reference-slot-width", "R-15-036a", r"seven (\d+)-bit slots", [
        (SPEC, r"(?<=At the reference )\d+(?=-bit slot)"),
        (SPEC, r"(?<=collects one )\d+(?=-bit slot rather than four bytes)"),
        (REGISTER, r"(?<=collects one )\d+(?=-bit slot rather than four bytes)"),
    ]),
    ("rvc-break-even", "R-15-036k", r"fails below \*p\* = ([\d.]+)", [
        (SPEC, r"(?<=reached at \*p\* = \*\*)[\d.]+(?=\*\*)"),
    ]),
]

# The one owned figure that is a range, held in both dash spellings: the documents
# write 33-43 in an entry's own line and 33–43 in running prose, both derived from
# the owner's capture below, so neither spelling is normalized away.
RANGE_OWNER = ("R-15-007e", r"the (\d+)-(\d+)% no-C penalty")
RANGE_SITES: list[tuple[str, str, str]] = [
    (REGISTER, r"(?<=the )\d+-\d+(?=% no-C penalty)", "{lo}-{hi}"),
    (SPEC, r"(?<=an accepted )\d+–\d+(?=% code-size penalty)", "{lo}–{hi}"),
    (SPEC, r"(?<=the former )\d+-\d+(?=% code-size penalty)", "{lo}-{hi}"),
]

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
        # The spans are discarded where the CLAIMS loop keeps them, and that is an
        # invariant rather than an oversight: a kept span exists to exempt its site
        # from K-26, which proposes only the distinctive forms of the counted
        # quantities, and no tag-plane figure is ever one of those, each being a
        # decimal ratio, a payload width no quantity counts, or a word form below
        # eleven. A tag-plane site therefore never needs a span to be exempted.
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

    The ceiling has a ground as well as a value, and R-15-007q states both: the group
    comes back in one integer register, so the bound is that register's width times the
    granule. Holding the entry's number against the same arithmetic is what keeps the
    derivable half of the constraint from having its only normative statement be one a
    later edit could move on its own. The value is the entry's and the arithmetic is
    here, and neither rewrites the other.
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

    stated = BLOCK_CEILING_RE.search(reg.accept_text.get("R-15-007q", ""))
    if stated is None:
        findings.append("R-15-007q no longer states the welded block's ceiling in a "
                        "form this rule reads, so the bound the destination register "
                        "sets has no normative statement left")
    elif int(stated.group(1)) != ceiling:
        findings.append(f"R-15-007q states a ceiling of {stated.group(1)} bytes, the "
                        f"{granule}-byte granule and an integer destination give "
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
               f"{len(candidates)} under the {ceiling}-byte ceiling R-15-007q states")


def _owned_figures(ctx: Context) -> None:
    """K-69: every figure one entry fixes, restated identically wherever it is stated.

    The K-54 shape without the arithmetic: a budget, a measurement, or a frozen width
    is one entry's statement, other sites repeat it verbatim, and an edit to the owner
    left the repeats standing in pairs whose other side states no figure at all, which
    is the drift the co-statement survey found K-61 structurally cannot see. Each
    figure is read from the entry that fixes it and every registered site is held to
    it; under `--fix` the sites are rewritten from the owner, never the other way,
    because the owner is where the decision lives.

    The one range among them is held in both dash spellings on purpose: an entry's own
    line writes 33-43 and running prose writes 33–43, both derived from the owner's
    captures, so the hold does not flatten a typographic convention.
    """
    rep, reg = ctx.rep, ctx.reg
    missed: list[str] = []
    held = 0

    def owner_text(ident: str) -> str:
        return reg.body.get(ident, "") + " " + reg.accept_text.get(ident, "")

    for key, ident, owner_pattern, sites in OWNED:
        m = re.search(owner_pattern, owner_text(ident))
        if not m:
            missed.append(f"{ident} no longer states the {key} figure in a form this "
                          "rule reads")
            continue
        for file, pattern in sites:
            held += 1
            r = figures.resolve_claim(ctx, file, pattern, m.group(1),
                                      f"the {key} figure")
            if r.fixed:
                rep.line(r.fixed)
            if r.finding:
                missed.append(r.finding)

    range_id, range_pattern = RANGE_OWNER
    m = re.search(range_pattern, owner_text(range_id))
    if not m:
        missed.append(f"{range_id} no longer states the no-C code-size range in a "
                      "form this rule reads")
    else:
        lo, hi = m.group(1), m.group(2)
        for file, pattern, shape in RANGE_SITES:
            held += 1
            r = figures.resolve_claim(ctx, file, pattern,
                                      shape.format(lo=lo, hi=hi),
                                      "the no-C code-size range")
            if r.fixed:
                rep.line(r.fixed)
            if r.finding:
                missed.append(r.finding)

    rep.report("K-69", "owned figure(s) restated differently than their entry fixes:",
               missed,
               f"all {len(OWNED) + 1} owned figures are restated identically at "
               f"their {held} registered sites")


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


def _freeze_delta(ctx: Context) -> None:
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

    # The free-prose tokens beyond the four table sites: a VLEN=n anywhere in the
    # corpus is a claim about some composed class's datapath, and the ones outside
    # the tables were held by nothing, so a re-picked geometry (R-15-108 names each
    # class's VLEN as a searched parameter) moved the tables and left the prose
    # citing a machine no longer composed. Membership is the strongest form the
    # token admits: a bare VLEN=n names no class, so a swap of two classes'
    # geometries stays in-set and is the residue the registry row declares.
    tokens = 0
    if cc.declared is not None:
        geometries = {v for v in cc.declared.values() if v}
        for doc in ctx.corpus.docs:
            for m in coreclass.VLEN_RE.finditer(doc.raw):
                if doc.is_fenced(m.start()):
                    continue
                tokens += 1
                if int(m.group(1)) not in geometries:
                    findings.append(
                        f"{doc.name}:{doc.at(m.start())} states VLEN={m.group(1)}, "
                        f"a geometry no composed class carries")

    ctx.shared["core_class_sites"] = sum(
        1 for table in cc.stated.values() if table is not None) + (
        (cc.declared is not None) + (cc.roster is not None))
    ctx.shared["vlen_tokens"] = tokens
    rep.report("K-60", "core-class table site(s) that disagree:", findings,
               f"the {len(coreclass.CLASSES)} core classes carry one vector geometry "
               f"across all {len(cc.stated) + 1} sites that write it, the "
               f"{len(cc.counts)} stated counts are the composed roster's, and every "
               f"one of the corpus's {tokens} VLEN tokens is a composed geometry")


def _citation_window(ctx: Context) -> tuple[list[tuple[str, str]], list[str]]:
    """The model-citation window, read once for the two rules that scan it.

    K-63 reads every file the window admits and K-66 re-read the Sail subset of the
    same files moments later, so the one read lives here and both consumers take
    `(rel, text)` pairs. The reads go through a thread pool because a file read
    releases the interpreter lock, so the on-access virus scan the window's first
    read pays overlaps across files instead of serializing; the pool's `map` returns
    in submission order, so the pairs come back in the sorted order they were asked
    in and the run's output does not depend on which read finished first.

    A file the index lists and the working tree no longer holds is dropped silently,
    as the corpus drops a deleted document; a file that is there and cannot be read
    is a finding worded once, under K-63, because pricing one unreadable file under
    both rules would report one defect twice.
    """
    rels = [rel for rel in sorted(ctx.corpus.tracked)
            if corpus_mod.is_model_citation_path(rel)]

    def read(rel: str) -> tuple[str, str] | str | None:
        path = ctx.root / rel
        if not path.is_file():
            return None
        try:
            return rel, path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return f"{rel}: unreadable, so its citations cannot be decided ({exc})"

    pairs: list[tuple[str, str]] = []
    faults: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for got in pool.map(read, rels):
            if isinstance(got, tuple):
                pairs.append(got)
            elif got is not None:
                faults.append(got)
    return pairs, faults


def _model_citations(ctx: Context, window: list[tuple[str, str]],
                     faults: list[str]) -> None:
    """K-63: every requirement the model cites, in the files this tool can see.

    The curated model argues from the register constantly: a Sail file states why a
    field is the width it is, why a class declares nothing where another declares
    something, why an instruction traps where the base ISA would execute. Every one of
    those arguments names a requirement id, and until now not one of them was checked,
    because `model/` is excluded from the checker's corpus wholesale and K-11 reads
    only tracked documents. A mistyped or invented id in a model comment therefore
    rendered as a citation, survived review, and pointed at nothing.

    The reach is by kind and not by name, which is a decision rather than the absence
    of one. `MODEL_FACTS` is the *value* window and stays narrow, because a rule reading
    a number out of the model should name the file it reads. This rule holds a
    construct that occurs wherever the model argues from the register, so its natural
    reach is the tree: pointed at the value window it would see under a quarter of the
    model's citations, which is a rule reporting `ok` about a quarter of its subject.
    The count itself is this rule's own `ok` line and is never written down here.

    Ids are permanent and a retired requirement is struck rather than removed
    (CLAUDE.md), so what this catches is not renumbering. It is the typo, the id
    invented while writing prose about a requirement that turned out to be numbered
    something else, and the citation carried across from an upstream that had its own.
    """
    rep, reg = ctx.rep, ctx.reg
    findings: list[str] = list(faults)
    cited = 0
    files = 0
    for rel, text in window:
        found = REQ_TOKEN_RE.findall(text)
        if found:
            files += 1
        cited += len(found)
        findings += [f"{rel} cites {ident}, which the register does not declare"
                     for ident in sorted(set(found)) if ident not in reg.id_set]
    ctx.shared["model_citations"] = cited
    rep.report("K-63", "model citation(s) naming no requirement:", findings,
               f"all {cited} requirement citations the model makes, across {files} of "
               "its files, name a requirement the register declares")


# A backticked name in an exclusion row's first cell. The cell is prose around them,
# so the backticks are what marks a name the document is spelling exactly rather than
# describing, which is the only part of that cell a machine has any business reading.
EXCLUDED_NAME_RE = re.compile(r"`([^`]+)`")

# The Sail constructor a row names where its subject is a single instruction form,
# written `Sail: `CTOR`` inside the first cell. It is read out before the names are,
# because a constructor is not a mnemonic the profile spells and counting it as one is
# what let it sit in that cell matching nothing and reported as checked.
MARKER_RE = re.compile(r"Sail:\s*`([^`]+)`")


def _excluded_forms(ctx: Context, window: list[tuple[str, str]]) -> None:
    """K-66: no form the profile excludes is still on the model's decode surface.

    The profile's §6 excludes by name and the model implements by clause, and until
    now nothing held the two together. `model.py sweep` does not: it runs the profile
    configuration against upstream `riscv-tests` and counts refusals of *those*
    programs, which is conformance against an external corpus and not a claim that the
    model implements only what the profile admits. Its figure reads the same whether or
    not an excluded form is still decoded, which is how the fault-only-first loads
    (R-15-039b) stayed on the surface after the amendment that excluded them.

    **Both halves of the surface are read, because a form leaves by two doors.** A
    `mapping clause assembly` is the model spelling what it decoded; `dialect.MNEMONICS`
    is the corpus assembler emitting a word for the model to decode. A form deleted from
    one and left in the other is still reachable: an encoder row with no clause lays
    down a word the model refuses, and a clause with no encoder row is surface no corpus
    program can reach and an implementation still carries. So a finding names the half
    it was found in, and the rule is not satisfied by either half alone.

    **The reach is by kind, and here that is not a preference.** `MODEL_FACTS` is the
    *value* window of files named one by one, and **none of the readable spellings is
    in one of them**, so aimed there this rule would have read nothing at all and passed
    green over the whole decode surface: not K-63's quarter of its subject but none of it.
    A decode clause occurs wherever the model defines an instruction, which is most of
    the tree, so the window that fits it is the one that admits by kind.

    **Where a row's subject is a single instruction form the profile names the Sail
    constructor, and that name is tested by membership rather than by matching.** A
    skeleton is a lower bound on what a clause spells, so a mnemonic assembled out of
    three mappings and a dot leaves nothing to match against: the profile writes
    `amocas.q`, the model writes `amo_mnemonic(op) ^ "." ^ width_mnemonic_wide(width)`,
    and the fragment test pairs the one with nothing. A marker is not a spelling and is
    not matched: the constructor is in the set of names the decode surface decodes to
    or it is not, which additionally reaches a form whose clause is shared with its
    neighbours and whose identity is a field value, `AMOCAS` being both.

    **The marker widens the rule and replaces no part of it.** The fragment path runs
    over every row's names exactly as before, marked or not, because a marker cannot
    see a form re-added under another constructor and is worth only the run that
    validated it: one that is stale or misspelled is absent for the same reason a
    deleted form is, and degrading to the fragment path is what keeps that from being a
    silent green. A row naming several forms, or an extension spanning many
    constructors, carries no marker and is out of the membership test's reach rather
    than mis-typed, so an unmarked row is read exactly as it was.

    **What it cannot see is most of the exclusion table, and the honest figure is in
    the `ok` line.** A row is read only where a name it spells matches something the
    machine can spell back: a CSR, a privilege mode, an extension name, and a
    microarchitectural structure are all excluded in prose that no mnemonic test
    decides, and such a row is read and passes. So a green run says *no excluded name
    is spelled by the surface and no marked constructor is decoded by it*, never *every
    exclusion is honoured*. On the model's side the same boundary holds for the
    fragment path: the assembly clauses that build their mnemonic entirely inside a
    mapping leave no literal in the file and are invisible to it, which is the gap a
    marker on such a form closes one row at a time.
    """
    rep = ctx.rep
    findings: list[str] = []
    spellings = decode.read_spellings(window)
    decoded = decode.read_decoded(window)

    names = 0
    markers = 0
    for row in ctx.art.exclusion_rows:
        cells = row.strip().strip("|").split("|")
        ground = ", ".join(sorted(set(REQ_TOKEN_RE.findall(cells[-1])))) or "no requirement"
        for ctor in MARKER_RE.findall(cells[0]):
            markers += 1
            findings += [
                f"{ISA_PROFILE} §6 excludes `{ctor}` on {ground}, and "
                f"{d.file}:{d.line} still decodes it, in {d.site}"
                for d in decoded if d.ctor == ctor]
        for name in EXCLUDED_NAME_RE.findall(MARKER_RE.sub("", cells[0])):
            names += 1
            findings += [
                f"{ISA_PROFILE} §6 excludes `{name}` on {ground}, and "
                f"{s.file}:{s.line} still spells it, as {s.ctor}"
                for s in spellings if decode.spells(s.skeleton, name)]
            findings += [
                f"{ISA_PROFILE} §6 excludes `{name}` on {ground}, and the corpus "
                f"assembler still encodes `{mnemonic}`"
                for mnemonic in decode.encoder_rows(name)]

    ctx.shared["exclusion_names"] = names
    ctx.shared["exclusion_markers"] = markers
    ctx.shared["decode_spellings"] = len(spellings)
    ctx.shared["decoded_names"] = len(decoded)
    ctx.shared["encoder_rows"] = len(decode.dialect.MNEMONICS)
    rep.report("K-66", "excluded form(s) still on the decode surface:", findings,
               f"none of the {names} names the profile's {len(ctx.art.exclusion_rows)} "
               f"exclusion rows spell is spelled by the {len(spellings)} readable "
               f"assembly clauses or carried by the "
               f"{len(decode.dialect.MNEMONICS)} encoder rows, and none of the "
               f"{markers} Sail constructors they mark is among the {len(decoded)} "
               f"names the decode surface decodes to")


# The configurations this tree ships, in the order the second is read against the
# first, and the keys the second is *allowed* to differ in.
#
# Both are enumerations rather than patterns on purpose. A third configuration is a
# line here, which is the point at which somebody decides what it is a configuration
# *of*; a third divergent key is the point at which somebody decides whether the second
# file still describes the same machine or has quietly become another one.
SHIPPED_CONFIGS = ("model/config/verifiedos.json", "model/config/verifiedos-v.json")

CONFIG_DIVERGENCE = ("platform.hartid", "extensions.V.vlen_exp")


def _shipped_configurations(ctx: Context) -> None:
    """K-65: the second shipped configuration is a configuration and not a fork.

    There is exactly one Sail model, parameterized by core class, and a V-class
    emulator is that model handed a different configuration rather than a second model
    (R-15-005, M0.8b). What makes the claim true is that the two files differ in the two
    keys naming which core of the one composed roster the emulator is, and in nothing
    else: the composed hart, and the vector geometry that hart's class declares.

    Nothing else holds them together. The model's own validator refuses a configuration
    whose roster puts the composed hart on a class whose declared geometry is not the
    one the run realizes, but it sees one file at a time and only when a run happens
    (postlude/validate_config.sail); `model.py config-keys` compares a configuration
    against the *generated* one and answers about keys rather than values. So the second
    file is a five-hundred-line near-copy of the first with no instrument over the
    copying, which is the two-copies-of-one-fact defect this checker exists to catch,
    sitting inside the artifact it checks.

    The divergent keys are held in **both** directions. A key that drifted makes the
    second file a second machine; a declared-divergent key that stopped diverging makes
    it a second *copy* of the first machine, and the V-class evidence measured against
    it would be evidence about the C class under another name.
    """
    rep = ctx.rep
    findings: list[str] = []
    primary, second = (config.flat_of(ctx.root / rel) for rel in SHIPPED_CONFIGS)

    findings += [f"{rel} is not there or no longer parses as the model's configuration "
                 f"dialect"
                 for rel, table in zip(SHIPPED_CONFIGS, (primary, second), strict=True)
                 if not table]

    if primary and second:
        findings += [f"{SHIPPED_CONFIGS[1]} does not declare {key}, which "
                     f"{SHIPPED_CONFIGS[0]} does"
                     for key in sorted(set(primary) - set(second))]
        findings += [f"{SHIPPED_CONFIGS[1]} declares {key}, which "
                     f"{SHIPPED_CONFIGS[0]} does not"
                     for key in sorted(set(second) - set(primary))]
        findings += [f"the two shipped configurations disagree on {key}, which is not "
                     f"one of the {len(CONFIG_DIVERGENCE)} keys that say which core of "
                     f"the composed roster an emulator is"
                     for key in sorted(set(primary) & set(second))
                     if primary[key] != second[key] and key not in CONFIG_DIVERGENCE]
        findings += [f"{key} is declared as the divergence between the two shipped "
                     f"configurations and does not diverge, so the second describes the "
                     f"same core as the first"
                     for key in CONFIG_DIVERGENCE
                     if key in primary and key in second
                     and primary[key] == second[key]]

    # Leaf paths rather than every key path, which is what `keys` counts and what
    # `model.py config-keys` reports: the question here is what the two files *say*, so
    # the figure is the values compared and not the surface declaring them.
    ctx.shared["shipped_config_values"] = len(primary)
    rep.report("K-65", "shipped configuration(s) that are not one model's:", findings,
               f"the {len(SHIPPED_CONFIGS)} shipped configurations state the same "
               f"{len(primary)} values and differ in the {len(CONFIG_DIVERGENCE)} that "
               "name the core each of them composes")


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

    _tag_plane(ctx)
    _owned_figures(ctx)
    _block_geometry(ctx)
    _freeze_delta(ctx)
    _core_classes(ctx)
    window, faults = _citation_window(ctx)
    _model_citations(ctx, window, faults)
    _excluded_forms(ctx, window)
    _shipped_configurations(ctx)
    rep.line()
