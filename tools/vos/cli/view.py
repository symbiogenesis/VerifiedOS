#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Weave the specification and the register into one generated reading view.

    tools/run.py view                 # writes out/spec-woven.md
    tools/run.py view --out PATH      # writes somewhere else

The two documents are one obligation written twice on purpose: prose a person
reads to understand the design, and atomic entries a reviewer decides alone,
paired by bookmark and held co-current by K-61. What neither file gives a reader
is the join. This tool derives it: the specification's text verbatim, with every
register entry rendered as a quoted block directly beneath the bookmark that
cites it, and a pointer wherever a later `-n` bookmark cites the same entry
again. An entry with no bookmark of its own (the written-out-trace departures)
renders beneath the bookmark its trace names, exactly where its co-read pair
already reads it.

The view is derived and disposable, never a source: it is written outside the
corpus into an ignored directory, it opens by saying so, and regenerating it is
the only way to change it. Deriving in this direction costs nothing the other
direction would have cost: the placement is the pairing rule `vos/coread.py`
already states, so the view and the co-read discipline cannot come to disagree
about where an entry belongs.
"""

import argparse
import re
from pathlib import Path

from vos import coread
from vos import corpus as corpus_mod
from vos.corpus import ANCHOR_RE, PROSE, Corpus
from vos.register import REGISTER, read_register

BANNER = (
    "*A generated reading view, never a source: the specification's prose with each "
    "register entry rendered beneath the bookmark that cites it. Derived by "
    "`tools/run.py view` from [spec.md](../docs/spec.md) and "
    "[requirements-register.md](../docs/requirements-register.md); edit those and "
    "regenerate.*"
)

_ENTRY_LEAD_RE = re.compile(r"^\*\*(R-\d\d-\d+[a-z]?)\*\* ")


def _entry_blocks(corpus: Corpus, ids: set[str]) -> dict[str, list[str]]:
    """Each entry's verbatim register lines, quoted for the view.

    The slice is presentation, not a parse of record: an entry's block runs from
    its header line to the blank line ending it, which is the same contiguity the
    register's own conventions state and `read_register` decides.
    """
    doc = corpus.by_name[REGISTER]
    out: dict[str, list[str]] = {}
    i = 0
    while i < len(doc.lines):
        m = _ENTRY_LEAD_RE.match(doc.lines[i])
        if m and m.group(1) in ids and m.group(1) not in out:
            block: list[str] = []
            j = i
            while j < len(doc.lines) and doc.lines[j]:
                block.append("> " + doc.lines[j])
                j += 1
            out[m.group(1)] = block
            i = j
        else:
            i += 1
    return out


def weave(corpus: Corpus) -> tuple[list[str], int, list[str]]:
    """The woven lines, how many entries were placed, and any entry left homeless."""
    reg = read_register(corpus)
    spec = corpus.by_name[PROSE]
    blocks = _entry_blocks(corpus, reg.id_set)
    marks = coread.bookmarks(corpus, reg)

    home: dict[str, list[str]] = {}      # bookmark -> entries rendered beneath it
    repeats: dict[str, list[str]] = {}   # bookmark -> entries it cites again
    homeless: list[str] = []
    for ident in reg.ids:
        targets = marks.get(ident, [])
        if not targets or ident not in blocks:
            homeless.append(ident)
            continue
        base = "r" + ident[1:].lower()
        anchor = base if base in targets else targets[0]
        home.setdefault(anchor, []).append(ident)
        for other in targets:
            if other != anchor:
                repeats.setdefault(other, []).append(ident)

    # every unfenced anchor, in order of appearance on its line
    at: dict[int, list[str]] = {}
    for m in ANCHOR_RE.finditer(spec.raw):
        i = spec.line_of(m.start())
        if not spec.fenced[i]:
            at.setdefault(i, []).append(m.group(1))

    lines: list[str] = [BANNER, ""]
    placed = 0
    for i, line in enumerate(spec.lines):
        lines.append(line)
        for anchor in at.get(i, ()):
            for ident in home.get(anchor, ()):
                lines.append("")
                lines.extend(blocks[ident])
                placed += 1
            cited = repeats.get(anchor, ())
            if cited:
                # direction-neutral on purpose: a -n repeat may precede its base
                # bookmark in the prose (r-12-035-2 does), so "above" would misdirect
                lines.append("")
                lines.append("> ↳ cited here again: " + ", ".join(cited)
                             + ", stated in full at their own bookmarks.")
    if homeless:
        lines += ["", "## Entries no bookmark places", ""]
        for ident in homeless:
            lines.append("")
            lines.extend(blocks.get(ident, [f"> **{ident}** (block unreadable)"]))
    return lines, placed, homeless


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Weave the specification and the register into one reading view.")
    parser.add_argument("--out", metavar="PATH",
                        help="where to write the view (default: out/spec-woven.md)")
    args = parser.parse_args(argv)

    root = corpus_mod.find_root()
    corpus = corpus_mod.load(root)
    out_path = Path(args.out) if args.out else root / "out" / "spec-woven.md"

    lines, placed, homeless = weave(corpus)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")

    print(f"wove {placed} entries into the prose -> {out_path}")
    if homeless:
        print(f"{len(homeless)} entries reach no bookmark and are appended at the "
              f"end: {', '.join(homeless)}")
    return 0

