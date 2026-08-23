# SPDX-License-Identifier: Apache-2.0
"""The pairing between a register entry and the prose it was extracted from.

The register is normative and [spec.md](../../docs/spec.md) is its rationale, and the
two are held together already: every entry derives a bookmark, every bookmark names a
live requirement, and the traces group decides both directions. What none of that
reaches is whether the pair still says the same thing. A bookmark cannot go stale, but
the paragraph *under* it can be rewritten while the entry it was extracted from stays
as it was, and nothing in the tool notices, because every reference still resolves.

That gap is not the one it looks like. The obvious reading is that the two documents
are copies of one text kept in step by hand, and the obvious repair is to generate one
from the other. Measured over the corpus, they are not copies at all: six-word-shingle
coverage of an entry's text found in its own prose span runs to a median of 0.23, the
longest verbatim run to a median of thirteen words, and 92k words of entries stand
against 146k words of spanned prose. There is nothing to transclude. The two are one
obligation written twice on purpose, once as prose a person reads to understand the
design and once as an atomic claim a reviewer can agree or disagree with alone, and
deleting either would delete something the other never carried.

So what is owed is not derivation but **co-currency**: when one side of a pair moves,
the other is owed a reading. This module computes the pair and reduces each side to a
digest; `checks/coread.py` decides the rule over them and `tools/co-read.py` is where a
person does the reading and records it.

**A co-read is a judgment, so it is recorded and never repaired.** tools/README.md
draws the line this obeys: *arithmetic is repaired, judgment is reported; a figure that
is a sum over an artifact is rewritten under `--fix`, a figure that is somebody's
decision is left standing as a finding, because absorbing it would delete the
decision.* Whether an entry still says what its prose says is exactly such a decision,
and there is no artifact to recompute it from, so `--fix` does not touch this ledger.

**What the pair is.** An entry's prose is what its trace cites, which for almost every
entry is the bookmark its own id derives, and the register's rule is already that a
trace is written out only where it departs from that. Following the trace rather than
the derived form alone is what makes the reading uniform: four entries (R-05-151a and
R-13-010c/d/e) cite a neighbour's bookmark instead of one of their own, and they pair
through their trace exactly as every other entry pairs through its id.

**What a bookmark owns.** The prose declares a bookmark at the end of the line whose
claim it marks, and the lines below it that continue that claim carry no bookmark of
their own. So a bookmark owns from its own line up to the next bookmark's line, or to
the next heading, whichever comes first; bookmarks sharing a line share its span, which
is what `- **G1** ... <a id="r-01-001"></a><a id="r-01-006"></a>` means. Adding a
sentence between two bookmarks moves one span, which is the locality this rule needs to
be an agenda rather than a nag: measured over the last twenty-two commits touching the
prose, a commit dirties a median of four spans.
"""

import contextlib
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from .corpus import ANCHOR_RE, PROSE, Corpus
from .register import Register

LEDGER = "tools/co-read.json"

# A trace departs from the derived form by citing a bookmark in the prose; this is that
# citation, and it is the register's own trace shape rather than a general link.
_TRACE_ANCHOR_RE = re.compile(r"\(spec\.md#([^)]+)\)")

# r-15-005-3 is the third place the prose carries r-15-005's bookmark, not a fourth
# requirement. The suffix is stripped to find the id a span belongs to.
_CITATION_SUFFIX_RE = re.compile(r"^(r-\d\d-\d+[a-z]?)-\d+$")

_PROSE_ID_RE = re.compile(r"^r-\d\d-\d")

# Whitespace is collapsed and the bookmark tags themselves are dropped, so a reflowed
# paragraph and a moved anchor are not edits to the claim. Nothing else is normalized:
# a digest that forgave emphasis or punctuation would forgive the edits that use them.
_TAG_RE = re.compile(r'<a id="[^"]*"></a>')

# Long enough that a collision across some thousands of entries is not a thing to think
# about, short enough that a ledger row stays readable in a diff.
_DIGEST_CHARS = 12

# The conferral lines belong to the entry, and they are read in a fixed order rather
# than in the order the parse happened to collect them, so a digest depends on the
# entry's text and never on a dictionary's insertion order.
_CONFERRAL_KINDS = ("Fail-closed", "RoT-fresh")


def digest(text: str) -> str:
    """One side of a pair, reduced to what a comparison needs.

    The collapse is `str.split` with no argument, which is the whitespace-run split
    and strip in one pass; the 1338 recorded digests pin this flattening exactly, so
    any change here must be proven byte-identical over every live side or it dirties
    the whole ledger at once.
    """
    flat = " ".join(_TAG_RE.sub(" ", text).split())
    return hashlib.sha256(flat.encode("utf-8")).hexdigest()[:_DIGEST_CHARS]


def spans(corpus: Corpus) -> dict[str, str]:
    """Every prose bookmark, and the text it owns.

    Fenced lines are skipped for the same reason the corpus skips them everywhere: an
    anchor a fence displays is text and not a bookmark, and the traces group already
    reports one as buried.
    """
    doc = corpus.by_name[PROSE]
    lines = doc.lines

    # anchors in document order, grouped by the line declaring them
    at: dict[int, list[str]] = {}
    for m in ANCHOR_RE.finditer(doc.raw):
        i = doc.line_of(m.start())
        if not doc.fenced[i]:
            at.setdefault(i, []).append(m.group(1))

    starts = sorted(at)
    out: dict[str, str] = {}
    for n, start in enumerate(starts):
        stop = starts[n + 1] if n + 1 < len(starts) else len(lines)
        end = start + 1
        while end < stop and not lines[end].startswith("#"):
            end += 1
        text = "\n".join(lines[start:end])
        for ident in at[start]:
            out[ident] = text
    return out


def _bookmarks(by_span: dict[str, str], reg: Register) -> dict[str, list[str]]:
    """Every requirement's prose bookmarks, in the order the prose side joins them.

    This is the pairing rule stated once, without the text: the one bookmark an id
    derives, the further places the prose carries that same bookmark under a `-n`
    suffix, and any bookmark a written-out trace names. `pairs` reads it to build the
    digested text and `co-read.py --where` reads it to say where a pair lives, so the
    two cannot come to disagree about which bookmarks a pair reaches.
    """
    # base id -> the bookmarks carrying it, so the `-n` repeats are found once for the
    # whole register instead of by scanning every bookmark for every entry
    carried: dict[str, list[str]] = {}
    for ident in by_span:
        if _PROSE_ID_RE.match(ident):
            carried.setdefault(_CITATION_SUFFIX_RE.sub(r"\1", ident), []).append(ident)

    out: dict[str, list[str]] = {}
    for ident in reg.ids:
        derived = "r" + ident[1:].lower()
        targets = set(carried.get(derived, ()))
        trace = reg.trace_of.get(ident, "")
        if "(spec.md#" in trace:
            targets.update(a for a in _TRACE_ANCHOR_RE.findall(trace) if a in by_span)
        out[ident] = sorted(targets)
    return out


def bookmarks(corpus: Corpus, reg: Register) -> dict[str, list[str]]:
    """The pairing rule over a loaded corpus, for a caller holding no span table."""
    return _bookmarks(spans(corpus), reg)


def pairs(corpus: Corpus, reg: Register) -> dict[str, tuple[str, str]]:
    """Every requirement, as the prose it cites and the entry it is.

    The prose side is the union of every bookmark the entry actually reaches, in the
    fixed order `_bookmarks` states. An entry reaching none of them pairs with the
    empty string, which the rule reports rather than passes: it means the traces group
    found a citation that resolves and this one found no prose behind it.
    """
    by_span = spans(corpus)
    marks = _bookmarks(by_span, reg)
    return {ident: ("\n".join(by_span[t] for t in marks[ident]), entry_text(reg, ident))
            for ident in reg.ids}


def entry_text(reg: Register, ident: str) -> str:
    """The entry as the ledger reads it: what it obliges, and what decides it.

    The trace is left out. It is derived from the id and already decided in both
    directions by the traces group, so folding it in would ask for a re-reading of the
    prose every time a crown-jewel target was added, which is a change to what the
    entry constrains and not to what it says.
    """
    parts = [reg.body.get(ident, ""), reg.accept_text.get(ident, "")]
    parts += [reg.confers.get(kind, {}).get(ident, "") for kind in _CONFERRAL_KINDS]
    return " ".join(p for p in parts if p)


def current(corpus: Corpus, reg: Register) -> dict[str, tuple[str, str]]:
    """Every requirement's pair, as the two digests standing today."""
    return {i: (digest(p), digest(e)) for i, (p, e) in pairs(corpus, reg).items()}


def read_ledger(root: Path) -> dict[str, tuple[str, str]]:
    """The recorded co-reads, or an empty ledger where the file is absent or damaged.

    A ledger that will not parse is reported by the rule as every pair being unread,
    which is the honest reading: nothing in it can be relied on to say a pair was ever
    looked at.
    """
    path = root / LEDGER
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {k: (v[0], v[1]) for k, v in raw.items()
            if isinstance(v, list) and len(v) == 2}


def write_ledger(root: Path, rows: dict[str, tuple[str, str]]) -> None:
    """One requirement per line, in the register's own order where the caller kept it.

    Hand-formatted rather than `json.dumps(indent=...)`, which would break each pair
    across three lines and make a diff of the blessings unreadable. One line per
    requirement is what makes `git diff` on this file say exactly which pairs were read.

    A write that would change nothing is skipped, so a re-bless of a current pair
    leaves the ledger's bytes and mtime alone and the bless path has a fixpoint a
    byte comparison can prove. The write that does land goes through a temporary
    file beside the ledger and one `os.replace`, so a crash mid-write leaves the
    recorded blessings standing rather than a truncated file `read_ledger` maps to
    an empty ledger.
    """
    body = ",\n".join(f'  {json.dumps(k)}: [{json.dumps(p)}, {json.dumps(e)}]'
                      for k, (p, e) in rows.items())
    text = "{\n" + body + "\n}\n" if rows else "{}\n"
    path = root / LEDGER
    with contextlib.suppress(OSError):
        if path.read_bytes() == text.encode("utf-8"):
            return
    fd, staged = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        Path(staged).replace(path)
    except BaseException:
        with contextlib.suppress(OSError):
            Path(staged).unlink()
        raise
