# SPDX-License-Identifier: Apache-2.0
"""interims: every citation of an interim anchor's lineage, against R-05-022's consumer lists.

R-05-022 books two interim non-Coq anchors, F\\*/Z3 for libcrux/HACL\\* and EasyCrypt's
Why3/SMT, and holds one consumer list for each: every admitted artifact whose certificate,
validation record or acceptance cites the interim's verdict as a premise, entered when it
is admitted. R-05-022a makes a list that grows without its destination advancing a
review-gate finding, and R-17-046 reads each interim's trust-base surface off its list.
**The proof gate cannot see a consumer.** An acceptance that rides HACL\\*'s verdict adds
no axiom to any Rocq term, so R-05-163 stays exactly as green as it was, and a list kept
by hand grows silently the day a landing forgets to enter itself, which is the silent
extension R-05-022a refuses.

**So the lists are closed in both directions over every file that can admit an
artifact.** Each place such a file names a lineage of either interim is resolved to a
consumer R-05-022 lists for that interim, by the anchor it sits under, or to a
declaration in `NON_PREMISE` below that it cites no premise, by its line. A declaration
names its anchor, the reason, and one literal fragment of each citing line it
classifies, K-68's literal-per-site shape: a line under a declared anchor that carries
none of the anchor's fragments is unresolved, so a premise written into an anchor
already declared is a finding and not a citation the declaration swallows. A citation
resolving to neither is the finding the rule exists for; a fragment naming no citing
line or two, a declaration no citation answers, and a listed consumer whose anchor
cites nothing of its interim are the other direction. The two sides are deliberately
not the same size: a consumer is entered by the artifact R-05-022 names, a requirement,
an item or a path, because the register lists artifacts and not sentences, while a
declaration is the rule's own and so can afford to be exact. The distinction the
declarations draw is R-05-061's own, as the completion log's M3.4a licence reading
states it: a pinned comparator read for its answers rides nothing, and a post-quantum
primitive imported so that its correctness rests on F\\* and Z3 is a consumer.

**A lineage is found by its names, never by its solver.** `Z3` and `Why3` are not read:
Z3 is a solver and Why3 a verification platform, each also serving tools R-05-022 books
as no interim, Cranelift/Crocus's SMT among them, so neither name identifies an interim
and reading one would turn every SMT mention into a classification. The names are the
prover and its low-level fragment (`F*` and `Low*`, escaped or not or with the
typographic star, and `fstar`, `f-star` and `lowstar` as a repository or binary spells
them), the libraries, extractor and vendor that deliver its verdicts (HACL\\* with
EverCrypt, libcrux, hax, KaRaMeL and its `krml`, Cryspen) and, for EasyCrypt, the prover
with Jasmin, libjade and formosa-crypto. Every name but the starred ones, hax and
formosa is read as the start of a word in any case, so `hacl-star`, a generated `Hacl_`
identifier, `fstar.exe` and `mitls-fstar` are the same lineage as the prose's names,
and Jasmin's tools, `jasminc` and `jasmin2ec`, are read while the word *jasmine* is not.
Vale is not read: it is a common word and the name of more than one language, and no
surface cites the F\\* lineage's Vale today, so reading it would classify prose rather
than find a lineage. The unit tests hold every token to its canonical spelling and a
fixed list of spellings to their tokens, which is the floor against the table
narrowing.

**The surfaces are the index less declared exclusions, and not a list of places to
look.** The corpus is what git tracks, read as the working tree holds it, so a file is
inside the rule the day it is tracked and escapes only by leaving the repository or by
joining an exclusion row. Each row names a class that admits nothing, with the reason,
as a directory when it ends in `/` and as one exact path otherwise; a row that no
longer matches any tracked file is a finding, as a residue that suppresses nothing is
under K-81. Retained evidence is read, being a validation record; the one exclusion
narrower than a path is the pin entry of a machine-written environment snapshot there,
which records what was checked out and repeats verbatim wherever the snapshot was
taken, and it too is a finding the day it passes over nothing. A file that is not
UTF-8 is read all the same, the line a citation quotes decoded with replacement, the
glyphs group owning what every tracked file is made of; a tracked file absent from
disk or refusing to read is a finding, whether it cites an interim being undecided,
as K-83 treats a source it cannot read.

**An anchor is where an admission is recorded.** A register line belongs to the
requirement whose entry it is in, a plan line to the innermost checklist item whose span
holds it, a completion-log line to the entry heading above it, and a line of the licence
record to its heading or, in the pin table, to the submodule its row pins; every other
file is one anchor, its path. Those are the three forms a consumer list names: a
requirement ID, a checklist label (its head, `M3.4b`, reaching the item and the log entry
its landing wrote), or a repository path in backticks.

**The lists are read from R-05-022's criterion in the register's own words.** `Both
consumer lists are empty.` is the empty form. A list with members is stated per interim,
as in F\\*/Z3's consumers are M3.4x and `kernel/src/mlkem.c`; EasyCrypt's consumer list
is empty. Each clause ends at a full stop or a semicolon. An absent entry, an
entry with no criterion, an interim with no statement, an interim stated twice, the
empty sentence beside a per-interim statement, and a consumer entered twice each fail
closed rather than leaving citations held against no list.

**Fail-closed, with the floors inside the rule.** An anchored document missing from the
corpus, a scan that reaches no surface, and an interim cited nowhere at all are each
findings here: R-05-022 names both lineages itself, so a scan finding either absent has
stopped reading rather than found nothing. Reporting the empty reading itself is what
lets the rule owe the floors group no count.

**What this cannot decide is whether a declaration is right.** A declared citation is
classified by its line, so a premise written into a line a fragment already names
resolves with it, and a citation under a listed consumer's anchor resolves with the
consumer; the declaration's reason is the reading a reviewer re-takes when a named
line's text moves. Whether a destination has advanced, the other half of R-05-022a's
test, is not read here at all.
Nothing is repaired: entering a consumer or declaring a non-premise is a judgment about
what an admission rests on, and a `--fix` that wrote either would record one nobody took.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, cast

from vos import findings as plan_mod
from vos import pins as pins_mod
from vos import sailbundle
from vos.corpus import HEADING_RE, UNREAD_PREFIX, Document, from_text
from vos.register import REGISTER, REQ_ID_PATTERN, REQ_TOKEN_RE

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = ("=== interims: every lineage citation of an interim anchor, against its "
           "consumer list ===")

GOVERNING = "R-05-022"
HOME = "tools/vos/checks/interims.py"
FSTAR = "F*/Z3"
EASYCRYPT = "EasyCrypt"
INTERIMS = (FSTAR, EASYCRYPT)

PLAN = plan_mod.PLAN
LOG = plan_mod.LOG
RECORD = pins_mod.RECORD
ANCHORED = (REGISTER, PLAN, LOG, RECORD)


@dataclass(frozen=True)
class Token:
    """One lineage name, how it is found, and the interim it belongs to.

    `folded` searches the ASCII case-folded bytes, for a name code spells as an
    identifier as well as prose does. `tail` is what may not follow the name: nothing
    for `prefix`, a letter or digit for `word`, and for `star` a word character or a
    second star, which after an unescaped `F*` is Markdown's bold closing. `refuse`
    names the letters, case-folded, that may not follow a `prefix` name, which is how
    Jasmin's tools are read and the word *jasmine* is not. `name` is the canonical
    spelling, which the unit tests hold each token to finding.
    """

    name: str
    needle: bytes
    folded: bool
    interim: str
    tail: str
    refuse: bytes = b""


_STAR_GLYPH = "⋆"   # the typographic star the F* project writes its names with

TOKENS: tuple[Token, ...] = (
    Token("F*", b"F*", False, FSTAR, "star"),
    Token("F\\*", b"F\\*", False, FSTAR, "word"),
    Token(f"F{_STAR_GLYPH}", f"F{_STAR_GLYPH}".encode(), False, FSTAR, "word"),
    Token("Low*", b"Low*", False, FSTAR, "star"),
    Token("Low\\*", b"Low\\*", False, FSTAR, "word"),
    Token(f"Low{_STAR_GLYPH}", f"Low{_STAR_GLYPH}".encode(), False, FSTAR, "word"),
    Token("FStar", b"fstar", True, FSTAR, "prefix"),
    Token("F-star", b"f-star", True, FSTAR, "prefix"),
    Token("LowStar", b"lowstar", True, FSTAR, "prefix"),
    Token("KaRaMeL", b"karamel", True, FSTAR, "prefix"),
    Token("krml", b"krml", True, FSTAR, "prefix"),
    Token("HACL", b"hacl", True, FSTAR, "prefix"),
    Token("EverCrypt", b"evercrypt", True, FSTAR, "prefix"),
    Token("libcrux", b"libcrux", True, FSTAR, "prefix"),
    Token("Cryspen", b"cryspen", True, FSTAR, "prefix"),
    Token("hax", b"hax", True, FSTAR, "word"),
    Token("EasyCrypt", b"easycrypt", True, EASYCRYPT, "prefix"),
    Token("Jasmin", b"jasmin", True, EASYCRYPT, "prefix", refuse=b"e"),
    Token("libjade", b"libjade", True, EASYCRYPT, "prefix"),
    Token("formosa-crypto", b"formosa", True, EASYCRYPT, "word"),
)

_ALNUM = frozenset(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
_WORD = _ALNUM | frozenset(b"_")
_STAR = ord("*")

# The classes of tracked file that admit nothing, each with the reason. A row ending in
# `/` is a directory and excludes every path under it; any other row is one exact path.
# A path no row excludes is an admission surface, so a new file is read by default.
_SURVEY = "a survey read ahead of any item; what it surveys is admitted at the item"
_CHECKER = ("the checker, its selftest, its tests and its registry, which spell the "
            "lineages to classify or seed them and decide admission rather than carry "
            "it; the admission and evidence tooling beside them is read")
EXCLUDED: dict[str, str] = {
    UNREAD_PREFIX: "the curated Sail model, the ISA anchor R-06-011 admits: a semantics "
                   "the proofs quantify over, never an artifact admitted on a prover's "
                   "verdict",
    sailbundle.BUNDLE: "the model's generated bundle, a function of the curated model",
    ".gitmodules": "submodule fetch configuration; a pin's standing is its licence-record "
                   "row, which is read",
    "docs/spec.md": "the design prose the register extracts, never an artifact's "
                    "certificate, validation record or acceptance (R-05-152)",
    "docs/background/": _SURVEY,
    "docs/implementation/static-memory/literature.md": _SURVEY,
    "docs/languages/": "language dossiers: design and verification-route surveys; a "
                       "component written in a language is admitted at its item",
    "docs/assurance/proof-reuse/": "the proof-reuse subject records, which qualify "
                                   "candidate sources from dated source and licence "
                                   "readings; a reused source is admitted at the item "
                                   "reusing it",
    "docs/assurance/proof-reuse.md": "the proof-reuse inventory's index, stating what "
                                     "qualifies a source and the dispositions its "
                                     "records use; it names other provers as precedent "
                                     "and admits nothing",
    "docs/assurance/unassigned-proof-map.md": "proof slices priced outside the plan until "
                                              "an item owns them, with a start-from "
                                              "column surveying candidate sources",
    "docs/assurance/findings-register.md": "findings and their dispositions, never an "
                                           "acceptance",
    "docs/implementation/userspace-porting.md": "the userland porting plan, ranking "
                                                "start-froms per component; a component "
                                                "is admitted at its item",
    "docs/performance/": "performance estimates, benchmarks and inference-demand inputs",
    "tools/vos/checks/": _CHECKER,
    "tools/vos/cli/selftest.py": _CHECKER,
    "tools/tests/": _CHECKER,
    "tools/check-rules.md": _CHECKER,
}

# The one exclusion narrower than a path: the pin entry of a machine-written environment
# snapshot, in the JSON the two evidence directories retain. Retained evidence is a
# validation record and is read, but a snapshot's digest map spells each gitlink as
# `"upstream/<path>": "gitlink:<commit>"`, as many times as the snapshot was taken, so
# no fragment could name one such line apart from its twin.
SNAPSHOT_DIRS = ("docs/implementation/retained-evidence/",
                 "docs/assurance/sail-assistance-evidence/")
SNAPSHOT_PIN_RE = re.compile(r'\s*"upstream/[^"\s]+": "gitlink:[0-9a-f]{40}",?\s*')
SNAPSHOT_PIN = ("an environment snapshot's pin entry, the path of a gitlink and the "
                "commit the index held for it when the evidence was taken: it records "
                "what was checked out, never what a result rests on, and the pin's "
                "standing is its licence-record row, which is read")


def _excludes(row: str, rel: str) -> bool:
    """Whether an exclusion row excludes a path: a directory by prefix, a file exactly."""
    return rel.startswith(row) if row.endswith("/") else rel == row


def _snapshot_pin(rel: str, text: str) -> bool:
    return (rel.endswith(".json") and rel.startswith(SNAPSHOT_DIRS)
            and SNAPSHOT_PIN_RE.fullmatch(text) is not None)


@dataclass(frozen=True)
class NonPremise:
    """A declaration that the named lines of an anchor cite no premise of these interims.

    `fragments` holds one short verbatim substring of each citing line the declaration
    classifies, unique among the anchor's citing lines; a citing line it does not name
    stays unresolved.
    """

    interims: tuple[str, ...]
    reason: str
    fragments: tuple[str, ...]


# Every anchor on an admission surface that cites a lineage and rides nothing, keyed by
# path and anchor, "" being a file read as one anchor. Each reason says what the named
# lines' citations are; none of them cites an interim's verdict as a premise.
NON_PREMISE: dict[tuple[str, str], NonPremise] = {
    (REGISTER, "R-05-010"): NonPremise(
        (FSTAR, EASYCRYPT), "the prohibition keeping a contained component's "
        "foreign-prover pedigree out of the trust base",
        ("attributes no entry to a contained component's",)),
    (REGISTER, GOVERNING): NonPremise(
        (FSTAR, EASYCRYPT), "the interims' own governing rule, which holds these lists",
        ("each carry a destination and a consumer list, held here",)),
    (REGISTER, "R-05-044"): NonPremise(
        (FSTAR,), "EverParse's refusal: no shipped parser derives from an F*/Z3 "
        "generator", ("no shipped parser derives from an",)),
    (REGISTER, "R-05-061"): NonPremise(
        (FSTAR,), "the booking of libcrux/HACL* as the interim F*/Z3 widening",
        ("widening with a named Coq-native destination, not an open-ended tolerance",)),
    (REGISTER, "R-05-075"): NonPremise(
        (EASYCRYPT,), "EasyCrypt results as accelerators whose destination is SSProve",
        ("results are accelerators with SSProve as the stated destination",)),
    (REGISTER, "R-12-032"): NonPremise(
        (FSTAR,), "the TLS route ranking, whose protocol proof is bonus and never "
        "trust base", ("over the memory-safety floor and never trust base",)),
    (REGISTER, "R-18-023"): NonPremise(
        (FSTAR, EASYCRYPT), "the admission of an EasyCrypt reduction as interim "
        "assurance beside libcrux/HACL*", ("is admissible interim assurance exactly as",)),
    (PLAN, "4. Verified crypto core (Coq)"): NonPremise(
        (FSTAR, EASYCRYPT), "installed OpenSSL's behaviour as the reference's oracle, HACL* and "
        "libjade named only as editions that do not carry it, no "
        "F*/Z3 dependency entering the golden model, and EasyCrypt gadget proofs "
        "informing the masking half without discharging it",
        ("behavior as the oracle", "dependency enters the golden model",
         "gadget proofs inform the Boolean half")),
    (PLAN, "Post-M10 · Author the Boolean composition half"): NonPremise(
        (EASYCRYPT,), "EasyCrypt's masking proofs as a source in the weakest sense, "
        "credited with no reduction", ("a source in the weakest of the three senses",)),
    (LOG, "M3.4a · The cryptography licence reads, and SHA-3 in Gallina"): NonPremise(
        (FSTAR, EASYCRYPT), "the licence reads of the pinned comparators, read for their "
        "answers, with R-05-061's line between a comparison and a widening",
        ("the Jasmin tree pinned here does state terms",
         "takes here is the comparator's, not the interim anchor's")),
    (RECORD, "upstream/hacl-star"): NonPremise(
        (FSTAR,), "the pin row of a planned comparator, never built, copied or "
        "extracted", ("No differential run, build, copying, or extraction occurs here.",)),
    (RECORD, "upstream/libjade"): NonPremise(
        (EASYCRYPT,), "the pin row of a planned comparator, never built, copied or "
        "extracted", ("Planned independent comparator from the Jasmin/EasyCrypt lineage",)),
    (RECORD, "Pinned as submodules"): NonPremise(
        (EASYCRYPT,), "the licence instruments re-read at an advanced pin",
        ("- libjade: `LICENSE` and the two texts under `LICENSES/`.",)),
    (RECORD, "Proof and lowering references"): NonPremise(
        (FSTAR, EASYCRYPT), "where the comparators' licence terms were located",
        ("**Cryptography references.** Reviews on",)),
    (RECORD, "The cryptography upstreams"): NonPremise(
        (FSTAR, EASYCRYPT), "the comparators' standing, unqualified, with nothing "
        "copied", ("without claiming the unrun",)),
    (RECORD, "Behavioral oracles"): NonPremise(
        (FSTAR, EASYCRYPT), "the comparators' terms, and that the comparator role "
        "supplies no proof assumption",
        ("No command builds them or computes a differential result",
         "The comparator role does not supply a proof assumption",
         "does not identify the licensed libjade tree")),
    ("docs/implementation/attested-tls-protocol.md", ""): NonPremise(
        (FSTAR, EASYCRYPT), "HACL* and libjade named as primitive comparators that are "
        "not a TLS stack, with no source incorporated",
        ("a primitive pin is not a TLS stack",)),
    ("docs/assurance/proof-reuse-bearing.md", ""): NonPremise(
        (EASYCRYPT,), "Jasmin's compiler theorem tabled as bearing on no consumer, on "
        "the unaimed ground, with no source acquired",
        ("it acquires no source and proposes no local consumer",)),
    ("proofs/campaigns/mldsa-reference.md", ""): NonPremise(
        (FSTAR,), "no libcrux or HACL* body copied, and the independent comparison run "
        "against OpenSSL instead",
        ("or Dilithium implementation body is copied",
         "The independent implementation campaign uses OpenSSL rather than")),
}


@dataclass(frozen=True)
class Citation:
    """One lineage name on an admission surface, its line and the anchor it sits under."""

    path: str
    line: int            # 1-based
    anchor: str          # "" where the file is read as one anchor
    token: str           # as the site spells it
    interim: str
    text: str            # the whole line, which a declaration's fragment is sought in


# A consumer entry: a requirement ID, a repository path in backticks, or a checklist
# label's head. The label's last character is a letter or digit so that a sentence's
# full stop is not read into it.
_MEMBER = rf"(?:{REQ_ID_PATTERN}|`[^`\s]+`|[A-Z][\w.-]*[A-Za-z0-9])"
_MEMBER_RE = re.compile(_MEMBER)
_STATED_RE = re.compile(
    r"(?P<interim>F\\\*/Z3|EasyCrypt)'s (?:(?P<empty>consumer list is empty)"
    rf"|consumers? (?:is|are) (?P<members>{_MEMBER}(?:, {_MEMBER})*(?:,? and {_MEMBER})?))"
    r"(?=[.;](?:\s|$))")
_SPELLED = {"F\\*/Z3": FSTAR, "EasyCrypt": EASYCRYPT}
BOTH_EMPTY = "Both consumer lists are empty."


@dataclass
class Lists:
    """R-05-022's consumer lists as its criterion states them, and what would not read."""

    consumers: dict[str, list[str]] = field(default_factory=dict)
    faults: list[str] = field(default_factory=list)


def read_lists(accept: str) -> Lists:
    """Both consumer lists, from the text of R-05-022's criteria."""
    read = Lists()
    stated = list(_STATED_RE.finditer(accept))
    if BOTH_EMPTY in accept:
        if stated:
            read.faults.append(
                f"{GOVERNING} states '{BOTH_EMPTY}' beside a list of its own for "
                f"{', '.join(m.group('interim') for m in stated)}, so neither reading "
                "holds")
        else:
            read.consumers = {interim: [] for interim in INTERIMS}
        return read
    for m in stated:
        interim = _SPELLED[m.group("interim")]
        if interim in read.consumers:
            read.faults.append(f"{GOVERNING} states {interim}'s consumer list twice")
            continue
        members = [] if m.group("empty") else _MEMBER_RE.findall(m.group("members"))
        twice = sorted({name for name in members if members.count(name) > 1})
        read.faults += [f"{GOVERNING} enters {name} in {interim}'s consumer list twice"
                        for name in twice]
        read.consumers[interim] = list(dict.fromkeys(members))
    read.faults += [
        f"{GOVERNING} states no consumer list for {interim} in a form this rule reads: "
        f"'{BOTH_EMPTY}', or '{spelled}'s consumer list is empty', or "
        f"'{spelled}'s consumers are' and the entries"
        for spelled, interim in _SPELLED.items() if interim not in read.consumers]
    return read


def hits(blob: bytes) -> list[tuple[int, Token]]:
    """Every lineage name in a file's bytes, as its offset and its token.

    One `find` pass per name over the bytes, the case-folded names over one ASCII
    lowering that keeps every offset where it was; the boundary is decided in Python
    on the few hits rather than by a lookbehind the engine would re-decide at every
    position.
    """
    low = blob.lower()
    found: list[tuple[int, Token]] = []
    for tok in TOKENS:
        hay = low if tok.folded else blob
        at = hay.find(tok.needle)
        while at >= 0:
            if _bounded(blob, at, tok):
                found.append((at, tok))
            at = hay.find(tok.needle, at + 1)
    found.sort(key=lambda hit: hit[0])
    return found


def _bounded(blob: bytes, at: int, tok: Token) -> bool:
    if at and blob[at - 1] in _ALNUM:
        return False
    end = at + len(tok.needle)
    after = blob[end] if end < len(blob) else None
    if tok.tail == "word":
        return after is None or after not in _ALNUM
    if tok.tail == "star":
        if after is not None and (after in _WORD or after == _STAR):
            return False
        # A letter or a word emphasized, `*F*` or `*Low*`, is not the prover: its
        # opening star stands alone where a bold opening would be two.
        return not (at and blob[at - 1] == _STAR and (at < 2 or blob[at - 2] != _STAR))
    return after is None or bytes([after]).lower() not in tok.refuse


def _heading(line: str, fenced: bool) -> str | None:
    if fenced or not line.startswith("#"):
        return None
    m = HEADING_RE.match(line)
    # the group is mandatory in the pattern, so its `Any` arm is narrowed here
    return cast("str", m.group(1)).strip() if m else None


def _headings(doc: Document) -> list[str]:
    """Each line's anchor as the nearest heading above it."""
    out: list[str] = []
    heading = ""
    for i, line in enumerate(doc.lines):
        heading = _heading(line, doc.fenced[i]) or heading
        out.append(heading)
    return out


_ENTRY_RE = re.compile(rf"\*\*({REQ_ID_PATTERN})\*\* (?:IS|MUST NOT|MUST)\b")


def _register_anchors(doc: Document) -> list[str]:
    """Each line's anchor as the entry it is in, or the heading above a line in none.

    An entry runs from its head through its criterion and property lines to the blank
    line the register separates entries with.
    """
    out: list[str] = []
    heading = entry = ""
    for i, line in enumerate(doc.lines):
        if not doc.fenced[i]:
            if not line.strip():
                entry = ""
            elif (head := _heading(line, False)) is not None:
                heading, entry = head, ""
            elif line.startswith("**") and (m := _ENTRY_RE.match(line)):
                entry = m.group(1)
        out.append(entry or heading)
    return out


def _plan_anchors(doc: Document) -> list[str]:
    """Each line's anchor as the innermost checklist item whose span holds it.

    An item's span is every line indented deeper than its bullet, up to the first
    non-blank line that is not, which is K-113's reading; a line in no item belongs to
    the heading above it. The item shape is the findings parse's, read rather than
    copied, struck items included.
    """
    out: list[str] = []
    heading = ""
    items: list[tuple[int, str]] = []
    for i, line in enumerate(doc.lines):
        if line.strip() and not doc.fenced[i]:
            head = _heading(line, False)
            if head is not None:
                heading = head
                items.clear()
            else:
                indent = len(line) - len(line.lstrip())
                while items and indent <= items[-1][0]:
                    items.pop()
                if (m := plan_mod._ITEM_RE.match(line)) is not None:
                    items.append((indent, m.group("label").strip()))
        out.append(items[-1][1] if items else heading)
    return out


def _record_anchors(doc: Document) -> list[str]:
    """Each line's anchor as its heading, or the submodule a pin-table row pins."""
    out = _headings(doc)
    for pin in pins_mod.read_record(doc.raw).rows:
        if pin.path and 0 < pin.line <= len(out):
            out[pin.line - 1] = pin.path
    return out


_ANCHORS: dict[str, Callable[[Document], list[str]]] = {
    REGISTER: _register_anchors,
    PLAN: _plan_anchors,
    LOG: _headings,
    RECORD: _record_anchors,
}
_ANCHORED_SET = frozenset(_ANCHORS)


def _head(label: str) -> str:
    return label.partition(" · ")[0].strip()


def _where(path: str, anchor: str, line: int | None = None) -> str:
    at = f"{path}:{line}" if line is not None else path
    return f"{at} ({anchor})" if anchor else at


@dataclass
class Scan:
    """What the surfaces carry: every citation, and each anchored document's anchors."""

    citations: list[Citation] = field(default_factory=list)
    anchors: dict[str, set[str]] = field(default_factory=dict)
    surfaces: int = 0
    unmatched: list[str] = field(default_factory=list)
    pins: int = 0        # snapshot pin entries passed over
    undecided: list[str] = field(default_factory=list)


def scan(ctx: Context, excluded: dict[str, str], snapshots: bool = False) -> Scan:
    """Every citation on every tracked file outside the exclusions.

    With `snapshots`, a snapshot's pin entry is passed over and counted rather than
    read as a citation.
    """
    read = Scan()
    used: set[str] = set()
    # `tracked` is what is on disk; `indexed` keeps a stage-zero file the working tree
    # has lost, which is what lets that loss be reported rather than walked past
    for rel in sorted(set(ctx.corpus.tracked) | ctx.corpus.indexed):
        matched = {row for row in excluded if _excludes(row, rel)}
        if matched:
            used |= matched
            continue
        read.surfaces += 1
        doc: Document | None = None
        if rel in ctx.corpus:
            text = ctx.text(rel)
            blob = text.encode("utf-8")
            if rel in _ANCHORED_SET:
                doc = from_text(text, rel) if rel in ctx.fixed else ctx.corpus.get(rel)
        elif not (ctx.root / rel).is_file():
            read.undecided.append(f"{rel} is in the index and not on disk, so whether it "
                                  "cites an interim's lineage is undecided")
            continue
        else:
            try:
                blob = (ctx.root / rel).read_bytes()
            except OSError as err:
                read.undecided.append(f"{rel} is in the index and will not read "
                                      f"({err.strerror or err}), so whether it cites an "
                                      "interim's lineage is undecided")
                continue
        anchors = _ANCHORS[rel](doc) if doc is not None else []
        if doc is not None:
            read.anchors[rel] = set(anchors)
        passed: set[int] = set()
        for at, tok in hits(blob):
            index = blob.count(b"\n", 0, at)
            start = blob.rfind(b"\n", 0, at) + 1
            end = blob.find(b"\n", at)
            line = blob[start:end if end >= 0 else len(blob)]
            text = line.decode("utf-8", errors="replace").rstrip("\r")
            if snapshots and _snapshot_pin(rel, text):
                passed.add(index)
                continue
            read.citations.append(Citation(
                path=rel, line=index + 1,
                anchor=anchors[index] if index < len(anchors) else "",
                token=blob[at:at + len(tok.needle)].decode("utf-8", errors="replace"),
                interim=tok.interim, text=text))
        read.pins += len(passed)
    read.unmatched = [row for row in excluded if row not in used]
    return read


def _resolve(name: str, ctx: Context, read: Scan) -> list[tuple[str, str]] | str:
    """The anchors a consumer entry names, or why it names none."""
    if REQ_TOKEN_RE.fullmatch(name):
        if name not in ctx.reg.id_set:
            return "the register declares no such requirement"
        return [(REGISTER, name)]
    if name.startswith("`"):
        path = name.strip("`")
        if path not in ctx.corpus.indexed:
            return "the index carries no such path"
        return [(path, "")]
    items = sorted({label for label in read.anchors.get(PLAN, set())
                    if label == name or _head(label) == name})
    if len(items) > 1:
        return (f"it is the head of {len(items)} checklist items ({'; '.join(items)}), so "
                "it names none of them")
    entries = sorted({label for label in read.anchors.get(LOG, set())
                      if label == name or _head(label) == name})
    sites = [(PLAN, label) for label in items] + [(LOG, label) for label in entries]
    return sites or "no checklist item or completion-log entry carries that label"


def decide(ctx: Context, excluded: dict[str, str],
           declared: dict[tuple[str, str], NonPremise],
           snapshots: bool = False) -> tuple[list[str], str]:
    """Every finding over the surfaces, and the sentence a clean run states.

    `snapshots` applies the snapshot pin exclusion, which the live run does and a
    fixture opts into.
    """
    found: list[str] = []

    # the lists, fail-closed at every reading
    lists = Lists()
    if GOVERNING not in ctx.reg.id_set:
        found.append(f"the register declares no {GOVERNING}, so there are no consumer "
                     "lists to hold a citation against")
    elif not ctx.reg.accept_text.get(GOVERNING, "").strip():
        found.append(f"{GOVERNING} carries no criterion, which is where its consumer "
                     "lists are held")
    else:
        lists = read_lists(ctx.reg.accept_text[GOVERNING])
        found += lists.faults

    # the surfaces, fail-closed at every reading
    found += [f"{name} is not in the checker's corpus, so the anchors it would carry "
              "go unread" for name in ANCHORED if name not in ctx.corpus]
    read = scan(ctx, excluded, snapshots)
    found += read.undecided
    if not read.surfaces:
        found.append("the index carries no file outside the declared exclusions, so no "
                     "admission surface is read")
    found += [f"the exclusion of {row} ({excluded[row]}) matches no file the index "
              "carries; an exclusion that excludes nothing is a carve-out nobody audits"
              for row in read.unmatched]
    found += [f"the exclusion of {row} carries no reason"
              for row, why in excluded.items() if not why.strip()]
    if snapshots and not read.pins:
        found.append(f"the exclusion of a snapshot's pin entry under "
                     f"{' and '.join(SNAPSHOT_DIRS)} ({SNAPSHOT_PIN}) passes over no line "
                     "citing a lineage; an exclusion that excludes nothing is a carve-out "
                     "nobody audits")
    cited = {c.interim for c in read.citations}
    found += [f"no admission surface cites {interim}'s lineage at all, while "
              f"{GOVERNING} names it; the reading of the lineage names has moved"
              for interim in INTERIMS if interim not in cited]

    # the listed consumers, each resolved and each citing its interim
    riding: dict[str, set[tuple[str, str]]] = {interim: set() for interim in INTERIMS}
    at: dict[tuple[str, str], set[str]] = {}
    for c in read.citations:
        at.setdefault((c.path, c.anchor), set()).add(c.interim)
    for interim, names in lists.consumers.items():
        for name in names:
            sites = _resolve(name, ctx, read)
            if isinstance(sites, str):
                found.append(f"{GOVERNING} lists {name} as a consumer of {interim}, and "
                             f"{sites}")
                continue
            riding[interim].update(sites)
            if not any(interim in at.get(site, set()) for site in sites):
                found.append(
                    f"{GOVERNING} lists {name} as a consumer of {interim}, and nothing "
                    f"at {', '.join(_where(*site) for site in sites)} cites {interim}'s "
                    "lineage; an artifact whose admission cites no verdict of the "
                    "interim does not ride it")

    # every declared fragment, naming exactly one citing line of its anchor
    citing: dict[tuple[str, str], dict[int, str]] = {}
    for c in read.citations:
        citing.setdefault((c.path, c.anchor), {})[c.line] = c.text
    named: set[tuple[str, int]] = set()
    for (path, anchor), declaration in declared.items():
        lines = sorted(citing.get((path, anchor), {}).items())
        if not declaration.fragments:
            found.append(f"{_where(path, anchor)} is declared no premise and names no "
                         "fragment of a line it classifies, so it classifies none")
        by_line: dict[int, list[str]] = {}
        for fragment in declaration.fragments:
            if not fragment.strip():
                found.append(f"{_where(path, anchor)} declares a blank fragment, which "
                             "names every line and so none")
                continue
            on = [line for line, text in lines if fragment in text]
            if not on:
                found.append(
                    f"{_where(path, anchor)} declares the fragment '{fragment}', and no "
                    "line there citing an interim's lineage carries it; a fragment "
                    "naming no citing line is a carve-out nobody audits")
            elif len(on) > 1:
                found.append(
                    f"{_where(path, anchor)} declares the fragment '{fragment}', which "
                    f"lines {', '.join(map(str, on))} there all carry, so it names none "
                    "of them; a fragment is a substring of one citing line only")
            else:
                by_line.setdefault(on[0], []).append(fragment)
        for line, fragments in by_line.items():
            named.add((path, line))
            if len(fragments) > 1:
                found.append(
                    f"{_where(path, anchor, line)} is named by {len(fragments)} declared "
                    f"fragments ({'; '.join(fragments)}); one fragment names one line")

    # every citation, a consumer or a declared non-premise
    unresolved: dict[tuple[str, int, str, str], list[str]] = {}
    unnamed: set[tuple[str, int, str, str]] = set()
    for c in read.citations:
        site = (c.path, c.anchor)
        if site in riding[c.interim]:
            continue
        declaration = declared.get(site)
        key = (c.path, c.line, c.anchor, c.interim)
        if declaration is not None and c.interim in declaration.interims:
            if (c.path, c.line) in named:
                continue
            unnamed.add(key)
        unresolved.setdefault(key, []).append(c.token)
    for key, tokens in unresolved.items():
        path, line, anchor, interim = key
        cites = (f"{_where(path, anchor, line)} cites {', '.join(dict.fromkeys(tokens))} "
                 f"of {interim}'s lineage")
        if key in unnamed:
            found.append(
                f"{cites} on a line none of the fragments {HOME} declares for its anchor "
                f"names, so it is neither a consumer {GOVERNING} lists for {interim} nor "
                "a declared non-premise; a declaration classifies the lines it names, and "
                "a line resting on the interim is entered in that list")
        else:
            found.append(
                f"{cites} and is neither a consumer {GOVERNING} lists for {interim} nor a "
                f"non-premise {HOME} declares; an admission riding the interim is entered "
                "in that list, and one riding nothing is declared there with its reason")

    # every declaration, answered by a citation and not also a consumer
    for (path, anchor), declaration in declared.items():
        if not declaration.reason.strip():
            found.append(f"{_where(path, anchor)} is declared no premise with no reason")
        for interim in declaration.interims:
            if (path, anchor) in riding.get(interim, set()):
                found.append(f"{_where(path, anchor)} is both a consumer {GOVERNING} lists "
                             f"for {interim} and a non-premise {HOME} declares; one of "
                             "the two is wrong")
            elif interim not in at.get((path, anchor), set()):
                found.append(
                    f"{_where(path, anchor)} is declared no premise of {interim} "
                    f"({declaration.reason}), and nothing there cites {interim}'s "
                    "lineage; a declaration that classifies nothing is a carve-out "
                    "nobody audits")

    listed = sum(len(names) for names in lists.consumers.values())
    ok = (f"the {len(read.citations)} citations of {FSTAR}'s and {EASYCRYPT}'s lineages "
          f"on {read.surfaces} admission surfaces are each a consumer {GOVERNING} lists "
          f"({listed} listed) or on a line one of {len(declared)} declared non-premises "
          f"names by fragment ({sum(len(d.fragments) for d in declared.values())} "
          f"fragments), with {read.pins} snapshot pin entries passed over")
    return found, ok


def run(ctx: Context) -> None:
    rep = ctx.rep
    rep.line(HEADING)
    found, ok = decide(ctx, EXCLUDED, NON_PREMISE, snapshots=True)
    rep.report("K-114", "citation(s) of an interim anchor's lineage that R-05-022's "
               "consumer lists do not account for:", found, ok)
    rep.line()
