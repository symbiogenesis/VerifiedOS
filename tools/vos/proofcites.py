# SPDX-License-Identifier: Apache-2.0
"""The citation index the proof artifacts already carry: what each `.v` cites, and what
each defines.

Every shipped proof opens by arguing from the register, and the arguments name
requirement ids in bulk. Nothing read them. That is a whole coverage question answered
for free, because the ids are already written down: which artifacts a register edit
re-opens is a scan away, where before it was a grep somebody had to remember to make.
This is that scan, held here rather than at its callers because two of them make it,
[the citations check](checks/citations.py) and [run.py blast](cli/blast.py), and *a
parse two tools make is written once*. Its two halves are named for what they read
out of one artifact, and the module is named for the half that has a rule under it.

**It is lexical and it stays lexical.** A requirement id inside a comment and a
`Theorem <name>` opening a sentence are not Gallina and need no Gallina parser, which
is exactly what lets the host wave decide them in CI on a clone with no prover
toolchain installed. What a term *means*, what a theorem quantifies over, whether a
witness inhabits a type: those are the prover's, they are decided in the guest by
[run.py proofs](cli/proofs.py), and nothing here approximates one of them. The name
says which half this is.

**The two halves are read differently and priced differently**, and the split is the
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

**A derived region is transcription and not citation, and the citation half holds it
out.** A proof artifact's header argues from the register in prose somebody maintains,
and the standing proposal is to replace the transcribed part of it with a delimited
region a repair writes from the cited entries' own normative lines. That region cannot
be read as citation, because a register entry line cites other entries: a transcription
would make an artifact cite everything it merely quotes, and the next regeneration would
transcribe those in turn. Measured over the shipped tree, one such pass introduces 43
ids `DischargeSequence.v` does not cite and 22 `PartitionContext.v` does not, and
repeating it converges at 200 and 77 against the 26 and 38 each genuinely makes. So
`ids` skips what sits between the delimiters, `derived` is where that reading is made,
and [the citations check](checks/citations.py)'s K-108 is what stops the exclusion
widening past a transcription. The exclusion is one substring pre-test on the artifacts
carrying no region, which is all of them today.

The **constant** half is not on that budget. It reads a sentence's opening vernacular,
so it has to know where the comments end, and `vos.proofs.sentences` is a character
walk costing about 400 ms over the same tree. That is nothing beside the prover run the
proof gate pays it inside, and it is two orders of magnitude above what one rule of
`check.py` may spend, so it is computed for the artifacts a query actually asks about
and never for the whole tree on the host wave. Nothing here caches it: a caller that
wants it says so by calling for it.

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
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from vos.proofs import sentences
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
    stray = text.count(DERIVED_MARK) - read
    if stray:
        faults.append(f"{stray} occurrence(s) of `{DERIVED_MARK}` are neither a BEGIN "
                      "nor an END this parse reads, so a region may be delimited by a "
                      "marker nothing excludes")

    return Derived((), tuple(faults)) if faults else Derived(tuple(spans), ())


def ids(text: str) -> list[str]:
    """Every requirement citation one artifact makes, in the order it makes them.

    Repeats are kept: how often an artifact argues from an entry is the caller's to
    count, and a set here would silently answer a different question.

    What a derived region holds is transcription rather than citation and is skipped,
    for the reason the module docstring states: an entry line cites other entries, so a
    region read as citation feeds itself on every regeneration. An artifact whose
    delimiters do not balance carries no region here, so the whole of it is read and
    the imbalance is `derived`'s fault for the caller to report.
    """
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


def citations(pairs: list[tuple[str, str]]) -> dict[str, set[str]]:
    """The citation index: each artifact against the requirements it names."""
    return {rel: set(ids(text)) for rel, text in pairs}


def constants(pairs: list[tuple[str, str]]) -> dict[str, list[str]]:
    """The definition index: each artifact against the constants it binds, in order."""
    return {rel: names(text) for rel, text in pairs}


def citing(index: dict[str, set[str]], ident: str) -> list[str]:
    """The artifacts citing one requirement, in the index's own order."""
    return [rel for rel, cited in index.items() if ident in cited]
