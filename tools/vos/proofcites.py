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


def citations(pairs: list[tuple[str, str]]) -> dict[str, set[str]]:
    """The citation index: each artifact against the requirements it names."""
    return {rel: set(ids(text)) for rel, text in pairs}


def constants(pairs: list[tuple[str, str]]) -> dict[str, list[str]]:
    """The definition index: each artifact against the constants it binds, in order."""
    return {rel: names(text) for rel, text in pairs}


def citing(index: dict[str, set[str]], ident: str) -> list[str]:
    """The artifacts citing one requirement, in the index's own order."""
    return [rel for rel, cited in index.items() if ident in cited]
