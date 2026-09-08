# SPDX-License-Identifier: Apache-2.0
"""The citation index the proof artifacts already carry: what each `.v` cites, and what
each defines.

Every shipped proof opens by arguing from the register, and the arguments name
requirement ids in bulk. Nothing read them. That is a whole coverage question answered
for free, because the ids are already written down: which artifacts a register edit
re-opens is a scan away, where before it was a grep somebody had to remember to make.
This is that scan, held here rather than at its callers because two of them make it,
[the citations check](checks/citations.py) and [run.py blast](cli/blast.py), and *a
parse two tools make is written once*. Its halves are named for what they read
out of one artifact, and the module is named for the citation, which is the half the
first rule stood over.

**It is lexical and it stays lexical.** A requirement id inside a comment and a
`Theorem <name>` opening a sentence are not Gallina and need no Gallina parser, which
is exactly what lets the host wave decide them in CI on a clone with no prover
toolchain installed. What a term *means*, what a theorem quantifies over, whether a
witness inhabits a type: those are the prover's, they are decided in the guest by
[run.py proofs](cli/proofs.py), and nothing here approximates one of them. The name
says which half this is.

**The halves are read differently and priced differently**, and the split is the
point rather than an accident of implementation.

The **citation** half is one whole-text `re.findall` per file, and reading the bytes off
disk is the larger half of what it costs. It needs no comment stripping at all, and that
is a property of the language rather than of today's files: a Gallina identifier cannot
carry a hyphen, so a `R-nn-nnn` token in a `.v` is inside a comment or a string literal
by construction and never a name the prover binds. The scan shape matters and it inverts
the usual intuition: measured over the shipped tree when this landed, a whole-text
`findall` ran in 1.1 ms where line iteration with a regex per line took 15.3 ms and line
iteration behind a prefix prefilter took 11.0 ms, because the C-level engine over one
large string beats a Python-level walk of sixty thousand lines. That is the reversal
[the tools' scan-shape rule](../README.md) warns is decided by timing rather than by
reading.

The **constant** half is not on that budget. It reads a sentence's opening vernacular,
so it has to know where the comments end, and `vos.proofs.sentences` is a character
walk costing about 400 ms over the same tree. That is nothing beside the prover run the
proof gate pays it inside, and it is two orders of magnitude above what one rule of
`check.py` may spend, so it is computed for the artifacts a query actually asks about
and never for the whole tree on the host wave. Nothing here caches it: a caller that
wants it says so by calling for it.

The **discharge** half is the third, and it is on the citation half's budget rather
than the constant half's, which is the whole of why it is written the way it is. A
discharge annotation is `(*| discharges: R-07-015, R-15-007i |*)` on its own line
immediately above a top-level statement, and what it says is that *this constant claims
to answer those entries*. That is a strictly stronger claim than the file-level
citation beside it, which says only that the entry informed the artifact, and the two
are kept apart in every name here for that reason: a citation is a bibliography and a
discharge is a debt. **Neither is evidence that the theorem states the obligation.**
Whether the sentence a constant proves is the sentence the entry demands is a reading,
it belongs to the review gate R-05-150 fixes and to the residue R-17-016 declares, and
nothing in this module or in any rule over it approximates it.

It is read with one whole-text `str.find` for the opening marker and one anchored
attempt per hit, which is the shape the citation half's timing argues for and not a
second walk of the sentences: the constant a discharge names is the one on the line
*below* it, so the vernacular and the name are read off that line rather than looked up
in the definition index. That is what keeps a rule over this at a few milliseconds
instead of at the half-second the definition index costs, and it is also where the
reading stops. A statement written inside an enclosing comment reads here exactly as one
the file binds, because telling those apart is what comment stripping is for; that
residue is declared at the rule and is not closed by anything cheaper.

**Fail-closed on the marker rather than on the form.** Every `(*|` in a proof artifact
is taken to be an attempt at an annotation, so one that will not parse comes back as a
fault instead of being skipped as an ordinary comment. The alternative reading, taking
only what matches and passing over the rest, makes a mistyped annotation invisible in
exactly the way an unread citation was invisible before this module existed. The price
is stated rather than hidden: a proof artifact that *writes the form out in its own
prose*, to explain the convention to a reader, is committing a fault by this reading and
has to spell the marker some other way. That is the trade a marker-level floor buys, and
it is the cheap direction to be wrong in, because the fault names the line.

**A note on the name, because this module was called `evidence.py` first and the
rename is the interesting part.** `vos/<name>.py` beside `vos/cli/<name>.py` is a
convention here rather than a coincidence: `proofs`, `coread`, `ring`, `oracle` and
`differential` all pair that way, and in every one of them the `vos/` module is the
shared machinery behind the command of that name. So a `vos/evidence.py` would not
merely collide with [cli/evidence.py](cli/evidence.py), the guest's exit-evidence
sweep; it would make a false promise in the repository's own vocabulary, saying *this
is the machinery behind that sweep*, and a reader looking for the sweep's
implementation would find this file first and the real one second. `proofcites` breaks
no convention and says what it holds.
"""

import re
from pathlib import Path
from typing import cast

from vos.proofs import sentences
from vos.register import REQ_TOKEN_RE

# The shipped proof artifacts, as the directory holding them and the kind they are.
PROOFS = "proofs"
SUFFIX = ".v"

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
_MODIFIERS = r"(?:#\[[^\]]*\]\s*)?(?:Local\s+|Global\s+|Program\s+)*"
_DEFINED_RE = re.compile(rf"^{_MODIFIERS}(?:{'|'.join(DEFINERS)})\s+([\w']+)")

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
    rf"[^\S\r\n]*{_MODIFIERS}(?P<vernac>[A-Za-z]+)[^\S\r\n]+(?P<name>[\w']+)")

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


def ids(text: str) -> list[str]:
    """Every requirement citation one artifact makes, in the order it makes them.

    Repeats are kept: how often an artifact argues from an entry is the caller's to
    count, and a set here would silently answer a different question.
    """
    # `findall` over a pattern with no group hands back the whole matches, which are
    # strings; the cast says so, where rebuilding the list to prove it would be a
    # Python-level pass over every hit for nothing.
    return cast("list[str]", REQ_TOKEN_RE.findall(text))


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
    at, line = 0, 1
    while (mark := text.find(DISCHARGE_OPEN, at)) >= 0:
        line += text.count("\n", at, mark)
        at = mark + len(DISCHARGE_OPEN)
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
