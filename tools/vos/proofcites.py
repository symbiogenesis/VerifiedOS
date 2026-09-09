# SPDX-License-Identifier: Apache-2.0
"""Requirement citations, discharge annotations and source declaration names.

The host reads citations lexically, resolving their ids against the live register.
Generated requirement-header regions are excluded: a manifest cannot select its own
membership, and legacy transcriptions cannot turn their references into authored cites.
The delimiters and region validation are shared with the header generator and K-108.

A discharge annotation claims that the following statement answers named requirements.
Marker-level validation rejects malformed annotations, enclosing comments and strings.
The native guest audit resolves each claim to a compiled symbol, checks its type is a
proposition, and enumerates its assumptions. Whether that proposition expresses the
requirement is still the specification review gate's judgment.

The source-name reader strips comments and reads declaration vernacular. It supports
host navigation; it is not the native inventory the assumption gate relies on.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from vos.proofs import marker_depths, sentences
from vos.register import REQ_TOKEN_RE

# The shipped proof artifacts, as the directory holding them and the kind they are.
PROOFS = "proofs"
SUFFIX = ".v"

# The delimiters a derived header region is written between, and the marker both of them
# open with. Each is a whole Gallina comment, so a region sits inside the header comment
# it belongs to as a nested one, and neither delimiter carries a requirement id itself.
# They are declared here rather than at either reader because three things spell them,
# the exclusion below, the rule holding it, and the writer that will fill a region in.
DERIVED_BEGIN = "(*| BEGIN derived: cited entries |*)"
DERIVED_END = "(*| END derived |*)"
DERIVED_MARK = "(*|"

# Both delimiters in one pattern, the BEGIN's label admitted and never required. The
# marker count is compared against the number of matches, so a delimiter respelled past
# this pattern is a fault rather than a region silently stopping being one.
_DERIVED_RE = re.compile(r"\(\*\|\s*(BEGIN|END)\s+derived\s*(?::[^|\r\n]*)?\|\*\)")

# The other construct spelled in this marker, and the reason the stray count subtracts
# it. `(*|` is coqdoc's delimiter rather than this repository's, so the region is not
# its only occupant: a discharge annotation above a constant is written in it too, and
# was here first. Counting every marker as an attempted delimiter therefore reported
# each of those as a region nothing excludes, which is a rule whose premise its own
# tree had already falsified. Subtracting the well-formed ones keeps what the stray
# count is for, a BEGIN or an END respelled past `_DERIVED_RE` leaving a region
# unexcluded with nothing said, and widens it by one honest case: an annotation
# misspelled past this pattern is a marker in neither set and is reported here rather
# than read as prose by everything.
_ANNOTATION_RE = re.compile(r"\(\*\|\s*discharges:[^|\r\n]*\|\*\)")

# The vernaculars whose sentence binds a top-level name. It is deliberately *not*
# `cli/proofs.py`'s `DEFINERS`, and the difference is the question each list answers
# rather than a second copy of one answer: that one is the shape a non-vacuity witness
# takes, a closed definition typed at a carrier record, so a `Fixpoint`, an `Inductive`
# and a `Record` are outside it by construction. An index of what a file *defines* wants
# all three, a record declaration being as much a constant of the file as a lemma is.
DEFINERS = ("Definition", "Example", "Theorem", "Lemma", "Corollary", "Fact",
            "Proposition", "Remark", "Instance", "Fixpoint", "CoFixpoint",
            "Inductive", "CoInductive", "Variant", "Record", "Structure")

# The modifiers a definition may open with and still be the same definition: an
# attribute block, and the locality and elaboration keywords that precede a vernacular.
# Public because [the citations check](checks/citations.py) composes a pattern of its
# own over the same opening, and what precedes a vernacular is one fact: written twice
# it becomes two, and the second one goes stale the first time a keyword is added here.
MODIFIERS = r"(?:#\[[^\]]*\]\s*)?(?:Local\s+|Global\s+|Program\s+)*"
_DEFINED_RE = re.compile(rf"^{MODIFIERS}(?:{'|'.join(DEFINERS)})\s+([\w']+)")

# The vernaculars whose sentence *states* something, which is the set a discharge may
# sit above. It is a subset of `DEFINERS` and the difference is the whole content of the
# distinction this module keeps: a `Definition`, a `Fixpoint`, an `Inductive` or a
# `Record` introduces a term, and a term answers no obligation, where a `Theorem` and
# its six synonyms assert one. `Example` is in because Rocq treats it as a `Definition`
# whose body is a proof script and this repository writes its known-answer checks that
# way, so an `Example` is a sentence somebody proved and can be claimed against an
# entry; `Instance` is out because what it asserts is a class membership the elaborator
# fills in, and a claim on it would be a claim about a resolution rather than about a
# statement.
STATEMENTS = ("Theorem", "Lemma", "Corollary", "Fact", "Proposition", "Remark",
              "Example")

# The marker a discharge annotation opens with. Every occurrence of it in a proof
# artifact is an attempt at an annotation, which is what makes a malformed one a fault
# rather than a comment this parse walks past. It is a literal, so the scan for it is
# `str.find` rather than a pattern: over the shipped tree that is one C-level pass
# costing about the same as the citation half's own `findall`.
DISCHARGE_OPEN = "(*|"

# The word the annotation states its claim with, held here so that the pattern below and
# every message about a malformed annotation spell it once.
DISCHARGE_WORD = "discharges"

# The annotation and the sentence beneath it, as one anchored match. The id list may not
# span lines, which is what bounds the `[^|\r\n]*` run to the line it opens on rather
# than to the rest of a two-megabyte artifact; nothing but horizontal space may follow
# the closing marker, and no blank line is admitted between the two, because a discharge
# that floats above an empty line names whichever sentence happens to come next.
_DISCHARGE_RE = re.compile(
    rf"\(\*\|[^\S\r\n]*{DISCHARGE_WORD}:(?P<ids>[^|\r\n]*)\|\*\)[^\S\r\n]*\r?\n"
    rf"[^\S\r\n]*{MODIFIERS}(?P<vernac>[A-Za-z]+)[^\S\r\n]+(?P<name>[\w']+)")

# One annotation's whole content: the constant it sits above, and the entries that
# constant claims to answer. Repeats inside one list are the caller's to notice; the
# order is the file's, because a ledger written in it reads down the artifact.
type Claim = tuple[str, list[str]]


def is_source(rel: str) -> bool:
    """Whether a repository-relative path is one of the shipped proof artifacts."""
    return rel.startswith(f"{PROOFS}/") and rel.endswith(SUFFIX)


def on_disk(root: Path) -> list[str]:
    """Every proof artifact the working tree holds, as relative paths in name order.

    The working tree and not the git index, and the two readers want opposite things.
    A rule decides about the corpus, which is what the index carries, so it takes its
    subject from there; a query answers for the person editing, whose new artifact is
    not staged yet and whose question is about the file in front of them.
    """
    directory = root / PROOFS
    if not directory.is_dir():
        return []
    return sorted(f"{PROOFS}/{path.name}" for path in directory.glob(f"*{SUFFIX}"))


def read(root: Path, rels: list[str]) -> tuple[list[tuple[str, str]], list[str]]:
    """The named artifacts as `(path, text)` pairs, and why any of them could not be.

    A path that is not on disk is one the caller's own listing has outrun, a peer
    session's deletion landing between the listing and the read; a path that is there
    and will not decode is a finding, because a proof artifact this tool cannot open is
    one whose citations nothing decides. Both come back rather than being raised, so the
    caller reports them under its own rule instead of ending in a traceback.
    """
    pairs: list[tuple[str, str]] = []
    faults: list[str] = []
    for rel in rels:
        path = root / rel
        if not path.is_file():
            faults.append(f"{rel} is listed and not in the working tree, so there are "
                          "no bytes here to read")
            continue
        try:
            pairs.append((rel, path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError) as exc:
            faults.append(f"{rel} is unreadable, so its citations cannot be decided "
                          f"({exc})")
    return pairs, faults


@dataclass(frozen=True)
class Derived:
    """One artifact's derived regions, and why its delimiters could not be read.

    `spans` are the character ranges between a BEGIN and the END that closes it,
    delimiters excluded; `faults` is why there are none. **The two are exclusive by
    construction**, and that is the whole safety property: an artifact whose
    delimiters do not balance yields no span at all, so a BEGIN nobody closed excludes
    nothing and the citation reading above it goes on reading the file whole rather
    than agreeing quietly with every one of no citations. The fault is what the caller
    reports; swallowing it would be the failure this exclusion is capable of.
    """

    spans: tuple[tuple[int, int], ...] = ()
    faults: tuple[str, ...] = ()


def line_at(text: str, offset: int) -> int:
    """The 1-based line an offset falls on, for a finding somebody has to go and read."""
    return text.count("\n", 0, offset) + 1


def derived(text: str) -> Derived:
    """Every derived region one artifact carries, or why its delimiters do not read.

    One whole-text pass behind a substring pre-test, which is what keeps it free on the
    artifacts carrying no region: `DERIVED_MARK` is a C-level scan and the pattern is
    spent only where a marker is actually there.

    **Four ways the delimiters fail to read, and each is a fault rather than a span
    quietly dropped.** A BEGIN inside an open region, an END no BEGIN opened, a BEGIN
    the file never closes, and a marker that is neither delimiter, which is what a
    respelled or mistyped one leaves behind and is the one of the four that would
    otherwise leave a region unexcluded with nothing said.
    """
    if DERIVED_MARK not in text:
        return Derived()

    spans: list[tuple[int, int]] = []
    faults: list[str] = []
    opened_at: int | None = None
    content_from = 0
    read = 0
    for m in _DERIVED_RE.finditer(text):
        read += 1
        if m.group(1) == "BEGIN":
            if opened_at is not None:
                faults.append(f"line {line_at(text, m.start())} opens a derived region "
                              f"inside the one line {line_at(text, opened_at)} opened, "
                              "and a region does not nest")
            else:
                opened_at, content_from = m.start(), m.end()
        elif opened_at is None:
            faults.append(f"line {line_at(text, m.start())} closes a derived region no "
                          "line above it opened")
        else:
            spans.append((content_from, m.start()))
            opened_at = None

    if opened_at is not None:
        faults.append(f"line {line_at(text, opened_at)} opens a derived region the file "
                      "never closes, which is the delimiter that would hold every "
                      "citation below it out of the reading")
    stray = text.count(DERIVED_MARK) - read - len(_ANNOTATION_RE.findall(text))
    if stray:
        faults.append(f"{stray} occurrence(s) of `{DERIVED_MARK}` are neither a BEGIN "
                      "nor an END this parse reads, nor a discharge annotation, so a "
                      "region may be delimited by a marker nothing excludes")

    return Derived((), tuple(faults)) if faults else Derived(tuple(spans), ())


def ids(text: str, region: Derived | None = None) -> list[str]:
    """Every requirement citation one artifact makes, in the order it makes them.

    Repeats are kept: how often an artifact argues from an entry is the caller's to
    count, and a set here would silently answer a different question.

    A derived reference manifest or legacy transcription is skipped, so its generated
    ids cannot select their own membership on the next regeneration. An artifact whose
    delimiters do not balance carries no region here, so the whole of it is read and
    the imbalance is `derived`'s fault for the caller to report.

    `region` is that parse where the caller has already made it, and the parameter is
    the scan's shape rather than a convenience: the exclusion costs one whole-text pass
    per artifact, and the citations group's two rules would otherwise each pay for it
    over the same bytes. A caller with nothing to hand over passes nothing.
    """
    if region is None:
        region = derived(text)
    if not region.spans:
        # `findall` over a pattern with no group hands back the whole matches, which are
        # strings; the cast says so, where rebuilding the list to prove it would be a
        # Python-level pass over every hit for nothing.
        return cast("list[str]", REQ_TOKEN_RE.findall(text))
    return [m.group() for m in REQ_TOKEN_RE.finditer(text)
            if not any(start <= m.start() < end for start, end in region.spans)]


def cited_within(text: str, span: tuple[int, int]) -> list[str]:
    """Every requirement id one derived region names, in the order it names them."""
    return cast("list[str]", REQ_TOKEN_RE.findall(text, span[0], span[1]))


def names(text: str) -> list[str]:
    """Every top-level constant one artifact defines, in declaration order.

    Comments are stripped first, so a vernacular written inside the header prose no
    more defines a constant than it would compile as one.
    """
    found: list[str] = []
    for sentence in sentences(text):
        m = _DEFINED_RE.match(sentence)
        if m:
            found.append(m.group(1))
    return found


def _listed(body: str) -> tuple[list[str], str | None]:
    """The annotation's id list, or why it is not one.

    Comma-separated and nothing else, so a list is read as a list rather than scanned
    for whatever happens to look like an id in it. The difference is the case the
    scanning reading gets wrong: `discharges: R-07-015 and the rest` yields one id under
    a `findall` and reports nothing, where the author wrote a sentence and meant two.
    """
    found: list[str] = []
    for token in body.split(","):
        word = token.strip()
        if not word:
            return [], ("an empty entry in its id list, so the list is not a "
                        "comma-separated one" if body.strip() else
                        "no requirement id at all, so it claims nothing")
        if not REQ_TOKEN_RE.fullmatch(word):
            return [], (f"{word!r} in its id list, which is not a requirement id; the "
                        "form is comma-separated R-nn-nnn with an optional letter "
                        "suffix and nothing else")
        if word in found:
            return [], (f"{word} twice in one id list, so how many entries the "
                        "annotation claims depends on which of the two is read")
        found.append(word)
    return found, None


def discharges(text: str) -> tuple[list[Claim], list[str]]:
    """Every discharge annotation one artifact makes, and the ones it could not read.

    The claims come back in the order the file makes them and the faults in the order it
    commits them, each naming the line a person has to go and visit. Both are returned
    rather than raised, on the same ground `read` above states about a file that will
    not decode: a rule reports what it could not read, and an artifact carrying one
    mistyped annotation still yields the rest of its claims.

    Four things are refused and each is worded as itself, because they are four
    different edits. A marker that shares its line with code before it is not the form
    at all. A marker whose annotation will not parse is a mistyped one. An id list that
    is not a comma-separated list of distinct requirement ids claims something this parse
    cannot name. And an annotation above a vernacular outside `STATEMENTS` is a claim on
    a term rather than on a sentence, which is the one of the four that renders
    perfectly and reads as correct.

    The line a fault names is accumulated across the scan rather than counted from the
    start of the file at each hit, which is one pass over the text for the whole walk
    instead of one per marker: the tree the host wave reads is two and a half megabytes,
    and the annotations are expected to number in the hundreds.
    """
    claims: list[Claim] = []
    faults: list[str] = []
    depths = marker_depths(text, DISCHARGE_OPEN) if DISCHARGE_OPEN in text else {}
    at, line = 0, 1
    while (mark := text.find(DISCHARGE_OPEN, at)) >= 0:
        line += text.count("\n", at, mark)
        at = mark + len(DISCHARGE_OPEN)
        if _DERIVED_RE.match(text, mark):
            continue
        if depths.get(mark) != 0:
            faults.append(f"line {line} places a discharge inside an enclosing "
                          "comment or string, where it binds no compiled statement")
            continue
        head = text.rfind("\n", 0, mark) + 1
        if text[head:mark].strip():
            faults.append(f"line {line} opens {DISCHARGE_OPEN} with code before it on "
                          "the same line; a discharge annotation sits alone on the line "
                          "above the statement it claims")
            continue
        hit = _DISCHARGE_RE.match(text, mark)
        if hit is None:
            faults.append(f"line {line} opens {DISCHARGE_OPEN} and no discharge "
                          f"annotation follows it; the form is `{DISCHARGE_OPEN} "
                          f"{DISCHARGE_WORD}: R-nn-nnn |*)` alone on its line, with a "
                          "statement on the next line and no blank line between")
            continue
        listed, fault = _listed(hit.group("ids"))
        if fault is not None:
            faults.append(f"line {line} states {fault}")
            continue
        vernac, name = hit.group("vernac"), hit.group("name")
        if vernac not in STATEMENTS:
            faults.append(f"line {line} claims {', '.join(listed)} above "
                          f"`{vernac} {name}`, which states nothing; a discharge sits "
                          f"above one of {', '.join(STATEMENTS)}")
            continue
        claims.append((name, listed))
    return claims, faults


def citations(pairs: list[tuple[str, str]]) -> dict[str, set[str]]:
    """The citation index: each artifact against the requirements it names."""
    return {rel: set(ids(text)) for rel, text in pairs}


def claims(pairs: list[tuple[str, str]]) -> tuple[dict[str, list[Claim]], list[str]]:
    """The discharge index: each artifact against what its constants claim to answer.

    The faults of every artifact are gathered into one list rather than kept per file,
    because their one reader reports them under a single rule and each already names the
    artifact it came from. A constant annotated twice in one file is a fault here rather
    than two claims, since the two annotations are two answers to the question *what
    does this constant claim*, and a ledger built over both would carry the constant
    twice against whichever union of ids the second annotation happened to write.
    """
    index: dict[str, list[Claim]] = {}
    faults: list[str] = []
    for rel, text in pairs:
        found, problems = discharges(text)
        faults += [f"{rel}: {problem}" for problem in problems]
        seen: set[str] = set()
        kept: list[Claim] = []
        for name, listed in found:
            if name in seen:
                faults.append(f"{rel}: `{name}` carries more than one discharge "
                              "annotation, so what that constant claims is stated twice")
                continue
            seen.add(name)
            kept.append((name, listed))
        index[rel] = kept
    return index, faults


def constants(pairs: list[tuple[str, str]]) -> dict[str, list[str]]:
    """The definition index: each artifact against the constants it binds, in order."""
    return {rel: names(text) for rel, text in pairs}


def citing(index: dict[str, set[str]], ident: str) -> list[str]:
    """The artifacts citing one requirement, in the index's own order."""
    return [rel for rel, cited in index.items() if ident in cited]
