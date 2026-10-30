# SPDX-License-Identifier: Apache-2.0
"""Ordinary Markdown pointers use pinned offline Lychee validation.

The licence-text check separately requires that redistributed terms belong to the
Git index. A file existing on disk does not establish that this repository ships
it.
"""

import re
import subprocess
from collections.abc import Iterator
from pathlib import PurePosixPath
from typing import TYPE_CHECKING

from vos import lychee
from vos.corpus import Document

# `Context` lives in this package's __init__, which imports this module in turn.
# Guarded, so the annotation below costs no import at run time: under PEP 649 an
# annotation is not evaluated unless something asks for it, and nothing here does.
if TYPE_CHECKING:
    from . import Context

HEADING = "=== links: every cross-reference against what it points at ==="

# The two tables of THIRD-PARTY.md whose last column names where a component's terms
# arrive. The other tables on that page are deliberately out of reach: the submodule
# table names terms without naming a file this tree carries, and the read-ahead tables
# name a file inside an upstream nothing here tracks, which is what "read ahead"
# means.
THIRD_PARTY = "THIRD-PARTY.md"
LICENCE_TABLES = ("Vendored, and redistributed here", "Fetched at build time")
LICENCE_COLUMN = "License text"

_CELL_PATH_RE = re.compile(r"`([^`]+)`")
_CELL_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s#]+)\)")
_H2_RE = re.compile(r"## +(.*)")


def _licence_texts(ctx: Context) -> tuple[list[tuple[int, str, bool]], list[str]]:
    """Every path THIRD-PARTY.md names as a component's licence text, with its line.

    Fail-closed in the reading, which matters more here than in most of this group:
    the claim is about redistribution, so a table this rule cannot find has to be a
    finding rather than a comparison made against an empty set. The page missing, a
    named section missing, a section carrying no table, and a table whose last column
    is no longer the licence text are four separate stops, each worded as itself.

    The third member of each tuple says whether the cell wrote a link, because a link
    at a file that is not there at all is K-12's finding, so the same missing file
    is not reported twice.
    """
    doc = ctx.corpus.get(THIRD_PARTY)
    if doc is None:
        return [], [f"{THIRD_PARTY} is not in the repository, so no component's "
                    "licence text can be located at all"]

    found: list[tuple[int, str, bool]] = []
    faults: list[str] = []
    for wanted in LICENCE_TABLES:
        rows = [(i, line) for i, line in _table_rows(doc, wanted)]
        if not rows:
            faults.append(f"{THIRD_PARTY} carries no table under '{wanted}', so the "
                          "components it lists cannot be read")
            continue
        header = [c.strip() for c in rows[0][1].strip().strip("|").split("|")]
        if not header or header[-1] != LICENCE_COLUMN:
            faults.append(f"{THIRD_PARTY}:{rows[0][0] + 1} the '{wanted}' table's last "
                          f"column is '{header[-1] if header else ''}' and not "
                          f"'{LICENCE_COLUMN}', so this rule is reading the wrong cell")
            continue
        for i, line in rows[2:]:
            cell = line.strip().strip("|").split("|")[-1].strip()
            link = _CELL_LINK_RE.search(cell)
            if link:
                found.append((i + 1, resolve(THIRD_PARTY, link.group(1)), True))
                continue
            paths = _CELL_PATH_RE.findall(cell)
            if not paths:
                faults.append(f"{THIRD_PARTY}:{i + 1} names no licence text at all, so "
                              "the row claims a component and locates its terms nowhere")
                continue
            found += [(i + 1, resolve(THIRD_PARTY, p), False) for p in paths]
    return found, faults


def _table_rows(doc: Document, heading: str) -> Iterator[tuple[int, str]]:
    """The `|`-led lines of the first table under a `##` heading, header row first."""
    inside = False
    started = False
    for i, line in enumerate(doc.lines):
        if doc.fenced[i]:
            continue
        if m := _H2_RE.match(line):
            if started:
                return
            inside = m.group(1).strip() == heading
            continue
        if not inside:
            continue
        if line.startswith("|"):
            started = True
            yield i, line
        elif started:
            return


def resolve(base: str, target: str) -> str:
    """A relative link target, against the document that carries it and not the root."""
    if not target:
        return base
    parts: list[str] = []
    for part in (PurePosixPath(base).parent / target).parts:
        if part == "..":
            if parts:
                parts.pop()
        elif part != ".":
            parts.append(part)
    return "/".join(parts)


def run(ctx: Context) -> None:
    rep, corpus = ctx.rep, ctx.corpus
    rep.line(HEADING)

    try:
        dead = lychee.findings(ctx.root, [doc.name for doc in corpus.docs], corpus.gitlinks)
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        dead = [f"ordinary link validation could not complete: {exc}"]
    rep.report("K-12", "dead link(s):", dead,
               "every link resolves to a file, and every fragment to a bookmark or heading")

    # The membership is the index and not the filesystem, which is the whole of what
    # separates this from K-12: a licence file present but untracked is one this
    # repository does not redistribute, so the page's claim over it is false while the
    # file sits right there. `tracked` is the index's own listing, so a licence text
    # staged for deletion reports here before the deletion lands.
    texts, faults = _licence_texts(ctx)
    tracked = set(corpus.tracked)
    findings = list(faults)
    for line, path, was_link in texts:
        if path in tracked:
            continue
        if was_link and not (ctx.root / path).exists():
            continue                           # K-12's finding; not priced twice
        findings.append(
            f"{THIRD_PARTY}:{line} locates a component's licence text at {path}, which "
            "the index does not carry, so the page claims to redistribute terms this "
            "repository does not ship")
    ctx.shared["licence_texts"] = len(texts)
    rep.report("K-80", "licence text(s) the repository does not carry:", findings,
               f"all {len(texts)} licence texts the third-party page locates are "
               "tracked files")
    rep.line()
